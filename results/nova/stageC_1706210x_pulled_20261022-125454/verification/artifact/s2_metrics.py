import json, glob, os, re
import pandas as pd, numpy as np
D="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454/agentload_c_closed"
W0,W1=900.0,2700.0
def mode(lbl):
    m=re.search(r'mode=""?([a-z_]+)',lbl); return m.group(1) if m else ""
rows=[]; gauges=[]
for r in sorted(glob.glob(D+"/*")):
    m=json.load(open(r+"/meta.json")); argv=" ".join(m["argv"])
    n=int(re.search(r"closed_n=(\d+)",argv).group(1)); pol=m["engine_label"].split("-")[1]
    df=pd.read_csv(r+"/metrics.csv")
    df["mode"]=df["labels"].astype(str).map(mode)
    df["key"]=np.where(df["mode"]!="", df["name"]+"["+df["mode"]+"]", df["name"])
    piv=df.groupby(["t_s","key"])["value"].sum().unstack()
    w=piv[(piv.index>=W0)&(piv.index<=W1)]
    a,b=w.iloc[0],w.iloc[-1]
    def d(k): return float(b[k]-a[k]) if k in piv else np.nan
    # monotonic check on counters within window
    ctrs=["sglang:cached_tokens_total","sglang:prompt_tokens_total","sglang:prefill_effective_tokens_total[input]","sglang:prefill_effective_tokens_total[device_hit]","sglang:realtime_tokens_total[prefill_compute]","sglang:realtime_tokens_total[prefill_cache]","sglang:evicted_tokens_total","sglang:uncached_prompt_tokens_histogram_sum","sglang:prompt_tokens_histogram_sum","sglang:num_requests_total"]
    nonmono={k:int((w[k].dropna().diff()<0).sum()) for k in ctrs if k in w}
    # client side
    rq=pd.read_csv(r+"/requests.csv")
    ok=rq[(rq.status=="ok")&(rq.t_complete>=W0)&(rq.t_complete<W1)]
    okt=ok[ok.turn>1]
    rec=dict(run=os.path.basename(r),pol=pol,n=n,t_first=a.name,t_last=b.name,
      d_cached=d("sglang:cached_tokens_total"), d_prompt=d("sglang:prompt_tokens_total"),
      d_pe_input=d("sglang:prefill_effective_tokens_total[input]"), d_pe_hit=d("sglang:prefill_effective_tokens_total[device_hit]"),
      d_rt_comp=d("sglang:realtime_tokens_total[prefill_compute]"), d_rt_cache=d("sglang:realtime_tokens_total[prefill_cache]"),
      d_evicted=d("sglang:evicted_tokens_total"), d_uncached_hist=d("sglang:uncached_prompt_tokens_histogram_sum"),
      d_prompt_hist=d("sglang:prompt_tokens_histogram_sum"), d_nreq=d("sglang:num_requests_total"),
      cl_n=len(ok), cl_prompt=int(ok.prompt_tokens.sum()), cl_cached=int(ok.cached_tokens.sum()),
      cl_frac=ok.cached_tokens.sum()/ok.prompt_tokens.sum(),
      cl_frac_t2=okt.cached_tokens.sum()/okt.prompt_tokens.sum(),
      cl_turn_hit=(okt.cached_tokens>0).mean(), cl_turn_hit_half=(okt.cached_tokens>=0.5*okt.prompt_tokens).mean(),
      cached_src=dict(ok.cached_source.value_counts(dropna=False)), cached_na=int(ok.cached_tokens.isna().sum()),
      nonmono=nonmono)
    rec["eng_frac_cached_over_prompt"]=rec["d_cached"]/rec["d_prompt"]
    rec["eng_frac_pe"]=rec["d_pe_hit"]/(rec["d_pe_hit"]+rec["d_pe_input"])
    rec["eng_frac_rt"]=rec["d_rt_cache"]/(rec["d_rt_cache"]+rec["d_rt_comp"])
    rec["eng_frac_hist"]=1-rec["d_uncached_hist"]/rec["d_prompt_hist"]
    rows.append(rec)
    g={}
    for k in ["sglang:cache_hit_rate","sglang:token_usage","sglang:full_token_usage","sglang:kv_evictable_tokens","sglang:kv_used_tokens","sglang:kv_available_tokens","sglang:num_retracted_reqs","sglang:num_paused_reqs","sglang:num_queue_reqs","sglang:num_running_reqs","sglang:max_total_num_tokens","agentload:inflight_requests"]:
        if k in w:
            s=w[k].dropna(); g[k.split(":")[1]]=(round(s.mean(),3),round(s.median(),3),round(s.min(),3),round(s.max(),3))
    gauges.append((os.path.basename(r),pol,n,g))
out=pd.DataFrame(rows).sort_values(["pol","n"])
pd.set_option("display.width",250); pd.set_option("display.max_columns",50)
print(out[["run","pol","n","t_first","t_last","d_prompt","d_cached","eng_frac_cached_over_prompt","eng_frac_pe","eng_frac_rt","eng_frac_hist","d_evicted","d_nreq","cl_n","cl_prompt","cl_cached","cl_frac","cl_frac_t2","cl_turn_hit","cl_turn_hit_half","cached_na"]].to_string())
print(out[["run","n","d_prompt","cl_prompt","d_pe_input","d_pe_hit","d_rt_comp","d_rt_cache","d_uncached_hist","d_prompt_hist","cached_src","nonmono"]].to_string())
for run,pol,n,g in sorted(gauges,key=lambda x:(x[1],x[2])):
    print(run,pol,n)
    for k,v in g.items(): print("   ",k,"mean/med/min/max",v)
out.to_csv(os.path.dirname(__file__)+"/s2_metrics_out.csv",index=False)
