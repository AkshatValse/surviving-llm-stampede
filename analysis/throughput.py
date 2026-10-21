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
* Uncached prefill tokens/s (``uncached_tokens_per_s``): sum over the ok turns completing in the interval of
  ``prompt_tokens - cached_tokens`` (a missing ``cached_tokens`` counts as 0 once the run reports it at all; NaN if no
  request of the run reports it), divided by the interval. This is the unit criterion (a) of the trap test uses: in a trap
  with a growing backlog the sessions in progress are mostly early in their lives and early turns have short prompts, so
  the session completion rate runs ABOVE the closed-population lambda_miss while the prefill-token rate stays at the
  all-miss capacity (review of 2026-10-21, finding 1; sessions/s vs tokens/s on the simulator's own traps in
  ``results/agentload_trap_sim_traces``).
* Outstanding backlog (``outstanding_*``): requests in flight at the client + sessions waiting at the client gate. It is the
  closest client-side analogue of the simulator's "waiting queue + gate" (``prefixmeta/sim.py``): it excludes sessions
  asleep in tool time, which the sessions-in-system backlog counts.
* Hit fraction: ``hit_frac_turns`` = fraction of ok turns with cached_tokens / prompt_tokens > the analysis threshold
  (the windows' ``frac_turns_cached_gt50``, first turns included, so < 1 even for a perfect cache),
  ``hit_frac_followup`` the same over turns >= 2 only, ``cached_frac_tokens`` = sum(cached) / sum(prompt).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

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


# ---------------------------------------------------------------- outstanding backlog (requests in flight + gate queue)
def outstanding_events(run: Run) -> Tuple[np.ndarray, np.ndarray]:
    """Event times and the number of outstanding units after each event: +1 when a request is sent, -1 when it
    completes (any status), +1 when a session arrives at a client gate that makes it wait, -1 when it is admitted (or ends
    still queued). Gate intervals come from sessions.csv (``arrival_s`` -> ``t_admit``; ``t_end`` if never admitted) and
    exist only for sessions with ``gate_wait_s`` > 0."""
    ts: List[np.ndarray] = []
    ds: List[np.ndarray] = []
    if len(run.requests):
        rq = run.requests
        ts += [rq["t_send"].to_numpy(dtype=float), rq["t_complete"].to_numpy(dtype=float)]
        ds += [np.ones(len(rq)), -np.ones(len(rq))]
    ses = run.sessions
    if len(ses) and "gate_wait_s" in ses.columns and "t_admit" in ses.columns:
        waited = ses[ses["gate_wait_s"].fillna(0.0) > 0.0]
        if len(waited):
            t_out = waited["t_admit"].where(waited["t_admit"].notna(), waited["t_end"]).to_numpy(dtype=float)
            t_in = waited["arrival_s"].to_numpy(dtype=float)
            ts += [t_in, t_out]
            ds += [np.ones(len(waited)), -np.ones(len(waited))]
    if not ts:
        return np.zeros(0), np.zeros(0)
    t, d = np.concatenate(ts), np.concatenate(ds)
    keep = np.isfinite(t)
    t, d = t[keep], d[keep]
    order = np.lexsort((-d, t))
    return t[order], np.cumsum(d[order])


def outstanding_mean(run: Run, t0: float, t1: float) -> float:
    """Time-average number of outstanding units (requests in flight + gated sessions) on [t0, t1)."""
    if t1 <= t0:
        return NAN
    t, v = outstanding_events(run)
    if len(t) == 0:
        return NAN
    return float(step_bins(t, v, np.array([t0, t1]))[0][0])


def outstanding_at(run: Run, t: float) -> float:
    te, v = outstanding_events(run)
    i = int(np.searchsorted(te, t, side="right"))
    return float(v[i - 1]) if i > 0 else 0.0


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
    prompt_sum, uncached_sum, cached_reported = _prompt_token_sums(ok, r)
    return {"interval_s": dur, "n_sessions_completed": n_sessions, "n_turns_completed": n_turns,
            "sessions_per_s": n_sessions / dur, "turns_per_s": n_turns / dur,
            "turns_based_per_s": (n_turns / dur) / et, "effective_mean_turns": et,
            "prompt_tokens_per_s": prompt_sum / dur, "cached_reported": cached_reported,
            "uncached_tokens_per_s": (uncached_sum / dur) if cached_reported else NAN}


def _prompt_token_sums(ok: pd.DataFrame, all_requests: pd.DataFrame) -> Tuple[float, float, bool]:
    """(sum of prompt tokens, sum of uncached prompt tokens, whether the run reports cached_tokens at all) of the ok
    requests ``ok`` (a slice of ``all_requests``). Prompt tokens: the server's count, else the client's."""
    prompt = ok["prompt_tokens"].where(ok["prompt_tokens"].notna(), ok["prompt_tokens_client"]).astype(float)
    cached = ok["cached_tokens"].fillna(0.0).astype(float)
    reported = bool(all_requests["cached_tokens"].notna().any()) if "cached_tokens" in all_requests.columns else False
    return float(prompt.sum()), float((prompt - cached).sum()), reported


RATE_ESTIMATORS = ("uncached_tokens", "sessions", "turns_based")


def pick_rate(rates: Dict[str, Any], estimator: str) -> float:
    if estimator == "uncached_tokens":
        return float(rates["uncached_tokens_per_s"])
    if estimator == "sessions":
        return float(rates["sessions_per_s"])
    if estimator == "turns_based":
        return float(rates["turns_based_per_s"])
    raise ValueError(f"rate estimator must be {'|'.join(RATE_ESTIMATORS)}, got {estimator!r}")


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
