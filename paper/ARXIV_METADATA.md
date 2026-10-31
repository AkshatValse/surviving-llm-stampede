# arXiv submission metadata

Prepared 2026-10-31 for the build of `paper/main.tex` with the r10/arxiv revision, the registered vLLM verdict, the first-principles model and the frozen-prediction section applied; updated for fill 2 (the registered rescue result, the reordered main text), its fix-up rounds, and the review fix round of 2026-10-31 (Saturday review: the cliff attributed to hit-dependent running reservations, Proposition 4 retitled, blindness and KAIROS positioning corrected). The PDF abstract in `main.tex` is the LaTeX form of the form abstract below: the two texts are identical once the macros are expanded (`$\lref$` to `$\lambda_{ref}$`, `\sps` to ` sessions/s`, `3000\,s` to `3000 s`, `\%` to `%`). If one is edited, edit the other and recount.

## Title

Thrashing Returns: Metastable Failures in Prefix-Cached Agent Serving

## Authors

Akshat Valse, Ali Jannesari

(Department of Computer Science, Iowa State University, Ames, IA, USA. Corresponding author: avalse@iastate.edu. Ali Jannesari: jannesar@iastate.edu. The authors should confirm both addresses.)

## Abstract (form)

```text
Prefix caching keeps an LLM agent session's KV across tool calls, so a hit prefills only new tokens. This can make the high-hit state metastable, in the physics sense. In a pre-registered paired test on SGLang 0.5.22 (Qwen2.5-7B-Instruct, one A100, 300k-token pool) at 1.35 and 1.65 times the measured all-miss capacity, a burst of 200 sessions left 6 of 6 runs at zero hits to the end, 7500 s later (5 trapped by the registered rule); without it 6 of 6 stayed good, and a client-side cap of 20 drained it in 6 of 6. The test also passed with SGLang's own 955,757-token pool and, registered, on vLLM 0.32.0 (a frozen mechanism check failed there); on an H200 the all-miss capacity rose 2.7-fold, the peak only 1.6-fold. In registered rescue tests that cap (64 with SGLang's pool), engaged in an established trap, rescued 9 of 9 runs with no session shed; released after the drain, every run stayed good at the same load; uncapped controls stayed at zero hits. A registered test put the basin boundary between bursts of 25 and 100 sessions. We derive closed-population throughput $\mu(n)$ from first principles, with misses swelling running requests' KV and nothing fitted to any $\mu(n)$, hit or trap measurement (another GPU or engine takes one speed factor): its all-miss onset is the sessions in tool calls plus one pool of running sessions, a uniformly faster GPU lowers its peak ratio, and exogenous-gap models without running KV cannot reach zero hits. In sample it reproduces the SGLang curves within 10% at the peak but misses vLLM's earlier cliff; its frozen predictions held for the rescue, the basin test and the H200's nominal from-empty edge (the last two on runs begun before freezing), not for the H200 curve's tail or 4 of 9 release times; others are pending. Rates are nominal; registered tests use one model, one GPU type and synthetic sessions (exponential tools, no shared prefixes).
```

The private-repository variant of the abstract and its ancillary file set were withdrawn: the authors decided that the paper's repository becomes a new public repository (COORD, "Author decisions", 2026-10-30).

