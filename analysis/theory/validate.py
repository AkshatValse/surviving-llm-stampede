"""Validation table of the merged theory on the three measured cells.

    PYTHONPATH="src;." python -m analysis.theory.validate [--quick] [--reuse]

Runs analysis.theory.predict on analysis/theory/cells/{a100_300k,a100_native,vllm_300k}.yaml (or, with --reuse, reads the
JSONs it wrote) and compares with the measured values.  Measured values are read here and ONLY here, after the predictions
exist: Stage C curves, E0a / E0a-POP64 calibrations, E0b brackets and E2 trap_v2 rows from results/nova/ (paths in
analysis/theory/fluid_rigorous/cells.py), and the frozen-loopvars values, E0b per-multiple outcomes, post-burst minima and
CAPPED drain times typed with their sources in analysis/theory/che_endogenous/measured.py.
Writes results/theory/merged/validation_table.{csv,md} and validation.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .che_endogenous.measured import MEASURED
from .fluid_rigorous.cells import e0a64, measured
from .merged.spec import CELLS_DIR, ROOT, load_spec
from .predict import OUT_DIR, clean, predict

CELLS = ("a100_300k", "a100_native", "vllm_300k")
FITTED = {"vllm_300k": "E0a token rate (fitted: one speed factor)"}
SECONDARY_LL: Dict[str, float] = {}


def _rel(p: float, m: float) -> float:
    return (p - m) / m if (m not in (0, None) and p is not None and math.isfinite(p) and math.isfinite(m)) else math.nan


def _seeds(pred: float, meas: List[float]) -> Dict[str, Any]:
    meas = [float(x) for x in meas]
    lo, hi, mean = min(meas), max(meas), float(np.mean(meas))
    return dict(meas=f"{', '.join(f'{x:.4g}' for x in meas)}", meas_mean=mean, in_range=bool(lo <= pred <= hi),
                err=_rel(pred, mean))


def rows_for(cell: str, P: Dict[str, Any]) -> List[Dict[str, Any]]:
    me = measured(cell)
    MT = MEASURED[cell]
    R: List[Dict[str, Any]] = []

    def add(group: str, quantity: str, pred, meas, err=None, note: str = "", in_range=None):
        R.append(dict(cell=cell, group=group, quantity=quantity, predicted=pred, measured=meas,
                      rel_err=err, in_seed_range=in_range, note=note))

    am, cc, fl, an = P["all_miss"], P["closed_curve"], P["closed_curve"]["fluid"], P["closed_curve"]["annealed"]
    fit_note = FITTED.get(cell, "")
    add("all-miss", "lambda_miss turns-based (E0a, POP 32)", am["e0a_pop32_lambda_turns"], me.lam_ref,
        _rel(am["e0a_pop32_lambda_turns"], me.lam_ref), "tokens fitted, turns predicted" if fit_note else "")
    add("all-miss", "E0a uncached tokens/s", am["e0a_pop32_tokens"], me.tokens_ref, _rel(am["e0a_pop32_tokens"], me.tokens_ref),
        fit_note)
    e64 = e0a64(cell)
    if e64:
        mr = e64["tokens"] / me.tokens_ref
        add("all-miss", "POP-64 / POP-32 E0a tokens", am["pop64_over_pop32_tokens"], mr, _rel(am["pop64_over_pop32_tokens"], mr),
            "check only (one POP-64 seed)")
    # closed curve landmarks
    add("closed", "peak n (fluid)", fl["peak_n"], me.peak_n_sessions, None, f"measured flat top (within 5%): {me.flat_top}")
    add("closed", "peak n (annealed F1)", an["peak_n"], me.peak_n_sessions, None, "")
    add("closed", "mu_max sessions/s (fluid)", fl["mu_max"], me.mu_max_sessions, _rel(fl["mu_max"], me.mu_max_sessions),
        f"turns-based measured {me.mu_max_turns:.4f}")
    add("closed", "mu_max sessions/s (annealed F1)", an["mu_max"], me.mu_max_sessions, _rel(an["mu_max"], me.mu_max_sessions), "")
    # post-review (2026-10-31): the model's mu is nu / E[T], i.e. the TURNS-BASED estimator; score against it too
    add("closed", "mu_max turns-based (fluid)", fl["mu_max"], me.mu_max_turns, _rel(fl["mu_max"], me.mu_max_turns),
        "model-consistent estimator")
    add("closed", "mu_max turns-based (annealed F1)", an["mu_max"], me.mu_max_turns, _rel(an["mu_max"], me.mu_max_turns),
        "model-consistent estimator; primary for blind scoring")
    add("closed", "0.5-hit crossing n (fluid)", fl["n_half"], me.n_half, _rel(fl["n_half"], me.n_half), "")
    add("closed", "0.5-hit crossing n (annealed F1)", an["n_half"], me.n_half, _rel(an["n_half"], me.n_half), "")
    gp = cc["grid_points"]
    rms_rows: List[Any] = []
    for n, mu_s, mu_t, h in zip(me.n, me.mu_sessions, me.mu_turns, me.hit):
        g = gp.get(str(float(n)))
        if g is None:
            continue
        if n < 300:
            add("closed", f"mu({n:g}) sessions/s fluid | annealed", f"{g['mu_fluid']:.4f} | {g['mu_annealed']:.4f}", mu_s,
                _rel(g["mu_annealed"], mu_s), "rel_err of annealed")
            add("closed", f"mu({n:g}) turns-based fluid | annealed", f"{g['mu_fluid']:.4f} | {g['mu_annealed']:.4f}", mu_t,
                _rel(g["mu_annealed"], mu_t), f"rel_err of annealed; fluid {_rel(g['mu_fluid'], mu_t):+.3f}")
            rms_rows.append((n, mu_s, mu_t, g["mu_fluid"], g["mu_annealed"]))
            add("closed", f"hit({n:g}) fluid | annealed", f"{g['hit_fluid']:.3f} | {g['hit_annealed']:.3f}", h, None, "")
        sy = g.get("stagec_synchronized")
        if sy and n >= fl["n_b"]:
            add("closed (Stage C protocol)", f"mu({n:g}) synchronized start, sessions | turns-based",
                f"{sy['mu_sessions']:.4f} | {sy['mu_turns_based']:.4f}", f"{mu_s:.4f} | {mu_t:.4f}", _rel(sy["mu_sessions"], mu_s),
                "graft of A; valid when trapped from t=0 (n E_1 > M)" + ("" if sy["trapped_from_start"] else " -- NOT the case here"))
    if rms_rows:
        arr = np.array(rms_rows, float)
        for j, est in ((1, "sessions"), (2, "turns-based")):
            for k, mod in ((3, "fluid"), (4, "annealed F1")):
                e_all = (arr[:, k] - arr[:, j]) / arr[:, j]
                sub = arr[:, 0] < fl["n_b"]
                e_sub = e_all[sub]
                add("closed (RMS)", f"RMS rel err of mu, {mod} vs {est}",
                    f"all n<300: {math.sqrt(float((e_all ** 2).mean())):.3f}", f"below n_b only: {math.sqrt(float((e_sub ** 2).mean())):.3f}",
                    math.sqrt(float((e_all ** 2).mean())), "all-points RMS is the headline; the below-n_b subset is chosen by the model")
    add("closed", "mu at large n, turns-based (stationary mu_b)", am["lambda_miss_model_turns"], me.mu_large_turns,
        _rel(am["lambda_miss_model_turns"], me.mu_large_turns), f"measured at n = {me.n_large:g}")
    add("closed", "all-miss threshold n_b (= closed form)", f"{fl['n_b']:.2f} (= {am['threshold']['n_b_closed_form']:.2f})",
        "collapse between measured grid points", None,
        "measured hit: " + ", ".join(f"{n:g}: {h:.2f}" for n, h in zip(me.n, me.hit) if n < 300))
    add("window", "mu_max / lambda_ref (fluid)", P["window"]["vs_lambda_ref"], me.window_sessions,
        _rel(P["window"]["vs_lambda_ref"], me.window_sessions), f"turns-based measured {me.window_turns:.2f}")
    add("window", "mu_max / lambda_ref (annealed F1)", P["window"]["annealed_vs_lambda_ref"], me.window_sessions,
        _rel(P["window"]["annealed_vs_lambda_ref"], me.window_sessions), "")
    add("window", "mu_max / lambda_ref turns-based (annealed F1)", P["window"]["annealed_vs_lambda_ref"], me.window_turns,
        _rel(P["window"]["annealed_vs_lambda_ref"], me.window_turns), "model-consistent; primary for blind scoring")
    # from-empty edge
    fe = P["from_empty_edge"]
    obs = MT["e0b"]
    ll = 0.0
    for x, st in sorted(obs.items()):
        p = fe["p_escape_registered"].get(str(float(x)))
        if p is None:
            continue
        pe = min(max(p, 1e-6), 1 - 1e-6)
        ll += math.log(1 - pe) if st else math.log(pe)
        add("from-empty edge (F2)", f"P(unstable 3000 s run) at {x:g} x", p, "stable" if st else "UNSTABLE", None, "")
    add("from-empty edge (F2)", "predicted bracket (stable, unstable)", f"{fe['predicted_bracket']}", f"[{me.bracket['stable']}, {me.bracket['unstable']}]",
        None, f"50% edge {fe['edge_mult']:.2f} x; log-likelihood of the observed outcomes {ll:.3f}")
    sec = fe.get("secondary_level_crossing")
    if sec:
        ll2 = 0.0
        for x, st in sorted(obs.items()):
            p = sec["p_unstable_registered"].get(str(float(x)))
            if p is None:
                continue
            pe = min(max(p, 1e-3), 1 - 1e-3)
            ll2 += math.log(1 - pe) if st else math.log(pe)
        add("from-empty edge (secondary: A's level crossing)", "P(unstable) at the registered multiples",
            ", ".join(f"{k}: {v:.3f}" for k, v in sec["p_unstable_registered"].items()), "", None,
            f"50% edge {sec['edge50_mult']:.2f} x; log-likelihood {ll2:.3f} (probabilities floored at 1e-3)")
        SECONDARY_LL[cell] = ll2
    # E2
    tr = me.trap
    for x, arm in P["e2"]["arms"].items():
        mult = float(x)
        sel = tr[(tr["arm"] == "burst") & (np.isclose(tr["rate_mult"], mult))]
        bt = arm.get("burst_trapped")
        if bt is None:
            continue
        lv = MT.get("loopvars", {}).get(mult, {})
        eb = MT.get("e2_burst", {}).get(mult, {})
        grp = f"E2 BURST {mult:g} x"
        if len(sel):
            s = _seeds(bt["backlog"], sel["backlog_eval_mean"].tolist()); add(grp, "backlog [5700, 8700) mean", bt["backlog"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(bt["backlog_slope"], sel["backlog_slope"].tolist()); add(grp, "backlog slope (sessions/s)", bt["backlog_slope"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(bt["sessions_per_s"], sel["rate_sessions"].tolist()); add(grp, "session rate (sessions/s)", bt["sessions_per_s"], s["meas"], s["err"], "", s["in_range"])
            ratio = (sel["rate_uncached_tokens"] / sel["uncached_tokens_ref"]).tolist()
            s = _seeds(bt["token_ratio_vs_model_e0a"], ratio); add(grp, "uncached token rate / E0a", bt["token_ratio_vs_model_e0a"], s["meas"], s["err"], "model ratio = trapped / model E0a", s["in_range"])
            s = _seeds(0.0, sel["hit_eval"].tolist()); add(grp, "hit", 0.0, s["meas"], None, "", s["in_range"])
        if lv.get("burst_gap_over_R"):
            s = _seeds(bt["gap_over_R"], lv["burst_gap_over_R"]); add(grp, "gap/R (frozen loopvars)", bt["gap_over_R"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(bt["R"], lv["burst_R"]); add(grp, "R = M/churn (s)", bt["R"], s["meas"], s["err"], "", s["in_range"])
        if eb.get("min_after"):
            s = _seeds(bt["backlog_min_after_burst"], eb["min_after"]); add(grp, "post-burst backlog minimum", bt["backlog_min_after_burst"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(bt["t_min_after_burst"], eb["t_min_after"]); add(grp, "time of the minimum after the burst (s)", bt["t_min_after_burst"], s["meas"], s["err"], "", s["in_range"])
        g = arm.get("noburst_good_state", {})
        grp = f"E2 NOBURST {mult:g} x"
        seln = tr[(tr["arm"] == "noburst") & (np.isclose(tr["rate_mult"], mult))]
        if len(seln):
            s = _seeds(g["hit"], seln["hit_eval"].tolist()); add(grp, "hit", g["hit"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(g["n1"], seln["backlog_eval_mean"].tolist()); add(grp, "sessions in system n1", g["n1"], s["meas"], s["err"], "", s["in_range"])
        if lv.get("good_gap_over_R"):
            s = _seeds(g["gap_over_R"], lv["good_gap_over_R"]); add(grp, "gap/R (frozen loopvars)", g["gap_over_R"], s["meas"], s["err"], "", s["in_range"])
            s = _seeds(g["R"], lv["good_R"]); add(grp, "R = M/churn (s)", g["R"], s["meas"], s["err"], "", s["in_range"])
        cp = arm.get("capped_static", {})
        if eb.get("capped_drain"):
            s = _seeds(cp["drain_after_burst_s"], eb["capped_drain"]); add(f"E2 CAPPED {mult:g} x (cap {P['e2']['cap']})", "gate empty after the burst (s)", cp["drain_after_burst_s"], s["meas"], s["err"], "", s["in_range"])
    return R, ll


def to_markdown(df: pd.DataFrame) -> str:
    def f(v):
        if isinstance(v, float):
            if not math.isfinite(v):
                return ""
            return f"{v:.4g}"
        return "" if v is None else str(v)
    lines = ["| cell | group | quantity | predicted | measured | rel. err | in seed range | note |", "|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        err = r["rel_err"]
        e = f"{100 * err:+.1f}%" if isinstance(err, float) and math.isfinite(err) else ""
        ir = "" if r["in_seed_range"] is None or (isinstance(r["in_seed_range"], float) and math.isnan(r["in_seed_range"])) else ("yes" if r["in_seed_range"] else "no")
        lines.append(f"| {r['cell']} | {r['group']} | {r['quantity']} | {f(r['predicted'])} | {f(r['measured'])} | {e} | {ir} | {f(r['note'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="read results/theory/merged/<cell>.json instead of recomputing")
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    allrows, scores, preds = [], {}, {}
    for c in CELLS:
        path = os.path.join(a.out, f"{c}.json")
        if a.reuse and os.path.exists(path):
            P = json.load(open(path))
        else:
            P = clean(predict(load_spec(os.path.join(CELLS_DIR, f"{c}.yaml")), quick=a.quick))
            with open(path, "w") as f:
                json.dump(P, f, indent=1)
        preds[c] = P
        rows, ll = rows_for(c, P)
        allrows += rows
        scores[c] = ll
    df = pd.DataFrame(allrows)
    df.to_csv(os.path.join(a.out, "validation_table.csv"), index=False)
    with open(os.path.join(a.out, "validation_table.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(df))
    summ = dict(e0b_log_likelihood=scores, e0b_log_likelihood_total=sum(scores.values()),
                e0b_log_likelihood_secondary=dict(SECONDARY_LL), e0b_log_likelihood_secondary_total=sum(SECONDARY_LL.values()),
                fitted_parameters={c: preds[c]["fitted_parameters"] for c in CELLS},
                uses_measured_mu_curve={c: preds[c]["uses_measured_mu_curve"] for c in CELLS},
                n_rows=len(df), seed_range_hits=int(df["in_seed_range"].fillna(False).astype(bool).sum()),
                seed_range_rows=int(df["in_seed_range"].notna().sum()))
    with open(os.path.join(a.out, "validation.json"), "w") as f:
        json.dump(clean(dict(summary=summ, rows=allrows)), f, indent=1)
    print(to_markdown(df))
    print(json.dumps(clean(summ), indent=1))


if __name__ == "__main__":
    main()
