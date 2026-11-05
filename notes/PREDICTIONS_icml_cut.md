# Frozen predictions: the arrival-cut test of Corollary 3 (tag `icml-cut-pred`)

These predictions were written on 2026-11-05 before any cut run existed. They come from the frozen model F and the
Theorem 1/2 code (`analysis/theory/icml/trap_renewal.py`, unchanged since tag `icml-trap-pred`).

- **Numbers:** `configs/icml_cut_predict.yaml`.
- **Full output:** `results/theory/icml/cut_predictions.json`.
- **Exact plans** (client `plan.csv` format): `results/theory/icml/cut_plans/{CUT-A,CUT-B}_seed{0,1,2}.csv`.
- **Reproduce:** `PYTHONPATH="src;." python -m analysis.theory.icml.cut_predict` (about 7 s).

**Blindness.** I read no run result dated on or after 2026-11-04. The only run data read are:
- the six committed `sglang-fcfs-r1` BURST runs at 1.35x and 1.65x (seeds 0–2, run 2026-10-24/25, in
  `results/nova/e2_170933xx_pulled_20261025-144558/`);
- their `plan.csv`.

## 1. Design, as I built it

- **Cell:** SGLang 0.5.22 FCFS, refresh 1, 300k pool, Qwen2.5-7B, A100 80GB PCIe (label `sglang-fcfs-r1`, model cell
  `a100_300k`).
- **Reference rate:** λ_ref = 0.07153402 sessions/s (`prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based`).
  The model's all-miss rate is λ_miss = 0.07183953 = 1.0043 λ_ref. The model's trap-exit population is n_b = 32.7 sessions.
- **Arrivals:** `kind: ramp`, `ramp_is_mult: true`, with knots `[[0, 1.65], [2400, 1.65], [2400.001, λ'/λ_ref], [8700, λ'/λ_ref]]`,
  in the SHED config's 1 ms-step convention.
  - Candidates are drawn at rate_max = 1.65 λ_ref from S_ARRIVALS; S_THIN does the thinning.
  - Burst: 200 sessions uniform on [1200, 1260) s. The run lasts 8700 s.
- **Plan construction:** `agentload.workload.build_open_plan` applied to `configs/agentload_e2_shed_t600.yaml` with these overrides:
  - `arrivals.ramp=<knots>`
  - `arrivals.lambda_ref=<calibration>`
  - `run.seed=<seed>`

  This is the client's own code path. I did not use the build agents' `cut_a115`/`cut_b085` YAMLs. If their knots
  differ only inside the 1 ms switch, the plans are identical unless a candidate lands in that millisecond. To check,
  compare their `plan.csv` with the CSVs here:
  - sid, origin, idx, arrival_s and n_turns should match exactly;
  - tool_time_total_s matches only to ~1e-13 s, because these CSVs were built on Windows and numpy's exponential draws
    differ in the last bit between platforms' libm.

  So `plan_sha256` in the YAML identifies these Windows-built files only. Do not expect a Linux-built plan.csv to hash
  the same.
- **Pre-cut identity:** for each seed, every session with arrival < 2400 s matches the committed 1.65x BURST control's
  `plan.csv`: exactly in sid, origin, idx, arrival and n_turns, and to within 2e-13 s in the tool total (the last-bit
  difference above).
  - Seeds 0, 1 and 2 have 519, 479 and 501 such sessions, in both arms.
  - Sessions after the cut are a thinned subset, with specs re-drawn (idx = rank among the kept base arrivals).

| arm | λ' (/s) | ρ' = λ'/λ_miss | sessions (seed 0/1/2) | base arrivals after 2400 s |
|---|---|---|---|---|
| CUT-A | 0.082264 (1.15 λ_ref) | 1.1451 | 1058 / 992 / 1041 | 539 / 513 / 540 |
| CUT-B | 0.060804 (0.85 λ_ref) | 0.8464 | 915 / 845 / 891 | 396 / 366 / 390 |

## 2. What "theory" means here

There are two layers, both from the frozen model F with no parameter fitted to any trap measurement.

1. **The fluid (Poisson average).** `fifo_fluid(1.65 λ_ref, n_bg = n1 = 10.43, lam_after = [(2400, λ')])`.
   - This is the expected trajectory over random plans.
   - Across the plans of seeds 0–39, the per-plan [3000, 8700) slope has mean +0.0067 and SD 0.0049/s in CUT-A, and mean
     −0.0062 and SD 0.0043/s in CUT-B. That matches the fluid; seeds 0–2 are ordinary draws. Only 90% of CUT-A plans give
     a positive slope (`plan_spread_seeds_0_39` in the YAML).
   - The fluid is therefore **not** the per-seed theory value.
