"""Candidate implementations of a 2D 5-point Jacobi stencil (N x N float64).

One call = `iters` sweep-pairs (a->b then b->a), fixed boundary. Candidates are a
parametric Numba family: loop order x tile size x parallel x fastmath, plus a
NumPy-slicing baseline (id 0).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

import numpy as np
from numba import njit, prange


# ---- pure-python kernel bodies (wrapped by njit with different flags) ----
def _untiled_row(a, b, iters):
    n = a.shape[0]
    for _ in range(iters):
        for i in prange(1, n - 1):
            for j in range(1, n - 1):
                b[i, j] = 0.25 * (a[i - 1, j] + a[i + 1, j] + a[i, j - 1] + a[i, j + 1])
        for i in prange(1, n - 1):
            for j in range(1, n - 1):
                a[i, j] = 0.25 * (b[i - 1, j] + b[i + 1, j] + b[i, j - 1] + b[i, j + 1])


def _untiled_col(a, b, iters):
    n = a.shape[0]
    for _ in range(iters):
        for j in prange(1, n - 1):
            for i in range(1, n - 1):
                b[i, j] = 0.25 * (a[i - 1, j] + a[i + 1, j] + a[i, j - 1] + a[i, j + 1])
        for j in prange(1, n - 1):
            for i in range(1, n - 1):
                a[i, j] = 0.25 * (b[i - 1, j] + b[i + 1, j] + b[i, j - 1] + b[i, j + 1])


def _tiled_row(a, b, iters, t):
    n = a.shape[0]
    nt = (n - 2 + t - 1) // t
    for _ in range(iters):
        for ti in prange(nt):
            i0 = 1 + ti * t
            i1 = min(i0 + t, n - 1)
            for j0 in range(1, n - 1, t):
                j1 = min(j0 + t, n - 1)
                for i in range(i0, i1):
                    for j in range(j0, j1):
                        b[i, j] = 0.25 * (a[i - 1, j] + a[i + 1, j] + a[i, j - 1] + a[i, j + 1])
        for ti in prange(nt):
            i0 = 1 + ti * t
            i1 = min(i0 + t, n - 1)
            for j0 in range(1, n - 1, t):
                j1 = min(j0 + t, n - 1)
                for i in range(i0, i1):
                    for j in range(j0, j1):
                        a[i, j] = 0.25 * (b[i - 1, j] + b[i + 1, j] + b[i, j - 1] + b[i, j + 1])


def _tiled_col(a, b, iters, t):
    n = a.shape[0]
    nt = (n - 2 + t - 1) // t
    for _ in range(iters):
        for tj in prange(nt):
            j0 = 1 + tj * t
            j1 = min(j0 + t, n - 1)
            for i0 in range(1, n - 1, t):
                i1 = min(i0 + t, n - 1)
                for j in range(j0, j1):
                    for i in range(i0, i1):
                        b[i, j] = 0.25 * (a[i - 1, j] + a[i + 1, j] + a[i, j - 1] + a[i, j + 1])
        for tj in prange(nt):
            j0 = 1 + tj * t
            j1 = min(j0 + t, n - 1)
            for i0 in range(1, n - 1, t):
                i1 = min(i0 + t, n - 1)
                for j in range(j0, j1):
                    for i in range(i0, i1):
                        a[i, j] = 0.25 * (b[i - 1, j] + b[i + 1, j] + b[i, j - 1] + b[i, j + 1])


_BODIES = {("row", False): _untiled_row, ("col", False): _untiled_col,
           ("row", True): _tiled_row, ("col", True): _tiled_col}
_JIT_CACHE: Dict[tuple, Callable] = {}


def _jitted(order: str, tiled: bool, parallel: bool, fastmath: bool) -> Callable:
    key = (order, tiled, parallel, fastmath)
    if key not in _JIT_CACHE:
        _JIT_CACHE[key] = njit(parallel=parallel, fastmath=fastmath)(_BODIES[(order, tiled)])
    return _JIT_CACHE[key]


def numpy_baseline(a: np.ndarray, b: np.ndarray, iters: int) -> None:
    """NumPy slicing implementation (candidate id 0)."""
    for _ in range(iters):
        b[1:-1, 1:-1] = 0.25 * (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:])
        a[1:-1, 1:-1] = 0.25 * (b[:-2, 1:-1] + b[2:, 1:-1] + b[1:-1, :-2] + b[1:-1, 2:])


@dataclass(frozen=True)
class Candidate:
    cid: int
    name: str
    order: str      # "row" | "col" | "numpy"
    tile: int       # 0 = untiled
    parallel: bool
    fastmath: bool

    def make(self, iters: int) -> Callable[[np.ndarray, np.ndarray], None]:
        """Return f(a, b) running `iters` sweep-pairs in place (result in a)."""
        if self.order == "numpy":
            return lambda a, b: numpy_baseline(a, b, iters)
        fn = _jitted(self.order, self.tile > 0, self.parallel, self.fastmath)
        if self.tile > 0:
            t = self.tile
            return lambda a, b: fn(a, b, iters, t)
        return lambda a, b: fn(a, b, iters)


def build_candidates(kcfg: dict) -> List[Candidate]:
    """Candidate 0 = NumPy baseline; 1.. = Numba family from the config grid."""
    cands = [Candidate(0, "baseline_numpy", "numpy", 0, False, False)]
    cid = 1
    for order in kcfg["orders"]:
        for tile in kcfg["tiles"]:
            for par in kcfg["parallel"]:
                for fm in kcfg["fastmath"]:
                    name = f"{order}_t{tile}_{'par' if par else 'ser'}_{'fm' if fm else 'nofm'}"
                    cands.append(Candidate(cid, name, order, int(tile), bool(par), bool(fm)))
                    cid += 1
    return cands


def make_grid(n: int, seed: int = 0) -> np.ndarray:
    """Random interior in [0,1), boundary 1 (keeps values bounded, no denormals)."""
    rng = np.random.default_rng(seed)
    g = rng.random((n, n))
    g[0, :] = g[-1, :] = g[:, 0] = g[:, -1] = 1.0
    return g


def warmup(cands: List[Candidate], n: int, iters: int) -> None:
    """JIT-compile and run every candidate once (small grid, exercises tile paths)."""
    g = make_grid(max(n, 40), 1)
    b = g.copy()
    for c in cands:
        c.make(iters)(g.copy(), b.copy())
