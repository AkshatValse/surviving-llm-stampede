r"""Grafts and new layers on top of the fluid model of approach B (notation of notes/THEORY_r13_merged.md).

All functions take B's ``Model`` and its ``CurveSummary``; nothing here is fitted.

threshold_closed_form   [graft of A's R2]  n_b = nu_b zbar' + M / E_S  (exact in B's model).
stagec_synchronized     [graft of A]       Stage C protocol at large n: synchronized fresh start, all-miss round robin.
good_state              [graft of A's R5b] the good open state at lam: hit, R = M/churn, gap/R = (zbar ln 2 + S) / R.
trapped_e2              [B's round robin]  the E2 BURST arm window means and the post-burst minimum.
capped_static_drain     [graft of A]       the E2 CAPPED arm: gate queue (burst + n1 - cap) drained at mu(cap) - lam.
burst_trap_probability  [new]              committor of B's F2 diffusion from the burst's peak demand.
rescue_two_phase        [new]              pause-cap RESCUE: resumed sessions first, then fresh arrivals.
registration_consequence[graft of A]       the registered window/cap rules applied to the model's own predictions.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import (CurveSummary, Model, critical_burst_fresh, curve_on_grid, kv_dispersion, live_demand,
                                    mu_good_of_n, open_equilibria)
from ..fluid_rigorous.oos import rescue_pause_cap
from ..fluid_rigorous.trapped import round_robin_trap, window_means


# ------------------------------------------------------------------------------------------------ helpers


def curve_fn(cs: CurveSummary, n_max: Optional[float] = None, npts: int = 6000):
    """mu(n) and hit(n) of the (fold-free) fluid curve as callables on [0, n_max] (flat at mu_b past n_b)."""
    n_max = n_max or max(cs.n_b * 2.0, 10.0)
    ng = np.linspace(0.0, n_max, npts)
    mu, hit, _ = curve_on_grid(cs, ng)
    return (lambda x: np.interp(x, ng, mu)), (lambda x: np.interp(x, ng, hit)), ng, mu, hit


def miss_turn_cost(m: Model) -> np.ndarray:
    """GPU time of a missing turn k in the memory-saturated all-miss state: its own prefill work plus the per-turn decode share
    (1 - p_b)/nu_b, so that sum_k w_k cost_k = 1/nu_b exactly (both modes)."""
    b = m.bad()
    if m.cost.mode == "mixed":
        pre = m.cost.b * m.P + m.cost.cp * m.P * (m.P + 1.0) / 2.0
    else:
        pre = m.tPm
    return pre + (1.0 - b["p"]) / b["nu"]


# ------------------------------------------------------------------------------------------------ R2 graft


def threshold_closed_form(m: Model) -> Dict[str, float]:
    """Exact identity of the model (graft of approach A's R2, proved in the notes, section 3):
        n_b = nu_b * zbar (1 - 1/E[T])  +  M / E_S,     E_S = sum_k w_k E_k S_k / sum_k w_k S_k  at (nu_b, h = 0):
    the sessions in tool calls at the all-miss rate plus one pool's worth of running sessions (E_S is the
    service-time-weighted reservation of a running request).  Approximation: n_b ~ lambda_miss E[T] zbar' + M / E_bar."""
    b = m.bad()
    s = m.server(b["nu"], 0.0)
    wl = m.wl
    if m.cost.mode == "separate":
        Sk = m.tPm + s.S_D
        E_S = float((wl.w * wl.E * Sk).sum() / (wl.w * Sk).sum())
    else:
        E_S = s.K_run / (b["nu"] * s.S_bar)
    zp = wl.zmean * (1.0 - 1.0 / m.ET)
    Ebar = float((wl.w * wl.E).sum())
    return dict(n_b=b["n_b"], n_b_closed_form=b["nu"] * zp + m.M / E_S, tool_call_part=b["nu"] * zp, pool_part=m.M / E_S,
                E_S=E_S, E_bar=Ebar, n_b_approx=b["mu"] * m.ET * zp + m.M / Ebar, nu_b=b["nu"], mu_b=b["mu"])


