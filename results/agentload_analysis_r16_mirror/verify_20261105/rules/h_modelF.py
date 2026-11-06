"""Re-run model F (tagged code, no file writes) on the frozen plans; per-session timing ratio as in the registered calibration."""
import sys, os, json, math, subprocess
sys.dont_write_bytecode = True
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
sys.path[:0] = [W + "/src", W]
os.chdir(W)
import numpy as np, pandas as pd
from analysis.theory.icml import mirror_predict as mp
from analysis.theory.icml.cut_predict import plan_fifo, backlog_stats, lam_ref
from analysis.theory.icml.trap_renewal import trap_costs
from analysis.theory.fluid_rigorous.model import open_equilibria, summarize_curve
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
lr = lam_ref(); m0, m, info = mp.capped_model(); tc = trap_costs(m); cs = summarize_curve(m); zbar = float(m.wl.zbar)
print("lam_ref", lr, "frozen", pred["lambda_ref"], "| lam_miss_model", tc.lam_miss, "frozen", pred["lambda_miss_model"])
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
key = {(1.65,0):"20261105-145227",(1.65,1):"20261105-145244-2",(1.65,2):"20261105-145240",
       (1.35,0):"20261105-145244-1",(1.35,1):"20261105-145246",(1.35,2):"20261105-145244"}
for (mult, seed), d in key.items():
    lam = mult * lr
    n1 = float(open_equilibria(cs, lam).n1)
    lat_good = (n1 / lam - (tc.ET - 1.0) * zbar) / tc.ET
    plan, cfg, rate = mp.build_plan(seed, mult, burst=True)
    pf = plan_fifo(plan, tc, lat_good)
    bt = mp.burst_timing(plan, pf["ends"])
    bs = backlog_stats(pf["starts"], pf["ends"], 6000.0, 8700.0)
    late = backlog_stats(pf["starts"], pf["ends"], 6600.0, 8700.0)["completion_rate"] / lr
    fz = pred["cells"][f"{mult:g}"]["seeds"][str(seed)]
    ok = (abs(bt["median"] - fz["burst_timing"]["median"]) < 1e-6 and abs(bs["slope"] - fz["windows"]["slope"]["slope"]) < 1e-9
          and abs(late - fz["windows"]["late"]["completion_over_lam_ref"]) < 1e-9)
    # per-session ratio as the registered calibration statistic (burst sessions completed, model end > 3000 s)
    ses = pd.read_csv(R + d + "/sessions.csv")
    pred_end = {p.sid: e for p, e in zip(plan, pf["ends"])}
    b = ses[(ses["origin"]=="burst")&(ses["status"]=="completed")]
    pairs = [(float(t), pred_end.get(int(s), math.inf)) for s, t in zip(b["sid"], b["t_end"])]
    pairs = [(a, e) for a, e in pairs if np.isfinite(e) and e > 3000.0]
    ratio = np.array([(a - 1200.0) / (e - 1200.0) for a, e in pairs])
    # per-session ratio over all burst sessions too
    print(f"{mult}x s{seed}: model F reproduces frozen (median, slope, late): {ok}; frozen median {fz['burst_timing']['median']:.1f}; "
          f"calibration statistic on this MIRROR run: median ratio {np.median(ratio):.4f} over n={len(ratio)} (registered standard-workload factor 0.9223, range 0.9125-0.9327)")
