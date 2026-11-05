# Paper input: r15 blind tests of 2026-11-05 (TOOLSLOW-W, REPLICATE-EDGE; CUT and A2 to follow)

Written 2026-11-05 from 06:20 CST by the lead session, on branch `r15/tonight`. Every number below comes from files in this
worktree. The pull is `results/nova/r15_t1_edge_1725667x_pulled_20261105-061000/` (abbreviated **TP**). Its `COMMANDS.txt`
holds the archive hash, the job-to-run map and the commands; `sacct_17256674-17256678.txt` holds the accounting records.
Frozen predictions: `notes/PREDICTIONS_r15.md`, `notes/PREDICTIONS_r15_edge.md` (tag `r15-reg`) and, for the trap-state
law, `notes/PREDICTIONS_icml_trap.md` (tag `icml-trap-pred`, branch `claude/theory-icml-2164a9`).

## Provenance and blindness

- **Registration:** commit `e05a262`, tag `r15-reg`, pushed at 03:18:36 CST (GitHub activity log). Five jobs were submitted at
  03:21:38 CST from the frozen clone `repo_r15_tonight` at `e05a262`, with a clean status. All five finished COMPLETED 0:0
  between 05:51:48 and 06:04:13 CST.
- **Trap-state predictions:** tag `icml-trap-pred` (`6b47a6c`) was pushed at 00:24:47 CST, about three hours before any of these
  jobs was submitted.
  - The scorer `analysis/theory/icml/score_new.py` was added at `24b5e13` (01:09 CST).
  - At `fdb80c9` (03:34 CST) it gained the unregistered γ/z column. That commit came after the jobs started and before any
    output existed.
  - The frozen inputs it reads (`configs/icml_trap_predict.yaml`, `results/theory/icml/frozen_predictions.json`) are unchanged
    between the tag and `fdb80c9` (`git diff --stat` is empty).
- **What these tests are not.**
  - T1 was designed after the r14 30 s TOOLSLOW arm trapped 1 of 3 seeds, and after reading simulator outputs. It is blind in
    outcome only, and up to 2100 s it repeats r14's d30 cell.
  - REPLICATE-EDGE is exploratory: its cell was chosen after the original outcomes were known.
  - S1–S5's tolerances were set after seeing the committed runs. The runs they score here did not exist at the tag's push.

## 1. TOOLSLOW-W (T1): a dependency slowdown alone traps the engine. Registered outcome **TRAPS** (stuck 3/3)

**Cell.**
- Label `sglang-fcfs-r1-toolslow-d30w1800`: SGLang FCFS with waiting-prefix refresh, 300k-token pool, Qwen2.5-7B-Instruct,
  "NVIDIA A100 80GB PCIe".
- Load 1.35 λ_ref = 0.096571 sessions/s, NOBURST arrivals.
- Every tool call that starts in [1200, 3000) s takes Z + 30 s.
- Seeds 0–2, 8700 s runs, W = [5700, 8700) s.
- Each run is paired by common random numbers with the committed NOBURST run of its seed at 1.35×. The controls are jobs
  17093387–404, runs `20261024-155125`, `-161834` and `20261024-211253` under
  `results/nova/e2_170933xx_pulled_20261025-144558/`.

**Registered verdict.**
- Source: `TP/analysis/agentload_analysis_r15/20261105-061431/` (`r15_verdict.json`, `r15_runs.csv`), from
  `analysis.r15_cells classify`.
- Every run is counted. Each is bound to its registration, paired with its control's plan (plan.csv byte-identical), and passes
  the manipulation check: 1620 / 1569 / 1763 tool calls lengthened, all starting in [1200.2, 2997.7] s.

| seed | job (node) | state | hit_eval | backlog slope (/s; threshold 0.012518) | outstanding at end | paired NOBURST control |
|---|---|---|---|---|---|---|
| 0 | 17256674 (nova22-gpu-2, bus 85:00.0) | **STUCK** | 0.000 (0 of 3690 turns) | 0.01919 | 174.4 | GOOD, hit 0.931 |
| 1 | 17256675 (nova22-gpu-3, bus C5:00.0) | **STUCK** | 0.000 (0 of 3357) | 0.01842 | 125.0 | GOOD, hit 0.930 |
| 2 | 17256676 (nova22-gpu-3, bus C6:00.0) | **STUCK** | 0.000 (0 of 3807) | 0.02319 | 132.9 | GOOD, hit 0.934 |

