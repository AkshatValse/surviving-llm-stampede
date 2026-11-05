# Reframed draft around the trap theorem (2026-11-05)

Branch `claude/reframe-draft-211a57` (worktree `.claude/worktrees/reframe-draft-211a57`), cut from the theory branch at
`e38735f` and merged with its later commits (`2f90267` CUT predictions, `0426a52` Khanin credit). Build:
`cd paper; pdflatex -interaction=nonstopmode main; bibtex main; pdflatex main; pdflatex main`. Nothing was posted or pushed
to any public place; no Nova job was touched; no Nova result of 2026-11-05 was read.

## Titles

Working title in the draft: **Inside the Trap: An Exact Theory of Throughput Collapse in Prefix-Cached Agent Serving**.
Options:
1. Inside the Trap: An Exact Theory of Throughput Collapse in Prefix-Cached Agent Serving
2. Trapped Servers Look Faster Than They Are: A Renewal Law for Prefix-Cache Collapse in LLM Agent Serving
3. The Renewal Law of the Trap: Exact Dynamics and Exits of Prefix-Cache Collapse in Agentic LLM Serving

## Abstract

The form text and its count are in `paper/ARXIV_METADATA.md` (1869 form characters with the `[pending: blind tests]` marker;
limit 1920).

## Structure (main text pp. 1-11, references, Appendices A-Z)

| new | content | from |
|---|---|---|
| 1 Introduction | the trap (Fig. 1), what is not ours (Lu et al.; Denning; metastability), the question, 5 contributions | new; Fig. 1 = old fig1 |
| 2 The trapped state | model F, Theorem 1 (a)-(f), Theorem 2, Corollary 3, Corollary 4, proof idea, classical vs new, idealization, why the trap does not heal | theory session's `theory_icml.tex`, rewritten; Khanin credit |
| 3 The renewal law on the engine | Fig. 2 (universality), Table 1, retrospective check, slope-rule account, persistence (D5, D1), blind tests (TOOLSLOW-W, CUT: predictions in, outcomes pending), SHED retrodiction | theory session's checks; data-only D1/D5 (verified) |
| 4 Entry | first-principles mu(n), onset n_b, speed law, out-of-sample record, Table 2 against Lu et al.'s model | old Sec. 6 (summary); D4 (verified) |
| 5 Two exits | starving (Corollary 3, SHED), restoring reuse (cap, R1/R4, Fig. 4, Table 3), D2 goodput, positioning against Lu et al. | old Sec. 5.3 and 7 |
| 6 Registered evidence | Table 4 of every registered test, honesty notes | old Secs. 4-5, 7 |
| 7 Related work | concurrent work (Lu et al., in full), thrashing/metastability, overloaded and re-entrant queues (new), LLM-serving queueing, agent KV | new; old Sec. 9 condensed |
| 8-9 Limitations, Conclusion | | new |
| App. A | model F proofs, remarks (PS variant, Kendall, Khanin, think time, convergence), the Corollary 3 cut illustration | theory session's `appendix_icml.tex`, edited |
| App. B | full trap tables (E0b, other E2 runs, plug-in, self-similarity) | `trap_check.md`, note sec. 6 |
| App. C | data-only results D5, D1, pool share, D2, D4 | `results/r15_dataonly/` |
| App. D-Z | the earlier paper: background, fluid model, method, results, first-principles model, frozen predictions, diagnostic, limitations in detail, proofs, protocol, prereg, timeline, provenance, ... | old sections, unchanged except the post-Lu fixes below |

## Contributions as stated (intro)

1. Exact theory of the trapped state (Theorems 1-2, Corollaries 3-4). The self-similar regime itself is credited to Khanin
   et al. (2001); claimed new as far as we found: the renewal recursion that carries every trapped state into it (with exact
   virtual origin and rate), the critical case, the youth premium decomposition, the recovery-threshold corollary.
2. Test across engines: retrospective on 57 stuck runs (8 cells); blind tests pending.
3. First-principles entry model with out-of-sample record and the head-to-head with Lu et al.'s model.
4. Control as two exits: starve (SHED) or restore reuse (cap; R1/R4 9/9, no shedding, release and persistence).
5. Registered evidence base.

