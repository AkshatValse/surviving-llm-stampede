"""Tests of the merged round-13 prediction code path (analysis/theory/predict.py, analysis/theory/merged/).

(i) The specs: every measured-cell spec builds the model from independent inputs only, the SGLang cells carry no fitted
parameter, the vLLM cell exactly one (fitted to its own E0a token rate, which the model then reproduces), and the typed
reference rates equal the E0a files.  (ii) The grafted identities: the closed-form all-miss threshold equals the model's n_b
exactly (any pool, speed, mode); the synchronized-start round robin conserves sessions and reproduces mu(300).  (iii) The new
layers: the committor is a probability, monotone in the burst and consistent with the deterministic critical burst; the
two-phase rescue drain lies between its bounds.  (iv) The CLI writes a JSON whose headline numbers are the validated ones.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import replace

import numpy as np
import pytest

from analysis.theory.fluid_rigorous.model import Costs, Model, Workload, summarize_curve
from analysis.theory.merged import extras as X
from analysis.theory.merged.spec import CELLS_DIR, ROOT, build, lambda_ref_of, load_spec
from analysis.theory import predict as P

MEASURED_SPECS = ("a100_300k", "a100_native", "vllm_300k")
E0A = {"a100_300k": "results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json",
       "a100_native": "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json",
       "vllm_300k": "results/nova/e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json"}


def spec(name):
    return load_spec(os.path.join(CELLS_DIR, f"{name}.yaml"))


@pytest.fixture(scope="module")
def m300():
    m, audit, info = build(spec("a100_300k"))
    return m, summarize_curve(m), audit, info


@pytest.mark.parametrize("name", MEASURED_SPECS)
def test_measured_specs_use_independent_inputs_only(name):
    s = spec(name)
    m, audit, info = build(s)
    fitted = [r for r in audit if r["kind"] == "fitted"]
    assert all(not r["uses_measured_mu_curve"] and not r["uses_e0b_or_e2_outcome"] for r in audit)
    assert all(r["source"] or r["kind"] in ("structural",) for r in audit)
    if name == "vllm_300k":
        assert len(fitted) == 1 and "E0a" in fitted[0]["fitted_to"]
        assert m.all_miss_closed(32)["tok"] == pytest.approx(s["costs"]["fit_speed_to_e0a"]["tokens_per_s"], rel=1e-6)
        assert m.wl.x_hit == 559 and m.cost.mode == "mixed"
    else:
        assert fitted == [] and m.cost.a == 9.24e-3 and m.cost.mode == "separate" and m.wl.x_hit == 551
    # the reference rate typed in the spec is the E0a file's value (used only to place the experiments' rates)
    cal = json.load(open(os.path.join(ROOT, E0A[name])))
    assert s["lambda_ref"]["value"] == pytest.approx(float(cal["lambda_miss_turns_based"]), rel=1e-5)
    if name == "vllm_300k":
        assert s["costs"]["fit_speed_to_e0a"]["tokens_per_s"] == pytest.approx(float(cal["all_miss_uncached_tokens_per_s"]), rel=1e-6)


def test_spec_inheritance_and_blind_specs():
    h = spec("h200_300k")
    assert h["pool_tokens"] == 300000 and h["blind"] is True and h["engine"]["mode"] == "separate"
    m, audit, info = build(h)
    assert len([r for r in audit if r["kind"] == "fitted"]) == 1
    assert info["speed_factor_fitted"] == pytest.approx(2.742, abs=0.01)          # 29,866 tok/s vs the A100's 11,091
    d2 = spec("h200_300k_decode2")
    assert d2["costs"]["decode_side_speedup"] == 2.0 and d2["costs"]["fit_speed_to_e0a"]["tokens_per_s"] == 29866.0
    ll = spec("llama31_8b_300k")
    ml, al, _ = build(ll)
    assert [r for r in al if r["kind"] == "fitted"] == [] and ml.cost.cd == pytest.approx(3.1e-4 * 32 * 8 / (28 * 4))
    lr, row = lambda_ref_of(ll, ml)
    assert row["kind"] == "derived" and lr == pytest.approx(ml.all_miss_closed(32)["mu"])
    for t in ("b1_basin_300k", "r1_rescue_300k", "r4_rescue_native"):
        s = spec(t)
        assert s["blind"] is True and len(s["tests"]) == 1


@pytest.mark.parametrize("M,speed,mode", [(300000.0, 1.0, "separate"), (955757.0, 1.0, "separate"), (150000.0, 2.74, "separate"),
                                          (300000.0, 0.918, "mixed")])
def test_closed_form_threshold_is_exact(M, speed, mode):
    """Graft of approach A's R2: n_b = nu_b zbar (1 - 1/E[T]) + M / E_S exactly (Little's law + the full pool at the all-miss end)."""
    wl = Workload(x_hit=559 if mode == "mixed" else 551)
    m = Model(wl, Costs(mode=mode).scaled(speed), M)
    t = X.threshold_closed_form(m)
    assert t["n_b_closed_form"] == pytest.approx(t["n_b"], rel=1e-9)
    assert t["n_b_approx"] == pytest.approx(t["n_b"], rel=0.05)                  # the E_bar form of approach A, to 5%
    assert 0 < t["tool_call_part"] < t["pool_part"]


def test_synchronized_start_round_robin(m300):
    m, cs, _, _ = m300
    r = X.stagec_synchronized(m, 300.0)
    assert r["trapped_from_start"] and r["mu_sessions"] > cs.mu_b
    assert r["mu_sessions"] == pytest.approx(0.1085, abs=0.002)                  # measured mu(300) = 0.1078 (validation)
    # per-turn costs average to 1/nu_b under the stationary turn mix (the decode share is exact)
    tau = X.miss_turn_cost(m)
    assert float((m.wl.w * tau).sum()) == pytest.approx(1.0 / m.bad()["nu"], rel=1e-9)
    # a population far above n_b relaxes toward the stationary all-miss rate if started late enough
    late = X.stagec_synchronized(m, 300.0, t0=60000.0, t1=62000.0, dt=2.0)
    assert late["mu_turns_based"] == pytest.approx(cs.mu_b, rel=0.03)


def test_committor_and_burst_probability(m300):
    m, cs, _, _ = m300
    lam = 1.65 * 0.071534
    r = X.burst_trap_probability(m, cs, lam, [10, 25, 40, 50, 53.4, 60, 100], 1.567)
    p = [x["p_trapped"] for x in r["rows"]]
    q = [x["committor"] for x in r["rows"]]
    assert all(0.0 <= v <= 1.0 for v in p) and all(np.diff(p) >= -1e-12) and all(np.diff(q) >= -1e-12)
    assert r["rows"][-1]["p_trapped"] == pytest.approx(1.0) and r["rows"][1]["p_trapped"] < 0.1     # b = 100 traps, 25 does not
    det = r["b_crit_deterministic"]
    assert 50 < det < 57                                                         # B's F3: 53.4 at 1.65 x
    # at the deterministic critical burst the cohort peak sits at the basin boundary n_u
    row = [x for x in r["rows"] if x["burst"] == 53.4][0]
    assert row["X0"] == pytest.approx(r["n_u"], rel=0.01)
    mu_f, _, _, _, _ = X.curve_fn(cs)
    eq_n1, n_b = r["n1"], cs.n_b
    assert X.committor(mu_f, lam, 1.567, n_b, eq_n1, eq_n1) == 0.0 and X.committor(mu_f, lam, 1.567, n_b, eq_n1, n_b) == 1.0


def test_two_phase_rescue_between_bounds(m300):
    m, cs, _, _ = m300
    r = X.rescue_two_phase(m, cs, 1.35 * 0.071534, 20.0, 1800.0, 1.567)
    tp, ta, col = r["two_phase"], r["two_phase_annealed"], r["phase1_collapsed"]
    assert r["in_window"] and tp["drains"] and ta["drains"]
    assert r["stationary"]["t_release"] <= tp["t_release"] + 10 <= r["adjusted"]["t_release"] + 20
    assert tp["t_release"] <= ta["t_release"] <= col["t_release"]
    assert (tp["t_release"] - 1800.0) % 10.0 == pytest.approx(0.0, abs=1e-6)     # release on the 10-s check grid
    assert r["mu_phase1_fluid"] == pytest.approx(r["mu_cap_adjusted"], rel=1e-6)  # = approach B's adjusted capped rate
    # a cap at or above the basin boundary does not rescue (B's Prop. 7)
    bad = X.rescue_two_phase(m, cs, 1.35 * 0.071534, 33.0, 1800.0, 1.567)
    assert not bad["two_phase"]["drains"]


def test_registration_rule():
    p = {1.25: 0.01, 1.5: 0.1, 1.75: 0.3, 2.0: 0.45, 2.5: 0.7, 3.0: 0.9}
    g = {16.0: 0.17, 20.0: 0.225, 24.0: 0.233, 32.0: 0.11}
    r = X.registration_consequence(p, 0.25, 0.0715, g)
    assert r["hi_mult"] == 2.0 and r["lambda_points"] == [1.35, 1.65] and r["n_cap"] == 20.0


def test_cli_writes_validated_numbers(tmp_path):
    out = tmp_path / "a100_300k.json"
    P.main([os.path.join(CELLS_DIR, "a100_300k.yaml"), "--quick", "--out", str(out)])
    d = json.load(open(out))
    fl = d["closed_curve"]["fluid"]
    assert d["fitted_parameters"] == [] and d["uses_measured_mu_curve"] is False
    assert fl["mu_max"] == pytest.approx(0.2478, abs=0.002) and fl["peak_n"] == pytest.approx(24.9, abs=0.3)
    assert fl["n_half"] == pytest.approx(31.5, abs=0.3) and fl["single_valued"]
    assert d["all_miss"]["e0a_pop32_lambda_turns"] == pytest.approx(0.0718, abs=0.0005)
    assert d["from_empty_edge"]["predicted_bracket"] == [2.0, 2.5]                # measured: stable 2.0, unstable 2.5
    a = d["e2"]["arms"]["1.35"]["burst_trapped"]
    assert a["gap_over_R"] == pytest.approx(6.93, abs=0.1) and 200 < a["backlog"] < 232
    assert d["window"]["s_times_zbar_s"] == 5.0 and d["window"]["local_condition"]["holds"]
    for p in d["provenance"]["sha256"]:
        assert os.path.exists(os.path.join(ROOT, p))
