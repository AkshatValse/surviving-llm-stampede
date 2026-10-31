# arXiv submission metadata

Prepared 2026-10-30 for the build of `paper/main.tex` with all section edits of the r10/arxiv revision applied. The PDF abstract in `main.tex` is the LaTeX form of the public abstract below: the two texts are identical once the macros are expanded (`$\lref$` to `$\lambda_{ref}$`, `\sps` to ` sessions/s`, `3000\,s` to `3000 s`, `$n=24$` to `n=24`). If one is edited, edit the other.

## Title

Thrashing Returns: Metastable Failures in Prefix-Cached Agent Serving

## Authors

Akshat Valse, Ali Jannesari

(Department of Computer Science, Iowa State University, Ames, IA, USA. Corresponding author: avalse@iastate.edu. Ali Jannesari: jannesar@iastate.edu. The authors should confirm both addresses.)

## Abstract, public repository (default)

Use this text if `AkshatValse/Nova-Research` is public when the preprint is posted.

```text
Prefix caching keeps an LLM agent session's KV across the tool calls between turns, so a turn that hits prefills only its new tokens. We show that this can make the engine's high-hit state metastable. On SGLang 0.5.22 with Qwen2.5-7B-Instruct, one A100 80GB and a 300k-token KV pool, closed-population throughput $\mu(n)$ peaks at 0.233 sessions/s at n=24 and falls to all-miss by n=48, while an empty server stayed good in single 3000 s runs at nominal rates up to 2.0 times $\lambda_{ref}$=0.0715 sessions/s, the measured all-miss capacity, and was unstable at 2.5. In a pre-registered paired test at 1.35 and 1.65 $\lambda_{ref}$, a burst of 200 sessions trapped the server by the registered rule in 5 of 6 runs, and all 6 had zero cache hits over an evaluation window ending 7500 s after it; without the burst 6 of 6 stayed good, and a client-side cap of 20 sessions recovered 6 of 6. A simulator whose cost model was fitted only to server-log timing predicted this outcome in a commit pushed before submission. vLLM 0.32.0's own curve and edge give the same window and cap, with a steeper cliff; exploratory burst-only runs had zero hits in 6 of 6, and a registered paired test is pending. With the pool SGLang sizes itself (955,757 tokens) the cliff moves out about threefold, the from-empty edge is between 5.5 and 6.5 $\lambda_{ref}$, and a second pre-registered test at 2.5 and 4.0 $\lambda_{ref}$ with a cap of 64 put all 18 runs in their predicted states. Rates are nominal; runs use one model, one GPU type and synthetic sessions with exponential tool times and no shared prefixes. We give a quasi-static model, prove that under request-level FCFS and stated assumptions no online eviction rule lets $\mu(n)$ exceed the all-miss capacity as $n\to\infty$, compare published mechanisms in an earlier, uncalibrated simulator, and give a diagnostic: measure $\mu(n)$ for the workload and cap sessions from it.
```

## Abstract, private repository (G21)

Use this text if the repository stays private. It drops "pre-registered", because the paper defines that term by the GitHub push log (Sec. 4.3), which readers could then reach only through the ancillary files. It also says the predictions were in a commit made, not pushed, before submission. It differs from the public text in three places only.

