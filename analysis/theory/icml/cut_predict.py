r"""Freeze model-F predictions for the arrival-cut test of Corollary 3 (arms CUT-A and CUT-B, seeds 0-2).

    PYTHONPATH="src;." python -m analysis.theory.icml.cut_predict [--mc 200000]

Design (lead session, 2026-11-05): SGLang FCFS refresh 1, 300k pool, Qwen2.5-7B, A100 80GB PCIe (cell sglang-fcfs-r1 ->
a100_300k).  Ramp arrivals (ramp_is_mult, rate_max 1.65 x lambda_ref) with a burst of 200 sessions on [1200, 1260) s; at
t_cut = 2400 s the rate drops to lambda' = 1.15 (CUT-A) or 0.85 (CUT-B) x lambda_ref until 8700 s.

Inputs.  (1) The frozen a100_300k cell model and the Theorem 1/2 code (trap_renewal.py, unchanged).  (2) The exact client
plans, rebuilt here with agentload.workload.build_open_plan from configs/agentload_e2_shed_t600.yaml with the cut ramp as
an override (the same code path the client runs).  (3) For the noise model and the expected value of the naive
comparator only: committed sglang-fcfs-r1 BURST runs whose run directory is dated before 2026-11-04.  No result of the
cut runs exists when this runs.

Writes configs/icml_cut_predict.yaml, results/theory/icml/cut_predictions.json and results/theory/icml/cut_plans/*.csv.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import heapq
import io
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

from ..fluid_rigorous.model import open_equilibria, summarize_curve
from ..merged.spec import ROOT
from . import measured as ms
from .run_check import cell_model
from .trap_renewal import busy_period, fifo_fluid, trap_asymptotics, trap_costs
from .trap_renewal import window_stats as fluid_window_stats

CALIB = "prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based"
SHED_CFG = "configs/agentload_e2_shed_t600.yaml"
BURST_CFG = "configs/agentload_e2_burst.yaml"
CELL = "a100_300k"
BASE_MULT = 1.65
T_B, T_CUT, T_END = 1200.0, 2400.0, 8700.0
ARMS = {"CUT-A": 1.15, "CUT-B": 0.85}
SEEDS = (0, 1, 2)
WINDOWS = {"w3000": (3000.0, 8700.0), "w5700": (5700.0, 8700.0)}
PRE_CUT = (1800.0, 2400.0)                       # the naive comparator's completion window
CONTROL_DIRS = {0: "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/20261024-155120",
                1: "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/20261024-184132",
                2: "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/20261025-000043"}
BLIND_BEFORE = "20261104"                       # never read a run directory dated on or after this


def R(x: float, n: int = 6) -> float:
    return float(round(float(x), n))


def lam_ref() -> float:
    path, key = CALIB.rsplit(":", 1)
    return float(json.loads(Path(ROOT, path).read_text())[key])


def cut_ramp(mult_after: float) -> List[List[float]]:
    """The cut in the SHED config's knot convention (a 1 ms linear step at the switch)."""
    return [[0.0, BASE_MULT], [T_CUT, BASE_MULT], [T_CUT + 0.001, mult_after], [T_END, mult_after]]


def build_cut_plan(seed: int, mult_after: float):
    from agentload.config import load_config, resolve_ramp
    from agentload.workload import build_open_plan
    ov = [f"arrivals.ramp={json.dumps(cut_ramp(mult_after))}", f"arrivals.lambda_ref={CALIB}", f"run.seed={seed}",
          "arrivals.burst={n: 200, t_s: 1200, width_s: 60}", "arrivals.kind=ramp", "arrivals.ramp_is_mult=true"]
    cfg, _ = load_config(os.path.join(ROOT, SHED_CFG), ov)
    knots = resolve_ramp(cfg.arrivals, base_dir=Path(ROOT))
    return build_open_plan(seed, cfg.workload, cfg.arrivals, T_END, None, knots), cfg.workload


def build_plan_from_run(run_dir: str):
    """The constant-rate plan of a committed run, rebuilt from its config_effective.yaml."""
    from agentload.config import load_config, resolve_rate, resolve_ramp
    from agentload.workload import build_open_plan
    cfg, _ = load_config(os.path.join(run_dir, "config_effective.yaml"))
    rate = resolve_rate(cfg.arrivals, base_dir=Path(ROOT))
    knots = resolve_ramp(cfg.arrivals, base_dir=Path(ROOT)) if cfg.arrivals.kind == "ramp" else []
    return build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, knots), cfg


