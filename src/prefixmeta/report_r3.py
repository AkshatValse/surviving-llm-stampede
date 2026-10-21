"""Round-3 report of the prefix-cache metastability pilot: ``results/prefix_meta_r3/<ts>/``.

Reads the phase / mech / escape / escape_inwindow / robust result dirs (never modifies them) and writes

* ``prediction_eval.{csv,json}``   P1-P8 verdicts with numbers (amended and registered readings side by side),
* ``table_*.csv``                  the summary tables behind the figures,
* ``table_pre_full_runs.csv``      every round-2 quick / smoke run that existed before the full runs, with the
                                   commit / dirty flag, its time relative to amendment 1, and what it showed,
* ``fig1_phase_diagram.pdf``       recovery fraction vs lambda / lambda_miss (FCFS / LPM / PEEK) with lambda_miss and
                                   lambda_cap marked,
* ``fig2_mechanisms.pdf``          recovery and burst outcomes per policy + each policy's stability limit / ceiling,
* ``fig3_escape_vs_k.pdf``         escape time vs system size (KM medians with CIs and exponential-MLE means, log scale),
* ``fig4_robustness.pdf``          R and the FCFS burst trap per workload variant,
* ``config.yaml`` / ``preregistration.yaml`` / ``meta.json`` (git commit + dirty flag at the START).

Every number in a figure or table is read from a file in the input result dirs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

FAMILY_COLOR = {"wc": "#7f7f7f", "peek": "#1f77b4", "pin": "#ff7f0e", "eager": "#9467bd", "cap": "#2ca02c"}
POLICY_FAMILY = {"fcfs": "wc", "lpm": "wc", "progfcfs": "wc", "peek_rank": "wc", "peek": "peek", "peek_lpm": "peek",
                 "ttl5": "pin", "ttl10": "pin", "ttl20": "pin", "ttlf5": "pin", "ttlf10": "pin", "ttlf20": "pin",
                 "ttl10e": "eager", "ttl20e": "eager", "ttl10ef": "eager", "ttl20ef": "eager",
                 "lb_cap": "cap", "cap_1p3": "cap", "aimd_cap": "cap", "concur_cap": "cap"}
FAMILY_NAME = {"wc": "work-conserving", "peek": "hard queued-session pin", "pin": "blocking TTL pin (idle-only release)",
               "eager": "Continuum-like eager unpin", "cap": "session cap"}


def _color(policy: str) -> str:
    return FAMILY_COLOR[POLICY_FAMILY.get(policy, "wc")]


def _legend_families(ax, present: Sequence[str]) -> None:
    fams = []
    for p in present:
        f = POLICY_FAMILY.get(p, "wc")
        if f not in fams:
            fams.append(f)
    handles = [plt.Rectangle((0, 0), 1, 1, color=FAMILY_COLOR[f]) for f in fams]
    ax.legend(handles, [FAMILY_NAME[f] for f in fams], fontsize=6, loc="best", frameon=False)


# ------------------------------------------------------------------------------------------------ figures
def fig_phase(phase_runs: pd.DataFrame, lam_miss: float, lam_cap_round1: float, out: Path) -> pd.DataFrame:
    """Recovery fraction (n_recovered / n_runs) vs lambda / lambda_miss for each policy, plus the mean tail hit rate.
    Returns the plotted table."""
    runs = phase_runs.copy()
    runs["recovered"] = runs["recovered"].astype(bool)
    g = runs.groupby(["policy", "lam_mult"]).agg(n_runs=("recovered", "size"), n_recovered=("recovered", "sum"),
                                                 tail_hit=("tail_hit_rate", "mean")).reset_index()
    g["frac_recovered"] = g["n_recovered"] / g["n_runs"]
    pols = [p for p in ("fcfs", "lpm", "peek_rank", "peek") if p in set(g["policy"])]
    style = {"fcfs": ("#d62728", "o", "-"), "lpm": ("#1f77b4", "s", "-"), "peek_rank": ("#2ca02c", "^", "-"),
             "peek": ("#9467bd", "v", "--")}
    names = {"fcfs": "FCFS", "lpm": "LPM", "peek_rank": "PEEK-like (rank only, work-conserving)",
             "peek": "queued-session hard pin (non-work-conserving)"}
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4))
    for i, p in enumerate(pols):
        d = g[g["policy"] == p].sort_values("lam_mult")
        c, m, ls = style[p]
        off = (i - (len(pols) - 1) / 2) * 0.012
        axes[0].plot(d["lam_mult"] * (1 + off), d["frac_recovered"], color=c, marker=m, ls=ls, ms=5, lw=1.2,
                     label=names[p])
        axes[1].plot(d["lam_mult"], d["tail_hit"], color=c, marker=m, ls=ls, ms=5, lw=1.2)
    cap_mult = lam_cap_round1 / lam_miss
    for ax in axes:
        ax.axvline(1.0, color="k", lw=0.8, ls=":")
        ax.axvline(cap_mult, color="k", lw=0.8, ls="--")
        ax.set_xlabel(r"arrival rate $\lambda/\lambda_{\rm miss}$")
        ax.grid(alpha=0.25)
    ymax = axes[0].get_ylim()[1]
    axes[0].text(1.0, 0.55, r" $\lambda_{\rm miss}$", rotation=90, fontsize=7, va="center")
    axes[0].text(cap_mult, 0.55, r" $\lambda_{\rm cap}$ (LPM, from empty, round 1)", rotation=90, fontsize=7,
                 va="center")
    axes[0].set_ylabel("fraction of seeds recovered from 300 cold sessions")
    axes[0].set_ylim(-0.05, max(1.05, ymax))
    axes[1].set_ylabel("tail hit rate (mean over seeds)")
    axes[1].set_ylim(-0.05, 1.05)
    axes[0].legend(fontsize=6, loc="upper right", frameon=False)
    axes[0].set_title("cold-start recovery", fontsize=9)
    axes[1].set_title("hit rate in the last 5000 s", fontsize=9)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return g


def fig_mechanisms(cold: pd.DataFrame, burst: pd.DataFrame, limits: Optional[pd.DataFrame],
                   capacity: Optional[pd.DataFrame], lam_miss: float, policies: Sequence[str], out: Path
                   ) -> pd.DataFrame:
    """(a) cold-300 recovery fraction at 1.5x and 2x, (b) burst outcomes at 2x (recovered / partial / trapped),
    (c) from-empty stable limit and good-state capacity ceiling in units of lambda_miss. Returns a wide table."""
    pols = [p for p in policies if p in set(cold["policy"])]
    rec = cold.assign(recovered=cold["recovered"].astype(bool)).groupby(["policy", "lam_mult"]).agg(
        n=("recovered", "size"), k=("recovered", "sum")).reset_index()
    bur = burst.assign(trapped=burst["trapped"].astype(bool), burst_recovered=burst["burst_recovered"].astype(bool))
    bg = bur.groupby("policy").agg(n=("trapped", "size"), trapped=("trapped", "sum"),
                                   recovered=("burst_recovered", "sum")).reset_index()
    bg["partial"] = bg["n"] - bg["trapped"] - bg["recovered"]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 0.32 * len(pols) + 1.8), sharey=True)
    y = np.arange(len(pols))[::-1]
    h = 0.38
    for j, (m, hatch) in enumerate(((1.5, None), (2.0, "//"))):
        vals = []
        for p in pols:
            r = rec[(rec["policy"] == p) & np.isclose(rec["lam_mult"], m)]
            vals.append(float(r["k"].iloc[0] / r["n"].iloc[0]) if len(r) else np.nan)
        axes[0].barh(y + (0.5 - j) * h, vals, h, color=[_color(p) for p in pols], hatch=hatch, edgecolor="white")
    axes[0].set_xlim(0, 1.05)
    axes[0].set_xlabel("fraction recovered, cold start 300 (solid 1.5x, hatched 2x)")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(pols, fontsize=7)
    bgi = bg.set_index("policy")
    left = np.zeros(len(pols))
    for col, color, lab in (("recovered", "#2ca02c", "burst-recovered"), ("partial", "#ffbb78", "partial"),
                            ("trapped", "#d62728", "trapped")):
        v = np.array([float(bgi.loc[p, col] / bgi.loc[p, "n"]) if p in bgi.index else np.nan for p in pols])
        axes[1].barh(y, np.nan_to_num(v), 0.7, left=left, color=color, label=lab)
        left += np.nan_to_num(v)
    axes[1].set_xlim(0, 1.0)
    axes[1].set_xlabel("burst of 200 at 2x: fraction of seeds")
    axes[1].legend(fontsize=6, loc="lower right", frameon=True)
    if limits is not None:
        li = limits.set_index("policy")
        v = [float(li.loc[p, "lambda_cap"] / lam_miss) if p in li.index else np.nan for p in pols]
        axes[2].barh(y + 0.2, v, 0.38, color=[_color(p) for p in pols], edgecolor="white", label="from-empty stable limit")
    if capacity is not None:
        ci = capacity.set_index("policy")
        v = [float(ci.loc[p, "ceiling_sessions_per_s"] / lam_miss) if p in ci.index else np.nan for p in pols]
        axes[2].barh(y - 0.2, v, 0.38, color=[_color(p) for p in pols], hatch="xx", edgecolor="white")
    axes[2].axvline(1.0, color="k", lw=0.7, ls=":")
    axes[2].set_xlabel(r"$/\lambda_{\rm miss}$: stable limit (solid), good-state ceiling (hatched)")
    _legend_families(axes[2], pols)
    for ax in axes:
        ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    wide = pd.DataFrame({"policy": pols})
    for m in (1.5, 2.0):
        wide[f"recovered_{m:g}x"] = [
            (f"{int(r['k'].iloc[0])}/{int(r['n'].iloc[0])}" if len(r) else "") for r in
            (rec[(rec["policy"] == p) & np.isclose(rec["lam_mult"], m)] for p in pols)]
    wide["burst_recovered"] = [int(bgi.loc[p, "recovered"]) if p in bgi.index else np.nan for p in pols]
    wide["burst_partial"] = [int(bgi.loc[p, "partial"]) if p in bgi.index else np.nan for p in pols]
    wide["burst_trapped"] = [int(bgi.loc[p, "trapped"]) if p in bgi.index else np.nan for p in pols]
    wide["burst_n"] = [int(bgi.loc[p, "n"]) if p in bgi.index else np.nan for p in pols]
    if limits is not None:
        li = limits.set_index("policy")
        wide["stable_limit_over_lambda_miss"] = [float(li.loc[p, "lambda_cap"] / lam_miss) if p in li.index else np.nan
                                                 for p in pols]
    if capacity is not None:
        ci = capacity.set_index("policy")
        wide["ceiling_over_lambda_miss"] = [float(ci.loc[p, "ceiling_sessions_per_s"] / lam_miss) if p in ci.index
                                            else np.nan for p in pols]
        wide["ceiling_ratio_to_lpm"] = [float(ci.loc[p, "ratio_to_lpm"]) if p in ci.index else np.nan for p in pols]
    return wide


def fig_escape(esc_reg: Optional[pd.DataFrame], esc_iw: Optional[pd.DataFrame], out: Path) -> pd.DataFrame:
    """Escape time vs k on a log axis: top row KM median with its Greenwood log-log interval (an upward arrow at the
    horizon when the median is censored), bottom row the exponential-MLE mean with its exact Poisson interval."""
    panels = [("registered sizes", esc_reg), ("in-window sizes", esc_iw)]
    panels = [(t, d) for t, d in panels if d is not None and len(d)]
    fig, axes = plt.subplots(2, len(panels), figsize=(5.2 * len(panels), 6.2), squeeze=False)
    cmap = plt.get_cmap("viridis")
    rows = []
    for c, (title, d) in enumerate(panels):
        mults = sorted(set(d["lam_mult"].astype(float)))
        for r, (col, lo, hi, ylab) in enumerate((("km_median", "km_median_ci_lo", "km_median_ci_hi", "KM median (s)"),
                                                 ("exp_mean", "exp_mean_ci_lo", "exp_mean_ci_hi",
                                                  "exponential-MLE mean (s)"))):
            ax = axes[r][c]
            for i, m in enumerate(mults):
                for sc, mk, fill in (("calibrated", "o", True), ("fluid", "s", False)):
                    dd = d[(d["scaling"] == sc) & np.isclose(d["lam_mult"].astype(float), m)].sort_values("k") \
                        if "scaling" in d.columns else d[np.isclose(d["lam_mult"].astype(float), m)].sort_values("k")
                    if not len(dd):
                        continue
                    colr = cmap(i / max(1, len(mults) - 1) * 0.85)
                    x = dd["k"].to_numpy(dtype=float)
                    y = dd[col].to_numpy(dtype=float)
                    horizon = dd["horizon"].to_numpy(dtype=float)
                    fin = np.isfinite(y)
                    xs = x * (1.0 if sc == "calibrated" else 1.03)
                    if fin.any():
                        yl = np.where(fin, y - dd[lo].to_numpy(dtype=float), np.nan)
                        yh = np.where(fin, dd[hi].to_numpy(dtype=float) - y, np.nan)
                        yl = np.where(np.isfinite(yl) & (yl >= 0), yl, 0.0)
                        yh = np.where(np.isfinite(yh) & (yh >= 0), yh, 0.0)
                        ax.errorbar(xs[fin], y[fin], yerr=[yl[fin], yh[fin]], marker=mk, color=colr,
                                    mfc=colr if fill else "white", ms=5, lw=1.0, capsize=2,
                                    label=f"{m:g}x {sc}")
                    cens = ~fin
                    if cens.any():
                        ax.scatter(xs[cens], horizon[cens], marker="^", color=colr, s=36,
                                   facecolors=colr if fill else "none", zorder=3)
                    for _, rw in dd.iterrows():
                        rows.append({"panel": title, "estimator": col, "scaling": sc, "lam_mult": m, "k": rw["k"],
                                     "value": rw[col], "ci_lo": rw[lo], "ci_hi": rw[hi], "n": rw["n"],
                                     "n_events": rw["n_events"], "horizon": rw["horizon"],
                                     "lam_over_cap": rw.get("lam_over_cap", np.nan)})
            ax.set_yscale("log")
            ax.set_xscale("log", base=2)
            ks = sorted(set(d["k"].astype(float)))
            ax.set_xticks(ks)
            ax.set_xticklabels([f"{k:g}" for k in ks])
            ax.set_xlabel("system size k")
            ax.set_ylabel(ylab)
            ax.grid(alpha=0.25, which="both")
            if r == 0:
                ax.set_title(f"{title} (triangles: median censored at the horizon)", fontsize=8)
            hl, _ = ax.get_legend_handles_labels()
            if hl and r == 0:
                ax.legend(fontsize=6, frameon=False, loc="best")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return pd.DataFrame(rows)


def fig_robust(rob: pd.DataFrame, out: Path, r_threshold: float = 1.5) -> pd.DataFrame:
    """R = lambda_cap / lambda_miss (LPM and FCFS from-empty limits) and the FCFS burst outcome per variant."""
    v = rob.copy()
    x = np.arange(len(v))
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.6))
    axes[0].bar(x - 0.2, v["R_lpm"], 0.4, color="#1f77b4", label="LPM")
    if "R_fcfs" in v.columns:
        axes[0].bar(x + 0.2, v["R_fcfs"], 0.4, color="#d62728", label="FCFS")
    axes[0].axhline(r_threshold, color="k", ls="--", lw=0.8)
    axes[0].text(len(v) - 0.5, r_threshold, " 1.5", fontsize=7, va="bottom", ha="right")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(v["variant"], rotation=35, ha="right", fontsize=7)
    axes[0].set_ylabel(r"$R=\lambda_{\rm cap}/\lambda_{\rm miss}$ (from empty)")
    axes[0].legend(fontsize=7, frameon=False)
    n = v["burst_n_runs"].astype(float)
    trapped = v["burst_n_trapped"].astype(float) / n
    rec = v["burst_n_recovered"].astype(float) / n
    part = 1.0 - trapped - rec
    axes[1].bar(x, trapped, 0.6, color="#d62728", label="trapped")
    axes[1].bar(x, part, 0.6, bottom=trapped, color="#ffbb78", label="partial")
    axes[1].bar(x, rec, 0.6, bottom=trapped + part, color="#2ca02c", label="burst-recovered")
    for i, hold in enumerate(v["holds"].astype(bool)):
        axes[1].text(i, 1.02, "holds" if hold else "fails", ha="center", fontsize=6)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(v["variant"], rotation=35, ha="right", fontsize=7)
    axes[1].set_ylabel("FCFS, burst of 200 at 1.6x: fraction of seeds")
    axes[1].set_ylim(0, 1.12)
    axes[1].legend(fontsize=7, frameon=False, loc="lower right")
    for ax in axes:
        ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    cols = [c for c in ("variant", "lambda_miss", "lambda_cap_lpm", "R_lpm", "lambda_cap_fcfs", "R_fcfs",
                        "burst_lam_mult", "burst_n_runs", "burst_n_trapped", "burst_n_recovered", "hit_eval_mean",
                        "burst_below_lpm_limit", "holds") if c in v.columns]
    return v[cols]


# ------------------------------------------------------------------------------------------------ provenance
def _epoch(stamp: str) -> float:
    return time.mktime(time.strptime(stamp, "%Y-%m-%dT%H:%M:%S"))


def _git_epoch(repo_dir: Path, rev: str) -> Optional[float]:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct", rev], cwd=repo_dir, capture_output=True, text=True,
                             timeout=30).stdout.strip()
        return float(out) if out else None
    except Exception:  # pragma: no cover
        return None


def _what_it_showed(d: Path) -> str:
    """Compact, file-derived summary of an earlier quick / smoke result dir (tables only; no re-computation)."""
    bits: List[str] = []
    f = d / "mech_burst_table.csv"
    if f.exists():
        b = pd.read_csv(f)
        bits.append("burst@2x trapped/n: " + ", ".join(f"{r.policy} {int(r.n_trapped)}/{int(r.n_runs)}"
                                                       for r in b.itertuples()))
    f = d / "mech_cold_table.csv"
    if f.exists():
        c = pd.read_csv(f)
        bits.append("cold300 recovered/n: " + ", ".join(f"{r.policy}@{r.lam_mult:g}x {int(r.n_recovered)}/{int(r.n_runs)}"
                                                        for r in c.itertuples()))
    f = d / "phase_table.csv"
    if f.exists():
        p = pd.read_csv(f)
        bits.append("phase recovered/n: " + ", ".join(f"{r.policy}@{r.lam_mult:g}x {int(r.n_recovered)}/{int(r.n_runs)}"
                                                      for r in p.itertuples()))
    f = d / "escape_summary.csv"
    if f.exists():
        e = pd.read_csv(f)
        bits.append("escape events/n: " + ", ".join(f"k={r.k:g}@{r.lam_mult:g}x {int(r.n_events)}/{int(r.n)}"
                                                    for r in e.itertuples()))
    f = d / "robust_summary.csv"
    if f.exists():
        r_ = pd.read_csv(f)
        bits.append("robust R_lpm/trapped: " + ", ".join(f"{r.variant} {r.R_lpm:.2f}/{int(r.burst_n_trapped)}"
                                                         for r in r_.itertuples()))
    f = d / "prediction_eval.csv"
    if f.exists():
        e2 = pd.read_csv(f)
        bits.append("verdicts: " + ", ".join(f"{r.id}={r.verdict}" for r in e2.itertuples()))
    return " | ".join(bits)


def pre_full_run_table(results_root: Path, repo_dir: Path, amendment1_commit: str = "cb9d0ce") -> pd.DataFrame:
    """One row per earlier round-2 result dir (``prefix_meta_{phase,mech,escape,escape_inwindow,robust,eval}*_quick``
    and ``*smoke*``): when it ran, at which commit, dirty or not, relative to the commit time of amendment 1, and what
    its tables showed. These are quick / smoke sizes (1 seed, short horizons): provenance only, not evidence."""
    t_am = _git_epoch(repo_dir, amendment1_commit)
    rows = []
    for name_dir in sorted(results_root.glob("prefix_meta_*")):
        if not name_dir.is_dir():
            continue
        n = name_dir.name
        if not any(n.startswith(f"prefix_meta_{e}") for e in ("phase", "mech", "escape", "robust", "eval")):
            continue
        for d in sorted(name_dir.glob("*")):
            mf = d / "meta.json"
            if not mf.exists():
                continue
            m = json.loads(mf.read_text())
            if not (m.get("quick") or "smoke" in n):
                continue
            start = m.get("start_time", "")
            t0 = _epoch(start) if start else None
            rel = ("unknown" if t_am is None or t0 is None else ("before amendment 1" if t0 < t_am
                                                                 else "after amendment 1"))
            g = m.get("git", {})
            rows.append({"dir": str(d.relative_to(results_root.parent)) if results_root.parent in d.parents else str(d),
                         "experiment": m.get("experiment"), "start_time": start, "git_commit": g.get("commit", "")[:7],
                         "git_dirty": g.get("dirty"), "quick": m.get("quick"), "tag": m.get("tag"),
                         "n_runs": m.get("n_runs"), "relation_to_amendment_1": rel, "what_it_showed": _what_it_showed(d)})
    return pd.DataFrame(rows).sort_values("start_time").reset_index(drop=True) if rows else pd.DataFrame()


def input_provenance_table(dirs: Dict[str, Optional[str]]) -> pd.DataFrame:
    rows = []
    for name, d in dirs.items():
        if not d:
            continue
        m = json.loads((Path(d) / "meta.json").read_text())
        g = m.get("git", {})
        rows.append({"input": name, "dir": str(d), "git_commit": g.get("commit"), "git_dirty": g.get("dirty"),
                     "start_time": m.get("start_time"), "end_time": m.get("end_time"), "wall_s": m.get("wall_s"),
                     "n_runs": m.get("n_runs"), "n_limit_search_runs": m.get("n_limit_search_runs"),
                     "quick": m.get("quick"), "workers": m.get("workers"), "hostname": m.get("hostname"),
                     "hardware": m.get("hardware")})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ command
def _read(d: Optional[str], f: str) -> Optional[pd.DataFrame]:
    if not d:
        return None
    p = Path(d) / f
    return pd.read_csv(p) if p.exists() else None


def cmd_report(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    from .mech_runner import begin, finish
    from .prereg_eval import evaluate_all, rows_to_frame
    from .mech_runner import _write_json, base_calibration, exp_cfg_deep
    ctx = begin("report", "prefix_meta_r3", cfg, cfg, args, repo_dir)
    out = ctx.out
    phase_runs = _read(args.phase_dir, "runs.csv")
    mech_runs = _read(args.mech_dir, "runs.csv")
    limits = _read(args.mech_dir, "mech_limits.csv")
    capacity = _read(args.mech_dir, "mech_capacity.csv")
    esc = _read(args.escape_dir, "escape_summary.csv")
    esc_iw = _read(args.escape_inwindow_dir, "escape_summary.csv")
    rob = _read(args.robust_dir, "robust_summary.csv")
    needed = int(exp_cfg_deep(cfg, "robust", False).get("holds_variants_needed", 5))
    cal = base_calibration(cfg, args, repo_dir)
    lam_miss = cal["lambda_miss"]

    rows = evaluate_all(phase_runs=phase_runs, mech_runs=mech_runs, mech_limits=limits, escape_summary=esc,
                        robust_summary=rob, p8_needed=needed, mech_capacity=capacity, escape_inwindow_summary=esc_iw)
    dirs = {"phase": args.phase_dir, "mech": args.mech_dir, "escape": args.escape_dir,
            "escape_inwindow": args.escape_inwindow_dir, "robust": args.robust_dir}
    prov = input_provenance_table(dirs)
    prov.to_csv(out / "table_input_provenance.csv", index=False)
    flags = []
    for r in prov.itertuples():
        if r.quick:
            flags.append(f"{r.input}: quick run")
        if r.git_dirty:
            flags.append(f"{r.input}: produced from a dirty git tree")
    _write_json(out / "prediction_eval.json", {"rows": rows, "inputs": prov.to_dict("records"), "flags": flags})
    rows_to_frame(rows).to_csv(out / "prediction_eval.csv", index=False)

    tables: Dict[str, int] = {}
    if phase_runs is not None:
        t = fig_phase(phase_runs, lam_miss, cal["lambda_cap_lpm_round1"], out / "fig1_phase_diagram.pdf")
        t.to_csv(out / "table_phase_recovery.csv", index=False)
        pt = _read(args.phase_dir, "phase_table.csv")
        if pt is not None:
            pt.to_csv(out / "table_phase_full.csv", index=False)
        tables["phase"] = len(t)
    if mech_runs is not None:
        cold = mech_runs[mech_runs["part"] == "cold"]
        burst = mech_runs[mech_runs["part"] == "burst"]
        wide = fig_mechanisms(cold, burst, limits, capacity, lam_miss, list(exp_cfg_deep(cfg, "mech", False)["policies"]),
                              out / "fig2_mechanisms.pdf")
        lab = cfg.get("labels", {})
        wide.insert(1, "label", [lab.get(p, p) for p in wide["policy"]])
        wide.to_csv(out / "table_mechanisms.csv", index=False)
        for f in ("mech_burst_table.csv", "mech_cold_table.csv", "mech_limits.csv", "mech_capacity.csv",
                  "mech_capacity_by_population.csv", "mech_capsweep_table.csv"):
            t = _read(args.mech_dir, f)
            if t is not None:
                t.to_csv(out / f"table_{f}", index=False)
        tables["mech"] = len(wide)
    if esc is not None or esc_iw is not None:
        t = fig_escape(esc, esc_iw, out / "fig3_escape_vs_k.pdf")
        t.to_csv(out / "table_escape_plotted.csv", index=False)
        for nm, dd in (("registered", args.escape_dir), ("inwindow", args.escape_inwindow_dir)):
            for f, tgt in (("escape_summary.csv", f"table_escape_{nm}_summary.csv"),
                           ("escape_limits.csv", f"table_escape_{nm}_limits.csv"),
                           ("escape_calib.csv", f"table_escape_{nm}_calib.csv")):
                tt = _read(dd, f)
                if tt is not None:
                    tt.drop(columns=[c for c in ("per_seed",) if c in tt.columns]).to_csv(out / tgt, index=False)
        tables["escape"] = len(t)
    if rob is not None:
        t = fig_robust(rob, out / "fig4_robustness.pdf")
        t.to_csv(out / "table_robustness.csv", index=False)
        tables["robust"] = len(t)
    pre = pre_full_run_table(Path(args.out_root), repo_dir)
    pre.to_csv(out / "table_pre_full_runs.csv", index=False)
    finish(ctx, [], {"inputs": prov.to_dict("records"), "flags": flags, "verdicts": {r["id"]: r["verdict"] for r in rows},
                     "tables": tables, "n_pre_full_runs_listed": int(len(pre))})
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(rows_to_frame(rows)[["id", "verdict", "notes"]].to_string())
    print("result dir:", out)
    return out
