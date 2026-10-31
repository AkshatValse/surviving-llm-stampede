# arXiv submission metadata

Prepared 2026-10-31 for the build of `paper/main.tex` with the r10/arxiv revision, the registered vLLM verdict, the first-principles model and the frozen-prediction section applied (fix-up round 1 included). The PDF abstract in `main.tex` is the LaTeX form of the form abstract below: the two texts are identical once the macros are expanded (`$\lref$` to `$\lambda_{ref}$`, `\sps` to ` sessions/s`, `3000\,s` to `3000 s`, `\%` to `%`). If one is edited, edit the other and recount.

## Title

Thrashing Returns: Metastable Failures in Prefix-Cached Agent Serving

## Authors

Akshat Valse, Ali Jannesari

(Department of Computer Science, Iowa State University, Ames, IA, USA. Corresponding author: avalse@iastate.edu. Ali Jannesari: jannesar@iastate.edu. The authors should confirm both addresses.)

## Abstract (form)

```text
Prefix caching keeps an LLM agent session's KV across its tool calls, so a turn that hits prefills only new tokens. We show that this can make the engine's high-hit state metastable. On SGLang 0.5.22 with Qwen2.5-7B-Instruct, one A100 and a 300k-token pool, an empty server stayed good for 3000 s at nominal rates up to 2.0 times $\lambda_{ref}$=0.0715 sessions/s, the measured all-miss capacity. In a pre-registered paired test at 1.35 and 1.65 $\lambda_{ref}$, a burst of 200 sessions left all 6 runs at zero hits over a window ending 7500 s after it (5 trapped by the registered rule), without the burst 6 of 6 stayed good, and a client-side cap of 20 recovered 6 of 6. A second such test, with the 955,757-token pool SGLang sizes itself, put all 18 runs in their predicted states. On vLLM 0.32.0 the registered analysis passes at both rates, though a frozen mechanism check failed (a hit-rate detector also fired in 2 capped runs). In BURST runs a session's gap between turns, mostly turn latency, is 4 to 10 times the pool's rewrite time (0.01 to 0.03 in the good state). We derive the closed-population throughput $\mu(n)$ from first principles, fitting nothing to any $\mu(n)$, hit or trap measurement (a faster GPU or engine takes one speed factor); its all-miss onset is the sessions in tool calls plus one pool of running sessions. It reproduces the SGLang curves within 10% at the peak but misses vLLM's earlier cliff. Its predictions for a faster GPU, other pools, a second model, burst sizes and a cap rescue were frozen; outcomes are pending. Under request-level FCFS and stated assumptions, including that the congested engine computes prompt tokens no faster than with caching disabled, no online eviction rule lets $\mu(n)$ exceed the all-miss capacity as $n\to\infty$. Rates are nominal; registered tests use one model, one GPU type and synthetic sessions (exponential tool times, no shared prefixes).
```

The private-repository variant of the abstract and its ancillary file set were withdrawn: the authors decided that the paper's repository becomes a new public repository (COORD, "Author decisions", 2026-10-30).

What the abstract says, against the paper: the vLLM sentence uses "the registered analysis passes", not "pre-registered" or "decisive", and states that the frozen r11 mechanism decision rule is not met (check (c), the online detector, also alarmed in two CAPPED runs; Sec. 6.5); "fitting nothing to any $\mu(n)$, hit or trap measurement" is the wording of Sec. 4, and the parenthesis says that the H200 and vLLM cells take one speed factor fitted to their all-miss token rate; the bound of Proposition 1 is stated with (A3), its bounding assumption; "were frozen; outcomes are pending" says that no outcome of these predictions is reported, and does not claim that nobody had seen the H200 values for n <= 32 (the first author had; Sec. 7).

## Character counts

Counted with `scratchpad/integrate2/fixup1/count.py` and `scratchpad/integrate2/plan/count_abs.py` (length of the stripped text; arXiv's limit is 1920 characters):

```text
form chars: 1919 | limit 1920 | margin 1 | ascii: True | newlines: 0
latex source chars: 1899
expanded latex == form: True
```

The margin is 1 character, so any later addition must be offset by a cut. (2026-10-31 fix-up 2: "were frozen in advance" became "were frozen; outcomes are pending", the clause became its own sentence, and "two capped runs" became "2 capped runs".)

## Comments field

Recounted from a full build of this version (pdflatex, bibtex, pdflatex x2; no undefined references, no overfull boxes, no float warnings): 52 pages in total. The main text with the back-matter statements is pp. 1-33, the references pp. 33-38, and Appendices A-G pp. 39-52. There are 10 figures and 13 tables.

```text
52 pages, 10 figures, 13 tables. Code, registrations, frozen predictions and all real-engine data: <URL of the public repository, the same as \repourl in main.tex>
```

Recount the pages when the `\pending` items are resolved.

## Categories

- **Primary: cs.DC** (Distributed, Parallel, and Cluster Computing). The paper is about LLM serving engines (SGLang, vLLM) and their admission and caching behaviour under load. The closest serving work it compares with (PEEK, CONCUR, MISA-T, VAMP, XPerf) is listed there.
- **Cross-list: cs.PF** (Performance). The core of the paper is performance modelling and measurement: closed-population throughput curves, a first-principles model of the thrashing curve (Sec. 4), a fluid model of an open system, metastability and recovery thresholds. The queueing and metastability work it builds on (Alvaro et al.; Yao et al.) is in cs.PF.
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

- Every `\pending{...}` marker must be resolved before posting; the list is in `paper/NUMBERS.md`, "Pending". Do not post a PDF that shows a red marker. The abstract's "Its predictions ... were frozen; outcomes are pending" must be changed when outcomes are reported; if an outcome is reported in the abstract, add it only if the form text stays under 1920 characters.
- `\repourl` in `main.tex` is the single place for the URL of the new public repository, whose name the authors choose; put the same URL in the comments field. Create the repository from the staged redacted copy (`Nova-Research-wt/public-release/`), add a LICENSE, and create and push tag `arxiv-v1` at the posted commit; the availability statement cites that tag and `provenance/REDACTIONS.md`.
- Commit `provenance/` and the derived tables the paper relies on, including `paper/derived/loopvars_e2.csv`, `loopvars_e2_native.csv` and `loopvars_vllm_expl.csv` (added in this revision), and merge the branches whose paths the paper cites (NUMBERS.md, Pending, item 7).
- When reporting any registered verdict, write "the registered analysis passes" (or fails) and do not repeat the tool's "pre-registered, decisive" labels: `analysis/summarize.py` sets them from commit order only, while Sec. 5.3 defines pre-registration by the GitHub push log.
- Upload `main.tex`, a freshly built `main.bbl`, `sections/*.tex` and `figs/fig1`-`fig10` PDFs (`fig1_e2_timeseries.pdf` to `fig7_e2_native_timeseries.pdf`, `fig8_theory_curves.pdf`, `fig9_theory_scaling.pdf`, `fig10_theory_fixed_points.pdf`). Do not upload `refs.bib`, `NUMBERS.md`, this file, `figs/README.md`, `derived/`, `main.pdf` or aux and log files. Select pdflatex in the processing options. The LaTeX source contains no comments apart from line-end `%`.
- `notes/lit/CITATION_AUDIT_2026-10-25.md` still says that Yuan et al. (arXiv:2605.26297) is not cited; Appendix D says the audit predates that citation. An addendum to the note (Yuan et al. cited from v2 Table II, 98.85% to 16.78% at concurrency 15 to 20 on vLLM; the earlier 84.6-99.5% describes the controlled benchmark runs) would make the note match the paper.
