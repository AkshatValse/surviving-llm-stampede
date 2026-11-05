import warnings;warnings.filterwarnings('ignore')
O='C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5'
import pandas as pd,numpy as np,glob,yaml,json,os
R='C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/'
rows=[]
for f in sorted(glob.glob(R+'results/nova/*/results/agentload_e2_*/*/sessions.csv')):
    d=os.path.dirname(f).replace(chr(92),'/')
    c=yaml.safe_load(open(d+'/config_effective.yaml'))
    m=json.load(open(d+'/meta.json'))
    s=pd.read_csv(f);r=pd.read_csv(d+'/requests.csv')
    r=r[r.status=='ok'].copy()
    r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
    ev=r[(r.t_complete>=5700)&(r.t_complete<8700)]
    hf=ev.hit.mean() if len(ev) else np.nan
    a=c['arrivals'];w=c['workload'];g=c.get('gate',{})
    bn=a['burst']['n'] if a.get('burst') else 0
    ts='tool_slowdown' in w
    trig=None
    if bn: trig=s[s.origin=='burst']
    if ts:
        t=pd.read_csv(d+'/tool_calls.csv');ids=set(t[t.add_s>0].sid);trig=s[s.sid.isin(ids)]
    nt=len(trig) if trig is not None else 0
    row=dict(pull=d.split('results/nova/')[1].split('/')[0],run_ts=os.path.basename(d),label=c['meta']['engine_label'],arm=c['meta']['arm'],seed=c['run']['seed'],hw=c['meta']['hardware'][:12],model=c['server']['model'],burst_n=bn,toolslow=ts,gate=g.get('mode'),t_on=g.get('t_on_s'),ramp=('ramp' in a),hit_eval=hf,n_eval=len(ev),stuck=(hf<0.2),n_trig=nt,dir=d.split('Nova-Research/')[-1] if False else d.replace(R,''))
    if nt:
        left=trig[trig.status=='completed']
        row['n_trig_present']=nt-len(left)
        row['last_left']=left.t_end.max() if len(left) else np.nan
        row['run_end']=m.get('wall_s')
        if row['n_trig_present']==0:
            L=row['last_left'];post=r[r.t_complete>L]
            row['post_turns']=len(post);row['post_hit']=post.hit.mean() if len(post) else np.nan
            row['post_hits_n']=int(post.hit.sum())
        row['frac_present']=row['n_trig_present']/max(1,len(s))
    rows.append(row)
df=pd.DataFrame(rows);df.to_csv(O+'/runs_base.csv',index=False)
print(len(df))
print(df.groupby(['label','arm','burst_n','toolslow','gate']).agg(n=('stuck','size'),stuck=('stuck','sum')).to_string())
