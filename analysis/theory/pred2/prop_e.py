r"""Proposition E (exogenous reuse gaps cannot produce the cliff) on the three measured cells, and Corollary C (capacity-ratio
predictors understate the all-miss onset by exactly the sessions in tool calls) on every cell, as rival predictions frozen now.

    PYTHONPATH="src;." python -m analysis.theory.pred2.prop_e        # -> results/theory/pred2/prop_e_cor_c.json

Proposition E (exact, one line).  If the follow-up reuse gap is exogenous (the tool time Z, no queue wait) and K >= 0 tokens are
held by running requests, the characteristic time T of the memory balance M - K = lambda0 [A1 E[min(Z, T)] + E[E_T] T]
(Yao et al., arXiv 2609.02027, Theorem 3.1, at K = 0; the frozen model's balance at W = 0 with K = K_run) satisfies
T >= (M - K) / (lambda0 E[T] Ebar), because E[min(Z, T)] <= T and A1 + E[E_T] = E[T] Ebar.  Hence the follow-up hit
h >= F_Z((M - K) / (lambda0 E[T] Ebar)), and a measured follow-up hit h_meas at throughput lambda0 needs
K >= M - lambda0 D(F_Z^-1(h_meas)): the non-idle KV must fill the pool, which under FCFS admission happens only with a queue
(A4).  The exogenous-gap closures evaluated (no parameter fitted, the measured throughput as their exogenous rate):
  * Yao Theorem 3.1: K = 0, lambda0 = the measured completed-session rate (turns-based; sessions-based as a band);
  * Yao closed by Little's law with exogenous gaps and no service time: lambda0 = n / ((E[T] - 1) zbar);
  * Che with W = Z: each live session is one object of the mean footprint Ebar, exponential renewal gaps Z, no dead content,
    closed population n: residency = F_Z(T_C), so the follow-up hit is min(1, M / (n Ebar)).
The frozen merged model (with the queue term) is listed next to them.

Corollary C (exact, from T3(b)).  n_b - M/E_S = nu_b zbar (1 - 1/E[T]) = lambda_miss zbar (E[T] - 1): any predictor of the
collapse from capacity over a per-session footprint understates the all-miss onset by the sessions in tool calls at the all-miss
rate, a gap that grows linearly with GPU speed (T3(c)) and tool time.
"""
from __future__ import annotations

import csv
import json
import math
import os
from typing import Dict, List

import numpy as np
from scipy.optimize import brentq

from ..fluid_rigorous.cells import PATHS, RN
from ..merged import extras as X
from .common import ROOT, cell, frozen_json, write_json

MEASURED = {"a100_300k": ("sglang-fcfs-r1", [32, 48, 96, 300]), "a100_native": ("sglang-fcfs-r1-native", [96, 128]),
            "vllm_300k": ("vllm-fcfs", [16, 20, 24, 28, 32, 40, 48, 96, 300])}
COR_C_CELLS = ["a100_300k", "a100_native", "vllm_300k", "a100_pool150k", "a100_pool600k", "h200_300k", "h200_300k_ratiofit",
               "h200_300k_lamratiofit", "h200_300k_decode2", "h200_300k_e0a2", "llama31_8b_300k"]


def measured_curve(name: str) -> List[Dict[str, float]]:
    label = MEASURED[name][0]
    with open(os.path.join(RN, PATHS[name]["mu_curve"]), newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["label"] == label]
    return [dict(n=float(r["n"]), mu_sessions=float(r["mu_sessions"]), mu_turns=float(r["mu_turns_based"]),
                 hit=float(r["hit_frac_turns"]), queue_mean=float(r["queue_mean"])) for r in rows]


def yao_T(wl, M: float, lam0: float, K: float = 0.0) -> float:
    """Characteristic time of M - K = lam0 [A1 E[min(Z, T)] + E[E_T] T] (strictly increasing in T)."""
    f = lambda T: lam0 * (wl.A1 * wl.Emin(T) + wl.EET * T) - (M - K)
    hi = 1.0
    while f(hi) < 0:
        hi *= 2.0
    return float(brentq(f, 0.0, hi, xtol=1e-10))


