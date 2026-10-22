"""Tests for the round-4 eviction rules (LRU / RANDOM / MRU_IDLE): the pure victim-selection function, the dedicated random
stream, and the engine integration (victims are only idle, unprotected KV; MRU picks the latest idle start; RANDOM is
reproducible per seed and uses its own stream; the LRU path is unchanged)."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from prefixmeta.engine import Engine
from prefixmeta.eviction import EVICTION_MODES, EVICTION_STREAM, eviction_rng, select_victims
from prefixmeta.mechanisms import make_mechanisms
from prefixmeta.sim import RunSpec, build_engine, deep_update, load_config, simulate
from prefixmeta.workload import ArrivalPlan, SessionSpecs, WorkloadParams, build_specs

CFG_PATH = Path(__file__).resolve().parent.parent / "configs" / "prefix_meta.yaml"


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config(str(CFG_PATH))


# =========================================================================== (1) pure victim selection
def idle_table(kvs: List[int]) -> "OrderedDict[int, int]":
    """sid i -> kvs[i]; iteration order = least recently idle first."""
    return OrderedDict((i, kv) for i, kv in enumerate(kvs))


def test_lru_takes_from_the_front_and_stops_when_covered():
    idle = idle_table([100, 100, 100, 100])
    v, got, ns = select_victims("lru", idle, 150, {}, {})
    assert v == [0, 1] and got == 200 and ns == 0
    v, got, _ = select_victims("lru", idle, 100, {}, {})
    assert v == [0] and got == 100                     # need == one block: exactly one victim
    v, got, _ = select_victims("lru", idle, 101, {}, {})
    assert v == [0, 1]


def test_mru_idle_takes_from_the_back():
    idle = idle_table([10, 20, 30, 40])
    v, got, _ = select_victims("mru_idle", idle, 45, {}, {})
    assert v == [3, 2] and got == 70
    v, got, _ = select_victims("mru_idle", idle, 1, {}, {})
    assert v == [3] and got == 40


def test_need_zero_or_negative_evicts_nothing():
    for mode in EVICTION_MODES:
        assert select_victims(mode, idle_table([5, 5]), 0, {}, {}, np.random.default_rng(0)) == ([], 0, 0)
        assert select_victims(mode, idle_table([5, 5]), -3, {}, {}, np.random.default_rng(0)) == ([], 0, 0)


def test_hard_protected_is_never_a_victim_soft_only_after_unprotected():
    idle = idle_table([100] * 6)
    hard = {0: 100, 5: 100}
    soft = {1: 100, 4: 100}
    rng = np.random.default_rng(1)
    for mode in EVICTION_MODES:
        # 2 unprotected sessions (2, 3): need 200 is served without touching soft
        v, got, ns = select_victims(mode, idle, 200, hard, soft, rng)
        assert sorted(v) == [2, 3] and got == 200 and ns == 0
        # need 300: both unprotected + one soft session
        v, got, ns = select_victims(mode, idle, 300, hard, soft, rng)
        assert set(v) >= {2, 3} and len(v) == 3 and ns == 1 and (set(v) - {2, 3}) <= {1, 4}
        assert not (set(v) & set(hard))
        # more than everything evictable: short, hard still untouched
        v, got, ns = select_victims(mode, idle, 10_000, hard, soft, rng)
        assert sorted(v) == [1, 2, 3, 4] and got == 400 and ns == 2
    # order inside the soft tier follows the rule (lru: oldest soft first; mru_idle: newest soft first)
    assert select_victims("lru", idle, 300, hard, soft, rng)[0] == [2, 3, 1]
    assert select_victims("mru_idle", idle, 300, hard, soft, rng)[0] == [3, 2, 4]


def test_random_is_reproducible_per_generator_seed_and_differs_across_seeds():
    idle = idle_table([100] * 50)
    a = select_victims("random", idle, 1000, {}, {}, np.random.default_rng(7))[0]
    b = select_victims("random", idle, 1000, {}, {}, np.random.default_rng(7))[0]
    c = select_victims("random", idle, 1000, {}, {}, np.random.default_rng(8))[0]
    assert a == b and len(a) == 10 == len(set(a))
    assert a != c


def test_random_is_uniform_over_the_evictable_sessions():
    """need = 1 token with m equal sessions evicts exactly one session; each should be picked with probability 1/m."""
    m, draws = 8, 16000
    idle = idle_table([100] * m)
    rng = np.random.default_rng(12345)
    counts = np.zeros(m)
    for _ in range(draws):
        v, _, _ = select_victims("random", idle, 1, {}, {}, rng)
        counts[v[0]] += 1
    chi2 = float(np.sum((counts - draws / m) ** 2 / (draws / m)))
    assert chi2 < 24.32, (chi2, counts)               # chi^2_{7} 0.999 quantile; the seed is fixed so this is deterministic
    # protected sessions are excluded from the support, the rest stay uniform
    counts = np.zeros(m)
    for _ in range(draws):
        v, _, _ = select_victims("random", idle, 1, {0: 100, 3: 100}, {}, rng)
        counts[v[0]] += 1
    assert counts[0] == 0 and counts[3] == 0
    keep = np.delete(counts, [0, 3])
    chi2 = float(np.sum((keep - draws / 6) ** 2 / (draws / 6)))
    assert chi2 < 20.52, (chi2, keep)                 # chi^2_{5} 0.999 quantile


def test_random_second_victim_is_uniform_among_the_rest():
    """Without replacement: with need = 2 blocks, the unordered pair is uniform over the C(m,2) pairs."""
    m, draws = 5, 20000
    idle = idle_table([100] * m)
    rng = np.random.default_rng(99)
    pairs: Dict[Any, int] = {}
    for _ in range(draws):
        v, _, _ = select_victims("random", idle, 200, {}, {}, rng)
        assert len(v) == 2 and v[0] != v[1]
        key = tuple(sorted(v))
        pairs[key] = pairs.get(key, 0) + 1
    assert len(pairs) == 10
    exp = draws / 10
    chi2 = sum((c - exp) ** 2 / exp for c in pairs.values())
    assert chi2 < 27.88, chi2                         # chi^2_{9} 0.999 quantile


def test_unknown_mode_and_missing_rng_are_errors():
    with pytest.raises(ValueError):
        select_victims("fifo", idle_table([1]), 1, {}, {})
    with pytest.raises(ValueError):
        select_victims("random", idle_table([1]), 1, {}, {}, None)
    with pytest.raises(ValueError):
        make_mechanisms({"eviction": "clock"}, None)
    assert make_mechanisms({}, None).eviction == "lru"
    assert make_mechanisms({"eviction": "random"}, None).eviction == "random"


# =========================================================================== (2) the dedicated random stream
def test_eviction_stream_is_child_4_and_disjoint_from_the_workload_children():
    seed = 123
    ss_children = np.random.SeedSequence(seed).spawn(EVICTION_STREAM + 1)
    assert EVICTION_STREAM == 4
    ev = eviction_rng(seed).random(8)
    assert np.array_equal(ev, np.random.default_rng(ss_children[EVICTION_STREAM]).random(8))
    for i in range(4):                                # workload.build_specs uses children 0..3
        assert not np.array_equal(ev, np.random.default_rng(ss_children[i]).random(8))
    assert not np.array_equal(ev, eviction_rng(seed + 1).random(8))
    assert np.array_equal(eviction_rng(seed).random(5), eviction_rng(seed).random(5))


def test_workload_is_unchanged_by_the_eviction_rule(cfg):
    """Common random numbers: the pre-generated sessions depend on (workload, plan, seed) only."""
    w = WorkloadParams.from_dict(cfg["workload"])
    plan = ArrivalPlan(kind="closed", horizon_s=1000.0, closed_n=10, pool=200)
    s1 = build_specs(w, plan, 5)
    _ = eviction_rng(5).random(100)                   # consuming the eviction stream cannot matter
    s2 = build_specs(w, plan, 5)
    assert np.array_equal(s1.n_turns, s2.n_turns) and np.array_equal(s1.tool_flat, s2.tool_flat)


# =========================================================================== (3) engine integration
BIG_WL = {"initial_context_tokens": 18000, "max_turns": 3, "mean_turns": 3}
BIG_EO = {"kv_memory_tokens": 45_000}


def specs_of(rows) -> SessionSpecs:
    """rows: (arrival, n_turns, tool_time) per session."""
    n = len(rows)
    nt = np.array([r[1] for r in rows], dtype=np.int64)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    flat = np.concatenate([np.full(int(r[1]) - 1, float(r[2])) for r in rows]) if n else np.zeros(0)
    return SessionSpecs(arrival=np.array([r[0] for r in rows], dtype=float), n_turns=nt, tool_off=off, tool_flat=flat)


def mk(cfg, spec: dict, specs: SessionSpecs, *, seed=0, wo=None, eo=None, debug=True, horizon=1000.0,
       plan=None) -> Engine:
    c2 = deep_update(cfg, {"policies": {"p": spec}})
    rs = RunSpec(exp="t", policy="p", seed=seed, horizon_s=horizon, plan=plan or ArrivalPlan(kind="none", horizon_s=horizon),
                 workload_overrides=wo or {}, engine_overrides=eo or {}, debug=debug)
    eng, _, _ = build_engine(c2, rs, specs)
    eng.trace = []
    return eng


def hits_by_turn(eng: Engine) -> Dict[tuple, bool]:
    return {(x[1], x[2]): x[3] for x in eng.trace if x[0] == "A"}


def two_idle_then_big_admission_specs() -> SessionSpecs:
    """A (sid 0, idle first) and B (sid 1, idle later) both finish turn 1 and wait in a 500-s tool call; at t = 100 session D
    (sid 2) needs 18100 tokens, which forces exactly one of the two idle KVs (18100 each) out of M = 45000."""
    return specs_of([(0.0, 2, 500.0), (1.0, 2, 500.0), (100.0, 1, 0.0)])


def run_two_idle(cfg, eviction: str, seed: int = 0):
    eng = mk(cfg, {"kind": "fcfs", "eviction": eviction}, two_idle_then_big_admission_specs(), seed=seed, wo=BIG_WL,
             eo=BIG_EO, horizon=800.0)
    eng.run(800.0)
    h = hits_by_turn(eng)
    return eng, h


def test_lru_evicts_the_oldest_idle_mru_the_newest(cfg):
    eng, h = run_two_idle(cfg, "lru")
    assert eng.n_evictions == 1
    assert h[(0, 2)] is False and h[(1, 2)] is True               # A (idle first) was evicted, B kept
    eng, h = run_two_idle(cfg, "mru_idle")
    assert eng.n_evictions == 1
    assert h[(0, 2)] is True and h[(1, 2)] is False               # B (idle most recently) was evicted, A kept


def test_random_evicts_exactly_one_of_the_two_and_both_outcomes_occur_across_seeds(cfg):
    outcomes = set()
    for seed in range(24):
        eng, h = run_two_idle(cfg, "random", seed)
        assert eng.n_evictions == 1
        assert h[(0, 2)] != h[(1, 2)]                              # exactly one of A, B lost its KV
        outcomes.add(h[(0, 2)])
        eng2, h2 = run_two_idle(cfg, "random", seed)               # reproducible per seed
        assert h2 == h and eng2.last_victims == eng.last_victims
    assert outcomes == {True, False}


def instrument(eng: Engine, log: List[dict]) -> None:
    """Wrap ``eng._evict`` to record, per call, the idle table, the protected sets and the running sessions before it and the
    victims after it. ``eng.trace`` must be a list (finish times are read from it)."""
    orig = eng._evict
    done_time: Dict[int, float] = {}
    seen = [0]

    def wrapped(need: int) -> None:
        for x in eng.trace[seen[0]:]:
            if x[0] == "D":
                done_time[x[1]] = x[3]
        seen[0] = len(eng.trace)
        before = dict(eng.idle)                                    # insertion order = least recently idle first
        hard, soft = dict(eng._hard), dict(eng._soft)
        pins = dict(eng._pin)
        running = ({r.sid for r in eng.prefill} | {r.sid for (_, _, r) in eng._done_heap}
                   | {r.sid for r in eng._pending_done})
        orig(need)
        victims = [s for s in before if s not in eng.idle]
        log.append({"need": need, "before": before, "hard": hard, "soft": soft, "pins": pins, "running": running,
                    "victims": victims, "last": list(eng.last_victims), "done": dict(done_time),
                    "mode": eng._evict_mode, "evicted_tokens": sum(before[s] for s in victims)})

    eng._evict = wrapped                                           # instance attribute shadows the method


def busy_run(cfg, spec: dict, seed: int = 3, horizon: float = 500.0, n: int = 30, M: float = 60_000):
    """Closed population of ``n`` sessions in a small memory (60k tokens), so that eviction is frequent."""
    plan = ArrivalPlan(kind="closed", horizon_s=horizon, closed_n=n, pool=4000)
    specs = build_specs(WorkloadParams.from_dict(cfg["workload"]), plan, seed)
    eng = mk(cfg, spec, specs, seed=seed, eo={"kv_memory_tokens": M}, horizon=horizon, plan=plan)
    assert eng.closed
    log: List[dict] = []
    instrument(eng, log)
    eng.run(horizon)
    return eng, log


@pytest.mark.parametrize("mode", ["lru", "random", "mru_idle"])
def test_victims_are_idle_unprotected_and_minimal_in_a_busy_run(cfg, mode):
    eng, log = busy_run(cfg, {"kind": "fcfs", "eviction": mode})
    assert len(log) > 20, "the scenario must actually exercise eviction"
    assert eng.n_evictions == sum(len(l["victims"]) for l in log)
    for l in log:
        assert set(l["victims"]) <= set(l["before"])               # only resident idle KV
        assert not (set(l["victims"]) & l["running"])              # never a running request's session
        assert not (set(l["victims"]) & set(l["hard"]))            # never hard-protected
        assert l["evicted_tokens"] >= l["need"]                    # frees enough ...
        if mode != "lru":
            assert sorted(l["last"]) == sorted(l["victims"])
            # ... and stops as soon as it has enough: dropping the last-chosen victim would leave too little
            assert l["evicted_tokens"] - l["before"][l["last"][-1]] < l["need"]
    # LRU run: the victims are exactly what the pure rule picks (cross-check of the fast path against select_victims)
    if mode == "lru":
        for l in log:
            v, _, _ = select_victims("lru", l["before"], l["need"], l["hard"], l["soft"])
            assert l["victims"] == v


@pytest.mark.parametrize("mode", ["lru", "random", "mru_idle"])
def test_pinned_kv_is_never_evicted_under_any_rule(cfg, mode):
    eng, log = busy_run(cfg, {"kind": "fcfs", "eviction": mode, "ttl_pin_s": 8.0}, seed=5, horizon=400.0, n=24)
    assert len(log) > 5
    assert any(l["pins"] for l in log), "some eviction must happen while pins exist"
    for l in log:
        assert not (set(l["victims"]) & set(l["pins"]))
        assert not (set(l["victims"]) & set(l["hard"]))
        assert not (set(l["victims"]) & l["running"])


def test_mru_idle_first_victim_has_the_latest_idle_start_and_lru_the_earliest(cfg):
    for mode in ("mru_idle", "lru"):
        eng, log = busy_run(cfg, {"kind": "fcfs", "eviction": mode}, seed=11)
        assert len(log) > 20
        for l in log:
            done = [l["done"][s] for s in l["before"]]             # idle start = finish time of the session's last turn
            order = [l["done"][s] for s in l["victims"]]
            if mode == "mru_idle":
                sel = [l["done"][s] for s in l["last"]]
                assert sel[0] == max(done)
                assert all(a >= b for a, b in zip(sel, sel[1:]))   # then progressively older
            else:
                assert order[0] == min(done)
                assert all(a <= b for a, b in zip(order, order[1:]))


def test_random_eviction_depends_on_its_own_stream_only(cfg):
    """Same workload, same eviction stream -> identical run; same workload, other eviction stream -> a different run;
    the workload specs are untouched either way (CRN across policies)."""
    plan = ArrivalPlan(kind="closed", horizon_s=500.0, closed_n=30, pool=4000)
    specs = build_specs(WorkloadParams.from_dict(cfg["workload"]), plan, 3)

    def run(ev_seed: int):
        c2 = deep_update(cfg, {"policies": {"p": {"kind": "fcfs", "eviction": "random"}}})
        rs = RunSpec(exp="t", policy="p", seed=3, horizon_s=500.0, plan=plan, engine_overrides={"kv_memory_tokens": 60_000})
        eng, _, _ = build_engine(c2, rs, specs)
        eng._evict_rng = eviction_rng(ev_seed)
        eng.trace = []
        eng.run(500.0)
        return eng

    a, b, c = run(3), run(3), run(4)
    assert a.trace == b.trace and a.n_evictions == b.n_evictions
    assert a.trace != c.trace
    assert a.n_evictions > 20


def test_default_and_explicit_lru_are_identical(cfg):
    plan = ArrivalPlan(kind="closed", horizon_s=500.0, closed_n=30, pool=4000)
    rs = RunSpec(exp="t", policy="fcfs", seed=3, horizon_s=500.0, plan=plan, engine_overrides={"kv_memory_tokens": 60_000})
    r0 = simulate(cfg, rs)
    c2 = deep_update(cfg, {"policies": {"fcfs_lru": {"kind": "fcfs", "eviction": "lru"}}})
    r1 = simulate(c2, RunSpec(exp="t", policy="fcfs_lru", seed=3, horizon_s=500.0, plan=plan,
                              engine_overrides={"kv_memory_tokens": 60_000}))
    for k in ("n_hits", "n_admitted", "n_evictions", "evicted_tokens", "n_sessions_done", "n_iterations"):
        assert r0["summary"][k] == r1["summary"][k]
    assert r0["summary"]["eviction"] == "lru"


def test_random_needs_a_generator_when_built_directly(cfg):
    c2 = deep_update(cfg, {"policies": {"p": {"kind": "fcfs", "eviction": "random"}}})
    rs = RunSpec(exp="t", policy="p", seed=0, horizon_s=10.0, plan=ArrivalPlan(kind="none", horizon_s=10.0))
    eng, _, _ = build_engine(c2, rs, specs_of([]))              # build_engine supplies eviction_rng(seed)
    assert eng._evict_rng is not None
    from prefixmeta.engine import EngineParams
    from prefixmeta.metrics import Recorder
    from prefixmeta.mechanisms import Mechanisms
    from prefixmeta.policies import Fcfs
    with pytest.raises(ValueError):
        Engine(EngineParams.from_dict(cfg["engine"]), WorkloadParams.from_dict(cfg["workload"]), specs_of([]), Fcfs(),
               Recorder(1000.0, 100.0), mech=Mechanisms(eviction="random"))


def test_recorder_counts_evictions_per_window(cfg):
    plan = ArrivalPlan(kind="closed", horizon_s=3000.0, closed_n=30, pool=4000)
    rs = RunSpec(exp="t", policy="fcfs", seed=3, horizon_s=3000.0, plan=plan, engine_overrides={"kv_memory_tokens": 60_000})
    res = simulate(cfg, rs)
    ev = sum(w["evictions"] for w in res["windows"])
    assert ev == res["summary"]["n_evictions"] > 0               # horizon is a multiple of the window; events are < horizon
    assert all(w["evictions_per_s"] == pytest.approx(w["evictions"] / 1000.0) for w in res["windows"])
