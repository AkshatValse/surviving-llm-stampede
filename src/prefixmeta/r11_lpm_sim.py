"""Round 11, L1 / S1 bundle 2: an instrumented single run for the LPM-INF predictions, plus one opt-in fallback variant.

Nothing here changes a default: ``engine.py``, ``policies.py`` and ``sim.py`` are not edited, and ``simulate_instrumented`` with a stock policy
produces exactly the windows and queue traces of ``prefixmeta.sim.simulate`` (tests/test_r11_lpm_fallback_sim.py checks it).

Policies used by bundle 2 (all existing ``configs/prefix_meta_r5.yaml`` entries except the last):
  fcfs_lru         FCFS
  lpm128_lru       stock SGLang LPM: ``LpmFallback(128)``, i.e. any pass with more than 128 waiting requests uses plain FCFS (queue-arrival) order
  lpm_lru          pure LPM (the LPM-INF engine: WAITING_QUEUE_PREFIX_MATCH_MAX raised to 1e9, so the fallback never engages)
  lpm128s_lru      LABELLED SENSITIVITY (this module): ``LpmFallbackSticky(128)``. SGLang 0.5.22 (schedule_policy.py:215-260, :300-311) does
                   not re-sort the waiting queue during the fallback: the queue keeps the order of the last LPM sort and new arrivals are
                   appended. This policy reproduces that: on an LPM pass it stores the full order it yields; on a fallback pass it yields the
                   stored requests that are still waiting (in the stored order), then every other waiting request in arrival order.
                   Selected with the policy spec ``{kind: lpm_fallback, threshold: 128, sticky: true}`` (``make_policy`` builds the stock
                   ``LpmFallback`` from it, ignoring ``sticky``; ``simulate_instrumented`` swaps in this class before the run starts).

Instrumentation (read-only wrappers on the engine INSTANCE; the dynamics are unchanged):
  * every admission: (sid, turn, hit, prompt tokens, cached tokens = resident prefix, queue-entry time, ready time, admission time);
  * every turn completion (the engine's own trace, ``("D", sid, turn, t)``);
  * the number of scheduling passes with more than ``count_threshold`` waiting requests (the passes in which stock LPM would fall back).
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, Iterator, List, Optional

import numpy as np

from .metrics import tail_stats, trend_rise
from .policies import Lpm, LpmFallback, Policy, _fifo_unmarked
from .sim import RunSpec, build_engine


class LpmFallbackSticky(Policy):
    """LPM; a pass with more than ``threshold`` waiting requests keeps the order of the last LPM pass (SGLang's real fallback), with the
    requests that joined the queue since then appended in arrival order."""
    name = "lpm_fallback_sticky"

    def __init__(self, threshold: int):
        self.threshold = int(threshold)
        self._order: List[Any] = []
        self.n_lpm_passes = 0
        self.n_fallback_passes = 0

    def candidates(self, view, now: float) -> Iterator:
        if view.n_waiting > self.threshold:
            self.n_fallback_passes += 1
            pid = view.pass_id
            kept = []
            for r in self._order:
                if r.alive:                  # still waiting (alive turns False at admission; full_reserve has no re-queue)
                    r.mark = pid
                    kept.append(r)
            self._order = kept
            return self._chain(kept, view)
        self.n_lpm_passes += 1
        order = view.resident_waiting()      # same snapshot semantics as Lpm (stamps mark = pass_id)
        order.extend(_fifo_unmarked(view))
        self._order = order
        return iter(order)

    @staticmethod
    def _chain(kept: List[Any], view) -> Iterator:
        yield from kept
        yield from _fifo_unmarked(view)


class _PassCounter(Policy):
    """Delegating wrapper: counts passes whose waiting queue exceeds ``threshold`` (no effect on the order)."""

    def __init__(self, inner: Policy, threshold: int):
        self.inner = inner
        self.name = inner.name
        self.time_dependent = inner.time_dependent
        self.needs_program_order = inner.needs_program_order
        self.threshold = int(threshold)
        self.n_passes = 0
        self.n_over = 0

    def candidates(self, view, now: float) -> Iterator:
        self.n_passes += 1
        if view.n_waiting > self.threshold:
            self.n_over += 1
        return self.inner.candidates(view, now)

    def next_time_event(self, view, now: float) -> float:
        return self.inner.next_time_event(view, now)


def policy_is_sticky(cfg: dict, name: str) -> bool:
    spec = cfg["policies"][name]
    return bool(spec.get("sticky", False))


def simulate_instrumented(cfg: dict, rs: RunSpec, specs=None, count_threshold: int = 128) -> Dict[str, Any]:
    """One run like ``prefixmeta.sim.simulate`` (same engine, recorder and stop rules), plus per-turn records.

    Returns {'summary', 'windows', 'qtrace', 'btrace', 'turns', 'policy_stats'} where ``turns`` is a dict of equal-length NumPy arrays over
    the ADMITTED turns (sid, turn, hit, prompt, cached, qtime, ready, t_admit, t_done; t_done = NaN if the turn did not complete)."""
    eng, rec, cap = build_engine(cfg, rs, specs)
    spec = cfg["policies"][rs.policy]
    if spec.get("sticky", False):
        if spec.get("kind") != "lpm_fallback" or not isinstance(eng.policy, LpmFallback):
            raise ValueError(f"policy {rs.policy!r}: sticky is defined for kind lpm_fallback only")
        if eng._dyn:
            raise ValueError("the sticky fallback variant is implemented for alloc_mode full_reserve only")
        eng.policy = LpmFallbackSticky(int(spec["threshold"]))
    inner = eng.policy
    counter = _PassCounter(inner, count_threshold)
    eng.policy = counter

    adm: List[tuple] = []
    orig_admit = eng._admit

    def _admit(req, now):                   # instance attribute shadows the bound method; same return value
        new = orig_admit(req, now)
        adm.append((req.sid, req.turn, req.hit, req.prompt, req.pos if req.hit else 0, req.qtime, req.ready, now))
        return new

    eng._admit = _admit
    eng.trace = []

    t0 = time.perf_counter()
    eng.run(rs.horizon_s)
    wall = time.perf_counter() - t0
    windows = rec.finalize(eng.end_time)
    qtrace = rec.queue_trace()
    btrace = rec.backlog_trace()

    done = {(e[1], e[2]): e[3] for e in eng.trace if e[0] == "D"}
    n = len(adm)
    turns = {
        "sid": np.fromiter((a[0] for a in adm), dtype=np.int64, count=n),
        "turn": np.fromiter((a[1] for a in adm), dtype=np.int64, count=n),
        "hit": np.fromiter((a[2] for a in adm), dtype=bool, count=n),
        "prompt": np.fromiter((a[3] for a in adm), dtype=np.int64, count=n),
        "cached": np.fromiter((a[4] for a in adm), dtype=np.int64, count=n),
        "qtime": np.fromiter((a[5] for a in adm), dtype=float, count=n),
        "ready": np.fromiter((a[6] for a in adm), dtype=float, count=n),
        "t_admit": np.fromiter((a[7] for a in adm), dtype=float, count=n),
        "t_done": np.fromiter((done.get((a[0], a[1]), math.nan) for a in adm), dtype=float, count=n),
    }
    eng.trace = None

    tail_s = min(cfg["metrics"]["tail_window_s"], eng.end_time / 2.0)
    tl = tail_stats(windows, eng.end_time - tail_s, eng.end_time)
    summary: Dict[str, Any] = {
        "exp": rs.exp, "policy": rs.policy, "seed": rs.seed, "variant": rs.variant, "horizon_s": rs.horizon_s, "sim_end_s": eng.end_time,
        "session_cap": cap if cap is not None else -1, "wall_s": wall, "tail_hit_rate": tl["hit_rate"],
        "tail_backlog_trend_rise": trend_rise(btrace, eng.end_time - tail_s, eng.end_time),
        "final_backlog": eng.n_wait + len(eng._gate),
    }
    summary.update(eng.stats())
    summary.update(rs.meta)
    pstats = {"policy_class": type(inner).__name__, "n_policy_calls": counter.n_passes, "n_passes_queue_over_threshold": counter.n_over,
              "count_threshold": int(count_threshold)}
    if isinstance(inner, LpmFallbackSticky):
        pstats.update({"sticky_lpm_passes": inner.n_lpm_passes, "sticky_fallback_passes": inner.n_fallback_passes})
    return {"summary": summary, "windows": windows, "qtrace": qtrace, "btrace": btrace, "turns": turns, "policy_stats": pstats}


__all__ = ["LpmFallbackSticky", "simulate_instrumented", "policy_is_sticky", "Lpm"]
