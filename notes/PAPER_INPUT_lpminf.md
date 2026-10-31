# Paper input: LPM-INF (r11 L1 step 2), stock LPM with its 128-request FCFS fallback disabled

Branch `r11/lpminf`. Status: **EXPLORATORY** (BURST arm only, one rate, three seeds, of which two are informative under the frozen rule). Not a registered decisive test. LOG entry: `notes/LOG.md`, 2026-10-31.

## Verdict

Frozen decision rule (`configs/r11_lpminf_predict.yaml → decision_rule`): **consistent** with the 128-request fallback causing stock LPM's collapse. LPM-INF did not collapse on seed 0 or seed 1. On those two arrival streams, stock LPM collapsed in 4 of 4 runs (both replicates of each).

The manipulation was verified on all three runs. On seed 2 the queue never passed 128, so the scheduler-cost item there is uninformative and that run is in effect a stock-LPM replicate. Seed 2 does not enter the rule.

## What was run, and provenance

- **Cell** `sglang-lpminf`: SGLang 0.5.22, Qwen2.5-7B-Instruct, one A100 80GB PCIe, 300k-token KV pool, POLICY=lpm, REFRESH=1, LPM_INF=1. A job-local `sitecustomize` hook (`slurm/hooks/lpm_inf/sitecustomize.py`, md5 `be788ae7495e6445788bad8bd370349a`) raises `sglang.srt.managers.schedule_policy.WAITING_QUEUE_PREFIX_MATCH_MAX` from 128 to 1e9 in the stock environment. Nothing else changes.
- **Protocol:** E2 BURST: 200 sessions in 60 s at t = 1200 s, 8700 s run, 1.65 × λ_ref = 0.11803 sessions/s, seeds 0, 1, 2.
- **Frozen before submission** (`r11/lpminf` at `5064580`, tag `r11-lpminf-pred`, GitHub push 2026-10-31 02:02:46 UTC = 21:02:46 CDT Fri, from `gh api repos/AkshatValse/Nova-Research/activity`):
  - the exploratory registration `configs/agentload_prereg_2026-10-30_grid_sglang-lpminf.yaml` (PREREG_SHA256 `f4454c5bbcf756cf62c885a2b18208074885f5256b1eacbc01ebb403c24973f2`);
  - the endpoints and decision rule `configs/r11_lpminf_predict.yaml`;
  - the blind simulator predictions `notes/PREDICTIONS_r11_lpminf.md` (`results/r11_predict_lpminf/20261030-194911/`).
- **Jobs:** 17168743 (seed 0), 17168744 (seed 1), 17168745 (seed 2). Submitted 2026-10-30 22:07:40 CDT from the Nova clone `$W/repo_r11_lpm` (HEAD `5064580`, clean). All COMPLETED 0:0; they ended Sat 03:51:56, 04:12:05 and 04:23:48 CDT.
- **Data:** `results/nova/lpminf_1716874x_pulled_20261031-042548/` (commit `fc8b028`; archive sha256 `ce1eb62db3ba3b96052f62b6ee137f973a39d5aae9023a1bda80e8acf51d00ca`).
  - Run dirs: `results/agentload_e2_burst/20261031-012346`, `-014355`, `-015539`.
  - Verdict: `results/agentload_analysis_burst2/20261031-042736`, made by `summarize burst2 --prereg <exploratory file>` with the E2 overrides (`burst.trap_min_s=3000`, `burst.hit_eval_from_s=4500`, `trap_v2.eval_from_s=4500`).
- **Endpoints:** `analysis/r11_lpminf_eval.py` → `results/r11_lpminf_eval/20261031-eval/` (`runs.csv`, `tables.md`, `summary.json`). Every constant is read from the frozen endpoint file. Tests: `tests/test_r11_lpminf_eval.py`.
- **Controls** (same `plan.csv` sha256 per seed in every cell, common random numbers):
  - stock LPM `sglang-lpm-r1`: 17097090 / 17097096 / 17097102;
  - stock LPM `sglang-lpm-r0`: 17097091 / 17097097 / 17097103;
  - FCFS `sglang-fcfs-r0`: 17097089 / 17097095 / 17097101;
  - all three from `results/nova/r7_native_grid_vllm_pulled_20261025-145126`, verdicts `agentload_analysis_burst2/20261025-1442{30,33,36}`;
  - FCFS E2 `sglang-fcfs-r1` BURST: 17093390 / 17093396 / 17093402, from `results/nova/e2_170933xx_pulled_20261025-144558`, verdict `agentload_analysis_burst2/20261025-144012`.
