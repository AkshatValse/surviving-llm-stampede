# Paper input: A100 KV-pool sweep (150,000 and 600,000 tokens), scored against the frozen round-13 theory

Branch `r13/pool-sweep` (from `origin/main` `a4896dd`). Written 2026-10-31 after the pull. Every number below has its source. Abbreviations: P = `results/nova/pool_sweep_1716886x_pulled_20261031-112342/`; D = `P/derived/` (written by `experiments/r13_pool_score.py`, read-only on P and on the frozen git objects).

## What was run

- **Cells:** SGLang 0.5.22, Qwen2.5-7B-Instruct, FCFS with the waiting-prefix refresh (the registered `sglang-fcfs-r1` cell), one A100 80GB PCIe (hardware string `NVIDIA A100 80GB PCIe, 81920 MiB` in all 30 `meta.json`), `--max-total-tokens` 150,000 and 600,000. Labels `sglang-fcfs-r1-p150k` and `sglang-fcfs-r1-p600k`. Every server log prints `max_total_num_tokens=150000` or `=600000`, equal to the requested pool, in all 18 jobs (`P/results/nova_job_logs/<job>-*/server.log`).
- **Clone:** `$W/repo_r13_pool` at `5a6fbcd`, clean; all 30 run `meta.json` record `5a6fbcd`, not dirty.
- **λ_ref** = 0.07153402 sessions/s, the 300k E0a value (`prereg/inputs/2026-10-23/calibration.json`). It does not depend on the pool, so both pools use it.
- **Stage C** (closed system, synchronized start, 900 s warmup and 1800 s measured, one run per n):
  - 600k: jobs 17168864 (n = 24, 32, 40), 17168865 (48, 56, 64), 17168866 (80, 96, 300);
  - 150k: jobs 17168867 (6, 8, 10), 17168868 (12, 14, 16), 17168869 (20, 24, 300).
- **E0b** (open system from an empty cache and queue, 3000 s, seed 0):
  - 600k: jobs 17168870–75 at 2.5, 3.0, 3.5, 4.0, 4.5, 5.0 × λ_ref;
  - 150k: jobs 17168876–81 at 1.1, 1.2, 1.3, 1.45, 1.6, 1.8 ×.
- **Job records:** all 18 COMPLETED 0:0 on nova22-gpu-[1-3] (`P/sacct_17168864-17168881.txt`). Submitted 22:58:03 CDT 10-30 (`P/submit_pool_sweep_20261030-225803.log`).
- **Combined analyses,** run on the Nova login node (`envs/swapp`, nice) and copied into P:
  - `summarize closed --warmup-s 900 --primary-label <label>` → `results/agentload_analysis_closed/20261031-112200` (600k) and `/20261031-112201` (150k);
  - `summarize stable` → `results/agentload_analysis_stable/20261031-112202` (600k) and `/20261031-112204` (150k).
  - Zero guard errors or warnings. The only note is the summarizer's default-grid remark ("n grid incomplete, missing [16, 20]" / "[32, 48, 96]"); it has no effect on n_cap or μ_max.
- **Archive:** sha256 `fcf51ad637ddc6cb34d7c8af77d7117638a5b15d39bf1100307707828bc90035`, the same on both ends. The remote archive was deleted after the copy.

## Measured (turns-based estimator is the theory's primary; sessions also given)

**μ(n)** (`P/results/agentload_analysis_closed/20261031-112201/mu_curve.csv` (150k) and `/20261031-112200/` (600k)):

| pool | n | μ turns | μ sessions | hit (all turns) | mean queue |
|---|---|---|---|---|---|
| 150k | 6 | 0.0702 | 0.0700 | 0.932 | 0.0 |
| 150k | 8 | 0.0915 | 0.0850 | 0.934 | 0.0 |
| 150k | 10 | 0.1117 | 0.1089 | 0.915 | 0.003 |
| 150k | **12** | **0.1201** | **0.1183** | 0.842 | 0.06 |
| 150k | 14 | 0.1127 | 0.1117 | 0.713 | 0.53 |
| 150k | 16 | 0.0987 | 0.0944 | 0.555 | 1.6 |
| 150k | 20 | 0.0664 | 0.0622 | 0.133 | 6.3 |
| 150k | 24 | 0.0627 | 0.0561 | 0.049 | 11.7 |
| 150k | 300 | 0.1081 | 0.1067 | 0.000 | 280 |
| 600k | 24 | 0.2528 | 0.2656 | 0.929 | 0.0 |
| 600k | 32 | 0.3204 | 0.3433 | 0.928 | 0.0 |
| 600k | 40 | 0.3746 | 0.3889 | 0.930 | 0.0 |
| 600k | **48** | **0.4084** | **0.4278** | 0.921 | 0.01 |
| 600k | 56 | 0.2390 | 0.2511 | 0.775 | 4.2 |
| 600k | 64 | 0.0815 | 0.0833 | 0.243 | 16.5 |
| 600k | 80 | 0.0721 | 0.0678 | 0.135 | 39.3 |
| 600k | 96 | 0.0692 | 0.0617 | 0.006 | 50.9 |
| 600k | 300 | 0.1103 | 0.1022 | 0.000 | 249 |

