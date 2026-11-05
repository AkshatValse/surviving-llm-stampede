import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np
exec(open('C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5/d5.py').read().split('rows=[]')[0])
e=pd.read_csv(O+'/d5_e2.csv');f=e[(e.kind=='fcfs')&e.onset_start.notna()&(e.cut_why=='end')]
res={}
for lo in [800,900,1000,1100,1200]:
  for lab in ['start','end','center']:
    tot=[];
    for _,x in f.iterrows():
        d=R+b.loc[x.idx,'dir'];r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
        W=windows(r,8700);on=None
        for a,en,hf,nn in W:
            if a>=lo and not np.isnan(hf) and hf<=0.2: on=a;break
        tot.append(8700-(on+{'start':0,'end':300,'center':150}[lab]))
    res[(lo,lab)]=(sum(tot),min(tot))
for k,v in res.items(): print(k,v)
