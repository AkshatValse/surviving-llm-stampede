"""The merged round-13 theory: ONE prediction code path, cell spec (YAML) -> predictions (JSON).

    PYTHONPATH="src;." python -m analysis.theory.predict analysis/theory/cells/a100_300k.yaml [--out FILE] [--quick]

Model: the fluid mean-field model of approach B (analysis/theory/fluid_rigorous) with the grafts and new layers of
analysis/theory/merged/extras.py; notes/THEORY_r13_merged.md has the statement, the proofs and the fitting audit.
A spec carries only independent inputs (analysis/theory/merged/spec.py); the JSON carries an ``audit`` list saying where
every parameter comes from and that no measured mu(n) point, E0b outcome or E2 outcome is used.  Deterministic: the only
numerical choices are grids, listed in ``numerics``.  Default output: results/theory/merged/<spec name>.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .fluid_rigorous.edge import predicted_edge
from .fluid_rigorous.model import (annealed_curve, critical_burst_fresh, curve_on_grid, kv_dispersion, local_window_condition,
                                   open_equilibria, summarize_curve, window_law_terms, window_upper_bound)
from .merged import extras as X
from .merged.spec import ROOT, build, lambda_ref_of, load_spec

OUT_DIR = os.path.join(ROOT, "results", "theory", "merged")
CODE = ["analysis/theory/predict.py", "analysis/theory/merged/spec.py", "analysis/theory/merged/extras.py",
        "analysis/theory/fluid_rigorous/model.py", "analysis/theory/fluid_rigorous/edge.py",
        "analysis/theory/fluid_rigorous/trapped.py", "analysis/theory/fluid_rigorous/oos.py", "analysis/theory/merged/fold.py",
        "analysis/theory/merged/scoring.yaml"]
MODEL_VERSION = "r13-merged-2"   # -1 plus the post-review fixes of 2026-10-31 (rescue collapsed bound, burst peak delay, outputs)


def sha256(path: str) -> str:
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def clean(o: Any) -> Any:
    """JSON-safe copy: numpy scalars to Python, non-finite floats to None."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [clean(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _scoring() -> Dict[str, Any]:
    import yaml
    with open(os.path.join(ROOT, "analysis", "theory", "merged", "scoring.yaml")) as f:
        return yaml.safe_load(f) or {}


def first_half_crossing(n: np.ndarray, hit: np.ndarray) -> float:
    for k in range(len(n) - 1):
        if hit[k] >= 0.5 > hit[k + 1]:
            return float(n[k] + (hit[k] - 0.5) / (hit[k] - hit[k + 1]) * (n[k + 1] - n[k]))
    return math.nan