**Against the frozen predictions** (`notes/PREDICTIONS_r15.md`, section 4). All models called this cell the same way, so it does
not discriminate between them; the discriminating cell is T2 (A2, pending).

| predictor | frozen call | result |
|---|---|---|
| calibrated simulator, exact plans, `mixed` (PRIMARY) | S / S / S → TRAPS | correct, 3/3 per seed |
| simulator, `separate_prefill_priority` | S / S / S → TRAPS | correct, 3/3 |
| pred2 fluid verdict (n(3000) = 69.8 > n_u = 32.2) | TRAPS | correct, 3/3 |
| pred2 per-seed layer | P(STUCK) = 1.00 / 1.00 / 1.00; P(TRAPS) = 1.00 | log score 0; Brier 0 over the 3 runs |

**Exploratory measures against the simulator** (`results/theory/r15/toolslow_measured_r15_t1.json`, from
`analysis.r15_sim_toolslow measure`).

| measure | GPU s0 / s1 / s2 | simulator `mixed` (frozen) | pred2 plan walk (frozen) |
|---|---|---|---|
| t_fu150 (s); band for STUCK runs [1800, 3300) | 1950 / 1950 / 2100 | 1950 / 1950 / 2100 | — |
| sessions alive at 2100 s | 49 / 38 / 39 | 49 / 37 / 39 | 49 / 37 / 39 |
| sessions alive at 3000 s | 55 / 70 / 74 | 57 / 72 / 76 | 48 / 53 / 56 |
| outstanding, mean over [2100, 2400) | 11.3 / 11.8 / 12.7 | 11.3 / 12.3 / 14.4 | — |
| outstanding at 3300 s | 65 / 67 / 64 | 57 / 62 / 70 | — |
| backlog slope over W (/s) | 0.0192 / 0.0184 / 0.0232 | 0.0191 / 0.0183 / 0.0246 | — |

- The frozen reference accuracy (from the post-hoc r14 table) was: alive at 2100 s within 1, alive at 3000 s within 4, and
  outstanding at 3300 s within 5.
- T1 meets the first two. Outstanding at 3300 s misses by 8 on seed 0 and by 6 on seed 2.
- The pred2 plan walk, which has no queueing, undercounts sessions alive at 3000 s by 7 to 18.
- **Replication of r14 d30 up to 2100 s.** Alive at 2100 s (49 / 38 / 39) and t_fu150 (1950 / 1950 / 2100) equal the d30 GPU
  runs exactly.

**Dose-response in the slowdown's duration (same plans, rate, delay and start):**
- r14 d30, slowed over [1200, 2100): stuck in 1 of 3. Seeds 0 and 1 recovered once the slowdown ended.
- T1, slowed over [1200, 3000): stuck in 3 of 3.
- The simulator's d30 rows are post hoc (GGS). Its T1 rows were blind (SSS).

**Theory: trap-state law on a trap entered with no burst.** The frozen `icml-trap-pred` predictions are scored with
S1–S5. The output is `TP/analysis/icml_score_new_t1/score.json` and `score.md`, from cell `a100_300k` at 1.35×, trigger
1200 s and W = [5700, 8700).
- All three runs are eligible: the follow-up hit over W is 0, and the window starts 4500 s after the trigger.
- Predicted values:
  - P = 9324.1 prompt tokens
  - γ = 0.013034 (γ/z = 0.012866)
  - D = 0.080891 sessions/s
  - α = 0.015677 /s

| run | S1 composition, P meas / pred | S2 gap-median slope / γ | S3 completion rate (/s) / D | S4 backlog slope / α | S5 plug-in slope; side, close |
|---|---|---|---|---|---|
| s0 | 9236 / 9324 (−0.9%) | 0.0196 / 0.0130 (1.50) | 0.0850 / 0.0809 | 0.0192 / 0.0157 | 0.0228; yes, yes |
| s1 | 10062 / 9324 (+7.9%; per-run limit ±8%) | 0.0103 / 0.0130 (0.79) | 0.0787 / 0.0809 | 0.0184 / 0.0157 | 0.0101; **no** (plug-in below the 0.0125 threshold, measured above), yes |
| s2 | 9209 / 9324 (−1.2%) | 0.0122 / 0.0130 (0.94) | 0.0837 / 0.0809 | 0.0232 / 0.0157 | 0.0208; yes, yes |
| **pooled** | **+1.9%** (limit ±5%): **pass** | **1.075 γ** (limit [0.6, 1.4]): **pass** | **+1.9%** (±15%), every run > λ_ref = 0.0715: **pass** | **+29%** (±35%): **pass** | side 2/3, close 3/3 |

