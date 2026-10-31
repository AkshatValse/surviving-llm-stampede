"""Che-type characteristic-time model of a prefix-cached LLM server with ENDOGENOUS inter-turn gaps.

Approach A of the round-13 theory work (notes/THEORY_r13_che_endogenous.md has the derivation and the validation).

Objects
-------
* Workload (configs/agentload_e2_burst.yaml, workload section): T = min(Geometric(1/15), 60) turns; turn k sends a prompt of
  L_k = L0 + (k-1)(tool + d) tokens; a hit prefills ``hit_new`` = 551 tokens (tool output + last decoded token), a miss the whole
  L_k; every turn decodes d = 100 tokens; tool time Z ~ Exp(z_mean) between turns. After turn k the radix cache holds
  c_k = L_k + d - 1 tokens of the session (the last decoded token has no KV).
* Pool of M tokens, LRU over unpinned KV, dead KV of finished sessions is NOT freed (the engine does not know a session ended).
* Iteration-time cost model (calibration/round6_server_log_fit/calibration.yaml, fitted only to SGLang server-log batch timing):
      prefill iteration  tau_P = fixed + max(floor, per_token * X) + prefill_attn * sum new_i * (pos_i + new_i / 2)
      decode iteration   tau_D = fixed + max(floor, per_token * B) + decode_attn * sum ctx_i / 8192
  SGLang runs prefill and decode as separate iterations with prefill priority ("separate"); vLLM mixes them ("mixed").

Mean-field state of a closed population of n sessions (all quantities stationary means)
-------------------------------------------------------------------------------------
  h   follow-up hit probability (turns k >= 2)
  nu  turn throughput (turns/s);   mu = nu / E[T] sessions/s
  B   decoding batch;   S running time of a request (admission -> completion);   W queue wait before admission
  A   pinned KV (running requests);   R  Che characteristic time of unpinned KV (age at eviction)

  Server (U, unsaturated: every request admitted at once, W = 0):
      B = 99 nu tau_D(B) / (1 - nu E[tau_P](h))          (decode starved by prefill priority; 99 decode iterations per turn)
      S = E[tau_P](h) + B / nu,   n = nu (zbar' + S),   zbar' = z_mean (1 - 1/E[T])
  Memory cap: the pinned KV cannot exceed (1 - eta) M (eta = mean unpinned headroom when admission is memory-blocked).
  If the U solution would pin more, the server is SATURATED (S): B = B_mem, nu = 1 / (E[tau_P] + 99 tau_D(B_mem) / B_mem),
      and the remaining n - nu (zbar' + S) sessions wait in the queue: W = n_Q / nu.
  Che equation (the pool is always full: dead KV is never freed):
      M - A = I(R; W) + D(R),
      I(R; W) = nu sum_k [P(T > k) / E[T]] c_k E[min(Z + W, R)]      (idle KV of live sessions, resident while age < R)
      D(R)    = (nu / E[T]) E[c_T] R                                (dead KV, resident for R after the last turn)
  Hit (endogenous gap: the age at reuse is the tool time PLUS the queue wait):
      h' = Phi_n(h) = P(Z + W < R) = 1 - exp(-(R - W)^+ / z_mean)
  Fixed points h = Phi_n(h) give h(n) and mu(n); stable iff Phi_n'(h) < 1.

Everything here is deterministic numpy; the stochastic parts (escape from the good state, bursts) live in open_system.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace, field
from functools import cached_property
from typing import Dict, List, Optional, Tuple

import numpy as np

# ----------------------------------------------------------------------------------------------------------------- workload


@dataclass(frozen=True)
class Workload:
    L0: float = 2000.0          # initial_context_tokens
    tool_tokens: float = 550.0  # new_prompt_tokens (tool output appended per turn)
    decode: float = 100.0       # decode_tokens
    mean_turns: float = 15.0    # Geometric mean (before the cap)
    max_turns: int = 60
    z_mean: float = 5.0         # tool_time_mean_s
    hit_new: float = 551.0      # tokens a hit prefills (measured: cached = prompt - 551)
    z_shape: float = 1.0        # gamma shape of the tool time (1 = exponential, the workload of record; inf = deterministic)

    # ---- tool-time law helpers (gamma(shape, mean z_mean); shape = inf is deterministic)
    def z_cdf(self, x: float) -> float:
        if x <= 0:
            return 0.0
        if math.isinf(self.z_shape):
            return 1.0 if x > self.z_mean else 0.0
        if self.z_shape == 1.0:
            return 1.0 - math.exp(-x / self.z_mean)
        from scipy.special import gammainc
        return float(gammainc(self.z_shape, x * self.z_shape / self.z_mean))

    def z_min_mean(self, x: float) -> float:
        """E[min(Z, x)]."""
        if x <= 0:
            return 0.0
        if math.isinf(self.z_shape):
            return min(self.z_mean, x)
        if self.z_shape == 1.0:
            return self.z_mean * (1.0 - math.exp(-x / self.z_mean))
        from scipy.special import gammainc
        k = self.z_shape
        F = float(gammainc(k, x * k / self.z_mean))
        part = self.z_mean * float(gammainc(k + 1.0, x * k / self.z_mean))   # E[Z 1{Z < x}]
        return x * (1.0 - F) + part

    def z_sample(self, rng, size):
        if math.isinf(self.z_shape):
            return np.full(size, self.z_mean)
        if self.z_shape == 1.0:
            return rng.exponential(self.z_mean, size=size)
        return rng.gamma(self.z_shape, self.z_mean / self.z_shape, size=size)

    @cached_property
    def k(self) -> np.ndarray:
        return np.arange(1, self.max_turns + 1, dtype=float)

    @cached_property
    def surv(self) -> np.ndarray:
        """P(T >= k), k = 1..max_turns."""
        q = 1.0 - 1.0 / self.mean_turns
        return q ** (self.k - 1.0)

    @cached_property
    def pT(self) -> np.ndarray:
        """P(T = k)."""
        s = self.surv
        return s - np.append(s[1:], 0.0)

    @cached_property
    def ET(self) -> float:
        return float(self.surv.sum())

    @cached_property
    def pi(self) -> np.ndarray:
        """Stationary turn mix: fraction of turns that are turn k = P(T >= k) / E[T]."""
        return self.surv / self.ET

    @cached_property
    def pi_next(self) -> np.ndarray:
        """Rate (per turn) of completions of turn k that are followed by turn k+1: P(T >= k+1) / E[T]."""
        return np.append(self.surv[1:], 0.0) / self.ET

    @cached_property
    def L(self) -> np.ndarray:
        """Prompt tokens at turn k."""
        return self.L0 + (self.k - 1.0) * (self.tool_tokens + self.decode)

    @cached_property
    def c(self) -> np.ndarray:
        """KV tokens the radix cache keeps for the session after turn k."""
        return self.L + self.decode - 1.0

    @cached_property
    def c_run(self) -> np.ndarray:
        """Mean pinned KV of a running turn-k request (prompt plus half the decode)."""
        return self.L + 0.5 * self.decode

    @cached_property
    def EcT(self) -> float:
        """Mean final KV of a session (becomes dead KV)."""
        return float((self.pT * self.c).sum())

    @cached_property
    def EW_allmiss(self) -> float:
        """E[sum_k L_k] = all-miss prefill tokens per session (154,529 for the workload of record)."""
        return float((self.surv * self.L).sum())

    @property
    def zbar_turn(self) -> float:
        """Mean tool time per turn (no tool call after the last turn)."""
        return self.z_mean * (1.0 - 1.0 / self.ET)

    def lb_moments(self, S_good: float) -> Tuple[float, float]:
        """Time-weighted (length-biased) mean and second moment of a session's KV demand in the good state.

        Turn k: running for S_good with c_run[k], then (if T > k) idle for Z ~ Exp(z_mean) with c[k]; the KV of the
        first turn's prompt only exists while it runs (nothing is cached before turn 1)."""
        w_run = self.surv * S_good
        w_idle = np.append(self.surv[1:], 0.0) * self.z_mean
        tot = w_run.sum() + w_idle.sum()
        m1 = ((w_run * self.c_run).sum() + (w_idle * self.c).sum()) / tot
        m2 = ((w_run * self.c_run ** 2).sum() + (w_idle * self.c ** 2).sum()) / tot
        return float(m1), float(m2)


