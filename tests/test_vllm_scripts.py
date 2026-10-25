"""Static and unit tests for the second engine (vLLM v0.32.0) of the Nova job scripts: slurm/engine_vllm.sh,
slurm/vllm_job.sbatch and slurm/setup_vllm_env.sbatch. Nothing here contacts Nova or starts an engine: fake `vllm` / `python`
binaries record their argv and environment, a fake HTTP server plays /reset_prefix_cache, and the checks that need the real
v0.32.0 are the ones notes/VLLM_RUNBOOK.md section 3 lists as verified against its source.

The tests in tests/test_slurm_scripts.py (labels, directives, KV cap of 18750 blocks, billing guard of the older scripts) are
unchanged and still apply to the vLLM files."""
import os
import re
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

from conftest import REPO

SLURM = REPO / "slurm"
BASH = shutil.which("bash")
ENGINE = SLURM / "engine_vllm.sh"
JOB = SLURM / "vllm_job.sbatch"
SETUP = SLURM / "setup_vllm_env.sbatch"
VLLM_FILES = [ENGINE, JOB, SETUP]
GOOD_CTX = {"SLURM_JOB_ACCOUNT": "f2026.coms.6250.02", "SLURM_JOB_PARTITION": "instruction", "SLURM_JOB_QOS": "instruction"}

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

# Flags that vllm serve --help=all must list for slurm/engine_vllm.sh (checked by check_engine_flags); each was read from
# vllm/engine/arg_utils.py or vllm/entrypoints/launchers/cli_args.py at tag v0.32.0.
REQUIRED_FLAGS = ["--enable-prefix-caching", "--no-enable-prefix-caching", "--block-size", "--num-gpu-blocks-override",
                  "--gpu-memory-utilization", "--max-num-seqs", "--max-num-batched-tokens", "--enable-chunked-prefill",
                  "--scheduling-policy", "--max-model-len", "--hf-overrides", "--enable-prompt-tokens-details", "--host", "--port"]
OPTIONAL_FLAGS = ["--generation-config", "--revision", "--enforce-eager"]
# Names read from vllm/envs.py at the same tag.
ENV_NAMES = ["VLLM_ALLOW_LONG_MAX_MODEL_LEN", "VLLM_SERVER_DEV_MODE", "VLLM_USE_FLASHINFER_SAMPLER", "VLLM_NO_USAGE_STATS",
             "VLLM_USE_RUST_FRONTEND", "VLLM_CACHE_ROOT"]


def run_bash(code, env=None, timeout=60, cwd=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([BASH, "-c", code], capture_output=True, text=True, env=e, timeout=timeout, cwd=cwd)


def engine_fn(code, env=None, timeout=60):
    """Run `code` in bash after sourcing slurm/common.sh and then slurm/engine_vllm.sh (the order the job script uses)."""
    return run_bash(f'source "{SLURM}/common.sh"\nsource "{ENGINE}"\n{code}\n', env=env, timeout=timeout)


# ----------------------------------------------------------------------------------------------------------- syntax
@pytest.mark.parametrize("path", VLLM_FILES, ids=lambda p: p.name)
def test_bash_syntax(path):
    r = subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("path", VLLM_FILES, ids=lambda p: p.name)
def test_unix_line_endings(path):
    assert b"\r" not in path.read_bytes(), f"{path.name} has CR characters (core.autocrlf must stay false)"


def test_no_scheduler_command_runs_from_the_new_files():
    for p in (ENGINE, SETUP):
        for line in p.read_text().splitlines():
            code = line.split("#", 1)[0]
            assert not re.search(r"\b(sbatch|srun|salloc|ssh|scp)\b", code), (p.name, line)


# -------------------------------------------------------------------------------------------- setup_vllm_env.sbatch
def _directives(path):
    return [l[len("#SBATCH "):].strip() for l in path.read_text().splitlines() if l.startswith("#SBATCH ")]


def test_setup_directives_are_cpu_only_and_on_the_course_account():
    d = _directives(SETUP)
    for want in ("--account=f2026.coms.6250.02", "--partition=instruction", "--qos=instruction", "--cpus-per-task=8",
                 "--mem=32G", "--time=02:00:00", "--output=logs/%x-%j.out"):
        assert want in d, want
    assert not any("gres" in x or "gpus" in x for x in d), d         # the install phase must not reserve a GPU
    assert not any("6720" in x for x in d)
    text = SETUP.read_text()
    assert "NEVER SUBMITTED" in text and "PHASE=check" in text and "--gres=gpu:a100:1" in text and "--exclude=nova22-amp-7" in text


def _guard(path):
    t = path.read_text()
    return t[t.index("# ---- BILLING GUARD"):t.index("# ---- end billing guard")]


def test_setup_billing_guard_is_identical_to_the_other_scripts_and_comes_first():
    assert _guard(SETUP) == _guard(SLURM / "setup_nova.sbatch") == _guard(SLURM / "sglang_job.sbatch") == _guard(JOB)
    t = SETUP.read_text()
    head = t[:t.index("# ---- BILLING GUARD")]
    assert [l for l in head.splitlines() if l.strip() and not l.startswith("#")] == []
    assert "source " not in head


@pytest.mark.parametrize("ctx", [{"SLURM_JOB_ACCOUNT": "f2026.coms.6720.01"}, {"SLURM_JOB_PARTITION": "nova"},
                                 {"SLURM_JOB_QOS": "normal"}, {"SLURM_JOB_ACCOUNT": ""}],
                         ids=["wrong-account", "wrong-partition", "wrong-qos", "unknown-account"])
def test_setup_billing_guard_refuses_the_wrong_context(ctx, tmp_path):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SLURM_")}
    e.update(GOOD_CTX)
    e.update(ctx, SWAPP_ROOT=str(tmp_path / "swapp"), SBATCH_ACCOUNT="f2026.coms.6720.01")
    r = subprocess.run([BASH, str(SETUP)], capture_output=True, text=True, env=e, cwd=tmp_path)
    assert r.returncode == 2 and "FATAL: wrong or unknown SLURM context" in r.stderr
    assert not (tmp_path / "swapp").exists()                             # nothing was created before the guard


def _setup_env(tmp_path, **extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("SLURM_", "SBATCH_"))}
    e.update(GOOD_CTX)
    e.update(SWAPP_ROOT=str(tmp_path / "swapp"), **extra)
    return e


