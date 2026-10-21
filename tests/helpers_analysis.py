"""Builders for synthetic analysis inputs (no files, no server)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from analysis.load import Run
from analysis.params import AnalysisParams, load_params
from conftest import REPO, make_raw

REQ_COLS = ["req_id", "sid", "turn", "n_turns", "t_send", "t_complete", "latency_s", "status", "prompt_tokens",
            "prompt_tokens_client", "cached_tokens"]


def params(*overrides: str) -> AnalysisParams:
    return load_params(REPO / "configs" / "agentload_analysis.yaml", list(overrides))


def req_df(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    for c in REQ_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df["status"] = df["status"].fillna("ok")
    if df["latency_s"].isna().any():
        df["latency_s"] = df["latency_s"].fillna(df["t_complete"] - df["t_send"])
    if df["prompt_tokens_client"].isna().all():
        df["prompt_tokens_client"] = df["prompt_tokens"]
    return df


def fake_run(requests: pd.DataFrame, t_end: float, *, metrics: Optional[pd.DataFrame] = None, aborted: bool = False,
             label: str = "cell", seed: int = 0, burst_t: Optional[float] = None, rate_mult: Optional[float] = None,
             cfg_extra: Optional[Dict[str, Any]] = None) -> Run:
    raw = make_raw(arrivals={"rate": 1.0, "burst": ({"n": 5, "t_s": burst_t, "width_s": 1.0} if burst_t is not None
                                                      else None), "rate_mult": rate_mult})
    if rate_mult is not None:
        raw["arrivals"]["rate"] = None
        raw["arrivals"]["lambda_ref"] = 1.0
    if cfg_extra:
        raw.update(cfg_extra)
    met = metrics if metrics is not None else pd.DataFrame(columns=["t_s", "name", "labels", "value"])
    return Run(dir=Path("/nonexistent"), meta={"engine_label": label, "seeds": [seed]}, cfg=raw, requests=requests,
               sessions=pd.DataFrame(), metrics=met, t_end_s=t_end, aborted=aborted,
               abort_reason="max_inflight>5" if aborted else None)


def mk_win(hits: Sequence[float], queues: Sequence[float], W: float = 1000.0, n_turns: int = 100) -> pd.DataFrame:
    """A window table like analysis.windows.window_table produces (turn-count metric)."""
    rows: List[Dict[str, Any]] = []
    for k, (h, q) in enumerate(zip(hits, queues)):
        n_hit = int(round(h * n_turns)) if h == h else 0
        rows.append({"window": k, "t_start": k * W, "t_end": (k + 1) * W, "n_turns_ok": n_turns if h == h else 0,
                     "n_cached_gt": n_hit, "hit_rate": h, "queue_mean": q, "prompt_tokens": 1000.0 * n_turns,
                     "cached_tokens": 1000.0 * n_hit, "hit_source": "requests:frac_turns_cached_gt50"})
    return pd.DataFrame(rows)
