"""Collect the frozen headline predictions from results/theory/merged/*.json into configs/r13_theory_predict.yaml.

    PYTHONPATH="src;." python -m analysis.theory.merged.freeze_table [--print]

Reads ONLY the prediction JSONs written by analysis.theory.predict and analysis.theory.merged.speed_table (no measured data).
"""
from __future__ import annotations

import argparse
import json
import os

import yaml

from .spec import ROOT

D = os.path.join(ROOT, "results", "theory", "merged")
CURVE_CELLS = ["h200_300k", "h200_300k_ratiofit", "h200_300k_lamratiofit", "h200_300k_decode2", "h200_300k_e0a2",
               "llama31_8b_300k", "a100_pool150k", "a100_pool600k"]
CMD = 'PYTHONPATH="src;." python -m analysis.theory.predict analysis/theory/cells/{}.yaml'


def r(x, k=4):
    return None if x is None else round(float(x), k)


def load(n):
    with open(os.path.join(D, f"{n}.json")) as f:
        return json.load(f)


def curve_cell(n):
    P = load(n)
    fl, an, am, w, fe = (P["closed_curve"]["fluid"], P["closed_curve"]["annealed"], P["all_miss"], P["window"],
                         P["from_empty_edge"])
    gp = {k: dict(mu_fluid=r(v["mu_fluid"]), mu_annealed=r(v["mu_annealed"]), hit_fluid=r(v["hit_fluid"], 3),
                  hit_annealed=r(v["hit_annealed"], 3)) for k, v in P["closed_curve"]["grid_points"].items()
          if float(k) < 300}
    sy = P["closed_curve"]["grid_points"].get("300.0", {}).get("stagec_synchronized", {})
    arms = {}
    for k, a in P["e2"]["arms"].items():
        if a.get("in_window"):
            arms[k] = dict(lam=r(a["lam"], 5), n1=r(a["n1"], 2), n_u=r(a["n_u"], 2),
                           burst_backlog=r(a["burst_trapped"]["backlog"], 1),
                           burst_token_ratio=r(a["burst_trapped"]["token_ratio_vs_model_e0a"], 3),
                           burst_gap_over_R=r(a["burst_trapped"]["gap_over_R"], 2),
                           noburst_hit=r(a["noburst_good_state"]["hit"], 3),
                           capped_drain_s=r(a["capped_static"]["drain_after_burst_s"], 0),
                           b_crit=r(a["critical_burst_fresh"].get("b_fresh"), 1))
    return dict(
        command=CMD.format(n), spec=f"analysis/theory/cells/{n}.yaml", fitted=P["fitted_parameters"],
        speed_factor=r(P["info"].get("speed_factor_fitted") or P["info"].get("compute_speed_factor_fitted"), 4),
        lambda_ref=r(fe["lambda_ref_used"], 6),
        e0a_model=dict(lambda_turns=r(am["e0a_pop32_lambda_turns"], 5), tokens=r(am["e0a_pop32_tokens"], 0),
                       pop64_over_pop32=r(am["pop64_over_pop32_tokens"], 4)),
        mu_max_fluid=r(fl["mu_max"]), mu_max_annealed_PRIMARY=r(an["mu_max"]), peak_n_fluid=r(fl["peak_n"], 1),
        peak_n_annealed_PRIMARY=r(an["peak_n"], 1), hit_at_peak_fluid=r(fl["hit_at_peak"], 3),
        n_half_fluid_PRIMARY=r(fl["n_half"], 1), n_half_annealed=r(an["n_half"], 1), n_b=r(fl["n_b"], 2),
        n_b_tool_call_part=r(am["threshold"]["tool_call_part"], 2), n_b_pool_part=r(am["threshold"]["pool_part"], 2),
        mu_b=r(am["lambda_miss_model_turns"], 5),
        window_fluid=r(w["vs_lambda_ref"], 3), window_annealed_PRIMARY=r(w["annealed_vs_lambda_ref"], 3),
        f2_edge_mult_PRIMARY=r(fe["edge_mult"], 3), f2_edge_lambda_sessions_per_s=r(fe["edge_lambda_sessions_per_s"], 5),
        f2_bracket=fe["predicted_bracket"], f2_p_unstable={k: r(v, 3) for k, v in fe["p_escape_registered"].items()},
        level_crossing_edge_mult=r(fe["secondary_level_crossing"]["edge50_mult"], 3),
        level_crossing_p_unstable={k: r(v, 3) for k, v in fe["secondary_level_crossing"]["p_unstable_registered"].items()},
        stagec_mu300_synchronized=r(sy.get("mu_turns_based"), 4),
        registration_consequence=P["registration_consequence"], e2_auto=arms, grid_points=gp,
        fold_margin=r(P.get("fold_identity", {}).get("max_ratio"), 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    out = dict(cells={n: curve_cell(n) for n in CURVE_CELLS})
    B = load("b1_basin_300k")["tests"]["B1"]
    out["B1"] = dict(command=CMD.format("b1_basin_300k"), multiple=1.65, stuck_by_s=r(B["stuck_by_s"], 0),
                     b_crit_deterministic=r(B["result"]["b_crit_deterministic"], 1),
                     rows={str(int(x["burst"])): dict(p_trapped=r(x["p_trapped"], 3), committor=r(x["committor"], 4),
                                                       X0=r(x["X0"], 2)) for x in B["result"]["rows"]})
    p100, p25 = out["B1"]["rows"]["100"]["p_trapped"], out["B1"]["rows"]["25"]["p_trapped"]
    pass100 = p100 ** 3 + 3 * p100 ** 2 * (1 - p100)
    good25 = (1 - p25) ** 3 + 3 * (1 - p25) ** 2 * p25
    out["B1"]["p_pass_registered_2of3"] = r(pass100 * good25, 3)
    # N_crit at 1.35 and 2.0 x from the 300k cell's E2 / critical-burst outputs
    # N_crit at 1.35, 1.65 and 2.0 x lambda_ref on the 300k cell: F3 deterministic critical burst plus the committor's 50% point
    from ..fluid_rigorous.model import critical_burst_fresh, summarize_curve
    from . import extras as X
    from .spec import build, load_spec
    import numpy as np
    m, _, _ = build(load_spec(os.path.join(ROOT, "analysis", "theory", "cells", "a100_300k.yaml")))
    cs = summarize_curve(m)
    lam_ref = 0.071534
    I_D = load("a100_300k")["from_empty_edge"]["I_D"]
    nc = {}
    for x in (1.35, 1.65, 2.0):
        lam = x * lam_ref
        det = critical_burst_fresh(m, cs, lam)
        sizes = list(np.arange(5.0, 121.0, 1.0))
        bt = X.burst_trap_probability(m, cs, lam, sizes, I_D, stuck_by_s=out["B1"]["stuck_by_s"])
        p50 = next((row["burst"] for row in bt["rows"] if row["committor"] >= 0.5), None)
        nc[str(x)] = dict(N_crit_deterministic=r(det.get("b_fresh"), 1), N_crit_committor_50pct=p50,
                          b_stat=r(det.get("b_stat"), 2))
    out["B1"]["N_crit_by_mult"] = nc
    for nm, key in (("r1_rescue_300k", "R1"), ("r4_rescue_native", "R4")):
        T = load(nm)["tests"][key]["result"]
        rows = {}
        for k, v in T.items():
            rows[k] = dict(in_window=v["in_window"], n1=r(v["n1"], 2), n_u=r(v["n_u"], 2), n_on=r(v.get("n_on"), 1),
                           t_release_fluid_PRIMARY=v["two_phase"].get("t_release"),
                           t_release_annealed=v["two_phase_annealed"].get("t_release"),
                           t_release_collapsed_resumed_mix=v["phase1_collapsed"].get("t_release"),
                           t_release_collapsed_stationary_mix=v["phase1_collapsed_stationary_mix"].get("t_release"),
                           released_by_7200_fluid=v["two_phase"].get("released_by_deadline"),
                           p_relapse=r(v["two_phase"].get("p_relapse"), 3),
                           mu_phase1_fluid=r(v["mu_phase1_fluid"], 4),
                           mu_phase1_needed=r(v["mu_phase1_needed_for_deadline"], 4),
                           needed_over_fluid=r(v["mu_phase1_needed_over_fluid"], 3))
        out[key] = dict(command=CMD.format(nm), rows=rows)
    S = json.load(open(os.path.join(D, "llama31_8b_300k_speed_table.json")))
    out["llama_speed_table"] = dict(command='PYTHONPATH="src;." python -m analysis.theory.merged.speed_table '
                                            'analysis/theory/cells/llama31_8b_300k.yaml', rule=S["rule"],
                                    rows=[{k: r(v, 5) for k, v in row.items()} for row in S["rows"]])
    path = os.path.join(ROOT, "results", "theory", "merged", "freeze_table.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False, width=140)
    if a.print:
        print(yaml.safe_dump(out, sort_keys=False, width=140))


if __name__ == "__main__":
    main()