def _run_setup(tmp_path, **extra):
    return subprocess.run([BASH, str(SETUP)], capture_output=True, text=True, env=_setup_env(tmp_path, **extra), cwd=tmp_path, timeout=60)


def test_setup_pins_the_release_and_keeps_every_cache_on_class_storage():
    text = SETUP.read_text()
    assert ': "${VLLM_SPEC:=vllm==0.32.0}"' in text and ': "${EXPECT_TORCH:=2.13.0}"' in text
    assert ': "${EXPECT_CUDA_MAJOR:=13}"' in text and ': "${VLLM_PYTHON:=3.12}"' in text
    for needle in ('PIP_CACHE_DIR="$SWAPP_ROOT/cache/pip"', 'XDG_CACHE_HOME="$SWAPP_ROOT/cache"', 'CONDA_PKGS_DIRS="$SWAPP_ROOT/mamba-pkgs"',
                   'MAMBA_ROOT_PREFIX="$SWAPP_ROOT/mamba-root"', "envs/vllm.lock.txt", 'ENV_VLLM="$SWAPP_ROOT/envs/vllm"',
                   'micromamba create -y -p "$ENV_VLLM"', '"$VLLM_SPEC"', "pip check"):
        assert needle in text, needle
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        assert "$HOME" not in code and "~/" not in code, line            # home has a 10 GB quota


def test_setup_refuses_an_unpinned_spec_and_an_unknown_phase(tmp_path):
    r = _run_setup(tmp_path, VLLM_SPEC="vllm")
    assert r.returncode == 2 and "exact version" in r.stdout
    r = _run_setup(tmp_path, VLLM_SPEC="vllm>=0.32")
    assert r.returncode == 2
    r = _run_setup(tmp_path, PHASE="everything")
    assert r.returncode == 2 and "PHASE must be install|check" in r.stdout


def _fake_bin(tmp_path, **scripts):
    b = tmp_path / "fakebin"
    b.mkdir(exist_ok=True)
    for name, body in scripts.items():
        f = b / name
        f.write_text("#!/bin/sh\n" + body)
        f.chmod(0o755)
    return b


def test_setup_stops_before_building_anything_when_pypi_is_unreachable(tmp_path):
    b = _fake_bin(tmp_path, curl="exit 0\n")
    r = _run_setup(tmp_path, PATH=f"{b}{os.pathsep}{os.environ['PATH']}")
    assert r.returncode == 3 and "no outbound internet" in r.stdout
    assert not (tmp_path / "swapp" / "envs" / "vllm").exists()


def test_setup_needs_the_micromamba_module_after_the_internet_check(tmp_path):
    if shutil.which("micromamba"):
        pytest.skip("micromamba is on PATH here, so the script would not need the module")
    b = _fake_bin(tmp_path, curl='echo "HTTP/2 200"\n')
    r = _run_setup(tmp_path, PATH=f"{b}{os.pathsep}{os.environ['PATH']}")
    assert r.returncode == 4 and "module load" in r.stdout


def test_setup_check_phase_demands_a_gpu(tmp_path):
    (tmp_path / "swapp" / "envs" / "vllm" / "bin").mkdir(parents=True)
    py = tmp_path / "swapp" / "envs" / "vllm" / "bin" / "python"
    py.write_text("#!/bin/sh\nexit 0\n")
    py.chmod(0o755)
    # a PATH without nvidia-smi: keep only the directories of bash itself and coreutils
    bash_dir = str(Path(BASH).parent)
    r = _run_setup(tmp_path, PHASE="check", PATH=bash_dir)
    assert r.returncode == 7 and "needs a GPU" in r.stdout