# ------------------------------------------------------------------------------------------------ Stage C at large n


def stagec_synchronized(m: Model, n: float, t0: float = 900.0, t1: float = 2700.0, dt: float = 1.0) -> Dict[str, float]:
    """Stage C protocol in the all-miss regime (graft of approach A's closed_trap_transient, on B's costs): n fresh sessions
    at t = 0, each finished session replaced at once by a fresh one, every turn misses, FCFS round robin (one turn per
    session per round, round length = sum of the present sessions' miss-turn costs).  Measured over [t0, t1).  The young
    synchronized composition makes the window throughput exceed the stationary mu_b (measured mu(300) > lambda_miss).
    Valid when the population cannot fit its KV even at the start (n E_1 > M: trapped from t = 0)."""
    wl = m.wl
    tau = miss_turn_cost(m)
    G, Gn = wl.G, wl.Gnext
    haz = np.where(G > 0, (G - Gn) / G, 1.0)
    x = np.zeros(wl.K)
    x[0] = float(n)
    done_w = turns_w = tok_w = 0.0
    t = 0.0
    while t < t1:
        r = 1.0 / float((x * tau).sum())
        served = np.minimum(r * x * dt, x)
        done = served * haz
        adv = served - done
        x = x - served
        x[1:] += adv[:-1]
        x[0] += done.sum()
        if t >= t0:
            done_w += float(done.sum())
            turns_w += float(served.sum())
            tok_w += float((served * m.P).sum())
        t += dt
    T = t1 - t0
    return dict(n=float(n), mu_sessions=done_w / T, mu_turns_based=turns_w / T / m.ET, tokens_per_s=tok_w / T,
                trapped_from_start=bool(n * wl.E[0] > m.M), stationary_mu_b=m.bad()["mu"])


# ------------------------------------------------------------------------------------------------ open good state


def good_state(m: Model, cs: CurveSummary, lam: float) -> Dict[str, float]:
    """The good open state at lam (graft of approach A's R5b in B's model): n1 from the phase line, its hit fraction, the
    loopvars quantities median gap = median(Z) + S = zbar ln 2 + S_bar and R = M / churn."""
    eq = open_equilibria(cs, lam)
    if not math.isfinite(eq.n1):
        return dict(lam=lam, exists=False)
    ng, _ = mu_good_of_n(cs)
    pts = cs.pts[: len(ng)]
    pt = min(pts, key=lambda p: abs(p["n"] - eq.n1))
    wl = m.wl
    hk = m.hk(pt["h"])
    churn = pt["nu"] * (float((wl.w * (hk * wl.x_hit + (1 - hk) * wl.P)).sum()) + wl.d)
    gap_med = wl.zmean * math.log(2.0) + pt["S_bar"]
    R = m.M / churn
    return dict(lam=lam, exists=True, n1=eq.n1, n_u=eq.n_u, hit=pt["hit"], S_bar=pt["S_bar"], churn=churn, R=R,
                gap_med=gap_med, gap_over_R=gap_med / R)


# ------------------------------------------------------------------------------------------------ E2 arms


def trapped_e2(m: Model, cs: CurveSummary, lam: float, burst_n: float = 200.0, t_b: float = 1200.0, burst_w: float = 60.0,
               window=(5700.0, 8700.0), t_end: float = 8700.0) -> Dict[str, float]:
    """E2 BURST arm: B's FCFS round-robin fluid from the good state n1(lam) plus the burst; window means over the
    registered evaluation window, and the post-burst minimum of the backlog."""
    eq = open_equilibria(cs, lam)
    n1 = eq.n1 if math.isfinite(eq.n1) else 0.0
    tr = round_robin_trap(m, lam, n1, t_b=t_b, burst_n=burst_n, burst_w=burst_w, t_end=t_end)
    w = window_means(tr, float(window[0]), float(window[1]))
    after = tr["t"] >= t_b + burst_w
    j = int(np.argmin(tr["n_sys"][after]))
    tok_e0a = m.all_miss_closed(32)["tok"]
    return dict(lam=lam, n1=n1, backlog=w["n_sys"], backlog_slope=w["backlog_slope"], sessions_per_s=w["completions"],
                turns_based=w["turns"] / m.ET, tokens_per_s=w["tok"], token_ratio_vs_model_e0a=w["tok"] / tok_e0a,
                gap_over_R=w["gap_over_R"], R=w["R"], cycle=w["c"], Pbar=w["Pbar"], hit=0.0,
                backlog_min_after_burst=float(tr["n_sys"][after][j]), t_min_after_burst=float(tr["t"][after][j] - t_b),
                backlog_at_window_start=float(np.interp(window[0], tr["t"], tr["n_sys"])))