```text
Prefix caching keeps an LLM agent session's KV across the tool calls between turns, so a turn that hits prefills only its new tokens. We show that this can make the engine's high-hit state metastable. On SGLang 0.5.22 with Qwen2.5-7B-Instruct, one A100 80GB and a 300k-token KV pool, closed-population throughput $\mu(n)$ peaks at 0.233 sessions/s at n=24 and falls to all-miss by n=48, while an empty server stayed good in single 3000 s runs at nominal rates up to 2.0 times $\lambda_{ref}$=0.0715 sessions/s, the measured all-miss capacity, and was unstable at 2.5. In a registered paired test at 1.35 and 1.65 $\lambda_{ref}$, a burst of 200 sessions trapped the server by the registered rule in 5 of 6 runs, and all 6 had zero cache hits over an evaluation window ending 7500 s after it; without the burst 6 of 6 stayed good, and a client-side cap of 20 sessions recovered 6 of 6. A simulator whose cost model was fitted only to server-log timing predicted this outcome in a commit made before submission. vLLM 0.32.0's own curve and edge give the same window and cap, with a steeper cliff; exploratory burst-only runs had zero hits in 6 of 6, and a registered paired test is pending. With the pool SGLang sizes itself (955,757 tokens) the cliff moves out about threefold, the from-empty edge is between 5.5 and 6.5 $\lambda_{ref}$, and a second registered test at 2.5 and 4.0 $\lambda_{ref}$ with a cap of 64 put all 18 runs in their predicted states. Rates are nominal; runs use one model, one GPU type and synthetic sessions with exponential tool times and no shared prefixes. We give a quasi-static model, prove that under request-level FCFS and stated assumptions no online eviction rule lets $\mu(n)$ exceed the all-miss capacity as $n\to\infty$, compare published mechanisms in an earlier, uncalibrated simulator, and give a diagnostic: measure $\mu(n)$ for the workload and cap sessions from it.
```

### Ancillary file set for the private case

If the repository stays private, upload these files under `anc/` so that the registrations, the frozen predictions and the push log can still be checked. The SHA-256 hashes of the four registration files are printed in Appendix B; the copies must be byte-identical (they match the values below, checked 2026-10-30).

| anc/ path | Source in the repository | Purpose |
|---|---|---|
| `anc/registrations/agentload_prereg_2026-10-24.yaml` | `configs/` | E2 registration, SHA-256 `2a6d680a...5cc0ac6` |
| `anc/registrations/agentload_prereg_2026-10-25_native.yaml` | `configs/` | native E2 registration, `21bf7c03...b9bf776c1` |
| `anc/registrations/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml` | `configs/` | exploratory vLLM registration, `c5037cac...c8891aeab5` |
| `anc/registrations/agentload_prereg_2026-10-30_vllm.yaml` | `configs/` | vLLM registration, `8f2d5b44...2bb95f84` |
| `anc/predictions/PREDICTIONS.md` | `notes/` | B1-B4, frozen at tag `r6-predictions-frozen` |
| `anc/predictions/PREDICTIONS_native.md` | `notes/` | B1n-B4n, tag `r8-native-predictions-frozen` |
| `anc/predictions/PREDICTIONS_vllm.md` | `notes/` | B1v-B4v, tag `r9-vllm-predictions-frozen` |
| `anc/predictions/PREDICTIONS_VERIFICATION.md` | `notes/` | the verifier's record (modified in this worktree; upload the committed version) |
| `anc/provenance/github_activity_2026-10.json` | `provenance/` | GitHub push log, the external record of push times |
| `anc/provenance/push_times_2026-10.tsv` | `provenance/` | push times derived from it |
| `anc/provenance/sacct_cited_jobs_2026-10-30.txt` | `provenance/` | Slurm submit, start and end times of every cited job |
| `anc/provenance/commit-map.tsv` | `provenance/` | old-to-new hash map of the 2026-10-22 history rewrite |
| `anc/README.txt` | new | one paragraph mapping these files to Sec. 4.3 and Appendices B-D |

All of these are text files, about 460 KB in total. The sacct file contains the cluster account string `f2026.coms.6250.02` 108 times, and the GitHub JSON contains the account name and the private repository's name; the authors should accept this or redact those fields before uploading (redacting changes the files, so say so in `anc/README.txt`). In the private case, the main text must also change: the "Code and data availability" section, `\repourl`, and the method and appendix sentences that cite repository paths would need to point to `anc/` instead.

## Character counts