# -------------------------------------------------------------------------------------------------------------------- costs


@dataclass(frozen=True)
class Costs:
    """Iteration-time cost model. Defaults: calibration/round6_server_log_fit/calibration.yaml (SGLang 0.5.22, A100 80GB PCIe)."""
    iter_fixed: float = 0.00924
    iter_floor: float = 0.00126
    per_token: float = 6.26e-05
    decode_attn: float = 0.00031
    attn_norm: float = 8192.0
    prefill_attn: float = 2.24e-09
    chunk: int = 8192
    mode: str = "separate"      # "separate" (SGLang prefill priority) or "mixed" (vLLM chunked prefill with decode)
    max_running: int = 256

    def scaled(self, s: float) -> "Costs":
        """All time constants multiplied by s (s < 1: faster hardware)."""
        return replace(self, iter_fixed=self.iter_fixed * s, iter_floor=self.iter_floor * s, per_token=self.per_token * s,
                       decode_attn=self.decode_attn * s, prefill_attn=self.prefill_attn * s)

    # ---- per-request prefill cost (separate mode: own iterations; mixed: the request's share of shared iterations)
    def prefill_time(self, u: np.ndarray, prefix: np.ndarray) -> np.ndarray:
        u = np.asarray(u, dtype=float)
        prefix = np.asarray(prefix, dtype=float)
        n_it = np.maximum(1.0, np.ceil(u / self.chunk))
        attn = self.prefill_attn * (u * prefix + 0.5 * u * u)
        if self.mode == "separate":
            return n_it * self.iter_fixed + np.maximum(n_it * self.iter_floor, self.per_token * u) + attn
        # mixed: the iteration overhead is shared with the decode batch and charged to the decode side
        return self.per_token * u + attn

    def decode_coeffs(self, B: float, cbar: float) -> Tuple[float, float]:
        """tau_D(B) = a + b B on the branch that contains B (floor below the knee B = floor / per_token)."""
        attn1 = self.decode_attn * cbar / self.attn_norm
        if self.per_token * B < self.iter_floor:
            return self.iter_fixed + self.iter_floor, attn1
        return self.iter_fixed, self.per_token + attn1

    def tau_D(self, B: float, cbar: float) -> float:
        a, b = self.decode_coeffs(B, cbar)
        return a + b * B


