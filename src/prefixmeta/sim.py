"""Glue: build and run one simulation from a config dict. Kept separate from experiment orchestration
(``runner.py``) so tests and notebooks can call ``simulate`` directly."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .engine import Engine, EngineParams
from .metrics import Recorder, tail_stats, trend_rise
from .policies import make_policy
from .workload import (ArrivalPlan, WorkloadParams, build_specs, default_session_cap, length_biased_session_cap,
                       triangle_rate)


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def deep_update(base: dict, upd: Optional[dict]) -> dict:
    out = copy.deepcopy(base)
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class RunSpec:
    """One simulation run. ``meta`` entries are copied into the output rows."""
    exp: str
    policy: str
    seed: int
    plan: ArrivalPlan
    horizon_s: float
    variant: str = "base"
    engine_overrides: Dict[str, Any] = field(default_factory=dict)
    workload_overrides: Dict[str, Any] = field(default_factory=dict)
    stop_queue_above: Optional[int] = None
    session_cap_override: Optional[int] = None
    debug: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


def resolve_policy(cfg: dict, name: str, ep: EngineParams, wl: WorkloadParams,
                   cap_override: Optional[int] = None):
    spec = cfg["policies"][name]
    policy = make_policy(spec)
    cap = spec.get("session_cap")
    if cap == "auto":                 # spec-literal: floor(M / mid-session context)
        cap = default_session_cap(ep.kv_memory_tokens, wl)
    elif cap == "auto_lb":            # length-bias-corrected: floor(M / turn-weighted mean context)
        cap = length_biased_session_cap(ep.kv_memory_tokens, wl)
    if cap_override is not None:
        cap = cap_override
    return policy, (int(cap) if cap is not None else None)


def build_engine(cfg: dict, rs: RunSpec, specs=None):
    """Construct (engine, recorder, session_cap) for ``rs``; ``specs`` may be supplied (tests)."""
    ep = EngineParams.from_dict(deep_update(cfg["engine"], rs.engine_overrides))
    wl = WorkloadParams.from_dict(deep_update(cfg["workload"], rs.workload_overrides))
    policy, cap = resolve_policy(cfg, rs.policy, ep, wl, rs.session_cap_override)
    if specs is None:
        specs = build_specs(wl, rs.plan, rs.seed)
    rec = Recorder(cfg["metrics"]["window_s"], cfg["metrics"]["fine_window_s"])
    eng = Engine(ep, wl, specs, policy, rec, session_cap=cap, closed=(rs.plan.kind == "closed"),
                 stop_queue_above=rs.stop_queue_above, debug=rs.debug)
    return eng, rec, cap


def simulate(cfg: dict, rs: RunSpec, specs=None) -> Dict[str, Any]:
    """Run one simulation. Returns {'summary': dict, 'windows': [dict], 'qtrace': [(t, mean, max)]}.
    Deterministic given (cfg, rs): all randomness is pre-drawn from SeedSequence(rs.seed)."""
    eng, rec, cap = build_engine(cfg, rs, specs)
    specs = None
    t0 = time.perf_counter()
    eng.run(rs.horizon_s)
    wall = time.perf_counter() - t0
    windows = rec.finalize(eng.end_time)
    qtrace = rec.queue_trace()
    if rs.plan.kind == "closed" and eng._next_idx >= eng._n:
        raise RuntimeError("closed-population session pool exhausted; increase the pool")

    tail_s = min(cfg["metrics"]["tail_window_s"], eng.end_time / 2.0)
    tl = tail_stats(windows, eng.end_time - tail_s, eng.end_time)
    summary: Dict[str, Any] = {
        "exp": rs.exp, "policy": rs.policy, "seed": rs.seed, "variant": rs.variant,
        "horizon_s": rs.horizon_s, "sim_end_s": eng.end_time,
        "session_cap": cap if cap is not None else -1,
        "wall_s": wall,
        "wall_s_per_10k_sim_s": wall / eng.end_time * 1e4 if eng.end_time > 0 else float("nan"),
        "tail_s": tail_s,
        "tail_hit_rate": tl["hit_rate"], "tail_queue_mean": tl["queue_mean"], "tail_queue_max": tl["queue_max"],
        "tail_turns_per_s": tl["turns_per_s"], "tail_sessions_per_s": tl["sessions_per_s"],
        "tail_busy_frac": tl["busy_frac"],
        "tail_queue_trend_rise": trend_rise(qtrace, eng.end_time - tail_s, eng.end_time),
    }
    summary.update(eng.stats())
    summary.update(rs.meta)
    return {"summary": summary, "windows": windows, "qtrace": qtrace}
