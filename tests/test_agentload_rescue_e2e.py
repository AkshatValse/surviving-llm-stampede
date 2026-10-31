"""RESCUE arm end to end on the mock server (plan R1 tests), plus identity with the client at the base commit.

The mock's LRU prefix cache is given a small KV capacity (30k tokens) and a miss cost that makes the all-miss request
throughput (about 20 req/s on 4 slots) lower than the offered load (6 sessions/s, about 5 turns each), while the
all-hit throughput is several times higher. A burst of 80 sessions then traps the uncapped mock within seconds: hits
go to 0 and the backlog grows to the end of the run (the BURST control). The compressed rescue config (cap 24 at
t_on = 12 s, hold 3 s, min_on 5 s, check every 1 s) shows the whole protocol: VALID trap at engage, pauses at tool-call
boundaries, the cure, the release and the hit fraction staying high after it at the unchanged arrival rate.

Both arms run at the same time in two threads (one event loop and one mock server each) to keep the test near one
minute. Every timing threshold has wide margins (3-s windows, cure and release within tens of seconds), so the 15.6 ms
Windows timer resolution and a loaded machine cannot flip it.

The identity tests run the client of the base commit (extracted with ``git archive``) and the current client in
subprocesses on the same tiny configs: uncapped and static-capped runs must produce the same requests (session, turn,
prompt hash, cached tokens) and the same admission order, and the old BURST config must generate the same plan.csv
bytes as the new rescue config.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agentload.mock_server import MockConfig
from conftest import REPO, make_raw, run_gen

BASE_COMMIT = "4d2bba2"
T_ON, CAP, HOLD, MIN_ON, D = 12.0, 24, 3.0, 5.0, 50.0
D_END = 16.0                     # the 'rescue_end' run stops 4 s after the engage, with sessions paused and gated
TRAP_MOCK = dict(kv_capacity_tokens=30_000, slots=4, fixed_s=0.005, per_uncached_token_s=3e-4,
                 per_completion_token_s=1e-3, log_requests=False)


def trap_raw(arm: str, seed: int = 0, duration: float = D):
    raw = make_raw(workload={"initial_context_tokens": 400, "new_prompt_tokens": 50, "decode_tokens": 10,
                             "mean_turns": 6, "max_turns": 12, "tool_time_mean_s": 0.3},
                   arrivals={"rate": 6.0, "burst": {"n": 80, "t_s": 5.0, "width_s": 0.5}, "analysis_t_burst_s": 5.0},
                   run={"duration_s": duration, "seed": seed, "max_inflight": 3000, "max_errors": 50},
                   metrics={"enabled": True, "interval_s": 1.0},
                   meta={"arm": arm, "engine_label": "mock-lru-small"})
    raw["workload"]["content_salt"] = 1
    if arm == "rescue":
        raw["gate"] = {"mode": "rescue", "n_cap": CAP, "t_on_s": T_ON, "pause_at_turns": True,
                       "release_hold_s": HOLD, "min_on_s": MIN_ON, "release_check_s": 1.0}
    return raw


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("rescue_e2e")
    raws = {"burst": trap_raw("burst"), "rescue": trap_raw("rescue"), "rescue_end": trap_raw("rescue", duration=D_END)}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {k: ex.submit(run_gen, raw, MockConfig(**TRAP_MOCK), root / k) for k, raw in raws.items()}
        outs = {k: f.result()[0] for k, f in futs.items()}
    data = {}
    for arm, out in outs.items():
        d = out.out_dir
        data[arm] = {"dir": d, "raw": raws[arm], "req": pd.read_csv(d / "requests.csv"), "ses": pd.read_csv(d / "sessions.csv"),
                     "meta": json.loads((d / "meta.json").read_text()), "metrics": pd.read_csv(d / "metrics.csv"),
                     "ev": pd.read_csv(d / "gate_events.csv") if (d / "gate_events.csv").exists() else None}
    return data


def fu_hit(req: pd.DataFrame, t0: float, t1: float) -> tuple:
    """FU-hit (the registered rule's): share of completed turns >= 2 with cached/prompt > 0.5, by completion time."""
    ok = req[(req["status"] == "ok") & (req["turn"] >= 2) & (req["t_complete"] >= t0) & (req["t_complete"] < t1)]
    if not len(ok):
        return float("nan"), 0
    return float((ok["cached_tokens"] / ok["prompt_tokens"] > 0.5).mean()), len(ok)


def in_system_at(ses: pd.DataFrame, t: float) -> int:
    end = ses["t_end"].fillna(np.inf)
    return int(((ses["arrival_s"] <= t) & (end > t)).sum())


def test_the_uncapped_burst_traps_the_small_cache_mock_and_stays_trapped(runs):
    b = runs["burst"]
    h_pre, n_pre = fu_hit(b["req"], 0.0, 5.0)
    h_trap, n_trap = fu_hit(b["req"], 8.0, D - 1)
    assert n_pre > 30 and h_pre > 0.9                         # good state before the burst
    assert n_trap > 200 and h_trap < 0.1                      # all-miss after it, to the end of the run
    assert in_system_at(b["ses"], D - 2) > in_system_at(b["ses"], T_ON) > 50     # the backlog keeps growing
    assert b["ev"] is None and "gate_mode" not in b["meta"] and b["meta"]["outcome"]["requests_error"] == 0


def test_rescue_plan_is_the_burst_plan_and_nothing_differs_before_t_on(runs):
    r, b = runs["rescue"], runs["burst"]
    pr, pb = (r["dir"] / "plan.csv").read_bytes(), (b["dir"] / "plan.csv").read_bytes()
    assert hashlib.sha256(pr).hexdigest() == hashlib.sha256(pb).hexdigest()
    early = r["ses"][r["ses"]["arrival_s"] < T_ON - 0.1]
    assert len(early) > 100 and (early["gate_wait_s"] == 0).all() and (early["gate_censored"] == 0).all()
    pre = r["req"][r["req"]["t_send"] < T_ON - 0.1]
    assert len(pre) > 200 and (pre["pause_s"] == 0).all()
    assert (r["ev"]["t_s"] >= T_ON - 0.05).all()              # no gate event before t_on
    m = r["metrics"]
    cap = m[m["name"] == "agentload:gate_cap"]
    assert cap[cap["t_s"] < T_ON - 0.1]["value"].isna().all()
    # the BURST and RESCUE request streams carry the same sessions and prompts up to t_on (CRN; timing differs by noise)
    key = ["sid", "turn", "prompt_hash"]
    a = set(map(tuple, r["req"][r["req"]["t_send"] < 4.0][key].to_numpy()))
    c = set(map(tuple, b["req"][b["req"]["t_send"] < 4.0][key].to_numpy()))
    assert len(a) > 50 and len(a ^ c) <= 0.1 * len(a)


def test_rescue_engages_inside_a_valid_trap(runs):
    r = runs["rescue"]
    ev = r["ev"]
    eng = ev[ev["event"] == "engage"]
    assert len(eng) == 1 and abs(float(eng["t_s"].iloc[0]) - T_ON) < 0.1 and int(eng["cap"].iloc[0]) == CAP
    h, n = fu_hit(r["req"], T_ON - 4.0, T_ON)                 # VALID: trapped at engage, many sessions outstanding
    assert n > 20 and h < 0.2
    assert in_system_at(r["ses"], T_ON) > 50
    g = r["meta"]["outcome"]["gate"]
    assert g["mode"] == "rescue" and abs(g["t_engage"] - T_ON) < 0.1 and g["n_cap_engaged"] == CAP
    assert r["meta"]["gate_mode"] == "rescue" and r["meta"]["arm"] == "rescue"
    assert r["meta"]["gate"] == {"mode": "rescue", "n_cap_configured": CAP, "t_on_s": T_ON, "pause_at_turns": True,
                                 "release_hold_s": HOLD, "min_on_s": MIN_ON, "release_check_s": 1.0,
                                 "n_cap_resolved": CAP}


def test_rescue_pauses_cures_and_releases(runs):
    r = runs["rescue"]
    ev, g = r["ev"], r["meta"]["outcome"]["gate"]
    assert (ev["event"] == "pause").sum() >= 10 and (ev["event"] == "resume").sum() >= 10
    rel = ev[ev["event"] == "release"]
    assert len(rel) == 1 and g["released"] and g["t_release"] == pytest.approx(float(rel["t_s"].iloc[0]))
    t_rel = g["t_release"]
    assert T_ON + MIN_ON - 0.05 <= t_rel <= D - 10.0
    assert int(rel["waiting"].iloc[0]) == 0 and int(rel["paused"].iloc[0]) == 0 and pd.isna(rel["cap"].iloc[0])
    # the queues were empty for the hold before the release: no pause / resume / queueing event in (t_rel - HOLD, t_rel)
    before = ev[(ev["t_s"] > t_rel - HOLD + 0.05) & (ev["t_s"] < t_rel)]
    assert not before["event"].isin(["pause", "resume"]).any()
    adm = r["ses"]["t_admit"].dropna()
    waited = r["ses"][r["ses"]["gate_wait_s"] > 0]
    assert len(waited) >= 10 and (waited["t_admit"] <= t_rel - HOLD + 0.05).all()
    assert len(adm) == len(r["ses"]) - int(r["ses"]["gate_censored"].sum())
    # the cure: some 3-s window between engage and release is good again
    cured = [fu_hit(r["req"], t, t + 3.0) for t in np.arange(T_ON, t_rel - 2.9, 1.0)]
    assert any(n >= 20 and h > 0.8 for h, n in cured)
    # after the release, at the unchanged arrival rate and with no cap, the engine stays in the high-hit state
    wins = [fu_hit(r["req"], t, t + 3.0) for t in np.arange(t_rel + 1.0, D - 3.9, 3.0)]
    assert len(wins) >= 2 and all(n >= 20 and h >= 0.5 for h, n in wins)
    h_post, n_post = fu_hit(r["req"], t_rel + 1.0, D - 1.0)
    assert n_post > 100 and h_post > 0.8
    assert in_system_at(r["ses"], D - 2) < 40                 # no backlog, against > 50 in the BURST control
    h_ctl, _ = fu_hit(runs["burst"]["req"], t_rel + 1.0, D - 1.0)
    assert h_ctl < 0.2                                        # same seed, same window, no rescue: still trapped


def test_the_cap_binds_after_attrition(runs):
    ev = runs["rescue"]["ev"]
    on = ev[(ev["t_s"] >= T_ON - 0.05) & ev["cap"].notna()].reset_index(drop=True)
    assert int(on["active"].iloc[0]) > CAP                    # engaged above the active count: attrition needed
    first_ok = int(np.argmax(on["active"].to_numpy() <= CAP))
    assert first_ok > 0 and (on["active"].iloc[first_ok:] <= CAP).all()
    assert runs["rescue"]["meta"]["outcome"]["gate"]["n_attrition"] >= int(on["active"].iloc[0]) - CAP


def test_pause_bookkeeping_is_consistent(runs):
    r = runs["rescue"]
    s, req, ev, g = r["ses"], r["req"], r["ev"], r["meta"]["outcome"]["gate"]
    o = r["meta"]["outcome"]
    assert o["requests_error"] == 0 and r["meta"]["status"] == "finished"
    # conservation: every started session is accounted for exactly once. "pending": spawned in the last instant and
    # cancelled at the end of the run before its task first ran (existing client behaviour, no t_end, no request)
    pend = s[s["status"] == "pending"]
    assert pend["t_end"].isna().all() and (pend["arrival_s"] >= o["t_end_s"] - 1.0).all() and len(pend) <= 3
    assert not req["sid"].isin(pend["sid"]).any()
    assert len(s) == o["sessions_started"] == (o["sessions_completed"] + o["sessions_failed"] + o["sessions_cancelled"]
                                               + len(pend))
    assert set(s["status"]) <= {"completed", "cancelled", "failed", "pending"}
    assert (s[s["pause_censored"] == 1]["status"] == "cancelled").all()
    assert s["n_pauses"].sum() == g["n_pauses"] == (ev["event"] == "pause").sum()
    assert s["n_pauses"].sum() - s["pause_censored"].sum() == g["n_resumes"] == (ev["event"] == "resume").sum()
    assert (ev["event"] == "pause_censored").sum() == s["pause_censored"].sum() == g["n_sessions_paused_at_end"]
    # each resume is followed at once by the paused turn's request, which carries the pause
    paused = req[req["pause_s"] > 0]
    assert len(paused) == g["n_resumes"] and (paused["turn"] >= 2).all()
    assert paused["pause_s"].sum() == pytest.approx(g["pause_s_total_resumed"], rel=1e-6, abs=1e-6)
    assert (paused["sched_delay_s"] < 0.25).all()             # measured from the resume, not from the tool end
    gap = paused["t_send"] - paused["t_ready"] - paused["pause_s"] - paused["sched_delay_s"]
    assert gap.abs().max() < 0.05
    per = paused.groupby("sid")["pause_s"].sum()                # per session: the request rows carry every closed pause
    by_sid = s.set_index("sid")
    no_cens = by_sid[by_sid["pause_censored"] == 0]
    assert np.allclose(per.reindex(no_cens.index).fillna(0.0), no_cens["pause_s_total"], atol=1e-6)
    cens = by_sid[by_sid["pause_censored"] == 1]               # a censored pause is counted up to t_end on top
    assert (cens["pause_s_total"] >= per.reindex(cens.index).fillna(0.0) - 1e-9).all()
    # turn-boundary only: a request row's t_ready is never before the previous turn's completion
    ok = req[req["status"] == "ok"].sort_values(["sid", "turn"])
    prev = ok.groupby("sid")["t_complete"].shift(1)
    assert ((ok["t_ready"] - prev).dropna() >= -1e-6).all()


def _e2_yaml(path: Path, raw: dict) -> Path:
    """An e2 config for check-run: the run's gate block, run length and burst."""
    import yaml
    path.write_text(yaml.safe_dump({"arrivals": {"kind": "constant", "burst": dict(raw["arrivals"]["burst"]),
                                                 "analysis_t_burst_s": raw["arrivals"]["analysis_t_burst_s"]},
                                    "gate": dict(raw["gate"]), "run": {"duration_s": raw["run"]["duration_s"]}},
                                   sort_keys=False))
    return path


def test_check_run_passes_the_mock_rescue_runs(runs, tmp_path):
    """The two halves together: the client's rescue output through ``analysis.rescue check-run`` (smoke criteria for the
    released run; the run stopped while capped, with sessions paused and gated, passes the mechanical checks)."""
    from analysis import rescue as AR
    for key, smoke in (("rescue", True), ("rescue_end", False)):
        r = runs[key]
        e2 = _e2_yaml(tmp_path / f"e2_{key}.yaml", r["raw"])
        bp = (runs["burst"] if key == "rescue" else r)["dir"] / "plan.csv"      # the BURST control's plan (same seed)
        args = ["check-run", str(r["dir"]), "--e2-config", str(e2), "--burst-plan", str(bp)]
        assert AR.main(args + (["--smoke", "--require-release"] if smoke else [])) == 0, key
        rep = AR.check_run(r["dir"], e2, smoke=smoke, require_release=smoke)
        c = {x["name"]: x["ok"] for x in rep["checks"]}
        for name in ("conservation", "gate_pause_rows", "gate_no_lost_wakeup", "gate_cap_held", "gate_uncap_rule",
                     "gate_uncap_hold", "gate_outcome_counts", "gate_end_state", "engage_cap"):
            assert c[name], (key, name, rep["failures"])
    assert AR.main(["check-run", str(runs["rescue"]["dir"]), "--e2-config",
                    str(_e2_yaml(tmp_path / "e2_end.yaml", runs["rescue_end"]["raw"]))]) == 1   # another run length


def test_no_slot_leaks_when_the_run_ends_with_sessions_paused_and_gated(runs):
    r = runs["rescue_end"]
    g, s = r["meta"]["outcome"]["gate"], r["ses"]
    assert g["t_release"] is None and g["n_sessions_paused_at_end"] > 0 and s["pause_censored"].sum() > 0
    assert g["n_still_paused_at_end"] > 0                     # taken before the end-of-run cancel emptied the deques
    assert g["n_still_waiting_at_end"] is not None and g["n_still_paused_at_end"] + g["n_still_waiting_at_end"] > 0
    assert g["active_after_end"] == 0 and g["queued_after_end"] == 0 and g["gate_control_error"] is None
    assert (r["ev"]["event"] == "pause_censored").sum() == g["n_sessions_paused_at_end"]
    assert r["meta"]["outcome"]["abort_reason"] is None


def test_rescue_gauges_are_logged(runs):
    m = runs["rescue"]["metrics"]
    paused = m[m["name"] == "agentload:paused_sessions"]["value"]
    cap = m[m["name"] == "agentload:gate_cap"]
    t_rel = runs["rescue"]["meta"]["outcome"]["gate"]["t_release"]
    assert len(paused) > 30 and paused.max() >= 5
    during = cap[(cap["t_s"] > T_ON + 0.1) & (cap["t_s"] < t_rel - 0.1)]["value"]
    assert len(during) >= 5 and (during == CAP).all()
    assert cap[cap["t_s"] > t_rel + 0.1]["value"].isna().all()
    b = runs["burst"]["metrics"]
    assert not b["name"].isin(["agentload:paused_sessions", "agentload:gate_cap"]).any()   # static/uncapped unchanged


# ============================================================================================ identity with the base commit
DRIVER = r'''
import asyncio, copy, json, sys
from datetime import datetime
from pathlib import Path
src, mode, arg, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, src)
from agentload.client import LoadGenerator, write_plan_csv
from agentload.config import config_from_dict, load_config, resolve_rate
from agentload.workload import build_open_plan
out.mkdir(parents=True, exist_ok=True)
if mode == "plan":
    cfg, _ = load_config(arg["config"], arg["overrides"])
    plan = build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, resolve_rate(cfg.arrivals), [])
    write_plan_csv(out / "plan.csv", plan)
    sys.exit(0)
from agentload.mock_server import MockConfig, MockServer
from agentload.runmeta import git_info, new_result_dir
async def go():
    async with MockServer(MockConfig(**arg["mock"])) as srv:
        raw = copy.deepcopy(arg["raw"])
        raw["server"]["base_url"] = srv.url
        raw["output"]["root"] = str(out)
        cfg = config_from_dict(raw)
        d = new_result_dir(cfg.output.root, cfg.output.name)
        gen = LoadGenerator(cfg, raw, d, Path(src).parent)
        plan = gen.build_plan()
        write_plan_csv(d / "plan.csv", plan)
        await gen.run(["identity"], {}, datetime.now(), plan)
        print(d)
asyncio.run(go())
'''


@pytest.fixture(scope="module")
def old_src(tmp_path_factory):
    try:
        tar = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", BASE_COMMIT, "src/agentload",
                              "configs/agentload_e2_burst.yaml"], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:     # pragma: no cover  (shallow clone without the commit)
        pytest.skip(f"base commit {BASE_COMMIT} not available: {e}")
    root = tmp_path_factory.mktemp("old_commit")
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        tf.extractall(root, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return root


def _drive(src: Path, mode: str, arg: dict, out: Path, tmp: Path) -> subprocess.Popen:
    drv = tmp / "driver.py"
    if not drv.exists():          # written once: rewriting it while an earlier subprocess starts can hand it an empty file
        drv.write_text(DRIVER)
    return subprocess.Popen([sys.executable, "-I", str(drv), str(src), mode, json.dumps(arg), str(out)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait(p: subprocess.Popen) -> str:
    so, se = p.communicate(timeout=300)
    assert p.returncode == 0, se
    return so.strip().splitlines()[-1] if so.strip() else ""


IDENT_MOCK = dict(kv_capacity_tokens=10**7, slots=8, fixed_s=0.01, per_uncached_token_s=0, per_completion_token_s=0)


def _ident_raw(n_cap):
    raw = make_raw(arrivals={"rate": 6.0, "burst": {"n": 20, "t_s": 1.0, "width_s": 0.2}, "analysis_t_burst_s": 1.0},
                   workload={"tool_time_mean_s": 0.1, "mean_turns": 3, "max_turns": 5},
                   run={"duration_s": 4.0, "seed": 3}, metrics={"enabled": False},
                   meta={"arm": "capped" if n_cap else "burst", "engine_label": "mock-identity"},
                   gate={"n_cap": n_cap})
    return raw


@pytest.mark.parametrize("n_cap", [None, 3])
def test_uncapped_and_static_capped_runs_match_the_base_commit(old_src, tmp_path, n_cap):
    arg = {"raw": _ident_raw(n_cap), "mock": IDENT_MOCK}
    po = _drive(old_src / "src", "run", arg, tmp_path / "old", tmp_path)
    pn = _drive(REPO / "src", "run", arg, tmp_path / "new", tmp_path)
    d_old, d_new = Path(_wait(po)), Path(_wait(pn))
    ro, rn = pd.read_csv(d_old / "requests.csv"), pd.read_csv(d_new / "requests.csv")
    so, sn = pd.read_csv(d_old / "sessions.csv"), pd.read_csv(d_new / "sessions.csv")
    assert (d_old / "plan.csv").read_bytes() == (d_new / "plan.csv").read_bytes()
    assert list(rn.columns) == list(ro.columns) + ["t_ready", "pause_s"]           # new columns appended only
    assert list(sn.columns) == list(so.columns) + ["n_pauses", "pause_s_total", "pause_censored"]
    assert not (d_new / "gate_events.csv").exists()
    assert (rn["pause_s"] == 0).all() and (sn["n_pauses"] == 0).all() and (sn["pause_censored"] == 0).all()
    assert np.allclose(rn["t_ready"], rn["t_planned"])
    # same requests for every session that finished in both runs (CRN content, deterministic cache hits)
    done = set(so[so["status"] == "completed"]["sid"]) & set(sn[sn["status"] == "completed"]["sid"])
    assert len(done) >= 0.7 * len(so)
    key = ["sid", "origin", "turn", "n_turns", "prompt_tokens_client", "prompt_hash", "cached_tokens", "status"]
    pick = lambda df: df[df["sid"].isin(done)].sort_values(["sid", "turn"])[key].reset_index(drop=True)
    # values compared exactly; the dtype of a column may differ when only one run has a cancelled (NaN) request at the end
    pd.testing.assert_frame_equal(pick(ro), pick(rn), check_dtype=False)
    # timing columns: turn 1 is sent at its planned time (arrival, or admission when gated) in both
    t1o = ro[ro["turn"] == 1].set_index("sid")["t_planned"]
    t1n = rn[rn["turn"] == 1].set_index("sid")["t_planned"]
    common = t1o.index.intersection(t1n.index)
    ungated = ((so.set_index("sid").loc[common, "gate_wait_s"] == 0)            # whether a capped session waits is
               & (sn.set_index("sid").loc[common, "gate_wait_s"] == 0)).to_numpy()   # timing: ungated in both runs
    assert ungated.sum() >= 10 and np.array_equal(t1o[common][ungated].to_numpy(), t1n[common][ungated].to_numpy())
    lat = (rn.set_index(["sid", "turn"])["t_send"] - ro.set_index(["sid", "turn"])["t_send"]).dropna().abs()
    assert lat.median() < 0.25                               # same send times up to scheduling noise
    mo = json.loads((d_old / "meta.json").read_text())
    mn = json.loads((d_new / "meta.json").read_text())
    assert set(mn) == set(mo) and set(mn["outcome"]) == set(mo["outcome"])
    assert list(mn["outcome"]["gate"]) == list(mo["outcome"]["gate"])           # exactly the old gate keys, in order
    if n_cap:
        # admission order; ties in t_admit (15.6 ms monotonic clock on Windows) broken by arrival, stably
        adm = lambda s: list(s[s["t_admit"].notna()].sort_values(["t_admit", "arrival_s"], kind="mergesort")["sid"])
        assert adm(so)[:40] == adm(sn)[:40] and mn["outcome"]["gate"]["max_active_seen"] <= n_cap
        assert mo["outcome"]["gate"]["n_waited"] > 5 and mn["outcome"]["gate"]["n_waited"] > 5


def test_new_rescue_configs_give_the_plan_of_the_old_burst_config(old_src, tmp_path):
    lam = "arrivals.lambda_ref=0.07153402100919228"
    cases = [("configs/agentload_e2_rescue.yaml", 1.35, 0, 1200, 8700, 20),
             ("configs/agentload_e2_rescue.yaml", 1.65, 2, 1200, 8700, 20),
             ("configs/agentload_e2_rescue_native.yaml", 4.0, 1, 1200, 8700, 64),
             ("configs/agentload_e2_rescue_smoke.yaml", 1.65, 0, 300, 2400, 20)]
    procs = []
    for i, (path, m, seed, t_b, run_s, cap) in enumerate(cases):
        glue = [f"run.seed={seed}", f"arrivals.rate_mult={m}", lam, f"arrivals.analysis_t_burst_s={t_b}",
                f"run.duration_s={run_s}", f"arrivals.burst.t_s={t_b}"]
        old = {"config": str(old_src / "configs/agentload_e2_burst.yaml"), "overrides": glue + ["meta.arm=\"burst\""]}
        new = {"config": str(REPO / path), "overrides": glue + ["meta.arm=\"rescue\"", f"gate.n_cap={cap}"]}
        procs.append((_drive(old_src / "src", "plan", old, tmp_path / f"o{i}", tmp_path),
                      _drive(REPO / "src", "plan", new, tmp_path / f"n{i}", tmp_path), i))
    for po, pn, i in procs:
        _wait(po), _wait(pn)
        a, b = (tmp_path / f"o{i}" / "plan.csv").read_bytes(), (tmp_path / f"n{i}" / "plan.csv").read_bytes()
        assert len(a) > 5000 and hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), cases[i]
