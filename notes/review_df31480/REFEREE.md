Referee report on draft df31480 (branch claude/reframe-draft-211a57). Paths are relative to C:/Users/Akshat/Desktop/Claude Code/Nova-Research/.claude/worktrees/reframe-draft-211a57/ unless absolute. Categories: [Math], [Novelty], [Evidence], [Clarity].

Math summary. I found no false statement in Theorems 1–2 or Corollaries 3–4. I re-derived these and they hold:
- the orbit recursion and h_n;
- the trichotomy and the busy period V_tot/(1−ρ);
- parts (b), (e) and (f);
- D/λmiss = H(z)Γ(z);
- the truncated-geometric formula for H and the ordering argument for Γ.

I also recomputed the 300k cell from the stated inputs: ρ=1.344, γ/z=0.0129, D=1.131 λref, α/(λ−λmiss)=0.634, served prompt 9,324, E[T]/k̄_c=0.6079, r=0.948–0.962. The negative-premium counterexample holds too. The math findings below (4, 9, 19, 20, 21, 24) are about presentation, not errors.

1. MUST-FIX [Evidence] paper/sections/v2_validation.tex:176-180; v2_conclusion.tex:37-39; v2_intro.tex:61-62
- Problem: CUT-A's persistence to 8700 s is listed as evidence that singles out model F, and the conclusion rests on it. The registered comparators predict it too.
- Evidence: the draft says "Three results single out model~F. ... And all three traps persisted to the end of the run." The conclusion says "the support for the corollary comes from the persistence and from the late backlog". The registered naive slopes are −0.0094, −0.0204 and −0.0099 /s (l.165-166). Starting from the 179–186 sessions present at the cut (notes/PREDICTIONS_icml_cut.md:106-108), they still leave about 126, 52 and 117 sessions at 8700 s. That is far above n_b=32.7 (l.201). Only the discarded draft-rule comparator (about −0.039 /s) would have reached n_b by 6300 s, and only in seeds 0 and 1 (notes/PREDICTIONS_icml_cut.md:148-150).
- Fix: change l.176 to "Two results single out model F." Replace the last sentence of l.180 with: "Persistence to 8700 s does not discriminate: the registered naive reading also leaves 50–125 sessions at the end of the run." In the conclusion: "...the support for the corollary comes from the late backlog, which followed model F's frozen slopes."

2. MUST-FIX [Clarity] λref is never defined as a symbol in pp. 1–13, and λmiss has three meanings.
- Where: v2_intro.tex:6-7 (first use) and throughout. The only definition is in an appendix, paper/sections/method.tex:11.
- Evidence of the three meanings:
  - method.tex:11 says "numeric multiples of $\lmiss$ in this paper are multiples of the $\lref$".
  - v2_theory.tex:14 defines λmiss=(Σc_kG_k)^{-1}, and Table 1 uses "the model's λmiss".
  - v2_validation.tex:68 speaks of "the 32-session reference behind $\lmiss$".
- v2_control.tex:28 writes "a cut to 0.2~$\lref$" for Lu et al.'s own reference rate, which is 12.0/min (C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/COORD/scoop-2611.02543/extract_theirs.md:80).
- Across cells λmiss/λref runs from 0.962 (150k) to 1.035 (H200 600k) (results/theory/icml/support.json, compared with the λref values in method.tex:11).
- Fix: after v2_theory.tex:15 add: "Rates are multiples of λref, the all-miss session rate measured on each cell with the radix cache disabled (E0a, 32 sessions; 0.0715 sessions/s on A100 300k); λmiss is model F's value from the cost model, λmiss/λref = 0.96–1.035." Then:
  - fix the convention in method.tex:11;
  - v2_control.tex:28: "0.2 of their reference rate (12 sessions/min)";
  - v2_validation.tex:68: "behind λref".

