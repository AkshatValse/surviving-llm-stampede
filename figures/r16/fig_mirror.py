"""Figure: the MIRROR test, step-capped vs standard workload in the trap (1.65 x lambda_ref, burst of 200 at 1200 s).

    PYTHONPATH="src;." python figures/r16/fig_mirror.py [--mirror-runs RUN ...] [--out results/theory/r16/fig_mirror]

Panel (a): session completions per 300-s bin (in lambda_ref) after the burst.  Panel (b): sessions in the system (300-s
means).  Grey: the committed STANDARD-workload BURST runs at 1.65 x (jobs 17093390 / 17093396 / 17093402).  Orange: the
step-capped MIRROR BURST runs (when given).  Blue dashed: model F's frozen per-seed predictions for the step-capped
workload (results/theory/r16/mirror_predictions.json).  Dotted: the all-miss capacities (model) of the two workloads.
"""
from __future__ import annotations

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analysis.load import load_run  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
BLUE, ORANGE, NEUTRAL, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#8a8a85", "#1f1f1d", "#5f5f5a", "#e6e6e3"
STD = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/"
STD_165 = ["20261024-155120", "20261024-184132", "20261025-000043"]
BIN = 300.0
T0, T1 = 1200.0, 8700.0


def bins_of(run, lam_ref):
    ses = run.sessions
    edges = np.arange(T0, T1 + 1e-9, BIN)
    t = ses[ses["status"].astype(str) == "completed"]["t_end"].to_numpy(float)
    c, _ = np.histogram(t[np.isfinite(t)], bins=edges)
    centers = edges[:-1] + BIN / 2
    st = ses["arrival_s"].to_numpy(float)
    en = ses["t_end"].to_numpy(float).copy()
    en[~np.isfinite(en)] = np.inf
    ok = ses["status"].astype(str).isin(["completed", "failed"]).to_numpy()
    en[~ok] = np.inf
    tt = np.arange(T0, T1, 1.0)
    n = np.searchsorted(np.sort(st), tt, side="right") - np.searchsorted(np.sort(en), tt, side="right")
    nb = n[: int(len(tt) // BIN) * int(BIN)].reshape(-1, int(BIN)).mean(axis=1)
    return centers, c / BIN / lam_ref, nb


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror-runs", nargs="*", default=[])
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "theory", "r16", "fig_mirror"))
    args = ap.parse_args(argv)
    pred = json.load(open(os.path.join(ROOT, "results", "theory", "r16", "mirror_predictions.json")))
    lr = float(pred["lambda_ref"])
    plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 6.8, "ytick.labelsize": 6.8,
                         "font.family": "serif", "mathtext.fontset": "stix", "legend.fontsize": 6.6})
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.3), layout="constrained")
    for i, name in enumerate(STD_165):
        r = load_run(os.path.join(ROOT, STD + name))
        c, rate, nb = bins_of(r, lr)
        axs[0].plot(c, rate, color=NEUTRAL, lw=0.9, label="standard workload, measured" if i == 0 else None)
        axs[1].plot(c, nb, color=NEUTRAL, lw=0.9, label="standard workload, measured" if i == 0 else None)
    cell = pred["cells"]["1.65"]
    for i, (s, sd) in enumerate(sorted(cell["seeds"].items())):
        b = sd["completion_bins"]
        c = np.array(b["bin_start"]) + BIN / 2
        axs[0].plot(c, b["rate_over_lam_ref"], color=BLUE, lw=0.9, ls=(0, (4, 2)),
                    label="step-capped, model F (frozen)" if i == 0 else None)
        axs[1].plot(sd["N_300s"]["center"], sd["N_300s"]["mean"], color=BLUE, lw=0.9, ls=(0, (4, 2)),
                    label="step-capped, model F (frozen)" if i == 0 else None)
    for i, d in enumerate(args.mirror_runs):
        r = load_run(d)
        c, rate, nb = bins_of(r, lr)
        axs[0].plot(c, rate, color=ORANGE, lw=1.1, label="step-capped, measured (blind)" if i == 0 else None)
        axs[1].plot(c, nb, color=ORANGE, lw=1.1, label="step-capped, measured (blind)" if i == 0 else None)
    for v, lab in ((pred["lambda_miss_standard_model_over_ref"], None), (pred["lambda_miss_model_over_ref"], None)):
        axs[0].axhline(v, color=MUTED, lw=0.6, ls=":")
    axs[0].text(T1 - 60, pred["lambda_miss_model_over_ref"] + 0.08, r"all-miss capacity $\lambda_{\rm miss}$",
                ha="right", va="bottom", fontsize=6.4, color=MUTED)
    axs[0].set_ylabel(r"completions / 300 s  ($\times\lambda_{\rm ref}$)")
    axs[1].set_ylabel("sessions in the system")
    for ax, t in zip(axs, ("(a) completions after the burst", "(b) backlog")):
        ax.set_xlabel("time since run start (s)")
        ax.set_xlim(T0, T1)
        ax.grid(color=GRID, lw=0.5)
        ax.set_title(t, fontsize=7.5, color=INK, loc="left", pad=3)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axs[0].set_ylim(0, None)
    axs[1].set_ylim(0, None)
    axs[0].legend(frameon=False, loc="upper left")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out + ".pdf")
    fig.savefig(args.out + ".png", dpi=220)
    print(args.out + ".pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
