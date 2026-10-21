"""Tests for the delayed-gradient edge-of-stability toy (src/delayeos)."""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import yaml

from delayeos.curvature import exact_hessian, fd_hvp, lambda_max, sharpness
from delayeos.mlp import MLPSpec, init_params, load_digits_subset, loss_and_grad, loss_only
from delayeos.optim import Adam, DelayedStepper, EMAMomentum, MuonLike, polar_factor
from delayeos.train import batch_stream, expand_grid, run_one

ROOT = Path(__file__).resolve().parents[1]


def load_cfg() -> dict:
    with open(ROOT / "configs" / "delay_eos.yaml") as f:
        return yaml.safe_load(f)


def small_problem(seed: int = 0, n: int = 9, spec: MLPSpec = MLPSpec(5, 4, 3)):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, spec.d_in))
    Y = np.eye(spec.d_out)[rng.integers(0, spec.d_out, n)]
    theta = init_params(spec, rng) + 0.3 * rng.standard_normal(spec.n_params)
    return spec, X, Y, theta


def tiny_cfg(steps: int = 60, every: int = 20) -> dict:
    cfg = load_cfg()
    cfg["data"]["n"] = 200
    cfg["steps"] = steps
    cfg["curvature"].update(every=every, power_iters=6)
    cfg["metrics"].update(final_loss_window=10, curvature_window=40)
    cfg["batches"] = [200, 32]
    return cfg


# ----------------------------------------------------------------------------- model / curvature
def test_gradient_matches_complex_step():
    spec, X, Y, theta = small_problem()
    L, g = loss_and_grad(theta, X, Y, spec)
    assert L == pytest.approx(loss_only(theta, X, Y, spec))
    h = 1e-30
    g_cs = np.empty_like(g)
    for j in range(theta.size):
        th = theta.astype(complex)
        th[j] += 1j * h
        g_cs[j] = loss_and_grad(th, X, Y, spec)[0].imag / h
    np.testing.assert_allclose(g, g_cs, rtol=1e-10, atol=1e-12)


def test_hvp_matches_exact_hessian():
    spec, X, Y, theta = small_problem(seed=1)
    H = exact_hessian(theta, X, Y, spec)
    assert np.allclose(H, H.T, atol=1e-10)
    grad_fn = lambda th: loss_and_grad(th, X, Y, spec)[1]  # noqa: E731
    rng = np.random.default_rng(5)
    for scale in (1.0, 1e-3, 1e3):  # HVP is invariant to the scale of the probe direction
        z = scale * rng.standard_normal(theta.size)
        hv = fd_hvp(grad_fn, theta, z, rel=1e-4)
        ref = H @ z
        assert np.linalg.norm(hv - ref) / np.linalg.norm(ref) < 1e-5


def test_sharpness_matches_eigvalsh_plain_and_preconditioned():
    spec, X, Y, theta = small_problem(seed=2)
    H = exact_hessian(theta, X, Y, spec)
    rng = np.random.default_rng(3)
    v0 = rng.standard_normal(theta.size)
    # make the top eigenvalue dominant in magnitude: use the Gauss-Newton-like regime near a trained point
    D = np.exp(rng.uniform(-1.0, 1.0, theta.size))
    A = H / np.sqrt(np.outer(D, D))
    for Dm, Am in ((None, H), (D, A)):
        ev = np.linalg.eigvalsh(Am)
        r = sharpness(theta, X, Y, spec, v0, Dm, iters=400, rel=1e-4)
        assert r["lam"] == pytest.approx(ev[-1], rel=1e-3)


def test_lambda_max_shift_recovers_largest_algebraic():
    rng = np.random.default_rng(0)
    Q, _ = np.linalg.qr(rng.standard_normal((6, 6)))
    A = Q @ np.diag([-5.0, 0.5, 1.0, 1.5, 2.0, 3.0]) @ Q.T
    r = lambda_max(lambda v: A @ v, rng.standard_normal(6), iters=300)
    assert r["shifted"]
    assert r["lam"] == pytest.approx(3.0, rel=1e-6)


# ----------------------------------------------------------------------------- optimizers
def test_adam_matches_reference_formula():
    rng = np.random.default_rng(0)
    n, lr, b1, b2, eps = 7, 0.01, 0.9, 0.95, 1e-8
    adam = Adam(n, lr, b1, b2, eps)
    m = np.zeros(n); v = np.zeros(n)
    for t in range(1, 8):
        g = rng.standard_normal(n)
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        ref = lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
        np.testing.assert_allclose(adam.update(g), ref, rtol=1e-13)
    np.testing.assert_allclose(adam.precond_diag(), np.sqrt(v / (1 - b2 ** 7)) + eps, rtol=1e-13)


