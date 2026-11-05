"""Figure: Theorem 1/2 against every trapped run (draft for paper/sections/theory_icml.tex).

    PYTHONPATH="src;." python figures/theory_icml/fig_trap_universality.py

Reads results/theory/icml/trap_check.json (analysis.theory.icml.run_check); predicted curves from the frozen cell models.
Writes paper/figs/fig_trap_universality.pdf and .png.
Palette (dataviz default, light): model F #2a78d6, E2-protocol runs #eb6834 (filled circles), E0b runs #1baf7a (hollow
diamonds: shape is the secondary encoding), quasi-static Eq. (fluid) a neutral dashed line.
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.theory.icml.run_check import cell_model
from analysis.theory.icml.trap_renewal import trap_asymptotics, trap_costs

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
BLUE, ORANGE, AQUA, NEUTRAL, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#8a8a85", "#1f1f1d", "#5f5f5a", "#e6e6e3"
CELLS = ["a100_300k", "a100_native", "vllm_300k", "llama31_fit", "h200_300k", "h200_600k", "a100_pool150k", "a100_pool600k"]


def main() -> int:
    J = json.load(open(os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")))
    plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 6.8, "ytick.labelsize": 6.8,
                         "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                         "font.family": "serif", "mathtext.fontset": "stix", "legend.fontsize": 6.8})
    fig, axs = plt.subplots(1, 4, figsize=(7.0, 2.15), layout="constrained")
    rho_grid = np.concatenate([1 + np.logspace(-3, -1, 12), np.linspace(1.12, 6.6, 120)])
    for i, cell in enumerate(CELLS):
        m, _ = cell_model(cell)
        tc = trap_costs(m)
        A = [trap_asymptotics(r * tc.lam_miss, tc) for r in rho_grid]
        kw = dict(color=BLUE, lw=1.0, alpha=0.85, zorder=2, label="model F (Thm. 1), 8 cells" if i == 0 else None)
        axs[0].plot(rho_grid, [a["P_served_ratio"] for a in A], **kw)
        axs[1].plot(rho_grid, [a["D_over_lam_miss"] for a in A], **kw)
        axs[2].plot(rho_grid, [a["alpha"] / tc.lam_miss for a in A], **kw)
        # Panel (d): measured.py regresses each gap on the turn's completion time, so the model-F constant is
        # gamma/z = 1 - 1/z, not gamma (Theorem 1(c)'s gamma indexes the join time). Fixed 2026-11-05 after review.
        axs[3].plot(rho_grid, [a["gamma"] / a["z"] for a in A], **kw)
    qs = dict(color=NEUTRAL, lw=1.0, ls=(0, (4, 2)), zorder=1, label="quasi-static fluid")
    axs[0].plot([1, 6.6], [1, 1], **qs)
    axs[1].plot([1, 6.6], [1, 1], **qs)
    axs[2].plot([1, 6.6], [0, 5.6], **qs)
    seen = set()
    for g in J["groups"]:
        a = g["asym"]
        me = g["measured"]
        lm = a["lam_miss"]
        e2 = g["kind"] == "e2"
        style = dict(marker="o", ms=3.4, mfc=ORANGE, mec="white", mew=0.5, ls="none", zorder=4) if e2 else \
            dict(marker="D", ms=3.2, mfc="white", mec=AQUA, mew=1.0, ls="none", zorder=5)
        lab = ("stuck runs, E2 protocol (57)" if e2 else "stuck from empty, E0b (13)")
        lab = lab if lab not in seen else None
        seen.add(lab)
        x = np.full(len(me["backlog_slope"]), a["rho"])
        axs[0].plot(x, np.array(me["P_served_mean"]) / a["P_stat_mean"], label=lab, **style)
        axs[1].plot(x, np.array(me["completion_rate"]) / lm, **style)
        axs[2].plot(x, np.array(me["backlog_slope"]) / lm, **style)
        axs[3].plot(x, np.array(me["gap_med_slope"]), **style)
    titles = [("(a) served prompt / stationary", "trapped turn mix"),
              ("(b) completions / $\\lambda_{\\mathrm{miss}}$", "youth premium"),
              ("(c) backlog slope / $\\lambda_{\\mathrm{miss}}$", "growth"),
              ("(d) gap slope vs completion time", "cycle $\\propto$ trap age")]
    for ax, (t, sub) in zip(axs, titles):
        ax.set_title(t, fontsize=7.5, color=INK, loc="left", pad=3)
        ax.set_xlabel("$\\rho=\\lambda/\\lambda_{\\mathrm{miss}}$")
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_xlim(1.0, 6.6)
    axs[0].set_ylim(0.45, 1.05)
    axs[1].set_ylim(0.9, 2.7)
    axs[2].set_ylim(-0.1, 5.0)
    axs[3].set_ylim(-0.005, 0.16)
    h, l = axs[0].get_legend_handles_labels()
    order = [l.index(x) for x in ("model F (Thm. 1), 8 cells", "quasi-static fluid", "stuck runs, E2 protocol (57)",
                                  "stuck from empty, E0b (13)")]
    fig.legend([h[i] for i in order], [l[i] for i in order], loc="outside upper center", ncols=4, frameon=False,
               handlelength=1.8, columnspacing=1.6)
    out = os.path.join(ROOT, "paper", "figs", "fig_trap_universality")
    fig.savefig(out + ".pdf")
    fig.savefig(out + ".png", dpi=220)
    print("wrote", out + ".pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
