"""Evaluation of the pre-registered round-4 predictions R1-R6 (configs/prefix_meta_r4_prereg.yaml, ``decision_readings``).

Pure functions on DataFrames. Each ``eval_*`` returns a row ``{id, reading, claim, verdict, numbers, notes}`` with verdict in
{PASS, FAIL, NOT_EVALUABLE, INFO}. ``reading`` is ``"headline"`` for the registered reading and ``"sensitivity"`` for the
labelled alternatives (ids carry a suffix such as ``R2-nearest-grid``); only headline rows are predictions. A prediction whose
required cells (the REGISTERED grid x seeds) are not all present is NOT_EVALUABLE, never judged on a partial design.

Inputs
  cr            curve_runs.csv   policy, k, n_nominal, n, seed, mu, ...                 (E-curve)
  burst_runs    runs.csv         policy, burst_n, seed, recovered                       (E-burst)
  cap_runs      runs.csv         eviction, cap, seed, recovered                         (E-cap)
  phase_runs    round-3 phase runs.csv   policy, lam_mult, recovered, horizon_used_s    (R4)
  lambda_cap    {k: lambda_cap(k)} from the round-3 escape limits                      (R6)
  design        ``registered_design`` of the pre-registration
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .fluid import FixedPoints, fixed_points, make_curve

PASS, FAIL, NA, INFO = "PASS", "FAIL", "NOT_EVALUABLE", "INFO"

CLAIMS = {
    "R1": "FCFS-LRU closed curve peaks at n* in [20, 32] and mu(n) <= 1.2 lambda_miss for all measured n >= 1.5 n*.",
    "R2": "at n = round(1.5 n*), FCFS-RANDOM mu >= 1.25 x FCFS-LRU mu (graceful degradation).",
    "R3": ("at lambda = 2 lambda_miss, the fluid-predicted critical burst b_c (from the FCFS-LRU curve) is within a factor of 2 "
           "of the empirical critical burst b_emp := smallest burst size in the sweep that leaves FCFS not recovered in >= 3/5 "
           "seeds."),
    "R4": ("for FCFS and LPM, the empirical recovery threshold from 300 cold sessions lies within +-15% of "
           "mu_policy(300)/lambda_miss measured here."),
    "R5": ("with a session cap N in {32, 36, 40}, FCFS-RANDOM or FCFS-MRU_IDLE recovers (>= 2/3 from cold 300 at 2 x "
           "lambda_miss, 150k-s horizon) for at least 2 of the 3 caps, while FCFS-LRU recovers 0/3 at each."),
    "R6": "lambda_cap(k)/mu*(k) increases with k over k in {0.5, 1, 2}.",
}


class Missing(Exception):
    """Required cells of the registered design are absent."""


def _py(o: Any) -> Any:
    """JSON-safe copy (numpy -> python, NaN/inf kept as floats)."""
    if isinstance(o, dict):
        return {str(k): _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_py(v) for v in o.tolist()]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _row(pid: str, verdict: str, numbers: Dict[str, Any], notes: str = "", reading: str = "headline",
         claim: Optional[str] = None) -> Dict[str, Any]:
    base = pid.split("-")[0]
    return {"id": pid, "reading": reading, "claim": claim if claim is not None else CLAIMS.get(base, ""),
            "verdict": verdict, "numbers": _py(numbers), "notes": notes}


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


# ----------------------------------------------------------------------------------------------- curve access
def seed_matrix(cr: pd.DataFrame, policy: str, k: float, grid: Sequence[int], seeds: Sequence[int]) -> np.ndarray:
    """mu per (grid point, seed) for ``policy`` at size ``k``: shape (len(grid), len(seeds)). Raises ``Missing``."""
    sel = cr[(cr["policy"] == policy) & np.isclose(cr["k"].astype(float), k)]
    if sel.duplicated(["n_nominal", "seed"]).any():
        raise ValueError(f"duplicate (n, seed) cells for {policy} k={k}")
    piv = sel.pivot_table(index="n_nominal", columns="seed", values="mu", aggfunc="first")
    missing = [(int(n), int(s)) for n in grid for s in seeds
               if n not in piv.index or s not in piv.columns or pd.isna(piv.loc[n, s])]
    if missing:
        raise Missing(f"{policy} k={k}: {len(missing)} registered (n, seed) cells missing, e.g. {missing[:4]}")
    return piv.loc[list(grid), list(seeds)].to_numpy(dtype=float)


def interp_at(grid: Sequence[float], values: Sequence[float], x: float) -> float:
    """Linear interpolation in n (exact at grid points; clamped outside the grid)."""
    return float(np.interp(x, np.asarray(grid, dtype=float), np.asarray(values, dtype=float)))


# ----------------------------------------------------------------------------------------------- R1
def eval_r1(cr: pd.DataFrame, lam_miss: float, d: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[int]]:
    """Headline R1. Returns (row, n_star or None)."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
    except Missing as e:
        return _row("R1", NA, {}, str(e)), None
    mu = M.mean(axis=1)
    i = int(np.argmax(mu))                                   # first argmax = smallest n on ties
    n_star = int(grid[i])
    in_band = 20 <= n_star <= 32
    tail = [(int(n), float(m)) for n, m in zip(grid, mu) if n >= 1.5 * n_star]
    viol = [n for n, m in tail if m > 1.2 * lam_miss]
    tail_ok = not viol
    nums = {"n_star": n_star, "mu_star": float(mu[i]), "mu_star_over_lambda_miss": float(mu[i] / lam_miss),
            "clause_peak_in_[20,32]": in_band, "clause_tail_le_1.2_lambda_miss": tail_ok,
            "tail_points_n>=1.5n*": [(n, m / lam_miss) for n, m in tail], "tail_violators": viol,
            "max_tail_over_lambda_miss": max((m for _, m in tail), default=float("nan")) / lam_miss,
            "per_seed_argmax_n": [int(grid[j]) for j in np.argmax(M, axis=0)],
            "mu_over_lambda_miss_by_n": {int(n): float(m / lam_miss) for n, m in zip(grid, mu)}}
    return _row("R1", PASS if (in_band and tail_ok) else FAIL, nums), n_star


