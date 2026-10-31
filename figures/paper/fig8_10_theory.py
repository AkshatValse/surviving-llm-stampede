"""F8-F10: the three first-principles-model figures, written into paper/figs/ for the paper.

    PYTHONPATH="src;." python figures/paper/fig8_10_theory.py

Draws with the functions of analysis/theory/paper/figs.py (fig_mu_validation, fig_scaling, fig_fixed_points; commit 5271ff6
plus the 2026-10-31 label edit, which changed no plotted value) and saves them as
  paper/figs/fig8_theory_curves.pdf        (= figures/theory/paper_mu_validation.pdf; Fig. fig:fpmu, Section 4)
  paper/figs/fig9_theory_scaling.pdf       (= figures/theory/paper_scaling.pdf;       Fig. fig:fpscale, Section 7)
  paper/figs/fig10_theory_fixed_points.pdf (= figures/theory/paper_fixed_points.pdf;  Fig. fig:fixed, Appendix F)
The PDFs carry no creation date, so a rebuild is byte-identical. Nothing else is written: the data CSVs under
results/theory/paper/ are left as committed (the functions' CSV writes are skipped here), and figures/theory/ is not touched.
The plotted values come from the frozen JSONs at tag r13-theory-pred (results/theory/merged/) and the measured Stage C and
E0a files that analysis/theory/fluid_rigorous/cells.py reads; no outcome of a pending test is plotted.
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
            a.plot([x], [0.367218 / H200_LREF], "^", color=T.COL["mt"], mfc="none", ms=5,
                   label="H200 measured (turns-based; seen before the freeze)")
            a.plot([x], [0.386109 / H200_LREF], "v", color=T.COL["ms"], ms=4, label="H200 measured (sessions/s)")
            a.legend(frameon=False, fontsize=6, loc="upper right")
            # the paper writes omega_b = mu*/mu_b for Proposition 3's ratio (omega_ref = mu*/lambda_ref is the scored one)
            for ax_ in fig.axes[:2]:
                ax_.set_ylabel(ax_.get_ylabel().replace(r"$\omega=", r"$\omega_b=").replace(r"$\omega$", r"$\omega_b$"))
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
