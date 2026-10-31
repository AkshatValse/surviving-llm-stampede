"""Rescue gate (plan R1): run-time cap changes, attrition, pause at tool-call boundaries and the resume deque, the release
rule of the client's gate-control task, GateCfg mode validation, and the two identity guarantees:

* a static cap from t = 0 (the CAPPED arm) makes exactly the decisions of the committed CAPPED gate (replayed on a
  recorded event sequence against the gate at the base commit), and never pauses;
* the rescue configs generate a plan.csv byte-identical to the BURST config's (same seed, rate and glue overrides), so a
  rescue run is the BURST run until t_on.

Timing-based tests use spacings of >= 50 ms so the 15.6 ms Windows timer resolution cannot flip them.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from agentload.client import LoadGenerator, write_plan_csv
from agentload.config import ARMS, config_from_dict, gate_rescue_params, load_config, resolve_rate
from agentload.gate import SessionGate
from agentload.workload import build_open_plan
from conftest import REPO, make_raw

BASE_COMMIT = "4d2bba2"          # r11/rescue branch point: the committed CAPPED gate and config before the rescue arm
LAMBDA_REF = 0.07153402100919228  # SGLang 300k lambda_miss (sessions/s), as in the plan's simulator bundles


def _old_file(rel: str) -> bytes:
    try:
        return subprocess.run(["git", "-C", str(REPO), "show", f"{BASE_COMMIT}:{rel}"], check=True,
                              capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:     # pragma: no cover  (shallow clone without the commit)
        pytest.skip(f"base commit {BASE_COMMIT} not available: {e}")


def _old_gate_class(tmp_path: Path):
    p = tmp_path / "old_gate.py"
    p.write_bytes(_old_file("src/agentload/gate.py"))
    spec = importlib.util.spec_from_file_location("old_gate_for_identity", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SessionGate


def _clock():
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    return lambda: loop.time() - t0


async def _settle(n: int = 6) -> None:
    for _ in range(n):
        await asyncio.sleep(0)


def _no_suspend(coro):
    """Run a coroutine that must finish without suspending; return its value."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    coro.close()
    raise AssertionError("the coroutine suspended")


# ============================================================================================ gate unit tests
def test_lowering_the_cap_below_active_works_by_attrition_without_hand_off():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(5):
            assert await g.acquire() == 0.0
        g.set_cap(2)
        assert g.active == 5                                  # nobody is evicted
        w = asyncio.ensure_future(g.acquire())                # a newcomer must queue: active >= cap
        await _settle()
        assert not w.done() and g.waiting == 1
        for left in (4, 3, 2):                                # three releases above the cap: slots disappear
            g.release()
            await _settle()
            assert g.active == left and not w.done()
        assert g.n_attrition == 3
        g.release()                                           # active == cap: this slot is handed to the waiter
        await asyncio.wait_for(w, 1.0)
        assert g.active == 2 and g.waiting == 0
        g.release(), g.release()
        return g

    g = asyncio.run(go())
    assert g.active == 0 and g.n_admitted == 6 and g.n_waited == 1


def test_checkpoint_pauses_only_when_over_the_cap():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(3):
            await g.acquire()
        assert _no_suspend(g.checkpoint()) == 0.0             # no cap
        g.set_cap(3)
        assert _no_suspend(g.checkpoint()) == 0.0             # at the cap, not over it
        g.set_cap(2)
        assert g.over_cap()
        p = asyncio.ensure_future(g.checkpoint("s0"))         # over the cap: gives the slot up and waits
        await _settle()
        assert not p.done() and g.active == 2 and g.paused == 1 and g.waiting == 1
        assert _no_suspend(g.checkpoint()) == 0.0             # back at the cap: the next checkpoint does not pause
        await asyncio.sleep(0.06)
        g.release()                                           # active == cap -> hand-off to the paused session
        pause = await asyncio.wait_for(p, 1.0)
        assert pause >= 0.05 and g.active == 2 and g.paused == 0
        return g

    g = asyncio.run(go())
    assert g.n_pauses == 1 and g.n_resumes == 1 and len(g.pauses_s) == 1
    kinds = [e["event"] for e in g.events]
    assert kinds == ["cap", "cap", "pause", "resume"] and g.events[2]["sid"] == "s0"
    assert g.events[3]["pause_s"] == pytest.approx(g.pauses_s[0])