- **Post-hoc context, not repeated here:** the LPM-128 crossing analysis, `analysis/lpm_crossing.py` and `notes/LPM_CROSSING_r11.md` on `origin/r11/strengthen`. In the 12 stock-LPM grid runs, 5 of 5 sustained crossings collapsed and 0 of 7 non-crossings did. That analysis is correlational; this experiment is its interventional follow-up.

## Manipulation check (frozen rule; a failing run would be excluded)

| seed | job | child-pid marker 128 → 1e9 | self-test (value, md5 b8ec334a…, LPM at queue 300) | queue max | bins with mean queue > 128 | scheduler cost there (s/s, median / min) | item | verified |
|---|---|---|---|---|---|---|---|---|
| 0 | 17168743 | pid 3826316 (parent = server 3826257) | pass | 165 | 42 | 0.0130 / 0.0107 | PASS (42/42 ≥ 0.008) | yes |
| 1 | 17168744 | pid 3327643 (parent = server 3327586) | pass | 184 | 94 | 0.0144 / 0.0119 | PASS (94/94) | yes |
| 2 | 17168745 | pid 3330171 (parent = server 3330103) | pass | 120 | 0 | — | UNINFORMATIVE | yes (hook never exercised) |

In stock LPM and FCFS bins with a queue above 128, the scheduler cost is 0.0027–0.0031 s/s, the FCFS level. So on seeds 0 and 1 the queue did exceed 128 while LPM's prefix matching stayed active.

## Numbers (W = [5700, 8700) s; source `results/r11_lpminf_eval/20261031-eval/runs.csv`)

| seed | cell | token hit W | collapse (< 0.05) | trap_v2 state | uncached tok/s ÷ all-miss | p50 / p99 turn latency W (s) | unfinished sessions |
|---|---|---|---|---|---|---|---|
| 0 | LPM-INF | 0.595 | no | draining | 0.84 | 12.0 / 210.7 | 104 |
| 0 | stock LPM (r1; r0) | 0.000; 0.000 | yes; yes | trapped; trapped | 1.05; 1.00 | 217.6 / 262.9; 228.9 / 278.7 | 354; 361 |
| 0 | FCFS (E2 r1; r0) | 0.000; 0.000 | yes; yes | trapped; trapped | 1.03; 1.04 | 240.7 / 277.6; 234.5 / 271.1 | 370; 366 |
| 1 | LPM-INF | 0.419 | no | indeterminate | 0.92 | 149.0 / 230.8 | 194 |
| 1 | stock LPM (r1; r0) | 0.000; 0.000 | yes; yes | trapped; trapped | 1.02; 1.02 | 200.1 / 238.5; 198.5 / 237.6 | 318; 317 |
| 1 | FCFS (E2 r1; r0) | 0.000; 0.000 | yes; yes | trapped; trapped | 1.03; 1.03 | 202.2 / 240.3; 202.1 / 240.2 | 320; 320 |
| 2 | LPM-INF (queue ≤ 120, hook inert) | 0.557 | no | draining | 0.88 | 13.5 / 113.9 | 59 |
| 2 | stock LPM (r1; r0) | 0.442; 0.816 | no; no | indeterminate; recovered | 0.92; 0.34 | 72.9 / 118.2; 1.6 / 30.6 | 105; 11 |
| 2 | FCFS (E2 r1; r0) | 0.000; 0.000 | yes; yes | trapped; trapped | 1.03; 1.03 | 212.8 / 255.8; 213.5 / 255.9 | 361; 360 |

- No turn waited longer than 600 s in any LPM-INF run (maximum 241 s). LPM-INF miss-turn p99 over W was 215 / 234 / 118 s, so there is no starvation beyond what stock LPM and FCFS show.
- Queue: LPM-INF passed 128 at nearly the same time as stock r1 on the same stream (s0: 2475 vs 2525 s; s1: 1855 vs 1865 s) and held above it for 1150 s and 2780 s (longest stretches). After the crossing its 900-s mean queue stayed between 82 and 168, while stock's grew to 255–294.
- Token-hit time course (900-s bins): both cells fall to about 0.2–0.3 at 1800–2700 s, before either queue reaches 128. After that, stock falls to 0.000 and LPM-INF climbs back to 0.4–0.6.

## Against the blind simulator predictions (scored per the frozen rule)

| seed | predicted token hit (mixed) | engine | abs diff (tolerance 0.1) | collapse flag | trap_v2 predicted → engine |
|---|---|---|---|---|---|
| 0 | 0.093 | 0.595 | 0.50 (miss) | match (no) | trapped → draining (miss) |
| 1 | 0.080 | 0.419 | 0.34 (miss) | match (no) | trapped → indeterminate (miss) |
| 2 | 0.100 | 0.557 | 0.46 (miss) | match (no) | trapped → draining (miss) |