def capped_static_drain(m: Model, cs: CurveSummary, lam: float, cap: float, burst_n: float = 200.0) -> Dict[str, float]:
    """E2 CAPPED arm (static FIFO cap from t = 0; graft of approach A): the burst and the good-state population beyond the cap
    wait at the gate, which drains at mu(cap) - lam while the cap sessions stay good (cap < n_b)."""
    mu_f, _, _, _, _ = curve_fn(cs)
    eq = open_equilibria(cs, lam)
    mu_c = float(mu_f(cap))
    q = burst_n + (eq.n1 if math.isfinite(eq.n1) else 0.0) - cap
    return dict(lam=lam, cap=cap, mu_cap=mu_c, gate_queue=q, cap_below_n_b=bool(cap < cs.n_b),
                drain_after_burst_s=q / (mu_c - lam) if (mu_c > lam and cap < cs.n_b) else math.inf)


# ------------------------------------------------------------------------------------------------ bursts (new)


def _scale_density(mu: Callable, lam: float, I_D: float, x_t: float, nx: int = 6000):
    y = np.linspace(0.0, x_t, nx + 1)
    muy = mu(y)
    s2 = np.maximum(I_D * (lam + muy), 1e-12)
    g = 2.0 * (lam - muy) / s2
    psi = np.concatenate([[0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * (y[1] - y[0]))])
    return y, np.exp(-(psi - psi.min()))          # scale density exp(-Psi), normalised to max 1


def committor(mu: Callable, lam: float, I_D: float, x_t: float, a: float, x0: float) -> float:
    """P(the F2 diffusion dX = (lam - mu(X)) dt + sqrt(I_D (lam + mu)) dW started at x0 reaches the all-miss end x_t
    before falling back to the good equilibrium a = n1):  int_a^x0 s / int_a^x_t s  with s = exp(-Psi) the scale density."""
    if x0 >= x_t:
        return 1.0
    if x0 <= a:
        return 0.0
    y, s = _scale_density(mu, lam, I_D, x_t)
    c = np.concatenate([[0.0], np.cumsum(0.5 * (s[1:] + s[:-1]) * (y[1] - y[0]))])
    Sa, S0, St = (float(np.interp(v, y, c)) for v in (a, x0, x_t))
    return float((S0 - Sa) / (St - Sa)) if St > Sa else 1.0


