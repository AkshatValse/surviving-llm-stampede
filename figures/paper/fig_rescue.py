"""F11 (double column): the registered rescue tests R1 and R4, seed 0 of each cell, against the same-seed BURST and NOBURST
controls of the paired tests (common random numbers): trap, rescue, release, persistence.

Columns: R1 at 1.35 and 1.65 x lambda_ref (300k pool, cap 20 engaged at 1800 s) and R4 at 4.0 x (native pool, cap 64 engaged
at 2100 s). Top: follow-up hit fraction (turns after the first with cached/prompt > 0.5, by completion time) in 60 s bins.
Bottom: outstanding work in 60 s bins (requests in flight in the engine plus sessions waiting at the client gate or paused), log
scale; for the rescue run also the sessions held at the client (gated + paused), dashed. Vertical lines: burst (1200 s, dashed),
engage t_on (dash-dotted), release t_rel (dotted). Green band: cap engaged [t_on, t_rel). Gray band: the registered post-release
interval [t_rel + 300, 8700).
Input (committed in 51c803d, written by figures/rescue_paper_data.py from the registered verdict dirs and the control runs):
results/nova/rescue_1716896x_pulled_20261031-070502/results/rescue_paper_data/20261031-071938/trace_aligned.csv
Run:  python figures/paper/fig_rescue.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

DATA = ("results/nova/rescue_1716896x_pulled_20261031-070502/results/rescue_paper_data/20261031-071938/"
        "trace_aligned.csv")
SEED = 0  # the first registered seed of every cell, fixed before plotting; seeds 1 and 2 are in Table tab:rescue
CELLS = [("r1", 1.35, "R1: 300k pool, 1.35", 20), ("r1", 1.65, "R1: 300k pool, 1.65", 20),
         ("r4", 4.0, "R4: native pool, 4.0", 64)]
EXPECT = {("r1", 1.35): (1800.0, 4550.0), ("r1", 1.65): (1800.0, 4920.0), ("r4", 4.0): (2100.0, 6000.0)}  # rescue_runs.csv
RESCUE = S.GREEN  # a session cap is green in every figure
T_END = 8700.0
BIN = 60.0


def main() -> None:
    t = pd.read_csv(S.src(DATA))
    fig, axes = plt.subplots(2, 3, figsize=(S.COL2, 3.75), sharex=True)
    for j, (prof, mult, title, cap) in enumerate(CELLS):
        d = t[(t.profile == prof) & np.isclose(t.rate_mult, mult) & (t.seed == SEED)]
        ser = {a: d[d.arm == a].sort_values("t_start") for a in ("burst", "noburst", "rescue")}
        for a, s in ser.items():
            assert len(s) == 145 and np.allclose(np.diff(s.t_start), BIN), (prof, mult, a, len(s))
        r = ser["rescue"]
        t_on, t_rel = float(r.t_engage.iloc[0]), float(r.t_release.iloc[0])
        e_on, e_rel = EXPECT[(prof, mult)]
        assert abs(t_on - e_on) < 0.01 and abs(t_rel - e_rel) < 0.01, (t_on, t_rel)
        assert set(r.cap.dropna().unique()) == {float(cap)}
        b = ser["burst"]
        assert (b[(b.t_start >= t_on) & (b.fu_n > 0)].fu_hit == 0).all()  # the uncapped control never hits again
        x = {a: s.t_start.to_numpy() + BIN / 2 for a, s in ser.items()}
        for ax in axes[:, j]:
            ax.axvspan(t_on, t_rel, color=RESCUE, alpha=0.10, lw=0, zorder=0)
            ax.axvspan(t_rel + 300.0, T_END, color=S.LGRAY, alpha=0.28, lw=0, zorder=0)
            ax.axvline(1200.0, color=S.DARK, lw=0.7, ls=(0, (3, 2)), zorder=1)
            ax.axvline(t_on, color=S.DARK, lw=0.7, ls=(0, (4, 1.5, 1, 1.5)), zorder=1)
            ax.axvline(t_rel, color=S.DARK, lw=0.7, ls=(0, (1, 1.5)), zorder=1)
            ax.set_xlim(0, T_END)
            ax.set_xticks([0, 2000, 4000, 6000, 8000])
        ax = axes[0, j]
        for a, col, lw, z in (("rescue", RESCUE, 1.5, 2), ("burst", S.VERM, 0.8, 3), ("noburst", S.BLUE, 0.6, 5)):
            s = ser[a]
            ax.plot(x[a], np.where(s.fu_n.to_numpy() > 0, s.fu_hit.to_numpy(), np.nan), color=col, lw=lw, zorder=z)
        ax.set_ylim(-0.03, 1.03)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_title(rf"{title} $\lambda_{{\mathrm{{ref}}}}$; cap {cap} from {t_on:.0f} s", pad=4, fontsize=8.5)
        ax.text((1200 + t_on) / 2 + 20, 0.5, "trapped", fontsize=6.5, ha="center", va="center", rotation=90, color=S.DARK)
        ax.text((t_on + t_rel) / 2, 0.45, "cap on", fontsize=7.5, ha="center", color=S.DARK)
        ax.text((t_rel + T_END) / 2, 0.45, "cap off:\nstays good", fontsize=7.5, ha="center", color=S.DARK)
        ax.text((t_rel + T_END) / 2, 0.06, "BURST: 0 hits", fontsize=6.5, ha="center", color=S.VERM)
        ax = axes[1, j]
        for a, col, lw, z in (("rescue", RESCUE, 1.5, 2), ("burst", S.VERM, 0.8, 3), ("noburst", S.BLUE, 0.6, 5)):
            ax.plot(x[a], np.clip(ser[a].outstanding_mean.to_numpy(), 0.5, None), color=col, lw=lw, zorder=z)
        held = (r.gated_mean + r.paused_mean).to_numpy()
        ax.plot(x["rescue"], np.where(held > 0, held, np.nan), color=RESCUE, lw=0.8, ls=(0, (3, 1.2)), zorder=4)
        ax.set_yscale("log")
        ax.set_ylim(0.5, 3000)
        ax.set_yticks([1, 10, 100, 1000])
        ax.set_yticklabels(["1", "10", "100", "1000"])
        ax.set_xlabel("time since start of run (s)")
    axes[0, 0].set_ylabel("follow-up hit fraction")
    axes[1, 0].set_ylabel("outstanding (log scale)")
    handles = [Line2D([0], [0], color=RESCUE, lw=1.6, label="rescue run (seed 0)"),
               Line2D([0], [0], color=RESCUE, lw=0.9, ls=(0, (3, 1.2)), label="rescue: held at the client"),
               Line2D([0], [0], color=S.VERM, lw=1.2, label="BURST control (never capped)"),
               Line2D([0], [0], color=S.BLUE, lw=0.7, label="NOBURST control (drawn on top)"),
               Patch(facecolor=RESCUE, alpha=0.18, label="cap engaged"),
               Patch(facecolor=S.LGRAY, alpha=0.5, label="registered post-release interval")]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.005), columnspacing=1.6,
               handlelength=2.0)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.93, bottom=0.215, hspace=0.12, wspace=0.16)
    S.save(fig, "fig_rescue")
    S.finish("fig_rescue")


if __name__ == "__main__":
    main()