2. **The per-seed plug-in (registered theory value).** This is model F driven by the exact plan, using
   `cut_predict.plan_fifo`:
   - one FIFO server does c_k GPU-seconds for a session's k-th turn (all miss) from t_b = 1200 s on;
   - each session's turn count and tool times come from the plan;
   - before 1200 s the engine is in the good state, with a turn latency of 1.33 s. That latency is calibrated so the mean
     background equals the frozen open-equilibrium n1 = 10.43; it is model-internal and not fitted to runs;
   - given the plan, the result is deterministic.

**Retrospective check of the plug-in (not blind).** The plug-in was run on the six committed 1.35x/1.65x BURST runs of
this cell (constant arrivals, no cut).

| quantity | measured − model |
|---|---|
| backlog slope over [3000, 8700) | −0.0011 to −0.0005 /s (mean −0.0007, SD 0.0002) |
| backlog slope over [5700, 8700) | −0.0024 to +0.0007 /s (mean −0.0003, SD 0.0011) |
| completion rate over [5700, 8700) | −0.0023 to +0.0027 /s |
| served-prompt mean | +0.5% to +1.4% |
| gap median | −3% to −6% |
| 300 s-median gap trend | within 25% |

These six runs are the whole noise model. They contain no cut, so the P(PASS) values below also use larger, assumed
noise levels.

## 3. Registered predictions, per arm and seed

Notation:
- slopes are OLS slopes of 10 s bin means of sessions in system (`measured.window_stats` `backlog_slope`), in sessions/s;
- C = session completions per second; W1 = [3000, 8700), W2 = [5700, 8700);
- N bins are 300 s bin means of sessions in system.

**Backlog slopes and completions**

| arm | seed | λ_plan W1 | λ_plan W2 | **theory slope W1** | theory slope W2 | naive W1 (expected) | C over W2 (× λ_ref) |
|---|---|---|---|---|---|---|---|
| CUT-A | 0 | 0.08614 | 0.08533 | **+0.00392** | +0.00691 | −0.0389 | 0.07467 (1.044) |
| CUT-A | 1 | 0.08018 | 0.07533 | **−0.00258** | −0.00359 | −0.0382 | 0.08567 (1.198) |
| CUT-A | 2 | 0.08474 | 0.08967 | **+0.00284** | +0.01289 | −0.0036 | 0.07767 (1.086) |
| CUT-B | 0 | 0.06263 | 0.06133 | **−0.00953** | −0.01213 | −0.0624 | 0.06567 (0.918) |
| CUT-B | 1 | 0.05772 | 0.05433 | **−0.01310** | −0.00982 | −0.0606 | 0.06833 (0.955) |
| CUT-B | 2 | 0.06105 | 0.06267 | **−0.01233** | −0.00733 | −0.0273 | 0.07000 (0.979) |

**Backlog levels, dip and served turns**

| arm | seed | N bin [2100, 2400) | N bin [8400, 8700) | dip: depth (300 s bins) | dip: lowest bin | served prompt W2 (tokens) | gap median W2 (s) | gap trend W2 |
|---|---|---|---|---|---|---|---|---|
| CUT-A | 0 | 185.6 | 231.2 | 5.5 (3.0%) | [2400, 2700) | 9994 | 188 | +0.0068 |
| CUT-A | 1 | 180.5 | 165.8 | 16.9 (9.4%) | [6600, 6900) | 10136 | 155 | −0.0018 |
| CUT-A | 2 | 178.9 | 203.6 | 15.2 (8.5%) | [6600, 6900) | 9718 | 153 | +0.0086 |
| CUT-B | 0 | 185.6 | 137.6 | n/a (drains) | n/a | 11547 | 151 | −0.0034 |
| CUT-B | 1 | 180.5 | 84.6 | n/a (drains) | n/a | 11300 | 104 | −0.0099 |
| CUT-B | 2 | 178.9 | 95.4 | n/a (drains) | n/a | 10954 | 110 | −0.0112 |

The full 300 s N trajectories are in the YAML (`N_300s_bins`; bin centres in `n_300s_bin_centers`).

**Fluid (Poisson average)**

