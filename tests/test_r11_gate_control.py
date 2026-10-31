"""Tests of the round-11 simulator gate controller (src/prefixmeta/gate_control.py), the optional lull fields of ArrivalPlan
(src/prefixmeta/workload.py), the probe's control / lull arms (src/prefixmeta/probe.py) and the bundle-3 driver's client-plan bridge
(experiments/r11_predict_rescue.py).

Plan S1 tests: (1) no controller and no lull -> the probe's burst output is bit-identical to golden digests of the r6 burst section taken on the
unmodified code (commit 4d2bba2, before these files changed); (2) a static cap via gate_control equals session_cap_override; (3) a lull with
keep = 1 equals the constant plan; (4) pause conserves sessions; (5) AIMD never goes below c_min."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prefixmeta import probe
from prefixmeta.gate_control import GateControl, GateEngine, rescue_measures, simulate_gate
from prefixmeta.sim import RunSpec, simulate
from prefixmeta.workload import ArrivalPlan, WorkloadParams, build_specs

REPO = Path(__file__).resolve().parent.parent
SPEC = "configs/r6_predict.yaml"
LAM_REF = 0.07153402100919228
LAM165 = 0.11803113466516726            # 1.65 x lambda_ref (300k)

# Golden digests of probe.run_burst on configs/r6_predict.yaml, --set probe.burst.lambda=0.11803113466516726 probe.burst.seeds=[0,1], default
# arms (no_burst, burst, burst_cap 20), workers=1, generated at commit 4d2bba2 with a clean src/ (scratch generator; the digest recipe is
# `_digest` below). Columns whose names contain wall / trend / slope / rise are excluded (np.polyfit's last bit differs between BLAS builds).
GOLDEN = {
    "mixed": {"runs": "64230dd1408efc50c3210b8dba2e7c1cb24075025d6ac16bfbde545aeec2247f",
              "windows": "065cf01ded38e97cfbe20433af6bd332a34e29ee0b3d976fd44f2ba3b2c9c445",
              "qtrace": "cd5be629b6279cabcd3801589ebe7b1bbb96f2a3eb4024b8d88940b754617a63",
              "arms": "6c235aade40f1ce8a41c47f824c297437c721dd7fc1fa653cbc01d09674c1cf8"},
    "separate_prefill_priority": {"runs": "46b294e5c467ddc3f9951c1201e461005572089ac973d5c9da18ff9d4587fb8a",
                                  "windows": "71651c1038d0965b7cb7d909a3eb678e1c224e54a2bb1b86a739ac579f9790b3",
                                  "qtrace": "5484a6f5e935f2f5d8d577dc836912147a32d02ac723633e333650e3d51de1ff",
                                  "arms": "449d84567266b57c59b24bd241fe57c5ce964533c815b3a983155a2283f9ebdd"},
}
COUNT_KEYS = ("n_arrived", "n_sessions_done", "n_in_flight", "n_turns_done", "n_admitted", "n_hits", "final_queue", "final_gate", "max_queue",
              "max_gate", "n_evictions", "evicted_tokens", "n_iterations", "max_running", "max_in_system", "entries_over_cap")


def _digest(df: pd.DataFrame) -> str:
    cols = [c for c in df.columns if not c.startswith("wall") and not any(s in c for s in ("trend", "slope", "rise"))]
    return hashlib.sha256(df[cols].to_csv(index=False).encode()).hexdigest()


@pytest.fixture(scope="module")
def cfg() -> dict:
    return probe.load_probe_config(str(REPO / SPEC), REPO)


def _rs(seed: int, *, lam: float = 1.35 * LAM_REF, burst: int = 200, cap=None, H: float = 8700.0, **plan_kw) -> RunSpec:
    return RunSpec(exp="t", policy="fcfs_lru", seed=seed, horizon_s=H, session_cap_override=cap,
                   plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=burst, burst_t0=1200.0, burst_width_s=60.0, **plan_kw))


# ============================================================================ (1) default path bit-identical to the golden digests
@pytest.mark.parametrize("batching", ["mixed", "separate_prefill_priority"])
def test_probe_burst_without_controller_or_lull_is_bit_identical_to_the_r6_golden_digests(batching):
    c = probe.load_probe_config(str(REPO / SPEC), REPO, [f"engine.batching={batching}", f"probe.burst.lambda={LAM165!r}", "probe.burst.seeds=[0,1]"])
    r = probe.run_burst(c, workers=1)
    _, wins, qts = r.frames
    got = {"runs": _digest(r.runs), "windows": _digest(wins), "qtrace": _digest(qts), "arms": _digest(r.arms)}
    assert got == GOLDEN[batching]
    assert set(probe.burst_arms(probe.probe_section(c, "burst", False))["burst"]) == {"burst_n", "cap"}     # no new keys on default arms


def test_explicit_arms_without_control_keep_the_old_keys_and_specs(cfg):
    sec = dict(probe.probe_section(cfg, "burst", False), arms={"b": {"burst_n": 200}, "c": {"burst_n": 200, "cap": 20}}, seeds=[0])
    arms = probe.burst_arms(sec)
    assert arms == {"b": {"burst_n": 200, "cap": None}, "c": {"burst_n": 200, "cap": 20}}
    for rs in probe.burst_specs(cfg, sec):
        assert "control" not in rs.meta and not rs.plan.has_lull()


# ============================================================================ (2) static cap via gate_control == session_cap_override
def test_static_cap_via_gate_control_equals_session_cap_override(cfg):
    sec = dict(probe.probe_section(cfg, "burst", False), lam_mult=None, seeds=[0, 1],
               arms={"cap": {"burst_n": 200, "cap": 20}, "ctl": {"burst_n": 200, "control": {"mode": "static", "cap": 20}}})
    sec["lambda"] = 1.35 * LAM_REF
    r = probe.run_burst(cfg, sec, workers=1)
    runs, wins, _ = r.frames
    a, b = runs[runs["arm"] == "cap"].reset_index(drop=True), runs[runs["arm"] == "ctl"].reset_index(drop=True)
    for k in COUNT_KEYS:                                   # every event count is identical
        assert (a[k].to_numpy() == b[k].to_numpy()).all(), k
    for k in ("tail_hit_rate", "tail_queue_mean", "tail_busy_frac", "trapped", "burst_recovered"):
        if a[k].dtype == bool:
            assert (a[k] == b[k]).all(), k
        else:
            assert np.allclose(a[k].to_numpy(dtype=float), b[k].to_numpy(dtype=float), rtol=1e-9, atol=1e-12, equal_nan=True), k
    wa = wins[wins["run_id"].isin(runs.index[runs["arm"] == "cap"])].reset_index(drop=True)
    wb = wins[wins["run_id"].isin(runs.index[runs["arm"] == "ctl"])].reset_index(drop=True)
    for k in ("admitted_turns", "hit_rate", "sessions_per_s", "turns_per_s", "first_turn_admits", "gate_max", "queue_max"):
        assert np.array_equal(wa[k].to_numpy(dtype=float), wb[k].to_numpy(dtype=float), equal_nan=True), k
    # time averages agree to rounding only: the 10-s tick clock splits batched decode runs, which reorders float additions (~1e-15)
    for k in ("queue_mean", "gate_mean", "busy_frac", "reserved_mean", "idle_mean", "lat_p50_s"):
        assert np.allclose(wa[k].to_numpy(dtype=float), wb[k].to_numpy(dtype=float), rtol=1e-9, atol=1e-9, equal_nan=True), k
    assert (b["n_ticks"] > 0).all() and (a["n_ticks"] == 0).all()


def test_a_rescue_controller_that_never_engages_has_the_uncontrolled_event_counts(cfg):
    a = simulate(cfg, _rs(0))
    b = simulate_gate(cfg, _rs(0), GateControl(mode="rescue", cap=20, t_on_s=1e18))
    for k in COUNT_KEYS:
        assert a["summary"][k] == b["summary"][k], k
    assert b["gate"]["stats"]["t_engage"] is None and b["gate"]["stats"]["n_pauses"] == 0


def test_no_controller_is_exactly_sim_simulate(cfg):
    a, b = simulate(cfg, _rs(1, H=3000.0)), simulate_gate(cfg, _rs(1, H=3000.0))
    dump = lambda x: json.dumps(x, sort_keys=True, default=float)          # noqa: E731  (NaN-safe comparison)
    assert dump(a["windows"]) == dump(b["windows"]) and dump(a["qtrace"]) == dump(b["qtrace"]) and "gate" not in b


# ============================================================================ (3) lulls
def test_lull_with_keep_one_equals_the_constant_plan(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    base = ArrivalPlan(kind="constant", horizon_s=8700.0, rate=1.65 * LAM_REF, burst_n=200, burst_t0=1200.0, burst_width_s=60.0)
    for sd in (0, 3):
        a = build_specs(wl, base, sd)
        b = build_specs(wl, ArrivalPlan(**{**base.__dict__, "lull_t0": 1800.0, "lull_t1": 4200.0, "lull_keep": 1.0}), sd)
        for f in ("arrival", "n_turns", "tool_off", "tool_flat"):
            assert np.array_equal(getattr(a, f), getattr(b, f)), f
    # and through the probe: an arm with lull keep = 1 gives the burst arm's output bit for bit
    sec = dict(probe.probe_section(cfg, "burst", False), seeds=[0], after_s=3000.0,
               arms={"burst": {"burst_n": 200}, "lull1": {"burst_n": 200, "lull": {"t0": 1800.0, "t1": 4200.0, "keep": 1.0}}})
    sec["lambda"] = 1.65 * LAM_REF
    r = probe.run_burst(cfg, sec, workers=1)
    runs, wins, qts = r.frames
    w = wins.drop(columns=["variant", "run_id"])
    assert w[wins["run_id"] == 0].reset_index(drop=True).equals(w[wins["run_id"] == 1].reset_index(drop=True))


def test_lull_thins_only_base_arrivals_in_the_window_and_keeps_the_others_specs(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    base = ArrivalPlan(kind="constant", horizon_s=8700.0, rate=1.65 * LAM_REF, burst_n=200, burst_t0=1200.0, burst_width_s=60.0)
    a = build_specs(wl, base, 0)
    for keep, lo, hi in ((0.0, 1.0, 1.0), (0.5, 0.35, 0.65)):
        b = build_specs(wl, ArrivalPlan(**{**base.__dict__, "lull_t0": 1800.0, "lull_t1": 4200.0, "lull_keep": keep}), 0)
        ina = (a.arrival >= 1800.0) & (a.arrival < 4200.0)
        inb = (b.arrival >= 1800.0) & (b.arrival < 4200.0)
        assert np.array_equal(a.arrival[~ina], b.arrival[~inb])                     # outside the window nothing changes
        frac_dropped = 1.0 - inb.sum() / ina.sum()
        assert lo <= frac_dropped <= hi
        # every kept session keeps its turn count and tool times (common random numbers)
        pos = {t: i for i, t in enumerate(a.arrival)}
        for j in range(len(b)):
            i = pos[b.arrival[j]]
            assert b.n_turns[j] == a.n_turns[i] and np.array_equal(b.tools_of(j), a.tools_of(i))
    with pytest.raises(ValueError):
        build_specs(wl, ArrivalPlan(**{**base.__dict__, "lull_t0": 4200.0, "lull_t1": 1800.0}), 0)
    with pytest.raises(ValueError):
        build_specs(wl, ArrivalPlan(**{**base.__dict__, "lull_t0": 1800.0, "lull_t1": 4200.0, "lull_keep": 1.5}), 0)


# ============================================================================ (4) pause conserves sessions
class _CheckedEngine(GateEngine):
    """Asserts the session bookkeeping at every controller tick."""

    def _tick(self, tt):
        assert self.n_arrived == self.n_sessions_done + self.in_system + len(self._gate) + self.n_shed
        assert set(self._paused) <= set(self._gate) and self._npaused_front == len(self._paused)
        assert list(self._gate)[: self._npaused_front] == [s for s in self._gate if s in self._paused]     # paused section first
        assert self.in_system >= 0
        super()._tick(tt)


@pytest.mark.parametrize("mult,pause", [(1.35, True), (1.65, True), (1.65, False)])
def test_pause_conserves_sessions_and_every_turn_runs_once(cfg, monkeypatch, mult, pause):
    import prefixmeta.gate_control as gc
    monkeypatch.setattr(gc, "GateEngine", _CheckedEngine)
    ctl = GateControl(mode="rescue", cap=20, t_on_s=1800.0, pause=pause)
    res = simulate_gate(cfg, _rs(0, lam=mult * LAM_REF), ctl)
    g = res["gate"]["stats"]
    assert g["conservation_ok"] and g["t_engage"] == 1800.0
    assert g["n_pauses"] == g["n_resumes"] + g["n_paused_end"]
    if pause:
        assert g["n_pauses"] >= 10 and g["t_release"] is not None and g["n_paused_end"] == 0
    else:
        assert g["n_pauses"] == 0
    turns = defaultdict(list)
    for t, sid, turn, hit, unc in res["gate"]["done"]:
        turns[int(sid)].append(int(turn))
    for sid, ts in turns.items():                     # each session's turns complete once each, in order (a pause never drops or repeats a turn)
        assert ts == list(range(1, len(ts) + 1)), sid
    ev = [e for e in res["gate"]["events"] if e[1] in ("pause", "resume")]
    state = {}
    for t, kind, sid in ev:                           # pause / resume alternate per session, and only while engaged
        assert state.get(sid, "resume") != kind
        state[sid] = kind
        assert t >= 1800.0
    if g["t_release"] is not None:
        rel = g["t_release"]
        assert rel >= 1800.0 + ctl.min_on_s
        assert not [e for e in res["gate"]["events"] if e[1] == "pause" and e[0] > rel]


def test_release_waits_for_hold_and_min_on(cfg):
    ctl = GateControl(mode="rescue", cap=20, t_on_s=1800.0, release_hold_s=300.0, min_on_s=600.0)
    res = simulate_gate(cfg, _rs(2, lam=1.65 * LAM_REF), ctl)
    rel = res["gate"]["stats"]["t_release"]
    tr = pd.DataFrame(res["gate"]["trace"], columns=["t", "in_system", "gate", "paused", "n_wait", "running", "cap", "H", "outstanding"])
    pre = tr[(tr["t"] >= rel - 300.0) & (tr["t"] <= rel)]
    assert (pre["gate"] == 0).all() and (pre["cap"] == 20).all()
    assert (tr[tr["t"] > rel]["cap"] == -1).all() and rel % 10 == 0


def test_shed_drops_arrivals_while_engaged_and_conserves(cfg):
    res = simulate_gate(cfg, _rs(0, lam=1.65 * LAM_REF, H=4000.0), GateControl(mode="rescue", cap=20, t_on_s=1800.0, shed=True))
    g = res["gate"]["stats"]
    assert g["n_shed"] > 0 and g["conservation_ok"] and g["n_gated_arrivals"] == 0


# ============================================================================ (5) AIMD never below c_min
@pytest.mark.parametrize("c_min,beta,mult", [(4, 0.7, 1.65), (15, 0.5, 1.65), (4, 0.5, 2.0)])
def test_aimd_never_goes_below_c_min(cfg, c_min, beta, mult):
    ctl = GateControl(mode="aimd", c_min=c_min, beta=beta, pause=True)
    res = simulate_gate(cfg, _rs(1, lam=mult * LAM_REF), ctl)
    caps = [c for _, c in res["cap_trace"] if c != -1]
    assert caps, "the controller never engaged after a 200-session burst"
    assert min(caps) >= c_min
    tr = pd.DataFrame(res["gate"]["trace"], columns=["t", "in_system", "gate", "paused", "n_wait", "running", "cap", "H", "outstanding"])
    assert ((tr["cap"] == -1) | (tr["cap"] >= c_min)).all()
    assert res["gate"]["stats"]["t_engage"] < 1200.0 + 300.0          # alarms within 300 s of the burst


def test_aimd_does_not_engage_without_a_burst_below_the_edge(cfg):
    res = simulate_gate(cfg, _rs(0, lam=1.65 * LAM_REF, burst=0), GateControl(mode="aimd"))
    assert res["gate"]["stats"]["t_engage"] is None and res["summary"]["n_ticks"] == 869


# ============================================================================ validation and the R1 measures
def test_control_validation():
    with pytest.raises(ValueError):
        GateControl(mode="schedule", cap=20)
    with pytest.raises(ValueError):
        GateControl(mode="rescue")
    with pytest.raises(ValueError):
        GateControl.from_dict({"mode": "rescue", "cap": 20, "t_on": 1800})
    assert GateControl.from_dict(GateControl(mode="aimd").to_json()) == GateControl(mode="aimd")
    with pytest.raises(ValueError):
        probe.burst_arms({"arms": {"x": {"burst_n": 1, "cap": 20, "control": {"mode": "static", "cap": 20}}}})
    with pytest.raises(ValueError):
        probe.burst_arms({"arms": {"x": {"burst_n": 1, "lul": {}}}})


def test_rescue_measures_on_a_rescue_and_a_burst_run(cfg):
    ctl = GateControl(mode="rescue", cap=20, t_on_s=1800.0)
    res = simulate_gate(cfg, _rs(0), ctl)
    m = rescue_measures(res, t_on=1800.0, t_end=8700.0, t_rel=res["gate"]["stats"]["t_release"], uncached_ref=11243.179816372982)
    assert m["VALID"] and m["RELEASED"] and m["POST_GOOD"] and m["RESCUED"] and not m["RELAPSE"]
    assert m["t_rec"] is not None and 1800.0 < m["t_rec"] < m["t_rel"] + 300.0
    obs = simulate_gate(cfg, _rs(0), GateControl(mode="rescue", cap=20, t_on_s=1e18))
    mb = rescue_measures(obs, t_on=1800.0, t_end=8700.0, t_rel=None, uncached_ref=11243.179816372982)
    assert mb["VALID"] and not mb["RELEASED"] and not mb["RESCUED"] and not mb["end_recovered"] and mb["end_hit_all"] < 0.2
    assert mb["STUCK"] and not m["STUCK"]


def test_t_rec_is_the_analysis_t_recovered_definition(cfg):
    """t_rec = the first tick t >= t_on whose window [t, t + 300) has FU-hit > 0.8 and mean outstanding < 20 (analysis/rescue.py
    t_recovered), checked against a direct loop; the descriptive release fields are filled for a rescue run."""
    from prefixmeta.gate_control import _done_array, fu_hit, trace_frame
    res = simulate_gate(cfg, _rs(1), GateControl(mode="rescue", cap=20, t_on_s=1800.0))
    t_rel = res["gate"]["stats"]["t_release"]
    m = rescue_measures(res, t_on=1800.0, t_end=8700.0, t_rel=t_rel, uncached_ref=11243.179816372982, cap=20)
    done, tr = _done_array(res), trace_frame(res)
    want = None
    for t in tr["t"][(tr["t"] >= 1800.0) & (tr["t"] <= 8400.0)]:
        h, n = fu_hit(done, t, t + 300.0)
        w = tr[(tr["t"] >= t) & (tr["t"] < t + 300.0)]
        if n and h > 0.8 and w["outstanding"].mean() < 20.0:
            want = float(t)
            break
    assert want is not None and m["t_rec"] == want
    assert m["fu_pre_rel"] > 0.8 and not m["trapped_at_rel"]
    assert m["t_cap_last_bound"] < t_rel and m["rel_after_last_bound_s"] >= 300.0           # the hold: gate empty >= 300 s
    assert 0.0 <= m["post_rel_frac_in_system_ge_cap"] <= 1.0 and m["post_rel_max_in_system"] >= 1


def test_per_session_costs_add_up_to_the_gate_totals(cfg):
    """Delay per session = admission wait + pauses (open ones to the end); it sums to the engine's totals plus the open parts, and the
    driver's cost summary counts shed sessions as planned and not completed."""
    sys.path.insert(0, str(REPO / "experiments"))
    import r11_predict_rescue as D
    for ctl, H in ((GateControl(mode="rescue", cap=20, t_on_s=1800.0), 8700.0), (GateControl(mode="rescue", cap=20, t_on_s=1800.0), 2500.0),
                   (GateControl(mode="rescue", cap=20, t_on_s=1800.0, shed=True), 8700.0)):
        res = simulate_gate(cfg, _rs(0, H=H), ctl)
        g, ses = res["gate"]["stats"], np.asarray(res["gate"]["sessions"], dtype=float)
        assert len(ses) == res["gate"]["n_arrived"] and int(ses[:, 4].sum()) == g["n_shed"]
        assert int(np.isfinite(ses[:, 2]).sum()) == res["gate"]["n_sessions_done"]
        closed = g["pause_s_total"] + g["gate_wait_s_total"]
        assert ses[:, 3].sum() >= closed - 1e-6
        if H == 8700.0 and not ctl.shed:
            assert g["n_paused_end"] == 0 and g["n_gated_end"] == 0 and ses[:, 3].sum() == pytest.approx(closed, rel=1e-12)
        if H == 2500.0:
            assert g["n_paused_end"] + g["n_gated_end"] > 0 and ses[:, 3].sum() > closed       # open waits counted to the end
        c = D.session_costs(res["gate"]["sessions"], build_specs(WorkloadParams.from_dict(cfg["workload"]), _rs(0, H=H).plan, 0).arrival,
                            1200.0, H)
        assert c["sessions_delayed_gt_60s"] >= c["sessions_delayed_gt_300s"] >= c["sessions_delayed_gt_600s"] >= 0
        assert c["delay_session_h"] == pytest.approx(ses[:, 3].sum() / 3600.0)
        assert 0.0 <= c["cohort_completed_frac"] <= 1.0 and 0.0 < c["completed_frac"] <= 1.0
        if ctl.shed:
            assert g["n_shed"] > 0 and c["cohort_completed_frac"] < 1.0


