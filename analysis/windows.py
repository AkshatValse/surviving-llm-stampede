"""Per-window statistics of an agentload run.

One row per COMPLETE window of ``window_s`` seconds (end <= run end), like the simulator's ``Recorder.finalize``.
A request is assigned to the window of its completion time (default) or send time (``attribute_by``). The
simulator assigns hits to the ADMISSION time, which a client cannot observe; completion time differs from it by
the service time only (seconds, vs. 1000 s windows).

Hit definitions (both reported; ``hit_rate`` is the one chosen by ``windows.hit_metric``):

* ``token_hit_rate``           = sum(cached_tokens) / sum(prompt_tokens)               (continuous)
* ``frac_turns_cached_gt50``   = fraction of turns with cached_tokens / prompt_tokens > threshold (default 0.5);
  the analogue of the simulator's per-turn hit/miss ``hit_rate`` (a first turn is always a miss in both).

If no request in the run reports a cached count, the cached columns are NaN and ``cached_available`` is False
(the engine counters, if present, give ``engine_counter_hit_rate``). If some requests report it and some do not,
the missing ones are counted as 0 cached tokens and tallied in ``n_cached_missing_as_zero`` (assumption: an
engine that reports cached counts but omits the field means 0; to be verified on the real engines).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .load import Run
from .params import AnalysisParams, MetricRole


# ---------------------------------------------------------------- step-function binning
def step_bins(t_events: np.ndarray, v_after: np.ndarray, edges: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Time-average and max of a right-continuous step function in bins ``[edges[j], edges[j+1])``.
    ``f(t) = v_after[i]`` on ``[t_events[i], t_events[i+1])`` and 0 before the first event."""
    nb = len(edges) - 1
    mean = np.zeros(nb)
    mx = np.zeros(nb)
    for j in range(nb):
        a, b = edges[j], edges[j + 1]
        i0 = int(np.searchsorted(t_events, a, side="right"))
        cur = float(v_after[i0 - 1]) if i0 > 0 else 0.0
        i1 = int(np.searchsorted(t_events, b, side="left"))
        times = np.concatenate([[a], t_events[i0:i1], [b]])
        vals = np.concatenate([[cur], v_after[i0:i1]])
        mean[j] = float(np.sum(vals * np.diff(times)) / (b - a))
        mx[j] = float(np.max(vals))
    return mean, mx


