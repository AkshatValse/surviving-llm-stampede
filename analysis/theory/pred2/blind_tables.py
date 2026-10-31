"""Remedy 2a items 2, 3, 4 and 7 (added after the pred2 review, before any of these cells' runs is read): blind lookup tables
from the FROZEN functions only.

    PYTHONPATH="src;." python -m analysis.theory.pred2.blind_tables   # -> results/theory/pred2/{blind_tables,h200_600k}.json

  2a.2  h200_600k: a NEW cell spec (analysis/theory/cells/h200_600k.yaml: base h200_300k, pool 600,000 tokens; zero new
        fitted parameters), run through the frozen analysis.theory.predict unchanged -> results/theory/pred2/h200_600k.json.
  2a.3  Trapped-state tables of the E2 arms for H200 (the primary and the four frozen band variants) at 1.05-1.65 x and for
        Llama-3.1-8B (the frozen a-priori spec) at 1.35-2.5 x, step 0.05, caps 20-32 (step 2): per multiple the frozen
        open_equilibria (n1, n_u, b_stat), good_state (NOBURST hit and n1), trapped_e2 (backlog, token ratio, gap/R, R, cycle,
        sessions/s), critical_burst_fresh, and capped_static_drain at every cap.  These are the same calls predict.py makes for
        a registered arm, so any point the cells later register is covered blind.  (For Llama the registration-conditional
        recipe, analysis.theory.pred2.conditional, stays the binding prediction at the registered points: it uses the measured
        E0a lambda_ref and token rate, which the a-priori table cannot.)  The table is in multiples of the frozen spec's
        lambda_ref and also lists lambda in sessions/s.
  2a.4  Rival predictions per blind cell, frozen alongside: the capacity ratios M/Ebar, M/E_lb, M/E_S, n_b, and the
        exogenous-gap closures that need no measured input -- Che with W = Z (h = min(1, M/(n Ebar)) (1 - 1/E[T])) and Yao's
        balance closed by Little's law with no service time (lambda0 = n / ((E[T] - 1) zbar)) -- on every integer n of the
        cell's Stage C range and its registered grid; b_stat at the table multiples (2a.3) and at the frozen E2 points.
  2a.7  Pool sweep (a100_pool150k, a100_pool600k), and h200_600k: the job grids of Stage C 17168864-69 and E0b 17168870-81 are
        set on Nova (lead-owned clone; not readable here without ssh), so the frozen curves are tabulated at EVERY integer n
        from 2 to 1.3 n_b (plus 192 and 300), fluid and F1, exactly as predict.py evaluates a grid point (fluid: curve_on_grid;
        F1: interpolation on the frozen annealed grid), and the frozen F2 escape probability at every multiple from 1.01 x in
        steps of 0.01 up to the fluid window; any registered n or multiple on these lattices is then a lookup.  Checked against
        the frozen JSON at its own grid points and 0.05 multiples (maximum difference reported; 0 expected).
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import critical_burst_fresh, curve_on_grid, open_equilibria
from ..merged import extras as X
from ..merged.spec import load_spec
from ..predict import clean, predict
from .common import CELLS_DIR, OUT_DIR, cell, frozen_json, provenance, write_json
from .prop_e import yao_T

H200 = ["h200_300k", "h200_300k_ratiofit", "h200_300k_lamratiofit", "h200_300k_decode2", "h200_300k_e0a2"]
TABLES = {name: [round(x, 2) for x in np.arange(1.05, 1.6501, 0.05)] for name in H200}
TABLES["llama31_8b_300k"] = [round(x, 2) for x in np.arange(1.35, 2.5001, 0.05)]
CAPS = [20, 22, 24, 26, 28, 30, 32]
BLIND = ["a100_pool150k", "a100_pool600k"] + H200 + ["h200_600k", "llama31_8b_300k"]
POOL = ["a100_pool150k", "a100_pool600k", "h200_600k"]


def _f(x):
    return float(x) if x is not None else None


def arm_table(name: str, mults: List[float]) -> Dict[str, Any]:
    c = cell(name)
    m, cs = c.m, c.cs
    rows = {}
    for x in mults:
        lam = float(x) * c.lam_ref
        eq = open_equilibria(cs, lam)
        rec: Dict[str, Any] = dict(mult=float(x), lam=lam, n1=eq.n1, n_u=eq.n_u, b_stat=eq.b_stat, trapped_drift=eq.trapped_drift,
                                   in_window=bool(cs.mu_b < lam < cs.mu_max))
        if rec["in_window"]:
            rec["noburst_good_state"] = X.good_state(m, cs, lam)
            rec["burst_trapped"] = X.trapped_e2(m, cs, lam)
            rec["critical_burst_fresh"] = critical_burst_fresh(m, cs, lam)
            rec["capped_static"] = {str(k): X.capped_static_drain(m, cs, lam, float(k)) for k in CAPS}
        elif lam >= cs.mu_max:
            rec["note"] = "lambda >= mu_max: no good state; every run is stuck (trapped state from n1 = 0 listed)"
            rec["burst_trapped"] = X.trapped_e2(m, cs, lam)
            rec["capped_static"] = {str(k): X.capped_static_drain(m, cs, lam, float(k)) for k in CAPS}
        else:
            rec["note"] = "lambda <= lambda_miss: no trap"
        rows[f"{x:.2f}"] = rec
    return dict(cell=name, lambda_ref=c.lam_ref, mu_max=cs.mu_max, mu_b=cs.mu_b, n_b=cs.n_b, window=cs.mu_max / c.lam_ref,
                caps=CAPS, rows=rows)


def rivals(name: str, fz: Dict[str, Any] = None) -> Dict[str, Any]:
    c = cell(name)
    wl, M, ET = c.m.wl, c.m.M, c.m.ET
    thr = X.threshold_closed_form(c.m)
    Ebar = thr["E_bar"]
    fu = 1.0 - 1.0 / ET
    grid = [float(g) for g in c.spec.get("stage_c", {}).get("grid", [])]
    ns = sorted(set(range(2, int(math.ceil(max(1.3 * c.cs.n_b, 2.2 * M / Ebar))) + 1)) | set(grid))
    h_che, h_little = {}, {}
    for n in ns:
        h_che[f"{n:g}"] = min(1.0, M / (n * Ebar)) * fu
        T = yao_T(wl, M, n / ((ET - 1.0) * wl.zmean))
        h_little[f"{n:g}"] = wl.F(T) * fu

    def cross(h):
        keys = sorted(h, key=float)
        for a, b in zip(keys[:-1], keys[1:]):
            if h[a] >= 0.5 > h[b]:
                return float(a) + (h[a] - 0.5) / (h[a] - h[b]) * (float(b) - float(a))
        return math.nan

    if fz is None:
        fz = frozen_json(name)
    b_stat_frozen = {k: a.get("b_stat") for k, a in (fz or {}).get("e2", {}).get("arms", {}).items()}
    return dict(cell=name, M=M, E_bar=Ebar, E_S=thr["E_S"], E_lb=c.E_lb, M_over_E_bar=M / Ebar, M_over_E_lb=M / c.E_lb,
                M_over_E_S=thr["pool_part"], n_b=thr["n_b"], tool_call_part=thr["tool_call_part"], n_half_fluid=c.cs.n_half,
                che_W_eq_Z_hit=h_che, yao_little_no_service_hit=h_little, che_half_crossing=cross(h_che),
                yao_little_half_crossing=cross(h_little), b_stat_at_frozen_e2_points=b_stat_frozen,
                note="exogenous-gap closures (Proposition E): no measured input; hit = all-turn fraction (first turns miss)")


def pool_lookup(name: str, frozen: Dict[str, Any]) -> Dict[str, Any]:
    c = cell(name)
    cs = c.cs
    cv = frozen["closed_curve"]["curve"]
    ng = np.asarray(cv["n"], float)
    mu_a, hit_a = np.asarray(cv["mu_annealed"], float), np.asarray(cv["hit_annealed"], float)
    ns = sorted(set(float(n) for n in range(2, int(math.ceil(1.3 * cs.n_b)) + 1)) | {192.0, 300.0})
    pts = {}
    for g in ns:
        f_mu, f_hit, _ = curve_on_grid(cs, np.array([g]))
        pts[f"{g:g}"] = dict(mu_fluid=float(f_mu[0]), hit_fluid=float(f_hit[0]),
                             mu_annealed=float(np.interp(g, ng, mu_a)) if g <= ng[-1] else cs.mu_b,
                             hit_annealed=float(np.interp(g, ng, hit_a)) if g <= ng[-1] else 0.0)
    # check at the frozen grid points (predict.py computes them the same way)
    d = 0.0
    for k, p in frozen["closed_curve"]["grid_points"].items():
        g = float(k)
        f_mu, f_hit, _ = curve_on_grid(cs, np.array([g]))
        a_mu = float(np.interp(g, ng, mu_a)) if g <= ng[-1] else cs.mu_b
        d = max(d, abs(float(f_mu[0]) - p["mu_fluid"]), abs(float(f_hit[0]) - p["hit_fluid"]), abs(a_mu - p["mu_annealed"]))
    # F2 escape at every 0.01 multiple (H and target exactly as predict.py)
    fe = frozen["from_empty_edge"]
    H = float(fe["horizon_s"])
    top = cs.mu_max / c.lam_ref
    esc = {}
    for x in [round(v, 2) for v in np.arange(1.01, top + 1e-9, 0.01)]:
        lam = x * c.lam_ref
        esc[f"{x:.2f}"] = 1.0 if lam >= cs.mu_max else float(escape_probability(c.mu_f, lam, c.I_D, cs.n_b, H)["p_escape"])
    de = max(abs(esc[f"{float(k):.2f}"] - v) for k, v in fe["p_escape_fine"].items() if f"{float(k):.2f}" in esc)
    return dict(cell=name, lambda_ref=c.lam_ref, n_b=cs.n_b, n_half_fluid=cs.n_half, mu_max=cs.mu_max, window=top,
                points_every_integer_n=pts, p_escape_every_0p01_mult=esc, horizon_s=H,
                frozen_check=dict(curve_max_abs_diff=d, escape_max_abs_diff_at_0p05=de))


def run_h200_600k() -> Dict[str, Any]:
    spec = load_spec(os.path.join(CELLS_DIR, "h200_600k.yaml"))
    res = predict(spec)
    res["pred2"] = dict(note="NEW blind cell spec (remedy 2a.2, for the contingent N6); frozen predict.py unchanged",
                        provenance=provenance([spec["_path"]]))
    return res


def main() -> None:
    import json
    os.makedirs(OUT_DIR, exist_ok=True)
    h6 = clean(run_h200_600k())
    p6 = os.path.join(OUT_DIR, "h200_600k.json")
    with open(p6, "w") as f:
        json.dump(h6, f, indent=1)
    print("wrote", p6, flush=True)
    out: Dict[str, Any] = dict(trapped_tables={}, rivals={}, pool_lookup={})
    for name, mults in TABLES.items():
        out["trapped_tables"][name] = arm_table(name, mults)
        print("table", name, flush=True)
    for name in BLIND:
        out["rivals"][name] = rivals(name, h6 if name == "h200_600k" else None)
    for name in POOL:
        fz = h6 if name == "h200_600k" else frozen_json(name)
        out["pool_lookup"][name] = pool_lookup(name, fz)
        print("lookup", name, out["pool_lookup"][name]["frozen_check"], flush=True)
    p = write_json("blind_tables", out, ["analysis/theory/cells/h200_600k.yaml"])
    print("wrote", p)


if __name__ == "__main__":
    main()