def prop_e_point(c, pt: Dict[str, float], frozen_pts: Dict[str, Dict]) -> Dict[str, object]:
    wl, M, ET = c.m.wl, c.m.M, c.m.ET
    Ebar = float((wl.w * wl.E).sum())
    fu = 1.0 - 1.0 / ET
    out = dict(n=pt["n"], measured=pt)
    for tag, lam0 in (("yao_measured_rate_turns", pt["mu_turns"]), ("yao_measured_rate_sessions", pt["mu_sessions"]),
                      ("yao_little_no_service", pt["n"] / ((ET - 1.0) * wl.zmean))):
        T = yao_T(wl, M, lam0)
        out[tag] = dict(lam0=lam0, T=T, hit_follow=wl.F(T), hit=wl.F(T) * fu)
    out["che_W_eq_Z"] = dict(hit_follow=min(1.0, M / (pt["n"] * Ebar)), hit=min(1.0, M / (pt["n"] * Ebar)) * fu,
                             M_over_Ebar=M / Ebar)
    lam0 = pt["mu_turns"]
    out["bound_K0"] = dict(T_lower=M / (lam0 * ET * Ebar), hit_lower=wl.F(M / (lam0 * ET * Ebar)) * fu)
    h_meas_f = min(max(pt["hit"] / fu, 0.0), 0.999999)
    Tm = wl.Finv(h_meas_f)
    K_need = M - lam0 * (wl.A1 * wl.Emin(Tm) + wl.EET * Tm)
    out["K_needed"] = dict(tokens=K_need, fraction_of_M=K_need / M)
    fp = frozen_pts.get(f"{pt['n']:.1f}") or frozen_pts.get(str(float(pt["n"])))
    if fp:
        out["merged_frozen"] = dict(hit_fluid=fp["hit_fluid"], hit_annealed=fp["hit_annealed"], mu_fluid=fp["mu_fluid"],
                                    mu_annealed=fp["mu_annealed"])
    return out


def measured_crossing(rows: List[Dict[str, float]]) -> Dict[str, float]:
    rows = sorted(rows, key=lambda r: r["n"])
    for a, b in zip(rows[:-1], rows[1:]):
        if a["hit"] >= 0.5 > b["hit"]:
            return dict(n_half=a["n"] + (a["hit"] - 0.5) / (a["hit"] - b["hit"]) * (b["n"] - a["n"]), bracket=[a["n"], b["n"]])
    return dict(n_half=math.nan, bracket=None)


def run() -> Dict[str, object]:
    out: Dict[str, object] = dict(prop_e={}, cor_c={})
    for name, (label, req) in MEASURED.items():
        c = cell(name)
        rows = measured_curve(name)
        fpts = frozen_json(name)["closed_curve"]["grid_points"]
        out["prop_e"][name] = dict(label=label, requested_n=req, pool=c.m.M,
                                   points=[dict(prop_e_point(c, r, fpts), requested=bool(r["n"] in req)) for r in rows])
    for name in COR_C_CELLS:
        c = cell(name)
        thr = X.threshold_closed_form(c.m)
        Ebar = thr["E_bar"]
        rec = dict(M=c.m.M, E_bar=Ebar, E_S=thr["E_S"], E_lb=c.E_lb, M_over_E_bar=c.m.M / Ebar, M_over_E_lb=c.m.M / c.E_lb,
                   M_over_E_S=thr["pool_part"], n_b=thr["n_b"], tool_call_part=thr["tool_call_part"],
                   identity_check=thr["n_b"] - thr["pool_part"] - thr["tool_call_part"], n_half_fluid=c.cs.n_half,
                   lambda_miss_model=thr["mu_b"], blind=bool(c.spec.get("blind", False)))
        if name in MEASURED:
            mc = measured_crossing(measured_curve(name))
            rec["measured"] = mc
            rec["errors_vs_measured_n_half"] = {k: rec[k] - mc["n_half"] for k in ("M_over_E_bar", "M_over_E_lb", "M_over_E_S",
                                                                                    "n_b", "n_half_fluid")}
        else:
            rec["rival_prediction"] = dict(
                capacity_ratio_crossing=rec["M_over_E_S"], capacity_ratio_lb_crossing=rec["M_over_E_lb"],
                frozen_n_half=c.cs.n_half, frozen_n_b=thr["n_b"],
                scoring="when the cell's Stage C is read: the predictor (M/E_S, M/E_lb, frozen n_half) nearest the measured 0.5-hit "
                        "crossing wins; T3(b)'s tool-call term is supported iff the measured crossing exceeds M/E_S by more "
                        "than half the predicted gap n_b - M/E_S")
        out["cor_c"][name] = rec
    return out


def main() -> None:
    p = write_json("prop_e_cor_c", run(), [os.path.relpath(os.path.join(RN, PATHS[n]["mu_curve"]), ROOT).replace(os.sep, "/")
                                           for n in MEASURED])
    print("wrote", p)


if __name__ == "__main__":
    main()
