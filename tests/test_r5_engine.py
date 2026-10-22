"""Round-5 engine tests: the allocation modes ``ondemand_preempt`` (vLLM-like) and ``ratio_reserve`` (SGLang-like).

Layers
 (1) pure rules (admission predicates, retraction ratio, the survivor-prefix equivalence of vLLM's pop-from-the-end loop);
 (2) hand-built scenarios with a known right answer (admission that FULL_RESERVE would refuse, newest-first preemption, whole-session
     loss vs. surviving partial prefill, token conservation);
 (3) the default mode is bit-identical to the round-4 engine (golden fixture generated from the unmodified engine + the round-4
     result file), and the two new modes with M = inf equal full_reserve with M = inf;
 (4) invariants on congested runs: memory never exceeds M, preemption / retraction accounting conserves sessions and tokens, every
     turn emits exactly d tokens, batched pure-decode runs equal iteration-by-iteration runs;
 (5) a deliberately naive iteration-by-iteration reference simulator (re-implemented from the prose of the pre-registration, with the
     LITERAL vLLM running loop) that must reproduce the engine's admission / completion / preemption / re-admission trace.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import pytest

from prefixmeta.engine import (ALLOC_MODES, Engine, EngineParams, ondemand_admit_ok, ratio_admit_ok, retraction_ratio)
from prefixmeta.mech_runner import load_mech_config
from prefixmeta.r4_runner import closed_spec, point_metrics
from prefixmeta.sim import RunSpec, build_engine, deep_update, simulate
from prefixmeta.workload import ArrivalPlan, SessionSpecs, WorkloadParams, build_specs

REPO = Path(__file__).resolve().parent.parent
CFG5 = REPO / "configs" / "prefix_meta_r5.yaml"
CFG4 = REPO / "configs" / "prefix_meta_r4.yaml"
GOLDEN = REPO / "tests" / "data" / "r4_golden.json"
R4_CURVE_RUNS = REPO / "results" / "prefix_meta_r4_curve" / "20261021-050856" / "curve_runs.csv"
INF = math.inf
DYN = ("ondemand_preempt", "ratio_reserve")
LAM_MISS = 0.047418947368421054


@pytest.fixture(scope="module")
def cfg5() -> dict:
    return load_mech_config(str(CFG5), REPO)


@pytest.fixture(scope="module")
def cfg4() -> dict:
    return load_mech_config(str(CFG4), REPO)


# ============================================================================ helpers
def specs_of(rows) -> SessionSpecs:
    """rows: (arrival, n_turns, tool_time) per session."""
    n = len(rows)
    nt = np.array([r[1] for r in rows], dtype=np.int64)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    flat = np.concatenate([np.full(int(r[1]) - 1, float(r[2])) for r in rows]) if n else np.zeros(0)
    return SessionSpecs(arrival=np.array([r[0] for r in rows], dtype=float), n_turns=nt, tool_off=off, tool_flat=flat)


SMALL_WL = {"initial_context_tokens": 1000, "new_prompt_tokens": 100, "decode_tokens": 10, "max_turns": 3, "mean_turns": 3}


def mk(cfg, specs, *, policy="fcfs_lru", wo=None, eo=None, debug=True, horizon=50.0, cap=None, cls=Engine) -> Engine:
    rs = RunSpec(exp="t", policy=policy, seed=0, horizon_s=horizon, plan=ArrivalPlan(kind="none", horizon_s=horizon),
                 workload_overrides=wo or {}, engine_overrides=eo or {}, debug=debug, session_cap_override=cap)
    eng, _, _ = build_engine(cfg, rs, specs)
    if cls is not Engine:
        eng.__class__ = cls
    eng.trace = []
    return eng


def trace_of(eng: Engine, kinds="ADPR"):
    return [x for x in eng.trace if x[0] in kinds]


# ============================================================================ (1) pure rules
def test_alloc_mode_constants_and_params_validation(cfg5):
    assert ALLOC_MODES == ("full_reserve", "ondemand_preempt", "ratio_reserve")
    assert EngineParams.from_dict(cfg5["engine"]).alloc_mode == "full_reserve"          # the default keeps rounds 1-4
    with pytest.raises(ValueError):
        EngineParams.from_dict({**cfg5["engine"], "alloc_mode": "nope"})


def test_ondemand_admit_predicate_boundaries():
    assert ondemand_admit_ok(1000, 1000, 0, 2000)            # exactly full is allowed (<=)
    assert not ondemand_admit_ok(1001, 1000, 0, 2000)
    assert ondemand_admit_ok(1000, 900, 100, 2000)           # watermark counts
    assert not ondemand_admit_ok(1000, 901, 100, 2000)
    assert ondemand_admit_ok(10 ** 12, 10 ** 12, 0, INF)


def test_ratio_admit_predicate_is_strict_and_has_the_idle_guard():
    # held + commit + offset + total + dec < M is STRICT
    assert ratio_admit_ok(500, 100, 50, 300, 49, 1000, n_running=3)           # 999 < 1000
    assert not ratio_admit_ok(500, 100, 50, 300, 50, 1000, n_running=3)       # 1000 !< 1000
    assert not ratio_admit_ok(500, 100, 50, 300, 51, 1000, n_running=3)
    # nothing running: a request that fits alone is admitted even if strictness would refuse it (M == prompt + d)
    assert ratio_admit_ok(0, 0, 0.0, 990, 10, 1000, n_running=0)
    assert not ratio_admit_ok(0, 0, 0.0, 990, 11, 1000, n_running=0)
    assert ratio_admit_ok(10 ** 9, 10 ** 9, 0.0, 10 ** 9, 10, INF, n_running=5)


def test_retraction_ratio_formula():
    # (sum outputs + 20 n) / (sum max_new + 1), capped at 1
    assert retraction_ratio(0, 1, 100, 20) == pytest.approx(20 / 101)
    assert retraction_ratio(300, 4, 100, 20) == pytest.approx((300 + 80) / 401)
    assert retraction_ratio(400, 4, 100, 20) == 1.0                              # (400+80)/401 > 1 -> capped
    assert retraction_ratio(0, 5, 100, 20) == pytest.approx(100 / 501)


def _literal_vllm_survivors(h: List[int], need: List[int], M: float) -> int:
    """vLLM's running loop, literally: requests in running order; if allocating request i fails, pop the LAST running request (free its
    blocks) and retry; if the popped request is i itself, stop. Returns the number of surviving requests."""
    order = list(range(len(h)))
    used = sum(h)
    i = 0
    while i < len(order):
        r = order[i]
        while used + need[r] > M:
            v = order.pop()
            used -= h[v]
            if v == r:
                break
        else:
            used += need[r]
            i += 1
            continue
        break
    return len(order)


def _prefix_rule_survivors(h: List[int], need: List[int], M: float) -> int:
    """The engine's rule: the largest admission-ordered prefix k with sum_{j<k}(h_j + need_j) <= M."""
    tot = 0
    k = 0
    for hj, nj in zip(h, need):
        if tot + hj + nj > M:
            break
        tot += hj + nj
        k += 1
    return k


