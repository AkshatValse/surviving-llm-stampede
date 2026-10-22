#!/usr/bin/env python
"""CLI for round 4 of the prefix-cache metastability pilot (thrashing curve / fluid picture / eviction rules).

    /opt/anaconda3/bin/python experiments/prefix_meta_r4_run.py curve [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r4_run.py burst [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r4_run.py cap   [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r4_run.py report --curve-dir D --burst-dir D --cap-dir D

Config: configs/prefix_meta_r4.yaml (merged over configs/prefix_meta.yaml). Predictions R1-R6, the registered grid / seeds /
horizons and the exact decision readings are in configs/prefix_meta_r4_prereg.yaml (committed before any round-4 code).
Never more than 3 worker processes. Run from the repository root.
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.r4_runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
