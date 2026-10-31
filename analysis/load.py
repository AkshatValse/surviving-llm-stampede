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
    def t_burst_ref(self) -> Optional[float]:
        """The burst time the post-burst window is anchored to: the run's own burst, else (NOBURST arm) the recorded
        ``arrivals.analysis_t_burst_s`` of the paired BURST arm."""
        if self.t_burst is not None:
            return self.t_burst
        v = (self.cfg.get("arrivals") or {}).get("analysis_t_burst_s")
        return float(v) if v is not None else None

    @property
    def arm(self) -> str:
        """Explicit ``meta.arm`` recorded by the job script ("" if the run is not part of a paired set)."""
        return str(self.meta.get("arm") or (self.cfg.get("meta") or {}).get("arm") or "")

    @property
    def gate_n_cap(self) -> Optional[int]:
        v = self.meta.get("gate_n_cap_resolved")
        return int(v) if v is not None else None

    @property
    def gate_mode(self) -> str:
        """Gate mode: ``meta.gate_mode`` (rescue runs record it), else the config's ``gate.mode``, else "static"."""
        v = self.meta.get("gate_mode") or (self.cfg.get("gate") or {}).get("mode")
        return str(v) if v else "static"

    @property
    def arm_derived(self) -> str:
        """What the config structurally implies: gate.mode rescue -> rescue (checked first: a rescue run records its engaged
        cap in gate_n_cap_resolved); no burst -> noburst; burst + gate -> capped; burst -> burst."""
        if self.gate_mode == "rescue":
            return "rescue"
        if self.t_burst is None:
            return "noburst"
        capped = self.gate_n_cap is not None or (self.cfg.get("gate") or {}).get("n_cap") is not None
        return "capped" if capped else "burst"

    @property
    def lam(self) -> Optional[float]:
        """Resolved constant arrival rate, sessions/s (recorded in meta.json at run start)."""
        v = self.meta.get("resolved_rate_sessions_per_s")
        return float(v) if v is not None else None

    @property
    def lambda_ref_value(self) -> Optional[float]:
        """lambda_miss the rate was set from (sessions/s): resolved ``arrivals.lambda_ref`` as recorded at run start,
        else rate / rate_mult."""
        v = self.meta.get("lambda_ref_resolved")
        if v is not None:
            return float(v)
        if self.lam is not None and self.rate_mult:
            return self.lam / self.rate_mult
        return None

    @property
    def uncached_tokens_ref_value(self) -> Optional[float]:
        """All-miss uncached prefill tokens/s (E0a) the run's trap criterion (a) is judged against, as resolved at run start
        from ``arrivals.uncached_tokens_ref`` (None if the run did not record it)."""
        v = self.meta.get("uncached_tokens_ref_resolved")
        return float(v) if v is not None else None

    @property
    def prereg_sha256(self) -> Optional[str]:
        """sha256 of the committed pre-registration file the job script validated before this run (None: not bound)."""
        v = self.meta.get("prereg_sha256") or (self.cfg.get("meta") or {}).get("prereg_sha256")
        return str(v) if v else None

    @property
    def t0_unix(self) -> Optional[float]:
        """Wall-clock time (unix seconds) at which the run clock started; falls back to the parsed ``start_time``."""
        v = self.meta.get("t0_unix")
        if v is not None:
            return float(v)
        st = self.meta.get("start_time")
        if st:
            try:
                from datetime import datetime
                return datetime.fromisoformat(str(st)).timestamp()
            except ValueError:
                return None
        return None

    @property
    def lambda_ref_key(self) -> str:
        """Key part of ``arrivals.lambda_ref = 'path:key'`` ("" for a plain number)."""
        ref = (self.cfg.get("arrivals") or {}).get("lambda_ref")
        return ref.rsplit(":", 1)[1] if isinstance(ref, str) and ":" in ref else ""

    @property
    def closed_n(self) -> Optional[int]:
        a = self.cfg.get("arrivals") or {}
        return int(a["closed_n"]) if a.get("kind") == "closed" and a.get("closed_n") else None

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
    for c in ("arrival_s", "t_first_send", "t_end", "t_admit", "gate_wait_s", "n_turns", "turns_completed"):
        if c in ses.columns:
            ses[c] = pd.to_numeric(ses[c], errors="coerce")
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
