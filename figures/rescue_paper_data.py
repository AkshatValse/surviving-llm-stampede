"""Descriptive tables and figure data for the rescue cells R1 / R4 (POST HOC, not part of the registered verdict).

Reads the registered verdict outputs of ``python -m analysis.rescue verdict`` (rescue_runs.csv, rescue_trace.csv) and the
committed run dirs, and writes into a new result dir:

  persistence.csv     per rescue run: the post-release interval [t_rel + 300, 8700) of the rescue run and, over the SAME
                      interval, its same-seed BURST and NOBURST controls (FU-hit, mean outstanding, engine latency), plus the
                      RECOVERED-predicate quantities over the last 300 s (hit, outstanding) and the uncapped run's maximum
                      in-system count after the release and the share of post-release time at or above the cap.
  costs.csv           user-facing costs (analysis.rescue.user_costs, the verdict's own cost function) of every arm: rescue,
                      BURST, NOBURST and the E2 CAPPED arm (static cap from t = 0) of the same seed and rate, with FU-hit over
                      [t_on, 8700) and RECOVERED at the end for each.
  costs_summary.csv   per rate and arm: mean and [min, max] over the three seeds of the main cost columns.
  trace_aligned.csv   the verdict's 60-s trace bins (all arms) with the rescue run's t_engage / t_rel of the same seed and
                      rate, and t - t_engage, t - t_rel (figure 'trap, rescue, release, persist').
  trace_median.csv    per rate, arm and 60-s bin: the median over seeds of FU-hit and outstanding (t absolute), and, for the
                      rescue arm, the same aligned on t - t_rel (60-s bins of t - t_rel).

  python figures/rescue_paper_data.py --verdict-dirs DIR [DIR ...] --capped-runs RUN [...] --out-root DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent.parent / "src")]

from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta  # noqa: E402
from analysis import rescue as R  # noqa: E402
from analysis.load import load_run  # noqa: E402
from analysis.params import load_params  # noqa: E402


def _norm(p: str) -> str:
    return str(Path(str(p).replace("\\", "/")))


def fu_and_end(run, t0, t1, p):
    fu = R.FollowUps(run, float(R.RULE["fu_cached_frac_threshold"]))
    out = R.outstanding_step(run, R.pause_intervals(run, None))
    h, n = fu.hit(t0, t1)
    rend = R.recovered_end(run, p, out)
    ok = run.requests[(run.requests["status"] == "ok") & (run.requests["t_complete"] >= t0) & (run.requests["t_complete"] < t1)]
    return {"fu_hit": h, "fu_n": n, "outstanding_mean": out.mean(t0, t1),
            "engine_latency_mean_s": float(ok["latency_s"].mean()) if len(ok) else np.nan,
            "hit_end": rend["hit_end"], "outstanding_end": rend["outstanding_end"], "recovered_end": rend["recovered"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict-dirs", nargs="+", required=True)
    ap.add_argument("--capped-runs", nargs="*", default=[])
    ap.add_argument("--params", default=R.DEFAULT_PARAMS)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--name", default="rescue_paper_data")
    a = ap.parse_args(argv)
    p = load_params(a.params)
    git = git_info(Path(a.params).resolve().parent.parent)
    t_start = datetime.now()

    capped = {}
    for d in a.capped_runs:
        c = load_run(d)
        capped[(c.label, round(float(c.rate_mult), 9), int(c.seed))] = c

    pers, costs, traces = [], [], []
    for vd in a.verdict_dirs:
        vd = Path(vd)
        doc = json.loads((vd / "rescue_verdict.json").read_text())
        prof = R.PROFILES[doc["profile"]]
        H, t_on, tb = float(prof["horizon_s"]), float(prof["t_on_s"]), float(prof["t_burst_s"])
        runs = pd.read_csv(vd / "rescue_runs.csv")
        tr = pd.read_csv(vd / "rescue_trace.csv")
        for _, r in runs.iterrows():
            m, s = float(r["rate_mult"]), int(r["seed"])
            t_rel, t_eng = float(r["t_release"]), float(r["t_engage"])
            a0 = t_rel + float(R.RULE["post_start_after_release_s"])
            arms = {"rescue": R.load_rescue_run(_norm(r["run_dir"])),
                    "burst": (load_run(_norm(r["burst_control_dir"])), None),
                    "noburst": (load_run(_norm(r["noburst_control_dir"])), None)}
            cp = capped.get((prof["control_label"], round(m, 9), s))
            if cp is not None:
                arms["capped"] = (cp, None)
            row = {"profile": doc["profile"], "rate_mult": m, "seed": s, "t_engage": t_eng, "t_release": t_rel,
                   "post_t0": a0, "post_t1": H, "post_release_max_active": r["post_release_max_active"],
                   "post_release_frac_active_ge_cap": r["post_release_frac_active_ge_cap"], "n_cap": r["n_cap"],
                   "t_cap_last_binding": r["t_cap_last_binding"], "t_recovered": r["t_recovered"],
                   "rescue_outcome": r["outcome"]}
            for arm in ("rescue", "burst", "noburst"):
                run, ev = arms[arm]
                x = fu_and_end(run, a0, H, p)
                if arm == "rescue":   # outstanding with the pause intervals (none after release, but exact)
                    x["outstanding_mean"] = R.outstanding_step(run, R.pause_intervals(run, ev)).mean(a0, H)
                for k, v in x.items():
                    row[f"{arm}_{k}"] = v
                row[f"{arm}_sessions_unfinished_at_end"] = int((run.sessions["status"].astype(str) == "cancelled").sum())
            pers.append(row)
            for arm, (run, ev) in arms.items():
                c = R.user_costs(run, t_on=t_on, t_burst=tb, horizon=H)
                x = fu_and_end(run, t_on, H, p)
                costs.append({"profile": doc["profile"], "rate_mult": m, "seed": s, "arm": arm, "run_dir": str(run.dir),
                              "label": run.label, "fu_hit_after_t_on": x["fu_hit"], "recovered_end": x["recovered_end"],
                              "hit_end": x["hit_end"], "outstanding_end": x["outstanding_end"], **c})
            sel = tr[np.isclose(tr["rate_mult"].astype(float), m) & (tr["seed"].astype(int) == s)].copy()
            sel["profile"] = doc["profile"]
            sel["t_mid"] = sel["t_start"] + R.TRACE_BIN_S / 2
            sel["t_engage"], sel["t_release"] = t_eng, t_rel
            sel["t_minus_engage"] = sel["t_mid"] - t_eng
            sel["t_minus_release"] = sel["t_mid"] - t_rel
            traces.append(sel.drop(columns=["run_dir"]))

    pers_df, cost_df = pd.DataFrame(pers), pd.DataFrame(costs)
    tr_df = pd.concat(traces, ignore_index=True)
    cols = ["sessions_started", "sessions_completed", "completed_frac", "sessions_unfinished", "sessions_failed",
            "sessions_paused", "pause_s_per_session", "pause_s_per_paused_session", "pause_s_max", "sessions_gated",
            "gate_wait_s_per_session", "gate_wait_s_per_gated_session", "gate_wait_s_max", "pause_hours", "gate_wait_hours",
            "delay_session_hours", "sessions_delayed_gt_60s", "sessions_delayed_gt_300s", "sessions_delayed_gt_600s",
            "request_wait_hours", "wait_hours_total", "engine_latency_mean_s_after_t_on", "session_duration_median_s",
            "cohort_completed_frac", "cohort_duration_median_s", "fu_hit_after_t_on", "outstanding_end"]
    summ = []
    for (prof, m, arm), g in cost_df.groupby(["profile", "rate_mult", "arm"], sort=False):
        row = {"profile": prof, "rate_mult": m, "arm": arm, "n_seeds": len(g), "n_recovered_end": int(g["recovered_end"].sum())}
        for c in cols:
            v = pd.to_numeric(g[c], errors="coerce")
            row[f"{c}_mean"], row[f"{c}_min"], row[f"{c}_max"] = v.mean(), v.min(), v.max()
        summ.append(row)
    med = (tr_df.groupby(["profile", "rate_mult", "arm", "t_start"])
           .agg(fu_hit_median=("fu_hit", "median"), outstanding_median=("outstanding_mean", "median"),
                gated_median=("gated_mean", "median"), paused_median=("paused_mean", "median"), n=("seed", "count"))
           .reset_index())
    resc = tr_df[tr_df["arm"] == "rescue"].copy()
    resc["rel_bin"] = np.floor(resc["t_minus_release"] / R.TRACE_BIN_S) * R.TRACE_BIN_S
    med_rel = (resc.groupby(["profile", "rate_mult", "rel_bin"])
               .agg(fu_hit_median=("fu_hit", "median"), outstanding_median=("outstanding_mean", "median"), n=("seed", "count"))
               .reset_index())

    out = new_result_dir(a.out_root, a.name)
    pers_df.to_csv(out / "persistence.csv", index=False)
    cost_df.to_csv(out / "costs.csv", index=False)
    pd.DataFrame(summ).to_csv(out / "costs_summary.csv", index=False)
    tr_df.to_csv(out / "trace_aligned.csv", index=False)
    med.to_csv(out / "trace_median.csv", index=False)
    med_rel.to_csv(out / "trace_median_rel_release.csv", index=False)
    meta = build_meta(experiment="rescue_paper_data", argv=[sys.executable, __file__, *(argv or sys.argv[1:])], seeds=[],
                      hardware=default_hardware(), git=git, t_start=t_start, t_end=datetime.now(),
                      extra={"inputs": [*a.verdict_dirs, *a.capped_runs], "post_hoc": True,
                             "note": "descriptive tables; the registered verdict is rescue_verdict.json in the input dirs"},
                      status="finished")
    write_meta(out, meta)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
