"""Evaluation of the pre-registered round-5 predictions S1-S4 (configs/prefix_meta_r5_prereg.yaml: ``decision_readings`` as clarified by
``amendment_2``) for each registered allocation mode.

Pure functions on DataFrames. Every ``eval_*`` returns rows ``{id, mode, reading, claim, verdict, numbers, notes}``. ``reading`` is
``"headline"`` (the registered reading: S1-S4, S1-KILL, ANSWER), ``"clause"`` (a clause of a headline test, reported separately as the
registration requires), ``"sensitivity"`` (labelled alternatives, including the sensitivity VARIANTS of amendment 2; never decide a
verdict) or ``"information"``. Verdicts: PASS / FAIL / NOT_EVALUABLE for tests, KILL_TRUE / KILL_FALSE for the S1 kill criterion,
persists / artifact / mixed for the ANSWER row, INFO for information rows. A test whose registered cells (grid x seeds) are not all present
is NOT_EVALUABLE, never judged on a partial design. The claim strings are read verbatim from the pre-registration.

Every headline row carries the preemption-thrash label of the cells it rests on (amendment 2) in ``numbers["thrash"]`` and in ``notes``;
the label never changes a verdict.

Inputs (``R5Inputs``)
  calib      calib_runs.csv         mode, seed, sessions_per_s, ...                          (lambda_miss per mode)
  curve      curve_runs.csv         mode, policy, n_nominal, seed, mu, ..., thrash, ...      (E-curve)
  burst      runs.csv               alloc_mode, burst_n, seed, recovered, tail_*, ...         (E-burst)
  cap        runs.csv               alloc_mode, arm, seed, cap, recovered, tail_*, ...        (E-cap)
"""
from __future__ import annotations

import functools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from .fluid import unimodal_projection
from .r4_eval import _py

PASS, FAIL, NA, INFO = "PASS", "FAIL", "NOT_EVALUABLE", "INFO"
KILL_T, KILL_F = "KILL_TRUE", "KILL_FALSE"
PERSISTS, ARTIFACT, MIXED = "persists", "artifact", "mixed"
TEST_VERDICTS = (PASS, FAIL, KILL_T, KILL_F, PERSISTS, ARTIFACT, MIXED)

PREREG_FILE = Path(__file__).resolve().parents[2] / "configs" / "prefix_meta_r5_prereg.yaml"
FCFS, LPM = "fcfs_lru", "lpm_lru"


class Missing(Exception):
    """Required cells of the registered design are absent."""


@functools.lru_cache(maxsize=8)
def _claims_from(path: str) -> Tuple[Tuple[str, str], ...]:
    preds = yaml.safe_load(Path(path).read_text())["preregistration"]["predictions"]
    return tuple((k, str(v)) for k, v in preds.items())


def registered_claims(path: Optional[Path] = None) -> Dict[str, str]:
    p = Path(path) if path else PREREG_FILE
    return dict(_claims_from(str(p))) if p.exists() else {}


@dataclass
class R5Inputs:
    calib: Optional[pd.DataFrame] = None
    curve: Optional[pd.DataFrame] = None
    burst: Optional[pd.DataFrame] = None
    cap: Optional[pd.DataFrame] = None


@dataclass
class Ctx:
    design: Dict[str, Any]                 # registered_design of the pre-registration (grid, seeds, modes)
    ev: Dict[str, Any]                     # config ``evaluation`` block (thresholds)
    thr: Dict[str, float]                  # config ``thrash`` block
    claims: Dict[str, str] = field(default_factory=dict)
    reading: str = "headline"
    suffix: str = ""                       # "@variant" for the sensitivity variants
    decode_tokens: int = 100               # workload d, for the scope statement of the ANSWER rows

    def pid(self, base: str) -> str:
        return base + self.suffix

    def row(self, base: str, mode: str, verdict: str, numbers: Dict[str, Any], notes: str = "", reading: Optional[str] = None) -> Dict[str, Any]:
        rd = reading or self.reading
        return {"id": self.pid(base), "mode": mode, "reading": rd, "claim": self.claims.get(base.split("-")[0], ""), "verdict": verdict,
                "numbers": _py(numbers), "notes": notes}


# ============================================================================================ lambda_miss
def lambda_miss_by_mode(calib: pd.DataFrame) -> Dict[str, float]:
    """Seed-mean per-run completion rate of the calibration runs (the registered lambda_m)."""
    return {m: float(g["sessions_per_s"].mean()) for m, g in calib.groupby("mode", sort=False)}


