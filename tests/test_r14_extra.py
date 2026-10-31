"""r14 extra cells (remedy plan N3 TOOLSLOW, N4 SHED): the client option workload.tool_slowdown, the four E2 configs, their
registrations and the sha256 / arms binding of analysis.prereg, the job glue argv, and analysis/r14_cells.py.

Identity: without workload.tool_slowdown the client of this branch writes the same files, columns, meta keys and requests as
the client at the base commit (tag r11-rescue-reg, extracted with ``git archive``), and the TOOLSLOW configs give the plan.csv
of the base commit's E2 config (NOBURST arm) byte for byte. CRN: the SHED ramp arrivals outside the stop are the BURST arm's
arrivals, and both equal the committed E2 runs' plans."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import REPO, make_raw, run_gen

from agentload.client import REQ_FIELDS, SESSION_FIELDS, TOOL_CALL_FIELDS, write_plan_csv
from agentload.config import config_from_dict, load_config, resolve_ramp, resolve_rate, tool_slowdown_add_s
from agentload.mock_server import MockConfig
from agentload.workload import build_open_plan, session_spec
from analysis import basin, prereg, r14_cells, r14_prereg
from analysis.load import load_run
from analysis.params import load_params

BASE_COMMIT = "f0bc3ad"                 # tag r11-rescue-reg: the branch point of r14/extra
DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
CAL = "prereg/inputs/2026-10-23/calibration.json"
LAM_REF = 0.07153402100919228
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
BASH = shutil.which("bash")
TOOLSLOW = {10: REPO / "configs/agentload_e2_toolslow_d10.yaml", 30: REPO / "configs/agentload_e2_toolslow_d30.yaml"}
SHED = {600: REPO / "configs/agentload_e2_shed_t600.yaml", 3600: REPO / "configs/agentload_e2_shed_t3600.yaml"}
CONTROLS = r14_cells.find_controls(REPO / r14_cells.CONTROL_ROOT)
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")


# ============================================================================================ config option
def _cfg(ts, **kw):
    raw = make_raw(workload={"tool_slowdown": ts}, **kw)
    return config_from_dict(raw)


def test_tool_slowdown_is_optional_and_validated():
    assert config_from_dict(make_raw()).workload.tool_slowdown is None
    assert _cfg(None).workload.tool_slowdown is None
    c = _cfg({"t_s": 1, "width_s": 2, "add_s": 0.5}).workload.tool_slowdown
    assert (c.t_s, c.width_s, c.add_s) == (1, 2, 0.5)
    with pytest.raises(KeyError, match="lacks"):
        _cfg({"t_s": 1, "width_s": 2})
    with pytest.raises(KeyError, match="unknown config key"):
        _cfg({"t_s": 1, "width_s": 2, "add_s": 1, "end_s": 3})
    for bad, msg in (({"t_s": -1, "width_s": 2, "add_s": 1}, "t_s must be >= 0"),
                     ({"t_s": 1, "width_s": 0, "add_s": 1}, "width_s must be > 0"),
                     ({"t_s": 1, "width_s": 2, "add_s": 0}, "add_s must be > 0"),
                     ({"t_s": 1, "width_s": 2, "add_s": True}, "finite number"),
                     ({"t_s": 1, "width_s": 2, "add_s": float("nan")}, "finite number"),
                     ({"t_s": 3, "width_s": 2, "add_s": 1}, "ends after run.duration_s")):
        with pytest.raises(ValueError, match=msg):
            _cfg(bad)
    with pytest.raises(ValueError, match="mapping"):
        _cfg(5)
    with pytest.raises(ValueError, match="open-loop"):
        _cfg({"t_s": 1, "width_s": 2, "add_s": 1}, arrivals={"kind": "closed", "closed_n": 2})


def test_tool_slowdown_window_is_half_open_on_the_start_time():
    ts = _cfg({"t_s": 1.0, "width_s": 2.0, "add_s": 0.5}).workload.tool_slowdown
    assert [tool_slowdown_add_s(ts, t) for t in (0.999, 1.0, 2.0, 2.999, 3.0, 3.5)] == [0.0, 0.5, 0.5, 0.5, 0.0, 0.0]
    assert tool_slowdown_add_s(None, 2.0) == 0.0


# ============================================================================================ the four configs
@pytest.mark.parametrize("d", sorted(TOOLSLOW))
def test_toolslow_config_is_the_e2_config_plus_the_slowdown_block(d):
    a, b = DEFAULT_CFG.read_bytes(), TOOLSLOW[d].read_bytes()
    assert b"\r" not in b
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    assert yb["workload"].pop("tool_slowdown") == {"t_s": 1200, "width_s": 900, "add_s": d}
    assert yb["meta"].pop("notes").startswith(f"E2 NOBURST + TOOLSLOW d{d}")
    ya["meta"].pop("notes")
    assert ya == yb
    la, lb = a.split(b"\n"), b.split(b"\n")
    added = [x for x in lb if x not in la]
    assert len(lb) == len(la) + 5 and all(x.startswith(b"  #") or x.startswith(b"  tool_slowdown:") or b"notes:" in x
                                          for x in added)
    cfg, _ = load_config(TOOLSLOW[d], ["meta.arm=noburst", "arrivals.burst=null", "arrivals.rate_mult=1.35",
                                       f"arrivals.lambda_ref={LAM_REF}"])
    assert cfg.workload.tool_slowdown.add_s == d and cfg.arrivals.burst is None


@pytest.mark.parametrize("tau", sorted(SHED))
def test_shed_config_is_the_e2_config_with_the_stop_ramp(tau):
    a, b = DEFAULT_CFG.read_bytes(), SHED[tau].read_bytes()
    assert b"\r" not in b
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    t1 = 1800 + tau
    assert yb["arrivals"]["kind"] == "ramp" and yb["arrivals"]["ramp_is_mult"] is True
    assert yb["arrivals"]["ramp"] == [[0, 1.35], [1800, 1.35], [1800.001, 0], [t1, 0], [t1 + 0.001, 1.35], [8700, 1.35]]
    assert yb["arrivals"]["burst"] == {"n": 200, "t_s": 1200, "width_s": 60}
    for k in ("ramp", "ramp_is_mult"):
        yb["arrivals"].pop(k)
    yb["arrivals"]["kind"] = "constant"
    yb["meta"].pop("notes"), ya["meta"].pop("notes")
    assert ya == yb


# ============================================================================================ plans and CRN
def _plan(cfg_path, seed, *, mult=1.35, burst_null=False):
    sets = [f"run.seed={seed}", f"arrivals.rate_mult={mult}", f"arrivals.lambda_ref=\"{CAL}:lambda_miss_turns_based\""]
    if burst_null:
        sets.append("arrivals.burst=null")
    cfg, _ = load_config(Path(cfg_path), sets)
    rate = resolve_rate(cfg.arrivals, REPO) if cfg.arrivals.kind == "constant" else None
    knots = resolve_ramp(cfg.arrivals, REPO) if cfg.arrivals.kind == "ramp" else []
    return build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, knots)


def _plan_bytes(plan, tmp_path, name):
    f = tmp_path / name
    write_plan_csv(f, plan)
    return f.read_bytes()


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_toolslow_plan_is_the_committed_noburst_plan(tmp_path, seed):
    """Sessions, arrival times exact; tool-time totals within 1e-9 (the committed plans were drawn on Linux; numpy's exponential
    can differ in the last bit on Windows, see tests/test_r11_basin.py). Byte-identical to the default config's plan here."""
    ref = pd.read_csv(CONTROLS[("noburst", seed)] / "plan.csv", float_precision="round_trip")
    here = _plan_bytes(_plan(DEFAULT_CFG, seed, burst_null=True), tmp_path, "default.csv")
    for d, path in TOOLSLOW.items():
        got = _plan_bytes(_plan(path, seed, burst_null=True), tmp_path, f"d{d}.csv")
        assert got == here
        assert r14_cells.plans_equal(pd.read_csv(tmp_path / f"d{d}.csv", float_precision="round_trip"), ref) and len(ref) > 500