**Summary quantities** (D `pool_sweep_scored.json`):

| quantity | 150k | 600k |
|---|---|---|
| peak n (both estimators) | 12 | 48 |
| μ_max turns / sessions (sessions/s) | 0.1201 / 0.1183 | 0.4084 / 0.4278 |
| **peak ratio μ_max/λ_ref**, turns / sessions | **1.68 / 1.65** | **5.71 / 5.98** |
| flat top (grid points within 2% of the maximum, turns) | {12} | {48} |
| 0.5-hit crossing (linear in hit, turns) | 16.52 (grid [16, 20]) | 60.14 (grid [56, 64]) |
| μ at large n, turns (all-miss branch) | 0.0664 (20), 0.0627 (24) | 0.0721 (80), 0.0692 (96) |
| μ(300), synchronized start, trapped from t = 0 | 0.108 | 0.110 |
| E0b largest stable / first unstable (nominal ×) | **1.2 / 1.3** | **4.5 / 5.0** |
| the same at the realized arrival rate | 1.356 / 1.463 | 4.804 / 5.317 |
| E0b monotone | yes | yes |

**E0b, per run** (`agentload_analysis_stable/20261031-11220{2,4}/stable_runs.csv`; realized rate = arrivals in the plan before 3000 s / (3000 λ_ref), D `pool_sweep_e0b.csv`). The rule: stable means not aborted, final queue < 50 and OLS rise ≤ 10 over the last window.

| pool | × | realized × | stable | final queue | trend rise |
|---|---|---|---|---|---|
| 150k | 1.1 | 1.249 | yes | 0.0 | 0.0 |
| 150k | 1.2 | 1.356 | yes | 3.25 | 1.41 |
| 150k | 1.3 | 1.463 | **no** | 24.2 | 11.9 |
| 150k | 1.45 | 1.622 | no | 53.9 | 36.0 |
| 150k | 1.6 | 1.780 | no | 74.3 | 50.2 |
| 150k | 1.8 | 1.990 | no | 125.4 | 83.6 |
| 600k | 2.5 | 2.726 | yes | 0 | 0 |
| 600k | 3.0 | 3.248 | yes | 0 | 0 |
| 600k | 3.5 | 3.765 | yes | 0 | 0 |
| 600k | 4.0 | 4.287 | yes | 0 | 0 |
| 600k | 4.5 | 4.804 | yes | 0 | 0 |
| 600k | 5.0 | 5.317 | **no** | 538 | 321 |

All E0b runs use seed 0. Its arrival plans run 6–14% above nominal: 600k ×1.06–1.09, 150k ×1.105–1.135. The same seed-0 excess appears in pred2's E0F retrodiction (2.199 at 2.0 ×).

## Scoring against the frozen theory

**Sources.**
- Frozen predictions: tag `r13-theory-pred` (`997d2c4`), `results/theory/merged/a100_pool{150k,600k}.json`.
- Rules: `notes/THEORY_r13_scoring.md` and `analysis/theory/merged/scoring.yaml`.
- Grid lookups and rivals: tag `r13-theory-pred2` (`cfa7712`), `results/theory/pred2/blind_tables.json`, i.e. `pool_lookup` (every integer n, every 0.01 multiple) and `rivals`.
- 600k n = 96 lies outside the pred2 lookup, which stops at 1.3 n_b. It is read from the frozen JSON's grid point instead.

**Rules applied.**
- Primary estimator: turns-based.
- μ_max and window: F1, ±10%.
- Peak n: inside the flat top or at the next grid point.
- n_half: fluid, ±3 sessions.
- E0b bracket: equal = hit, one grid step = near miss, two or more = miss.

Table: D `pool_sweep_scoring.csv`.

