"""Driver: validation on the measured cells and out-of-sample predictions of the Che endogenous-gap model.

Run from the worktree root:
    PYTHONPATH="src;." python -m analysis.theory.che_endogenous.run_che [--quick] [--out results/theory/che_endogenous]

Writes validation.json, predictions.json, curves_<cell>.csv, scaling.csv, meta.json under --out, and figures under
figures/theory/ (che_*.png).  Deterministic (fixed seeds).  No input is read from any result directory: the measured
targets are typed in measured.py with their sources, and only the INPUTS listed there are used by the model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import replace, asdict
from typing import Dict, List, Sequence

import numpy as np

from .model import CheModel, Cell, Costs, Workload, calibrate_scale, default_cells
from .open_system import (mean_field_curve, smoothed_curve, landmarks, crossings, good_state_S, escape_mc,
                          e0b_unstable_prob, burst_trap_path, window_stats, rescue_prediction, critical_burst_det,
                          closed_trap_transient, capped_drain_from_t0)
from .measured import MEASURED, H200_E0A

ETA = 0.10                     # unpinned share when admission blocks (engine behaviour; sensitivity reported)
GRID_STD = [16, 20, 24, 28, 32, 40, 48, 96, 300]
MULTS_STD = [1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]


def n_grid(M: float) -> List[float]:
    """Fine population grid scaled with the pool (step 0.5 below the cliff region of a 300k pool, coarser beyond)."""
    s = M / 300_000.0
    top = 42.0 * s
    step = max(0.5, round(0.5 * s * 2) / 2)
    g = list(np.arange(2.0, top, step))
    g += [top, 48.0 * s, 64.0 * s, 96.0 * s, 150.0 * s, 300.0]
    return sorted(set(float(round(x, 3)) for x in g if x <= 300.0))


def edge50(mults: Sequence[float], p_uns: Sequence[float]) -> float:
    """Multiple at which the predicted probability of an unstable 3000 s run crosses 1/2 (linear interpolation)."""
    for i in range(len(mults) - 1):
        if p_uns[i] < 0.5 <= p_uns[i + 1]:
            return float(mults[i] + (mults[i + 1] - mults[i]) * (0.5 - p_uns[i]) / (p_uns[i + 1] - p_uns[i]))
    return float("nan") if p_uns[-1] < 0.5 else float(mults[0])


def good_gap_over_R(model: CheModel, rows, lam: float) -> Dict:
    """Good open state at lam: median follow-up gap (Z + latency) and R = M / churn as the frozen loopvars script defines them."""
    wl = model.wl
    S = good_state_S(model, rows, lam)
    gap_med = wl.z_mean * math.log(2.0) + S
    tok_per_session = wl.L0 + wl.hit_new * (wl.ET - 1.0) + wl.decode * wl.ET
    churn = lam * tok_per_session
    R = model.cell.M / churn
    return dict(S_good=S, gap_med=gap_med, churn=churn, R=R, gap_over_R=gap_med / R)


def analyse_cell(name: str, model: CheModel, lam_ref: float, mults: Sequence[float], e2_points: Sequence[float],
                 grid_ns: Sequence[float], n_rep: int, smooth_nodes: int, seed: int = 0, cap: int = 0) -> Dict:
    t0 = time.time()
    M = model.cell.M
    ns = n_grid(M)
    mf = mean_field_curve(model, ns)
    sgrid = sorted(set([float(x) for x in grid_ns] + [float(x) for x in np.arange(max(4, 0.3 * M / 10_500), 1.35 * M / 10_500, max(1.0, M / 300_000))]))
    sm = smoothed_curve(model, sgrid, nodes=smooth_nodes)
    lm_mf = landmarks(mf, grid_ns=grid_ns)
    lm_sm = landmarks(sm, grid_ns=[n for n in grid_ns if n <= max(sgrid)])
    ref = model.allmiss_reference(32)
    lam_miss_model = ref["lambda_miss_turns"]
    # from-empty edge
    e0b = []
    for i, mlt in enumerate(mults):
        r = e0b_unstable_prob(model, mf, mlt * lam_ref, lam_miss_model, n_rep=n_rep, seed=seed + i)
        r["mult"] = mlt
        e0b.append(r)
    e50 = edge50([r["mult"] for r in e0b], [r["p_unstable"] for r in e0b])
    # trapped state after the registered 200-session burst
    trap = {}
    for mlt in e2_points:
        lam = mlt * lam_ref
        p = burst_trap_path(model, mf, lam, 200, t_b=1200.0, t_end=8700.0)
        ws = window_stats(p, 5700.0, 8700.0, ref["tokens_per_s"])
        ws["good_state"] = good_gap_over_R(model, mf, lam)
        ws["critical_burst_det"] = critical_burst_det(model, mf, lam)
        # cap of the CAPPED arm: the registered one for measured cells, else the model's own cap rule on the grid
        cap_used = cap or int(lm_sm.get("n_cap_smallest_within_5pct") or lm_mf.get("n_cap_smallest_within_5pct"))
        ws["capped_static_drain"] = capped_drain_from_t0(model, mf, lam, cap=cap_used)
        trap[str(mlt)] = ws
    # Stage C protocol (synchronized start) in the trapped regime: the measured mu(n) at large n is a transient
    sync = {str(n): closed_trap_transient(model, int(n)) for n in grid_ns if n >= 1.4 * M / 10_500}
    out = dict(cell=name, M=M, eta=model.cell.eta, costs=asdict(model.cell.costs), lambda_ref_used=lam_ref,
               synchronized_start_trapped=sync,
               e0a_model=ref, mean_field=dict(landmarks=lm_mf, n_fixed_points_max=max(r["n_fixed_points"] for r in mf),
                                              window_mu_max_over_lmiss_model=lm_mf["mu_max"] / lam_miss_model,
                                              window_mu_max_over_lref=lm_mf["mu_max"] / lam_ref),
               smoothed=dict(landmarks=lm_sm, window_mu_max_over_lmiss_model=lm_sm["mu_max"] / lam_miss_model,
                             window_mu_max_over_lref=lm_sm["mu_max"] / lam_ref),
               e0b=e0b, edge50_mult=e50, trap=trap, seconds=time.time() - t0)
    return out, mf, sm


def write_curve_csv(path: str, mf, sm):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "n", "mu", "hit_all", "h_followup", "regime", "R_s", "W_s", "B", "S_s", "churn_tok_s",
                    "R_loopvars_s", "n_fixed_points"])
        for r in mf:
            w.writerow(["mean_field", r["n"], r["mu"], r["hit_all"], r["h"], r["regime"], r["R"], r["W"], r["B"], r["S"],
                        r["churn"], r["R_loopvars"], r["n_fixed_points"]])
        for r in sm:
            w.writerow(["smoothed", r["n"], r["mu"], r["hit_all"], "", "", "", "", "", "", "", "", ""])


def compare_cell(name: str, res: Dict, meas: Dict) -> Dict:
    """Predicted vs measured table for one validation cell."""
    lm_mf, lm_sm = res["mean_field"]["landmarks"], res["smoothed"]["landmarks"]
    rows = {}
    rows["lambda_miss_turns"] = dict(pred=res["e0a_model"]["lambda_miss_turns"], meas=meas["lambda_miss_turns"])
    rows["allmiss_tok_s"] = dict(pred=res["e0a_model"]["tokens_per_s"], meas=meas["allmiss_tok_s"])
    rows["peak_n"] = dict(pred_mean_field=lm_mf["peak_n"], pred_smoothed=lm_sm["peak_n"], meas=meas["peak_n"])
    rows["mu_max"] = dict(pred_mean_field=lm_mf["mu_max"], pred_smoothed=lm_sm["mu_max"], meas=meas["mu_max"])
    rows["hit_cross_0p5"] = dict(pred_mean_field=lm_mf["hit_cross_0p5"], pred_smoothed=lm_sm["hit_cross_0p5"], meas=meas["hit_cross"])
    rows["mu_large_n"] = dict(pred=lm_mf["mu_at_big_n"], meas_mu300=meas["curve"][300][0],
                              meas_note="measured mu(300) is a synchronized-start transient; compare with lambda_miss")
    lam_ref = meas["lambda_ref"]
    rows["window_mu_max_over_lambda_miss"] = dict(pred_mean_field=lm_mf["mu_max"] / res["e0a_model"]["lambda_miss_turns"],
                                                  pred_smoothed=lm_sm["mu_max"] / res["e0a_model"]["lambda_miss_turns"],
                                                  meas=meas["mu_max"] / meas["lambda_miss_turns"])
    stab = meas["e0b"]
    last_stable = max(m for m, s in stab.items() if s)
    first_unst = min((m for m, s in stab.items() if not s), default=float("nan"))
    rows["from_empty_edge"] = dict(pred_edge50_mult=res["edge50_mult"], meas_bracket=(last_stable, first_unst),
                                   pred_p_unstable={str(r["mult"]): r["p_unstable"] for r in res["e0b"]})
    # curve point by point
    pts = {}
    for n, (mu, mu_t, hit) in meas["curve"].items():
        pm = lm_mf.get("grid_mu", {}).get(float(n))
        ps = lm_sm.get("grid_mu", {}).get(float(n))
        pts[str(n)] = dict(meas_mu=mu, meas_mu_turns=mu_t, meas_hit=hit, pred_mf_mu=pm, pred_sm_mu=ps)
    rows["curve_points"] = pts
    # trapped state
    tr = {}
    for mlt, ws in res["trap"].items():
        mm = meas["e2_burst"].get(float(mlt), {})
        lv = meas.get("loopvars", {}).get(float(mlt), {})
        tr[mlt] = dict(pred_backlog=ws["backlog_mean"], meas_backlog=mm.get("backlog"),
                       pred_token_ratio=ws["token_ratio"], meas_token_ratio=mm.get("ratio"),
                       pred_rate_sessions=ws["rate_sessions"], meas_rate_sessions=mm.get("rate"),
                       pred_slope=ws["backlog_slope"], meas_slope=mm.get("slope"),
                       pred_min_after=ws["backlog_min_after"], meas_min_after=mm.get("min_after"),
                       pred_t_min_after_burst=ws["t_min_after"] - 1200.0, meas_t_min_after_burst=mm.get("t_min_after"),
                       pred_gap_over_R_trapped=ws["gap_over_R_mid"], meas_gap_over_R_trapped=lv.get("burst_gap_over_R"),
                       pred_R_trapped=ws["round_s_mid"] / ws["gap_over_R_mid"], meas_R_trapped=lv.get("burst_R"),
                       pred_gap_over_R_good=ws["good_state"]["gap_over_R"], meas_gap_over_R_good=lv.get("good_gap_over_R"),
                       pred_R_good=ws["good_state"]["R"], meas_R_good=lv.get("good_R"),
                       critical_burst_det=ws["critical_burst_det"]["b_crit"],
                       pred_capped_drain_s=ws["capped_static_drain"]["drain_s"], meas_capped_drain_s=mm.get("capped_drain"))
    rows["trapped_state"] = tr
    sy = {}
    for n, r in res.get("synchronized_start_trapped", {}).items():
        mc = meas["curve"].get(int(float(n)))
        sy[n] = dict(pred_mu_sessions=r["mu_sessions"], pred_mu_turns_based=r["mu_turns_based"],
                     meas_mu_sessions=mc[0] if mc else None, meas_mu_turns_based=mc[1] if mc else None)
    rows["large_n_synchronized_start"] = sy
    return rows


# ------------------------------------------------------------------------------------------------------ prediction cells

def h200_cells(eta: float):
    base = Costs()
    c0 = Cell("h200_300k", M=300_000.0, costs=base, eta=eta)
    cA, sA = calibrate_scale(c0, H200_E0A["allmiss_tok_s"])          # uniform speed-up fitted to the H200 E0a token rate
    # variant B: memory-bound terms (iteration overhead, decode attention) scaled by the HBM bandwidth ratio of the
    # spec sheets (A100 80GB PCIe 1.935 TB/s, H200 NVL 4.8 TB/s), compute terms fitted to the E0a token rate
    bw = 1.935 / 4.8
    lo, hi = 0.05, 1.0
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        cc = replace(base, iter_fixed=base.iter_fixed * bw, iter_floor=base.iter_floor * bw, decode_attn=base.decode_attn * bw,
                     per_token=base.per_token * mid, prefill_attn=base.prefill_attn * mid)
        tok = CheModel(replace(c0, costs=cc)).allmiss_reference(32)["tokens_per_s"]
        if tok > H200_E0A["allmiss_tok_s"]:
            lo = mid
        else:
            hi = mid
    sc = math.sqrt(lo * hi)
    cB = replace(c0, name="h200_300k_bwsplit", costs=replace(base, iter_fixed=base.iter_fixed * bw, iter_floor=base.iter_floor * bw,
                                                         decode_attn=base.decode_attn * bw, per_token=base.per_token * sc,
                                                         prefill_attn=base.prefill_attn * sc))
    return cA, sA, cB, sc


def llama_cell(eta: float):
    """Llama-3.1-8B on the A100, 300k pool: the calibrated Qwen2.5-7B costs scaled by architecture ratios (uncalibrated).

    Qwen2.5-7B: 28 layers, 28 query / 4 KV heads, head dim 128, 6.53B non-embedding, 15.2 GB of bf16 weights.
    Llama-3.1-8B: 32 layers, 32 query / 8 KV heads, head dim 128, 6.98B non-embedding, 16.1 GB.
      per-token prefill/decode linear work  x 6.98/6.53 = 1.069
      prefill attention per (query, key) pair x (32*32)/(28*28) = 1.306
      decode attention per context token (KV bytes) x (32*8)/(28*4) = 2.286
      iteration fixed cost (weight reads)  x 16.06/15.23 = 1.054
    """
    base = Costs()
    c = replace(base, per_token=base.per_token * (6.98 / 6.53), prefill_attn=base.prefill_attn * (32 * 32) / (28 * 28),
                decode_attn=base.decode_attn * (32 * 8) / (28 * 4), iter_fixed=base.iter_fixed * (16.06 / 15.23),
                iter_floor=base.iter_floor * (16.06 / 15.23))
    return Cell("llama31_8b_300k", M=300_000.0, costs=c, eta=eta)


def predict_cell(name: str, cell: Cell, lam_ref: float, mults, grid_ns, n_rep: int, smooth_nodes: int, e2_points=()):
    model = CheModel(cell)
    res, mf, sm = analyse_cell(name, model, lam_ref, mults, e2_points, grid_ns, n_rep, smooth_nodes)
    lm = res["smoothed"]["landmarks"]
    lmiss = res["e0a_model"]["lambda_miss_turns"]
    # registration consequences under the registered rules (cap = smallest grid n within 5% of the peak; hi = largest
    # all-stable E0b multiple capped by mu_max / lambda_ref; points at 1/3 and 2/3 of (1, hi), rounded to 0.05)
    p_uns = {r["mult"]: r["p_unstable"] for r in res["e0b"]}
    hi_pred = max([m for m in sorted(p_uns) if all(p_uns[x] < 0.5 for x in sorted(p_uns) if x <= m)] or [float("nan")])
    hi_cap = min(hi_pred, lm["mu_max"] / lam_ref) if math.isfinite(hi_pred) else float("nan")
    pts = None
    if math.isfinite(hi_cap) and hi_cap > 1.0:
        pts = (round((1 + (hi_cap - 1) / 3) / 0.05) * 0.05, round((1 + 2 * (hi_cap - 1) / 3) / 0.05) * 0.05)
    res["registration_consequence"] = dict(hi_mult_pred=hi_pred, hi_capped=hi_cap, lambda_points=pts,
                                           n_cap_smoothed=lm.get("n_cap_smallest_within_5pct"),
                                           n_cap_mean_field=res["mean_field"]["landmarks"].get("n_cap_smallest_within_5pct"),
                                           window_width_mult=(hi_cap - 1.0) if math.isfinite(hi_cap) else float("nan"))
    return res, mf, sm


# ---------------------------------------------------------------------------------------------------------- scaling law

def scaling_table(eta: float, quick: bool) -> List[Dict]:
    rows = []
    Ms = [75_000, 150_000, 300_000, 600_000, 955_757, 1_500_000] if not quick else [150_000, 300_000, 600_000]
    speeds = [1.0, 0.5, 1 / 2.66, 0.25] if not quick else [1.0, 1 / 2.66]
    zs = [1.0, 2.0, 5.0, 10.0] if not quick else [5.0]
    for M in Ms:
        for s in speeds:
            for z in zs:
                cell = Cell(f"M{M}_s{s:.3f}_z{z}", M=float(M), costs=Costs().scaled(s), wl=Workload(z_mean=z), eta=eta)
                m = CheModel(cell)
                ns = n_grid(M)
                mf = mean_field_curve(m, ns)
                lm = landmarks(mf)
                ref = m.allmiss_reference(32)
                # closed-form approximation: window ~ theta * M * tau_miss / (E_lb (zbar' + S_hit))
                g = m.good_branch(lm["peak_n"])
                m1, _ = m.wl.lb_moments(g["S"])
                tau_miss = 1.0 / ref["nu"]
                approx_mem = M * tau_miss / (m1 * (m.wl.zbar_turn + g["S"]))
                nu_hit = 1.0 / (m.tauP_mean(1.0) + m.cell.decode_iters * m.cell.costs.decode_coeffs(1e9, m.cbar_dec)[1])
                approx_cmp = nu_hit * tau_miss
                rows.append(dict(M=M, speed=s, z_mean=z, lambda_miss=ref["lambda_miss_turns"], mu_max=lm["mu_max"], peak_n=lm["peak_n"],
                                 hit_cross=lm["hit_cross_0p5"], window=lm["mu_max"] / ref["lambda_miss_turns"],
                                 approx_mem_bound=approx_mem, approx_compute_bound=approx_cmp,
                                 n_peak_over_M_over_Elb=lm["peak_n"] * m1 / M))
    return rows


# ------------------------------------------------------------------------------------------------------------- figures

def make_figures(val: Dict, curves: Dict, preds: Dict, scal: List[Dict], figdir: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(figdir, exist_ok=True)
    # 1. closed curves
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, cell in zip(axs, ["a100_300k", "a100_native", "vllm_300k"]):
        mf, sm = curves[cell]
        meas = MEASURED[cell]["curve"]
        ax.plot([r["n"] for r in mf], [r["mu"] for r in mf], "-", color="#888", lw=1.2, label="mean field")
        ax.plot([r["n"] for r in sm], [r["mu"] for r in sm], "-", color="#1f5fa8", lw=2, label="mean field + live-KV fluctuation")
        ax.plot(list(meas), [v[0] for v in meas.values()], "o", color="#c0392b", label="measured (sessions/s)")
        sy = val[cell].get("synchronized_start_trapped", {})
        if sy:
            ax.plot([float(n) for n in sy], [v["mu_sessions"] for v in sy.values()], "D", mfc="none", color="#1f5fa8",
                    label="model, synchronized-start window [900, 2700) s")
        ax.axhline(MEASURED[cell]["lambda_miss_turns"], color="#c0392b", ls=":", lw=1)
        ax.set_xscale("log")
        ax.set_title(cell)
        ax.set_xlabel("closed population n")
        ax.set_ylabel("mu(n), sessions/s")
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "che_closed_curves.png"), dpi=150)
    plt.close(fig)
    # 2. from-empty instability probability
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, cell in zip(axs, ["a100_300k", "a100_native", "vllm_300k"]):
        e = val[cell]["e0b"]
        ax.plot([r["mult"] for r in e], [r["p_unstable"] for r in e], "-o", color="#1f5fa8", ms=3, label="P(unstable 3000 s run), model")
        for mlt, st in MEASURED[cell]["e0b"].items():
            ax.plot([mlt], [0.0 if st else 1.0], "s", color="#c0392b", ms=6)
        ax.set_title(cell)
        ax.set_xlabel("arrival rate / lambda_ref")
        ax.set_ylim(-0.05, 1.05)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "che_from_empty_edge.png"), dpi=150)
    plt.close(fig)
    # 3. window scaling
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for s in sorted(set(r["speed"] for r in scal)):
        rr = [r for r in scal if r["speed"] == s and r["z_mean"] == 5.0]
        ax.plot([r["M"] for r in rr], [r["window"] for r in rr], "-o", ms=3, label=f"speed x{1 / s:.2f}")
    ax.set_xscale("log")
    ax.set_xlabel("KV pool M (tokens)")
    ax.set_ylabel("mu_max / lambda_miss")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "che_window_scaling.png"), dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------------------ main

def sha256_files(paths):
    out = {}
    for p in paths:
        with open(p, "rb") as f:
            out[p] = hashlib.sha256(f.read()).hexdigest()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/theory/che_endogenous")
    ap.add_argument("--figdir", default="figures/theory")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="", help="comma list: validation,predictions,scaling,bursts,rescue,sensitivity")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    n_rep = 120 if a.quick else 400
    nodes = 7 if a.quick else 11
    todo = set(x for x in a.only.split(",") if x) or {"validation", "predictions", "scaling", "bursts", "rescue", "sensitivity"}
    t_start = time.time()
    cells = default_cells()
    val, curves = {}, {}
    # ---------------------------------------------------------------- validation
    vcells = {"a100_300k": replace(cells["a100_300k"], eta=ETA), "a100_native": replace(cells["a100_native"], eta=ETA)}
    cv, s_vllm = calibrate_scale(replace(cells["vllm_300k"], eta=ETA), MEASURED["vllm_300k"]["allmiss_tok_s"])
    vcells["vllm_300k"] = cv
    grids = {"a100_300k": [16, 20, 24, 32, 48, 96, 300], "a100_native": [24, 48, 64, 80, 96, 128, 300],
             "vllm_300k": [16, 20, 24, 28, 32, 40, 48, 96, 300]}
    mults = {"a100_300k": MULTS_STD, "a100_native": [1.5, 2.5, 3.5, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5],
             "vllm_300k": MULTS_STD}
    if "validation" in todo:
        for name, cell in vcells.items():
            meas = MEASURED[name]
            res, mf, sm = analyse_cell(name, CheModel(cell), meas["lambda_ref"], mults[name], meas["e2_points"], grids[name],
                                       n_rep, nodes, cap={"a100_300k": 20, "a100_native": 64, "vllm_300k": 20}[name])
            if name == "vllm_300k":
                res["scale_fitted_to_vllm_e0a"] = s_vllm
            res["comparison"] = compare_cell(name, res, meas)
            val[name] = res
            curves[name] = (mf, sm)
            write_curve_csv(os.path.join(a.out, f"curves_{name}.csv"), mf, sm)
            print(f"[validation] {name} done in {res['seconds']:.0f} s", flush=True)
        with open(os.path.join(a.out, "validation.json"), "w") as f:
            json.dump(val, f, indent=1, default=float)
    # ---------------------------------------------------------------- sensitivity to eta (validation cells)
    if "sensitivity" in todo:
        sens = {}
        for eta in (0.03, 0.10, 0.25):
            for name in ("a100_300k", "a100_native"):
                m = CheModel(replace(vcells[name], eta=eta))
                mf = mean_field_curve(m, n_grid(m.cell.M))
                lm = landmarks(mf)
                sens[f"{name}_eta{eta}"] = dict(landmarks=lm, B_mem=m.B_mem, n_fixed_points_max=max(r["n_fixed_points"] for r in mf),
                                                trap_R_che=mf[-1]["R"], trap_W_n300=mf[-1]["W"])
        with open(os.path.join(a.out, "sensitivity_eta.json"), "w") as f:
            json.dump(sens, f, indent=1, default=float)
        print("[sensitivity] done", flush=True)
    # ---------------------------------------------------------------- predictions
    preds = {}
    if "predictions" in todo:
        cA, sA, cB, sB = h200_cells(ETA)
        for nm, cc, extra in (("h200_300k", cA, dict(scale=sA, variant="uniform speed-up fitted to H200 E0a")),
                              ("h200_300k_bwsplit", cB, dict(compute_scale=sB, variant="HBM-bandwidth ratio on memory-bound terms, compute fitted"))):
            res, mf, sm = predict_cell(nm, cc, H200_E0A["lambda_miss_turns"], [1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 1.75, 2.0, 2.25, 2.5, 3.0],
                                       GRID_STD, n_rep, nodes, e2_points=(1.35,))
            res.update(extra)
            preds[nm] = res
            write_curve_csv(os.path.join(a.out, f"curves_{nm}.csv"), mf, sm)
            print(f"[pred] {nm} done", flush=True)
        cl = llama_cell(ETA)
        ml = CheModel(cl)
        lref_l = ml.allmiss_reference(32)["lambda_miss_turns"]
        res, mf, sm = predict_cell("llama31_8b_300k", cl, lref_l, MULTS_STD, GRID_STD, n_rep, nodes, e2_points=(1.35, 1.65))
        res["lambda_ref_note"] = "multiples of the MODEL's own lambda_miss (the cell's E0a is not known)"
        preds["llama31_8b_300k"] = res
        write_curve_csv(os.path.join(a.out, "curves_llama31_8b_300k.csv"), mf, sm)
        print("[pred] llama done", flush=True)
        for M in (150_000, 600_000):
            nm = f"a100_pool{M // 1000}k"
            cell = Cell(nm, M=float(M), costs=Costs(), eta=ETA)
            g = sorted(set([int(round(x * M / 300_000)) for x in GRID_STD[:-1]] + [300]))
            mm = [1.1, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0] if M < 300_000 else [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
            res, mf, sm = predict_cell(nm, cell, MEASURED["a100_300k"]["lambda_ref"], mm, g, n_rep, nodes, e2_points=())
            res["lambda_ref_note"] = "multiples of the A100 300k E0a lambda_ref 0.071534 (lambda_miss does not depend on the pool)"
            preds[nm] = res
            write_curve_csv(os.path.join(a.out, f"curves_{nm}.csv"), mf, sm)
            print(f"[pred] {nm} done", flush=True)
    # ---------------------------------------------------------------- bursts (B1) and critical burst size
    if "bursts" in todo:
        m3 = CheModel(vcells["a100_300k"])
        mf3 = mean_field_curve(m3, n_grid(300_000))
        lam_ref = MEASURED["a100_300k"]["lambda_ref"]
        b1 = {}
        for mlt in (1.35, 1.65, 2.0):
            lam = mlt * lam_ref
            for b in (10, 25, 40, 50, 60, 75, 100, 200):
                mc = escape_mc(m3, mf3, lam, horizon=5700.0, n_rep=600 if not a.quick else 150, seed=1000 + b,
                               burst_n=b, burst_t=1200.0, burst_w=60.0, t_start_check=1200.0)
                # P(stuck) = escape in [1200, 5700): the trap then persists through the evaluation window
                b1[f"{mlt}_{b}"] = dict(mult=mlt, burst=b, p_stuck=mc.p_escape,
                                        median_t_escape_after_burst=float(np.median(mc.t_escape[np.isfinite(mc.t_escape)] - 1200.0))
                                        if np.isfinite(mc.t_escape).any() else None)
            b1[f"{mlt}_det"] = critical_burst_det(m3, mf3, lam)
        preds["B1_basin"] = b1
        print("[pred] bursts done", flush=True)
    # ---------------------------------------------------------------- rescue R1 / R4
    if "rescue" in todo:
        m3 = CheModel(vcells["a100_300k"])
        mf3 = mean_field_curve(m3, n_grid(300_000))
        mn = CheModel(vcells["a100_native"])
        mfn = mean_field_curve(mn, n_grid(955_757))
        rs = {}
        for mlt in (1.35, 1.65):
            rs[f"R1_{mlt}"] = rescue_prediction(m3, mf3, mlt * MEASURED["a100_300k"]["lambda_ref"], cap=20, t_on=1800.0,
                                                mc_rep=300 if not a.quick else 100)
        rs["R4_4.0"] = rescue_prediction(mn, mfn, 4.0 * MEASURED["a100_native"]["lambda_ref"], cap=64, t_on=2100.0,
                                         mc_rep=300 if not a.quick else 100)
        rs["R4_4.0_cap80_check"] = rescue_prediction(mn, mfn, 4.0 * MEASURED["a100_native"]["lambda_ref"], cap=80, t_on=2100.0,
                                                     mc_rep=100)
        preds["rescue"] = rs
        print("[pred] rescue done", flush=True)
    if preds:
        with open(os.path.join(a.out, "predictions.json"), "w") as f:
            json.dump(preds, f, indent=1, default=float)
    scal = []
    if "scaling" in todo:
        scal = scaling_table(ETA, a.quick)
        with open(os.path.join(a.out, "scaling.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(scal[0].keys()))
            w.writeheader()
            w.writerows(scal)
        print("[scaling] done", flush=True)
    if val and scal:
        make_figures(val, curves, preds, scal, a.figdir)
    here = os.path.dirname(os.path.abspath(__file__))
    files = [os.path.join(here, f) for f in ("model.py", "open_system.py", "measured.py", "run_che.py")]
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip() != ""
    except Exception:
        head, dirty = "unknown", True
    meta = dict(created=time.strftime("%Y-%m-%dT%H:%M:%S%z"), argv=sys.argv, git_head=head, git_dirty=dirty,
                code_sha256={os.path.basename(k): v for k, v in sha256_files(files).items()}, eta=ETA, n_rep=n_rep,
                smooth_nodes=nodes, seconds=time.time() - t_start, python=sys.version, numpy=np.__version__,
                inputs="workload (configs/agentload_e2_burst.yaml), pools, calibration/round6_server_log_fit/calibration.yaml, "
                       "vLLM E0a token rate (scale), H200 E0a token rate (scale); measured targets only in measured.py for comparison")
    meta["parts"] = sorted(todo)
    full = todo == {"validation", "predictions", "scaling", "bursts", "rescue", "sensitivity"}
    with open(os.path.join(a.out, "meta.json" if full else "meta_" + "-".join(sorted(todo)) + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"total {time.time() - t_start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