# --------------------------------------------------------------------------------------------------- launch command
def _fake_env(tmp_path):
    envdir = tmp_path / "env"
    (envdir / "bin").mkdir(parents=True, exist_ok=True)
    marker, envfile = tmp_path / "argv.txt", tmp_path / "environ.txt"
    f = envdir / "bin" / "vllm"
    f.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{marker}"\nenv | sort > "{envfile}"\n')
    f.chmod(0o755)
    (tmp_path / "jd").mkdir(exist_ok=True)
    return envdir, marker, envfile


def _launch(tmp_path, kv_tokens="300000", mode="burst", help_text="", **extra):
    envdir, marker, envfile = _fake_env(tmp_path)
    (tmp_path / "jd" / "engine_help.txt").write_text(help_text)
    e = {"ENV_VLLM": str(envdir), "JOB_DIR": str(tmp_path / "jd"), "SERVER_LOG": str(tmp_path / "server.log"), "PORT": "1",
         "MODE": mode, "KV_TOKENS": kv_tokens, "HF_HOME": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path / "xdg"),
         "VLLM_CACHE_ROOT": "", "TRITON_CACHE_DIR": ""}
    e.update(extra)
    r = engine_fn("launch_engine\nwait", env=e)
    return r, (marker.read_text().splitlines() if marker.exists() else None), (envfile.read_text() if envfile.exists() else "")


def test_default_command_line_is_the_verified_one(tmp_path):
    r, argv, environ = _launch(tmp_path)
    assert r.returncode == 0, r.stderr
    assert argv[:2] == ["serve", "Qwen/Qwen2.5-7B-Instruct"]
    joined = " ".join(argv)
    for needle in ("--host 127.0.0.1", "--port 1", "--enable-prefix-caching", "--block-size 16", "--num-gpu-blocks-override 18750",
                   "--scheduling-policy fcfs", "--enable-chunked-prefill", "--max-num-seqs 256", "--max-num-batched-tokens 8192",
                   "--max-model-len 49152", "--enable-prompt-tokens-details", "--gpu-memory-utilization 0.90"):
        assert needle in joined, needle
    assert '--hf-overrides {"max_position_embeddings": 49152}' in joined      # sizes Qwen2's rotary cos/sin cache to the context
    assert "--no-enable-prefix-caching" not in joined and "--enforce-eager" not in joined
    assert "--generation-config" not in joined and "--revision" not in joined  # optional flags only when the help lists them / pinned


def test_environment_of_the_server_process(tmp_path):
    r, argv, environ = _launch(tmp_path)
    env = dict(l.split("=", 1) for l in environ.splitlines() if "=" in l)
    assert env["VLLM_ALLOW_LONG_MAX_MODEL_LEN"] == "1" and env["VLLM_SERVER_DEV_MODE"] == "1"     # /reset_prefix_cache needs dev mode
    assert env["VLLM_USE_FLASHINFER_SAMPLER"] == "0" and env["VLLM_USE_RUST_FRONTEND"] == "0"
    assert env["VLLM_NO_USAGE_STATS"] == "1" and env["DO_NOT_TRACK"] == "1" and env["HF_HUB_OFFLINE"] == "1"
    assert env["VLLM_CACHE_ROOT"].replace("\\", "/") == (tmp_path / "xdg" / "vllm").as_posix()    # class storage, not $HOME
    assert env["TRITON_CACHE_DIR"].replace("\\", "/") == (tmp_path / "xdg" / "triton").as_posix()
    assert env["PATH"].replace("\\", "/").startswith((tmp_path / "env" / "bin").as_posix() + ":")     # the env's bin/ comes first (ninja, python)


def test_miss_mode_turns_prefix_caching_off_and_keeps_the_pool_cap(tmp_path):
    r, argv, _ = _launch(tmp_path, mode="miss")
    joined = " ".join(argv)
    assert "--no-enable-prefix-caching" in argv and "--enable-prefix-caching" not in argv
    assert "--num-gpu-blocks-override 18750" in joined


def test_native_pool_drops_the_cap_but_keeps_the_block_size(tmp_path):
    r, argv, _ = _launch(tmp_path, kv_tokens="native")
    joined = " ".join(argv)
    assert "--num-gpu-blocks-override" not in joined and "native" not in joined
    assert "--block-size 16" in joined and "--enable-prefix-caching" in argv


@pytest.mark.parametrize("kv,blocks", [("300000", 18750), ("160000", 10000), ("300016", 18751)])
def test_pool_cap_is_kv_tokens_over_the_block_size(tmp_path, kv, blocks):
    _, argv, _ = _launch(tmp_path, kv_tokens=kv)
    assert f"--num-gpu-blocks-override {blocks}" in " ".join(argv)


def test_other_block_size_changes_the_block_count(tmp_path):
    _, argv, _ = _launch(tmp_path, BLOCK_SIZE="32")
    assert "--block-size 32" in " ".join(argv) and "--num-gpu-blocks-override 9375" in " ".join(argv)