3. MUST-FIX [Novelty] Corollary 3 is claimed as new, but the paper's own citations give it.
- Where: v2_related.tex:44-46; v2_theory.tex:114-115; v2_intro.tex:53-54.
- Evidence: the draft says "Corollary 3's statement that the trapped throughput exceeds the drain threshold, have no counterpart we found". But D(λ)>λmiss is Theorem 2 itself, and the threshold is "the classical busy-period condition" (v2_theory.tex:115-116). For overloaded processor sharing the paper itself cites departures that "can exceed 1/E[S]" (l.113-114), while that queue drains iff λ<1/E[S]. That is the same consequence.
- Fix: related l.44-46 should read "...its turn-count and cost-growth factors have no counterpart we found; Corollary 3 is the operational reading of Theorem 2 with the classical drain condition, and its processor-sharing counterpart follows from [jeanmarie1994transient] in the same way." Delete the matching clauses in intro l.53-54 and theory l.114-115.

4. SHOULD-FIX [Math, presentation] Theorem 1 states limits the data do not test, and part (d) does not carry the "exact virtual origin" that l.110-111 claims as new.
- Where: v2_theory.tex:40, 43-44, 92, 110-111.
- The centring constant in (d) is empty: "$f^m(u)+c=z^m(u+c)(1+o(1))$ with $c=V_{tot}(0)/(\rho-1)$". Since (u+c)/u→1, deleting c leaves an equivalent statement.
- The real content is only in the proof (v2_app_trap.tex:169-175): u_n+c = Bz^n + O((r+ε)^n). This is an additive error, and it vanishes only because r<1 in these cells (l.176), not in general.
- It matters for the data. At 1.35 λref, c≈8,000 s (V_tot=3,834 s at 4,200 s, support.json "kendall"). So the fluid's window-mean gap of 193 s (support.json "fluid") is about 2–2.5·γt, not γt. The slope tests work because of the affine law, not because of (c)'s V(t)/t→γ.
- The "exact identity" at l.92 holds only for n≥K−1 (app l.164).
- Fix: rewrite (d) as: "With c=V_tot(0)/(ρ−1), u_n+c=Bz^n+O((r+ε)^n); hence V(u)=γ(u+c)+O((r+ε)^n), N(u)=α(u+c)+O((r+ε)^n), and f^m(u)+c−z^m(u+c)=O(z^m(r+ε)^n); when r<1 these errors vanish absolutely." Merge (f) into it, and add "for n≥K−1" at l.92.

5. SHOULD-FIX [Evidence] CUT-A's registered rule has no reported power against an alternative the text admits fits equally well, and the rule was loosened after simulation.
- Where: v2_intro.tex:62-63; v2_validation.tex:147-158, 172-175.
- Evidence: the intro says "the registered rule favoured model F over both constant-throughput readings in every seed". The two comparators sit at −0.009 to −0.020 /s and +0.009 to +0.015 /s, with model F near 0 "well between them" (l.147-149), so almost any flat backlog passes. The draft concedes that "completions equal to the nominal cut rate fit as well as model F" (l.174). Moving the sign clause "raised CUT-A's probability of passing from 0.82 to 0.99" (l.157-158), and that probability was computed only with model F as the truth (notes/PREDICTIONS_icml_cut.md:180-190).
- Fix: rerun the existing Monte Carlo (analysis/theory/icml/cut_predict.py) with "completions = λ'_plan" as the truth and report P(PASS). In the intro write: "the rule rejected the two constant-throughput readings it was built against; a flat-backlog reading fits as well over [3000,8700) s; post hoc, the late backlog followed model F's frozen slopes."

6. SHOULD-FIX [Evidence] The engine-side youth premium is confounded with a faster congested engine.
- Where: main.tex:57; v2_validation.tex:66-69.
- Evidence: the abstract claims "completions above the all-miss capacity in every run". But the text also says "Part of the excess over D is a congested engine computing prompt tokens faster than the 32-session reference". Measured token-rate ratios are 0.95–1.12 against 1.01–1.05 expected from the composition (v2_app_trapdata.tex:49); for example, 1.106–1.113 against 1.026 on H200 600k at 2.0 λref (results/theory/icml/trap_check.md).
- I rescaled each run's completions by (predicted/measured token ratio). All 57 runs stay at 1.10–1.89 λref, mean 1.04 D, so the claim survives, but the paper has to show it.
- Fix: add that sentence to the youth-premium bullet and a rescaled column to Table 1.

