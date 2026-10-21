"""Throughput, backlog and hit statistics of one run over an arbitrary time interval.

Shared by the Stage-C closed-population analysis (``analysis.closed``) and the throughput-based trap criterion
(``analysis.trap_v2``). Conventions:

* A request belongs to the interval of its completion time ``t_complete``: ``t0 <= t_complete < t1``.
* Session completion rate (sessions/s), two estimators of the same estimand:
  ``sessions``     number of completed sessions (their last turn completed ok) / (t1 - t0)   [literal];
  ``turns_based``  ok turns / (t1 - t0) / E[T]  with E[T] = E[min(Geom(1/mean_turns), max_turns)]   [lower variance].
* Backlog = client sessions in the system = arrived (planned arrival time) minus ended (completed or failed). Sessions
  waiting at the client-side gate (CAPPED arm) are in the system; sessions cancelled at the end of the run are not
  "ended". For an uncapped run this equals the number of active sessions (in the engine queue, running, or in a
  tool-time sleep); by Little's law its healthy level is about lambda * (mean session duration), mostly tool time.
* Hit fraction: ``hit_frac_turns`` = fraction of ok turns with cached_tokens / prompt_tokens > the analysis threshold
  (the windows' ``frac_turns_cached_gt50``, first turns included, so < 1 even for a perfect cache),
  ``hit_frac_followup`` the same over turns >= 2 only, ``cached_frac_tokens`` = sum(cached) / sum(prompt).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from agentload.config import config_from_dict
from agentload.workload import effective_mean_turns

from .load import Run
from .params import AnalysisParams
from .windows import _prepare_requests, step_bins

NAN = float("nan")


# ---------------------------------------------------------------- backlog
def backlog_events(ses: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Event times and the number of sessions in the system after each event (+1 at arrival, -1 when a session
    completed or failed). Needs sessions.csv columns ``arrival_s``, ``t_end``, ``status``."""
    if len(ses) == 0:
        return np.zeros(0), np.zeros(0)
    arr = ses["arrival_s"].to_numpy(dtype=float)
    ended = ses["status"].isin(["completed", "failed"]).to_numpy() & ses["t_end"].notna().to_numpy()
    te = ses["t_end"].to_numpy(dtype=float)[ended]
    t = np.concatenate([arr, te])
    d = np.concatenate([np.ones(len(arr)), -np.ones(len(te))])
    order = np.lexsort((-d, t))                           # by time; arrivals before departures at equal times
    return t[order], np.cumsum(d[order])


def backlog_mean(ses: pd.DataFrame, t0: float, t1: float) -> float:
    """Time-average number of sessions in the system on [t0, t1)."""
    if t1 <= t0 or len(ses) == 0:
        return NAN
    t, v = backlog_events(ses)
    return float(step_bins(t, v, np.array([t0, t1]))[0][0])


def backlog_at(ses: pd.DataFrame, t: float) -> float:
    """Number of sessions in the system at time t (right-continuous)."""
    te, v = backlog_events(ses)
    i = int(np.searchsorted(te, t, side="right"))
    return float(v[i - 1]) if i > 0 else 0.0


def backlog_slope(ses: pd.DataFrame, t0: float, t1: float, dt: float) -> Tuple[float, int]:
    """OLS slope (sessions/s) of the backlog's bin means (bins of width ``dt``) over [t0, t1), and the number of bins.
    NaN if fewer than 3 bins."""
    nb = int(np.floor((t1 - t0) / dt + 1e-9))
    if nb < 3 or len(ses) == 0:
        return NAN, max(nb, 0)
    edges = t0 + dt * np.arange(nb + 1)
    t, v = backlog_events(ses)
    mean, _ = step_bins(t, v, edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return float(np.polyfit(centers, mean, 1)[0]), nb


def backlog_trace(ses: pd.DataFrame, t0: float, t1: float, dt: float) -> pd.DataFrame:
    """Backlog bin means on [t0, t1) in bins of ``dt`` (for plots / CSV)."""
    nb = int(np.floor((t1 - t0) / dt + 1e-9))
    if nb < 1 or len(ses) == 0:
        return pd.DataFrame({"t_start": [], "backlog_mean": []})
    edges = t0 + dt * np.arange(nb + 1)
    t, v = backlog_events(ses)
    mean, _ = step_bins(t, v, edges)
    return pd.DataFrame({"t_start": edges[:-1], "backlog_mean": mean})


# ---------------------------------------------------------------- rates
def mean_turns_of(run: Run) -> float:
    return effective_mean_turns(config_from_dict(run.cfg).workload)


def completion_rates(run: Run, t0: float, t1: float) -> Dict[str, Any]:
    """Session completion rate over [t0, t1) by both estimators (sessions/s), plus raw counts."""
    dur = t1 - t0
    if dur <= 0:
        raise ValueError("empty interval")
    r = run.requests
    ok = r[(r["status"] == "ok") & (r["t_complete"] >= t0) & (r["t_complete"] < t1)]
    n_turns = int(len(ok))
    n_sessions = int((ok["turn"] == ok["n_turns"]).sum())
    et = mean_turns_of(run)
    return {"interval_s": dur, "n_sessions_completed": n_sessions, "n_turns_completed": n_turns,
            "sessions_per_s": n_sessions / dur, "turns_per_s": n_turns / dur,
            "turns_based_per_s": (n_turns / dur) / et, "effective_mean_turns": et}


def pick_rate(rates: Dict[str, Any], estimator: str) -> float:
    if estimator == "sessions":
        return float(rates["sessions_per_s"])
    if estimator == "turns_based":
        return float(rates["turns_based_per_s"])
    raise ValueError(f"rate estimator must be sessions|turns_based, got {estimator!r}")


# ---------------------------------------------------------------- hit
def hit_stats(run: Run, p: AnalysisParams, t0: float, t1: float) -> Dict[str, Any]:
    """Hit fractions of the ok turns completing in [t0, t1). NaN where undefined (no requests, or the server reports no
    cached counts at all: ``cached_available`` False)."""
    r = _prepare_requests(run, p)
    sel = r[(r["t_complete"] >= t0) & (r["t_complete"] < t1)]
    avail = bool(r["cached_reported"].any())
    n = len(sel)
    out: Dict[str, Any] = {"n_turns": int(n), "cached_available": avail, "hit_frac_turns": NAN,
                           "hit_frac_followup": NAN, "cached_frac_tokens": NAN}
    if not avail or n == 0:
        return out
    fu = sel[sel["turn"] >= 2]
    out["hit_frac_turns"] = float(sel["cached_gt"].mean())
    out["hit_frac_followup"] = float(fu["cached_gt"].mean()) if len(fu) else NAN
    d = float(sel["prompt_eff"].sum())
    out["cached_frac_tokens"] = float(sel["cached_eff"].sum() / d) if d else NAN
    return out


def hit_value(h: Dict[str, Any], p: AnalysisParams) -> float:
    """The hit number the analysis config selects (``windows.hit_metric``)."""
    return float(h["cached_frac_tokens"] if p.w["hit_metric"] == "token_hit_rate" else h["hit_frac_turns"])