def test_vllm_pop_from_the_end_equals_longest_fitting_prefix():
    rng = np.random.default_rng(1)
    for _ in range(3000):
        m = int(rng.integers(1, 9))
        h = [int(x) for x in rng.integers(0, 50, m)]
        need = [int(x) for x in rng.integers(0, 12, m)]
        M = int(rng.integers(max(h[0] + need[0], 1), sum(h) + sum(need) + 5))      # the first request alone always fits
        assert _literal_vllm_survivors(h, need, M) == _prefix_rule_survivors(h, need, M), (h, need, M)


# ============================================================================ (2) hand-built scenarios
@pytest.mark.parametrize("rule", ["whole", "tail"])
def test_ondemand_admits_what_full_reserve_refuses_then_preempts_the_newest(cfg5, rule):
    """M = 2002, two single-turn sessions (prompt 1000, d = 10) at t = 0. FULL_RESERVE needs 1010 + 1010 > M, so the second waits for
    the first to finish. ONDEMAND needs only the prompt: held 1001 (first prompt + sampled token) + 1000 <= 2002, both are admitted at
    t = 0 and fill M exactly; the next decode step needs 2 more tokens, so the NEWEST request (session 1) is preempted and its 1001 tokens
    go to the idle pool. The survivor needs 1 more token per decode step (9 steps). Stage-1 rule ``whole``: the first token of growth
    evicts the victim's session entirely, so it is re-admitted as a full miss that recomputes prompt + the token it had already
    generated. Amendment-2 rule ``tail``: each step trims one token off the victim's tail, so 1001 - 9 = 992 tokens survive and the
    re-admission recomputes only the 9 missing ones."""
    sp = specs_of([(0.0, 1, 0.0), (0.0, 1, 0.0)])
    full = mk(cfg5, sp, wo=SMALL_WL, eo={"kv_memory_tokens": 2002, "alloc_mode": "full_reserve"})
    full.run(50.0)
    a = trace_of(full, "A")
    assert a[0][4] == 0.0 and a[1][4] > 0.0                       # second admission only after the first one finished
    od = mk(cfg5, sp, wo=SMALL_WL, eo={"kv_memory_tokens": 2002, "alloc_mode": "ondemand_preempt", "victim_kv_eviction": rule})
    od.run(50.0)
    tr = od.trace
    assert [x for x in tr if x[0] == "A"] == [("A", 0, 1, False, 0.0), ("A", 1, 1, False, 0.0)]
    p = [x for x in tr if x[0] == "P"]
    assert len(p) == 1 and p[0][:4] == ("P", 1, 1, 1001)                       # the newest, holding 1001 tokens
    d0 = [x for x in tr if x[0] == "D" and x[1] == 0][0]
    r = [x for x in tr if x[0] == "R"]
    hit, new = (0, 1001) if rule == "whole" else (992, 9)
    assert len(r) == 1 and r[0][:5] == ("R", 1, 1, hit, new)
    assert r[0][5] == pytest.approx(d0[3], abs=1e-12)                          # re-admitted the moment the survivor finished
    s = od.stats()
    assert s["n_preempt"] == 1 and s["n_readmit"] == 1 and s["n_readmit_with_kv"] == (0 if rule == "whole" else 1)
    assert s["recompute_tokens"] == new and s["lost_prefill_tokens"] == 0 and s["recompute_processed_tokens"] == new
    assert s["admitted_prefill_tokens"] == s["processed_prefill_tokens"] == 1000 + 1000 + new
    assert s["n_turns_done"] == 2 and od.held == 0 and od.idle_sum == 0
    assert s["n_admitted"] == 2 and s["n_hits"] == 0                            # re-admissions are not in the hit statistics
    assert s["max_preempt_per_turn"] == 1 and s["n_turns_preempted"] == 1 and s["n_turns_preempted_ge3"] == 0
    # evicted tokens are additive (batching-independent): the whole victim vs the 9 tokens the survivor grew by
    assert s["evicted_tokens"] == (1001 if rule == "whole" else 9) and s["n_evictions"] == (1 if rule == "whole" else 0)
    assert (s["n_partial_evictions"] == 0) == (rule == "whole")
    # boundary of the admission test: the second prompt needs 1000 tokens + 1 sampled token next to the first request's 1001
    tight = mk(cfg5, sp, wo=SMALL_WL, eo={"kv_memory_tokens": 2001, "alloc_mode": "ondemand_preempt", "victim_kv_eviction": rule})
    tight.run(50.0)
    a2 = trace_of(tight, "A")
    assert a2[0][4] == 0.0 and a2[1][4] > 0.0 and tight.stats()["n_preempt"] == 0


def test_preempted_prefill_keeps_its_partial_kv_when_memory_is_not_needed(cfg5):
    """Chunk budget 400, M = 1600, prompts 1000: the newest request is mid-prefill (200 of 1000 tokens processed) when its next 400-token
    chunk would overflow. It is preempted, its 200 cached tokens stay in the idle pool (the survivor only needs 1 token), and its
    re-admission hits them and recomputes only the 800 remaining tokens."""
    sp = specs_of([(0.0, 1, 0.0), (0.0, 1, 0.0)])
    eo = {"kv_memory_tokens": 1600, "alloc_mode": "ondemand_preempt", "prefill_chunk_budget": 400,
          "admission_limited_by_prefill_budget": False}
    od = mk(cfg5, sp, wo=SMALL_WL, eo=eo)
    od.run(50.0)
    p = [x for x in od.trace if x[0] == "P"]
    r = [x for x in od.trace if x[0] == "R"]
    assert len(p) == 1 and p[0][:4] == ("P", 1, 1, 200)
    assert len(r) == 1 and r[0][:5] == ("R", 1, 1, 200, 800)
    s = od.stats()
    assert s["lost_prefill_tokens"] == 800 and s["recompute_tokens"] == 800 and s["n_readmit_with_kv"] == 1
    assert s["processed_prefill_tokens"] == 1000 + 200 + 800 and s["admitted_prefill_tokens"] == 1000 + 1000 + 800
    assert s["processed_prefill_tokens"] + s["lost_prefill_tokens"] == s["admitted_prefill_tokens"]
    assert s["n_turns_done"] == 2


def test_cache_disabled_victim_loses_everything(cfg5):
    sp = specs_of([(0.0, 1, 0.0), (0.0, 1, 0.0)])
    eo = {"kv_memory_tokens": 1600, "alloc_mode": "ondemand_preempt", "prefill_chunk_budget": 400,
          "admission_limited_by_prefill_budget": False, "cache_enabled": False}
    od = mk(cfg5, sp, wo=SMALL_WL, eo=eo)
    od.run(50.0)
    r = [x for x in od.trace if x[0] == "R"]
    assert len(r) == 1 and r[0][3] == 0 and r[0][4] == 1000                    # nothing cached: the whole prompt again
    assert od.stats()["n_turns_done"] == 2 and od.idle_sum == 0


