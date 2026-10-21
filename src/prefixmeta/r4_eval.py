"""Evaluation of the pre-registered round-4 predictions R1-R6 (configs/prefix_meta_r4_prereg.yaml: ``decision_readings`` as
amended by ``amendment_1``).

Pure functions on DataFrames. Each ``eval_*`` returns a row ``{id, reading, claim, verdict, numbers, notes}``. ``reading`` is
``"headline"`` for the registered reading (R4 as amended: strictly stricter), ``"sensitivity"`` for the labelled alternatives
(ids carry a suffix such as ``R2-nearest-grid``) and ``"information"`` for rows that are not tests; only headline rows are
predictions. Verdicts: PASS / FAIL / NOT_EVALUABLE for tests, MIXED for a sensitivity set whose members disagree, ROBUST /
FRAGILE for the R3 robustness label, INFO for information rows. A prediction whose required cells (the REGISTERED grid x seeds) are
not all present is NOT_EVALUABLE, never judged on a partial design. The claim strings are loaded verbatim from the pre-registration
(``predictions``), not abbreviated here.

Inputs
  cr               curve_runs.csv   policy, k, n_nominal, n, seed, mu, ...                 (E-curve)
  burst_runs       runs.csv         policy, burst_n, seed, recovered                       (E-burst)
  burst_info_runs  runs.csv         policy, lam_mult, burst_n, seed, recovered             (burst_info, informational)
  cap_runs         runs.csv         eviction, cap, seed, recovered                         (E-cap)
  phase_runs       round-3 phase runs.csv   policy, lam_mult, recovered, horizon_used_s    (R4)
  lambda_cap       {k: lambda_cap(k)} from the round-3 escape limits                      (R6)
  lambda_miss_k    {k: lambda_miss(k)} (k = 1 is the base lambda_miss)                    (R6 null)
  design           ``registered_design`` of the pre-registration
"""
from __future__ import annotations

import functools
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from . import r4_boot as B
from .fluid import FixedPoints, fixed_points, make_curve

PASS, FAIL, NA, INFO = "PASS", "FAIL", "NOT_EVALUABLE", "INFO"
MIXED, ROBUST, FRAGILE = "MIXED", "ROBUST", "FRAGILE"
TEST_VERDICTS = (PASS, FAIL, MIXED, ROBUST, FRAGILE)

PREREG_FILE = Path(__file__).resolve().parents[2] / "configs" / "prefix_meta_r4_prereg.yaml"
_CLAIMS_OVERRIDE: Optional[Dict[str, str]] = None


# ----------------------------------------------------------------------------------------------- claims (from the prereg)
@functools.lru_cache(maxsize=8)
def _claims_from(path: str) -> Tuple[Tuple[str, str], ...]:
    preds = yaml.safe_load(Path(path).read_text())["preregistration"]["predictions"]
    return tuple((k, str(v)) for k, v in preds.items())


def registered_claims(path: Optional[Path] = None) -> Dict[str, str]:
    """The verbatim prediction strings R1..R6 of the pre-registration file (not abbreviated)."""
    p = Path(path) if path else PREREG_FILE
    return dict(_claims_from(str(p))) if p.exists() else {}


def _claim(base: str) -> str:
    cl = _CLAIMS_OVERRIDE if _CLAIMS_OVERRIDE is not None else registered_claims()
    return cl.get(base, "")


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
    return {"id": pid, "reading": reading, "claim": claim if claim is not None else _claim(base),
            "verdict": verdict, "numbers": _py(numbers), "notes": notes}


def _is_true(v: Any) -> bool:
    return v is True or str(v) == "True"


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _agg(flags: Sequence[bool]) -> str:
    """PASS if all flags hold, FAIL if none does, MIXED otherwise."""
    if all(flags):
        return PASS
    return FAIL if not any(flags) else MIXED


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


# ----------------------------------------------------------------------------------------------- R1 / R2 building blocks
def r1_clauses(grid: Sequence[int], mu: Sequence[float], lam_miss: float, n_star: int) -> Dict[str, Any]:
    """Both clauses of R1 for a given ``n_star`` on a curve ``mu`` (values at ``grid``)."""
    in_band = 20 <= n_star <= 32
    tail = [(int(n), float(m)) for n, m in zip(grid, mu) if n >= 1.5 * n_star]
    viol = [n for n, m in tail if m > 1.2 * lam_miss]
    return {"in_band": in_band, "tail_ok": not viol, "tail": tail, "violators": viol,
            "max_tail": max((m for _, m in tail), default=float("nan")), "pass": in_band and not viol}


def r2_point(grid: Sequence[int], mu_lru: Sequence[float], mu_other: Sequence[float], n_star: int
             ) -> Dict[str, Any]:
    """R2 at n_R2 = round_half_up(1.5 n*): both curves interpolated linearly in n as registered."""
    n_r2 = round_half_up(1.5 * n_star)
    a, b = interp_at(grid, mu_lru, n_r2), interp_at(grid, mu_other, n_r2)
    ratio = b / a if a > 0 else float("inf")
    return {"n_R2": n_r2, "mu_lru": a, "mu_other": b, "ratio": ratio, "pass": bool(b >= 1.25 * a)}


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
    c = r1_clauses(grid, mu, lam_miss, n_star)
    se = B.se_rows(M)
    nums = {"n_star": n_star, "mu_star": float(mu[i]), "mu_star_over_lambda_miss": float(mu[i] / lam_miss),
            "clause_peak_in_[20,32]": c["in_band"], "clause_tail_le_1.2_lambda_miss": c["tail_ok"],
            "tail_points_n>=1.5n*": [(n, m / lam_miss) for n, m in c["tail"]], "tail_violators": c["violators"],
            "max_tail_over_lambda_miss": c["max_tail"] / lam_miss,
            "per_seed_argmax_n": [int(grid[j]) for j in np.argmax(M, axis=0)],
            "mu_over_lambda_miss_by_n": {int(n): float(m / lam_miss) for n, m in zip(grid, mu)},
            "mu_se_over_lambda_miss_by_n": {int(n): float(s / lam_miss) for n, s in zip(grid, se)}}
    return _row("R1", PASS if c["pass"] else FAIL, nums,
                "n* is the argmax of a noisy, flat-topped seed-mean curve: see the R1-nearmax / R1-per-seed / R1-bootstrap rows"), n_star


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


# ----------------------------------------------------------------------------------------------- R1 / R2 sensitivity (amendment 1)
def _lru_and_random(cr: pd.DataFrame, d: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    return seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds), seed_matrix(cr, "fcfs_random", 1.0, grid, seeds)


