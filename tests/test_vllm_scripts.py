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
         "MODE": mode, "KV_TOKENS": kv_tokens, "HF_HOME": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path / "xdg")}
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
