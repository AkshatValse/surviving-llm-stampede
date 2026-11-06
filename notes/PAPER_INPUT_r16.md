# PAPER_INPUT r16 (MIRROR), part 0: design, frozen predictions and rules (results pending)

For the paper session (nova-reframe), from the lead, 2026-11-05 about 14:35 CST. Branch `r16/mirror` (worktree
`Nova-Research-wt/mirror`). Results will follow as part 1; until then every outcome below is `\pending`.

## One-paragraph summary for the paper (adapt freely; numbers are frozen)

Theorem 2 factors the trapped completion rate as D = lambda_miss H(z) Gamma(z):
- Gamma(z) >= 1 comes from context growth;
- H(z) comes from the turn-count law, and is about 1 for the geometric turn count of our workload, which is why every
  trapped run at a load above the all-miss capacity completes sessions above it (the youth premium). CUT-B's runs, cut
  to below it, completed 0.92-0.97 lambda_ref, as model F predicts. (Corrected 16:30 after the audit; the earlier text
  said "every trapped run so far".)

The theorem therefore predicts that the premium reverses when agents run to a fixed step budget, since a nearly
deterministic T gives H(z) well below 1. MIRROR tests this blind:
- **Design.** The same engine, pool, burst and run length as the E2 protocol, with one change: the workload's turn count is
  T = min(Geometric(1/1000), 20), so about 98% of the sessions run exactly 20 turns. Its model all-miss capacity is
  1.046 lambda_ref, against 1.004 for the standard workload.
- **Model F's predictions.** At 1.65 lambda_ref, model F predicts three things:
  - completions nearly stop for about 40 minutes after the burst (0.05-0.09 lambda_ref over [2400, 3600) s), because the
    burst cohort must pass through 20 FIFO cycles, each longer than the last, before any of it can finish;
  - the cohort then completes in a wave, with its median completion at 5135-5195 s by seed;
  - completions then stay near half the all-miss capacity (0.49-0.60 lambda_ref over [6600, 8700) s), while the backlog
    grows 1.65-1.95 times as fast as the plan's excess load lambda_plan - lambda_miss over [6000, 8700) s (1.4 times
    asymptotically). (Corrected 16:30 after the audit; the earlier text gave only the asymptotic 1.4, which is not what
    rule M4 scores. See the errata in notes/PREDICTIONS_r16_mirror.md.)
- **The alternatives.** Every throughput-curve reading predicts steady completions near 1.05 lambda_ref and no wave: the
  quasi-static one, Lu et al.'s dN/dt = lambda - X(N)/K, and our Eq. (fluid). The standard workload's measured traps sit
  at 1.05-1.48 lambda_ref in the first window and 1.01-1.35 in the second.

## Design (what changed, exactly)

- Config: `configs/agentload_e2_mirror_k20.yaml` is `configs/agentload_e2_burst.yaml` with `workload.mean_turns` 15 -> 1000
  and `workload.max_turns` 60 -> 20 (plus its description text). Nothing else differs (scripted diff of the parsed YAML).
- Cell label `sglang-fcfs-r1-mirror-k20`: SGLang 0.5.22 FCFS, waiting-prefix refresh on, 300k pool, Qwen2.5-7B-Instruct,
  A100 80GB PCIe.
- Rates are multiples of the standard workload's registered lambda_ref = 0.071534 /s.
- Arms (one per job, seeds 0-2, 8700-s runs, burst of 200 sessions in [1200, 1260) s):
  - BURST at 1.65 x (decisive cell);
  - BURST at 1.35 x (secondary cell);
  - NOBURST at 1.65 x (controls);
  - one E0a of the workload (MODE=miss, closed POP 32, cache off), which measures its all-miss capacity; no rule uses it.
- Why K = 20:
  - the model all-miss capacity of the step-capped workload matches the standard one (1.046 vs 1.004 lambda_ref);
  - its good-state basin at 1.65 x is wide (n1 = 14.3, n_u = 41.8), so the no-burst arm should stay good;
  - chosen by computation only (K = 15, 20 and 25 and mean_turns 30, 40 and 60 were compared in the model). No engine run
    of the workload existed.

## Theory numbers (asymptotic; `results/theory/r16/mirror_predictions.json`)

| rate | rho | D / lambda_miss | H | Gamma | standard workload D / lambda_miss | alpha / (lambda - lambda_miss) |
|---|---|---|---|---|---|---|
| 1.65 x | 1.577 | 0.771 | 0.699 | 1.103 | 1.223 (H 0.989, Gamma 1.236) | 1.398 (standard: 0.65) |
| 1.35 x | 1.291 | 0.870 | 0.825 | 1.055 | 1.126 | 1.447 |

