# Triage of the read-only review of the reframed draft at df31480 (2026-11-05, 07:20–07:52 CST)

Two independent reviewers read the draft (branch `claude/reframe-draft-211a57`, commit `df31480`) and changed nothing:
an evidence-and-honesty auditor (`AUDITOR.md`) and a fresh-eyes referee for a performance-modelling venue
(`REFEREE.md`). This file is the lead's triage. Findings are cited as A# (auditor) and R# (referee); the full text,
evidence and proposed wording are in those two files.

Referee's overall read: the mathematics is correct and honestly hedged, with no false statement in Theorems 1–2 or
Corollaries 3–4. As it stands, the paper is a weak reject or major revision at a performance venue. With the one-day
fixes it becomes "a credible modelling-and-measurement paper, though not a queueing-theory one".

## APPLY NOW (reframe session, with PAPER_INPUT part 2b), in this order

**Must-fix**
1. **A1, priority scope.**
   - The intro and §6 claim that the registered experiments were designed, registered and run before Lu et al. That claim
     now covers Table 4, which includes TOOLSLOW-W, TOOLSLOW-D15 and CUT, all registered on 2026-11-05, after Lu et al.
   - Scope it to the tests up to SHED/TOOLSLOW (r14) as A1 proposes. The theory of §2 and the r15 blind tests came after.
   - The trap-state predictions' author had read the Lu et al. text.
2. **A2, TOOLSLOW-D15 missing.** The registered r15 cell T2 (`sglang-fcfs-r1-toolslow-d15-165`) is absent. Add:
   - its Table 4 row;
   - a §3 bullet with the frozen calls: simulator S/G/G → NO-TRAP; pred2 fluid TRAPS; pred2 per-seed P(TRAPS) 0.58;
   - the outcome from part 2b, and its S1–S5 score if any run is stuck;
   - the §8 and intro counts.

   "Only … three TOOLSLOW-W runs … and the six CUT runs" and "Two blind tests followed" are false as written.
3. **A3 = R1, persistence does not discriminate.** Every constant reading also leaves CUT-A stuck to 8700 s: the registered
   naive one leaves about 50–130 sessions, far above n_b = 32.7.
   - Persistence rules out only a drain at the completion rate an operator saw just before the cut. That is D_pre over
     [1800, 2400) = 1.70 / 1.65 / 1.21 λ_ref, which would have reached the onset near 6300 s in seeds 0 and 1.
   - Say exactly that. It is the operator-facing content of Corollary 3, and it is real.
   - "Three results single out model F" becomes "one result singles out model F": the late-window slopes, compared post hoc
     against frozen values. The completion rate is supporting evidence, also post hoc at the 0.004 /s cut (A4).
4. **R2, λ_ref vs λ_miss.**
   - Define λ_ref in the main text before first use: the all-miss session rate measured on each cell with the radix cache
     disabled (E0a, 32 sessions; 0.0715 sessions/s on A100 300k).
   - Say that λ_miss is model F's cost-model value, with λ_miss/λ_ref = 0.96–1.035 across cells. Take this from
     `results/theory/icml/support.json` and check it.
   - Fix method.tex:11, v2_control.tex:28 (Lu et al.'s own reference rate; verify the 12 sessions/min figure in
     `COORD/scoop-2611.02543/extract_theirs.md` before using it) and v2_validation.tex:68.
5. **R3, Corollary 3 is not new as mathematics.**
   - Drop it from the novelty claims (related l.44–46, intro l.53–54, theory l.114–115). It is the operational reading of
     Theorem 2 with the classical drain condition, and its processor-sharing counterpart follows from
     `jeanmarie1994transient` (already verified in `notes/LIT_CHECK_trap_2026-11-05.md`).
   - What is new is the engine test of that reading, and the turn-count and cost-growth factors of the premium.

