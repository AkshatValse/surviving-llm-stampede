"""r15 TOOLSLOW cells T1 and T2: the frozen pred2 TOOLSLOW layer at new (mult, delta, window), unchanged.

    PYTHONPATH="src;." python -m analysis.r15_pred2_toolslow [--out results/theory/r15/toolslow_pred2.json]

Cells (A100 300k cell a100_300k, NOBURST arrivals, 8700 s, W = [5700, 8700) s; every tool call that STARTS in
[t_on, t_off) lasts Z + delta, Z ~ Exp(5 s)):
    T1  1.35 x lambda_ref, delta = 30 s, [1200, 3000)      PREDICTION (no run exists)
    T2  1.65 x lambda_ref, delta = 15 s, [1200, 2100)      PREDICTION (no run exists)
    d10 / d30  1.35 x, delta = 10 / 30 s, [1200, 2100)    REPRODUCTION of the committed r13 rows
                (results/theory/pred2/toolslow.json, tag r13-theory-pred2 = cfa7712): a check that this driver's
                parameter path gives the frozen numbers. Those rows were blind in r13 and have been scored on the GPU
                (jobs 17169902-07: d10 GOOD / GOOD / GOOD, d30 GOOD / GOOD / STUCK).

Frozen code, called unchanged (analysis/theory/pred2/toolslow.py; analysis/theory is unchanged since tag r13-theory-pred2
except analysis/theory/paper/figs.py, and the model since r13-theory-pred = 997d2c4): Curve, slowed_model, fluid_verdict,
plan_population, stochastic; common.cell, common.client_plan, common.eval_times, common.provenance. The module hard-codes
CELL = "a100_300k", MULT = 1.35 (line 40), T_ON, T_OFF = 1200, 2100 and WIN = (5700, 8700).
  * MULT is read only by toolslow.run(), which this driver never calls: lambda = mult x lambda_ref (the cell's spec
    lambda_ref, as run() does) and the exact plans at mult are built here and passed as arguments.
  * T_ON / T_OFF are read at call time by fluid_verdict (T_ON; t_off is its argument, passed explicitly), plan_population
    and stochastic (both). For each cell the driver sets the two module constants to the cell's window inside a context
    manager (``window``) and restores them afterwards; nothing on disk is edited. WIN is unchanged.
The per-cell block mirrors toolslow.run()'s per-delta block line for line: fluid verdict (STUCK iff n(t_off) > n_u(lambda)
of the normal curve), the band with the switch at t_off + delta, the exchangeable stochastic layer at X0 = n(t_off) and
its band (escape target n_u), the per-seed layer at X0 = the exact plan's sessions alive at t_off (plan walk with the
slowed curve's good-state service per turn, or the normal curve's when no slowed good state exists), and the exponential
law of the same mean as a sensitivity. Added here (new, outside the frozen block): the plan-walk alive counts at 2100 s
and 3000 s (the exploratory measure), the critical delta of the cell's (mult, window) by bisection of the frozen
fluid_verdict, and the per-seed call: STUCK if P(STUCK) > 0.5, GOOD if P(GOOD) > 0.5, otherwise NEITHER.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "src", REPO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from analysis.theory.pred2 import common as P          # noqa: E402
from analysis.theory.pred2 import toolslow as T        # noqa: E402
from analysis.theory.predict import clean              # noqa: E402

DEFAULT_OUT = "results/theory/r15/toolslow_pred2.json"
SUBSET_OUT = "results/theory/r15/toolslow_pred2_subset.json"
FROZEN_PRED2_TAG = "r13-theory-pred2"
FROZEN_PRED2_COMMIT = "cfa77127dbcbea285d5f44b6c7195d02019bf831"
COMMITTED_R14 = "results/theory/pred2/toolslow.json"
SEEDS = (0, 1, 2)
ALIVE_PROBES = (2100.0, 3000.0)

CELLS: Dict[str, Dict[str, Any]] = {
    "T1": {"mult": 1.35, "delta": 30.0, "t_on": 1200.0, "t_off": 3000.0, "role": "prediction"},
    "T2": {"mult": 1.65, "delta": 15.0, "t_on": 1200.0, "t_off": 2100.0, "role": "prediction"},
    "d10": {"mult": 1.35, "delta": 10.0, "t_on": 1200.0, "t_off": 2100.0, "role": "reproduction of the committed r13 row",
            "gpu": ["GOOD", "GOOD", "GOOD"]},
    "d30": {"mult": 1.35, "delta": 30.0, "t_on": 1200.0, "t_off": 2100.0, "role": "reproduction of the committed r13 row",
            "gpu": ["GOOD", "GOOD", "STUCK"]},
}


@contextlib.contextmanager
def window(t_on: float, t_off: float) -> Iterator[None]:
    """Set the frozen module's slowdown window constants for one cell; always restored."""
    old = (T.T_ON, T.T_OFF)
    T.T_ON, T.T_OFF = float(t_on), float(t_off)
    try:
        yield
    finally:
        T.T_ON, T.T_OFF = old


