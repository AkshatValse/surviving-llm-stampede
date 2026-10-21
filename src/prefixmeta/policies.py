"""Admission-order policies.

A policy turns the current waiting queue into an ordered stream of candidate requests; the engine
walks that stream, admitting while memory / the running cap / the prefill budget allow (it stops at the
first request that does not fit unless ``skip_ahead``). Order is computed once per scheduling pass
(like SGLang's per-round ``calc_priority``); a candidate whose session KV was evicted earlier in the
same pass is simply admitted as a miss.

Policies only use this narrow view of the engine::

    view.n_waiting                 -> int   number of live waiting requests
    view.fifo_iter()               -> iterator over live waiting requests in queue-arrival order
    view.resident_waiting(skip_marked=False)
                                   -> list of live waiting requests whose session KV is resident now,
                                      sorted by (matched prefix length desc, queue time asc); each
                                      returned request is stamped ``req.mark = view.pass_id``; with
                                      skip_marked=True requests already stamped in this pass are omitted
    view.pass_id                   -> int, unique id of the current pass

``req.qtime`` is the time the request entered the waiting queue.
"""
from __future__ import annotations

from typing import Iterator, Optional


class Policy:
    name = "base"
    #: True if the order depends on wall-clock time (aging); the engine then re-runs passes at every boundary
    time_dependent = False

    def candidates(self, view, now: float) -> Iterator:
        raise NotImplementedError


def _fifo_unmarked(view) -> Iterator:
    """Waiting requests in FCFS order, skipping those already yielded in this pass (mark == pass_id)."""
    pid = view.pass_id
    for r in view.fifo_iter():
        if r.mark != pid:
            yield r


class Fcfs(Policy):
    name = "fcfs"

    def candidates(self, view, now: float) -> Iterator:
        return view.fifo_iter()


class Lpm(Policy):
    """Longest-prefix-match first: requests whose session KV is resident come first (longest matched
    prefix first, ties FCFS), then the remaining requests in FCFS order. Work-conserving: never idles
    a request that could hit to serve one that cannot."""
    name = "lpm"

    def candidates(self, view, now: float) -> Iterator:
        yield from view.resident_waiting()
        yield from _fifo_unmarked(view)


class LpmFallback(Policy):
    """LPM, but any pass in which more than ``threshold`` requests are waiting uses plain FCFS order
    (mirrors SGLang's WAITING_QUEUE_PREFIX_MATCH_MAX fallback)."""
    name = "lpm_fallback"

    def __init__(self, threshold: int):
        self.threshold = int(threshold)
        self._lpm = Lpm()
        self._fcfs = Fcfs()

    def candidates(self, view, now: float) -> Iterator:
        if view.n_waiting > self.threshold:
            return self._fcfs.candidates(view, now)
        return self._lpm.candidates(view, now)


class AgingLpm(Policy):
    """Requests that have waited longer than ``w_max_s`` go first in FCFS order; the rest by LPM."""
    name = "aging_lpm"
    time_dependent = True

    def __init__(self, w_max_s: float):
        self.w_max_s = float(w_max_s)

    def candidates(self, view, now: float) -> Iterator:
        pid = view.pass_id
        cutoff = now - self.w_max_s
        for r in view.fifo_iter():          # FIFO is qtime-sorted, so aged requests form a prefix
            if r.qtime >= cutoff:
                break
            r.mark = pid
            yield r
        # the rest (not aged) by LPM; aged requests are already marked and are skipped
        yield from view.resident_waiting(skip_marked=True)
        for r in _fifo_unmarked(view):
            yield r


def make_policy(spec: dict) -> Policy:
    kind = spec["kind"]
    if kind == "fcfs":
        return Fcfs()
    if kind == "lpm":
        return Lpm()
    if kind == "lpm_fallback":
        return LpmFallback(spec["threshold"])
    if kind == "aging_lpm":
        return AgingLpm(spec["w_max_s"])
    raise ValueError(f"unknown policy kind {kind!r}")
