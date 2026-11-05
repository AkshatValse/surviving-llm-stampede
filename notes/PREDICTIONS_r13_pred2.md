# Round-13 theory, second prediction set (pred2): B2, N2, TOOLSLOW, SHED, E0F, Propositions S and E, Corollary C

Written 2026-10-31, 02:40-03:40 CDT, on branch `r13/pred2` (worktree base `5271ff6`, the `r13/theory` tip); revised the same morning after an adversarial check (list below), then committed, tagged `r13-theory-pred2` and pushed before the first B2, N2, TOOLSLOW or SHED job (push time at the end of this file). The model is the one frozen at tag `r13-theory-pred` (commit `997d2c4`) and is **unchanged**: `git diff 997d2c4 -- analysis/theory` lists only new files (`analysis/theory/paper/*` from `5271ff6`, the new driver package `analysis/theory/pred2/*` and the new cell spec `analysis/theory/cells/h200_600k.yaml`).

- Machine-readable: `configs/r13_theory_pred2.yaml`. Full records: `results/theory/pred2/{b2_basin,h200_n2,toolslow,shed,e0f,prop_e_cor_c,blind_tables,h200_600k}.json` (git-ignored; force-added). Outputs of the conditional recipe, once run on a registration, go to `results/theory/pred2/conditional/*.json` and `*.yaml`; they are also git-ignored and need `git add -f`.
- Drivers: `analysis/theory/pred2/` (`b2`, `h200_n2`, `toolslow`, `shed`, `e0f`, `prop_e`, `blind_tables`, `conditional`, `run_all`, `freeze_table`, `common`). Tests: `tests/test_theory_pred2.py` (11 tests, under a minute).
- Reproduce (Windows Git Bash, about 10 minutes): `PYTHONPATH="src;." python -m analysis.theory.pred2.run_all`. Deterministic: fixed grids, the exact client plans of fixed seeds, and fixed synthetic seeds 1000-1399.

**Revisions after the adversarial check** (before any B2, N2, TOOLSLOW or SHED job; no frozen function changed):
1. *B2 plan statistic calibrated (changes the headline).* The realized cohort's time-maximum live KV does not average to b · 4,331: over the 400 synthetic seeds its mean is 12.9 / 27.6 / 42.3 / 51.5 / 61.2 at b = 10 / 25 / 40 / 50 / 60 (+29% at b = 10, +6% at b = 40). The time maximum picks up the cohort's own noise, which the committor's F2 diffusion then adds a second time; §1 already rejected the window maximum of background + cohort for the same double counting. The per-seed b_eff is now put on the frozen layer's scale, b_cal = b_eff · b / E_synth[b_eff(b)], before the frozen committor is called. P(rule) moves from 0.42 to **0.66**; the uncalibrated 0.42 is kept as a band.
2. *Remedy 2a items 2, 3, 4 and 7 added* (§8): the `h200_600k` spec and its frozen predictions; trapped-state tables for H200 (1.05-1.65×) and Llama (1.35-2.5×) at caps 20-32; exogenous-gap rival curves and b_stat for every blind cell; pool-sweep lookups at every integer n and every 0.01 multiple.
3. *TOOLSLOW:* the stochastic 50% δ is frozen as well (16.4 s; the fluid δ* = 16.8 s is where the stochastic layer already gives 0.87). The non-monotonicity of the stochastic layer at δ = 13.7 s is now stated.
4. *Rounding:* the good-from time is 8,274 s (8274.4), not 8,275.
5. *SHED:* the refused counts are a protocol check (fixed by the client plans), not a model prediction. The registered SHED rule (commit `b006291`, read as protocol only) uses seeds 0 and 1, 2 of 2 each, so the registered P(rule) is 0.997; the earlier three-seed 0.995 is kept for reference.
6. *E0F:* the horizon approximation of the F2 escape is stated.

## Headline

