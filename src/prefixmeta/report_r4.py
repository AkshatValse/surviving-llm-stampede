"""Round-4 report of the prefix-cache metastability pilot: ``results/prefix_meta_r4/<ts>/``.

Reads the E-curve / E-burst / E-cap result dirs (never modifies them), the registered design in the pre-registration, and the
round-3 files named there (``lambda_miss(k)``, ``lambda_cap(k)``, phase runs), and writes

* ``prediction_eval.{csv,json}``  R1-R6 under the REGISTERED readings first, then labelled sensitivity / information rows,
* ``table_*.csv``                 the tables behind the figures,
* ``fig1_mu_curves.pdf``          mu(n)/lambda_miss by eviction policy, lambda_miss / lambda_cap / N_lb marked (+ hit rate),
* ``fig2_fluid_burst.pdf``        fluid critical burst b_c(lambda) vs the empirical burst outcomes,
* ``fig3_cap_heatmap.pdf``        cap x eviction recovery heatmap,
* ``fig4_k_scaling.pdf``          mu(n) at k = 0.5, 1, 2 normalised, and lambda_cap(k)/mu*(k),
* ``config.yaml`` / ``preregistration.yaml`` / ``meta.json`` (git commit + dirty flag at the START).

Every number in a figure or table is read from a file in the input result dirs (or the round-3 files named in the
pre-registration). Seeds are the unit of replication; cells that share a seed are CRN-coupled, not independent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from .fluid import fixed_points, make_curve  # noqa: E402
from .mech_runner import _write_json, base_calibration, begin, finish  # noqa: E402
from .r4_eval import Missing, evaluate_all, rows_to_frame, seed_matrix  # noqa: E402
from .r4_runner import burst_counts, cap_cells  # noqa: E402

POLICY_STYLE = {"fcfs_lru": ("#d62728", "o", "-"), "lpm_lru": ("#1f77b4", "s", "-"),
                "fcfs_random": ("#2ca02c", "^", "-"), "fcfs_mru_idle": ("#9467bd", "v", "-")}
POLICY_LABEL = {"fcfs_lru": "FCFS-LRU", "lpm_lru": "LPM-LRU", "fcfs_random": "FCFS-RANDOM",
                "fcfs_mru_idle": "FCFS-MRU_IDLE"}
EVICTION_LABEL = {"lru": "FCFS-LRU", "random": "FCFS-RANDOM", "mru_idle": "FCFS-MRU_IDLE"}


# ------------------------------------------------------------------------------------------------ inputs
def load_design(cfg: dict, repo_dir: Path) -> Dict[str, Any]:
    """``registered_design`` of the pre-registration named in the config."""
    d = yaml.safe_load((repo_dir / cfg["preregistration_file"]).read_text())
    return d["preregistration"]["registered_design"]


def _read_csv(d: Optional[str], name: str) -> Optional[pd.DataFrame]:
    if not d:
        return None
    f = Path(d) / name
    return pd.read_csv(f) if f.exists() else None


def provenance(d: Optional[str]) -> Optional[Dict[str, Any]]:
    if not d:
        return None
    mf = Path(d) / "meta.json"
    if not mf.exists():
        return {"dir": str(d), "meta": None}
    m = json.loads(mf.read_text())
    return {"dir": str(d), "experiment": m.get("experiment"), "git_commit": m.get("git", {}).get("commit"),
            "git_dirty": m.get("git", {}).get("dirty"), "quick": m.get("quick"), "n_runs": m.get("n_runs"),
            "start_time": m.get("start_time"), "status": m.get("status"), "seeds": m.get("seeds")}


def read_round3_values(design: Dict[str, Any], repo_dir: Path) -> Dict[str, Any]:
    """lambda_cap(k) (R6) and lambda_miss(k) (figure normalisation) from the round-3 files named in the registration."""
    lam_cap: Dict[float, float] = {}
    drift: Dict[str, float] = {}
    for ks, rel in design["r6_sources"]["lambda_cap"].items():
        df = pd.read_csv(repo_dir / rel)
        row = df[np.isclose(df["k"].astype(float), float(ks))]
        if len(row):
            lam_cap[float(ks)] = float(row["lambda_cap"].iloc[0])
            exp = design["r6_sources"]["lambda_cap_values_at_writing"].get(ks)
            if exp is not None:
                drift[ks] = abs(lam_cap[float(ks)] - float(exp))
    lam_miss_k: Dict[float, float] = {}
    for ks, rel in design["curve"]["k_scaled"]["lambda_miss_k_source"].items():
        df = pd.read_csv(repo_dir / rel)
        row = df[np.isclose(df["k"].astype(float), float(ks))]
        if len(row):
            lam_miss_k[float(ks)] = float(row["lambda_miss"].iloc[0])
    return {"lambda_cap": lam_cap, "lambda_cap_abs_diff_vs_registered": drift, "lambda_miss_k": lam_miss_k}


# ------------------------------------------------------------------------------------------------ tables
def fluid_table(cr: pd.DataFrame, lam_miss: float, design: Dict[str, Any], n_points: int) -> pd.DataFrame:
    """b_c(lambda) over (mu_inf, mu*) for each k = 1 curve (projected and raw piecewise-linear), as a long table."""
    grid, seeds = design["curve"]["n_grid"], design["curve"]["seeds"]
    rows = []
    for pol in POLICY_LABEL:
        try:
            mu = seed_matrix(cr, pol, 1.0, grid, seeds).mean(axis=1)
        except Missing:
            continue
        for tag, uni in (("unimodal", True), ("raw", False)):
            c = make_curve(grid, mu, unimodal=uni)
            lo, hi = c.mu_inf, c.mu_star
            for lam in np.linspace(lo, hi, n_points + 2)[1:-1]:
                fp = fixed_points(c, lam)
                rows.append({"policy": pol, "curve": tag, "lam": float(lam), "lam_over_lambda_miss": float(lam / lam_miss),
                             "kind": fp.kind, "n1": fp.n1, "n2": fp.n2, "b_c": fp.b_c, "mu_inf": c.mu_inf,
                             "mu_star": c.mu_star, "n_star": c.n_star})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ figures
def fig_curves(ct: pd.DataFrame, lam_miss: float, lam_cap_k1: Optional[float], n_lb: int, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9))
    for pol, (c, m, ls) in POLICY_STYLE.items():
        d = ct[(ct["policy"] == pol) & np.isclose(ct["k"], 1.0)].sort_values("n_nominal")
        if d.empty:
            continue
        off = 1.0 + 0.012 * list(POLICY_STYLE).index(pol)           # tiny x offset so error bars do not overlap
        axes[0].errorbar(d["n_nominal"] * off, d["mu_mean"] / lam_miss, yerr=d["mu_sd"].fillna(0) / lam_miss, color=c,
                         marker=m, ms=4, lw=1.1, ls=ls, capsize=2, label=POLICY_LABEL[pol])
        axes[1].plot(d["n_nominal"] * off, d["hit_rate_mean"], color=c, marker=m, ms=4, lw=1.1, ls=ls)
    for a in axes:
        a.axvline(n_lb, color="k", lw=0.8, ls="-.")
        a.set_xscale("log")
        a.set_xlabel("closed population $n$ (sessions)")
        a.grid(alpha=0.25, which="both")
    ax = axes[0]
    ax.axhline(1.0, color="k", lw=0.8, ls=":", label=r"$\lambda_{\rm miss}$ (all-miss capacity)")
    if lam_cap_k1 is not None:
        ax.axhline(lam_cap_k1 / lam_miss, color="k", lw=0.8, ls="--",
                   label=r"$\lambda_{\rm cap}$ (FCFS, from empty, round 3)")
    ax.axhline(2.0, color="gray", lw=0.7, ls="-.", label=r"$2\lambda_{\rm miss}$ (burst / cap experiments)")
    ax.plot([], [], color="k", lw=0.8, ls="-.", label=f"$N_{{\\rm lb}}$ = {n_lb}")
    ax.set_ylabel(r"$\mu(n)/\lambda_{\rm miss}$  (sessions/s, normalised)")
    axes[1].set_ylabel("hit rate (mean over seeds)")
    axes[1].set_ylim(-0.03, 1.03)
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    ax.set_title(r"closed-population thrashing curve (mean $\pm$ sd over seeds)", fontsize=9)
    axes[1].set_title("hit rate in the same window", fontsize=9)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_fluid_burst(cr: Optional[pd.DataFrame], burst_runs: Optional[pd.DataFrame], lam_miss: float,
                    design: Dict[str, Any], r3_row: Optional[Dict[str, Any]], out: Path) -> None:
    grid, seeds = design["curve"]["n_grid"], design["curve"]["seeds"]
    sizes = design["burst"]["sizes"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9))
    ax = axes[0]
    if cr is not None:
        try:
            mu = seed_matrix(cr, "fcfs_lru", 1.0, grid, seeds).mean(axis=1)
            for uni, ls, lab in ((True, "-", "unimodal-projected PL (registered)"), (False, ":", "raw PL (sensitivity)")):
                c = make_curve(grid, mu, unimodal=uni)
                lams = np.linspace(c.mu_inf, c.mu_star, 400)[1:-1]
                bc = [fixed_points(c, x).b_c for x in lams]
                ax.plot(lams / lam_miss, bc, color="#d62728", ls=ls, lw=1.3, label=f"fluid $b_c(\\lambda)$, FCFS-LRU, {lab}")
        except Missing:
            pass
    ax.axvline(design["burst"]["lam_mult"], color="k", lw=0.7, ls=":")
    nums = (r3_row or {}).get("numbers", {})
    be = nums.get("b_emp")
    if be:
        j = sizes.index(be)
        lo = sizes[j - 1] if j > 0 else 0
        ax.errorbar([design["burst"]["lam_mult"]], [(lo + be) / 2], yerr=[[(be - lo) / 2], [(be - lo) / 2]], color="k",
                    marker="s", ms=5, capsize=3, lw=1.2,
                    label=f"empirical $b_{{emp}}$ (bracket {lo}-{be}; $\\geq$3/5 seeds not recovered)")
    ax.set_xlabel(r"arrival rate $\lambda/\lambda_{\rm miss}$")
    ax.set_ylabel("critical burst $b_c = n_2 - n_1$ (sessions)")
    ax.set_ylim(0, max(sizes) * 1.3)
    ax.grid(alpha=0.25)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    ax.set_title("fluid-predicted critical burst vs empirical", fontsize=9)
    ax = axes[1]
    if burst_runs is not None:
        bc = (burst_runs.assign(recovered=burst_runs["recovered"].astype(bool)).groupby(["policy", "burst_n"])
              .agg(n_runs=("seed", "size"), n_recovered=("recovered", "sum")).reset_index())
        bc["n_not_recovered"] = bc["n_runs"] - bc["n_recovered"]
        for pol, ls, lab in (("fcfs_lru", "-", "FCFS-LRU (primary)"), ("fcfs_random", "--", "FCFS-RANDOM (informational)")):
            d = bc[bc["policy"] == pol].sort_values("burst_n")
            if d.empty:
                continue
            ax.plot(d["burst_n"], d["n_not_recovered"] / d["n_runs"], ls=ls, marker="o", ms=4,
                    color=POLICY_STYLE[pol][0], label=lab)
    bcv = nums.get("fluid", {}).get("b_c")
    if bcv is not None and np.isfinite(bcv):
        ax.axvline(bcv, color="#d62728", lw=1.0, ls="--")
        ax.text(bcv, 1.02, r" fluid $b_c$", color="#d62728", fontsize=7, va="bottom")
    ax.axhline(0.6, color="k", lw=0.6, ls=":")
    ax.set_xlabel("burst size $b$ (sessions within 60 s, on top of $2\\lambda_{\\rm miss}$)")
    ax.set_ylabel("fraction of seeds not recovered")
    ax.set_ylim(-0.05, 1.12)
    ax.grid(alpha=0.25)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.set_title("burst outcomes (last 5000 s: hit $>0.8$ and backlog $<20$ = recovered)", fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_cap_heatmap(cc: Optional[pd.DataFrame], design: Dict[str, Any], n_lb: int, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    evs, caps = design["cap"]["evictions"], design["cap"]["caps"]
    if cc is not None and len(cc):
        Z = np.full((len(evs), len(caps)), np.nan)
        T = [["" for _ in caps] for _ in evs]
        for i, ev in enumerate(evs):
            for j, cap in enumerate(caps):
                r = cc[(cc["eviction"] == ev) & (cc["cap"] == cap)]
                if len(r):
                    Z[i, j] = float(r["n_recovered"].iloc[0]) / float(r["n_runs"].iloc[0])
                    T[i][j] = f"{int(r['n_recovered'].iloc[0])}/{int(r['n_runs'].iloc[0])}"
        im = ax.imshow(Z, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
        for i in range(len(evs)):
            for j in range(len(caps)):
                ax.text(j, i, T[i][j], ha="center", va="center", fontsize=9)
        fig.colorbar(im, ax=ax, label="fraction of seeds recovered")
    ax.set_xticks(range(len(caps)))
    ax.set_xticklabels([f"{c}" + (r" ($N_{\rm lb}$)" if c == n_lb else "") for c in caps], fontsize=8)
    ax.set_yticks(range(len(evs)))
    ax.set_yticklabels([EVICTION_LABEL[e] for e in evs], fontsize=8)
    ax.set_xlabel("session cap $N$ (sessions)")
    ax.set_title(r"recovery from cold 300 at $2\lambda_{\rm miss}$, 150 000 s (seeds recovered / seeds)", fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_k_scaling(ct: pd.DataFrame, lam_miss_k: Dict[float, float], r6_row: Optional[Dict[str, Any]], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.7))
    ax = axes[0]
    cols = {0.5: "#ff7f0e", 1.0: "#d62728", 2.0: "#1f77b4"}
    for k in (0.5, 1.0, 2.0):
        d = ct[(ct["policy"] == "fcfs_lru") & np.isclose(ct["k"], k)].sort_values("n_nominal")
        if d.empty or k not in lam_miss_k:
            continue
        ax.errorbar(d["n"] / k, d["mu_mean"] / lam_miss_k[k], yerr=d["mu_sd"].fillna(0) / lam_miss_k[k], color=cols[k],
                    marker="o", ms=3.5, lw=1.0, capsize=2, label=f"$k$ = {k:g}  ($\\lambda_{{miss}}(k)$ = {lam_miss_k[k]:.4f}/s)")
    ax.set_xscale("log")
    ax.axhline(1.0, color="k", lw=0.7, ls=":")
    ax.set_xlabel("population per unit size, $n/k$ (sessions)")
    ax.set_ylabel(r"$\mu_k(n)/\lambda_{\rm miss}(k)$")
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("FCFS-LRU thrashing curve at three system sizes (normalised)", fontsize=9)
    ax = axes[1]
    nums = (r6_row or {}).get("numbers", {})
    ks = [k for k in (0.5, 1.0, 2.0) if f"k={k}" in nums]
    if ks:
        ax.plot(ks, [nums[f"k={k}"]["rho"] for k in ks], "o-", color="k", label=r"$\lambda_{\rm cap}(k)/\mu^*(k)$ (seed-mean $\mu^*$)")
        for k in ks:
            ax.plot([k] * len(nums[f"k={k}"]["per_seed_rho"]), nums[f"k={k}"]["per_seed_rho"], "x", color="gray", ms=4)
        ax.plot([], [], "x", color="gray", label="per-seed maximum")
        ax.set_xscale("log", base=2)
        ax.set_xticks(ks)
        ax.set_xticklabels([f"{k:g}" for k in ks])
        ax.legend(fontsize=7, frameon=False)
    ax.set_xlabel("system size $k$")
    ax.set_ylabel(r"$\lambda_{\rm cap}(k)/\mu^*(k)$")
    ax.grid(alpha=0.25)
    ax.set_title(r"R6: stability limit over fluid capacity", fontsize=9)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ command
def cmd_report(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    design = load_design(cfg, repo_dir)
    cal = base_calibration(cfg, args, repo_dir)
    lam_miss, n_lb = cal["lambda_miss"], int(cal["N_lb"])
    ctx = begin("r4_report", "prefix_meta_r4", cfg, {**cfg, "registered_design": design, "calibration": cal}, args, repo_dir)
    cr = _read_csv(args.curve_dir, "curve_runs.csv")
    ct = _read_csv(args.curve_dir, "curve_table.csv")
    burst_runs = _read_csv(args.burst_dir, "runs.csv")
    cap_runs = _read_csv(args.cap_dir, "runs.csv")
    src = design["r4_sources"]["phase_runs"]
    phase_runs = pd.read_csv(repo_dir / src) if (repo_dir / src).exists() else None
    r3v = read_round3_values(design, repo_dir)
    rows = evaluate_all(cr, burst_runs, cap_runs, phase_runs, r3v["lambda_cap"] or None, lam_miss, design)
    prov = {"curve": provenance(args.curve_dir), "burst": provenance(args.burst_dir), "cap": provenance(args.cap_dir)}
    flags = [f"{k}: quick run" for k, v in prov.items() if v and v.get("quick")]
    flags += [f"{k}: produced from a dirty git tree" for k, v in prov.items() if v and v.get("git_dirty")]
    flags += [f"{k}: result dir missing" for k, v in prov.items() if v is None]
    flags += [f"lambda_cap({k}) differs from the registered value by {v:.2e}" for k, v in
              r3v["lambda_cap_abs_diff_vs_registered"].items() if v > 1e-5]
    out = ctx.out
    _write_json(out / "prediction_eval.json", {"rows": rows, "inputs": prov, "flags": flags, "lambda_miss": lam_miss,
                                               "round3_values": r3v})
    pe = rows_to_frame(rows)
    pe.to_csv(out / "prediction_eval.csv", index=False)
    pd.DataFrame([{"input": k, **(v or {})} for k, v in prov.items()]).to_csv(out / "table_input_provenance.csv", index=False)

    r3_row = next((r for r in rows if r["id"] == "R3"), None)
    r6_row = next((r for r in rows if r["id"] == "R6"), None)
    if ct is not None:
        ct2 = ct.copy()
        ct2["mu_over_lambda_miss"] = ct2["mu_mean"] / lam_miss
        ct2.to_csv(out / "table_curve.csv", index=False)
        fig_curves(ct, lam_miss, r3v["lambda_cap"].get(1.0), n_lb, out / "fig1_mu_curves.pdf")
        fig_k_scaling(ct, r3v["lambda_miss_k"] | {1.0: lam_miss}, r6_row, out / "fig4_k_scaling.pdf")
    if cr is not None:
        fluid_table(cr, lam_miss, design, int(cfg["report"]["fluid_lambda_points"])).to_csv(out / "table_fluid_bc.csv", index=False)
    fig_fluid_burst(cr, burst_runs, lam_miss, design, r3_row, out / "fig2_fluid_burst.pdf")
    if burst_runs is not None:
        burst_counts(burst_runs.assign(recovered=burst_runs["recovered"].astype(bool))).to_csv(out / "table_burst_counts.csv",
                                                                                              index=False)
    cc = None
    if cap_runs is not None:
        cc = cap_cells(cap_runs.assign(recovered=cap_runs["recovered"].astype(bool)))
        cc.to_csv(out / "table_cap_cells.csv", index=False)
    fig_cap_heatmap(cc, design, n_lb, out / "fig3_cap_heatmap.pdf")
    finish(ctx, [], {"inputs": prov, "flags": flags, "lambda_miss": lam_miss,
                     "verdicts": {r["id"]: r["verdict"] for r in rows},
                     "note": "headline rows are the registered readings; sensitivity / information rows never decide a verdict"})
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(pe[["id", "reading", "verdict", "notes"]].to_string())
    for f in flags:
        print("FLAG:", f)
    print("result dir:", out)
    return out
