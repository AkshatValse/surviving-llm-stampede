import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np,yaml
O='C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5'
R='C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/'
b=pd.read_csv(O+'/runs_d1.csv')
def windows(r,end):
    f=r[(r.turn>1)]
    nb=int(np.ceil(end/100))
    h=np.zeros(nb);n=np.zeros(nb)
    k=(f.t_complete//100).astype(int).clip(upper=nb-1)
    np.add.at(n,k.values,1);np.add.at(h,k.values,f.hit.values.astype(float))
    W=[]
    for i in range(nb-2):
        nn=n[i:i+3].sum()
        W.append((i*100.,(i+3)*100.,h[i:i+3].sum()/nn if nn>0 else np.nan,nn))
    return W
rows=[]
for i,x in b.iterrows():
    if x.label.startswith(('sglang-lpm',)) : kind='lpm'
    else: kind='fcfs'
    d=R+x['dir']
    trig = x.burst_n>0 or x.toolslow
    if not trig or x.arm=='capped' or (x.arm=='noburst' and not x.toolslow): continue
    c=yaml.safe_load(open(d+'/config_effective.yaml'))
    cut=8700.0;why='end'
    if c.get('gate',{}).get('mode')=='rescue': cut=float(c['gate']['t_on_s']);why='rescue_on'
    if x.ramp: cut=float(c['arrivals']['ramp'][1][0]);why='shed_stop'
    r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
    W=windows(r,8700)
    ttr=1200.
    onset=None;esc=None
    for (a,e,hf,nn) in W:
        if a>=ttr and e<=cut and not np.isnan(hf) and hf<=0.2: onset=(a,e);break
    if onset:
        for (a,e,hf,nn) in W:
            if a>onset[0] and e<=cut and not np.isnan(hf) and hf>=0.5: esc=(a,e,hf);break
    rows.append(dict(idx=i,kind=kind,label=x.label,seed=x.seed,pull=x.pull,run_ts=x.run_ts,cut=cut,cut_why=why,onset_start=onset[0] if onset else np.nan,onset_end=onset[1] if onset else np.nan,
       escape=bool(esc),esc_start=esc[0] if esc else np.nan,esc_hit=esc[2] if esc else np.nan,stuck=x.stuck,hit_eval=x.hit_eval))
e=pd.DataFrame(rows)
e['trapped_s_start']=e.cut-e.onset_start; e['trapped_s_end']=e.cut-e.onset_end
e.to_csv(O+'/d5_e2.csv',index=False)
pd.set_option('display.width',250)
print(e.drop(columns=['pull','idx']).to_string())
