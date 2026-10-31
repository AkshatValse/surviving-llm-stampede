"""Blind predictions for the out-of-sample targets (H200 cell, Llama-3.1-8B cell, basin test B1, rescue tests R1/R4).

Nothing here reads any H200 / Llama / basin / rescue result: the only cell-specific inputs are
  * H200: its E0a (given in the task brief as an allowed input): all-miss 29,866 tok/s, turns-based 0.19388 sessions/s,
    POP-64 / POP-32 token ratio 1.046 (used only as a CHECK of the speed scaling, not fitted);
  * Llama-3.1-8B: published architecture constants (layers, heads, KV heads, parameters) used to rescale the calibrated
    Qwen2.5-7B costs ("roofline" scaling, an assumption), and nothing measured;
  * B1 / R1 / R4: their registered protocols (configs in the rescue worktree: burst sizes, rates, cap, t_on, hold).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, List, Optional

import numpy as np

from .edge import predicted_edge
from .model import (Costs, CurveSummary, Model, Workload, critical_burst_fresh, curve_on_grid, kv_dispersion, mu_good_of_n,
                    open_equilibria, summarize_curve)
from .trapped import round_robin_trap

H200_E0A = dict(tokens=29866.0, lambda_miss_turns=0.19388, pop64_token_ratio=1.046)


def fit_uniform_speed(base: Costs, wl: Workload, M: float, target_tokens: float, pop: float = 32.0) -> float:
    s = target_tokens / Model(wl, base, M).all_miss_closed(pop)["tok"]
    for _ in range(4):
        s *= target_tokens / Model(wl, base.scaled(s), M).all_miss_closed(pop)["tok"]
    return float(s)


def h200_models(wl: Optional[Workload] = None) -> Dict[str, Model]:
    """Primary: every calibrated A100 cost divided by one factor s_H fitted to the H200 E0a token rate (POP 32).
    Sensitivity 'decode2': the iteration-fixed, floor and decode-attention costs (memory-bandwidth / CPU bound) divided by
    2.0 only, the per-token and prefill-attention costs (compute bound) by the factor that restores the E0a rate."""
    wl = wl or Workload()
    base = Costs()
    sH = fit_uniform_speed(base, wl, 300000.0, H200_E0A["tokens"])
    out = {"uniform": Model(wl, base.scaled(sH), 300000.0)}
    # decode-side 2.0, compute side fitted
    def mk(sp: float) -> Costs:
        return replace(base, a=base.a / 2.0, f=base.f / 2.0, cd=base.cd / 2.0, b=base.b / sp, cp=base.cp / sp)
    lo, hi = 1.0, 6.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        r = Model(wl, mk(mid), 300000.0).all_miss_closed(32)["tok"]
        if r < H200_E0A["tokens"]:
            lo = mid
        else:
            hi = mid
    out["decode2"] = Model(wl, mk(0.5 * (lo + hi)), 300000.0)
    out["_s"] = sH  # type: ignore[assignment]
    out["_s_compute_decode2"] = 0.5 * (lo + hi)  # type: ignore[assignment]
    return out


LLAMA_SCALE = dict(a=1.05, f=1.05, b=1.06, cd=32 * 8 * 128 / (28 * 4 * 128), cp=32 * 32 * 128 / (28 * 28 * 128))


def llama_model(wl: Optional[Workload] = None, extra_speed: float = 1.0) -> Model:
    """Llama-3.1-8B on the A100 / SGLang / 300k cell: calibrated Qwen2.5-7B costs rescaled by architecture ratios
    (per-token GEMM ~ parameters 1.06; weight streaming per iteration 1.05; prefill attention per pair ~ layers x heads
    32*32 / (28*28) = 1.31; decode attention per context token ~ layers x KV heads 32*8 / (28*4) = 2.29).  An ASSUMPTION
    (roofline scaling), not a measurement; extra_speed rescales everything once Llama's own E0a is known."""
    wl = wl or Workload()
    c = Costs()
    c = replace(c, a=c.a * LLAMA_SCALE["a"], f=c.f * LLAMA_SCALE["f"], b=c.b * LLAMA_SCALE["b"], cd=c.cd * LLAMA_SCALE["cd"],
                cp=c.cp * LLAMA_SCALE["cp"])
    return Model(wl, c.scaled(extra_speed), 300000.0)


def cell_predictions(m: Model, lam_ref: float, mults=(1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0), H: float = 3000.0) -> Dict[str, object]:
    cs = summarize_curve(m)
    ngrid = np.linspace(0.0, max(cs.n_b * 1.6, 10.0), 4000)
    mug, hitg, _ = curve_on_grid(cs, ngrid)
    mu_f = lambda x: np.interp(x, ngrid, mug)
    pk = min(cs.pts, key=lambda p: abs(p["mu"] - cs.mu_max))
    kd = kv_dispersion(m.wl, pk["S_bar"])
    ed = predicted_edge(mu_f, lam_ref, mults, kd["I_D"], cs.n_b, H, cs.mu_max)
    b = m.bad()
    e0a32 = m.all_miss_closed(32)
    e0a64 = m.all_miss_closed(64)
    bursts = {}
    for mult in (1.35, 1.65, 2.0):
        lam = mult * lam_ref
        if lam < cs.mu_max:
            bursts[str(mult)] = critical_burst_fresh(m, cs, lam)
    return dict(mu_max=cs.mu_max, n_star=cs.n_star, hit_star=cs.h_star, n_half=cs.n_half, n_b=cs.n_b, mu_b=cs.mu_b,
                bistable=cs.bistable, folds=cs.folds, window_model=cs.window, window_vs_lam_ref=cs.mu_max / lam_ref,
                e0a32_tokens=e0a32["tok"], e0a32_mu=e0a32["mu"], e0a64_tokens=e0a64["tok"], pop64_ratio=e0a64["tok"] / e0a32["tok"],
                edge=ed, I_D=kd["I_D"], bursts=bursts, mu_at=dict((str(n), float(np.interp(n, ngrid, mug))) for n in (16, 20, 24, 28, 32, 40, 48)),
                hit_at=dict((str(n), float(np.interp(n, ngrid, hitg))) for n in (16, 20, 24, 28, 32, 40, 48)))


