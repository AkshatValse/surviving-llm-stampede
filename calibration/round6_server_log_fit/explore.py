import sys
import numpy as np
import pandas as pd

df = pd.read_pickle(sys.argv[1])
out = []
for job, g in df.groupby("job", sort=False):
    g = g.sort_values("line").reset_index(drop=True)
    prev = g.shift(1)
    g["prev_kind"] = prev["kind"]
    g["prev_pending"] = prev["pending"]
    g["prev_new_tok"] = prev["new_tok"]
    g["prev_running"] = prev["running"]
    g["prev_token"] = prev["token"]
    g["prev_epoch"] = prev["epoch"]
    out.append(g)
df = pd.concat(out, ignore_index=True)

P = df[df.kind == "P"].copy()
P["gap"] = P.new_tok / P.thr
D = df[df.kind == "D"].copy()
D["it"] = D.running / D.thr

print("P total", len(P), " prev is P:", (P.prev_kind == "P").sum(),
      " prev P & pending>0:", ((P.prev_kind == "P") & (P.prev_pending > 0)).sum())
pc = P[(P.prev_kind == "P") & (P.prev_pending > 0) & (P.prev_epoch == P.epoch)]
print(pc.groupby("job").size())
print(pc[["new_seq", "new_tok", "cached", "running", "gap"]].describe().T)
print("new_tok==8192 share in clean:", (pc.new_tok == 8192).mean())

# decode clean
dc = D[(D.prev_kind == "D") & (D.prev_running == D.running) & (D.running > 0) & (D.token > 0) & (D.prev_epoch == D.epoch)].copy()
dc["dtok"] = dc.token - dc.prev_token
print("D total", len(D), "clean", len(dc))
print(dc.groupby("job").size())
print("R distribution of clean D:")
print(dc.running.value_counts().sort_index().to_string())
dc["dtok_per_R"] = dc.dtok / dc.running
print("dtok/R (expect ~40):")
print(dc.dtok_per_R.describe())
print(dc[["running", "token", "it", "dtok"]].describe().T)