| target (protocol) | primary prediction | bands / alternatives | registered rule: predicted probability |
|---|---|---|---|
| **B2** (300k, 1.65×, bursts of 40, 50, 60 in 60 s at 1200 s, seeds 0-2) | Per-seed P(STUCK) on the exact client plans (calibrated cohort peak), seeds 0 / 1 / 2: **b40 0.78 / 0.36 / 0.09; b50 0.86 / 1.00 / 0.22; b60 1.00 / 1.00 / 0.81.** P(GOOD at b40) 0.22 / 0.63 / 0.90. The realized 40-session cohorts of seeds 0 and 1 are heavy: on the frozen layer's scale their peak live KV equals 53.0 and 46.9 average cohorts' worth (seed 2: 36.1), against b_c = 53.4. Deterministic critical burst 53.4 (frozen); committor 50% at 49.5; composition-averaged 50% (a seed with an unknown plan) at 48.4 | per seed b40 P(STUCK): uncalibrated time maximum 1.00 / 0.52 / 0.11; lockstep 0.41 / 0.51 / 0.10; 2.5 s service 0.74 / 0.41 / 0.10; realized background at the peak 0.43 / 0.17 / 0.07. Frozen exchangeable layer (cohort at its mean): 0.14 at every seed | **bracketed (b40 GOOD ≥ 2/3 and b60 STUCK ≥ 2/3): P = 0.66** (bands 0.23-0.88; uncalibrated 0.42; frozen exchangeable layer 0.94). For the lead: 0.42 to 0.66 depending on how a plan is mapped to the cohort size; the frozen layer gives 0.94. Secondary, A's deterministic level crossing on the exact plans: b40 GOOD 3/3, b60 STUCK 3/3, so the rule holds |
| **N2** (H200 300k Stage C at n = 36, 44, 52) | hit 0.564 / 0.000 / 0.000 (fluid), 0.527 / 0.083 / 0.002 (F1); μ turns-based 0.359 / 0.197 / 0.197 (fluid), 0.348 / 0.221 / 0.197 (F1). 0.5-hit crossing 37.3 (fluid), 36.5 (F1); n_b 41.3 | the four frozen cost variants: hit(36) 0.52-0.57 (fluid), 0.50-0.53 (F1); n_half 36.4-37.4. The rival capacity ratio M/E_S = 27.8 predicts hit(36) < 0.5 | **T3(c) supported (hit(36) ≥ 0.5 and hit(44) < 0.5): P = 0.80** (band 0.46-1.00); deterministic: holds in 9 of 10 variant × estimator cases (fails: e0a2 under F1, hit(36) = 0.497) |
| **TOOLSLOW** (300k, 1.35× NOBURST, every tool call starting in [1200, 2100) s lasts Z + δ) | δ = 10 s: GOOD (fluid n(2100) = 21.5 < n_u = 32.2), but the slowed curve's peak is only 1.21 λ, so P(escape during the 900 s) = 0.29: **P(GOOD) = 0.71 per seed.** δ = 30 s: **STUCK, P = 1.00** (no good state while slowed; n(2100) = 46.9). **Critical δ: fluid δ* = 16.8 s, stochastic 50% point 16.4 s**; above δ = 13.7 s no good state exists during the slowdown | band (escape target n_u instead of n_b): P(GOOD at δ = 10) = 0.59. An exponential law of the same mean puts δ* at 18-20 s. Per-seed plan walk at 2100 s: 22 / 15 / 15 sessions (δ = 10), 49 / 37 / 39 (δ = 30) | **δ = 10 GOOD ≥ 2/3 and δ = 30 STUCK ≥ 2/3: P = 0.80** (band 0.63) |
| **SHED** (300k, 1.35×, burst 200 at 1200 s, arrivals stopped from 1800 s for τ) | **Proposition S: τ_min = 1,795 s** (x0 = n(1800) = 161.3; 1,790 s on the all-miss branch plus 5.5 s on the good branch). **τ = 600 s: STUCK (P = 1.00); τ = 3600 s: GOOD (P = 0.998).** Sessions refused (protocol check, fixed by the client plans): 59 / 56 / 61 (τ = 600) and 355 / 378 / 377 (τ = 3600) on seeds 0 / 1 / 2, against 0 for the R1 cap | composition-aware round robin: τ_min = 1,928 s (the young backlog drains at 1.71 λ_ref at first, then ages to 0.034 sessions/s); plan-driven round robin per seed: x0 = 179 / 178 / 171, τ_min ≈ 2,260 / 1,990 / 1,840 s. Optional τ = 1800 s is near-critical: P(STUCK) 0.74 (quasi-static) to 1.00 (round robin, every seed) | registered rule (seeds 0, 1; τ = 600 STUCK and τ = 3600 GOOD, 2 of 2 each): **P = 1.00 × 0.998² = 0.997** (three seeds: 0.995) |
| **E0F** (300k, from empty, 3000 s, seeds 3-5) | per-seed P(unstable) **0.150 at 2.0×, 0.691 at 2.5×** (frozen F2). Binomial (k = 0..3 unstable): 2.0× 0.614, 0.326, 0.058, 0.003; 2.5× 0.030, 0.198, 0.443, 0.330 | realized rates 2.013 / 2.148 / 1.971 and 2.512 / 2.665 / 2.470: F2 at them 0.16 / 0.28 / 0.13 and 0.70 / 0.84 / 0.66. A's level crossing on the exact plans: all six stable (it retrodicts seed 0 correctly: 2.0× stable, 2.5× at a realized 2.73× unstable) | **replicated (2.0× stable 3/3 and 2.5× unstable ≥ 2/3): P = 0.47** (realized-rate band 0.44; A's crossing: not replicated) |
| **Proposition E** (measured cells; retrospective) | Exogenous-gap closures cannot produce the cliff. At the measured throughput, Yao et al.'s Theorem 3.1 gives the full good-state hit 0.932 at every measured point. The closed variants (Che with W = Z; Yao closed by Little's law) give 0.50-0.55 at n = 48, 0.25-0.28 at 96 and 0.08-0.09 at 300 (300k), and 0.59-0.66 at n = 128 (native). Measured: 0.000, 0.000, 0.000, 0.007 | reconciling the measured hits with exogenous gaps needs the non-idle KV to fill ≥ 99.95% of the pool at every all-miss point, which is the memory-gated queue (A4); measured mean queues 24-269 requests | n/a (measured data) |
| **Corollary C** (every cell) | n_b − M/E_S = λ_miss z̄ (E[T] − 1) exactly: 4.94 (A100 300k), 5.07 (native), 4.73 / 5.04 (150k / 600k), 4.26 (Llama), **13.55 (H200)** | measured crossings: 32.16 (300k) and 93.42 (native) against M/E_S 27.76 and 89.79 (errors −4.4, −3.6) and n_b 32.70, 94.86 (+0.5, +1.4); on vLLM the capacity ratio is closer (−0.9 against +3.7) | frozen rival predictions for the blind cells: 150k 13.6 vs n_half 16.9; 600k 56.1 vs 60.0; H200 27.8 vs 37.3; Llama 27.8 vs 30.9 |
| **Blind tables** (remedy 2a.2, 2a.3, 2a.4, 2a.7; §8) | `h200_600k` (new spec, frozen code): 0.5-hit crossing 66.6 (fluid) / 64.8 (F1), n_b 69.9, window 3.27 λ_ref, F2 edge 2.57×, registration consequence 1.5 / 2.0× with cap 48. Trapped-state tables: H200 1.05-1.65×, Llama 1.35-2.5×, caps 20-32. Exogenous-gap rival curves and b_stat for every blind cell. Pool-sweep and h200_600k lookups at every integer n and every 0.01 multiple | the four H200 band variants are tabulated too; every lookup reproduces the frozen JSON at its own points (difference 0) | n/a (lookup tables; the cells' own rules are the frozen ones) |
| **Conditional recipe** (H200, Llama) | `python -m analysis.theory.pred2.conditional --cell h200_300k --registration <file>` (and `--cell llama31_8b_300k`); mechanical, at the frozen code | self-test: fed the model's own registration consequence (1.10 / 1.15×, cap 32) it reproduces the frozen `h200_300k.json` E2 block exactly (102 values, 0 differences) | n/a |

Every μ is turns-based (completed turns per second / E[T]); every hit is the all-turn fraction (first turns always miss), the estimator of Stage C's `hit_frac_turns` and of the E2/B1 `frac_turns_cached_gt50`.

## 1. B2: the basin dose-response at 1.65× (remedy N1)

**Protocol** (registrations `configs/agentload_prereg_2026-10-31_b{40,50,60}.yaml`, commit `621d88f`, read as protocol only): A100 300k cell, SGLang FCFS, 1.65 λ_ref = 0.118031 sessions/s, BURST arm only, burst n ∈ {40, 50, 60} uniform in [1200, 1260) s, seeds 0-2, 8700 s, window [5700, 8700) s. STUCK := hit < 0.2; GOOD := RECOVERED or (hit > 0.8 and backlog slope ≤ 0.5(λ − λ_ref)). Rule: bracketed iff b = 40 GOOD in ≥ 2/3 and b = 60 STUCK in ≥ 2/3.

**Layers.**
- *Frozen (unchanged):* the deterministic critical fresh burst b_c (F3) and the committor of B's F2 diffusion, `extras.burst_trap_probability`: X0 = D_live⁻¹(D_live(n1) + b · 4,331 tokens), P(STUCK) = q(X0) + (1 − q) P_esc, with P_esc the F2 background escape before the stuck-by time 6,344 s. The driver reproduces the frozen B1 rows exactly (maximum difference 0).
- *New, the GOOD side:* P(GOOD) = (1 − q)(1 − P_esc(until 8,274 s)), 8,274 s (8274.4) being the earliest escape time that still leaves the window hit above 0.8 (an escape is taken to drop the hit from 0.932 to 0 at once). The frozen P(PASS) counted every non-trapped run as GOOD; the difference is about 0.01.
- *New, exact plans (PRIMARY per seed):* the plans are rebuilt with the client's own generator (`agentload.workload.build_open_plan`, the r11 S1 method), seed by seed. For each burst size, the realized cohort peak is computed with the frozen live-KV function `extras._live_paths`, fed with the plan's burst sessions (arrival times, turn counts, tool times) and the good-state service S(n1) = 1.33 s per turn. The raw statistic is b_eff = peak / 4,331. The background stays at the frozen mean D_live(n1) = 110,025 tokens.
- *Calibration (review fix).* The time maximum of a random cohort's live KV does not average to b: the max picks up the cohort's own fluctuation. Over the 400 synthetic seeds, E[b_eff(b)] / b = 1.287 / 1.106 / 1.056 / 1.030 / 1.019 / 1.008 at b = 10 / 25 / 40 / 50 / 60 / 75, and 0.96-0.99 at b = 100-200. Feeding the raw b_eff to the committor would count that noise twice, since the F2 diffusion carries it again. So the primary uses **b_cal = b_eff · b / E_synth[b_eff(b)]**: the plan's deviation from an average cohort, on the frozen layer's scale (E_synth[b_cal] = b exactly). The construction is the frozen one; only the burst's composition is conditioned on.
- *Bands* (all calibrated the same way unless marked raw): the lockstep peak with the realized turn counts (max_j E_j #{T_i ≥ j}, its own factor, 1.32 at b = 10 and 1.11 at b = 40); the cohort at 2.5 s per turn (the S(n1) factor, so the service shift is kept); the plan's realized background at the cohort's peak instant (the cohort part calibrated, the background deviation added unchanged); the background escape at the realized post-burst arrival rate (1.75 / 1.70 / 1.76× on seeds 0 / 1 / 2); and the raw versions of the first four. The raw time maximum is the value this note gave before the review.
- *Not used:* the maximum over a window of background + cohort. It double counts the background noise that the committor already carries; over synthetic seeds it gives P(STUCK) = 0.18 at b = 25, against the F2 background escape of 0.03.
- *Secondary (deterministic):* A's level-crossing criterion applied to the exact plan. The live KV of all the plan's sessions (base + burst) first reaches D_live(n_u) = 341,355 tokens before 6,344 s (STUCK), or not before 8,274 s (GOOD).

**Critical sizes** (λ = 1.65 λ_ref): deterministic 53.4 (frozen); committor q = 0.5 at 49.5; P(STUCK) = 0.5 at 49.3; composition-averaged P(STUCK) = 0.5 at **48.4** (400 synthetic seeds of the same generator, calibrated; realized-background band 48.0; uncalibrated 46.6). Stationary-composition rival b_stat = 21.3. At 1.35× (remedy 2a.5): 59.4 / 55.6 / composition-averaged 54.8 (uncalibrated 53.6), exchangeable P(STUCK) 0.004 / 0.024 / 0.178 / 0.931 at b = 25 / 40 / 50 / 60.

**Full dose-response row** (P(STUCK); P(GOOD) in brackets; b_cal is the calibrated cohort size, raw b_eff in parentheses):

| b | frozen layer (cohort at its mean) | composition-averaged | seed 0: b_cal (raw), P | seed 1: b_cal (raw), P | seed 2: b_cal (raw), P | A's crossing (seeds 0/1/2) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0.040 [0.949] (frozen function's post-burst horizon: 0.032) | = | retrodiction | retrodiction | retrodiction | GOOD / GOOD / GOOD |
| 10 | 0.033 [0.955] | 0.033 | 10.2 (13.1), 0.033 | 12.1 (15.5), 0.034 | 8.3 (10.7), 0.033 | G / G / G |
| 25 (B1) | 0.042 [0.946] | 0.046 | 28.0 (31.0), 0.048 | 30.6 (33.9), 0.055 | 20.8 (23.0), 0.038 | G / G / G |
| **40** | 0.139 [0.850] | 0.212 [0.779] | **53.0 (56.0), 0.778 [0.219]** | **46.9 (49.5), 0.360 [0.632]** | **36.1 (38.2), 0.088 [0.900]** | G / G / G |
| **50** | 0.547 [0.447] | 0.561 [0.434] | **54.1 (55.7), 0.862 [0.136]** | **58.2 (60.0), 1.000** | **43.3 (44.6), 0.217 [0.773]** | G / S / G |
| **60** | 1.000 | 0.886 [0.112] | **62.6 (63.8), 1.000** | **71.6 (73.0), 1.000** | **53.4 (54.4), 0.810 [0.188]** | S / S / S |
| 75 | 1.000 | 0.998 | 81.2 (81.8), 1.000 | 82.4 (83.0), 1.000 | 67.2 (67.7), 1.000 | S / S / S |
| 100 (B1) | 1.000 | 1.000 | 104.9 (103.6), 1.000 | 111.3 (109.8), 1.000 | 96.9 (95.7), 1.000 | S / S / S |
| 150 | 1.000 | 1.000 | 150.4 (146.1), 1.000 | 154.1 (149.7), 1.000 | 154.7 (150.3), 1.000 | S / S / S |
| 200 (E2) | 1.000 | 1.000 | 207.9 (200.1), retrodiction | 217.7 (209.4), retrodiction | 187.6 (180.5), retrodiction | S / S / S |

(b = 0 and b = 200 on seeds 0-2 are the committed E2 NOBURST and BURST runs, whose outcomes were known before the freeze: retrodictions. B1's sizes 25 and 100 are listed for the seven-point curve; their results were not read.)

**Why the per-seed numbers move.** For b = 40 the burst specs are the first 40 of the seed's burst stream. Seed 0 drew long sessions (mean 17.2 turns; 14 of 40 still alive at turn 23), so its cohort holds 242,600 tokens of live KV 184 s after the burst starts. That is 56.0 average cohorts' worth raw and 53.0 calibrated, just below b_c = 53.4, so seed 0 sits on the committor's steep part (P(STUCK) 0.78). Seed 1 (46.9) is below the committor's 50% point (49.5). Seed 2 drew short sessions (mean 12.5 turns). The plan's realized background is 21,000 tokens below its mean at seed 0's peak (band P(STUCK) 0.43). The per-seed calls are sensitive to how a realized plan is mapped to X0, and the bands are wide.

**Bracketing rule.** Primary, seeds independent (a shared-susceptibility coupling of b40 and b60 within a seed gives the same 0.656): P(b40 GOOD ≥ 2/3) = 0.656 from per-seed P(GOOD) = 0.219 / 0.632 / 0.900, and P(b60 STUCK ≥ 2/3) = 1.000 (per seed 1.000 / 1.000 / 0.810). **P(rule) = 0.66.** Bands (calibrated): lockstep 0.73, 2.5 s service 0.63, realized background 0.88. Raw (uncalibrated) bands: time maximum 0.42 (the pre-review primary), lockstep 0.23, 2.5 s service 0.37, realized background 0.78. So the range is **0.42 to 0.66 depending on how a plan is mapped to the cohort size** (0.23-0.88 over every band), while the frozen exchangeable layer gives 0.94 (0.947 if every non-trapped run counts as GOOD, the remedy plan's figure). The composition-averaged value for three random seeds (plans unknown) is 0.84 (realized-background band 0.67; uncalibrated 0.78). A's deterministic crossing gives b40 GOOD 3/3 and b60 STUCK 3/3, so it predicts that the rule holds.

## 2. N2: the H200 cliff bracket (n = 36, 44, 52)

Values come from the frozen curve functions, evaluated on exactly the grid of `analysis.theory.predict`. They equal the frozen JSON curves (maximum difference 0 for every variant).

| variant | n_half fluid / F1 | n_b | hit(32) fl / F1 | hit(36) fl / F1 | hit(40) | hit(44) fl / F1 | hit(48) | hit(52) fl / F1 | μ(36) fl / F1 | μ(44) fl / F1 | μ(52) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **h200_300k (primary)** | 37.32 / 36.52 | 41.31 | 0.696 / 0.690 | **0.564 / 0.527** | 0.265 / 0.277 | **0.000 / 0.083** | 0.000 / 0.013 | **0.000 / 0.002** | 0.359 / 0.348 | 0.197 / 0.221 | 0.197 / 0.197 |
| ratiofit (s = 2.703) | 37.20 / 36.38 | 41.12 | 0.696 / 0.688 | 0.560 / 0.521 | 0.240 / 0.264 | 0.000 / 0.076 | 0.000 / 0.012 | 0.000 / 0.002 | 0.354 / 0.343 | 0.194 / 0.216 | 0.194 / 0.195 |
| lamratiofit (s = 2.761) | 37.38 / 36.57 | 41.40 | 0.697 / 0.690 | 0.566 / 0.530 | 0.276 / 0.283 | 0.000 / 0.086 | 0.000 / 0.013 | 0.000 / 0.002 | 0.362 / 0.351 | 0.198 / 0.223 | 0.198 / 0.199 |
| decode2 | 37.00 / 36.30 | 41.46 | 0.691 / 0.683 | 0.549 / 0.516 | 0.256 / 0.272 | 0.000 / 0.083 | 0.000 / 0.012 | 0.000 / 0.002 | 0.338 / 0.331 | 0.199 / 0.221 | 0.199 / 0.199 |
| e0a2 (pessimistic) | 36.43 / 35.94 | 41.74 | 0.680 / 0.671 | 0.521 / **0.497** | 0.242 / 0.262 | 0.000 / 0.082 | 0.000 / 0.012 | 0.000 / 0.002 | 0.305 / 0.302 | 0.202 / 0.220 | 0.202 / 0.203 |

- **Rule** "T3(c) supported iff hit(36) ≥ 0.5 and hit(44) < 0.5" holds in 9 of the 10 variant × estimator cases; it fails only under e0a2 with F1.
- **Probability (declared error model).** The measured crossing is taken as N ~ Normal(n_half, σ), with P(rule) ≈ P(36 < N < 44) because the hit curve is monotone on every variant. σ is the RMS error of the fluid n_half on the three validated cells: errors −0.67 (300k), +0.32 (native) and +2.65 (vLLM), σ = 1.59. This gives **P = 0.80** for the primary. With σ = 0.53 (the two SGLang cells only) it is 0.99. With the F1 crossing as the center it is 0.63 (σ = 1.59) or 0.84 (σ = 0.53). Over all variants the range is 0.46-1.00, the lowest being e0a2 under F1. P(hit(44) < 0.5) is 1.000 in every case, so the rule turns on hit(36).
- **Rival.** The capacity ratio M/E_S = 27.76 (M/E_lb = 28.46) puts the crossing near 28-30 and predicts hit(36) < 0.5. A measured hit(36) ≥ 0.5 refutes it, and hit(36) < 0.5 refutes T3(c).
- μ is the turns-based estimator. The freeze record expects it to come out 4-12% high on the H200 (Assumption MF has a negative margin there). At n = 44 and 52 the predicted Stage C synchronized-start value equals the stationary all-miss rate, 0.197.

## 3. TOOLSLOW: a temporary tool-latency increase (remedy N3)

**Protocol** (remedy plan; not yet registered): 300k cell, 1.35× NOBURST arrivals, which are common random numbers with the E2 NOBURST arm. Every tool call that *starts* in [1200, 2100) s sleeps its drawn Z plus δ, with δ ∈ {10, 30} s. The run lasts 8700 s, with the E2/B1 endpoints over [5700, 8700) s.

**Driver** (`toolslow.py`; frozen functions only):
- *New input.* During the slowdown the tool time is Z + δ, a shifted exponential: the protocol's law. It is implemented as a `Workload` subclass that overrides only the law's F, E[min(Z, r)], mean, density at 0 and inverse. With δ = 0 it reproduces the frozen curve exactly (test). A follow-up hits only if R > δ + Z, so hits need an eviction age longer than δ.
- *Quasi-static time-varying driver* (A5 with a switched curve): n(1200) = n1(λ) = 8.47; dn/dt = λ − μ(n; δ) on [1200, 2100); dn/dt = λ − μ(n; 0) afterwards.
- *Verdict.* STUCK iff n(2100) > n_u(λ) = 32.23 of the normal curve.
- *Stochastic layer.* P_slow is the frozen F2 escape on the slowed curve over 900 s (target its n_b(δ); band: the normal n_u). After the switch, the frozen committor of the normal curve from X0 = n(2100), plus the F2 background escape. P(STUCK) = P_slow + (1 − P_slow)(q0 + (1 − q0) P_esc).

| δ (s) | slowed curve: μ_max, n1, n_u, n_b | hit at n1 | n(2100) | fluid verdict | P(escape while slowed) | committor after | **P(STUCK) / P(GOOD)** | per-seed X0 at 2100 s (plan walk) |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.1164, 21.76, 30.78, 42.6 | 0.932 | 21.5 | GOOD | 0.285 (band 0.41) | 0.004 | **0.29 / 0.71** (band 0.41 / 0.59) | 22, 15, 15 |
| 30 | 0.0718 (= μ_b < λ), none, none, 62.4 | n/a | 46.9 | STUCK | n/a (no good state) | 1.000 | **1.00 / 0.00** | 49, 37, 39 |
| 16.8 (δ*) | 0.0847, none, none, 49.3 | n/a | 32.24 | boundary | n/a | 0.87 | 0.87 / 0.13 | 27, 26, 25 (good-service walk: an underestimate) |

- **Critical delta.** Above **δ = 13.7 s** the slowed curve's peak falls below λ = 0.0966 and no good state exists during the slowdown. The bottleneck passage still needs time, so the fluid critical value is **δ* = 16.8 s** (16.7 s if the switch is taken at 2100 + δ). With an exponential law of the same mean (5 + δ), δ* lies between 18 and 20 s. That law keeps short gaps, which the shifted law removes.
- **Stochastic 50% point (frozen for a later δ sweep).** At δ* the stochastic layer already gives P(STUCK) = 0.87, so its 50% point is lower: **δ_50 = 16.4 s** (primary, last upward crossing, on a 0.25 s grid). The band with escape target n_u first crosses 0.5 at **11.4 s**. The layer is *not monotone* in δ. For δ in (13.7, 16.8) there is no slowed good state: P_slow is set to 0 and no noise is added during the passage, because the fluid n(2100) carries the state. So P(STUCK) drops at 13.7 s, from 0.44 to 0.05, and then rises along the committor of n(2100): 0.29 at 16.0 s, 0.56 at 16.5 s, 1.00 from 17.0 s. The drop is an artefact of that approximation. A δ sweep is scored against δ_50 = 16.4 s, with 11.4-16.8 s as the band. The full scan is in the YAML (`toolslow.p_stuck_scan`).
- The remedy plan's Little's-law arithmetic (n ≈ 22 at δ = 10, δ* ≈ 18 s) leaves out that hits need R > δ. The model agrees with it at δ = 10 for the fluid state, but the slowed peak is only 1.21 λ at δ = 10, hence the 0.29 escape risk.
- **Secondary** (plan walk, deterministic). The most sessions alive during the δ = 10 slowdown are 28 / 27 / 23, all below the slowed n_u = 30.8. No seed crosses.
- **Rule** (δ = 10 GOOD ≥ 2/3 and δ = 30 STUCK ≥ 2/3): **P = 0.80**, from per-seed P(GOOD at δ = 10) = 0.709 / 0.712 / 0.712. The band (escape target n_u) gives 0.63.

## 4. SHED and Proposition S (remedy N4)

**Proposition S** (shedding; quasi-static A5, fold-free unimodal curve; λ in (μ_b, μ_max)). Let the system be at x0 > n_u(λ). Cut the arrival rate to λ' < λ for a time τ, then restore λ.
- (a) If λ' < μ_b (= λ_miss, the minimum of μ on [n_u, x0], by A4), n decreases strictly during the cut and reaches n_u(λ) after τ_min(λ') = ∫_{n_u}^{x0} dn / (μ(n) − λ'). The system is rescued (n → n1 after restoration) iff τ > τ_min. At τ < τ_min, n(t0 + τ) > n_u and the trap resumes.
- (b) If x0 ≥ n_b and λ' ≥ μ_b, no τ rescues.
- (c) The cut refuses (λ − λ')τ_min arrivals at the least. That number increases with λ', since d/dλ' [(λ − λ')/(μ_b − λ')] = (λ − μ_b)/(μ_b − λ')² > 0, so the full stop (λ' = 0) refuses the fewest: λ τ_min(0). A cap c ∈ (n1, n_u) (T9) refuses none.
- *Proof.* Under (a), dn/dt = λ' − μ(n) < 0 on [n_u, x0], so the time from x0 to n_u is ∫ dn/|dn/dt|. After restoration, dn/dt = λ − μ(n) is < 0 on (n1, n_u) and > 0 on (n_u, ∞) (T7: fold-free, unimodal), which gives both directions. Under (b), dn/dt = λ' − μ_b ≥ 0 on the all-miss branch. (c) is the displayed derivative. ∎

**Numbers** (300k, 1.35×; x0 = n(1800) = 161.3, from the frozen round robin, = R1's n_on):
- τ_min = **1,795 s** (λ' = 0): 1,790 s on the all-miss branch and 5.5 s from n_b = 32.70 to n_u = 32.23.
- Partial cuts: 2,393 s (λ' = 0.25 μ_b), 3,589 s (0.5), 7,175 s (0.75). The minimum refused count is λ τ_min = 173 sessions.
- *Composition-aware band.* The frozen round-robin recursion is re-run with arrivals taken from a function. With a constant rate it equals `round_robin_trap` exactly (asserted). With λ = 0 from 1800 s, the population reaches n_b at 3,722 s, so τ_min = **1,928 s**. The young backlog first completes 1.71 λ_ref sessions/s, but with no fresh arrivals it ages, down to 0.034/s at n_b (mean 0.067 < μ_b). The remedy plan's "about 1,450 s if the young-backlog rate persists" therefore does not hold: the rate does not persist.
- *Per seed* (the recursion fed with the plan's own post-1200 s arrivals, each with its own turn count, on the fluid background n1): x0 = 179.1 / 178.1 / 171.1 and τ_min ≈ 2,265 / 1,989 / 1,837 s.

| τ (s) | resume at | n at resume: quasi-static / round robin | verdict | P(STUCK) / P(GOOD) | per seed (plan round robin) | sessions refused, expected (seeds 0 / 1 / 2) |
|---|---|---|---|---|---|---|
| **600** | 2400 | 118.2 / 102.6 | **STUCK** | 1.00 / 0.00 | STUCK, STUCK, STUCK (n 113, 118, 101) | 57.9 (59 / 56 / 61) |
| **3600** | 5400 | 0 / 0 (drained by about 3,600-4,060 s) | **GOOD** | 0.0005 / 0.998 | GOOD × 3 | 347.7 (355 / 378 / 377) |
| 1800 (optional) | 3600 | 31.7 / 37.3 | near-critical | 0.74 (quasi-static) to 1.00 (round robin) | STUCK × 3 (n 48, 41, 37) | 173.8 (184 / 194 / 188) |

- The committor's 50% point is X = 30.8, reached at τ = 1,807 s (quasi-static) or 1,940 s (round robin).
- After a full drain (τ = 3600), the system restarts from empty at 1.35×, and the F2 escape before the GOOD threshold is 0.002.
- Refused counts come from the exact ramp plans (`arrivals.kind: ramp`, knots as in the remedy and in the registrations of `b006291`). The kept base arrivals are a subset of the BURST arm's, and the refused ones are exactly the BURST arm's base arrivals in the stop window (checked). They are fixed by the client plans, so they are a **protocol check** of the run (the registered "sessions shed" count), not a model prediction.
- The R1 cap refuses none. It defers them, with the frozen release at 3,830 s at 1.35×.
- **Registered rule** (`configs/agentload_prereg_2026-10-31_shed_t{600,3600}.yaml`, commit `b006291`, read as protocol only): τ = 600 STUCK and τ = 3600 GOOD in ≥ 2/3 of the registered seeds 0 and 1, i.e. 2 of 2 each. **P = 1.00² × 0.998² = 0.997.** Seed 2 above is a prediction for an unregistered run; with three seeds the value is 0.995.

## 5. E0F: fresh-seed E0b (seeds 3-5)

**Rule** (`configs/r11_basin_predict.yaml`, commit `c600fd7`): stable := not aborted, final queue < 50, and OLS rise of the 100 s queue means over the last 1500 s ≤ 10. Replicated iff 2.0× is stable 3/3 and 2.5× is unstable in ≥ 2/3.

| | 2.0× (λ = 0.1431) | 2.5× (λ = 0.1788) |
|---|---|---|
| **per-seed P(unstable), frozen F2 (primary)** | **0.150** | **0.691** |
| binomial P(k = 0, 1, 2, 3 unstable) | 0.614, 0.326, 0.058, 0.003 | 0.030, 0.198, 0.443, 0.330 |
| realized rate, seeds 3 / 4 / 5 (exact plans) | 2.013 / 2.148 / 1.971 | 2.512 / 2.665 / 2.470 |
| F2 at the realized rate (band) | 0.160 / 0.280 / 0.131 | 0.703 / 0.839 / 0.658 |
| Poisson-binomial (band) | 0.526, 0.384, 0.085, 0.006 | 0.016, 0.156, 0.440, 0.388 |
| A's level crossing on the exact plan (secondary) | stable × 3 | stable × 3 |
| seed 0 (retrodiction; known 2.0× stable, 2.5× unstable) | realized 2.199, F2 0.335, A stable | realized 2.726, F2 0.878, A **unstable** (crossing at 1,464 s) |

- **P(replicated)** = 0.614 × 0.772 = **0.47** (primary). The realized-rate band gives 0.44.
- A's crossing predicts **not replicated**. That is also the frozen r11 simulator prediction (2.5× stable 3/3 on seeds 3-5), and A's crossing retrodicts seed 0 correctly.
- The frozen F2 values are reproduced exactly (asserted against `a100_300k.json`).
- *Horizon approximation.* The primary is the frozen F2 escape over the full 3000 s. A run that escapes only in roughly the last 100-150 s cannot reach "final queue ≥ 50 or rise > 10" by 3000 s, so P(unstable) is slightly overstated. The effect is small, and the value is kept at the frozen one.

## 6. Proposition E and Corollary C

**Proposition E** (exogenous reuse gaps cannot produce the cliff; exact, one line). Let the follow-up reuse gap be exogenous: the tool time Z, with no queue wait. Let K ≥ 0 tokens be held by running requests. Then the characteristic time T of M − K = λ0 [A1 E[min(Z, T)] + E[E_T] T] satisfies T ≥ (M − K)/(λ0 E[T] Ē). This is Yao et al.'s Theorem 3.1 at K = 0, and the frozen model's balance at W = 0. It holds because E[min(Z, T)] ≤ T and A1 + E[E_T] = E[T] Ē (a test checks the identity). Hence h ≥ F_Z((M − K)/(λ0 E[T] Ē)). A measured follow-up hit h_meas at throughput λ0 therefore needs K ≥ M − λ0 D(F_Z⁻¹(h_meas)): the non-idle KV must fill the pool. Under FCFS admission that happens only with a queue (A4), so the queue term is necessary. ∎

Evaluated on the measured cells (no parameter fitted; the measured turns-based throughput serves as the closures' exogenous rate):

| cell, n | measured hit (mean queue) | Yao Thm 3.1 at measured λ0 | Yao closed by Little, no service | Che, W = Z (objects of size Ē) | bound, K = 0 | K needed / M | frozen merged model fluid (F1) |
|---|---|---|---|---|---|---|---|
| 300k, 32 | 0.505 (7) | 0.932 | 0.723 | 0.827 | ≥ 0.899 | 0.83 | 0.371 (0.357) |
| 300k, 48 | **0.000** (24) | 0.932 | 0.499 | **0.551** | ≥ 0.930 | 1.000 | 0.000 (0.001) |
| 300k, 96 | **0.000** (66) | 0.932 | 0.254 | 0.276 | ≥ 0.927 | 1.000 | 0.000 |
| 300k, 300 | **0.000** (269) | 0.932 | 0.082 | 0.088 | ≥ 0.903 | 1.000 | 0.000 |
| native, 96 | 0.419 (13) | 0.932 | 0.761 | 0.878 | ≥ 0.932 | 0.957 | 0.000 (0.355) |
| native, 128 | **0.007** (44) | 0.932 | 0.590 | 0.659 | ≥ 0.932 | 0.9995 | 0.000 |
| vLLM, 16 / 20 / 24 / 28 | 0.932 / 0.926 / 0.879 / 0.658 | 0.932 | 0.932 / 0.929 / 0.889 / 0.806 | 0.932 | | 0.33 / 0.30 / 0.41 / 0.76 | 0.932 / 0.932 / 0.910 / 0.812 |
| vLLM, 32 / 40 / 48 | 0.083 / 0.007 / 0.000 | 0.932 | 0.723 / 0.592 / 0.499 | 0.827 / 0.662 / 0.551 | ≥ 0.93 | 0.987 / 0.999 / 1.000 | 0.441 / 0.000 / 0.000 |
| vLLM, 96 / 300 | 0.000 / 0.000 | 0.932 | 0.254 / 0.082 | 0.276 / 0.088 | ≥ 0.91 | 1.000 | 0.000 |

- The exogenous closures decay smoothly in n (Che: ∝ 1/n beyond M/Ē = 28.4) and never reach the measured zeros. The model with the queue term does.
- The reviewer's "0.55 at n = 48" is the Che row.
- Two points are missed by the merged model too: vLLM at n = 32 (0.441 against 0.083; the known vLLM partial miss) and native n = 96 (fluid 0.000 against 0.419; F1 0.355).

**Corollary C** (exact, from T3(b)): n_b − M/E_S = ν_b z̄ (1 − 1/E[T]) = λ_miss z̄ (E[T] − 1). Any predictor of the collapse from capacity over a per-session footprint (M/Ē, Denning's M/E_lb, AgentKV's or MISA-T's M/E_S) understates the all-miss onset by the sessions in tool calls at the all-miss rate. That gap grows linearly with GPU speed (T3(c)) and with tool time.

| cell | M/Ē | M/E_lb | M/E_S | n_b (gap = tool-call part) | n_half fluid | measured crossing [grid bracket] | errors vs measured: M/E_S, M/E_lb, n_b, n_half |
|---|---|---|---|---|---|---|---|
| A100 300k | 28.39 | 28.45 | 27.76 | 32.70 (4.94) | 31.49 | 32.16 [32, 48] | −4.41, −3.72, +0.53, −0.67 |
| A100 native | 90.43 | 90.57 | 89.79 | 94.86 (5.07) | 93.74 | 93.42 [80, 96] | −3.64, −2.85, +1.44, +0.32 |
| vLLM 300k | 28.39 | 28.45 | 28.22 | 32.83 (4.61) | 31.75 | 29.10 [28, 32] | **−0.88, −0.65**, +3.73, +2.65 (capacity ratio closer: disclosed) |
| pool 150k (blind) | 14.19 | 14.23 | 13.59 | 18.32 (4.73) | 16.91 | pending | rival: 13.6 |
| pool 600k (blind) | 56.77 | 56.88 | 56.13 | 61.17 (5.04) | 60.03 | pending | rival: 56.1 |
| H200 (blind; 4 variants) | 28.39 | 28.46 | 27.76 (27.76-27.83) | 41.31 (13.55; 41.12-41.74) | 37.32 (36.43-37.38) | pending | rival: 27.8 |
| Llama-3.1-8B (blind, a priori) | 28.39 | 28.44 | 27.76 | 32.02 (4.26) | 30.92 | pending | rival: 27.8 |

**Rival scoring, declared now** for the blind cells: when a cell's Stage C is read, the predictor nearest the measured 0.5-hit crossing wins (M/E_S, M/E_lb, or the frozen n_half). T3(b)'s tool-call term is supported iff the measured crossing exceeds M/E_S by more than half of n_b − M/E_S: 15.96 (150k), 58.65 (600k), 34.53 (H200), 29.89 (Llama).

## 7. Conditional predictions at the H200 and Llama registered points

This implements the frozen `registration_conditional_rule` (scoring.yaml). Once a cell's E2 registration is pushed, run from a clone at this pred2 commit (its `analysis/theory` code is the frozen tag's plus new files):

```
PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell h200_300k --registration configs/agentload_prereg_<date>_h200.yaml
PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell llama31_8b_300k --registration configs/agentload_prereg_<date>_llama31.yaml
```

- **Fields read.** Only `lambda_selection.lambda_mults` and `measured.n_cap`; for Llama also `measured.lambda_ref` and `measured.all_miss_uncached_tokens_per_s`, the measured E0a.
- **Derived specs.** One spec is written per variant under `results/theory/pred2/conditional/`. Its base is the frozen spec, and it changes only `e2.multiples`, `e2.cap` and `tests`; Llama also sets `lambda_ref`, plus a second variant with `fit_speed_to_e0a` set to the measured tokens.
- **Output.** The frozen `analysis.theory.predict` is run on each derived spec and writes `<cell>_conditional[_fit].json`. Each carries a `conditional` block: the registration path, its sha256, the fields read and the rule.
- **Variants.** H200 runs the primary and the four frozen band variants, about 40 s each.
- **Manual form.** `--mults 1.10 1.15 --cap 32` (Llama: add `--lambda-ref` and `--tokens`).
- **Self-test.** With the model's own registration consequence it reproduces the frozen `h200_300k.json` E2 block exactly. The Llama path ran end to end in quick mode.
- **Committing its outputs.** `results/` is git-ignored: after a run, commit `results/theory/pred2/conditional/*.json` and `*.yaml` with `git add -f`, before the cell's E2 result is read.
- For Llama the a-priori trapped-state table of §8 covers 1.35-2.5× at the frozen λ_ref; the recipe stays the binding prediction at the registered points, because it uses the measured E0a λ_ref and token rate.

## 8. Blind lookup tables (remedy 2a.2, 2a.3, 2a.4, 2a.7)

Driver `blind_tables.py`: frozen functions only, called as `predict.py` calls them. Output: `results/theory/pred2/blind_tables.json` and `h200_600k.json`; the YAML block `blind_tables` carries the headline values and the primary tables.

**2a.2 `h200_600k`** (new spec `analysis/theory/cells/h200_600k.yaml`: `h200_300k` with a 600,000-token pool; zero new fitted parameters; frozen `predict.py` unchanged; for the contingent N6):
- closed curve: peak at n = 53.7, μ_max 0.634 (3.27 λ_ref, against 1.95 at 300k); 0.5-hit crossing **66.6 (fluid) / 64.8 (F1)**; n_b **69.9**;
- hit fluid / F1 at n = 56, 60, 64, 68, 72: 0.805 / 0.789, 0.739 / 0.700, 0.631 / 0.550, 0.373 / 0.336, 0.000 / 0.147;
- F2 edge 2.57× (P(escape) 0.37 at 2.5×, 0.97 at 3.0×), bracket [2.5, 3.0]; A's criterion 2.74×;
- registration consequence: points 1.5 and 2.0×, cap 48; b_stat 46.2 / 36.6, b_c 114.3 / 90.6;
- capacity ratio M/E_S = 56.1, so Corollary C's gap is 13.8 sessions.

**2a.3 Trapped-state tables.** Per multiple: n1, n_u, b_stat, NOBURST hit, trapped backlog, token ratio, gap/R, R, b_c and the capped drain at caps 20-32 (step 2). Coverage: H200 (primary and the four band variants) at 1.05-1.65×, Llama-3.1-8B (a priori) at 1.35-2.5×, both in 0.05 steps.
- H200 primary: at 1.10 / 1.15×, backlog 171 / 208, token ratio 1.021 / 1.022, gap/R 5.9 / 7.1, capped drain 1,125 / 1,201 s at cap 32. At 1.65×, backlog 599 and gap/R 17.6. The frozen E2 arms (1.10 / 1.15×) are reproduced.
- Llama: at 1.35 / 1.65×, backlog 204 / 282, token ratio 1.006 / 1.015, gap/R 6.5 / 8.3 (equal to the frozen arms).
- Above the window (λ ≥ μ_max) the row lists the trapped state from n1 = 0 and marks every run as stuck.

**2a.4 Rivals per blind cell** (no measured input): the capacity ratios and n_b of Corollary C, plus two exogenous-gap closures at every integer n. Che with W = Z crosses hit 0.5 at 26.5 (150k), 105.8 (600k and h200_600k) and 52.9 (H200 and Llama). Yao closed by Little's law crosses at 23.9, 95.8 and 47.9. Against the frozen n_half of 16.9, 60.0 / 66.6, 37.3 and 30.9, these are Proposition E's prediction that the exogenous closures put the 0.5-hit crossing 28-76% above the cliff on every blind cell (smallest: Yao-Little on the H200, 47.9 against 37.3). b_stat is listed at every table multiple and at the frozen E2 points (600k pool: 45.9 / 35.0 at 2.15 / 3.35×).

**2a.7 Pool-sweep lookups.** The per-job n of Stage C 17168864-69 and the multiples of E0b 17168870-81 are set on Nova and were not readable here. So `a100_pool150k`, `a100_pool600k` and `h200_600k` are tabulated at every integer n from 2 to 1.3 n_b (plus 192 and 300; fluid and F1), and the F2 escape at every multiple from 1.01× in 0.01 steps up to the fluid window. Any registered integer n or two-decimal multiple is then a lookup. Both tables equal the frozen JSON at its own points (difference 0).

## Blindness scope

**Read for this set:**
- the repo `CLAUDE.md`;
- `notes/THEORY_r13_merged.md`, `notes/PREDICTIONS_r13_theory.md`, `notes/PAPER_INPUT_theory.md`, `notes/THEORY_r13_scoring.md`, `configs/r13_theory_predict.yaml`, and the first section of `notes/THEORY_r13_fluid_rigorous.md`;
- the code under `analysis/theory/`, and the frozen prediction and validation JSONs in `results/theory/merged/`. These carry the three measured cells' values, which the freeze already used;
- the remedy plan (`scratchpad/novelty2/REMEDY_PLAN.md`);
- the B2 registration commit `621d88f`: its message, and `configs/agentload_prereg_2026-10-31_b40.yaml` (protocol and rule);
- the r11 S1 simulator-prediction commit `c600fd7`: `notes/PREDICTIONS_r11_basin.md`, `configs/r11_predict_basin.yaml`, the E0F part of `configs/r11_basin_predict.yaml`, and the plan builder of `experiments/r11_predict_basin.py`. These are predictions and protocol, written before any B1 or E0F run existed;
- the client code `src/agentload/{workload,config}.py`, `configs/agentload_e2_burst.yaml`, `configs/agentload_e0_cap.yaml` and `prereg/inputs/2026-10-23/calibration.json` (the registered λ_ref);
- for the revision only: the r14 registration commits `b006291` (TOOLSLOW/SHED: commit message and the `rule` fields of `configs/agentload_prereg_2026-10-31_{shed_t600,toolslow_d10}.yaml`, the `tool_slowdown` line of `configs/agentload_e2_toolslow_d10.yaml`), `19c58e9` and `db24efa` (commit messages: analysis-side eligibility fixes, no change of rule or endpoint); line 34 of `Nova-Research-wt/COORD/COORDINATION.md` (the pool sweep's labels and job ranges; the per-job n and multiples are set on Nova and were not read); the adversarial check's scratch scripts. All are protocol, written before any of these runs existed;
- for Proposition E only, the three measured Stage C files of the frozen measured cells: `results/nova/stageC_1706210x_pulled_20261022-125454/.../mu_curve.csv`, `r7_native_grid_vllm_pulled_20261025-145126/.../mu_curve.csv` and `stageC_vllm_1716295x_pulled_20261030-153621/.../mu_curve.csv`. The 300k file also lists the committed round-7 `sglang-lpm-r1` points, which were not used.

**Not read:**
- any result of B1, B2, H200 (beyond the brief's E0a inputs, already frozen), Llama, E0F, LPM-INF, rescue (R1/R4), the pool sweep, TOOLSLOW or SHED. B2, TOOLSLOW, SHED and N2 do not exist yet;
- any other `results/nova` directory, and no other worktree's results. Of `r11/strengthen` only the commit list, the `notes/` file names and the two commits above were looked at;
- Nova: there was no ssh connection.

**Retrodictions inside the tables.**
- The 1.65× seeds 0-2 plans share their base sessions with the committed E2 runs, whose outcomes were known before the freeze (BURST-200 trapped, NOBURST good). The b = 0 and b = 200 per-seed rows are therefore retrodictions.
- E0b seed 0 (2.0× stable, 2.5× unstable) is a retrodiction.
- The H200 operator saw the H200 μ for n = 16-32 before the first freeze (`PREDICTIONS_r13_theory.md`). N2's points (36, 44, 52) were never measured.

## Inputs (every one)

**Model.**
- *Frozen model and parameters:* the A100 server-log cost calibration, the workload of `configs/agentload_e2_burst.yaml`, the pools and λ_ref of the cell specs, F1/F2/F3, the committor, the round robin and the scoring.
- *Not used:* no measured μ(n) point, E0b outcome or E2 outcome enters any blind prediction. Proposition E's table uses the measured Stage C points as the exogenous closures' operating point, and is retrospective by construction.

**Exact client plans.** `agentload.workload.build_open_plan` on the job configs, with:
- the job's seed;
- rate = mult × 0.07153402100919228;
- burst n in 60 s at 1200 s (B2), none (TOOLSLOW, E0F), or 200 plus the ramp knots (SHED);
- durations 8700 s, or 3000 s for E0F.

**Per item.**
- *B2:* the protocol of the registrations; the stuck-by (6,344 s) and good-from (8,274 s) times from the registered thresholds 0.2 / 0.8 and the model's good-state hit 0.932; the calibration factors from synthetic seeds 1000-1399 of the same generator.
- *Blind tables:* the frozen specs; the new `h200_600k.yaml` (pool 600,000 tokens, otherwise `h200_300k`); multiples 1.05-1.65× (H200) and 1.35-2.5× (Llama), step 0.05; caps 20-32, step 2.
- *N2:* the five frozen H200 specs (E0a inputs only); the error-model σ from the frozen `validation.json`.
- *TOOLSLOW:* δ ∈ {10, 30} s; the slowdown window [1200, 2100) s; the shifted-exponential law (protocol).
- *SHED:* τ ∈ {600, 3600} (plus 1800) s; the stop at 1800 s; the remedy's ramp knots.
- *E0F:* the registered rule of `c600fd7`.
- *Corollary C:* the frozen specs of every cell.

## Approximations (stated)

**B2.**
1. The frozen committor layer is a heuristic: a time-dependent cohort mapped onto a one-dimensional diffusion at its demand peak.
2. The new per-seed input is the cohort's live KV under good-state service (1.33 s per turn, no eviction), on the mean background, calibrated multiplicatively per burst size to the frozen layer's scale (E_synth[b_cal] = b). The calibration assumes the plan's excess over an average cohort, not the max-statistic's bias, is what the run feels; the uncalibrated value is the band.
3. GOOD is taken as no escape before 8,274 s; the slope and backlog parts of RECOVERED are not modelled separately.
4. Seeds are independent.
5. Plans use the registered full-precision λ_ref, while the theory uses the spec value 0.071534 (relative difference 3 × 10⁻⁷).

**N2.**
1. The Gaussian error model for the crossing comes from three validated cells.
2. A single Stage C run per n.
3. The F1 / fluid choice is reported as a band.

**TOOLSLOW.**
1. Quasi-static on a switched curve: the internal state relaxes at once at the switches.
2. Only n carries over across the switches.
3. The switch-off lag is up to δ + about 5 s (band).
4. The F2 escape during the slowdown starts from empty on the slowed curve.
5. The per-seed plan walk uses one service time per turn. It underestimates n where the slowed state is all-miss, but that does not affect δ = 30, which is STUCK either way.
6. For δ in (13.7, 16.8) s there is no slowed good state: P_slow = 0 and no noise is added during the passage (the fluid n(2100) is the committor's start). This makes the stochastic layer drop at 13.7 s (§3).

**SHED.**
1. Quasi-static (A5) with μ_b on the all-miss branch.
2. The round robin assumes deep congestion (gap = cycle), and the trap releases at n_b of the stationary mix.
3. The per-seed round robin uses the fluid background n1 at 1200 s and the plan's arrivals afterwards, with exact turn counts.
4. After a drain, the system restarts from empty with F2.

**E0F.**
1. F2 is exchangeable.
2. The realized-rate band keeps F2's arrival noise.
3. A's criterion uses the good-state service at n1 and q_final = 50.
4. The F2 escape counts escapes up to 3000 s, including late ones that cannot meet the queue criterion by then (§5).

**Blind tables.** The frozen functions, as `predict.py` calls them for a registered arm or grid point; the Llama table is at the a-priori λ_ref and cost model; the pool lookups replace the unknown per-job grids by every integer n and every 0.01 multiple.

**Proposition E.** The closures are evaluated at the measured throughput; Che's objects have the mean footprint and no dead content; the Little closure has zero service time. Each choice is the one most favourable to hits, except the bound.

## Scoring, declared now (frozen with this file)

- **B2.**
  - The primary is the per-seed plan-conditional P(STUCK) and P(GOOD) above.
  - Report the log-likelihood (probabilities floored at 10⁻³) and the Brier score of the nine (seed, b) STUCK outcomes, and separately of the nine GOOD outcomes, for the primary, each band, the frozen exchangeable layer and A's deterministic labels.
  - The theory-specific claims are three. Seed 0 is the most trap-prone at b = 40 and seed 2 the least. Seed 2's b40 is GOOD (0.90) and seed 2's b60 STUCK (0.81). P(rule) = 0.66 (uncalibrated band 0.42).
  - The calibrated and the uncalibrated mapping are both scored (log-likelihood and Brier), so the data say which mapping is better.
  - The deterministic b_c = 53.4 and the committor's 49.5 are tested by the dose-response curve as a whole.
- **N2.**
  - P(rule) = 0.80 (primary).
  - hit(36) < 0.5 supports the capacity-ratio rival over T3(c).
  - hit(44) ≥ 0.5 refutes T3(b)/(c), as in the frozen hit(48) rule.
  - μ(36) is scored with the frozen ±10% tolerance on the turns-based estimator.
- **TOOLSLOW.** P(rule) = 0.80. δ = 10 STUCK on ≥ 2/3 seeds would refute the fluid layer only together with a measured slowed-curve peak above 1.21 λ. For a later δ sweep: the stochastic 50% point δ_50 = 16.4 s (band 11.4-16.8 s; fluid δ* = 16.8 s).
- **SHED.**
  - Registered rule (seeds 0, 1): τ = 600 STUCK and τ = 3600 GOOD on both, P = 0.997. Either failing refutes Proposition S's quasi-static form.
  - The refused counts (59 / 56 and 355 / 378 on the registered seeds 0 / 1) are a protocol check: a mismatch means the run did not follow its plan, not that the model failed.
- **E0F.** P(replicated) = 0.47. Report the log-likelihood of the six outcomes under F2, the realized-rate band and A's crossing, and quote the realized rates.
- **Corollary C.** The rival rule above.
- **Blind tables.** No new rule. A registered point of the H200, Llama, pool-sweep or H200 600k cells is scored with the frozen rules at the tabulated values. When a cell's Stage C is read, the exogenous-gap curves (Che, Yao-Little) are scored beside the frozen curve, by the same nearest-crossing rule as Corollary C.

## Checks run

- **Frozen code unchanged.** `common.frozen_code_unchanged()`: no tracked file under `analysis/theory` differs from `997d2c4`, and only new files exist.
- **Exact reproduction of frozen outputs:**
  - the frozen B1 rows (maximum difference 0);
  - the frozen H200 curves, all five variants, fluid and F1 (maximum difference 0);
  - the frozen F2 E0b probabilities (asserted);
  - the frozen round robin, by its time-varying copy (maximum difference 0);
  - the frozen H200 E2 arms, by the conditional recipe (0 of 102 values differ);
  - the frozen E2 arms of h200_300k, its band variants and Llama, by the trapped-state tables at the same multiples and cap (maximum difference 0);
  - the frozen pool-sweep curves and 0.05-step escape probabilities, by the integer-n and 0.01-step lookups (maximum difference 0, also for h200_600k against its own predict output).
- **B2 calibration.** The raw statistics reproduce the pre-review values (maximum difference 3 × 10⁻¹⁴; P(rule) 0.421, composition-averaged 46.6), and E_synth[b_cal] = b by construction. Re-running every other driver after the revision changes no pre-review value; it only adds the new fields.
- **PlanRNG.** Feeding the frozen `_live_paths` through `PlanRNG` gives arrays identical to its own random draws (test).
- **Plans.** Plan CRN properties hold: the base sessions of every burst size equal the NOBURST plan's, and the burst cohort equals the plan's burst sessions. The SHED ramp plan keeps a subset of the constant plan's arrivals.
- **Tests.** `tests/test_theory_pred2.py` 11 passed. Together with the frozen theory tests (`tests/test_theory_{r13_freeze,predict,fluid_rigorous,che_endogenous,paper}.py`), 83 passed.

## Files

- `analysis/theory/pred2/*.py` (new), `analysis/theory/cells/h200_600k.yaml` (new), `tests/test_theory_pred2.py` (new);
- `configs/r13_theory_pred2.yaml` (generated), this file;
- `results/theory/pred2/*.json`, and `results/theory/pred2/conditional/` once a registration exists (force-add both).

## Freeze record (follow-up commit; nothing above this section changed after the tag)

- Freeze commit `cfa77127dbcbea285d5f44b6c7195d02019bf831`, annotated tag `r13-theory-pred2` (tag object `6f0b5043488a334494f91f25e6fbf04e5ed5770c`).
- GitHub push time of branch `r13/pred2` at that commit: **2026-10-31T09:20:20Z (04:20:20 CDT)**, from `gh api repos/AkshatValse/Nova-Research/activity` (activity_type branch_creation, after = cfa7712). The tag was pushed immediately afterwards (local clock 2026-10-31T09:20:20Z). The activity API does not list tag pushes; `gh api repos/AkshatValse/Nova-Research/git/refs/tags/r13-theory-pred2` resolves to the tag object above.
- Tests at the freeze: `tests/test_theory_{pred2,r13_freeze,predict,fluid_rigorous,che_endogenous,paper}.py`, 83 passed.

## Erratum (2026-10-31, after the freeze; nothing above changed)

Lines 3, 9, 241 and 248 above say, or imply, that pred2 was pushed before the first N2 job, and line 241 that the N2 points did not exist yet. That is wrong for N2. The H200 closed runs at n = 36, 44 and 52 (jobs 17169612-17169614) were submitted at 02:33:06 CDT, started at 02:39, 02:50 and 03:15, and ended between 03:25 and 04:01 CDT (`notes/LOG.md`, H200 extra Stage C entry; `paper/sections/appendix.tex`, timeline), all before pred2's push at 04:20:20 CDT. Their predictions in the earlier freeze `r13-theory-pred` (pushed 02:05:30 CDT, before submission) are blind in time; pred2's N2 table is **not** blind in time. The predicting agents had no Nova access and did not read those runs (see "Not read" above), so pred2's N2 table is blind by access only. The B2, TOOLSLOW and SHED jobs were submitted at 04:21:40-04:21:43 CDT, after the push, so the statements above hold for them. The E0F runs (jobs 17168506-17168507) had also ended before the push (03:54:12 and 04:01:04 CDT, `results/nova/b1_e0f_1716850x_pulled_20261031-040517/sacct_17168500-17168507.txt`), so pred2's E0F table (section 5) is likewise blind by access only, not in time.
