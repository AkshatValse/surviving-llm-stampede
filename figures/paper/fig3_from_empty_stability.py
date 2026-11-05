"""F3 (single column): from-empty stability of the open system against the blind simulator predictions, in three engine cells.

Top, 300k-token pool: real engine E0b, one 3000 s run per arrival rate, open-loop Poisson sessions from an empty cache and
queue at 1.25 ... 3.0 x lambda_ref (lambda_ref = 0.07153 sessions/s, E0a turns-based); a run is stable if its final queue is
below 50 and the queue shows no upward trend (the operational rule in analysis.summarize stable, the same as B2's).
Simulator: blind prediction B2 (notes/PREDICTIONS.md, frozen before E0b was read), mixed batching, stable fraction of
3 registered seeds and of the 20-seed supplement at each lambda of the B2 grid.
Bottom, native pool (955,757 tokens): real native E0b (jobs 17100938-39), one 3000 s run at 1.5 ... 6.5 x the native
lambda_ref (0.07180 sessions/s); simulator: blind prediction B2n (notes/PREDICTIONS_native.md, pushed before any native E0b
run had finished), 10 seeds per multiple of each batching mode's own lambda_miss, mixed (primary) and separate (secondary).
Bottom, vLLM 0.32.0, 300k-token pool (18,750 blocks of 16): real vLLM E0b (jobs 17162962-63), one 3000 s run at
1.25 ... 3.0 x vLLM's own lambda_ref (0.06566 sessions/s, vLLM E0a turns-based); simulator: blind prediction B2v
(notes/PREDICTIONS_vllm.md, frozen at tag r9-vllm-predictions-frozen before any vLLM E0b run), variant V1 (token costs
scaled to vLLM's measured all-miss token rate, so its rates are in vLLM's units), mixed batching (primary), 10 seeds per
multiple of V1's own lambda_miss (0.06623). The other three B2v configurations are not drawn (README).
All real runs used arrival seed 0 and are plotted at their nominal rates (meta.json resolved_rate_sessions_per_s).
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

E0B_NAT = "results/nova/e0b_native_1710093x_pulled_20261025-173038/results"
STABLE_RUNS_NAT = f"{E0B_NAT}/agentload_analysis_stable/20261025-172934/stable_runs.csv"  # bracket over all six native runs
CAL_NAT = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json"
B2N = "results/r8_native_report/20261025-150146/{mode}_edge_edge_verdicts.csv"

E0B_VLLM = "results/nova/e0b_vllm_1716296x_pulled_20261030-172810/results"
STABLE_RUNS_VLLM = f"{E0B_VLLM}/agentload_analysis_stable/20261030-172042/stable_runs.csv"  # bracket over all six vLLM runs
# vLLM lambda_ref: the registration's input copy, byte-identical to the vLLM E0a analysis it was copied from (checked below)
CAL_VLLM = "prereg/inputs/2026-10-25-vllm/calibration.json"
CAL_VLLM_ORIG = "results/nova/e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json"
B2V = "results/r9_vllm_report/20261030-122723/v1_mixed_edge_edge_verdicts.csv"   # B2v: V1, mixed, seeds 0-9


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


def draw_real(ax, runs: pd.DataFrame, lam_ref: float) -> None:
    ax.axvline(lam_ref, color=S.VERM, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
    st = runs[runs["stable"]]
    un = runs[~runs["stable"]]
    ax.plot(st["lam"], np.ones(len(st)), lw=0, marker="o", color=S.REAL, ms=4.6, zorder=5)
    ax.plot(un["lam"], np.zeros(len(un)), lw=0, marker="X", color=S.REAL, ms=5.0, zorder=5)
    ax.set_ylim(-0.12, 1.14)
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_yticks([0.25, 0.75], minor=True)


def top_axis(ax, lam_ref: float, label: str, ticks) -> None:
    sec = ax.secondary_xaxis("top", functions=(lambda x: x / lam_ref, lambda m: m * lam_ref))
    sec.set_xlabel(label + r": multiple of $\lambda_{\mathrm{ref}}$ = %.4f sessions/s" % lam_ref, fontsize=7.5, labelpad=2.5)
    sec.set_xticks(ticks)
    sec.tick_params(labelsize=7.5, pad=1.5)


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

    assert S.src(CAL_VLLM).read_bytes() == S.src(CAL_VLLM_ORIG).read_bytes()
    runs_v, lam_ref_v = real_runs(STABLE_RUNS_VLLM, E0B_VLLM, CAL_VLLM)
    assert (runs_v["seed"] == 0).all() and (runs_v["label"] == "vllm-fcfs").all()
    b2v = pd.read_csv(S.src(B2V))
    assert not b2v["refinement"].astype(bool).any() and (b2v["workload"] == "exp5").all()
    b2v = b2v.groupby("lam", as_index=False).agg(n=("seed", "size"), mult=("lam_mult", "first"),
                                                 stable_frac=("stable", "mean")).sort_values("lam")
    assert (b2v["n"] == 10).all() and len(b2v) == 6, b2v

    fig, (ax, axn, axv) = plt.subplots(3, 1, figsize=(S.COL1, 4.3))
    # ---- top: 300k pool (unchanged reading)
    ax.text(lam_ref + 0.002, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    ax.plot(b20["lam"], b20["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (1, 1.2)), marker="s", mfc="white", mec=S.SIM,
            ms=2.8, mew=0.7, zorder=2, label="simulator, 20 seeds")
    ax.plot(b3["lam"], b3["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM,
            ms=3.4, mew=0.8, zorder=3, label="simulator, 3 seeds")
    draw_real(ax, runs, lam_ref)
    ax.set_xlim(0.06, 0.232)
    ax.set_xticks([0.08, 0.12, 0.16, 0.20])
    top_axis(ax, lam_ref, "SGLang, 300k pool", [1, 1.5, 2, 2.5, 3])
    ax.legend(loc="lower left", bbox_to_anchor=(0.115, 0.10), fontsize=7.5, handlelength=2.2)
    # ---- bottom: native pool
    axn.text(lam_ref_n + 0.006, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    axn.plot(b2n["separate"]["lam"], b2n["separate"]["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (1, 1.2)), marker="s", mfc="white",
             mec=S.SIM, ms=2.8, mew=0.7, zorder=2, label="simulator, separate batching")
    axn.plot(b2n["mixed"]["lam"], b2n["mixed"]["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white",
             mec=S.SIM, ms=3.4, mew=0.8, zorder=3, label="simulator, mixed (primary)")
    draw_real(axn, runs_n, lam_ref_n)
    axn.set_xlim(0.04, 0.575)
    axn.set_xticks([0.1, 0.2, 0.3, 0.4, 0.5])
    top_axis(axn, lam_ref_n, "SGLang, native pool", [1, 2, 3, 4, 5, 6, 7])
    axn.legend(loc="lower left", bbox_to_anchor=(0.10, 0.06), fontsize=7.5, handlelength=2.2, title="10 seeds each (B2n)",
               title_fontsize=7.5)
    # ---- bottom: vLLM 0.32.0, 300k pool (same x range as the top panel)
    axv.text(lam_ref_v + 0.002, 0.5, r"$\lambda_{\mathrm{miss}}$", color=S.VERM, fontsize=8, ha="left", va="center", rotation=90)
    axv.plot(b2v["lam"], b2v["stable_frac"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM,
             ms=3.4, mew=0.8, zorder=3, label="simulator, mixed (primary)")
    draw_real(axv, runs_v, lam_ref_v)
    axv.set_xlim(0.06, 0.232)
    axv.set_xticks([0.08, 0.12, 0.16, 0.20])
    top_axis(axv, lam_ref_v, "vLLM, 300k pool", [1, 1.5, 2, 2.5, 3])
    axv.legend(loc="lower left", bbox_to_anchor=(0.115, 0.06), fontsize=7.5, handlelength=2.2, title="10 seeds each (B2v, variant V1)",
               title_fontsize=7.5)
    # shared labels: bottom axes are sessions/s in every panel, top axes multiples of that cell's lambda_ref
    for a in (ax, axn, axv):
        a.tick_params(axis="x", labelsize=7.5, pad=1.5)
        a.tick_params(axis="y", labelsize=7.5)
    axv.set_xlabel(r"arrival rate $\lambda$ (sessions/s; all panels)", labelpad=1.5)
    fig.text(0.015, 0.5, "fraction of runs stable", rotation=90, ha="left", va="center", fontsize=8.5)
    real_h = [Line2D([0], [0], lw=0, marker="o", color=S.REAL, ms=4.6), Line2D([0], [0], lw=0, marker="X", color=S.REAL, ms=5.0)]
    fig.legend(real_h, ["real run: stable", "real run: unstable"], loc="upper center", bbox_to_anchor=(0.56, 1.0), ncol=2,
               fontsize=7.5, handlelength=1.0, columnspacing=1.6, borderaxespad=0.15)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.872, bottom=0.083, hspace=0.70)
    S.save(fig, "fig3_from_empty_stability")
    S.finish("fig3_from_empty_stability")


if __name__ == "__main__":
    main()
