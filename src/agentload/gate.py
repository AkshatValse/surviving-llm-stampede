"""Client-side FIFO session gate: the CAPPED arm (a static cap from t = 0) and the RESCUE arm (a cap engaged mid-run).

Open-loop sessions ARRIVE on schedule regardless of the server. The gate sits between a session's arrival and its
first request: at most ``max_active`` sessions are admitted at any time (admitted = holds a slot until the session
ends, tool-time sleeps included), later arrivals wait in a FIFO queue. A freed slot is HANDED OFF to the head of the
queue (a newcomer can never barge past a waiter), so admission order is arrival order.

Everything runs on one event loop (no locks). ``max_active=None`` disables the cap but keeps the bookkeeping, so an
uncapped run logs the same columns (``gate_wait_s`` = 0).

Cancellation (end of run, abort) is handled: a waiter cancelled while queued leaves the queue; a waiter cancelled after
the slot was already handed to it gives the slot to the next waiter.

Changing the cap at run time (the RESCUE arm, :meth:`set_cap`):

* Raising the cap, or removing it (``None``), fills the free slots at once: the RESUME deque (paused sessions) first,
  then the arrival queue, FIFO within each.
* Lowering the cap below the active count never evicts anyone. Slots disappear by ATTRITION: while ``active > cap`` a
  :meth:`release` decrements the active count without handing the slot on.
* :meth:`checkpoint` is the pause point at a tool-call boundary (the client calls it before each turn >= 2). If
  ``active > cap`` the caller gives up its slot (attrition) and waits in the resume deque, which is served before new
  arrivals; it returns the seconds paused (0.0, without suspending, when not over the cap).
* :meth:`acquire` queues whenever EITHER deque holds a live entry, so a newcomer never barges past a paused session.

A static cap from t = 0 never pauses anyone (admission keeps ``active <= cap`` at all times, so ``active > cap`` is
impossible), and its decisions are exactly those of the CAPPED gate before the rescue arm existed: the resume deque
stays empty, so every branch reduces to the old code (tests/test_agentload_gate_rescue.py replays a recorded event
sequence against the committed old gate).

Gate events (``set_cap`` and pause / resume) are appended to :attr:`events` as dicts for ``gate_events.csv``.
"""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional


def _check_cap(n: Optional[int]) -> None:
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
        raise ValueError("max_active must be an integer >= 1 (or None for no cap)")


