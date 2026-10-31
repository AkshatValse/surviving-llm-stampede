"""B1 basin test (r11): the n=100 / n=25 E2 configs, their registrations, the E2_CONFIG job glue and analysis/basin.py.

No engine anywhere: plans come from the generator's own plan code, check-job is the real CLI, and the job-glue argv test runs
the real ``e2_run`` / ``run_gen`` of slurm/common.sh with ``gen_python`` stubbed out."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import REPO

from analysis import basin, prereg
from analysis.params import load_params

NS = (100, 25)
DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
CAL = "prereg/inputs/2026-10-23/calibration.json"
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
BASE_RUNS = REPO / basin.BASELINE_RUN_ROOT
BURST200_165 = {0: "20261024-155120", 1: "20261024-184132", 2: "20261025-000043"}     # committed BURST n=200, 1.65 x
NOBURST_165 = {0: "20261024-160218", 1: "20261024-184259", 2: "20261025-000053"}       # committed NOBURST, 1.65 x
BASH = shutil.which("bash")


def cfg_path(n):
    return REPO / "configs" / f"agentload_e2_burst_n{n}.yaml"


def reg_path(n):
    return REPO / "configs" / f"agentload_prereg_2026-10-30_b{n}.yaml"


# ---------------------------------------------------------------- configs
@pytest.mark.parametrize("n", NS)
def test_cell_config_is_a_byte_copy_except_burst_n(n):
    a, b = DEFAULT_CFG.read_bytes(), cfg_path(n).read_bytes()
    assert b"\r" not in b
    la, lb = a.split(b"\n"), b.split(b"\n")
    assert len(la) == len(lb)
    diff = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    assert len(diff) == 1
    old, new = la[diff[0]], lb[diff[0]]
    assert old.startswith(b"  burst: {n: 200, t_s: 1200, width_s: 60}")
    assert new.startswith(b"  burst: {n: %d, t_s: 1200, width_s: 60}" % n)
    assert old.split(b"#", 1)[1] == new.split(b"#", 1)[1]                  # comment unchanged
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    assert yb["arrivals"]["burst"] == {"n": n, "t_s": 1200, "width_s": 60}
    yb["arrivals"]["burst"]["n"] = 200
    assert ya == yb


# ---------------------------------------------------------------- plans: common random numbers with the committed E2
def _base(plan):
    return [(s.idx, repr(s.arrival_s), s.n_turns, tuple(repr(t) for t in s.tool_times_s)) for s in plan if s.origin == "base"]


def _burst_times(plan):
    return sorted(s.arrival_s for s in plan if s.origin == "burst")


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cell_plans_share_base_sessions_and_draw_burst_times_as_a_subset(seed):
    p200 = basin.basin_plan(DEFAULT_CFG, seed)
    p0 = basin.basin_plan(DEFAULT_CFG, seed, burst_null=True)
    assert sum(s.origin == "burst" for s in p200) == 200 and not any(s.origin == "burst" for s in p0)
    b200 = _burst_times(p200)
    for n in NS:
        pn = basin.basin_plan(cfg_path(n), seed)
        assert _base(pn) == _base(p200) == _base(p0)                       # byte-identical base sessions
        bn = _burst_times(pn)
        assert len(bn) == n and set(bn) <= set(b200)                       # burst starts: the first n draws of the 200
        assert all(1200.0 <= t < 1260.0 for t in bn)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_generated_n200_and_noburst_plans_equal_the_committed_e2_plans(seed):
    import csv

    for runs, burst_null in ((BURST200_165, False), (NOBURST_165, True)):
        d = BASE_RUNS / runs[seed]
        meta = json.loads((d / "meta.json").read_text())
        assert meta["seeds"] == [seed] and "arrivals.rate_mult=1.65" in meta["argv"]
        with (d / "plan.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        plan = basin.basin_plan(DEFAULT_CFG, seed, burst_null=burst_null)
        assert len(rows) == len(plan)
        for r, s in zip(rows, plan):
            assert (int(r["sid"]), r["origin"], int(r["idx"]), int(r["n_turns"])) == (s.sid, s.origin, s.idx, s.n_turns)
            assert float(r["arrival_s"]) == s.arrival_s
            assert math.isclose(float(r["tool_time_total_s"]), sum(s.tool_times_s), rel_tol=0, abs_tol=1e-9)


# ---------------------------------------------------------------- registrations
@pytest.mark.parametrize("n", NS)
def test_registration_is_reproduced_by_fill_and_is_valid(n):
    data = reg_path(n).read_bytes()
    assert b"\r" not in data
    assert basin.dump_registration(basin.fill_registration(n)) == data
    pr = prereg.load_prereg(reg_path(n))
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", [])
    errs = [x for x in prereg.validate(pr, p, "fcfs", prereg_path=reg_path(n)) if x["severity"] == "error"]
    assert errs == []
    assert pr["status"] == "FILLED"
    assert pr["inputs"]["engine_cell_label"] == f"sglang-fcfs-r1-b{n}"
    assert pr["inputs"]["e2_config"] == f"configs/agentload_e2_burst_n{n}.yaml"
    assert pr["protocol"] == {"duration_s": 8700, "t_burst_s": 1200, "burst_n": n, "burst_width_s": 60}
    assert pr["lambda_selection"]["lambda_mults"] == [1.65]
    assert pr["measured"]["n_cap"] == 20
    rule = pr["lambda_selection"]["rule"]
    for needle in ("STUCK := hit_eval < 0.2", "GOOD := trap_v2 RECOVERED", "[5700, 8700)", "configs/r11_basin_predict.yaml",
                   "17093387-404"):
        assert needle in rule


@pytest.mark.parametrize("n", NS)
def test_registration_differs_from_the_2026_10_24_file_only_where_allowed(n):
    d = basin.registration_diff(prereg.load_prereg(PARENT), prereg.load_prereg(reg_path(n)))
    assert d["forbidden"] == []
    assert sorted(d["allowed"]) == sorted(basin.REGISTRATION_DIFF_ALLOWED)
    assert all(k.startswith("predicted_boundaries.capped_drain.") for k in d["derived"])
    # same inputs, measurements, window, pass rule, kill conditions
    a, b = prereg.load_prereg(PARENT), prereg.load_prereg(reg_path(n))
    for sec in ("measured", "pass_rule", "kill_conditions", "predictions", "checks", "fill_problems"):
        assert a[sec] == b[sec], sec
    for k in ("mu_curve_json", "calibration_json", "e0b_bracket_json"):
        assert a["inputs"][k] == b["inputs"][k]


# ---------------------------------------------------------------- check-job
def _check_job(capsys, reg, cfg, label):
    rc = prereg.main(["check-job", str(reg), "--label", label, "--mults", "1.65", "--arms", "burst", "--calib", str(REPO / CAL),
                      "--hardware", HW, "--e2-config", str(cfg), "--duration-s", "8700", "--t-burst-s", "1200",
                      "--params", str(REPO / "configs" / "agentload_analysis.yaml"), "--set", "trap_v2.eval_from_s=4500.0",
                      "--allow-uncommitted"])
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("n", NS)
def test_check_job_accepts_the_cell_config_with_its_registration(capsys, n):
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), f"sglang-fcfs-r1-b{n}")
    assert rc == 0, out
    assert "PREREG_SHA256=" in out


@pytest.mark.parametrize("n", NS)
def test_check_job_refuses_the_default_config_under_the_cell_registration(capsys, n):
    rc, out = _check_job(capsys, reg_path(n), DEFAULT_CFG, f"sglang-fcfs-r1-b{n}")
    assert rc == 1
    assert f"E2 config burst.n=200 != registered protocol {n}" in out
    assert out.count("PREREG PROBLEM") == 1


@pytest.mark.parametrize("n", NS)
def test_check_job_refuses_the_cell_config_under_the_2026_10_24_registration(capsys, n):
    rc, out = _check_job(capsys, PARENT, cfg_path(n), f"sglang-fcfs-r1-b{n}")
    assert rc == 1
    assert "!= registered cell 'sglang-fcfs-r1'" in out and f"E2 config burst.n={n} != registered protocol 200" in out
    rc, out = _check_job(capsys, PARENT, cfg_path(n), "sglang-fcfs-r1")     # even under the registered label: burst.n
    assert rc == 1 and f"E2 config burst.n={n} != registered protocol 200" in out and out.count("PREREG PROBLEM") == 1


def test_check_job_default_config_still_passes_the_2026_10_24_registration(capsys):
    rc, out = _check_job(capsys, PARENT, DEFAULT_CFG, "sglang-fcfs-r1")
    assert rc == 0, out


# ---------------------------------------------------------------- job glue
def test_common_sh_wires_e2_config():
    text = (REPO / "slurm" / "common.sh").read_text()
    assert "E2_CONFIG_DEFAULT=configs/agentload_e2_burst.yaml" in text
    assert ': "${E2_CONFIG:=$E2_CONFIG_DEFAULT}"' in text
    assert '[ -f "$E2_CONFIG" ] || die' in text
    assert 'run_gen "${E2_CONFIG:-$E2_CONFIG_DEFAULT}" "agentload_e2_burst"' in text
    assert '--e2-config "${E2_CONFIG:-$E2_CONFIG_DEFAULT}"' in text
    assert "E2_CONFIG_SHA256=$(file_sha256" in text


needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")


@needs_bash
def test_common_sh_syntax():
    r = subprocess.run([BASH, "-n", str(REPO / "slurm" / "common.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _set_value(argv, key):
    for i, a in enumerate(argv):
        if a == "--set" and argv[i + 1].startswith(key + "="):
            v = argv[i + 1].split("=", 1)[1]
            return v[1:-1] if v.startswith('"') else v
    raise KeyError(key)


def _e2_run_argv(tmp_path, meta_argv, arm, e2_config=None):
    """Run the real e2_run of slurm/common.sh with gen_python stubbed; returns the argv gen_python received."""
    port = _set_value(meta_argv, "server.base_url").rsplit(":", 1)[1]
    env_lines = {
        "REPO_DIR": REPO.as_posix(), "JOB_DIR": tmp_path.as_posix(), "RESULTS_ROOT": "results",
        "BASE_URL": f"http://127.0.0.1:{port}", "SERVED_MODEL": _set_value(meta_argv, "server.model"),
        "REQUEST_TOKEN_IDS": _set_value(meta_argv, "server.request_token_ids"),
        "OUTPUT_FEEDBACK": _set_value(meta_argv, "workload.output_feedback"),
        "ENGINE_LABEL": _set_value(meta_argv, "meta.engine_label"), "HW": _set_value(meta_argv, "meta.hardware"),
        "START_VERIFIED": _set_value(meta_argv, "meta.start_state_verified"),
        "START_DETAIL": _set_value(meta_argv, "meta.start_state_detail"),
        "CALIB_FILE": CAL, "PREREG_SHA256": _set_value(meta_argv, "meta.prereg_sha256"),
        "PREREG_FILE": _set_value(meta_argv, "meta.prereg_file"), "T_BURST": "1200", "BURST_RUN_S": "8700", "MODE": "burst",
    }
    lines = ["set -u", f'source "{(REPO / "slurm" / "common.sh").as_posix()}"']
    lines += [f"{k}={json.dumps(v)}" for k, v in env_lines.items()]
    lines.append(f"E2_CONFIG={json.dumps(e2_config)}" if e2_config else ': "${E2_CONFIG:=$E2_CONFIG_DEFAULT}"')
    lines.append('gen_python() { local a; for a in "$@"; do printf "ARG:%s\\n" "$a"; done; }')
    tail = {"burst": "--set arrivals.burst.t_s=$T_BURST", "noburst": "--set arrivals.burst=null"}[arm]
    lines.append(f'cd "$REPO_DIR" && e2_run {arm} 1.65 0 {tail}')
    r = subprocess.run([BASH, "-c", "\n".join(lines)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return [ln[4:] for ln in r.stdout.splitlines() if ln.startswith("ARG:")]


@needs_bash
@pytest.mark.parametrize("arm,runs", [("burst", BURST200_165), ("noburst", NOBURST_165)])
def test_default_e2_run_argv_is_identical_to_the_committed_e2_runs(tmp_path, arm, runs):
    meta = json.loads((BASE_RUNS / runs[0] / "meta.json").read_text())
    got = _e2_run_argv(tmp_path, meta["argv"], arm)
    assert got == meta["argv"][1:]
    got_n = _e2_run_argv(tmp_path, meta["argv"], arm, e2_config="configs/agentload_e2_burst_n100.yaml")
    i = got_n.index("--config")
    assert got_n[i + 1] == "configs/agentload_e2_burst_n100.yaml"
    assert got_n[:i + 1] + got_n[i + 2:] == got[:i + 1] + got[i + 2:]


# ---------------------------------------------------------------- analysis/basin.py
ENDPOINTS = {"endpoints": {"eval_window_s": [5700, 8700], "stuck_hit_below": 0.2, "good_hit_above": 0.8,
                           "trapped_co_primary_n": [100]}}


def _ep(tmp_path, data=ENDPOINTS):
    f = tmp_path / "ep.yaml"
    f.write_text(yaml.safe_dump(data))
    return basin.load_endpoints(f)


def test_endpoints_must_come_from_the_frozen_file(tmp_path):
    ep = _ep(tmp_path)
    assert ep["eval_window_s"] == [5700.0, 8700.0] and ep["trapped_co_primary_n"] == [100]
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", ["trap_v2.eval_from_s=4500.0"])
    assert basin.endpoint_problems(ep, p) == []
    bad = {"endpoints": dict(ENDPOINTS["endpoints"], stuck_hit_below=0.25)}
    assert basin.endpoint_problems(_ep(tmp_path, bad), p)
    with pytest.raises(ValueError):
        _ep(tmp_path, {"endpoints": {"stuck_hit_below": 0.2}})
    with pytest.raises(ValueError):
        _ep(tmp_path, {"something_else": {}})


def _rec(seed, stuck=False, good=False, trapped=False):
    return {"seed": seed, "stuck": stuck, "good": good, "trapped": trapped}


def test_decision_rule():
    d = basin.decision({100: [_rec(0, stuck=True, trapped=True), _rec(1, stuck=True, trapped=True), _rec(2)],
                        25: [_rec(0, good=True), _rec(1, good=True), _rec(2, stuck=True)]})
    assert d["basin_pass"] is True and d["notes"] == []
    d = basin.decision({100: [_rec(0, stuck=True), _rec(1, stuck=True), _rec(2, stuck=True, trapped=True)],
                        25: [_rec(0, good=True), _rec(1, good=True), _rec(2, good=True)]})
    assert d["basin_pass"] is True and any("slope-indeterminate" in x for x in d["notes"])
    d = basin.decision({100: [_rec(0, good=True), _rec(1, good=True), _rec(2, stuck=True)],
                        25: [_rec(0, stuck=True), _rec(1, stuck=True), _rec(2, good=True)]})
    assert d["basin_pass"] is False
    assert any("between 100 and 200" in x for x in d["notes"]) and any("even 25 traps" in x for x in d["notes"])
    d = basin.decision({100: [_rec(0, stuck=True, trapped=True), _rec(1, stuck=True, trapped=True)]})
    assert d["basin_pass"] is None and d["cells"]["100"]["missing_seeds"] == [2]
    d = basin.decision({100: [_rec(0, stuck=True, trapped=True), _rec(1, stuck=True, trapped=True)], 25: []})
    assert d["basin_pass"] is None and d["incomplete"] == ["25", "100"]   # n=25 still open
    d = basin.decision({100: [_rec(0), _rec(1)], 25: [_rec(0, good=True)]})
    assert d["basin_pass"] is False                                        # n=100 can no longer reach 2/3 STUCK


def test_classify_joins_the_committed_n0_and_n200_runs_by_seed(tmp_path):
    ep = _ep(tmp_path)
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", ["trap_v2.eval_from_s=4500.0"])
    base = basin.find_baselines(BASE_RUNS)
    assert sorted(x.name for x in base) == sorted(list(BURST200_165.values()) + list(NOBURST_165.values()))
    res = basin.classify([], base, ep, p, [PARENT])
    assert sorted(int(n) for n in res["by_n"]) == [0, 200]
    assert sorted(r["seed"] for r in res["by_n"][0]) == [0, 1, 2] == sorted(r["seed"] for r in res["by_n"][200])
    assert res["window_mismatch_runs"] == [] and res["endpoint_problems"] == [] and res["duplicate_seed_runs"] == {}
    for r in res["rows"]:
        assert r["role"] == "baseline" and isinstance(r["stuck"], bool) and isinstance(r["good"], bool)
        assert r["eval_from"] == 5700.0 and r["prereg_bound"] is True, r.get("prereg_blockers")
    assert set(res["by_seed"]) == {"0", "1", "2"} and all(set(v) == {"0", "200"} for v in res["by_seed"].values())
    assert res["decision"]["basin_pass"] is None                           # no B1 runs yet