**Should-fix (honesty and evidence wording)**
- **A4.** The completion-rate comparison is post hoc at 0.004 /s. At the registered ±0.006 a constant (0.080 /s) also fits.
- **A5.** Use one sentence everywhere about what singles out model F: abstract, intro, §3, §5, §8, §9. Suggested: "the
  registered rule rejects only the constant-throughput readings; the late-window slopes, scored post hoc against frozen
  values, single out model F".
- **A6.** The main text must also report the failed fresh-seed replication of the from-empty edge. This is a listed honesty
  fact. At 300k, 2.5 λ_ref was stable in 3 of 3 fresh seeds, so the replication rule was not met; in realized rates the edge
  lies at 2.665–2.726 λ_ref. Report it next to the successful same-plan replication (conclusion l.14–17).
- **A7.** Contribution 2 should say "lasting 1800 s" and "designed after a 900 s one trapped 1 of 3".
- **A8.** Report T1's frozen exploratory misses:
  - outstanding requests at 3300 s missed the "within 5" reference by 8 and 6 (seeds 0 and 2);
  - pred2's plan walk undercounted sessions alive at 3000 s by 7–18.
- **A9.** The record tables claim to be complete:
  - add the round-15 rows to the ledger, the frozen-prediction tables and the timeline;
  - cite the 11-05 provenance exports (`push_times_2026-11-05.tsv`, `github_activity_2026-11-05.json`,
    `sacct_cited_jobs_2026-11-05.txt`);
  - mark `configs/r15_edge_replicate.yaml` EXPLORATORY.
- **A10.** Delete appendix_supp.tex:109's "the only real runs that lowered the rate after a trap".
- **R5 (wording only).** In the intro: "the rule rejected the two constant-throughput readings it was built against; a
  flat-backlog reading fits as well over [3000, 8700) s; post hoc, the late backlog followed model F's frozen slopes."
- **R7.** The abstract's TOOLSLOW-W clause states a single cell, blind in outcome, against pre-set tolerances. Shorten as the
  1920-character limit requires.
- **R8.** In the retrospective summary:
  - give the per-run range of the gap ratio (0.04–1.81) next to the pooled median;
  - give distinct-plan counts next to run counts (36 registered-protocol runs on 30 plans);
  - after "up to 2.4 times", add "(one from-empty run at 6.5 λ_ref)".
- **R9 (wording only).** In the abstract and intro, do not credit the Perron root with the classical drain condition (part
  (a)). Say part (a) is classical and the Perron root governs growth above it.
- **R10.** Credit the classical structure:
  - Eq. (1) is a discrete renewal equation of Lotka–Leslie type; cite `feller1968introduction`, already verified.
  - Cite Kleinrock 1967 (JACM 14(2):242–261), Coffman & Kleinrock 1968 (JACM 15(4):549–576) and Frolkova, Foss & Zwart 2014
    (AAP 46:76–101) in §7. Their metadata is verified in the LIT_CHECK note. Confirm each title by DOI or Crossref before
    adding a bib entry; if a title cannot be confirmed, do not add the entry, and say so.
  - Add no other new citations.
- **R11.** State model-F results as model-F results, not as engine facts (control l.26–27, related l.16–17, theory l.62).
- **R16 (hedge only).** "Points to window arrival rates above nominal" is unchecked. Write "may reflect … (not checked)", or
  check it from the committed plans.
- **R18 (intro wording).** Give the measured and predicted H200 cliff shifts instead of "as predicted".

**Should-fix (math presentation and clarity)**
- **R4.** Restate Theorem 1(d) so the virtual origin carries content:
  - u_n + c = B z^n + O((r+ε)^n);
  - hence V(u) = γ(u + c) + O(·) and N(u) = α(u + c) + O(·);
  - the errors vanish absolutely when r < 1;
  - merge (f) into it;
  - add "for n ≥ K − 1" to the exact identity at l.92.

  Check every line against the proof in v2_app_trap.tex:164–176. If anything does not follow, leave the statement, flag it
  and tell the lead. Do not invent a proof step.
