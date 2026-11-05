# r15 TOOLSLOW cells T1 and T2: frozen blind predictions (calibrated simulator and pred2)

Written 2026-11-05, about 01:30-02:40 CST, on branch `r15/tonight` (worktree base `8aaabdb` = `r10/arxiv`). No T1 or T2 run existed
anywhere when this file and its outputs were written, and no output of tonight's jobs was opened. Files read under `results/nova/`:
the six committed NOBURST `plan.csv` files that are the cells' CRN controls (plan check), and, for the retrodiction table in
section 3 only, the committed r14 d10 / d30 runs (pulled 2026-11-01) and the same six NOBURST control runs (pulled 2026-10-25).

**These predictions are blind in time only if this file and its outputs are committed and pushed before the first T1 or T2
job is submitted.** The freeze record at the end is for the lead to fill in at commit time.

- Simulator driver: `analysis/r15_sim_toolslow.py`. Output: `results/theory/r15/toolslow_sim.json` (every run, per-seed measures,
  the plan check, a sensitivity block and provenance).
- pred2 driver: `analysis/r15_pred2_toolslow.py`. Output: `results/theory/r15/toolslow_pred2.json`.
- Retrodiction measures on the r14 GPU runs: `results/theory/r15/toolslow_measured_r14.json`.
- Tests: `tests/test_r15_preds_toolslow.py` (7 tests, about 3 s).
- The three JSON files are git-ignored (`results/*`), so they need `git add -f`.

## Cells

