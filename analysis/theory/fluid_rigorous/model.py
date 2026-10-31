r"""Mean-field (fluid) model of prefix-cached multi-turn agent serving.

Notation follows notes/THEORY_r13_fluid_rigorous.md (section numbers in brackets).

[S1] Workload.  A session has T turns, P(T >= k) = G_k = q^(k-1) for k <= K (q = 1 - 1/15, K = 60), G_{K+1} = 0,
     E[T] = sum_k G_k.  Turn k sends a prompt of P_k = L0 + (k-1)(Delta + d) tokens and decodes d tokens; after it the
     session's KV is E_k = P_k + d tokens.  A hit at turn k >= 2 prefills x_h = Delta + 1 tokens (the measured SGLang
     value, "cached = prompt - 551"); a miss prefills P_k; the first turn always misses.  Tool times Z are i.i.d.
     (Exp(zbar) in the workload of record; a finite mixture of exponentials is supported).

[S2] Service.  The calibrated iteration-cost model of calibration/round6_server_log_fit/calibration.yaml (fitted to
     SGLang server-log timing only, never to mu(n)):
        prefill iteration  tau_P = a + max(f, b X) + c_p * sum_i x_i (c_i + (x_i + 1)/2)
        decode iteration   tau_D = a + max(f, b R) + c_d * C / 8192
     ``separate`` mode (SGLang: prefill iterations have priority and stall decode) or ``mixed`` mode (vLLM-like
     chunked prefill: decode tokens ride along each iteration).  The stationary fluid server is in ``server``.

[S3] Memory.  Pool of M tokens.  A running request reserves E_k for its whole service (full reservation).  Idle KV
     (sessions in a tool call or waiting in the queue, and the dead KV of finished sessions, which the engine cannot
     know is dead) is evicted least-recently-used first, only when space is needed.  In a stationary regime the LRU
     eviction frontier moves at unit speed, so an idle item is evicted exactly when its idle age reaches R:
        M = K_run + mu * D(R; W),     D(R; W) = sum_k G_{k+1} E_k E[min(Z + W, R)] + E[E_T] R.
     A follow-up hits iff Z + W < R:  h = F_Z(R - W)  (0 if R <= W).

[S4] Closed system with n sessions (a finished session is replaced at once).  Little's law:
        n = mu * (E[T] (W + S_bar) + (E[T] - 1) zbar),     mu = nu / E[T].
     FCFS admission is work-conserving and memory-gated: a queue (W > 0) exists only when the running reservations
     fill the pool, K_run = M, which leaves no room for idle KV (R = 0, h = 0): the all-miss branch.

Everything is deterministic (fluid limit).  All rates are per second; KV in tokens.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import brentq

# ------------------------------------------------------------------------------------------------ [S1] workload


@dataclass(frozen=True)
class Workload:
    L0: int = 2000                 # first prompt (tokens)
    delta: int = 550               # tool output appended per turn
    d: int = 100                   # decoded tokens per turn
    mean_turns: float = 15.0       # Geometric(1/mean_turns) ...
    K: int = 60                    # ... truncated at K turns
    zbar: float = 5.0              # mean tool time (s)
    tool_mix: Tuple[Tuple[float, float], ...] = ()   # optional mixture of exponentials ((prob, mean), ...); () = Exp(zbar)
    x_hit: int = 551               # prefill tokens of a hit (Delta + 1 on SGLang)

    # --- arrays -------------------------------------------------------------------------------------------------
    @property
    def k(self) -> np.ndarray:
        return np.arange(1, self.K + 1)

    @property
    def P(self) -> np.ndarray:
        return (self.L0 + (self.k - 1) * (self.delta + self.d)).astype(float)

    @property
    def E(self) -> np.ndarray:
        return self.P + self.d

    @property
    def G(self) -> np.ndarray:
        q = 1.0 - 1.0 / self.mean_turns
        return q ** (self.k - 1.0)

    @property
    def Gnext(self) -> np.ndarray:
        g = self.G
        return np.append(g[1:], 0.0)

    @property
    def ET(self) -> float:
        return float(self.G.sum())

    @property
    def w(self) -> np.ndarray:
        """Turn mix: share of turn k among all turns (stationary closed system or long-run open system)."""
        return self.G / self.ET

    # --- tool-time law ------------------------------------------------------------------------------------------
    def _mix(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.tool_mix:
            p = np.array([m[0] for m in self.tool_mix], float)
            z = np.array([m[1] for m in self.tool_mix], float)
            p = p / p.sum()
            return p, z
        return np.array([1.0]), np.array([float(self.zbar)])

    @property
    def zmean(self) -> float:
        p, z = self._mix()
        return float((p * z).sum())

    def F(self, r: float) -> float:
        """P(Z <= r)."""
        if r <= 0:
            return 0.0
        p, z = self._mix()
        return float((p * (1.0 - np.exp(-r / z))).sum())

    def Emin(self, r: float) -> float:
        """E[min(Z, r)] = int_0^r P(Z > u) du."""
        if r <= 0:
            return 0.0
        p, z = self._mix()
        return float((p * z * (1.0 - np.exp(-r / z))).sum())

    def dens0(self) -> float:
        """Density of Z at 0+."""
        p, z = self._mix()
        return float((p / z).sum())

    def Finv(self, h: float) -> float:
        if h <= 0:
            return 0.0
        if h >= 1:
            return math.inf
        if not self.tool_mix:
            return -self.zbar * math.log1p(-h)
        hi = 1.0
        while self.F(hi) < h:
            hi *= 2.0
        return brentq(lambda r: self.F(r) - h, 0.0, hi, xtol=1e-12)

    # --- per-session KV integrals -------------------------------------------------------------------------------
    @property
    def A1(self) -> float:
        """sum_k G_{k+1} E_k: KV held through the tool calls of one session (tokens), the coefficient of E[min(Z,R)]."""
        return float((self.Gnext * self.E).sum())

    @property
    def EET(self) -> float:
        """E[E_T]: the final (dead) KV of a session."""
        return float(((self.G - self.Gnext) * self.E).sum())

    @property
    def tokens_all_miss(self) -> float:
        """E[sum_k P_k]: uncached prefill tokens per session if every turn misses (154,529 for the record workload)."""
        return float((self.G * self.P).sum())

    def kv_time_all_hit(self, S_bar: float) -> float:
        """E[int c(t) dt] over a session's life when every follow-up hits and each turn is in service S_bar (no queue)."""
        return float((self.G * self.E).sum() * S_bar + self.A1 * self.zmean)

    def E_lb(self, S_bar: float) -> float:
        """Length-biased (time-averaged) KV footprint of a live session, all follow-ups hitting (H = lambda G)."""
        life = self.ET * S_bar + (self.ET - 1.0) * self.zmean
        return self.kv_time_all_hit(S_bar) / life


