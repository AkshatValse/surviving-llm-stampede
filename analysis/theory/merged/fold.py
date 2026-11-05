r"""Proposition F (fold identity) of notes/THEORY_r13_merged.md section 2.6, added after the round-13 adversarial review.

Separate mode (SGLang), the W = 0 branch of B's fluid model parametrised by the LRU frontier R, any tool-time law with density
f = F_Z' (here: the exponential mixtures ``Workload.tool_mix`` supports).  With h = F_Z(R),

    dn/dR = (nu / Phi_nu) [ f(R) I(R) - n_nu D'(R) / E[T] ],                                       (F)

    I     = nu dS_D/dnu [C_E + rho (Ebar (Sbar + z') - S_E - D/E[T])] + beta_E (Sbar + z') - beta_P (S_E + D/E[T]),
    rho   = -(dS_D/dh) / (nu dS_D/dnu),        C_E = beta_E - Ebar beta_P,
    n_nu  = Sbar + z' + nu dS_D/dnu,            D' = A1 P(Z > R) + E[E_T],    Phi_nu > 0.

So n(R) is strictly decreasing (no fold: T6) iff the ratio r(R) = f I / (n_nu D'/E[T]) stays below 1 for every R, and a ratio
above 1 anywhere gives n_fold = max_R n(R) > n_b: three closed stationary states for n in (n_b, n_fold).

The partial derivatives of S_D are taken by central differences (S_D is B's decode-time function; nothing is fitted).  This
module only DIAGNOSES the model; no prediction depends on it (every predicted cell is fold-free, see ``fold_margin``).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from ..fluid_rigorous.model import Model, summarize_curve


def _law(wl) -> Tuple[np.ndarray, np.ndarray]:
    p, z = wl._mix()
    return np.asarray(p, float), np.asarray(z, float)


def density(wl, r: float) -> float:
    p, z = _law(wl)
    return float((p / z * np.exp(-r / z)).sum())


def survival(wl, r: float) -> float:
    p, z = _law(wl)
    return float((p * np.exp(-r / z)).sum())


def constants(m: Model) -> Dict[str, float]:
    w, E, fol = m.w, m.E, m.is_follow
    dt = m.tPm - m.tPh
    beta_P = float((w * fol * dt).sum())
    beta_E = float((w * E * fol * dt).sum())
    Ebar = float((w * E).sum())
    return dict(beta_P=beta_P, beta_E=beta_E, Ebar=Ebar, C_E=beta_E - Ebar * beta_P,
                zp=m.wl.zmean * (1.0 - 1.0 / m.ET), c_t=float((w * (E - Ebar) * m.tPm).sum()))


def terms(m: Model, R: float, k: Optional[Dict[str, float]] = None) -> Optional[Dict[str, float]]:
    """Every term of identity (F) at frontier R (None where the W = 0 branch does not exist)."""
    if m.cost.mode != "separate":
        raise ValueError("Proposition F is stated for separate mode (SGLang)")
    k = k or constants(m)
    wl = m.wl
    nu = m.nu_of_R(float(R))
    if not math.isfinite(nu) or nu <= 0:
        return None
    h = wl.F(float(R))
    s = m.server(nu, h)
    e = 1e-6 * nu
    SDn = (m.server(nu + e, h).S_D - m.server(nu - e, h).S_D) / (2 * e)
    eh = 1e-6
    h_hi, h_lo = min(h + eh, 1.0), max(h - eh, 0.0)
    SDh = (m.server(nu, h_hi).S_D - m.server(nu, h_lo).S_D) / (h_hi - h_lo)
    hk = m.hk(h)
    S_E = float((m.w * m.E * (hk * m.tPh + (1.0 - hk) * m.tPm + s.S_D)).sum())
    Dv = m.D(float(R))
    Dp = wl.A1 * survival(wl, float(R)) + wl.EET
    ET = m.ET
    nuSDn = nu * SDn
    rho = -SDh / nuSDn if nuSDn != 0 else 0.0
    I = (nuSDn * (k["C_E"] + rho * (k["Ebar"] * (s.S_bar + k["zp"]) - S_E - Dv / ET))
         + k["beta_E"] * (s.S_bar + k["zp"]) - k["beta_P"] * (S_E + Dv / ET))
    n_nu = s.S_bar + k["zp"] + nuSDn
    f = density(wl, float(R))
    lhs, rhs = f * I, n_nu * Dp / ET
    return dict(R=float(R), h=h, nu=nu, n=nu * (s.S_bar + k["zp"]), I=I, rho=rho, n_nu=n_nu, f=f, D=Dv, Dprime=Dp,
                lhs=lhs, rhs=rhs, ratio=lhs / rhs)


def fold_margin(m: Model, R_grid: Optional[Sequence[float]] = None) -> Dict[str, object]:
    """max_R r(R) on a grid (r < 1 everywhere <=> n(R) strictly decreasing), with the sign agreement of (F) against the finite
    difference of n along the grid (a numerical check of the identity)."""
    k = constants(m)
    if R_grid is None:
        R_grid = np.geomspace(1e-3, 50.0 * m.wl.zmean, 400)[::-1]
    rows = [t for t in (terms(m, R, k) for R in R_grid) if t is not None]
    ratio = np.array([t["ratio"] for t in rows])
    n = np.array([t["n"] for t in rows])
    dn = np.diff(n)                                      # R decreasing along rows: dn > 0 <=> dn/dR < 0
    pred_dec = ratio < 1.0
    agree = float(np.mean((dn > 0) == pred_dec[1:])) if len(dn) else math.nan
    j = int(np.argmax(ratio))
    return dict(max_ratio=float(ratio[j]), R_at_max=rows[j]["R"], h_at_max=rows[j]["h"], fold_free=bool(ratio.max() < 1.0),
                sign_agreement=agree, n_points=len(rows))


def leading_order_ratio(m: Model) -> Dict[str, float]:
    """Corollary F.3: the ratio at R -> 0+ to leading order, f(0+) [C_E + rho0 (Ebar z' - c_t)] / Ebar."""
    k = constants(m)
    b = m.bad()
    s = m.server(b["nu"], 0.0)
    c = m.cost
    tauDp = (c.b if s.R_D >= c.f / c.b else 0.0) + m.betac
    rho0 = k["beta_P"] / (float((m.w * m.tPm).sum()) + (m.wl.d - 1) * tauDp)
    lo = m.wl.dens0() * (k["C_E"] + rho0 * (k["Ebar"] * k["zp"] - k["c_t"])) / k["Ebar"]
    return dict(leading_order_ratio=lo, rho0=rho0, C_E=k["C_E"], c_t=k["c_t"], f0_times_EZ=m.wl.dens0() * m.wl.zmean,
                fold_threshold_f0EZ=1.0 / (rho0 * (1.0 - 1.0 / m.ET)))


def fold_band(m: Model) -> Dict[str, float]:
    """n_b and n_fold = the largest n on B's W = 0 solution curve (n_fold > n_b <=> bistable band (n_b, n_fold))."""
    cs = summarize_curve(m)
    n_fold = max(p["n"] for p in cs.pts)
    return dict(n_b=cs.n_b, n_fold=max(n_fold, cs.n_b), band_width=max(n_fold - cs.n_b, 0.0), n_folds=len(cs.folds))


def mixture(m: Model, mix) -> Model:
    """The same cell with tool times drawn from an exponential mixture ((prob, mean), ...) instead of Exp(zbar)."""
    return Model(replace(m.wl, tool_mix=tuple(tuple(x) for x in mix)), m.cost, m.M)
