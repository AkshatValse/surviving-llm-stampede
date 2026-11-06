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
> composition +1.9\% (limit $\pm5$\%), gap slope $1.075\gamma$, completion rate +1.9\% of $D$ with every run above $\lref$, and
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

## 3. CUT-A (Corollary 3, λ′ = 1.15 λ_ref): registered verdict **PASS** (theory-favoured 3/3, sign clause 2/3)

**Pull and sources.**
- Pull: `results/nova/r15_cut_a_1725686x_pulled_20261105-063800/` (abbreviated **CP**). It holds `COMMANDS.txt`, the sacct
  records and the archive sha256 `db4812fb…`, checked on both ends.
- Registered verdict: `CP/analysis/agentload_analysis_r15_cut/20261105-063936/` (`cut_verdict.json`, `cut_runs.csv`,
  `cut_n_grid.csv`), from `analysis.r15_cut classify` with `--theory-git icml-cut-pred:results/theory/icml/cut_predictions.json`.
  It reports CUT-B as PENDING because CUT-B had not finished.

**Timeline.**
- Theory predictions: tag `icml-cut-pred` (`2f90267`), pushed 02:25:43 CST.
- Rule: commit `11b0e4e`, tag `r15-cut-reg`, pushed 03:54:49 CST. Its RULE HISTORY sentence says the rule was fixed after the
  predictions and before any CUT job, and calls it "stricter than the draft" the theory session simulated (R1/R2 in
  `PREDICTIONS_icml_cut.md`). The skeptic's review found that wording only partly accurate. It differs from the draft in four
  ways, and the rule was finalised after the per-seed predictions had been read:
  - **stricter:** the quasi-static comparator is added, and an unstuck run counts against the theory;
  - **mixed:** the naive comparator uses the frozen D_trap instead of the run's own D_pre. That is stricter for seeds 0 and 1
    and looser for seed 2, the seed the theory note names as its weakest;
  - **looser:** the CUT-A sign clause moved from [3000, 8700) to [5700, 8700) on the theory session's advice. In its own
    Monte Carlo that raised P(PASS) from 0.82 to 0.99.
  - **Same verdict either way:** under the draft rule (R1 with the run's own D_pre, sign over [3000, 8700)) the verdict is
    also PASS, with 3/3 theory-favoured and the sign positive in 2/3.
  - Do not call the rule "stricter" in the paper.
- Jobs 17256867–69: submitted 03:57:14 CST from the frozen clone `repo_r15_cut` at `11b0e4e`; all three ran on nova22-gpu-1.
  The runs' t0 is 04:07:04–04:07:48 CST and every run's meta.json records commit `11b0e4e`.

**Validity.** All three runs are counted, finished at 8700 s and bound to the CUT-A registration (prereg sha256 `23997ce2…`).
They pass the manipulation check:
- sessions before 2400 s identical to the same-seed uncut 1.65× BURST control (tool times equal to 0.0 s);
- post-cut sessions exactly the registered thinned plan, with kept counts 539 / 513 / 540 of 775 / 767 / 788 candidates
  (z = −0.09 / −1.70 / −0.71 against keep probability 1.15/1.65);
- the 200 burst sessions in [1200, 1260) s;
- the ramp is the registered one.

All three are STUCK, with a follow-up hit of 0.000 over [5700, 8700) s.

| seed | measured S, [3000, 8700) (/s) | model F (frozen) | naive λ′_plan − D_trap | quasi-static λ′_plan − λ_ref | call | S over [5700, 8700) |
|---|---|---|---|---|---|---|
| 0 | **+0.00404** | +0.00392 (error 0.00012) | −0.00943 (error 0.0135) | +0.01461 (error 0.0106) | THEORY-FAVOURED | +0.00705 (> 0) |
| 1 | **−0.00217** | −0.00258 (error 0.00041) | −0.02036 (error 0.0182) | +0.00864 (error 0.0108) | THEORY-FAVOURED | −0.00274 (model F predicted < 0 for this plan) |
| 2 | **+0.00295** | +0.00284 (error 0.00010) | −0.00987 (error 0.0128) | +0.01320 (error 0.0103) | THEORY-FAVOURED | +0.01315 (> 0) |

- The arrival rate after the cut, λ′_plan over [3000, 8700), is 0.0861 / 0.0802 / 0.0847 sessions/s, i.e. 1.20 / 1.12 /
  1.18 λ_ref.
- The frozen trapped throughput of the uncut controls is D_trap = 0.0956 / 0.1005 / 0.0946 (1.34 / 1.41 / 1.32 λ_ref).
- In every seed, then, the cut put arrivals below the throughput measured in the trap. The trap still did not drain.
- **Rate in the cut runs:** they completed 0.0753 / 0.0847 / 0.0787 sessions/s over [5700, 8700) (1.05 / 1.18 / 1.10 λ_ref):
  below D_trap, and above the all-miss capacity λ_ref.
- **The theory's registered secondary predictions** (`notes/PREDICTIONS_icml_cut.md` item 4, not part of PASS; computed in
  `CP/analysis/icml_cut_secondary_cut_a.json` with `analysis/theory/icml/measured.py` at `fdb80c9`). All hold:
  - completion over [5700, 8700) within ±0.006 /s of the per-seed plug-in (0.07467 / 0.08567 / 0.07767): errors +0.0007 /
    −0.0010 / +0.0010;
  - served prompt within ±5% (9994 / 10136 / 9718): measured 10011 / 10132 / 9804 (+0.2% / −0.0% / +0.9%);
  - dip < 15% of the [2100, 2400) level on 300 s bins: 0.7% (lowest bin [2400, 2700)), 9.6% ([6600, 6900)) and 11.0%
    ([6300, 6600)), against model F's 3.0% / 9.4% / 8.5%;
  - last bin [8400, 8700) > 150: 225.7 / 161.9 / 194.9 (model F 231.2 / 165.8 / 203.6).
  - The classifier's own descriptive dip (10 s bins, against N at the cut) is deeper: 3.1% / 13.2% / 19.1%. Quote the
    registered 300 s definition, and say which one you use.
