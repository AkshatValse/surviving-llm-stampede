"""Released-baseline rule checks and platform-independent golden trace checks.

The original golden tests still compare every summary field. These additional
checks reach the window/queue digests even when Windows polyfit rounding makes a
summary comparison fail first; no fixture or summary assertion is relaxed.
"""
from __future__ import annotations

import heapq
import json

import pytest

from golden_cells import GOLDEN as MIXED_GOLDEN, golden_specs, load_cfg
from prefixmeta.engine import Engine, EngineParams
from prefixmeta.mechanisms import Mechanisms, make_mechanisms
from prefixmeta.metrics import Recorder
from prefixmeta.policies import Fcfs
from prefixmeta.sim import simulate
from prefixmeta.workload import WorkloadParams
from test_mech_engine import BIG_EO, BIG_WL, E1, _eager_state, cfg, mk, specs_of
from test_r5_engine import GOLDEN as R4_GOLDEN, _digest, _golden_specs, cfg4


MODE = "continuum_waiting"
POLICY = {"kind": "fcfs", "ttl_pin_s": 500.0, "ttl_unpin": MODE}


def _set_expiries(eng, first: float, second: float) -> None:
    for sid, expiry in ((1, first), (2, second)):
        eng._pin[sid] = (expiry, eng._pin[sid][1])
    eng._pin_heap = [(expiry, seq, sid) for sid, (expiry, seq) in eng._pin.items()]
    heapq.heapify(eng._pin_heap)


@pytest.mark.parametrize(
    "first,second,victim",
    [(600.0, 500.0, 1), (500.0, 600.0, 2), (500.0, 500.0, 1)],
    ids=["older-program-later-expiry", "newer-program-later-expiry", "tie-first-pin"],
)
def test_continuum_waiting_uses_expiry_then_first_pin(cfg, first, second, victim):
    eng = _eager_state(cfg, MODE)
    _set_expiries(eng, first, second)
    # A release changes eligibility only: eviction and admission happen on retry.
    eng._schedule_pass()
    assert set(eng._pin) == {1, 2} - {victim}
    assert set(eng._hard) == set(eng._pin)
    assert eng._hard_sum == E1
    assert eng.idle_sum == 2 * E1 and set(eng.idle) == {1, 2}
    assert eng.n_released == 1 and eng.n_stall_breaks == 1
    assert eng.n_admitted == 0 and eng.n_evictions == 0 and eng.dirty


def test_continuum_waiting_all_pins_includes_the_waiting_heads_own_pin(cfg):
    eng = _eager_state(cfg, MODE)
    own = eng._q[0].sid
    eng.idle[own] = 5000
    eng.idle_sum += 5000
    eng._pin_seq += 1
    eng._pin[own] = (1000.0, eng._pin_seq)
    heapq.heappush(eng._pin_heap, (1000.0, eng._pin_seq, own))
    eng._refresh_prot(own)
    assert eng.idle_sum <= eng.M
    assert eng._continuum_waiting_unpin()
    assert own not in eng._pin and own not in eng._hard
    assert eng.idle[own] == 5000 and set(eng._pin) == {1, 2}
    assert eng.n_released == 1 and eng.n_evictions == 0


def test_continuum_waiting_releases_one_per_pass_even_if_two_are_needed(cfg):
    eng = _eager_state(cfg, MODE)
    # Exercise the allocation predicate with a longer waiting request: neither
    # pin can coexist with its 30k end context, but both idle prefixes fit in M.
    head = eng._q[0]
    head.prompt, head.end = 29900, 30000
    assert 2 * E1 <= eng.M < E1 + head.end
    eng._schedule_pass()
    assert len(eng._pin) == 1 and eng.n_released == 1
    assert eng.n_admitted == 0 and not eng.prefill and eng.dirty
    eng._schedule_pass()
    assert not eng._pin and eng.n_released == 2
    assert eng.n_admitted == 0 and not eng.prefill and eng.dirty
    eng._schedule_pass()
    assert eng.n_admitted == 1 and eng.prefill == [head]
    assert eng.n_released == 2 and eng.n_eager_unpins == 0
    assert eng.reserved == 30000 and eng.idle_sum == 0


def test_continuum_waiting_does_not_release_for_a_blocked_head_while_running(cfg):
    eng = _eager_state(cfg, MODE, reserved_extra=5000)
    eng.n_D = 1
    before = dict(eng._pin)
    eng._schedule_pass()
    assert eng._pin == before and eng.n_released == 0
    assert eng.n_admitted == 0 and eng._first_blocked is eng._q[0]


