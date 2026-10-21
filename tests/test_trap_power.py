"""The trap-criterion operating-characteristic script (experiments/agentload_trap_power.py): checked against closed forms."""
import importlib.util

import numpy as np
import pytest
from scipy import stats

from conftest import REPO

spec = importlib.util.spec_from_file_location("trap_power", REPO / "experiments" / "agentload_trap_power.py")
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

LAM_MISS, W, DT = 0.0474, 3000.0, 10.0


def sim(mult, seed=0, n=40000, err=0.0, tol=0.15, frac=0.5):
    return tp.simulate(np.random.default_rng(seed), mult * LAM_MISS, LAM_MISS, W, DT, n, err, tol, frac)


def test_criterion_a_matches_the_poisson_closed_form():
    mu = LAM_MISS * W                                                  # expected completions in the window
    lo, hi = int(np.ceil(0.85 * mu)), int(np.floor(1.15 * mu))
    exact = stats.poisson.cdf(hi, mu) - stats.poisson.cdf(lo - 1, mu)
    assert sim(1.6)["p_a"] == pytest.approx(exact, abs=0.01)


def test_slope_mean_is_lambda_minus_lambda_miss_and_power_grows_with_lambda():
    out = {m: sim(m, n=20000) for m in (1.1, 1.3, 1.6, 2.0)}
    for m, r in out.items():
        assert r["slope_mean"] == pytest.approx((m - 1) * LAM_MISS, abs=0.0015)
        assert r["slope_threshold"] == pytest.approx(0.5 * (m - 1) * LAM_MISS)
    p = [out[m]["p_b"] for m in (1.1, 1.3, 1.6, 2.0)]
    assert p == sorted(p) and p[0] < 0.75 and p[-1] > 0.99


def test_deterministic_per_seed_and_estimator_noise_lowers_power():
    assert sim(1.3, seed=3, n=2000) == sim(1.3, seed=3, n=2000)
    assert sim(1.3, seed=3, n=2000) != sim(1.3, seed=4, n=2000)
    assert sim(1.6, err=0.05, n=20000)["p_trapped"] < sim(1.6, err=0.0, n=20000)["p_trapped"]
