"""Seeded workload generation: session arrivals, turn counts, tool times and synthetic content.

Mirrors ``prefixmeta.workload`` (the simulator): Poisson session arrivals, an optional scripted burst
(``N`` extra sessions with start times uniform on ``[t_b, t_b+W)``), an optional piecewise-linear rate ramp
(thinning), ``T ~ min(Geometric(1/mean_turns), max_turns)`` turns, and tool times ``Z ~ Exp(mean)`` between
turns. Prompt context at turn ``t`` is ``P_t = L0 + (t-1)(Delta+d)`` tokens.

Reproducibility. Every random quantity comes from ``numpy.random.Generator`` objects built from
``SeedSequence(entropy=seed, spawn_key=(stream, ...))``. Arrivals use stream-level generators; everything
per-session (turn count, tool times, content) is keyed by ``(origin, index-within-origin[, turn])`` so a
session's spec and text depend only on ``(seed, origin, index)``: adding a burst or changing the rate does not
change the content or length of the other sessions (common random numbers across configurations).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np

from .config import ArrivalsCfg, WorkloadCfg

# stream ids (first element of every spawn_key)
S_ARRIVALS, S_THIN, S_BURST, S_SPEC, S_CONTENT, S_SYNTH_OUT = range(6)
ORIGIN_CODE = {"base": 0, "burst": 1, "closed": 2}

Context = Union[np.ndarray, str]


def make_rng(seed: int, *key: int) -> np.random.Generator:
    """Generator for stream ``key`` of run seed ``seed`` (explicit, never global state)."""
    return np.random.default_rng(np.random.SeedSequence(entropy=int(seed), spawn_key=tuple(int(k) for k in key)))


@dataclass(frozen=True)
class SessionPlan:
    sid: int                     # unique within a run (rank in arrival order for open plans)
    origin: str                  # base | burst | closed
    idx: int                     # index within origin (keys the per-session random streams)
    arrival_s: float
    n_turns: int
    tool_times_s: Tuple[float, ...]    # length n_turns - 1


# ---------------------------------------------------------------- per-session spec
def draw_tool_times(rng: np.random.Generator, n: int, dist: str, mean: float, cv: float) -> np.ndarray:
    if n <= 0:
        return np.zeros(0)
    if dist == "exp":
        return rng.exponential(mean, size=n)
    if dist == "lognormal":
        s2 = np.log1p(cv * cv)
        return rng.lognormal(np.log(mean) - 0.5 * s2, np.sqrt(s2), size=n)
    if dist == "const":
        return np.full(n, float(mean))
    raise ValueError(f"unknown tool_time_dist {dist!r}")


def session_spec(seed: int, origin: str, idx: int, wl: WorkloadCfg) -> Tuple[int, Tuple[float, ...]]:
    """(n_turns, tool_times) of session ``(origin, idx)``. T ~ min(Geometric(1/mean_turns), max_turns)."""
    rng = make_rng(seed, S_SPEC, ORIGIN_CODE[origin], idx)
    t = min(int(rng.geometric(1.0 / wl.mean_turns)), wl.max_turns)
    tools = draw_tool_times(rng, t - 1, wl.tool_time_dist, wl.tool_time_mean_s, wl.tool_time_cv)
    return t, tuple(float(x) for x in tools)


def effective_mean_turns(wl: WorkloadCfg) -> float:
    """E[min(Geometric(1/mean_turns), max_turns)] (same formula as the simulator)."""
    p = 1.0 / wl.mean_turns
    return (1.0 - (1.0 - p) ** wl.max_turns) / p


def prompt_len(wl: WorkloadCfg, turn: int) -> int:
    """Prompt context P_t (tokens) at 1-based turn t:  L0 + (t-1)(Delta+d)."""
    return wl.initial_context_tokens + (turn - 1) * (wl.new_prompt_tokens + wl.decode_tokens)


# ---------------------------------------------------------------- arrivals
def poisson_times(rng: np.random.Generator, rate: float, t0: float, t1: float) -> np.ndarray:
    """Homogeneous Poisson on [t0, t1): N ~ Poisson(rate*dt), then sorted uniforms (exact)."""
    if rate <= 0 or t1 <= t0:
        return np.zeros(0)
    n = int(rng.poisson(rate * (t1 - t0)))
    return np.sort(rng.uniform(t0, t1, size=n))


def ramp_rate(t: np.ndarray, knots: Sequence[Tuple[float, float]]) -> np.ndarray:
    """Piecewise-linear rate through ``knots`` = [(t_s, rate)], constant outside the knot range."""
    ts = np.array([k[0] for k in knots], dtype=float)
    rs = np.array([k[1] for k in knots], dtype=float)
    return np.interp(np.asarray(t, dtype=float), ts, rs)


def ramp_times(rng_cand: np.random.Generator, rng_keep: np.random.Generator,
               knots: Sequence[Tuple[float, float]], horizon: float) -> np.ndarray:
    """Non-homogeneous Poisson with the piecewise-linear ramp rate on [0, horizon) via thinning."""
    rate_max = max(r for _, r in knots)
    cand = poisson_times(rng_cand, rate_max, 0.0, horizon)
    if len(cand) == 0:
        return cand
    keep = rng_keep.random(cand.shape[0]) < ramp_rate(cand, knots) / rate_max
    return cand[keep]


def burst_times(seed: int, n: int, t0: float, width: float) -> np.ndarray:
    """``n`` burst start times uniform on [t0, t0+width), sorted."""
    rng = make_rng(seed, S_BURST)
    return np.sort(rng.uniform(t0, t0 + width, size=n)) if width > 0 else np.full(n, float(t0))


def build_open_plan(seed: int, wl: WorkloadCfg, arr: ArrivalsCfg, duration_s: float,
                    rate: Optional[float], ramp_knots: Sequence[Tuple[float, float]]) -> List[SessionPlan]:
    """All sessions of an open-loop run (constant or ramp arrivals, plus an optional burst), sorted by arrival.
    Session ids are ranks in arrival order (stable: base before burst on ties)."""
    if arr.kind == "constant":
        if rate is None:
            raise ValueError("constant arrivals need a rate (arrivals.rate or rate_mult*lambda_ref)")
        base = poisson_times(make_rng(seed, S_ARRIVALS), rate, 0.0, duration_s)
    elif arr.kind == "ramp":
        base = ramp_times(make_rng(seed, S_ARRIVALS), make_rng(seed, S_THIN), ramp_knots, duration_s)
    else:
        raise ValueError(f"build_open_plan does not handle kind={arr.kind!r}")
    parts: List[Tuple[str, int, float]] = [("base", i, float(t)) for i, t in enumerate(base)]
    if arr.burst is not None and arr.burst.n > 0:
        bt = burst_times(seed, arr.burst.n, arr.burst.t_s, arr.burst.width_s)
        parts += [("burst", i, float(t)) for i, t in enumerate(bt)]
    parts.sort(key=lambda p: p[2])          # python sort is stable: base precedes burst on ties
    plan = []
    for sid, (origin, idx, t) in enumerate(parts):
        n_turns, tools = session_spec(seed, origin, idx, wl)
        plan.append(SessionPlan(sid=sid, origin=origin, idx=idx, arrival_s=t, n_turns=n_turns, tool_times_s=tools))
    return plan


def make_closed_session(seed: int, wl: WorkloadCfg, sid: int, idx: int, arrival_s: float) -> SessionPlan:
    """Session ``idx`` of a closed-population run (the first ``closed_n`` start at t=0, replacements later)."""
    n_turns, tools = session_spec(seed, "closed", idx, wl)
    return SessionPlan(sid=sid, origin="closed", idx=idx, arrival_s=arrival_s, n_turns=n_turns, tool_times_s=tools)


# ---------------------------------------------------------------- synthetic content
# Distinct common English words (count is len(WORDS), tested for uniqueness), intended to be ~one token each (with a leading space) in common BPE
# vocabularies. NOT verified against the Qwen tokenizer offline: text mode reports the server's prompt_tokens.
WORDS: Tuple[str, ...] = tuple("""
the of and to in is it you that he was for on are with as his they be at one have this from or had by hot but some
what there we can out other were all your when up use word how said an each she which do their time if will way
about many then them would write like so these her long make thing see him two has look more day could go come did
number sound no most people my over know water than call first who may down side been now find any new work part take
get place made live where after back little only round man year came show every good me give our under name very
through just form much great think say help low line before turn cause same mean differ move right boy old too does
tell sentence set three want air well also play small end put home read hand port large spell add even land here must
big high such follow act why ask men change went light kind off need house picture try us again animal point mother
world near build self earth father head stand own page should country found answer school grow study still learn
plant cover food sun four between state keep eye never last let thought city tree cross farm hard start might story saw
far sea draw left late run while press close night real life few north open seem together next white children begin
got walk example ease paper group always music those both mark often letter until mile river car feet care second book
carry took science eat room friend began idea fish mountain stop once base hear horse cut sure watch color face wood main
""".split())


def _words_text(rng: np.random.Generator, n_words: int) -> str:
    idx = rng.integers(0, len(WORDS), size=n_words)
    return "".join(" " + WORDS[i] for i in idx)


class ContentGen:
    """Deterministic synthetic text/tokens per (seed, origin, idx, turn)."""

    def __init__(self, seed: int, wl: WorkloadCfg):
        self.seed = int(seed)
        self.wl = wl

    def _n(self, tokens: int) -> int:
        return max(1, int(round(tokens * self.wl.text_words_per_token)))

    def _fresh(self, stream: int, origin: str, idx: int, turn: int, n_tokens: int) -> Context:
        rng = make_rng(self.seed, stream, ORIGIN_CODE[origin], idx, turn)
        if self.wl.prompt_mode == "tokens":
            return rng.integers(self.wl.token_id_low, self.wl.token_id_high, size=n_tokens, dtype=np.int32)
        return _words_text(rng, self._n(n_tokens))

    def initial(self, sp: SessionPlan) -> Context:
        """Turn-1 prompt context: L0 tokens, unique to the session."""
        return self._fresh(S_CONTENT, sp.origin, sp.idx, 1, self.wl.initial_context_tokens)

    def delta(self, sp: SessionPlan, turn: int) -> Context:
        """New content appended at turn ``turn`` >= 2: Delta tokens."""
        return self._fresh(S_CONTENT, sp.origin, sp.idx, turn, self.wl.new_prompt_tokens)

    def synthetic_output(self, sp: SessionPlan, turn: int) -> Context:
        """Stand-in for the model's output when the server returns no token ids (tokens mode)."""
        return self._fresh(S_SYNTH_OUT, sp.origin, sp.idx, turn, self.wl.decode_tokens)


def extend_context(ctx: Context, more: Context) -> Context:
    if isinstance(ctx, str):
        assert isinstance(more, str)
        return ctx + more
    assert not isinstance(more, str)
    return np.concatenate([ctx, np.asarray(more, dtype=np.int32)])


def context_len(ctx: Context) -> int:
    """Length in tokens (tokens mode) or whitespace-separated words (text mode)."""
    return len(ctx.split()) if isinstance(ctx, str) else int(ctx.shape[0])