def test_the_resume_deque_is_served_before_new_waiters():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(3):
            await g.acquire()
        g.set_cap(2)
        order = []

        async def newcomer(i):
            await g.acquire()
            order.append(f"new{i}")

        async def pauser(i):
            await g.checkpoint(i)
            order.append(f"resume{i}")

        n0 = asyncio.ensure_future(newcomer(0))               # the newcomer queues FIRST...
        await _settle()
        p0 = asyncio.ensure_future(pauser(0))                 # ...then a session pauses (3 > 2)
        await _settle()
        assert g.waiting_new == 1 and g.paused == 1 and g.active == 2
        n1 = asyncio.ensure_future(newcomer(1))               # a later newcomer queues (both deques non-empty)
        await _settle()
        g.release()                                           # the paused session goes first, regardless of age
        await _settle()
        g.release()
        await _settle()
        g.release()
        await _settle()
        await asyncio.gather(n0, p0, n1)
        return order, g

    order, g = asyncio.run(go())
    assert order == ["resume0", "new0", "new1"]


def test_acquire_queues_while_only_the_resume_deque_is_non_empty():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(3):
            await g.acquire()
        g.set_cap(2)
        p = asyncio.ensure_future(g.checkpoint())
        await _settle()
        g.set_cap(3)                                          # room again: _fill resumes the paused session at once
        await asyncio.wait_for(p, 1.0)
        assert g.active == 3 and g.paused == 0
        g.set_cap(2)
        p2 = asyncio.ensure_future(g.checkpoint())
        await _settle()
        assert g.active == 2 and g.paused == 1
        g._active = 1                                         # force "room" while the resume deque is non-empty
        w = asyncio.ensure_future(g.acquire())                # must not barge past the paused session
        await _settle()
        assert not w.done()
        g._active = 2
        for f in (p2, w):
            f.cancel()
        await asyncio.gather(p2, w, return_exceptions=True)
        return g

    g = asyncio.run(go())
    assert g.waiting == 0


def test_a_paused_session_cancelled_after_its_slot_was_handed_back_passes_it_on():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(3):
            await g.acquire()
        g.set_cap(2)
        p = asyncio.ensure_future(g.checkpoint("a"))          # paused
        await _settle()
        w = asyncio.ensure_future(g.acquire())                # newcomer queued behind it
        await _settle()
        g.release()                                           # hands the slot to the paused session (future resolved)
        p.cancel()                                            # ...cancelled before it resumes
        res = await asyncio.gather(p, return_exceptions=True)
        assert isinstance(res[0], asyncio.CancelledError)
        await asyncio.wait_for(w, 1.0)                        # the slot reached the newcomer, it did not leak
        assert g.active == 2 and g.waiting == 0
        return g

    g = asyncio.run(go())
    assert g.n_pauses == 1 and g.n_resumes == 0


def test_a_paused_session_cancelled_while_queued_leaves_the_resume_deque():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(3):
            await g.acquire()
        g.set_cap(2)
        p = asyncio.ensure_future(g.checkpoint())
        await _settle()
        assert g.paused == 1 and g.queues_empty_since() is None
        p.cancel()
        await asyncio.gather(p, return_exceptions=True)
        assert g.paused == 0 and g.active == 2 and g.queues_empty_since() is not None
        w = asyncio.ensure_future(g.acquire())
        await _settle()
        g.release()                                           # goes to the newcomer, not to the cancelled pause
        await asyncio.wait_for(w, 1.0)
        return g

    g = asyncio.run(go())
    assert g.active == 2


