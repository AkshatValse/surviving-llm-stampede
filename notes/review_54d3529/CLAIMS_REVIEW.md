FLAGGED ITEMS (worktree reframe-draft-211a57 at 54d3529)

(1) "met pre-set tolerances": yes, an overclaim. S5 is a pre-set per-run tolerance and it failed in 2 of the 4 runs: wrong side in TOOLSLOW-W seed 1, and closeness missed by 0.0004 /s in TOOLSLOW-D15 seed 0. MUST-FIX (#1).

(2) "as predicted" for the cuts: not an overclaim by itself. Model F's frozen per-seed predictions held: all six runs stuck, slopes within 0.001 /s, and CUT-A's late-window sign as predicted. Both registered rules passed. The phrase does not say the cuts singled out model F. Keep it once "drained slowly" is fixed. Do not strengthen it to "confirming Corollary 3", because the evidence against intermediate readings is post hoc.

(3) "drained slowly" for CUT-B: yes, an overclaim. No CUT-B trap drained: all three were still stuck at 8700 s with 77–140 sessions, and only the backlog fell. Two sentences earlier the abstract uses "drains" to mean "empties". MUST-FIX in the abstract (#2), SHOULD-FIX elsewhere (#4).

(4) Youth-premium confound: not an overclaim. The sign holds even after removing the faster-engine effect, in every run.
- I computed this from results/theory/icml/trap_check.json: completions/λref divided by each run's measured token-rate ratio (uncached tok/s over the cell's E0a rate, 0.948–1.124).
- The result is 1.08–1.81 across all 57 E2-protocol runs. The minimum is BASIN-60 seed 1: 1.118 λref at a token ratio of 1.034.
- That is above the 2% gap between the turn-based and token-based λref.
- So a faster congested engine explains part of the excess over D, as the body already says, not the excess over λref. Keep the abstract clause and add the check to the body (#9).

Other checks:
- Corollary 3's novelty: the abstract claims none. The intro ("what is new about it is its test on the engine") matches §2. Only v2_related overreaches, and it is stale (#13).
- "Before Lu et al." scope: the intro, Table 4 ("Registered on 2026-11-05, after Lu et al. appeared"), the timeline and the conclusion agree. No issue.
- "Blind": qualified as "blind in outcome" everywhere, and the calibrated tolerances and post-prediction CUT rule are disclosed. No issue.

FINDINGS

MUST-FIX

1. paper/main.tex:57
- Problem: the abstract says the 4 tool-slowdown runs met pre-set tolerances; S5 failed in 2 of the 4.
- Evidence: v2_validation.tex:152-153 "S1--S4 pass in both cells, and S5 is close in 3 of 4 and on the correct side in 3 of 4".
- Replacement: "met pre-set tolerances" → "met 4 of 5 pre-set scores".
- Also update the form twin and count in paper/ARXIV_METADATA.md:17-23 and paper/NUMBERS.md row 87.

2. paper/main.tex:57
- Problem: "the traps persisted or drained slowly" says CUT-B's traps drained. None did.
- Evidence: v2_validation.tex:219 "All three runs were still stuck at 8700\,s (hit 0.000 over $[5700,8700)$\,s; 140, 77 and 89 sessions present".
- Replacement: "the traps persisted or drained slowly, as predicted" → "the traps persisted, backlogs rising or falling slowly, as predicted".

3. paper/sections/v2_intro.tex:71
- Problem: "(a flat backlog fits CUT-A as well...)" is false.
  - A flat backlog (S=0) misses the measured slopes (+0.0040, −0.0022, +0.0029 /s) by 0.0022–0.0040 /s.
  - Model F misses by 0.0001–0.0004 /s, and run-to-run jitter is 0.0001–0.0005 /s.
  - The reading that does fit is constant completions at the nominal cut rate: λ'_plan − 1.15λref = +0.0039, −0.0021, +0.0025, errors 0.0002/0.0001/0.0005, using the frozen lam_plan values.
- Evidence: v2_validation.tex:202 "over $[3000,8700)$\,s, completions equal to the nominal cut rate fit as well as model~F".
- Replacement: "(a flat backlog fits CUT-A as well over $[3000,8700)$\,s)" → "(constant completions at the nominal cut rate fit CUT-A as well over $[3000,8700)$\,s)".

SHOULD-FIX

4. "Drained" used for CUT-B on the engine, in several places.
- Problem: v2_intro.tex:80 uses "drained" for CUT-B, where the trap persisted, and for SHED, where it emptied, in the same sentence.
- Evidence: "registered cut to 0.85~$\lref$ drained it only slowly (CUT-B); refusing arrivals (SHED) sheds sessions: in a registered test a 3600\,s stop drained the trap".
- Replacements:
  - v2_intro.tex:80 "drained it only slowly (CUT-B);" → "shrank its backlog only slowly, all three runs still trapped at 8700\,s (CUT-B);"
  - v2_intro.tex:69 "drained the three CUT-B traps only slowly" → "shrank the three CUT-B backlogs only slowly"
  - v2_conclusion.tex:40-41 "a cut below the all-miss capacity drained the trap only slowly, as" → "a cut below the all-miss capacity shrank the backlog only slowly, all three runs still trapped at 8700\,s, as"
  - v2_validation.tex:217 "the backlog drained, slowly, at" → "the backlog fell, slowly, at"
  - v2_validation.tex:228-229 "and ``drained slowly'' is within 8700\,s." → "and none left the trap within 8700\,s."
  - v2_validation.tex:231-232 "the all-miss capacity drained the trap only slowly:" → "the all-miss capacity shrank the backlog only slowly, every run still trapped at 8700\,s:"
  - v2_control.tex:33 (same sentence, outside my scope) "drained the CUT-B traps only slowly:" → "shrank the CUT-B backlogs only slowly:"

5. paper/sections/v2_conclusion.tex:36-37
- Problem: same S5 overclaim as #1.
- Evidence: "and, with predictions frozen before the runs, on four runs in two cells trapped by a tool slowdown alone".
- Replacement: "...trapped by a tool slowdown alone." → "...trapped by a tool slowdown alone, in four of the five pre-set scores (a per-run slope check failed in two)."

6. paper/sections/v2_intro.tex:66-68
- Problem: the intro has no counterpart to the abstract's "4 runs in two cells". It omits TOOLSLOW-D15's trap-state scores and both S5 misses.
- Evidence: v2_validation.tex:131-132 "S5's plug-in lies on the measured side of the threshold in 2 of 3 runs".
- Replacement: "model's plan-averaged TRAPS. After a burst," → "model's plan-averaged TRAPS; its one trapped run also met the four pooled scores, and across the four runs trapped by a slowdown a fifth, per-run slope check failed twice. After a burst,"

7. paper/sections/v2_validation.tex:223-224 (CUT-B)
- Problem: "fits the slopes about as well" understates. The "theory-favoured 3/3" in Table 4 depends on which comparators were registered.
- Evidence: PAPER_INPUT_r15.md, verified recompute: "seed 0 would have been QS-FAVOURED (|S − S_qs| = 0.00036 < |S − S_theory| = 0.00099)".
- Replacement: "this arm, fits the slopes about as well." → "this arm, fits the slopes about as well: had it been one, seed~0 would have favoured it (error 0.00036 against model~F's 0.00099\,/s), and the arm would still have passed, 2 of 3."

8. paper/sections/v2_validation.tex:200-201
- Problem: the sentence says the rule rejects "the constant-throughput readings", but the next clause says a constant reading (the nominal cut rate) fits as well.
- Evidence: "rejects only the constant-throughput readings, those in which the trap drains at the throughput it showed or completes sessions at the all-miss capacity".
- Replacement: "rejects only the constant-throughput readings, those in which" → "rejects only the two constant-throughput readings it was built against, in which".

9. paper/sections/v2_validation.tex:69-72 (Youth premium bullet; outside my paragraphs, but it closes flag 4)
- Problem: the confound is conceded but not bounded.
- Evidence: "Part of the excess over $D$ is a congested engine computing prompt tokens faster than the 32-session reference behind $\lref$".
- Replacement: after "...is not explained." add "That speed-up does not make the sign: divided by each run's measured token-rate ratio (0.95--1.12), completions still exceed $\lref$ by a factor of 1.08--1.81 in every one of the 57 runs."
- This needs a NUMBERS.md row. Script: C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/final_review_54d3529/premium_vs_tokrate.py

NIT

10. paper/sections/v2_intro.tex:38
- Problem: the sentence pairs the from-empty maximum (2.4×) with a pooled average for the backlog. From trap_check.json, slope/(λ−λmiss) averages 0.65 (median 0.69) over the 57 runs but 0.80 (0.51–0.94) over the 13 from-empty runs.
- Evidence: "by up to 2.4 times (one from-empty run at 6.5~$\lref$), while their backlog grows at about two thirds of the quasi-static rate".
- Replacement: "while their backlog grows at about two thirds of the quasi-static rate." → "while over the 57 stuck runs of our paired-test protocol their backlog grows, on average, at about two thirds of the quasi-static rate."

11. paper/sections/v2_intro.tex:48-49
- Problem: "(Theorem 2)" overstates what is proved for the premium.
- Evidence: v2_theory.tex:75-77 "proved by Theorem~\ref{thm:premium}'s monotonicity for $\rho\ge1.04$, shown by a monotone bracket ... and only to first order below that".
- Replacement: "a youth premium above 1 for our workload (Theorem~\ref{thm:premium})" → "a youth premium above 1 for our workload at every load we checked (Theorem~\ref{thm:premium} for $\rho\ge1.04$)".
- The abstract can stay as it is: every load in the paper has ρ ≥ 1.145.

12. paper/sections/v2_conclusion.tex:31-32
- Problem: the sentence says the engine converges, which line 6 says is not proved.
- Evidence: "the trapped engine obeys a linear renewal recursion along FIFO orbits, so from any trapped state it converges".
- Replacement: "as a fluid FIFO server on which every turn misses, the trapped engine obeys" → "model~F, the trapped engine idealized as a fluid FIFO server on which every turn misses, obeys".

13. paper/sections/v2_related.tex:15-18 (outside scope)
- Problem: it lists the Corollary 3 reading itself as an addition, while the intro (line 56-57) and §2 say only its engine test is new. It also omits CUT-B.
- Evidence: "we add ... the reading that the throughput measured in a trap exceeds the drain threshold ... CUT-A is consistent with it".
- Replacement: "the reading that the throughput measured in a trap" → "an engine test of the reading that the throughput measured in a trap", and "CUT-A is consistent with it" → "CUT-A and CUT-B are consistent with it".

REPLACEMENT ABSTRACT (paper/main.tex:57)

Prefix caching lets an LLM agent's follow-up turns reuse cached KV, but a burst can tip a serving engine into a trap in which every turn misses and the backlog does not drain, at a load it served before. Lu et al., who posted first, reported this metastable collapse, its feedback loop and a fluid model of its window. In registered paired tests on two engines, two GPUs and two models, a 200-session burst left the engine at zero hits in all 30 runs, while every matched no-burst run stayed good. We analyse an idealized model of the trapped state exactly: for a fluid FIFO server on which every turn misses, we prove that along FIFO orbits its cycles obey a linear renewal recursion. As is classical, the trap drains if and only if arrivals are below the all-miss capacity; above it, a Perron root fixes the dynamics: every trapped state converges to a known self-similar regime in which the gap between turns grows linearly, the backlog grows at 0.6 to 0.8 of the excess load here, and the turns served are young and short. For our workload, sessions then complete faster than the all-miss capacity, a youth premium with turn-count and cost-growth factors, so in the model a trap's measured throughput overstates the recovery threshold. Retrospectively, with nothing fitted to trap data, the theory matches 57 stuck runs: the turn mix within 3\% in 50 runs, completions above the all-miss capacity in every run, and the pooled gap growth. Blind in outcome, 4 runs in two cells trapped by a tool slowdown alone met 4 of 5 pre-set scores, and after arrival cuts the traps persisted, backlogs rising or falling slowly, as predicted. Of two exits, refusing arrivals sheds sessions, while a session cap restores reuse: in registered tests it rescued 9 of 9 established zero-hit traps at the same load without shedding, and the engine stayed good after release. We do not prove that the engine converges to the model.

Count: 1913 form characters (1914 LaTeX source), limit 1920, margin 7, from COORD/release-tools/count.py. count_abs.py reports "expanded latex == form: True".

Only three things change; everything else is verbatim:
- "met pre-set tolerances" → "met 4 of 5 pre-set scores"
- "the traps persisted or drained slowly" → "the traps persisted, backlogs rising or falling slowly"
- The last sentence loses its redundant "The model is an idealization;" to make room. "idealized model" stays in sentence 4.
- No new numbers: "4 of 5" is S1–S5 of the body.

Files are in C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/final_review_54d3529/:
- abstract_proposed.tex
- abstract_proposed_form.txt
- premium_vs_tokrate.py (flag 4 / #9 check)
- twothirds.py (#10 averages)

JUDGEMENT
Close to submittable: the three MUST-FIXes are wording errors, not result problems ("met pre-set tolerances", "drained slowly", and the false "flat backlog" alternative in the intro).
With them fixed (proposed abstract 1913/1920), the abstract, intro and conclusion claim no more than the body supports; "as predicted" and the youth-premium clause need no abstract change.