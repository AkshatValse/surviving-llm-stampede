"""Workload generation: Poisson agent programs with tool-call pauses.

Workload is generated up front from (config, lam, mix, seed) so all policies
see identical programs (common random numbers).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


@dataclass
class Program:
    pid: int
    arrival: float
    new: list[int]          # new input tokens per step (step 0: the initial prompt L0)
    dec: list[int]          # decode tokens per step
    tool: list[int]         # tool type index after step k (len K-1)
    dur: list[float]        # tool duration (s) after step k (len K-1)

    @property
    def K(self) -> int:
        return len(self.new)


def _lognorm_int(rng: np.random.Generator, spec: dict, size: int) -> np.ndarray:
    x = spec["median"] * np.exp(spec["sigma"] * rng.standard_normal(size))
    return np.clip(np.rint(x), spec["min"], spec["max"]).astype(np.int64)


def _tool_durations(rng: np.random.Generator, tools: dict, names: list[str],
                    idx: np.ndarray, cap: float) -> np.ndarray:
    n = len(idx)
    z = rng.standard_normal(n)
    u = 1.0 - rng.random(n)  # uniform in (0, 1]
    out = np.zeros(n)
    for j, nm in enumerate(names):
        m = idx == j
        if not m.any():
            continue
        sp = tools[nm]
        if sp["kind"] == "lognormal":
            out[m] = sp["median"] * np.exp(sp["sigma"] * z[m])
        elif sp["kind"] == "pareto":  # classical Pareto(xm, alpha)
            out[m] = sp["xm"] * u[m] ** (-1.0 / sp["alpha"])
        else:
            raise ValueError(sp["kind"])
    return np.minimum(out, cap)


def tool_names(cfg: dict) -> list[str]:
    return list(cfg["workload"]["tools"].keys())


def generate_workload(cfg: dict, lam: float, mix: str, seed: int) -> list[Program]:
    """Generate programs arriving over [0, horizon). `mix` in cfg mixes or 'shift'."""
    wl, sim, srv = cfg["workload"], cfg["sim"], cfg["server"]
    rng = np.random.default_rng([seed, 0])
    H = sim["horizon_s"]
    n = int(rng.poisson(lam * H))
    arr = np.sort(rng.uniform(0.0, H, n))
    names = tool_names(cfg)
    probs = {}
    for m, d in wl["mixes"].items():
        pr = np.array([d[t] for t in names], dtype=float)
        probs[m] = pr / pr.sum()
    scale = sim.get("tool_time_scale", 1.0)
    maxctx = srv["max_context"]
    progs: list[Program] = []
    Ks = np.minimum(rng.geometric(1.0 / wl["mean_steps"], n), wl["max_steps"])
    for pid in range(n):
        K = int(Ks[pid])
        new = _lognorm_int(rng, wl["new"], K)
        new[0] = _lognorm_int(rng, wl["L0"], 1)[0]
        dec = _lognorm_int(rng, wl["dec"], K)
        cum = np.cumsum(new + dec)  # truncate so context never exceeds max_context
        K = int(max(1, np.searchsorted(cum, maxctx, side="right")))
        new, dec = new[:K], dec[:K]
        if mix == "shift":
            use = "default" if arr[pid] < wl["shift_frac"] * H else "heavy"
        else:
            use = mix
        idx = (rng.choice(len(names), size=K - 1, p=probs[use])
               if K > 1 else np.zeros(0, dtype=int))
        dur = _tool_durations(rng, wl["tools"], names, idx, wl["tool_cap_s"]) * scale
        progs.append(Program(pid, float(arr[pid]), new.tolist(), dec.tolist(),
                             idx.tolist(), dur.tolist()))
    return progs
