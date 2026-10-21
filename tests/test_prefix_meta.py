"""Tests for the prefix-cache metastability simulator (CPU, small horizons)."""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prefixmeta import runner
from prefixmeta.engine import Engine, EngineParams, Request
from prefixmeta.metrics import AreaTrace, Recorder, longest_run_below, tail_stats
from prefixmeta.policies import AgingLpm, Fcfs, Lpm, LpmFallback, make_policy
from prefixmeta.sim import RunSpec, build_engine, deep_update, load_config, simulate
from prefixmeta.workload import (ArrivalPlan, SessionSpecs, WorkloadParams, build_specs, default_session_cap,
                                 tool_times, triangle_rate, turn_counts)

CFG_PATH = Path(__file__).resolve().parent.parent / "configs" / "prefix_meta.yaml"
ALL_POLICIES = ["fcfs", "lpm", "lpm128", "aging10", "aging30", "fcfs_cap"]


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config(str(CFG_PATH))


def const_spec(policy: str, lam: float, horizon: float, seed: int = 0, arrivals_until: float | None = None,
               **kw) -> RunSpec:
    au = horizon if arrivals_until is None else arrivals_until
    return RunSpec(exp="t", policy=policy, seed=seed, horizon_s=horizon,
                   plan=ArrivalPlan(kind="constant", horizon_s=au, rate=lam), **kw)


def windows_csv(res: dict) -> str:
    return pd.DataFrame(res["windows"]).to_csv(index=False)


def one_session_specs(n_turns: int = 1, tool: float = 5.0, arrival: float = 0.0) -> SessionSpecs:
    return SessionSpecs(arrival=np.array([arrival]), n_turns=np.array([n_turns], dtype=np.int64),
                        tool_off=np.array([0], dtype=np.int64), tool_flat=np.full(max(n_turns - 1, 0), tool))


