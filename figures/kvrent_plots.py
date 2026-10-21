"""Plots for the KV-retention pilot (vector PDF)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def _sel(summ: pd.DataFrame, mix: str, pol: str, eta: float) -> pd.DataFrame:
    d = summ[(summ.mix == mix) & (summ.policy == pol) & (summ.eta == eta)]
    return d.sort_values("lam")


def _offered_util(summ: pd.DataFrame, mix: str) -> pd.Series:
    h = summ[(summ.mix == mix) & (summ.policy == "ALWAYS_HOLD")].groupby("lam").util_mean.mean()
    return h


def make_plots(summ: pd.DataFrame, cfg: dict, out: Path, eta: float | None = None) -> None:
    etas = cfg["policy"]["etas"]
    eta = etas[len(etas) // 2] if eta is None else eta
    pols = cfg["experiment"]["policies"]

    # (1) mean and p95 latency vs utilization, default mix
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    u = _offered_util(summ, "default")
    for pol in pols:
        d = _sel(summ, "default", pol, eta)
        x = d.lam.map(u)
        for a, c in zip(ax, ["mean_lat", "p95"]):
            a.errorbar(x, d[c], yerr=d[c + "_ci95"], marker="o", ms=3, capsize=2, label=pol)
    for a, t in zip(ax, ["Mean program latency", "p95 program latency"]):
        a.set_xlabel("Memory utilization under ALWAYS_HOLD (fraction of M)")
        a.set_ylabel(f"{t} (s, completed programs)")
        a.set_yscale("log")
        a.set_title(f"{t}, default mix, eta={eta:g}", fontsize=9)
    ax[0].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out / "fig1_latency_vs_util_default.pdf")
    plt.close(fig)

    # (2) ratio to ORACLE_STATIC under distribution shift
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    u = _offered_util(summ, "shift")
    for pol in pols:
        if pol == "ORACLE_STATIC":
            continue
        d = _sel(summ, "shift", pol, eta)
        x = d.lam.map(u)
        for a, c in zip(ax, ["ratio_mean", "ratio_p95"]):
            a.errorbar(x, d[c], yerr=d[c + "_ci95"], marker="o", ms=3, capsize=2, label=pol)
    for a, t in zip(ax, ["mean", "p95"]):
        a.axhline(1.0, color="k", lw=0.5)
        a.set_xlabel("Memory utilization under ALWAYS_HOLD, shift mix (fraction of M)")
        a.set_ylabel(f"{t} latency / ORACLE_STATIC (ratio)")
        a.set_yscale("log")
        a.set_title(f"Shift mix (default then heavy), eta={eta:g}", fontsize=9)
    ax[0].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out / "fig2_ratio_to_oracle_shift.pdf")
    plt.close(fig)
