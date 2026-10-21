"""Client-side session gate (CAPPED arm) and the three paired E2 arms (BURST / NOBURST / CAPPED) on the mock server:
arms share identical session specs except the burst, the cap is never exceeded, gate waits are logged."""
import asyncio
import json

import numpy as np
import pandas as pd
import pytest

from agentload.config import config_from_dict, resolve_n_cap
from agentload.gate import SessionGate
from agentload.mock_server import MockConfig
from agentload.workload import build_open_plan
from conftest import make_raw, run_gen

FAST = dict(kv_capacity_tokens=10**7, slots=64, fixed_s=0.05, per_uncached_token_s=0, per_completion_token_s=0,
            log_requests=False)


# ---------------------------------------------------------------------------------------------- SessionGate unit tests
def _clock():
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    return lambda: loop.time() - t0


def test_gate_is_fifo_and_never_exceeds_the_cap():
    async def go():
        g = SessionGate(3, _clock())
        order, live, peak = [], 0, 0

        async def sess(i, hold):
            nonlocal live, peak
            await g.acquire()
            order.append(i)
            live += 1
            peak = max(peak, live)
            await asyncio.sleep(hold)
            live -= 1
            g.release()

        rng = np.random.default_rng(0)
        tasks = []
        for i in range(40):                                  # 40 arrivals 1 ms apart, holds 5-30 ms: heavy queueing
            tasks.append(asyncio.ensure_future(sess(i, float(rng.uniform(0.005, 0.03)))))
            await asyncio.sleep(0.001)
        await asyncio.gather(*tasks)
        return g, order, peak

    g, order, peak = asyncio.run(go())
    assert order == list(range(40))                          # admission order == arrival order
    assert peak == 3 and g.max_active_seen == 3 and g.active == 0 and g.waiting == 0
    assert g.n_admitted == 40 and g.n_waited > 20 and g.max_waiting_seen >= 10
    assert len(g.waits_s) == 40 and min(g.waits_s) == 0.0 and max(g.waits_s) > 0.02


def test_gate_without_a_cap_admits_everything_at_once():
    async def go():
        g = SessionGate(None, _clock())
        waits = [await g.acquire() for _ in range(50)]
        return g, waits

    g, waits = asyncio.run(go())
    assert waits == [0.0] * 50 and g.n_waited == 0 and g.active == 50 and g.max_active_seen == 50


def test_gate_waiter_cancelled_in_the_queue_leaves_it():
    async def go():
        g = SessionGate(1, _clock())
        await g.acquire()
        w1 = asyncio.ensure_future(g.acquire())
        w2 = asyncio.ensure_future(g.acquire())
        await asyncio.sleep(0.01)
        assert g.waiting == 2
        w1.cancel()
        await asyncio.gather(w1, return_exceptions=True)
        assert g.waiting == 1
        g.release()                                          # the slot must skip the cancelled w1 and go to w2
        await asyncio.wait_for(w2, 1.0)
        assert g.active == 1
        g.release()
        return g

    g = asyncio.run(go())
    assert g.active == 0 and g.waiting == 0 and g.n_admitted == 2


def test_gate_waiter_cancelled_after_the_slot_was_handed_over_passes_it_on():
    async def go():
        g = SessionGate(1, _clock())
        await g.acquire()
        w1 = asyncio.ensure_future(g.acquire())
        w2 = asyncio.ensure_future(g.acquire())
        await asyncio.sleep(0.01)
        g.release()                                          # hands the slot to w1 (future resolved, task not yet run)
        w1.cancel()                                          # ...and w1 is cancelled before it resumes
        await asyncio.gather(w1, return_exceptions=True)
        await asyncio.wait_for(w2, 1.0)                      # the slot must reach w2, not leak
        g.release()
        return g

    g = asyncio.run(go())
    assert g.active == 0 and g.waiting == 0


def test_gate_rejects_nonpositive_cap():
    with pytest.raises(ValueError):
        SessionGate(0, lambda: 0.0)


# ---------------------------------------------------------------------------------------------- config
def test_gate_config_validation_and_resolution(tmp_path):
    cfg = config_from_dict(make_raw(gate={"n_cap": 12}))
    assert resolve_n_cap(cfg.gate) == 12 and resolve_n_cap(config_from_dict(make_raw()).gate) is None
    f = tmp_path / "mu_curve.json"
    f.write_text(json.dumps({"n_cap": 24, "bad": 2.5, "nothing": None}))
    assert resolve_n_cap(config_from_dict(make_raw(gate={"n_cap": f"{f}:n_cap"})).gate) == 24
    for key in ("bad", "nothing"):                            # non-integer / null Stage-C result must not become a cap
        with pytest.raises((ValueError, TypeError)):
            resolve_n_cap(config_from_dict(make_raw(gate={"n_cap": f"{f}:{key}"})).gate)
    with pytest.raises(FileNotFoundError, match="placeholder"):
        resolve_n_cap(config_from_dict(make_raw(gate={"n_cap": "<RESULTS_DIR>/mu_curve.json:n_cap"})).gate)
    with pytest.raises(ValueError):
        config_from_dict(make_raw(gate={"n_cap": 0}))
    with pytest.raises(ValueError):
        config_from_dict(make_raw(gate={"n_cap": 2.5}))
    with pytest.raises(ValueError, match="closed"):
        config_from_dict(make_raw(arrivals={"kind": "closed", "closed_n": 3, "rate": None}, gate={"n_cap": 3}))
    with pytest.raises(ValueError, match="meta.arm"):
        config_from_dict(make_raw(meta={"arm": "weird"}))
    with pytest.raises(ValueError, match="analysis_t_burst_s"):
        config_from_dict(make_raw(arrivals={"burst": {"n": 3, "t_s": 2.0, "width_s": 0.1}, "analysis_t_burst_s": 5.0}))


