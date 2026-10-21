"""Glue: build and run one simulation from a config dict. Kept separate from experiment orchestration
(``runner.py``) so tests and notebooks can call ``simulate`` directly."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .engine import Engine, EngineParams
from .eviction import eviction_rng
from .mechanisms import AimdParams, make_mechanisms, resolve_session_cap
from .metrics import Recorder, tail_stats, trend_rise
from .policies import make_policy
from .workload import ArrivalPlan, WorkloadParams, build_specs, default_session_cap


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
    stop_backlog_above: Optional[int] = None           # waiting queue + gate queue (round 2)
    stop_low_hit: Optional[Tuple[float, int]] = None   # (hit rate threshold, consecutive complete windows)
    session_cap_override: Optional[int] = None
    debug: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


def resolve_policy(cfg: dict, name: str, ep: EngineParams, wl: WorkloadParams,
                   cap_override: Optional[int] = None):
    """(ordering policy, initial session cap or None, mechanisms) for the named policy spec.

    ``session_cap`` entries: None | int | "auto" (round-1 spec-literal floor(M / mid-session context)) |
    "auto_lb"/"lb" (floor(M / length-biased mean context)) | {lb_mult: x} | {aimd: {...}}. A ``cap_override``
    replaces the cap by a static integer (and drops any AIMD controller)."""
    spec = cfg["policies"][name]
    policy = make_policy(spec)
    cap = spec.get("session_cap")
    aimd: Optional[AimdParams] = None
    if cap == "auto":                 # spec-literal: floor(M / mid-session context)
        cap = default_session_cap(ep.kv_memory_tokens, wl)
    else:
        cap, aimd = resolve_session_cap(cap, ep.kv_memory_tokens, wl)
    if cap_override is not None:
        cap, aimd = cap_override, None
    return policy, (int(cap) if cap is not None else None), make_mechanisms(spec, aimd)


def build_engine(cfg: dict, rs: RunSpec, specs=None):
    """Construct (engine, recorder, session_cap) for ``rs``; ``specs`` may be supplied (tests)."""
    ep = EngineParams.from_dict(deep_update(cfg["engine"], rs.engine_overrides))
    wl = WorkloadParams.from_dict(deep_update(cfg["workload"], rs.workload_overrides))
    policy, cap, mech = resolve_policy(cfg, rs.policy, ep, wl, rs.session_cap_override)
    if specs is None:
        specs = build_specs(wl, rs.plan, rs.seed)
    rec = Recorder(cfg["metrics"]["window_s"], cfg["metrics"]["fine_window_s"])
    rec.mem_on = bool(cfg["metrics"].get("track_memory", False))
    eng = Engine(ep, wl, specs, policy, rec, session_cap=cap, closed=(rs.plan.kind == "closed"),
                 stop_queue_above=rs.stop_queue_above, debug=rs.debug, mech=mech,
                 stop_backlog_above=rs.stop_backlog_above, stop_low_hit=rs.stop_low_hit,
                 evict_rng=eviction_rng(rs.seed) if mech.eviction == "random" else None)
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
    btrace = rec.backlog_trace()
    if rs.plan.kind == "closed" and eng._next_idx >= eng._n:
        raise RuntimeError("closed-population session pool exhausted; increase the pool")

    tail_s = min(cfg["metrics"]["tail_window_s"], eng.end_time / 2.0)
    tl = tail_stats(windows, eng.end_time - tail_s, eng.end_time)
    summary: Dict[str, Any] = {
        "exp": rs.exp, "policy": rs.policy, "seed": rs.seed, "variant": rs.variant,
        "horizon_s": rs.horizon_s, "sim_end_s": eng.end_time,
        "session_cap": cap if cap is not None else -1,
        "eviction": eng.mech.eviction,
        "wall_s": wall,
        "wall_s_per_10k_sim_s": wall / eng.end_time * 1e4 if eng.end_time > 0 else float("nan"),
        "tail_s": tail_s,
        "tail_hit_rate": tl["hit_rate"], "tail_queue_mean": tl["queue_mean"], "tail_queue_max": tl["queue_max"],
        "tail_turns_per_s": tl["turns_per_s"], "tail_sessions_per_s": tl["sessions_per_s"],
        "tail_busy_frac": tl["busy_frac"],
        "tail_queue_trend_rise": trend_rise(qtrace, eng.end_time - tail_s, eng.end_time),
        # backlog = waiting queue + gate queue (a session cap moves backlog from the queue to the gate)
        "tail_gate_mean": tl["gate_mean"],
        "tail_backlog_mean": tl["queue_mean"] + tl["gate_mean"],
        "tail_backlog_trend_rise": trend_rise(btrace, eng.end_time - tail_s, eng.end_time),
        "final_backlog": eng.n_wait + len(eng._gate),
    }
    summary.update(eng.stats())
    summary.update(rs.meta)
    out = {"summary": summary, "windows": windows, "qtrace": qtrace, "btrace": btrace}
    if eng.aimd is not None:
        out["cap_trace"] = list(eng.cap_trace)
    return out
