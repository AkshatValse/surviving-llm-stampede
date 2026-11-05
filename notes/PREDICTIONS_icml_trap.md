# Frozen predictions: the trapped engine as an overloaded re-entrant FIFO queue (tag `icml-trap-pred`)

Written 2026-11-05 (about 00:30-01:00 CST) on branch `claude/theory-icml-2164a9`, cut from `r10/arxiv` at `8aaabdb`. The
theory, with full proofs, is in `notes/THEORY_ICML_2026-11.md` (being written; this file freezes its predictions first).

**Blindness.** The author of this file read only committed data pulled on or before 2026-11-01 (`results/nova/`), the paper at
`8aaabdb`, and the Lu et al. text. No run result newer than 2026-11-04 was opened, and nothing on Nova was touched. The
predictions below are conditional on a run being trapped, so they apply to any new experiment that ends in a trap.

## The statement being tested (Theorem 1, in brief)

In the trap every turn misses (turn k costs c_k all-miss GPU seconds), the GPU is never idle and requests are served in the
order they join (request-level FCFS). Let G_k = P(T >= k), lambda_miss = 1 / sum_k c_k G_k (the model's all-miss capacity) and
z the root of lambda * sum_k c_k G_k z^{-k} = 1. Along every FIFO orbit (a request joining at u completes at u + V(u)) the
cycle Delta_n = V(u_n) solves the renewal recursion Delta_n = sum_k lambda c_k G_k Delta_{n-k}. Hence, for lambda > lambda_miss:
- the gap between a session's consecutive turns grows linearly in time with slope gamma = z - 1;
- the sessions present, and the turns served, have the z-tilted turn mix G_k z^{-k} / sum_j G_j z^{-j} (younger and cheaper than the stationary mix);
- sessions complete at D = lambda E[z^{-T}] > lambda_miss (youth premium, Theorem 2), while the backlog grows at alpha = lambda - D.

Nothing is fitted to any trap measurement: c_k comes from the frozen calibrated cost model of each cell
(`analysis/theory/cells/*.yaml`; the Llama cell with one speed factor fitted to its own E0a token rate, as in pred2's
conditional "fit" variant).

## What is frozen

`configs/icml_trap_predict.yaml` (and `results/theory/icml/frozen_predictions.json`) per cell
(`a100_300k`, `a100_native`, `vllm_300k`, `llama31_fit`, `h200_300k`, `h200_600k`, `a100_pool150k`, `a100_pool600k`):
- `asymptotic`: at multiples 1.1 to 6.5 of the cell's lambda_ref: z, gamma, alpha, D / lambda_ref, the mean prompt and turn
  index of the turns served, the composition token ratio, and Theorem 2's factors H_T and C_c;
- `e2_protocol`: for the registered burst protocol (200 sessions at 1200 s, window [5700, 8700) s): the exact FIFO fluid's
  window slope, completion rate, mean prompt and cycle slope; the stochastic FIFO distribution of the registered slope
  statistic (mean, sd, P(slope > 0.5 (lambda - lambda_ref)), P(at least 2 of 3)); and, per seed 0-5, the plan's realized
  base-arrival rate in the window (a protocol quantity, `agentload.workload` stream S_ARRIVALS) and the plug-in slope
  lam_window_plan - D.

## Scoring, declared now (copied from the YAML)

Applies to every run of a new experiment whose follow-up hit fraction over its evaluation window is below 0.2 and whose window
starts at least 3000 s after the trigger began, on a listed cell, at its nominal multiple of lambda_ref.
- **S1 composition:** mean prompt of the turns completed in the window within +-8% of `P_served_mean` per run; pooled mean within +-5%.
- **S2 cycle growth:** OLS slope of the 300 s medians of the gap against time, pooled over the runs of a (cell, multiple), within [0.6, 1.4] x gamma.
- **S3 youth premium:** session completion rate in the window above lambda_ref in every trapped run whose realized window arrival
  rate is at least 1.1 lambda_ref; pooled mean within +-15% of D.
- **S4 backlog:** pooled mean backlog slope within +-35% of alpha (or of the E2 fluid slope).
- **S5 per seed:** for a constant-rate client plan with known seed, slope predicted by lam_window_plan - D; scored by the side of
  the registered threshold 0.5 (lambda - lambda_ref) and by |slope - plug-in| <= 0.01 /s.
- **Refutation:** Theorem 1's application to the engine is refuted for a (cell, multiple) if the pooled S1 or S2 fails in a group of at least two trapped runs.

The tolerances were chosen after seeing the committed runs (calibration, not blind). The runs they will score did not exist
when this tag was pushed.

## Retrospective check on the committed runs (not blind; `results/theory/icml/trap_check.md`)

57 trapped E2-protocol runs (SGLang 300k r0/r1, BASIN b50/b60/b100, SHED t600, TOOLSLOW d30, LPM r0/r1 past their fallback,
native, vLLM (6 registered and 6 exploratory runs repeating their workloads), H200 600k, Llama-3.1-8B) and 13 unstable E0b
runs: served-prompt means within +-8% (most within +-3%) of the tilted-mix prediction in the E2 runs (6,115 to 9,393 tokens
predicted across cells and rates), the gap trend tracks gamma from 0.013 to
0.13 per second, every trapped run completes sessions above lambda_ref (1.10-2.40 lambda_ref), and the seed whose plan has
the lowest window arrival rate (seed 1 at 1.35x, 6-9% below nominal in every cell, common random numbers) is the one whose
registered slope test came out indeterminate or draining in SGLang 300k, vLLM and Llama.

## Reproduce

```
PYTHONPATH="src;." python -m analysis.theory.icml.freeze_predictions --reps 200     # ~4 min
PYTHONPATH="src;." python -m analysis.theory.icml.run_check --reps 400              # ~5 min, the retrospective table
```