def lambda_miss_rows(calib: Optional[pd.DataFrame], ev: Dict[str, Any], ctx: Ctx, modes: Sequence[str]) -> List[Dict[str, Any]]:
    out = []
    if calib is None:
        return out
    for m in modes:
        g = calib[calib["mode"] == m].sort_values("seed")
        if g.empty:
            continue
        x = g["sessions_per_s"].to_numpy(dtype=float)
        ref = float(ev["round1_lambda_miss_full_reserve"])
        out.append(ctx.row("INFO-lambda_miss", m, INFO, {
            "lambda_miss": float(x.mean()), "sd": float(x.std(ddof=1)) if len(x) > 1 else float("nan"), "per_seed": x.tolist(),
            "seeds": [int(s) for s in g["seed"]], "ratio_to_round1_full_reserve": float(x.mean()) / ref,
            "preemptions_per_s": float(g["preemptions_per_s"].mean()) if "preemptions_per_s" in g else float("nan"),
            "preemptions_per_turn": float(g["preemptions_per_turn"].mean()) if "preemptions_per_turn" in g else float("nan"),
            "recompute_frac": float(g["recompute_frac"].mean()) if "recompute_frac" in g else float("nan")},
            "cache disabled, closed population 60, FCFS; CRN across modes (same seeds)", "information"))
    return out


# ============================================================================================ curve access
def curve_matrix(cr: pd.DataFrame, mode: str, policy: str, grid: Sequence[int], seeds: Sequence[int], col: str = "mu") -> np.ndarray:
    """``col`` per (grid point, seed): shape (len(grid), len(seeds)). Raises ``Missing`` unless every registered cell is present once."""
    sel = cr[(cr["mode"] == mode) & (cr["policy"] == policy)]
    if sel.duplicated(["n_nominal", "seed"]).any():
        raise ValueError(f"duplicate (n, seed) cells for {mode}/{policy}")
    piv = sel.pivot_table(index="n_nominal", columns="seed", values=col, aggfunc="first")
    miss = [(int(n), int(s)) for n in grid for s in seeds if n not in piv.index or s not in piv.columns or pd.isna(piv.loc[n, s])]
    if miss:
        raise Missing(f"{mode}/{policy}: {len(miss)} registered (n, seed) cells missing, e.g. {miss[:4]}")
    return piv.loc[list(grid), list(seeds)].to_numpy(dtype=float)


