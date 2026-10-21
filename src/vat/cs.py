"""Predictable-plug-in empirical-Bernstein confidence sequence (PrPl-EB).

Reference: I. Waudby-Smith and A. Ramdas, "Estimating means of bounded random
variables by betting", JRSSB 2024 (arXiv:2010.09686). Implemented from the formulas
in the task spec; NOT checked against the paper text in this environment.

Target: mean of iid (or conditionally mean-mu) observations in [0,1].
  mu_t = (1/2 + sum X_i)/(t+1), s2_t = (1/4 + sum (X_i-mu_i)^2)/(t+1)
  lam_t = min(sqrt(2 log(2/a) / (s2_{t-1} t log(1+t))), c)
  psi_E(l) = (-log(1-l) - l)/4, v_t = 4 (X_t - mu_{t-1})^2
  C_t = sum lam X / sum lam; W_t = (log(2/a) + sum v psi_E(lam)) / sum lam
Interval [C_t - W_t, C_t + W_t] cap [0,1], then running intersection over t.

Clipping the log-speedup to [-b, b] means the CS covers the mean of the CLIPPED
log-ratio, not of the raw log-ratio.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def prpl_eb_cs(x: np.ndarray, alpha: float, c: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
    """CS for each prefix along the last axis. x in [0,1], shape (..., T). Returns (lo, hi)."""
    x = np.asarray(x, dtype=float)
    T = x.shape[-1]
    t = np.arange(1, T + 1, dtype=float)
    mu = (0.5 + np.cumsum(x, -1)) / (t + 1)
    s2 = (0.25 + np.cumsum((x - mu) ** 2, -1)) / (t + 1)
    shp = x.shape[:-1] + (1,)
    mu_prev = np.concatenate([np.full(shp, 0.5), mu[..., :-1]], -1)
    s2_prev = np.concatenate([np.full(shp, 0.25), s2[..., :-1]], -1)
    la = np.log(2.0 / alpha)
    lam = np.minimum(np.sqrt(2 * la / (s2_prev * t * np.log1p(t))), c)
    v = 4 * (x - mu_prev) ** 2
    psi = (-np.log1p(-lam) - lam) / 4
    sl = np.cumsum(lam, -1)
    center = np.cumsum(lam * x, -1) / sl
    width = (la + np.cumsum(v * psi, -1)) / sl
    lo = np.maximum.accumulate(np.clip(center - width, 0, 1), axis=-1)
    hi = np.minimum.accumulate(np.clip(center + width, 0, 1), axis=-1)
    return lo, hi


def to_unit(x: np.ndarray, b: float) -> np.ndarray:
    """Clip log-speedup to [-b,b] and map to [0,1]."""
    return (np.clip(x, -b, b) + b) / (2 * b)


def from_unit(u: np.ndarray, b: float) -> np.ndarray:
    return u * (2 * b) - b