7. SHOULD-FIX [Evidence] The abstract overstates the blind TOOLSLOW-W test.
- Where: main.tex:57; v2_intro.tex:59-61; v2_conclusion.tex:34-35.
- Evidence: "Blind, it matched 3 runs trapped by a tool slowdown alone". But:
  - it is one cell at one rate;
  - "The tolerances were set after seeing the committed runs" (v2_validation.tex:113);
  - the backlog came in at +29% of α against a ±35% limit (l.126);
  - the S5 plug-in fell on the correct side in only 2 of 3 runs (l.127-128);
  - every frozen model predicted the trap (l.128-130).
- Fix: "In a blind test on 3 runs in one cell, trapped by a tool slowdown alone, it passed its pre-set tolerances (composition +1.9%, gap slope 1.08γ, backlog +29% of α against ±35%)."

8. SHOULD-FIX [Evidence] The retrospective summary in the abstract reads as a per-run match.
- Where: main.tex:57; v2_intro.tex:36, 55-58.
- Evidence: "the theory matches 57 stuck runs: the turn mix within 3% in 50 runs, the gap growth (median ratio 1.01)". But:
  - the per-run gap ratio ranges 0.04–1.81 (v2_validation.tex:64);
  - the per-run backlog fraction ranges −0.002 to 1.01 (support.json slope_frac_e2);
  - the 57 runs reuse arrival plans: the 36 registered-protocol runs use 30 distinct plans (v2_app_trapdata.tex:57-58);
  - "by up to 2.4 times" (intro l.36) comes from a single from-empty run at 6.5 λref.
- Fix: write "...and, pooled, the gap growth (median ratio 1.01; per run 0.04–1.81)", give counts of distinct plans next to run counts, and add "(one from-empty run at 6.5 λref)" after "2.4 times".

9. SHOULD-FIX [Novelty/Math presentation] Theorem 1 bundles classical facts with the new recursion, and the abstract credits the Perron root for the classical drain condition.
- Where: main.tex:57; v2_theory.tex:35-45.
- Evidence: the abstract says "Its Perron root fixes the dynamics: the trap drains if and only if arrivals are below the all-miss capacity". Yet the paper itself calls (a) classical, (b) a fluid state-space collapse and (e) "an elementary expansion" (l.96-112). Part (a) follows from Lemma 2(iii) alone (v2_app_trap.tex:52, 90-94).
- Fix: split into three statements:
  - a Lemma: the orbit recursion;
  - a Theorem for ρ>1: convergence from any state, with the affine law of item 4 and the rate r/z per generation;
  - a Proposition collecting (a), (b) and (e), citing Kendall, Reiman and Dai–Kurtz.
  Reword the abstract to match.

10. SHOULD-FIX [Novelty] The classical structure behind Eq. (1) is not credited.
- Where: v2_theory.tex:96-112; v2_related.tex:33-46.
- Evidence: the draft says "What we add ... is the renewal recursion along FIFO orbits". But Eq. (1) is a discrete Lotka–Leslie renewal equation:
  - the arrivals λΔ_n play the role of births, G_k of survival, and a_k of net maternity;
  - the tilted mix G_k z^{-k} is Lotka's stable age distribution.
- The authors' own literature check verified, but does not cite, three directly relevant works (notes/LIT_CHECK_trap_2026-11-05.md:26-29): Kleinrock 1967 and Coffman & Kleinrock 1968 (round robin with feedback to the tail) and Frolkova, Foss & Zwart 2014 (overloaded polling).
- Fix: add that sentence after l.99 and cite the three works in §7.

