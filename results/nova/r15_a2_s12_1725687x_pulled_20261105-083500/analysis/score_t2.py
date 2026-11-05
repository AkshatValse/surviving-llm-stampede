"""Score the r15 T1/T2 TOOLSLOW cells against the frozen predictions (notes/PREDICTIONS_r15.md section 4).

Usage: python score_t2.py <r15_runs.csv from analysis.r15_cells classify> <out.json>
Reads only the classify output; the frozen calls below are copied from PREDICTIONS_r15.md (frozen YAML block).
"""
import csv
import json
import math
import sys

FROZEN = {
    "T1": {"simulator_mixed": ["STUCK", "STUCK", "STUCK"], "simulator_separate": ["STUCK", "STUCK", "STUCK"],
           "pred2_fluid": "STUCK", "p_stuck": [1.000, 1.000, 1.000], "p_good": [0.000, 0.000, 0.000],
           "modal": ["STUCK", "STUCK", "STUCK"], "cell": {"simulator": "TRAPS", "pred2_fluid": "TRAPS"},
           "p_cell": {"TRAPS": 1.000, "NO-TRAP": 0.0, "MIXED": 0.0}},
    "T2": {"simulator_mixed": ["STUCK", "GOOD", "GOOD"], "simulator_separate": ["STUCK", "GOOD", "GOOD"],
           "pred2_fluid": "STUCK", "p_stuck": [1.000, 0.462, 0.220], "p_good": [0.000, 0.532, 0.770],
           "modal": ["STUCK", "GOOD", "GOOD"], "cell": {"simulator": "NO-TRAP", "pred2_fluid": "TRAPS"},
           "p_cell": {"TRAPS": 0.580, "NO-TRAP": 0.409, "MIXED": 0.010}},
}
FLOOR = 1e-3


def state(r):
    st, gd = r["stuck"] == "True", r["good"] == "True"
    return "STUCK" if st and not gd else "GOOD" if gd and not st else "NEITHER"


def main(path, out):
    rows = [r for r in csv.DictReader(open(path)) if r["role"] == "new" and r.get("counted") == "True"]
    res = {}
    for cell, fz in FROZEN.items():
        rr = sorted([r for r in rows if r["cell"] == cell], key=lambda r: int(r["seed"]))
        if not rr:
            continue
        obs = {int(r["seed"]): state(r) for r in rr}
        seeds = sorted(obs)
        n_st = sum(v == "STUCK" for v in obs.values())
        n_gd = sum(v == "GOOD" for v in obs.values())
        cell_out = ("MIXED" if n_st >= 2 and n_gd >= 2 else "TRAPS" if n_st >= 2 else "NO-TRAP" if n_gd >= 2 else "MIXED") \
            if len(seeds) == 3 else None
        agree = {}
        for k in ("simulator_mixed", "simulator_separate", "modal"):
            agree[k] = sum(obs[s] == fz[k][s] for s in seeds)
        agree["pred2_fluid"] = sum(obs[s] == fz["pred2_fluid"] for s in seeds)
        ll_st = sum(math.log(max(FLOOR, fz["p_stuck"][s] if obs[s] == "STUCK" else 1 - fz["p_stuck"][s])) for s in seeds)
        ll_gd = sum(math.log(max(FLOOR, fz["p_good"][s] if obs[s] == "GOOD" else 1 - fz["p_good"][s])) for s in seeds)
        br_st = sum((fz["p_stuck"][s] - (obs[s] == "STUCK")) ** 2 for s in seeds) / len(seeds)
        br_gd = sum((fz["p_good"][s] - (obs[s] == "GOOD")) ** 2 for s in seeds) / len(seeds)
        p_obs = fz["p_cell"].get(cell_out) if cell_out else None
        res[cell] = {"observed_per_seed": {str(s): obs[s] for s in seeds}, "cell_outcome_from_counted": cell_out,
                     "simulator_cell_call_correct": (fz["cell"]["simulator"] == cell_out) if cell_out else None,
                     "pred2_fluid_cell_call_correct": (fz["cell"]["pred2_fluid"] == cell_out) if cell_out else None,
                     "per_seed_agreement": agree, "n_seeds": len(seeds),
                     "pred2_per_seed_loglik_stuck": ll_st, "pred2_per_seed_loglik_good": ll_gd,
                     "pred2_per_seed_brier_stuck": br_st, "pred2_per_seed_brier_good": br_gd,
                     "pred2_p_cell_outcome": p_obs, "pred2_log_score_cell": math.log(max(FLOOR, p_obs)) if p_obs is not None else None}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
