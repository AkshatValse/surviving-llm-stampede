# Restructure into one theory-led preprint (2026-11-05)

Branch `claude/reframe-draft-211a57`, on top of 524fc0e (the reframe draft after its final fix round). Requested by the lead
session ("Nova preprint scoop assessment") on Akshat's direction, quoted verbatim in its message: "My recommendation is to publish
one shorter, theory-led preprint for now: keep the strongest stampede and recovery experiments as its empirical foundation, and
reorganize the duplicated old manuscript into a focused appendix. Then consider a second paper only if the stampede framework
develops a genuinely separate question and substantial new evidence, such as a well-controlled prevention or recovery method. The
two papers should cite each other and be clear about reused experiments." Timing: "ASAP". No split into two preprints now.

## Build

`cd paper; pdflatex -interaction=nonstopmode main; bibtex main; pdflatex ... main; pdflatex ... main`: every step exits 0; no
errors, no undefined references or citations, no multiply defined labels, no overfull boxes, no "Float too large".

- After the audit fix round (below): 65 pages (64 at 8a212bd, 94 before the restructure). Main text pp. 1-12: Section 8 and the
  three unnumbered statements end on p. 12, about four lines short of its foot, and the references start on p. 13; references
  pp. 13-17; appendices pp. 18-65 (A 18, B 21, C 22, D 26, E 26-63, F 63).
- 8 figures (Fig. 4 is the MIRROR placeholder in App. C), 20 tables. Abstract 1917 form characters, margin 3
  (`COORD/release-tools/count.py`; 1913 before the audit's HON-16). Title and `\repourl` unchanged.
- Red `\pending{}` markers (9, counted by the strict packager in the sources and in the PDF): `\repourl` and the MIRROR outcome
  (Section 1, Section 4.1, Table 2, the Fig. 4 box and caption, App. C, Tables `tab:ledger` and `tab:frozensum15`).
- Commits: 4f62b4c (first restructure, 63 pages), 8a212bd (second pass), ce56977 (merge of fdb80c9), then the audit fix round.

## New outline

Main text (sources `paper/sections/v3_*.tex`):

| Section | Page | Content |
|---|---|---|
| 1 Introduction | 1 | Fig. 1 (E2 time series); what is not ours (Lu et al. first; the stampede experiments registered and run 21 Oct - 1 Nov, before them; the theory, the r15 blind tests and MIRROR after them); the question; four contributions |
| 2 The stampede: registered tests | 3 | Table 1 (the nine registered stampede and recovery tests); workload and engines; calibration and the registered rule; what the tests show; persistence and the trigger; what the record does not show |
| 3 Model F: a renewal law for the trap | 4 | Model F (F1)-(F6); Lemma 1, Theorem 1, Proposition 1, Theorem 2, Corollary 3, Remark 1; proof idea; what is new; idealization; why the trap does not heal |
| 4 The renewal law on the engine | 6 | Fig. 2 (trap universality); Table 2 (evidence ledger); retrospective check; the slope rule post hoc; blind tests TOOLSLOW-W and TOOLSLOW-D15; 4.1 A predicted reversal of the youth premium (MIRROR; outcome pending) |
| 5 What trapped throughput does not tell | 9 | Fig. 3 (rescue); Corollary 3 read for an operator; CUT-A and CUT-B; SHED; the cap rescue; what the rescue does and does not show |
| 6 Related work | 11 | Lu et al. in one paragraph (full comparison in App. F); thrashing, metastability and overloaded queues; LLM serving and KV management |
| 7 Limitations, 8 Conclusion | 11-12 | |

Appendices:

| Appendix | Page | Source |
|---|---|---|
| A Model F: proofs and remarks | 18 | `v2_app_trap.tex`, proofs regrouped for the split |
| B Model F against the engine: full tables | 21 | `v2_app_trapdata.tex`, now with the per-cell table (ex-Table 1) |
| C The blind tests in detail | 22 | `v3_app_blind.tex`: the TOOLSLOW-W, TOOLSLOW-D15 and CUT text of the old Section 3, verbatim; MIRROR in full (design, predictions, rules, provenance; outcome pending) with the Fig. 4 placeholder |
| D Persistence, the trigger, pool occupancy and goodput | 25 | `v2_app_dataonly.tex` without D4 |
| E The stampede experiments | 26-62 | `v3_app_stampede.tex`, assembled from the old manuscript's appendices (D-T) |
| F Lu et al.'s concurrent work and other systems in detail | 62 | `v3_app_lu.tex` |

Appendix E: E.1 Dates and reuse (new); E.2 Workload, engines and harness; E.3 Calibration and the from-empty edge; E.4 The
quasi-static model, the window and the cap; E.5 The registered paired tests; E.6 Dose response, tool slowdown and arrival stop; E.7
The rescue tests; E.8 Other orderings (exploratory); E.9 The entry model (the old Section 4 and the first-principles model); E.10
Frozen predictions and their outcomes; E.11 The registrations; E.12 The calibrated simulator, prediction rounds and timeline; E.13
Provenance; E.14 Proofs of the quasi-static results; E.15 Threats to validity.

E is assembled from whole paragraphs, floats and environments of the old files, kept verbatim except for demoted headings and the
reference fixes listed below. The scripts are in the session scratchpad (`assemble.py`, `fix_refs.py`, `fix_threats.py`); the old
files stay in `paper/sections/` (no longer input by `main.tex`), so anything cut can be restored from them.

## Theorem split (DEFER item (a) of `notes/review_df31480/TRIAGE.md`)

- Lemma 1 (the orbit recursion): the old Theorem 1's recursion with `h_n`, plus the rate `rho - 1` of the remaining work while busy
  and the exact identity `u_{n+1} = V_tot(0) + sum_k lambda c_k G_k u_{n+1-k}` for `n >= K-1` (old proof of (d), continued).
- Theorem 1 (every trapped state converges), `rho > 1`: (a) the old (c), the limits `gamma = z - 1`, `alpha`, `D`, the tilted mix;
  (b) the old (d), the affine law with the virtual origin `u*`, with "relative to z^n the transient is O(((r+eps)/z)^n)" added as a
  restatement of its O-term (the "rate r/z per generation" of the triage).
- Proposition 1 (the classical parts): (a) the old (a), the busy period, now stated "if and only if rho < 1" (the "only if" is the
  bound `V >= eta V_tot(0)` already in the proof of the well-posedness lemma) and "with arrivals stopped at V_tot(0)" (already in the
  old proof, used for SHED); (b) the old (b), the critical case; (c) the old (e), the near-threshold expansion. Credits after it:
  work conservation and Kendall for (a); the fluid counterpart of state-space collapse (Reiman; Dai and Kurtz) for (b); an
  elementary expansion for (c).
- Remark 1 (invariance): the old Corollary 4, unchanged in content (a numbered remark, `\newtheorem{nremark}{Remark}`).
- Theorem 2 and Corollary 3: statements unchanged; references updated.
- Appendix A: the proof of the old Theorem 1 is regrouped into proofs of Lemma 1, Theorem 1 and Proposition 1; no step is new.
- Reference map applied everywhere (main text and appendices): old 1(a) -> Prop. 1(a); old 1(b) -> Prop. 1(b); old 1(c) -> Thm 1(a);
  old 1(d) -> Thm 1(b); old 1(e) -> Prop. 1(c); Cor. 4 -> Rem. 1.

## Evidence ledger (DEFER item (b))

Table 2 in Section 4, one row per claim: claim | test and runs | status (pre-registered/registered, blind in outcome,
retrospective, post hoc) | result | appendix. 16 rows: four stampede claims, four retrospective model-F laws, five blind tests
(including the MIRROR row, pending), two exits, the entry model. Hashes and clock times are in Appendix E.11-E.12, as R15 asked.

## Shortening and the Lu et al. comparison (DEFER item (d))

The old Section 4 (entry) left the main text (Appendix E.9); the Lu et al. comparison (old Section 7's concurrent-work paragraph
in full, old Table 2 and "Against Lu et al.'s empirical model", the Lu et al. remarks of old Section 5, D4) is Appendix F. DEFER
item (c)'s two open analyses (R5, R17) were not done.

## What moved where

- Old 1 Introduction -> 1, rewritten shorter. Contributions now: (1) the renewal law, (2) the law on the engine, (3) what trapped
  throughput does not tell (CUT, SHED, rescue), (4) the evidence base and the entry model (App. E.9) with the ledger.
- Old 2 (the trapped state) -> 3, with the split; "What is classical and what is new" became the credits after Proposition 1 and
  the paragraph "What is new" (Lotka-Leslie, Khanin et al., the processor-sharing analogue, Corollary 3 not new as mathematics).
- Old 3 (validation): the retrospective check, the slope rule and TOOLSLOW-W/TOOLSLOW-D15 -> 4, compressed; their full text, with
  the frozen exploratory measures (hits and misses), and the full CUT text -> App. C verbatim; CUT -> 5, compressed; the SHED
  retrodiction -> 5; old Table 1 -> App. B; the persistence paragraph -> 2.
- Old 4 (entry) -> App. E.9 (verbatim, with Fig. 8, `fig:fpmu`); old Table 2 and its paragraph -> App. F.
- Old 5 (two exits) -> 5; old Table 3 (rescue) -> App. E.7; its Lu et al. remarks -> App. F.
- Old 6 (registered evidence base) and old Table 4 -> 2 (Table 1, without the round-15 rows, which are ledger rows).
- Old 7 (related) -> 6 (the concurrent-work paragraph shortened; the full one, with the Basin footnote, -> App. F).
- Old 8-9 -> 7-8, shortened; the pointer to "Limitations in detail" now goes to App. E.15.
- Old App. A, B -> A, B; old C -> D (D4 -> F); old D-T -> E (condensed) and F.

## Claim and wording changes

No claim's content changed and no new number was introduced except those listed in `paper/NUMBERS.md` under "Restructure".
Wording that changed:
- The reuse statement: the stampede experiments "were designed, registered and run between 21 October and 1 November 2026, before
  it appeared" (Section 1, App. E.1). The lead's message said 22 October; Table `tab:timeline` shows Stage 0 passing and Stage C
  submitted on 10-21, so the text says 21 October. The last of these jobs ended on 11-01 (SHED/TOOLSLOW, H200 600k and Llama E2).
- Section 5 summarizes the CUT rule history as "five ways: three stricter, one stricter for two seeds and looser for the third,
  and one looser" (App. C keeps the full list unchanged).
- The ledger's entry row says the five blind cells are "3 in time, 2 by access only, one partly seen" (the H200 300k cell, n <= 32
  seen by its operating agent and the first author).