# ----------------------------------------------------------------------------- workload
def test_turn_counts_mean_and_cap(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    t = turn_counts(np.random.default_rng(1), 200_000, wl.mean_turns, wl.max_turns)
    assert t.min() >= 1 and t.max() <= wl.max_turns
    assert abs(t.mean() - wl.effective_mean_turns()) < 0.1
    assert (t == wl.max_turns).mean() == pytest.approx((1 - 1 / wl.mean_turns) ** (wl.max_turns - 1), abs=0.003)


def test_tool_time_moments():
    rng = np.random.default_rng(2)
    e = tool_times(rng, 300_000, "exp", 5.0, 1.5)
    assert e.mean() == pytest.approx(5.0, rel=0.02)
    ln = tool_times(rng, 1_000_000, "lognormal", 5.0, 1.5)
    assert ln.mean() == pytest.approx(5.0, rel=0.05)
    assert ln.std() / ln.mean() == pytest.approx(1.5, rel=0.15)


def test_context_lengths(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    assert wl.prompt_len(1) == 2000 and wl.end_len(1) == 2100
    assert wl.prompt_len(2) - wl.end_len(1) == 550            # hit prefill = Delta
    assert wl.end_len(2) - wl.end_len(1) == 650               # growth per turn
    assert default_session_cap(300_000, wl) == math.floor(300_000 / wl.end_len(8)) == 45
    assert default_session_cap(float("inf"), wl) is None


def test_specs_deterministic_and_crn(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=2000.0, rate=0.1)
    a, b = build_specs(wl, plan, 5), build_specs(wl, plan, 5)
    assert np.array_equal(a.arrival, b.arrival) and np.array_equal(a.tool_flat, b.tool_flat)
    c = build_specs(wl, plan, 6)
    assert not np.array_equal(a.arrival, c.arrival)
    # extras (cold start + burst) must not change the base Poisson sessions
    plan2 = ArrivalPlan(kind="constant", horizon_s=2000.0, rate=0.1, initial_cold=7, burst_n=11, burst_t0=500.0,
                        burst_width_s=60.0)
    d = build_specs(wl, plan2, 5)
    assert len(d) == len(a) + 18
    base_set = set(np.round(a.arrival, 9))
    assert base_set <= set(np.round(d.arrival, 9))
    assert np.sum(d.arrival == 0.0) >= 7
    assert np.all(np.diff(d.arrival) >= 0)
    burst = d.arrival[(d.arrival >= 500.0) & (d.arrival < 560.0)]
    assert len(burst) >= 11
    assert len(d.tool_flat) == int(np.sum(d.n_turns - 1))


def test_poisson_count_and_triangle_thinning(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    n = [len(build_specs(wl, ArrivalPlan(kind="constant", horizon_s=1000.0, rate=0.5), s)) for s in range(40)]
    assert np.mean(n) == pytest.approx(500, rel=0.05)
    plan = ArrivalPlan(kind="triangle", horizon_s=2000.0, rate_lo=0.1, rate_hi=0.5, ramp_s=1000.0)
    tot = [len(build_specs(wl, plan, s)) for s in range(40)]
    assert np.mean(tot) == pytest.approx(0.3 * 2000, rel=0.06)
    sp = build_specs(wl, plan, 3)
    first_half = np.sum(sp.arrival < 1000.0)
    assert first_half > 0 and abs(first_half - np.sum(sp.arrival >= 1000.0)) < 0.25 * len(sp)
    assert triangle_rate(np.array([0.0, 1000.0, 2000.0]), 0.1, 0.5, 1000.0).tolist() == pytest.approx([0.1, 0.5, 0.1])


# ----------------------------------------------------------------------------- metrics helpers
def test_area_trace_piecewise():
    a = AreaTrace(10.0)
    a.set(2.0, 4.0)        # 0 on [0,2), 4 on [2,7), 1 on [7,25)
    a.set(7.0, 1.0)
    a.advance(25.0)
    assert a.out[0] == pytest.approx((4.0 * 5 / 10 + 1.0 * 3 / 10, 4.0))
    assert a.out[1] == pytest.approx((1.0, 1.0))
    assert len(a.out) == 2          # third bucket still open


def test_recorder_busy_split_and_tail():
    r = Recorder(10.0, 5.0)
    r.add_busy(8.0, 23.0)
    rows = r.finalize(30.0)
    assert [x["busy_frac"] for x in rows] == pytest.approx([0.2, 1.0, 0.3])
    ts = tail_stats(rows, 10.0, 30.0)
    assert ts["n_windows"] == 2
    assert longest_run_below([0.1, 0.1, 0.5, 0.1, float("nan"), 0.1], 0.2) == 2


# ----------------------------------------------------------------------------- engine physics
def hand_latency(cfg, prompt: int, d: int = 100, pos0: int = 0, n_other_dec: int = 0) -> float:
    """Latency of one lone request by explicit iteration-by-iteration arithmetic (independent of engine code)."""
    e = cfg["engine"]
    budget = e["prefill_chunk_budget"]
    t = 0.0
    done = 0
    pos = pos0
    new_total = prompt - pos0
    while done < new_total:
        c = min(budget, new_total - done)
        tok_t = max(e["iter_floor_s"], e["per_token_s"] * c)
        t += e["iter_fixed_s"] + tok_t + e["prefill_attn_s"] * c * (pos + c)
        pos += c
        done += c
    ctx = pos + 1                   # first token emitted by the last prefill iteration
    for _ in range(d - 1):
        t += e["iter_fixed_s"] + max(e["iter_floor_s"], e["per_token_s"] * 1) + e["decode_attn_s"] * ctx / e["attn_ctx_norm"]
        ctx += 1
    return t


@pytest.mark.parametrize("batch", [True, False])
def test_single_request_latency_matches_hand_arithmetic(cfg, batch):
    rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=1000.0,
                 plan=ArrivalPlan(kind="none", horizon_s=1000.0), engine_overrides={"batch_decode_iterations": batch},
                 debug=True)
    res = simulate(cfg, rs, specs=one_session_specs(1))
    w = res["windows"][0]
    assert w["lat_p50_s"] == pytest.approx(hand_latency(cfg, 2000), rel=1e-9)
    assert res["summary"]["n_turns_done"] == 1 and res["summary"]["n_sessions_done"] == 1
    assert res["summary"]["n_iterations"] == 1 + 99


def test_chunked_prefill_spans_iterations(cfg):
    rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=1000.0, plan=ArrivalPlan(kind="none", horizon_s=1000.0),
                 workload_overrides={"initial_context_tokens": 20000}, engine_overrides={"kv_memory_tokens": 1e6},
                 debug=True)
    res = simulate(cfg, rs, specs=one_session_specs(1))
    assert res["summary"]["n_iterations"] == 3 + 99            # 8192 + 8192 + 3616 prefill iterations
    assert res["windows"][0]["lat_p50_s"] == pytest.approx(hand_latency(cfg, 20000), rel=1e-9)
    assert res["windows"][0]["prefill_tok_per_s"] * 1000 == pytest.approx(20000)


def test_hit_second_turn_prefills_only_delta(cfg):
    rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=1000.0, plan=ArrivalPlan(kind="none", horizon_s=1000.0),
                 debug=True)
    res = simulate(cfg, rs, specs=one_session_specs(2, tool=5.0))
    w = res["windows"][0]
    assert res["summary"]["n_hits"] == 1 and res["summary"]["n_admitted"] == 2
    assert w["prefill_tok_per_s"] * 1000 == pytest.approx(2000 + 550)
    assert w["hit_rate_followup"] == 1.0 and w["hit_rate"] == 0.5


