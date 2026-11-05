import pandas as pd, numpy as np, glob, os, json, sys
REPO="C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/"
INV="C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/data-A/inventory.csv"
inv=pd.read_csv(INV)
inv['rd']=REPO+inv.run_dir
FAM={'sglang300k':('e2_170933xx','sglang-fcfs-r1'),
     'native':('e2_native_vllm','sglang-fcfs-r1-native'),
     'vllm':('e2_vllm_1716612x','vllm-fcfs'),
     'h200':('h200p600k_e2','sglang-fcfs-r1-h200-p600k'),
     'llama':('llama31_e2','sglang-fcfs-r1-llama31')}
def sel(fam,arm):
    p,l=FAM[fam]
    return inv[inv.pulled.str.startswith(p)&(inv.label==l)&(inv.arm==arm)]
def load(rd):
    s=pd.read_csv(rd+'/sessions.csv',low_memory=False); q=pd.read_csv(rd+'/requests.csv',low_memory=False); p=pd.read_csv(rd+'/plan.csv')
    return s,q,p
def prep_req(q):
    q=q[q.status=='ok'].sort_values(['sid','turn']).copy()
    pp=q.groupby('sid').prompt_tokens.shift(1); pc=q.groupby('sid').completion_tokens.shift(1)
    q['new']=np.where(pp.isna(),q.prompt_tokens,q.prompt_tokens-pp-pc).clip(min=1)
    return q
# reference model per family, fit on NOBURST low-load requests
def fit_ref(fam,tmax=600):
    X=[];Y=[]
    for _,r in sel(fam,'noburst').iterrows():
        s,q,p=load(r.rd); q=prep_req(q)
        q=q[(q.t_send<tmax)&(q.sched_delay_s<0.05)]
        X.append(q[['new','completion_tokens','latency_s']])
    d=pd.concat(X)
    A=np.c_[np.ones(len(d)),d.new,d.completion_tokens]
    coef=np.linalg.lstsq(A,d.latency_s,rcond=None)[0]
    res=d.latency_s-A@coef
    return coef,res,len(d)
REF={}
def refs(fam):
    if fam not in REF: REF[fam]=fit_ref(fam)
    return REF[fam]
def session_table(rd,fam,mode='ols',scale=1.0):
    coef,res,_=refs(fam)
    c=coef.copy()
    if mode=='p10': c[0]+=np.percentile(res,10)
    if mode=='p50': c[0]+=np.percentile(res,50)
    s,q,p=load(rd); q=prep_req(q)
    q['ref']=np.maximum(c[0]+c[1]*q.new+c[2]*q.completion_tokens,0.01)
    g=q.groupby('sid').agg(refsum=('ref','sum'),nreq=('turn','size'))
    t=s[s.origin=='base'].merge(p[['sid','tool_time_total_s']],on='sid').merge(g,on='sid',how='left')
    t['complete']=(t.status=='completed')&(t.nreq==t.n_turns)
    t['elapsed']=t.t_end-t.arrival_s
    t['ref_total']=(t.tool_time_total_s+t.refsum)*scale
    t['slow']=t.elapsed/t.ref_total
    return t
def gp(t,w,thr=4.0):
    m=(t.arrival_s>=w[0])&(t.arrival_s<w[1])
    n=int(m.sum()); good=int((m&t.complete&(t.slow<=thr)).sum()); done=int((m&t.complete).sum())
    return n,done,good
RESFAM={'sglang300k':('rescue_1716896x','sglang-fcfs-r1-rescue'),'native':('rescue_1716896x','sglang-fcfs-r1-rescue-native')}
def runs_for(fam,arm):
    if arm=='rescue':
        p,l=RESFAM[fam]; return inv[inv.pulled.str.startswith(p)&(inv.label==l)&(inv.arm=='rescue')]
    return sel(fam,arm)