- Section 2 restates the CAPPED result as "prevented the trap in all 30 CAPPED runs of the five paired tests", with the 405-471 s
  mean wait "in E2" (corrected in the second pass; this line, which described the first pass, was corrected after the audit,
  F-15).
- Prose in the appendices that pointed at dropped material was reworded (list under "Reference fixes" below).

## MIRROR (drafted from PAPER_INPUT_r16 part 0; outcomes pending)

- Source: `notes/PAPER_INPUT_r16.md` part 0 on `r16/mirror` (daa9dd4), read from the `Nova-Research-wt/mirror` worktree, with
  `notes/PREDICTIONS_r16_mirror.md` and `results/theory/r16/mirror_predictions.json` of the registration (commit bc81ee7, tag
  `r16-mirror-reg`, pushed 14:07:37 CST, before any job). The numbers of the lead's first message were replaced by these: in
  particular the backlog now "grows 1.4 times faster than the excess load" (alpha/(lam - lmiss) = 1.398), not "about 2.5 times
  faster than the standard trap".
- Section 4.1 "A predicted reversal of the youth premium (MIRROR)" (retitled after the review): the H-factor argument, the design, the asymptotic D/lmiss, model F's three
  predictions at 1.65 lref (blackout 0.05-0.09 lref, wave at 5135-5195 s, late completions 0.49-0.60 lref, backlog 1.4 times the
  excess load), the throughput-curve alternative, the registered rule (M1-M4, RENEWAL/CURVE, the cell verdicts), the not-blind
  statements; outcome `\pending`.
- Table 2 row: "Model F's prediction that a near-deterministic turn count reverses the premium"; MIRROR, 6 BURST and 3 NOBURST runs; pre-registered, blind in
  outcome, workload chosen with the model; result `\pending`.
- Appendix C, paragraph MIRROR: the full design, why K = 20, the asymptotics at both rates, the frozen per-seed predictions (a
  six-row table), the rules M1-M4, the seed and cell calls, the run-validity conditions, W5-W10, the tolerance provenance and the
  not-blind statements; outcome `\pending`. Figure 4 (`fig:mirror`, p. 25) is a framed placeholder there: placed in Section 4.1 it pushed
  the acknowledgments and the references to p. 13, so it went to the appendix (the lead left the choice to this session). Put
  `figs/fig_mirror.pdf` (from `figures/r16/fig_mirror.py`) in its place with part 1; moving it to Section 4.1 needs about 0.3 column
  of cuts elsewhere.
- Also: a FILLED row for `configs/agentload_prereg_2026-11-05_mirror_k20.yaml` (bc81ee7, 11-05 14:07:08, on GitHub 14:07:37) in
  `tab:ledger` (caption: five rows of 2026-11-05) and a round-16 row in `tab:frozensum15` (caption: rounds 15 and 16), both with the
  outcome `\pending`. `tab:timeline-r15` has no MIRROR rows yet: add the registration and job times with part 1.
- Other places that depend on MIRROR (no source comments mark them any more; see "Comments" below): the last sentence of
  contribution (2) in Section 1; the pointer to Section 4.1 after Theorem 2 in Section 3; "and MIRROR's runs" in Section 7 (if MIRROR is dropped, put "and" before "the six CUT runs"); "CUT and
  MIRROR were registered on 5 November 2026" in Appendix E.1. Section 1's priority sentence covers MIRROR without naming it ("the
  blind tests of Sections 4 and 5 (registered on 2026-11-05)").

## Comments and unused files (the lead's request: arXiv publishes the source)

- Every comment with text in `main.tex` and the files it inputs was removed; the only one left after the assembly was
  `main.tex:15` ("% Working title (draft): ..."), and the `% MIRROR` markers of the first restructure commit are gone. Bare
  line-end `%` (space control, e.g. after `\resizebox{...}{!}{`) remain.
- The section files that `main.tex` no longer inputs were deleted from `paper/sections/` (git history keeps them, e.g.
  `git show 524fc0e:paper/sections/appendix.tex`): `appendix.tex`, `appendix_fp.tex`, `appendix_icml.tex`, `appendix_supp.tex`,
  `background.tex`, `conclusion.tex`, `diagnostic.tex`, `frozen.tex`, `frozen_app.tex`, `intro.tex`, `limitations.tex`,
  `mechanisms.tex`, `method.tex`, `model.tex`, `related.tex`, `results.tex`, `robustness.tex`, `theory.tex`, `theory_icml.tex`,
  and the reframe draft's `v2_intro.tex`, `v2_theory.tex`, `v2_validation.tex`, `v2_entry.tex`, `v2_control.tex`,
  `v2_evidence.tex`, `v2_related.tex`, `v2_conclusion.tex`. Where this note says the old files "stay in `paper/sections/`", read
  "stay in git history".
- Figure files in `paper/figs/` that the PDF no longer uses were left in place (they are outputs of the figure scripts):
  `fig4_mechanisms.pdf`, `fig5_robustness.pdf`, `fig6_policy_grid.pdf`, `fig9_theory_scaling.pdf`,
  `fig10_theory_fixed_points.pdf`, `fig_lpm_crossing.pdf` and any other file not in the upload list of `paper/ARXIV_METADATA.md`;
  do not upload them.

