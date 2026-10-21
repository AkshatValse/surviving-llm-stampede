# One-page outline: metastable failures in agentic LLM serving (DRAFT)

**Working title:** *Thrashing Returns: Metastable Failures in Prefix-Cached Agent Serving*

**Status:** simulation evidence only (`pilot/prefix-meta`; rounds 1–3 verified, round 4 pending). Recommended real-engine kill-test design changes (paired burst / no-burst / capped arms with CRN, a throughput-based trap criterion, real μ(n) measured first) are in `REFEREE_prefix_meta.md`. Real-engine validation (SGLang v0.5.22, vLLM v0.32.0 on a Nova A100) is planned in `NOVA_PLAN_prefix_meta.md` on branch `harness/prefix-meta` and is not yet run. The paper exists only if Stage 0–2 on Nova show the trap on at least one real engine.

## Claim (softened after referee and math-check, 2026-10-21; see `REFEREE_prefix_meta.md`)
In simulation, multi-turn tool-calling agents served with prefix caching give the server a **metastable** good state. For λ between the all-miss capacity λ_miss and roughly 2.4 λ_miss (k=1, horizon-limited), a finite burst of fresh sessions moves the system into a congested regime. That regime persists for the whole simulated horizon. Each policy's recovery threshold tracks its closed-population congested throughput μ_∞:
- **FCFS-type order (and PEEK-like protection, which keeps FCFS order):** μ_∞ = λ_miss under any eviction rule (Prop. A).
- **Resident-first order (LPM):** μ_∞ rises above λ_miss by an amount set by P(tool time < congested idle-KV lifetime). It is 1.16× for Exp(5 s) tools and 1.44× for a bimodal mix.
- **Session caps (static at n\*≈20–22, AIMD/CONCUR) and tuned TTL pins (τ=5–10 s with program priority):** raise μ_∞ to 2.2–3.3×.
- **Cap identity (exact):** a cap N is stable iff λ < μ(N). Under LRU, μ(n) drops steeply over roughly 0.8–1.3 N_lb, which makes cap choice fragile.

*Real-engine status:* untested.

## Contributions
1. **Phenomenon and measurement.**
   - Hysteresis and burst-triggered collapse in a calibrated continuous-batching simulator.
   - (Pending) the same on SGLang and vLLM with a 300k-token KV pool, Qwen2.5-7B, one A100.
2. **Theory (thrashing curve).**
   - **Model.** ṅ = λ − μ(n), with μ(n) the measured closed-population thrashing curve. This is a quasi-static approximation: it is reliable for fixed points and for recovery from deep congestion, and not for transients near the cliff (ε≈6).
   - **Metastable window:** (μ_∞, μ\*).
   - **Recovery threshold:** μ_∞.
   - **Prop. A (rigorous):** under FCFS-type ordering and any eviction rule, μ_∞ = λ_miss.
   - **Prop. B (empirical mechanism):** under LPM, μ_∞ = μ_cong(P(Z < R_∞)).
   - **Cap identity (exact):** a cap N is stable iff λ < μ(N).
   - **Length-biased working set:** N_lb ≈ 28.4 with E_t pairing. The best cap sits below N_lb because of occupancy fluctuations (n\*≈20–22).
   - **Critical burst:** n₂ − n₁ underestimates it by 1.3–2.5×, because burst sessions are fresh and have small footprints. A footprint-weighted correction is open.
   - **Escape (conjecture):** a 1-D birth–death chain on the measured μ(n) matches k=1 escape times within 2× (math-checker sanity run; re-run from a clean tree before citing). Rare-event estimation via splitting is future work.
   - **Math-check:** `notes/MATHCHECK_thrashing_curve.md` (done).
3. **Unified evaluation of deployed mechanisms.**
   - LPM, PEEK, Continuum-style TTL pins, CONCUR AIMD caps, a static cap at N_lb, and eviction order (LRU, random, MRU-idle).
   - Each is assessed by the single quantity it changes: μ(n) and μ_∞.
4. **Diagnostic.**
   - A cheap closed-population saturation test, comparing μ(300) with open-loop capacity, is *proposed* as a pre-deployment metastability check. Untested on any real engine.
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
- **"It's just Denning."** Yes, and that is the point. The claim is that agent serving reintroduces thrashing in a form where FCFS-type ordering and queued-prefix protection provably cannot raise μ_∞ (Prop. A), while LPM helps only through short tool calls. The paper must be explicit about which parts are classical.

## Venues (deadlines unverified)
MLSys 2027 or its workshops, EuroMLSys 2027, a NeurIPS 2027 ML-for-Systems workshop, SIGMETRICS/Performance (if the theory gets rigorous), and an SC'27 workshop.