## Frozen per-seed predictions (model F, plan-driven FIFO; rates in lambda_ref)

1.65 x (decisive):

| seed | blackout [2400,3600) | wave time (median t_end of burst sessions) | burst IQR | late [6600,8700) | backlog slope [6000,8700) F / QS |
|---|---|---|---|---|---|
| 0 | 0.047 | 5195 s | 4803-5392 | 0.546 | +0.0789 / +0.0478 |
| 1 | 0.070 | 5135 s | 4876-5299 | 0.599 | +0.0857 / +0.0441 |
| 2 | 0.093 | 5157 s | 4788-5376 | 0.486 | +0.0930 / +0.0518 |

1.35 x (secondary): the wave times are 4883 / 4802 / 4870 s. Each is earlier than at 1.65 x, by 287-334 s per seed (corrected after the audit from "270-330 s"); this is
registered secondary W6.

## Registered rules (`analysis/r16_mirror.py`; registration commit bc81ee7, tag `r16-mirror-reg`, pushed 14:07:35 CST per GitHub's activity log)

Per BURST run, the rules are:
- M1: blackout completions <= 0.30.
- M2: |wave time - F| <= 0.15 (F - 1200 s).
- M3: late completions <= 0.85.
- M4: the backlog slope is closer to model F's than to the quasi-static slope.

Seed calls:
- RENEWAL iff the run is STUCK and M1-M4 hold;
- CURVE iff both completion windows are >= 0.85 (the throughput-curve signature);
- NOT-TRAPPED iff the run is not STUCK;
- otherwise MIXED.

The cell PASSES with 2 of 3 RENEWAL, FAILS with 2 of 3 CURVE, and is NO-TRAP with 2 of 3 NOT-TRAPPED. Secondary rules:
- W5: the wave against the calibrated value, +-5% of the elapsed time;
- W6: the rate ordering;
- W7: composition within 5%;
- W8: the late level within 0.25;
- W9: NOBURST controls GOOD;
- W10: the measured all-miss capacity.

**Tolerance provenance (committed data only).** On the six committed standard-workload BURST runs, model F's plan-driven
FIFO times burst-session completions about 8% late: measured/model elapsed time is 0.9125-0.9327 per run, mean 0.9223. M2's
+-15% covers that bias. W5 applies the factor 0.9223 with +-5%.

**Not blind, to state:**
- The lead chose the workload after computing the model's predictions for it and for a few alternatives.
- The tolerance factor comes from the standard workload's committed runs.
- No simulator prediction was made for MIRROR.
- The test came after Lu et al. (5 Nov).

## Figure

`figures/r16/fig_mirror.py` (in `r16/mirror`) draws:
- panel (a): completions per 300-s bin after the burst;
- panel (b): the backlog.

Each panel shows the standard workload's three committed 1.65 x traps (grey), model F's frozen step-capped predictions
(blue dashed) and, once pulled, the step-capped runs (orange). A preview without MIRROR data is
`results/theory/r16/fig_mirror.pdf` once rendered there. The final version comes with part 1.

## Suggested paper text placement

- One subsection in the evidence section, "A reversed youth premium (MIRROR)", with the figure.
- One ledger row: claim "the premium's sign is set by the turn-count law (Theorem 2's H)"; test MIRROR; blind;
  result \pending.
- In the intro's contributions, one clause, once the result is in.

---

# PAPER_INPUT r16 (MIRROR), part 1: the outcome (2026-11-05, about 18:50 CST)

For nova-reframe, from the lead. Branch `r16/mirror`. Every number below comes from the registered output
`results/agentload_analysis_r16_mirror/20261105-173136/` (commit f641b02, pushed 17:39:41 CST) or the files named with it.
Five independent checks verified it (`results/agentload_analysis_r16_mirror/verify_20261105/`, REPORT.md and results.json).

## Verdict (registered)

- 1.65 x lambda_ref (DECISIVE): RENEWAL in seeds 0, 1 and 2 -> **PASS**.
- 1.35 x lambda_ref (SECONDARY): RENEWAL in seeds 0, 1 and 2 -> **PASS**.
- All nine runs count. Each is the registered cell's, finished at 8700 s, is bound to the registration (prereg sha256
  88e20ce2...), and was driven by its frozen plan. The plans are exact in sid, origin, idx, n_turns and arrival_s; tool times
  agree within 5.7e-14 s, inside the registered tolerance. Do not write "byte-identical".
