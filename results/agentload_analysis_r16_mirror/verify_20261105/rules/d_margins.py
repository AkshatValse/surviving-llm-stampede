import json, math, subprocess
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
S = r"C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/rules/"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR = float(pred["lambda_ref"]); LM = float(pred["lambda_miss_model"])
print("timing calibration:", {k: v for k, v in pred["timing_calibration_standard_workload"].items() if k != "runs"})
df = pd.read_csv(S+"recomputed.csv").set_index("key")
sc = pd.read_csv(W + "/results/agentload_analysis_r16_mirror/20261105-173136/mirror_runs.csv")
sc["key"] = sc["run_dir"].str.replace("\\","/",regex=False).str.split("/").str[-1]; sc = sc.set_index("key")
thr_bo = 0.30*LR*1200; thr_late = 0.85*LR*2100; thr_curve_bo = 0.85*LR*1200
print(f"lambda_ref {LR}; M1 count threshold {thr_bo:.3f} (max count {math.floor(thr_bo)}); M3 count threshold {thr_late:.3f} (max {math.floor(thr_late)}); CURVE blackout count >= {thr_curve_bo:.3f}")
out = []
for k, r in df[df["arm"]=="burst"].sort_values(["mult","seed"], ascending=[False,True]).iterrows():
    sd = pred["cells"][f"{r.mult:g}"]["seeds"][str(int(r.seed))]
    F = sd["burst_timing"]["median"]; Fc = sd["burst_timing"]["median_calibrated"]
    SF = sd["windows"]["slope"]["slope"]; SQS = r.lam_plan - LM
    Fl = sd["windows"]["late"]["completion_over_lam_ref"]; Fb = sd["windows"]["blackout"]["completion_over_lam_ref"]; FP = sd["windows"]["w5700"]["P_served_mean"]
    assert abs(F - sc.loc[k,"F_wave"])<1e-9 and abs(Fc - sc.loc[k,"F_wave_cal"])<1e-9 and abs(SF - sc.loc[k,"S_F"])<1e-12 and abs(SQS - sc.loc[k,"S_QS"])<1e-12
    tol2 = 0.15*(F-1200); d2 = abs(r.wave-F)
    tol5 = 0.05*(Fc-1200); d5 = abs(r.wave-Fc)
    dF = abs(r.S-SF); dQ = abs(r.S-SQS); mid = 0.5*(SF+SQS)
    o = dict(cell=f"{r.mult:g}x", seed=int(r.seed),
             M1=f"{r.blackout:.4f} vs 0.30 (n={r.blackout_n} vs max {math.floor(thr_bo)}; +{math.floor(thr_bo)-int(r.blackout_n)+1} to flip)",
             M2=f"|{r.wave:.1f}-{F:.1f}|={d2:.1f} vs tol {tol2:.1f} (margin {tol2-d2:.1f} s; ratio (w-1200)/(F-1200)={(r.wave-1200)/(F-1200):.4f})",
             M3=f"{r.late:.4f} vs 0.85 (n={r.late_n} vs max {math.floor(thr_late)}; +{math.floor(thr_late)-int(r.late_n)+1} to flip)",
             M4=f"S={r.S:.5f} S_F={SF:.5f} S_QS={SQS:.5f}: |S-S_F|={dF:.5f} |S-S_QS|={dQ:.5f}; midpoint {mid:.5f}, margin S-mid={r.S-mid:+.5f}/s = {(r.S-mid)*2700:+.1f} sessions over 2700 s",
             STUCK=f"hit_eval {r.hit_eval:.4f} vs 0.2",
             CURVE=f"blackout {r.blackout:.3f} late {r.late:.3f} (both >= 0.85 needed)",
             W5=f"|{r.wave:.1f}-{Fc:.1f}|={d5:.1f} vs tol {tol5:.1f} -> {'PASS' if d5<=tol5 else 'FAIL'} (margin {tol5-d5:+.1f} s)",
             W7=f"P {r.P_served:.1f} vs F {FP:.1f}: {100*(r.P_served/FP-1):+.2f}% (tol 5%) -> {'PASS' if abs(r.P_served-FP)<=0.05*FP else 'FAIL'}",
             W8=f"late {r.late:.4f} vs F {Fl:.4f}: diff {r.late-Fl:+.4f} (tol 0.25) -> {'PASS' if abs(r.late-Fl)<=0.25 else 'FAIL'}",
             blackout_vs_F=f"{r.blackout:.4f} vs F {Fb:.4f} (ratio {r.blackout/Fb if Fb else float('inf'):.2f})")
    out.append(o)
    print("-----", o["cell"], "seed", o["seed"])
    for kk, vv in o.items():
        if kk not in ("cell","seed"): print("  ", kk, ":", vv)
