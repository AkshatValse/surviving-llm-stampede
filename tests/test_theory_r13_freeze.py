"""Post-review checks added before the r13-theory-pred freeze (2026-10-31).

* a REAL leakage guard: the prediction code path, run on blind specs, must never open or probe a path under results/nova
  or any path naming an out-of-sample cell or test (replaces reliance on the self-attested audit flags);
* Proposition F (fold identity): the exact sign identity agrees with finite differences, every predicted (exponential-tool)
  cell is fold-free, and dispersed (hyperexponential) tool times fold above n_b;
* the corrected collapsed phase-1 bound of the rescue layer.
"""
from __future__ import annotations

import builtins
import os

import numpy as np
import pytest

from analysis.theory import predict as P
from analysis.theory.fluid_rigorous.model import summarize_curve
from analysis.theory.merged import extras as X
from analysis.theory.merged import fold as F
from analysis.theory.merged.spec import CELLS_DIR, build, load_spec

FORBIDDEN = ("results/nova", "results\\nova", "repo_h200", "h200_pulled", "llama31_pulled", "b100", "b25", "rescue_pulled",
             "e0bfresh", "lpminf", "/r11", "\\r11")


def spec(name):
    return load_spec(os.path.join(CELLS_DIR, f"{name}.yaml"))


@pytest.fixture
def guard(monkeypatch):
    real_open, real_exists, real_isfile = builtins.open, os.path.exists, os.path.isfile
    touched = []

    def check(p):
        s = os.fspath(p) if isinstance(p, (str, bytes, os.PathLike)) else ""
        s = s.decode() if isinstance(s, bytes) else s
        low = s.replace("\\", "/").lower()
        for bad in FORBIDDEN:
            if bad.replace("\\", "/").lower() in low:
                touched.append(s)
                raise AssertionError(f"prediction code touched a forbidden path: {s}")

    def g_open(file, *a, **k):
        check(file)
        return real_open(file, *a, **k)

    def g_exists(p):
        check(p)
        return real_exists(p)

    def g_isfile(p):
        check(p)
        return real_isfile(p)

    monkeypatch.setattr(builtins, "open", g_open)
    monkeypatch.setattr(os.path, "exists", g_exists)
    monkeypatch.setattr(os.path, "isfile", g_isfile)
    return touched


@pytest.mark.parametrize("name", ["h200_300k", "llama31_8b_300k", "r1_rescue_300k"])
def test_blind_predictions_never_touch_results_or_oos_paths(guard, name):
    out = P.predict(spec(name), quick=True)
    assert guard == []
    assert out["fitted_parameters"] in ([], ["uniform speed factor s (every cost divided by s)"])
    assert out["scoring"]["general"]["estimator"]["primary"].startswith("turns-based")


def test_guard_actually_fires(guard):
    with pytest.raises(AssertionError):
        open(os.path.join("results", "nova", "x.json"))


CELL_MARGINS = {"a100_300k": 0.805, "a100_native": 0.826, "h200_300k": 0.784, "llama31_8b_300k": 0.781,
                "a100_pool150k": 0.761, "a100_pool600k": 0.821}


@pytest.mark.parametrize("name,expect", sorted(CELL_MARGINS.items()))
def test_prop_F_every_predicted_cell_is_fold_free(name, expect):
    m, _, _ = build(spec(name))
    fm = F.fold_margin(m)
    assert fm["fold_free"] and fm["max_ratio"] == pytest.approx(expect, abs=0.003)
    assert fm["sign_agreement"] == 1.0
    assert fm["R_at_max"] < 0.01           # the binding point is the all-miss end R -> 0+ (Corollary F.2)
    lo = F.leading_order_ratio(m)
    assert lo["leading_order_ratio"] < 1.0 and abs(lo["leading_order_ratio"] - fm["max_ratio"]) < 0.08


@pytest.mark.parametrize("mix,n_fold", [(((0.5, 1.0), (0.5, 9.0)), 34.18), (((0.8, 1.0), (0.2, 21.0)), 38.16),
                                        (((0.95, 1.0), (0.05, 81.0)), 44.63)])
def test_prop_F_dispersed_tool_times_fold_above_n_b(mix, n_fold):
    m, _, _ = build(spec("a100_300k"))
    mm = F.mixture(m, mix)
    fb = F.fold_band(mm)
    assert fb["n_fold"] == pytest.approx(n_fold, abs=0.05) and fb["n_b"] == pytest.approx(32.70, abs=0.02)
    fm = F.fold_margin(mm)
    assert not fm["fold_free"] and fm["sign_agreement"] > 0.99


def test_prop_F_identity_matches_finite_difference_pointwise():
    m, _, _ = build(spec("a100_300k"))
    mm = F.mixture(m, ((0.5, 1.0), (0.5, 9.0)))
    for R in (0.05, 0.3, 1.0, 3.0, 10.0):
        t0, t1 = F.terms(mm, R * (1 - 1e-4)), F.terms(mm, R * (1 + 1e-4))
        dn = (t1["n"] - t0["n"]) / (t1["R"] - t0["R"])
        sign = np.sign(F.terms(mm, R)["lhs"] - F.terms(mm, R)["rhs"])
        assert np.sign(dn) == sign


def test_rescue_collapsed_bound_is_the_closed_cap_population():
    m, _, _ = build(spec("a100_300k"))
    cs = summarize_curve(m)
    r135 = X.rescue_two_phase(m, cs, 1.35 * 0.071534, 20.0, 1800.0, 1.567)
    r165 = X.rescue_two_phase(m, cs, 1.65 * 0.071534, 20.0, 1800.0, 1.567)
    assert r135["mu_phase1_collapsed_stationary"] == pytest.approx(0.0695, abs=3e-4)
    assert r135["mu_phase1_collapsed_resumed"] == pytest.approx(0.0487, abs=3e-4)
    assert r165["mu_phase1_collapsed_resumed"] == pytest.approx(0.0495, abs=3e-4)
    assert not r135["phase1_collapsed"]["released_by_deadline"] and not r165["phase1_collapsed"]["released_by_deadline"]
    assert r165["phase1_collapsed_stationary_mix"]["t_release"] == pytest.approx(7240.0, abs=10.0)
    assert r135["two_phase"]["t_release"] == pytest.approx(3830.0, abs=10.0)
    assert r165["two_phase"]["t_release"] == pytest.approx(4360.0, abs=10.0)
