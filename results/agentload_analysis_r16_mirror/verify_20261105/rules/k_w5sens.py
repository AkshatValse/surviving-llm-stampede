import json, subprocess
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
key = {"20261105-145227":(1.65,0),"20261105-145244-2":(1.65,1),"20261105-145240":(1.65,2),
       "20261105-145244-1":(1.35,0),"20261105-145246":(1.35,1),"20261105-145244":(1.35,2)}
for d, (m, s) in key.items():
    ses = pd.read_csv(R + d + "/sessions.csv")
    t = np.sort(ses[(ses.origin=="burst")&(ses.status=="completed")]["t_end"].to_numpy(float))
    Fc = pred["cells"][f"{m:g}"]["seeds"][str(s)]["burst_timing"]["median_calibrated"]; tol = 0.05*(Fc-1200)
    res = []
    for k in range(0, 4):
        up = np.median(t[k:]) if k else np.median(t)        # drop k earliest (median moves later)
        dn = np.median(t[:len(t)-k]) if k else np.median(t) # drop k latest (median moves earlier)
        res.append(f"k={k}: later {up:.1f} ({'P' if abs(up-Fc)<=tol else 'F'}), earlier {dn:.1f} ({'P' if abs(dn-Fc)<=tol else 'F'})")
    print(f"{m}x s{s}: F_cal {Fc:.1f} tol {tol:.1f} [{Fc-tol:.1f}, {Fc+tol:.1f}]; order stats 99-102: {t[98]:.1f} {t[99]:.1f} {t[100]:.1f} {t[101]:.1f}; " + "; ".join(res))
