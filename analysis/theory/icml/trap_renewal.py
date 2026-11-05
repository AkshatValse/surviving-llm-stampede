r"""The trapped engine as an overloaded re-entrant FIFO queue, and its renewal structure.

Statement and proofs: notes/THEORY_ICML_2026-11.md (Theorem 1, Theorem 2, Corollaries 3-5).

Model (the trap: every turn misses, the GPU is never idle, requests are served in the order they join).
  * T, the turns of a session: G_k = P(T >= k), k = 1..K, p_k = P(T = k).
  * c_k, the all-miss GPU seconds of turn k: the calibrated miss prefill of P_k tokens plus the all-miss per-turn decode
    share, so that sum_k G_k c_k = 1 / mu_b exactly (mu_b = the model's lambda_miss, Proposition 2(a) of the paper).
  * lambda_miss = 1 / sum_k c_k G_k,   rho = lambda / lambda_miss.
  * Perron root z of  lambda * sum_k c_k G_k z^{-k} = 1   (z > 1 iff rho > 1).
Theorem 1 (fluid, zero think time): along every FIFO orbit u_{n+1} = u_n + V(u_n) the cycle Delta_n = V(u_n) solves the
renewal recursion Delta_n = sum_k lambda c_k G_k Delta_{n-k} + h_n, hence for rho > 1
    V(t)/t -> gamma = z - 1,   N(t)/t -> alpha = lambda (1 - E z^{-T}),   departures/t -> lambda E z^{-T},
and the sessions present have the z-tilted turn mix G_k z^{-k} / sum_j G_j z^{-j}.
Theorem 2: lambda E z^{-T} / lambda_miss = H_T(z) * C_c(z) with H_T = E[T] E z^{-T} / sum_k G_k z^{-k} (= 1 for a geometric T)
and C_c = (sum c G / sum G) / (sum c G z^{-k} / sum G z^{-k}) (>= 1 for non-decreasing costs).

Also here: the PS variant (the paper's round-robin layer RR, continuous progress), an exact atomic-FIFO fluid solver from the
registered burst initial condition, and a stochastic FIFO simulator for the registered backlog-slope test.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy.optimize import brentq

from ..fluid_rigorous.model import Model


# ------------------------------------------------------------------------------------------------ per-turn costs


@dataclass(frozen=True)
class TrapCosts:
    k: np.ndarray        # 1..K
    c: np.ndarray        # all-miss GPU seconds of turn k
    P: np.ndarray        # prompt tokens of turn k
    G: np.ndarray        # P(T >= k)
    p: np.ndarray        # P(T = k)
    d: float             # decoded tokens per turn
    mu_b: float          # the model's lambda_miss (all-miss memory-saturated state)
    delta: float         # per-turn residual (decode) GPU seconds at the all-miss state
    nu_b: float

    @property
    def ET(self) -> float:
        return float(self.G.sum())

    @property
    def lam_miss(self) -> float:
        return 1.0 / float((self.c * self.G).sum())


def trap_costs(m: Model) -> TrapCosts:
    """c_k = miss prefill time of turn k + delta, with delta the per-turn residual GPU time of the all-miss state, so that
    sum_k (G_k / E[T]) c_k = 1 / nu_b (one GPU second per second at nu_b turns/s).  In separate mode delta = (1 - p_b) / nu_b,
    the round-robin layer's decode share (analysis/theory/fluid_rigorous/trapped.py)."""
    b = m.bad()
    G = m.G.astype(float)
    ET = float(G.sum())
    tPm = m.tPm.astype(float)
    delta = 1.0 / b["nu"] - float((G / ET * tPm).sum())
    c = tPm + delta
    Gn = np.append(G[1:], 0.0)
    return TrapCosts(k=np.arange(1, len(G) + 1, dtype=float), c=c, P=m.P.astype(float), G=G, p=G - Gn, d=float(m.wl.d),
                     mu_b=float(b["mu"]), delta=float(delta), nu_b=float(b["nu"]))


