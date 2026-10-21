# One-page outline: metastable failures in agentic LLM serving (DRAFT)

**Working title:** *Thrashing Returns: Metastable Failures in Prefix-Cached Agent Serving*

**Status:** simulation evidence only (rounds 1–4 on `pilot/prefix-meta`). Real-engine validation (SGLang v0.5.22, vLLM v0.32.0 on a Nova A100) is planned in `NOVA_PLAN_prefix_meta.md` on branch `harness/prefix-meta` and is not yet run. The paper exists only if Stage 0–2 on Nova show the trap on at least one real engine.

## Claim
Multi-turn, tool-calling agents served with prefix caching make the server **bistable**. Between the all-miss capacity λ_miss and the hit capacity μ\*, a finite burst moves the system permanently from a high-hit state to an all-miss state. Queue ordering (FCFS, LPM, aging) and queued-prefix protection (PEEK) do not change the congested-state throughput μ_∞ ≈ λ_miss. Only admission that bounds the session working set near N_lb = M / E_lb[L] restores global stability. Under LRU eviction that cap sits on a cliff.

## Contributions
1. **Phenomenon and measurement.**
   - Hysteresis and burst-triggered collapse in a calibrated continuous-batching simulator.
   - (Pending) the same on SGLang and vLLM with a 300k-token KV pool, Qwen2.5-7B, one A100.
2. **Theory (thrashing curve).**
   - The open-system fluid model is ṅ = λ − μ(n), where μ(n) is the closed-population thrashing curve.
   - Bistability window: (μ_∞, μ\*).
   - Critical burst: n₂ − n₁.
   - Recovery threshold: μ_∞.
   - Length-biased working set N_lb.
   - Under LRU with cyclic agent re-reference, μ(n) collapses just past N_lb.
   - Finite-size escape: the horizon-limited capacity λ_cap(k) approaches μ\* as size grows (Freidlin–Wentzell flavour; rare-event estimator via splitting is future work).
   - *Math-check pending:* `notes/MATHCHECK_thrashing_curve.md`.
3. **Unified evaluation of deployed mechanisms.**
   - LPM, PEEK, Continuum-style TTL pins, CONCUR AIMD caps, a static cap at N_lb, and eviction order (LRU, random, MRU-idle).
   - Each is assessed by the single quantity it changes: μ(n) and μ_∞.
4. **Diagnostic.**
   - A cheap closed-population saturation test, comparing μ(300) with open-loop capacity, flags metastability before deployment.
   - It could become a standard step in serving benchmarks such as AutoTuneBench-style protocols.

## Experiments
| ID | What | Status |
|---|---|---|
| S1 | Phase diagram: recovery vs λ/λ_miss by policy | done (sim, round 3) |
| S2 | Burst trap vs burst size; fluid critical burst vs empirical | round 4 running |
| S3 | μ(n) curves by eviction policy; cap × eviction robustness | round 4 running |
| S4 | Robustness across workload variants | done (7/8 variants, round 3) |
| S5 | Finite-size: λ_cap(k) vs μ\*(k) | round 4 running |
| N0–N2 | Real engine: smoke, λ_miss / λ_cap calibration, burst kill test | needs approval, ~42 GPU-h through gate 2 |
| N3 | Real-engine grid: FCFS / LPM / LPM-∞ / vLLM, refresh on/off | ~90 GPU-h |
| N4 (stretch) | Real agent traces (SWE-bench-style tool timings) instead of synthetic Exp(5 s) | — |

## Figures
1. Hit rate and queue over time around a burst, for FCFS vs capped (sim plus real).
2. Thrashing curves μ(n) for LRU, random and MRU, with λ_miss, μ\* and N_lb marked.
3. Phase diagram over (λ, burst size), comparing fluid and simulated boundaries.
4. Mechanism comparison: μ_∞ for each deployed mechanism.

## Risks, and what kills it
- **Mechanism does not transfer to real engines.** Partial radix prefixes, SGLang's waiting-prefix refresh, and vLLM's lazy eviction could all break it. Kill rule: no FCFS trap in at least 2/3 of runs at any λ in (1.2, 2)·λ_miss.
- **Scoop or overlap.** The Ao/Simchi-Levi group (2606.15555, active) and CONCUR. Our differentiators are prefix reuse, sessions with tool calls, the thrashing-curve unification, and the deployed-mechanism evaluation.
- **"It's just Denning."** Yes, and that is the point. The claim is that agent serving reintroduces thrashing in a form where common fixes (ordering, prefix protection) provably cannot help. The paper must be explicit about which parts are classical.

## Venues (deadlines unverified)
MLSys 2027 or its workshops, EuroMLSys 2027, a NeurIPS 2027 ML-for-Systems workshop, SIGMETRICS/Performance (if the theory gets rigorous), and an SC'27 workshop.
