CHECKS RUN (all pass unless a finding below says otherwise)

1. Numbers in the diff. Every CUT-B, TOOLSLOW-D15, joint-CUT, abstract, Table 4, ledger, frozen-table and timeline number, count, hash and job ID matches the sources. The sources were PAPER_INPUT §3b/§4, BP/analysis/agentload_analysis_r15_cut/20261105-082543 (cut_verdict.json, cut_runs.csv), icml_cut_secondary_cut_b.json, AP/.../20261105-083614 (r15_verdict.json, r15_runs.csv), r15_t1_t2_scoring.json, icml_score_new_t2/score.json, toolslow_measured_r15_t2.json and toolslow_sim.json, cut_predictions.json, and sacct.
   - I recomputed some values from cut_n_grid.csv: N[3000,3300) is 172.5/146.4/158.1; the naive reading reaches n_b at 7245/5656/6739 s and the D_pre drain at 5437/4877/7598 s; N at 8700 s is 139.8/77/89, against model F's 138.6/79.0/93.8.
   - Timeline rows match the pull and analysis directory names and the COMMANDS.txt pull times: 06:51 = cut_b0_…065100; 08:23 = cut_b12_…082300 and a2_s0_…082300; 08:25 = 20261105-082543; 08:35 = a2_s12_…083500; 08:36 = 20261105-083614.
   - Note: PAPER_INPUT moved from 4a37e25 to 1d32859 while I was auditing. Only the Brier line changed (Brier is not used in the draft), plus new Verification text (see S2).
2. R12, recomputed with my own code from trap_check.json:
   - The file holds 70 runs: 57 E2-protocol runs in 20 groups and 13 E0b runs. Group and run lists map 1:1. All 57 have follow-up hit 0 over [5700,8700). The script uses all of them; nothing is dropped. The 36 Table 1 runs are the 10 registered cells.
   - E2 slope/α: mean 0.9912, median 1.0556, per run −0.0040 (vLLM 1.35, seed 1) to 1.6165 (LPM r0 1.35, seed 0). Quasi-static (λ−λmiss)/α: 1.3588–1.5919.
   - From-empty runs: 11 of 13 are above α, by 6.45% to 34.98%. The two below are H200 300k 1.4 (0.797) and the 600k pool at 5.0 (0.995). Mean 1.157, median 1.175, quasi-static 1.270–1.572.
   - All 10 Table 1 cells and all 13 App. B rows match at two decimals. The committed backlog_over_alpha.json equals my values exactly (maximum difference 0). The draft's sentences are correct.
3. Abstract: there is no count.py in the reframe worktree. My own plain-text count is 1916 characters (limit 1920, margin 4), identical to the ARXIV_METADATA form text. COORD/release-tools/count.py also gives 1916.

MUST-FIX

M1. paper/sections/v2_intro.tex:71
- Problem: "a flat backlog fits CUT-A as well" is false. Measured S was +0.0040/−0.0022/+0.0029, so S = 0 misses by 0.0022–0.0040 /s, against model F's ≤0.0004. What fits as well is completions at the nominal cut rate (errors 0.00016/0.00008/0.00047).
- Evidence: v2_validation.tex:202 "completions equal to the nominal cut rate fit as well as model~F".
- Replace with: "(completions at the nominal cut rate fit CUT-A as well over $[3000,8700)$\,s)"

M2. paper/main.tex:57 (also the ARXIV_METADATA.md form text and the NUMBERS.md abstract row)
- Problem: "4 runs … met pre-set tolerances" overclaims. The stuck TOOLSLOW-D15 run missed S5's pre-set 0.01 /s tolerance (0.0104). The claim held for the 3 TOOLSLOW-W runs alone, not for 4.
- Evidence: v2_validation.tex:151 "its S5 plug-in missed the 0.01\,/s tolerance by 0.0004\,/s".
- Replace with: "Blind in outcome, 4 runs trapped by a tool slowdown alone met pre-set pooled tolerances, and after arrival cuts the traps persisted or drained slowly, as predicted." This counts 1910 form characters.

SHOULD-FIX

S1. Paper-branch provenance/push_times_2026-11-05.tsv rows 3, 8, 10, 12 and provenance/sacct_cited_jobs_2026-11-05{,_utc}.txt lines 10–15. These files are cited at appendix.tex:345.
- Problem: the branch carries the 07:10 export. Jobs 17256870–75 show as RUNNING with end Unknown, and the TSV has no end time for the CUT-B and D15 rows. The source of truth (r15/tonight 4a37e25) has COMPLETED 0:0, with ends from 06:50:40 to 08:33:38.
- Evidence: "17256873|pm-tsd15|…|2026-11-05T05:52:28|Unknown|RUNNING|0:0|nova22-gpu-3"
- Fix: git checkout 4a37e25 -- provenance/push_times_2026-11-05.tsv provenance/sacct_cited_jobs_2026-11-05.txt provenance/sacct_cited_jobs_2026-11-05_utc.txt (the github_activity and tag_refs files are already identical).