11. SHOULD-FIX [Novelty/Clarity] Model F results are stated as facts about the engine.
- Where: v2_control.tex:26-27; v2_related.tex:16-17; v2_theory.tex:62.
- Evidence: "Corollary 3 sharpens this for an FCFS engine on which every turn misses" and "A trapped engine thus completes sessions faster than its all-miss capacity while its backlog diverges". The paper itself says "We do not prove that the engine converges to model~F" (l.124-125).
- Fix: write "for model F, an all-miss FCFS fluid" in the control and related-work sentences, and "In model F the trapped server thus..." in the theory sentence.

12. SHOULD-FIX [Evidence/Clarity] Table 1 and §3 compare backlog slopes on two different scales.
- Where: v2_validation.tex:22, 70-71.
- Evidence: "Backlog: slope as a fraction of $\lambda-\lref$, against $\alpha/(\lambda-\lmiss)$." The scales differ by up to 9%: the ratio (λ−λmiss)/(λ−λref) is 0.93 on H200 600k at 1.5 λref and 1.09 on the 150k pool at 1.45 λref.
- Fix: report measured slope/α. From trap_check.md this is mean 0.99, median 1.05, range −0.01 to 1.61 over the 57 runs, against 1.35–1.59 for the quasi-static reading. That is a stronger statement than the current one.

13. SHOULD-FIX [Clarity] Notation collisions:
- Fig. 3's legend labels the H1 layer "F1" (v2_entry.tex:5-6), while (F1) is model F's all-miss assumption.
- c means the cost vector (v2_theory.tex:57), the virtual origin (l.44) and the session cap (v2_control.tex:34).
- z̄′ (tool time per turn, v2_entry.tex:38) sits next to the Perron root z.
- The same tilted mix is called π^z (l.42) and ν^z (l.56), and π_k means pending mass in the appendix (app l.30).
- α means both the backlog slope and the exponent in λE[e^{−αS}] (l.114).
- The main text lists assumptions (F1)–(F5), but the proof of Corollary 3 cites (F6) (v2_app_trap.tex:217).
- Fix: change the Fig. 3 legend to "H1"; write u* for the virtual origin, n_cap for the cap (the \ncap macro exists) and α_PS for the processor-sharing exponent; use ν^z only; align the assumption lists.

14. SHOULD-FIX [Clarity] Section 2 uses symbols and a cross-reference the reader cannot yet resolve.
- Where: v2_theory.tex:35, 120, 128.
- Evidence:
  - h_n is described only by its properties (its formula is at v2_app_trap.tex:58);
  - M, E_S and churn are undefined at first use ("up to the M/E_S requests that run concurrently", "R_M=M/churn");
  - "(F3) is request-level FCFS admission (Proposition A)" cites a result that assumes FCFS (appendix.tex:468) and concludes limsup μ(n)≤λmiss (l.471), which a reader will set against Theorem 2;
  - model.tex:28 says "deep congestion is bounded by the all-miss capacity".
- Fix:
  - add a notation line defining M, E_S and churn;
  - give the formula for h_n;
  - cite the FCFS defaults in background.tex:4 for (F3);
  - add "Proposition A bounds the closed system at the stationary mix; the open trap exceeds λmiss only through its tilted mix";
  - in model.tex:28, write "of the closed system".

15. SHOULD-FIX [Clarity/Evidence] The evidence-status vocabulary is hard to follow.
- Where: v2_validation.tex:56-57, 107-119, 141-142; v2_entry.tex:9-12, 55-63.
- Evidence: the main text uses eleven or more status labels, for example "so it is blind in outcome only". It also interleaves commit hashes and clock times ("pushed at 00:24:47 CST on 2026-11-05 by GitHub's activity log"). Table 4 gives a status only for the registered tests, not for the claims behind Table 1 and Fig. 2.
- Fix: add one evidence-ledger table in §3 with columns: claim, runs (distinct plans), status (registered verdict / blind prediction with rule fixed beforehand / post hoc), and when the tolerance was set. Tag the abstract's numbers with these statuses and move hashes and times to the provenance appendix.

