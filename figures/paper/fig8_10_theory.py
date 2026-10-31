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


def main():
    T.save = save
    T.write_csv = lambda *a, **k: None
    T.style(plt)
    T.fig_mu_validation(plt)  # the order of analysis/theory/paper/figs.py main()
    T.fig_fixed_points(plt)
    T.fig_scaling(plt)


if __name__ == "__main__":
    main()