- **R13.** Notation:
  - u* for the virtual origin;
  - n_cap for the cap (the `\ncap` macro exists);
  - α_PS for the processor-sharing exponent;
  - ν^z only, for the tilted mix;
  - align the assumption lists, since the proof of Corollary 3 cites (F6).

  Leave Fig. 3's legend; its caption already notes it.
- **R14.** Define M, E_S and churn at first use, give the formula for h_n, and add the Proposition-A remark. In
  model.tex:28, write "of the closed system".
- **R19.** Fig. 2 caption: the curves "nearly coincide because the cells' ω are close (E[T]/k̄_c = 0.60–0.62)", not "as
  Corollary 4 predicts".
- **R20–R21, R23–R25 (nits, apply):**
  - Theorem 2's K = ∞ remark and the z ≥ z1 condition;
  - Corollary 3: "[λ_miss, D(λ)) … does not empty model F's queue";
  - self-similarity ranges;
  - "less than 0.02%";
  - cite Fig. 3;
  - wrap the overfull table;
  - the conclusion's "known self-similar regime" with `khanin2001steady`.

  Fig. 2(d)'s clipped title needs a figure re-export. Skip it if the plotting script is not at hand, and list it.
- **R22.** Put the rescue's cost (386–569 s average wait per paused session; 45–97% of the first hour's goodput) in the
  intro. Put it in the abstract only if space allows.
- **A11–A24 (auditor nits, apply all).** In particular:
  - A12: call the theory's CUT secondary predictions "frozen", not "registered";
  - A13: five rule changes, not four;
  - A14: "does not clear", not "does not drain";
  - A16: scope "every stuck run completes 1.10–2.40 λ_ref" to the retrospective check, since CUT-A seed 0 is at 1.05;
  - A17: "blind in outcome";
  - A18: the frozen qualifier on H2;
  - A19: H200 seen by the operating agent and the first author; no blind simulator prediction;
  - A20: BASIN-1 blind by access only;
  - A21: vLLM's push came after two of its jobs had started;
  - A22: Corollary 3 is proved in model F; CUT-A is consistent with it;
  - A23: "in the fluid," on the operator sentence;
  - A24: the frozen TOOLSLOW caveat.

## DEFER (propose at the meeting; do not do tonight)

- **R9 (structure).** Split Theorem 1 into a Lemma (the orbit recursion), a Theorem (ρ > 1: convergence from any state, the
  affine law, rate r/z per generation) and a Proposition collecting the classical parts (a), (b) and (e). Demote Corollary 4
  to a Remark (R19). This is a theorem-structure decision for Akshat and Dr. Jannesari.
- **R15.** One evidence-ledger table in §3 (claim, runs and distinct plans, status, when the tolerance was set). Move hashes
  and clock times to the provenance appendix.
- **R5, R6, R16, R17 (new analyses on existing data, for the theory session):**
  - CUT-A's P(PASS) under the flat-backlog alternative (re-run `cut_predict.py`'s Monte Carlo);
  - the youth premium rescaled by each run's token-rate ratio (the referee's quick check: all runs stay at 1.10–1.89 λ_ref,
    mean 1.04 D);
  - plan window arrival rates for the 13 from-empty traps;
  - per-run standardized residuals against model F's stochastic SD.

  Each would need a committed script and output before entering the paper.
- **R12.** Report backlog slope/α in Table 1 instead of a fraction of λ − λ_ref (the referee's check: mean 0.99, median
  1.05). It needs a committed recomputation from `trap_check.md`/`support.json`.
- **Top-5 item 5.** Shorten §4, move the Lu et al. comparison and the provenance detail to the appendix, and prune the
  reused appendices.

## REJECTED

- None outright. R6's abstract change (rescaling the premium) is deferred because the claim as written ("completions above
  the all-miss capacity in every run") is a measured fact; the attribution caveat already sits in the youth-premium bullet.