What the abstract says, against the paper. The opening test sentence reports E2 (Sec. 5.2): BURST at zero hits in 6 of 6 runs to the end, 5 of them trapped by the registered rule (seed 1 at 1.35 x is indeterminate); "the test also passed" covers native E2 and, as "registered" (not pre-registered), the vLLM test, whose frozen mechanism decision rule is not met because the online detector also alarmed in two capped runs. The H200 clause gives the measured 2.71-fold and 1.63-fold ratios, rounded (Sec. 5.5); the H200 has no registered test. The rescue sentence reports the registered rescue tests R1 and R4 (Sec. 5.3): 9 of 9 runs rescued, no session shed, every run good after release at the same arrival process and matching its no-burst control, the same-seed uncapped controls at zero hits; release came only after both client queues had been empty for 300 s, which the abstract states as "released after the drain" (fix-up 2 of fill 2) and the body in full. The basin sentence is BASIN-1 (registration name B1; Sec. 5.4); BASIN-2 is pending. The model sentence follows Sec. 6: nothing fitted to any mu(n), hit or trap measurement; one speed factor for the H200 and vLLM cells ("another GPU or engine": vLLM is slower than SGLang, so not "faster"); the mechanism of the cliff, hit-dependent running reservations ("misses swelling running requests' KV"; on every partially hitting state the gap is still the tool time, and the queue sets it only on the all-miss branch, Sec. 6.1); the all-miss onset of Proposition 2; the peak-ratio law of Proposition 3, which is for a uniform speed-up ("a uniformly faster GPU"); and Proposition 4 ("exogenous-gap models without running KV cannot reach zero hits"; it does not show that exogenous gaps cannot produce a cliff, since the model's own cliff forms with exogenous gaps). "In sample" marks that the agents that derived the model knew the SGLang curves. The outcome sentence reports the frozen predictions in hand (Sec. 7): held for the rescue verdicts (blind in time), BASIN-1 and the H200 from-empty edge in nominal multiples ("the last two on runs begun before freezing": both blind by access only; in realized rates the H200 edge is 1.496-1.503 and F2's 1.39 about 7% pessimistic, as on the A100); missed for the H200 curve's tail past the peak and for 4 of the 9 rescue release times (one R1 release, +18.8%, and all three R4 releases, 19-22% late, outside the frozen +-15%). It does not claim the H200 peak ratio, which is not blind to the first author. The second sentence glosses "metastable" as the physics sense (the good state persists until a large enough perturbation; in Bronson et al.'s terms the trap is the metastable failure state, Sec. 1-2). The review fix round dropped "=0.0715 sessions/s" (Sec. 4.2 and Fig. 1 give it) and "like its no-burst control" (Sec. 5.3) to make room. "Others are pending": BASIN-2, TOOLSLOW, SHED, the Llama-3.1-8B cell, the 150k/600k pool sweep and the 600k H200 cell. The request-level FCFS bound (Proposition 6 since fix-up 2 of fill 2, stated and proved in Appendix E) is no longer in the abstract; Sec. 3.4 summarizes it. The from-empty clause of the earlier abstract is gone; the body (Secs. 5.1, 7) states that the seed-0 bracket was not replicated with fresh seeds.

## Character counts

Counted with `scratchpad/fill2/count.py` (expands the LaTeX abstract of `main.tex`) and `scratchpad/fill2/count_abs.py` (checks the form text above against `main.tex`); length of the stripped text; arXiv's limit is 1920 characters:

```text
latex source chars: 1905 | form chars: 1903 | limit 1920 | margin 17 | ascii: True | newlines: 0
expanded latex == form: True
```

The margin is 17 characters (review fix round, 2026-10-31; from 1911). (Fix-up 2 of fill 2 replaced "after its release every run stayed good" with "released after the drain, every run stayed good", +8 characters, from 1903. Fill 2 rewrote the abstract around the rescue result: 1912 form characters. Fix-up 1 of fill 2 replaced "the native-pool release times" with "4 of 9 release times", which also counts the R1 release that missed the frozen tolerance.)

## Comments field

Recounted from a full build of this version (pdflatex, bibtex, pdflatex x2; no undefined references, no overfull boxes, no float warnings) on 2026-10-31 after the review fix round: 69 pages in total. The main text is pp. 1-22 (Table 1 now spans both columns; Section 6 starts on p. 12, Section 7 on p. 16, the conclusion on p. 22), the back-matter statements pp. 22-23, the references pp. 23-28, and Appendices A-I pp. 29-69. There are 11 figures and 18 tables.

```text
69 pages, 11 figures, 18 tables. Code, registrations, frozen predictions and all real-engine data: <URL of the public repository, the same as \repourl in main.tex>
```

Recount the pages when the `\pending` items are resolved.

## Categories

- **Primary: cs.DC** (Distributed, Parallel, and Cluster Computing). The paper is about LLM serving engines (SGLang, vLLM) and their admission and caching behaviour under load. The closest serving work it compares with (PEEK, CONCUR, MISA-T, VAMP, XPerf) is listed there.
- **Cross-list: cs.PF** (Performance). The core of the paper is performance modelling and measurement: closed-population throughput curves, a first-principles model of the thrashing curve (Sec. 6), a fluid model of the open system (Sec. 3), metastability and recovery thresholds. The queueing and metastability work it builds on (Alvaro et al.; Yao et al.) is in cs.PF.
- **Cross-list: cs.OS** (Operating Systems). The mechanism is classical OS thrashing: working sets, KV eviction, multiprogramming-level load control. ThunderAgent and Continuum, which treat agent KV as an OS memory problem, are in cs.OS.
- Not cs.LG or cs.AI: the paper has no learning method, and moderators may remove such a cross-list.

## ACM classes

C.4 (Performance of Systems); D.4.2 (Storage Management); D.4.8 (Performance).

The ACM class field is optional. MSC classes do not apply.

## License options

The license is chosen on the submission form and cannot be changed for this version afterwards.

