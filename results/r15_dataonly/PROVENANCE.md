# Data-only results of 2026-11-04/05 (D1, D2, D4, D5, pool share): provenance

These analyses read only real-engine runs already committed under `results/nova/` (pulled on or before 2026-11-01). No new
GPU run, no Nova access. They are post hoc. The paper uses them in Appendix C (`paper/sections/v2_app_dataonly.tex`) and in
Sections 3 and 5 of the reframed draft.

## Origin (first computation)

Computed 2026-11-04, about 23:30-23:56 CST, each by a single agent of the lead session's workflow `wf_c62273d6-d59`, in that
session's scratchpad
`C:\Users\Akshat\AppData\Local\Temp\claude\93194b88851e3ff4\90500cb0-d13d-4ffe-a42a-2ca3a3f8018c\scratchpad\tonight\`.
Copied here unchanged on 2026-11-05:
- `analysis/r15_dataonly/original/data-A/`: `inventory.py` (run list), `d1_trap_outlives.py`, `d1_summary.py` (D1),
  `d2_goodput.py`, `d2_summary.py` (D2). Outputs in `results/r15_dataonly/original/data-A/`.
- `analysis/r15_dataonly/original/data-B/`: `extract.py`, `states.py`, `d3d5.py` (D3, D5), `design.py`. Outputs in
  `results/r15_dataonly/original/data-B/` (`bins.csv` is the 100 s bin table that `d3d5.py` reads).
- D4 (Lu et al.'s model on our cells) was a hand analysis in the workflow's theory-pred agent; its text is the field
  `lu_model_on_our_configs` of `inv_theory-pred.json` in the same scratchpad, summarized in `TONIGHT_PLAN_2026-11-05.md` (COORD).

The original scripts contain absolute paths of that scratchpad and of the `Nova-Research-wt/arxiv` worktree (for the frozen
theory JSONs, identical to `results/theory/merged/` here); edit them before re-running.

## Independent recomputation (second computation)

2026-11-05, about 02:15-02:45 CST, by separate agents started from the reframe-draft session, each with its own code written from
the raw CSVs, not importing the first scripts (which they read only afterwards, to explain differences):
- D1, D5 and pool share: `analysis/r15_dataonly/verify_d1d5/` (`build.py`, `d1.py`, `d5.py`, `d5var.py`, `d5var2.py`, `e0b.py`,
  `pool.py`, `final.py`); report and per-run tables in `results/r15_dataonly/verify_d1d5/verify_D1D5.md` and the CSVs beside it.
  The 8 MB intermediate `runs_d1.csv` was not copied (`d1.py` rebuilds it).
- D2: `analysis/r15_dataonly/verify_d2/` (`gp.py`, `run.py`, `run2.py`); report `results/r15_dataonly/verify_d2/verify_D2.md`.
- D4: `analysis/r15_dataonly/verify_d4/`; report `results/r15_dataonly/verify_d4/verify_D4.md` (see the status line below).

## Verdicts and the numbers the paper uses

| item | first computation | independent check | paper uses |
|---|---|---|---|
| D5 persistence | 50 trapped FCFS runs, 104.5 h, 0 escapes, bound 5.8% | CONFIRMED in substance: 50 runs (49 burst + TOOLSLOW d30 s2), 0 escapes, max post-onset window hit 0.164; 99.0-103.1 h (window end/start convention), shortest span 6100-6400 s; 104.5 h not reproduced | 50 runs, 0 escapes, about 100 h (99-103 h), bound 5.8% |
| D5 side counts | from-empty 16 collapses, 1 escape; LPM 10 trapped, 5 escapes | from-empty CONFIRMED (escape: 150k pool, 1.30x, seed 0, run 20261031-093158); LPM CORRECTED: stock LPM 9 trapped, 4 escapes; LPM-INF 1 trapped run, escaped | stock LPM 4 of 9; LPM-INF its one trapped run |
| D1 trap outlives trigger | 16 runs, all later turns 0.000 hits | CORRECTED: all 16 have every trigger session gone 558-6246 s before the end (727-15,453 later turns); 15 have zero hits after; TOOLSLOW d30 s2 had 4 hits in 5,937 (0.00067) | 16 runs; zero hits in 15, 4 of 5,937 in the TOOLSLOW run |
| D1 A100 200-burst cells | 3-30 burst sessions left, <= 5.8% of population | 3-30 CONFIRMED; 5.8% not reproducible (max 4.07% of sessions present at the end) | 3-30, at most 4.1% of sessions present |
| pool share in traps | 63-79% in registered traps (b60 56-75%) | CORRECTED: 63-79% holds for the six SGLang 300k r1 runs; 55-83% over all 34 non-native SGLang FCFS stuck runs; native 85-94%; vLLM 92-94% (`kv_cache_usage_perc`) | the corrected ranges, with the gauge caveat |
| D2 SLO goodput, first hour | 99.4-100% loss | CORRECTED: 99.2-100% (26 of 30 runs with no good session); mean-latency reference | 99.2-100% |
| D2 judged window | 100% loss; CAPPED/rescue within 0-2% of NOBURST | CONFIRMED (CAPPED 0.00-1.74%; rescue -0.3% to +0.9%), robust to a 2x reference | as checked |
| D2 first-hour cost of the cap | CAPPED 5-57%, rescue 46-97% | reference-dependent: CAPPED 4.2-55.7% (p10 ref 4.5-57.0%), rescue 45.4-94.8% (45.7-96.8%) | CAPPED 4-57%, rescue 45-97%, stated as reference-dependent |
| D4 onset | Lu-fit MAE 4.7 (7 cells) vs ours 1.5; 4.1 vs 1.55 on 5 blind cells | CONFIRMED (4.66/1.53; 4.11/1.55); native Lu-fit 102.5 not 102.4; of the 5 cells 3 blind in time, 2 by access only; robust (kappa fitted to all 8: 3.74 vs 1.42; LOO 4.72; token hit 4.05 vs 1.53); the 1.9 C/cbar column is not their prediction; affine intercept 2.97 +- 0.71 (95% CI -0.1 to 6.0), not 'about +2' | Table tab:lu and its caption |
| D4 H200 shift | +6.7/+10.9 measured vs +5.8/+6.6 ours, 0 for Lu | CONFIRMED, with the qualifier 'one hit curve carried across GPUs'; per-GPU refit still +6.7 at H200 600k | as checked |
| D4 Eq. 2 | f <~ 0.5, flags 7 of 8, 'nearly vacuous' | numbers CONFIRMED (300k f = 0.315); 'nearly vacuous' UNFAIR: f moves along the curve (0.19-0.53 at the peak, 0.67-0.95 at n_b) | described, not scored |
| D4 window | native/300k 2.06 measured, Lu 3.19, ours 2.11 | numbers CONFIRMED; comparison UNFAIR (drops their prefill/decode bounds); ours in sample | omitted |
| D4 drain | Eq. 4 20-37% early, ours 2-18% | CONFIRMED with R4 -34 to -39%; reword: Eq. 4 is for resident-first ordering with healthy reuse; our own single-phase variant is 12-34% early, so the gain is the two-phase structure | the like-for-like statement |

Lu et al.'s goodput also requires 95% of decode steps to meet an ITL target; we have no per-token latencies, so both
computations omit it, which makes the losses lower bounds.

## Not read

Neither computation read any run of 2026-11-05 (TOOLSLOW-W, CUT, REPLICATE-EDGE) or touched Nova.