## Every novelty claim and its evidence

| claim (where) | evidence | strength |
|---|---|---|
| Renewal recursion along FIFO orbits; convergence from any trapped state; exact virtual origin (Thm 1, Sec. 2) | complete proofs (App. A; note sec. 4), three referees; lit check: not found (Khanin et al. cover steady solutions only and leave general trajectories open) | proved in model F; "as far as we found" |
| Youth premium D/lambda_miss = H Gamma, sign conditions, truncation counterexample (Thm 2) | proof; support.py certificate for the workload | proved; workload positivity partly numerical (floating-point bracket below rho 1.04) |
| Trapped throughput overstates the recovery threshold (Cor 3) | proof; consistent with Lu et al.'s simulated recoveries (below their measured trapped departures); CUT blind test frozen (`icml-cut-pred`) | proved in model F; engine test pending |
| Model F matches the engine (Sec. 3) | 57 + 13 runs, nothing fitted to trap data | retrospective only |
| Onset with a tool-call term; faster GPU moves it out (Sec. 4) | Prop. nb; H200 measured +6.7/+10.9 sessions | earlier paper's result; held out of sample in 5 cells |
| Our onset beats Lu et al.'s fitted hit-curve reading (Table 2) | D4 verified: 4.1 vs 1.5 sessions (5 cells), 3.7 vs 1.4 with their constant fitted in sample | post hoc reading of their model; stated as ours |
| Registered, replicated rescue of an established zero-hit trap at the same load, without shedding, with release and persistence (Sec. 5) | R1/R4 9/9 | registered; Lu et al. have prevention by shedding on hardware, late rescue in simulation, CONCUR slow recovery in one hardware run |

## Claims changed or dropped

Against the withdrawn r10/arxiv text:
- No priority claim for the phenomenon, the loop, the fluid model, the window or the drain threshold (Lu et al. state that
  arrivals below D_low drain the population; Corollary 3 is stated as a sharpening).
- "KAIROS ... asserts, untested" no longer stands as the state of the field; Lu et al. are cited wherever the old text
  described the field (intro, related, model hysteresis, diagnostic, frozen_app rescue, results hit-collapse and GPU scaling,
  prior-model paragraphs, appendix_supp, scoop-check line).
- "Measured basin boundary on an LLM engine" is no longer a headline contribution (Lu et al. bracket a surge on hardware and
  map trap frequency in simulation); the BASIN bracket is part of the registered evidence.
- "Recovery without a cap needs a rate below lambda_miss is untested" became: proved within model F, tested on the engine by
  SHED's full stop and the CUT runs (pending).
- The rescue claim is narrowed to "registered, replicated rescue of an established zero-hit trap at the same offered load,
  without shedding, with release and persistence" (Lu et al. L586).

Against tonight's single-agent data-only claims (after independent checks):
- D1: 15 of 16 runs have zero hits after the last trigger session (TOOLSLOW: 4 of 5,937); "5.8% of the population" was not
  reproducible (at most 4.1% of sessions present).
- D5: 99-103 trapped hours (not 104.5); stock LPM 4 of 9 escaped (not 5 of 10).
- Pool share: 63-79% holds only for the SGLang 300k runs; 55-94% across cells.
- D2: first-hour loss 99.2-100% (not 99.4); first-hour costs of the cap are reference-dependent.
- D4: "nearly vacuous" dropped (unfair: f moves along the curve); the window comparison dropped (needs bounds Lu et al. do not
  specify for colocated serving); the drain comparison reworded (Eq. 4 is for resident-first ordering; our own single-phase
  variant is also 12-34% early, so the gain is the two-phase structure); the 1.9 C/cbar column is not presented as their
  prediction; the onset comparison kept with corrections.
- Theory novelty: narrowed after the literature check found Khanin et al. (2001); random turn counts are not claimed (their
  closing remark covers fractional exits); Corollary 4 is their normalization.
