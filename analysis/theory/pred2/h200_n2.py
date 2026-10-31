"""N2 (remedy rank 4): the H200 300k curve at the cliff-bracket points n = 36, 44, 52 (one Stage C job, the cell's 900 s
warm-up + 1800 s window), under the frozen primary spec h200_300k and its four frozen cost variants, and the registered
rule "T3(c) supported iff hit(36) >= 0.5 and hit(44) < 0.5".

    PYTHONPATH="src;." python -m analysis.theory.pred2.h200_n2       # -> results/theory/pred2/h200_n2.json

Every number is the frozen model's: the closed curve (fluid) and its F1 annealing on exactly the grid analysis.theory.predict
uses (so the values equal the frozen JSON curves, which is checked).  New here: the rule's probability under a declared error
model for the measured 0.5-hit crossing N, N ~ Normal(n_half_pred, sigma) with sigma the RMS error of the fluid n_half on the
three validated cells (frozen validation.json), and P(rule) ~ P(36 < N < 44) (the hit curve is monotone in n on every
variant).  hit is the all-turn hit fraction (first turns always miss), the estimator of Stage C's hit_frac_turns; mu is the
model's nu/E[T], the turns-based estimator (expect it 4-12% high: notes/THEORY_r13_merged.md caveats).
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List

import numpy as np

from ..fluid_rigorous.model import annealed_curve, curve_on_grid
from ..merged import extras as X
from .common import ROOT, cell, frozen_json, write_json

VARIANTS = ["h200_300k", "h200_300k_ratiofit", "h200_300k_lamratiofit", "h200_300k_decode2", "h200_300k_e0a2"]
POINTS = [28.0, 32.0, 36.0, 40.0, 44.0, 48.0, 52.0]
RULE = dict(n_lo=36.0, n_hi=44.0, statement="T3(c) supported iff hit(36) >= 0.5 and hit(44) < 0.5")


def predict_grid(c) -> np.ndarray:
    """The n grid of analysis.theory.predict for this spec (copied expression)."""
    sc = c.spec.get("stage_c", {})
    grid = sorted(float(x) for x in sc.get("grid", [16, 20, 24, 28, 32, 40, 48, 96, 300]))
    cs = c.cs
    nmax = max(cs.n_b * 1.3, max([g for g in grid if g < 300] or [cs.n_b]) * 1.05)
    step = max(0.5, round(cs.n_b / 64.0 * 2) / 2)
    return np.unique(np.concatenate([np.arange(2.0, nmax, step), [g for g in grid if g <= nmax]]))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def validation_sigma() -> Dict[str, object]:
    with open(os.path.join(ROOT, "results", "theory", "merged", "validation.json")) as f:
        rows = json.load(f)["rows"]
    err = {r["cell"]: r["predicted"] - r["measured"] for r in rows if r["quantity"] == "0.5-hit crossing n (fluid)"}
    sg = [err["a100_300k"], err["a100_native"]]
    return dict(errors_pred_minus_meas=err, sigma_all_cells=float(np.sqrt(np.mean(np.square(list(err.values()))))),
                sigma_sglang_cells=float(np.sqrt(np.mean(np.square(sg)))), mean_error_all=float(np.mean(list(err.values()))),
                source="results/theory/merged/validation.json rows '0.5-hit crossing n (fluid)' (frozen)")


def p_rule(center: float, sigma: float, lo: float = 36.0, hi: float = 44.0) -> Dict[str, float]:
    p_lo = 1.0 - _norm_cdf((lo - center) / sigma)        # P(N > 36) = P(hit(36) >= 0.5)
    p_hi = _norm_cdf((hi - center) / sigma)              # P(N < 44) = P(hit(44) < 0.5)
    return dict(p_hit36_ge_half=p_lo, p_hit44_lt_half=p_hi, p_rule=max(0.0, p_lo + p_hi - 1.0))


def run() -> Dict[str, object]:
    sig = validation_sigma()
    out: Dict[str, object] = dict(rule=RULE, error_model=sig, variants={})
    for name in VARIANTS:
        c = cell(name)
        ng = predict_grid(c)
        mu_fl, hit_fl, _ = curve_on_grid(c.cs, ng)
        ann = annealed_curve(c.m.wl, c.m.cost, c.m.M, ng, n_theta=41)
        fz = frozen_json(name)["closed_curve"]["curve"]
        fz_n = np.array(fz["n"], float)
        check = max(float(np.max(np.abs(np.array(fz[k], float) - v))) for k, v in
                    (("mu_fluid", mu_fl), ("hit_fluid", hit_fl), ("mu_annealed", ann["mu"]), ("hit_annealed", ann["hit"])))
        assert len(fz_n) == len(ng) and np.allclose(fz_n, ng)
        pts = {}
        for n in POINTS:
            i = int(np.argmin(np.abs(ng - n)))
            assert abs(ng[i] - n) < 1e-9, (name, n)
            pts[f"{n:g}"] = dict(mu_fluid=float(mu_fl[i]), hit_fluid=float(hit_fl[i]), mu_annealed=float(ann["mu"][i]),
                                 hit_annealed=float(ann["hit"][i]), mu_fluid_over_lambda_ref=float(mu_fl[i]) / c.lam_ref,
                                 above_n_b=bool(n >= c.cs.n_b))
            if n >= c.cs.n_b:
                pts[f"{n:g}"]["stagec_synchronized"] = X.stagec_synchronized(c.m, n)
        nh_fl = c.cs.n_half
        nh_an = float(np.interp(0.5, ann["hit"][::-1], ng[::-1]))   # monotone decreasing hit -> crossing
        det = {}
        for est in ("fluid", "annealed"):
            h36, h44 = pts["36"][f"hit_{est}"], pts["44"][f"hit_{est}"]
            det[est] = dict(hit36=h36, hit44=h44, rule_holds=bool(h36 >= 0.5 and h44 < 0.5))
        prob = {}
        for cen_tag, cen in (("fluid_n_half", nh_fl), ("annealed_n_half", nh_an)):
            for s_tag in ("sigma_all_cells", "sigma_sglang_cells"):
                prob[f"{cen_tag}|{s_tag}"] = dict(center=cen, sigma=sig[s_tag], **p_rule(cen, sig[s_tag]))
        out["variants"][name] = dict(points=pts, n_half_fluid=nh_fl, n_half_annealed=nh_an, n_b=c.cs.n_b, mu_b=c.cs.mu_b,
                                     lambda_ref=c.lam_ref, deterministic=det, probability=prob,
                                     frozen_curve_max_abs_diff=check)
    v = out["variants"]
    det_all = [(k, e, v[k]["deterministic"][e]["rule_holds"]) for k in VARIANTS for e in ("fluid", "annealed")]
    out["band"] = dict(n_rule_holds=sum(1 for *_, x in det_all if x), n_combinations=len(det_all),
                       failing=[f"{k}/{e}" for k, e, x in det_all if not x],
                       p_rule_primary=v["h200_300k"]["probability"]["fluid_n_half|sigma_all_cells"]["p_rule"],
                       p_rule_range=[min(p["p_rule"] for k in VARIANTS for p in v[k]["probability"].values()),
                                     max(p["p_rule"] for k in VARIANTS for p in v[k]["probability"].values())])
    m = cell("h200_300k")
    thr = X.threshold_closed_form(m.m)
    out["rival_capacity_ratio"] = dict(M_over_E_S=thr["pool_part"], M_over_E_bar=m.m.M / thr["E_bar"],
                                       M_over_E_lb=m.m.M / m.E_lb,
                                       prediction="crossing near M/E_S = 27.8 (28-30): hit(36) < 0.5; the rival is refuted by "
                                                  "hit(36) >= 0.5, T3(c) by hit(36) < 0.5")
    return out


def main() -> None:
    p = write_json("h200_n2", run(), [f"analysis/theory/cells/{n}.yaml" for n in VARIANTS] +
                   ["results/theory/merged/validation.json"])
    print("wrote", p)


if __name__ == "__main__":
    main()
