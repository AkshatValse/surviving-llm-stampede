import json, subprocess
import numpy as np
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
bins = json.load(open(W + "/results/agentload_analysis_r16_mirror/20261105-173136/mirror_bins.json"))
key = {"20261105-145227":(1.65,0),"20261105-145244-2":(1.65,1),"20261105-145240":(1.65,2),
       "20261105-145244-1":(1.35,0),"20261105-145246":(1.35,1),"20261105-145244":(1.35,2)}
starts = pred["cells"]["1.65"]["seeds"]["0"]["completion_bins"]["bin_start"]
print("bin starts:", " ".join(f"{int(s):>5d}" for s in starts))
for d, (m, s) in key.items():
    meas = next(v for k, v in bins.items() if k.replace("\\","/").endswith(d))
    F = pred["cells"][f"{m:g}"]["seeds"][str(s)]["completion_bins"]["rate_over_lam_ref"]
    print(f"{m}x s{s} meas:", " ".join(f"{x:5.2f}" for x in meas))
    print(f"{m}x s{s} F   :", " ".join(f"{x:5.2f}" for x in F))
    a = pred["cells"][f"{m:g}"]["asymptotics"]
    print(f"   asymptotic D/lam_ref {a['D_over_lam_ref']:.3f}; F late {pred['cells'][f'{m:g}']['seeds'][str(s)]['windows']['late']['completion_over_lam_ref']:.3f}; measured peak bin {starts[int(np.argmax(meas))]:.0f} ({max(meas):.2f}); F peak {pred['cells'][f'{m:g}']['seeds'][str(s)]['peak']}")