@pytest.mark.parametrize("pol,lam,H", [("lpm", 0.08, 4000.0), ("fcfs", 0.2, 3000.0), ("lpm128", 0.3, 3000.0)])
def test_batched_equals_unbatched(cfg, pol, lam, H):
    a = simulate(cfg, const_spec(pol, lam, H, seed=3, engine_overrides={"batch_decode_iterations": True}))
    b = simulate(cfg, const_spec(pol, lam, H, seed=3, engine_overrides={"batch_decode_iterations": False}))
    for k in ["n_arrived", "n_sessions_done", "n_turns_done", "n_admitted", "n_hits", "n_evictions",
              "n_iterations", "final_queue", "max_queue"]:
        assert a["summary"][k] == b["summary"][k], k
    assert a["summary"]["n_steps"] < b["summary"]["n_steps"]
    da, db = pd.DataFrame(a["windows"]), pd.DataFrame(b["windows"])
    pd.testing.assert_frame_equal(da, db, rtol=1e-8, atol=1e-10)


def test_first_pass_admission_respects_prefill_budget(cfg):
    n = 50
    specs = SessionSpecs(arrival=np.zeros(n), n_turns=np.ones(n, dtype=np.int64),
                         tool_off=np.zeros(n, dtype=np.int64), tool_flat=np.zeros(0))
    for limited, expect in [(True, 5), (False, 50)]:
        rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=10.0, plan=ArrivalPlan(kind="none", horizon_s=10.0),
                     engine_overrides={"admission_limited_by_prefill_budget": limited})
        eng, rec, _ = build_engine(cfg, rs, specs)
        eng._process_exogenous(0.0)
        eng._schedule_pass()
        assert len(eng.prefill) == expect, (limited, len(eng.prefill))


# ----------------------------------------------------------------------------- invariants
@pytest.mark.parametrize("pol", ALL_POLICIES)
def test_memory_never_exceeds_M(cfg, pol):
    M = 80_000
    rs = const_spec(pol, 0.3, 1500.0, seed=1, engine_overrides={"kv_memory_tokens": M}, debug=True)
    res = simulate(cfg, rs)              # debug=True asserts reserved+idle<=M and held<=reserved at every step
    s = res["summary"]
    assert s["max_resident_tokens"] <= M
    assert s["max_held_tokens_debug"] <= M
    assert s["n_evictions"] > 0
    assert s["max_running"] <= cfg["engine"]["max_running_seqs"]


def test_running_cap_respected(cfg):
    rs = const_spec("fcfs", 0.3, 800.0, engine_overrides={"max_running_seqs": 4}, debug=True)
    res = simulate(cfg, rs)
    assert res["summary"]["max_running"] <= 4
    assert res["summary"]["n_turns_done"] > 0


def test_infinite_memory_all_followups_hit_and_policies_agree(cfg):
    out = {}
    for pol in ALL_POLICIES:
        rs = const_spec(pol, 0.03, 12_000.0, seed=2, arrivals_until=5_000.0,
                        engine_overrides={"kv_memory_tokens": float("inf")}, debug=True)
        res = simulate(cfg, rs)
        s = res["summary"]
        out[pol] = (s["n_arrived"], s["n_sessions_done"], s["n_turns_done"], s["n_admitted"], s["n_hits"])
        assert s["n_in_flight"] == 0                       # fully drained
        assert s["n_evictions"] == 0
        assert s["n_hits"] == s["n_admitted"] - s["n_arrived"]          # every turn after the first is a hit
        fu = [w["hit_rate_followup"] for w in res["windows"] if w["admitted_turns"] > 0]
        assert all(x == 1.0 for x in fu)
    assert len(set(out.values())) == 1, out


def test_cache_disabled_gives_zero_hits_for_all_policies(cfg):
    for pol in ALL_POLICIES:
        res = simulate(cfg, const_spec(pol, 0.05, 3000.0, seed=4, engine_overrides={"cache_enabled": False}, debug=True))
        s = res["summary"]
        assert s["n_hits"] == 0 and s["n_admitted"] > 100
        assert all(w["hit_rate"] == 0.0 for w in res["windows"] if w["admitted_turns"] > 0)


@pytest.mark.parametrize("pol", ALL_POLICIES)
@pytest.mark.parametrize("lam", [0.08, 0.4])
def test_conservation(cfg, pol, lam):
    res = simulate(cfg, const_spec(pol, lam, 3000.0, seed=7, debug=True))
    s = res["summary"]
    assert s["n_arrived"] == s["n_sessions_done"] + s["n_in_flight"]
    assert s["n_admitted"] >= s["n_turns_done"]
    ws = sum(w["sessions_per_s"] for w in res["windows"]) * cfg["metrics"]["window_s"]
    assert ws <= s["n_sessions_done"] + 1e-6


def test_conservation_closed_and_cap_and_burst(cfg):
    res = simulate(cfg, RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=3000.0,
                                plan=ArrivalPlan(kind="closed", horizon_s=3000.0, closed_n=10, pool=3000),
                                engine_overrides={"cache_enabled": False}, debug=True))
    s = res["summary"]
    assert s["n_in_flight"] == 10 and s["n_arrived"] == s["n_sessions_done"] + 10
    rs = RunSpec(exp="t", policy="fcfs_cap", seed=0, horizon_s=3000.0,
                 plan=ArrivalPlan(kind="constant", horizon_s=3000.0, rate=0.3, initial_cold=100, burst_n=50,
                                  burst_t0=500.0, burst_width_s=60.0), debug=True)
    s = simulate(cfg, rs)["summary"]
    assert s["session_cap"] == 45 and s["n_arrived"] == s["n_sessions_done"] + s["n_in_flight"]
    assert s["max_gate"] > 0                                  # the gate was exercised (and in_system<=cap checked)