def test_polar_factor_properties():
    rng = np.random.default_rng(1)
    M = rng.standard_normal((6, 4))
    P = polar_factor(M)
    np.testing.assert_allclose(P.T @ P, np.eye(4), atol=1e-12)
    # P = M (M^T M)^{-1/2}
    w, V = np.linalg.eigh(M.T @ M)
    np.testing.assert_allclose(P, M @ (V * w ** -0.5) @ V.T, atol=1e-10)
    # rank-deficient with an exactly-zero row (constant pixel): null directions map to 0, zero row stays 0
    M2 = rng.standard_normal((6, 6)); M2[2] = 0.0
    P2 = polar_factor(M2)
    np.testing.assert_allclose(P2[2], 0.0, atol=1e-12)
    s = np.linalg.svd(P2, compute_uv=False)
    assert np.sum(s > 0.5) == 5 and s.max() == pytest.approx(1.0)
    assert not np.any(polar_factor(np.zeros((3, 3))))


def test_muon_like_weights_polar_biases_adam():
    spec = MLPSpec(5, 4, 3)
    rng = np.random.default_rng(2)
    g = rng.standard_normal(spec.n_params)
    opt = MuonLike(spec, lr=0.01, momentum=0.95)
    u = opt.update(g)
    off = spec.offsets()
    for k in ("W1", "W2"):
        a, b = off[k]
        s = np.linalg.svd(u[a:b].reshape(spec.shapes()[k]), compute_uv=False)
        assert s.max() == pytest.approx(0.01) and s.min() > 0
    ref = Adam(spec.d_hidden + spec.d_out, 0.01, 0.9, 0.95, 1e-8).update(
        np.concatenate([g[slice(*off["b1"])], g[slice(*off["b2"])]]))
    np.testing.assert_allclose(np.concatenate([u[slice(*off["b1"])], u[slice(*off["b2"])]]), ref)


# ----------------------------------------------------------------------------- delay / EF
class RecordingSGD:
    def __init__(self, lr: float) -> None:
        self.lr, self.seen = lr, []

    def update(self, g):
        self.seen.append(g.copy())
        return self.lr * g

    def precond_diag(self):
        return None


def test_delay_mode_uses_stale_gradient():
    spec, X, Y, x = small_problem(seed=4)
    grad = lambda th: loss_and_grad(th, X, Y, spec)[1]  # noqa: E731
    lr, T = 0.05, 8
    for mode in ("sync", "delay"):
        base = RecordingSGD(lr)
        stepper = DelayedStepper(base, mode, tau=1)
        xs = [x.copy()]
        for t in range(T):
            xs.append(stepper.step(xs[-1], grad(xs[-1]))[0])
        for t in range(T):
            expected = grad(xs[t]) if mode == "sync" else grad(xs[max(t - 1, 0)])
            np.testing.assert_allclose(base.seen[t], expected, rtol=0, atol=0)
        for t in range(T):  # x_{t+1} = x_t - lr * g(x_{t-1})  (delay) / g(x_t) (sync)
            src = xs[t] if mode == "sync" else xs[max(t - 1, 0)]
            np.testing.assert_allclose(xs[t + 1], xs[t] - lr * grad(src))


def test_ef_is_update_extrapolation():
    spec, X, Y, x = small_problem(seed=6)
    grad = lambda th: loss_and_grad(th, X, Y, spec)[1]  # noqa: E731
    lr = 0.02
    base = RecordingSGD(lr)
    stepper = DelayedStepper(base, "ef", tau=1)
    xs = [x.copy()]
    for _ in range(6):
        xs.append(stepper.step(xs[-1], grad(xs[-1]))[0])
    u = [lr * g for g in base.seen]  # base updates u_t built from the stale gradient
    np.testing.assert_allclose(xs[1], xs[0] - u[0])  # first step: no extrapolation
    for t in range(1, 6):
        np.testing.assert_allclose(xs[t + 1], xs[t] - 2 * u[t] + u[t - 1])