# ---------------------------------------------------------------------------------------------- plans
def plan(seed=3, *, burst=True):
    raw = make_raw(arrivals={"rate": 4.0, "burst": {"n": 30, "t_s": 40.0, "width_s": 5.0} if burst else None,
                             "analysis_t_burst_s": 40.0})
    cfg = config_from_dict(raw)
    return build_open_plan(seed, cfg.workload, cfg.arrivals, 100.0, 4.0, [])


def test_plan_arms_share_every_session_spec_except_the_burst_sessions():
    burst, noburst = plan(), plan(burst=False)
    capped = plan()                                          # the cap acts at run time: the CAPPED plan IS the BURST plan
    assert burst == capped
    b_burst = [p for p in burst if p.origin == "burst"]
    assert len(b_burst) == 30 and not any(p.origin == "burst" for p in noburst)
    key = lambda p: (p.origin, p.idx, p.arrival_s, p.n_turns, p.tool_times_s)
    assert sorted(key(p) for p in burst if p.origin == "base") == sorted(key(p) for p in noburst)
    assert len(burst) == len(noburst) + 30


# ---------------------------------------------------------------------------------------------- end to end, three arms
def arm_raw(arm, seed=0, n_cap=4, **extra):
    """BURST / NOBURST / CAPPED variants of one tiny configuration (same seed => same arrival and spec streams)."""
    arrivals = {"rate": 5.0, "analysis_t_burst_s": 1.5,
                "burst": None if arm == "noburst" else {"n": 25, "t_s": 1.5, "width_s": 0.2}}
    raw = make_raw(arrivals=arrivals, workload={"tool_time_mean_s": 0.15, "mean_turns": 3, "max_turns": 5},
                   run={"duration_s": 5.0, "seed": seed}, meta={"arm": arm, "engine_label": "mock-fcfs"},
                   gate={"n_cap": n_cap if arm == "capped" else None})
    raw["arrivals"]["rate"] = 5.0
    raw.update(extra)
    return raw


@pytest.fixture(scope="module")
def arms(tmp_path_factory):
    root = tmp_path_factory.mktemp("arms")
    outs, truth = {}, {}
    for i, arm in enumerate(("burst", "noburst", "capped")):
        raw = arm_raw(arm)
        raw["workload"]["content_salt"] = i + 1              # as the job scripts: a different salt per run
        outs[arm], truth[arm] = run_gen(raw, MockConfig(**FAST), root)
    return outs


def read(out):
    d = out.out_dir
    return (pd.read_csv(d / "sessions.csv"), pd.read_csv(d / "plan.csv"), pd.read_csv(d / "requests.csv"),
            json.loads((d / "meta.json").read_text()))