def test_determinism_same_seed_identical_csv_different_seed_differs(cfg):
    a = simulate(cfg, const_spec("lpm128", 0.2, 3000.0, seed=11))
    b = simulate(cfg, const_spec("lpm128", 0.2, 3000.0, seed=11))
    c = simulate(cfg, const_spec("lpm128", 0.2, 3000.0, seed=12))
    assert windows_csv(a) == windows_csv(b)
    assert a["qtrace"] == b["qtrace"]
    assert windows_csv(a) != windows_csv(c)
    strip = lambda s: {k: v for k, v in s.items() if not k.startswith("wall")}      # noqa: E731
    sa, sb = strip(a["summary"]), strip(b["summary"])
    assert {k: (v if v == v else None) for k, v in sa.items()} == {k: (v if v == v else None) for k, v in sb.items()}


# ----------------------------------------------------------------------------- policy equivalences
def test_lpm128_equals_lpm_when_queue_never_exceeds_threshold(cfg):
    a = simulate(cfg, const_spec("lpm", 0.15, 4000.0, seed=5))
    b = simulate(cfg, const_spec("lpm128", 0.15, 4000.0, seed=5))
    assert a["summary"]["max_queue"] <= 128
    assert windows_csv(a) == windows_csv(b)


def test_lpm128_equals_lpm_with_huge_threshold_under_congestion(cfg):
    c2 = deep_update(cfg, {"policies": {"lpm_inf": {"kind": "lpm_fallback", "threshold": 10**9},
                                         "lpm128_t0": {"kind": "lpm_fallback", "threshold": 0}}})
    a = simulate(c2, const_spec("lpm", 0.2, 3000.0, seed=6, engine_overrides={"kv_memory_tokens": 60_000}))
    b = simulate(c2, const_spec("lpm_inf", 0.2, 3000.0, seed=6, engine_overrides={"kv_memory_tokens": 60_000}))
    assert a["summary"]["max_queue"] > 128          # the threshold would have bitten under congestion
    assert windows_csv(a) == windows_csv(b)


def test_lpm128_threshold_zero_equals_fcfs(cfg):
    c2 = deep_update(cfg, {"policies": {"lpm128_t0": {"kind": "lpm_fallback", "threshold": 0}}})
    for lam, M in [(0.1, 300_000), (0.3, 120_000)]:
        a = simulate(c2, const_spec("fcfs", lam, 3000.0, seed=8, engine_overrides={"kv_memory_tokens": M}))
        b = simulate(c2, const_spec("lpm128_t0", lam, 3000.0, seed=8, engine_overrides={"kv_memory_tokens": M}))
        assert windows_csv(a) == windows_csv(b)
        assert a["summary"]["n_hits"] == b["summary"]["n_hits"]


def test_lpm_differs_from_fcfs_under_pressure(cfg):
    kw = dict(engine_overrides={"kv_memory_tokens": 80_000})
    a = simulate(cfg, const_spec("fcfs", 0.25, 3000.0, seed=9, **kw))
    b = simulate(cfg, const_spec("lpm", 0.25, 3000.0, seed=9, **kw))
    assert a["summary"]["n_hits"] != b["summary"]["n_hits"]


# ----------------------------------------------------------------------------- policy ordering on the real view
def _engine_with_waiting(cfg, policy_name: str, setup):
    n = 6
    specs = SessionSpecs(arrival=np.full(n, np.inf), n_turns=np.full(n, 10, dtype=np.int64),
                         tool_off=np.zeros(n, dtype=np.int64), tool_flat=np.zeros(0))
    rs = RunSpec(exp="t", policy=policy_name, seed=0, horizon_s=10.0, plan=ArrivalPlan(kind="none", horizon_s=10.0))
    eng, rec, _ = build_engine(cfg, rs, specs)
    eng._tool = [1.0] * 100
    setup(eng)
    return eng


def _queue(eng, sid, turn, t):
    eng._turn[sid] = turn
    eng._arrived_t[sid] = 0.0
    eng._enqueue_turn(sid, t, t)


def _order(eng, now):
    eng.pass_id += 1
    return [r.sid for r in eng.policy.candidates(eng, now)]


def test_lpm_orders_hits_by_matched_length_then_misses_fcfs(cfg):
    def setup(eng):
        _queue(eng, 0, 3, 1.0)     # miss, earliest
        _queue(eng, 1, 3, 2.0)     # hit, short prefix
        _queue(eng, 2, 5, 3.0)     # hit, long prefix
        _queue(eng, 3, 2, 4.0)     # miss
        eng.idle[1] = 3000
        eng.idle[2] = 5000
        eng.idle_sum = 8000
    eng = _engine_with_waiting(cfg, "lpm", setup)
    assert _order(eng, 5.0) == [2, 1, 0, 3]
    eng = _engine_with_waiting(cfg, "fcfs", setup)
    assert _order(eng, 5.0) == [0, 1, 2, 3]


