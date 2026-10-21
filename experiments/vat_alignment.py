"""Mechanism check for the VAT pilot: does grid placement (alignment offset) explain
the between-process variance of paired log-speedups?

Usage: python experiments/vat_alignment.py configs/vat_alignment.yaml
       (internal) python experiments/vat_alignment.py <config> --worker <proc_idx> <outdir>
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def placed_grid(src: np.ndarray, offset: int, pad: int = 4096) -> np.ndarray:
    """Copy `src` into a page-aligned buffer starting `offset` float64 elements in."""
    n = src.size
    raw = np.empty(n + pad + 4096 // 8, dtype=np.float64)
    base = (-raw.ctypes.data % 4096) // 8  # elements to the next 4 KiB boundary
    view = raw[base + offset: base + offset + n].reshape(src.shape)
    view[...] = src
    return view


def worker(cfg: dict, proc: int, outdir: Path) -> None:
    os.environ.setdefault("NUMBA_NUM_THREADS", str(cfg["numba_threads"]))
    from vat.kernels import build_candidates, make_grid, warmup, numpy_baseline

    kcfg = {"orders": ["row", "col"], "tiles": [0, 16, 32, 64, 128, 256],
            "parallel": [False, True], "fastmath": [False, True]}
    allc = {c.name: c for c in build_candidates(kcfg)}
    cands = [allc[n] for n in cfg["candidates"]]
    ss = np.random.SeedSequence(cfg["seed"]).spawn(cfg["processes"])[proc]
    rng = np.random.default_rng(ss)
    n, iters = cfg["N"], cfg["iters"]
    warmup(cands, 64, iters)
    g0 = make_grid(n, 0)
    cells = [(c.name, oa, ob) for c in cands for oa in cfg["offsets_a"] for ob in cfg["offsets_b"]]
    order = [cell for cell in cells for _ in range(cfg["reps_per_cell"])]
    rng.shuffle(order)
    fns = {c.name: c.make(iters) for c in cands}
    rows = []
    for name, oa, ob in order:
        a = placed_grid(g0, oa); b = placed_grid(g0, ob)
        cand_first = bool(rng.integers(2))
        def run_base():
            a2 = placed_grid(g0, oa); b2 = placed_grid(g0, ob)
            t0 = time.perf_counter_ns(); numpy_baseline(a2, b2, iters); return time.perf_counter_ns() - t0
        def run_cand():
            t0 = time.perf_counter_ns(); fns[name](a, b); return time.perf_counter_ns() - t0
        if cand_first:
            tc = run_cand(); tb = run_base()
        else:
            tb = run_base(); tc = run_cand()
        rows.append(dict(proc=proc, cand=name, off_a=oa, off_b=ob, cand_first=cand_first,
                         baseline_ns=tb, candidate_ns=tc, t_ns=time.monotonic_ns()))
    pd.DataFrame(rows).to_parquet(outdir / f"proc_{proc}.parquet")


def main() -> None:
    cfg_path = Path(sys.argv[1])
    cfg = yaml.safe_load(cfg_path.read_text())
    if len(sys.argv) > 2 and sys.argv[2] == "--worker":
        worker(cfg, int(sys.argv[3]), Path(sys.argv[4]))
        return
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = ROOT / cfg["output_root"] / "vat_alignment" / ts
    outdir.mkdir(parents=True, exist_ok=False)
    (outdir / "config.yaml").write_text(cfg_path.read_text())
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    import numba
    meta = dict(git_commit=git, git_dirty=dirty, seed=cfg["seed"], hostname=socket.gethostname(),
                hardware=cfg["hardware"], python=sys.version, platform=platform.platform(),
                numpy=np.__version__, numba=numba.__version__, pandas=pd.__version__,
                numba_num_threads=cfg["numba_threads"], start=datetime.now().isoformat(),
                note="machine shared with other processes during timing")
    env = dict(os.environ, NUMBA_NUM_THREADS=str(cfg["numba_threads"]))
    for p in range(cfg["processes"]):
        subprocess.run([sys.executable, __file__, str(cfg_path), "--worker", str(p), str(outdir)],
                       check=True, env=env)
    meta["end"] = datetime.now().isoformat()
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2))
    d = pd.concat([pd.read_parquet(f) for f in sorted(outdir.glob("proc_*.parquet"))])
    d.to_parquet(outdir / "timings.parquet")
    print(outdir)


if __name__ == "__main__":
    main()