- SHED: model F's 2,020 s (to n_b) and the hardware's 2300-2600 s (hits back) are reported; pred2's 1,795 s is called early by
  about a quarter.

## Open items

- TOOLSLOW-W and CUT outcomes, and REPLICATE-EDGE and the 15 s slowdown at 1.65x if the lead wants them in: `\pending{}`
  slots in the abstract, Sec. 1 (contribution 2), Sec. 3 (Blind tests), Table 4, App. J/R (`appendix_supp`, `limitations`).
- The repository URL (`\repourl`) and the code-availability paragraph.
- Dr. Jannesari's review; the authors' choice of title.
- Length: main text pp. 1-11 in this format; ICML's 8 pages would need Table 4 or Sec. 7 shortened.
- The old sections now in the appendices repeat material; a later pass could cut them.

## Adversarial review (2026-11-05, an independent AI referee; report in `results/r15_dataonly/review/`)

7 MUST-FIX, 21 SHOULD-FIX, 22 MINOR; the proofs held up (Lemma 2(iv), Theorem 1(b), (c), (f), Theorem 2(i), (iii), Corollary 3
re-derived), all 90 entries of Table 1, the from-empty table, the summary statistics, the data-only numbers and all 50 citation
keys matched their sources. Applied:
- **Gap-slope constant.** `analysis/theory/icml/measured.py` regresses each gap on the turn's completion time, so model F's
  constant is gamma/z = 1 - 1/z, not gamma. Recomputed (`analysis/theory/icml/gap_slope_completion_time.py`,
  `results/theory/icml/gap_slope_completion_time.json`): E2 median ratio 1.01 (was 0.98), mean 0.96; E0b mean 1.03, range
  0.63-1.37. Table 1, Fig. 2(d) (`figures/theory_icml/fig_trap_universality.py` now plots 1 - 1/z), App. B, abstract and intro
  updated. The frozen rule S2 compares with gamma (1.3% off at 1.35x; noted in Sec. 3).
- **CUT** written as model F's predictions, not outcomes, with the theory session's caveats (young-trap transient; CUT-B cannot
  show recovery within the run; weak naive comparator); seed 1 of CUT-A is predicted to have a slightly negative slope.
- **Corollary 3** now conditional on D > lambda_miss (true for our workload at every load checked).
- **Threshold novelty** withdrawn: the drain threshold is the classical busy-period condition and Lu et al. state it for
  D_low; claimed new is only that the trapped throughput exceeds it.
- **Lu et al.'s simulated recoveries**: the draft no longer calls them "consistent with" Corollary 3 (with a host tier one seed
  in three recovered above the trapped departures; their systems keep some reuse).
- **Workload scope**: the premium and "0.6 to 0.8 of the excess load" are stated for our workload and loads; "matches 57 runs" is
  stated for the runs taken together, retrospectively.
- "No trapped FCFS run escaped" narrowed to runs trapped by a burst or the tool slowdown (one FCFS from-empty collapse recovered).
- Also: Lu et al. posted first (abstract), their hit rate falls to about 0.3 (conclusion), the Basin hardware result is an
  arrival-time prototype, critical-case novelty qualified against Bramson (1996, Kelly type), the AI referees named as such,
  completion ranges split E2/E0b, the "13" from-empty runs defined, TOOLSLOW-W status pending and its design history stated,
  the Llama edge near miss added to the record, goodput-loss bounds corrected, Lu et al.'s classifier result added, minor fixes.
- Not applied (left for the authors): the main text now runs to p. 12 (cut candidates: Table 4 to the appendix, the two last
  related-work paragraphs, a shorter Limitations).

## Messages sent

- To the theory session: the gamma/z issue in `measured.py` and S2, the note's sec. 5 sentence on Lu et al.'s simulated
  recoveries, and the Kendall value 3e-54 (support.json: 2.3e-54).
- To the lead session: the draft is ready, with this note's summary.

## Lead's advisor-eyes edits (2026-11-05, applied on Akshat's instruction to follow the lead)