def predict(spec: Dict[str, Any], quick: bool = False) -> Dict[str, Any]:
    t_start = time.time()
    m, audit, info = build(spec)
    cs = summarize_curve(m)
    lam_ref, lr_row = lambda_ref_of(spec, m)
    audit.append(lr_row)
    b = m.bad()
    thr = X.threshold_closed_form(m)
    e32, e64 = m.all_miss_closed(32), m.all_miss_closed(64)
    out: Dict[str, Any] = dict(model=MODEL_VERSION, spec_name=spec.get("name"), spec_path=spec.get("_path"),
                               description=spec.get("description", ""), blind=spec.get("blind", False), info=info)

    # ---------------------------------------------------------------- all-miss state and E0a analogue
    out["all_miss"] = dict(lambda_miss_model_turns=b["mu"], nu_b=b["nu"], n_b=b["n_b"], threshold=thr,
                           tokens_saturated=b["tok"], e0a_pop32_lambda_turns=e32["mu"], e0a_pop32_tokens=e32["tok"],
                           e0a_pop64_tokens=e64["tok"], pop64_over_pop32_tokens=e64["tok"] / e32["tok"],
                           decode_share_saturated=1.0 - b["p"], compute_bound=b["compute_bound"])

    # ---------------------------------------------------------------- closed curve: fluid and annealed (F1)
    sc = spec.get("stage_c", {})
    grid = sorted(float(x) for x in sc.get("grid", [16, 20, 24, 28, 32, 40, 48, 96, 300]))
    sc_w = sc.get("window_s", [900.0, 2700.0])
    nmax = max(cs.n_b * 1.3, max([g for g in grid if g < 300] or [cs.n_b]) * 1.05)
    step = max(0.5, round(cs.n_b / 64.0 * 2) / 2)
    ngrid = np.unique(np.concatenate([np.arange(2.0, nmax, step), [g for g in grid if g <= nmax]]))
    mu_fl, hit_fl, _ = curve_on_grid(cs, ngrid)
    n_theta = 21 if quick else 41
    ann = annealed_curve(m.wl, m.cost, m.M, ngrid, n_theta=n_theta)
    ia = int(np.argmax(ann["mu"]))
    lm_ann = dict(peak_n=float(ngrid[ia]), mu_max=float(ann["mu"][ia]), hit_at_peak=float(ann["hit"][ia]),
                  n_half=first_half_crossing(ngrid, ann["hit"]), cv2=float(ann["cv2"]))
    lm_fl = dict(peak_n=cs.n_star, mu_max=cs.mu_max, hit_at_peak=cs.h_star, n_half=cs.n_half, n_b=cs.n_b,
                 single_valued=not cs.bistable, n_folds=len(cs.folds),
                 dn_dR_negative_everywhere=bool(np.all(np.diff([p["n"] for p in cs.pts]) > 0)))
    pts = {}
    for g in grid:
        f_mu, f_hit, _ = curve_on_grid(cs, np.array([g]))
        a_mu = float(np.interp(g, ngrid, ann["mu"])) if g <= ngrid[-1] else cs.mu_b
        a_hit = float(np.interp(g, ngrid, ann["hit"])) if g <= ngrid[-1] else 0.0
        rec = dict(mu_fluid=float(f_mu[0]), hit_fluid=float(f_hit[0]), mu_annealed=a_mu, hit_annealed=a_hit)
        if g >= cs.n_b:
            rec["stagec_synchronized"] = X.stagec_synchronized(m, g, t0=float(sc_w[0]), t1=float(sc_w[1]))
        pts[str(g)] = rec
    out["closed_curve"] = dict(fluid=lm_fl, annealed=lm_ann, grid_points=pts,
                               curve=dict(n=ngrid, mu_fluid=mu_fl, hit_fluid=hit_fl, mu_annealed=ann["mu"], hit_annealed=ann["hit"]))

    # ---------------------------------------------------------------- window and theory-side checks
    lw = window_law_terms(m, cs)
    uniform = not info.get("architecture_ratios") and not info.get("decode_side_speedup")
    s_unif = (info.get("speed_factor_fitted") or 1.0) if uniform else None
    out["window"] = dict(model_units=cs.window, vs_lambda_ref=cs.mu_max / lam_ref, annealed_vs_lambda_ref=lm_ann["mu_max"] / lam_ref,
                         law_approx=lw["omega_mem"], compute_cap=lw["omega_cap"],
                         upper_bound=window_upper_bound(m, nh=120 if quick else 400)["omega_upper"],
                         speed_factor_vs_a100=s_unif, s_times_zbar_s=(s_unif * m.wl.zmean) if s_unif else None,
                         local_condition=local_window_condition(m))

    # ---------------------------------------------------------------- from-empty edge (F2)
    pk = min(cs.pts, key=lambda p: abs(p["mu"] - cs.mu_max))
    kd = kv_dispersion(m.wl, pk["S_bar"])
    I_D = kd["I_D"]
    mu_fn, _, _, _, _ = X.curve_fn(cs)
    e0b = spec.get("e0b", {})
    reg = sorted(float(x) for x in e0b.get("multiples", [1.25, 1.5, 1.75, 2.0, 2.5, 3.0]))
    H = float(e0b.get("horizon_s", 3000.0))
    top = min(cs.mu_max / lam_ref, max(reg) + 0.5)
    fine = [round(x, 2) for x in np.arange(1.05, top + 1e-9, 0.05)]
    mults = sorted(set(reg) | set(fine))
    ed = predicted_edge(mu_fn, lam_ref, mults, I_D, cs.n_b, H, cs.mu_max)
    p_by = {float(r["mult"]): float(r["p_escape"]) for r in ed["rows"]}
    p_reg = {x: p_by[x] for x in reg}
    stable = [x for x in reg if all(p_reg[y] < 0.5 for y in reg if y <= x)]
    largest_stable = max(stable) if stable else math.nan
    first_unst = min([x for x in reg if x > largest_stable], default=math.nan) if stable else min(reg)
    out["from_empty_edge"] = dict(horizon_s=H, I_D=I_D, E_lb=kd["E_lb"], target="n_b (all-miss end)",
                                  edge_mult=ed["edge_mult"], p_escape_registered=p_reg, p_escape_fine=p_by,
                                  predicted_bracket=[largest_stable, first_unst], fluid_upper_edge_mult=cs.mu_max / lam_ref)
    # secondary (approach A's R6 criterion on this curve; reported, not used for the registration consequence)
    sec_mults = sorted(set(reg) | set(fine[::2]))
    sec = X.edge_level_crossing(m, cs, lam_ref, sec_mults, horizon=H, n_rep=100 if quick else 400, seed=0)
    out["from_empty_edge"]["secondary_level_crossing"] = dict(
        edge50_mult=sec["edge50_mult"], criterion=sec["criterion"], n_rep=sec["n_rep"],
        p_unstable_registered={str(r["mult"]): r["p_unstable"] for r in sec["rows"] if r["mult"] in reg},
        p_unstable_all={str(r["mult"]): r["p_unstable"] for r in sec["rows"]})
    # absolute-rate output (sessions/s), so a change of lambda_ref needs no reinterpretation
    out["from_empty_edge"]["edge_lambda_sessions_per_s"] = ed["edge_lam"]
    out["from_empty_edge"]["p_escape_by_lambda_sessions_per_s"] = {f"{x * lam_ref:.6f}": p for x, p in sorted(p_by.items())}
    out["from_empty_edge"]["lambda_ref_used"] = lam_ref
    grid_ann = {g: (float(np.interp(g, ngrid, ann["mu"])) if g <= ngrid[-1] else cs.mu_b) for g in grid if g < 300}
    out["registration_consequence"] = X.registration_consequence(p_reg, cs.mu_max, lam_ref, grid_ann)

    # ---------------------------------------------------------------- open system and the E2 arms
    e2 = spec.get("e2", {})
    e2m = e2.get("multiples", "auto")
    if e2m == "auto":
        e2m = out["registration_consequence"]["lambda_points"] or []
    cap = e2.get("cap", "auto")
    if cap == "auto":
        cap = out["registration_consequence"]["n_cap"]
    burst = e2.get("burst", dict(n=200, t_s=1200, width_s=60))
    win = e2.get("window_s", [5700.0, 8700.0])
    arms = {}
    for x in e2m:
        lam = float(x) * lam_ref
        eq = open_equilibria(cs, lam)
        rec = dict(mult=float(x), lam=lam, n1=eq.n1, n_u=eq.n_u, b_stat=eq.b_stat, trapped_drift=eq.trapped_drift,
                   in_window=bool(cs.mu_b < lam < cs.mu_max))
        if rec["in_window"]:
            rec["noburst_good_state"] = X.good_state(m, cs, lam)
            rec["burst_trapped"] = X.trapped_e2(m, cs, lam, burst_n=float(burst["n"]), t_b=float(burst["t_s"]),
                                                burst_w=float(burst["width_s"]), window=win)
            rec["capped_static"] = X.capped_static_drain(m, cs, lam, float(cap), burst_n=float(burst["n"]))
            rec["critical_burst_fresh"] = critical_burst_fresh(m, cs, lam)
        arms[str(x)] = rec
    out["e2"] = dict(cap=cap, burst=burst, window_s=win, arms=arms)

    # ---------------------------------------------------------------- registered tests (bursts, rescue)
    tests = {}
    for t in spec.get("tests", []) or []:
        kind, name = t["kind"], t.get("name", t["kind"])
        if kind == "burst_basin":
            lam = float(t["multiple"]) * lam_ref
            w0, w1 = t.get("eval_window_s", [5700.0, 8700.0])
            gsb = X.good_state(m, cs, lam)
            if gsb.get("exists") and gsb.get("hit", 0.0) > 0:
                hb = float(gsb["hit"])
                stuck_by = float(w0) + min(1.0, float(t.get("stuck_hit_below", 0.2)) / hb) * (float(w1) - float(w0))
            else:   # no good state at this rate: every run is stuck; the background escape horizon is irrelevant
                hb, stuck_by = math.nan, float(w0)
            sizes = sorted(set([float(v) for v in t["bursts"]] + [float(v) for v in t.get("sweep", [])]))
            tests[name] = dict(kind=kind, spec=t, stuck_by_s=stuck_by,
                               result=X.burst_trap_probability(m, cs, lam, sizes, I_D, t_b=float(t.get("t_s", 1200.0)),
                                                               burst_w=float(t.get("width_s", 60.0)), stuck_by_s=stuck_by))
        elif kind == "rescue":
            res = {}
            bt = t.get("burst", burst)
            for x in t["multiples"]:
                res[str(x)] = X.rescue_two_phase(m, cs, float(x) * lam_ref, float(t["cap"]), float(t["t_on_s"]), I_D,
                                                 t_b=float(bt["t_s"]), burst_n=float(bt["n"]), hold=float(t.get("release_hold_s", 300.0)),
                                                 min_on=float(t.get("min_on_s", 600.0)), check=float(t.get("release_check_s", 10.0)),
                                                 release_by=float(t.get("release_by_s", 7200.0)), horizon=float(t.get("horizon_s", 8700.0)))
            tests[name] = dict(kind=kind, spec=t, result=res)
        else:
            raise ValueError(f"unknown test kind {kind!r}")
    out["tests"] = tests

    # ---------------------------------------------------------------- Proposition F (fold identity; diagnostic only)
    if m.cost.mode == "separate":
        from .merged import fold as FOLD
        out["fold_identity"] = dict(FOLD.fold_margin(m), **FOLD.leading_order_ratio(m),
                                    note="max_R f I / (n_nu D'/E[T]) < 1 <=> n(R) strictly decreasing (no closed-system fold)")

    # ---------------------------------------------------------------- frozen scoring declaration (blind cells)
    sc_all = _scoring()
    out["scoring"] = dict(general=sc_all.get("general", {}), cell=sc_all.get("cells", {}).get(spec.get("name"), {}))

    # ---------------------------------------------------------------- provenance
    files = CODE + [spec["_path"], info["calibration"], spec.get("workload", {}).get("config", "configs/agentload_e2_burst.yaml")]
    out["audit"] = audit
    out["fitted_parameters"] = [r["parameter"] for r in audit if r["kind"] == "fitted"]
    out["uses_measured_mu_curve"] = any(r["uses_measured_mu_curve"] for r in audit)
    out["uses_e0b_or_e2_outcome"] = any(r["uses_e0b_or_e2_outcome"] for r in audit)
    out["numerics"] = dict(n_theta_annealed=n_theta, n_grid_step=step, quick=quick, edge_fine_step=0.05,
                           solution_curve_points=len(cs.pts))
    out["provenance"] = dict(sha256={p: sha256(p) for p in files}, python=sys.version.split()[0], numpy=np.__version__,
                             seconds=time.time() - t_start, created=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    return out


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", nargs="+", help="cell spec YAML file(s) (analysis/theory/cells/*.yaml)")
    ap.add_argument("--out", default=None, help="output JSON (single spec) or directory (default results/theory/merged)")
    ap.add_argument("--quick", action="store_true", help="coarser annealing and bound grids (tests)")
    a = ap.parse_args(argv)
    for sp in a.spec:
        spec = load_spec(sp)
        res = clean(predict(spec, quick=a.quick))
        if a.out and a.out.endswith(".json") and len(a.spec) == 1:
            path = a.out
        else:
            d = a.out or OUT_DIR
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"{spec['name']}.json")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            json.dump(res, f, indent=1)
        fl, an = res["closed_curve"]["fluid"], res["closed_curve"]["annealed"]
        print(f"{spec['name']}: peak n {fl['peak_n']:.1f} (annealed {an['peak_n']:.1f}), mu_max {fl['mu_max']:.4f} "
              f"({an['mu_max']:.4f}), n_half {fl['n_half']:.1f}, n_b {fl['n_b']:.2f}, lambda_miss {res['all_miss']['e0a_pop32_lambda_turns']:.4f}, "
              f"window {res['window']['vs_lambda_ref']:.2f}, edge {res['from_empty_edge']['edge_mult']:.2f} x  "
              f"[{res['provenance']['seconds']:.0f} s] -> {os.path.relpath(path, ROOT)}", flush=True)


if __name__ == "__main__":
    main()
