#!/usr/bin/env python
"""Summary tables of the baselines source audit (notes/BASELINES_AUDIT.md): old behaviour vs each audited switch, same seeds.

Reads the result directories written by experiments/prefix_meta_probe_run.py (curve, burst) and experiments/prefix_meta_mech_run.py
(phase) under ``--results`` (tags ``baselines_audit*``; the newest timestamp of each tag) and writes, into a fresh
``--out/<YYYYmmdd-HHMMSS>/``: tables.md, curve_<tag>.csv, paired_<tag>.csv, burst_summary.csv, cold_summary.csv, meta.json.

Units: closed-population service rate mu(300) in units of lambda_miss (all-miss capacity of the base workload, the value in the
calibration subset file). 95% intervals are two-sided Student-t over seeds (the seeds are the only randomness; lambda_miss is a
fixed constant, its own calibration error, se 1.5% of its value, is not propagated). Paired differences use the same seed on both
sides (common random numbers: the workload stream of a seed is shared by every policy).

    python analysis/baselines_audit_tables.py [--results results] [--out results/prefix_meta_baselines_audit_summary]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parent.parent

# audited row -> the row it is paired with (the old behaviour, or the previous step of the audit)
PAIRS = [
    ("peek_order_audit", "peek_rank"), ("peek_score_audit", "peek_rank"), ("peek_singleton_audit", "peek_rank"),
    ("peek_singleton_audit", "lpm"),
    ("ttl5cw", "ttl5"), ("ttl5cwr", "ttl5cw"), ("ttl5cwr", "ttl5"),
    ("ttl10cw", "ttl10"), ("ttl10cwr", "ttl10cw"), ("ttl10cwr", "ttl10"),
    ("ttl20cw", "ttl20"), ("ttl20cwr", "ttl20cw"), ("ttl20cwr", "ttl20"),
    ("concur_lpm", "concur_cap"), ("concur_i5", "concur_cap"), ("concur_i20", "concur_cap"),
    ("concur_s8", "concur_cap"), ("concur_s56", "concur_cap"),
]
GROUPS = [
    ("PEEK", ["fcfs", "peek_rank", "peek", "peek_order_audit", "peek_score_audit", "peek_singleton_audit", "lpm"]),
    ("Continuum pins", ["ttl5", "ttl5cw", "ttl5cwr", "ttl10", "ttl10e", "ttl10ef", "ttl10cw", "ttl10cwr",
                        "ttl20", "ttl20e", "ttl20ef", "ttl20cw", "ttl20cwr"]),
    ("CONCUR", ["concur_cap", "concur_lpm", "concur_i5", "concur_i20", "concur_s8", "concur_s56"]),
]


def newest(results: Path, name: str) -> Optional[Path]:
    base = results / name
    if not base.is_dir():
        return None
    runs = sorted(p for p in base.iterdir() if p.is_dir() and (p / "meta.json").exists())
    return runs[-1] if runs else None


def tci(x: np.ndarray, level: float = 0.95) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    return float(stats.t.ppf(0.5 + level / 2, n - 1) * np.std(x, ddof=1) / math.sqrt(n))


def curve_tables(d: Path, lam_miss: float) -> Dict[str, pd.DataFrame]:
    runs = pd.read_csv(d / "curve_runs.csv")
    runs["x"] = runs["mu"] / lam_miss
    rows = []
    for pol, g in runs.groupby("policy", sort=False):
        x = g.sort_values("seed")["x"].to_numpy()
        rows.append({"policy": pol, "n_seeds": len(x), "mean_x": x.mean(), "sd_x": np.std(x, ddof=1) if len(x) > 1 else float("nan"),
                     "ci95_half": tci(x), "min_x": x.min(), "max_x": x.max(), "hit_rate": g["hit_rate"].mean(),
                     "gpu_busy": g["gpu_busy"].mean(), "per_seed_x": json.dumps([round(float(v), 4) for v in x])})
    tab = pd.DataFrame(rows)
    wide = runs.pivot(index="seed", columns="policy", values="x")
    prow = []
    for a, b in PAIRS:
        if a in wide and b in wide:
            dlt = (wide[a] - wide[b]).to_numpy()
            prow.append({"audited": a, "reference": b, "n_seeds": len(dlt), "mean_diff_x": dlt.mean(),
                         "ci95_half": tci(dlt), "rel_diff_pct": 100 * dlt.mean() / wide[b].mean(),
                         "n_seeds_positive": int((dlt > 0).sum()), "n_seeds_zero": int((dlt == 0).sum())})
    return {"curve": tab, "paired": pd.DataFrame(prow)}


def fmt(v: float, nd: int = 3) -> str:
    return "nan" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{nd}f}"


def md_curve(tab: pd.DataFrame, paired: pd.DataFrame, title: str) -> str:
    t = tab.set_index("policy")
    out = [f"### {title}", "", "mu(300) / lambda_miss, mean +- 95% t half-width over seeds (sd in brackets); hit = mean steady-state hit rate.", "",
           "| group | policy | seeds | mu/lambda_miss | sd | min..max | hit rate | GPU busy |", "|---|---|---|---|---|---|---|---|"]
    for gname, pols in GROUPS:
        for p in pols:
            if p in t.index:
                r = t.loc[p]
                out.append(f"| {gname} | {p} | {int(r.n_seeds)} | {fmt(r.mean_x)} +- {fmt(r.ci95_half)} | {fmt(r.sd_x)} | "
                           f"{fmt(r.min_x, 2)}..{fmt(r.max_x, 2)} | {fmt(r.hit_rate)} | {fmt(r.gpu_busy)} |")
    out += ["", "Paired differences (same seeds), audited minus reference, in units of lambda_miss:", "",
            "| audited | reference | mean diff +- 95% half-width | relative to reference | seeds > 0 / = 0 / n |", "|---|---|---|---|---|"]
    for _, r in paired.iterrows():
        out.append(f"| {r.audited} | {r.reference} | {r.mean_diff_x:+.3f} +- {fmt(r.ci95_half)} | {r.rel_diff_pct:+.1f}% | "
                   f"{int(r.n_seeds_positive)} / {int(r.n_seeds_zero)} / {int(r.n_seeds)} |")
    return "\n".join(out) + "\n"


def burst_summary(results: Path, policies: List[str]) -> pd.DataFrame:
    rows = []
    for p in policies:
        d = newest(results, f"prefix_meta_probe_burst_baselines_audit_{p}")
        if d is None:
            continue
        runs = pd.read_csv(d / "runs.csv")
        r = {"policy": p, "dir": d.relative_to(results).as_posix(), "n_runs": len(runs)}
        for c in ("trapped", "recovered", "recovered_queue_only"):
            if c in runs:
                r["n_" + c] = int(runs[c].astype(bool).sum())
        for c in ("tail_hit_rate", "tail_backlog_mean", "tail_sessions_per_s"):
            if c in runs:
                r[c if c.endswith("_mean") else c + "_mean"] = float(runs[c].mean())
        rows.append(r)
    return pd.DataFrame(rows)


def cold_summary(d: Path, lam_miss: float) -> pd.DataFrame:
    t = pd.read_csv(d / "phase_table.csv")
    return t


def md_cold(t: pd.DataFrame, title: str) -> str:
    mults = sorted(t["lam_mult"].unique())
    pivot = t.pivot(index="policy", columns="lam_mult", values="n_recovered")
    nruns = int(t["n_runs"].max())
    hz = sorted(set(int(h) for h in t["horizon_used_s"]))
    out = [f"### {title} (300 cold sessions, open arrivals at m x lambda_miss, horizon {'/'.join(str(h) for h in hz)} s): recovered runs / {nruns}", "",
           "| group | policy | " + " | ".join(f"{m:g}x" for m in mults) + " | highest m with all recovered |", "|---|---|" + "---|" * (len(mults) + 1)]
    for gname, pols in GROUPS:
        for p in pols:
            if p in pivot.index:
                cnt = [int(pivot.loc[p, m]) for m in mults]
                hi = "none in range" if cnt[0] != nruns else "none"
                for m, c in zip(mults, cnt):
                    if c == nruns:
                        hi = f"{m:g}x"
                    else:
                        break
                out.append(f"| {gname} | {p} | " + " | ".join(f"{c}" for c in cnt) + f" | {hi} |")
    return "\n".join(out) + "\n"


def md_burst(b: pd.DataFrame) -> str:
    out = ["### Burst (200 extra sessions in 60 s at t = 5000 s, open arrivals at 2 x lambda_miss, horizon 30000 s, seeds 0-4)", "",
           "| group | policy | trapped | recovered | tail hit rate | tail backlog |", "|---|---|---|---|---|---|"]
    t = b.set_index("policy")
    for gname, pols in GROUPS:
        for p in pols:
            if p in t.index:
                r = t.loc[p]
                out.append(f"| {gname} | {p} | {int(r.n_trapped)} / {int(r.n_runs)} | {int(r.n_recovered)} / {int(r.n_runs)} | "
                           f"{fmt(r.tail_hit_rate_mean)} | {fmt(r.tail_backlog_mean, 1)} |")
    return "\n".join(out) + "\n"


def git_state() -> Dict[str, object]:
    def run(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="results/prefix_meta_baselines_audit_summary")
    ap.add_argument("--calib", default="results/prefix_meta_baselines_audit_calibration/e0_summary.json")
    args = ap.parse_args(argv)
    results = Path(args.results)
    lam_miss = float(json.loads(Path(args.calib).read_text())["lambda_miss"])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) / stamp
    out.mkdir(parents=True, exist_ok=False)
    md: List[str] = ["# Baselines audit: measured tables", "", f"lambda_miss = {lam_miss!r} sessions/s. Generated {stamp}.", ""]
    srcs: Dict[str, str] = {}
    for tag, title in (("baselines_audit", "Closed-population service rate, seeds 0-2 (the round-3 seeds)"),
                       ("baselines_audit_s10", "Closed-population service rate, seeds 0-9"),
                       ("baselines_audit_deadkv", "Closed-population service rate, seeds 0-2, finished sessions keep their KV (engine.free_kv_on_session_end=false)")):
        d = newest(results, f"prefix_meta_probe_curve_{tag}")
        if d is None:
            continue
        srcs[f"curve_{tag}"] = d.as_posix()
        tabs = curve_tables(d, lam_miss)
        tabs["curve"].to_csv(out / f"curve_{tag}.csv", index=False)
        tabs["paired"].to_csv(out / f"paired_{tag}.csv", index=False)
        md.append(md_curve(tabs["curve"], tabs["paired"], title))
    pols = [p for _, ps in GROUPS for p in ps]
    for tag, fname, title in (("cold", "cold_summary.csv", "Cold-start recovery"),
                              ("cold_hi", "cold_hi_summary.csv", "Cold-start recovery, higher multiples for the rows that still recovered at 3.5x"),
                              ("cold_long", "cold_long_summary.csv", "Cold-start recovery near lambda_miss at the registered long horizon")):
        d = newest(results, f"prefix_meta_phase_baselines_audit_{tag}")
        if d is not None:
            srcs[tag] = d.as_posix()
            t = cold_summary(d, lam_miss)
            t.to_csv(out / fname, index=False)
            md.append(md_cold(t, title))
    b = burst_summary(results, pols)
    if len(b):
        b.to_csv(out / "burst_summary.csv", index=False)
        srcs["burst"] = "prefix_meta_probe_burst_baselines_audit_<policy> (newest timestamp each): " + ", ".join(b["dir"])
        md.append(md_burst(b))
    (out / "tables.md").write_text("\n".join(md))
    (out / "meta.json").write_text(json.dumps({"script": "analysis/baselines_audit_tables.py", "argv": sys.argv, "git": git_state(),
                                               "lambda_miss": lam_miss, "inputs": srcs}, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
