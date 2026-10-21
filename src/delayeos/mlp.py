"""Two-layer tanh MLP with manual backprop (float64), MSE-to-one-hot loss, and the digits data subset.

Loss convention: L(theta) = (1/(2 n)) * sum_i sum_k (out_ik - y_ik)^2  (half the per-sample squared error, averaged
over samples).  The code never casts or conjugates, so it also runs on complex parameters; the tests use
complex-step differentiation to obtain exact gradients/Hessians independent of the finite-difference HVP.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MLPSpec:
    """Layer sizes of the d_in -> d_hidden -> d_out tanh MLP (with biases)."""

    d_in: int
    d_hidden: int
    d_out: int

    @property
    def n_params(self) -> int:
        return self.d_in * self.d_hidden + self.d_hidden + self.d_hidden * self.d_out + self.d_out

    def offsets(self) -> dict[str, tuple[int, int]]:
        """Half-open (start, stop) index ranges of W1, b1, W2, b2 in the flat parameter vector."""
        d, h, k = self.d_in, self.d_hidden, self.d_out
        o1 = d * h
        o2 = o1 + h
        o3 = o2 + h * k
        o4 = o3 + k
        return {"W1": (0, o1), "b1": (o1, o2), "W2": (o2, o3), "b2": (o3, o4)}

    def shapes(self) -> dict[str, tuple[int, ...]]:
        return {
            "W1": (self.d_in, self.d_hidden),
            "b1": (self.d_hidden,),
            "W2": (self.d_hidden, self.d_out),
            "b2": (self.d_out,),
        }


def load_digits_subset(n: int = 1000, standardize: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """First `n` rows of sklearn's bundled digits set; features standardized on the subset; one-hot targets."""
    from sklearn.datasets import load_digits

    X, y = load_digits(return_X_y=True)
    X = X[:n].astype(np.float64)
    y = y[:n]
    if standardize:
        X = (X - X.mean(0)) / (X.std(0) + 1e-8)  # constant pixels map to exactly 0
    Y = np.eye(10)[y]
    return X, Y


def unpack(theta: np.ndarray, spec: MLPSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Views (W1, b1, W2, b2) into the flat parameter vector."""
    o = spec.offsets()
    sh = spec.shapes()
    return tuple(theta[o[k][0]:o[k][1]].reshape(sh[k]) for k in ("W1", "b1", "W2", "b2"))  # type: ignore[return-value]


def init_params(spec: MLPSpec, rng: np.random.Generator) -> np.ndarray:
    """W1 ~ N(0, 1/d_in), W2 ~ N(0, 1/d_hidden), zero biases (flat float64 vector)."""
    W1 = rng.standard_normal((spec.d_in, spec.d_hidden)) / np.sqrt(spec.d_in)
    W2 = rng.standard_normal((spec.d_hidden, spec.d_out)) / np.sqrt(spec.d_hidden)
    return np.concatenate([W1.ravel(), np.zeros(spec.d_hidden), W2.ravel(), np.zeros(spec.d_out)])


def forward(theta: np.ndarray, X: np.ndarray, spec: MLPSpec) -> np.ndarray:
    W1, b1, W2, b2 = unpack(theta, spec)
    return np.tanh(X @ W1 + b1) @ W2 + b2


def loss_only(theta: np.ndarray, X: np.ndarray, Y: np.ndarray, spec: MLPSpec) -> float:
    R = forward(theta, X, spec) - Y
    return 0.5 * np.sum(R * R) / X.shape[0]


def loss_and_grad(theta: np.ndarray, X: np.ndarray, Y: np.ndarray, spec: MLPSpec) -> tuple[float, np.ndarray]:
    """Loss and flat gradient by manual backprop."""
    n = X.shape[0]
    W1, b1, W2, b2 = unpack(theta, spec)
    A = np.tanh(X @ W1 + b1)
    R = A @ W2 + b2 - Y
    L = 0.5 * np.sum(R * R) / n
    gW2 = A.T @ R / n
    gb2 = R.sum(0) / n
    gZ = (R @ W2.T) * (1.0 - A * A)
    gW1 = X.T @ gZ / n
    gb1 = gZ.sum(0) / n
    return L, np.concatenate([gW1.ravel(), gb1, gW2.ravel(), gb2])