- **CUT-A:**
  - Slopes: +0.00716 over W1 and +0.00880 over W2. C over W2 = 1.028 λ_ref.
  - Dip: N(2400) = 182.6, lowest 173.5 at t ≈ 3520 s (−9.2, −5.0%), then regrowth to N(8700) = 211.3.
  - Served prompt over W2: 10,096. The FIFO wait trend is +0.0088 s/s.
  - Asymptotics at λ' (Theorem 1/2): z' = 1.00575, γ' = 0.00575, α' = 0.00646/s, D' = 1.0597 λ_ref. So D' sits below
    λ' = 1.15 λ_ref and above λ_miss: Corollary 3's regrowth.
- **CUT-B:**
  - Slopes: −0.00543 over W1 and −0.00307 over W2. C over W2 = 0.903 λ_ref.
  - N(8700) = 123.5. The remaining all-miss work at the cut is V_tot(2400) = 3794 GPU-s.
  - Theorem 1(a): the trap empties after V_tot/(1 − ρ') = 24,700 s, at **t ≈ 27,100 s**, far beyond 8700 s.
  - Served prompt over W2: 11,447. The wait trend is −0.0027 s/s.

**Item-by-item answers**

1. **Backlog slope:** see the tables above. The **naive comparator** is
   `naive(W) = λ_plan(W) − C_run[1800, 2400)`:
   - λ_plan(W) is the plan's base arrivals in W divided by |W|;
   - C_run is that run's own completions in [1800, 2400) divided by 600 s.

   The expected values above use the same-seed 1.65x control's C[1800, 2400): 0.1250, 0.1183 and 0.0883 /s for seeds 0, 1
   and 2. The pre-cut plan is identical, so the cut run should replicate them up to engine jitter. For reference, model F
   gives 0.1183, 0.1267 and 0.1017.
2. **CUT-A dip:**
   - Fluid: a 5.0% dip with its lowest point at ≈ 3520 s.
   - Per seed (300 s bins against the [2100, 2400) bin): 3.0% in [2400, 2700); 9.4% and 8.5% in [6600, 6900).
   - **Registered:** the dip depth is < 15% of the [2100, 2400) level in every CUT-A seed, and the [8400, 8700) bin is > 150.
3. **Completion rate over W2:** see the first table. The registered tolerance is ±0.006/s, three times the retrospective
   SD of 0.002.
4. **Follow-up hit over W2:** STUCK (< 0.2) in all six runs, with expected value ≈ 0.00. Model F is all-miss while N > n_b
   = 32.7. The lowest predicted 300 s bin after the burst is 163 in CUT-A and 85 in CUT-B. All six committed 1.35x/1.65x
   controls measured exactly 0.000 over W2.
   - **Contrast:** the naive slope projected from the [2100, 2400) level reaches n_b, the level at which hits return,
     before 8700 s in 5 of 6 runs:
     - CUT-A seeds 0 and 1 at ≈ 6300 s;
     - CUT-B seeds 0 and 1 at ≈ 4850 s, and seed 2 at ≈ 7750 s.
5. **Other quantities the theorems sharpen:**
   - **The cut lengthens the served prompts** (the turn mix ages: the tilt z'^-k flattens). The served-prompt mean over W2
     is 9.7–10.1k tokens in CUT-A and 11.0–11.5k in CUT-B. The 1.65x controls measured 8.4–8.8k. The registered tolerance
     is ±5%.
   - **The cycle trend changes sign in CUT-B.** The 300 s-median gap trend is negative in all three CUT-B seeds. In CUT-A
     it is positive in seeds 0 and 2.
   - **CUT-B clears only at ≈ 27,100 s** (Theorem 1(a)). With the trap at its size at the cut, a cut clears within this
     protocol's 8700 s only for λ' ≲ 0.40 λ_ref.

## 4. Proposed registered decision rule

- **R1 (the lead's rule).** Per seed, the run is THEORY-FAVOURED iff |m − T| < |m − naive| over W1, where:
  - m is the measured slope;
  - T is `theory_slope_w3000` from the YAML (the per-seed plug-in, not the fluid);
  - naive = λ_plan(W1) − C_run[1800, 2400), computed from that run.
- **R2 (CUT-A only, regrowth).** The measured slope is > 0 in ≥ 2 of 3 seeds. **I recommend W2 = [5700, 8700) for R2
  instead of W1.**
  - The theory puts the per-seed dip minimum as late as 6750 s, so W1 straddles the dip.
  - The theory itself predicts a negative slope for seed 1 in both windows, because seed 1's plan has light post-cut
    arrivals: 0.0802/s in W1 and 0.0753/s in W2. R2 therefore needs both seed 0 and seed 2 to be positive.
  - Seed 2's W1 margin is small (+0.0028), and its W2 margin is large (+0.0129).
- **PASS:**
  - CUT-B passes iff R1 holds in ≥ 2 of 3 seeds.
  - CUT-A passes iff R1 holds in ≥ 2 of 3 seeds AND R2 holds.
- **Unstuck runs.** A run that is not STUCK over W2 (follow-up hit ≥ 0.2) counts as a seed that is not theory-favoured.
- **Secondary predictions, registered but not part of PASS:** completion over W2 within ±0.006/s; served prompt within
  ±5%; CUT-B gap trend < 0; CUT-A dip < 15% with the last bin > 150.

**P(PASS).** These come from a Monte Carlo with 200k draws. In it:
- measured = plug-in + bias + noise;
- the bias is the retrospective mean (−0.0007 over W1, −0.0003 over W2);
- the noise in the two windows is correlated at 0.7;
- the naive's own C_run[1800, 2400) is drawn as the control's value plus Poisson noise on the count, which is
  conservative.

| noise SD (W1 / W2) | CUT-A, lead's R2 (W1) | CUT-A, amended R2 (W2) | CUT-B |
|---|---|---|---|
| fitted (0.0002 / 0.0011; 6 runs, no cut) | 0.9999 | 0.9999 | 1.000 |
| 0.002 / 0.003 (my headline) | **0.82** (0.91 without bias) | **0.99** | **1.000** |
| 0.004 / 0.006 (stress) | 0.63 (0.72) | 0.88 (0.90) | 0.9996 |

Per seed at the headline noise:
- P(theory-favoured) is 0.998, 0.994 and 0.90 for CUT-A, and 1.00, 0.999 and 0.94 for CUT-B. Seed 2 is the weakest in
  both arms because its control's pre-cut completion rate was low (0.0883), which moves the naive close to the theory.
- In CUT-A, P(slope > 0) is 0.95, 0.05 and 0.86 over W1, and 0.985, 0.095 and 1.00 over W2.

## 5. Design flaws and caveats

1. **CUT-A is near the boundary.**
   - ρ' = 1.145, and the asymptotic growth is only α' = 0.0065/s.
   - The sign of a single run's slope depends on its plan: 10% of random plans give a negative slope over W1, and seed 1
     is one of them.
   - Use the per-seed plug-in, not the fluid or α', as the theory value, and test regrowth over W2 (R2 amended).
2. **The cut is early.**
   - It comes 1200 s after the burst, when the trap is young (Remark 8: ≈ 35 generations to converge). The window does
     not reach α' or D'; the test checks model F's transient trajectory.
   - That is fine for R1, but it means the experiment does not test the asymptotic regrowth rate of Corollary 3.
3. **The naive comparator is weak by construction.**
   - Its window [1800, 2400) sits 600–1200 s after the burst. There, completions are inflated by the burst cohort's short
     sessions: model F gives 1.42–1.77 λ_ref, and the controls measured 1.23–1.75 λ_ref.
   - So R1 mostly tests "model F versus early-trap throughput". A stronger optional comparator is λ_plan(W) − λ_ref (an
     operator who knows λ_miss but not the transient). It predicts +0.0146, +0.0086 and +0.0132 over W1 for CUT-A seeds 0–2,
     and −0.0089, −0.0138 and −0.0105 for CUT-B. That is 0.010–0.011 away from the plug-in in CUT-A, but within 0.002 of
     it in CUT-B. If you want a harder test, report this comparator too, without registering it.
4. **CUT-B cannot show recovery within 8700 s.** The predicted clearing time is ≈ 27,100 s. CUT-B tests the drain rate and
   the "still stuck" prediction, not the recovery threshold itself.
5. **The noise model is thin.** It rests on six constant-rate runs without a cut. The engine's small speed excess appears
   as a −0.0007/s slope bias and a 3–6% shorter gap. P(PASS) is therefore also given at noise SDs of 0.002 and 0.004/s over W1
   and 0.003 and 0.006/s over W2, about 3 and 6 times the fitted RMS residuals (0.0007 and 0.0011).
6. **The plans must match.** The predictions are conditional on the run's `plan.csv` matching
   `results/theory/icml/cut_plans/` (same seeds, same knots). If the build agents' knots differ, rerun `cut_predict.py`
   with their knots **before** any result exists.