def burst_trap_probability(m: Model, cs: CurveSummary, lam: float, bursts: Sequence[float], I_D: float,
                           t_b: float = 1200.0, burst_w: float = 60.0, stuck_by_s: float = 6345.0) -> Dict[str, object]:
    """A burst of b fresh sessions at rate lam (new layer, consistent with B's F2 and F3).
    Deterministic (B's F3): trapped iff D_live(n1) + b max_j G_j E_j > D_live(n_u), i.e. b > b_c.
    Stochastic: at the cohort's peak the live demand is D_live(n1) + b c_peak; X0 = the population whose live demand that is
    (inverted along the good curve, X0 = n_u exactly at b = b_c).  P(trapped) = q(X0) + (1 - q(X0)) P_esc(H), q the committor
    of the F2 diffusion to the all-miss end n_b and P_esc the F2 escape from the good state over the time H left until
    ``stuck_by_s`` (the latest escape that still makes the registered window's hit fall below 0.2)."""
    mu_f, _, _, _, _ = curve_fn(cs)
    eq = open_equilibria(cs, lam)
    det = critical_burst_fresh(m, cs, lam)
    out: Dict[str, object] = dict(lam=lam, n1=eq.n1, n_u=eq.n_u, b_crit_deterministic=det.get("b_fresh"),
                                  b_stat=det.get("b_stat"), cohort_peak_kv=det.get("cohort_peak_kv"),
                                  cohort_peak_turn=det.get("cohort_peak_turn"), rows=[])
    if not math.isfinite(eq.n1):
        out["note"] = "lam >= mu_max: no good state"
        return out
    ng, _ = mu_good_of_n(cs)
    pts = cs.pts[: len(ng)]
    n_arr = np.array([p["n"] for p in pts])
    D_arr = np.array([live_demand(m, p) for p in pts])
    o = np.argsort(n_arr)
    n_arr, D_arr = n_arr[o], D_arr[o]
    D1 = float(np.interp(eq.n1, n_arr, D_arr))
    # per-turn cycle of the burst cohort = tool time + the good-state mean service time at n1 (post-review fix: was a
    # hard-coded 1.5 s)
    gs = good_state(m, cs, lam)
    S_n1 = float(gs["S_bar"]) if gs.get("exists") else 1.5
    peak_delay = (int(det.get("cohort_peak_turn") or 12) - 1) * (m.wl.zmean + S_n1)
    H = max(stuck_by_s - (t_b + burst_w + peak_delay), 0.0)
    p_bg = escape_probability(mu_f, lam, I_D, cs.n_b, H)["p_escape"] if H > 0 else 0.0
    for b in bursts:
        Dt = D1 + float(b) * float(det.get("cohort_peak_kv") or 0.0)
        X0 = float(np.interp(Dt, D_arr, n_arr)) if Dt <= D_arr[-1] else cs.n_b
        q = committor(mu_f, lam, I_D, cs.n_b, eq.n1, X0)
        out["rows"].append(dict(burst=float(b), X0=X0, committor=q, p_escape_background=p_bg, p_trapped=q + (1 - q) * p_bg,
                                deterministic="trapped" if b > (det.get("b_fresh") or math.inf) else "not trapped"))
    out["horizon_after_peak_s"] = H
    out["S_bar_at_n1"] = S_n1
    out["peak_delay_s"] = peak_delay
    return out


# ------------------------------------------------------------------------------------------------ rescue (new)


