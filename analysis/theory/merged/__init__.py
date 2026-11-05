"""Round-13 merged theory: one prediction code path (notes/THEORY_r13_merged.md).

Base model: the fluid / mean-field model of approach B (analysis/theory/fluid_rigorous, notes/THEORY_r13_fluid_rigorous.md),
chosen over approach A (analysis/theory/che_endogenous) because it has no judgment parameter (A's headroom eta), carries the
complete proofs, matches the closed curves as well as A, and scores better on the from-empty edges of all three measured
cells.  Grafted from approach A (and re-derived inside B's model, so every number below comes from one model):

* the closed-form all-miss threshold  n_b = nu_b zbar' + M / E_S  (A's R2), an exact identity of B's model;
* the Stage C synchronized-start transient at large n (A's closed_trap_transient, on B's costs): the measured mu(300);
* the good-state loopvars ratio gap/R from (median tool time + latency) x churn / M (A's R5b);
* the static CAPPED-arm drain time (A's capped_drain_from_t0) and the registration-consequence rule (A's predict_cell).

New in the merge (not in A or B):

* burst trapping probabilities from the committor (splitting probability) of B's own one-dimensional demand diffusion F2,
  so the from-empty edge and the burst basin use one fluctuation model;
* a two-phase drain for the registered pause-cap RESCUE gate (the resume deque is served before new arrivals): resumed
  mid-session sessions at the composition-adjusted rate, then fresh arrivals at mu(cap).

Modules: ``spec`` (cell spec YAML -> model and fitting audit), ``extras`` (the grafts and the new layers).  Entry points:
``python -m analysis.theory.predict SPEC.yaml`` and ``python -m analysis.theory.validate``.
"""
