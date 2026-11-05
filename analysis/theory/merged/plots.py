"""Figures of the merged theory from results/theory/merged/*.json (run analysis.theory.validate and predict first).

    PYTHONPATH="src;." python -m analysis.theory.merged.plots

figures/theory/merged_validation.{png,pdf}: the three measured cells, predicted (fluid, annealed F1, Stage C synchronized
start) against measured mu(n), and the predicted from-empty instability (F2 primary, A's level crossing secondary) against
the measured E0b outcomes.  figures/theory/merged_blind.{png,pdf}: the blind cells (H200 variants, Llama-3.1-8B, pools
150k / 600k) next to the validated A100 300k prediction.
"""
from __future__ import annotations

import json
import os

import numpy as np

from ..che_endogenous.measured import MEASURED
from ..fluid_rigorous.cells import measured
from .spec import ROOT

RES = os.path.join(ROOT, "results", "theory", "merged")
FIG = os.path.join(ROOT, "figures", "theory")
TITLES = {"a100_300k": "SGLang, A100, 300k pool", "a100_native": "SGLang, A100, native pool (955,757)",
          "vllm_300k": "vLLM 0.32, A100, 300k (1 fitted factor)"}


def load(name):
    with open(os.path.join(RES, f"{name}.json")) as f:
        return json.load(f)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(FIG, exist_ok=True)
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 6.5})
    col = dict(fl="#1f4e79", an="#7aa6c2", sy="#2e7d32", ms="#c0392b", mt="#e67e22", sec="#8e44ad")
    fig, ax = plt.subplots(2, 3, figsize=(7.4, 4.6))
    for j, c in enumerate(("a100_300k", "a100_native", "vllm_300k")):
        P = load(c)
        me = measured(c)
        cv = P["closed_curve"]["curve"]
        a = ax[0, j]
        a.plot(cv["n"], cv["mu_fluid"], color=col["fl"], lw=1.3, label="predicted, fluid")
        a.plot(cv["n"], cv["mu_annealed"], color=col["an"], lw=1.0, ls="--", label="predicted, + demand fluctuation (F1)")
        sy = [(float(n), g["stagec_synchronized"]["mu_sessions"]) for n, g in P["closed_curve"]["grid_points"].items()
              if g.get("stagec_synchronized")]
        if sy:
            a.plot([x for x, _ in sy], [y for _, y in sy], "D", mfc="none", ms=4, color=col["sy"],
                   label="predicted, Stage C synchronized start")
        a.plot(me.n, me.mu_sessions, "o", ms=3.5, color=col["ms"], label="measured, sessions/s")
        a.plot(me.n, me.mu_turns, "s", ms=3, mfc="none", color=col["mt"], label="measured, turns-based")
        a.axhline(me.lam_ref, color="#555555", lw=0.6, ls=":")
        a.set_xscale("log")
        a.set_title(TITLES[c])
        a.set_xlabel("closed population n")
        if j == 0:
            a.set_ylabel(r"$\mu(n)$ (sessions/s)")
        b = ax[1, j]
        fe = P["from_empty_edge"]
        xs = sorted(float(k) for k in fe["p_escape_fine"])
        b.plot(xs, [fe["p_escape_fine"][str(x)] for x in xs], color=col["fl"], lw=1.3, label="F2 (primary)")
        sec = fe.get("secondary_level_crossing", {}).get("p_unstable_all", {})
        if sec:
            xs2 = sorted(float(k) for k in sec)
            b.plot(xs2, [sec[str(x)] for x in xs2], color=col["sec"], lw=1.0, ls=":", label="A's level crossing (secondary)")
        for x, st in MEASURED[c]["e0b"].items():
            b.plot([x], [0.0 if st else 1.0], "o" if st else "X", color="green" if st else col["ms"], ms=5)
        b.axhline(0.5, color="#999999", lw=0.5)
        b.set_ylim(-0.06, 1.06)
        b.set_xlabel(r"arrival rate / $\lambda_{ref}$")
        if j == 0:
            b.set_ylabel("P(unstable 3000 s run from empty)")
    h1, l1 = ax[0, 0].get_legend_handles_labels()
    h2, l2 = ax[1, 0].get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"merged_validation.{ext}"), dpi=200)
    plt.close(fig)
    # blind cells
    fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.8))
    cells = [("a100_300k", "A100 300k (validated)", "-"), ("h200_300k", "H200, uniform speed-up", "-"),
             ("h200_300k_decode2", "H200, decode side 2.0x", "--"), ("h200_300k_e0a2", "H200, 2 E0a parameters", ":"),
             ("llama31_8b_300k", "Llama-3.1-8B (a priori)", "-."), ("a100_pool150k", "A100 150k pool", "-"),
             ("a100_pool600k", "A100 600k pool", "-")]
    for name, lab, ls in cells:
        if not os.path.exists(os.path.join(RES, f"{name}.json")):
            continue
        P = load(name)
        cv = P["closed_curve"]["curve"]
        lr = P["closed_curve"]["fluid"]["mu_max"] / P["window"]["vs_lambda_ref"]
        ax[0].plot(cv["n"], np.array(cv["mu_annealed"]) / lr, ls=ls, lw=1.1, label=lab)
        fe = P["from_empty_edge"]
        xs = sorted(float(k) for k in fe["p_escape_fine"])
        ax[1].plot(xs, [fe["p_escape_fine"][str(x)] for x in xs], ls=ls, lw=1.1, label=lab)
    ax[0].set_xlabel("closed population n")
    ax[0].set_ylabel(r"predicted $\mu(n)/\lambda_{ref}$ (annealed)")
    ax[0].set_xscale("log")
    ax[0].axhline(1.0, color="#555555", lw=0.6, ls=":")
    ax[0].legend(frameon=False, fontsize=6)
    ax[1].set_xlabel(r"arrival rate / $\lambda_{ref}$")
    ax[1].set_ylabel("predicted P(unstable 3000 s run), F2")
    ax[1].axhline(0.5, color="#999999", lw=0.5)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"merged_blind.{ext}"), dpi=200)
    plt.close(fig)
    print("written", os.path.join(FIG, "merged_validation.png"), os.path.join(FIG, "merged_blind.png"))


if __name__ == "__main__":
    main()
