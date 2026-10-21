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
                 "--gres=gpu:a100:1", "--cpus-per-task=16", "--mem=128G", "--time=04:00:00",
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
    e.update(env, SLURM_SUBMIT_DIR=str(tmp_path))
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


@pytest.mark.parametrize("mode,port", [("miss", 18091), ("cap", 18092), ("burst", 18093)])
def test_job_glue_runs_locally_against_the_mock_server(mode, port, tmp_path):
    env = dict(os.environ, ENV_GEN=sys.prefix, RESULTS_ROOT=str(tmp_path), PORT=str(port), MULTS="1.0", SEEDS="0",
               POP_CHECK="6" if mode == "miss" else "")
    r = subprocess.run([BASH, str(SLURM / "local_smoke.sh"), mode], capture_output=True, text=True, env=env, timeout=240,
                       cwd=REPO)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]     # a failed run makes the job exit non-zero
    assert "0 failed" in r.stdout
    logs = list((tmp_path / "nova_job_logs").iterdir())
    assert len(logs) == 1
    banner = (logs[0] / "banner.txt").read_text()
    for needle in ("hostname:", "nvidia-smi", "commit:", "SEEDS=\"0\"", "ENGINE=mock", f"MODE={mode}", "research_question"):
        assert needle in banner, needle
    assert "vllm:num_requests_waiting" in (logs[0] / "probe.txt").read_text()
    assert "flush OK" in (logs[0] / "job_events.log").read_text()
    run_dirs = (logs[0] / f"run_dirs_{mode}.txt").read_text().split()
    assert len(run_dirs) == 1 and (Path(run_dirs[0]) / "meta.json").exists()
    meta = json.loads((Path(run_dirs[0]) / "meta.json").read_text())
    assert meta["engine_label"] == "mock-fcfs" and meta["seeds"] == [0] and meta["status"] == "finished"
    assert meta["outcome"]["requests_ok"] > 5
    ana = {"miss": ("agentload_analysis_miss", "calibration.json"), "cap": ("agentload_analysis_stable", "stable_runs.csv"),
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
