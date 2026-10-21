"""Load one agentload result directory into DataFrames."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml


@dataclass
class Run:
    dir: Path
    meta: Dict[str, Any]
    cfg: Dict[str, Any]                  # effective config (after overrides)
    requests: pd.DataFrame
    sessions: pd.DataFrame
    metrics: pd.DataFrame                # long format: t_s, name, labels, value (may be empty)
    t_end_s: float                       # run length used to decide which windows are complete
    aborted: bool = False
    abort_reason: Optional[str] = None
    t_abort_s: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return str(self.meta.get("engine_label", "?"))

    @property
    def seed(self) -> int:
        return int(self.meta["seeds"][0])

    @property
    def t_burst(self) -> Optional[float]:
        b = (self.cfg.get("arrivals") or {}).get("burst")
        return float(b["t_s"]) if b else None

    @property
    def hardware(self) -> Optional[str]:
        return self.meta.get("hardware")

    @property
    def start_state_verified(self) -> Optional[bool]:
        v = self.meta.get("start_state_verified")
        return None if v is None else bool(v)

    @property
    def output_ids_sources(self) -> Dict[str, int]:
        """ok requests per output_ids_source (from meta.outcome; recomputed from requests.csv for older runs)."""
        c = (self.meta.get("outcome") or {}).get("output_ids_source_counts")
        if c is not None:
            return {str(k): int(v) for k, v in c.items()}
        if "output_ids_source" in self.requests.columns and "status" in self.requests.columns:
            ok = self.requests[self.requests["status"] == "ok"]["output_ids_source"].dropna()
            return {str(k): int(v) for k, v in ok.value_counts().items()}
        return {}

    @property
    def rate_mult(self) -> Optional[float]:
        v = (self.cfg.get("arrivals") or {}).get("rate_mult")
        return float(v) if v is not None else None


def load_run(run_dir: str | Path) -> Run:
    d = Path(run_dir)
    meta = json.loads((d / "meta.json").read_text())
    cfg = yaml.safe_load((d / "config_effective.yaml").read_text())
    req = pd.read_csv(d / "requests.csv")
    for c in ("t_send", "t_headers", "t_complete", "latency_s", "prompt_tokens", "prompt_tokens_client",
              "completion_tokens", "cached_tokens", "turn", "n_turns", "sid"):
        if c in req.columns:
            req[c] = pd.to_numeric(req[c], errors="coerce")
    ses = pd.read_csv(d / "sessions.csv") if (d / "sessions.csv").exists() else pd.DataFrame()
    mpath = d / "metrics.csv"
    met = pd.read_csv(mpath) if mpath.exists() and mpath.stat().st_size > 0 else pd.DataFrame(
        columns=["t_s", "name", "labels", "value"])
    out = meta.get("outcome") or {}
    t_end = out.get("t_end_s")
    if t_end is None:
        t_end = float(np.nanmax(req["t_complete"])) if len(req) else 0.0
    return Run(dir=d, meta=meta, cfg=cfg, requests=req, sessions=ses, metrics=met, t_end_s=float(t_end),
               aborted=bool(out.get("abort_reason")), abort_reason=out.get("abort_reason"),
               t_abort_s=out.get("t_abort_s"))