- Not refuted (the refutation rule is a pooled S1 or S2 failure).
- The unregistered γ/z comparison gives 1.089.
- The trapped runs process uncached tokens at 11,360 / 11,259 / 11,686 tok/s. That is the cell's all-miss rate: the
  node-to-node spread measured earlier is 11,347–11,573 tok/s.

**Reading for the paper.**
- A 30 s tool slowdown lasting 1800 s, with no arrival burst, trapped the engine in all three seeds at 1.35 λ_ref. The same
  arrival plans without the slowdown stayed good.
- The trapped state that results obeys the trap-state law frozen before the runs, whose tolerances came from burst-triggered
  traps.
- The cell does not distinguish the simulator from pred2, since both predicted TRAPS.

**Suggested text for the `\pending{TOOLSLOW-W outcome ...}` slot (v2_validation.tex)**:

> Outcome: TRAPS. All three runs were stuck (hit 0.000 over $[5700,8700)$\,s; backlog slopes 0.0192, 0.0184 and 0.0232\,/s
> against a threshold of 0.0125), while their paired NOBURST controls stayed good (hit 0.930--0.934). The 30\,s arm that ended
> at 2100\,s had trapped 1 of 3 on the same plans. All three runs are eligible for S1--S5, and the pooled scores pass:
> composition +1.9\% (limit $\pm5$\%), gap slope $1.08\gamma$, completion rate +1.9\% of $D$ with every run above $\lref$, and
> backlog slope +29\% of $\alpha$ (limit $\pm35$\%). Per run, composition is within $\pm8$\% in all three (seed~1 at +7.9\%).
> S5's plug-in lies on the measured side of the threshold in 2 of 3 runs and within 0.01\,/s in 3 of 3. Every
> model we froze predicted this cell's outcome, so it tests the trap-state law on a trap with no burst, not the models against
> each other.

## 2. REPLICATE-EDGE (exploratory): the 2.5× from-empty edge is fixed by the arrival path. Frozen verdict **REPRODUCIBLE**

**Cell.**
- Two MODE=cap jobs of three 3000 s runs at 2.5 λ_ref, label `sglang-fcfs-r1-edgerep`. The plans are those of seeds 0 and 4,
  unchanged.
- Originals: seed 0 collapsed at 1600 s (job 17084754, nova22-gpu-1); seed 4 stayed stable (job 17168507, nova22-gpu-3).
- The rule is `configs/r15_edge_replicate.yaml`, frozen with the predictions at `r15-reg`.

**Frozen verdict.**
- Source: `TP/analysis/agentload_analysis_r15_edge/20261105-061605/` (`r15_edge_verdict.json`, `r15_edge_runs.csv`).
- All six replicates are valid:
  - plan.csv byte-equal to the original's, with tool-time totals differing by 0.0 s;
  - engine verified, with no differing SGLang server args or banner parameters;
  - commit `e05a262`, not dirty, start state verified;
  - finished at 3000 s with 0 request errors.

| plan | original | replicates (job, GPU bus id, position, salt): label, τ | agree |
|---|---|---|---|
| seed 0 | UNSTABLE, τ 1600 s (nova22-gpu-1, 86:00.0) | 17256677 (45:00.0, pos 1, salt 1): UNSTABLE, 1600 s; 17256677 (45:00.0, pos 3, salt 3): UNSTABLE, 1600 s; 17256678 (46:00.0, pos 2, salt 2): UNSTABLE, 1800 s | 4/4 |
| seed 4 | STABLE (nova22-gpu-3, 06:00.0) | 17256677 (45:00.0, pos 2): STABLE; 17256678 (46:00.0, pos 1): STABLE; 17256678 (46:00.0, pos 3): STABLE | 4/4 |

- All six replicates ran on nova22-gpu-3, on two GPUs (bus 45 and 46). Seed 0's original ran on nova22-gpu-1.
- Seed 0's replicates ended with 141 / 145 / 123 requests queued (the original had 127) and completed 402 / 404 / 427 sessions.
  Seed 4's replicates completed 552 / 553 / 553 sessions (the original completed 553).
- The registered E0b stability rule gives the same label for all eight runs.