def test_optional_flags_follow_the_help_and_the_revision_pin(tmp_path):
    _, argv, _ = _launch(tmp_path, help_text="  --generation-config GENERATION_CONFIG\n", HF_REVISION="a09a35458c702b33eeacc393d103063234e8bc28")
    joined = " ".join(argv)
    assert "--generation-config vllm" in joined and "--revision a09a35458c702b33eeacc393d103063234e8bc28" in joined


def test_enforce_eager_is_a_smoke_only_diagnostic(tmp_path):
    r, argv, _ = _launch(tmp_path, mode="smoke", ENFORCE_EAGER="1")
    assert r.returncode == 0 and "--enforce-eager" in argv
    r, argv, _ = _launch(tmp_path / "burst", mode="burst", ENFORCE_EAGER="1")
    assert r.returncode != 0 and argv is None and "ENFORCE_EAGER=1 is a diagnostic" in r.stderr    # refused before any server starts


def test_every_flag_the_launcher_passes_is_checked_before_launch(tmp_path):
    """check_engine_flags must cover each flag launch_engine can pass (a flag added to one place only fails here)."""
    help_text = "\n".join(f"  {f}" for f in REQUIRED_FLAGS + ["--generation-config", "--revision"]) + "\n"
    env = _check_env(tmp_path / "chk", help_text, HF_REVISION="abc", MODE="smoke")
    r = engine_fn("check_engine_flags", env=env)
    checked = set(re.findall(r"^(?:optional )?flag ok:\s+(--\S+)", r.stdout, re.M))
    assert r.returncode == 0, r.stdout
    _, argv, _ = _launch(tmp_path / "launch", mode="smoke", help_text=help_text, HF_REVISION="abc", ENFORCE_EAGER="1")
    passed = {t for t in argv if t.startswith("--")}
    assert passed <= checked | {"--enforce-eager"}, passed - checked - {"--enforce-eager"}
    assert {"--enable-prefix-caching", "--no-enable-prefix-caching"} <= checked        # both polarities are checked


# -------------------------------------------------------------------------------------------------- flag check
def _check_env(tmp_path, help_text, version="0.32.0", env_names=tuple(ENV_NAMES), **extra):
    tmp_path.mkdir(parents=True, exist_ok=True)
    envdir = tmp_path / "env"
    (envdir / "bin").mkdir(parents=True, exist_ok=True)
    pkg = tmp_path / "pkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "envs.py").write_text("\n".join(f'X_{i} = os.environ.get("{n}")' for i, n in enumerate(env_names)) + "\n")
    helpf = tmp_path / "help.txt"
    helpf.write_text(help_text)
    v = envdir / "bin" / "vllm"
    v.write_text('#!/bin/sh\n[ "$1 $2" = "serve --help=all" ] && cat "$HELP_FILE"\nexit 0\n')
    v.chmod(0o755)
    p = envdir / "bin" / "python"
    p.write_text('#!/bin/sh\ncase "$2" in\n *dirname*) echo "$PKGDIR";;\n *__version__*) echo "$FAKE_VER";;\n'
                 ' *torch*) echo "torch 2.13.0 cuda build 13.0 cuda available True fake-gpu";;\nesac\n')
    p.chmod(0o755)
    (tmp_path / "jd").mkdir(exist_ok=True)
    e = {"ENV_VLLM": str(envdir), "JOB_DIR": str(tmp_path / "jd"), "HELP_FILE": str(helpf), "PKGDIR": str(pkg), "FAKE_VER": version,
         "HF_HOME": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path / "xdg"), "MODE": "burst"}
    e.update(extra)
    return e


FULL_HELP = "\n".join(f"  {f}" for f in REQUIRED_FLAGS) + "\n"


def test_flag_check_passes_on_a_complete_install(tmp_path):
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path, FULL_HELP))
    assert r.returncode == 0, r.stdout
    assert "vllm version ok: 0.32.0" in r.stdout and "MISSING" not in r.stdout and "MISMATCH" not in r.stdout
    assert "optional flag missing: --generation-config" in r.stdout          # reported, not fatal
    assert (tmp_path / "jd" / "engine_help.txt").read_text() == FULL_HELP


@pytest.mark.parametrize("flag", REQUIRED_FLAGS)
def test_flag_check_fails_when_a_required_flag_is_missing(tmp_path, flag):
    help_text = "".join(l + "\n" for l in FULL_HELP.splitlines() if l.strip() != flag)
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path, help_text))
    assert r.returncode == 1 and f"flag MISSING: {flag}" in r.stdout
    r2 = engine_fn("check_engine_flags", env=_check_env(tmp_path / "lenient", help_text, STRICT_FLAGS="0"))
    assert r2.returncode == 0 and f"flag MISSING: {flag}" in r2.stdout       # STRICT_FLAGS=0 reports but continues


def test_flag_check_is_an_exact_token_match(tmp_path):
    # a longer flag name must not satisfy a shorter required one (e.g. --port-base for --port)
    help_text = FULL_HELP.replace("  --port\n", "  --port-base\n").replace("  --host\n", "  --hostname\n")
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path, help_text))
    assert r.returncode == 1 and "flag MISSING: --port" in r.stdout and "flag MISSING: --host" in r.stdout