def near_max_indices(M: np.ndarray, n_se: float = 2.0) -> List[int]:
    """Grid indices whose seed-mean is within ``n_se`` standard errors (unpaired: sqrt(SE_max^2 + SE_n^2)) of the maximum."""
    mu, se = M.mean(axis=1), B.se_rows(M)
    i_max = int(np.argmax(mu))
    out = []
    for i in range(len(mu)):
        tol = n_se * math.sqrt(se[i_max] ** 2 + se[i] ** 2) if np.isfinite(se[i_max]) and np.isfinite(se[i]) else 0.0
        if i == i_max or mu[i_max] - mu[i] <= tol:
            out.append(i)
    return out


def eval_r1r2_nearmax(cr: pd.DataFrame, lam_miss: float, d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """R1 and R2 evaluated at every grid n whose seed-mean is within 2 SE of the maximum, each taken as n*."""
    grid = d["curve"]["n_grid"]
    try:
        ML, MO = _lru_and_random(cr, d)
    except Missing as e:
        return [_row("R1-nearmax", NA, {}, str(e), "sensitivity"), _row("R2-nearmax", NA, {}, str(e), "sensitivity")]
    mu_l, mu_o = ML.mean(axis=1), MO.mean(axis=1)
    cand = near_max_indices(ML)
    c1, c2 = [], []
    for i in cand:
        n_c = int(grid[i])
        a = r1_clauses(grid, mu_l, lam_miss, n_c)
        c1.append({"n_star_candidate": n_c, "mu_over_lambda_miss": float(mu_l[i] / lam_miss), "clause_peak": a["in_band"],
                   "clause_tail": a["tail_ok"], "tail_violators": a["violators"], "pass": a["pass"]})
        r = r2_point(grid, mu_l, mu_o, n_c)
        c2.append({"n_star_candidate": n_c, "n_R2": r["n_R2"], "ratio": r["ratio"], "pass": r["pass"]})
    note = ("candidates = grid n with seed-mean within 2 sqrt(SE_max^2 + SE_n^2) of the maximum (3 seeds: SEs are themselves "
            "very noisy)")
    return [_row("R1-nearmax", _agg([c["pass"] for c in c1]), {"candidates": c1}, note, "sensitivity"),
            _row("R2-nearmax", _agg([c["pass"] for c in c2]), {"candidates": c2}, note, "sensitivity")]


def eval_r1r2_per_seed(cr: pd.DataFrame, lam_miss: float, d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """R1 and R2 on each seed's own curves with that seed's own first argmax as n* (LRU and RANDOM of the same seed)."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    try:
        ML, MO = _lru_and_random(cr, d)
    except Missing as e:
        return [_row("R1-per-seed", NA, {}, str(e), "sensitivity"), _row("R2-per-seed", NA, {}, str(e), "sensitivity")]
    c1, c2 = [], []
    for j, sd in enumerate(seeds):
        n_s = int(grid[int(np.argmax(ML[:, j]))])
        a = r1_clauses(grid, ML[:, j], lam_miss, n_s)
        c1.append({"seed": int(sd), "n_star": n_s, "clause_peak": a["in_band"], "clause_tail": a["tail_ok"],
                   "tail_violators": a["violators"], "pass": a["pass"]})
        r = r2_point(grid, ML[:, j], MO[:, j], n_s)
        c2.append({"seed": int(sd), "n_star": n_s, "n_R2": r["n_R2"], "ratio": r["ratio"], "pass": r["pass"]})
    note = "seeds are the unit of replication; RANDOM and LRU of one seed share the workload (CRN)"
    return [_row("R1-per-seed", _agg([c["pass"] for c in c1]), {"seeds": c1}, note, "sensitivity"),
            _row("R2-per-seed", _agg([c["pass"] for c in c2]), {"seeds": c2}, note, "sensitivity")]


def _boot_cfg(boot: Optional[Dict[str, Any]]) -> Tuple[int, int, float]:
    b = boot or {}
    return int(b.get("n_boot", B.BOOT_N)), int(b.get("entropy", B.BOOT_ENTROPY)), float(b.get("level", B.BOOT_LEVEL))


def eval_r1r2_bootstrap(cr: pd.DataFrame, lam_miss: float, d: Dict[str, Any], boot: Optional[Dict[str, Any]] = None
                        ) -> List[Dict[str, Any]]:
    """Seed-bootstrap distribution of n*, of the R1 verdict and of the R2 ratio (information)."""
    grid = np.asarray(d["curve"]["n_grid"])
    nb, ent, lev = _boot_cfg(boot)
    try:
        ML, MO = _lru_and_random(cr, d)
    except Missing as e:
        return [_row("R1-bootstrap", NA, {}, str(e), "information"), _row("R2-bootstrap", NA, {}, str(e), "information")]
    idx = B.resample_indices("R1R2", ML.shape[1], nb, ent)
    bl, bo = B.boot_means(ML, idx), B.boot_means(MO, idx)                 # (B, G) each
    i_star = np.argmax(bl, axis=1)
    n_star = grid[i_star]
    in_band = (n_star >= 20) & (n_star <= 32)
    tail_mask = grid[None, :] >= 1.5 * n_star[:, None]
    tail_ok = ~(((bl > 1.2 * lam_miss) & tail_mask).any(axis=1))
    ratios = np.empty(nb)
    for b in range(nb):
        r = r2_point(grid, bl[b], bo[b], int(n_star[b]))
        ratios[b] = r["ratio"]
    vals, cnts = np.unique(n_star, return_counts=True)
    r1_nums = {"n_boot": nb, "entropy": ent, "n_star_distribution": {int(v): int(c) for v, c in zip(vals, cnts)},
               "n_star_interval": B.interval(n_star, lev), "P_R1_pass": float(np.mean(in_band & tail_ok)),
               "P_clause_peak": float(np.mean(in_band)), "P_clause_tail": float(np.mean(tail_ok))}
    r2_nums = {"n_boot": nb, "ratio_interval": B.interval(ratios, lev), "P_ratio_ge_1.25": float(np.mean(ratios >= 1.25)),
               "n_star_distribution": r1_nums["n_star_distribution"]}
    note = "B resamples of the 3 seeds with replacement (crude with 3 seeds); the same resample for every grid point and policy"
    return [_row("R1-bootstrap", INFO, r1_nums, note, "information"), _row("R2-bootstrap", INFO, r2_nums, note, "information")]


# ----------------------------------------------------------------------------------------------- R3
def empirical_critical_burst(sizes: Sequence[int], n_not_rec: Sequence[int], n_runs: Sequence[int], min_count: int = 3
                             ) -> Tuple[Optional[int], str]:
    """(b_emp, status): smallest size with >= ``min_count`` not-recovered runs. status: "found", "left_censored" (the smallest
    size already qualifies: b_emp <= sizes[0]) or "right_censored" (none qualifies: b_emp > sizes[-1])."""
    for j, (s, k) in enumerate(zip(sizes, n_not_rec)):
        if k >= min_count:
            return int(s), "left_censored" if j == 0 else "found"
    return None, "right_censored"


def monotone_envelope_burst(sizes: Sequence[int], n_not_rec: Sequence[int], min_count: int = 3) -> Tuple[Optional[int], str]:
    """(b_env, status): smallest size such that EVERY size >= it has >= ``min_count`` not-recovered runs. "right_censored" if the
    largest size does not qualify; "left_censored" if all sizes qualify (b_env = smallest size)."""
    j = len(sizes)
    while j > 0 and n_not_rec[j - 1] >= min_count:
        j -= 1
    if j == len(sizes):
        return None, "right_censored"
    return int(sizes[j]), "left_censored" if j == 0 else "found"


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
        rec = g["recovered"].map(_is_true)
        nr.append(int((~rec).sum()))
        nn.append(int(len(g)))
    return nr, nn


def r3_verdict(bc: float, b_emp: Optional[int], status: str, sizes: Sequence[int]) -> Tuple[str, str]:
    """The registered R3 verdict rule as a function of the fluid b_c and the empirical critical burst (found / censored)."""
    if status == "found":
        if not math.isfinite(bc):
            return FAIL, "fluid prediction is not a finite critical burst (overload or monostable)"
        return (PASS if 0.5 <= bc / b_emp <= 2.0 else FAIL), ""
    if status == "left_censored":
        if not math.isfinite(bc) or bc > 2 * sizes[0]:
            return FAIL, f"b_emp <= {sizes[0]} (left-censored) and b_c > {2 * sizes[0]}"
        return NA, f"b_emp <= {sizes[0]} (left-censored); b_c within reach of the factor-2 band: cannot be established"
    if math.isfinite(bc) and bc < sizes[-1] / 2:
        return FAIL, f"b_emp > {sizes[-1]} (right-censored) and b_c < {sizes[-1] / 2}"
    return NA, f"b_emp > {sizes[-1]} (right-censored): within-factor-2 cannot be established"


def r3_change_points(b_emp: Optional[int], status: str, sizes: Sequence[int]) -> List[float]:
    """The values of b_c at which ``r3_verdict`` changes (for the robustness check)."""
    if status == "found":
        return [b_emp / 2.0, 2.0 * b_emp]
    if status == "left_censored":
        return [2.0 * sizes[0]]
    return [sizes[-1] / 2.0]


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
    verdict, note = r3_verdict(bc, b_emp, status, sizes)
    return _row(pid, verdict, nums, note, reading)


def bc_replicates(M: np.ndarray, grid: Sequence[int], lam: float, idx: np.ndarray, unimodal: bool = True) -> np.ndarray:
    """b_c of each bootstrap-resampled seed-mean curve (registered fluid_curve construction)."""
    out = np.empty(len(idx))
    for b, mu in enumerate(B.boot_means(M, idx)):
        out[b] = fixed_points(make_curve(grid, mu, unimodal=unimodal), lam).b_c
    return out


def robustness_label(bc_boot: np.ndarray, b_emp: Optional[int], status: str, sizes: Sequence[int], level: float
                     ) -> Dict[str, Any]:
    """R3 robustness: does the registered verdict function give the same verdict over the whole bootstrap interval of b_c?"""
    iv = B.interval(bc_boot, level)
    if iv["n"] == 0:
        return {"label": NA, "interval": iv, "verdicts_in_interval": [], "P_pass": float("nan")}
    lo, hi = iv["lo"], iv["hi"]
    pts = {lo, hi}
    for cp in r3_change_points(b_emp, status, sizes):
        if lo <= cp <= hi:
            pts |= {cp - 1e-9, cp, cp + 1e-9}
    pts = {p for p in pts if lo - 1e-12 <= p <= hi + 1e-12}
    verdicts = sorted({r3_verdict(p, b_emp, status, sizes)[0] for p in pts})
    ok = ~np.isnan(bc_boot)
    p_pass = float(np.mean([r3_verdict(float(b), b_emp, status, sizes)[0] == PASS for b in bc_boot[ok]]))
    return {"label": ROBUST if len(verdicts) == 1 else FRAGILE, "interval": iv, "verdicts_in_interval": verdicts,
            "P_pass": p_pass}


def eval_r3_robustness(cr: pd.DataFrame, burst_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any],
                       boot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Row R3-robustness: ROBUST / FRAGILE (NOT_EVALUABLE if the headline R3 is). Never changes the headline verdict."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    sizes, bseeds = d["burst"]["sizes"], d["burst"]["seeds"]
    nb, ent, lev = _boot_cfg(boot)
    if burst_runs is None:
        return _row("R3-robustness", NA, {}, "no E-burst runs", "sensitivity")
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
        nr, nn = burst_table(burst_runs, d["burst"]["policies"]["primary"], sizes, bseeds)
    except Missing as e:
        return _row("R3-robustness", NA, {}, str(e), "sensitivity")
    lam = d["burst"]["lam_mult"] * lam_miss
    b_emp, status = empirical_critical_burst(sizes, nr, nn)
    idx = B.resample_indices("R3", M.shape[1], nb, ent)
    rep = bc_replicates(M, grid, lam, idx)
    rob = robustness_label(rep, b_emp, status, sizes, lev)
    point = fixed_points(make_curve(grid, M.mean(axis=1)), lam)
    head = r3_verdict(point.b_c, b_emp, status, sizes)[0]
    label = rob["label"] if head != NA else NA
    nums = {"b_c_point": point.b_c, "b_emp": b_emp, "b_emp_status": status, "headline_verdict": head, "n_boot": nb,
            "bootstrap": rob, "b_c_replicate_quantiles": {q: float(np.nanpercentile(rep[np.isfinite(rep)], q))
                                                           for q in (5, 25, 50, 75, 95)} if np.isfinite(rep).any() else {}}
    return _row("R3-robustness", label, nums,
                "ROBUST iff the registered R3 verdict is the same over the whole 95% bootstrap interval of b_c (seed resampling of "
                "the FCFS-LRU curve; b_emp taken as observed); the label never changes the headline. With 3 seeds the bootstrap "
                "interval is narrow, and the stage-2 review measured a larger sampling SD (0.67) over disjoint 3-seed sets on "
                "non-registered seeds (not re-verified here), so a ROBUST label is optimistic (amendment 2)", "sensitivity")


def eval_r3_envelope(cr: pd.DataFrame, burst_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any]
                     ) -> Dict[str, Any]:
    """Row R3-envelope: the registered verdict function with b_env (monotone envelope) in place of b_emp."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    sizes, bseeds = d["burst"]["sizes"], d["burst"]["seeds"]
    if burst_runs is None:
        return _row("R3-envelope", NA, {}, "no E-burst runs", "sensitivity")
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
        nr, _ = burst_table(burst_runs, d["burst"]["policies"]["primary"], sizes, bseeds)
    except Missing as e:
        return _row("R3-envelope", NA, {}, str(e), "sensitivity")
    lam = d["burst"]["lam_mult"] * lam_miss
    fp = fixed_points(make_curve(grid, M.mean(axis=1)), lam)
    b_env, status = monotone_envelope_burst(sizes, nr)
    b_emp, st_emp = empirical_critical_burst(sizes, nr, [len(bseeds)] * len(sizes))
    verdict, note = r3_verdict(fp.b_c, b_env, status, sizes)
    return _row("R3-envelope", verdict, {"b_env": b_env, "b_env_status": status, "b_emp": b_emp, "b_emp_status": st_emp,
                                         "b_c": fp.b_c, "not_recovered_by_size": dict(zip(map(int, sizes), nr))},
                note or "b_env = smallest size such that every larger size also has >= 3/5 not recovered", "sensitivity")


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


def eval_burst_info(cr: pd.DataFrame, info_runs: Optional[pd.DataFrame], burst_runs: Optional[pd.DataFrame],
                    lam_miss: float, d: Dict[str, Any], info: Optional[Dict[str, Any]],
                    boot: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Information rows from the burst_info cells: R3-info-b0 (no-burst controls) and R3-info-lambda (lambda dependence of b_c
    and of the empirical critical burst, with the bootstrap interval of the fluid b_c)."""
    ids = ("R3-info-b0", "R3-info-lambda")
    if info_runs is None or not info:
        return [_row(i, NA, {}, "no burst_info runs", "information") for i in ids]
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    nb, ent, lev = _boot_cfg(boot)
    ld, cr_ = info["lambda_dependence"], info["control_random"]
    bseeds = info["seeds"]
    runs = info_runs.copy()
    runs["rec"] = runs["recovered"].map(_is_true)
    # ---- b = 0 controls
    b0 = []
    for pol, mult in ((ld["policy"], m) for m in ld["lam_mults"]):
        g = runs[(runs["policy"] == pol) & np.isclose(runs["lam_mult"].astype(float), mult) & (runs["burst_n"] == 0)]
        b0.append({"policy": pol, "lam_mult": float(mult), "n_runs": int(len(g)), "n_not_recovered": int((~g["rec"]).sum())})
    g = runs[(runs["policy"] == cr_["policy"]) & np.isclose(runs["lam_mult"].astype(float), cr_["lam_mult"])
             & (runs["burst_n"] == 0)]
    b0.append({"policy": cr_["policy"], "lam_mult": float(cr_["lam_mult"]), "n_runs": int(len(g)),
               "n_not_recovered": int((~g["rec"]).sum())})
    rows = [_row("R3-info-b0", INFO, {"no_burst_controls": b0},
                 "b = 0 on the registered burst seeds: runs that are not recovered without any burst", "information")]
    # ---- lambda dependence
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
    except Missing as e:
        return rows + [_row("R3-info-lambda", NA, {}, str(e), "information")]
    sizes = list(ld["sizes"])
    idx = B.resample_indices("R3", M.shape[1], nb, ent)
    per_lam = []
    for mult in ld["lam_mults"]:
        lam = float(mult) * lam_miss
        nr, nn = [], []
        for b in sizes:
            gg = runs[(runs["policy"] == ld["policy"]) & np.isclose(runs["lam_mult"].astype(float), mult)
                      & (runs["burst_n"] == b) & runs["seed"].isin(bseeds)]
            if sorted(int(s) for s in gg["seed"]) != sorted(int(s) for s in bseeds):
                return rows + [_row("R3-info-lambda", NA, {}, f"burst_info cell (lam_mult {mult}, size {b}) lacks the seeds", "information")]
            nr.append(int((~gg["rec"]).sum()))
            nn.append(int(len(gg)))
        fp = fixed_points(make_curve(grid, M.mean(axis=1)), lam)
        rep = bc_replicates(M, grid, lam, idx)
        b_emp, st = empirical_critical_burst(sizes, nr, nn)
        b_env, st_env = monotone_envelope_burst(sizes, nr)
        # b_emp == 0 (the no-burst control already fails) leaves the ratio undefined (NaN)
        ratio = (fp.b_c / b_emp) if (b_emp and math.isfinite(fp.b_c)) else float("nan")
        per_lam.append({"lam_mult": float(mult), "lambda": lam, "fluid": _fp_dict(fp), "b_c_interval": B.interval(rep, lev),
                        "b_emp": b_emp, "b_emp_status": st, "b_env": b_env, "b_env_status": st_env,
                        "b_c_over_b_emp": ratio, "within_factor_2": bool(0.5 <= ratio <= 2.0) if np.isfinite(ratio) else None,
                        "not_recovered_by_size": dict(zip(map(int, sizes), nr))})
    # determinism check: lam_mult 2.0 cells of the fine grid that coincide with registered E-burst runs must agree exactly
    check = {"n_compared": 0, "n_mismatch": 0}
    if burst_runs is not None:
        reg = burst_runs[burst_runs["policy"] == ld["policy"]]
        for _, r in runs[(runs["policy"] == ld["policy"]) & np.isclose(runs["lam_mult"].astype(float), 2.0)].iterrows():
            m = reg[(reg["burst_n"] == r["burst_n"]) & (reg["seed"] == r["seed"])]
            if len(m) == 1:
                check["n_compared"] += 1
                check["n_mismatch"] += int(_is_true(m["recovered"].iloc[0]) != bool(r["rec"]))
    rows.append(_row("R3-info-lambda", INFO, {"per_lambda": per_lam, "registered_consistency_check": check},
                     "lambda dependence of the fluid b_c and of the empirical critical burst on the fine grid (information; CRN with "
                     "the registered burst seeds); a weak trend may be unresolvable on a step-5 grid", "information"))
    return rows


def eval_r3_posthoc_b0_excluded(cr: pd.DataFrame, burst_runs: Optional[pd.DataFrame], info_runs: Optional[pd.DataFrame],
                                lam_miss: float, d: Dict[str, Any], info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """POST-HOC, UNREGISTERED information row (amendment 2): the registered FCFS-LRU burst counts recomputed without the seeds that
    are not recovered at b = 0 (no burst) at 2 lambda_miss in the burst_info cells. Never decides anything."""
    pid = "R3-posthoc-b0-excluded"
    if burst_runs is None or info_runs is None or not info:
        return _row(pid, NA, {}, "needs the E-burst and burst_info runs", "information")
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    sizes, bseeds = d["burst"]["sizes"], d["burst"]["seeds"]
    pol = d["burst"]["policies"]["primary"]
    try:
        M = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds)
        nr, nn = burst_table(burst_runs, pol, sizes, bseeds)
    except Missing as e:
        return _row(pid, NA, {}, str(e), "information")
    g0 = info_runs[(info_runs["policy"] == pol) & np.isclose(info_runs["lam_mult"].astype(float), d["burst"]["lam_mult"])
                   & (info_runs["burst_n"] == 0) & info_runs["seed"].isin(bseeds)]
    if sorted(int(s_) for s_ in g0["seed"]) != sorted(int(s_) for s_ in bseeds):
        return _row(pid, NA, {}, "burst_info b = 0 cell lacks the registered seeds", "information")
    trapped0 = sorted(int(s_) for s_, rec in zip(g0["seed"], g0["recovered"]) if not _is_true(rec))
    rest = [int(s_) for s_ in bseeds if int(s_) not in trapped0]
    reg = burst_runs[burst_runs["policy"] == pol].assign(rec=lambda x: x["recovered"].map(_is_true))
    nr_ex = [int(((~reg[(reg["burst_n"] == b) & reg["seed"].isin(rest)]["rec"]).sum())) for b in sizes]
    first_fail: Dict[str, Optional[int]] = {}
    for sd in bseeds:
        fails = {int(b): not bool(reg[(reg["burst_n"] == b) & (reg["seed"] == sd)]["rec"].iloc[0]) for b in sizes}
        ff = None
        for j, b in enumerate(sizes):
            if all(fails[int(x)] for x in sizes[j:]):
                ff = int(b)
                break
        first_fail[str(int(sd))] = ff
    n_rem = len(rest)
    lam = d["burst"]["lam_mult"] * lam_miss
    fp = fixed_points(make_curve(grid, M.mean(axis=1)), lam)
    nums = {"baseline_trapped_seeds": trapped0, "remaining_seeds": rest, "not_recovered_by_size_all_seeds": dict(zip(map(int, sizes), nr)),
            "not_recovered_by_size_excluding_baseline_trapped": dict(zip(map(int, sizes), nr_ex)),
            "first_size_from_which_every_larger_size_is_not_recovered_by_seed": first_fail, "b_c": fp.b_c}
    if n_rem == 0:
        return _row(pid, NA, nums, "every seed is trapped at b = 0", "information")
    need = int(math.ceil(0.6 * n_rem - 1e-9))
    b_ex, st = empirical_critical_burst(sizes, nr_ex, [n_rem] * len(sizes), need)
    nums.update({"min_count_rule": f">= ceil(0.6 x {n_rem}) = {need} of {n_rem}", "b_emp_excl": b_ex, "b_emp_excl_status": st,
                 "b_c_over_b_emp_excl": (fp.b_c / b_ex) if (b_ex and math.isfinite(fp.b_c)) else float("nan")})
    return _row(pid, INFO, nums, "POST-HOC and unregistered (amendment 2): the registered burst counts without the seeds that are not "
                                 "recovered at b = 0; information only, the headline R3 is unchanged", "information")


# ----------------------------------------------------------------------------------------------- R4
def phase_threshold(phase_runs: pd.DataFrame, policy: str, min_horizon_s: float, need: int = 2, n_seeds: int = 3
                    ) -> Dict[str, Any]:
    """Empirical recovery-threshold interval [lo, hi] of ``policy`` from the round-3 phase runs (150k-s multiples only):
    lo = largest multiple such that every multiple <= it has >= ``need`` of ``n_seeds`` recovered; hi = smallest multiple
    above lo with <= need - 1 recovered."""
    sel = phase_runs[(phase_runs["policy"] == policy) & (phase_runs["horizon_used_s"].astype(float) >= min_horizon_s)]
    rows = []
    for m, g in sel.groupby("lam_mult"):
        rec = g["recovered"].map(_is_true)
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


def r4_tests(r: float, lo: float, hi: float) -> Dict[str, bool]:
    """All R4 readings for a predicted ratio ``r`` and an empirical bracket [lo, hi] (t = midpoint).

    registered       |r - t| <= 0.15 t                       (band centred on the empirical value; the registered headline)
    verbatim         |t - r| <= 0.15 r                       (band centred on the prediction; the claim's orientation)
    strict/lenient   verbatim orientation, EVERY / SOME point of [lo, hi]: hi/1.15 <= r <= lo/0.85 ; lo/1.15 <= r <= hi/0.85
    *_as_registered  the original formulas 0.85 hi <= r <= 1.15 lo ; 0.85 lo <= r <= 1.15 hi
    bracket          lo < r <= hi
    headline         registered AND verbatim (amendment 1: strictly stricter than the registered headline)"""
    t = 0.5 * (lo + hi)
    reg = abs(r - t) <= 0.15 * t
    ver = abs(t - r) <= 0.15 * r
    return {"registered": reg, "verbatim": ver, "headline": reg and ver,
            "strict": hi / 1.15 <= r <= lo / 0.85, "lenient": lo / 1.15 <= r <= hi / 0.85,
            "strict_as_registered": 0.85 * hi <= r <= 1.15 * lo, "lenient_as_registered": 0.85 * lo <= r <= 1.15 * hi,
            "bracket": lo < r <= hi}


R4_POLICIES = (("FCFS", "fcfs_lru"), ("LPM", "lpm_lru"))


def eval_r4(cr: pd.DataFrame, phase_runs: Optional[pd.DataFrame], lam_miss: float, d: Dict[str, Any],
            boot: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """R4 rows: the amended headline first, then the labelled sensitivities (see ``r4_tests``) and R4-bootstrap (information)."""
    grid, seeds = list(d["curve"]["n_grid"]), d["curve"]["seeds"]
    src = d["r4_sources"]
    ids = ["R4", "R4-as-registered", "R4-strict", "R4-lenient", "R4-strict-as-registered", "R4-lenient-as-registered",
           "R4-bracket", "R4-mintail"]
    readings = {i: ("headline" if i == "R4" else "sensitivity") for i in ids}

    def all_na(msg: str) -> List[Dict[str, Any]]:
        return [_row(i, NA, {}, msg, readings[i], _claim("R4")) for i in ids] + [_row("R4-bootstrap", NA, {}, msg, "information")]

    if phase_runs is None:
        return all_na("round-3 phase runs not available")
    nums: Dict[str, Any] = {}
    flags = {i: True for i in ids}
    mats: Dict[str, np.ndarray] = {}
    try:
        for label, pol in R4_POLICIES:
            M = seed_matrix(cr, pol, 1.0, grid, seeds)
            if 300 not in grid:
                raise Missing("n = 300 not in the registered grid")
            mats[label] = M
            mu = M.mean(axis=1)
            i300 = grid.index(300)
            th = phase_threshold(phase_runs, src["phase_policies"][label], src["min_horizon_s"])
            if not th["ok"]:
                raise Missing(th["reason"])
            r = float(mu[i300]) / lam_miss
            i_p = int(np.argmax(mu))
            r_min = float(np.min(mu[i_p:])) / lam_miss
            lo, hi = th["lo"], th["hi"]
            t = 0.5 * (lo + hi)
            tt = r4_tests(r, lo, hi)
            tm = r4_tests(r_min, lo, hi)
            nums[label] = {"mu300": float(mu[i300]), "mu300_se": float(B.se_rows(M)[i300]), "r_pred": r,
                           "r_pred_se": float(B.se_rows(M)[i300]) / lam_miss, "lo": lo, "hi": hi, "t_mid": t,
                           "rel_err_vs_mid": (r - t) / t, "within_15pct_of_mid_registered_orientation": tt["registered"],
                           "within_15pct_verbatim_orientation": tt["verbatim"], "tests": tt,
                           "n_star_own": int(grid[i_p]), "r_pred_min_over_n>=n_star": r_min, "tests_mintail": tm,
                           "phase_cells": th["cells"]}
            flags["R4"] &= tt["headline"]
            flags["R4-as-registered"] &= tt["registered"]
            flags["R4-strict"] &= tt["strict"]
            flags["R4-lenient"] &= tt["lenient"]
            flags["R4-strict-as-registered"] &= tt["strict_as_registered"]
            flags["R4-lenient-as-registered"] &= tt["lenient_as_registered"]
            flags["R4-bracket"] &= tt["bracket"]
            flags["R4-mintail"] &= tm["headline"]
    except Missing as e:
        return all_na(str(e))
    notes = {"R4": "amended headline: registered |r-t|<=0.15 t AND verbatim |t-r|<=0.15 r, both policies",
             "R4-mintail": "amended headline rule applied to r from min over n>=n*_p of the seed-mean mu_p(n)"}
    out = [_row(i, PASS if flags[i] else FAIL, nums, notes.get(i, ""), readings[i], _claim("R4")) for i in ids]
    # bootstrap of the headline (information)
    nb, ent, lev = _boot_cfg(boot)
    idx = B.resample_indices("R4", len(seeds), nb, ent)
    i300 = grid.index(300)
    res: Dict[str, Any] = {"n_boot": nb}
    pass_b = np.ones(nb, dtype=bool)
    for label, _ in R4_POLICIES:
        r_b = B.boot_means(mats[label], idx)[:, i300] / lam_miss
        lo, hi = nums[label]["lo"], nums[label]["hi"]
        ok = np.array([r4_tests(float(x), lo, hi)["headline"] for x in r_b])
        pass_b &= ok
        res[label] = {"r_interval": B.interval(r_b, lev), "P_headline_pass_policy": float(ok.mean())}
    res["P_headline_pass_both"] = float(pass_b.mean())
    out.append(_row("R4-bootstrap", INFO, res, "seed bootstrap of r_p = mu_p(300)/lambda_miss at the observed empirical brackets",
                    "information"))
    return out


# ----------------------------------------------------------------------------------------------- R5
def eval_r5(cap_runs: Optional[pd.DataFrame], d: Dict[str, Any]) -> List[Dict[str, Any]]:
    cd = d["cap"]
    caps5 = [32, 36, 40]
    if cap_runs is None:
        return [_row("R5", NA, {}, "no E-cap runs"), _row("R5-union", NA, {}, "no E-cap runs", "sensitivity")]
    seeds = cd["seeds"]
    cells: Dict[Tuple[str, int], Dict[str, int]] = {}
    for ev in cd["evictions"]:
        for cap in cd["caps"]:
            g = cap_runs[(cap_runs["eviction"] == ev) & (cap_runs["cap"] == cap)]
            if sorted(int(s) for s in g["seed"]) != sorted(int(s) for s in seeds):
                return [_row("R5", NA, {}, f"E-cap cell ({ev}, {cap}) does not have the registered seeds"),
                        _row("R5-union", NA, {}, "see R5", "sensitivity", _claim("R5"))]
            rec = g["recovered"].map(_is_true)
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
    return [_row("R5", head, nums, note), _row("R5-union", sens, nums, note, "sensitivity", _claim("R5"))]


# ----------------------------------------------------------------------------------------------- R6
R6_KS = (0.5, 1.0, 2.0)
R6_MARGIN = 1.10          # registered in amendment 1: E(2) >= 1.10


def loo_mu_star(M: np.ndarray) -> float:
    """Leave-one-seed-out estimate of mu*: the argmax is chosen on the mean of the other seeds and evaluated on the held-out
    seed; averaged over the folds (removes the upward selection bias of max_n of a noisy seed-mean)."""
    S = M.shape[1]
    vals = []
    for j in range(S):
        others = np.delete(M, j, axis=1).mean(axis=1)
        vals.append(M[int(np.argmax(others)), j])
    return float(np.mean(vals))


def r6_quantities(mu_star: Dict[float, float], lambda_cap: Dict[float, float], lambda_miss_k: Dict[float, float]
                  ) -> Dict[str, Dict[float, float]]:
    """rho = lambda_cap / mu*, c = mu* / lambda_miss(k), the ratio lambda_cap / lambda_miss(k), the null-implied
    rho_null = lambda_cap / (c(1) lambda_miss(k)) and the excess ratio E = rho / rho_null = c(1) / c(k)."""
    c = {k: mu_star[k] / lambda_miss_k[k] for k in R6_KS}
    rho = {k: lambda_cap[k] / mu_star[k] for k in R6_KS}
    cap_over_miss = {k: lambda_cap[k] / lambda_miss_k[k] for k in R6_KS}
    rho_null = {k: cap_over_miss[k] / c[1.0] for k in R6_KS}
    E = {k: rho[k] / rho_null[k] for k in R6_KS}
    return {"rho": rho, "c": c, "cap_over_miss": cap_over_miss, "rho_null": rho_null, "E": E}


def beyond_null(E: Dict[float, float], margin: float = R6_MARGIN) -> bool:
    """Registered interpretation rule: E(0.5) < 1 and E(2) >= margin."""
    return bool(E[0.5] < 1.0 and E[2.0] >= margin)


def eval_r6(cr: pd.DataFrame, lambda_cap: Optional[Dict[float, float]], d: Dict[str, Any],
            lambda_miss_k: Optional[Dict[float, float]] = None) -> Dict[str, Any]:
    """Headline R6 (strict increase of rho(k) = lambda_cap(k)/mu*(k)). With ``lambda_miss_k`` the numbers also carry c(k),
    rho_null(k) and E(k) (amendment 1)."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    if not lambda_cap or any(k not in lambda_cap for k in R6_KS):
        return _row("R6", NA, {}, "lambda_cap(k) of the round-3 escape results not available")
    rho, nums, mu_star = {}, {}, {}
    try:
        for k in R6_KS:
            M = seed_matrix(cr, "fcfs_lru", k, grid, seeds)
            mu = M.mean(axis=1)
            i = int(np.argmax(mu))
            mu_star[k] = float(mu[i])
            rho[k] = lambda_cap[k] / mu_star[k]
            seed_max = M.max(axis=0)
            nums[f"k={k}"] = {"lambda_cap": lambda_cap[k], "mu_star": mu_star[k], "argmax_n_nominal": int(grid[i]),
                              "argmax_n_actual": int(round_half_up(k * grid[i])) if k != 1.0 else int(grid[i]),
                              "mu_star_se_at_argmax": float(B.se_rows(M)[i]),
                              "rho": rho[k], "per_seed_mu_star": [float(x) for x in seed_max],
                              "per_seed_rho": [float(lambda_cap[k] / x) for x in seed_max]}
    except Missing as e:
        return _row("R6", NA, {}, str(e))
    if lambda_miss_k and all(k in lambda_miss_k for k in R6_KS):
        q = r6_quantities(mu_star, lambda_cap, lambda_miss_k)
        for k in R6_KS:
            nums[f"k={k}"].update({"lambda_miss_k": lambda_miss_k[k], "c_mu_star_over_lambda_miss": q["c"][k],
                                   "lambda_cap_over_lambda_miss": q["cap_over_miss"][k], "rho_null": q["rho_null"][k],
                                   "E_excess_ratio": q["E"][k]})
    inc = rho[0.5] < rho[1.0] < rho[2.0]
    return _row("R6", PASS if inc else FAIL, nums,
                "lambda_cap(k) is a finite-horizon (20000 s) from-empty stability limit, not a fluid quantity; R6 passes under the "
                "k-independent-shape null (see R6-beyond-null)")


def eval_r6_extras(cr: pd.DataFrame, lambda_cap: Optional[Dict[float, float]], lambda_miss_k: Optional[Dict[float, float]],
                   d: Dict[str, Any], boot: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """R6-beyond-null, R6-loo, R6-loo-beyond-null (sensitivity) and R6-bootstrap (information)."""
    ids = [("R6-beyond-null", "sensitivity"), ("R6-loo", "sensitivity"), ("R6-loo-beyond-null", "sensitivity"),
           ("R6-bootstrap", "information")]
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]

    def all_na(msg: str) -> List[Dict[str, Any]]:
        return [_row(i, NA, {}, msg, rd, _claim("R6")) for i, rd in ids]

    if not lambda_cap or any(k not in lambda_cap for k in R6_KS):
        return all_na("lambda_cap(k) not available")
    if not lambda_miss_k or any(k not in lambda_miss_k for k in R6_KS):
        return all_na("lambda_miss(k) not available")
    try:
        mats = {k: seed_matrix(cr, "fcfs_lru", k, grid, seeds) for k in R6_KS}
    except Missing as e:
        return all_na(str(e))
    mu_star = {k: float(mats[k].mean(axis=1).max()) for k in R6_KS}
    q = r6_quantities(mu_star, lambda_cap, lambda_miss_k)
    mu_loo = {k: loo_mu_star(mats[k]) for k in R6_KS}
    ql = r6_quantities(mu_loo, lambda_cap, lambda_miss_k)
    beyond, beyond_l = beyond_null(q["E"]), beyond_null(ql["E"])
    inc_l = ql["rho"][0.5] < ql["rho"][1.0] < ql["rho"][2.0]

    def pack(qq: Dict[str, Dict[float, float]], ms: Dict[float, float]) -> Dict[str, Any]:
        return {f"k={k}": {"mu_star": ms[k], "c": qq["c"][k], "rho": qq["rho"][k], "rho_null": qq["rho_null"][k],
                           "E": qq["E"][k], "lambda_cap_over_lambda_miss": qq["cap_over_miss"][k]} for k in R6_KS}

    nb, ent, lev = _boot_cfg(boot)
    idx = B.resample_indices("R6", len(seeds), nb, ent)
    reps = {k: B.boot_means(mats[k], idx).max(axis=1) for k in R6_KS}               # (B,) mu*(k)
    rho_b = {k: lambda_cap[k] / reps[k] for k in R6_KS}
    c_b = {k: reps[k] / lambda_miss_k[k] for k in R6_KS}
    E_b = {k: c_b[1.0] / c_b[k] for k in R6_KS}
    bnums: Dict[str, Any] = {"n_boot": nb}
    for k in R6_KS:
        bnums[f"k={k}"] = {"rho": B.interval(rho_b[k], lev), "c": B.interval(c_b[k], lev), "E": B.interval(E_b[k], lev)}
    bnums["P_rho_strictly_increasing"] = float(np.mean((rho_b[0.5] < rho_b[1.0]) & (rho_b[1.0] < rho_b[2.0])))
    bnums["P_beyond_null"] = float(np.mean((E_b[0.5] < 1.0) & (E_b[2.0] >= R6_MARGIN)))
    note_b = ("PASS iff E(0.5) < 1 and E(2) >= %.2f, E = rho / rho_null = c(1)/c(k), c = mu*/lambda_miss(k) (amendment 1)"
              % R6_MARGIN)
    return [_row("R6-beyond-null", PASS if beyond else FAIL, pack(q, mu_star), note_b, "sensitivity", _claim("R6")),
            _row("R6-loo", PASS if inc_l else FAIL, pack(ql, mu_loo),
                 "strict increase of rho(k) with mu*(k) replaced by the leave-one-seed-out estimate", "sensitivity", _claim("R6")),
            _row("R6-loo-beyond-null", PASS if beyond_l else FAIL, pack(ql, mu_loo), note_b + "; leave-one-seed-out mu*",
                 "sensitivity", _claim("R6")),
            _row("R6-bootstrap", INFO, bnums, "seed bootstrap (same resample for every k); information", "information")]


# ----------------------------------------------------------------------------------------------- bootstrap table
def _rep_rows(rows: List[Dict[str, Any]], quantity: str, policy: str, k: float, est: float, rep: np.ndarray, lev: float,
              note: str = "") -> None:
    iv = B.interval(rep, lev)
    rows.append({"quantity": quantity, "policy": policy, "k": k, "estimate": est, "lo": iv["lo"], "median": iv["median"],
                 "hi": iv["hi"], "n_boot": iv["n"], "n_nan": iv["n_nan"], "n_inf": iv["n_inf"], "note": note})


def bootstrap_table(cr: pd.DataFrame, lam_miss: float, d: Dict[str, Any], lambda_cap: Optional[Dict[float, float]] = None,
                    lambda_miss_k: Optional[Dict[float, float]] = None, boot: Optional[Dict[str, Any]] = None
                    ) -> pd.DataFrame:
    """Seed-bootstrap intervals of the derived quantities: n*, mu*/lambda_miss and mu(300)/lambda_miss per policy, the fluid
    b_c (and n1, n2 at 2 lambda_miss) of FCFS-LRU at lambda = 1.5, 2, 2.5 lambda_miss, the R2 ratio, rho(k), c(k), E(k)."""
    grid, seeds = d["curve"]["n_grid"], d["curve"]["seeds"]
    nb, ent, lev = _boot_cfg(boot)
    rows: List[Dict[str, Any]] = []
    G = np.asarray(grid)
    idx = B.resample_indices("table", len(seeds), nb, ent)
    for pol in ("fcfs_lru", "lpm_lru", "fcfs_random", "fcfs_mru_idle"):
        try:
            M = seed_matrix(cr, pol, 1.0, grid, seeds)
        except Missing:
            continue
        bm = B.boot_means(M, idx)
        mu = M.mean(axis=1)
        _rep_rows(rows, "n_star", pol, 1.0, float(G[int(np.argmax(mu))]), G[np.argmax(bm, axis=1)], lev)
        _rep_rows(rows, "mu_star_over_lambda_miss", pol, 1.0, float(mu.max() / lam_miss), bm.max(axis=1) / lam_miss, lev)
        if 300 in grid:
            i3 = list(grid).index(300)
            _rep_rows(rows, "mu300_over_lambda_miss", pol, 1.0, float(mu[i3] / lam_miss), bm[:, i3] / lam_miss, lev)
    try:
        ML, MO = _lru_and_random(cr, d)
        mu_l = ML.mean(axis=1)
        for mult in (1.5, 2.0, 2.5):
            lam = mult * lam_miss
            rep = bc_replicates(ML, grid, lam, idx)
            fp = fixed_points(make_curve(grid, mu_l), lam)
            _rep_rows(rows, f"b_c@{mult}x", "fcfs_lru", 1.0, fp.b_c, rep, lev, "fluid, unimodal-projected")
            if mult == 2.0:
                for nm in ("n1", "n2"):
                    r2 = np.array([getattr(fixed_points(make_curve(grid, m), lam), nm) for m in B.boot_means(ML, idx)])
                    _rep_rows(rows, f"{nm}@2.0x", "fcfs_lru", 1.0, getattr(fp, nm), r2, lev)
        n_star = int(G[int(np.argmax(mu_l))])
        bl, bo = B.boot_means(ML, idx), B.boot_means(MO, idx)
        ratios = np.array([r2_point(grid, bl[b], bo[b], int(G[int(np.argmax(bl[b]))]))["ratio"] for b in range(nb)])
        _rep_rows(rows, "R2_ratio_random_over_lru", "fcfs_random", 1.0, r2_point(grid, mu_l, MO.mean(axis=1), n_star)["ratio"],
                  ratios, lev, "n* re-estimated in every resample")
    except Missing:
        pass
    if lambda_cap and lambda_miss_k and all(k in lambda_cap and k in lambda_miss_k for k in R6_KS):
        try:
            mats = {k: seed_matrix(cr, "fcfs_lru", k, grid, seeds) for k in R6_KS}
            q = r6_quantities({k: float(mats[k].mean(axis=1).max()) for k in R6_KS}, lambda_cap, lambda_miss_k)
            ridx = B.resample_indices("R6", len(seeds), nb, ent)
            reps = {k: B.boot_means(mats[k], ridx).max(axis=1) for k in R6_KS}
            cb = {k: reps[k] / lambda_miss_k[k] for k in R6_KS}
            for k in R6_KS:
                _rep_rows(rows, "rho", "fcfs_lru", k, q["rho"][k], lambda_cap[k] / reps[k], lev)
                _rep_rows(rows, "c_mu_star_over_lambda_miss_k", "fcfs_lru", k, q["c"][k], cb[k], lev)
                _rep_rows(rows, "E_excess_ratio", "fcfs_lru", k, q["E"][k], cb[1.0] / cb[k], lev)
        except Missing:
            pass
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------- suppression
def suppress_verdicts(rows: Sequence[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
    """Turn every test verdict into NOT_EVALUABLE (numbers kept) because an input is unsafe (quick, dirty tree, no meta)."""
    out = []
    for r in rows:
        if r["verdict"] in TEST_VERDICTS:
            r = {**r, "verdict": NA, "notes": (r["notes"] + " " if r["notes"] else "") + f"VERDICT SUPPRESSED: {reason}"}
        out.append(r)
    return out


# ----------------------------------------------------------------------------------------------- all
def evaluate_all(cr: Optional[pd.DataFrame], burst_runs: Optional[pd.DataFrame], cap_runs: Optional[pd.DataFrame],
                 phase_runs: Optional[pd.DataFrame], lambda_cap: Optional[Dict[float, float]], lam_miss: float,
                 design: Dict[str, Any], *, lambda_miss_k: Optional[Dict[float, float]] = None,
                 burst_info_runs: Optional[pd.DataFrame] = None, burst_info: Optional[Dict[str, Any]] = None,
                 boot: Optional[Dict[str, Any]] = None, claims: Optional[Dict[str, str]] = None
                 ) -> List[Dict[str, Any]]:
    """Headline rows R1..R6 first (registered readings; R4 as amended), then the labelled sensitivity / information rows."""
    global _CLAIMS_OVERRIDE
    prev, _CLAIMS_OVERRIDE = _CLAIMS_OVERRIDE, claims
    try:
        return _evaluate_all(cr, burst_runs, cap_runs, phase_runs, lambda_cap, lam_miss, design, lambda_miss_k,
                             burst_info_runs, burst_info, boot)
    finally:
        _CLAIMS_OVERRIDE = prev


def _evaluate_all(cr, burst_runs, cap_runs, phase_runs, lambda_cap, lam_miss, design, lambda_miss_k, burst_info_runs,
                  burst_info, boot) -> List[Dict[str, Any]]:
    d = design
    if cr is None:
        return [_row(f"R{i}", NA, {}, "no E-curve runs") if i != 5 else eval_r5(cap_runs, d)[0] for i in range(1, 7)]
    r1, n_star = eval_r1(cr, lam_miss, d)
    r2 = eval_r2(cr, n_star, d)
    r3 = eval_r3(cr, burst_runs, lam_miss, d)
    r4 = eval_r4(cr, phase_runs, lam_miss, d, boot)
    r5 = eval_r5(cap_runs, d)
    lmk = {**(lambda_miss_k or {}), 1.0: lam_miss} if lambda_miss_k else None
    r6 = eval_r6(cr, lambda_cap, d, lmk)
    heads = [r1, r2, r3, r4[0], r5[0], r6]
    sens = [eval_r2(cr, n_star, d, pid="R2-nearest-grid", reading="sensitivity", nearest=True),
            eval_r2(cr, n_star, d, other="fcfs_mru_idle", pid="R2-MRU", reading="information", informational=True),
            *eval_r1r2_nearmax(cr, lam_miss, d), *eval_r1r2_per_seed(cr, lam_miss, d), *eval_r1r2_bootstrap(cr, lam_miss, d, boot),
            eval_r3(cr, burst_runs, lam_miss, d, unimodal=False, pid="R3-raw", reading="sensitivity"),
            eval_r3_robustness(cr, burst_runs, lam_miss, d, boot), eval_r3_envelope(cr, burst_runs, lam_miss, d),
            eval_r3_info_random(cr, burst_runs, lam_miss, d),
            *eval_burst_info(cr, burst_info_runs, burst_runs, lam_miss, d, burst_info, boot),
            eval_r3_posthoc_b0_excluded(cr, burst_runs, burst_info_runs, lam_miss, d, burst_info),
            *r4[1:], r5[1], *eval_r6_extras(cr, lambda_cap, lmk, d, boot)]
    return heads + sens


def rows_to_frame(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{**r, "numbers": json.dumps(r["numbers"], default=float)} for r in rows],
                        columns=["id", "reading", "verdict", "claim", "numbers", "notes"])