def inflight_events(req: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Event times and in-flight count after each event (+1 at send, -1 at completion, all statuses)."""
    ts = req["t_send"].to_numpy(dtype=float)
    tc = req["t_complete"].to_numpy(dtype=float)
    t = np.concatenate([ts, tc])
    d = np.concatenate([np.ones(len(ts)), -np.ones(len(tc))])
    order = np.lexsort((-d, t))                 # by time; +1 before -1 at equal times
    return t[order], np.cumsum(d[order])


def n_complete_windows(t_end: float, w: float) -> int:
    return int(math.floor(t_end / w + 1e-9))


# ---------------------------------------------------------------- engine metrics
def pick_series(metrics: pd.DataFrame, role: MetricRole) -> Tuple[Optional[str], pd.DataFrame]:
    """First candidate name present; values aggregated across label sets at each scrape time."""
    if metrics is None or len(metrics) == 0:
        return None, pd.DataFrame(columns=["t_s", "value"])
    for name in role.names:
        sub = metrics[metrics["name"] == name]
        if len(sub):
            g = sub.groupby("t_s")["value"]
            s = g.sum() if role.agg == "sum" else g.mean()
            return name, s.reset_index().sort_values("t_s")
    return None, pd.DataFrame(columns=["t_s", "value"])


def _gauge_bins(series: pd.DataFrame, edges: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Mean and max of scrape samples within each bin (NaN where a bin has no sample)."""
    nb = len(edges) - 1
    mean = np.full(nb, np.nan)
    mx = np.full(nb, np.nan)
    if len(series) == 0:
        return mean, mx
    t = series["t_s"].to_numpy()
    v = series["value"].to_numpy()
    idx = np.searchsorted(edges, t, side="right") - 1
    for j in range(nb):
        sel = v[idx == j]
        if len(sel):
            mean[j], mx[j] = float(np.mean(sel)), float(np.max(sel))
    return mean, mx


def _counter_delta(series: pd.DataFrame, a: float, b: float) -> float:
    """Increase of a cumulative counter over [a, b] using the last sample <= each end (first sample if none)."""
    if len(series) < 2:
        return float("nan")
    t = series["t_s"].to_numpy()
    v = series["value"].to_numpy()
    ia = max(int(np.searchsorted(t, a, side="right")) - 1, 0)
    ib = max(int(np.searchsorted(t, b, side="right")) - 1, 0)
    return float(v[ib] - v[ia])


# ---------------------------------------------------------------- request-derived columns
def _prepare_requests(run: Run, p: AnalysisParams) -> pd.DataFrame:
    r = run.requests.copy()
    r = r[r["status"] == "ok"].copy()
    prompt = r["prompt_tokens"].where(r["prompt_tokens"].notna(), r["prompt_tokens_client"])
    r["prompt_eff"] = prompt.astype(float)
    reported = r["cached_tokens"].notna()
    r["cached_reported"] = reported
    r["cached_eff"] = r["cached_tokens"].fillna(0.0).astype(float)
    r["cached_frac"] = np.where(r["prompt_eff"] > 0, r["cached_eff"] / r["prompt_eff"], np.nan)
    thr = float(p.w["cached_frac_threshold"])
    r["cached_gt"] = r["cached_frac"] > thr
    key = "t_complete" if p.w["attribute_by"] == "complete" else "t_send"
    r["t_attr"] = r[key]
    return r


def window_table(run: Run, p: AnalysisParams, window_s: Optional[float] = None) -> pd.DataFrame:
    """One row per complete window; see the module docstring for column semantics."""
    W = float(window_s or p.window_s)
    nw = n_complete_windows(run.t_end_s, W)
    edges = np.arange(nw + 1) * W
    ok = _prepare_requests(run, p)
    allreq = run.requests
    cached_available = bool(ok["cached_reported"].any())

    # client in-flight (exact) and engine metrics
    ev_t, ev_v = inflight_events(allreq) if len(allreq) else (np.zeros(0), np.zeros(0))
    infl_mean, infl_max = step_bins(ev_t, ev_v, edges) if nw else (np.zeros(0), np.zeros(0))
    roles = {k: pick_series(run.metrics, p.role(k)) for k in ("waiting", "running", "cache_usage", "hit_gauge",
                                                             "hit_counter", "query_counter")}
    wait_mean, wait_max = _gauge_bins(roles["waiting"][1], edges)
    run_mean, run_max = _gauge_bins(roles["running"][1], edges)
    cu_mean, _ = _gauge_bins(roles["cache_usage"][1], edges)
    hg_mean, _ = _gauge_bins(roles["hit_gauge"][1], edges)
    have_engine_queue = roles["waiting"][0] is not None

    rows: List[Dict[str, float]] = []
    for k in range(nw):
        a, b = edges[k], edges[k + 1]
        sel = ok[(ok["t_attr"] >= a) & (ok["t_attr"] < b)]
        n = len(sel)
        fu = sel[sel["turn"] >= 2]
        row: Dict[str, float] = {"window": k, "t_start": a, "t_end": b, "n_turns_ok": n,
                                 "turns_per_s": n / W}
        last = sel[(sel["turn"] == sel["n_turns"])]
        row["sessions_per_s"] = len(last) / W
        cached_cols = ["token_hit_rate", "cached_tokens", "n_cached_gt", "frac_turns_cached_gt50", "n_followup",
                       "n_cached_gt_followup", "frac_turns_cached_gt50_followup", "n_cached_missing_as_zero"]
        row["prompt_tokens"] = float(sel["prompt_eff"].sum()) if n else np.nan
        if cached_available and n:
            row["cached_tokens"] = float(sel["cached_eff"].sum())
            row["token_hit_rate"] = row["cached_tokens"] / row["prompt_tokens"] if row["prompt_tokens"] else np.nan
            row["n_cached_gt"] = int(sel["cached_gt"].sum())
            row["frac_turns_cached_gt50"] = row["n_cached_gt"] / n
            row["n_followup"] = len(fu)
            row["n_cached_gt_followup"] = int(fu["cached_gt"].sum())
            row["frac_turns_cached_gt50_followup"] = (row["n_cached_gt_followup"] / len(fu)) if len(fu) else np.nan
            row["n_cached_missing_as_zero"] = int((~sel["cached_reported"]).sum())
        else:
            for c in cached_cols:
                row[c] = np.nan
        lat = sel["latency_s"].to_numpy()
        for q in (50, 90, 99):
            row[f"lat_p{q}_s"] = float(np.percentile(lat, q)) if n else np.nan
        ft = sel[sel["turn"] == 1]["latency_s"].to_numpy()
        row["first_turn_lat_mean_s"] = float(np.mean(ft)) if len(ft) else np.nan
        row["first_turn_lat_p99_s"] = float(np.percentile(ft, 99)) if len(ft) else np.nan
        row["inflight_mean"], row["inflight_max"] = float(infl_mean[k]), float(infl_max[k])
        row["engine_waiting_mean"], row["engine_waiting_max"] = float(wait_mean[k]), float(wait_max[k])
        row["engine_running_mean"], row["engine_running_max"] = float(run_mean[k]), float(run_max[k])
        row["cache_usage_mean"] = float(cu_mean[k])
        row["engine_hit_gauge_mean"] = float(hg_mean[k])
        hc, qc = roles["hit_counter"][1], roles["query_counter"][1]
        dh, dq = _counter_delta(hc, a, b), _counter_delta(qc, a, b)
        row["engine_counter_hit_rate"] = dh / dq if dq and dq == dq and dq > 0 else np.nan
        if have_engine_queue:
            row["queue_mean"], row["queue_max"], row["queue_source"] = wait_mean[k], wait_max[k], "engine_waiting"
        else:
            row["queue_mean"], row["queue_max"], row["queue_source"] = infl_mean[k], infl_max[k], "client_inflight"
        err = allreq[(allreq["status"] == "error") & (allreq["t_complete"] >= a) & (allreq["t_complete"] < b)]
        can = allreq[(allreq["status"] == "cancelled") & (allreq["t_complete"] >= a) & (allreq["t_complete"] < b)]
        row["n_errors"], row["n_cancelled"] = len(err), len(can)
        row["n_errors_transport"] = int((err["error_kind"] == "transport").sum()) if "error_kind" in err.columns else 0
        rows.append(row)
    df = pd.DataFrame(rows)
    if len(df):
        metric = p.w["hit_metric"]
        df["cached_available"] = cached_available
        if cached_available:
            df["hit_rate"] = df[metric]
            df["hit_source"] = f"requests:{metric}"
        else:                         # no per-request cached counts: fall back to the engine's counters (token-level)
            df["hit_rate"] = df["engine_counter_hit_rate"]
            df["hit_source"] = "engine_counters"
    return df


def queue_trace(run: Run, p: AnalysisParams, bin_s: Optional[float] = None) -> pd.DataFrame:
    """Fine-resolution queue trace (default ``fine_window_s``): t_start, queue_mean, queue_max, source.
    Complete bins only. Engine ``waiting`` metric if present, else the client in-flight count."""
    B = float(bin_s or p.fine_window_s)
    nb = n_complete_windows(run.t_end_s, B)
    edges = np.arange(nb + 1) * B
    name, series = pick_series(run.metrics, p.role("waiting"))
    if name is not None:
        m, x = _gauge_bins(series, edges)
        src = "engine_waiting"
    else:
        t, v = inflight_events(run.requests) if len(run.requests) else (np.zeros(0), np.zeros(0))
        m, x = step_bins(t, v, edges)
        src = "client_inflight"
    return pd.DataFrame({"t_start": edges[:-1], "queue_mean": m, "queue_max": x, "source": src})
