"""Tests for analysis/theory/fluid_rigorous (the mean-field model of notes/THEORY_r13_fluid_rigorous.md).

Checks (i) the inputs (calibrated constants, workload moments), (ii) the lemmas the propositions rest on (server and
LRU monotonicity, the end points of the solution curve), (iii) the exact statements (time-rescaling invariance of the
window, monotonicity of the window in the tool time and GPU speed, the stability criterion, the open-system phase line,
the round-robin identity gap/R = sum(P + d)/M), and (iv) regression values of the validation numbers quoted in the note.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pytest
import yaml

from analysis.theory.fluid_rigorous.edge import escape_probability
from analysis.theory.fluid_rigorous.model import (Costs, Model, Workload, curve_on_grid, feedback_map, fixed_points,
                                                  kv_dispersion, open_equilibria, summarize_curve, window_upper_bound)
from analysis.theory.fluid_rigorous.trapped import round_robin_trap

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def m300():
    m = Model(Workload(), Costs(), 300000.0)
    return m, summarize_curve(m)


def test_costs_equal_the_calibration_file():
    cal = yaml.safe_load(open(os.path.join(ROOT, "calibration", "round6_server_log_fit", "calibration.yaml")))["engine"]
    c = Costs()
    assert c.a == cal["iter_fixed_s"] and c.f == cal["iter_floor_s"] and c.b == cal["per_token_s"]
    assert c.cd == cal["decode_attn_s"] and c.cp == cal["prefill_attn_s"] and cal["prefill_attn_ctx"] == "mid"
    assert c.chunk == cal["prefill_chunk_budget"] and c.norm == cal["attn_ctx_norm"]


def test_workload_moments_match_the_record():
    wl = Workload()
    assert wl.ET == pytest.approx(14.761055, abs=1e-5)                 # E[T] of min(Geometric(1/15), 60)
    assert wl.tokens_all_miss == pytest.approx(154529, rel=2e-4)       # E[W] all-miss tokens per session
    assert wl.P[0] == 2000 and wl.P[1] - wl.P[0] == 650 and wl.E[0] == 2100
    kd = kv_dispersion(wl, 1.7)
    assert 10300 < kd["E_lb"] < 10700                                  # ~10.6k length-biased footprint
    assert 1.4 < kd["I_D"] < 1.8


def test_server_is_monotone_in_rate_and_hits(m300):
    m, _ = m300
    for h in (0.0, 0.5, 0.95):
        nus = np.linspace(0.01, m.nu_cap(h) * 0.999, 40)
        K = [m.server(nu, h).K_run for nu in nus]
        S = [m.server(nu, h).S_bar for nu in nus]
        assert all(np.diff(K) > 0) and all(np.diff(S) > 0)
        assert m.server(m.nu_cap(h) * (1 - 1e-9), h).K_run > 1e7        # (C1): reservations blow up at capacity
    for nu in (0.5, 1.0, 2.0):
        Ks = [m.server(nu, h).K_run for h in np.linspace(0, 0.99, 12) if m.server(nu, h).feasible]
        assert all(np.diff(Ks) < 0)


def test_lru_kv_time_is_strictly_increasing(m300):
    m, _ = m300
    R = np.linspace(0, 200, 300)
    D = [m.D(r) for r in R]
    assert D[0] == 0 and all(np.diff(D) > 0)


def test_curve_end_points(m300):
    m, cs = m300
    b = m.bad()
    assert b["K_run"] == pytest.approx(m.M, rel=1e-9)
    p_far, p_near = m.point(1e5), m.point(1e-4)
    assert p_far["n"] < 0.2 and p_far["mu"] < 0.002                       # R -> inf: empty system
    assert p_near["nu"] == pytest.approx(b["nu"], rel=2e-3)               # R -> 0: the all-miss state
    assert p_near["n"] == pytest.approx(b["n_b"], rel=2e-3)
    assert cs.mu_max > cs.mu_b                                            # a peak above the all-miss level


def test_stability_criterion_matches_the_feedback_map(m300):
    m, cs = m300
    # on the computed curve dn/dR < 0 everywhere (no fold) and every fixed point of Phi_n has slope < 1
    n = np.array([p["n"] for p in cs.pts])
    assert np.all(np.diff(n) > 0) and not cs.bistable
    for frac in (0.6, 0.9, 0.99):
        fps = fixed_points(m, frac * cs.n_b, ngrid=121)
        assert len(fps) == 1 and fps[0]["stable"] and fps[0]["slope"] < 1.0
    # dPhi/dn <= 0 (condition C2) at a few points
    for nn in (20.0, 28.0, 31.0):
        assert feedback_map(m, nn + 0.05, 0.6)["phi"] <= feedback_map(m, nn, 0.6)["phi"] + 1e-12


def test_window_time_rescaling_is_exact():
    wl = Workload()
    for s in (2.0, 3.0):
        a = summarize_curve(Model(wl, Costs().scaled(s), 300000.0))
        b = summarize_curve(Model(Workload(zbar=wl.zbar * s), Costs(), 300000.0))
        assert a.window == pytest.approx(b.window, rel=1e-3)
        assert a.mu_max == pytest.approx(s * b.mu_max, rel=1e-3)
        assert a.mu_b == pytest.approx(s * Model(wl, Costs(), 300000.0).bad()["mu"], rel=1e-6)


def test_window_decreases_with_tool_time_and_gpu_speed():
    wins = [summarize_curve(Model(Workload(zbar=z), Costs(), 300000.0)).window for z in (2.0, 5.0, 10.0, 20.0)]
    assert all(np.diff(wins) < 0)
    winss = [summarize_curve(Model(Workload(), Costs().scaled(s), 300000.0)).window for s in (1.0, 2.0, 4.0)]
    assert all(np.diff(winss) < 0)


def test_explicit_upper_bound_holds(m300):
    m, cs = m300
    ub = window_upper_bound(m, nh=120)
    assert ub["omega_upper"] >= cs.window


def test_open_phase_line(m300):
    m, cs = m300
    for lam in (0.09, 0.12, 0.18, 0.23):
        eq = open_equilibria(cs, lam)
        assert eq.n1 < cs.n_star < eq.n_u <= cs.n_b + 1e-9
        ng = np.linspace(0, cs.n_b, 3000)
        mu, _, _ = curve_on_grid(cs, ng)
        assert np.interp(eq.n1, ng, mu) == pytest.approx(lam, rel=2e-3)
        assert eq.trapped_drift > 0                                      # past n_u the backlog grows at lam - mu_b
    eq_low = open_equilibria(cs, 0.9 * cs.mu_b)
    assert eq_low.trapped_drift < 0                                      # below lambda_miss no trap


def test_round_robin_identity(m300):
    m, cs = m300
    tr = round_robin_trap(m, 0.0966, 8.5, t_end=8700.0)
    # gap/R = c / (M / churn) = sum(P + d)/M  (definition-level identity of the round-robin)
    assert np.allclose(tr["gap_over_R"], tr["c"] / tr["R"], rtol=1e-9)
    t, n = tr["t"], tr["n_sys"]
    # the burst cohort first drains (cheap early turns), then the backlog grows above lambda_miss (measured: minimum
    # 135-172 sessions 300-1300 s after the burst, then growth)
    j = int(np.argmin(n[t > 1300.0])) + int(np.sum(t <= 1300.0))
    assert 130.0 < n[j] < 175.0 and 1300.0 < t[j] < 3500.0
    assert n[-1] > n[j] + 20.0
    assert 0.95 < tr["tok"][-1] / m.bad()["tok"] < 1.06


def test_escape_probability_increases_with_rate(m300):
    m, cs = m300
    ng = np.linspace(0, cs.n_b * 1.5, 3000)
    mu, _, _ = curve_on_grid(cs, ng)
    f = lambda x: np.interp(x, ng, mu)
    ps = [escape_probability(f, lam, 1.57, cs.n_b, 3000.0)["p_escape"] for lam in (0.10, 0.13, 0.16, 0.19)]
    assert all(np.diff(ps) > 0)


def test_validation_numbers_regression(m300):
    """The numbers quoted in notes/THEORY_r13_fluid_rigorous.md for the 300k cell (no fitted parameter)."""
    m, cs = m300
    assert cs.mu_max == pytest.approx(0.2478, abs=0.002)
    assert cs.n_star == pytest.approx(24.9, abs=0.3)
    assert cs.n_half == pytest.approx(31.5, abs=0.3)
    assert cs.mu_b == pytest.approx(0.0718, abs=0.0005)
    assert m.all_miss_closed(32)["tok"] == pytest.approx(11091, rel=0.003)
