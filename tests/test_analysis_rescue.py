"""analysis.rescue: the automatic check-run of a rescue run and the registered verdict (plan R1 / R4), on synthetic run
dirs written in the client-gate builder's format (requests.csv t_ready / pause_s, sessions.csv n_pauses / pause_s_total /
pause_censored, gate_events.csv engage / pause / resume / release / pause_censored, meta gate_mode / gate / outcome.gate).

The fixture is a deterministic toy, not a model of an engine: sessions of K turns with a tool time Z; a request sent inside
a "bad" interval takes LAT_BAD and misses, otherwise LAT_GOOD and (turns >= 2) hits. A rescue run pauses even sessions at
their tool-call boundaries inside the pause window, gates arrivals inside the gate window, and logs engage / release at
the given times."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pytest
import yaml

from analysis import rescue as R
from analysis.load import Run
from analysis.params import load_params
from analysis.throughput import outstanding_events

REPO = Path(__file__).resolve().parent.parent
PARAMS = load_params(REPO / "configs" / "agentload_analysis.yaml")

T_END, T_B, K, Z, P = 8700.0, 1200.0, 10, 5.0, 1000.0
LAM_MISS = 0.035
LAT_GOOD, LAT_BAD = 2.0, 120.0
EPS = 0.01
TOK_REF = 1000.0
GATE_R1 = {"mode": "rescue", "n_cap": 20, "t_on_s": 1800, "pause_at_turns": True, "release_hold_s": 300,
           "min_on_s": 600, "release_check_s": 10}
GATE_R4 = {**GATE_R1, "n_cap": 64, "t_on_s": 2100}
FOREVER = 1e9


# ------------------------------------------------------------------------------------------------ synthetic runs
def make_plan(seed: int, mult: float, burst: bool = True, burst_n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng([seed, int(round(mult * 100))])
    lam = LAM_MISS * mult
    base = np.cumsum(rng.exponential(1.0 / lam, size=int(T_END * lam * 2) + 50))
    base = base[base < T_END]
    b = np.sort(rng.uniform(T_B, T_B + 60.0, size=burst_n))       # drawn after the base: the base is identical without it
    rows = [("base", i, float(a)) for i, a in enumerate(base)]
    if burst:
        rows += [("burst", i, float(a)) for i, a in enumerate(b)]
    rows.sort(key=lambda r: r[2])
    return pd.DataFrame([{"sid": k, "origin": o, "idx": i, "arrival_s": a, "n_turns": K, "tool_time_total_s": Z * (K - 1)}
                         for k, (o, i, a) in enumerate(rows)])


def simulate(plan: pd.DataFrame, *, bad: Sequence[Tuple[float, float]] = (), partial_hits: bool = False,
             rescue: Optional[Dict[str, Any]] = None, rescue_columns: bool = False):
    def is_bad(t: float) -> bool:
        return any(a <= t < b for a, b in bad)

    req, ses, ev = [], [], []
    rid = 0
    for row in plan.itertuples(index=False):
        sid, arr = int(row.sid), float(row.arrival_s)
        gw, t_admit = 0.0, arr
        if rescue and rescue["t_on"] <= arr < rescue["gate_until"]:
            gw, t_admit = rescue["gate_wait"], arr + rescue["gate_wait"]
        n_p, p_tot, cens = 0, 0.0, 0
        status, t_end, done, t_first = "completed", None, 0, None
        if t_admit >= T_END:
            ses.append({"sid": sid, "origin": row.origin, "idx": row.idx, "arrival_s": arr, "n_turns": K, "t_first_send": "",
                        "t_end": T_END + EPS, "turns_completed": 0, "status": "cancelled", "t_admit": "",
                        "gate_wait_s": T_END + EPS - arr, "gate_censored": 1, "n_pauses": 0, "pause_s_total": 0.0,
                        "pause_censored": 0})
            continue
        t_prev = None
        for turn in range(1, K + 1):
            t_ready = t_admit if turn == 1 else t_prev + Z
            if t_ready >= T_END:
                status, t_end = "cancelled", T_END + EPS
                break
            pause = 0.0
            if (rescue and turn >= 2 and sid % 2 == 0 and rescue["pause_from"] <= t_ready < rescue["pause_until"]):
                pause = rescue["pause_s"]
                ev.append({"t_s": t_ready, "event": "pause", "sid": sid, "pause_s": ""})
                if t_ready + pause >= T_END:
                    n_p += 1
                    p_tot += T_END + EPS - t_ready
                    cens = 1
                    ev.append({"t_s": T_END + EPS, "event": "pause_censored", "sid": sid, "pause_s": T_END + EPS - t_ready})
                    status, t_end = "cancelled", T_END + EPS
                    break
                n_p += 1
                p_tot += pause
                ev.append({"t_s": t_ready + pause, "event": "resume", "sid": sid, "pause_s": pause})
            t_send = t_ready + pause
            t_first = t_send if t_first is None else t_first
            lat = LAT_BAD if is_bad(t_send) else LAT_GOOD
            t_c = t_send + lat
            rid += 1
            base = {"req_id": rid, "sid": sid, "origin": row.origin, "turn": turn, "n_turns": K, "t_planned": t_ready,
                    "t_send": t_send, "prompt_tokens_client": P, "t_ready": t_ready, "pause_s": pause}
            if t_c >= T_END:
                req.append({**base, "t_headers": "", "t_complete": T_END + EPS, "latency_s": T_END + EPS - t_send,
                            "status": "cancelled", "prompt_tokens": np.nan, "completion_tokens": np.nan,
                            "cached_tokens": np.nan})
                status, t_end = "cancelled", T_END + EPS
                break
            hit = turn >= 2 and not is_bad(t_c) and (not partial_hits or (sid + turn) % 4 != 0)
            req.append({**base, "t_headers": t_c, "t_complete": t_c, "latency_s": lat, "status": "ok", "prompt_tokens": P,
                        "completion_tokens": 100, "cached_tokens": 0.9 * P if hit else 0.0})
            done, t_prev = turn, t_c
        if status == "completed":
            t_end = t_prev
        ses.append({"sid": sid, "origin": row.origin, "idx": row.idx, "arrival_s": arr, "n_turns": K,
                    "t_first_send": t_first, "t_end": t_end, "turns_completed": done, "status": status, "t_admit": t_admit,
                    "gate_wait_s": gw, "gate_censored": 0, "n_pauses": n_p, "pause_s_total": p_tot, "pause_censored": cens})
    req_df, ses_df = pd.DataFrame(req), pd.DataFrame(ses)
    if not rescue_columns:
        req_df = req_df.drop(columns=["t_ready", "pause_s"])
        ses_df = ses_df.drop(columns=["n_pauses", "pause_s_total", "pause_censored"])
    return req_df, ses_df, ev


def write_plan(path: Path, plan: pd.DataFrame) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sid", "origin", "idx", "arrival_s", "n_turns", "tool_time_total_s"])
        w.writeheader()
        for r in plan.to_dict("records"):
            w.writerow(r)


def make_run(root: Path, name: str, *, arm: str, seed: int = 0, mult: float = 1.35, label: Optional[str] = None,
             bad: Optional[Sequence[Tuple[float, float]]] = None, gate: Optional[Dict[str, Any]] = None,
             t_rel: Optional[float] = 3600.0, cure: float = 3000.0, pause_window: Tuple[float, float] = (None, None),
             pause_s: float = 50.0, gate_until: Optional[float] = None, gate_wait: float = 30.0, partial_hits: bool = False,
             burst_n: int = 200, tok_ref: float = TOK_REF, prereg_sha: str = "a" * 64, plan_seed: Optional[int] = None,
             with_events: bool = True, engage_at: Optional[float] = None, engage: bool = True,
             cfg_edit=None, meta_edit=None, ses_edit=None, ev_edit=None, req_edit=None, extra_events=()) -> Path:
    """One synthetic run dir. arm: rescue | burst | noburst | capped."""
    if arm == "rescue":
        gate = dict(GATE_R1 if gate is None else gate)
        label = label or "sglang-fcfs-r1-rescue"
    else:
        label = label or "sglang-fcfs-r1"
    plan = make_plan(seed if plan_seed is None else plan_seed, mult, burst=(arm != "noburst"), burst_n=burst_n)
    if bad is None:
        bad = [] if arm == "noburst" else ([(T_B + 30.0, cure)] if arm == "rescue" else [(T_B + 30.0, FOREVER)])
    resc = None
    if arm == "rescue":
        t_on = float(gate["t_on_s"])
        p0, p1 = pause_window
        resc = {"t_on": t_on, "pause_from": t_on if p0 is None else p0,
                "pause_until": (t_on + 800.0) if p1 is None else p1, "pause_s": pause_s,
                "gate_until": (t_on + 800.0) if gate_until is None else gate_until, "gate_wait": gate_wait}
    req, ses, ev = simulate(plan, bad=bad, partial_hits=partial_hits, rescue=resc, rescue_columns=(arm == "rescue"))
    d = root / name
    d.mkdir(parents=True)
    write_plan(d / "plan.csv", plan)
    n_cap = None
    if arm == "rescue":
        n_cap = int(gate["n_cap"])
        t_on = float(gate["t_on_s"])
        t_eng = t_on if engage_at is None else engage_at
        adm = pd.to_numeric(ses["t_admit"], errors="coerce").to_numpy(dtype=float)
        te = ses["t_end"].to_numpy(dtype=float)
        active = int(np.sum((adm <= t_eng) & ~(te <= t_eng)))
        rows = []
        if engage:
            rows.append({"t_s": t_eng, "event": "engage", "sid": "", "cap": n_cap, "active": active, "waiting": 0,
                         "paused": 0})
        if t_rel is not None:
            rows.append({"t_s": t_rel, "event": "release", "sid": "", "cap": "", "active": 10, "waiting": 0, "paused": 0})
        # the counts after each event, as the client logs them (a toy: pause rows at the cap with one paused session)
        rows += [{"active": n_cap, "waiting": 0, "paused": int(e["event"] == "pause"), **e, "cap": n_cap} for e in ev]
        rows += list(extra_events)
        evdf = pd.DataFrame(rows, columns=["t_s", "event", "sid", "cap", "active", "waiting", "paused", "pause_s"])
        evdf = evdf.sort_values("t_s", kind="stable")
        if ev_edit:
            evdf = ev_edit(evdf)
        if with_events:
            evdf.to_csv(d / "gate_events.csv", index=False)
    elif arm == "capped":
        n_cap = 20
        gate = {"n_cap": 20}
    else:
        gate = {"n_cap": None}
    if ses_edit:
        ses = ses_edit(ses)
    if req_edit:
        req = req_edit(req, ses)
    req.to_csv(d / "requests.csv", index=False)
    ses.to_csv(d / "sessions.csv", index=False)
    lam = LAM_MISS * mult
    cfg = {"research_question": "synthetic",
           "server": {"base_url": "http://127.0.0.1:1", "model": "m"},
           "workload": {"prompt_mode": "tokens", "initial_context_tokens": 2000, "mean_turns": 15, "max_turns": 60,
                        "tool_time_mean_s": Z, "content_salt": 1, "output_feedback": "server"},
           "arrivals": {"kind": "constant", "rate_mult": mult, "lambda_ref": "x/calibration.json:lambda_miss_turns_based",
                        "uncached_tokens_ref": "x/calibration.json:all_miss_uncached_tokens_per_s",
                        "burst": None if arm == "noburst" else {"n": burst_n, "t_s": T_B, "width_s": 60},
                        "analysis_t_burst_s": T_B},
           "gate": gate, "run": {"duration_s": T_END, "seed": seed, "max_inflight": 4000},
           "meta": {"hardware": "synthetic GPU", "engine_label": label, "arm": arm, "notes": "E2 burst",
                    "prereg_sha256": prereg_sha, "prereg_file": "configs/x.yaml"},
           "output": {"root": "results", "name": "agentload_e2_burst"}}
    if cfg_edit:
        cfg_edit(cfg)
    st = ses["status"]
    outcome = {"t_end_s": T_END, "abort_reason": None, "sessions_planned": len(plan), "sessions_started": len(ses),
               "sessions_completed": int((st == "completed").sum()), "sessions_failed": int((st == "failed").sum()),
               "sessions_cancelled": int((st == "cancelled").sum())}
    meta = {"engine_label": label, "seeds": [seed], "arm": arm, "n_sessions_planned": len(plan),
            "resolved_rate_sessions_per_s": lam, "lambda_ref_resolved": LAM_MISS, "uncached_tokens_ref_resolved": tok_ref,
            "gate_n_cap_resolved": n_cap, "hardware": "synthetic GPU", "t0_unix": 2_000_000_000.0,
            "prereg_sha256": prereg_sha, "start_state_verified": True, "status": "finished", "outcome": outcome}
    if arm == "rescue":
        meta["gate_mode"] = "rescue"
        meta["gate"] = {**{k: v for k, v in gate.items() if k != "n_cap"}, "n_cap_configured": gate["n_cap"],
                        "n_cap_resolved": n_cap}
        outcome["gate"] = {"mode": "rescue", "t_engage": float(gate["t_on_s"]) if engage else None, "t_release": t_rel,
                           "released": t_rel is not None, "n_pauses": sum(e["event"] == "pause" for e in ev),
                           "n_resumes": sum(e["event"] == "resume" for e in ev),
                           "n_sessions_paused_at_end": sum(e["event"] == "pause_censored" for e in ev),
                           "active_after_end": 0, "queued_after_end": 0, "gate_control_error": None}
    if meta_edit:
        meta_edit(meta)
    (d / "meta.json").write_text(json.dumps(meta))
    (d / "config_effective.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return d


def e2_file(root: Path, gate: Dict[str, Any] = GATE_R1, name: str = "e2.yaml", duration: float = T_END,
            t_burst: float = T_B) -> Path:
    p = root / name
    p.write_text(yaml.safe_dump({"arrivals": {"kind": "constant", "burst": {"n": 200, "t_s": t_burst, "width_s": 60},
                                              "analysis_t_burst_s": t_burst},
                                 "gate": dict(gate), "run": {"duration_s": duration}}, sort_keys=False))
    return p


def checks(rep: Dict[str, Any]) -> Dict[str, bool]:
    return {c["name"]: c["ok"] for c in rep["checks"]}


@pytest.fixture(scope="module")
def std(tmp_path_factory):
    """The R1 set: rescue runs RESCUED at every (rate, seed) and the committed-style BURST / NOBURST controls."""
    root = tmp_path_factory.mktemp("std")
    out: Dict[str, Path] = {"root": root}
    for m in (1.35, 1.65):
        for s in (0, 1, 2):
            out[f"rescue_{m}_{s}"] = make_run(root, f"rescue_{m}_{s}", arm="rescue", seed=s, mult=m)
            out[f"burst_{m}_{s}"] = make_run(root, f"burst_{m}_{s}", arm="burst", seed=s, mult=m, prereg_sha="b" * 64)
            out[f"noburst_{m}_{s}"] = make_run(root, f"noburst_{m}_{s}", arm="noburst", seed=s, mult=m, prereg_sha="b" * 64)
    out["e2"] = e2_file(root)
    return out


def controls(std, mults=(1.35, 1.65), seeds=(0, 1, 2)):
    return [str(std[f"{a}_{m}_{s}"]) for m in mults for s in seeds for a in ("burst", "noburst")]


def rescues(std, mults=(1.35, 1.65), seeds=(0, 1, 2)):
    return [str(std[f"rescue_{m}_{s}"]) for m in mults for s in seeds]


def evaluate(d: Path, prof: str = "r1"):
    run, ev = R.load_rescue_run(d)
    return R.evaluate_rescue_run(run, ev, R.PROFILES[prof], PARAMS)


# ------------------------------------------------------------------------------------------------ building blocks
def test_post_windows_tile_from_the_start_and_cover_the_remainder_with_a_window_ending_at_the_horizon():
    assert R.post_windows(3900.0, 8700.0, 300.0) == [(3900.0 + 300 * k, 4200.0 + 300 * k) for k in range(16)]
    w = R.post_windows(4000.0, 8700.0, 300.0)
    assert w[0] == (4000.0, 4300.0) and w[-1] == (8400.0, 8700.0) and len(w) == 16
    assert all(abs((b - a) - 300.0) < 1e-9 for a, b in w)
    assert R.post_windows(8500.0, 8700.0, 300.0) == []


def test_outstanding_without_pauses_is_exactly_the_throughput_definition(std):
    run, ev = R.load_rescue_run(std["burst_1.35_0"])
    st = R.outstanding_step(run, R.pause_intervals(run, None))
    t, v = outstanding_events(run)
    assert np.array_equal(st.t, t) and np.array_equal(st.v, v)


def _tiny_run(n_paused_open: int, hits: bool = True) -> Tuple[Run, pd.DataFrame]:
    """40 sessions; requests completing in the last 300 s hit; ``n_paused_open`` sessions are paused from 8300 to the end."""
    t = np.linspace(8401.0, 8690.0, 200)
    req = pd.DataFrame({"sid": np.arange(200) % 40, "turn": 2, "n_turns": 3, "t_send": t - 1.0, "t_complete": t,
                        "latency_s": 1.0, "status": "ok", "prompt_tokens": P, "prompt_tokens_client": P,
                        "cached_tokens": 0.9 * P if hits else 0.0, "t_ready": t - 1.0, "pause_s": 0.0})
    ses = pd.DataFrame({"sid": np.arange(40), "arrival_s": 8000.0, "t_end": T_END + EPS, "status": "cancelled",
                        "t_admit": 8000.0, "gate_wait_s": 0.0, "n_turns": 3})
    ev = pd.DataFrame({"t_s": [8300.0] * n_paused_open, "event": ["pause"] * n_paused_open,
                       "sid": np.arange(n_paused_open, dtype=float), "cap": 20.0})
    run = Run(dir=Path("/nonexistent/tiny"), meta={"engine_label": "x", "seeds": [0]}, cfg={"run": {"duration_s": T_END}},
              requests=req, sessions=ses, metrics=pd.DataFrame(), t_end_s=T_END)
    return run, ev


def test_open_pauses_are_outstanding_until_the_session_ends_and_break_the_recovered_predicate():
    run, ev = _tiny_run(30)
    pz = R.pause_intervals(run, ev)
    assert len(pz) == 30 and set(pz["source"]) == {"open"} and (pz["t1"] == T_END + EPS).all()
    with_p = R.outstanding_step(run, pz)
    without = R.outstanding_step(run, R.pause_intervals(run, None))
    assert with_p.mean(8400.0, 8700.0) - without.mean(8400.0, 8700.0) == pytest.approx(30.0)
    assert R.recovered_end(run, PARAMS, without)["recovered"] is True        # the hits and the in-flight count are good ...
    assert R.recovered_end(run, PARAMS, with_p)["recovered"] is False        # ... but 30 paused sessions are outstanding


def test_request_pauses_are_outstanding_over_t_ready_to_t_send(std):
    run, ev = R.load_rescue_run(std["rescue_1.35_0"])
    pz = R.pause_intervals(run, ev)
    assert len(pz) > 10 and (pz["source"] == "request").all()
    assert np.allclose(pz["t1"] - pz["t0"], 50.0)
    base = R.outstanding_step(run, pz.iloc[0:0])
    full = R.outstanding_step(run, pz)
    assert full.mean(1800.0, 2700.0) > base.mean(1800.0, 2700.0)
    assert full.mean(4000.0, 8700.0) == pytest.approx(base.mean(4000.0, 8700.0))


def test_gate_events_reader_accepts_aliases_and_rejects_a_file_without_events(tmp_path):
    d = tmp_path / "r"
    d.mkdir()
    (d / "gate_events.csv").write_text("time_s,kind,session\n1800,ENGAGE,\n1810,pause,4\n")
    ev = R.read_gate_events(d)
    assert list(ev["event"]) == ["engage", "pause"] and ev["sid"].iloc[1] == 4
    (d / "gate_events.csv").write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        R.read_gate_events(d)
    assert R.read_gate_events(tmp_path) is None


# ------------------------------------------------------------------------------------------------ per-run rule
def test_a_trap_drained_released_and_good_afterwards_is_rescued(std):
    rec, wins = evaluate(std["rescue_1.35_0"])
    assert rec["outcome"] == "RESCUED" and rec["rescued"]
    assert rec["valid"] and rec["valid_fu_hit"] == 0.0 and rec["outstanding_at_t_on"] > 50
    assert rec["t_engage"] == 1800.0 and rec["t_release"] == 3600.0 and rec["released_by_deadline"]
    assert rec["post_t0"] == 3900.0 and rec["post_n_windows"] == 16 == len(wins)
    assert rec["post_windows_ok"] and rec["post_fu_hit"] == 1.0 and rec["post_uncached_rel"] < 0.5
    assert rec["recovered_end"] and rec["relapse"] is False
    assert 2900.0 <= rec["t_recovered"] <= 3300.0
    assert rec["max_paused"] > 0 and rec["max_gated"] > 0
    # descriptive: the cap last held a session back at the end of the pause / gate windows, long before the release
    assert 2600.0 < rec["t_cap_last_binding"] <= 2700.0 and rec["release_after_last_binding_s"] == pytest.approx(
        3600.0 - rec["t_cap_last_binding"])
    assert 0.0 <= rec["post_release_frac_active_ge_cap"] <= 1.0 and rec["post_release_max_active"] >= 0
    assert rec["sessions_failed"] == 0 and rec["requests_error"] == 0


def test_valid_needs_the_trap_at_engage(tmp_path):
    rec, _ = evaluate(make_run(tmp_path, "notrap", arm="rescue", bad=[]))
    assert rec["outcome"] == "INVALID" and not rec["valid_hit_ok"] and not rec["rescued"]
    rec, _ = evaluate(make_run(tmp_path, "shallow", arm="rescue", burst_n=10))       # hit 0, but too few outstanding
    assert rec["valid_hit_ok"] and not rec["valid_outstanding_ok"] and rec["outcome"] == "INVALID"


def test_a_release_after_7200_s_or_none_fails_rule_b(tmp_path):
    rec, _ = evaluate(make_run(tmp_path, "late", arm="rescue", t_rel=7300.0))
    assert rec["released"] and not rec["released_by_deadline"] and rec["post_good"] and rec["outcome"] == "RELEASED_LATE"
    rec, _ = evaluate(make_run(tmp_path, "never", arm="rescue", t_rel=None))
    assert not rec["released"] and rec["relapse"] is None and rec["outcome"] == "NOT_RELEASED"


def test_a_window_back_in_the_trap_after_release_is_a_relapse(tmp_path):
    rec, _ = evaluate(make_run(tmp_path, "relapse", arm="rescue", bad=[(T_B + 30.0, 3000.0), (6000.0, 6700.0)]))
    assert rec["relapse"] and rec["post_min_window_fu_hit"] < 0.2 and not rec["post_good"] and rec["outcome"] == "RELAPSE"


def test_post_good_needs_the_whole_interval_above_0_8_and_the_token_rate_below_half_the_all_miss_rate(tmp_path):
    rec, _ = evaluate(make_run(tmp_path, "partial", arm="rescue", partial_hits=True))      # follow-up hits 3 in 4
    assert rec["post_windows_ok"] and rec["post_fu_hit"] == pytest.approx(0.75, abs=0.02)
    assert not rec["post_interval_ok"] and rec["outcome"] == "NOT_GOOD_AFTER_RELEASE"
    rec, _ = evaluate(make_run(tmp_path, "tokens", arm="rescue", tok_ref=150.0))
    assert rec["post_interval_ok"] and rec["post_uncached_rel"] > 0.5 and not rec["post_uncached_ok"]
    assert not rec["rescued"]


def test_burst_controls_that_stay_at_hit_zero_are_stuck_and_a_recovering_one_is_not(std, tmp_path):
    run = R.load_rescue_run(std["burst_1.35_0"])[0]
    assert R.burst_stuck(run, R.PROFILES["r1"], PARAMS)["stuck"] is True
    run = R.load_rescue_run(make_run(tmp_path, "bcure", arm="burst", bad=[(T_B + 30.0, 2500.0)]))[0]
    assert R.burst_stuck(run, R.PROFILES["r1"], PARAMS)["stuck"] is False


# ------------------------------------------------------------------------------------------------ verdict
def test_all_rescued_with_stuck_controls_passes_at_both_test_points(std):
    doc, frames = R.verdict(rescues(std), controls(std), PARAMS, e2_cfg=yaml.safe_load(std["e2"].read_text()))
    assert doc["profile"] == "r1" and not doc["rejected_runs"]
    for c in doc["cells"]:
        assert c["n_rescued"] == 3 and c["burst_controls_stuck_all"] and c["meets_valid_pairing"], c
    assert doc["family"]["all_rates_pass"] and not doc["family"]["refuted"]
    assert doc["family"]["verdict"].startswith("PASS") and "both test points" in doc["family"]["verdict"]
    assert doc["decisive"] is False                                          # no --prereg
    runs = frames["rescue_runs"]
    assert len(runs) == 6 and set(runs["outcome"]) == {"RESCUED"}
    assert len(frames["rescue_windows"]) == 6 * 16
    pairs = frames["rescue_pairs"]
    assert (pairs["burst_fu_hit_cmp"] == 0.0).all() and (pairs["rescue_fu_hit_cmp"] == 1.0).all()
    assert (pairs["rescue_fu_hit_valid_window"] == pairs["burst_fu_hit_valid_window"]).all()   # identical before t_on
    assert set(frames["rescue_trace"]["arm"]) == {"rescue", "burst", "noburst"}


def test_user_costs_sit_next_to_the_controls(std):
    _, frames = R.verdict(rescues(std, (1.35,), (0,)), controls(std, (1.35,), (0,)), PARAMS)
    c = frames["rescue_costs"].set_index("arm")
    assert c.loc["rescue", "pause_hours"] > 0 and c.loc["rescue", "sessions_paused"] > 0
    assert c.loc["rescue", "gate_wait_hours"] > 0 and c.loc["rescue", "sessions_gated"] > 0
    assert c.loc["burst", "pause_hours"] == 0 and c.loc["burst", "gate_wait_hours"] == 0
    assert c.loc["noburst", "completed_frac"] > c.loc["burst", "completed_frac"]
    assert c.loc["rescue", "sessions_completed"] > c.loc["burst", "sessions_completed"]
    assert c.loc["burst", "request_wait_hours"] > c.loc["rescue", "wait_hours_total"]
    p = frames["rescue_pairs"].iloc[0]
    assert p["rescue_pause_hours"] == pytest.approx(c.loc["rescue", "pause_hours"])
    run = R.load_rescue_run(std["rescue_1.35_0"])[0]
    assert c.loc["rescue", "pause_hours"] == pytest.approx(run.sessions["pause_s_total"].sum() / 3600.0)


def test_two_of_three_rescued_passes_a_cell_and_one_does_not(std, tmp_path):
    bad2 = [(T_B + 30.0, 3000.0), (6000.0, 6700.0)]
    r = [str(std["rescue_1.35_0"]), str(std["rescue_1.35_1"]),
         str(make_run(tmp_path, "r135_2", arm="rescue", seed=2, mult=1.35, bad=bad2)),
         str(std["rescue_1.65_0"]),
         str(make_run(tmp_path, "r165_1", arm="rescue", seed=1, mult=1.65, t_rel=None)),
         str(make_run(tmp_path, "r165_2", arm="rescue", seed=2, mult=1.65, bad=[]))]
    doc, _ = R.verdict(r, controls(std), PARAMS)
    c135, c165 = doc["cells"]
    assert c135["n_rescued"] == 2 and c135["meets_valid_pairing"] and c135["n_relapse"] == 1
    assert c165["n_rescued"] == 1 and not c165["meets"] and c165["n_invalid"] == 1
    fam = doc["family"]
    assert fam["primary_rate_pass"] and not fam["all_rates_pass"] and not fam["refuted"]
    assert fam["n_relapse"] == 1 and fam["n_not_released_by_deadline"] == 1
    assert fam["verdict"] == "PASS: " + R.PROFILES["r1"]["claims"]["primary"]


def test_two_relapses_or_two_unreleased_runs_refute(std, tmp_path):
    bad2 = [(T_B + 30.0, 3000.0), (6000.0, 6700.0)]
    r = rescues(std, (1.35,)) + [str(make_run(tmp_path, f"rl{s}", arm="rescue", seed=s, mult=1.65, bad=bad2))
                                 for s in (0, 1)] + [str(std["rescue_1.65_2"])]
    doc, _ = R.verdict(r, controls(std), PARAMS)
    assert doc["family"]["refuted_by_relapse"] and doc["family"]["verdict"].startswith("REFUTED")
    assert "takes precedence over PASS" in doc["family"]["verdict"]           # REFUTED wins; 1.35 x still meets PASS
    assert doc["family"]["refuted_takes_precedence"] and doc["family"]["cells_meeting_pass"] == [1.35]
    r = rescues(std, (1.35,)) + [str(make_run(tmp_path, f"nr{s}", arm="rescue", seed=s, mult=1.65, t_rel=7400.0))
                                 for s in (0, 1)] + [str(std["rescue_1.65_2"])]
    doc, _ = R.verdict(r, controls(std), PARAMS)
    assert doc["family"]["refuted_by_unreleased"] and not doc["family"]["refuted_by_relapse"]
    assert doc["family"]["n_not_released_by_deadline"] == 2


def test_r1_and_r4_need_stuck_controls(std, tmp_path):
    ctl = [str(make_run(tmp_path, f"b{s}", arm="burst", seed=s, bad=[(T_B + 30.0, 2500.0)])) for s in (0, 1, 2)]
    ctl += [str(std[f"noburst_1.35_{s}"]) for s in (0, 1, 2)]
    doc, _ = R.verdict(rescues(std, (1.35,)), ctl, PARAMS)
    c = doc["cells"][0]
    assert c["n_rescued"] == 3 and not c["burst_controls_stuck_all"] and not c["meets"]
    assert c["burst_controls_not_stuck"] == [0, 1, 2] and "not stuck" in c["diagnosis"]
    # R4: same structure at the native registration (4.0 x, cap 64, t_on 2100), with recovering BURST controls
    kw = dict(mult=4.0, gate=GATE_R4, label="sglang-fcfs-r1-rescue-native", cure=3200.0, t_rel=3800.0)
    r4 = [str(make_run(tmp_path, f"n{s}", arm="rescue", seed=s, **kw)) for s in (0, 1, 2)]
    c4 = [str(make_run(tmp_path, f"nb{s}", arm="burst", seed=s, mult=4.0, label="sglang-fcfs-r1-native",
                       bad=[(T_B + 30.0, 2900.0)])) for s in (0, 1, 2)]
    c4 += [str(make_run(tmp_path, f"nn{s}", arm="noburst", seed=s, mult=4.0, label="sglang-fcfs-r1-native"))
           for s in (0, 1, 2)]
    doc, frames = R.verdict(r4, c4, PARAMS, e2_cfg={"gate": GATE_R4, "run": {"duration_s": T_END}})
    assert doc["profile"] == "r4"
    assert (frames["rescue_runs"]["t_on_registered"] == 2100.0).all()
    c = doc["cells"][0]
    assert c["n_rescued"] == 3 and not c["burst_controls_stuck_all"] and not c["meets_valid_pairing"], c
    assert c["require_controls_stuck"] and doc["family"]["verdict"] == "NOT SHOWN"
    # with stuck native controls the same rescue runs pass
    c4s = [str(make_run(tmp_path, f"nbs{s}", arm="burst", seed=s, mult=4.0, label="sglang-fcfs-r1-native"))
           for s in (0, 1, 2)] + c4[3:]
    doc, _ = R.verdict(r4, c4s, PARAMS, e2_cfg={"gate": GATE_R4, "run": {"duration_s": T_END}})
    assert doc["cells"][0]["meets_valid_pairing"] and doc["family"]["verdict"].startswith("PASS")


def test_a_missing_seed_counts_against_pass(std):
    doc, _ = R.verdict([str(std["rescue_1.35_0"])], controls(std, (1.35,)), PARAMS)
    c = doc["cells"][0]
    assert c["n_missing"] == 2 and not c["complete"] and not c["meets"]
    assert "2 seed(s) missing" in c["diagnosis"] and "not stuck" not in c["diagnosis"]
    assert doc["cells"][1]["n_present"] == 0 and not doc["family"]["complete"]
    assert doc["family"]["verdict"] == "NOT SHOWN"
    # two of the three registered seeds RESCUED with stuck controls: PASS, flagged incomplete
    doc, _ = R.verdict(rescues(std, (1.35,), (0, 2)), controls(std, (1.35,)), PARAMS)
    c = doc["cells"][0]
    assert c["meets_valid_pairing"] and not c["complete"] and "1 registered seed(s) missing" in c["diagnosis"]
    assert doc["family"]["primary_rate_pass"] and not doc["family"]["complete"]


def test_pairing_problems_block_a_cell_but_cross_commit_fields_may_differ(std, tmp_path):
    # the rescue and control prereg sha256 differ in std (a vs b) and the cell is fine: the allow-list
    doc, _ = R.verdict(rescues(std, (1.35,)), controls(std, (1.35,)), PARAMS)
    assert doc["cells"][0]["meets_valid_pairing"]
    # a BURST control drawn from another plan, and a NOBURST control with another workload
    ctl = [str(make_run(tmp_path, "b0", arm="burst", seed=0, plan_seed=7)), str(std["noburst_1.35_0"]),
           str(std["burst_1.35_1"]),
           str(make_run(tmp_path, "nb1", arm="noburst", seed=1, cfg_edit=lambda c: c["workload"].update(mean_turns=9))),
           str(std["burst_1.35_2"]), str(std["noburst_1.35_2"])]
    doc, _ = R.verdict(rescues(std, (1.35,)), ctl, PARAMS)
    c = doc["cells"][0]
    assert c["meets"] and not c["meets_valid_pairing"]
    assert any("plan.csv sha256 differs" in x for x in c["problems"]["0"])
    assert any("workload.mean_turns" in x for x in c["problems"]["1"])
    assert "2" not in c["problems"]


def test_the_e2_config_gate_block_is_checked(std):
    e2 = {"gate": {**GATE_R1, "release_hold_s": 120}, "run": {"duration_s": T_END}}
    doc, _ = R.verdict(rescues(std, (1.35,)), controls(std, (1.35,)), PARAMS, e2_cfg=e2)
    c = doc["cells"][0]
    assert c["meets"] and not c["meets_valid_pairing"]
    assert any("gate.release_hold_s" in x for x in c["problems"]["0"])


def test_runs_that_are_not_registered_rescue_runs_are_rejected_not_relabelled(std, tmp_path):
    capped = make_run(tmp_path, "capped", arm="capped")
    other = make_run(tmp_path, "other", arm="rescue", mult=1.5)
    doc, frames = R.verdict(rescues(std, (1.35,)) + [str(capped), str(other)], controls(std, (1.35,)), PARAMS,
                            profile="r1")
    rej = {Path(x["run_dir"]).name: x["reasons"] for x in doc["rejected_runs"]}
    assert set(rej) == {"capped", "other"}
    assert any("meta.arm is 'capped'" in s for s in rej["capped"]) and any("rate_mult 1.5" in s for s in rej["other"])
    assert len(frames["rescue_runs"]) == 3
    with pytest.raises(ValueError):
        R.verdict([str(capped)], controls(std, (1.35,)), PARAMS)               # auto: label maps to no profile


def test_registration_blockers_bind_runs_to_the_rescue_registration(std):
    run = R.load_rescue_run(std["rescue_1.35_0"])[0]
    pr = {"inputs": {"engine_cell_label": "sglang-fcfs-r1-rescue"}, "lambda_selection": {"lambda_mults": [1.35, 1.65]},
          "protocol": {"duration_s": T_END, "t_burst_s": T_B, "burst_n": 200, "burst_width_s": 60, "gate": dict(GATE_R1)},
          "measured": {"lambda_ref": LAM_MISS, "all_miss_uncached_tokens_per_s": TOK_REF, "hardware": "synthetic GPU",
                       "n_cap": 20}}
    prov = {"sha256": "a" * 64, "git_last_commit_unix": 1_900_000_000.0}
    assert R.prereg_mod.registered_mults(pr) == [1.35, 1.65]
    assert R.registration_blockers(pr, prov, run) == []
    pr_m = {**pr, "lambda_selection": {"lambda_mults": [1.35]}}
    run165 = R.load_rescue_run(std["rescue_1.65_0"])[0]
    assert any("not in the registered lambda_mults" in b for b in R.registration_blockers(pr_m, prov, run165))
    bl = R.registration_blockers(pr, {**prov, "sha256": "c" * 64, "git_last_commit_unix": 2_100_000_000.0}, run)
    assert any("not bound" in b for b in bl) and any("does not predate" in b for b in bl)
    pr2 = {**pr, "protocol": {**pr["protocol"], "gate": {**GATE_R1, "t_on_s": 2400}}}
    assert any("gate.t_on_s" in b for b in R.registration_blockers(pr2, prov, run))
    pr3 = {**pr, "protocol": {k: v for k, v in pr["protocol"].items() if k != "gate"}}
    assert any("no protocol.gate" in b for b in R.registration_blockers(pr3, prov, run))


def test_verdict_cli_writes_its_outputs(std, tmp_path):
    out_root = tmp_path / "out"
    rc = R.main(["verdict", "--rescue-runs", *rescues(std), "--control-runs", *controls(std), "--e2-config", str(std["e2"]),
                 "--params", str(REPO / "configs" / "agentload_analysis.yaml"), "--out-root", str(out_root)])
    assert rc == 0
    (d,) = list((out_root / "agentload_analysis_rescue").iterdir())
    for f in ("rescue_runs.csv", "rescue_windows.csv", "rescue_pairs.csv", "rescue_costs.csv", "rescue_trace.csv",
              "rescue_verdict.json", "meta.json", "config.yaml"):
        assert (d / f).exists(), f
    doc = json.loads((d / "rescue_verdict.json").read_text())
    assert doc["schema"] == "rescue_verdict_v1" and doc["family"]["all_rates_pass"]
    assert doc["rule"] == R.RULE


# ------------------------------------------------------------------------------------------------ check-run
def test_check_run_passes_a_correct_rescue_run_with_its_burst_plan(std):
    rep = R.check_run(std["rescue_1.35_0"], std["e2"], burst_plan=std["burst_1.35_0"] / "plan.csv")
    assert rep["ok"], rep["failures"]
    c = checks(rep)
    assert c["engage"] and c["pause_when_over_cap"] and c["conservation"] and c["plan_sha256"] and c["e2_config_gate"]


def test_check_run_report_is_blind_to_the_outcome(std):
    rep = R.check_run(std["rescue_1.35_0"], std["e2"])
    txt = json.dumps(rep).lower()
    for word in ("t_release", "hit", "latency", "completed", "rescued", "release"):
        assert word not in txt, word
    rep = R.check_run(std["rescue_1.35_0"], std["e2"], require_release=True, smoke=True)
    assert rep["ok"] and rep["t_release"] == 3600.0 and rep["breakdown_at_end"]["started"] > 0


def test_check_run_refuses_another_seeds_burst_plan(std):
    rep = R.check_run(std["rescue_1.35_0"], std["e2"], burst_plan=std["burst_1.35_1"] / "plan.csv")
    assert not rep["ok"] and checks(rep)["plan_sha256"] is False


def test_check_run_fails_on_a_static_cap_run(tmp_path, std):
    d = make_run(tmp_path, "capped", arm="capped")
    rep = R.check_run(d, std["e2"])
    c = checks(rep)
    assert not rep["ok"] and not c["arm"] and not c["gate_mode_config"] and not c["gate_mode_meta"]
    assert not c["gate_events"] and not c["e2_config_gate"]
    assert R.main(["check-run", str(d), "--e2-config", str(std["e2"])]) == 1
    assert R.main(["check-run", str(std["rescue_1.35_0"]), "--e2-config", str(std["e2"])]) == 0


def test_check_run_needs_one_engage_at_t_on(tmp_path, std):
    rep = R.check_run(make_run(tmp_path, "noeng", arm="rescue", engage=False), std["e2"])
    assert not rep["ok"] and not checks(rep)["engage"] and not checks(rep)["pause_order"]
    rep = R.check_run(make_run(tmp_path, "late", arm="rescue", engage_at=1830.0), std["e2"])
    assert not checks(rep)["engage"]
    rep = R.check_run(make_run(tmp_path, "ok8", arm="rescue", engage_at=1808.0), std["e2"])
    assert checks(rep)["engage"]
    rep = R.check_run(make_run(tmp_path, "noev", arm="rescue", with_events=False), std["e2"])
    assert not checks(rep)["gate_events"]


def test_check_run_needs_pauses_when_sessions_were_over_the_cap(tmp_path, std):
    d = make_run(tmp_path, "nopause", arm="rescue", pause_window=(0.0, 0.0))
    rep = R.check_run(d, std["e2"])
    assert not checks(rep)["pause_when_over_cap"]
    d = make_run(tmp_path, "undercap", arm="rescue", pause_window=(0.0, 0.0), bad=[], gate={**GATE_R1, "n_cap": 500})
    rep = R.check_run(d, e2_file(tmp_path, {**GATE_R1, "n_cap": 500}, name="e2_500.yaml"))
    assert checks(rep)["pause_when_over_cap"]


def test_check_run_catches_pauses_outside_the_engaged_period(tmp_path, std):
    d = make_run(tmp_path, "after", arm="rescue", extra_events=[{"t_s": 5000.0, "event": "pause", "sid": 3}])
    rep = R.check_run(d, std["e2"])
    assert not checks(rep)["pause_order"] and "after the release" in " ".join(rep["failures"])


def test_check_run_conservation(tmp_path, std):
    def drop(s):
        return s[s["sid"] != 5]

    def running(s):
        s.loc[s.index[3], "status"] = "running"
        return s

    def early_cancel(s):
        i = s.index[s["status"] == "completed"][0]
        s.loc[i, "status"] = "cancelled"
        return s

    for name, edit in (("drop", drop), ("running", running), ("early", early_cancel)):
        rep = R.check_run(make_run(tmp_path, name, arm="rescue", ses_edit=edit), std["e2"])
        assert not checks(rep)["conservation"], name
    rep = R.check_run(make_run(tmp_path, "metaoff", arm="rescue",
                               meta_edit=lambda m: m["outcome"].update(sessions_started=1)), std["e2"])
    assert not checks(rep)["conservation"] and "meta.outcome.sessions_started" in " ".join(rep["failures"])


def test_check_run_compares_the_pause_logs_of_sessions_paused_or_gated_at_the_end(tmp_path, std):
    kw = dict(arm="rescue", t_rel=None, pause_window=(8000.0, FOREVER), pause_s=2000.0, gate_until=FOREVER,
              gate_wait=1000.0)
    d = make_run(tmp_path, "openend", **kw)
    rep = R.check_run(d, std["e2"], smoke=True)
    br = rep["breakdown_at_end"]
    assert checks(rep)["conservation"], rep["failures"]
    assert br["paused_at_end"] > 0 and br["gated_at_end"] > 0 and br["not_started_at_end"] == 0
    run, ev = R.load_rescue_run(d)
    assert (R.pause_intervals(run, ev)["source"] == "open").sum() == br["paused_at_end"]

    # the independent records of the pauses must agree: one edit to any of them fails the check
    def meta_cens(m):
        m["outcome"]["gate"]["n_sessions_paused_at_end"] += 1

    def drop_first(kind):
        def f(e):
            return e.drop(index=e.index[e["event"] == kind][0])
        return f

    def zero_one_pause(rq, ses):
        rq.loc[rq.index[rq["pause_s"] > 0][0], "pause_s"] = 0.0
        return rq

    std_kw = dict(arm="rescue")                               # closed pauses (resumed before the end)
    for name, base, extra, word in (("mc", kw, dict(meta_edit=meta_cens), "paused at the end"),
                                    ("dc", kw, dict(ev_edit=drop_first("pause_censored")), "paused at the end"),
                                    ("dr", std_kw, dict(ev_edit=drop_first("resume")), "resume events"),
                                    ("zp", std_kw, dict(req_edit=zero_one_pause), "requests with a pause")):
        rep = R.check_run(make_run(tmp_path, f"openend_{name}", **base, **extra), std["e2"])
        assert not checks(rep)["conservation"] and word in " ".join(rep["failures"]), name


def test_check_run_accepts_a_few_sessions_spawned_at_the_end_that_never_ran(tmp_path, std):
    def pend(k, arrival=T_END - 0.5):
        def f(ses):
            i = ses.sort_values("arrival_s").index[-k:]
            for c, v in (("status", "pending"), ("t_end", np.nan), ("t_admit", np.nan), ("t_first_send", np.nan),
                         ("turns_completed", 0), ("gate_wait_s", 0.0), ("arrival_s", arrival)):
                ses.loc[i, c] = v
            return ses
        return f

    def no_req(rq, ses):
        return rq[~rq["sid"].isin(ses.loc[ses["status"] == "pending", "sid"])]

    rep = R.check_run(make_run(tmp_path, "p2", arm="rescue", ses_edit=pend(2), req_edit=no_req), std["e2"], smoke=True)
    assert checks(rep)["conservation"], rep["failures"]
    assert rep["breakdown_at_end"]["not_started_at_end"] == 2
    rep = R.check_run(make_run(tmp_path, "p5", arm="rescue", ses_edit=pend(5), req_edit=no_req), std["e2"])
    assert not checks(rep)["conservation"] and "never started" in " ".join(rep["failures"])
    rep = R.check_run(make_run(tmp_path, "pr", arm="rescue", ses_edit=pend(2)), std["e2"])        # it sent requests
    assert not checks(rep)["conservation"] and "non-terminal" in " ".join(rep["failures"])
    rep = R.check_run(make_run(tmp_path, "pe", arm="rescue", ses_edit=pend(2, arrival=8000.0), req_edit=no_req),
                      std["e2"])                                                                    # not at the end
    assert not checks(rep)["conservation"]


def _set_row(kind, k=0, **vals):
    def f(e):
        i = e.index[e["event"] == kind][k]
        for c, v in vals.items():
            e.loc[i, c] = v
        return e
    return f


def test_check_run_gate_log_invariants(tmp_path, std):
    rep = R.check_run(std["rescue_1.35_0"], std["e2"])
    for name in ("gate_counts", "gate_pause_rows", "gate_no_lost_wakeup", "gate_cap_held", "gate_uncap_rule",
                 "gate_uncap_hold", "gate_outcome_counts", "gate_end_state"):
        assert checks(rep)[name], (name, rep["failures"])
    rel = {"t_s": 4000.0, "event": "release", "sid": "", "cap": "", "active": 5, "waiting": 0, "paused": 0}
    cases = [
        ("pz_low", dict(ev_edit=_set_row("pause", active=5)), "gate_pause_rows"),
        ("pz_nocap", dict(ev_edit=_set_row("pause", cap=np.nan)), "gate_pause_rows"),
        ("lost", dict(ev_edit=_set_row("resume", 3, active=19, waiting=2)), "gate_no_lost_wakeup"),
        ("above", dict(ev_edit=_set_row("resume", 5, active=23)), "gate_cap_held"),
        ("nocnt", dict(ev_edit=_set_row("pause", 1, active=np.nan)), "gate_counts"),
        ("two", dict(extra_events=[rel]), "gate_uncap_rule"),
        ("offgrid", dict(t_rel=3605.0), "gate_uncap_rule"),
        ("early", dict(t_rel=2300.0, pause_window=(1800.0, 1900.0), gate_until=1900.0), "gate_uncap_rule"),
        ("queued", dict(ev_edit=_set_row("release", waiting=1)), "gate_uncap_rule"),
        ("holdp", dict(pause_window=(1800.0, 3500.0)), "gate_uncap_hold"),
        ("holdg", dict(gate_until=3500.0), "gate_uncap_hold"),
        ("cnt", dict(meta_edit=lambda m: m["outcome"]["gate"].update(n_resumes=1)), "gate_outcome_counts"),
        ("leak", dict(meta_edit=lambda m: m["outcome"]["gate"].update(active_after_end=1)), "gate_end_state"),
        ("err", dict(meta_edit=lambda m: m["outcome"]["gate"].update(gate_control_error="ValueError: x")),
         "gate_end_state"),
    ]
    for name, kw, check in cases:
        rep = R.check_run(make_run(tmp_path, f"inv_{name}", arm="rescue", **kw), std["e2"])
        assert not rep["ok"] and checks(rep)[check] is False, (name, rep["failures"])
    rep = R.check_run(make_run(tmp_path, "inv_lag", arm="rescue", t_rel=3601.0), std["e2"])       # scheduling lag
    assert checks(rep)["gate_uncap_rule"], rep["failures"]
    rep = R.check_run(make_run(tmp_path, "inv_tick_early", arm="rescue", t_rel=3599.985), std["e2"])   # timer one clock tick early
    assert checks(rep)["gate_uncap_rule"], rep["failures"]
    rep = R.check_run(make_run(tmp_path, "inv_tick_early2", arm="rescue", t_rel=3599.5), std["e2"])
    assert not checks(rep)["gate_uncap_rule"]
    # an unreleased run passes the same checks with the same details (blind)
    a = {c["name"]: c["detail"] for c in R.check_run(std["rescue_1.35_0"], std["e2"])["checks"]}
    b = {c["name"]: c["detail"] for c in R.check_run(make_run(tmp_path, "inv_norel", arm="rescue", t_rel=None),
                                                     std["e2"])["checks"]}
    for k in ("gate_uncap_rule", "gate_uncap_hold", "gate_cap_held", "gate_end_state"):
        assert a[k] == b[k], k


def test_check_run_needs_the_engage_row_to_carry_the_cap(tmp_path, std):
    rep = R.check_run(make_run(tmp_path, "blankcap", arm="rescue", ev_edit=_set_row("engage", cap=np.nan)), std["e2"])
    assert not checks(rep)["engage_cap"]


def test_failed_sessions_withhold_the_no_shed_claim(std, tmp_path):
    def fail_one(ses):
        ses.loc[ses.index[ses["status"] == "completed"][0], "status"] = "failed"
        return ses

    r = [str(make_run(tmp_path, "f0", arm="rescue", seed=0, ses_edit=fail_one))] + rescues(std, (1.35,), (1, 2))
    doc, frames = R.verdict(r, controls(std, (1.35,)), PARAMS, profile="r1")
    fam = doc["family"]
    assert fam["primary_rate_pass"] and fam["n_sessions_failed"] == 1 and not fam["no_shed"]
    assert fam["verdict"].startswith("PASS") and "WITHHELD" in fam["verdict"]
    assert int(frames["rescue_runs"]["sessions_failed"].sum()) == 1
    doc, _ = R.verdict(rescues(std, (1.35,)), controls(std, (1.35,)), PARAMS, profile="r1")
    assert doc["family"]["no_shed"] and "WITHHELD" not in doc["family"]["verdict"]


def test_release_times_are_scored_against_the_frozen_prediction(std, tmp_path):
    pdir = tmp_path / "pred"
    pdir.mkdir()
    pd.DataFrame([{"cell": "R1_rescue", "mult": 1.35, "t_rel_min": 3000.0, "t_rel_max": 3500.0},
                  {"cell": "R1_rescue", "mult": 1.65, "t_rel_min": 4000.0, "t_rel_max": 5000.0},
                  {"cell": "R4s_t2100", "mult": 4.0, "t_rel_min": 1.0, "t_rel_max": 2.0}]).to_csv(
        pdir / "cells_mixed.csv", index=False)
    ex = [(1.35, 0, 3550.0), (1.35, 1, 3700.0), (1.35, 2, 3400.0), (1.65, 0, 4100.0), (1.65, 1, 4200.0),
          (1.65, 2, 4300.0)]
    rows = [{"cell": "R1_rescue", "kind": "exact", "mult": m, "seed": sd, "t_rel": t} for m, sd, t in ex]
    rows.append({"cell": "R1_rescue", "kind": "sim", "mult": 1.35, "seed": 0, "t_rel": 9999.0})
    pd.DataFrame(rows).to_csv(pdir / "runs_mixed.csv", index=False)
    doc, frames = R.verdict(rescues(std), controls(std), PARAMS, predictions=str(pdir))
    sc = frames["rescue_t_rel_scoring"].set_index(["rate_mult", "seed"]).sort_index()
    assert len(sc) == 6 and (sc["gpu_t_rel"] == 3600.0).all()
    assert sc.loc[1.35, "inside_union"].all() and not sc.loc[1.35, "inside_band"].any()       # 3600 in [3000, 3700]
    assert not sc.loc[1.65, "inside_union"].any()                                             # 3600 < 4000
    assert list(sc.loc[1.65, "within_tol_of_exact"]) == [True, True, False]                   # 500, 600, 700 s off
    t = doc["t_rel_scoring"]
    assert t["n_scored"] == 6 and t["n_inside_union"] == 3 and t["n_within_tol_of_exact"] == 5
    assert t["expected_inside_if_simulator_exact"] == pytest.approx(6 * 19 / 21)
    out = tmp_path / "out"
    assert R.main(["verdict", "--rescue-runs", *rescues(std), "--control-runs", *controls(std), "--predictions",
                   str(pdir), "--out-root", str(out)]) == 0
    assert len(list(out.glob("**/rescue_t_rel_scoring.csv"))) == 1


def test_check_run_compares_the_gate_block_with_the_e2_config(tmp_path, std):
    rep = R.check_run(std["rescue_1.35_0"], e2_file(tmp_path, {**GATE_R1, "release_hold_s": 120}))
    assert not checks(rep)["e2_config_gate"] and "release_hold_s" in " ".join(rep["failures"])
    rep = R.check_run(std["rescue_1.35_0"], e2_file(tmp_path, {**GATE_R1, "n_cap": 22}, name="e2b.yaml"))
    assert not checks(rep)["e2_config_gate"]
    rep = R.check_run(std["rescue_1.35_0"], e2_file(tmp_path, {**GATE_R1, "mode": "static"}, name="e2c.yaml"))
    assert not checks(rep)["e2_config_gate"]
    rep = R.check_run(std["rescue_1.35_0"], e2_file(tmp_path, name="e2d.yaml", duration=2400.0))
    assert not checks(rep)["e2_config_gate"]


def test_check_run_smoke_criteria(tmp_path, std):
    rep = R.check_run(std["rescue_1.35_0"], std["e2"], min_pauses=10, min_resumes=10, max_request_errors=0)
    assert rep["ok"], rep["failures"]
    few = make_run(tmp_path, "few", arm="rescue", pause_window=(1800.0, 1806.0))
    rep = R.check_run(few, std["e2"], min_pauses=10, min_resumes=10)
    assert not checks(rep)["pause_counts"]
    assert R.main(["check-run", str(few), "--e2-config", str(std["e2"]), "--smoke"]) == 1
    rep = R.check_run(std["rescue_1.35_0"], std["e2"], require_release=True)
    assert checks(rep)["release"]
    rep = R.check_run(make_run(tmp_path, "norel", arm="rescue", t_rel=None), std["e2"], require_release=True)
    assert not checks(rep)["release"]


def test_check_run_json_out(tmp_path, std):
    out = tmp_path / "check.json"
    assert R.main(["check-run", str(std["rescue_1.35_0"]), "--e2-config", str(std["e2"]), "--json-out", str(out)]) == 0
    assert json.loads(out.read_text())["ok"] is True
