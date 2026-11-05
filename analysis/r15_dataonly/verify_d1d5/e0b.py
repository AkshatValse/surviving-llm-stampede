import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np,glob,yaml,os
O='C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5'
R='C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/'
def windows(r,end):
    f=r[(r.turn>1)];nb=int(np.ceil(end/100));h=np.zeros(nb);n=np.zeros(nb)
    k=(f.t_complete//100).astype(int).clip(upper=nb-1,lower=0)
    np.add.at(n,k.values,1);np.add.at(h,k.values,f.hit.values.astype(float))
    return [(i*100.,(i+3)*100.,h[i:i+3].sum()/n[i:i+3].sum() if n[i:i+3].sum()>0 else np.nan) for i in range(nb-2)]
rows=[]
for f in sorted(glob.glob(R+'results/nova/*/results/agentload_e0_cap/*/config_effective.yaml')):
    d=os.path.dirname(f).replace(chr(92),'/');c=yaml.safe_load(open(f))
    r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
    W=windows(r,3000);hv=np.array([w[2] for w in W]);st=np.array([w[0] for w in W])
    late=r[r.t_complete>=2000];hl=late[late.turn>1].hit.mean()
    # collapse: windows after t>=600 with hit<=.2
    on=next((w[0] for w in W if w[0]>=600 and w[2]<=0.2),None)
    esc=None
    if on is not None: esc=next((w[0] for w in W if w[0]>on and w[2]>=0.5),None)
    rows.append(dict(pull=d.split('results/nova/')[1].split('/')[0],run_ts=os.path.basename(d),label=c['meta']['engine_label'],seed=c['run']['seed'],rate=c['arrivals']['rate_mult'],
      hit_last1000=hl,hit_w_min=np.nanmin(hv[st>=600]),hit_w_max=np.nanmax(hv[st>=600]),first_w600=hv[st==600][0] if (st==600).any() else np.nan,onset=on,escape_start=esc,trace=' '.join(f'{x:.2f}' for x in hv[::3])))
e=pd.DataFrame(rows);e.to_csv(O+'/e0b_cap_runs.csv',index=False)
pd.set_option('display.width',300);pd.set_option('display.max_colwidth',200)
print(e.drop(columns=['pull','trace']).to_string())
print('--- sensitivity')
import re
for lo in [0,300,600,900]:
    ncol=nesc=0
    for _,x in e.iterrows():
        d=[g for g in glob.glob(R+'results/nova/'+x.pull+'/results/agentload_e0_cap/'+x.run_ts)][0]
        r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
        W=windows(r,3000)
        on=next((w[0] for w in W if w[0]>=lo and w[2]<=0.2),None)
        if on is None: continue
        ncol+=1
        if any(w[0]>on and w[2]>=0.5 for w in W): nesc+=1
    print(lo,ncol,nesc)
