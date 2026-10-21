"""Glue: one (lam, mix, policy, eta, seed) run -> metrics row; sweep -> raw DataFrame."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .metrics import run_metrics
from .policies import ETA_FREE, Costs, make_policy
from .sim import SimParams, SimResult, simulate
from .workload import generate_workload, tool_names


def run_one(cfg: dict, lam: float, mix: str, policy: str, eta: float | None, seed: int,
            progs=None) -> tuple[SimResult, dict[str, Any]]:
    prm = SimParams.from_cfg(cfg)
    if progs is None:
        progs = generate_workload(cfg, lam, mix, seed)
    costs = Costs(prm.p, prm.s, prm.M)
    rng = np.random.default_rng([seed, 1])   # policy randomness (SKI_RAND)
    pol = make_policy(policy, costs, eta if eta is not None else math.nan,
                      len(tool_names(cfg)), rng, cfg["policy"])
    res = simulate(progs, pol, prm)
    row = dict(mix=mix, lam=lam, policy=policy,
               eta=(math.nan if policy in ETA_FREE else eta), seed=seed)
    row.update(run_metrics(res, prm))
    return res, row


def sweep(cfg: dict, lams: list[float], mixes: list[str], policies: list[str],
          etas: list[float], seeds: list[int]) -> pd.DataFrame:
    rows = []
    for mix in mixes:
        for lam in lams:
            for seed in seeds:
                progs = generate_workload(cfg, lam, mix, seed)
                for pol in policies:
                    for eta in ([None] if pol in ETA_FREE else etas):
                        rows.append(run_one(cfg, lam, mix, pol, eta, seed, progs)[1])
    return pd.DataFrame(rows)