# ------------------------------------------------------------------------------------------------ [S2] service


@dataclass(frozen=True)
class Costs:
    a: float = 9.24e-3        # iter_fixed_s
    f: float = 1.26e-3        # iter_floor_s
    b: float = 6.26e-5        # per_token_s
    cd: float = 3.10e-4       # decode_attn_s per `norm` context tokens per decode step
    cp: float = 2.24e-9       # prefill_attn_s per causal pair ('mid' convention)
    norm: float = 8192.0      # attn_ctx_norm
    chunk: float = 8192.0     # prefill_chunk_budget
    mode: str = "separate"    # 'separate' (SGLang) | 'mixed' (vLLM-like)
    max_running: float = 256.0

    def scaled(self, s: float) -> "Costs":
        """Every GPU time divided by s (a uniformly s-times faster GPU)."""
        return replace(self, a=self.a / s, f=self.f / s, b=self.b / s, cd=self.cd / s, cp=self.cp / s)


def t_prefill(x: np.ndarray, c: np.ndarray, cost: Costs) -> np.ndarray:
    """GPU time attributable to prefilling x new tokens on top of a cached prefix of c tokens (separate mode).
    The fixed iteration cost is amortised per full chunk (prefill iterations of misses are full under load)."""
    x = np.asarray(x, float)
    c = np.asarray(c, float)
    return cost.a * np.maximum(1.0, x / cost.chunk) + np.maximum(cost.f, cost.b * x) + cost.cp * (x * c + x * (x + 1.0) / 2.0)


@dataclass
class Server:
    nu: float            # turn admission (= completion) rate, turns/s
    h: float             # follow-up hit probability
    feasible: bool
    p: float             # fraction of GPU time in prefill (separate) / prefill share (mixed)
    R_D: float           # mean number of decoding sequences
    S_D: float           # decode duration (first token -> last token), s
    S_bar: float         # mean service time per turn (admission -> completion), s
    K_run: float         # KV reserved by running requests, tokens
    tok_rate: float      # uncached prefill tokens / s
    S_hit: float         # mean service time of a hit turn
    S_miss: float        # mean service time of a miss turn (turn-mix weighted, incl. first turns)


