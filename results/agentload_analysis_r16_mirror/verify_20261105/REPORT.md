# RECOMPUTE notes
COMMAND (from the scratch dir C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/recompute):
PYTHONIOENCODING=utf-8 "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" -I recompute_mirror.py --pred mirror_predictions_tag.json --plans-dir "<wt>/results/theory/r16/mirror_plans" --out-dir . <the 9 run dirs>
- mirror_predictions_tag.json is the output of `git show r16-mirror-reg:results/theory/r16/mirror_predictions.json`. The working-tree copy is identical (git diff --quiet returned 0); the same holds for the prereg/e2 configs, the frozen plans and configs/agentload_analysis.yaml.
- The script imports only numpy, pandas and yaml; nothing from the repo. I opened none of the forbidden analysis/*.py files.
- Outputs: recompute_out.json and recompute_runs.csv, both written 17:38:09. I first opened the registered files after that (show_registered.py is from 17:39:32). Post-hoc scripts: compare_registered.py, probe_slope.py, compare_bins_and_margins.py, extra_checks.py, all in the same dir.

IDENTITY (from meta.json, config_effective.yaml, argv and plan.csv; every source agrees):
- 145227 = job 17264055, burst 1.65x, seed 0
- 145244-2 = job 17264056, burst 1.65x, seed 1
- 145240 = job 17264057, burst 1.65x, seed 2
- 145242 = job 17264058, NOBURST 1.65x, seed 0
- 145247 = job 17264059, NOBURST 1.65x, seed 1
- 145248 = job 17264060, NOBURST 1.65x, seed 2
- 145244-1 = job 17264062, burst 1.35x, seed 0
- 145246 = job 17264063, burst 1.35x, seed 1
- 145244 = job 17264064, burst 1.35x, seed 2
All nine runs: label sglang-fcfs-r1-mirror-k20, status finished, run end 8700.014-8700.114 s, no abort, git bc81ee7 (clean), prereg sha 88e20ce2..., mean_turns 1000 / max_turns 20, resolved rate = mult x lambda_ref.
Each plan.csv equals its frozen plan: sid, origin, idx and n_turns exactly; arrival_s bitwise; tool_time_total_s within 5.6e-16 relative (float text formatting only).
Every burst run has 200/200 burst sessions completed before 8700 s. No session has status failed.

PER RUN (burst; rates in lambda_ref; completion counts in brackets; S_QS uses the brief's constant):
| run | blackout | late | wave (F, tol) s | slope (S_F, S_QS) | lambda_plan (base arrivals) | M1-M4 | call |
|---|---|---|---|---|---|---|---|
| 1.65 s0 | .0699 [6] | .5925 [89] | 4995.9 (5194.7, 599.2) | .076738 (.078944, .047762) | .122593 (331) | TTTT | RENEWAL |
| 1.65 s1 | .0582 [5] | .6058 [91] | 4944.5 (5135.4, 590.3) | .083678 (.085715, .044058) | .118889 (321) | TTTT | RENEWAL |
| 1.65 s2 | .0932 [8] | .4993 [75] | 5088.6 (5157.5, 593.6) | .093538 (.093000, .051836) | .126667 (342) | TTTT | RENEWAL |
| 1.35 s0 | .1048 [9] | .6191 [93] | 4758.7 (4883.0, 552.4) | .055673 (.056524, .027391) | .102222 (276) | TTTT | RENEWAL |
| 1.35 s1 | .0932 [8] | .7389 [111] | 4673.2 (4801.8, 540.3) | .050391 (.053358, .019243) | .094074 (254) | TTTT | RENEWAL |
| 1.35 s2 | .1631 [14] | .8454 [127] | 4575.6 (4870.2, 550.5) | .049656 (.060308, .027762) | .102593 (277) | TTTT | RENEWAL |
NOBURST (blackout, late, slope): s0 1.7358 [149], 1.6842 [253], -0.000968; s1 1.7940 [154], 1.6642 [250], -0.000335; s2 1.7008 [146], 1.8173 [273], +0.000148.

AGREEMENT: bitwise equal to the registered values (max relative difference 0.0):
- blackout and late rates, and their counts; wave, burst_completed, lambda_plan, S_F, F_wave, run_end_s;
- plan_matches_frozen, stuck, M1-M4, call, cell verdicts;
- the 25 per-300-s bins in mirror_bins.json (an extra check), for all 9 runs.

MARGINS:
- M3 at 1.35x s2 (job 17264064) holds by ONE completion: 127 against 127.69 needed (late 0.8454 vs 0.85). No completion falls within 2 s of 6600 or 8700, so the window convention cannot flip it. If M3 had failed, that seed would be MIXED and the 1.35x cell would still PASS 2/3.
- Every other margin is wide: M1 needs at most 14 of 25.75 completions; M2 has at least 256 s of room; M4 at least 0.0112 /s; CURVE is never close (blackout at most 0.163).

AMBIGUITIES:
(a) Backlog bin mean. Resolved as the brief says, with 1-s samples. The exact-average reading reproduces the registered slope; no boolean changes. The bin-centre choice (+5 or +4.5) does not change the slope.
(b) Hit metric. Resolved as the brief's "> 0". Both gt50 readings give 0.0 for every burst run and the same values as "> 0" for NOBURST. STUCK agrees across both windows and all metrics in all 9 runs.
(c) The STUCK window: I used both windows as the brief asks; the registered scorer uses [5700, 8700].
(d) The registered STUCK is the basin classify. Its backlog_slope also exceeds 0.5(mult-1)lambda_ref in every burst run and is below it in every NOBURST run, so no change.
(e) The S_QS constant: see disagreements.
(f) Wave median with even n: numpy's average of the middle two values. The lower and upper medians also pass M2.
(g) Call precedence: irrelevant here, since all burst runs are STUCK with CURVE false.

COMPLETIONS PER 300-s BIN, [1200, 8700), all origins (bins start at 1200, 1500, ..., 8400):
- 1.65 s0: 6 2 3 3 0 0 2 4 6 25 18 26 55 74 13 8 11 12 16 6 16 14 11 12 14
- 1.65 s1: 10 6 1 2 3 1 0 1 2 14 18 39 76 60 5 11 6 9 14 12 19 10 8 15 13
- 1.65 s2: 3 4 1 0 5 1 1 1 6 12 22 32 31 60 49 7 8 10 9 13 12 11 9 13 8
- 1.35 s0: 6 3 1 1 0 0 2 7 16 21 25 43 89 14 10 9 19 12 17 20 8 16 6 13 13
- 1.35 s1: 7 4 0 1 2 0 2 4 17 15 33 79 60 6 9 6 18 13 16 9 14 12 16 23 21
- 1.35 s2: 5 2 0 2 2 1 1 10 16 33 30 59 64 7 8 16 10 14 11 12 17 21 24 22 20
- NB s0: 35 43 38 32 26 30 40 53 41 34 32 35 37 36 34 42 46 40 30 37 44 25 35 42 40
- NB s1: 34 41 39 30 33 41 43 37 43 42 29 42 38 42 34 24 28 38 24 40 49 38 42 35 22
- NB s2: 31 44 33 40 48 40 26 32 39 43 31 39 46 32 37 34 40 31 31 47 40 38 38 40 39

EXTRA (outside the brief, rule text from the tagged note): W5, W6, W8 and W10 all match the registered values. W5 is False only at 1.65 s2 (|wave - F_cal| 238.7 > 182.5). The E0a lambda_miss_turns_based is 0.0759665 = 1.062 lambda_ref.

NOT CHECKED: p
code: C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/recompute/recompute_mirror.py
remaining disagreements:
CAUSE of the 6 S_QS differences, each a constant offset of 3.132e-7 /s: the brief's capacity constant 0.07483084 differs from the frozen lambda_miss_model 0.07483115322200824 (mirror_predictions.json:14, tag r16-mirror-reg). With the JSON value my S_QS equals the registered one bitwise in all 6 runs. M4 is unchanged under either constant.
burst_completed for the 3 NOBURST runs (20261105-145242, -145247, -145248): my script leaves it undefined because those runs have no burst sessions; the registered file has 0. This is a representational difference only; the count is 0 either way.

# PROVENANCE summary
All nine counted runs are bound to the r16-mirror-reg registration, and the registration was on GitHub well before any MIRROR job. The only deviation from the registration is the E0a resubmission with --time 02:15:00 (jobs 17264061 and 17264093), which only the secondary W10 uses. Everything else not as registered is prose or documentation and enters no rule: plan.csv files are not byte-identical to the frozen plans (equal within the registered tolerance), GitHub keeps no push time for the tag itself, and a few lines of notes are wrong.

Timing: GitHub's activity log records the creation of branch r16/mirror at bc81ee7 at 20:07:35Z = 14:07:35 CST. I re-queried GitHub read-only and got the same record. The commit and tagger time is 14:07:08 CST. The first MIRROR job, smoke test 17264039, was submitted at 14:49:05 (+2490 s) and started at 14:49:07 (+2492 s). The nine counted jobs were submitted at 14:50:52-53 (+2597 to +2598 s) and started at 14:50:57-14:51:28 (+2602 to +2633 s). The E0a resubmission 17264093 was submitted at 14:53:08 (+2733 s). The tag points to bc81ee7 both locally and on GitHub.

The nine runs: each one records commit bc81ee7 (branch r16-mirror-reg-run, clean) and the tagged registration's sha256 88e20ce2. Each job log shows the workload config sha256 afea48b8 and one PREREG_OK line. All nine have the registered label, arm, rate and seed, finished at 8700.01-8700.11 s and were not aborted. Each plan.csv matches its frozen plan row for row, within the registered tolerance. The workload really is step-capped (mean_turns 1000, max_turns 20, 97.7-98.3% of sessions at exactly 20 turns), and every BURST run has exactly 200 burst sessions arriving in [1200, 1260) s.

The scorer: its verdict file shows it read the predictions from the tag. Rerunning it with the code from the tag (output to scratch only) reproduced all three output files byte for byte. analysis/, src/, configs/ and prereg/ are identical to the tag. All 12 submit lines match the registered lines except the E0a --time, and every job used account f2026.coms.6250.02, partition instruction, QoS instruction.

Could not check:
- whether Nova holds MIRROR-workload jobs outside the exported sacct list (it lists only cited jobs; there is no cluster access from here);
- the sha256s of the pulled archives (they were deleted), though the pulled files match the counts that the analyses run on Nova recorded;
- the Nova bundle's sha256.

I changed nothing in any repository: git commands ran with GIT_OPTIONAL_LOCKS=0 and Python with -B, and no bytecode was written. The very first `git status` ran before I set that, so it may have refreshed the index's stat cache.

My scripts and outputs are in C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/provenance:
- check_runs.py, check_runs.out, runs_provenance.csv
- check_sacct.py, check_sacct.out, registered_sbatch_lines.txt
- check_plans.py, check_plans.out, plans_workload.csv
- gh_activity_r16_mirror_live.json
- rescore/agentload_analysis_r16_mirror/20261105-174446/ (the scorer rerun)
PROBLEMS:
- [should-disclose] The E0a run was not submitted as registered. The registered E0a submit line (--time 01:30:00) could never have run: the job script's default POP-64 check needs 7080 s against 5400 s, so 17264061 failed its pre-check. The resubmission 17264093 used --time 02:15:00 and was otherwise identical. Only secondary W10 uses the E0a; the verdict does not.
    evidence: sacct lines 9 and 13; pm-mire0a-17264061.out:470-471; r16_mirror.py:393 (tag). Already recorded in notes/LOG.md (2026-11-05 entry, 'Deviation (recorded)') and the E0a COMMANDS.txt. Any text reporting W10 or the E0a capacity (1.062 lambda_ref) should state it.
- [minor] No plan.csv is byte-identical to its frozen plan. They match row for row, but tool_time_total_s differs by up to 3 ulp (5.7e-14 s) in 555-697 rows per run. This passes the registered tolerance (1e-9 s). Write 'equal to the frozen plan within the registered tolerance (exact in sid/origin/idx/n_turns/arrival_s)' and never 'byte-identical'.
    evidence: scratchpad/mirror_verify/provenance/check_plans.out and the exact float pass (max abs diff 5.68e-14 s); r16_mirror.py:103, 190-202 (tag).
- [minor] GitHub keeps no push time for tags (the activity log holds only refs/heads events). The freeze record's 'tagged ... and pushed to GitHub before any MIRROR job' can be verified only for the commit bc81ee7 (branch r16/mirror created at 14:07:35 CST), not for the tag. The tag now points to that same commit on GitHub, so what was frozen is unaffected.
    evidence: provenance/github_activity_2026-11-05-r16.json: 165 events, all 'heads' (133 push, 32 branch_creation); tagged notes/PREDICTIONS_r16_mirror.md:150-153; provenance/README.md:63 ('Tag objects carry no push time').
- [minor] The tagged note's writing time ('about 16:00 CST') is impossible: the commit is from 14:07:08. Erratum 18ac5e6, prose only, corrected it. It reached GitHub at 14:49:22, before the counted jobs (14:50:52) but 17 s after the smoke job 17264039 was submitted.
    evidence: git show r16-mirror-reg:notes/PREDICTIONS_r16_mirror.md line 3; activity id 49162713099 (bc81ee7->daa9dd4, 20:49:22Z); working-tree errata block (git diff r16-mirror-reg -- notes/PREDICTIONS_r16_mirror.md).
- [minor] The E0a pull's COMMANDS.txt says 17264093 ran 'closed POP 32 seeds 0-2'. It ran seed 0 only, plus the POP-64 check at seed 0.
    evidence: results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/COMMANDS.txt:17 against SubmitLine SEEDS=0 (sacct line 13), pm-mire0a-17264093.out:55 (SEEDS="0"), and its only runs at lines 578 (closed_n=32 --seed 0) and 601 (closed_n=64 --seed 0).
- [minor] Prose range in the tagged note: '97.7-98.2% of the sessions in the plans run exactly 20 turns'. The 12 frozen plans actually span 97.72-98.28%: noburst_1.65_seed1 is 1028/1046 = 98.28%, and that plan is the counted NOBURST run 17264059. No rule uses this.
    evidence: tagged notes/PREDICTIONS_r16_mirror.md:17; awk over `git show r16-mirror-reg:results/theory/r16/mirror_plans/*.csv`.
- [minor] Not a deviation, but it can mislead a reader. The registration YAML still carries the generic E2 template's pass_rule, kill_conditions and assumptions_note, which mention a CAPPED arm MIRROR does not run. The job script's per-job `summarize burst`/`burst2` outputs in every job log (e.g. "kill_strict": true, "kill_test_pass_decisive": false) come from that generic machinery and cover one run each. They are not MIRROR results. The MIRROR rules are lambda_selection.rule plus analysis/r16_mirror.py.
    evidence: tagged configs/agentload_prereg_2026-11-05_mirror_k20.yaml:169-199 versus 125-138; pm-mir165b-17264055.out:690-745.
CHECKS (failed only):
checks passed: 19 of 19

# RULESAUDIT summary
The registered verdict is computed correctly. When I re-ran the tagged scorer, mirror_runs.csv, mirror_verdict.json and mirror_bins.json came out byte-identical. I also re-implemented every measure without importing analysis.*, and all of them match. The tagged model-F code, re-run on the frozen plans, reproduces the frozen per-seed F values (wave median, S_F, late) exactly.

Hand re-derivation from mirror_runs.csv: all six BURST runs are STUCK (hit_eval 0.000) with M1-M4 all true, so every seed is RENEWAL. That gives RENEWAL 3/3 in both cells: PASS at 1.65x (decisive) and PASS at 1.35x (secondary).

Code against the tagged text: I found ten discrepancies (STUCK window end, plan tolerance, run-end slack, seed-call precedence, M2 undefined case, wave set, W10 estimator, W6 prose, base-only lambda_plan, backlog estimator). None changes any boolean or call for these nine runs. I checked each one against the raw data.

Decisive-cell margins are large:
- M1: 18 or more extra blackout completions needed to flip.
- M2: at least 399 s of spare tolerance.
- M3: 37 or more extra late completions needed to flip.
- M4: S minus the midpoint is at least +0.0134/s.
- STUCK: hit 0.000 against 0.2.

The only near-threshold primary case is M3 at 1.35x seed 2: 127 completions against a ceiling of 127.69. One more completion makes it 0.852, M3 fails, and the call becomes MIXED; the 1.35x cell still PASSes at 2/3. ±1 s edge shifts do not flip it. Moving the window start later by more than 11.3 s does.

Secondary rules:
- W5 FAILS at 1.65x seed 2: 238.7 s against a tolerance of 182.5 s, over by 56.2 s. The 0.922 timing factor did not carry over. The registered per-session statistic on MIRROR is 0.924-0.982 (mean 0.954); 5 of 6 values fall outside the calibration range of 0.9125-0.9327.
- W5 also nearly fails at 1.35x seed 0 (margin 7.9 s; two sessions crossing the median would flip it).
- W6 order holds 3/3, but the shifts are 237/271/513 s against model F's 312/334/287 s.
- W7, W8, W9 and W10 pass.

Caveats on what the PASS shows:
- M4 is not independent of M3. Exactly, S = S_A - S_C, and S_A is fixed by the plan, so M4 is a second test of the post-wave completion shortfall. RENEWAL therefore rests on three distinct observations: blackout, wave timing, and lull.
- The late window measures model F's transient lull, not Theorem 2's asymptote. F's late values are 0.49-0.73 λref against asymptotes of 0.806 and 0.910 λref; at 1.35x a second completion wave is entering the window.
- M2's ±15% band is 1.9-8.6 times the observed errors, and the registration gives no alternative wave-time value.

No failure confound found: no session or request failures, the cache works before the burst and in NOBURST, the engine runs at the E0a all-miss token rate, and the plans are exact. What I could not check: whether any MIRROR jobs exist beyond the cited ones (no Slurm access), and the tag's own push time (the GitHub export has no tag events).
PROBLEMS:
- [should-disclose] M4 is not independent of M3. Because N(t) is arrivals minus completions and the arrivals come from the frozen plan, the M4 slope decomposes exactly into a fixed arrival term minus an OLS-weighted completion rate over [6000,8700). M4 is therefore a second test of the same post-wave completion shortfall that M3 measures. RENEWAL rests on three distinct observations (blackout, wave timing, lull), not four.
    evidence: C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/rules/m_decomp.py shows S = S_A - S_C to 5 decimals in every run. For 1.65x s0: 0.11852 - 0.04178 = 0.07673. M4 is equivalent to S_C below a run-specific ceiling of 0.771/0.835/0.798 λref (1.65x) and 0.819/0.877/0.868 λref (1.35x). The OLS-weighted completion rates S_C (0.584/0.572/0.503; 0.627/0.680/0.789 λref) track M3's late values (0.592/0.606/0.499; 0.619/0.739/0.845).
- [should-disclose] M3's late window tests model F's post-wave transient lull, not Theorem 2's asymptotic reversed youth premium (D/lambda_miss = 0.77 at 1.65x, 0.87 at 1.35x). At 1.35x the asymptote is above the M3 threshold, and the late window already contains the onset of a second completion wave. The PASS supports the plan-driven FIFO transient; it does not measure the asymptotic value.
    evidence: Frozen JSON: asymptotics D_over_lam_ref = 0.806 (1.65x) and 0.910 (1.35x). Model F's own late-window values are 0.546/0.599/0.486 and 0.599/0.686/0.726. Measured 300-s bins at 1.35x s2 (mirror_bins.json), bins 7500-8700: 0.98, 1.12, 1.03, 0.93 λref (F: 0.47, 1.12, 0.89, 1.03). At 1.35x s1: 0.56, 0.75, 1.07, 0.98.
- [should-disclose] The registered timing calibration did not carry over to this workload, and W5 fails at 1.65x seed 2. M2's ±15% band is 1.9-8.6 times the observed timing errors, and the registration gives no wave-time value for the throughput-curve alternatives (its M2 column says only 'no wave'). M2 can falsify model F's timing, but it does not discriminate between model F and the registered alternatives.
    evidence: The registered per-session statistic (mirror_predict.timing_calibration) applied to the MIRROR runs gives 0.9449/0.9520/0.9823 (1.65x) and 0.9651/0.9583/0.9236 (1.35x), mean 0.954, against the frozen 0.9223 (range 0.9125-0.9327 over 6 standard runs). W5 at 1.65x s2: 238.7 s against 182.5 s. M2 errors are 198.8/190.9/68.9/124.3/128.6/294.7 s against tolerances of 540-599 s. Note line 83: the alternatives column for M2 says 'no wave'.
- [minor] The '1.35x RENEWAL 3/3' result is one completion away from 2/3. The 1.35x PASS itself survives that change.
    evidence: 1.35x s2 late_n = 127 against a ceiling of 127.69 (0.85 x 0.0715340 x 2100). 128 completions gives 0.8521, M3 False, call MIXED (blackout 0.163 < 0.85), and the cell is still PASS on seeds 0 and 1. ±1 s edge shifts do not flip it. A start moved later by 11.3 s or more does ([6630,8700) gives 0.8577). The same run also has the largest model-F misfits: S - S_F = -0.0107/s (-17.7%, about 10x the frozen standard-workload residual sd of 0.00108), W8 +0.120, blackout 2.33x F.
- [minor] Code-vs-text discrepancies. None changes any boolean or call for these nine runs:
(a) the STUCK window runs to run.t_end_s+1e-9 inclusive, not the frozen [5700,8700), and window_matches_endpoints is never checked;
(b) the plan tolerance is relative (1e-9 x column max) rather than 1e-9 s;
(c) the run-end check allows 8700-1e-6 s;
(d) NOT-TRAPPED takes precedence over CURVE where the text's two 'iff' clauses conflict;
(e) an undefined M2 (fewer than 100 completed) counts as M2 False, which the text leaves unstated;
(f) the wave uses only burst sessions completed by 8700 (the note says just 'burst sessions');
(g) W10 uses lambda_miss_turns_based, an estimator the text does not name;
(h) lambda_plan counts base arrivals only;
(i) the backlog estimator differs from model F's (exact integration with failed sessions departing, against 1-s sampling with completed-only departures).
    evidence: Tagged files:
(a) trap_v2.py:120,194; basin.py:301,305; r16_mirror.py:241. 0 turns completed in (8700, t_end_s]; hit is the same over both windows.
(b) r16_mirror.py:200; actual differences 0 and 5.7e-14 s.
(c) r16_mirror.py:320; t_end_s 8700.014-8700.114.
(d) r16_mirror.py:257-265; all BURST runs STUCK.
(e) r16_mirror.py:210,252; 200/200 completed.
(f) r16_mirror.py:207-209, the same as mirror_predict.py:104-105.
(g) r16_mirror.py:361; the booleans are the same at 1.002 or 1.100 λref.
(h) r15_cut.py:580-583; burst arrivals all fall in [1200.35,1259.93].
(i) r15_cut.py:536-547 against cut_predict.py:157-169; there are no failed sessions and the slopes agree to 1.2e-5/s.
- [minor] W6's registered parenthetical magnitude is wrong (already covered by the working-tree erratum). The measured shifts also miss the per-seed model values by large amounts, but the rule tests order only.
    evidence: Tagged note line 109 says '270-330 s'; the frozen shifts are 311.7/333.6/287.2 s. Measured shifts are 237.2/271.3/513.0 s.
- [minor] The E0a pull record overstates the E0a design, and W10's capacity figure depends on which estimator and population are used.
    evidence: results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/COMMANDS.txt says 'closed POP 32 seeds 0-2'. Only seed 0 ran: sacct SEEDS=0, job log 17264093 line 578 shows '--seed 0', and lambda_miss_runs.csv has 1 row. lambda_miss is 1.062 λref (turns-based, POP 32), 1.002 (sessions-based) and 1.100 (POP-64 popcheck, turns-based). The E0a ran on nova22-gpu-1 alongside NOBURST seeds 1 and 2. Its job was resubmitted with --time 02:15:00 after 17264061 failed its pre-check (7080 s needed > 5369 s available).
- [minor] Provenance gap: the GitHub activity export has no tag events, so the push time of r16-mirror-reg is not recorded directly. The scorer's predates check uses the author-set commit time rather than the server push time.
    evidence: provenance/github_activity_2026-11-05-r16.json contains only refs/heads events (133 push, 32 branch_creation). The commit itself was pushed as branch creation at 20:07:35Z. r16_mirror.py:367-369 compares commit_unix (from git show --format=%ct) with min t0. Both times precede the runs by about 45 min, so there is no impact.
- [minor] Scope. The PASS rejects the three registered throughput-curve readings, which the registration itself describes as producing 'no blackout or wave'. No age-structured or FIFO alternative with different costs was registered. Beyond the M2 and M4 numbers, the PASS therefore does not single out model F's particular renewal law among models that share its turn-count structure.
    evidence: Tagged note lines 29-35 list the alternatives (quasi-static, Lu et al. fluid, Eq. (fluid)) and say 'None of them gives a blackout or a wave'. The rules table (lines 80-85) compares only against these. Not checkable: whether other MIRROR jobs exist outside the cited sacct records (no Slurm access), and the pulled tarballs against Nova (the remote archives were deleted; only the sha256 recorded in COMMANDS.txt remains).
CHECKS (failed only):
- FAIL W5 calibrated wave (±5%): |wave - F_cal| against 0.05 (F_cal - 1200), all in seconds:
- 1.65x s0: 111.7 vs 184.2, PASS (+72.6).
- 1.65x s1: 115.0 vs 181.5, PASS (+66.5).
- 1.65x s2: 238.7 vs 182.5, FAIL (over by 56.2 s; wave 5088.6 against F_cal 4849.9).
- 1.35x s0: 161.9 vs 169.8, PASS (+7.9; two sessions crossing the median flip it: 4767.3 > 4766.6).
- 1.35x s1: 151.3 vs 166.1, PASS (+14.8).
- 1.35x s2: 9.4 vs 169.3, PASS.
Registered per-session calibration statistic on these runs: 0.9449, 0.9520, 0.9823, 0.9651, 0.9583, 0.9236 (mean 0.954), against the frozen 0.9223 (range 0.9125-0.9327).
checks passed: 18 of 19

# ARTIFACT summary
Artifact risk is LOW. I found no cause other than FIFO queueing of a zero-hit engine at its all-miss rate that could have produced the blackout, the wave and the low late completions; that queueing is model F's mechanism.

In all six BURST runs the engine stayed busy at the all-miss rate through the blackout. It served 1.46-1.60 turns/s and 11,950-12,470 uncached tok/s (0.99-1.03x E0a's 12,120), with three independent sources agreeing (client requests, server batch log, engine counters). Hits were exactly zero. The queue never emptied (264-389 waiting) and the scheduler was never idle. The GPU sat at 100% and 300 W, and service was strictly FIFO (Spearman 1.000000).

There were no errors, aborts, restarts, retractions, OOMs, timeouts or client throttling, and no completion gap over 20 s after the burst. Cancellations happened only at 8700 s. The client ran the frozen plan to within milliseconds.

The burst cohort explains the blackout. 97-99% of its sessions have T=20. At 3000 s they were 12-19 turns in and advancing in lock-step, with per-turn steps growing from 48 s to about 375 s, which is the FIFO latency. The wave is their 20th turns; median 4576-5089 s, and all 200 completed.

Late completions are low because of the turn mix: only 2.0-3.7% of the turns served late were final turns (5% would be stationary), while turns kept being served at the full rate.

The NOBURST controls stayed good the whole run: follow-up hit 0.9999, empty queue, 1.6-1.8 lambda_ref steady.

E0a is clean: no errors, POP-64 within +1.5%. W10 holds against every capacity estimate (late 0.50-0.85 vs at least 0.994 lambda_ref). However, E0a's sessions-based lambda_miss depends on the window because of cohort waves, so the turns-based 1.062 should be quoted. COMMANDS.txt wrongly says seeds 0-2.

All my scripts and outputs are under C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/artifact (a01-a06 *.py, out/*.csv, a0*_out.txt). I did not edit anything in the worktree.
PROBLEMS:
- [should-disclose] For this workload, E0a's sessions-based lambda_miss (0.071666 /s = 1.002 lambda_ref, in calibration.json and COMMANDS.txt) depends on the window chosen. The closed POP-32 population starts synchronized and T is nearly fixed, so session completions come in waves that persist through the [900,2700) window. The turns-based value is stable and is the one to cite; the LOG already uses it (1.062). There is only one E0a run (n_runs 1), so no SE.
    evidence: a05_e0a.py over results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results/agentload_e0_miss/20261105-145429. Completions per 300-s block in [900,2700): POP32 [4,30,30,12,22,31]; POP64 [4,7,55,2,18,44]. Sessions-based rate by window, same POP32 run: [900,2700) 1.002, [600,2700) 1.065, [1200,2700) 1.165, [900,1800) 0.994. POP64 run: 0.994-1.27. Turns-based: 1.050-1.078 (POP32), 1.043-1.107 (POP64). The W10 conclusion holds under every variant.
- [minor] COMMANDS.txt for the E0a pull says job 17264093 ran 'closed POP 32 seeds 0-2 + the POP-64 check'. It actually ran seed 0 only, which is what was registered.
    evidence: results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/COMMANDS.txt:17 vs logs/pm-mire0a-17264093.out:55 (SEEDS="0") and :578 (a single '--seed 0 --set arrivals.closed_n=32' run). calibration.json has n_runs 1. The registered line has SEEDS=0 (analysis/r16_mirror.py:398). This is a documentation error only.
- [minor] All three decisive 1.65x BURST runs, plus 1.35x s1, ran at the same time on one node (nova22-gpu-2), on separate GPUs. E0a ran on another node (gpu-1). All-miss speed varies about 2-3% between GPUs. The slowest is 1.65x s2, which could explain part of its late wave (the W5 miss) but cannot change any M-rule.
    evidence: sacct NodeList and nvidia-smi bus ids in the job logs. 1.65x s2 (17264057, bus C6): blackout prefill 11,950 tok/s and 13,150 tok/s per full chunk, vs 12,350 / 13,630 for s0 and 13,623 per chunk in E0a. Its wave is 5089 s against W5's 4850+-182; M2 margin is 68 of 594 s. NOBURST pairs also ran on other GPUs and nodes (e.g. s0 on gpu-3). That is harmless: NOBURST engines ran at about 12% of all-miss prefill with an empty queue.
- [minor] GPU utilization by itself does not show the engine is saturated. SGLang's own sglang:utilization and sglang:fwd_occupancy gauges read 0 in every run (not populated in 0.5.22). nvidia-smi reports 93-95% utilization and about 285 W even for the lightly loaded NOBURST engines. Saturation has to be shown from the prefill token rate, the non-empty queue and scheduler idle = 0, as done here.
    evidence: windows_metrics.csv: utilization_mean and fwd_occupancy_mean are 0 in every run and window. gpu_serverlog_windows.csv: NOBURST gpu_util_mean 90.9-95.7%, power 278-291 W, vs BURST trapped 99.7-100% and 297-300 W.
- [minor] Completion gaps of about 19-25 s exist, inside E0a's measurement window and once in a BURST run after the burst. They are prefill-first scheduling phases, roughly the 300k-token pool divided by 12k tok/s, not stalls. Worth noting for anyone who audits gaps.
    evidence: E0a POP32: 24.8-s gap starting at t=2062 s; POP64: 24.9 s at 1442 s. 1.35x s2: 19.4 s after 1200 s. The engine batch log shows no gap over 2 s in E0a [900,2700) and none over 2-4 s in BURST [1200,8700], and scheduler idle is about 0.
- [minor] By design, the 1.35x secondary cell has no NOBURST control (the registration has NOBURST only at 1.65x). That the burst caused the 1.35x trap rests on the 1.65x controls plus each 1.35x run's own pre-burst follow-up hit fraction of 1.00.
    evidence: configs/agentload_prereg_2026-11-05_mirror_k20.yaml lambda_selection: noburst at 1.65x only. a04/a06 outputs: 1.35x pre-burst follow-up hit 1.0000, then 0.0000 from 1500 s.
CHECKS (failed only):
checks passed: 12 of 12

# CLAIMS
headline: In a registered test frozen on GitHub before any MIRROR job, the only change was a 20-step budget for the agents, and model F's predicted reversal of the youth premium held on SGLang: after a 200-session burst, all six BURST runs (1.65 and 1.35 λref, seeds 0–2) stayed at zero hits. They almost stopped completing sessions (0.06–0.16 λref over [2400,3600) s), finished the burst cohort in a wave at 4576–5089 s (69–295 s before model F's frozen times), and then completed 0.50–0.85 λref over [6600,8700) s. That is below the measured all-miss capacity of 1.06 λref and below the ~1.05 λref every throughput-curve reading predicts, so the registered rule called RENEWAL in 3 of 3 seeds in both the decisive and the secondary cell. The test is blind in outcome only: the workload was chosen with the model.
claims:
- Verdict. The registered scorer gives PASS in the decisive cell (1.65 λref) and PASS in the secondary cell (1.35 λref), RENEWAL in seeds 0, 1 and 2 of each (results/agentload_analysis_r16_mirror/20261105-173136/mirror_verdict.json, cells). It used code identical to tag r16-mirror-reg and read the predictions from the tag (mirror_verdict.json predictions.source.git_ref). Two verifiers re-ran it and reproduced mirror_runs.csv, mirror_bins.json and mirror_verdict.json byte for byte (sha256 c7e27b30…, 512b66f3…, 4e835bc8…, which I confirmed with sha256sum). A blind re-implementation that imports no repository code matched every M1–M4, STUCK, call and cell verdict.
- Registration and binding. Commit bc81ee7 (14:07:08 CST, tag r16-mirror-reg) reached GitHub at 14:07:35 CST: branch r16/mirror was created at bc81ee7 at 20:07:35Z (provenance/github_activity_2026-11-05-r16.json:153-159). That was 41.5 min before the first MIRROR job was submitted (cache-off smoke test 17264039, 14:49:05) and 43.3 min before the nine counted jobs (17264055-60 and 17264062-64, 14:50:52-53; provenance/sacct_cited_jobs_2026-11-05-r16.txt lines 2-12). Every run's meta.json records commit bc81ee7 (clean) and prereg_sha256 88e20ce2…, which equals sha256 of the tagged registration (spot-checked by me for all nine). All nine finished at 8700.01-8700.11 s with 0 failed sessions and 0 request errors. Each was driven by its frozen plan, exact in sid/origin/idx/n_turns/arrival_s, with tool times within 5.7e-14 s.
- Trapped, with good controls. All six BURST runs were STUCK: hit fraction 0.000 over [5700,8700) s (mirror_runs.csv hit_eval and fu_hit_5700_8700 = 0.0). In each, all 200 burst sessions completed by 8700 s (burst_completed = 200). The three NOBURST controls at 1.65 λref stayed GOOD (W9 3/3): hit 0.9493-0.9499, which is the ceiling 1-1/E[T] = 0.9495 for E[T] = 19.81; follow-up hit 0.9999-1.0000; completions 1.66-1.82 λref in both windows; backlog slopes -0.00097 to +0.00015 /s.
- Blackout (M1 ≤ 0.30 λref). Over [2400,3600) s, the 1.65 λref runs completed 0.070, 0.058 and 0.093 λref (6, 5 and 8 sessions) against model F's frozen 0.047, 0.070 and 0.093. The 1.35 λref runs completed 0.105, 0.093 and 0.163 (9, 8 and 14) against 0.000, 0.058 and 0.070. The standard workload's six committed traps completed 1.05-1.48 λref in the same window (I recomputed this from their sessions.csv: 1.048-1.479).
- Wave (M2: within 15% of model F's elapsed time). The median completion of the 200 burst sessions came at 4996, 4945 and 5089 s at 1.65 λref (model F 5195, 5135, 5157; tolerance ±599, 590, 594 s). At 1.35 λref it came at 4759, 4673 and 4576 s (model F 4883, 4802, 4870; tolerance ±552, 540, 551 s). Every wave was early, by 69-295 s, which is 1.7-8.0% of the elapsed time. At 1.65 λref the waves peaked at 2.8-3.5 λref per 300-s bin (model F 3.2-4.4).
- Lull below the all-miss capacity (M3 ≤ 0.85 λref). Over [6600,8700) s the runs completed 0.592, 0.606 and 0.499 λref at 1.65 (model F 0.546, 0.599, 0.486) and 0.619, 0.739 and 0.845 at 1.35 (model F 0.599, 0.686, 0.726). All six are below this workload's measured all-miss rate of 1.062 λref (E0a, turns-based). That is 47-57% of it at 1.65 λref and 58-80% at 1.35 λref. They are also below the sessions-based 1.002 and the model's 1.046. The standard workload's traps completed 1.01-1.35 λref in the same window. On one engine and protocol, the sign of the trapped-completion premium followed the turn-count law, as Theorem 2's H predicts (H 0.699 at 1.65 λref, against 0.989 for the standard workload).
- Backlog (M4: slope nearer model F's than the quasi-static one). At 1.65 λref the OLS slopes over [6000,8700) s were 0.0767, 0.0837 and 0.0935 /s (model F 0.0789, 0.0857, 0.0930; quasi-static 0.0478, 0.0441, 0.0518). That is 1.61-1.90 times the plan's excess load, against model F's 1.65-1.95, and within -2.8% to +0.6% of model F. At 1.35 λref the slopes were 0.0557, 0.0504 and 0.0496 (model F 0.0565, 0.0534, 0.0603; quasi-static 0.0274, 0.0192, 0.0278), 1.5-17.7% below model F. Every slope was nearer model F's than the quasi-static one, by at least 0.011 /s.
- Registered secondary checks (not in the verdict). W5 held in 5 of 6 and failed in 1. W6 held in 3 of 3: shifts 237, 271 and 513 s against model F's 312, 334 and 287 s, and only the order is registered. W7 held in 6 of 6 (served prompt +0.2% to +2.6% of model F). W8 held in 6 of 6 (late completions 0.007-0.120 λref above model F, every one positive). W9 held in 3 of 3. W10: the E0a measured 1.062 λref (model 1.046, +1.5%), and every late value lies below it (mirror_verdict.json W10_capacity).
- Post hoc checks by the verifiers, not registered, found no artifact. The trapped engines prefilled at the all-miss token rate: 11,950-12,470 uncached tok/s, 0.99-1.03 times the E0a's 12,120. The queue never emptied, and completion order was strictly FIFO (Spearman 1.000000). There were no errors, restarts or timeouts. The burst cohort advanced in lock-step, and the wave is its 20th turns. The late lull comes from the young turn mix (2.0-3.7% of served turns were 20th turns, against 5% stationary), not from a slower engine. Before the burst, follow-up hits at 1.35 λref were 1.00, and they were 0.000 from 1500 s on.
caveats:
- Blind in outcome only, and these limits are already registered and must stay in the text. The lead chose the workload after computing model F's and the fluid model's predictions for it and for K = 15, 20, 25 and mean_turns 30, 40, 60. K = 20 was picked for the capacity match (1.046 against 1.004 λref) and the wide basin (n_u 41.8). The M2/W5 timing factor (0.9223) and the M1/M3/CURVE thresholds were set from the standard workload's committed runs. No simulator prediction was made. The test was registered on 5 Nov, after Lu et al.'s paper (2 Nov).
- Near threshold: 1.35 λref seed 2 (job 17264064) passed M3 by one completion (127 against a ceiling of 127.69; 0.8454 against 0.85). One more late completion, or a late window starting at least 11.3 s later, would have made that seed MIXED. The 1.35 λref cell would still pass 2/3, and the decisive cell is unaffected. The same run has the largest model-F misfits: slope 17.7% below S_F, late +0.120 λref, blackout 2.3 times model F. W5 at 1.35 λref seed 0 held by only 7.9 s (161.9 against 169.8 s).
- A registered secondary check failed. W5 failed at 1.65 λref seed 2 (job 17264057): |5088.6 - 4849.9| = 238.7 s against 182.5 s. The standard workload's timing calibration did not transfer: (wave-1200)/(F-1200) is 0.92-0.98 on MIRROR against 0.9125-0.9327 there, so model F ran only 2-8% slow and the 0.9223 factor over-corrected. The text should report the miss; the proposed fill-ins do.
- Scope of the rejection. The registered alternatives are only the throughput-curve readings (quasi-static, Lu et al.'s dN/dt = λ - X(N)/K, Eq. (fluid)), and none of them predicts a blackout or a wave. The PASS rejects them. It does not single out model F among FIFO or age-structured models with the same nearly deterministic turn count. No alternative wave time was registered, and M2's ±15% band is 1.9-8.6 times the observed timing errors.
- M4 is not independent of M3. The plan fixes the arrivals, so the backlog slope is the arrival rate minus a weighted completion rate over a window overlapping M3's. RENEWAL therefore rests on three observations (blackout, wave, lull), not four.
- The late window measures model F's post-wave transient (frozen values 0.49-0.73 λref), not Theorem 2's asymptote (D = 0.81 and 0.91 λref; D/λmiss = 0.771 and 0.870). At 1.35 λref a second completion wave enters the window: seed 2 completed 1.01 λref over [7500,8700) s (model F 0.87). 'Below the all-miss capacity' is shown only for the registered window, within an 8700-s run.
- E0a deviation. The registered E0a job 17264061 failed its own pre-run time check. It needed 7080 s and had 5369 s left of the registered --time 01:30:00 (pm-mire0a-17264061.out:470-471), so no run started. It was resubmitted as 17264093 at 14:53:08 with --time 02:15:00 and nothing else changed (sacct lines 9 and 13). Only the secondary W10 uses it. It is a single run with no SE. The sessions-based estimate depends on the window (about 0.99-1.17 λref, because synchronized cohorts arrive in waves), so quote the turns-based 1.062. The E0a COMMANDS.txt says 'seeds 0-2', but only seed 0 ran.
- Breadth. One engine (SGLang 0.5.22, FCFS with waiting-prefix refresh), one GPU type (A100 80GB PCIe), one model (Qwen2.5-7B-Instruct), one 300k pool, one synthetic workload family (exponential 5 s tool times, fixed tool and output lengths, no shared prefixes), one burst (200 sessions in [1200,1260) s), two rates and three seeds per cell. Seeds are shared: NOBURST uses the same base plans as BURST, and the same seed indices are used at both rates. These are not independent trials.
- NOBURST controls ran only at 1.65 λref (by design). That the burst caused the 1.35 λref trap rests on the 1.65 λref controls and on those runs' pre-burst follow-up hit of 1.00 (a post hoc verifier check).
- Co-location. The three decisive runs ran concurrently on nova22-gpu-2 on separate GPUs; the E0a ran on nova22-gpu-1. All-miss speed varies about 2-3% between GPUs, and 1.65 λref seed 2 was on the slowest one, which may explain part of its W5 miss. No M-rule is affected.
- Provenance details. The paper's '14:07:37' (Section 4.1 line 144, App. C line 177, Table 14 line 718) is wrong: GitHub's activity log gives 14:07:35 CST. That log records the push of commit bc81ee7 (branch creation), not of the tag object, which carries no push time. The repository is private, so readers see only the export. Erratum 18ac5e6 (prose: the note's writing time) reached GitHub at 14:49:22, 17 s after the smoke job was submitted and before the counted jobs. Erratum d8c49b7 (prose) was pushed at 16:19:36 during the runs; 'before any output was read' rests on the lead's record, since the cluster keeps no access times. The plan.csv files equal the frozen plans within the registered tolerance but are not byte-identical (tool_time_total_s off by at most 5.7e-14 s).
- The verifiers' artifact and mechanism checks (token rate, FIFO order, cohort lock-step, turn mix) are post hoc. If the paper cites them, it must label them so.
- The scorer's code and its docstring differ in ten places (STUCK window end, plan tolerance, run-end slack, call precedence, an undefined M2 counted as False, and others). None changes any boolean for these nine runs. The registration YAML still carries the generic E2 template's pass_rule and kill_conditions, which mention a CAPPED arm. The per-job 'summarize burst' outputs in the job logs (for example kill_strict) are not MIRROR results.
- Do not copy these documentation errors: the tagged note's 'about 16:00 CST' (corrected by 18ac5e6), '97.7-98.2%' (the actual range is 97.72-98.28%), W6 '270-330 s' (actual 287-334 s, d8c49b7) and the 1.4 backlog multiple (that is asymptotic; the plan-driven value is 1.65-1.95). Also the E0a COMMANDS.txt 'seeds 0-2', and the uncommitted notes/LOG.md evening entry's 'NOBURST completions 1.70-1.82' (the registered windows give 1.66-1.82).
- Space, which I measured on a scratch build of 7ea6eef. The main-text slack is about 4 lines at the foot of p. 11 (usable only by text before §7) plus about 3 lines at the foot of p. 12. The proposed core and fix entries fill p. 11 and leave p. 12 unchanged, so the build stays at 65 pages. Adding the two optional conclusion and Limitations sentences still ends the main text on p. 12, with about 1 line spare. A longer 4.1 outcome (+6 lines) pushed 'Use of AI tools' and 'Acknowledgments' to p. 13, so do not lengthen the 4.1 text. The Table 18 rows add one appendix page (66).
- Packaging. After the fill-ins only \repourl stays pending, so the strict packager needs ALLOW_PENDING=1, not 9. Copy results/theory/r16/fig_mirror.pdf (commit f641b02) to paper/figs/fig_mirror.pdf and add it to the upload list in ARXIV_METADATA.md. Fig. 4 must become a figure* at \textwidth: the figure is 6.6 in wide, and at column width its 7.5-pt labels would shrink to about 3.8 pt. Recount the comments field: 65 pages, or 66 with the Table 18 rows. Merge r16/mirror into the paper branch so the cited files exist.
- The abstract does not mention MIRROR. It is at 1917 of 1920 form characters. The optional abstract fill-in adds 2 characters but drops 'in two cells', 'alone' and 'backlogs rising or falling slowly'. Akshat should decide, and COORD/release-tools/count.py must confirm the count.
- Working files, for the lead and not for the paper, all under C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/mirror_verify/claims/. The exact fill-ins are in fillins.py, fillins_final.json and fillins_final.jsonl. The unified diff against 7ea6eef is mirror_fillins_7ea6eef.diff. The test build with every fill-in is main_with_mirror_fillins.pdf (66 pages, main text ending on p. 12, 0 overfull boxes, 1 pending marker). The numbers come from claims_numbers.py, claims_numbers.out and claims_numbers_burst.csv. Nothing in the worktree was changed. The uncommitted notes/LOG.md edit there (mtime 17:38) is the lead's, not mine.
not_shown:
- The asymptotic reversed premium (D/λmiss = 0.771 at 1.65 λref, 0.870 at 1.35 λref) and the H × Γ factorization: only a post-wave transient window was measured, the runs end at 8700 s, and at 1.35 λref completions were climbing toward the capacity by the end.
- That model F's renewal law, rather than any FIFO or age-structured model with a nearly deterministic turn count, is the right description: only the throughput-curve readings were registered as rivals.
- Wave timing to the calibrated ±5%: W5 failed once, and the standard workload's timing factor did not carry over.
- Generality to other engines (vLLM), GPUs (H200), models (Llama), pools, burst sizes, tool-time laws, real agent traces, step budgets other than 20, or other turn-count laws.
- Statistical strength beyond three seeds per cell on shared plans; no interval or significance statement is supported.
- Behaviour after 8700 s: whether the trap persists or completions stay below capacity.
- Any operational consequence for step-capped workloads, for example Corollary 3's drain threshold when D < λmiss: no cut, cap or shed arm was run on this workload.
- That the burst, and nothing else, caused the trap at 1.35 λref: that cell had no NOBURST control.
- A precise all-miss capacity for this workload: one E0a run, no SE, and estimator-dependent values of 1.00-1.10 λref.
- That the engine converges to model F, which the paper itself disclaims.
- Blindness in design: the workload was selected using the model's predictions.
fillins:
## paper/sections/v3_intro.tex:64-65 (contribution 2, \pending{MIRROR outcome}; core)
CURRENT: A further blind test, MIRROR, uses a step-capped
workload for which the theory predicts completions \emph{below} the all-miss capacity \pending{MIRROR outcome}.
PROPOSED: A further blind test, MIRROR, with a step-capped
workload for which the theory predicts completions \emph{below} the all-miss capacity, passed at both rates: all six trapped
runs completed 0.50--0.85~$\lref$, against a measured 1.06~$\lref$.
## paper/sections/v3_evidence.tex:41 (Table 2 ledger, MIRROR row, Result cell; stays 3 lines, so the float does not grow; core)
CURRENT: workload chosen with the model & \pending{MIRROR outcome} & \ref{app:blind}\\
PROPOSED: workload chosen with the model & pass at both rates, RENEWAL 3/3 each; late 0.50--0.85~$\lref$, below the measured 1.06; rejects only the throughput-curve readings & \ref{app:blind}\\
## paper/sections/v3_evidence.tex:148-149 (Section 4.1 outcome; +3.5 lines, the longest that fits; core)
CURRENT: Outcome:
\pending{MIRROR outcome}.
PROPOSED: Outcome:
PASS at both rates, RENEWAL in 3 of 3 seeds each: at 1.65~$\lref$, 0.06--0.09~$\lref$, waves at 4945--5089\,s,
then 0.50--0.61~$\lref$, below the measured capacity of 1.06~$\lref$. This rejects only the throughput-curve readings; a
secondary check, the calibrated wave time, missed in 1 of 6 runs.
## paper/sections/v3_app_blind.tex:137-142 (Fig. 4 box at about line 138 and caption marker at about line 141, replaced together because the float becomes figure*; first copy results/theory/r16/fig_mirror.pdf at f641b02 to paper/figs/fig_mirror.pdf; core)
CURRENT: \begin{figure}[htbp]\centering
\fbox{\parbox[c][0.5\columnwidth][c]{0.93\columnwidth}{\centering\footnotesize\pending{MIRROR figure,
\fpath{figures/r16/fig_mirror.py}: (a) completions per 300\,s bin after the burst, (b) the backlog}}}
\caption{MIRROR at 1.65~$\lref$: the standard workload's three committed traps (grey), model~F's frozen predictions for the
step-capped workload (blue, dashed) and the MIRROR runs (orange). \pending{MIRROR runs}}\label{fig:mirror}
\end{figure}
PROPOSED: \begin{figure*}[tbp]\centering
\includegraphics[width=\textwidth]{figs/fig_mirror.pdf}
\caption{MIRROR at 1.65~$\lref$: the standard workload's three committed traps (grey), model~F's frozen predictions for the
step-capped workload (blue, dashed) and the MIRROR runs (orange). (a)~Session completions per 300\,s bin, in $\lref$; dotted:
the model's all-miss capacities of the two workloads (1.004 and 1.046~$\lref$). (b)~Sessions in the system, 300\,s means.
Orange: the decisive cell's three BURST runs (jobs 17264055--57, seeds 0--2), all RENEWAL; the dashed lines were frozen under
tag \texttt{r16-mirror-reg} before any MIRROR job. Grey: jobs 17093390, 17093396 and 17093402
(\fpath{figures/r16/fig_mirror.py}).}\label{fig:mirror}
\end{figure*}
## paper/sections/v3_app_blind.tex:198 (App. C MIRROR outcome: paragraph, table and scope paragraph; core)
CURRENT: test came after Lu et al.'s paper. Outcome: \pending{MIRROR runs, per-seed calls and scores, W5--W10}.
PROPOSED: test came after Lu et al.'s paper. Outcome: PASS in both cells, RENEWAL in 3 of 3 seeds each (the registered scorer at the tag's code, reading the
predictions from the tag; \fpath{results/agentload_analysis_r16_mirror/20261105-173136/}). The nine runs (jobs 17264055--60 and
17264062--64, submitted at 14:50:52--53 CST and ended at 17:20:42--17:21:03) all count: each is the registered cell's, finished
at 8700\,s, is bound to the registration and was driven by its frozen plan (exact in sessions, turn counts and arrival times; tool
times within $10^{-13}$\,s). Measured, with model~F's frozen value in parentheses (rates in $\lref$; slopes in sessions/s, model~F's
and the quasi-static one):
\begin{center}\footnotesize
\resizebox{\columnwidth}{!}{%
\begin{tabular}{@{}c c c c c@{}}
\toprule
rate, seed & $[2400,3600)$ & wave (s) & $[6600,8700)$ & slope (F / QS)\\
\midrule
1.65, 0 & 0.070 (0.047) & 4996 (5195) & 0.592 (0.546) & 0.0767 (0.0789 / 0.0478)\\
1.65, 1 & 0.058 (0.070) & 4945 (5135) & 0.606 (0.599) & 0.0837 (0.0857 / 0.0441)\\
1.65, 2 & 0.093 (0.093) & 5089 (5157) & 0.499 (0.486) & 0.0935 (0.0930 / 0.0518)\\
1.35, 0 & 0.105 (0.000) & 4759 (4883) & 0.619 (0.599) & 0.0557 (0.0565 / 0.0274)\\
1.35, 1 & 0.093 (0.058) & 4673 (4802) & 0.739 (0.686) & 0.0504 (0.0534 / 0.0192)\\
1.35, 2 & 0.163 (0.070) & 4576 (4870) & 0.845 (0.726) & 0.0496 (0.0603 / 0.0278)\\
\bottomrule
\end{tabular}}
\end{center}
Every seed was called RENEWAL. All six BURST runs were stuck (hit fraction 0.000 over $[5700,8700)$\,s), and in each all 200
burst sessions completed by 8700\,s. The rules held with room in every run but one. The blackout windows held 5--14 completions, against M1's ceiling of 25.75;
the waves came 69--295\,s before model~F's times (1.7--8.0\% of the elapsed time, against M2's 15\%) and peaked at 2.8--3.5~$\lref$
per 300\,s bin at 1.65~$\lref$ (model~F 3.2--4.4); the backlog grew 1.61--1.90 times as fast as the plan's excess load at
1.65~$\lref$ (model~F 1.65--1.95), and every slope was nearer model~F's than the quasi-static one by at least 0.011\,/s. At
1.35~$\lref$, seed~2's 127 late completions were 0.7 below M3's ceiling of 127.7 (0.845 against 0.85): one more would have made that
seed MIXED, and the cell would still have passed, 2 of 3. Secondary checks: W5 held in 5 of 6 runs and failed at 1.65~$\lref$,
seed~2 (5089\,s against $F_{\mathrm{cal}}=4850\pm182$\,s); on this workload model~F's timing ran 2--8\% slow
($(\text{wave}-1200)/(F-1200)=0.92$--0.98), not the 8\% that the factor 0.9223 removes. W6 held in 3 of 3 seeds, with shifts of
237, 271 and 513\,s against model~F's 312, 334 and 287\,s. W7 held in 6 of 6 (served prompt $+0.2$ to $+2.6$\% of model~F's) and W8
in 6 of 6 (late completions 0.007--0.120~$\lref$ above model~F's). W9: the three NOBURST controls stayed good, with hit fraction
0.949--0.950, the ceiling $1-1/E[T]$ of this workload, completions of 1.66--1.82~$\lref$ in both windows and backlog slopes within
0.001\,/s of zero. W10: the E0a of this workload (one run, closed population 32, cache off) measured an all-miss rate of
1.062~$\lref$ turns-based (1.002 counting sessions), against the model's $\lmiss=1.046~\lref$, above every late value. The registered E0a job (17264061) failed its own
pre-run time check, which needed 7080\,s where 5369\,s of the registered 01:30:00 limit were left, so no run started; it was
resubmitted as 17264093 (14:53:08) with \texttt{-{}-time 02:15:00} and nothing else changed, and only W10 uses it.

What the pass shows. The registered alternatives are throughput-curve readings, which predict neither the blackout nor the wave, so
the pass rejects them but does not separate model~F from other models with its FIFO turn structure. M4 is not an independent fourth check: the plan
fixes the arrivals, so the backlog slope is the plan's arrival rate less a weighted completion rate over $[6000,8700)$\,s, nearly
what M3 measures over $[6600,8700)$\,s; the pass rests on three observations, the blackout, the wave and the lull. The late window measures
model~F's post-wave lull, not its asymptotic $D$ (0.81 and 0.91~$\lref$ at 1.65 and 1.35~$\lref$); at 1.35~$\lref$ a second
completion wave enters the window, and seed~2 completed 1.01~$\lref$ over $[7500,8700)$\,s (model~F 0.87). The NOBURST
controls ran at 1.65~$\lref$ only, the three decisive runs on one node (separate GPUs), and the test covers one engine, GPU,
model and workload family.
## paper/sections/v3_app_stampede.tex:635 (Table 12, tab:frozensum15, MIRROR row Outcome cell; core)
CURRENT: Blind in time; the workload was chosen after these predictions had been computed & \pending{MIRROR outcome} (\S\ref{sec:mirror})\\
PROPOSED: Blind in time; the workload was chosen after these predictions had been computed & PASS at 1.65 and 1.35 $\lref$, RENEWAL in 3 of 3 seeds each; all six stuck at zero hits, NOBURST good 3 of 3; at 1.65 $\lref$: 0.06--0.09 $\lref$ over $[2400,3600)$\,s, the wave at 4945--5089\,s, 0.50--0.61 $\lref$ over $[6600,8700)$\,s, below the measured all-miss capacity (1.062 $\lref$); the calibrated wave (W5) missed in 1 of 6 (\S\ref{sec:mirror})\\
## paper/sections/v3_app_stampede.tex:718 (Table 14, tab:ledger, MIRROR row: on-GitHub time corrected and jobs and outcome filled; core)
CURRENT: \texttt{bc81ee7} 11-05 14:07:08 & 14:07:37 & 9 runs and one E0a, \pending{jobs and outcome} (\S\ref{sec:mirror})\\
PROPOSED: \texttt{bc81ee7} 11-05 14:07:08 & 14:07:35 & 9 runs and one E0a, submitted 14:50:52--53 (17264055--64; the E0a, 17264061, failed its time check and ran as 17264093 at 14:53:08); pass at 1.65 and 1.35 $\lref$, RENEWAL 3 of 3 each (\S\ref{sec:mirror})\\
## paper/sections/v3_evidence.tex:144 (EXISTING sentence now wrong: push time; GitHub's log says 14:07:35)
CURRENT: pushed at 14:07:37 CST on 2026-11-05, before any job) calls
PROPOSED: pushed at 14:07:35 CST on 2026-11-05, before any job) calls
## paper/sections/v3_app_blind.tex:177 (EXISTING sentence now wrong: push time)
CURRENT: \texttt{bc81ee7}, tag \texttt{r16-mirror-reg}, pushed at 14:07:37 CST on 2026-11-05, before any job;
PROPOSED: \texttt{bc81ee7}, tag \texttt{r16-mirror-reg}, pushed at 14:07:35 CST on 2026-11-05, before any job;
## paper/sections/v3_app_blind.tex:150 (EXISTING sentence inconsistent with W10, which uses the E0a)
CURRENT: workload measures its all-miss capacity, which no rule uses.
PROPOSED: workload measures its all-miss capacity, which only the secondary check W10 uses.
## paper/sections/v3_evidence.tex:129-130 (Section 4.1; 'every trapped run ... above it' is contradicted two sentences later by MIRROR unless scoped; no extra line)
CURRENT: consistent
with every trapped run at a load above the all-miss capacity completing sessions above it
PROPOSED: consistent
with every trapped run of our workload at a load above the all-miss capacity completing sessions above it
## paper/sections/v3_intro.tex:37-38 (intro 'The question': an unscoped claim that trapped runs complete faster than the all-miss capacity is now false for MIRROR; no extra line)
CURRENT: Trapped runs at
loads above the all-miss capacity measured with caching disabled
PROPOSED: Trapped runs of our workload at
loads above the all-miss capacity measured with caching disabled
## paper/sections/v3_evidence.tex:55 (Section 4: MIRROR's trapped runs are a ninth cell, so 'every trapped run we have, in eight cells' is no longer true)
CURRENT: We test model~F on every trapped run we have, in eight cells:
PROPOSED: We test model~F on every trapped run of our workload, in eight cells:
## paper/sections/v3_evidence.tex:5 (Fig. 2 caption: MIRROR's six stuck runs are not in the figure; the caption does not grow)
CURRENT: \caption{Theorem~\ref{thm:trap} against every stuck run, as a function of the load
PROPOSED: \caption{Theorem~\ref{thm:trap} against every stuck run of our workload, as a function of the load
## paper/sections/v3_conclusion.tex:31-33 (Conclusion: 'the backlog grows at a fraction of the excess load' is false for the step-capped case, where model F gives 1.4 asymptotically and MIRROR measured 1.61-1.90; no extra line)
CURRENT: the backlog grows
at a fraction of the excess load (0.6 to 0.8 at our loads) and the turns served are young and short; for our workload sessions then
complete faster than the all-miss capacity.
PROPOSED: the backlog grows
at a fixed multiple of the excess load and the turns served are young and short; for our workload the multiple is 0.6 to 0.8
and sessions complete faster than the all-miss capacity.
## paper/sections/v3_app_stampede.tex:211 (App. E registered trap criterion (a): the general claim 'completes sessions faster than lmiss' is now contradicted by MIRROR)
CURRENT: Criterion (a) uses tokens because a trapped engine with a growing backlog completes sessions faster than $\lmiss$ while it prefills at the all-miss token rate
PROPOSED: Criterion (a) uses tokens because a trapped engine with a growing backlog completes sessions at a rate other than $\lmiss$ (faster for our workload, slower with a 20-step budget, \S\ref{sec:mirror}) while it prefills at the all-miss token rate
## paper/sections/v3_app_stampede.tex:932 (Table 19, tab:prov, MIRROR row; no marker, but the release checklist asks for the pull directories; this compact form avoids the 'Float too large' error the full paths caused)
CURRENT: MIRROR & \fpath{results/theory/r16/}, \fpath{analysis/r16_mirror.py}, \fpath{analysis/theory/icml/mirror_predict.py}, \fpath{configs/agentload_e2_mirror_k20.yaml} (tag \texttt{r16-mirror-reg}, \texttt{bc81ee7}; erratum \texttt{d8c49b7})\\
PROPOSED: MIRROR & \fpath{results/nova/r16_mirror_*_pulled_20261105-*/}, \fpath{results/agentload_analysis_r16_mirror/} (\texttt{f641b02}); \fpath{results/theory/r16/}, \fpath{analysis/r16_mirror.py}, \fpath{analysis/theory/icml/mirror_predict.py} (tag \texttt{r16-mirror-reg}, \texttt{bc81ee7}; erratum \texttt{d8c49b7})\\
## paper/sections/v3_app_stampede.tex:883-884 (Table 18, tab:timeline-r15: MIRROR rows per the release checklist; adds one appendix page, 65 to 66)
CURRENT: 11-05 08:35 & TOOLSLOW-D15 seeds 1 and 2 pulled; registered verdict at 08:36\\
\bottomrule
PROPOSED: 11-05 08:35 & TOOLSLOW-D15 seeds 1 and 2 pulled; registered verdict at 08:36\\
\addlinespace
11-05 14:07 & MIRROR (round 16): registration, frozen predictions and plans (\texttt{bc81ee7}, 14:07:08); tag \texttt{r16-mirror-reg}; on GitHub 14:07:35\\
11-05 14:49 & MIRROR cache-off smoke test submitted (17264039, 14:49:05); the erratum to the prediction note's writing time (\texttt{18ac5e6}, 14:24:49) reached GitHub at 14:49:22\\
11-05 14:50 & MIRROR jobs submitted in the registered order (17264055--64, 14:50:52--53); the E0a, 17264061, failed its pre-run time check (14:51:57) and was resubmitted as 17264093 (14:53:08) with a longer time limit\\
11-05 16:19 & errata to the prediction note's prose (\texttt{d8c49b7}, 16:19:32) pushed (16:19:36), during the runs and before any MIRROR output was read\\
11-05 16:59 & the E0a pulled (it ended at 16:27:41)\\
11-05 17:22 & the nine MIRROR runs pulled (they ended at 17:20:42--17:21:03); registered verdict at 17:31\\
\bottomrule
## paper/sections/v3_app_stampede.tex:866 (Table 18 caption, with the rows above)
CURRENT: \caption{Order of the round-15 events, 2026-11-05 (times CST; commit times by the committer, push times from GitHub's activity log, job times by Slurm's accounting, pull and verdict times from the pull records in \fpath{results/nova/r15_*_pulled_*}).}
PROPOSED: \caption{Order of the round-15 and round-16 (MIRROR) events, 2026-11-05 (times CST; commit times by the committer, push times from GitHub's activity log, job times by Slurm's accounting, pull and verdict times from the pull records in \fpath{results/nova/r15_*_pulled_*} and \fpath{results/nova/r16_*_pulled_*}).}
## paper/sections/v3_conclusion.tex:32-33 (OPTIONAL, applied after the conclusion fix above: the conclusion's one mention of MIRROR; fits on p. 12 together with the next item)
CURRENT: and sessions complete faster than the all-miss capacity.
PROPOSED: and sessions complete faster than the all-miss capacity, and with a 20-step budget slower, as a blind test found on the engine after a burst.
## paper/sections/v3_conclusion.tex:14 (OPTIONAL: Limitations, MIRROR's scope next to CUT's)
CURRENT: what singles out model~F against intermediate readings is post hoc. The from-empty runs
PROPOSED: what singles out model~F against intermediate readings is post hoc; MIRROR's rule rejects only the throughput-curve readings.
The from-empty runs
## paper/main.tex:57 (OPTIONAL, author's call: abstract; +2 form characters, so 1919 of 1920 expected; drops 'in two cells', 'alone' and 'backlogs rising or falling slowly'; not checked with count.py)
CURRENT: Blind in outcome, 4 runs in two cells trapped by a tool slowdown alone met 4 of 5 pre-set scores, and after arrival cuts the traps persisted, backlogs rising or falling slowly, as predicted.
PROPOSED: Blind in outcome, 4 runs trapped by a tool slowdown met 4 of 5 pre-set scores, cut traps persisted, and with a 20-step budget, trapped runs completed below the all-miss capacity, as predicted.
numbers_used:
- PASS at 1.65 and at 1.35 λref; RENEWAL in 3 of 3 seeds each: results/agentload_analysis_r16_mirror/20261105-173136/mirror_verdict.json: cells.1.65 and cells.1.35, fields calls and verdict
- six trapped runs; hit fraction 0.000; all six stuck: mirror_runs.csv: stuck=True, hit_eval=0.0, fu_hit_5700_8700=0.0 on the six burst rows
- 200 burst sessions completed by 8700 s: mirror_runs.csv burst_completed = 200 (burst rows)
- late 0.50-0.85 λref (all six); 0.592/0.606/0.499 and 0.619/0.739/0.845: mirror_runs.csv late_rate (min 0.49926 for 20261105-145240, max 0.84542 for 20261105-145244)
- 1.65 λref late 0.50-0.61: mirror_runs.csv late_rate on the 1.65 burst rows, 0.49926-0.60577
- blackout 0.06-0.09 at 1.65 λref; 0.070/0.058/0.093 and 0.105/0.093/0.163: mirror_runs.csv blackout_rate (1.65 rows 0.05825-0.09320; 1.35 rows 0.09320-0.16309)
- 5-14 blackout completions: mirror_runs.csv blackout_n (5 to 14)
- M1 ceiling 25.75 completions: BLACKOUT_MAX 0.30 (tagged analysis/r16_mirror.py:100) × lambda_ref 0.07153402 (mirror_runs.csv) × 1200 s
- waves 4996/4945/5089 s and 4759/4673/4576 s; range 4945-5089 at 1.65: mirror_runs.csv wave_time
- model F waves 5195/5135/5157 and 4883/4802/4870 s: mirror_runs.csv F_wave = tagged mirror_predictions.json cells.<mult>.seeds.<s>.burst_timing.median
- waves 69-295 s early; 1.7-8.0% of the elapsed time; M2 15%: mirror_runs.csv F_wave - wave_time (68.9-294.7 s), divided by (F_wave - 1200); WAVE_TOL_REL 0.15 (r16_mirror.py:101)
- wave peaks 2.8-3.5 λref per 300-s bin (model F 3.2-4.4): mirror_bins.json maxima of the three 1.65 runs (3.448, 3.541, 2.796); mirror_predictions.json cells.1.65.seeds.*.peak.rate_over_lam_ref (3.308, 4.380, 3.169)
- model F blackout 0.047/0.070/0.093 and 0.000/0.058/0.070; late 0.546/0.599/0.486 and 0.599/0.686/0.726: tagged mirror_predictions.json cells.<mult>.seeds.<s>.windows.blackout and late .completion_over_lam_ref
- slopes 0.0767/0.0837/0.0935 and 0.0557/0.0504/0.0496 /s: mirror_runs.csv slope
- S_F 0.0789/0.0857/0.0930 and 0.0565/0.0534/0.0603; S_QS 0.0478/0.0441/0.0518 and 0.0274/0.0192/0.0278: mirror_runs.csv S_F and S_QS (equal to mirror_predictions.json windows.slope.slope and qs_slope)
- backlog 1.61-1.90 times the plan's excess (model F 1.65-1.95): mirror_runs.csv slope/S_QS = 1.607, 1.899, 1.804 and S_F/S_QS = 1.653, 1.946, 1.794 (1.65 rows)
- nearer model F's slope by at least 0.011 /s: mirror_runs.csv: min over burst rows of |slope-S_QS| - |slope-S_F| = 0.0112 (20261105-145244)
- 127 late completions; ceiling 127.7; 0.845 against 0.85: mirror_runs.csv late_n 127 and late_rate 0.84542 (20261105-145244); LATE_MAX 0.85 (r16_mirror.py:100) × 0.07153402 × 2100 = 127.69
- W5: 5089 s against F_cal 4850 ± 182 s; 1 of 6 missed: mirror_runs.csv wave_time 5088.59, F_wave_cal 4849.94, W5_calibrated_wave False (20261105-145240 only); 0.05 × (4849.94 - 1200) = 182.50
- timing ratio 0.92-0.98; 2-8% slow: (wave_time - 1200)/(F_wave - 1200) from mirror_runs.csv = 0.9197-0.9826
- 8% bias; factor 0.9223; 0.9125-0.9327: tagged notes/PREDICTIONS_r16_mirror.md:119-125
- W6 shifts 237/271/513 s; model F 312/334/287 s: mirror_runs.csv wave_time(1.65) - wave_time(1.35) per seed; F_wave differences (311.7/333.6/287.2); mirror_verdict.json W6_order
- W7 +0.2% to +2.6%: (mirror_runs.csv P_served_5700_8700 - mirror_predictions.json windows.w5700.P_served_mean)/the latter: +2.61/+2.06/+0.20/+1.46/+1.65/+2.37%
- W8 +0.007 to +0.120 λref: mirror_runs.csv late_rate - mirror_predictions.json windows.late.completion_over_lam_ref
- NOBURST hit 0.949-0.950; ceiling 1-1/E[T]: mirror_runs.csv hit_eval 0.94932-0.94993 (NOBURST rows); mirror_predictions.json workload.ET 19.8111, giving 0.9495
- NOBURST completions 1.66-1.82 λref; slopes within 0.001 /s: mirror_runs.csv blackout_rate/late_rate on NOBURST rows (1.6642-1.8173); slope -0.00097 to +0.00015; mirror_verdict.json W9_controls_good
- measured all-miss rate 1.06 / 1.062 λref (turns-based): mirror_verdict.json W10_capacity.over_lambda_ref 1.06196 = calibration.json (results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results/agentload_analysis_miss/20261105-162735/) lambda_miss_turns_based 0.0759665 / lambda_ref 0.0715340
- 1.002 counting sessions: the same calibration.json lambda_miss 0.0716659 / 0.0715340
- one run, closed population 32: calibration.json n_runs 1; logs/pm-mire0a-17264093.out:578 (closed_n=32, --seed 0)
- model λmiss 1.046 λref; standard 1.004 λref: tagged mirror_predictions.json lambda_miss_model_over_ref 1.04609 and lambda_miss_standard_model_over_ref 1.00427
- asymptotic D 0.81 and 0.91 λref: mirror_predictions.json cells.1.65/1.35.asymptotics.D_over_lam_ref 0.80602 / 0.91021
- seed 2 at 1.35 λref: 1.01 λref over [7500,8700) s (model F 0.87): mirror_bins.json 20261105-145244, mean of the last four 300-s bins 1.014; mirror_predictions.json cells.1.35.seeds.2.completion_bins.rate_over_lam_ref, last four 0.874
- E0a check: 7080 s needed, 5369 s left, 01:30:00: results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/logs/pm-mire0a-17264061.out:470-471; tagged analysis/r16_mirror.py:393
- 17264093 at 14:53:08 with --time 02:15:00; failure at 14:51:57; E0a ended 16:27:41: provenance/sacct_cited_jobs_2026-11-05-r16.txt lines 9 and 13
- jobs 17264055-60, 17264062-64 (17264055-64 incl. E0a); submitted 14:50:52-53; ended 17:20:42-17:21:03: provenance/sacct_cited_jobs_2026-11-05-r16.txt lines 3-12; meta.json slurm_env.SLURM_JOB_ID
- decisive runs: jobs 17264055-57: meta.json slurm_env of 20261105-145227 / 145244-2 / 145240; sacct lines 3-5
- grey traces: jobs 17093390, 17093396, 17093402: meta.json slurm_env of results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/{20261024-155120,20261024-184132,20261025-000043}; figures/r16/fig_mirror.py:6
- on GitHub at 14:07:35 CST; commit 14:07:08: provenance/github_activity_2026-11-05-r16.json:153-159 (id 49158340380, 2026-11-05T20:07:35Z); provenance/push_times_2026-11-05-r16.tsv row 2
- smoke test 17264039 submitted 14:49:05: sacct line 2
- 18ac5e6 committed 14:24:49, on GitHub 14:49:22; d8c49b7 16:19:32 / 16:19:36: provenance/push_times_2026-11-05-r16.tsv rows 8-9
- E0a pulled 16:59; runs pulled 17:22; verdict 17:31: COMMANDS.txt line 1 of the two r16 pull directories; verdict directory name 20261105-173136
- tool times within 1e-13 s: provenance verifier's check_plans (maximum difference 5.68e-14 s in tool_time_total_s)
- f641b02: git log: the commit adding the pulls, the verdict and fig_mirror.pdf (on origin/r16/mirror)
- 20-step budget: configs/agentload_e2_mirror_k20.yaml max_turns 20; mirror_predictions.json workload.max_turns 20
- standard-workload traps 1.05-1.48 and 1.01-1.35 λref (already in the text): tagged note lines 34-35; recomputed by me from sessions.csv of the six standard E2 BURST runs: 1.048-1.479 and 1.012-1.351
disagreements_with_verifiers: None of the four reports disagrees with the registered verdict, with any call or with any M1-M4/STUCK boolean, and I found no reason to.

