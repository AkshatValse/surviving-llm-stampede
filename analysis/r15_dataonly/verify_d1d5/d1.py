import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np
O='C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5'
R='C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/'
b=pd.read_csv(O+'/runs_pool.csv')
rows=[]
for i,x in b.iterrows():
    if not x.n_trig>0: continue
    d=R+x['dir'];s=pd.read_csv(d+'/sessions.csv');r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'];r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
    if x.burst_n>0: trig=s[s.origin=='burst']
    else:
        t=pd.read_csv(d+'/tool_calls.csv');trig=s[s.sid.isin(set(t[t.add_s>0].sid))]
    left=trig[trig.status=='completed'];pres=trig[trig.status!='completed']
    allpres=s[s.status!='completed']
    runend=8700.0
    ent=dict(idx=i,n_trig=len(trig),n_trig_present=len(pres),n_all_present=len(allpres),n_sessions=len(s),
      pct_of_present=100*len(pres)/max(1,len(allpres)),pct_of_trig=100*len(pres)/len(trig),
      cancelled_t_end_min=pres.t_end.min() if len(pres) else np.nan)
    if len(pres)==0:
        L=left.t_end.max();p=r[r.t_complete>L]
        ent.update(last_left=L,left_before_end=runend-L,post_turns=len(p),post_hits=int(p.hit.sum()),post_hit=p.hit.mean())
        if p.hit.sum()>0:
            q=p[p.hit];ent['post_hit_times']=';'.join(f'{t:.0f}' for t in q.t_complete);ent['post_hit_ratios']=';'.join(f'{a/b_:.2f}' for a,b_ in zip(q.cached_tokens,q.prompt_tokens))
    rows.append(ent)
e=pd.DataFrame(rows).set_index('idx');j=b.join(e,rsuffix='_d1',how='inner')
j.to_csv(O+'/runs_d1.csv',index=False)
pd.set_option('display.width',250)
print(j[j.stuck][['label','seed','n_trig','n_trig_present','n_all_present','pct_of_present','pct_of_trig','last_left','left_before_end','post_turns','post_hits']].to_string())
