"""Open system on top of the closed mean-field curve (model.py).

1. Deterministic skeleton.  dN/dt = lambda - mu(N), mu = the closed mean-field curve (single-valued for the measured cells).
   For lambda in (mu_inf, mu_max) it has a stable good point N1 (ascending crossing) and a saddle N2 (descending crossing);
   for N > N2 the hit fraction falls to 0 and N grows at lambda - mu_inf: the trapped regime (an attractor at infinity).
2. Escape from the good state (from-empty edge, burst size).  The memory sees the live KV volume V(t) = sum of the contexts
   of the sessions present, not N.  In the good state sessions barely interact, so V is the M/G/infinity shot-noise process of
   the workload (arrival Poisson(lambda), each session's KV path: c_run[k] while turn k runs for S_good, c[k] during its tool
   call).  The basin boundary is the saddle expressed as a KV volume, V2(lambda) = N2(lambda) * E_lb (E_lb = time-weighted
   KV per session).  A run escapes when V(t) first reaches V2.  Burst sessions enter as fresh sessions (2000 tokens).
3. Trapped state.  Every present session gets one turn per round of the FCFS queue, every turn misses, and the server is
   busy all the time, so per-session turn rate r = 1 / sum_k n_k tau_k (tau_k = saturated all-miss cost of a turn-k request).
   This gives the backlog path after a burst, the trapped token rate and the reuse gap: one round C = 1 / r, the churn
   r sum_k n_k (L_k + d), hence the loopvars ratio gap / R = C churn / M = sum_k n_k (L_k + d) / M.
4. Cap engaged inside the trap (rescue): attrition to the cap within one round, the capped closed system relaxes to its
   unique (good) mean-field state, the gate drains at mu(N_c) - lambda, release after a 300 s empty hold, then the good
   state persists unless V(t) reaches V2 again.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .model import CheModel, Cell


# ------------------------------------------------------------------------------------------------- closed curve utilities

def mean_field_curve(model: CheModel, ns: Sequence[float]) -> List[Dict]:
    rows = []
    for n in ns:
        fps = model.fixed_points(float(n))
        st = [r for r in fps if r["stable"]]
        good = max(st, key=lambda r: r["h"]) if st else fps[-1]
        bad = min(st, key=lambda r: r["h"]) if st else fps[0]
        rows.append(dict(n=float(n), mu=good["mu"], h=good["h"], hit_all=good["hit_all"], regime=good["regime"],
                         R=good["R"], W=good["W"], B=good["B"], S=good["S"], nu=good["nu"], churn=good["churn"],
                         R_loopvars=good["R_loopvars"], n_fixed_points=len(fps), n_stable=len(st),
                         mu_low_branch=bad["mu"], h_low_branch=bad["h"]))
    return rows


def smoothed_curve(model: CheModel, ns: Sequence[float], nodes: int = 15) -> List[Dict]:
    """Closed-system curve averaged over the Gaussian fluctuation of the live KV volume at fixed n.

    At fixed n the live volume is V = n E_lb (1 + eps) with eps ~ N(0, CV^2 / n) (slots independent in the good state,
    CV = sd / mean of a session's time-weighted KV, computed from the workload).  A volume (1 + eps) times larger is
    equivalent to a pool M / (1 + eps); the time-average throughput is E_eps[mu(n; M / (1 + eps))] (quasi-static).
    """
    x, w = np.polynomial.hermite_e.hermegauss(nodes)
    w = w / w.sum()
    out = []
    cache: Dict[Tuple[float, float], Dict] = {}
    for n in ns:
        g = model.good_branch(float(n))
        S_good = g["S"] if g is not None else 1.5
        m1, m2 = model.wl.lb_moments(min(S_good, 5.0))
        cv = math.sqrt(max(m2 / m1 ** 2 - 1.0, 0.0))
        sd = cv / math.sqrt(max(n, 1.0))
        mu_acc = hit_acc = 0.0
        for xi, wi in zip(x, w):
            eps = max(-0.9, sd * xi)
            M_eff = model.cell.M / (1.0 + eps)
            key = (round(float(n), 6), round(M_eff, 1))
            if key not in cache:
                mm = CheModel(replace(model.cell, M=M_eff))
                cache[key] = mm.good_branch(float(n))
            r = cache[key]
            mu_acc += wi * r["mu"]
            hit_acc += wi * r["hit_all"]
        out.append(dict(n=float(n), mu=mu_acc, hit_all=hit_acc, cv=cv, sd_eps=sd))
    return out


def landmarks(rows: List[Dict], key_mu: str = "mu", key_hit: str = "hit_all", grid_ns: Optional[Sequence[float]] = None,
              big_n: float = 300.0) -> Dict:
    ns = np.array([r["n"] for r in rows])
    mu = np.array([r[key_mu] for r in rows])
    hit = np.array([r[key_hit] for r in rows])
    i = int(np.argmax(mu))
    # 0.5-hit crossing (all-turn hit fraction), first downward crossing after the peak region
    cross = float("nan")
    for j in range(len(ns) - 1):
        if hit[j] >= 0.5 > hit[j + 1]:
            cross = float(ns[j] + (ns[j + 1] - ns[j]) * (hit[j] - 0.5) / (hit[j] - hit[j + 1]))
            break
    out = dict(peak_n=float(ns[i]), mu_max=float(mu[i]), hit_cross_0p5=cross)
    jb = int(np.argmin(np.abs(ns - big_n)))
    out["mu_at_big_n"] = float(mu[jb])
    out["big_n"] = float(ns[jb])
    if grid_ns is not None:
        gm = {float(n): float(np.interp(n, ns, mu)) for n in grid_ns}
        peak = max(gm.values())
        cap = min(n for n, v in gm.items() if v >= 0.95 * peak)
        out["grid_mu"] = gm
        out["grid_argmax"] = max(gm, key=gm.get)
        out["n_cap_smallest_within_5pct"] = cap
    return out


def crossings(rows: List[Dict], lam: float) -> Tuple[float, float]:
    """N1 (ascending crossing of lambda) and N2 (first descending crossing after the peak) of the closed curve."""
    ns = np.array([r["n"] for r in rows])
    mu = np.array([r["mu"] for r in rows])
    i = int(np.argmax(mu))
    if lam >= mu[i]:
        return float("nan"), float("nan")
    N1 = float(np.interp(lam, mu[: i + 1], ns[: i + 1])) if lam > mu[0] else float(ns[0] * lam / mu[0])
    N2 = float("inf")
    for j in range(i, len(ns) - 1):
        if mu[j] >= lam > mu[j + 1]:
            N2 = float(ns[j] + (ns[j + 1] - ns[j]) * (mu[j] - lam) / (mu[j] - mu[j + 1]))
            break
    return N1, N2


def good_state_S(model: CheModel, rows: List[Dict], lam: float) -> float:
    """Running time S of the good open state at arrival rate lam (the closed state at N1)."""
    N1, _ = crossings(rows, lam)
    if not math.isfinite(N1):
        return float("nan")
    g = model.good_branch(N1)
    return g["S"]


# ------------------------------------------------------------------------------------------- live-volume Monte Carlo

@dataclass
class MCResult:
    lam: float
    V2: float
    n_rep: int
    p_escape: float
    t_escape: np.ndarray
    realized_mult: np.ndarray


def _session_paths(rng, wl, arrivals: np.ndarray, S_good: float, horizon: float, dt: float) -> np.ndarray:
    """Live KV volume on a grid of step dt for sessions arriving at ``arrivals`` (vectorised shot noise)."""
    n_s = len(arrivals)
    nt = int(math.ceil(horizon / dt)) + 2
    diff = np.zeros(nt + 1)
    if n_s == 0:
        return np.zeros(nt)
    q = 1.0 / wl.mean_turns
    T = np.minimum(rng.geometric(q, size=n_s), wl.max_turns)
    tot = int(T.sum())
    sid = np.repeat(np.arange(n_s), T)
    first = np.cumsum(T) - T
    k = np.arange(tot) - np.repeat(first, T)                # 0-based turn index
    last = (k == np.repeat(T - 1, T))
    Z = wl.z_sample(rng, tot)
    Z[last] = 0.0
    step = S_good + Z
    cs = np.cumsum(step)
    start_off = np.repeat(cs[first] - step[first], T)        # cumulative before each session's first turn
    t_turn = arrivals[sid] + (cs - step) - start_off        # start of turn k
    c_run = wl.c_run[k]
    c_idle = wl.c[k]
    # service segment [t_turn, t_turn + S_good) with c_run; tool segment [t_turn + S, t_turn + S + Z) with c_idle
    seg_t0 = np.concatenate([t_turn, t_turn + S_good])
    seg_t1 = np.concatenate([t_turn + S_good, t_turn + S_good + Z])
    seg_v = np.concatenate([c_run, c_idle])
    keep = (seg_t1 > seg_t0) & (seg_t0 < horizon)
    i0 = np.clip(np.ceil(seg_t0[keep] / dt).astype(np.int64), 0, nt)
    i1 = np.clip(np.ceil(seg_t1[keep] / dt).astype(np.int64), 0, nt)
    np.add.at(diff, i0, seg_v[keep])
    np.add.at(diff, i1, -seg_v[keep])
    return np.cumsum(diff)[:nt]


def escape_mc(model: CheModel, rows: List[Dict], lam: float, horizon: float, n_rep: int = 400, seed: int = 0,
              dt: float = 1.0, burst_n: int = 0, burst_t: float = 1200.0, burst_w: float = 60.0,
              lam_ref: Optional[float] = None, V2_override: Optional[float] = None,
              t_start_check: float = 0.0) -> MCResult:
    """P(V(t) reaches V2(lam) before ``horizon``) for Poisson(lam) arrivals from empty, optionally with a burst."""
    rng = np.random.default_rng(seed)
    wl = model.wl
    N1, N2 = crossings(rows, lam)
    S_good = good_state_S(model, rows, lam)
    m1, _ = wl.lb_moments(S_good)
    V2 = V2_override if V2_override is not None else N2 * m1
    t_esc = np.full(n_rep, np.inf)
    real = np.zeros(n_rep)
    for r in range(n_rep):
        n_arr = rng.poisson(lam * horizon)
        arr = np.sort(rng.uniform(0.0, horizon, size=n_arr))
        real[r] = n_arr / horizon / (lam_ref if lam_ref else lam)
        if burst_n > 0:
            arr = np.sort(np.concatenate([arr, rng.uniform(burst_t, burst_t + burst_w, size=burst_n)]))
        V = _session_paths(rng, wl, arr, S_good, horizon, dt)
        idx = np.nonzero(V[int(t_start_check / dt):] >= V2)[0]
        if len(idx):
            t_esc[r] = (idx[0] + int(t_start_check / dt)) * dt
    return MCResult(lam=lam, V2=V2, n_rep=n_rep, p_escape=float(np.mean(np.isfinite(t_esc))), t_escape=t_esc,
                    realized_mult=real)


def e0b_unstable_prob(model: CheModel, rows: List[Dict], lam: float, lam_miss: float, horizon: float = 3000.0,
                      q_final: float = 50.0, n_rep: int = 400, seed: int = 0) -> Dict:
    """Probability that a 3000 s from-empty run fails the E0b rule (final queue >= 50).

    After an escape at t the backlog grows at about (lam - lam_miss); the run is unstable if it can reach q_final by the end:
    t < horizon - q_final / (lam - lam_miss)."""
    N1, N2 = crossings(rows, lam)
    if not math.isfinite(N1):
        # lam >= mu_max of the mean-field curve: no good state exists, every run is unstable
        return dict(lam=lam, p_unstable=1.0, p_escape=1.0, V2=float("nan"), note="lambda above mu_max")
    if lam <= lam_miss:
        return dict(lam=lam, p_unstable=0.0, p_escape=0.0, V2=float("nan"), note="lambda below lambda_miss")
    res = escape_mc(model, rows, lam, horizon, n_rep=n_rep, seed=seed)
    t_lim = horizon - q_final / (lam - lam_miss)
    p = float(np.mean(res.t_escape < t_lim))
    return dict(lam=lam, p_unstable=p, p_escape=res.p_escape, V2=res.V2, t_lim=t_lim)


# ---------------------------------------------------------------------------------------------- trapped-state fluid model

def trap_fluid(model: CheModel, lam: float, n0: np.ndarray, t0: float, t1: float, dt: float = 1.0,
               cap: Optional[int] = None) -> Dict[str, np.ndarray]:
    """Round-robin all-miss fluid of the trapped server.

    n0[k-1] = sessions whose next turn is k.  Every present session gets one turn per round; the server is busy, so the
    per-session turn rate is r = 1 / sum_k n_k tau_k.  Arrivals enter at k = 1.  Returns time series."""
    wl = model.wl
    tau = model.trapped_turn_cost()
    haz = np.where(wl.surv > 0, wl.pT / wl.surv, 1.0)
    n = n0.astype(float).copy()
    ts = np.arange(t0, t1 + 1e-9, dt)
    N, X, C, gapR, comp, Lbar = [], [], [], [], [], []
    for t in ts:
        work = float((n * tau).sum())
        r = 1.0 / work if work > 0 else 0.0
        served = r * n * dt                     # turns served per index in dt (fluid)
        served = np.minimum(served, n)
        done = served * haz
        adv = served - done
        n = n - served
        n[1:] += adv[:-1]
        n[0] += lam * dt
        N.append(n.sum())
        X.append(float((r * n * wl.L).sum()))
        C.append(work)
        gapR.append(float((n * (wl.L + wl.decode)).sum()) / model.cell.M)
        comp.append(float(done.sum()) / dt)
        Lbar.append(float((n * wl.L).sum() / max(n.sum(), 1e-9)))
    return dict(t=ts, N=np.array(N), X=np.array(X), C=np.array(C), gap_over_R=np.array(gapR), completions=np.array(comp),
                Lbar=np.array(Lbar), state=n)


def good_composition(model: CheModel, N1: float) -> np.ndarray:
    """Turn-index composition of N1 sessions in the good state: time at each turn index ~ P(T >= k)."""
    return N1 * model.wl.pi


def burst_trap_path(model: CheModel, rows: List[Dict], lam: float, burst_n: int, t_b: float = 1200.0,
                    t_end: float = 8700.0, dt: float = 1.0) -> Dict:
    """Backlog path of a trapped run: good-state composition at t_b plus burst_n fresh sessions, all-miss from t_b."""
    N1, _ = crossings(rows, lam)
    n0 = good_composition(model, N1)
    n0[0] += burst_n
    return trap_fluid(model, lam, n0, t_b, t_end, dt=dt)


def window_stats(path: Dict, t0: float, t1: float, X_ref: float) -> Dict:
    t = path["t"]
    m = (t >= t0) & (t < t1)
    mid = 0.5 * (t0 + t1)
    j = int(np.argmin(np.abs(t - mid)))
    Nw = path["N"][m]
    slope = float(np.polyfit(t[m], Nw, 1)[0]) if m.sum() > 2 else float("nan")
    return dict(backlog_mean=float(Nw.mean()), backlog_slope=slope, token_ratio=float(path["X"][m].mean() / X_ref),
                rate_sessions=float(path["completions"][m].mean()), gap_over_R_mid=float(path["gap_over_R"][j]),
                round_s_mid=float(path["C"][j]), backlog_min_after=float(path["N"].min()),
                t_min_after=float(path["t"][int(np.argmin(path["N"]))]))


# ------------------------------------------------------------------------------------------------------------- rescue

def rescue_prediction(model: CheModel, rows: List[Dict], lam: float, cap: int, t_on: float, burst_n: int = 200,
                      t_b: float = 1200.0, hold_s: float = 300.0, t_end: float = 8700.0, mc_rep: int = 300,
                      seed: int = 0) -> Dict:
    """Release time and post-release persistence of a pause cap engaged at t_on inside the trap.

    Phase 1 (t_b .. t_on): trapped fluid from the burst.  Phase 2 (one round C(t_on)): attrition to the cap while the
    server queue drains; sessions keep arriving.  Phase 3: the capped closed N_c system relaxes to its unique mean-field
    state (good branch at N_c) and the gate (paused + new) drains at mu(N_c) - lam.  Release after hold_s empty."""
    path = burst_trap_path(model, rows, lam, burst_n, t_b=t_b, t_end=t_on)
    N_on = float(path["N"][-1])
    C_on = float(path["C"][-1])
    g = model.good_branch(float(cap))
    mu_c = g["mu"]
    # during attrition the server still runs trapped at about the all-miss session rate of the current composition
    comp_rate = float(path["completions"][-1])
    N_after_att = N_on + (lam - comp_rate) * C_on
    gate_q = max(N_after_att - cap, 0.0)
    if mu_c <= lam:
        return dict(lam=lam, cap=cap, t_on=t_on, N_on=N_on, round_on=C_on, mu_cap=mu_c, drains=False,
                    t_release=float("inf"))
    t_empty = t_on + C_on + gate_q / (mu_c - lam)
    t_rel = t_empty + hold_s
    out = dict(lam=lam, cap=cap, t_on=t_on, N_on=N_on, round_on=C_on, mu_cap=mu_c, h_cap=g["h"], drains=True,
               gate_queue_after_attrition=gate_q, t_gate_empty=t_empty, t_release=t_rel)
    # post-release persistence: escape probability of the good state over the remaining horizon
    rem = max(t_end - t_rel, 0.0)
    if rem > 0:
        mc = escape_mc(model, rows, lam, horizon=rem + 300.0, n_rep=mc_rep, seed=seed, t_start_check=300.0)
        out["p_relapse_after_release"] = mc.p_escape
    else:
        out["p_relapse_after_release"] = float("nan")
    return out


# --------------------------------------------------------------------------------------------- deterministic estimates

def critical_burst_det(model: CheModel, rows: List[Dict], lam: float) -> Dict:
    """Deterministic critical burst: (V2 - V1) / c_peak, c_peak = max_k P(T >= k) c_k (a fresh cohort's peak KV per session)."""
    N1, N2 = crossings(rows, lam)
    S_good = good_state_S(model, rows, lam)
    m1, _ = model.wl.lb_moments(S_good)
    wl = model.wl
    c_peak = float((wl.surv * wl.c).max())
    return dict(lam=lam, N1=N1, N2=N2, E_lb=m1, V1=N1 * m1, V2=N2 * m1, c_peak=c_peak,
                b_crit=(N2 - N1) * m1 / c_peak if math.isfinite(N2) else float("inf"))


def closed_trap_transient(model: CheModel, n: int, t0: float = 900.0, t1: float = 2700.0, dt: float = 1.0) -> Dict:
    """Stage C protocol in the trapped regime: n fresh sessions at t = 0 (synchronized start), every finished session is
    replaced at once by a fresh one, all turns miss.  Returns the session and turn throughput measured over [t0, t1)."""
    wl = model.wl
    tau = model.trapped_turn_cost()
    haz = np.where(wl.surv > 0, wl.pT / wl.surv, 1.0)
    x = np.zeros_like(wl.L)
    x[0] = float(n)
    done_w = turns_w = tok_w = 0.0
    t = 0.0
    while t < t1:
        work = float((x * tau).sum())
        r = 1.0 / work
        served = np.minimum(r * x * dt, x)
        done = served * haz
        adv = served - done
        x = x - served
        x[1:] += adv[:-1]
        x[0] += done.sum()                     # replacement at turn 1
        if t >= t0:
            done_w += done.sum()
            turns_w += served.sum()
            tok_w += float((served * wl.L).sum())
        t += dt
    T = t1 - t0
    return dict(n=n, mu_sessions=done_w / T, turns_per_s=turns_w / T, mu_turns_based=turns_w / T / wl.ET, tokens_per_s=tok_w / T)


def capped_drain_from_t0(model: CheModel, rows: List[Dict], lam: float, cap: int, burst_n: int = 200) -> Dict:
    """E2 CAPPED arm: static FIFO cap from t = 0, burst of burst_n at 1200 s; the gate queue (burst + N1 - cap) drains at
    mu(cap) - lam (the admitted cap sessions stay in their good state).  Returns the time after the burst at which the gate
    first empties."""
    N1, _ = crossings(rows, lam)
    g = model.good_branch(float(cap))
    q = burst_n + N1 - cap
    return dict(lam=lam, cap=cap, mu_cap=g["mu"], gate_queue=q, drain_s=q / (g["mu"] - lam) if g["mu"] > lam else float("inf"))
