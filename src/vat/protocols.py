"""Benchmarking/selection protocols, run offline on resampled collected timings.

All protocols consume "streams": x[K, T] clipped log-speedups (log baseline/candidate)
and ns[K, T] timing cost (baseline_ns + candidate_ns of the block), where column t is
the t-th block drawn for that candidate. Candidate k is a "real improvement" iff
theta[k] > log(1+delta), theta being the mean clipped log-ratio on held-out processes.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy import stats

from .cs import from_unit, prpl_eb_cs, to_unit


def pct(logx: np.ndarray | float) -> np.ndarray | float:
    """log-speedup -> % speedup."""
    return 100.0 * (np.exp(logx) - 1.0)


def draw_streams(x_pool: np.ndarray, ns_pool: np.ndarray, rng: np.random.Generator):
    """Independent random permutation (without replacement) of each candidate's pool."""
    K, M = x_pool.shape
    perm = np.argsort(rng.random((K, M)), axis=1)
    rows = np.arange(K)[:, None]
    return x_pool[rows, perm], ns_pool[rows, perm]


def _finish(winner: int, accepted: np.ndarray, blocks: int, ns: float, mean_log: np.ndarray,
            theta: np.ndarray, delta: float, extra: dict | None = None) -> dict:
    real = theta > np.log1p(delta)
    best_true = pct(theta.max())
    out = {
        "reported_pct": float(pct(mean_log[winner])),
        "true_pct": float(pct(theta[winner])),
        "inflation_pct": float(pct(mean_log[winner]) - pct(theta[winner])),
        "regret_pct": float(best_true - pct(theta[winner])),
        "n_accept": int(accepted.sum()),
        "n_false_accept": int((accepted & ~real).sum()),
        "any_false_accept": float((accepted & ~real).any()),
        "power": float((accepted & real).sum() / real.sum()) if real.any() else np.nan,
        "winner_is_real": float(real[winner]),
        "blocks": int(blocks),
        "ns": float(ns),
    }
    if extra:
        out.update(extra)
    return out


def naive_fixed(x: np.ndarray, ns: np.ndarray, r: int, delta: float, theta: np.ndarray) -> dict:
    m = x[:, :r].mean(1)
    acc = m > np.log1p(delta)
    return _finish(int(np.argmax(m)), acc, x.shape[0] * r, ns[:, :r].sum(), m, theta, delta)


def bonf_t(x: np.ndarray, ns: np.ndarray, r: int, delta: float, alpha: float,
           theta: np.ndarray) -> dict:
    K = x.shape[0]
    xs = x[:, :r]
    m = xs.mean(1)
    se = xs.std(1, ddof=1) / np.sqrt(r)
    tq = stats.t.ppf(1 - alpha / K, r - 1)
    acc = (m - tq * se) > np.log1p(delta)
    return _finish(int(np.argmax(m)), acc, K * r, ns[:, :r].sum(), m, theta, delta)


def race_bounds(x: np.ndarray, alpha: float, b: float, c: float):
    """Per-candidate PrPl-EB CS (level alpha/K) along each stream, in log-speedup units."""
    K = x.shape[0]
    lo, hi = prpl_eb_cs(to_unit(x, b), alpha / K, c)
    return from_unit(lo, b), from_unit(hi, b)


def cs_race(x: np.ndarray, ns: np.ndarray, lo: np.ndarray, hi: np.ndarray, B: int,
            delta: float, b: float, theta: np.ndarray, freeze_on_accept: bool = True) -> dict:
    """Sequential round-robin race. lo/hi from race_bounds (same shape as x).

    Round: one block for each currently-sampled candidate.
    Accept k when lower_k > log(1+delta). Eliminate k when upper_k < max(log(1+delta),
    best lower bound among non-eliminated). freeze_on_accept=True (spec-literal):
    accepted candidates stop being sampled ("decided"); False (variant CS-RACE-BEST):
    accepted candidates keep being sampled until eliminated, race ends when <=1
    candidate is left undecided/alive.  Stops at budget B blocks.
    """
    K, T = x.shape
    thr_d = np.log1p(delta)
    L = np.full(K, -b)
    U = np.full(K, b)
    n = np.zeros(K, dtype=int)
    acc = np.zeros(K, bool)
    elim = np.zeros(K, bool)
    blocks = 0
    while True:
        samp = ~elim & (n < T)
        if freeze_on_accept:
            samp &= ~acc
        else:
            undecided = ~elim & ~acc
            if not undecided.any() and (~elim).sum() <= 1:
                break
        m = int(samp.sum())
        if m == 0 or blocks + m > B:
            break
        idx = np.where(samp)[0]
        n[idx] += 1
        blocks += m
        L[idx] = lo[idx, n[idx] - 1]
        U[idx] = hi[idx, n[idx] - 1]
        acc |= L > thr_d
        thr = max(thr_d, L[~elim].max())
        kill = U < thr
        if freeze_on_accept:
            kill &= ~acc
        elim |= kill
    cx = np.concatenate([np.zeros((K, 1)), np.cumsum(x, 1)], 1)
    cn = np.concatenate([np.zeros((K, 1)), np.cumsum(ns, 1)], 1)
    rows = np.arange(K)
    mean = np.where(n > 0, cx[rows, n] / np.maximum(n, 1), -np.inf)
    for pool in (acc & ~elim, acc, ~elim, np.ones(K, bool)):
        pool = pool & (n > 0)
        if pool.any():
            break
    w = int(np.argmax(np.where(pool, mean, -np.inf)))
    mean_safe = np.where(n > 0, mean, 0.0)
    extra = {"winner_cs_cover": float(L[w] <= theta[w] <= U[w]),
             "n_elim": int(elim.sum()), "mean_n": float(n.mean())}
    return _finish(w, acc, blocks, cn[rows, n].sum(), mean_safe, theta, delta, extra)


def run_protocols(x: np.ndarray, ns: np.ndarray, theta: np.ndarray, cfg: dict, b: float,
                  c: float, ks: List[int] | None = None) -> List[dict]:
    """Run all protocols on one replicate's streams. Returns rows (protocol, param, metrics)."""
    a, delta = cfg["alpha"], cfg["delta"]
    K, T = x.shape
    rows = []
    for r in cfg["r_values"]:
        if r > T:
            continue
        rows.append({"protocol": "NAIVE", "param": r, **naive_fixed(x, ns, r, delta, theta)})
        rows.append({"protocol": "BONF-T", "param": r, **bonf_t(x, ns, r, delta, a, theta)})
    lo, hi = race_bounds(x, a, b, c)
    for mult in cfg["race_budget_per_candidate"]:
        B = mult * K
        rows.append({"protocol": "CS-RACE", "param": mult,
                     **cs_race(x, ns, lo, hi, B, delta, b, theta, True)})
        rows.append({"protocol": "CS-RACE-BEST", "param": mult,
                     **cs_race(x, ns, lo, hi, B, delta, b, theta, False)})
    return rows
