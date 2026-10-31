"""Markdown summary of the merged theory's outputs: selection scores (A vs B), condensed validation, blind predictions.

    PYTHONPATH="src;." python -m analysis.theory.merged.summarize

Reads results/theory/merged/*.json (this code path), results/theory/che_endogenous/validation.json (approach A's own run,
for the selection scores only) and the measured targets (analysis/theory/che_endogenous/measured.py).  Writes
results/theory/merged/summary.md.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

from ..che_endogenous.measured import MEASURED
from .spec import ROOT

RES = os.path.join(ROOT, "results", "theory", "merged")
CELLS = ("a100_300k", "a100_native", "vllm_300k")


def J(name):
    p = os.path.join(RES, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def ll(pd, obs, floor=1e-6):
    s = 0.0
    for x, st in obs.items():
        p = pd.get(str(float(x)), pd.get(str(x)))
        if p is None:
            continue
        p = min(max(p, floor), 1 - floor)
        s += math.log(1 - p) if st else math.log(p)
    return s


def selection_scores():
    A = json.load(open(os.path.join(ROOT, "results", "theory", "che_endogenous", "validation.json")))
    rows = []
    for c in CELLS:
        B = J(c)
        meas = MEASURED[c]
        nb = B["closed_curve"]["fluid"]["n_b"]
        cm = A[c]["comparison"]
        e = {k: [] for k in ("A_mf", "A_sm", "B_fl", "B_an")}
        for n, (mu, _, _) in meas["curve"].items():
            if n >= nb:
                continue
            p = cm["curve_points"][str(n)]
            g = B["closed_curve"]["grid_points"][str(float(n))]
            e["A_mf"].append((p["pred_mf_mu"] - mu) / mu)
            e["A_sm"].append((p["pred_sm_mu"] - mu) / mu)
            e["B_fl"].append((g["mu_fluid"] - mu) / mu)
            e["B_an"].append((g["mu_annealed"] - mu) / mu)
        rms = {k: math.sqrt(np.mean(np.square(v))) for k, v in e.items()}
        ta, tb = [], []
        for mlt, t in cm["trapped_state"].items():
            bt = B["e2"]["arms"][mlt]["burst_trapped"]
            lv = meas.get("loopvars", {}).get(float(mlt), {})
            eb = meas["e2_burst"][float(mlt)]
            for kp, pv, mv in (("pred_backlog", bt["backlog"], eb.get("backlog")), ("pred_token_ratio", bt["token_ratio_vs_model_e0a"], eb.get("ratio")),
                               ("pred_gap_over_R_trapped", bt["gap_over_R"], lv.get("burst_gap_over_R")), ("pred_R_trapped", bt["R"], lv.get("burst_R"))):
                if mv:
                    ta.append(abs(t[kp] - np.mean(mv)) / np.mean(mv))
                    tb.append(abs(pv - np.mean(mv)) / np.mean(mv))
        sec = B["from_empty_edge"].get("secondary_level_crossing", {}).get("p_unstable_registered", {})
        rows.append(dict(cell=c, n_pts=len(e["A_mf"]), rms=rms, llA=ll(cm["from_empty_edge"]["pred_p_unstable"], meas["e0b"], 1e-3),
                         llB=ll(B["from_empty_edge"]["p_escape_registered"], meas["e0b"], 1e-3),
                         llBsec=ll(sec, meas["e0b"], 1e-3) if sec else math.nan,
                         trapA=float(np.mean(ta)), trapB=float(np.mean(tb)),
                         peakA=cm["mu_max"]["pred_mean_field"] / meas["mu_max"] - 1, peakB=B["closed_curve"]["fluid"]["mu_max"] / meas["mu_max"] - 1,
                         peakAs=cm["mu_max"]["pred_smoothed"] / meas["mu_max"] - 1, peakBa=B["closed_curve"]["annealed"]["mu_max"] / meas["mu_max"] - 1,
                         crossA=cm["hit_cross_0p5"]["pred_mean_field"] - meas["hit_cross"], crossB=B["closed_curve"]["fluid"]["n_half"] - meas["hit_cross"]))
    L = ["| cell | curve RMS rel. err. at measured n < n_b: A mean field / A smoothed / B fluid / B annealed | mu_max err. A MF / A SM / B fluid / B annealed | 0.5-hit crossing err. (sessions) A / B | E0b log-likelihood A / B (F2) / B with A's criterion | trapped-state mean abs. rel. err. A / B |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        q = r["rms"]
        L.append(f"| {r['cell']} ({r['n_pts']} pts) | {q['A_mf']:.3f} / {q['A_sm']:.3f} / {q['B_fl']:.3f} / {q['B_an']:.3f} | "
                 f"{100 * r['peakA']:+.1f}% / {100 * r['peakAs']:+.1f}% / {100 * r['peakB']:+.1f}% / {100 * r['peakBa']:+.1f}% | "
                 f"{r['crossA']:+.1f} / {r['crossB']:+.1f} | {r['llA']:.2f} / {r['llB']:.2f} / {r['llBsec']:.2f} | {r['trapA']:.3f} / {r['trapB']:.3f} |")
    tot = (sum(r["llA"] for r in rows), sum(r["llB"] for r in rows), sum(r["llBsec"] for r in rows))
    L.append(f"| total | | | | {tot[0]:.2f} / {tot[1]:.2f} / {tot[2]:.2f} | |")
    return "\n".join(L) + "\n"


def f(x, d=3):
    if x is None:
        return "n/a"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, d) for v in x) + "]"
    if isinstance(x, float):
        return f"{x:.{d}f}" if math.isfinite(x) else "n/a"
    return str(x)


def blind_table():
    L = ["| cell | lambda_miss (turns) | n_b (closed form) | peak n fluid / F1 | mu_max fluid / F1 | hit at peak | 0.5-hit n | window mu_max/lambda_ref fluid / F1 | edge F2 (x lambda_ref) | edge, A's criterion | P(unstable) F2 at the E0b grid | registration consequence (hi, points, cap) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in ("h200_300k", "h200_300k_decode2", "h200_300k_e0a2", "llama31_8b_300k", "a100_pool150k", "a100_pool600k"):
        P = J(name)
        if P is None:
            continue
        fl, an, am, w, fe, rc = (P["closed_curve"]["fluid"], P["closed_curve"]["annealed"], P["all_miss"], P["window"],
                                 P["from_empty_edge"], P["registration_consequence"])
        pr = ", ".join(f"{k}: {v:.2f}" for k, v in fe["p_escape_registered"].items())
        L.append(f"| {name} | {am['e0a_pop32_lambda_turns']:.4f} | {fl['n_b']:.1f} | {fl['peak_n']:.1f} / {an['peak_n']:.1f} | "
                 f"{fl['mu_max']:.3f} / {an['mu_max']:.3f} | {fl['hit_at_peak']:.2f} | {fl['n_half']:.1f} | {w['vs_lambda_ref']:.2f} / {w['annealed_vs_lambda_ref']:.2f} | "
                 f"{fe['edge_mult']:.2f} | {f(fe['secondary_level_crossing']['edge50_mult'], 2)} | {pr} | "
                 f"{f(rc['hi_capped'], 2)}, {f(rc['lambda_points'], 2)}, {f(rc['n_cap'], 0)} |")
    L.append("")
    L.append("Closed-curve points (sessions/s; annealed F1 in brackets; Stage C synchronized-start value for n >= n_b):")
    L.append("")
    for name in ("h200_300k", "h200_300k_decode2", "h200_300k_e0a2", "llama31_8b_300k", "a100_pool150k", "a100_pool600k"):
        P = J(name)
        if P is None:
            continue
        parts = []
        for n, g in P["closed_curve"]["grid_points"].items():
            s = f"n={float(n):g}: {g['mu_fluid']:.3f} ({g['mu_annealed']:.3f}), hit {g['hit_fluid']:.2f}"
            if g.get("stagec_synchronized"):
                s += f", sync {g['stagec_synchronized']['mu_sessions']:.3f}"
            parts.append(s)
        L.append(f"- {name}: " + "; ".join(parts))
    return "\n".join(L) + "\n"


def tests_table():
    L = []
    P = J("b1_basin_300k")
    if P:
        r = P["tests"]["B1"]["result"]
        L.append(f"B1 (300k, 1.65 x, burst in 60 s at 1200 s; STUCK if the [5700, 8700) hit < 0.2): deterministic critical burst "
                 f"{r['b_crit_deterministic']:.1f} (stationary-composition {r['b_stat']:.1f}); n1 = {r['n1']:.1f}, n_u = {r['n_u']:.1f}; "
                 f"background escape before {P['tests']['B1']['stuck_by_s']:.0f} s: {r['rows'][0]['p_escape_background']:.3f}.")
        L.append("")
        L.append("| burst | X0 (session equiv.) | committor q | P(STUCK) per seed | deterministic |")
        L.append("|---|---|---|---|---|")
        for x in r["rows"]:
            L.append(f"| {x['burst']:.0f} | {x['X0']:.1f} | {x['committor']:.3f} | {x['p_trapped']:.3f} | {x['deterministic']} |")
        p100 = [x for x in r["rows"] if x["burst"] == 100][0]["p_trapped"]
        p25 = [x for x in r["rows"] if x["burst"] == 25][0]["p_trapped"]
        pass_p = (p100 ** 3 + 3 * p100 ** 2 * (1 - p100)) * ((1 - p25) ** 3 + 3 * (1 - p25) ** 2 * p25)
        L.append("")
        L.append(f"P(B1 PASS: 100 STUCK in >= 2/3 and 25 not STUCK in >= 2/3, treating not-STUCK as GOOD) = {pass_p:.3f}.")
        L.append("")
    for name, t in (("r1_rescue_300k", "R1"), ("r4_rescue_native", "R4")):
        P = J(name)
        if not P:
            continue
        L.append(f"{t}:")
        L.append("")
        L.append("| rate | n in system at t_on | cycle at t_on (s) | footprint inflation | phase-1 rate fluid / F1 (sessions/s) | mu(cap) fresh | release, two-phase fluid / F1 (s) | release, B stationary / B single-queue adjusted / phase-1 collapsed (s) | phase-1 rate needed for release by 7200 s | P(relapse) after release |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for m, x in P["tests"][t]["result"].items():
            tp, ta, col = x["two_phase"], x["two_phase_annealed"], x["phase1_collapsed"]
            adj = x["adjusted"]
            L.append(f"| {m} x | {x['n_on']:.0f} | {x['cycle_on']:.0f} | {x['footprint_inflation']:.2f} | {x['mu_phase1_fluid']:.3f} / {x['mu_phase1_annealed']:.3f} | "
                     f"{x['mu_cap_fresh']:.3f} | {f(tp.get('t_release'), 0)} / {f(ta.get('t_release'), 0)} | "
                     f"{x['stationary']['t_release']:.0f} / {f(adj.get('t_release'), 0) if adj.get('drains') else 'never'} / "
                     f"{f(col.get('t_release'), 0)} | {x['mu_phase1_needed_for_deadline']:.3f} ({x['mu_phase1_needed_over_fluid']:.2f} of fluid) | "
                     f"{f(tp.get('p_relapse'), 3)} |")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    out = ["# Merged theory: generated summary", "", "## Selection scores (approach A vs approach B, the three measured cells)", "",
           selection_scores(), "## Blind predictions: cells", "", blind_table(), "## Blind predictions: registered tests", "", tests_table()]
    p = os.path.join(RES, "summary.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
