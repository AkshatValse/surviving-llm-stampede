# Paper input: B1 (finite basin of the good state) and E0F (fresh-seed from-empty replication)

Written 2026-10-31 for the lead. Every number below comes from committed files on branch `r11/strengthen`. The pull is `results/nova/b1_e0f_1716850x_pulled_20261031-040517/` (abbreviated **BP**). Commands, the archive hash and the run-dir list are in `BP/COMMANDS.txt`. Full narrative: `notes/LOG.md`, entry 2026-10-31 "B1 basin test PASS".

## Verdicts

**B1: PASS (basin shown on the engine), decided by the registered rule.** All three seeds agree.
- With a burst of 100 sessions, the server is STUCK (hit 0.000 over [5700, 8700) s) in 3/3 seeds. The co-primary trap_v2 label is TRAPPED in 3/3.
- With a burst of 25 sessions, it is GOOD (trap_v2 RECOVERED, hit 0.92-0.93) in 3/3 seeds.
- None of the pre-stated alternative outcomes occurred: "stuck, slope-indeterminate", "critical size refuted" and "even 25 traps" are all absent.
- The registrations are `configs/agentload_prereg_2026-10-30_b100.yaml` and `_b25.yaml`, both FILLED. They sit at tag `r11-basin-reg` (`9b67c26`). GitHub records the push at 01:04:30Z, which is 20:04:30 CDT Fri 2026-10-30. The jobs were submitted at 21:12:45 CDT. `registration_diff` against the 2026-10-24 parent has an empty `forbidden` list. Every run is bound to its registration (`prereg_bound` True, no blockers).

**E0F: NOT replicated (exploratory).** Under the registered E0b rule:
- 2.0 × is stable in 3/3 fresh seeds;
- 2.5 × is also stable in 3/3, where the replication rule needed it unstable in ≥ 2/3.

The frozen rule's fallback therefore applies: restate the from-empty bracket in realized arrival rates over all runs, seed 0 included. Over 12 runs, every run with a realized base rate ≤ 2.665 × λ_ref is stable, and every run at ≥ 2.726 × is unstable. Ordered by realized rate, the stability calls are monotone.

## Sources

| key | path | what |
|---|---|---|
| BV | `BP/analysis/agentload_analysis_basin/20261031-040758/` (`basin_runs.csv`, `basin_verdict.json`, `meta.json`) | registered B1 classification + decision, `analysis.basin classify` at `19c58e9` |
| BJ | `BP/results/agentload_analysis_burst2/2026103*-*/trap_v2_runs.csv` | the jobs' own in-job trap_v2 analyses (agree with BV run by run) |
| BL | `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/` (runs `20261024-155120`, `-160218`, `-184132`, `-184259`, `20261025-000043`, `-000053`) | committed n = 0 / n = 200 runs at 1.65 ×, seeds 0-2 (jobs 17093387-404), found by `classify` itself |
| ES | `BP/analysis/agentload_analysis_stable/20261031-040957/` (`stable_runs.csv`, `lambda_cap_bracket.json`) | E0F six-run stability, `analysis.summarize stable` |
| EJ | `BP/results/agentload_analysis_stable/20261031-035407`, `-040058` | the two E0F jobs' own per-job brackets (agree with ES) |
| ER | `BP/analysis/derived/e0f_realized_rates.csv` | realized base rates of the 6 E0F runs + 6 committed seed-0 E0b runs (`analysis/r11_b1_e0f_derived.py`) |
| E0 | `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/stable_runs.csv` | committed E0b seed 0 (jobs 17084750-55) |
| TC | `BP/analysis/derived/b1_time_course_descriptive.csv` | descriptive B1 time course (100 s windows) |
| SQ | `BP/sacct_17168500-17168507.txt` | sacct records |
| S1 | `notes/PREDICTIONS_r11_basin.md`, `results/r11_predict_basin/20261030-194539/` (`basin_runs.csv`, `e0b_runs.csv`, `headline.json`) at `c600fd7`, pushed 20:04:30 CDT Fri | blind simulator bundle 1 |
| TH | `notes/PREDICTIONS_r13_theory.md`, `configs/r13_theory_predict.yaml`, `results/theory/merged/b1_basin_300k.json` at tag `r13-theory-pred` (`997d2c4`, pushed 07:05:30Z = 02:05:30 CDT Sat) | frozen first-principles theory |
| EP | `configs/r11_basin_predict.yaml` (frozen at `r11-basin-reg`) | frozen endpoints and decision rules |