def test_ratio_reserve_admission_is_strict_and_charges_prompt_plus_decode_budget(cfg5):
    """Three single-turn sessions (prompt 1000, d = 10) at t = 0. The SGLang-like test charges, per earlier admission of the pass,
    extend + max_new = 1010 (unscaled), so the third request sees 0 + 2020 + 0 + 1000 + 10 = 3030: admitted at t = 0 iff M > 3030
    (strict), otherwise it waits for the others."""
    sp = specs_of([(0.0, 1, 0.0)] * 3)
    for M, third_at_zero in ((3031, True), (3030, False)):
        eng = mk(cfg5, sp, wo=SMALL_WL, eo={"kv_memory_tokens": M, "alloc_mode": "ratio_reserve"})
        eng.run(50.0)
        a = trace_of(eng, "A")
        assert len(a) == 3 and a[0][4] == 0.0 and a[1][4] == 0.0
        assert (a[2][4] == 0.0) == third_at_zero, (M, a)
        assert eng.stats()["n_turns_done"] == 3


class _RatioProbe(Engine):
    """Records every retraction: the victim chosen, the brute-force minimum of the registered key computed from the contexts, and the
    ratio set afterwards versus the registered formula."""
    probes: list

    def _pick_retract_victim(self):
        G = self.G
        live = [r for (_, _, r) in self._done_heap if not r.gone]
        v = super()._pick_retract_victim()
        # generated tokens recomputed from the context (independent of the gen / g_enter bookkeeping)
        key = lambda r: (r.offs + G - r.prompt, -r.prompt, -r.rid)                      # noqa: E731
        best = min(live, key=key)
        self.probes.append(("victim", v.rid, best.rid, key(v), key(best)))
        return v

    def _running_step_ratio(self):
        out = super()._running_step_ratio()
        if out:
            G = self.G
            live = [r for (_, _, r) in self._done_heap if not r.gone]
            sum_gen = sum(r.offs + G - r.prompt for r in live)
            n = len(live)
            expect = min(1.0, (sum_gen + self.p.retract_decode_steps * n) / (self.wl.decode_tokens * n + 1))
            self.probes.append(("ratio", self.new_token_ratio, expect, n))
        return out


