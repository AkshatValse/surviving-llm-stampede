r"""The trapped (all-miss) regime of the open system as an FCFS round-robin fluid [T7], and the loopvars measurement.

Model.  In the trapped regime every follow-up misses and the engine is memory-saturated, so the GPU is never idle and
serves the queued turns in FCFS order.  Every session in the system therefore completes exactly one turn per cycle,
and the cycle length is the GPU work of one round:
        c(t) = sum_{i in system} g(k_i),     g(k) = t_P,miss(k) + delta_dec,
with t_P,miss the calibrated prefill time of a miss at turn k and delta_dec = (1 - p_b) / nu_b the per-turn decode
share of the memory-saturated all-miss state (both from the stationary model of the cell).  Each session advances its
turn index at rate 1 / c(t); its survival to turn K is G(K) = q^(K-1) (smoothed).  Arrivals: Poisson rate lam plus a
burst.  The background good-state population n_1(lam) (stationary turn mix) is present at the burst.

Identities of the round-robin (exact in this fluid; [T7]):
    gap  = time from the end of turn k to the end of turn k+1 of a session = c(t)
    R    = M / churn,   churn = sum_i (P_{k_i} + d) / c       (uncached prompt + completion tokens per second)
    gap / R = sum_i (P_{k_i} + d) / M                         (total next-turn context of the sessions present / pool)
    uncached tokens / s = sum_i P_{k_i} / sum_i g(k_i)        (depends only on the in-system turn mix)
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics as st
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from .model import Model


def round_robin_trap(m: Model, lam: float, n_bg: float, t_b: float = 1200.0, burst_n: float = 200.0, burst_w: float = 60.0,
                     t_end: float = 8700.0, dt: float = 1.0) -> Dict[str, np.ndarray]:
    wl = m.wl
    b = m.bad()
    q = 1.0 - 1.0 / wl.mean_turns
    delta_dec = (1.0 - b["p"]) / b["nu"]
    L0, inc, d, K = wl.L0, wl.delta + wl.d, wl.d, wl.K
    cpar = m.cost

    def P_of(Kc: np.ndarray) -> np.ndarray:
        return L0 + (np.floor(Kc) - 1.0) * inc

    def g_of(Kc: np.ndarray) -> np.ndarray:
        P = P_of(Kc)
        return cpar.a * np.maximum(1.0, P / cpar.chunk) + np.maximum(cpar.f, cpar.b * P) + cpar.cp * P * (P + 1) / 2.0 + delta_dec

    def G_of(Kc: np.ndarray) -> np.ndarray:
        return np.where(Kc < K + 1, q ** (Kc - 1.0), 0.0)

    # cohorts: masses (initial sessions) and continuous turn counters
    # background: n_bg present sessions with the stationary mix w_k  ->  initial mass m_k = n_bg w_k / G_k at phase k
    ks = np.arange(1, K + 1, dtype=float)
    w = wl.w
    mass = list(n_bg * w / wl.G)
    phase = list(ks + 0.5)
    times = np.arange(t_b, t_end + dt, dt)
    out = {k: np.zeros_like(times) for k in ("n_sys", "c", "tok", "turns", "completions", "gap_over_R", "R", "Pbar")}
    mass_a = np.array(mass)
    phase_a = np.array(phase)
    for it, t in enumerate(times):
        add = lam * dt
        if t_b <= t < t_b + burst_w:
            add += burst_n / burst_w * dt
        mass_a = np.append(mass_a, add)
        phase_a = np.append(phase_a, 1.0)
        G = G_of(phase_a)
        pres = mass_a * G
        n_sys = pres.sum()
        c = float((pres * g_of(phase_a)).sum())
        P = P_of(phase_a)
        tok = float((pres * P).sum()) / c
        churn = float((pres * (P + d)).sum()) / c
        out["n_sys"][it] = n_sys
        out["c"][it] = c
        out["tok"][it] = tok
        out["turns"][it] = n_sys / c
        out["completions"][it] = float((pres * (1.0 / wl.mean_turns)).sum()) / c
        out["R"][it] = m.M / churn
        out["gap_over_R"][it] = float((pres * (P + d)).sum()) / m.M
        out["Pbar"][it] = float((pres * P).sum()) / n_sys
        phase_a = phase_a + dt / c
        keep = phase_a < K + 1
        mass_a, phase_a = mass_a[keep], phase_a[keep]
    out["t"] = times
    return out


def window_means(tr: Dict[str, np.ndarray], t0: float, t1: float) -> Dict[str, float]:
    sel = (tr["t"] >= t0) & (tr["t"] < t1)
    res = {k: float(np.mean(v[sel])) for k, v in tr.items() if k != "t"}
    x = tr["t"][sel]
    y = tr["n_sys"][sel]
    res["backlog_slope"] = float(np.polyfit(x, y, 1)[0])
    return res


# ------------------------------------------------------------------------------------------------ measurement


def _argval(argv: List[str], key: str) -> Optional[str]:
    for i, a in enumerate(argv):
        if a == "--set" and i + 1 < len(argv) and argv[i + 1].startswith(key + "="):
            return argv[i + 1].split("=", 1)[1].strip('"')
        if a == key and i + 1 < len(argv):
            return argv[i + 1]
    return None


def loopvars(run_dir: str, M: float, t0: float = 5700.0, t1: float = 8700.0) -> Dict[str, float]:
    """Re-implementation of analysis/r11/loopvars_frozen.py (same definitions) for one run directory:
    hit = follow-up turns with cached > prompt/2; gap = Z + latency (end of turn k -> end of turn k+1), median;
    churn = (uncached prompt + completion tokens of requests completed in the window) / window; R = M / churn."""
    meta = json.load(open(os.path.join(run_dir, "meta.json")))
    argv = meta.get("argv", [])
    by_sid: Dict[str, Dict[int, dict]] = defaultdict(dict)
    reqs = []
    with open(os.path.join(run_dir, "requests.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["status"] != "ok":
                continue
            rec = dict(t_send=float(r["t_send"]), t_c=float(r["t_complete"]), k=int(r["turn"]), pt=int(r["prompt_tokens"] or 0),
                       ct=int(r["cached_tokens"] or 0), comp=int(r["completion_tokens"] or 0), lat=float(r["latency_s"]))
            by_sid[r["sid"]][rec["k"]] = rec
            reqs.append(rec)
    win = [q for q in reqs if t0 <= q["t_c"] < t1]
    fu = [q for q in win if q["k"] > 1]
    hit = sum(1 for q in fu if q["ct"] > q["pt"] / 2) / max(1, len(fu))
    gaps, Zs = [], []
    for sid, turns in by_sid.items():
        for k, q in turns.items():
            if k > 1 and (k - 1) in turns and t0 <= q["t_c"] < t1:
                z = q["t_send"] - turns[k - 1]["t_c"]
                Zs.append(z)
                gaps.append(z + q["lat"])
    churn = sum((q["pt"] - q["ct"]) + q["comp"] for q in win) / (t1 - t0)
    R = M / churn if churn > 0 else math.inf
    tok = sum(q["pt"] - q["ct"] for q in win) / (t1 - t0)
    return dict(run=os.path.basename(run_dir), arm=_argval(argv, "meta.arm"), rate=_argval(argv, "arrivals.rate_mult"),
                seed=_argval(argv, "--seed"), n_fu=len(fu), hit=hit, Z_mean=st.mean(Zs) if Zs else math.nan,
                gap_med=st.median(gaps) if gaps else math.nan, gap_mean=st.mean(gaps) if gaps else math.nan,
                churn=churn, R=R, gap_over_R=(st.median(gaps) / R) if gaps else math.nan, tok=tok,
                turns_per_s=len(win) / (t1 - t0), Pbar=(tok / (len(win) / (t1 - t0))) if win else math.nan)
