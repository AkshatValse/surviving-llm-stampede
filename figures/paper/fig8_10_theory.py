"""F8-F10: the three first-principles-model figures, written into paper/figs/ for the paper.

    PYTHONPATH="src;." python figures/paper/fig8_10_theory.py

Draws with the functions of analysis/theory/paper/figs.py (fig_mu_validation, fig_scaling, fig_fixed_points; commit 5271ff6
plus the 2026-10-31 label edit, which changed no plotted value) and saves them as
  paper/figs/fig8_theory_curves.pdf        (= figures/theory/paper_mu_validation.pdf; Fig. fig:fpmu, Section 6)
  paper/figs/fig9_theory_scaling.pdf       (= figures/theory/paper_scaling.pdf;       Fig. fig:fpscale, Appendix H)
  paper/figs/fig10_theory_fixed_points.pdf (= figures/theory/paper_fixed_points.pdf;  Fig. fig:fixed, Appendix F)
The PDFs carry no creation date, so a rebuild is byte-identical. Nothing else is written: the data CSVs under
results/theory/paper/ are left as committed (the functions' CSV writes are skipped here), and figures/theory/ is not touched.
The plotted values come from the frozen JSONs at tag r13-theory-pred (results/theory/merged/) and the measured Stage C and
E0a files that analysis/theory/fluid_rigorous/cells.py reads; fill 3 adds to F9 (b) the measured pool-sweep and 600k H200 peak
ratios, the H200 model curve against the pool and the H200 frozen predictions at 300k and 600k. No outcome of a pending test is
plotted.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "src"), ROOT]

import matplotlib  # noqa: E402
import numpy as np  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis.theory.paper import figs as T  # noqa: E402

NAMES = {"paper_mu_validation": "fig8_theory_curves", "paper_scaling": "fig9_theory_scaling",
         "paper_fixed_points": "fig10_theory_fixed_points"}
OUT = os.path.join(ROOT, "paper", "figs")


def save(fig, name):
    path = os.path.join(OUT, NAMES[name] + ".pdf")
    fig.savefig(path, dpi=220, metadata={"CreationDate": None})
    plt.close(fig)
    print("written", os.path.relpath(path, ROOT))


# --- fix-up 1 of fill 2 (2026-10-31): F8 gets a fourth panel, the H200 frozen prediction against the measured H200 curve,
# and the serif style and logarithmic n axis of F2 (fig2_thrashing_curve.py: log x, ticks 16-128); F9 (a) also plots the
# measured H200 peak ratio. The frozen JSONs (tag r13-theory-pred) and the measured files are read as before; the H200
# measured curve is the 12-point Stage C analysis of the H200 cell (MU12 in paper/NUMBERS.md).
H200_MU = os.path.join(ROOT, "results", "nova", "h200_stageC_extra_1716961x_pulled_20261031-040933", "results",
                       "agentload_analysis_closed_supp12", "20261031-040909", "mu_curve.csv")
H200_LREF = 0.193877          # H200 E0a turns-based lambda_ref (CALH in paper/NUMBERS.md)
H200_SEEN = (16, 20, 24, 28, 32)   # closed-curve values seen by the first author before the freeze
H200_BLIND_TIME = (36, 44, 52)     # submitted after the freeze
TICKS = [16, 24, 32, 48, 64, 96]
# --- fill 3 (2026-10-31): F9 (b) also shows the measured A100 pool-sweep peak ratios (150k, 600k; blind in time), the model
# against the pool with the frozen H200 costs (spec h200_300k, s = 2.742), the H200 frozen predictions at 300k (r13-theory-pred)
# and 600k (pred2), and the measured H200 peak ratios at 300k (seen before the freeze) and 600k (blind in time); turns-based.
POOL_SCORED = os.path.join(ROOT, "results", "nova", "pool_sweep_1716886x_pulled_20261031-112342", "derived",
                           "pool_sweep_scored.json")
H200_600K_MU = os.path.join(ROOT, "results", "nova", "h200p600k_stageC_e0b_171696xx_pulled_20261031-092822", "results",
                            "agentload_analysis_closed", "20261031-092435", "mu_curve.json")
H200_600K_PRED = os.path.join(ROOT, "results", "theory", "pred2", "h200_600k.json")


def pool_panel(b):
    """Add the fill-3 points and the H200 curve to panel (b) of the scaling figure."""
    import json
    from analysis.theory.fluid_rigorous.model import Model, summarize_curve
    C = T.COL
    for ln in b.get_lines():
        if ln.get_label() == "measured (turns-based)":
            ln.set_label("A100 measured, in sample (turns-based)")
        elif ln.get_marker() == "D":   # the two pool-sweep predictions (only the 150k one carries a label)
            ln.set_markersize(6)       # all diamonds of (b) at one size
            if ln.get_label() == "pool sweep frozen prediction":
                ln.set_label("A100 pool sweep, frozen prediction")
    with open(POOL_SCORED) as f:
        Q = json.load(f)["cells"]
    # filled squares under the open diamonds (zorder 1.9 < 2), so the 600k prediction stays visible over its outcome
    b.plot([150, 600], [Q["150k"]["measured"]["peak_ratio_turns"], Q["600k"]["measured"]["peak_ratio_turns"]], "s",
           color=C["mt"], ms=4.5, zorder=1.9, label="A100 measured, blind in time (turns-based)")
    Hm = T.model("h200_300k")
    Ms = np.geomspace(1.0e5, 1.2e6, 24)
    om = []
    for M in Ms:
        s = summarize_curve(Model(Hm.wl, Hm.cost, float(M)))
        om.append(s.mu_max / s.mu_b)
    b.plot(Ms / 1e3, om, color=C["ok"], lw=1.0, ls="--", label="model, H200 costs ($s$ = 2.742)")
    with open(H200_600K_PRED) as f:
        p600 = json.load(f)["window"]["model_units"]
    p300 = T.load("h200_300k")["window"]["model_units"]
    s6 = summarize_curve(Model(Hm.wl, Hm.cost, 6.0e5))
    print("check: H200 model at 600k %.4f, pred2 h200_600k %.4f" % (s6.mu_max / s6.mu_b, p600))
    # at 300k the H200 prediction (1.918) and measurement (1.894) nearly coincide: the diamonds have a white face (hiding the
    # dashed curve inside them) and the smaller triangles are drawn on top, so the open triangle shows inside its diamond
    b.plot([300, 600], [p300, p600], "D", color=C["ok"], mfc="white", ms=6, zorder=2.1, label="H200 frozen prediction")
    with open(H200_600K_MU) as f:
        cell = json.load(f)["cells"]["sglang-fcfs-r1-h200-p600k"]
    m600 = max(m for n, m in zip(cell["n"], cell["mu_turns_based"]) if n < 300)
    b.plot([300], [0.367218 / H200_LREF], "^", color=C["ok"], mfc="none", ms=3.4, zorder=2.2,
           label="H200 measured, seen before the freeze")
    b.plot([600], [m600 / H200_LREF], "^", color=C["ok"], ms=3.4, zorder=2.2, label="H200 measured, blind in time")
    # legend order per GPU: measured (in sample or seen, then blind in time), model, frozen prediction; the longer labels sit
    # in the upper rows, where the A100 curve is farthest right, so no label crosses a curve
    hs = dict(zip(*b.get_legend_handles_labels()[::-1]))
    order = ["A100 measured, in sample (turns-based)", "A100 measured, blind in time (turns-based)",
             "model, A100 costs, $\\bar z$ = 5 s", "A100 pool sweep, frozen prediction",
             "H200 measured, seen before the freeze", "H200 measured, blind in time",
             "model, H200 costs ($s$ = 2.742)", "H200 frozen prediction"]
    assert sorted(order) == sorted(hs), sorted(hs)
    b.legend([hs[k] for k in order], order, frameon=False, fontsize=5.5, loc="upper left", labelspacing=0.35,
             handlelength=1.6)


def fig_mu_validation_4(plt):
    import csv
    from figures.paper import _style as S  # noqa: F401  (applies the serif style of F1-F7)
    C = T.COL
    fig, ax = plt.subplots(1, 4, figsize=(7.0, 2.45))
    cells = ("a100_300k", "a100_native", "vllm_300k", "h200_300k")
    titles = dict(T.TITLES)
    titles.update({"a100_300k": "SGLang, A100, 300k pool", "a100_native": "SGLang, A100, native pool",
                   "vllm_300k": "vLLM, A100, 300k pool", "h200_300k": "SGLang, H200, 300k pool (frozen)"})
    for j, c in enumerate(cells):
        P = T.load(c)
        cv = P["closed_curve"]["curve"]
        nb = P["all_miss"]["n_b"]
        a = ax[j]
        a.plot(cv["n"], cv["mu_fluid"], color=C["fl"], lw=1.2, label="predicted, fluid")
        a.plot(cv["n"], cv["mu_annealed"], color=C["an"], lw=0.9, ls="--", label="predicted, F1")
        if c != "h200_300k":
            me = T.measured(c)
            keep = me.n < 300
            ns, ms, mt, lref = me.n[keep], me.mu_sessions[keep], me.mu_turns[keep], me.lam_ref
        else:
            with open(H200_MU) as f:
                rows = [r for r in csv.DictReader(f) if float(r["n"]) < 300]
            ns = np.array([float(r["n"]) for r in rows])
            ms = np.array([float(r["mu_sessions"]) for r in rows])
            mt = np.array([float(r["mu_turns_based"]) for r in rows])
            lref = H200_LREF
            a.axvspan(11, 32.5, color="#BDBDBD", alpha=0.35, lw=0, zorder=0)
            a.text(13, 0.03, "seen before\nthe freeze", fontsize=6.5, color="#555555", va="bottom")
            bt = np.isin(ns, H200_BLIND_TIME)
            a.plot(ns[bt], mt[bt], "o", ms=7.0, mfc="none", mec="black", mew=0.7, zorder=5,
                   label="blind in time ($n$ = 36, 44, 52)")
        a.plot(ns, ms, "o", ms=3.2, color=C["ms"], label="measured, sessions/s", zorder=4)
        a.plot(ns, mt, "s", ms=2.8, mfc="none", color=C["mt"], label="measured, turns-based", zorder=4)
        a.axvline(nb, color=C["grey"], lw=0.6, ls=":")
        a.axhline(lref, color=C["grey"], lw=0.6, ls="-.")
        a.set_xscale("log")
        a.set_xlim(11, 140)
        a.set_xticks(TICKS)
        a.set_xticklabels([str(t) for t in TICKS])
        a.minorticks_off()
        a.set_ylim(0, None)
        a.text(nb * 1.03, a.get_ylim()[1] * 0.97, "$n_b$", fontsize=7, va="top", color=C["grey"])
        a.set_title(titles[c], fontsize=8)
        a.set_xlabel("closed population $n$")
        if j == 0:
            a.set_ylabel(r"$\mu(n)$ (sessions/s)")
    h, l = ax[0].get_legend_handles_labels()
    h3, l3 = ax[3].get_legend_handles_labels()
    h += [h3[l3.index("blind in time ($n$ = 36, 44, 52)")]]
    l += ["H200: blind in time ($n$ = 36, 44, 52)"]
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, fontsize=7)
    fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=0.6)
    save(fig, "paper_mu_validation")


def add_h200_measured_to_scaling():
    """Wrap T.save so that the scaling figure's panel (a) also shows the measured H200 peak ratio."""
    orig = T.save

    def save_with_h200(fig, name):
        if name == "paper_scaling":
            a = fig.axes[0]
            H = T.load("h200_300k")
            x = H["window"]["speed_factor_vs_a100"] * 5.0
            # fix round 2 of fill 3: the long label is split over two lines, so the legend (upper right) ends to the right of
            # the model curve and of the A100 markers (fontsize 5.5 as in (b); checked: no legend text or handle box meets a line
            # or marker)
            a.plot([x], [0.367218 / H200_LREF], "^", color=T.COL["mt"], mfc="none", ms=5,
                   label="H200 measured (turns-based;\nseen before the freeze)")
            a.plot([x], [0.386109 / H200_LREF], "v", color=T.COL["ms"], ms=4, label="H200 measured (sessions/s)")
            # the paper writes omega_b = mu*/mu_b for Proposition 3's ratio (omega_ref = mu*/lambda_ref is the scored one)
            for ln in a.get_lines():
                ln.set_label(ln.get_label().replace(r"$\omega(", r"$\omega_b("))
            a.legend(frameon=False, fontsize=5.5, loc="upper right", labelspacing=0.35, handlelength=1.6)
            for ax_ in fig.axes[:2]:
                ax_.set_ylabel(ax_.get_ylabel().replace(r"$\omega=", r"$\omega_b=").replace(r"$\omega$", r"$\omega_b$")
                               .replace(r"\mu_{\max}", r"\mu^*"))
            pool_panel(fig.axes[1])
        orig(fig, name)
    T.save = save_with_h200


def main():
    import matplotlib as mpl
    T.save = save
    T.write_csv = lambda *a, **k: None
    fig_mu_validation_4(plt)
    mpl.rcdefaults()
    T.style(plt)
    T.fig_fixed_points(plt)
    add_h200_measured_to_scaling()
    T.fig_scaling(plt)


if __name__ == "__main__":
    main()
