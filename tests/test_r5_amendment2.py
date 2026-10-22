"""Round-5 amendment 2 (stage 3, review findings F2-F5): tail-first eviction of a preempted request's cached KV, the thrash counters and
window columns, processed-recompute accounting, the first-chunk admission sensitivity and the lpm_fallback ordering in the new modes.

Layers: (1) the eviction primitive on a hand-built idle table; (2) hand-built engine scenarios with a known answer; (3) counters against an
independent recomputation from the trace; (4) the naive reference simulator (tests/test_r5_engine.py) with the amendment-2 switches."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

import pytest

from prefixmeta.engine import Engine, EngineParams, Request
from prefixmeta.mech_runner import load_mech_config
from prefixmeta.sim import deep_update

from test_r5_engine import (DYN, SMALL_WL, _congested, _assert_dyn_traces_equal, _ref_vs_engine, mk, specs_of, trace_of)

REPO = Path(__file__).resolve().parent.parent
CFG5 = REPO / "configs" / "prefix_meta_r5.yaml"


@pytest.fixture(scope="module")
def cfg5() -> dict:
    return load_mech_config(str(CFG5), REPO)


# ============================================================================ (1) the eviction primitive
def _bare_engine(cfg5, rule="tail"):
    eng = mk(cfg5, specs_of([(0.0, 3, 1.0)] * 3), wo=SMALL_WL,
             eo={"alloc_mode": "ondemand_preempt", "kv_memory_tokens": 1e9, "victim_kv_eviction": rule}, debug=False)
    return eng


def _put(eng: Engine, table: Dict[int, Tuple[int, bool]]) -> None:
    """idle table in LRU order; ``True`` = the session has a live re-queued (resumed) request, i.e. it is a preemption victim."""
    eng.idle.clear()
    eng._waiting.clear()
    eng.idle_sum = 0
    for sid, (kv, victim) in table.items():
        eng.idle[sid] = kv
        eng.idle_sum += kv
        if victim:
            r = Request(100 + sid, sid, 1, 0.0, 0.0, 1000, 1010)
            r.resumed = True
            eng._waiting[sid] = r


def test_tail_eviction_trims_only_the_victim_and_only_by_the_deficit(cfg5):
    eng = _bare_engine(cfg5)
    _put(eng, {0: (5000, False), 1: (3000, True), 2: (4000, False)})       # LRU order: whole A, victim V, whole B
    eng._evict_dyn(5500)                                                   # A goes whole (5000), V is trimmed by 500
    assert list(eng.idle.items()) == [(1, 2500), (2, 4000)] and eng.idle_sum == 6500
    assert eng.n_evictions == 1 and eng.n_partial_evictions == 1 and eng.evicted_tokens == 5500
    eng._evict_dyn(2500)                                                   # exactly the rest of V: removed entirely, not partial
    assert list(eng.idle.items()) == [(2, 4000)] and eng.idle_sum == 4000
    assert eng.n_evictions == 2 and eng.n_partial_evictions == 1 and eng.evicted_tokens == 8000
    _put(eng, {0: (5000, False), 1: (3000, True), 2: (4000, False)})
    eng._evict_dyn(8100)                                                   # A, V whole, then a NON-victim is never trimmed: B whole
    assert list(eng.idle.items()) == [] and eng.idle_sum == 0
    _put(eng, {2: (4000, False), 1: (3000, True)})                         # a non-victim at the LRU head absorbs the deficit whole
    eng._evict_dyn(10)
    assert list(eng.idle.items()) == [(1, 3000)] and eng.idle_sum == 3000
    with pytest.raises(AssertionError):
        eng._evict_dyn(10_000)                                             # more than is cached cannot be evicted


def test_whole_rule_is_the_stage1_behaviour(cfg5):
    eng = _bare_engine(cfg5, "whole")
    _put(eng, {1: (3000, True), 2: (4000, False)})
    eng._evict_dyn(1)
    assert list(eng.idle.items()) == [(2, 4000)] and eng.n_partial_evictions == 0 and eng.n_evictions == 1


def test_invalid_amendment2_parameters_are_refused(cfg5):
    with pytest.raises(ValueError):
        EngineParams.from_dict({**cfg5["engine"], "victim_kv_eviction": "nope"})
    with pytest.raises(ValueError):
        EngineParams.from_dict({**cfg5["engine"], "ondemand_admission": "nope"})
    # defaults: the registered rules
    ep = EngineParams.from_dict(cfg5["engine"])
    assert ep.victim_kv_eviction == "tail" and ep.ondemand_admission == "full_isl"
    # tail-first eviction is implemented for LRU only: explicit refusal instead of a silent whole-session fallback
    c2 = deep_update(cfg5, {"policies": {"ev": {"kind": "fcfs", "eviction": "random"}}})
    with pytest.raises(ValueError):
        mk(c2, specs_of([(0.0, 1, 0.0)]), policy="ev", eo={"alloc_mode": "ondemand_preempt"})
    mk(c2, specs_of([(0.0, 1, 0.0)]), policy="ev", eo={"alloc_mode": "ondemand_preempt", "victim_kv_eviction": "whole"})


# ============================================================================ (2) hand-built scenarios
def test_ratio_retraction_keeps_the_prompt_head_under_tail_eviction(cfg5):
    """Review finding F2 for ratio_reserve: with an empty idle pool the stage-1 rule evicted the retracted request's whole prompt (the
    20 x n headroom is far below any whole session). Under the tail rule only the headroom (20 x remaining decode requests) is trimmed.
    Three single-turn sessions, prompt 1000, d = 100, M just above the three prompts; the third request is retracted at the first
    decode OOM."""
    sp = specs_of([(0.0, 1, 0.0)] * 3)
    wo = {**SMALL_WL, "decode_tokens": 100}
    out = {}
    for rule in ("whole", "tail"):
        eng = mk(cfg5, sp, wo=wo, eo={"alloc_mode": "ratio_reserve", "kv_memory_tokens": 3250, "victim_kv_eviction": rule,
                                      "init_new_token_ratio": 0.01, "min_new_token_ratio_factor": 1.0})
        eng.run(100.0)
        out[rule] = (eng.trace, eng.stats())
    pw = [x for x in out["whole"][0] if x[0] == "P"]
    pt = [x for x in out["tail"][0] if x[0] == "P"]
    assert pw and len(pw) == len(pt)
    rw = [x for x in out["whole"][0] if x[0] == "R"]
    rt = [x for x in out["tail"][0] if x[0] == "R"]
    assert rw and rt
    assert sum(x[3] for x in rw) < sum(x[3] for x in rt), "tail rule must retain more of the retracted prompts than the whole rule"
    assert out["tail"][1]["n_readmit_with_kv"] >= out["whole"][1]["n_readmit_with_kv"]
    assert out["tail"][1]["n_turns_done"] == out["whole"][1]["n_turns_done"] == 3


def test_first_chunk_admission_admits_what_the_full_sequence_test_refuses(cfg5):
    """M = 1350, two prompts of 1000 (d = 10), chunk budget 400 (the first request takes the whole first chunk, so the second one's first
    chunk is empty): next to the 400 tokens held after the first admission the second request's cached prefix + first chunk (0 + 0) fits,
    but its whole sequence does not (400 + 1000 > 1350)."""
    sp = specs_of([(0.0, 1, 0.0), (0.0, 1, 0.0)])
    base = {"kv_memory_tokens": 1350, "alloc_mode": "ondemand_preempt", "prefill_chunk_budget": 400,
            "admission_limited_by_prefill_budget": False}
    full = mk(cfg5, sp, wo=SMALL_WL, eo={**base, "ondemand_admission": "full_isl"})
    full.run(50.0)
    a = trace_of(full, "A")
    assert a[0][4] == 0.0 and a[1][4] > 0.0
    chunk = mk(cfg5, sp, wo=SMALL_WL, eo={**base, "ondemand_admission": "first_chunk"})
    chunk.run(50.0)
    a2 = trace_of(chunk, "A")
    assert a2[0][4] == 0.0 and a2[1][4] == 0.0
    assert chunk.stats()["n_turns_done"] == 2


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("kind", ["fcfs", "lpm"])
def test_lpm_fallback_with_threshold_zero_is_fcfs_and_a_huge_threshold_is_lpm(cfg5, mode, kind):
    c2 = deep_update(cfg5, {"policies": {"fb0": {"kind": "lpm_fallback", "threshold": 0, "eviction": "lru"},
                                         "fbinf": {"kind": "lpm_fallback", "threshold": 10 ** 9, "eviction": "lru"}}})
    import numpy as np
    from prefixmeta.workload import ArrivalPlan, WorkloadParams, build_specs
    wl = WorkloadParams.from_dict(c2["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=0.5, initial_cold=20, burst_n=40, burst_t0=100.0, burst_width_s=10.0)
    specs = build_specs(wl, plan, 11)
    tr = {}
    for pol in ("fcfs_lru", "lpm_lru", "fb0", "fbinf"):
        eng = mk(c2, specs, policy=pol, eo={"kv_memory_tokens": 70_000, "alloc_mode": mode}, horizon=900.0)
        eng.run(900.0)
        tr[pol] = eng.trace
    assert tr["fb0"] == tr["fcfs_lru"] and tr["fbinf"] == tr["lpm_lru"] and tr["fcfs_lru"] != tr["lpm_lru"]


# ============================================================================ (3) counters against the trace
def _thrash_run(cfg5, mode, rule="tail"):
    eng, _ = _congested(cfg5, mode, 45_000, eo={"admission_limited_by_prefill_budget": False, "victim_kv_eviction": rule},
                        cls=Engine, rate=0.6, cold=30, burst=60, horizon=1500.0)
    return eng


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("rule", ["tail", "whole"])
def test_thrash_counters_equal_a_recount_from_the_trace(cfg5, mode, rule):
    eng = _thrash_run(cfg5, mode, rule)
    s = eng.stats()
    cnt: Dict[Tuple[int, int], int] = defaultdict(int)
    win_max: Dict[int, int] = defaultdict(int)
    win_n: Dict[int, int] = defaultdict(int)
    for x in eng.trace:
        if x[0] == "P":
            key = (x[1], x[2])
            cnt[key] += 1
            k = int(x[4] // 1000.0)
            win_max[k] = max(win_max[k], cnt[key])
            win_n[k] += 1
    assert s["n_preempt"] == sum(cnt.values()) > 20
    assert s["n_turns_preempted"] == len(cnt)
    assert s["max_preempt_per_turn"] == max(cnt.values())
    assert s["n_turns_preempted_ge3"] == sum(1 for v in cnt.values() if v >= 3)
    wins = eng.rec.finalize(eng.end_time)
    for w in wins:
        k = w["window"]
        assert w["preemptions"] == win_n.get(k, 0)
        assert w["preempt_max_turn"] == win_max.get(k, 0), k
    # processed recompute work: bounded by the demand; per-window columns sum to the run totals
    assert 0 < s["recompute_processed_tokens"] <= s["recompute_tokens"]
    assert s["recompute_processed_tokens"] <= s["processed_prefill_tokens"]
    complete = [w for w in wins]
    assert sum(w["recompute_processed"] for w in complete) <= s["recompute_processed_tokens"]
    assert sum(w["lost_prefill"] for w in complete) <= s["lost_prefill_tokens"]
    assert sum(w["recompute_tokens"] for w in complete) <= s["recompute_tokens"]


def test_the_stage1_rule_loses_more_prefill_work_than_the_tail_rule(cfg5):
    """The point of finding F2: on a congested run the tail rule re-admits with more surviving KV (ondemand_preempt; ratio_reserve is
    equal here: the survivors' growth consumes every retracted prompt before its re-admission) and never with less."""
    for mode in DYN:
        w, t = _thrash_run(cfg5, mode, "whole").stats(), _thrash_run(cfg5, mode, "tail").stats()
        assert t["n_readmit_with_kv"] >= w["n_readmit_with_kv"]
        if mode == "ondemand_preempt":
            assert t["n_readmit_with_kv"] > w["n_readmit_with_kv"] > 0
            assert t["n_readmit_with_kv"] / t["n_readmit"] > w["n_readmit_with_kv"] / w["n_readmit"]


# ============================================================================ (4) naive reference with the amendment-2 switches
@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("kind", ["fcfs", "lpm"])
@pytest.mark.parametrize("rule", ["whole", "tail"])
def test_engine_matches_the_reference_under_both_victim_rules(cfg5, mode, kind, rule):
    tr_e, ref, eng = _ref_vs_engine(cfg5, mode, kind, 70_000, seed=21, eo={"victim_kv_eviction": rule})
    assert sum(1 for x in tr_e if x[0] == "P") >= 3
    _assert_dyn_traces_equal(tr_e, ref)


@pytest.mark.parametrize("kind", ["fcfs", "lpm"])
@pytest.mark.parametrize("M,eo", [(70_000, {}), (45_000, {"admission_limited_by_prefill_budget": False}), (70_000, {"prefill_chunk_budget": 1500})])
def test_engine_matches_the_reference_with_first_chunk_admission(cfg5, kind, M, eo):
    tr_e, ref, eng = _ref_vs_engine(cfg5, "ondemand_preempt", kind, M, seed=21, eo={**eo, "ondemand_admission": "first_chunk"})
    assert sum(1 for x in tr_e if x[0] == "P") >= 3
    _assert_dyn_traces_equal(tr_e, ref)
    base_eo = {k: v for k, v in eo.items()}
    tr_f, _, _ = _ref_vs_engine(cfg5, "ondemand_preempt", kind, M, seed=21, eo=base_eo)
    assert [x[:-1] for x in tr_f] != [x[:-1] for x in tr_e], "first_chunk must change the schedule on a congested run"
