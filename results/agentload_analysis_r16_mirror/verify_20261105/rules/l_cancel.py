import json
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
for d in ["20261105-145227","20261105-145240","20261105-145242","20261105-145244","20261105-145244-1","20261105-145244-2","20261105-145246","20261105-145247","20261105-145248"]:
    ses = pd.read_csv(R + d + "/sessions.csv"); req = pd.read_csv(R + d + "/requests.csv")
    c = ses[ses.status=="cancelled"]
    rc = req[req.status=="cancelled"]
    print(d, f"cancelled sessions t_end: min {c.t_end.min():.3f} max {c.t_end.max():.3f} (NaN {int(c.t_end.isna().sum())}); "
          f"cancelled requests t_complete min {rc.t_complete.min():.3f}; t_send min {rc.t_send.min():.1f}; "
          f"cancelled sessions with a request in flight: {int(c.sid.isin(rc.sid).sum())}/{len(c)} (others asleep in tool time)")
