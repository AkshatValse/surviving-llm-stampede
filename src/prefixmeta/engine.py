"""Iteration-level simulator of a continuous-batching LLM engine with a prefix (KV) cache serving
multi-turn agent sessions.

ALL physical constants are ASSUMPTIONS passed in via ``EngineParams`` (configs/prefix_meta.yaml).

Model summary (see the config for the numbers)
----------------------------------------------
* Iteration time (s)::

      tau = iter_fixed + max(iter_floor, per_token * (prefill_tokens + n_decode))
            + decode_attn * sum_{decode seqs} ctx_i / attn_ctx_norm
            + prefill_attn * sum_{prefill chunks} new_i * ctx_i

  ``ctx_i`` of a decode sequence is its context at the start of the iteration; for a prefill chunk it is
  the KV length after the chunk (``prefill_attn_ctx="end"``) or its causal average (``"mid"``).
* Chunked prefill: at most ``prefill_chunk_budget`` prefill tokens per iteration, handed out FIFO over the
  admitted-but-not-fully-prefilled requests. A request whose last prefill chunk runs in iteration k emits
  its first output token in iteration k and then needs ``d-1`` pure decode iterations (so exactly d tokens).
* Each running decode sequence emits one token per iteration; at most ``max_running_seqs`` requests are
  running (prefilling or decoding).
* KV memory M tokens. A running request *reserves* its full end-of-turn context E_t at admission (no
  mid-run preemption). Idle KV (sessions in a tool call or waiting) is kept per *whole session*
  (all-or-nothing; a simplification of radix-tree partial prefixes) in an LRU (by turn-end time).
  To admit a request the engine evicts idle KV LRU-first (never the admitted request's own session) until
  reserved + E_t + idle <= M; a request is feasible iff reserved + E_t <= M.
* Hit/miss is decided at ADMISSION: if the session's KV is resident the turn prefills only Delta tokens (hit);
  otherwise the whole prompt context P_t (miss). Waiting requests do NOT pin their session's KV
  (assumption, matches vLLM/SGLang behavior): it can be evicted while the request waits.
* Admission pass: runs at an iteration boundary when the state changed (new waiting request, a completion,
  or a prefill iteration finished). The policy supplies the candidate order; admission continues while
  memory / the running cap / the remaining prefill budget allow. By default the pass stops at the first
  candidate that does not fit (``skip_ahead=False``).

Iteration batching (exact)
--------------------------
Between events a pure-decode run (no prefill in progress) has fixed batch composition; tau_k grows
linearly in k because every sequence's context grows by one token per iteration. Using a global
iteration counter G, a decode sequence entering at G_e with context c_e has context (c_e - G_e) + G, so
sum(ctx) = off_sum + n_decode * G is maintained in O(1). n iterations take
S_n = n*tau_0 + b*n*(n-1)/2 (b = decode_attn/norm * n_decode); the run is cut at the first iteration
boundary at/after the next exogenous event (arrival / tool return / horizon) or at the next decode
completion, whichever comes first, so the result equals iteration-by-iteration simulation (tested).
For time-dependent policies (AGING-LPM) the run is additionally cut at the next aging-threshold crossing
(``Policy.next_time_event``), so a request that ages mid-run is considered at the first iteration boundary
after it crosses, exactly as in iteration-by-iteration simulation (tested against the unbatched engine and the
naive reference simulator).

Documented simplifications / fidelity gaps (see the stage-3 review; none changes the qualitative result)
-------------------------------------------------------------------------------------------------------
* Whole-session, all-or-nothing eviction (spec-mandated); a radix cache evicts leaf-by-leaf. A reviewer variant
  with partial eviction gave escape counts within binomial noise.
* Eviction runs per admission inside a pass: an earlier admission can evict the KV of a later candidate of the
  same pass, which is then admitted as a miss (SGLang locks chosen prefixes first). ~0.4% of admissions in a
  trapped run; a reviewer "lock at add" variant gave identical hazard counts.
* No LRU refresh when LPM matches a waiting prefix (SGLang touches matched prefixes). A reviewer variant had no
  effect: the KV of a session is evicted during its tool call, before its next turn is even queued.
Round-2 mechanisms (``mechanisms.py``; all off by default, which reproduces the round-1 engine bit for bit)
--------------------------------------------------------------------------------------------------------
* HARD protection (TTL pins, and queued-session KV under PEEK ``pin``): protected idle KV is never evicted, so the
  feasibility test of an admission becomes ``reserved + end + hard_protected_excluding_own <= M`` and a request that
  does not fit WAITS (under FCFS no-skip the pass stops there). The request's own session KV is part of its
  reservation, so it does not count against it.
* SOFT protection (PEEK ``rank``): queued-session KV is evicted only after all unprotected idle KV.
* TTL pin: set when a non-final turn finishes, expires at ``finish + ttl_s`` (processed in time order with arrivals
  and tool returns; a tool return at exactly the expiry time wins). At expiry the pin is dropped unless the session's
  next request is queued, in which case it stays until that request is admitted. An expired pin leaves the KV as
  ordinary evictable idle KV at its LRU position.
* TTL-pin release before expiry (``Mechanisms.ttl_unpin``): "idle" (default) = only the deadlock breaker below
  ("pins throttle admission"); "eager" / "eager_fit" = Continuum-style release of pins, latest program arrival first,
  whenever the request under consideration does not fit (round-2 review finding 1; the Continuum rule is taken from
  the scout summary and is NOT verified against the paper or its code).
* Deadlock breaker: if the engine is idle (nothing running), a request is waiting, memory is blocked by hard
  protection and no pin expiry is pending, protection is released in LATEST-program-arrival order (largest session id
  first, never the blocked request's own session) until the blocked request fits. Counted in ``n_stall_breaks`` /
  ``n_released``.
* Session cap: a gate of sessions waiting to enter. ``session_cap`` may change over time (AIMD tick every
  ``interval_s``); a decrease never evicts or pauses sessions already in the system (it acts by attrition).
* Early-stop criteria for escape experiments: waiting queue > ``stop_queue_above`` (round 1), backlog = waiting + gate
  > ``stop_backlog_above``, or hit rate < thresh in n consecutive complete metric windows (``stop_low_hit``).

* ``free_kv_on_session_end`` (default True): KV of a finished session is freed at once (an oracle; a real engine
  cannot know the session ended). False keeps it as most-recently-used evictable idle KV, which crowds out live
  sessions and raises the escape rate.

Round-4 eviction rules (``Mechanisms.eviction``; default ``lru`` keeps the rounds 1-3 code path unchanged)
---------------------------------------------------------------------------------------------------------
* ``mru_idle``: evict the idle session whose turn finished most recently (the idle table is ordered by that time).
* ``random``: evict idle sessions uniformly at random without replacement, one draw per victim until the memory need is
  covered; the draws come from a generator dedicated to eviction (``eviction.eviction_rng(seed)``), never from the workload
  streams. Both go through ``eviction.select_victims`` and respect hard (never) / soft (last) protection; the admitted
  request's own session has already left the idle table, and running requests' KV is not in it, so neither is evictable.
* ``Engine(closed=True)`` is the closed-population mode used for the thrashing curve mu(n): ``n`` sessions at t = 0, a fresh
  turn-1 session injected (from the pre-generated pool) at the instant a session completes.

Round-5 allocation modes (``EngineParams.alloc_mode``; ``full_reserve`` = everything above, the default, bit-identical to round 4)
---------------------------------------------------------------------------------------------------------------------------
Registered in configs/prefix_meta_r5_prereg.yaml (+ amendments 1 and 2). Simulator models of the allocation rules a scout reported for
vLLM v0.32.0 (``ondemand_preempt``) and SGLang v0.5.22 (``ratio_reserve``); NOT the engines.

* KV accounting in tokens (block size 1). ``held`` = KV owned by running requests: pos for a prefilling request, ctx = prompt +
  generated for a decoding one (the sampled token counts; a chunk that completes the prompt is charged one extra token), so the idle
  KV after a turn is E_t = P_t + d as in rounds 1-4. Idle KV is cached and counts as FREE: it is evicted (whole sessions, configured
  rule) only when held + idle would exceed M. A request never reserves its decode tail at admission (ondemand) or reserves it scaled by
  the ratio (ratio_reserve).
* Turn = exogenous events -> completions -> RUNNING LOOP (allocate the coming iteration of the running requests; shortage ->
  preempt / retract) -> WAITING LOOP (admission pass, skipped in a turn with a preemption / retraction, due again at the next iteration
  boundary) -> one iteration or a batched pure-decode run (capped so that the decode tokens fit, and at 1 iteration while a pass is due).
* ``ondemand_preempt`` (vLLM-like). Admission: used + prompt-and-generated tokens (+1 if the first chunk completes the prompt) +
  watermark <= M, ``used`` = KV held incl. this turn's allocations. Shortage: the most recently admitted running requests (any phase)
  are preempted until the survivors' (held + demand) fit; their KV stays cached as idle KV at the MRU end, they go to the FRONT of the
  waiting queue and keep their generated tokens; re-admission hits min(surviving KV, num_tokens - 1).
* ``ratio_reserve`` (SGLang-like). Admission (strict): held + commit + ratio * sum(remaining decode tokens) + prompt-and-generated +
  remaining decode budget < M, commit = extend still to prefill + (extend + max_new) of this pass's admissions. Decode OOM (one token
  per decode request does not fit): retract decode requests, fewest outputs first (ties longest prompt), keep one, evict 20 x remaining
  idle tokens per victim, set ratio = min(1, (sum outputs + 20 n) / (d n + 1)); the prompt stays cached, outputs are freed, the victim
  goes to the TAIL of the queue. The ratio decays by (init - min) / 600 per decode iteration without retraction, resets when idle.
* Metrics: hit rate / admissions / waits are those of the FIRST admission of a turn; re-admissions are counted separately
  (n_readmit, recompute_tokens). Only fcfs / lpm / lpm_fallback ordering, no TTL / PEEK protection.
* Amendment 2 (stage 3, before any registered run):
  - ``victim_kv_eviction`` ("tail", the registered rule; "whole" = the stage-1 rule kept as a sensitivity). The cached KV of a preempted /
    retracted request is evicted tail-first and only as far as the memory deficit requires; every other idle session is still evicted
    whole. In stage 1 the victim was evicted whole like any idle session, which destroyed it in almost every case (review finding F2).
    A victim's entry keeps the LRU position it was given at the preemption (MRU end): older idle sessions are evicted first. This favours
    retention (SGLang would place a retracted prompt by its older last-access time), so "tail" and "whole" bracket the real systems.
  - ``ondemand_admission`` ("full_isl" registered | "first_chunk" sensitivity, review finding F4).
  - thrash counters: ``max_preempt_per_turn``, ``n_turns_preempted``, ``n_turns_preempted_ge3``; window columns ``recompute_processed``
    (prefill tokens processed for re-admitted requests), ``lost_prefill`` (admitted prefill tokens discarded unprocessed) and
    ``preempt_max_turn`` (review finding F3). ``recompute_tokens`` stays the re-admission DEMAND (tokens a re-admission asks for).

Iteration batching modes (``EngineParams.batching``; ``mixed`` = everything above, the default, bit-identical to the engine before this option)
------------------------------------------------------------------------------------------------------------------------------------------
* ``mixed`` (default). Every iteration advances ALL running decode sequences by one token and carries up to ``prefill_chunk_budget`` prefill
  tokens (chunked prefill piggy-backed on the decode batch); the shared iteration-time formula at the top of this docstring applies.
* ``separate_prefill_priority`` (SGLang's default scheduler, ``enable_mixed_chunk=False``; scheduler.py ``get_next_batch_to_run``: "run prefill
  first if possible"). Each iteration is EITHER a prefill iteration OR a decode iteration, never both:

  - At every iteration boundary the admission pass runs first (when the state changed, as before). If it leaves a prefill batch to run (a
    request was admitted now, or a chunked prefill is in progress, i.e. ``Engine.prefill`` is non-empty) the iteration is a PREFILL iteration:
    the FIFO chunk hand-out of ``prefill_chunk_budget`` NEW tokens over the admitted-but-unfinished requests (SGLang subtracts the running decode
    batch from the chunk budget only in mixed mode, so the budget is the full ``prefill_chunk_budget`` here). The decode sequences do NOT
    advance (no token, no context growth, ``G`` unchanged); a request whose last chunk runs emits its first token in that iteration and then
    joins the decode set with context prompt + 1, exactly as in mixed mode. Prefill has priority: while requests can be admitted decode starves.
  - Otherwise, if any sequence is decoding, the iteration is a DECODE iteration: every decode sequence advances one token. The closed-form
    batching of pure-decode runs (section "Iteration batching") is still EXACT, because the composition of a decode run is fixed between
    events and its iteration time is linear in the iteration index; it only uses the decode cost terms below (tested against the unbatched engine).
  - Iteration times::

        tau_prefill = prefill_iter_fixed_s + prefill_per_token_s * (new prefill tokens) + prefill_attn_s * sum_{chunks} new_i * ctx_i
        tau_decode  = decode_iter_fixed_s + max(decode_iter_floor_s, decode_per_seq_s * n_decode)
                      + decode_attn_s * sum_{decode seqs} ctx_i / attn_ctx_norm

    ``prefill_attn_s`` and ``decode_attn_s`` are the existing keys. The other five are OPTIONAL and fall back to the shared keys when absent:
    prefill_iter_fixed_s <- iter_fixed_s, prefill_per_token_s <- per_token_s, decode_iter_fixed_s <- iter_fixed_s, decode_iter_floor_s <-
    iter_floor_s, decode_per_seq_s <- per_token_s. There is deliberately NO floor on a prefill iteration (the floor models the weight-read time
    of a small decode batch; a prefill iteration of a few tokens is not modelled separately). In ``mixed`` mode the five keys are ignored.
  - Supported with ``full_reserve`` and ``ratio_reserve`` (the SGLang-like allocation mode). ``ondemand_preempt`` (vLLM-like) is refused: vLLM's
    chunked-prefill scheduler is mixed by construction and a separate-iteration vLLM would be a different system.
  - ``ratio_reserve`` ordering (as in SGLang): the admission pass first; then, if a prefill iteration runs, only its chunks are allocated (decode
    sequences allocate nothing, the new-token ratio does not decay); if a decode iteration runs, the decode-OOM check / retraction and the ratio
    decay happen there (``update_running_batch``). In mixed mode the running loop (retraction) comes before the waiting loop instead.
  - Known gap (also present in mixed mode): the pass is re-run only when the state changed; SGLang's ``batch_is_full`` flag has a similar effect
    after a failed admission, but a new arrival can be admitted by an LPM pass here while SGLang would not retry until a request finished.
  - Not modelled (source-read in SGLang's scheduler.py / schedule_policy.py, not measured): ``max_prefill_tokens`` (a second prefill budget that is
    charged the same new-token amount as the chunk budget, so it never binds while ``prefill_chunk_budget <= max_prefill_tokens``),
    ``prefill_max_requests``, the prefill / min-free-slots delayers, the page-size rounding of the budgets, and the overlap scheduler.
  - Extra statistics (``stats()``, only in this mode): n_prefill_iters, n_decode_iters, prefill_busy_s, decode_busy_s.
"""
from __future__ import annotations