class Model:
    """The stationary fluid model for one cell (workload, costs, pool M)."""

    def __init__(self, wl: Workload, cost: Costs, M: float):
        self.wl, self.cost, self.M = wl, cost, float(M)
        self.P, self.E, self.G, self.w = wl.P, wl.E, wl.G, wl.w
        self.ET = wl.ET
        k = wl.k
        self.tPm = t_prefill(self.P, np.zeros_like(self.P), cost)                                   # miss prefill
        xh = np.full_like(self.P, float(wl.x_hit))
        self.tPh = t_prefill(xh, np.maximum(self.P - wl.x_hit, 0.0), cost)                          # hit prefill
        self.tPh[k == 1] = self.tPm[k == 1]                                                           # turn 1 always misses
        self.is_follow = (k >= 2).astype(float)
        self.cD = float((self.w * (self.P + wl.d / 2.0)).sum())                                     # mean decode context
        self.betac = cost.cd * self.cD / cost.norm
        # mixed-mode per-turn token / pair counts
        self.xm = self.P.copy()
        self.xh = np.where(k >= 2, float(wl.x_hit), self.P)
        self.pim = self.P * (self.P + 1.0) / 2.0
        c = np.maximum(self.P - wl.x_hit, 0.0)
        self.pih = np.where(k >= 2, wl.x_hit * c + wl.x_hit * (wl.x_hit + 1.0) / 2.0, self.pim)
        self._cap_cache: Dict[float, float] = {}

    # ---------------------------------------------------------------------------------------- the fluid server
    def hk(self, h: float) -> np.ndarray:
        return h * self.is_follow

    def server(self, nu: float, h: float) -> Server:
        if self.cost.mode == "mixed":
            return self._server_mixed(nu, h)
        return self._server_separate(nu, h)

    def _server_separate(self, nu: float, h: float) -> Server:
        cost, wl = self.cost, self.wl
        hk = self.hk(h)
        tP = hk * self.tPh + (1.0 - hk) * self.tPm          # mean prefill GPU time of turn k
        tbar = float((self.w * tP).sum())
        p = nu * tbar
        g = nu * (wl.d - 1.0)
        inf = Server(nu, h, False, p, math.inf, math.inf, math.inf, math.inf, math.nan, math.inf, math.inf)
        if p >= 1.0:
            return inf
        # decode: R (1 - p) = g (a + max(f, b R) + betac R); smallest positive root of a concave piecewise-linear phi
        Rk = cost.f / cost.b
        s1 = (1.0 - p) - g * self.betac
        s2 = (1.0 - p) - g * (cost.b + self.betac)
        R = math.nan
        if s1 > 0:
            R1 = g * (cost.a + cost.f) / s1
            if R1 <= Rk:
                R = R1
        if math.isnan(R) and s2 > 0:
            R2 = g * cost.a / s2
            if R2 >= Rk:
                R = R2
        if math.isnan(R):
            return inf
        if nu > 0:
            SD = R / nu
        else:
            SD = (wl.d - 1.0) * (cost.a + cost.f)
        S_k = tP + SD
        S_bar = float((self.w * S_k).sum())
        K_run = nu * float((self.w * self.E * S_k).sum())
        tok = nu * float((self.w * (hk * wl.x_hit * self.is_follow + (1.0 - hk * self.is_follow) * self.P)).sum())
        wf = self.w * self.is_follow
        S_hit = float((wf * (self.tPh + SD)).sum() / wf.sum())
        S_miss = float((self.w * (self.tPm + SD)).sum())
        return Server(nu, h, True, p, R, SD, S_bar, K_run, tok, S_hit, S_miss)

    def _server_mixed(self, nu: float, h: float) -> Server:
        cost, wl = self.cost, self.wl
        hk = self.hk(h)
        xbar = float((self.w * (hk * self.xh + (1.0 - hk) * self.xm)).sum())
        pibar = float((self.w * (hk * self.pih + (1.0 - hk) * self.pim)).sum())
        c_turn = cost.b * xbar + cost.cp * pibar + (cost.b + self.betac) * (wl.d - 1.0)
        inf = Server(nu, h, False, math.nan, math.inf, math.inf, math.inf, math.inf, math.nan, math.inf, math.inf)
        # GPU-time balance: I a + nu c_turn = 1 (I = iterations/s); budget: tokens per iteration <= chunk
        if nu * c_turn >= 1.0:
            return inf
        I = (1.0 - nu * c_turn) / cost.a
        if nu > 0 and nu * (xbar + wl.d - 1.0) / I > cost.chunk:
            return inf
        tau = 1.0 / I
        SD = (wl.d - 1.0) * tau
        R_D = nu * SD
        avail = max(cost.chunk - R_D, 1.0)
        SPm = tau * np.maximum(1.0, self.xm / avail)
        SPh = tau * np.maximum(1.0, self.xh / avail)
        SP = hk * SPh + (1.0 - hk) * SPm
        S_k = SP + SD
        S_bar = float((self.w * S_k).sum())
        K_run = nu * float((self.w * self.E * S_k).sum())
        tok = nu * float((self.w * (hk * self.xh + (1.0 - hk) * self.xm)).sum())
        wf = self.w * self.is_follow
        S_hit = float((wf * (SPh + SD)).sum() / wf.sum())
        S_miss = float((self.w * (SPm + SD)).sum())
        return Server(nu, h, True, nu * cost.b * xbar + nu * cost.cp * pibar, R_D, SD, S_bar, K_run, tok, S_hit, S_miss)

    def nu_cap(self, h: float) -> float:
        """Largest feasible turn rate of the server at hit probability h (decode / budget capacity)."""
        key = round(h, 12)
        if key in self._cap_cache:
            return self._cap_cache[key]
        lo, hi = 0.0, 1.0
        while self.server(hi, h).feasible:
            lo, hi = hi, hi * 2.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if self.server(mid, h).feasible:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-13 * hi:
                break
        self._cap_cache[key] = lo
        return lo

    # ---------------------------------------------------------------------------------------- [S3] LRU memory
    def D(self, R: float, W: float = 0.0) -> float:
        """Idle KV-time per session (tokens x s) with eviction age R and queue wait W: live idle + dead KV."""
        wl = self.wl
        if R <= W:
            live = wl.A1 * R
        else:
            live = wl.A1 * (W + wl.Emin(R - W))
        return live + wl.EET * R

    def hit_of_R(self, R: float, W: float = 0.0) -> float:
        return self.wl.F(R - W) if R > W else 0.0

    # ---------------------------------------------------------------------------------------- [S4] closed system
    def lifetime(self, srv: Server, W: float = 0.0) -> float:
        return self.ET * (W + srv.S_bar) + (self.ET - 1.0) * self.wl.zmean

    def nu_of_R(self, R: float) -> float:
        """The unique turn rate of the W = 0 stationary state with eviction age R: K_run(nu, h(R)) + mu D(R) = M."""
        h = self.hit_of_R(R)
        Dv = self.D(R)
        cap = self.nu_cap(h)

        def fun(nu: float) -> float:
            s = self.server(nu, h)
            if not s.feasible:
                return math.inf
            return s.K_run + nu / self.ET * Dv - self.M

        hi = cap * (1.0 - 1e-12)
        fhi = fun(hi)
        if not (fhi > 0):        # memory never binds below capacity (only possible if M is huge)
            return math.nan
        return brentq(fun, 0.0, hi, xtol=1e-14, rtol=1e-12, maxiter=500)

    def point(self, R: float) -> Dict[str, float]:
        """The W = 0 stationary state with eviction age R (R in (0, inf))."""
        nu = self.nu_of_R(R)
        h = self.hit_of_R(R)
        s = self.server(nu, h)
        mu = nu / self.ET
        n = mu * self.lifetime(s)
        hit_all_turns = h * (1.0 - 1.0 / self.ET)
        return dict(R=R, W=0.0, h=h, hit=hit_all_turns, nu=nu, mu=mu, n=n, S_bar=s.S_bar, S_D=s.S_D, R_D=s.R_D,
                    p=s.p, K_run=s.K_run, idle=mu * self.D(R), dead=mu * self.wl.EET * R, tok=s.tok_rate)

    def bad(self) -> Dict[str, float]:
        """The all-miss memory-saturated state: K_run(nu_b, 0) = M (R = 0, h = 0).  mu_b = nu_b / E[T] is the model's
        lambda_miss; n_b is the smallest population that can sustain it (W = 0)."""
        cap = self.nu_cap(0.0)

        def fun(nu: float) -> float:
            s = self.server(nu, 0.0)
            return (s.K_run if s.feasible else math.inf) - self.M

        hi = cap * (1.0 - 1e-12)
        compute_bound = not (fun(hi) > 0)
        if compute_bound:
            # the pool never fills before the server saturates (very large M, or a budget-bound mixed-mode server):
            # the all-miss state is compute-gated; report it at capacity (outside condition (C1) of the notes)
            nu_b = cap * (1.0 - 1e-9)
        else:
            nu_b = brentq(fun, 0.0, hi, xtol=1e-14, rtol=1e-12, maxiter=500)
        s = self.server(nu_b, 0.0)
        mu = nu_b / self.ET
        n_b = mu * self.lifetime(s)
        return dict(nu=nu_b, mu=mu, n_b=n_b, S_bar=s.S_bar, S_D=s.S_D, R_D=s.R_D, p=s.p, tok=s.tok_rate, K_run=s.K_run,
                    nu_cap0=cap, compute_bound=compute_bound)

    def all_miss_closed(self, n: float) -> Dict[str, float]:
        """Cache disabled (E0a protocol): every turn misses, no idle KV; closed population n."""
        s_cap = self.nu_cap(0.0)

        def little(nu: float) -> float:
            s = self.server(nu, 0.0)
            return (nu / self.ET * self.lifetime(s) if s.feasible else math.inf) - n

        nu0 = brentq(little, 0.0, s_cap * (1.0 - 1e-12), xtol=1e-14, maxiter=500)
        s0 = self.server(nu0, 0.0)
        b = self.bad()
        if s0.K_run <= self.M:
            nu, s, W = nu0, s0, 0.0
        else:
            nu = b["nu"]
            s = self.server(nu, 0.0)
            W = (n / (nu / self.ET) - self.lifetime(s)) / self.ET
        return dict(n=n, nu=nu, mu=nu / self.ET, tok=s.tok_rate, W=W, memory_bound=s0.K_run > self.M)

    def curve(self, R_grid: Optional[np.ndarray] = None) -> List[Dict[str, float]]:
        """The W = 0 solution curve, ordered from R = large (n ~ 0) to R = small (the all-miss end)."""
        if R_grid is None:
            z = self.wl.zmean
            R_grid = np.unique(np.concatenate([np.geomspace(z * 1e-4, z * 1e-2, 40), np.geomspace(z * 1e-2, z * 40, 900),
                                               np.geomspace(z * 40, z * 4000, 60)]))[::-1]
        out = []
        for R in R_grid:
            nu = self.nu_of_R(float(R))
            if not math.isfinite(nu):
                continue
            out.append(self.point(float(R)))
        return out