def test_grad_history_wiring_in_train_matches_manual_loop():
    """run_one in delay mode == manual Adam loop that feeds the gradient evaluated at x_{t-1}."""
    cfg = tiny_cfg(steps=25, every=0)
    X, Y = load_digits_subset(cfg["data"]["n"])
    run = {"optimizer": "adam", "beta1": 0.9, "mode": "delay", "batch": 200, "eta": 0.01, "seed": 3}
    out = run_one(run, cfg, X, Y)
    spec = MLPSpec(64, 64, 10)
    s_init, *_ = np.random.SeedSequence(3).spawn(3)
    x = init_params(spec, np.random.default_rng(s_init))
    adam = Adam(spec.n_params, 0.01, 0.9, 0.95, 1e-8)
    xs = [x]
    for t in range(25):
        g_stale = loss_and_grad(xs[max(t - 1, 0)], X, Y, spec)[1]
        xs.append(xs[-1] - adam.update(g_stale))
    np.testing.assert_allclose(out["theta"], xs[-1], rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("beta1,mode,thr", [
    (0.9, "sync", 38.0), (0.9, "delay", 1.0), (0.9, "ef", 2.7016),
    (0.99, "delay", 1.0), (0.99, "ef", 9.5125),
])
def test_linear_stability_thresholds_match_theory(beta1, mode, thr):
    """1-D quadratic f = y^2/2 with frozen-D EMA momentum: stable just below, unstable just above the cap."""
    def final_amp(lam: float) -> float:
        base = EMAMomentum(1, lr=lam, beta1=beta1, D=1.0)
        stepper = DelayedStepper(base, mode, tau=1)
        y = np.array([1.0])
        for _ in range(60000):
            y, _ = stepper.step(y, y.copy())
            if abs(y[0]) > 1e12:
                break
        return abs(y[0])

    assert final_amp(0.93 * thr) < 1e-3
    assert final_amp(1.07 * thr) > 1e3


# ----------------------------------------------------------------------------- run-level properties
def test_determinism_and_curvature_does_not_perturb_trajectory():
    cfg = tiny_cfg(steps=60, every=20)
    X, Y = load_digits_subset(cfg["data"]["n"])
    for opt, beta1, mode in (("adam", 0.9, "ef"), ("muon", float("nan"), "delay")):
        run = {"optimizer": opt, "beta1": beta1, "mode": mode, "batch": 32, "eta": 0.01, "seed": 1}
        a = run_one(run, cfg, X, Y)
        b = run_one(run, cfg, X, Y)
        np.testing.assert_array_equal(a["loss"], b["loss"])
        assert len(a["curv"]) == len(b["curv"]) == 3
        for r1, r2 in zip(a["curv"], b["curv"]):
            np.testing.assert_array_equal(list(r1.values()), list(r2.values()))
        cfg0 = copy.deepcopy(cfg); cfg0["curvature"]["every"] = 0
        c = run_one(run, cfg0, X, Y)
        np.testing.assert_array_equal(a["loss"], c["loss"])
        np.testing.assert_array_equal(a["theta"], c["theta"])
        d = run_one({**run, "seed": 2}, cfg, X, Y)
        assert not np.array_equal(a["loss"], d["loss"])


def test_same_seed_shares_init_and_batches_across_modes():
    cfg = tiny_cfg(steps=3, every=0)
    X, Y = load_digits_subset(cfg["data"]["n"])
    base = {"optimizer": "adam", "beta1": 0.9, "batch": 32, "eta": 0.01, "seed": 7}
    l_sync = run_one({**base, "mode": "sync"}, cfg, X, Y)["loss"]
    l_delay = run_one({**base, "mode": "delay"}, cfg, X, Y)["loss"]
    assert l_sync[0] == l_delay[0]                    # same init
    assert l_sync[1] == pytest.approx(l_delay[1])     # step 0 is identical: x_{-1} := x_0 and same batch


def test_batch_stream_epochs_cover_data_without_repeats():
    rng = np.random.default_rng(0)
    it = batch_stream(rng, 100, 25)
    epoch = np.concatenate([next(it) for _ in range(4)])
    assert sorted(epoch) == list(range(100))
    assert next(batch_stream(rng, 100, 100)) is None


def test_divergence_flag_triggers():
    cfg = tiny_cfg(steps=200, every=0)
    cfg["metrics"]["divergence_loss"] = 1e-6  # any realistic loss exceeds this at step 0
    X, Y = load_digits_subset(cfg["data"]["n"])
    run = {"optimizer": "adam", "beta1": 0.9, "mode": "sync", "batch": 200, "eta": 0.01, "seed": 0}
    s = run_one(run, cfg, X, Y)["summary"]
    assert s["diverged"] == 1 and s["div_step"] == 0 and np.isnan(s["final_loss"])


# ----------------------------------------------------------------------------- config
def test_config_first_key_is_research_question_and_grid_size():
    with open(ROOT / "configs" / "delay_eos.yaml") as f:
        first_key = next(iter(yaml.safe_load(f)))
    assert first_key == "research_question"
    runs = expand_grid(load_cfg())
    assert len(runs) == 144  # 108 Adam + 36 Muon-like
    assert all(r["batch"] == 1000 for r in runs[:72])  # full batch first
