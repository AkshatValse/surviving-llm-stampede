"""Gap slope against completion time: the right model-F constant is gamma/z = 1 - 1/z, not gamma.

analysis/theory/icml/measured.py regresses each follow-up turn's gap (completion minus the same session's previous
completion) on the turn's completion time t. In model F a turn that completes at t joined at u = f^{-1}(t), and the gap
is V(u) with V(u) ~ gamma*u and t ~ z*u, so the gap grows at gamma/z per second of completion time. Theorem 1(c)'s
V(t)/t -> gamma is indexed by the join time. This script recomputes the measured/predicted ratios of
results/theory/icml/trap_check.json with gamma/z (found by an independent review of the reframe draft, 2026-11-05).

Usage: PYTHONPATH="src;." python -m analysis.theory.icml.gap_slope_completion_time
Writes results/theory/icml/gap_slope_completion_time.json and prints the summary.
"""
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")
OUT = os.path.join(ROOT, "results", "theory", "icml", "gap_slope_completion_time.json")


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    groups = []
    ratios = {"e2": [], "e0b": []}
    ratios_gamma = {"e2": [], "e0b": []}
    for g in d["groups"]:
        a = g["asym"]
        z, gamma = a["z"], a["gamma"]
        pred = gamma / z
        meas = [m for m in g["measured"]["gap_med_slope"]]
        r = [m / pred for m in meas]
        r_gamma = [m / gamma for m in meas]
        ratios[g["kind"]].extend(r)
        ratios_gamma[g["kind"]].extend(r_gamma)
        groups.append(dict(kind=g["kind"], label=g["label"], rate_mult=g["rate_mult"], rho=a["rho"], z=z, gamma=gamma,
                           gamma_over_z=pred, measured=meas, ratio=r))
    summ = {}
    for k in ("e2", "e0b"):
        x = np.array(ratios[k])
        y = np.array(ratios_gamma[k])
        summ[k] = dict(n=int(len(x)), median=float(np.median(x)), mean=float(np.mean(x)), min=float(x.min()),
                       max=float(x.max()), median_vs_gamma=float(np.median(y)), mean_vs_gamma=float(np.mean(y)),
                       min_vs_gamma=float(y.min()), max_vs_gamma=float(y.max()))
    out = dict(note=__doc__.strip().splitlines()[0], source="results/theory/icml/trap_check.json", summary=summ,
               groups=groups)
    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
    for k, v in summ.items():
        print(k, json.dumps({kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}))
    for g in groups:
        if g["kind"] == "e2":
            print(f"{g['label']:<32} {g['rate_mult']:<5} gamma {g['gamma']:.4f}  gamma/z {g['gamma_over_z']:.4f}  "
                  f"meas {min(g['measured']):.4f}-{max(g['measured']):.4f}")


if __name__ == "__main__":
    main()
