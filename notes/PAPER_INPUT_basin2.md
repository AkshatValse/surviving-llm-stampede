# Paper input: B2 / BASIN-2 (basin dose-response at 1.65 ×: bursts of 40, 50 and 60 sessions)

Written 2026-10-31 for the lead. Every number below comes from files in the worktree of branch `r11/strengthen` (HEAD `4dd21e0`; the B2 pull, the two scripts and this note are not yet committed) or from the frozen prediction files at tag `r13-theory-pred2`. The pull is `results/nova/b2_1716989x_pulled_20261031-154500/` (abbreviated **B2P**). Commands, the archive hash, the job-to-run map and the cross-checks are in `B2P/COMMANDS.txt`. Narrative: `notes/LOG.md`, entry 2026-10-31 "BASIN-2 bracketed". The BASIN-1 counterpart is `notes/PAPER_INPUT_basin.md`.

## Verdict

**BASIN-2: bracketed. The registered rule holds; all three seeds agree on n = 40 and on n = 60.**
- With a burst of 40 sessions the server is GOOD in 3/3 seeds (trap_v2 RECOVERED; hit 0.934 / 0.934 / 0.925 over [5700, 8700) s).
- With a burst of 60 sessions it is STUCK in 3/3 seeds (hit 0.000), and trap_v2 calls all three TRAPPED.
- With 50 sessions, which the rule does not use: seed 0 GOOD (0.933), seed 1 STUCK and TRAPPED (0.000), seed 2 GOOD (0.924).
- The registrations are `configs/agentload_prereg_2026-10-31_b40.yaml`, `_b50.yaml` and `_b60.yaml`, all FILLED, at tag `r14-basin2-reg` (`621d88f`). The commit is from 01:58:38 CDT; GitHub records the branch push of that commit at 07:10:48Z = 02:10:48 CDT (the tag's own push time is not observable; see Blindness). The nine jobs were submitted at 04:21:40-41 CDT, 131 minutes later. `registration_diff` against the 2026-10-24 parent has an empty `forbidden` list for all three files.
- Every run is bound to its registration (`prereg_bound` True), counted (`b2_counted` True), and `b2_not_counted`, `endpoint_problems` and `window_mismatch_runs` are empty.
- Along the seven sizes 0, 25, 40, 50, 60, 100 and 200, every seed switches from GOOD to STUCK exactly once. The edge is in (50, 60] for seeds 0 and 2 and in (40, 50] for seed 1.

**Against the frozen predictions (pred2, blind in time):** the rule held (P(rule) = 0.66). The **primary** per-seed probabilities put the observed state on the less likely side in two of nine runs, both seed 0: P(STUCK) = 0.78 at 40 and 0.86 at 50, and both runs were GOOD. Their mean Brier score over the nine STUCK outcomes is 0.174. Among the declared scores, for comparison: 0.096 for the frozen exchangeable layer, which ignores the plans, and 0.259 for the uncalibrated mapping. Not declared, scored after the fact: 0.111 for the frozen composition-averaged column and 0.250 for P = 0.5. pred2's **secondary** prediction, A's deterministic level crossing on the exact plans, called all nine runs. The frozen critical burst b_c = 53.4 lies inside the edge interval of seeds 0 and 2 but not of seed 1, and the model's 50% points (48.4-49.5) lie only inside seed 1's.

## Sources

| key | path | what |
|---|---|---|
| BV | `B2P/analysis/agentload_analysis_basin/20261031-154526/` (`basin_runs.csv`, `basin_verdict.json`, `meta.json`) | registered classification, B2 bracket rule and seven-point curve, `analysis.basin classify` at `4dd21e0` |
| BJ | `B2P/results/agentload_analysis_burst2/20261031-1*/trap_v2_runs.csv` | the jobs' own in-job trap_v2 analyses (agree with BV run by run) |
| BL | `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/` (runs `20261024-155120`, `-160218`, `-184132`, `-184259`, `20261025-000043`, `-000053`) | committed n = 0 / n = 200 runs at 1.65 ×, seeds 0-2 (jobs 17093390, 17093391, 17093396, 17093397, 17093402, 17093403), found by `classify` itself |
| B1 | `results/nova/b1_e0f_1716850x_pulled_20261031-040517/results/agentload_e2_burst/` (n = 100: `20261030-220255`, `-220426`, `-232552`; n = 25: `20261030-235523`, `20261031-001011`, `-002140`) | BASIN-1 runs, re-classified in BV for the curve |
| TC | `B2P/analysis/derived/b2_time_course_descriptive.csv`, `b2_time_course_windows.csv` | descriptive 100 s time course (`experiments/r14_b2_derived.py`) |
| SC | `B2P/analysis/derived/b2_scoring.json`, `b2_scoring.csv` | scoring against pred2 (`experiments/r14_b2_score.py`); `declared_scores_b2_nine_runs` holds only the predictors pred2's declaration names, and the rest is under `not_declared` (CSV column `declared`) |
| SQ | `B2P/sacct_17169893-17169901.txt` | sacct records |
| P2 | `notes/PREDICTIONS_r13_pred2.md` §1 and "Scoring, declared now", `configs/r13_theory_pred2.yaml` (`b2:`), `results/theory/pred2/b2_basin.json`, all at tag `r13-theory-pred2` (`cfa7712`, branch push 09:20:20Z = 04:20:20 CDT) | frozen second prediction set |
| TH | `notes/PREDICTIONS_r13_theory.md`, `results/theory/merged/b1_basin_300k.json` at tag `r13-theory-pred` (`997d2c4`, pushed 02:05:30 CDT) | frozen first set: committor curve, b_c = 53.4 |
| R7 | `notes/ROBUSTNESS_r7.md` summary item 3 and §5 (Burst-size sweep), the 1.65 × table | round-7 simulator burst-size sweep (10 seeds, record workload) |
| EP | `configs/r11_basin_predict.yaml` (frozen at `r11-basin-reg`, unchanged) | frozen endpoints |
| IR | `C:\Users\Akshat\AppData\Local\Temp\claude\C--Users-Akshat-Desktop-Claude-Code\ebe78110-49cc-4b14-8d64-613717176b77\scratchpad\b2_recompute\` (`recompute.py`, `recompute2.py`, `compare.py`, `prov.py` and their outputs; session scratchpad, **not committed**) | independent recompute from the raw `requests.csv`, `sessions.csv` and `meta.json`, with no repo code. It **agrees**: hit_eval and STUCK identical in all 21 runs (9 B2, 6 B1, 6 baselines), backlog slope within 2e-17 /s; for the nine B2 runs GOOD identical, outstanding end within 5e-4 and uncached-token rel. dev. within 5e-6; every B2 config.yaml byte-identical to `621d88f`, prereg sha256 equal to the registration at `621d88f`, commit `621d88f`, dirty False. No failures; its provenance caveats are under Caveats |

**Setup:**
- **Cell:** SGLang FCFS, 300k-token pool, Qwen2.5-7B-Instruct, "NVIDIA A100 80GB PCIe, 81920 MiB" (nova22-gpu-1/2/3).
- **Arm:** BURST only, at 1.65 × λ_ref (λ = 0.118031 sessions/s). The burst of n ∈ {40, 50, 60} sessions arrives uniformly in [1200, 1260) s; runs last 8700 s; W = [5700, 8700) s. Labels `sglang-fcfs-r1-b40` / `-b50` / `-b60`.
- **Endpoints (EP, unchanged):** STUCK := hit_eval < 0.2. GOOD := trap_v2 RECOVERED, or (hit_eval > 0.8 and backlog slope ≤ 0.5(λ − λ_ref)); the slope threshold is 0.023249 sessions/s. The hit metric is `frac_turns_cached_gt50`: a turn is a hit if cached/prompt tokens > 0.5, and turns are attributed to W by completion time.
- **Rule:** bracketed iff n = 40 is GOOD in ≥ 2/3 seeds AND n = 60 is STUCK in ≥ 2/3 seeds.
- **Provenance:** all nine jobs ran from clone `repo_r14_basin2` at `621d88f` and finished COMPLETED 0:0.
  - Every run's `meta.json` records commit `621d88f`, dirty False, `start_state_verified` True, and not aborted. Every canary passed (exit 0).
  - Each run's `config.yaml` has the sha256 of the tagged `configs/agentload_e2_burst_n{40,50,60}.yaml`.
- **Pairing (common random numbers):** the base sessions of every run equal the same seed's n = 0 plan. The burst arrival times of n = 25, 40, 50, 60 and 100 are nested subsets of the n = 200 draw. The k-th burst session spec (turns, tool time) is the k-th of the n = 200 plan, given to the k-th earliest burst arrival.

## Numbers

**Per run** (BV; W = [5700, 8700) s; slope threshold 0.023249 sessions/s; baselines and BASIN-1 rows for the curve. "Outstanding end" is trap_v2's RECOVERED backlog, the time-mean number of requests in flight, plus sessions waiting at a client gate (none in these uncapped runs), over the last 300 s, [8400, 8700) s (`analysis/throughput.py` `outstanding_mean`; frozen `recovered_backlog_metric: outstanding`, RECOVERED needs < 20). It is not the number of sessions in system: by that measure the five GOOD B2 runs average 8.55-12.8 over the same 300 s (IR), also < 20, so their RECOVERED labels hold under either definition.)

| n | seed | job | run | state | trap_v2 | hit_eval | backlog slope /s | uncached-token rel. dev. | outstanding end |
|---|---|---|---|---|---|---|---|---|---|
| 0 (BL) | 0 / 1 / 2 | 17093391 / 17093397 / 17093403 | `20261024-160218` `-184259` `20261025-000053` | GOOD ×3 | recovered ×3 | 0.934 / 0.934 / 0.921 | -0.0005 / 0.0011 / 0.0001 | -0.892 / -0.899 / -0.874 | 3.2 / 1.9 / 2.2 |
| 25 (B1) | 0 / 1 / 2 | 17168503 / 04 / 05 | `20261030-235523` `20261031-001011` `-002140` | GOOD ×3 | recovered ×3 | 0.933 / 0.934 / 0.923 | -0.0005 / 0.0011 / 0.0001 | -0.892 / -0.899 / -0.878 | 3.2 / 1.9 / 2.2 |
| **40** | 0 | 17169893 | `20261031-101139` | **GOOD** | recovered | 0.934 | -0.0005 | -0.892 | 3.1 |
| **40** | 1 | 17169894 | `20261031-101245` | **GOOD** | recovered | 0.934 | 0.0011 | -0.899 | 1.9 |
| **40** | 2 | 17169895 | `20261031-101308` | **GOOD** | recovered | 0.925 | 0.0001 | -0.881 | 2.1 |
| **50** | 0 | 17169899 | `20261031-105804` | **GOOD** | recovered | 0.933 | -0.0005 | -0.892 | 3.2 |
| **50** | 1 | 17169900 | `20261031-110506` | **STUCK** | **trapped** | 0.000 | 0.0456 | -0.009 | 241.1 |
| **50** | 2 | 17169901 | `20261031-124223` | **GOOD** | recovered | 0.924 | 0.0001 | -0.879 | 2.2 |
| **60** | 0 | 17169896 | `20261031-101444` | **STUCK** | **trapped** | 0.000 | 0.0295 | +0.015 | 277.4 |
| **60** | 1 | 17169897 | `20261031-102650` | **STUCK** | **trapped** | 0.000 | 0.0435 | +0.034 | 234.6 |
| **60** | 2 | 17169898 | `20261031-103956` | **STUCK** | **trapped** | 0.000 | 0.0396 | +0.031 | 232.5 |
| 100 (B1) | 0 / 1 / 2 | 17168500 / 01 / 02 | `20261030-220255` `-220426` `-232552` | STUCK ×3 | trapped ×3 | 0.000 ×3 | 0.0318 / 0.0344 / 0.0361 | +0.026 / +0.013 / +0.037 | 306.2 / 269.3 / 272.9 |
| 200 (BL) | 0 / 1 / 2 | 17093390 / 17093396 / 17093402 | `20261024-155120` `-184132` `20261025-000043` | STUCK ×3 | trapped ×3 | 0.000 ×3 | 0.0320 / 0.0277 / 0.0362 | +0.025 / +0.029 / +0.026 | 363.2 / 313.0 / 351.5 |

Decision (BV `b2_bracket`): n = 40 GOOD 3/3, STUCK 0/3; n = 60 STUCK 3/3, GOOD 0/3; `good_majority_40` true, `stuck_majority_60` true, **`bracketed` true**. Notes and `incomplete` are empty. The B1 decision in the same file is unchanged (`basin_pass` true).

**Seven-point curve** (BV `curve` and `by_seed`; G = GOOD, S = STUCK)

| n | 0 | 25 | 40 | 50 | 60 | 100 | 200 |
|---|---|---|---|---|---|---|---|
| seed 0 | G | G | G | G | S | S | S |
| seed 1 | G | G | G | **S** | S | S | S |
| seed 2 | G | G | G | G | S | S | S |
| STUCK | 0/3 | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 | 3/3 |

Each per-seed CRN chain is monotone. The edges are (50, 60] for seed 0, (40, 50] for seed 1 and (50, 60] for seed 2, so the boundary is between 40 and 60 sessions in every seed. Every STUCK run at n ≥ 50 is also trap_v2 TRAPPED.

**Descriptive time course** (TC; not registered; 100 s windows by completion time, same definitions as the B1 time course):
- **STUCK runs:**
  - Hit < 0.2 in every window from the 1400 s window on (n = 50 seed 1; n = 60 seed 1), or from the 1500 s window on (n = 60 seeds 0 and 2). With 100 sessions it was 1300 s in all three seeds (`results/nova/b1_e0f_1716850x_pulled_20261031-040517/analysis/derived/b1_time_course_descriptive.csv`).
  - On the way down, the 1300 s window had hit 0.32 (n = 50 seed 1) and 0.38 / 0.21 / 0.56 (n = 60 seeds 0 / 1 / 2). The 1400 s window had 0.05 and 0.45 / 0.05 / 0.30 (`b2_time_course_windows.csv`).
- **GOOD runs, lowest 100 s window hit in [1200, 5700) s:**
  - n = 40: 0.779 (1400 s window), 0.784 (1300 s) and 0.828 (2100 s) in seeds 0 / 1 / 2.
  - n = 50: 0.699 (1400 s) in seed 0 and 0.814 (1200 s) in seed 2.
  - Every one is back above 0.8 in the next window.
  - Seed 2's n = 40 dip at 2100 s matches its n = 0 run (0.824 at 2100 s), so it comes from the base sessions, not the burst. The other n = 0 runs' lowest windows are 0.889 (4800 s) and 0.870 (5400 s).
- **GOOD runs, hit_eval minus the same seed's n = 0 run:**
  - n = 40: +0.00005 / 0.00000 / +0.0037.
  - n = 50: -0.0002 (seed 0) and +0.0029 (seed 2).
  - The 40-session burst of seed 1 leaves W exactly as without a burst: 4909 hits of 5254 turns, identical to its n = 0 run.
- **Peak requests in flight** (`max_inflight_seen`): GOOD runs 23-35 against 13-25 without a burst; STUCK runs 245-289.
- **The burst sessions are gone before W in every run** (`burst_ok_turns`, `last_burst_ok_turn_complete_s`, `burst_ok_turns_in_W`):
  - Every planned burst turn completed ok.
  - The last burst turn completed at 1510-1680 s in the GOOD runs and at 2454-4719 s in the STUCK runs. None completed inside W.
  - So the four STUCK runs stay at hit 0.000 over [5700, 8700) s on base sessions alone, the same arrivals that the n = 0 runs serve at hit 0.92-0.93.

## Against the predictions

**pred2 (P2, `r13-theory-pred2`, blind in time). Per run** (SC; P(STUCK) as frozen; P(GOOD) in brackets for the primary; b_cal is pred2's calibrated cohort size, with the raw value in parentheses; the composition-averaged column is frozen but not among the declared predictors):

| n | seed | engine | primary P(STUCK) [P(GOOD)] | b_cal (raw) | frozen exchangeable layer | composition-averaged (not declared) | uncalibrated (raw time max) | A's crossing (secondary) | Brier, primary |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 0 | GOOD | **0.778 [0.219]** | 53.0 (56.0) | 0.139 | 0.212 | 1.000 | GOOD | 0.605 |
| 40 | 1 | GOOD | 0.360 [0.632] | 46.9 (49.5) | 0.139 | 0.212 | 0.515 | GOOD | 0.130 |
| 40 | 2 | GOOD | 0.088 [0.900] | 36.1 (38.2) | 0.139 | 0.212 | 0.111 | GOOD | 0.008 |
| 50 | 0 | GOOD | **0.862 [0.136]** | 54.1 (55.7) | 0.547 | 0.561 | 0.987 | GOOD | 0.744 |
| 50 | 1 | STUCK | 1.000 [0.000] | 58.2 (60.0) | 0.547 | 0.561 | 1.000 | STUCK | 0.000 |
| 50 | 2 | GOOD | 0.217 [0.773] | 43.3 (44.6) | 0.547 | 0.561 | 0.261 | GOOD | 0.047 |
| 60 | 0 | STUCK | 1.000 [0.000] | 62.6 (63.8) | 1.000 | 0.886 | 1.000 | STUCK | 0.000 |
| 60 | 1 | STUCK | 1.000 [0.000] | 71.6 (73.0) | 1.000 | 0.886 | 1.000 | STUCK | 0.000 |
| 60 | 2 | STUCK | 0.810 [0.188] | 53.4 (54.4) | 1.000 | 0.886 | 0.892 | STUCK | 0.036 |

**Primary per-seed calls that missed** (stated plainly):
- Seed 0 at n = 40: predicted P(STUCK) = 0.78 (P(GOOD) 0.22). The run was GOOD: it was RECOVERED with hit 0.934, and its hit_eval is within 0.0001 of the no-burst run.
- Seed 0 at n = 50: predicted P(STUCK) = 0.86 (P(GOOD) 0.14). The run was GOOD: RECOVERED, hit 0.933.

Every other primary call has the observed state on its more likely side (7 of 9). The uncalibrated band misses the same two runs harder (P(STUCK) 1.000 and 0.987) and also seed 1 at n = 40 (0.515, GOOD).

**Declared scores over the nine B2 runs** (SC `declared_scores_b2_nine_runs`: exactly the predictors pred2's declaration names, "the primary, each band, the frozen exchangeable layer and A's deterministic labels"; Brier = mean of (p − y)²; log-likelihood = sum of ln p(observed), floored at 10⁻³; observed STUCK 4 of 9, GOOD 5 of 9)

| predictor | Brier STUCK | Brier GOOD | log-lik STUCK | log-lik GOOD | expected STUCK |
|---|---|---|---|---|---|
| **primary** (calibrated cohort peak, per seed) | **0.174** | **0.177** | -4.48 | -4.54 | 6.12 |
| band: lockstep | 0.083 | 0.085 | -2.45 | -2.50 | 5.45 |
| band: 2.5 s service | 0.158 | 0.161 | -3.85 | -3.91 | 6.34 |
| band: realized background at peak | 0.062 | 0.063 | -2.04 | -2.09 | 4.63 |
| band: raw time maximum (**uncalibrated**, the pre-review primary) | 0.259 | 0.261 | -12.51 | -12.56 | 6.77 |
| band: raw lockstep | 0.244 | 0.246 | -6.17 | -6.23 | 6.98 |
| band: raw 2.5 s service | 0.252 | 0.254 | -7.57 | -7.63 | 6.97 |
| band: raw realized background at peak | 0.089 | 0.091 | -2.57 | -2.62 | 5.16 |
| band: realized post-burst rate | 0.239 | 0.242 | -8.42 | -8.53 | 6.78 |
| **frozen exchangeable layer** (cohort at its mean; 0.139 / 0.547 / 1.000) | **0.096** | 0.098 | -2.64 | -2.69 | 5.06 |
| A's deterministic level crossing (secondary; labels as 0/1) | 0.000 | 0.000 | 0.00 | 0.00 | 4 |

**Not declared: frozen numbers scored after the fact** (SC `not_declared.scores_b2_nine_runs_not_declared`; same definitions). The composition-averaged column is a separate frozen column of pred2's table (P2 §1, the dose-response table), not one of its bands (P2 §1, "Bands"), and the declaration does not list it among the predictors to score. These rows were added after the outcome was known.

| predictor | Brier STUCK | Brier GOOD | log-lik STUCK | log-lik GOOD | expected STUCK |
|---|---|---|---|---|---|
| composition-averaged (0.212 / 0.561 / 0.886) | 0.111 | 0.113 | -3.30 | -3.35 | 4.98 |
| composition-averaged, realized-background band | 0.135 | 0.137 | -3.97 | -4.01 | 4.96 |
| composition-averaged, raw time maximum | 0.130 | 0.133 | -3.68 | -3.73 | 5.41 |
| composition-averaged, raw realized background | 0.149 | 0.152 | -4.23 | -4.28 | 5.29 |
| reference P = 0.5 (not frozen, scale only) | 0.250 | 0.250 | -6.24 | -6.24 | 4.5 |

- **Calibrated vs uncalibrated** (the declaration asks the data to choose): the calibrated mapping scores better, with Brier 0.174 against 0.259 and log-likelihood -4.48 against -12.51.
- **Both lose to the frozen exchangeable layer**, which does not look at the plans (0.096). On this data, conditioning on each seed's burst composition through the cohort peak made the probabilities worse, not better. After the fact (not declared), the frozen composition-averaged column, which averages over plans, also does better than the primary (0.111).
- **The bands that use the plan's realized background at the cohort peak score best** (0.062 calibrated, 0.089 raw). pred2 notes that seed 0's background was 21,000 tokens below its mean at seed 0's peak.

**Rule** (SC `rule`): bracketed, observed.
- Primary P(rule) = 0.656 (stated as 0.66): Brier 0.119, log score -0.42.
- Uncalibrated band 0.421: Brier 0.335.
- The other bands range from 0.230 to 0.881.
- Frozen exchangeable layer 0.939 (0.947 if every non-trapped run counts as GOOD): Brier 0.0037.
- Composition-averaged, three random seeds (not declared): 0.840.
- A's deterministic crossing (secondary): holds (b40 GOOD 3/3, b60 STUCK 3/3), as predicted.

**Secondary, A's deterministic level crossing on the exact plans** (SC `secondary_level_crossing`; pred2 §1 lists it as "*Secondary (deterministic)*", below the primary per-seed probabilities): b40 G/G/G, b50 G/S/G, b60 S/S/S. That is **9 of 9 correct**, and 15 of 15 with the BASIN-1 sizes (those six not blind, see Blindness).

**The three theory-specific claims in pred2's scoring declaration** (SC `theory_specific_claims`):
1. *"Seed 0 is the most trap-prone at b = 40 and seed 2 the least": not borne out.*
   - No seed was stuck at 40, so b = 40 does not order the seeds.
   - Over 40-60 the STUCK counts are 1 / 2 / 1 for seeds 0 / 1 / 2. Seed 1 is the most trap-prone: it is the only seed STUCK at 50, and its edge, (40, 50], is the lowest. Seeds 0 and 2 tie at (50, 60].
   - pred2 ranked seed 0 first. Its P(STUCK) for seed 0 was 0.78 / 0.86 / 1.00, against 0.36 / 1.00 / 1.00 for seed 1.
2. *"Seed 2's b40 is GOOD (0.90) and seed 2's b60 STUCK (0.81)": both held.*
3. *P(rule) = 0.66 (uncalibrated 0.42): the rule held.*

**Per-seed edges against the frozen critical sizes** (SC `per_seed_edges_vs_frozen_critical_sizes`; nominal burst sizes):

| frozen size | value | seed 0 (50, 60] | seed 1 (40, 50] | seed 2 (50, 60] |
|---|---|---|---|---|
| deterministic critical burst b_c (TH, P2) | 53.4 | inside | outside | inside |
| committor q = 0.5 (P2) | 49.5 | outside | inside | outside |
| P(STUCK) = 0.5, exchangeable (P2) | 49.3 | outside | inside | outside |
| composition-averaged P(STUCK) = 0.5 (P2) | 48.4 | outside | inside | outside |

- Seed 1's interval and seeds 0 and 2's intervals are disjoint, so no single size fits every seed. b_c = 53.4 fits two of three; the three 50% points fit one. pred2 declared that b_c and the committor's 49.5 "are tested by the dose-response curve as a whole"; the curve gives each a partial fit, not a confirmation.
- Pooled STUCK fractions are 0/3, 1/3 and 3/3 at 40 / 50 / 60. The frozen exchangeable layer said 0.139 / 0.547 / 1.000 per run, and the composition-averaged column said 0.212 / 0.561 / 0.886.

**Not declared, descriptive** (SC `not_declared`; besides the composition-averaged and P = 0.5 rows above):
- *pred2's per-seed cohort scale:* no single threshold separates the outcomes.
  - On the calibrated scale, the largest GOOD run is seed 0 at n = 50 (b_cal 54.08), and the smallest STUCK run is seed 2 at n = 60 (b_cal 53.42).
  - b_c = 53.418 classifies 8 of 9 runs; the miss is seed 0 at n = 50. Seed 2 at n = 60 is called right by a margin of 0.005 (b_cal 53.423).
  - On the raw scale, 7 of 9: seed 0 at n = 40 (56.02) and seed 0 at n = 50 (55.71) are GOOD above seed 2's stuck 54.45.
- *A's crossing statistic does separate them:* the plan's peak live KV, base plus burst. Its GOOD maximum is 336,550 tokens (seed 0, n = 50), and its STUCK minimum is 351,800 (seed 2, n = 60). D_live(n_u) = 341,355 lies between the two. This statistic counts the plan's actual background, and the cohort-only statistic does not.
- *BASIN-1 sizes* (n = 25, 100; SC `b1_sizes_not_blind`): primary Brier 0.0011, exchangeable 0.0009, all six calls right. pred2's rows for them are **not blind**: pred2 was pushed at 04:20:20, after the BASIN-1 outcomes were first read at about 04:07 (see Blindness).

**First theory set (TH, `r13-theory-pred`, blind in time for B2):** P(STUCK) per seed 0.139 / 0.547 / 1.000 at 40 / 50 / 60 and b_c = 53.4. This is pred2's exchangeable layer, which reproduces the frozen B1 rows exactly (P2 §1), so its scores are the "frozen exchangeable layer" row above. The rule probability under it is 0.94.

**Earlier simulator (R7, not a B2 prediction):** the round-7 burst sweep (record workload, 10 seeds, 1.65 × the simulator's λ_miss) had 25 never trapping (0/10). At 50 it had TRAPPED 6/10 and hit < 0.2 in 7/10; from 100 every run was stuck. The engine's 50 is 1/3 TRAPPED and 1/3 STUCK (the same run), so like for like: 1/3 against 6/10 trapped, 1/3 against 7/10 stuck. The r11 S1 bundle (`notes/PREDICTIONS_r11_basin.md`) predicted only 25 and 100, so it has no B2 prediction.

## Blindness

Push times come from `gh api repos/AkshatValse/Nova-Research/activity`, read 2026-10-31. They are the **branch pushes of the tagged commits**:
- `r14-basin2-reg` (`621d88f`): push `9b67c26..621d88f` to `r11/strengthen` at 07:10:48Z.
- The analysis-only fix `19c58e9`: 08:12:59Z.
- B1 verdict `4dd21e0`: 09:20:02Z.
- pred2 (`cfa7712`, branch creation `r13/pred2`): 09:20:20Z.
- **The tags' own push times cannot be observed:** the activity API returns no tag events. `git ls-remote origin` (read ~16:20 CDT) shows both remote tags pointing at the same tag objects as the local ones: `r14-basin2-reg` = `692450e` → `621d88f`, `r13-theory-pred2` = `6f0b504` → `cfa7712`. Their tagger dates are 02:10:35 and 04:20:17 CDT. The timing claims below therefore rest on the branch pushes of the tagged commits.

`r13-theory-pred` (`997d2c4`) was pushed at 07:05:30Z (PAPER_INPUT_basin.md). Submit, start and end times come from sacct (SQ); run start and end come from each run's `meta.json`. All times below are CDT.

| job | cell | submitted | sacct Start-End | run start-end (meta) |
|---|---|---|---|---|
| 17169893 | b40 s0 | 04:21:40 | 10:10:27-12:39:49 | 10:11:39-12:36:40 |
| 17169894 | b40 s1 | 04:21:40 | 10:11:27-12:40:55 | 10:12:45-12:37:46 |
| 17169895 | b40 s2 | 04:21:41 | 10:11:58-12:41:18 | 10:13:08-12:38:10 |
| 17169896 | b60 s0 | 04:21:41 | 10:13:28-12:42:59 | 10:14:44-12:39:45 |
| 17169897 | b60 s1 | 04:21:41 | 10:25:33-12:55:00 | 10:26:50-12:51:51 |
| 17169898 | b60 s2 | 04:21:41 | 10:38:39-13:08:06 | 10:39:56-13:04:58 |
| 17169899 | b50 s0 | 04:21:41 | 10:56:47-13:26:14 | 10:58:04-13:23:06 |
| 17169900 | b50 s1 | 04:21:41 | 11:03:50-13:33:15 | 11:05:06-13:30:07 |
| 17169901 | b50 s2 | 04:21:41 | 12:41:05-15:10:34 | 12:42:23-15:07:25 |

- **Registration:** pushed at 02:10:48, 2 h 11 min before submission. This test is pre-registered in the paper's sense: the registration push precedes the submission.
  - The analysis-only fix `19c58e9` (one vote per seed; only bound runs count) was committed at 03:12:56 and pushed at 03:12:59, also before submission and before any B2 run existed. It is stricter only.
  - Re-running `analysis/basin.py` exactly as tagged (`621d88f`) gives the same bracket, curve and per-run numbers (COMMANDS.txt).
- **pred2:** pushed at 04:20:20, 80 s before the first submission and 5 h 51 min before the first run started. **Blind in time** for all nine runs.
- **First theory set:** pushed at 02:05:30. **Blind in time**.
- **pred2's rows for n = 25 and 100** (BASIN-1 runs, which ended 00:27-02:46) are **not blind**: pred2 was pushed at 04:20:20, after the BASIN-1 outcomes were first read at about 04:07 (the paper's timeline, appendix.tex: "first recorded reading of the BASIN-1 and fresh-seed outcomes (about 04:07)"; `notes/PAPER_INPUT_basin.md`). The paper's "by access only" requires the runs to be first read after the push, so it does not apply. This matches the paper's treatment of pred2's fresh-seed (E0F) table, which it calls not blind.
  - By pred2's own record, its `b2_basin.json` was `created` at 04:01:24, before that reading, and its drivers read no B1 result (P2 §1). No access record can confirm this.
  - These rows enter only the supplementary score (SC `not_declared.b1_sizes_not_blind`).
- **First read:** the outcomes were first read on the PC after the pull at about 15:42 CDT. Blindness here does not depend on this, because every prediction was pushed before submission.

## Caveats

- **Sample size:** three seeds per size and one run per (n, seed). The registered rule is per seed, with no pooled intervals. The 95% Clopper-Pearson intervals are [0, 0.71] for 0/3, [0.008, 0.91] for 1/3 and [0.29, 1] for 3/3.
  - n = 50 does not enter the rule. It is a registered curve point (`b2_counted`), reported against the committor.
  - Brier and log-likelihood over nine binary outcomes rank the predictors on this data only.
- **Edge resolution:** each seed's edge is known only to a 10-session interval.
  - **Composition pairing shifts with n:** the burst of n uses the first n arrival times and the first n session specs of the n = 200 draw, but spec k goes to the k-th earliest arrival. When n grows, therefore, specs move to other arrival times; the chain is nested as sets, not by session identity.
- **Analysis code version:** `classify` ran at `4dd21e0`, which contains the post-tag fix `19c58e9`. The tagged code gives identical results; only `prereg_bound` reads False there, because a git-less export cannot read commit times.
- **What the scores compare:** the pred2 per-seed numbers depend on how a realized plan is mapped to the committor's starting point; pred2 says so itself and gives wide bands (P(rule) 0.23-0.88). The score table shows which mappings the data favour. It does not change any frozen number.
- **Not declared in advance:** the four composition-averaged rows (frozen numbers, but pred2's declaration does not name that column among the predictors to score), the P = 0.5 reference, the BASIN-1-size supplement and the threshold separability checks are additions, scored after the fact and kept under `not_declared` in SC (CSV `declared` False).
- **Provenance, from the independent recompute (IR) and the operator's re-checks.** IR found no failures (Sources, IR). Its caveats:
  - *Tag push times are not observable.* The activity API has no tag events; the timing rests on the branch pushes of the tagged commits (Blindness). The remote tags match the local tag objects; tagger dates 02:10:35 (`r14-basin2-reg`) and 04:20:17 (`r13-theory-pred2`) CDT.
  - *Archive hash.* IR did not re-check it: the remote copy is deleted and no archive sits in the pull dir. The operator's local copy is only in the session scratchpad (`C:\Users\Akshat\AppData\Local\Temp\claude\C--Users-Akshat-Desktop-Claude-Code\ebe78110-49cc-4b14-8d64-613717176b77\scratchpad\b2pull\b2_pull_lead.tar.xz`, not committed and not backed up). It was re-checked at ~16:20 CDT: sha256 `58e77d7e…` and 22,205,520 bytes match, and its 388 files extract byte-identical (cmp) to B2P. The Nova-side hash and the clone's clean `git status` are the pull-time record only. IR checked integrity indirectly: each run's `config.yaml` equals the bytes at `621d88f`, each prereg sha256 in `meta.json` equals the registration at `621d88f`, each E2_CONFIG sha256 in the job banners equals `git show 621d88f`, and `requests_ok` / `requests_total` in `meta.json` equal the ok-row / row counts of `requests.csv` (the operator re-checked the last two items for all nine B2 runs).
  - *`git dirty` = true in BV's `meta.json`* (at `4dd21e0`): `git status --porcelain` counts untracked files, and the pull dir was untracked. `git diff HEAD` is empty for `analysis/`, `src/` and `configs/`, and a re-run gives identical output.
  - *"Outstanding" is requests in flight,* not sessions in system (per-run table note). IR inferred this from the numbers (its in-flight mean matches `outstanding_end` to ≤ 5e-4); the operator confirmed it in `analysis/trap_v2.py` and `analysis/throughput.py`. The RECOVERED labels hold under either definition.
- **b40 seed 1 matches its no-burst run in W:** its hit_eval equals the n = 0 seed-1 run's to every digit, and both runs' `requests.csv` have 4909 hits among 5254 ok turns completed in W, with the same prompt and cached token totals. The base sessions and token content are the same, and the 40 burst sessions finished by 1680 s (TC). This is a property of the CRN design, not a duplicated run:
  - the run dirs, job IDs and nodes differ (17169894 on nova22-gpu-3; 17093397 on nova22-gpu-2);
  - 22 of the 46 100 s windows from 1100 to 5600 s and 16 inside W have different hit fractions (`b2_time_course_windows.csv`).

## Suggested text

Wording rules used below: pred2's per-seed probabilities are its **primary** B2 prediction and A's deterministic level crossing its **secondary** one (P2 §1), so every scored sentence names which is which; the composition-averaged column is not quoted as a declared score; the time course is labelled descriptive; and the critical burst's partial fit is stated wherever BASIN-2 is said to test it.

**(a) `paper/sections/results.tex`, §sec:basin.** Replace "BASIN-2 tests the first-principles model's critical fresh burst of 53.4 sessions, from a heuristic of \S\ref{sec:fp-heur} that counts a burst session at its peak footprint; its outcome is pending in this version. BASIN-1's registration reached GitHub 68 minutes before its jobs were submitted; \S\ref{sec:frozen} scores the frozen predictions." with:

> BASIN-2 tests the first-principles model's critical fresh burst of 53.4 sessions, from a heuristic of \S\ref{sec:fp-heur} that counts a burst session at its peak footprint. Its registered rule held: a burst of 40 sessions left the engine good (RECOVERED, hit fraction 0.925--0.934, within 0.004 of the no-burst run with the same arrivals) and one of 60 left it stuck and trapped, in 3 of 3 seeds each, while 50 sessions, which the rule does not use, trapped seed 1 and left seeds 0 and 2 good. Over the seven sizes 0, 25, 40, 50, 60, 100 and 200 each seed switches from good to stuck exactly once, between 50 and 60 sessions in seeds 0 and 2 and between 40 and 50 in seed 1, so the boundary lies between 40 and 60 sessions in every seed but is not the same for all three. The critical burst of 53.4 therefore lies inside the edge interval of seeds 0 and 2 but not of seed 1, and the sizes at which the model's stuck probability or committor reaches one half (48.4--49.5 sessions) lie inside seed 1's only. Descriptively (not registered), the stuck runs' hit fraction stayed below 0.2 from the 1400 or 1500\,s window on, 100--200\,s later than with 100 sessions. BASIN-1's and BASIN-2's registrations reached GitHub 68 and 131 minutes before their jobs were submitted; \S\ref{sec:frozen} scores the frozen predictions.

**(b1) `paper/sections/frozen_app.tex`, Table tab:frozen2, BASIN-2 row.**
- *Prediction cell:* change "pred2, conditioning on each seed's burst:" to "pred2, conditioning on each seed's burst (primary):", and after "(bands 0.23--0.88; 0.94 for average bursts)" add "; secondary, a deterministic level crossing on each seed's exact plan: good, good, good at 40, good, stuck, good at 50 and stuck in all three seeds at 60".
- *Outcome cell* (replace `\pending{BASIN-2 verdict}`):

> Bracketed: 40 good and 60 stuck and trapped, each in 3 of 3; 50 stuck in seed 1 only. Per-seed edges $(50,60]$, $(40,50]$, $(50,60]$, so 53.4 lies in two of the three. pred2: rule held; primary per-seed probabilities on the more likely side in 7 of 9, wrong for seed 0 at 40 and 50 (stuck with probability 0.78 and 0.86; both good); their Brier score 0.17 (frozen average-burst layer 0.10, uncalibrated 0.26); secondary deterministic crossing right in 9 of 9. Blind in time

**(b2) `paper/sections/frozen.tex`, Table tab:frozensum.** Add a row before "Rescue R1":

> `BASIN-2, 1.65 $\lref$ (registered) & Theory: stuck with probability 0.14, 0.55 and 1.0 per seed at 40, 50 and 60 (critical burst 53.4). pred2, per seed from each burst's composition (primary): the rule holds with probability 0.66; secondary, a deterministic crossing on each seed's exact plan. Both blind in time & Bracketed: 40 good and 60 stuck, 3 of 3 seeds each; 50 stuck in 1 of 3; 53.4 inside two of the three per-seed edge intervals. pred2's primary per-seed probabilities right in 7 of 9, wrong for seed 0 at 40 and 50; its secondary deterministic crossing right in 9 of 9\\`

and change the Pending row to:

> `Pending & H200 with a 600k pool; pools of 150k and 600k; Llama-3.1-8B; SHED; TOOLSLOW & ---\\`

Also in `frozen.tex`:
- In the "Basin" paragraph, after "...the registered bracketing rule holds with probability 0.66.", add: "It held. pred2's primary per-seed probabilities put the observed state on the more likely side in 7 of the 9 runs; they gave seed 0 a stuck run with probability 0.78 at 40 and 0.86 at 50 sessions, and both runs stayed good, so seed 1, not seed 0 as pred2 declared, was the most trap-prone. Over the nine runs their Brier score is 0.17, against 0.10 for the same model's frozen average-burst probabilities and 0.25 for a coin. pred2's secondary prediction, a deterministic level crossing on each seed's exact arrivals, called all nine. The critical burst of 53.4 lies inside the edge interval of seeds 0 and 2, $(50,60]$, but not of seed 1, $(40,50]$, and the sizes at which the model's stuck probability or committor reaches one half (48.4--49.5) inside seed 1's only."
- In the "Pending" paragraph, delete "the second basin test, BASIN-2 (bursts of 40, 50 and 60 around the model's critical burst of 53.4),".

**(c) `paper/sections/appendix.tex`.**
- Table tab:ledger, BASIN-2 row, last cell (replace `9 runs, submitted 04:21; \pending{BASIN-2}`):

> `9 runs, submitted 04:21; bracketed: 40 good, 60 stuck, 3 of 3 each (\S\ref{sec:basin})`

- Data table (after the row "BASIN-1, E0F & \fpath{results/nova/b1_e0f_1716850x_pulled_20261031-040517/} (\texttt{4dd21e0})\\"), add:

> `BASIN-2 & \fpath{results/nova/b2_1716989x_pulled_20261031-154500/}; scoring \fpath{experiments/r14_b2_score.py}, \fpath{experiments/r14_b2_derived.py} (\texttt{<commit>})\\`

- Stages caption (tab:stages): replace "those of the BASIN-1 and fresh-seed jobs and of the rescue jobs in theirs (\fpath{sacct_17168500-17168507.txt}, \fpath{sacct_1716896x.txt})" with "those of the BASIN-1 and fresh-seed jobs, the rescue jobs and the BASIN-2 jobs in theirs (\fpath{sacct_17168500-17168507.txt}, \fpath{sacct_1716896x.txt}, \fpath{sacct_17169893-17169901.txt})".

**(d) One sentence each.**
- `intro.tex`, item "A measured basin": replace "; BASIN-2, with bursts of 40, 50 and 60 sessions around the model's critical burst of 53.4, is pending in this version." with "; BASIN-2, registered before its jobs were submitted, narrowed it to between 40 and 60 sessions in every seed (40 good and 60 stuck in 3 of 3 seeds, 50 stuck in seed 1 only), so the model's critical burst of 53.4 sessions matches the edge of seeds 0 and 2 but not of seed 1, which tipped between 40 and 50."
- `intro.tex`, item "A first-principles thrashing curve": "its critical-burst prediction (BASIN-2) is pending" becomes "in its critical-burst test (BASIN-2) the registered rule held (probability 0.66 beforehand), as did its secondary deterministic per-seed calls, while its primary per-seed probabilities favoured the wrong state for one seed at 40 and 50 sessions and its critical burst of 53.4 matches the edge of two of the three seeds".
- `intro.tex`, paragraph "What is ours": replace "ours is a measured boundary on an LLM engine, predicted beforehand by the simulator." with "ours is a measured boundary on an LLM engine, whose 25/100-session bracket the simulator predicted beforehand and to whose 40/60-session bracket the first-principles model gave probability 0.66 before the jobs were submitted." (No simulator prediction was frozen for BASIN-2: the r11 S1 bundle covers 25 and 100 only, and round 7 is not a B2 prediction.)
- `robustness.tex`, "Burst size and horizon": replace "; BASIN-2, with 40, 50 and 60 sessions, is pending (\S\ref{sec:basin})." with "; BASIN-2 found 40 sessions good and 60 stuck in 3 of 3 seeds and 50 trapped in 1 of 3 (the simulator at 1.65 $\lmiss$: 6 of 10), which puts the boundary between 40 and 60 sessions (\S\ref{sec:basin})."
- `limitations.tex`:
  - "Scope of the registered evidence": in "The 600k-pool H200, Llama-3.1-8B, pool-sweep, BASIN-2, shedding and tool-slowdown tests have pending outcomes in this version.", delete "BASIN-2, ".
  - "Models and simulators": after "it misses the H200's tail past the peak and vLLM's earlier cliff," add "its per-seed BASIN-2 probabilities favoured the wrong state for seed 0 at 40 and 50 sessions (the deterministic crossing on the same plans called all nine runs),".
- `frozen_app.tex`, "Out-of-sample predictions": after the BASIN-1 clause "...and its predictions are blind by access only);" add "BASIN-2's registered rule held (pred2's probability 0.66), as did pred2's secondary deterministic crossing in all nine runs, while its primary per-seed probabilities were on the wrong side for seed 0 at 40 and 50 sessions and the critical burst of 53.4 matches the edge of two of the three seeds;".
- `conclusion.tex`: replace "Bursts of 25 sessions were absorbed and bursts of 100 trapped the engine, so the good state has a finite basin." with "Bursts of 25 and 40 sessions were absorbed and bursts of 60 and more trapped the engine in every seed, so the good state has a finite basin, whose boundary lies between 40 and 60 sessions at 1.65 $\lref$ and depends on the seed." In the same paragraph, replace "the rescue, the 25/100-session basin test and, in nominal multiples, an H200's from-empty edge, though not that GPU's softer tail past the peak or 4 of the 9 rescue release times." with "the rescue, both basin tests' rules (BASIN-2's with probability 0.66) and, in nominal multiples, an H200's from-empty edge, though not that GPU's softer tail past the peak, 4 of the 9 rescue release times or, at 40 and 50 sessions, one seed's basin probabilities." Both parts go together: the rule sentence without the miss would list BASIN-2 as a clean success.
- Abstract (short clauses), **all three changes together**: replace "A registered test put the basin boundary between bursts of 25 and 100 sessions." with "Two registered tests put the basin boundary between bursts of 40 and 60 sessions."; "its frozen predictions held for the rescue, the basin test and the H200's nominal from-empty edge (the last two on runs begun before freezing)" becomes "its frozen predictions held for the rescue, both basin tests' rules and the H200's nominal from-empty edge (the first basin test and the edge on runs begun before freezing)"; and "not for the H200 curve's tail or 4 of 9 release times" becomes "not for the H200 curve's tail, 4 of 9 release times or one seed's basin probabilities". The last change is **not optional**: the existing abstract lists the rescue's missed release times in its "not for" list, and without the same clause for BASIN-2 it would claim a clean BASIN-2 success although the declared primary favoured the wrong state for seed 0 at 40 and 50. Net change: +64 characters (the `main.tex` abstract line goes from 1905 to 1969 characters of source), so trim elsewhere if the arXiv form's 1920-character limit is taken from this text.
