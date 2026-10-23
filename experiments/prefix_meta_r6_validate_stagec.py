#!/usr/bin/env python
"""CLI of the round-6 validation against the real Stage C curve (src/prefixmeta/r6_validate.py, configs/r6_validate_stagec.yaml).

    /opt/anaconda3/bin/python experiments/prefix_meta_r6_validate_stagec.py run --spec configs/r6_validate_stagec.yaml [--quick] [--workers 4]

Writes a NEW results/r6_validate_stagec[_quick]/<YYYYmmdd-HHMMSS>/ (config copies, config_effective.yaml, meta.json with the git commit and dirty
flag captured at the start, seeds, calibration file sha256, versions; runs.csv, cell_table.csv, summary.json, tables.md, real_stagec.csv and the
supplementary files). Run from the repository root. At most 8 processes (default 4).
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.r6_validate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