| quantity | 150k pred | 150k meas | verdict | 600k pred | 600k meas | verdict |
|---|---|---|---|---|---|---|
| μ_max turns (F1) | 0.1339 | 0.1201 | **miss** (+11.5%) | 0.3914 | 0.4084 | hit (−4.2%) |
| μ_max sessions (also reported) | 0.1339 | 0.1183 | miss (+13.2%) | 0.3914 | 0.4278 | hit (−8.5%) |
| window μ_max/λ_ref turns (F1) | 1.87 | 1.68 | **miss** (+11.5%) | 5.47 | 5.71 | hit (−4.2%) |
| peak n (F1) | 14 | 12 (flat top {12}) | hit (next grid point) | 45 | 48 (flat top {48}) | hit |
| n_half (fluid) | 16.91 | 16.52 | hit (+0.38) | 60.03 | 60.14 | hit (−0.11) |
| n_half (F1, band) | 16.34 | 16.52 | (−0.18) | 58.93 | 60.14 | (−1.21) |
| n_b (fluid identity T3(b)) | 18.32 | hit 0.133 at 20, 0.049 at 24 | consistent | 61.17 | hit 0.243 at 64, 0.135 at 80 | consistent (soft tail) |
| E0b bracket, F2 (edge 1.09 / 4.53 ×) | [<1.1, 1.1] | [1.2, 1.3] | **miss** (2 steps) | [4.5, 5.0] | [4.5, 5.0] | **hit** |
| E0b bracket, A's crossing (1.47 / 4.82 ×; secondary) | [1.45, 1.6] | [1.2, 1.3] | miss (2 steps) | [4.5, 5.0] | [4.5, 5.0] | hit |
| log-lik. of the six outcomes: F2 / A / F2 at realized rates (floor 1e-3) | −2.14 / −2.95 / −3.59 | | | −0.93 / −0.54 / −1.74 | | |
| refutation rules | window ≥ 2.5 or hit(24) ≥ 0.5 | 1.68, 0.049 | **not refuted** | window < 4.5 or hit(48) < 0.5 | 5.71, 0.921 | **not refuted** |
| RMS rel. err. of F1 μ vs turns, n < n_b | | 13.3% (6 pts) | | | 6.0% (5 pts) | |

**Reading.**
- **600k:** every frozen quantity is a hit. The error is −0.1 sessions on the 0.5-hit crossing and −4% on the window, and the E0b bracket is exact; its F2 P(unstable) is 0.470 at 4.5 × and 0.847 at 5.0 ×.
- **150k:**
  - The cliff is hit: crossing +0.4, peak n next to the measured one, F1 hit(20) 0.133 against 0.133 measured.
  - The height misses by 1.5 points beyond the tolerance. F1 μ_max is +11.5%, the declared upward-bias direction (+3.6% to +11.6% on the measured cells). The freeze record also lists the MF margin at 150k as 0.01 composition s.d., the second-worst after the H200.
  - The from-empty edge misses: F2 says the 1.1 × run is already unstable (P = 0.51), but 1.1 and 1.2 × were stable and 1.3 × was the first unstable.
  - A's level crossing errs the other way: 1.47 ×, two steps high. Neither edge heuristic brackets the 150k edge.
  - F2 at the realized rates fits worse still (it predicts P = 0.76 / 0.88 unstable for the two stable runs). F2 is too pessimistic at small pools.
- **μ on the all-miss branch:**
  - At n = 300 the synchronized-start graft (A) gives 0.106 / 0.112 turns, against 0.108 / 0.110 measured (−1.7% / +1.5%). This is also reported.
  - The stationary μ_b (0.0688 / 0.0732) lies 3–9% from the n = 20–24 / 80–96 points.
  - The 150k all-miss state is only 0.90 μ_max at n = 300: the closed-system collapse is shallow at 150k, while the open-system edge still sits at 1.2–1.3 ×.

## Rivals

Rival quantities are from pred2 `rivals` and Corollary C (`notes/PREDICTIONS_r13_pred2.md` §6, §8 2a.4).

| predictor of the 0.5-hit crossing | 150k | error | 600k | error |
|---|---|---|---|---|
| measured | 16.52 | | 60.14 | |
| capacity ratio M/E_S (AgentKV / MISA-T form) | 13.59 | −2.94 | 56.13 | −4.01 |
| Denning M/E_lb | 14.23 | −2.30 | 56.88 | −3.26 |
| M/Ē | 14.19 | −2.33 | 56.77 | −3.37 |
| **frozen n_half (fluid, with the queue term)** | **16.91** | **+0.38** | **60.03** | **−0.11** |
| Che, exogenous gap W = Z | 26.47 | +9.95 | 105.85 | +45.71 |
| Yao Thm 3.1 closed by Little (no service) | 23.94 | +7.41 | 95.75 | +35.61 |

