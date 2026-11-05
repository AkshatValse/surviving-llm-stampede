from gp import *
W1=(1260,4860); WJ=(5700,8400)
rows=[]
for fam in FAM:
    for _,b in sel(fam,'burst').iterrows():
        nb=sel(fam,'noburst'); nb=nb[(nb.seed==b.seed)&(nb.rate_mult==b.rate_mult)]
        assert len(nb)==1,(fam,b.seed,b.rate_mult,len(nb))
        for mode,sc in [('ols',1.0)]:
            tb=session_table(b.rd,fam,mode,sc); tn=session_table(nb.iloc[0].rd,fam,mode,sc)
            assert set(tb.idx)==set(tn.idx) and np.allclose(tb.set_index('idx').arrival_s.sort_index(),tn.set_index('idx').arrival_s.sort_index()),'CRN'
            r=dict(fam=fam,arm='burst',seed=b.seed,rate=b.rate_mult,run=b.rd.split('results/nova/')[1])
            for nm,w in [('W1',W1),('WJ',WJ)]:
                n,d,g=gp(tb,w); n2,d2,g2=gp(tn,w)
                r.update({f'{nm}_n':n,f'{nm}_burst_done':d,f'{nm}_burst_good':g,f'{nm}_nob_good':g2,f'{nm}_loss':1-g/g2 if g2 else np.nan})
            rows.append(r)
d=pd.DataFrame(rows); d.to_csv('burst_runs.csv',index=False)
pd.set_option('display.width',250)
print(d.drop(columns='run').round(4).to_string())
print({f:(refs(f)[0].round(5),len(refs(f)[1])) for f in FAM})
print(d.W1_loss.min(),d.W1_loss.max(),d.WJ_loss.min(),d.WJ_loss.max())