def test_ratio_retraction_victim_order_and_ratio_formula_on_a_congested_run(cfg5):
    wl = WorkloadParams.from_dict(cfg5["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=300.0, rate=0.4, initial_cold=20, burst_n=30, burst_t0=60.0, burst_width_s=5.0)
    specs = build_specs(wl, plan, 7)
    eng = mk(cfg5, specs, eo={"kv_memory_tokens": 60_000, "alloc_mode": "ratio_reserve"}, horizon=500.0, cls=_RatioProbe)
    eng.probes = []
    eng.run(500.0)
    vic = [p for p in eng.probes if p[0] == "victim"]
    rat = [p for p in eng.probes if p[0] == "ratio"]
    assert len(vic) >= 5, "scenario must retract several times"
    for _, rid, best_rid, k, kb in vic:
        assert rid == best_rid and k == kb
    assert len(rat) >= 3
    for _, got, expect, n in rat:
        assert got == pytest.approx(expect, rel=1e-12) and 0.0 < got <= 1.0 and n >= 1


def test_ratio_dynamics_init_min_decay_and_reset(cfg5):
    eng = mk(cfg5, specs_of([(0.0, 1, 0.0)]), wo=SMALL_WL, eo={"kv_memory_tokens": 1e6, "alloc_mode": "ratio_reserve"})
    assert eng.new_token_ratio == pytest.approx(0.7) and eng._ratio_min == pytest.approx(0.098)
    assert eng._ratio_decay == pytest.approx((0.7 - 0.098) / 600)
    eng._decay_ratio(1)
    assert eng.new_token_ratio == pytest.approx(0.7 - (0.7 - 0.098) / 600)
    eng._decay_ratio(599)                                                      # 600 decays in total reach the minimum
    assert eng.new_token_ratio == pytest.approx(0.098)
    eng._decay_ratio(10_000)
    assert eng.new_token_ratio == pytest.approx(0.098)                         # clamped
    eng._retracted_turn = True
    eng.new_token_ratio = 0.5
    eng._decay_ratio(5)
    assert eng.new_token_ratio == 0.5                                          # no decay in a retraction turn
    # conservativeness scales the initial ratio and is capped at 1
    e2 = mk(cfg5, specs_of([(0.0, 1, 0.0)]), wo=SMALL_WL,
            eo={"kv_memory_tokens": 1e6, "alloc_mode": "ratio_reserve", "sched_conservativeness": 2.0})
    assert e2._ratio_init == 1.0
    # an idle gap resets the ratio to its initial value
    e3 = mk(cfg5, specs_of([(0.0, 1, 0.0), (500.0, 1, 0.0)]), wo=SMALL_WL, horizon=2000.0,
            eo={"kv_memory_tokens": 1e6, "alloc_mode": "ratio_reserve"})
    seen = []
    orig = e3._iterate_with_prefill

    def spy(chunks=None):
        seen.append(e3.new_token_ratio)
        orig(chunks)
    e3._iterate_with_prefill = spy
    e3.run(2000.0)
    assert seen[0] == pytest.approx(0.7) and seen[-1] == pytest.approx(0.7)    # the second session starts from the reset ratio


def test_unsupported_configurations_are_refused(cfg5):
    sp = specs_of([(0.0, 1, 0.0)])
    c2 = deep_update(cfg5, {"policies": {"ttl": {"kind": "fcfs", "ttl_pin_s": 5.0}, "ag": {"kind": "aging_lpm", "w_max_s": 5.0}}})
    for pol in ("ttl", "ag"):
        with pytest.raises(ValueError):
            mk(c2, sp, policy=pol, eo={"alloc_mode": "ondemand_preempt"})
    with pytest.raises(ValueError):
        mk(cfg5, sp, eo={"alloc_mode": "ratio_reserve", "kv_memory_tokens": INF}, wo={"decode_tokens": 5000})


# ============================================================================ (3) full_reserve is untouched; M = inf equivalences
def _golden_specs(cfg4: dict) -> Dict[str, RunSpec]:
    cv = cfg4["curve"]
    LAM = LAM_MISS
    cv2 = dict(cv)
    cv2["horizon_s"] = 20000.0
    H = 20000.0
    return {
        "closed_fcfs_lru_n28_s2000_H35000": closed_spec("fcfs_lru", 28, 1.0, 2000, cv, cfg4["engine"]),
        "closed_lpm_lru_n24_s2001_H35000": closed_spec("lpm_lru", 24, 1.0, 2001, cv, cfg4["engine"]),
        "closed_fcfs_random_n32_s2000_H20000": closed_spec("fcfs_random", 32, 1.0, 2000, cv2, cfg4["engine"]),
        "burst50_fcfs_lru_s2100_H20000": RunSpec(
            exp="g", policy="fcfs_lru", seed=2100, horizon_s=H, variant="g",
            plan=ArrivalPlan(kind="constant", horizon_s=H, rate=2 * LAM, burst_n=50, burst_t0=5000.0, burst_width_s=60.0),
            meta={"lam": 2 * LAM}),
        "cap28_cold300_fcfs_lru_s2200_H20000": RunSpec(
            exp="g", policy="fcfs_lru", seed=2200, horizon_s=H, variant="g", session_cap_override=28,
            plan=ArrivalPlan(kind="constant", horizon_s=H, rate=2 * LAM, initial_cold=300), meta={"lam": 2 * LAM}),
        "cap20_cold300_lpm_lru_s2201_H20000": RunSpec(
            exp="g", policy="lpm_lru", seed=2201, horizon_s=H, variant="g", session_cap_override=20,
            plan=ArrivalPlan(kind="constant", horizon_s=H, rate=2 * LAM, initial_cold=300), meta={"lam": 2 * LAM}),
    }


def _digest(res) -> tuple:
    w = json.dumps(res["windows"], sort_keys=True, default=float)
    q = json.dumps([list(map(float, x)) for x in res["qtrace"]])
    return hashlib.sha256(w.encode()).hexdigest(), hashlib.sha256(q.encode()).hexdigest()


GOLDEN_CELLS = sorted(json.loads(GOLDEN.read_text())["cells"]) if GOLDEN.exists() else []


@pytest.mark.parametrize("cell", GOLDEN_CELLS)
def test_full_reserve_is_bit_identical_to_the_round4_engine(cfg4, cell):
    """tests/data/r4_golden.json was generated from the UNMODIFIED round-4 engine (commit 8ab986f): closed FCFS-LRU / LPM-LRU /
    FCFS-RANDOM cells, a burst cell and two capped cold-start cells. The default alloc_mode must reproduce summary, every window and the
    queue trace bit for bit."""
    gold = json.loads(GOLDEN.read_text())["cells"][cell]
    rs = _golden_specs(cfg4)[cell]
    res = simulate(cfg4, rs)
    summary = {k: v for k, v in res["summary"].items() if not k.startswith("wall")}
    assert json.dumps(summary, sort_keys=True, default=float) == json.dumps(gold["summary"], sort_keys=True, default=float)
    wd, qd = _digest(res)
    assert wd == gold["windows_sha256"] and qd == gold["qtrace_sha256"]
    assert len(res["windows"]) == gold["n_windows"]
    assert "preemptions" not in res["windows"][0] and "alloc_mode" not in res["summary"]      # the output schema is unchanged


def test_full_reserve_reproduces_the_round4_result_file(cfg4):
    """Sample cell of the committed-on-disk round-4 E-curve run (results/prefix_meta_r4_curve/20261021-050856): FCFS-LRU, n = 28, seed
    2000, measured over [5000, 35000): 3373 sessions, mu = 3373 / 30000, hit rate 0.7157, 0.3605 evictions / s."""
    rs = closed_spec("fcfs_lru", 28, 1.0, 2000, cfg4["curve"], cfg4["engine"])
    res = simulate(cfg4, rs)
    pm = point_metrics(res["windows"], 5000.0, 35000.0, 1000.0)
    assert pm["n_sessions"] == 3373 and pm["mu"] == 3373 / 30000.0
    if R4_CURVE_RUNS.exists():
        row = pd.read_csv(R4_CURVE_RUNS).query("policy == 'fcfs_lru' and k == 1.0 and n_nominal == 28 and seed == 2000")
        assert len(row) == 1
        for key in ("n_sessions", "mu", "hit_rate", "evictions_per_s", "gpu_busy", "reserved_tokens", "idle_tokens"):
            assert float(row[key].iloc[0]) == pytest.approx(pm[key], rel=1e-12), key       # CSV round trip: last-ulp tolerance


def _summary_without_run_specific(s: dict) -> dict:
    skip = {"wall_s", "wall_s_per_10k_sim_s", "max_resident_tokens", "alloc_mode", "max_held_tokens_debug"}
    return {k: v for k, v in s.items() if k not in skip and not k.startswith("wall")
            and k not in ("n_preempt", "n_readmit", "n_readmit_with_kv", "recompute_tokens", "lost_prefill_tokens",
                          "admitted_prefill_tokens", "processed_prefill_tokens", "n_fallback_retract", "ratio_final",
                          "ratio_min_seen", "recompute_processed_tokens", "max_preempt_per_turn", "n_turns_preempted",
                          "n_turns_preempted_ge3", "n_partial_evictions")}


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("policy", ["fcfs_lru", "lpm_lru"])
def test_alloc_mode_with_infinite_memory_equals_full_reserve_with_infinite_memory(cfg5, mode, policy):
    wl = WorkloadParams.from_dict(cfg5["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=800.0, rate=0.25, initial_cold=15, burst_n=25, burst_t0=100.0, burst_width_s=10.0)
    specs = build_specs(wl, plan, 31)
    outs = {}
    for m in ("full_reserve", mode):
        rs = RunSpec(exp="t", policy=policy, seed=31, horizon_s=1500.0, plan=plan, variant="x",
                     engine_overrides={"kv_memory_tokens": INF, "alloc_mode": m}, debug=True)
        eng, rec, _ = build_engine(cfg5, rs, specs)
        eng.trace = []
        eng.run(1500.0)
        wins = rec.finalize(eng.end_time)
        outs[m] = (_summary_without_run_specific(eng.stats()), [{k: v for k, v in w.items() if k not in ("preemptions", "recompute_tokens", "reserved_mean", "recompute_processed",
                                                                                 "lost_prefill", "preempt_max_turn")}
                                                                 for w in wins], rec.queue_trace(), [x for x in eng.trace if x[0] in "AD"])
    a, b = outs["full_reserve"], outs[mode]
    dump = lambda o: json.dumps(o, sort_keys=True, default=float)                           # noqa: E731  (NaN-safe comparison)
    assert dump(a[0]) == dump(b[0])
    assert dump(a[1]) == dump(b[1]) and dump(a[2]) == dump(b[2])
    assert a[3] == b[3] and len(a[3]) > 200
    # reserved_mean is the only memory column that legitimately differs (full end-of-turn reservations vs KV actually held)
    assert a[0]["n_evictions"] == 0 and a[0]["n_hits"] > 0


# ============================================================================ (4) invariants on congested runs
class _CheckedEngine(Engine):
    """At every completion: the turn emitted exactly d tokens and its context is the end-of-turn context (token conservation of the
    preempt / recompute / resume path), and the occupancy is within M (independent of Engine.check_invariants, which recomputes held)."""

    def _finish_request(self, req, t):
        assert req.gen + (self.G - req.g_enter) == self.wl.decode_tokens, "a turn must emit exactly d tokens"
        assert req.offs + self.G == req.end, "context at completion != end-of-turn context"
        super()._finish_request(req, t)
        assert self.held + self.idle_sum <= self.M + 1e-9


def _congested(cfg, mode, M, seed=11, horizon=900.0, eo=None, policy="fcfs_lru", cap=None, cls=_CheckedEngine, rate=0.5, cold=20, burst=40):
    wl = WorkloadParams.from_dict(cfg["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=rate, initial_cold=cold, burst_n=burst, burst_t0=100.0, burst_width_s=10.0)
    specs = build_specs(wl, plan, seed)
    eng = mk(cfg, specs, policy=policy, eo={"kv_memory_tokens": M, "alloc_mode": mode, **(eo or {})}, horizon=horizon, cap=cap, cls=cls)
    eng.run(horizon)
    return eng, specs


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("M,policy,eo", [
    (70_000, "fcfs_lru", {}), (70_000, "lpm_lru", {}), (150_000, "fcfs_lru", {}),
    (70_000, "fcfs_lru", {"prefill_chunk_budget": 2048}),
    (70_000, "fcfs_lru", {"cache_enabled": False}), (45_000, "fcfs_lru", {"admission_limited_by_prefill_budget": False}),
    (70_000, "fcfs_lru", {"free_kv_on_session_end": False}),
])
def test_memory_never_exceeds_M_and_sessions_and_tokens_are_conserved(cfg5, mode, M, policy, eo):
    eng, specs = _congested(cfg5, mode, M, policy=policy, eo=eo)          # debug=True: check_invariants every engine turn
    s = eng.stats()
    assert s["max_resident_tokens"] <= M
    assert s["n_turns_done"] > 100
    assert s["n_preempt"] > 0 and s["n_readmit"] > 0, "the scenario must exercise preemption / retraction"
    # conservation of sessions: every arrived session is done or still in the system
    assert s["n_arrived"] == s["n_sessions_done"] + s["n_in_flight"]
    # preemptions are matched by re-admissions except for requests still waiting at the horizon
    still_waiting = sum(1 for r in eng._waiting.values() if r.resumed)
    assert s["n_preempt"] == s["n_readmit"] + still_waiting
    # prefill tokens: admitted = processed + lost (preempted mid-prefill) + still to process
    assert s["admitted_prefill_tokens"] == s["processed_prefill_tokens"] + s["lost_prefill_tokens"] + sum(r.rem for r in eng.prefill)
    assert s["recompute_tokens"] <= s["admitted_prefill_tokens"]
    # first admissions only are counted in the hit statistics
    assert s["n_admitted"] == sum(1 for x in eng.trace if x[0] == "A")
    assert s["n_readmit"] == sum(1 for x in eng.trace if x[0] == "R") and s["n_preempt"] == sum(1 for x in eng.trace if x[0] == "P")
    assert s["n_fallback_retract"] == 0


@pytest.mark.parametrize("mode", DYN)
def test_every_session_finishes_and_everything_is_released_when_the_system_drains(cfg5, mode):
    wl = WorkloadParams.from_dict(cfg5["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=60.0, rate=0.5, initial_cold=15, burst_n=20, burst_t0=10.0, burst_width_s=5.0)
    specs = build_specs(wl, plan, 5)
    eng = mk(cfg5, specs, eo={"kv_memory_tokens": 50_000, "alloc_mode": mode}, horizon=20_000.0, cls=_CheckedEngine)
    eng.run(20_000.0)
    s = eng.stats()
    assert s["n_sessions_done"] == len(specs) == s["n_arrived"]
    assert s["n_turns_done"] == int(specs.n_turns.sum())
    assert s["n_preempt"] > 0 and s["n_preempt"] == s["n_readmit"]
    assert eng.held == 0 and eng.idle_sum == 0 and not eng.idle and not eng.prefill and eng.n_D == 0 and not eng._run_order
    assert s["admitted_prefill_tokens"] == s["processed_prefill_tokens"] + s["lost_prefill_tokens"]


@pytest.mark.parametrize("mode", DYN)
def test_a_session_cap_works_in_the_new_modes(cfg5, mode):
    eng, _ = _congested(cfg5, mode, 70_000, cap=12)
    assert eng.stats()["max_in_system"] <= 12 and eng.stats()["entries_over_cap"] == 0


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("policy", ["fcfs_lru", "lpm_lru"])
def test_batched_decode_runs_equal_iteration_by_iteration_runs(cfg5, mode, policy):
    trs = []
    for batch in (True, False):
        eng, _ = _congested(cfg5, mode, 70_000, policy=policy, eo={"batch_decode_iterations": batch}, horizon=700.0, cls=Engine)
        trs.append((eng.trace, eng.stats()))
    (ta, sa), (tb, sb) = trs
    assert len(ta) == len(tb) > 200
    for x, y in zip(ta, tb):
        assert x[:-1] == y[:-1], (x, y)
        assert x[-1] == pytest.approx(y[-1], rel=1e-9, abs=1e-9)
    for k in ("n_preempt", "n_readmit", "recompute_tokens", "n_evictions", "n_turns_done", "n_iterations", "n_hits"):
        assert sa[k] == sb[k], k
    assert sa["n_steps"] < sb["n_steps"]


@pytest.mark.parametrize("mode", DYN)
def test_results_are_deterministic_and_the_closed_mode_keeps_n_sessions(cfg5, mode):
    cv = dict(cfg5["curve"])
    cv["horizon_s"] = 3000.0
    outs = []
    for _ in range(2):
        rs = closed_spec("fcfs_lru", 40, 1.0, 7300, cv, cfg5["engine"])
        rs.engine_overrides = {"alloc_mode": mode}
        rs.debug = True
        res = simulate(cfg5, rs)
        outs.append((json.dumps({k: v for k, v in res["summary"].items() if not k.startswith("wall")}, sort_keys=True, default=float),
                     _digest(res)))
    assert outs[0] == outs[1]
    s = json.loads(outs[0][0])
    assert s["n_in_flight"] == 40 and s["n_arrived"] == 40 + s["n_sessions_done"]


# ============================================================================ (5) naive reference simulator
def reference_dyn_trace(cfg: dict, specs: SessionSpecs, kind: str, horizon: float, *, M: float, mode: str, cache: bool = True,
                        limited: bool = True, chunk_budget: Optional[int] = None, max_seqs: Optional[int] = None,
                        watermark: float = 0.0, tail: bool = True, first_chunk: bool = False, sep: Optional[dict] = None):
    """``sep`` (ratio_reserve only; batching=separate_prefill_priority): dict with pf_fixed, pf_tok, dc_fixed, dc_floor, dc_seq. The turn is then
    admission pass -> chunk plan -> (chunks: prefill-only iteration, decode neither allocates nor advances) else (decode-OOM check / retraction,
    one token per decode request, decode-only iteration, ratio decay) -- SGLang get_next_batch_to_run / update_running_batch.

    Deliberately naive iteration-by-iteration re-implementation of both allocation modes from the prose of the pre-registration:
    plain lists, everything recomputed from per-request records on every turn, the LITERAL vLLM running loop, the SGLang sort key,
    no global counters / batching / lazy queues. A pass runs when the state changed (arrival, tool return, completion, prefill iteration,
    preemption), never in a turn with a preemption / retraction. ``tail`` = amendment 2 (the entry of a preempted request is trimmed
    tail-first by the deficit; every other idle session is evicted whole), ``first_chunk`` = the first-chunk admission sensitivity.
    Returns the trace in the Engine.trace format (A, D, P, R)."""
    e, w = cfg["engine"], cfg["workload"]
    CB = chunk_budget if chunk_budget is not None else e["prefill_chunk_budget"]
    MS = max_seqs if max_seqs is not None else e["max_running_seqs"]
    L0, DELTA, D = w["initial_context_tokens"], w["new_prompt_tokens"], w["decode_tokens"]
    prompt_len = lambda turn: L0 + (turn - 1) * (DELTA + D)          # noqa: E731
    arr = specs.arrival.tolist()
    n = len(arr)
    nt = specs.n_turns.tolist()
    tools = [specs.tools_of(i).tolist() for i in range(n)]
    turn = [1] * n
    nxt = 0
    t = 0.0
    waiting, idle, running, tool_ev, pending_done, trace = [], [], [], [], [], []   # idle: [sid, kv] LRU first
    rid_ctr, seq_ctr = 0, 0
    dirty = False
    ratio_init = min(e.get("init_new_token_ratio", 0.7) * e.get("sched_conservativeness", 1.0), 1.0)
    ratio_min = ratio_init * e.get("min_new_token_ratio_factor", 0.14)
    ratio_decay = (ratio_init - ratio_min) / e.get("new_token_ratio_decay_steps", 600)
    R = e.get("retract_decode_steps", 20)
    headroom = e.get("retract_evict_headroom", True)
    ratio = ratio_init

    def new_req(sid, tq, ready, prompt, gen=0, resumed=False, turn_=None):
        nonlocal rid_ctr
        d = dict(rid=rid_ctr, sid=sid, turn=turn[sid] if turn_ is None else turn_, q=tq, ready=ready, prompt=prompt, gen=gen,
                 resumed=resumed)
        rid_ctr += 1
        return d

    def enqueue(sid, tq, ready):
        nonlocal dirty
        waiting.append(new_req(sid, tq, ready, prompt_len(turn[sid])))
        dirty = True

    def idle_sum():
        return sum(k for _, k in idle)

    def is_victim(sid):
        return any(r["sid"] == sid and r["resumed"] for r in waiting)

    def evict_tokens(need):
        """Free ``need`` idle tokens, LRU first; a preempted request's entry is trimmed from its tail (``tail``), others are evicted whole."""
        while need > 0:
            sid, kv = idle[0]
            if tail and kv > need and is_victim(sid):
                idle[0][1] = kv - need
                return
            idle.pop(0)
            need -= kv

    def evict_to_fit(used):
        over = used + idle_sum() - M
        if over > 0:
            evict_tokens(over)

    def order(now):
        if kind == "fcfs":
            return list(waiting)
        kv = {s: k for s, k in idle}
        hits = sorted([r for r in waiting if r["sid"] in kv], key=lambda r: (-kv[r["sid"]], r["q"], r["rid"]))
        hs = {r["rid"] for r in hits}
        return hits + [r for r in waiting if r["rid"] not in hs]

    def held_now():
        return sum(x["pos"] if x["kind"] == "pf" else x["ctx"] for x in running)

    def requeue(x, kv_idle, front):
        nonlocal dirty
        r = x["r"]
        if cache and kv_idle > 0:
            assert all(s != r["sid"] for s, _ in idle)
            idle.append([r["sid"], kv_idle])
        nr = new_req(r["sid"], r["q"], r["ready"], r["prompt"], gen=x["gen"], resumed=True, turn_=r["turn"])
        if front:
            waiting.insert(0, nr)
        else:
            waiting.append(nr)
        dirty = True
        trace.append(("P", r["sid"], r["turn"], kv_idle, t))

    def finish(x, now):
        nonlocal seq_ctr, dirty
        r = x["r"]
        sid = r["sid"]
        running.remove(x)
        trace.append(("D", sid, r["turn"], now))
        dirty = True
        end = r["prompt"] + D
        if r["turn"] < nt[sid]:
            if cache:
                idle.append([sid, end])
            turn[sid] = r["turn"] + 1
            seq_ctr += 1
            tool_ev.append((now + tools[sid][r["turn"] - 1], seq_ctr, sid))

    def chunk_plan(cands_pf):
        budget, ch = CB, []
        for x in cands_pf:
            if budget <= 0:
                break
            c = min(budget, x["rem"])
            ch.append((x, c))
            budget -= c
        return ch

    def ratio_running_step():
        """SGLang decode-OOM check: retract (fewest outputs first) until one token per decode request fits, re-estimate the ratio, allocate
        one token per decode request. Returns (retracted, tokens allocated)."""
        nonlocal ratio
        retracted = False
        dec = [x for x in running if x["kind"] == "dec"]
        if held_now() + len(dec) > M:
            retracted = True
            while held_now() + len(dec) > M and len(dec) > 1:
                v = min(dec, key=lambda x: (x["gen"], -x["r"]["prompt"], -x["r"]["rid"]))
                dec.remove(v)
                running.remove(v)
                requeue(v, v["r"]["prompt"], front=False)
                need = min(R * len(dec), idle_sum()) if headroom else 0
                evict_tokens(need)
            while held_now() + len(dec) > M:
                pfs = [x for x in running if x["kind"] == "pf"]
                v = pfs[-1]
                running.remove(v)
                requeue(v, v["pos"], front=False)
            n_k = len(dec)
            ratio = min(1.0, (sum(x["gen"] for x in dec) + R * n_k) / (D * n_k + 1))
        evict_to_fit(held_now() + len(dec))
        return retracted, len(dec)

    while t < horizon:
        # ---- exogenous events (arrival before tool return at ties)
        while True:
            ta = arr[nxt] if nxt < n else float("inf")
            te = min(tool_ev) if tool_ev else (float("inf"),)
            if ta <= te[0] and ta <= t:
                turn[nxt] = 1
                enqueue(nxt, ta, ta)
                nxt += 1
            elif te[0] <= t:
                tool_ev.remove(te)
                enqueue(te[2], te[0], te[0])
            else:
                break
        for x in sorted(pending_done, key=lambda z: z["r"]["rid"]):
            finish(x, t)
        pending_done = []

        # ---- running loop
        changed = False
        step_alloc = 0
        chunks: List = []
        retracted = False
        if mode == "ondemand_preempt":
            pf = [x for x in running if x["kind"] == "pf"]
            plan = dict((id(x), c) for x, c in chunk_plan(pf))
            used = held_now()
            order_ = list(running)
            budget_used_chunks = []
            i = 0
            # the literal vLLM loop (running order; pop the LAST running request until the allocation fits)
            while i < len(order_):
                x = order_[i]
                need = (plan.get(id(x), 0) + (1 if (plan.get(id(x), 0) > 0 and plan[id(x)] == x["rem"]) else 0)) if x["kind"] == "pf" else 1
                self_preempted = False
                while used + need > M:
                    v = order_.pop()
                    used -= v["pos"] if v["kind"] == "pf" else v["ctx"]
                    running.remove(v)
                    requeue(v, v["pos"] if v["kind"] == "pf" else v["ctx"], front=True)
                    changed = True
                    if v is x:
                        self_preempted = True
                        break
                if self_preempted:
                    break
                used += need
                if x["kind"] == "pf" and plan.get(id(x), 0) > 0:
                    chunks.append((x, plan[id(x)]))
                i += 1
            step_alloc = used - held_now()
            # preempted requests were requeued in pop order (newest first) at the FRONT: oldest victim ends up first
            evict_to_fit(held_now() + step_alloc)
        elif sep is None:
            retracted, step_alloc = ratio_running_step()
            changed = retracted

        # ---- waiting loop
        if dirty and not changed:
            dirty = False
            if waiting:
                pf_now = [x for x in running if x["kind"] == "pf"]
                n_run = len(running)
                pending = sum(x["rem"] for x in pf_now)
                budget_left = CB - pending if limited else float("inf")
                used = held_now() + step_alloc
                if mode == "ondemand_preempt":
                    chunk_left = CB - sum(c for _, c in chunks)
                else:
                    dec_now = [x for x in running if x["kind"] == "dec"]
                    offset = ratio * sum(D - x["gen"] for x in dec_now)
                    commit = pending
                for r in order(t):
                    if n_run >= MS or (limited and budget_left <= 0):
                        break
                    total = r["prompt"] + r["gen"]
                    if mode == "ondemand_preempt":
                        wm = int(watermark * M) if (watermark > 0 and M != float("inf") and n_run > 0) else 0
                        kv_ = next((k for s, k in idle if s == r["sid"]), None)
                        new_ = total - (0 if kv_ is None else min(kv_, total - 1))
                        c_ = min(new_, chunk_left)
                        hit_ = total - new_
                        fits = used + ((hit_ + c_) if first_chunk else total) + (1 if (c_ > 0 and c_ == new_) else 0) + wm <= M
                    else:
                        dec_b = D - r["gen"]
                        fits = (used + commit + offset + total + dec_b < M) or (n_run == 0 and total + dec_b <= M)
                    if not fits:
                        break
                    kv = next((k for s, k in idle if s == r["sid"]), None)
                    if kv is not None:
                        idle[:] = [[s, k] for s, k in idle if s != r["sid"]]
                    hit = 0 if kv is None else min(kv, total - 1)
                    new = total - hit
                    used += hit
                    x = dict(r=r, kind="pf", pos=hit, rem=new, ctx=0, left=0, gen=r["gen"])
                    if mode == "ondemand_preempt":
                        c0 = min(new, chunk_left)
                        if c0 > 0:
                            used += c0 + (1 if c0 == new else 0)
                            chunk_left -= c0
                            chunks.append((x, c0))
                    else:
                        commit += new + dec_b
                    evict_to_fit(used)
                    waiting.remove(r)
                    running.append(x)
                    if r["resumed"]:
                        trace.append(("R", r["sid"], r["turn"], hit, new, t))
                    else:
                        trace.append(("A", r["sid"], r["turn"], kv is not None, t))
                    n_run += 1
                    if limited:
                        budget_left -= new
        if mode == "ratio_reserve":
            # chunks are handed out FIFO but only up to the free memory
            pf = [x for x in running if x["kind"] == "pf"]
            n_dec_alloc = 0 if sep is not None else len([x for x in running if x["kind"] == "dec"])      # separate: decode allocates in its own iteration
            free = M - held_now() - n_dec_alloc
            budget, chunks = CB, []
            for x in pf:
                if budget <= 0 or free <= 0:
                    break
                c = min(x["rem"], budget, free)
                need = c + (1 if c == x["rem"] else 0)
                if need > free:
                    c -= 1
                    need = c
                    if c <= 0:
                        break
                chunks.append((x, c))
                budget -= c
                free -= need
            evict_to_fit(held_now() + n_dec_alloc + sum(c + (1 if c == x["rem"] else 0) for x, c in chunks))

        # ---- idle engine
        if not running:
            assert not waiting
            if mode == "ratio_reserve":
                ratio = ratio_init
            ta = arr[nxt] if nxt < n else float("inf")
            te = min(tool_ev)[0] if tool_ev else float("inf")
            nx = min(ta, te)
            if nx >= horizon:
                break
            t = nx
            continue

        # ---- one iteration
        if sep is not None and not chunks:
            retracted, step_alloc = ratio_running_step()               # decode iteration: the decode-OOM check happens here
        dec = [x for x in running if x["kind"] == "dec"]
        ntok = sum(c for _, c in chunks)
        attn = sum(c * (x["pos"] + c) for x, c in chunks)
        if sep is not None and chunks:
            tau = sep["pf_fixed"] + sep["pf_tok"] * ntok + e["prefill_attn_s"] * attn
            dec_adv = []                                               # prefill iteration: decode sequences neither advance nor decay the ratio
        elif sep is not None:
            tau = (sep["dc_fixed"] + max(sep["dc_floor"], sep["dc_seq"] * len(dec)) + e["decode_attn_s"] * sum(x["ctx"] for x in dec) / e["attn_ctx_norm"])
            dec_adv = dec
        else:
            tau = (e["iter_fixed_s"] + max(e["iter_floor_s"], e["per_token_s"] * (ntok + len(dec)))
                   + e["decode_attn_s"] * sum(x["ctx"] for x in dec) / e["attn_ctx_norm"] + e["prefill_attn_s"] * attn)
            dec_adv = dec
        t += tau
        if mode == "ratio_reserve" and dec_adv and not retracted:
            ratio = max(ratio - ratio_decay, ratio_min)
        for x in dec_adv:
            x["ctx"] += 1
            x["gen"] += 1
            x["left"] -= 1
            if x["left"] == 0:
                pending_done.append(x)
        for x, c in chunks:
            x["pos"] += c
            x["rem"] -= c
            if x["rem"] == 0:
                x["gen"] += 1
                x["kind"], x["ctx"], x["left"] = "dec", x["pos"] + 1, D - x["gen"]
                if x["left"] <= 0:
                    pending_done.append(x)
        if chunks:
            dirty = True
    return trace


def _ref_vs_engine(cfg5, mode, kind, M, seed, eo=None, rate=0.5, cold=20, burst=40, horizon=900.0, cache=True):
    wl = WorkloadParams.from_dict(cfg5["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=rate, initial_cold=cold, burst_n=burst, burst_t0=100.0, burst_width_s=10.0)
    specs = build_specs(wl, plan, seed)
    eo = dict(eo or {})
    eng = mk(cfg5, specs, policy="fcfs_lru" if kind == "fcfs" else "lpm_lru",
             eo={"kv_memory_tokens": M, "alloc_mode": mode, "cache_enabled": cache, **eo}, horizon=horizon)
    eng.run(horizon)
    ratio_keys = ("sched_conservativeness", "init_new_token_ratio", "min_new_token_ratio_factor", "new_token_ratio_decay_steps",
                  "retract_decode_steps", "retract_evict_headroom")
    cfg_ref = deep_update(cfg5, {"engine": {k: eo[k] for k in ratio_keys if k in eo}})
    ref = reference_dyn_trace(cfg_ref, specs, kind, horizon, M=M, mode=mode, cache=cache, limited=eo.get("admission_limited_by_prefill_budget", True),
                              chunk_budget=eo.get("prefill_chunk_budget"), max_seqs=eo.get("max_running_seqs"),
                              watermark=eo.get("watermark_frac", 0.0), tail=eo.get("victim_kv_eviction", "tail") == "tail",
                              first_chunk=eo.get("ondemand_admission", "full_isl") == "first_chunk")
    return eng.trace, ref, eng


def _assert_dyn_traces_equal(a, b):
    assert len(a) == len(b), (len(a), len(b))
    for x, y in zip(a, b):
        assert x[:-1] == y[:-1], (x, y)
        assert x[-1] == pytest.approx(y[-1], rel=1e-9, abs=1e-9), (x, y)


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("kind", ["fcfs", "lpm"])
@pytest.mark.parametrize("M,eo,cache", [
    (70_000, {}, True),
    (150_000, {}, True),
    (45_000, {"admission_limited_by_prefill_budget": False}, True),
    (70_000, {"prefill_chunk_budget": 1500}, True),
    (41_000, {"prefill_chunk_budget": 3000}, True),
    (70_000, {}, False),
])
def test_engine_matches_the_naive_reference_simulator(cfg5, mode, kind, M, eo, cache):
    tr_e, ref, eng = _ref_vs_engine(cfg5, mode, kind, M, seed=21, eo=eo, cache=cache)
    assert sum(1 for x in tr_e if x[0] == "D") > 50
    assert sum(1 for x in tr_e if x[0] == "P") >= 3, "the scenario must preempt / retract"
    _assert_dyn_traces_equal(tr_e, ref)


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("kind", ["fcfs", "lpm"])
@pytest.mark.parametrize("eo", [{"prefill_chunk_budget": 700, "max_running_seqs": 10}, {"prefill_chunk_budget": 700, "max_running_seqs": 40},
                                {"max_running_seqs": 6}])
def test_engine_matches_the_naive_reference_with_a_small_running_cap(cfg5, mode, kind, eo):
    tr_e, ref, eng = _ref_vs_engine(cfg5, mode, kind, 70_000, seed=21, eo=eo)
    assert sum(1 for x in tr_e if x[0] == "D") > 50
    _assert_dyn_traces_equal(tr_e, ref)


@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("seed", [22, 23, 24])
def test_engine_matches_the_naive_reference_over_seeds_with_a_watermark(cfg5, mode, seed):
    eo = {"watermark_frac": 0.02} if mode == "ondemand_preempt" else {}
    tr_e, ref, eng = _ref_vs_engine(cfg5, mode, "fcfs", 70_000, seed=seed, eo=eo, rate=0.6, cold=30, burst=60)
    assert sum(1 for x in tr_e if x[0] == "P") >= 1
    _assert_dyn_traces_equal(tr_e, ref)
    if mode == "ondemand_preempt":                    # a 2 % watermark must change the schedule relative to watermark 0
        tr0, _, _ = _ref_vs_engine(cfg5, mode, "fcfs", 70_000, seed=seed, rate=0.6, cold=30, burst=60)
        assert [x[:-1] for x in tr0] != [x[:-1] for x in tr_e]


# ============================================================================ eviction rules and window columns in the new modes
@pytest.mark.parametrize("mode", DYN)
@pytest.mark.parametrize("ev", ["random", "mru_idle"])
def test_new_modes_work_with_the_round4_eviction_rules(cfg5, mode, ev):
    c2 = deep_update(cfg5, {"policies": {"ev": {"kind": "fcfs", "eviction": ev}}})
    outs = []
    for _ in range(2):
        wl = WorkloadParams.from_dict(c2["workload"])
        plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=0.5, initial_cold=20, burst_n=40, burst_t0=100.0, burst_width_s=10.0)
        specs = build_specs(wl, plan, 13)
        rs = RunSpec(exp="t", policy="ev", seed=13, horizon_s=900.0, plan=plan,
                     engine_overrides={"kv_memory_tokens": 70_000, "alloc_mode": mode, "victim_kv_eviction": "whole"}, debug=True)
        res = simulate(c2, rs, specs)
        outs.append(res["summary"])
    s = outs[0]
    assert s["n_preempt"] > 0 and s["n_evictions"] > 0 and s["max_resident_tokens"] <= 70_000
    assert {k: v for k, v in outs[0].items() if not k.startswith("wall")}.keys() == {k: v for k, v in outs[1].items() if not k.startswith("wall")}.keys()
    for k in ("n_preempt", "n_evictions", "n_turns_done", "recompute_tokens", "n_hits"):
        assert outs[0][k] == outs[1][k], k


@pytest.mark.parametrize("mode", DYN)
def test_window_columns_count_preemptions_and_recompute_tokens(cfg5, mode):
    wl = WorkloadParams.from_dict(cfg5["workload"])
    plan = ArrivalPlan(kind="constant", horizon_s=500.0, rate=0.5, initial_cold=20, burst_n=40, burst_t0=100.0, burst_width_s=10.0)
    specs = build_specs(wl, plan, 17)
    rs = RunSpec(exp="t", policy="fcfs_lru", seed=17, horizon_s=2000.0, plan=plan,
                 engine_overrides={"kv_memory_tokens": 70_000, "alloc_mode": mode})
    res = simulate(cfg5, rs, specs)
    wins, s = res["windows"], res["summary"]
    assert sum(w["preemptions"] for w in wins) == s["n_preempt"] > 0
    assert sum(w["recompute_tokens"] for w in wins) == s["recompute_tokens"] > 0
    full = simulate(cfg5, RunSpec(exp="t", policy="fcfs_lru", seed=17, horizon_s=2000.0, plan=plan,
                                  engine_overrides={"kv_memory_tokens": 70_000}), specs)
    assert "preemptions" not in full["windows"][0] and "n_preempt" not in full["summary"]


def test_full_reserve_memory_never_exceeds_M_on_the_same_congested_scenarios(cfg5):
    """The third mode of 'memory never exceeds M in every mode': full_reserve (reservations + idle) on the congested scenario that makes
    the new modes preempt; it never preempts and reports no allocation-mode statistics."""
    for M in (45_000, 70_000):
        eng, _ = _congested(cfg5, "full_reserve", M, cls=Engine)
        s = eng.stats()
        assert s["max_resident_tokens"] <= M and s["n_turns_done"] > 100 and s["n_evictions"] > 0
        assert "n_preempt" not in s and eng.reserved >= 0