def test_flag_check_refuses_another_vllm_version(tmp_path):
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path, FULL_HELP, version="0.31.0"))
    assert r.returncode == 1 and "vllm version MISMATCH: installed '0.31.0'" in r.stdout
    ok = engine_fn("check_engine_flags", env=_check_env(tmp_path / "ok", FULL_HELP, version="0.31.0", EXPECTED_VLLM_VERSION="0.31.0"))
    assert ok.returncode == 0


def test_flag_check_fails_when_an_env_var_name_is_not_in_the_installed_package(tmp_path):
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path, FULL_HELP, env_names=[n for n in ENV_NAMES if n != "VLLM_SERVER_DEV_MODE"]))
    assert r.returncode == 1 and "env var MISSING: VLLM_SERVER_DEV_MODE" in r.stdout


def test_revision_flag_is_required_only_when_a_revision_is_pinned(tmp_path):
    assert engine_fn("check_engine_flags", env=_check_env(tmp_path, FULL_HELP)).returncode == 0
    r = engine_fn("check_engine_flags", env=_check_env(tmp_path / "pin", FULL_HELP, HF_REVISION="abc"))
    assert r.returncode == 1 and "flag MISSING: --revision" in r.stdout


# ------------------------------------------------------------------------------------------------------- flush
def _flush_server(script):
    """HTTP server answering POSTs with the (status, body) pairs of `script` in order, then the last one forever."""
    calls = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            status, body = script[min(len(calls), len(script) - 1)]
            calls.append(self.path)
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, calls


def _flush(tmp_path, script, strict="1", tries="4"):
    srv, calls = _flush_server(script)
    try:
        (tmp_path / "jd").mkdir(parents=True, exist_ok=True)
        r = engine_fn("flush_cache; echo FLUSH_RC=$?",
                      env={"BASE_URL": f"http://127.0.0.1:{srv.server_address[1]}", "JOB_DIR": str(tmp_path / "jd"),
                           "FLUSH_RETRY_S": "0", "FLUSH_TRIES": tries, "FLUSH_CURL_MAX_S": "5", "STRICT_FLUSH": strict})
    finally:
        srv.shutdown()
    return r, calls, (tmp_path / "jd" / "job_events.log").read_text() if (tmp_path / "jd" / "job_events.log").exists() else ""


def test_flush_endpoint_and_method_are_the_dev_mode_route():
    r = engine_fn('echo "$FLUSH_METHOD $FLUSH_PATH $HEALTH_PATH"')
    assert r.stdout.strip() == "POST /reset_prefix_cache /health"


def test_flush_succeeds_immediately_on_success_true(tmp_path):
    r, calls, ev = _flush(tmp_path, [(200, '{"success":true}')])
    assert "FLUSH_RC=0" in r.stdout and calls == ["/reset_prefix_cache"] and "success=true" in ev


def test_http_200_with_success_false_is_retried_until_the_blocks_are_free(tmp_path):
    r, calls, ev = _flush(tmp_path, [(200, '{"success": false}'), (200, '{"success":false}'), (200, '{"success":true}')])
    assert "FLUSH_RC=0" in r.stdout and len(calls) == 3 and "after 2 retries" in ev


def test_a_server_error_is_retried_too(tmp_path):
    r, calls, _ = _flush(tmp_path, [(503, "unavailable"), (200, '{"success": true}')])
    assert "FLUSH_RC=0" in r.stdout and len(calls) == 2


def test_flush_that_never_succeeds_is_logged_and_fatal_only_under_strict_flush(tmp_path):
    r, calls, ev = _flush(tmp_path / "lenient", [(200, '{"success": false}')], strict="0", tries="3")
    assert "FLUSH_RC=1" in r.stdout and len(calls) == 3 and "flush FAILED" in ev and "success" in ev
    r2, calls2, ev2 = _flush(tmp_path / "strict", [(200, '{"success": false}')], strict="1", tries="3")
    assert "FLUSH_RC" not in r2.stdout and r2.returncode == 1 and "STRICT_FLUSH=1 and flush failed" in r2.stderr and len(calls2) == 3


# ------------------------------------------------------------------ names shared with the harness configs
def test_harness_metric_candidates_list_the_names_verified_in_v0_32_0():
    """vllm/v1/metrics/loggers.py at v0.32.0 registers these (counters carry the _total suffix in the Prometheus text)."""
    cfg = yaml.safe_load((REPO / "configs" / "agentload_analysis.yaml").read_text())["engine_metrics"]
    assert "vllm:num_requests_waiting" in cfg["waiting"]["names"]
    assert "vllm:num_requests_running" in cfg["running"]["names"]
    assert "vllm:kv_cache_usage_perc" in cfg["cache_usage"]["names"]
    assert "vllm:prefix_cache_hits_total" in cfg["hit_counter"]["names"]
    assert "vllm:prefix_cache_queries_total" in cfg["query_counter"]["names"]
    from agentload.config import CanaryCfg
    c = CanaryCfg()
    assert "vllm:num_requests_waiting" in c.waiting_metrics and "vllm:num_requests_running" in c.running_metrics
    assert "vllm:kv_cache_usage_perc" in c.kv_in_use_metrics
    assert c.max_cached_after_flush == 15                                      # one 16-token vLLM block, with --block-size 16
    assert c.tokens == 1024                                                     # canary prime: 1008 cached of 1024 >= 0.5 x tokens