# ------------------------------------------------------------------------------------------------ curve analysis


@dataclass
class CurveSummary:
    mu_max: float
    n_star: float
    h_star: float
    R_star: float
    mu_b: float
    n_b: float
    folds: List[Dict[str, float]]          # turning points of n along the curve (dn/dR = 0)
    n_fold_hi: float                       # largest n on a stable good segment (upper fold); nan if no fold
    n_fold_lo: float                       # smallest n of the lower (all-miss side) stable branch
    bistable: bool
    n_half: float                          # n where the all-turn hit fraction crosses 0.5 (first crossing on the curve)
    n_half_stable_good: float              # same, restricted to the stable good segment (nan if it never gets there)
    window: float                          # mu_max / mu_b
    pts: List[Dict[str, float]] = field(default_factory=list)


def summarize_curve(m: Model, pts: Optional[List[Dict[str, float]]] = None) -> CurveSummary:
    if pts is None:
        pts = m.curve()
    b = m.bad()
    n = np.array([p["n"] for p in pts])
    mu = np.array([p["mu"] for p in pts])
    hit = np.array([p["hit"] for p in pts])
    R = np.array([p["R"] for p in pts])
    i = int(np.argmax(mu))
    # stability: along increasing index R decreases; stable iff dn/dR < 0  <=>  n increases with the index
    dn = np.diff(n)
    stable_seg = np.concatenate([[dn[0] > 0], dn > 0])     # point j stable if n rose into it
    folds = []
    for j in range(1, len(dn)):
        if (dn[j - 1] > 0) != (dn[j] > 0):
            kind = "upper" if dn[j - 1] > 0 else "lower"
            folds.append(dict(kind=kind, n=float(n[j]), mu=float(mu[j]), hit=float(hit[j]), R=float(R[j])))
    upper = [f for f in folds if f["kind"] == "upper"]
    lower = [f for f in folds if f["kind"] == "lower"]
    n_fold_hi = upper[0]["n"] if upper else math.nan
    n_fold_lo = min([f["n"] for f in lower] + [b["n_b"]]) if lower else b["n_b"]
    # first 0.5 crossing of the all-turn hit fraction along the curve (from the good end)
    def first_cross(mask: np.ndarray) -> float:
        idx = np.where(mask[:-1] & (hit[:-1] >= 0.5) & (hit[1:] < 0.5))[0]
        if len(idx) == 0:
            return math.nan
        j = idx[0]
        t = (hit[j] - 0.5) / (hit[j] - hit[j + 1])
        return float(n[j] + t * (n[j + 1] - n[j]))
    n_half = first_cross(np.ones_like(hit, bool))
    if upper:
        jf = int(np.where(np.isclose(n, upper[0]["n"]))[0][0])
        good_mask = np.zeros_like(hit, bool)
        good_mask[: jf + 1] = True
    else:
        good_mask = np.ones_like(hit, bool)
    n_half_good = first_cross(good_mask)
    return CurveSummary(mu_max=float(mu[i]), n_star=float(n[i]), h_star=float(hit[i]), R_star=float(R[i]), mu_b=b["mu"],
                        n_b=b["n_b"], folds=folds, n_fold_hi=n_fold_hi, n_fold_lo=n_fold_lo, bistable=bool(upper),
                        n_half=n_half, n_half_stable_good=n_half_good, window=float(mu[i] / b["mu"]), pts=pts)


