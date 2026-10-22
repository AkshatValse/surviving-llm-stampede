"""Reviewer spot-checks for Stage C (read-only on pulled data)."""
import json, glob, os
import numpy as np, pandas as pd, yaml

B = "/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454/agentload_c_closed"
M = 300_000
# workload analytics
p = 1 / 15
k = np.arange(1, 61)
surv = (1 - p) ** (k - 1)              # P(T>=k), T=min(Geom(p),60)
ET = surv.sum()
prompt = 2000 + 650 * (k - 1)
tok_allmiss = (surv * prompt).sum()      # E[sum_k prompt_k]
tok_allhit = (surv * np.where(k == 1, 2000, 551)).sum()
# time-avg footprint of a live session: after turn k its cached prefix ~ prompt_k+99,
# weight each turn-cycle equally (turn index distribution of live time ~ P(T>=k)/E[T])
foot = (surv * (prompt + 99)).sum() / ET
print(f"E[T]={ET:.4f} tok_allmiss={tok_allmiss:.0f} tok_allhit={tok_allhit:.0f} ratio={tok_allmiss/tok_allhit:.1f}")
print(f"mean live footprint={foot:.0f} tok; n_fit=M/foot={M/foot:.1f}")
# native pool estimate from server.log numbers: K+V 16.02 GB for 300k -> per token
per_tok = 2 * 8.01e9 / M
print(f"KV bytes/token (from log)={per_tok:.0f}")

rows = []
for d in sorted(glob.glob(B + "/*/")):
    c = yaml.safe_load(open(d + "config_effective.yaml"))
    m = json.load(open(d + "meta.json"))
    r = pd.read_csv(d + "requests.csv", usecols=["sid", "turn", "n_turns", "t_send", "t_complete", "status", "prompt_tokens", "cached_tokens"])
    ok = r[r.status == "ok"]
    w = ok[(ok.t_complete >= 900) & (ok.t_complete < 2700)]
    unc = (w.prompt_tokens - w.cached_tokens).sum() / 1800
    tps = len(w) / 1800
    # 300 s bins of uncached tok/s
    bins = [((w[(w.t_complete >= a) & (w.t_complete < a + 300)].prompt_tokens - w[(w.t_complete >= a) & (w.t_complete < a + 300)].cached_tokens).sum() / 300) for a in range(900, 2700, 300)]
    # early hit fraction, turn>=2, t_complete<300
    e = ok[(ok.turn >= 2) & (ok.t_complete < 300)]
    early_hit = (e.cached_tokens > 0).mean() if len(e) else np.nan
    pol = "LPM" if "lpm" in c["meta"]["engine_label"] else "FCFS"
    rows.append(dict(run=os.path.basename(d[:-1]), pol=pol, n=c["arrivals"]["closed_n"], host=m.get("hostname"),
                     tps=tps, mu_turns=tps / ET, unc_tok_s=unc,
                     mu_allmiss_proj=unc / tok_allmiss, unc_b0=bins[0], unc_b5=bins[-1],
                     n_over_nfit=c["arrivals"]["closed_n"] / (M / foot), early_hit_t2=early_hit,
                     mean_prompt_win=w.prompt_tokens.mean()))
df = pd.DataFrame(rows).sort_values(["pol", "n"])
pd.set_option("display.width", 250)
print(df.round(4).to_string(index=False))
df.to_csv(os.path.join(os.path.dirname(__file__), "review_calc_out.csv"), index=False)