def rescue_two_phase(m: Model, cs: CurveSummary, lam: float, cap: float, t_on: float, I_D: float, t_b: float = 1200.0,
                     burst_n: float = 200.0, hold: float = 300.0, min_on: float = 600.0, check: float = 10.0,
                     release_by: float = 7200.0, horizon: float = 8700.0, post_start: float = 300.0) -> Dict[str, object]:
    """Registered pause-cap RESCUE arm.  B's construction (rescue_pause_cap: trapped round robin until t_on, attrition within
    one cycle, composition-adjusted capped throughput mu_adj of resumed mid-session sessions whose first resumed turn misses)
    with the registered gate order made explicit: the resume deque is served BEFORE new arrivals.
      phase 1: the n_on - cap paused sessions are admitted as slots free up, at the capped completion rate mu_adj
               (T1 = (n_on - cap)/mu_adj); the gate collects the fresh arrivals since t_on;
      phase 2: the gate (fresh sessions) drains at mu(cap) - lam (stationary composition).
    t_empty = t_on + c_on + T1 + lam (c_on + T1)/(mu(cap) - lam); release at the first check tick >= max(t_empty, t_on + min_on)
    + hold.  Bounds: 'stationary' (B: everything at mu(cap)), 'adjusted_single_queue' (B: everything at mu_adj - lam) and
    'phase1_collapsed' (phase 1 at the all-miss rate of a closed population of `cap` resumed sessions; the stationary-mix
    variant is 'phase1_collapsed_stationary_mix'); 'two_phase_annealed' averages the phase-1 rate over the F1 demand
    fluctuation of the cap sessions.  Rescue needs n1 < cap < n_u (B's Prop. 7).  Relapse: F2 escape over
    [t_rel + post_start, horizon)."""
    base = rescue_pause_cap(m, cs, lam, cap, t_on, t_b=t_b, burst_n=burst_n, release_hold=hold, min_on=min_on,
                            duration=horizon)
    eq = open_equilibria(cs, lam)
    out: Dict[str, object] = dict(base)
    out.update(n1=eq.n1, n_u=eq.n_u, in_window=bool(math.isfinite(eq.n1) and eq.n1 < cap < eq.n_u),
               cap_below_n_b=bool(cap < cs.n_b))
    if not base.get("recovers", False) or not out["in_window"]:
        out["two_phase"] = dict(drains=False, released_by_deadline=False, reason=base.get("reason", "cap outside (n1, n_u)"))
        return out
    mu_f, _, _, _, _ = curve_fn(cs)
    mu_c = float(mu_f(cap))
    n_on, c_on = float(base["n_on"]), float(base["cycle_on"])
    D0 = max(n_on - cap, 0.0)

    def release(t_empty: float) -> float:
        # first check tick (t_on + k check) at or after t_on + min_on at which both queues have been empty for `hold`
        t0 = max(t_empty + hold, t_on + min_on)
        return t_on + math.ceil((t0 - t_on) / check - 1e-9) * check

    def phase(mu1: float) -> Dict[str, float]:
        if mu_c <= lam or mu1 <= 0:
            return dict(drains=False, released_by_deadline=False)
        T1 = D0 / mu1
        t_empty = t_on + c_on + T1 + lam * (c_on + T1) / (mu_c - lam)
        tr = release(t_empty)
        return dict(drains=True, phase1_rate=mu1, T1=T1, t_queue_empty=t_empty, t_release=tr,
                    released_by_deadline=bool(tr <= release_by))

    infl = float(base["footprint_inflation"])
    mu1_fluid = mu_resumed(m, infl, cap)
    # F1 applied to phase 1: the cap sessions' KV demand fluctuates with relative variance cv2 / cap (pool M / (infl theta))
    cv2 = kv_dispersion(m.wl, 1.7)["cv2"]
    xg, wg = np.polynomial.hermite_e.hermegauss(7)
    wg = wg / wg.sum()
    sd = math.sqrt(cv2 / cap)
    mu1_ann = float(sum(w * mu_resumed(m, infl * max(0.5, 1.0 + sd * x), cap) for x, w in zip(xg, wg)))
    tp = phase(mu1_fluid)
    ta = phase(mu1_ann)
    # Collapsed phase 1 (post-review fix, 2026-10-31): the all-miss rate of a CLOSED population of `cap` sessions, not the
    # memory-saturated mu_b of a stationary population >= n_b.  Two bounds: the resumed mix (prompts shifted by
    # (Delta + d)(k0 - 1), the composition phase 1 actually serves) and the stationary turn mix.
    from dataclasses import replace as _dc_replace
    k0 = float(base.get("k0", 1.0))
    wl_res = _dc_replace(m.wl, L0=int(round(m.wl.L0 + (m.wl.delta + m.wl.d) * (k0 - 1.0))))
    mu_col_resumed = float(Model(wl_res, m.cost, m.M).all_miss_closed(cap)["mu"])
    mu_col_stationary = float(m.all_miss_closed(cap)["mu"])
    col = phase(mu_col_resumed)
    col["mix"] = "resumed (L0 shifted by (Delta + d)(k0 - 1))"
    col_st = phase(mu_col_stationary)
    col_st["mix"] = "stationary turn mix"
    for d in (tp, ta):
        if d.get("drains"):
            rem = horizon - (d["t_release"] + post_start)
            d["p_relapse"] = escape_probability(mu_f, lam, I_D, cs.n_b, rem)["p_escape"] if rem > 0 else 0.0
    # robustness: the smallest phase-1 rate that still releases by the deadline (tick rounding and min_on ignored)
    budget = release_by - hold - t_on - c_on - lam * c_on / (mu_c - lam) if mu_c > lam else -1.0
    T1_max = budget * (mu_c - lam) / mu_c if budget > 0 else 0.0
    mu1_needed = D0 / T1_max if T1_max > 0 else math.inf
    out.update(two_phase=tp, two_phase_annealed=ta, phase1_collapsed=col, phase1_collapsed_stationary_mix=col_st,
               mu_phase1_collapsed_resumed=mu_col_resumed, mu_phase1_collapsed_stationary=mu_col_stationary, mu_cap_fresh=mu_c, mu_phase1_fluid=mu1_fluid,
               mu_phase1_annealed=mu1_ann, mu_phase1_needed_for_deadline=mu1_needed,
               mu_phase1_needed_over_fluid=mu1_needed / mu1_fluid if mu1_fluid > 0 else math.inf,
               n_eff_phase1=float(base.get("n_eff", math.nan)), phase1_margin_to_n_b=float(cs.n_b - base.get("n_eff", math.nan)))
    return out


