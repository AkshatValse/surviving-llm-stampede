"""Seed-bootstrap utilities for the round-4 evaluation (amendment 1 of configs/prefix_meta_r4_prereg.yaml).

The unit of replication is the SEED. A bootstrap resample draws ``S`` seeds with replacement from the ``S`` registered seeds
(S = 3 for the curve) and uses the SAME resampled seed set for every grid point, policy and k within that resample, so a resample
is a coherent set of per-seed curves (cells that share a seed are CRN-coupled, never independent). With S = 3 the bootstrap is
crude (27 equally likely index triples); it is reported as a noise indicator, not as a calibrated confidence interval.

Randomness: ``numpy.random.default_rng(SeedSequence([entropy, crc32(tag)]))``, one stream per tag, so a quantity's resamples do
not depend on the order in which quantities are evaluated, and are reproducible. No global RNG state is used.
"""
from __future__ import annotations

import math
import zlib
from typing import Dict, Sequence

import numpy as np

BOOT_ENTROPY = 20261021        # registered in amendment 1
BOOT_N = 2000                  # registered in amendment 1
BOOT_LEVEL = 0.95              # registered in amendment 1 (percentile interval)


def boot_rng(tag: str, entropy: int = BOOT_ENTROPY) -> np.random.Generator:
    """The generator of the bootstrap stream ``tag``."""
    return np.random.default_rng(np.random.SeedSequence([int(entropy), zlib.crc32(tag.encode("utf-8"))]))


def resample_indices(tag: str, n_seeds: int, n_boot: int = BOOT_N, entropy: int = BOOT_ENTROPY) -> np.ndarray:
    """``(n_boot, n_seeds)`` integer array: the seeds (column indices) drawn with replacement in each resample."""
    return boot_rng(tag, entropy).integers(0, int(n_seeds), size=(int(n_boot), int(n_seeds)))


def boot_means(M: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Bootstrap seed-mean curves. ``M``: ``(n_grid, n_seeds)`` per-seed values; returns ``(n_boot, n_grid)``."""
    return M[:, idx].mean(axis=2).T


def _pct_sorted(x: np.ndarray, q: float) -> float:
    """Linear-interpolation percentile ``q`` in [0, 1] of a SORTED array that may contain +inf (inf stays inf)."""
    n = len(x)
    pos = q * (n - 1)
    i = int(math.floor(pos))
    f = pos - i
    a = float(x[i])
    if f == 0.0 or i + 1 >= n:
        return a
    b = float(x[i + 1])
    if math.isinf(b) or math.isinf(a):
        return b if b > a else a
    return a + (b - a) * f


def interval(x: Sequence[float], level: float = BOOT_LEVEL) -> Dict[str, float]:
    """Percentile interval of replicates ``x``: NaN replicates are dropped and counted, +inf is kept.

    Returns ``{lo, median, hi, n, n_nan, n_inf}`` (all NaN if no finite-or-inf replicate remains)."""
    a = np.asarray(x, dtype=float)
    n_nan = int(np.isnan(a).sum())
    a = np.sort(a[~np.isnan(a)])
    n_inf = int(np.isposinf(a).sum())
    if a.size == 0:
        return {"lo": math.nan, "median": math.nan, "hi": math.nan, "n": 0, "n_nan": n_nan, "n_inf": 0}
    alpha = (1.0 - level) / 2.0
    return {"lo": _pct_sorted(a, alpha), "median": _pct_sorted(a, 0.5), "hi": _pct_sorted(a, 1.0 - alpha),
            "n": int(a.size), "n_nan": n_nan, "n_inf": n_inf}


def se_rows(M: np.ndarray) -> np.ndarray:
    """Standard error of each row of ``M`` (sample sd with ddof 1 over the seeds / sqrt(S)); NaN if S < 2."""
    S = M.shape[1]
    if S < 2:
        return np.full(M.shape[0], math.nan)
    return M.std(axis=1, ddof=1) / math.sqrt(S)