def mu_good_of_n(cs: CurveSummary) -> Tuple[np.ndarray, np.ndarray]:
    """The stable good branch as a function n -> mu (from n ~ 0 up to the upper fold, or the whole curve)."""
    n = np.array([p["n"] for p in cs.pts])
    mu = np.array([p["mu"] for p in cs.pts])
    if cs.bistable:
        jf = int(np.where(np.isclose(n, cs.n_fold_hi))[0][0])
        return n[: jf + 1], mu[: jf + 1]
    keep = np.concatenate([[True], np.diff(n) > 0])
    return n[keep], mu[keep]


# ------------------------------------------------------------------------------------------------ the feedback map


def feedback_map(m: Model, n: float, h: float) -> Dict[str, float]:
    """Phi_n(h): the follow-up hit probability produced at population n when the current follow-up hit probability
    is h.  Given h, Little's law fixes the turn rate (W = 0) unless the running reservations alone exceed the pool,
    in which case admission is memory-gated (W > 0), no idle KV survives and Phi = 0."""
    cap = m.nu_cap(h)

    def little(nu: float) -> float:
        s = m.server(nu, h)
        return (nu / m.ET * m.lifetime(s) if s.feasible else math.inf) - n

    nu0 = brentq(little, 0.0, cap * (1.0 - 1e-12), xtol=1e-14, maxiter=500)
    s0 = m.server(nu0, h)
    if s0.K_run >= m.M:
        return dict(phi=0.0, R=0.0, nu=nu0, W_pos=True, K_run=s0.K_run)
    free = m.M - s0.K_run
    mu = nu0 / m.ET
    hi = 1.0
    while mu * m.D(hi) < free:
        hi *= 2.0
    R = brentq(lambda r: mu * m.D(r) - free, 0.0, hi, xtol=1e-12)
    return dict(phi=m.wl.F(R), R=R, nu=nu0, W_pos=False, K_run=s0.K_run)


def fixed_points(m: Model, n: float, ngrid: int = 801) -> List[Dict[str, float]]:
    """All fixed points h* = Phi_n(h*) on [0, h_max] with their slopes Phi_n'(h*) (stable iff slope < 1)."""
    hs = np.linspace(0.0, 1.0 - 1e-9, ngrid)
    ph = np.array([feedback_map(m, n, float(x))["phi"] for x in hs])
    g = ph - hs
    out = []
    if g[0] <= 0 and ph[0] == 0.0:
        # h = 0 is a fixed point (memory-gated all-miss state) when Phi(0) = 0
        out.append(dict(h=0.0, slope=float((ph[1] - ph[0]) / (hs[1] - hs[0])), stable=bool(ph[1] - ph[0] < hs[1] - hs[0])))
    for j in range(len(hs) - 1):
        if g[j] > 0 and g[j + 1] <= 0 or g[j] < 0 and g[j + 1] >= 0:
            if j == 0 and ph[0] == 0.0:
                continue
            hstar = brentq(lambda x: feedback_map(m, n, x)["phi"] - x, hs[j], hs[j + 1], xtol=1e-10)
            eps = 1e-5
            sl = (feedback_map(m, n, min(hstar + eps, 1 - 1e-9))["phi"] - feedback_map(m, n, max(hstar - eps, 0.0))["phi"]) / (2 * eps)
            out.append(dict(h=hstar, slope=sl, stable=bool(sl < 1.0)))
    return out


