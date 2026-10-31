"""N3 TOOLSLOW: a temporary tool-latency increase at 1.35 x lambda_ref on the A100 300k cell, NOBURST arrivals (CRN with the
E2 NOBURST arm), every tool call that STARTS in [1200, 2100) s lasting its drawn Z plus delta (delta = 10 or 30 s), 8700 s,
evaluation [5700, 8700) s with the E2/B1 endpoints (STUCK := hit < 0.2; GOOD := hit > 0.8 and no growth).

    PYTHONPATH="src;." python -m analysis.theory.pred2.toolslow      # -> results/theory/pred2/toolslow.json

Driver around the frozen quasi-static model (no frozen function changed):
  * NEW INPUT, the tool-time law during the slowdown: Z + delta with Z ~ Exp(5 s) (a shifted exponential, the protocol's
    law), as a Workload subclass that overrides only the law's F, E[min(Z, r)], mean, density at 0 and inverse.  The frozen
    Model, curve and open-system functions are applied to it unchanged.  Sensitivity: an exponential of the same mean
    (5 + delta), which the frozen Workload supports natively;
  * quasi-static time-varying driver (A5 with a switched curve): n(1200) = n1(lambda) of the normal curve; dn/dt =
    lambda - mu(n; delta) on [1200, 2100); dn/dt = lambda - mu(n; 0) afterwards.  Approximations: the internal state (R, h,
    the turn mix) relaxes at once to the stationary state of the current curve at the current n; the switch is instantaneous
    (tool calls that start just before 2100 s end up to delta + ~5 s later: band 'switch at 2100 + delta');
  * verdict: STUCK iff n(2100) > n_u(lambda) of the normal curve (then dn/dt > 0 for good); critical delta* = the delta at
    which n(2100) = n_u, and delta_mu = the delta at which the slowed curve's peak equals lambda (no good state during the
    slowdown above it);
  * stochastic layer (heuristic, the frozen F2 pieces): P_slow = F2 escape on the slowed curve over the 900 s (target its
    n_b(delta), as F2; band: target n_u(lambda) of the normal curve); after the switch the frozen committor of the normal
    curve from X0 = n(2100) (session units, stationary composition) and the F2 background escape until the stuck-by /
    good-from times.  P(STUCK) = P_slow + (1 - P_slow)(q0 + (1 - q0) P_esc);
  * per seed (exact client plans, seeds 0-2): X0 = the number of the plan's sessions alive at 2100 s, walking every session
    with the slowed curve's good-state service time per turn and its own tool times (+ delta for tool calls starting in the
    slowdown); the committor is then evaluated at that X0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import Model, Workload, kv_dispersion, open_equilibria, summarize_curve
from ..merged import extras as X
from .common import E2_CONFIG, cell, client_plan, eval_times, write_json

CELL, MULT = "a100_300k", 1.35
T_ON, T_OFF, WIN = 1200.0, 2100.0, (5700.0, 8700.0)
DELTAS = [10.0, 30.0]
SEEDS = [0, 1, 2]


@dataclass(frozen=True)
class ShiftedExpWorkload(Workload):
    """Tool time Z' = shift + Exp(zbar): a NEW INPUT law (the TOOLSLOW protocol), not a change of the frozen Workload."""
    shift: float = 0.0

    @property
    def zmean(self) -> float:
        return float(self.zbar) + float(self.shift)

    def F(self, r: float) -> float:
        if r <= self.shift:
            return 0.0
        return float(1.0 - math.exp(-(r - self.shift) / self.zbar))

    def Emin(self, r: float) -> float:
        if r <= 0:
            return 0.0
        if r <= self.shift:
            return float(r)
        return float(self.shift + self.zbar * (1.0 - math.exp(-(r - self.shift) / self.zbar)))

    def dens0(self) -> float:
        return 0.0 if self.shift > 0 else 1.0 / self.zbar

    def Finv(self, h: float) -> float:
        if h <= 0:
            return 0.0
        if h >= 1:
            return math.inf
        return float(self.shift - self.zbar * math.log1p(-h))


def slowed_model(m: Model, delta: float, law: str = "shifted") -> Model:
    wl = m.wl
    if law == "shifted":
        w2 = ShiftedExpWorkload(L0=wl.L0, delta=wl.delta, d=wl.d, mean_turns=wl.mean_turns, K=wl.K, zbar=wl.zbar,
                                tool_mix=wl.tool_mix, x_hit=wl.x_hit, shift=float(delta))
    else:                                            # exponential of the same mean (frozen Workload)
        w2 = replace(wl, zbar=float(wl.zbar) + float(delta))
    return Model(w2, m.cost, m.M)


