import json, sys, os
import pandas as pd, numpy as np
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
runs = ["20261105-145227","20261105-145240","20261105-145242","20261105-145244","20261105-145244-1","20261105-145244-2","20261105-145246","20261105-145247","20261105-145248"]
for d in runs:
    p = R + d
    meta = json.load(open(p + "/meta.json"))
    ses = pd.read_csv(p + "/sessions.csv")
    req = pd.read_csv(p + "/requests.csv")
    import yaml
    cfg = yaml.safe_load(open(p + "/config_effective.yaml"))
    arm = meta.get("arm"); mult = cfg["arrivals"].get("rate_mult"); seed = meta["seeds"][0]
    out = meta.get("outcome") or {}
    print("=====", d, "arm", arm, "mult", mult, "seed", seed, "status", meta.get("status"), "t_end_s", out.get("t_end_s"), "abort", out.get("abort_reason"))
    print("  session status:", ses["status"].value_counts().to_dict(), " origin:", ses["origin"].value_counts().to_dict())
    print("  request status:", req["status"].value_counts().to_dict())
    if "error_kind" in req.columns:
        print("  request error_kind:", req["error_kind"].value_counts(dropna=False).to_dict())
    print("  http_status:", req["http_status"].value_counts(dropna=False).to_dict())
    # sessions not completed: what are they
    nc = ses[ses["status"] != "completed"]
    print("  non-completed sessions: n=%d, turns_completed mean=%.2f, arrival min=%.1f" % (len(nc), nc["turns_completed"].mean() if len(nc) else float('nan'), nc["arrival_s"].min() if len(nc) else float('nan')))
    # completed sessions with turns_completed != n_turns
    c = ses[ses["status"] == "completed"]
    print("  completed with turns_completed != n_turns:", int((c["turns_completed"] != c["n_turns"]).sum()))
    # t_end vs last request t_complete
    last = req[req["status"]=="ok"].groupby("sid")["t_complete"].max()
    cc = c.set_index("sid")
    dd = (cc["t_end"] - last.reindex(cc.index)).abs()
    print("  |t_end - last ok t_complete| max over completed: %.6g" % dd.max())
    # meta keys of interest
    keys = [k for k in meta.keys()]
    print("  meta keys:", keys)
