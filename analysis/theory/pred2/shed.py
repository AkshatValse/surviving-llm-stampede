r"""N4 SHED and Proposition S: an arrival stop (load shedding) inside the 300k trap at 1.35 x lambda_ref.

Protocol (remedy N4): burst of 200 in 60 s at 1200 s; arrivals stopped from 1800 s for tau (600 or 3600 s), then resumed at
1.35 x (arrivals.kind: ramp, ramp_is_mult, knots [[0,1.35],[1800,1.35],[1800.001,0],[1800+tau,0],[1800+tau+0.001,1.35],
[8700,1.35]], plus the burst); 8700 s; evaluation [5700, 8700) s with the E2/B1 endpoints.

    PYTHONPATH="src;." python -m analysis.theory.pred2.shed          # -> results/theory/pred2/shed.json

Proposition S (quasi-static, fold-free curve; proof in notes/PREDICTIONS_r13_pred2.md): a rate cut to lambda' for a time
tau, started at x0 > n_u(lambda), rescues (n relaxes to n1 after the rate returns to lambda) iff lambda' < mu(n) on
[n_u, x0] -- i.e. lambda' < mu_b = lambda_miss when x0 >= n_b, by A4 -- and tau >= tau_min = int_{n_u}^{x0} dn / (mu(n) - lambda').
It refuses (lambda - lambda') tau arrivals; a cap c in (n1, n_u) (T9) refuses none.

Drivers (no frozen function changed):
  * x0 = n(1800 s) from the frozen trapped round robin (fluid_rigorous.trapped.round_robin_trap; R1's n_on);
  * tau_min (Prop. S) with the frozen fluid curve mu(n) (mu_b beyond n_b);
  * composition-aware band: the frozen round-robin recursion, re-run with a TIME-VARYING arrival input (a copy of the frozen
    loop that takes the arrivals of each step from a function; with a constant rate it reproduces the frozen function exactly,
    which is asserted), until n falls to n_b, plus the good-branch transit n_b -> n_u;
  * per seed (exact client plans, seeds 0-2): the same recursion fed with the plan's own arrivals after 1200 s (base and
    burst, each with its own turn count) on the fluid background n1 at 1200 s; and the exact number of arrivals the stop
    refuses (the ramp plan's thinned candidates, identical to the BURST arm's base arrivals in the stop window);
  * stochastic layer: the frozen committor of the normal curve from X0 = n(1800 + tau), and after a full drain the F2
    from-empty escape until the stuck-by / good-from times.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import Model, open_equilibria
from ..fluid_rigorous.trapped import round_robin_trap
from ..merged import extras as X
from .common import E2_CONFIG, LREF_300K_REG, at_least, cell, client_plan, eval_times, write_json

CELL, MULT = "a100_300k", 1.35
T_B, WIDTH, BURST_N, T_STOP, END = 1200.0, 60.0, 200.0, 1800.0, 8700.0
WIN = (5700.0, 8700.0)
TAUS = [600.0, 3600.0, 1800.0]
SEEDS = [0, 1, 2]


def round_robin_tv(m: Model, n_bg: float, add: Callable[[float, float], List[Tuple[float, float]]], t_b: float = T_B,
                   t_end: float = END, dt: float = 1.0, stop_below: Optional[float] = None,
                   check_from: float = T_STOP) -> Dict[str, np.ndarray]:
    """The frozen fluid_rigorous.trapped.round_robin_trap recursion with the arrivals of step [t, t + dt) given by
    add(t, dt) -> [(mass, T)], T = math.inf for the frozen geometric survival q^(k-1), else a known turn count (survival
    1{phase < T + 1}).  Identical statements otherwise.  Stops at the first t >= check_from with n_sys < stop_below (the trap's
    validity ends; before the stop the population is the good background plus the burst, so the check starts at the stop)."""
    wl = m.wl
    b = m.bad()
    q = 1.0 - 1.0 / wl.mean_turns
    delta_dec = (1.0 - b["p"]) / b["nu"]
    L0, inc, d, K = wl.L0, wl.delta + wl.d, wl.d, wl.K
    cpar = m.cost

    def P_of(Kc):
        return L0 + (np.floor(Kc) - 1.0) * inc

    def g_of(Kc):
        P = P_of(Kc)
        return cpar.a * np.maximum(1.0, P / cpar.chunk) + np.maximum(cpar.f, cpar.b * P) + cpar.cp * P * (P + 1) / 2.0 + delta_dec

    def G_of(Kc, Tc):
        geo = np.where(Kc < K + 1, q ** (Kc - 1.0), 0.0)
        return np.where(np.isinf(Tc), geo, (Kc < Tc + 1).astype(float))

    ks = np.arange(1, K + 1, dtype=float)
    mass_a = np.array(n_bg * wl.w / wl.G)
    phase_a = ks + 0.5
    T_a = np.full(K, math.inf)
    times = np.arange(t_b, t_end + dt, dt)
    out = {k: np.full_like(times, np.nan) for k in ("n_sys", "c", "completions", "gap_over_R")}
    for it, t in enumerate(times):
        new = add(float(t), dt)
        if new:
            mass_a = np.append(mass_a, [x[0] for x in new])
            phase_a = np.append(phase_a, np.ones(len(new)))
            T_a = np.append(T_a, [x[1] for x in new])
        G = G_of(phase_a, T_a)
        pres = mass_a * G
        n_sys = pres.sum()
        c = float((pres * g_of(phase_a)).sum())
        P = P_of(phase_a)
        out["n_sys"][it] = n_sys
        out["c"][it] = c
        # sessions ending per second: geometric cohorts end w.p. 1/mean_turns per turn; known-T cohorts at their last turn
        last = np.where(np.isinf(T_a), 1.0 / wl.mean_turns, (np.floor(phase_a) == T_a).astype(float))
        out["completions"][it] = float((pres * last).sum()) / c if c > 0 else 0.0
        out["gap_over_R"][it] = float((pres * (P + d)).sum()) / m.M
        if stop_below is not None and t >= check_from and n_sys < stop_below:
            break
        if c > 0:
            phase_a = phase_a + dt / c
        keep = (phase_a < K + 1) & ~((~np.isinf(T_a)) & (phase_a >= T_a + 1))
        mass_a, phase_a, T_a = mass_a[keep], phase_a[keep], T_a[keep]
    out["t"] = times
    return out


def fluid_add(lam_fn: Callable[[float], float], burst_n: float = BURST_N):
    def add(t: float, dt: float):
        a = lam_fn(t) * dt
        if T_B <= t < T_B + WIDTH:
            a += burst_n / WIDTH * dt
        return [(a, math.inf)]
    return add


def plan_add(plan, t_stop: float, tau: float):
    """Arrivals of the exact plan after T_B (base and burst), minus the base arrivals refused by the stop."""
    arr = sorted((s.arrival_s, s.n_turns, s.origin) for s in plan if s.arrival_s >= T_B and
                 not (s.origin == "base" and t_stop <= s.arrival_s < t_stop + tau))
    ts = np.array([a[0] for a in arr])
    Ts = [float(a[1]) for a in arr]

    def add(t: float, dt: float):
        i0, i1 = np.searchsorted(ts, t), np.searchsorted(ts, t + dt)
        return [(1.0, Ts[i]) for i in range(i0, i1)]
    return add


def tau_min_quasi_static(mu_f, n_u: float, n_b: float, mu_b: float, x0: float, lam_prime: float = 0.0) -> Dict[str, float]:
    if not lam_prime < mu_b:
        return dict(rescues=False, reason="lambda' >= mu_b = lambda_miss: the trapped population does not shrink")
    ng = np.linspace(n_u, x0, 20001)
    f = 1.0 / (mu_f(ng) - lam_prime)
    tau = float(np.trapz(f, ng))
    nn = np.linspace(n_u, n_b, 2001)
    good_part = float(np.trapz(1.0 / (mu_f(nn) - lam_prime), nn))
    return dict(rescues=True, tau_min=tau, all_miss_part=(x0 - n_b) / (mu_b - lam_prime), good_branch_part=good_part)


def drain_quasi_static(mu_f, x0: float, tau: float, dt: float = 0.5) -> float:
    n, t = float(x0), 0.0
    while t < tau - 1e-9 and n > 1e-6:
        h = min(dt, tau - t)
        n = max(0.0, n - h * float(mu_f(n)))
        t += h
    return n


def run() -> Dict[str, object]:
    c = cell(CELL)
    m, cs = c.m, c.cs
    lam = MULT * c.lam_ref
    eq = open_equilibria(cs, lam)
    gs = X.good_state(m, cs, lam)
    stuck_by, good_from = eval_times(gs["hit"], *WIN)
    mu_big = X.curve_fn(cs, n_max=600.0, npts=24000)[0]
    # ---- x0 = n(1800) in the frozen round robin, and the regression check of the time-varying copy
    fr = round_robin_trap(m, lam, eq.n1, t_b=T_B, burst_n=BURST_N, burst_w=WIDTH, t_end=END)
    x0 = float(np.interp(T_STOP, fr["t"], fr["n_sys"]))
    tv = round_robin_tv(m, eq.n1, fluid_add(lambda t: lam))
    regress = float(np.max(np.abs(tv["n_sys"] - fr["n_sys"])))
    assert regress < 1e-9, regress
    out: Dict[str, object] = dict(cell=CELL, mult=MULT, lam=lam, n1=eq.n1, n_u=eq.n_u, n_b=cs.n_b, mu_b=cs.mu_b,
                                  x0_n_at_1800=x0, round_robin_regression_max_abs_diff=regress,
                                  stuck_by_s=stuck_by, good_from_s=good_from)
    # ---- Proposition S: tau_min for lambda' = 0 (the registered stop) and partial cuts
    out["tau_min"] = {f"{lp:g}": tau_min_quasi_static(mu_big, eq.n_u, cs.n_b, cs.mu_b, x0, lp * cs.mu_b)
                      for lp in (0.0, 0.25, 0.5, 0.75)}
    out["tau_min"]["note"] = "keys: lambda' as a fraction of mu_b = lambda_miss; tau_min diverges as lambda' -> mu_b"
    # ---- composition-aware band: round robin with lambda = 0 from 1800 s until n_b, then the good-branch transit
    stop = round_robin_tv(m, eq.n1, fluid_add(lambda t: 0.0 if t >= T_STOP else lam), stop_below=cs.n_b)
    ok = ~np.isnan(stop["n_sys"])
    t_nb = float(stop["t"][ok][-1])
    i1800 = int(np.argmin(np.abs(stop["t"] - T_STOP)))
    rr_rate_1800 = float(stop["completions"][i1800])
    good_transit = out["tau_min"]["0"]["good_branch_part"]
    out["round_robin_drain"] = dict(t_reach_n_b=t_nb, tau_min=t_nb - T_STOP + good_transit,
                                    completion_rate_at_1800=rr_rate_1800, completion_rate_at_1800_over_lambda_ref=rr_rate_1800 / c.lam_ref,
                                    completion_rate_at_n_b=float(stop["completions"][ok][-1]),
                                    mean_completion_rate=(x0 - cs.n_b) / max(t_nb - T_STOP, 1e-9))
    # ---- predictions per tau (fluid, round robin, stochastic)
    q50 = None
    xs = np.linspace(eq.n1 + 1e-6, cs.n_b - 1e-6, 4001)
    qs = np.array([X.committor(c.mu_f, lam, c.I_D, cs.n_b, eq.n1, x) for x in xs])
    q50 = float(np.interp(0.5, qs, xs))
    res = {}
    for tau in TAUS:
        n_qs = drain_quasi_static(mu_big, x0, tau)
        rr = round_robin_tv(m, eq.n1, fluid_add(lambda t, tau=tau: 0.0 if T_STOP <= t < T_STOP + tau else lam),
                            t_end=T_STOP + tau, stop_below=cs.n_b)
        okr = ~np.isnan(rr["n_sys"])
        trapped_at_resume = bool(rr["t"][okr][-1] >= T_STOP + tau - 1e-9)
        n_rr = float(rr["n_sys"][okr][-1]) if trapped_at_resume else drain_quasi_static(
            mu_big, cs.n_b, T_STOP + tau - float(rr["t"][okr][-1]))
        recs = {}
        for tag, n_res in (("quasi_static", n_qs), ("round_robin", n_rr)):
            q = X.committor(c.mu_f, lam, c.I_D, cs.n_b, eq.n1, n_res)
            t_res = T_STOP + tau
            pe_s = escape_probability(c.mu_f, lam, c.I_D, cs.n_b, max(stuck_by - t_res, 0.0))["p_escape"]
            pe_g = escape_probability(c.mu_f, lam, c.I_D, cs.n_b, max(good_from - t_res, 0.0))["p_escape"]
            recs[tag] = dict(n_at_resume=n_res, verdict="STUCK" if n_res > eq.n_u else "GOOD", committor=q,
                             p_stuck=q + (1 - q) * pe_s, p_good=(1 - q) * (1 - pe_g))
        res[f"{tau:g}"] = dict(tau=tau, resume_s=T_STOP + tau, expected_sessions_refused=lam * tau, **recs)
    out["taus"] = res
    out["committor_50_point_X"] = q50
    out["tau_50_quasi_static"] = float(tau_for_level(mu_big, x0, q50))
    out["tau_50_round_robin"] = float(t_nb - T_STOP + tau_for_level(mu_big, cs.n_b, q50))
    # ---- per seed: exact client plans (refused counts; plan-driven round robin)
    seeds = {}
    for sd in SEEDS:
        recs = {}
        p_const, rate = client_plan(E2_CONFIG, sd, MULT, END, int(BURST_N), T_B, WIDTH)
        for tau in TAUS:
            knots = [[0, 1.35], [T_STOP, 1.35], [T_STOP + 0.001, 0], [T_STOP + tau, 0], [T_STOP + tau + 0.001, 1.35], [END, 1.35]]
            p_ramp, _ = client_plan(E2_CONFIG, sd, MULT, END, int(BURST_N), T_B, WIDTH, ramp=knots)
            base_c = [s.arrival_s for s in p_const if s.origin == "base"]
            base_r = [s.arrival_s for s in p_ramp if s.origin == "base"]
            refused = len(base_c) - len(base_r)
            in_win = sum(1 for a in base_c if T_STOP <= a < T_STOP + tau)
            kept_ok = set(base_r) <= set(base_c)
            rr = round_robin_tv(m, eq.n1, plan_add(p_const, T_STOP, tau), t_end=T_STOP + tau, stop_below=cs.n_b)
            okr = ~np.isnan(rr["n_sys"])
            n1800 = float(np.interp(T_STOP, rr["t"][okr], rr["n_sys"][okr]))
            trapped = bool(rr["t"][okr][-1] >= T_STOP + tau - 1e-9)
            n_res = float(rr["n_sys"][okr][-1]) if trapped else drain_quasi_static(mu_big, cs.n_b, T_STOP + tau - float(rr["t"][okr][-1]))
            q = X.committor(c.mu_f, lam, c.I_D, cs.n_b, eq.n1, n_res)
            recs[f"{tau:g}"] = dict(refused_sessions=refused, base_arrivals_in_stop_window=in_win, ramp_plan_subset_of_constant=kept_ok,
                                    n_at_1800_plan_round_robin=n1800, t_reach_n_b=None if trapped else float(rr["t"][okr][-1]),
                                    n_at_resume=n_res, verdict="STUCK" if n_res > eq.n_u else "GOOD", committor=q)
        seeds[str(sd)] = recs
    out["per_seed"] = seeds
    # ---- the registered decision rule (configs/agentload_prereg_2026-10-31_shed_t{600,3600}.yaml, commit b006291, read as
    #      protocol only): tau600 STUCK and tau3600 GOOD in >= 2/3 of the REGISTERED seeds 0, 1, i.e. 2 of 2 each.  Seed 2 is
    #      listed above as a prediction only (not registered).  Seeds independent; the quasi-static layer per seed.
    ps600, pg3600 = res["600"]["quasi_static"]["p_stuck"], res["3600"]["quasi_static"]["p_good"]
    out["rule"] = dict(statement="tau600 STUCK in >= 2/3 and tau3600 GOOD in >= 2/3 of the registered seeds 0, 1 (2 of 2 each)",
                       registration="configs/agentload_prereg_2026-10-31_shed_t600.yaml, _t3600.yaml (commit b006291)",
                       registered_seeds=[0, 1], p_stuck_600=ps600, p_good_3600=pg3600,
                       p_rule=ps600 ** 2 * pg3600 ** 2, p_rule_if_three_seeds=ps600 ** 3 * pg3600 ** 3,
                       refused_counts_role="protocol check (fixed by the client plans, not a model prediction)")
    # ---- the cap comparison (R1, frozen): no session refused
    out["cap_comparison"] = dict(refused_sessions=0, note="R1 (cap 20 at 1800 s) defers arrivals at its gate; frozen release "
                                                         "3,830 s at 1.35 x (r13-theory-pred); the stop refuses lambda tau")
    return out


def tau_for_level(mu_f, x_start: float, x_level: float, dt: float = 0.5) -> float:
    """Time for dn/dt = -mu(n) to fall from x_start to x_level (quasi-static, no arrivals)."""
    n, t = float(x_start), 0.0
    while n > x_level:
        n -= dt * float(mu_f(n))
        t += dt
    return t


def main() -> None:
    p = write_json("shed", run())
    print("wrote", p)


if __name__ == "__main__":
    main()