1. The blind recompute differs from the registered output in 22 of 252 values. All are definitional: the exact time-averaged backlog against 1-s samples (at most 1.2e-5 /s, against a smallest M4 margin of 0.0112 /s), the cached>50% hit metric against cached>0 (configs/agentload_analysis.yaml:18-19), a rounded λmiss constant (offset 3.1e-7 /s), and NaN against 0 for burst_completed in NOBURST. The registered values are what the tagged code computes (two verifiers reproduced the files byte for byte), so the registered output stands.

2. For the timing bias I quote (wave-1200)/(F-1200) = 0.920-0.983, which can be computed from the published table. The rules audit's registered per-session statistic is 0.924-0.982. Both round to 0.92-0.98.

3. No verifier raised these:
   - The uncommitted notes/LOG.md evening entry gives NOBURST completions of '1.70-1.82 λref in both windows'. The registered windows give 1.664-1.817 (late 1.664 at seed 1, 1.684 at seed 0). The artifact skeptic's '1.58-1.82' covers other windows.
   - App. C's existing 'which no rule uses' for the E0a contradicts W10.
   - The general sentences in the intro, the Section 4 lead-in, the Fig. 2 caption, App. E criterion (a) and the conclusion ('a fraction of the excess load') become false once MIRROR is in the paper. I give a zero-length scope fix for each.

4. The brief's 'about four spare lines on p. 12' is close but not exact. I measured about 4 lines at the foot of p. 11 (usable only by text before §7) and about 3 at the foot of p. 12. The fill-ins were sized and test-built to fit: main text still ends on p. 12, with no overfull boxes.