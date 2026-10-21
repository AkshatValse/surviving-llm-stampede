"""Windowed metric recording and post-hoc summaries for the simulator.

``Recorder`` is fed by the engine at event times. Time-integrated quantities (queue length) use exact
piecewise-constant integration; counters are attributed to the window containing the event stamp.
Only *complete* windows (end <= end of simulation) are reported.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np


class AreaTrace:
    """Time-average and max of a piecewise-constant signal in fixed-width buckets."""

    def __init__(self, width: float):
        self.w = float(width)
        self.k = 0               # index of the current (open) bucket
        self.t = 0.0             # time up to which the signal has been integrated
        self.v = 0.0             # current value
        self.area = 0.0
        self.vmax = 0.0
        self.out: List[Tuple[float, float]] = []   # (mean, max) of closed buckets

    def advance(self, t: float) -> None:
        w = self.w
        end = (self.k + 1) * w
        while t >= end:
            self.area += self.v * (end - self.t)
            self.out.append((self.area / w, self.vmax))
            self.k += 1
            self.area = 0.0
            self.vmax = self.v
            self.t = end
            end = (self.k + 1) * w
        if t > self.t:
            self.area += self.v * (t - self.t)
            self.t = t

    def set(self, t: float, v: float) -> None:
        self.advance(t)
        self.v = v
        if v > self.vmax:
            self.vmax = v


def _pct(xs: Sequence[float], q: float) -> float:
    return float(np.percentile(xs, q)) if len(xs) else float("nan")


class Recorder:
    """Per-window counters + queue traces. All time arguments are simulation seconds."""

    def __init__(self, window_s: float, fine_window_s: float):
        self.w = float(window_s)
        self.q = AreaTrace(window_s)
        self.gate = AreaTrace(window_s)
        self.q_fine = AreaTrace(fine_window_s)
        self.gate_fine = AreaTrace(fine_window_s)
        self.cap = AreaTrace(window_s)               # session cap (only meaningful once set_cap was called)
        self._cap_set = False
        self.mem_on = False                           # opt-in memory-occupancy traces (round-2 experiments)
        self.res = AreaTrace(window_s)                # tokens reserved by running requests
        self.idl = AreaTrace(window_s)                # idle (tool-call / queued) KV tokens
        self.prot = AreaTrace(window_s)               # of which hard-protected (pinned) tokens
        self._admits: List[int] = []
        self._hits: List[int] = []
        self._first_admits: List[int] = []
        self._turns_done: List[int] = []
        self._sessions_done: List[int] = []
        self._busy: List[float] = []
        self._pf_tokens: List[int] = []
        self._evictions: List[int] = []                 # evicted whole sessions per window (round 4)
        self.dyn_on = False                              # round 5: allocation modes add the two columns below to the windows
        self._preempts: List[int] = []                  # running requests preempted / retracted per window
        self._recompute: List[int] = []                 # prefill tokens demanded at re-admissions of such requests
        self._recompute_done: List[int] = []            # prefill tokens PROCESSED for re-admitted requests (amendment 2)
        self._lost: List[int] = []                      # admitted prefill tokens discarded unprocessed (victim preempted mid-prefill)
        self._pre_max: List[int] = []                   # most preemptions suffered by one turn, over the events of the window
        self._lat: List[List[float]] = []
        self._first_wait: List[List[float]] = []

    # -- internal
    def _ensure(self, k: int) -> None:
        while len(self._admits) <= k:
            self._admits.append(0)
            self._hits.append(0)
            self._first_admits.append(0)
            self._turns_done.append(0)
            self._sessions_done.append(0)
            self._busy.append(0.0)
            self._pf_tokens.append(0)
            self._evictions.append(0)
            self._preempts.append(0)
            self._recompute.append(0)
            self._recompute_done.append(0)
            self._lost.append(0)
            self._pre_max.append(0)
            self._lat.append([])
            self._first_wait.append([])

    def _win(self, t: float) -> int:
        k = int(t // self.w)
        self._ensure(k)
        return k

    # -- signals
    def set_queue(self, t: float, n_wait: int) -> None:
        self.q.set(t, float(n_wait))
        self.q_fine.set(t, float(n_wait))

    def set_gate(self, t: float, n_gate: int) -> None:
        self.gate.set(t, float(n_gate))
        self.gate_fine.set(t, float(n_gate))

    def set_cap(self, t: float, cap: int) -> None:
        self._cap_set = True
        self.cap.set(t, float(cap))

    def set_mem(self, t: float, reserved: float, idle: float, protected: float) -> None:
        self.res.set(t, float(reserved))
        self.idl.set(t, float(idle))
        self.prot.set(t, float(protected))

    # -- events
    def add_busy(self, t0: float, t1: float) -> None:
        w = self.w
        k = self._win(t0)
        while True:
            end = (k + 1) * w
            if t1 <= end:
                self._ensure(k)
                self._busy[k] += t1 - t0
                return
            self._ensure(k)
            self._busy[k] += end - t0
            t0 = end
            k += 1

    def add_prefill_tokens(self, t: float, n: int) -> None:
        self._pf_tokens[self._win(t)] += n

    def on_evict(self, t: float, n: int) -> None:
        """``n`` sessions' idle KV were evicted at time ``t`` (called once per admission that needed memory)."""
        if n:
            self._evictions[self._win(t)] += n

    def on_preempt(self, t: float, times: int = 1) -> None:
        """A running request was preempted (vLLM-like) or retracted (SGLang-like) at time ``t``; it is the ``times``-th preemption of
        its turn (the window records the maximum over its events)."""
        k = self._win(t)
        self._preempts[k] += 1
        if times > self._pre_max[k]:
            self._pre_max[k] = times

    def on_lost(self, t: float, n: int) -> None:
        """``n`` admitted prefill tokens of a request preempted mid-prefill were discarded unprocessed at time ``t``."""
        if n:
            self._lost[self._win(t)] += n

    def add_recompute_processed(self, t: float, n: int) -> None:
        """``n`` prefill tokens of re-admitted (previously preempted / retracted) requests were processed by an iteration ending at ``t``."""
        self._recompute_done[self._win(t)] += n

    def on_readmit(self, t: float, new_tokens: int) -> None:
        """A preempted / retracted request was re-admitted; it needs ``new_tokens`` prefill tokens (recompute)."""
        self._recompute[self._win(t)] += new_tokens

    def on_admit(self, t: float, hit: bool, first_turn: bool, wait_first: float) -> None:
        k = self._win(t)
        self._admits[k] += 1
        if hit:
            self._hits[k] += 1
        if first_turn:
            self._first_admits[k] += 1
            self._first_wait[k].append(wait_first)

    def on_turn_done(self, t: float, latency: float) -> None:
        k = self._win(t)
        self._turns_done[k] += 1
        self._lat[k].append(latency)

    def on_session_done(self, t: float) -> None:
        self._sessions_done[self._win(t)] += 1

    # -- output
    def finalize(self, t_end: float) -> List[Dict[str, float]]:
        """Close buckets up to t_end and return one dict per complete 1000 s window."""
        self.q.advance(t_end)
        self.gate.advance(t_end)
        self.q_fine.advance(t_end)
        self.gate_fine.advance(t_end)
        if self._cap_set:
            self.cap.advance(t_end)
        if self.mem_on:
            self.res.advance(t_end)
            self.idl.advance(t_end)
            self.prot.advance(t_end)
        n_full = int(math.floor(t_end / self.w + 1e-9))
        self._ensure(max(n_full - 1, 0))
        rows: List[Dict[str, float]] = []
        for k in range(n_full):
            qm, qx = self.q.out[k] if k < len(self.q.out) else (float("nan"), float("nan"))
            gm, gx = self.gate.out[k] if k < len(self.gate.out) else (float("nan"), float("nan"))
            cm = self.cap.out[k][0] if self._cap_set and k < len(self.cap.out) else float("nan")
            rm = self.res.out[k][0] if self.mem_on and k < len(self.res.out) else float("nan")
            im = self.idl.out[k][0] if self.mem_on and k < len(self.idl.out) else float("nan")
            pm = self.prot.out[k][0] if self.mem_on and k < len(self.prot.out) else float("nan")
            adm, hit, fa = self._admits[k], self._hits[k], self._first_admits[k]
            fw = self._first_wait[k]
            rows.append({
                "window": k,
                "t_start": k * self.w,
                "t_end": (k + 1) * self.w,
                "admitted_turns": adm,
                "hit_rate": hit / adm if adm else float("nan"),
                "hit_rate_followup": hit / (adm - fa) if adm - fa > 0 else float("nan"),
                "queue_mean": qm,
                "queue_max": qx,
                "gate_mean": gm,
                "gate_max": gx,
                "cap_mean": cm,
                "reserved_mean": rm,
                "idle_mean": im,
                "protected_mean": pm,
                "sessions_per_s": self._sessions_done[k] / self.w,
                "turns_per_s": self._turns_done[k] / self.w,
                "lat_p50_s": _pct(self._lat[k], 50),
                "lat_p99_s": _pct(self._lat[k], 99),
                "first_turn_wait_mean_s": float(np.mean(fw)) if fw else float("nan"),
                "first_turn_wait_p99_s": _pct(fw, 99),
                "first_turn_admits": fa,
                "busy_frac": self._busy[k] / self.w,
                "prefill_tok_per_s": self._pf_tokens[k] / self.w,
                "hits": hit,
                "evictions": self._evictions[k],
                "evictions_per_s": self._evictions[k] / self.w,
            })
            if self.dyn_on:
                rows[-1]["preemptions"] = self._preempts[k]
                rows[-1]["recompute_tokens"] = self._recompute[k]
                rows[-1]["recompute_processed"] = self._recompute_done[k]
                rows[-1]["lost_prefill"] = self._lost[k]
                rows[-1]["preempt_max_turn"] = self._pre_max[k]
        return rows

    def backlog_trace(self) -> List[Tuple[float, float, float]]:
        """(t_start, mean, max-bound) of waiting queue + gate queue per fine bucket (max-bound = sum of maxes)."""
        fw = self.q_fine.w
        n = min(len(self.q_fine.out), len(self.gate_fine.out))
        return [(i * fw, self.q_fine.out[i][0] + self.gate_fine.out[i][0],
                 self.q_fine.out[i][1] + self.gate_fine.out[i][1]) for i in range(n)]

    def queue_trace(self) -> List[Tuple[float, float, float]]:
        """(t_start, mean, max) of the waiting queue per fine bucket (complete buckets only)."""
        fw = self.q_fine.w
        return [(i * fw, m, x) for i, (m, x) in enumerate(self.q_fine.out)]


