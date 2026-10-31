"""r14 B2 (BASIN-2): derived, DESCRIPTIVE numbers for the paper (not part of the registered rule).

Written 2026-10-31 after the B2 runs (jobs 17169893-17169901) were pulled and classified. The registered B2 verdict is
``analysis.basin classify`` (basin_runs.csv / basin_verdict.json). This script only adds a 100 s time course of the nine B2 runs,
with the same definitions as the B1 time course (``analysis.r11_b1_e0f_derived.time_course``, reused unchanged): 100 s windows by
completion time, hit = cached / prompt tokens > 0.5 over ok turns.

Outputs (in --out):
* ``b2_time_course_descriptive.csv``: one row per B2 run: the pre-burst hit (1100-1200 s), the lowest 100 s window hit in
  [1200, 5700) s and its window start, the first later window back above 0.8, the first window from which every later window
  has hit < 0.2 ("stuck onset"), and, from the registered basin_runs.csv, the run's basin_state and hit_eval, the hit_eval of
  the n = 0 run of the same seed and the difference; max_inflight_seen from the run's meta.json; and, for reference, the same
  seed's n = 0 run's lowest 100 s window hit in [1200, 5700) s, its window start, and its max_inflight_seen; per run, the number of
  ok burst-session turns, the completion time of the last one and how many of them complete inside W = [5700, 8700) s.
* ``b2_time_course_windows.csv``: the per-window series behind it (run, burst_n, seed, window_start_s, ok_turns, hit), for the
  nine B2 runs and the three n = 0 runs (burst_n 0).

Usage: PYTHONPATH="src;." python experiments/r14_b2_derived.py <pulled dir> <basin_runs.csv> --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from analysis.r11_b1_e0f_derived import time_course


def windows(run_dirs: Iterable[Path]) -> pd.DataFrame:
    """The 100 s window series that time_course() summarizes (same definitions, kept in long form)."""
    rows = []
    for d in run_dirs:
        meta = json.loads((d / "meta.json").read_text())
        r = pd.read_csv(d / "requests.csv", usecols=["status", "t_complete", "prompt_tokens", "cached_tokens"])
        r = r[r["status"] == "ok"].copy()
        r["hit"] = (r["cached_tokens"] / r["prompt_tokens"]) > 0.5
        g = r.groupby((r["t_complete"] // 100).astype(int))["hit"].agg(["size", "mean"])
        for w, (cnt, h) in g.iterrows():
            rows.append({"run": d.name, "seed": meta["seeds"][0], "window_start_s": int(w) * 100, "ok_turns": int(cnt),
                         "hit": float(h)})
    return pd.DataFrame(rows)


def _max_inflight(d: Path) -> int:
    return json.loads((d / "meta.json").read_text())["outcome"]["max_inflight_seen"]


def main() -> int:
    ap = argparse.ArgumentParser(prog="python experiments/r14_b2_derived.py")
    ap.add_argument("pulled")
    ap.add_argument("basin_runs")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pulled, out = Path(a.pulled), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tc = time_course(pulled)
    br = pd.read_csv(a.basin_runs)
    br["path"] = br["run_dir"].astype(str).str.replace("\\", "/", regex=False).str.rstrip("/")
    br["run"] = br["path"].str.split("/").str[-1]
    base0 = br[(br["role"] == "baseline") & (br["burst_n"] == 0)].set_index("seed")
    b2 = br[br["burst_n"].isin([40, 50, 60]) & (br["role"] == "new")].set_index("run")
    if set(b2.index) != set(tc["run"]):
        raise SystemExit(f"run sets differ: basin_runs {sorted(b2.index)} vs pulled {sorted(tc['run'])}")
    tc["basin_state"] = tc["run"].map(b2["basin_state"])
    tc["trap_v2_state"] = tc["run"].map(b2["state"])
    tc["hit_eval"] = tc["run"].map(b2["hit_eval"])
    tc["hit_eval_n0_same_seed"] = tc["seed"].map(base0["hit_eval"])
    tc["hit_eval_minus_n0"] = tc["hit_eval"] - tc["hit_eval_n0_same_seed"]
    tc["max_inflight_seen"] = [_max_inflight(pulled / "results/agentload_e2_burst" / r) for r in tc["run"]]
    last = {}
    for r in tc["run"]:
        q = pd.read_csv(pulled / "results/agentload_e2_burst" / r / "requests.csv", usecols=["origin", "status", "t_complete"])
        q = q[(q["origin"] == "burst") & (q["status"] == "ok")]
        last[r] = (len(q), float(q["t_complete"].max()), int(((q["t_complete"] >= 5700) & (q["t_complete"] < 8700)).sum()))
    tc["burst_ok_turns"] = tc["run"].map({r: v[0] for r, v in last.items()})
    tc["last_burst_ok_turn_complete_s"] = tc["run"].map({r: v[1] for r, v in last.items()})
    tc["burst_ok_turns_in_W"] = tc["run"].map({r: v[2] for r, v in last.items()})

    n0_dirs = {int(s): Path(p) for s, p in base0["path"].items()}
    w0 = windows(n0_dirs[s] for s in sorted(n0_dirs))
    dip0 = w0[(w0["window_start_s"] >= 1200) & (w0["window_start_s"] < 5700)]
    lo = dip0.loc[dip0.groupby("seed")["hit"].idxmin()].set_index("seed")
    tc["n0_run"] = tc["seed"].map({s: d.name for s, d in n0_dirs.items()})
    tc["n0_min_hit_100s_1200_5700"] = tc["seed"].map(lo["hit"])
    tc["n0_t_min_hit_s"] = tc["seed"].map(lo["window_start_s"])
    tc["n0_max_inflight_seen"] = tc["seed"].map({s: _max_inflight(d) for s, d in n0_dirs.items()})
    tc.to_csv(out / "b2_time_course_descriptive.csv", index=False, lineterminator="\n")

    w = windows(sorted((pulled / "results/agentload_e2_burst").iterdir()))
    w["burst_n"] = w["run"].map(tc.set_index("run")["burst_n"])
    w0["burst_n"] = 0
    w = pd.concat([w0, w], ignore_index=True)
    w = w[["run", "burst_n", "seed", "window_start_s", "ok_turns", "hit"]].sort_values(["burst_n", "seed", "window_start_s"])
    w.to_csv(out / "b2_time_course_windows.csv", index=False, lineterminator="\n")

    pd.set_option("display.width", 250)
    print(tc.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
