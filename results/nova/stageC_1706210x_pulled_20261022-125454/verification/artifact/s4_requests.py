import json, glob, os, re
import pandas as pd, numpy as np
B="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454"
W0,W1=900,2700
res=[]
for r in sorted(glob.glob(B+"/agentload_c_closed/*")):
    m=json.load(open(r+"/meta.json")); argv=" ".join(m["argv"])
    n=int(re.search(r"closed_n=(\d+)",argv).group(1)); pol=m["engine_label"].split("-")[1]
    rq=pd.read_csv(r+"/requests.csv")
    ok=rq[rq.status=="ok"].copy()
    u=ok.raw_usage_json.map(json.loads)
    ok["raw_ct"]=u.map(lambda d:d["usage"].get("prompt_tokens_details",{}) .get("cached_tokens") if d.get("usage") and d["usage"].get("prompt_tokens_details") is not None else None)
    ok["raw_pt"]=u.map(lambda d:d["usage"]["prompt_tokens"]); ok["raw_comp"]=u.map(lambda d:d["usage"]["completion_tokens"])
    ok["has_ptd"]=u.map(lambda d:"prompt_tokens_details" in d["usage"] and d["usage"]["prompt_tokens_details"] is not None)
    exp=2000+650*(ok.turn-1)
    # consecutive-turn growth within session
    s=ok.sort_values(["sid","turn"]); s["dpt"]=s.groupby("sid").prompt_tokens.diff(); s["dturn"]=s.groupby("sid").turn.diff()
    g=s[s.dturn==1].dpt
    win=ok[(ok.t_complete>=W0)&(ok.t_complete<W1)]
    # inter-turn gap: next t_send - prev t_complete (tool time), and prev complete -> next complete
    s["gap_tool"]=s.groupby("sid").t_send.shift(-1)-s.t_complete
    sw=s[(s.t_complete>=W0)&(s.t_complete<W1)]
    rec=dict(pol=pol,n=n,ok=len(ok),raw_ct_eq_col=float((ok.raw_ct==ok.cached_tokens).mean()), has_ptd=float(ok.has_ptd.mean()),
             raw_pt_eq=float((ok.raw_pt==ok.prompt_tokens).mean()), pt_client_eq=float((ok.prompt_tokens_client==ok.prompt_tokens).mean()),
             pt_eq_expected=float((ok.prompt_tokens==exp).mean()), comp100=float((ok.raw_comp==100).mean()),
             growth_650=float((g==650).mean()), growth_vals=dict(g.value_counts().head(3)), oid_src=dict(ok.output_ids_source.value_counts()),
             ct_gt_pt=int((ok.cached_tokens>ok.prompt_tokens).sum()),
             lat_mean=round(win.latency_s.mean(),1), lat_p50=round(win.latency_s.median(),1), lat_p95=round(win.latency_s.quantile(.95),1),
             sched_delay_max=round(win.sched_delay_s.max(),3), tool_gap_mean=round(sw.gap_tool.mean(),2),
             mean_pt_win=round(win.prompt_tokens.mean()), max_pt=int(ok.prompt_tokens.max()), statuses=dict(rq.status.value_counts()))
    res.append(rec)
    if n in (16,48) and pol=="fcfs":
        smp=win[win.turn>1].sample(4,random_state=0)
        print(f"--- sample n={n} {pol}"); print(smp[["sid","turn","prompt_tokens","cached_tokens","cached_source","output_ids_source","raw_usage_json"]].to_string(index=False))
pd.set_option("display.width",300); pd.set_option("display.max_columns",40); pd.set_option("display.max_colwidth",60)
print(pd.DataFrame(res).sort_values(["pol","n"]).to_string(index=False))
