"""Run the KV-retention simulation sweep (or a calibration of arrival rates).

Usage (from repo root):
  /opt/anaconda3/bin/python experiments/kvrent_run.py --calibrate
  /opt/anaconda3/bin/python experiments/kvrent_run.py [--workers 1] [--horizon 7200]
"""
from __future__ import annotations

import argparse
import copy
import json
import platform
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from kvrent.metrics import summarize  # noqa: E402
from kvrent.policies import ETA_FREE  # noqa: E402
from kvrent.runner import run_one  # noqa: E402
from kvrent.workload import generate_workload, load_config  # noqa: E402


def git_info() -> dict:
    def g(*a: str) -> str:
        try:
            return subprocess.check_output(["git", *a], cwd=ROOT, text=True).strip()
        except Exception:
            return "unknown"
    return dict(commit=g("rev-parse", "HEAD"), branch=g("rev-parse", "--abbrev-ref", "HEAD"),
                dirty=bool(g("status", "--porcelain")))


def _task(args: tuple) -> list[dict]:
    cfg, mix, lam, seed, policies, etas = args
    progs = generate_workload(cfg, lam, mix, seed)
    rows = []
    for pol in policies:
        for eta in ([None] if pol in ETA_FREE else etas):
            rows.append(run_one(cfg, lam, mix, pol, eta, seed, progs)[1])
    return rows


def run_tasks(cfg: dict, mixes, lams, seeds, policies, etas, workers: int) -> pd.DataFrame:
    tasks = [(cfg, m, l, s, policies, etas) for m in mixes for l in lams for s in seeds]
    if workers > 1:
        with Pool(workers) as p:
            out = p.map(_task, tasks, chunksize=1)
    else:
        out = [_task(t) for t in tasks]
    df = pd.DataFrame([r for rows in out for r in rows])
    return df.sort_values(["mix", "lam", "policy", "eta", "seed"], na_position="first",
                          kind="stable").reset_index(drop=True)


def write_meta(outdir: Path, cfg: dict, seeds, t0: float, t1: float, extra: dict) -> None:
    meta = dict(
        git=git_info(), seeds=list(seeds), hostname=socket.gethostname(),
        hardware=cfg["experiment"]["hardware"],
        python=sys.version, platform=platform.platform(),
        packages=dict(numpy=np.__version__, scipy=scipy.__version__, pandas=pd.__version__,
                      pyyaml=yaml.__version__),
        start_time=datetime.fromtimestamp(t0).isoformat(),
        end_time=datetime.fromtimestamp(t1).isoformat(),
        wall_seconds=t1 - t0, **extra)
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2))


def make_outdir(cfg: dict, prefix: str = "") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / cfg["experiment"]["output_dir"] / f"{prefix}{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    return out


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs/kvrent_pilot.yaml"))
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--horizon", type=float, default=None, help="override sim.horizon_s")
    ap.add_argument("--outdir", default=None, help="explicit output dir (tests)")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args(argv)
    assert a.workers <= 2, "pilot limit: at most 2 workers"
    cfg = load_config(a.config)
    if a.horizon is not None:
        cfg["sim"]["horizon_s"] = a.horizon
    ex = cfg["experiment"]
    t0 = time.time()
    if a.outdir:
        out = Path(a.outdir)
        out.mkdir(parents=True, exist_ok=True)
    else:
        out = make_outdir(cfg, "calibration-" if a.calibrate else "")
    shutil.copy(a.config, out / "config_original.yaml")
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    if a.calibrate:
        df = run_tasks(cfg, ["default", "heavy"], ex["calibration_rates"], [0],
                       ["ALWAYS_HOLD"], [], a.workers)
        df[["mix", "lam", "util_mean", "mean_lat", "p95", "n_inflight", "n_forced"]].to_csv(
            out / "calibration.csv", index=False)
        write_meta(out, cfg, [0], t0, time.time(), dict(mode="calibration"))
        print(df[["mix", "lam", "util_mean", "mean_lat", "n_inflight", "n_forced"]])
        return out

    raw = run_tasks(cfg, ex["mixes"], ex["arrival_rates"], ex["seeds"], ex["policies"],
                    cfg["policy"]["etas"], a.workers)
    raw.to_csv(out / "results.csv", index=False)
    summ = summarize(raw, cfg["policy"]["etas"])
    summ.to_csv(out / "summary.csv", index=False)
    write_meta(out, cfg, ex["seeds"], t0, time.time(), dict(mode="sweep", n_runs=len(raw)))
    if not a.no_plots:
        from figures.kvrent_plots import make_plots
        make_plots(summ, cfg, out)
    print("wrote", out)
    return out


if __name__ == "__main__":
    main()