16. SHOULD-FIX [Evidence] The explanation for the from-empty backlog excess is never checked.
- Where: v2_validation.tex:76-78; v2_app_trapdata.tex:40-42.
- Evidence: the draft says this "points to window arrival rates above nominal in these single seed-0 runs". But the plans "reproduce the measured window arrival rates exactly" (v2_app_trapdata.tex:53-54), so this can be checked directly. Conservation applied to trap_check.md implies window arrival rates 4–16% above nominal in all 13 runs; for example, 300k at 3.0 λref gives 1.66+1.83 = 3.49 λref.
- Fix: compute λ_window(plan) over [1500,3000) s for these runs and report slope − (λ_window − D), as is already done for the E2 runs.

17. SHOULD-FIX [Evidence] The per-run scatter is never compared with the stochastic model, which already exists.
- Where: v2_validation.tex:73-74.
- Evidence: "per run the gap and backlog statistics scatter widely, mostly with the plan's arrivals over the window". trap_check.md already gives model F's stochastic slope SD for each cell, for example 0.0181 (0.0077) at 300k and 1.35×.
- Fix: report per-run standardized residuals, (measured − plug-in)/SD, and the share of runs inside the model's 90% band.

18. SHOULD-FIX [Novelty/Evidence] The Lu et al. comparison and the H200 claim are overstated.
- Where: v2_intro.tex:67-70; v2_entry.tex:92-101.
- Evidence: the intro says "the measured cliff moved out on the H200 as the tool-call term predicts". But the measured shifts are 6.7 and 10.9 sessions against 5.8 and 6.6 predicted (v2_entry.tex:98-99), and the 600k crossing was a 4.4-session miss (l.58). The 1.5-versus-4.1 comparison is against a post-hoc reading of a model its authors do not use to predict hits.
- Fix: in the intro, give the measured and predicted shifts instead of "as predicted". Move Table 2's h(W/C) column and the 1.5-versus-4.1 sentence to the appendix (D4).

19. SHOULD-FIX [Math/Clarity] The Fig. 2 caption misreads Corollary 4.
- Where: v2_validation.tex:7; v2_theory.tex:78-84.
- Evidence: the caption says "they nearly coincide, as Corollary 4 predicts". The corollary itself says "This needs proportional cost vectors". The eight cells have different cost-weighted mixes ω (c60/c1 = 17.4–22.8; E[T]/k̄_c = 0.601–0.619, support.json). And l.104 credits the rescaling itself to Khanin et al.
- Fix: write "nearly coincide because the cells' ω are close (E[T]/k̄_c = 0.60–0.62)", and demote Corollary 4 to a Remark.

20. NIT [Math] The statement of Theorem 2 has two gaps.
- Where: v2_theory.tex:57, 66.
- Evidence: "$H=1$ for a geometric $T$ on $\{1,2,\dots\}$" is outside model F's assumptions (finite K, G_K>0). The claim "proved ... for ρ≥1.04" uses H>1−q^K and Γ(z1)=1/(1−q^K), with z1=1.00158 (support.json premium_certificate); both appear only in the appendix proof.
- Fix: write "(K=∞; the formulas extend for z>1)", and add to Theorem 2: "if E_ν[c]/c1 > 1/(1−q^K), then D>λmiss for all z≥z1".

21. NIT [Math] The wording of Corollary 3.
- Where: v2_theory.tex:70-75.
- Evidence: "a cut to any rate in (λmiss,D(λ)), below the throughput measured in the trap, does not clear it". But:
  - a cut to exactly λmiss also fails to clear it (l.73);
  - D(λ) is the asymptotic rate, whereas the CUT test used window rates of 1.32–1.41 λref against 1.23 (v2_validation.tex:145);
  - on the engine, hits return at n_b, not when the queue is empty.
- Fix: "any rate in [λmiss, D(λ)), below the asymptotic trapped throughput, does not empty model F's queue", and retitle it "...overstates the drain threshold".

