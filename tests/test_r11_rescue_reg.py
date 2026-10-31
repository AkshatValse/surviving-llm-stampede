"""R1 / R4 rescue registrations, the prereg rescue binding (fill / check-job / run_blockers), the rescue job glue in
slurm/common.sh, analysis.load / analysis.guards for rescue runs, and the mock job glue end to end for ARMS=rescue.

check-job is the real CLI; the glue tests run the real slurm/common.sh functions with ``gen_python`` stubbed out, except the
last one, which runs slurm/local_smoke.sh against the mock server (about 40 s)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from conftest import REPO

from analysis import guards, prereg, rescue_prereg as RP
from analysis import rescue as R
from analysis.load import Run
from analysis.params import load_params

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
PARAMS = REPO / "configs" / "agentload_analysis.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
PARENT_NATIVE = REPO / "configs" / "agentload_prereg_2026-10-25_native.yaml"
CAL = REPO / "prereg/inputs/2026-10-23/calibration.json"
CAL_N = REPO / "prereg/inputs/2026-10-25-native/calibration.json"
E2 = {"r1": REPO / "configs/agentload_e2_rescue.yaml", "r4": REPO / "configs/agentload_e2_rescue_native.yaml",
      "smoke": REPO / "configs/agentload_e2_rescue_smoke.yaml"}
REG = {k: REPO / v["out"] for k, v in RP.CELLS.items()}
DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
# the job each registration authorises (what validate_mode_inputs passes)
JOB = {"r1": dict(label="sglang-fcfs-r1-rescue", mults="1.35 1.65", n_cap=20, calib=CAL, dur=8700, tb=1200),
       "r4": dict(label="sglang-fcfs-r1-rescue-native", mults="4.0", n_cap=64, calib=CAL_N, dur=8700, tb=1200),
       "smoke": dict(label="sglang-fcfs-r1-rescue-smoke", mults="1.65", n_cap=20, calib=CAL, dur=2400, tb=300)}


# ---------------------------------------------------------------- registrations
@pytest.mark.parametrize("cell", sorted(RP.CELLS))
def test_registration_is_reproduced_by_fill_and_is_valid(cell):
    data = REG[cell].read_bytes()
    assert b"\r" not in data
    assert RP.dump_registration(RP.fill_registration(cell)) == data
    pr = prereg.load_prereg(REG[cell])
    errs = [x for x in prereg.validate(pr, load_params(PARAMS, []), "fcfs", prereg_path=REG[cell]) if x["severity"] == "error"]
    assert errs == [] and pr["status"] == "FILLED"
    c = RP.CELLS[cell]
    assert pr["inputs"]["engine_cell_label"] == c["label"] and pr["inputs"]["e2_config"] == c["e2"]
    assert pr["lambda_selection"]["lambda_mults"] == c["mults"]
    e2 = yaml.safe_load(E2[cell].read_text())
    assert pr["protocol"]["gate"] == e2["gate"] and pr["protocol"]["gate"]["mode"] == "rescue"
    assert pr["protocol"]["e2_config_sha256"] == R.file_sha256(E2[cell])
    assert pr["measured"]["n_cap"] == JOB[cell]["n_cap"] == e2["gate"]["n_cap"] and pr["measured"]["hardware"] == HW
    assert pr["protocol"]["duration_s"] == JOB[cell]["dur"] and pr["protocol"]["t_burst_s"] == JOB[cell]["tb"]
    rule = pr["lambda_selection"]["rule"]
    assert "smallest_within_margin" in rule and HW in rule
    if cell != "smoke":
        prof = R.PROFILES[cell]
        assert prof["t_on_s"] == e2["gate"]["t_on_s"] and prof["n_cap"] == e2["gate"]["n_cap"] and prof["hardware"] == HW
        for needle in ("(a) VALID", "(b) RELEASED with t_rel <= 7200", "(c) POST-GOOD", "REFUTED takes precedence over PASS",
                       "no-shed part of a PASS claim is withheld", "R4 requires stuck same-seed BURST controls",
                       "is INVALID", "nova22-amp-7", "r11-rescue-pred", "FROZEN CONSTANTS", '"max_not_started_at_end": 3',
                       '"clock_early_tol_s": 0.05', '"release_grid_tol_s": 2.0'):
            assert needle in rule, needle
    if cell == "r4":
        assert e2["gate"]["t_on_s"] == 2100 and "[1800, 2100)" in rule and "R4s_t2100" in rule
        assert "after the 2400-s bundle-3 prediction (13/20" in rule and R.PROFILES["r4"]["prediction_cell"] == "R4s_t2100"
    if cell == "smoke":
        assert "A release is NOT required" in rule and "no verdict of it is ever decisive" in rule


@pytest.mark.parametrize("cell,parent", [("r1", PARENT), ("r4", PARENT_NATIVE), ("smoke", PARENT)])
def test_registration_differs_from_its_parent_only_where_allowed(cell, parent):
    a, b = prereg.load_prereg(parent), prereg.load_prereg(REG[cell])
    d = RP.registration_diff(a, b, cell)
    assert d["forbidden"] == []
    assert {"inputs.engine_cell_label", "inputs.e2_config", "protocol.e2_config_sha256", "lambda_selection.rule",
            "protocol.gate.mode", "protocol.gate.t_on_s"} <= set(d["allowed"])
    for sec in ("measured", "pass_rule", "kill_conditions", "predictions", "checks"):
        assert a[sec] == b[sec], sec
    for k in ("mu_curve_json", "calibration_json", "e0b_bracket_json"):
        assert a["inputs"][k] == b["inputs"][k]


def test_default_fill_adds_no_gate_block():
    p = load_params(PARAMS, [])
    rd = lambda rel: (REPO / rel).read_text()                                   # noqa: E731
    inp = "prereg/inputs/2026-10-23"
    pr = prereg.fill(yaml.safe_load(rd(RP.TEMPLATE)), json.loads(rd(f"{inp}/mu_curve.json")),
                     json.loads(rd(f"{inp}/calibration.json")), e0b=json.loads(rd(f"{inp}/lambda_cap_bracket.json")),
                     e2_cfg=yaml.safe_load(DEFAULT_CFG.read_text()), lambda_mults=[1.35, 1.65], rule="x",
                     n_cap_rule="smallest_within_margin", p=p, e2_cfg_sha256="0" * 64)
    assert pr["protocol"] == prereg.load_prereg(PARENT)["protocol"]
    assert not prereg.is_rescue_registration(pr)


# ---------------------------------------------------------------- check-job
def _check_job(capsys, reg, cfg, label, mults, arms, n_cap=None, calib=CAL, dur=8700, tb=1200):
    argv = ["check-job", str(reg), "--label", label, "--mults", mults, "--arms", arms, "--calib", str(calib),
            "--hardware", HW, "--e2-config", str(cfg), "--duration-s", str(dur), "--t-burst-s", str(tb),
            "--params", str(PARAMS), "--set", "trap_v2.eval_from_s=4500", "--allow-uncommitted"]
    if n_cap is not None:
        argv += ["--n-cap", str(n_cap)]
    rc = prereg.main(argv)
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("cell", sorted(RP.CELLS))
def test_check_job_accepts_each_registration_with_its_rescue_config(capsys, cell):
    j = JOB[cell]
    rc, out = _check_job(capsys, REG[cell], E2[cell], j["label"], j["mults"], "rescue", j["n_cap"], j["calib"], j["dur"], j["tb"])
    assert rc == 0, out
    assert "PREREG_SHA256=" in out


def test_check_job_refuses_a_different_gate_block_or_config_bytes(capsys, tmp_path):
    j = JOB["r1"]
    raw = E2["r1"].read_text()
    for name, text, needle in (
            ("t_on.yaml", raw.replace("  t_on_s: 1800\n", "  t_on_s: 2400\n"), "gate.t_on_s: 2400 != registered 1800"),
            ("cap.yaml", raw.replace("  n_cap: 20\n", "  n_cap: 24\n"), "gate.n_cap: 24 != registered 20"),
            ("hold.yaml", raw.replace("  release_hold_s: 300\n", "  release_hold_s: 200\n"), "gate.release_hold_s"),
            ("comment.yaml", raw + "# same values, different bytes\n", "E2 config sha256")):
        assert text != raw
        f = tmp_path / name
        f.write_bytes(text.encode())
        rc, out = _check_job(capsys, REG["r1"], f, j["label"], j["mults"], "rescue", 20)
        assert rc == 1 and needle in out, (name, out)
    # a different cap at run time
    rc, out = _check_job(capsys, REG["r1"], E2["r1"], j["label"], j["mults"], "rescue", 22)
    assert rc == 1 and "n_cap 22 != registered n_cap 20" in out
    # the R4 registration with the R1 config and vice versa
    rc, out = _check_job(capsys, REG["r4"], E2["r1"], JOB["r4"]["label"], "4.0", "rescue", 64, CAL_N)
    assert rc == 1 and "gate.t_on_s" in out


def test_check_job_refuses_a_missing_gate_block_and_other_arms(capsys):
    j = JOB["r1"]
    rc, out = _check_job(capsys, REG["r1"], DEFAULT_CFG, j["label"], j["mults"], "rescue", 20)      # missing gate block
    assert rc == 1 and "no rescue gate block" in out
    for arms in ("burst", "capped", "noburst"):
        rc, out = _check_job(capsys, REG["r1"], E2["r1"], j["label"], j["mults"], arms, 20)
        assert rc == 1 and "authorises only the rescue arm" in out, arms
    rc, out = _check_job(capsys, REG["r1"], E2["r1"], j["label"], j["mults"], "rescue", None)     # no resolved cap
    assert rc == 1 and "no resolved cap" in out


def test_check_job_refuses_the_rescue_arm_under_the_2026_10_24_registration(capsys):
    rc, out = _check_job(capsys, PARENT, E2["r1"], "sglang-fcfs-r1", "1.35 1.65", "rescue", 20)
    assert rc == 1 and "needs a rescue registration" in out
    rc, out = _check_job(capsys, PARENT, E2["r1"], "sglang-fcfs-r1", "1.35 1.65", "capped", 20)    # capped + rescue config
    assert rc == 1 and "only the rescue arm may run it" in out
    rc, out = _check_job(capsys, PARENT, DEFAULT_CFG, "sglang-fcfs-r1", "1.35 1.65", "burst noburst capped", 20)
    assert rc == 0, out                                                                            # the default job is unchanged


def _run(arm, gate, prov_sha="s", **kw):
    cfg = {"run": {"duration_s": 8700}, "arrivals": {"burst": {"n": 200, "width_s": 60}}, "gate": gate}
    base = dict(label="sglang-fcfs-r1-rescue", rate_mult=1.35, lambda_ref_value=None, uncached_tokens_ref_value=None,
                hardware=HW, cfg=cfg, t_burst_ref=1200.0, arm=arm, arm_derived=arm, gate_n_cap=20, prereg_sha256=prov_sha,
                t0_unix=2e9)
    base.update(kw)
    return SimpleNamespace(**base)


def test_run_blockers_bind_the_rescue_arm_to_a_rescue_registration():
    pr = prereg.load_prereg(REG["r1"])
    m = pr["measured"]
    prov = {"sha256": "s", "git_last_commit_unix": 1e9}
    ok = dict(lambda_ref_value=m["lambda_ref"], uncached_tokens_ref_value=m["all_miss_uncached_tokens_per_s"])
    gate = dict(pr["protocol"]["gate"])
    assert prereg.run_blockers(pr, prov, _run("rescue", gate, **ok)) == []
    b = prereg.run_blockers(pr, prov, _run("rescue", {**gate, "t_on_s": 2400}, **ok))
    assert any("gate.t_on_s" in x for x in b)
    b = prereg.run_blockers(pr, prov, _run("capped", {"n_cap": 20}, **ok))
    assert any("under a rescue registration" in x for x in b)
    parent = prereg.load_prereg(PARENT)
    b = prereg.run_blockers(parent, prov, _run("rescue", gate, label="sglang-fcfs-r1", **ok))
    assert any("no rescue gate block" in x for x in b)


# ---------------------------------------------------------------- load / guards
def _toy_run(gate, meta_extra=None):
    meta = {"gate_n_cap_resolved": 20, "outcome": {"gate": {"max_active_seen": 150}}, **(meta_extra or {})}
    cfg = {"gate": gate, "arrivals": {"burst": {"n": 200, "t_s": 1200.0, "width_s": 60}}, "meta": {}}
    ses = pd.DataFrame({"t_admit": [1.0, 2.0, 3.0], "t_end": [10.0, 10.0, 10.0]})
    return Run(dir=Path("."), meta=meta, cfg=cfg, requests=pd.DataFrame(), sessions=ses, metrics=pd.DataFrame(), t_end_s=10.0)


def test_arm_derived_and_check_gate_know_the_rescue_arm():
    resc = _toy_run({"mode": "rescue", "n_cap": 20}, {"gate_mode": "rescue"})
    assert resc.gate_mode == "rescue" and resc.arm_derived == "rescue"
    assert guards.check_gate([resc]) == []                       # active far above the cap before the engage: by design
    capped = _toy_run({"n_cap": 20})
    assert capped.gate_mode == "static" and capped.arm_derived == "capped"
    assert [p["code"] for p in guards.check_gate([capped])] == ["gate_cap_exceeded"]
    nob = _toy_run({"n_cap": None})
    nob.cfg["arrivals"]["burst"] = None
    nob.meta["gate_n_cap_resolved"] = None
    assert nob.arm_derived == "noburst"


# ---------------------------------------------------------------- job glue
def test_common_sh_wires_the_rescue_arm():
    t = (REPO / "slurm" / "common.sh").read_text()
    assert "burst|noburst|capped|rescue) ;;" in t
    assert '*" capped "*|*" rescue "*)' in t
    assert ('e2_run rescue "$m" "$seed" --set "arrivals.burst.t_s=$T_BURST" --set "gate.n_cap=$GATE_N_CAP_YAML"' in t)
    assert 'gen_python -m analysis.rescue check-run "$rd" --e2-config "$E2_CONFIG" $smoke_flag' in t
    assert 'case "$E2_CONFIG" in *rescue_smoke*.yaml) smoke_flag="--smoke"' in t
    assert "--require-release" not in t
    assert 'if [ "${ARMS:-}" = "rescue" ]; then' in t and "skipping summarize burst / burst2 (blinding)" in t


def _bash(code, env, timeout=60):
    e = dict(os.environ)
    e.update(env)
    return subprocess.run([BASH, "-c", f'source "{(REPO / "slurm" / "common.sh").as_posix()}"\n{code}\n'],
                          capture_output=True, text=True, env=e, timeout=timeout)


@needs_bash
def test_validate_mode_inputs_resolves_the_rescue_cap_and_refuses_mixed_arms(tmp_path):
    for f in ("prereg.yaml", "cal.json"):
        (tmp_path / f).write_text("{}")
    env = {"MODE": "burst", "ENGINE_LABEL": "sglang-fcfs-r1-rescue", "MULTS": "1.35", "PREREG_FILE": str(tmp_path / "prereg.yaml"),
           "CALIB_FILE": str(tmp_path / "cal.json"), "HW": HW, "BURST_RUN_S": "8700", "T_BURST": "1200", "HIT_EVAL_FROM_S": "4500",
           "E2_CONFIG": "configs/agentload_e2_rescue.yaml"}
    stub = 'gen_python() { printf "<%s>\\n" "$@"; echo "PREREG_SHA256=checked"; }\n'
    r = _bash(stub + "validate_mode_inputs; echo GATE=$GATE_N_CAP_YAML CAP=$RESOLVED_N_CAP", {**env, "ARMS": "rescue", "N_CAP": "20"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GATE=20 CAP=20" in r.stdout and "<--arms>\n<rescue>\n" in r.stdout and "<--n-cap>\n<20>\n" in r.stdout
    assert "<--e2-config>\n<configs/agentload_e2_rescue.yaml>\n" in r.stdout
    r = _bash(stub + "validate_mode_inputs", {**env, "ARMS": "burst rescue", "N_CAP": "20"})
    assert r.returncode == 1 and "must be the only arm" in r.stderr
    r = _bash(stub + "validate_mode_inputs", {**env, "ARMS": "rescue", "N_CAP": "", "CAP_FILE": ""})
    assert r.returncode == 1 and "CAP_FILE is empty" in r.stderr


@needs_bash
@pytest.mark.parametrize("e2,smoke", [("configs/agentload_e2_rescue.yaml", False), ("configs/agentload_e2_rescue_smoke.yaml", True)])
def test_mode_burst_rescue_runs_the_arm_then_check_run_and_post_analysis_is_blind(tmp_path, e2, smoke):
    jd = tmp_path / "job"
    jd.mkdir()
    code = f'''
JOB_DIR={json.dumps(jd.as_posix())}; RESULTS_ROOT=results; BASE_URL=http://127.0.0.1:1; SERVED_MODEL=m; REQUEST_TOKEN_IDS=true
OUTPUT_FEEDBACK=server; HW="{HW}"; START_VERIFIED=true; START_DETAIL=x; PREREG_SHA256=abc; GAP_S=0
check_calib_hardware() {{ :; }}; between_runs() {{ :; }}
gen_python() {{
  if [ "$2" = "agentload" ]; then echo "GEN $*"; echo '  "out_dir": "/r/run_'"$RUN_IDX"'",'; return 0; fi
  echo "PY $*"; return ${{CHECK_RC:-0}}
}}
GATE_N_CAP_YAML=20
mode_burst; echo FAILED=$FAILED_RUNS
echo /r/run_1 > "$JOB_DIR/run_dirs_burst.txt"; post_analysis; echo POST_DONE
'''
    env = {"MODE": "burst", "ARMS": "rescue", "MULTS": "1.35", "SEEDS": "0 1", "CALIB_FILE": "cal.json", "PREREG_FILE": "p.yaml",
           "T_BURST": "1200", "BURST_RUN_S": "8700", "GATE_N_CAP_YAML": "20", "E2_CONFIG": e2, "ENGINE_LABEL": "sglang-fcfs-r1-rescue"}
    r = _bash(code, env)
    assert r.returncode == 0, r.stdout + r.stderr
    gens = [ln for ln in r.stdout.splitlines() if ln.startswith("GEN ")]
    checks = [ln for ln in r.stdout.splitlines() if ln.startswith("PY -m analysis.rescue check-run")]
    assert len(gens) == 2 and len(checks) == 2 and "FAILED=0" in r.stdout
    for g in gens:
        assert f"--config {e2}" in g and "--set meta.arm=\"rescue\"" in g and "--set gate.n_cap=20" in g
        assert "--set arrivals.burst.t_s=1200" in g
    assert "check-run /r/run_1 --e2-config " + e2 in checks[0] and "check-run /r/run_2" in checks[1]
    assert ("--smoke" in checks[0]) == smoke and "--require-release" not in checks[0]
    assert "skipping summarize burst / burst2 (blinding)" in r.stdout and "summarize" not in r.stdout.replace("skipping summarize", "")
    r = _bash(code, {**env, "CHECK_RC": "1"})
    assert "FAILED=2" in r.stdout and "rescue check-run FAILED" in r.stdout


@needs_bash
def test_post_analysis_of_the_default_burst_arms_is_unchanged(tmp_path):
    jd = tmp_path / "job"
    jd.mkdir()
    (jd / "run_dirs_burst.txt").write_bytes(b"/r/a\n/r/b\n")
    code = f'''JOB_DIR={json.dumps(jd.as_posix())}; RESULTS_ROOT=results; TRAP_MIN_S=3000; HIT_EVAL_FROM_S=4500; PREREG_FILE=p.yaml
gen_python() {{ echo "PY $*"; }}
post_analysis'''
    r = _bash(code, {"MODE": "burst", "ARMS": "burst noburst capped"})
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("PY ")]
    assert len(lines) == 2 and "summarize burst --run-dirs /r/a /r/b " in lines[0] and "summarize burst2" in lines[1]


# ---------------------------------------------------------------- mock job glue end to end
@needs_bash
def test_job_glue_runs_the_rescue_arm_end_to_end_against_the_mock_server(tmp_path):
    hw = _bash("hardware_string", {}).stdout.strip()
    env = dict(os.environ, ENV_GEN=sys.prefix, RESULTS_ROOT=tmp_path.as_posix(), PORT="18197", SEEDS="0", ARMS="rescue",
               FAKE_CALIB_HW=hw)
    for k in ("MULTS", "N_CAP", "CAP_FILE", "E2_CONFIG", "MOCK_EXTRA", "MOCK_KV", "MOCK_SLOTS"):
        env.pop(k, None)
    r = subprocess.run([BASH, str(REPO / "slurm" / "local_smoke.sh"), "burst"], capture_output=True, text=True, env=env,
                       timeout=300, cwd=REPO)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-4000:]
    assert "0 failed" in r.stdout and "rescue check-run:" in r.stdout and "rescue check-run FAILED" not in r.stdout
    assert "skipping summarize burst / burst2 (blinding)" in r.stdout
    assert "agentload_analysis_burst2" not in r.stdout and "burst2 analysis" not in r.stdout and "kill_verdict_v2.json:" not in r.stdout
    assert not (tmp_path / "agentload_analysis_burst2").exists() and not (tmp_path / "agentload_analysis_burst").exists()
    jd = next((tmp_path / "nova_job_logs").iterdir())
    chk = json.loads(next(jd.glob("rescue_check_*.json")).read_text())
    assert chk["ok"] is True, [c for c in chk["checks"] if not c["ok"]]
    names = {c["name"] for c in chk["checks"]}
    assert {"pause_counts", "engage", "gate_cap_held"} <= names and "release" not in names
    rd = Path((jd / "run_dirs_burst.txt").read_text().split()[0].replace("\\\\", "\\"))
    meta = json.loads((rd / "meta.json").read_text())
    assert meta["arm"] == "rescue" and meta["gate_mode"] == "rescue" and meta["gate_n_cap_resolved"] == 3
