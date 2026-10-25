"""F2 (double column): the thrashing curve mu(n), real engine against the simulator, 300k-token pool and native pool.

Closed population of n agent sessions (synchronized start, window [900, 2700) s, FCFS, SGLang 0.5.22, Qwen2.5-7B-Instruct,
one A100 80GB PCIe). Top row: completed sessions per second (filled circles; the lower-variance turns-based estimate as
small plus signs). Bottom row: hit fraction (fraction of turns with cached/prompt > 0.5).

Left, 300k-token pool (Stage C): real single runs; simulator = round-6 calibrated simulator, mixed batching, 17-point grid,
3-seed mean +- 1 s.e. (VALIDATION.md, registered seeds 0-2).
Right, native pool (955,757 tokens, sized by SGLang): real single runs; simulator = the blind prediction B4 at the nearest
simulated pool (900k tokens, registered seed 0, frozen before any native run; the real pool is 6% larger).
lambda_miss = E0a all-miss capacity (turns-based): 0.0715 (300k) and 0.0718 (native) sessions/s.
Run:  python figures/paper/fig2_thrashing_curve.py
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
from matplotlib.patches import Patch  # noqa: E402

REAL_300K = "results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv"
REAL_NATIVE = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv"
SIM_300K = "results/r6_validate_stagec/20261024-025222/supp_fine_curve_mixed.csv"
SIM_900K = "results/r6_predict_report/20261024-034707/b4_runs.csv"
CAL_300K = "results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json"
CAL_NATIVE = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json"
NATIVE_POOL_TOKENS = 955_757       # max_total_num_tokens reported by SGLang (notes/LOG.md, 2026-10-25 native entry)
N_CAP_E2 = 20                      # registered session cap of E2 (configs/agentload_prereg_2026-10-24.yaml)


def main() -> None:
    r300 = pd.read_csv(S.src(REAL_300K))
    r300 = r300[r300["label"] == "sglang-fcfs-r1"].sort_values("n")
    rnat = pd.read_csv(S.src(REAL_NATIVE))
    rnat = rnat[rnat["label"] == "sglang-fcfs-r1-native"].sort_values("n")
    assert len(r300) == 7 and len(rnat) == 7, (len(r300), len(rnat))
    s300 = pd.read_csv(S.src(SIM_300K)).sort_values("n")
    b4 = pd.read_csv(S.src(SIM_900K))
    s900 = b4[(b4["mode"] == "mixed") & (b4["kv_k"] == 900) & (b4["set"].str.startswith("registered"))].sort_values("n")
    assert len(s900) == 7 and (s900["seed"] == 0).all(), len(s900)
    lam300 = json.loads(S.src(CAL_300K).read_text())["lambda_miss_turns_based"]
    lamnat = json.loads(S.src(CAL_NATIVE).read_text())["lambda_miss_turns_based"]

    fig, axes = plt.subplots(2, 2, figsize=(S.COL2, 4.0), sharex=True, sharey="row")
    panels = [
        dict(real=r300, lam=lam300, title="300k-token KV pool (Stage C)", sim="300k"),
        dict(real=rnat, lam=lamnat, title=f"native KV pool ({NATIVE_POOL_TOKENS:,} tokens)", sim="900k"),
    ]
    for j, pn in enumerate(panels):
        axm, axh = axes[0, j], axes[1, j]
        real = pn["real"]
        # simulator
        if pn["sim"] == "300k":
            axm.fill_between(s300["n"], s300["mu_mean"] - s300["mu_se"], s300["mu_mean"] + s300["mu_se"], color=S.SIM, alpha=0.22, lw=0)
            axm.plot(s300["n"], s300["mu_mean"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM, ms=2.6, mew=0.7, zorder=2)
            axh.plot(s300["n"], s300["hit_mean"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="o", mfc="white", mec=S.SIM, ms=2.6, mew=0.7, zorder=2)
        else:
            axm.plot(s900["n"], s900["mu"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="D", mfc="white", mec=S.SIM, ms=3.2, mew=0.8, zorder=2)
            axh.plot(s900["n"], s900["hit_rate"], color=S.SIM, lw=1.0, ls=(0, (4, 2)), marker="D", mfc="white", mec=S.SIM, ms=3.2, mew=0.8, zorder=2)
        # real
        axm.plot(real["n"], real["mu_sessions"], color=S.REAL, lw=1.1, marker="o", ms=3.8, zorder=4)
        axm.plot(real["n"], real["mu_turns_based"], color=S.REAL, lw=0, marker="+", ms=4.2, mew=0.8, zorder=4)
        axh.plot(real["n"], real["hit_frac_turns"], color=S.REAL, lw=1.1, marker="o", ms=3.8, zorder=4)
        # lambda_miss
        axm.axhline(pn["lam"], color=S.VERM, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
        axm.text(11.6, pn["lam"] + 0.012, rf"$\lambda_{{\mathrm{{miss}}}}$ = {pn['lam']:.4f}", fontsize=7.5, color=S.VERM, ha="left", va="bottom")
        axm.set_title(pn["title"], pad=4)
        axh.set_xscale("log")
        axh.set_xlim(11, 420)
        axh.set_xticks([16, 24, 32, 48, 64, 96, 128, 300])
        axh.set_xticklabels(["16", "24", "32", "48", "64", "96", "128", "300"])
        axh.xaxis.set_minor_locator(plt.NullLocator())
        axh.set_xlabel("closed population $n$ (concurrent sessions)")
    axes[0, 0].axvline(N_CAP_E2, color=S.GREEN, lw=0.8, ls=(0, (3, 2)), zorder=1)
    axes[1, 0].axvline(N_CAP_E2, color=S.GREEN, lw=0.8, ls=(0, (3, 2)), zorder=1)
    axes[0, 0].text(N_CAP_E2 * 0.93, 0.52, r"$n_{\mathrm{cap}}$ = 20" "\n(E2 cap)", fontsize=7.5, color=S.GREEN, ha="right", va="center")
    axes[0, 0].set_ylim(0, 0.56)
    axes[0, 0].set_ylabel("completed sessions / s")
    axes[1, 0].set_ylim(-0.03, 1.03)
    axes[1, 0].set_ylabel("hit fraction")

    h1 = [Line2D([0], [0], color=S.REAL, marker="o", ms=3.8, lw=1.1, label="real, sessions/s"),
          Line2D([0], [0], color=S.REAL, marker="+", ms=4.2, mew=0.8, lw=0, label="real, turns-based"),
          Line2D([0], [0], color=S.SIM, ls=(0, (4, 2)), marker="o", mfc="white", ms=2.8, mew=0.7, lw=1.0, label="simulator, mixed batching")]
    axes[0, 0].legend(handles=h1, loc="upper right", bbox_to_anchor=(1.0, 1.0), fontsize=7.5)
    h2 = [Line2D([0], [0], color=S.REAL, marker="o", ms=3.8, lw=1.1, label="real, sessions/s"),
          Line2D([0], [0], color=S.REAL, marker="+", ms=4.2, mew=0.8, lw=0, label="real, turns-based"),
          Line2D([0], [0], color=S.SIM, ls=(0, (4, 2)), marker="D", mfc="white", ms=3.0, mew=0.8, lw=1.0,
                 label="simulator, 900k pool\n(blind prediction B4)")]
    axes[0, 1].legend(handles=h2, loc="upper right", bbox_to_anchor=(1.0, 1.0), fontsize=7.5)
    fig.subplots_adjust(left=0.085, right=0.99, top=0.93, bottom=0.115, hspace=0.12, wspace=0.07)
    S.save(fig, "fig2_thrashing_curve")
    S.finish("fig2_thrashing_curve")


if __name__ == "__main__":
    main()