def token_server_costs(tc: TrapCosts, tokens_per_s: float) -> TrapCosts:
    """Variant: every turn costs its prompt tokens at a constant token rate (decode ignored), lambda_miss = C / E[sum P]."""
    c = tc.P / float(tokens_per_s)
    lam = 1.0 / float((c * tc.G).sum())
    return TrapCosts(k=tc.k, c=c, P=tc.P, G=tc.G, p=tc.p, d=tc.d, mu_b=lam, delta=0.0, nu_b=lam * tc.ET)


# ------------------------------------------------------------------------------------------------ Theorem 1, Theorem 2


def perron_root(lam: float, tc: TrapCosts) -> float:
    """The unique z > 0 with lam * sum_k c_k G_k z^{-k} = 1."""
    a = lam * tc.c * tc.G
    k = tc.k
    la = np.log(a)

    def f(logz: float) -> float:          # log phi(e^logz), computed stably (log-sum-exp)
        e = la - k * logz
        mx = float(np.max(e))
        return mx + float(np.log(np.sum(np.exp(e - mx))))

    lo, hi = -1.0, 1.0
    while f(lo) < 0:
        lo *= 2.0
    while f(hi) > 0:
        hi *= 2.0
    return float(math.exp(brentq(f, lo, hi, xtol=1e-15, rtol=1e-14, maxiter=500)))


def ps_root(lam: float, tc: TrapCosts) -> float:
    """Continuous-progress (processor-sharing) variant, the paper's RR layer: gamma with
    lam * sum_k c_k G_k int_{k-1}^k e^{-gamma a} da = 1.  Returns gamma (0 at rho = 1, negative below)."""
    a = lam * tc.c * tc.G
    k = tc.k

    la = np.log(a)

    def f(g: float) -> float:             # log of the left side, computed stably
        e = la - g * (k - 1.0)
        mx = float(np.max(e))
        fac = 1.0 if abs(g) < 1e-12 else (-math.expm1(-g)) / g
        return mx + float(np.log(np.sum(np.exp(e - mx)))) + math.log(fac)

    lo, hi = -0.5, 0.5
    while f(lo) < 0:
        lo *= 2.0
    while f(hi) > 0:
        hi *= 2.0
    return float(brentq(f, lo, hi, xtol=1e-15, rtol=1e-14, maxiter=500))


def trap_asymptotics(lam: float, tc: TrapCosts) -> Dict[str, float]:
    """Theorem 1 (b)-(d), Theorem 2 and Corollary 4 quantities at arrival rate lam (sessions/s)."""
    lam_miss = tc.lam_miss
    rho = lam / lam_miss
    z = perron_root(lam, tc)
    zk = z ** (-tc.k)
    S = float((tc.G * zk).sum())
    Ez = float((tc.p * zk).sum())                          # E z^{-T}
    alpha = lam * (1.0 - Ez)
    D = lam * Ez
    comp = tc.G * zk / S                                    # turn mix of the sessions present (and of turns served)
    ET = tc.ET
    stat = tc.G / ET                                        # stationary turn mix
    cG = float((tc.c * tc.G).sum())
    cGz = float((tc.c * tc.G * zk).sum())
    H = ET * Ez / S
    Cc = (cG / ET) / (cGz / S)
    kbar_c = float((tc.k * tc.c * tc.G).sum()) / cG         # cost-weighted mean turn index
    tok_trap = float((tc.P * tc.G * zk).sum()) / cGz       # prompt tokens per GPU second in the trap
    tok_stat = float((tc.P * tc.G).sum()) / cG             # ... at the stationary mix (the closed all-miss rate)
    turns_rate = float((tc.G * zk).sum()) / cGz            # turns per second in the trap
    g_ps = ps_root(lam, tc)
    Eps = float((tc.p * np.exp(-g_ps * tc.k)).sum()) if rho > 1 else float("nan")
    return dict(
        lam=lam, lam_miss=lam_miss, rho=rho, z=z, gamma=z - 1.0, alpha=alpha, D=D,
        alpha_over_excess=alpha / (lam - lam_miss) if rho != 1 else float("nan"),
        D_over_lam_miss=D / lam_miss, premium=D / lam_miss - 1.0, H_T=H, C_c=Cc, premium_check=H * Cc - 1.0,
        k_served_mean=float((tc.k * comp).sum()), k_stat_mean=float((tc.k * stat).sum()),
        P_served_mean=float((tc.P * comp).sum()), P_stat_mean=float((tc.P * stat).sum()),
        P_served_ratio=float((tc.P * comp).sum()) / float((tc.P * stat).sum()),
        tok_rate_trap=tok_trap, tok_rate_stat=tok_stat, tok_ratio=tok_trap / tok_stat,
        turns_per_s=turns_rate, pending_per_session=(z - 1.0) / alpha if alpha > 0 else float("nan"),
        kbar_c=kbar_c, near_threshold_coef=ET / kbar_c,
        gamma_ps=g_ps, alpha_ps=lam * (1.0 - Eps) if rho > 1 else float("nan"),
        D_ps=lam * Eps if rho > 1 else float("nan"),
    )


