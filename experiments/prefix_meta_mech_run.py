#!/usr/bin/env python
"""CLI for round 2 of the prefix-cache metastability pilot (mechanisms, phase diagram, escape scaling, robustness).

    /opt/anaconda3/bin/python experiments/prefix_meta_mech_run.py phase  [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_mech_run.py mech   [--quick] [--only fcfs peek ...]
    /opt/anaconda3/bin/python experiments/prefix_meta_mech_run.py escape [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_mech_run.py robust [--quick]
    /opt/anaconda3/bin/python experiments/prefix_meta_mech_run.py evaluate --phase-dir D --mech-dir D --escape-dir D --robust-dir D

Config: configs/prefix_meta_mech.yaml (merged over configs/prefix_meta.yaml). Predictions P1-P8 are pre-registered in
configs/prefix_meta_mech_prereg.yaml (committed before any round-2 run). Never more than 3 worker processes.
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.mech_runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