def mu_resumed(m: Model, infl: float, cap: float) -> float:
    """Approach B's composition-adjusted capped throughput (fluid_rigorous.oos.rescue_pause_cap), as a function of the footprint
    inflation: cap resumed mid-session sessions see the pool as M / infl, and one forced miss per resumed session lowers the
    follow-up hit probability by 1/(E[T] - 1).  If the cap population is memory-gated at that hit rate, the all-miss rate."""
    from scipy.optimize import brentq
    from ..fluid_rigorous.model import summarize_curve
    m_eff = Model(m.wl, m.cost, m.M / infl)
    cs_eff = summarize_curve(m_eff)
    ng = np.linspace(0.0, max(cs_eff.n_b, cap) * 1.5, 3000)
    _, hit_e, _ = curve_on_grid(cs_eff, ng)
    h_cap = float(np.interp(cap, ng, hit_e)) / (1.0 - 1.0 / m.ET)
    h_adj = max(0.0, h_cap - 1.0 / (m.ET - 1.0))
    f = lambda nu: nu / m.ET * m_eff.lifetime(m_eff.server(nu, h_adj)) - cap
    nu = brentq(f, 1e-9, m_eff.nu_cap(h_adj) * (1 - 1e-9))
    if m_eff.server(nu, h_adj).K_run > m_eff.M:
        return float(m_eff.bad()["mu"])
    return float(nu / m.ET)


# ------------------------------------------------------------------------------------------------ registration rules


def registration_consequence(p_by_mult: Dict[float, float], mu_max: float, lam_ref: float, grid_mu: Dict[float, float],
                             margin: float = 0.05) -> Dict[str, object]:
    """The registered rules applied to the model's own predictions (graft of approach A): hi = the largest E0b multiple that
    is predicted stable (P < 1/2) together with every smaller one, capped by mu_max/lam_ref; lambda points at 1/3 and 2/3 of
    (1, hi) rounded to 0.05; cap = the smallest Stage C grid n with mu(n) >= (1 - margin) max_grid mu."""
    ms = sorted(p_by_mult)
    hi = math.nan
    for x in ms:
        if all(p_by_mult[y] < 0.5 for y in ms if y <= x):
            hi = x
    hi_c = min(hi, mu_max / lam_ref) if math.isfinite(hi) else math.nan
    pts = None
    if math.isfinite(hi_c) and hi_c > 1.0:
        pts = [round(round((1 + (hi_c - 1) * f) / 0.05) * 0.05, 2) for f in (1 / 3, 2 / 3)]
    peak = max(grid_mu.values())
    cap = min(n for n, v in grid_mu.items() if v >= (1 - margin) * peak)
    return dict(hi_mult=hi, hi_capped=hi_c, lambda_points=pts, n_cap=cap, grid_argmax=max(grid_mu, key=grid_mu.get))


# ------------------------------------------------------------------------------------------------ secondary edge criterion


