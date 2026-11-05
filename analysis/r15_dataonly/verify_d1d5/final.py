import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np
exec(open('C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5/d5.py').read().split('rows=[]')[0])
e=pd.read_csv(O+'/d5_e2.csv');t=e[e.onset_start.notna()&(e.trapped_s_start>=1000)].copy()
mx=[]
for _,x in t.iterrows():
    d=R+b.loc[x.idx,'dir'];r=pd.read_csv(d+'/requests.csv');r=r[r.status=='ok'].copy();r['hit']=(r.cached_tokens/r.prompt_tokens)>0.5
    W=windows(r,8700);mx.append(max([w[2] for w in W if w[0]>x.onset_start and w[1]<=x.cut and not np.isnan(w[2])] or [np.nan]))
t['max_post_onset_window_hit']=mx
t['cohort']=np.where(t.kind=='lpm',np.where(t.label=='sglang-lpminf','LPM-inf','stock-LPM'),'FCFS-trapped')
t.drop(columns=['pull','idx']).to_csv(O+'/D5_trapped_runs.csv',index=False)
f=t[t.cohort=='FCFS-trapped']
print(len(f),f.escape.sum(),f.trapped_s_start.sum(),f.trapped_s_end.sum(),f.max_post_onset_window_hit.max(),f[f.label.str.contains('toolslow')].max_post_onset_window_hit.values)
print(f.groupby('label').size().to_dict(), (f.cut_why!='end').sum())
l=t[t.cohort!='FCFS-trapped'];print(l.groupby('cohort').agg(n=('escape','size'),esc=('escape','sum')))
print(l[l.escape][['label','seed','run_ts','onset_start','esc_start','esc_hit','hit_eval']])
print(1-0.05**(1/50), 371300/3600,356300/3600)
# D1 final csv
j=pd.read_csv(O+'/runs_d1.csv');s=j[j.stuck].drop(columns=['pull']).copy()
s.drop(columns=[c for c in ['dir','post_hit_times','post_hit_ratios'] if c in s]).to_csv(O+'/D1_stuck_runs.csv',index=False)
p=pd.read_csv(O+'/runs_pool.csv');p[p.stuck][['label','pull','run_ts','seed','engine','pool','run_share','run_share_med','evict_share','running','queue','hit_eval','n_snap']].to_csv(O+'/P_pool_share_stuck_runs.csv',index=False)
print(p[p.stuck].groupby(['label','pull']).run_share.agg(['min','max','count']))
