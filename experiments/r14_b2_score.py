"""r14 B2 (BASIN-2): score the engine outcome against the frozen pred2 predictions (tag r13-theory-pred2, commit cfa7712).

Written 2026-10-31 after the registered B2 classification (``analysis.basin classify`` -> basin_runs.csv, basin_verdict.json).
Nothing here changes a call: the per-run outcome is the registered basin_state (STUCK := hit_eval < 0.2; GOOD := trap_v2
RECOVERED or (hit_eval > 0.8 and backlog slope <= threshold)), and the rule outcome is basin_verdict.json b2_bracket.bracketed.

The scoring follows the declaration frozen with the predictions (notes/PREDICTIONS_r13_pred2.md, "Scoring, declared now", B2):
Brier score and log-likelihood (probabilities floored at 1e-3) of the nine (seed, b) STUCK outcomes and, separately, of the nine
GOOD outcomes, for the primary (per-seed, calibrated cohort peak), each band, the frozen exchangeable layer and A's deterministic
level-crossing labels (declared_scores_b2_nine_runs holds exactly these). Also: the rule outcome against each predictor's P(rule),
the secondary deterministic crossing (per-run label agreement), the three theory-specific claims of the declaration, and the
per-seed edges of the seven-point curve against the frozen critical sizes (deterministic 53.4, committor 50% 49.5, P(STUCK) 50%
49.3, composition-averaged 50% 48.4).

Added here, not declared (labelled as such in the output, under not_declared, and by declared = False in the CSV): the
composition-averaged column (a separate frozen column of pred2's table, not one of its bands, so not among the declared predictors)
and an uninformative reference (P = 0.5) for the Brier scale, both scored after the fact; the same scores over the six BASIN-1 runs
(n = 25, 100), whose pred2 rows are not blind (pred2 was pushed at 04:20:20 CDT, after the BASIN-1 outcomes were first read at
about 04:07); and whether a single threshold on the per-seed calibrated (or raw) cohort size separates the observed outcomes.

The frozen files are read from git at --pred-ref (default the tag r13-theory-pred2), so the scored numbers are the frozen ones;
--pred-json / --pred-yaml read files instead. Their sha256 and the commit are recorded.

Usage: PYTHONPATH="src;." python experiments/r14_b2_score.py --basin-dir <.../agentload_analysis_basin/<stamp>> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

FLOOR = 1e-3
B2_SIZES = (40, 50, 60)
B1_SIZES = (25, 100)
JSON_PATH = "results/theory/pred2/b2_basin.json"
YAML_PATH = "configs/r13_theory_pred2.yaml"
PER_SEED_BANDS = ("band_lockstep", "band_service_2p5s", "band_realized_background_at_peak", "band_raw_time_maximum",
                  "band_raw_lockstep", "band_raw_service_2p5s", "band_raw_realized_background_at_peak")
COMP_AVG = ("primary_calibrated", "band_realized_background_at_peak_calibrated", "band_raw_time_maximum",
            "band_raw_realized_background_at_peak")
REFERENCE = "reference_uninformative_0.5 (not frozen)"


def is_declared(name: str) -> bool:
    """True for the predictors pred2's scoring declaration names (primary, each band, the frozen exchangeable layer, A's labels).
    The composition-averaged column and the P = 0.5 reference are scored after the fact."""
    return not (name.startswith("composition_averaged_") or name == REFERENCE)


def _git_blob(ref: str, path: str) -> bytes:
    return subprocess.run(["git", "show", f"{ref}:{path}"], check=True, capture_output=True).stdout


def _git_commit(ref: str) -> str:
    return subprocess.run(["git", "rev-parse", f"{ref}^{{commit}}"], check=True, capture_output=True, text=True).stdout.strip()


def load_frozen(ref: str, pred_json: Optional[str], pred_yaml: Optional[str]) -> tuple:
    jb = Path(pred_json).read_bytes() if pred_json else _git_blob(ref, JSON_PATH)
    yb = Path(pred_yaml).read_bytes() if pred_yaml else _git_blob(ref, YAML_PATH)
    src = {"json": pred_json or f"{ref}:{JSON_PATH}", "yaml": pred_yaml or f"{ref}:{YAML_PATH}",
           "json_sha256": hashlib.sha256(jb).hexdigest(), "yaml_sha256": hashlib.sha256(yb).hexdigest(),
           "ref": None if (pred_json and pred_yaml) else ref,
           "ref_commit": None if (pred_json and pred_yaml) else _git_commit(ref)}
    return json.loads(jb), yaml.safe_load(yb), src


def predictors(j: Dict[str, Any], b: int, s: int) -> Dict[str, Dict[str, float]]:
    """(p_stuck, p_good) of every frozen predictor for burst size b, seed s."""
    r = j["per_seed"][str(s)][str(b)]
    out = {"primary": {"p_stuck": r["primary"]["p_stuck"], "p_good": r["primary"]["p_good"]}}
    for k in PER_SEED_BANDS:
        out[k] = {"p_stuck": r[k]["p_stuck"], "p_good": r[k]["p_good"]}
    out["band_realized_post_burst_rate"] = {"p_stuck": r["band_realized_post_burst_rate"]["p_stuck"],
                                            "p_good": r["band_realized_post_burst_rate"]["p_good"]}
    ex = {int(round(x["burst"])): x for x in j["exchangeable"]["rows"]}[b]
    out["exchangeable_frozen_layer"] = {"p_stuck": ex["p_stuck"], "p_good": ex["p_good"]}
    for k in COMP_AVG:
        row = j["composition_averaged"][k]["rows"][str(b)]
        out[f"composition_averaged_{k}"] = {"p_stuck": row["p_stuck"], "p_good": row["p_good"]}
    lab = r["level_crossing"]["label"]
    out["level_crossing_deterministic"] = {"p_stuck": float(lab == "STUCK"), "p_good": float(lab == "GOOD")}
    out[REFERENCE] = {"p_stuck": 0.5, "p_good": 0.5}
    return out


def _ll(p: float, y: bool) -> float:
    q = p if y else 1.0 - p
    return math.log(max(q, FLOOR))


def _job_of(run_dir: str) -> Optional[str]:
    try:
        m = json.loads((Path(str(run_dir)) / "meta.json").read_text())
        return (m.get("slurm_env") or {}).get("SLURM_JOB_ID")
    except OSError:
        return None


def per_run_rows(br: pd.DataFrame, j: Dict[str, Any], sizes, set_name: str) -> List[Dict[str, Any]]:
    rows = []
    sel = br[(br["role"] == "new") & br["burst_n"].isin(sizes)].sort_values(["burst_n", "seed"])
    for _, x in sel.iterrows():
        b, s = int(x["burst_n"]), int(x["seed"])
        y_s, y_g = bool(x["stuck"]), bool(x["good"])
        cell = j["per_seed"][str(s)][str(b)]
        for name, p in predictors(j, b, s).items():
            rows.append({"set": set_name, "burst_n": b, "seed": s, "slurm_job_id": _job_of(x["run_dir"]),
                         "run": Path(str(x["run_dir"]).replace("\\", "/")).name, "basin_state": x["basin_state"],
                         "trap_v2_state": x["state"], "hit_eval": x["hit_eval"], "y_stuck": y_s, "y_good": y_g,
                         "b_cal": cell["b_eff_used"]["primary"], "b_eff_raw": cell["cohort"]["b_eff"],
                         "level_crossing_label": cell["level_crossing"]["label"],
                         "lc_peak_live_kv": cell["level_crossing"]["peak_live_kv"], "predictor": name,
                         "declared": is_declared(name),
                         "p_stuck": p["p_stuck"], "p_good": p["p_good"],
                         "brier_stuck": (p["p_stuck"] - y_s) ** 2, "brier_good": (p["p_good"] - y_g) ** 2,
                         "ll_stuck": _ll(p["p_stuck"], y_s), "ll_good": _ll(p["p_good"], y_g)})
    return rows


def summarize(df: pd.DataFrame) -> Dict[str, Any]:
    out = {}
    for name, g in df.groupby("predictor", sort=False):
        out[name] = {"n_runs": int(len(g)), "brier_stuck_mean": float(g["brier_stuck"].mean()),
                     "brier_good_mean": float(g["brier_good"].mean()), "ll_stuck_sum": float(g["ll_stuck"].sum()),
                     "ll_good_sum": float(g["ll_good"].sum()), "expected_stuck": float(g["p_stuck"].sum()),
                     "observed_stuck": int(g["y_stuck"].sum()), "expected_good": float(g["p_good"].sum()),
                     "observed_good": int(g["y_good"].sum())}
    return out


def rule_scores(j: Dict[str, Any], bracketed: bool) -> Dict[str, Any]:
    br = j["bracketing_rule"]
    p = {"primary": br["primary"]["p_rule_independent"]}
    for k in PER_SEED_BANDS:
        p[k] = br[k]["p_rule_independent"]
    p["exchangeable_frozen_layer"] = br["exchangeable_frozen_layer"]["p_rule_independent"]
    p["exchangeable_not_trapped_as_good"] = br["exchangeable_not_trapped_as_good"]["p_rule"]
    for k in COMP_AVG:
        p[f"composition_averaged_{k} (three random seeds; not declared)"] = j["composition_averaged"][k]["p_rule_three_random_seeds"]
    p["level_crossing_deterministic"] = float(bool(br["secondary_level_crossing_deterministic"]["rule_holds"]))
    y = float(bracketed)
    return {"outcome_bracketed": bracketed,
            "by_predictor": {k: {"p_rule": v, "brier": (v - y) ** 2, "log_score": math.log(max(v if bracketed else 1 - v, FLOOR))}
                             for k, v in p.items()}}


def curve_edges(br: pd.DataFrame, crit: Dict[str, float]) -> Dict[str, Any]:
    out = {}
    for s, g in br.groupby("seed"):
        g = g.sort_values("burst_n")
        states = {int(n): st for n, st in zip(g["burst_n"], g["basin_state"])}
        ns = sorted(states)
        seq = [states[n] for n in ns]
        first_stuck = next((n for n in ns if states[n] == "stuck"), None)
        monotone = all(st == "good" for st in seq[:ns.index(first_stuck)]) and all(st == "stuck" for st in seq[ns.index(first_stuck):]) \
            if first_stuck is not None else all(st == "good" for st in seq)
        last_good = max((n for n in ns if states[n] == "good" and (first_stuck is None or n < first_stuck)), default=None)
        lo, hi = last_good, first_stuck
        out[str(int(s))] = {"curve": {str(n): states[n] for n in ns}, "monotone": bool(monotone), "edge_interval": [lo, hi],
                            "contains": {k: (lo is not None and hi is not None and lo < v <= hi) for k, v in crit.items()}}
    return out


def threshold_check(df: pd.DataFrame, thresholds: Dict[str, float]) -> Dict[str, Any]:
    """Descriptive (not a declared score): does one threshold on a per-run statistic separate the observed outcomes?
    b_cal / b_eff_raw: the per-seed calibrated / raw cohort size against b_c; lc_peak_live_kv: the plan's peak live KV (base + burst)
    of A's level crossing against D_live(n_u)."""
    out = {}
    runs = df[df["predictor"] == "primary"]
    for col, b_crit in thresholds.items():
        good, stuck = runs[runs["y_good"]], runs[runs["y_stuck"]]
        gmax, smin = float(good[col].max()), float(stuck[col].min())
        gi, si = good.loc[good[col].idxmax()], stuck.loc[stuck[col].idxmin()]
        out[col] = {"max_over_good": gmax, "max_over_good_run": f"b{int(gi['burst_n'])} seed {int(gi['seed'])}",
                    "min_over_stuck": smin, "min_over_stuck_run": f"b{int(si['burst_n'])} seed {int(si['seed'])}",
                    "separable": gmax < smin, "threshold": b_crit,
                    "calls_matching_threshold": int(((runs[col] >= b_crit) == runs["y_stuck"]).sum()), "n_runs": int(len(runs)),
                    "mismatches_vs_threshold": [f"b{int(r.burst_n)} seed {int(r.seed)} ({col} {getattr(r, col):.2f}, {r.basin_state})"
                                             for r in runs.itertuples() if (getattr(r, col) >= b_crit) != r.y_stuck]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="python experiments/r14_b2_score.py")
    ap.add_argument("--basin-dir", required=True, help="agentload_analysis_basin/<stamp> with basin_runs.csv, basin_verdict.json")
    ap.add_argument("--pred-ref", default="r13-theory-pred2")
    ap.add_argument("--pred-json")
    ap.add_argument("--pred-yaml")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bd, out = Path(a.basin_dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    br = pd.read_csv(bd / "basin_runs.csv")
    verdict = json.loads((bd / "basin_verdict.json").read_text())
    j, yml, src = load_frozen(a.pred_ref, a.pred_json, a.pred_yaml)

    counted = br[(br["role"] == "new") & br["burst_n"].isin(B2_SIZES)]
    if len(counted) != 9 or not counted["b2_counted"].astype(bool).all() or verdict["b2_not_counted"]:
        raise SystemExit("expected nine counted B2 runs and an empty b2_not_counted")

    df = pd.DataFrame(per_run_rows(br, j, B2_SIZES, "B2") + per_run_rows(br, j, B1_SIZES, "B1 (not blind)"))
    b2 = df[df["set"] == "B2"]
    b2_decl, b2_undecl = b2[b2["declared"]], b2[~b2["declared"]]
    crit = {"b_crit_deterministic": j["critical"]["b_crit_deterministic"], "b_committor_50": j["critical"]["b_committor_50"],
            "b_p_stuck_50": j["critical"]["b_p_stuck_50"],
            "composition_averaged_b_p_stuck_50": j["composition_averaged"]["primary_calibrated"]["b_p_stuck_50"]}

    thr = {"b_cal": crit["b_crit_deterministic"], "b_eff_raw": crit["b_crit_deterministic"],
           "lc_peak_live_kv": j["demand_levels"]["D_live_n_u"]}
    prim = b2[b2["predictor"] == "primary"]
    lc = b2[b2["predictor"] == "level_crossing_deterministic"]
    lc_match = int(((lc["level_crossing_label"] == "STUCK") == lc["y_stuck"]).sum())
    stuck_by_seed = {str(s): int(g["y_stuck"].sum()) for s, g in prim.groupby("seed")}
    p40 = {str(int(r.seed)): r.p_stuck for r in prim[prim["burst_n"] == 40].itertuples()}
    edges = curve_edges(br, crit)

    def cell(b, s):
        return prim[(prim["burst_n"] == b) & (prim["seed"] == s)].iloc[0]

    misses = [{"burst_n": int(r.burst_n), "seed": int(r.seed), "p_stuck_primary": r.p_stuck, "p_good_primary": r.p_good,
               "outcome": r.basin_state} for r in prim.itertuples() if (r.p_stuck > 0.5) != r.y_stuck]
    res = {
        "inputs": {"basin_dir": bd.as_posix(), "frozen": src, "floor": FLOOR,
                   "outcome_source": "basin_runs.csv basin_state (registered endpoints); rule: basin_verdict.json b2_bracket"},
        "outcomes": {f"b{int(r.burst_n)}_seed{int(r.seed)}": r.basin_state for r in prim.itertuples()},
        "declared_scores_b2_nine_runs": summarize(b2_decl),
        "rule": rule_scores(j, bool(verdict["b2_bracket"]["bracketed"])),
        "secondary_level_crossing": {"labels": {f"b{int(r.burst_n)}_seed{int(r.seed)}": r.level_crossing_label for r in lc.itertuples()},
                                     "matches": lc_match, "n_runs": int(len(lc))},
        "primary_calls_at_0.5": {"misses": misses, "n_misses": len(misses), "n_runs": int(len(prim))},
        "theory_specific_claims": {
            "1_seed0_most_trap_prone_at_b40_seed2_least": {
                "predicted_p_stuck_b40": p40, "observed_b40": {str(int(r.seed)): r.basin_state for r in prim[prim["burst_n"] == 40].itertuples()},
                "observed_stuck_count_b40_b50_b60_by_seed": stuck_by_seed,
                "observed_edge_by_seed": {s: e["edge_interval"] for s, e in edges.items()},
                "b40_orders_the_seeds": len(set(prim[prim["burst_n"] == 40]["basin_state"])) > 1,
                "seed0_strictly_most_stuck_over_b40_b60": stuck_by_seed["0"] > max(stuck_by_seed["1"], stuck_by_seed["2"]),
                "seed2_strictly_least_stuck_over_b40_b60": stuck_by_seed["2"] < min(stuck_by_seed["0"], stuck_by_seed["1"]),
                "holds": bool(stuck_by_seed["0"] > max(stuck_by_seed["1"], stuck_by_seed["2"])
                              and stuck_by_seed["2"] < min(stuck_by_seed["0"], stuck_by_seed["1"])),
                "note": "operationalized as STUCK counts over b40-b60 per seed (b40 alone cannot order seeds that are all GOOD)"},
            "2_seed2_b40_good_and_b60_stuck": {"b40_seed2": cell(40, 2)["basin_state"], "b60_seed2": cell(60, 2)["basin_state"],
                                               "holds": bool(cell(40, 2)["y_good"] and cell(60, 2)["y_stuck"])},
            "3_p_rule_0.66": {"p_rule": j["bracketing_rule"]["primary"]["p_rule_independent"],
                              "outcome_bracketed": bool(verdict["b2_bracket"]["bracketed"])}},
        "per_seed_edges_vs_frozen_critical_sizes": {"critical": crit, "seeds": edges},
        "not_declared": {
            "scores_b2_nine_runs_not_declared": summarize(b2_undecl),
            "scores_b2_nine_runs_not_declared_note": (
                "frozen numbers scored after the fact: the composition-averaged column is a separate frozen column of pred2's table, "
                "not one of its bands, and pred2's declaration does not list it among the predictors to score; the P = 0.5 "
                "reference is not frozen (Brier 0.25 for any outcome), for scale only"),
            "b1_sizes_not_blind": summarize(df[df["set"] != "B2"]),
            "b1_sizes_not_blind_note": (
                "pred2 was pushed at 04:20:20 CDT, after the BASIN-1 outcomes were first read at about 04:07 CDT, so its rows for "
                "n = 25 and 100 are not blind; by pred2's own record (b2_basin.json created 04:01:24) its drivers read no B1 result"),
            "cohort_size_threshold_b2": threshold_check(b2, thr),
            "cohort_size_threshold_b2_and_b1": threshold_check(df, thr)},
        "yaml_crosscheck": {"b2.bracketing_rule.primary.p_rule": yml["b2"]["bracketing_rule"]["primary"]["p_rule"],
                            "b2.bracketing_rule.exchangeable_frozen_layer.p_rule": yml["b2"]["bracketing_rule"]["exchangeable_frozen_layer"]["p_rule"],
                            "b2.critical": yml["b2"]["critical"]},
    }
    df.to_csv(out / "b2_scoring.csv", index=False, lineterminator="\n")
    (out / "b2_scoring.json").write_text(json.dumps(res, indent=1, default=float) + "\n", newline="\n")

    pd.set_option("display.width", 250)
    cols = ["n_runs", "brier_stuck_mean", "brier_good_mean", "ll_stuck_sum", "ll_good_sum", "expected_stuck", "observed_stuck"]
    print("declared:")
    print(pd.DataFrame(res["declared_scores_b2_nine_runs"]).T[cols].round(4).to_string())
    print("not declared (scored after the fact):")
    print(pd.DataFrame(res["not_declared"]["scores_b2_nine_runs_not_declared"]).T[cols].round(4).to_string())
    print(json.dumps({k: res[k] for k in ("rule", "secondary_level_crossing", "primary_calls_at_0.5", "theory_specific_claims",
                                          "per_seed_edges_vs_frozen_critical_sizes")}, indent=1, default=float))
    print(json.dumps(res["not_declared"]["cohort_size_threshold_b2"], indent=1, default=float))
    print(json.dumps(res["not_declared"]["cohort_size_threshold_b2_and_b1"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
