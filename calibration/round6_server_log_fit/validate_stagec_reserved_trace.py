#!/usr/bin/env python
"""Diagnostic for VALIDATION.md: how does the KV reserved by running requests (full_reserve) evolve in mixed vs separate batching?

Re-runs ONE closed-population cell per (n, batching) of configs/r6_validate_stagec.yaml (primary arm, FCFS, one seed) and samples
(time, iteration length, reserved KV, decode-batch size) after every prefill / decode iteration call in the measured window [warmup, horizon).
Prints time-weighted statistics. It only instruments the engine (wraps two methods); the dynamics are the engine's own.

    /opt/anaconda3/bin/python calibration/round6_server_log_fit/validate_stagec_reserved_trace.py [--seed 0] [--n 48 300] [--out FILE]

Note: a decode call may be a closed-form run of several iterations (batch_decode_iterations); the weights are call durations.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from prefixmeta import r6_validate as rv  # noqa: E402
from prefixmeta.r4_runner import closed_spec  # noqa: E402
from prefixmeta.sim import build_engine, deep_update  # noqa: E402


def trace_cell(cfg: dict, n: int, batching: str, seed: int) -> dict:
    pr = cfg["validate"]["protocol"]
    eng_cfg = deep_update(cfg["engine"], {"batching": batching})
    cfg2 = {**cfg, "engine": eng_cfg}
    rs = closed_spec("fcfs_lru", n, 1.0, seed, {"horizon_s": pr["horizon_s"], "pool_sessions_per_k": pr["pool_sessions"]}, eng_cfg)
    eng, _rec, _cap = build_engine(cfg2, rs)
    samples = []
    orig_p, orig_d = eng._iterate_with_prefill, eng._iterate_decode

    def wp(*a, **k):
        t0 = eng.now
        orig_p(*a, **k)
        samples.append((eng.now, eng.now - t0, eng.reserved, eng.n_D, "P"))

    def wd(*a, **k):
        t0 = eng.now
        orig_d(*a, **k)
        samples.append((eng.now, eng.now - t0, eng.reserved, eng.n_D, "D"))

    eng._iterate_with_prefill, eng._iterate_decode = wp, wd
    eng.run(pr["horizon_s"])
    s = [x for x in samples if x[0] >= pr["warmup_s"]]
    t = np.array([x[1] for x in s])
    res = np.array([x[2] for x in s], dtype=float)
    nD = np.array([x[3] for x in s], dtype=float)
    kind = np.array([x[4] for x in s])
    w = t / t.sum()
    d = kind == "D"
    return {"n": n, "batching": batching, "seed": seed, "reserved_mean": float(np.sum(w * res)), "reserved_min": float(res.min()),
            "reserved_max": float(res.max()), "frac_time_reserved_below_100k": float(np.sum(w[res < 100000])),
            "frac_time_in_prefill_calls": float(np.sum(w[kind == "P"])),
            "mean_decode_batch_over_decode_time": float(np.sum(w[d] * nD[d]) / max(np.sum(w[d]), 1e-12)),
            "n_prefill_calls": int((kind == "P").sum()), "n_decode_calls": int(d.sum())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="configs/r6_validate_stagec.yaml")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, nargs="+", default=[48, 300])
    ap.add_argument("--out", default=None, help="also write the lines to this NEW file (refuses to overwrite)")
    args = ap.parse_args()
    cfg = rv.load_validation_config(str(REPO / args.spec), REPO)
    lines = [f"# reserved-KV trace, primary arm (calibration.yaml unchanged, full_reserve), FCFS, seed {args.seed}, window [900, 2700) s"]
    for n in args.n:
        for b in (rv.MIXED, rv.SEP):
            r = trace_cell(cfg, n, b, args.seed)
            lines.append(f"n={r['n']} {r['batching']}: reserved mean {r['reserved_mean']:.0f} min {r['reserved_min']:.0f} max {r['reserved_max']:.0f}; "
                         f"time share with reserved<100k {r['frac_time_reserved_below_100k']:.2f}; time share in prefill calls "
                         f"{r['frac_time_in_prefill_calls']:.2f}; mean decode batch (time-weighted over decode calls) "
                         f"{r['mean_decode_batch_over_decode_time']:.1f}; calls P/D {r['n_prefill_calls']}/{r['n_decode_calls']}")
    text = "\n".join(lines)
    print(text)
    if args.out:
        out = Path(args.out)
        with open(out, "x") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