## Honesty facts of `COORD/LEAD_HANDOFF.md`: where each is now

- vLLM "registered", not "pre-registered" (push after two jobs had started): 2 (What the record does not show), Table 1 status,
  ledger, App. E.5 ("A second engine: vLLM"), E.11 (vLLM registration timing), E.12 (slips). Its frozen mechanism checks held on
  (a), (b), (d); the detector (c) failed (two CAPPED false alarms), so the decision rule was not met: Table 1, App. E.5 (both the
  short paragraph and the full mechanism-prediction paragraph).
- H200 300k: Stage C values for n <= 32 seen by the operating agent and the first author before the theory freeze; no blind
  simulator prediction: App. E.9 (Fig. 8 caption), E.10 (Table `tab:frozensum`, H200 paragraph), App. F (`tab:lu` caption), ledger
  ("one partly seen"); 2 says the 300k H200 cell is a measurement, not a registered test.
- BASIN-1: the theory's prediction blind by access only (the 100-session runs had ended before the 02:05:30 push; the 25-session
  runs had started): `tab:frozensum` and App. E.12 (rounds 11-14 paragraph, "no BASIN-1 run is blind in time").
- Fresh-seed E0b: the replication rule not met (2.5 lref stable 3 of 3); the edge in realized rates 2.665-2.726 lref; pred2's E0F
  table not blind in time: 2, 7, App. E.3, `tab:frozensum`, E.15.
- Rescue: 4 of 9 release times outside the frozen +-15% (R4 19-22% late); "persists" means that the drained state sustains itself
  after the cap stopped binding: 5, ledger, App. E.7, `tab:frozensum`.
- LPM-INF: exploratory, two informative seeds, "not a fix": App. E.8, `tab:frozensum`, `tab:ledger`.
- Pool 150k: peak height and edge missed in the declared direction; 600k all within tolerance: `tab:frozensum`, App. E.9
  (weaknesses), E.10 (pools paragraph).
- The round-15 qualifiers (blind in outcome only, tolerances set on earlier runs, designed after the 900 s arm and after reading
  simulator outputs, the rule fixed after the per-seed predictions were read and changed in five ways, the CUT narrowing) are in
  4 and 5 where the claims are made, and in full in App. C.

## Reference fixes in the assembled appendices

Labels that moved were repointed (the audit of 8a212bd found two that were not: pointers to `app:proofs` for the fluid statements,
the cap-rescue proof and the drain estimate, which moved into E.4, and to `sec:frozen` for the H200 and Llama paired tests, which
moved into E.5; both repointed in the audit round, F-02 and F-10) (`sec:e2` -> E.5, `sec:fp`/`app:fp` -> E.9, `sec:background` -> E.2, `sec:curve` -> E.3,
`sec:model`/`sec:props` -> E.4, `app:protocol` -> the table or subsection meant, `app:frozen` -> `tab:frozensum`, `tab:frozen*` ->
`tab:frozensum`, `app:e2detail` -> E.5, CUT pointers -> 5). References to dropped material were removed or reworded: the fold
proposition and its figure (E.4, E.9), Proposition E and its `tab:prov` row, the validation table `tab:fpval`, the simulator
studies (`sec:robust`, `sec:mech`, `sec:simstudies`), the B-round table `tab:blind` (now pointed at `notes/PREDICTIONS*.md`), the
drain-time estimates, the supplementary-results appendix (`app:supp`), the scaling figure `fig:fpscale` and the policy-grid figure
`fig:grid`. One sentence of E.15 was rebuilt after its pointer went ("Uncontrolled factors remain, among them the choice of the
native cap and the coincidence of the cliff with a change of job and node in both SGLang curves.").

## Candidates for further cuts (not done; the lead's call)

- E.14: the full proof of Proposition A (about 2.5 pages; keep its statement, proof idea and scope).
- E.12: Table `tab:timeline` (rounds 6-9) and the three B-round blindness paragraphs (about 1.5 pages), if the "Earlier prediction
  rounds" paragraph of E.10, which they qualify, is cut too.
- E.9: the weaknesses paragraph and the sustaining-variable text (about 1 page); E.8 (about 1 page).

## What was cut

Not in the PDF any more (the sources stay in `paper/sections/`). By topic:

- Background and "what is classical" (old App. D; the engines paragraph is kept in E.2): duplicated by Sections 1 and 6.
- The operator diagnostic (old App. J) and the pre-deployment procedure in detail (old App. R): the claims are dropped.
- Simulator studies: the paired test's robustness and the published mechanisms in the earlier simulator (old App. T, with
  `fig5_robustness.pdf` and `fig4_mechanisms.pdf`), trace-driven tool times and mechanisms in detail (old App. R): claims dropped.
- The calibrated simulator's B-round prediction table `tab:blind` and its discussion (old App. N): compressed to the paragraph
  "Earlier prediction rounds" (E.10); its blindness statements stay in E.12.
- First-principles model parts the theory-led paper does not use: Proposition E (exogenous-gap lower bound) and `tab:propE`; the
  fold identity (Proposition `prop:fold`, its proof, the fold criterion on the cells, `fig10_theory_fixed_points.pdf`); the
  validation table `tab:fpval` and its subsection; the open system on the predicted curve; the heuristic layers in detail (the
  short definition paragraph is kept); relation to prior models in detail.
- The detailed frozen-prediction tables `tab:frozen`, `tab:frozen2`, `tab:frozen3`, the per-cell outcome narratives of old App. S
  (GPU generation, the 600k pool and paired test, pools, the second model and its paired test, fresh seeds, LPM-INF) and
  `fig9_theory_scaling.pdf`. The summary tables `tab:frozensum` and `tab:frozensum15`, with every miss, and the paragraphs of old
  App. I stay (E.10); every prediction stays in `notes/PREDICTIONS_*.md`.
