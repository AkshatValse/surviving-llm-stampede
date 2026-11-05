"""Round 11 B1 / E0F: derived, DESCRIPTIVE numbers for the paper (not part of any registered rule).

Written 2026-10-31 after the B1 and E0F runs were pulled (jobs 17168500-17168507). The registered B1 verdict is
``analysis.basin classify``; the E0F stability calls are ``analysis.summarize stable``. This script only adds:

* ``e0f_realized_rates.csv``: per E0F run (and the committed seed-0 E0b runs, jobs 17084750-55) the realized base arrival
  rate = base sessions in plan.csv / configured duration, and its multiple of lambda_ref, next to the stable call of the
  given stable_runs.csv files. The frozen endpoint file names analysis/seed_effects.py for this; that module does not exist
  in the repository, so the same quantity is computed here exactly as experiments/r11_predict_basin.py defines it
  (n_base / duration_s / lambda_ref).
* ``b1_time_course_descriptive.csv``: per B1 run, 100 s windows by completion time, hit = cached / prompt tokens > 0.5 over ok
  turns: the pre-burst hit (1100-1200 s), the lowest window hit in [1200, 5700) s and when it occurred, the first later
  window back above 0.8, and the first window from which every later window has hit < 0.2 ("stuck onset").

Usage: python -m analysis.r11_b1_e0f_derived <pulled dir> <stable_runs.csv> [<stable_runs.csv> ...] --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

LAMBDA_REF = 0.07153402100919228   # prereg measured.lambda_ref (configs/r11_basin_predict.yaml e0f.lambda_ref)


def _run_dir(path: str, roots: list[Path]) -> Path:
    p = Path(str(path).replace("\\", "/"))
    if p.is_dir():
        return p
    for r in roots:
        if (r / p).is_dir():
            return r / p
    raise FileNotFoundError(path)


def realized_rates(stable_csvs: list[Path], roots: list[Path]) -> pd.DataFrame:
    rows = []
    for f in stable_csvs:
        for _, s in pd.read_csv(f).iterrows():
            d = _run_dir(s["run_dir"], roots)
            plan, meta = pd.read_csv(d / "plan.csv"), json.loads((d / "meta.json").read_text())
            n_base, dur = int((plan["origin"] == "base").sum()), float(meta["duration_s_configured"])
            rows.append({"label": s["label"], "seed": int(s["seed"]), "rate_mult": float(s["rate_mult"]), "stable": bool(s["stable"]),
                         "final_queue": s["final_queue"], "trend_rise": s["trend_rise"], "aborted": s["aborted"],
                         "n_base": n_base, "duration_s": dur, "realized_base_rate": n_base / dur,
                         "realized_base_mult": n_base / dur / LAMBDA_REF,
                         "resolved_rate": meta.get("resolved_rate_sessions_per_s"),
                         "slurm_job_id": (meta.get("slurm_env") or {}).get("SLURM_JOB_ID"),
                         "stable_runs_csv": f.as_posix(), "run_dir": d.as_posix()})
    return pd.DataFrame(rows).sort_values(["realized_base_mult"]).reset_index(drop=True)


def time_course(pulled: Path) -> pd.DataFrame:
    rows = []
    for d in sorted((pulled / "results/agentload_e2_burst").iterdir()):
        meta = json.loads((d / "meta.json").read_text())
        b = ((yaml.safe_load((d / "config.yaml").read_text()).get("arrivals") or {}).get("burst") or {})
        r = pd.read_csv(d / "requests.csv", usecols=["status", "t_complete", "prompt_tokens", "cached_tokens"])
        r = r[r["status"] == "ok"].copy()
        r["hit"] = (r["cached_tokens"] / r["prompt_tokens"]) > 0.5
        g = r.groupby((r["t_complete"] // 100).astype(int))["hit"].mean()
        post = g[g.index >= 12]
        onset = next((int(w) * 100 for w in post.index if (post.loc[w:] < 0.2).all()), None)
        dip = post[post.index < 57]
        w_min = int(dip.idxmin()) * 100
        back = post[(post.index * 100 > w_min) & (post > 0.8)]
        rows.append({"run": d.name, "slurm_job_id": (meta.get("slurm_env") or {}).get("SLURM_JOB_ID"), "burst_n": b.get("n"),
                     "seed": meta["seeds"][0], "hit_pre_burst_1100_1200": float(g.loc[11]) if 11 in g.index else np.nan,
                     "min_hit_100s_1200_5700": float(dip.min()), "t_min_hit_s": w_min,
                     "first_window_hit_gt_0.8_after_min_s": int(back.index.min()) * 100 if len(back) else None,
                     "stuck_onset_window_s": onset})
    return pd.DataFrame(rows).sort_values(["burst_n", "seed"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r11_b1_e0f_derived")
    ap.add_argument("pulled")
    ap.add_argument("stable_csvs", nargs="+")
    ap.add_argument("--root", action="append", default=[], help="dirs that relative run_dir entries resolve against")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rr = realized_rates([Path(f) for f in a.stable_csvs], [Path(x) for x in a.root])
    rr.to_csv(out / "e0f_realized_rates.csv", index=False)
    tc = time_course(Path(a.pulled))
    tc.to_csv(out / "b1_time_course_descriptive.csv", index=False)
    pd.set_option("display.width", 250)
    print(rr.drop(columns=["run_dir", "stable_runs_csv"]).to_string())
    print(tc.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
