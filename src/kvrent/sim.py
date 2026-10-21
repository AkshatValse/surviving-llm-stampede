"""Discrete-event simulator of KV-cache memory under agent tool-call pauses.

Model summary (see configs/kvrent_pilot.yaml for parameters):
  * Memory M tokens. A program running an LLM call reserves its full
    post-call context (ctx + new + dec) for the whole call.
  * Admission is FCFS with head-of-line blocking. A HOLD-return needs only the
    delta (new + dec) since its KV is still resident; SWAP/DISCARD returns and
    new programs need the full post-call context.
  * SWAP: memory freed at eviction time (optimistic; swap-out occupies a
    single FIFO PCIe channel). On return: admission, then swap-in on the same
    channel, then prefill(new) + decode.
  * DISCARD: on return: admission, then prefill(ctx + new) + decode.
  * GPU compute is NOT contended (decode/prefill times are load-independent).
  * Deadlock breaker: if the queue head cannot fit and nothing is running,
    held KV (queued-growth first, then paused) is force-evicted (cheaper
    action), counted as `forced`.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .policies import EVICT_SWAP, INF, Policy
from .workload import Program

ARRIVE, CALL_DONE, TTL, TOOL_RET, SWAPIN_DONE = range(5)
K_NEW, K_HOLD, K_SWAP, K_DISC = range(4)
M_HELD, M_SWAP, M_DISC = 0, 1, 2   # paused-call modes (== action+1 for evictions)


@dataclass
class SimParams:
    M: float
    p: float
    d: float
    s: float
    horizon: float
    warmup: float
    margin: float

    @staticmethod
    def from_cfg(cfg: dict) -> "SimParams":
        sv, sm = cfg["server"], cfg["sim"]
        return SimParams(sv["M_tokens"], sv["prefill_s_per_token"], sv["decode_s_per_token"],
                         sv["swap_s_per_token"], sm["horizon_s"], sm["warmup_s"], sm["margin_s"])


@dataclass
class SimResult:
    arrival: np.ndarray
    finish: np.ndarray            # nan if unfinished by horizon
    util_mean: float
    max_used: float
    n_held: int = 0
    n_swap: int = 0
    n_discard: int = 0
    n_forced: int = 0
    recompute_s: float = 0.0
    swap_s: float = 0.0
    n_events: int = 0


@dataclass
class _Req:
    pid: int
    need: float
    kind: int


class Simulator:
    def __init__(self, progs: list[Program], policy: Policy, prm: SimParams):
        self.progs, self.pol, self.P = progs, policy, prm
        n = len(progs)
        self.k = [0] * n                 # current step index
        self.ctx = [0] * n               # KV tokens at last pause / call end
        self.mode = [M_HELD] * n
        self.act = [EVICT_SWAP] * n      # eviction action chosen at decision time
        self.tok = [0] * n               # TTL validity token
        self.call_t0 = [0.0] * n
        self.finish = np.full(n, np.nan)
        self.heap: list = []
        self.seq = 0
        self.q: deque[_Req] = deque()
        self.qreq: dict[int, _Req] = {}
        self.paused: set[int] = set()    # pids paused with KV resident
        self.used = 0.0
        self.max_used = 0.0
        self.running = 0
        self.pcie_free = 0.0
        self.area = 0.0
        self.last_t = 0.0
        self.res = SimResult(np.array([g.arrival for g in progs]), self.finish, 0.0, 0.0)

    # --- infrastructure -------------------------------------------------
    def _push(self, t: float, kind: int, pid: int, aux: int = 0) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (t, self.seq, kind, pid, aux))

    def _advance(self, t: float) -> None:
        lo, hi = max(self.last_t, self.P.warmup), min(t, self.P.horizon)
        if hi > lo:
            self.area += self.used * (hi - lo)
        self.last_t = t

    def _alloc(self, x: float) -> None:
        self.used += x
        if self.used > self.max_used:
            self.max_used = self.used

    def _pcie(self, now: float, dur: float) -> float:
        start = max(now, self.pcie_free)
        self.pcie_free = start + dur
        return self.pcie_free

    def _post_ctx(self, pid: int) -> int:
        g, k = self.progs[pid], self.k[pid]
        return self.ctx[pid] + g.new[k] + g.dec[k]

    # --- core -----------------------------------------------------------
    def run(self) -> SimResult:
        for g in self.progs:
            self._push(g.arrival, ARRIVE, g.pid)
        H = self.P.horizon
        heap = self.heap
        n_ev = 0
        while heap and heap[0][0] <= H:
            t, _, kind, pid, aux = heapq.heappop(heap)
            self._advance(t)
            n_ev += 1
            if kind == ARRIVE:
                self._enqueue(pid, K_NEW)
            elif kind == CALL_DONE:
                self._call_done(t, pid)
            elif kind == TTL:
                self._ttl(t, pid, aux)
            elif kind == TOOL_RET:
                self._tool_ret(t, pid)
            else:  # SWAPIN_DONE
                g, k = self.progs[pid], self.k[pid]
                self._push(t + self.P.p * g.new[k] + self.P.d * g.dec[k], CALL_DONE, pid)
            self._schedule(t)
        self._advance(H)
        r = self.res
        r.util_mean = self.area / (self.P.M * max(H - self.P.warmup, 1e-9))
        r.max_used = self.max_used
        r.n_events = n_ev
        return r

    def _enqueue(self, pid: int, kind: int) -> None:
        if kind == K_HOLD:
            g, k = self.progs[pid], self.k[pid]
            need = g.new[k] + g.dec[k]
        else:
            need = self._post_ctx(pid)
        r = _Req(pid, need, kind)
        self.q.append(r)
        self.qreq[pid] = r

    def _schedule(self, now: float) -> None:
        while True:
            while self.q and self.q[0].need <= self.P.M - self.used + 1e-9:
                r = self.q.popleft()
                del self.qreq[r.pid]
                self._alloc(r.need)
                self._start(now, r)
            if self.q and self.running == 0:
                self._force_evict(now)   # deadlock breaker
                continue
            break

    def _start(self, now: float, r: _Req) -> None:
        pid, P = r.pid, self.P
        g, k = self.progs[pid], self.k[pid]
        self.running += 1
        if r.kind == K_NEW:
            self._push(now + P.p * g.new[0] + P.d * g.dec[0], CALL_DONE, pid)
        elif r.kind == K_HOLD:
            self.paused.discard(pid)
            self._push(now + P.p * g.new[k] + P.d * g.dec[k], CALL_DONE, pid)
        elif r.kind == K_SWAP:
            L = self.ctx[pid]
            fin = self._pcie(now, P.s * L)
            if now >= P.warmup:
                self.res.swap_s += P.s * L
            self._push(fin, SWAPIN_DONE, pid)
        else:  # K_DISC
            L = self.ctx[pid]
            if now >= P.warmup:
                self.res.recompute_s += P.p * L
            self._push(now + P.p * (L + g.new[k]) + P.d * g.dec[k], CALL_DONE, pid)

    def _evict(self, now: float, pid: int, action: int) -> None:
        L = self.ctx[pid]
        self.used -= L
        self.paused.discard(pid)
        self.mode[pid] = M_SWAP if action == EVICT_SWAP else M_DISC
        if action == EVICT_SWAP:
            self._pcie(now, self.P.s * L)
            if now >= self.P.warmup:
                self.res.swap_s += self.P.s * L

    def _force_evict(self, now: float) -> None:
        held_q = [r for r in self.q if r.kind == K_HOLD]
        if held_q:
            r = max(held_q, key=lambda x: self.ctx[x.pid])
            pid = r.pid
            self._evict(now, pid, self.act[pid])
            r.kind = K_SWAP if self.mode[pid] == M_SWAP else K_DISC
            r.need = self._post_ctx(pid)
        elif self.paused:
            pid = max(self.paused, key=lambda x: self.ctx[x])
            self.tok[pid] += 1  # invalidate pending TTL
            self._evict(now, pid, self.act[pid])
        else:
            raise RuntimeError("deadlock: head request exceeds capacity")
        self.res.n_forced += 1

    # --- handlers -------------------------------------------------------
    def _call_done(self, now: float, pid: int) -> None:
        self.running -= 1
        g, k = self.progs[pid], self.k[pid]
        self.ctx[pid] = L = self._post_ctx(pid)
        if k == g.K - 1:
            self.used -= L
            self.finish[pid] = now
            return
        D = g.dur[k]
        tau, action = self.pol.decide(g.tool[k], L, D)
        self.act[pid] = action
        self.call_t0[pid] = now
        self.mode[pid] = M_HELD
        self._push(now + D, TOOL_RET, pid)
        if D <= tau:
            self.paused.add(pid)
        elif tau <= 0.0:
            self._evict(now, pid, action)
        else:
            self.paused.add(pid)
            self.tok[pid] += 1
            self._push(now + tau, TTL, pid, self.tok[pid])

    def _ttl(self, now: float, pid: int, token: int) -> None:
        if token == self.tok[pid] and self.mode[pid] == M_HELD and pid in self.paused:
            self._evict(now, pid, self.act[pid])

    def _tool_ret(self, now: float, pid: int) -> None:
        g, k = self.progs[pid], self.k[pid]
        self.pol.observe(g.tool[k], g.dur[k])
        m = self.mode[pid]
        if self.call_t0[pid] >= self.P.warmup:
            r = self.res
            if m == M_HELD:
                r.n_held += 1
            elif m == M_SWAP:
                r.n_swap += 1
            else:
                r.n_discard += 1
        self.k[pid] = k + 1
        self.tok[pid] += 1
        self._enqueue(pid, K_HOLD if m == M_HELD else (K_SWAP if m == M_SWAP else K_DISC))


def simulate(progs: list[Program], policy: Policy, prm: SimParams) -> SimResult:
    return Simulator(progs, policy, prm).run()