def test_removing_the_cap_drains_both_deques_in_order():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(6):
            await g.acquire()
        g.set_cap(2)
        order = []

        async def pauser(i):
            await g.checkpoint(i)
            order.append(f"p{i}")

        async def newcomer(i):
            await g.acquire()
            order.append(f"n{i}")

        tasks = []
        for i in range(3):
            tasks.append(asyncio.ensure_future(newcomer(i)))
            await _settle()
            tasks.append(asyncio.ensure_future(pauser(i)))
            await _settle()
        assert g.paused == 3 and g.waiting_new == 3 and g.active == 3
        g.set_cap(None, reason="release")
        await asyncio.gather(*tasks)
        return order, g

    order, g = asyncio.run(go())
    assert order == ["p0", "p1", "p2", "n0", "n1", "n2"]      # resume deque first, FIFO within each
    assert g.active == 9 and g.waiting == 0
    kinds = [e["event"] for e in g.events]
    rel = kinds.index("release")
    assert g.events[rel]["cap"] is None and g.events[rel]["paused"] == 0 and g.events[rel]["waiting"] == 0
    assert kinds[rel + 1:] == ["resume"] * 3                  # the three paused sessions resume after the release


def test_raising_the_cap_fills_free_slots_resume_first():
    async def go():
        g = SessionGate(None, _clock())
        for _ in range(4):
            await g.acquire()
        g.set_cap(1)
        ps = []
        for i in range(3):                                    # 4 -> 3 -> 2 -> 1 active, three paused
            ps.append(asyncio.ensure_future(g.checkpoint(i)))
            await _settle()
        w = asyncio.ensure_future(g.acquire())
        await _settle()
        assert g.active == 1 and g.paused == 3 and g.waiting_new == 1
        g.set_cap(3)                                          # two free slots: the two oldest paused sessions
        await _settle()
        assert [p.done() for p in ps] == [True, True, False] and not w.done() and g.active == 3
        g.set_cap(None)
        await asyncio.gather(*ps, w)
        return g

    g = asyncio.run(go())
    assert g.active == 5 and g.n_resumes == 3


def test_queues_empty_since_tracks_the_last_time_both_deques_emptied():
    async def go():
        clock = {"t": 0.0}
        g = SessionGate(None, lambda: clock["t"])
        assert g.queues_empty_since() == float("-inf")
        for _ in range(2):
            await g.acquire()
        g.set_cap(1)
        clock["t"] = 5.0
        p = asyncio.ensure_future(g.checkpoint())
        await _settle()
        assert g.queues_empty_since() is None
        clock["t"] = 7.5
        g.release()                                           # active 1 == cap: hand-off empties the resume deque
        await asyncio.wait_for(p, 1.0)
        assert g.queues_empty_since() == 7.5
        clock["t"] = 9.0
        w = asyncio.ensure_future(g.acquire())
        await _settle()
        assert g.queues_empty_since() is None
        clock["t"] = 11.0
        w.cancel()
        await asyncio.gather(w, return_exceptions=True)
        assert g.queues_empty_since() == 11.0
        return g

    asyncio.run(go())


def test_set_cap_rejects_bad_values():
    async def go():
        g = SessionGate(None, _clock())
        for bad in (0, -1, 2.5, True, "3"):
            with pytest.raises(ValueError):
                g.set_cap(bad)
    asyncio.run(go())


def test_a_static_cap_never_pauses():
    async def go():
        g = SessionGate(3, _clock())
        rng = np.random.default_rng(1)
        live = peak = 0

        async def sess(i, turns):
            nonlocal live, peak
            await g.acquire()
            live += 1
            peak = max(peak, live)
            for _ in range(turns):
                await asyncio.sleep(float(rng.uniform(0.0, 0.004)))
                assert not g.over_cap()
                assert _no_suspend(g.checkpoint(i)) == 0.0    # a tool-call boundary under a static cap
            live -= 1
            g.release()

        tasks = []
        for i in range(40):
            tasks.append(asyncio.ensure_future(sess(i, int(rng.integers(1, 5)))))
            await asyncio.sleep(0.001)
        await asyncio.gather(*tasks)
        return g, peak

    g, peak = asyncio.run(go())
    assert peak == 3 and g.n_pauses == 0 and g.n_attrition == 0 and g.events == [] and g.max_paused_seen == 0
    assert g.n_admitted == 40 and g.n_waited > 10


# ============================================================================================ CAPPED decision identity
OLD_SUMMARY_KEYS = ["n_cap", "n_admitted", "n_waited", "max_active_seen", "max_waiting_seen", "wait_s_max",
                    "wait_s_mean", "n_still_waiting_at_end"]