22. NIT [Evidence] The rescue's cost is missing from the abstract.
- Where: main.tex:57; v2_intro.tex:72-74.
- Evidence: the abstract says "rescued 9 of 9 ... without shedding", but the cost of 386–569 s average wait per paused session, and 45–97% of the first hour's goodput, appears only in v2_control.tex:46-50.
- Fix: append "at an average client-side wait of 6–10 min per paused session".

23. NIT [Evidence] Self-similarity is reported only for the best cell.
- Where: v2_validation.tex:78-80.
- Evidence: the main text reports "on the H200 at 600k ... 0.86–1.19". Elsewhere the ratio is 0.2–1.6, and 0.1–0.8 for long sessions (v2_app_trapdata.tex:64-66).
- Fix: report all the ranges, or move the check to the appendix.

24. NIT [Math] "Unchanged to four significant digits" is slightly wrong.
- Where: v2_theory.tex:121-122; v2_app_trap.tex:267-268.
- Evidence: at 1.65 λref, the completion rate is 0.086695 against 0.086686 /s and the served prompt 8678.1 against 8679.5 (support.json fluid.think_time).
- Fix: "changes them by less than 0.02%".

25. NIT [Clarity] Small typesetting and reference issues:
- Fig. 3 (fig:fpmu) is never cited in v2_*.tex.
- The title of Fig. 2(d) is clipped ("gap slope vs completion", main.pdf p.6).
- There is a 55 pt overfull box at main.log:954, from the table at v2_app_trapdata.tex:20-39.
- The conclusion (v2_conclusion.tex:30-31) drops "known" from "self-similar regime" and does not cite Khanin et al., unlike the abstract.
- Fix: cite Fig. 3 in the first paragraph of §4, re-export Fig. 2, wrap the table in \resizebox, and write "converges to the known self-similar regime [khanin2001steady]".

Where a reader is most likely to get lost in pp. 1–13: findings 2, 4, 13, 14 and 15.

Top five changes that fit in one day:
1. Restate Theorem 1 as a lemma, a theorem and a proposition, with the affine virtual-origin law. Credit Lotka–Leslie, Kleinrock and polling; drop Corollary 3 from the novelty claims and demote Corollary 4 to a remark. (Findings 3, 4, 9, 10, 19.)
2. Do one definitions pass: define λref against λmiss, use slope/α in Table 1, fix the F1 legend and the collisions of c, z̄′ and π/ν. (Findings 2, 12, 13, 14.)
3. Add the evidence-ledger table and reword the abstract, intro and conclusion to match it. (Findings 1, 5, 7, 8, 15, 22.)
4. Run four analyses on existing data: the rescaled premium, the plan arrival rates for the from-empty runs, the stochastic per-run residuals, and CUT-A's P(PASS) under the flat-backlog alternative. (Findings 5, 6, 16, 17.)
5. Shorten §4 and move the Lu et al. comparison and the provenance detail to the appendix. Prune or reconcile the reused appendices (method.tex:11, model.tex:28). Use the freed space for a plot of V and N against t showing the virtual origin.

Checks I ran: the scripts are in C:/Users/Akshat/AppData/Local/Temp/claude/93194b88851e3ff4/90500cb0-d13d-4ffe-a42a-2ca3a3f8018c/scratchpad/tonight/review_df31480/scripts/ (check_modelF.py, premium_norm.py, e0b_implied.py, slope_over_alpha.py, slow_costs.py). I wrote nothing in either worktree.

Overall judgement:
The mathematics is correct and honestly hedged, but Theorem 1's statement hides what is actually new (the affine law with its virtual origin) behind classical parts, and the novelty claim for Corollary 3 is contradicted by the paper's own processor-sharing citation.
The engine evidence is extensive and the body labels it carefully, but the abstract, intro and conclusion overstate the blind tests (3 runs in one cell; CUT-A's persistence does not discriminate), and the λref/λmiss confusion makes every table harder to read than it needs to be.
For a performance venue as it stands: weak reject or major revision. With the one-day fixes it becomes a credible modelling-and-measurement paper, though not a queueing-theory one.