# ----------------------------------------------------------------------------------------------- R2
def eval_r2(cr: pd.DataFrame, n_star: Optional[int], d: Dict[str, Any], other: str = "fcfs_random",
            pid: str = "R2", reading: str = "headline", nearest: bool = False, informational: bool = False
            ) -> Dict[str, Any]:
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    if n_star is None:
        return _row(pid, NA, {}, "n* from R1 not available", reading)
    try:
        ML = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
        MO = seed_matrix(cr, other, 1.0, grid, seeds)
    except Missing as e:
        return _row(pid, NA, {}, str(e), reading)
    n_r2 = round_half_up(1.5 * n_star)
    at = min(grid, key=lambda g: (abs(g - n_r2), -g)) if nearest else n_r2        # ties -> larger n
    mu_l = interp_at(grid, ML.mean(axis=1), at)
    mu_o = interp_at(grid, MO.mean(axis=1), at)
    ratio = mu_o / mu_l if mu_l > 0 else float("inf")
    per_seed = [interp_at(grid, MO[:, j], at) / interp_at(grid, ML[:, j], at) for j in range(len(seeds))]
    nums = {"n_star": n_star, "n_R2": n_r2, "evaluated_at_n": at, "mu_lru": mu_l, f"mu_{other}": mu_o,
            "ratio": ratio, "per_seed_ratio": per_seed, "threshold": 1.25, "meets_threshold": bool(mu_o >= 1.25 * mu_l),
            "on_grid": n_r2 in list(grid)}
    verdict = INFO if informational else (PASS if mu_o >= 1.25 * mu_l else FAIL)
    return _row(pid, verdict, nums,
                "per-seed ratios are CRN-coupled (same workload per seed for both policies)"
                + ("; informational (not part of R2)" if informational else ""), reading)


# ----------------------------------------------------------------------------------------------- R3
def empirical_critical_burst(sizes: Sequence[int], n_not_rec: Sequence[int], n_runs: Sequence[int], min_count: int = 3
                             ) -> Tuple[Optional[int], str]:
    """(b_emp, status): smallest size with >= ``min_count`` not-recovered runs. status: "found", "left_censored" (the smallest
    size already qualifies: b_emp <= sizes[0]) or "right_censored" (none qualifies: b_emp > sizes[-1])."""
    for j, (s, k) in enumerate(zip(sizes, n_not_rec)):
        if k >= min_count:
            return int(s), "left_censored" if j == 0 else "found"
    return None, "right_censored"


def _fp_dict(fp: FixedPoints) -> Dict[str, Any]:
    return {"kind": fp.kind, "n1": fp.n1, "n2": fp.n2, "b_c": fp.b_c}


