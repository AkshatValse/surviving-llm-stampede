import json, subprocess, math
import pandas as pd, numpy as np
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR, LM = pred["lambda_ref"], pred["lambda_miss_model"]
d = pd.read_csv(W + "/results/agentload_analysis_r16_mirror/20261105-173136/mirror_runs.csv")
b = d[d["arm"]=="burst"].sort_values(["rate_mult","seed"], ascending=[False, True])
# W6
for s in (0,1,2):
    a = float(b[(b.rate_mult==1.35)&(b.seed==s)].wave_time.iloc[0]); c = float(b[(b.rate_mult==1.65)&(b.seed==s)].wave_time.iloc[0])
    fa = pred["cells"]["1.35"]["seeds"][str(s)]["burst_timing"]["median"]; fc = pred["cells"]["1.65"]["seeds"][str(s)]["burst_timing"]["median"]
    print(f"W6 seed {s}: wave 1.35x {a:.1f} < 1.65x {c:.1f}: {a<c}; measured shift {c-a:.1f} s; model F shift {fc-fa:.1f} s; diff {c-a-(fc-fa):+.1f} s; in tagged 270-330: {270<=c-a<=330}")
# M4 as an implied completion threshold, and S vs conservation
for _, r in b.iterrows():
    sd = pred["cells"][f"{r.rate_mult:g}"]["seeds"][str(int(r.seed))]
    SF, SQS = r.S_F, r.S_QS
    thr = (r.lambda_plan_slope_window - SF + LM) / 2 / LR
    print(f"{r.rate_mult}x s{int(r.seed)}: M4 holds iff S > {(SF+SQS)/2:.5f}; S/(lam_plan-lam_miss) = {r.slope/SQS:.2f}; "
          f"S - S_F = {r.slope-SF:+.5f} ({100*(r.slope/SF-1):+.1f}%); M4-equivalent completion ceiling ~{thr:.3f} lam_ref; "
          f"late {r.late_rate:.3f}; W8 margin {0.25-abs(r.late_rate-sd['windows']['late']['completion_over_lam_ref']):.3f}")
print("noise (standard workload, frozen):", pred["noise_standard_workload"]["noise"])
