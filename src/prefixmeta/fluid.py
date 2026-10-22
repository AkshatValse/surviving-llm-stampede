r"""Fluid predictor for the thrashing-curve picture of metastability (round 4).

Setting. ``mu(n)`` is the long-run session completion rate of the CLOSED system in which ``n`` sessions are always present
(a completed session is replaced at once by a fresh turn-1 session). The open system with Poisson($\lambda$) arrivals is
approximated by the fluid ODE ``dn/dt = lambda - mu(n)``. For a unimodal curve with maximum ``mu* = mu(n*)`` and tail value
``mu_inf = mu(n_max) < mu*``:

* ``lambda > mu*``                 : no fixed point (overload; ``b_c`` undefined = NaN).
* ``mu_inf < lambda < mu*``        : two fixed points ``n1 < n* < n2``; ``n1`` stable, ``n2`` unstable; a burst of ``b``
                                     extra sessions on top of ``n1`` diverges iff ``b > b_c := n2 - n1``.
* ``lambda <= mu_inf``             : only ``n1`` (globally attracting); no instability, ``b_c = +inf``.
* ``lambda == mu*``                : ``n1 = n2 = n*`` (``b_c = 0``).

On a non-unimodal ("raw") curve the monostable condition is ``lambda <= min_{n >= n*} mu(n)`` (amendment 1 of the
pre-registration; it equals ``mu_inf`` on a unimodal curve): a tail dip below ``lambda`` followed by a rise back above it still
produces an unstable crossing. ``n2`` is then the FIRST downward crossing after ``n*``; with a tail bump the ODE started above
``n2`` can settle at an intermediate stable point, so ``n2 - n1`` does not by itself imply divergence.

Curve model (pre-registered, configs/prefix_meta_r4_prereg.yaml, ``operationalization.fluid_curve``): piecewise-linear
interpolation through ``(0, 0)`` and the measured points, optionally after a pool-adjacent-violators projection of the
measured values onto unimodal sequences (non-decreasing up to the first argmax, non-increasing after it; the peak value is
preserved), constant beyond the largest measured ``n``. Fixed points are exact roots of that piecewise-linear function:
``n1`` = smallest ``n`` with ``mu(n) >= lambda``; ``n2`` = smallest ``n >= n*`` with ``mu(n) <= lambda`` (``+inf`` if
``lambda <= mu_inf``).

Pure NumPy; no randomness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np


# ----------------------------------------------------------------------------------------------- isotonic helpers
def pav_nondecreasing(y: Sequence[float]) -> np.ndarray:
    """Unweighted pool-adjacent-violators: the L2-closest non-decreasing sequence to ``y``."""
    vals: list = []
    cnt: list = []
    for v in np.asarray(y, dtype=float):
        vals.append(float(v))
        cnt.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            tot = vals[-2] * cnt[-2] + vals[-1] * cnt[-1]
            c = cnt[-2] + cnt[-1]
            vals.pop()
            cnt.pop()
            vals[-1] = tot / c
            cnt[-1] = c
    return np.repeat(vals, cnt) if vals else np.zeros(0)


def pav_nonincreasing(y: Sequence[float]) -> np.ndarray:
    """The L2-closest non-increasing sequence to ``y``."""
    return -pav_nondecreasing(-np.asarray(y, dtype=float))


def unimodal_projection(y: Sequence[float]) -> np.ndarray:
    """Project ``y`` onto sequences that are non-decreasing up to the FIRST argmax of ``y`` and non-increasing from it on.
    The value at the mode is unchanged (the fits at the mode equal ``max(y)``), so the measured maximum is preserved."""
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return y.copy()
    i = int(np.argmax(y))                 # first argmax
    left = pav_nondecreasing(y[: i + 1])
    right = pav_nonincreasing(y[i:])
    return np.concatenate([left[:-1], right])


# ----------------------------------------------------------------------------------------------- the curve
@dataclass(frozen=True)
class FluidCurve:
    """Piecewise-linear ``mu(n)`` on ``n[0] = 0 < n[1] < ...`` (constant beyond ``n[-1]``)."""
    n: np.ndarray
    mu: np.ndarray

    def __post_init__(self) -> None:
        n, mu = np.asarray(self.n, dtype=float), np.asarray(self.mu, dtype=float)
        if n.ndim != 1 or n.shape != mu.shape or n.size < 2:
            raise ValueError("n and mu must be 1-D arrays of equal length >= 2")
        if np.any(np.diff(n) <= 0):
            raise ValueError("n must be strictly increasing")
        if np.any(~np.isfinite(mu)) or np.any(mu < 0):
            raise ValueError("mu must be finite and non-negative")
        object.__setattr__(self, "n", n)
        object.__setattr__(self, "mu", mu)

    def __call__(self, x):
        return np.interp(x, self.n, self.mu)

    @property
    def i_star(self) -> int:
        return int(np.argmax(self.mu))          # first argmax

    @property
    def n_star(self) -> float:
        return float(self.n[self.i_star])

    @property
    def mu_star(self) -> float:
        return float(self.mu[self.i_star])

    @property
    def n_max(self) -> float:
        return float(self.n[-1])

    @property
    def mu_inf(self) -> float:
        """``mu(n_max)``: the tail value of the (interpolated) curve."""
        return float(self.mu[-1])

    @property
    def mu_tail_min(self) -> float:
        """``min_{n >= n*} mu(n)`` (equals ``mu_inf`` when the tail is non-increasing)."""
        return float(np.min(self.mu[self.i_star:]))


def make_curve(n: Sequence[float], mu: Sequence[float], *, unimodal: bool = True, origin: bool = True) -> FluidCurve:
    """Build the fluid curve from measured points (any order). ``origin`` adds the anchor ``(0, 0)`` (no session, no
    completions) unless ``n`` already contains 0. ``unimodal`` applies ``unimodal_projection`` to the measured values."""
    n = np.asarray(n, dtype=float)
    mu = np.asarray(mu, dtype=float)
    order = np.argsort(n, kind="stable")
    n, mu = n[order], mu[order]
    if np.any(np.diff(n) <= 0):
        raise ValueError("measured n values must be distinct")
    if unimodal:
        mu = unimodal_projection(mu)
    if origin and n[0] > 0:
        n = np.concatenate([[0.0], n])
        mu = np.concatenate([[0.0], mu])
    return FluidCurve(n=n, mu=mu)


# ----------------------------------------------------------------------------------------------- fixed points
@dataclass(frozen=True)
class FixedPoints:
    """Fixed points of ``dn/dt = lambda - mu(n)``. ``kind``: ``"overload"`` (lambda > mu*), ``"critical"``
    (lambda == mu*), ``"bistable"`` (min_{n >= n*} mu < lambda < mu*; on a unimodal curve the minimum is mu_inf) or
    ``"monostable"`` (lambda <= min_{n >= n*} mu(n))."""
    lam: float
    kind: str
    n1: float          # stable (NaN if overload)
    n2: float          # unstable (+inf if monostable, NaN if overload)

    @property
    def b_c(self) -> float:
        """Critical burst ``n2 - n1`` (+inf monostable, NaN overload, 0 critical)."""
        if self.kind == "overload":
            return math.nan
        return self.n2 - self.n1


def fixed_points(curve: FluidCurve, lam: float) -> FixedPoints:
    n, mu = curve.n, curve.mu
    lam = float(lam)
    i_star = curve.i_star
    mu_star = curve.mu_star
    if lam > mu_star:
        return FixedPoints(lam, "overload", math.nan, math.nan)
    # n1: first crossing of lambda from below on [0, n*]
    if lam <= mu[0]:
        n1 = float(n[0])
    else:
        i = int(np.argmax(mu[: i_star + 1] >= lam))          # first index with mu >= lam (exists: mu[i_star] >= lam)
        n1 = float(n[i - 1] + (lam - mu[i - 1]) / (mu[i] - mu[i - 1]) * (n[i] - n[i - 1]))
    if lam == mu_star:
        return FixedPoints(lam, "critical", n1, float(n[i_star]))      # n1 == n* here (first argmax), so b_c = 0
    if lam <= curve.mu_tail_min:
        return FixedPoints(lam, "monostable", n1, math.inf)
    # n2: first n >= n* with mu(n) <= lambda (a crossing exists because min_{n >= n*} mu < lambda < mu*)
    tail = mu[i_star:]
    j = int(np.argmax(tail <= lam)) + i_star
    n2 = float(n[j - 1] + (mu[j - 1] - lam) / (mu[j - 1] - mu[j]) * (n[j] - n[j - 1]))
    return FixedPoints(lam, "bistable", n1, n2)


def critical_burst(curve: FluidCurve, lam: float) -> float:
    """Predicted critical burst ``b_c(lambda) = n2 - n1`` (see ``FixedPoints.b_c`` for the degenerate cases)."""
    return fixed_points(curve, lam).b_c


def bc_curve(curve: FluidCurve, lams: Sequence[float]) -> np.ndarray:
    """``b_c`` at each ``lambda`` (vectorised convenience; NaN where undefined, +inf where monostable)."""
    return np.array([critical_burst(curve, lam) for lam in lams], dtype=float)


def stability(curve: FluidCurve, n_point: float, lam: float, eps: float = 1e-6) -> str:
    """'stable' / 'unstable' / 'degenerate' for a fixed point of dn/dt = lam - mu(n), by the sign of the one-sided slopes."""
    f_l = lam - float(curve(n_point - eps))
    f_r = lam - float(curve(n_point + eps))
    if f_l > 0 > f_r:
        return "stable"
    if f_l < 0 < f_r:
        return "unstable"
    return "degenerate"


# ----------------------------------------------------------------------------------------------- ODE (validation only)
def integrate_fluid(curve: FluidCurve, lam: float, n0: float, t_end: float, dt: float = 0.05,
                    n_cap: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Forward-Euler path of ``dn/dt = lam - mu(n)`` from ``n0`` (clipped at 0 from below). Stops early once ``n`` exceeds
    ``n_cap`` (default ``3 * n_max``). Used to check that bursts below / above ``b_c`` return / diverge in tests."""
    cap = 3.0 * curve.n_max if n_cap is None else float(n_cap)
    ts = [0.0]
    ns = [float(n0)]
    n, t = float(n0), 0.0
    while t < t_end and n < cap:
        n = max(0.0, n + dt * (lam - float(curve(n))))
        t += dt
        ts.append(t)
        ns.append(n)
    return np.array(ts), np.array(ns)