- Duplicated text: the old main-text curve, edge and rescue paragraphs where the supplementary version was kept (or the reverse);
  the E2, native and vLLM "in detail" paragraphs (vLLM's registration timing and the failed mechanism rule are kept); the
  registration-fill paragraph (duplicate of the decision-rule subsection); the native, rescue and exploratory-vLLM registration
  paragraphs and the vLLM verdict paragraph (their commits and push times are in `tab:ledger`); "The sequence of stages", the E0F
  paragraph of old App. L (its content is in E.3), the drain-time estimates.
  Correction after the audit of 8a212bd (F-01, F-06, F-09, F-15): some of these blocks (appendix_supp [9], [19], [20]; appendix
  [12], [23], [24]; results [12], [13]) were not pure duplicates. They held facts found nowhere else: the 18:21 lowering of the
  vLLM jobs' memory request, the three rescue-rule changes after the simulator review, the verdict tool's commit-order labels,
  B3v's trapped token range, the first-principles vLLM drains, the engine check of the fluid drain estimate, the CAPPED arm's hit
  dip and the rescue's 60 s-bin minima. The audit round restored each of them (E.4, E.5, E.7, E.10, E.11, E.12, E.15).
- Old App. P: the LPM conjecture remark, covered orders at finite n, other orders, the quasi-static model in congestion (superseded
  by model F), the non-monotone tail and Bronson et al.'s terms.
- The exploratory policy-grid figure `fig6_policy_grid.pdf` and its introductory paragraph (the LPM results and LPM-INF stay, E.8).
- Threats to validity in detail (old App. R; the shorter "Limitations in detail" of old App. K is kept as E.15).
- The native-pool prediction round paragraphs of old App. R (their blindness statements are in E.12).
- The vLLM closed-curve, edge and blind-prediction paragraphs of old App. R (the curve and edge numbers are in E.5; the figures in
  E.3).

Block by block (old file, block index in `blocks.py`, lines, bytes, fate, labels and opening words):

| Block | Bytes | Fate | Labels and opening |
|---|---|---|---|
| `background.tex` [0] L1-1 | 64 | cut | `sec:background` \section{Background and what is classical}\label{sec:background} |
| `background.tex` [2] L6-7 | 1782 | cut | \paragraph{Thrashing and metastability.} Denning showed that admitting one more program to a memory near satur |
| `background.tex` [3] L9-10 | 1056 | cut | \paragraph{What is classical, and what is specific to agent serving.} The collapse past the working-set level, |
| `model.tex` [0] L1-1 | 59 | cut | `sec:model` \section{A fluid model of the open system}\label{sec:model} |
| `model.tex` [7] L26-26 | 57 | cut | `sec:props` \subsection{Caps and a congestion bound}\label{sec:props} |
| `method.tex` [0] L1-1 | 39 | cut | `sec:method` \section{Methodology}\label{sec:method} |
| `results.tex` [0] L1-1 | 56 | cut | `sec:results` \section{Results on the real engines}\label{sec:results} |
| `results.tex` [1] L3-3 | 73 | cut | `sec:curve` \subsection{The thrashing curve and the from-empty edge}\label{sec:curve} |
| `results.tex` [3] L10-11 | 2245 | cut | With the 300k pool (Fig.~\ref{fig:curve}, left), $\mu(n)$ rises from 0.176\sps{} at $n=16$ to 0.224 at 20 and  |
| `results.tex` [4] L13-14 | 1619 | cut | `sec:edge` \paragraph{The all-miss capacity and the from-empty edge.}\label{sec:edge} E0a gives $\lref=0.0715\pm0.0038$\s |
| `results.tex` [5] L16-16 | 54 | cut | `sec:e2` \subsection{The registered paired tests}\label{sec:e2} |
| `results.tex` [10] L64-64 | 62 | cut | `sec:rescue` \subsection{Rescue from an established trap}\label{sec:rescue} |
| `results.tex` [11] L65-67 | 2275 | cut | % (fig:rescue moved to the main text, sections/v2_*.tex) The paired tests show that a cap present when the bur |
| `results.tex` [12] L68-70 | 1182 | cut | % (tab:rescue moved to the main text, sections/v2_*.tex) The registered analysis passes in all three cells, R1 |
| `results.tex` [13] L71-72 | 1782 | cut | With the cap removed, every run stayed good at the same arrival process for the remaining 3780--4720\,s (300k) |
| `results.tex` [14] L73-74 | 1746 | cut | The rescue costs waiting, not sessions. In the rescue runs 121--143 (300k) and 220--251 (native) sessions were |
| `theory.tex` [0] L1-1 | 71 | cut | `sec:fp` \section{A first-principles model of the thrashing curve}\label{sec:fp} |
| `theory.tex` [1] L2-3 | 1623 | cut | Section~\ref{sec:fluid} takes $\mu(n)$ as measured. Here we \emph{predict} it, together with the all-miss leve |
| `theory.tex` [2] L4-5 | 55 | cut | % (fig:fpmu moved to the main text, sections/v2_*.tex) |
| `theory.tex` [6] L38-45 | 3351 | cut | `prop:E` \begin{proposition}[an exogenous-gap lower bound on hits]\label{prop:E} Suppose that the reuse gap of every fo |
| `theory.tex` [7] L47-63 | 3003 | cut | `tab:fpval` \begin{table*}[t]\centering\footnotesize \caption{First-principles predictions against measurements (\fpath{re |
| `theory.tex` [8] L64-65 | 759 | cut | On the finite grids evaluated, the fold criterion for the closed curve (Proposition~\ref{prop:fold}, Appendix~ |
| `theory.tex` [9] L66-67 | 1236 | cut | Conditional on fold-freeness and unimodality of the predicted curves in the sense of \S\ref{sec:fluid}, as sug |
| `theory.tex` [14] L104-105 | 1577 | cut | `sec:fp-val` \subsection{Validation}\label{sec:fp-val} Table~\ref{tab:fpval} compares the predictions with the three measur |
| `theory.tex` [16] L110-111 | 2332 | cut | `sec:fp-prior` \subsection{Relation to prior models}\label{sec:fp-prior} Yao et al.~\citep{yao2026multiturn} give a mean-fiel |
| `frozen.tex` [0] L1-1 | 62 | cut | `sec:frozen` \section{Frozen predictions and their tests}\label{sec:frozen} |
| `diagnostic.tex` [0] L1-1 | 59 | cut | `sec:diag` \section{A diagnostic, and what it implies}\label{sec:diag} |
| `diagnostic.tex` [1] L2-3 | 1138 | cut | Choosing the number of admitted jobs from the throughput curve is the classical selection of a multiprogrammin |
| `diagnostic.tex` [2] L4-5 | 1750 | cut | The window of Eq.~\eqref{eq:window} comes from three measurements that an operator can make before deployment, |
| `diagnostic.tex` [3] L6-7 | 2434 | cut | If $\mu^*>\lmiss$, then in the fluid model of \S\ref{sec:fluid}, under request-level FCFS and the assumptions  |
| `diagnostic.tex` [4] L8-9 | 2032 | cut | The cap must be measured again when the workload or configuration changes. On the engine it moved from 20 to 6 |
| `limitations.tex` [0] L1-1 | 53 | cut | `sec:limits-old` \section{Limitations in detail}\label{sec:limits-old} |
| `appendix.tex` [0] L1-1 | 46 | cut | `app:protocol` \section{Protocol details}\label{app:protocol} |
| `appendix.tex` [5] L97-97 | 1125 | cut | \paragraph{The sequence of stages.} \emph{Stage~0}, a smoke test of server and client on one GPU, came first;  |
| `appendix.tex` [9] L104-105 | 1328 | cut | The fresh-seed E0b (E0F; jobs 17168506--07) repeated 2.0 and 2.5 $\lref$ on the 300k pool with arrival seeds 3 |
| `appendix.tex` [12] L111-111 | 851 | cut | \paragraph{Drain-time estimates.} The registrations' feasibility check used $b/(\mu(c)-\lambda)$, which ignore |
| `appendix.tex` [16] L143-145 | 4041 | cut | `app:prereg` \section{The registrations}\label{app:prereg} \begingroup\raggedright The registration was filled by formula f |
| `appendix.tex` [20] L161-161 | 1679 | cut | \paragraph{The native registration.} \fpath{configs/agentload_prereg_2026-10-25_native.yaml}, status FILLED, c |
| `appendix.tex` [21] L163-163 | 1221 | cut | \paragraph{The exploratory vLLM registration.} \fpath{configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml} |
| `appendix.tex` [23] L166-167 | 1086 | cut | The verdict, \fpath{results/agentload_analysis_burst2/20261031-020837/} in the paired test's data directory (\ |
| `appendix.tex` [24] L169-169 | 2068 | cut | \paragraph{The rescue registrations.} \fpath{configs/agentload_prereg_2026-10-31_rescue.yaml} (R1, cell \textt |
| `appendix.tex` [28] L205-205 | 60 | cut | `app:timeline` \section{Prediction rounds and timeline}\label{app:timeline} |
| `appendix.tex` [29] L207-207 | 1351 | cut | \paragraph{The calibrated simulator in detail.} Our discrete-event simulator models a continuous-batching engi |
| `appendix.tex` [31] L211-211 | 1721 | cut | \paragraph{Prediction rounds.} The calibrated simulator then predicted, in both modes (mixed primary), B1: $\l |
| `appendix.tex` [38] L288-288 | 1622 | cut | \paragraph{Rounds 11 to 14.} Table~\ref{tab:timeline-r11} gives the time record of the later rounds. Round 11  |
| `appendix.tex` [43] L371-371 | 64 | cut | `sec:blind` \subsection{Blind predictions against outcomes}\label{sec:blind} |
| `appendix.tex` [44] L373-430 | 3960 | cut | `tab:blind` \begin{table}[!tp] \centering\footnotesize \caption{Blind predictions (calibrated simulator, mixed batching un |
| `appendix.tex` [45] L431-432 | 2565 | cut | B1 matched within 3.1\% (Table~\ref{tab:blind}), which mostly checks the simulator's bookkeeping (\S\ref{sec:s |
| `appendix.tex` [46] L433-434 | 522 | cut | The second round, for the native pool, held in part: B3n's pass held at the registered rates, which lie 6--16\ |
| `appendix.tex` [53] L490-490 | 62 | cut | `app:proofs` \section{Proofs of the quasi-static results}\label{app:proofs} |
| `appendix.tex` [56] L504-507 | 1026 | cut | \begin{remark}[resident-first orders; a conjecture] Under pure LPM (without SGLang's 128-request fallback) in  |
| `appendix.tex` [68] L564-564 | 998 | cut | \paragraph{Covered orders at finite $n$.} In our earlier simulator, under FCFS order, a hard pin of queued pre |
| `appendix.tex` [69] L566-566 | 2633 | cut | \paragraph{Other orders.} The proof uses the order only through Lemma~\ref{lem:waits}, so it holds for any ord |
| `appendix.tex` [71] L570-570 | 1872 | cut | \paragraph{The quasi-static model in congestion.} Eq.~\eqref{eq:fluid} assumes that the internal state (turn-i |
| `appendix.tex` [72] L571-572 | 1769 | cut | A work balance, which this paragraph does not make rigorous for the open system (Corollary~\ref{cor:trapthr} d |
| `appendix.tex` [73] L574-574 | 1215 | cut | \paragraph{A non-monotone tail, and Bronson et al.'s terms.} Without the monotone tail, the recovery threshold |
| `appendix_fp.tex` [0] L1-1 | 66 | cut | `app:fp` \section{First-principles model: details and proofs}\label{app:fp} |
| `appendix_fp.tex` [7] L43-43 | 1349 | cut | \paragraph{The feedback map and the fold identity.} For a closed population $n$ define the \emph{feedback map} |
| `appendix_fp.tex` [8] L44-54 | 1872 | cut | `prop:fold` \begin{proposition}[fold identity and relaxation stability]\label{prop:fold} Assume that $f$ is continuous on  |
| `appendix_fp.tex` [9] L55-87 | 5002 | cut | \begin{proof}[Proof of Proposition~\ref{prop:fold}] We work away from crossings of the decode-cost kink, where |
| `appendix_fp.tex` [10] L89-89 | 2659 | cut | \paragraph{The fold criterion on the predicted cells.} For the registered exponential tool times the largest s |
| `appendix_fp.tex` [11] L91-94 | 1127 | cut | `fig:fixed` \begin{figure*}[t]\centering \includegraphics[width=\textwidth]{figs/fig10_theory_fixed_points.pdf} \caption{F |
| `appendix_fp.tex` [13] L100-100 | 1662 | cut | \paragraph{Proposition~\ref{prop:E} on the measured cells.} Table~\ref{tab:propE} evaluates three exogenous-ga |
| `appendix_fp.tex` [14] L102-127 | 2038 | cut | `tab:propE` \begin{table}[htbp] \centering\footnotesize \caption{Proposition~\ref{prop:E} on the measured closed curves (\ |
| `appendix_fp.tex` [15] L129-129 | 1364 | cut | \paragraph{The open system on the predicted curve.} For $\mu_b<\lambda<\mu^*$, under Proposition~\ref{prop:fol |
| `appendix_fp.tex` [16] L131-138 | 5653 | cut | \paragraph{Heuristic layers.} These are heuristics, not consequences of the propositions (H1--H4 are F1--F4 in |
| `appendix_fp.tex` [17] L140-140 | 4099 | cut | \paragraph{Relation to prior models in detail.} Yao et al.~\citep{yao2026multiturn} give a mean-field (Che-typ |
| `appendix_supp.tex` [0] L1-1 | 47 | cut | `app:supp` \section{Supplementary results}\label{app:supp} |
| `appendix_supp.tex` [8] L22-23 | 1645 | cut | `app:e2detail` \subsection{The registered paired tests in detail}\label{app:e2detail} The registered analysis, run on all 18  |
| `appendix_supp.tex` [9] L24-25 | 3382 | cut | In Fig.~\ref{fig:e2}, every BURST run is at zero hits from the window starting at 1300\,s to the end. Its back |
| `appendix_supp.tex` [11] L32-33 | 566 | cut | A second registration was filled by the same formulas from the native curve, the native E0a calibration and th |
| `appendix_supp.tex` [12] L34-35 | 1210 | cut | The registered analysis passes at both rates, and every run is in the predicted state (Table~\ref{tab:e2}, bot |
| `appendix_supp.tex` [13] L36-37 | 1854 | cut | With the larger pool the collapse took longer and the backlog never drained (Fig.~\ref{fig:e2native}). In the  |
| `appendix_supp.tex` [14] L38-39 | 546 | cut | vLLM 0.32.0 passed its smoke test on the same GPU type (token ids and cached-token counts returned, flush veri |
| `appendix_supp.tex` [15] L40-41 | 1828 | cut | Six exploratory BURST runs came first, under a registration derived from E2's: the multiples 1.35 and 1.65 of  |
| `appendix_supp.tex` [16] L42-43 | 1098 | cut | vLLM's own closed curve (Fig.~\ref{fig:curve}, right; one run per $n$) has the shape of SGLang's at the same p |
| `appendix_supp.tex` [17] L44-45 | 842 | cut | From an empty cache and queue (Fig.~\ref{fig:edge}, bottom; one 3000\,s run per rate) vLLM stayed stable at 1. |
| `appendix_supp.tex` [18] L46-47 | 1364 | cut | Blind predictions for this cell, B4v for the curve and B2v for the edge, were made with the calibrated simulat |
| `appendix_supp.tex` [19] L48-49 | 2039 | cut | A registration for vLLM was then filled by the formulas used for SGLang (Appendix~\ref{app:prereg}) from this  |
| `appendix_supp.tex` [20] L50-51 | 2600 | cut | The registered analysis passes at both rates (Table~\ref{tab:e2}, bottom): at each rate, in two of three seeds |
| `appendix_supp.tex` [24] L81-81 | 50 | cut | \subsection{Exploratory policy grid and stock LPM} |
| `appendix_supp.tex` [25] L82-86 | 690 | cut | `fig:grid` \begin{figure}[t] \centering \includegraphics[width=\columnwidth]{figs/fig6_policy_grid.pdf} \caption{Explorat |
| `appendix_supp.tex` [26] L87-88 | 661 | cut | Three other engine cells ran the BURST arm at the registered rates and seeds (Fig.~\ref{fig:grid}) under explo |
| `appendix_supp.tex` [30] L96-96 | 45 | cut | \subsection{The native-pool prediction round} |
| `appendix_supp.tex` [31] L97-97 | 2347 | cut | \paragraph{The native-pool round.} A second round (B1n--B4n) reran the same simulator with only the pool chang |
| `appendix_supp.tex` [32] L98-99 | 991 | cut | B1n and B4n are not blind. The native curve and $\lmiss$ had been measured and summarised in our project statu |
| `appendix_supp.tex` [33] L101-101 | 61 | cut | \subsection{Trace-driven tool times and mechanisms in detail} |
| `appendix_supp.tex` [34] L102-102 | 1910 | cut | \paragraph{Trace-driven tool times.} TraceLab's sessions come from 52 pseudonymous users (release v0.0.2, a la |
| `appendix_supp.tex` [35] L104-104 | 1506 | cut | \paragraph{Mechanisms in detail.} \emph{TTL pins.} Continuum's released preview pins for 2\,s, and only when t |
| `appendix_supp.tex` [36] L106-107 | 3133 | cut | \subsection{The pre-deployment procedure in detail} The window of Eq.~\eqref{eq:window} comes from three measu |
| `appendix_supp.tex` [37] L108-109 | 4340 | cut | If $\mu^*>\lmiss$, then in the fluid model of \S\ref{sec:fluid}, under request-level FCFS and the assumptions  |
| `appendix_supp.tex` [38] L110-111 | 2437 | cut | The cap must be measured again when the workload or configuration changes. In the simulator the peak moved fro |
| `appendix_supp.tex` [39] L113-113 | 42 | cut | \subsection{Threats to validity in detail} |
| `appendix_supp.tex` [40] L114-114 | 2190 | cut | \paragraph{Synthetic sessions and clients.} Sessions are synthetic (random tokens, fixed tool outputs and outp |
| `appendix_supp.tex` [41] L116-116 | 3533 | cut | \paragraph{Few runs, finite horizons, nominal rates, uncontrolled factors.} The closed curves and, apart from  |
| `appendix_supp.tex` [42] L118-118 | 3943 | cut | \paragraph{Model and simulators.} Eq.~\eqref{eq:fluid} is used for the window and H2's from-empty edge, the re |
| `appendix_supp.tex` [43] L120-120 | 2251 | cut | \paragraph{The first-principles model.} Its propositions hold for a deterministic fluid model, and no limit th |
| `appendix_supp.tex` [44] L122-122 | 33 | cut | \subsection{Further related work} |
| `appendix_supp.tex` [45] L123-123 | 3074 | cut | `app:classical` \paragraph{What is classical, and what is specific to agent serving, in full.}\label{app:classical} The collap |
| `appendix_supp.tex` [46] L125-125 | 2383 | Appendix F (other systems) | \paragraph{Other systems.} CacheWise evaluates coding agents with sessions started together~\citep{tiwari2026c |
| `frozen_app.tex` [0] L1-1 | 63 | cut | `app:frozen` \section{Frozen predictions: the full record}\label{app:frozen} |
| `frozen_app.tex` [1] L2-5 | 1398 | cut | `fig:fpscale` \begin{figure*}[t]\centering \includegraphics[width=\textwidth]{figs/fig9_theory_scaling.pdf} \caption{Frozen  |
| `frozen_app.tex` [2] L6-7 | 1596 | cut | This appendix gives every prediction frozen for the later tests up to round 14 (Tables~\ref{tab:frozen}--\ref{ |
| `frozen_app.tex` [3] L9-9 | 4233 | cut | \paragraph{Out-of-sample predictions.} The model's predictions for an H200 at the same pool, for pools of 150k |
| `frozen_app.tex` [5] L29-29 | 2646 | cut | \paragraph{GPU generation.} The H200 cell repeats the 300k SGLang cell on one H200 NVL, with SGLang's default  |
| `frozen_app.tex` [6] L31-50 | 5618 | cut | `tab:frozen` \begin{table*}[tp] \centering\footnotesize \caption{Frozen predictions and their tests. Each prediction was co |
| `frozen_app.tex` [7] L52-69 | 4829 | cut | `tab:frozen2` \begin{table*}[tp] \centering\footnotesize \caption{Frozen predictions and their tests: Llama-3.1-8B, the fres |
| `frozen_app.tex` [8] L71-90 | 5170 | cut | `tab:frozen3` \begin{table*}[tp] \centering\footnotesize \caption{Frozen predictions and their tests: the rescue tests, SHED |
| `frozen_app.tex` [9] L92-92 | 1675 | cut | \paragraph{GPU generation: outcome.} Section~\ref{sec:h200} reports the measurement and \S\ref{sec:frozen} sco |
| `frozen_app.tex` [10] L94-94 | 2063 | cut | \paragraph{GPU generation: the 600k pool.} The 600k H200 cell (Stage~C 17169672--80, E0b 17169682--87) repeats |
| `frozen_app.tex` [11] L96-96 | 1814 | cut | \paragraph{GPU generation: the 600k paired test.} The 18 jobs (17171020--37, seed-major, one 8700\,s arm per j |
| `frozen_app.tex` [12] L98-98 | 602 | cut | \paragraph{Pools and a second model.} The pool sweep repeats Stage~C and E0b on the A100 with pools of 150k an |
| `frozen_app.tex` [13] L100-100 | 2653 | cut | \paragraph{Pools: outcome.} The 18 pool-sweep jobs (Stage~C 17168864--69, E0b 17168870--81; every server log r |
| `frozen_app.tex` [14] L102-102 | 2859 | cut | \paragraph{A second model: outcome.} Stage~C (17166814--16), E0a (17166823, 29, 31, and the 64-session check 1 |
| `frozen_app.tex` [15] L104-104 | 1642 | cut | \paragraph{A second model: the paired test.} The 18 jobs (17170409--26) were submitted at 07:50:02 CDT, 47\,s  |
| `frozen_app.tex` [19] L112-112 | 813 | cut | \paragraph{Fresh-seed from-empty runs: outcome.} Sections~\ref{sec:edge} and~\ref{sec:frozen} and Appendix~\re |
| `frozen_app.tex` [24] L122-122 | 265 | cut | \paragraph{LPM-INF: outcome (exploratory).} Appendix~\ref{app:supp} gives the outcome in full: on the two info |
| `robustness.tex` [0] L1-1 | 49 | cut | `sec:simstudies` \section{Simulator studies}\label{sec:simstudies} |
| `robustness.tex` [1] L2-2 | 60 | cut | `sec:robust` \subsection{Robustness of the paired test}\label{sec:robust} |
| `robustness.tex` [2] L3-4 | 682 | cut | The real test fixes one workload, one burst size and one horizon; we varied each in the calibrated simulator ( |
| `robustness.tex` [3] L6-10 | 842 | cut | `fig:robust` \begin{figure}[t] \centering \includegraphics[width=0.94\columnwidth]{figs/fig5_robustness.pdf} \caption{The p |
| `robustness.tex` [4] L12-12 | 691 | cut | \paragraph{Tool-time laws.} With exponential tool times of mean 1, 2 and 5\,s, a lognormal law (mean 5\,s, coe |
| `robustness.tex` [5] L14-14 | 1075 | cut | \paragraph{Tool times from real agent traces.} We replaced the tool-time law by empirical tables from SyFI Tra |
| `robustness.tex` [6] L16-16 | 1159 | cut | \paragraph{Burst size and horizon.} At 1.35 and 1.65 $\lmiss$, a burst of 25 sessions never traps (0 of 10), 5 |
| `robustness.tex` [7] L18-18 | 1812 | cut | \paragraph{The slope rule is the fragile part.} Over the 100 BURST runs of the tool-time test the registered r |
| `robustness.tex` [8] L20-20 | 477 | cut | \paragraph{The cap must follow the measured curve.} The right cap, 20 for the workload of record at 300k, move |
| `mechanisms.tex` [0] L1-1 | 74 | cut | `sec:mech` \subsection{Published mechanisms in the earlier simulator}\label{sec:mech} |
| `mechanisms.tex` [1] L3-7 | 1154 | cut | `fig:mech` \begin{figure*}[t] \centering \includegraphics[width=0.92\textwidth]{figs/fig4_mechanisms.pdf} \caption{$\mu(3 |
| `mechanisms.tex` [2] L8-9 | 1432 | cut | In the fluid model of \S\ref{sec:fluid} the recovery threshold from deep congestion is at most $\muinf$, so a  |
| `mechanisms.tex` [3] L11-11 | 1345 | cut | \paragraph{Orderings.} FCFS gives $1.024\pm0.020$ with hit fraction 0.000 and the GPU always busy; with the 1. |
| `mechanisms.tex` [4] L13-13 | 776 | cut | \paragraph{TTL pins.} Continuum keeps a program's KV after a non-final turn for a time-to-live chosen by a cos |
| `mechanisms.tex` [5] L15-15 | 637 | cut | \paragraph{Adaptive caps.} CONCUR adds 2 to a window on active agents when KV usage is below 0.2 and halves it |
| `mechanisms.tex` [6] L17-17 | 533 | cut | \paragraph{Static caps.} By Proposition~\ref{prop:cap} a cap $c$ holds a large population at $\mu(c)$: $4.04\p |
| `mechanisms.tex` [7] L19-19 | 1735 | cut | \paragraph{Admission by memory demand.} ThunderAgent periodically compares the programs' KV demand with the ca |
| `mechanisms.tex` [8] L21-21 | 1251 | cut | \paragraph{Why the ranking comes out this way.} Under request-level FCFS, with or without protection that keep |

The main-text files of the reframe draft (`v2_intro`, `v2_theory`, `v2_validation`, `v2_entry`, `v2_control`, `v2_evidence`,
`v2_related`, `v2_conclusion`) are no longer input either; their content is in the new files as mapped above.

## Read-only review of 4f62b4c (one agent, after the first commit) and what was done with it

28 findings; the theorem split was found consistent with App. A and every part-letter reference correct. Applied:
- must-fix: "two pre-registered cells slow the tool calls with no burst" (TOOLSLOW-D15 did not trap); the processor-sharing analogy
  restored to "can exceed 1/E[S]" with alpha_PS defined; Section 2's "the plug-in puts four of the other seven below the threshold
  and two within 1e-4 /s" (not "explains the others"); the H200 300k qualifier (n <= 32 seen, no blind simulator prediction) in
  Section 2.
- should-fix: CAPPED "in all 30 CAPPED runs of the five paired tests" with the 405-471 s "in E2"; App. F's pointers to its own D4
  paragraph and the recomputation; "blind in outcome" for CUT in Section 5 and Table 2; "on 300 s bins" for the dip bound; the
  0.82 -> 0.99 effect of the one looser CUT rule change; Khanin et al.'s closing remark on random T; the intro's processor-sharing
  credit and "the derivation of the recursion"; the MIRROR wording (title "A predicted reversal ...", the ledger claim as model F's
  prediction, "can put H far enough below 1", "read on this workload"); the intro's "the theory ... and the blind tests" list; two
  repointed citations in E.4 (decomposition, bounded multiprogramming); the TOOLSLOW-W row of `tab:frozensum15` -> App. C; two
  pointers to cut paragraphs removed; "(36 registered, on 30 plans)" in Table 2; the S2-against-gamma sentence and 1.089 against
  gamma/z; the rescue's goodput cost in the intro; appendix pointers after Proposition A, Proposition `prop:cap`, Corollary
  `cor:rescue` and Eq. (fluid); LPM expanded and the client plan defined in Section 2.
- nits: App. E references to cut simulator material deleted or reworded; assembly seams fixed (a stray space, self-references in
  E.6, E.7, E.9, E.12, a dangling pointer to EfficientAgent and CacheRoute); the release-time pointer -> E.7 and `tab:frozensum`;
  Proposition 1(a)'s "lambda = 0, outside (F5)" (and in App. A); the proof of Lemma 1 now says why u_0 in [0, V_0) suffices ((F6):
  the state at any time is an admissible initial state); "(post hoc)" on the SHED hit-return times; Lu et al.'s late controller
  "(and leaving it on)"; "and by turning sessions away" in the conclusion; the pool gauge's locked prefixes.
Not applied: the S1-S5 table (space); MIRROR drop mechanics beyond the list above (MIRROR stays).

To keep the main text at 12 pages after these additions, about 25 lines were trimmed without dropping a claim or qualifier: the
definition of pre-registered in Section 2's text (it is in Table 1's caption), a sentence of the composition bullet, the Kendall
sentence (two of its four probabilities; all four stay in App. A), the Lu et al. sentence of Section 5's opening, the goodput
sentence of the rescue (detail in App. D; its qualifiers, slowdown-only, own reference, post hoc, went with it, so this trim did
drop qualifiers: restored in the audit round, HON-1), the MIRROR rule sentence (in full in App. C), the concurrent-work paragraph and the
from-empty summary of Section 4. The MIRROR figure placeholder went to App. C for the same reason.

## Audit fix round (2026-11-05): the independent audit of 8a212bd

Requested by the lead session (cross-session message, about 16:40 CST): apply its triage of the independent pre-upload audit,
`COORD/AUDIT_8a212bd_FIXLIST.md` (five reviewers: numbers, honesty and priority, mathematics, restructure losses, arXiv compliance;
a skeptic confirmed 55 of 61 findings and refuted 6; reasoning in `COORD/audit_8a212bd/confirmed.json`). Order: the merge; sections
A (20 must-fix and should-fix items) and B (31 nits); the 9 MIRROR and `\repourl` placeholders and section D's decisions
(repository, title, categories, license) left alone; rebuild; the strict packager with ALLOW_PENDING=9; push.

### 1. The merge (ARX-3)

ce56977 merges `origin/claude/theory-icml-2164a9` (fdb80c9, the one commit this branch lacked; the paper cites it as the commit that
added the scorer's unregistered gamma/z column). It brings `analysis/theory/icml/score_new.py` (S2'), `support.py` and
`results/theory/icml/support.json` (gamma/z ratios) and the post-registration notes in `notes/PREDICTIONS_icml_trap.md`,
`notes/PREDICTIONS_icml_cut.md` and `notes/THEORY_ICML_2026-11.md`. The five conflicts the lead named were resolved to this branch:
`figures/theory_icml/fig_trap_universality.py`, `paper/figs/fig_trap_universality.pdf` and `.png`, `paper/sections/v2_app_trap.tex`
(git's rename of `appendix_icml.tex`), and `paper/sections/theory_icml.tex` kept deleted. Nothing under `paper/` changed: two builds
with a fixed SOURCE_DATE_EPOCH, before and after, give the same PDF byte for byte (md5 9e8882d4bd4ad0bb507d43d3e32321d2, 64 pages).

### 2. Section A, applied

- M1 (must-fix): Section 4.1 now says the backlog "grows 1.65--1.95 times as fast as the plan's excess load lambda_plan - lambda_miss
  over [6000,8700) s (1.4 times asymptotically)"; App. C's table states that its slopes are over [6000,8700) s and gains the
  erratum sentence (the prediction note quoted the asymptotic 1.4 and 270-330 s; corrected in d8c49b7 on `r16/mirror`, after the tag
  and before any MIRROR run output was read; M4 scores the per-seed slopes and W6 only the order, so neither error enters a rule).
- F-01 (must-fix): the 18:21 memory-request sentence is back in E.5's vLLM paragraph with its qualifier; the E.12 pointer goes to
  `sec:vllm`; E.12 gains the three stricter rescue-rule changes (wording of 524fc0e) and E.15 a clause on them; E.11's vLLM
  paragraph says the verdict tool labels the test pre-registered and decisive by commit order.
- ARX-1: `ARXIV_METADATA.md` lists all nine markers and the unmarked MIRROR-dependent sentences; `NUMBERS.md`'s pending section
  lists the nine markers and no longer names the 11-04 URL.
- ARX-2: Table 19's tag is `trap-arxiv-v1`, recorded in `ARXIV_METADATA.md`.
- ARX-3: the merge above; the release build and E.13's redaction counts are a checklist item in `ARXIV_METADATA.md`.
- ARX-5: Table 19 gains rows for the model-F check, round 15 (the six pull directories by name, `analysis/r15_cut.py`, the three
  tags), the data-only analyses and MIRROR (no pull directory yet: with part 1); the r13 row is relabelled "entry model (App. E.9)";
  the figures row names `figures/theory_icml/` (Fig. 2) and `figures/r16/` (Fig. 4); `paper/figs/README.md` covers Figs. 2 and 4.
- HON-1 (also F-04): the goodput sentence of Section 5 says "slowdown-only form ... (their inter-token-latency condition omitted,
  our own unloaded reference; post hoc)", "all 30 registered BURST runs ... against the same-seed NOBURST run" and "(depending on
  the reference)"; the intro says "in a slowdown-only goodput computed post hoc".
- HON-2: App. D dates the analyses (computed on 2026-11-04/05, after Lu et al.'s paper appeared); Section 2 and the ledger's
  status cell say so too.
- HON-3: E.5 and App. F: "a larger and faster GPU (H200 profiles with about twice the cache and decode memory)", the 0.46-0.70
  across their GPU and host-tier sweep, "differ in normalization and in memory".
- HON-4: E.7: Lu et al. restore service on hardware by terminating the burst sessions, prevent the trap with their controller
  active before the surge, and rescue an established trap in simulation.
- HON-5: App. E's opening: "an earlier, longer draft of this work, which was withdrawn from arXiv before announcement and never
  published (its sources are in the repository history)". Akshat confirms the status in his arXiv account (checklist).
- M2: "proved in model F for our workload" (Section 6 and App. F's summary), "which for our workload lies below the trapped
  throughput D(lambda) (Theorem 2)" (App. F), Corollary 3 retitled "the drain threshold is lambda_miss, not the trapped
  throughput", "for our workload" in Sections 1, 5 (opening) and 8, "can thus complete" in Section 3, and Section 1's contribution
  (1) "in model F with such a premium".
- F1: Section 4.1: "every trapped run at a load above the all-miss capacity completing sessions above it (CUT-B's runs, cut to
  below it, completed 0.92--0.97 lambda_ref, as model F predicts)"; the intro: "Trapped runs at loads above the all-miss capacity".
- F3: Section 4 and the intro: "36 ... in the five registered paired-test cells, 30 registered runs and 6 earlier exploratory vLLM
  runs on the same plans, on 30 distinct arrival plans"; the ledger: "36 in paired-test cells: 30 registered, 6 exploratory" (see
  4 below); the slope-rule paragraph: "8 of the 9 below-threshold runs (6 of the 7 registered ones) are seed 1".
- F4: "serves turns 9--41% shorter than the stationary mix (the tilted mix predicts 10--42%)".
- F-02: the stale `app:proofs` pointers in E.2, E.4 and E.5 now point to the end of E.4, to Theorem 2 and Section 4, or to E.9
  (burst sizes).
- F-05: the ledger and Table 12: "rejects only the naive and quasi-static readings (a constant rate at the cut fits as well)".
- F-06: E.5's vLLM paragraph restores B3v's token range and the first-principles drains with their blindness qualifier (524fc0e's
  sentence); E.4 gains the engine check of the drain estimate (3-52%, -4 to +13%, 1.05-1.63 times); E.9 Weaknesses gains H2's vLLM
  edge; E.10's earlier-rounds paragraph notes B3v's token range.
- F-07: E.10 "Pools and the window law" gains the declared log-likelihood sentence, each number checked (`notes/LOG.md`,
  `notes/PAPER_INPUT_pool.md`, 524fc0e `frozen_app.tex`, pred2's E0F declaration); no prediction file is cited for an outcome.
- F-08: E.15 names the traces with citations (TraceLab, mini-SWE-agent, SWE-bench Verified) and `notes/lit/AGENT_TRACES.md`;
  Section 7 cites TraceLab; E.5's definition of pre-registered cites suram2026cacheable (optional, done).

### 3. Section B, applied

ARX-6 (categories, license and upload rule recorded, not decided), ARX-8 (fence), ARX-9 (Feller "Third" edition and Ch. XIII at
both places; Khanin DOI, checked: doi.org redirects to the AMS MMJ vol. 1(3) 2001 Khanin PDF; Huang et al.'s OSDI '22 URL, checked),
HON-6, HON-8, HON-9, HON-10 (also in Section 6 and App. F's summary), HON-11, HON-12 (times checked in
`provenance/sacct_cited_jobs_2026-11-05.txt`: 17256674-76 started 03:22:28), HON-13 (17169565-70 submitted 02:06:31, first start
04:33:21, in `provenance/sacct_cited_jobs_2026-11-01.txt`), HON-14, HON-15, HON-16 (see 4), M3, M4, M5 (see 4), M6, M7, M8, M9, M11
(App. A also lists what the tests do not cover), N1, N2, N3, N4 (also App. D's D1), F-09 (E.5 sentence; the optional 60 s-bin minima
in E.7), F-10 (label `sec:h200llama`; E.5, E.12 and two `tab:ledger` cells repointed), F-11, F-12 (1)-(4), F-13 (the map written
with references, plus Corollary 4 = the cap rescue here), F-15 (corrections above in this note).

### 4. Changed from the fix list's text, and why

- F3, ledger cell: the given text made Table 2 taller than a two-column top float may be (`\dbltopfraction` 0.7), and LaTeX moved
  it behind the references (p. 18). The cell now reads "36 in paired-test cells: 30 registered, 6 exploratory"; the full breakdown
  (6 earlier exploratory vLLM runs on the same plans; 30 plans) is in Section 4's text and in the intro.
- HON-16: "(passed at 9 of 10 rates)" instead of "(the registered trap rule held at 9 of 10 rates)", for space; four trims pay for
  it (`ARXIV_METADATA.md`); 1917 form characters.
- M5: the main text states the conditioning and drops "orders of magnitude"; App. A adds that with unrealized turn counts the
  probability is the product of per-session transforms, larger by Jensen's inequality (no new number; the skeptic's values are not
  cited).
- M1, erratum sentence: "M4 scores the per-seed slopes ... and W6 only the order of the waves" (W6 tests the order, not the shift).
- F-01 (a): the wording of 524fc0e ("after a review of the simulator's predictions and before any rescue run"), not "before the
  registration commit", which no committed record states.
- ARX-5: two stale rows of Table 19 (robustness and mechanisms: simulator studies that the restructure cut, cited nowhere in this
  version) were removed, so that the table fits a page.
- HON-4 and HON-10 at E.7 are one sentence; HON-10's parenthetical is also used in Section 6 and App. F's summary.

### 5. Not applied (all optional or outside the Do lines)

HON-1's optional clause on the 540-840 s of trap before the cap engaged (space); F-07's other losses (the 150k collapse
overstatement, the 600k soft tail, the H200 600k edge in realized rates; the verifier found the last two unscored); F-08's
hysteresis and MPL-control credits (not in the Do); F-09's Fig. 1 caption alternative; dates for CUT's uncut controls in App. C
(not in HON-15's Do). No item of sections A or B was skipped.

### 6. Space

The audit's qualifiers added about 22 main-text lines; the main text, statements included, still ends on p. 12, with about four
lines left for MIRROR's part 1. Trims, all of redundancy (no claim or qualifier dropped): Section 3's opening (the intro states the
quasi-static reading; Lu et al.'s D_low kept), Section 6's processor-sharing and Khanin sentences (they are in Section 3, with the
same citations), the S1-S5 tolerances and TOOLSLOW-W's slope values in Section 4 (in full in App. C), the CUT sign clauses in
Section 5 (in App. C), the engage times and caps in Fig. 3's caption (in the text), the turn-mix closeness in Fig. 2's caption (in
Section 3), the source of the costs in Section 4's opening (in Section 3), and model F's definition and two clauses of the CUT recap
in the conclusion.

### 7. Build and package

65 pages; clean build. Strict packager (`make_arxiv_pkg_v3.sh`, PKG_NAME=inside-the-trap, ALLOW_PENDING=9): "inputs: 13 files",
"figures: 7", "pending markers in sources: 9 (allowed 9)", "test build: 65 pages; 'not found': 0; 'undefined': 0; overfull: 0",
"pending markers in the PDF: 9 (allowed 9)", "OK".
