"""F6 (single column): the real exploratory policy grid, per-run state of the BURST arm.

Cells (rows): FCFS with waiting-prefix refresh on (the registered E2 BURST arm, decisive), FCFS refresh off, LPM refresh on,
LPM refresh off (the last three are exploratory registrations derived from the E2 one, BURST arm only, never decisive).
Columns: arrival rate 1.35 and 1.65 x lambda_ref, seeds 0, 1, 2. SGLang 0.5.22, Qwen2.5-7B-Instruct, 300k-token KV cap, A100.
Colour: per-run state of the trap analysis over the evaluation window (t_b + 4500 s to the end): trapped (hit ~0, token rate at the
all-miss rate, backlog growing), indeterminate (neither trapped, draining nor recovered), draining (backlog falling),
recovered (hit > 0.8 and backlog < 20 at the end). Numbers: hit fraction (upper) and mean backlog in sessions (lower) over the
evaluation window.
Run:  python figures/paper/fig6_policy_grid.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

E2_VERDICT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/trap_v2_runs.csv"
GRID_DIR = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2"
GRID_VERDICTS = [f"{GRID_DIR}/20261025-144230/trap_v2_runs.csv", f"{GRID_DIR}/20261025-144233/trap_v2_runs.csv",
                 f"{GRID_DIR}/20261025-144236/trap_v2_runs.csv"]

CELLS = [  # (engine label, row label)
    ("sglang-fcfs-r1", "FCFS, refresh on\n(registered E2)"),
    ("sglang-fcfs-r0", "FCFS, refresh off"),
    ("sglang-lpm-r1", "LPM, refresh on"),
    ("sglang-lpm-r0", "LPM, refresh off"),
]
MULTS = (1.35, 1.65)
SEEDS = (0, 1, 2)


def main() -> None:
    e2 = pd.read_csv(S.src(E2_VERDICT))
    e2 = e2[e2["arm"] == "burst"]
    frames = [e2] + [pd.read_csv(S.src(p)) for p in GRID_VERDICTS]
    allr = pd.concat(frames, ignore_index=True)
    allr = allr[allr["arm"] == "burst"]
    assert allr.groupby(["label", "rate_mult", "seed"]).size().max() == 1
    assert len(allr) == 24, len(allr)

    cw, ch, gap = 0.36, 0.42, 0.12
    n_rows = len(CELLS)
    fig_w, fig_h = S.COL1, 0.50 + n_rows * ch + 0.72
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    x0 = 1.18                      # left edge of the grid in inches (room for the row labels)
    y_top = fig_h - 0.50           # top of the grid in inches
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    for i, (lab, rlabel) in enumerate(CELLS):
        y = y_top - (i + 1) * ch
        ax.text(x0 - 0.07, y + ch / 2, rlabel, ha="right", va="center", fontsize=8)
        for j, m in enumerate(MULTS):
            for k, sd in enumerate(SEEDS):
                row = allr[(allr["label"] == lab) & (allr["rate_mult"] == m) & (allr["seed"] == sd)]
                assert len(row) == 1, (lab, m, sd)
                r = row.iloc[0]
                x = x0 + j * (3 * cw + gap) + k * cw
                ax.add_patch(Rectangle((x, y), cw, ch, facecolor=S.STATE_COLOR[r["state"]], edgecolor="white", lw=1.2))
                hit = float(r["hit_eval"])
                ax.text(x + cw / 2, y + ch * 0.64, f"{hit:.2f}", ha="center", va="center", fontsize=7.5, color="black")
                ax.text(x + cw / 2, y + ch * 0.25, f"{float(r['backlog_eval_mean']):.0f}", ha="center", va="center", fontsize=6.8,
                        color="black")
    # column headers
    for j, m in enumerate(MULTS):
        xc = x0 + j * (3 * cw + gap)
        ax.text(xc + 1.5 * cw, y_top + 0.20, rf"{m:.2f} $\times\ \lambda_{{\mathrm{{ref}}}}$", ha="center", va="bottom", fontsize=8.5)
        for k, sd in enumerate(SEEDS):
            ax.text(xc + (k + 0.5) * cw, y_top + 0.03, f"{sd}", ha="center", va="bottom", fontsize=7.5, color=S.GRAY)
    ax.text(x0 - 0.07, y_top + 0.03, "seed", ha="right", va="bottom", fontsize=7.5, color=S.GRAY)
    # registered vs exploratory separator
    ax.plot([0.02, x0 + 2 * (3 * cw) + gap], [y_top - ch] * 2, color=S.DARK, lw=0.6, zorder=3)
    # legend
    handles = [Patch(facecolor=S.STATE_COLOR[s], edgecolor="none", label=S.STATE_LABEL[s]) for s in ("trapped", "indeterminate", "draining", "recovered")]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.20 / fig_h), fontsize=7.5, columnspacing=0.9,
               handlelength=1.0, handletextpad=0.4)
    fig.text(0.5, 0.02 / fig_h, "in each square: hit fraction (upper), mean backlog in sessions (lower).\nRows 2-4: exploratory, BURST arm only; row 1: decisive E2 BURST arm.",
             ha="center", va="bottom", fontsize=7.0, color=S.GRAY, linespacing=1.15)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    S.save(fig, "fig6_policy_grid")
    S.finish("fig6_policy_grid")


if __name__ == "__main__":
    main()