def test_lpm_fallback_switches_on_queue_length(cfg):
    def setup(eng):
        _queue(eng, 0, 3, 1.0)
        _queue(eng, 1, 3, 2.0)
        _queue(eng, 2, 5, 3.0)
        eng.idle[2] = 5000
        eng.idle_sum = 5000
    eng = _engine_with_waiting(cfg, "lpm128", setup)       # 3 waiting <= 128 -> LPM
    assert _order(eng, 4.0) == [2, 0, 1]
    eng.policy = LpmFallback(2)                            # 3 > 2 -> FCFS
    assert _order(eng, 4.0) == [0, 1, 2]
    eng.policy = LpmFallback(3)                            # 3 > 3 false -> LPM
    assert _order(eng, 4.0) == [2, 0, 1]


def test_aging_puts_old_requests_first_fcfs_then_lpm(cfg):
    def setup(eng):
        _queue(eng, 0, 3, 1.0)     # miss, old
        _queue(eng, 1, 3, 2.0)     # hit, old
        _queue(eng, 2, 4, 20.0)    # hit, new
        _queue(eng, 3, 2, 21.0)    # miss, new
        eng.idle[1] = 3000
        eng.idle[2] = 4000
        eng.idle_sum = 7000
    eng = _engine_with_waiting(cfg, "aging10", setup)
    # now=25: waits are 24, 23, 5, 4 -> first two aged (FCFS: 0 then 1), then LPM among the rest (2 hit, 3 miss)
    assert _order(eng, 25.0) == [0, 1, 2, 3]
    # now=11.5: nothing aged except sid0 (wait 10.5 > 10): 0, then LPM: hits 1 (3000)... sid2 queued at 20 > now
    eng2 = _engine_with_waiting(cfg, "aging10", setup)
    assert _order(eng2, 11.5)[0] == 0
    assert len(set(_order(eng2, 25.0))) == 4              # no duplicates


def test_skip_ahead_flag(cfg):
    def mk(skip):
        n = 3
        specs = SessionSpecs(arrival=np.full(n, np.inf), n_turns=np.full(n, 60, dtype=np.int64),
                             tool_off=np.zeros(n, dtype=np.int64), tool_flat=np.zeros(0))
        rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=10.0, plan=ArrivalPlan(kind="none", horizon_s=10.0),
                     engine_overrides={"kv_memory_tokens": 45_000, "skip_ahead": skip})
        eng, rec, _ = build_engine(cfg, rs, specs)
        eng.reserved = 40_000                     # pretend other requests hold most of the memory
        _queue(eng, 0, 60, 1.0)                   # end context 40450 -> does not fit in 5000
        _queue(eng, 1, 1, 2.0)                    # end 2100 fits
        return eng
    e0, e1 = mk(False), mk(True)
    e0._schedule_pass()
    e1._schedule_pass()
    assert e0.n_admitted == 0 and e0.n_wait == 2
    assert e1.n_admitted == 1 and [r.sid for r in e1.prefill] == [1]


# ----------------------------------------------------------------------------- session cap / gate
def test_session_cap_limits_concurrency_and_records_gate(cfg):
    res = simulate(cfg, const_spec("fcfs_cap", 0.5, 3000.0, seed=1, debug=True))     # debug asserts in_system<=cap
    s = res["summary"]
    assert s["session_cap"] == 45                           # floor(300000 / E_8 = 6650)
    assert s["max_gate"] > 0
    assert max(w["gate_max"] for w in res["windows"]) > 0
    # a smaller cap keeps the working set resident, so follow-up turns hit even at 10x the all-miss capacity
    res2 = simulate(cfg, const_spec("fcfs_cap", 0.5, 4000.0, seed=1, debug=True, session_cap_override=15))
    assert res2["summary"]["session_cap"] == 15
    assert res2["summary"]["tail_hit_rate"] > 0.85
    assert res2["summary"]["max_gate"] > 0


# ----------------------------------------------------------------------------- orchestration
def test_hysteresis_area():
    lam = np.linspace(0, 1, 30)
    assert runner.hysteresis_area(np.ones(30), np.ones(30), lam, lam, 0.0, 1.0, 50) == pytest.approx(0.0)
    assert runner.hysteresis_area(np.ones(30), np.full(30, 0.5), lam, lam[::-1], 0.0, 1.0, 50) == pytest.approx(0.5)