def curve_thrash(cr: pd.DataFrame, mode: str, policy: str, ns: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    """Thrash label per grid point: seeds flagged, largest preemptions per turn / most preemptions of one turn over the seeds."""
    out: Dict[int, Dict[str, Any]] = {}
    for n in ns:
        g = cr[(cr["mode"] == mode) & (cr["policy"] == policy) & (cr["n_nominal"] == n)]
        if g.empty or "thrash" not in g:
            continue
        out[int(n)] = {"n_flagged": int(g["thrash"].astype(bool).sum()), "n_seeds": int(len(g)),
                       "max_preemptions_per_turn": float(g["preemptions_per_turn"].max()),
                       "max_preempt_per_turn_in_window": float(g["preempt_max_turn"].max())}
    return out


def _thrash_note(cells: Dict[str, Dict[str, Any]]) -> str:
    flagged = [k for k, v in cells.items() if v.get("n_flagged", 0) > 0]
    if not cells:
        return "thrash label: not available"
    return ("THRASH-FLAG at " + ", ".join(flagged)) if flagged else "no thrash flag at the cells this rests on"


def edge_argmax(mu_bar: np.ndarray) -> bool:
    i = int(np.argmax(mu_bar))
    return i == 0 or i == len(mu_bar) - 1


# ============================================================================================ S1
def s1_stats(grid: Sequence[int], M: np.ndarray, lam: float, ev: Dict[str, Any], *, rel_tol: float, se_mult: Optional[float] = None,
             abs_tol: Optional[float] = None) -> Dict[str, Any]:
    """The three clauses and the kill criterion for the seed matrix ``M`` (grid x seeds). Unimodality: |mu_bar - u| <= max(se_mult SE, rel_tol
    lambda) at every grid point, u = unimodal projection (non-decreasing up to the FIRST argmax, non-increasing after, peak preserved); with
    ``abs_tol`` the tolerance is the constant ``abs_tol`` (strict variant)."""
    s1 = ev["S1"]
    k = M.shape[1]
    mu = M.mean(axis=1)
    se = M.std(axis=1, ddof=1) / math.sqrt(k) if k > 1 else np.zeros_like(mu)
    u = unimodal_projection(mu)
    sm = float(ev["unimodal"]["se_mult"]) if se_mult is None else se_mult
    tol = np.full_like(mu, abs_tol) if abs_tol is not None else np.maximum(sm * se, rel_tol * lam)
    dev = np.abs(mu - u)
    c0 = bool(np.all(dev <= tol))
    i_max = int(np.argmax(mu))
    mu300 = float(mu[-1])
    mx = float(mu[i_max])
    c1 = bool(mu300 <= float(s1["c1_mult"]) * lam)
    c2_num = bool(mx >= float(s1["c2_mult"]) * mu300)
    edge = edge_argmax(mu)
    c2 = bool(c2_num and not edge)
    kill = bool(mu300 >= float(s1["kill_frac"]) * mx)
    return {"C0_unimodal": c0, "C1": c1, "C2": c2, "C2_numeric": c2_num, "argmax_at_grid_edge": edge, "KILL": kill,
            "mu300": mu300, "mu_max": mx, "n_star": int(grid[i_max]), "mu300_over_lambda": mu300 / lam, "mu_max_over_lambda": mx / lam,
            "max_over_mu300": mx / mu300 if mu300 > 0 else float("inf"), "mu300_over_max": mu300 / mx if mx > 0 else float("nan"),
            "max_unimodal_deviation": float(dev.max()), "max_deviation_over_tol": float((dev / np.maximum(tol, 1e-300)).max()),
            "lambda_m": lam, "mu_bar": mu.tolist(), "mu_se": se.tolist(), "grid": [int(g) for g in grid]}


def _s1_inputs(inp: R5Inputs, mode: str, ctx: Ctx, policy: str = FCFS) -> Tuple[np.ndarray, float]:
    grid, seeds = ctx.design["curve"]["n_grid"], ctx.design["curve"]["seeds"]
    if inp.curve is None or inp.calib is None:
        raise Missing("curve or calibration runs absent")
    lam = lambda_miss_by_mode(inp.calib).get(mode)
    if lam is None:
        raise Missing(f"no calibration runs for {mode}")
    return curve_matrix(inp.curve, mode, policy, grid, seeds), lam


def _s1_thrash(inp: R5Inputs, mode: str, n_star: int) -> Dict[str, Dict[str, Any]]:
    cells: Dict[str, Dict[str, Any]] = {}
    for n in (n_star, 300):
        for pol in (FCFS,):
            t = curve_thrash(inp.curve, mode, pol, [n]).get(n)
            if t:
                cells[f"{pol} n={n}"] = t
    return cells


def eval_s1(inp: R5Inputs, mode: str, ctx: Ctx) -> List[Dict[str, Any]]:
    """Headline S1 + KILL + the three clauses, plus the sensitivity rows (strict / lenient unimodality, per seed) when ``ctx.reading`` is headline."""
    ev = ctx.ev
    try:
        M, lam = _s1_inputs(inp, mode, ctx)
    except Missing as e:
        return [ctx.row("S1", mode, NA, {}, f"{e}"), ctx.row("S1-KILL", mode, NA, {}, f"{e}")]
    grid = ctx.design["curve"]["n_grid"]
    rt = float(ev["unimodal"]["rel_tol_registered"])
    st = s1_stats(grid, M, lam, ev, rel_tol=rt)
    th = _s1_thrash(inp, mode, st["n_star"])
    tn = _thrash_note(th)
    ok = st["C0_unimodal"] and st["C1"] and st["C2"]
    edge = " argmax at a grid edge: C2 cannot hold (registered)." if st["argmax_at_grid_edge"] else ""
    rows = [ctx.row("S1", mode, PASS if ok else FAIL, {**st, "thrash": th},
                    f"C0={st['C0_unimodal']} C1={st['C1']} C2={st['C2']} (mu300/lambda={st['mu300_over_lambda']:.3f}, max/mu300="
                    f"{st['max_over_mu300']:.2f}, n*={st['n_star']}).{edge} {tn}"),
            ctx.row("S1-KILL", mode, KILL_T if st["KILL"] else KILL_F, {"KILL": st["KILL"], "mu300": st["mu300"], "mu_max": st["mu_max"],
                                                                       "mu300_over_max": st["mu300_over_max"], "thrash": th},
                    ("KILL_TRUE: mu(300) >= 0.8 max mu => metastability is a full-reservation artifact in this mode. " if st["KILL"] else
                     "KILL_FALSE: mu(300) < 0.8 max mu. ") + tn),
            ctx.row("S1-clause-C0-unimodal", mode, PASS if st["C0_unimodal"] else FAIL, {"max_deviation_over_tol": st["max_deviation_over_tol"]},
                    "", "clause"),
            ctx.row("S1-clause-C1-mu300", mode, PASS if st["C1"] else FAIL, {"mu300_over_lambda": st["mu300_over_lambda"]}, "", "clause"),
            ctx.row("S1-clause-C2-peak", mode, PASS if st["C2"] else FAIL, {"max_over_mu300": st["max_over_mu300"], "C2_numeric": st["C2_numeric"],
                                                                           "argmax_at_grid_edge": st["argmax_at_grid_edge"]}, "", "clause")]
    if ctx.reading != "headline":
        return [{**r, "reading": ctx.reading if r["reading"] == "headline" else r["reading"]} for r in rows]
    # ---- sensitivities named in the registration
    strict = s1_stats(grid, M, lam, ev, rel_tol=0.0, abs_tol=float(ev["unimodal"]["abs_tol_strict"]))
    lenient = s1_stats(grid, M, lam, ev, rel_tol=float(ev["unimodal"]["rel_tol_lenient"]))
    for pid, s in (("S1-strict-unimodal", strict), ("S1-lenient-unimodal", lenient)):
        rows.append(ctx.row(pid, mode, PASS if (s["C0_unimodal"] and s["C1"] and s["C2"]) else FAIL,
                            {"C0_unimodal": s["C0_unimodal"], "max_deviation_over_tol": s["max_deviation_over_tol"], "KILL": s["KILL"]},
                            "", "sensitivity"))
    seeds = ctx.design["curve"]["seeds"]
    per = []
    for j, sd in enumerate(seeds):
        sj = s1_stats(grid, M[:, [j]], lam, ev, rel_tol=rt)          # one seed: no SE term (k = 1), tolerance rt * lambda
        per.append({"seed": int(sd), "C0": sj["C0_unimodal"], "C1": sj["C1"], "C2": sj["C2"], "KILL": sj["KILL"],
                    "pass": bool(sj["C0_unimodal"] and sj["C1"] and sj["C2"]), "n_star": sj["n_star"]})
    npass = sum(p["pass"] for p in per)
    rows.append(ctx.row("S1-per-seed", mode, PASS if npass == len(per) else (FAIL if npass == 0 else MIXED),
                        {"per_seed": per, "n_pass": npass, "n_seeds": len(per), "n_kill": sum(p["KILL"] for p in per)},
                        f"{npass}/{len(per)} seeds pass all three clauses on their own curve (CRN-coupled, not independent)", "sensitivity"))
    return rows


def eval_s1_reference(inp: R5Inputs, mode: str, ctx: Ctx, ref_mode: str) -> List[Dict[str, Any]]:
    """S1-vs-reference: the same statistics for the reference mode on the same seeds, next to the registered mode (information)."""
    try:
        M, lam = _s1_inputs(inp, mode, ctx)
        Mr, lamr = _s1_inputs(inp, ref_mode, ctx)
    except Missing as e:
        return [ctx.row("S1-vs-reference", mode, NA, {}, str(e), "sensitivity")]
    grid = ctx.design["curve"]["n_grid"]
    rt = float(ctx.ev["unimodal"]["rel_tol_registered"])
    a, b = s1_stats(grid, M, lam, ctx.ev, rel_tol=rt), s1_stats(grid, Mr, lamr, ctx.ev, rel_tol=rt)
    keys = ("C0_unimodal", "C1", "C2", "KILL", "mu300_over_lambda", "max_over_mu300", "n_star", "mu_max_over_lambda")
    return [ctx.row("S1-vs-reference", mode, INFO, {mode: {k: a[k] for k in keys}, ref_mode: {k: b[k] for k in keys}},
                    f"the same statistics for {ref_mode} on the same seeds; the registration makes no prediction about it", "sensitivity")]


# ============================================================================================ S2
def _cells(df: pd.DataFrame, mode_col: str, mode: str, sel: Dict[str, Any], seeds: Sequence[int]) -> pd.DataFrame:
    g = df[df[mode_col] == mode]
    for k, v in sel.items():
        g = g[g[k] == v]
    if g.duplicated("seed").any():
        raise ValueError(f"duplicate seeds in {mode} {sel}")
    g = g.set_index("seed")
    missing = [int(s) for s in seeds if s not in g.index]
    if missing:
        raise Missing(f"{mode} {sel}: seeds {missing} missing")
    return g.loc[list(seeds)]


def _thrash_runs(g: pd.DataFrame) -> Dict[str, Any]:
    if "tail_thrash" not in g:
        return {}
    return {"n_flagged": int(g["tail_thrash"].astype(bool).sum()), "n_runs": int(len(g)),
            "max_tail_preemptions_per_turn": float(g["tail_preemptions_per_turn"].max()),
            "max_tail_preempt_per_turn_in_window": float(g["tail_preempt_max_turn"].max())}


def eval_s2(inp: R5Inputs, mode: str, ctx: Ctx) -> List[Dict[str, Any]]:
    b = ctx.design["burst"]
    sizes, seeds = b["sizes"], b["seeds"]
    big = max(sizes)
    if inp.burst is None:
        return [ctx.row("S2", mode, NA, {}, "no burst runs")]
    try:
        g0 = _cells(inp.burst, "alloc_mode", mode, {"burst_n": 0}, seeds)
        g1 = _cells(inp.burst, "alloc_mode", mode, {"burst_n": big}, seeds)
    except Missing as e:
        return [ctx.row("S2", mode, NA, {}, str(e))]
    nr1 = int((~g1["recovered"].astype(bool)).sum())
    nr0 = int((~g0["recovered"].astype(bool)).sum())
    need, mx0 = int(ctx.ev["S2"]["min_not_recovered_burst"]), int(ctx.ev["S2"]["max_not_recovered_nobust"])
    c_b, c_0 = nr1 >= need, nr0 <= mx0
    th = {f"burst={big}": _thrash_runs(g1), "burst=0": _thrash_runs(g0)}
    per = {"seeds": [int(s) for s in seeds],
           "burst_tail_hit": g1["tail_hit_rate"].tolist(), "burst_tail_backlog": g1["tail_backlog_mean"].tolist(),
           "burst_recovered": g1["recovered"].astype(bool).tolist(), "noburst_tail_hit": g0["tail_hit_rate"].tolist(),
           "noburst_tail_backlog": g0["tail_backlog_mean"].tolist(), "noburst_recovered": g0["recovered"].astype(bool).tolist()}
    note = (f"not recovered: burst {nr1}/{len(seeds)} (need >= {need}), no-burst {nr0}/{len(seeds)} (need <= {mx0}). "
            + ("the open system is unstable at 2 lambda_m without any perturbation (>= 2/5 no-burst runs not recovered). " if nr0 >= 2 else "")
            + _thrash_note(th))
    rows = [ctx.row("S2", mode, PASS if (c_b and c_0) else FAIL, {"n_not_recovered_burst": nr1, "n_not_recovered_noburst": nr0, **per, "thrash": th}, note),
            ctx.row("S2-clause-burst", mode, PASS if c_b else FAIL, {"n_not_recovered_burst": nr1}, "", "clause"),
            ctx.row("S2-clause-noburst", mode, PASS if c_0 else FAIL, {"n_not_recovered_noburst": nr0}, "", "clause")]
    if ctx.reading == "headline":
        nh1 = int((~(g1["tail_hit_rate"] > float(b["recovered_hit_above"]))).sum())
        nh0 = int((~(g0["tail_hit_rate"] > float(b["recovered_hit_above"]))).sum())
        rows.append(ctx.row("S2-hit-only", mode, PASS if (nh1 >= need and nh0 <= mx0) else FAIL,
                            {"n_not_recovered_hit_only_burst": nh1, "n_not_recovered_hit_only_noburst": nh0},
                            "'not recovered' by hit rate <= 0.8 alone (backlog ignored)", "sensitivity"))
    else:
        rows = [{**r, "reading": ctx.reading if r["reading"] == "headline" else r["reading"]} for r in rows]
    return rows


# ============================================================================================ S3
def eval_s3(inp: R5Inputs, mode: str, ctx: Ctx, n_star: Optional[int]) -> List[Dict[str, Any]]:
    c = ctx.design["cap"]
    seeds = c["seeds"]
    if inp.cap is None or n_star is None:
        return [ctx.row("S3", mode, NA, {}, "no cap runs or no curve (n*)")]
    try:
        gc = _cells(inp.cap, "alloc_mode", mode, {"arm": "capped_at_nstar"}, seeds)
        gn = _cells(inp.cap, "alloc_mode", mode, {"arm": "no_cap"}, seeds)
    except Missing as e:
        return [ctx.row("S3", mode, NA, {"n_star": n_star}, str(e))]
    if n_star >= int(ctx.ev["S3"]["max_nstar_exclusive"]):
        return [ctx.row("S3", mode, NA, {"n_star": n_star}, f"n* = {n_star} >= {ctx.ev['S3']['max_nstar_exclusive']}: no collapse to cap (registered)")]
    used = sorted(set(int(x) for x in gc["cap"]))
    if used != [int(n_star)]:
        return [ctx.row("S3", mode, NA, {"n_star": n_star, "cap_used": used}, "the cap used by the runs is not n* of the evaluated curve")]
    rc, rn = int(gc["recovered"].astype(bool).sum()), int(gn["recovered"].astype(bool).sum())
    need, mxn = int(ctx.ev["S3"]["min_recovered_capped"]), int(ctx.ev["S3"]["max_recovered_nocap"])
    c1, c2 = rc >= need, rn <= mxn
    th = {"capped": _thrash_runs(gc), "no_cap": _thrash_runs(gn)}
    nums = {"n_star": int(n_star), "n_recovered_capped": rc, "n_recovered_nocap": rn, "seeds": [int(s) for s in seeds],
            "capped_tail_hit": gc["tail_hit_rate"].tolist(), "capped_tail_backlog": gc["tail_backlog_mean"].tolist(),
            "capped_tail_gate": gc["tail_gate_mean"].tolist(), "nocap_tail_hit": gn["tail_hit_rate"].tolist(),
            "nocap_tail_backlog": gn["tail_backlog_mean"].tolist(), "thrash": th}
    rows = [ctx.row("S3", mode, PASS if (c1 and c2) else FAIL, nums,
                    f"cap = n* = {n_star}: capped recovers {rc}/{len(seeds)} (need >= {need}), no-cap recovers {rn}/{len(seeds)} (need <= {mxn}). "
                    + _thrash_note(th)),
            ctx.row("S3-clause-capped", mode, PASS if c1 else FAIL, {"n_recovered_capped": rc}, "", "clause"),
            ctx.row("S3-clause-nocap", mode, PASS if c2 else FAIL, {"n_recovered_nocap": rn}, "", "clause")]
    if ctx.reading != "headline":
        rows = [{**r, "reading": ctx.reading if r["reading"] == "headline" else r["reading"]} for r in rows]
    return rows


# ============================================================================================ S4
def eval_s4(inp: R5Inputs, mode: str, ctx: Ctx) -> List[Dict[str, Any]]:
    grid, seeds = ctx.design["curve"]["n_grid"], ctx.design["curve"]["seeds"]
    try:
        if inp.curve is None or inp.calib is None:
            raise Missing("curve or calibration runs absent")
        lam = lambda_miss_by_mode(inp.calib).get(mode)
        if lam is None:
            raise Missing(f"no calibration runs for {mode}")
        n300 = [300]                                            # S4 needs only the n = 300 cells of both policies
        f = curve_matrix(inp.curve, mode, FCFS, n300, seeds)[0]
        l = curve_matrix(inp.curve, mode, LPM, n300, seeds)[0]
    except Missing as e:
        return [ctx.row("S4", mode, NA, {}, str(e))]
    diff = l - f
    d = float(l.mean() - f.mean())
    thr = float(ctx.ev["S4"]["min_gap_over_lambda"])
    th = {"fcfs_lru n=300": curve_thrash(inp.curve, mode, FCFS, [300]).get(300, {}), "lpm_lru n=300": curve_thrash(inp.curve, mode, LPM, [300]).get(300, {})}
    nums = {"d_m": d, "d_m_over_lambda": d / lam, "d_m_over_mu300_fcfs": d / float(f.mean()), "threshold_over_lambda": thr,
            "mu300_lpm": float(l.mean()), "mu300_fcfs": float(f.mean()), "per_seed_diff": diff.tolist(), "per_seed_diff_over_lambda": (diff / lam).tolist(),
            "lambda_m": lam, "thrash": {k: v for k, v in th.items() if v}}
    rows = [ctx.row("S4", mode, PASS if d >= thr * lam else FAIL, nums,
                    f"d_m = {d:.5f} = {d / lam:.3f} lambda_m (threshold {thr}); this tests the allocation rule plus an IDEALISED LPM (no queue-length "
                    f"fallback; vLLM has no LPM policy, SGLang falls back to FCFS above 128 waiting requests); " + _thrash_note(th))]
    if ctx.reading == "headline":
        rows.append(ctx.row("S4-all-seeds", mode, PASS if bool(np.all(diff >= thr * lam)) else FAIL,
                            {"per_seed_diff_over_lambda": (diff / lam).tolist()}, "every paired per-seed difference >= 0.05 lambda_m", "sensitivity"))
    else:
        rows = [{**r, "reading": ctx.reading} for r in rows]
    return rows


def eval_s4_lpm128(inp_main: R5Inputs, inp_var: Optional[R5Inputs], mode: str, ctx: Ctx) -> List[Dict[str, Any]]:
    """Informational (finding F5): LPM that falls back to FCFS above 128 waiting requests at closed n = 300, against the registered FCFS-LRU."""
    if inp_var is None or inp_var.curve is None:
        return [ctx.row("S4-lpm128", mode, NA, {}, "no lpm128 variant curve", "information")]
    seeds = ctx.design["curve"]["seeds"]
    try:
        f = curve_matrix(inp_main.curve, mode, FCFS, [300], seeds)[0]
        l = curve_matrix(inp_var.curve, mode, "lpm128_lru", [300], seeds)[0]
        lam = lambda_miss_by_mode(inp_main.calib)[mode]
    except (Missing, KeyError, TypeError, AttributeError) as e:
        return [ctx.row("S4-lpm128", mode, NA, {}, str(e), "information")]
    d = float(l.mean() - f.mean())
    g = inp_var.curve[(inp_var.curve["mode"] == mode)]
    return [ctx.row("S4-lpm128", mode, INFO, {"d_m": d, "d_m_over_lambda": d / lam, "mu300_lpm128": float(l.mean()), "mu300_fcfs": float(f.mean()),
                                              "per_seed_diff_over_lambda": ((l - f) / lam).tolist(),
                                              "hit_rate_lpm128": float(g["hit_rate"].mean()) if "hit_rate" in g else float("nan")},
                    "LPM with SGLang's fall back to FCFS above 128 waiting requests, closed n = 300 (informational; not the registered S4)", "information")]


# ============================================================================================ answer + information
def eval_answer(rows: Sequence[Dict[str, Any]], mode: str, ctx: Ctx) -> Dict[str, Any]:
    """Registered answer template: 'persists' iff S1 PASS and KILL False; 'artifact' iff KILL True; otherwise 'mixed'."""
    by = {r["id"]: r for r in rows if r["mode"] == mode and r["reading"] == ctx.reading}
    s1, kill = by.get(ctx.pid("S1")), by.get(ctx.pid("S1-KILL"))
    if s1 is None or kill is None or s1["verdict"] == NA or kill["verdict"] == NA:
        return ctx.row("ANSWER", mode, NA, {}, "S1 not evaluable")
    if kill["verdict"] == KILL_T:
        ans = ARTIFACT
    elif s1["verdict"] == PASS:
        ans = PERSISTS
    else:
        ans = MIXED
    support = {k: by[ctx.pid(k)]["verdict"] for k in ("S2", "S3", "S4") if ctx.pid(k) in by}
    return ctx.row("ANSWER", mode, ans, {"S1": s1["verdict"], "KILL": kill["verdict"], "supporting": support},
                   f"S2-S4 as supporting evidence: {support}. SCOPE: this workload only (d = {ctx.decode_tokens} decode tokens per turn, so the end-of-turn "
                   "reservation excess is small); nothing here speaks to long-decode workloads. No verdict is aggregated across modes")


def reservation_excess_rows(inp: R5Inputs, modes: Sequence[str], ref_mode: str, M_tokens: float, ctx: Ctx) -> List[Dict[str, Any]]:
    """Information (finding F1): mean KV held by running requests in the new mode vs mean KV RESERVED by full_reserve at the same n (different
    trajectories: indicative only), FCFS-LRU, at n = 100 and 300 and at the mode's n*."""
    out = []
    if inp.curve is None:
        return out
    cr = inp.curve
    for m in modes:
        for pol in (FCFS,):
            sel_m = cr[(cr["mode"] == m) & (cr["policy"] == pol)].groupby("n_nominal")["reserved_tokens"].mean()
            sel_r = cr[(cr["mode"] == ref_mode) & (cr["policy"] == pol)].groupby("n_nominal")["reserved_tokens"].mean()
            ns = sorted(set(sel_m.index) & set(sel_r.index))
            tab = {int(n): {"held_new_mode": float(sel_m[n]), "reserved_full_reserve": float(sel_r[n]), "excess": float(sel_r[n] - sel_m[n]),
                            "excess_over_M": float((sel_r[n] - sel_m[n]) / M_tokens)} for n in ns}
            out.append(ctx.row("INFO-reservation-excess", m, INFO, {"policy": pol, "by_n": tab},
                               "mean tokens reserved by full_reserve minus mean tokens held by running requests in this mode (different trajectories, "
                               "indicative only); the registration's bound '<= 0.9 % of M' omitted the unprefilled remainder of in-progress prefills "
                               "(amendment 2)", "information"))
    return out


def stationarity_rows(inp: R5Inputs, modes: Sequence[str], ctx: Ctx) -> List[Dict[str, Any]]:
    out = []
    if inp.curve is None:
        return out
    for m in modes:
        g = inp.curve[(inp.curve["mode"] == m) & (inp.curve["policy"] == FCFS)].groupby("n_nominal")[["mu_first_half", "mu_second_half"]].mean()
        out.append(ctx.row("INFO-stationarity", m, INFO, {"by_n": {int(n): {"first_half": float(r["mu_first_half"]), "second_half": float(r["mu_second_half"])}
                                                                 for n, r in g.iterrows()}},
                           "mu over the two halves of the measurement window (FCFS-LRU, seed mean)", "information"))
    return out


def thrash_summary_rows(inp: R5Inputs, modes: Sequence[str], ctx: Ctx) -> List[Dict[str, Any]]:
    """Information: every cell that carries the thrash label, and the preemption / re-computation rates vs n."""
    out = []
    for m in modes:
        d: Dict[str, Any] = {}
        if inp.curve is not None and "thrash" in inp.curve:
            g = inp.curve[inp.curve["mode"] == m]
            d["curve_flagged"] = [{"policy": r["policy"], "n": int(r["n_nominal"]), "seed": int(r["seed"]), "preemptions_per_turn": float(r["preemptions_per_turn"]),
                                   "preempt_max_turn": float(r["preempt_max_turn"])} for _, r in g[g["thrash"].astype(bool)].iterrows()]
            d["curve_max_preemptions_per_turn"] = float(g["preemptions_per_turn"].max())
            d["curve_max_preempt_per_turn_in_window"] = float(g["preempt_max_turn"].max())
        for nm, df, key in (("burst", inp.burst, "alloc_mode"), ("cap", inp.cap, "alloc_mode")):
            if df is not None and "tail_thrash" in df:
                g = df[df[key] == m]
                d[f"{nm}_tail_flagged"] = int(g["tail_thrash"].astype(bool).sum())
                d[f"{nm}_runs"] = int(len(g))
                d[f"{nm}_max_tail_preemptions_per_turn"] = float(g["tail_preemptions_per_turn"].max())
                d[f"{nm}_max_run_preempt_per_turn"] = float(g["max_preempt_per_turn"].max())
        out.append(ctx.row("INFO-thrash", m, INFO, d, "registered label (amendment 2): preemptions per admitted turn > threshold OR max preemptions of one turn > threshold",
                           "information"))
    return out


# ============================================================================================ all
def nstar_of(inp: R5Inputs, mode: str, ctx: Ctx) -> Optional[int]:
    try:
        M = curve_matrix(inp.curve, mode, FCFS, ctx.design["curve"]["n_grid"], ctx.design["curve"]["seeds"])
    except (Missing, TypeError, AttributeError):
        return None
    return int(ctx.design["curve"]["n_grid"][int(np.argmax(M.mean(axis=1)))])


def evaluate_mode_set(inp: R5Inputs, modes: Sequence[str], ctx: Ctx) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for m in modes:
        r = []
        r += eval_s1(inp, m, ctx)
        r += eval_s2(inp, m, ctx)
        r += eval_s3(inp, m, ctx, nstar_of(inp, m, ctx))
        r += eval_s4(inp, m, ctx)
        rows += r
        rows.append(eval_answer(r, m, ctx))
    return rows


def order_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Registered (headline) readings first, then clauses, sensitivities, information."""
    rank = {"headline": 0, "clause": 1, "sensitivity": 2, "information": 3}
    return sorted(rows, key=lambda r: rank.get(r["reading"], 9))      # stable: keeps the mode / test order inside a reading


def evaluate_all(main: R5Inputs, design: Dict[str, Any], ev: Dict[str, Any], thr: Dict[str, float], *, claims: Optional[Dict[str, str]] = None,
                 variants: Optional[Dict[str, R5Inputs]] = None, ref_mode: str = "full_reserve", M_tokens: float = 300000.0,
                 modes: Optional[Sequence[str]] = None, decode_tokens: int = 100) -> List[Dict[str, Any]]:
    """Headline rows for each registered mode, the registered sensitivities, the sensitivity-VARIANT rows (suffix ``@variant``, reading
    ``sensitivity``) and the information rows."""
    cl = claims if claims is not None else registered_claims()
    modes = list(modes or design["modes"]["registered"])
    ctx = Ctx(design, ev, thr, cl, decode_tokens=decode_tokens)
    rows = evaluate_mode_set(main, modes, ctx)
    for m in modes:
        rows += eval_s1_reference(main, m, ctx, ref_mode)
    rows += lambda_miss_rows(main.calib, ev, ctx, modes + [ref_mode])
    rows += reservation_excess_rows(main, modes, ref_mode, M_tokens, ctx)
    rows += stationarity_rows(main, modes + [ref_mode], ctx)
    rows += thrash_summary_rows(main, modes, ctx)
    for name, vin in (variants or {}).items():
        if name == "lpm128":
            vctx = Ctx(design, ev, thr, cl, reading="information", suffix="", decode_tokens=decode_tokens)
            for m in modes:
                rows += eval_s4_lpm128(main, vin, m, vctx)
            continue
        vmodes = [m for m in modes if (vin.curve is not None and m in set(vin.curve["mode"])) or
                  (vin.burst is not None and m in set(vin.burst["alloc_mode"]))]
        vctx = Ctx(design, ev, thr, cl, reading="sensitivity", suffix=f"@{name}", decode_tokens=decode_tokens)
        rows += evaluate_mode_set(vin, vmodes, vctx)
        rows += lambda_miss_rows(vin.calib, ev, vctx, vmodes)
        rows += thrash_summary_rows(vin, vmodes, vctx)
    return order_rows(rows)


def suppress_verdicts(rows: Sequence[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
    """Every test verdict becomes NOT_EVALUABLE (numbers kept) because an input is unsafe (quick run, dirty tree, no / unfinished meta)."""
    out = []
    for r in rows:
        if r["verdict"] in TEST_VERDICTS:
            r = {**r, "verdict": NA, "notes": (r["notes"] + " " if r["notes"] else "") + f"VERDICT SUPPRESSED: {reason}"}
        out.append(r)
    return out


def rows_to_frame(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{**r, "numbers": json.dumps(r["numbers"], default=float)} for r in rows],
                        columns=["id", "mode", "reading", "verdict", "claim", "numbers", "notes"])