# ------------------------------------------------------------------------------------------------------------------- model


@dataclass(frozen=True)
class Cell:
    """One measured or predicted cell: workload, pool, costs and the saturated headroom eta."""
    name: str
    M: float
    costs: Costs = field(default_factory=Costs)
    wl: Workload = field(default_factory=Workload)
    eta: float = 0.03           # unpinned share of the pool when admission is memory-blocked (decode-phase usage ~0.97)
    decode_iters: float = 99.0  # decode iterations per turn after the prefill (first token comes from the prefill)


@dataclass
class State:
    """One evaluation of the map Phi_n at a given follow-up hit probability h."""
    n: float
    h_in: float
    h_out: float
    regime: str                 # "U" or "S"
    nu: float                   # turns/s
    B: float                    # decoding batch
    S: float                    # mean running time (s)
    W: float                    # queue wait (s)
    A: float                    # pinned tokens
    R: float                    # Che characteristic time (s)
    churn: float                # new KV tokens written per second (uncached prefill + decode)
    tau_P: float                # mean prefill cost per turn (s)


class CheModel:
    def __init__(self, cell: Cell):
        self.cell = cell
        wl = cell.wl
        self.wl = wl
        c = cell.costs
        k = wl.k
        # per-turn prefill cost on a miss and on a hit
        self.tauP_miss = c.prefill_time(wl.L, np.zeros_like(wl.L))
        self.tauP_hit = c.prefill_time(np.full_like(wl.L, wl.hit_new), wl.L - wl.hit_new)
        self.tauP_hit[0] = self.tauP_miss[0]          # turn 1 always misses
        self.u_miss = wl.L.copy()
        self.u_hit = np.full_like(wl.L, wl.hit_new)
        self.u_hit[0] = wl.L[0]
        self.cbar_run = float((wl.pi * wl.c_run).sum())
        self.cbar_dec = self.cbar_run
        self.idle_w = wl.pi_next * wl.c               # weights of idle KV per unit turn throughput
        self.dead_w = wl.EcT / wl.ET

    # ---------------------------------------------------------------- per-h averages
    def tauP_mean(self, h: float) -> float:
        wl = self.wl
        t = h * self.tauP_hit + (1.0 - h) * self.tauP_miss
        t[0] = self.tauP_miss[0]
        return float((wl.pi * t).sum())

    def u_mean(self, h: float) -> float:
        u = h * self.u_hit + (1.0 - h) * self.u_miss
        u[0] = self.u_miss[0]
        return float((self.wl.pi * u).sum())

    def churn(self, nu: float, h: float) -> float:
        return nu * (self.u_mean(h) + self.wl.decode)

    # ---------------------------------------------------------------- server
    def batch_U(self, nu: float, h: float) -> float:
        """Decoding batch of the unsaturated server at turn rate nu (inf if the GPU cannot keep up)."""
        c = self.cell.costs
        di = self.cell.decode_iters
        if c.mode == "separate":
            P = nu * self.tauP_mean(h)
            if P >= 1.0:
                return math.inf
            for branch_B in (1.0, 1e9):       # try the floor branch, then the linear branch
                a, b = c.decode_coeffs(branch_B, self.cbar_dec)
                den = 1.0 - P - di * nu * b
                if den <= 0:
                    continue
                B = di * nu * a / den
                a2, b2 = c.decode_coeffs(B, self.cbar_dec)
                if abs(a2 - a) < 1e-15:
                    return B
            # the two branches disagree around the knee: take the linear one if feasible
            a, b = c.decode_coeffs(1e9, self.cbar_dec)
            den = 1.0 - P - di * nu * b
            return di * nu * a / den if den > 0 else math.inf
        # mixed: every iteration advances all running requests; per-request prefill cost w_p, iteration overhead a
        wp = self.tauP_mean(h)
        steps = di + 1.0
        for branch_B in (1.0, 1e9):
            a, b = c.decode_coeffs(branch_B, self.cbar_dec)
            den = 1.0 - nu * wp - steps * nu * b
            if den <= 0:
                continue
            B = steps * nu * a / den
            a2, _ = c.decode_coeffs(B, self.cbar_dec)
            if abs(a2 - a) < 1e-15:
                return B
        a, b = c.decode_coeffs(1e9, self.cbar_dec)
        den = 1.0 - nu * wp - steps * nu * b
        return steps * nu * a / den if den > 0 else math.inf

    def S_U(self, nu: float, h: float) -> float:
        B = self.batch_U(nu, h)
        if not math.isfinite(B):
            return math.inf
        if self.cell.costs.mode == "separate":
            return self.tauP_mean(h) + B / nu
        return B / nu

    def nu_sat(self, h: float, B: float) -> float:
        """Turn throughput of the saturated server with decoding batch B."""
        c = self.cell.costs
        di = self.cell.decode_iters
        if c.mode == "separate":
            return 1.0 / (self.tauP_mean(h) + di * c.tau_D(B, self.cbar_dec) / B)
        steps = di + 1.0
        return 1.0 / (self.tauP_mean(h) + steps * c.tau_D(B, self.cbar_dec) / B)

    @cached_property
    def B_mem(self) -> float:
        """Decoding batch of the saturated all-miss server: pinned KV = (1 - eta) M (prefilling request included)."""
        return self.B_sat(0.0)

    def B_sat(self, h: float) -> float:
        """Decoding batch B with pinned(nu_sat(h, B), B, h) = (1 - eta) M (fixed-point iteration; capped by max_running)."""
        cap = (1.0 - self.cell.eta) * self.cell.M / self.cbar_run
        B = cap
        for _ in range(50):
            nu = self.nu_sat(h, B)
            extra = nu * self.tauP_mean(h) if self.cell.costs.mode == "separate" else 0.0
            B_new = max(1.0, cap - extra)
            if abs(B_new - B) < 1e-9:
                break
            B = B_new
        return float(min(B, self.cell.costs.max_running))

    def pinned(self, nu: float, B: float, h: float) -> float:
        """Pinned KV: decoding batch plus the request(s) in prefill."""
        if self.cell.costs.mode == "separate":
            return (B + nu * self.tauP_mean(h)) * self.cbar_run
        return B * self.cbar_run

    def nu_U(self, n: float, h: float) -> float:
        """Solve n = nu (zbar' + S_U(nu, h)) for nu by bisection (the right side increases in nu)."""
        z = self.wl.zbar_turn
        lo, hi = 0.0, 1.0
        while math.isfinite(self.S_U(hi, h)) and hi * (z + self.S_U(hi, h)) < n:
            hi *= 2.0
            if hi > 1e4:
                break
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            s = self.S_U(mid, h)
            if not math.isfinite(s) or mid * (z + s) > n:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    # ---------------------------------------------------------------- Che equation
    def idle_mean(self, R: float, W: float) -> float:
        """E[min(Z + W, R)] for the workload's tool-time law (W deterministic)."""
        if R <= W:
            return R
        return W + self.wl.z_min_mean(R - W)

    def solve_R(self, free: float, nu: float, W: float) -> float:
        """R >= 0 with I(R; W) + D(R) = free (free = M - A)."""
        if free <= 0:
            return 0.0
        iw = nu * float(self.idle_w.sum())
        dw = nu * self.dead_w

        def f(R):
            return iw * self.idle_mean(R, W) + dw * R - free

        lo, hi = 0.0, 1.0
        while f(hi) < 0:
            hi *= 2.0
            if hi > 1e9:
                return hi
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    # ---------------------------------------------------------------- the map Phi_n
    def evaluate(self, n: float, h: float) -> State:
        M, eta = self.cell.M, self.cell.eta
        z = self.wl.zbar_turn
        nu = self.nu_U(n, h)
        B = self.batch_U(nu, h)
        A = self.pinned(nu, B, h) if math.isfinite(B) else math.inf
        if math.isfinite(A) and A <= (1.0 - eta) * M:
            regime, W = "U", 0.0
            S = self.S_U(nu, h)
        else:
            regime = "S"
            B = self.B_sat(h)
            nu = self.nu_sat(h, B)
            A = self.pinned(nu, B, h)
            S = (self.tauP_mean(h) if self.cell.costs.mode == "separate" else 0.0) + B / nu
            nQ = n - nu * (z + S)
            if nQ < 0:
                # not enough sessions to keep memory blocked: boundary case, the U solution pinned slightly more than the cap
                nQ = 0.0
            W = nQ / nu
        R = self.solve_R(M - A, nu, W)
        h_out = self.wl.z_cdf(R - W) if R > W else 0.0
        return State(n=n, h_in=h, h_out=h_out, regime=regime, nu=nu, B=B, S=S, W=W, A=A, R=R,
                     churn=self.churn(nu, h), tau_P=self.tauP_mean(h))

    def fixed_points(self, n: float, grid: int = 81) -> List[Dict]:
        """All fixed points of h -> Phi_n(h) on [0, 1], with stability (slope of Phi_n below 1)."""
        hs = np.linspace(0.0, 1.0, grid)
        g = np.array([self.evaluate(n, h).h_out - h for h in hs])
        out = []
        # h = 0 is a fixed point iff Phi_n(0) = 0
        if g[0] <= 1e-12:
            st = self.evaluate(n, 0.0)
            slope = (self.evaluate(n, 1e-4).h_out - st.h_out) / 1e-4
            out.append(self._fp_record(n, 0.0, slope))
        for i in range(len(hs) - 1):
            if g[i] > 1e-12 and g[i + 1] <= 1e-12 or g[i] < -1e-12 and g[i + 1] >= -1e-12 or (g[i] > 1e-12 and g[i + 1] < -1e-12):
                lo, hi = hs[i], hs[i + 1]
                glo = g[i]
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    gm = self.evaluate(n, mid).h_out - mid
                    if (gm > 0) == (glo > 0):
                        lo, glo = mid, gm
                    else:
                        hi = mid
                hstar = 0.5 * (lo + hi)
                if hstar < 1e-6 and out and out[0]["h"] == 0.0:
                    continue
                eps = 1e-4
                slope = (self.evaluate(n, min(1.0, hstar + eps)).h_out - self.evaluate(n, max(0.0, hstar - eps)).h_out) / (
                    min(1.0, hstar + eps) - max(0.0, hstar - eps))
                out.append(self._fp_record(n, hstar, slope))
        # dedupe
        ded = []
        for r in sorted(out, key=lambda r: r["h"]):
            if not ded or abs(r["h"] - ded[-1]["h"]) > 1e-4:
                ded.append(r)
        return ded

    def _fp_record(self, n: float, h: float, slope: float) -> Dict:
        st = self.evaluate(n, h)
        wl = self.wl
        return dict(n=n, h=h, hit_all=h * (1.0 - 1.0 / wl.ET), stable=bool(slope < 1.0), slope=slope, regime=st.regime,
                    nu=st.nu, mu=st.nu / wl.ET, B=st.B, S=st.S, W=st.W, A=st.A, R=st.R, churn=st.churn,
                    R_loopvars=self.cell.M / st.churn if st.churn > 0 else math.inf)

    # ---------------------------------------------------------------- curves
    def closed_curve(self, ns) -> List[Dict]:
        rows = []
        for n in ns:
            fps = self.fixed_points(float(n))
            stable = [r for r in fps if r["stable"]]
            for r in fps:
                r = dict(r)
                r["n_fixed_points"] = len(fps)
                r["n_stable"] = len(stable)
                rows.append(r)
        return rows

    def good_branch(self, n: float) -> Optional[Dict]:
        """Highest stable fixed point (the state reached from a warm, all-hit start)."""
        fps = [r for r in self.fixed_points(n) if r["stable"]]
        return max(fps, key=lambda r: r["h"]) if fps else None

    def bad_branch(self, n: float) -> Optional[Dict]:
        fps = [r for r in self.fixed_points(n) if r["stable"]]
        return min(fps, key=lambda r: r["h"]) if fps else None

    # ---------------------------------------------------------------- reference rates
    def allmiss_reference(self, pop: int = 32) -> Dict:
        """Model analogue of E0a: closed population ``pop``, radix cache disabled (h = 0, nothing evictable, eta ~ 0)."""
        wl = self.wl
        h = 0.0
        # with the cache disabled the pinned cap is the whole pool
        Bcap = min(self.cell.M / self.cbar_run, self.cell.costs.max_running)
        nu = self.nu_U(pop, h)
        B = self.batch_U(nu, h)
        if not math.isfinite(B) or self.pinned(nu, B, h) > self.cell.M:
            B = Bcap
            nu = self.nu_sat(h, B)
        tok = nu * self.u_mean(h)
        return dict(nu=nu, lambda_miss_turns=nu / wl.ET, tokens_per_s=tok, B=B)

    def trapped_turn_cost(self, B: Optional[float] = None) -> np.ndarray:
        """Server time per turn-k request in the saturated all-miss state (prefill + amortized decode)."""
        c = self.cell.costs
        B = self.B_mem if B is None else B
        di = self.cell.decode_iters if c.mode == "separate" else self.cell.decode_iters + 1.0
        return self.tauP_miss + di * c.tau_D(B, self.cbar_dec) / B


def default_cells() -> Dict[str, Cell]:
    """The three measured cells, with the independent inputs only (pool, workload, costs)."""
    base = Costs()
    return {
        "a100_300k": Cell("a100_300k", M=300_000.0, costs=base),
        "a100_native": Cell("a100_native", M=955_757.0, costs=base),
        # vLLM: same model, mixed batching; the time scale is fitted to vLLM's own E0a all-miss rate in calibrate_scale()
        "vllm_300k": Cell("vllm_300k", M=300_000.0, costs=replace(base, mode="mixed")),
    }


def calibrate_scale(cell: Cell, target_tokens_per_s: float, pop: int = 32) -> Tuple[Cell, float]:
    """One-parameter fit: scale all cost constants so the model's E0a analogue matches a measured all-miss token rate."""
    lo, hi = 0.05, 20.0
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        m = CheModel(replace(cell, costs=cell.costs.scaled(mid)))
        tok = m.allmiss_reference(pop)["tokens_per_s"]
        if tok > target_tokens_per_s:
            lo = mid
        else:
            hi = mid
    s = math.sqrt(lo * hi)
    return replace(cell, costs=cell.costs.scaled(s)), s
