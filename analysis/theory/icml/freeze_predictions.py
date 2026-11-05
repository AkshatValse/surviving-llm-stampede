r"""Freeze Theorem 1/2 predictions for trapped runs that do not exist yet (conditional on a run being trapped).

    PYTHONPATH="src;." python -m analysis.theory.icml.freeze_predictions [--reps 200]

Writes configs/icml_trap_predict.yaml and results/theory/icml/frozen_predictions.json.  Nothing here reads any run result;
inputs are the frozen cell specs (analysis/theory/cells/) and the protocol constants below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from typing import Dict, List

import numpy as np
import yaml

from ..merged.spec import ROOT
from ..fluid_rigorous.model import open_equilibria, summarize_curve
from .run_check import cell_model
from .trap_renewal import fifo_fluid, stochastic_fifo, trap_asymptotics, trap_costs, window_stats

CELLS = {  # cell -> lambda_ref (sessions/s) used for the multiples, and its source
    "a100_300k": (0.071534, "A100 300k E0a lambda_miss_turns_based"),
    "a100_native": (0.0717974, "A100 native E0a lambda_miss_turns_based"),
    "vllm_300k": (0.065663, "vLLM E0a lambda_miss_turns_based"),
    "llama31_fit": (0.0596408614267974, "Llama-3.1-8B E0a lambda_miss_turns_based (speed fitted to its E0a token rate)"),
    "h200_300k": (0.19388, "H200 300k E0a lambda_miss_turns_based"),
    "h200_600k": (0.19388, "H200 300k E0a lambda_miss_turns_based (the 600k E2 runs use it)"),
    "a100_pool150k": (0.071534, "A100 300k E0a (the pool sweep's reference)"),
    "a100_pool600k": (0.071534, "A100 300k E0a (the pool sweep's reference)"),
}
MULTS = [1.1, 1.2, 1.25, 1.35, 1.5, 1.65, 1.75, 2.0, 2.25, 2.5, 2.7, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5]
E2_POINTS = {"a100_300k": [1.35, 1.65, 2.0, 2.5, 2.7], "a100_native": [2.5, 4.0], "vllm_300k": [1.35, 1.65, 2.0],
             "llama31_fit": [1.35, 1.65, 2.0], "h200_300k": [1.1, 1.2, 1.35], "h200_600k": [1.5, 2.0],
             "a100_pool150k": [1.2, 1.35], "a100_pool600k": [2.0, 3.0, 4.0]}

ROUND = lambda x, n=5: float(np.round(x, n))


def plan_window_rate(seed: int, rate: float, t0: float, t1: float, duration: float = 8700.0) -> float:
    """Base arrivals per second in [t0, t1) of the client's constant-rate plan for `seed` (agentload.workload.build_open_plan:
    poisson_times on stream S_ARRIVALS); a protocol quantity, fixed before any run."""
    from agentload.workload import S_ARRIVALS, make_rng, poisson_times
    base = poisson_times(make_rng(seed, S_ARRIVALS), rate, 0.0, duration)
    return float(((base >= t0) & (base < t1)).sum() / (t1 - t0))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    args = ap.parse_args(argv)
    rng = np.random.default_rng(20261105)
    out: Dict[str, object] = dict(
        tag="icml-trap-pred", theory="notes/THEORY_ICML_2026-11.md (Theorem 1, Theorem 2)",
        what=("Conditional predictions for any run that is in the all-miss request-level-FCFS trap (follow-up hit < 0.2) over "
              "its evaluation window: the turn mix and mean prompt of the turns served, the cycle growth (trend of the gap "
              "between a session's consecutive turns), the session completion rate and the backlog slope. Inputs: the frozen "
              "cell specs only; no run result is read."),
        cells={})
    for cell, (lam_ref, src) in CELLS.items():
        m, info = cell_model(cell)
        tc = trap_costs(m)
        cs = summarize_curve(m)
        rows: List[Dict[str, float]] = []
        for mult in MULTS:
            lam = mult * lam_ref
            if lam <= tc.lam_miss * 1.0001:
                continue
            a = trap_asymptotics(lam, tc)
            rows.append(dict(mult=mult, lam=ROUND(lam, 6), rho=ROUND(a["rho"], 4), z=ROUND(a["z"], 6), gamma=ROUND(a["gamma"], 6),
                             alpha=ROUND(a["alpha"], 6), alpha_over_excess_model=ROUND(a["alpha_over_excess"], 4),
                             D_over_lam_ref=ROUND(a["D"] / lam_ref, 4), P_served_mean=ROUND(a["P_served_mean"], 1),
                             P_served_ratio=ROUND(a["P_served_ratio"], 4), k_served_mean=ROUND(a["k_served_mean"], 3),
                             tok_ratio_composition=ROUND(a["tok_ratio"], 4), premium=ROUND(a["premium"], 4),
                             H_T=ROUND(a["H_T"], 4), C_c=ROUND(a["C_c"], 4)))
        e2 = []
        for mult in E2_POINTS[cell]:
            lam = mult * lam_ref
            if lam <= tc.lam_miss:
                continue
            try:
                n1 = open_equilibria(cs, lam).n1
            except Exception:
                n1 = float("nan")
            n1 = n1 if (n1 == n1 and n1 > 0) else 0.0
            tr = fifo_fluid(lam, tc, n1)
            fw = window_stats(tr, 5700.0, 8700.0, tc)
            sl = np.array([stochastic_fifo(lam, tc, n1, rng)["slope"] for _ in range(args.reps)])
            thr = 0.5 * (lam - lam_ref)
            a_pt = trap_asymptotics(lam, tc)
            per_seed = []
            for seed in range(6):
                lw = plan_window_rate(seed, lam, 5700.0, 8700.0)
                per_seed.append(dict(seed=seed, lam_window_plan=ROUND(lw, 5), slope_plugin=ROUND(lw - a_pt["D"], 5),
                                     plugin_above_threshold=bool(lw - a_pt["D"] > 0.5 * (lam - lam_ref))))
            e2.append(dict(mult=mult, n1=ROUND(n1, 2), per_seed_plan=per_seed, fluid_slope=ROUND(fw["slope"], 5), fluid_completion_over_lam_ref=ROUND(
                fw["completion_rate"] / lam_ref, 4), fluid_P_served=ROUND(fw["P_served_mean"], 1), fluid_V_slope=ROUND(fw["V_slope"], 5),
                fluid_N_mean=ROUND(fw["N_mean"], 1), stoch_slope_mean=ROUND(sl.mean(), 5), stoch_slope_sd=ROUND(sl.std(ddof=1), 5),
                registered_threshold=ROUND(thr, 5), p_slope_above_threshold=ROUND((sl > thr).mean(), 3),
                p_two_of_three=ROUND(float(sum(__import__("math").comb(3, j) * (sl > thr).mean() ** j * (1 - (sl > thr).mean()) ** (3 - j)
                                               for j in (2, 3))), 3)))
        out["cells"][cell] = dict(lambda_ref=lam_ref, lambda_ref_source=src, lambda_miss_model=ROUND(tc.lam_miss, 6),
                                  near_threshold_coef=ROUND(trap_asymptotics(tc.lam_miss * 1.001, tc)["near_threshold_coef"], 4),
                                  speed_fit=info.get("speed_factor_fitted"), asymptotic=rows,
                                  e2_protocol=dict(burst="200 sessions uniform in [1200, 1260) s", window="[5700, 8700) s",
                                                   reps=args.reps, points=e2))
    out["scoring"] = dict(
        applies_to=("every run of a new experiment whose follow-up hit fraction over its evaluation window is below 0.2 and whose "
                    "window starts at least 3000 s after the trigger began (burst, tool slowdown, long-prompt batch, a "
                    "spontaneous from-empty collapse, a running-request cap, ...), on a cell listed here, at the run's nominal "
                    "multiple of the cell's lambda_ref (nearest grid row, or linear interpolation in mult)"),
        S1_composition="mean prompt of the turns completed in the window within +-8% of P_served_mean (per run); the pooled "
                       "mean within +-5%",
        S2_cycle_growth=("OLS slope of the 300 s medians of the gap (turn completion minus the same session's previous turn "
                         "completion) against time, pooled over the runs of a (cell, multiple): within [0.6, 1.4] x gamma"),
        S3_youth_premium=("session completion rate in the window above lambda_ref in every trapped run whose realized arrival "
                          "rate over the window is at least 1.1 lambda_ref; pooled mean within +-15% of D_over_lam_ref x lambda_ref"),
        S4_backlog=("pooled mean OLS slope of the 10 s bin means of sessions in the system within +-35% of alpha (asymptotic) or "
                    "of fluid_slope (E2 protocol); individual runs scatter with sd about stoch_slope_sd"),
        S5_per_seed=("for a run whose arrival plan is the client's constant-rate plan (seed known), the per-run slope is "
                     "predicted by slope_plugin = lam_window_plan - D (the realized base-arrival rate of the plan over the "
                     "window minus Theorem 1's trapped completion rate); scored by the sign of slope - 0.5 (lam - lam_ref) "
                     "(the registered trap-slope criterion) and by |slope - slope_plugin| <= 0.01 /s"),
        refutation=("Theorem 1's application to the engine is refuted for a (cell, multiple) if S1 fails for the pooled mean "
                    "or S2 fails, in a group of at least two trapped runs"),
        note=("tolerances were set after seeing the committed runs (results/theory/icml/trap_check.md), so they are calibrated "
              "on existing data; the predictions they score are for runs that did not exist when this file was pushed"))
    path_yaml = os.path.join(ROOT, "configs", "icml_trap_predict.yaml")
    with open(path_yaml, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False, width=140)
    os.makedirs(os.path.join(ROOT, "results", "theory", "icml"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "theory", "icml", "frozen_predictions.json"), "w") as f:
        json.dump(out, f, indent=1)
    code = {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in (
        "analysis/theory/icml/trap_renewal.py", "analysis/theory/icml/freeze_predictions.py", "analysis/theory/icml/run_check.py")}
    print(json.dumps(dict(written=[path_yaml], code_sha256=code), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
