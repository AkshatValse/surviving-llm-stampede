"""Exact decomposition of the M4 slope: N = N0 + A - C on the window, so S = slope(A bins) - slope(C bins)."""
import json, math, subprocess
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR, LM = pred["lambda_ref"], pred["lambda_miss_model"]
key = {"20261105-145227":(1.65,0),"20261105-145244-2":(1.65,1),"20261105-145240":(1.65,2),
       "20261105-145244-1":(1.35,0),"20261105-145246":(1.35,1),"20261105-145244":(1.35,2)}
def binmean_count(times, edges):
    # mean over each bin of the cumulative count of events since edges[0] (right-continuous step), exact
    t = np.sort(times[(times >= edges[0]) & (times < edges[-1])])
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        before = np.searchsorted(t, a, side="right")
        inside = t[(t >= a) & (t < b)]
        out.append(before + np.sum(b - inside) / (b - a))
    return np.array(out)
for d, (m, s) in key.items():
    ses = pd.read_csv(R + d + "/sessions.csv")
    edges = np.arange(6000.0, 8700.0 + 1e-9, 10.0); c = 0.5 * (edges[:-1] + edges[1:])
    A = binmean_count(ses["arrival_s"].to_numpy(float), edges)
    C = binmean_count(ses[ses.status == "completed"]["t_end"].to_numpy(float), edges)
    SA, SC = np.polyfit(c, A, 1)[0], np.polyfit(c, C, 1)[0]
    sd = pred["cells"][f"{m:g}"]["seeds"][str(s)]
    SF = sd["windows"]["slope"]["slope"]; lp = sd["windows"]["slope"]["lam_plan"]; SQS = lp - LM; mid = 0.5 * (SF + SQS)
    print(f"{m}x s{s}: S_A {SA:.5f} - S_C {SC:.5f} = {SA-SC:.5f}; M4 <=> S_C < S_A - mid = {SA-mid:.5f}/s = {(SA-mid)/LR:.3f} lam_ref "
          f"(OLS-weighted completion rate S_C = {SC/LR:.3f} lam_ref; M3 late {((ses.status=='completed')&(ses.t_end>=6600)&(ses.t_end<8700)).sum()/2100/LR:.3f})")
