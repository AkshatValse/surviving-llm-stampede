"""Produce every number and figure of notes/THEORY_r13_fluid_rigorous.md.

    PYTHONPATH="src;." python -m analysis.theory.fluid_rigorous.run_all [--quick] [--no-loopvars]

Writes results/theory/fluid_rigorous/*.csv|json and figures/theory/fluid_rigorous_*.png|pdf.  Deterministic.
Reads only: calibration/round6_server_log_fit/calibration.yaml constants (hard-coded in model.Costs, checked by the
test), results/nova/ directories of the three measured cells (validation targets), and nothing under any h200, llama31,
r11, b100, b25, e0bfresh, lpminf or rescue results directory.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict
from typing import Dict, List

import numpy as np
import pandas as pd

from .cells import PATHS, POOLS, RN, e0a, e0a64, measured, model_for
from .edge import predicted_edge
from .model import (Costs, Model, Workload, annealed_curve, critical_burst_fresh, curve_on_grid, feedback_map, fixed_points,
                    kv_dispersion, local_window_condition, mu_good_of_n, open_equilibria, summarize_curve, window_law_terms,
                    window_upper_bound)
from .oos import H200_E0A, cell_predictions, h200_models, llama_model, rescue_pause_cap
from .trapped import loopvars, round_robin_trap, window_means

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "results", "theory", "fluid_rigorous")
FIG = os.path.join(ROOT, "figures", "theory")
CELLS = ("a100_300k", "a100_native", "vllm_300k")
TITLES = {"a100_300k": "SGLang, A100, 300k pool", "a100_native": "SGLang, A100, native pool (955,757)", "vllm_300k": "vLLM 0.32, A100, 300k pool"}


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    raise TypeError(type(o))


def dump(name: str, obj) -> None:
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, default=_json, sort_keys=False)


def rel(a: float, b: float) -> float:
    return (a - b) / b


# ------------------------------------------------------------------------------------------------ per-cell validation


def validate_cell(cell: str, quick: bool) -> Dict[str, object]:
    me = measured(cell)
    m = model_for(cell)
    cs = summarize_curve(m)
    nmax = max(me.n[me.n < 300].max(), cs.n_b) * 1.15
    ngrid = np.unique(np.concatenate([np.arange(2, nmax, 1.0), me.n[me.n < 300]]))
    ann = annealed_curve(m.wl, m.cost, m.M, ngrid, n_theta=21 if quick else 41)
    mu_f, hit_f, _ = curve_on_grid(cs, ngrid)
    # annealed landmarks
    ia = int(np.argmax(ann["mu"]))
    ha = ann["hit"]
    nh_a = math.nan
    for k in range(len(ngrid) - 1):
        if ha[k] >= 0.5 > ha[k + 1]:
            nh_a = float(ngrid[k] + (ha[k] - 0.5) / (ha[k] - ha[k + 1]) * (ngrid[k + 1] - ngrid[k]))
            break
    pr = cell_predictions(m, me.lam_ref, mults=PATHS[cell]["e0b_mults"])
    b = m.bad()
    e64 = e0a64(cell)
    row = dict(
        cell=cell, M=m.M, mode=m.cost.mode, speed_factor=Costs().a / m.cost.a,
        meas_peak_n=me.peak_n_sessions, meas_flat_top=me.flat_top, pred_peak_n=cs.n_star, pred_peak_n_annealed=float(ngrid[ia]),
        meas_mu_max_sessions=me.mu_max_sessions, meas_mu_max_turns=me.mu_max_turns, pred_mu_max=cs.mu_max,
        pred_mu_max_annealed=float(ann["mu"][ia]),
        err_mu_max_vs_sessions=rel(cs.mu_max, me.mu_max_sessions), err_mu_max_vs_turns=rel(cs.mu_max, me.mu_max_turns),
        meas_n_half=me.n_half, pred_n_half=cs.n_half, pred_n_half_annealed=nh_a,
        meas_mu_large_turns=me.mu_large_turns, meas_n_large=me.n_large, pred_mu_inf=cs.mu_b, pred_n_b=cs.n_b,
        meas_lambda_miss_turns=me.lam_ref, meas_e0a_tokens=me.tokens_ref,
        pred_lambda_miss_pop32=pr["e0a32_mu"], pred_e0a_tokens_pop32=pr["e0a32_tokens"],
        pred_lambda_miss_saturated=b["mu"], pred_tokens_saturated=b["tok"],
        meas_pop64_token_ratio=(e64.get("tokens", math.nan) / me.tokens_ref) if e64 else math.nan, pred_pop64_token_ratio=pr["pop64_ratio"],
        meas_window_sessions=me.window_sessions, meas_window_turns=me.window_turns, pred_window=cs.mu_max / me.lam_ref,
        pred_window_model_units=cs.window,
        meas_edge_stable=me.bracket["stable"], meas_edge_unstable=me.bracket["unstable"], pred_edge_mult=pr["edge"]["edge_mult"],
        pred_edge_stable=pr["edge"]["largest_stable_mult"], pred_edge_unstable=pr["edge"]["first_unstable_mult"],
        fluid_edge_upper=cs.mu_max / me.lam_ref, I_D=pr["I_D"], bistable=cs.bistable,
    )
    curve = pd.DataFrame(dict(n=ngrid, mu_fluid=mu_f, hit_fluid=hit_f, mu_annealed=ann["mu"], hit_annealed=ann["hit"]))
    meas = pd.DataFrame(dict(n=me.n, mu_sessions=me.mu_sessions, mu_turns=me.mu_turns, hit=me.hit,
                             pred_mu_fluid=np.interp(me.n, ngrid, mu_f), pred_hit_fluid=np.interp(me.n, ngrid, hit_f),
                             pred_mu_annealed=np.interp(me.n, ngrid, ann["mu"]), pred_hit_annealed=np.interp(me.n, ngrid, ann["hit"])))
    edge_rows = pd.DataFrame(pr["edge"]["rows"])
    return dict(row=row, curve=curve, meas=meas, edge=edge_rows, cs=cs, m=m, me=me, pr=pr)


# ------------------------------------------------------------------------------------------------ trapped state


def trapped_cell(cell: str, v: Dict[str, object], do_loopvars: bool) -> pd.DataFrame:
    me, m, cs = v["me"], v["m"], v["cs"]
    tr = me.trap
    rows = []
    for _, r in tr.iterrows():
        lam = float(r["lambda"])
        eq = open_equilibria(cs, lam)
        rec = dict(cell=cell, seed=int(r["seed"]), mult=float(r["rate_mult"]), arm=r["arm"], state=r["state"], lam=lam,
                   meas_hit=float(r["hit_eval"]), meas_tok_ratio=float(r["rate_uncached_tokens"]) / float(r["uncached_tokens_ref"]),
                   meas_backlog=float(r["backlog_eval_mean"]), meas_slope=float(r["backlog_slope"]),
                   meas_sessions_per_s=float(r["rate_sessions"]), meas_turns_based=float(r["rate_turns_based"]))
        if do_loopvars:
            rd = os.path.join(RN, PATHS[cell]["trap_root"], r["run_dir"])
            if os.path.exists(os.path.join(rd, "requests.csv")):
                lv = loopvars(rd, m.M)
                rec.update(meas_gap_med=lv["gap_med"], meas_R=lv["R"], meas_gap_over_R=lv["gap_over_R"], meas_Pbar=lv["Pbar"],
                           meas_turns_per_s=lv["turns_per_s"], meas_identity_gap_over_R=float(r["backlog_eval_mean"]) * (lv["Pbar"] + m.wl.d) / m.M)
        if r["arm"] == "burst":
            t = round_robin_trap(m, lam, eq.n1)
            w = window_means(t, 5700.0, 8700.0)
            rec.update(pred_hit=0.0, pred_tok_ratio_vs_meas_e0a=w["tok"] / float(r["uncached_tokens_ref"]),
                       pred_tok_ratio_vs_model_e0a=w["tok"] / m.all_miss_closed(32)["tok"], pred_backlog=w["n_sys"],
                       pred_slope=w["backlog_slope"], pred_sessions_per_s=w["completions"], pred_gap_over_R=w["gap_over_R"],
                       pred_R=w["R"], pred_cycle=w["c"], pred_Pbar=w["Pbar"])
        else:
            # good state (NOBURST / CAPPED): quasi-static equilibrium n1, gap = Z + S, R = M / churn
            pts = cs.pts
            ng, mug = mu_good_of_n(cs)
            n1 = eq.n1
            pt = min(pts[: len(ng)], key=lambda p: abs(p["n"] - n1))
            churn = pt["nu"] * (float((m.wl.w * (m.hk(pt["h"]) * m.wl.x_hit + (1 - m.hk(pt["h"])) * m.wl.P)).sum()) + m.wl.d)
            # median gap of Z + latency with Z ~ Exp(zbar): median(Z) + S
            gap_med = m.wl.zmean * math.log(2.0) + pt["S_bar"]
            rec.update(pred_hit=pt["hit"], pred_backlog=n1, pred_gap_over_R=gap_med / (m.M / churn), pred_R=m.M / churn)
        rows.append(rec)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ window law scans


def window_scans() -> pd.DataFrame:
    wl = Workload()
    rows = []
    for M in (150000.0, 300000.0, 600000.0, 955757.0):
        for s in (0.5, 1.0, 1.5, 2.0, 2.74, 3.5, 5.0, 7.0, 10.0):
            m = Model(wl, Costs().scaled(s), M)
            cs = summarize_curve(m)
            lw = window_law_terms(m, cs)
            ub = window_upper_bound(m, nh=120)
            rows.append(dict(M=M, speed=s, zbar=wl.zmean, mu_max=cs.mu_max, n_star=cs.n_star, h_star=cs.h_star, mu_b=cs.mu_b,
                             window=cs.window, window_law=lw["omega_mem"], window_cap=lw["omega_cap"], window_upper=ub["omega_upper"],
                             n_b=cs.n_b, bistable=cs.bistable))
    # time-rescaling check: (costs / s, zbar) == (costs, s zbar)
    for s in (2.0, 4.0):
        a = summarize_curve(Model(wl, Costs().scaled(s), 300000.0))
        b = summarize_curve(Model(Workload(zbar=wl.zmean * s), Costs(), 300000.0))
        rows.append(dict(M=300000.0, speed=s, zbar=wl.zmean, window=a.window, window_equiv_zbar=b.window, check="time_rescaling",
                         mu_max=a.mu_max, mu_max_equiv_times_s=b.mu_max * s))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ figures


def figures(vals: Dict[str, Dict[str, object]], trap: pd.DataFrame, scans: pd.DataFrame, oos: Dict[str, object]) -> List[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    written = []
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7})
    col = dict(fluid="#1f4e79", ann="#7aa6c2", meas_s="#c0392b", meas_t="#e67e22", miss="#555555")
    # F1: closed curves and hit fractions
    fig, ax = plt.subplots(2, 3, figsize=(7.2, 4.4), sharex="col")
    for j, cell in enumerate(CELLS):
        v = vals[cell]
        c, me, cs = v["curve"], v["me"], v["cs"]
        a = ax[0, j]
        a.plot(c["n"], c["mu_fluid"], color=col["fluid"], lw=1.4, label="fluid model (predicted)")
        a.plot(c["n"], c["mu_annealed"], color=col["ann"], lw=1.0, ls="--", label="fluid + demand fluctuations")
        k = me.n < 300
        a.plot(me.n[k], me.mu_sessions[k], "o", ms=3.5, color=col["meas_s"], label="measured, sessions/s")
        a.plot(me.n[k], me.mu_turns[k], "s", ms=3, mfc="none", color=col["meas_t"], label="measured, turns-based")
        a.axhline(me.lam_ref, color=col["miss"], lw=0.7, ls=":", label=r"E0a $\lambda_{miss}$")
        a.set_title(TITLES[cell])
        a.set_ylabel(r"$\mu(n)$ (sessions/s)" if j == 0 else "")
        a.set_ylim(0, max(me.mu_sessions.max(), cs.mu_max) * 1.15)
        b2 = ax[1, j]
        b2.plot(c["n"], c["hit_fluid"], color=col["fluid"], lw=1.4)
        b2.plot(c["n"], c["hit_annealed"], color=col["ann"], lw=1.0, ls="--")
        b2.plot(me.n[k], me.hit[k], "o", ms=3.5, color=col["meas_s"])
        b2.axhline(0.5, color="#999999", lw=0.5)
        b2.set_xlabel("closed population n")
        b2.set_ylabel("hit fraction (all turns)" if j == 0 else "")
        b2.set_ylim(-0.03, 1.0)
        xm = float(me.n[k].max()) * 1.05
        a.set_xlim(0, xm)
        b2.set_xlim(0, xm)
    h, l = ax[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "fluid_rigorous_closed_curves." + ext)
        fig.savefig(p, dpi=200)
        written.append(p)
    plt.close(fig)
    # F2: from-empty escape probability vs multiple, with measured brackets
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.3))
    for j, cell in enumerate(CELLS):
        v = vals[cell]
        me, m, cs = v["me"], v["m"], v["cs"]
        ngrid = np.linspace(0, cs.n_b * 1.6, 4000)
        mug, _, _ = curve_on_grid(cs, ngrid)
        mu_f = lambda x: np.interp(x, ngrid, mug)
        mults = np.linspace(1.0, min(cs.mu_max / me.lam_ref, PATHS[cell]["e0b_mults"][-1] + 0.5), 60)
        ed = predicted_edge(mu_f, me.lam_ref, list(mults), v["pr"]["I_D"], cs.n_b, 3000.0, cs.mu_max)
        ax[j].plot(mults, [r["p_escape"] for r in ed["rows"]], color=col["fluid"])
        ax[j].axvspan(me.bracket["stable"], me.bracket["unstable"], color=col["meas_s"], alpha=0.15, label="measured edge bracket")
        for mm in PATHS[cell]["e0b_mults"]:
            st_ = mm <= me.bracket["stable"]
            ax[j].plot([mm], [-0.04], marker="o" if st_ else "x", color="green" if st_ else col["meas_s"], ms=4)
        ax[j].axhline(0.5, color="#999999", lw=0.5)
        ax[j].set_title(TITLES[cell])
        ax[j].set_xlabel(r"arrival rate / $\lambda_{ref}$")
        ax[j].set_ylim(-0.08, 1.02)
    ax[0].set_ylabel("P(escape within 3000 s), predicted")
    ax[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "fluid_rigorous_from_empty_edge." + ext)
        fig.savefig(p, dpi=200)
        written.append(p)
    plt.close(fig)
    # F3: window vs GPU speed (and the tool-time equivalence)
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
    sc = scans[scans.get("check").isna()] if "check" in scans else scans
    for M, g in sc.groupby("M"):
        ax[0].plot(g["speed"], g["window"], marker="o", ms=3, label="M = %dk" % round(M / 1000))
        ax[1].plot(g["speed"], g["n_star"], marker="o", ms=3)
    ax[0].axvline(1.0, color="#999999", lw=0.5)
    ax[0].axvline(2.74, color="#999999", lw=0.5, ls="--")
    ax[0].text(2.8, ax[0].get_ylim()[1] * 0.9 if ax[0].get_ylim()[1] > 0 else 5, "H200 (E0a)", fontsize=6)
    ax[0].axhline(1.0, color="k", lw=0.5)
    ax[0].set_xscale("log")
    ax[0].set_xlabel(r"GPU speed $s$ (A100 = 1); equivalently tool time $s\,\bar z$")
    ax[0].set_ylabel(r"window $\mu_{max}/\lambda_{miss}$ (fluid)")
    ax[0].legend(frameon=False)
    ax[1].set_xscale("log")
    ax[1].set_xlabel(r"GPU speed $s$")
    ax[1].set_ylabel(r"peak population $n^*$")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "fluid_rigorous_window_scaling." + ext)
        fig.savefig(p, dpi=200)
        written.append(p)
    plt.close(fig)
    # F4: trapped gap/R predicted vs measured
    if "meas_gap_over_R" in trap:
        fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
        bt = trap[trap["arm"] == "burst"]
        for cell, g in bt.groupby("cell"):
            ax[0].plot(g["pred_gap_over_R"], g["meas_gap_over_R"], "o", ms=4, label=TITLES[cell])
            ax[1].plot(g["pred_tok_ratio_vs_meas_e0a"], g["meas_tok_ratio"], "o", ms=4)
        lim = [0, max(bt["meas_gap_over_R"].max(), bt["pred_gap_over_R"].max()) * 1.1]
        ax[0].plot(lim, lim, color="#999999", lw=0.5)
        ax[0].set_xlabel("predicted gap/R (round-robin fluid)")
        ax[0].set_ylabel("measured gap/R (loopvars)")
        ax[0].legend(frameon=False, fontsize=6)
        l2 = [0.95, 1.15]
        ax[1].plot(l2, l2, color="#999999", lw=0.5)
        ax[1].set_xlabel("predicted trapped token rate / E0a")
        ax[1].set_ylabel("measured trapped token rate / E0a")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            p = os.path.join(FIG, "fluid_rigorous_trapped." + ext)
            fig.savefig(p, dpi=200)
            written.append(p)
        plt.close(fig)
    # F5: the feedback map at several populations (300k): no fold, near-critical slope at the cliff
    m = vals["a100_300k"]["m"]
    cs = vals["a100_300k"]["cs"]
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
    hs = np.linspace(0, 0.999, 120)
    for n in (20.0, 28.0, 31.0, 32.4, 34.0):
        ph = [feedback_map(m, n, float(h))["phi"] for h in hs]
        ax[0].plot(hs, ph, label="n = %g" % n)
    ax[0].plot([0, 1], [0, 1], color="k", lw=0.5)
    ax[0].set_xlabel("follow-up hit probability h (this cycle)")
    ax[0].set_ylabel(r"$\Phi_n(h)$ (next cycle)")
    ax[0].legend(frameon=False)
    n_arr = np.array([p["n"] for p in cs.pts])
    R_arr = np.array([p["R"] for p in cs.pts])
    ax[1].plot(R_arr, n_arr, color=col["fluid"])
    ax[1].set_xscale("log")
    ax[1].set_xlabel("LRU eviction age R (s)")
    ax[1].set_ylabel("population n on the solution curve")
    ax[1].axhline(cs.n_b, color="#999999", lw=0.5, ls=":")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "fluid_rigorous_feedback_map." + ext)
        fig.savefig(p, dpi=200)
        written.append(p)
    plt.close(fig)
    # F6: blind H200 / Llama predicted curves next to the A100 300k prediction
    fig, ax = plt.subplots(1, 1, figsize=(3.6, 2.6))
    for name, mm, ls in (("A100 300k (validated)", vals["a100_300k"]["m"], "-"), ("H200, uniform speed-up", oos["_models"]["h200_uniform"], "-"),
                         ("H200, decode-side 2.0x", oos["_models"]["h200_decode2"], "--"), ("Llama-3.1-8B (a priori)", oos["_models"]["llama"], ":")):
        c2 = summarize_curve(mm)
        ng = np.linspace(1, 60, 400)
        mu, _, _ = curve_on_grid(c2, ng)
        ax.plot(ng, mu, ls=ls, label=name)
    ax.set_xlabel("closed population n")
    ax.set_ylabel(r"predicted $\mu(n)$ (sessions/s)")
    ax.legend(frameon=False, fontsize=6)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "fluid_rigorous_blind_cells." + ext)
        fig.savefig(p, dpi=200)
        written.append(p)
    plt.close(fig)
    return written


# ------------------------------------------------------------------------------------------------ main


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-loopvars", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    t0 = time.time()
    vals = {c: validate_cell(c, args.quick) for c in CELLS}
    comp = pd.DataFrame([vals[c]["row"] for c in CELLS])
    comp.to_csv(os.path.join(OUT, "cells_comparison.csv"), index=False)
    dump("cells_comparison.json", [vals[c]["row"] for c in CELLS])
    for c in CELLS:
        vals[c]["curve"].to_csv(os.path.join(OUT, "curve_%s.csv" % c), index=False)
        vals[c]["meas"].to_csv(os.path.join(OUT, "measured_vs_predicted_%s.csv" % c), index=False)
        vals[c]["edge"].to_csv(os.path.join(OUT, "edge_%s.csv" % c), index=False)
    # theorem-side diagnostics per cell
    diag = {}
    for c in CELLS:
        m, cs = vals[c]["m"], vals[c]["cs"]
        nb = cs.n_b
        fps = {str(round(f * nb, 3)): fixed_points(m, f * nb, ngrid=201) for f in (0.5, 0.8, 0.9, 0.97, 0.995)}
        dn = np.diff([p["n"] for p in cs.pts])
        diag[c] = dict(n_b=nb, mu_b=cs.mu_b, bad=m.bad(), folds=cs.folds, dn_dR_negative_everywhere=bool(np.all(dn > 0)),
                       fixed_points=fps, local_window_condition=local_window_condition(m), window_upper_bound=window_upper_bound(m),
                       window_law=window_law_terms(m, cs), nu_cap_h1=m.nu_cap(1.0), nu_cap_h0=m.nu_cap(0.0),
                       open_equilibria={str(x): asdict(open_equilibria(cs, x * vals[c]["me"].lam_ref)) for x in (1.35, 1.65, 2.0, 2.5, 4.0)
                                        if x * vals[c]["me"].lam_ref < cs.mu_max},
                       critical_burst_fresh={str(x): critical_burst_fresh(m, cs, x * vals[c]["me"].lam_ref) for x in (1.35, 1.65, 2.0, 2.5, 4.0)
                                             if x * vals[c]["me"].lam_ref < cs.mu_max})
    dump("diagnostics.json", diag)
    trap = pd.concat([trapped_cell(c, vals[c], not args.no_loopvars) for c in CELLS], ignore_index=True)
    trap.to_csv(os.path.join(OUT, "trapped_and_good_runs.csv"), index=False)
    scans = window_scans()
    scans.to_csv(os.path.join(OUT, "window_scaling.csv"), index=False)
    # numerical check of the fluid approximation against the finite stochastic system with the SAME calibrated costs:
    # the round-6 simulator (separate-iteration mode, k = 1, 3 seeds, synchronized start, window [900, 2700) s)
    simf = os.path.join(ROOT, "results", "r6_validate_stagec", "20261024-025222", "supp_fine_curve_separate_prefill_priority.csv")
    if os.path.exists(simf):
        sim = pd.read_csv(simf)
        c3 = vals["a100_300k"]["curve"]
        sim["fluid_mu"] = np.interp(sim["n"], c3["n"], c3["mu_fluid"])
        sim["annealed_mu"] = np.interp(sim["n"], c3["n"], c3["mu_annealed"])
        sim["fluid_hit"] = np.interp(sim["n"], c3["n"], c3["hit_fluid"])
        sim["annealed_hit"] = np.interp(sim["n"], c3["n"], c3["hit_annealed"])
        sim.to_csv(os.path.join(OUT, "fluid_vs_stochastic_simulator_300k.csv"), index=False)
    # fold scan: is the SGLang (separate) fluid curve single-valued over pools and tool times?
    fold_rows = []
    for M in (150000.0, 300000.0, 955757.0):
        for z in (1.0, 2.0, 5.0, 10.0, 20.0, 40.0):
            mm = Model(Workload(zbar=z), Costs(), M)
            cz = summarize_curve(mm)
            nn = np.array([p["n"] for p in cz.pts])
            fold_rows.append(dict(M=M, zbar=z, window=cz.window, n_star=cz.n_star, h_star=cz.h_star, n_b=cz.n_b, n_folds=len(cz.folds),
                                  min_dn=float(np.diff(nn).min()), single_valued=bool(np.all(np.diff(nn) > 0))))
    pd.DataFrame(fold_rows).to_csv(os.path.join(OUT, "fold_scan_separate.csv"), index=False)
    # out-of-sample blind predictions
    hm = h200_models()
    lm = llama_model()
    oos: Dict[str, object] = {}
    for k in ("uniform", "decode2"):
        oos["h200_" + k] = cell_predictions(hm[k], H200_E0A["lambda_miss_turns"], mults=(1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.75, 2.0, 2.5))
    oos["h200_speed_factor_uniform"] = hm["_s"]
    oos["h200_compute_factor_decode2"] = hm["_s_compute_decode2"]
    oos["llama_a_priori"] = cell_predictions(lm, lm.bad()["mu"])
    oos["llama_scale"] = dict(note="roofline ratios Llama-3.1-8B / Qwen2.5-7B applied to the calibrated costs", **{k: float(v) for k, v in __import__("analysis.theory.fluid_rigorous.oos", fromlist=["LLAMA_SCALE"]).LLAMA_SCALE.items()})
    # basin test B1 (300k, 1.65 x lam_ref, bursts of 100 and 25) and rescue R1 (300k, 1.35/1.65, cap 20, t_on 1800), R4 (native 4.0, cap 64, t_on 2100)
    v3, vn = vals["a100_300k"], vals["a100_native"]
    lam165 = 1.65 * v3["me"].lam_ref
    cb = critical_burst_fresh(v3["m"], v3["cs"], lam165)
    oos["B1"] = dict(lam=lam165, b_fresh=cb["b_fresh"], b_stat=cb["b_stat"], burst_100="trapped" if 100 > cb["b_fresh"] else "not trapped",
                     burst_25="trapped" if 25 > cb["b_fresh"] else "not trapped", detail=cb)
    oos["R1"] = {str(x): rescue_pause_cap(v3["m"], v3["cs"], x * v3["me"].lam_ref, 20.0, 1800.0) for x in (1.35, 1.65)}
    oos["R4"] = rescue_pause_cap(vn["m"], vn["cs"], 4.0 * vn["me"].lam_ref, 64.0, 2100.0)
    oos["_models"] = dict(h200_uniform=hm["uniform"], h200_decode2=hm["decode2"], llama=lm)
    written = figures(vals, trap, scans, oos)
    oos_public = {k: v for k, v in oos.items() if not k.startswith("_")}
    dump("blind_predictions.json", oos_public)
    meta = dict(written=written, seconds=time.time() - t0, inputs=dict(
        calibration="calibration/round6_server_log_fit/calibration.yaml (constants in model.Costs)",
        workload="configs/agentload_e2_burst.yaml workload section (model.Workload defaults)",
        measured={c: PATHS[c] for c in CELLS}, h200_e0a=H200_E0A))
    dump("meta.json", meta)
    print(comp.T.to_string())
    print("written", len(written), "figures in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