async def _replay(GateCls, cap, seed, n_ops=400, checkpoints=False):
    """Drive a gate through a recorded (seeded) event sequence on a step clock; return the op list and the decision
    trace (state after every op). Ops: arrive (a new session), end (an admitted session finishes), cancel (a random live
    session, queued or admitted), turn (an admitted session passes a tool-call boundary; checkpoint() on the new gate)."""
    clock = {"t": 0.0}
    g = GateCls(cap, lambda: clock["t"])
    rng = np.random.default_rng(seed)
    cmds, tasks, holding, admitted_order, ops, trace = {}, {}, set(), [], [], []

    async def sess(i):
        held = False
        try:
            await g.acquire()
            held = True
            holding.add(i)
            admitted_order.append(i)
            while True:
                c = await cmds[i].get()
                if c == "end":
                    return
                if checkpoints:
                    assert await g.checkpoint(i) == 0.0
        finally:
            holding.discard(i)
            if held:
                g.release()

    nxt = 0
    for _ in range(n_ops):
        live = sorted(i for i, t in tasks.items() if not t.done())
        hold = sorted(holding)
        r = rng.random()
        if r < 0.45 or not live:
            op = ("arrive", nxt)
            cmds[nxt] = asyncio.Queue()
            tasks[nxt] = asyncio.ensure_future(sess(nxt))
            nxt += 1
        elif r < 0.75 and hold:
            i = int(rng.choice(hold))
            op = ("end", i)
            cmds[i].put_nowait("end")
        elif r < 0.85:
            i = int(rng.choice(live))
            op = ("cancel", i)
            tasks[i].cancel()
        elif hold:
            i = int(rng.choice(hold))
            op = ("turn", i)
            cmds[i].put_nowait("turn")
        else:
            op = ("noop", -1)
        clock["t"] += 1.0
        await _settle(8)
        ops.append(op)
        trace.append((op, g.active, g.waiting, len(admitted_order), tuple(admitted_order[-3:]), g.max_active_seen,
                      g.max_waiting_seen, g.n_admitted, g.n_waited))
    for t in tasks.values():
        t.cancel()
    await asyncio.gather(*tasks.values(), return_exceptions=True)
    s = g.summary()
    return ops, trace, admitted_order, list(g.waits_s), {k: s[k] for k in OLD_SUMMARY_KEYS}, g


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


# sha256 of the full (ops, trace, admission order, waits, summary) of the committed CAPPED gate on _replay(cap=3, seed=7).
# Lets the identity test run even where the base commit is unavailable; recomputed from the base commit when it is.
RECORDED_CAP3_SEED7 = "180d6c794e73658a3a759216a584a90141797a4579d98f7c38aeb4c3eb2a5910"


@pytest.mark.parametrize("cap,seed", [(1, 0), (3, 7), (7, 2), (None, 5)])
def test_a_static_cap_makes_exactly_the_committed_capped_gates_decisions(tmp_path, cap, seed):
    OldGate = _old_gate_class(tmp_path)
    old = asyncio.run(_replay(OldGate, cap, seed))
    new = asyncio.run(_replay(SessionGate, cap, seed, checkpoints=True))   # new gate also checkpoints at every turn
    assert new[0] == old[0]                                   # same recorded op sequence (it reacts to the state)
    assert new[1] == old[1]                                   # identical state after every op
    assert new[2] == old[2] and new[3] == old[3] and new[4] == old[4]
    g = new[5]
    assert g.n_pauses == 0 and g.n_attrition == 0 and g.events == []
    assert sum(op[0] == "cancel" for op in old[0]) > 10 and old[4]["n_waited"] > (10 if cap and cap < 7 else -1)


def test_the_recorded_capped_trace_digest(tmp_path):
    """The recorded decision trace of the static gate (no git needed): guards the CAPPED semantics on any clone."""
    new = asyncio.run(_replay(SessionGate, 3, 7, checkpoints=True))
    got = _digest(new[:5])
    try:
        OldGate = _old_gate_class(tmp_path)
        old = asyncio.run(_replay(OldGate, 3, 7))
        assert _digest(old[:5]) == got
    except pytest.skip.Exception:                             # pragma: no cover
        pass
    assert got == RECORDED_CAP3_SEED7


