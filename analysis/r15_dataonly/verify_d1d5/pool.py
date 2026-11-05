import warnings;warnings.filterwarnings('ignore')
import pandas as pd,numpy as np
O='C:/Users/Akshat/AppData/Local/Temp/claude/736ce9da4f625ecb/9863ad4b-593e-4883-b8f4-501c30190dc6/scratchpad/verify/D1D5'
R='C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/'
b=pd.read_csv(O+'/runs_base.csv')
out=[]
for _,x in b.iterrows():
    d=R+x['dir'];m=pd.read_csv(d+'/metrics.csv',usecols=['t_s','name','value'])
    row=dict(pull=x['pull'],run_ts=x['run_ts'])
    if m.name.str.startswith('sglang:').any():
        g=lambda n: m[m.name=='sglang:'+n].groupby('t_s').value.mean()
        mx=g('max_total_num_tokens');used=g('kv_used_tokens');ev=g('kv_evictable_tokens');run=g('num_running_reqs');q=g('num_queue_reqs')
        sel=lambda s:s[(s.index>=5700)&(s.index<8700)]
        row.update(engine='sglang',pool=mx.iloc[-1],run_share=sel(used).mean()/mx.iloc[-1],evict_share=sel(ev).mean()/mx.iloc[-1],running=sel(run).mean(),queue=sel(q).mean(),n_snap=len(sel(used)))
        # share by dense timeline
        row['run_share_med']=sel(used).median()/mx.iloc[-1]
    elif m.name.str.startswith('vllm:').any():
        k=m[m.name=='vllm:kv_cache_usage_perc'].groupby('t_s').value.mean()
        r=m[m.name=='vllm:num_requests_running'].groupby('t_s').value.mean()
        sel=lambda s:s[(s.index>=5700)&(s.index<8700)]
        row.update(engine='vllm',run_share=sel(k).mean(),running=sel(r).mean(),n_snap=len(sel(k)))
    out.append(row)
o=pd.DataFrame(out);j=b.merge(o,on=['pull','run_ts']);j.to_csv(O+'/runs_pool.csv',index=False)
pd.set_option('display.width',250)
print(j[j.stuck][['label','pull','seed','engine','pool','run_share','run_share_med','evict_share','running','queue','hit_eval']].to_string())
