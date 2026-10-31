r"""Figures for notes/PAPER_INPUT_theory.md (round-13 theory, written after the freeze tag r13-theory-pred).

    PYTHONPATH="src;." python -m analysis.theory.paper.figs

Writes figures/theory/paper_{mu_validation,fixed_points,scaling}.{pdf,png} and the plotted data under results/theory/paper/.

* paper_mu_validation: predicted mu(n) (fluid and the F1 annealed curve, read from the frozen JSONs) against the measured
  Stage C points (sessions/s and turns-based) for the three measured cells.  Inputs of the prediction: pool, workload,
  server-log cost model (vLLM: plus one speed factor fitted to its own E0a token rate).  No measured mu(n) point is used.
* paper_fixed_points: (a) the open-system phase line dn/dt = lambda - mu(n) of the predicted 300k curve at 1.65 lambda_ref,
  with the stable good state n1, the basin boundary n_u, the all-miss onset n_b and the trap (n -> infinity at
  lambda - mu_b); (b) the closed-system feedback map Phi_n(h) at n = 33.5 > n_b for the registered exponential tool times
  (one stationary state, all-miss) and for the two-phase mixture 0.5 Exp(1 s) + 0.5 Exp(9 s) of the same mean (three:
  all-miss and good both stable, one unstable), the case Proposition F predicts; (c) the closed curves mu(n) of the two laws,
  showing the fold of the mixture above n_b.
* paper_scaling: the window omega = mu_max / mu_b of the frozen model as a function of s * zbar (Theorem T8(a): GPU speed s
  and mean tool time zbar enter only through their product) and of the pool M, with the measured A100 windows and the
  frozen blind predictions (H200; pools 150k and 600k) marked.  Blind outcomes are NOT plotted (none was read).
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import replace

import numpy as np

from ..fluid_rigorous.cells import measured
from ..fluid_rigorous.model import Model, fixed_points, feedback_map, open_equilibria, summarize_curve
from ..merged import fold as F
from ..merged.spec import ROOT, build, load_spec

RES = os.path.join(ROOT, "results", "theory", "merged")
OUT = os.path.join(ROOT, "results", "theory", "paper")
FIG = os.path.join(ROOT, "figures", "theory")
CELLS = os.path.join(ROOT, "analysis", "theory", "cells")
TITLES = {"a100_300k": "SGLang, A100, 300k-token pool", "a100_native": "SGLang, A100, native pool (955,757)",
          "vllm_300k": "vLLM 0.32, A100, 300k pool"}
MIX = ((0.5, 1.0), (0.5, 9.0))        # two-phase tool-time law, mean 5 s, CV 1.5 (Proposition F example)


def load(name):
    with open(os.path.join(RES, f"{name}.json")) as f:
        return json.load(f)


def model(name):
    m, _, _ = build(load_spec(os.path.join(CELLS, f"{name}.yaml")))
    return m


def write_csv(name, header, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def style(plt):
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 6.5,
                         "pdf.fonttype": 42, "ps.fonttype": 42})


COL = dict(fl="#1f4e79", an="#6a9fc4", ms="#b03a2e", mt="#e67e22", grey="#666666", mix="#7d3c98", ok="#2e7d32")


def fig_mu_validation(plt):
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.5))
    rows = []
    for j, c in enumerate(("a100_300k", "a100_native", "vllm_300k")):
        P, me = load(c), measured(c)
        cv = P["closed_curve"]["curve"]
        nb = P["all_miss"]["n_b"]
        a = ax[j]
        a.plot(cv["n"], cv["mu_fluid"], color=COL["fl"], lw=1.3, label="predicted, fluid")
        a.plot(cv["n"], cv["mu_annealed"], color=COL["an"], lw=1.0, ls="--", label="predicted, F1 (demand fluctuation)")
        keep = me.n < 300          # n = 300 is a synchronized-start transient (not a stationary point)
        a.plot(me.n[keep], me.mu_sessions[keep], "o", ms=3.4, color=COL["ms"], label="measured, sessions/s")
        a.plot(me.n[keep], me.mu_turns[keep], "s", ms=3.0, mfc="none", color=COL["mt"], label="measured, turns-based")
        a.axvline(nb, color=COL["grey"], lw=0.6, ls=":")
        a.text(nb, a.get_ylim()[1] * 0.97 if j else 0.255, r" $n_b$", fontsize=6.5, va="top", color=COL["grey"])
        a.axhline(me.lam_ref, color=COL["grey"], lw=0.6, ls="-.")
        a.set_xlim(0, min(3.2 * nb, 140) if c != "a100_native" else 135)
        a.set_ylim(0, None)
        a.set_title(TITLES[c])
        a.set_xlabel("closed population $n$")
        if j == 0:
            a.set_ylabel(r"$\mu(n)$ (sessions/s)")
        for n, mf, ma in zip(cv["n"], cv["mu_fluid"], cv["mu_annealed"]):
            rows.append((c, "predicted", n, mf, ma, "", ""))
        for n, s, t in zip(me.n, me.mu_sessions, me.mu_turns):
            rows.append((c, "measured", n, "", "", s, t))
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    save(fig, "paper_mu_validation")
    write_csv("mu_validation.csv", ["cell", "kind", "n", "mu_fluid", "mu_F1", "mu_sessions_meas", "mu_turns_meas"], rows)


def fig_fixed_points(plt):
    m = model("a100_300k")
    cs = summarize_curve(m)
    P = load("a100_300k")
    lam_ref = 0.071534
    lam = 1.65 * lam_ref
    oe = open_equilibria(cs, lam)
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.45))
    # (a) open-system phase line on the predicted curve
    a = ax[0]
    cv = P["closed_curve"]["curve"]
    n = np.asarray(cv["n"])
    mu = np.asarray(cv["mu_fluid"])
    a.plot(n, mu, color=COL["fl"], lw=1.3, label=r"predicted $\mu(n)$")
    a.axhline(lam, color=COL["ms"], lw=1.0, label=r"$\lambda=1.65\,\lambda_{ref}$")
    a.axhline(cs.mu_b, color=COL["grey"], lw=0.6, ls="-.")
    a.text(52, cs.mu_b + 0.004, r"$\mu_b$", fontsize=6.5, color=COL["grey"])
    for x, lab, mk in ((oe.n1, r"$n_1$", "o"), (oe.n_u, r"$n_u$", "o"), (cs.n_b, r"$n_b$", "|")):
        a.plot([x], [lam if mk == "o" else cs.mu_b], mk, color="k", ms=5, mfc="k" if lab == r"$n_1$" else "white")
        a.text(x, (lam if mk == "o" else cs.mu_b) - 0.022, lab, ha="center", fontsize=7)
    y0 = 0.006
    for x0, x1 in ((1.0, oe.n1 - 1.2), (oe.n_u - 1.0, oe.n1 + 1.2), (oe.n_u + 1.0, 58.0)):
        a.annotate("", xy=(x1, y0), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", color=COL["ok"] if x1 < 40 else COL["ms"], lw=1.0))
    a.text(44, 0.016, "trap:\n" + r"$\dot n=\lambda-\mu_b$", fontsize=6, color=COL["ms"], ha="center")
    a.set_xlim(0, 60)
    a.set_ylim(0, 0.27)
    a.set_xlabel("sessions in system $n$")
    a.set_ylabel("sessions/s")
    a.set_title("(a) open system, 300k pool")
    a.legend(frameon=False, loc="upper right", fontsize=6)
    # (b) closed-system feedback map at n = 33.5 > n_b
    b = ax[1]
    mm = F.mixture(m, MIX)
    n_fp = 33.5
    hs = np.linspace(0.0, 0.93, 187)
    rows = []
    for lab, mod, col in (("exponential (registered)", m, COL["fl"]), ("two-phase, CV 1.5", mm, COL["mix"])):
        ph = [feedback_map(mod, n_fp, float(x))["phi"] for x in hs]
        b.plot(hs, ph, color=col, lw=1.2, label=lab)
        for x, y in zip(hs, ph):
            rows.append(("feedback_map", lab, n_fp, x, y))
        for fp in fixed_points(mod, n_fp, ngrid=401):
            b.plot([fp["h"]], [fp["h"]], "o", color=col, ms=4.5, mfc=col if fp["stable"] else "white")
            rows.append(("fixed_point", lab, n_fp, fp["h"], fp["slope"]))
    b.plot([0, 0.93], [0, 0.93], color=COL["grey"], lw=0.6, ls=":")
    b.set_xlabel("trial follow-up hit probability $h$")
    b.set_ylabel(r"$\Phi_n(h)$")
    b.set_title(r"(b) closed system, $n=33.5>n_b=32.7$")
    b.legend(frameon=False, loc="upper left", fontsize=6)
    b.text(0.55, 0.08, "filled: stable\nopen: unstable", fontsize=6)
    # (c) closed curves of the two laws (W = 0 branch parametrised by R, then the all-miss branch)
    c = ax[2]
    for lab, mod, col in (("exponential", m, COL["fl"]), ("two-phase, CV 1.5", mm, COL["mix"])):
        s = summarize_curve(mod)
        pts = sorted(s.pts, key=lambda p: -p["R"])
        c.plot([p["n"] for p in pts] + [s.n_b, 60], [p["mu"] for p in pts] + [s.mu_b, s.mu_b], color=col, lw=1.2, label=lab)
        for p in pts:
            rows.append(("closed_curve", lab, p["n"], p["R"], p["mu"]))
    fb = F.fold_band(mm)
    c.axvspan(fb["n_b"], fb["n_fold"], color=COL["mix"], alpha=0.15, lw=0)
    c.text(fb["n_fold"] + 0.6, 0.20, "bistable\nband", fontsize=6, color=COL["mix"])
    c.set_xlim(0, 45)
    c.set_ylim(0, 0.27)
    c.set_xlabel("closed population $n$")
    c.set_title("(c) closed curves")
    c.legend(frameon=False, loc="lower left", fontsize=6)
    fig.tight_layout()
    save(fig, "paper_fixed_points")
    rows.append(("open_equilibria", "300k 1.65x", lam, oe.n1, oe.n_u))
    rows.append(("fold_band", "two-phase CV 1.5", fb["n_b"], fb["n_fold"], fb["band_width"]))
    write_csv("fixed_points.csv", ["what", "law", "x", "y", "z"], rows)


def fig_scaling(plt):
    base = model("a100_300k")
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.5))
    a = ax[0]
    sz = np.geomspace(1.0, 60.0, 30)
    om = []
    for x in sz:
        mm = Model(replace(base.wl, zbar=float(x)), base.cost, base.M)
        s = summarize_curve(mm)
        om.append(s.mu_max / s.mu_b)
        rows.append(("s_zbar", x, base.M, s.mu_max / s.mu_b))
    a.plot(sz, om, color=COL["fl"], lw=1.3, label=r"model $\omega(\mathcal{C},s\bar z)$, 300k pool")
    me = measured("a100_300k")
    a.plot([5.0], [me.window_turns], "s", color=COL["mt"], mfc="none", ms=4.5, label="A100 measured (turns-based)")
    a.plot([5.0], [me.window_sessions], "o", color=COL["ms"], ms=3.5, label="A100 measured (sessions/s)")
    H = load("h200_300k")
    sH = H["window"]["speed_factor_vs_a100"]
    a.plot([sH * 5.0], [H["window"]["model_units"]], "D", color=COL["mix"], mfc="none", ms=5,
           label=f"H200 frozen prediction ($s$={sH:.3f})")
    a.set_xscale("log")
    a.set_xlabel(r"$s\,\bar z$ (s): mean tool time in A100-equivalent seconds")
    a.set_ylabel(r"peak ratio $\omega=\mu_{\max}/\mu_b$")
    a.axhline(1.0, color=COL["grey"], lw=0.6, ls=":")
    a.legend(frameon=False, fontsize=6, loc="upper right")
    a.set_title("(a) speed and tool time enter only as $s\\bar z$")
    b = ax[1]
    Ms = np.geomspace(1.0e5, 1.2e6, 24)
    om2, nb2 = [], []
    for M in Ms:
        s = summarize_curve(Model(base.wl, base.cost, float(M)))
        om2.append(s.mu_max / s.mu_b)
        nb2.append(s.n_b)
        rows.append(("pool", 5.0, M, s.mu_max / s.mu_b))
    b.plot(Ms / 1e3, om2, color=COL["fl"], lw=1.3, label="model, A100 costs, $\\bar z$ = 5 s")
    mn = measured("a100_native")
    b.plot([300, 955.757], [me.window_turns, mn.window_turns], "s", color=COL["mt"], mfc="none", ms=4.5, label="measured (turns-based)")
    for nm in ("a100_pool150k", "a100_pool600k"):
        Q = load(nm)
        b.plot([Q["all_miss"]["threshold"]["pool_part"] * Q["all_miss"]["threshold"]["E_S"] / 1e3], [Q["window"]["model_units"]],
               "D", color=COL["mix"], mfc="none", ms=5, label="pool sweep frozen prediction" if "150" in nm else None)
    b.set_xscale("log")
    b.set_xlabel("KV pool $M$ (thousand tokens)")
    b.set_ylabel(r"peak ratio $\omega$")
    b.legend(frameon=False, fontsize=6)
    b.set_title("(b) peak ratio against pool size")
    fig.tight_layout()
    save(fig, "paper_scaling")
    write_csv("scaling.csv", ["sweep", "s_zbar_s", "M_tokens", "omega_fluid_model_units"], rows)


def save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), dpi=220)
    import matplotlib.pyplot as plt
    plt.close(fig)
    print("written", os.path.join(FIG, f"{name}.pdf"))


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    fig_mu_validation(plt)
    fig_fixed_points(plt)
    fig_scaling(plt)


if __name__ == "__main__":
    main()
