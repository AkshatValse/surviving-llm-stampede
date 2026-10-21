"""Paired, interleaved, randomized timing collection."""
from __future__ import annotations

import time
from typing import List

import numpy as np
import pandas as pd

from .kernels import Candidate, make_grid, warmup


def process_seeds(master: int, P: int) -> List[np.random.SeedSequence]:
    return np.random.SeedSequence(master).spawn(P)


def time_call(f, a, b) -> int:
    t0 = time.perf_counter_ns()
    f(a, b)
    return time.perf_counter_ns() - t0


def collect_process(cands: List[Candidate], n: int, iters: int, R: int, proc: int,
                    ss: np.random.SeedSequence, progress: bool = False) -> pd.DataFrame:
    """One process worth of blocks. A block = baseline + one candidate back-to-back
    in rng-chosen order; blocks are visited in random round-robin rounds
    (each round visits every candidate once, in random order)."""
    rng = np.random.Generator(np.random.PCG64(ss))
    warmup(cands, n, iters)
    fns = [c.make(iters) for c in cands]
    a = make_grid(n, 0)
    b = a.copy()
    for f in fns:                      # warm each at the real size (page-in, threads)
        f(a, b)
    K = len(cands) - 1
    rows = np.empty((R * K, 7), dtype=np.int64)
    k = 0
    for blk in range(R):
        for cid in rng.permutation(K) + 1:
            cand_first = int(rng.integers(2))
            t_start = time.perf_counter_ns()
            if cand_first:
                tc = time_call(fns[cid], a, b)
                tb = time_call(fns[0], a, b)
            else:
                tb = time_call(fns[0], a, b)
                tc = time_call(fns[cid], a, b)
            rows[k] = (proc, blk, cid, cand_first, tb, tc, t_start)
            k += 1
        if progress and blk % 10 == 0:
            print(f"  proc {proc} block {blk}/{R}", flush=True)
    return pd.DataFrame(rows, columns=["proc", "block", "cand", "cand_first",
                                       "baseline_ns", "candidate_ns", "t_ns"])
