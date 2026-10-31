"""Shared helpers of the pred2 drivers: frozen cells, exact client plans, the plan-fed live-KV path, provenance.

The model is the frozen one (tag r13-theory-pred).  The helpers here only (a) build the frozen Model / CurveSummary of a cell
spec exactly as analysis.theory.predict does, (b) rebuild the exact session plans the real jobs send
(agentload.workload.build_open_plan, the generator the jobs run), and (c) feed a plan into the frozen live-KV function
analysis.theory.merged.extras._live_paths in place of its random draws (PlanRNG), so that A's live-demand path and the burst
cohort's peak demand are computed for the actual sessions of a seed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import yaml

from ..fluid_rigorous.model import kv_dispersion, summarize_curve
from ..merged import extras as X
from ..merged.spec import ROOT, build, lambda_ref_of, load_spec
from ..predict import CODE as FROZEN_CODE, clean

FROZEN_TAG = "r13-theory-pred"
FROZEN_COMMIT = "997d2c4d9d25b1d2ef26fdbc8c7b35a9860ceff0"
OUT_DIR = os.path.join(ROOT, "results", "theory", "pred2")
CELLS_DIR = os.path.join(ROOT, "analysis", "theory", "cells")
# lambda_ref of the 300k cell: the spec value the frozen predictions use (theory side), and the registered full-precision
# value the client multiplies by to draw arrivals (prereg/inputs/2026-10-23/calibration.json, lambda_miss_turns_based)
LREF_300K_SPEC = 0.071534
LREF_300K_REG = 0.07153402100919228
E2_CONFIG = "configs/agentload_e2_burst.yaml"
E0_CONFIG = "configs/agentload_e0_cap.yaml"
PRED2_FILES = ["analysis/theory/pred2/__init__.py", "analysis/theory/pred2/common.py", "analysis/theory/pred2/b2.py",
               "analysis/theory/pred2/h200_n2.py", "analysis/theory/pred2/toolslow.py", "analysis/theory/pred2/shed.py",
               "analysis/theory/pred2/e0f.py", "analysis/theory/pred2/prop_e.py", "analysis/theory/pred2/conditional.py",
               "analysis/theory/pred2/run_all.py", "analysis/theory/pred2/freeze_table.py", "analysis/theory/pred2/blind_tables.py"]


# ------------------------------------------------------------------------------------------------ frozen cells


class Cell:
    """A frozen cell exactly as analysis.theory.predict builds it: Model, CurveSummary, lambda_ref, I_D (F2 noise at the peak)."""

    def __init__(self, name: str):
        self.name = name
        self.spec = load_spec(os.path.join(CELLS_DIR, f"{name}.yaml"))
        self.m, self.audit, self.info = build(self.spec)
        self.cs = summarize_curve(self.m)
        self.lam_ref, _ = lambda_ref_of(self.spec, self.m)
        pk = min(self.cs.pts, key=lambda p: abs(p["mu"] - self.cs.mu_max))
        kd = kv_dispersion(self.m.wl, pk["S_bar"])
        self.I_D, self.E_lb, self.S_peak = kd["I_D"], kd["E_lb"], pk["S_bar"]
        self.mu_f = X.curve_fn(self.cs)[0]          # the same mu(n) callable the frozen burst / rescue layers use


@lru_cache(maxsize=None)
def cell(name: str) -> Cell:
    return Cell(name)


def frozen_json(name: str) -> Dict[str, Any]:
    with open(os.path.join(ROOT, "results", "theory", "merged", f"{name}.json")) as f:
        return json.load(f)


def eval_times(hit_good: float, w0: float = 5700.0, w1: float = 8700.0, stuck_below: float = 0.2,
               good_above: float = 0.8) -> Tuple[float, float]:
    """Latest escape time that still makes the window hit fall below `stuck_below` (the frozen B1 stuck-by time, same
    formula as analysis.theory.predict) and earliest escape time that still leaves the window hit above `good_above`
    (new: the GOOD side of the registered endpoints), for an escape that drops the hit from `hit_good` to 0 at once."""
    stuck_by = w0 + min(1.0, stuck_below / hit_good) * (w1 - w0)
    good_from = w0 + min(1.0, good_above / hit_good) * (w1 - w0)
    return float(stuck_by), float(good_from)


# ------------------------------------------------------------------------------------------------ exact client plans


def client_config(cfg_path: str, seed: int, mult: float, duration_s: float, burst_n: int = 0, t_burst: float = 1200.0,
                  width_s: float = 60.0, lambda_ref: float = LREF_300K_REG, ramp: Optional[List[List[float]]] = None):
    """The agentload Config a job builds (run_gen --seed, --set arrivals.rate_mult / lambda_ref / run.duration_s, the burst of
    the cell's E2 config or arrivals.burst = null), as experiments/r11_predict_basin.py built it for the frozen B1/E0F
    simulator predictions.  `ramp` (knots [[t, mult], ...], ramp_is_mult) switches to kind: ramp (the SHED protocol)."""
    from agentload.config import config_from_dict
    with open(os.path.join(ROOT, cfg_path)) as f:
        raw = yaml.safe_load(f)
    raw["arrivals"]["lambda_ref"] = float(lambda_ref)
    if "uncached_tokens_ref" in raw["arrivals"]:
        raw["arrivals"]["uncached_tokens_ref"] = None          # analysis reference only; unused by the generator
    if ramp is not None:
        raw["arrivals"]["kind"] = "ramp"
        raw["arrivals"]["ramp"] = [[float(t), float(r)] for t, r in ramp]
        raw["arrivals"]["ramp_is_mult"] = True
        raw["arrivals"]["rate_mult"] = None
    else:
        raw["arrivals"]["rate_mult"] = float(mult)
    raw["arrivals"]["burst"] = {"n": int(burst_n), "t_s": float(t_burst), "width_s": float(width_s)} if burst_n > 0 else None
    raw["run"]["seed"] = int(seed)
    raw["run"]["duration_s"] = float(duration_s)
    raw.setdefault("meta", {})["engine_label"] = "theory-pred2"
    return config_from_dict(raw)


def client_plan(cfg_path: str, seed: int, mult: float, duration_s: float, burst_n: int = 0, t_burst: float = 1200.0,
                width_s: float = 60.0, lambda_ref: float = LREF_300K_REG, ramp: Optional[List[List[float]]] = None):
    """(plan, rate or ramp knots): the exact sessions (arrival time, turn count, tool times) of one job."""
    from agentload.config import resolve_ramp, resolve_rate
    from agentload.workload import build_open_plan
    cfg = client_config(cfg_path, seed, mult, duration_s, burst_n, t_burst, width_s, lambda_ref, ramp)
    if ramp is not None:
        knots = resolve_ramp(cfg.arrivals)
        return build_open_plan(int(seed), cfg.workload, cfg.arrivals, cfg.run.duration_s, None, knots), knots
    rate = resolve_rate(cfg.arrivals)
    return build_open_plan(int(seed), cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, []), float(rate)


@lru_cache(maxsize=None)
def _workload_cfg(cfg_path: str):
    return client_config(cfg_path, 0, 1.0, 8700.0).workload


def burst_cohort(seed: int, n: int, t_burst: float = 1200.0, width_s: float = 60.0, cfg_path: str = E2_CONFIG):
    """The burst sessions of a plan without building the base sessions (same calls as build_open_plan: burst_times, then
    session_spec(seed, 'burst', rank)): list of (arrival, n_turns, tool_times)."""
    from agentload.workload import burst_times, session_spec
    wl = _workload_cfg(cfg_path)
    bt = burst_times(int(seed), int(n), float(t_burst), float(width_s))
    return [(float(t),) + tuple(session_spec(int(seed), "burst", i, wl)) for i, t in enumerate(bt)]


class PlanRNG:
    """Stands in for the numpy Generator that the frozen extras._live_paths draws from: its two draws (turn counts, then one
    tool time per turn with the last turn's set to 0 by the frozen code) return the plan's values instead."""

    def __init__(self, n_turns: Sequence[int], tools_per_session: Sequence[Sequence[float]]):
        self.T = np.asarray(n_turns, dtype=np.int64)
        self.Z = np.concatenate([np.append(np.asarray(z, float), 0.0) for z in tools_per_session]) if len(self.T) else np.zeros(0)
        assert len(self.Z) == int(self.T.sum())

    def geometric(self, p, size=None):
        assert size == len(self.T), (size, len(self.T))
        return self.T.copy()

    def exponential(self, scale, size=None):
        assert size == len(self.Z), (size, len(self.Z))
        return self.Z.copy()


def live_path(m, arrivals: Sequence[float], n_turns: Sequence[int], tools: Sequence[Sequence[float]], S: float,
              horizon: float, dt: float = 1.0) -> np.ndarray:
    """Live KV volume (tokens) on the grid t = 0, dt, 2dt, ...: the FROZEN extras._live_paths fed with the given sessions."""
    if len(arrivals) == 0:
        return np.zeros(int(math.ceil(horizon / dt)) + 2)
    return X._live_paths(PlanRNG(n_turns, tools), m, np.asarray(arrivals, float), float(S), float(horizon), float(dt))


def plan_arrays(sessions) -> Tuple[np.ndarray, List[int], List[Tuple[float, ...]]]:
    """(arrivals, n_turns, tool_times) of SessionPlan objects or (arrival, n_turns, tools) tuples."""
    if not sessions:
        return np.zeros(0), [], []
    if hasattr(sessions[0], "arrival_s"):
        return (np.array([s.arrival_s for s in sessions], float), [int(s.n_turns) for s in sessions],
                [tuple(s.tool_times_s) for s in sessions])
    return (np.array([s[0] for s in sessions], float), [int(s[1]) for s in sessions], [tuple(s[2]) for s in sessions])


# ------------------------------------------------------------------------------------------------ small probability helpers


def poisson_binomial(ps: Sequence[float]) -> List[float]:
    """pmf of the number of successes of independent Bernoulli(p_i)."""
    pmf = np.array([1.0])
    for p in ps:
        pmf = np.convolve(pmf, [1.0 - float(p), float(p)])
    return [float(x) for x in pmf]


def at_least(ps: Sequence[float], k: int) -> float:
    return float(sum(poisson_binomial(ps)[k:]))


# ------------------------------------------------------------------------------------------------ provenance and output


def sha256(path: str) -> str:
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def frozen_code_unchanged() -> Dict[str, Any]:
    """git diff of analysis/theory against the freeze commit must list only NEW files (status A)."""
    try:
        out = subprocess.run(["git", "diff", "--name-status", FROZEN_COMMIT, "--", "analysis/theory"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split("\n")
        rows = [r.split("\t") for r in out if r.strip()]
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "analysis/theory"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.split()
        changed = [r for r in rows if r[0] != "A"]
        return dict(ok=not changed, modified_tracked=changed, added_committed=[r[1] for r in rows if r[0] == "A"],
                    untracked_new=untracked)
    except Exception as e:  # noqa: BLE001
        return dict(ok=None, error=str(e))


def provenance(extra_inputs: Iterable[str] = ()) -> Dict[str, Any]:
    files = list(FROZEN_CODE) + [p for p in PRED2_FILES if os.path.exists(os.path.join(ROOT, p))] + list(extra_inputs)
    return dict(frozen_tag=FROZEN_TAG, frozen_commit=FROZEN_COMMIT, git_head=git_head(), frozen_code_check=frozen_code_unchanged(),
                sha256={p: sha256(p) for p in dict.fromkeys(files)}, python=sys.version.split()[0], numpy=np.__version__,
                created=time.strftime("%Y-%m-%dT%H:%M:%S%z"))


def write_json(name: str, obj: Dict[str, Any], extra_inputs: Iterable[str] = ()) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    obj = dict(obj)
    obj["provenance"] = provenance(extra_inputs)
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(clean(obj), f, indent=1)
    return path
