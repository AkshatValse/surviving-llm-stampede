# Round 11, S1 bundle 2: blind simulator predictions for L1 (LPM-INF)

Written 2026-10-30 (about 19:50 CDT), before any LPM-INF (`sglang-lpminf`) engine run exists. Frozen endpoints: `configs/r11_lpminf_predict.yaml`.
Spec: `configs/r11_predict_lpminf.yaml`. Driver: `experiments/r11_predict_lpminf.py`. Instrumented runs and the sticky-fallback variant:
`src/prefixmeta/r11_lpm_sim.py` (a new file; no existing simulator default is changed). Tests: `tests/test_r11_lpm_fallback_sim.py`.
Result dir (summaries, force-added): `results/r11_predict_lpminf/20261030-194911/` (`headline.json`, `summary.csv`, `runs.csv`, `tables.md`,
`engine_seed_windows.csv`, `plan_checks.csv`, `meta.json`). The per-window data of the 10 extra seeds (`full/`) are not committed; the driver
regenerates them bit for bit in about 5 s.

## What is predicted

The L1 step-2 cell on the real engine: SGLang 0.5.22, POLICY=lpm, REFRESH=1, LPM_INF=1 (the job-local hook raises
`WAITING_QUEUE_PREFIX_MATCH_MAX` from 128 to 1e9, so LPM never falls back to FCFS order), BURST arm, 300k pool, E2 protocol (200 sessions in 60 s at
t = 1200 s, 8700 s run), 1.65 x lambda_ref = 0.118031 sessions/s, seeds 0, 1, 2.

Simulator arms, all on the same client plans (common random numbers):

