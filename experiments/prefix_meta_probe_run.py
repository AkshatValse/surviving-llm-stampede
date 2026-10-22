#!/usr/bin/env python
"""CLI of the probe runner: mu(n) curve / open-loop stability from empty / burst with paired no-burst and client-side-cap arms, with engine and
workload overrides from a YAML spec (batching mode, allocation mode, iteration-cost keys, workload, ...).

    /opt/anaconda3/bin/python experiments/prefix_meta_probe_run.py curve --spec configs/prefix_meta_probe.yaml [--quick] [--workers 3]
    /opt/anaconda3/bin/python experiments/prefix_meta_probe_run.py open  --spec configs/prefix_meta_probe.yaml [--set engine.batching=mixed]
    /opt/anaconda3/bin/python experiments/prefix_meta_probe_run.py burst --spec configs/prefix_meta_probe.yaml

Each call writes a NEW results/prefix_meta_probe_<cmd>[_tag][_quick]/<YYYYmmdd-HHMMSS>/ (spec and base config copies, config_effective.yaml,
meta.json with git commit + dirty flag, seeds, versions; CSVs). At most 6 processes (default 3). Run from the repository root.
See src/prefixmeta/probe.py for the spec format and the definitions.
"""
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from prefixmeta.probe import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(repo_dir=REPO))
