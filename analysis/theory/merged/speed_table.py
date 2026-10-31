"""Speed-conditional predictions for a cell whose E0a is not yet known (the Llama-3.1-8B cell).

    PYTHONPATH="src;." python -m analysis.theory.merged.speed_table analysis/theory/cells/llama31_8b_300k.yaml [--out FILE]

For a uniform speed factor s applied on top of the spec's costs (every iteration cost divided by s), the table gives the
model's E0a analogue (closed POP 32, cache off: tokens/s and lambda_miss in turns), the closed curve (fluid and F1-annealed
mu_max, peak n, 0.5-hit crossing, n_b and its two parts) and the F2 from-empty edge in ABSOLUTE units (sessions/s).

Use (frozen rule, notes/PREDICTIONS_r13_theory.md): once the cell's E0a is measured, s = T_meas / T_model(1), where T_model(1)
is the s = 1 row's E0a token rate (the model's all-miss token rate is exactly proportional to s), and every prediction is read
off the table by linear interpolation in s; windows and edges are then expressed in multiples of the MEASURED lambda_miss.
Quantities in sessions (M / E_S, the cliff's pool part) do not depend on s; n_b depends on s only through nu_b zbar'.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List, Optional

import numpy as np

from ..fluid_rigorous.edge import predicted_edge
from ..fluid_rigorous.model import Model, annealed_curve, curve_on_grid, kv_dispersion, summarize_curve
from . import extras as X
from .spec import ROOT, build, load_spec

S_GRID = [0.70, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.50]


def row(m0: Model, s: float, n_theta: int = 21) -> dict:
    m = Model(m0.wl, m0.cost.scaled(s), m0.M)
    cs = summarize_curve(m)
    e32 = m.all_miss_closed(32)
    thr = X.threshold_closed_form(m)
    ng = np.arange(2.0, cs.n_b * 1.3, 0.5)
    ann = annealed_curve(m.wl, m.cost, m.M, ng, n_theta=n_theta)
    ia = int(np.argmax(ann["mu"]))
    pk = min(cs.pts, key=lambda p: abs(p["mu"] - cs.mu_max))
    I_D = kv_dispersion(m.wl, pk["S_bar"])["I_D"]
    mu_fn, _, _, _, _ = X.curve_fn(cs)
    ed = predicted_edge(mu_fn, e32["mu"], [1.0], I_D, cs.n_b, 3000.0, cs.mu_max)
    return dict(s=s, e0a_tokens_per_s=e32["tok"], lambda_miss_turns_model=e32["mu"], mu_b=cs.mu_b,
                mu_max_fluid=cs.mu_max, peak_n_fluid=cs.n_star, n_half_fluid=cs.n_half, n_b=cs.n_b,
                n_b_tool_call_part=thr["tool_call_part"], n_b_pool_part=thr["pool_part"],
                mu_max_annealed=float(ann["mu"][ia]), peak_n_annealed=float(ng[ia]),
                window_fluid_vs_model_lambda=cs.mu_max / e32["mu"], window_annealed_vs_model_lambda=float(ann["mu"][ia]) / e32["mu"],
                f2_edge_lambda_sessions_per_s=ed["edge_lam"], f2_edge_vs_model_lambda=ed["edge_mult"])


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    spec = load_spec(a.spec)
    m0, _, info = build(spec)
    rows = [row(m0, s) for s in S_GRID]
    out = dict(spec_name=spec["name"], s_grid=S_GRID, rows=rows, info=info,
               rule="s = T_meas / rows[s=1].e0a_tokens_per_s; interpolate every column linearly in s; express windows and "
                    "edges in multiples of the measured lambda_miss")
    path = a.out or os.path.join(ROOT, "results", "theory", "merged", f"{spec['name']}_speed_table.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    for r in rows:
        print(f"s={r['s']:.2f} tok {r['e0a_tokens_per_s']:.0f} lam {r['lambda_miss_turns_model']:.4f} mu_max {r['mu_max_fluid']:.4f}"
              f"/{r['mu_max_annealed']:.4f} peak {r['peak_n_fluid']:.1f} n_half {r['n_half_fluid']:.1f} n_b {r['n_b']:.2f} "
              f"(pool part {r['n_b_pool_part']:.2f}) edge {r['f2_edge_lambda_sessions_per_s']:.4f}/s")


if __name__ == "__main__":
    main()
