"""Tests of the fluid predictor (src/prefixmeta/fluid.py) on synthetic thrashing curves with known fixed points."""
from __future__ import annotations

import math

import numpy as np
import pytest

from prefixmeta.fluid import (FluidCurve, bc_curve, critical_burst, fixed_points, integrate_fluid, make_curve,
                              pav_nondecreasing, pav_nonincreasing, stability, unimodal_projection)


def tent(a=0.01, n_star=20.0, mu_inf=0.05, n_flat=60.0, n_max=300.0, extra=()):
    """mu = a n up to (n_star, a n_star), linear fall to mu_inf at n_flat, flat to n_max."""
    mu_star = a * n_star
    n = [0.0, n_star, n_flat, n_max] + list(extra)
    mu = [0.0, mu_star, mu_inf, mu_inf] + [mu_inf] * len(extra)
    order = np.argsort(n)
    return FluidCurve(np.array(n)[order], np.array(mu)[order]), dict(a=a, n_star=n_star, mu_star=mu_star, mu_inf=mu_inf,
                                                                    slope=(mu_inf - mu_star) / (n_flat - n_star), n_flat=n_flat)


# ------------------------------------------------------------------------------------------ isotonic helpers
def test_pav_known_examples():
    assert np.allclose(pav_nondecreasing([1, 3, 2, 4]), [1, 2.5, 2.5, 4])
    assert np.allclose(pav_nondecreasing([3, 2, 1]), [2, 2, 2])
    assert np.allclose(pav_nondecreasing([1, 2, 3]), [1, 2, 3])
    assert np.allclose(pav_nonincreasing([3, 1, 2]), [3, 1.5, 1.5])
    assert pav_nondecreasing([]).size == 0


def test_pav_matches_sklearn_when_available():
    sk = pytest.importorskip("sklearn.isotonic")
    rng = np.random.default_rng(0)
    for _ in range(50):
        y = rng.normal(size=int(rng.integers(2, 30)))
        ref = sk.IsotonicRegression(increasing=True).fit_transform(np.arange(len(y)), y)
        assert np.allclose(pav_nondecreasing(y), ref)
        ref2 = sk.IsotonicRegression(increasing=False).fit_transform(np.arange(len(y)), y)
        assert np.allclose(pav_nonincreasing(y), ref2)


def test_unimodal_projection_properties():
    rng = np.random.default_rng(1)
    for _ in range(200):
        y = np.abs(rng.normal(size=int(rng.integers(2, 25))))
        u = unimodal_projection(y)
        i = int(np.argmax(y))
        assert u.shape == y.shape
        assert u[i] == y[i] == u.max()                                   # the measured peak is preserved
        assert np.all(np.diff(u[: i + 1]) >= -1e-12) and np.all(np.diff(u[i:]) <= 1e-12)
        if np.all(np.diff(y[: i + 1]) >= 0) and np.all(np.diff(y[i:]) <= 0):
            assert np.array_equal(u, y)                                  # already unimodal: unchanged
        assert np.sum(u[: i + 1]) == pytest.approx(np.sum(y[: i + 1]))    # PAV preserves block means
    assert np.allclose(unimodal_projection([0.1, 0.3, 0.2, 0.5, 0.4, 0.45, 0.3]), [0.1, 0.25, 0.25, 0.5, 0.425, 0.425, 0.3])


def test_make_curve_adds_origin_sorts_and_projects():
    c = make_curve([20, 4, 8], [0.12, 0.05, 0.08], unimodal=True)
    assert np.array_equal(c.n, [0, 4, 8, 20]) and np.allclose(c.mu, [0, 0.05, 0.08, 0.12])
    # a wiggly tail is made non-increasing, raw keeps it
    n = [4, 8, 24, 40, 80, 300]
    mu = [0.05, 0.1, 0.2, 0.07, 0.072, 0.071]
    proj = make_curve(n, mu)
    raw = make_curve(n, mu, unimodal=False)
    assert np.all(np.diff(proj.mu[proj.i_star:]) <= 1e-12)
    assert raw.mu[-1] == 0.071 and proj.mu[-1] == pytest.approx((0.07 + 0.072 + 0.071) / 3)
    assert proj.mu_star == raw.mu_star == 0.2
    with pytest.raises(ValueError):
        make_curve([4, 4], [1, 2])
    with pytest.raises(ValueError):
        FluidCurve(np.array([0.0, 1.0, 1.0]), np.array([0.0, 1.0, 2.0]))
    with pytest.raises(ValueError):
        FluidCurve(np.array([0.0, 1.0]), np.array([0.0, -1.0]))


# ------------------------------------------------------------------------------------------ fixed points
def test_fixed_points_match_closed_form_on_a_tent_curve():
    c, p = tent()
    assert (c.n_star, c.mu_star, c.mu_inf, c.n_max) == (20.0, pytest.approx(0.2), pytest.approx(0.05), 300.0)
    for lam in (0.06, 0.1, 0.15, 0.19):
        fp = fixed_points(c, lam)
        n1 = lam / p["a"]
        n2 = p["n_star"] + (p["mu_star"] - lam) / (-p["slope"])
        assert fp.kind == "bistable"
        assert fp.n1 == pytest.approx(n1) and fp.n2 == pytest.approx(n2)
        assert fp.b_c == pytest.approx(n2 - n1) == pytest.approx(critical_burst(c, lam))
        assert float(c(fp.n1)) == pytest.approx(lam) and float(c(fp.n2)) == pytest.approx(lam)