**Against the frozen predictions** (`notes/PREDICTIONS_r15_edge.md`):
- Every deterministic predictor called **REPRODUCIBLE** and was correct: the realized arrival count, the turn load, the token
  work, pred2's level crossing, and the calibrated simulator in both modes.
- The simulator's collapse-time band for seed 0 was 1500–1800 s. The replicates gave 1600, 1600 and 1800 s.
- The F2 escape law, read as independent draws per run, gave P(REPRODUCIBLE) = 0.0097 and P(PLAN-CONDITIONAL ESCAPE) = 0.990.
  The note froze the reading of this outcome: "F2 does not describe same-plan replicates", not a refutation of F2's cell-level
  escape probability. Under F2's own noise model the frozen disagreement probabilities are upper bounds, by Jensen's inequality.

**Reading for the paper.**
- Near the 2.5× edge, whether a from-empty run collapses was fixed by its arrival path in 8 of 8 runs.
- Two plans, each run four times (across two nodes for seed 0), gave identical labels, and seed 0's collapse time repeated
  within one 200 s step.
- The spread of outcomes across seeds at the edge therefore comes from plan-to-plan workload variation, not from service noise
  at a fixed workload. This is consistent with the deterministic fluid picture.
- This weakens any reading of F2's escape probability as noise-driven escape from a fixed workload.
- The sample is small: 2 plans, 6 new runs, mostly one node. MODE=cap has no registration branch.
- Possible place: the limitations paragraph of the conclusion ("The from-empty runs are single runs per rate") can now say that
  same-plan replicates at the 2.5× edge reproduced both originals in 3 of 3 each.

## 3. CUT (Corollary 3) — pending (jobs 17256867–72)

## 4. A2 / T2 TOOLSLOW d15 at 1.65× — pending (jobs 17256873–75)

## Verification

- Archive sha256 equal on both ends (`75090c94…`).
- **Independent recompute (T1 and EDGE): agrees everywhere.** A subagent wrote its own pandas/numpy code from the raw
  `requests.csv`, `sessions.csv`, `tool_calls.csv`, `plan.csv`, `meta.json` and job logs. It ran no project classifier, computed
  first, and only then compared with the official outputs. Every number matches them to the precision they print.
  - **T1 values:**
    - hit_eval is 0 in all three runs (0 of 3690 / 3357 / 3807 turns; the highest cached/prompt ratio of any turn in W is
      0.0005).
    - Backlog slopes 0.0191879 / 0.0184187 / 0.0231853 /s; threshold 0.0125185.
    - Controls GOOD at 0.931286 / 0.930036 / 0.934188.
  - **T1 manipulation:** the 1620 / 1569 / 1763 calls starting in [1200, 3000) all have add_s = 30, and no call outside has a
    nonzero add_s.
  - **T1 timing, plans and binding:**
    - Every slowed call's next request left at least 30.002 s after the call started. t_ready is exact.
    - The plans are byte-identical to the controls' (sha256 b99e7413…, e7162e95…, b22561f6…).
    - The registration's sha256 equals each run's `meta.prereg_sha256`, and the file was committed (`e05a262`, unix 1793870268)
      before the runs' t0 (1793870620 / 655 / 660).
  - **T1 exploratory measures and S1–S4 statistics:** identical. Gap-median slopes 0.0195513 / 0.0102881 / 0.0121922; pooled
    P 9502.05, D 0.0824444, slope 0.0202632.
  - **EDGE:**
    - Labels and τ are identical in all 8 runs (originals included). Plans are byte-identical to the originals. All 6
      replicates are valid on every condition in the yaml.
    - Verdict REPRODUCIBLE.
    - Detail: seed 0's τ is 1600 s on bus 45:00.0 (twice) and on the original's GPU, and 1800 s on bus 46:00.0.
    - After the onset, no window of an UNSTABLE run exceeded 0.142.
  - **Definition notes from the check (none changes a number or an outcome here):**
    - trap_v2 evaluates up to t_end, 8700.015–8700.020 s, rather than 8700. No turn completed after 8696.7 s.
    - `measured.window_stats` lets only completed sessions leave the backlog and samples once per second. The basin code also
      lets failed sessions leave and time-averages. The two slopes differ in the 4th digit; there are no failed sessions.
    - The EDGE code also exempts `meta.start_state_verified` from the config comparison, and has a RULE-ERROR outcome that the
      yaml does not define. Neither applies here.
  - Scripts and outputs: session scratchpad `tonight/recompute_t1_edge/` (not committed).