def burst_table(burst_runs: pd.DataFrame, policy: str, sizes: Sequence[int], seeds: Sequence[int]
                ) -> Tuple[List[int], List[int]]:
    """(not-recovered count, run count) per registered burst size for ``policy``; raises ``Missing``."""
    sel = burst_runs[burst_runs["policy"] == policy]
    nr, nn = [], []
    for b in sizes:
        g = sel[sel["burst_n"] == b]
        have = set(int(s) for s in g["seed"])
        if not set(int(s) for s in seeds) <= have or g.duplicated("seed").any():
            raise Missing(f"burst runs of {policy} at size {b}: seeds {sorted(have)} != registered {list(seeds)}")
        g = g[g["seed"].isin(seeds)]
        rec = g["recovered"].map(lambda v: v is True or str(v) == "True")
        nr.append(int((~rec).sum()))
        nn.append(int(len(g)))
    return nr, nn


def eval_r3(cr: pd.DataFrame, burst_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any],
            unimodal: bool = True, pid: str = "R3", reading: str = "headline") -> Dict[str, Any]:
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    sizes, bseeds = d["burst"]["sizes"], d["burst"]["seeds"]
    if burst_runs is None:
        return _row(pid, NA, {}, "no E-burst runs", reading)
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
        nr, nn = burst_table(burst_runs, d["burst"]["policies"]["primary"], sizes, bseeds)
    except Missing as e:
        return _row(pid, NA, {}, str(e), reading)
    lam = d["burst"]["lam_mult"] * lam_miss
    fp = fixed_points(make_curve(grid, M.mean(axis=1), unimodal=unimodal), lam)
    b_emp, status = empirical_critical_burst(sizes, nr, nn)
    bc = fp.b_c
    nums = {"lambda": lam, "fluid": _fp_dict(fp), "b_emp": b_emp, "b_emp_status": status,
            "not_recovered_by_size": dict(zip(map(int, sizes), nr)), "runs_per_size": dict(zip(map(int, sizes), nn)),
            "counts_monotone_in_size": bool(all(a <= b for a, b in zip(nr, nr[1:]))),
            "b_c_over_b_emp": (bc / b_emp) if (b_emp and math.isfinite(bc)) else float("nan"),
            "curve": "unimodal-projected piecewise-linear" if unimodal else "raw piecewise-linear"}
    verdict, note = NA, ""
    if status == "found":
        if not math.isfinite(bc):
            verdict, note = FAIL, "fluid prediction is not a finite critical burst (overload or monostable)"
        else:
            verdict = PASS if 0.5 <= bc / b_emp <= 2.0 else FAIL
    elif status == "left_censored":
        if not math.isfinite(bc) or bc > 2 * sizes[0]:
            verdict, note = FAIL, f"b_emp <= {sizes[0]} (left-censored) and b_c > {2 * sizes[0]}"
        else:
            note = f"b_emp <= {sizes[0]} (left-censored); b_c within reach of the factor-2 band: cannot be established"
    else:
        if math.isfinite(bc) and bc < sizes[-1] / 2:
            verdict, note = FAIL, f"b_emp > {sizes[-1]} (right-censored) and b_c < {sizes[-1] / 2}"
        else:
            note = f"b_emp > {sizes[-1]} (right-censored): within-factor-2 cannot be established"
    return _row(pid, verdict, nums, note, reading)


