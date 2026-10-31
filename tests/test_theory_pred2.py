"""Tests of the pred2 drivers (analysis/theory/pred2): the frozen model is untouched and every driver reproduces the frozen
functions where they overlap."""
from __future__ import annotations

import math

import numpy as np
import pytest

from analysis.theory.fluid_rigorous.model import Model, summarize_curve
from analysis.theory.fluid_rigorous.trapped import round_robin_trap
from analysis.theory.merged import extras as X
from analysis.theory.pred2 import common, conditional, prop_e, shed, toolslow


def test_frozen_theory_code_unchanged():
    chk = common.frozen_code_unchanged()
    assert chk["ok"] is True, chk
    assert all(p.startswith("analysis/theory/") for p in chk["added_committed"] + chk["untracked_new"])


def test_plan_rng_feeds_the_frozen_live_paths_exactly():
    c = common.cell("a100_300k")
    rng = np.random.default_rng(7)
    arr = np.sort(rng.uniform(0, 600, size=30))
    rng_a = np.random.default_rng(11)
    V_frozen = X._live_paths(rng_a, c.m, arr, 1.3, 1200.0, 1.0)
    rng_b = np.random.default_rng(11)                      # the same draws, laid out per session as a plan
    T = np.minimum(rng_b.geometric(1.0 / c.m.wl.mean_turns, size=len(arr)), c.m.wl.K)
    Z = rng_b.exponential(c.m.wl.zmean, size=int(T.sum()))
    first = np.cumsum(T) - T
    tools = [tuple(Z[f:f + t - 1]) for f, t in zip(first, T)]
    V_plan = common.live_path(c.m, arr, T, tools, 1.3, 1200.0)
    assert np.array_equal(V_frozen, V_plan)


def test_b2_driver_reproduces_the_frozen_b1_rows():
    c = common.cell("a100_300k")
    lam = 1.65 * c.lam_ref
    gs = X.good_state(c.m, c.cs, lam)
    stuck_by, _ = common.eval_times(gs["hit"])
    fz = {r["burst"]: r["p_trapped"] for r in common.frozen_json("b1_basin_300k")["tests"]["B1"]["result"]["rows"]}
    r = X.burst_trap_probability(c.m, c.cs, lam, sorted(fz), c.I_D, stuck_by_s=stuck_by)
    assert max(abs(row["p_trapped"] - fz[row["burst"]]) for row in r["rows"]) == 0.0
    assert abs(c.I_D - common.frozen_json("b1_basin_300k")["from_empty_edge"]["I_D"]) < 1e-12


def test_exact_plans_are_crn_nested():
    p0, _ = common.client_plan(common.E2_CONFIG, 1, 1.65, 8700.0, 0)
    p40, _ = common.client_plan(common.E2_CONFIG, 1, 1.65, 8700.0, 40)
    base0 = [(s.arrival_s, s.n_turns, s.tool_times_s) for s in p0 if s.origin == "base"]
    base40 = [(s.arrival_s, s.n_turns, s.tool_times_s) for s in p40 if s.origin == "base"]
    assert base0 == base40
    burst = [(s.arrival_s, s.n_turns, tuple(s.tool_times_s)) for s in p40 if s.origin == "burst"]
    assert burst == [(a, t, tuple(z)) for a, t, z in common.burst_cohort(1, 40)]
    assert len(burst) == 40 and all(1200.0 <= a < 1260.0 for a, _, _ in burst)


def test_time_varying_round_robin_equals_the_frozen_one_at_constant_rate():
    c = common.cell("a100_300k")
    lam = 1.35 * c.lam_ref
    eq = X.open_equilibria(c.cs, lam)
    fr = round_robin_trap(c.m, lam, eq.n1, t_b=1200.0, burst_n=200.0, burst_w=60.0, t_end=2600.0)
    tv = shed.round_robin_tv(c.m, eq.n1, shed.fluid_add(lambda t: lam), t_end=2600.0)
    assert np.max(np.abs(tv["n_sys"] - fr["n_sys"])) == 0.0


def test_shifted_law_with_zero_shift_is_the_frozen_curve():
    c = common.cell("a100_300k")
    cs0 = summarize_curve(toolslow.slowed_model(c.m, 0.0))
    assert abs(cs0.mu_max - c.cs.mu_max) < 1e-12 and abs(cs0.n_b - c.cs.n_b) < 1e-12
    wl = toolslow.slowed_model(c.m, 10.0).wl
    assert wl.F(10.0) == 0.0 and abs(wl.F(15.0) - (1 - math.exp(-1.0))) < 1e-12 and wl.zmean == 15.0
    assert abs(wl.Emin(1e6) - 15.0) < 1e-9 and wl.Emin(4.0) == 4.0


def test_proposition_e_lower_bound():
    c = common.cell("a100_300k")
    wl = c.m.wl
    Ebar = float((wl.w * wl.E).sum())
    assert abs(wl.A1 + wl.EET - c.m.ET * Ebar) < 1e-6 * wl.A1      # A1 + E[E_T] = E[T] Ebar
    for lam0 in (0.02, 0.07, 0.2, 0.6):
        T = prop_e.yao_T(wl, c.m.M, lam0)
        assert T >= c.m.M / (lam0 * c.m.ET * Ebar) - 1e-9


def test_conditional_spec_changes_only_the_allowed_fields():
    d = conditional.derived_specs("h200_300k", [1.1, 1.15], 32, None, None, variants="primary")[0]
    assert set(d) == {"base", "name", "description", "e2", "tests"}
    ll = conditional.derived_specs("llama31_8b_300k", [1.35, 1.65], 24, 0.06, 9000.0)
    assert set(ll[0]) == {"base", "name", "description", "e2", "tests", "lambda_ref"}
    assert set(ll[1]) == {"base", "name", "description", "e2", "tests", "lambda_ref", "costs"}
    assert ll[1]["costs"] == {"fit_speed_to_e0a": {"tokens_per_s": 9000.0, "pop": 32, "source": ll[1]["costs"]["fit_speed_to_e0a"]["source"]}}


def test_b2_lockstep_helper_equals_the_cohort_peak_lockstep():
    from analysis.theory.pred2 import b2
    c = common.cell("a100_300k")
    coh = common.burst_cohort(2, 40)
    T = [t for _, t, _ in coh]
    pk = b2._cohort_peaks(c, 1.65 * c.lam_ref, coh, 1.33)
    assert b2._lockstep(c, T) == pk["peak_lockstep"]


def test_h200_600k_spec_changes_only_the_pool():
    a, b = common.cell("h200_300k"), common.cell("h200_600k")
    assert b.m.M == 600000.0 and a.m.M == 300000.0
    assert b.lam_ref == a.lam_ref and b.m.wl == a.m.wl
    assert b.info.get("speed_factor_fitted") == a.info.get("speed_factor_fitted")


def test_shed_registered_rule_uses_the_two_registered_seeds():
    import json, os
    p = os.path.join(common.OUT_DIR, "shed.json")
    if not os.path.exists(p):
        pytest.skip("shed.json not generated")
    with open(p) as f:
        S = json.load(f)
    rr = S["rule"]
    assert rr["registered_seeds"] == [0, 1]
    assert abs(rr["p_rule"] - rr["p_stuck_600"] ** 2 * rr["p_good_3600"] ** 2) < 1e-12
