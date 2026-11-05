# Adversarial review of the reframe draft ("Inside the Trap"), 2026-11-05

Reviewed: worktree `reframe-draft-211a57` at HEAD `250df81` plus the uncommitted edits to `paper/main.tex`,
`v2_theory.tex` and `v2_conclusion.tex` present at 02:50 CST (another session was editing while I read; line numbers are
those of the files at that time). Read-only: nothing in the repository was edited, committed or deleted; Nova was not contacted.
Lu et al. (`COORD/scoop-2611.02543/other_paper.txt`) was read as data only. Scratch script for finding 6:
`scratchpad/review/scripts/gapz.py`.

Summary: 7 MUST-FIX, 21 SHOULD-FIX, 22 MINOR. The theorem proofs in Appendix A check out against
`notes/THEORY_ICML_2026-11.md` sections 3-4 (I re-derived Lemma 2(iv), Theorem 1(b),(c),(f), Theorem 2(i),(iii) and Corollary 3).
The problems are in how the results are stated (one corollary stated unconditionally, novelty against Lu et al.), one wrong
predicted constant in the validation, predictions written as outcomes, and a misreading of Lu et al.'s simulations.

---------------------------------------------------------------------------------------------------------------------------

## MUST-FIX

### 1. CUT predictions are written as if they were measured outcomes
- **Where:** `v2_validation.tex:106-111`.
- **Problem:** "All six runs stay stuck over [5700,8700) s. CUT-A ... does not drain: its backlog dips by less than 15% and
  grows again (per-seed slopes ... of +0.0039, -0.0026 and +0.0028 /s ...). CUT-B drains, slowly (slopes -0.0095 to
  -0.0131 /s), and empties only at about 27,100 s" are the frozen model-F predictions, stated in the indicative. The
  `\pending{CUT outcomes}` at the end does not undo this; a reader takes these as data. Even as predictions, "grows again"
  is wrong for seed 1, whose predicted slope is negative and whose last bin (165.8) is below its pre-cut level (180.5).
- **Evidence:** `notes/PREDICTIONS_icml_cut.md:93-111` (theory slopes W1 +0.00392 / -0.00258 / +0.00284; CUT-B -0.00953,
  -0.01310, -0.01233; N bins), `:126` (27,100 s from the fluid), `:148-151` (naive 5 of 6); `notes/REFRAME_DRAFT_2026-11-05.md:27`
  ("CUT: predictions in, outcomes pending").
