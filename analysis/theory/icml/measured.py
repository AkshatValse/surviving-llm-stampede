"""Window statistics of committed trapped runs (read-only; results/nova/, every pull dated 2026-11-01 or earlier).

For one run directory: the sessions in the system (arrived, not ended) sampled every second and averaged in 10 s bins
(the registered backlog statistic), the OLS slope over the window, the session completion rate, the turns served, their
mean turn index and prompt, the follow-up hit fraction, the uncached prompt-token rate, and the gap between a session's
consecutive turn completions (median, and its OLS trend against time: Theorem 1(b) predicts V(t)/t -> gamma).
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
from typing import Dict, List, Optional

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _argval(argv: str, key: str) -> Optional[str]:
    m = re.search(re.escape(key) + r'=("?)([^" ]+)\1', argv)
    return m.group(2) if m else None


def run_info(run_dir: str) -> Dict[str, object]:
    meta = json.load(open(os.path.join(run_dir, "meta.json")))
    argv = " ".join(meta.get("argv", []))
    seed = re.search(r"--seed (\d+)", argv)
    name = re.search(r"--name (\S+)", argv)
    return dict(run_dir=os.path.relpath(run_dir, ROOT).replace(os.sep, "/"), name=name.group(1) if name else None,
                label=_argval(argv, "meta.engine_label"), arm=meta.get("arm") or _argval(argv, "meta.arm"),
                rate_mult=float(_argval(argv, "arrivals.rate_mult")) if _argval(argv, "arrivals.rate_mult") else None,
                seed=int(seed.group(1)) if seed else None, lambda_ref=meta.get("lambda_ref_resolved"),
                tokens_ref=meta.get("uncached_tokens_ref_resolved"), hardware=_argval(argv, "meta.hardware"))


def window_stats(run_dir: str, t0: float, t1: float, t_burst: Optional[float] = 1200.0, bin_s: float = 10.0) -> Dict[str, float]:
    starts: List[float] = []
    ends: List[float] = []
    with open(os.path.join(run_dir, "sessions.csv"), newline="") as f:
        for r in csv.DictReader(f):
            a = float(r["arrival_s"])
            starts.append(a)
            e = r.get("t_end") or ""
            ends.append(float(e) if (e and r.get("status") == "completed") else math.inf)
    starts_a, ends_a = np.sort(np.array(starts)), np.sort(np.array(ends))
    tt = np.arange(t0, t1, 1.0)
    n_sys = np.searchsorted(starts_a, tt, side="right") - np.searchsorted(ends_a, tt, side="right")
    nb = int(len(tt) // bin_s)
    means = n_sys[: nb * int(bin_s)].reshape(nb, int(bin_s)).mean(axis=1)
    centers = t0 + bin_s * (np.arange(nb) + 0.5)
    slope = float(np.polyfit(centers, means, 1)[0])
    span = t1 - t0
    ends_raw = np.array(ends)
    completions = int(((ends_raw >= t0) & (ends_raw < t1)).sum())
    arrivals_win = int(((np.array(starts) >= t0) & (np.array(starts) < t1)).sum())
    arr_since_burst = None
    if t_burst is not None:
        arr_since_burst = int(((np.array(starts) >= t_burst) & (np.array(starts) < t1)).sum())

    last_done: Dict[str, Dict[int, float]] = {}
    turns = []
    with open(os.path.join(run_dir, "requests.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["status"] != "ok":
                continue
            k = int(r["turn"])
            tc = float(r["t_complete"])
            last_done.setdefault(r["sid"], {})[k] = tc
            turns.append((tc, k, int(r["prompt_tokens"] or 0), int(r["cached_tokens"] or 0), r["sid"]))
    win = [x for x in turns if t0 <= x[0] < t1]
    fu = [x for x in win if x[1] > 1]
    hit = sum(1 for x in fu if x[3] > x[2] / 2) / max(1, len(fu))
    gaps_t, gaps = [], []
    for tc, k, pt, ct, sid in fu:
        prev = last_done.get(sid, {}).get(k - 1)
        if prev is not None:
            gaps_t.append(tc)
            gaps.append(tc - prev)
    gaps_t, gaps = np.array(gaps_t), np.array(gaps)
    gap_slope = float(np.polyfit(gaps_t, gaps, 1)[0]) if len(gaps) > 10 else float("nan")
    # cycle trend from 300 s window medians (robust to the tool-time noise)
    med_t, med_g = [], []
    for a in np.arange(t0, t1, 300.0):
        sel = (gaps_t >= a) & (gaps_t < a + 300.0)
        if sel.sum() >= 10:
            med_t.append(a + 150.0)
            med_g.append(float(np.median(gaps[sel])))
    gap_med_slope = float(np.polyfit(med_t, med_g, 1)[0]) if len(med_t) >= 3 else float("nan")
    return dict(
        t0=t0, t1=t1, backlog_slope=slope, N_mean=float(np.mean(means)), N_start=float(means[0]), N_end=float(means[-1]),
        completion_rate=completions / span, arrival_rate_window=arrivals_win / span,
        arrival_rate_since_burst=(arr_since_burst / (t1 - t_burst)) if arr_since_burst is not None else float("nan"),
        turns_per_s=len(win) / span, k_served_mean=float(np.mean([x[1] for x in win])) if win else float("nan"),
        P_served_mean=float(np.mean([x[2] for x in win])) if win else float("nan"),
        fu_hit=hit, uncached_tok_per_s=sum(x[2] - x[3] for x in win) / span,
        gap_median=float(np.median(gaps)) if len(gaps) else float("nan"), gap_slope=gap_slope, gap_med_slope=gap_med_slope,
        n_turns_window=len(win),
    )


def find_runs(pattern: str = "results/nova/**/meta.json") -> List[Dict[str, object]]:
    out = []
    for mp in glob.glob(os.path.join(ROOT, pattern), recursive=True):
        d = os.path.dirname(mp)
        if not (os.path.exists(os.path.join(d, "requests.csv")) and os.path.exists(os.path.join(d, "sessions.csv"))):
            continue
        try:
            out.append(run_info(d))
        except Exception:
            continue
    return out
