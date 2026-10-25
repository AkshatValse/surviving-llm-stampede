"""Round 7: opt-in tool-time distributions of the workload model (lognormal mean/CV, explicit two-point mixture, empirical quantile table)
and the guarantee that the earlier workloads are unchanged (digests of ``build_specs`` computed with the round-6 code, before the change)."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from prefixmeta.probe import load_probe_config
from prefixmeta.sim import RunSpec, deep_update, simulate
from prefixmeta.workload import (ArrivalPlan, WorkloadParams, bimodal_p_hi, build_specs, empirical_moments, empirical_table, tool_time_moments,
                                 tool_times)

REPO = Path(__file__).resolve().parent.parent

BASE = dict(initial_context_tokens=2000, new_prompt_tokens=550, decode_tokens=100, mean_turns=15, max_turns=60,
            tool_time_mean_s=5.0, tool_time_dist="exp", tool_time_cv=1.5)


def _digest(specs) -> str:
    h = hashlib.sha256()
    for a in (specs.arrival, specs.n_turns, specs.tool_off, specs.tool_flat):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


# sha256 of the (arrival, n_turns, tool_off, tool_flat) arrays, computed with the UNMODIFIED round-6 workload.py
PRE_R7 = {
    "exp_constant": "26ae1886ae65dcd7dbc16dfc80afa55df2cefa50241dd6e31b1584c65d40f4a9",
    "lognormal_burst": "05018cc9120938706a2baf9d594f6f9612db501b4d11ae31dec6a5c0e9fb879f",
    "bimodal_cold": "62228bbafb9c198e9f36e45b4cc7e0a9a01373919ea8c9d4ee7035b909acb9de",
    "exp_closed": "457e8ddb0ec1b182ac0dd05b7676304bc15c51104ec05dd8566f2d66bcb06111",
    "bimodal_custom": "f98d99cb86014053116c62f4510a86c54a69303cd45c7cc76e83f6d3907492f8",
}
PRE_R7_CASES = {
    "exp_constant": (dict(BASE), ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.1), 7),
    "lognormal_burst": (dict(BASE, tool_time_dist="lognormal", tool_time_cv=1.5),
                        ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.1, burst_n=40, burst_t0=500.0, burst_width_s=60.0), 8),
    "bimodal_cold": (dict(BASE, tool_time_dist="bimodal"), ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.1, initial_cold=30), 9),
    "exp_closed": (dict(BASE), ArrivalPlan(kind="closed", horizon_s=1500.0, closed_n=32, pool=400), 10),
    "bimodal_custom": (dict(BASE, tool_time_dist="bimodal", tool_time_lo_s=1.0, tool_time_hi_s=20.0, tool_time_mean_s=4.8),
                       ArrivalPlan(kind="triangle", horizon_s=1500.0, rate_lo=0.05, rate_hi=0.15, ramp_s=700.0), 11),
}


@pytest.mark.parametrize("case", sorted(PRE_R7))
def test_earlier_workloads_are_bit_identical_to_round6(case):
    wl, plan, seed = PRE_R7_CASES[case]
    assert _digest(build_specs(WorkloadParams.from_dict(wl), plan, seed)) == PRE_R7[case]


def test_new_fields_default_to_none_and_old_dicts_still_load():
    wl = WorkloadParams.from_dict(dict(BASE))
    assert wl.tool_time_p_hi is None and wl.tool_time_quantiles is None and wl.tool_time_quantile_levels is None
    assert (wl.tool_time_lo_s, wl.tool_time_hi_s) == (0.3, 20.0)


# ----------------------------------------------------------------------------- (i) lognormal with a given mean and CV
@pytest.mark.parametrize("mean,cv", [(5.0, 2.0), (5.0, 0.5), (2.0, 3.0)])
def test_lognormal_mean_and_cv(mean, cv):
    s2 = math.log1p(cv * cv)
    x = tool_times(np.random.default_rng(11), 4_000_000, "lognormal", mean, cv)
    lx = np.log(x)
    assert lx.mean() == pytest.approx(math.log(mean) - 0.5 * s2, abs=0.01)         # log-moments converge fast
    assert lx.std() == pytest.approx(math.sqrt(s2), rel=0.01)
    assert x.mean() == pytest.approx(mean, rel=0.03)                               # CV 3 has a heavy tail: loose bound on the raw mean
    assert np.median(x) == pytest.approx(mean / math.sqrt(1.0 + cv * cv), rel=0.01)
    wl = WorkloadParams.from_dict(dict(BASE, tool_time_dist="lognormal", tool_time_mean_s=mean, tool_time_cv=cv))
    assert tool_time_moments(wl) == (mean, cv)


def test_lognormal_cv2_through_build_specs():
    wl = WorkloadParams.from_dict(dict(BASE, tool_time_dist="lognormal", tool_time_mean_s=5.0, tool_time_cv=2.0))
    sp = build_specs(wl, ArrivalPlan(kind="closed", horizon_s=1.0, closed_n=10, pool=60_000), 3)
    s2 = math.log1p(4.0)
    assert sp.tool_flat.shape[0] > 500_000
    assert np.log(sp.tool_flat).mean() == pytest.approx(math.log(5.0) - 0.5 * s2, abs=0.01)
    assert sp.tool_flat.mean() == pytest.approx(5.0, rel=0.03)


# ----------------------------------------------------------------------------- (ii) two-point mixture
def test_bimodal_explicit_probability_80_20():
    x = tool_times(np.random.default_rng(5), 1_000_000, "bimodal", 999.0, 0.0, 1.0, 20.0, p_hi=0.2)     # `mean` is unused when p_hi is given
    assert set(np.unique(x)) == {1.0, 20.0}
    assert (x == 20.0).mean() == pytest.approx(0.2, abs=0.002)
    assert x.mean() == pytest.approx(4.8, rel=0.005)
    wl = WorkloadParams.from_dict(dict(BASE, tool_time_dist="bimodal", tool_time_lo_s=1.0, tool_time_hi_s=20.0, tool_time_p_hi=0.2))
    mean, cv = tool_time_moments(wl)
    assert mean == pytest.approx(4.8) and cv == pytest.approx(math.sqrt(0.2 * 0.8) * 19.0 / 4.8)
    assert cv == pytest.approx(x.std() / x.mean(), rel=0.01)


def test_bimodal_derived_probability_is_unchanged_and_consistent_with_the_explicit_one():
    assert bimodal_p_hi(4.8, 1.0, 20.0) == pytest.approx(0.2)
    a = tool_times(np.random.default_rng(9), 200_000, "bimodal", 4.8, 1.5, 1.0, 20.0)
    b = tool_times(np.random.default_rng(9), 200_000, "bimodal", 4.8, 1.5, 1.0, 20.0, p_hi=0.2)
    assert (a != b).mean() < 1e-4                      # same stream; they can differ only if a uniform falls within 1e-16 of 0.2


def test_bimodal_p_hi_validation():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            WorkloadParams.from_dict(dict(BASE, tool_time_dist="bimodal", tool_time_p_hi=bad))
    with pytest.raises(ValueError):
        WorkloadParams.from_dict(dict(BASE, tool_time_dist="exp", tool_time_p_hi=0.2))


# ----------------------------------------------------------------------------- (iii) empirical quantile table
class _FixedUniform:
    """A generator stub whose ``random(n)`` returns given values: lets the interpolation be checked by hand."""

    def __init__(self, u):
        self.u = np.asarray(u, dtype=float)

    def random(self, n):
        assert n == self.u.shape[0]
        return self.u


def test_empirical_inverse_cdf_is_linear_interpolation_by_hand():
    q = [0.0, 1.0, 3.0, 10.0]                      # equally spaced levels 0, 1/3, 2/3, 1
    u = [0.0, 1 / 6, 1 / 3, 0.5, 2 / 3, 5 / 6, 1.0]
    x = tool_times(_FixedUniform(u), len(u), "empirical", 0.0, 0.0, quantiles=q)
    assert x == pytest.approx([0.0, 0.5, 1.0, 2.0, 3.0, 6.5, 10.0])
    lv = [0.0, 0.5, 0.9, 1.0]                      # explicit levels
    q2 = [1.0, 2.0, 6.0, 26.0]
    u2 = [0.25, 0.5, 0.7, 0.95, 1.0]
    x2 = tool_times(_FixedUniform(u2), len(u2), "empirical", 0.0, 0.0, quantiles=q2, levels=lv)
    assert x2 == pytest.approx([1.5, 2.0, 4.0, 16.0, 26.0])


def test_empirical_sampling_matches_the_table_and_its_exact_moments():
    q = (0.5, 1.0, 2.0, 4.0, 9.0, 30.0)
    wl = WorkloadParams.from_dict(dict(BASE, tool_time_dist="empirical", tool_time_quantiles=list(q)))      # a YAML list is accepted
    assert wl.tool_time_quantiles == q and isinstance(wl.tool_time_quantiles, tuple)
    x = tool_times(np.random.default_rng(1), 2_000_000, "empirical", 0.0, 0.0, quantiles=q)
    assert x.min() >= q[0] and x.max() <= q[-1]
    lv = np.linspace(0.0, 1.0, len(q))
    for level, value in zip(lv, q):                # the empirical CDF at a table point is its level
        assert (x <= value).mean() == pytest.approx(level, abs=0.002)
    mean, cv = tool_time_moments(wl)
    m, c = empirical_moments(q)
    assert (mean, cv) == (m, c)
    assert x.mean() == pytest.approx(mean, rel=0.005) and x.std() / x.mean() == pytest.approx(cv, rel=0.01)
    assert mean == pytest.approx(sum(0.2 * (a + b) / 2.0 for a, b in zip(q[:-1], q[1:])))       # trapezoid rule by hand
    assert np.median(x) == pytest.approx(0.5 * (2.0 + 4.0), abs=0.02)                              # level 0.5 lies between q[2] (0.4) and q[3] (0.6)


def test_empirical_through_build_specs_is_reproducible_and_changes_tools_only():
    q = [0.2, 1.0, 5.0, 40.0]
    wl_e = WorkloadParams.from_dict(dict(BASE, tool_time_dist="empirical", tool_time_quantiles=q))
    wl_x = WorkloadParams.from_dict(dict(BASE))
    plan = ArrivalPlan(kind="constant", horizon_s=2000.0, rate=0.1, burst_n=20, burst_t0=100.0, burst_width_s=60.0)
    a, b, c = build_specs(wl_e, plan, 5), build_specs(wl_e, plan, 5), build_specs(wl_x, plan, 5)
    assert _digest(a) == _digest(b)
    assert np.array_equal(a.arrival, c.arrival) and np.array_equal(a.n_turns, c.n_turns)          # same sessions, other tool times
    assert not np.array_equal(a.tool_flat, c.tool_flat) and a.tool_flat.min() >= 0.2 and a.tool_flat.max() <= 40.0


def test_empirical_validation():
    bad = [dict(tool_time_quantiles=None), dict(tool_time_quantiles=[1.0]), dict(tool_time_quantiles=[2.0, 1.0]),
           dict(tool_time_quantiles=[-1.0, 1.0]), dict(tool_time_quantiles=[0.0, float("nan")]),
           dict(tool_time_quantiles=[1.0, 2.0, 3.0], tool_time_quantile_levels=[0.0, 1.0]),
           dict(tool_time_quantiles=[1.0, 2.0, 3.0], tool_time_quantile_levels=[0.1, 0.5, 1.0]),
           dict(tool_time_quantiles=[1.0, 2.0, 3.0], tool_time_quantile_levels=[0.0, 0.5, 0.9]),
           dict(tool_time_quantiles=[1.0, 2.0, 3.0], tool_time_quantile_levels=[0.0, 0.0, 1.0])]
    for kw in bad:
        with pytest.raises(ValueError):
            WorkloadParams.from_dict(dict(BASE, tool_time_dist="empirical", **kw))
    with pytest.raises(ValueError):                # a table with another distribution would be silently ignored
        WorkloadParams.from_dict(dict(BASE, tool_time_dist="exp", tool_time_quantiles=[1.0, 2.0]))
    with pytest.raises(ValueError):
        empirical_table(None)
    with pytest.raises(ValueError):
        tool_times(np.random.default_rng(0), 3, "weird", 1.0, 1.0)


# ----------------------------------------------------------------------------- the engine accepts the new workloads
@pytest.mark.parametrize("wo", [
    {"tool_time_dist": "lognormal", "tool_time_mean_s": 5.0, "tool_time_cv": 2.0},
    {"tool_time_dist": "bimodal", "tool_time_lo_s": 1.0, "tool_time_hi_s": 20.0, "tool_time_p_hi": 0.2},
    {"tool_time_dist": "empirical", "tool_time_quantiles": [0.5, 1.0, 3.0, 9.0, 40.0]},
])
def test_simulator_runs_with_each_new_tool_time_distribution(wo):
    cfg = load_probe_config(str(REPO / "configs" / "r6_predict.yaml"), REPO)
    rs = RunSpec(exp="t", policy="fcfs_lru", seed=0, horizon_s=600.0, workload_overrides=wo,
                 plan=ArrivalPlan(kind="constant", horizon_s=600.0, rate=0.06))
    res = simulate(cfg, rs)
    assert res["summary"]["n_arrived"] > 10 and res["summary"]["n_sessions_done"] >= 0
    WorkloadParams.from_dict(deep_update(cfg["workload"], wo))