def test_decision_rule_logic(cfg):
    def row(variant, pol, mult, seed, rec):
        return {"variant": variant, "policy": pol, "lam_mult": mult, "seed": seed, "recovered": rec,
                "recovered_incl_gate": rec, "tail_hit_rate": 0.9 if rec else 0.0, "tail_queue_mean": 1.0,
                "tail_gate_mean": 0.0, "tail_busy_frac": 1.0, "tail_sessions_per_s": 0.1}
    rows = []
    for mult in (1.5, 2.0):
        for sd in range(3):
            rows += [row("base", "lpm", mult, sd, True), row("base", "fcfs", mult, sd, False),
                     row("base", "lpm128", mult, sd, False), row("base", "aging30", mult, sd, True)]
    e1 = pd.DataFrame(rows)
    e2 = pd.DataFrame([{"policy": "lpm128", "seed": s, "trapped": s < 4, "hit_returned": False} for s in range(5)] +
                      [{"policy": "lpm", "seed": s, "trapped": False, "hit_returned": s < 4} for s in range(5)])
    dec = runner.evaluate_decision(cfg, {"R": 2.5}, e1, e2)
    assert dec["verdict"] == "GO", dec
    dec2 = runner.evaluate_decision(cfg, {"R": 1.2}, e1, e2)
    assert dec2["verdict"] == "KILL"
    e1b = e1.copy()
    e1b["recovered"] = False
    dec3 = runner.evaluate_decision(cfg, {"R": 2.5}, e1b, e2)
    assert dec3["verdict"] == "REFRAME"


def test_pipeline_quick_e0_to_e4_writes_expected_files_and_never_overwrites(cfg, tmp_path):
    repo = CFG_PATH.resolve().parent.parent
    root = str(tmp_path / "res")
    base = ["--config", str(CFG_PATH), "--quick", "--workers", "1", "--out-root", root]
    d0 = runner.cmd_e0(cfg, runner.build_parser().parse_args(["e0"] + base), repo)
    for f in ["meta.json", "config.yaml", "config_effective.yaml", "e0_summary.json", "runs.csv", "windows.csv",
              "qtrace.csv", "cap_search.csv", "miss_runs.csv"]:
        assert (d0 / f).exists(), f
    meta = json.loads((d0 / "meta.json").read_text())
    for k in ["git", "seeds", "versions", "hostname", "hardware", "start_time", "end_time", "argv"]:
        assert k in meta
    assert set(meta["git"]) >= {"commit", "dirty"}
    assert meta["hardware"] == "Apple M3 Money CPU (simulation)".replace("Money", "Max")
    summ = json.loads((d0 / "e0_summary.json").read_text())
    assert summ["lambda_miss"] > 0 and summ["lambda_cap"] > 0 and summ["R"] > 0
    d0b = runner.cmd_e0(cfg, runner.build_parser().parse_args(["e0"] + base), repo)
    assert d0b != d0 and (d0 / "e0_summary.json").exists()       # a fresh dir; the old one untouched
    # E1..E4 + ablation + decision on a fixed synthetic calibration (independent of the quick E0 numbers)
    calib_path = tmp_path / "calib.json"
    calib_path.write_text(json.dumps({"lambda_miss": 0.05, "lambda_cap": 0.16, "R": 3.2, "session_cap_N_star": 45}))
    calib = runner.load_calibration(str(calib_path), root)
    outs = {}
    for cmd in ["e1", "e2", "e3", "e4", "ablation"]:
        args = runner.build_parser().parse_args([cmd] + base + ["--calib", str(calib_path)])
        if cmd == "ablation":
            out = runner.cmd_e1(cfg, args, repo, calib, ablation=True)
        else:
            out = {"e1": runner.cmd_e1, "e2": runner.cmd_e2, "e3": runner.cmd_e3, "e4": runner.cmd_e4}[cmd](
                cfg, args, repo, calib)
        outs[cmd] = out
        for f in ["meta.json", "runs.csv", "windows.csv", "config.yaml", "config_effective.yaml"]:
            assert (out / f).exists(), (cmd, f)
    hyst = pd.read_csv(outs["e3"] / "e3_hysteresis.csv")
    assert {"fcfs", "lpm"} <= set(hyst["policy"])
    e2 = pd.read_csv(outs["e2"] / "runs.csv")
    assert {"trapped", "hit_eval", "hit_returned", "recovered_e2"} <= set(e2.columns)
    e4 = pd.read_csv(outs["e4"] / "e4_summary.csv")
    assert "n_escaped" in e4.columns
    args = runner.build_parser().parse_args(["decision"] + base + ["--calib", str(calib_path),
                                                                    "--e1-dir", str(outs["e1"]),
                                                                    "--e2-dir", str(outs["e2"])])
    dd = runner.cmd_decision(cfg, args, repo, calib)
    dec = json.loads((dd / "decision.json").read_text())
    assert dec["verdict"] in ("GO", "KILL", "REFRAME") or dec["verdict"].startswith("NEITHER")