| arm | simulator policy | role |
|---|---|---|
| fcfs | `fcfs_lru` | FCFS reference (the engine FCFS cell's outcome is known to the lead) |
| lpm128 | `lpm128_lru` (`LpmFallback(128)`) | stock LPM: plain FCFS order in any pass with more than 128 waiting requests. Retrodiction. |
| **lpminf** | `lpm_lru` (pure LPM) | **the predicted cell** (LPM-INF) |
| lpm128s | `lpm128s_lru` (`LpmFallbackSticky(128)`) | labelled sensitivity: stock LPM with SGLang's real fallback order (the queue keeps its last LPM sort; arrivals are appended) |

Engine: the round-6 calibrated engine block inherited unchanged from `configs/r6_predict.yaml` (asserted by the driver). PRIMARY column: mixed
batching. SECONDARY (labelled): `separate_prefill_priority`. Seeds: 0-2 on the exact client plans (`agentload.workload.build_open_plan` on
`configs/agentload_e2_burst.yaml`), plus 10 extra seeds (100-109) from the same generator.

Before simulating, the driver reproduces the `plan.csv` of the six committed stock-LPM 1.65 x BURST runs (sglang-lpm-r0 and -r1, seeds 0-2,
`results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_e2_burst/{20261025-061332,-074047,-084258,-090204,-105152,-112253}`).
Arrival times, turn counts, origins and the resolved rate match bit for bit. Tool-time totals match to 1.7e-13 s (last-bit libm differences between
Nova and the PC). These are the plans the LPM-INF jobs will send.

## Headline prediction for the real LPM-INF BURST runs (mixed, primary)

| seed | token hit over W = [5700, 8700) | collapse (< 0.05) | trap_v2 state | turn hit over W | p99 latency over W (s) | unfinished sessions |
|---|---|---|---|---|---|---|
| 0 | 0.093 | no | trapped | 0.137 | 263.2 | 334 |
| 1 | 0.080 | no | trapped | 0.125 | 233.8 | 295 |
| 2 | 0.100 | no | trapped | 0.142 | 245.5 | 321 |
| 10 extra seeds | 0.069-0.118 (mean 0.097) | 0/10 | 6 trapped, 4 indeterminate, 0 recovered | | 197-315 | 232-387 |

Predicted outcome of the frozen decision rule: **consistent** with the 128-request fallback causing stock LPM's collapse. Pure LPM does not
collapse on seed 0 or seed 1 (nor on seed 2, nor on any extra seed). It also does **not recover**: it stays in a partial-hit state (token hit
about 0.08-0.10, turn hit about 0.12-0.14) with uncached prefill at about 1.02 x the all-miss rate and a growing backlog (slope 0.025-0.034
sessions/s, against the 0.023 threshold). The registered trap_v2 rule therefore labels it **trapped** in 3/3 engine seeds. The primary endpoint
and trap_v2 are predicted to disagree on every INF run. This is the case the plan anticipated: trap_v2 cannot tell a partial-hit slow growth
from an all-miss trap.

Margin. In mixed mode the predicted token hit is only 0.03-0.05 above the 0.05 cut. The simulator is expected to be pessimistic about LPM (see
Fidelity). The secondary column is much further from the cut: separate batching gives token hit 0.38-0.42 on seeds 0-2 (extra seeds 0.35-0.56),
0/13 collapses, with states s0 indeterminate, s1 trapped and s2 indeterminate (extra seeds: 6 draining, 4 indeterminate).

Same-seed contrasts (mixed; lpminf minus lpm128):

| seed | token hit over W | unfinished sessions | p99 latency over W (s) | miss-turn p99 latency over W (s) | max waiting queue |
|---|---|---|---|---|---|
| 0 | 0.093 vs 0.000 | 334 vs 364 (-30) | 263.2 vs 261.2 (+0.8%) | 263.9 vs 261.2 | 308 vs 335 |
| 1 | 0.080 vs 0.000 | 295 vs 317 (-22) | 233.8 vs 231.6 (+0.9%) | 234.1 vs 231.6 | 265 vs 287 |
| 2 | 0.100 vs 0.000 | 321 vs 353 (-32) | 245.5 vs 246.4 (-0.4%) | 245.7 vs 246.4 | 292 vs 321 |

Starvation (pure LPM can make a miss wait behind every hit). The simulator predicts that miss turns wait for the whole queue: miss-turn queue
wait p99 is about 210-240 s, against about 2 s for hit turns. But no turn waits longer than 600 s in any run of any arm, and INF leaves 22-32
fewer sessions unfinished than stock on the same seed. The frozen trade-off clause ("p99 turn latency over W above stock's") has no tolerance.
The simulator puts INF's p99 within 1% of stock's on every seed (above stock on seeds 0 and 1, below on seed 2), so the sign of that comparison
is **not predicted**. A p99 difference of about 1% on the engine should be read as noise, not as a trade-off.

## Retrodictions (outcomes known to the lead; not blind)

- **Stock LPM-128 (mixed):** collapses on seeds 0, 1 and 2 (token hit over W 0.000), trap_v2 trapped 3/3, and collapses on 10/10 extra seeds. The
  engine's committed stock-LPM 1.65 x runs (from the task text): trapped or stuck in 4 of 6 runs, both replicates of seeds 0 and 1, neither
  replicate of seed 2. So the simulator matches seeds 0-1 (4/4 runs) and misses seed 2 (0/2). The scout's scratch runs (COORD/scope_lpm/sim) found
  the same pessimism at 1.35 x: simulated LPM-128 traps 9/10, while the engine's stock LPM recovered there in most runs. The simulator's stock LPM
  is too willing to collapse, so its pure-LPM column is expected to be pessimistic too.
- **Sticky fallback (lpm128s):** identical to lpm128 on the three mixed-mode engine seeds. On 3 mixed extra seeds the latency and max queue differ
  slightly, but collapse, token hit and state are the same on all 13. In separate mode the engine seeds differ only in latency and queue (all
  three collapse and are trapped under both orders). One extra seed, 101, changes from indeterminate (token hit 0.26) to draining (0.45); the
  collapse count is 7/10 under both orders. Which fallback order the simulator uses does not change the prediction. What matters is that the
  order stops being LPM once the queue passes 128.
- **FCFS:** collapses 3/3 (and 10/10 extra), trap_v2 trapped 3/3.

## Blindness scope (exactly what was and was not blind)

- Blind: every lpminf (pure-LPM) row. No LPM-INF engine run exists. No `sglang-lpminf` job has been submitted, and none can run before the
  registration and these files are committed.
- Not blind: the lead knows the committed stock-LPM grid outcomes (at 1.65 x, trapped or stuck in 4 of 6 runs) and the FCFS outcomes. The task
  text that produced these predictions also stated that 4-of-6 figure, and the scout's post-hoc queue-vs-128 analysis and scratch simulator
  runs (COORD/scope_lpm/, with pure LPM at "hit about 0.15, not recovered") were read before this bundle. No engine outcome file (`requests.csv`,
  `windows`, `outcome`, analyses) was opened for this bundle. The only engine files read were the six committed runs' `plan.csv` and their
  `meta.json` (argv, label, resolved rate). Nothing in the spec or the endpoints was set from an outcome: the engine block, workload, rate,
  protocol, endpoint constants and decision rule all come from the round-6 spec, the registered prereg file and the r11 plan item L1.

## Provenance

- The run used a clean scratch clone of this branch at 4d2bba2 plus a scratch commit holding exactly the five bundle-2 files: HEAD `f02fa4b`,
  `simulation_inputs_clean_vs_head: true`, empty `git status`. That commit exists only in the scratch clone; the sha256 of every simulation
  input (all of `src/prefixmeta/*.py`, the two configs, the driver, the agentload workload/config modules and configs) is in
  `meta.json → sha256`, and every one equals the file committed here. Command (from the clone):
  `PYTHONPATH="src;." python -B experiments/r11_predict_lpminf.py run --workers 6 --plan-root <this worktree>`. `--plan-root` reads the six
  committed `plan.csv`/`meta.json` from this worktree, because the scratch clone's paths exceed Windows MAX_PATH; the driver refuses unless each
  file is git-blob-identical to HEAD.
- 104 simulations (4 arms x 2 modes x 13 seeds), 5.2 s on 6 workers, Akshat-PC (Windows 11, Python 3.12.10, NumPy 1.26.4).
- Tests: `tests/test_r11_lpm_fallback_sim.py`, 15 pass in this worktree. They check that the instrumented run reproduces `prefixmeta.sim.simulate`
  exactly for fcfs/lpm128/lpm (windows, queue and backlog traces, counters, both batching modes); that the per-turn records agree with the
  engine counters; that the sticky variant equals pure LPM when its threshold is never reached and keeps the last LPM order during a fallback
  pass; that the frozen endpoint constants equal the registered pass_rule; and they cover plan reproduction and the decision rule. No existing
  `src/` file was edited, so the golden digests are untouched. The 18 known Windows-only bit-identity failures (the polyfit last bit) are unchanged.

## Simulator analogues and fidelity (read before scoring)

- Token hit = sum of cached tokens / sum of prompt tokens over turns completing in W. A simulator hit caches the whole previous context
  (P_t - 550 tokens), a miss caches nothing: there are **no partial hits**. The engine's radix cache gives partial prefix hits, and LPM sorts by
  partial matches too.
- Not modelled: the per-pass LRU touch of waiting requests' prefixes by LPM's matching (radix_cache `_match_prefix_helper`), SGLang's LPM tie order
  (stable on the previous queue order rather than FCFS), scheduler CPU cost (about 0.01 s/s per 100 waiting requests on the engine), and the
  hook itself. These omissions should make the simulator pessimistic about pure LPM. The scout's engine-side extrapolation (hit 0.15-0.6 at
  1.65 x) sits above this bundle's 0.08-0.10.
- trap_v2 in the simulator: criterion (a) against the simulator's own all-miss token rate (r6 B1: 11,219.7 tok/s mixed, 11,146.8 separate); the
  ratio to the registered 11,243.18 is recorded too (`token_ratio_registered_ref`). Criterion (b) is the OLS slope of 10 s bin means of
  sessions in the system, the same as the engine's. RECOVERED uses the turn hit and the outstanding requests over the last 300 s.
- Turn latency is completion minus turn ready time (the client's send). Miss-turn latency and queue wait are reported separately.

## Scoring against the engine (frozen in configs/r11_lpminf_predict.yaml → decision_rule.simulator_comparison)

Per seed: the primary collapse flag matches; the trap_v2 state matches; and |token hit over W (engine) - simulator| <= 0.1. A predicted
INF seed scores a numeric match if the engine's token hit is in [0, 0.193] (seed 0), [0, 0.180] (seed 1) or [0, 0.200] (seed 2). A miss is
reported, not explained away. Separate-batching values are a labelled secondary and are not scored.
