"""Round 7 real-trace runs: POST-HOC diagnostics of the paired-arm stage (read off the finished stage result dirs, no simulation).

    python -m prefixmeta.r7_posthoc --spec configs/r7_traces_sim.yaml [--out-root results/r7_traces_sim]     -> <out-root>/r7_posthoc/<ts>/{posthoc.md, summary.json, meta.json}

NOT part of the declared verdicts of the spec: it explains the verdicts that the declared rules produced. Two tables.

1. Per tested point: what the CAPPED arm did apart from the declared RECOVERED test (hit > 0.8 AND mean backlog < 20 over the evaluation window), and a back-of-the-envelope
   drain time. A CAPPED run can fail RECOVERED while the cache has recovered, if the burst backlog has not drained by the end of the run. Estimate (arithmetic on two
   measured numbers, not a simulation): with a standing backlog the gated system runs at its cap n, so it completes mu(cap) sessions/s (the closed-curve value of the
   curves stage, turns-based) while lambda keep arriving; a burst of B sessions then drains in B / (mu(cap) - lambda) seconds. RECOVERED needs mean backlog < 20 over
   [t_burst + 5000, t_burst + 7500].
2. NOBURST runs that are not RECOVERED: when the first window with backlog above 50 and the first window after t_burst with hit rate below 0.2 end (the definitions of the
   round-7 spec's horizon block, thresholds copied: 50, 0.2), against the horizon of the from-empty edge stage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from .mech_runner import begin, finish
from .probe import load_probe_config
from .r6_predict import df_md
from .r7_report import Stages, fs
from .r7_robustness import run_events

EVENT_THRESHOLDS = {"collapse_backlog_above": 50.0, "trap_hit_below": 0.2, "release_hit_above": 0.5}      # the horizon block of configs/r7_robustness.yaml


def drain_time_s(burst_n: float, mu_cap: float, lam: float) -> float:
    """B / (mu(cap) - lambda) seconds; inf if the capped system cannot serve more than lambda."""
    return float(burst_n) / (mu_cap - lam) if mu_cap > lam else float("inf")


def capped_table(S: Stages, r7: dict, z: float) -> pd.DataFrame:
    cur = S.summary("curves")["workloads"]
    pr = S.summary("pairs")["workloads"]
    cl = S.csv("pairs", "classified_runs.csv")
    burst_n = float(r7["pairs"]["burst_n"])
    eval_from = float(r7["classify"]["eval_window_rel_to_burst_s"][0])
    rows = []
    for name, w in pr.items():
        if w["window_empty"]:
            continue
        for mult, p in w["points"].items():
            g = cl[(cl["workload"] == name) & (np.isclose(cl["mult"], float(mult)))]
            c, nb = g[g["arm"] == "burst_cap"], g[g["arm"] == "no_burst"]
            n = len(c)
            mu_cap = float(cur[name]["mu_turns_by_n"][str(int(w["cap_n"]))])
            lam = float(p["lam"])
            rows.append({"workload": w["label"], "x lambda_miss": float(mult), "lambda (sessions/s)": lam, "cap n": int(w["cap_n"]), "mu(cap) (sessions/s)": mu_cap,
                         "[estimate] drain time of the burst (s)": drain_time_s(burst_n, mu_cap, lam), "[estimate] / eval window start (%g s)" % eval_from:
                         drain_time_s(burst_n, mu_cap, lam) / eval_from,
                         "CAPPED recovered (declared)": fs(int(c["recovered"].sum()), n, z), "CAPPED hit > 0.8 (hit only)": fs(int((c["hit"] > 0.8).sum()), n, z),
                         "CAPPED hit (mean)": c["hit"].mean(), "CAPPED backlog (mean over seeds)": c["backlog"].mean(), "CAPPED backlog slope < 0": fs(int((c["slope"] < 0).sum()), n, z),
                         "NOBURST recovered (declared)": fs(int(nb["recovered"].sum()), len(nb), z), "NOBURST trapped": fs(int(nb["trapped"].sum()), len(nb), z)})
    return pd.DataFrame(rows)


def noburst_events(S: Stages, r7: dict) -> pd.DataFrame:
    pr = S.summary("pairs")["workloads"]
    cl = S.csv("pairs", "classified_runs.csv")
    win = S.csv("pairs", "windows.csv")
    t_burst = float(r7["pairs"]["warmup_s"])
    rows = []
    for name, w in pr.items():
        if w["window_empty"]:
            continue
        for mult in w["points"]:
            g = cl[(cl["workload"] == name) & (np.isclose(cl["mult"], float(mult))) & (cl["arm"] == "no_burst") & (cl["label"] != "RECOVERED")]
            for _, r in g.sort_values("seed").iterrows():
                ww = win[(win["call"] == r["call"]) & (win["run_id"] == r["run_id"])]
                ev = run_events(ww, t_burst, EVENT_THRESHOLDS)
                rows.append({"workload": w["label"], "x lambda_miss": float(mult), "seed": int(r["seed"]), "label": r["label"], "first window with backlog > 50 ends (s)": ev["collapse_s"],
                             "first window after t_burst with hit < 0.2 ends (s)": ev["trap_onset_s"], "final backlog": ev["final_backlog"], "final hit": ev["final_hit"]})
    return pd.DataFrame(rows)


def build(S: Stages, r7: dict) -> str:
    z = float(r7["wilson_z"])
    edge_h = float(r7["edge"]["horizon_s"])
    pair_h = float(r7["pairs"]["warmup_s"]) + float(r7["pairs"]["after_s"])
    ct = capped_table(S, r7, z)
    ne = noburst_events(S, r7)
    out = ["### P1. CAPPED and NOBURST arms beyond the declared test (POST-HOC, not part of the verdicts)\n",
           "The estimate column is arithmetic on two measured numbers (see the module docstring), not a simulation. `CAPPED hit > 0.8` ignores the backlog condition of "
           "RECOVERED; the declared verdict is the `recovered (declared)` columns.\n", df_md(ct, "{:.4g}") if len(ct) else "(no point was tested)", "",
           f"### P2. NOBURST runs that are not RECOVERED (POST-HOC): when did they collapse? (edge stage horizon {edge_h:g} s, paired runs {pair_h:g} s)\n",
           df_md(ne, "{:.4g}") if len(ne) else "(every NOBURST run of every tested point was RECOVERED)", ""]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round 7 real-trace runs: post-hoc diagnostics of the paired-arm stage")
    ap.add_argument("--spec", "--config", dest="config", required=True)
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[])
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> Path:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    cfg = load_probe_config(args.config, repo_dir)
    r7 = cfg["r7"]
    S = Stages(args.out_root, r7.get("stages"))
    if not (S.ok("pairs") and S.ok("curves")):
        raise SystemExit("the post-hoc tables need the stages 'curves' and 'pairs' in the manifest of --out-root")
    cfg_eff = {k: v for k, v in cfg.items() if k != "preregistration_file"}
    ctx = begin("r7_posthoc", "r7_posthoc", cfg_eff, cfg_eff, args, repo_dir)
    text = build(S, r7)
    (ctx.out / "posthoc.md").write_text(text, encoding="utf-8")
    ct = capped_table(S, r7, float(r7["wilson_z"]))
    ne = noburst_events(S, r7)
    (ctx.out / "summary.json").write_text(json.dumps({"capped": ct.to_dict(orient="records"), "noburst_not_recovered": ne.to_dict(orient="records"),
                                                      "inputs": {s: S.dir[s].as_posix() for s in ("curves", "pairs")}}, indent=2, default=float))
    finish(ctx, [], {"stage": "posthoc", "stage_dirs": {s: S.dir[s].as_posix() for s in ("curves", "pairs")}})
    print(text)
    print("result dir:", ctx.out)
    return ctx.out


if __name__ == "__main__":      # pragma: no cover
    main()
    sys.exit(0)
