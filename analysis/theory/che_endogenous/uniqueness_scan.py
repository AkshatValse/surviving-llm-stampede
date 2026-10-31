"""Scan of the number of fixed points of Phi_n (closed system) across cells, headroom eta and tool-time law.

    PYTHONPATH="src;." python -m analysis.theory.che_endogenous.uniqueness_scan  -> results/theory/che_endogenous/uniqueness_scan.json
"""
import json
import math
import os
from dataclasses import replace

import numpy as np

from .model import CheModel, Workload, calibrate_scale, default_cells


def main(out="results/theory/che_endogenous/uniqueness_scan.json"):
    cells = default_cells()
    cv, _ = calibrate_scale(replace(cells["vllm_300k"], eta=0.10), 10348.97)
    todo = (("a100_300k", replace(cells["a100_300k"], eta=0.10), np.arange(16, 40, 0.5)),
            ("a100_native", replace(cells["a100_native"], eta=0.10), np.arange(60, 104, 1.0)),
            ("vllm_300k", cv, np.arange(16, 40, 0.5)))
    rows = []
    for nm, c, ns in todo:
        for eta in (0.03, 0.10, 0.25):
            for shape in (1.0, 4.0, 16.0, math.inf):
                m = CheModel(replace(c, eta=eta, wl=Workload(z_shape=shape)))
                mx, smax = 0, -math.inf
                for n in ns:
                    fps = m.fixed_points(float(n), grid=121)
                    mx = max(mx, len(fps))
                    for r in fps:
                        if np.isfinite(r["slope"]):
                            smax = max(smax, r["slope"])
                rows.append(dict(cell=nm, eta=eta, gamma_shape=("inf" if math.isinf(shape) else shape), n_min=float(ns[0]),
                                 n_max=float(ns[-1]), n_step=float(ns[1] - ns[0]), max_fixed_points=mx, max_slope_at_fixed_point=smax))
                print(rows[-1], flush=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