# ----------------------------------------------------------------------------- independent reference simulator
def reference_trace(cfg: dict, specs: SessionSpecs, policy: dict, horizon: float, *, M: float, limited: bool = True,
                    skip_ahead: bool = False, cap: int | None = None, cache: bool = True):
    """Deliberately naive iteration-by-iteration re-implementation (plain lists, full re-sorting on every pass,
    pass at EVERY iteration boundary, per-sequence ctx arrays, no global counters / batching / lazy queues).
    Returns the admission/completion trace in the same format as Engine.trace."""
    e, w = cfg["engine"], cfg["workload"]
    L0, DELTA, D = w["initial_context_tokens"], w["new_prompt_tokens"], w["decode_tokens"]
    prompt_len = lambda turn: L0 + (turn - 1) * (DELTA + D)          # noqa: E731
    arr = specs.arrival.tolist()
    n = len(arr)
    nt = specs.n_turns.tolist()
    tools = [specs.tools_of(i).tolist() for i in range(n)]
    turn = [1] * n
    arrived_at = [0.0] * n
    nxt = 0
    t = 0.0
    waiting, idle, running, tool_ev, gate = [], [], [], [], []
    reserved, rid_ctr, seq_ctr, in_sys = 0, 0, 0, 0
    pending_done, trace = [], []

    def enqueue(sid, tq, ready):
        nonlocal rid_ctr
        p = prompt_len(turn[sid])
        waiting.append(dict(rid=rid_ctr, sid=sid, turn=turn[sid], q=tq, ready=ready, prompt=p, end=p + D))
        rid_ctr += 1

    def enter(sid, tt):
        nonlocal in_sys
        in_sys += 1
        turn[sid] = 1
        enqueue(sid, tt, arrived_at[sid])

    def order(now):
        fcfs = sorted(waiting, key=lambda r: (r["q"], r["rid"]))
        kv = dict(idle)

        def lpm(pool):
            hits = sorted([r for r in pool if r["sid"] in kv], key=lambda r: (-kv[r["sid"]], r["q"], r["rid"]))
            hs = {r["rid"] for r in hits}
            return hits + [r for r in pool if r["rid"] not in hs]
        kind = policy["kind"]
        if kind == "fcfs":
            return fcfs
        if kind == "lpm":
            return lpm(fcfs)
        if kind == "lpm_fallback":
            return fcfs if len(waiting) > policy["threshold"] else lpm(fcfs)
        if kind == "aging_lpm":
            aged = [r for r in fcfs if r["q"] < now - policy["w_max_s"]]
            ids = {r["rid"] for r in aged}
            return aged + lpm([r for r in fcfs if r["rid"] not in ids])
        raise ValueError(kind)

    def schedule(now):
        nonlocal reserved
        if not waiting:
            return
        n_run = len(running)
        pending = sum(x["rem"] for x in running if x["kind"] == "pf")
        budget_left = e["prefill_chunk_budget"] - pending if limited else float("inf")
        for r in order(now):
            if n_run >= e["max_running_seqs"] or (limited and budget_left <= 0):
                break
            if reserved + r["end"] > M:
                if skip_ahead:
                    continue
                break
            hit = any(s == r["sid"] for s, _ in idle)
            if hit:
                kv = [k for s, k in idle if s == r["sid"]][0]
                idle[:] = [(s, k) for s, k in idle if s != r["sid"]]
                pos, new = kv, r["prompt"] - kv
            else:
                pos, new = 0, r["prompt"]
            while reserved + r["end"] + sum(k for _, k in idle) > M:
                idle.pop(0)
            reserved += r["end"]
            waiting[:] = [x for x in waiting if x["rid"] != r["rid"]]
            running.append(dict(r=r, kind="pf", pos=pos, rem=new, ctx=0, left=0))
            trace.append(("A", r["sid"], r["turn"], hit, now))
            n_run += 1
            if limited:
                budget_left -= new

    def finish(x, now):
        nonlocal reserved, seq_ctr, in_sys, nxt
        r = x["r"]
        sid = r["sid"]
        reserved -= r["end"]
        running.remove(x)
        trace.append(("D", sid, r["turn"], now))
        if r["turn"] < nt[sid]:
            if cache:
                idle.append((sid, r["end"]))
            z = tools[sid][r["turn"] - 1]
            turn[sid] = r["turn"] + 1
            seq_ctr += 1
            tool_ev.append((now + z, seq_ctr, sid))
        else:
            in_sys -= 1
            if gate:
                j = gate.pop(0)
                enter(j, now)

    while t < horizon:
        while True:
            ta = arr[nxt] if nxt < n else float("inf")
            te = min(tool_ev) if tool_ev else (float("inf"),)
            if ta <= te[0] and ta <= t:
                arrived_at[nxt] = ta
                if cap is not None and in_sys >= cap:
                    gate.append(nxt)
                else:
                    enter(nxt, ta)
                nxt += 1
            elif te[0] <= t:
                tool_ev.remove(te)
                enqueue(te[2], te[0], te[0])
            else:
                break
        for x in sorted(pending_done, key=lambda z: z["r"]["rid"]):
            finish(x, t)
        pending_done = []
        schedule(t)
        if not running:
            ta = arr[nxt] if nxt < n else float("inf")
            te = min(tool_ev)[0] if tool_ev else float("inf")
            nx = min(ta, te)
            assert not waiting
            if nx >= horizon:
                break
            t = nx
            continue
        pf = [x for x in running if x["kind"] == "pf"]
        dec = [x for x in running if x["kind"] == "dec"]
        budget, chunks, ntok, attn = e["prefill_chunk_budget"], [], 0, 0.0
        for x in pf:
            if budget <= 0:
                break
            c = min(budget, x["rem"])
            chunks.append((x, c))
            budget -= c
            ntok += c
            attn += c * (x["pos"] + c)
        tau = (e["iter_fixed_s"] + max(e["iter_floor_s"], e["per_token_s"] * (ntok + len(dec)))
               + e["decode_attn_s"] * sum(x["ctx"] for x in dec) / e["attn_ctx_norm"] + e["prefill_attn_s"] * attn)
        t += tau
        for x in dec:
            x["ctx"] += 1
            x["left"] -= 1
            if x["left"] == 0:
                pending_done.append(x)
        for x, c in chunks:
            x["pos"] += c
            x["rem"] -= c
            if x["rem"] == 0:
                if D <= 1:
                    pending_done.append(x)
                else:
                    x["kind"], x["ctx"], x["left"] = "dec", x["pos"] + 1, D - 1
    return trace