The predicted outcome of the rule ("consistent") holds, and so does no collapse on 3/3. The level and the trap_v2 state miss on 3/3. The engine is much better than the simulator's pure LPM.

The labelled separate-batching column predicted 0.38–0.42 and is the closer of the two, but it also misses the states. The simulator was flagged in advance as pessimistic about LPM: it has no partial prefix hits and no LRU touch of waiting prefixes by LPM's matching.

## Caveats (each must travel with any sentence that uses this result)

1. **Exploratory.** One rate (1.65 ×), BURST arm only, three seeds. Only seeds 0 and 1 are informative, because stock LPM never collapsed on seed 2. No pooled interval or p-value.
2. **Replicate noise is large in the partial-hit regime.** On seed 2, three LPM runs with an effectively identical configuration (stock r0, stock r1, and INF, all with the queue below 128) gave token hit 0.82, 0.44 and 0.56. So 0.42–0.59 versus 0.000 on seeds 0–1 is a clear qualitative difference. INF-versus-stock differences of a few tenths in token hit, or in p99, are not interpretable.
3. **Pure LPM is not a fix.** No LPM-INF run recovered by the registered rule. Seed 1 ends indeterminate, with 189 requests outstanding and uncached prefill at 0.92 × the all-miss rate.
4. **Mechanism not separated.** The fallback switches off two things at once: LPM ordering, and the LRU touch of waiting requests' prefixes during LPM's prefix matching. LPM-INF keeps both, so this result cannot say which one prevents the collapse. The refresh flag is not the explanation: `-r0` (refresh off) collapsed on seeds 0–1 like `-r1`.
5. **Identity of the marking process is inferred.** The child that logged the hook marker is taken to be the scheduler. It is the only spawned child that imports `schedule_policy`, and the scheduler-cost behaviour shows LPM active above the threshold. The log does not name the process.
6. **Different days and nodes.** LPM-INF ran on 2026-10-31 on nova22-gpu-1/-2, and the controls on 2026-10-24/25. The arrival plans are byte-identical, but engine timing is not deterministic.

## Suggested text (paragraph)

> **Removing LPM's fallback (exploratory).** SGLang's LPM policy silently reverts to FCFS order whenever more than 128 requests are waiting (`WAITING_QUEUE_PREFIX_MATCH_MAX`). In the grid, every stock-LPM run whose queue stayed above 128 collapsed, and none of the others did (§X; post hoc). To test this causally, we reran the three 1.65 × λ_ref BURST streams with the constant raised to 10⁹ by a job-local hook. The arrival plans were byte-identical, and the engine was otherwise unchanged. We verified in each run that the spawned engine child that imports the scheduling policy (the scheduler) loaded the patched value, and, on the two informative streams, that LPM's prefix-matching cost persisted while the queue exceeded 128. On the two streams where stock LPM had collapsed in all four runs, LPM without the fallback did not collapse: token hit over the last 3000 s was 0.59 and 0.42, against 0.000, and the waiting queue stayed below 170 instead of growing past 250. This matches the frozen decision rule's "consistent" outcome. It does not make pure LPM a remedy: no run returned to the good state by the registered rule, and one stayed at 0.92 × the all-miss prefill rate with a large backlog. The blind simulator predicted the absence of collapse but put the hit rate at 0.08–0.10, well below the engine. With one rate and two informative seeds this is directional evidence that the trap under stock LPM is triggered by its FCFS fallback, not by LPM ordering itself.

## Suggested table rows (for a mechanism table; 1.65 × λ_ref, BURST, seeds 0 / 1 / 2)

| policy | token hit [5700, 8700) | collapsed | trap_v2 | unfinished sessions | source |
|---|---|---|---|---|---|
| FCFS (E2, `sglang-fcfs-r1`) | 0.000 / 0.000 / 0.000 | 3/3 | trapped ×3 | 370 / 320 / 361 | jobs 17093390, -96, 17093402 |
| stock LPM (`sglang-lpm-r1`) | 0.000 / 0.000 / 0.442 | 2/3 | trapped, trapped, indeterminate | 354 / 318 / 105 | jobs 17097090, -96, 17097102 |
| stock LPM (`sglang-lpm-r0`) | 0.000 / 0.000 / 0.816 | 2/3 | trapped, trapped, recovered | 361 / 317 / 11 | jobs 17097091, -97, 17097103 |
| LPM, fallback disabled (`sglang-lpminf`, exploratory) | 0.595 / 0.419 / 0.557† | 0/3 | draining, indeterminate, draining | 104 / 194 / 59 | jobs 17168743–45 |

† Seed 2: the queue never passed 128, so the hook was inert in that run.