class SessionGate:
    def __init__(self, max_active: Optional[int], now: Callable[[], float]):
        if max_active is not None and max_active < 1:
            raise ValueError("max_active must be >= 1 (or None for no cap)")
        self.max_active = max_active
        self._now = now
        self._active = 0
        self._waiters: Deque["asyncio.Future[None]"] = deque()     # new arrivals, FIFO
        self._resume: Deque["asyncio.Future[None]"] = deque()      # paused sessions, FIFO; served before _waiters
        self.max_active_seen = 0
        self.max_waiting_seen = 0
        self.n_admitted = 0
        self.n_waited = 0                  # admissions that had to queue (the cap was reached or a waiter was ahead)
        self.waits_s: List[float] = []     # wait of every admitted session, in admission order
        # rescue-arm bookkeeping (all stay at their initial values under a static cap)
        self.n_pauses = 0                  # checkpoints that paused
        self.n_resumes = 0                 # paused sessions that got a slot back
        self.n_attrition = 0               # releases (incl. pauses) that dropped a slot because active > cap
        self.pauses_s: List[float] = []    # duration of every completed pause, in resume order
        self.max_paused_seen = 0
        self.events: List[Dict[str, Any]] = []
        # time both deques last became empty (-inf: empty since before the run started; None: not empty now)
        self._empty_since: Optional[float] = float("-inf")

    # ------------------------------------------------------------ state
    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting_new(self) -> int:
        """Live entries of the arrival queue (sessions not yet admitted)."""
        return sum(1 for f in self._waiters if not f.done())

    @property
    def paused(self) -> int:
        """Live entries of the resume deque (paused sessions waiting for a slot back)."""
        return sum(1 for f in self._resume if not f.done())

    @property
    def waiting(self) -> int:
        """Sessions waiting for a slot: both deques."""
        return self.waiting_new + self.paused

    def over_cap(self) -> bool:
        """True when a checkpoint now would pause (a cap is set and ``active > cap``)."""
        return self.max_active is not None and self._active > self.max_active

    def queues_empty_since(self) -> Optional[float]:
        """When both deques last became empty (``-inf`` if they have been empty since the gate was built), or None
        if a session is queued now. The rescue release rule reads this."""
        return self._empty_since

    def _touch(self) -> None:
        if self.waiting > 0:
            self._empty_since = None
        elif self._empty_since is None:
            self._empty_since = self._now()

    def _event(self, kind: str, **kw: Any) -> None:
        row = {"t_s": self._now(), "event": kind, "cap": self.max_active, "active": self._active,
               "waiting": self.waiting_new, "paused": self.paused}
        row.update(kw)
        self.events.append(row)

    def _admit(self, wait_s: float, queued: bool) -> None:
        self.n_admitted += 1
        if queued:
            self.n_waited += 1
        self.waits_s.append(wait_s)
        self.max_active_seen = max(self.max_active_seen, self._active)

    def _room(self) -> bool:
        return self.max_active is None or self._active < self.max_active

    @staticmethod
    def _pop_live(dq: Deque["asyncio.Future[None]"]) -> Optional["asyncio.Future[None]"]:
        while dq:
            fut = dq.popleft()
            if not fut.done():              # skip entries cancelled while queued
                return fut
        return None

    # ------------------------------------------------------------ API
    async def acquire(self) -> float:
        """Wait for a slot; returns the seconds waited (0.0 if admitted at once)."""
        t0 = self._now()
        if self._room() and not self._waiters and not self._resume:
            self._active += 1
            self._admit(0.0, queued=False)
            return 0.0
        fut: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        self._waiters.append(fut)
        self._touch()
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
                self._touch()
            raise
        wait = self._now() - t0
        self._admit(wait, queued=True)
        return wait

    def release(self) -> None:
        """Free one slot. Over the cap (``active > cap``): drop it (attrition). Otherwise hand it to the oldest live
        paused session, else to the oldest live waiter, else decrement the active count."""
        if self.max_active is not None and self._active > self.max_active:
            self._active -= 1
            self.n_attrition += 1
            return
        for dq in (self._resume, self._waiters):
            fut = self._pop_live(dq)
            if fut is not None:
                fut.set_result(None)        # active count unchanged: the slot changes owner
                self._touch()
                return
        self._touch()
        self._active -= 1
        if self._active < 0:                # pragma: no cover  (a release without an acquire is a bug)
            self._active = 0
            raise RuntimeError("SessionGate.release() without a matching acquire()")

    def _fill(self) -> None:
        """Hand every free slot to the deques' heads, resume deque first."""
        while self._room():
            fut = self._pop_live(self._resume) or self._pop_live(self._waiters)
            if fut is None:
                break
            self._active += 1
            fut.set_result(None)
        self._touch()

    def set_cap(self, new: Optional[int], reason: str = "cap") -> None:
        """Change the cap at run time. A higher cap or None hands the free slots out at once (resume deque first);
        a lower cap acts by attrition (see the module docstring). Logged as a gate event named ``reason``."""
        _check_cap(new)
        self.max_active = new
        self._fill()
        self._event(reason)

    async def checkpoint(self, sid: Any = None) -> float:
        """Pause point at a tool-call boundary. If ``active > cap``, give up the slot (attrition) and wait in the
        resume deque for one; returns the seconds paused (0.0, without suspending, when not over the cap).
        On cancellation the caller holds NO slot (a slot handed over during the cancel is passed on)."""
        if not self.over_cap():
            return 0.0
        t0 = self._now()
        self._active -= 1                   # active > cap: the slot is dropped, not handed on
        self.n_attrition += 1
        fut: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        self._resume.append(fut)
        self._touch()
        self.n_pauses += 1
        self.max_paused_seen = max(self.max_paused_seen, self.paused)
        self._event("pause", sid=sid)
        try:
            await fut
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                self.release()              # granted a slot back while being cancelled: pass it on
            else:
                try:
                    self._resume.remove(fut)
                except ValueError:
                    pass
                self._touch()
            raise
        pause = self._now() - t0
        self.n_resumes += 1
        self.pauses_s.append(pause)
        self._event("resume", sid=sid, pause_s=pause)
        return pause

    def summary(self) -> dict:
        w = self.waits_s
        p = self.pauses_s
        return {"n_cap": self.max_active, "n_admitted": self.n_admitted, "n_waited": self.n_waited,
                "max_active_seen": self.max_active_seen, "max_waiting_seen": self.max_waiting_seen,
                "wait_s_max": max(w) if w else 0.0, "wait_s_mean": (sum(w) / len(w)) if w else 0.0,
                "n_still_waiting_at_end": self.waiting_new,
                "n_pauses": self.n_pauses, "n_resumes": self.n_resumes, "n_still_paused_at_end": self.paused,
                "n_attrition": self.n_attrition, "max_paused_seen": self.max_paused_seen,
                "pause_s_max": max(p) if p else 0.0, "pause_s_mean": (sum(p) / len(p)) if p else 0.0,
                "pause_s_total_resumed": float(sum(p))}