import bisect
import heapq
import math
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterator, List, Optional, Set, Tuple

import numpy as np

from .eviction import select_victims
from .mechanisms import Mechanisms, aimd_step
from .metrics import Recorder
from .policies import Policy
from .workload import SessionSpecs, WorkloadParams

INF = math.inf

FULL_RESERVE = "full_reserve"
ONDEMAND_PREEMPT = "ondemand_preempt"
RATIO_RESERVE = "ratio_reserve"
ALLOC_MODES = (FULL_RESERVE, ONDEMAND_PREEMPT, RATIO_RESERVE)

MIXED = "mixed"
SEPARATE_PREFILL_PRIORITY = "separate_prefill_priority"
BATCHING_MODES = (MIXED, SEPARATE_PREFILL_PRIORITY)


def ondemand_admit_ok(held: float, total_tokens: int, watermark_tokens: int, M: float) -> bool:
    """vLLM-like waiting-loop test: the whole sequence (prompt + generated so far; never max_tokens) plus the watermark must fit next
    to the KV currently held by running requests (idle cached KV counts as free)."""
    return held + total_tokens + watermark_tokens <= M


def ratio_admit_ok(held: float, commit: float, offset: float, total_tokens: int, dec_budget: int, M: float, n_running: int) -> bool:
    """SGLang-like PrefillAdder test, strict: held + commit + offset + (prompt + generated) + min(max_new - generated, clip) < M.
    ``held`` includes the locked hit prefixes of earlier admissions of the pass; ``commit`` is the unscaled (extend + max_new) of earlier
    admissions of the pass plus the extend still to be allocated for in-progress prefills; ``offset`` is ratio x remaining decode tokens
    of the decode requests. Guard: if nothing is running, a request whose prompt + decode budget fits M alone is admitted."""
    return held + commit + offset + total_tokens + dec_budget < M or (n_running == 0 and total_tokens + dec_budget <= M)


def retraction_ratio(sum_generated: int, n_kept: int, max_new: int, retract_decode_steps: int) -> float:
    """New ratio after a retraction: min(1, (sum len(output_ids) + steps * n) / (sum max_new + 1)) over the KEPT requests."""
    return min(1.0, (sum_generated + retract_decode_steps * n_kept) / (max_new * n_kept + 1))


@dataclass(frozen=True)
class EngineParams:
    iter_fixed_s: float
    iter_floor_s: float
    per_token_s: float
    decode_attn_s: float
    attn_ctx_norm: float
    prefill_attn_s: float
    prefill_attn_ctx: str
    prefill_chunk_budget: int
    max_running_seqs: int
    kv_memory_tokens: float
    cache_enabled: bool
    skip_ahead: bool
    admission_limited_by_prefill_budget: bool
    batch_decode_iterations: bool
    free_kv_on_session_end: bool = True
    # ---- round 5: allocation mode (default full_reserve = rounds 1-4, bit-identical) -------------------------------------
    alloc_mode: str = "full_reserve"          # full_reserve | ondemand_preempt | ratio_reserve (see the module docstring)
    watermark_frac: float = 0.0               # ondemand_preempt: vLLM watermark (fraction of M), only while something runs
    sched_conservativeness: float = 1.0       # ratio_reserve (SGLang-like) constants, scout-reported, unverified
    init_new_token_ratio: float = 0.7
    min_new_token_ratio_factor: float = 0.14
    new_token_ratio_decay_steps: int = 600
    retract_decode_steps: int = 20
    clip_max_new_tokens_estimation: int = 4096
    retract_evict_headroom: bool = True       # ratio_reserve: evict retract_decode_steps x remaining idle tokens per victim
    # ---- round 5, amendment 2 (both inert in full_reserve) ---------------------------------------------------------------------
    victim_kv_eviction: str = "tail"          # "tail": a preempted / retracted request's cached KV is evicted tail-first, token by token,
    #                                           only as far as the memory deficit requires (vLLM frees a victim's blocks tail-first into
    #                                           an LRU free queue; SGLang evicts radix leaves). "whole": the stage-1 rule (the victim's
    #                                           session is evicted all-or-nothing like every idle session; rounds 1-4 / stage-1 behaviour)
    ondemand_admission: str = "full_isl"      # ondemand_preempt waiting-loop test: "full_isl" (registered; scout: scheduler_reserve_full_isl=True,
    #                                           the whole sequence must fit) | "first_chunk" (sensitivity: hit + first chunk must fit)
    # ---- iteration batching (see the module docstring, "Iteration batching modes"); the default reproduces the engine before this option -------
    batching: str = MIXED                     # "mixed" | "separate_prefill_priority" (SGLang default scheduler, enable_mixed_chunk=False)
    prefill_iter_fixed_s: Optional[float] = None   # the five optional per-iteration-type costs are used ONLY by separate_prefill_priority;
    prefill_per_token_s: Optional[float] = None    # None = fall back to the shared key (iter_fixed_s / per_token_s / iter_floor_s). The attention
    decode_iter_fixed_s: Optional[float] = None    # terms keep their shared keys: prefill_attn_s (prefill iterations), decode_attn_s (decode iterations).
    decode_iter_floor_s: Optional[float] = None
    decode_per_seq_s: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "EngineParams":
        p = cls(**d)
        if p.batching not in BATCHING_MODES:
            raise ValueError(f"batching must be one of {BATCHING_MODES}, got {p.batching!r}")
        if p.batching == SEPARATE_PREFILL_PRIORITY and p.alloc_mode == ONDEMAND_PREEMPT:
            raise ValueError("batching='separate_prefill_priority' is implemented for alloc_mode full_reserve and ratio_reserve only "
                             "(vLLM-like ondemand_preempt schedules mixed iterations by construction)")
        for k in ("prefill_iter_fixed_s", "prefill_per_token_s", "decode_iter_fixed_s", "decode_iter_floor_s", "decode_per_seq_s"):
            v = getattr(p, k)
            if v is not None and not (v >= 0.0):
                raise ValueError(f"{k} must be >= 0 (or absent), got {v!r}")
        if p.prefill_attn_ctx not in ("end", "mid"):
            raise ValueError("prefill_attn_ctx must be 'end' or 'mid'")
        if p.alloc_mode not in ALLOC_MODES:
            raise ValueError(f"alloc_mode must be one of {ALLOC_MODES}, got {p.alloc_mode!r}")
        if p.victim_kv_eviction not in ("tail", "whole"):
            raise ValueError(f"victim_kv_eviction must be 'tail' or 'whole', got {p.victim_kv_eviction!r}")
        if p.ondemand_admission not in ("full_isl", "first_chunk"):
            raise ValueError(f"ondemand_admission must be 'full_isl' or 'first_chunk', got {p.ondemand_admission!r}")
        return p


class Request:
    """One turn of one session, from queue entry to last decode token."""
    __slots__ = ("rid", "sid", "turn", "qtime", "ready", "prompt", "end", "alive", "mark",
                 "pos", "rem", "offs", "done_g", "hit", "gen", "g_enter", "gone", "resumed", "npre")

    def __init__(self, rid: int, sid: int, turn: int, qtime: float, ready: float, prompt: int, end: int):
        self.rid = rid
        self.sid = sid
        self.turn = turn
        self.qtime = qtime       # time it joined the engine waiting queue (FCFS key)
        self.ready = ready       # turn-ready time for latency (first turn: session arrival incl. gate wait)
        self.prompt = prompt     # P_t
        self.end = end           # E_t (reserved at admission)
        self.alive = True        # False once admitted (lazy deletion from the queue list)
        self.mark = -1           # pass id stamp used by policies
        self.pos = 0             # tokens currently in KV (prefix + prefilled so far)
        self.rem = 0             # prefill tokens still to process
        self.offs = 0            # decode: ctx_i = offs + G
        self.done_g = 0          # decode: finishes when G >= done_g
        self.hit = False
        # round 5 (allocation modes; inert in full_reserve): tokens generated so far (as of ``g_enter`` for a decoding request:
        # gen_now = gen + G - g_enter), global iteration at which it entered decode, True once it left the running set by
        # preemption / retraction (stale heap entries), True for a re-queued preempted / retracted request
        self.gen = 0
        self.g_enter = 0
        self.gone = False
        self.resumed = False
        self.npre = 0            # how many times this turn has been preempted / retracted so far (carried over to the re-queued request)