def plan_csv(plan) -> str:
    """Same columns and float formatting as the client's plan.csv."""
    buf = io.StringIO()
    buf.write("sid,origin,idx,arrival_s,n_turns,tool_time_total_s\n")
    for p in plan:
        buf.write(f"{p.sid},{p.origin},{p.idx},{p.arrival_s!r},{p.n_turns},{float(sum(p.tool_times_s))!r}\n")
    return buf.getvalue()


def read_plan_csv(path: str) -> List[Tuple[str, int, float, int, float]]:
    rows = []
    with open(path) as f:
        next(f)
        for line in f:
            s = line.strip().split(",")
            rows.append((s[1], int(s[2]), float(s[3]), int(s[4]), float(s[5])))
    return rows


# ------------------------------------------------------------------ model F driven by the exact plan (per-seed plug-in)
def plan_fifo(plan, tc, lat_good: float, t_b: float = T_B, t_end: float = T_END) -> Dict[str, np.ndarray]:
    """Model F with the plan as input: one FIFO server doing c_k GPU-seconds for a session's k-th turn (all miss) from t_b on,
    each session's exact turn count and tool times from the plan.  Before t_b the engine is in the good state: a turn takes
    lat_good seconds (calibrated so the mean background equals the frozen open-equilibrium n1), so the sessions present at
    t_b and their next turns come from the plan as well.  Deterministic given the plan."""
    K = len(tc.k)
    n = len(plan)
    starts = np.array([p.arrival_s for p in plan])
    ends = np.full(n, math.inf)
    ev: List[tuple] = []
    seq = 0
    for i, p in enumerate(plan):
        if p.arrival_s >= t_b:
            ev.append((p.arrival_s, seq, i, 1)); seq += 1
            continue
        s = p.arrival_s                               # good state: turn j occupies [s, s + lat_good), then a tool call
        placed = False
        for j in range(1, p.n_turns + 1):
            if s + lat_good > t_b:                    # in service at t_b (or later): joins the trap's FIFO
                ev.append((max(s, t_b), seq, i, j)); seq += 1
                placed = True
                break
            if j == p.n_turns:
                ends[i] = s + lat_good
                placed = True
                break
            s = s + lat_good + p.tool_times_s[j - 1]
        assert placed
    heapq.heapify(ev)
    t_free = t_b
    served = []                                       # (start, done, sid, k)
    while ev:
        tj, _, i, k = heapq.heappop(ev)
        if tj > t_end:
            break
        start = max(t_free, tj)
        done = start + tc.c[min(k, K) - 1]
        t_free = done
        served.append((start, done, i, k))
        if k >= plan[i].n_turns:
            ends[i] = done
        else:
            heapq.heappush(ev, (done + plan[i].tool_times_s[k - 1], seq, i, k + 1)); seq += 1
    return dict(starts=starts, ends=ends, served=np.array(served) if served else np.zeros((0, 4)))