- **Backlog levels:** at [2100, 2400) the measured N is 176.1 / 175.0 / 172.4, against model F's 185.6 / 180.5 / 178.9.

**What the registered PASS does and does not show** (from the adversarial review; numbers recomputed by the lead,
`plan.csv` base arrivals and `cut_runs.csv`).
- **It rejects two constant-throughput stories.** Both comparators are constant-throughput endpoints:
  - the naive one: completions at the uncut trapped throughput D_trap;
  - the quasi-static one: completions at the all-miss capacity λ_ref.

  The rule calls THEORY for any prediction lying between them.
- **It does not reject intermediate stories.** A zero-drift story fits [3000, 8700) as well as model F: completions equal to
  the nominal cut rate 1.15 λ_ref, i.e. S = λ′_plan − 1.15 λ_ref = +0.00388 / −0.00209 / +0.00247. Its errors are 0.00016 /
  0.00008 / 0.00047, against model F's 0.00012 / 0.00041 / 0.00010. A midpoint story, C = (λ_ref + D_trap)/2, would clear the
  trap slowly, and it is still theory-favoured under the rule.
- **What separates model F from those stories.**
  1. **The late window, [5700, 8700) s.** Model F's frozen W2 slopes are in `cut_predictions.json` (`w5700.theory_slope`):
     +0.00691 / −0.00359 / +0.01289. Measured: +0.00705 / −0.00274 / +0.01315 (errors 0.00014 / 0.00085 / 0.00025). The
     alternatives miss by:
     - zero drift: 0.0040 / 0.0042 / 0.0057;
     - midpoint: 0.0053 / 0.0080 / 0.0066;
     - quasi-static: 0.0068 / 0.0065 / 0.0050;
     - naive: 0.017 / 0.022 / 0.018.

     The predictions were frozen, but this comparison was not registered as a test, so report it as post hoc.
  2. **The completion rate over [5700, 8700).** Registered as a secondary prediction, ±0.006 /s. Measured 1.053 / 1.184 /
     1.100 λ_ref against model F's 1.044 / 1.198 / 1.086: it varies with the plan as model F says.
     - No single constant rate comes within 0.004 /s of all three seeds. The best constant, 0.0800 /s (the midrange),
       misses by up to 0.0047 /s, which is inside the ±0.006 tolerance, so do not say "no constant fits". Zero drift
       misses by 0.0069 / 0.0024 / 0.0036 /s, the all-miss capacity by 0.0038 / 0.0131 / 0.0071, D_trap by
       0.020 / 0.016 / 0.016. Model F misses by at most 0.0010. (Corrected after the reframe session's check.)
     - In seeds 0 and 2, completions over W2 fell below arrivals: the backlog regrew, towards model F's asymptotic
       D′ = 1.06 λ_ref.
  3. **STUCK in all three runs to 8700 s.** This is registered. The follow-up hit is 0.000, and N never fell below 149.
- **Precision.**
  - Engine jitter between runs with identical plans (the pre-cut parts, [1300, 2400)) is 0.0001–0.0005 /s in slope.
    - Over [3000, 8700) the agreement (within 0.0004 /s) is at that noise floor. Quote it as "within the engine's
      run-to-run jitter", not to four decimals.
    - In the late window seed 1 misses by 0.00085 /s, above the jitter, so scope the jitter sentence to [3000, 8700).
  - The model's backlog level runs 5–10 sessions high, e.g. 186 against 176 at [2100, 2400) for seed 0.
  - On the six uncut controls the model's slope bias was −0.0007 ± 0.0002 /s. Here the residuals are +0.0001 to +0.0004.
- **"Below the throughput measured in the trap"** compares with D_trap, the uncut same-seed run's trapped throughput over
  [3000, 8700) (1.34 / 1.41 / 1.32 λ_ref). That is a counterfactual quantity, not something an operator could read off before
  cutting.
  - **What an operator would have seen before cutting:** the cut runs' own completion rate over [1800, 2400) (D_pre, in
    `cut_runs.csv`) was 0.1217 / 0.1183 / 0.0867 sessions/s = 1.70 / 1.65 / 1.21 λ_ref. That still includes the burst
    sessions' own completions.
    - The nominal cut rate 1.15 λ_ref is below it in all three seeds.
    - The realised rate over [3000, 8700) (1.20 / 1.12 / 1.18) is also below it in all three, narrowly for seed 2 (1.185 vs
      1.212).
    - Over [5700, 8700), seed 2's realised rate (1.254) is above its D_pre.
  - The realised post-cut arrival rate was 1.20 / 1.12 / 1.18 λ_ref over [3000, 8700) and 1.19 / 1.05 / 1.25 over
    [5700, 8700), not exactly 1.15. The plans are thinned Poisson streams.
  - Seed 1's backlog fell 11.5% (175 to 155), and trap_v2 labels it "draining". It stayed STUCK.
