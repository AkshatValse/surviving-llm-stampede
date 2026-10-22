#!/usr/bin/env python
"""CLI for the prefix-cache metastability pilot.

    /opt/anaconda3/bin/python experiments/prefix_meta_run.py e0
    /opt/anaconda3/bin/python experiments/prefix_meta_run.py e1 [--quick] [--calib results/prefix_meta_e0/<ts>]
    subcommands: e0 e1 e2 e3 e4 ablation decision
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