# ============================================================================================ rescue control (client task)
def _rescue_gen(tmp_path, **gate):
    g = {"mode": "rescue", "n_cap": 1, "t_on_s": 0.2, "pause_at_turns": True, "release_hold_s": 0.3, "min_on_s": 0.4,
         "release_check_s": 0.1}
    g.update(gate)
    raw = make_raw(gate=g, meta={"arm": "rescue", "engine_label": "mock-test"})
    cfg = config_from_dict(raw)
    return LoadGenerator(cfg, raw, tmp_path, REPO)


def test_gate_control_engages_at_t_on_and_releases_after_the_hold(tmp_path):
    async def go():
        gen = _rescue_gen(tmp_path)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        g = gen.gate
        assert g.max_active is None and gen.n_cap == 1
        for _ in range(3):
            await g.acquire()                                 # three active sessions before t_on
        ctl = asyncio.ensure_future(gen._gate_control())
        await gen._sleep_until(0.27)
        assert gen.t_engage is not None and abs(gen.t_engage - 0.2) < 0.05 and g.max_active == 1
        p = asyncio.ensure_future(g.checkpoint("x"))          # 3 > 1: pauses
        await gen._sleep_until(0.65)
        assert not p.done() and gen.t_release is None         # past t_on + min_on = 0.6, but the queue is not empty
        g.release()                                           # attrition: 2 -> 1
        g.release()                                           # 1 == cap: handed to the paused session; queues empty now
        t_empty = gen.now()
        await asyncio.wait_for(p, 1.0)
        await asyncio.wait_for(ctl, 2.0)
        return gen, t_empty

    gen, t_empty = asyncio.run(go())
    # release at the first tick t_on + k*0.1 with now - t_empty >= 0.3: about 1.0 s (ticks 0.7-0.9 are too early)
    assert gen.t_release is not None and gen.t_release - t_empty >= 0.3 - 1e-6 and gen.t_release < t_empty + 0.45
    assert [e["event"] for e in gen.gate.events] == ["engage", "pause", "resume", "release"]
    assert gen.gate.max_active is None


def test_gate_control_does_not_release_before_min_on(tmp_path):
    async def go():
        gen = _rescue_gen(tmp_path, n_cap=5, min_on_s=0.5, release_hold_s=0.0)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        await asyncio.wait_for(gen._gate_control(), 2.0)      # queues empty throughout
        return gen

    gen = asyncio.run(go())
    assert gen.t_release == pytest.approx(0.7, abs=0.06)      # first tick >= t_on + min_on = 0.2 + 0.5


def test_gate_control_never_releases_while_sessions_wait(tmp_path):
    async def go():
        gen = _rescue_gen(tmp_path, min_on_s=0.1, release_hold_s=0.1)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        g = gen.gate
        await g.acquire()
        ctl = asyncio.ensure_future(gen._gate_control())
        await gen._sleep_until(0.25)
        w = asyncio.ensure_future(g.acquire())                # queued behind the cap of 1 for the rest of the test
        await gen._sleep_until(1.0)
        assert gen.t_release is None and not ctl.done()
        ctl.cancel()
        w.cancel()
        await asyncio.gather(ctl, w, return_exceptions=True)
        return gen

    gen = asyncio.run(go())
    assert gen.t_release is None and gen.t_engage is not None


def test_before_t_on_a_rescue_checkpoint_never_suspends_and_logs_nothing(tmp_path):
    """The identity of the rescue arm with BURST before t_on rests on this: uncapped, checkpoint() returns at once."""
    async def go():
        gen = _rescue_gen(tmp_path, n_cap=1)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        g = gen.gate
        assert gen.pause_at_turns and g.max_active is None
        for _ in range(50):
            await g.acquire()
        for i in range(200):
            assert not g.over_cap() and _no_suspend(g.checkpoint(i)) == 0.0
        return g

    g = asyncio.run(go())
    assert g.events == [] and g.n_pauses == 0 and g.n_attrition == 0 and g.active == 50