def _engine_trace(cfg, specs, pol_name, horizon, **ov):
    eo = ov.pop("engine_overrides", {})
    rs = RunSpec(exp="t", policy=pol_name, seed=0, horizon_s=horizon, plan=ArrivalPlan(kind="none", horizon_s=horizon),
                 engine_overrides=eo, debug=True, **ov)
    eng, rec, cap = build_engine(cfg, rs, specs)
    eng.trace = []
    eng.run(horizon)
    return eng.trace, cap


def _assert_traces_equal(a, b):
    assert len(a) == len(b), (len(a), len(b))
    for x, y in zip(a, b):
        assert x[:-1] == y[:-1], (x, y)
        assert x[-1] == pytest.approx(y[-1], rel=1e-9, abs=1e-9), (x, y)


@pytest.mark.parametrize("pol,polspec,eo,cap", [
    ("fcfs", {"kind": "fcfs"}, {}, None),
    ("lpm", {"kind": "lpm"}, {}, None),
    ("lpm_t6", {"kind": "lpm_fallback", "threshold": 6}, {}, None),
    ("fcfs", {"kind": "fcfs"}, {"skip_ahead": True}, None),
    ("lpm", {"kind": "lpm"}, {"skip_ahead": True}, None),
    ("fcfs", {"kind": "fcfs"}, {"admission_limited_by_prefill_budget": False}, None),
    ("lpm", {"kind": "lpm"}, {"admission_limited_by_prefill_budget": False}, None),
    ("fcfs", {"kind": "fcfs"}, {}, 12),
    ("aging", {"kind": "aging_lpm", "w_max_s": 4.0}, {"batch_decode_iterations": False}, None),
    ("fcfs", {"kind": "fcfs"}, {"cache_enabled": False}, None),
])
@pytest.mark.parametrize("scenario", [(70_000, 0.5, 15, 20), (150_000, 0.3, 10, 40)])
def test_engine_matches_naive_reference_simulator(cfg, pol, polspec, eo, cap, scenario):
    c2 = deep_update(cfg, {"policies": {pol: {**polspec, **({"session_cap": cap} if cap else {})}}})
    M, rate, cold, burst = scenario
    wl = WorkloadParams.from_dict(c2["workload"])
    # congested, with a cold-start queue and a burst: many evictions, queue builds up, hits and misses interleave
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=rate, initial_cold=cold, burst_n=burst, burst_t0=100.0,
                       burst_width_s=10.0)
    specs = build_specs(wl, plan, 21)
    H = 900.0
    tr_e, _ = _engine_trace(c2, specs, pol, H, engine_overrides={**eo, "kv_memory_tokens": M})
    ref = reference_trace(c2, specs, c2["policies"][pol], H, M=M,
                          limited=eo.get("admission_limited_by_prefill_budget", True),
                          skip_ahead=eo.get("skip_ahead", False), cap=cap, cache=eo.get("cache_enabled", True))
    assert sum(1 for x in tr_e if x[0] == "D") > 50
    _assert_traces_equal(tr_e, ref)
    if eo.get("cache_enabled", True):
        assert any(x[0] == "A" and x[3] for x in tr_e) and any(x[0] == "A" and not x[3] and x[2] > 1 for x in tr_e)


def test_process_pool_results_identical_to_serial(cfg):
    specs = [const_spec("lpm", 0.15, 2000.0, seed=s, engine_overrides={"kv_memory_tokens": 90_000}) for s in (1, 2)]
    with runner.Runner(cfg, 1) as R1:
        a = R1.run(specs)
    with runner.Runner(cfg, 2) as R2:
        b = R2.run(specs)
    for x, y in zip(a, b):
        assert windows_csv(x) == windows_csv(y)
        assert x["qtrace"] == y["qtrace"]


def test_worker_cap_enforced(cfg):
    assert runner.Runner(cfg, 64).workers == cfg["parallel"]["max_workers"] <= 3
