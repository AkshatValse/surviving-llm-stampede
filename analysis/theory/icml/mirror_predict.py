r"""Freeze model-F predictions for the r16 MIRROR test: the step-capped workload, BURST arms at 1.65x and 1.35x, seeds 0-2.

    PYTHONPATH="src;." python -m analysis.theory.icml.mirror_predict

Design (lead session, 2026-11-05).  The E2 BURST protocol with configs/agentload_e2_mirror_k20.yaml, which is
configs/agentload_e2_burst.yaml with exactly two workload values changed: mean_turns 15 -> 1000 and max_turns 60 -> 20, so
T = min(Geometric(1/1000), 20) and about 98% of sessions run exactly 20 turns.  SGLang 0.5.22 FCFS, waiting-prefix refresh
on, 300k pool, Qwen2.5-7B-Instruct, A100 80GB PCIe: the measured cell a100_300k with its workload replaced.  Rates are
multiples of the registered lambda_ref of the STANDARD workload (prereg/inputs/2026-10-23/calibration.json), as in every E2 job.

Inputs.  (1) The frozen a100_300k cell model (analysis/theory/cells/a100_300k.yaml, calibrated costs used unchanged) with the
step-capped workload, and the Theorem 1/2 code (trap_renewal.py, unchanged).  (2) The exact client plans, rebuilt with
agentload.workload.build_open_plan from the MIRROR config (the code path the client runs).  (3) For the tolerance only: the
model-minus-measured residuals of model F on the committed STANDARD-workload BURST runs, frozen in
results/theory/icml/cut_predictions.json (noise) at tag icml-cut-pred.  No MIRROR result exists when this runs.

What model F says for this workload (Theorem 2): the turn-count factor H(z) = E[T] E z^{-T} / sum_k G_k z^{-k} is far below 1
for a nearly deterministic T, and outweighs the cost-growth factor Gamma(z) > 1, so the trapped engine completes sessions
BELOW its all-miss capacity (the youth premium reversed).  The exact plan-driven FIFO (plan_fifo) adds the transient: a
burst cohort that needs 20 FIFO cycles before any of it completes, hence a near-blackout of completions and then a completion
wave.  Every throughput-curve reading (quasi-static: completions at lambda_miss while trapped; Lu et al.'s
dN/dt = lambda - X(N)/K; the paper's Eq. (fluid)) predicts steady completions at the all-miss capacity instead.

Writes results/theory/r16/mirror_predictions.json and results/theory/r16/mirror_plans/<arm>_<mult>_seed<k>.csv.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import replace
from pathlib import Path
from typing import Dict, List

import numpy as np

from ..fluid_rigorous.model import Model, open_equilibria, summarize_curve
from ..merged.spec import ROOT
from .cut_predict import backlog_stats, lam_ref, n_series, plan_csv, plan_fifo, served_stats
from .run_check import cell_model
from .trap_renewal import fifo_fluid, trap_asymptotics, trap_costs
from .trap_renewal import window_stats as fluid_window_stats

CFG = "configs/agentload_e2_mirror_k20.yaml"
CALIB = "prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based"
CELL = "a100_300k"
MEAN_TURNS, MAX_TURNS = 1000.0, 20
MULTS = (1.65, 1.35)                 # 1.65: decisive cell; 1.35: secondary cell
SEEDS = (0, 1, 2)
T_B, T_END = 1200.0, 8700.0
BIN_S = 300.0                        # completion-rate bins: [1200 + 300 j, 1500 + 300 j)
WINDOWS = {                          # named windows of the registered rules (seconds)
    "blackout": (2400.0, 3600.0),    # M1: completions while the burst cohort is still cycling
    "late": (6600.0, 8700.0),        # M3: completions after the wave
    "slope": (6000.0, 8700.0),       # M4: backlog slope after the wave
    "w5700": (5700.0, 8700.0),       # the frozen E2 evaluation window (reported)
}
PEAK_SEARCH = (3000.0, 8700.0)       # M2: the 300-s bin with the most completions is searched here
NOISE_SRC = ("icml-cut-pred", "results/theory/icml/cut_predictions.json")
OUT = "results/theory/r16/mirror_predictions.json"
PLAN_DIR = "results/theory/r16/mirror_plans"


def capped_model():
    m0, info = cell_model(CELL)
    m = Model(replace(m0.wl, mean_turns=MEAN_TURNS, K=MAX_TURNS), m0.cost, m0.M)
    return m0, m, info


def build_plan(seed: int, mult: float, burst: bool):
    from agentload.config import load_config
    from agentload.workload import build_open_plan
    ov = [f"arrivals.lambda_ref={CALIB}", f"arrivals.rate_mult={mult}", f"run.seed={seed}"]
    if not burst:
        ov.append("arrivals.burst=null")
    cfg, _ = load_config(os.path.join(ROOT, CFG), ov)
    from agentload.config import resolve_rate
    rate = resolve_rate(cfg.arrivals, base_dir=Path(ROOT))
    plan = build_open_plan(seed, cfg.workload, cfg.arrivals, T_END, rate, [])
    assert cfg.workload.mean_turns == MEAN_TURNS and cfg.workload.max_turns == MAX_TURNS
    return plan, cfg, rate


def bins_completion(ends: np.ndarray, lr: float) -> Dict[str, List[float]]:
    edges = np.arange(T_B, T_END + 1e-9, BIN_S)
    cnt, _ = np.histogram(ends[np.isfinite(ends)], bins=edges)
    rate = cnt / BIN_S
    return dict(bin_start=[float(x) for x in edges[:-1]], count=[int(c) for c in cnt],
                rate_over_lam_ref=[float(r / lr) for r in rate])


def peak_bin(b: Dict[str, List[float]]) -> Dict[str, float]:
    st = np.array(b["bin_start"])
    r = np.array(b["rate_over_lam_ref"])
    sel = (st >= PEAK_SEARCH[0]) & (st + BIN_S <= PEAK_SEARCH[1])
    j = int(np.flatnonzero(sel)[int(np.argmax(r[sel]))])
    return dict(bin_start=float(st[j]), center=float(st[j] + BIN_S / 2), rate_over_lam_ref=float(r[j]))


def burst_timing(plan, ends: np.ndarray) -> Dict[str, float]:
    """Completion times of the burst cohort (origin burst) in the plan-driven model F: median, quartiles, deciles, and the
    share completed by T_END.  The median is the registered 'wave time'."""
    e = np.array([x for p, x in zip(plan, ends) if p.origin == "burst"])
    fin = e[np.isfinite(e) & (e <= T_END)]
    q = np.percentile(fin, [10, 25, 50, 75, 90]) if len(fin) else [math.nan] * 5
    return dict(n=int(len(e)), completed_by_end=int(len(fin)), p10=float(q[0]), q1=float(q[1]), median=float(q[2]),
                q3=float(q[3]), p90=float(q[4]))


def timing_calibration() -> Dict[str, object]:
    """The engine-vs-model-F timing factor on COMMITTED STANDARD-workload runs only (the six sglang-fcfs-r1 BURST runs at
    1.35x and 1.65x dated before 2026-11-04, cut_predict.committed_burst_runs): per run, the median over burst sessions that
    completed and that model F predicts to complete after 3000 s of (t_end measured - 1200) / (t_end model F - 1200).
    The factor is the mean of the six medians.  No MIRROR result is read."""
    import pandas as pd
    from .cut_predict import build_plan_from_run, committed_burst_runs
    lr = lam_ref()
    m0, _ = cell_model(CELL)
    tc0 = trap_costs(m0)
    cs0 = summarize_curve(m0)
    rows = []
    for r in committed_burst_runs():
        d = os.path.join(ROOT, r["run_dir"])
        plan, cfg = build_plan_from_run(d)
        lam = float(cfg.arrivals.rate_mult) * lr
        n1 = float(open_equilibria(cs0, lam).n1)
        lat = (n1 / lam - (tc0.ET - 1.0) * float(m0.wl.zbar)) / tc0.ET
        pf = plan_fifo(plan, tc0, lat)
        pred = {p.sid: e for p, e in zip(plan, pf["ends"])}
        ses = pd.read_csv(os.path.join(d, "sessions.csv"))
        ses = ses[(ses["origin"] == "burst") & (ses["status"] == "completed")]
        pairs = [(float(t), pred.get(int(s), math.inf)) for s, t in zip(ses["sid"], ses["t_end"])]
        pairs = [(a, b) for a, b in pairs if np.isfinite(b) and b > 3000.0]
        ratio = np.array([(a - T_B) / (b - T_B) for a, b in pairs])
        rows.append(dict(run_dir=r["run_dir"], mult=float(cfg.arrivals.rate_mult), seed=int(cfg.run.seed), n=int(len(ratio)),
                         median_ratio=float(np.median(ratio))))
    med = np.array([x["median_ratio"] for x in rows])
    return dict(rule=timing_calibration.__doc__.split("\n")[0], runs=rows, factor=float(med.mean()),
                sd=float(med.std(ddof=1)), min=float(med.min()), max=float(med.max()))


def load_noise() -> Dict[str, object]:
    import subprocess
    tag, path = NOISE_SRC
    try:
        txt = subprocess.run(["git", "-C", ROOT, "show", f"{tag}:{path}"], check=True, capture_output=True, text=True).stdout
        return dict(source=f"{tag}:{path}", noise=json.loads(txt).get("noise"))
    except Exception as e:                                   # the tag is not fetched: report, never invent
        return dict(source=f"{tag}:{path}", noise=None, error=str(e)[:200])


def main(argv=None) -> int:
    lr = lam_ref()
    m0, m, info = capped_model()
    tc, tc0 = trap_costs(m), trap_costs(m0)
    cs = summarize_curve(m)
    zbar = float(m.wl.zbar)
    out: Dict[str, object] = dict(
        tag="r16-mirror-reg", config=CFG, config_sha256=hashlib.sha256(open(os.path.join(ROOT, CFG), "rb").read()).hexdigest(),
        theory="notes/THEORY_ICML_2026-11.md (Theorem 1, Theorem 2: D/lambda_miss = H(z) Gamma(z)); model F unchanged",
        cell=CELL, workload=dict(mean_turns=MEAN_TURNS, max_turns=MAX_TURNS, ET=tc.ET, P_T_eq_K=float(tc.p[-1])),
        lambda_ref=lr, lambda_miss_model=tc.lam_miss, lambda_miss_model_over_ref=tc.lam_miss / lr,
        lambda_miss_standard_model_over_ref=tc0.lam_miss / lr,
        n_b=float(cs.n_b), mu_max_over_ref=float(cs.mu_max / lr), windows=WINDOWS, bin_s=BIN_S, peak_search=PEAK_SEARCH,
        noise_standard_workload=load_noise(), cells={})
    cal = timing_calibration()
    cal["rule"] = " ".join((timing_calibration.__doc__ or "").split())
    out["timing_calibration_standard_workload"] = cal
    os.makedirs(os.path.join(ROOT, PLAN_DIR), exist_ok=True)
    for mult in MULTS:
        lam = mult * lr
        oe = open_equilibria(cs, lam)
        n1 = float(oe.n1)
        lat_good = (n1 / lam - (tc.ET - 1.0) * zbar) / tc.ET
        a = trap_asymptotics(lam, tc)
        a_std = trap_asymptotics(lam, tc0)
        tr = fifo_fluid(lam, tc, n1, think=zbar)
        fl = {k: fluid_window_stats(tr, t0, t1, tc) for k, (t0, t1) in WINDOWS.items()}
        cell: Dict[str, object] = dict(
            mult=mult, lam=lam, rho=a["rho"], n1_good=n1, n_u_good=float(oe.n_u), lat_good_s=lat_good,
            asymptotics=dict(z=a["z"], gamma=a["gamma"], alpha=a["alpha"], D=a["D"], D_over_lam_miss=a["D_over_lam_miss"],
                             D_over_lam_ref=a["D"] / lr, H_T=a["H_T"], Gamma_c=a["C_c"],
                             alpha_over_excess=a["alpha_over_excess"], P_served_mean=a["P_served_mean"]),
            standard_workload_asymptotics=dict(D_over_lam_miss=a_std["D_over_lam_miss"], D_over_lam_ref=a_std["D"] / lr,
                                               alpha=a_std["alpha"], H_T=a_std["H_T"], Gamma_c=a_std["C_c"]),
            fluid_nominal=dict(completion_over_lam_ref={k: fl[k]["completion_rate"] / lr for k in WINDOWS},
                               slope={k: fl[k]["slope"] for k in WINDOWS},
                               P_served={k: fl[k]["P_served_mean"] for k in WINDOWS}),
            seeds={})
        for seed in SEEDS:
            plan, cfg, rate = build_plan(seed, mult, burst=True)
            assert abs(rate - lam) < 1e-12 * lam
            with open(os.path.join(ROOT, PLAN_DIR, f"burst_{mult:g}_seed{seed}.csv"), "w", newline="\n") as f:
                f.write(plan_csv(plan))
            nb_plan, _, _ = build_plan(seed, mult, burst=False)
            with open(os.path.join(ROOT, PLAN_DIR, f"noburst_{mult:g}_seed{seed}.csv"), "w", newline="\n") as f:
                f.write(plan_csv(nb_plan))
            pf = plan_fifo(plan, tc, lat_good)
            starts, ends = pf["starts"], pf["ends"]
            b = bins_completion(ends, lr)
            sd: Dict[str, object] = dict(
                n_sessions=len(plan), n_burst=int(sum(p.origin == "burst" for p in plan)),
                frac_T_eq_20=float(np.mean([p.n_turns == MAX_TURNS for p in plan])),
                completion_bins=b, peak=peak_bin(b), windows={})
            bt = burst_timing(plan, ends)
            bt["median_calibrated"] = T_B + cal["factor"] * (bt["median"] - T_B)
            sd["burst_timing"] = bt
            for k, (t0, t1) in WINDOWS.items():
                bs = backlog_stats(starts, ends, t0, t1)
                ss = served_stats(pf, tc, t0, t1)
                lam_plan = float(((starts >= t0) & (starts < t1)).sum() / (t1 - t0))
                sd["windows"][k] = dict(
                    lam_plan=lam_plan, completion_over_lam_ref=bs["completion_rate"] / lr, slope=bs["slope"],
                    N_start=bs["N_start"], N_end=bs["N_end"], P_served_mean=ss["P_served_mean"],
                    k_served_mean=ss["k_served_mean"], gap_median=ss["gap_median"], gap_med_slope=ss["gap_med_slope"],
                    qs_completion_over_lam_ref=tc.lam_miss / lr, qs_slope=lam_plan - tc.lam_miss)
            c, nmeans = n_series(starts, ends, T_B, T_END, 300.0)
            sd["N_300s"] = dict(center=[float(x) for x in c], mean=[float(x) for x in nmeans])
            cell["seeds"][str(seed)] = sd
        out["cells"][f"{mult:g}"] = cell
    os.makedirs(os.path.dirname(os.path.join(ROOT, OUT)), exist_ok=True)
    with open(os.path.join(ROOT, OUT), "w", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    # console summary
    print(f"lambda_miss model {tc.lam_miss / lr:.3f} x ref (standard {tc0.lam_miss / lr:.3f}); n_b {cs.n_b:.1f}")
    print(f"timing factor (standard workload, committed runs): {cal['factor']:.4f} sd {cal['sd']:.4f} "
          f"[{cal['min']:.4f}, {cal['max']:.4f}] over {len(cal['runs'])} runs")
    for mk, cell in out["cells"].items():
        a = cell["asymptotics"]
        print(f"\n{mk}x: rho {cell['rho']:.3f}  D/lam_miss {a['D_over_lam_miss']:.3f} (H {a['H_T']:.3f}, Gamma {a['Gamma_c']:.3f});"
              f" standard D/lam_miss {cell['standard_workload_asymptotics']['D_over_lam_miss']:.3f}; n1 {cell['n1_good']:.1f} n_u {cell['n_u_good']:.1f}")
        for s, sd in cell["seeds"].items():
            w = sd["windows"]
            print(f"  seed {s}: n={sd['n_sessions']} burst={sd['n_burst']} T=20 {sd['frac_T_eq_20']:.3f} | "
                  f"blackout {w['blackout']['completion_over_lam_ref']:.3f} | peak {sd['peak']['center']:.0f}s "
                  f"{sd['peak']['rate_over_lam_ref']:.2f} | late {w['late']['completion_over_lam_ref']:.3f} | "
                  f"slope[6000,8700) {w['slope']['slope']:+.4f} (QS {w['slope']['qs_slope']:+.4f}) | "
                  f"P_served w5700 {w['w5700']['P_served_mean']:.0f}")
            bt = sd["burst_timing"]
            print(f"     burst cohort: median {bt['median']:.0f}s (calibrated {bt['median_calibrated']:.0f}s) IQR "
                  f"[{bt['q1']:.0f}, {bt['q3']:.0f}] p10-p90 [{bt['p10']:.0f}, {bt['p90']:.0f}] done {bt['completed_by_end']}/{bt['n']}")
            print("     bins: " + " ".join(f"{x:.2f}" for x in sd["completion_bins"]["rate_over_lam_ref"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
