"""Burst-trap / recovery / hysteresis / stability detection, following the simulator's definitions.

Definitions ported from ``prefixmeta.runner`` / ``prefixmeta.metrics`` (branch ``pilot/prefix-meta``,
commit 8e71275) and ``configs/prefix_meta.yaml``:

* ``longest_run_below``  : longest run of consecutive windows with value < thresh (NaN breaks a run).
* burst ``trapped``      : after the burst start ``t_b``, the longest run of consecutive complete windows with
                           hit rate < ``trap_hit_below`` (0.2) lasts >= ``trap_min_s`` (10000 s in the simulator).
* ``hit_eval``           : aggregated hit rate over complete windows inside [t_b + hit_eval_from_s, end of run].
* ``recovered``          : ``hit_eval > recovered_hit_above`` (0.8) AND mean queue over the tail window
                           (last ``min(tail_window_s, run/2)`` s) < ``recovered_queue_below`` (20).
* ``stable`` (lambda_cap): final queue < 50, fitted queue rise over the last ``min(5000, run/2)`` s <= 10
                           (OLS slope of the fine queue means x window), and the run was not aborted.
* ramp escape / re-entry : first fine bin with mean queue > 128; then first run of 5 bins with mean queue < 20.

ROLE: since the referee review (notes/REFEREE_prefix_meta.md) this hit-rate rule is the SECONDARY criterion of the
real-engine kill test; the primary one is the throughput-based criterion of ``analysis.trap_v2`` (paired arms).

Additions that the simulator does not have (all reported separately, none silently changes a simulator rule):

* ``good_before``  : the pre-burst state was good (aggregated hit > 0.5, mean queue < 20). A burst can only
                     demonstrate HYSTERESIS if the system was in the good state before it; ``trapped`` without
                     ``good_before`` just means the offered load was already too high.
* ``tail_queue_slope_per_window`` : fitted change per window of the tail queue means; a ``trapped`` run whose
                     slope is clearly negative may be a slow drain rather than a trap (short protocol, see the plan).
* ``trapped_aborted`` : the client aborted the run for overload (in-flight cap) before the trap duration could
                     be observed, and the last ``aborted_trap_last_windows`` complete post-burst windows all had
                     hit rate < ``trap_hit_below``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Sequence

import numpy as np
import pandas as pd

from agentload.config import config_from_dict
from agentload.workload import effective_mean_turns, ramp_rate

from .load import Run
from .params import AnalysisParams

_trapz = getattr(np, "trapezoid", None) or np.trapz


# ---------------------------------------------------------------- primitives
def longest_run_below(values: Sequence[float], thresh: float) -> int:
    """Longest run of consecutive entries with value < thresh (NaN breaks a run)."""
    best = cur = 0
    for v in values:
        if v == v and v < thresh:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def agg_hit(win: pd.DataFrame) -> float:
    """Aggregate hit rate over a set of windows, weighting by turns (or prompt tokens for the token metric)."""
    if len(win) == 0 or "hit_source" not in win.columns:
        return float("nan")
    src = str(win["hit_source"].iloc[0])
    if src == "requests:frac_turns_cached_gt50":
        n = win["n_turns_ok"].sum()
        return float(win["n_cached_gt"].sum() / n) if n else float("nan")
    if src == "requests:token_hit_rate":
        d = win["prompt_tokens"].sum()
        return float(win["cached_tokens"].sum() / d) if d else float("nan")
    return float(np.nanmean(win["hit_rate"])) if win["hit_rate"].notna().any() else float("nan")


def select_windows(win: pd.DataFrame, t_from: float, t_to: float) -> pd.DataFrame:
    """Complete windows with t_start >= t_from and t_end <= t_to (as ``tail_stats`` in the simulator)."""
    return win[(win["t_start"] >= t_from - 1e-9) & (win["t_end"] <= t_to + 1e-9)]


def _nanmean(x: pd.Series) -> float:
    return float(np.nanmean(x)) if len(x) and x.notna().any() else float("nan")


def trend_rise(trace: pd.DataFrame, t_from: float, t_to: float) -> float:
    """OLS slope of the fine queue-mean series on [t_from, t_to) times (t_to - t_from); NaN if < 3 bins."""
    sel = trace[(trace["t_start"] >= t_from - 1e-9) & (trace["t_start"] < t_to - 1e-9) & trace["queue_mean"].notna()]
    if len(sel) < 3:
        return float("nan")
    slope = np.polyfit(sel["t_start"].to_numpy(), sel["queue_mean"].to_numpy(), 1)[0]
    return float(slope * (t_to - t_from))


# ---------------------------------------------------------------- burst
def burst_verdict(run: Run, win: pd.DataFrame, p: AnalysisParams) -> Dict[str, Any]:
    """Per-run burst classification (see module docstring). Requires ``run.t_burst`` (from the run's config)."""
    b, W = p.burst, p.window_s
    tb = run.t_burst
    if tb is None:
        raise ValueError(f"{run.dir}: config has no arrivals.burst, cannot classify a burst run")
    end = run.t_end_s
    out: Dict[str, Any] = {"label": run.label, "seed": run.seed, "rate_mult": run.rate_mult, "t_burst": tb,
                           "t_end_s": end, "aborted": run.aborted, "abort_reason": run.abort_reason}
    post = win[win["t_start"] >= tb - 1e-9]
    out["n_post_windows"] = int(len(post))
    run_win = longest_run_below(post["hit_rate"].tolist(), b["trap_hit_below"])
    out["trap_run_s"] = run_win * W
    out["trapped"] = bool(run_win * W >= b["trap_min_s"] - 1e-9)
    ev = select_windows(win, tb + b["hit_eval_from_s"], end)
    out["hit_eval"] = agg_hit(ev)
    out["n_eval_windows"] = int(len(ev))
    tail_len = min(b["tail_window_s"], end / 2.0)
    tail = win[win["t_start"] >= end - tail_len - 1e-9]
    out["tail_queue_mean"] = _nanmean(tail["queue_mean"]) if len(tail) else float("nan")
    out["tail_hit_rate"] = agg_hit(tail)
    qs = tail["queue_mean"].dropna()
    # fitted change of the window-mean queue per 1000 s over the tail windows (< 0 = still draining at the end);
    # NOT in the simulator: needed because the short real-engine protocol cannot wait for the drain to finish
    out["tail_queue_slope_per_window"] = (float(np.polyfit(np.arange(len(qs)), qs.to_numpy(), 1)[0])
                                          if len(qs) >= 3 else float("nan"))
    out["hit_returned"] = bool(out["hit_eval"] == out["hit_eval"] and out["hit_eval"] > b["recovered_hit_above"])
    out["queue_returned"] = bool(out["tail_queue_mean"] == out["tail_queue_mean"]
                                 and out["tail_queue_mean"] < b["recovered_queue_below"])
    out["recovered"] = out["hit_returned"] and out["queue_returned"]
    pre = select_windows(win, b["good_before_from_s"], tb)
    out["n_pre_windows"] = int(len(pre))
    out["pre_hit"] = agg_hit(pre)
    out["pre_queue_mean"] = _nanmean(pre["queue_mean"]) if len(pre) else float("nan")
    out["good_before"] = bool(len(pre) >= 1 and out["pre_hit"] == out["pre_hit"]
                              and out["pre_hit"] > b["good_before_hit_above"]
                              and out["pre_queue_mean"] == out["pre_queue_mean"]
                              and out["pre_queue_mean"] < b["good_before_queue_below"])
    k = int(b["aborted_trap_last_windows"])
    last = post.tail(k)
    out["trapped_aborted"] = bool(run.aborted and len(last) >= 1 and bool((last["hit_rate"] < b["trap_hit_below"]).all()))
    if end < tb:
        verdict = "no_burst"
    elif out["recovered"]:
        verdict = "recovered"
    elif out["trapped"]:
        verdict = "trapped"
    elif out["trapped_aborted"]:
        verdict = "trapped_aborted"
    else:
        verdict = "indeterminate"
    out["verdict"] = verdict
    out["is_trap"] = verdict in ("trapped", "trapped_aborted")
    out["hysteresis_run"] = bool(out["is_trap"] and out["good_before"])
    return out


def kill_table(runs: pd.DataFrame, fraction_min: float, min_runs: int) -> pd.DataFrame:
    """Per (label, rate_mult): counts of runs, traps, traps from a good pre-burst state, recoveries."""
    g = runs.groupby(["label", "rate_mult"], dropna=False)
    t = g.agg(n_runs=("seed", "size"), n_trap=("is_trap", "sum"), n_good_before=("good_before", "sum"),
              n_hysteresis=("hysteresis_run", "sum"), n_recovered=("recovered", "sum"),
              n_aborted=("aborted", "sum")).reset_index()
    t["frac_hysteresis"] = t["n_hysteresis"] / t["n_runs"]
    t["frac_trap_any"] = t["n_trap"] / t["n_runs"]
    t["meets_strict"] = (t["n_hysteresis"] / t["n_runs"] >= fraction_min - 1e-12) & (t["n_runs"] >= min_runs)
    t["meets_loose"] = (t["n_trap"] / t["n_runs"] >= fraction_min - 1e-12) & (t["n_runs"] >= min_runs)
    return t


def kill_verdict(table: pd.DataFrame, p: AnalysisParams, fcfs_substr: str = "fcfs") -> Dict[str, Any]:
    """Kill criterion: no hysteresis = the burst does not trap FCFS in >= 2/3 of runs at ANY rate multiple in the
    open interval (lo, hi). Evaluated per FCFS cell (label containing ``fcfs_substr``); ``strict`` requires the
    pre-burst state to be good (a real hysteresis), ``loose`` counts any trap.

    ``mechanism_transfers_any_fcfs_cell`` is True if some FCFS cell meets the criterion; the plan treats
    ``kill = not mechanism_transfers_any_fcfs_cell`` (all FCFS cells must fail) as an open interpretation."""
    lo, hi = p.kill["lam_mult_open_interval"]
    t = table[table["label"].str.contains(fcfs_substr) & (table["rate_mult"] > lo) & (table["rate_mult"] < hi)]
    cells: Dict[str, Any] = {}
    for label, g in t.groupby("label"):
        cells[label] = {"rate_mults_tested_in_interval": sorted(float(x) for x in g["rate_mult"]),
                        "strict_meets_at": sorted(float(x) for x in g[g["meets_strict"]]["rate_mult"]),
                        "loose_meets_at": sorted(float(x) for x in g[g["meets_loose"]]["rate_mult"])}
    strict_any = any(c["strict_meets_at"] for c in cells.values())
    loose_any = any(c["loose_meets_at"] for c in cells.values())
    return {"interval": [lo, hi], "fraction_min": p.kill["trapped_fraction_min"], "min_runs_per_cell":
            p.kill["min_runs_per_cell"], "cells": cells, "n_fcfs_cells_with_data": len(cells),
            "mechanism_transfers_any_fcfs_cell_strict": strict_any,
            "mechanism_transfers_any_fcfs_cell_loose": loose_any,
            "kill_strict": (not strict_any) if cells else None, "kill_loose": (not loose_any) if cells else None}


# ---------------------------------------------------------------- stability / lambda_cap / ramps
def stable_verdict(run: Run, trace: pd.DataFrame, p: AnalysisParams) -> Dict[str, Any]:
    """Stability of an open-loop run from an empty start (simulator ``stable_verdict``; uses the last complete
    fine bin for the final queue)."""
    s = p.stability
    end = run.t_end_s
    Wt = min(s["stable_trend_window_s"], end / 2.0)
    rise = trend_rise(trace, end - Wt, end)
    q = trace["queue_mean"].dropna()
    final_queue = float(q.iloc[-1]) if len(q) else float("nan")
    fq_ok = bool(final_queue == final_queue and final_queue < s["stable_final_queue_below"])
    rise_ok = bool(rise == rise and rise <= s["stable_trend_max_rise"])
    stable = (not run.aborted) and fq_ok and rise_ok
    return {"label": run.label, "seed": run.seed, "rate_mult": run.rate_mult, "stable": bool(stable),
            "final_queue": final_queue, "trend_rise": rise, "aborted": run.aborted,
            "queue_source": str(trace["source"].iloc[0]) if len(trace) else ""}


def lambda_cap_bracket(by_rate: pd.DataFrame) -> Dict[str, Any]:
    """From per-rate stability counts (columns rate_mult, n_stable, n_runs): the simulator's rule is that a rate is
    stable iff ALL its seeds are stable. Returns the largest all-stable multiple and the smallest unstable multiple
    above it, so R = lambda_cap / lambda_miss lies in that bracket if stability is monotone in the rate
    (``monotone`` False flags a stable rate above an unstable one, i.e. noise or a non-monotone region)."""
    g = by_rate.sort_values("rate_mult").reset_index(drop=True)
    g["all_stable"] = g["n_stable"] == g["n_runs"]
    stable = g[g["all_stable"]]["rate_mult"]
    largest = float(stable.max()) if len(stable) else None
    above = g[(~g["all_stable"]) & (g["rate_mult"] > (largest if largest is not None else -np.inf))]["rate_mult"]
    first_unstable = float(above.min()) if len(above) else None
    first_unstable_any = g[~g["all_stable"]]["rate_mult"]
    monotone = bool(len(first_unstable_any) == 0 or len(stable) == 0 or stable.max() < first_unstable_any.min())
    return {"largest_all_stable_mult": largest, "first_unstable_mult_above": first_unstable, "monotone": monotone,
            "n_rates": int(len(g))}


def ramp_transitions(trace: pd.DataFrame, lam_at: Callable[[float], float], escape_above: float,
                     reenter_below: float, reenter_bins: int, bin_s: float, leg_s: float) -> Dict[str, Any]:
    """Escape / re-entry rates of one ramp run (same definition as the simulator; see module docstring)."""
    nan = float("nan")
    t = trace["t_start"].to_numpy()
    m = trace["queue_mean"].to_numpy()
    out: Dict[str, Any] = {"escaped": False, "escape_time_s": nan, "escape_lambda": nan, "escape_leg": "",
                           "reentered": False, "reentry_time_s": nan, "reentry_lambda": nan}
    idx = np.nonzero(m > escape_above)[0]
    if len(idx) == 0:
        return out
    i0 = int(idx[0])
    te = float(t[i0] + 0.5 * bin_s)
    out.update(escaped=True, escape_time_s=te, escape_lambda=float(lam_at(te)),
               escape_leg="up" if te <= leg_s else "down")
    below = m < reenter_below
    for i in range(i0 + 1, len(m) - reenter_bins + 1):
        if below[i:i + reenter_bins].all():
            out.update(reentered=True, reentry_time_s=float(t[i]), reentry_lambda=float(lam_at(float(t[i]))))
            break
    return out


def hysteresis_area(up: np.ndarray, dn: np.ndarray, lam_up: np.ndarray, lam_dn: np.ndarray,
                    lo: float, hi: float, n_grid: int = 40) -> float:
    """Normalized integral of |f_up(lam) - f_down(lam)| over [lo, hi] (np.interp on a common grid)."""
    grid = np.linspace(lo, hi, n_grid)
    ou, od = np.argsort(lam_up), np.argsort(lam_dn)
    f_up = np.interp(grid, lam_up[ou], up[ou])
    f_dn = np.interp(grid, lam_dn[od], dn[od])
    return float(_trapz(np.abs(f_up - f_dn), grid) / (hi - lo))


def ramp_lam_at(run: Run) -> Callable[[float], float]:
    """Instantaneous arrival rate of a ramp run (sessions/s) from its effective config (needs absolute rates,
    or ramp_is_mult with a numeric lambda_ref)."""
    a = run.cfg["arrivals"]
    scale = 1.0
    if a.get("ramp_is_mult"):
        ref = a["lambda_ref"]
        if not isinstance(ref, (int, float)):
            from agentload.config import resolve_lambda_ref
            ref = resolve_lambda_ref(ref)
        scale = float(ref)
    knots = [(float(t), float(r) * scale) for t, r in a["ramp"]]
    return lambda t: float(ramp_rate(np.array([t]), knots)[0])


# ---------------------------------------------------------------- lambda_miss (closed population, caching off)
def lambda_miss_closed(run: Run, warmup_s: float) -> Dict[str, Any]:
    """Throughput of a closed-population run over [warmup_s, run end): completed sessions/s (the simulator's
    ``lambda_miss``) and the lower-variance turns-based estimate  turns/s / E[min(Geom(1/mean_turns), cap)]."""
    cfg = config_from_dict(run.cfg)
    end = run.t_end_s
    dur = end - warmup_s
    if dur <= 0:
        raise ValueError("warmup_s must be < run length")
    r = run.requests
    ok = r[(r["status"] == "ok") & (r["t_complete"] >= warmup_s) & (r["t_complete"] < end)]
    n_turns = len(ok)
    n_sessions = int((ok["turn"] == ok["n_turns"]).sum())
    et = effective_mean_turns(cfg.workload)
    return {"label": run.label, "seed": run.seed, "warmup_s": warmup_s, "measure_s": dur,
            "sessions_completed": n_sessions, "turns_completed": n_turns,
            "sessions_per_s": n_sessions / dur, "turns_per_s": n_turns / dur,
            "lambda_miss_sessions": n_sessions / dur, "lambda_miss_turns_based": (n_turns / dur) / et,
            "effective_mean_turns": et, "aborted": run.aborted,
            "closed_n": cfg.arrivals.closed_n}