def test_an_error_in_the_gate_controller_aborts_the_run(tmp_path):
    async def go():
        gen = _rescue_gen(tmp_path)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        gen._stop = asyncio.Event()
        gen.events = []
        gen.n_cap = 0                                         # set_cap(0) raises at the engage
        await asyncio.wait_for(gen._gate_control(), 2.0)
        return gen

    gen = asyncio.run(go())
    assert gen._stop.is_set() and gen.abort_reason == "gate_control_error" and gen.t_abort is not None
    assert gen.gate_control_error.startswith("ValueError") and "gate_control_error" in gen.events[0]
    assert gen._gate_outcome()["gate_control_error"] == gen.gate_control_error


# ============================================================================================ config
def test_gate_mode_validation():
    ok = config_from_dict(make_raw(gate={"mode": "rescue", "n_cap": 4, "t_on_s": 10, "pause_at_turns": True},
                                   meta={"arm": "rescue", "engine_label": "mock-test"}))
    p = gate_rescue_params(ok.gate)
    assert p == {"mode": "rescue", "n_cap_configured": 4, "t_on_s": 10.0, "pause_at_turns": True,
                 "release_hold_s": 300.0, "min_on_s": 600.0, "release_check_s": 10.0}
    assert "rescue" in ARMS and {"", "burst", "noburst", "capped"} <= ARMS
    assert config_from_dict(make_raw(gate={"n_cap": 4})).gate.mode == "static"
    assert gate_rescue_params(config_from_dict(make_raw(gate={"n_cap": 4})).gate) == {"mode": "static",
                                                                                      "n_cap_configured": 4}
    resc = {"mode": "rescue", "n_cap": 4, "t_on_s": 10, "pause_at_turns": True}
    bad = [
        ({"mode": "adaptive"}, {}, "static|rescue"),
        ({"n_cap": 4, "t_on_s": 10}, {}, "only apply to gate.mode=rescue"),               # rescue keys on a static gate
        ({"n_cap": 4, "pause_at_turns": False}, {}, "only apply"),
        ({}, {"arm": "rescue"}, "needs gate.mode=rescue"),                                 # arm rescue, static gate
        ({**resc, "n_cap": None}, {"arm": "rescue"}, "requires gate.n_cap"),
        ({**resc, "t_on_s": None}, {"arm": "rescue"}, "t_on_s"),
        ({**resc, "t_on_s": -1}, {"arm": "rescue"}, "t_on_s"),
        ({**resc, "pause_at_turns": None}, {"arm": "rescue"}, "pause_at_turns"),
        ({**resc, "pause_at_turns": "yes"}, {"arm": "rescue"}, "pause_at_turns"),
        ({**resc, "release_hold_s": -5}, {"arm": "rescue"}, "release_hold_s"),
        ({**resc, "min_on_s": "x"}, {"arm": "rescue"}, "min_on_s"),
        ({**resc, "release_check_s": 0}, {"arm": "rescue"}, "release_check_s"),
        (resc, {"arm": "capped"}, "meta.arm must be rescue"),                              # capped + a rescue config
        (resc, {"arm": "burst"}, "meta.arm must be rescue"),
        ({**resc, "n_cap": 0}, {"arm": "rescue"}, "n_cap"),
    ]
    for gate, meta, msg in bad:
        with pytest.raises(ValueError, match=msg):
            config_from_dict(make_raw(gate=gate, meta={"engine_label": "mock-test", **meta}))
    with pytest.raises(ValueError, match="closed|open-loop"):
        config_from_dict(make_raw(gate=resc, arrivals={"kind": "closed", "closed_n": 3, "rate": None},
                                  meta={"arm": "rescue", "engine_label": "mock-test"}))
    with pytest.raises(KeyError):
        config_from_dict(make_raw(gate={**resc, "t_off_s": 5}, meta={"arm": "rescue", "engine_label": "mock-test"}))


RESCUE_CONFIGS = {"configs/agentload_e2_rescue.yaml": (20, 1800.0, 300.0, 600.0),
                  "configs/agentload_e2_rescue_native.yaml": (64, 2100.0, 300.0, 600.0),
                  "configs/agentload_e2_rescue_smoke.yaml": (20, 900.0, 120.0, 300.0)}


