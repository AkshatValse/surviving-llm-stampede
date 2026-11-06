# Blind recompute of the r16 MIRROR measures (independent code; do not import analysis/r16_mirror.py)

You are checking a registered scoring script by recomputing its measures from the raw run files with your own code.

Inputs (read-only):
- The run directories listed in RUNS below, each with `sessions.csv`, `plan.csv`, `meta.json`, `config_effective.yaml` and `requests.csv`.
- Frozen predictions: `results/theory/r16/mirror_predictions.json` in the worktree
  `C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\mirror`.

Definitions (implement them yourself from these words):
- lambda_ref = 0.07153402100919228 sessions/s. Report rates in units of lambda_ref.
- Completion rate over [a, b): the number of sessions with status `completed` and `t_end` in [a, b), divided by (b - a).
- Windows: BLACKOUT [2400, 3600), LATE [6600, 8700).
- WAVE TIME: the median `t_end` of the sessions with origin `burst` and status `completed` and `t_end` <= 8700. If fewer
  than 100 such sessions exist, it is undefined.
- Backlog N(t) = the sessions that arrived (`arrival_s` <= t) and have not ended. A session ends at `t_end` if its status is
  `completed` or `failed`; otherwise it ends at the run end. Sample N at 1-s steps on [0, 8700) (count at each integer t),
  average over 10-s bins, and fit an OLS line to the bin means against the bin centres over [6000, 8700).
- lambda_plan = the base arrivals (origin `base`) in `plan.csv` with arrival_s in [6000, 8700), divided by 2700.
- Quasi-static slope S_QS = lambda_plan - 0.07483084 /s (the model all-miss capacity); S_F = the frozen
  `cells.<mult>.seeds.<seed>.windows.slope.slope`; F_wave = `...burst_timing.median`.
- Rules:
  - M1: blackout <= 0.30;
  - M2: |wave - F_wave| <= 0.15 (F_wave - 1200);
  - M3: late <= 0.85;
  - M4: |S - S_F| < |S - S_QS|.
- Also report, per run, completions per 300-s bin over [1200, 8700).
- STUCK: from `requests.csv`, take the successful requests (turns) whose completion time is in the window, and compute
  the hit fraction two ways: the share of turns with cached tokens > 0, and the token-weighted cached share (cached
  prompt tokens / prompt tokens). Use both windows [4500, 8700] and [5700, 8700]. The registered rule is: STUCK iff the
  hit fraction is below 0.2. The metric is the one `configs/agentload_analysis.yaml` selects (`windows.hit_metric`; read
  only that config value, not the code). Report all four numbers per run, and flag any run where the windows or metrics
  disagree about STUCK.
- Seed call per BURST run: RENEWAL iff STUCK and M1-M4 all hold; CURVE iff blackout >= 0.85 and late >= 0.85; NOT-TRAPPED
  iff not STUCK; otherwise MIXED. Cell verdict per rate: PASS iff RENEWAL in >= 2 of 3 seeds; FAIL iff CURVE in >= 2 of 3;
  NO-TRAP iff NOT-TRAPPED in >= 2 of 3; otherwise MIXED.
- NOBURST runs: report blackout, late, the hit fractions and the backlog slope only (no rules).
- Independence: do not read the code of `analysis/r16_mirror.py`, `analysis/r15_cut.py`, `analysis/basin.py`,
  `analysis/trap_v2.py`, `analysis/throughput.py` or `analysis/theory/icml/measured.py`. Compute everything first; read
  the registered script's `mirror_runs.csv` and `mirror_verdict.json` only for the final comparison.

Output: a table per run (label, arm, rate_mult, seed, blackout, late, wave, n burst completed, slope, lambda_plan, M1-M4),
and a list of every disagreement with the registered script's `mirror_runs.csv`. A disagreement is any difference above
1e-9 relative, or any different boolean. Do not edit any file outside your own scratch directory.