Counted with `scratchpad/fixrun/r2fix/count.py` (length of the stripped text; arXiv's limit is 1920 characters):

```text
form_public.txt chars: 1917 ascii: True newlines: 0
form_private.txt chars: 1907 ascii: True newlines: 0
```

Recounted 2026-10-31 after the theory clause became "lets $\mu(n)$ exceed the all-miss capacity as $n\to\infty$", "predicted this pass" became "predicted this outcome", and "A simulator fitted only to server-log timing" became "A simulator whose cost model was fitted only to server-log timing" (only the cost model was fitted to the logs; the batching mode was chosen against the real Stage C curve). The public text is now 3 characters under the limit, so any later addition must be offset by a cut. The LaTeX source of the PDF abstract is 1879 characters. A script check confirms that it expands to exactly the public text.

## Comments field

Recounted from a full build of this version (pdflatex, bibtex, pdflatex x2; no undefined references, no warnings, no overfull boxes; the bibliography, Appendix B and Table 8 are set ragged right to avoid stretched lines): 36 pages in total. The main text with the back-matter statements is pp. 1-23, the references (78 entries) are pp. 24-28, and Appendices A-E are pp. 29-36. There are 7 figures and 8 tables (Tables 1-2 in the main text, Tables 3-8 in the appendices).

Public repository:

```text
36 pages, 7 figures, 8 tables. Code, registrations, frozen predictions and all real-engine data: https://github.com/AkshatValse/Nova-Research
```

Private repository:

```text
36 pages, 7 figures, 8 tables. The registration files, frozen predictions and GitHub push log are in the ancillary files.
```

Recount the pages if anything changes after this build, in particular when the vLLM verdict replaces the `\pending` item in Sec. 5.7 (G20).

## Categories

- **Primary: cs.DC** (Distributed, Parallel, and Cluster Computing). The paper is about LLM serving engines (SGLang, vLLM) and their admission and caching behaviour under load. The closest serving work it compares with (PEEK, CONCUR, MISA-T, VAMP, XPerf) is listed there.
- **Cross-list: cs.PF** (Performance). The core of the paper is performance modelling and measurement: closed-population throughput curves, a fluid model of an open system, metastability and recovery thresholds. The queueing and metastability work it builds on (Alvaro et al.; Yao et al.) is in cs.PF.
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

- The registered vLLM paired test (jobs 17166121-17166138) is still running. In this build, Sec. 5.7 shows its verdict as a single red `\pending` box (the only one in the PDF), both abstracts say "a registered paired test is pending", the last paragraph of the introduction says "That test was still running when this version was prepared", and the conclusion says the test "was still running when this version was prepared". When the verdict is in, replace the Sec. 5.7 box with the verdict (compared with B3v, which Sec. 5.7 states), rewrite those two sentences of the introduction and conclusion, rewrite the vLLM sentence of both abstracts (keep each under 1920 characters and recount; they are now 3 and 13 characters under it), keep the PDF and form texts identical, and remove `\pending` and `xcolor` from `main.tex`. Do not post a PDF that shows the red box.
- When writing the vLLM verdict, report it as "the registered analysis reports a pass" (or a fail) and do not repeat the tool's "pre-registered, decisive" labels. The analysis (`analysis/summarize.py`) sets `pre_registered` and `kill_test_pass_decisive` from commit order only (a valid, clean, FILLED file whose last commit predates every run), so it will label this test pre-registered, while Sec. 4.3 and Sec. 5.7 call it registered but not pre-registered because the file reached GitHub after the first job had started. The red `\pending` box says the same.
- Upload `main.tex`, a freshly built `main.bbl`, `sections/*.tex` and `figs/fig1`-`fig7` PDFs. Do not upload `refs.bib`, `NUMBERS.md`, this file, `figs/README.md`, `derived/`, `main.pdf` or aux and log files. Select pdflatex in the processing options.
- Public case: make the repository public, add a LICENSE, and create and push tag `arxiv-v1` at the posted commit. The availability statement cites that tag. Also commit `provenance/`, which is currently untracked apart from `commit-map.tsv`, and the untracked derived tables the paper relies on (`paper/derived/e0b_vllm_hit.csv`, `e2_client_side.csv`, `e2_client_side_summary.csv`). The tag does not exist yet; until it is pushed, the availability statement and the caption of Table 8 point at nothing.
- `notes/lit/CITATION_AUDIT_2026-10-25.md` still says that Yuan et al. (arXiv:2605.26297) is not cited; Appendix D now says the audit predates that citation. An addendum to the note (Yuan et al. cited from v2 Table II, 98.85% to 16.78% at concurrency 15 to 20 on vLLM; the earlier 84.6-99.5% describes the controlled benchmark runs) would make the note match the paper.