- **Replace with:** "Model F, driven by each seed's exact plan, predicts that all six runs stay stuck over [5700,8700) s; that
  CUT-A, although its rate is below the throughput measured in the trap, does not drain (backlog dip under 15%; predicted
  slopes over [3000,8700) s of +0.0039, -0.0026 and +0.0028/s, seed 1's plan having few post-cut arrivals); and that CUT-B
  drains only slowly (predicted slopes -0.0095 to -0.0131/s; in the fluid the queue empties at about 27,100 s, the busy
  period of Theorem 1(a)). A naive projection from the throughput measured in the trap would put five of the six runs back
  below the onset before 8700 s."

### 2. Corollary 3 asserts D(lambda) > lambda_miss unconditionally; the paper's own counterexample refutes it
- **Where:** `v2_theory.tex:73-74` ("In particular, since D(lambda) > lambda_miss, a cut to any rate in (lambda_miss, D(lambda))
  ... does not clear it").
- **Problem:** In model F, D > lambda_miss is not a theorem. Three paragraphs earlier (`v2_theory.tex:62-64`) the draft itself
  reports that with T = min(Geometric(1/15), 60) and c_k = 1 + 1e-3 (k-1) the premium is negative at every load checked. The
  corollary is a statement about model F in general, so "since" makes it false as stated.
- **Evidence:** the source corollary is conditional: `notes/THEORY_ICML_2026-11.md:239-240` ("Whenever the premium is positive,
  a cut to lambda' in (lambda_miss, D(lambda)) does not clear the trap"); Theorem 2(v), `:222-226`.
- **Replace with:** "In particular, whenever D(lambda) > lambda_miss (Theorem 2; for our workload at every rho >= 1.04), a cut
  to any rate in (lambda_miss, D(lambda)), below the throughput measured in the trap, does not clear it."

### 3. The drain threshold and Corollary 3 are claimed as new; Lu et al. state the threshold, and the busy period is classical
- **Where:** `v2_intro.tex:47-48` ("the renewal recursion ..., the premium and the threshold are new as far as we found");
  `v2_related.tex:41-42` ("Theorem 2 and Corollary 3 have no counterpart we found"); `v2_theory.tex:110-111` (the whole of
  "Corollary 3" listed under "What we add").
- **Problem:** priority/novelty overclaim against Lu et al. They write "Arrivals below D_low let the population drain while
  reuse remains poor" and "Throughput measured in this collapsed state sets the scale of the arrival reduction needed". The
  theory note says outright that the threshold is not new against them. Part (a)'s busy period is classical, as the draft
  itself says (`v2_theory.tex:94-96`), and our own earlier Proposition A already argued for lambda_miss. The related-work
  paragraph also contradicts itself: line 9 credits Lu et al. with the D_low drain statement, and line 42 says Corollary 3
  has no counterpart.
- **Evidence:** `other_paper.txt:222`, `:251`; `notes/THEORY_ICML_2026-11.md:540-547` ("so the threshold itself is not new
  against them"; "Theorem 2 and Corollary 3 sharpen that remark"), `:523-525`.
- **Replace with:**
  - intro: "The self-similar regime itself is known [khanin2001steady], and the drain threshold has a qualitative
    counterpart in Lu et al.'s statement that arrivals below their low-reuse departure rate drain the population. New, as
    far as we found, are the renewal recursion that carries every trapped state into the regime, the premium, and the gap
    between the throughput measured in a trap and the threshold."
  - related: "...; we found no counterpart of Theorem 2, and Corollary 3 sharpens Lu et al.'s qualitative drain statement
    (the threshold is their D_low counterpart and the busy period is classical) by showing that the trapped throughput
    exceeds it."
  - theory, line 110: "...; and Corollary 3's comparison of the trapped throughput with the drain threshold."

### 4. Lu et al.'s simulated recoveries are misreported, and Corollary 3 is said to "require" them
- **Where:** `v2_control.tex:26-27` ("their simulated recoveries came only at rates below the trapped departures they measured,
  as Corollary 3 requires"); `v2_related.tex:16` ("their simulated recoveries are consistent with it").
- **Problem:** this is false for the host-tier case.
  - With the host tier, every seed recovered at 0.2 lambda_ref, which equals the bottom of the measured trapped departures
    (0.20-0.24). It is not below them.
  - At each of 0.3 and 0.4 lambda_ref, one seed of three was not trapped. Both rates are above all of those departures.
  - Only the GPU-only case fits the claim: recovery at 0.1, trapped at 0.2, against departures of 0.20-0.31.
  - Corollary 3 is a model-F (request-level FCFS) statement. It requires nothing of Lu et al.'s PD-disaggregated HiCache
    system; the theory note itself says "this is consistency only".
  - The error comes from the source note, which says the host tier "stayed trapped at 0.3-0.5". That sentence needs the
    same fix.
- **Evidence:** `other_paper.txt:245` ("With the host tier, every seed recovers at 0.2 lambda_ref and remains trapped at 0.5
  lambda_ref; two of three seeds are trapped at each of 0.3 lambda_ref and 0.4 lambda_ref"), `:251` (departures 0.20-0.31
  GPU-only, 0.20-0.24 host tier); `notes/THEORY_ICML_2026-11.md:548-550`; `notes/REFRAME_DRAFT_2026-11-05.md:54`.
- **Replace with** (control): "On GPU-only 1P3D every seed recovered at 0.1 and stayed trapped at 0.2 lambda_ref, against
  trapped departures of 0.20-0.31 lambda_ref, as Corollary 3 would suggest. With the host tier every seed recovered at 0.2
  lambda_ref (departures 0.20-0.24), and one seed in three also escaped at 0.3 and at 0.4. Their engine is PD-disaggregated
  with a host tier, not a request-level FCFS server, so the corollary does not apply to it directly."
- **Replace with** (related, line 16): "(Corollary 3; their GPU-only simulations agree with it, their host-tier ones only
  partly)".

### 5. The gap-slope comparison uses the wrong predicted constant (gamma instead of gamma/z)
- **Where:**
  - `v2_validation.tex:10` (Fig. 2(d)), `:19` and `:27` (Table 1, "gap slope / gamma"), `:55-56` ("median 0.98 (mean 0.94)"),
    `:64` (E0b "0.62-1.30, mean 0.98");
  - `v2_app_trapdata.tex:8`, `:20`, `:38`;
  - `main.tex:57` (abstract, "median ratio 0.98") and `v2_intro.tex:51`.
- **Problem:** the measured statistic regresses each gap (completion of turn k minus completion of turn k-1) on the
  completion time of turn k (`analysis/theory/icml/measured.py:77-92`: `gaps_t.append(tc)`). Theorem 1(c),(d),(f) give
  V(u)/u -> gamma with u the time the turn joins. In model F the turn that completes at t joined at u = f^{-1}(t), and
  f(u) + c ~ z(u + c). So the gap as a function of completion time grows at gamma/z = 1 - 1/z, not gamma = z - 1. The
  "exact fluid V slope" column of `trap_check.md` is also taken against join time.
- **Size of the effect,** recomputed from `trap_check.md:56-75`:
  - E2 runs: median ratio 0.978 against gamma becomes 1.013 against gamma/z (mean 0.938 becomes 0.960).
  - E0b runs: mean 0.978 becomes 1.026, range 0.63-1.30 becomes 0.64-1.38.
  - The systematic shortfall at high load in Fig. 2(d) mostly disappears: native 4.0x 0.82-0.94 becomes 0.89-1.02; native
    6.5x 0.83 becomes 0.94; 600k 5.0x 0.87 becomes 0.96.
  - The conclusions survive, but the stated comparison is against the wrong quantity.
  - The frozen S2 rule (`notes/PREDICTIONS_icml_trap.md:41`) inherits the bias. That is immaterial at 1.35x (z = 1.013),
    but it must be reported if the rule is applied at high load.
- **Replace with:** either regress on the previous turn's completion time (then gamma is right), or define in Table 1 and
  Fig. 2: "Gap slope: trend of the median gap against the turn's completion time, against gamma/z = 1 - 1/z (gamma = z - 1
  against the time the turn is sent)". Then update 0.98 to the recomputed value everywhere (about 1.01).

### 6. The abstract (and conclusion) state workload-specific results as general consequences of the theorem
- **Where:** `main.tex:57`; `v2_conclusion.tex:26-27`.
- **Problem:** after "we prove ...", the abstract says that above the threshold every trapped state converges to a regime
  in which "the backlog grows at 0.6 to 0.8 of the excess load ... and sessions complete faster than the all-miss
  capacity". Neither holds in general:
  - The premium can be negative under truncation (Theorem 2(v), as the draft reports at `v2_theory.tex:62-64`). For our
    workload it is proved only for rho >= 1.04.
  - alpha/(lambda - lambda_miss) tends to E[T]/kbar_c (0.60-0.62) as rho -> 1 but to 1 as rho -> infinity. The range
    0.6-0.8 holds only over the measured loads (rho <= 6.3).
- **Evidence:** `notes/THEORY_ICML_2026-11.md:44-48`, `:518-519`, `:632-641`.
- **Replace with:** "... the backlog grows at a fixed fraction of the excess load (0.6 to 0.8 at our loads), the turns served
  are young and short, and, for our workload, sessions complete faster than the all-miss capacity, a youth premium that we
  decompose into turn-count and cost-growth factors (it can fail under truncation)." Make the same change in the conclusion.

### 7. "No trapped FCFS run left the trap on its own" is contradicted two sentences later
- **Where:** `v2_validation.tex:80` against `:85`.
- **Problem:** the from-empty collapse that recovered (150k pool, 1.30 lambda_ref, seed 0) is an SGLang FCFS run (label
  `sglang-fcfs-r1-p150k`). The topic sentence is false as worded.
- **Evidence:** `results/r15_dataonly/verify_d1d5/verify_D1D5.md:20`; `D5_e0b_from_empty_runs.csv` (row 54, onset 1200 s,
  escape 2200 s).
- **Replace with:** "No FCFS run trapped by a burst or by the tool slowdown left the trap on its own."

---------------------------------------------------------------------------------------------------------------------------

## SHOULD-FIX

### 8. The abstract frames Lu et al. as concurrent without saying that they posted first, or what they have
- **Where:** `main.tex:57` ("Lu et al. reported this metastable collapse concurrently"); `v2_conclusion.tex:23-24` ("Lu et al.
  and we observed this independently", where "this" is a trap "in which every turn misses").
- **Problem:**
  - The intro says "Their paper appeared first". The abstract does not, and it omits that they also have the loop, the
    fluid model and the window.
  - Lu et al.'s traps were not zero-hit: the hit rate fell to 0.27 on H100 and to 0.33-0.35 on H200.
- **Evidence:** `v2_intro.tex:26`; `other_paper.txt:131`, `:586`.
- **Replace with:**
  - abstract: "Lu et al. first reported this metastable collapse, its sustaining loop and a fluid model of its window,
    concurrently with and independently of this work."
  - conclusion: "...; Lu et al. first reported such a trap (with reuse collapsed to a hit rate near 0.3), and we observed
    zero-hit traps independently."

### 9. The youth-premium bullet attributes the E0b range to the 57 E2 runs
- **Where:** `v2_validation.tex:57`.
- **Problem:** the bullet sits under "Over the 57 stuck runs of the E2 protocol" and says "at 1.10-2.40 lambda_ref". The
  2.40 is the E0b native 6.5x run; the E2 maximum is 2.03.
- **Evidence:** `support.json` `data.summary.compl_over_lref_all` = [1.104, 2.405] (all 70 runs); `trap_check.md:14` (E0b
  native 2.40), `:32` (E2 maximum 2.03).
- **Replace with:** "Every stuck run completes sessions above lambda_ref, at 1.10-2.03 lambda_ref (1.24-2.40 in the
  from-empty runs), and on average 1.055 times D ..."

### 10. "The premium is positive at every load" is more than is established
- **Where:** `v2_theory.tex:65-67`.
- **Problem:** it is proved only for rho >= 1.04. On [1+1e-12, z_1] it rests on a floating-point bracket (the smallest
  bracket bound is 9e-12), and below that it holds only to first order, with no remainder bound. The limitations paragraph
  (`v2_conclusion.tex:7-8`) states this correctly.
- **Evidence:** `notes/THEORY_ICML_2026-11.md:632-641`; `support.json` `premium_certificate.*.min_bracket_lower_bound`.
- **Replace with:** "the premium is proved positive for rho >= 1.04 (Theorem 2's monotonicity), checked in floating point on
  z in [1+1e-12, z_1] by a monotone bracket, and positive to first order below (no remainder bound)."

### 11. "Matches, in all 57 stuck runs" and "these laws hold" claim a per-run match the data do not show
- **Where:** `v2_intro.tex:49-52`; `main.tex:57` ("the theory matches 57 stuck runs"); `v2_conclusion.tex:27-28`.
- **Problem:**
  - Per-run gap-slope ratios run from 0.04 to 1.79, and backlog fractions from -0.00 to 1.01 against 0.63-0.74. The median
    0.98 is a pooled statistic.
  - The conclusion drops "retrospectively" and uses "nothing fitted", which Referee C corrected to "no parameter fitted to
    any trap measurement". vLLM, H200 and Llama each take a fitted speed factor.
- **Evidence:** `trap_check.md:20-39`, `:56-75`; `notes/THEORY_ICML_2026-11.md:1017`.
- **Replace with:**
  - intro: "model F reproduces, across the 57 stuck runs ..., the trapped turn mix (within 3% in 50 runs, 8% in all), the
    linear growth of the gap on average (median measured/predicted ratio about 1.0; runs whose plan's arrivals dipped grow
    slowly) and completions above the all-miss capacity in every run";
  - conclusion: "Checked retrospectively on 57 stuck runs ..., with no parameter fitted to any trap measurement, these laws
    hold on average."

### 12. The novelty of the critical case overlooks Bramson (1996), and related work misdescribes it
- **Where:** `v2_theory.tex:109`; `v2_related.tex:36-37`, `:41`; `v2_app_trap.tex:258`.
- **Problem:** the literature check records `bramson1996convergence` as "Kelly-type, load <= 1": convergence to equilibria
  of FIFO fluid models, which includes load one. Model F with equal costs c_k is a Kelly-type single-station FIFO line, so
  its critical case falls under that result. "Studied mostly for stability at load below one" misdescribes it.
- **Evidence:** `notes/LIT_CHECK_trap_2026-11-05.md:22`.
- **Replace with:** "the critical case for visit-dependent costs (for equal costs, a Kelly-type line, it is covered by
  Bramson's convergence of FIFO fluid models at load at most one [bramson1996convergence])". In related work, write "at
  load at most one". If the overlap is doubtful, check Bramson's statement before claiming part (b).

### 13. The intro sets the theory against a quasi-static trap model that neither we nor Lu et al. used as stated
- **Where:** `v2_intro.tex:31-34` ("Quasi-static models, Lu et al.'s and our own, treat the trap as ...: sessions complete at
  the all-miss capacity lambda_miss and accumulate at lambda - lambda_miss. On the engine both statements are wrong");
  `v2_theory.tex:3` ("Quasi-static models of the trap, ours of §4").
- **Problem:**
  - Our §4 says the fluid model is used "never for the trap" (`v2_entry.tex:22`). The earlier paper disclaimed it for
    growth in congestion, and its RR layer already gave 0.63-0.64.
  - Lu et al.'s D_low is a low-reuse rate (hit rate about 0.3), not the all-miss capacity. They also report measured
    trapped departures.
- **Evidence:** `notes/THEORY_ICML_2026-11.md:516-522`; `other_paper.txt:158`, `:222`, `:251`.
- **Replace with:** "Read literally in congestion, the quasi-static balance N' = lambda - mu(N) used for the window, Lu et
  al.'s and ours, would have a trapped engine complete sessions at a fixed low-reuse rate (D_low in theirs, lambda_miss in
  ours) and accumulate them at the excess. On the engine neither holds: ... (our earlier round-robin heuristic already gave
  the two-thirds numerically at 300k)."

### 14. CUT is called "a blind test of Corollary 3", which it cannot be in full
- **Where:** `v2_validation.tex:103`.
- **Problem:**
  - The cut comes 1200 s after the burst, so CUT tests model F's transient, not the corollary's asymptotic regrowth.
  - CUT-B cannot show recovery within 8700 s.
  - The naive comparator is "weak by construction" (its window is inflated by the burst cohort).
- **Evidence:** `notes/PREDICTIONS_icml_cut.md:205-217`.
- **Replace with:** "CUT (a blind test of model F's trajectory on both sides of the threshold of Corollary 3; within 8700 s
  it cannot show CUT-B's recovery) ...". Add the caveat on the naive comparator to the sentence at `:110-111`.

### 15. TOOLSLOW-W: status inconsistent, and the required disclosure is missing
- **Where:** `v2_validation.tex:100` ("TOOLSLOW-W (registered)") against `v2_evidence.tex:27` (status `\pending`).
- **Problem:**
  - Registration is asserted in one place and left pending in the other. No registration file is on this branch.
  - The lead's plan requires the test to be "written as chosen after d30's 1-of-3 result". The draft does not say this.
- **Evidence:** `COORD/scoop-2611.02543/TONIGHT_PLAN_2026-11-05.md:43-48`.
- **Replace with:** "TOOLSLOW-W (status pending; chosen after the 900 s slowdown of TOOLSLOW trapped 1 of 3 seeds): ..."

### 16. "Three independent checks" and "a referee" were AI subagents
- **Where:** `v2_theory.tex:91-92`; `v2_app_trapdata.tex:11-12`.
- **Problem:** readers will take these as independent human verification. They were subagents of the theory session, and
  none of them found Khanin et al. (2001).
- **Evidence:** `notes/THEORY_ICML_2026-11.md:954` ("Three independent referees (subagents)"), `:1024-1026`.
- **Replace with:** "Three independent AI-agent checks, each with its own code, found no wrong statement (they did not find
  Khanin et al.; see below); their fixes are applied."

### 17. Token-ratio inference: "most for Llama and vLLM" contradicts the token ratios
- **Where:** `v2_app_trapdata.tex:47-49`; also `v2_validation.tex:57-59` ("consistent with congested engines that compute
  prompt tokens 1-12% faster").
- **Problem:**
  - vLLM's measured token ratios (0.948-1.031) are at or below the composition prediction (1.012/1.019), and Llama's are
    0-4% above.
  - The largest excesses are on the H200 (2.6-8.5%) and the native pool (3.6-7.4%).
  - So faster token processing does not explain vLLM's and Llama's completion excess (4-21% above D).
- **Evidence:** `trap_check.md:27-32`, `:38-39` (columns "tok rate meas. / ref" and "tok ratio pred.").
- **Replace with:** "The measured token ratios exceed the composition prediction by up to 8% on the H200 and the native pool,
  which accounts for their completion excess; on vLLM they do not, and on Llama only partly, so the 4-21% excess there is
  unexplained."

### 18. "The 13 runs that lost the good state from empty" contradicts "16 from-empty collapses"
- **Where:** `v2_validation.tex:6`, `:63`; `v2_app_trapdata.tex:14` against `v2_validation.tex:85`.
- **Problem:** 16 from-empty runs collapsed. The 13 are those still stuck over [1500,3000) s. vLLM 2.5x and Llama 2.5x
  collapsed late (onset 1800 and 2000 s), and the 150k 1.30x run escaped.
- **Evidence:** `results/r15_dataonly/verify_d1d5/D5_e0b_from_empty_runs.csv` (16 rows with onset); `trap_check.md:7-19`.
- **Replace with:** "the 13 from-empty runs that were stuck over [1500,3000) s (of 16 that collapsed)".

### 19. Lu et al.'s hardware result is attributed to the full Basin design
- **Where:** `v2_related.tex:12-14`.
- **Problem:** "Basin ... combines fixed session priority, admission by predicted peak context, ... and beats six baselines on
  H200 hardware" mixes two systems. The hardware prototype used arrival-time ordering and current-context admission. The
  predictor-driven controller was evaluated only in simulation.
- **Evidence:** `other_paper.txt:586` ("The hardware prototype uses arrival-time ordering and current-context admission ...;
  the predictor-driven controller is evaluated in simulation").
- **Replace with:** "Their controller, Basin, combines fixed session priority, admission by predicted peak context,
  decode-memory lending and shedding; an arrival-time prototype (current-context admission) beats six baselines on H200
  hardware, and the full controller is evaluated in simulation."

### 20. The intro's head-to-head with Lu et al. drops the "post hoc" and scope qualifiers
- **Where:** `v2_intro.tex:56-59`.
- **Problem:** the verifier made the fitted-h comparison conditional on stating that it is our post-hoc reading of a model
  built for PD-disaggregated serving that does not aim to predict h. Section 4 carries these qualifiers; the intro does not.
- **Evidence:** `results/r15_dataonly/verify_d4/verify_D4.md:188-194`.
- **Replace with:** "Read post hoc on our colocated cells with one fitted hit curve (their model was built for disaggregated
  serving and does not aim to predict the hit rate), Lu et al.'s model puts the cliff ..."

### 21. The gap/R_M range is attributed to "every BURST run"
- **Where:** `v2_theory.tex:122` ("as it is in every BURST run (gap/R_M = 4.1-9.7, Table 7)").
- **Problem:** Table gapR covers the 24 BURST runs of the three original paired tests plus the exploratory vLLM runs. It
  does not cover the H200 and Llama BURST runs; the evidence base now has 30 registered BURST runs.
- **Evidence:** `paper/NUMBERS.md:642`; `paper/sections/theory.tex:83`.
- **Replace with:** "as it is in every BURST run of the SGLang 300k, native and vLLM tests (gap/R_M = 4.1-9.7, Table 7)".

### 22. The out-of-sample record omits a priori misses on Llama
- **Where:** `v2_entry.tex:55-61` ("misses included").
- **Problem:** the a priori Llama edge was one grid step high (a near miss). The list includes the 150k edge miss but not
  this one.
- **Evidence:** `paper/sections/frozen.tex:17`.
- **Replace with:** add "the Llama-3.1-8B edge (one grid step high)" to the list of misses.

### 23. "We do not score them as predictions", yet the appendix scores the drain estimate
- **Where:** `v2_entry.tex:96-98` against `v2_app_dataonly.tex:59-64`.
- **Problem:** the appendix applies Eq. 4 to R1 and R4 and reports that it is 19-39% early.
- **Replace with:** "... so we do not treat them as predictions of their model; Appendix C applies the drain estimate post
  hoc, next to our own single-phase variant."

### 24. "Complete proofs ... and the processor-sharing variant" overstates the appendix
- **Where:** `v2_theory.tex:90-91`.
- **Problem:** Appendix A gives only a sketch of the processor-sharing variant ("we do not write out the details").
- **Evidence:** `v2_app_trap.tex:231-239`; `notes/THEORY_ICML_2026-11.md:278-279`.
- **Replace with:** "Appendix A gives complete proofs of Theorems 1-2 and Corollaries 3-4, the (classical) stochastic
  counterpart and a sketch of the processor-sharing variant."

### 25. The control section says Lu et al. "prevent" the trap by termination; related work says "restored service"
- **Where:** `v2_control.tex:82` against `v2_related.tex:6`.
- **Problem:**
  - Lu et al. say termination "restores service within two minutes". At that point the engine was already degraded
    (110 active sessions, median TTFT about 9 s).
  - Their hardware prevention with controls active from the start (Basin, Continuum, ThunderAgent) goes unmentioned in the
    control section.
- **Evidence:** `other_paper.txt:146`, `:586`.
- **Replace with:** "Lu et al. restore service on hardware by terminating the burst sessions at the end of the burst
  (shedding), keep reuse with controls active from the start, rescue an established trap in simulation ..."

### 26. "Losses are lower bounds" does not follow from omitting the ITL condition
- **Where:** `v2_control.tex:42`; `v2_app_dataonly.tex:33`.
- **Problem:** dropping a condition raises goodput in both arms, so the loss, one minus their ratio, is not bounded in
  either direction. Losses of 100% are unaffected.
- **Replace with:** "(their per-token latency condition omitted, so goodputs are upper bounds; losses of 100% are unaffected)".

### 27. The from-empty excess is explained by "a young trap", which contradicts the exact fluid
- **Where:** `v2_app_trapdata.tex:38-40` ("Completions and backlog slopes run above the asymptotic values, as a young trap's
  should").
- **Problem:** at a fixed arrival rate, slope plus completions equals arrivals. In the model's own young-trap fluid the slope
  is above alpha while completions are below D (300k 1.35x: slope 0.0176 against alpha 0.0157; completions 0.0789 against
  D 0.0808). Both above, as in 9 of the 13 E0b runs, implies window arrivals above nominal (as for the E2 seeds) or a
  strongly curved N(t), not youth.
- **Evidence:** `trap_check.md:7-19`, `:20-22`; `support.json` `fluid.think_time."1.35"."0.0".completion_rate`.
- **Replace with:** "Both run above the asymptotic values. Since in model F they trade off at a fixed arrival rate, this
  points to window arrival rates above nominal (seed 0's plan) rather than to the trap's youth; we have not computed the
  E0b plug-in."

### 28. The fairness record on Lu et al.'s model is incomplete
- **Where:** `v2_app_dataonly.tex:54-58`.
- **Problem:** the draft notes that their own classifier uses throughput bounds but not how well it did: it flags all 17
  cache-first cases among 36 simulated deployments (28 of 36 correct). Their simulations also show the trapped load rising
  on the larger GPU (3.5 to 5.5 sessions/min). "State exactly what they have" calls for both.
- **Evidence:** `other_paper.txt:193`, `:237`.
- **Replace with:** add "their throughput-bound classifier flags all 17 cache-first cases among 36 simulated deployments
  (28 of 36 correct)".

---------------------------------------------------------------------------------------------------------------------------

## MINOR

29. **The value "M/E_S approx 28" holds only for the 300k pool.**
    - **Where:** `v2_theory.tex:114`, `v2_app_trap.tex:36`, `v2_conclusion.tex:4`.
    - **Problem:** across cells it is 13.6-89.8 (`verify_D4.md:78-85`).
    - **Replace with:** "up to M/E_S (about 28 at 300k, 14-90 across cells) concurrent requests".
30. **Adding the think time does change one window statistic by more than 1e-3.**
    - **Where:** `v2_theory.tex:115-116` and `v2_app_trap.tex:37-38`.
    - **Problem:** the mean cycle changes by 5 s (2-2.5%: V_mean 193.4 to 188.5, and 246.2 to 241.4; `support.json`
      `fluid.think_time`). The appendix says so itself.
    - **Replace with:** "changes the fluid's backlog slope, completion rate and served prompt by less than 1e-3 (the cycle is
      5 s shorter)".
31. **Corollary 4's "the same on both GPUs" is not a general hardware claim.**
    - **Where:** `v2_theory.tex:80-81`; `v2_validation.tex:7`.
    - **Problem:** it holds only for proportional cost vectors, which our H200 cell model is by construction
      (`THEORY_ICML_2026-11.md:247-249`, "not a general hardware claim"). The curves in Fig. 2 nearly coincide because the
      cells' omega are similar, not because Corollary 4 predicts it.
32. **Khanin et al.'s remark is quoted as "at each stage" in §2 but "at each node" in Appendix A.**
    - **Where:** `v2_theory.tex:101`; `v2_app_trap.tex:254`.
    - **Problem:** the source quote says "node" (`THEORY_ICML_2026-11.md:573-575`; `LIT_CHECK:39`). Use "node" or quote it.
33. **Theorem 1(d)'s centred form adds nothing as written.**
    - **Where:** `v2_theory.tex:42-43`.
    - **Problem:** f^m(u) + c = z^m(u + c)(1 + o(1)) holds for any constant c once f^m(u)/u -> z^m. To carry the "exact virtual
      origin" claim, state the rate (1 + O(((r+eps)/z)^n)) along orbits, from (f).
34. **"H = 1 for a geometric T" lies outside model F.**
    - **Where:** `v2_theory.tex:56`.
    - **Problem:** model F has K finite with G_K > 0, so untruncated geometric T is not in it; the note says this is a
      statement about the formulas (`THEORY_ICML_2026-11.md:222-224`). Add "(as a formula, K = infinity)".
35. **(F5) admits a zero initial mass.**
    - **Where:** `v2_theory.tex:21`.
    - **Problem:** "any finite pending mass" should be "positive", since the proofs need V_0 > 0, and lambda > 0 for parts
      (b)-(f). The appendix's (F6) has V_0 > 0.
36. **The two conventions for the 600k H200 crossing miss disagree.**
    - **Where:** `v2_entry.tex:58` says "4.4 sessions late"; `v2_app_dataonly.tex:51` says "(ours: 4.4 early)".
    - **Replace with:** use one convention, e.g. "predicted 4.4 sessions early".
37. **The appendix counts its analyses as four; there are five.**
    - **Where:** `v2_app_dataonly.tex:3`.
    - **Problem:** it has five data-only items: D5, D1, pool share, D2 and D4 (`PROVENANCE.md:1`).
38. **Two statistics treat correlated runs as independent.**
    - **Where:** `v2_validation.tex:75` ("30 independent plans") and `:83` (the 5.8% bound).
    - **Problem:** the plans are common random numbers across cells, which is why seed 1 dips everywhere, and the 50 runs
      reuse base plans (r0 and r1, the vLLM repeats, the BASIN runs). Say "distinct plans" and "treating runs as
      independent".
39. **A post-hoc account is stated as fact.**
    - **Where:** `v2_validation.tex:77-78` ("it says that the indeterminate seed-1 runs are traps").
    - **Replace with:** "it suggests that".
40. **Two places claim more coverage than the table gives.**
    - **Where:** `v2_validation.tex:16` (Table 1 caption, "against every stuck run of the E2 protocol") and `:43` ("every
      trapped run we have").
    - **Problem:** the table shows 36 of the 57 runs, and the check covers only runs stuck over their window.
41. **The draft says a faster GPU narrows the window; Proposition 3 proves less.**
    - **Where:** `v2_entry.tex:52`.
    - **Problem:** Proposition 3 is about the peak ratio, not the from-empty edge (`frozen.tex:42`; old `theory.tex`:
      "the upper end of the window when the from-empty edge does not bind").
42. **Two tag times are unverified.**
    - **Where:** `v2_validation.tex:94` and `:106`.
    - **Problem:** "pushed ... at about 00:25 CST" is unverified against GitHub's activity log, as the note itself requires
      (`THEORY_ICML_2026-11.md:901-903`). "02:25 CST" for `icml-cut-pred` is the tag/commit time (tagger epoch 1793867139),
      not a push time.
43. **The description of the frozen scoring rules omits three parts.**
    - **Where:** `v2_validation.tex:95-97`.
    - **Problem:** S4 also allows "or of the E2 fluid slope" (a post-hoc choice of reference), S5 has a second criterion
      (|slope - plug-in| <= 0.01/s), and the refutation rule is not stated (`PREDICTIONS_icml_trap.md:44-47`).
44. **The abstract says the backlog "never drains".**
    - **Where:** `main.tex:57`.
    - **Problem:** empirically it did not drain within the 7500 s horizon. The limitations say "does not escape" means
      within that horizon.
45. **SHED: model F is early too.**
    - **Where:** `v2_validation.tex:115-120`.
    - **Problem:** model F's 2,020 s to n_b is also early against the engine's 2,300-2,600 s (12-22%). The draft states
      only the quasi-static model's 25% miss.
46. **The cap is not an exit the theory allows.**
    - **Where:** `main.tex:57` and `v2_intro.tex:60` ("the two exits the theory allows"); `v2_control.tex:32-34` ("In
      model-F terms the cap keeps the admitted sessions below the onset").
    - **Problem:** the cap leaves model F, about which the theory is silent (`THEORY_ICML_2026-11.md:911-912`), and n_b is
      the first-principles model's onset, not model F's.
47. **Lu et al.'s Eq. 2 as printed reduces to f <~ 1/2.**
    - **Where:** `v2_app_dataonly.tex:55`.
    - **Problem:** 1/1.9 needs their unrounded cliff constant. Write "f <~ 1/2 (1/1.9 with the unrounded constant)".
48. **The 0.5-hit crossing and Lu et al.'s cliff are different hit levels.**
    - **Where:** `v2_entry.tex:47` and the `tab:lu` caption.
    - **Problem:** "1.4-1.9 times further out" compares their cliff, defined near h of about 0.3 (`other_paper.txt:158`),
      with our 0.5-hit crossings. Add "(their cliff is defined near a hit rate of 0.3)".
49. **Two source records disagree with the draft.**
    - **Where:** `THEORY_ICML_2026-11.md:269`; `paper/NUMBERS.md:51`.
    - **Problem:** the note gives the Kendall probability at 1.65 as 3e-54, but `support.json` gives 2.30e-54; the draft's
      2e-54 is right. NUMBERS.md gives the abstract as 1878 form characters; it now counts 1872 (margin 48).
50. **The high-load shortfall in Fig. 2(d) should be discussed after finding 5's fix.**
    - **Where:** Fig. 2(d) (`v2_validation.tex:10`).
    - **Problem:** with gamma/z the shortfall largely vanishes. Without the fix it is a visible, undiscussed bias (measured
      0.74-0.88 of gamma at rho >= 2.9).

---------------------------------------------------------------------------------------------------------------------------

## Checked and found consistent (no action)

- **Theorem statements against `THEORY_ICML_2026-11.md`.** I compared Theorem 1(a)-(f), Theorem 2 (decomposition; the H
  range for K >= 2; Gamma >= 1 and monotone; the near-threshold slope), Corollary 3 (apart from finding 2) and Corollary 4.
  All match sections 3-4.
  - Appendix A's proofs match section 4.
  - The renewal lemma, Lemma 2(iii)-(v) and Theorem 1(f)'s particular solution re-derive correctly.
- **Kendall numbers.** All six (0.35, 0.12, 4e-3, 1e-5, 4e-23, 2e-54) match `support.json` `kendall`.
- **Workload premium.** z_1 = 1.00154-1.00165, 53 brackets, c_60/c_1 = 17.4-22.8 and E[T]/kbar_c = 0.601-0.619 match
  `support.json` `premium*`.
- **Table 1.** All 90 entries match `trap_check.md:21-39`.
- **E0b table.** All 13 rows (78 entries) match `trap_check.md:7-19` and `:43-55`.
- **Validation summary numbers.** All match `support.json` `data.summary` and `trap_check.md`:
  - 57 runs in 20 groups, 13 E0b runs;
  - composition -6.6% to +7.7%, 50 runs within 3%, 54 within 5%;
  - 1.055 times D (range 0.90-1.21), seven runs below D;
  - backlog fraction 0.632, plug-in residual median -0.0022;
  - 49 and 18 runs within the two plug-in tolerances; 33 of 36 runs, 27 of 30 plans, 23 for always-trapped;
  - seed 1's window dip 0.8-8.9%;
  - self-similarity ratios 0.86-1.19 and 0.85-0.96.
- **Data-only results (D1, D5, D2, pool share).** All match `verify_D1D5.md`, `verify_D2.md` and `PROVENANCE.md`:
  - D5: 50 runs, 0.164, 99-103 h, 6100-6400 s, 5.8%, stock LPM 4 of 9;
  - D1: 16 runs, 558-6246 s, 727-15,453 turns, 4 hits in 5,937, 3-30 sessions, 4.1%;
  - pool share: 63-79%, 55-83%, 85-94%, 92-94%;
  - D2: 99.2-100% with 26 runs at zero, 100%, 0-1.7%, -0.3% to +0.9%, 4-57%, 45-97%.
- **Lu et al. head-to-head (Table tab:lu and D4).** All match `verify_D4.md` sections 3.1-3.4:
  - every Table tab:lu entry; mean errors 4.1/1.5/7.0 and 4.7/1.5/5.6;
  - 3.74 against 1.42, 3.57, 4.72, 4.05;
  - the H200 shift +6.7/+10.9 against +5.8/+6.6, and the per-GPU refit +6.74;
  - the affine fit 2.97 + 1.003 M/E (95% interval -0.08 to 6.02);
  - the f ranges; the drain errors 19-39%, 12-34% and 2-18%, and the late releases 24-64%, 14-51% and 2-22%.
- **Rescue numbers.** All match `NUMBERS.md:883-897`: 0.000-0.002, 139-324, release times 3980-6140 s, 2560-4720 s after
  release, 386-569 s per paused session, 38-78 and 222-230 session-hours, sessions paused, hit fractions and outstanding
  work.
- **Remaining paper numbers.** All match their sources:
  - SHED: 32.7, 2,020 s, 3,180 s, 2300-2600 s, 4100 s, 1,795 s, 56-59 and 355-378 sessions refused;
  - the cut illustration: 1.223, -0.3%, 59,655 s;
  - CUT predictions: rho' 1.145 and 0.846, the per-seed slopes, 27,100 s, five of six;
  - evidence counts: 23 of 30 runs trapped, 4 and 2 of the other 7;
  - H200: 2.71x and 1.63x; the window (1,2.0) narrowing to (1,1.3), and (1,2.5) with the 600k pool;
  - the workload: 551 tokens, 11,100 tokens, 16 times.
- **Citations.** Every `\citep` key in the v2 files and the abstract exists in `refs.bib` (50 keys). The new queueing
  entries (Grishechkin, Jean-Marie & Robert, Puha-Stolyar-Williams, Chen & Mandelbaum, Kumar, Dai & Weiss, Jennings & Puha,
  Dong, Kendall, Takacs, van den Berg et al., Bramson, Khanin et al., Feller) match `LIT_CHECK_trap_2026-11-05.md:11-24` in
  authors, venue, volume, pages, year and DOI. The attributions match its notes, except finding 12 (Bramson) and finding 32
  (Khanin's "node").
- **Honesty facts preserved** (`LEAD_HANDOFF.md`):
  - vLLM is "registered", and its mechanism-check rule was not met;
  - the H200 300k values for n <= 32 were seen by the first author;
  - 4 of 9 rescue release times fell outside +-15% (R4 19-22% late);
  - "persists" is defined as in the handoff;
  - the rescue wording is the TONIGHT_PLAN L586 wording (`v2_control.tex:85-86`, `v2_related.tex:17-18`, abstract).
- **Lu et al.'s paper.** The statements about it in `v2_intro.tex:22-26` and `v2_related.tex:3-11` match its text:
  - the 88% from one run, the termination run, Eq. 1, D_low and the drain statement, Eq. 2, Eq. 4 and hysteresis;
  - CONCUR's hit rate falling to 0.33 and recovering slowly (`other_paper.txt:61`, `131`, `146`, `208-273`, `249`, `586`);
  - exceptions are findings 4, 8, 19, 25 and 28.
- **Not verified.** I did not check Khanin et al. itself (not available offline) or Bramson (1996) beyond the literature
  check's note.
