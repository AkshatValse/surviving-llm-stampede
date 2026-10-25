"""Build the seeded download list for the mini-SWE-agent v2.0.0 sample (SWE-bench bash-only leaderboard runs).

Input: one S3 listing per run, "key<TAB>size" per line (saved from the public bucket listing, see
notes/lit/AGENT_TRACES.md). Output: "url<TAB>relative_path<TAB>size" lines for scripts/traces/fetch.py files.
The SAME seeded sample of instances is used for every run (paired by instance); instances that are missing in
any run are dropped first.

  python -I scripts/traces/make_sample_list.py LISTING_DIR OUT_LIST --runs RUN [RUN ...] --n 100 --seed 20261024
"""
from __future__ import annotations

import argparse
import os
import random

BASE = "https://swe-bench-submissions.s3.amazonaws.com/"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("listing_dir")
    ap.add_argument("out")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261024)
    a = ap.parse_args()

    per_run: dict[str, dict[str, tuple[str, int]]] = {}
    for run in a.runs:
        d: dict[str, tuple[str, int]] = {}
        with open(os.path.join(a.listing_dir, run + ".tsv"), encoding="utf-8") as f:
            for line in f:
                key, size = line.rstrip("\n").split("\t")
                if not key.endswith(".traj.json"):
                    continue
                inst = key.rsplit("/", 1)[1][: -len(".traj.json")]
                d[inst] = (key, int(size))
        per_run[run] = d
    common = sorted(set.intersection(*[set(d) for d in per_run.values()]))
    rng = random.Random(a.seed)
    pick = sorted(rng.sample(common, min(a.n, len(common))))
    tot = 0
    with open(a.out, "w", encoding="utf-8", newline="\n") as g:
        for run in a.runs:
            for inst in pick:
                key, size = per_run[run][inst]
                g.write(f"{BASE}{key}\t{run}/{inst}.traj.json\t{size}\n")
                tot += size
    print(f"common instances {len(common)}, sampled {len(pick)} x {len(a.runs)} runs, {tot / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