- **Code nit (no effect).** The skeptic found that when S_naive and S_qs are exactly equally close, `seed_call` returns
  NAIVE-FAVOURED where the rule text says TIE. That needs exact float equality, it errs against the theory, and the code
  stays frozen.

**Reading for the paper (narrowed).**
- After a burst trapped the engine at 1.65 λ_ref, cutting arrivals to about 1.15 λ_ref left all three runs trapped to the
  end of the run. That rate is below the uncut runs' trapped throughput (1.32–1.41 λ_ref) and above the all-miss capacity.
- The registered rule favoured model F over both constant-throughput readings in 3/3 seeds:
  - "the trap drains at the throughput it showed";
  - "completions fall to the all-miss capacity".
- Over the last 3000 s the backlog grew again in seeds 0 and 2, at the rates model F froze (within 0.0003 /s). Completions
  matched its per-seed values within 0.001 /s.
- This supports Corollary 3's claim that the measured trapped throughput overstates the recovery threshold. It does so
  through the persistence and the late-window regrowth, not through the registered PASS alone.
- **Limits.**
  - The cut comes 1200 s after the burst, so the test sees the young trap's transient and the start of the regrowth, not
    the asymptotic rate.
  - There are 3 seeds, all on one node.
  - "Did not clear" means within 8700 s.