@pytest.mark.parametrize("tau", sorted(SHED))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_shed_arrivals_outside_the_stop_are_the_burst_arms(tau, seed):
    """CRN: the ramp's candidate stream is the constant arm's; every candidate outside the stop is kept (probability 1)."""
    burst = _plan(DEFAULT_CFG, seed)
    shed = _plan(SHED[tau], seed)
    lo, hi = 1800.0, 1800.0 + tau + 0.001
    outside = lambda ps: [s.arrival_s for s in ps if s.origin == "base" and not lo <= s.arrival_s < hi]   # noqa: E731
    inside = lambda ps: [s.arrival_s for s in ps if s.origin == "base" and lo <= s.arrival_s < hi]       # noqa: E731
    assert outside(shed) == outside(burst) and len(outside(burst)) > 300
    assert inside(shed) == [] and len(inside(burst)) > 0.5 * LAM_REF * 1.35 * tau
    bb = [(s.idx, s.arrival_s, s.n_turns, s.tool_times_s) for s in burst if s.origin == "burst"]
    assert bb == [(s.idx, s.arrival_s, s.n_turns, s.tool_times_s) for s in shed if s.origin == "burst"] and len(bb) == 200
    # base sessions before the stop are the same sessions (same index, so same spec and content); after it they are redrawn
    pre_b = [(s.idx, s.arrival_s, s.n_turns, s.tool_times_s) for s in burst if s.origin == "base" and s.arrival_s < lo]
    pre_s = [(s.idx, s.arrival_s, s.n_turns, s.tool_times_s) for s in shed if s.origin == "base" and s.arrival_s < lo]
    assert pre_b == pre_s
    # and the BURST arm's plan here is the committed BURST control's plan.csv (job 1709338x), so the SHED arrivals are its
    if ("burst", seed) in CONTROLS:
        tmp = io.StringIO()
        ref = pd.read_csv(CONTROLS[("burst", seed)] / "plan.csv", float_precision="round_trip")
        rb = ref[ref["origin"] == "base"]
        got = rb[(rb["arrival_s"] < lo) | (rb["arrival_s"] >= hi)]["arrival_s"].tolist()
        assert got == outside(shed)
        del tmp


def test_shed_ramp_rate_is_the_constant_rate_outside_the_stop():
    for tau, path in SHED.items():
        cfg, _ = load_config(path, ["arrivals.rate_mult=1.35", f"arrivals.lambda_ref={LAM_REF}"])
        knots = resolve_ramp(cfg.arrivals, REPO)
        assert max(r for _, r in knots) == 1.35 * LAM_REF == resolve_rate(cfg.arrivals, REPO)