class Curve:
    def __init__(self, m: Model, lam: float):
        self.m = m
        self.cs = summarize_curve(m)
        self.mu_f = X.curve_fn(self.cs)[0]                                   # as the frozen burst / rescue layers
        self.mu_ode = X.curve_fn(self.cs, n_max=max(self.cs.n_b * 2.5, 200.0))[0]   # flat at mu_b far beyond n_b
        self.eq = open_equilibria(self.cs, lam)
        pk = min(self.cs.pts, key=lambda p: abs(p["mu"] - self.cs.mu_max))
        self.I_D = kv_dispersion(m.wl, pk["S_bar"])["I_D"]
        gs = X.good_state(m, self.cs, lam)
        self.good = gs


def integrate(lam: float, n0: float, segments: List, dt: float = 0.5) -> Dict[str, np.ndarray]:
    """Quasi-static dn/dt = lam - mu(n) with the curve switched per segment [(t0, t1, mu_f), ...] (explicit Euler)."""
    ts, ns = [], []
    n = float(n0)
    for t0, t1, mu_f in segments:
        t = t0
        while t < t1 - 1e-9:
            ts.append(t)
            ns.append(n)
            h = min(dt, t1 - t)
            n = max(0.0, n + h * (lam - float(mu_f(n))))
            t += h
    ts.append(segments[-1][1])
    ns.append(n)
    return dict(t=np.array(ts), n=np.array(ns))


def fluid_verdict(base: Curve, slow: Curve, lam: float, t_off: float = T_OFF) -> Dict[str, object]:
    n0 = base.eq.n1
    tr = integrate(lam, n0, [(T_ON, t_off, slow.mu_ode), (t_off, WIN[1], base.mu_ode)])
    n_off = float(np.interp(t_off, tr["t"], tr["n"]))
    n_end = float(tr["n"][-1])
    stuck = bool(n_off > base.eq.n_u)
    return dict(n_at_on=n0, n_at_off=n_off, n_at_end=n_end, n_max_slowdown=float(tr["n"][tr["t"] < t_off].max()),
                n_u_normal=base.eq.n_u, verdict="STUCK" if stuck else "GOOD", trace_t=tr["t"][::120], trace_n=tr["n"][::120])


def plan_population(plan, delta: float, S: float, t_probe: float) -> Dict[str, float]:
    """Sessions of the exact plan alive at t_probe, each walked with service S per turn and its own tool times, + delta for
    tool calls starting in [T_ON, T_OFF)."""
    alive, alive_max, n_long = 0, 0, 0
    ends = []
    for s in plan:
        t = s.arrival_s
        for k in range(s.n_turns):
            t += S
            if k < s.n_turns - 1:
                z = s.tool_times_s[k]
                if T_ON <= t < T_OFF:
                    z += delta
                    n_long += 1
                t += z
        ends.append((s.arrival_s, t))
    ends = np.array(ends)
    alive = int(np.sum((ends[:, 0] <= t_probe) & (ends[:, 1] > t_probe)))
    grid = np.arange(T_ON, T_OFF + delta + 10.0, 5.0)
    alive_t = np.array([np.sum((ends[:, 0] <= g) & (ends[:, 1] > g)) for g in grid])
    return dict(alive_at_probe=alive, max_alive_slowdown=int(alive_t[grid < T_OFF].max()),
                max_alive_switch=int(alive_t[grid >= T_OFF].max()), lengthened_tool_calls=n_long)


def stochastic(base: Curve, slow: Curve, lam: float, X0: float, stuck_by: float, good_from: float,
               slow_target: str = "n_b_slow") -> Dict[str, float]:
    if slow.eq.n1 != slow.eq.n1:
        # no good state on the slowed curve: the passage is deterministic (the fluid n(2100) carries it into X0)
        p_slow = 0.0
    else:
        x_t = slow.cs.n_b if slow_target == "n_b_slow" else base.eq.n_u
        p_slow = escape_probability(slow.mu_f, lam, slow.I_D, x_t, T_OFF - T_ON)["p_escape"]
    q0 = X.committor(base.mu_f, lam, base.I_D, base.cs.n_b, base.eq.n1, X0)
    pe_s = escape_probability(base.mu_f, lam, base.I_D, base.cs.n_b, max(stuck_by - T_OFF, 0.0))["p_escape"]
    pe_g = escape_probability(base.mu_f, lam, base.I_D, base.cs.n_b, max(good_from - T_OFF, 0.0))["p_escape"]
    p_stuck = p_slow + (1 - p_slow) * (q0 + (1 - q0) * pe_s)
    p_good = (1 - p_slow) * (1 - q0) * (1 - pe_g)
    return dict(X0=X0, p_escape_slowdown=p_slow, committor_after=q0, p_escape_after_stuck=pe_s, p_escape_after_good=pe_g,
                p_stuck=p_stuck, p_good=p_good, p_neither=max(0.0, 1 - p_stuck - p_good))


