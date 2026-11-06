"""Independent recomputation of the MIRROR measures from raw run files (no import of analysis.*)."""
import json, math, subprocess
import numpy as np, pandas as pd, yaml
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
runs = ["20261105-145227","20261105-145240","20261105-145242","20261105-145244","20261105-145244-1","20261105-145244-2","20261105-145246","20261105-145247","20261105-145248"]
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR = float(pred["lambda_ref"]); LM = float(pred["lambda_miss_model"])
scored = pd.read_csv(W + "/results/agentload_analysis_r16_mirror/20261105-173136/mirror_runs.csv")
scored["key"] = scored["run_dir"].str.replace("\\","/",regex=False).str.split("/").str[-1]
scored = scored.set_index("key")

def step_mean(t_ev, v_after, a, b):
    i0 = np.searchsorted(t_ev, a, side="right"); cur = v_after[i0-1] if i0>0 else 0.0
    i1 = np.searchsorted(t_ev, b, side="left")
    times = np.concatenate([[a], t_ev[i0:i1], [b]]); vals = np.concatenate([[cur], v_after[i0:i1]])
    return float(np.sum(vals*np.diff(times))/(b-a))

def backlog_events(ses, run_end):
    arr = ses["arrival_s"].to_numpy(float); te = ses["t_end"].to_numpy(float)
    ended = ses["status"].isin(["completed","failed"]).to_numpy() & np.isfinite(te)
    dep = np.where(ended, te, run_end)
    t = np.concatenate([arr, dep]); d = np.concatenate([np.ones(len(arr)), -np.ones(len(dep))])
    o = np.lexsort((-d, t)); return t[o], np.cumsum(d[o])

def slope_exact(ses, run_end, w0, w1, dt=10.0):
    t, v = backlog_events(ses, run_end)
    edges = np.arange(w0, w1 + 1e-9, dt)
    means = np.array([step_mean(t, v, edges[j], edges[j+1]) for j in range(len(edges)-1)])
    cent = 0.5*(edges[:-1]+edges[1:])
    return float(np.polyfit(cent, means, 1)[0]), len(means), means

def slope_1s(ses, w0, w1, dt=10):   # model-F / measured.window_stats estimator: completed only depart, 1-s sampling
    st = np.sort(ses["arrival_s"].to_numpy(float))
    en = np.sort(np.where(ses["status"]=="completed", ses["t_end"].to_numpy(float), np.inf))
    tt = np.arange(w0, w1, 1.0)
    n = np.searchsorted(st, tt, side="right") - np.searchsorted(en, tt, side="right")
    nb = len(tt)//dt; m = n[:nb*dt].reshape(nb, dt).mean(1); c = w0 + dt*(np.arange(nb)+0.5)
    return float(np.polyfit(c, m, 1)[0])

rows = []
for d in runs:
    p = R + d
    meta = json.load(open(p+"/meta.json")); cfg = yaml.safe_load(open(p+"/config_effective.yaml"))
    ses = pd.read_csv(p+"/sessions.csv"); req = pd.read_csv(p+"/requests.csv"); plan = pd.read_csv(p+"/plan.csv", float_precision="round_trip")
    arm = meta["arm"]; mult = float(cfg["arrivals"]["rate_mult"]); seed = int(meta["seeds"][0])
    run_end = float(meta["outcome"]["t_end_s"]); lr = float(meta["lambda_ref_resolved"])
    comp = ses[ses["status"]=="completed"]; te = comp["t_end"].to_numpy(float)
    bo_n = int(((te>=2400)&(te<3600)).sum()); late_n = int(((te>=6600)&(te<8700)).sum())
    b = comp[comp["origin"]=="burst"]["t_end"].to_numpy(float); b = b[np.isfinite(b)&(b<=8700)]
    wave = float(np.median(b)) if len(b)>=100 else math.nan
    S, nb, _ = slope_exact(ses, run_end, 6000.0, 8700.0)
    S1 = slope_1s(ses, 6000.0, 8700.0)
    lam_plan = ((plan["origin"]=="base")&(plan["arrival_s"]>=6000)&(plan["arrival_s"]<8700)).sum()/2700.0
    ok = req[req["status"]=="ok"].copy()
    ok["pe"] = ok["prompt_tokens"].where(ok["prompt_tokens"].notna(), ok["prompt_tokens_client"]).astype(float)
    ok["ce"] = ok["cached_tokens"].fillna(0).astype(float)
    sel = ok[(ok["t_complete"]>=5700)&(ok["t_complete"]<run_end+1e-9)]
    hit_eval = float(((sel["ce"]/sel["pe"])>0.5).mean())
    sel2 = ok[(ok["t_complete"]>=5700)&(ok["t_complete"]<8700)]
    P_served = float(sel2["prompt_tokens"].fillna(0).astype(int).mean())
    rows.append(dict(key=d, arm=arm, mult=mult, seed=seed, run_end=run_end, lr=lr, blackout_n=bo_n, late_n=late_n,
                     blackout=bo_n/1200/lr, late=late_n/2100/lr, wave=wave, burst_done=len(b), S=S, S_1s=S1, nb=nb,
                     lam_plan=lam_plan, hit_eval=hit_eval, P_served=P_served))
df = pd.DataFrame(rows).set_index("key")
# compare with the scorer
cmp = [("blackout_n","blackout_n"),("late_n","late_n"),("wave","wave_time"),("burst_done","burst_completed"),("S","slope"),
       ("lam_plan","lambda_plan_slope_window"),("hit_eval","hit_eval"),("P_served","P_served_5700_8700"),("run_end","run_end_s")]
for k in df.index:
    diffs = {a: (df.loc[k,a], scored.loc[k,b]) for a,b in cmp}
    bad = {a: v for a, v in diffs.items() if not (isinstance(v[0], float) and math.isnan(v[0]) and math.isnan(v[1])) and abs(float(v[0])-float(v[1]))>1e-9*max(1,abs(float(v[1])))}
    print(k, df.loc[k,"arm"], df.loc[k,"mult"], df.loc[k,"seed"], "MISMATCH" if bad else "all match", bad)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(df[["arm","mult","seed","blackout_n","blackout","late_n","late","wave","burst_done","S","S_1s","lam_plan","hit_eval","P_served"]].to_string())
df.to_csv(r"C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/rules/recomputed.csv")
