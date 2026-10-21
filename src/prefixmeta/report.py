"""Consolidated report for the prefix-cache metastability pilot: ``results/prefix_meta/<ts>/`` with
``summary.csv`` (long format: experiment, variant, policy, lam_mult, setting, metric, value), the decision
(``decision.json``), and two vector PDFs (E1/E2 hit rate + queue vs time by policy; E3 throughput + hit rate vs
lambda on the up / down legs). Reads the per-experiment result dirs; never modifies them.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .runner import (_json_default, evaluate_decision, new_result_dir, sanitize, save_configs,  # noqa: E402
                     write_meta)

POLICY_COLORS = {"fcfs": "#d62728", "lpm": "#1f77b4", "lpm128": "#9467bd", "aging10": "#2ca02c", "aging30": "#8c564b",
                 "fcfs_cap": "#ff7f0e", "fcfs_cap_lb": "#17becf"}
POLICY_LABELS = {"fcfs": "FCFS", "lpm": "LPM", "lpm128": "LPM-128", "aging10": "AGING-LPM(10 s)",
                 "aging30": "AGING-LPM(30 s)", "fcfs_cap": "FCFS-CAP(N*=45, spec)", "fcfs_cap_lb": "FCFS-CAP(N*=28, len.-biased)"}


def latest_dir(root: Path, name: str, marker: str) -> Path:
    c = sorted((root / name).glob(f"*/{marker}"))
    if not c:
        raise FileNotFoundError(f"no {name} result under {root}")
    return c[-1].parent


def melt_table(df: pd.DataFrame, experiment: str, id_cols: Dict[str, str], metrics: Sequence[str]) -> pd.DataFrame:
    """Wide -> long. ``id_cols`` maps output column (variant/policy/lam_mult/setting) -> source column name or
    a constant (prefixed with '=')."""
    rows = []
    for _, r in df.iterrows():
        ident = {"experiment": experiment}
        for k in ("variant", "policy", "lam_mult", "setting"):
            src = id_cols.get(k, "=")
            if src.startswith("="):
                ident[k] = src[1:] if (src[1:] or k != "lam_mult") else np.nan
            else:
                ident[k] = r[src]
        for m in metrics:
            if m in df.columns:
                v = r[m]
                rows.append({**ident, "metric": m, "value": float(v) if pd.notna(v) else np.nan})
    return pd.DataFrame(rows)


def build_summary(e0: Dict[str, Any], e1d: Path, e2d: Path, e3d: Path, e4d: Path, sens: Sequence[Path],
                  dec: Dict[str, Any]) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []

    def e0_rows(summary: Dict[str, Any], variant: str) -> pd.DataFrame:
        rows = []
        for k in ("lambda_miss", "lambda_cap", "R", "session_cap_N_star", "session_cap_N_star_length_biased",
                  "length_biased_mean_context_tokens"):
            if k in summary and summary[k] is not None:
                rows.append({"experiment": "e0", "variant": variant, "policy": "", "lam_mult": np.nan, "setting": "",
                             "metric": k, "value": float(summary[k])})
        for h in summary.get("cap_hazard", []):
            for k in ("n_runs", "n_escaped", "frac_escaped", "frac_escaped_ci95_lo", "frac_escaped_ci95_hi",
                      "escape_time_median_s"):
                v = h.get(k)
                rows.append({"experiment": "e0_hazard", "variant": variant, "policy": h["policy"], "lam_mult": h["lam_mult"],
                             "setting": f"horizon={int(h['horizon_s'])}s,escape>{h['escape_queue_above']}",
                             "metric": k, "value": np.nan if v is None else float(v)})
        return pd.DataFrame(rows)

    parts.append(e0_rows(e0, "primary"))
    for sd in sens:
        s = json.loads((sd / "e0_summary.json").read_text())
        ov = ",".join(s.get("overrides", [])) or sd.name
        parts.append(e0_rows(s, ov))

    t1 = pd.read_csv(e1d / "e1_recovery_table.csv")
    t1["setting"] = "cold_start=300"
    parts.append(melt_table(t1, "e1", {"variant": "variant", "policy": "policy", "lam_mult": "lam_mult", "setting": "setting"},
                            ["n_runs", "n_recovered", "n_recovered_incl_gate", "tail_hit_mean", "tail_queue_mean",
                             "tail_gate_mean", "tail_busy_mean"]))
    if (e1d / "e1_basin_table.csv").exists():
        bt = pd.read_csv(e1d / "e1_basin_table.csv")
        bt["setting"] = "cold=" + bt["cold_sessions"].astype(str)
        bt["variant"] = "cold_sweep"
        parts.append(melt_table(bt, "e1_basin", {"variant": "variant", "policy": "policy", "lam_mult": "lam_mult",
                                                 "setting": "setting"},
                                ["n_runs", "n_recovered", "tail_hit_mean", "tail_queue_mean", "basin_size"]))
    if (e1d / "e1_lpm128_vs_fcfs_identity.csv").exists():
        idn = pd.read_csv(e1d / "e1_lpm128_vs_fcfs_identity.csv")
        g = idn.groupby(["variant", "lam_mult"]).agg(n_pairs=("identical", "size"), n_identical=("identical", "sum")).reset_index()
        g["setting"] = "lpm128_bit_identical_to_fcfs"
        g["policy"] = "lpm128"
        parts.append(melt_table(g, "e1_identity", {"variant": "variant", "policy": "policy", "lam_mult": "lam_mult",
                                                   "setting": "setting"}, ["n_pairs", "n_identical"]))

    t2 = pd.read_csv(e2d / "e2_summary.csv")
    t2["setting"] = "burst=" + t2["burst_sessions"].astype(str)
    parts.append(melt_table(t2, "e2", {"variant": "variant", "policy": "policy", "setting": "setting"},
                            ["n_runs", "n_trapped", "n_hit_returned", "n_queue_returned", "n_recovered", "hit_eval_mean",
                             "hit_eval_min", "hit_eval_max", "tail_queue_mean"]))
    if (e2d / "e2_lpm128_vs_fcfs_identity.csv").exists():
        idn = pd.read_csv(e2d / "e2_lpm128_vs_fcfs_identity.csv")
        g = idn.groupby(["variant", "burst_sessions"]).agg(n_pairs=("identical", "size"), n_identical=("identical", "sum")).reset_index()
        g["setting"] = "burst=" + g["burst_sessions"].astype(str)
        g["policy"] = "lpm128"
        parts.append(melt_table(g, "e2_identity", {"variant": "variant", "policy": "policy", "setting": "setting"},
                                ["n_pairs", "n_identical"]))

    t3 = pd.read_csv(e3d / "e3_hysteresis.csv")
    t3["setting"] = "peak=" + t3["hi_mult_of_lambda_miss"].round(3).astype(str) + "x lambda_miss"
    parts.append(melt_table(t3, "e3", {"variant": "variant", "policy": "policy", "setting": "setting"},
                            ["hi_mult_of_lambda_miss", "n_seeds", "hysteresis_area_mean", "n_escaped", "n_reentered",
                             "escape_lambda_mult_mean", "reentry_lambda_mult_mean", "hit_up_mean", "hit_down_mean",
                             "turns_per_s_up_mean", "turns_per_s_down_mean", "max_queue_mean"]))

    t4 = pd.read_csv(e4d / "e4_summary.csv")
    t4["variant"] = "base"
    parts.append(melt_table(t4, "e4", {"variant": "variant", "policy": "policy", "lam_mult": "lam_mult",
                                       "setting": "=escape>128"},
                            [c for c in t4.columns if c not in ("policy", "lam_mult", "setting", "variant")]))

    drows = []
    for name, item in dec["items"].items():
        drows.append({"experiment": "decision", "variant": "", "policy": "", "lam_mult": np.nan, "setting": name,
                      "metric": "pass", "value": float(bool(item["pass"]))})
    for name, v in dec["kill_conditions"].items():
        drows.append({"experiment": "decision", "variant": "", "policy": "", "lam_mult": np.nan, "setting": "kill:" + name,
                      "metric": "holds", "value": float(bool(v))})
    parts.append(pd.DataFrame(drows))
    out = pd.concat([p for p in parts if len(p)], ignore_index=True)
    return out[["experiment", "variant", "policy", "lam_mult", "setting", "metric", "value"]]


# ----------------------------------------------------------------------------- figures
def _band(ax: Any, df: pd.DataFrame, x: str, y: str, color: str, label: str, xoff: float = 0.0, scale: float = 1.0) -> None:
    g = df.groupby(x)[y]
    m, lo, hi = g.mean(), g.min(), g.max()
    xs = (m.index.to_numpy() - xoff) / scale
    ax.plot(xs, m.to_numpy(), color=color, label=label, lw=1.4)
    ax.fill_between(xs, lo.to_numpy(), hi.to_numpy(), color=color, alpha=0.12, lw=0)


def fig_e1_e2(e1d: Path, e2d: Path, out: Path, mults: Optional[Sequence[float]] = None) -> None:
    w1 = pd.read_csv(e1d / "windows.csv")
    w1 = w1[w1["variant"] == "base"]
    w2 = pd.read_csv(e2d / "windows.csv")
    w2 = w2[w2["variant"] == "base"]
    r2 = pd.read_csv(e2d / "runs.csv")
    tb = float(r2["t_burst"].iloc[0])
    mults = sorted(w1["lam_mult"].unique()) if mults is None else list(mults)
    ncol = len(mults) + 1
    fig, axes = plt.subplots(2, ncol, figsize=(3.6 * ncol, 6.2), squeeze=False, sharey="row")
    pols = [p for p in POLICY_COLORS if p in set(w1["policy"])]
    for j, m in enumerate(mults):
        sub = w1[np.isclose(w1["lam_mult"], m)]
        for p in pols:
            d = sub[sub["policy"] == p]
            if len(d):
                _band(axes[0, j], d, "t_start", "hit_rate", POLICY_COLORS[p], POLICY_LABELS[p], scale=1000.0)
                _band(axes[1, j], d, "t_start", "queue_mean", POLICY_COLORS[p], POLICY_LABELS[p], scale=1000.0)
        axes[0, j].set_title(f"E1: {m:g}$\\times\\lambda_{{miss}}$, 300 cold sessions at t=0")
        axes[1, j].set_xlabel("simulated time (ks)")
    j = ncol - 1
    for p in pols:
        d = w2[w2["policy"] == p]
        if len(d):
            _band(axes[0, j], d, "t_start", "hit_rate", POLICY_COLORS[p], POLICY_LABELS[p], xoff=tb, scale=1000.0)
            _band(axes[1, j], d, "t_start", "queue_mean", POLICY_COLORS[p], POLICY_LABELS[p], xoff=tb, scale=1000.0)
    axes[0, j].set_title(f"E2: burst of {int(r2['burst_sessions'].iloc[0])} at 2$\\times\\lambda_{{miss}}$")
    axes[1, j].set_xlabel("time since burst start (ks)")
    for j in range(ncol):
        axes[0, j].set_ylim(-0.03, 1.03)
        axes[0, j].axhline(0.8, color="k", lw=0.5, ls=":")
        axes[1, j].set_yscale("symlog", linthresh=10)
        axes[1, j].axhline(20, color="k", lw=0.5, ls=":")
    axes[0, 0].set_ylabel("prefix hit rate")
    axes[1, 0].set_ylabel("waiting queue (1000 s mean)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), fontsize=7, frameon=False)
    fig.suptitle("E1 / E2: hit rate and waiting queue vs time by policy (line = mean over seeds, band = min..max; "
                 "when trapped, FCFS, LPM-128 and AGING-LPM coincide; FCFS-CAP queue excludes its outer-gate backlog)", fontsize=8.5)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    fig.savefig(out, format="pdf")
    plt.close(fig)


def fig_e3(e3d: Path, lam_miss: float, lam_cap: float, out: Path) -> None:
    w = pd.read_csv(e3d / "windows.csv")
    r3 = pd.read_csv(e3d / "runs.csv")
    peak = r3.groupby("variant")["hi_mult_of_lambda_miss"].first().to_dict()
    variants = list(dict.fromkeys(w["variant"]))
    fig, axes = plt.subplots(len(variants), 2, figsize=(10.5, 3.6 * len(variants)), squeeze=False)
    pols = [p for p in POLICY_COLORS if p in set(w["policy"])]
    for i, v in enumerate(variants):
        sub = w[w["variant"] == v]
        for k, (col, lab) in enumerate([("turns_per_s", "completed turns / s"), ("hit_rate", "prefix hit rate")]):
            ax = axes[i, k]
            for p in pols:
                for leg, ls in (("up", "-"), ("down", "--")):
                    d = sub[(sub["policy"] == p) & (sub["leg"] == leg)].dropna(subset=[col])
                    if not len(d):
                        continue
                    g = d.groupby("window").agg(x=("lam_window", "mean"), y=(col, "mean")).sort_values("x")
                    ax.plot(g["x"] / lam_miss, g["y"], color=POLICY_COLORS[p], ls=ls, lw=1.3,
                            label=f"{POLICY_LABELS[p]} ({leg})")
            ax.axvline(lam_cap / lam_miss, color="k", lw=0.6, ls=":")
            if col == "hit_rate":
                ax.set_ylim(-0.03, 1.03)
            ax.set_xlabel(r"arrival rate $\lambda / \lambda_{miss}$ (window midpoint)")
            ax.set_ylabel(lab)
            pk = peak[v]
            ax.set_title(f"E3 ramp '{v}' (peak {pk:.2f}$\\times\\lambda_{{miss}}$; dotted = $\\lambda_{{cap}}$)", fontsize=9)
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], color=POLICY_COLORS[p], lw=1.6) for p in pols]
    labels = [POLICY_LABELS[p] for p in pols]
    handles += [Line2D([0], [0], color="k", ls="-", lw=1.2), Line2D([0], [0], color="k", ls="--", lw=1.2)]
    labels += ["up leg", "down leg"]
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7, frameon=False)
    fig.suptitle("E3: triangle ramp, mean over seeds (non-escaping seeds included in the mean); identical lines overlap",
                 fontsize=9)
    fig.tight_layout(rect=[0, 0.08, 1, 0.96])
    fig.savefig(out, format="pdf")
    plt.close(fig)


# ----------------------------------------------------------------------------- command
def cmd_report(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any]) -> Path:
    t_start = time.time()
    root = Path(args.out_root)
    sfx = "_quick" if args.quick else ""
    e1d = Path(args.e1_dir) if args.e1_dir else latest_dir(root, "prefix_meta_e1" + sfx, "runs.csv")
    e2d = Path(args.e2_dir) if args.e2_dir else latest_dir(root, "prefix_meta_e2" + sfx, "runs.csv")
    e3d = Path(args.e3_dir) if args.e3_dir else latest_dir(root, "prefix_meta_e3" + sfx, "runs.csv")
    e4d = Path(args.e4_dir) if args.e4_dir else latest_dir(root, "prefix_meta_e4" + sfx, "runs.csv")
    sens = [Path(s) for s in (args.sens_dir or [])]
    e1 = pd.read_csv(e1d / "runs.csv")
    e2 = pd.read_csv(e2d / "runs.csv")
    dec = evaluate_decision(cfg, calib, e1, e2)
    out = new_result_dir(args.out_root, "prefix_meta" + sfx)
    summary = build_summary(calib, e1d, e2d, e3d, e4d, sens, dec)
    summary.to_csv(out / "summary.csv", index=False)
    inputs = {"e0": calib.get("_path"), "e1": str(e1d), "e2": str(e2d), "e3": str(e3d), "e4": str(e4d),
              "e0_sensitivity": [str(s) for s in sens]}
    dec["inputs"] = inputs
    (out / "decision.json").write_text(json.dumps(sanitize(dec), indent=2))
    fig_e1_e2(e1d, e2d, out / "fig_e1_e2_hit_queue_vs_time.pdf")
    fig_e3(e3d, calib["lambda_miss"], calib["lambda_cap"], out / "fig_e3_throughput_hit_vs_lambda.pdf")
    save_configs(out, args.config, cfg)
    write_meta(out, experiment="report", argv=sys.argv, seeds=[], t_start=t_start, t_end=time.time(), repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "inputs": inputs, "calibration": {k: calib.get(k) for k in
                      ("lambda_miss", "lambda_cap", "R", "session_cap_N_star", "session_cap_N_star_length_biased")}})
    print(json.dumps(sanitize(dec), indent=2))
    print("result dir:", out)
    return out