@pytest.mark.parametrize("path", sorted(RESCUE_CONFIGS))
def test_rescue_configs_are_the_burst_config_plus_the_gate_block(path):
    burst = yaml.safe_load((REPO / "configs/agentload_e2_burst.yaml").read_bytes())
    resc = yaml.safe_load((REPO / path).read_bytes())
    n_cap, t_on, hold, min_on = RESCUE_CONFIGS[path]
    assert resc["gate"] == {"mode": "rescue", "n_cap": n_cap, "t_on_s": t_on, "pause_at_turns": True,
                            "release_hold_s": hold, "min_on_s": min_on, "release_check_s": 10}
    diff = {k for k in set(burst) | set(resc) if burst.get(k) != resc.get(k)}
    if "smoke" in path:                                       # 2400-s run, burst at 300 s
        assert diff == {"gate", "arrivals", "run"}
        assert resc["run"] == {**burst["run"], "duration_s": 2400}
        assert resc["arrivals"] == {**burst["arrivals"], "burst": {**burst["arrivals"]["burst"], "t_s": 300},
                                    "analysis_t_burst_s": 300}
    else:
        assert diff == {"gate"}
    b_lines = (REPO / "configs/agentload_e2_burst.yaml").read_bytes().split(b"\n")
    r_lines = (REPO / path).read_bytes().split(b"\n")
    assert b"\r" not in (REPO / path).read_bytes()
    i = b_lines.index(b"gate:")
    assert r_lines[:i] == b_lines[:i] or "smoke" in path      # byte copy up to the gate block
    assert r_lines[-25:] == b_lines[-25:] or "smoke" in path  # ...and after it
    for arm in ("rescue",):                                   # what the job glue does: meta.arm + the registered n_cap
        cfg, _ = load_config(REPO / path, [f"meta.arm={arm}", f"gate.n_cap={n_cap}"])
        assert cfg.gate.mode == "rescue"
    with pytest.raises(ValueError, match="meta.arm must be rescue"):
        load_config(REPO / path, ["meta.arm=capped"])


# ============================================================================================ plan identity
GLUE = {"configs/agentload_e2_rescue.yaml": (1200, 8700), "configs/agentload_e2_rescue_native.yaml": (1200, 8700),
        "configs/agentload_e2_rescue_smoke.yaml": (300, 2400)}


def _plan_bytes(path: Path, overrides, tmp: Path, name: str) -> bytes:
    cfg, _ = load_config(path, overrides)
    plan = build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, resolve_rate(cfg.arrivals), [])
    out = tmp / name
    write_plan_csv(out, plan)
    return out.read_bytes()


def _glue_overrides(mult, seed, t_b, run_s):
    # e2_run's common --set list (slurm/common.sh), with lambda_ref as a number instead of a calibration path
    return [f"run.seed={seed}", f"arrivals.rate_mult={mult}", f"arrivals.lambda_ref={LAMBDA_REF}",
            f"arrivals.analysis_t_burst_s={t_b}", f"run.duration_s={run_s}", f"arrivals.burst.t_s={t_b}"]


@pytest.mark.parametrize("path", sorted(GLUE))
def test_rescue_plan_csv_is_byte_identical_to_the_burst_plan(tmp_path, path):
    t_b, run_s = GLUE[path]
    n_cap = RESCUE_CONFIGS[path][0]
    mults = (4.0,) if "native" in path else (1.35, 1.65)
    for mult in mults:
        for seed in (0, 1, 2):
            o = _glue_overrides(mult, seed, t_b, run_s)
            b = _plan_bytes(REPO / "configs/agentload_e2_burst.yaml", o + ["meta.arm=burst"], tmp_path, "b.csv")
            r = _plan_bytes(REPO / path, o + ["meta.arm=rescue", f"gate.n_cap={n_cap}"], tmp_path, "r.csv")
            c = _plan_bytes(REPO / "configs/agentload_e2_burst.yaml", o + ["meta.arm=capped", f"gate.n_cap={n_cap}"],
                            tmp_path, "c.csv")
            assert hashlib.sha256(r).hexdigest() == hashlib.sha256(b).hexdigest() == hashlib.sha256(c).hexdigest()
            assert r.count(b"\n") > 200                       # a real plan (with the 200-session burst)
