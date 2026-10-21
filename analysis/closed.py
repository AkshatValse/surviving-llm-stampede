"""Stage C: the closed-population throughput curve mu(n) of the real engine (prefix cache ON).

One run = n sessions kept alive (a finished session is replaced at once), cache on, a fixed schedule policy; warmup
``warmup_s`` discarded, the rest measured. Per run: completions/s (both estimators, see ``analysis.throughput``), hit
fraction (turns whose cached share exceeds the threshold) and token-weighted cached fraction, queue (engine waiting
gauge if present, else client in-flight requests), and the start-state flag.

``mu_curve``: per cell (engine label), mu at every n, argmax_n mu(n) by the configured estimator (both are reported; a
disagreement is flagged), mu(n_inf) with n_inf = 300 standing for mu(infinity), mu_max, whether the n grid is complete,
and how close the runner-up is (one run per n: the argmax is noisy, so a near-tie is flagged ``argmax_ambiguous``).
The top-level ``n_cap`` / ``mu_300`` / ``mu_max`` are those of the PRIMARY cell: the label containing ``fcfs_substr``
with the most distinct n. ``n_cap`` is what ``gate.n_cap = "<dir>/mu_curve.json:n_cap"`` reads for the CAPPED arm.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .hysteresis import lambda_miss_closed
from .load import Run
from .params import AnalysisParams
from .throughput import hit_stats
from .windows import inflight_events, pick_series, queue_trace, step_bins

NAN = float("nan")


def closed_point(run: Run, warmup_s: float, p: AnalysisParams) -> Dict[str, Any]:
    """Stage-C measurements of one closed-population run over [warmup_s, run end)."""
    n = run.closed_n
    if n is None:
        raise ValueError(f"{run.dir}: not a closed-population run (arrivals.kind != closed)")
    base = lambda_miss_closed(run, warmup_s)
    end = run.t_end_s
    h = hit_stats(run, p, warmup_s, end + 1e-9)
    tr = queue_trace(run, p)
    tr = tr[(tr["t_start"] >= warmup_s - 1e-9)]
    q_mean = float(tr["queue_mean"].mean()) if len(tr) and tr["queue_mean"].notna().any() else NAN
    t, v = inflight_events(run.requests) if len(run.requests) else (np.zeros(0), np.zeros(0))
    infl = float(step_bins(t, v, np.array([warmup_s, end]))[0][0]) if len(t) and end > warmup_s else NAN
    name, series = pick_series(run.metrics, p.role("waiting"))
    waiting = float(series[series["t_s"] >= warmup_s]["value"].mean()) if name is not None and len(series) else NAN
    return {"label": run.label, "seed": run.seed, "n": int(n), "run_dir": str(run.dir), "warmup_s": warmup_s,
            "measure_s": base["measure_s"], "sessions_completed": base["sessions_completed"],
            "turns_completed": base["turns_completed"], "mu_sessions": base["sessions_per_s"],
            "mu_turns_based": base["lambda_miss_turns_based"], "turns_per_s": base["turns_per_s"],
            "hit_frac_turns": h["hit_frac_turns"], "hit_frac_followup": h["hit_frac_followup"],
            "cached_frac_tokens": h["cached_frac_tokens"], "cached_available": h["cached_available"],
            "queue_mean": q_mean, "queue_source": str(tr["source"].iloc[0]) if len(tr) else "",
            "engine_waiting_mean": waiting, "client_inflight_mean": infl, "aborted": run.aborted,
            "start_state_verified": run.start_state_verified, "hardware": run.hardware,
            "output_ids_sources": ",".join(sorted(run.output_ids_sources))}


def _cell_curve(g: pd.DataFrame, cp: Dict[str, Any], grid: List[int]) -> Dict[str, Any]:
    est = str(cp["mu_estimator"])
    key = {"sessions": "mu_sessions", "turns_based": "mu_turns_based"}[est]
    by_n = g.groupby("n").agg(n_runs=("seed", "size"), mu_sessions=("mu_sessions", "mean"),
                              mu_turns_based=("mu_turns_based", "mean"), turns_per_s=("turns_per_s", "mean"),
                              hit_frac_turns=("hit_frac_turns", "mean"), hit_frac_followup=("hit_frac_followup", "mean"),
                              cached_frac_tokens=("cached_frac_tokens", "mean"), queue_mean=("queue_mean", "mean"),
                              n_aborted=("aborted", "sum")).reset_index().sort_values("n")
    ns = [int(x) for x in by_n["n"]]
    out: Dict[str, Any] = {"n": ns, "n_runs": [int(x) for x in by_n["n_runs"]]}
    for col in ("mu_sessions", "mu_turns_based", "turns_per_s", "hit_frac_turns", "hit_frac_followup",
                "cached_frac_tokens", "queue_mean"):
        out[col] = [None if x != x else float(x) for x in by_n[col]]
    out["n_aborted_runs"] = int(by_n["n_aborted"].sum())
    am = {}
    for e, col in (("sessions", "mu_sessions"), ("turns_based", "mu_turns_based")):
        vals = by_n[col].to_numpy(dtype=float)
        am[e] = int(by_n["n"].iloc[int(np.nanargmax(vals))]) if np.isfinite(vals).any() else None
    out["argmax_n_by_estimator"] = am
    out["argmax_estimators_agree"] = am["sessions"] == am["turns_based"]
    vals = by_n[key].to_numpy(dtype=float)
    order = np.argsort(-vals, kind="stable")        # ties: the smaller n wins
    out["estimator"] = est
    out["argmax_n"] = int(ns[order[0]]) if len(ns) else None
    out["mu_max"] = float(vals[order[0]]) if len(ns) else None
    if len(ns) >= 2 and vals[order[0]] > 0:
        out["argmax_margin_rel"] = float((vals[order[0]] - vals[order[1]]) / vals[order[0]])
        out["runner_up_n"] = int(ns[order[1]])
        out["argmax_ambiguous"] = bool(out["argmax_margin_rel"] < float(cp["argmax_margin_warn"]))
    else:
        out["argmax_margin_rel"], out["runner_up_n"], out["argmax_ambiguous"] = None, None, True
    n_inf = int(cp["n_inf"])
    out["n_inf"] = n_inf
    out["mu_n_inf"] = float(by_n[by_n["n"] == n_inf][key].iloc[0]) if n_inf in ns else None
    out["missing_n"] = sorted(set(grid) - set(ns))
    out["complete_grid"] = not out["missing_n"]
    out["extra_n"] = sorted(set(ns) - set(grid))
    out["mu_by_n"] = {str(n): float(v) for n, v in zip(ns, vals)}
    out["monotone_non_decreasing_to_argmax"] = bool(all(vals[i] <= vals[i + 1] + 1e-12 for i in range(ns.index(out["argmax_n"]))))
    return out


def mu_curve(points: pd.DataFrame, cp: Dict[str, Any], fcfs_substr: str = "fcfs") -> Dict[str, Any]:
    """The Stage-C summary (see module docstring). ``points`` has one row per run (``closed_point`` dicts)."""
    est = str(cp["mu_estimator"])
    if est not in ("sessions", "turns_based"):
        raise ValueError(f"closed.mu_estimator must be sessions|turns_based, got {est!r}")
    cells: Dict[str, Any] = {}
    for label, g in points.groupby("label"):
        is_lpm = "lpm" in str(label).lower()
        grid = [int(x) for x in (cp["lpm_n"] if is_lpm else cp["n_grid"])]
        cells[str(label)] = _cell_curve(g, cp, grid)
    fc = [(len(c["n"]), lab) for lab, c in cells.items() if fcfs_substr in lab]
    primary = sorted(fc, key=lambda x: (-x[0], x[1]))[0][1] if fc else None
    out: Dict[str, Any] = {"estimator": est, "cells": cells, "primary_label": primary,
                           "fcfs_substr": fcfs_substr, "n_cap": None, "mu_300": None, "mu_max": None, "notes": []}
    if primary is None:
        out["notes"].append(f"no cell label contains {fcfs_substr!r}: n_cap is null (the CAPPED arm needs the FCFS cell)")
    else:
        c = cells[primary]
        out["n_cap"], out["mu_max"], out["mu_300"] = c["argmax_n"], c["mu_max"], c["mu_n_inf"]
        if not c["complete_grid"]:
            out["notes"].append(f"primary cell {primary}: n grid incomplete, missing {c['missing_n']}; n_cap is the argmax "
                                "over the points that exist")
        if c["argmax_ambiguous"]:
            out["notes"].append(f"n_cap={c['argmax_n']} is ambiguous: runner-up n={c['runner_up_n']} is within "
                                f"{cp['argmax_margin_warn']:.0%} (margin {c['argmax_margin_rel']}); one run per n")
        if not c["argmax_estimators_agree"]:
            out["notes"].append(f"argmax differs by estimator {c['argmax_n_by_estimator']}; n_cap uses {est}")
        if c["mu_n_inf"] is None:
            out["notes"].append(f"mu(n={cp['n_inf']}) missing: the recovery threshold cannot be predicted")
    return out
