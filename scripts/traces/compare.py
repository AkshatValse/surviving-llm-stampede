"""Exceedance table: how often a tool call outlasts t seconds, and how much of the total tool time those calls carry, for the real
traces against the simulator's current Exp(5 s) (the workload of record).

  python -I scripts/traces/compare.py OUTDIR [--config configs/traces_analysis.yaml]

Reads results/traces_norm/<source>/*.csv (written by parse_tracelab.py / parse_mini_swe.py), writes OUTDIR/exceedance.csv and
OUTDIR/exceedance.md. Series (same definitions as analyze.py / make_configs.py), all capped at analysis.cap_s for the time shares:
  tracelab_round_z   per-turn idle interval (last tool result - last tool request), tool calls except human-interaction tools
  tracelab_gap_next  next request ready minus end of this call's model output (adds overheads and human waits)
  mini_swe_v2_phase  shell command wall time per step in the SWE-bench docker container (60 s timeout)
  exp5               Exp(5 s), analytic
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
import yaml

THRESHOLDS = (0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0)


def exp_row(mean: float, cap: float) -> dict:
    row = {"series": f"exp{mean:g}", "n": 0, "mean_s": mean, "median_s": mean * np.log(2.0)}
    for t in THRESHOLDS:
        row[f"P(>{t:g}s)"] = float(np.exp(-t / mean))
        # share of E[min(X, cap)] carried by X > t, analytic: int_t^cap x f(x) dx + cap * P(X > cap)
        num = (t + mean) * np.exp(-t / mean) - (cap + mean) * np.exp(-cap / mean) + cap * np.exp(-cap / mean)
        den = mean * (1.0 - np.exp(-cap / mean))
        row[f"time_share(>{t:g}s)"] = float(num / den) if t < cap else 0.0
    return row


def series_row(name: str, x: np.ndarray, cap: float) -> dict:
    x = x[np.isfinite(x) & (x >= 0)]
    xc = np.minimum(x, cap)
    row = {"series": name, "n": int(x.size), "mean_s": float(xc.mean()), "median_s": float(np.median(x))}
    for t in THRESHOLDS:
        row[f"P(>{t:g}s)"] = float((x > t).mean())
        row[f"time_share(>{t:g}s)"] = float(xc[xc > t].sum() / xc.sum())
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--config", default="configs/traces_analysis.yaml")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cap = float(cfg["analysis"]["cap_s"])
    tl_norm = cfg["sources"]["tracelab"]["norm_dir"]
    ms_norm = cfg["sources"]["mini_swe_v2"]["norm_dir"]
    r = pd.read_csv(os.path.join(tl_norm, "rounds.csv"), usecols=["n_tools", "classes", "z_round_s", "gap_next_s"])
    r = r[(r.n_tools > 0) & (~r.classes.fillna("").str.contains("human"))]
    ms = pd.read_csv(os.path.join(ms_norm, "calls.csv"), usecols=["wall_s"])["wall_s"].dropna().to_numpy()
    rows = [exp_row(float(cfg["analysis"]["exp_ref_mean_s"]), cap),
            series_row("tracelab_round_z", r["z_round_s"].dropna().to_numpy(), cap),
            series_row("tracelab_gap_next", r["gap_next_s"].dropna().to_numpy(), cap),
            series_row("mini_swe_v2_phase", ms, cap)]
    df = pd.DataFrame(rows)
    os.makedirs(a.out, exist_ok=True)
    df.to_csv(os.path.join(a.out, "exceedance.csv"), index=False, float_format="%.5g")
    lines = ["| series | n | mean (s, capped) | median | " + " | ".join(f"P(>{t:g}s)" for t in THRESHOLDS) + " |",
             "|---|---|---|---|" + "---|" * len(THRESHOLDS)]
    for _, x in df.iterrows():
        lines.append(f"| {x['series']} | {int(x['n']):,} | {x['mean_s']:.3g} | {x['median_s']:.3g} | " + " | ".join(f"{100 * x[f'P(>{t:g}s)']:.2f}%" for t in THRESHOLDS) + " |")
    lines += ["", "Share of the total (capped) tool time carried by the calls longer than t:", "",
              "| series | " + " | ".join(f">{t:g}s" for t in THRESHOLDS) + " |", "|---|" + "---|" * len(THRESHOLDS)]
    for _, x in df.iterrows():
        lines.append(f"| {x['series']} | " + " | ".join(f"{100 * x[f'time_share(>{t:g}s)']:.1f}%" for t in THRESHOLDS) + " |")
    with open(os.path.join(a.out, "exceedance.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