**Suggested text (the PASS draft in v2_validation.tex, CUT-A half).**

> CUT-A passed its registered rule. All three runs stayed stuck to the end of the run after arrivals were cut to
> 1.15~$\lref$, below the trapped throughput of the same seeds' uncut runs (1.32--1.41~$\lref$). The backlog's slope over
> $[3000,8700)$\,s was $+0.0040$, $-0.0022$ and $+0.0029$\,/s, against model~F's frozen $+0.0039$, $-0.0026$ and $+0.0028$, the
> naive comparator's $-0.0094$, $-0.0204$ and $-0.0099$, and the quasi-static comparator's $+0.0146$, $+0.0086$ and $+0.0132$, so
> all three seeds were theory-favoured; the slope over $[5700,8700)$\,s was positive in seeds 0 and 2 and negative in seed~1,
> whose plan has few post-cut arrivals, as model~F predicted. Both comparators assume a constant throughput, and over
> $[3000,8700)$\,s a backlog that merely tracks arrivals above 1.15~$\lref$ fits as well as model~F, so the PASS alone does not
> single out the theorem. What does is the late window, scored after the fact against slopes frozen with the predictions: over
> $[5700,8700)$\,s the backlog's slope was $+0.0071$, $-0.0027$ and $+0.0131$\,/s against model~F's $+0.0069$, $-0.0036$ and
> $+0.0129$, while every constant-throughput reading missed by at least 0.004\,/s; and the completion rate there, a registered
> secondary prediction, varied with the plan as model~F said (1.05, 1.18 and 1.10~$\lref$ against 1.04, 1.20 and 1.09); no single
> constant rate comes within 0.004\,/s of all three seeds. Over $[3000,8700)$\,s the agreement is at the level of the engine's
> run-to-run jitter (0.0001--0.0005\,/s).

## 3b. CUT-B (λ′ = 0.85 λ_ref): registered verdict **PASS** (theory-favoured 3/3, S < 0 in 3/3)

**Pulls and verdict.**
- Seed 0: `results/nova/r15_cut_b0_17256870_pulled_20261105-065100/` (job 17256870, nova22-gpu-2; sha256 `bf273305…` both ends).
- Seeds 1–2: `results/nova/r15_cut_b12_1725687x_pulled_20261105-082300/` (abbreviated **BP**). Jobs 17256871 (nova22-gpu-2) and
  17256872 (nova22-gpu-3), all COMPLETED 0:0; sha256 `37d73004…` both ends.
- Final registered verdict over all six CUT runs: `BP/analysis/agentload_analysis_r15_cut/20261105-082543/` (CUT-A PASS as
  before; CUT-B PASS).
- Secondary and alternative comparisons: `BP/analysis/icml_cut_secondary_cut_b.json`.

**Validity.**
- All three runs are counted, bound to the CUT-B registration, finished at 8700 s, and STUCK (follow-up hit 0.000 over
  [5700, 8700) s).
- Manipulation check passes. Kept counts are 396 / 366 / 390 of 775 / 767 / 788 candidates (z = −0.23 / −2.10 / −1.14 at
  keep probability 0.85/1.65).

| seed | measured S, [3000, 8700) (/s) | model F (frozen) | naive λ′_plan − D_trap | call | S < 0 | N at end (model F) |
|---|---|---|---|---|---|---|
| 0 | **−0.00854** | −0.00953 (error 0.00099) | −0.03294 (error 0.0244) | THEORY-FAVOURED | yes | 139.8 (138.6) |
| 1 | **−0.01260** | −0.01310 (error 0.00050) | −0.04282 (error 0.0302) | THEORY-FAVOURED | yes | 77.0 (79.0) |
| 2 | **−0.01237** | −0.01233 (error 0.00004) | −0.03355 (error 0.0212) | THEORY-FAVOURED | yes | 89.0 (93.8) |

- **Arrivals:** λ′_plan over [3000, 8700) was 0.876 / 0.807 / 0.853 λ_ref.
- **Operator's pre-cut completion rate:** D_pre over [1800, 2400) was 1.68 / 1.65 / 1.23 λ_ref.