# ------------------------------------------------------------------------------------------------ open system


@dataclass
class OpenEquilibria:
    lam: float
    n1: float              # stable good equilibrium (nan if lam >= mu_max)
    n_u: float             # basin boundary on the good branch (unstable equilibrium or the upper fold)
    trapped_drift: float   # dn/dt on the all-miss branch = lam - mu_b (> 0: the backlog grows)
    b_stat: float          # critical burst of stationary-composition sessions = n_u - n1


def open_equilibria(cs: CurveSummary, lam: float) -> OpenEquilibria:
    """Quasi-static open system dn/dt = lam - mu(n, branch).  On the stable good branch n -> n1 if n < n_u; past n_u
    the good branch is left (it ends at the upper fold or mu < lam) and the system falls to the all-miss branch,
    where dn/dt = lam - mu_b."""
    ng, mug = mu_good_of_n(cs)
    if lam >= cs.mu_max:
        return OpenEquilibria(lam, math.nan, math.nan, lam - cs.mu_b, math.nan)
    i_star = int(np.argmax(mug))
    # n1: first upward crossing of lam on the rising part
    j = np.where((mug[:-1] < lam) & (mug[1:] >= lam))[0]
    j = j[j < i_star + 1]
    if len(j) == 0:
        n1 = 0.0
    else:
        j0 = j[0]
        n1 = float(ng[j0] + (lam - mug[j0]) / (mug[j0 + 1] - mug[j0]) * (ng[j0 + 1] - ng[j0]))
    # n_u: first downward crossing after the peak, else the end of the stable good branch
    jj = np.where((np.arange(len(mug) - 1) >= i_star) & (mug[:-1] >= lam) & (mug[1:] < lam))[0]
    if len(jj):
        k0 = jj[0]
        n_u = float(ng[k0] + (mug[k0] - lam) / (mug[k0] - mug[k0 + 1]) * (ng[k0 + 1] - ng[k0]))
    else:
        n_u = float(ng[-1])
    return OpenEquilibria(lam, n1, n_u, lam - cs.mu_b, n_u - n1)


# ------------------------------------------------------------------------------------------------ fresh-cohort burst


def cohort_peak_kv(wl: Workload) -> Tuple[float, int]:
    """max_j G_j E_j: the largest expected KV per initial session of a cohort started together (tokens), and its turn."""
    v = wl.G * wl.E
    j = int(np.argmax(v))
    return float(v[j]), j + 1


def live_demand(m: Model, pt: Dict[str, float]) -> float:
    """KV that would be resident if no live session had been evicted: running reservations plus the full KV of every
    session in a tool call (dead KV excluded)."""
    return pt["K_run"] + pt["mu"] * m.wl.A1 * m.wl.zmean


def critical_burst_fresh(m: Model, cs: CurveSummary, lam: float) -> Dict[str, float]:
    """Critical size of a burst of FRESH sessions (heuristic, see notes [T5]).  The good state survives the burst iff
    the peak live KV demand stays below the live demand at the end of the stable good branch:
        D_bg(lam) + b * max_j G_j E_j  <  D_live(n_u).
    Fresh sessions start with 2,100 tokens and grow by 650 per turn; the cohort's expected KV per initial session
    peaks at max_j G_j E_j (4,331 tokens at turn 12), against E_lb ~ 10.6k for a stationary session."""
    eq = open_equilibria(cs, lam)
    if not math.isfinite(eq.n1):
        return dict(lam=lam, b_fresh=0.0, b_stat=0.0, D_bg=math.nan, D_u=math.nan)
    pts = cs.pts
    n = np.array([p["n"] for p in pts])
    Dl = np.array([live_demand(m, p) for p in pts])
    ng, _ = mu_good_of_n(cs)
    jg = len(ng)
    D_bg = float(np.interp(eq.n1, n[:jg], Dl[:jg]))
    D_u = float(np.interp(eq.n_u, n[:jg], Dl[:jg]))
    cpk, jpk = cohort_peak_kv(m.wl)
    return dict(lam=lam, n1=eq.n1, n_u=eq.n_u, b_stat=eq.b_stat, D_bg=D_bg, D_u=D_u, cohort_peak_kv=cpk, cohort_peak_turn=jpk,
                b_fresh=(D_u - D_bg) / cpk)


# ------------------------------------------------------------------------------------------------ rescue by a cap