1. **arXiv.org perpetual, non-exclusive license 1.0.** This gives arXiv only the right to distribute the paper and leaves all other rights with the authors. It is the most compatible choice if the paper later goes to a venue whose copyright or license form needs those rights.
2. **CC BY 4.0.** Anyone may reuse and adapt the paper with attribution. It is irrevocable for this version. Most venues accept a prior CC BY preprint, but check the target venue's policy first.
3. CC BY-SA 4.0, CC BY-NC-SA 4.0, CC BY-NC-ND 4.0 and CC0 are also offered. None of them has a particular reason to be used here.

This is an author decision.

## Before submitting

- Every `\pending{...}` marker must be resolved before posting; the list is in `paper/NUMBERS.md`, "Pending". Do not post a PDF that shows a red marker. The abstract's outcome sentence ("its frozen predictions held for ...; others are pending") must be revised when the pending outcomes are reported; add an outcome only if the form text stays at or under 1920 characters.
- `\repourl` in `main.tex` is the single place for the URL of the new public repository, whose name the authors choose; put the same URL in the comments field. Create the repository from the staged redacted copy (`Nova-Research-wt/public-release/`), add a LICENSE, and create and push tag `arxiv-v1` at the posted commit; the availability statement cites that tag and `provenance/REDACTIONS.md`.
- Done: `provenance/` is committed in 3c755f3 and the three loopvars CSVs in 6d84c84, both pushed on `r10/arxiv`; the cited-path merges are in `r10/arxiv` at cdb9a99. Still to do before the Monday build: merge the Sunday outcomes into `r10/arxiv`, together with r13/pool-sweep, r12/h200, r12/h200-prereg and r12/llama31 (which brings `notes/STATE_llama31.md` and `configs/agentload_prereg_2026-10-30_llama31.yaml`, both cited); then fast-forward `main` to the final paper commit (`origin/main` a4896dd is an ancestor of 2cdbf3b) or add `branch r10/arxiv` to `public-release/config/refs.conf`, which today publishes neither `r10/arxiv` nor `r13/*` or `r14/*`; rebuild the staged copy with a fresh mirror and activity export, so that `r13-theory-pred2` and `r14-extra-reg` are included; and check that the commit tagged `arxiv-v1` contains `paper/NUMBERS.md`, `configs/r13_theory_pred2.yaml`, `results/theory/merged/` and `results/theory/pred2/` (NUMBERS.md, Pending, item 7). Do not merge r13/theory, r13/pred2 or r14/extra again; they are in 2cdbf3b.
- Re-export GitHub's activity log (and /events, /tags while the 30-day window still covers 10-30 and 10-31) and rerun `provenance/make_push_times.py`, so that the archived log covers every registration and freeze push through the Llama registration (NUMBERS.md, Pending, item 2); then delete the "not yet in the archived copy" clauses of Appendices B and C. The paper now says that the development repository is private and that readers see its log only as this export.
- Append the dated N2 erratum to `notes/PREDICTIONS_r13_pred2.md` (NUMBERS.md, Pending, item 8); Appendix C already states it.
- When reporting any registered verdict, write "the registered analysis passes" (or fails) and do not repeat the tool's "pre-registered, decisive" labels: `analysis/summarize.py` sets them from commit order only, while Sec. 5.3 defines pre-registration by the GitHub push log.
- Upload `main.tex`, a freshly built `main.bbl`, `sections/*.tex` and the 11 figure PDFs in `figs/`: `fig1_e2_timeseries.pdf` to `fig7_e2_native_timeseries.pdf`, `fig8_theory_curves.pdf`, `fig9_theory_scaling.pdf`, `fig10_theory_fixed_points.pdf` and `fig_rescue.pdf` (the rescue figure, `sections/results.tex`). Do not upload `refs.bib`, `NUMBERS.md`, this file, `figs/README.md`, `figs/fig_lpm_crossing.pdf` (not used), `derived/`, `main.pdf` or aux and log files. Before submitting, rebuild in an empty directory that holds exactly the listed files and check that pdflatex exits 0 and the log has no "not found" line. Select pdflatex in the processing options. The LaTeX source contains no comments apart from line-end `%`.
- `notes/lit/CITATION_AUDIT_2026-10-25.md` still says that Yuan et al. (arXiv:2605.26297) is not cited; Appendix D says the audit predates that citation. An addendum to the note (Yuan et al. cited from v2 Table II, 98.85% to 16.78% at concurrency 15 to 20 on vLLM; the earlier 84.6-99.5% describes the controlled benchmark runs) would make the note match the paper.
