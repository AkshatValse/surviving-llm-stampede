r"""Finite-size heuristic for the from-empty edge [F2] (not a theorem).

The fluid model makes the good state stable from empty for every lambda < mu_max.  A finite system escapes earlier:
the KV demand of the sessions present fluctuates and can carry the system past the basin boundary n_u(lambda) of the
quasi-static dynamics.  We model the demand in units of stationary sessions, X = D / E_lb, as a one-dimensional
diffusion on [0, inf) reflected at 0,

    dX = (lambda - mu(X)) dt + sqrt(I_D (lambda + mu(X))) dW,

with mu the fluid closed curve (predicted, not measured) and I_D = E[int c^2] / (E[int c] E_lb) the dispersion index of
the open (Poisson) session process's KV demand (shot noise, Campbell's theorem), computed from the workload alone.  The
noise intensity is the birth-death value lambda + mu scaled by I_D so that the linearised stationary variance equals the
shot-noise variance n_1 I_D.  The mean first-passage time from 0 to x_t (the all-miss end n_b) is

    T = int_0^{x_t} dy int_0^y dz (2 / s2(z)) exp(Psi(z) - Psi(y)),     Psi(y) = int_0^y 2 (lambda - mu) / s2,

and a run of horizon H escapes with probability 1 - exp(-H / T) (exponential-escape approximation).  The predicted
edge is the lambda at which that probability is 1/2.  Nothing is fitted; H, the target and I_D are stated inputs.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence

import numpy as np


def mean_passage_time(mu: Callable[[np.ndarray], np.ndarray], lam: float, I_D: float, x_t: float, nx: int = 6000) -> float:
    y = np.linspace(0.0, x_t, nx + 1)
    dy = y[1] - y[0]
    muy = mu(y)
    s2 = I_D * (lam + muy)
    s2 = np.maximum(s2, 1e-12)
    drift = lam - muy
    # Psi on the grid (trapezoid)
    g = 2.0 * drift / s2
    psi = np.concatenate([[0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * dy)])
    # J(y) = int_0^y (2/s2(z)) exp(Psi(z) - Psi(y)) dz, recursively and stably
    J = np.zeros_like(y)
    for i in range(1, len(y)):
        J[i] = J[i - 1] * math.exp(psi[i - 1] - psi[i]) + 0.5 * (2.0 / s2[i] + 2.0 / s2[i - 1] * math.exp(psi[i - 1] - psi[i])) * dy
    return float(np.trapz(J, y))


def escape_probability(mu: Callable[[np.ndarray], np.ndarray], lam: float, I_D: float, x_t: float, H: float) -> Dict[str, float]:
    T = mean_passage_time(mu, lam, I_D, x_t)
    return dict(lam=lam, T=T, p_escape=1.0 - math.exp(-H / T) if T > 0 else 1.0)


def predicted_edge(mu: Callable[[np.ndarray], np.ndarray], lam_ref: float, mults: Sequence[float], I_D: float, x_t: float,
                   H: float, mu_max: float) -> Dict[str, object]:
    rows: List[Dict[str, float]] = []
    for m in mults:
        lam = m * lam_ref
        if lam >= mu_max:
            rows.append(dict(mult=m, lam=lam, T=0.0, p_escape=1.0))
            continue
        r = escape_probability(mu, lam, I_D, x_t, H)
        r["mult"] = m
        rows.append(r)
    # continuous edge: bisection on p_escape = 1/2 between 1.0 x lam_ref and mu_max
    lo, hi = 1.0 * lam_ref, mu_max * (1 - 1e-6)

    def p(l: float) -> float:
        return escape_probability(mu, l, I_D, x_t, H)["p_escape"]

    if p(lo) >= 0.5:
        edge = lo
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if p(mid) < 0.5:
                lo = mid
            else:
                hi = mid
        edge = 0.5 * (lo + hi)
    stable = [r["mult"] for r in rows if r["p_escape"] < 0.5]
    unstable = [r["mult"] for r in rows if r["p_escape"] >= 0.5]
    return dict(rows=rows, edge_lam=edge, edge_mult=edge / lam_ref, largest_stable_mult=max(stable) if stable else math.nan,
                first_unstable_mult=min([u for u in unstable if not stable or u > max(stable)], default=math.nan))