# ============================================================================================ client on the mock
TS_MOCK = dict(kv_capacity_tokens=10**7, slots=8, fixed_s=0.005, per_uncached_token_s=0, per_completion_token_s=0,
               log_requests=False)


def _ts_raw(ts):
    raw = make_raw(workload={"tool_time_mean_s": 0.2, "mean_turns": 5, "max_turns": 10},
                   arrivals={"rate": 4.0}, run={"duration_s": 6.0, "seed": 1}, metrics={"enabled": False},
                   meta={"arm": "noburst", "engine_label": "mock-toolslow"})
    if ts is not None:
        raw["workload"]["tool_slowdown"] = ts
    return raw


def test_tool_slowdown_on_the_mock_server_adds_the_delay_to_tool_calls_started_in_the_window(tmp_path):
    ts = {"t_s": 1.5, "width_s": 1.5, "add_s": 0.6}
    out, _ = run_gen(_ts_raw(ts), MockConfig(**TS_MOCK), tmp_path)
    d = out.out_dir
    tc = pd.read_csv(d / "tool_calls.csv", float_precision="round_trip")
    assert list(tc.columns) == TOOL_CALL_FIELDS and len(tc) > 30
    inwin = (tc["t_start"] >= 1.5) & (tc["t_start"] < 3.0)
    assert inwin.sum() >= 5 and (~inwin).sum() >= 5
    assert (tc.loc[inwin, "add_s"] == 0.6).all() and (tc.loc[~inwin, "add_s"] == 0.0).all()
    assert np.allclose(tc["t_ready"], tc["t_start"] + tc["tool_s"] + tc["add_s"], atol=1e-9)
    raw = _ts_raw(ts)
    wl = config_from_dict(raw).workload
    for _, r in tc.head(40).iterrows():                     # the drawn tool time is the plan's (no random draw changes)
        assert r["tool_s"] == session_spec(1, r["origin"], int(r["idx"]), wl)[1][int(r["turn"]) - 1]
    req = pd.read_csv(d / "requests.csv", float_precision="round_trip")
    assert list(req.columns) == REQ_FIELDS
    nxt = req.set_index(["sid", "turn"])["t_send"]
    sent = [(nxt.get((r.sid, r.turn + 1)), r.t_ready) for r in tc.itertuples() if (r.sid, r.turn + 1) in nxt.index]
    assert len(sent) > 20 and all(t_send >= t_ready - 0.05 for t_send, t_ready in sent)
    # the gap: a slowed follow-up waits at least add_s longer than its drawn tool time after the previous response
    comp = req.set_index(["sid", "turn"])["t_complete"]
    gaps = [(nxt[(r.sid, r.turn + 1)] - comp[(r.sid, r.turn)]) - r.tool_s for r in tc[inwin].itertuples()
            if (r.sid, r.turn + 1) in nxt.index]
    assert gaps and min(gaps) >= 0.6 - 0.05
    meta = json.loads((d / "meta.json").read_text())
    assert meta["tool_slowdown"]["add_s"] == 0.6 and meta["tool_slowdown"]["log"] == "tool_calls.csv"
    assert meta["outcome"]["tool_slowdown"] == {"n_tool_calls": len(tc), "n_tool_calls_slowed": int(inwin.sum())}


def test_without_the_option_no_tool_log_and_no_meta_keys(tmp_path):
    out, _ = run_gen(_ts_raw(None), MockConfig(**TS_MOCK), tmp_path)
    d = out.out_dir
    assert not (d / "tool_calls.csv").exists()
    meta = json.loads((d / "meta.json").read_text())
    assert "tool_slowdown" not in meta and "tool_slowdown" not in meta["outcome"]


