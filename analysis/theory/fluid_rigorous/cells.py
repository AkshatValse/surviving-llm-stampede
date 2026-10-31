"""The three measured validation cells: independent inputs for the model and the measured landmarks (read-only).

Inputs the model is allowed to use (task brief): the pool M, the workload (configs/agentload_e2_burst.yaml), the
tool-time law, and service costs from the calibrated cost model (calibration/round6_server_log_fit/calibration.yaml,
fitted to SGLang server-log timing only) and/or E0a all-miss throughput (for vLLM: its own E0a).  Measured Stage C
curves, E0b brackets and E2 runs are VALIDATION TARGETS only; nothing in this module feeds them into the model.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .model import Costs, Model, Workload

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RN = os.path.join(ROOT, "results", "nova")

PATHS = {
    "a100_300k": dict(
        mu_curve="stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv",
        label="sglang-fcfs-r1",
        e0a="e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json",
        e0a64="e0a_1707263x_pulled_20261023-142037/agentload_analysis_miss/20261022-163440/calibration.json",
        bracket="e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/lambda_cap_bracket.json",
        e0b_mults=(1.25, 1.5, 1.75, 2.0, 2.5, 3.0),
        trap="e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/trap_v2_runs.csv",
        trap_root="e2_170933xx_pulled_20261025-144558",
    ),
    "a100_native": dict(
        mu_curve="r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv",
        label="sglang-fcfs-r1-native",
        e0a="r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json",
        e0a64="r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss_popcheck/20261025-054654/calibration.json",
        bracket="e0b_native_1710093x_pulled_20261025-173038/results/agentload_analysis_stable/20261025-172934/lambda_cap_bracket.json",
        e0b_mults=(1.5, 2.5, 3.5, 4.5, 5.5, 6.5),
        trap="e2_native_vllm_burst_pulled_20261026-101256/results/agentload_analysis_burst2/20261026-100653/trap_v2_runs.csv",
        trap_root="e2_native_vllm_burst_pulled_20261026-101256",
    ),
    "vllm_300k": dict(
        mu_curve="stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv",
        label="vllm-fcfs",
        e0a="e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json",
        e0a64="e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss_popcheck/20261025-175648/calibration.json",
        bracket="e0b_vllm_1716296x_pulled_20261030-172810/results/agentload_analysis_stable/20261030-172042/lambda_cap_bracket.json",
        e0b_mults=(1.25, 1.5, 1.75, 2.0, 2.5, 3.0),
        trap="e2_native_vllm_burst_pulled_20261026-101256/results/agentload_analysis_burst2/20261026-100701/trap_v2_runs.csv",
        trap_root="e2_native_vllm_burst_pulled_20261026-101256",
    ),
}

POOLS = {"a100_300k": 300000.0, "a100_native": 955757.0, "vllm_300k": 18750.0 * 16.0}


def _p(rel: str) -> str:
    return os.path.join(RN, rel)


def e0a(cell: str) -> Dict[str, float]:
    c = json.load(open(_p(PATHS[cell]["e0a"])))
    return dict(lambda_miss_turns=float(c["lambda_miss_turns_based"]), tokens=float(c["all_miss_uncached_tokens_per_s"]),
                lambda_miss_sessions=float(c.get("lambda_miss", c.get("lambda_miss_sessions", math.nan))))


def e0a64(cell: str) -> Dict[str, float]:
    p = _p(PATHS[cell]["e0a64"])
    if not os.path.exists(p):
        return {}
    c = json.load(open(p))
    return dict(lambda_miss_turns=float(c["lambda_miss_turns_based"]), tokens=float(c["all_miss_uncached_tokens_per_s"]))


def model_for(cell: str, wl: Optional[Workload] = None) -> Model:
    """The model of a cell, built from independent inputs only.
    a100_300k, a100_native: SGLang separate-iteration mode, calibrated costs unchanged (zero fitted parameters).
    vllm_300k: vLLM-like mixed iterations; ONE factor s_v fitted to vLLM's own E0a all-miss token rate (allowed
    input), hit prefill = 559 tokens (551 + the mean unfilled 16-token block)."""
    wl = wl or Workload()
    if cell in ("a100_300k", "a100_native"):
        return Model(wl, Costs(), POOLS[cell])
    if cell == "vllm_300k":
        wlv = Workload(**{**wl.__dict__, "x_hit": 559})
        s = vllm_speed_factor(wlv)
        return Model(wlv, Costs(mode="mixed").scaled(s), POOLS[cell])
    raise KeyError(cell)


def vllm_speed_factor(wl: Workload) -> float:
    """s such that the mixed-mode model's E0a (closed POP 32, cache off) token rate equals vLLM's measured 10,349 tok/s.
    The model's all-miss rate scales exactly linearly with s (time rescaling), so s = target / rate(s=1)."""
    target = e0a("vllm_300k")["tokens"]
    m1 = Model(wl, Costs(mode="mixed"), POOLS["vllm_300k"])
    r1 = m1.all_miss_closed(32)["tok"]
    # one fixed-point refinement: the POP-32 point depends weakly on s through the tool-time / service ratio
    s = target / r1
    for _ in range(3):
        r = Model(wl, Costs(mode="mixed").scaled(s), POOLS["vllm_300k"]).all_miss_closed(32)["tok"]
        s *= target / r
    return float(s)


@dataclass
class Measured:
    cell: str
    n: np.ndarray
    mu_sessions: np.ndarray
    mu_turns: np.ndarray
    hit: np.ndarray
    lam_ref: float
    tokens_ref: float
    bracket: Dict[str, float]
    peak_n_sessions: float
    peak_n_turns: float
    mu_max_sessions: float
    mu_max_turns: float
    flat_top: List[float]
    n_half: float
    mu_large_turns: float
    n_large: float
    window_sessions: float
    window_turns: float
    trap: pd.DataFrame = field(default_factory=pd.DataFrame)


def measured(cell: str) -> Measured:
    P = PATHS[cell]
    d = pd.read_csv(_p(P["mu_curve"]))
    d = d[d["label"] == P["label"]].sort_values("n")
    n = d["n"].to_numpy(float)
    ms = d["mu_sessions"].to_numpy(float)
    mt = d["mu_turns_based"].to_numpy(float)
    h = d["hit_frac_turns"].to_numpy(float)
    e = e0a(cell)
    br = json.load(open(_p(P["bracket"])))
    i = int(np.argmax(ms))
    j = int(np.argmax(mt))
    flat = [float(x) for x, v in zip(n, ms) if v >= 0.95 * ms[i]]
    # 0.5 crossing by linear interpolation between grid points (first crossing)
    nh = math.nan
    for k in range(len(n) - 1):
        if h[k] >= 0.5 > h[k + 1]:
            nh = float(n[k] + (h[k] - 0.5) / (h[k] - h[k + 1]) * (n[k + 1] - n[k]))
            break
    # large n: the largest n below 300 (mu(300) is biased upward by the synchronized start, LOG 2026-10-22)
    big = [k for k in range(len(n)) if n[k] < 300]
    kl = big[-1]
    tr = pd.read_csv(_p(P["trap"]))
    return Measured(cell, n, ms, mt, h, e["lambda_miss_turns"], e["tokens"],
                    dict(stable=float(br["largest_all_stable_mult"]), unstable=float(br["first_unstable_mult_above"])),
                    float(n[i]), float(n[j]), float(ms[i]), float(mt[j]), flat, nh, float(mt[kl]), float(n[kl]),
                    float(ms[i] / e["lambda_miss_turns"]), float(mt[j] / e["lambda_miss_turns"]), tr)
