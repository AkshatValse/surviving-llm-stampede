"""Burst cohort: turn counts, t_end distribution (the wave), turns completed by 3000 s, lock-step progress per turn, and the
composition of the blackout and wave completions; hit fraction in 300-s bins (BURST and NOBURST).

Usage: python -I a04_cohort.py WORKTREE OUTDIR
"""
import json
import os
import sys

import numpy as np
import pandas as pd

WT = sys.argv[1]
OUT = sys.argv[2]
PULL = os.path.join(WT, "results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst")
RUNS = ["20261105-145227", "20261105-145244-2", "20261105-145240", "20261105-145244-1", "20261105-145246", "20261105-145244",
        "20261105-145242", "20261105-145247", "20261105-145248"]
LAM_REF = 0.07153402100919228


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.float_format", lambda x: f"{x:.4g}")
    hit_tab = {}
    comp_tab = {}
    for r in RUNS:
        d = os.path.join(PULL, r)
        meta = json.load(open(os.path.join(d, "meta.json")))
        tag = f"{round(meta['resolved_rate_sessions_per_s'] / LAM_REF, 2)}x-{meta['arm']}-s{meta['seeds'][0]}"
        req = pd.read_csv(os.path.join(d, "requests.csv"),
                          usecols=["sid", "origin", "turn", "n_turns", "t_send", "t_complete", "status", "prompt_tokens",
                                   "cached_tokens", "latency_s", "t_ready", "t_planned"])
        ses = pd.read_csv(os.path.join(d, "sessions.csv"))
        plan = pd.read_csv(os.path.join(d, "plan.csv"))
        ok = req[req.status == "ok"].copy()
        ok["hit"] = (ok.cached_tokens / ok.prompt_tokens) > 0.5
        # --- hit fraction, 300-s bins
        ok["b300"] = (ok.t_complete // 300 * 300).astype(int)
        hit_tab[tag] = ok.groupby("b300").hit.mean().reindex(range(0, 8700, 300))
        comp = ses[ses.status == "completed"].copy()
        comp["b300"] = (comp.t_end // 300 * 300).astype(int)
        comp_tab[tag] = comp.groupby("b300").size().reindex(range(0, 8700, 300)).fillna(0) / 300 / LAM_REF

        # --- consistency sessions vs requests: completed sessions end at their last turn's completion
        last = ok.sort_values("turn").groupby("sid").tail(1).set_index("sid")
        cs = comp.set_index("sid")
        j = cs.join(last[["turn", "t_complete"]], how="left")
        mism_turns = int((j.turns_completed != j.n_turns).sum())
        mism_last = int((j.turn != j.n_turns).sum())
        dt_end = (j.t_end - j.t_complete).abs()
        # sessions planned vs started; plan n_turns vs sessions n_turns
        pj = ses.set_index("sid")[["n_turns"]].join(plan.set_index("sid")[["n_turns"]], rsuffix="_plan")
        plan_mism = int((pj.n_turns != pj.n_turns_plan).sum())
        # turns per session sequential and no duplicates
        dup = int(ok.duplicated(["sid", "turn"]).sum())
        print(f"\n##### {tag} ({r})  sessions: {len(ses)}  completed {len(comp)}; completed with turns_completed!=n_turns: {mism_turns}; "
              f"last ok turn != n_turns: {mism_last}; |t_end - last t_complete| max {dt_end.max():.4f} s; "
              f"plan n_turns mismatches {plan_mism}; duplicate (sid,turn) ok rows {dup}")

        b = ses[ses.origin == "burst"]
        if len(b) == 0:
            continue
        print(f"burst cohort: n {len(b)}, arrival [{b.arrival_s.min():.1f}, {b.arrival_s.max():.1f}] s, n_turns==20: "
              f"{(b.n_turns == 20).sum()} ({(b.n_turns == 20).mean():.3f}); n_turns<20 values {sorted(b.n_turns[b.n_turns < 20].tolist())}")
        bc = b[b.status == "completed"]
        q = bc.t_end.quantile([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
        print(f"   completed by end {len(bc)}; t_end quantiles min/p10/q1/med/q3/p90/max: "
              + " / ".join(f"{v:.0f}" for v in q.values))
        b20 = bc[bc.n_turns == 20]
        print(f"   T=20 burst sessions t_end: min {b20.t_end.min():.0f} med {b20.t_end.median():.0f}; "
              f"T<20 burst sessions t_end: {sorted(np.round(bc[bc.n_turns < 20].t_end, 0).tolist())}")
        # turns done by 3000 s for each burst session
        okb = ok[ok.origin == "burst"]
        by3000 = okb[okb.t_complete <= 3000].groupby("sid").size().reindex(b.sid).fillna(0).astype(int)
        vc = by3000.value_counts().sort_index()
        print("   burst turns completed by t=3000 s (value: n sessions): " + ", ".join(f"{k}:{v}" for k, v in vc.items()))
        by2400 = okb[okb.t_complete <= 2400].groupby("sid").size().reindex(b.sid).fillna(0).astype(int)
        by3600 = okb[okb.t_complete <= 3600].groupby("sid").size().reindex(b.sid).fillna(0).astype(int)
        print(f"   burst turns completed by 2400 s: median {by2400.median():.0f} [{by2400.min()}, {by2400.max()}]; by 3600 s: "
              f"median {by3600.median():.0f} [{by3600.min()}, {by3600.max()}]")
        # lock-step: per turn k, completion time spread across the cohort (T=20 sessions only)
        ids20 = set(b.sid[b.n_turns == 20])
        okb20 = okb[okb.sid.isin(ids20)]
        g = okb20.groupby("turn").t_complete
        lk = pd.DataFrame({"n": g.size(), "p05": g.quantile(0.05), "med": g.median(), "p95": g.quantile(0.95)})
        lk["width90"] = lk.p95 - lk.p05
        lk["step_med"] = lk.med.diff()
        lat = okb20.groupby("turn").latency_s.median()
        lk["lat_med"] = lat
        print("   lock-step (T=20 burst sessions): turn, n, p05, median, p95 of t_complete, 90% width, step of median, median latency")
        print("   " + lk.round(0).fillna(-1).astype(int).to_string().replace("\n", "\n   "))
        # composition of completions in the blackout and in the wave peak
        cbl = comp[(comp.t_end >= 2400) & (comp.t_end < 3600)]
        print(f"   blackout completions: {len(cbl)} = origin {cbl.origin.value_counts().to_dict()}, n_turns {cbl.n_turns.value_counts().to_dict()}, "
              f"arrival_s range [{cbl.arrival_s.min():.0f}, {cbl.arrival_s.max():.0f}]")
        late = comp[(comp.t_end >= 6600) & (comp.t_end < 8700)]
        print(f"   late completions: {len(late)} = origin {late.origin.value_counts().to_dict()}, n_turns<20: {(late.n_turns < 20).sum()}, "
              f"arrival_s range [{late.arrival_s.min():.0f}, {late.arrival_s.max():.0f}]")
        # mid-way check: at t = 3000 s, how many requests in flight belong to burst sessions, and the distribution of turn index
        inflight3000 = req[(req.t_send <= 3000) & ((req.t_complete > 3000) | req.t_complete.isna())]
        print(f"   at t=3000 s: {len(inflight3000)} requests in flight, {int((inflight3000.origin == 'burst').sum())} from burst sessions")

    H = pd.DataFrame(hit_tab)
    C = pd.DataFrame(comp_tab)
    H.to_csv(os.path.join(OUT, "hit300.csv"))
    C.to_csv(os.path.join(OUT, "completions300_over_ref.csv"))
    print("\n=== hit fraction (cached/prompt > 0.5) of completed turns, 300-s bins (by t_complete)")
    print(H.round(3).to_string())
    print("\n=== session completions / lambda_ref, 300-s bins (by t_end)")
    print(C.round(3).to_string())


if __name__ == "__main__":
    main()