S2. paper/sections/v2_validation.tex:223–224
- Problem: the current PAPER_INPUT (1d32859, Verification) asks for one clause the draft lacks: with a quasi-static comparator, CUT-B seed 0 would have favoured it, and the verdict would still pass.
- Evidence: "seed 0 would have been QS-FAVOURED (|S − S_qs| = 0.00036 < |S − S_theory| = 0.00099)"
- Replace with: "A reading in which the trap completes sessions at the all-miss capacity, not a registered comparator for this arm, fits the slopes about as well: had it been one, seed~0 would have favoured it (error 0.00036 against model~F's 0.00099\,/s), and CUT-B would still have passed, 2 of 3."

S3. paper/sections/v2_validation.tex:80–81 and paper/sections/v2_app_trapdata.tex:45
- Problem: "(not checked)" is contradicted by trap_check.json, the file R12 reads. Its arrival_rate_window puts all 13 from-empty windows 3.8–13.1% above nominal, and R12's α uses the nominal rate.
- Evidence: "which may reflect window arrival rates above nominal in these single seed-0 runs (not checked;"
- Replace with: "…in these single seed-0 runs (3.8--13.1\% above in all 13, by \fpath{trap_check.json}; Appendix~\ref{app:trapdata})". In App. B, replace with "(each is a single seed-0 run, with window arrivals 3.8--13.1\% above nominal)".

S4. paper/sections/v2_theory.tex:7–8
- Problem: the range 1.10–2.40 refers to all 70 stuck runs, but 0.99 is the mean over the 57 E2 runs. Over all 70 the mean is 1.02 and the median 1.09.
- Evidence: "every stuck run of the retrospective check completes sessions at 1.10--2.40~$\lref$, and the backlog grows on average at model~F's $\alpha$ (mean ratio 0.99)"
- Replace with: "…at 1.10--2.40~$\lref$, and over the 57 E2-protocol runs the backlog grows on average at model~F's $\alpha$ (mean ratio 0.99), not at the excess load"

S5. paper/sections/limitations.tex:9 and paper/sections/appendix_supp.tex:118
- Problem: the full appendix list of the model's misses omits the TOOLSLOW-D15 fluid miss.
- Evidence: "would trap the engine in every seed; it trapped 1 of 3."
- Fix in limitations.tex: after that sentence, insert "Its fluid verdict for TOOLSLOW-D15, a 15\,s slowdown for 900\,s at 1.65~$\lref$, was again a trap in every seed; one run of three trapped, as the calibrated simulator predicted seed by seed."
- Fix in appendix_supp.tex: replace "and the TOOLSLOW prediction of a trap in every seed at $\delta=30$\,s did not (1 of 3)" with "and the TOOLSLOW predictions of a trap in every seed, at $\delta=30$\,s and in TOOLSLOW-D15, did not (1 of 3 each)".

NIT

N1. v2_validation.tex:85
- Problem: after R12 the section's backlog figures are ratios to α, so the bare 0.63–0.64 reads as slope/α.
- Evidence: "reproduced the backlog slope at 300k numerically (0.63--0.64)"
- Replace with: "(0.63--0.64 of $\lambda-\lmiss$)"

N2. v2_validation.tex:73–74
- Problem: "with the plans' window arrivals" reads as if α were evaluated at window arrivals; the script uses α at the nominal rate.
- Evidence: "(per run 0.00 to 1.62, with the plans' window arrivals)"
- Replace with: "(per run 0.00 to 1.62, varying mostly with the plans' window arrivals; $\alpha$ at the nominal rate)"

N3. v2_validation.tex:152
- Problem: five runs were trapped by a tool slowdown alone (r14's 900 s arm, seed 2, is among the 57); the four are the blind ones.
- Evidence: "Across the four runs trapped by a tool slowdown alone"
- Replace with: "Across the four blind runs trapped by a tool slowdown alone"

N4. appendix.tex:349 (caption)
- Problem: the new pull and verdict times have no stated source.
- Evidence: "job times by Slurm's accounting)"
- Replace with: "job times by Slurm's accounting, pull and verdict times from the pull records in \fpath{results/nova/r15_*_pulled_*})"

N5. paper/NUMBERS.md:60 and :85 are stale.
- Evidence: "seeds 1 and 2 discriminate; outcome pending" and "three TOOLSLOW-W runs in one cell".
- Line 60: replace "outcome pending" with "outcome NO-TRAP (PI3 rows)".
- Line 85: replace with "four runs trapped by a tool slowdown in two cells (three TOOLSLOW-W, jobs 17256674-76; one TOOLSLOW-D15, job 17256873) and six CUT runs (jobs 17256867-72) | 8 | PI1, PI3; r15-reg (e05a262), r15-cut-reg (11b0e4e)".

My scripts and outputs are in C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/final_review_54d3529/ (r12_recompute.py, r12_rows.json, abs_count.py, abs_plain.txt).

JUDGEMENT
Every number, time, hash and job ID the diff adds matches the sources, R12 reproduces exactly with nothing dropped, and the abstract is 1916/1920.
Fix M1 and M2 (two sentences that contradict the paper's own data) and S1 (stale provenance on the branch) before release; the rest are clarity and consistency fixes.