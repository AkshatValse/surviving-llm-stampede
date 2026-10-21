#!/usr/bin/env python
"""CLI for round 5 of the prefix-cache metastability pilot (allocation-mode robustness: ONDEMAND_PREEMPT, RATIO_RESERVE).

    /opt/anaconda3/bin/python experiments/prefix_meta_r5_run.py calib [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r5_run.py curve [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r5_run.py burst --calib-dir D [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_r5_run.py cap   --calib-dir D --curve-dir D [--quick]

Config: configs/prefix_meta_r5.yaml (merged over configs/prefix_meta.yaml). Predictions S1-S4, the registered grid / seeds / horizons
and the exact decision readings are in configs/prefix_meta_r5_prereg.yaml (committed before any round-5 code).
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

from prefixmeta.r5_runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
