"""Synthetic E2 runs for the throughput-based trap criterion: a single FIFO server whose service rate depends on the
time a session STARTS service (a stand-in for the good / thrashing states), driven by deterministic arrivals plus an
optional burst. It is a test fixture for the verdict LOGIC, not a model of any engine. CAUTION (review of 2026-10-21): its trapped service rate is
exactly lambda_miss by construction, so tests built on it check the logic, not that a real trap looks like this; the
discrepancy between session and token units on realistic traps is tested separately (young_session_trap in
test_analysis_trap_v2.py; the simulator's traces in test_trap_sim_traces.py)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import yaml

from analysis.load import Run
from conftest import make_raw

LAM_MISS = 0.04          # sessions/s, "all-miss capacity"
MULT = 1.5               # lambda = 0.06
T_B, T_END, K = 1200.0, 8700.0, 15
PROMPT = 1000.0          # tokens per turn in the fixture (constant, so one session = K * PROMPT prompt tokens)
FIXTURE_START = time.time() + 86400.0          # wall-clock start of every synthetic run: a day from now, i.e. after any commit made in a test


def synth_run(*, arm: str, seed: int = 0, mu_fn: Callable[[float], float], hit_fn: Callable[[float], float],
              burst_n: int = 200, lam_miss: float = LAM_MISS, mult: float = MULT, t_b: float = T_B, t_end: float = T_END,
              label: str = "sglang-fcfs-r1", n_cap: int = 22, tag: str = "", cfg_edit: Optional[Callable[[dict], None]] = None,
              explicit_arm: Optional[str] = None, lam_override: Optional[float] = None) -> Run:
    """One run. ``mu_fn(t)`` = service rate (sessions/s) for a session whose service starts at t; ``hit_fn(t)`` = P(turn hit)."""
    lam = lam_override if lam_override is not None else lam_miss * mult
    rng = np.random.default_rng(1000 + seed)
    arr = np.arange(rng.uniform(0, 1.0 / lam), t_end, 1.0 / lam)
    if arm != "noburst":
        arr = np.sort(np.concatenate([arr, np.sort(rng.uniform(t_b, t_b + 60.0, size=burst_n))]))
    start = np.zeros(len(arr))
    end = np.zeros(len(arr))
    free = 0.0
    for i, a in enumerate(arr):
        start[i] = max(a, free)
        end[i] = start[i] + 1.0 / mu_fn(start[i])
        free = end[i]
    ended = end <= t_end
    # requests: K turns per session, completing evenly between service start and end
    sid = np.repeat(np.arange(len(arr)), K)
    turn = np.tile(np.arange(1, K + 1), len(arr))
    t_c = start[sid] + (end[sid] - start[sid]) * turn / K
    # CAPPED arm: the FIFO queue in front of the single server plays the gate (admitted = starts service, at most 1 active)
    t_admit = start if arm == "capped" else arr
    # a turn's request is outstanding from the previous turn's completion; the first one from the session's arrival (queued in
    # the engine) or, behind the gate, from its admission -- as in the real client
    t_prev = np.where(turn == 1, t_admit[sid], start[sid] + (end[sid] - start[sid]) * (turn - 1) / K)
    keep = t_c < t_end
    sid, turn, t_c, t_prev = sid[keep], turn[keep], t_c[keep], t_prev[keep]
    hit = (rng.random(len(t_c)) < np.array([hit_fn(t) for t in t_c])) & (turn >= 2)
    req = pd.DataFrame({"req_id": np.arange(len(t_c)), "sid": sid, "turn": turn, "n_turns": K, "t_send": t_prev,
                        "t_complete": t_c, "latency_s": t_c - t_prev, "status": "ok", "prompt_tokens": PROMPT,
                        "prompt_tokens_client": PROMPT, "cached_tokens": np.where(hit, 0.9 * PROMPT, 0.0)})
    # requests still outstanding when the run ends (queued or in service) are cancelled at t_end, as the real client logs them
    n_done = np.bincount(sid, minlength=len(arr))
    pend = np.nonzero((n_done < K) & (t_admit < t_end))[0]
    t_send_pend = np.where(n_done[pend] == 0, t_admit[pend],
                           start[pend] + (end[pend] - start[pend]) * n_done[pend] / K)
    pend_df = pd.DataFrame({"req_id": len(req) + np.arange(len(pend)), "sid": pend, "turn": n_done[pend] + 1, "n_turns": K,
                            "t_send": t_send_pend, "t_complete": t_end, "latency_s": t_end - t_send_pend, "status": "cancelled",
                            "prompt_tokens": np.nan, "prompt_tokens_client": PROMPT, "cached_tokens": np.nan})
    req = pd.concat([req, pend_df], ignore_index=True)
    ses = pd.DataFrame({"sid": np.arange(len(arr)), "arrival_s": arr, "n_turns": K,
                        "t_end": np.where(ended, end, t_end), "status": np.where(ended, "completed", "cancelled"),
                        "t_admit": t_admit, "gate_wait_s": t_admit - arr, "gate_censored": 0})
    tok_ref = lam_miss * K * PROMPT            # all-miss uncached prefill tokens/s of the fixture: lambda_miss sessions/s x K turns x PROMPT
    raw = make_raw(arrivals={"rate": None, "rate_mult": mult, "lambda_ref": "/x/calibration.json:lambda_miss",
                             "uncached_tokens_ref": "/x/calibration.json:all_miss_uncached_tokens_per_s",
                             "burst": None if arm == "noburst" else {"n": burst_n, "t_s": t_b, "width_s": 60.0},
                             "analysis_t_burst_s": t_b},
                   workload={"mean_turns": 15, "max_turns": 60}, run={"duration_s": t_end, "seed": seed},
                   gate={"n_cap": n_cap if arm == "capped" else None}, meta={"arm": arm if explicit_arm is None else explicit_arm,
                                                                           "engine_label": label})
    if cfg_edit:
        cfg_edit(raw)
    meta = {"engine_label": label, "seeds": [seed], "resolved_rate_sessions_per_s": lam, "lambda_ref_resolved": lam_miss,
            "uncached_tokens_ref_resolved": tok_ref, "t0_unix": FIXTURE_START, "prereg_sha256": None,
            "arm": arm if explicit_arm is None else explicit_arm, "analysis_t_burst_s": t_b,
            "gate_n_cap_resolved": n_cap if arm == "capped" else None, "hardware": "synthetic",
            "outcome": {"t_end_s": t_end, "abort_reason": None}}
    return Run(dir=Path(f"/nonexistent/{label}-{mult}-{seed}-{arm}{tag}"), meta=meta, cfg=raw, requests=req, sessions=ses,
               metrics=pd.DataFrame(columns=["t_s", "name", "labels", "value"]), t_end_s=t_end)


def write_run_dir(run: Run, root: Path) -> Path:
    """Write a synthetic run to disk in the layout analysis.load.load_run reads."""
    d = root / run.dir.name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({**run.meta, "start_state_verified": True, "status": "finished"}))
    (d / "config_effective.yaml").write_text(yaml.safe_dump(run.cfg, sort_keys=False))
    run.requests.to_csv(d / "requests.csv", index=False)
    run.sessions.to_csv(d / "sessions.csv", index=False)
    return d


# --- scenarios -----------------------------------------------------------------------------------------------------
GOOD_MU = 0.12
HIT_GOOD = lambda t: 0.97
HIT_BAD = lambda t: 0.05


def scenario_trapped(burst_n: int = 200):
    """Good service until just after the burst, then the all-miss capacity (= lambda_miss): the backlog grows at ~ lambda-lambda_miss."""
    return dict(mu_fn=lambda t: GOOD_MU if t < T_B + 100 else LAM_MISS,
                hit_fn=lambda t: HIT_GOOD(t) if t < T_B + 100 else HIT_BAD(t), burst_n=burst_n)


def scenario_draining():
    """Slow drain: service only slightly above lambda (0.07 > 0.06), so a 200-session burst is still draining at the end
    (hit rate depressed meanwhile, completion rate well above lambda_miss)."""
    return dict(mu_fn=lambda t: 0.07, hit_fn=lambda t: 0.5)


def scenario_recovered():
    """Fast service: a burst of 50 drains in ~15 min and the system is back to the good state long before the window."""
    return dict(mu_fn=lambda t: GOOD_MU, hit_fn=HIT_GOOD, burst_n=50)


def scenario_collapse():
    """No good state at all: service at the all-miss capacity from the start (the NOBURST arm of a dead framing)."""
    return dict(mu_fn=lambda t: LAM_MISS, hit_fn=HIT_BAD)
