# Triage of the final read-only review of draft 54d3529 (2026-11-05, 08:55–09:20 CST)

Two reviewers read the diff `d4b4f1d..54d3529` and the abstract, intro and conclusion. Neither changed anything.
- `NUMBERS_AUDIT.md`: findings M1–M2, S1–S5, N1–N5. Every number, time, hash and job ID matches the sources. The R12
  slope/α figures reproduce exactly with nothing dropped. The abstract is 1916/1920.
- `CLAIMS_REVIEW.md`: findings 1–13, plus a replacement abstract (`abstract_proposed.tex`, 1913/1920 by
  `COORD/release-tools/count.py`).

## APPLY

**Must-fix**
- **Abstract.** Use `abstract_proposed.tex` verbatim. It changes three things:
  - "met pre-set tolerances" becomes "met 4 of 5 pre-set scores" (S5 failed in two of the four runs);
  - "the traps persisted or drained slowly" becomes "the traps persisted, backlogs rising or falling slowly" (no CUT-B
    trap drained; all were stuck at 8700 s);
  - the redundant "The model is an idealization;" is dropped.

  Re-count, and update the form twin in ARXIV_METADATA.md and the NUMBERS.md abstract row.
- **M1 / claims 3, intro l.71.** "a flat backlog fits CUT-A as well" is false: S = 0 misses by 0.0022–0.0040 /s. Write
  "(constant completions at the nominal cut rate fit CUT-A as well over [3000, 8700) s)".
- **S1, stale provenance on the paper branch.** The draft branch has the 07:10 export, with jobs 17256870–75 RUNNING and no
  end times. Check out `push_times_2026-11-05.tsv`, `sacct_cited_jobs_2026-11-05.txt` and
  `sacct_cited_jobs_2026-11-05_utc.txt` from `origin/r15/tonight`; they are the same at 4a37e25 and later.

**Should-fix**
- **S2 = claims 7.** Add CUT-B's quasi-static counterfactual: had it been a comparator, seed 0 would have favoured it (0.00036
  against 0.00099) and the arm would still have passed, 2 of 3.
- **S3, from-empty excess.** Replace "(not checked)" with the checked fact: the window arrival rates are 3.8–13.1% above
  nominal in all 13 runs, by `trap_check.json`. Recompute that range from the file yourself before writing it, and add a
  NUMBERS.md row.
- **S4.** Scope "mean ratio 0.99" to the 57 E2-protocol runs (v2_theory l.7–8).
- **S5.** Add the TOOLSLOW-D15 fluid miss to limitations.tex:9 and appendix_supp.tex:118.
- **Claims 4.** Wherever CUT-B is described, use "shrank the backlog", not "drained", and say all three runs were still
  trapped at 8700 s. Places: intro l.69 and l.80; conclusion l.40–41; validation l.217, l.228–229 and l.231–232; control
  l.33. Keep "drained" for SHED, which did empty.
- **Claims 5 and 6.** In the conclusion and intro, state the S5 misses ("four of the five pre-set scores; a per-run slope
  check failed in two"), and give TOOLSLOW-D15's trapped run its four pooled scores.
- **Claims 8.** "rejects only the two constant-throughput readings it was built against".
- **Claims 9 (closes R6), only with a committed script.** Write `analysis/theory/icml/premium_over_tokrate.py`, reading
  `trap_check.json` only:
  - for each of the 57 E2-protocol stuck runs, compute completions/λ_ref divided by the run's measured token-rate ratio
    (its uncached tokens/s over its cell's E0a all-miss rate);
  - force-add the output JSON and add a NUMBERS.md row.

  The reviewer's check gives 1.08–1.81, minimum BASIN-60 seed 1 (1.118 λ_ref at a ratio of 1.034), with ratios
  0.95–1.12. If your script reproduces that, add the one sentence to the youth-premium bullet. If it does not, leave the
  bullet as it is and tell the lead.
- **Claims 10–13.**
  - Intro: "two thirds" over the 57 runs.
  - Intro: Theorem 2's premium is proved for ρ ≥ 1.04.
  - Conclusion: "model F, the trapped engine idealized as …".
  - Related: "an engine test of the reading", with "CUT-A and CUT-B are consistent with it".
- **N1–N5.**
  - N1: "of λ − λ_miss" on the 0.63–0.64.
  - N2: α at the nominal rate.
  - N3: "four blind runs".
  - N4: source of the pull and verdict times in the timeline caption.
  - N5: the stale NUMBERS.md rows.

## NOT APPLIED

- Nothing rejected. The structural DEFER list from the first review (`notes/review_df31480/TRIAGE.md`) stays on the meeting
  brief.
