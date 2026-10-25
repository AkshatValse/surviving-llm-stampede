"""TTL release recency from Continuum's released free-block queue behavior."""
from __future__ import annotations

import heapq
from collections import OrderedDict

import pytest

from prefixmeta.mechanisms import Mechanisms, make_mechanisms
from test_mech_engine import BIG_EO, BIG_WL, E1, cfg, mk, specs_of


FLAG = "ttl_refresh_lru_on_unpin"


def _state(cfg, refresh=None, mode="idle", protection=None):
    policy = {"kind": "fcfs", "ttl_pin_s": 30.0, "ttl_unpin": mode}
    if refresh is not None:
        policy[FLAG] = refresh
    if protection is not None:
        policy["protect_queued"] = protection
    rows = [(0.0, 1, 0.0), (0.0, 2, 1.0), (0.0, 2, 1.0)]
    eng = mk(cfg, policy, specs_of(rows), wo=BIG_WL, eo=BIG_EO, debug=False)
    eng._next_idx = eng.in_system = 3
    # The latest program finished first, so release changes its eviction age.
    for sid, expiry in ((2, 30.0), (1, 20.0)):
        eng.idle[sid] = E1
        eng.idle_sum += E1
        eng._turn[sid] = 2
        eng._arrived_t[sid] = 0.0
        eng._pin_seq += 1
        eng._pin[sid] = (expiry, eng._pin_seq)
        heapq.heappush(eng._pin_heap, (expiry, eng._pin_seq, sid))
        eng._refresh_prot(sid)
    eng._turn[0] = 1
    eng._arrived_t[0] = 0.0
    eng._enqueue_turn(0, 1.0, 1.0)
    assert list(eng.idle) == [2, 1]
    return eng


def test_ttl_recency_default_and_explicit_false_need_no_ttl():
    assert Mechanisms().ttl_refresh_lru_on_unpin is False
    assert make_mechanisms({}, None).ttl_refresh_lru_on_unpin is False
    assert make_mechanisms({FLAG: False}, None).ttl_refresh_lru_on_unpin is False
    assert make_mechanisms({FLAG: True, "ttl_pin_s": 2.0}, None).ttl_refresh_lru_on_unpin is True


@pytest.mark.parametrize("value", [None, 0, 1, 1.0, "true", "false", [], {}])
def test_ttl_recency_requires_a_strict_bool(value):
    with pytest.raises(ValueError, match="must be a bool"):
        make_mechanisms({FLAG: value, "ttl_pin_s": 2.0}, None)
    with pytest.raises(ValueError, match="must be a bool"):
        Mechanisms(ttl_s=2.0, ttl_refresh_lru_on_unpin=value)


def test_ttl_recency_enabled_requires_ttl():
    with pytest.raises(ValueError, match="requires ttl_pin_s"):
        make_mechanisms({FLAG: True}, None)
    with pytest.raises(ValueError, match="requires ttl_pin_s"):
        Mechanisms(ttl_refresh_lru_on_unpin=True)


@pytest.mark.parametrize("refresh", [None, False, True], ids=["absent", "false", "true"])
def test_expired_pin_changes_the_next_eviction_only_when_enabled(cfg, refresh):
    eng = _state(cfg, refresh)
    # Session 1 is ordinary idle KV; session 2 is the only outstanding pin.
    del eng._pin[1]
    eng._refresh_prot(1)
    assert eng._pin_next_time() == 30.0  # discards the stale session-1 expiry
    eng._expire_pin(30.0)
    assert not eng._pin and not eng._hard
    assert eng.n_pin_expired == 1 and eng.idle_sum == 2 * E1
    eng._evict(E1)
    assert list(eng.idle) == ([2] if refresh else [1])
    assert eng.n_evictions == 1 and eng.idle_sum == E1


@pytest.mark.parametrize("mode", ["idle", "eager", "eager_fit", "continuum_waiting"])
@pytest.mark.parametrize("refresh", [False, True])
def test_pressure_release_changes_recency_in_every_ttl_mode(cfg, mode, refresh):
    eng = _state(cfg, refresh, mode)
    head = eng._waiting[0]
    assert eng.reserved + head.end + eng._hard_sum > eng.M
    if mode == "idle":
        eng._first_blocked = head
        released = eng._break_stall()
    elif mode == "continuum_waiting":
        released = eng._continuum_waiting_unpin()
    else:
        released = eng._eager_unpin(head)
    assert released and set(eng._pin) == {1} and set(eng._hard) == {1}
    assert list(eng.idle) == ([1, 2] if refresh else [2, 1])
    assert eng.idle_sum == 2 * E1 and eng.n_evictions == 0


def test_waiting_followup_preserves_pin_and_recency_at_expiry(cfg):
    eng = _state(cfg, True)
    eng._enqueue_turn(2, 2.0, 2.0)
    # Make the session-2 pin the next expiry without changing its insertion age.
    eng._pin[2] = (10.0, eng._pin[2][1])
    heapq.heappush(eng._pin_heap, (10.0, eng._pin[2][1], 2))
    eng._expire_pin(10.0)
    assert set(eng._pin) == {1, 2} and list(eng.idle) == [2, 1]
    assert eng.n_pin_expired == 0


def test_queued_only_protection_release_does_not_refresh_ttl_recency(cfg):
    eng = _state(cfg, True, protection="pin")
    for sid in (1, 2):
        del eng._pin[sid]
        eng._enqueue_turn(sid, 2.0 + sid, 2.0 + sid)
        eng._refresh_prot(sid)
    eng._first_blocked = eng._waiting[0]
    assert set(eng._hard) == {1, 2}
    assert eng._break_stall()
    assert set(eng._hard) == {1} and not eng._pin
    assert list(eng.idle) == [2, 1]


class _NoRecencyRefresh(OrderedDict):
    def move_to_end(self, key, last=True):
        raise AssertionError("admission must not refresh idle recency")


def test_admission_drops_pin_without_an_idle_recency_operation(cfg):
    eng = _state(cfg, True)
    eng._enqueue_turn(2, 2.0, 2.0)
    eng.idle = _NoRecencyRefresh(eng.idle)
    req = eng._waiting[2]
    eng._admit(req, 2.0)
    assert req.hit and list(eng.idle) == [1]
    assert set(eng._pin) == {1} and eng._hard_sum == E1
    assert eng.idle_sum == E1 and eng.n_pin_expired == 0
