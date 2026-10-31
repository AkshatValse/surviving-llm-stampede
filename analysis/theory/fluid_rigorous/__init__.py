"""Fluid / mean-field model of prefix-cached multi-turn agent serving (round 13, approach B).

Modules
-------
model     -- workload, calibrated cost model, stationary fluid server, LRU memory balance,
             the closed-system solution curve (good branch, fold, all-miss branch) and the
             quasi-static open system (equilibria, basin boundary, critical burst, rescue).
cells     -- the measured validation cells and their independent inputs (read-only).
edge      -- finite-size heuristic for the from-empty edge (Poisson session process, no fitting).
trapped   -- trapped-state predictions (token rate, gap/R) and the loopvars-style measurement.
run_all   -- produces results/theory/fluid_rigorous/* and figures/theory/fluid_rigorous_*.

Pure NumPy/SciPy. No randomness except in ``edge`` (seeded).
"""
