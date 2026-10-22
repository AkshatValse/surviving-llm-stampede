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
                                 length_biased_mean_context, length_biased_session_cap, tool_times, triangle_rate,
                                 turn_counts)

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


def test_length_biased_cap_matches_explicit_sum_and_is_28(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    p = 1.0 / wl.mean_turns
    # independent computation: E[sum_{t<=T} E_t] / E[T] from the pmf of the capped geometric
    pmf = {k: p * (1 - p) ** (k - 1) for k in range(1, wl.max_turns)}
    pmf[wl.max_turns] = (1 - p) ** (wl.max_turns - 1)
    assert sum(pmf.values()) == pytest.approx(1.0)
    num = sum(pr * sum(wl.end_len(t) for t in range(1, k + 1)) for k, pr in pmf.items())
    den = sum(pr * k for k, pr in pmf.items())
    assert length_biased_mean_context(wl) == pytest.approx(num / den, rel=1e-12)
    assert length_biased_mean_context(wl) > wl.end_len(8)          # length bias raises the typical context
    assert length_biased_session_cap(300_000, wl) == 28 < default_session_cap(300_000, wl) == 45
    assert length_biased_session_cap(float("inf"), wl) is None


def test_session_cap_auto_lb_resolves_to_28(cfg):
    eng, _, cap = build_engine(cfg, const_spec("fcfs_cap_lb", 0.1, 100.0))
    assert cap == 28 and eng.session_cap == 28
    assert build_engine(cfg, const_spec("fcfs_cap", 0.1, 100.0))[2] == 45
    assert build_engine(cfg, const_spec("fcfs_cap", 0.1, 100.0, session_cap_override=17))[2] == 17


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


@pytest.mark.parametrize("pol", ["aging10", "aging30"])
@pytest.mark.parametrize("lam_mult,cold,M", [(2.0, 75, 300_000), (2.75, 0, 300_000), (2.0, 40, 90_000)])
def test_aging_batched_equals_unbatched(cfg, pol, lam_mult, cold, M):
    """Batched decode runs are cut at aging-threshold crossings, so AGING-LPM is exact too."""
    lam_miss = 0.0474
    plan = ArrivalPlan(kind="constant", horizon_s=5000.0, rate=lam_mult * lam_miss, initial_cold=cold)
    res = []
    for batch in (True, False):
        rs = RunSpec(exp="t", policy=pol, seed=4, horizon_s=5000.0, plan=plan,
                     engine_overrides={"batch_decode_iterations": batch, "kv_memory_tokens": M})
        res.append(simulate(cfg, rs))
    a, b = res
    for k in ["n_arrived", "n_sessions_done", "n_turns_done", "n_admitted", "n_hits", "n_evictions", "n_iterations",
              "final_queue", "max_queue"]:
        assert a["summary"][k] == b["summary"][k], k
    assert a["summary"]["n_steps"] < b["summary"]["n_steps"]
    pd.testing.assert_frame_equal(pd.DataFrame(a["windows"]), pd.DataFrame(b["windows"]), rtol=1e-8, atol=1e-10)


def test_aging_crossing_during_batched_decode_matches_unbatched(cfg):
    """Hand-built state: one turn-60 request decoding (99 iterations left), memory almost full, a resident hit H that
    does not fit blocks the head, and an older small miss S that ages (W_max=4 s) mid-run. Unbatched, S is admitted
    at the first iteration boundary after it ages (and evicts H's KV, so H is later a MISS). The batched engine must
    reproduce that exactly (earlier code only re-checked at the end of the decode run)."""
    import heapq

    def build(batch):
        n = 3
        specs = SessionSpecs(arrival=np.full(n, np.inf), n_turns=np.full(n, 60, dtype=np.int64),
                             tool_off=np.zeros(n, dtype=np.int64), tool_flat=np.full(200, 1e6))
        c2 = deep_update(cfg, {"policies": {"ag4": {"kind": "aging_lpm", "w_max_s": 4.0}}})
        rs = RunSpec(exp="t", policy="ag4", seed=0, horizon_s=20.0, plan=ArrivalPlan(kind="none", horizon_s=20.0),
                     engine_overrides={"kv_memory_tokens": 52_000, "batch_decode_iterations": batch})
        eng, rec, _ = build_engine(c2, rs, specs)
        wl = eng.wl
        eng.now = 3.0
        A = Request(eng._rid, 0, 60, 0.0, 0.0, wl.prompt_len(60), wl.end_len(60))
        eng._rid += 1
        A.pos = A.prompt
        A.offs = (A.pos + 1) - eng.G
        A.done_g = eng.G + 99
        eng.reserved += A.end
        eng.n_D = 1
        eng.sum_off += A.offs
        heapq.heappush(eng._done_heap, (A.done_g, A.rid, A))
        eng._turn[0] = 60
        eng.in_system = 3
        eng._turn[1] = 1
        eng._arrived_t[1] = 0.0
        eng._enqueue_turn(1, 0.0, 0.0)
        eng._turn[2] = 16
        eng._arrived_t[2] = 0.0
        eng._enqueue_turn(2, 2.0, 2.0)
        eng.idle[2] = wl.end_len(15)
        eng.idle_sum = wl.end_len(15)
        eng.trace = []
        eng.run(20.0)
        return [x for x in eng.trace if x[0] == "A"][:2]
    unb, bat = build(False), build(True)
    assert [x[1:4] for x in unb] == [(1, 1, False), (2, 16, False)]        # S first, then H as a miss
    _assert_traces_equal(bat, unb)


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


def test_free_kv_on_session_end_flag(cfg):
    """False keeps the dead session's KV as idle evictable cache (no oracle); True frees it at once."""
    kw = dict(seed=2, arrivals_until=2_000.0)
    done = {}
    for flag in (True, False):
        eo = {"kv_memory_tokens": float("inf"), "free_kv_on_session_end": flag}
        eng, rec, _ = build_engine(cfg, const_spec("fcfs", 0.05, 8_000.0, engine_overrides=eo, debug=True, **kw))
        eng.run(8_000.0)
        assert eng.in_flight() == 0 and eng.n_sessions_done > 20
        done[flag] = (len(eng.idle), eng.idle_sum, eng.n_sessions_done)
    assert done[True][0] == 0 and done[True][1] == 0
    assert done[False][0] == done[False][2]                  # every finished session left its KV behind
    # under memory pressure dead KV is evicted LRU like any other idle KV and memory is still respected
    res = simulate(cfg, const_spec("lpm", 0.3, 1500.0, seed=1, debug=True,
                                   engine_overrides={"kv_memory_tokens": 80_000, "free_kv_on_session_end": False}))
    assert res["summary"]["max_resident_tokens"] <= 80_000 and res["summary"]["n_evictions"] > 0
    # dead KV crowds out live sessions: fewer follow-up hits than with the oracle at the same load/seed
    base = simulate(cfg, const_spec("lpm", 0.3, 1500.0, seed=1, engine_overrides={"kv_memory_tokens": 80_000}))
    assert res["summary"]["n_hits"] <= base["summary"]["n_hits"]


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


def test_infinite_memory_per_window_throughput_identical_across_policies(cfg):
    """During the arrival period (not just after the drain) every policy completes the same turns per window and
    has the same median latency, within a few percent, at a load where the waiting queue is sometimes nonempty."""
    frames = {}
    for pol in ["fcfs", "lpm", "lpm128", "aging10"]:
        res = simulate(cfg, const_spec(pol, 0.4, 8_000.0, seed=2, engine_overrides={"kv_memory_tokens": float("inf")},
                                       debug=False))
        assert res["summary"]["max_queue"] >= 2                      # ordering can matter at this load
        frames[pol] = pd.DataFrame(res["windows"])
    ref = frames["fcfs"]
    for pol, f in frames.items():
        assert np.allclose(f["turns_per_s"], ref["turns_per_s"], rtol=0.06, atol=0.0), pol
        assert np.allclose(f["lat_p50_s"], ref["lat_p50_s"], rtol=0.15, atol=0.05), pol
        assert np.allclose(f["hit_rate_followup"].dropna(), 1.0), pol


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


def _debug_engine_midrun(cfg, t_stop: float = 500.0, **eo):
    """A congested mid-run state with waiting, prefilling/decoding, tool-call and idle sessions all present."""
    plan = ArrivalPlan(kind="constant", horizon_s=t_stop, rate=0.2, initial_cold=30)
    rs = RunSpec(exp="t", policy="lpm", seed=3, horizon_s=t_stop, plan=plan,
                 engine_overrides={"kv_memory_tokens": 150_000, **eo}, debug=True)
    eng, rec, _ = build_engine(cfg, rs)
    eng.run(t_stop)
    eng.check_invariants()
    return eng


def test_invariant_checker_detects_lost_duplicated_and_leaked_state(cfg):
    """The location check must fail on mutants that the counting-only conservation test cannot see."""
    import heapq
    eng = _debug_engine_midrun(cfg)
    assert eng._tool_heap and eng.idle and eng._waiting and eng._done_heap  # the interesting state exists
    # (1) a session silently vanishes from the tool heap (tool-return event lost)
    eng = _debug_engine_midrun(cfg)
    eng._tool_heap.pop()
    heapq.heapify(eng._tool_heap)
    with pytest.raises(AssertionError):
        eng.check_invariants()
    # (2) a session is both waiting and in a tool call
    eng = _debug_engine_midrun(cfg)
    assert eng._waiting
    sid = next(iter(eng._waiting))
    heapq.heappush(eng._tool_heap, (1e9, 10**9, sid))
    with pytest.raises(AssertionError):
        eng.check_invariants()
    # (3) KV leak: idle KV for a session that is decoding
    eng = _debug_engine_midrun(cfg)
    assert eng._done_heap
    r = eng._done_heap[0][2]
    eng.idle[r.sid] = 1000
    eng.idle_sum += 1000
    with pytest.raises(AssertionError):
        eng.check_invariants()
    # (4) idle KV of the wrong length
    eng = _debug_engine_midrun(cfg)
    k = next(iter(eng.idle))
    eng.idle[k] += 1
    eng.idle_sum += 1
    with pytest.raises(AssertionError):
        eng.check_invariants()
    # (5) a gate session also in the system
    eng = _debug_engine_midrun(cfg)
    eng._gate.append(next(iter(eng._waiting)))
    with pytest.raises(AssertionError):
        eng.check_invariants()


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


def _aging_setup(eng):
    _queue(eng, 0, 3, 1.0)     # miss, old
    _queue(eng, 1, 3, 2.0)     # hit, old
    _queue(eng, 2, 4, 20.0)    # miss, new (queued BEFORE the new hit, so FCFS != AGING-LPM)
    _queue(eng, 3, 2, 21.0)    # hit, new
    eng.idle[1] = 3000
    eng.idle[3] = 2650
    eng.idle_sum = 5650


def test_aging_puts_old_requests_first_fcfs_then_lpm(cfg):
    eng = _engine_with_waiting(cfg, "aging10", _aging_setup)
    # now=25: waits are 24, 23, 5, 4 -> first two aged (FCFS: 0 then 1), then LPM among the rest: hit 3 BEFORE miss 2
    assert _order(eng, 25.0) == [0, 1, 3, 2]
    fcfs_order = _order(_engine_with_waiting(cfg, "fcfs", _aging_setup), 25.0)
    lpm_order = _order(_engine_with_waiting(cfg, "lpm", _aging_setup), 25.0)
    assert fcfs_order == [0, 1, 2, 3] and lpm_order == [1, 3, 0, 2]
    assert _order(eng, 25.0) not in (fcfs_order, lpm_order)   # distinguishable from both plain FCFS and plain LPM
    # now=11.5: only sid0 aged (wait 10.5 > 10), then LPM over the rest; sids 2 and 3 are queued after `now`
    eng2 = _engine_with_waiting(cfg, "aging10", _aging_setup)
    assert _order(eng2, 11.5)[0] == 0
    assert len(set(_order(eng2, 25.0))) == 4              # no duplicates


def test_aging_order_is_a_snapshot_taken_before_aged_admissions(cfg):
    """Same semantics as Lpm / the reference simulator: the LPM part of the order is fixed at the start of the pass,
    so an eviction caused by an aged admission does not re-rank the rest."""
    eng = _engine_with_waiting(cfg, "aging10", _aging_setup)
    eng.pass_id += 1
    gen = eng.policy.candidates(eng, 25.0)
    first = next(gen)
    assert first.sid == 0
    eng.idle.pop(3)                                       # sid 3's KV evicted after the first (aged) candidate
    eng.idle_sum -= 2650
    assert [r.sid for r in gen] == [1, 3, 2]              # still ranked as a hit (it is admitted as a miss later)


def test_policy_next_time_event(cfg):
    eng = _engine_with_waiting(cfg, "aging10", _aging_setup)
    assert eng.policy.next_time_event(eng, 11.5) == pytest.approx(12.0)      # sid1 (qtime 2) ages next
    assert eng.policy.next_time_event(eng, 25.0) == pytest.approx(30.0)      # sid2 (qtime 20) ages next
    assert eng.policy.next_time_event(eng, 45.0) == float("inf")             # everything already aged
    for name in ("fcfs", "lpm", "lpm128"):
        e = _engine_with_waiting(cfg, name, _aging_setup)
        assert e.policy.next_time_event(e, 11.5) == float("inf") and not e.policy.time_dependent


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


def _e1_rows(spec):
    """spec: {(policy, mult): n_recovered_of_3}"""
    rows = []
    for (pol, mult), k in spec.items():
        for sd in range(3):
            rec = sd < k
            rows.append({"variant": "base", "policy": pol, "lam_mult": mult, "seed": sd, "recovered": rec,
                         "recovered_incl_gate": rec, "tail_hit_rate": 0.9 if rec else 0.0, "tail_queue_mean": 1.0,
                         "tail_gate_mean": 0.0, "tail_busy_frac": 1.0, "tail_sessions_per_s": 0.1})
    return pd.DataFrame(rows)


def _e2_rows(n_trapped_l128, n_back_lpm):
    return pd.DataFrame([{"variant": "base", "policy": "lpm128", "seed": s, "trapped": s < n_trapped_l128,
                          "hit_returned": False} for s in range(5)] +
                        [{"variant": "base", "policy": "lpm", "seed": s, "trapped": False, "hit_returned": s < n_back_lpm}
                         for s in range(5)])


def test_decision_kill_uses_spec_e2_trap_criterion_not_any_e1_nonrecovery(cfg):
    """Reviewer case: all policies recover at 1.25x, none at 2.0x (LPM fails there too, so the fallback is not the
    cause), LPM-128 never trapped in E2, R=2.44. Old code counted the E1 non-recovery at 2.0x as 'trapped' and returned
    REFRAME; the spec's trap definition (E2: hit<0.2 for >=10 ks) says LPM-128 was never trapped => KILL."""
    spec = {(p, 1.25): 3 for p in ("lpm", "fcfs", "lpm128", "aging30")}
    spec.update({(p, 2.0): 0 for p in ("lpm", "fcfs", "lpm128", "aging30")})
    dec = runner.evaluate_decision(cfg, {"R": 2.44}, _e1_rows(spec), _e2_rows(0, 0))
    assert dec["verdict"] == "KILL", dec
    assert dec["kill_conditions"]["lpm128_never_trapped"] is True
    ev = dec["lpm128_trap_evidence"]
    assert ev["e2_spec_criterion_n_trapped"] == 0 and ev["e1_attributable_lam_mults"] == []
    assert ev["e1_lpm128_any_nonrecovery_not_used"] is True                # reported for transparency only


def test_decision_e1_failure_counts_as_trap_only_where_lpm_recovers(cfg):
    # LPM recovers 3/3 at 1.5x but LPM-128 does not -> attributable E1 trap even though E2 never trapped it
    spec = {("lpm", 1.5): 3, ("fcfs", 1.5): 0, ("lpm128", 1.5): 0, ("aging30", 1.5): 3}
    dec = runner.evaluate_decision(cfg, {"R": 2.44}, _e1_rows(spec), _e2_rows(0, 5))
    assert dec["lpm128_trap_evidence"]["e1_attributable_lam_mults"] == [1.5]
    assert dec["kill_conditions"]["lpm128_never_trapped"] is False
    assert dec["verdict"] != "KILL"
    # E2 trapped in 4/5 and everything else as in the GO case -> GO still reachable
    dec2 = runner.evaluate_decision(cfg, {"R": 2.44}, _e1_rows(spec), _e2_rows(4, 4))
    assert dec2["verdict"] == "GO", dec2


def test_decision_reframe_when_lpm_fails_but_lpm128_trapped_in_e2(cfg):
    spec = {(p, 1.5): 0 for p in ("lpm", "fcfs", "lpm128", "aging30")}
    dec = runner.evaluate_decision(cfg, {"R": 2.44}, _e1_rows(spec), _e2_rows(5, 0))
    assert dec["verdict"] == "REFRAME", dec


def test_ramp_transitions_and_good_state_stats():
    bins = 100.0
    # queue-mean trace: calm (2) for 1000 s, spike up above 128 at bin 12, back below 20 from bin 30 on
    m = [2.0] * 12 + [200.0] * 18 + [3.0] * 20
    tr = [(i * bins, v, v + 1) for i, v in enumerate(m)]
    lam_at = lambda t: t / 1000.0                                                  # noqa: E731
    r = runner.ramp_transitions(tr, lam_at, 128, 20, 5, bins, leg_s=2000.0)
    assert r["escaped"] and r["escape_time_s"] == pytest.approx(1250.0) and r["escape_leg"] == "up"
    assert r["escape_lambda"] == pytest.approx(1.25)
    assert r["reentered"] and r["reentry_time_s"] == pytest.approx(3000.0) and r["reentry_lambda"] == pytest.approx(3.0)
    calm = runner.ramp_transitions([(i * bins, 1.0, 2.0) for i in range(40)], lam_at, 128, 20, 5, bins, 2000.0)
    assert not calm["escaped"] and np.isnan(calm["escape_lambda"]) and not calm["reentered"]
    # a down-leg escape is labelled as such and a never-returning queue has no re-entry
    r2 = runner.ramp_transitions([(i * bins, 500.0 if i > 30 else 1.0, 501.0) for i in range(60)], lam_at, 128, 20, 5, bins, 2000.0)
    assert r2["escape_leg"] == "down" and not r2["reentered"]
    # good-state statistics: onset = end of last calm bin before the escape; the raw max (128) is not reported
    tr2 = [(i * bins, v, v + 5.0) for i, v in enumerate([3.0, 6.0, 10.0, 5.0, 40.0, 90.0, 120.0])]
    g = runner.good_state_stats(tr2, stop_time=700.0, onset_below=20.0, bin_s=bins)
    assert g["good_state_end_s"] == pytest.approx(400.0) and g["runaway_duration_s"] == pytest.approx(300.0)
    assert g["good_state_queue_max"] == pytest.approx(15.0) and g["good_state_queue_mean100_max"] == pytest.approx(10.0)
    g2 = runner.good_state_stats(tr2[:4], stop_time=None, onset_below=20.0, bin_s=bins)
    assert g2["good_state_end_s"] == pytest.approx(400.0) and np.isnan(g2["runaway_duration_s"])


def test_wilson_ci_overrides_and_tables():
    lo, hi = runner.wilson_ci(0, 20)
    assert lo == 0.0 and 0.1 < hi < 0.2
    lo, hi = runner.wilson_ci(10, 20)
    assert lo < 0.5 < hi and lo == pytest.approx(0.299, abs=0.01)
    assert all(np.isnan(x) for x in runner.wilson_ci(0, 0))
    cfg2 = runner.apply_overrides({"engine": {"a": 1, "b": 2}}, ["engine.a=3", "new.x.y=[1, 2]"])
    assert cfg2 == {"engine": {"a": 3, "b": 2}, "new": {"x": {"y": [1, 2]}}}
    with pytest.raises(ValueError):
        runner.apply_overrides({}, ["novalue"])
    # basin table: contiguous from the smallest cold size
    rows = []
    for cold, ok in [(25, True), (50, True), (100, False), (200, True)]:
        for sd in range(2):
            rows.append({"variant": "base" if cold == 200 else f"cold={cold}", "policy": "lpm", "lam_mult": 2.0,
                         "cold_sessions": cold, "recovered": ok, "tail_hit_rate": 0.9, "tail_queue_mean": 1.0})
    bt = runner.basin_table(pd.DataFrame(rows))
    assert bt["basin_size"].unique().tolist() == [50]                           # 200 recovered but 100 did not
    # identity check
    base = {"n_admitted": 10, "n_hits": 3, "n_evictions": 2, "evicted_tokens": 5, "final_queue": 1, "n_turns_done": 4}
    runs = pd.DataFrame([{"policy": "fcfs", "variant": "base", "lam_mult": 2.0, "seed": 0, **base},
                         {"policy": "lpm128", "variant": "base", "lam_mult": 2.0, "seed": 0, **base},
                         {"policy": "fcfs", "variant": "base", "lam_mult": 2.0, "seed": 1, **base},
                         {"policy": "lpm128", "variant": "base", "lam_mult": 2.0, "seed": 1, **{**base, "n_hits": 4}}])
    ident = runner.identity_vs_fcfs(runs)
    assert ident.sort_values("seed")["identical"].tolist() == [True, False]


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
    assert {"e2_spec_criterion_n_trapped", "e1_attributable_lam_mults"} <= set(dec["lpm128_trap_evidence"])
    # supplementary outputs
    assert (outs["e1"] / "e1_basin_table.csv").exists() and (outs["e1"] / "e1_lpm128_vs_fcfs_identity.csv").exists()
    assert {"cold=25", "cap=20", "base"} <= set(pd.read_csv(outs["e1"] / "runs.csv")["variant"])
    assert (outs["e3"] / "e3_transitions.csv").exists()
    assert {"spec", "above_cap"} <= set(pd.read_csv(outs["e3"] / "e3_hysteresis.csv")["variant"])
    assert "good_state_queue_max" in pd.read_csv(outs["e4"] / "runs.csv").columns
    # the consolidated report
    rargs = runner.build_parser().parse_args(["report"] + base + ["--calib", str(calib_path)] +
                                             [x for k, v in outs.items() if k in ("e1", "e2", "e3", "e4")
                                              for x in (f"--{k}-dir", str(v))])
    from prefixmeta.report import cmd_report
    rd = cmd_report(cfg, rargs, repo, calib)
    for f in ["summary.csv", "decision.json", "meta.json", "config.yaml", "fig_e1_e2_hit_queue_vs_time.pdf",
              "fig_e3_throughput_hit_vs_lambda.pdf"]:
        assert (rd / f).exists() and (rd / f).stat().st_size > 0, f
    assert (rd / "fig_e3_throughput_hit_vs_lambda.pdf").read_bytes()[:4] == b"%PDF"
    sm = pd.read_csv(rd / "summary.csv")
    assert list(sm.columns) == ["experiment", "variant", "policy", "lam_mult", "setting", "metric", "value"]
    assert {"e1", "e2", "e3", "e4", "decision"} <= set(sm["experiment"])


# ----------------------------------------------------------------------------- independent reference simulator
def reference_trace(cfg: dict, specs: SessionSpecs, policy: dict, horizon: float, *, M: float, limited: bool = True,
                    skip_ahead: bool = False, cap: int | None = None, cache: bool = True, free_on_end: bool = True,
                    sep: dict | None = None):
    """Deliberately naive iteration-by-iteration re-implementation (plain lists, full re-sorting on every pass,
    pass at EVERY iteration boundary, per-sequence ctx arrays, no global counters / batching / lazy queues).
    Returns the admission/completion trace in the same format as Engine.trace.
    ``sep`` (batching=separate_prefill_priority): dict with pf_fixed, pf_tok, dc_fixed, dc_floor, dc_seq; each iteration is then EITHER a
    prefill iteration (some request has prefill left: chunks only, decode sequences do not advance) OR a decode iteration."""
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
            if cache and not free_on_end:
                idle.append((sid, r["end"]))
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
        k = sep or {}
        if sep is not None and pf:
            tau = k["pf_fixed"] + k["pf_tok"] * ntok + e["prefill_attn_s"] * attn
            adv = []
        else:
            tau = (k.get("dc_fixed", e["iter_fixed_s"]) + max(k.get("dc_floor", e["iter_floor_s"]), k.get("dc_seq", e["per_token_s"]) * (ntok + len(dec)))
                   + e["decode_attn_s"] * sum(x["ctx"] for x in dec) / e["attn_ctx_norm"] + e["prefill_attn_s"] * attn)
            adv = dec
        t += tau
        for x in adv:
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
    ("aging", {"kind": "aging_lpm", "w_max_s": 4.0}, {"batch_decode_iterations": True}, None),
    ("lpm", {"kind": "lpm"}, {"free_kv_on_session_end": False}, None),
    ("fcfs", {"kind": "fcfs"}, {"free_kv_on_session_end": False}, None),
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
                          skip_ahead=eo.get("skip_ahead", False), cap=cap, cache=eo.get("cache_enabled", True),
                          free_on_end=eo.get("free_kv_on_session_end", True))
    assert sum(1 for x in tr_e if x[0] == "D") > 50
    _assert_traces_equal(tr_e, ref)
    if eo.get("cache_enabled", True):
        assert any(x[0] == "A" and x[3] for x in tr_e) and any(x[0] == "A" and not x[3] and x[2] > 1 for x in tr_e)


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("w_max", [1.0, 4.0])
@pytest.mark.parametrize("seed", [21, 22, 23, 24, 25, 26])
def test_aging_matches_reference_over_seeds(cfg, seed, w_max, batch):
    """The review found 3/80 trace mismatches (aged admissions re-ranking the LPM part within a pass) under the old
    lazy AgingLpm; across seeds / thresholds / scenarios the engine now equals the naive reference."""
    pol = {"kind": "aging_lpm", "w_max_s": w_max}
    c2 = deep_update(cfg, {"policies": {"ag": pol}})
    wl = WorkloadParams.from_dict(c2["workload"])
    for (M, rate, cold, burst) in [(70_000, 0.5, 15, 20), (150_000, 0.3, 10, 40)]:
        plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=rate, initial_cold=cold, burst_n=burst, burst_t0=100.0,
                           burst_width_s=10.0)
        specs = build_specs(wl, plan, seed)
        tr_e, _ = _engine_trace(c2, specs, "ag", 900.0,
                                engine_overrides={"kv_memory_tokens": M, "batch_decode_iterations": batch})
        ref = reference_trace(c2, specs, pol, 900.0, M=M)
        _assert_traces_equal(tr_e, ref)


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
