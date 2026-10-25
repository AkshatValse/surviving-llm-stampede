"""F3 (single column): from-empty stability of the open system (E0b, 300k pool) against the blind B2 prediction.

Real engine: one 3000 s run per arrival rate, open-loop Poisson sessions from an empty cache and queue at 1.25 ... 3.0 x
lambda_ref (lambda_ref = 0.07153 sessions/s, E0a turns-based); a run is stable if its final queue is below 50 and the queue
shows no upward trend (the operational rule in analysis.summarize stable, the same as B2's).
Simulator: blind prediction B2 (notes/PREDICTIONS.md, frozen before E0b was read), mixed batching, stable fraction of
3 registered seeds and of the 20-seed supplement at each lambda of the B2 grid.
Run:  python figures/paper/fig3_from_empty_stability.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

E0B = "results/nova/e0b_1708475x_pulled_20261024-150639/results"
STABLE_RUNS = f"{E0B}/agentload_analysis_stable/20261024-150720/stable_runs.csv"      # bracket over all six runs
B2_3 = "results/r6_predict_report/20261024-034707/b2_table.csv"
B2_20 = "results/r6_predict_report/20261024-034707/b2_supp20_table.csv"
CAL = "results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json"


def main() -> None:
    runs = pd.read_csv(S.src(STABLE_RUNS))
    assert len(runs) == 6 and runs["stable"].dtype == bool, runs
    # the arrival rate each run actually used, from the run's own meta.json (run_dir is relative to the Nova root)
    lam = []
    for rd in runs["run_dir"]:
        meta = json.loads(S.src(f"{E0B}/{rd[len('results/'):]}/meta.json").read_text())
        lam.append(float(meta["resolved_rate_sessions_per_s"]))
    runs["lam"] = lam
    lam_ref = json.loads(S.src(CAL).read_text())["lambda_miss_turns_based"]
    assert np.allclose(runs["lam"], runs["rate_mult"] * lam_ref, rtol=1e-9)
    runs = runs.sort_values("lam")

    b3 = pd.read_csv(S.src(B2_3))
    b3 = b3[b3["mode"] == "mixed"].sort_values("lam")
    b20 = pd.read_csv(S.src(B2_20))
    b20 = b20[b20["mode"] == "mixed"].sort_values("lam")
    assert (b3["n_runs"] == 3).all() and (b20["n_runs"] == 20).all()

    fig, ax = plt.subplots(figsize=(S.COL1, 2.45))
    ax.axvline(lam_ref, color=S.VERM, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
    ax.text(lam_ref + 0.002, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    ax.plot(b20["lam"], b20["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (1, 1.2)), marker="s", mfc="white", mec=S.SIM,
            ms=2.8, mew=0.7, zorder=2, label="simulator, 20 seeds")
    ax.plot(b3["lam"], b3["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM,
            ms=3.4, mew=0.8, zorder=3, label="simulator, 3 seeds")
    st = runs[runs["stable"]]
    un = runs[~runs["stable"]]
    ax.plot(st["lam"], np.ones(len(st)), lw=0, marker="o", color=S.REAL, ms=4.6, zorder=5, label="real run: stable")
    ax.plot(un["lam"], np.zeros(len(un)), lw=0, marker="X", color=S.REAL, ms=5.0, zorder=5, label="real run: unstable")
    ax.set_xlim(0.06, 0.232)
    ax.set_xticks([0.08, 0.12, 0.16, 0.20])
    ax.set_ylim(-0.1, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel(r"arrival rate $\lambda$ (sessions/s)")
    ax.set_ylabel("fraction of runs stable")
    sec = ax.secondary_xaxis("top", functions=(lambda x: x / lam_ref, lambda m: m * lam_ref))
    sec.set_xlabel(r"multiple of $\lambda_{\mathrm{ref}}$ = 0.0715 sessions/s", fontsize=8)
    sec.set_xticks([1, 1.5, 2, 2.5, 3])
    sec.tick_params(labelsize=8)
    ax.legend(loc="lower left", bbox_to_anchor=(0.115, 0.06), fontsize=7.5, handlelength=2.2)
    fig.subplots_adjust(left=0.16, right=0.985, top=0.80, bottom=0.18)
    S.save(fig, "fig3_from_empty_stability")
    S.finish("fig3_from_empty_stability")


if __name__ == "__main__":
    main()