def seed_call(st: Dict[str, float]) -> str:
    return "STUCK" if st["p_stuck"] > 0.5 else "GOOD" if st["p_good"] > 0.5 else "NEITHER"


def _bisect(f, lo: float, hi: float, it: int = 24) -> Optional[float]:
    flo, fhi = f(lo), f(hi)
    if (flo > 0) == (fhi > 0):
        return None
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cell_block(name: str, spec: Dict[str, Any], plans_cache: Dict[Any, Any]) -> Dict[str, Any]:
    c = P.cell(T.CELL)
    mult, d, t_on, t_off = float(spec["mult"]), float(spec["delta"]), float(spec["t_on"]), float(spec["t_off"])
    lam = mult * c.lam_ref
    with window(t_on, t_off):
        base = T.Curve(c.m, lam)
        stuck_by, good_from = P.eval_times(base.good["hit"], *T.WIN)
        cv = T.Curve(T.slowed_model(c.m, d), lam)
        fv = T.fluid_verdict(base, cv, lam, t_off)
        fv_late = T.fluid_verdict(base, cv, lam, t_off + d)
        st = T.stochastic(base, cv, lam, fv["n_at_off"], stuck_by, good_from)
        st_band = T.stochastic(base, cv, lam, fv["n_at_off"], stuck_by, good_from, slow_target="n_u_normal")
        S_q = cv.good.get("S_bar") if cv.good.get("exists") else base.good["S_bar"]
        seeds: Dict[str, Any] = {}
        for sd in SEEDS:
            key = (mult, sd)
            if key not in plans_cache:
                plans_cache[key] = P.client_plan(P.E2_CONFIG, sd, mult, T.WIN[1], 0)[0]
            plan = plans_cache[key]
            pp = T.plan_population(plan, d, float(S_q), t_off)
            sst = T.stochastic(base, cv, lam, float(pp["alive_at_probe"]), stuck_by, good_from)
            alive = {f"alive_at_{int(a)}": int(T.plan_population(plan, d, float(S_q), a)["alive_at_probe"]) for a in ALIVE_PROBES}
            seeds[str(sd)] = dict(plan_population=pp, stochastic=sst, call=seed_call(sst), plan_walk_alive=alive,
                                  n_sessions=len(plan))
        exp_cv = T.Curve(T.slowed_model(c.m, d, "exp_same_mean"), lam)
        sens = T.fluid_verdict(base, exp_cv, lam, t_off)

        # critical delta of this (mult, window): n(t_off) = n_u, and the slowed curve's peak = lambda (new, outside run())
        def n_off(x: float) -> float:
            return T.fluid_verdict(base, T.Curve(T.slowed_model(c.m, x), lam), lam, t_off)["n_at_off"] - base.eq.n_u

        def mu_gap(x: float) -> float:
            return T.Curve(T.slowed_model(c.m, x), lam).cs.mu_max - lam

        d_star = _bisect(n_off, 0.5, 60.0)
        d_mu = _bisect(mu_gap, 0.0, 60.0)
    margin = fv["n_at_off"] - base.eq.n_u
    calls = [seeds[str(s)]["call"] for s in SEEDS]
    ps = [seeds[str(s)]["stochastic"]["p_stuck"] for s in SEEDS]
    pg = [seeds[str(s)]["stochastic"]["p_good"] for s in SEEDS]
    p_traps, p_notrap = P.at_least(ps, 2), P.at_least(pg, 2)          # independent seeds (frozen helper)
    return dict(
        cell=name, role=spec["role"], frozen_cell=T.CELL, mult=mult, lam=lam, lam_ref_spec=c.lam_ref, delta_s=d,
        window_s=[t_on, t_off], eval_window_s=list(T.WIN), stuck_by_s=stuck_by, good_from_s=good_from,
        normal_curve=dict(n1=base.eq.n1, n_u=base.eq.n_u, n_b=base.cs.n_b, mu_max=base.cs.mu_max, hit_n1=base.good.get("hit")),
        slowed_curve=dict(mu_max=cv.cs.mu_max, good_state_exists=bool(cv.eq.n1 == cv.eq.n1), n1=cv.eq.n1, n_u=cv.eq.n_u,
                          n_b=cv.cs.n_b, I_D=cv.I_D, good_state=cv.good),
        fluid=dict(n_at_on=fv["n_at_on"], n_at_slowdown_end=fv["n_at_off"], n_u_normal=fv["n_u_normal"],
                   margin_n_minus_n_u=margin, n_max_slowdown=fv["n_max_slowdown"], n_at_8700=fv["n_at_end"],
                   verdict=fv["verdict"], trace_t=fv["trace_t"], trace_n=fv["trace_n"]),
        fluid_switch_at_t_off_plus_delta=dict(n_at_off=fv_late["n_at_off"], verdict=fv_late["verdict"]),
        sensitivity_exp_same_mean=dict(n_at_off=sens["n_at_off"], verdict=sens["verdict"]),
        stochastic=st, stochastic_band_target_n_u=st_band, service_per_turn_plan_walk=float(S_q),
        per_seed=seeds, per_seed_calls=calls,
        cell_call=dict(fluid=fv["verdict"], fluid_tri_state="TRAPS" if fv["verdict"] == "STUCK" else "NO-TRAP",
                       per_seed_layer_modal_calls="TRAPS" if sum(x == "STUCK" for x in calls) >= 2
                       else "NO-TRAP" if sum(x == "GOOD" for x in calls) >= 2 else "MIXED",
                       per_seed_layer_p_traps=p_traps, per_seed_layer_p_notrap=p_notrap,
                       per_seed_layer_p_mixed=max(0.0, 1.0 - p_traps - p_notrap)),
        critical_delta=dict(delta_star_fluid=d_star, delta_mu_max_equals_lambda=d_mu,
                            note="bisection of the frozen fluid_verdict at this (mult, window); new, not in the frozen run()"),
        gpu_known=spec.get("gpu"))


