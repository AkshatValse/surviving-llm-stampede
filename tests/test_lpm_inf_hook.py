"""The LPM_INF=1 job-local hook (slurm/hooks/lpm_inf/sitecustomize.py) and its glue in slurm/engine_sglang.sh / common.sh.

Everything here runs on a stand-in `sglang` package (no torch, no GPU) whose schedule_policy.py has the stock 0.5.22
shape: WAITING_QUEUE_PREFIX_MATCH_MAX = 128 and the real _determine_active_policy body. The self-test against the REAL
installed SGLang runs on the Nova login node (import only); see notes/E2_RUNBOOK.md.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conftest import REPO

SLURM = REPO / "slurm"
HOOK_DIR = SLURM / "hooks" / "lpm_inf"
HOOK = HOOK_DIR / "sitecustomize.py"
BASH = shutil.which("bash")
VAR = "PM_WAITING_QUEUE_PREFIX_MATCH_MAX"
INF = "1000000000"
STOCK_MD5 = "b8ec334ac1ed028e3c176022ea1f9143"      # sglang 0.5.22 srt/managers/schedule_policy.py (envs/sglang on Nova)
BASE_COMMIT = "582c2a6"                             # origin/main before the hook: the stock engine_sglang.sh
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")
posix_only = pytest.mark.skipif(os.name == "nt", reason="bash $! is an MSYS pid on Windows, not the python pid")

SCHEDULE_POLICY = textwrap.dedent('''\
    """Stand-in for sglang 0.5.22 srt/managers/schedule_policy.py: the constant and the real switch body."""
    from enum import Enum


    class CacheAwarePolicy(Enum):
        LPM = "lpm"
        DFS_WEIGHT = "dfs-weight"


    class CacheAgnosticPolicy(Enum):
        FCFS = "fcfs"


    # Arbitrary; bounds per-round prefix work on the waiting queue.
    WAITING_QUEUE_PREFIX_MATCH_MAX = {stock}


    class SchedulePolicy:
        def _determine_active_policy(self, waiting_queue):
            if (
                self.policy
                in (
                    CacheAwarePolicy.LPM,
                )
                and len(waiting_queue) > WAITING_QUEUE_PREFIX_MATCH_MAX
            ):
                return CacheAgnosticPolicy.FCFS
            return self.policy
    ''')

LAUNCH_SERVER = textwrap.dedent('''\
    """Stand-in for `python -m sglang.launch_server`: spawns one 'scheduler' child that imports schedule_policy."""
    import multiprocessing as mp
    import sys


    def scheduler():
        import sglang.srt.managers.schedule_policy as sp
        print("child sees", sp.WAITING_QUEUE_PREFIX_MATCH_MAX, flush=True)


    if __name__ == "__main__":
        mp.set_start_method("spawn", force=True)
        p = mp.Process(target=scheduler)
        p.start()
        p.join()
        sys.exit(p.exitcode)
    ''')


def make_fake_sglang(site: Path, stock=128):
    pkg = site / "sglang" / "srt" / "managers"
    pkg.mkdir(parents=True)
    for d in (site / "sglang", site / "sglang" / "srt", pkg):
        (d / "__init__.py").write_text("")
    (pkg / "schedule_policy.py").write_text(SCHEDULE_POLICY.format(stock=stock), newline="\n")
    (site / "sglang" / "launch_server.py").write_text(LAUNCH_SERVER, newline="\n")
    return pkg / "schedule_policy.py"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def fwd(p) -> str:
    return str(p).replace("\\", "/")


def make_fake_env(root: Path, stock=128, record=False):
    """A fake ENV_SGLANG prefix: bin/python is a bash shim onto this interpreter with the stand-in package appended to
    PYTHONPATH (after the hook dir, like site-packages comes after PYTHONPATH). record=True: it only records argv/env."""
    site = root / "site"
    sp = make_fake_sglang(site, stock)
    (root / "bin").mkdir(parents=True)
    shim = root / "bin" / "python"
    if record:
        body = 'printf "%s\\n" "$0" "$@" > "$(dirname "$0")/../rec_argv"; env | LC_ALL=C sort > "$(dirname "$0")/../rec_env"\n'
    else:
        body = (f'export PYTHONPATH="${{PYTHONPATH:+$PYTHONPATH{os.pathsep}}}{fwd(site)}"\n'
                f'exec "{fwd(sys.executable)}" "$@"\n')
    shim.write_text("#!/usr/bin/env bash\n" + body, newline="\n")
    shim.chmod(0o755)
    return sp


def run_bash(script: str, env_extra: dict, cwd: Path):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", VAR, "LPM_INF", "MODE", "POLICY")}
    env.update(env_extra)
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True, env=env, cwd=cwd, timeout=180)


SOURCE = 'source "$REPO_DIR/slurm/common.sh"; source "$ENGINE_FILE"; '


def glue_env(**kw):
    e = {"REPO_DIR": fwd(REPO), "ENGINE_FILE": fwd(SLURM / "engine_sglang.sh")}
    e.update(kw)
    return e


# ------------------------------------------------------------------ the hook itself

def test_pinned_md5s_match_the_files():
    text = (SLURM / "engine_sglang.sh").read_text()
    assert re.search(r"^LPM_INF_HOOK_MD5=([0-9a-f]{32})\b", text, re.M).group(1) == md5(HOOK)
    assert re.search(r"^LPM_INF_STOCK_MD5=([0-9a-f]{32})\b", text, re.M).group(1) == STOCK_MD5
    assert re.search(r"^LPM_INF_MAX=(\d+)\b", text, re.M).group(1) == INF
    assert b"\r" not in HOOK.read_bytes()


CHILD_TEST = textwrap.dedent('''\
    import multiprocessing as mp, os, sys, types


    def probe():
        from sglang.srt.managers import schedule_policy as sp
        me = types.SimpleNamespace(policy=sp.CacheAwarePolicy.LPM)
        return (os.getpid(), sp.WAITING_QUEUE_PREFIX_MATCH_MAX,
                sp.SchedulePolicy._determine_active_policy(me, [None] * 300).value,
                sp.SchedulePolicy._determine_active_policy(me, [None] * 100).value)


    def child(q):
        q.put(probe())


    if __name__ == "__main__":
        mp.set_start_method("spawn", force=True)
        print("parent", *probe(), flush=True)
        q = mp.Queue()
        p = mp.Process(target=child, args=(q,))
        p.start()
        print("child", *q.get(), flush=True)
        p.join()
        print("childpid", p.pid, flush=True)
    ''')


@pytest.mark.parametrize("hooked", [True, False], ids=["with_var", "without_var"])
def test_spawn_child_sees_the_patch_only_with_the_env_var(hooked, tmp_path):
    site = tmp_path / "site"
    make_fake_sglang(site)
    script = tmp_path / "child_test.py"
    script.write_text(CHILD_TEST)
    env = {k: v for k, v in os.environ.items() if k != VAR}
    env["PYTHONPATH"] = os.pathsep.join([str(HOOK_DIR), str(site)])
    if hooked:
        env[VAR] = INF
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stderr
    rows = {l.split()[0]: l.split()[1:] for l in r.stdout.splitlines()}
    want = [INF, "lpm", "lpm"] if hooked else ["128", "fcfs", "lpm"]
    assert rows["parent"][1:] == want and rows["child"][1:] == want
    ppid, cpid = rows["parent"][0], rows["child"][0]
    assert cpid != ppid and rows["childpid"] == [cpid]
    markers = re.findall(r"^\[pm-lpminf-hook\] pid=(\d+) ppid=(\d+) (\S+) 128 -> (\d+) file=(.*)$", r.stderr, re.M)
    if hooked:
        assert sorted(m[0] for m in markers) == sorted([ppid, cpid])          # one marker per process
        assert all(m[2] == "sglang.srt.managers.schedule_policy.WAITING_QUEUE_PREFIX_MATCH_MAX" and m[3] == INF for m in markers)
        assert [m[1] for m in markers if m[0] == cpid] == [ppid]               # the child's parent is the parent
    else:
        assert markers == [] and "pm-lpminf-hook" not in r.stderr


def _import_with_hook(site, value, tmp_path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(HOOK_DIR), str(site)]), **{VAR: value})
    return subprocess.run([sys.executable, "-c", "import sglang.srt.managers.schedule_policy as sp; print(sp.WAITING_QUEUE_PREFIX_MATCH_MAX)"],
                          capture_output=True, text=True, env=env, cwd=tmp_path, timeout=60)


def test_hook_refuses_a_stock_value_other_than_128(tmp_path):
    make_fake_sglang(tmp_path / "site", stock=64)
    r = _import_with_hook(tmp_path / "site", INF, tmp_path)
    assert r.returncode != 0 and "refusing to patch" in r.stderr and "found 64" in r.stderr


@pytest.mark.parametrize("value", ["abc", "128", "5"])
def test_hook_refuses_a_bad_target_value(value, tmp_path):
    make_fake_sglang(tmp_path / "site")
    r = _import_with_hook(tmp_path / "site", value, tmp_path)
    assert r.returncode != 0 and "[pm-lpminf-hook]" in r.stderr


def test_hook_leaves_other_modules_alone(tmp_path):
    make_fake_sglang(tmp_path / "site")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(HOOK_DIR), str(tmp_path / "site")]), **{VAR: INF})
    r = subprocess.run([sys.executable, "-c", "import json, sglang.srt.managers as m; print('ok')"], capture_output=True,
                       text=True, env=env, cwd=tmp_path, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "ok" and "pm-lpminf-hook" not in r.stderr


# ------------------------------------------------------------------ bash glue

@needs_bash
@pytest.mark.parametrize("path", ["engine_sglang.sh", "common.sh", "sglang_job.sbatch"])
def test_bash_syntax(path):
    r = subprocess.run([BASH, "-n", str(SLURM / path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


SELFTEST = SOURCE + ('[ -n "${OVR_STOCK:-}" ] && LPM_INF_STOCK_MD5="$OVR_STOCK"; [ -n "${OVR_HOOK:-}" ] && LPM_INF_HOOK_MD5="$OVR_HOOK"; '
                     'check_lpm_inf_hook "$ENV_SGLANG/bin/python"; echo "RC=$?"')


@needs_bash
def test_self_test_passes_on_the_stand_in_when_its_md5_is_the_pinned_one(tmp_path):
    sp = make_fake_env(tmp_path / "env")
    r = run_bash(SELFTEST, glue_env(LPM_INF="1", POLICY="lpm", MODE="burst", ENV_SGLANG=fwd(tmp_path / "env"),
                                    OVR_STOCK=md5(sp)), tmp_path)
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    assert f"lpm_inf_selftest value={INF} md5={md5(sp)} hook_md5={md5(HOOK)} active100=lpm active300=lpm" in r.stdout
    assert "lpm_inf_selftest value=128" in r.stdout and "active300=fcfs" in r.stdout          # the control import
    assert f"128 -> {INF} file=" in r.stdout and "lpm_inf hook ok" in r.stdout


@needs_bash
@pytest.mark.parametrize("case", ["stock_md5_mismatch", "hook_md5_mismatch", "policy_fcfs", "mode_miss",
                                  "pythonpath_set", "stock_value_64"])
def test_self_test_refuses(case, tmp_path):
    sp = make_fake_env(tmp_path / "env", stock=64 if case == "stock_value_64" else 128)
    e = glue_env(LPM_INF="1", POLICY="lpm", MODE="burst", ENV_SGLANG=fwd(tmp_path / "env"), OVR_STOCK=md5(sp))
    if case == "stock_md5_mismatch":
        e.pop("OVR_STOCK")                 # the stand-in is not the real 0.5.22 file: its md5 differs from the pinned one
    elif case == "hook_md5_mismatch":
        e["OVR_HOOK"] = "0" * 32
    elif case == "policy_fcfs":
        e["POLICY"] = "fcfs"
    elif case == "mode_miss":
        e["MODE"] = "miss"
    elif case == "pythonpath_set":
        e["PYTHONPATH"] = fwd(tmp_path)
    r = run_bash(SELFTEST, e, tmp_path)
    assert "RC=1" in r.stdout and "lpm_inf FAILED" in r.stdout, r.stdout + r.stderr
    assert "lpm_inf hook ok" not in r.stdout


@needs_bash
def test_lpm_inf_0_functions_are_silent_noops(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("")
    script = SOURCE + ('check_lpm_inf_hook /nonexistent/python; echo "A=$?"; SERVER_PID=1; SERVER_LOG="$LOG"; '
                       'engine_post_health_check; echo "B=$?"; echo "PREFIX=$(engine_env_prefix) VARS=$(engine_required_vars)"')
    r = run_bash(script, glue_env(LPM_INF="0", POLICY="lpm", MODE="burst", ENV_SGLANG="/e", LOG=fwd(log)), tmp_path)
    assert r.stdout.splitlines() == ["A=0", "B=0", "PREFIX=/e VARS=ENV_SGLANG HF_HOME"], r.stdout + r.stderr


POST = SOURCE + 'SERVER_PID=100; SERVER_LOG="$LOG"; JOB_DIR="$JD"; engine_post_health_check; echo "RC=$?"'
MARK = "[pm-lpminf-hook] pid={pid} ppid={ppid} sglang.srt.managers.schedule_policy.WAITING_QUEUE_PREFIX_MATCH_MAX 128 -> {v} file=/x/schedule_policy.py"


@needs_bash
@pytest.mark.parametrize("lines,ok", [
    ([MARK.format(pid=100, ppid=50, v=INF)], False),                                            # only the server pid
    ([MARK.format(pid=100, ppid=50, v=INF), MARK.format(pid=101, ppid=100, v=INF)], True),       # plus the scheduler
    (["Loading safetensors: 50%|#####\r" + MARK.format(pid=101, ppid=100, v=INF)], True),       # after a partial line
    ([MARK.format(pid=101, ppid=100, v="999")], False),                                         # wrong value
    ([MARK.format(pid=101, ppid=100, v=INF), MARK.format(pid=102, ppid=100, v="999")], False),   # one wrong value
    (["INFO server started", "[pm-lpminf-hook] pid=101 ppid=100"], False),                       # truncated marker
    ([], False),                                                                                 # hook never ran
    ([MARK.format(pid=101, ppid=100, v=INF),
      "RuntimeError: [pm-lpminf-hook] expected stock WAITING_QUEUE_PREFIX_MATCH_MAX=128 in /x, found 64; refusing to patch"], False),
], ids=["parent_only", "child", "midline", "wrong_value", "one_wrong", "truncated", "none", "refused"])
def test_post_health_check_on_fake_logs(lines, ok, tmp_path):
    log = tmp_path / "server.log"
    log.write_text("".join(l + "\n" for l in lines), newline="\n")
    r = run_bash(POST, glue_env(LPM_INF="1", LOG=fwd(log), JD=fwd(tmp_path)), tmp_path)
    assert ("RC=0" if ok else "RC=1") in r.stdout, r.stdout + r.stderr
    kept = (tmp_path / "lpm_inf_markers.txt").read_text().split("\n")
    assert sum(1 for l in kept if l.startswith("[pm-lpminf-hook] pid=") and "-> " in l) == \
        sum(1 for l in lines if re.search(r"pid=\d+ ppid=\d+ \S+ 128 -> \d+", l))


def test_common_calls_the_post_health_check_once_right_after_wait_health():
    lines = (SLURM / "common.sh").read_text().splitlines()
    calls = [i for i, l in enumerate(lines) if "engine_post_health_check" in l]
    assert len(calls) == 1
    assert lines[calls[0] - 1].strip().startswith('wait_health "$BASE_URL$HEALTH_PATH"')
    assert "declare -F engine_post_health_check" in lines[calls[0]] and "die " in lines[calls[0]]
    # a failed hook self-test aborts the job even with STRICT_FLAGS=0
    assert ('check_lpm_inf_hook "$py" || { echo "lpm_inf self-test FAILED: aborting (independent of STRICT_FLAGS)"; return 1; }'
            in (SLURM / "engine_sglang.sh").read_text())


LAUNCH = SOURCE + ('JOB_DIR="$JD"; SERVER_LOG="$JD/server.log"; PORT=1; launch_engine; wait "$SERVER_PID"; echo "EXIT=$?"')


def _launch(engine_file: Path, tmp_path: Path, lpm_inf: str):
    env_dir = tmp_path / "env"
    for f in ("rec_argv", "rec_env"):
        (env_dir / f).unlink(missing_ok=True)
    r = run_bash(LAUNCH, glue_env(ENGINE_FILE=fwd(engine_file), LPM_INF=lpm_inf, POLICY="lpm", MODE="burst",
                                  ENV_SGLANG=fwd(env_dir), JD=fwd(tmp_path), HF_HOME="/hf"), tmp_path)
    assert "EXIT=0" in r.stdout, r.stdout + r.stderr
    logs = [re.sub(r"^\[\d\d:\d\d:\d\d\] ", "", l) for l in r.stdout.splitlines()]
    rec_env = "".join(l for l in (env_dir / "rec_env").read_text().splitlines(True) if not l.startswith(("ENGINE_FILE=", "LPM_INF=")))  # harness inputs
    return (env_dir / "rec_argv").read_text(), rec_env, logs


@needs_bash
def test_lpm_inf_0_launches_the_byte_identical_stock_command(tmp_path):
    stock = tmp_path / "engine_sglang_stock.sh"
    try:
        blob = subprocess.run(["git", "-C", str(REPO), "show", f"{BASE_COMMIT}:slurm/engine_sglang.sh"], capture_output=True,
                              check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"git history with {BASE_COMMIT} not available")
    stock.write_bytes(blob)
    make_fake_env(tmp_path / "env", record=True)
    a_argv, a_env, a_log = _launch(stock, tmp_path, "0")
    b_argv, b_env, b_log = _launch(SLURM / "engine_sglang.sh", tmp_path, "0")
    assert "--schedule-policy\nlpm\n" in a_argv and "-m\nsglang.launch_server\n" in a_argv
    assert b_argv == a_argv and b_env == a_env
    assert [l for l in b_log if not l.startswith("server pid")] == [l for l in a_log if not l.startswith("server pid")]
    # LPM_INF=1: the same argv; the environment differs by exactly the two hook variables
    c_argv, c_env, c_log = _launch(SLURM / "engine_sglang.sh", tmp_path, "1")
    assert c_argv == a_argv
    extra = sorted(set(c_env.splitlines()) - set(a_env.splitlines()))
    missing = sorted(set(a_env.splitlines()) - set(c_env.splitlines()))
    assert missing == [] and [x.split("=", 1)[0] for x in extra] == ["PM_WAITING_QUEUE_PREFIX_MATCH_MAX", "PYTHONPATH"]
    assert f"PM_WAITING_QUEUE_PREFIX_MATCH_MAX={INF}" in extra
    assert any(x.startswith("PYTHONPATH=") and x.rstrip().endswith("slurm/hooks/lpm_inf") for x in extra)
    assert any("lpm_inf: server command prefixed with: env PYTHONPATH=" in l for l in c_log)


@needs_bash
@posix_only
def test_launch_then_post_health_check_end_to_end_on_the_stand_in(tmp_path):
    """launch_engine (LPM_INF=1) -> the hook in the stand-in launch_server and its spawn child -> server.log ->
    engine_post_health_check passes, and the child's marker has pid != SERVER_PID and ppid == SERVER_PID."""
    make_fake_env(tmp_path / "env")
    script = SOURCE + ('JOB_DIR="$JD"; SERVER_LOG="$JD/server.log"; PORT=1; launch_engine; wait "$SERVER_PID"; echo "EXIT=$?"; '
                       'echo "SPID=$SERVER_PID"; engine_post_health_check; echo "RC=$?"')
    r = run_bash(script, glue_env(LPM_INF="1", POLICY="lpm", MODE="burst", ENV_SGLANG=fwd(tmp_path / "env"),
                                  JD=fwd(tmp_path), HF_HOME="/hf"), tmp_path)
    assert "EXIT=0" in r.stdout and "RC=0" in r.stdout, r.stdout + r.stderr
    spid = re.search(r"SPID=(\d+)", r.stdout).group(1)
    log = (tmp_path / "server.log").read_text()
    assert f"child sees {INF}" in log
    child = [m for m in re.findall(r"pid=(\d+) ppid=(\d+) \S+ 128 -> (\d+)", log) if m[0] != spid]
    assert child and all(m[1] == spid and m[2] == INF for m in child)