def test_request_body_fields_are_vllm_completion_request_fields():
    """CompletionRequest (vllm/entrypoints/openai/completion/protocol.py) defines ignore_eos, repetition_penalty, top_p and
    return_token_ids; the response carries choices[0].token_ids and usage.prompt_tokens_details.cached_tokens."""
    cfg = yaml.safe_load((REPO / "configs" / "agentload_e2_burst.yaml").read_text())
    assert set(cfg["server"]["extra_body"]) == {"ignore_eos", "repetition_penalty", "top_p"}
    from agentload.config import ServerCfg
    assert "choices.0.token_ids" in ServerCfg().output_ids_paths
    client = (REPO / "src" / "agentload" / "client.py").read_text()
    assert 'body["return_token_ids"] = True' in client
    assert "usage.prompt_tokens_details" in (REPO / "src" / "agentload" / "parse.py").read_text()


def test_cache_roots_can_be_redirected_to_a_job_local_directory(tmp_path):
    _, _, environ = _launch(tmp_path, VLLM_CACHE_ROOT=str(tmp_path / "local-cc"), TRITON_CACHE_DIR=str(tmp_path / "local-tr"))
    env = dict(l.split("=", 1) for l in environ.splitlines() if "=" in l)
    assert env["VLLM_CACHE_ROOT"].replace("\\", "/") == (tmp_path / "local-cc").as_posix()
    assert env["TRITON_CACHE_DIR"].replace("\\", "/") == (tmp_path / "local-tr").as_posix()


# ------------------------------------------------------------ the whole job against a vLLM-like server
import socket
import sys


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _job_env_with_fake_vllm(tmp_path, port, mode="smoke", **extra):
    """Environment for `source common.sh; source engine_vllm.sh; job_main` with a fake `vllm` that serves the mock engine."""
    env = _check_env(tmp_path / "eng", FULL_HELP, MODE=mode)
    vllm_bin = Path(env["ENV_VLLM"]) / "bin" / "vllm"
    vllm_bin.write_text('#!/bin/sh\n[ "$1 $2" = "serve --help=all" ] && { cat "$HELP_FILE"; exit 0; }\n'
                        'exec "$FAKE_PY" "$HELPER" "$@"\n')
    vllm_bin.chmod(0o755)
    env.update(FAKE_PY=sys.executable, HELPER=str(REPO / "tests" / "helpers_vllm_server.py"), FAKE_VLLM_LIFETIME_S="150",
               ENV_GEN=sys.prefix, RESULTS_ROOT=str(tmp_path / "res"), PORT=str(port), MODE=mode,
               ENGINE_LABEL="vllm-smoke", SEEDS="0", OUTPUT_FEEDBACK="server", KV_TOKENS="300000", GAP_S="1",
               HEALTH_TIMEOUT_S="60", POP="4", SMOKE_RUN_S="8", STRICT_FLUSH="1", HF_REVISION="",
               GEN_EXTRA="--set workload.initial_context_tokens=200 --set workload.new_prompt_tokens=55 --set workload.decode_tokens=10 "
                         "--set workload.mean_turns=4 --set workload.max_turns=12 --set workload.tool_time_mean_s=0.3 "
                         "--set run.preflight_wait_s=10 --set metrics.interval_s=1",
               ANALYSIS_EXTRA="--set windows.window_s=3 --set windows.fine_window_s=1")
    env.update(extra)
    return env


def run_job(env, timeout):
    """job_main with REPO_DIR set the way slurm/local_smoke.sh sets it (a POSIX path, so PYTHONPATH converts on Windows too)."""
    return engine_fn(f'REPO_DIR="$(cd "{REPO.as_posix()}" && pwd)"; export REPO_DIR\njob_main', env=env, timeout=timeout)


def test_smoke_job_runs_end_to_end_through_the_real_vllm_launcher(tmp_path):
    """job_main with the real engine_vllm.sh: flag/version check, launch (fake vllm), /health, /v1/models, probe, the overridden
    flush_cache inside reset_and_verify (STRICT_FLUSH=1: the canary must prove the cache was emptied), one closed run, analysis."""
    env = _job_env_with_fake_vllm(tmp_path, _free_port())
    r = run_job(env, 240)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert "0 failed" in r.stdout and "vllm version ok: 0.32.0" in r.stdout and "CANARY_RESULT" in r.stdout
    logs = list((tmp_path / "res" / "nova_job_logs").iterdir())
    assert len(logs) == 1
    ev = (logs[0] / "job_events.log").read_text()
    assert "flush HTTP 200 success=true" in ev and "reset_and_verify: verified=true" in ev
    banner = (logs[0] / "banner.txt").read_text()
    assert "ENGINE=vllm" in banner and "MODE=smoke" in banner and "KV_TOKENS=300000" in banner
    probe = (logs[0] / "probe.txt").read_text()
    assert "PROBE_SUMMARY" in probe and "vllm:num_requests_waiting" in probe
    assert "vllm version ok" in (logs[0] / "flag_check.txt").read_text()
    run_dir = Path((logs[0] / "run_dirs_smoke.txt").read_text().split()[0])
    assert (run_dir / "meta.json").exists()


