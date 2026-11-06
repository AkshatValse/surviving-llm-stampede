import json, math, subprocess
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR = float(pred["lambda_ref"]); LM = float(pred["lambda_miss_model"])
burst = {"20261105-145227":(1.65,0),"20261105-145244-2":(1.65,1),"20261105-145240":(1.65,2),
         "20261105-145244-1":(1.35,0),"20261105-145246":(1.35,1),"20261105-145244":(1.35,2)}
def step_mean(t_ev, v_after, a, b):
    i0 = np.searchsorted(t_ev, a, side="right"); cur = v_after[i0-1] if i0>0 else 0.0
    i1 = np.searchsorted(t_ev, b, side="left")
    times = np.concatenate([[a], t_ev[i0:i1], [b]]); vals = np.concatenate([[cur], v_after[i0:i1]])
    return float(np.sum(vals*np.diff(times))/(b-a))
def ev(ses, run_end):
    arr = ses["arrival_s"].to_numpy(float); te = ses["t_end"].to_numpy(float)
    ended = ses["status"].isin(["completed","failed"]).to_numpy() & np.isfinite(te)
    dep = np.where(ended, te, run_end)
    t = np.concatenate([arr, dep]); d = np.concatenate([np.ones(len(arr)), -np.ones(len(dep))])
    o = np.lexsort((-d, t)); return t[o], np.cumsum(d[o])
def slope(t, v, w0, w1, dt=10.0):
    nb = int(math.floor((w1-w0)/dt+1e-9)); edges = w0 + dt*np.arange(nb+1)
    m = np.array([step_mean(t, v, edges[j], edges[j+1]) for j in range(nb)]); c = 0.5*(edges[:-1]+edges[1:])
    return float(np.polyfit(c, m, 1)[0])
for k, (mult, seed) in burst.items():
    p = R + k
    meta = json.load(open(p+"/meta.json")); run_end = float(meta["outcome"]["t_end_s"])
    ses = pd.read_csv(p+"/sessions.csv"); plan = pd.read_csv(p+"/plan.csv", float_precision="round_trip")
    te = np.sort(ses[ses["status"]=="completed"]["t_end"].to_numpy(float))
    sd = pred["cells"][f"{mult:g}"]["seeds"][str(seed)]
    print(f"===== {mult}x seed {seed} ({k})")
    # completions nearest the window edges
    for edge in (2400.0, 3600.0, 6600.0, 8700.0):
        below = te[te < edge]; above = te[te >= edge]
        print(f"   edge {edge:.0f}: nearest completion below {edge - below.max() if len(below) else float('nan'):.2f} s before, above {above.min() - edge if len(above) else float('nan'):.2f} s after")
    print(f"   completions in [8700, run_end={run_end:.3f}]: {int(((te>=8700)&(te<=run_end)).sum())}")
    def cnt(a, b): return int(((te>=a)&(te<b)).sum())
    for name, (a, b, thr) in {"M1 blackout": (2400.,3600.,0.30), "M3 late": (6600.,8700.,0.85)}.items():
        base = cnt(a, b)
        res = []
        for da, db in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-5,0),(5,0),(-10,0),(10,0),(-30,0),(30,0),(-60,0),(60,0),(0,-10),(0,-30),(0,-60)]:
            n = cnt(a+da, b+db); r = n/(b+db-a-da)/LR
            res.append(f"[{a+da:.0f},{b+db:.0f}):{n}->{r:.4f}{'*' if (r<=thr) != (base/(b-a)/LR<=thr) else ''}")
        print(f"   {name} base {base} -> {base/(b-a)/LR:.4f}; shifts: " + " ".join(res))
    # M4 under window perturbations
    t, v = ev(ses, run_end)
    SF = sd["windows"]["slope"]["slope"]
    for w0, w1 in [(6000,8700),(5999,8700),(6001,8700),(6000,8699),(6010,8700),(5990,8700),(6000,8690),(6060,8700),(5940,8700),(6300,8700),(5700,8700),(6000,8400),(6600,8700)]:
        S = slope(t, v, float(w0), float(w1))
        lp = ((plan["origin"]=="base")&(plan["arrival_s"]>=w0)&(plan["arrival_s"]<w1)).sum()/(w1-w0)
        qs = lp - LM
        print(f"   M4 window [{w0},{w1}): S={S:.5f} (S_F frozen {SF:.5f}; QS={qs:.5f}) -> |S-S_F|<|S-S_QS|: {abs(S-SF)<abs(S-qs)}  margin to midpoint {S-0.5*(SF+qs):+.5f}")
    # wave perturbation: drop/add one burst completion at extremes
    b = np.sort(ses[(ses["origin"]=="burst")&(ses["status"]=="completed")]["t_end"].to_numpy(float))
    F = sd["burst_timing"]["median"]
    print(f"   wave median {np.median(b):.1f}; drop earliest {np.median(b[1:]):.1f}; drop latest {np.median(b[:-1]):.1f}; F {F:.1f}; tol {0.15*(F-1200):.1f}")
