import json, glob, os, re
from datetime import datetime, timedelta, timezone
import pandas as pd, numpy as np
B="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454"
runs=[]
for r in sorted(glob.glob(B+"/agentload_c_closed/*")):
    m=json.load(open(r+"/meta.json")); argv=" ".join(m["argv"])
    n=int(re.search(r"closed_n=(\d+)",argv).group(1))
    t0=datetime.fromisoformat(m["t0_utc"])
    runs.append(dict(run=os.path.basename(r),n=n,pol=m["engine_label"].split("-")[1],job=m["slurm_env"]["SLURM_JOB_ID"],t0=t0,
                     start_local=datetime.fromisoformat(m["start_time"])))
# infer local offset from start_time vs t0_utc
for x in runs:
    off=(x["start_local"]-x["t0"].replace(tzinfo=None)).total_seconds()
    x["off_h"]=round(off/3600)
print("utc offsets (h):",sorted(set(x["off_h"] for x in runs)))
pre=re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Prefill batch, #new-seq: (\d+), #new-token: (\d+), #cached-token: (\d+), token usage: ([\d.]+), #running-req: (\d+), #queue-req: (\d+)")
dec=re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Decode batch, #running-req: (\d+), #token: (\d+), token usage: ([\d.]+).*#queue-req: (\d+)")
out=[]
for J in sorted(glob.glob(B+"/nova_job_logs/*")):
    job=os.path.basename(J).split("-")[0]
    P=[];Dd=[]
    for line in open(J+"/server.log",errors="replace"):
        mm=pre.match(line)
        if mm: P.append((mm.group(1),*map(int,mm.group(2,3,4)),float(mm.group(5)),int(mm.group(6)),int(mm.group(7)))); continue
        mm=dec.match(line)
        if mm: Dd.append((mm.group(1),int(mm.group(2)),int(mm.group(3)),float(mm.group(4)),int(mm.group(5))))
    P=pd.DataFrame(P,columns=["ts","new_seq","new_tok","cached_tok","usage","running","queue"]); P["ts"]=pd.to_datetime(P["ts"])
    Dd=pd.DataFrame(Dd,columns=["ts","running","tok","usage","queue"]); Dd["ts"]=pd.to_datetime(Dd["ts"])
    for x in [r for r in runs if r["job"]==job]:
        t0l=pd.Timestamp(x["t0"].replace(tzinfo=None))+pd.Timedelta(hours=x["off_h"])
        a,b=t0l+pd.Timedelta(seconds=900),t0l+pd.Timedelta(seconds=2700)
        p=P[(P.ts>=a)&(P.ts<b)]; d=Dd[(Dd.ts>=a)&(Dd.ts<b)]
        pw=P[(P.ts>=t0l)&(P.ts<a)]
        share=p.cached_tok.sum()/(p.cached_tok.sum()+p.new_tok.sum())
        q=lambda s:[round(v,2) for v in np.percentile(s,[5,25,50,75,95])] if len(s) else None
        out.append(dict(run=x["run"],pol=x["pol"],n=x["n"],job=job,n_prefill_lines=len(p),new_tok=int(p.new_tok.sum()),cached_tok=int(p.cached_tok.sum()),
            cached_share=round(share,4), lines_with_cached=int((p.cached_tok>0).sum()), new_seq=int(p.new_seq.sum()),
            warm_cached_share=round(pw.cached_tok.sum()/max(1,pw.cached_tok.sum()+pw.new_tok.sum()),4),
            pre_usage_pct=q(p.usage), dec_usage_pct=q(d.usage), dec_usage_ge095=round((d.usage>=0.95).mean(),3) if len(d) else None,
            pre_queue_mean=round(p.queue.mean(),1), dec_queue_mean=round(d.queue.mean(),1) if len(d) else None, dec_running_mean=round(d.running.mean(),1) if len(d) else None, n_dec_lines=len(d)))
o=pd.DataFrame(out).sort_values(["pol","n"])
pd.set_option("display.width",300); pd.set_option("display.max_columns",40)
print(o.to_string(index=False))
o.to_csv(os.path.dirname(__file__)+"/s3_serverlog_out.csv",index=False)
