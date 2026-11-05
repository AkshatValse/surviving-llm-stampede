"""Checks of Theorem 1 / Theorem 2 (notes/THEORY_ICML_2026-11.md) and of their implementation (analysis/theory/icml)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from analysis.theory.icml.trap_renewal import (TrapCosts, fifo_fluid, orbit_recursion, perron_root, remaining_work,
                                               trap_asymptotics, trap_costs)


def _toy(c, G):
    c = np.asarray(c, float)
    G = np.asarray(G, float)
    k = np.arange(1, len(G) + 1, dtype=float)
    Gn = np.append(G[1:], 0.0)
    lam = 1.0 / float((c * G).sum())
    return TrapCosts(k=k, c=c, P=1000.0 + 600.0 * (k - 1), G=G, p=G - Gn, d=100.0, mu_b=lam, delta=0.0, nu_b=lam * G.sum())


@pytest.fixture(scope="module")
def cell300():
    from analysis.theory.icml.run_check import cell_model
    m, _ = cell_model("a100_300k")
    return m, trap_costs(m)


def test_costs_reproduce_model_lambda_miss(cell300):
    m, tc = cell300
    assert abs(tc.lam_miss - m.bad()["mu"]) < 1e-12
    assert np.all(np.diff(tc.c) > 0)


@pytest.mark.parametrize("rho", [0.5, 0.9, 1.0, 1.2, 2.0, 5.0])
def test_perron_root(cell300, rho):
    _, tc = cell300
    lam = rho * tc.lam_miss
    z = perron_root(lam, tc)
    assert abs(lam * float((tc.c * tc.G * z ** (-tc.k)).sum()) - 1.0) < 1e-12
    assert (z > 1) == (rho > 1) and (abs(z - 1) < 1e-9) == (rho == 1.0)


@pytest.mark.parametrize("rho", [1.05, 1.35, 1.65, 3.0, 8.0])
def test_premium_decomposition_and_identities(cell300, rho):
    _, tc = cell300
    a = trap_asymptotics(rho * tc.lam_miss, tc)
    assert abs(a["premium"] - a["premium_check"]) < 1e-12                       # Theorem 2(i)
    assert a["premium"] > 0                                                      # the workload (numerical claim)
    q, K = 14.0 / 15.0, len(tc.G)
    z = a["z"]
    S = float((tc.G * z ** (-tc.k)).sum())
    H_formula = 1 - q ** K * (1 - tc.ET * z ** (-K) / S)                         # Theorem 2(iii)
    assert abs(a["H_T"] - H_formula) < 1e-12 and 1 - q ** K <= a["H_T"] <= 1
    assert a["C_c"] > 1                                                          # Theorem 2(ii)
    assert abs(a["alpha"] + a["D"] - a["lam"]) < 1e-12
    # pending work per session = mean next-turn cost of the tilted mix: gamma / alpha
    comp = tc.G * z ** (-tc.k) / S
    assert abs(a["pending_per_session"] - float((tc.c * comp).sum())) < 1e-9


def test_geometric_constant_cost_has_no_premium():
    K, q = 4000, 14.0 / 15.0                     # effectively untruncated geometric
    G = q ** np.arange(K)
    tc = _toy(np.full(K, 0.7), G)
    for rho in (1.2, 2.0, 4.0):
        a = trap_asymptotics(rho * tc.lam_miss, tc)
        assert abs(a["D_over_lam_miss"] - 1.0) < 1e-9 and abs(a["H_T"] - 1) < 1e-9 and abs(a["C_c"] - 1) < 1e-9


def test_gamma_factor_ge_one_for_nondecreasing_costs():
    rng = np.random.default_rng(3)
    for _ in range(50):
        K = int(rng.integers(2, 40))
        G = np.cumprod(np.r_[1.0, rng.uniform(0.5, 1.0, K - 1)])
        c = np.cumsum(rng.uniform(0.0, 1.0, K)) + 0.1
        tc = _toy(c, G)
        a = trap_asymptotics(float(rng.uniform(1.01, 6.0)) * tc.lam_miss, tc)
        assert a["C_c"] >= 1 - 1e-12


def test_near_threshold_coefficient(cell300):
    _, tc = cell300
    a = trap_asymptotics((1 + 1e-6) * tc.lam_miss, tc)
    assert abs(a["alpha_over_excess"] - a["near_threshold_coef"]) < 1e-4       # Theorem 1(e)
    assert abs(a["premium"] / 1e-6 - (1 - a["near_threshold_coef"])) < 1e-3    # Theorem 2(iv)


def test_sum_of_forcing_is_total_remaining_work(cell300):
    _, tc = cell300
    rng = np.random.default_rng(1)
    pi = rng.uniform(0, 3, len(tc.G))
    K = len(tc.G)
    h = [sum(tc.c[k - 1] * tc.G[k - 1] / tc.G[k - n - 1] * pi[k - n - 1] for k in range(n + 1, K + 1)) for n in range(K)]
    Vtot = sum(pi[j] * remaining_work(j + 1, tc) for j in range(K))
    assert abs(sum(h) - Vtot) < 1e-9 * Vtot                                      # Lemma 2(iv)


def test_renewal_lemma_critical_limit(cell300):
    _, tc = cell300
    lam = tc.lam_miss                                                             # rho = 1
    rng = np.random.default_rng(2)
    h = list(rng.uniform(0, 1, 30)) + [0.0] * 30
    D = orbit_recursion(lam, tc, h, 4000)
    kbar = float((tc.k * tc.c * tc.G).sum()) * lam
    assert abs(D[-1] - sum(h) / kbar) < 1e-6 * D[-1]                             # Theorem 1(b) / the renewal lemma


def test_orbit_recursion_holds_on_the_fluid(cell300):
    _, tc = cell300
    lam = 1.65 * 0.071534
    tr = fifo_fluid(lam, tc, 10.4, t_end=30000.0, grid=1000.0, dt_arr=1.0, orbit_from=1300.0)
    D = tr["orbit"][:, 1]
    a = lam * tc.c * tc.G
    K = len(a)
    assert len(D) > K + 5
    res = [abs(D[n] - sum(a[k - 1] * D[n - k] for k in range(1, K + 1))) / D[n] for n in range(K, len(D))]
    assert max(res) < 2e-3                                                        # packet discretisation only


def test_fluid_converges_to_asymptotics(cell300):
    _, tc = cell300
    lam = 1.35 * 0.071534
    a = trap_asymptotics(lam, tc)
    tr = fifo_fluid(lam, tc, 8.47, t_end=120000.0, grid=200.0, dt_arr=10.0)
    from analysis.theory.icml.trap_renewal import window_stats
    w = window_stats(tr, 90000.0, 120000.0, tc)
    assert abs(w["slope"] / a["alpha"] - 1) < 0.03
    assert abs(w["completion_rate"] / a["D"] - 1) < 0.01
    assert abs(w["P_served_mean"] / a["P_served_mean"] - 1) < 0.01


def test_busy_period_subcritical(cell300):
    _, tc = cell300
    rho, n0 = 0.5, 60.0
    lam = rho * tc.lam_miss
    stat = tc.G / tc.ET
    Vtot0 = n0 * sum(stat[j] * remaining_work(j + 1, tc) for j in range(len(tc.G)))
    tau = Vtot0 / (1 - rho)                                                       # Theorem 1(a)
    tr = fifo_fluid(lam, tc, n0, t_b=0.0, burst_n=0.0, t_end=1.5 * tau, grid=5.0, dt_arr=1.0)
    N = tr["N"]
    i = int(np.argmax(N < 0.5))
    assert N[i] < 0.5 and abs(tr["t"][i] / tau - 1) < 0.03


def test_cut_plans_equal_the_constant_rate_plan_before_the_cut():
    """The cut test's ramp plan (rate_max 1.65 x lambda_ref, S_ARRIVALS candidates, S_THIN keep) keeps every candidate before
    2400 s, so its pre-cut sessions are the constant-rate 1.65x BURST plan's (same idx, so the same specs)."""
    from analysis.theory.icml import cut_predict as cp
    from agentload.workload import S_ARRIVALS, make_rng, poisson_times
    lr = cp.lam_ref()
    base = poisson_times(make_rng(1, S_ARRIVALS), 1.65 * lr, 0.0, 8700.0)
    plan, _ = cp.build_cut_plan(1, 0.85)
    pre = [p for p in plan if p.origin == "base" and p.arrival_s < 2400.0]
    assert [p.arrival_s for p in pre] == [float(t) for t in base[base < 2400.0]]
    assert [p.idx for p in pre] == list(range(len(pre)))
    post = [p.arrival_s for p in plan if p.origin == "base" and p.arrival_s >= 2400.0]
    assert 0.6 < len(post) / ((base >= 2400.0).sum() * 0.85 / 1.65) < 1.4


def test_plan_fifo_is_deterministic_and_conserves_sessions():
    from analysis.theory.icml import cut_predict as cp
    from analysis.theory.icml.run_check import cell_model
    from analysis.theory.icml.trap_renewal import trap_costs
    m, _ = cell_model("a100_300k")
    tc = trap_costs(m)
    plan, _ = cp.build_cut_plan(0, 1.15)
    a = cp.plan_fifo(plan, tc, 1.33)
    b = cp.plan_fifo(plan, tc, 1.33)
    assert np.array_equal(a["ends"], b["ends"])
    st = cp.backlog_stats(a["starts"], a["ends"], 3000.0, 8700.0)
    n_in = ((a["starts"] < 8700.0)).sum() - (a["ends"] < 8700.0).sum()
    assert n_in > 32 and st["N_end"] > 32          # still trapped (N above n_b) at the end of the run