**What the registered PASS does and does not show.**
- **Persistence discriminates here, unlike in CUT-A.** Starting from the measured N over [3000, 3300) (172.5 / 146.4 /
  158.1):
  - the registered naive reading would have reached the hit-recovery onset n_b = 32.7 at 7245 / 5656 / 6739 s, inside the
    run;
  - the operator's D_pre drain would have reached it at 5437 / 4877 / 7598 s.
  - Yet all three runs stayed stuck, with N never below 125 / 76 / 82 and a follow-up hit of 0.000.
  - Model F's fluid empties the trap only at about 27,100 s, the busy period of Theorem 1(a).
- **The quasi-static reading fits the slopes about as well.** That reading is completions at the all-miss capacity λ_ref; it
  was not a registered CUT-B comparator. Its errors:

  | window | quasi-static | model F |
  |---|---|---|
  | [3000, 8700) | 0.00036 / 0.00121 / 0.00188 | 0.00099 / 0.00050 / 0.00004 |
  | [5700, 8700) | 0.00067 / 0.00819 / 0.00025 | 0.00126 / 0.00081 / 0.00128 |

  So the slopes do not single model F out against it.
- **Model F's distinctive prediction for CUT-B is completions below the all-miss capacity**, because the trapped mix ages
  once arrivals fall below λ_miss.
  - Measured over [5700, 8700): 0.918 / 0.932 / 0.974 λ_ref, against model F's 0.918 / 0.955 / 0.979 and the quasi-static
    1.000. The errors are 0.0000 / 0.0017 / 0.0003 /s against 0.0059 / 0.0049 / 0.0019.
  - This is post hoc. At the frozen tolerance of ±0.006 /s the quasi-static value is also (just) inside.
- **The theory's frozen secondary predictions for CUT-B all hold** (declared in `PREDICTIONS_icml_cut.md`, not part of the
  registered rule):
  - completion over [5700, 8700) within ±0.006 /s (errors above);
  - served prompt within ±5%: measured 11453 / 11331 / 10945 tokens against 11547 / 11300 / 10954 (−0.8 / +0.3 / −0.1%).
    That is far longer than the 8.4–8.8k of the uncut 1.65× runs: the cut ages the mix, as frozen;
  - the 300 s-median gap trend negative in all three: −0.0022 / −0.0096 / −0.0118, against −0.0034 / −0.0099 / −0.0112.
- **Zero drift, naive and operator readings** all miss the slopes by ≥ 0.0025 /s, and mostly by ≥ 0.01 /s (the JSON has
  every value).

**Reading for the paper.**
- Below the all-miss capacity the trap drained, but slowly: −0.009 to −0.013 sessions/s, at model F's frozen per-seed rates.
  It was still stuck at 8700 s, where the registered naive reading (drain at the uncut trapped throughput) and an operator's
  pre-cut reading would both have reached the hit-recovery onset by 4900–7600 s.
- Model F's specific prediction for this arm held: completions fell below the all-miss capacity (0.92–0.97 λ_ref) as the
  served prompts lengthened to 10.9–11.5k tokens. A quasi-static reading, completions at the all-miss capacity, fits the
  backlog slopes about as well.
- Together with CUT-A: on the engine, a cut below the trapped throughput but above the all-miss capacity did not clear the
  trap, and a cut below the all-miss capacity drained it only slowly. This is the pattern of Theorem 1(a) and Corollary 3.
  - Each arm's registered rule rejected the naive reading.
  - The evidence that singles model F out against intermediate readings is post hoc: CUT-A's late window, CUT-B's
    completions.
- **Limits.** 3 seeds per arm: CUT-A on one node (nova22-gpu-1), CUT-B on two (gpu-2 and gpu-3). "Drains slowly" is within
  8700 s; the busy period itself (about 27,100 s) is far beyond the run.

**Suggested text (the PASS draft in v2_validation.tex, CUT-B half)**:

