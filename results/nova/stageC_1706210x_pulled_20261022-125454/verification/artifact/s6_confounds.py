import json, glob, os, re
import pandas as pd, numpy as np
B="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454"
for J in sorted(glob.glob(B+"/nova_job_logs/*")):
    for f in sorted(glob.glob(J+"/canary_*_prime.json")):
        p=json.load(open(f)); c=json.load(open(f.replace("prime","check")))
        print(os.path.basename(J)[:8],os.path.basename(f)[:8],"prime 2nd cached",p["second"]["cached_tokens"],"/",p["second"]["prompt_tokens"],"| check after flush cached",c["after_flush"]["cached_tokens"],"idle",c["idle"]["idle"],"usage",c["idle"]["kv_in_use"]["value"],"ok",p["ok"],c["ok"])
    g=open(J+"/gpu_util.csv").read().splitlines()[1:]
    print("  gpu_util rows",len(g))
for r in sorted(glob.glob(B+"/agentload_c_closed/*")):
    m=json.load(open(r+"/meta.json")); argv=" ".join(m["argv"])
    n=int(re.search(r"closed_n=(\d+)",argv).group(1)); pol=m["engine_label"].split("-")[1]
    gt=m["outcome"]["gate"]
    rq=pd.read_csv(r+"/requests.csv"); ok=rq[(rq.status=="ok")&(rq.turn>1)]
    early=ok[ok.t_complete<300]; full=(early.cached_tokens==early.prompt_tokens-551)
    late=ok[(ok.t_complete>=900)&(ok.t_complete<2700)]
    lf=(late.cached_tokens==late.prompt_tokens-551)
    print(pol,n,m["hostname"],"job",m["slurm_env"]["SLURM_JOB_ID"],"gate waited",gt["n_waited"],"max_active",gt["max_active_seen"],"| early(<300s) turn>1 reqs",len(early),"frac full-prefix hit (cached=pt-551)",round(full.mean(),3),"frac zero",round((early.cached_tokens==0).mean(),3),"| window full-hit",round(lf.mean(),3),"zero",round((late.cached_tokens==0).mean(),3),"partial",round(((late.cached_tokens>0)&~lf).mean(),3))