def test_regimes_overload_critical_monostable():
    c, p = tent()
    over = fixed_points(c, 0.2001)
    assert over.kind == "overload" and math.isnan(over.n1) and math.isnan(over.n2) and math.isnan(over.b_c)
    crit = fixed_points(c, p["mu_star"])
    assert crit.kind == "critical" and crit.b_c == 0.0 and crit.n1 == crit.n2 == 20.0
    mono = fixed_points(c, 0.05)                                         # lambda == mu_inf: no instability
    assert mono.kind == "monostable" and mono.n2 == math.inf and mono.b_c == math.inf and mono.n1 == pytest.approx(5.0)
    low = fixed_points(c, 0.01)
    assert low.kind == "monostable" and low.n1 == pytest.approx(1.0)
    just = fixed_points(c, 0.0500001)                                    # just above mu_inf: n2 at the end of the fall
    assert just.kind == "bistable" and just.n2 == pytest.approx(60.0, abs=1e-3)
    assert fixed_points(c, 0.0).n1 == 0.0


def test_b_c_decreases_in_lambda_across_the_bistable_window():
    c, _ = tent()
    lams = np.linspace(0.0501, 0.1999, 60)
    b = bc_curve(c, lams)
    assert np.all(np.isfinite(b)) and np.all(b > 0)
    assert np.all(np.diff(b) < 0)                                        # n1 up, n2 down as lambda -> mu*
    assert b[0] > 40 and b[-1] < 1.0


def test_stability_classification_of_the_two_fixed_points():
    c, _ = tent()
    fp = fixed_points(c, 0.1)
    assert stability(c, fp.n1, 0.1) == "stable"
    assert stability(c, fp.n2, 0.1) == "unstable"


def test_fluid_ode_returns_below_b_c_and_diverges_above():
    c, _ = tent()
    lam = 0.1
    fp = fixed_points(c, lam)
    for frac, expect_back in ((0.9, True), (0.5, True), (1.1, False), (1.5, False)):
        n0 = fp.n1 + frac * fp.b_c
        ts, ns = integrate_fluid(c, lam, n0, t_end=20000.0, dt=0.1, n_cap=150.0)
        if expect_back:
            assert abs(ns[-1] - fp.n1) < 0.5, (frac, ns[-1])
        else:
            assert ns[-1] >= 150.0 - 1e-9, (frac, ns[-1])                 # escaped far beyond n2 and the fall (diverges)
    # from empty the system settles at n1
    ts, ns = integrate_fluid(c, lam, 0.0, t_end=2000.0, dt=0.1)
    assert ns[-1] == pytest.approx(fp.n1, abs=0.2)


def test_lru_like_cliff_between_two_grid_points():
    """A sharp cliff (LRU) between n = 28 and 32: n2 lies inside the cliff segment; a graceful (RANDOM-like) tail has a far
    larger critical burst at the same lambda."""
    n = [4, 8, 12, 16, 20, 24, 28, 32, 40, 100, 300]
    lru = [0.04, 0.086, 0.12, 0.163, 0.168, 0.17, 0.105, 0.066, 0.049, 0.047, 0.048]
    rnd = [0.04, 0.086, 0.12, 0.163, 0.168, 0.17, 0.15, 0.13, 0.10, 0.07, 0.06]
    cl, cr = make_curve(n, lru), make_curve(n, rnd)
    lam = 0.095
    f_l, f_r = fixed_points(cl, lam), fixed_points(cr, lam)
    assert f_l.kind == f_r.kind == "bistable"
    assert 28 < f_l.n2 < 32 and f_l.n1 == pytest.approx(f_r.n1)
    assert f_r.b_c > 2 * f_l.b_c
    # lambda below mu_inf of the graceful curve: monostable there, still bistable for the cliff curve
    assert fixed_points(cr, 0.05).kind == "monostable" and fixed_points(cl, 0.05).kind == "bistable"


def test_projection_changes_tail_not_the_rising_branch():
    n = [4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 64, 300]
    mu = [0.04, 0.086, 0.12, 0.163, 0.168, 0.17, 0.105, 0.066, 0.0487, 0.0472, 0.0473, 0.0481]
    proj, raw = make_curve(n, mu), make_curve(n, mu, unimodal=False)
    lam = 0.095
    assert fixed_points(proj, lam).n1 == pytest.approx(fixed_points(raw, lam).n1)
    assert fixed_points(proj, lam).n2 == pytest.approx(fixed_points(raw, lam).n2)   # crossing is on the steep fall
    assert proj.mu_inf != raw.mu_inf                                                 # tail wiggle pooled
    assert raw.mu_inf == 0.0481 and proj.mu_inf == pytest.approx((0.0472 + 0.0473 + 0.0481) / 3)
    # lam2 lies between the pooled tail value and the raw end value; the raw tail also dips to 0.0472 < lam2 at n = 48, so after
    # amendment 1 (monostable only if lambda <= min over n >= n* of mu) BOTH curves are bistable with n2 on the fall into the tail
    lam2 = 0.0478
    fr, fp = fixed_points(raw, lam2), fixed_points(proj, lam2)
    assert fr.kind == "bistable" and 40.0 < fr.n2 < 48.0                    # raw: first downward crossing (0.0487 -> 0.0472)
    assert fp.kind == "bistable" and 40.0 < fp.n2 < 48.0                    # pooled tail 0.04753 < lam2
    # a lambda below every tail value is monostable on both
    assert fixed_points(raw, 0.0470).kind == "monostable" and fixed_points(proj, 0.0470).kind == "monostable"


