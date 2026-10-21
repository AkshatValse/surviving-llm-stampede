"""Workload generation for the prefix-cache metastability simulator.

A *session* is an agent trajectory: T turns, each turn appends ``new_prompt_tokens`` (Delta) to the
context, decodes ``decode_tokens`` (d) tokens, then (except after the last turn) spends a tool-call
time Z before the next turn. Context lengths (tokens):

* prompt context at turn t (what a miss must prefill):  P_t = L0 + (t-1) * (Delta + d)
* end context at turn t (resident KV after decode):      E_t = P_t + d
* a hit at turn t>=2 prefills only Delta tokens (the resident prefix is E_{t-1} = P_t - Delta).

All randomness comes from ``numpy.random.Generator`` streams spawned from one ``SeedSequence`` per
seed. Per-session quantities (number of turns, tool times) are drawn *at generation time in arrival
order*, never inside the engine, so the same seed gives the same workload under every policy
(common random numbers).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class WorkloadParams:
    initial_context_tokens: int
    new_prompt_tokens: int
    decode_tokens: int
    mean_turns: float
    max_turns: int
    tool_time_mean_s: float
    tool_time_dist: str
    tool_time_cv: float

    @classmethod
    def from_dict(cls, d: dict) -> "WorkloadParams":
        return cls(**d)

    def prompt_len(self, turn: int) -> int:
        """Prompt context P_t (tokens) at 1-based turn t."""
        return self.initial_context_tokens + (turn - 1) * (self.new_prompt_tokens + self.decode_tokens)

    def end_len(self, turn: int) -> int:
        """End-of-turn context E_t = P_t + d."""
        return self.prompt_len(turn) + self.decode_tokens

    def effective_mean_turns(self) -> float:
        """E[min(Geometric(1/mean_turns), max_turns)]."""
        p = 1.0 / self.mean_turns
        return (1.0 - (1.0 - p) ** self.max_turns) / p


@dataclass
class SessionSpecs:
    """Pre-generated sessions, sorted by arrival time. Session id = index."""
    arrival: np.ndarray      # (n,) float64 seconds (np.inf = not scheduled, used by closed mode)
    n_turns: np.ndarray      # (n,) int64
    tool_off: np.ndarray     # (n,) int64 offset into tool_flat
    tool_flat: np.ndarray    # (sum(T-1),) float64 tool-call times; session i uses tool_flat[off : off+T-1]

    def __len__(self) -> int:
        return int(self.arrival.shape[0])

    def tools_of(self, i: int) -> np.ndarray:
        o = int(self.tool_off[i])
        return self.tool_flat[o:o + int(self.n_turns[i]) - 1]


@dataclass(frozen=True)
class ArrivalPlan:
    """How sessions arrive. kind: 'constant' | 'triangle' | 'closed' | 'none'.

    constant : homogeneous Poisson with ``rate`` on [0, horizon_s].
    triangle : Poisson with rate rising linearly rate_lo -> rate_hi over ramp_s, then back (2*ramp_s total).
    closed   : ``closed_n`` sessions at t=0; the engine injects a replacement at each completion;
               ``pool`` sessions are generated (arrival = inf beyond the first closed_n).
    none     : no Poisson arrivals (only the extras below).
    Extras (on top of any kind): ``initial_cold`` sessions arriving at t=0; ``burst_n`` sessions with
    arrival times uniform on [burst_t0, burst_t0 + burst_width_s).
    """
    kind: str
    horizon_s: float
    rate: float = 0.0
    rate_lo: float = 0.0
    rate_hi: float = 0.0
    ramp_s: float = 0.0
    closed_n: int = 0
    pool: int = 0
    initial_cold: int = 0
    burst_n: int = 0
    burst_t0: float = 0.0
    burst_width_s: float = 0.0


def turn_counts(rng: np.random.Generator, n: int, mean_turns: float, max_turns: int) -> np.ndarray:
    """T ~ Geometric(p=1/mean_turns) on {1,2,...}, capped at max_turns."""
    t = rng.geometric(1.0 / mean_turns, size=n).astype(np.int64)
    return np.minimum(t, max_turns)


def tool_times(rng: np.random.Generator, n: int, dist: str, mean: float, cv: float) -> np.ndarray:
    """Tool-call durations: exponential(mean) or lognormal with the given mean and CV."""
    if n == 0:
        return np.zeros(0)
    if dist == "exp":
        return rng.exponential(mean, size=n)
    if dist == "lognormal":
        s2 = np.log1p(cv * cv)
        return rng.lognormal(np.log(mean) - 0.5 * s2, np.sqrt(s2), size=n)
    raise ValueError(f"unknown tool_time_dist {dist!r}")


def triangle_rate(t: np.ndarray, rate_lo: float, rate_hi: float, ramp_s: float) -> np.ndarray:
    """Triangle rate: rate_lo at t=0, rate_hi at t=ramp_s, rate_lo at t=2*ramp_s."""
    t = np.asarray(t, dtype=float)
    frac = np.where(t <= ramp_s, t / ramp_s, 2.0 - t / ramp_s)
    return rate_lo + (rate_hi - rate_lo) * np.clip(frac, 0.0, 1.0)


def _poisson_times(rng: np.random.Generator, rate: float, t0: float, t1: float) -> np.ndarray:
    """Homogeneous Poisson on [t0, t1): N ~ Poisson(rate*dt), then sorted uniforms (exact)."""
    n = int(rng.poisson(rate * (t1 - t0)))
    return np.sort(rng.uniform(t0, t1, size=n))


def _thinned_triangle_times(rng: np.random.Generator, plan: ArrivalPlan) -> np.ndarray:
    """Non-homogeneous Poisson with triangle rate via thinning of a rate_max process."""
    rate_max = max(plan.rate_lo, plan.rate_hi)
    cand = _poisson_times(rng, rate_max, 0.0, plan.horizon_s)
    keep = rng.random(cand.shape[0]) < triangle_rate(cand, plan.rate_lo, plan.rate_hi, plan.ramp_s) / rate_max
    return cand[keep]


def _make_block(arrivals: np.ndarray, turn_rng: np.random.Generator, tool_rng: np.random.Generator,
                wl: WorkloadParams):
    n = arrivals.shape[0]
    nt = turn_counts(turn_rng, n, wl.mean_turns, wl.max_turns)
    flat = tool_times(tool_rng, int(np.sum(nt - 1)), wl.tool_time_dist, wl.tool_time_mean_s, wl.tool_time_cv)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    return arrivals.astype(float), nt, off, flat


def build_specs(wl: WorkloadParams, plan: ArrivalPlan, seed: int) -> SessionSpecs:
    """Generate all sessions for one run. Streams (spawned from SeedSequence(seed)):
    0 base arrivals (and thinning uniforms), 1 turn counts, 2 tool times, 3 extras (cold start / burst),
    with the extras' turn counts and tool times drawn from children of stream 3.
    """
    ss = np.random.SeedSequence(seed)
    s_arr, s_turn, s_tool, s_extra = ss.spawn(4)
    arr_rng, turn_rng, tool_rng = (np.random.default_rng(s) for s in (s_arr, s_turn, s_tool))

    if plan.kind == "constant":
        base = _poisson_times(arr_rng, plan.rate, 0.0, plan.horizon_s)
    elif plan.kind == "triangle":
        base = _thinned_triangle_times(arr_rng, plan)
    elif plan.kind == "closed":
        base = np.full(plan.pool, np.inf)
        base[:plan.closed_n] = 0.0
    elif plan.kind == "none":
        base = np.zeros(0)
    else:
        raise ValueError(f"unknown arrival plan kind {plan.kind!r}")
    blocks = [_make_block(base, turn_rng, tool_rng, wl)]

    if plan.initial_cold > 0 or plan.burst_n > 0:
        e_main, e_turn, e_tool = (np.random.default_rng(s) for s in s_extra.spawn(3))
        if plan.initial_cold > 0:
            blocks.append(_make_block(np.zeros(plan.initial_cold), e_turn, e_tool, wl))
        if plan.burst_n > 0:
            tb = np.sort(e_main.uniform(plan.burst_t0, plan.burst_t0 + plan.burst_width_s, size=plan.burst_n))
            blocks.append(_make_block(tb, e_turn, e_tool, wl))

    arrival = np.concatenate([b[0] for b in blocks])
    nt = np.concatenate([b[1] for b in blocks])
    shift = 0
    offs = []
    flats = []
    for b in blocks:
        offs.append(b[2] + shift)
        flats.append(b[3])
        shift += b[3].shape[0]
    off = np.concatenate(offs) if offs else np.zeros(0, np.int64)
    flat = np.concatenate(flats) if flats else np.zeros(0)
    order = np.argsort(arrival, kind="stable")      # stable: base before cold before burst on ties
    return SessionSpecs(arrival=arrival[order], n_turns=nt[order], tool_off=off[order], tool_flat=flat)


def default_session_cap(memory_tokens: float, wl: WorkloadParams) -> Optional[int]:
    """Spec-literal N* = floor(M / mean context at mid-session); mid-session turn = ceil(mean_turns / 2),
    context = end-of-turn context E_mid. None if memory is unbounded."""
    if not np.isfinite(memory_tokens):
        return None
    mid_turn = int(np.ceil(wl.mean_turns / 2.0))
    return int(np.floor(memory_tokens / wl.end_len(mid_turn)))


def length_biased_mean_context(wl: WorkloadParams) -> float:
    """Turn-weighted mean end-of-turn context of the sessions *present in the system*.

    Sessions in the system are length-biased (a session with T turns is present ~T times as long), so the
    time-average context per session is  E[sum_{t<=T} E_t] / E[T] = sum_t P(T >= t) E_t / sum_t P(T >= t)
    with T ~ min(Geometric(1/mean_turns), max_turns). (Treats each turn as equally long; the turn's actual
    duration also depends on hit/miss, which this deliberately ignores.)"""
    p = 1.0 / wl.mean_turns
    t = np.arange(1, wl.max_turns + 1)
    surv = (1.0 - p) ** (t - 1)                     # P(T >= t)
    ctx = wl.initial_context_tokens + (t - 1) * (wl.new_prompt_tokens + wl.decode_tokens) + wl.decode_tokens
    return float(np.sum(surv * ctx) / np.sum(surv))


def length_biased_session_cap(memory_tokens: float, wl: WorkloadParams) -> Optional[int]:
    """N*_lb = floor(M / length_biased_mean_context): the cap at which the *expected* resident working set
    (cap sessions x turn-weighted mean context) fits in M. None if memory is unbounded."""
    if not np.isfinite(memory_tokens):
        return None
    return int(np.floor(memory_tokens / length_biased_mean_context(wl)))