# ----------------------------------------------------------------- post-hoc summaries
def tail_stats(rows: List[Dict[str, float]], t_from: float, t_to: float) -> Dict[str, float]:
    """Aggregate complete windows with t_start >= t_from and t_end <= t_to."""
    sel = [r for r in rows if r["t_start"] >= t_from - 1e-9 and r["t_end"] <= t_to + 1e-9]
    if not sel:
        return {"n_windows": 0, "hit_rate": float("nan"), "queue_mean": float("nan"),
                "queue_max": float("nan"), "gate_mean": float("nan"), "turns_per_s": float("nan"),
                "sessions_per_s": float("nan"), "busy_frac": float("nan")}
    adm = sum(r["admitted_turns"] for r in sel)
    hits = sum(r["hits"] for r in sel)
    return {
        "n_windows": len(sel),
        "hit_rate": hits / adm if adm else float("nan"),
        "queue_mean": float(np.mean([r["queue_mean"] for r in sel])),
        "queue_max": float(np.max([r["queue_max"] for r in sel])),
        "gate_mean": float(np.mean([r["gate_mean"] for r in sel])),
        "turns_per_s": float(np.mean([r["turns_per_s"] for r in sel])),
        "sessions_per_s": float(np.mean([r["sessions_per_s"] for r in sel])),
        "busy_frac": float(np.mean([r["busy_frac"] for r in sel])),
    }


