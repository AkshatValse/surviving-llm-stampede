from gp import *
import warnings; warnings.filterwarnings('ignore')
W1=(1260,4860); WJ=(5700,8400)
CFG=[('ols',1.0),('p10',1.0),('ols',0.5),('ols',2.0),('ols',3.0)]
rows=[]
cache={}
def T(rd,fam,mode,sc):
    k=(rd,mode,sc)
    if k not in cache: cache[k]=session_table(rd,fam,mode,sc)
    return cache[k]
for fam in FAM:
  for arm in ['burst','capped','rescue']:
    if arm=='rescue' and fam not in RESFAM: continue
    for _,b in runs_for(fam,arm).iterrows():
        nb=sel(fam,'noburst'); nb=nb[(nb.seed==b.seed)&(nb.rate_mult==b.rate_mult)]
        assert len(nb)==1
        for mode,sc in CFG:
          for thr in ([4.0] if (mode,sc)!=('ols',1.0) else [4.0]):
            tb=T(b.rd,fam,mode,sc); tn=T(nb.iloc[0].rd,fam,mode,sc)
            r=dict(fam=fam,arm=arm,seed=b.seed,rate=b.rate_mult,t_on=b.t_on,ref=f'{mode}x{sc}',run=b.rd.split('results/nova/')[1])
            for nm,w in [('W1',W1),('W1b',(1200,4800)),('WJ',WJ)]:
                n,d,g=gp(tb,w); n2,d2,g2=gp(tn,w)
                r.update({f'{nm}_n':n,f'{nm}_done':d,f'{nm}_good':g,f'{nm}_nob_good':g2,f'{nm}_loss':1-g/g2 if g2 else np.nan})
            r['min_slow_W1']=tb[(tb.arrival_s>=W1[0])&(tb.arrival_s<W1[1])&tb.complete].slow.min()
            r['nob_p5_slow']=tn[tn.complete].slow.quantile(.05); r['nob_med_slow']=tn[tn.complete].slow.median(); r['nob_p95_slow']=tn[tn.complete].slow.quantile(.95)
            rows.append(r)
d=pd.DataFrame(rows); d.to_csv('all_runs_sensitivity.csv',index=False)
d[d.ref=='olsx1.0'].to_csv('per_run_primary.csv',index=False)
pd.set_option('display.width',250,'display.max_rows',500)
for arm in ['burst','capped','rescue']:
    x=d[(d.arm==arm)]
    print(arm, x.groupby('ref')[['W1_loss','W1b_loss','WJ_loss']].agg(['min','max']).round(4).to_string())
p=d[d.ref=='olsx1.0']
print(p[p.arm!='burst'][['fam','arm','seed','rate','W1_loss','WJ_loss','W1_nob_good','WJ_nob_good','WJ_good']].round(4).to_string())
print(p[['nob_p5_slow','nob_med_slow','nob_p95_slow','min_slow_W1']].describe())