# ============================================================================================ identity with the base commit
@pytest.fixture(scope="module")
def old_src(tmp_path_factory):
    try:
        tar = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", BASE_COMMIT, "src/agentload",
                              "configs/agentload_e2_burst.yaml"], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:     # pragma: no cover
        pytest.skip(f"base commit {BASE_COMMIT} not available: {e}")
    root = tmp_path_factory.mktemp("old_r14")
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        tf.extractall(root, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return root


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
from agentload.runmeta import new_result_dir
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


def _drive(src, mode, arg, out, tmp):
    drv = tmp / "driver_r14.py"
    if not drv.exists():
        drv.write_text(DRIVER)
    return subprocess.Popen([sys.executable, "-I", str(drv), str(src), mode, json.dumps(arg), str(out)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait(p):
    so, se = p.communicate(timeout=300)
    assert p.returncode == 0, se
    return so.strip().splitlines()[-1] if so.strip() else ""


IDENT_MOCK = dict(kv_capacity_tokens=10**7, slots=8, fixed_s=0.01, per_uncached_token_s=0, per_completion_token_s=0)


@pytest.mark.parametrize("arm", ["burst", "noburst"])
def test_without_the_option_the_client_matches_the_base_commit(old_src, tmp_path, arm):
    raw = make_raw(arrivals={"rate": 6.0, "burst": {"n": 20, "t_s": 1.0, "width_s": 0.2} if arm == "burst" else None,
                             "analysis_t_burst_s": 1.0},
                   workload={"tool_time_mean_s": 0.1, "mean_turns": 3, "max_turns": 5},
                   run={"duration_s": 4.0, "seed": 3}, metrics={"enabled": True, "interval_s": 0.5},
                   meta={"arm": arm, "engine_label": "mock-identity"})
    arg = {"raw": raw, "mock": IDENT_MOCK}
    po = _drive(old_src / "src", "run", arg, tmp_path / "old", tmp_path)
    pn = _drive(REPO / "src", "run", arg, tmp_path / "new", tmp_path)
    d_old, d_new = Path(_wait(po)), Path(_wait(pn))
    assert sorted(p.name for p in d_old.iterdir()) == sorted(p.name for p in d_new.iterdir())
    assert (d_old / "plan.csv").read_bytes() == (d_new / "plan.csv").read_bytes()
    ro, rn = pd.read_csv(d_old / "requests.csv"), pd.read_csv(d_new / "requests.csv")
    so, sn = pd.read_csv(d_old / "sessions.csv"), pd.read_csv(d_new / "sessions.csv")
    assert list(ro.columns) == list(rn.columns) == REQ_FIELDS and list(so.columns) == list(sn.columns) == SESSION_FIELDS
    assert (d_old / "requests.csv").read_bytes().split(b"\n")[0] == (d_new / "requests.csv").read_bytes().split(b"\n")[0]
    done = set(so[so["status"] == "completed"]["sid"]) & set(sn[sn["status"] == "completed"]["sid"])
    assert len(done) >= 0.7 * len(so)
    key = ["sid", "origin", "turn", "n_turns", "prompt_tokens_client", "prompt_hash", "cached_tokens", "status"]
    pick = lambda df: df[df["sid"].isin(done)].sort_values(["sid", "turn"])[key].reset_index(drop=True)   # noqa: E731
    pd.testing.assert_frame_equal(pick(ro), pick(rn), check_dtype=False)
    mo, mn = json.loads((d_old / "meta.json").read_text()), json.loads((d_new / "meta.json").read_text())
    assert list(mo) == list(mn) and list(mo["outcome"]) == list(mn["outcome"])
    assert list(mo["outcome"]["gate"]) == list(mn["outcome"]["gate"])
    mt_o, mt_n = pd.read_csv(d_old / "metrics.csv"), pd.read_csv(d_new / "metrics.csv")
    assert sorted(set(mt_o["name"])) == sorted(set(mt_n["name"]))


def test_toolslow_configs_give_the_base_commits_noburst_plan(old_src, tmp_path):
    procs = []
    for i, (d, seed) in enumerate([(10, 0), (30, 1), (10, 2)]):
        glue = [f"run.seed={seed}", "arrivals.rate_mult=1.35", f"arrivals.lambda_ref={LAM_REF}", "arrivals.analysis_t_burst_s=1200",
                "run.duration_s=8700", "arrivals.burst=null", "meta.arm=\"noburst\""]
        old = {"config": str(old_src / "configs/agentload_e2_burst.yaml"), "overrides": glue}
        new = {"config": str(TOOLSLOW[d]), "overrides": glue}
        procs.append((_drive(old_src / "src", "plan", old, tmp_path / f"o{i}", tmp_path),
                      _drive(REPO / "src", "plan", new, tmp_path / f"n{i}", tmp_path), i))
    for po, pn, i in procs:
        _wait(po), _wait(pn)
        a, b = (tmp_path / f"o{i}" / "plan.csv").read_bytes(), (tmp_path / f"n{i}" / "plan.csv").read_bytes()
        assert len(a) > 5000 and hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


# ============================================================================================ registrations
@pytest.mark.parametrize("cell", sorted(r14_prereg.CELLS))
def test_registration_is_reproduced_by_fill_and_differs_from_the_parent_only_where_allowed(cell):
    c = r14_prereg.CELLS[cell]
    data = (REPO / c["out"]).read_bytes()
    assert b"\r" not in data
    assert r14_prereg.dump_registration(r14_prereg.fill_registration(cell)) == data
    pr = yaml.safe_load(data)
    assert pr["status"] == "FILLED" and pr["inputs"]["engine_cell_label"] == c["label"]
    assert pr["protocol"]["arms"] == c["arms"] and pr["lambda_selection"]["lambda_mults"] == [1.35]
    assert pr["protocol"]["e2_config_sha256"] == hashlib.sha256((REPO / c["e2"]).read_bytes()).hexdigest()
    assert pr["measured"]["hardware"] == HW and pr["measured"]["n_cap"] == 20
    assert not [x for x in prereg.validate(pr, load_params(REPO / "configs/agentload_analysis.yaml", []))
                if x["severity"] == "error"]
    diff = r14_prereg.registration_diff(yaml.safe_load(PARENT.read_text()), pr)
    assert diff["forbidden"] == [] and set(diff["derived"]) <= {"predicted_boundaries.capped_drain.predicted_drain_s_by_mult.1.65"}
    rule = pr["lambda_selection"]["rule"]
    assert (r14_prereg.TOOLSLOW_RULE if c["family"] == "toolslow" else r14_prereg.SHED_RULE) in rule
    assert "configs/r11_basin_predict.yaml" in rule and "[5700, 8700)" in rule and "pred2" in rule
    rc = r14_cells.CELLS[c["label"]]
    assert rc["arm"] == c["arms"][0] and list(rc["seeds"]) == c["seeds"] and rc["e2"] == c["e2"]
    assert r14_cells.RULES[c["family"]] in rule


def test_default_fill_is_unchanged_and_the_sha_is_recorded_only_for_non_default_configs():
    p = load_params(REPO / "configs/agentload_analysis.yaml", [])
    inp = "prereg/inputs/2026-10-23"
    rd = lambda rel: (REPO / rel).read_text()                                  # noqa: E731
    args = dict(e0b=json.loads(rd(f"{inp}/lambda_cap_bracket.json")), lambda_mults=[1.35, 1.65], rule="x",
                engine_cell_label="sglang-fcfs-r1", mu_curve_path=f"{inp}/mu_curve.json", calibration_path=f"{inp}/calibration.json",
                e0b_path=f"{inp}/lambda_cap_bracket.json", n_cap_rule="smallest_within_margin", p=p)
    tm, mu, cal = yaml.safe_load(rd("configs/agentload_prereg_template.yaml")), json.loads(rd(f"{inp}/mu_curve.json")), \
        json.loads(rd(f"{inp}/calibration.json"))
    sha = hashlib.sha256(DEFAULT_CFG.read_bytes()).hexdigest()
    a = prereg.fill(tm, mu, cal, e2_cfg=yaml.safe_load(DEFAULT_CFG.read_text()), e2_cfg_path="configs/agentload_e2_burst.yaml",
                    e2_cfg_sha256=sha, **args)
    assert set(a["protocol"]) == {"duration_s", "t_burst_s", "burst_n", "burst_width_s"}
    b = prereg.fill(tm, mu, cal, e2_cfg=yaml.safe_load(TOOLSLOW[10].read_text()), e2_cfg_path="configs/agentload_e2_toolslow_d10.yaml",
                    **args)                                                    # no sha passed (as analysis.basin fill): nothing
    assert set(b["protocol"]) == set(a["protocol"])


def _check_job(capsys, reg, cfg, label, arms="noburst", mults="1.35"):
    argv = ["check-job", str(reg), "--label", label, "--mults", mults, "--calib", str(REPO / CAL), "--hardware", HW,
            "--e2-config", str(cfg), "--duration-s", "8700", "--t-burst-s", "1200",
            "--params", str(REPO / "configs" / "agentload_analysis.yaml"), "--set", "trap_v2.eval_from_s=4500.0",
            "--allow-uncommitted"]
    if arms is not None:
        argv[4:4] = ["--arms", arms]
    rc = prereg.main(argv)
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("cell", sorted(r14_prereg.CELLS))
def test_check_job_binds_the_e2_config_bytes_and_the_arm(capsys, cell, tmp_path):
    c = r14_prereg.CELLS[cell]
    reg, cfg, arm = REPO / c["out"], REPO / c["e2"], c["arms"][0]
    rc, out = _check_job(capsys, reg, cfg, c["label"], arm)
    assert rc == 0 and "PREREG_SHA256=" in out, out
    other = "burst" if arm == "noburst" else "noburst"
    rc, out = _check_job(capsys, reg, cfg, c["label"], other)
    assert rc == 1 and "not in the registered protocol.arms" in out
    rc, out = _check_job(capsys, reg, cfg, c["label"], None)
    assert rc == 1 and "must pass explicit ARMS" in out
    rc, out = _check_job(capsys, reg, DEFAULT_CFG, c["label"], arm)                 # same burst / duration, other bytes
    assert rc == 1 and "!= registered protocol.e2_config_sha256" in out and out.count("PREREG PROBLEM") == 1
    edited = tmp_path / "edited.yaml"
    edited.write_bytes(cfg.read_bytes().replace(b'notes: "E2', b'notes: "e2'))
    rc, out = _check_job(capsys, reg, edited, c["label"], arm)
    assert rc == 1 and "!= registered protocol.e2_config_sha256" in out
    rc, out = _check_job(capsys, reg, cfg, c["label"], arm, mults="1.65")
    assert rc == 1 and "not in the registered lambda_mults" in out
    if c["family"] == "shed":
        assert "the ramp's rate outside the stop" in out


def test_the_parent_and_b1_registrations_still_pass_check_job(capsys):
    rc, out = _check_job(capsys, PARENT, DEFAULT_CFG, "sglang-fcfs-r1", "burst noburst capped", mults="1.35 1.65")
    assert rc == 0, out
    for n in (25, 100):
        rc, out = _check_job(capsys, REPO / f"configs/agentload_prereg_2026-10-30_b{n}.yaml",
                             REPO / f"configs/agentload_e2_burst_n{n}.yaml", f"sglang-fcfs-r1-b{n}", "burst", mults="1.65")
        assert rc == 0, out


def test_ramp_problems():
    e2 = yaml.safe_load(SHED[600].read_text())
    assert prereg.ramp_problems(e2, [1.35]) == []
    assert prereg.ramp_problems(yaml.safe_load(DEFAULT_CFG.read_text()), [1.65]) == []
    assert "!= the ramp's rate" in prereg.ramp_problems(e2, [1.65])[0]
    e2["arrivals"]["ramp_is_mult"] = False
    assert "ramp_is_mult" in prereg.ramp_problems(e2, [1.35])[0]


def _fake_run(tmp_path, cfg_bytes, arm, label, cfg_extra=None):
    d = tmp_path / f"run_{arm}"
    d.mkdir(exist_ok=True)
    (d / "config.yaml").write_bytes(cfg_bytes)
    cfg = yaml.safe_load(cfg_bytes)
    if arm == "noburst":
        cfg["arrivals"]["burst"] = None
    cfg["run"]["duration_s"] = 8700
    return SimpleNamespace(dir=d, label=label, rate_mult=1.35, lambda_ref_value=LAM_REF, uncached_tokens_ref_value=11243.179816372982,
                           hardware=HW, cfg=cfg, t_burst_ref=1200.0, arm=arm, arm_derived=arm, gate_n_cap=None,
                           prereg_sha256="x", t0_unix=4e9)


def test_run_blockers_check_the_run_config_bytes_and_the_arm(tmp_path):
    c = r14_prereg.CELLS["toolslow-d10"]
    reg = REPO / c["out"]
    pr, prov = prereg.load_prereg(reg), prereg.file_provenance(reg)
    raw = TOOLSLOW[10].read_bytes()
    run = _fake_run(tmp_path, raw, "noburst", c["label"])
    run.prereg_sha256 = prov["sha256"]
    bl = [b for b in prereg.run_blockers(pr, prov, run) if "registration committed" not in b and "commit time unknown" not in b]
    assert bl == []
    (run.dir / "config.yaml").write_bytes(raw.replace(b"\n", b"\r\n"))                    # a Windows copy of the same text
    assert not [b for b in prereg.run_blockers(pr, prov, run) if "config.yaml" in b]
    (run.dir / "config.yaml").write_bytes(TOOLSLOW[30].read_bytes())
    assert any("config.yaml sha256" in b for b in prereg.run_blockers(pr, prov, run))
    run.arm = run.arm_derived = "burst"
    assert any("not in the registered protocol.arms" in b for b in prereg.run_blockers(pr, prov, run))


# ============================================================================================ job glue argv
def _e2_argv(tmp_path, meta_argv, arm, e2_config):
    from test_r11_basin import _set_value
    port = _set_value(meta_argv, "server.base_url").rsplit(":", 1)[1]
    env = {"REPO_DIR": REPO.as_posix(), "JOB_DIR": tmp_path.as_posix(), "RESULTS_ROOT": "results",
           "BASE_URL": f"http://127.0.0.1:{port}", "SERVED_MODEL": _set_value(meta_argv, "server.model"),
           "REQUEST_TOKEN_IDS": _set_value(meta_argv, "server.request_token_ids"),
           "OUTPUT_FEEDBACK": _set_value(meta_argv, "workload.output_feedback"),
           "ENGINE_LABEL": _set_value(meta_argv, "meta.engine_label"), "HW": _set_value(meta_argv, "meta.hardware"),
           "START_VERIFIED": _set_value(meta_argv, "meta.start_state_verified"),
           "START_DETAIL": _set_value(meta_argv, "meta.start_state_detail"),
           "CALIB_FILE": CAL, "PREREG_SHA256": _set_value(meta_argv, "meta.prereg_sha256"),
           "PREREG_FILE": _set_value(meta_argv, "meta.prereg_file"), "T_BURST": "1200", "BURST_RUN_S": "8700", "MODE": "burst"}
    lines = ["set -u", f'source "{(REPO / "slurm" / "common.sh").as_posix()}"']
    lines += [f"{k}={json.dumps(v)}" for k, v in env.items()]
    lines.append(f"E2_CONFIG={json.dumps(e2_config)}" if e2_config else ': "${E2_CONFIG:=$E2_CONFIG_DEFAULT}"')
    lines.append('gen_python() { local a; for a in "$@"; do printf "ARG:%s\\n" "$a"; done; }')
    tail = {"burst": "--set arrivals.burst.t_s=$T_BURST", "noburst": "--set arrivals.burst=null"}[arm]
    lines.append(f'cd "$REPO_DIR" && e2_run {arm} 1.35 0 {tail}')
    r = subprocess.run([BASH, "-c", "\n".join(lines)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return [ln[4:] for ln in r.stdout.splitlines() if ln.startswith("ARG:")]


@needs_bash
@pytest.mark.parametrize("arm,cfg", [("noburst", "configs/agentload_e2_toolslow_d10.yaml"),
                                     ("noburst", "configs/agentload_e2_toolslow_d30.yaml"),
                                     ("burst", "configs/agentload_e2_shed_t600.yaml"),
                                     ("burst", "configs/agentload_e2_shed_t3600.yaml")])
def test_e2_run_argv_differs_from_the_committed_arm_only_in_the_config(tmp_path, arm, cfg):
    meta = json.loads((CONTROLS[(arm, 0)] / "meta.json").read_text())
    got = _e2_argv(tmp_path, meta["argv"], arm, None)
    assert got == meta["argv"][1:]                                        # default: the committed 1.35 x run's argv
    got_c = _e2_argv(tmp_path, meta["argv"], arm, cfg)
    i = got_c.index("--config")
    assert got_c[i + 1] == cfg and got_c[:i + 1] + got_c[i + 2:] == got[:i + 1] + got[i + 2:]
    # the generator accepts exactly that argv (the overrides parse and validate; kind ramp with the recorded rate_mult)
    sets = [got_c[k + 1] for k, a in enumerate(got_c) if a == "--set"]
    sets = [s for s in sets if not s.startswith(("server.", "meta.prereg"))]
    loaded, _ = load_config(REPO / cfg, sets)
    assert loaded.meta.arm == arm and math.isclose(loaded.arrivals.rate_mult, 1.35)


# ============================================================================================ analysis/r14_cells.py
def _rec(label, seed, stuck=False, good=False, counted=True, **kw):
    return {"role": "new", "label": label, "seed": seed, "stuck": stuck, "good": good, "counted": counted, **kw}


def test_decision_rules():
    L = {k: v for k, v in ((c["key"], lab) for lab, c in r14_cells.CELLS.items())}
    rows = ([_rec(L["d10"], s, good=True) for s in (0, 1)] + [_rec(L["d10"], 2, stuck=True)]
            + [_rec(L["d30"], s, stuck=True) for s in (0, 2)] + [_rec(L["d30"], 1, good=True)]
            + [_rec(L["t600"], s, stuck=True, sessions_shed=58) for s in (0, 1)]
            + [_rec(L["t3600"], 0, good=True, sessions_shed=348)])
    d = r14_cells.decision(rows)
    assert d["toolslow"]["pass"] is True and d["cells"]["d10"]["need"] == 2 and d["cells"]["t600"]["need"] == 2
    assert d["shed"]["pass"] is None and d["cells"]["t3600"]["missing_seeds"] == [1]       # seed 1 of t3600 missing
    assert d["shed"]["r1_sessions_shed"] == 0 and d["cells"]["t600"]["sessions_shed_by_seed"] == {"0": 58, "1": 58}
    rows.append(_rec(L["t3600"], 1, stuck=True))
    assert r14_cells.decision(rows)["shed"]["pass"] is False                                # 1 of 2 GOOD
    rows2 = [r for r in rows if r["label"] != L["d30"]] + [_rec(L["d30"], s, stuck=True, counted=(s != 0)) for s in (0, 1, 2)]
    d2 = r14_cells.decision(rows2)
    assert d2["cells"]["d30"]["stuck"] == 2 and d2["toolslow"]["pass"] is True              # an uncounted run is not counted
    rows3 = [r for r in rows2 if not (r["label"] == L["d10"] and r["seed"] == 0)]
    assert r14_cells.decision(rows3)["toolslow"]["pass"] is None                             # d10: 1 good, 1 missing
    assert r14_cells.RULES["toolslow"] == r14_prereg.TOOLSLOW_RULE and r14_cells.RULES["shed"] == r14_prereg.SHED_RULE


def test_decision_does_not_let_a_resubmitted_seed_vote_twice():
    L = {k: v for k, v in ((c["key"], lab) for lab, c in r14_cells.CELLS.items())}
    rows = ([_rec(L["d10"], 0, good=True), _rec(L["d10"], 0, good=True), _rec(L["d10"], 1, stuck=True),
             _rec(L["d10"], 2, stuck=True)] + [_rec(L["d30"], s, stuck=True) for s in (0, 1, 2)])
    d = r14_cells.decision(rows)
    assert d["cells"]["d10"]["duplicate_seeds"] == [0] and d["toolslow"]["d10_good_majority"] is None
    assert d["toolslow"]["pass"] is None
    rows = rows[1:]                                                                          # drop the duplicate
    assert r14_cells.decision(rows)["toolslow"]["pass"] is False                            # one vote for seed 0: 1 of 3


def test_cli_checks_the_binding_of_every_cell_by_default():
    ap_default = [str(REPO / c["out"]) for c in r14_prereg.CELLS.values()]
    assert sorted(Path(x).name for x in ap_default) == sorted(Path(r14_cells.CELLS[lab]["e2"]).name.replace(
        "agentload_e2_", "agentload_prereg_2026-10-31_") for lab in r14_cells.CELLS)
    assert all(Path(x).is_file() for x in ap_default)


def test_frozen_endpoints_are_the_basin_files_and_agree_with_the_registered_constants():
    ep = basin.load_endpoints(REPO / r14_cells.ENDPOINTS)
    assert ep["eval_window_s"] == [5700.0, 8700.0] and ep["stuck_hit_below"] == 0.2 and ep["good_hit_above"] == 0.8
    p = load_params(REPO / r14_cells.PARAMS, [f"trap_v2.eval_from_s={r14_cells.REGISTERED_EVAL_FROM_S}"])
    assert basin.endpoint_problems(ep, p) == []


def test_controls_are_found_for_every_registered_seed():
    for c in r14_cells.CELLS.values():
        ctl = "noburst" if c["family"] == "toolslow" else "burst"
        assert all((ctl, s) in CONTROLS for s in c["seeds"])


def _synthetic_shed_run(tmp_path, seed, tau):
    """A run dir whose plan is the generator's SHED plan (no engine): enough for the pairing and ramp checks."""
    d = tmp_path / f"shed_{tau}_{seed}"
    d.mkdir()
    write_plan_csv(d / "plan.csv", _plan(SHED[tau], seed))
    cfg, raw = load_config(SHED[tau], [f"run.seed={seed}", "arrivals.rate_mult=1.35", f"arrivals.lambda_ref={LAM_REF}"])
    knots = resolve_ramp(cfg.arrivals, REPO)
    return SimpleNamespace(dir=d, cfg=raw, meta={"ramp_knots": [list(k) for k in knots]}, lam=knots[-1][1])


@pytest.mark.parametrize("tau", sorted(SHED))
def test_shed_pairing_and_sessions_shed_against_the_committed_burst_control(tmp_path, tau):
    run = _synthetic_shed_run(tmp_path, 0, tau)
    res = r14_cells.shed_pairing(run, CONTROLS[("burst", 0)], float(tau))
    assert res["paired"] is True and res["pairing_problem"] == ""
    assert res["run_base_arrivals_in_stop"] == 0 and res["sessions_shed"] == res["control_base_arrivals_in_stop"] > 0
    assert 0.5 * 1.35 * LAM_REF * tau < res["sessions_shed"] < 1.6 * 1.35 * LAM_REF * tau
    assert r14_cells.ramp_flat_over_window(run, 5700.0, 8700.0)
    assert not r14_cells.ramp_flat_over_window(run, 1700.0, 8700.0)
    bad = r14_cells.shed_pairing(run, CONTROLS[("burst", 1)], float(tau))                 # another seed: not CRN
    assert bad["paired"] is False


def test_toolslow_pairing_with_the_committed_noburst_plan(tmp_path):
    d = tmp_path / "ts"
    d.mkdir()
    write_plan_csv(d / "plan.csv", _plan(TOOLSLOW[30], 1, burst_null=True))
    run = SimpleNamespace(dir=d)
    assert r14_cells.toolslow_pairing(run, CONTROLS[("noburst", 1)])["paired"] is True
    assert r14_cells.toolslow_pairing(run, CONTROLS[("noburst", 2)])["paired"] is False
    assert r14_cells.toolslow_pairing(run, None)["paired"] is False


def test_ramp_run_lam_is_the_post_stop_rate(tmp_path):
    from analysis.load import Run
    knots = [[0, 0.1], [10, 0.1], [10.001, 0.0], [20, 0.0], [20.001, 0.1], [100, 0.1]]
    r = Run(dir=tmp_path, meta={"ramp_knots": knots, "resolved_rate_sessions_per_s": None}, cfg={"arrivals": {"kind": "ramp"}},
            requests=pd.DataFrame(), sessions=pd.DataFrame(), metrics=pd.DataFrame(), t_end_s=100.0)
    assert r.lam == 0.1
    c = Run(dir=tmp_path, meta={"resolved_rate_sessions_per_s": 0.2}, cfg={"arrivals": {"kind": "constant"}},
            requests=pd.DataFrame(), sessions=pd.DataFrame(), metrics=pd.DataFrame(), t_end_s=100.0)
    assert c.lam == 0.2


def test_controls_classify_with_the_frozen_endpoints():
    """The committed controls load and classify (no new data: these are the E2 runs the registrations pair with)."""
    ep = basin.load_endpoints(REPO / r14_cells.ENDPOINTS)
    p = load_params(REPO / r14_cells.PARAMS, [f"trap_v2.eval_from_s={r14_cells.REGISTERED_EVAL_FROM_S}"])
    res = r14_cells.classify([], ep, p)
    roles = sorted(r["role"] for r in res["rows"])
    assert roles.count("control_burst") == 3 and roles.count("control_noburst") == 3
    assert all(r["window_matches_endpoints"] for r in res["rows"])
    assert res["decision"]["toolslow"]["pass"] is None and res["decision"]["shed"]["pass"] is None     # no new runs yet


# ============================================================================================ job glue end to end (mock server)
def _local_hardware_string():
    r = subprocess.run([BASH, "-c", f'source "{(REPO / "slurm" / "common.sh").as_posix()}"; hardware_string'],
                       capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


@needs_bash
@pytest.mark.parametrize("cell,port", [("toolslow", 18195), ("shed", 18196)])
def test_r14_job_glue_runs_locally_against_the_mock_server(cell, port, tmp_path):
    """slurm/local_smoke.sh with R14_CELL: the real job glue (MODE=burst, the cell's one arm, E2_CONFIG = a mock-scale copy of the
    cell config registered by sha256 and arm), check-job, the run, and the in-job post-analysis (burst2 on a ramp run)."""
    env = dict(os.environ, ENV_GEN=Path(sys.prefix).as_posix(), RESULTS_ROOT=tmp_path.as_posix(), PORT=str(port), SEEDS="0", R14_CELL=cell,
               FAKE_CALIB_HW=_local_hardware_string())
    r = subprocess.run([BASH, str(REPO / "slurm" / "local_smoke.sh"), "burst"], capture_output=True, text=True, env=env,
                       timeout=300, cwd=REPO)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert "0 failed" in r.stdout and "PREREG_OK" in r.stdout and "analysis failed" not in r.stdout
    logs = list((tmp_path / "nova_job_logs").iterdir())
    run_dirs = (logs[0] / "run_dirs_burst.txt").read_text().split()
    assert len(run_dirs) == 1
    d = Path(run_dirs[0])
    meta = json.loads((d / "meta.json").read_text())
    pr = yaml.safe_load((tmp_path / "fake_calib" / "prereg.yaml").read_text())
    assert meta["prereg_sha256"] and pr["protocol"]["e2_config_sha256"] == prereg.config_text_sha256(d / "config.yaml")
    plan = pd.read_csv(d / "plan.csv", float_precision="round_trip")
    if cell == "toolslow":
        assert meta["arm"] == "noburst" and pr["protocol"]["arms"] == ["noburst"] and (plan["origin"] == "burst").sum() == 0
        tc = pd.read_csv(d / "tool_calls.csv", float_precision="round_trip")
        assert (tc["add_s"] == 1.0).sum() >= 3 and meta["outcome"]["tool_slowdown"]["n_tool_calls_slowed"] >= 3
    else:
        assert meta["arm"] == "burst" and pr["protocol"]["arms"] == ["burst"] and (plan["origin"] == "burst").sum() == 10
        b = plan[plan["origin"] == "base"]
        assert ((b["arrival_s"] >= 7.001) & (b["arrival_s"] < 9.0)).sum() == 0 and meta["resolved_rate_sessions_per_s"] is None
        assert load_run(d).lam == 1.5
        assert sorted((tmp_path / "agentload_analysis_burst2").iterdir())