def trend_rise(trace: List[Tuple[float, float, float]], t_from: float, t_to: float) -> float:
    """OLS slope of the fine queue-mean series on [t_from, t_to), times (t_to - t_from): the fitted
    rise (in requests) across the interval. NaN if fewer than 3 buckets."""
    pts = [(t, m) for (t, m, _) in trace if t >= t_from - 1e-9 and t < t_to - 1e-9]
    if len(pts) < 3:
        return float("nan")
    x = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    slope = np.polyfit(x, y, 1)[0]
    return float(slope * (t_to - t_from))


def longest_run_below(values: Sequence[float], thresh: float) -> int:
    """Longest run of consecutive entries with value < thresh (NaN breaks a run)."""
    best = cur = 0
    for v in values:
        if v == v and v < thresh:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def trailing_low_hit_onset(t_start: Sequence[float], hit_rate: Sequence[float], thresh: float, width: float
                           ) -> float:
    """Start time of the maximal TRAILING run of consecutive complete windows whose hit rate is < ``thresh`` (a NaN hit
    rate, i.e. a window without admissions, breaks the run; so does a gap in ``t_start``). NaN if the last window is not
    below the threshold. This is the single event time of the escape experiments (round-2 review finding 9)."""
    t = list(t_start)
    h = list(hit_rate)
    onset = float("nan")
    i = len(t) - 1
    while i >= 0:
        if not (h[i] == h[i] and h[i] < thresh):
            break
        if i + 1 < len(t) and abs(t[i + 1] - t[i] - width) > 1e-6:
            break
        onset = float(t[i])
        i -= 1
    return onset


def first_good_window(rows: List[Dict[str, float]], hit_above: float, backlog_below: float) -> float:
    """Start time of the first complete window with hit rate > ``hit_above`` AND (waiting queue + gate queue) mean
    < ``backlog_below``; NaN if there is none. (Time to first good window; a lower bound on the recovery time.)"""
    for r in sorted(rows, key=lambda x: x["t_start"]):
        hr = r["hit_rate"]
        if hr == hr and hr > hit_above and (r["queue_mean"] + r["gate_mean"]) < backlog_below:
            return float(r["t_start"])
    return float("nan")
