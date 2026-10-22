"""Follow-ups: fine-grained regime switching, length-biased in-flight expectation, CRN check,
prefill-token throughput constancy."""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = "/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454/agentload_c_closed"
q = 14.0 / 15.0
K = np.arange(1, 61)
S = q ** (K - 1)
ET = S.sum()

runs = {}
for d in sorted(glob.glob(ROOT + "/*/")):
    m = json.load(open(d + "meta.json"))
    n = int([a for a in m["argv"] if a.startswith("arrivals.closed_n=")][0].split("=")[1])
    pol = "LPM" if "lpm" in m["engine_label"] else "FCFS"
    runs[(pol, n)] = (pd.read_csv(d + "requests.csv"), pd.read_csv(d + "sessions.csv"))

# common random numbers across runs?
base = runs[("FCFS", 16)][1].set_index("idx").n_turns
for key, (rq, ss) in runs.items():
    s = ss.set_index("idx").n_turns
    c = base.index.intersection(s.index)
    print("CRN", key, "same n_turns for idx in common:", (base.loc[c] == s.loc[c]).mean().round(3), "n_common", len(c),
          "initial cohort arrival_s max", round(float(ss[ss.idx < key[1]].arrival_s.max()), 3))

print("\ncount-biased E[k] =", (K * S).sum() / ET, " E[prompt] =", 2000 + 650 * ((K * S).sum() / ET - 1))
print("E[total prompt tokens per session] =", (S * (2000 + 650 * (K - 1))).sum())

# fine bins (60 s) over the full run for regime runs
for key in [("FCFS", 24), ("FCFS", 32), ("LPM", 48), ("FCFS", 48)]:
    rq, ss = runs[key]
    ok = rq[rq.status == "ok"].copy()
    ok["b"] = (ok.t_complete // 150).astype(int)
    ok["hit"] = ok.cached_tokens / ok.prompt_tokens > 0.5
    g = ok.groupby("b").agg(tps=("turn", lambda x: len(x) / 150), hit=("hit", "mean"), lat=("latency_s", "median"))
    print("\n", key, "150 s bins over full run (bin start s: turns/s, hit, median lat)")
    print(" ".join(f"{int(b*150)}:{r.tps:.2f}/{r.hit:.2f}/{r.lat:.0f}" for b, r in g.iterrows()))

# length-biased in-flight expectation using empirical latency by turn index
print("\nIn-flight expectations (requests in flight). L(k) = in-window mean latency by turn, smoothed by linear fit on k")
for key, (rq, ss) in sorted(runs.items(), key=lambda x: (x[0][0], x[0][1])):
    ok = rq[(rq.status == "ok") & (rq.t_complete >= 900) & (rq.t_complete < 2700)]
    coef = np.polyfit(ok.turn, ok.latency_s, 1)
    L = np.clip(np.polyval(coef, K), 1e-3, None)
    w = S * L
    ek = (K * w).sum() / w.sum()
    ep = ((2000 + 650 * (K - 1)) * w).sum() / w.sum()
    # observed time-averaged in-flight over window (sample every 10 s)
    ts = np.arange(900, 2700, 10.0)
    tc = rq.t_complete.fillna(np.inf).to_numpy()
    tsend = rq.t_send.to_numpy()
    turn = rq.turn.to_numpy()
    pr = rq.prompt_tokens_client.to_numpy()
    mk, mp = [], []
    for t in ts:
        f = (tsend <= t) & (tc > t)
        if f.any():
            mk.append(turn[f].mean()); mp.append(pr[f].mean())
    # prefill-token throughput per 300 s bin (uncached tokens)
    ok2 = ok.copy(); ok2["b"] = ((ok2.t_complete - 900) // 300).astype(int)
    unc = ok2.groupby("b").apply(lambda x: (x.prompt_tokens - x.cached_tokens).sum() / 300, include_groups=False)
    print(f"{key}: L(k)={coef[1]:.1f}+{coef[0]:.2f}k s; stationary in-flight E[k]={ek:.2f}, E[prompt]={ep:.0f}; "
          f"observed window-avg in-flight E[k]={np.mean(mk):.2f}, E[prompt]={np.mean(mp):.0f}; "
          f"uncached tok/s per bin={np.round(unc.to_numpy()/1000,2).tolist()}k")