def busy_period(V_tot: float, lam_cut: float, tc: TrapCosts) -> float:
    """Theorem 1(a): with arrivals at lam_cut < lambda_miss from a backlog of total remaining all-miss work V_tot (GPU s),
    the all-miss server empties after V_tot / (1 - lam_cut / lambda_miss)."""
    r = lam_cut / tc.lam_miss
    return V_tot / (1.0 - r) if r < 1 else math.inf


def remaining_work(k_now: int, tc: TrapCosts) -> float:
    """E[ sum_{j=k_now}^T c_j | T >= k_now ]: all-miss work left to a session whose next turn is k_now."""
    i = k_now - 1
    return float((tc.c[i:] * tc.G[i:]).sum() / tc.G[i])


# ------------------------------------------------------------------------------------------------ orbit recursion


def orbit_recursion(lam: float, tc: TrapCosts, h: Sequence[float], n_steps: int) -> np.ndarray:
    """Delta_n = sum_{k=1}^{min(n,K)} lam c_k G_k Delta_{n-k} + h_n, Delta_0 = h_0 (Theorem 1's recursion)."""
    K = len(tc.k)
    a = lam * tc.c * tc.G
    D = np.zeros(n_steps)
    hh = np.zeros(n_steps)
    hh[: min(len(h), n_steps)] = np.asarray(h, float)[:n_steps]
    for n in range(n_steps):
        s = hh[n]
        for k in range(1, min(n, K) + 1):
            s += a[k - 1] * D[n - k]
        D[n] = s
    return D


# ------------------------------------------------------------------------------------------------ atomic FIFO fluid