def test_job_stops_before_launching_when_the_installed_vllm_is_not_the_verified_release(tmp_path):
    env = _job_env_with_fake_vllm(tmp_path, _free_port(), FAKE_VER="0.31.0")
    r = run_job(env, 120)
    assert r.returncode != 0 and "vllm version MISMATCH" in r.stdout and "flag/env-var check failed" in r.stderr
    assert not (tmp_path / "res" / "nova_job_logs").exists() or not list((tmp_path / "res" / "nova_job_logs").glob("*/server.log"))


def test_a_flush_that_keeps_answering_success_false_aborts_the_job_under_strict_flush(tmp_path):
    env = _job_env_with_fake_vllm(tmp_path, _free_port(), FLUSH_TRIES="2", FLUSH_RETRY_S="0", FAKE_VLLM_RESET="fail")
    r = run_job(env, 120)
    assert r.returncode != 0 and "STRICT_FLUSH=1 and flush failed" in r.stderr
    ev = list((tmp_path / "res" / "nova_job_logs").glob("*/job_events.log"))[0].read_text()
    assert "flush FAILED" in ev and "success" in ev


# ------------------------------------------------------------------------------------------ the runbook
RUNBOOK = REPO / "notes" / "VLLM_RUNBOOK.md"


def test_runbook_lines_agree_with_the_scripts_and_the_registration():
    t = RUNBOOK.read_text()
    reg = yaml.safe_load((REPO / "configs" / "agentload_prereg_2026-10-24.yaml").read_text())
    mults = reg["lambda_selection"]["lambda_mults"]
    assert "for m in " + " ".join(str(m) for m in mults) in t                  # the two registered multiples, nothing else
    assert reg["measured"]["hardware"] in t
    for rel in set(re.findall(r"slurm/[A-Za-z0-9_]+\.(?:sbatch|sh)", t)):
        assert (REPO / rel).exists(), rel
    sbatch_lines = [l.strip() for l in t.splitlines() if l.strip().startswith("sbatch ")]
    assert len(sbatch_lines) == 5                                                  # install, check, smoke, E0a, the burst loop
    for l in sbatch_lines:
        assert "$SLURMOPT" in l, l                                                # account, partition and QoS on every submission
        assert l.rstrip().endswith(".sbatch"), l
    assert "--account=f2026.coms.6250.02" in t and "f2026.coms.6720" not in t
    assert 'SLURMOPT="--account=f2026.coms.6250.02 --partition=instruction --qos=instruction"' in t
    assert "ENGINE_LABEL=vllm-fcfs" in t and "ARMS=burst" in t and "MODE=miss" in t and "MODE=smoke" in t
    assert re.search(r"derive-exploratory --from configs/agentload_prereg_2026-10-24\.yaml", t)
    for line in t.splitlines():
        if line.strip().startswith(("ssh ", "scp ", "squeue", "sacct")):
            raise AssertionError(line)


def test_runbook_gpu_hours_follow_the_plan_formula():
    """0.25 h startup + k x (run_s + 150)/3600 + g x 180/3600 + 0.05 h teardown, as in analysis/plan_budget.py."""
    def job(k, run_s, gaps):
        return 0.25 + k * (run_s + 150) / 3600 + gaps * 180 / 3600 + 0.05
    smoke, e0a, burst = job(1, 1800, 0), job(4, 2700, 3), job(1, 8700, 1)
    assert (round(smoke, 2), round(e0a, 2), round(6 * burst, 2)) == (0.84, 3.62, 16.85)
    assert round(smoke + e0a + 6 * burst, 2) == 21.31
    t = RUNBOOK.read_text()
    for needle in ("0.84", "3.62", "16.85", "21.31"):
        assert needle in t


# ------------------------------------------------------------ setup_vllm_env.sbatch, install phase with fake tools
FAKE_ENV_PYTHON = r"""#!/bin/sh
# fake env python: pip is simulated (the "install" writes a dist-info for $FAKE_PIP_VERSION); everything else runs the real python,
# which sees a fake torch and the fake vllm metadata through PYTHONPATH
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  echo "pip $3 $4 $5" >> "$FAKE_LOG"
  case "$3" in
    install) case "$*" in *vllm==*) mkdir -p "$FAKE_SITE/vllm-$FAKE_PIP_VERSION.dist-info"
             printf 'Metadata-Version: 2.1\nName: vllm\nVersion: %s\n' "$FAKE_PIP_VERSION" > "$FAKE_SITE/vllm-$FAKE_PIP_VERSION.dist-info/METADATA";; esac;;
    check) echo "No broken requirements found.";;
    freeze) echo "vllm==$FAKE_PIP_VERSION"; echo "torch==2.13.0";;
    index) echo "vllm (0.32.0)";;
  esac
  exit 0
fi
[ "$1" = "--version" ] && { echo "Python 3.12.0"; exit 0; }
exec "$REAL_PY" "$@"
"""

