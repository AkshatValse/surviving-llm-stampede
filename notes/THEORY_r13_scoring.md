# Round-13 theory: frozen scoring declaration

This declaration is frozen with the predictions under tag `r13-theory-pred` (2026-10-31). The machine-readable copy is `analysis/theory/merged/scoring.yaml`, and it is embedded under `scoring` in every prediction JSON. It was written before any blind result was read, and it answers the freeze audit: without fixed primaries, tolerances and refutation rules, almost any outcome could be matched afterwards to one of the several numbers each JSON carries.

## Primaries (one per quantity)

| quantity | primary | also reported (bands, never alternative primaries) |
|---|---|---|
| μ_max, peak n, μ(n) below n_b, window | F1 annealed curve | fluid curve |
| 0.5-hit crossing n_half | fluid | F1 |
| all-miss onset n_b | fluid identity T3(b) | none |
| from-empty edge | F2 (target n_b, I_D from Campbell, H = 3000 s) | A's level crossing; F2 variants |
| trapped state | B's fluid round robin | none |
| rescue release time | two-phase drain, fluid phase 1 | F1 phase 1; collapsed bounds |
| H200 cost variant | `h200_300k` (uniform s = 2.742 fitted to the absolute E0a tokens) | ratio fits (s = 2.703 and 2.761), decode2, e0a2 |
| Llama | `llama31_8b_300k` a priori, plus the speed-table conditional | none |

## Estimator

- **Primary:** turns-based. μ = completed turns per second / E[T], which is what the model's μ = ν/E[T] is.
- **Also reported:** μ_sessions, with both errors.
- **On the measured cells:** F1 μ_max errors on the turns-based estimator are +3.6% (300k), +6.3% (native) and +11.6% (vLLM). On μ_sessions they are +0.2%, +3.3% and +7.2%.

## Tolerances counted as a hit

- **μ_max:** within ±10%.
- **Window:** within ±10%.
- **Peak n:** inside the measured flat top (the grid points within 2% of the measured grid maximum) or at the grid point next to it.
- **n_half:** within ±3 sessions.
- **E0b bracket:** equal is a hit, one grid step off is a near miss, two or more steps off is a miss. The log-likelihood of the six outcomes is reported under both F2 and A's criterion.
- **Trapped state:** backlog within ±15%; token ratio within ±0.03.
- **Rescue release time:** within ±15%.

**Reading the score.** gap/R and R are identities given the backlog and the E0a composition cost, so they are not counted as independent rows. An unbiased model lands about 50% of single quantities inside a 3-seed range.

## Refutation rules

- **H200:**
  - A measured window (turns-based μ_max / 0.19388) of 2.4 or more refutes T8 under uniform scaling. Predicted: 1.92, band 1.65-1.96.
  - A measured hit(32) < 0.5, i.e. a cliff at or inside the A100 300k cell's, refutes T3(c). Predicted: n_b 41.3, n_half 37.3.
  - A measured hit(48) ≥ 0.5 refutes T3(b)/(c). The pool part M/E_S = 27.8 does not depend on speed, and n_b ≤ 41.8 in every variant.
- **Llama:**
  - A measured n_half outside n_half(s) ± 3 refutes, with s the speed-table speed factor implied by the measured E0a.
  - No rise-peak-collapse refutes: μ at n = 48 within 10% of the measured peak.
- **150k:** a window ≥ 2.5, or hit(24) ≥ 0.5.
- **600k:** a window < 4.5, or hit(48) < 0.5.
- **B1:**
  - FAIL refutes, but PASS is shared with the round-7 simulator.
  - The theory-specific predictions are N_crit = 53.4 (deterministic) and a 50% committor near 50 at 1.65×. They are untested by B1's two burst sizes.
- **R1 and R4:**
  - NOT RESCUED refutes.
  - A release time outside ±15% of 3,830 s or 4,360 s (R1), or of 5,040 s (R4), is a miss.
  - RESCUED is also the registered simulator's prediction.
- **Relapse:**
  - P(relapse) is the F2 escape to n_b over [t_rel + 300 s, 8,700 s). It is identified with the registered relapse event, any 300 s window with follow-up hit < 0.2 after t_rel + 300 s.
  - Predicted: 0.002 and 0.025 (R1), about 0 (R4).

## Registration-conditional rule (mechanical; written now)

The blind JSONs place their E2 arms at the model's own registration consequence. The H200 and Llama cells will register their own rates and caps, so predictions at those rates are made by the following rule:

1. After a cell's registration is pushed, rerun `analysis.theory.predict` at the frozen tag.
2. Use a spec that differs from the frozen one only in `e2.multiples`, `e2.cap` and `tests`. For Llama it may also set `lambda_ref` to the measured E0a value, with a second variant using `fit_speed_to_e0a` = the measured E0a tokens.
3. Read only the registration's rate and cap fields.
4. Write `<cell>_conditional.json`, labelled conditional.

Every blind JSON also carries the F2 escape probability as a function of the absolute λ (sessions/s), `p_escape_by_lambda_sessions_per_s`. A change of λ_ref therefore needs no reinterpretation.
