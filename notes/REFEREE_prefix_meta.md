# Referee review: prefix-cache metastability (planned paper), 2026-10-21 ~05:00

Source: the global `referee` agent (model: inherit), run once tonight. It reviewed OUTLINE, THEORY_v3 plus the math-check corrections, MATHCHECK, RELATED_WORK, LOG rounds 1–3, the lit notes, MORNING, and NOVA_PLAN. Round 4 was not available to it. This is a condensed record. The headline numbers and recommendations are kept verbatim in substance.

## What the evidence supports
**Now (simulation only):**
- The good state is metastable for λ ∈ (λ_miss, ≈2.4 λ_miss) at k=1.
- Bursts of 50 or more fresh sessions trap FCFS, LPM-128, aging and PEEK-like policies within 25k s.
- Each policy's recovery threshold tracks its closed μ(300). This was found post hoc.
- Prop. A: FCFS-type ordering gives μ_∞ = λ_miss.
- LPM gives μ_∞ = 1.16, and the size of that gain depends on P(Z < R_∞).
- The cap identity is exact.
- **Verdict:** a workshop note applying Denning's thrashing curve to agent serving.

**If Nova succeeds:** an existence proof that a 200-session burst traps SGLang v0.5.22 FCFS at some λ ∈ (1.2, 2)·λ_miss. This holds for one model, one A100, synthetic sessions, and a 300k-token pool.

## Top rejection reasons, and what would neutralize each
1. **Novelty.** Reviewers will see it as Denning plus Bronson plus CONCUR, which already reports a hit-rate drop from 77.7% to 35.4% between 32 and 40 agents, and an agent cap that fixes it.
   - *Fix:* real-engine burst irreversibility against a no-burst control. Pre-registered predictions of each policy's recovery threshold from a measured μ(n). Props A and B stated as "which mechanisms can and cannot work". An explicit "what is classical" section.
2. **The simulation abstracts exactly the mechanism under test.** Whole-session hits, no partial radix hits, no refresh, no lazy eviction. The reservation diagnostic is in no results directory.
   - *Fix:* measure real-engine μ(n) and run paired bursts.
3. **Synthetic workload.** Exp(5 s) tools, while Continuum reports roughly 0.9–1.9 s mean tool time (unverified). With shorter tools, LPM may rescue the system. decode=400 kills the window. "Fancy Eviction" sees no LRU collapse on production traces.
   - *Fix:* tool-time sweep (1, 2 and 5 s, plus heavy tails), a regime map, and at least one real trace.
4. **The theory is thin.** Prop. A assumes the wait goes to infinity, and the cap identity is near-tautological. Every predictive piece failed (b_c, N_lb as the cap, exp(kV), P7). ε≈6 near the cliff.
   - *Fix:* frame this as an empirical systems paper with a phenomenological model, or derive μ(n) for a tractable case. Not SIGMETRICS as is.
5. **Baseline fidelity and statistics.** PEEK, Continuum and CONCUR were re-implemented from summaries. n=3 seeds. N\*=28 chosen post hoc. Verdicts flip with the horizon.
   - *Fix:* at least 10 seeds with Wilson CIs at the cliff, check baselines against released code, and register a fixed horizon.

## Overclaims flagged (fixed in OUTLINE, RELATED_WORK, MORNING, THEORY on 2026-10-21)
- "bistable" → "metastable".
- "permanently" → "within the simulated horizon".
- "ordering does not change μ_∞" → "true for FCFS-type ordering only; LPM gains an amount set by P(Z<R_∞)".
- "only working-set caps" → tuned pins and CONCUR also recover.
- "best cap N_lb" → n\*≈20–22.
- The critical-burst predictor is off by 1.3–2.5×.
- The Freidlin–Wentzell framing becomes a conjecture.
- The "flags metastability before deployment" diagnostic is untested.
- In THEORY_v3, the N_lb values were swapped. Corrected: the E_t pairing gives 28.4.
- In MORNING, "every number re-run bit-identically" overreached. It does not cover n\*/μ\*, the LPM-by-Z table, the birth–death escape fit, or the reservation diagnostic.

## Kill-test design changes (recommended)
1. **Paired arms with common random numbers.** For each (λ, seed), run three arms: burst, no-burst, and burst plus a client-side session cap at the measured n\*.
   - PASS requires all three: the burst arm traps, the no-burst arm stays good, and the capped arm recovers.
2. **Throughput-based trap criterion (pre-registered).**
   - Trapped means the completion rate stays within ±15% of λ_miss, with a positive backlog slope of about (λ−λ_miss).
   - A draining run shows a negative slope instead. This resolves D1 inside 4 h jobs.
3. **Measure the real curve and use real feedback.**
   - Measure real-engine closed μ(n) at n ∈ {16, 24, 32, 48, 96, 300} first (≈6–8 GPU-h), and pre-register the trap and recovery boundaries from it.
   - Use server token ids rather than synthetic feedback.
   - Run at least one λ on the native pool.

## Recommendation
**Conditional GO on the cheap stages:** Stage 0, calibration, and closed μ(n), about 20–25 GPU-h. **NO-GO on the framing as written.**

Estimates:
- P(the trap transfers to SGLang FCFS at a 300k-token pool): ≈60%.
- P(workshop-or-better paper by Dec 18): ≈40%.
- P(main track): under 15%.

**Decisive result:** at a λ inside the *measured* window, on SGLang FCFS, the burst arm traps while the paired no-burst and capped arms stay good, in at least 2/3 of seeds. That would raise the estimate to about 65–70%. If the no-burst arm also collapses, or nothing traps, drop this framing.
