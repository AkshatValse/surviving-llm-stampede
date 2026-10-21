"""Offline analysis of a vat_collect run directory.

Usage: python experiments/vat_analyze.py --timings results/vat_collect/<ts> [--config ...] [--S N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vat import analysis as an  # noqa: E402
from vat.provenance import new_run_dir, write_meta  # noqa: E402


def plots(summary: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sty = {"NAIVE": ("o-", "C0"), "BONF-T": ("s-", "C1"), "CS-RACE": ("^", "C3"), "CS-RACE-BEST": ("v", "C2")}
    for fname, xcol, ycol, xl, yl, logx in [
        ("inflation_vs_cost.pdf", "blocks_per_cand", "inflation_pct",
         "benchmark blocks per candidate (mean)", "winner's-curse inflation (% speedup points)", True),
        ("fwer_vs_cost.pdf", "seconds", "fwer",
         "benchmark time consumed (s, baseline+candidate calls)", "family-wise false-improvement rate", True)]:
        fig, ax = plt.subplots(figsize=(5, 3.6))
        for proto, (m, col) in sty.items():
            d = summary[summary.protocol == proto]
            ax.plot(d[xcol], d[ycol], m, color=col, label=proto, ms=5)
        if ycol == "fwer":
            ax.axhline(0.05, color="k", ls=":", lw=0.8)
        if logx:
            ax.set_xscale("log")
        ax.set_xlabel(xl); ax.set_ylabel(yl); ax.legend(fontsize=7); fig.tight_layout()
        fig.savefig(out / fname)
        plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timings", required=True)
    ap.add_argument("--config", default=str(ROOT / "configs/vat_pilot.yaml"))
    ap.add_argument("--S", type=int, default=None)
    ap.add_argument("--name", default="vat_analyze")
    ap.add_argument("--clip-factor", type=float, default=None, help="override cs.clip_factor (supplementary)")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    if a.clip_factor:
        cfg["cs"]["clip_factor"] = a.clip_factor
    if a.S:
        cfg["analysis"]["S"] = cfg["analysis"]["null_test"]["S"] = a.S
    acfg = cfg["analysis"]
    b = float(np.log(cfg["cs"]["clip_factor"]))
    start = dt.datetime.now().isoformat()
    run_dir = new_run_dir(ROOT / cfg["output_root"], a.name)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    df = pd.read_parquet(Path(a.timings) / "timings.parquet")
    s_hold, s_main, s_null = np.random.SeedSequence(cfg["seeds"]["analysis"]).spawn(3)
    holdout = an.choose_holdout(np.sort(df["proc"].unique()), acfg["holdout"],
                                np.random.Generator(np.random.PCG64(s_hold)))
    arr = an.build_arrays(df, b, holdout)
    K = arr["K"]
    theta = arr["theta"]
    thr = np.log1p(acfg["delta"])
    cand_tbl = pd.DataFrame({"cand": arr["cands"], "theta_heldout_pct": an.pct(theta),
                             "theta_train_pct": an.pct(arr["theta_train"]),
                             "real_improvement": theta > thr})
    cand_tbl.to_csv(run_dir / "candidates_truth.csv", index=False)
    print(f"holdout procs {holdout}; K={K}; real improvements: {int((theta > thr).sum())}; "
          f"near-threshold (|theta-thr|<2% pts): {int((np.abs(an.pct(theta) - an.pct(thr)) < 2).sum())}")

    rep = an.run_main(arr, acfg, b, cfg["cs"]["c"], s_main)
    summary = an.summarize(rep, K)
    summary.to_csv(run_dir / "summary.csv", index=False)
    null = an.run_null(arr, acfg, b, cfg["cs"]["c"], s_null)
    null.to_csv(run_dir / "null_stress.csv", index=False)
    an.noise_summary(df, b).to_csv(run_dir / "noise.csv", index=False)
    plots(summary, run_dir)
    write_meta(run_dir, cfg, start, dt.datetime.now().isoformat(),
               {"timings_dir": str(a.timings), "holdout_procs": holdout, "K": K})
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(summary.round(3).to_string())
    print(null.round(3).to_string())
    print("wrote", run_dir)


if __name__ == "__main__":
    main()
