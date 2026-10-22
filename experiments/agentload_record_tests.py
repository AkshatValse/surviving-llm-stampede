"""Run the agentload / analysis test-suite and record the outcome in a new timestamped results dir
(junit XML + stdout + meta.json with git state captured BEFORE the run). Usage:
    /opt/anaconda3/bin/python experiments/agentload_record_tests.py [pytest args...]
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta  # noqa: E402


def main(argv: list[str]) -> int:
    git = git_info(REPO)                                   # at START
    t0 = datetime.now()
    out = new_result_dir(REPO / "results", "agentload_tests")
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", f"--junitxml={out / 'junit.xml'}", "-v", *argv]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    (out / "pytest_stdout.txt").write_text(r.stdout + r.stderr)
    write_meta(out, build_meta(experiment="agentload_tests", argv=cmd, seeds=[], hardware=default_hardware(),
                               git=git, t_start=t0, t_end=datetime.now(),
                               extra={"returncode": r.returncode, "summary_line": r.stdout.strip().splitlines()[-1]},
                               status="finished"))
    print(r.stdout.strip().splitlines()[-1])
    print("result dir:", out)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