- Novelty: Reiman (1988) and Dai & Kurtz (1995) verified on Crossref and cited; Theorem 1(b) is now the fluid counterpart of
  heavy-traffic state-space collapse, not new; Theorem 2 is the visit-indexed analogue of the overloaded processor-sharing
  property (departures lambda E[e^{-alpha S}] can exceed 1/E[S]); new are the renewal recursion, the premium's turn-count and
  cost-growth factors, and Corollary 3's consequence. Khanin et al.'s open question is the uniqueness of non-steady trajectories.
- "Exact" calibrated: abstract ("We analyse an idealized model of the trapped state exactly"), intro contribution title,
  related work, conclusion ("Idealized, the trap has an exact law"), section 2 title; working title now "Inside the Trap: A
  Renewal Law for Prefix-Cache Collapse in LLM Agent Serving" (options kept in ARXIV_METADATA.md).
- Corollary 3 scoped to model F in the intro and conclusion until CUT reports; Lu et al.'s GPU-only point added in Sec. 5.
- CUT: the registered rule (11b0e4e, tag r15-cut-reg) replaces "weak by construction"; comparator values computed from the frozen
  plans; pass and fail outcome drafts are LaTeX comments in v2_validation.tex.
- Abstract: the registered-evidence sentence (30 of 30 BURST runs at zero hits, every NOBURST run good) replaces the
  first-principles sentence; "refusing arrivals sheds sessions"; 1852 form characters.
- Terms (E2, BURST/NOBURST/CAPPED, BASIN, SHED, TOOLSLOW, E0b, LPM) defined at the start of Sec. 3.
- Timeline: the registered experiments of Sec. 6 predate Lu et al.; the theory and the blind tests came afterwards (the lead's
  wording said "our experiments", which would include tonight's runs, so it was narrowed). Push times recorded.
- AI-referee sentences shortened; the approved AI-use statement is unchanged.
- Housekeeping: SHED cites the lambda = 0 busy period directly; the from-empty backlog excess is stated; "single runs, as their
  run accounting implies"; the head-to-head is "against a post-hoc reading" of Lu et al.'s model.

## PAPER_INPUT part 1 (TOOLSLOW-W, REPLICATE-EDGE), filled 2026-11-05

Source: the lead's `notes/PAPER_INPUT_r15.md` sections 1, 2 and Verification (branch `r15/tonight`, commit 24dcc91); every
number there was independently recomputed from the raw CSVs. No Nova result was read by this session.

- Abstract: "Blind, it matched 3 runs trapped by a tool slowdown alone; \pending{CUT}." 1903 form characters (margin 17), so
  the CUT clause has about 30 characters unless something else is trimmed.
- Sec. 1, contribution 2: the pre-registered tool slowdown trapped 3 of 3 runs with paired no-burst runs good, and the frozen
  predictions met all four pooled scores; CUT still pending.
- Sec. 3, TOOLSLOW-W item: outcome TRAPS with per-run slopes, controls, the 900 s arm's 1 of 3, the pooled S1-S4 scores, per-run
  composition and S5, "not refuted", and that every frozen model called it (so it tests the law on a trap with no burst, not the
  models against each other). Caveats kept: tolerances set on committed runs; designed after d30 and after reading simulator
  outputs, so blind in outcome only.
- Gap slope written as 1.075 gamma (the note's 3-decimal value): the per-run slopes 0.0195513 / 0.0102881 / 0.0121922 over gamma
  0.013034 give 1.0749, so the suggested "1.08" would be a double rounding (1.07 at two decimals).
- Sec. 6, Table 4: TOOLSLOW-W outcome cell filled. Sec. 4: the out-of-sample record now adds that the 1800 s slowdown trapped 3
  of 3 as predicted, next to the 900 s miss. Sec. 8: the blind runs are named (three TOOLSLOW-W runs in one cell, six CUT runs);
  the REPLICATE-EDGE sentence follows "single runs per rate". The frozen-predictions appendix (frozen.tex), fresh-seed row: one clause on the same-plan
  replicates.
- Still pending: CUT (abstract, Sec. 1, Sec. 3, Table 4, Sec. 9, App. appendix_supp lines on CUT, limitations.tex), and
  `\repourl`.
