"""Run directories and meta.json provenance."""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def git_info() -> dict:
    def run(*a):
        return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(run("status", "--porcelain"))}


def new_run_dir(root: str | Path, name: str) -> Path:
    """results/<name>/<YYYYmmdd-HHMMSS>; refuses to reuse an existing directory."""
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    d = Path(root) / name / ts
    d.mkdir(parents=True, exist_ok=False)
    return d


def write_meta(run_dir: Path, cfg: dict, start: str, end: str, extra: dict | None = None) -> None:
    import numba, numpy, pandas, scipy
    meta = {
        "git": git_info(), "seeds": cfg["seeds"], "hostname": socket.gethostname(),
        "hardware": cfg["hardware"], "platform": platform.platform(),
        "python": sys.version, "versions": {"numpy": numpy.__version__, "scipy": scipy.__version__,
                                            "numba": numba.__version__, "pandas": pandas.__version__},
        "NUMBA_NUM_THREADS": os.environ.get("NUMBA_NUM_THREADS"),
        "start_time": start, "end_time": end,
        "note": "Machine shared with other processes during timing (confound).",
    }
    if extra:
        meta.update(extra)
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
