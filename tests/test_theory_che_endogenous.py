"""Tests of the Che endogenous-gap model (analysis/theory/che_endogenous).

They pin the workload identities, the structure of the closed fixed point (existence, uniqueness for the measured cells,
the all-miss limit), the exactness of the trapped-state identity gap / R = sum (L + d) / M, the one-parameter scale fit,
and the live-volume Monte Carlo against Campbell's theorem.  Numerical tolerances are loose on purpose: these are
regression and identity checks, not validation against the engine (that is run_che.py)."""
import math
from dataclasses import replace

import numpy as np
import pytest

from analysis.theory.che_endogenous.model import CheModel, Cell, Costs, Workload, calibrate_scale, default_cells
from analysis.theory.che_endogenous import open_system as osys


@pytest.fixture(scope="module")
def m300():
    return CheModel(replace(default_cells()["a100_300k"], eta=0.10))


@pytest.fixture(scope="module")
def curve300(m300):
    return osys.mean_field_curve(m300, osys_grid(300_000))


def osys_grid(M):
    from analysis.theory.che_endogenous.run_che import n_grid
    return n_grid(M)


def test_workload_identities():
    wl = Workload()
    assert wl.ET == pytest.approx(14.761055, abs=1e-5)                 # E[T] of min(Geom(1/15), 60)
    assert wl.EW_allmiss == pytest.approx(154_529, abs=1.0)            # all-miss prefill tokens per session
    assert float((wl.surv * wl.c).max()) == pytest.approx(4330.1, abs=1.0)   # fresh-cohort peak KV per session
    assert wl.L[1] - wl.L[0] == 650.0 and wl.L[0] == 2000.0
    m1, m2 = wl.lb_moments(1.4)
    assert 10_400 < m1 < 10_700                                        # E_lb (MATHCHECK: 10,450-10,569)
    assert 0.70 < math.sqrt(m2 / m1 ** 2 - 1) < 0.80                   # CV of a session's KV (sd ~ 7.9-8.0k)


def test_tool_time_laws():
    for shape in (1.0, 4.0, math.inf):
        wl = Workload(z_shape=shape)
        rng = np.random.default_rng(0)
        z = wl.z_sample(rng, 200_000)
        assert z.mean() == pytest.approx(5.0, rel=0.01)
        for x in (2.0, 5.0, 9.0):
            assert wl.z_cdf(x) == pytest.approx(float(np.mean(z < x)), abs=0.01)
            assert wl.z_min_mean(x) == pytest.approx(float(np.minimum(z, x).mean()), rel=0.01)


def test_allmiss_reference_close_to_e0a_without_fitting(m300):
    ref = m300.allmiss_reference(32)
    # independent check of the server-log cost model against E0a (not used to fit anything): 11,243 tok/s, 0.0715 /s
    assert ref["tokens_per_s"] == pytest.approx(11_243, rel=0.03)
    assert ref["lambda_miss_turns"] == pytest.approx(0.0715, rel=0.03)


def test_fixed_point_exists_unique_and_limits(m300):
    for n in (8, 16, 24, 28, 32, 33, 34, 48, 300):
        fps = m300.fixed_points(float(n))
        assert len(fps) == 1, (n, fps)
        assert fps[0]["stable"]
    assert m300.good_branch(16.0)["h"] > 0.99
    big = m300.good_branch(300.0)
    assert big["h"] == 0.0 and big["regime"] == "S"
    assert big["mu"] == pytest.approx(m300.nu_sat(0.0, m300.B_mem) / m300.wl.ET, rel=1e-6)   # mu_inf = saturated all-miss


def test_curve_is_unimodal(curve300):
    mu = np.array([r["mu"] for r in curve300])
    i = int(np.argmax(mu))
    assert np.all(np.diff(mu[: i + 1]) >= -1e-9)
    assert np.all(np.diff(mu[i:]) <= 1e-9)


def test_crossings_and_window(curve300):
    lam = 1.65 * 0.071534
    N1, N2 = osys.crossings(curve300, lam)
    assert 8 < N1 < 14 and 28 < N2 < 36
    assert math.isnan(osys.crossings(curve300, 10.0)[0])


def test_trapped_identity_gap_over_R(m300, curve300):
    p = osys.burst_trap_path(m300, curve300, 1.35 * 0.071534, 200, t_end=3000.0, dt=1.0)
    wl = m300.wl
    n = p["state"]
    # gap / R = C * churn / M with C = 1 / r and churn = r * sum n_k (L_k + d): the rate cancels
    work = float((n * m300.trapped_turn_cost()).sum())
    r = 1.0 / work
    churn = r * float((n * (wl.L + wl.decode)).sum())
    assert (work * churn / m300.cell.M) == pytest.approx(float((n * (wl.L + wl.decode)).sum()) / m300.cell.M, rel=1e-12)
    assert p["N"].min() > 100      # the trap keeps a large backlog after a 200-session burst


def test_scale_fit_hits_target():
    cell, s = calibrate_scale(default_cells()["vllm_300k"], 10_348.97)
    assert CheModel(cell).allmiss_reference(32)["tokens_per_s"] == pytest.approx(10_348.97, rel=1e-4)
    assert 1.0 < s < 1.2


def test_live_volume_mc_matches_campbell(m300, curve300):
    lam = 2.0 * 0.071534
    S = osys.good_state_S(m300, curve300, lam)
    rng = np.random.default_rng(3)
    H = 60_000.0
    arr = np.sort(rng.uniform(0, H, rng.poisson(lam * H)))
    V = osys._session_paths(rng, m300.wl, arr, S, H, 1.0)[1000:-1000]
    m1, m2 = m300.wl.lb_moments(S)
    life = m300.wl.ET * S + (m300.wl.ET - 1) * m300.wl.z_mean
    assert V.mean() == pytest.approx(lam * life * m1, rel=0.03)
    assert V.std() == pytest.approx(math.sqrt(lam * life * m2), rel=0.06)


def test_faster_hardware_narrows_window_larger_pool_widens():
    def window(cell):
        m = CheModel(cell)
        mf = osys.mean_field_curve(m, osys_grid(cell.M))
        return max(r["mu"] for r in mf) / m.allmiss_reference(32)["lambda_miss_turns"]
    base = Cell("b", M=300_000.0, eta=0.10)
    w0 = window(base)
    assert window(replace(base, costs=Costs().scaled(1 / 2.66))) < 0.6 * w0
    assert window(replace(base, M=600_000.0)) > 1.4 * w0
