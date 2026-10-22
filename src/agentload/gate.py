"""Client-side FIFO session gate (the CAPPED arm of the paired E2 test).

Open-loop sessions ARRIVE on schedule regardless of the server. The gate sits between a session's arrival and its
first request: at most ``max_active`` sessions are admitted at any time (admitted = holds a slot until the session
ends, tool-time sleeps included), later arrivals wait in a FIFO queue. A freed slot is HANDED OFF to the head of the
queue (a newcomer can never barge past a waiter), so admission order is arrival order.

Everything runs on one event loop (no locks). ``max_active=None`` disables the cap but keeps the bookkeeping, so an
uncapped run logs the same columns (``gate_wait_s`` = 0).

Cancellation (end of run, abort) is handled: a waiter cancelled while queued leaves the queue; a waiter cancelled after
the slot was already handed to it gives the slot to the next waiter.
"""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable, Deque, List, Optional


class SessionGate:
    def __init__(self, max_active: Optional[int], now: Callable[[], float]):
        if max_active is not None and max_active < 1:
            raise ValueError("max_active must be >= 1 (or None for no cap)")
        self.max_active = max_active
        self._now = now
        self._active = 0
        self._waiters: Deque["asyncio.Future[None]"] = deque()
        self.max_active_seen = 0
        self.max_waiting_seen = 0
        self.n_admitted = 0
        self.n_waited = 0                  # admissions that had to queue (the cap was reached or a waiter was ahead)
        self.waits_s: List[float] = []     # wait of every admitted session, in admission order

    # ------------------------------------------------------------ state
    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return sum(1 for f in self._waiters if not f.done())

    def _admit(self, wait_s: float, queued: bool) -> None:
        self.n_admitted += 1
        if queued:
            self.n_waited += 1
        self.waits_s.append(wait_s)
        self.max_active_seen = max(self.max_active_seen, self._active)

    # ------------------------------------------------------------ API
    async def acquire(self) -> float:
        """Wait for a slot; returns the seconds waited (0.0 if admitted at once)."""
        t0 = self._now()
        if (self.max_active is None or self._active < self.max_active) and not self._waiters:
            self._active += 1
            self._admit(0.0, queued=False)
            return 0.0
        fut: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        self._waiters.append(fut)
        self.max_waiting_seen = max(self.max_waiting_seen, self.waiting)
        try:
            await fut                       # the slot (already counted in _active) is handed to us by release()
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                self.release()              # we were granted a slot but are being cancelled: pass it on
            else:
                try:
                    self._waiters.remove(fut)
                except ValueError:
                    pass
            raise
        wait = self._now() - t0
        self._admit(wait, queued=True)
        return wait

    def release(self) -> None:
        """Free one slot: hand it to the oldest live waiter, else decrement the active count."""
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.done():              # skip waiters cancelled while queued
                fut.set_result(None)        # active count unchanged: the slot changes owner
                return
        self._active -= 1
        if self._active < 0:                # pragma: no cover  (a release without an acquire is a bug)
            self._active = 0
            raise RuntimeError("SessionGate.release() without a matching acquire()")

    def summary(self) -> dict:
        w = self.waits_s
        return {"n_cap": self.max_active, "n_admitted": self.n_admitted, "n_waited": self.n_waited,
                "max_active_seen": self.max_active_seen, "max_waiting_seen": self.max_waiting_seen,
                "wait_s_max": max(w) if w else 0.0, "wait_s_mean": (sum(w) / len(w)) if w else 0.0,
                "n_still_waiting_at_end": self.waiting}