> CUT-B passed its registered rule. After the cut to 0.85~$\lref$ the backlog drained, slowly, at $-0.0085$, $-0.0126$ and
> $-0.0124$\,/s over $[3000,8700)$\,s, against model~F's frozen $-0.0095$, $-0.0131$ and $-0.0123$ and the naive comparator's
> $-0.033$, $-0.043$ and $-0.034$, so all three seeds were theory-favoured and all three slopes were negative. All three runs
> were still stuck at 8700\,s (hit 0.000), where the naive reading would have reached the hit-recovery onset by 5700--7200\,s;
> model~F's fluid clears only at about 27{,}100\,s, the busy period of Theorem~\ref{thm:trap}(a). A reading in which the trap
> completes sessions at the all-miss capacity, not a registered comparator, fits these slopes about as well. Model~F's
> distinctive prediction for this arm, completions below that capacity as the trapped mix ages, held after the fact (0.92,
> 0.93 and 0.97~$\lref$ against 0.92, 0.96 and 0.98, with served prompts of 10.9--11.5k tokens against 8.4--8.8k uncut), as did
> its frozen secondary predictions (completion within 0.002\,/s, served prompt within 1\%, a negative gap trend in all seeds).

## 4. TOOLSLOW-D15 (cell T2): 1.65 λ_ref, +15 s on tool calls starting in [1200, 2100) s. Registered outcome **NO-TRAP** (stuck 1, good 2)

**Pulls.**
- Seed 0: `results/nova/r15_a2_s0_17256873_pulled_20261105-082300/` (job 17256873; sha256 `5210d8ad…` both ends).
- Seeds 1–2: `results/nova/r15_a2_s12_1725687x_pulled_20261105-083500/` (abbreviated **AP**; jobs 17256874–75; sha256
  `2b98a658…` both ends).
- All three ran on nova22-gpu-3 from the frozen clone `repo_r15_tonight` at `e05a262` (tag `r15-reg`). All COMPLETED 0:0.

**Registered verdict.** `AP/analysis/agentload_analysis_r15/20261105-083614/` (`analysis.r15_cells classify` over the six T1
and T2 runs: T1 TRAPS, T2 NO-TRAP). Every run is counted, bound to its registration, paired byte-identically with its NOBURST
control, and passes the manipulation check: 1144 / 1039 / 1064 calls slowed, all starting in [1200.2, 2099.5] s.

| seed | state | hit_eval | backlog slope (/s; threshold 0.02325) | outstanding at end | paired NOBURST control |
|---|---|---|---|---|---|
| 0 | **STUCK** | 0.000 | 0.02577 | 233.5 | GOOD, hit 0.934 |
| 1 | **GOOD** (RECOVERED and hit/slope) | 0.934 | 0.00109 | 1.9 | GOOD, hit 0.934 |
| 2 | **GOOD** (RECOVERED and hit/slope) | 0.924 | 0.00009 | 2.2 | GOOD, hit 0.921 |

**Against the frozen predictions** (`notes/PREDICTIONS_r15.md` section 4; scoring in `AP/analysis/r15_t1_t2_scoring.json`).
This is the cell that discriminates between the models.

| predictor | frozen call | result |
|---|---|---|
| calibrated simulator, exact plans, `mixed` (PRIMARY) | S / G / G → NO-TRAP | **correct**, 3/3 per seed |
| simulator, `separate_prefill_priority` | S / G / G → NO-TRAP | correct, 3/3 |
| pred2 fluid verdict (n(2100) = 51.1 > n_u = 31.8) | TRAPS (S / S / S) | **wrong**: 1/3 per seed; seeds 1 and 2 recovered |
| pred2 per-seed layer | modal S / G / G; P(TRAPS) / P(NO-TRAP) / P(MIXED) = 0.58 / 0.41 / 0.01 | modal 3/3; log score of the outcome ln 0.409 = −0.894; per-seed log-likelihood −0.868 (STUCK) and −0.892 (GOOD) (T1 adds 0); Brier over the declared six T1 + T2 runs 0.044 (STUCK) and 0.045 (GOOD), T2 alone 0.087 and 0.091 |

- Over the six T1 and T2 runs, per-seed agreement was: simulator 6/6 (both modes), pred2's per-seed modal call 6/6, pred2's
  fluid verdict 4/6.