def rescue_plan(m: Model, cs: CurveSummary, lam: float, cap: float, n_engage: float, gate_engage: float = 0.0) -> Dict[str, float]:
    """Fluid prediction for a client cap c engaged in the trapped state with n_engage sessions in the system [T6].
    Phase 1: the population in the system falls by attrition at the all-miss completion rate mu_b (the gate admits
    nothing while n > c) until it leaves the all-miss branch at n_lo = min(n_fold_lo, n_b) (only if c < n_lo).
    Phase 2: on the good branch the population falls from n_lo to c at rate mu_good(n).
    Phase 3: the gate (fed at rate lam since engagement) drains at rate mu_good(c) - lam.
    If c >= n_lo the capped system is a closed system of c sessions on its all-miss branch: no recovery."""
    ng, mug = mu_good_of_n(cs)
    n_lo = cs.n_fold_lo
    mu_c = float(np.interp(cap, ng, mug)) if cap <= ng[-1] else math.nan
    out = dict(lam=lam, cap=cap, n_engage=n_engage, n_lo=n_lo, mu_cap=mu_c, mu_b=cs.mu_b)
    if not (cap < n_lo) or not math.isfinite(mu_c):
        out.update(recovers=False, reason="cap at or above the lower end of the all-miss branch: the capped closed system "
                                          "is bistable and stays on its all-miss branch")
        return out
    if lam >= mu_c:
        out.update(recovers=False, reason="lam >= mu(cap): the gate never drains")
        return out
    t1 = max(n_engage - n_lo, 0.0) / cs.mu_b
    # phase 2: integrate dn/dt = -mu_good(n) from n_lo to cap
    nn = np.linspace(n_lo, cap, 400)
    mu_nn = np.interp(nn, ng, mug)
    t2 = float(np.trapz(1.0 / mu_nn, -nn)) if n_lo > cap else 0.0
    gate = gate_engage + lam * (t1 + t2)
    t3 = gate / (mu_c - lam)
    out.update(recovers=True, t_leave_trap=t1, t_to_cap=t2, gate_at_cap=gate, t_drain=t3, t_total=t1 + t2 + t3,
               after_release="good forever (fluid): released at the stable equilibrium n1 < cap")
    return out


# ------------------------------------------------------------------------------------------------ on a grid of n


