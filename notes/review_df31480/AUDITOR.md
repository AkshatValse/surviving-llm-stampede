Draft root: C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/paper/ (cited as main.tex and sections/*.tex, at df31480; the built main.pdf matches the source). Sources root: C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/tonight/. The tag extracts and pdftotext output are in C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/review_df31480/. Nothing in either worktree was modified.

1. MUST-FIX — sections/v2_intro.tex:26-28; sections/v2_evidence.tex:33-34 (Table 4 rows at v2_evidence.tex:27-28)
Problem: The priority and independence claims cover Table 4, and Table 4 now includes TOOLSLOW-W and CUT. Both tests were registered and run on 2026-11-05, after Lu et al. appeared.
Evidence: The draft says "The registered experiments of §6 were designed, registered and run before it appeared" and "a phenomenon that we tested, independently of Lu et al., under registered rules (Table 4)". Against that:
- Lu et al. appeared 2026-11-02 (appendix.tex:458).
- r15-reg was pushed 03:18:36 and r15-cut-reg 03:54:49 on 2026-11-05 (provenance/push_times_2026-11-05.tsv).
- The trap-state predictions' author read "the Lu et al. text" (icml-trap-pred:notes/PREDICTIONS_icml_trap.md:6-7).
Fix: In the intro, write "The registered experiments of §6 up to SHED and TOOLSLOW were designed, registered and run before it appeared; the theory of §2 and the blind tests of §3 (TOOLSLOW-W and CUT, registered on 2026-11-05) came afterwards." In §6, write "...under registered rules (Table 4); every test above TOOLSLOW-W was registered and run before Lu et al. appeared." Optionally add a midrule in Table 4 labelled "registered after Lu et al.".

2. MUST-FIX — sections/v2_conclusion.tex:11-12; v2_intro.tex:59; Table 4 (no row); v2_validation.tex (no bullet after :130)
Problem: The second r15 registration, TOOLSLOW-D15 (T2: +15 s on [1200,2100) at 1.65 λref), appears nowhere in the draft. Its FILLED registration is in the same r15-reg commit, its jobs 17256873–75 were submitted after both tags, and the frozen notes call it the model-discriminating cell. As a result, "Only..." and "Two blind tests followed" are false, and a registered test is missing from the file.
Evidence: The draft says "Only the runs submitted after tag icml-trap-pred test it blind: three TOOLSLOW-W runs in one cell, and the six CUT runs." Against that:
- push_times_2026-11-05.tsv row "TOOLSLOW d15 1.65x 17256873 2026-11-05 03:57:14".
- e05a262:configs/agentload_prereg_2026-11-05_toolslow_d15_165.yaml has "status: FILLED".
- PREDICTIONS_r15.md:198-199: "T2 seeds 1 and 2 are the discriminating runs". Lines 244-248 say STUCK T2 runs are scored by S1–S5.
- PAPER_INPUT_r15.md:51-52 and :316 list T2 as pending.
Fix:
- Add a Table 4 row: "TOOLSLOW-D15 | 300k, 1.65, no burst; tool calls 15 s longer for 900 s; traps iff stuck in ≥2 of 3 | pre-registered | \pending{outcome}".
- Add a pending bullet in §3 with the frozen calls: simulator S/G/G → NO-TRAP; pred2 fluid TRAPS; pred2 per-seed P(TRAPS) 0.58.
- In §8, write "three TOOLSLOW-W runs, three TOOLSLOW-D15 runs (\pending{outcome}) and the six CUT runs".
- In the intro, write "Three blind tests followed (one pending)".

3. MUST-FIX — sections/v2_validation.tex:175-180; v2_conclusion.tex:38-39
Problem: Persistence is listed as one of the results that "single out model F", and as half the "support for the corollary". But every reading the paragraph names also predicts STUCK to 8700 s.
Evidence: The draft says "Three results single out model F. ... And all three traps persisted to the end of the run." I recomputed the projections from cut_n_grid.csv, starting from N over [3000,3300) = 183/167/175 and using each reading's slope. Projected N(8700) is:
- 129/51/119 at D_trap;
- 266/216/251 at λref;
- 205/155/190 at the nominal cut rate;
- 198/133/185 at the midpoint.
All of these are far above n_b = 32.7 (PREDICTIONS_icml_cut.md:21,146). Only a drain at the pre-cut completion rate D_pre (cut_runs.csv: 0.122/0.118/0.087) reaches n_b, near 6300 s in seeds 0 and 1 (PREDICTIONS_icml_cut.md:148-151).
Fix: In §3, write "Two results single out model F: [late window] [completion rate]. All three traps also persisted to 8700 s, which each constant reading above also predicts. Persistence rules out only a drain at the completion rate seen just before the cut (1.65–1.70 λref in seeds 0 and 1), which would have reached the onset near 6300 s." In §9, write "...the support for the corollary comes from the late backlog, which in seeds 0 and 2 regrew at model F's frozen slopes (a post-hoc comparison)".

4. SHOULD-FIX — sections/v2_validation.tex:178-180
Problem: The completion-rate result is presented as a registered result that singles out model F. In fact its 0.004 /s cut is post hoc, and at the registered tolerance of ±0.006 /s a single constant rate also fits.
Evidence: The draft says "a registered secondary prediction, varied with the plan as model F said ..., and no single constant rate comes within 0.004 /s of all three seeds". Against that:
- The tolerance is ±0.006 /s (PREDICTIONS_icml_cut.md:143-144,177-178).
- A constant 0.0800 /s misses the measured 0.0753/0.0847/0.0787 by at most 0.0047 (cut_runs.csv; PAPER_INPUT_r15.md:253-256: "do not say 'no constant fits'").
Fix: Append "...although the best constant (0.080 /s) stays within the registered ±0.006 /s, so this comparison is also post hoc."

5. SHOULD-FIX — sections/v2_conclusion.tex:38-39; v2_control.tex:30-32 (compare v2_validation.tex:176, v2_conclusion.tex:13-14, v2_intro.tex:63)
Problem: Each section credits a different set of results with singling out model F:
- §3 names three results.
- §8 names only the late window, "after the fact".
- The intro names only the late backlog, "post-hoc".
- §9 names persistence and the late backlog, with no post-hoc caveat.
- §5 reports CUT-A with no narrowing at all.
Evidence: §9 says "the support for the corollary comes from the persistence and from the late backlog, which followed model F's frozen slopes". §5 says "left all three CUT-A traps in place to the end of the run". PAPER_INPUT_r15.md:250 says "this comparison was not registered as a test, so report it as post hoc".
Fix: Use one sentence everywhere: "the registered rule rejects only the constant-throughput readings; the late-window slopes, scored post hoc against frozen values, single out model F". Append "(the registered rule rejects only constant-throughput readings; §3)" after v2_control.tex:31.

6. SHOULD-FIX — sections/v2_conclusion.tex:14-17
Problem: The main text reports only the successful same-plan replication of the from-empty edge. The failed fresh-seed replication, where the registered rule was not met, appears only in the appendices.
Evidence: The draft says "The from-empty runs are single runs per rate; in an exploratory replication ... three runs on each of two arrival plans reproduced both originals". Against that, appendix_supp.tex:116 and frozen.tex:19 report that fresh seeds were "stable at both 2.0 and 2.5 λref ... the replication rule ... is not met", with the edge at 2.665–2.726 λref in realized rates (limitations.tex:7).
Fix: Write "The from-empty runs are single runs per rate, and at 300k the seed-0 bracket did not replicate on fresh seeds (2.5 λref stable in 3 of 3; in realized rates the edge lies between 2.665 and 2.726 λref). In an exploratory replication on two plans chosen because their outcomes were known, three runs each reproduced both originals..."

7. SHOULD-FIX — sections/v2_intro.tex:59-61
Problem: The contribution drops the 1800 s duration and the design history. It reads as if a pre-registered 30 s slowdown traps 3 of 3, but the pre-registered 900 s one trapped 1 of 3 and its rule was not met.
Evidence: The draft says "A pre-registered 30 s tool slowdown with no burst trapped the engine in 3 of 3 runs". Against that, v2_evidence.tex:26 says "+30 s trapped 1/3", and PAPER_INPUT_r15.md:22-23 says it was "designed after the r14 30 s TOOLSLOW arm trapped 1 of 3 ... blind in outcome only".
Fix: Write "A pre-registered 30 s tool slowdown lasting 1800 s with no burst, designed after a 900 s one had trapped 1 of 3, trapped the engine in 3 of 3 runs..."

8. SHOULD-FIX — sections/v2_validation.tex:127-130
Problem: T1's frozen exploratory comparisons are not reported, although the frozen scoring plan committed to reporting larger errors.
Evidence: The draft says only "Every model we froze ... predicted this outcome, so the cell tests the trap-state law on a trap entered with no burst". Against that:
- PREDICTIONS_r15.md:215-216: "Larger errors on T1 / T2 are reported as such".
- Outstanding requests at 3300 s were 65/67/64 against the simulator's 57/62/70, missing the frozen "within 5" reference by 8 and 6 (PAPER_INPUT_r15.md:70,75).
- pred2's plan walk undercounts sessions alive at 3000 s by 7–18 (PAPER_INPUT_r15.md:76).
Fix: Add "Of the frozen exploratory measures, t_fu150 (1950/1950/2100 s) and sessions alive at 2100 and 3000 s met the reference accuracy. Outstanding requests at 3300 s missed it by 8 and 6 in seeds 0 and 2, and pred2's queue-free plan walk undercounted sessions alive at 3000 s by 7–18."

9. SHOULD-FIX — appendix.tex:171,176,411; frozen.tex:5,38; frozen_app.tex:7; method.tex:16
Problem: The record tables claim to be complete but contain nothing from round 15. method.tex defines "registered" by reference to the ledger, so TOOLSLOW-W's and CUT's "pre-registered" status has no ledger entry and no cited push-log export.
Evidence: appendix.tex:176 says "Every registration, in order." frozen_app.tex:7 says "This appendix gives every prediction frozen for the later tests". appendix.tex:411 cites only push_times_2026-11-01.tsv and the 258-job sacct export. Yet provenance/push_times_2026-11-05.tsv, github_activity_2026-11-05.json and sacct_cited_jobs_2026-11-05.txt are already in the draft branch.
Fix:
- Ledger (times in CST): 2026-11-05_toolslow_d30w1800 and _d15_165 at e05a262 03:17:48, on GitHub 03:18:36; _cut_a115 and _cut_b085 at 11b0e4e 03:54:28, on GitHub 03:54:49. Also note the EXPLORATORY configs/r15_edge_replicate.yaml.
- Frozen-prediction tables: add rows for TOOLSLOW-W, CUT, REPLICATE-EDGE and TOOLSLOW-D15.
- Timeline: icml-trap-pred 00:24:47, 24b5e13 01:09:25, icml-cut-pred 02:25:43, and fdb80c9 03:34:35 (777 s after the TOOLSLOW-W submit).
- Appendix prov: cite the 11-05 exports.

10. SHOULD-FIX — appendix_supp.tex:109
Problem: This sentence is out of date and contradicts the CUT sentence later in the same paragraph.
Evidence: The draft says "the registered SHED test ..., the only real runs that lowered the rate after a trap, stopped arrivals entirely". But CUT-A cut arrivals to 1.15 λref at 2400 s inside a trap (jobs 17256867–69; cut_runs.csv).
Fix: Delete ", the only real runs that lowered the rate after a trap,".

11. NIT — sections/v2_validation.tex:178
The draft says "each missed by at least 0.004 /s". The nominal-rate (zero-drift) reading misses seed 0 by 0.00398: 0.0070531 − (0.0853333 − 0.0822641), from cut_verdict.json sign_slope and cut_predictions.json w5700.lam_plan.
Fix: "each missed by about 0.004 /s or more (smallest 0.0040, rounded: the nominal cut rate in seed 0)".

12. NIT — sections/v2_validation.tex:168 and :179
The draft calls them "registered secondary predictions". The CUT registration (11b0e4e: configs/agentload_prereg_2026-11-05_cut_a115.yaml) contains none of them. They were declared only in PREDICTIONS_icml_cut.md:177-178, so by method.tex:16's definition they are frozen, not registered.
Fix: "the secondary predictions frozen with model F (tolerances declared in the prediction note, not part of the registered rule)".

13. NIT — sections/v2_validation.tex:154-158
The draft says the rule "differs from the draft rule ... in four ways". The registration's RULE HISTORY also lists "CUT-B adds S < 0". The note's draft rule (PREDICTIONS_icml_cut.md:173-176) already counted an unstuck run as not theory-favoured.
Fix: "in five ways ... and CUT-B adds S<0 in at least 2 of 3 (stricter); the note already counted an unstuck run as not theory-favoured, and the rule also counts it toward a fail".

14. NIT — sections/v2_validation.tex:136
The draft says "CUT-A ... does not drain". Model F's own seed-1 slopes are −0.0026 and −0.0036 /s. The run's backlog fell 175→155 and cut_runs.csv labels it "draining".
Fix: "does not clear".

15. NIT — sections/v2_validation.tex:162-171
A limitation listed in the sources is omitted: "The model's backlog level runs 5–10 sessions high, e.g. 186 against 176" (PAPER_INPUT_r15.md:265; LOG.md:1105).
Fix: Add "Model F's backlog levels ran 5–10 sessions high (186 against 176 over [2100,2400) s in seed 0)."

16. NIT — sections/v2_theory.tex:7
The draft says "every stuck run completes sessions at 1.10–2.40 λref". The stuck CUT-A seed-0 run completed 0.0753 /s = 1.05 λref over [5700,8700) (cut_runs.csv).
Fix: "every stuck run of the retrospective check (§3) completes sessions at...".

17. NIT — main.tex:57 and sections/v2_conclusion.tex:35
The draft says "Blind, it matched 3 runs" and "and blind on three runs". T1 is blind in outcome only, and the S1–S5 tolerances were set on committed runs (PAPER_INPUT_r15.md:22-25).
Fix: In §9, "and, with predictions frozen before the runs, on three runs...". In the abstract, if space allows, "Blind in outcome, it matched...".

18. NIT — frozen.tex:19
The draft says "H2 does not describe same-plan replicates". This drops the frozen qualifier "not as a refutation of F2's cell-level escape probability" (PREDICTIONS_r15_edge.md:87).
Fix: Append "(not a refutation of its cell-level escape probability)".

19. NIT — sections/v2_evidence.tex:47-48; v2_entry.tex:11 and :70-71
The draft says "seen by the first author before the model's freeze". The fact is that the operating agent saw n=16–32 and showed them to the first author (frozen_app.tex:29; limitations.tex:11). "No blind simulator prediction" for the H200 appears only in the appendices.
Fix: "seen by the cell's operating agent and the first author before the freeze; no blind simulator prediction was made for this cell".

20. NIT — sections/v2_entry.tex:55-57
The draft lists "both basin tests' rules" among the held out-of-sample predictions, but BASIN-1's are blind by access only: the n=100 runs had ended and the n=25 runs had started before the push (frozen.tex:46; appendix.tex:286).
Fix: "both basin tests' rules (BASIN-1's blind by access only)".

21. NIT — method.tex:16
The draft says vLLM's registration "reached GitHub after its jobs were submitted, before any could have ended". That is weaker than the recorded fact, "after two of its jobs had started" (v2_evidence.tex:46; appendix.tex:185).
Fix: Use the latter wording.

22. NIT — sections/v2_related.tex:16-17; v2_control.tex:26-27
The draft says "(Corollary 3, for an FCFS engine on which every turn misses ...)" and "the cut must go below λmiss". These read as engine results, but the corollary is proved only in model F.
Fix: "(Corollary 3, proved in model F, our idealization of an FCFS engine on which every turn misses; CUT-A is consistent with it)".

23. NIT — sections/v2_app_trap.tex:294
The draft says "An operator who sets arrivals between λmiss and the trapped throughput sees at most a brief dip, then renewed growth." That holds for the Poisson-average fluid only:
- Model F's per-seed CUT-A seed 1 declines all run.
- 10% of random plans give a negative slope (PREDICTIONS_icml_cut.md:57-59,200-203).
- The engine's seed 1 fell 11.5%.
Fix: Prefix "In the fluid," and add "; on one arrival path the backlog can keep falling slowly for the whole run (CUT-A seed 1)".

24. NIT — sections/v2_validation.tex:128-130
The TOOLSLOW-W reading ("the cell tests the trap-state law on a trap entered with no burst") omits the caveat frozen with TOOLSLOW: "it would not separate the longer gap from the capacity loss and the larger population" (frozen_app.tex:118).
Fix: Append that sentence for TOOLSLOW-W.

Overall judgement:
Every TOOLSLOW-W, REPLICATE-EDGE and CUT-A number, time, hash, job ID and verdict I checked matches the verdict files, the frozen JSON and the push log, except one rounding (0.00398 quoted as "at least 0.004"); the vLLM, BASIN-1, rescue, LPM-INF, pool and H200 honesty facts survive, some only in the appendices.
The serious problems are in the wording around those numbers: the priority claim now covers two post-Lu et al. tests, the registered TOOLSLOW-D15 test (T2) has vanished, and §3 and §9 count persistence and a post-hoc 0.004 /s cut as evidence that singles out model F.
After findings 1–3, one consistent post-hoc caveat, and round 15 added to the ledger, timeline and frozen-prediction tables, the narrowed CUT-A reading and the TOOLSLOW-W result are defensible.