Setup:
- **Cell:** SGLang FCFS, 300k-token pool, Qwen2.5-7B-Instruct, "NVIDIA A100 80GB PCIe, 81920 MiB" (nodes nova22-gpu-1/2/3).
- **B1 arm:** one BURST arm per job at 1.65 × λ_ref (λ = 0.118031 sessions/s). The burst is 60 s wide at t = 1200 s; runs last 8700 s.
- **E0F:** from empty, 3000 s per run, label `sglang-fcfs-r1-e0bfresh`.
- **Provenance:** all 8 jobs ran from clone `repo_r11_basin` at `9b67c26` and finished COMPLETED 0:0. Every run has `start_state_verified` True, and every canary passed (rc 0).
- **Pairing:** B1 runs pair by seed with the committed n = 0 / 200 runs (common random numbers). The base sessions are identical, and the burst start times are the first n of the n = 200 draw.

## Numbers

**B1, per run** (BV; W = [5700, 8700) s; slope threshold 0.023249 sessions/s)

| n | seed | job | run | state | trap_v2 | hit_eval | backlog slope /s | uncached-token rel. dev. | outstanding end |
|---|---|---|---|---|---|---|---|---|---|
| 0 (BL) | 0 / 1 / 2 | 17093387-404 | `-160218` `-184259` `-000053` | GOOD ×3 | recovered ×3 | 0.934 / 0.934 / 0.921 | -0.0005 / 0.0011 / 0.0001 | -0.89 / -0.90 / -0.87 | 3.2 / 1.9 / 2.2 |
| **25** | 0 | 17168503 | `20261030-235523` | **GOOD** | recovered | 0.933 | -0.0005 | -0.892 | 3.2 |
| **25** | 1 | 17168504 | `20261031-001011` | **GOOD** | recovered | 0.934 | 0.0011 | -0.899 | 1.9 |
| **25** | 2 | 17168505 | `20261031-002140` | **GOOD** | recovered | 0.923 | 0.0001 | -0.878 | 2.2 |
| **100** | 0 | 17168500 | `20261030-220255` | **STUCK** | **trapped** | 0.000 | 0.0318 | +0.026 | 306 |
| **100** | 1 | 17168501 | `20261030-220426` | **STUCK** | **trapped** | 0.000 | 0.0344 | +0.013 | 269 |
| **100** | 2 | 17168502 | `20261030-232552` | **STUCK** | **trapped** | 0.000 | 0.0361 | +0.037 | 273 |
| 200 (BL) | 0 / 1 / 2 | 17093387-404 | `-155120` `-184132` `-000043` | STUCK ×3 | trapped ×3 | 0.000 ×3 | 0.0320 / 0.0277 / 0.0362 | +0.025 / +0.029 / +0.026 | 363 / 313 / 352 |

Decision (BV `decision`): n100 STUCK 3/3, TRAPPED 3/3; n25 GOOD 3/3, STUCK 0/3. `basin_pass` = true, notes empty, no endpoint problems, no window mismatches.

**Dose-response so far (per-seed STUCK counts, 1.65 ×):** n = 0: 0/3; n = 25: 0/3; n = 100: 3/3; n = 200: 3/3. In each seed the CRN chain is good, good, stuck, stuck, so each seed puts the edge between 25 and 100.

**Descriptive time course (TC; not registered):**
- **n = 100:** hit < 0.2 in every 100 s window from the 1300 s window on, in all three seeds. The server tips within 100 s of the burst's start.
- **n = 25:** the lowest 100 s window hit between 1200 and 5700 s is 0.88 / 0.87 / 0.83 (at 1200 / 5400 / 2100 s), back above 0.8 in the next window. The burst of 25 leaves no visible dent: hit_eval is within 0.002 of the n = 0 run of the same seed.

**E0F, per run** (ES, ER; λ_ref 0.0715340)