def test_continuum_waiting_run_retries_immediately_before_future_expiry(cfg):
    rows = [(0.0, 2, 1000.0), (0.0, 2, 1000.0), (3.0, 1, 0.0)]
    eng = mk(cfg, POLICY, specs_of(rows), wo=BIG_WL, eo=BIG_EO)
    eng.run(50.0)
    first_finishes = [x[3] for x in eng.trace if x[0] == "D" and x[1] in (0, 1) and x[2] == 1]
    assert len(first_finishes) == 2
    third = [x for x in eng.trace if x[0] == "A" and x[1] == 2]
    assert len(third) == 1
    assert third[0][4] == max(first_finishes)
    assert third[0][4] < min(first_finishes) + POLICY["ttl_pin_s"]
    assert eng.n_released == 1 and eng.n_pin_expired == 0
    assert eng.n_eager_unpins == 0 and eng.n_turns_done == 3
    assert eng.max_resident <= eng.M


@pytest.mark.parametrize("protection", ["pin", "rank", "rank_length"])
def test_continuum_waiting_rejects_combined_queued_protection(protection):
    with pytest.raises(ValueError, match="cannot be combined with protect_queued"):
        make_mechanisms({**POLICY, "protect_queued": protection}, None)


def test_continuum_waiting_requires_ttl_and_head_of_line_admission(cfg):
    with pytest.raises(ValueError, match="requires ttl_pin_s"):
        make_mechanisms({"ttl_unpin": MODE}, None)
    with pytest.raises(ValueError, match="requires skip_ahead=False"):
        mk(cfg, POLICY, specs_of([(0.0, 1, 0.0)]), eo={"skip_ahead": True})


@pytest.mark.parametrize(
    "ttl,protection,error",
    [(None, None, "requires ttl_pin_s"),
     (500.0, "pin", "cannot be combined with protect_queued"),
     (500.0, "rank", "cannot be combined with protect_queued"),
     (500.0, "rank_length", "cannot be combined with protect_queued")],
)
def test_direct_engine_rejects_invalid_continuum_waiting_combinations(cfg, ttl, protection, error):
    # Direct dataclass construction bypasses make_mechanisms; it must not create
    # a pin-release mode with no TTL or a second source of hard/soft protection.
    with pytest.raises(ValueError, match=error):
        Engine(
            EngineParams.from_dict(cfg["engine"]),
            WorkloadParams.from_dict(cfg["workload"]),
            specs_of([(0.0, 1, 0.0)]),
            Fcfs(),
            Recorder(1000.0, 100.0),
            mech=Mechanisms(ttl_s=ttl, ttl_unpin=MODE, protect_queued=protection),
        )


R4_CELLS = json.loads(R4_GOLDEN.read_text())["cells"]
MIXED_CELLS = json.loads(MIXED_GOLDEN.read_text())["cells"]


@pytest.fixture(scope="module")
def mixed_cfg():
    return load_cfg()


def test_audit_digest_coverage_matches_both_golden_fixtures(cfg4, mixed_cfg):
    assert len(R4_CELLS) == 6 and set(R4_CELLS) == set(_golden_specs(cfg4))
    assert len(MIXED_CELLS) == 12 and set(MIXED_CELLS) == set(golden_specs(mixed_cfg))


def _assert_fixture_digests(result, golden):
    assert _digest(result) == (golden["windows_sha256"], golden["qtrace_sha256"])
    assert len(result["windows"]) == golden["n_windows"]


@pytest.mark.parametrize("cell", sorted(R4_CELLS))
def test_default_round4_windows_and_queue_remain_bit_identical(cfg4, cell):
    result = simulate(cfg4, _golden_specs(cfg4)[cell])
    _assert_fixture_digests(result, R4_CELLS[cell])


@pytest.mark.parametrize("extra_costs", [False, True], ids=["default", "ignored-extra-costs"])
@pytest.mark.parametrize("cell", sorted(MIXED_CELLS))
def test_default_mixed_windows_and_queue_remain_bit_identical(mixed_cfg, cell, extra_costs):
    rs = golden_specs(mixed_cfg)[cell]
    if extra_costs:
        rs.engine_overrides = {
            **rs.engine_overrides,
            "batching": "mixed",
            "prefill_iter_fixed_s": 0.5,
            "prefill_iter_floor_s": 0.2,
            "prefill_per_token_s": 9.0,
            "decode_iter_fixed_s": 0.7,
            "decode_iter_floor_s": 0.3,
            "decode_per_seq_s": 1.0,
        }
    _assert_fixture_digests(simulate(mixed_cfg, rs), MIXED_CELLS[cell])