def backlog_stats(starts: np.ndarray, ends: np.ndarray, t0: float, t1: float, bin_s: float = 10.0) -> Dict[str, float]:
    """The registered statistic (as in measured.window_stats): sessions in system (arrived, not completed) sampled at 1 s,
    10 s bin means, OLS slope; completions and arrivals per second in [t0, t1)."""
    st, en = np.sort(starts), np.sort(ends)
    tt = np.arange(t0, t1, 1.0)
    n_sys = np.searchsorted(st, tt, side="right") - np.searchsorted(en, tt, side="right")
    nb = int(len(tt) // bin_s)
    means = n_sys[: nb * int(bin_s)].reshape(nb, int(bin_s)).mean(axis=1)
    centers = t0 + bin_s * (np.arange(nb) + 0.5)
    return dict(slope=float(np.polyfit(centers, means, 1)[0]),
                completion_rate=float(((ends >= t0) & (ends < t1)).sum() / (t1 - t0)),
                arrival_rate=float(((starts >= t0) & (starts < t1)).sum() / (t1 - t0)),
                N_start=float(means[0]), N_end=float(means[-1]), N_mean=float(means.mean()))


def n_series(starts: np.ndarray, ends: np.ndarray, t0: float, t1: float, bin_s: float) -> Tuple[np.ndarray, np.ndarray]:
    st, en = np.sort(starts), np.sort(ends)
    tt = np.arange(t0, t1, 1.0)
    n_sys = np.searchsorted(st, tt, side="right") - np.searchsorted(en, tt, side="right")
    nb = int(len(tt) // bin_s)
    return t0 + bin_s * (np.arange(nb) + 0.5), n_sys[: nb * int(bin_s)].reshape(nb, int(bin_s)).mean(axis=1)


def served_stats(pf: Dict[str, np.ndarray], tc, t0: float, t1: float) -> Dict[str, float]:
    """Turns completed in [t0, t1) in the plan-driven model, with measured.window_stats' definitions: mean prompt of the turns
    served, mean turn index, and the gap between consecutive turn completions of a session (median and the trend of 300 s
    medians, by completion time)."""
    sv = pf["served"]
    if len(sv) == 0:
        return dict(P_served_mean=float("nan"), k_served_mean=float("nan"), gap_median=float("nan"), gap_med_slope=float("nan"))
    done, sid, k = sv[:, 1], sv[:, 2].astype(int), sv[:, 3].astype(int)
    last = {(int(a), int(b)): float(c) for a, b, c in zip(sid, k, done)}
    win = (done >= t0) & (done < t1)
    P = np.array([tc.P[min(kk, len(tc.k)) - 1] for kk in k[win]])
    gt, gg = [], []
    for d, i, kk in zip(done[win], sid[win], k[win]):
        if kk > 1 and (int(i), int(kk) - 1) in last:
            gt.append(d); gg.append(d - last[(int(i), int(kk) - 1)])
    gt, gg = np.array(gt), np.array(gg)
    mt, mg = [], []
    for a in np.arange(t0, t1, 300.0):
        sel = (gt >= a) & (gt < a + 300.0)
        if sel.sum() >= 10:
            mt.append(a + 150.0); mg.append(float(np.median(gg[sel])))
    return dict(P_served_mean=float(P.mean()), k_served_mean=float(k[win].mean()), turns_per_s=float(win.sum() / (t1 - t0)),
                gap_median=float(np.median(gg)) if len(gg) else float("nan"),
                gap_med_slope=float(np.polyfit(mt, mg, 1)[0]) if len(mt) >= 3 else float("nan"))


def dip(starts: np.ndarray, ends: np.ndarray, bin_s: float = 300.0) -> Dict[str, float]:
    """Post-cut dip on 300 s bin means: the reference is the [2100, 2400) mean; the dip is the lowest bin in [2400, 8700)."""
    c, m = n_series(starts, ends, T_CUT - bin_s, T_END, bin_s)
    ref = float(m[0])
    j = int(np.argmin(m[1:])) + 1
    return dict(N_ref_2100_2400=ref, N_min=float(m[j]), t_min_bin_center=float(c[j]), depth=ref - float(m[j]),
                depth_frac=(ref - float(m[j])) / ref, N_last_bin=float(m[-1]))


def fluid_dip(tr: Dict[str, np.ndarray]) -> Dict[str, float]:
    t, N = tr["t"], tr["N"]
    i0 = int(np.searchsorted(t, T_CUT))
    j = i0 + int(np.argmin(N[i0:]))
    return dict(N_cut=float(N[i0]), N_min=float(N[j]), t_min=float(t[j]), depth=float(N[i0] - N[j]),
                depth_frac=float((N[i0] - N[j]) / N[i0]), N_end=float(N[-1]), regrows=bool(N[-1] > N[j] + 1e-9))


# ------------------------------------------------------------------ committed runs: noise model and the naive's pre-cut value
def committed_burst_runs() -> List[Dict[str, object]]:
    """sglang-fcfs-r1 BURST runs (constant rate, burst 200, no cap) dated before 2026-11-04 that are stuck over [5700, 8700)."""
    out = []
    for r in ms.find_runs():
        if r["label"] != "sglang-fcfs-r1" or r["name"] != "agentload_e2_burst":
            continue
        stamp = re.findall(r"(\d{8})-\d{6}", r["run_dir"])
        if not stamp or stamp[-1] >= BLIND_BEFORE:
            continue
        d = os.path.join(ROOT, r["run_dir"])
        raw = yaml.safe_load(open(os.path.join(d, "config_effective.yaml")))
        a, g = raw.get("arrivals", {}), raw.get("gate", {}) or {}
        if a.get("kind") != "constant" or not a.get("burst") or (a["burst"] or {}).get("n") != 200 or g.get("n_cap"):
            continue
        out.append(r)
    return out


def write_yaml(out: Dict[str, object]) -> None:
    """configs/icml_cut_predict.yaml: the registered per-arm, per-seed numbers (rounded) and the rule."""
    lr = out["lambda_ref"]
    y: Dict[str, object] = dict(
        tag="icml-cut-pred",
        theory=out["theory"],
        cell=dict(label="sglang-fcfs-r1", model_cell=CELL, lambda_ref=R(lr, 8), lambda_miss_model=R(out["lambda_miss_model"], 8),
                  n_b_sessions=R(out["n_b"], 2)),
        design=dict(arrivals="kind ramp, ramp_is_mult, rate_max 1.65 x lambda_ref (S_ARRIVALS candidates, S_THIN keep)",
                    ramp_knots={arm: cut_ramp(m) for arm, m in ARMS.items()}, burst="200 sessions uniform on [1200, 1260) s",
                    duration_s=T_END, seeds=list(SEEDS),
                    plans_built_with=("agentload.workload.build_open_plan on configs/agentload_e2_shed_t600.yaml with overrides "
                                      "arrivals.ramp=<knots above>, arrivals.lambda_ref=" + CALIB + ", run.seed=<seed>; plan CSVs in "
                                      "results/theory/icml/cut_plans/ (client plan.csv format)"),
                    pre_cut_identical_to_controls=out["pre_cut_identity_with_controls"]),
        statistic=("backlog = sessions arrived and not completed, sampled at 1 s, 10 s bin means, OLS slope over the window "
                   "(analysis/theory/icml/measured.py window_stats: backlog_slope)"),
        naive=dict(formula="naive_slope(W) = lam_plan(W) - C_run[1800, 2400), lam_plan(W) = plan base arrivals in W / |W|, "
                           "C_run = sessions of that run completed in [1800, 2400) / 600 s",
                   note="expected values below use the same-seed 1.65x BURST control's C[1800, 2400) (identical pre-cut plan)"),
        arms={})
    for arm, a in out["arms"].items():
        fl = a["fluid"]
        ya: Dict[str, object] = dict(
            lam_after=R(a["lam_after"], 6), rho_after=R(a["rho_after"], 4),
            fluid_poisson_average=dict(slope_w3000=R(fl["slope"]["w3000"]), slope_w5700=R(fl["slope"]["w5700"]),
                                       completion_over_lam_ref_w5700=R(fl["completion_over_lam_ref_w5700"], 4),
                                       N_at_cut=R(fl["N_at_cut"], 1), N_8700=R(fl["N_8700"], 1),
                                       dip_depth=R(fl["dip"]["depth"], 1), dip_depth_frac=R(fl["dip"]["depth_frac"], 4),
                                       dip_time_s=R(fl["dip"]["t_min"], 0), regrows=fl["dip"]["regrows"],
                                       P_served_w5700=R(fl["P_served_w5700"], 0), V_slope_w5700=R(fl["V_slope_w5700"], 5),
                                       Vtot_at_cut_gpu_s=R(fl["Vtot_at_cut"], 1),
                                       clear_time_s=(R(fl["clear_time_s"], 0) if math.isfinite(fl["clear_time_s"]) else "never (rho' > 1)")),
            asymptotics_after=a["asymptotics_after"] and {k: R(v, 6) for k, v in a["asymptotics_after"].items()},
            plan_spread_seeds_0_39={wk: {k: R(v, 5) for k, v in d.items()} for wk, d in a["plan_spread_seeds_0_39"].items()},
            seeds={})
        for seed, sd in a["seeds"].items():
            ya["seeds"][int(seed)] = dict(
                plan_sha256=sd["plan_sha256"], plan_sessions=sd["plan_sessions"],
                theory_slope_w3000=R(sd["w3000"]["theory_slope"]), theory_slope_w5700=R(sd["w5700"]["theory_slope"]),
                lam_plan_w3000=R(sd["w3000"]["lam_plan"]), lam_plan_w5700=R(sd["w5700"]["lam_plan"]),
                naive_expected_w3000=R(sd["w3000"]["naive_expected"]), naive_expected_w5700=R(sd["w5700"]["naive_expected"]),
                control_C_1800_2400=R(sd["pre_cut_completion_control_meas"]), model_C_1800_2400=R(sd["pre_cut_completion_model"]),
                completion_w5700=R(sd["w5700"]["theory_completion"]),
                completion_over_lam_ref_w5700=R(sd["w5700"]["theory_completion"] / lr, 4),
                fu_hit_w5700="< 0.2 (STUCK; model F is all-miss while N > n_b)",
                N_bin_2100_2400=R(sd["dip"]["N_ref_2100_2400"], 1), N_last_bin_8400_8700=R(sd["dip"]["N_last_bin"], 1),
                dip_depth_300s_bins=R(sd["dip"]["depth"], 1), dip_depth_frac=R(sd["dip"]["depth_frac"], 4),
                dip_bin_center_s=R(sd["dip"]["t_min_bin_center"], 0),
                P_served_w5700=R(sd["served_w5700"]["P_served_mean"], 0), k_served_w5700=R(sd["served_w5700"]["k_served_mean"], 3),
                gap_median_w5700=R(sd["served_w5700"]["gap_median"], 1), gap_med_slope_w5700=R(sd["served_w5700"]["gap_med_slope"], 5),
                N_300s_bins=sd["N_300s_bins"]["N"])
        ya["p_pass"] = {k: dict(P_PASS_lead_rule=R(v["P_PASS_lead_rule"], 4), P_PASS_amended_rule=R(v["P_PASS_amended_rule"], 4),
                                sd_w3000=v["sd_w3000"], sd_w5700=v["sd_w5700"], bias_w3000=R(v["bias_w3000"]), bias_w5700=R(v["bias_w5700"]))
                        for k, v in a["p_pass"].items()}
        y["arms"][arm] = ya
    y["noise_model"] = {k: {kk: R(vv) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in out["noise"].items()}
    y["n_300s_bin_centers"] = out["arms"]["CUT-A"]["seeds"][0]["N_300s_bins"]["t"]
    with open(os.path.join(ROOT, "configs/icml_cut_predict.yaml"), "w", newline="\n") as f:
        f.write("# Frozen model-F predictions for the arrival-cut test of Corollary 3 (tag icml-cut-pred).\n"
                "# Generated by: PYTHONPATH=\"src;.\" python -m analysis.theory.icml.cut_predict ; see notes/PREDICTIONS_icml_cut.md\n")
        yaml.safe_dump(y, f, sort_keys=False, width=140, default_flow_style=None)


NOISE_SCENARIOS = {               # (sd over [3000, 8700), sd over [5700, 8700)) of measured minus the per-seed theory
    "fitted": None,                 # the committed-run residual sd (6 runs; the cut regime is not covered by them)
    "sd_0.002": (0.002, 0.003),
    "sd_0.004": (0.004, 0.006),
}


def p_pass_grid(arm: str, arm_out: Dict[str, object], noise: Dict[str, Dict[str, float]], mc: int,
                rng: np.random.Generator) -> Dict[str, object]:
    """Monte Carlo of the decision rules.  measured_w = theory_w(seed) + bias_w + e_w, e ~ N(0, sd_w) (corr 0.7 between the two
    windows); the naive uses that run's own completion rate over [1800, 2400) = the control's measured value + replicate noise
    (Poisson sd on the count: conservative).  Rules: LEAD = theory-favoured over [3000, 8700) in >= 2/3 seeds (and, for CUT-A,
    slope > 0 over [3000, 8700) in >= 2/3); AMENDED = the same but the CUT-A sign condition uses [5700, 8700)."""
    res: Dict[str, object] = {}
    seeds = sorted(arm_out["seeds"])
    for name, sc in NOISE_SCENARIOS.items():
        for biased in (True, False):
            sd3, sd57 = (noise["w3000"]["sd"], noise["w5700"]["sd"]) if sc is None else sc
            b3, b57 = (noise["w3000"]["mean"], noise["w5700"]["mean"]) if biased else (0.0, 0.0)
            fav = np.zeros((mc, len(seeds)), bool)
            pos3 = np.zeros_like(fav)
            pos57 = np.zeros_like(fav)
            per = {}
            for j, seed in enumerate(seeds):
                sd = arm_out["seeds"][seed]
                z1 = rng.standard_normal(mc)
                z2 = 0.7 * z1 + math.sqrt(1 - 0.49) * rng.standard_normal(mc)
                m3 = sd["w3000"]["theory_slope"] + b3 + sd3 * z1
                m57 = sd["w5700"]["theory_slope"] + b57 + sd57 * z2
                n_pre = sd["pre_cut_completion_control_meas"] * (PRE_CUT[1] - PRE_CUT[0])
                pre = sd["pre_cut_completion_control_meas"] + rng.normal(0.0, math.sqrt(max(n_pre, 1.0)) / (PRE_CUT[1] - PRE_CUT[0]), mc)
                naive = sd["w3000"]["lam_plan"] - pre
                fav[:, j] = np.abs(m3 - sd["w3000"]["theory_slope"]) < np.abs(m3 - naive)
                pos3[:, j] = m3 > 0
                pos57[:, j] = m57 > 0
                per[seed] = dict(favoured=float(fav[:, j].mean()), slope_w3000_pos=float(pos3[:, j].mean()),
                                 slope_w5700_pos=float(pos57[:, j].mean()))
            f2 = fav.sum(1) >= 2
            if arm == "CUT-A":
                lead = float((f2 & (pos3.sum(1) >= 2)).mean())
                amended = float((f2 & (pos57.sum(1) >= 2)).mean())
            else:
                lead = amended = float(f2.mean())
            res[f"{name}{'' if biased else '_nobias'}"] = dict(sd_w3000=sd3, sd_w5700=sd57, bias_w3000=b3, bias_w5700=b57,
                                                              P_PASS_lead_rule=lead, P_PASS_amended_rule=amended,
                                                              P_two_of_three_favoured=float(f2.mean()), per_seed=per)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=200000)
    args = ap.parse_args(argv)
    lr = lam_ref()
    m, _ = cell_model(CELL)
    tc = trap_costs(m)
    cs = summarize_curve(m)
    lam0 = BASE_MULT * lr
    n1 = float(open_equilibria(cs, lam0).n1)
    n_b = float(cs.n_b)
    zbar = 5.0
    lat_good = (n1 / lam0 - (tc.ET - 1.0) * zbar) / tc.ET
    a0 = trap_asymptotics(lam0, tc)
    out: Dict[str, object] = dict(
        tag="icml-cut-pred", theory="notes/THEORY_ICML_2026-11.md (Theorem 1(a), Theorem 2, Corollary 3); model F unchanged",
        cell=CELL, lambda_ref=lr, lambda_miss_model=tc.lam_miss, n_b=n_b, n1_good_at_1p65=n1, lat_good_s=lat_good,
        base=dict(mult=BASE_MULT, lam=lam0, rho=a0["rho"], D_over_lam_ref=a0["D"] / lr, alpha=a0["alpha"]),
        arms={})

    # ---- plans (and the pre-cut identity with the committed 1.65x BURST controls)
    plans = {}
    plan_dir = os.path.join(ROOT, "results/theory/icml/cut_plans")
    os.makedirs(plan_dir, exist_ok=True)
    for arm, mult in ARMS.items():
        for seed in SEEDS:
            plan, _ = build_cut_plan(seed, mult)
            plans[(arm, seed)] = plan
            txt = plan_csv(plan)
            with open(os.path.join(plan_dir, f"{arm}_seed{seed}.csv"), "w", newline="\n") as f:
                f.write(txt)
    identity = {}
    for seed in SEEDS:
        ctrl = read_plan_csv(os.path.join(ROOT, CONTROL_DIRS[seed], "plan.csv"))
        ctrl_pre = [r for r in ctrl if r[2] < T_CUT]
        res = {}
        for arm in ARMS:
            mine = [(p.origin, p.idx, p.arrival_s, p.n_turns, float(sum(p.tool_times_s))) for p in plans[(arm, seed)]]
            mine_pre = [r for r in mine if r[2] < T_CUT]
            same = len(mine_pre) == len(ctrl_pre) and all(
                a[0] == b[0] and a[1] == b[1] and a[2] == b[2] and a[3] == b[3] and abs(a[4] - b[4]) <= 1e-9 * max(1.0, abs(b[4]))
                for a, b in zip(mine_pre, ctrl_pre))
            res[arm] = dict(pre_cut_sessions=len(mine_pre), identical_to_control=bool(same))
        identity[seed] = res
    out["pre_cut_identity_with_controls"] = identity

    # ---- noise model: measured minus model F (plan-driven) on committed BURST runs of this cell
    resid = []
    for r in committed_burst_runs():
        d = os.path.join(ROOT, r["run_dir"])
        st57 = ms.window_stats(d, 5700.0, 8700.0)
        if st57["fu_hit"] >= 0.2:
            continue
        plan, cfg = build_plan_from_run(d)
        ctrl = read_plan_csv(os.path.join(d, "plan.csv"))
        mine = [(p.origin, p.idx, p.arrival_s, p.n_turns) for p in plan]
        plan_ok = len(mine) == len(ctrl) and all(a[:4] == b[:4] for a, b in zip(mine, ctrl))
        lam = float(cfg.arrivals.rate_mult) * lr
        n1r = float(open_equilibria(cs, lam).n1) if lam > 0 else 0.0
        latr = (n1r / lam - (tc.ET - 1.0) * zbar) / tc.ET
        pf = plan_fifo(plan, tc, latr)
        row = dict(run_dir=r["run_dir"], mult=float(cfg.arrivals.rate_mult), seed=int(cfg.run.seed), plan_ok=bool(plan_ok),
                   fu_hit_w5700=st57["fu_hit"], P_served_w5700_meas=st57["P_served_mean"],
                   P_served_w5700_model=served_stats(pf, tc, 5700.0, T_END)["P_served_mean"],
                   gap_median_w5700_meas=st57["gap_median"], gap_med_slope_w5700_meas=st57["gap_med_slope"],
                   gap_median_w5700_model=served_stats(pf, tc, 5700.0, T_END)["gap_median"],
                   gap_med_slope_w5700_model=served_stats(pf, tc, 5700.0, T_END)["gap_med_slope"])
        for wk, (t0, t1) in WINDOWS.items():
            mw = ms.window_stats(d, t0, t1)
            pw = backlog_stats(pf["starts"], pf["ends"], t0, t1)
            row[wk] = dict(meas_slope=mw["backlog_slope"], model_slope=pw["slope"], resid=mw["backlog_slope"] - pw["slope"],
                           meas_completion=mw["completion_rate"], model_completion=pw["completion_rate"])
        pre = ms.window_stats(d, *PRE_CUT, t_burst=None)
        row["pre_cut_completion_meas"] = pre["completion_rate"]
        row["pre_cut_completion_model"] = backlog_stats(pf["starts"], pf["ends"], *PRE_CUT)["completion_rate"]
        resid.append(row)
    out["committed_runs_noise_model"] = resid
    res_w = {wk: np.array([r[wk]["resid"] for r in resid if r["plan_ok"]]) for wk in WINDOWS}
    out["noise"] = {wk: dict(n=int(len(v)), mean=float(v.mean()), sd=float(v.std(ddof=1)), rms=float(np.sqrt((v ** 2).mean())))
                    for wk, v in res_w.items()}
    pre_resid = np.array([r["pre_cut_completion_meas"] - r["pre_cut_completion_model"] for r in resid if r["plan_ok"]])
    out["noise"]["pre_cut_completion"] = dict(n=int(len(pre_resid)), mean=float(pre_resid.mean()), sd=float(pre_resid.std(ddof=1)))

    # ---- predictions per arm and seed
    rng = np.random.default_rng(20261105)
    for arm, mult in ARMS.items():
        lam1 = mult * lr
        tr = fifo_fluid(lam0, tc, n1, lam_after=[(T_CUT, lam1)])
        a1 = trap_asymptotics(lam1, tc) if lam1 > tc.lam_miss * 1.0001 else None
        i_cut = int(np.searchsorted(tr["t"], T_CUT))
        vtot_cut = float(tr["Vtot"][i_cut])
        fl = {wk: fluid_window_stats(tr, t0, t1, tc) for wk, (t0, t1) in WINDOWS.items()}
        arm_out: Dict[str, object] = dict(
            mult_after=mult, lam_after=lam1, rho_after=lam1 / tc.lam_miss,
            asymptotics_after=(None if a1 is None else dict(z=a1["z"], gamma=a1["gamma"], alpha=a1["alpha"], D=a1["D"],
                                                            D_over_lam_ref=a1["D"] / lr)),
            fluid=dict(
                slope={wk: fl[wk]["slope"] for wk in WINDOWS},
                completion_rate_w5700=fl["w5700"]["completion_rate"], completion_over_lam_ref_w5700=fl["w5700"]["completion_rate"] / lr,
                N_at_cut=float(tr["N"][i_cut]), N_8700=float(tr["N"][-1]), V_at_cut=float(tr["V"][i_cut]), V_8700=float(tr["V"][-1]),
                Vtot_at_cut=vtot_cut, V_slope_w5700=fl["w5700"]["V_slope"], P_served_w5700=fl["w5700"]["P_served_mean"],
                dip=fluid_dip(tr),
                clear_time_s=(T_CUT + busy_period(vtot_cut, lam1, tc)) if lam1 < tc.lam_miss else math.inf),
            seeds={})
        for seed in SEEDS:
            plan = plans[(arm, seed)]
            pf = plan_fifo(plan, tc, lat_good)
            starts = pf["starts"]
            sd: Dict[str, object] = {}
            for wk, (t0, t1) in WINDOWS.items():
                pw = backlog_stats(starts, pf["ends"], t0, t1)
                lam_plan = float(((starts >= t0) & (starts < t1)).sum() / (t1 - t0))
                sd[wk] = dict(lam_plan=lam_plan, theory_slope=pw["slope"], theory_completion=pw["completion_rate"],
                              N_start=pw["N_start"], N_end=pw["N_end"])
            pre = backlog_stats(starts, pf["ends"], *PRE_CUT)
            ctrl_pre = ms.window_stats(os.path.join(ROOT, CONTROL_DIRS[seed]), *PRE_CUT, t_burst=None)["completion_rate"]
            sd["pre_cut_completion_model"] = pre["completion_rate"]
            sd["pre_cut_completion_control_meas"] = ctrl_pre
            for wk in WINDOWS:
                sd[wk]["naive_expected"] = sd[wk]["lam_plan"] - ctrl_pre
            sd["served_w5700"] = served_stats(pf, tc, 5700.0, T_END)
            sd["plan_sha256"] = hashlib.sha256(plan_csv(plan).encode()).hexdigest()
            sd["plan_sessions"] = dict(total=len(plan), burst=sum(1 for p in plan if p.origin == "burst"),
                                       base_before_cut=sum(1 for p in plan if p.origin == "base" and p.arrival_s < T_CUT),
                                       base_after_cut=sum(1 for p in plan if p.origin == "base" and p.arrival_s >= T_CUT))
            sd["dip"] = dip(starts, pf["ends"])
            c, nser = n_series(starts, pf["ends"], T_B, T_END, 300.0)
            sd["N_300s_bins"] = dict(t=[R(x, 1) for x in c], N=[R(x, 2) for x in nser])
            sd["N_below_n_b_before_8700"] = bool(nser.min() < n_b) if len(nser) else False
            arm_out["seeds"][seed] = sd

        spread = {wk: [] for wk in WINDOWS}             # the per-plan spread around the fluid (seeds 0-39): why the plug-in is per seed
        for sp_seed in range(40):
            plan_sp, _ = build_cut_plan(sp_seed, mult)
            pf_sp = plan_fifo(plan_sp, tc, lat_good)
            for wk, (t0, t1) in WINDOWS.items():
                spread[wk].append(backlog_stats(pf_sp["starts"], pf_sp["ends"], t0, t1)["slope"])
        arm_out["plan_spread_seeds_0_39"] = {wk: dict(mean=float(np.mean(v)), sd=float(np.std(v, ddof=1)),
                                                      frac_positive=float(np.mean(np.array(v) > 0))) for wk, v in spread.items()}
        arm_out["p_pass"] = p_pass_grid(arm, arm_out, out["noise"], args.mc, rng)
        out["arms"][arm] = arm_out

    write_yaml(out)
    os.makedirs(os.path.join(ROOT, "results/theory/icml"), exist_ok=True)
    with open(os.path.join(ROOT, "results/theory/icml/cut_predictions.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k not in ("committed_runs_noise_model",)}, indent=1, default=float)[:20000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
