import json, glob, os, re
import pandas as pd, numpy as np
B="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454"
def mode(l):
    m=re.search(r'mode=""?([a-z_]+)',l); return m.group(1) if m else ""
for r in sorted(glob.glob(B+"/agentload_c_closed/*")):
    m=json.load(open(r+"/meta.json")); argv=" ".join(m["argv"])
    n=int(re.search(r"closed_n=(\d+)",argv).group(1)); pol=m["engine_label"].split("-")[1]
    df=pd.read_csv(r+"/metrics.csv"); df["mode"]=df["labels"].astype(str).map(mode)
    df["key"]=np.where(df["mode"]!="",df["name"]+"["+df["mode"]+"]",df["name"])
    p=df.groupby(["t_s","key"]).value.sum().unstack()
    hit=p["sglang:prefill_effective_tokens_total[device_hit]"]; inp=p["sglang:prefill_effective_tokens_total[input]"]
    bins=np.arange(0,2701,300); fr=[]
    for a,b in zip(bins[:-1],bins[1:]):
        s=p[(p.index>=a)&(p.index<=b)]
        h=s["sglang:prefill_effective_tokens_total[device_hit]"]; i=s["sglang:prefill_effective_tokens_total[input]"]
        dh=h.iloc[-1]-h.iloc[0]; di=i.iloc[-1]-i.iloc[0]; fr.append(round(dh/(dh+di),3) if dh+di>0 else None)
    # last time cached counter increased
    c=p["sglang:cached_tokens_total"]; inc=c.diff()>0; last_inc=c.index[inc].max() if inc.any() else None
    w=p[(p.index>=900)&(p.index<=2700)]
    ev=(w["sglang:evicted_tokens_total"].iloc[-1]-w["sglang:evicted_tokens_total"].iloc[0])/(w.index[-1]-w.index[0])
    qt=(w["sglang:queue_time_seconds_sum"].iloc[-1]-w["sglang:queue_time_seconds_sum"].iloc[0])/(w["sglang:queue_time_seconds_count"].iloc[-1]-w["sglang:queue_time_seconds_count"].iloc[0])
    print(f"{pol:4s} n={n:3d} hit-frac per 300s bin {fr} | last cached_tokens increase t={last_inc} | evict rate {ev:,.0f} tok/s -> 300k pool turnover {300000/ev:.1f}s | engine mean queue time {qt:.1f}s")
