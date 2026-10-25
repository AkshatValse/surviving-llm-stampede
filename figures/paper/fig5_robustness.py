"""F5 (single column): robustness of the paired kill test in the simulator across tool-time laws.

One row per tool-time law. Gray bar: the measured metastability window [1, hi] in multiples of the law's own lambda_miss
(hi = largest multiple at which all seeds are stable from empty, B2 rule, 10 seeds). Markers: the two test points of the
paired NOBURST / BURST / CAPPED test at lo + (hi - lo)/3 and lo + 2(hi - lo)/3 (rounded to the grid); filled = PASS,
crossed open circle = FAIL under the declared rule (BURST trapped, NOBURST good and CAPPED recovered each in >= 7 of 10
seeds); the number above a marker is BURST trapped / seeds, the grey note names a non-BURST criterion that failed.
Top row: the real engine (E2, SGLang, 3 seeds, need 2) for reference; its window edge is the last all-stable multiple of E0b.
The last row is a labelled post-hoc rerun of the secondary workload with the protocol adjusted (converged lambda_miss,
longer horizons); it is not part of the declared results.
Sources: results/r7_report (synthetic laws), results/r7_traces_sim/r7_report (trace laws), results/r7_traces_sim_adj/r7_report
(post hoc), the E2 verdict and the E0b bracket (real engine).
Run:  python figures/paper/fig5_robustness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

R7 = "results/r7_report/20261024-233554/pairs_summary.json"
R7_TRACES = "results/r7_traces_sim/r7_report/20261025-012451/pairs_summary.json"
R7_ADJ = "results/r7_traces_sim_adj/r7_report/20261025-012453/pairs_summary.json"
E2_VERDICT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/kill_verdict_v2.json"
E0B_BRACKET = "results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/lambda_cap_bracket.json"

SHORT = {"exp1": "Exp(1 s)", "exp2": "Exp(2 s)", "exp5": "Exp(5 s) (record)", "lognormal": "lognormal, CV 2",
         "bimodal": "bimodal 1 s / 20 s", "tl_turn": "TraceLab per turn", "tl_idle": "TraceLab idle gap",
         "mini_tool": "mini-SWE-agent tool time", "mini_full": "mini-SWE-agent full workload"}


def load_workload(path: str, key: str) -> dict:
    return json.loads(S.src(path).read_text())["workloads"][key]


def row_from_summary(w: dict) -> dict:
    pts = []
    for mult, p in sorted(w["points"].items(), key=lambda kv: float(kv[0])):
        n, need = int(p["n_seeds"]), int(p["need"])
        notes = []
        if p["noburst_good"] < need:
            notes.append(f"NOBURST {p['noburst_good']}/{n}")
        if p["cap_recovered"] < need:
            notes.append(f"CAPPED {p['cap_recovered']}/{n}")
        pts.append(dict(x=float(mult), trapped=int(p["burst_trapped"]), n=n, ok=bool(p["PASS"]), note="; ".join(notes)))
    return dict(hi=float(w["hi"]), pts=pts)


def main() -> None:
    rows = []   # (section, label, row, posthoc)
    for k in ("exp1", "exp2", "exp5", "lognormal", "bimodal"):
        rows.append(("synthetic", SHORT[k], row_from_summary(load_workload(R7, k)), False))
    for k in ("tl_turn", "tl_idle", "mini_tool", "mini_full"):
        rows.append(("traces", SHORT[k], row_from_summary(load_workload(R7_TRACES, k)), False))
    rows.append(("traces", "same, post hoc, adjusted", row_from_summary(load_workload(R7_ADJ, "mini_full")), True))

    # real engine reference row
    e2 = json.loads(S.src(E2_VERDICT).read_text())
    e0b = json.loads(S.src(E0B_BRACKET).read_text())
    real_pts = []
    for c in sorted(e2["cells"], key=lambda c: c["rate_mult"]):
        n_seeds = int(c["n_seeds_complete"])
        real_pts.append(dict(x=float(c["rate_mult"]), trapped=int(round(c["burst_trapped_frac"] * n_seeds)), n=n_seeds,
                             ok=bool(c["meets"]), note=""))
    real = dict(hi=float(e0b["largest_all_stable_mult"]), pts=real_pts)

    n_rows = len(rows) + 1
    row_h = 0.285
    fig_h = n_rows * row_h + 0.95
    fig, ax = plt.subplots(figsize=(S.COL1, fig_h))
    y_real = len(rows) + 1.0
    ys = [len(rows) - i for i in range(len(rows))]       # top-down, leaving a gap below the real row
    allrows = [(y_real, "real engine (E2)", real, False, True)] + [(y, lab, r, ph, False) for y, (sec, lab, r, ph) in zip(ys, [(a, b, c, d) for a, b, c, d in rows])]

    for y, label, r, posthoc, is_real in allrows:
        ax.plot([1.0, r["hi"]], [y, y], color=S.LGRAY, lw=5.5, solid_capstyle="butt", zorder=1, alpha=0.9 if not posthoc else 0.55)
        pts = r["pts"]
        close = len(pts) == 2 and abs(pts[1]["x"] - pts[0]["x"]) < 0.3
        for i, p in enumerate(pts):
            if p["ok"]:
                ax.plot(p["x"], y, lw=0, marker="o", ms=4.6, mfc=S.DARK, mec=S.DARK, mew=1.0, zorder=4)
            else:
                ax.plot(p["x"], y, lw=0, marker="o", ms=5.0, mfc="white", mec=S.DARK, mew=1.0, zorder=4)
                ax.plot(p["x"], y, lw=0, marker="x", ms=3.6, mec=S.DARK, mew=1.0, zorder=5)
            ha = "center" if not close else ("right" if i == 0 else "left")
            dx = 0.0 if not close else (0.03 if i else -0.03)
            ax.text(p["x"] + dx, y + 0.2, f"{p['trapped']}/{p['n']}", fontsize=7, ha=ha, va="bottom", color=S.DARK, zorder=6)
            if p["note"]:
                ax.text(p["x"], y - 0.3, p["note"], fontsize=6.6, ha="center", va="top", color=S.GRAY, zorder=6)
    # labels
    ax.set_yticks([y for y, *_ in allrows])
    ax.set_yticklabels([lab for _, lab, *_ in allrows])
    ax.tick_params(axis="y", length=0, pad=2)
    for lab, t in zip(ax.get_yticklabels(), allrows):
        if t[3]:
            lab.set_color(S.GRAY)
    ax.set_ylim(0.35, y_real + 0.65)
    ax.set_xlim(0.78, 3.35)
    ax.set_xticks([1, 1.5, 2, 2.5, 3])
    ax.set_xlabel(r"arrival rate ($\times$ the law's own $\lambda_{\mathrm{miss}}$)")
    # section separators + headers
    ax.axhline(y_real - 0.5, color=S.LGRAY, lw=0.5, zorder=0)
    ax.axhline(ys[4] - 0.5, color=S.LGRAY, lw=0.5, zorder=0)
    ax.text(3.33, y_real - 0.6 - 0.02, "synthetic laws", fontsize=7, ha="right", va="top", color=S.GRAY, style="italic")
    ax.text(3.33, ys[4] - 0.6 - 0.02, "real-trace laws", fontsize=7, ha="right", va="top", color=S.GRAY, style="italic")
    h = [Line2D([0], [0], marker="o", mfc=S.DARK, mec=S.DARK, lw=0, ms=4.6, label="PASS"),
         Line2D([0], [0], marker="o", mfc="white", mec=S.DARK, lw=0, ms=5.0, label="FAIL")]
    ax.legend(handles=h, loc="upper right", bbox_to_anchor=(1.0, 1.02), ncol=2, fontsize=7.5, columnspacing=1.0, handletextpad=0.2)
    fig.subplots_adjust(left=0.43, right=0.985, top=1 - 0.12 / fig_h, bottom=0.62 / fig_h)
    S.save(fig, "fig5_robustness")
    S.finish("fig5_robustness")


if __name__ == "__main__":
    main()