- **Frozen rule** (nearest crossing wins): the frozen n_half wins at both pools.
- **T3(b) tool-call term** is supported iff the crossing exceeds M/E_S + ½(n_b − M/E_S), which is 15.96 at 150k and 58.65 at 600k. Measured: 16.52 and 60.14, so it is **supported at both**. At 150k the margin is only 0.56 sessions.
- **The exogenous-gap closures** never reach the measured near-zeros:
  - 150k, n = 24: Che 0.551, Yao-Little 0.499, against 0.049 measured;
  - 600k, n = 96: 0.551 / 0.499 against 0.006.
  - Their crossings lie 45–76% above the cliff, as Proposition E said they would.

## Window-scaling law across GPU and pool

Peak ratio = μ_max / λ_ref (turns / sessions). Edge = the E0b bracket (largest stable, first unstable). "Pred" = the frozen F1 window and the F2 50% edge.

| cell | measured peak ratio (turns / sessions) | pred window (F1) | measured edge bracket | pred F2 edge [bracket] | source of measured |
|---|---|---|---|---|---|
| A100 150k | 1.68 / 1.65 | 1.87 | [1.2, 1.3) | 1.09 [—, 1.1] | this sweep |
| A100 300k | 3.15 / 3.26 | 3.27 | [2.0, 2.5) | 2.34 [2.0, 2.5] | frozen validation table (`r13-theory-pred` `validation_table.md`) |
| A100 600k | 5.71 / 5.98 | 5.47 | [4.5, 5.0) | 4.53 [4.5, 5.0] | this sweep |
| A100 native (955,757) | 6.48 / 6.67 | 6.89 | [5.5, 6.5) | 6.26 [5.5, 6.5] | frozen validation table |
| H200 300k | 1.89 / 1.99 | 1.92 | 1.3–1.4 | 1.39 [1.25, 1.5] | H200 session (as given to this cell; not read here) |
| H200 600k | 2.98 / 3.05 | 3.20 (pred2 `h200_600k`; fluid 3.27) | [2.5, 3.0) | 2.57 [2.5, 3.0] | H200 session (as given; not read here) |

**Ratios in the 2×2** (measured, turns; predicted F1):

| ratio | measured | predicted |
|---|---|---|
| pool doubling 300k → 600k, A100 | 5.71 / 3.15 = 1.81 | 1.67 |
| pool doubling 300k → 600k, H200 | 2.98 / 1.89 = 1.58 | 1.67 |
| speed, H200 / A100 at 300k | 0.60 | 0.59 |
| speed, H200 / A100 at 600k | 0.52 | 0.58 |
| pool halving 300k → 150k, A100 | 1.68 / 3.15 = 0.53 | 0.57 |

- **Shape of the law:** the window grows with the pool and shrinks with GPU speed. The model puts that dependence in s·z̄ and M/E_S.
- **Measured vs predicted:** the measured pool effect is steeper than predicted on the A100 and shallower on the H200. The speed effect is as predicted at 300k but stronger at 600k.
- **Edge/window:** the measured edge-bracket midpoint is 0.71–0.93 of the measured window in all six cells (150k 0.75, 300k 0.71, 600k 0.83, native 0.93, H200 300k 0.71, H200 600k 0.92).
- **F2 bracket score:** the F2 edge brackets the measured edge in five of six cells; it misses only at 150k.

## Blindness

- **Freeze times.** Both theory freezes were on GitHub before any pool job started. From `gh api repos/AkshatValse/Nova-Research/activity`:
  - `r13/theory` branch creation at `997d2c4` (tag `r13-theory-pred`): 2026-10-31 07:05:30Z = 02:05:30 CDT;
  - `r13/pred2` branch creation at `cfa7712` (tag `r13-theory-pred2`): 09:20:20Z = 04:20:20 CDT.
- **Job times.** From sacct: Eligible 02:30:32 CDT for all 18 jobs (after the first freeze, before pred2). Start times:

| job | Start (CDT 10-31) | End |
|---|---|---|
| 17168864 / 65 / 66 | 06:50:13 / 06:51:44 / 06:53:15 | 09:15:51 / 09:17:18 / 09:18:50 |
| 17168867 / 68 / 69 | 06:57:18 / 07:36:14 / 07:45:19 | 09:22:42 / 10:01:50 / 10:11:00 |
| 17168870–75 | 07:45:19, 08:36:14, 08:40:01, 08:48:58, 09:13:58, 09:15:51 | 08:39:54 … 10:10:15 |
| 17168876–81 | 09:17:19, 09:18:50, 09:30:40, 09:43:46, 10:01:53, 10:08:26 | 10:11:42 … 11:03:30 |

