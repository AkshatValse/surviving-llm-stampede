"""Curvature measurement: finite-difference Hessian-vector products and power iteration for
lambda_max(H) and lambda_max(D^{-1/2} H D^{-1/2}) (preconditioned sharpness)."""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from .mlp import MLPSpec, loss_and_grad

Vec = np.ndarray


def fd_hvp(grad_fn: Callable[[Vec], Vec], x: Vec, z: Vec, rel: float = 1e-4) -> Vec:
    """Central-difference H(x) z ~ (g(x + e z) - g(x - e z)) / (2 e), perturbation norm e*||z|| = rel * ||x||."""
    nz = float(np.linalg.norm(z))
    if nz == 0.0:
        return np.zeros_like(z)
    scale = max(float(np.linalg.norm(x)), 1e-8)
    e = rel * scale / nz
    return (grad_fn(x + e * z) - grad_fn(x - e * z)) / (2.0 * e)


def power_iteration(matvec: Callable[[Vec], Vec], v0: Vec, iters: int = 30) -> tuple[float, Vec, float]:
    """Largest-|eigenvalue| of a symmetric operator: (Rayleigh quotient, next unit iterate, relative residual)."""
    v = v0 / np.linalg.norm(v0)
    lam, resid = 0.0, float("nan")
    for _ in range(iters):
        w = matvec(v)
        lam = float(v @ w)
        nw = float(np.linalg.norm(w))
        resid = float(np.linalg.norm(w - lam * v) / max(abs(lam), 1e-300))
        if nw == 0.0:
            return 0.0, v, 0.0
        v = w / nw
    return lam, v, resid


def lambda_max(matvec: Callable[[Vec], Vec], v0: Vec, iters: int = 30) -> dict:
    """lambda_max (algebraically largest eigenvalue) by power iteration.

    If the dominant-magnitude eigenvalue is negative (Rayleigh quotient < 0), a second power iteration on
    (A - lam I) recovers the largest algebraic eigenvalue; ``shifted`` records that this happened.
    """
    lam, v, resid = power_iteration(matvec, v0, iters)
    shifted = False
    if lam < 0.0:
        shift = lam
        # restart from the caller's v0: the current iterate sits on the (now smallest) shifted eigenvector
        lam2, v, resid = power_iteration(lambda u: matvec(u) - shift * u, v0, iters)
        lam, shifted = lam2 + shift, True
    return {"lam": lam, "v": v, "resid": resid, "shifted": shifted}


def sharpness(theta: Vec, X: np.ndarray, Y: np.ndarray, spec: MLPSpec, v0: Vec, D: Optional[Vec] = None,
              iters: int = 30, rel: float = 1e-4) -> dict:
    """lambda_max of H (D is None) or of D^{-1/2} H D^{-1/2}, with H the Hessian of the loss on (X, Y) at theta."""

    def grad_fn(th: Vec) -> Vec:
        return loss_and_grad(th, X, Y, spec)[1]

    if D is None:
        def matvec(w: Vec) -> Vec:
            return fd_hvp(grad_fn, theta, w, rel)
    else:
        dm = 1.0 / np.sqrt(D)

        def matvec(w: Vec) -> Vec:
            return dm * fd_hvp(grad_fn, theta, dm * w, rel)

    return lambda_max(matvec, v0, iters)


def exact_hessian(theta: Vec, X: np.ndarray, Y: np.ndarray, spec: MLPSpec, h: float = 1e-30) -> np.ndarray:
    """Exact Hessian by complex-step differentiation of the analytic gradient (no subtractive cancellation).
    O(P) gradient evaluations; for small test networks only."""
    P = theta.size
    H = np.empty((P, P))
    for j in range(P):
        th = theta.astype(complex)
        th[j] += 1j * h
        H[:, j] = loss_and_grad(th, X, Y, spec)[1].imag / h
    return 0.5 * (H + H.T)