def fifo_fluid(lam: float, tc: TrapCosts, n_bg: float, t_b: float = 1200.0, burst_n: float = 200.0, burst_w: float = 60.0,
               t_end: float = 8700.0, dt_arr: float = 1.0, think: float = 0.0, grid: float = 10.0,
               lam_after: Optional[Sequence[tuple]] = None, orbit_from: Optional[float] = None) -> Dict[str, np.ndarray]:
    """Exact (up to the packet discretisation dt_arr) fluid of the trap: a FIFO queue of request packets (mass, class);
    the server does GPU work at unit rate; a completed class-k packet loses the fraction p_k / G_k (departures) and
    re-joins the tail as class k+1 after `think` seconds.  Starts at t_b with n_bg present sessions in the stationary mix
    (all pending), then arrivals at lam (plus the burst).  `lam_after` = [(t, lam'), ...] changes the arrival rate.
    Records on a `grid`-second grid: N (sessions present), V (pending work = FIFO wait of a request joining now),
    cumulative departures, turns and prompt tokens served, and the class mix of turns served."""
    K = len(tc.k)
    cont = np.append(tc.G[1:] / tc.G[:-1], 0.0)          # P(T >= k+1 | T >= k)
    q = deque()
    stat = tc.G / tc.ET
    for i in np.argsort(-tc.k):                          # oldest classes first (an arbitrary FIFO order)
        if n_bg * stat[i] > 0:
            q.append([n_bg * stat[i], int(i)])
    rates = [(t_b, lam)] + list(lam_after or [])
    rates.sort()

    def lam_at(t: float) -> float:
        r = rates[0][1]
        for tt, rr in rates:
            if t >= tt:
                r = rr
        return r

    t = t_b
    next_arr = t_b
    thinking: List[tuple] = []                            # (rejoin time, mass, class) kept sorted by time
    times = np.arange(t_b, t_end + 1e-9, grid)
    out = {key: np.zeros_like(times) for key in ("N", "V", "dep", "turns", "tok", "Vtot")}
    Rk = np.array([float((tc.c[i:] * tc.G[i:]).sum() / tc.G[i]) for i in range(K)])   # remaining all-miss work by class
    served_k = np.zeros((len(times), K))
    cum_dep = cum_turns = cum_tok = 0.0
    cum_k = np.zeros(K)
    gi = 0
    head_left = None                                       # remaining work of the head packet

    def N_now() -> float:
        return sum(m for m, _ in q) + sum(m for _, m, _ in thinking)

    def V_now() -> float:
        v = sum(m * tc.c[i] for m, i in q)
        if head_left is not None and q:
            v = v - q[0][0] * tc.c[q[0][1]] + head_left
        return v

    t_probe = orbit_from if orbit_from is not None else math.inf    # optional FIFO-orbit probe (Theorem 1's recursion)
    orbit: List[tuple] = []
    while gi < len(times):
        # next event: arrival packet, rejoin, head completion, orbit probe, or grid point
        t_head = t + head_left if (q and head_left is not None) else math.inf
        if q and head_left is None:
            head_left = q[0][0] * tc.c[q[0][1]]
            t_head = t + head_left
        t_rej = thinking[0][0] if thinking else math.inf
        t_grid = times[gi]
        t_next = min(next_arr, t_head, t_rej, t_grid, t_probe)
        if q and head_left is not None:
            head_left -= (t_next - t)
        t = t_next
        if t == t_probe:
            v = V_now()
            orbit.append((t, v))
            t_probe = t + v if v > 0 else math.inf
            continue
        if t == t_grid:
            out["N"][gi] = N_now()
            out["V"][gi] = V_now()
            vt = sum(m * Rk[i] for m, i in q) + sum(m * Rk[i] for _, m, i in thinking)
            if head_left is not None and q:
                vt -= q[0][0] * tc.c[q[0][1]] - head_left
            out["Vtot"][gi] = vt
            out["dep"][gi], out["turns"][gi], out["tok"][gi] = cum_dep, cum_turns, cum_tok
            served_k[gi] = cum_k
            gi += 1
            continue
        if t == next_arr:
            add = lam_at(t) * dt_arr
            if t_b <= t < t_b + burst_w:
                add += burst_n / burst_w * dt_arr
            q.append([add, 0])
            next_arr = t + dt_arr
            continue
        if t == t_rej:
            _, m, i = thinking.pop(0)
            q.append([m, i])
            continue
        # head completion
        m, i = q.popleft()
        head_left = None
        cum_turns += m
        cum_tok += m * tc.P[i]
        cum_k[i] += m
        cum_dep += m * (1.0 - cont[i])
        mc = m * cont[i]
        if mc > 1e-15 and i + 1 < K:
            if think > 0:
                thinking.append((t + think, mc, i + 1))
                thinking.sort(key=lambda x: x[0])
            else:
                q.append([mc, i + 1])
    out["t"] = times
    out["served_k"] = served_k
    out["orbit"] = np.array(orbit) if orbit else np.zeros((0, 2))
    return out