- **Exploratory measures** (`results/theory/r15/toolslow_measured_r15_t2.json`), GPU against the simulator (`mixed`):

  | measure | GPU | simulator | pred2 walk |
  |---|---|---|---|
  | t_fu150 | 1950 / none / none | 2100 / none / none | — |
  | alive at 2100 s | 40 / 34 / 28 | 39 / 30 / 29 | 38 / 30 / 28 |
  | alive at 3000 s | 63 / 11 / 8 | 67 / 11 / 8 | 12 / 11 / 8 |
  | outstanding, mean [2100, 2400) | 36.9 / 6.2 / 5.6 | 36.7 / 4.0 / 5.7 | — |
  | outstanding at 3300 s | 82 / 0 / 2 | 75 / 0 / 2 | — |

  - Against the reference accuracy, these misses are reported: alive at 2100 s for seed 1 (+4, reference within 1); seed
    0's outstanding at 3300 s (+7, reference within 5); and seed 0's t_fu150, one 150 s bin early.
  - pred2's queue-free plan walk misses seed 0's alive-at-3000 s by 51.
- **Trap-state law on the stuck seed** (`AP/analysis/icml_score_new_t2/score.json`; `icml-trap-pred` at 1.65×, trigger
  1200 s; one eligible run, so the refutation rule, which needs a group of ≥ 2, cannot apply):
  - S1 composition 8612 / 8606 (+0.1%);
  - S2 gap-median slope 0.0235 / γ 0.0230 (1.02);
  - S3 completion 0.0967 / D 0.0879 (+10%; limit ±15%; above λ_ref);
  - S4 backlog slope 0.0258 / α 0.0302 (−15%; limit ±35%);
  - S5: side correct; close **no** (|slope − plug-in 0.0361| = 0.0104 > 0.01).
- Across the four runs trapped by a tool slowdown alone (T1 3, T2 1), S1–S4 pass in every cell group, and S5 is close in 3 of
  4 and on the correct side in 3 of 4.

**Reading for the paper.**
- At 1.65 λ_ref, a 15 s tool slowdown for 900 s, with no burst, trapped the engine on one arrival plan out of three. The other
  two recovered fully, to their no-slowdown controls' hit rates.
- The calibrated simulator had predicted exactly this, seed by seed, from the exact plans. pred2's plan-averaged fluid
  verdict had predicted a trap on every seed. Its per-seed layer, which starts each plan at its own sessions alive when the
  slowdown ends, called the right side for every seed, though seed 1 was a near coin flip (P(GOOD) = 0.53).
- This cell was registered to discriminate between the two frozen predictors, and the exact-plan simulator won. Do not call
  it the first such cell unless that is checked.
- The trapped run again obeys the trap-state law's pooled checks; its per-seed slope plug-in misses by 0.0004 /s beyond the
  tolerance.
- **Limits.**
  - The design is not blind: the cells were chosen after r14's d30 result and after reading simulator outputs.
  - 3 seeds on one node.
  - The per-seed probabilities were not sharp: P(NO-TRAP) was 0.41.

**Suggested text (a new §3 bullet, or the TOOLSLOW-D15 \pending)**:

> \emph{TOOLSLOW-D15} (pre-registered with TOOLSLOW-W, tag \texttt{r15-reg}): no burst; every tool call that starts in
> $[1200,2100)$\,s takes 15\,s longer, at 1.65~$\lref$, seeds 0--2, paired with the committed NOBURST runs. It was chosen so that
> our two frozen predictors disagree: the calibrated simulator, run on the exact client plans, called seed~0 stuck and seeds
> 1 and 2 good (NO-TRAP), while the plan-averaged fluid model called every seed stuck (TRAPS). Outcome: NO-TRAP, as the
> simulator said, seed by seed. Seed~0 was stuck (hit 0.000), and seeds 1 and 2 recovered to their controls' hit rates (0.934 and
> 0.924). The stuck run passed S1--S4 (composition +0.1\%, gap slope $1.02\gamma$, completion +10\% of $D$, backlog slope $-15$\% of
> $\alpha$); its S5 plug-in missed the 0.01\,/s tolerance by 0.0004\,/s.

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
- **CUT-A: blind recompute plus an adversarial review (two agents in parallel, own code, neither ran the classifier).**
  - **Recompute: full agreement.**
    - S over both windows matches to ≤ 1.3e-17.
    - D_trap recomputed from the three uncut controls equals the frozen constants to 2e-17.
    - λ′_plan equals the theory file's `lam_plan`, and each plan.csv equals the theory session's own frozen plan
      (`cut_plans/CUT-A_seed{0,1,2}.csv`).
    - Manipulation, binding, STUCK, calls, verdict and every registered secondary prediction match.
    - The registration predates each run by 756–800 s. The theory commit `2f90267` predates the registration.
    - No failed checks.
  - **Skeptic.**
    - Numbers and timeline: NONE-FOUND. The 65 tests of `tests/test_r15_cut.py` pass.
    - Rule application: NONE-FOUND, apart from the exact-tie code nit above.
    - Robustness: NONE-FOUND. The calls survive 1 s sampling, other bin widths, trimmed windows, in-flight requests instead
      of sessions, and D_trap over [5700, 8700). The margins to a changed call are ≥ 0.005 /s, at least 10× the engine
      jitter.
    - MINOR: the rule-history wording ("stricter"); "below the throughput measured in the trap" is loose; the naive
      comparator is a weak foil; "did not clear" holds only to 8700 s; the noise model does not fit these residuals.
    - SERIOUS, for the interpretation only: the registered PASS cannot separate Corollary 3 from zero-drift or
      slow-clearing stories.
    - All of this is folded into section 3 above.
  - Scripts and outputs: session scratchpad `tonight/verify_cut_a_recompute/` and `tonight/verify_cut_a_skeptic/` (not
    committed).
- **CUT-B and TOOLSLOW-D15: blind recompute (one agent, own code, ran no classifier): full agreement.**
  - 289 field-by-field comparisons with the official outputs, 0 disagreements; the largest relative difference is 1.45e-13.
  - Recomputed:
    - CUT-B: S over both windows, λ′_plan, the frozen D_trap (to 3e-17), comparators, STUCK, calls, the manipulation check
      (pre-cut sessions bit-exact; post-cut arrivals a subset of the control's candidates; kept-count z), the binding, and
      the secondary measures;
    - T2: hit_eval, slopes, STUCK/GOOD, the manipulation check (every in-window call add_s = 15 exactly, none outside),
      plans byte-identical to the controls, the binding, the exploratory measures and the scoring.
  - **Declared scoring, corrected.** `PREDICTIONS_r15.md` §4 declares Brier "over the 6 STUCK outcomes and over the 6 GOOD
    outcomes", i.e. T1 and T2 together. Those six-run means are 0.0436 (STUCK) and 0.0453 (GOOD). The 0.087 / 0.091 reported
    first are T2's three runs alone. The log-likelihood sums are unchanged, since T1 contributes 0.
  - **Counterfactual worth one clause in the paper.** Had the quasi-static comparator also been part of CUT-B's rule, seed 0
    would have been QS-FAVOURED (|S − S_qs| = 0.00036 < |S − S_theory| = 0.00099). The verdict would still be PASS (2 of 3).
  - **Naming caution.** In `cut_runs.csv` the column `naive_slope_3000_8700` is the D_pre-based comparator, reported only.
    The registered naive comparator is `naive_slope` in `cut_verdict.json`, and every number in this note uses the
    registered one.
  - **Cosmetic, no effect on any number.** The analysis-side `meta.json` of the PC classifier runs records hardware
    "Apple M3 Max CPU (simulation)", a default of the analysis metadata, although the analyses ran on Akshat-PC. It also
    records dirty = true, from the uncommitted notes and pulled results at the time; `analysis/`, `configs/` and `src/` were
    clean.
  - **Borderline exploratory value.** For T2 seed 2, the follow-up hit over [1800, 1950) s was 100/197 = 0.508, just above 0.5,
    so its t_fu150 "none" is two hits from 1800.
  - Scripts and outputs: session scratchpad `tonight/recompute_cutb_t2/` (not committed).