def eval_r3_info_random(cr: pd.DataFrame, burst_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any]
                        ) -> Dict[str, Any]:
    """Informational (not a prediction): the same burst sweep and fluid prediction for FCFS-RANDOM."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    sizes, bseeds = d["burst"]["sizes"], d["burst"]["seeds"]
    pol = d["burst"]["policies"]["informational"]
    if burst_runs is None:
        return _row("R3-info-random", NA, {}, "no E-burst runs", "information")
    try:
        M = seed_matrix(cr, pol, 1.0, grid, seeds)
        nr, nn = burst_table(burst_runs, pol, sizes, bseeds)
    except Missing as e:
        return _row("R3-info-random", NA, {}, str(e), "information")
    lam = d["burst"]["lam_mult"] * lam_miss
    fp = fixed_points(make_curve(grid, M.mean(axis=1)), lam)
    b_emp, status = empirical_critical_burst(sizes, nr, nn)
    return _row("R3-info-random", INFO, {"lambda": lam, "fluid": _fp_dict(fp), "b_emp": b_emp, "b_emp_status": status,
                                          "not_recovered_by_size": dict(zip(map(int, sizes), nr))},
                "FCFS-RANDOM burst sweep and its own fluid prediction (informational, not a registered prediction)",
                "information")


# ----------------------------------------------------------------------------------------------- R4
def phase_threshold(phase_runs: pd.DataFrame, policy: str, min_horizon_s: float, need: int = 2, n_seeds: int = 3
                    ) -> Dict[str, Any]:
    """Empirical recovery-threshold interval [lo, hi] of ``policy`` from the round-3 phase runs (150k-s multiples only):
    lo = largest multiple such that every multiple <= it has >= ``need`` of ``n_seeds`` recovered; hi = smallest multiple
    above lo with <= need - 1 recovered."""
    sel = phase_runs[(phase_runs["policy"] == policy) & (phase_runs["horizon_used_s"].astype(float) >= min_horizon_s)]
    rows = []
    for m, g in sel.groupby("lam_mult"):
        rec = g["recovered"].map(lambda v: v is True or str(v) == "True")
        rows.append((float(m), int(rec.sum()), int(len(g))))
    rows.sort()
    if not rows or any(n != n_seeds for _, _, n in rows):
        return {"ok": False, "reason": f"phase cells of {policy} missing or not {n_seeds} seeds", "cells": rows}
    lo = None
    for m, c, _ in rows:
        if c >= need:
            lo = m
        else:
            break
    hi = None
    if lo is not None:
        for m, c, _ in rows:
            if m > lo and c <= need - 1:
                hi = m
                break
    if lo is None or hi is None:
        return {"ok": False, "reason": "no bracket [lo, hi] in the 150k-s multiples", "cells": rows}
    return {"ok": True, "lo": lo, "hi": hi, "cells": rows}


def eval_r4(cr: pd.DataFrame, phase_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any]
            ) -> List[Dict[str, Any]]:
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    src = d["r4_sources"]
    heads = {"R4": None, "R4-strict": None, "R4-lenient": None}
    if phase_runs is None:
        return [_row(k, NA, {}, "round-3 phase runs not available", "headline" if k == "R4" else "sensitivity",
                     CLAIMS["R4"]) for k in heads]
    nums: Dict[str, Any] = {}
    ok = {"R4": True, "R4-strict": True, "R4-lenient": True}
    notes = ""
    try:
        for label, pol in (("FCFS", "fcfs_lru"), ("LPM", "lpm_lru")):
            M = seed_matrix(cr, pol, 1.0, grid, seeds)
            if 300 not in list(grid):
                raise Missing("n = 300 not in the registered grid")
            mu300 = float(M.mean(axis=1)[list(grid).index(300)])
            th = phase_threshold(phase_runs, src["phase_policies"][label], src["min_horizon_s"])
            if not th["ok"]:
                raise Missing(th["reason"])
            r = mu300 / lam_miss
            lo, hi = th["lo"], th["hi"]
            t = 0.5 * (lo + hi)
            nums[label] = {"mu300": mu300, "r_pred": r, "lo": lo, "hi": hi, "t_mid": t, "rel_err_vs_mid": (r - t) / t,
                           "within_15pct_of_mid": abs(r - t) <= 0.15 * t,
                           "within_strict": 0.85 * hi <= r <= 1.15 * lo, "within_lenient": 0.85 * lo <= r <= 1.15 * hi,
                           "phase_cells": th["cells"]}
            ok["R4"] &= nums[label]["within_15pct_of_mid"]
            ok["R4-strict"] &= nums[label]["within_strict"]
            ok["R4-lenient"] &= nums[label]["within_lenient"]
    except Missing as e:
        return [_row(k, NA, {}, str(e), "headline" if k == "R4" else "sensitivity", CLAIMS["R4"]) for k in heads]
    out = []
    for k in heads:
        out.append(_row(k, PASS if ok[k] else FAIL, nums, notes, "headline" if k == "R4" else "sensitivity", CLAIMS["R4"]))
    return out


# ----------------------------------------------------------------------------------------------- R5
def eval_r5(cap_runs: Optional[pd.DataFrame], d: Dict[str, Any]) -> List[Dict[str, Any]]:
    cd = d["cap"]
    caps5 = [32, 36, 40]
    if cap_runs is None:
        return [_row("R5", NA, {}, "no E-cap runs"), _row("R5-union", NA, {}, "no E-cap runs", "sensitivity", CLAIMS["R5"])]
    seeds = cd["seeds"]
    cells: Dict[Tuple[str, int], Dict[str, int]] = {}
    for ev in cd["evictions"]:
        for cap in cd["caps"]:
            g = cap_runs[(cap_runs["eviction"] == ev) & (cap_runs["cap"] == cap)]
            if sorted(int(s) for s in g["seed"]) != sorted(int(s) for s in seeds):
                return [_row("R5", NA, {}, f"E-cap cell ({ev}, {cap}) does not have the registered seeds"),
                        _row("R5-union", NA, {}, "see R5", "sensitivity", CLAIMS["R5"])]
            rec = g["recovered"].map(lambda v: v is True or str(v) == "True")
            cells[(ev, int(cap))] = {"k": int(rec.sum()), "n": int(len(g))}
    recovers = {key: v["k"] >= 2 for key, v in cells.items()}                 # >= 2 of 3 seeds
    per_rule = {ev: sum(recovers[(ev, c)] for c in caps5) for ev in ("random", "mru_idle")}
    union = sum(recovers[("random", c)] or recovers[("mru_idle", c)] for c in caps5)
    lru_zero = all(cells[("lru", c)]["k"] == 0 for c in caps5)
    nums = {"cells_recovered_of_3": {f"{ev}@{c}": v["k"] for (ev, c), v in sorted(cells.items())},
            "caps_recovered_per_rule": per_rule, "caps_recovered_union": int(union), "lru_zero_at_all_caps": lru_zero,
            "best_single_rule": max(per_rule.values())}
    head = PASS if (max(per_rule.values()) >= 2 and lru_zero) else FAIL
    sens = PASS if (union >= 2 and lru_zero) else FAIL
    note = "cells share 3 seeds (CRN) and are not independent; caps 24 and 28 are context only"
    return [_row("R5", head, nums, note), _row("R5-union", sens, nums, note, "sensitivity", CLAIMS["R5"])]


# ----------------------------------------------------------------------------------------------- R6
def eval_r6(cr: pd.DataFrame, lambda_cap: Optional[Dict[float, float]], d: Dict[str, Any]) -> Dict[str, Any]:
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    ks = [0.5, 1.0, 2.0]
    if not lambda_cap or any(k not in lambda_cap for k in ks):
        return _row("R6", NA, {}, "lambda_cap(k) of the round-3 escape results not available")
    rho, nums = {}, {}
    try:
        for k in ks:
            M = seed_matrix(cr, "fcfs_lru", k, grid, seeds)
            mu = M.mean(axis=1)
            i = int(np.argmax(mu))
            mu_star = float(mu[i])
            rho[k] = lambda_cap[k] / mu_star
            seed_max = M.max(axis=0)
            nums[f"k={k}"] = {"lambda_cap": lambda_cap[k], "mu_star": mu_star, "argmax_n_nominal": int(grid[i]),
                              "argmax_n_actual": int(round_half_up(k * grid[i])) if k != 1.0 else int(grid[i]),
                              "rho": rho[k], "per_seed_mu_star": [float(x) for x in seed_max],
                              "per_seed_rho": [float(lambda_cap[k] / x) for x in seed_max]}
    except Missing as e:
        return _row("R6", NA, {}, str(e))
    inc = rho[0.5] < rho[1.0] < rho[2.0]
    return _row("R6", PASS if inc else FAIL, nums,
                "lambda_cap(k) is a finite-horizon (20000 s) from-empty stability limit, not a fluid quantity")


# ----------------------------------------------------------------------------------------------- all
def evaluate_all(cr: Optional[pd.DataFrame], burst_runs: Optional[pd.DataFrame], cap_runs: Optional[pd.DataFrame],
                 phase_runs: Optional[pd.DataFrame], lambda_cap: Optional[Dict[float, float]], lam_miss: float,
                 design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Headline rows R1..R6 first (registered readings), then the labelled sensitivity / information rows."""
    d = design
    if cr is None:
        return [_row(f"R{i}", NA, {}, "no E-curve runs") if i != 5 else eval_r5(cap_runs, d)[0] for i in range(1, 7)]
    r1, n_star = eval_r1(cr, lam_miss, d)
    r2 = eval_r2(cr, n_star, d)
    r3 = eval_r3(cr, burst_runs, lam_miss, d)
    r4 = eval_r4(cr, phase_runs, lam_miss, d)
    r5 = eval_r5(cap_runs, d)
    r6 = eval_r6(cr, lambda_cap, d)
    heads = [r1, r2, r3, r4[0], r5[0], r6]
    sens = [eval_r2(cr, n_star, d, pid="R2-nearest-grid", reading="sensitivity", nearest=True),
            eval_r2(cr, n_star, d, other="fcfs_mru_idle", pid="R2-MRU", reading="information", informational=True),
            eval_r3(cr, burst_runs, lam_miss, d, unimodal=False, pid="R3-raw", reading="sensitivity"),
            *r4[1:], r5[1], eval_r3_info_random(cr, burst_runs, lam_miss, d)]
    return heads + sens


def rows_to_frame(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{**r, "numbers": json.dumps(r["numbers"], default=float)} for r in rows],
                        columns=["id", "reading", "verdict", "claim", "numbers", "notes"])
