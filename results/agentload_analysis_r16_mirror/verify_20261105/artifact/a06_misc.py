"""Misc artifact checks: plan.csv vs the tagged frozen plans; client start lag (t_first_send - arrival_s); client scrape
latency; BURST vs NOBURST pre-burst pairing; base sessions' fate in BURST runs; the late window's served-turn composition.

Usage: python -I a06_misc.py WORKTREE OUTDIR
"""
import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

WT = sys.argv[1]
OUT = sys.argv[2]
PULL = os.path.join(WT, "results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst")
RUNS = ["20261105-145227", "20261105-145244-2", "20261105-145240", "20261105-145244-1", "20261105-145246", "20261105-145244",
        "20261105-145242", "20261105-145247", "20261105-145248"]
LAM_REF = 0.07153402100919228


def tagged_plan(arm, mult, seed):
    rel = f"results/theory/r16/mirror_plans/{arm}_{mult}_seed{seed}.csv"
    txt = subprocess.run(["git", "-C", WT, "show", f"r16-mirror-reg:{rel}"], capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(txt))


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", lambda x: f"{x:.4g}")
    for r in RUNS:
        d = os.path.join(PULL, r)
        meta = json.load(open(os.path.join(d, "meta.json")))
        mult = round(meta["resolved_rate_sessions_per_s"] / LAM_REF, 2)
        arm, seed = meta["arm"], meta["seeds"][0]
        tag = f"{mult}x-{arm}-s{seed}"
        plan = pd.read_csv(os.path.join(d, "plan.csv"))
        fz = tagged_plan(arm, f"{mult:.2f}", seed)
        same_cols = list(plan.columns) == list(fz.columns)
        exact = same_cols and len(plan) == len(fz) and all((plan[c] == fz[c]).all() for c in ["sid", "origin", "idx", "n_turns"])
        dmax = max(float((plan.arrival_s - fz.arrival_s).abs().max()), float((plan.tool_time_total_s - fz.tool_time_total_s).abs().max())) if exact else None
        ses = pd.read_csv(os.path.join(d, "sessions.csv"))
        lag = (ses.t_first_send - ses.arrival_s)
        m = pd.read_csv(os.path.join(d, "metrics.csv"), keep_default_na=False)
        sl = pd.to_numeric(m[m.name == "agentload:scrape_latency_s"].value, errors="coerce")
        print(f"{tag}: plan==tagged frozen plan: {exact} (rows {len(plan)}/{len(fz)}, max |dt| {dmax}); "
              f"session start lag max {lag.max():.4f} s p99 {lag.quantile(0.99):.4f}; scrape latency median {sl.median():.4f} max {sl.max():.3f} s")
        if arm == "burst":
            # base sessions that arrived before the burst: did they all finish, and when?
            pre = ses[(ses.origin == "base") & (ses.arrival_s < 1200)]
            print(f"    pre-burst base sessions: {len(pre)}, completed {int((pre.status == 'completed').sum())}, "
                  f"completed after 2400 s: {int(((pre.status == 'completed') & (pre.t_end >= 2400)).sum())}, "
                  f"last t_end {pre.t_end.max():.0f}")
            req = pd.read_csv(os.path.join(d, "requests.csv"), usecols=["sid", "origin", "turn", "t_complete", "status"])
            ok = req[(req.status == "ok") & (req.t_complete >= 6600) & (req.t_complete < 8700)]
            vc = ok.turn.value_counts().sort_index()
            print(f"    late window [6600,8700): {len(ok)} turns served; share that were turn 20: {(ok.turn == 20).mean():.4f} "
                  f"(1/20 = 0.05); mean turn index {ok.turn.mean():.2f}; share turn<=5: {(ok.turn <= 5).mean():.3f}")


if __name__ == "__main__":
    main()
