"""r15 REPLICATE-EDGE (exploratory): frozen predictions for the same-plan replicates of seeds 0 and 4 at 2.5 x (3000 s from empty).

    PYTHONPATH="src;." python experiments/r15_edge_preds.py [--out results/theory/r15/edge_preds.json]

Writes ONE json (and prints a summary). Nothing in src/, analysis/theory/ or experiments/r11_predict_basin.py is edited; the r11
driver is imported and called unchanged.

1. Deterministic comparators of each plan, from the exact client plan (agentload.workload.build_open_plan on
   configs/agentload_e0_cap.yaml with seed, 2.5 x lambda_ref, 3000 s), as the N3 review defined them (scratch verify-N3/rates.py):
   realized arrival count n and n / (3000 lambda_ref); turn load = total turns / (3000 lambda_ref x mean_turns 15); token work =
   sum over sessions of T L0 + (Delta + d) T (T - 1) / 2 (the prompt tokens of an all-miss run), in Mtok. Brackets from the four
   committed 2.5 x runs (seeds 3, 4, 5 stable, seed 0 unstable). Any deterministic function of the plan gives every replicate of
   a plan the same outcome, so each comparator predicts REPRODUCIBLE.
2. The calibrated simulator's exact-plan calls: the round-6 calibrated engine of configs/r6_predict.yaml (asserted) through the
   r11 E0F driver (configs/r11_predict_basin.yaml; experiments/r11_predict_basin.py _work + e0b_classify, unchanged), PRIMARY
   mixed batching and SECONDARY separate_prefill_priority, at duration 3000 s with the E0b config; both the registered stable
   rule (r11's e0b_classify) and the r15 per-run rule (analysis.r15_edge.classify_bins on the simulator's 100 s follow-up hit
   windows: hits / (admitted turns - first-turn admits), attributed by admission time, not completion time). The simulator is
   deterministic given the plan, so it also predicts REPRODUCIBLE when it calls 0 UNSTABLE and 4 STABLE. Descriptive add-on:
   a service-speed sensitivity (every engine time constant x f, f = 0.70 .. 1.30; the ~2 % spread of the all-miss token rate
   across nova22-gpu-1/2/3 is f within about 0.99 .. 1.01), to show whether a node-speed difference alone could flip a plan.
3. The frozen F2 escape law at 2.5 x (results/theory/merged/a100_300k.json from_empty_edge.p_escape_fine['2.5'], frozen at
   r13-theory-pred 997d2c4) and its verdict probabilities if each replicate were an independent draw; and the frozen pred2
   realized-rate band and level-crossing calls for seeds 0 and 4 (results/theory/pred2/e0f.json, r13-theory-pred2 cfa7712).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
for p in (str(REPO / "src"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agentload.config import load_config, resolve_rate  # noqa: E402
from agentload.workload import build_open_plan  # noqa: E402
from analysis import r15_edge as E  # noqa: E402
from prefixmeta.probe import load_probe_config  # noqa: E402
from prefixmeta.sim import deep_update  # noqa: E402

import experiments.r11_predict_basin as R11  # noqa: E402

RULE_FILE = "configs/r15_edge_replicate.yaml"
SPEC = "configs/r11_predict_basin.yaml"
ENDPOINTS = "configs/r11_basin_predict.yaml"
F2_FILE = "results/theory/merged/a100_300k.json"
PRED2_FILE = "results/theory/pred2/e0f.json"
R11_E0B_RUNS = "results/r11_predict_basin/20261030-194539/e0b_runs.csv"
MULT, H = 2.5, 3000.0
BRACKET_SEEDS = {0: "UNSTABLE", 3: "STABLE", 4: "STABLE", 5: "STABLE"}      # the four committed 2.5 x runs
SPEED_FACTORS = (0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99, 1.0, 1.01, 1.02, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30)
TIME_KEYS = ("iter_fixed_s", "iter_floor_s", "per_token_s", "decode_attn_s", "prefill_attn_s")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(args: List[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:      # pragma: no cover
        return f"<git failed: {e}>"


# ======================================================================= 1. deterministic comparators
def plan_stats(seed: int, lam_ref: float) -> Dict[str, Any]:
    sets = [f"run.seed={seed}", f"arrivals.rate_mult={MULT}", f"arrivals.lambda_ref={lam_ref!r}", f"run.duration_s={H}"]
    cfg, _ = load_config(REPO / "configs/agentload_e0_cap.yaml", sets)
    rate = resolve_rate(cfg.arrivals)
    plan = build_open_plan(seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, [])
    wl = cfg.workload
    T = np.array([p.n_turns for p in plan], dtype=float)
    L0, dd = float(wl.initial_context_tokens), float(wl.new_prompt_tokens + wl.decode_tokens)
    work = float(np.sum(T * L0 + dd * T * (T - 1) / 2.0))
    arr = np.array([p.arrival_s for p in plan])
    max600 = max(int(((arr >= a) & (arr < a + 600.0)).sum()) for a in np.arange(0.0, H - 600.0 + 1.0, 50.0))
    return {"n_sessions": int(len(plan)), "realized_mult_count": len(plan) / (H * lam_ref), "turns_total": int(T.sum()),
            "turn_load_mult": float(T.sum()) / (H * lam_ref * float(wl.mean_turns)), "token_work_Mtok": work / 1e6,
            "n_arrivals_first_1500_s": int((arr < 1500.0).sum()), "max_arrivals_in_600_s": max600, "resolved_rate": rate}


def comparators(lam_ref: float) -> Dict[str, Any]:
    st = {s: plan_stats(s, lam_ref) for s in BRACKET_SEEDS}
    out: Dict[str, Any] = {"definitions": {
        "count": "n sessions arriving in [0, 3000) / (3000 lambda_ref)",
        "turns": "total turns of those sessions / (3000 lambda_ref x 15)  (15 = workload.mean_turns, as verify-N3 rates.py)",
        "token_work": "sum over sessions of T L0 + (Delta + d) T (T - 1) / 2 with L0 2000, Delta + d 650 (Mtok; all-miss prompt tokens)"},
        "per_seed": {str(s): {**v, "committed_2p5x_outcome": BRACKET_SEEDS[s]} for s, v in st.items()}, "brackets": {}, "calls": {}}
    for key, name in (("realized_mult_count", "count"), ("turn_load_mult", "turns"), ("token_work_Mtok", "token_work")):
        smax = max(st[s][key] for s in st if BRACKET_SEEDS[s] == "STABLE")
        umin = min(st[s][key] for s in st if BRACKET_SEEDS[s] == "UNSTABLE")
        out["brackets"][name] = {"stable_max": smax, "unstable_min": umin, "separates": bool(smax < umin)}
        for s in E.PLANS:
            x = st[s][key]
            call = "UNSTABLE" if x >= umin else "STABLE" if x <= smax else "UNDETERMINED"
            out["calls"].setdefault(str(s), {})[name] = call
    calls = out["calls"]
    out["predicted_verdict_each"] = {name: ("REPRODUCIBLE" if calls["0"][name] == "UNSTABLE" and calls["4"][name] == "STABLE"
                                           else "UNDETERMINED") for name in out["brackets"]}
    out["note"] = ("the brackets were measured on these very runs (seeds 0 and 4 define them), so the calls are retrodictions of the "
                   "originals; for the replicates they predict that every run of a plan repeats its original (REPRODUCIBLE), "
                   "because a deterministic plan statistic cannot differ between replicates of one plan")
    return out


# ======================================================================= 2. calibrated simulator, exact plans
def r15_rule_on_sim(windows: List[Dict[str, Any]], pr: Dict[str, Any]) -> Dict[str, Any]:
    w = pd.DataFrame(windows).sort_values("t_start")
    bins = pd.DataFrame({"t0": w["t_start"].to_numpy(float),
                         "n": (w["admitted_turns"] - w["first_turn_admits"]).to_numpy(float), "hits": w["hits"].to_numpy(float)})
    c = E.classify_bins(bins, pr)
    return {k: c[k] for k in ("label", "tau_s", "stable_kind", "min_hit_after_warm", "last_window_hit", "coarse_300s")}


def simulate(cfg: Dict[str, Any], rb: Dict[str, Any], ep: Dict[str, Any], pr: Dict[str, Any], seed: int, mode: str,
             batching: str) -> Dict[str, Any]:
    job = {"cfg": cfg, "kind": "e0b", "mode": mode, "batching": batching, "policy": rb["policy"], "seed": int(seed),
           "seed_kind": "engine", "mult": MULT, "lambda_ref": float(rb["lambda_ref"]), "burst_n": 0, "duration_s": H,
           "agentload_config": rb["e0b"]["agentload_config"], "variant": f"e0b|m={MULT}|{mode}",
           "stop_backlog_above": int(rb["e0b"]["unstable_backlog_stop"])}
    r = R11._work(job)
    e = R11.e0b_classify(r, ep)
    return {"n_sessions": r["n_base"], "registered_rule": {k: e[k] for k in ("stable", "final_queue_lastwin", "trend_rise",
                                                                             "stopped_early", "tail_hit", "max_queue")},
            "r15_rule": r15_rule_on_sim(r["windows"], pr)}


def simulator_calls(pr: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_probe_config(str(REPO / SPEC), REPO, None)
    rb = cfg["r11_basin"]
    r6 = load_probe_config(str(REPO / "configs/r6_predict.yaml"), REPO, None)
    if cfg["engine"] != r6["engine"] or cfg["workload"] != r6["workload"] or cfg["metrics"] != r6["metrics"]:
        raise SystemExit("effective engine / workload / metrics differ from configs/r6_predict.yaml")
    ep = yaml.safe_load((REPO / ENDPOINTS).read_text())
    calls: Dict[str, Any] = {}
    for mode, batching in rb["modes"].items():
        for s in E.PLANS:
            calls.setdefault(str(s), {})[mode] = simulate(cfg, rb, ep, pr, s, mode, batching)
    # the committed r11 E0F scoring (results/r11_predict_basin/20261030-194539, same driver) must be reproduced
    ref = pd.read_csv(REPO / R11_E0B_RUNS)
    repro = {}
    for s in E.PLANS:
        for mode in rb["modes"]:
            row = ref[(ref["mode"] == mode) & (ref["seed"] == s) & (ref["mult"] == MULT)].iloc[0]
            mine = calls[str(s)][mode]["registered_rule"]
            repro[f"{s}|{mode}"] = bool(bool(row["stable"]) == mine["stable"]
                                        and abs(float(row["final_queue_lastwin"]) - mine["final_queue_lastwin"]) < 1e-9
                                        and abs(float(row["trend_rise"]) - mine["trend_rise"]) < 1e-6)
    sens: Dict[str, Any] = {}
    for f in SPEED_FACTORS:
        cf = deep_update(cfg, {"engine": {k: float(cfg["engine"][k]) * f for k in TIME_KEYS}})
        for mode, batching in rb["modes"].items():
            for s in E.PLANS:
                x = simulate(cf, rb, ep, pr, s, mode, batching)
                sens.setdefault(f"{f}", {}).setdefault(mode, {})[str(s)] = {
                    "r15_label": x["r15_rule"]["label"], "r15_tau_s": x["r15_rule"]["tau_s"],
                    "registered_stable": x["registered_rule"]["stable"]}
    # first factor (moving away from 1) at which each plan's r15 call differs from its call at f = 1 (None: no flip in the scan)
    flips: Dict[str, Any] = {}
    for mode in rb["modes"]:
        for s in E.PLANS:
            base = sens["1.0"][mode][str(s)]["r15_label"]
            up = next((f for f in SPEED_FACTORS if f > 1.0 and sens[f"{f}"][mode][str(s)]["r15_label"] != base), None)
            dn = next((f for f in sorted(SPEED_FACTORS, reverse=True) if f < 1.0
                       and sens[f"{f}"][mode][str(s)]["r15_label"] != base), None)
            flips.setdefault(mode, {})[str(s)] = {"call_at_1": base, "first_flip_slower": up, "first_flip_faster": dn}
    prim = rb["primary_mode"]
    verdict_by_mode = {}
    for mode in rb["modes"]:
        l0, l4 = calls["0"][mode]["r15_rule"]["label"], calls["4"][mode]["r15_rule"]["label"]
        verdict_by_mode[mode] = ("REPRODUCIBLE" if (l0, l4) == ("UNSTABLE", "STABLE") else
                                 f"REPRODUCIBLE-OF-ITS-OWN-CALLS (seed 0 {l0}, seed 4 {l4}): every replicate of a plan repeats the "
                                 f"simulator's call, so a run that matches its original but not the simulator is a simulator miss")
    return {"engine": "round-6 calibrated engine (configs/r6_predict.yaml, asserted equal) via configs/r11_predict_basin.yaml and "
                      "experiments/r11_predict_basin.py _work + e0b_classify (unchanged); plans = the exact client plans",
            "primary_mode": prim, "modes": rb["modes"], "deterministic_given_plan": True, "per_plan": calls,
            "reproduces_committed_r11_e0b_rows": repro, "predicted_verdict_by_mode": verdict_by_mode,
            "speed_sensitivity_descriptive": {"engine_time_keys_scaled": list(TIME_KEYS), "service_time_factors": list(SPEED_FACTORS),
                                              "calls": sens, "first_flip": flips,
                                              "note": "f > 1 = slower service; the 300k E2 trapped all-miss token rate spans 2.0 % "
                                                      "across nova22-gpu-1/2/3 (N3 review), i.e. f within about 0.99-1.01"},
            "caveats": ["the simulator attributes hits by admission time, the engine by completion time",
                        "the simulator has no service noise: it cannot produce a same-plan disagreement except through a speed "
                        "difference (the sensitivity rows)",
                        "the r11 E0F note called seed 4 (2.665 x) its least secure stable call; 11/20 extra seeds at 2.5 x were "
                        "stable (mixed)"]}


# ======================================================================= 3. frozen F2 law and pred2 band
def f2_and_pred2() -> Dict[str, Any]:
    f2 = json.loads((REPO / F2_FILE).read_text())["from_empty_edge"]
    p = float(f2["p_escape_fine"][f"{MULT}"])
    assert p == float(f2["p_escape_registered"][f"{MULT}"])
    q = 1.0 - p
    exch = {"p_unstable_per_run": p, "P_seed0_unstable_3of3": p ** 3, "P_seed4_stable_3of3": q ** 3,
            "P_REPRODUCIBLE_given_3_plus_3": p ** 3 * q ** 3, "P_PLAN_CONDITIONAL_ESCAPE_given_3_plus_3": 1.0 - p ** 3 * q ** 3,
            "P_disagreement_in_plan0": 1.0 - p ** 3, "P_disagreement_in_plan4": 1.0 - q ** 3,
            "P_same_gpu_pair_differs": 2.0 * p * q,
            "P_at_least_one_same_gpu_pair_differs": 1.0 - (1.0 - 2.0 * p * q) ** 2,
            "expected_unstable_replicates_per_plan": 3.0 * p}
    T = -float(f2["horizon_s"]) / math.log(q)
    eff = {"note": "derived, not frozen: the r15 rule's last collapse window starts at 2800 s and needs a fall to <= 0.2, so the "
                   "effective horizon is shorter than 3000 s; with the constant hazard implied by p(3000) the probability at "
                   "2700 s and 2500 s is", "T_escape_s": T, "p_at_2700_s": 1.0 - math.exp(-2700.0 / T),
           "p_at_2500_s": 1.0 - math.exp(-2500.0 / T)}
    pr2 = json.loads((REPO / PRED2_FILE).read_text())
    rows = pr2["rows"][f"{MULT}"]["per_seed"]
    band = {str(s): {k: rows[str(s)][k] for k in ("role", "n_sessions", "realized_mult", "p_unstable_exchangeable",
                                                   "p_unstable_realized_rate")} for s in E.PLANS}
    p0, p4 = band["0"]["p_unstable_realized_rate"], band["4"]["p_unstable_realized_rate"]
    lc = {str(s): rows[str(s)]["level_crossing"] for s in E.PLANS}
    return {"F2": {"source": f"{F2_FILE} from_empty_edge.p_escape_fine['{MULT}'] (= p_escape_registered; frozen at r13-theory-pred "
                             "997d2c4)", "horizon_s": f2["horizon_s"], "target": f2.get("target"), "edge_mult": f2.get("edge_mult"),
                   "exchangeable_independent_replicates": exch, "effective_horizon_derived": eff,
                   "predicted_verdict": "PLAN-CONDITIONAL ESCAPE",
                   "reading": "F2 is a law for a cell, not for a fixed plan: read as independent draws it predicts that both plans "
                              "disagree with themselves. With the arrival path held fixed only service noise is left, so under "
                              "F2's own noise model these disagreement probabilities are upper bounds (Jensen: E[q^4]/E[q] >= "
                              "E[q]^3 for the plan-conditional collapse probability q)."},
            "pred2_realized_rate_band": {"source": f"{PRED2_FILE} rows['{MULT}'].per_seed (frozen at r13-theory-pred2 cfa7712)",
                                         "per_plan": band, "P_REPRODUCIBLE_given_3_plus_3": p0 ** 3 * (1 - p4) ** 3,
                                         "P_PLAN_CONDITIONAL_ESCAPE_given_3_plus_3": 1.0 - p0 ** 3 * (1 - p4) ** 3,
                                         "predicted_verdict": "PLAN-CONDITIONAL ESCAPE"},
            "pred2_level_crossing": {"source": f"{PRED2_FILE} rows['{MULT}'].per_seed[*].level_crossing (deterministic on the exact plan)",
                                     "per_plan": lc, "calls": {s: ("UNSTABLE" if lc[s]["unstable"] else "STABLE") for s in lc},
                                     "predicted_verdict": ("REPRODUCIBLE" if lc["0"]["unstable"] and not lc["4"]["unstable"]
                                                           else "UNDETERMINED")}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="results/theory/r15/edge_preds.json")
    args = ap.parse_args(argv)
    t0 = datetime.now()
    rule = E.load_rule(REPO / RULE_FILE)
    pr = rule["per_run_rule"]
    lam_ref = float(rule["cell"]["lambda_ref"])
    comp = comparators(lam_ref)
    sim = simulator_calls(pr)
    th = f2_and_pred2()
    inputs = [RULE_FILE, SPEC, ENDPOINTS, F2_FILE, PRED2_FILE, R11_E0B_RUNS, "configs/r6_predict.yaml", "configs/agentload_e0_cap.yaml",
              "src/agentload/workload.py", "src/agentload/config.py", "experiments/r11_predict_basin.py", "analysis/r15_edge.py",
              "experiments/r15_edge_preds.py"]
    prim = sim["primary_mode"]
    out = {
        "name": "r15_edge_preds", "status": "FROZEN", "exploratory": True,
        "cell": "r15 REPLICATE-EDGE: A100 300k SGLang FCFS (sglang-fcfs-r1-edgerep), 2.5 x lambda_ref, 3000 s from empty, plans of "
                "seeds 0 and 4 (jobs A: 0 4 0, B: 4 0 4)",
        "written": t0.isoformat(timespec="seconds"),
        "blindness": "written before any run of this cell was submitted; the outcomes of the two ORIGINAL runs (seed 0 UNSTABLE at "
                     "1600 s, seed 4 STABLE) are known and selected the plans, so the per-plan calls below are retrodictions of the "
                     "originals and predictions only of whether the replicates repeat them",
        "rule_file": RULE_FILE,
        "headline": {
            "deterministic_comparators": comp["predicted_verdict_each"],
            "pred2_level_crossing": th["pred2_level_crossing"]["predicted_verdict"],
            "simulator": {m: v for m, v in sim["predicted_verdict_by_mode"].items()},
            "simulator_calls": {s: {m: sim["per_plan"][s][m]["r15_rule"]["label"] for m in sim["modes"]} for s in ("0", "4")},
            "simulator_tau_s": {s: {m: sim["per_plan"][s][m]["r15_rule"]["tau_s"] for m in sim["modes"]} for s in ("0", "4")},
            "simulator_speed_first_flip": sim["speed_sensitivity_descriptive"]["first_flip"],
            "F2_exchangeable": {"verdict": th["F2"]["predicted_verdict"],
                                "P_PLAN_CONDITIONAL_ESCAPE": th["F2"]["exchangeable_independent_replicates"][
                                    "P_PLAN_CONDITIONAL_ESCAPE_given_3_plus_3"],
                                "P_REPRODUCIBLE": th["F2"]["exchangeable_independent_replicates"]["P_REPRODUCIBLE_given_3_plus_3"]},
            "F2_realized_rate_band": {"verdict": th["pred2_realized_rate_band"]["predicted_verdict"],
                                      "P_REPRODUCIBLE": th["pred2_realized_rate_band"]["P_REPRODUCIBLE_given_3_plus_3"]},
            "reading": "every deterministic predictor (plan statistics, level crossing, the simulator) predicts REPRODUCIBLE; only "
                       "the F2 law read as independent draws predicts PLAN-CONDITIONAL ESCAPE (P about 0.99). A within-node "
                       "disagreement would contradict all deterministic predictors; REPRODUCIBLE contradicts F2-as-independent-"
                       "draws but not F2 as a cell law with plan-dependent hazard."},
        "deterministic_comparators": comp, "simulator": sim, **th,
        "provenance": {"git_head": git(["rev-parse", "HEAD"]), "git_branch": git(["rev-parse", "--abbrev-ref", "HEAD"]),
                       "git_status_porcelain": git(["status", "--porcelain"]).splitlines(),
                       "sha256": {f: sha256(REPO / f) for f in inputs}, "hostname": socket.gethostname(),
                       "platform": platform.platform(), "python": sys.version.split()[0], "numpy": np.__version__,
                       "pandas": pd.__version__, "argv": [sys.executable, *sys.argv],
                       "wall_s": (datetime.now() - t0).total_seconds()}}
    p = REPO / args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(out, indent=2) + "\n").encode())
    print(json.dumps(out["headline"], indent=2))
    print("simulator r11 reproduction:", sim["reproduces_committed_r11_e0b_rows"])
    print("speed sensitivity:", json.dumps(sim["speed_sensitivity_descriptive"]["calls"]))
    print("comparators:", json.dumps({k: v for k, v in comp.items() if k in ("brackets", "calls")}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
