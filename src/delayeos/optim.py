"""Optimizers (Adam, Muon-like, frozen-preconditioner EMA momentum) and the delay / EF step wrapper.

Convention: every base optimizer exposes ``update(g) -> u`` returning the *descent step* (x_new = x - u, lr
already included) and ``precond_diag() -> D | None`` returning the diagonal D such that the update is
approximately lr * m / D (None when the optimizer is not diagonally preconditioned).

Delay and EF live in :class:`DelayedStepper`, independent of the base optimizer:
  sync   : the base optimizer sees the gradient g(x_t) at step t.
  delay  : (tau=1) it sees g(x_{t-1}); for t < tau the oldest available gradient g(x_0) is used (x_{-k} := x_0).
  ef     : delay plus update extrapolation, x_{t+1} = x_t - (2 u_t - u_{t-1}) where u_t is the base update built
           from the (stale) gradient; with u_s labelled by the iterate its gradient was evaluated at this reads
           x_{t+1} = x_t - 2 u_{t-1} + u_{t-2}, the linear weight prediction of the spec.  At the first step
           u_{-1} := u_0 (no extrapolation).
"""
from __future__ import annotations

from collections import deque
from typing import Optional, Protocol

import numpy as np

from .mlp import MLPSpec


class BaseOptimizer(Protocol):
    def update(self, g: np.ndarray) -> np.ndarray: ...

    def precond_diag(self) -> Optional[np.ndarray]: ...


class Adam:
    """Adam with bias correction, no weight decay: u = lr * m_hat / (sqrt(v_hat) + eps)."""

    def __init__(self, n: int, lr: float, beta1: float, beta2: float, eps: float) -> None:
        self.lr, self.beta1, self.beta2, self.eps = lr, beta1, beta2, eps
        self.m = np.zeros(n)
        self.v = np.zeros(n)
        self.t = 0

    def update(self, g: np.ndarray) -> np.ndarray:
        self.t += 1
        self.m = self.beta1 * self.m + (1.0 - self.beta1) * g
        self.v = self.beta2 * self.v + (1.0 - self.beta2) * g * g
        m_hat = self.m / (1.0 - self.beta1 ** self.t)
        return self.lr * m_hat / self.precond_diag()

    def precond_diag(self) -> np.ndarray:
        """D = sqrt(v_hat) + eps with the current bias-corrected second moment."""
        if self.t == 0:
            return np.full_like(self.v, 1.0)
        return np.sqrt(self.v / (1.0 - self.beta2 ** self.t)) + self.eps


class EMAMomentum:
    """EMA momentum with a frozen diagonal preconditioner D (theory/test base): u = lr * m / D, m_0 = 0."""

    def __init__(self, n: int, lr: float, beta1: float, D: float | np.ndarray = 1.0) -> None:
        self.lr, self.beta1 = lr, beta1
        self.D = np.broadcast_to(np.asarray(D, dtype=float), (n,)).copy()
        self.m = np.zeros(n)

    def update(self, g: np.ndarray) -> np.ndarray:
        self.m = self.beta1 * self.m + (1.0 - self.beta1) * g
        return self.lr * self.m / self.D

    def precond_diag(self) -> np.ndarray:
        return self.D


def polar_factor(M: np.ndarray, rtol: float = 1e-8) -> np.ndarray:
    """Polar factor U V^T of M via SVD, keeping only singular values > rtol * s_max.

    Truncation makes rank-deficient inputs (e.g. zero rows from constant pixels) map null directions to 0, as the
    Newton-Schulz iteration in Muon does; without it SVD returns arbitrary orthonormal completions there.
    """
    if not np.any(M):
        return np.zeros_like(M)
    U, s, Vt = np.linalg.svd(M, full_matrices=False)
    keep = s > rtol * s[0]
    return U[:, keep] @ Vt[keep]


class MuonLike:
    """Weights: polar factor of the heavy-ball momentum buffer (buf = mu*buf + g), step lr * polar(buf).
    Biases: Adam(beta1, beta2, eps) with the same lr.  (polar() is invariant to the buffer's scale, so EMA vs
    heavy-ball buffers are equivalent.)"""

    def __init__(self, spec: MLPSpec, lr: float, momentum: float = 0.95, bias_beta1: float = 0.9,
                 bias_beta2: float = 0.95, bias_eps: float = 1e-8, rank_rtol: float = 1e-8) -> None:
        self.spec, self.lr, self.mu, self.rank_rtol = spec, lr, momentum, rank_rtol
        off = spec.offsets()
        self.off = off
        self.shapes = spec.shapes()
        self.buf = {k: np.zeros(self.shapes[k]) for k in ("W1", "W2")}
        self.bias_idx = np.concatenate([np.arange(*off["b1"]), np.arange(*off["b2"])])
        self.bias_adam = Adam(self.bias_idx.size, lr, bias_beta1, bias_beta2, bias_eps)

    def update(self, g: np.ndarray) -> np.ndarray:
        u = np.zeros_like(g)
        for k in ("W1", "W2"):
            a, b = self.off[k]
            self.buf[k] = self.mu * self.buf[k] + g[a:b].reshape(self.shapes[k])
            u[a:b] = self.lr * polar_factor(self.buf[k], self.rank_rtol).ravel()
        u[self.bias_idx] = self.bias_adam.update(g[self.bias_idx])
        return u

    def precond_diag(self) -> Optional[np.ndarray]:
        return None


class DelayedStepper:
    """Wraps a base optimizer with gradient delay `tau` and optional update extrapolation (EF).

    ``step(x, g_new)`` takes the gradient evaluated at the *current* iterate x_t and applies the base optimizer
    to the gradient evaluated tau steps ago (clipped to g(x_0)); returns (x_{t+1}, g_used).
    """

    MODES = ("sync", "delay", "ef")

    def __init__(self, base: BaseOptimizer, mode: str, tau: int = 1) -> None:
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}, got {mode!r}")
        self.base = base
        self.mode = mode
        self.tau = 0 if mode == "sync" else tau
        self._grads: deque[np.ndarray] = deque(maxlen=self.tau + 1)
        self._u_prev: Optional[np.ndarray] = None

    def step(self, x: np.ndarray, g_new: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self._grads.append(g_new.copy())
        g_used = self._grads[0]  # g(x_{t-tau}), or g(x_0) while the history is still filling
        u = self.base.update(g_used)
        if self.mode == "ef":
            u_prev = u if self._u_prev is None else self._u_prev
            step_vec = 2.0 * u - u_prev
            self._u_prev = u
        else:
            step_vec = u
        return x - step_vec, g_used
