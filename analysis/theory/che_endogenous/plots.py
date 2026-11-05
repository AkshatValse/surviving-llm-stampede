"""Extra figures from the written outputs of run_che.py (no recomputation).

    PYTHONPATH="src;." python -m analysis.theory.che_endogenous.plots [--res results/theory/che_endogenous] [--figdir figures/theory]
"""
from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np

from .measured import MEASURED


def read_curve(path):
    mf, sm = [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            (mf if r["kind"] == "mean_field" else sm).append((float(r["n"]), float(r["mu"]), float(r["hit_all"])))
    return mf, sm


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="results/theory/che_endogenous")
    ap.add_argument("--figdir", default="figures/theory")
    a = ap.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(a.figdir, exist_ok=True)
    preds = json.load(open(os.path.join(a.res, "predictions.json")))
    val = json.load(open(os.path.join(a.res, "validation.json")))
    # 1. out-of-sample predicted curves (blind targets)
    fig, axs = plt.subplots(1, 4, figsize=(16, 3.6))
    for ax, nm, title in zip(axs, ["h200_300k", "llama31_8b_300k", "a100_pool150k", "a100_pool600k"],
                             ["H200 NVL, 300k (pred.)", "Llama-3.1-8B, A100, 300k (pred.)", "A100, 150k pool (pred.)", "A100, 600k pool (pred.)"]):
        mf, sm = read_curve(os.path.join(a.res, f"curves_{nm}.csv"))
        ax.plot([x[0] for x in mf], [x[1] for x in mf], "-", color="#888", lw=1.2, label="mean field")
        ax.plot([x[0] for x in sm], [x[1] for x in sm], "-", color="#1f5fa8", lw=2, label="with live-KV fluctuation")
        lm = preds[nm]["e0a_model"]["lambda_miss_turns"]
        ax.axhline(lm, color="#c0392b", ls=":", lw=1, label="model lambda_miss")
        if nm == "h200_300k_bwsplit":
            pass
        ax.set_xscale("log")
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("closed population n")
    axs[0].set_ylabel("mu(n), sessions/s")
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(a.figdir, "che_predicted_curves.png"), dpi=150)
    plt.close(fig)
    # 2. trapped state: predicted vs measured backlog, token ratio, gap/R
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5))
    k = 0
    labels = []
    for cell in ("a100_300k", "a100_native", "vllm_300k"):
        for mlt, t in val[cell]["comparison"]["trapped_state"].items():
            labels.append(f"{cell.split('_')[0]}{'-nat' if 'native' in cell else ''} {mlt}x")
            for ax, kp, km in zip(axs, ("pred_backlog", "pred_token_ratio", "pred_gap_over_R_trapped"),
                                  ("meas_backlog", "meas_token_ratio", "meas_gap_over_R_trapped")):
                ax.plot([k], [t[kp]], "D", color="#1f5fa8")
                if t.get(km):
                    ax.plot([k] * len(t[km]), t[km], "o", color="#c0392b", ms=4, alpha=0.8)
            k += 1
    for ax, ttl in zip(axs, ("backlog (sessions) over [5700, 8700) s", "uncached token rate / E0a all-miss", "loopvars gap / R (R = M / churn)")):
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
        ax.set_title(ttl, fontsize=9)
    axs[0].plot([], [], "D", color="#1f5fa8", label="model (no fitted parameter)")
    axs[0].plot([], [], "o", color="#c0392b", label="measured runs")
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(a.figdir, "che_trapped_state.png"), dpi=150)
    plt.close(fig)
    # 3. B1 basin: P(stuck) vs burst size
    b1 = preds.get("B1_basin", {})
    fig, ax = plt.subplots(figsize=(5, 3.6))
    for mlt, col in (("1.35", "#2e86c1"), ("1.65", "#1f5fa8"), ("2.0", "#0b2e59")):
        rows = sorted([(v["burst"], v["p_stuck"]) for kk, v in b1.items() if kk.startswith(mlt + "_") and "burst" in v])
        if rows:
            ax.plot([r[0] for r in rows], [r[1] for r in rows], "-o", ms=3, color=col, label=f"{mlt} x lambda_ref")
    ax.axvline(25, color="#888", ls=":")
    ax.axvline(100, color="#888", ls=":")
    ax.set_xlabel("burst size (fresh sessions in 60 s)")
    ax.set_ylabel("P(stuck by 5700 s), model")
    ax.set_xscale("log")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(a.figdir, "che_burst_basin.png"), dpi=150)
    plt.close(fig)
    # 4. the fixed-point map Phi_n(h) at the 300k cell (computed here, fast)
    from dataclasses import replace
    from .model import CheModel, default_cells, Workload
    m = CheModel(replace(default_cells()["a100_300k"], eta=0.10))
    md = CheModel(replace(default_cells()["a100_300k"], eta=0.10, wl=Workload(z_shape=float("inf"))))
    hs = np.linspace(0, 1, 101)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for ax, mm, ttl in ((axs[0], m, "Exp(5 s) tool time (workload of record)"), (axs[1], md, "deterministic 5 s tool time")):
        for n, col in ((20, "#2e86c1"), (26, "#1f5fa8"), (28, "#16a085"), (30, "#7d3c98"), (32, "#c0392b"), (34, "#555")):
            ax.plot(hs, [mm.evaluate(n, h).h_out for h in hs], "-", color=col, label=f"n = {n}")
        ax.plot([0, 1], [0, 1], "k:", lw=1)
        ax.set_xlabel("follow-up hit probability h (input)")
        ax.set_ylabel("Phi_n(h) = P(Z + W < R)")
        ax.set_title(ttl, fontsize=9)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(a.figdir, "che_feedback_map.png"), dpi=150)
    plt.close(fig)
    print("figures written to", a.figdir)


if __name__ == "__main__":
    main()
