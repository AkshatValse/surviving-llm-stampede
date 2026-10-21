"""Run the delay-EoS grid: Adam / Muon-like x {sync, delay, ef} x batch x eta x seed on a tanh MLP (CPU).

Usage (repo root):
  /opt/anaconda3/bin/python experiments/delay_eos_run.py [--config configs/delay_eos.yaml] [--batches 1000 64]
                                                         [--out-root results/delay_eos] [--processes 3]
Outputs go to <out-root>/<YYYYmmdd-HHMMSS>/ (never overwritten): config.yaml, meta.json, runs_summary.csv,
curvature.csv, loss_curve.csv.
"""
import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"  # one BLAS thread per worker process (shared machine, <= 3 processes)

import argparse  # noqa: E402
import copy  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delayeos.mlp import load_digits_subset  # noqa: E402
from delayeos.train import RUN_KEYS, expand_grid, run_one  # noqa: E402

_G: dict = {}


def _init_worker(cfg: dict) -> None:
    X, Y = load_digits_subset(cfg["data"]["n"], cfg["data"]["standardize"])
    _G.update(cfg=cfg, X=X, Y=Y)


def _work(item: tuple[int, dict]) -> tuple[int, dict]:
    idx, run = item
    t0 = time.time()
    out = run_one(run, _G["cfg"], _G["X"], _G["Y"])
    out["wall_s"] = time.time() - t0
    out.pop("theta", None)
    return idx, out


def git_info(repo: Path) -> dict:
    def sh(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()

    return {"commit": sh("rev-parse", "HEAD"), "branch": sh("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(sh("status", "--porcelain"))}


def versions() -> dict:
    import scipy
    import sklearn
    return {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "pandas": pd.__version__, "sklearn": sklearn.__version__, "yaml": yaml.__version__,
            "platform": platform.platform()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "delay_eos.yaml"))
    ap.add_argument("--out-root", default=None, help="default: output.root from the config (relative to repo root)")
    ap.add_argument("--batches", type=int, nargs="*", default=None, help="subset of config batches to run")
    ap.add_argument("--steps", type=int, default=None, help="override steps (smoke tests only)")
    ap.add_argument("--processes", type=int, default=None)
    ap.add_argument("--max-runs", type=int, default=None, help="truncate the run list (smoke tests only)")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    eff = copy.deepcopy(cfg)
    if args.batches:
        eff["batches"] = args.batches
    if args.steps:
        eff["steps"] = args.steps
    procs = min(args.processes or eff["parallel"]["processes"], 3)  # hard cap: shared machine
    runs = expand_grid(eff)
    if args.max_runs:
        runs = runs[:args.max_runs]

    out_root = Path(args.out_root) if args.out_root else ROOT / eff["output"]["root"]
    out_dir = out_root / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=False)  # never overwrite
    shutil.copy(args.config, out_dir / "config.yaml")
    if eff != cfg:
        with open(out_dir / "config_effective.yaml", "w") as f:
            yaml.safe_dump(eff, f, sort_keys=False)

    meta = {"experiment": eff["experiment"], "research_question": " ".join(str(eff["research_question"]).split()),
            "git": git_info(ROOT), "seeds": eff["seeds"], "versions": versions(), "hostname": socket.gethostname(),
            "hardware": eff["hardware"], "start_time": datetime.now().isoformat(timespec="seconds"),
            "command": " ".join(sys.argv), "n_runs_planned": len(runs), "processes": procs,
            "batches_run": sorted({r["batch"] for r in runs}, reverse=True)}
    print(f"[{meta['start_time']}] {len(runs)} runs, {procs} processes -> {out_dir}", flush=True)

    results: dict[int, dict] = {}
    t0 = time.time()
    try:
        ctx = mp.get_context("spawn")
        with ctx.Pool(procs, initializer=_init_worker, initargs=(eff,)) as pool:
            for k, (idx, out) in enumerate(pool.imap_unordered(_work, list(enumerate(runs)), chunksize=1), 1):
                results[idx] = out
                if k % 8 == 0 or k == len(runs):
                    print(f"  {k}/{len(runs)} done, {time.time() - t0:.0f}s elapsed", flush=True)
    finally:
        done = sorted(results)
        summ = pd.DataFrame([{**results[i]["summary"], "wall_s": results[i]["wall_s"]} for i in done])
        curv_rows, loss_rows = [], []
        every = int(eff["output"]["loss_log_every"])
        for i in done:
            key = {k: runs[i][k] for k in RUN_KEYS}
            curv_rows += [{**key, **r} for r in results[i]["curv"]]
            ls = results[i]["loss"]
            loss_rows.append(pd.DataFrame({**{k: [v] * len(ls[::every]) for k, v in key.items()},
                                           "step": np.arange(len(ls))[::every], "loss": ls[::every]}))
        summ.to_csv(out_dir / "runs_summary.csv", index=False)
        pd.DataFrame(curv_rows).to_csv(out_dir / "curvature.csv", index=False)
        if loss_rows:
            pd.concat(loss_rows).to_csv(out_dir / "loss_curve.csv", index=False)
        meta.update(end_time=datetime.now().isoformat(timespec="seconds"), wall_s=time.time() - t0,
                    n_runs_completed=len(done))
        with open(out_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)
    print(f"finished {len(done)}/{len(runs)} runs in {time.time() - t0:.0f}s -> {out_dir}", flush=True)


if __name__ == "__main__":
    main()