class Engine:
    def __init__(self, params: EngineParams, wl: WorkloadParams, specs: SessionSpecs, policy: Policy,
                 rec: Recorder, *, session_cap: Optional[int] = None, closed: bool = False,
                 stop_queue_above: Optional[int] = None, debug: bool = False,
                 mech: Optional[Mechanisms] = None, stop_backlog_above: Optional[int] = None,
                 stop_low_hit: Optional[Tuple[float, int]] = None,
                 evict_rng: Optional[np.random.Generator] = None):
        self.p = params
        self.wl = wl
        self.policy = policy
        self.rec = rec
        self.session_cap = session_cap
        self.closed = closed
        self.stop_q = stop_queue_above
        self.stop_backlog = stop_backlog_above
        self.stop_hit = stop_low_hit                  # (hit-rate threshold, consecutive complete windows)
        self._hit_streak = 0
        self._hit_win_checked = 0
        self.stop_reason = ""
        self.debug = debug
        self.mech = mech if mech is not None else Mechanisms()
        self._peek = self.mech.protect_queued          # None | "pin" | "rank"
        self._ttl = self.mech.ttl_s
        self._unpin = self.mech.ttl_unpin               # "idle" | "eager" | "eager_fit" (see mechanisms.py)
        self.aimd = self.mech.aimd
        self._evict_mode = self.mech.eviction            # "lru" (rounds 1-3 code path) | "random" | "mru_idle" (eviction.py)
        self._evict_rng = evict_rng
        if self._evict_mode == "random" and evict_rng is None:
            raise ValueError("eviction='random' needs evict_rng (a generator dedicated to eviction; eviction.eviction_rng)")
        self.last_victims: List[int] = []                # victims of the latest non-LRU eviction, in selection order
        self.M = float(params.kv_memory_tokens)
        max_end = wl.end_len(wl.max_turns)
        if self.M < max_end:
            raise ValueError(f"kv_memory_tokens={self.M} < largest possible request context {max_end}")

        # session tables
        self._n = len(specs)
        self._arr: List[float] = specs.arrival.tolist()
        self._nt: List[int] = specs.n_turns.tolist()
        self._toff: List[int] = specs.tool_off.tolist()
        self._tool: List[float] = specs.tool_flat.tolist()
        self._turn: List[int] = [0] * self._n
        self._arrived_t: List[float] = [0.0] * self._n
        self._next_idx = 0

        # clock / iteration state
        self.now = 0.0
        self.G = 0                         # global decode-iteration counter
        self.n_D = 0                       # decode sequences
        self.sum_off = 0                   # sum over decode seqs of (ctx_enter - G_enter)
        self._done_heap: List[Tuple[int, int, Request]] = []
        self.prefill: List[Request] = []   # admitted, prefill unfinished (FIFO)
        self._pending_done: List[Request] = []

        # memory
        self.idle: "OrderedDict[int, int]" = OrderedDict()   # sid -> resident KV tokens (LRU first)
        self.idle_sum = 0
        # protection bookkeeping (all empty/zero unless a mechanism is on); every membership change goes through
        # _refresh_prot so the two dicts are a pure function of (idle, _pin, _waiting, _released)
        self._hard: Dict[int, int] = {}            # sid -> tokens, never evictable
        self._soft: Dict[int, int] = {}            # sid -> tokens, evicted after all unprotected idle KV
        self._hard_sum = 0
        self._soft_sum = 0
        self._pin: Dict[int, Tuple[float, int]] = {}      # sid -> (expiry time, token) of active TTL pins
        self._pin_heap: List[Tuple[float, int, int]] = []  # (expiry, token, sid); stale entries skipped lazily
        self._pin_seq = 0
        self._released: Set[int] = set()           # queued sessions whose PEEK-pin protection the breaker released
        self._ended: set = set()           # sids whose KV stays idle after their last turn (free_kv_on_session_end=False)
        self.reserved = 0
        self.max_resident = 0              # max of reserved + idle_sum (must stay <= M)

        # queues
        self._q: List[Request] = []
        self._qh = 0
        self._waiting: Dict[int, Request] = {}   # sid -> live waiting request
        self.n_wait = 0
        self._gate: Deque[int] = deque()
        self.in_system = 0
        self._tool_heap: List[Tuple[float, int, int]] = []
        self._tool_seq = 0
        self._rid = 0
        self.pass_id = 0
        self.dirty = False
        self._first_blocked: Optional[Request] = None
        self._track_prog = bool(getattr(policy, "needs_program_order", False))
        self._wsorted: List[int] = []              # sids of live waiting requests, ascending (program order)
        # session cap / AIMD
        self.max_in_system = 0
        self.entries_over_cap = 0                  # entries into the system while in_system >= cap (must stay 0)
        self.cap_trace: List[Tuple[float, int]] = []
        self._next_tick = self.aimd.interval_s if self.aimd is not None else INF
        self._tk_adm = 0
        self._tk_hit = 0
        self.n_ticks = 0
        self.cap_min = session_cap
        self.cap_max = session_cap
        if session_cap is not None:
            self.cap_trace.append((0.0, int(session_cap)))
            rec.set_cap(0.0, int(session_cap))
        if self.aimd is not None and session_cap is None:
            raise ValueError("AIMD needs an initial session cap")

        # bookkeeping
        self.n_arrived = 0
        self.n_sessions_done = 0
        self.n_turns_done = 0
        self.n_admitted = 0
        self.n_hits = 0
        self.n_evictions = 0
        self.evicted_tokens = 0
        self.n_iterations = 0              # engine iterations simulated (batched runs count n)
        self.n_steps = 0                   # simulator steps (a batched run counts 1)
        self.n_passes = 0
        self.max_queue = 0
        self.max_gate = 0
        self.busy_s = 0.0
        self.stopped = False
        self.stop_time: Optional[float] = None
        self.max_queue_pre_stop = 0
        self.n_stall_breaks = 0
        self.n_released = 0
        self.n_eager_unpins = 0            # pins released by the eager-unpin rule (ttl_unpin != "idle")
        self.n_pins = 0
        self.n_pin_expired = 0
        self.n_soft_evictions = 0
        self.end_time = 0.0
        self.max_running = 0
        self.max_held_tokens = 0           # only tracked when debug
        self.processed_prefill_tokens = 0  # prefill tokens processed by iterations (all modes)
        self.trace: Optional[list] = None  # set to [] to record ("A", sid, turn, hit, t) / ("D", sid, turn, t); allocation modes also ("P", sid, turn, kv_kept, t) preemption / retraction and ("R", sid, turn, hit_tokens, new_tokens, t) re-admission

        # iteration batching. In ``mixed`` mode the decode cost terms ARE the shared keys, so the decode run below evaluates exactly the same floats
        # as the engine before the option existed (bit-identical); ``separate_prefill_priority`` resolves the optional per-type keys (module docstring).
        self._sep = params.batching == SEPARATE_PREFILL_PRIORITY
        self._dc_fixed = params.iter_fixed_s
        self._dc_floor = params.iter_floor_s
        self._dc_seq = params.per_token_s
        self._pf_fixed = params.iter_fixed_s
        self._pf_tok = params.per_token_s
        if self._sep:
            if params.decode_iter_fixed_s is not None:
                self._dc_fixed = params.decode_iter_fixed_s
            if params.decode_iter_floor_s is not None:
                self._dc_floor = params.decode_iter_floor_s
            if params.decode_per_seq_s is not None:
                self._dc_seq = params.decode_per_seq_s
            if params.prefill_iter_fixed_s is not None:
                self._pf_fixed = params.prefill_iter_fixed_s
            if params.prefill_per_token_s is not None:
                self._pf_tok = params.prefill_per_token_s
        self.n_prefill_iters = 0           # separate_prefill_priority only: prefill-only iterations (decode iterations = n_iterations - this)
        self.prefill_busy_s = 0.0          # separate_prefill_priority only: time spent in prefill iterations

        # round 5: allocation modes. Everything below is inert (never read) when alloc_mode == full_reserve.
        self._alloc = params.alloc_mode
        self._dyn = self._alloc != FULL_RESERVE
        if self._dyn:
            self._init_dyn()

    # ------------------------------------------------------------------ view for policies
    @property
    def n_waiting(self) -> int:
        return self.n_wait

    def fifo_iter(self) -> Iterator[Request]:
        q = self._q
        i = self._qh
        while i < len(q):
            r = q[i]
            i += 1
            if r.alive:
                yield r

    def waiting_by_program(self) -> Iterator[Request]:
        """Live waiting requests in ascending session id (= program arrival order). Snapshot at call time."""
        w = self._waiting
        for sid in list(self._wsorted):
            r = w.get(sid)
            if r is not None and r.alive:
                yield r

    def pinned_waiting(self) -> List[Request]:
        """Waiting requests whose session KV is TTL-pinned, ascending session id; stamps ``mark = pass_id``."""
        pid = self.pass_id
        w = self._waiting
        out = []
        for sid in sorted(self._pin):
            r = w.get(sid)
            if r is not None and r.alive:
                r.mark = pid
                out.append(r)
        return out

    def resident_waiting(self, skip_marked: bool = False) -> List[Request]:
        pid = self.pass_id
        waiting = self._waiting
        out = []
        for sid, kv in self.idle.items():
            r = waiting.get(sid)
            if r is not None and r.alive and not (skip_marked and r.mark == pid):
                out.append((-kv, r.qtime, r.rid, r))
        out.sort(key=lambda x: x[:3])
        res = []
        for item in out:
            item[3].mark = pid
            res.append(item[3])
        return res

    # ------------------------------------------------------------------ protection bookkeeping
    def _refresh_prot(self, sid: int) -> None:
        """Recompute the protection class of ``sid``'s idle KV from (idle, pins, queue, released) and update the
        two dicts and their sums. Single source of truth for protection."""
        kv = self.idle.get(sid)
        hard = soft = False
        if kv is not None and sid not in self._ended:
            if sid in self._pin:
                hard = True
            elif self._peek is not None and sid in self._waiting:
                if self._peek == "pin":
                    hard = sid not in self._released
                else:
                    soft = True
        ch = self._hard.get(sid)
        if hard:
            if ch != kv:
                self._hard_sum += kv - (ch or 0)
                self._hard[sid] = kv
        elif ch is not None:
            self._hard_sum -= ch
            del self._hard[sid]
        cs = self._soft.get(sid)
        if soft:
            if cs != kv:
                self._soft_sum += kv - (cs or 0)
                self._soft[sid] = kv
        elif cs is not None:
            self._soft_sum -= cs
            del self._soft[sid]

    def _drop_prot(self, sid: int) -> None:
        """``sid``'s idle KV is leaving ``idle`` (admitted or evicted): forget every protection record."""
        ch = self._hard.pop(sid, None)
        if ch is not None:
            self._hard_sum -= ch
        cs = self._soft.pop(sid, None)
        if cs is not None:
            self._soft_sum -= cs
        self._pin.pop(sid, None)
        self._released.discard(sid)

    def _pin_next_time(self) -> float:
        """Time of the next pending (valid) pin expiry, INF if none. Drops stale heap entries."""
        h = self._pin_heap
        pin = self._pin
        while h:
            exp, tok, sid = h[0]
            cur = pin.get(sid)
            if cur is not None and cur[1] == tok:
                return exp
            heapq.heappop(h)
        return INF

    def _expire_pin(self, now: float) -> None:
        """Process the earliest pending pin expiry (its time is <= now)."""
        exp, tok, sid = heapq.heappop(self._pin_heap)
        cur = self._pin.get(sid)
        if cur is None or cur[1] != tok:
            return
        if sid in self._waiting:
            return                      # next request already queued: the pin persists until it is admitted
        del self._pin[sid]
        self.n_pin_expired += 1
        self._refresh_prot(sid)
        if self.n_wait > 0:
            self.dirty = True           # memory that was blocked may now be reclaimable

    def _break_stall(self) -> bool:
        """Deadlock breaker (see module docstring). Returns True if protection was released."""
        blocked = self._first_blocked
        if blocked is None:
            return False
        own = blocked.sid
        M = self.M
        released = 0
        for sid in sorted(self._hard, reverse=True):
            if self.reserved + blocked.end + self._hard_sum - self._hard.get(own, 0) <= M:
                break
            if sid == own:
                continue
            self._pin.pop(sid, None)
            if self._peek == "pin" and sid in self._waiting:
                self._released.add(sid)
            self._refresh_prot(sid)
            released += 1
        if released == 0:
            return False
        self.n_stall_breaks += 1
        self.n_released += released
        self.dirty = True
        return True

    def _eager_unpin(self, req: Request) -> bool:
        """Continuum-style release (``ttl_unpin`` "eager" / "eager_fit"): ``req`` does not fit because of hard-protected
        KV of other sessions; release TTL pins of other sessions, latest program arrival (largest session id) first,
        until it fits or no pin is left. With "eager_fit" nothing is released unless that makes ``req`` fit. Returns
        True if at least one pin was released."""
        own = req.sid
        M = self.M
        hard = self._hard
        if self._unpin == "eager_fit":
            nonpin = sum(kv for sid, kv in hard.items() if sid != own and sid not in self._pin)
            if self.reserved + req.end + nonpin > M:
                return False
        released = 0
        for sid in sorted(self._pin, reverse=True):
            if self.reserved + req.end + self._hard_sum - hard.get(own, 0) <= M:
                break
            if sid == own:
                continue
            del self._pin[sid]
            self._refresh_prot(sid)
            released += 1
        if released:
            self.n_eager_unpins += released
        return released > 0

    def _evict(self, need: int) -> None:
        """Free at least ``need`` tokens of idle KV: unprotected LRU-first, then soft-protected LRU-first. Hard
        protection is never evicted (feasibility was checked by the caller). Rounds 1-3 behaviour (``lru``) is the code
        below; ``random`` / ``mru_idle`` (round 4) go through ``_evict_variant``."""
        if self._evict_mode != "lru":
            self._evict_variant(need)
            return
        idle = self.idle
        if not self._hard and not self._soft:
            while need > 0:
                sid2, kv2 = idle.popitem(last=False)
                if self._ended:
                    self._ended.discard(sid2)
                self.idle_sum -= kv2
                self.n_evictions += 1
                self.evicted_tokens += kv2
                need -= kv2
            return
        victims: List[int] = []
        got = 0
        hard, soft = self._hard, self._soft
        for sid2, kv2 in idle.items():
            if sid2 in hard or sid2 in soft:
                continue
            victims.append(sid2)
            got += kv2
            if got >= need:
                break
        if got < need:
            for sid2 in idle:
                if sid2 in soft:
                    victims.append(sid2)
                    got += idle[sid2]
                    self.n_soft_evictions += 1
                    if got >= need:
                        break
        if got < need:
            raise AssertionError("eviction short of memory: hard-protected KV blocks an admission that was "
                                 "declared feasible")
        for sid2 in victims:
            kv2 = idle.pop(sid2)
            self._drop_prot(sid2)
            if self._ended:
                self._ended.discard(sid2)
            self.idle_sum -= kv2
            self.n_evictions += 1
            self.evicted_tokens += kv2

    def _evict_variant(self, need: int) -> None:
        """Round-4 eviction rules (``random`` / ``mru_idle``): victims from ``eviction.select_victims`` among the idle KV
        that is not hard-protected (soft-protected KV only after all unprotected KV), whole sessions."""
        idle = self.idle
        victims, got, n_soft = select_victims(self._evict_mode, idle, need, self._hard, self._soft, self._evict_rng)
        if got < need:
            raise AssertionError("eviction short of memory: hard-protected KV blocks an admission that was "
                                 "declared feasible")
        self.n_soft_evictions += n_soft
        self.last_victims = victims
        for sid2 in victims:
            kv2 = idle.pop(sid2)
            self._drop_prot(sid2)
            if self._ended:
                self._ended.discard(sid2)
            self.idle_sum -= kv2
            self.n_evictions += 1
            self.evicted_tokens += kv2

    def _check_stop(self, t: float, prev_max: int, n_gate: int) -> None:
        if self.stopped:
            return
        if self.stop_q is not None and self.n_wait > self.stop_q:
            self.stop_reason = "queue"
        elif self.stop_backlog is not None and self.n_wait + n_gate > self.stop_backlog:
            self.stop_reason = "backlog"
        else:
            return
        self.stopped = True
        self.stop_time = t
        self.max_queue_pre_stop = prev_max

    def _check_hit_stop(self) -> None:
        """Stop when the hit rate has been < thresh in ``n`` consecutive complete metric windows (windows with no
        admission reset the streak). ``stop_time`` = start of the first window of the streak."""
        thr, n = self.stop_hit
        W = self.rec.w
        kw = int(self.now // W)
        rec = self.rec
        while self._hit_win_checked < kw:
            j = self._hit_win_checked
            self._hit_win_checked += 1
            adm = rec._admits[j] if j < len(rec._admits) else 0
            if adm > 0 and rec._hits[j] / adm < thr:
                self._hit_streak += 1
                if self._hit_streak >= n:
                    self.stopped = True
                    self.stop_reason = "hit"
                    self.stop_time = (j - n + 1) * W
                    self.max_queue_pre_stop = self.max_queue
                    return
            else:
                self._hit_streak = 0

    # ------------------------------------------------------------------ session lifecycle
    def _arrive(self, i: int, t: float) -> None:
        self.n_arrived += 1
        self._arrived_t[i] = t
        if self.session_cap is not None and self.in_system >= self.session_cap:
            self._gate.append(i)
            g = len(self._gate)
            if g > self.max_gate:
                self.max_gate = g
            self.rec.set_gate(t, g)
            if self.stop_backlog is not None:
                self._check_stop(t, self.max_queue, g)
        else:
            self._enter(i, t)

    def _enter(self, i: int, t: float) -> None:
        if self.session_cap is not None and self.in_system >= self.session_cap:
            self.entries_over_cap += 1
        self.in_system += 1
        if self.in_system > self.max_in_system:
            self.max_in_system = self.in_system
        self._turn[i] = 1
        self._enqueue_turn(i, t, self._arrived_t[i])

    def _enqueue_turn(self, sid: int, t: float, ready: float) -> None:
        turn = self._turn[sid]
        prompt = self.wl.prompt_len(turn)
        req = Request(self._rid, sid, turn, t, ready, prompt, prompt + self.wl.decode_tokens)
        self._rid += 1
        self._q.append(req)
        self._waiting[sid] = req
        self.n_wait += 1
        if self._track_prog:
            bisect.insort(self._wsorted, sid)
        if self._peek is not None:
            self._refresh_prot(sid)
        prev_max = self.max_queue
        if self.n_wait > self.max_queue:
            self.max_queue = self.n_wait
        self.rec.set_queue(t, self.n_wait)
        self.dirty = True
        if self.stop_q is not None or self.stop_backlog is not None:
            self._check_stop(t, prev_max, len(self._gate))

    def _process_exogenous(self, now: float) -> None:
        """Process, in time order, every event with time <= now: session arrivals, tool returns, TTL-pin expiries
        and AIMD ticks. Ties: arrival, then tool return, then pin expiry, then tick."""
        arr = self._arr
        n = self._n
        th = self._tool_heap
        track_pins = self._ttl is not None
        while not self.stopped:
            ta = arr[self._next_idx] if self._next_idx < n else INF
            tt = th[0][0] if th else INF
            tp = self._pin_next_time() if track_pins else INF
            tk = self._next_tick
            if ta <= tt and ta <= tp and ta <= tk:
                if ta > now:
                    return
                i = self._next_idx
                self._next_idx += 1
                self._arrive(i, ta)
            elif tt <= tp and tt <= tk:
                if tt > now:
                    return
                t, _, sid = heapq.heappop(th)
                self._enqueue_turn(sid, t, t)
            elif tp <= tk:
                if tp > now:
                    return
                self._expire_pin(tp)
            else:
                if tk > now:
                    return
                self._tick(tk)

    def _next_exogenous_time(self) -> float:
        """Next time the exogenous state can matter: arrival, tool return, AIMD tick, and (only while requests are
        waiting, since only then can it unblock an admission) the next pin expiry."""
        ta = self._arr[self._next_idx] if self._next_idx < self._n else INF
        tt = self._tool_heap[0][0] if self._tool_heap else INF
        t = ta if ta < tt else tt
        if self._next_tick < t:
            t = self._next_tick
        if self._ttl is not None and self.n_wait > 0:
            tp = self._pin_next_time()
            if tp < t:
                t = tp
        return t

    def _tick(self, tt: float) -> None:
        """AIMD controller step at nominal time ``tt``; the window is the interval since the previous tick."""
        a = self.aimd
        self.n_ticks += 1
        dn = self.n_admitted - self._tk_adm
        dh = self.n_hits - self._tk_hit
        self._tk_adm, self._tk_hit = self.n_admitted, self.n_hits
        hr = dh / dn if dn > 0 else float("nan")
        usage = (self.reserved + self.idle_sum) / self.M
        self._next_tick += a.interval_s
        new = aimd_step(int(self.session_cap), hr, usage, a)
        if new != self.session_cap:
            self.session_cap = new
            self.cap_trace.append((tt, new))
            self.rec.set_cap(tt, new)
            if new < self.cap_min:
                self.cap_min = new
            if new > self.cap_max:
                self.cap_max = new
        self._release_gate(tt)

    def _release_gate(self, t: float) -> None:
        moved = False
        while self._gate and self.in_system < self.session_cap:
            j = self._gate.popleft()
            moved = True
            self._enter(j, t)
        if moved:
            self.rec.set_gate(t, len(self._gate))

    def _finish_request(self, req: Request, t: float) -> None:
        if self._dyn:
            self.held -= req.end                    # ctx at completion == end (see the KV accounting note)
            del self._run_order[req.rid]
        else:
            self.reserved -= req.end
        self.n_turns_done += 1
        self.rec.on_turn_done(t, t - req.ready)
        sid = req.sid
        if self.trace is not None:
            self.trace.append(("D", sid, req.turn, t))
        self.dirty = True
        if req.turn < self._nt[sid]:
            if self.p.cache_enabled:
                self.idle[sid] = req.end            # most-recently-used end of the LRU
                self.idle_sum += req.end
                if self._ttl is not None:
                    self._pin_seq += 1
                    exp = t + self._ttl
                    self._pin[sid] = (exp, self._pin_seq)
                    heapq.heappush(self._pin_heap, (exp, self._pin_seq, sid))
                    self.n_pins += 1
                if self._ttl is not None or self._peek is not None:
                    self._released.discard(sid)
                    self._refresh_prot(sid)
            z = self._tool[self._toff[sid] + req.turn - 1]
            self._turn[sid] = req.turn + 1
            self._tool_seq += 1
            heapq.heappush(self._tool_heap, (t + z, self._tool_seq, sid))
        else:
            if self.p.cache_enabled and not self.p.free_kv_on_session_end:
                self.idle[sid] = req.end            # dead KV: stays evictable at the MRU end (no oracle)
                self.idle_sum += req.end
                self._ended.add(sid)
            self.n_sessions_done += 1
            self.in_system -= 1
            self.rec.on_session_done(t)
            if self._gate and self.in_system < self.session_cap:
                j = self._gate.popleft()
                self.rec.set_gate(t, len(self._gate))
                self._enter(j, t)
            if self.closed and self._next_idx < self._n:
                i = self._next_idx
                self._next_idx += 1
                self._arrive(i, t)

    def _process_done(self) -> None:
        if self._pending_done:
            pend = self._pending_done
            self._pending_done = []
            t = self.now
            for req in pend:
                self._finish_request(req, t)

    # ------------------------------------------------------------------ admission
    def _admit(self, req: Request, now: float) -> int:
        """Admit ``req`` (memory feasibility already checked). Returns its new prefill tokens."""
        sid = req.sid
        kv = self.idle.pop(sid, None)
        if kv is not None:
            self.idle_sum -= kv
            if self._ttl is not None or self._peek is not None:
                self._drop_prot(sid)
            req.hit = True
            req.pos = kv
            new = req.prompt - kv
            if new != self.wl.new_prompt_tokens:
                raise AssertionError(f"hit prefix {kv} inconsistent with prompt {req.prompt}")
        else:
            req.hit = False
            req.pos = 0
            new = req.prompt
        need = self.reserved + req.end + self.idle_sum - self.M
        if need > 0:
            n_ev0 = self.n_evictions
            self._evict(need)
            self.rec.on_evict(now, self.n_evictions - n_ev0)
        self.reserved += req.end
        used = self.reserved + self.idle_sum
        if used > self.max_resident:
            self.max_resident = used
        req.alive = False
        del self._waiting[sid]
        if self._track_prog:
            del self._wsorted[bisect.bisect_left(self._wsorted, sid)]
        self.n_wait -= 1
        self.rec.set_queue(now, self.n_wait)
        req.rem = new
        self.prefill.append(req)
        self.n_admitted += 1
        if req.hit:
            self.n_hits += 1
        first = req.turn == 1
        if self.trace is not None:
            self.trace.append(("A", sid, req.turn, req.hit, now))
        self.rec.on_admit(now, req.hit, first, (now - self._arrived_t[sid]) if first else 0.0)
        return new

    def _schedule_pass(self) -> None:
        self.dirty = False
        if self.n_wait == 0:
            return
        self.n_passes += 1
        self.pass_id += 1
        self._first_blocked = None
        p = self.p
        n_run = self.n_D + len(self.prefill)
        max_seqs = p.max_running_seqs
        if p.admission_limited_by_prefill_budget:
            pending = 0
            for r in self.prefill:
                pending += r.rem
            budget_left = p.prefill_chunk_budget - pending
        else:
            budget_left = INF
        M = self.M
        skip = p.skip_ahead
        limited = p.admission_limited_by_prefill_budget
        for req in self.policy.candidates(self, self.now):
            if n_run >= max_seqs or (limited and budget_left <= 0):
                break
            if self._hard_sum:
                # hard-protected idle KV of OTHER sessions cannot be evicted to make room
                need_ok = self.reserved + req.end + self._hard_sum - self._hard.get(req.sid, 0) <= M
                if not need_ok and self._unpin != "idle" and self._pin and self._eager_unpin(req):
                    need_ok = (self.reserved + req.end + self._hard_sum - self._hard.get(req.sid, 0) <= M)
            else:
                need_ok = self.reserved + req.end <= M
            if not need_ok:
                if self._first_blocked is None:
                    self._first_blocked = req
                if skip:
                    continue
                break
            new = self._admit(req, self.now)
            n_run += 1
            if limited:
                budget_left -= new
        if n_run > self.max_running:
            self.max_running = n_run
        self._compact_queue()

    def _compact_queue(self) -> None:
        q = self._q
        h = self._qh
        n = len(q)
        while h < n and not q[h].alive:
            h += 1
        if h > 4096 and h * 2 > n:
            del q[:h]
            h = 0
        self._qh = h

    # ------------------------------------------------------------------ iterations
    def _collect_done_decodes(self) -> None:
        heap = self._done_heap
        G = self.G
        while heap and heap[0][0] <= G:
            _, _, req = heapq.heappop(heap)
            if req.gone:
                continue                            # preempted / retracted while decoding (round 5); already removed from n_D
            self.n_D -= 1
            self.sum_off -= req.offs
            if self._dyn:
                self._sum_gc -= req.gen - req.g_enter
            self._pending_done.append(req)

    def _iterate_with_prefill(self, planned: Optional[List[Tuple[Request, int]]] = None) -> None:
        """One iteration with prefill chunks. ``planned`` (round 5, allocation modes) is the chunk list that the memory model
        has already allocated; ``None`` (full_reserve) hands the chunk budget out FIFO as in rounds 1-4."""
        p = self.p
        chunks: List[Tuple[Request, int]] = []
        ntok = 0
        attn = 0.0
        mid = p.prefill_attn_ctx == "mid"
        if planned is None:
            budget = p.prefill_chunk_budget
            for req in self.prefill:
                if budget <= 0:
                    break
                c = req.rem if req.rem < budget else budget
                chunks.append((req, c))
                budget -= c
                ntok += c
                attn += c * ((req.pos + 0.5 * c) if mid else (req.pos + c))
        else:
            for req, c in planned:
                chunks.append((req, c))
                ntok += c
                attn += c * ((req.pos + 0.5 * c) if mid else (req.pos + c))
        n_D = self.n_D
        if self._sep:
            # prefill-only iteration (batching=separate_prefill_priority): the decode sequences do not take part and do not advance
            tau = self._pf_fixed + self._pf_tok * ntok + p.prefill_attn_s * attn
        else:
            sumctx = self.sum_off + n_D * self.G
            dec_tok = ntok + n_D
            tok_t = p.per_token_s * dec_tok
            if tok_t < p.iter_floor_s:
                tok_t = p.iter_floor_s
            tau = p.iter_fixed_s + tok_t + p.decode_attn_s * sumctx / p.attn_ctx_norm + p.prefill_attn_s * attn
        t0 = self.now
        self.now = t0 + tau
        self.busy_s += tau
        self.rec.add_busy(t0, self.now)
        self.rec.add_prefill_tokens(self.now, ntok)
        self.processed_prefill_tokens += ntok
        if self._dyn:
            rp = 0
            for req, c in chunks:
                if req.resumed:
                    rp += c
            if rp:
                self.recompute_processed_tokens += rp
                self.rec.add_recompute_processed(self.now, rp)
        if self._sep:
            self.n_prefill_iters += 1
            self.prefill_busy_s += tau
        else:
            self.G += 1
        self.n_iterations += 1
        self.n_steps += 1
        if not self._sep:
            if self._dyn and n_D:
                self._decay_ratio(1)
            self._collect_done_decodes()      # decode members of this iteration (before new members join)
        d = self.wl.decode_tokens
        G = self.G
        finished = False
        for req, c in chunks:
            req.pos += c
            req.rem -= c
            if req.rem == 0:
                finished = True
        if finished:
            keep = []
            for req in self.prefill:
                if req.rem > 0:
                    keep.append(req)
                    continue
                # prefill done in this iteration: first token (number gen + 1) emitted now; gen == 0 in full_reserve
                rem_dec = d - 1 - req.gen
                if rem_dec <= 0:
                    self._pending_done.append(req)
                else:
                    req.offs = (req.pos + 1) - G
                    req.done_g = G + rem_dec
                    self.sum_off += req.offs
                    self.n_D += 1
                    if self._dyn:
                        req.gen += 1
                        req.g_enter = G
                        self._sum_gc += req.gen - req.g_enter
                    heapq.heappush(self._done_heap, (req.done_g, req.rid, req))
            self.prefill = keep
        self.dirty = True       # prefill budget / running slots changed

    def _iterate_decode(self, t_cap: float, n_cap: Optional[int] = None) -> None:
        """A run of pure-decode iterations. ``n_cap`` (round 5): at most this many iterations (memory for the decode tokens)."""
        p = self.p
        if self._dyn:
            h = self._done_heap
            while h and h[0][2].gone:                  # entries of preempted / retracted requests
                heapq.heappop(h)
        n_D = self.n_D
        c0 = self._dc_fixed + max(self._dc_floor, self._dc_seq * n_D)
        a = p.decode_attn_s / p.attn_ctx_norm
        b = a * n_D
        tau0 = c0 + a * (self.sum_off + n_D * self.G)
        n_done = self._done_heap[0][0] - self.G
        n = 1
        if p.batch_decode_iterations and n_done > 1:
            delta = t_cap - self.now
            if delta > tau0:
                if b > 0.0:
                    h = tau0 - 0.5 * b
                    n_ev = int(math.ceil((-h + math.sqrt(h * h + 2.0 * b * delta)) / b))
                else:
                    n_ev = int(math.ceil(delta / tau0))
                if n_ev < 1:
                    n_ev = 1
                # float-safe fix-ups: smallest n with S_n >= delta
                while n_ev > 1 and (n_ev - 1) * tau0 + 0.5 * b * (n_ev - 1) * (n_ev - 2) >= delta:
                    n_ev -= 1
                while n_ev * tau0 + 0.5 * b * n_ev * (n_ev - 1) < delta:
                    n_ev += 1
                n = n_ev if n_ev < n_done else n_done
        if n_cap is not None and n > n_cap:
            n = n_cap
        S = n * tau0 + 0.5 * b * n * (n - 1)
        t0 = self.now
        self.now = t0 + S
        self.busy_s += S
        self.rec.add_busy(t0, self.now)
        self.G += n
        self.n_iterations += n
        self.n_steps += 1
        if self._dyn:
            self._after_decode_run(n, n_D)
        self._collect_done_decodes()

    # ------------------------------------------------------------------ main loop
    def run(self, horizon: float) -> None:
        if self._dyn:
            self._run_dyn(horizon)
            return
        always_pass = self.policy.time_dependent
        mem_on = self.rec.mem_on
        while self.now < horizon and not self.stopped:
            self._process_exogenous(self.now)
            if self.stopped:
                break
            self._process_done()
            if (self.dirty or (always_pass and self.n_wait > 0)) and not self.stopped:
                self._schedule_pass()
            if self.debug:
                self.check_invariants()
            if mem_on:
                self.rec.set_mem(self.now, self.reserved, self.idle_sum, self._hard_sum)
            if self.stop_hit is not None:
                self._check_hit_stop()
                if self.stopped:
                    break
            if self.n_D == 0 and not self.prefill:
                if self.n_wait > 0:
                    if not self._hard:
                        raise RuntimeError("engine idle with waiting requests and no admissible request (deadlock)")
                    if self._pin_next_time() == INF:        # nothing can free memory by waiting
                        if not self._break_stall():
                            raise RuntimeError("engine idle, blocked by protected KV and the breaker found nothing "
                                               "to release")
                        continue
                nxt = self._next_exogenous_time()
                if nxt >= horizon:
                    self.now = horizon
                    break
                self.now = nxt
                continue
            if self.prefill:
                self._iterate_with_prefill()
            else:
                nxt = self._next_exogenous_time()
                if always_pass and self.n_wait > 0:        # never batch across an aging-threshold crossing
                    nt = self.policy.next_time_event(self, self.now)
                    if nt < nxt:
                        nxt = nt
                self._iterate_decode(nxt if nxt < horizon else horizon)
        if self.stopped and self.stop_reason == "hit":
            self.end_time = self.now          # windows up to now are complete; stop_time is the streak onset
        else:
            self.end_time = self.stop_time if (self.stopped and self.stop_time is not None) else horizon
        self.rec.set_queue(self.end_time, self.n_wait)
        self.rec.set_gate(self.end_time, len(self._gate))

    # ------------------------------------------------------------------ round 5: dynamic allocation modes
    # Everything from here to ``introspection`` is used only when ``alloc_mode != full_reserve``.
    def _init_dyn(self) -> None:
        p = self.p
        if self.mech.any_protection:
            raise ValueError(f"alloc_mode={self._alloc} does not support TTL / PEEK protection")
        if self._sep and self._alloc == ONDEMAND_PREEMPT:
            raise ValueError("batching='separate_prefill_priority' is not implemented for alloc_mode='ondemand_preempt'")
        if self.policy.name not in ("fcfs", "lpm", "lpm_fallback"):
            raise ValueError(f"alloc_mode={self._alloc} supports the ordering policies fcfs, lpm and lpm_fallback only, "
                             f"got {self.policy.name!r}")
        self._victim_tail = p.victim_kv_eviction == "tail"
        if self._victim_tail and self._evict_mode != "lru":
            raise ValueError("victim_kv_eviction='tail' is implemented for LRU eviction only; pass victim_kv_eviction='whole' for "
                             f"eviction={self._evict_mode!r}")
        self._first_chunk_adm = p.ondemand_admission == "first_chunk"
        if self.wl.decode_tokens < 1:
            raise ValueError("alloc modes need decode_tokens >= 1")
        if self._alloc == RATIO_RESERVE and self.wl.decode_tokens > p.clip_max_new_tokens_estimation:
            raise ValueError("ratio_reserve: decode_tokens above clip_max_new_tokens_estimation is not modelled")
        if p.new_token_ratio_decay_steps <= 0 or not (0.0 < p.init_new_token_ratio * p.sched_conservativeness):
            raise ValueError("bad new_token_ratio parameters")
        self.held = 0                                   # KV tokens owned by running requests (see the module docstring)
        self._run_order: "OrderedDict[int, Request]" = OrderedDict()   # rid -> running request, in ADMISSION order
        self._sum_gc = 0                                # sum over decode requests of (gen - g_enter); sum gen_now = _sum_gc + n_D * G
        self._step_chunks: List[Tuple[Request, int]] = []   # prefill chunks (already allocated) of the coming iteration
        self._step_ntok = 0
        self._chunk_left = 0
        init = min(p.init_new_token_ratio * p.sched_conservativeness, 1.0)
        self._ratio_init = init
        self._ratio_min = init * p.min_new_token_ratio_factor
        self._ratio_decay = (init - self._ratio_min) / p.new_token_ratio_decay_steps
        self.new_token_ratio = init
        self._retracted_turn = False
        self._stall_guard = 0
        # counters
        self.n_preempt = 0                              # running requests thrown back to the waiting queue (preempted / retracted)
        self.n_fallback_retract = 0                     # ratio_reserve: prefilling request retracted (not an SGLang path)
        self.n_readmit = 0
        self.n_readmit_with_kv = 0                      # re-admissions that found surviving KV
        self.recompute_tokens = 0                       # prefill tokens spent at re-admissions
        self.lost_prefill_tokens = 0                    # prefill tokens admitted but never processed (victim preempted mid-prefill)
        self.recompute_processed_tokens = 0             # prefill tokens PROCESSED for re-admitted requests (recompute work actually done)
        self.max_preempt_per_turn = 0                   # most preemptions / retractions suffered by one turn (thrash detector)
        self.n_turns_preempted = 0                      # turns preempted at least once
        self.n_turns_preempted_ge3 = 0                  # turns preempted at least three times
        self.n_partial_evictions = 0                    # tail-first partial evictions of a preempted request's cached KV
        self.admitted_prefill_tokens = 0                # sum of `new` over all admissions (first + re-admissions)
        self.ratio_min_seen = init

    def _make_room(self) -> None:
        """After an allocation: evict idle KV (configured eviction rule) until held + idle <= M; track the peak."""
        deficit = self.held + self.idle_sum - self.M
        if deficit > 0:
            n0 = self.n_evictions
            self._evict_dyn(deficit)
            self.rec.on_evict(self.now, self.n_evictions - n0)
        used = self.held + self.idle_sum
        if used > self.max_resident:
            self.max_resident = used

    def _evict_dyn(self, need: int) -> None:
        """Allocation modes: free ``need`` tokens of idle KV. ``victim_kv_eviction='whole'``: the configured whole-session rule."""
        if self._victim_tail:
            self._evict_tail(need)
        else:
            self._evict(need)

    def _evict_tail(self, need: int) -> None:
        """LRU eviction of ``need`` tokens in which the entry of a PREEMPTED / RETRACTED request (its session has a live re-queued
        request with ``resumed``) is evicted tail-first, token by token, only as far as the deficit requires (amendment 2). Every other
        idle session is evicted whole (rounds 1-4 simplification). LRU order is unchanged: a victim's entry sits where it was put (MRU
        end at the time of the preemption), so older idle sessions go first and a victim is trimmed only when they do not cover ``need``."""
        idle = self.idle
        waiting = self._waiting
        need = int(math.ceil(need))                       # integer tokens (M is stored as a float)
        while need > 0:
            if not idle:
                raise AssertionError("eviction short of memory: nothing left to evict")
            sid2 = next(iter(idle))
            kv2 = idle[sid2]
            if kv2 > need:
                w = waiting.get(sid2)
                if w is not None and w.resumed:
                    idle[sid2] = kv2 - need                # keep the head of the sequence, drop its last ``need`` tokens
                    self.idle_sum -= need
                    self.evicted_tokens += need            # token-additive; ``n_evictions`` counts only entries removed entirely
                    self.n_partial_evictions += 1
                    return
            del idle[sid2]
            if self._ended:
                self._ended.discard(sid2)
            self.idle_sum -= kv2
            self.n_evictions += 1
            self.evicted_tokens += kv2
            need -= kv2

    def _decay_ratio(self, k: int) -> None:
        """``k`` decode steps without retraction: ratio = max(ratio - k * decay, min_ratio) (ratio_reserve only)."""
        if self._alloc != RATIO_RESERVE or self._retracted_turn:
            return
        r = self.new_token_ratio - k * self._ratio_decay
        self.new_token_ratio = r if r > self._ratio_min else self._ratio_min
        if self.new_token_ratio < self.ratio_min_seen:
            self.ratio_min_seen = self.new_token_ratio

    def _after_decode_run(self, n: int, n_D: int) -> None:
        """Bookkeeping of a batched pure-decode run of ``n`` iterations with ``n_D`` decode requests: the first iteration's
        tokens were allocated in the running loop, the remaining n - 1 are allocated now (the run was capped so they fit)."""
        if n > 1:
            self.held += (n - 1) * n_D
            self._make_room()
        self._decay_ratio(n)

    # ---- leaving the running set
    def _leave_running(self, v: Request) -> int:
        """Remove ``v`` from the running structures and return the KV tokens it owns. Does not touch held / idle."""
        if v.rem > 0:                                   # prefilling
            self.prefill.remove(v)
            kv = v.pos
            self.lost_prefill_tokens += v.rem
            self.rec.on_lost(self.now, v.rem)
        else:                                           # decoding: ctx = offs + G, generated so far = gen + G - g_enter
            G = self.G
            kv = v.offs + G
            self.n_D -= 1
            self.sum_off -= v.offs
            self._sum_gc -= v.gen - v.g_enter
            v.gen += G - v.g_enter
            v.g_enter = G
        v.gone = True
        self._run_order.pop(v.rid, None)
        return kv

    def _requeue(self, v: Request, kv_idle: int, front: bool) -> None:
        """Put a preempted / retracted request back into the waiting queue (a NEW Request object: the old one is a dead slot of
        the queue list). ``kv_idle`` tokens of its KV stay cached as idle KV of its session at the MRU end."""
        sid = v.sid
        if self.p.cache_enabled and kv_idle > 0:
            if sid in self.idle:
                raise AssertionError(f"session {sid} already has idle KV")
            self.idle[sid] = kv_idle
            self.idle_sum += kv_idle
        new = Request(self._rid, sid, v.turn, v.qtime, v.ready, v.prompt, v.end)
        self._rid += 1
        new.gen = v.gen
        new.resumed = True
        new.npre = v.npre + 1
        if new.npre == 1:
            self.n_turns_preempted += 1
        elif new.npre == 3:
            self.n_turns_preempted_ge3 += 1
        if new.npre > self.max_preempt_per_turn:
            self.max_preempt_per_turn = new.npre
        q = self._q
        if front:
            if self._qh > 0:
                self._qh -= 1
                q[self._qh] = new
            else:
                q.insert(0, new)
        else:
            q.append(new)
        self._waiting[sid] = new
        self.n_wait += 1
        prev_max = self.max_queue
        if self.n_wait > self.max_queue:
            self.max_queue = self.n_wait
        self.rec.set_queue(self.now, self.n_wait)
        self.dirty = True
        self.n_preempt += 1
        self.rec.on_preempt(self.now, new.npre)
        if self.trace is not None:
            self.trace.append(("P", sid, v.turn, kv_idle, self.now))
        if self.stop_q is not None or self.stop_backlog is not None:
            self._check_stop(self.now, prev_max, len(self._gate))

    # ---- chunk planning
    def _plan_chunks(self) -> Tuple[List[Tuple[Request, int]], int, int]:
        """FIFO hand-out of ``prefill_chunk_budget`` over the prefilling requests: (chunks, tokens, #chunks completing a prompt)."""
        budget = self.p.prefill_chunk_budget
        chunks: List[Tuple[Request, int]] = []
        ntok = 0
        comp = 0
        for req in self.prefill:
            if budget <= 0:
                break
            c = req.rem if req.rem < budget else budget
            chunks.append((req, c))
            budget -= c
            ntok += c
            if c == req.rem:
                comp += 1
        return chunks, ntok, comp

    # ---- running loop
    def _running_step_ondemand(self) -> bool:
        """vLLM-like running loop. Allocates the coming iteration for the requests that are already running (decode: one token
        each; prefill: the FIFO chunks, +1 token for a chunk that completes its prompt). If that does not fit, preempt the most
        recently admitted running requests (prefilling or decoding), one at a time, until the survivors' (held + demand) fit.
        Returns True iff something was preempted."""
        M = self.M
        chunks, ntok, comp = self._plan_chunks()
        demand = ntok + comp + self.n_D
        preempted = False
        if self.held + demand > M:
            preempted = True
            total = self.held + demand
            chunk_of = {r.rid: c for r, c in chunks}
            G = self.G
            while total > M:
                if not self._run_order:
                    raise AssertionError("memory too small for a single running request")
                rid, v = self._run_order.popitem(last=True)          # newest admission
                if v.rem > 0:
                    c = chunk_of.get(rid, 0)
                    need = c + (1 if (c > 0 and c == v.rem) else 0)
                    h = v.pos
                else:
                    need = 1
                    h = v.offs + G
                total -= h + need
                kv = self._leave_running(v)
                assert kv == h
                self.held -= kv
                self._requeue(v, kv, front=True)
            chunks = [(r, c) for (r, c) in chunks if not r.gone]
            ntok = sum(c for _, c in chunks)
            comp = sum(1 for r, c in chunks if c == r.rem)
            demand = ntok + comp + self.n_D
            assert self.held + demand == total, "preemption bookkeeping"
        self.held += demand
        self._make_room()
        self._step_chunks = chunks
        self._step_ntok = ntok
        return preempted

    def _pick_retract_victim(self) -> Request:
        """SGLang retract_decode order: sort key (len(output_ids), -len(origin_input_ids)) descending, pop from the end =
        fewest outputs first, ties longest prompt; remaining ties: newest request."""
        G = self.G
        best: Optional[Request] = None
        bk = None
        for (_, rid, r) in self._done_heap:
            if r.gone:
                continue
            key = (r.gen + G - r.g_enter, -r.prompt, -rid)
            if bk is None or key < bk:
                best, bk = r, key
        assert best is not None
        return best

    def _newest_prefilling(self) -> Optional[Request]:
        for v in reversed(self._run_order.values()):
            if v.rem > 0:
                return v
        return None

    def _running_step_ratio(self) -> bool:
        """SGLang-like decode-OOM check. One new token per decode request must fit (idle cache counts as evictable). If not,
        retract decode requests (fewest outputs first) until it does, keeping at least one, and re-estimate the ratio.
        Returns True iff something was retracted."""
        M = self.M
        p = self.p
        retracted = False
        if self.held + self.n_D > M:
            retracted = True
            R = p.retract_decode_steps
            while self.held + self.n_D > M and self.n_D > 1:
                v = self._pick_retract_victim()
                kv = self._leave_running(v)
                self.held -= kv
                self._requeue(v, v.prompt, front=False)          # prompt stays cached; outputs are freed
                if p.retract_evict_headroom and self.idle_sum > 0:
                    need = min(R * self.n_D, self.idle_sum)
                    if need > 0:
                        n0 = self.n_evictions
                        self._evict_dyn(need)
                        self.rec.on_evict(self.now, self.n_evictions - n0)
            while self.held + self.n_D > M:
                v = self._newest_prefilling()
                if v is None:
                    raise AssertionError("memory too small for a single decoding request")
                kv = self._leave_running(v)
                self.held -= kv
                self._requeue(v, kv, front=False)
                self.n_fallback_retract += 1
            n = self.n_D
            d = self.wl.decode_tokens
            sum_gen = self._sum_gc + n * self.G
            self.new_token_ratio = retraction_ratio(sum_gen, n, d, R)
            if self.new_token_ratio < self.ratio_min_seen:
                self.ratio_min_seen = self.new_token_ratio
        self._retracted_turn = retracted
        self.held += self.n_D
        self._make_room()
        return retracted

    def _plan_chunks_ratio(self) -> None:
        """ratio_reserve: hand the chunk budget out FIFO but only up to the free memory (a stalled prefill waits)."""
        free = self.M - self.held
        if free != INF:
            free = int(free)
        budget = self.p.prefill_chunk_budget
        chunks: List[Tuple[Request, int]] = []
        ntok = 0
        alloc = 0
        for req in self.prefill:
            if budget <= 0 or free <= 0:
                break
            c = req.rem if req.rem < budget else budget
            if c > free:
                c = free
            need = c + (1 if c == req.rem else 0)
            if need > free:
                c -= 1                       # no room for the first sampled token: finish the prompt in the next iteration
                need = c
                if c <= 0:
                    break
            chunks.append((req, c))
            budget -= c
            free -= need
            ntok += c
            alloc += need
        self.held += alloc
        self._make_room()
        self._step_chunks = chunks
        self._step_ntok = ntok

    # ---- waiting loop
    def _admit_dyn(self, req: Request, now: float) -> int:
        """Admit ``req`` (the memory test was passed). Moves its surviving KV from the idle table to held (the 'lock'), and
        (ondemand_preempt) allocates its first chunk. Returns the prefill tokens it still needs."""
        sid = req.sid
        total = req.prompt + req.gen
        kv = self.idle.pop(sid, None)
        if kv is not None:
            self.idle_sum -= kv
            if not req.resumed and kv != req.prompt - self.wl.new_prompt_tokens:
                raise AssertionError(f"hit prefix {kv} inconsistent with prompt {req.prompt}")
            hit = kv if kv < total else total - 1             # min(kv, num_tokens - 1)
        else:
            hit = 0
        if not req.resumed:
            req.hit = kv is not None
        new = total - hit
        req.pos = hit
        req.rem = new
        self.held += hit
        req.alive = False
        del self._waiting[sid]
        self.n_wait -= 1
        self.rec.set_queue(now, self.n_wait)
        self.prefill.append(req)
        self._run_order[req.rid] = req
        if self._alloc == ONDEMAND_PREEMPT:
            c0 = new if new < self._chunk_left else self._chunk_left
            if c0 > 0:
                self.held += c0 + (1 if c0 == new else 0)
                self._chunk_left -= c0
                self._step_ntok += c0
                self._step_chunks.append((req, c0))
        self._make_room()
        self.admitted_prefill_tokens += new
        if req.resumed:
            self.n_readmit += 1
            if hit > 0:
                self.n_readmit_with_kv += 1
            self.recompute_tokens += new
            self.rec.on_readmit(now, new)
            if self.trace is not None:
                self.trace.append(("R", sid, req.turn, hit, new, now))
        else:
            self.n_admitted += 1
            if req.hit:
                self.n_hits += 1
            first = req.turn == 1
            if self.trace is not None:
                self.trace.append(("A", sid, req.turn, req.hit, now))
            self.rec.on_admit(now, req.hit, first, (now - self._arrived_t[sid]) if first else 0.0)
        return new

    def _schedule_pass_dyn(self) -> None:
        self.dirty = False
        if self.n_wait == 0:
            return
        self.n_passes += 1
        self.pass_id += 1
        self._first_blocked = None
        p = self.p
        od = self._alloc == ONDEMAND_PREEMPT
        n_run = self.n_D + len(self.prefill)
        max_seqs = p.max_running_seqs
        limited = p.admission_limited_by_prefill_budget
        pending = 0
        for r in self.prefill:
            pending += r.rem
        budget_left = p.prefill_chunk_budget - pending if limited else INF
        M = self.M
        skip = p.skip_ahead
        d = self.wl.decode_tokens
        if od:
            wm = int(p.watermark_frac * M) if (p.watermark_frac > 0.0 and M != INF) else 0
            self._chunk_left = p.prefill_chunk_budget - self._step_ntok
        else:
            # PrefillAdder: total_offset = ratio * remaining decode tokens of the running (decode) requests + the extend still
            # to be allocated for in-progress prefills (amendment 1, item A1) + (extend + max_new) of this pass's admissions
            n_D = self.n_D
            sum_gen = self._sum_gc + n_D * self.G
            offset = self.new_token_ratio * (n_D * d - sum_gen)
            commit = pending
        for req in self.policy.candidates(self, self.now):
            if n_run >= max_seqs or (limited and budget_left <= 0):
                break
            total = req.prompt + req.gen
            if od:
                # a first chunk that completes the prompt is charged one more token (the sampled token; module docstring), so the
                # test must cover it or the allocation right after the test could overflow M (amendment 1, item A2)
                kv0 = self.idle.get(req.sid)
                hit0 = 0 if kv0 is None else (kv0 if kv0 < total else total - 1)
                new0 = total - hit0
                c0 = new0 if new0 < self._chunk_left else self._chunk_left
                extra = 1 if (c0 > 0 and c0 == new0) else 0
                # registered: the whole sequence must fit (scout: scheduler_reserve_full_isl=True); sensitivity ``first_chunk``: the cached
                # prefix plus the first chunk must fit (what an engine without the full-ISL check would do)
                fits = ondemand_admit_ok(self.held, (hit0 + c0 + extra) if self._first_chunk_adm else (total + extra),
                                         wm if n_run > 0 else 0, M)
            else:
                dec = d - req.gen
                fits = ratio_admit_ok(self.held, commit, offset, total, dec, M, n_run)
            if not fits:
                if self._first_blocked is None:
                    self._first_blocked = req
                if skip:
                    continue
                break
            new = self._admit_dyn(req, self.now)
            if not od:
                commit += new + dec
            n_run += 1
            if limited:
                budget_left -= new
        if n_run > self.max_running:
            self.max_running = n_run
        self._compact_queue()

    # ---- main loop (allocation modes)
    def _run_dyn(self, horizon: float) -> None:
        if self._sep:
            self._run_dyn_separate(horizon)
            return
        always_pass = self.policy.time_dependent
        mem_on = self.rec.mem_on
        od = self._alloc == ONDEMAND_PREEMPT
        M = self.M
        while self.now < horizon and not self.stopped:
            self._process_exogenous(self.now)
            if self.stopped:
                break
            self._process_done()
            if self.debug:
                self.check_invariants()
            changed = self._running_step_ondemand() if od else self._running_step_ratio()
            if (self.dirty or (always_pass and self.n_wait > 0)) and not changed and not self.stopped:
                self._schedule_pass_dyn()
            if not od:
                self._plan_chunks_ratio()
            if mem_on:
                self.rec.set_mem(self.now, self.held, self.idle_sum, 0)
            if self.stop_hit is not None:
                self._check_hit_stop()
                if self.stopped:
                    break
            if self.n_D == 0 and not self.prefill:
                if self.n_wait > 0:
                    raise RuntimeError("engine idle with waiting requests and no admissible request (deadlock)")
                if self._alloc == RATIO_RESERVE:
                    self.new_token_ratio = self._ratio_init          # scheduler fully idle: tracker.reset()
                nxt = self._next_exogenous_time()
                if nxt >= horizon:
                    self.now = horizon
                    break
                self.now = nxt
                continue
            if self._step_chunks:
                self._stall_guard = 0
                self._iterate_with_prefill(self._step_chunks)
            elif self.n_D > 0:
                self._stall_guard = 0
                nxt = self._next_exogenous_time()
                if always_pass and self.n_wait > 0:
                    nt = self.policy.next_time_event(self, self.now)
                    if nt < nxt:
                        nxt = nt
                if self.dirty:
                    n_cap = 1               # the admission pass was skipped (preemption / retraction): it is due at the next boundary
                else:
                    n_cap = None if M == INF else 1 + int((M - self.held) // self.n_D)
                self._iterate_decode(nxt if nxt < horizon else horizon, n_cap)
            else:
                # prefilling requests only, none could be allocated (cannot happen with the registered admission test)
                self._stall_guard += 1
                if self._stall_guard > 1000:
                    raise RuntimeError("prefill stall without progress")
                v = self._newest_prefilling()
                kv = self._leave_running(v)
                self.held -= kv
                self._requeue(v, kv, front=False)
                self.n_fallback_retract += 1
        if self.stopped and self.stop_reason == "hit":
            self.end_time = self.now
        else:
            self.end_time = self.stop_time if (self.stopped and self.stop_time is not None) else horizon
        self.rec.set_queue(self.end_time, self.n_wait)
        self.rec.set_gate(self.end_time, len(self._gate))

    def _run_dyn_separate(self, horizon: float) -> None:
        """Main loop of ``ratio_reserve`` with ``batching=separate_prefill_priority`` (SGLang ``get_next_batch_to_run``): the admission pass
        first; if a prefill batch results, run a prefill-only iteration (only its chunks are allocated; decode sequences neither allocate nor
        advance, the new-token ratio does not decay); otherwise run decode iterations, where the decode-OOM check / retraction and the ratio
        decay happen (``update_running_batch``)."""
        always_pass = self.policy.time_dependent
        mem_on = self.rec.mem_on
        M = self.M
        while self.now < horizon and not self.stopped:
            self._process_exogenous(self.now)
            if self.stopped:
                break
            self._process_done()
            if self.debug:
                self.check_invariants()
            if (self.dirty or (always_pass and self.n_wait > 0)) and not self.stopped:
                self._schedule_pass_dyn()
            self._plan_chunks_ratio()
            if mem_on:
                self.rec.set_mem(self.now, self.held, self.idle_sum, 0)
            if self.stop_hit is not None:
                self._check_hit_stop()
                if self.stopped:
                    break
            if self.n_D == 0 and not self.prefill:
                if self.n_wait > 0:
                    raise RuntimeError("engine idle with waiting requests and no admissible request (deadlock)")
                self.new_token_ratio = self._ratio_init          # scheduler fully idle: tracker.reset()
                nxt = self._next_exogenous_time()
                if nxt >= horizon:
                    self.now = horizon
                    break
                self.now = nxt
                continue
            if self._step_chunks:
                self._stall_guard = 0
                self._iterate_with_prefill(self._step_chunks)
            elif self.n_D > 0:
                self._stall_guard = 0
                self._running_step_ratio()                       # decode-OOM check (retract, re-estimate the ratio) + one token per decode request
                nxt = self._next_exogenous_time()
                if always_pass and self.n_wait > 0:
                    nt = self.policy.next_time_event(self, self.now)
                    if nt < nxt:
                        nxt = nt
                if self.dirty:
                    n_cap = 1               # a retraction re-queued a request: the admission pass is due at the next boundary
                else:
                    n_cap = None if M == INF else 1 + int((M - self.held) // self.n_D)
                self._iterate_decode(nxt if nxt < horizon else horizon, n_cap)
            else:
                # prefilling requests only, none could be allocated (cannot happen with the registered admission test)
                self._stall_guard += 1
                if self._stall_guard > 1000:
                    raise RuntimeError("prefill stall without progress")
                v = self._newest_prefilling()
                kv = self._leave_running(v)
                self.held -= kv
                self._requeue(v, kv, front=False)
                self.n_fallback_retract += 1
        if self.stopped and self.stop_reason == "hit":
            self.end_time = self.now
        else:
            self.end_time = self.stop_time if (self.stopped and self.stop_time is not None) else horizon
        self.rec.set_queue(self.end_time, self.n_wait)
        self.rec.set_gate(self.end_time, len(self._gate))

    # ------------------------------------------------------------------ introspection
    def in_flight(self) -> int:
        return self.in_system + len(self._gate)

    def stats(self) -> Dict[str, float]:
        out = {
            "n_arrived": self.n_arrived,
            "n_sessions_done": self.n_sessions_done,
            "n_in_flight": self.in_flight(),
            "n_turns_done": self.n_turns_done,
            "n_admitted": self.n_admitted,
            "n_hits": self.n_hits,
            "hit_rate_all": self.n_hits / self.n_admitted if self.n_admitted else float("nan"),
            "final_queue": self.n_wait,
            "final_gate": len(self._gate),
            "max_queue": self.max_queue,
            "max_queue_pre_stop": self.max_queue_pre_stop if self.stopped else self.max_queue,
            "max_gate": self.max_gate,
            "n_evictions": self.n_evictions,
            "evicted_tokens": self.evicted_tokens,
            "n_iterations": self.n_iterations,
            "n_steps": self.n_steps,
            "n_passes": self.n_passes,
            "busy_frac_total": self.busy_s / self.end_time if self.end_time > 0 else float("nan"),
            "max_resident_tokens": self.max_resident,
            "max_running": self.max_running,
            "max_held_tokens_debug": self.max_held_tokens,
            "stopped_early": int(self.stopped),
            "stop_time": self.stop_time if self.stop_time is not None else float("nan"),
            "stop_reason": self.stop_reason,
            "max_in_system": self.max_in_system,
            "entries_over_cap": self.entries_over_cap,
            "cap_min": self.cap_min if self.cap_min is not None else -1,
            "cap_max": self.cap_max if self.cap_max is not None else -1,
            "cap_final": self.session_cap if self.session_cap is not None else -1,
            "n_ticks": self.n_ticks,
            "n_pins": self.n_pins,
            "n_pin_expired": self.n_pin_expired,
            "n_stall_breaks": self.n_stall_breaks,
            "n_released": self.n_released,
            "n_eager_unpins": self.n_eager_unpins,
            "n_soft_evictions": self.n_soft_evictions,
        }
        if self._sep:
            out.update({
                "batching": SEPARATE_PREFILL_PRIORITY,
                "n_prefill_iters": self.n_prefill_iters,
                "n_decode_iters": self.n_iterations - self.n_prefill_iters,
                "prefill_busy_s": self.prefill_busy_s,
                "decode_busy_s": self.busy_s - self.prefill_busy_s,
            })
        if self._dyn:
            out.update({
                "alloc_mode": self._alloc,
                "n_preempt": self.n_preempt,
                "n_readmit": self.n_readmit,
                "n_readmit_with_kv": self.n_readmit_with_kv,
                "recompute_tokens": self.recompute_tokens,
                "lost_prefill_tokens": self.lost_prefill_tokens,
                "recompute_processed_tokens": self.recompute_processed_tokens,
                "max_preempt_per_turn": self.max_preempt_per_turn,
                "n_turns_preempted": self.n_turns_preempted,
                "n_turns_preempted_ge3": self.n_turns_preempted_ge3,
                "n_partial_evictions": self.n_partial_evictions,
                "admitted_prefill_tokens": self.admitted_prefill_tokens,
                "processed_prefill_tokens": self.processed_prefill_tokens,
                "n_fallback_retract": self.n_fallback_retract,
                "ratio_final": self.new_token_ratio if self._alloc == RATIO_RESERVE else float("nan"),
                "ratio_min_seen": self.ratio_min_seen if self._alloc == RATIO_RESERVE else float("nan"),
            })
        return out

    def check_invariants(self) -> None:
        """Debug-only structural checks (O(running + idle))."""
        if self._dyn:
            self._check_invariants_dyn()
            return
        M = self.M
        run_reqs = list(self.prefill) + [r for (_, _, r) in self._done_heap]
        assert self.reserved == sum(r.end for r in run_reqs) + sum(r.end for r in self._pending_done), "reserved mismatch"
        assert self.idle_sum == sum(self.idle.values()), "idle_sum mismatch"
        assert self.reserved + self.idle_sum <= M + 1e-9, f"memory exceeded: {self.reserved}+{self.idle_sum}>{M}"
        n_run = len(run_reqs)
        assert n_run <= self.p.max_running_seqs, "running cap exceeded"
        assert self.n_D == len(self._done_heap), "n_D mismatch"
        held = sum(r.pos for r in self.prefill) + sum(r.offs + self.G for (_, _, r) in self._done_heap)
        assert held <= self.reserved, "held KV exceeds reservation"
        if held + self.idle_sum > self.max_held_tokens:
            self.max_held_tokens = held + self.idle_sum
        assert self.n_wait == sum(1 for r in self._q[self._qh:] if r.alive), "n_wait mismatch"
        assert self.n_wait == len(self._waiting), "waiting dict mismatch"
        run_sids = {r.sid for r in run_reqs}
        for sid in self.idle:
            assert sid not in run_sids, "running session also idle-resident"
        if self.session_cap is not None and self.aimd is None:
            assert self.in_system <= self.session_cap, "session cap exceeded"
        assert self.entries_over_cap == 0, "a session entered the system while at/over the cap"
        self._check_protection()
        self._check_locations()

    def _check_invariants_dyn(self) -> None:
        """Allocation modes: held is recomputed from the request states; memory, running set, waiting set, locations."""
        M = self.M
        G = self.G
        live = [r for (_, _, r) in self._done_heap if not r.gone]
        run = list(self.prefill) + live + list(self._pending_done)
        held = (sum(r.pos for r in self.prefill) + sum(r.offs + G for r in live)
                + sum(r.end for r in self._pending_done))
        assert self.held == held, f"held mismatch: {self.held} != {held}"
        assert self.idle_sum == sum(self.idle.values()), "idle_sum mismatch"
        assert self.held + self.idle_sum <= M + 1e-9, f"memory exceeded: {self.held}+{self.idle_sum}>{M}"
        assert self.max_resident <= M + 1e-9, "peak memory exceeded"
        assert set(self._run_order) == {r.rid for r in run}, "running-order table out of sync"
        assert len(run) <= self.p.max_running_seqs, "running cap exceeded"
        assert self.n_D == len(live), "n_D mismatch"
        assert self.sum_off == sum(r.offs for r in live), "sum_off mismatch"
        assert self._sum_gc == sum(r.gen - r.g_enter for r in live), "generated-token sum mismatch"
        d = self.wl.decode_tokens
        for r in live:
            gen_now = r.gen + G - r.g_enter
            assert 1 <= gen_now <= d, "generated tokens out of range"
            assert r.offs + G == r.prompt + gen_now, "decode context != prompt + generated"
            assert r.done_g - G == d - gen_now, "remaining decode iterations inconsistent"
        for r in self.prefill:
            assert r.rem > 0 and not r.gone, "prefill request with nothing to prefill or marked gone"
            assert r.pos + r.rem == r.prompt + r.gen, "prefill pos + rem != num_tokens"
        assert self.n_wait == sum(1 for r in self._q[self._qh:] if r.alive), "n_wait mismatch"
        assert self.n_wait == len(self._waiting), "waiting dict mismatch"
        for r in self._waiting.values():
            assert r.alive and not r.gone, "waiting request flags"
        run_sids = {r.sid for r in run}
        for sid in self.idle:
            assert sid not in run_sids, "running session also idle-resident"
        if self.session_cap is not None and self.aimd is None:
            assert self.in_system <= self.session_cap, "session cap exceeded"
        assert self.entries_over_cap == 0, "a session entered the system while at/over the cap"
        assert self.n_arrived == self.n_sessions_done + self.in_flight(), "session conservation"
        assert self.processed_prefill_tokens + self.lost_prefill_tokens + sum(r.rem for r in self.prefill) \
            == self.admitted_prefill_tokens, "prefill-token conservation"
        self._check_locations()

    def _check_protection(self) -> None:
        """Protection dicts equal their definition; hard-protected KV is resident and fits next to the reservations."""
        hard: Dict[int, int] = {}
        soft: Dict[int, int] = {}
        for sid, kv in self.idle.items():
            if sid in self._ended:
                continue
            if sid in self._pin:
                hard[sid] = kv
            elif self._peek is not None and sid in self._waiting:
                if self._peek == "pin":
                    if sid not in self._released:
                        hard[sid] = kv
                else:
                    soft[sid] = kv
        assert hard == self._hard, "hard-protection dict out of sync"
        assert soft == self._soft, "soft-protection dict out of sync"
        assert self._hard_sum == sum(hard.values()) and self._soft_sum == sum(soft.values()), "protection sums"
        assert set(self._pin) <= self.idle.keys(), "pin without resident KV"
        assert self._released <= self._waiting.keys(), "released set holds a non-waiting session"
        assert self.reserved + self._hard_sum <= self.M + 1e-9, "hard-protected KV + reservations exceed M"
        if self._track_prog:
            assert self._wsorted == sorted(self._waiting), "program-order index out of sync"
        # every valid pin has a heap entry unless its session is waiting past expiry
        valid = {sid for (_, tok, sid) in self._pin_heap if self._pin.get(sid, (None, None))[1] == tok}
        for sid, (exp, tok) in self._pin.items():
            assert sid in valid or sid in self._waiting, f"pin of {sid} lost its expiry event"

    def _check_locations(self) -> None:
        """Every in-system session is in exactly one place (waiting queue, prefill, decode, awaiting finish, or
        tool call); gate sessions are not in the system; idle KV belongs only to waiting / tool-call sessions
        (or ended sessions when ``free_kv_on_session_end=False``) and has the length the next turn expects."""
        loc: Dict[int, str] = {}

        def put(sid: int, where: str) -> None:
            assert sid not in loc, f"session {sid} is in both {loc[sid]} and {where}"
            loc[sid] = where

        for sid in self._waiting:
            put(sid, "waiting")
        for r in self.prefill:
            put(r.sid, "prefill")
        for (_, _, r) in self._done_heap:
            if not r.gone:
                put(r.sid, "decode")
        for r in self._pending_done:
            put(r.sid, "pending")
        for (_, _, sid) in self._tool_heap:
            put(sid, "tool")
        assert len(loc) == self.in_system, f"{len(loc)} located sessions != in_system {self.in_system}"
        assert not (set(self._gate) & loc.keys()), "gate session also in the system"
        delta = self.wl.new_prompt_tokens
        for sid, kv in self.idle.items():
            if sid in self._ended:
                assert sid not in loc, "ended session still located in the system"
                assert kv == self.wl.end_len(self._nt[sid]), "ended session KV length wrong"
                continue
            assert loc.get(sid) in ("waiting", "tool"), f"idle KV of session {sid} located in {loc.get(sid)}"
            wreq = self._waiting.get(sid)
            if wreq is not None and wreq.resumed:
                # preempted / retracted request: whatever survived of prompt + generated tokens (round 5)
                assert 0 < kv <= wreq.prompt + wreq.gen, f"surviving KV of preempted session {sid} out of range"
                continue
            assert kv == self.wl.prompt_len(self._turn[sid]) - delta, f"idle KV length wrong for session {sid}"
        assert self._ended <= self.idle.keys(), "ended set holds a non-idle session"