# ------------------------------------------------------------------------------------------------ rescue (pause cap)


def rescue_pause_cap(m: Model, cs: CurveSummary, lam: float, cap: float, t_on: float, t_b: float = 1200.0, burst_n: float = 200.0,
                     release_hold: float = 300.0, min_on: float = 600.0, duration: float = 8700.0) -> Dict[str, float]:
    """Fluid prediction for the registered RESCUE arm [T6]: the cap is engaged inside the trap at t_on by attrition plus
    pause at tool-call boundaries (a session whose tool call ends while active > cap waits in a resume deque served before
    new arrivals).  In the round-robin trap every session reaches a tool-call boundary within one cycle c(t_on), so the
    active population drops to the cap within ~c(t_on).  If cap < n_b (the all-miss branch cannot exist at the cap), the
    capped system leaves the trap: the active sessions miss once, then hit (their total KV fits).  The backlog (paused +
    gate) then drains at mu_cap - lam, where mu_cap is the good-state throughput of `cap` sessions whose footprint is that
    of resumed mid-session sessions (memoryless T: E_lb + 650 (k0 - 1)) and whose first resumed turn misses.
    Release = first time >= t_on + min_on at which the backlog has been empty for release_hold."""
    eq = open_equilibria(cs, lam)
    tr = round_robin_trap(m, lam, eq.n1, t_b=t_b, burst_n=burst_n, t_end=t_on + 1.0, dt=1.0)
    i = int(np.argmin(np.abs(tr["t"] - t_on)))
    n_on, c_on, Pbar = float(tr["n_sys"][i]), float(tr["c"][i]), float(tr["Pbar"][i])
    out = dict(lam=lam, cap=cap, t_on=t_on, n_on=n_on, cycle_on=c_on, n_b=cs.n_b)
    if not cap < cs.n_fold_lo:
        out.update(recovers=False, reason="cap >= lower end of the all-miss branch")
        return out
    wl = m.wl
    k0 = 1.0 + (Pbar - wl.L0) / (wl.delta + wl.d)
    pk = min(cs.pts, key=lambda p: abs(p["mu"] - cs.mu_max))
    E_lb = kv_dispersion(wl, pk["S_bar"])["E_lb"]
    infl = 1.0 + (wl.delta + wl.d) * (k0 - 1.0) / E_lb        # footprint of a resumed session / stationary footprint
    n_eff = cap * infl
    ngrid = np.linspace(0, cs.n_b * 1.5, 3000)
    mug, hitg, _ = curve_on_grid(cs, ngrid)
    mu_stat = float(np.interp(cap, ngrid, mug))
    # composition-adjusted: `cap` sessions with footprints inflated by `infl` see the pool as M / infl; one extra
    # (forced) miss per resumed session over its ~E[T] remaining turns
    from scipy.optimize import brentq
    m_eff = Model(wl, m.cost, m.M / infl)
    cs_eff = summarize_curve(m_eff)
    mu_e, hit_e, _ = curve_on_grid(cs_eff, ngrid)
    h_cap = float(np.interp(cap, ngrid, hit_e)) / (1.0 - 1.0 / m.ET)
    h_adj = max(0.0, h_cap - 1.0 / (m.ET - 1.0))
    f = lambda nu: nu / m.ET * m_eff.lifetime(m_eff.server(nu, h_adj)) - cap
    nu = brentq(f, 1e-9, m_eff.nu_cap(h_adj) * (1 - 1e-9))
    mu_adj = nu / m.ET
    out.update(k0=k0, footprint_inflation=infl, n_eff=n_eff, h_cap_adjusted=h_adj, mu_cap_stationary=mu_stat, mu_cap_adjusted=mu_adj,
               cap_below_cliff_adjusted=bool(cap < cs_eff.n_b))
    B0 = n_on - cap + lam * c_on
    for tag, mu_c in (("stationary", mu_stat), ("adjusted", mu_adj)):
        if lam >= mu_c:
            out[tag] = dict(mu_cap=mu_c, drains=False, released_by_7200=False, reason="lam >= mu_cap")
            continue
        t_empty = t_on + c_on + B0 / (mu_c - lam)
        t_rel = max(t_empty, t_on + min_on) + release_hold
        out[tag] = dict(mu_cap=mu_c, drains=True, t_queue_empty=t_empty, t_release=t_rel, released_by_7200=bool(t_rel <= 7200.0))
    out.update(recovers=True, backlog_after_pause=B0, n1=eq.n1,
               post_release="good (fluid: released at the stable equilibrium n1 = %.1f < cap)" % eq.n1)
    return out