| cell | label (registration agent's files) | rate | slowdown (client `workload.tool_slowdown`) | CRN controls (committed NOBURST, jobs 17093387-404) |
|---|---|---|---|---|
| **T1** | `sglang-fcfs-r1-toolslow-d30w1800`: `configs/agentload_e2_toolslow_d30w1800.yaml`, `configs/agentload_prereg_2026-11-05_toolslow_d30w1800.yaml` | 1.35 λ_ref = 0.096571 sessions/s | every tool call that **starts** in [1200, 3000) s lasts Z + 30 s | `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/` 20261024-155125 (s0), 20261024-161834 (s1), 20261024-211253 (s2) |
| **T2** | `sglang-fcfs-r1-toolslow-d15-165`: `configs/agentload_e2_toolslow_d15.yaml`, `configs/agentload_prereg_2026-11-05_toolslow_d15_165.yaml` | 1.65 λ_ref = 0.118031 sessions/s | every tool call that starts in [1200, 2100) s lasts Z + 15 s | same directory: 20261024-160218 (s0), 20261024-184259 (s1), 20261025-000053 (s2) |

Both cells: 300k pool, SGLang FCFS with waiting-prefix refresh, NOBURST arrivals, seeds 0-2, 8700-s runs, evaluation window
W = [5700, 8700) s. λ_ref = 0.07153402100919228 (registered, `prereg/inputs/2026-10-23/calibration.json`). The frozen endpoints are
those of `configs/r11_basin_predict.yaml`: STUCK := hit_eval < 0.2, GOOD := RECOVERED, or (hit_eval > 0.8 and backlog slope
≤ 0.5 (λ − λ_ref)). hit_eval is the all-turn hit (`frac_turns_cached_gt50`, first turns included, attributed by completion). The
registered rule for each cell is decided alone (`analysis/r15_cells.py`): TRAPS iff STUCK in ≥ 2 of 3 seeds; NO-TRAP iff GOOD
in ≥ 2 of 3; otherwise MIXED (also MIXED if both counts reach 2; a seed without a counted run counts against both).

## Headline (frozen)

| | **T1** (1.35×, +30 s on [1200, 3000)) | **T2** (1.65×, +15 s on [1200, 2100)) |
|---|---|---|
| Simulator, exact plans, `mixed` (**PRIMARY**) | STUCK / STUCK / STUCK → **TRAPS** | STUCK / GOOD / GOOD → **NO-TRAP** |
| Simulator, exact plans, `separate_prefill_priority` | STUCK / STUCK / STUCK → TRAPS | STUCK / GOOD / GOOD → NO-TRAP |
| Simulator, 20 random seeds (each mode) | 20 STUCK, 0 GOOD | 16 STUCK, 4 GOOD (for 3 random plans, P(TRAPS) = 0.90) |
| pred2 fluid verdict (**pred2's cell call**) | n(3000) = **69.8 > n_u = 32.2** → STUCK → **TRAPS** | n(2100) = **51.1 > n_u = 31.8** → STUCK → **TRAPS** |
| pred2 per-seed layer, P(STUCK) for s0 / s1 / s2 | 1.00 / 1.00 / 1.00 (X0 = 48 / 53 / 56) | **1.00 / 0.46 / 0.22** (X0 = 38 / 30 / 28); P(GOOD) 0.00 / 0.53 / 0.77 |
| pred2 per-seed layer, cell | modal S / S / S; P(TRAPS) = 1.00 | modal S / G / G (NO-TRAP); but P(TRAPS) = 0.58, P(NO-TRAP) = 0.41, P(MIXED) = 0.01 |

The scratch check run earlier tonight gave T1 STUCK and T2 STUCK with n = 51.1 > 31.8. This driver gives the same fluid
verdicts and the same n.

**Read this before using T2 as a model-discrimination cell.** The simulator and pred2 disagree on T2 seeds 1 and 2 only through
pred2's *fluid* verdict, which is one plan-averaged number applied to every seed. pred2's frozen *per-seed* layer starts the
committor at each exact plan's sessions alive at 2100 s. That is the method r13 used for its TOOLSLOW per-seed numbers. Under
that layer pred2's modal calls are S / G / G, the same as the simulator's, and seed 1 is close to even (P(GOOD) = 0.53).
The registrations' history text (`analysis/r15_prereg.py` `_HISTORY`, owned by the registration agent, as read at 02:35 CST)
names pred2's fluid verdict as the output that differs from the simulator's exact-plan runs, which is consistent with this.
The secondary score below keeps the two pred2 variants separate.

## 1. Simulator (calibrated round-6 engine, unchanged)

**Method.** The engine is configured exactly as in `configs/r11_predict_rescue.yaml`: the round-6 calibrated engine block
inherited from `configs/r6_predict.yaml` (checked equal at start), `kv_memory_tokens` 300000, `fcfs_lru`. The PRIMARY batching
mode is `mixed` and the SECONDARY mode is `separate_prefill_priority`. The run uses the registered `observe` controller, which
never engages and supplies the per-turn and 10-s tick records. The sessions are the exact client plans of seeds 0-2, rebuilt
with the client's own generator (`experiments/r11_predict_rescue.client_plan` on `configs/agentload_e2_burst.yaml` with
`arrivals.burst = null`). All six equal the committed NOBURST controls' `plan.csv`, with tool-time totals within 6e-16 relative
(the last bit of libm differs between Nova and this PC; `python -m analysis.r15_sim_toolslow plans`). The slowdown is a hook,
`ToolSlowEngine`, which subclasses the frozen `gate_control.GateEngine` and extends only `_finish_request`. When turn k < T of
a session completes at t inside the window, its tool time k is increased by the delay before the frozen method schedules the
tool return. The frozen `simulate_gate` is used unchanged, with its module-level `GateEngine` name bound to the subclass for
the duration of one call. Nothing under `src/` is edited. Without a slowdown the hook is bit-identical to the frozen engine
(`selfcheck`: summary, windows, queue/backlog traces, tick trace, completion records and session rows all match in both modes),
and with the d30 slowdown it lengthens exactly the 770 tool calls of seed 0 that start in [1200, 2100). The hook is a port of
the scratch driver `theory-pred/simdrv.py` (2026-11-04), toolslow hook only. The port reproduces that driver's saved outputs
(`c1_toolslow.json`) bit for bit: exact-plan hit_eval of 1.35/900/30, 1.35/1800/30 and 1.65/900/30 in both modes, and its
stuck/good counts on its seeds 200-219. The simulator side of the endpoints is the all-turn hit by completion time over W.
RECOVERED is the hit over the last 300 s > 0.8 and the mean outstanding (waiting + running + gate, tick samples) < 20. The
backlog slope is an OLS fit of the sessions in the system over the tick samples in W.

**Per seed, exact plans** (secondary and exploratory measures defined in section 4; slope threshold 0.01252 at 1.35× and 0.02325 at 1.65×):

| cell | mode | seed | state | hit_eval | backlog slope | outstanding, mean [2100, 2400) | outstanding at 3300 s | alive at 2100 s | alive at 3000 s | t_fu150 (s) | tool calls slowed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | mixed | 0 | **STUCK** | 0.0000 | 0.0191 | 11.3 | 57 | 49 | 57 | 1950 | 1594 |
| T1 | mixed | 1 | **STUCK** | 0.0000 | 0.0183 | 12.3 | 62 | 37 | 72 | 1950 | 1541 |
| T1 | mixed | 2 | **STUCK** | 0.0000 | 0.0246 | 14.4 | 70 | 39 | 76 | 2100 | 1713 |
| T1 | separate | 0 | STUCK | 0.0000 | 0.0191 | 12.5 | 66 | 49 | 55 | 1950 | 1629 |
| T1 | separate | 1 | STUCK | 0.0000 | 0.0191 | 12.8 | 67 | 37 | 69 | 1950 | 1583 |
| T1 | separate | 2 | STUCK | 0.0000 | 0.0253 | 13.8 | 58 | 39 | 74 | 2100 | 1752 |
| T2 | mixed | 0 | **STUCK** | 0.0000 | 0.0273 | 36.7 | 75 | 39 | 67 | 2100 | 1159 |
| T2 | mixed | 1 | **GOOD** | 0.9344 | 0.0010 | 4.0 | 0 | 30 | 11 | none | 1057 |
| T2 | mixed | 2 | **GOOD** | 0.9287 | 0.0001 | 5.7 | 2 | 29 | 8 | none | 1057 |
| T2 | separate | 0 | STUCK | 0.0000 | 0.0283 | 34.9 | 84 | 40 | 66 | 2100 | 1160 |
| T2 | separate | 1 | GOOD | 0.9344 | 0.0011 | 4.1 | 0 | 30 | 11 | none | 1052 |
| T2 | separate | 2 | GOOD | 0.9295 | 0.0002 | 4.8 | 2 | 28 | 8 | none | 1071 |

The T2 GOOD runs are GOOD by both clauses (RECOVERED and hit/slope). In T1 the outstanding count stays low until about 3000 s
because the sessions are parked in slowed tool calls; it jumps after the slowdown ends. Seed 0 in `mixed`, 150-s means: 1.5,
4.9, 9.9 over [1800, 2250), then 12.7-17.9 until 3000 s, then 49.9, 55.0, 61.7. The follow-up hit falls to 0.30 in [1950, 2100),
stays between 0.095 and 0.25 until 3000 s, is 0.06 in [3000, 3150), and is 0.00 from 3150 s.

**20 random simulator seeds per cell and mode** (`prefixmeta.workload.build_specs` seeds 0-19, the r11 convention; these are
independent plans, a band and not the GPU plans): T1 20/20 STUCK in both modes. T2 16 STUCK and 4 GOOD in both modes (GOOD seeds:
0, 7, 8, 14 in `mixed`; 0, 7, 8, 13 in separate). For three random plans that gives P(TRAPS) = 0.896. The three exact plans are
kinder than an average plan: seeds 1 and 2 have 30 and 29 sessions alive at 2100 s, while the random-seed median is 45.5.
Bands over the random seeds (min / median / max, `mixed`): T1 alive at 2100 s 37 / 46 / 58, at 3000 s 54 / 66 / 88, outstanding
[2100, 2400) 5.2 / 15.6 / 25.7. T2 alive at 2100 s 31 / 45.5 / 72, at 3000 s 10 / 74 / 105.

**Sensitivity of the exact-plan calls** (`sensitivity` block; these are **not predictions**, and the registered delay with the
calibrated engine stays the prediction). The calls are written s0 s1 s2, mixed | separate:

| varied input | T1 | T2 |
|---|---|---|
| add_s (at the cell's window and rate) | 15: SSG \| SSG; 20: SSS \| SSG; 25-60: SSS \| SSS | 10-18: SGG \| SGG; 20: SGS \| SGG; 25: SSS \| SSS |
| engine speed: every iteration cost × f, f = 0.85, 0.9, 1.1, 1.15 | SSS at every f, both modes | SGG at every f, both modes |

Both calls are therefore robust in the simulator. T1 traps at every delay of 25 s or more and at ±15% engine speed. T2's
split is set by the plans and not by fine tuning: seed 0 traps even at +10 s, and seeds 1 and 2 survive up to +18 s.

## 2. pred2 (the frozen r13 TOOLSLOW layer, unchanged)

**Method.** `analysis/theory/pred2/toolslow.py`, unchanged since tag `r13-theory-pred2` (`cfa7712`); the model is at
`r13-theory-pred` (`997d2c4`, `frozen_code_check.ok = true`). Its functions `Curve`, `slowed_model`, `fluid_verdict`,
`plan_population` and `stochastic` are called unchanged. The module hard-codes `MULT = 1.35` (line 40), and only `run()` reads
it; the driver never calls `run()`. Instead it computes λ = mult × λ_ref itself and builds the exact plans at the cell's rate
itself. `T_ON` and `T_OFF` are read at call time by `plan_population` and `stochastic`. A context manager sets these two module
constants to the cell's window for each cell and restores them afterwards, and `t_off` is passed to `fluid_verdict` explicitly.
The same driver reproduces the committed r13 rows for d10 and d30 (`results/theory/pred2/toolslow.json`) exactly: fluid n,
verdicts, exchangeable and band P(STUCK), and per-seed X0, lengthened calls and P(STUCK) all agree, with a maximum absolute
difference of 0.

| | T1 | T2 |
|---|---|---|
| λ (spec λ_ref 0.071534) | 0.096571 | 0.118031 |
| normal curve: n1, n_u, n_b, μ_max | 8.47, **32.23**, 32.70, 0.2478 | 10.43, **31.77**, 32.70, 0.2478 |
| slowed curve: μ_max (vs λ), good state | 0.0718 < λ: none (n_b 62.4) | 0.0912 < λ: none (n_b 47.5) |
| **fluid n at the slowdown's end** (t_off) vs n_u → verdict | **69.82 vs 32.23 → STUCK** (margin +37.6) | **51.12 vs 31.77 → STUCK** (margin +19.3) |
| n(8700) | 210.8 | 356.0 |
| band: switch at t_off + δ | 70.56 → STUCK | 51.81 → STUCK |
| sensitivity: exponential law of the same mean | 50.10 → STUCK | 35.09 → STUCK |
| critical δ at this (mult, window): fluid δ*, and δ at which the slowed peak equals λ | 14.46 s; 13.72 s | 11.29 s; 9.75 s |
| exchangeable stochastic layer (X0 = fluid n(t_off)) | P(STUCK) = 1.000 | P(STUCK) = 1.000 |
| per seed: X0 = the plan walk's sessions alive at t_off | 48 / 53 / 56 | 38 / 30 / 28 |
| per seed: committor q0 | 1.00 / 1.00 / 1.00 | 1.00 / 0.447 / 0.199 |
| per seed: P(STUCK) / P(GOOD) | 1.00/0.00, 1.00/0.00, 1.00/0.00 | 1.000/0.000, **0.462/0.532**, **0.220/0.770** |
| per-seed modal calls → cell | S / S / S → TRAPS (P = 1.000) | S / G / G → NO-TRAP; P(TRAPS) = 0.580, P(NO-TRAP) = 0.409, P(MIXED) = 0.010 |
| plan walk, alive at 2100 s / 3000 s (no queueing) | 49 / 37 / 39; 48 / 53 / 56 | 38 / 30 / 28; 12 / 11 / 8 |

The per-seed call is STUCK if P(STUCK) > 0.5, GOOD if P(GOOD) > 0.5, and NEITHER otherwise. P(TRAPS) and P(NO-TRAP) assume
independent seeds (`common.at_least`).

## 3. Retrodictions (not predictions)

**Caveat.** The simulator's tool-slowdown hook was written on 2026-11-04, after the r14 d10 / d30 GPU results were known. Every
d10, d30 and control row of the simulator is therefore post hoc: it shows that the hook and the plans reproduce known outcomes,
not that the simulator predicted them. pred2's d10 / d30 rows are different: they were blind in r13 (tag `r13-theory-pred2`,
pushed before the r14 jobs) and have since been scored.

| cell (GPU jobs) | GPU per seed | simulator, exact plans, mixed / separate | pred2 (blind in r13) |
|---|---|---|---|
| d10: 1.35×, +10 s on [1200, 2100) (17169902-04) | GOOD / GOOD / GOOD | GGG / GGG (3/3) | fluid GOOD (3/3); per seed P(GOOD) 0.71 each |
| d30: 1.35×, +30 s on [1200, 2100) (17169905-07) | GOOD / GOOD / STUCK | **GGS / GGS (3/3)** | fluid STUCK; per seed P(STUCK) = 1.00 each (1/3); the r14 rule (P = 0.80) failed |
| NOBURST 1.35× controls | GOOD × 3 | GGG / GGG | not applicable |
| NOBURST 1.65× controls | GOOD × 3 | GGG / GGG | not applicable |

Random seeds, as a band: d10 has 2/20 STUCK in both modes; d30 has 18/20 (mixed) and 17/20 (separate); the controls have
0/20 at either rate. d30's exact plans are kinder than an average plan, as T2's are.

The exploratory measures on the same GPU runs (`python -m analysis.r15_sim_toolslow measure`, frozen analysis helpers) are
compared with the simulator (`mixed`) below. They show the accuracy to expect in section 4; all of these are also post hoc.

| run | alive at 2100 s, GPU / sim | alive at 3000 s | outstanding [2100, 2400) | outstanding at 3300 s | t_fu150 |
|---|---|---|---|---|---|
| d10 s0 / s1 / s2 | 22/22, 15/15, 15/15 | 9/9, 14/14, 10/10 | 2.9/2.4, 2.3/1.7, 3.0/2.4 | 1/2, 0/0, 0/0 | none / none (all) |
| d30 s0 / s1 / s2 | 49/49, 38/37, 39/39 | 9/9, 14/14, 62/66 | 19.0/17.6, 24.4/30.1, 33.8/35.5 | 1/2, 0/0, 51/56 | 1950/1950, 1950/1950, 2100/2100 |
| ctl 1.35× s0 / s1 / s2 | 7/7, 7/7, 4/4 | 9/9, 14/14, 10/10 | 1.7/1.7, 1.6/1.3, 2.6/2.2 | 2/2, 0/0, 0/0 | none |
| ctl 1.65× s0 / s1 / s2 | 17/17, 9/9, 2/2 | 12/12, 11/11, 8/8 | 3.7/3.0, 2.2/2.1, 2.9/2.6 | 8/7, 1/0, 2/2 | none |

**T1 equals the r14 d30 cell until 2100 s**: same plans, rate, delay and start; only the window is longer. T1's quantities up
to 2100 s were therefore already measured on the GPU in the d30 runs: t_fu150 1950 / 1950 / 2100 and sessions alive at 2100 s
49 / 38 / 39, up to engine run-to-run variation. Those are a replication check, not a blind test. T1's blind content is
everything after 2100 s: whether seeds 0 and 1, which recovered in d30 once the slowdown ended, stay trapped when it lasts
until 3000 s, plus alive at 3000 s, outstanding at 3300 s and the state over W. T2 is fully blind: no GPU run at 1.65× with a
slowdown exists.

## 4. Scoring plan (declared now)

**Primary: the registered tri-state per cell.** The outcome is the `outcome` that `python -m analysis.r15_cells classify` gives
for the counted runs: TRAPS / NO-TRAP / MIXED, as registered. If a seed never gets a counted run, the registered call is
`outcome_if_missing_count_against` (a missing seed counts against both TRAPS and NO-TRAP); two counted runs of one seed leave
the cell undecided until a human resolves it. A model's cell call is correct iff it equals that outcome. Frozen
calls:
- simulator (`mixed`, primary): T1 TRAPS, T2 NO-TRAP; `separate` gives the same;
- pred2 fluid verdict: T1 TRAPS, T2 TRAPS;
- pred2 per-seed layer, scored as a probability: P(TRAPS) = 1.00 for T1; P(TRAPS) / P(NO-TRAP) / P(MIXED) = 0.58 / 0.41 / 0.01
  for T2. The log score of the observed outcome is reported.

**Secondary: per-seed agreement of pred2 and the simulator.** For each counted run (up to 6), the GPU per-seed state (STUCK,
GOOD or neither, from the classify records) is compared with four per-seed predictions: (i) simulator `mixed`, (ii) simulator
`separate`, (iii) the pred2 fluid verdict applied to every seed of the cell, and (iv) pred2's per-seed modal call. Report k/6
for each and k/3 per cell. A neither run counts as a miss for every model, since all of them predict STUCK or GOOD. Frozen
pairwise agreement between the models: the simulator and pred2-fluid agree on 4 of 6 runs and differ on T2 seeds 1 and 2
(simulator GOOD, pred2-fluid STUCK); the simulator and pred2's per-seed modal call agree on 6 of 6. **T2 seeds 1 and 2 are the
discriminating runs.** GOOD there supports the simulator (and pred2's per-seed layer) against the fluid verdict; STUCK supports
the fluid verdict. pred2's per-seed probabilities are also scored by log-likelihood (floored at 1e-3) and Brier score over the
6 STUCK outcomes and over the 6 GOOD outcomes, as in `notes/PREDICTIONS_r13_pred2.md`.

**Exploratory** (reported per seed beside each model's value; there is no pass/fail beyond the band stated in (a)). Engine-side
definitions are in `analysis.r15_sim_toolslow.measure_run`, which uses the frozen `analysis.throughput` helpers:
- (a) **t_fu150**: the start of the first 150-s window [1200 + 150k, + 150) whose follow-up hit (ok turns ≥ 2 completing in it,
  cached/prompt > 0.5) is below 0.5. **Prediction: inside [1800, 3300) for every T1 STUCK run.** Simulator per seed: 1950 /
  1950 / 2100 in both modes. Across every simulated T1 STUCK run (3 exact plus 20 random per mode), 21 of 23 fall inside; 2
  random seeds (9 and 11) are at 1650. As section 3 notes, the per-seed T1 values coincide with what the d30 GPU runs already
  showed. For T2 the simulator gives 2100 for seed 0 and none for seeds 1 and 2.
- (b) **Sessions alive at 2100 s and 3000 s** (`backlog_at` of sessions.csv). Simulator (`mixed`): T1 49 / 37 / 39 and 57 / 72
  / 76; T2 39 / 30 / 29 and 67 / 11 / 8. pred2 plan walk (good-state service, no queueing): T1 49 / 37 / 39 and 48 / 53 / 56;
  T2 38 / 30 / 28 and 12 / 11 / 8.
- (c) **Outstanding requests**: the mean over [2100, 2400) (`outstanding_mean`) and the value at 3300 s (`outstanding_at`).
  Simulator (`mixed`): T1 11.3 / 12.3 / 14.4 and 57 / 62 / 70; T2 36.7 / 4.0 / 5.7 and 75 / 0 / 2.
- Reference accuracy from the post-hoc r14 table in section 3: alive at 2100 s within 1 on all 12 runs, alive at 3000 s within
  4, outstanding at 3300 s within 5. Larger errors on T1 / T2 are reported as such.

**Frozen per-seed calls (a copy of the JSON values, for the scorer; seeds 0, 1, 2):**

```yaml
T1:   # sglang-fcfs-r1-toolslow-d30w1800
  simulator_mixed:    [STUCK, STUCK, STUCK]   # cell TRAPS (PRIMARY)
  simulator_separate: [STUCK, STUCK, STUCK]   # cell TRAPS
  pred2_fluid:        STUCK                   # n(3000) = 69.82 > n_u = 32.23; cell TRAPS
  pred2_per_seed:     {p_stuck: [1.000, 1.000, 1.000], p_good: [0.000, 0.000, 0.000], modal: [STUCK, STUCK, STUCK], p_traps: 1.000}
  exploratory:        {t_fu150_band_for_stuck_runs: [1800, 3300], sim_t_fu150: [1950, 1950, 2100],
                       sim_alive_2100: [49, 37, 39], sim_alive_3000: [57, 72, 76], sim_out_2100_2400: [11.3, 12.3, 14.4], sim_out_3300: [57, 62, 70],
                       pred2_walk_alive_2100: [49, 37, 39], pred2_walk_alive_3000: [48, 53, 56]}
T2:   # sglang-fcfs-r1-toolslow-d15-165
  simulator_mixed:    [STUCK, GOOD, GOOD]     # cell NO-TRAP (PRIMARY)
  simulator_separate: [STUCK, GOOD, GOOD]     # cell NO-TRAP
  pred2_fluid:        STUCK                   # n(2100) = 51.12 > n_u = 31.77; cell TRAPS
  pred2_per_seed:     {p_stuck: [1.000, 0.462, 0.220], p_good: [0.000, 0.532, 0.770], modal: [STUCK, GOOD, GOOD],
                       p_traps: 0.580, p_notrap: 0.409, p_mixed: 0.010}
  exploratory:        {sim_t_fu150: [2100, null, null], sim_alive_2100: [39, 30, 29], sim_alive_3000: [67, 11, 8],
                       sim_out_2100_2400: [36.7, 4.0, 5.7], sim_out_3300: [75, 0, 2],
                       pred2_walk_alive_2100: [38, 30, 28], pred2_walk_alive_3000: [12, 11, 8]}
```

**The theory session's trap-state predictions.** The separate theory session froze its trap-state predictions at tag
**`icml-trap-pred`** (commit `6b47a6c` on branch `claude/theory-icml-2164a9`, pushed to origin). The files are
`notes/PREDICTIONS_icml_trap.md`, `configs/icml_trap_predict.yaml` and `results/theory/icml/frozen_predictions.json`, with
scoring rules S1-S5. Those predictions score any trapped run: follow-up hit below 0.2 over the evaluation window, with the
window starting at least 3000 s after the trigger began, on a listed cell (`a100_300k` here) at the run's nominal multiple of
the cell's lambda_ref (1.35 for T1, 1.65 for T2; that file interpolates its 1.1-6.5 grid). A STUCK run of T1 or T2 qualifies
when its follow-up hit over W is also below 0.2 (STUCK uses the all-turn hit; the 209 STUCK runs in `toolslow_sim.json` have a
follow-up hit over W of at most 0.0041, and the r14 d30 GPU STUCK run a hit of 0), and is then scored there by that file's
rules, not by this one.

## 5. Reproduce

From the worktree root in Git Bash (Windows PC; the simulator runs are deterministic, so a re-run reproduces every number;
only the provenance timestamps change):

```bash
cd "C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/tonight"
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
export PYTHONPATH="src;."
"$PY" -m analysis.r15_sim_toolslow plans                                      # 6 x OK (plans = committed NOBURST controls)
"$PY" -m analysis.r15_sim_toolslow selfcheck --modes mixed separate_prefill_priority   # SELFCHECK PASS
"$PY" -m analysis.r15_sim_toolslow run --workers 4                            # 276 runs + 138 sensitivity runs, ~30 s
                                                                              #   -> results/theory/r15/toolslow_sim.json
"$PY" -m analysis.r15_pred2_toolslow                                          # ~2 min -> results/theory/r15/toolslow_pred2.json
TS=results/nova/toolslow_shed_1716990x_pulled_20261101-154800/results/agentload_e2_burst
C=results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst
"$PY" -m analysis.r15_sim_toolslow measure --out results/theory/r15/toolslow_measured_r14.json --run-dirs \
  $TS/20261031-210448 $TS/20261031-210648 $TS/20261031-215143 $TS/20261031-220113 $TS/20261031-220954 $TS/20261031-224211 \
  $C/20261024-155125 $C/20261024-161834 $C/20261024-211253 $C/20261024-160218 $C/20261024-184259 $C/20261025-000053
"$PY" -m pytest -q tests/test_r15_preds_toolslow.py                          # 7 passed
```

Scoring, once the T1 / T2 runs are pulled:
`"$PY" -m analysis.r15_cells classify --run-dirs <T1 and T2 run dirs>` gives the primary outcome and the per-seed states, and
`"$PY" -m analysis.r15_sim_toolslow measure --run-dirs <same dirs> --out results/theory/r15/toolslow_measured_r15.json` gives the
exploratory measures.

## 6. Approximations (stated)

- *Simulator.* It frees a finished session's KV at once (an oracle), and a cached prefix is all-or-nothing per session
  (full_reserve LRU). Outstanding requests are 10-s tick samples, while the engine side uses exact time averages. The exact-plan
  calls are deterministic, so their uncertainty is model error, which the random-seed counts and the sensitivity grid only
  bracket. The plans equal the GPU's up to the last bit of the tool times.
- *pred2.* The quasi-static switched curve and its stated approximations are r13's: the internal state relaxes at once; the
  switch at t_off is instantaneous, with t_off + δ as a band; the plan walk uses good-state service with no queueing; and the
  per-seed committor starts at X0 = sessions alive at t_off. With no slowed good state (both cells), P_slow = 0 and the fluid
  carries n to t_off. On the GPU, d30 seeds 0 and 1 recovered from X0 = 49 and 37, well above n_u = 32.2, so this per-seed
  layer already has a known miss in this cell family.
- *Design.* T1 and T2 were chosen after d30 scored 1 of 3 and after reading simulator outputs (see the registration's
  history text), so the cells are not blind in design. The predictions are blind in outcome only once pushed before the first
  job.

## 7. Files (sha256 at writing; the JSON values are deterministic, but their provenance timestamps change on a re-run)

- New code: `analysis/r15_sim_toolslow.py` (`0b1541a2e203ff36fba858e3ec8a0eaac72998af3ea725bf02712c3a056de638`),
  `analysis/r15_pred2_toolslow.py` (`ea6c96db8966cc4b53a562de67167eb52623ced897c65b98c1c39b47e1fad7e2`),
  `tests/test_r15_preds_toolslow.py` (`ef04be055b58ba4a632714056ce057e90d459881f1b8c0eb4a6d98aff2ae7473`), and this file.
- New outputs (`git add -f`): `results/theory/r15/toolslow_sim.json`
  (`3ca6d345b24954d41d9d60436dad2fb19d3845573738806fce13aaa91ac25d4e`), `toolslow_pred2.json`
  (`ae67af8b28be7c8140e2e712ec90cb6ca17981a5b7c3a8e1efffb117d0a5af6b`), `toolslow_measured_r14.json`
  (`7331d35af11cf8ae1ce8660993a58177a5c63f318508dfd228f9f12df4cd283f`). Each JSON's provenance block records the sha256 of the
  code and inputs it was made with, and they match the files above. A `run --quick` writes `toolslow_sim_quick.json` and a
  `--cells` subset of the pred2 driver writes `toolslow_pred2_subset.json`, so neither can overwrite the frozen files.
- The frozen inputs read: `configs/r11_predict_rescue.yaml`, `configs/r6_predict.yaml`, `configs/r11_basin_predict.yaml`,
  `configs/agentload_e2_burst.yaml`, `experiments/r11_predict_rescue.py`, `src/prefixmeta/*`, `src/agentload/{workload,config}.py`,
  `prereg/inputs/2026-10-23/calibration.json`, `analysis/theory/**` and `results/theory/pred2/toolslow.json`. None was edited;
  their sha256 values are recorded in each JSON's provenance.

## Freeze record (to be filled by the lead at commit; nothing above changes after the tag)

- Commit: `<hash>`, tag `<tag>`, pushed `<UTC time>` (`gh api repos/AkshatValse/Nova-Research/activity`).
- First T1 / T2 job submitted at `<time>`; it must be later than the push.
