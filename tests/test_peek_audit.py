"""Source-audit tests for the opt-in private-prefix PEEK projection.

Expected orders are hand-derived from upstream group-major sections and demand*depth eviction,
not from paper summaries. These tests do not claim to cover shared-prefix or block-allocation behavior.
"""
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from prefixmeta.engine import Engine, Request
from prefixmeta.mechanisms import Mechanisms, make_mechanisms
from prefixmeta.policies import make_policy
from prefixmeta.sim import RunSpec, build_engine, deep_update, load_config
from prefixmeta.workload import ArrivalPlan


def ordering_view(lengths):
    requests = [Request(i, i, 1, float(i), float(i), 1000, 1100) for i in range(len(lengths))]
    view = SimpleNamespace(
        pass_id=1, _waiting={r.sid: r for r in requests},
        idle=OrderedDict((sid, length) for sid, length in enumerate(lengths) if length is not None),
    )
    view.fifo_iter = lambda: iter(requests)
    view.cached_prefix = lambda sid: Engine.cached_prefix(view, sid)
    return view


def test_singleton_order_is_warm_fifo_not_fcfs_or_longest_prefix():
    view = ordering_view([None, 80, 900, None, 120])
    policy = make_policy({"kind": "peek_singleton"})
    assert [r.sid for r in policy.candidates(view, 10.0)] == [1, 2, 4, 0, 3]


def test_singleton_warm_threshold_is_strict_and_cold_cached_requests_are_not_lost():
    view = ordering_view([32, None, 33, 1])
    assert [r.sid for r in make_policy({"kind": "peek_singleton"}).candidates(view, 10.0)] == [2, 0, 1, 3]


def test_singleton_candidate_order_uses_one_residency_snapshot():
    view = ordering_view([None, 80, 900])
    order = make_policy({"kind": "peek_singleton"}).candidates(view, 10.0)
    assert next(order).sid == 1
    del view.idle[2]
    assert [r.sid for r in order] == [2, 0]


def test_singleton_equal_arrivals_follow_source_stride_and_dynamic_share():
    view = ordering_view([100, 200, 300, 400, 500, 600])
    for request in view._waiting.values():
        request.qtime = 0.0
    policy = make_policy({"kind": "peek_singleton"})
    # Lane A is [0,1,2,3,4,5], lane B is [5,4,3,2,1,0]. With initial fairness EMA .3,
    # the first shares are .39 and .453. Clocks restart at one stride for each scheduling pass.
    assert [r.sid for r in policy.candidates(view, 10.0)] == [0, 5, 1, 2, 4, 3]
    assert policy._fair_share == pytest.approx(0.39)
    assert [r.sid for r in policy.candidates(view, 10.0)] == [0, 5, 1, 4, 2, 3]
    assert policy._fair_share == pytest.approx(0.453)


def eviction_state(mode):
    eng = object.__new__(Engine)
    # Oldest first: long queued, hard protected, short queued, equal short queued, unprotected.
    eng.idle = OrderedDict([(0, 900), (1, 10), (2, 100), (3, 100), (4, 500)])
    eng.idle_sum = sum(eng.idle.values())
    eng._hard = {1: 10}
    eng._hard_sum = 10
    eng._soft = {0: 900, 2: 100, 3: 100}
    eng._soft_sum = 1100
    eng._pin = {1: (100.0, 0)}
    eng._released = set()
    eng._ended = set()
    eng._evict_mode = "lru"
    eng._peek = mode
    eng.n_evictions = eng.evicted_tokens = eng.n_soft_evictions = 0
    return eng


def test_length_ranking_uses_unprotected_first_then_shortest_and_lru_ties():
    eng = eviction_state("rank_length")
    eng._evict(550)
    assert list(eng.idle) == [0, 1, 3]
    assert eng.evicted_tokens == 600 and eng.n_soft_evictions == 1
    assert eng._hard == {1: 10} and eng._soft == {0: 900, 3: 100}
    assert eng.idle_sum == 1010 and eng._soft_sum == 1000


def test_legacy_rank_keeps_lru_order_for_positive_demand():
    eng = eviction_state("rank")
    eng._evict(550)
    assert list(eng.idle) == [1, 2, 3]
    assert eng.evicted_tokens == 1400 and eng.n_soft_evictions == 1


@pytest.mark.parametrize("eviction", ["random", "mru_idle"])
def test_length_ranking_rejects_non_lru_composition(eviction):
    with pytest.raises(ValueError, match="rank_length requires"):
        make_mechanisms({"protect_queued": "rank_length", "eviction": eviction}, None)
    with pytest.raises(ValueError, match="rank_length requires"):
        Mechanisms(protect_queued="rank_length", eviction=eviction)


@pytest.mark.parametrize(
    "policy,needs_soft_evictions",
    [({"kind": "peek_singleton", "protect_queued": "rank_length"}, False),
     ({"kind": "fcfs", "protect_queued": "rank_length"}, True)],
    ids=["singleton-plus-score", "score-only"],
)
def test_projection_integrates_without_hard_pins_and_conserves_memory(policy, needs_soft_evictions):
    repo = Path(__file__).resolve().parent.parent
    cfg = load_config(str(repo / "configs" / "prefix_meta.yaml"))
    # The default 300k-token memory never fills at this load; 60k does, so the eviction path (and, for the
    # FCFS order, the soft-protected sorted path) is exercised under debug invariant checks.
    cfg = deep_update(cfg, {"engine": {"kv_memory_tokens": 60000}, "policies": {"audit": policy}})
    spec = RunSpec(exp="audit-test", policy="audit", seed=701, horizon_s=300.0, debug=True,
                   plan=ArrivalPlan(kind="constant", horizon_s=300.0, rate=0.3, initial_cold=30))
    eng, _, _ = build_engine(cfg, spec)
    eng.run(300.0)
    eng.check_invariants()
    assert eng.n_admitted > 0 and eng.n_evictions > 0
    if needs_soft_evictions:
        assert eng.n_soft_evictions > 0
    assert eng.max_resident <= eng.M and eng._hard_sum == 0
    assert eng.n_stall_breaks == 0
