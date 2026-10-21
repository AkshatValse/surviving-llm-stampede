"""Eviction rules for idle KV (round 4).

The engine keeps the KV of sessions that are not running (in a tool call, or waiting with a resident prefix) in an
ordered table ``idle`` (least recently idle first: a session is inserted when its turn finishes and removed when its next
turn is admitted or its KV is evicted). To admit a request that needs ``need`` more tokens it evicts WHOLE sessions from
that table. This module holds the victim-selection rule, as a pure function so it can be tested without an engine.

Rules (``mode``)
  ``lru``       least recently idle first (the rule of rounds 1-3; the engine keeps its own fast path for it and uses
                this function only for cross-checking in tests)
  ``mru_idle``  the session that became idle MOST recently first
  ``random``    uniformly at random without replacement among the evictable sessions, one draw per victim until at least
                ``need`` tokens are freed; uses a generator that is dedicated to eviction (``eviction_rng``)

Evictable = idle KV that is not hard-protected. Soft-protected KV (PEEK ``rank``) is used only after every unprotected
session has been taken, in the same order rule. Running requests' KV is not in ``idle`` at all, and the admitted request's
own session has already been removed from ``idle`` when the engine evicts, so none of these can be a victim.
"""
from __future__ import annotations

from typing import Container, List, Mapping, Optional, Tuple

import numpy as np

EVICTION_MODES = ("lru", "random", "mru_idle")

#: child index of ``SeedSequence(seed).spawn(...)`` reserved for the eviction stream. The workload generator uses children
#: 0-3 (arrivals, turn counts, tool times, extras; see workload.build_specs), so this one never overlaps with it.
EVICTION_STREAM = 4


def eviction_rng(seed: int) -> np.random.Generator:
    """The generator dedicated to RANDOM eviction for run seed ``seed``: child ``EVICTION_STREAM`` of SeedSequence(seed)."""
    return np.random.default_rng(np.random.SeedSequence(int(seed)).spawn(EVICTION_STREAM + 1)[EVICTION_STREAM])


def _draw(pool: List[int], idle: Mapping[int, int], need: int, got: int, rng: np.random.Generator,
          victims: List[int]) -> int:
    """Draw victims uniformly without replacement from ``pool`` (consumed) until ``got >= need``; returns the new ``got``."""
    while pool and got < need:
        j = int(rng.integers(len(pool)))
        sid = pool[j]
        pool[j] = pool[-1]
        pool.pop()
        victims.append(sid)
        got += idle[sid]
    return got


def select_victims(mode: str, idle: Mapping[int, int], need: int, hard: Container[int], soft: Container[int],
                   rng: Optional[np.random.Generator] = None) -> Tuple[List[int], int, int]:
    """Choose whole sessions to evict so that at least ``need`` tokens are freed.

    ``idle``: sid -> resident tokens, iterated from least to most recently idle. ``hard`` / ``soft``: sids that must not /
    should not be evicted (disjoint). Returns ``(victims in selection order, tokens freed, number of soft victims)``. If
    the evictable KV cannot cover ``need`` the victims are all evictable sessions and ``tokens freed < need`` (the caller
    decides what that means). Victims are minimal in the sense that the rule stops as soon as ``need`` is covered.
    """
    if mode not in EVICTION_MODES:
        raise ValueError(f"unknown eviction mode {mode!r}; expected one of {EVICTION_MODES}")
    victims: List[int] = []
    got = 0
    if need <= 0:
        return victims, 0, 0
    if mode == "random":
        if rng is None:
            raise ValueError("random eviction needs a dedicated generator (eviction_rng(seed))")
        pool = [s for s in idle if s not in hard and s not in soft]
        got = _draw(pool, idle, need, got, rng, victims)
        n_soft = 0
        if got < need:
            pool = [s for s in idle if s in soft and s not in hard]
            before = len(victims)
            got = _draw(pool, idle, need, got, rng, victims)
            n_soft = len(victims) - before
        return victims, got, n_soft
    reverse = mode == "mru_idle"
    for sid in (reversed(idle) if reverse else iter(idle)):
        if sid in hard or sid in soft:
            continue
        victims.append(sid)
        got += idle[sid]
        if got >= need:
            return victims, got, 0
    n_soft = 0
    for sid in (reversed(idle) if reverse else iter(idle)):
        if sid in soft and sid not in hard:
            victims.append(sid)
            got += idle[sid]
            n_soft += 1
            if got >= need:
                break
    return victims, got, n_soft
