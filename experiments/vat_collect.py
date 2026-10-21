"""Timing collection. Orchestrator launches one fresh subprocess per process index.

Usage: python experiments/vat_collect.py [--config configs/vat_pilot.yaml] [--quick]
       [--estimate-only] [--force]
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def apply_quick(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    q = cfg["collect"]["quick"]
    cfg["kernel"].update(N=q["N"], iters=q["iters"], tiles=q["tiles"])
    cfg["collect"].update(R=q["R"], P=q["P"])
    return cfg


def worker(cfg: dict, proc: int, out: str, calib: bool) -> None:
    from vat.kernels import build_candidates
    from vat.measure import collect_process, process_seeds
    k, c = cfg["kernel"], cfg["collect"]
    cands = build_candidates(k)
    t0 = time.time()
    ss = process_seeds(cfg["seeds"]["collect"], c["P"])[proc]
    R = c["calib_blocks"] if calib else c["R"]
    df = collect_process(cands, k["N"], k["iters"], R, proc, ss, progress=not calib)
    if calib:
        blk_s = float((df["baseline_ns"] + df["candidate_ns"]).mean() / 1e9)
        json.dump({"block_s": blk_s, "wall_s": time.time() - t0, "K": len(cands) - 1}, open(out, "w"))
    else:
        df.to_parquet(out)


def spawn(cfg_path: Path, proc: int, out: Path, calib: bool) -> None:
    cmd = [sys.executable, __file__, "--worker", "--config", str(cfg_path), "--proc", str(proc),
           "--out", str(out)] + (["--calib"] if calib else [])
    subprocess.run(cmd, check=True, env=os.environ.copy())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs/vat_pilot.yaml"))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="run even if estimate exceeds limit")
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--calib", action="store_true")
    ap.add_argument("--proc", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    os.environ["NUMBA_NUM_THREADS"] = str(cfg["collect"]["numba_threads"])
    if a.quick and not a.worker:
        cfg = apply_quick(cfg)
    if a.worker:
        return worker(cfg, a.proc, a.out, a.calib)

    from vat.provenance import new_run_dir, write_meta
    start = dt.datetime.now().isoformat()
    run_dir = new_run_dir(ROOT / cfg["output_root"], "vat_collect_quick" if a.quick else "vat_collect")
    cfg_path = run_dir / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    c = cfg["collect"]

    cal = run_dir / "calib.json"
    spawn(cfg_path, 0, cal, True)
    cj = json.load(open(cal))
    K = cj["K"]
    est_min = (cj["block_s"] * K * c["R"] * c["P"] + cj["wall_s"] * c["P"]) / 60
    print(f"[estimate] K={K} block={cj['block_s']*1e3:.1f} ms; calib wall {cj['wall_s']:.1f} s "
          f"(incl. JIT); full run ~ {est_min:.1f} min (limit {c['max_estimated_minutes']})", flush=True)
    if a.estimate_only or (est_min > c["max_estimated_minutes"] and not a.force):
        print("stopping (estimate-only or over limit); scale down N/iters/R/P in the config")
        return

    for p in range(c["P"]):
        t = time.time()
        spawn(cfg_path, p, run_dir / f"proc_{p}.parquet", False)
        print(f"proc {p} done in {time.time()-t:.0f}s", flush=True)
    import pandas as pd
    df = pd.concat([pd.read_parquet(run_dir / f"proc_{p}.parquet") for p in range(c["P"])],
                   ignore_index=True)
    df.to_parquet(run_dir / "timings.parquet")
    write_meta(run_dir, cfg, start, dt.datetime.now().isoformat(),
               {"estimate_min": est_min, "calibration": cj, "n_rows": len(df), "quick": a.quick})
    print("wrote", run_dir)


if __name__ == "__main__":
    main()
