"""Checks behind notes/PAPER_INPUT_theory.md (written after the freeze tag r13-theory-pred; changes no prediction).

* Proposition F holds as an identity in magnitude (not only in sign): (nu / Phi_nu) [f I - n_nu D'/E[T]] equals the
  finite-difference dn/dR of the model's W = 0 branch, for the registered exponential law and for a folding mixture.
* The decode-equation identity used in the proof: -dS_D/dh = rho * nu dS_D/dnu with
  rho = beta_P / (tbar_P(h) + (d - 1) tau_D'(R_D)).
* T3(b) n_b = nu_b zbar' + M / E_S and the speed corollary T3(c) n_b(s) = n_b(1) + (s - 1) nu_b(1) zbar'.
* The numbers quoted in the paper text equal the frozen JSONs.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

from analysis.theory.fluid_rigorous.model import Model, summarize_curve
from analysis.theory.merged import fold as F
from analysis.theory.merged.spec import ROOT, build, load_spec

CELLS = os.path.join(ROOT, "analysis", "theory", "cells")
RES = os.path.join(ROOT, "results", "theory", "merged")


def cell(name):
    m, _, _ = build(load_spec(os.path.join(CELLS, f"{name}.yaml")))
    return m


def frozen(name):
    with open(os.path.join(RES, f"{name}.json")) as f:
        return json.load(f)


def n_of_R(m, R):
    nu = m.nu_of_R(R)
    s = m.server(nu, m.wl.F(R))
    return nu * (s.S_bar + m.wl.zmean * (1.0 - 1.0 / m.ET))


def dn_dR_identity(m, R):
    t = F.terms(m, R)
    nu, h = t["nu"], t["h"]
    e = 1e-6 * nu
    a = nu * (m.server(nu + e, h).S_D - m.server(nu - e, h).S_D) / (2 * e)
    s = m.server(nu, h)
    hk = m.hk(h)
    S_E = float((m.w * m.E * (hk * m.tPh + (1.0 - hk) * m.tPm + s.S_D)).sum())
    Ebar = float((m.w * m.E).sum())
    Phi_nu = S_E + Ebar * a + t["D"] / m.ET
    return nu / Phi_nu * (t["lhs"] - t["rhs"])


@pytest.mark.parametrize("mix", [None, ((0.5, 1.0), (0.5, 9.0))])
@pytest.mark.parametrize("R", [0.05, 0.4, 2.0, 8.0, 25.0])
def test_prop_F_identity_in_magnitude(mix, R):
    m = cell("a100_300k")
    if mix is not None:
        m = F.mixture(m, mix)
    eps = 1e-4 * R
    fd = (n_of_R(m, R + eps) - n_of_R(m, R - eps)) / (2 * eps)
    ident = dn_dR_identity(m, R)
    assert ident == pytest.approx(fd, rel=2e-3, abs=1e-6)


@pytest.mark.parametrize("h", [0.0, 0.3, 0.9])
def test_decode_identity_rho(h):
    m = cell("a100_300k")
    nu = 0.6
    s = m.server(nu, h)
    e = 1e-6
    SDn = (m.server(nu + e * nu, h).S_D - m.server(nu - e * nu, h).S_D) / (2 * e * nu)
    hh = max(h, e)
    SDh = (m.server(nu, hh + e).S_D - m.server(nu, hh - e).S_D) / (2 * e) if h > 0 else \
        (m.server(nu, 2 * e).S_D - m.server(nu, 0.0).S_D) / (2 * e)
    k = F.constants(m)
    hk = m.hk(h)
    tbar = float((m.w * (hk * m.tPh + (1 - hk) * m.tPm)).sum())
    c = m.cost
    tauDp = (c.b if s.R_D >= c.f / c.b else 0.0) + m.betac
    rho = k["beta_P"] / (tbar + (m.wl.d - 1) * tauDp)
    assert -SDh == pytest.approx(rho * nu * SDn, rel=2e-4)


@pytest.mark.parametrize("name,n_b,pool_part", [("a100_300k", 32.70, 27.76), ("a100_native", 94.86, None),
                                                ("h200_300k", 41.31, 27.76), ("a100_pool150k", 18.3, None),
                                                ("a100_pool600k", 61.2, None)])
def test_threshold_identity(name, n_b, pool_part):
    th = frozen(name)["all_miss"]["threshold"]
    assert th["n_b"] == pytest.approx(th["tool_call_part"] + th["pool_part"], rel=1e-9)
    assert th["n_b"] == pytest.approx(n_b, abs=0.06)
    if pool_part is not None:
        assert th["pool_part"] == pytest.approx(pool_part, abs=0.01)


def test_speed_corollary_T3c():
    m = cell("a100_300k")
    b1 = m.bad()
    zp = m.wl.zmean * (1 - 1 / m.ET)
    for s in (2.0, 2.742):
        ms = Model(m.wl, m.cost.scaled(s), m.M)
        bs = ms.bad()
        assert bs["nu"] == pytest.approx(s * b1["nu"], rel=1e-8)
        assert bs["n_b"] == pytest.approx(b1["n_b"] + (s - 1) * b1["nu"] * zp, rel=1e-8)


def test_quoted_numbers_match_frozen_jsons():
    a = frozen("a100_300k")
    assert a["closed_curve"]["fluid"]["mu_max"] == pytest.approx(0.2478, abs=1e-4)
    assert a["closed_curve"]["annealed"]["mu_max"] == pytest.approx(0.2337, abs=1e-4)
    assert a["window"]["local_condition"]["Delta_S"] == pytest.approx(594.6, abs=0.1)
    h = frozen("h200_300k")
    assert h["closed_curve"]["annealed"]["mu_max"] == pytest.approx(0.371, abs=1.5e-3)
    assert h["window"]["annealed_vs_lambda_ref"] == pytest.approx(1.92, abs=0.006)
    assert h["from_empty_edge"]["edge_mult"] == pytest.approx(1.39, abs=0.006)
    assert h["all_miss"]["n_b"] == pytest.approx(41.3, abs=0.06)
    ll = frozen("llama31_8b_300k")
    assert ll["window"]["annealed_vs_lambda_ref"] == pytest.approx(3.37, abs=0.006)
    assert frozen("a100_pool150k")["window"]["annealed_vs_lambda_ref"] == pytest.approx(1.87, abs=0.006)
    assert frozen("a100_pool600k")["window"]["annealed_vs_lambda_ref"] == pytest.approx(5.47, abs=0.006)


def test_fold_example_three_states():
    from analysis.theory.fluid_rigorous.model import fixed_points
    m = F.mixture(cell("a100_300k"), ((0.5, 1.0), (0.5, 9.0)))
    fps = fixed_points(m, 33.5, ngrid=401)
    hs = [round(f["h"], 3) for f in fps]
    assert hs == [0.0, 0.29, 0.694]
    assert [f["stable"] for f in fps] == [True, False, True]
    fb = F.fold_band(m)
    assert fb["n_fold"] == pytest.approx(34.18, abs=0.05)
