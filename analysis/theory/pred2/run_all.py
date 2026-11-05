"""Run every pred2 driver, then collect configs/r13_theory_pred2.yaml.

    PYTHONPATH="src;." python -m analysis.theory.pred2.run_all        # about 10 minutes on the PC

Deterministic: fixed grids, the exact client plans of fixed seeds, and fixed synthetic seeds (1000-1399).
"""
from __future__ import annotations

import time

from . import b2, blind_tables, e0f, freeze_table, h200_n2, prop_e, shed, toolslow


def main() -> None:
    for mod in (b2, h200_n2, toolslow, shed, e0f, prop_e, blind_tables):
        t = time.time()
        mod.main()
        print(f"  {mod.__name__}: {time.time() - t:.0f} s", flush=True)
    freeze_table.main()


if __name__ == "__main__":
    main()