def test_plateau_peak_uses_the_first_argmax_and_n1_is_first_crossing():
    c = FluidCurve(np.array([0.0, 10.0, 20.0, 30.0, 100.0]), np.array([0.0, 0.2, 0.2, 0.1, 0.05]))
    assert c.n_star == 10.0
    fp = fixed_points(c, 0.2)
    assert fp.kind == "critical" and fp.n1 == 10.0 and fp.n2 == 10.0
    fp = fixed_points(c, 0.15)
    assert fp.n1 == pytest.approx(7.5)
    assert fp.n2 == pytest.approx(25.0)                                    # on the segment (20, .2)-(30, .1)


def test_lambda_equal_to_a_node_value_returns_the_node():
    c = FluidCurve(np.array([0.0, 10.0, 20.0, 40.0, 100.0]), np.array([0.0, 0.1, 0.2, 0.1, 0.02]))
    fp = fixed_points(c, 0.1)
    assert fp.n1 == pytest.approx(10.0) and fp.n2 == pytest.approx(40.0) and fp.b_c == pytest.approx(30.0)


# ------------------------------------------------------------------------------------------ raw (non-unimodal) curves, amendment 1
def test_raw_curve_with_a_tail_dip_is_bistable_not_monostable():
    """Review finding F8: a tail dip below lambda followed by a rise back above it (mu(n_max) > lambda) used to be classified
    monostable (b_c = +inf) on the raw curve."""
    n = [4, 8, 16, 24, 28, 32, 40, 60, 100, 200, 300]
    mu = [0.5, 1.0, 2.0, 3.0, 2.2, 1.5, 1.1, 1.1, 1.1, 1.6, 2.1]            # lambda_miss = 1 units; peak 3 at n = 24; dip to 1.1
    lam = 2.0
    raw, proj = make_curve(n, mu, unimodal=False), make_curve(n, mu)
    assert raw.mu_inf > lam and raw.mu_tail_min == pytest.approx(1.1)
    fr, fp = fixed_points(raw, lam), fixed_points(proj, lam)
    assert fr.kind == "bistable" and np.isfinite(fr.n2) and np.isfinite(fr.b_c)
    # n2 is the first downward crossing after n*: between n = 28 (mu 2.2) and 32 (mu 1.5), at 28 + 4 (2.2 - 2.0) / (2.2 - 1.5)
    assert fr.n2 == pytest.approx(28.0 + 4.0 * (2.2 - 2.0) / (2.2 - 1.5))
    # the unimodal projection pools the non-monotone tail; it is bistable too (its tail value 1.4 < lambda)
    assert fp.kind == "bistable" and fp.n2 > 24.0
    # unimodal curves are unaffected: mu_tail_min == mu_inf
    c, _ = tent()
    assert c.mu_tail_min == c.mu_inf


def test_raw_curve_with_a_tail_bump_does_not_diverge_beyond_n2():
    """The documented caveat: with a tail bump above lambda, n2 - n1 does not imply divergence; the ODE settles at the
    intermediate stable point where the bump comes back down through lambda."""
    n = [4, 8, 16, 24, 28, 32, 40, 50, 60, 70, 100, 300]
    mu = [0.5, 1.0, 2.0, 3.0, 2.2, 1.5, 1.1, 1.4, 2.3, 1.5, 1.1, 1.05]      # bump to 2.3 at n = 60
    lam = 2.0
    raw = make_curve(n, mu, unimodal=False)
    fp = fixed_points(raw, lam)
    assert fp.kind == "bistable"
    ts, ns = integrate_fluid(raw, lam, fp.n1 + fp.b_c + 1.0, t_end=50000.0, dt=0.05, n_cap=250.0)
    assert ns[-1] < 250.0 - 1e-9                                            # did not diverge
    # settled at the upward crossing of lambda on the rising side of the bump (n = 50 + 10 (2.0 - 1.4) / (2.3 - 1.4)), a stable point
    assert ns[-1] == pytest.approx(50.0 + 10.0 * (2.0 - 1.4) / (2.3 - 1.4), abs=0.05)
    # a burst below b_c still returns to n1
    ts, ns = integrate_fluid(raw, lam, fp.n1 + 0.5 * fp.b_c, t_end=50000.0, dt=0.05, n_cap=250.0)
    assert abs(ns[-1] - fp.n1) < 0.5