- **Margins.** The earliest Start (06:50:13) is 4 h 45 min after the first push and 2 h 30 min after pred2. No pool-sweep datum existed at either freeze, so both prediction sets are **blind in time** for every number above.
- **pred2's pool lookups** were tabulated without the per-job n or multiples (pred2 §8 2a.7), so they cannot be tuned to the grid.
- **Not blind:** the comparison cells' measured values (A100 300k, native) were known to the theory, which used them for validation. The H200 n = 16–32 Stage C values were seen by the H200 operator before the first freeze (COORDINATION, lead additions).

## Caveats

- One run per n and one seed per E0b multiple. The brackets are single-path outcomes; the theory's own P(unstable) at 4.5 × (600k) is 0.47.
- The seed-0 plans arrive 6–14% above nominal. The realized-rate brackets are 1.36 / 1.46 × (150k) and 4.80 / 5.32 × (600k).
- The E0b grid steps differ (0.1–0.2 at 150k, 0.5 at 600k), so "one grid step" means different widths.
- The 600k collapse has a soft tail: hit 0.135 at n = 80, where fluid and F1 give 0.000.
- The F1 μ errors inside the 150k collapse are large: +19%, +25% and +28% at n = 14, 16 and 20.
- SGLang warns that the context length (49152) exceeds the derived 32768 in every server log. This warning is the same in every earlier SGLang cell, and no request errored.

## Suggested text

> **Pool sweep (out of sample, blind in time).** We re-ran the calibrated A100 cell with the KV pool halved (150,000 tokens) and doubled (600,000), with no parameter refitted and with both prediction sets pushed before the first job started. At 600k the frozen model predicted the window (5.47 vs 5.71 measured, turns-based), the 0.5-hit crossing (60.0 vs 60.1 sessions) and the from-empty edge bracket [4.5, 5.0) × λ_ref exactly. At 150k it located the cliff (crossing 16.9 vs 16.5; peak n 14 vs 12) but overstated the peak by 11.5%, just outside the ±10% tolerance, and its from-empty edge (1.09 ×) was too pessimistic: the server held 1.2 × and failed at 1.3 ×. No refutation rule fired at either pool. At both pools the nearest predictor of the crossing was the frozen n_half, which includes the sessions in tool calls; the capacity ratio M/E_S was 2.9 and 4.0 sessions early, and the exogenous-gap closures of Che and Yao were 7–46 sessions late. Across the A100/H200 × 300k/600k grid, the window grows with the pool and shrinks with GPU speed as the s·z̄ law predicts (pool-doubling factor 1.81 / 1.58 measured vs 1.67 predicted), and the measured from-empty edge sits at 0.71–0.93 of the window in all six cells.

**Table row** (blind-cell table):
`A100 150k | 1.87 / 1.68 (miss, +11.5%) | 16.9 / 16.5 (hit) | edge 1.09 / [1.2, 1.3) (miss) | not refuted`
`A100 600k | 5.47 / 5.71 (hit, −4.2%) | 60.0 / 60.1 (hit) | edge 4.53 / [4.5, 5.0) (hit) | not refuted`

## Figure spec: "Peak ratio and edge vs pool size and GPU, measured vs predicted"

- **Data:** the window-scaling table above, as CSV columns: cell, gpu, pool_tokens, meas_ratio_turns, meas_ratio_sessions, pred_window_F1, pred_window_fluid, edge_lo, edge_hi, pred_edge_F2, pred_edge_A.
  - Pool sweep: D `pool_sweep_scored.json`.
  - 300k and native: `r13-theory-pred:results/theory/merged/validation_table.md` and `a100_{300k,native}.json`.
  - H200: the H200 cell's paper input; H200 600k prediction: `r13-theory-pred2:results/theory/pred2/h200_600k.json`.
- **Layout:** one panel, log-x pool size M (150k, 300k, 600k, 956k), y = multiple of λ_ref (each GPU's own λ_ref). Two series by colour, A100 and H200.
- **Marks:**
  - Measured peak ratio (turns-based): filled circle; sessions-based: a small tick.
  - Frozen F1 window: an open circle joined by a dashed line across pools (the prediction curve). A100 uses `pool_lookup`'s window at each pool; H200 uses 300k and 600k.
  - Measured E0b bracket: a vertical bar from largest-stable to first-unstable, offset slightly right of the circle.
  - F2 50% edge: an open triangle on the bar; A's crossing: a small open square (secondary).
- **Annotation:** mark the one F2 bracket miss (A100 150k) and the one window miss (A100 150k, +11.5%).
- **Optional inset:** edge midpoint / measured window per cell (0.71–0.93), showing the edge tracks the window.
