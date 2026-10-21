"""The Nova scripts are DRAFTS and are never submitted. These tests only check syntax, the required directives and
-- by running the shared job code against the mock server on this machine -- the glue logic."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from conftest import REPO

SLURM = REPO / "slurm"
JOB_SCRIPTS = [SLURM / "sglang_job.sbatch", SLURM / "vllm_job.sbatch"]
ALL = sorted(SLURM.glob("*.sh")) + sorted(SLURM.glob("*.sbatch"))
BASH = shutil.which("bash")
GOOD_CTX = {"SLURM_JOB_ACCOUNT": "f2026.coms.6250.02", "SLURM_JOB_PARTITION": "instruction", "SLURM_JOB_QOS": "instruction"}

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_bash_syntax(path):
    r = subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("path", JOB_SCRIPTS, ids=lambda p: p.name)
def test_required_sbatch_directives(path):
    text = path.read_text()
    directives = [l[len("#SBATCH "):].strip() for l in text.splitlines() if l.startswith("#SBATCH ")]
    for want in ("--account=f2026.coms.6250.02", "--partition=instruction", "--qos=instruction",
                 "--gres=gpu:a100:1", "--exclude=nova22-amp-7", "--cpus-per-task=16", "--mem=128G", "--time=04:00:00",
                 "--output=logs/%x-%j.out"):
        assert want in directives, (path.name, want)
    assert not any("6720" in d for d in directives)                       # never the other course's account
    assert "DRAFT" in text and "NEVER SUBMITTED" in text


def test_shared_job_code_prints_what_the_spec_requires():
    text = (SLURM / "common.sh").read_text()
    for needle in ("hostname", "nvidia-smi", "nvidia-smi topo -m", "git -C", "SEEDS", "configs (verbatim)",
                   "metric names", "agentload probe"):
        assert needle in text, needle


def test_default_engine_labels_name_the_kill_rule_cells():
    sg = (SLURM / "sglang_job.sbatch").read_text()
    vl = (SLURM / "vllm_job.sbatch").read_text()
    for lab in ("sglang-nocache", "sglang-lpminf", "sglang-${POLICY:-fcfs}-r${REFRESH:-1}"):
        assert lab in sg
    assert "vllm-nocache" in vl and "vllm-fcfs" in vl                  # cells whose label contains 'fcfs'


@pytest.mark.parametrize("script,env,label", [
    ("sglang_job.sbatch", {"MODE": "smoke"}, "sglang-smoke"),
    ("vllm_job.sbatch", {"MODE": "smoke"}, "vllm-smoke"),
    ("sglang_job.sbatch", {"MODE": "miss"}, "sglang-nocache"),
    ("sglang_job.sbatch", {"MODE": "burst"}, "sglang-fcfs-r1"),
    ("sglang_job.sbatch", {"MODE": "burst", "POLICY": "lpm", "REFRESH": "0"}, "sglang-lpm-r0"),
    ("sglang_job.sbatch", {"MODE": "burst", "POLICY": "lpm", "LPM_INF": "1"}, "sglang-lpminf"),
    ("sglang_job.sbatch", {"MODE": "burst", "ENGINE_LABEL": "custom"}, "custom"),
    ("vllm_job.sbatch", {"MODE": "miss"}, "vllm-nocache"),
    ("vllm_job.sbatch", {"MODE": "cap"}, "vllm-fcfs"),
])
def test_default_labels_are_computed_by_the_scripts(script, env, label, tmp_path):
    (tmp_path / "slurm").mkdir()
    (tmp_path / "slurm" / "common.sh").write_text('job_main() { echo "LABEL=$ENGINE_LABEL SEEDS=$SEEDS"; }\n')
    for n in ("engine_sglang.sh", "engine_vllm.sh"):
        (tmp_path / "slurm" / n).write_text("")
    e = {k: v for k, v in os.environ.items() if k not in ("MODE", "POLICY", "REFRESH", "LPM_INF", "ENGINE_LABEL", "SEEDS")}
    e.update(env, SLURM_SUBMIT_DIR=str(tmp_path), **GOOD_CTX)
    r = subprocess.run([BASH, str(SLURM / script)], capture_output=True, text=True, env=e, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert f"LABEL={label} " in r.stdout and "SEEDS=0" in r.stdout


def test_no_executable_sbatch_and_placeholders_are_guarded():
    for p in ALL:
        for line in p.read_text().splitlines():
            code = line.split("#", 1)[0] if not line.startswith("#!") else ""
            assert not re.search(r"\b(sbatch|srun|salloc)\b", code), (p.name, line)
    for name in ("engine_sglang.sh", "engine_vllm.sh", "download_model.sbatch"):
        t = (SLURM / name).read_text()
        assert "<group-dir>" in t                                          # unresolved Nova paths stay placeholders
    assert "require_set" in (SLURM / "common.sh").read_text()


def test_engine_launch_commands_contain_the_spec_flags():
    sg = (SLURM / "engine_sglang.sh").read_text()
    for needle in ("python\" -m sglang.launch_server", "--model-path", "Qwen/Qwen2.5-7B-Instruct", "--schedule-policy",
                   "SGLANG_ENABLE_WAITING_PREFIX_REFRESH", "--disable-radix-cache", "--enable-metrics"):
        assert needle in sg, needle
    vl = (SLURM / "engine_vllm.sh").read_text()
    for needle in ("vllm\" serve", "Qwen/Qwen2.5-7B-Instruct", "--enable-prefix-caching", "--no-enable-prefix-caching"):
        assert needle in vl, needle
    assert "UNVERIFIED" in sg and "UNVERIFIED" in vl


@pytest.mark.parametrize("mode,port", [("smoke", 18090), ("miss", 18091), ("cap", 18092), ("burst", 18093)])
def test_job_glue_runs_locally_against_the_mock_server(mode, port, tmp_path):
    env = dict(os.environ, ENV_GEN=sys.prefix, RESULTS_ROOT=str(tmp_path), PORT=str(port), MULTS="1.0", SEEDS="0",
               POP_CHECK="6" if mode == "miss" else "")
    r = subprocess.run([BASH, str(SLURM / "local_smoke.sh"), mode], capture_output=True, text=True, env=env, timeout=240,
                       cwd=REPO)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]     # a failed run makes the job exit non-zero
    assert "0 failed" in r.stdout
    assert "CANARY_RESULT" in r.stdout
    logs = list((tmp_path / "nova_job_logs").iterdir())
    assert len(logs) == 1
    banner = (logs[0] / "banner.txt").read_text()
    for needle in ("hostname:", "nvidia-smi", "commit:", "SEEDS=\"0\"", "ENGINE=mock", f"MODE={mode}", "research_question"):
        assert needle in banner, needle
    assert "vllm:num_requests_waiting" in (logs[0] / "probe.txt").read_text()
    ev = (logs[0] / "job_events.log").read_text()
    assert "flush HTTP 200" in ev and "reset_and_verify: verified=true" in ev
    assert "CANARY_RESULT" in (logs[0] / "canary.log").read_text()
    assert "PROBE_SUMMARY" in (logs[0] / "probe.txt").read_text()
    assert (logs[0] / "flag_check.txt").exists() and any(f.name.startswith("pip_freeze_") for f in logs[0].iterdir())
    run_dirs = (logs[0] / f"run_dirs_{mode}.txt").read_text().split()
    assert len(run_dirs) == 1 and (Path(run_dirs[0]) / "meta.json").exists()
    meta = json.loads((Path(run_dirs[0]) / "meta.json").read_text())
    assert meta["engine_label"] == "mock-fcfs" and meta["seeds"] == [0] and meta["status"] == "finished"
    assert meta["start_state_verified"] is True and "canary" in meta["start_state_detail"]
    assert meta["content_salt"] == 1 and meta["output_feedback_configured"] == "server"
    assert meta["outcome"]["output_ids_source_counts"] == {"server_ids": meta["outcome"]["requests_ok"]}
    assert meta["outcome"]["prompt_tokens_mismatch"] == 0 and meta["force_close_connections"] is True
    assert meta["outcome"]["requests_ok"] > 5
    ana = {"smoke": ("agentload_analysis_windows", "windows.csv"),
           "miss": ("agentload_analysis_miss", "calibration.json"), "cap": ("agentload_analysis_stable", "stable_runs.csv"),
           "burst": ("agentload_analysis_burst", "burst_runs.csv")}[mode]
    d = sorted((tmp_path / ana[0]).iterdir())[-1]
    assert (d / ana[1]).exists()
    if mode == "miss":       # the population-sensitivity run is analysed separately, not averaged into lambda_miss
        pc = (logs[0] / "run_dirs_miss_popcheck.txt").read_text().split()
        assert len(pc) == 1 and "popcheck" in pc[0] and pc[0] != run_dirs[0]
        cal = json.loads((d / "calibration.json").read_text())
        assert cal["n_runs"] == 1
        d2 = sorted((tmp_path / "agentload_analysis_miss_popcheck").iterdir())[-1]
        assert json.loads((d2 / "calibration.json").read_text())["n_runs"] == 1
    if mode == "burst":
        assert pd.read_csv(d / "burst_runs.csv")["t_burst"].iloc[0] == 6.0
    # the mock server process must be gone
    assert subprocess.run(["pgrep", "-f", f"agentload.mock_server --port {port}"], capture_output=True).returncode != 0


# ---------------------------------------------------------------------------------------------------------------
# review round 4: billing guard, flag-check abort, curl timeouts, wall-time budget, port, start-state verification
# ---------------------------------------------------------------------------------------------------------------
import socket
import threading
import time

BILLING = [SLURM / "sglang_job.sbatch", SLURM / "vllm_job.sbatch", SLURM / "download_model.sbatch"]


def bash_fn(code, env=None, timeout=60):
    """Run `code` in bash after sourcing slurm/common.sh (functions only; nothing is executed by sourcing)."""
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([BASH, "-c", f'source "{SLURM}/common.sh"\n{code}\n'], capture_output=True, text=True, env=e,
                          timeout=timeout)


def _guard_block(path):
    t = path.read_text()
    a, b = t.index("# ---- BILLING GUARD"), t.index("# ---- end billing guard")
    return t[a:b]


def test_billing_guard_is_identical_in_every_sbatch_and_precedes_other_code():
    blocks = {p.name: _guard_block(p) for p in BILLING}
    assert len(set(blocks.values())) == 1
    for p in BILLING:
        t = p.read_text()
        head = t[:t.index("# ---- BILLING GUARD")]
        code = [l for l in head.splitlines() if l.strip() and not l.startswith("#")]
        assert code == [], (p.name, code)                     # nothing but comments / #SBATCH before the guard
        assert "source " not in head


@pytest.mark.parametrize("path", BILLING, ids=lambda p: p.name)
@pytest.mark.parametrize("ctx", [
    {"SLURM_JOB_ACCOUNT": "f2026.coms.6720.01"},                        # the user's default account (the other course)
    {"SLURM_JOB_PARTITION": "nova"}, {"SLURM_JOB_QOS": "normal"},
    {"SLURM_JOB_ACCOUNT": ""},                                          # unknown
], ids=["wrong-account", "wrong-partition", "wrong-qos", "unknown-account"])
def test_billing_guard_refuses_the_wrong_context(path, ctx, tmp_path):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SLURM_")}
    e.update(GOOD_CTX)
    e.update(ctx, MODE="smoke", SLURM_SUBMIT_DIR=str(tmp_path), SBATCH_ACCOUNT="f2026.coms.6720.01")
    r = subprocess.run([BASH, str(path)], capture_output=True, text=True, env=e, cwd=tmp_path)
    assert r.returncode == 2 and "FATAL: wrong or unknown SLURM context" in r.stderr
    assert "SBATCH_ACCOUNT=f2026.coms.6720.01" in r.stderr             # the likely culprit is printed


def test_billing_guard_passes_the_right_context_and_falls_back_to_scontrol(tmp_path):
    (tmp_path / "bin").mkdir()
    sc = tmp_path / "bin" / "scontrol"
    sc.write_text("#!/bin/sh\necho 'JobId=7 JobName=x UserId=u(1) Account=ACCT Partition=instruction QOS=instruction'\n")
    sc.chmod(0o755)
    base = {k: v for k, v in os.environ.items() if not k.startswith("SLURM_")}
    base.update(PATH=f"{tmp_path / 'bin'}:{base['PATH']}", SLURM_JOB_ID="7", MODE="smoke", HF_HOME="<x>", ENV_GEN="<y>")
    for acct, want in (("f2026.coms.6720.01", 2), ("f2026.coms.6250.02", 1)):    # 1 = download script's placeholder exit
        sc.write_text(f"#!/bin/sh\necho 'JobId=7 JobName=x UserId=u(1) Account={acct} Partition=instruction QOS=instruction'\n")
        r = subprocess.run([BASH, str(SLURM / "download_model.sbatch")], capture_output=True, text=True, env=base, cwd=tmp_path)
        assert r.returncode == want, (acct, r.stdout, r.stderr)
    assert "placeholder" in r.stdout


def test_help_has_flag_is_exact_token_match():
    help_text = "  --port-base INT\n  --enable-prefix-caching, --no-enable-prefix-caching\n  --max-model-len N\n  x--odd\n"
    cases = {"--port": 1, "--port-base": 0, "--enable-prefix-caching": 0, "--no-enable-prefix-caching": 0,
             "--max-model-len": 0, "--model-len": 1, "--odd": 1, "--max-model": 1}
    for flag, want_rc in cases.items():
        r = bash_fn(f'help_has_flag "$H" {flag}', env={"H": help_text})
        assert r.returncode == want_rc, (flag, r.returncode)


def test_check_envvars_reports_missing_names(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "envs.py").write_text('X = os.environ.get("REAL_VAR")\n')
    ok = bash_fn(f'check_envvars "{tmp_path / "pkg"}" REAL_VAR')
    assert ok.returncode == 0 and "env var ok:      REAL_VAR" in ok.stdout
    bad = bash_fn(f'check_envvars "{tmp_path / "pkg"}" REAL_VAR MISSPELT_VAR')
    assert bad.returncode == 1 and "env var MISSING: MISSPELT_VAR" in bad.stdout
    assert bash_fn(f'check_envvars "{tmp_path / "nope"}" REAL_VAR').returncode == 1       # no package dir => not ok


def _driver(tmp_path, engine_body, extra_env=None):
    eng = tmp_path / "engine_fake.sh"
    eng.write_text("ENGINE=fake; HEALTH_PATH=/health; FLUSH_PATH=/flush_cache; RADIX=1; SERVED_MODEL=mock\n" + engine_body)
    drv = tmp_path / "drv.sh"
    drv.write_text(f'source "{SLURM}/common.sh"\nsource "{eng}"\njob_main\n')
    e = dict(os.environ, MODE="smoke", ENGINE_LABEL="fake", SEEDS="0", ENV_GEN=sys.prefix, REPO_DIR=str(REPO),
             RESULTS_ROOT=str(tmp_path / "res"), PORT="18110", MARKER=str(tmp_path / "LAUNCHED"))
    e.update(extra_env or {})
    return subprocess.run([BASH, str(drv)], capture_output=True, text=True, env=e, cwd=REPO, timeout=120)


def test_failed_flag_check_aborts_before_the_engine_is_launched(tmp_path):
    r = _driver(tmp_path, 'check_engine_flags() { echo "flag MISSING: --nope"; return 1; }\n'
                          'launch_engine() { touch "$MARKER"; }\n')
    assert r.returncode == 1 and "engine flag/env-var check failed" in r.stderr
    assert "flag MISSING: --nope" in r.stdout                   # the check output reaches the job log
    assert not (tmp_path / "LAUNCHED").exists()                 # (the old piped check ran launch_engine regardless)


def test_unfilled_placeholder_in_a_required_var_aborts_before_launch(tmp_path):
    r = _driver(tmp_path, 'engine_required_vars() { echo "ENV_FAKE"; }\ncheck_engine_flags() { :; }\n'
                          'launch_engine() { touch "$MARKER"; }\n', {"ENV_FAKE": "/work/<group-dir>/x"})
    assert r.returncode == 1 and "placeholder" in r.stderr and not (tmp_path / "LAUNCHED").exists()


def test_a_busy_port_is_refused_and_a_derived_port_skips_it(tmp_path):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]
    try:
        assert bash_fn(f"port_in_use {port}").returncode == 0
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        fp = free.getsockname()[1]
        free.close()
        assert bash_fn(f"port_in_use {fp}").returncode != 0
        r = _driver(tmp_path, 'check_engine_flags() { :; }\nlaunch_engine() { touch "$MARKER"; }\n', {"PORT": str(port)})
        assert r.returncode == 1 and "already in use" in r.stderr and not (tmp_path / "LAUNCHED").exists()
    finally:
        srv.close()


class _Stall:
    """A TCP listener that accepts connections and never answers (a wedged engine)."""

    def __enter__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        return self

    def __exit__(self, *a):
        self.sock.close()


def test_health_wait_and_flush_cannot_hang_on_a_stalled_engine(tmp_path):
    (tmp_path / "jd").mkdir()
    with _Stall() as st:
        base = {"BASE_URL": f"http://127.0.0.1:{st.port}", "JOB_DIR": str(tmp_path / "jd"), "SERVER_PID": "",
                "SERVER_LOG": "x", "HEALTH_CURL_MAX_S": "1", "FLUSH_CURL_MAX_S": "1", "FLUSH_TRIES": "2",
                "FLUSH_RETRY_S": "0", "STRICT_FLUSH": "0", "FLUSH_PATH": "/flush_cache"}
        t0 = time.time()
        r = bash_fn(f'SERVER_PID=""; wait_health "$BASE_URL/health" 1', env=base)
        assert r.returncode == 1 and "not healthy after 1s" in r.stderr and time.time() - t0 < 15
        t0 = time.time()
        r = bash_fn("flush_cache; echo rc=$?", env=base)
        assert "rc=1" in r.stdout and time.time() - t0 < 15
        assert "flush FAILED" in (tmp_path / "jd" / "job_events.log").read_text()


def test_wait_health_notices_a_dead_server_even_if_something_else_answers(tmp_path):
    r = bash_fn('sleep 0.1 & P=$!; wait $P; SERVER_PID=$P; SERVER_LOG=x; wait_health "http://127.0.0.1:9/health" 30')
    assert r.returncode == 1 and "server process died during startup" in r.stderr


TIME_ENV = {"SMOKE_RUN_S": "1800", "MISS_RUN_S": "2700", "GAP_S": "180", "RUN_OVERHEAD_S": "150", "CAP_RUN_S": "3000",
            "BURST_RUN_S": "8700", "TIME_MARGIN_S": "600", "STARTUP_ALLOW_S": "600"}


@pytest.mark.parametrize("env,want", [
    ({"MODE": "burst", "SEEDS": "0", "MULTS": "1.3"}, 8700 + 180 + 150),
    ({"MODE": "burst", "SEEDS": "0", "MULTS": "1.3 1.6"}, 2 * (8700 + 180 + 150)),
    ({"MODE": "cap", "SEEDS": "0", "MULTS": "1 1.4 1.8 2.2"}, 4 * (3000 + 180 + 150)),
    ({"MODE": "miss", "SEEDS": "0 1 2", "POP_CHECK": "64"}, 3 * (2700 + 180 + 150) + 2700 + 150),
    ({"MODE": "miss", "SEEDS": "0 1 2", "POP_CHECK": ""}, 3 * (2700 + 180 + 150)),
    ({"MODE": "smoke", "SEEDS": "0"}, 1800 + 150),
])
def test_planned_seconds(env, want):
    r = bash_fn("planned_seconds", env={**TIME_ENV, **env})
    assert r.returncode == 0 and int(r.stdout.strip()) == want


def test_time_budget_dies_when_the_plan_does_not_fit():
    two = {**TIME_ENV, "MODE": "burst", "SEEDS": "0", "MULTS": "1.3 1.6", "REMAINING_S_OVERRIDE": "14400"}
    r = bash_fn("check_time_budget pre", env=two)
    assert r.returncode == 1 and "do not fit" in r.stderr
    one = {**two, "MULTS": "1.3"}
    assert bash_fn("check_time_budget pre", env=one).returncode == 0
    # the post-startup check uses the time that is really left
    r = bash_fn("check_time_budget post", env={**one, "REMAINING_S_OVERRIDE": "9000"})
    assert r.returncode == 1 and "do not fit" in r.stderr
    # default E0a plan (3 seeds + population check) fits a 4 h job with the startup allowance; unknown time skips
    miss = {**TIME_ENV, "MODE": "miss", "SEEDS": "0 1 2", "POP_CHECK": "64", "REMAINING_S_OVERRIDE": "14400"}
    assert bash_fn("check_time_budget pre", env=miss).returncode == 0
    r = bash_fn("check_time_budget pre", env={**TIME_ENV, "MODE": "burst", "SEEDS": "0", "MULTS": "1.3", "SLURM_JOB_ID": ""})
    assert r.returncode == 0 and "skipped" in r.stdout


@pytest.mark.parametrize("txt,want", [("1-02:03:04", 93784), ("3:45:12", 13512), ("45:12", 2712), ("00:00:09", 9),
                                      ("UNLIMITED", ""), ("", "")])
def test_parse_slurm_time(txt, want):
    r = bash_fn(f'parse_slurm_time "{txt}"')
    assert r.returncode == 0 and r.stdout.strip() == str(want)


def _smoke(mode, tmp_path, port, **env):
    e = dict(os.environ, ENV_GEN=sys.prefix, RESULTS_ROOT=str(tmp_path), PORT=str(port), MULTS="1.0", SEEDS="0", POP_CHECK="")
    e.update(env)
    return subprocess.run([BASH, str(SLURM / "local_smoke.sh"), mode], capture_output=True, text=True, env=e, timeout=240, cwd=REPO)


def test_auto_output_feedback_is_refused_for_everything_but_smoke(tmp_path):
    r = _smoke("burst", tmp_path, 18101, OUTPUT_FEEDBACK="auto")
    assert r.returncode != 0 and "OUTPUT_FEEDBACK=auto is only allowed for MODE=smoke" in r.stderr
    r = _smoke("burst", tmp_path / "b", 18102, OUTPUT_FEEDBACK="maybe")
    assert r.returncode != 0 and "OUTPUT_FEEDBACK must be server|synthetic" in r.stderr
    r = _smoke("smoke", tmp_path / "c", 18103, OUTPUT_FEEDBACK="auto")                     # Stage 0 may use auto
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    runs = (next((tmp_path / "c" / "nova_job_logs").iterdir()) / "run_dirs_smoke.txt").read_text().split()
    assert json.loads((Path(runs[0]) / "meta.json").read_text())["output_feedback_configured"] == "auto"


def test_cap_and_burst_refuse_hardware_that_differs_from_the_calibration(tmp_path):
    for i, mode in enumerate(("cap", "burst")):
        r = _smoke(mode, tmp_path / mode, 18104 + i, FAKE_CALIB_HW="NVIDIA A100-SXM4-80GB, 81920 MiB")
        assert r.returncode != 0 and "hardware differs from the calibration" in r.stderr, mode
        jd = next((tmp_path / mode / "nova_job_logs").iterdir())
        assert not (jd / f"run_dirs_{mode}.txt").exists()                                  # no run was started
    r = _smoke("cap", tmp_path / "ok", 18106, FAKE_CALIB_HW="NVIDIA A100-SXM4-80GB, 81920 MiB", ALLOW_HW_MISMATCH="1")
    assert r.returncode == 0 and "ALLOW_HW_MISMATCH=1" in r.stdout


def test_a_flush_that_answers_200_but_does_not_empty_the_cache_is_caught(tmp_path):
    r = _smoke("cap", tmp_path / "strict", 18107, MOCK_EXTRA="--set flush_is_noop=true")
    assert r.returncode != 0 and "start-state check did not pass" in r.stderr
    jd = next((tmp_path / "strict" / "nova_job_logs").iterdir())
    assert "start state NOT verified" in (jd / "job_events.log").read_text()
    assert not (jd / "run_dirs_cap.txt").exists()                                          # died before any run
    res = json.loads((jd / "canary_1_check.json").read_text())
    assert res["exit_code"] == 1 and "still cached after flush" in res["reason"]
    # STRICT_FLUSH=0: the job goes on, but the run says in its meta.json that its start state was NOT verified
    r = _smoke("cap", tmp_path / "lax", 18108, MOCK_EXTRA="--set flush_is_noop=true", STRICT_FLUSH="0")
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    jd = next((tmp_path / "lax" / "nova_job_logs").iterdir())
    run = (jd / "run_dirs_cap.txt").read_text().split()[0]
    meta = json.loads((Path(run) / "meta.json").read_text())
    assert meta["start_state_verified"] is False and "check rc=1" in meta["start_state_detail"]
    an = sorted((tmp_path / "lax" / "agentload_analysis_stable").iterdir())[-1]
    guards = json.loads((an / "guards.json").read_text())
    assert "start_state_unverified" in guards["summary"]["codes"] and guards["summary"]["n_errors"] >= 1
