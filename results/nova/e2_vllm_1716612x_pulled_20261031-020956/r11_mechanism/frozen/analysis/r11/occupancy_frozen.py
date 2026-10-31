"""Frozen r11 check (b) and TTFT rule (d), read-only on committed run dirs.
(b) mean of the engine KV-usage gauge (vllm:kv_cache_usage_perc, or sglang:token_usage) over metrics samples with
    t_s in [5700, 8700), and the uncached-prompt-token rate of ok requests sent in [5700, 8700) divided by the
    calibrated all-miss reference (argument).
(d) engine TTFT rule: 100-s mean TTFT from the *_time_to_first_token_seconds_{sum,count} counters > 30 s; first tick
    (10-s ticks) at which it holds, relative to t_burst = 1200 s.
Usage: python analysis/r11/occupancy_frozen.py <ref_uncached_tok_per_s> <run_dir> [<run_dir> ...]"""
import sys, json, os
import numpy as np, pandas as pd
T0, T1, TB, TICK, WIN, TTFT_HI = 5700.0, 8700.0, 1200.0, 10.0, 100.0, 30.0
ref = float(sys.argv[1]); rows = []
for d in sys.argv[2:]:
    meta = json.load(open(os.path.join(d, "meta.json")))
    m = pd.read_csv(os.path.join(d, "metrics.csv"))
    g = m[m.name.isin(["vllm:kv_cache_usage_perc", "sglang:token_usage"])]
    occ = g[(g.t_s >= T0) & (g.t_s < T1)].value.mean()
    q = pd.read_csv(os.path.join(d, "requests.csv"))
    w = q[(q.status == "ok") & (q.t_send >= T0) & (q.t_send < T1)]
    unc = (w.prompt_tokens - w.cached_tokens.fillna(0)).sum() / (T1 - T0)
    s = m[m.name.str.endswith("time_to_first_token_seconds_sum")].groupby("t_s").value.sum()
    c = m[m.name.str.endswith("time_to_first_token_seconds_count")].groupby("t_s").value.sum()
    tt = pd.DataFrame({"s": s, "c": c}).dropna().sort_index()
    first = None
    for t in np.arange(WIN, tt.index.max() if len(tt) else 0, TICK):
        a = tt[tt.index <= t - WIN].tail(1); b = tt[tt.index <= t].tail(1)
        if len(a) and len(b) and (b.c.iloc[0] - a.c.iloc[0]) > 0:
            if (b.s.iloc[0] - a.s.iloc[0]) / (b.c.iloc[0] - a.c.iloc[0]) > TTFT_HI:
                first = float(t); break
    rows.append(dict(run=os.path.basename(os.path.normpath(d)), arm=meta.get("arm"), label=meta.get("engine_label"),
                     occ_mean=round(occ, 4) if occ == occ else None, uncached_tok_s=round(unc, 1), uncached_ratio=round(unc / ref, 4),
                     ttft_first_alarm=first, ttft_delay_after_burst=(first - TB) if first is not None else None))
print(pd.DataFrame(rows).to_string())
if os.environ.get("OCC_OUT"):
    pd.DataFrame(rows).to_csv(os.environ["OCC_OUT"], index=False)