| mult | seed | job | run | stable | final queue | trend rise | realized base mult |
|---|---|---|---|---|---|---|---|
| 2.0 | 3 | 17168506 | `20261031-011458` | yes | 0 | 0.000 | 2.013 |
| 2.0 | 4 | 17168506 | `20261031-020801` | yes | 0 | 0.000 | 2.148 |
| 2.0 | 5 | 17168506 | `20261031-030104` | yes | 0 | 0.000 | 1.971 |
| 2.5 | 3 | 17168507 | `20261031-012149` | yes | 0 | -0.005 | 2.512 |
| 2.5 | 4 | 17168507 | `20261031-021452` | yes | 0 | 0.000 | 2.665 |
| 2.5 | 5 | 17168507 | `20261031-030755` | yes | 0 | 0.000 | 2.470 |

- **Replication rule** (EP `e0f.decision_rule`): 2.0 × stable in 3/3 holds, but 2.5 × unstable in ≥ 2/3 fails (0/3). The result is NOT replicated.
- **Bracket over the six fresh runs alone** (ES): largest all-stable 2.5 ×, no unstable multiple, no guard warnings.
- **Pooled with seed 0 (E0):** 2.0 × is 4/4 stable; 2.5 × is 3/4 stable (seed 0 is unstable, realized 2.726 ×). By the registered all-seeds-stable bracket rule, the nominal bracket stays (2.0, 2.5).
- **In realized rates over all 12 runs** (seeds 0, 3, 4, 5; ER):
  - stable at 1.41, 1.67, 1.94, 1.97, 2.01, 2.15, 2.20, 2.47, 2.51 and 2.67 ×;
  - unstable at 2.73 × (final queue 127, rise +146) and 3.25 × (288.6, +196);
  - realized-rate edge between 2.665 × and 2.726 ×, monotone.

## Against the predictions

**Simulator bundle 1 (S1), blind:**

| item | predicted | engine | |
|---|---|---|---|
| B1 verdict | PASS | PASS | hit |
| n100 per seed | STUCK + TRAPPED ×3 | STUCK + TRAPPED ×3 | 3/3 hit |
| n25 per seed | GOOD (RECOVERED) ×3 | GOOD (RECOVERED) ×3 | 3/3 hit |
| hit_eval band ±0.1 | n25 0.934 / 0.934 / 0.928; n100 0.000 ×3 | 0.933 / 0.934 / 0.923; 0.000 ×3 | all within 0.006 |
| n100 slope (descriptive) | 0.031-0.036 /s (per seed 0.0314 / 0.0349 / 0.0360, mixed) | 0.0318 / 0.0344 / 0.0361 | within 0.0005 per seed |
| n100 token ratio (descriptive) | 1.03-1.05 | 1.026 / 1.013 / 1.037 | seeds 0 and 1 slightly below the band |
| n100 trap onset (descriptive) | 1300-1400 s window | 1300 s window | consistent |
| E0F 2.0 × | stable ×3 | stable ×3 | 3/3 hit |
| E0F 2.5 × | stable ×3 (fragile: 11-12/20 extra seeds stable) | stable ×3 | 3/3 hit |
| E0F verdict | NOT replicated | NOT replicated | hit |
| realized mults | 2.01 / 2.15 / 1.97; 2.51 / 2.67 / 2.47 | identical | plan reproduction confirmed |

All 12 per-run state calls and both verdicts match. The simulator's 30-extra-seed rates were n25 STUCK 2/30 and n100 STUCK 30/30. The three-seed engine counts are compatible with both: the 95% Clopper-Pearson interval is [0, 0.71] for 0/3 and [0.29, 1] for 3/3.

**Theory (TH, `r13-theory-pred`):**
- **B1 (frozen):** P(STUCK) per seed 1.000 at n = 100 and 0.042 at n = 25; P(PASS) = 0.995. The engine shows PASS, with 3/3 stuck at 100 and 0/3 at 25. The probability of exactly this outcome under the theory is 1.000 × 0.958³ = 0.879. Per the frozen scoring (`notes/THEORY_r13_scoring.md`), FAIL would have refuted; PASS is shared with the round-7 simulator. The theory-specific content is N_crit = 53.4 (deterministic) and a 50% committor at n ≈ 50 at 1.65 ×, and B1's two sizes do not test it. The engine says only 25 < edge ≤ 100 per seed.
- **Committor curve against the engine** (TH `results/theory/merged/b1_basin_300k.json`, p_trapped):

  | n | 0 | 10 | 25 | 40 | 50 | 60 | 75 | 100 | 150 | 200 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | theory p_trapped | not stated | 0.033 | 0.042 | 0.139 | 0.547 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
  | engine STUCK | 0/3 | n/a | **0/3** | (B2) | (B2) | (B2) | n/a | **3/3** | n/a | 3/3 |

  Everything above 60 is 1.0 in the theory, and n = 200 is a retrodiction because its outcome was known. The B2 cells (n = 40, 50, 60; registered at `r14-basin2-reg`) test the theory's specific claim. They are not part of this note.
