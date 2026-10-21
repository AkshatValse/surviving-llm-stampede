"""Result-directory and provenance helpers (new timestamped dir per run, meta.json with git state at START)."""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# env vars worth recording when running under SLURM (values are job metadata, not secrets)
_SLURM_VARS = ("SLURM_JOB_ID", "SLURM_JOB_NAME", "SLURM_JOB_ACCOUNT", "SLURM_JOB_PARTITION", "SLURM_JOB_QOS",
               "SLURM_JOB_NODELIST", "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE", "SLURM_GPUS_ON_NODE",
               "CUDA_VISIBLE_DEVICES", "SGLANG_ENABLE_WAITING_PREFIX_REFRESH", "HF_HOME")


def default_hardware() -> str:
    """Hardware label for meta.json of tools that do not take one from a config. This machine's label unless the job
    script exports AGENTLOAD_HARDWARE (slurm/common.sh does, from nvidia-smi)."""
    return os.environ.get("AGENTLOAD_HARDWARE", "Apple M3 Max CPU (simulation)")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def new_result_dir(root: str | Path, name: str) -> Path:
    """Create ``<root>/<name>/<YYYYmmdd-HHMMSS>[-k]`` (never reuses or overwrites an existing dir)."""
    base = Path(root) / name
    base.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    for k in range(1000):
        d = base / (stamp if k == 0 else f"{stamp}-{k}")
        try:
            d.mkdir(exist_ok=False)
            return d
        except FileExistsError:
            continue
    raise RuntimeError("could not create a fresh result dir")


def _git(args: List[str], cwd: Path) -> str:
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # pragma: no cover
        return ""


def git_info(repo_dir: Path) -> Dict[str, Any]:
    """Commit, dirty flag (tracked changes or untracked non-ignored files) and branch. Call at run START."""
    return {"commit": _git(["rev-parse", "HEAD"], repo_dir),
            "dirty": bool(_git(["status", "--porcelain"], repo_dir)),
            "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir),
            "captured_at": "run start"}


def env_versions() -> Dict[str, str]:
    out = {"python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform()}
    for mod in ("aiohttp", "pandas", "yaml", "scipy"):
        try:
            m = __import__(mod)
            out[mod] = str(getattr(m, "__version__", "?"))
        except Exception:  # pragma: no cover
            out[mod] = "missing"
    return out


def json_default(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def build_meta(*, experiment: str, argv: List[str], seeds: List[int], hardware: str,
               git: Dict[str, Any], t_start: datetime, extra: Optional[Dict[str, Any]] = None,
               t_end: Optional[datetime] = None, status: str = "running") -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "experiment": experiment,
        "status": status,
        "argv": argv,
        "git": git,
        "seeds": seeds,
        "versions": env_versions(),
        "hostname": socket.gethostname(),
        "hardware": hardware,
        "start_time": t_start.isoformat(timespec="seconds"),
        "end_time": t_end.isoformat(timespec="seconds") if t_end else None,
        "wall_s": (t_end - t_start).total_seconds() if t_end else None,
        "slurm_env": {k: os.environ[k] for k in _SLURM_VARS if k in os.environ},
    }
    if extra:
        meta.update(extra)
    return meta


def write_meta(d: Path, meta: Dict[str, Any]) -> None:
    (d / "meta.json").write_text(json.dumps(meta, indent=2, default=json_default))
