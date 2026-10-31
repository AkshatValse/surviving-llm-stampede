"""F3 (single column): from-empty stability of the open system against the blind simulator predictions, at both pool sizes.

Top, 300k-token pool: real engine E0b, one 3000 s run per arrival rate, open-loop Poisson sessions from an empty cache and
queue at 1.25 ... 3.0 x lambda_ref (lambda_ref = 0.07153 sessions/s, E0a turns-based); a run is stable if its final queue is
below 50 and the queue shows no upward trend (the operational rule in analysis.summarize stable, the same as B2's).
Simulator: blind prediction B2 (notes/PREDICTIONS.md, frozen before E0b was read), mixed batching, stable fraction of
3 registered seeds and of the 20-seed supplement at each lambda of the B2 grid.
Bottom, native pool (955,757 tokens): real native E0b (jobs 17100938-39), one 3000 s run at 1.5 ... 6.5 x the native
lambda_ref (0.07180 sessions/s); simulator: blind prediction B2n (notes/PREDICTIONS_native.md, pushed before any native E0b
run had finished), 10 seeds per multiple of each batching mode's own lambda_miss, mixed (primary) and separate (secondary).
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

E0B = "results/nova/e0b_1708475x_pulled_20261024-150639/results"
STABLE_RUNS = f"{E0B}/agentload_analysis_stable/20261024-150720/stable_runs.csv"      # bracket over all six runs
B2_3 = "results/r6_predict_report/20261024-034707/b2_table.csv"
B2_20 = "results/r6_predict_report/20261024-034707/b2_supp20_table.csv"
CAL = "results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json"

E0B_NAT = "results/nova/e0b_native_1710093x_pulled_20261025-173038/results"
STABLE_RUNS_NAT = f"{E0B_NAT}/agentload_analysis_stable/20261025-172934/stable_runs.csv"  # bracket over all six native runs
CAL_NAT = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json"
B2N = "results/r8_native_report/20261025-150146/{mode}_edge_edge_verdicts.csv"


def real_runs(stable_csv: str, root: str, cal: str) -> tuple:
    runs = pd.read_csv(S.src(stable_csv))
    assert len(runs) == 6 and runs["stable"].dtype == bool, runs
    # the arrival rate each run actually used, from the run's own meta.json (run_dir is relative to the Nova root)
    lam = []
    for rd in runs["run_dir"]:
        meta = json.loads(S.src(f"{root}/{rd[len('results/'):]}/meta.json").read_text())
        lam.append(float(meta["resolved_rate_sessions_per_s"]))
    runs["lam"] = lam
    lam_ref = json.loads(S.src(cal).read_text())["lambda_miss_turns_based"]
    assert np.allclose(runs["lam"], runs["rate_mult"] * lam_ref, rtol=1e-9)
    return runs.sort_values("lam"), lam_ref


def draw_real(ax, runs: pd.DataFrame, lam_ref: float, legend: bool) -> None:
    ax.axvline(lam_ref, color=S.VERM, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
    st = runs[runs["stable"]]
    un = runs[~runs["stable"]]
    ax.plot(st["lam"], np.ones(len(st)), lw=0, marker="o", color=S.REAL, ms=4.6, zorder=5, label="real run: stable" if legend else None)
    ax.plot(un["lam"], np.zeros(len(un)), lw=0, marker="X", color=S.REAL, ms=5.0, zorder=5, label="real run: unstable" if legend else None)
    ax.set_ylim(-0.1, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_ylabel("fraction of runs stable")


def main() -> None:
    runs, lam_ref = real_runs(STABLE_RUNS, E0B, CAL)
    b3 = pd.read_csv(S.src(B2_3))
    b3 = b3[b3["mode"] == "mixed"].sort_values("lam")
    b20 = pd.read_csv(S.src(B2_20))
    b20 = b20[b20["mode"] == "mixed"].sort_values("lam")
    assert (b3["n_runs"] == 3).all() and (b20["n_runs"] == 20).all()

    runs_n, lam_ref_n = real_runs(STABLE_RUNS_NAT, E0B_NAT, CAL_NAT)
    b2n = {}
    for mode in ("mixed", "separate"):
        d = pd.read_csv(S.src(B2N.format(mode=mode)))
        d = d[~d["refinement"].astype(bool)]
        g = d.groupby("lam", as_index=False).agg(n=("seed", "size"), stable_frac=("stable", "mean")).sort_values("lam")
        assert (g["n"] == 10).all() and len(g) == 13, g
        b2n[mode] = g

    fig, (ax, axn) = plt.subplots(2, 1, figsize=(S.COL1, 4.75))
    # ---- top: 300k pool (unchanged reading)
    ax.text(lam_ref + 0.002, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    ax.plot(b20["lam"], b20["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (1, 1.2)), marker="s", mfc="white", mec=S.SIM,
            ms=2.8, mew=0.7, zorder=2, label="simulator, 20 seeds")
    ax.plot(b3["lam"], b3["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM,
            ms=3.4, mew=0.8, zorder=3, label="simulator, 3 seeds")
    draw_real(ax, runs, lam_ref, legend=True)
    ax.set_xlim(0.06, 0.232)
    ax.set_xticks([0.08, 0.12, 0.16, 0.20])
    ax.set_xlabel(r"arrival rate $\lambda$ (sessions/s)")
    sec = ax.secondary_xaxis("top", functions=(lambda x: x / lam_ref, lambda m: m * lam_ref))
    sec.set_xlabel(r"300k pool: multiple of $\lambda_{\mathrm{ref}}$ = 0.0715 sessions/s", fontsize=8)
    sec.set_xticks([1, 1.5, 2, 2.5, 3])
    sec.tick_params(labelsize=8)
    ax.legend(loc="lower left", bbox_to_anchor=(0.115, 0.06), fontsize=7.5, handlelength=2.2)
    # ---- bottom: native pool
    axn.text(lam_ref_n + 0.006, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    axn.plot(b2n["separate"]["lam"], b2n["separate"]["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (1, 1.2)), marker="s", mfc="white",
             mec=S.SIM, ms=2.8, mew=0.7, zorder=2, label="simulator, separate batching")
    axn.plot(b2n["mixed"]["lam"], b2n["mixed"]["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white",
             mec=S.SIM, ms=3.4, mew=0.8, zorder=3, label="simulator, mixed (primary)")
    draw_real(axn, runs_n, lam_ref_n, legend=False)
    axn.set_xlim(0.04, 0.575)
    axn.set_xticks([0.1, 0.2, 0.3, 0.4, 0.5])
    axn.set_xlabel(r"arrival rate $\lambda$ (sessions/s)")
    secn = axn.secondary_xaxis("top", functions=(lambda x: x / lam_ref_n, lambda m: m * lam_ref_n))
    secn.set_xlabel(r"native pool: multiple of $\lambda_{\mathrm{ref}}$ = 0.0718 sessions/s", fontsize=8)
    secn.set_xticks([1, 2, 3, 4, 5, 6, 7])
    secn.tick_params(labelsize=8)
    axn.legend(loc="lower left", bbox_to_anchor=(0.10, 0.06), fontsize=7.5, handlelength=2.2, title="10 seeds each (B2n)",
               title_fontsize=7.5)
    fig.subplots_adjust(left=0.16, right=0.985, top=0.895, bottom=0.085, hspace=0.62)
    S.save(fig, "fig3_from_empty_stability")
    S.finish("fig3_from_empty_stability")


if __name__ == "__main__":
    main()
