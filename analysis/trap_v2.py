"""Throughput-based trap criterion and the PASS rule of the paired kill test (kill_verdict_v2.json).

Referee-requested (notes/REFEREE_prefix_meta.md, "Kill-test design changes"); the hit-rate criterion of
``analysis.hysteresis`` is kept as a SECONDARY output. Everything is in sessions and seconds.

Per run, over the post-burst evaluation window  W = [t_b + eval_from_s, end of run]   (t_b = burst time of the paired set;
the NOBURST arm has no burst and uses the recorded ``arrivals.analysis_t_burst_s``):

  lambda        arrival rate of the run (sessions/s);      lambda_miss  the all-miss capacity lambda was set from
  rate          session completion rate over W (estimator ``trap_v2.rate_estimator``: sessions | turns_based)
  slope         OLS slope of the backlog (client sessions in the system INCLUDING the gate queue), on bin means over W

  TRAPPED   iff (a) |rate - lambda_miss| <= rate_tolerance * lambda_miss     (completion stuck at the all-miss capacity)
                AND (b) slope > slope_frac * (lambda - lambda_miss)           (backlog grows at about lambda - lambda_miss)
                [and lambda > lambda_miss: below it no trap is defined; the formula alone would accept a healthy system
                 running at 0.9 * lambda_miss, so this is an explicit extra condition, reported as ``lambda_above_miss``]
  DRAINING  iff slope < 0
  RECOVERED iff hit fraction > recovered_hit_above AND backlog < recovered_backlog_below, both averaged over the last
                end_window_s (the NOBURST arm's "good" is the same predicate)

``state`` is one label: trapped > recovered > draining > indeterminate (a window shorter than ``min_eval_s`` is
``indeterminate``, reason ``window_too_short``). The three flags are written independently as well.

PASS per (cell label, lambda): over seeds, BURST trapped AND NOBURST good AND CAPPED recovered, in >= pass_fraction_min
of the seeds (>= min_seeds seeds present; a seed missing an arm counts as a failure and is listed under ``incomplete``).
The kill test passes if some lambda of an FCFS cell meets this (and, if a pre-registration file is given, lies inside the
registered window). Arms of one (label, lambda, seed) must be common-random-number pairs: ``pairing_problems`` compares
their effective configs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .hysteresis import burst_verdict
from .load import Run
from .params import AnalysisParams
from .throughput import (backlog_at, backlog_mean, backlog_slope, completion_rates, hit_stats, hit_value, pick_rate)
from .windows import window_table

NAN = float("nan")
ARM_ORDER = ("burst", "noburst", "capped")

# Config sections/keys that legitimately differ between the arms of one pair (everything else must be identical).
_ALLOWED_DIFF_PREFIXES = ("arrivals.burst", "gate", "meta.", "output.", "server.base_url", "workload.content_salt",
                          "research_question", "assumptions_note")


def _isnan(x: Any) -> bool:
    return not (isinstance(x, (int, float, np.floating, np.integer)) and x == x)


def _flatten(d: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(d, dict):
        out: Dict[str, Any] = {}
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        if not d:
            out[prefix] = {}
        return out
    return {prefix: d}


def config_diff(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    """Flattened config keys whose values differ (or exist on one side only), minus the keys allowed to differ between
    arms of a pair."""
    fa, fb = _flatten(a), _flatten(b)
    keys = sorted(set(fa) | set(fb))
    return [k for k in keys if fa.get(k, "<absent>") != fb.get(k, "<absent>")
            and not any(k == pre.rstrip(".") or k.startswith(pre) for pre in _ALLOWED_DIFF_PREFIXES)]


# ---------------------------------------------------------------- one run
def trap_v2_run(run: Run, p: AnalysisParams) -> Dict[str, Any]:
    """Throughput-based classification of one run (see module docstring)."""
    tp = p.trap_v2
    tb = run.t_burst_ref
    if tb is None:
        raise ValueError(f"{run.dir}: no burst time (config has neither arrivals.burst nor arrivals.analysis_t_burst_s)")
    lam, lam_miss = run.lam, run.lambda_ref_value
    if lam is None or lam_miss is None:
        raise ValueError(f"{run.dir}: meta.json lacks the resolved arrival rate / lambda_ref (not an open-loop E2 run?)")
    end = run.t_end_s
    t0 = tb + float(tp["eval_from_s"])
    eval_len = end - t0
    too_short = eval_len < float(tp["min_eval_s"]) - 1e-9
    est = str(tp["rate_estimator"])
    arm_explicit, arm_derived = run.arm, run.arm_derived
    rec: Dict[str, Any] = {
        "run_dir": str(run.dir), "label": run.label, "seed": run.seed, "rate_mult": run.rate_mult,
        "arm": arm_explicit or arm_derived, "arm_explicit": arm_explicit, "arm_derived": arm_derived,
        "arm_consistent": (arm_explicit in ("", arm_derived)), "gate_n_cap": run.gate_n_cap,
        "lambda": lam, "lambda_miss": lam_miss, "lambda_ref_key": run.lambda_ref_key, "lambda_above_miss": bool(lam > lam_miss),
        "t_burst": tb, "t_end_s": end, "eval_from": t0, "eval_len_s": eval_len, "window_too_short": bool(too_short),
        "aborted": run.aborted, "abort_reason": run.abort_reason, "rate_estimator": est,
        "hit_metric": p.w["hit_metric"]}
    nan_fields = ("rate_sessions", "rate_turns_based", "rate_primary", "rate_rel_dev", "backlog_slope", "slope_threshold",
                  "hit_eval", "backlog_eval_mean", "backlog_eval_start", "hit_end", "backlog_end", "backlog_end_inst")
    for k in nan_fields:
        rec[k] = NAN
    rec.update(crit_a=False, crit_a_sessions=False, crit_a_turns=False, estimators_agree=True, crit_b=False,
               trapped=False, draining=False, recovered=False, good=False, state="indeterminate",
               state_reason="", n_slope_bins=0)

    # end-of-run state (RECOVERED / good) is defined even when the evaluation window is too short
    ew = min(float(tp["end_window_s"]), max(end, 0.0))
    if ew > 0:
        h_end = hit_stats(run, p, end - ew, end + 1e-9)
        rec["hit_end"] = hit_value(h_end, p)
        rec["hit_end_turns_n"] = h_end["n_turns"]
        rec["hit_available"] = h_end["cached_available"]
        rec["backlog_end"] = backlog_mean(run.sessions, end - ew, end)
        rec["backlog_end_inst"] = backlog_at(run.sessions, end)
    rec["recovered"] = bool(not _isnan(rec["hit_end"]) and rec["hit_end"] > float(tp["recovered_hit_above"])
                            and not _isnan(rec["backlog_end"]) and rec["backlog_end"] < float(tp["recovered_backlog_below"]))
    rec["good"] = rec["recovered"]

    if too_short:
        rec["state_reason"] = "window_too_short"
        rec["state"] = "recovered" if rec["recovered"] else "indeterminate"
        return rec

    rates = completion_rates(run, t0, end)
    rec["rate_sessions"], rec["rate_turns_based"] = rates["sessions_per_s"], rates["turns_based_per_s"]
    rec["n_sessions_completed_eval"], rec["n_turns_completed_eval"] = rates["n_sessions_completed"], rates["n_turns_completed"]
    rec["rate_primary"] = pick_rate(rates, est)
    tol = float(tp["rate_tolerance"]) * lam_miss
    rec["crit_a_sessions"] = bool(abs(rates["sessions_per_s"] - lam_miss) <= tol)
    rec["crit_a_turns"] = bool(abs(rates["turns_based_per_s"] - lam_miss) <= tol)
    rec["crit_a"] = rec["crit_a_sessions"] if est == "sessions" else rec["crit_a_turns"]
    rec["estimators_agree"] = rec["crit_a_sessions"] == rec["crit_a_turns"]
    rec["rate_rel_dev"] = rec["rate_primary"] / lam_miss - 1.0
    slope, nb = backlog_slope(run.sessions, t0, end, float(tp["slope_dt_s"]))
    rec["backlog_slope"], rec["n_slope_bins"] = slope, nb
    rec["slope_threshold"] = float(tp["slope_frac"]) * (lam - lam_miss)
    rec["crit_b"] = bool(not _isnan(slope) and slope > rec["slope_threshold"])
    rec["backlog_eval_mean"] = backlog_mean(run.sessions, t0, end)
    rec["backlog_eval_start"] = backlog_at(run.sessions, t0)
    rec["hit_eval"] = hit_value(hit_stats(run, p, t0, end + 1e-9), p)
    rec["trapped"] = bool(rec["crit_a"] and rec["crit_b"] and rec["lambda_above_miss"])
    rec["draining"] = bool(not _isnan(slope) and slope < 0)
    if rec["trapped"]:
        rec["state"] = "trapped"
    elif rec["recovered"]:
        rec["state"] = "recovered"
    elif rec["draining"]:
        rec["state"] = "draining"
    else:
        rec["state"] = "indeterminate"
        rec["state_reason"] = ("hit fraction unavailable" if not rec.get("hit_available", True) else
                               "neither trapped, drained nor recovered by the end")
    return rec


def legacy_secondary(run: Run, p: AnalysisParams) -> Optional[Dict[str, Any]]:
    """The OLD hit-rate criterion (analysis.hysteresis.burst_verdict) for runs that have a burst; None otherwise."""
    if run.t_burst is None:
        return None
    v = burst_verdict(run, window_table(run, p), p)
    keep = ("verdict", "is_trap", "trapped", "trapped_aborted", "recovered", "good_before", "hysteresis_run", "hit_eval",
            "tail_queue_mean", "tail_queue_slope_per_window", "trap_run_s")
    return {k: v[k] for k in keep}


# ---------------------------------------------------------------- pairs and the PASS rule
def pairing_problems(group: Sequence[Tuple[Dict[str, Any], Run]]) -> List[str]:
    """Why the arms of one (label, rate_mult, seed) group are NOT valid common-random-number pairs (empty = fine)."""
    probs: List[str] = []
    by_arm: Dict[str, List[Tuple[Dict[str, Any], Run]]] = {}
    for rec, run in group:
        by_arm.setdefault(rec["arm"], []).append((rec, run))
    for arm, items in by_arm.items():
        if len(items) > 1:
            probs.append(f"duplicate {arm} runs: {[r['run_dir'] for r, _ in items]}")
    ref_arm = next((a for a in ARM_ORDER if a in by_arm), None)
    if ref_arm is None:
        return probs
    rec0, run0 = by_arm[ref_arm][0]
    for arm, items in by_arm.items():
        rec, run = items[0]
        if not rec["arm_consistent"]:
            probs.append(f"{arm}: meta.arm={rec['arm_explicit']!r} but the config implies {rec['arm_derived']!r}")
        if arm != ref_arm:
            diff = config_diff(run0.cfg, run.cfg)
            if diff:
                probs.append(f"{arm} vs {ref_arm}: configs differ in {diff}")
            if abs(rec["lambda"] - rec0["lambda"]) > 1e-12 * max(1.0, rec0["lambda"]) or abs(rec["lambda_miss"] - rec0["lambda_miss"]) > 1e-12:
                probs.append(f"{arm} vs {ref_arm}: different resolved lambda / lambda_miss")
            if rec["t_burst"] != rec0["t_burst"]:
                probs.append(f"{arm} vs {ref_arm}: different burst reference time")
    b, c = by_arm.get("burst"), by_arm.get("capped")
    if b and c and (b[0][1].cfg.get("arrivals") or {}).get("burst") != (c[0][1].cfg.get("arrivals") or {}).get("burst"):
        probs.append("burst vs capped: different burst specification")
    n = by_arm.get("noburst")
    if n and (n[0][1].cfg.get("arrivals") or {}).get("burst"):
        probs.append("noburst arm has a burst configured")
    if c and not c[0][0]["gate_n_cap"]:
        probs.append("capped arm ran without a resolved gate cap")
    if b and b[0][0]["gate_n_cap"]:
        probs.append("burst arm ran with a gate cap")
    return probs


def seed_verdict(arms: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """PASS for one seed: BURST trapped AND NOBURST good AND CAPPED recovered; missing arms are listed."""
    missing = [a for a in ARM_ORDER if a not in arms]
    out: Dict[str, Any] = {
        "missing_arms": missing,
        "burst_trapped": bool(arms["burst"]["trapped"]) if "burst" in arms else None,
        "noburst_good": bool(arms["noburst"]["good"]) if "noburst" in arms else None,
        "capped_recovered": bool(arms["capped"]["recovered"]) if "capped" in arms else None,
        "states": {a: arms[a]["state"] for a in ARM_ORDER if a in arms}}
    out["pass"] = bool(not missing and out["burst_trapped"] and out["noburst_good"] and out["capped_recovered"])
    return out


def cell_verdicts(records: Sequence[Dict[str, Any]], tp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One entry per (label, rate_mult): per-seed results, pass counts, and the PASS-rule decision."""
    df = pd.DataFrame(list(records))
    cells: List[Dict[str, Any]] = []
    if len(df) == 0:
        return cells
    frac_min, min_seeds = float(tp["pass_fraction_min"]), int(tp["min_seeds"])
    for (label, mult), g in df.groupby(["label", "rate_mult"], dropna=False):
        seeds: Dict[str, Any] = {}
        for seed, gs in g.groupby("seed"):
            arms = {r["arm"]: r for r in gs.to_dict("records")}      # a duplicate arm is a pairing problem; last wins
            seeds[str(int(seed))] = seed_verdict(arms)
        n_seen = len(seeds)
        n_pass = sum(v["pass"] for v in seeds.values())
        n_complete = sum(not v["missing_arms"] for v in seeds.values())

        def frac(key: str) -> Optional[float]:
            vals = [v[key] for v in seeds.values() if v[key] is not None]
            return (sum(vals) / len(vals)) if vals else None

        cells.append({
            "label": label, "rate_mult": None if _isnan(mult) else float(mult),
            "lambda": float(g["lambda"].iloc[0]), "lambda_miss": float(g["lambda_miss"].iloc[0]),
            "seeds": seeds, "n_seeds_seen": n_seen, "n_seeds_complete": n_complete, "n_pass": n_pass,
            "frac_pass": (n_pass / n_seen) if n_seen else None,
            "burst_trapped_frac": frac("burst_trapped"), "noburst_good_frac": frac("noburst_good"),
            "capped_recovered_frac": frac("capped_recovered"),
            "enough_seeds": bool(n_seen >= min_seeds),
            "meets": bool(n_seen >= min_seeds and n_pass / n_seen >= frac_min - 1e-12),
            "incomplete": sorted(s for s, v in seeds.items() if v["missing_arms"])})
    return cells


def diagnose(cell: Dict[str, Any]) -> str:
    """Plain-language reading of a cell, following the referee's decisive-result text."""
    if cell["meets"]:
        return "PASS: burst traps, no-burst stays good, capped recovers"
    if not cell["enough_seeds"]:
        return f"INSUFFICIENT: {cell['n_seeds_seen']} seeds < min_seeds"
    nb, bt, cr = cell["noburst_good_frac"], cell["burst_trapped_frac"], cell["capped_recovered_frac"]
    if nb is not None and nb < 0.5:
        return "FAIL: the no-burst arm does not stay good (no good state at this lambda)"
    if bt is not None and bt < 0.5:
        return "FAIL: the burst arm is not trapped (nothing traps at this lambda)"
    if cr is not None and cr < 0.5:
        return "FAIL: the capped arm does not recover (cap does not rescue)"
    return "FAIL: arms individually mostly behave as predicted but fewer than the required fraction of seeds pass jointly"
