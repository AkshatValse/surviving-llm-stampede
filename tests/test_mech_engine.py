"""Tests for the round-2 mechanisms (queued-prefix protection, TTL pins, session caps, AIMD) in the engine.

Layers: (1) pure controller maths, (2) hand-built engine states with a known right answer, (3) full runs with the
debug invariant checker, (4) an independent, deliberately naive reference simulator that re-implements every
mechanism from the prose spec and must reproduce the engine's admission/completion trace exactly.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from prefixmeta.engine import Engine
from prefixmeta.mechanisms import AimdParams, aimd_step, resolve_session_cap
from prefixmeta.sim import RunSpec, build_engine, deep_update, load_config, simulate
from prefixmeta.workload import (ArrivalPlan, SessionSpecs, WorkloadParams, build_specs, length_biased_mean_context,
                                 length_biased_session_cap, turn_counts)

CFG_PATH = Path(__file__).resolve().parent.parent / "configs" / "prefix_meta_mech.yaml"
INF = math.inf


@pytest.fixture(scope="module")
def cfg() -> dict:
    top = load_config(str(CFG_PATH))
    base = load_config(str(CFG_PATH.parent / "prefix_meta.yaml"))
    return deep_update(base, {k: v for k, v in top.items() if k != "base_config"})


# a tight-memory workload: every first-turn context is 18100 tokens, sessions have at most 3 turns
BIG_WL = {"initial_context_tokens": 18000, "max_turns": 3, "mean_turns": 3}
BIG_EO = {"kv_memory_tokens": 45_000}
E1 = 18100            # end-of-turn-1 context under BIG_WL


def specs_of(rows) -> SessionSpecs:
    """rows: (arrival, n_turns, tool_time) per session."""
    n = len(rows)
    nt = np.array([r[1] for r in rows], dtype=np.int64)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    flat = np.concatenate([np.full(int(r[1]) - 1, float(r[2])) for r in rows]) if n else np.zeros(0)
    return SessionSpecs(arrival=np.array([r[0] for r in rows], dtype=float), n_turns=nt, tool_off=off, tool_flat=flat)


def mk(cfg, policy: dict, specs: SessionSpecs, *, wo=None, eo=None, debug=True, horizon=1000.0, cap=None) -> Engine:
    c2 = deep_update(cfg, {"policies": {"p": policy}})
    rs = RunSpec(exp="t", policy="p", seed=0, horizon_s=horizon, plan=ArrivalPlan(kind="none", horizon_s=horizon),
                 workload_overrides=wo or {}, engine_overrides=eo or {}, debug=debug, session_cap_override=cap)
    eng, _, _ = build_engine(c2, rs, specs)
    eng.trace = []
    return eng


def admits(eng):
    return [x for x in eng.trace if x[0] == "A"]


def dones(eng):
    return [x for x in eng.trace if x[0] == "D"]


# ============================================================================ (1) controller maths
def test_aimd_step_hit_rule_decrease_increase_and_floor():
    p = AimdParams()
    assert aimd_step(40, 0.5, 0.9, p) == max(4, math.floor(40 * 0.7)) == 28
    assert aimd_step(10, 0.69999, 0.9, p) == 7
    assert aimd_step(28, 0.7, 0.9, p) == 29           # exactly at the threshold is NOT below it -> increase
    assert aimd_step(28, 0.95, 0.9, p) == 29
    assert aimd_step(5, 0.0, 0.9, p) == 4             # floor(3.5) = 3 -> clipped to min_cap
    assert aimd_step(4, 0.0, 0.9, p) == 4             # never below min_cap
    assert aimd_step(10, float("nan"), 0.9, p) == 11  # no admissions in the window -> no evidence of thrash
    assert aimd_step(10, 0.0, 0.0, AimdParams(max_cap=10, hit_threshold=-1.0)) == 10   # max_cap clips the increase


def test_aimd_step_bounds_and_exact_increments_over_random_sequences():
    rng = np.random.default_rng(0)
    p = AimdParams(min_cap=4, max_cap=60)
    cap = 28
    for _ in range(5000):
        hr = float(rng.random()) if rng.random() > 0.05 else float("nan")
        new = aimd_step(cap, hr, float(rng.random()), p)
        assert p.min_cap <= new <= p.max_cap
        if hr == hr and hr < p.hit_threshold:
            assert new == max(p.min_cap, math.floor(cap * 0.7))
            assert new <= cap
        else:
            assert new == min(cap + 1, p.max_cap)
        cap = new


def test_aimd_step_concur_rule():
    p = AimdParams(rule="concur", increase=2, decrease=0.5)
    assert aimd_step(20, 0.9, 0.1, p) == 22                       # U < 0.2 -> +2
    assert aimd_step(20, 0.1, 0.6, p) == 10                       # U > 0.5 and H < 0.2 -> x0.5
    assert aimd_step(20, 0.9, 0.6, p) == 20                       # high U but healthy hit rate is tolerated
    assert aimd_step(20, 0.1, 0.3, p) == 20                       # mid U -> hold
    assert aimd_step(20, float("nan"), 0.9, p) == 20              # NaN hit rate never cuts
    assert aimd_step(5, 0.0, 0.9, p) == 4                         # min_cap
    with pytest.raises(ValueError):
        AimdParams.from_dict({"rule": "nope"})


def test_resolve_session_cap_forms(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    M = 300_000.0
    n = length_biased_session_cap(M, wl)
    assert n == 28
    assert resolve_session_cap(None, M, wl) == (None, None)
    assert resolve_session_cap(17, M, wl) == (17, None)
    assert resolve_session_cap("lb", M, wl) == (n, None)
    assert resolve_session_cap("auto_lb", M, wl) == (n, None)
    assert resolve_session_cap({"lb_mult": 1.3}, M, wl) == (math.floor(1.3 * n), None) == (36, None)
    cap, ap = resolve_session_cap({"aimd": {"start": "lb"}}, M, wl)
    assert cap == n and ap.rule == "hit" and ap.min_cap == 4
    cap, ap = resolve_session_cap({"aimd": {"start": 2, "min_cap": 4}}, M, wl)
    assert cap == 4                                               # start is clipped up to min_cap
    assert resolve_session_cap("lb", float("inf"), wl) == (None, None)
    with pytest.raises(ValueError):
        resolve_session_cap(True, M, wl)


# ============================================================================ (2) LB-CAP / static caps
def test_lb_cap_value_is_a_function_of_memory_and_workload_only(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    E = length_biased_mean_context(wl)
    assert length_biased_session_cap(300_000, wl) == math.floor(300_000 / E) == 28
    # changes with M and with the workload, not with the seed / policy
    assert length_biased_session_cap(150_000, wl) == math.floor(150_000 / E)
    wl16 = WorkloadParams.from_dict({**cfg["workload"], "initial_context_tokens": 16000})
    assert length_biased_session_cap(300_000, wl16) < 28
    eng, _, cap = build_engine(cfg, RunSpec(exp="t", policy="lb_cap", seed=123, horizon_s=10.0,
                                            plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.1)))
    assert cap == eng.session_cap == 28
    _, _, cap2 = build_engine(cfg, RunSpec(exp="t", policy="cap_1p3", seed=0, horizon_s=10.0,
                                           plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.1)))
    assert cap2 == 36 == math.floor(1.3 * 28)
    _, _, cap3 = build_engine(cfg, RunSpec(exp="t", policy="lb_cap", seed=0, horizon_s=10.0, session_cap_override=9,
                                           plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.1)))
    assert cap3 == 9


def test_cap_c_for_arbitrary_integer_c(cfg):
    for c in (1, 7, 40):
        c2 = deep_update(cfg, {"policies": {"capc": {"kind": "fcfs", "session_cap": c}}})
        res = simulate(c2, RunSpec(exp="t", policy="capc", seed=2, horizon_s=1200.0, debug=True,
                                   plan=ArrivalPlan(kind="constant", horizon_s=1200.0, rate=0.3)))
        s = res["summary"]
        assert s["session_cap"] == c and s["max_in_system"] <= c and s["entries_over_cap"] == 0
    # the RunSpec override replaces the policy's cap (round-1 mechanism, still available)
    res = simulate(cfg, RunSpec(exp="t", policy="lb_cap", seed=2, horizon_s=600.0, session_cap_override=5,
                                plan=ArrivalPlan(kind="constant", horizon_s=600.0, rate=0.3)))
    assert res["summary"]["session_cap"] == 5 and res["summary"]["max_in_system"] <= 5


def test_e_lb_matches_monte_carlo(cfg):
    """E_lb = E[sum_{t<=T} E_t] / E[T], re-estimated by sampling session lengths."""
    wl = WorkloadParams.from_dict(cfg["workload"])
    T = turn_counts(np.random.default_rng(7), 400_000, wl.mean_turns, wl.max_turns)
    ctx_cum = np.concatenate([[0.0], np.cumsum([wl.end_len(t) for t in range(1, wl.max_turns + 1)])])
    mc = ctx_cum[T].sum() / T.sum()
    assert mc == pytest.approx(length_biased_mean_context(wl), rel=0.01)


@pytest.mark.parametrize("pol", ["lb_cap", "cap_1p3"])
def test_cap_never_exceeded_in_a_congested_run(cfg, pol):
    plan = ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.2, initial_cold=80, burst_n=60, burst_t0=400.0,
                       burst_width_s=30.0)
    res = simulate(cfg, RunSpec(exp="t", policy=pol, seed=4, horizon_s=1500.0, plan=plan, debug=True))
    s = res["summary"]
    cap = 28 if pol == "lb_cap" else 36
    assert s["session_cap"] == cap
    assert s["max_in_system"] == cap                         # the cap binds ...
    assert s["max_in_system"] <= cap and s["entries_over_cap"] == 0   # ... and is never exceeded
    assert s["max_gate"] > 0
    assert s["n_arrived"] == s["n_sessions_done"] + s["n_in_flight"]


# ============================================================================ (3) TTL pin
def test_ttl_pin_is_set_at_finish_and_expires_when_no_request_is_queued(cfg):
    tool = 50.0
    pol = {"kind": "fcfs", "ttl_pin_s": 2.0}
    dry = mk(cfg, {"kind": "fcfs"}, specs_of([(0.0, 2, tool)]))
    dry.run(30.0)
    t1 = dones(dry)[0][3]                                      # finish time of turn 1
    eng = mk(cfg, pol, specs_of([(0.0, 2, tool)]))
    eng.run(t1 + 1.0)
    eng._process_exogenous(eng.now)
    assert 0 in eng._pin and eng._pin[0][0] == pytest.approx(t1 + 2.0)
    E = eng.wl.end_len(1)
    assert eng._hard == {0: E} and eng._hard_sum == E and eng.idle[0] == E
    assert eng.n_pins == 1 and eng.n_pin_expired == 0
    eng.run(t1 + 3.0)
    eng._process_exogenous(eng.now)
    assert 0 not in eng._pin and eng._hard_sum == 0            # expired; KV is still resident but evictable
    assert eng.idle[0] == E and eng.n_pin_expired == 1
    eng.run(t1 + tool + 100.0)                                 # next turn: KV survived (memory is plentiful) -> hit
    assert [a[3] for a in admits(eng)] == [False, True]
    assert eng.n_stall_breaks == 0


def test_ttl_pin_longer_than_tool_time_is_dropped_at_admission(cfg):
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 20.0}, specs_of([(0.0, 2, 3.0)]))
    eng.run(500.0)
    assert [a[3] for a in admits(eng)] == [False, True]
    assert eng._pin == {} and eng._hard_sum == 0 and eng.idle == {}   # last turn frees the KV; no pin left behind
    assert eng.n_pin_expired == 0                                       # never expired: dropped when admitted
    assert eng._pin_next_time() == INF                                  # stale heap entry is discarded


def test_pin_persists_past_expiry_while_the_next_request_is_queued(cfg):
    """Continuum: a pin is freed at expiry only if the program has no request waiting."""
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of([(0.0, 3, 1.0)]), wo=BIG_WL, eo=BIG_EO, debug=False)
    eng.run(0.0)
    sid = 0
    eng._next_idx = 1                                          # the session's arrival is already consumed
    eng.idle[sid] = E1
    eng.idle_sum = E1
    eng._turn[sid] = 2
    eng.in_system = 1
    eng._arrived_t[sid] = 0.0
    eng._pin_seq += 1
    eng._pin[sid] = (5.0, eng._pin_seq)
    import heapq
    heapq.heappush(eng._pin_heap, (5.0, eng._pin_seq, sid))
    eng._refresh_prot(sid)
    # the request is queued at t=4 (before expiry) but the engine has not admitted it yet
    eng._enqueue_turn(sid, 4.0, 4.0)
    eng.reserved = 0
    eng._process_exogenous(6.0)                                # the expiry (t=5) is processed here
    assert sid in eng._pin and eng._hard_sum == E1             # still pinned: its request is waiting
    assert eng.n_pin_expired == 0
    eng.check_invariants()


def test_tool_return_exactly_at_pin_expiry_keeps_the_pin(cfg):
    """Tie rule: a tool return at exactly the expiry time is processed first, so the request is queued when the
    expiry fires and the pin persists until the request is admitted (Continuum: freed only if nothing is waiting)."""
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of([(0.0, 2, 5.0)]), debug=False)
    eng.run(200.0)
    assert [a[3] for a in admits(eng)] == [False, True]
    assert eng.n_pin_expired == 0 and eng._pin == {}
    # contrast: tool time just above the pin length -> the pin expires first
    eng2 = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of([(0.0, 2, 5.5)]), debug=False)
    eng2.run(200.0)
    assert eng2.n_pin_expired == 1


def test_pinned_kv_is_not_evicted_and_admission_waits(cfg):
    """3 sessions of 18100 tokens in 45000: s0, s1 finish turn 1 (pinned 5 s each, tool time 100 s); s2 arrives at 3 s
    and does not fit next to two pinned blocks. FCFS evicts s0's KV at once; the TTL pin makes s2 wait for s0's
    expiry, and only then evicts it."""
    rows = [(0.0, 2, 100.0), (0.0, 2, 100.0), (3.0, 1, 0.0)]
    plain = mk(cfg, {"kind": "fcfs"}, specs_of(rows), wo=BIG_WL, eo=BIG_EO)
    plain.run(60.0)
    d0 = [d for d in dones(plain) if d[1] == 0 and d[2] == 1][0][3]
    a2_plain = [a for a in admits(plain) if a[1] == 2][0][4]
    assert a2_plain < d0 + 5.0 - 1e-9 and plain.n_evictions >= 1       # no pin: s2 evicts s0's KV right away

    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of(rows), wo=BIG_WL, eo=BIG_EO)
    protected_after_evict = []
    orig = eng._evict

    def spy(need):
        before = dict(eng._hard)
        orig(need)
        protected_after_evict.append(all(s in eng.idle for s in before))
    eng._evict = spy
    eng.run(60.0)
    d0 = [d for d in dones(eng) if d[1] == 0 and d[2] == 1][0][3]
    a2 = [a for a in admits(eng) if a[1] == 2][0][4]
    assert a2 >= d0 + 5.0 - 1e-9                                       # waited for the first pin to expire
    assert a2 > a2_plain + 1.0
    assert eng.n_evictions >= 1 and protected_after_evict and all(protected_after_evict)
    assert eng.n_stall_breaks == 0                                     # waiting was enough, no forced release
    # s0's pin expired and its KV was the LRU evictable block -> its second turn (at ~100 s) would be a miss
    eng.run(400.0)
    second = {a[1]: a[3] for a in admits(eng) if a[2] == 2}
    assert second == {0: False, 1: True}


def test_stall_breaker_releases_latest_program_arrival_first(cfg):
    """Pins that outlive their expiry because their sessions are queued can deadlock a FCFS head that needs the
    memory; the breaker releases protection latest-arrival-first (largest session id) until the head fits."""
    rows = [(0.0, 1, 0.0), (0.0, 2, 1.0), (0.0, 2, 1.0)]      # session 0: one turn; sessions 1, 2: second turn queued
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of(rows), wo=BIG_WL, eo=BIG_EO, debug=False)
    eng.run(0.0)
    eng._next_idx = 3                                          # sessions 0..2 are already in the system
    eng.in_system = 3
    for sid in (1, 2):                                         # queued follow-ups holding pinned KV (expiry passed)
        eng.idle[sid] = E1
        eng.idle_sum += E1
        eng._turn[sid] = 2
        eng._arrived_t[sid] = 0.0
        eng._pin_seq += 1
        eng._pin[sid] = (0.0, eng._pin_seq)                    # no heap entry: the expiry already happened
    eng._turn[0] = 1
    eng._arrived_t[0] = 0.0
    eng._enqueue_turn(0, 1.0, 1.0)                             # head: first turn of session 0, needs 18100
    for sid in (1, 2):
        eng._enqueue_turn(sid, 2.0 + sid, 2.0 + sid)
        eng._refresh_prot(sid)
    eng.check_invariants()
    assert eng._hard_sum == 2 * E1 and eng.reserved + E1 + eng._hard_sum > eng.M
    eng.run(30.0)
    assert eng.n_stall_breaks == 1 and eng.n_released == 1
    a = {x[1]: x for x in admits(eng)}
    assert a[0][3] is False                                    # head admitted
    assert a[2][3] is False                                    # session 2 (latest arrival) lost its KV ...
    assert a[1][3] is True                                     # ... session 1 kept its pinned KV
    assert a[0][4] <= a[1][4]


def test_continuum_order_is_pinned_first_then_program_order(cfg):
    eng = mk(cfg, {"kind": "continuum", "ttl_pin_s": 50.0}, specs_of([(0.0, 5, 1.0)] * 6), debug=False)
    eng.run(0.0)
    delta = eng.wl.new_prompt_tokens
    for sid, turn in [(5, 2), (3, 2), (0, 1), (4, 3), (1, 2)]:       # queue order = arrival order of REQUESTS
        eng._turn[sid] = turn
        eng._arrived_t[sid] = 0.0
        eng._enqueue_turn(sid, float(len(eng._q)), 1.0)
    for sid in (1, 4):                                         # pinned KV for sessions 1 and 4 (turn >= 2)
        turn = eng._turn[sid]
        eng.idle[sid] = eng.wl.prompt_len(turn) - delta
        eng.idle_sum += eng.idle[sid]
        eng._pin_seq += 1
        eng._pin[sid] = (99.0, eng._pin_seq)
        eng._refresh_prot(sid)
    eng.pass_id += 1
    order = [r.sid for r in eng.policy.candidates(eng, 5.0)]
    assert order == [1, 4, 0, 3, 5]                            # pinned by program order, then the rest by program order
    prog = mk(cfg, {"kind": "program_fcfs"}, specs_of([(0.0, 5, 1.0)] * 6), debug=False)
    prog.run(0.0)
    for sid in (5, 3, 0, 4, 1):
        prog._turn[sid] = 1
        prog._arrived_t[sid] = 0.0
        prog._enqueue_turn(sid, float(len(prog._q)), 1.0)
    prog.pass_id += 1
    assert [r.sid for r in prog.policy.candidates(prog, 5.0)] == [0, 1, 3, 4, 5]


def test_eager_unpin_releases_a_pin_at_once_instead_of_waiting_for_expiry(cfg):
    """Same scene as the blocking-pin test. s2 arrives at 3 s while s1 still runs and only s0 is pinned (from d0 on).
    The idle-only rule makes s2 wait until s0's pin expires (d0 + 5 s); with ``ttl_unpin: eager`` the pin of s0 is
    released the moment s0 finishes, so s2 is admitted at d0 and s0's KV is the one evicted (s0's second turn misses)."""
    rows = [(0.0, 2, 100.0), (0.0, 2, 100.0), (3.0, 1, 0.0)]
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0, "ttl_unpin": "eager"}, specs_of(rows), wo=BIG_WL, eo=BIG_EO)
    eng.run(400.0)
    d0 = [d for d in dones(eng) if d[1] == 0 and d[2] == 1][0][3]
    a2 = [a for a in admits(eng) if a[1] == 2][0][4]
    assert a2 == pytest.approx(d0, abs=1e-9)                           # admitted at once, no wait for the expiry
    assert eng.n_eager_unpins == 1 and eng.n_stall_breaks == 0
    assert {a[1]: a[3] for a in admits(eng) if a[2] == 2} == {0: False, 1: True}
    idle_mode = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 5.0}, specs_of(rows), wo=BIG_WL, eo=BIG_EO)
    idle_mode.run(400.0)
    a2_idle = [a for a in admits(idle_mode) if a[1] == 2][0][4]
    assert idle_mode.n_eager_unpins == 0 and a2_idle == pytest.approx(d0 + 5.0, abs=1e-6)     # the registered rule waits


def _eager_state(cfg, mode, reserved_extra=0):
    """Sessions 1 and 2 hold pinned KV (E1 each, expiry far away); head = first turn of session 0 (needs E1)."""
    rows = [(0.0, 1, 0.0), (0.0, 2, 1.0), (0.0, 2, 1.0)]
    eng = mk(cfg, {"kind": "fcfs", "ttl_pin_s": 500.0, "ttl_unpin": mode}, specs_of(rows), wo=BIG_WL, eo=BIG_EO,
             debug=False)
    eng.run(0.0)
    eng._next_idx = 3
    eng.in_system = 3
    for sid in (1, 2):
        eng.idle[sid] = E1
        eng.idle_sum += E1
        eng._turn[sid] = 2
        eng._arrived_t[sid] = 0.0
        eng._pin_seq += 1
        eng._pin[sid] = (500.0, eng._pin_seq)
        eng._pin_heap.append((500.0, eng._pin_seq, sid))
        eng._refresh_prot(sid)
    eng._turn[0] = 1
    eng._arrived_t[0] = 0.0
    eng._enqueue_turn(0, 1.0, 1.0)
    eng.reserved += reserved_extra
    return eng


@pytest.mark.parametrize("mode", ["eager", "eager_fit"])
def test_eager_unpin_stops_as_soon_as_the_request_fits(cfg, mode):
    eng = _eager_state(cfg, mode)
    head = eng._q[0]
    assert eng.reserved + head.end + eng._hard_sum > eng.M            # blocked by the two pins (3 x 18100 > 45000)
    assert eng._eager_unpin(head) is True
    assert eng.n_eager_unpins == 1 and set(eng._pin) == {1} and set(eng._hard) == {1}      # session 2 (latest) went


def test_eager_unpin_variants_differ_when_unpinning_cannot_make_the_request_fit(cfg):
    """Running requests hold so much memory that the head cannot fit even with no pins: ``eager`` (literal reading)
    still releases every pin, ``eager_fit`` releases nothing."""
    literal = _eager_state(cfg, "eager", reserved_extra=30_000)
    assert literal._eager_unpin(literal._q[0]) is True and literal.n_eager_unpins == 2 and not literal._pin
    fit = _eager_state(cfg, "eager_fit", reserved_extra=30_000)
    assert fit._eager_unpin(fit._q[0]) is False and fit.n_eager_unpins == 0 and set(fit._pin) == {1, 2}


def test_eager_unpin_never_releases_the_requests_own_pin(cfg):
    eng = _eager_state(cfg, "eager")
    eng._pin_seq += 1
    own = 0                                                            # pin the head's own (resident) KV as well
    eng.idle[own] = 0 + 10_000
    eng.idle_sum += 10_000
    eng._pin[own] = (500.0, eng._pin_seq)
    eng._pin_heap.append((500.0, eng._pin_seq, own))
    eng._refresh_prot(own)
    head = eng._q[0]
    eng._eager_unpin(head)
    assert own in eng._pin                                             # kept; sessions 2 then 1 are the only victims


def test_mechanisms_reject_bad_ttl_unpin_specs():
    from prefixmeta.mechanisms import make_mechanisms
    assert make_mechanisms({"ttl_pin_s": 5.0}, None).ttl_unpin == "idle"
    with pytest.raises(ValueError):
        make_mechanisms({"ttl_pin_s": 5.0, "ttl_unpin": "lazy"}, None)
    with pytest.raises(ValueError):
        make_mechanisms({"ttl_unpin": "eager"}, None)                  # no TTL, nothing to unpin


# ============================================================================ (4) PEEK-like protection
def _peek_state(cfg, mode, queued_sids, tool_sids, policy_extra=None):
    """Idle KV of sessions in LRU order [1, 2], head = miss of session 0 that needs one eviction."""
    pol = {"kind": "fcfs", **({"protect_queued": mode} if mode else {}), **(policy_extra or {})}
    rows = [(0.0, 1, 0.0), (0.0, 2, 1.0), (0.0, 2, 1.0)]
    eng = mk(cfg, pol, specs_of(rows), wo=BIG_WL, eo=BIG_EO, debug=False)
    eng.run(0.0)
    eng._next_idx = 3
    eng.in_system = 3
    for sid in (1, 2):
        eng._turn[sid] = 2
        eng._arrived_t[sid] = 0.0
        eng.idle[sid] = E1
        eng.idle_sum += E1
    import heapq
    for sid in tool_sids:
        eng._tool_seq += 1
        heapq.heappush(eng._tool_heap, (1e9, eng._tool_seq, sid))
    eng._turn[0] = 1
    eng._arrived_t[0] = 0.0
    eng._enqueue_turn(0, 1.0, 1.0)                              # head, a miss
    for sid in queued_sids:
        eng._enqueue_turn(sid, 2.0 + sid, 2.0 + sid)
    for sid in (1, 2):
        eng._refresh_prot(sid)
    return eng


def test_peek_pin_evicts_the_tool_call_session_not_the_queued_one(cfg):
    plain = _peek_state(cfg, None, queued_sids=[1], tool_sids=[2])
    plain._schedule_pass()
    assert [r.sid for r in plain.prefill] == [0] and 1 not in plain.idle and 2 in plain.idle   # LRU = the queued one
    for mode in ("pin", "rank"):
        eng = _peek_state(cfg, mode, queued_sids=[1], tool_sids=[2])
        assert set(eng._hard) | set(eng._soft) == {1}
        eng.check_invariants()
        eng._schedule_pass()
        assert [r.sid for r in eng.prefill] == [0], mode
        assert 1 in eng.idle and 2 not in eng.idle, mode                 # the tool-call session paid, not the queued
        assert eng.n_soft_evictions == 0, mode


def test_peek_pin_blocks_but_rank_evicts_queued_kv_as_a_last_resort(cfg):
    pin = _peek_state(cfg, "pin", queued_sids=[1, 2], tool_sids=[])
    assert set(pin._hard) == {1, 2}
    pin._schedule_pass()
    assert pin.n_admitted == 0 and pin._first_blocked.sid == 0         # 18100 + 2 x 18100 > 45000, nothing evictable
    assert set(pin.idle) == {1, 2}
    rank = _peek_state(cfg, "rank", queued_sids=[1, 2], tool_sids=[])
    assert set(rank._soft) == {1, 2} and not rank._hard
    rank._schedule_pass()
    assert [r.sid for r in rank.prefill] == [0]
    assert rank.n_soft_evictions == 1 and set(rank.idle) == {2}        # LRU among the queued ones: session 1


def test_peek_pin_breaker_when_engine_idle(cfg):
    eng = _peek_state(cfg, "pin", queued_sids=[1, 2], tool_sids=[])
    eng.run(30.0)                                                      # engine idle + blocked -> breaker, no exception
    assert eng.n_stall_breaks == 1 and eng.n_released == 1
    a = {x[1]: x for x in admits(eng)}
    assert a[0][3] is False and a[1][3] is True and a[2][3] is False   # latest arrival (session 2) lost its KV


def test_peek_protection_follows_the_queue_state(cfg):
    eng = _peek_state(cfg, "pin", queued_sids=[], tool_sids=[1, 2])
    assert not eng._hard and not eng._soft                             # nobody queued -> nothing protected
    eng._tool_heap[:] = [x for x in eng._tool_heap if x[2] != 1]       # session 1's tool call returns ...
    eng._enqueue_turn(1, 5.0, 5.0)                                     # ... and its next request is queued
    assert set(eng._hard) == {1}
    eng.check_invariants()


@pytest.mark.parametrize("pol", ["peek", "peek_rank", "ttl10", "ttlf10", "ttl10e"])
def test_protected_kv_is_never_evicted_in_a_congested_run(cfg, pol):
    """Wrap _evict: after every eviction every block that was hard-protected before it is still resident. The test is
    only meaningful if protection was actually PRESENT at some eviction, so that is asserted per policy: hard
    protection for peek / ttl*, soft protection for peek_rank (which has no hard protection and so must evict soft
    blocks only after all unprotected blocks)."""
    plan = ArrivalPlan(kind="constant", horizon_s=900.0, rate=0.25, initial_cold=60, burst_n=40, burst_t0=200.0,
                       burst_width_s=20.0)
    c2 = deep_update(cfg, {})
    rs = RunSpec(exp="t", policy=pol, seed=5, horizon_s=900.0, plan=plan, debug=True,
                 engine_overrides={"kv_memory_tokens": 90_000})
    eng, _, _ = build_engine(c2, rs)
    checks = {"n": 0, "bad": 0, "hard_present": 0, "soft_present": 0, "soft_order_bad": 0}
    orig = eng._evict

    def spy(need):
        before = dict(eng._hard)
        soft_before = dict(eng._soft)
        free_before = sum(kv for sid, kv in eng.idle.items() if sid not in before and sid not in soft_before)
        orig(need)
        checks["n"] += 1
        checks["hard_present"] += int(bool(before))
        checks["soft_present"] += int(bool(soft_before))
        if not all(s in eng.idle for s in before):
            checks["bad"] += 1
        # soft ordering: a soft-protected block may be evicted only if the unprotected idle KV did not suffice
        evicted_soft = [s for s in soft_before if s not in eng.idle]
        if evicted_soft and free_before >= need:
            checks["soft_order_bad"] += 1
    eng._evict = spy
    eng.run(900.0)
    assert checks["n"] > 20 and checks["bad"] == 0 and checks["soft_order_bad"] == 0
    if pol == "peek_rank":
        assert checks["hard_present"] == 0 and checks["soft_present"] > 0 and eng.n_soft_evictions > 0
    else:
        assert checks["hard_present"] > 0, "hard protection never present at an eviction: the test would be vacuous"
    st = eng.stats()
    assert st["n_turns_done"] > 50
    if pol in ("ttl10", "ttlf10", "ttl10e"):
        assert st["n_pins"] > 0 and (st["n_pin_expired"] > 0 or st["n_eager_unpins"] > 0)


def test_peek_lpm_protection_never_binds_in_this_workload_so_it_is_lpm(cfg):
    """Round-2 review finding: under LPM order every queued session whose KV is resident is admitted before any miss
    can evict, so the hard PEEK protection is never present at an eviction and ``peek_lpm`` equals ``lpm`` here. This
    pins that observation (a property of this private-whole-session-KV workload, not of PEEK in general)."""
    plan = ArrivalPlan(kind="constant", horizon_s=900.0, rate=0.25, initial_cold=60, burst_n=40, burst_t0=200.0,
                       burst_width_s=20.0)
    out = {}
    for pol in ("lpm", "peek_lpm"):
        rs = RunSpec(exp="t", policy=pol, seed=5, horizon_s=900.0, plan=plan, debug=True,
                     engine_overrides={"kv_memory_tokens": 90_000})
        eng, _, _ = build_engine(deep_update(cfg, {}), rs)
        eng.trace = []
        present = {"n": 0}
        orig = eng._evict

        def spy(need, eng=eng, orig=orig, present=present):
            present["n"] += int(bool(eng._hard or eng._soft))
            orig(need)
        eng._evict = spy
        eng.run(900.0)
        out[pol] = (eng.trace, present["n"], eng.n_evictions)
    assert out["peek_lpm"][1] == 0 and out["peek_lpm"][2] > 20
    assert out["peek_lpm"][0] == out["lpm"][0]


# ============================================================================ (5) AIMD in the engine
def _aimd_cfg(cfg, **kw):
    return deep_update(cfg, {"policies": {"ai": {"kind": "fcfs", "session_cap": {"aimd": {"start": 5, **kw}}}}})


def test_aimd_ticks_every_interval_and_increments_by_one(cfg):
    c2 = _aimd_cfg(cfg, hit_threshold=-1.0, max_cap=8)         # never decrease
    plan = ArrivalPlan(kind="constant", horizon_s=2500.0, rate=0.5)
    res = simulate(c2, RunSpec(exp="t", policy="ai", seed=1, horizon_s=2500.0, plan=plan, debug=True))
    s = res["summary"]
    assert res["cap_trace"] == [(0.0, 5), (10.0, 6), (20.0, 7), (30.0, 8)]
    assert s["cap_min"] == 5 and s["cap_max"] == 8 and s["cap_final"] == 8
    assert s["n_ticks"] == 249                                  # ticks at 10, 20, ..., 2490 (the run ends at 2500)
    assert s["entries_over_cap"] == 0 and s["max_in_system"] <= 8
    assert s["max_gate"] > 0
    cm = [w["cap_mean"] for w in res["windows"]]
    assert cm[0] == pytest.approx((5 * 10 + 6 * 10 + 7 * 10 + 8 * 970) / 1000) and cm[-1] == 8.0


def test_aimd_multiplicative_decrease_never_below_min_cap_and_acts_by_attrition(cfg):
    c2 = _aimd_cfg(cfg, hit_threshold=2.0, min_cap=4)          # always decrease (hit rate <= 1 < 2)
    c2["policies"]["ai"]["session_cap"]["aimd"]["start"] = 40
    plan = ArrivalPlan(kind="constant", horizon_s=400.0, rate=0.4, initial_cold=60)
    res = simulate(c2, RunSpec(exp="t", policy="ai", seed=2, horizon_s=400.0, plan=plan, debug=True))
    caps = [c for _, c in res["cap_trace"]]
    assert caps[:7] == [40, 28, 19, 13, 9, 6, 4]               # floor(0.7 cap), clipped at 4
    assert min(caps) == 4 and caps[-1] == 4
    s = res["summary"]
    assert s["entries_over_cap"] == 0 and s["n_sessions_done"] > 0
    assert s["max_in_system"] > 4                              # sessions already inside are not evicted or paused


def test_aimd_start_defaults_to_n_lb_and_policy_specs_load(cfg):
    eng, _, cap = build_engine(cfg, RunSpec(exp="t", policy="aimd_cap", seed=0, horizon_s=10.0,
                                            plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.1)))
    assert cap == 28 and eng.aimd is not None and eng.aimd.rule == "hit" and eng.aimd.hit_threshold == 0.7
    eng2, _, cap2 = build_engine(cfg, RunSpec(exp="t", policy="concur_cap", seed=0, horizon_s=10.0,
                                              plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.1)))
    assert cap2 == 28 and eng2.aimd.rule == "concur" and eng2.aimd.increase == 2 and eng2.aimd.decrease == 0.5


# ============================================================================ (6) stop criteria and stats
def test_stop_backlog_counts_the_gate(cfg):
    plan = ArrivalPlan(kind="constant", horizon_s=3000.0, rate=0.5)
    base = dict(exp="t", policy="lb_cap", seed=1, horizon_s=3000.0, plan=plan)
    r_q = simulate(cfg, RunSpec(**base, stop_queue_above=60))              # queue alone never reaches 60 behind the cap
    r_b = simulate(cfg, RunSpec(**base, stop_backlog_above=60))
    assert not r_q["summary"]["stopped_early"]
    s = r_b["summary"]
    assert s["stopped_early"] == 1 and s["stop_reason"] == "backlog" and s["final_backlog"] >= 60
    assert s["sim_end_s"] == pytest.approx(s["stop_time"])


def test_stop_low_hit_stops_at_the_streak_onset_found_post_hoc(cfg):
    plan = ArrivalPlan(kind="constant", horizon_s=12_000.0, rate=0.0948, initial_cold=300)
    full = simulate(cfg, RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=12_000.0, plan=plan))
    hr = [w["hit_rate"] for w in full["windows"]]
    streak = next(j for j in range(len(hr) - 2) if all(h == h and h < 0.2 for h in hr[j:j + 3]))
    stopped = simulate(cfg, RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=12_000.0, plan=plan,
                                    stop_low_hit=(0.2, 3)))
    s = stopped["summary"]
    assert s["stop_reason"] == "hit" and s["stop_time"] == pytest.approx(streak * 1000.0)
    assert s["sim_end_s"] >= (streak + 3) * 1000.0 - 1e-6
    # a threshold nothing falls below never stops the run
    calm = simulate(cfg, RunSpec(exp="t", policy="lpm", seed=0, horizon_s=3000.0,
                                 plan=ArrivalPlan(kind="constant", horizon_s=3000.0, rate=0.04), stop_low_hit=(0.2, 3)))
    assert not calm["summary"]["stopped_early"]


def test_memory_traces_and_protected_tokens_are_recorded(cfg):
    c2 = deep_update(cfg, {"metrics": {"track_memory": True}})
    res = simulate(c2, RunSpec(exp="t", policy="ttl10", seed=3, horizon_s=1500.0,
                               plan=ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.1), debug=True))
    w = res["windows"][-1]
    assert 0 < w["reserved_mean"] <= 300_000 and 0 <= w["idle_mean"] and 0 < w["protected_mean"] <= w["idle_mean"] + 1
    off = simulate(deep_update(cfg, {"metrics": {"track_memory": False}}),
                   RunSpec(exp="t", policy="fcfs", seed=3, horizon_s=1500.0,
                                plan=ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.1)))
    assert math.isnan(off["windows"][-1]["reserved_mean"])


# ============================================================================ (7) reference simulator
# NOTE (round-2 review): this simulator is INDEPENDENT of the engine's code (plain lists, a full re-sort and a scheduling
# pass at every iteration boundary, no batching), but NOT independent of the specification: it re-implements the
# implementer's reading of each mechanism (idle-only vs eager pin release, persisting pins, breaker order, tie rules).
# It therefore catches implementation bugs, not misreadings of Continuum / PEEK / CONCUR; those are covered only by
# the named eager-unpin variants, which are NOT verified against the papers or their code.
def reference_trace2(cfg: dict, specs: SessionSpecs, spec: dict, horizon: float, *, M: float, cap: int | None = None,
                     aimd: dict | None = None, free_on_end: bool = True):
    """Naive iteration-by-iteration simulator with every round-2 mechanism written from the prose spec (plain lists, a
    full re-sort and a scheduling pass at EVERY iteration boundary, per-sequence arrays, no batching / counters).
    Returns (trace, cap_trace)."""
    e, w = cfg["engine"], cfg["workload"]
    L0, DELTA, D = w["initial_context_tokens"], w["new_prompt_tokens"], w["decode_tokens"]
    prompt_len = lambda turn: L0 + (turn - 1) * (DELTA + D)          # noqa: E731
    kind = spec["kind"]
    peek = spec.get("protect_queued")
    ttl = spec.get("ttl_pin_s")
    unpin = spec.get("ttl_unpin", "idle")
    arr = specs.arrival.tolist()
    n = len(arr)
    nt = specs.n_turns.tolist()
    tools = [specs.tools_of(i).tolist() for i in range(n)]
    turn = [1] * n
    arrived_at = [0.0] * n
    nxt = 0
    t = 0.0
    waiting, idle, running, tool_ev, gate = [], [], [], [], []
    pins = {}            # sid -> [expiry, expired_but_kept]
    released = set()
    reserved, rid_ctr, seq_ctr, in_sys = 0, 0, 0, 0
    pending_done, trace, cap_trace = [], [], []
    n_adm = n_hit = 0
    tk_adm = tk_hit = 0
    cur_cap = cap
    next_tick = aimd["interval_s"] if aimd else INF
    if cap is not None:
        cap_trace.append((0.0, cap))
    first_blocked = [None]

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

    def queued(sid):
        return any(r["sid"] == sid for r in waiting)

    def has_idle(sid):
        return any(s == sid for s, _ in idle)

    def is_hard(sid):
        if not has_idle(sid):
            return False
        if sid in pins:
            return True
        return peek == "pin" and queued(sid) and sid not in released

    def is_soft(sid):
        return has_idle(sid) and not is_hard(sid) and peek == "rank" and queued(sid)

    def order(now):
        fcfs = sorted(waiting, key=lambda r: (r["q"], r["rid"]))
        kv = dict(idle)

        def lpm(pool):
            hits = sorted([r for r in pool if r["sid"] in kv], key=lambda r: (-kv[r["sid"]], r["q"], r["rid"]))
            hs = {r["rid"] for r in hits}
            return hits + [r for r in pool if r["rid"] not in hs]
        if kind == "fcfs":
            return fcfs
        if kind == "lpm":
            return lpm(fcfs)
        if kind == "program_fcfs":
            return sorted(waiting, key=lambda r: r["sid"])
        if kind == "continuum":
            pw = sorted([r for r in waiting if r["sid"] in pins], key=lambda r: r["sid"])
            ids = {r["rid"] for r in pw}
            return pw + sorted([r for r in waiting if r["rid"] not in ids], key=lambda r: r["sid"])
        raise ValueError(kind)

    def eager_release(r):
        """Prose spec of ``ttl_unpin`` eager / eager_fit: while the request does not fit because of hard-protected
        KV of other sessions, unpin the pinned session with the largest session id (never its own); with eager_fit
        nothing is unpinned unless the request can then fit."""
        def blocked():
            return reserved + r["end"] + sum(k for s, k in idle if s != r["sid"] and is_hard(s)) > M
        if unpin == "eager_fit":
            nonpin = sum(k for s, k in idle if s != r["sid"] and is_hard(s) and s not in pins)
            if reserved + r["end"] + nonpin > M:
                return
        for s in sorted([s for s in pins if s != r["sid"]], reverse=True):
            if not blocked():
                break
            del pins[s]

    def schedule(now):
        nonlocal reserved, n_adm, n_hit
        first_blocked[0] = None
        if not waiting:
            return
        n_run = len(running)
        pending = sum(x["rem"] for x in running if x["kind"] == "pf")
        budget_left = e["prefill_chunk_budget"] - pending
        for r in order(now):
            if n_run >= e["max_running_seqs"] or budget_left <= 0:
                break
            hard_other = sum(k for s, k in idle if s != r["sid"] and is_hard(s))
            if reserved + r["end"] + hard_other > M and unpin != "idle" and pins:
                eager_release(r)
                hard_other = sum(k for s, k in idle if s != r["sid"] and is_hard(s))
            if reserved + r["end"] + hard_other > M:
                if first_blocked[0] is None:
                    first_blocked[0] = r
                break
            hit = has_idle(r["sid"])
            if hit:
                kv = [k for s, k in idle if s == r["sid"]][0]
                idle[:] = [(s, k) for s, k in idle if s != r["sid"]]
                pins.pop(r["sid"], None)
                released.discard(r["sid"])
                pos, new = kv, r["prompt"] - kv
            else:
                pos, new = 0, r["prompt"]
            while reserved + r["end"] + sum(k for _, k in idle) > M:
                victim = next((s for s, _ in idle if not is_hard(s) and not is_soft(s)), None)
                if victim is None:
                    victim = next(s for s, _ in idle if is_soft(s))
                idle[:] = [(s, k) for s, k in idle if s != victim]
            reserved += r["end"]
            waiting[:] = [x for x in waiting if x["rid"] != r["rid"]]
            running.append(dict(r=r, kind="pf", pos=pos, rem=new, ctx=0, left=0))
            trace.append(("A", r["sid"], r["turn"], hit, now))
            n_adm += 1
            n_hit += int(hit)
            n_run += 1
            budget_left -= new

    def finish(x, now):
        nonlocal reserved, seq_ctr, in_sys
        r = x["r"]
        sid = r["sid"]
        reserved -= r["end"]
        running.remove(x)
        trace.append(("D", sid, r["turn"], now))
        if r["turn"] < nt[sid]:
            idle.append((sid, r["end"]))
            if ttl is not None:
                pins[sid] = [now + ttl, False]
            released.discard(sid)
            z = tools[sid][r["turn"] - 1]
            turn[sid] = r["turn"] + 1
            seq_ctr += 1
            tool_ev.append((now + z, seq_ctr, sid))
        else:
            if not free_on_end:
                idle.append((sid, r["end"]))
            in_sys -= 1
            if gate and (cur_cap is None or in_sys < cur_cap):
                enter(gate.pop(0), now)

    def do_tick(tt):
        nonlocal tk_adm, tk_hit, next_tick, cur_cap
        dn, dh = n_adm - tk_adm, n_hit - tk_hit
        tk_adm, tk_hit = n_adm, n_hit
        hr = dh / dn if dn > 0 else float("nan")
        usage = (reserved + sum(k for _, k in idle)) / M
        next_tick += aimd["interval_s"]
        new = cur_cap
        if aimd["rule"] == "hit":
            if hr < aimd["hit_threshold"]:
                new = max(aimd["min_cap"], math.floor(cur_cap * aimd["decrease"]))
            else:
                new = cur_cap + aimd["increase"]
        else:
            if usage > aimd["u_high"] and hr < aimd["h_thresh"]:
                new = max(aimd["min_cap"], math.floor(cur_cap * aimd["decrease"]))
            elif usage < aimd["u_low"]:
                new = cur_cap + aimd["increase"]
        if aimd.get("max_cap") is not None:
            new = min(new, aimd["max_cap"])
        if new != cur_cap:
            cur_cap = new
            cap_trace.append((tt, new))
        while gate and in_sys < cur_cap:
            enter(gate.pop(0), tt)

    def events_upto(now):
        nonlocal nxt
        while True:
            ta = arr[nxt] if nxt < n else INF
            te = min(tool_ev) if tool_ev else (INF,)
            pend = [(v[0], s) for s, v in pins.items() if not v[1]]
            tp = min(pend) if pend else (INF, -1)
            tk = next_tick
            tmin = min(ta, te[0], tp[0], tk)
            if tmin > now:
                return
            if ta == tmin:
                arrived_at[nxt] = ta
                if cur_cap is not None and in_sys >= cur_cap:
                    gate.append(nxt)
                else:
                    enter(nxt, ta)
                nxt += 1
            elif te[0] == tmin:
                tool_ev.remove(te)
                enqueue(te[2], te[0], te[0])
            elif tp[0] == tmin:
                sid = tp[1]
                if queued(sid):
                    pins[sid][1] = True              # request already queued: pin persists until admitted
                else:
                    del pins[sid]
            else:
                do_tick(tk)

    def break_stall():
        blocked = first_blocked[0]
        if blocked is None:
            return False
        rel = 0
        for sid in sorted([s for s, _ in idle if is_hard(s)], reverse=True):
            hard_other = sum(k for s, k in idle if s != blocked["sid"] and is_hard(s))
            if reserved + blocked["end"] + hard_other <= M:
                break
            if sid == blocked["sid"]:
                continue
            pins.pop(sid, None)
            if peek == "pin" and queued(sid):
                released.add(sid)
            rel += 1
        return rel > 0

    while t < horizon:
        events_upto(t)
        for x in sorted(pending_done, key=lambda z: z["r"]["rid"]):
            finish(x, t)
        pending_done = []
        schedule(t)
        if not running:
            if waiting:
                if not any(is_hard(s) for s, _ in idle):
                    raise RuntimeError("reference: deadlock without protection")
                if not [1 for v in pins.values() if not v[1]]:
                    assert break_stall()
                    continue
                cands = [arr[nxt] if nxt < n else INF, min(tool_ev)[0] if tool_ev else INF, next_tick,
                         min(v[0] for v in pins.values() if not v[1])]
            else:
                cands = [arr[nxt] if nxt < n else INF, min(tool_ev)[0] if tool_ev else INF, next_tick]
            nx = min(cands)
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
    return trace, cap_trace


def _assert_traces_equal(a, b):
    assert len(a) == len(b), (len(a), len(b))
    for x, y in zip(a, b):
        assert x[:-1] == y[:-1], (x, y)
        assert x[-1] == pytest.approx(y[-1], rel=1e-9, abs=1e-9), (x, y)


REF_CASES = [
    ("peek_pin", {"kind": "fcfs", "protect_queued": "pin"}, None, None),
    ("peek_rank", {"kind": "fcfs", "protect_queued": "rank"}, None, None),
    ("peek_lpm", {"kind": "lpm", "protect_queued": "pin"}, None, None),
    ("ttl_cont", {"kind": "continuum", "ttl_pin_s": 5.0}, None, None),
    ("ttl_fcfs", {"kind": "fcfs", "ttl_pin_s": 5.0}, None, None),
    ("ttl_fcfs_long", {"kind": "fcfs", "ttl_pin_s": 20.0}, None, None),
    ("ttl_cont_eager", {"kind": "continuum", "ttl_pin_s": 5.0, "ttl_unpin": "eager"}, None, None),
    ("ttl_cont_eager_fit", {"kind": "continuum", "ttl_pin_s": 5.0, "ttl_unpin": "eager_fit"}, None, None),
    ("ttl_fcfs_eager_long", {"kind": "fcfs", "ttl_pin_s": 20.0, "ttl_unpin": "eager"}, None, None),
    ("ttl_peek_rank", {"kind": "fcfs", "ttl_pin_s": 3.0, "protect_queued": "rank"}, None, None),
    ("ttl_peek_pin", {"kind": "continuum", "ttl_pin_s": 3.0, "protect_queued": "pin"}, None, None),
    ("prog", {"kind": "program_fcfs"}, None, None),
    ("aimd_hit", {"kind": "fcfs"}, None,
     {"rule": "hit", "interval_s": 10.0, "min_cap": 4, "hit_threshold": 0.7, "increase": 1, "decrease": 0.7,
      "start": 12}),
    ("aimd_concur", {"kind": "fcfs"}, None,
     {"rule": "concur", "interval_s": 10.0, "min_cap": 4, "u_low": 0.2, "u_high": 0.5, "h_thresh": 0.2,
      "increase": 2, "decrease": 0.5, "start": 12}),
]


@pytest.mark.parametrize("batch", [True, False])
@pytest.mark.parametrize("scenario", [(70_000, 0.5, 15, 20), (150_000, 0.3, 10, 40)])
@pytest.mark.parametrize("name,pol,cap,aimd", REF_CASES, ids=[c[0] for c in REF_CASES])
def test_engine_matches_naive_reference_with_mechanisms(cfg, name, pol, cap, aimd, scenario, batch):
    M, rate, cold, burst = scenario
    spec = dict(pol)
    if aimd:
        spec["session_cap"] = {"aimd": dict(aimd)}
    c2 = deep_update(cfg, {"policies": {"x": spec}})
    wl = WorkloadParams.from_dict(c2["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=rate, initial_cold=cold, burst_n=burst, burst_t0=100.0,
                       burst_width_s=10.0)
    specs = build_specs(wl, plan, 21)
    H = 900.0
    rs = RunSpec(exp="t", policy="x", seed=0, horizon_s=H, plan=ArrivalPlan(kind="none", horizon_s=H), debug=True,
                 engine_overrides={"kv_memory_tokens": M, "batch_decode_iterations": batch})
    eng, _, eng_cap = build_engine(c2, rs, specs)
    eng.trace = []
    eng.run(H)
    ref, ref_caps = reference_trace2(c2, specs, spec, H, M=M, cap=eng_cap, aimd=aimd)
    assert sum(1 for x in eng.trace if x[0] == "D") > 50
    _assert_traces_equal(eng.trace, ref)
    if aimd:
        assert [c for _, c in eng.cap_trace] == [c for _, c in ref_caps]
        for (t1, _), (t2, _) in zip(eng.cap_trace, ref_caps):
            assert t1 == pytest.approx(t2, abs=1e-9)
        assert eng.stats()["n_ticks"] in (89, 90)          # ticks at 10, ..., 890 (+ 900 if the last boundary reaches it)
    st = eng.stats()
    if "ttl_pin_s" in pol:
        assert st["n_pins"] > 0
        if pol.get("ttl_unpin", "idle") == "idle":
            assert st["n_pin_expired"] > 0 and st["n_eager_unpins"] == 0
        else:                                              # pins are released early; most never reach their expiry
            assert st["n_eager_unpins"] > 0
    assert any(x[0] == "A" and x[3] for x in eng.trace) and any(x[0] == "A" and not x[3] and x[2] > 1 for x in eng.trace)


def test_reference_scenarios_exercise_the_breaker_and_soft_evictions(cfg):
    """The parametrised equality above is only convincing if the hard cases actually occur in it."""
    wl = WorkloadParams.from_dict(cfg["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=0.5, initial_cold=15, burst_n=20, burst_t0=100.0,
                       burst_width_s=10.0)
    specs = build_specs(wl, plan, 21)
    seen = {"breaks": 0, "soft": 0, "eager": 0}
    for spec in ({"kind": "fcfs", "protect_queued": "pin"}, {"kind": "fcfs", "ttl_pin_s": 5.0},
                 {"kind": "fcfs", "protect_queued": "rank"},
                 {"kind": "continuum", "ttl_pin_s": 5.0, "ttl_unpin": "eager"}):
        c2 = deep_update(cfg, {"policies": {"x": spec}})
        rs = RunSpec(exp="t", policy="x", seed=0, horizon_s=900.0, plan=ArrivalPlan(kind="none", horizon_s=900.0),
                     engine_overrides={"kv_memory_tokens": 70_000})
        eng, _, _ = build_engine(c2, rs, specs)
        eng.run(900.0)
        seen["breaks"] += eng.n_stall_breaks
        seen["soft"] += eng.n_soft_evictions
        seen["eager"] += eng.n_eager_unpins
    assert seen["breaks"] > 0 and seen["soft"] > 0 and seen["eager"] > 0


# ============================================================================ (8) determinism
@pytest.mark.parametrize("pol", ["ttl10", "peek", "aimd_cap", "lb_cap"])
def test_mechanism_runs_are_deterministic_and_pool_equals_serial(cfg, pol):
    from prefixmeta import runner
    specs = [RunSpec(exp="t", policy=pol, seed=s, horizon_s=1500.0,
                     plan=ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.15, initial_cold=40),
                     engine_overrides={"kv_memory_tokens": 120_000}) for s in (1, 2)]
    a = [simulate(cfg, rs) for rs in specs]
    b = [simulate(cfg, rs) for rs in specs]
    with runner.Runner(cfg, 2) as R:
        c = R.run(specs)
    for x, y, z in zip(a, b, c):
        import pandas as pd
        keep = lambda r: repr(sorted((k, v) for k, v in r["summary"].items() if not k.startswith("wall")))   # noqa: E731
        win = lambda r: pd.DataFrame(r["windows"]).to_csv(index=False)                                    # noqa: E731
        assert keep(x) == keep(y) == keep(z)
        assert win(x) == win(y) == win(z) and x["qtrace"] == y["qtrace"] == z["qtrace"]
    assert keep(a[0]) != keep(a[1])                                                                 # seeds differ


# ============================================================================ (9) regression against recorded round-1 results
ROUND1_E1 = Path(__file__).resolve().parent.parent / "results" / "prefix_meta_e1" / "20261021-005837" / "runs.csv"
ROUND1_E0 = Path(__file__).resolve().parent.parent / "results" / "prefix_meta_e0" / "20261021-005706" / "e0_summary.json"


@pytest.mark.skipif(not (ROUND1_E1.exists() and ROUND1_E0.exists()), reason="round-1 result files not present")
@pytest.mark.parametrize("policy", ["fcfs", "lpm", "lpm128", "aging10", "fcfs_cap", "fcfs_cap_lb"])
def test_round2_engine_reproduces_recorded_round1_runs(cfg, policy):
    """With every round-2 mechanism off the engine must give exactly the recorded round-1 E1 numbers (2x lambda_miss,
    300 cold sessions, seed 0, 30000 s), which were produced at commit 7e9704e before this code existed."""
    import json
    import pandas as pd
    lam_miss = json.loads(ROUND1_E0.read_text())["lambda_miss"]
    rec = pd.read_csv(ROUND1_E1)
    row = rec[(rec["variant"] == "base") & (rec["seed"] == 0) & (rec["policy"] == policy)
              & np.isclose(rec["lam_mult"], 2.0)].iloc[0]
    plan = ArrivalPlan(kind="constant", horizon_s=30000.0, rate=2.0 * lam_miss, initial_cold=300)
    s = simulate(cfg, RunSpec(exp="t", policy=policy, seed=0, horizon_s=30000.0, plan=plan))["summary"]
    for k in ("n_admitted", "n_hits", "n_evictions", "evicted_tokens", "final_queue", "n_turns_done",
              "n_sessions_done", "max_queue"):
        assert s[k] == row[k], (policy, k, s[k], row[k])
    assert s["tail_hit_rate"] == pytest.approx(row["tail_hit_rate"], abs=1e-12)
    assert s["tail_queue_mean"] == pytest.approx(row["tail_queue_mean"], rel=1e-9)