def reproduction_check(blocks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The d10 / d30 blocks against the committed r13 rows (results/theory/pred2/toolslow.json)."""
    ref = json.loads((REPO / COMMITTED_R14).read_text())
    out: Dict[str, Any] = {"source": COMMITTED_R14, "source_sha256": hashlib.sha256((REPO / COMMITTED_R14).read_bytes()).hexdigest()}
    worst = 0.0
    for name, key in (("d10", "10"), ("d30", "30")):
        a, r = blocks[name], ref["deltas"][key]
        pairs = [("n_at_off", a["fluid"]["n_at_slowdown_end"], r["fluid"]["n_at_off"]),
                 ("n_at_end", a["fluid"]["n_at_8700"], r["fluid"]["n_at_end"]),
                 ("p_stuck", a["stochastic"]["p_stuck"], r["stochastic"]["p_stuck"]),
                 ("p_good", a["stochastic"]["p_good"], r["stochastic"]["p_good"]),
                 ("band_p_stuck", a["stochastic_band_target_n_u"]["p_stuck"], r["stochastic_band_target_n_u"]["p_stuck"])]
        for s in SEEDS:
            ps, rs = a["per_seed"][str(s)], r["per_seed"][str(s)]
            pairs += [(f"seed{s}_alive", ps["plan_population"]["alive_at_probe"], rs["plan_population"]["alive_at_probe"]),
                      (f"seed{s}_lengthened", ps["plan_population"]["lengthened_tool_calls"], rs["plan_population"]["lengthened_tool_calls"]),
                      (f"seed{s}_p_stuck", ps["stochastic"]["p_stuck"], rs["stochastic"]["p_stuck"])]
        diffs = {k: abs(float(x) - float(y)) for k, x, y in pairs}
        same_verdict = a["fluid"]["verdict"] == r["fluid"]["verdict"]
        worst = max([worst] + list(diffs.values()))
        out[name] = dict(max_abs_diff=max(diffs.values()), diffs=diffs, verdict=a["fluid"]["verdict"],
                         committed_verdict=r["fluid"]["verdict"], same_verdict=same_verdict)
    out["max_abs_diff_all"] = worst
    out["reproduced"] = bool(worst <= 1e-9 and out["d10"]["same_verdict"] and out["d30"]["same_verdict"])
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help=f"default {DEFAULT_OUT} ({SUBSET_OUT} when --cells names a subset)")
    ap.add_argument("--cells", nargs="*", default=None, choices=list(CELLS))
    args = ap.parse_args(argv)
    subset = bool(args.cells) and set(args.cells) != set(CELLS)
    args.out = args.out or (SUBSET_OUT if subset else DEFAULT_OUT)          # a subset run never overwrites the frozen file
    t0 = time.time()
    os.chdir(REPO)
    cells = list(args.cells or CELLS)
    cache: Dict[Any, Any] = {}
    blocks = {name: cell_block(name, CELLS[name], cache) for name in cells}
    if (T.T_ON, T.T_OFF, T.MULT) != (1200.0, 2100.0, 1.35):
        raise AssertionError("frozen module constants not restored")
    obj: Dict[str, Any] = {
        "experiment": "r15_pred2_toolslow",
        "status": ("FROZEN blind pred2 calls for T1 and T2 (no GPU run of these cells existed); d10 / d30 reproduce the "
                   "committed r13 rows (blind in r13, scored on the GPU since)"),
        "frozen_code": dict(module="analysis/theory/pred2/toolslow.py", pred2_tag=FROZEN_PRED2_TAG, pred2_commit=FROZEN_PRED2_COMMIT,
                            model_tag=P.FROZEN_TAG, model_commit=P.FROZEN_COMMIT,
                            parametrization="lambda and plans built here at mult (module MULT never read); T_ON / T_OFF set per "
                                            "cell by a context manager and restored; t_off passed to fluid_verdict explicitly"),
        "call_rule": dict(fluid="STUCK iff n(t_off) > n_u(lambda) of the normal curve (frozen fluid_verdict)",
                          per_seed="STUCK if P(STUCK) > 0.5, GOOD if P(GOOD) > 0.5, else NEITHER (frozen stochastic layer at "
                                   "X0 = the plan walk's sessions alive at t_off)",
                          cell="TRAPS (STUCK >= 2 of 3) | NO-TRAP (GOOD >= 2 of 3) | MIXED; reported three ways: the fluid "
                               "verdict applied to every seed, the per-seed modal calls, and P(TRAPS) / P(NO-TRAP) of the per-seed "
                               "layer with independent seeds (common.at_least)"),
        "cells": blocks,
        "summary": {n: dict(mult=b["mult"], delta_s=b["delta_s"], window_s=b["window_s"],
                            n_at_slowdown_end=b["fluid"]["n_at_slowdown_end"], n_u=b["normal_curve"]["n_u"],
                            margin=b["fluid"]["margin_n_minus_n_u"], fluid_call=b["fluid"]["verdict"],
                            switch_band_call=b["fluid_switch_at_t_off_plus_delta"]["verdict"],
                            exp_same_mean_call=b["sensitivity_exp_same_mean"]["verdict"],
                            p_stuck_exchangeable=b["stochastic"]["p_stuck"],
                            per_seed_X0=[b["per_seed"][str(s)]["plan_population"]["alive_at_probe"] for s in SEEDS],
                            per_seed_p_stuck=[b["per_seed"][str(s)]["stochastic"]["p_stuck"] for s in SEEDS],
                            per_seed_p_good=[b["per_seed"][str(s)]["stochastic"]["p_good"] for s in SEEDS],
                            per_seed_calls=b["per_seed_calls"],
                            cell_call_fluid=b["cell_call"]["fluid_tri_state"],
                            cell_call_per_seed_modal=b["cell_call"]["per_seed_layer_modal_calls"],
                            p_traps_per_seed_layer=b["cell_call"]["per_seed_layer_p_traps"],
                            p_notrap_per_seed_layer=b["cell_call"]["per_seed_layer_p_notrap"],
                            slowed_good_state_exists=b["slowed_curve"]["good_state_exists"],
                            plan_walk_alive_2100=[b["per_seed"][str(s)]["plan_walk_alive"]["alive_at_2100"] for s in SEEDS],
                            plan_walk_alive_3000=[b["per_seed"][str(s)]["plan_walk_alive"]["alive_at_3000"] for s in SEEDS],
                            delta_star_fluid=b["critical_delta"]["delta_star_fluid"], role=b["role"])
                    for n, b in blocks.items()},
    }
    if "d10" in blocks and "d30" in blocks:
        obj["r13_reproduction"] = reproduction_check(blocks)
    prov = P.provenance(extra_inputs=["analysis/r15_pred2_toolslow.py", P.E2_CONFIG, COMMITTED_R14])
    prov.update(argv=sys.argv, wall_s=time.time() - t0)
    obj["provenance"] = prov
    out = (REPO / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clean(obj), indent=1) + "\n", encoding="utf-8", newline="\n")
    for n, s in obj["summary"].items():
        print(f"{n:4s} {s['mult']}x delta {s['delta_s']:g} [{s['window_s'][0]:g}, {s['window_s'][1]:g}): n(t_off) "
              f"{s['n_at_slowdown_end']:.1f} vs n_u {s['n_u']:.1f} -> {s['fluid_call']} (switch band {s['switch_band_call']}, "
              f"exp law {s['exp_same_mean_call']}); P(STUCK) {s['p_stuck_exchangeable']:.3f}; per seed X0 {s['per_seed_X0']} "
              f"P(STUCK) {[round(x, 3) for x in s['per_seed_p_stuck']]} calls {s['per_seed_calls']} -> P(TRAPS) "
              f"{s['p_traps_per_seed_layer']:.3f} P(NO-TRAP) {s['p_notrap_per_seed_layer']:.3f}; delta* {s['delta_star_fluid']:.2f}")
    if "r13_reproduction" in obj:
        r = obj["r13_reproduction"]
        print(f"r13 reproduction: max |diff| {r['max_abs_diff_all']:.3g}, reproduced={r['reproduced']}")
    print("wrote", out.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
