"""Analysis parameters loaded from ``configs/agentload_analysis.yaml``."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml


@dataclass(frozen=True)
class MetricRole:
    names: List[str]
    agg: str      # sum | mean


@dataclass
class AnalysisParams:
    raw: Dict[str, Any]

    @property
    def w(self) -> Dict[str, Any]:
        return self.raw["windows"]

    @property
    def window_s(self) -> float:
        return float(self.w["window_s"])

    @property
    def fine_window_s(self) -> float:
        return float(self.w["fine_window_s"])

    @property
    def burst(self) -> Dict[str, Any]:
        return self.raw["burst"]

    @property
    def stability(self) -> Dict[str, Any]:
        return self.raw["stability"]

    @property
    def escape(self) -> Dict[str, Any]:
        return self.raw["escape"]

    @property
    def kill(self) -> Dict[str, Any]:
        return self.raw["kill"]

    def role(self, name: str) -> MetricRole:
        d = self.raw["engine_metrics"][name]
        return MetricRole(names=list(d["names"]), agg=str(d["agg"]))


def load_params(path: str | Path, overrides: Optional[Sequence[str]] = None) -> AnalysisParams:
    raw = yaml.safe_load(Path(path).read_text())
    raw = copy.deepcopy(raw)
    for item in overrides or []:
        key, val = item.split("=", 1)
        node = raw
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = yaml.safe_load(val)
    return AnalysisParams(raw)