def test_a_lull_can_end_at_another_cells_release_time():
    sys.path.insert(0, str(REPO / "experiments"))
    import r11_predict_rescue as D
    jobs = [{"cell": "L", "mode": "mixed", "mult": 1.35, "kind": "sim", "seed": s, "protocol": {"duration_s": 8700.0},
             "lull": {"t0": 1800.0, "t1_from": "R", "keep": 0.0}} for s in (0, 1)]
    rows = [{"mode": "mixed", "cell": "R", "mult": 1.35, "kind": "sim", "seed": 0, "t_rel": 4210.0},
            {"mode": "mixed", "cell": "R", "mult": 1.35, "kind": "sim", "seed": 1, "t_rel": None}]
    D.resolve_lull_ends(jobs, rows)
    assert [j["lull"]["t1"] for j in jobs] == [4210.0, 8700.0]                # never released: the lull lasts to the end
    with pytest.raises(ValueError):
        D.resolve_lull_ends([dict(jobs[0], seed=7)], rows)


def test_post_windows_tile_like_the_analysis():
    from prefixmeta.gate_control import post_windows
    w = post_windows(4630.0, 8700.0, 300.0)
    assert w[0] == (4630.0, 4930.0) and w[-1] == (8400.0, 8700.0) and len(w) == 14 and all(b - a == 300.0 for a, b in w)
    assert post_windows(8500.0, 8700.0, 300.0) == [] and post_windows(8100.0, 8700.0, 300.0) == [(8100.0, 8400.0), (8400.0, 8700.0)]


# ============================================================================ the driver's exact client plans
def test_exact_client_plan_reproduces_the_committed_burst_plan():
    sys.path.insert(0, str(REPO / "experiments"))
    import r11_predict_rescue as D
    import yaml
    rcfg = yaml.safe_load((REPO / "configs/r11_predict_rescue.yaml").read_text())["r11_rescue"]
    plan, rate = D.client_plan(rcfg, seed=0, mult=1.35, lambda_ref_spec="prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based",
                               protocol=rcfg["protocol"], burst=True)
    assert rate == 1.35 * LAM_REF
    committed = REPO / "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/20261024-153951/plan.csv"
    if not committed.is_file():
        pytest.skip("committed BURST plan not present")
    m = D.match_committed(D.plan_frame(plan), D.plan_csv_sha256(plan), [("c", "x", pd.read_csv(committed, float_precision="round_trip"))])
    assert m["committed_equal_up_to_tool_ulp"] == "c" and m["max_rel_tool_total_diff"] < 1e-12
    sp = D.specs_from_plan(plan)
    assert len(sp) == len(plan) and int(sp.n_turns.sum()) == sum(p.n_turns for p in plan)
    assert np.array_equal(sp.tools_of(2), np.array(plan[2].tool_times_s))