def window_stats(tr: Dict[str, np.ndarray], t0: float, t1: float, tc: TrapCosts) -> Dict[str, float]:
    t = tr["t"]
    sel = (t >= t0) & (t <= t1)
    x, y = t[sel], tr["N"][sel]
    i0, i1 = np.where(sel)[0][[0, -1]]
    span = t[i1] - t[i0]
    dk = tr["served_k"][i1] - tr["served_k"][i0]
    turns = tr["turns"][i1] - tr["turns"][i0]
    return dict(
        slope=float(np.polyfit(x, y, 1)[0]),
        N_mean=float(np.mean(y)),
        completion_rate=float((tr["dep"][i1] - tr["dep"][i0]) / span),
        turns_per_s=float(turns / span),
        tok_per_s=float((tr["tok"][i1] - tr["tok"][i0]) / span),
        P_served_mean=float((tc.P * dk).sum() / max(dk.sum(), 1e-12)),
        k_served_mean=float((tc.k * dk).sum() / max(dk.sum(), 1e-12)),
        V_mean=float(np.mean(tr["V"][sel])),
        V_slope=float(np.polyfit(x, tr["V"][sel], 1)[0]),
    )


# ------------------------------------------------------------------------------------------------ stochastic FIFO


def stochastic_fifo(lam: float, tc: TrapCosts, n_bg_mean: float, rng: np.random.Generator, t_b: float = 1200.0,
                    burst_n: int = 200, burst_w: float = 60.0, t_end: float = 8700.0, think_mean: float = 5.0,
                    bin_s: float = 10.0, t_eval: float = 5700.0) -> Dict[str, float]:
    """Discrete sessions: Poisson(lam) arrivals from t_b, the burst uniform in [t_b, t_b + burst_w), n_bg ~ Poisson(n_bg_mean)
    present at t_b in the stationary mix; one FIFO server doing c_k seconds per turn (all miss); exponential think times.
    Returns the registered backlog statistic: OLS slope of 10 s bin means of the sessions in the system over [t_eval, t_end]."""
    K = len(tc.k)
    cont = np.append(tc.G[1:] / tc.G[:-1], 0.0)
    # sessions: (arrival time, T); background sessions: next turn k drawn from the stationary mix, T from P(T | T >= k)
    arr = []
    n_a = rng.poisson(lam * (t_end - t_b))
    arr += list(t_b + rng.uniform(0, t_end - t_b, n_a))
    arr += list(t_b + rng.uniform(0, burst_w, burst_n))
    arr.sort()
    events = []                                           # (time the request joins the FIFO queue, session id, turn index)
    sess_T = []
    sess_start = []
    for a in arr:
        T = 1
        while T < K and rng.random() < cont[T - 1]:
            T += 1
        sess_T.append(T)
        sess_start.append(a)
        events.append((a, len(sess_T) - 1, 1))
    nb = rng.poisson(n_bg_mean)
    stat = tc.G / tc.ET
    for _ in range(nb):
        k = int(rng.choice(K, p=stat)) + 1
        T = k
        while T < K and rng.random() < cont[T - 1]:
            T += 1
        sess_T.append(T)
        sess_start.append(t_b - 1.0)
        events.append((t_b, len(sess_T) - 1, k))
    import heapq
    heapq.heapify(events)
    t_free = t_b
    end_time = [math.inf] * len(sess_T)
    while events:
        tj, s, k = heapq.heappop(events)                 # FIFO: requests are served in join order
        if tj > t_end:
            break
        start = max(t_free, tj)
        done = start + tc.c[k - 1]
        t_free = done
        if k >= sess_T[s]:
            end_time[s] = done
        else:
            heapq.heappush(events, (done + rng.exponential(think_mean) if think_mean > 0 else done, s, k + 1))
    starts = np.array(sess_start)
    ends = np.array(end_time)
    bins = np.arange(t_eval, t_end, bin_s)
    # bin means of the number in system, sampled at 1 s within each bin
    tt = np.arange(t_eval, t_end, 1.0)
    st = np.sort(starts)
    en = np.sort(ends)
    n_sys = np.searchsorted(st, tt, side="right") - np.searchsorted(en, tt, side="right")
    nb_ = len(bins)
    means = n_sys[: nb_ * int(bin_s)].reshape(nb_, int(bin_s)).mean(axis=1)
    slope = float(np.polyfit(bins + bin_s / 2.0, means, 1)[0])
    done_win = int(((ends >= t_eval) & (ends < t_end)).sum())
    return dict(slope=slope, completion_rate=done_win / (t_end - t_eval), N_end=float(n_sys[-1]))
