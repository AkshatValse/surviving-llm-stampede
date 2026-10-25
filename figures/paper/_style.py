"""Shared style, palette and input guard for the paper figures (figures/paper/fig*.py).

Rules enforced here, so every figure script follows them the same way:

* Inputs: ``src(relpath)`` returns the absolute path of a file and refuses it unless git tracks it and it has no
  uncommitted modification. A figure therefore cannot silently read an untracked scratch file. Every read is
  recorded; ``FIG_SOURCES=1`` makes ``finish()`` print the list (used to write paper/figs/README.md).
* Output: ``save(fig, name)`` writes a vector PDF to paper/figs/<name>.pdf (fonts embedded as TrueType).
* Style: one colorblind-safe palette (Okabe-Ito), the same colour for the same arm / policy / state in every
  figure, 8-9 pt text at final size, single column 3.4 in, double column 7.0 in.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Set

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "paper" / "figs"

# --------------------------------------------------------------------------- sizes (inches)
COL1 = 3.4
COL2 = 7.0

# --------------------------------------------------------------------------- palette (Okabe-Ito)
BLACK = "#000000"
ORANGE = "#E69F00"
SKY = "#56B4E9"
GREEN = "#009E73"
YELLOW = "#F0E442"
BLUE = "#0072B2"
VERM = "#D55E00"
PURPLE = "#CC79A7"
GRAY = "#7F7F7F"
LGRAY = "#BDBDBD"
DARK = "#222222"

# arms of the paired kill test (F1, and wherever an arm is named)
ARM_COLOR = {"burst": VERM, "noburst": BLUE, "capped": GREEN}
ARM_LABEL = {"burst": "BURST", "noburst": "NOBURST", "capped": "CAPPED"}

# policies / mechanisms (F2, F4, F6). A static session cap IS the CAPPED arm's mechanism: same green.
POLICY_COLOR = {"fcfs": DARK, "lpm": PURPLE, "peek": ORANGE, "continuum": SKY, "concur": "#B59B00", "cap": GREEN}

# per-run states of the trap analysis (F6). Trapped = the BURST colour, recovered = the CAPPED colour.
STATE_COLOR = {"trapped": VERM, "indeterminate": LGRAY, "draining": SKY, "recovered": GREEN}
STATE_LABEL = {"trapped": "trapped", "indeterminate": "indeterminate", "draining": "draining", "recovered": "recovered"}

# real engine vs simulator (F2, F3): real = black, filled; simulator = gray, open, dashed
REAL = DARK
SIM = GRAY


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8.5,
        "axes.titlesize": 9,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.borderaxespad": 0.2,
        "legend.labelspacing": 0.25,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "lines.linewidth": 1.1,
        "lines.markersize": 3.6,
        "axes.grid": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,       # embed TrueType, text stays text
        "ps.fonttype": 42,
        "pdf.compression": 6,
        "figure.constrained_layout.use": False,
    })


apply_style()

# --------------------------------------------------------------------------- guarded input
_READ: List[str] = []
_tracked: Set[str] | None = None
_modified: Set[str] | None = None


def _git_set(*args: str) -> Set[str]:
    out = subprocess.run(["git", "-C", str(ROOT), *args, "-z"], check=True, capture_output=True).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


def src(rel: str) -> Path:
    """Absolute path of ``rel`` (relative to the repo root) after checking that git tracks it unmodified."""
    global _tracked, _modified
    rel = rel.replace("\\", "/")
    if _tracked is None:
        _tracked = _git_set("ls-files")
        _modified = _git_set("ls-files", "-m")
    if rel not in _tracked:
        raise FileNotFoundError(f"{rel}: not tracked by git (figures read committed files only)")
    if rel in _modified:  # type: ignore[operator]
        raise RuntimeError(f"{rel}: has uncommitted modifications")
    p = ROOT / rel
    if not p.is_file():
        raise FileNotFoundError(f"{rel}: tracked but missing in the working tree")
    if rel not in _READ:
        _READ.append(rel)
    return p


# --------------------------------------------------------------------------- output
def save(fig: plt.Figure, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"{name}.pdf"
    fig.savefig(p, format="pdf", metadata={"CreationDate": None, "Creator": "matplotlib", "Producer": "matplotlib"})  # no timestamp: rebuilds are byte-identical
    plt.close(fig)
    return p


def panel_label(ax, text: str, dx: float = -0.02, dy: float = 1.04, **kw) -> None:
    ax.text(dx, dy, text, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right", **kw)


def finish(name: str) -> None:
    print(f"wrote {OUT_DIR / (name + '.pdf')}")
    if os.environ.get("FIG_SOURCES"):
        print(f"SOURCES {name} ({len(_READ)} files)")
        for r in _READ:
            print("  " + r)


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return c - h, c + h


def add_repo_paths() -> None:
    """Make ``analysis`` and ``agentload`` importable (PYTHONPATH='src;.' does the same)."""
    for p in (str(ROOT), str(ROOT / "src")):
        if p not in sys.path:
            sys.path.insert(0, p)


def t_half_width(sd: float, n: int, conf: float = 0.95) -> float:
    """Two-sided Student-t half-width of a mean from ``n`` values with sample sd ``sd``."""
    from scipy import stats
    if n < 2:
        return float("nan")
    return float(stats.t.ppf(0.5 + conf / 2, n - 1) * sd / n ** 0.5)
