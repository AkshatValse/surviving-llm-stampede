"""r15 TOOLSLOW cells T1 (sglang-fcfs-r1-toolslow-d30w1800, 1.35 x, +30 s over [1200, 3000) s) and T2
(sglang-fcfs-r1-toolslow-d15-165, 1.65 x, +15 s over [1200, 2100) s): the two E2 configs, their registrations (fill reproduces
them; the scripted diff against the 2026-10-24 file; check-job and run_blockers bind the config bytes, the arm and the cell's own
rate), the job glue argv, and analysis/r15_cells.py (pairing against both rates' committed NOBURST plans, the stronger
manipulation check, the per-cell tri-state decision, an end-to-end classification of synthetic runs).

Mirrors tests/test_r14_extra.py; the r14 modules, configs, registrations and their tests are unchanged. No run of these cells
exists: every "run" here is synthetic (built in tmp_path) or a committed r14 / E2 control run read as it is."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import REPO

from agentload.client import TOOL_CALL_FIELDS, write_plan_csv
from agentload.config import load_config, resolve_rate
from agentload.workload import build_open_plan
from analysis import basin, prereg, r15_cells, r15_prereg
from analysis.params import load_params

DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
D30_CFG = REPO / "configs" / "agentload_e2_toolslow_d30.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
CAL = "prereg/inputs/2026-10-23/calibration.json"
LAM_REF = 0.07153402100919228
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")
CELL_KEYS = sorted(r15_prereg.CELLS)
MULTS = (1.35, 1.65)
CONTROLS = {m: r15_cells.find_controls(REPO / r15_cells.CONTROL_ROOT, rate_mult=m) for m in MULTS}
R14_RUNS = REPO / "results/nova/toolslow_shed_1716990x_pulled_20261101-154800/results/agentload_e2_burst"
R14_D30 = {0: "20261031-220113", 1: "20261031-220954", 2: "20261031-224211"}      # jobs 17169905-07 (COMMANDS.txt)
R14_D10 = {0: "20261031-210448", 1: "20261031-210648", 2: "20261031-215143"}      # jobs 17169902-04
R14_D30_CELL = {"t_s": 1200.0, "width_s": 900.0, "add_s": 30.0}
R14_D10_CELL = {"t_s": 1200.0, "width_s": 900.0, "add_s": 10.0}


def _label(cell_key):
    return r15_prereg.CELLS[cell_key]["label"]


def _rc(cell_key):
    return r15_cells.CELLS[_label(cell_key)]


def _other(m):
    return 1.65 if m == 1.35 else 1.35


# ============================================================================================ the cell tables
def test_the_two_cell_tables_agree():
    assert sorted(c["label"] for c in r15_prereg.CELLS.values()) == sorted(r15_cells.CELLS)
    assert r15_cells.RULE == r15_prereg.TRI_RULE
    for key, c in r15_prereg.CELLS.items():
        rc = r15_cells.CELLS[c["label"]]
        assert rc["key"] == c["id"] and rc["mult"] == c["mult"] and rc["arm"] == c["arms"][0] and list(rc["seeds"]) == c["seeds"]
        assert (rc["t_s"], rc["width_s"], rc["add_s"]) == (c["t_s"], c["width_s"], c["add_s"]) and rc["e2"] == c["e2"]
        assert rc["rule"] == r15_prereg.decision_rule(key) and "no conjunction" in rc["rule"]
    # T1 is the r14 d30 cell with only the window width changed; T2 the d30 window at half the delay, at the upper rate
    t1, t2 = r15_prereg.CELLS["toolslow-d30w1800"], r15_prereg.CELLS["toolslow-d15-165"]
    assert (t1["id"], t1["mult"], t1["t_s"], t1["width_s"], t1["add_s"]) == ("T1", 1.35, 1200, 1800, 30)
    assert (t2["id"], t2["mult"], t2["t_s"], t2["width_s"], t2["add_s"]) == ("T2", 1.65, 1200, 900, 15)
    assert t1["label"] == "sglang-fcfs-r1-toolslow-d30w1800" and t2["label"] == "sglang-fcfs-r1-toolslow-d15-165"


def test_no_hard_coded_rate_is_left():
    import inspect
    assert not hasattr(r15_cells, "MULT")
    sig = inspect.signature(r15_cells.find_controls)
    assert sig.parameters["rate_mult"].default is inspect.Parameter.empty      # every caller passes the cell's own rate
    assert sig.parameters["rate_mult"].kind is inspect.Parameter.KEYWORD_ONLY


# ============================================================================================ the two configs
@pytest.mark.parametrize("cell", CELL_KEYS)
def test_config_is_the_d30_config_with_only_the_slowdown_values_and_comments_changed(cell):
    c = r15_prereg.CELLS[cell]
    a, b = D30_CFG.read_bytes(), (REPO / c["e2"]).read_bytes()
    assert b"\r" not in b
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    old = ya["workload"].pop("tool_slowdown")
    new = yb["workload"].pop("tool_slowdown")
    assert old == {"t_s": 1200, "width_s": 900, "add_s": 30}
    assert new == {"t_s": c["t_s"], "width_s": c["width_s"], "add_s": c["add_s"]}
    assert sum(old[k] != new[k] for k in old) == 1                              # one factor changed from the d30 cell
    ya["meta"].pop("notes")
    assert yb["meta"].pop("notes").startswith("E2 NOBURST + TOOLSLOW d")
    assert ya == yb
    la, lb = a.split(b"\n"), b.split(b"\n")
    assert len(la) == len(lb)
    changed = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    i_ts = next(i for i, x in enumerate(lb) if x.startswith(b"  tool_slowdown:"))
    assert set(changed) <= set(range(i_ts - 4, i_ts + 1)) | {next(i for i, x in enumerate(lb) if x.startswith(b"  notes:"))}
    assert all(lb[i].startswith(b"  #") for i in changed if i_ts - 4 <= i < i_ts)
    cfg, _ = load_config(REPO / c["e2"], ["meta.arm=noburst", "arrivals.burst=null", f"arrivals.rate_mult={c['mult']}",
                                          f"arrivals.lambda_ref={LAM_REF}"])
    ts = cfg.workload.tool_slowdown
    assert (ts.t_s, ts.width_s, ts.add_s) == (c["t_s"], c["width_s"], c["add_s"]) and cfg.arrivals.burst is None
    assert ts.t_s + ts.width_s <= cfg.run.duration_s == 8700


def test_the_r14_d30_config_the_cells_are_copied_from_is_unchanged():
    """The sha256 the r14 d30 job banners print (jobs 17169905-07); the new configs are byte copies of this file."""
    assert hashlib.sha256(D30_CFG.read_bytes()).hexdigest() == "45dd1ba720ec1ccda415788e3108f23450c98bed8da471d789c8a674a01a0536"


# ============================================================================================ plans and CRN
def _plan(cfg_path, seed, *, mult):
    sets = [f"run.seed={seed}", f"arrivals.rate_mult={mult}", f"arrivals.lambda_ref=\"{CAL}:lambda_miss_turns_based\"",
            "arrivals.burst=null"]
    cfg, _ = load_config(Path(cfg_path), sets)
    return build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, resolve_rate(cfg.arrivals, REPO), [])


def _plan_file(plan, tmp_path, name):
    f = tmp_path / name
    write_plan_csv(f, plan)
    return f


def _read_plan(f):
    return pd.read_csv(f, float_precision="round_trip")


def test_controls_are_found_for_every_registered_seed_at_both_rates():
    for c in r15_cells.CELLS.values():
        assert all(("noburst", s) in CONTROLS[c["mult"]] and ("burst", s) in CONTROLS[c["mult"]] for s in c["seeds"])
    names = {m: sorted(d.name for (arm, _), d in CONTROLS[m].items() if arm == "noburst") for m in MULTS}
    assert names[1.35] == ["20261024-155125", "20261024-161834", "20261024-211253"]
    assert names[1.65] == ["20261024-160218", "20261024-184259", "20261025-000053"]


@pytest.mark.parametrize("cell", CELL_KEYS)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cell_plan_is_the_committed_noburst_plan_at_the_cells_rate(tmp_path, cell, seed):
    """Sessions exact, float columns within 1e-9 (the committed plans were drawn on Linux; numpy's exponential can differ in
    the last bit on Windows); byte-identical to the default E2 config's NOBURST plan built here. Not the other rate's plan."""
    c = r15_prereg.CELLS[cell]
    got = _plan_file(_plan(REPO / c["e2"], seed, mult=c["mult"]), tmp_path, "cell.csv")
    here = _plan_file(_plan(DEFAULT_CFG, seed, mult=c["mult"]), tmp_path, "default.csv")
    assert got.read_bytes() == here.read_bytes()
    ref = _read_plan(CONTROLS[c["mult"]][("noburst", seed)] / "plan.csv")
    d = r15_cells.plan_diff(_read_plan(got), ref)
    assert d["equal"] and d["max_abs_diff_s"] <= 1e-9 and len(ref) > 800, d
    assert not r15_cells.plans_equal(_read_plan(got), _read_plan(CONTROLS[_other(c["mult"])][("noburst", seed)] / "plan.csv"))


def test_plan_diff_tolerance_and_exact_columns():
    a = _read_plan(CONTROLS[1.35][("noburst", 0)] / "plan.csv")
    assert r15_cells.plan_diff(a, a.copy()) == {"equal": True, "max_abs_diff_s": 0.0, "plan_problem": ""}
    for col, eps, ok in (("tool_time_total_s", 5e-10, True), ("tool_time_total_s", 5e-9, False), ("arrival_s", 5e-10, True),
                         ("arrival_s", 5e-9, False)):
        b = a.copy()
        b.loc[7, col] += eps
        assert r15_cells.plans_equal(a, b) is ok, (col, eps)
    for mutate in (lambda b: b.assign(n_turns=b["n_turns"].where(b.index != 3, b["n_turns"] + 1)),
                   lambda b: b.assign(origin=b["origin"].where(b.index != 3, "burst")),
                   lambda b: b.assign(idx=b["idx"].where(b.index != 3, 10**6)),
                   lambda b: b.iloc[:-1], lambda b: b[list(b.columns[::-1])],
                   lambda b: b.assign(arrival_s=b["arrival_s"].where(b.index != 3, np.nan))):
        assert not r15_cells.plans_equal(a, mutate(a.copy()))


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_pairing_with_the_committed_noburst_plans_of_the_cells_rate(tmp_path, cell):
    c = r15_prereg.CELLS[cell]
    ctl = CONTROLS[c["mult"]]
    for seed in (0, 1, 2):
        d = tmp_path / f"s{seed}"
        d.mkdir()
        write_plan_csv(d / "plan.csv", _plan(REPO / c["e2"], seed, mult=c["mult"]))
        run = SimpleNamespace(dir=d)
        res = r15_cells.toolslow_pairing(run, ctl[("noburst", seed)])
        assert res["paired"] is True and res["pairing_problem"] == "" and res["plan_max_abs_diff_s"] <= 1e-9
        assert r15_cells.toolslow_pairing(run, ctl[("noburst", (seed + 1) % 3)])["paired"] is False      # another seed
        assert r15_cells.toolslow_pairing(run, CONTROLS[_other(c["mult"])][("noburst", seed)])["paired"] is False  # other rate
        assert r15_cells.toolslow_pairing(run, ctl[("burst", seed)])["paired"] is False                   # the BURST plan
    assert r15_cells.toolslow_pairing(SimpleNamespace(dir=tmp_path / "s0"), None)["paired"] is False
    empty = tmp_path / "noplan"
    empty.mkdir()
    res = r15_cells.toolslow_pairing(SimpleNamespace(dir=empty), ctl[("noburst", 0)])
    assert res["paired"] is False and "no plan.csv" in res["pairing_problem"]


def test_pairing_on_real_data_the_r14_toolslow_runs_are_byte_identical_to_their_controls():
    """The r14 TOOLSLOW runs (Nova, jobs 17169902-07) wrote plan.csv byte for byte equal to the 1.35 x NOBURST controls."""
    for runs in (R14_D10, R14_D30):
        for seed, name in runs.items():
            run = SimpleNamespace(dir=R14_RUNS / name)
            res = r15_cells.toolslow_pairing(run, CONTROLS[1.35][("noburst", seed)])
            assert res["paired"] and res["plan_bytes_identical"] and res["plan_max_abs_diff_s"] == 0.0
            assert not r15_cells.toolslow_pairing(run, CONTROLS[1.65][("noburst", seed)])["paired"]


# ============================================================================================ registrations
@pytest.mark.parametrize("cell", CELL_KEYS)
def test_registration_is_reproduced_by_fill_and_differs_from_the_parent_only_where_allowed(cell):
    c = r15_prereg.CELLS[cell]
    data = (REPO / c["out"]).read_bytes()
    assert b"\r" not in data
    assert r15_prereg.dump_registration(r15_prereg.fill_registration(cell)) == data
    pr = yaml.safe_load(data)
    assert pr["status"] == "FILLED" and pr["inputs"]["engine_cell_label"] == c["label"] and pr["inputs"]["e2_config"] == c["e2"]
    assert pr["protocol"]["arms"] == ["noburst"] and pr["lambda_selection"]["lambda_mults"] == [c["mult"]]
    assert pr["protocol"]["e2_config_sha256"] == hashlib.sha256((REPO / c["e2"]).read_bytes()).hexdigest()
    assert pr["measured"]["hardware"] == HW and pr["measured"]["n_cap"] == 20
    assert pr["measured"]["lambda_ref"] == LAM_REF and pr["lambda_selection"]["seeds"] == [0, 1, 2]
    assert not [x for x in prereg.validate(pr, load_params(REPO / "configs/agentload_analysis.yaml", []))
                if x["severity"] == "error"]
    diff = r15_prereg.registration_diff(yaml.safe_load(PARENT.read_text()), pr)
    assert diff["forbidden"] == []
    assert diff["derived"] == [f"predicted_boundaries.capped_drain.predicted_drain_s_by_mult.{_other(c['mult']):g}"]
    rule = pr["lambda_selection"]["rule"]
    assert r15_prereg.decision_rule(cell) in rule and r15_cells.CELLS[c["label"]]["rule"] in rule
    for phrase in ("configs/r11_basin_predict.yaml", "[5700, 8700)", f"{c['mult']:g} x lambda_ref",
                   f"lambda_selection.lambda_mults = [{c['mult']:g}]", c["e2"], "trapped 1 of its 3 seeds",
                   "after reading simulator outputs", "predicts that T1 TRAPS", "reliability test of the trigger",
                   "discriminates pred2 vs the simulator per seed", "no conjunction with any other cell",
                   f"[{c['t_s']}, {c['t_s'] + c['width_s']}) s", f"add_s = {c['add_s']}",
                   "configs/agentload_prereg_2026-10-31_toolslow_d30.yaml", "17169905-17169907"):
        assert phrase in rule, phrase
    assert "1.35 x lambda_ref" not in rule if c["mult"] == 1.65 else "1.65 x lambda_ref" not in rule


def test_lambda_mult_165_is_accepted_and_inside_the_registered_window():
    pr = yaml.safe_load((REPO / r15_prereg.CELLS["toolslow-d15-165"]["out"]).read_text())
    w = prereg.window_of(pr)
    assert (w["lo_mult"], w["hi_mult"]) == (1.0, 2.0) and prereg.mult_is_registered(pr, 1.65)
    assert not prereg.mult_is_registered(pr, 1.35) and prereg.lambda_in_window(pr, 1.65 * LAM_REF)
    assert 1.65 < pr["predicted_boundaries"]["capped_drain"]["max_lambda_mult"]


def _check_job(capsys, reg, cfg, label, arms="noburst", mults="1.35"):
    argv = ["check-job", str(reg), "--label", label, "--mults", mults, "--calib", str(REPO / CAL), "--hardware", HW,
            "--e2-config", str(cfg), "--duration-s", "8700", "--t-burst-s", "1200",
            "--params", str(REPO / "configs" / "agentload_analysis.yaml"), "--set", "trap_v2.eval_from_s=4500.0",
            "--allow-uncommitted"]
    if arms is not None:
        argv[4:4] = ["--arms", arms]
    rc = prereg.main(argv)
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_check_job_binds_the_config_bytes_the_arm_and_the_cells_rate(capsys, cell, tmp_path):
    c = r15_prereg.CELLS[cell]
    reg, cfg, m = REPO / c["out"], REPO / c["e2"], f"{c['mult']:g}"
    rc, out = _check_job(capsys, reg, cfg, c["label"], mults=m)
    assert rc == 0 and "PREREG_SHA256=" in out, out
    rc, out = _check_job(capsys, reg, cfg, c["label"], "burst", mults=m)
    assert rc == 1 and "not in the registered protocol.arms" in out
    rc, out = _check_job(capsys, reg, cfg, c["label"], None, mults=m)
    assert rc == 1 and "must pass explicit ARMS" in out
    for other_cfg in (DEFAULT_CFG, D30_CFG, REPO / r15_cells.CELLS[_label([k for k in CELL_KEYS if k != cell][0])]["e2"]):
        rc, out = _check_job(capsys, reg, other_cfg, c["label"], mults=m)            # same protocol fields, other bytes
        assert rc == 1 and "!= registered protocol.e2_config_sha256" in out and out.count("PREREG PROBLEM") == 1, other_cfg
    edited = tmp_path / "edited.yaml"
    edited.write_bytes(cfg.read_bytes().replace(b'notes: "E2', b'notes: "e2'))
    rc, out = _check_job(capsys, reg, edited, c["label"], mults=m)
    assert rc == 1 and "!= registered protocol.e2_config_sha256" in out
    rc, out = _check_job(capsys, reg, cfg, c["label"], mults=f"{_other(c['mult']):g}")
    assert rc == 1 and "not in the registered lambda_mults" in out
    rc, out = _check_job(capsys, reg, cfg, c["label"], mults="1.35 1.65")
    assert rc == 1 and "not in the registered lambda_mults" in out
    rc, out = _check_job(capsys, reg, cfg, "sglang-fcfs-r1-toolslow-d30", mults=m)
    assert rc == 1 and "!= registered cell" in out


def test_check_job_refuses_an_uncommitted_registration(capsys):
    """Until the lead commits the two files, a real job would stop at check-job (this is the only blocker then)."""
    for cell in CELL_KEYS:
        c = r15_prereg.CELLS[cell]
        prov = prereg.file_provenance(REPO / c["out"])
        if prov["committed_clean"]:
            continue                                         # committed: nothing to check here
        argv = ["check-job", str(REPO / c["out"]), "--arms", "noburst", "--label", c["label"], "--mults", f"{c['mult']:g}",
                "--calib", str(REPO / CAL), "--hardware", HW, "--e2-config", str(REPO / c["e2"]), "--duration-s", "8700",
                "--t-burst-s", "1200", "--params", str(REPO / "configs" / "agentload_analysis.yaml"),
                "--set", "trap_v2.eval_from_s=4500.0"]
        rc = prereg.main(argv)
        out = capsys.readouterr().out
        assert rc == 1 and out.count("PREREG PROBLEM") == 1 and "not committed" in out


def _fake_run(tmp_path, cfg_bytes, label, mult, arm="noburst"):
    d = tmp_path / f"run_{label}_{mult}"
    d.mkdir(exist_ok=True)
    (d / "config.yaml").write_bytes(cfg_bytes)
    cfg = yaml.safe_load(cfg_bytes)
    cfg["arrivals"]["burst"] = None
    cfg["run"]["duration_s"] = 8700
    return SimpleNamespace(dir=d, label=label, rate_mult=mult, lambda_ref_value=LAM_REF, uncached_tokens_ref_value=11243.179816372982,
                           hardware=HW, cfg=cfg, t_burst_ref=1200.0, arm=arm, arm_derived=arm, gate_n_cap=None,
                           prereg_sha256="x", t0_unix=4e9)


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_run_blockers_check_the_run_config_bytes_the_arm_and_the_rate(tmp_path, cell):
    c = r15_prereg.CELLS[cell]
    reg = REPO / c["out"]
    pr, prov = prereg.load_prereg(reg), prereg.file_provenance(reg)
    raw = (REPO / c["e2"]).read_bytes()
    run = _fake_run(tmp_path, raw, c["label"], c["mult"])
    run.prereg_sha256 = prov["sha256"]
    keep = lambda bl: [b for b in bl if "registration committed" not in b and "commit time unknown" not in b]   # noqa: E731
    assert keep(prereg.run_blockers(pr, prov, run)) == []
    (run.dir / "config.yaml").write_bytes(raw.replace(b"\n", b"\r\n"))                    # a Windows copy of the same text
    assert keep(prereg.run_blockers(pr, prov, run)) == []
    (run.dir / "config.yaml").write_bytes(D30_CFG.read_bytes())
    assert any("config.yaml sha256" in b for b in prereg.run_blockers(pr, prov, run))
    (run.dir / "config.yaml").write_bytes(raw)
    run.rate_mult = _other(c["mult"])
    assert any("not in the registered lambda_mults" in b for b in prereg.run_blockers(pr, prov, run))
    run.rate_mult = c["mult"]
    run.arm = run.arm_derived = "burst"
    assert any("not in the registered protocol.arms" in b for b in prereg.run_blockers(pr, prov, run))


# ============================================================================================ job glue argv
def _e2_argv(tmp_path, meta_argv, arm, e2_config, mult):
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
    lines.append(f'cd "$REPO_DIR" && e2_run {arm} {mult} 0 {tail}')
    r = subprocess.run([BASH, "-c", "\n".join(lines)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return [ln[4:] for ln in r.stdout.splitlines() if ln.startswith("ARG:")]


@needs_bash
@pytest.mark.parametrize("cell", CELL_KEYS)
def test_e2_run_argv_differs_from_the_committed_noburst_arm_only_in_the_config(tmp_path, cell):
    c = r15_prereg.CELLS[cell]
    m = f"{c['mult']:g}"
    meta = json.loads((CONTROLS[c["mult"]][("noburst", 0)] / "meta.json").read_text())
    got = _e2_argv(tmp_path, meta["argv"], "noburst", None, m)
    assert got == meta["argv"][1:]                                        # default: the committed run's argv at this rate
    got_c = _e2_argv(tmp_path, meta["argv"], "noburst", c["e2"], m)
    i = got_c.index("--config")
    assert got_c[i + 1] == c["e2"] and got_c[:i + 1] + got_c[i + 2:] == got[:i + 1] + got[i + 2:]
    sets = [got_c[k + 1] for k, a in enumerate(got_c) if a == "--set"]
    sets = [s for s in sets if not s.startswith(("server.", "meta.prereg"))]
    loaded, _ = load_config(REPO / c["e2"], sets)
    ts = loaded.workload.tool_slowdown
    assert loaded.meta.arm == "noburst" and math.isclose(loaded.arrivals.rate_mult, c["mult"]) and loaded.arrivals.burst is None
    assert (ts.t_s, ts.width_s, ts.add_s) == (c["t_s"], c["width_s"], c["add_s"])


def test_the_client_is_the_one_the_r14_toolslow_jobs_ran():
    """src/agentload in the working tree equals its tree at b006291 (tag r14-extra-reg, jobs 17169902-11)."""
    try:
        r = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "b006291", "--", "src/agentload"],
                           capture_output=True, timeout=60)
    except OSError as e:                                                    # pragma: no cover
        pytest.skip(f"git not available: {e}")
    if r.returncode not in (0, 1):
        pytest.skip(f"b006291 not available: {r.stderr!r}")
    assert r.returncode == 0
    assert TOOL_CALL_FIELDS == r15_cells.TOOL_CALL_COLUMNS


# ============================================================================================ manipulation check
def _tool_calls(rows):
    return pd.DataFrame(rows, columns=TOOL_CALL_FIELDS)


def _call(t, add, tool_s=2.5, sid=1, turn=1):
    return {"sid": sid, "origin": "base", "idx": sid, "turn": turn, "t_start": t, "tool_s": tool_s, "add_s": add,
            "t_ready": t + tool_s + add}


def _manip_run(tmp_path, cell, tc, *, meta_ts=None, counts=None, name="m"):
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    if tc is not None:
        tc.to_csv(d / "tool_calls.csv", index=False)
    ts = meta_ts if meta_ts is not None else {"t_s": float(cell["t_s"]), "width_s": float(cell["width_s"]),
                                              "add_s": float(cell["add_s"]), "log": "tool_calls.csv"}
    n = 0 if tc is None else len(tc)
    ns = 0 if tc is None else int((tc["add_s"] > 0).sum())
    oc = counts if counts is not None else {"n_tool_calls": n, "n_tool_calls_slowed": ns}
    return SimpleNamespace(dir=d, meta={"tool_slowdown": ts, "outcome": {"tool_slowdown": oc}})


def _good_calls(cell):
    t_s, t_e, dl = cell["t_s"], cell["t_s"] + cell["width_s"], cell["add_s"]
    rows = [_call(t, 0.0, sid=i) for i, t in enumerate((5.0, 600.0, t_s - 1e-6, t_e, t_e + 0.5, 8000.0))]
    rows += [_call(t, dl, sid=100 + i) for i, t in enumerate((t_s, t_s + 1.0, (t_s + t_e) / 2, t_e - 1e-6))]
    return rows


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_manipulation_check_passes_only_when_every_call_is_slowed_exactly_as_registered(tmp_path, cell):
    c = _rc(cell)
    t_s, t_e, dl = c["t_s"], c["t_s"] + c["width_s"], c["add_s"]
    good = _good_calls(c)
    res = r15_cells.manipulation_check(_manip_run(tmp_path, c, _tool_calls(good), name="ok"), c)
    assert res["manipulation_ok"] is True and res["manipulation_problem"] == "", res
    assert res["n_tool_calls_in_window"] == res["n_tool_calls_slowed"] == 4 and res["n_tool_calls"] == 10
    assert res["slowed_t_start_min"] == t_s and res["slowed_t_start_max"] == t_e - 1e-6 and res["add_s_values"] == [0.0, dl]
    cases = {
        "a call inside the window not slowed": good + [_call(t_s + 5.0, 0.0, sid=200)],
        "a call inside the window with another delay": good + [_call(t_s + 5.0, dl / 2, sid=201)],
        "a call at the window end slowed": good + [_call(t_e, dl, sid=202)],
        "a call before the window slowed": good + [_call(t_s - 1.0, dl, sid=203)],
        "a call after the window with a tiny add": good + [_call(t_e + 100.0, 1e-3, sid=204)],
        "no call inside the window": [r for r in good if not (t_s <= r["t_start"] < t_e)],
        "a NaN start time": good + [_call(float("nan"), 0.0, sid=205)],
    }
    want = {"a call inside the window not slowed": "have add_s !=", "a call inside the window with another delay": "have add_s !=",
            "a call at the window end slowed": "outside", "a call before the window slowed": "outside",
            "a call after the window with a tiny add": "outside", "no call inside the window": "did not happen",
            "a NaN start time": "non-numeric"}
    for k, rows in cases.items():
        res = r15_cells.manipulation_check(_manip_run(tmp_path, c, _tool_calls(rows), name=k.replace(" ", "_")), c)
        assert res["manipulation_ok"] is False and want[k] in res["manipulation_problem"], (k, res["manipulation_problem"])
    bad_ready = [dict(r) for r in good]
    bad_ready[-1]["t_ready"] -= dl                                          # the delay logged but not applied
    res = r15_cells.manipulation_check(_manip_run(tmp_path, c, _tool_calls(bad_ready), name="ready"), c)
    assert not res["manipulation_ok"] and "t_ready" in res["manipulation_problem"] and res["t_ready_consistent"] is False


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_manipulation_check_needs_the_cells_meta_block_and_the_complete_log(tmp_path, cell):
    c = _rc(cell)
    tc = _tool_calls(_good_calls(c))
    for name, ts in (("r14_d30", R14_D30_CELL), ("none", {}),            # the r14 d30 block: other width (T1) / delay (T2)
                     ("width", {**{k: c[k] for k in ("t_s", "add_s")}, "width_s": c["width_s"] + 1}),
                     ("start", {**{k: c[k] for k in ("width_s", "add_s")}, "t_s": c["t_s"] + 1}),
                     ("add", {**{k: c[k] for k in ("t_s", "width_s")}, "add_s": c["add_s"] + 1}),
                     ("string", {"t_s": str(c["t_s"]), "width_s": c["width_s"], "add_s": c["add_s"]})):
        res = r15_cells.manipulation_check(_manip_run(tmp_path, c, tc, meta_ts=ts, name=f"meta_{name}"), c)
        assert not res["manipulation_ok"] and "meta.tool_slowdown" in res["manipulation_problem"], name
    for i, counts in enumerate(({"n_tool_calls": len(tc) + 1, "n_tool_calls_slowed": 4},
                                {"n_tool_calls": len(tc), "n_tool_calls_slowed": 3}, {})):
        res = r15_cells.manipulation_check(_manip_run(tmp_path, c, tc, counts=counts, name=f"counts_{i}"), c)
        assert not res["manipulation_ok"] and "not the complete log" in res["manipulation_problem"], counts
    res = r15_cells.manipulation_check(_manip_run(tmp_path, c, None, name="nofile"), c)
    assert not res["manipulation_ok"] and "tool_calls.csv missing" in res["manipulation_problem"]
    run = _manip_run(tmp_path, c, tc, name="cols")
    tc.drop(columns=["t_ready"]).to_csv(run.dir / "tool_calls.csv", index=False)
    res = r15_cells.manipulation_check(run, c)
    assert not res["manipulation_ok"] and "columns" in res["manipulation_problem"]


def test_manipulation_check_on_real_data_the_r14_toolslow_runs():
    """The committed r14 runs pass the stronger check with their own registered blocks (every call starting in [1200, 2100)
    took +d, none outside, complete logs), and fail it as T1 / T2 runs (wrong window or delay; wrong meta block)."""
    def r14_run(name):                                   # what manipulation_check reads: the run dir and its meta.json
        return SimpleNamespace(dir=R14_RUNS / name, meta=json.loads((R14_RUNS / name / "meta.json").read_text()))

    for runs, cell in ((R14_D30, R14_D30_CELL), (R14_D10, R14_D10_CELL)):
        for seed, name in runs.items():
            res = r15_cells.manipulation_check(r14_run(name), cell)
            assert res["manipulation_ok"], (name, res["manipulation_problem"])
            assert res["n_tool_calls_in_window"] == res["n_tool_calls_slowed"] > 500 and res["n_outside_add_nonzero"] == 0
            assert res["tool_log_complete"] and res["t_ready_consistent"]
    r = r14_run(R14_D30[2])
    res = r15_cells.manipulation_check(r, _rc("toolslow-d30w1800"))
    assert not res["manipulation_ok"] and res["n_in_window_add_not_delta"] > 500          # calls in [2100, 3000) took +0 s
    res = r15_cells.manipulation_check(r, _rc("toolslow-d15-165"))
    assert not res["manipulation_ok"] and res["n_in_window_add_not_delta"] == res["n_tool_calls_in_window"]   # +30, not +15


# ============================================================================================ decision
def _rec(label, seed, stuck=False, good=False, counted=True, **kw):
    return {"role": "new", "label": label, "seed": seed, "stuck": stuck, "good": good, "counted": counted, **kw}


L1, L2 = _label("toolslow-d30w1800"), _label("toolslow-d15-165")
S, G, N, B = (True, False), (False, True), (False, False), (True, True)       # (stuck, good) of one seed


def _rows(label, states):
    return [_rec(label, seed, stuck=st, good=gd) for seed, (st, gd) in states.items()]


def test_outcome_of_is_the_registered_tri_state_rule():
    for stuck, good in itertools.product(range(4), range(4)):
        want = ("TRAPS" if stuck >= 2 and good < 2 else "NO-TRAP" if good >= 2 and stuck < 2 else "MIXED")
        assert r15_cells.outcome_of(stuck, good, 2) == want


def test_decision_each_cell_alone_with_three_seeds():
    d = r15_cells.decision(_rows(L1, {0: S, 1: S, 2: G}) + _rows(L2, {0: G, 1: G, 2: S}))
    t1, t2 = d["cells"]["T1"], d["cells"]["T2"]
    assert (t1["outcome"], t2["outcome"]) == ("TRAPS", "NO-TRAP")                  # no conjunction: each its own call
    assert t1["need"] == t2["need"] == 2 and t1["mult"] == 1.35 and t2["mult"] == 1.65
    assert t1["rule"] == r15_cells.CELLS[L1]["rule"] and t2["rule"] == r15_cells.CELLS[L2]["rule"]
    assert t1["stuck_seeds"] == [0, 1] and t1["good_seeds"] == [2] and t1["possible_outcomes"] == ["TRAPS"]
    for states, want in (({0: S, 1: G, 2: N}, "MIXED"), ({0: S, 1: S, 2: S}, "TRAPS"), ({0: G, 1: G, 2: G}, "NO-TRAP"),
                         ({0: N, 1: N, 2: N}, "MIXED"), ({0: S, 1: N, 2: N}, "MIXED"), ({0: B, 1: S, 2: G}, "MIXED"),
                         ({0: B, 1: S, 2: N}, "TRAPS"), ({0: B, 1: B, 2: N}, "MIXED"), ({0: G, 1: N, 2: G}, "NO-TRAP")):
        c = r15_cells.decision(_rows(L1, states))["cells"]["T1"]
        assert c["outcome"] == c["outcome_if_missing_count_against"] == want, (states, c)
        assert r15_cells.decision(_rows(L1, states))["cells"]["T2"]["outcome"] is None        # T2 has no runs


def test_decision_with_missing_seeds_waits_until_the_present_seeds_decide():
    d = r15_cells.decision(_rows(L1, {0: S, 1: S}))["cells"]["T1"]
    assert d["outcome"] == "TRAPS" and d["missing_seeds"] == [2]                    # 2 STUCK: nothing seed 2 does changes it
    d = r15_cells.decision(_rows(L1, {0: G, 1: G}))["cells"]["T1"]
    assert d["outcome"] == "NO-TRAP"
    d = r15_cells.decision(_rows(L1, {0: S, 1: G}))["cells"]["T1"]
    assert d["outcome"] is None and d["possible_outcomes"] == ["TRAPS", "NO-TRAP", "MIXED"]
    assert d["outcome_if_missing_count_against"] == "MIXED"                         # a seed without a counted run counts against
    d = r15_cells.decision(_rows(L1, {0: S, 1: N}))["cells"]["T1"]
    assert d["outcome"] is None and d["possible_outcomes"] == ["TRAPS", "MIXED"]
    d = r15_cells.decision(_rows(L1, {0: N, 1: N}))["cells"]["T1"]
    assert d["outcome"] == "MIXED"                                                   # one seed left cannot reach 2 of 3
    d = r15_cells.decision([])["cells"]["T1"]
    assert d["outcome"] is None and d["outcome_if_missing_count_against"] == "MIXED" and d["missing_seeds"] == [0, 1, 2]
    # exhaustive: a decided outcome is the outcome of every completion of the missing seeds
    for k in range(4):
        for present in itertools.combinations((0, 1, 2), k):
            for states in itertools.product((S, G, N, B), repeat=k):
                rows = _rows(L1, dict(zip(present, states)))
                got = r15_cells.decision(rows)["cells"]["T1"]
                missing = [s for s in (0, 1, 2) if s not in present]
                finals = {r15_cells.decision(rows + _rows(L1, dict(zip(missing, more))))["cells"]["T1"]["outcome"]
                          for more in itertools.product((S, G, N, B), repeat=len(missing))}
                assert set(got["possible_outcomes"]) == finals
                assert got["outcome"] == (finals.pop() if len(finals) == 1 else None)


def test_decision_counts_only_counted_runs_of_registered_seeds_and_no_seed_twice():
    rows = _rows(L1, {0: S, 1: S, 2: G}) + [_rec(L1, 2, stuck=True, counted=False), _rec(L1, 3, stuck=True)]
    d = r15_cells.decision(rows)["cells"]["T1"]
    assert d["stuck"] == 2 and d["good"] == 1 and d["outcome"] == "TRAPS" and d["seeds_present"] == [0, 1, 2]
    rows = _rows(L1, {0: G, 1: S, 2: S}) + [_rec(L1, 0, good=True)]                # a resubmitted seed 0
    d = r15_cells.decision(rows)["cells"]["T1"]
    assert d["duplicate_seeds"] == [0] and d["outcome"] is None and d["outcome_if_missing_count_against"] is None
    assert r15_cells.decision(rows[:-1])["cells"]["T1"]["outcome"] == "TRAPS"
    rows = _rows(L1, {0: S, 1: S}) + [dict(r, role="control_noburst") for r in _rows(L1, {2: G})]   # controls never vote
    assert r15_cells.decision(rows)["cells"]["T1"]["seeds_present"] == [0, 1]


# ============================================================================================ classification
def _ep_p():
    ep = basin.load_endpoints(REPO / r15_cells.ENDPOINTS)
    p = load_params(REPO / r15_cells.PARAMS, [f"trap_v2.eval_from_s={r15_cells.REGISTERED_EVAL_FROM_S}"])
    return ep, p


def test_frozen_endpoints_are_the_basin_files_and_agree_with_the_registered_constants():
    ep, p = _ep_p()
    assert ep["eval_window_s"] == [5700.0, 8700.0] and ep["stuck_hit_below"] == 0.2 and ep["good_hit_above"] == 0.8
    assert basin.endpoint_problems(ep, p) == []


def test_controls_at_both_rates_classify_with_the_frozen_endpoints():
    """The committed controls load and classify (no new data: the E2 runs the registrations pair with). The NOBURST controls
    of both rates are GOOD (the CRN baseline of each cell); the BURST controls, reported beside them, are STUCK."""
    ep, p = _ep_p()
    res = r15_cells.classify([], ep, p)
    rows = res["rows"]
    assert sorted((r["role"], r["control_mult"]) for r in rows) == sorted(
        [(f"control_{a}", m) for a in ("burst", "noburst") for m in MULTS for _ in range(3)])
    assert all(r["window_matches_endpoints"] and r["counted"] is False for r in rows)
    for r in rows:
        assert math.isclose(r["rate_mult"], r["control_mult"])
        assert r["basin_state"] == ("good" if r["role"] == "control_noburst" else "stuck"), r["run_dir"]
    assert set(res["by_seed"]["0"]) == {"control_burst@1.35", "control_noburst@1.35", "control_burst@1.65", "control_noburst@1.65"}
    for key in ("T1", "T2"):
        c = res["decision"]["cells"][key]
        assert c["outcome"] is None and c["possible_outcomes"] == ["TRAPS", "NO-TRAP", "MIXED"]
    assert res["endpoint_problems"] == []


def _synthetic_run(tmp_path, cell_key, source_mult, seed, name, *, delta=None):
    """A run dir built from the committed NOBURST control at ``source_mult`` (its requests / sessions / plan, so its basin
    state is the control's), relabelled as the cell, with the cell's config bytes, its meta.tool_slowdown block and a
    synthetic tool_calls.csv (one call per completed non-final turn, starting at the turn's completion, +delta inside the
    window). Bound to the cell's registration by sha256. Never a GPU run."""
    c = r15_prereg.CELLS[cell_key]
    rc = r15_cells.CELLS[c["label"]]
    src = CONTROLS[source_mult][("noburst", seed)]
    d = tmp_path / name
    d.mkdir()
    for f in ("config_effective.yaml", "plan.csv", "requests.csv", "sessions.csv"):
        shutil.copyfile(src / f, d / f)
    (d / "config.yaml").write_bytes((REPO / c["e2"]).read_bytes())
    req = pd.read_csv(src / "requests.csv")
    ok = req[(req["status"] == "ok") & (req["turn"] < req["n_turns"])].sort_values("t_complete")
    dl = rc["add_s"] if delta is None else delta
    t = ok["t_complete"].to_numpy(float)
    add = np.where((t >= rc["t_s"]) & (t < rc["t_s"] + rc["width_s"]), dl, 0.0)
    tool_s = np.full(len(t), 5.0)
    tc = pd.DataFrame({"sid": ok["sid"].to_numpy(), "origin": ok["origin"].to_numpy(), "idx": ok["sid"].to_numpy(),
                       "turn": ok["turn"].to_numpy(), "t_start": t, "tool_s": tool_s, "add_s": add, "t_ready": t + tool_s + add})
    tc.to_csv(d / "tool_calls.csv", index=False)
    meta = json.loads((src / "meta.json").read_text())
    meta["engine_label"] = c["label"]
    meta["prereg_file"] = c["out"]
    meta["prereg_sha256"] = hashlib.sha256((REPO / c["out"]).read_bytes()).hexdigest()
    meta["tool_slowdown"] = {"t_s": float(rc["t_s"]), "width_s": float(rc["width_s"]), "add_s": float(rc["add_s"]),
                             "applies_to": "tool calls whose sleep starts in [t_s, t_s + width_s)", "log": "tool_calls.csv"}
    meta["outcome"]["tool_slowdown"] = {"n_tool_calls": int(len(tc)), "n_tool_calls_slowed": int((add > 0).sum())}
    (d / "meta.json").write_text(json.dumps(meta, indent=2))
    return d


@pytest.fixture
def committed_registrations(monkeypatch):
    """Provenance of the two registration files as if committed (at unix time 1.7e9, before any control run started); they
    are not committed yet, so without this no synthetic run could be bound."""
    real = prereg.file_provenance

    def fake(path):
        out = real(path)
        out.update(git_last_commit="0" * 40, git_last_commit_unix=1.7e9, git_first_commit_unix=1.7e9, git_tracked=True,
                   git_modified_since_commit=False, committed_clean=True)
        return out
    monkeypatch.setattr(r15_cells.prereg_mod, "file_provenance", fake)
    return [str(REPO / c["out"]) for c in r15_prereg.CELLS.values()]


def test_classify_end_to_end_counts_a_bound_paired_manipulated_run_at_the_cells_rate(tmp_path, committed_registrations):
    ep, p = _ep_p()
    runs = {("toolslow-d30w1800", 0): _synthetic_run(tmp_path, "toolslow-d30w1800", 1.35, 0, "t1_s0"),
            ("toolslow-d15-165", 1): _synthetic_run(tmp_path, "toolslow-d15-165", 1.65, 1, "t2_s1")}
    res = r15_cells.classify(list(runs.values()), ep, p, preregs=committed_registrations)
    new = {(r["cell"], r["seed"]): r for r in res["rows"] if r["role"] == "new"}
    for (cell, seed), d in runs.items():
        r = new[(r15_prereg.CELLS[cell]["id"], seed)]
        assert r["counted"] is True and r["problem"] == "", r["problem"]
        assert r["paired"] and r["plan_bytes_identical"] and r["manipulation_ok"] and r["prereg_bound"]
        assert math.isclose(r["rate_mult"], r15_prereg.CELLS[cell]["mult"]) and r["basin_state"] == "good"   # the control's data
        assert math.isclose(r["slope_threshold"], 0.5 * (r15_prereg.CELLS[cell]["mult"] - 1.0) * LAM_REF, rel_tol=1e-9)
    dec = res["decision"]["cells"]
    assert dec["T1"]["seeds_present"] == [0] and dec["T1"]["good"] == 1 and dec["T1"]["outcome"] is None
    assert dec["T2"]["seeds_present"] == [1] and dec["T2"]["possible_outcomes"] == ["TRAPS", "NO-TRAP", "MIXED"]
    assert res["by_seed"]["0"]["T1"] == "good" and res["by_seed"]["1"]["T2"] == "good"


def test_classify_end_to_end_refuses_a_run_at_the_other_cells_rate_or_without_the_manipulation(tmp_path, committed_registrations):
    ep, p = _ep_p()
    wrong_rate = _synthetic_run(tmp_path, "toolslow-d15-165", 1.35, 0, "t2_at_135")       # T2 labelled, 1.35 x data
    wrong_rate1 = _synthetic_run(tmp_path, "toolslow-d30w1800", 1.65, 2, "t1_at_165")     # T1 labelled, 1.65 x data
    no_delay = _synthetic_run(tmp_path, "toolslow-d30w1800", 1.35, 1, "t1_nodelay", delta=0.0)
    unbound = _synthetic_run(tmp_path, "toolslow-d15-165", 1.65, 2, "t2_unbound")
    meta = json.loads((unbound / "meta.json").read_text())
    meta["prereg_sha256"] = "0" * 64
    (unbound / "meta.json").write_text(json.dumps(meta))
    res = r15_cells.classify([wrong_rate, wrong_rate1, no_delay, unbound], ep, p, preregs=committed_registrations)
    new = {Path(r["run_dir"]).name: r for r in res["rows"] if r["role"] == "new"}
    for name in ("t2_at_135", "t1_at_165"):
        r = new[name]
        assert r["counted"] is False and "rate_mult" in r["problem"] and "not in the registered lambda_mults" in r["problem"]
        assert r["paired"] is False and "plan.csv differs" in r["problem"]
    assert new["t1_nodelay"]["counted"] is False and "manipulation check failed" in new["t1_nodelay"]["problem"]
    assert new["t1_nodelay"]["paired"] is True and new["t1_nodelay"]["prereg_bound"] is True
    assert new["t2_unbound"]["counted"] is False and "not bound to this file" in new["t2_unbound"]["problem"]
    for key in ("T1", "T2"):
        assert res["decision"]["cells"][key]["seeds_present"] == []


def test_classify_does_not_count_a_run_whose_binding_was_not_checked(tmp_path):
    ep, p = _ep_p()
    d = _synthetic_run(tmp_path, "toolslow-d30w1800", 1.35, 0, "t1_noprereg")
    res = r15_cells.classify([d], ep, p, preregs=[])
    r = next(x for x in res["rows"] if x["role"] == "new")
    assert r["counted"] is False and "binding not checked" in r["problem"] and r["manipulation_ok"] and r["paired"]
    other = tmp_path / "other_label"
    shutil.copytree(d, other)
    meta = json.loads((other / "meta.json").read_text())
    meta["engine_label"] = "sglang-fcfs-r1-toolslow-d30"
    (other / "meta.json").write_text(json.dumps(meta))
    r = next(x for x in r15_cells.classify([other], ep, p)["rows"] if x["role"] == "new")
    assert r["counted"] is False and "is not an r15 cell" in r["problem"]


def test_cli_writes_the_outputs_and_checks_the_binding_of_both_cells_by_default(tmp_path):
    d = _synthetic_run(tmp_path, "toolslow-d15-165", 1.65, 0, "t2_cli")
    out_root = tmp_path / "out"
    rc = r15_cells.main(["classify", "--run-dirs", str(d), "--out-root", str(out_root)])
    assert rc == 0
    (od,) = list((out_root / "agentload_analysis_r15").iterdir())
    runs = pd.read_csv(od / "r15_runs.csv")
    v = json.loads((od / "r15_verdict.json").read_text())
    assert set(v["decision"]["cells"]) == {"T1", "T2"} and (od / "meta.json").is_file()
    new = runs[runs["role"] == "new"].iloc[0]
    assert bool(new["manipulation_ok"]) and bool(new["paired"])
    # the default --prereg is the two registrations: the binding is checked, and this synthetic run (its start time is the
    # control's, 2026-10-24) can never be bound, before or after the registrations are committed
    assert bool(new["counted"]) is False and "not bound to its registration" in str(new["problem"])
    assert all((REPO / c["out"]).is_file() for c in r15_prereg.CELLS.values())


@pytest.mark.parametrize("cell", CELL_KEYS)
def test_prereg_cli_refuses_to_overwrite_and_its_diff_has_nothing_forbidden(tmp_path, cell, capsys):
    c = r15_prereg.CELLS[cell]
    before = (REPO / c["out"]).read_bytes()
    assert r15_prereg.main(["fill", "--cell", cell]) == 2 and (REPO / c["out"]).read_bytes() == before
    out = tmp_path / "again.yaml"
    assert r15_prereg.main(["fill", "--cell", cell, "--out", str(out)]) == 0 and out.read_bytes() == before
    assert r15_prereg.main(["diff", "--cell", cell]) == 0
    assert "forbidden: 0" in capsys.readouterr().out