FAKE_MICROMAMBA = r"""case "$1" in
  --version) echo 1.4.2;;
  create) prefix=; while [ $# -gt 0 ]; do [ "$1" = "-p" ] && prefix="$2"; shift; done
          mkdir -p "$prefix/bin"; cp "$FAKE_ENV_PY" "$prefix/bin/python"; chmod +x "$prefix/bin/python"; echo "created $prefix" >> "$FAKE_LOG";;
  env) echo "name: fake";;
esac
"""


def _install_env(tmp_path, pip_version="0.32.0", torch_cuda="13.0", **extra):
    tmp_path.mkdir(parents=True, exist_ok=True)
    site = tmp_path / "site"
    (site / "torch").mkdir(parents=True, exist_ok=True)
    (site / "torch" / "__init__.py").write_text(
        "import os, types\n__version__ = '2.13.0+cu130'\nversion = types.SimpleNamespace(cuda=os.environ['FAKE_TORCH_CUDA'])\n"
        "cuda = types.SimpleNamespace(is_available=lambda: False)\n")
    envpy = tmp_path / "fake_env_python"
    envpy.write_text(FAKE_ENV_PYTHON)
    b = _fake_bin(tmp_path, curl='echo "HTTP/2 200"\n', micromamba=FAKE_MICROMAMBA)
    log = tmp_path / "fake.log"
    return dict(PATH=f"{b}{os.pathsep}{os.environ['PATH']}", FAKE_SITE=str(site), PYTHONPATH=str(site), FAKE_ENV_PY=str(envpy),
                FAKE_LOG=str(log), FAKE_PIP_VERSION=pip_version, FAKE_TORCH_CUDA=torch_cuda, REAL_PY=sys.executable, **extra), log


def test_setup_install_phase_builds_verifies_and_records_the_env(tmp_path):
    env, log = _install_env(tmp_path)
    r = _run_setup(tmp_path, **env)
    assert r.returncode == 0, r.stdout[-2500:] + r.stderr[-1500:]
    for needle in ("pypi: HTTP/2 200", "=== 3. pip install vllm==0.32.0", "VERSIONS_OK", "SETUP_DONE install"):
        assert needle in r.stdout, needle
    swapp = tmp_path / "swapp"
    assert (swapp / "envs" / "vllm" / "bin" / "python").exists()
    assert "vllm==0.32.0" in (swapp / "envs" / "vllm.lock.txt").read_text() and (swapp / "envs" / "vllm.micromamba.yml").exists()
    calls = log.read_text()
    assert "created" in calls and "pip install --upgrade pip" in calls and "pip install vllm==0.32.0" in calls and "pip check" in calls
    assert "PIP_CACHE_DIR=" in r.stdout and "/cache/pip" in r.stdout.replace("\\", "/")              # caches on class storage
    # second run: the pinned release is already there, so nothing is installed again
    before = log.read_text().count("pip install vllm==")
    r2 = _run_setup(tmp_path, **env)
    assert r2.returncode == 0 and "already installed; re-verifying only" in r2.stdout
    assert log.read_text().count("pip install vllm==") == before


def test_setup_install_phase_fails_loudly_on_the_wrong_release_or_a_cuda_12_torch(tmp_path):
    env, _ = _install_env(tmp_path / "a", pip_version="0.31.0")
    r = _run_setup(tmp_path / "a", **env)
    assert r.returncode == 6 and "VERSIONS_BAD" in r.stdout and "vllm 0.31.0 != 0.32.0" in r.stdout
    env, _ = _install_env(tmp_path / "b", torch_cuda="12.9")
    r = _run_setup(tmp_path / "b", **env)
    assert r.returncode == 6 and "expected a CUDA 13.x build" in r.stdout
    assert not (tmp_path / "b" / "swapp" / "envs" / "vllm.lock.txt").exists()          # no lock file for a rejected env


def test_python_heredocs_of_the_setup_script_are_valid_python():
    """The GPU check phase cannot run off Nova; at least every embedded Python block must parse."""
    import ast
    text = SETUP.read_text()
    blocks = re.findall(r"<<'PY'[^\n]*\n(.*?)\nPY\n", text, re.S)
    assert len(blocks) == 3                                    # report_versions, assert_versions, the GPU import check
    for b in blocks:
        ast.parse(b)
    assert "torch.cuda.is_available()" in blocks[2] and "vllm._custom_ops" in blocks[2] and "bf16" in blocks[2]
