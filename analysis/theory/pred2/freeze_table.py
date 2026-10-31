"""Collect the pred2 predictions from results/theory/pred2/*.json into configs/r13_theory_pred2.yaml.

    PYTHONPATH="src;." python -m analysis.theory.pred2.freeze_table

Reads ONLY the JSONs written by the pred2 drivers (no measured data beyond what those JSONs already carry).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import yaml

from .common import FROZEN_COMMIT, FROZEN_TAG, OUT_DIR, ROOT

CFG = os.path.join(ROOT, "configs", "r13_theory_pred2.yaml")
CMD = 'PYTHONPATH="src;." python -m analysis.theory.pred2.{}'


def r(x, k=4):
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    try:
        return round(float(x), k)
    except (TypeError, ValueError):
        return x


def load(n: str) -> Dict[str, Any]:
    with open(os.path.join(OUT_DIR, f"{n}.json")) as f:
        return json.load(f)


def b2_block() -> Dict[str, Any]:
    B = load("b2_basin")
    ex = {str(int(x["burst"])): dict(p_stuck=r(x["p_stuck"], 3), p_good=r(x["p_good"], 3), committor=r(x["committor"], 4),
                                     X0=r(x["X0"], 2)) for x in B["exchangeable"]["rows"]}
    ex["0"]["note"] = "frozen function's b = 0 row (post-burst horizon); the NOBURST protocol row is noburst_protocol"
    comp = {tag: dict(b_p_stuck_50=r(v["b_p_stuck_50"], 1), p_rule_three_random_seeds=r(v.get("p_rule_three_random_seeds"), 3),
                      rows={k: dict(p_stuck=r(x["p_stuck"], 3), p_good=r(x["p_good"], 3), b_eff_mean=r(x["b_eff_mean"], 1),
                                    b_eff_sd=r(x["b_eff_sd"], 1)) for k, x in v["rows"].items()})
            for tag, v in B["composition_averaged"].items() if isinstance(v, dict) and "rows" in v}
    per = {}
    for sd, recs in B["per_seed"].items():
        rows = {}
        for b, rec in recs.items():
            if b == "0":
                rows["0"] = dict(realized_rate_mult_post_burst=r(rec["realized_rate_mult_post_burst"], 3),
                                 secondary_level_crossing=rec["level_crossing"]["label"])
                continue
            u = rec["b_eff_used"]
            rows[b] = dict(b_eff_calibrated=r(u["primary"], 1), b_eff_raw=r(u["band_raw_time_maximum"], 1),
                           calibration_factor=r(rec["calibration_factor"]["time_resolved"], 4),
                           p_stuck_PRIMARY=r(rec["primary"]["p_stuck"], 3), p_good_PRIMARY=r(rec["primary"]["p_good"], 3),
                           band_p_stuck={k[5:]: r(rec[k]["p_stuck"], 3) for k in u if k.startswith("band_")},
                           band_p_good={k[5:]: r(rec[k]["p_good"], 3) for k in u if k.startswith("band_")},
                           band_p_stuck_realized_post_burst_rate=r(rec["band_realized_post_burst_rate"]["p_stuck"], 3),
                           b_eff_bands={k[5:]: r(v, 1) for k, v in u.items() if k.startswith("band_")},
                           secondary_level_crossing=rec["level_crossing"]["label"])
        per[f"seed_{sd}"] = rows
    br = B["bracketing_rule"]
    rule = {k: dict(p_rule=r(v.get("p_rule_independent", v.get("p_rule")), 3),
                    **({"p_rule_shared_susceptibility": r(v["p_rule_comonotone"], 3)} if "p_rule_comonotone" in v else {}),
                    **({"p_good_40_per_seed": [r(x, 3) for x in v["p_good_40_per_seed"]],
                        "p_stuck_60_per_seed": [r(x, 3) for x in v["p_stuck_60_per_seed"]]} if "p_good_40_per_seed" in v else {}))
            for k, v in br.items() if k != "secondary_level_crossing_deterministic"}
    rule["secondary_level_crossing_deterministic"] = br["secondary_level_crossing_deterministic"]
    cr = B["critical"]
    r135 = B["row_1p35x"]
    return dict(
        command=CMD.format("b2"), cell="a100_300k", multiple=1.65, lam=r(B["lam"], 6), seeds=[0, 1, 2],
        stuck_by_s=r(B["stuck_by_s"], 0), good_from_s=r(B["good_from_s"], 0), S_bar_n1=r(B["S_bar_n1"], 3),
        critical=dict(b_crit_deterministic=r(cr["b_crit_deterministic"], 1), b_committor_50=r(cr["b_committor_50"], 1),
                      b_p_stuck_50=r(cr["b_p_stuck_50"], 1), b_stat=r(cr["b_stat"], 1), n1=r(cr["n1"], 2), n_u=r(cr["n_u"], 2),
                      composition_averaged_b_p_stuck_50=r(B["composition_averaged"]["primary_calibrated"]["b_p_stuck_50"], 1),
                      composition_averaged_b_p_stuck_50_raw=r(B["composition_averaged"]["band_raw_time_maximum"]["b_p_stuck_50"], 1)),
        calibration=dict(rule=B["calibration"]["rule"], seeds=B["calibration"]["seeds"],
                         factor_time_resolved={k: r(v, 4) for k, v in B["calibration"]["factor_time_resolved"].items()},
                         factor_lockstep={k: r(v, 4) for k, v in B["calibration"]["factor_lockstep"].items()}),
        dose_response_exchangeable_frozen_layer=ex,
        noburst_protocol=dict(p_stuck=r(B["noburst_protocol"]["p_stuck"], 3), p_good=r(B["noburst_protocol"]["p_good"], 3)),
        dose_response_composition_averaged=comp, per_seed_exact_plans=per, bracketing_rule=rule,
        frozen_check_max_abs_diff=B.get("frozen_check_max_abs_diff"),
        row_1p35x=dict(critical={k: r(v, 1) for k, v in r135["critical"].items()},
                       exchangeable={str(int(x["burst"])): r(x["p_stuck"], 3) for x in r135["exchangeable"]["rows"]},
                       composition_averaged_b_p_stuck_50=r(r135["composition_averaged"]["primary_calibrated"]["b_p_stuck_50"], 1),
                       composition_averaged_b_p_stuck_50_raw=r(r135["composition_averaged"]["band_raw_time_maximum"]["b_p_stuck_50"], 1)))


def n2_block() -> Dict[str, Any]:
    N = load("h200_n2")
    var = {}
    for k, v in N["variants"].items():
        var[k] = dict(n_half_fluid=r(v["n_half_fluid"], 2), n_half_annealed=r(v["n_half_annealed"], 2), n_b=r(v["n_b"], 2),
                      points={n: dict(hit_fluid=r(p["hit_fluid"], 3), hit_annealed=r(p["hit_annealed"], 3), mu_fluid=r(p["mu_fluid"], 4),
                                      mu_annealed=r(p["mu_annealed"], 4)) for n, p in v["points"].items()},
                      rule_deterministic={e: d["rule_holds"] for e, d in v["deterministic"].items()},
                      p_rule={t: r(p["p_rule"], 3) for t, p in v["probability"].items()},
                      frozen_curve_max_abs_diff=v["frozen_curve_max_abs_diff"])
    em = N["error_model"]
    return dict(command=CMD.format("h200_n2"), rule=N["rule"]["statement"], primary_variant="h200_300k",
                primary_probability="fluid n_half center, sigma = RMS of the fluid n_half error on the three validated cells",
                error_model=dict(sigma_all_cells=r(em["sigma_all_cells"], 3), sigma_sglang_cells=r(em["sigma_sglang_cells"], 3),
                                 errors_pred_minus_meas={k: r(x, 2) for k, x in em["errors_pred_minus_meas"].items()}),
                p_rule_PRIMARY=r(N["band"]["p_rule_primary"], 3), p_rule_band=[r(x, 3) for x in N["band"]["p_rule_range"]],
                deterministic_band=f"{N['band']['n_rule_holds']}/{N['band']['n_combinations']} variant x estimator combinations hold; "
                                   f"failing: {', '.join(N['band']['failing']) or 'none'}",
                variants=var, rival_capacity_ratio={k: r(v, 2) if not isinstance(v, str) else v for k, v in N["rival_capacity_ratio"].items()})


def toolslow_block() -> Dict[str, Any]:
    T = load("toolslow")
    deltas = {}
    for d, v in T["deltas"].items():
        st = v["stochastic"]
        deltas[d] = dict(fluid_verdict=v["fluid"]["verdict"], n_at_2100=r(v["fluid"]["n_at_off"], 2), n_u_normal=r(v["fluid"]["n_u_normal"], 2),
                         slowed_curve=dict(mu_max=r(v["slowed_curve"]["mu_max"], 4), n1=r(v["slowed_curve"]["n1"], 2),
                                           n_u=r(v["slowed_curve"]["n_u"], 2), n_b=r(v["slowed_curve"]["n_b"], 2)),
                         p_escape_during_slowdown=r(st["p_escape_slowdown"], 3), committor_after=r(st["committor_after"], 4),
                         p_stuck_PRIMARY=r(st["p_stuck"], 3), p_good_PRIMARY=r(st["p_good"], 3),
                         band_target_n_u=dict(p_stuck=r(v["stochastic_band_target_n_u"]["p_stuck"], 3),
                                              p_good=r(v["stochastic_band_target_n_u"]["p_good"], 3)),
                         switch_at_2100_plus_delta=v["fluid_switch_at_2100_plus_delta"]["verdict"],
                         sensitivity_exp_same_mean=v["sensitivity_exp_same_mean"],
                         per_seed={f"seed_{s}": dict(X0=x["plan_population"]["alive_at_probe"],
                                                     max_alive_slowdown=x["plan_population"]["max_alive_slowdown"],
                                                     p_stuck=r(x["stochastic"]["p_stuck"], 3), p_good=r(x["stochastic"]["p_good"], 3))
                                   for s, x in v["per_seed"].items()})
    return dict(command=CMD.format("toolslow"), cell="a100_300k", multiple=1.35, slowdown=[1200, 2100],
                critical_delta={k: (r(v, 2) if not isinstance(v, list) else [dict(delta=r(x["delta"], 2), direction=x["direction"]) for x in v])
                                for k, v in T["critical_delta"].items() if k != "p_stuck_scan"},
                p_stuck_scan={f"{d:g}": [r(a, 3), r(b, 3)] for d, a, b in zip(T["critical_delta"]["p_stuck_scan"]["delta"],
                                                                         T["critical_delta"]["p_stuck_scan"]["p_stuck"],
                                                                         T["critical_delta"]["p_stuck_scan"]["p_stuck_band_target_n_u"])},
                p_stuck_scan_columns=["primary (escape target n_b(delta))", "band (escape target n_u)"], deltas=deltas,
                rule=dict(statement=T["rule"]["statement"], p_rule_PRIMARY=r(T["rule"]["p_rule"], 3),
                          p_rule_exchangeable=r(T["rule"]["p_rule_exchangeable"], 3)),
                delta_table_shifted={d: dict(mu_max=r(x["mu_max"], 4), n1=r(x["n1"], 2), n_u=r(x["n_u"], 2), n_at_2100=r(x["n_at_off"], 1),
                                             verdict=x["verdict"]) for d, x in T["delta_table"]["shifted"].items()},
                delta_table_exp_same_mean={d: dict(n_at_2100=r(x["n_at_off"], 1), verdict=x["verdict"])
                                           for d, x in T["delta_table"]["exp_same_mean"].items()})


def shed_block() -> Dict[str, Any]:
    S = load("shed")
    taus = {t: dict(resume_s=v["resume_s"], expected_refused=r(v["expected_sessions_refused"], 1),
                    quasi_static=dict(n_at_resume=r(v["quasi_static"]["n_at_resume"], 1), verdict=v["quasi_static"]["verdict"],
                                      p_stuck=r(v["quasi_static"]["p_stuck"], 3), p_good=r(v["quasi_static"]["p_good"], 3)),
                    round_robin=dict(n_at_resume=r(v["round_robin"]["n_at_resume"], 1), verdict=v["round_robin"]["verdict"],
                                     p_stuck=r(v["round_robin"]["p_stuck"], 3)))
            for t, v in S["taus"].items()}
    per = {f"seed_{sd}": {t: dict(refused=x["refused_sessions"], n_at_1800=r(x["n_at_1800_plan_round_robin"], 1),
                                  n_at_resume=r(x["n_at_resume"], 1), verdict=x["verdict"]) for t, x in v.items()}
           for sd, v in S["per_seed"].items()}
    tm = S["tau_min"]
    return dict(command=CMD.format("shed"), cell="a100_300k", multiple=1.35, x0_n_at_1800=r(S["x0_n_at_1800"], 1),
                n_u=r(S["n_u"], 2), n_b=r(S["n_b"], 2), mu_b=r(S["mu_b"], 5),
                tau_min_prop_S_PRIMARY=r(tm["0"]["tau_min"], 0),
                tau_min_partial_cuts={k: r(v["tau_min"], 0) for k, v in tm.items() if isinstance(v, dict) and "tau_min" in v},
                tau_min_round_robin_band=r(S["round_robin_drain"]["tau_min"], 0),
                round_robin_completion_rate=dict(at_1800_over_lambda_ref=r(S["round_robin_drain"]["completion_rate_at_1800_over_lambda_ref"], 2),
                                                 mean=r(S["round_robin_drain"]["mean_completion_rate"], 4),
                                                 at_n_b=r(S["round_robin_drain"]["completion_rate_at_n_b"], 4)),
                tau_50_committor=dict(quasi_static=r(S["tau_50_quasi_static"], 0), round_robin=r(S["tau_50_round_robin"], 0)),
                taus=taus, per_seed=per, cap_comparison=S["cap_comparison"],
                rule=dict(statement=S["rule"]["statement"], registration=S["rule"]["registration"],
                          registered_seeds=S["rule"]["registered_seeds"], p_rule_PRIMARY=r(S["rule"]["p_rule"], 4),
                          p_rule_if_three_seeds=r(S["rule"]["p_rule_if_three_seeds"], 4),
                          refused_counts_role=S["rule"]["refused_counts_role"]))


def e0f_block() -> Dict[str, Any]:
    E = load("e0f")
    rows = {}
    for m, v in E["rows"].items():
        rows[m] = dict(p_unstable_PRIMARY=r(v["p_unstable_exchangeable"], 3),
                       binomial_k_unstable_0_to_3=[r(x, 4) for x in v["binomial_exchangeable"]],
                       poisson_binomial_realized=[r(x, 4) for x in v["poisson_binomial_realized"]],
                       per_seed={f"seed_{s}": dict(role=x["role"], realized_mult=r(x["realized_mult"], 3),
                                                   p_unstable_realized_rate=r(x["p_unstable_realized_rate"], 3),
                                                   secondary_level_crossing="unstable" if x["level_crossing"]["unstable"] else "stable")
                                 for s, x in v["per_seed"].items()})
    rr = E["replication_rule"]
    return dict(command=CMD.format("e0f"), cell="a100_300k", horizon_s=3000, seeds=[3, 4, 5], rows=rows,
                replication_rule=dict(statement=rr["statement"],
                                      PRIMARY={k: r(v, 3) for k, v in rr["primary_exchangeable"].items()},
                                      band_realized_rate={k: r(v, 3) for k, v in rr["band_realized_rate"].items()},
                                      secondary_level_crossing=rr["secondary_level_crossing"]))


def prop_e_block() -> Dict[str, Any]:
    P = load("prop_e_cor_c")
    pe = {}
    for name, v in P["prop_e"].items():
        pts = {}
        for p in v["points"]:
            n = f"{int(p['n'])}"
            pts[n] = dict(requested=p["requested"], measured_hit=r(p["measured"]["hit"], 3), measured_mu_turns=r(p["measured"]["mu_turns"], 4),
                          measured_queue_mean=r(p["measured"]["queue_mean"], 1),
                          yao_thm31_measured_rate=r(p["yao_measured_rate_turns"]["hit"], 3),
                          yao_little_no_service=r(p["yao_little_no_service"]["hit"], 3), che_W_eq_Z=r(p["che_W_eq_Z"]["hit"], 3),
                          bound_K0=r(p["bound_K0"]["hit_lower"], 3), K_needed_fraction_of_M=r(p["K_needed"]["fraction_of_M"], 4),
                          merged_frozen_fluid=r(p.get("merged_frozen", {}).get("hit_fluid"), 3),
                          merged_frozen_annealed=r(p.get("merged_frozen", {}).get("hit_annealed"), 3))
        pe[name] = dict(label=v["label"], pool=v["pool"], points=pts)
    cc = {}
    for name, v in P["cor_c"].items():
        cc[name] = dict(blind=v["blind"], M_over_E_bar=r(v["M_over_E_bar"], 2), M_over_E_lb=r(v["M_over_E_lb"], 2), M_over_E_S=r(v["M_over_E_S"], 2),
                        n_b=r(v["n_b"], 2), tool_call_part=r(v["tool_call_part"], 2), n_half_fluid=r(v["n_half_fluid"], 2))
        if "measured" in v:
            cc[name]["measured_n_half"] = r(v["measured"]["n_half"], 2)
            cc[name]["measured_bracket"] = v["measured"]["bracket"]
            cc[name]["errors_vs_measured"] = {k: r(x, 2) for k, x in v["errors_vs_measured_n_half"].items()}
        else:
            cc[name]["rival_prediction_crossing"] = dict(M_over_E_S=r(v["M_over_E_S"], 2), M_over_E_lb=r(v["M_over_E_lb"], 2))
            cc[name]["scoring"] = v["rival_prediction"]["scoring"]
    return dict(command=CMD.format("prop_e"), prop_e=pe, cor_c=cc)


def blind_block() -> Dict[str, Any]:
    B = load("blind_tables")
    H = load("h200_600k")
    fl, an, fe = H["closed_curve"]["fluid"], H["closed_curve"]["annealed"], H["from_empty_edge"]
    h6 = dict(spec="analysis/theory/cells/h200_600k.yaml", json="results/theory/pred2/h200_600k.json",
              n_half_fluid=r(fl["n_half"], 2), n_half_annealed=r(an["n_half"], 2), n_b=r(fl["n_b"], 2), peak_n=r(fl["peak_n"], 1),
              mu_max=r(fl["mu_max"], 4), window_vs_lambda_ref=r(H["window"]["vs_lambda_ref"], 3), edge_mult=r(fe["edge_mult"], 3),
              predicted_bracket=fe["predicted_bracket"], secondary_edge50=r(fe["secondary_level_crossing"]["edge50_mult"], 3),
              p_escape_registered={k: r(v, 3) for k, v in fe["p_escape_registered"].items()},
              registration_consequence=H["registration_consequence"],
              grid_points={k: dict(hit_fluid=r(v["hit_fluid"], 3), hit_annealed=r(v["hit_annealed"], 3), mu_fluid=r(v["mu_fluid"], 4),
                                   mu_annealed=r(v["mu_annealed"], 4)) for k, v in H["closed_curve"]["grid_points"].items()},
              e2_arms={k: dict(n1=r(a["n1"], 2), n_u=r(a["n_u"], 2), b_stat=r(a["b_stat"], 1),
                               backlog=r(a.get("burst_trapped", {}).get("backlog"), 1),
                               gap_over_R=r(a.get("burst_trapped", {}).get("gap_over_R"), 2),
                               capped_drain_s=r(a.get("capped_static", {}).get("drain_after_burst_s"), 0),
                               b_crit=r(a.get("critical_burst_fresh", {}).get("b_fresh"), 1)) for k, a in H["e2"]["arms"].items()})

    def tab(t):
        rows = {}
        for k, x in t["rows"].items():
            bt, gs, cp = x.get("burst_trapped", {}), x.get("noburst_good_state", {}), x.get("capped_static") or {}
            rows[k] = dict(lam=r(x["lam"], 5), in_window=x["in_window"], n1=r(x["n1"], 2), n_u=r(x["n_u"], 2), b_stat=r(x["b_stat"], 1),
                           noburst_hit=r(gs.get("hit"), 3), backlog=r(bt.get("backlog"), 1),
                           token_ratio=r(bt.get("token_ratio_vs_model_e0a"), 4), gap_over_R=r(bt.get("gap_over_R"), 2), R=r(bt.get("R"), 1),
                           b_crit=r(x.get("critical_burst_fresh", {}).get("b_fresh"), 1),
                           capped_drain_s={c: r(v["drain_after_burst_s"], 0) for c, v in cp.items()})
        return dict(lambda_ref=r(t["lambda_ref"], 5), window=r(t["window"], 3), caps=t["caps"], rows=rows)

    riv = {n: dict(M_over_E_bar=r(v["M_over_E_bar"], 2), M_over_E_lb=r(v["M_over_E_lb"], 2), M_over_E_S=r(v["M_over_E_S"], 2),
                   n_b=r(v["n_b"], 2), n_half_fluid=r(v["n_half_fluid"], 2), che_W_eq_Z_half_crossing=r(v["che_half_crossing"], 2),
                   yao_little_half_crossing=r(v["yao_little_half_crossing"], 2),
                   b_stat_at_frozen_e2_points={k: r(x, 1) for k, x in v["b_stat_at_frozen_e2_points"].items()})
           for n, v in B["rivals"].items()}
    look = {n: dict(frozen_check=v["frozen_check"], n_range=[min(float(k) for k in v["points_every_integer_n"]),
                                                              max(float(k) for k in v["points_every_integer_n"])],
                    mult_range=[min(float(k) for k in v["p_escape_every_0p01_mult"]), max(float(k) for k in v["p_escape_every_0p01_mult"])])
            for n, v in B["pool_lookup"].items()}
    return dict(command=CMD.format("blind_tables"), json="results/theory/pred2/blind_tables.json", h200_600k=h6,
                trapped_tables_in_this_file=dict(h200_300k=tab(B["trapped_tables"]["h200_300k"]),
                                                 llama31_8b_300k=tab(B["trapped_tables"]["llama31_8b_300k"])),
                trapped_tables_variants_in_json=[n for n in B["trapped_tables"] if n not in ("h200_300k", "llama31_8b_300k")],
                rivals=riv, rival_exogenous_gap_curves_in_json="rivals.<cell>.che_W_eq_Z_hit / yao_little_no_service_hit (every integer n)",
                pool_lookup_in_json=look)


def main() -> None:
    T = load("b2_basin")["provenance"]
    doc = dict(
        model=f"r13-merged-2 at tag {FROZEN_TAG} ({FROZEN_COMMIT[:7]}), UNCHANGED: drivers in analysis/theory/pred2/ only",
        frozen_code_check=T.get("frozen_code_check"),
        reproduce=dict(env='Windows Git Bash; python = "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"; PYTHONPATH="src;."',
                       all=CMD.format("run_all"), this_file=CMD.format("freeze_table"), deterministic=True,
                       conditional_h200='PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell h200_300k --registration <the pushed H200 E2 registration>',
                       conditional_llama='PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell llama31_8b_300k --registration <the pushed Llama E2 registration>'),
        b2=b2_block(), n2_h200=n2_block(), toolslow=toolslow_block(), shed=shed_block(), e0f=e0f_block(), prop_e_cor_c=prop_e_block(), blind_tables=blind_block())
    hdr = ("# configs/r13_theory_pred2.yaml -- SECOND blind prediction set of the round-13 theory (pred2), branch r13/pred2.\n"
           "# Model frozen at tag r13-theory-pred (997d2c4): no function or parameter under analysis/theory that existed there changed;\n"
           "# new drivers only (analysis/theory/pred2/).  Written before any B2, TOOLSLOW, SHED or N2 run exists and without reading any\n"
           "# B1, H200, Llama, E0F, LPM-INF, rescue or pool-sweep result.  Prose, blindness scope, inputs and approximations:\n"
           "# notes/PREDICTIONS_r13_pred2.md.  Generated from results/theory/pred2/*.json by analysis/theory/pred2/freeze_table.py.\n")
    with open(CFG, "w") as f:
        f.write(hdr)
        yaml.safe_dump(doc, f, sort_keys=False, width=140)
    print("wrote", CFG)


if __name__ == "__main__":
    main()