def curve_on_grid(cs: CurveSummary, ngrid: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(mu, hit, stable_unique) on a grid of populations for a fold-free curve: the W = 0 curve below n_b, the all-miss
    level mu_b (hit 0) at and above n_b.  If the curve has a fold, the stable good branch is used below the upper fold
    and the all-miss branch above it (the 'good-first' convention), and stable_unique flags the bistable band."""
    n = np.array([p["n"] for p in cs.pts])
    mu = np.array([p["mu"] for p in cs.pts])
    hit = np.array([p["hit"] for p in cs.pts])
    if not cs.bistable:
        o = np.argsort(n)
        mu_g = np.interp(ngrid, n[o], mu[o], right=cs.mu_b)
        hit_g = np.interp(ngrid, n[o], hit[o], right=0.0)
        return mu_g, hit_g, np.ones_like(ngrid, bool)
    ng, mug = mu_good_of_n(cs)
    jg = len(ng)
    mu_g = np.where(ngrid <= ng[-1], np.interp(ngrid, ng, mug), cs.mu_b)
    hit_g = np.where(ngrid <= ng[-1], np.interp(ngrid, ng, hit[:jg]), 0.0)
    uniq = (ngrid < cs.n_fold_lo) | (ngrid > cs.n_fold_hi)
    return mu_g, hit_g, uniq


def kv_dispersion(wl: Workload, S_bar: float) -> Dict[str, float]:
    """Moments of the KV footprint of the sessions present.
    closed: a session present is at turn k with probability ~ w_k (equal time per turn), footprint E_k:
            CV^2 = Var_w(E) / E_w(E)^2, so the total KV of n sessions has variance n CV^2 (in units of E_w(E)).
    open (Poisson sessions, shot noise): Var(D) / E[D] in units of E_lb = E[int c^2] / (E[int c] E_lb) = I_D."""
    E, G, Gn = wl.E, wl.G, wl.Gnext
    w = wl.w
    Ebar = float((w * E).sum())
    cv2 = float((w * E ** 2).sum()) / Ebar ** 2 - 1.0
    int_c = float((G * E).sum() * S_bar + (Gn * E).sum() * wl.zmean)
    int_c2 = float((G * E ** 2).sum() * S_bar + (Gn * E ** 2).sum() * wl.zmean)
    life = wl.ET * S_bar + (wl.ET - 1.0) * wl.zmean
    E_lb = int_c / life
    return dict(Ebar=Ebar, cv2=cv2, E_lb=E_lb, I_D=int_c2 / (int_c * E_lb))


def annealed_curve(wl: Workload, cost: Costs, M: float, ngrid: np.ndarray, cv2: Optional[float] = None,
                   n_theta: int = 41) -> Dict[str, np.ndarray]:
    """Finite-size heuristic [F1]: at population n the total KV demand of the sessions present fluctuates around its
    mean with relative variance cv2 / n (turn-index mix), slowly compared with the internal relaxation.  Averaging the
    fluid model over that demand ratio theta ~ N(1, cv2/n), i.e. over pools M / theta, gives
        mu~(n) = E_theta[ mu_fluid(n; M / theta) ],   hit~(n) likewise.
    Uses only the workload (cv2) and the fluid model; nothing is fitted."""
    if cv2 is None:
        cv2 = kv_dispersion(wl, 1.7)["cv2"]
    sd_max = math.sqrt(cv2 / max(ngrid.min(), 1.0))
    thetas = np.linspace(max(0.5, 1 - 4.0 * sd_max), 1 + 4.0 * sd_max, n_theta)
    tab_mu, tab_hit = [], []
    for th in thetas:
        m = Model(wl, cost, M / th)
        cs = summarize_curve(m)
        a, b, _ = curve_on_grid(cs, ngrid)
        tab_mu.append(a)
        tab_hit.append(b)
    tab_mu, tab_hit = np.array(tab_mu), np.array(tab_hit)
    mu_a, hit_a = np.zeros_like(ngrid), np.zeros_like(ngrid)
    for j, n in enumerate(ngrid):
        sd = math.sqrt(cv2 / n)
        wts = np.exp(-0.5 * ((thetas - 1.0) / sd) ** 2)
        wts /= wts.sum()
        mu_a[j] = float((wts * tab_mu[:, j]).sum())
        hit_a[j] = float((wts * tab_hit[:, j]).sum())
    i1 = int(np.argmin(np.abs(thetas - 1.0)))
    return dict(n=ngrid, mu=mu_a, hit=hit_a, mu_fluid=tab_mu[i1], hit_fluid=tab_hit[i1], cv2=np.array(cv2))


# ------------------------------------------------------------------------------------------------ window law


def window_law_terms(m: Model, cs: CurveSummary) -> Dict[str, float]:
    """The explicit window formula [T4] evaluated with model quantities at the peak, for comparison with the exact
    mu_max / mu_b:
        omega_approx = (M / E_bar) * c_miss / (S_hit + h* zbar (1 - 1/E[T]) + R*/E[T])          (memory regime)
        omega_cap    = c_miss / c_hit                                                            (compute regime)
    with E_bar = sum_k w_k E_k, c_miss = GPU time per miss turn = 1 / nu_b, c_hit = per-turn GPU time at h = 1."""
    wl = m.wl
    b = m.bad()
    c_miss = 1.0 / b["nu"]
    c_hit = 1.0 / m.nu_cap(1.0)
    pk = min(cs.pts, key=lambda p: abs(p["mu"] - cs.mu_max))
    s = m.server(pk["nu"], pk["h"])
    Ebar = float((wl.w * wl.E).sum())
    denom = s.S_bar + pk["h"] * wl.zmean * (1 - 1 / m.ET) + pk["R"] / m.ET
    om_mem = (m.M / Ebar) * c_miss / denom
    return dict(omega_exact=cs.window, omega_mem=om_mem, omega_cap=c_miss / c_hit, c_miss=c_miss, c_hit=c_hit,
                S_hit_peak=s.S_bar, h_peak=pk["h"], R_peak=pk["R"], Ebar=Ebar)


def window_upper_bound(m: Model, nh: int = 400) -> Dict[str, float]:
    """Rigorous (within the model) explicit bound [T4(d)]: for every W = 0 state with follow-up hit probability h,
        nu <= nu_cap(h)                                         (compute)
        nu <= M E[T] / ( E[T] kappa0(h) + A1 E[min(Z, F^-1(h))] + E[E_T] F^-1(h) )      (memory)
    where kappa0(h) = sum_k w_k E_k (t_P,k(h) + S_D(0, h)) is the zero-load KV-time per turn (K_run >= nu kappa0).
    Hence mu_max / mu_b <= max_h min(...) / nu_b."""
    wl = m.wl
    b = m.bad()
    best, hbest = 0.0, 0.0
    for h in np.linspace(0.0, 1.0 - 1e-6, nh):
        s0 = m.server(1e-9, float(h))
        kappa0 = s0.K_run / 1e-9
        R = wl.Finv(float(h))
        mem = m.M * m.ET / (m.ET * kappa0 + wl.A1 * wl.Emin(R) + wl.EET * R)
        v = min(m.nu_cap(float(h)), mem)
        if v > best:
            best, hbest = v, float(h)
    return dict(omega_upper=best / b["nu"], h_at_bound=hbest, nu_bound=best)


def local_window_condition(m: Model, dh: float = 1e-4) -> Dict[str, float]:
    """[T3] The curve leaves the all-miss end with increasing throughput iff
        Delta_S := sum_k w_k E_k |dS_k/dh| / E_bar  >  1 / f_Z(0+)   (= zbar for exponential tool times),
    evaluated at (nu_b, h = 0): a marginal hit must save more reservation time than the idle time it costs."""
    wl = m.wl
    b = m.bad()
    s0 = m.server(b["nu"], 0.0)
    s1 = m.server(b["nu"], dh)
    Ebar = float((wl.w * wl.E).sum())
    hk0, hk1 = m.hk(0.0), m.hk(dh)
    S0 = hk0 * m.tPh + (1 - hk0) * m.tPm + s0.S_D
    S1 = hk1 * m.tPh + (1 - hk1) * m.tPm + s1.S_D
    dS = (S1 - S0) / dh
    Delta_S = float(-(wl.w * wl.E * dS).sum() / Ebar)
    return dict(Delta_S=Delta_S, inv_f0=1.0 / wl.dens0(), holds=bool(Delta_S > 1.0 / wl.dens0()))