def run() -> Dict[str, object]:
    c = cell(CELL)
    lam = MULT * c.lam_ref
    base = Curve(c.m, lam)
    stuck_by, good_from = eval_times(base.good["hit"], *WIN)
    out: Dict[str, object] = dict(cell=CELL, mult=MULT, lam=lam, protocol=dict(t_on=T_ON, t_off=T_OFF, window=WIN),
                                  stuck_by_s=stuck_by, good_from_s=good_from,
                                  normal_curve=dict(n1=base.eq.n1, n_u=base.eq.n_u, n_b=base.cs.n_b, mu_max=base.cs.mu_max))
    # ---- the slowed curves on a delta grid (shifted law = protocol; exponential of the same mean = sensitivity)
    grid = sorted(set(DELTAS) | {0.0, 2.0, 4.0, 6.0, 8.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0, 20.0, 25.0})
    curves: Dict[str, Dict[float, Curve]] = {"shifted": {}, "exp_same_mean": {}}
    table = {}
    for law in curves:
        rows = {}
        for d in grid:
            cv = Curve(slowed_model(c.m, d, law), lam)
            curves[law][d] = cv
            fv = fluid_verdict(base, cv, lam)
            rows[f"{d:g}"] = dict(mu_max=cv.cs.mu_max, peak_n=cv.cs.n_star, hit_at_peak=cv.cs.h_star, n_b=cv.cs.n_b,
                                  folds=len(cv.cs.folds), good_state_exists=bool(cv.eq.n1 == cv.eq.n1),
                                  n1=cv.eq.n1, n_u=cv.eq.n_u, hit_at_n1=cv.good.get("hit"), S_bar_n1=cv.good.get("S_bar"),
                                  n_at_off=fv["n_at_off"], verdict=fv["verdict"])
        table[law] = rows
    out["delta_table"] = table
    # ---- critical deltas (bisection on the shifted law)
    def n_off(d: float, t_off: float = T_OFF) -> float:
        return fluid_verdict(base, Curve(slowed_model(c.m, d), lam), lam, t_off)["n_at_off"]

    def mu_gap(d: float) -> float:
        return Curve(slowed_model(c.m, d), lam).cs.mu_max - lam

    def bisect(f, lo: float, hi: float, it: int = 18) -> float:
        flo = f(lo)
        for _ in range(it):
            mid = 0.5 * (lo + hi)
            if (f(mid) > 0) == (flo > 0):
                lo, flo = mid, f(mid)
            else:
                hi = mid
        return 0.5 * (lo + hi)

    d_mu = bisect(mu_gap, 10.0, 20.0)
    d_star = bisect(lambda d: n_off(d) - base.eq.n_u, 10.0, 20.0)
    d_star_late = bisect(lambda d: n_off(d, T_OFF + d) - base.eq.n_u, 10.0, 20.0)
    out["critical_delta"] = dict(delta_mu_max_equals_lambda=d_mu, delta_star_fluid=d_star, delta_star_switch_at_2100_plus_delta=d_star_late)
    # ---- review fix (2026-10-31): the STOCHASTIC 50% delta, for scoring a later delta sweep.  P(STUCK)(delta) of the
    #      exchangeable stochastic layer on a 0.25 s grid.  It is NOT monotone: for delta in (delta_mu, delta*) there is no
    #      slowed good state, P_slow is set to 0 and no noise is added during the passage (the fluid n(2100) carries the
    #      state), so P(STUCK) drops at delta_mu (from about 0.44 to 0.05) and then rises along the committor of n(2100).
    sgrid = [round(x, 2) for x in np.arange(4.0, 20.0001, 0.25)]
    sp, sb_ = [], []
    for d in sgrid:
        cv = Curve(slowed_model(c.m, d), lam)
        nf = fluid_verdict(base, cv, lam)["n_at_off"]
        sp.append(stochastic(base, cv, lam, nf, stuck_by, good_from)["p_stuck"])
        sb_.append(stochastic(base, cv, lam, nf, stuck_by, good_from, slow_target="n_u_normal")["p_stuck"])

    def crossings(y):
        xs = []
        for i in range(1, len(y)):
            if (y[i - 1] < 0.5) != (y[i] < 0.5):
                xs.append(dict(delta=float(sgrid[i - 1] + (0.5 - y[i - 1]) / (y[i] - y[i - 1]) * (sgrid[i] - sgrid[i - 1])),
                               direction="up" if y[i] > y[i - 1] else "down"))
        return xs

    cp, cb = crossings(sp), crossings(sb_)
    out["critical_delta"].update(
        delta_50_stochastic_PRIMARY=[x["delta"] for x in cp if x["direction"] == "up"][-1],
        delta_50_stochastic_crossings=cp, delta_50_band_target_n_u_first=[x["delta"] for x in cb if x["direction"] == "up"][0],
        delta_50_band_target_n_u_crossings=cb,
        p_stuck_scan=dict(delta=sgrid, p_stuck=sp, p_stuck_band_target_n_u=sb_),
        note="P(STUCK) is not monotone in delta: above delta_mu no slowed good state exists, P_slow = 0 and no noise is added "
             "during the passage, so the layer drops at delta_mu; the primary 50% point is the last upward crossing (the "
             "committor branch); the band (escape target n_u) first crosses 0.5 below delta_mu")
    # ---- the registered deltas and delta*: fluid verdict, stochastic layer, per seed
    res = {}
    plans = {sd: client_plan(E2_CONFIG, sd, MULT, WIN[1], 0)[0] for sd in SEEDS}
    for d in DELTAS + [round(d_star, 2)]:
        cv = curves["shifted"].get(d) or Curve(slowed_model(c.m, d), lam)
        fv = fluid_verdict(base, cv, lam)
        fv_late = fluid_verdict(base, cv, lam, T_OFF + d)
        st = stochastic(base, cv, lam, fv["n_at_off"], stuck_by, good_from)
        st_band = stochastic(base, cv, lam, fv["n_at_off"], stuck_by, good_from, slow_target="n_u_normal")
        S_q = cv.good.get("S_bar") if cv.good.get("exists") else base.good["S_bar"]
        seeds = {}
        for sd, plan in plans.items():
            pp = plan_population(plan, d, float(S_q), T_OFF)
            seeds[str(sd)] = dict(plan_population=pp, stochastic=stochastic(base, cv, lam, float(pp["alive_at_probe"]), stuck_by,
                                                                            good_from))
        exp_cv = Curve(slowed_model(c.m, d, "exp_same_mean"), lam)
        res[f"{d:g}"] = dict(fluid=fv, fluid_switch_at_2100_plus_delta=dict(n_at_off=fv_late["n_at_off"], verdict=fv_late["verdict"]),
                             slowed_curve=dict(mu_max=cv.cs.mu_max, n1=cv.eq.n1, n_u=cv.eq.n_u, n_b=cv.cs.n_b, I_D=cv.I_D,
                                               good_state=cv.good),
                             stochastic=st, stochastic_band_target_n_u=st_band, per_seed=seeds, service_per_turn_plan_walk=S_q,
                             sensitivity_exp_same_mean=fluid_verdict(base, exp_cv, lam)["verdict"])
    out["deltas"] = res
    pg10 = [res["10"]["per_seed"][str(s)]["stochastic"]["p_good"] for s in SEEDS]
    ps30 = [res["30"]["per_seed"][str(s)]["stochastic"]["p_stuck"] for s in SEEDS]
    from .common import at_least
    out["rule"] = dict(statement="delta = 10 GOOD in >= 2/3 seeds and delta = 30 STUCK in >= 2/3",
                       p_good_10_per_seed=pg10, p_stuck_30_per_seed=ps30,
                       p_rule=at_least(pg10, 2) * at_least(ps30, 2),
                       p_rule_exchangeable=at_least([res["10"]["stochastic"]["p_good"]] * 3, 2) *
                       at_least([res["30"]["stochastic"]["p_stuck"]] * 3, 2))
    return out


def main() -> None:
    p = write_json("toolslow", run())
    print("wrote", p)


if __name__ == "__main__":
    main()