- All six BURST runs were STUCK (hit fraction 0.000 over [5700, 8700) s), and all 200 burst sessions of each completed by
  8700 s. The three NOBURST controls stayed GOOD (W9 3/3): hit 0.949-0.950 (the workload's ceiling 1 - 1/E[T]),
  completions 1.66-1.82 lambda_ref in the two windows, backlog slopes within 0.001 /s of zero.

## Per run (rates in lambda_ref; model F's frozen value in parentheses; slopes /s, F / quasi-static)

| rate, seed | blackout [2400,3600) | wave (s) | late [6600,8700) | slope [6000,8700) |
|---|---|---|---|---|
| 1.65, 0 | 0.070 (0.047) | 4996 (5195) | 0.592 (0.546) | 0.0767 (0.0789 / 0.0478) |
| 1.65, 1 | 0.058 (0.070) | 4945 (5135) | 0.606 (0.599) | 0.0837 (0.0857 / 0.0441) |
| 1.65, 2 | 0.093 (0.093) | 5089 (5157) | 0.499 (0.486) | 0.0935 (0.0930 / 0.0518) |
| 1.35, 0 | 0.105 (0.000) | 4759 (4883) | 0.619 (0.599) | 0.0557 (0.0565 / 0.0274) |
| 1.35, 1 | 0.093 (0.058) | 4673 (4802) | 0.739 (0.686) | 0.0504 (0.0534 / 0.0192) |
| 1.35, 2 | 0.163 (0.070) | 4576 (4870) | 0.845 (0.726) | 0.0496 (0.0603 / 0.0278) |

- The waves came 69-295 s before model F's times, i.e. 1.7-8.0% of the elapsed time against M2's 15%. At 1.65 x they peaked
  at 2.8-3.5 lambda_ref per 300-s bin (model F 3.2-4.4).
- At 1.65 x the backlog grew 1.61-1.90 times as fast as the plan's excess load (model F 1.65-1.95). Every slope was nearer
  model F's than the quasi-static one, by at least 0.011 /s.
- The late completions are below this workload's measured all-miss capacity, 1.062 lambda_ref (E0a, turns-based; W10): 47-57%
  of it at 1.65 x and 58-80% at 1.35 x. The standard workload's traps sit at 1.01-1.35 lambda_ref in the same window.
- Secondary checks:
  - W5 held in 5 of 6. It failed at 1.65 x seed 2: 5089 s against F_cal = 4850 +- 182 s. On this workload model F's timing ran
    2-8% slow, (wave - 1200)/(F - 1200) = 0.92-0.98, so the standard workload's factor 0.9223 over-corrected.
  - W6 held 3/3: shifts 237 / 271 / 513 s against model F's 312 / 334 / 287 s. W6 tests only the order.
  - W7 held 6/6 (served prompt +0.2% to +2.6% of model F).
  - W8 held 6/6 (late +0.007 to +0.120 lambda_ref above model F).
  - W9 held 3/3; W10 is above.

## What must be said with it (from the verifiers; all should-disclose)

1. Near threshold. At 1.35 x, seed 2 passed M3 by one completion: 127 against a ceiling of 127.69 (0.845 against 0.85). One
   more would have made that seed MIXED, and the cell would still have passed, 2 of 3. The decisive cell has wide margins: M1
   needs at least 18 more blackout completions to flip, M2 has at least 399 s spare, M3 needs at least 37 more late completions,
   and M4 is at least 0.0134 /s past the midpoint.
2. W5 failed once (above).
3. M4 is not independent of M3. The plan fixes the arrivals, so the backlog slope is the plan's arrival rate minus a weighted
   completion rate over [6000, 8700), nearly what M3 measures. The pass rests on three observations: the blackout, the wave
   and the lull.
4. The late window measures model F's post-wave transient lull (frozen 0.49-0.73), not Theorem 2's asymptote (D = 0.81 and
   0.91 lambda_ref, D/lambda_miss = 0.771 and 0.870). At 1.35 x a second completion wave enters the window: seed 2 completed
   1.01 lambda_ref over [7500, 8700) s (model F 0.87). So the test confirms the plan-driven prediction of the sign reversal; it
   does not measure the asymptotic premium.
5. Scope. The registered rivals are the throughput-curve readings, none of which gives a blackout or a wave. The pass rejects
   them; it does not separate model F from other FIFO or age-structured models with the same turn count. No alternative wave
   time was registered.
6. The E0a deviation. 17264061 failed its own pre-run time check (it needed 7080 s, and 5369 s of the registered 01:30:00
   were left), so no run started. It was resubmitted as 17264093 (14:53:08) with --time 02:15:00 and nothing else changed.
   Only W10 uses it. It is one run (closed POP 32, seed 0, as registered). Quote the turns-based 1.062: the sessions-based
   value depends on the window here (0.99-1.17), because synchronized cohorts complete in waves.
7. Breadth. One engine (SGLang 0.5.22), one GPU type, one model, the 300k pool, one synthetic workload family, one burst, two
   rates and three seeds per cell. The seeds share plans across arms and rates.
   - NOBURST controls ran at 1.65 x only, by design. For the 1.35 x trap, the burst as cause rests on the 1.65 x controls and on
     those runs' pre-burst follow-up hit of 1.00 (post hoc).
   - The three decisive runs ran concurrently on one node, on separate GPUs.
8. The verifiers' mechanism checks are post hoc. Label them so if cited: engine prefilling at the all-miss rate (11,950-12,470
   uncached tok/s, 0.99-1.03 times the E0a's), strict FIFO completion order, no errors or restarts, the cohort in lock-step,
   and only 2.0-3.7% of the turns served late being final turns.
9. Provenance.
   - GitHub's activity log puts the registration at 14:07:35 CST (branch r16/mirror created at bc81ee7). The draft's 14:07:37 is
     wrong in three places. GitHub keeps no push time for the tag object itself.
   - The registration was on GitHub 41.5 min before the first MIRROR job (the smoke test 17264039, submitted 14:49:05) and
     43.3 min before the nine counted jobs (14:50:52-53).
   - Erratum 18ac5e6 (the note's writing time) reached GitHub at 14:49:22. Errata d8c49b7 (prose) were pushed at 16:19:36,
     during the runs. "Before any output was read" rests on the lead's record.
   - Files: provenance/push_times_2026-11-05-r16.tsv, sacct_cited_jobs_2026-11-05-r16{,_utc}.txt,
     github_activity_2026-11-05-r16.json and github_tag_refs_2026-11-05-r16.json.
   - Do not copy the documentation errors listed in REPORT.md: "97.7-98.2%" (actual 97.72-98.28%), W6 "270-330 s", the 1.4
     backlog multiple, and the E0a "seeds 0-2" (corrected).

## The fill-ins (drafted by the claims verifier, reviewed by the lead)

`results/agentload_analysis_r16_mirror/verify_20261105/claims/mirror_fillins_7ea6eef.diff` is a unified diff against paper
7ea6eef. It applies cleanly there (`git apply --check -p1`). The item-by-item list is in `claims/fillins_final.txt`.
- Core: the intro clause, the ledger cell, Section 4.1's outcome, Fig. 4 as a figure* at \textwidth with its caption, App. C's
  outcome (a table and a scope paragraph), the Table 12 and Table 14 cells, and Table 18's MIRROR rows.
- Also corrected: the push time in three places, and W10 ("which only the secondary check W10 uses").
- Scoping "of our workload" in the five places MIRROR now contradicts: the intro's "The question", Section 4's opening, the
  Fig. 2 caption, Section 4.1's opening and App. E criterion (a).
- The conclusion's backlog sentence, the Limitations sentence, and Table 19's MIRROR row.
- The verifier's test build of all of it: 66 pages, main text ending on p. 12, 0 overfull boxes, one pending marker (\repourl).
- Two polish notes from the lead:
  - "a fixed multiple of the excess load" in the conclusion reads as constant across loads; "a load-dependent multiple" is
    more precise.
  - The conclusion's added clause "and with a 20-step budget slower, as a blind test found on the engine after a burst" could
    read better as "; with a 20-step budget they complete slower, as a blind test on the engine found after a burst".
- The figure: copy `results/theory/r16/fig_mirror.pdf` (f641b02) to `paper/figs/fig_mirror.pdf`. Orange lines are the three
  decisive BURST runs (jobs 17264055-57); grey lines are 17093390 / 17093396 / 17093402.
- The abstract (not in the diff; the lead recommends it, flagged for Akshat). Replace the sentence "Blind in outcome, 4 runs in
  two cells trapped by a tool slowdown alone met 4 of 5 pre-set scores, and after arrival cuts the traps persisted, backlogs
  rising or falling slowly, as predicted." with "Blind in outcome, 4 runs trapped by a tool slowdown met 4 of 5 pre-set
  scores, cut traps persisted, and with a 20-step budget, trapped runs completed below the all-miss capacity, as predicted."
  The verifier estimates 1919 of 1920 form characters; confirm with count.py and keep ARXIV_METADATA.md's form text equal to
  it.
