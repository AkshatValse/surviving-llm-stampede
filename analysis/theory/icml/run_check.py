r"""Theorem 1/2 against every committed trapped FCFS run (retrospective; nothing fitted to any trap measurement).

    PYTHONPATH="src;." python -m analysis.theory.icml.run_check [--reps 200] [--out results/theory/icml]

Writes trap_check.json (per run and per group), trap_check.md (tables) and universality.csv.
Inputs: the frozen cell specs (analysis/theory/cells/*.yaml; the Llama cell with its speed fitted to its own E0a token rate,
as in pred2's registration-conditional "fit" variant) and the run directories under results/nova/ (all pulled by 2026-11-01).
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from typing import Dict, List

import numpy as np

from ..merged.spec import ROOT, build, load_spec
from ..fluid_rigorous.model import summarize_curve, open_equilibria
from . import measured as ms
from .trap_renewal import (fifo_fluid, stochastic_fifo, trap_asymptotics, trap_costs, window_stats as fluid_window)

CELL_OF_LABEL = {
    "sglang-fcfs-r1": "a100_300k", "sglang-fcfs-r0": "a100_300k", "sglang-fcfs-r1-b100": "a100_300k",
    "sglang-fcfs-r1-b50": "a100_300k", "sglang-fcfs-r1-b60": "a100_300k", "sglang-fcfs-r1-shed-t600": "a100_300k",
    "sglang-fcfs-r1-toolslow-d30": "a100_300k", "sglang-lpm-r1": "a100_300k", "sglang-lpm-r0": "a100_300k",
    "sglang-fcfs-r1-native": "a100_native", "vllm-fcfs": "vllm_300k", "sglang-fcfs-r1-h200-p600k": "h200_600k",
    "sglang-fcfs-r1-llama31": "llama31_fit", "sglang-fcfs-r1-e0bfresh": "a100_300k", "sglang-fcfs-r1-p150k": "a100_pool150k",
    "sglang-fcfs-r1-p600k": "a100_pool600k", "sglang-fcfs-r1-h200": "h200_300k",
}
BURST_N = {"sglang-fcfs-r1-b100": 100, "sglang-fcfs-r1-b50": 50, "sglang-fcfs-r1-b60": 60}


def cell_model(cell: str):
    if cell == "llama31_fit":
        spec = load_spec(os.path.join(ROOT, "analysis/theory/cells/llama31_8b_300k.yaml"))
        spec["costs"]["fit_speed_to_e0a"] = dict(tokens_per_s=9352.893143955092, pop=32,
                                                 source="Llama E0a all-miss uncached tokens (registration measured value)")
        spec["costs"].pop("decode_side_speedup", None)
        spec["name"] = "llama31_8b_300k_fit"
        m, _, info = build(spec)
        return m, info
    m, _, info = build(load_spec(os.path.join(ROOT, f"analysis/theory/cells/{cell}.yaml")))
    return m, info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "theory", "icml"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    runs = [r for r in ms.find_runs() if r["name"] == "agentload_e2_burst" and r["arm"] in ("burst", "noburst")
            and r["label"] in CELL_OF_LABEL and not str(r["label"]).startswith(("sglang-fcfs-r1-rescue", "sglang-lpminf"))]
    e0b = [r for r in ms.find_runs() if r["name"] == "agentload_e0_cap" and r["label"] in CELL_OF_LABEL]
    models: Dict[str, tuple] = {}
    out_runs: List[Dict[str, object]] = []
    for r in sorted(runs, key=lambda x: (x["label"], x["rate_mult"], x["seed"], x["run_dir"])):
        st = ms.window_stats(os.path.join(ROOT, r["run_dir"]), 5700.0, 8700.0)
        if st["fu_hit"] >= 0.2:            # not stuck in the window: outside the theorem's regime (the trap)
            continue
        out_runs.append(dict(r, kind="e2", **st))
    for r in sorted(e0b, key=lambda x: (x["label"], x["rate_mult"], x["seed"], x["run_dir"])):
        st = ms.window_stats(os.path.join(ROOT, r["run_dir"]), 1500.0, 3000.0, t_burst=None)
        if st["fu_hit"] >= 0.2:
            continue
        out_runs.append(dict(r, kind="e0b", **st))

    rng = np.random.default_rng(20261105)
    groups = defaultdict(list)
    for r in out_runs:
        groups[(r["kind"], r["label"], r["rate_mult"])].append(r)
    out_groups = []
    for (kind, label, mult), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        cell = CELL_OF_LABEL[label]
        if cell not in models:
            m, info = cell_model(cell)
            tc = trap_costs(m)
            cs = summarize_curve(m)
            models[cell] = (m, tc, cs, info)
        m, tc, cs, info = models[cell]
        lam_ref = float(rs[0]["lambda_ref"])
        lam = mult * lam_ref
        a = trap_asymptotics(lam, tc)
        lam_real = float(np.mean([x["arrival_rate_since_burst"] for x in rs])) if kind == "e2" else float(
            np.mean([x["arrival_rate_window"] for x in rs]))
        g = dict(kind=kind, label=label, cell=cell, rate_mult=mult, lam=lam, lam_ref=lam_ref, n_runs=len(rs),
                 asym=a, mu_b=tc.mu_b, lam_miss_over_ref=tc.lam_miss / lam_ref)
        if kind == "e2":
            try:
                n1 = open_equilibria(cs, lam).n1
            except Exception:
                n1 = float("nan")
            n1 = n1 if (n1 == n1 and n1 > 0) else 0.0
            burst = BURST_N.get(label, 200)
            lam_after = None
            if label == "sglang-fcfs-r1-shed-t600":
                lam_after = [(1800.0, 0.0), (2400.0, lam)]
            tr = fifo_fluid(lam, tc, n1, burst_n=burst, lam_after=lam_after)
            fw = fluid_window(tr, 5700.0, 8700.0, tc)
            g["fluid_window"] = fw
            g["n1"] = n1
            # stochastic FIFO: distribution of the registered slope statistic
            if args.reps > 0 and label not in ("sglang-fcfs-r1-shed-t600", "sglang-fcfs-r1-toolslow-d30"):
                sl = [stochastic_fifo(lam, tc, n1, rng, burst_n=burst)["slope"] for _ in range(args.reps)]
                sl = np.array(sl)
                thr = 0.5 * (lam - lam_ref)
                g["stoch_slope"] = dict(mean=float(sl.mean()), sd=float(sl.std(ddof=1)), q10=float(np.quantile(sl, 0.1)),
                                        q90=float(np.quantile(sl, 0.9)), threshold=thr, p_above=float((sl > thr).mean()),
                                        p_neg=float((sl < 0).mean()), reps=args.reps)
        meas = {k: [x[k] for x in rs] for k in ("backlog_slope", "completion_rate", "P_served_mean", "k_served_mean",
                                                "uncached_tok_per_s", "gap_median", "gap_slope", "gap_med_slope", "N_mean",
                                                "arrival_rate_since_burst", "arrival_rate_window", "fu_hit")}
        meas["tokens_ref"] = rs[0]["tokens_ref"]
        g["measured"] = meas
        g["runs"] = [x["run_dir"] for x in rs]
        g["seeds"] = [x["seed"] for x in rs]
        out_groups.append(g)

    with open(os.path.join(args.out, "trap_check.json"), "w") as f:
        json.dump(dict(groups=out_groups, runs=out_runs, reps=args.reps), f, indent=1, default=float)
    # tables
    L = ["# Theorem 1/2 against the committed trapped runs (retrospective; nothing fitted to trap data)", "",
         "Window [5700, 8700) s for E2-protocol runs, [1500, 3000) s for unstable E0b runs. rho = lambda / lambda_miss(model). "
         "Measured values are per seed. alpha = asymptotic backlog slope (Theorem 1); fluid = the exact FIFO fluid from the "
         "registered burst, over the same window; D = asymptotic session completion rate; P = mean prompt of the turns served.", "",
         "| run group | rho | slope meas. (per seed) | alpha / fluid window | slope / (lam - lam_ref) meas. | alpha / (lam - lam_miss) | "
         "completions meas. / lam_ref | D / lam_ref | P served meas. | P pred. (asym / fluid) | tok rate meas. / ref | tok ratio pred. |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in out_groups:
        a, me = g["asym"], g["measured"]
        lr = g["lam_ref"]
        fw = g.get("fluid_window", {})
        sl = me["backlog_slope"]
        L.append("| {k} {lab} {m}x ({n}) | {rho:.2f} | {s} | {al:.4f} / {fl} | {sr} | {ar:.3f} | {cr} | {D:.2f} | {P} | {Pa:.0f} / {Pf} | {tr} | {tk:.3f} |".format(
            k=g["kind"], lab=g["label"], m=g["rate_mult"], n=g["n_runs"], rho=a["rho"],
            s=", ".join(f"{x:.4f}" for x in sl), al=a["alpha"], fl=(f"{fw['slope']:.4f}" if fw else "-"),
            sr=", ".join(f"{x / (g['lam'] - lr):.2f}" for x in sl), ar=a["alpha_over_excess"],
            cr=", ".join(f"{x / lr:.2f}" for x in me["completion_rate"]), D=a["D"] / lr,
            P=", ".join(f"{x:.0f}" for x in me["P_served_mean"]), Pa=a["P_served_mean"],
            Pf=(f"{fw['P_served_mean']:.0f}" if fw else "-"),
            tr=", ".join(f"{x / me['tokens_ref']:.3f}" for x in me["uncached_tok_per_s"]) if me["tokens_ref"] else "-",
            tk=a["tok_ratio"]))
    L += ["", "| run group | stochastic FIFO slope mean (sd) | registered threshold 0.5 (lam - lam_ref) | P(slope > threshold) per run | "
          "measured slopes above threshold | gap slope meas. (300 s medians) | gamma (asym) / fluid V slope |", "|---|---|---|---|---|---|---|"]
    for g in out_groups:
        s = g.get("stoch_slope")
        me = g["measured"]
        thr = 0.5 * (g["lam"] - g["lam_ref"])
        L.append("| {k} {lab} {m}x | {sm} | {thr:.4f} | {p} | {na}/{n} | {gs} | {ga:.4f} / {fv} |".format(
            k=g["kind"], lab=g["label"], m=g["rate_mult"],
            sm=(f"{s['mean']:.4f} ({s['sd']:.4f})" if s else "-"), thr=thr, p=(f"{s['p_above']:.2f}" if s else "-"),
            na=sum(1 for x in me["backlog_slope"] if x > thr), n=len(me["backlog_slope"]),
            gs=", ".join(f"{x:.4f}" for x in me["gap_med_slope"]), ga=g["asym"]["gamma"],
            fv=(f"{g['fluid_window']['V_slope']:.4f}" if g.get("fluid_window") else "-")))
    with open(os.path.join(args.out, "trap_check.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    # universality: alpha / lambda_miss against rho, measured and predicted
    with open(os.path.join(args.out, "universality.csv"), "w") as f:
        f.write("kind,label,cell,rate_mult,seed,rho,slope_over_lam_miss,completion_over_lam_miss,alpha_over_lam_miss_pred,"
                "D_over_lam_miss_pred,P_ratio_meas,P_ratio_pred\n")
        for g in out_groups:
            lm = g["asym"]["lam_miss"]
            Pst = g["asym"]["P_stat_mean"]
            for i in range(g["n_runs"]):
                me = g["measured"]
                f.write(f"{g['kind']},{g['label']},{g['cell']},{g['rate_mult']},{g['seeds'][i]},{g['asym']['rho']:.5f},"
                        f"{me['backlog_slope'][i] / lm:.5f},{me['completion_rate'][i] / lm:.5f},{g['asym']['alpha'] / lm:.5f},"
                        f"{g['asym']['D'] / lm:.5f},{me['P_served_mean'][i] / Pst:.5f},{g['asym']['P_served_ratio']:.5f}\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
