#!/usr/bin/env python
"""CLI of the round-7 robustness stages (tool-time sweep, burst-size sweep, horizon, low-lambda fragility); see src/prefixmeta/r7_robustness.py.

    python experiments/r7_robustness_run.py {lambda_miss,curves,edge,pairs,burst_sizes,horizon,lowlam} --spec configs/r7_robustness.yaml [--workers 6]

Each call writes a NEW results/r7_<stage>/<timestamp>/ and appends it to results/r7_robustness/manifest.tsv. At most 6 processes. Run from the repository root.
The whole set is experiments/r7_robustness_run.sh; the tables and the notes file come from `python -m prefixmeta.r7_report`.
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.r7_robustness import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