- **The theory's "stuck by" time** (6,344 s, a model bound) is far later than the engine's: the engine is stuck from about 1,300 s.
- **E0F: no frozen prediction.** `r13-theory-pred` makes no E0F prediction; the coordination file assigns E0F to a second set, `r13-theory-pred2`.
  - As of 04:13 CDT Sat, `git ls-remote origin` shows neither a `r13-theory-pred2` tag nor a `r13/pred2` branch. Any pred2 E0F prediction pushed after this time is **not blind**: this session read the E0F results from 04:07 CDT, and this branch publishes them.
  - **What the frozen JSON implies (not a declared E0F prediction):** the a100_300k cell's F2 from-empty escape probability over 3000 s at the nominal multiples (TH `from_empty_edge.p_escape_registered`) is 0.150 at 2.0 × and 0.691 at 2.5 ×, with edge 2.34 ×.
    - Implied probabilities: P(2.0 × stable 3/3) = 0.614; P(2.5 × stable 3/3) = 0.030; P(replicated) = 0.47.
    - The engine's 0/3 unstable at 2.5 × therefore sits in the lower tail of F2.
    - The secondary level-crossing criterion in the same JSON (p_unstable 0.0325 / 0.3675) gives P(2.5 × stable 3/3) = 0.25.
    - This cell's E0b seed 0 (2.0 stable, 2.5 unstable) was known to the theory authors and was a validation target, so none of this is blind for seed 0.

## Blindness

Push times come from `gh api repos/AkshatValse/Nova-Research/activity`. Bundle 1 at `c600fd7` went out in the push `4d2bba2..9b67c26` at 01:04:30Z (20:04:30 CDT Fri). The theory tag `r13-theory-pred` went out with the `r13/theory` branch creation at 07:05:30Z (02:05:30 CDT Sat). Run ends are from each run's `meta.json` `end_time`; job ends are from sacct (SQ). All times are CDT.

| job | run | sacct End | run end | vs bundle 1 (20:04:30 Fri) | vs theory (02:05:30 Sat) |
|---|---|---|---|---|---|
| 17168500 b100 s0 | `20261030-220255` | 00:31:05 | 00:27:56 | blind in time | **blind only by access** (ended before the push) |
| 17168501 b100 s1 | `20261030-220426` | 00:32:36 | 00:29:27 | blind in time | **blind only by access** |
| 17168502 b100 s2 | `20261030-232552` | 01:54:02 | 01:50:54 | blind in time | **blind only by access** |
| 17168503 b25 s0 | `20261030-235523` | 02:23:33 | 02:20:24 | blind in time | blind in time |
| 17168504 b25 s1 | `20261031-001011` | 02:38:20 | 02:35:12 | blind in time | blind in time |
| 17168505 b25 s2 | `20261031-002140` | 02:49:50 | 02:46:42 | blind in time | blind in time |
| 17168506 2.0× s3 | `20261031-011458` | 03:54:12 (job) | 02:04:59 | blind in time | no frozen E0F prediction; run ended 31 s before the push |
| 17168506 2.0× s4, s5 | `-020801`, `-030104` | 03:54:12 (job) | 02:58:02, 03:51:05 | blind in time | no frozen E0F prediction (after the push) |
| 17168507 2.5× s3, s4, s5 | `-012149`, `-021452`, `-030755` | 04:01:04 (job) | 02:11:51, 03:04:53, 03:57:56 | blind in time | no frozen E0F prediction (after the push) |

