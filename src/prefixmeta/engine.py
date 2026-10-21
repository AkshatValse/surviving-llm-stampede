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
* ``free_kv_on_session_end`` (default True): KV of a finished session is freed at once (an oracle; a real engine
  cannot know the session ended). False keeps it as most-recently-used evictable idle KV, which crowds out live
  sessions and raises the escape rate.
"""
from __future__ import annotations

import heapq
import math
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterator, List, Optional, Tuple

from .metrics import Recorder
from .policies import Policy
from .workload import SessionSpecs, WorkloadParams

INF = math.inf


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

    @classmethod
    def from_dict(cls, d: dict) -> "EngineParams":
        p = cls(**d)
        if p.prefill_attn_ctx not in ("end", "mid"):
            raise ValueError("prefill_attn_ctx must be 'end' or 'mid'")
        return p


class Request:
    """One turn of one session, from queue entry to last decode token."""
    __slots__ = ("rid", "sid", "turn", "qtime", "ready", "prompt", "end", "alive", "mark",
                 "pos", "rem", "offs", "done_g", "hit")

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


class Engine:
    def __init__(self, params: EngineParams, wl: WorkloadParams, specs: SessionSpecs, policy: Policy,
                 rec: Recorder, *, session_cap: Optional[int] = None, closed: bool = False,
                 stop_queue_above: Optional[int] = None, debug: bool = False):
        self.p = params
        self.wl = wl
        self.policy = policy
        self.rec = rec
        self.session_cap = session_cap
        self.closed = closed
        self.stop_q = stop_queue_above
        self.debug = debug
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
        self.end_time = 0.0
        self.max_running = 0
        self.max_held_tokens = 0           # only tracked when debug
        self.trace: Optional[list] = None  # set to [] to record ("A", sid, turn, hit, t) / ("D", sid, turn, t)

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
        else:
            self._enter(i, t)

    def _enter(self, i: int, t: float) -> None:
        self.in_system += 1
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
        prev_max = self.max_queue
        if self.n_wait > self.max_queue:
            self.max_queue = self.n_wait
        self.rec.set_queue(t, self.n_wait)
        self.dirty = True
        if self.stop_q is not None and self.n_wait > self.stop_q and not self.stopped:
            self.stopped = True
            self.stop_time = t
            self.max_queue_pre_stop = prev_max

    def _process_exogenous(self, now: float) -> None:
        arr = self._arr
        n = self._n
        th = self._tool_heap
        while not self.stopped:
            ta = arr[self._next_idx] if self._next_idx < n else INF
            tt = th[0][0] if th else INF
            if ta <= tt:
                if ta > now:
                    return
                i = self._next_idx
                self._next_idx += 1
                self._arrive(i, ta)
            else:
                if tt > now:
                    return
                t, _, sid = heapq.heappop(th)
                self._enqueue_turn(sid, t, t)

    def _next_exogenous_time(self) -> float:
        ta = self._arr[self._next_idx] if self._next_idx < self._n else INF
        tt = self._tool_heap[0][0] if self._tool_heap else INF
        return ta if ta < tt else tt

    def _finish_request(self, req: Request, t: float) -> None:
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
            if self._gate:
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
        idle = self.idle
        while need > 0:
            sid2, kv2 = idle.popitem(last=False)
            if self._ended:
                self._ended.discard(sid2)
            self.idle_sum -= kv2
            self.n_evictions += 1
            self.evicted_tokens += kv2
            need -= kv2
        self.reserved += req.end
        used = self.reserved + self.idle_sum
        if used > self.max_resident:
            self.max_resident = used
        req.alive = False
        del self._waiting[sid]
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
            if self.reserved + req.end > M:
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
            self.n_D -= 1
            self.sum_off -= req.offs
            self._pending_done.append(req)

    def _iterate_with_prefill(self) -> None:
        p = self.p
        budget = p.prefill_chunk_budget
        chunks: List[Tuple[Request, int]] = []
        ntok = 0
        attn = 0.0
        mid = p.prefill_attn_ctx == "mid"
        for req in self.prefill:
            if budget <= 0:
                break
            c = req.rem if req.rem < budget else budget
            chunks.append((req, c))
            budget -= c
            ntok += c
            attn += c * ((req.pos + 0.5 * c) if mid else (req.pos + c))
        n_D = self.n_D
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
        self.G += 1
        self.n_iterations += 1
        self.n_steps += 1
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
                # prefill done in this iteration: first token emitted now
                if d <= 1:
                    self._pending_done.append(req)
                else:
                    req.offs = (req.pos + 1) - G
                    req.done_g = G + d - 1
                    self.sum_off += req.offs
                    self.n_D += 1
                    heapq.heappush(self._done_heap, (req.done_g, req.rid, req))
            self.prefill = keep
        self.dirty = True       # prefill budget / running slots changed

    def _iterate_decode(self, t_cap: float) -> None:
        p = self.p
        n_D = self.n_D
        c0 = p.iter_fixed_s + max(p.iter_floor_s, p.per_token_s * n_D)
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
        S = n * tau0 + 0.5 * b * n * (n - 1)
        t0 = self.now
        self.now = t0 + S
        self.busy_s += S
        self.rec.add_busy(t0, self.now)
        self.G += n
        self.n_iterations += n
        self.n_steps += 1
        self._collect_done_decodes()

    # ------------------------------------------------------------------ main loop
    def run(self, horizon: float) -> None:
        always_pass = self.policy.time_dependent
        while self.now < horizon and not self.stopped:
            self._process_exogenous(self.now)
            if self.stopped:
                break
            self._process_done()
            if (self.dirty or (always_pass and self.n_wait > 0)) and not self.stopped:
                self._schedule_pass()
            if self.debug:
                self.check_invariants()
            if self.n_D == 0 and not self.prefill:
                if self.n_wait > 0:
                    raise RuntimeError("engine idle with waiting requests and no admissible request (deadlock)")
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
        self.end_time = self.stop_time if (self.stopped and self.stop_time is not None) else horizon
        self.rec.set_queue(self.end_time, self.n_wait)
        self.rec.set_gate(self.end_time, len(self._gate))

    # ------------------------------------------------------------------ introspection
    def in_flight(self) -> int:
        return self.in_system + len(self._gate)

    def stats(self) -> Dict[str, float]:
        return {
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
        }

    def check_invariants(self) -> None:
        """Debug-only structural checks (O(running + idle))."""
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
        if self.session_cap is not None:
            assert self.in_system <= self.session_cap, "session cap exceeded"
        self._check_locations()

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
            assert kv == self.wl.prompt_len(self._turn[sid]) - delta, f"idle KV length wrong for session {sid}"
        assert self._ended <= self.idle.keys(), "ended set holds a non-idle session"
