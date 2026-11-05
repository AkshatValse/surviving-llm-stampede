r"""Score new runs against the frozen predictions of tag icml-trap-pred (configs/icml_trap_predict.yaml, rules S1-S5).

    PYTHONPATH="src;." python -m analysis.theory.icml.score_new --cell a100_300k --trigger-s 1200 \
        --run-dirs <run dir> [<run dir> ...] [--window 5700 8700] [--mult 1.35] [--yaml configs/icml_trap_predict.yaml]

A run is scored only if it is stuck (follow-up hit < 0.2 over the window) and the window starts >= 3000 s after
--trigger-s. Each run's nominal multiple of the cell's lambda_ref is read from its meta.json (arrivals.rate_mult) unless
--mult is given. Predictions are linearly interpolated in the multiple from the frozen `asymptotic` table.

S5 (per seed) applies only to runs whose client plan is a constant-rate plan with a recorded seed; it uses the plan's
realized base-arrival rate in the window. It assumes `run.duration_s` (default 8700) matches the run.

Writes JSON and a markdown table next to --out (default: results/theory/icml/score_new/<timestamp>/).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Dict, List

import numpy as np
import yaml

from ..merged.spec import ROOT
from . import measured as ms
from .freeze_predictions import plan_window_rate


def _interp(rows: List[Dict[str, float]], mult: float, key: str) -> float:
    xs = np.array([r["mult"] for r in rows], float)
    ys = np.array([r[key] for r in rows], float)
    if mult < xs.min() or mult > xs.max():
        raise ValueError(f"multiple {mult} outside the frozen table [{xs.min()}, {xs.max()}]")
    return float(np.interp(mult, xs, ys))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    ap.add_argument("--run-dirs", nargs="+", required=True)
    ap.add_argument("--trigger-s", type=float, required=True, help="time the trigger began (burst, slowdown, ...)")
    ap.add_argument("--window", nargs=2, type=float, default=None, help="evaluation window [t0, t1) in s")
    ap.add_argument("--mult", type=float, default=None)
    ap.add_argument("--duration-s", type=float, default=8700.0)
    ap.add_argument("--yaml", default=os.path.join(ROOT, "configs", "icml_trap_predict.yaml"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    Y = yaml.safe_load(open(args.yaml))
    C = Y["cells"][args.cell]
    lam_ref = float(C["lambda_ref"])
    t0, t1 = (args.window or [args.trigger_s + 4500.0, args.duration_s])
    out_runs = []
    for rd in args.run_dirs:
        info = ms.run_info(rd)
        mult = args.mult if args.mult is not None else float(info["rate_mult"])
        st = ms.window_stats(rd, t0, t1, t_burst=args.trigger_s)
        row = dict(run=rd, seed=info["seed"], label=info["label"], mult=mult, **st)
        row["eligible"] = bool(st["fu_hit"] < 0.2 and t0 - args.trigger_s >= 3000.0)
        if row["eligible"]:
            lam = mult * lam_ref
            P = _interp(C["asymptotic"], mult, "P_served_mean")
            D = _interp(C["asymptotic"], mult, "D_over_lam_ref") * lam_ref
            alpha = _interp(C["asymptotic"], mult, "alpha")
            gamma = _interp(C["asymptotic"], mult, "gamma")
            # gap_med_slope is regressed on the turn's completion time; a turn completing at t joined at ~t/z, so the
            # model value of that trend is gamma/z = 1 - 1/z (not registered; S2 below stays as registered, against gamma)
            gamma_z = gamma / _interp(C["asymptotic"], mult, "z")
            thr = 0.5 * (lam - lam_ref)
            row.update(pred_P=P, pred_D=D, pred_alpha=alpha, pred_gamma=gamma, pred_gamma_over_z=gamma_z, threshold=thr,
                       S1_run=bool(abs(st["P_served_mean"] / P - 1.0) <= 0.08),
                       S3_run=(bool(st["completion_rate"] > lam_ref) if st["arrival_rate_window"] >= 1.1 * lam_ref else None))
            if info["seed"] is not None:
                lw = plan_window_rate(int(info["seed"]), lam, t0, t1, args.duration_s)
                plug = lw - D
                row.update(lam_window_plan=lw, plugin=plug,
                           S5_side=bool((plug > thr) == (st["backlog_slope"] > thr)),
                           S5_close=bool(abs(st["backlog_slope"] - plug) <= 0.01))
        out_runs.append(row)
    el = [r for r in out_runs if r["eligible"]]
    pooled = {}
    if el:
        P = el[0]["pred_P"]
        pooled = dict(
            n=len(el),
            S1_pooled=bool(abs(np.mean([r["P_served_mean"] for r in el]) / P - 1.0) <= 0.05),
            S2_pooled=bool(0.6 <= np.mean([r["gap_med_slope"] for r in el]) / el[0]["pred_gamma"] <= 1.4),
            S2_gamma_over_z_pooled_NOT_REGISTERED=bool(
                0.6 <= np.mean([r["gap_med_slope"] for r in el]) / el[0]["pred_gamma_over_z"] <= 1.4),
            S3_pooled=bool(abs(np.mean([r["completion_rate"] for r in el]) / el[0]["pred_D"] - 1.0) <= 0.15),
            S4_pooled=bool(abs(np.mean([r["backlog_slope"] for r in el]) / el[0]["pred_alpha"] - 1.0) <= 0.35),
        )
        pooled["refuted"] = bool(len(el) >= 2 and (not pooled["S1_pooled"] or not pooled["S2_pooled"]))
    out = dict(tag="icml-trap-pred", cell=args.cell, window=[t0, t1], trigger_s=args.trigger_s, runs=out_runs, pooled=pooled,
               scored_at=dt.datetime.now().isoformat(timespec="seconds"))
    od = args.out or os.path.join(ROOT, "results", "theory", "icml", "score_new", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, "score.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    lines = ["| run | seed | eligible | P meas/pred | gap slope / gamma | gap slope / (gamma/z), not registered | completions / D "
             "| slope / alpha | S5 side | S5 close |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in out_runs:
        if not r["eligible"]:
            lines.append(f"| {os.path.basename(r['run'])} | {r['seed']} | no (hit {r['fu_hit']:.2f}) | | | | | | | |")
            continue
        lines.append("| {} | {} | yes | {:.0f}/{:.0f} | {:.4f}/{:.4f} | {:.4f}/{:.4f} | {:.4f}/{:.4f} | {:.4f}/{:.4f} | {} | {} |".format(
            os.path.basename(r["run"]), r["seed"], r["P_served_mean"], r["pred_P"], r["gap_med_slope"], r["pred_gamma"],
            r["gap_med_slope"], r["pred_gamma_over_z"], r["completion_rate"], r["pred_D"], r["backlog_slope"], r["pred_alpha"],
            r.get("S5_side"), r.get("S5_close")))
    lines.append("")
    lines.append(f"pooled: {json.dumps(pooled)}")
    with open(os.path.join(od, "score.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
