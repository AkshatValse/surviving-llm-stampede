import json
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
runs = {"20261105-145227":"b1.65s0","20261105-145244-2":"b1.65s1","20261105-145240":"b1.65s2","20261105-145244-1":"b1.35s0",
        "20261105-145246":"b1.35s1","20261105-145244":"b1.35s2","20261105-145242":"n1.65s0","20261105-145247":"n1.65s1","20261105-145248":"n1.65s2"}
for d, name in runs.items():
    req = pd.read_csv(R + d + "/requests.csv")
    ok = req[req["status"]=="ok"].copy(); ok["h"] = (ok["cached_tokens"].fillna(0)/ok["prompt_tokens"]) > 0.5
    fu = ok[ok["turn"]>=2]
    out = []
    for a, b in [(600,1200),(1200,1800),(1800,2400),(2400,3600),(3600,5700),(5700,8700)]:
        s = fu[(fu["t_complete"]>=a)&(fu["t_complete"]<b)]
        out.append(f"[{a},{b}):{s['h'].mean():.3f}(n={len(s)})")
    print(name, "follow-up hit:", " ".join(out))
