"""F2 (double column): the thrashing curve mu(n), real engine against the simulator, in three engine cells.

Closed population of n agent sessions (synchronized start, window [900, 2700) s, FCFS, Qwen2.5-7B-Instruct, one A100 80GB
PCIe, one run per n). Top row: completed sessions per second (filled circles; the lower-variance turns-based estimate as
plus signs, drawn larger than the circles so that both stay visible where they coincide). Bottom row: hit fraction
(fraction of turns with cached/prompt > 0.5).

Left, SGLang 0.5.22, 300k-token pool (Stage C): simulator = round-6 calibrated simulator, mixed batching, 17-point grid,
3-seed mean +- 1 s.e. (VALIDATION.md, registered seeds 0-2).
Middle, SGLang 0.5.22, native pool (955,757 tokens, sized by SGLang): simulator = the blind prediction B4 at the nearest
simulated pool (900k tokens, registered seed 0, frozen before any native run; the real pool is 6% larger), and the round-8
run B4n at the real native pool (955,757 tokens, mixed batching, 3-seed mean; its spec was written after the real native
curve was known, so it is not a blind test).
Right, vLLM 0.32.0, 300k-token pool (18,750 blocks of 16): vLLM's own Stage C (jobs 17162959-61); simulator = the blind
prediction B4v (notes/PREDICTIONS_vllm.md, frozen at tag r9-vllm-predictions-frozen before any vLLM Stage C result),
variant V1 (the SGLang-calibrated engine with its token costs scaled to vLLM's measured all-miss token rate, so its
sessions/s are in vLLM's units), mixed batching (the primary mode), 10-seed mean +- 1 s.e. The other three B4v
configurations (V0, and the separate batching mode) are not drawn; the README gives how far they lie from V1 mixed.
Horizontal dotted line: lambda_miss = the cell's E0a all-miss capacity (turns-based), 0.0715 / 0.0718 / 0.0657 sessions/s.
Green dashed line: the cell's registered session cap n_cap (20 / 64 / 20).
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
import yaml  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

REAL_300K = "results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv"
REAL_NATIVE = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv"
REAL_VLLM = "results/nova/stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv"
SIM_300K = "results/r6_validate_stagec/20261024-025222/supp_fine_curve_mixed.csv"
SIM_900K = "results/r6_predict_report/20261024-034707/b4_runs.csv"
SIM_B4N = "results/r8_native_report/20261025-150146/mixed_curves_curve_runs.csv"   # B4n: pool 955,757, mixed, seeds 0-2
SIM_B4V = "results/r9_vllm_report/20261030-122723/v1_mixed_curves_curve_runs.csv"   # B4v: V1, mixed, pool 300k, seeds 0-9
CAL_300K = "results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json"
CAL_NATIVE = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json"
# vLLM lambda_ref: the registration's input copy, byte-identical to the vLLM E0a analysis it was copied from (checked below)
CAL_VLLM = "prereg/inputs/2026-10-25-vllm/calibration.json"
CAL_VLLM_ORIG = "results/nova/e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json"
PREREG_VLLM = "configs/agentload_prereg_2026-10-30_vllm.yaml"
NATIVE_POOL_TOKENS = 955_757       # max_total_num_tokens reported by SGLang (notes/LOG.md, 2026-10-25 native entry)
N_CAP_E2 = 20                      # registered session cap of E2 (configs/agentload_prereg_2026-10-24.yaml)
N_CAP_NATIVE = 64                  # registered native cap (configs/agentload_prereg_2026-10-25_native.yaml)

SIM_LS = (0, (4, 2))


def _sim_line(ax, x, y, marker, ms, **kw):
    ax.plot(x, y, color=S.SIM, lw=1.0, ls=SIM_LS, marker=marker, mfc="white", mec=S.SIM, ms=ms, mew=0.75, zorder=2, **kw)


def main() -> None:
    r300 = pd.read_csv(S.src(REAL_300K))
    r300 = r300[r300["label"] == "sglang-fcfs-r1"].sort_values("n")
    rnat = pd.read_csv(S.src(REAL_NATIVE))
    rnat = rnat[rnat["label"] == "sglang-fcfs-r1-native"].sort_values("n")
    rvl = pd.read_csv(S.src(REAL_VLLM))
    rvl = rvl[rvl["label"] == "vllm-fcfs"].sort_values("n")
    assert len(r300) == 7 and len(rnat) == 7 and len(rvl) == 9, (len(r300), len(rnat), len(rvl))
    assert (rvl["n_runs"] == 1).all()
    s300 = pd.read_csv(S.src(SIM_300K)).sort_values("n")
    b4 = pd.read_csv(S.src(SIM_900K))
    s900 = b4[(b4["mode"] == "mixed") & (b4["kv_k"] == 900) & (b4["set"].str.startswith("registered"))].sort_values("n")
    assert len(s900) == 7 and (s900["seed"] == 0).all(), len(s900)
    b4n = pd.read_csv(S.src(SIM_B4N))
    assert set(b4n["seed"]) == {0, 1, 2} and (b4n["workload"] == "exp5").all()
    b4n = b4n.groupby("n", as_index=False)[["mu", "hit_rate"]].mean().sort_values("n")
    b4v = pd.read_csv(S.src(SIM_B4V))
    assert set(b4v["seed"]) == set(range(10)) and (b4v["workload"] == "exp5").all()
    b4v = b4v.groupby("n").agg(mu=("mu", "mean"), mu_sd=("mu", "std"), k=("mu", "size"), hit=("hit_rate", "mean"))
    assert (b4v["k"] == 10).all() and len(b4v) == 9
    b4v["mu_se"] = b4v["mu_sd"] / np.sqrt(b4v["k"])
    b4v = b4v.reset_index().sort_values("n")
    lam300 = json.loads(S.src(CAL_300K).read_text())["lambda_miss_turns_based"]
    lamnat = json.loads(S.src(CAL_NATIVE).read_text())["lambda_miss_turns_based"]
    assert S.src(CAL_VLLM).read_bytes() == S.src(CAL_VLLM_ORIG).read_bytes()
    lamvl = json.loads(S.src(CAL_VLLM).read_text())["lambda_miss_turns_based"]
    reg = yaml.safe_load(S.src(PREREG_VLLM).read_text(encoding="utf-8"))["measured"]
    assert reg["lambda_ref"] == lamvl, (reg["lambda_ref"], lamvl)
    n_cap_vllm = int(reg["n_cap"])

    fig, axes = plt.subplots(2, 3, figsize=(S.COL2, 4.55), sharex=True, sharey="row")
    panels = [
        dict(real=r300, lam=lam300, title="SGLang 0.5.22\n300k-token pool", sim="300k", cap=N_CAP_E2),
        dict(real=rnat, lam=lamnat, title=f"SGLang 0.5.22\nnative pool ({NATIVE_POOL_TOKENS:,} tokens)", sim="900k",
             cap=N_CAP_NATIVE),
        dict(real=rvl, lam=lamvl, title="vLLM 0.32.0\n300k-token pool", sim="vllm", cap=n_cap_vllm),
    ]
    for j, pn in enumerate(panels):
        axm, axh = axes[0, j], axes[1, j]
        real = pn["real"]
        # simulator
        if pn["sim"] == "300k":
            axm.fill_between(s300["n"], s300["mu_mean"] - s300["mu_se"], s300["mu_mean"] + s300["mu_se"], color=S.SIM, alpha=0.22, lw=0)
            _sim_line(axm, s300["n"], s300["mu_mean"], "o", 2.6)
            _sim_line(axh, s300["n"], s300["hit_mean"], "o", 2.6)
        elif pn["sim"] == "900k":
            for ax, col in ((axm, "mu"), (axh, "hit_rate")):
                ax.plot(b4n["n"], b4n[col], color=S.LGRAY, lw=0.9, ls=(0, (1, 1.2)), marker="s", mfc="white", mec=S.GRAY, ms=2.4,
                        mew=0.6, zorder=1.5)
            _sim_line(axm, s900["n"], s900["mu"], "D", 3.0)
            _sim_line(axh, s900["n"], s900["hit_rate"], "D", 3.0)
        else:
            axm.fill_between(b4v["n"], b4v["mu"] - b4v["mu_se"], b4v["mu"] + b4v["mu_se"], color=S.SIM, alpha=0.22, lw=0)
            _sim_line(axm, b4v["n"], b4v["mu"], "^", 3.0)
            _sim_line(axh, b4v["n"], b4v["hit"], "^", 3.0)
        # real
        axm.plot(real["n"], real["mu_sessions"], color=S.REAL, lw=1.1, marker="o", ms=3.4, zorder=4)
        axm.plot(real["n"], real["mu_turns_based"], color=S.REAL, lw=0, marker="+", ms=6.5, mew=0.8, zorder=5)
        axh.plot(real["n"], real["hit_frac_turns"], color=S.REAL, lw=1.1, marker="o", ms=3.4, zorder=4)
        # lambda_miss
        axm.axhline(pn["lam"], color=S.VERM, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
        axm.text(405, pn["lam"] - 0.008, rf"$\lambda_{{\mathrm{{miss}}}}$ = {pn['lam']:.4f}", fontsize=7.5, color=S.VERM, ha="right",
                 va="top")
        # registered session cap
        for ax in (axm, axh):
            ax.axvline(pn["cap"], color=S.GREEN, lw=0.8, ls=(0, (3, 2)), zorder=1)
        axh.text(pn["cap"] * 0.95, 0.80, rf"$n_{{\mathrm{{cap}}}}$ = {pn['cap']}", fontsize=7.5, color=S.GREEN,
                 ha="right", va="top", rotation=90)
        axm.set_title(pn["title"], pad=4, fontsize=8.5)
        axh.set_xscale("log")
        axh.set_xlim(11, 420)
        axh.set_xticks([16, 24, 32, 48, 64, 96, 128, 300])
        axh.set_xticklabels(["16", "24", "32", "48", "64", "96", "128", "300"])
        axh.xaxis.set_minor_locator(plt.NullLocator())
        axh.set_xlabel("closed population $n$")
    axes[0, 0].set_ylim(0, 0.56)
    axes[0, 0].set_ylabel("completed sessions / s")
    axes[1, 0].set_ylim(-0.03, 1.03)
    axes[1, 0].set_ylabel("hit fraction")

    band = Patch(facecolor=S.SIM, alpha=0.22, lw=0)
    sim_o = Line2D([0], [0], color=S.SIM, ls=SIM_LS, marker="o", mfc="white", mec=S.SIM, ms=2.8, mew=0.75, lw=1.0)
    sim_t = Line2D([0], [0], color=S.SIM, ls=SIM_LS, marker="^", mfc="white", mec=S.SIM, ms=3.0, mew=0.75, lw=1.0)
    handles = [
        Line2D([0], [0], color=S.REAL, marker="o", ms=3.4, lw=1.1),
        Line2D([0], [0], color=S.REAL, marker="+", ms=6.5, mew=0.8, lw=0),
        (band, sim_o),
        Line2D([0], [0], color=S.SIM, ls=SIM_LS, marker="D", mfc="white", mec=S.SIM, ms=3.0, mew=0.75, lw=1.0),
        Line2D([0], [0], color=S.LGRAY, ls=(0, (1, 1.2)), marker="s", mfc="white", mec=S.GRAY, ms=2.4, mew=0.6, lw=0.9),
        (band, sim_t),
    ]
    labels = [
        "real engine, sessions/s (one run per $n$)",
        "real engine, turns-based estimate",
        "left: calibrated simulator, 3 seeds, mean $\\pm$ 1 s.e.",
        "middle: blind prediction B4, 900k-token pool, seed 0",
        f"middle: B4n, {NATIVE_POOL_TOKENS:,} tokens, 3 seeds (not blind)",
        "right: blind prediction B4v (V1, mixed), 10 seeds, mean $\\pm$ 1 s.e.",
    ]
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=2, fontsize=7.5, columnspacing=2.0,
               handlelength=2.2)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.905, bottom=0.205, hspace=0.12, wspace=0.08)
    S.save(fig, "fig2_thrashing_curve")
    S.finish("fig2_thrashing_curve")


if __name__ == "__main__":
    main()
