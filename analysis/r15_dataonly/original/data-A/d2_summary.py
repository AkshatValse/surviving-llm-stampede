"""Summarize d2_runs.csv: per (stat, cell, rate, arm) mean and range across seeds of goodput and the paired loss vs NOBURST."""
import os, sys
import numpy as np
import pandas as pd

S = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(f"{S}/d2_runs.csv")
d["armx"] = np.where(d.label.str.contains(r"-b\d+$", regex=True), "burst_n" + d.burst_n.fillna(0).astype(int).astype(str),
                     np.where(d.label.str.contains("shed"), d.label.str.split("-").str[-1].radd("shed_"), d.arm))
nb = d[d.arm == "noburst"].set_index(["stat", "cell", "rate_mult", "seed"])
W = ["H1", "J", "JC", "ALL"]
for w in W:
    ref = nb[f"G_{w}"]
    key = pd.MultiIndex.from_frame(d[["stat", "cell", "rate_mult", "seed"]])
    d[f"loss_{w}"] = 1 - d[f"G_{w}"].values / ref.reindex(key).values
d.to_csv(f"{S}/d2_runs_with_loss.csv", index=False)


def fmt(x):
    x = x.dropna()
    if not len(x):
        return "-"
    return f"{x.mean():.1f} [{x.min():.1f}, {x.max():.1f}]"


def fmtp(x):
    x = x.dropna()
    if not len(x):
        return "-"
    return f"{100*x.mean():.0f}% [{100*x.min():.0f}, {100*x.max():.0f}]"


stat = sys.argv[1] if len(sys.argv) > 1 else "min"
e = d[d.stat == stat]
order = {"noburst": 0, "burst": 1, "capped": 2, "rescue": 3}
rows = []
for (cell, rate, arm), g in e.groupby(["cell", "rate_mult", "armx"]):
    rows.append(dict(cell=cell, rate=rate, arm=arm, n=len(g), G_H1=fmt(g.G_H1), loss_H1=fmtp(g.loss_H1),
                     G_J=fmt(g.G_J), loss_J=fmtp(g.loss_J), G_JC=fmt(g.G_JC), loss_JC=fmtp(g.loss_JC),
                     G_ALL=fmt(g.G_ALL), loss_ALL=fmtp(g.loss_ALL),
                     compl_J=f"{g.compl_J.mean():.2f}", medslow_J=f"{g.medslow_J.median():.2f}",
                     compl_H1=f"{g.compl_H1.mean():.2f}", medslow_H1=f"{g.medslow_H1.median():.2f}",
                     _o=order.get(arm, 4)))
t = pd.DataFrame(rows).sort_values(["cell", "rate", "_o", "arm"]).drop(columns="_o")
cols=list(t.columns); print("| "+" | ".join(cols)+" |"); print("|"+"---|"*len(cols))
for _, r in t.iterrows(): print("| "+" | ".join(str(r[c]) for c in cols)+" |")