- **Bundle 1:** the jobs were submitted at 21:12:45, more than an hour after the push, so every prediction is blind in time. The bundle's own scope note says the lead knew the n = 0 / 200 and seed-0 E0b outcomes, which shaped the hypothesis; only the new burst sizes and seeds are blind inputs.
- **Theory, n = 100 seeds 0-2:** these runs ended 0.2-1.6 h before the theory push. They are **blind by access only**.
  - The lead and every agent were told not to read B1/E0F results before the freeze.
  - The theory note records that no one in its workflow connected to Nova or opened any `results/nova` dir naming b100/b25/e0bfresh.
  - No commit on any GitHub branch before 02:05:30 references these runs. One string match in `cacf833` is a different clone's analysis dir with the same timestamp.
  - What cannot be shown: no file-access record exists, because `/work/classtmp` is mounted `noatime` and atime evidence is therefore unavailable. We cannot prove that no session read the in-job `.out` summaries (written 00:31-01:54) before 02:05:30.
  - The first read of any outcome recorded here is this session's, at about 04:07 CDT Sat.
  - Suggested wording: "n = 100 predictions blind by access (no reader before the push is known), n = 25 blind in time."

## Caveats

- Three seeds per cell; one run per (n, seed). The registered rule is per seed with no pooled intervals. 0/3 and 3/3 are compatible with true rates up to 0.71 and down to 0.29.
- The edge is located only to (25, 100]. B1 does not test the theory's N_crit ≈ 50-53; B2 (n = 40, 50, 60) does.
- `analysis.basin classify` ran at `19c58e9`, which adds the B2 rule after the tag. Re-running `analysis/basin.py` exactly as tagged (`9b67c26`) on the same runs gives an identical decision and identical per-run numbers.
- **E0F is exploratory** (no registration).
  - The frozen endpoint file says realized rates come "from analysis/seed_effects.py". That module does not exist in the repository, so `analysis/r11_b1_e0f_derived.py` computes the same quantity as the simulator driver: n_base / duration / λ_ref. This is a stated substitution.
  - The realized-rate bracket is descriptive. It conditions on the arrival count only; turn counts and tool times also vary by seed.
- **The 2.0/2.5 × E0b bracket that fixed the registered window (hi = 2.0) is not changed by E0F.** The registration and its window stand as frozen. With seeds 3-5, 2.5 × is stable in 3 of 4 seeds, so the edge in nominal multiples is seed-dependent near 2.5 ×.
- The n = 25 burst is effectively invisible: hit_eval is within 0.002 of n = 0 per seed. "GOOD" at 25 is therefore far from marginal. The theory's p_trapped 0.042 at 25 and the simulator's 2/30 both say the same.

## Suggested text

**Paragraph.** *Finite basin (registered).* At 1.65 × λ_ref, inside the metastable window, we ran a burst-size test with two sizes, registered before any run (tag `r11-basin-reg`, pushed 20:04 CDT, jobs submitted 21:12). A burst of 25 extra sessions left the server in the good state in all three seeds (hit 0.92-0.93 over the last 3000 s, indistinguishable from no burst). A burst of 100 trapped it in all three (hit 0.000; uncached prefill within 4% of the all-miss rate; backlog growing 0.032-0.036 sessions/s). The registered rule (100 stuck and 25 good in at least 2 of 3 seeds) passes, so the good state has a finite basin on the real engine: it absorbs small perturbations and tips only past a critical size between 25 and 100 sessions. The calibrated simulator's blind predictions matched every per-run call, to within 0.006 in hit and 0.0005 sessions/s in backlog slope. A separate first-principles model, frozen later, put P(pass) at 0.995 and the critical size near 50-53. For n = 100 that prediction is blind only by access, since those runs had ended before it was frozen.

**Table row.** `B1 basin | SGLang FCFS 300k, A100 | 1.65× | n=25: GOOD 3/3 (hit 0.923-0.934); n=100: STUCK 3/3, TRAPPED 3/3 (hit 0.000) | registered (r11-basin-reg) | PASS | sim S1: 12/12 calls; theory P(PASS) 0.995`

**E0F sentence.** On three fresh seeds the from-empty runs at 2.0 × and 2.5 × were all stable. The single seed-0 instability at 2.5 × (realized 2.73 ×) is therefore an arrival-count effect, as the blind simulator predicted. Across all 12 from-empty runs, stability is monotone in the realized arrival rate, with the edge between 2.67 × and 2.73 × λ_ref.