def test_three_arms_share_arrivals_and_session_specs(arms):
    ses = {a: read(o) for a, o in arms.items()}
    plan_b, plan_n, plan_c = ses["burst"][1], ses["noburst"][1], ses["capped"][1]
    cols = ["origin", "idx", "arrival_s", "n_turns", "tool_time_total_s"]
    base = lambda df: df[df["origin"] == "base"].sort_values("idx")[cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(base(plan_b), base(plan_n))
    pd.testing.assert_frame_equal(base(plan_b), base(plan_c))
    burst = lambda df: df[df["origin"] == "burst"].sort_values("idx")[cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(burst(plan_b), burst(plan_c))
    assert len(burst(plan_b)) == 25 and len(burst(plan_n)) == 0
    assert len(plan_b) == len(plan_n) + 25 and len(plan_c) == len(plan_b)
    for arm, (_, _, _, meta) in ses.items():
        assert meta["arm"] == arm and meta["analysis_t_burst_s"] == 1.5 and meta["seeds"] == [0]
    assert ses["capped"][3]["gate_n_cap_resolved"] == 4 and ses["burst"][3]["gate_n_cap_resolved"] is None


def test_capped_arm_never_has_more_than_n_cap_active_sessions(arms):
    s, _, _, meta = read(arms["capped"])
    adm = s[s["t_admit"].notna()]
    assert len(adm) > 40
    peak = 0
    for t in adm["t_admit"]:                                  # active(t) just after each admission, from the log alone
        active = int(((adm["t_admit"] <= t) & (adm["t_end"] > t)).sum())
        peak = max(peak, active)
    assert peak <= 4
    assert peak == 4                                          # the burst saturated the cap (else the test proves nothing)
    g = meta["outcome"]["gate"]
    assert g["n_cap"] == 4 and g["max_active_seen"] == 4 and g["max_active_seen"] <= g["n_cap"]
    # the engine never saw more than n_cap concurrent first-turn+follow-up requests: at most one outstanding per session
    assert meta["outcome"]["max_inflight_seen"] <= 4


def test_gate_waits_are_logged_and_fifo(arms):
    s, _, req, meta = read(arms["capped"])
    adm = s[s["t_admit"].notna()].sort_values("t_admit")
    waited = adm[adm["gate_wait_s"] > 0]
    assert len(waited) >= 10                                  # the 25-session burst has to queue behind 4 slots
    assert np.allclose(adm["t_admit"] - adm["arrival_s"], adm["gate_wait_s"], atol=0.05)   # wait == admit - arrival
    assert adm["gate_wait_s"].max() > 0.1
    # FIFO: sessions are admitted in arrival order
    assert (np.diff(adm["arrival_s"].to_numpy()) >= -1e-9).all()
    g = meta["outcome"]["gate"]
    assert g["n_waited"] == len(waited) or abs(g["n_waited"] - len(waited)) <= 1
    assert g["wait_s_max"] == pytest.approx(adm["gate_wait_s"].max(), abs=1e-6)
    assert g["max_waiting_seen"] >= 5 and g["n_admitted"] == len(adm)
    # a session's first request is sent right after admission, not at arrival: the gate wait is not "scheduler delay"
    first = req[(req["turn"] == 1) & (req["status"] == "ok")].merge(s[["sid", "t_admit", "gate_wait_s"]], on="sid")
    assert (first["t_send"] - first["t_admit"]).between(-1e-6, 0.1).all()
    assert (first["sched_delay_s"] < 0.1).all()
    assert (s[s["t_admit"].isna()]["gate_censored"] == 1).all() and (adm["gate_censored"] == 0).all()


def test_uncapped_arms_log_zero_gate_wait(arms):
    for arm in ("burst", "noburst"):
        s, _, _, meta = read(arms[arm])
        assert (s["gate_wait_s"] == 0).all() and (s["gate_censored"] == 0).all() and s["t_admit"].notna().all()
        assert meta["outcome"]["gate"]["n_cap"] is None and meta["outcome"]["gate"]["n_waited"] == 0
    # ...and the burst genuinely loads the uncapped arm with many more concurrent sessions than the capped one
    peaks = {a: read(arms[a])[3]["outcome"]["max_inflight_seen"] for a in arms}
    assert peaks["burst"] > 4 and peaks["noburst"] < peaks["burst"]


def test_gate_gauges_are_in_the_metrics_log(arms):
    m = pd.read_csv(arms["capped"].out_dir / "metrics.csv")
    gated = m[m["name"] == "agentload:gated_sessions"]["value"]
    system = m[m["name"] == "agentload:sessions_in_system"]["value"]
    assert len(gated) > 5 and gated.max() > 0 and system.max() >= gated.max()
    g0 = pd.read_csv(arms["burst"].out_dir / "metrics.csv")
    assert g0[g0["name"] == "agentload:gated_sessions"]["value"].max() == 0


def test_all_sessions_are_accounted_for_with_the_gate(arms):
    s, plan, req, meta = read(arms["capped"])
    o = meta["outcome"]
    assert len(s) == len(plan) == o["sessions_started"]
    assert o["sessions_never_admitted"] == int(s["t_admit"].isna().sum())
    done = s[s["status"] == "completed"]
    per = req[req["status"] == "ok"].groupby("sid")["turn"].max()
    assert (per.reindex(done["sid"]).to_numpy() == done["n_turns"].to_numpy()).all()


def test_cap_larger_than_the_load_changes_nothing(tmp_path):
    raw = arm_raw("capped", n_cap=500)
    out, _ = run_gen(raw, MockConfig(**FAST), tmp_path)
    s, _, _, meta = read(out)
    assert (s["gate_wait_s"] == 0).all() and meta["outcome"]["gate"]["n_waited"] == 0


def test_capped_run_aborted_while_sessions_are_queued_is_finalized(tmp_path):
    # one slow slot: the cap of 2 leaves most of the burst queued at the gate when the run ends; those sessions are
    # cancelled while waiting (no request ever sent) and must appear as censored, with no leaked slot or exception
    slow = MockConfig(kv_capacity_tokens=10**7, slots=1, fixed_s=0.3, per_uncached_token_s=0, per_completion_token_s=0)
    raw = arm_raw("capped", n_cap=2)
    raw["run"]["duration_s"] = 3.0
    raw["metrics"] = {"enabled": False}
    out, _ = run_gen(raw, slow, tmp_path)
    s, _, _, meta = read(out)
    cens = s[s["gate_censored"] == 1]
    assert len(cens) >= 10 and cens["t_admit"].isna().all() and (cens["status"] == "cancelled").all()
    assert (cens["gate_wait_s"] > 0).all()
    assert meta["status"] == "finished" and meta["outcome"]["sessions_never_admitted"] == len(cens)
    assert meta["outcome"]["gate"]["max_active_seen"] <= 2