def _live_paths(rng, m: Model, arrivals: np.ndarray, S_good: float, horizon: float, dt: float) -> np.ndarray:
    """Live KV volume (every present session's KV as if nothing were evicted: E_k while turn k runs for S_good, E_k during the
    following tool call) of sessions arriving at ``arrivals``, on a grid of step dt (vectorised shot noise; approach A)."""
    wl = m.wl
    nt = int(math.ceil(horizon / dt)) + 2
    diff = np.zeros(nt + 1)
    n_s = len(arrivals)
    if n_s == 0:
        return np.zeros(nt)
    T = np.minimum(rng.geometric(1.0 / wl.mean_turns, size=n_s), wl.K)
    tot = int(T.sum())
    sid = np.repeat(np.arange(n_s), T)
    first = np.cumsum(T) - T
    k = np.arange(tot) - np.repeat(first, T)
    last = k == np.repeat(T - 1, T)
    Z = rng.exponential(wl.zmean, size=tot)
    Z[last] = 0.0
    step = S_good + Z
    cs_ = np.cumsum(step)
    t_turn = arrivals[sid] + (cs_ - step) - np.repeat(cs_[first] - step[first], T)
    E = wl.E[k]
    seg_t0 = np.concatenate([t_turn, t_turn + S_good])
    seg_t1 = np.concatenate([t_turn + S_good, t_turn + S_good + Z])
    seg_v = np.concatenate([E, E])
    keep = (seg_t1 > seg_t0) & (seg_t0 < horizon)
    i0 = np.clip(np.ceil(seg_t0[keep] / dt).astype(np.int64), 0, nt)
    i1 = np.clip(np.ceil(seg_t1[keep] / dt).astype(np.int64), 0, nt)
    np.add.at(diff, i0, seg_v[keep])
    np.add.at(diff, i1, -seg_v[keep])
    return np.cumsum(diff)[:nt]


def edge_level_crossing(m: Model, cs: CurveSummary, lam_ref: float, mults: Sequence[float], horizon: float = 3000.0,
                        n_rep: int = 400, seed: int = 0, q_final: float = 50.0) -> Dict[str, object]:
    """Approach A's from-empty criterion (R6) on THIS model's curve, reported as a secondary prediction: a run escapes when
    the live KV volume of the Poisson session process (M/G/inf shot noise, good-state service time) first reaches the live
    demand at the basin boundary, D_live(n_u(lam)); it fails the E0b rule if the escape leaves time for the queue to reach
    q_final at the trapped drift: t_esc < horizon - q_final / (lam - mu_b).  Monte Carlo with fixed seeds."""
    ng, _ = mu_good_of_n(cs)
    pts = cs.pts[: len(ng)]
    n_arr = np.array([p["n"] for p in pts])
    D_arr = np.array([live_demand(m, p) for p in pts])
    S_arr = np.array([p["S_bar"] for p in pts])
    o = np.argsort(n_arr)
    n_arr, D_arr, S_arr = n_arr[o], D_arr[o], S_arr[o]
    rows = []
    for i, x in enumerate(mults):
        lam = float(x) * lam_ref
        eq = open_equilibria(cs, lam)
        if not math.isfinite(eq.n1):
            rows.append(dict(mult=float(x), p_unstable=1.0, note="lam >= mu_max"))
            continue
        if lam <= cs.mu_b:
            rows.append(dict(mult=float(x), p_unstable=0.0, note="lam <= mu_b"))
            continue
        V2 = float(np.interp(eq.n_u, n_arr, D_arr))
        S_good = float(np.interp(eq.n1, n_arr, S_arr))
        t_lim = horizon - q_final / (lam - cs.mu_b)
        rng = np.random.default_rng(seed + 1000 * i)
        hits = 0
        for _ in range(n_rep):
            n_a = rng.poisson(lam * horizon)
            arr = np.sort(rng.uniform(0.0, horizon, size=n_a))
            V = _live_paths(rng, m, arr, S_good, horizon, 1.0)
            idx = np.nonzero(V >= V2)[0]
            if len(idx) and idx[0] < t_lim:
                hits += 1
        rows.append(dict(mult=float(x), p_unstable=hits / n_rep, V2=V2, S_good=S_good, t_lim=t_lim))
    ps = [(r["mult"], r["p_unstable"]) for r in rows]
    e50 = math.nan
    for (a, pa), (b, pb) in zip(ps[:-1], ps[1:]):
        if pa < 0.5 <= pb:
            e50 = a + (b - a) * (0.5 - pa) / (pb - pa)
            break
    return dict(rows=rows, edge50_mult=e50, n_rep=n_rep, criterion="A's R6 level crossing of D_live(n_u) on the merged curve")
