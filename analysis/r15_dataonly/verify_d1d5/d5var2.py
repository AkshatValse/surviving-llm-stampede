import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np
exec(open('C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5/d5.py').read().split('rows=[]')[0])
e=pd.read_csv(O+'/d5_e2.csv');f=e[(e.kind=='fcfs')&e.onset_start.notna()&(e.cut_why=='end')]
for key in ['t_complete','t_send','t_headers']:
  for tr in [1,2]:
    tot=[]
    for _,x in f.iterrows():
        d=R+b.loc[x.idx,'dir'];r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
        r['t_complete']=r[key];r=r[r.turn>=tr+0] if tr==2 else r  # tr=1: includes first turns? 
        if tr==1: r=r.assign(turn=r.turn+1)  # include all turns as followups
        W=windows(r,8700);on=None
        for a,en,hf,nn in W:
            if a>=1200 and not np.isnan(hf) and hf<=0.2: on=a;break
        tot.append(8700-on if on is not None else np.nan)
    print(key,'all turns' if tr==1 else 'turn>1',np.nansum(tot),np.nanmin(tot),np.isnan(tot).sum())
