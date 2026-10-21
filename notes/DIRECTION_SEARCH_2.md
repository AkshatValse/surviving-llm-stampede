# Direction search round 2 (multi-agent workflow, 2026-10-20/21)

Provenance: workflow `novel-direction-search` (run wf_c2ee3776-7a9). 5 ideators (one per math lens) → 15 proposals → selector picked 6 → each got a deep lit-check (scout) + 2 adversarial refuters (novelty, substance) → synthesis. 25 agents. **Every lit agent hit its search budget, so novelty statements are provisional.** The [V-run] items below are toy simulations that agents ran in the scratchpad, not repo-committed code. The pilots that matter are being re-implemented in `pilot/prefix-meta` and `pilot/delay-eos`.

## All 15 proposals
- [0] measurement-stats: P1. Anytime-valid certificates certify the session, not the code: the pseudoreplication floor in agent-driven kernel tuning, plus a cost-optimal hierarchical e-process (a sharpened version of the seed, and a required fix to VAT) — For agent-generated GPU kernel candidates timed with KernelBench-style single-process harnesses (3 warmup + 100 trials in one process) on Nova A100/H200, the process-, job- or node-level variance component of the paired log-speedup is big enough (median $n\lambda \ge 0.65$ at $n=100$, where $\lambda=\sigma_u^2/\sigma^2$) that a nominal-5% within-session test or confidence sequence has a deployment type-I error of at least 10%, rising toward 1/2 as $n$ grows. A cluster-level e-process with predictable, cost-optimal blocks per process brings the error back to at most $\alpha$ at no more than 3x the cost of the invalid within-session test.
- [1] measurement-stats: P2. Speedups do not transport across identical GPUs: a low-rank roofline model of device-by-kernel interaction, and fleet-census probes as control variates — Across 16 or more same-SKU A100-80GB-PCIe GPUs on Nova, the GPU-to-GPU SD of paired log-speedup between kernels in different roofline regimes exceeds both 1% and the within-GPU between-session SD. At least 50% of that device-level variance is explained by a rank-2 or rank-3 model built from per-GPU probe throughputs (GEMM, STREAM, launch latency) weighted by each kernel's roofline elasticities. So ridge-straddling speedups smaller than about that SD change sign from device to device, and probe-adjusted estimation cuts the number of devices needed for a fleet-level certificate by about $1/(1-R^2)$.
- [2] measurement-stats: P3. Do LLM agents shop for sessions? Outcome-dependent re-measurement in agent-driven performance optimization, and tool-owned stopping rules — In a controlled tuning environment with known ground truth and hierarchical noise calibrated to real data, Claude-based optimization agents re-benchmark at least twice as often after a result below their pre-stated expectation as after one above it. Their final reported speedups exceed the true speedups by more than the fixed-protocol winner's curse predicts, by an amount that a selection model fitted to their logged stopping decisions matches within its CI. Replacing the raw benchmark tool with a certify() tool that owns the stopping rule removes this excess at no more than a 10% loss in true speedup achieved.
- [3] queueing-agents: Prefix caching does not enlarge the stability region: metastable KV thrashing and hysteresis in open agentic LLM serving — Consider an open agent-serving system with finite KV memory M, request-level admission, and cache-oblivious ordering (FCFS, as in vLLM's default). For every eviction rule, Belady included, the arrival rates at which the system is positive recurrent are exactly the all-miss region λ·E[W_miss] < 1. Above that rate and below the memory-time capacity, the system is metastable. It stays in a high-hit, low-utilization state for a time that grows rapidly as λ falls, and it shows hysteresis: once congested, it does not recover until λ drops below the all-miss capacity. A non-work-conserving session-level cap restores stability up to the memory-time capacity, which can be several times larger.
- [4] queueing-agents: Agent swarms are pulse-coupled oscillators: scheduler-induced self-synchronization of closed-loop agents on shared continuous-batching servers — Picture N closed-loop agents (agentic-RL rollouts, batch agent inference, or multi-agent simulations) sharing one continuous-batching LLM server. They act as pulse-coupled oscillators, and the scheduler sets the sign of their coupling. If an arriving prefill stalls in-flight decodes (prefill priority, or a chunk budget whose compute time exceeds the per-iteration decode overhead, C·c_prefill > τ_iter), the coupling is attractive. The swarm then phase-locks into convoys whenever tool-time jitter is below a critical coefficient of variation. In that state the GPU idles 10–45% and per-call latency rises 1.4–2× at the same N. Chunk budgets below C* ≈ τ_iter × prefill rate make the coupling repulsive, and the agents spread into an evenly spaced (splay) state. Testable: the Kuramoto order parameter r measured on vLLM or SGLang crosses from near the random-phase baseline to near 1 at a predictable chunk budget and jitter level.
- [5] queueing-agents: Locally sensible, globally unstable: virtual-station instability of prefill/decode-disaggregated serving for multi-turn agents — Serve multi-turn agents (K ≥ 3 turns) on prefill/decode-disaggregated pools with turn-indexed priorities that order turns oppositely in the two pools. Example: the prefill pool favors later turns, as with program-age or finish-the-program priority; the decode pool favors earlier turns, as with smallest-KV-first admission. That system is unstable whenever λ(p_j + d_i) > 1 for some i ≤ j−2, where p_j and d_i are the mean prefill and decode work of turn j and turn i. This can happen with both pools at about 65% utilization. Consistent orders (FBFS or LBFS on turn index, or one program-level priority shared by both pools) and FCFS are stable. Agents with K ≤ 2 turns are immune.
- [6] variance-reduction-training: The price of unbiased straggler-cutting in RL rollouts: a Godambe–Joshi phase transition, and timeouts that leak cluster capacity into agent policies — In synchronous agentic GRPO with a shared, congestible slow tool, scoring timeouts as failures makes the learned tool-use rate depend on the training cluster's tool-server capacity (a shift of 5 points or more between two capacities with the task held fixed). Randomized straggler killing with inverse-survival weights (Rhee–Glynn/McLeish roulette) removes that dependence while cutting step wall-clock by at least 20% at under 15% gradient-variance cost. For token-length tails in reasoning RL, any design-unbiased tail-cutter must inflate gradient variance by at least $1+(N\varepsilon^2/\mu-\varepsilon)\rho$, so it cannot beat full synchronous rollouts in MSE×time.
- [7] variance-reduction-training: Honeymoon goodput: short-run LLM serving benchmarks overstate sustainable capacity, and the bias differs by configuration — For continuous-batching LLM servers at loads near saturation, goodput measured with standard fixed-N open-loop runs (N=1000, starting empty, with drain) overstates steady-state goodput by ≥10%. The overstatement differs across configurations by ≥5 points, favoring configs with more buffering (larger max batch or KV). So short-run rankings and short-run-driven autotuning (including agent-driven tuning) disagree with steady-state rankings among configs within ~5% of each other.
- [8] variance-reduction-training: Efficiency claims are first-passage times: the null distribution of 'X× faster to target/peak' in RL post-training, and a stochastic-root-finding estimator of cost-to-quality — When two RLVR training methods have identical dynamics and are evaluated on AIME-sized benchmarks (30 items, avg@16) every 20 steps, the standard 'steps to reach the baseline's peak' metric produces a ≥1.5× speedup claim in ≥10% of comparisons. Raw first-crossing time-to-target is biased early by ≥15%. A monotone (isotonic) fit plus a probabilistic-bisection evaluation design over saved checkpoints removes most of the bias and gives valid CIs on the cost-to-quality curve C(q) at ≤1/3 of the dense-evaluation GPU cost.
- [9] numerics: Delay erases momentum's stability margin: overlapped/asynchronous training self-stabilizes at sharpness c*_tau/eta (a mechanism for why 1-step delay breaks AdamW but not Muon) — With a one-step gradient delay (async pipeline / PipeDream-2BW, ZeRO-Offload delayed parameter update, optimizer/communication overlap), the largest stable (preconditioned) sharpness of every EMA-momentum method (SGD-m, Adam with slowly varying v) falls from 2(1+beta1)/((1-beta1)eta) to exactly 1/eta for every beta1 (a 38x collapse at Adam's default beta1=0.9). Edge-of-stability self-stabilization therefore makes delayed training settle at eta*S ~ 1 instead of diverging. Update-extrapolation 'error feedback' raises the cap to about (1-beta1)^(-1/2)/eta, and amplitude-bounded optimizers (Muon, sign-like) have no such cap.
- [10] numerics: The 2^p ring law: low-precision ring reductions silently shrink the high-SNR part of the gradient beyond ~2^p x max(1, CV) ranks — Consider a ring reduce-scatter, or any sequential accumulation chain, that rounds to a p-bit-significand format after every hop. The expected reduced value of a coordinate whose cross-rank coefficient of variation is CV stays unbiased up to a chain length P* ~ c x 2^p x max(1, CV) with c ~ 2-4, and beyond that collapses toward about P*/P of its true value. So BF16 (p=8) reduce-scatter underestimates coherent (high-SNR) gradient coordinates by >10% beyond about 500 ranks, and FP8 rings do so beyond about 16-64 ranks. Tree or 2-level reductions with each level below P*, or per-hop stochastic rounding, remove the bias at BF16 byte cost.
- [11] numerics: Chunked delta-rule attention is uniformly well-conditioned: an Ostrowski-Reich bound for the UT transform (DeltaNet, Gated DeltaNet, KDA) and what it licenses for low-precision kernels — Take unit-norm keys, beta_t in (0,2), and any scalar or channel-wise decay gates. The chunkwise UT-transform matrix A = I + strictLower(diag(beta)(Gamma o K K^T)) then satisfies ||D^{-1/2} A^{-1} D^{1/2}||_2 <= 2/(2 - beta_max) for every chunk size C. Its conditioning therefore grows only with key coherence (at most like log C x ||D^{1/2}(Gamma o KK^T) D^{1/2}||_2), not exponentially in C. The only numerically dangerous regime is beta_max -> 2 (negative-eigenvalue variants), where errors scale like 1/(2 - beta_max).
- [12] wildcard-hpc: More repetitions, worse coverage: long-range-dependent interference noise on shared GPU clusters and the silent failure of iid and anytime-valid benchmark inference — On Nova's shared GPU nodes, timing noise for ML kernels and training steps has a long-range-dependent component (Hurst H >= 0.65 across at least 3 decades of time scale, seconds to hours, for at least 2 of 5 workloads on at least 2 node types). As a result, any design that compares measurements taken at different times (cached baseline, cross-job leaderboards, sequential agent loops) has nominal-95% iid CIs that cover under 70% at n=1000 repetitions, and coverage falls as n grows. Time-uniform confidence sequences miscover with probability tending to 1. Interleaved or randomized paired designs keep nominal coverage.
- [13] wildcard-hpc: Cold benchmarks, hot deployments: power-state mismatch makes agentic kernel tuning pick the wrong winner on shared, clock-unlockable GPUs — On Nova's air-cooled 300 W A100-80GB-PCIe GPUs, users cannot lock clocks. There, the short-burst timing protocol used by Triton autotune and KernelBench-style agent loops (about 100 ms bursts) selects a candidate that runs >= 3% slower than the sustained-optimal candidate under >= 60 s steady-state load, in at least one of three compute-bound kernel families (GEMM, attention, stencil/conv). A power-aware score computed from the same short bursts, s_k = t_k * max(1, (P_k/P_avail)^{1/gamma}), recovers the sustained ranking with Kendall tau >= 0.9.
- [14] wildcard-hpc: Working-set collapse in agent serving: closed-loop tool calls turn LRU prefix caches into a knife-edge goodput cliff whose location is set by tool-latency variance — On a prefix-caching LLM server (vLLM, default LRU eviction, one A100-80GB) serving K closed-loop agents with contexts of 16k tokens or more, aggregate goodput (completed agent turns/s) is non-monotone in K. It peaks at K* close to the number of contexts that fit in free KV memory, then falls by >= 40% toward the no-cache bound P/(s+a). The cliff's location and sharpness are predicted to within 25% by a renewal-LRU fixed point that depends on the tool-latency distribution F_Z. Low-variance tool latencies give a near-step cliff; higher-variance ones at the same mean push K* up. Beyond K*, a working-set admission cap at K-hat* Pareto-dominates plain LRU in both goodput and mean agent cycle time.

## Dropped by selector

- **More repetitions, worse coverage: long-range-dependent interference noise on shared GPU clusters and the silent failure of iid and anytime-valid benchmark inference**: Merged into [0]: same data and same consequence (more repetitions give worse coverage and CS gates fail); LRD vs per-session random effects is a model choice that [0]'s E1 must resolve via between-job correlation vs time gap.
- **P2. Speedups do not transport across identical GPUs: a low-rank roofline model of device-by-kernel interaction, and fleet-census probes as control variates**: Merged into [0] as the device level of the nested variance model; standalone, the same-SKU ratio SD may be under 1% and the claim is unpiloted on GPUs, so test it free inside [0]'s E1 (key devices by UUID, add probes).
- **P3. Do LLM agents shop for sessions? Outcome-dependent re-measurement in agent-driven performance optimization, and tool-owned stopping rules**: Merged into [0] as its agent arm (E3, certify() tool, SHOP formula): it presupposes [0]'s sigma_u is non-negligible, LLM p-hacking under freedom is partly known (Thomas et al., Asher et al.), and a prompt-dependent null is likely.
- **Cold benchmarks, hot deployments: power-state mismatch makes agentic kernel tuning pick the wrong winner on shared, clock-unlockable GPUs**: Nothing piloted, and the effect is plausibly under 1% because 300 W PCIe A100s may be power-bound even in short bursts; fold NVML power/clock/throttle logging into [0]'s E1 as a mechanism ablation instead.
- **Working-set collapse in agent serving: closed-loop tool calls turn LRU prefix caches into a knife-edge goodput cliff whose location is set by tool-latency variance**: Merged into [3] as the closed-loop counterpart; its own pilot found no hysteresis, and the K* cliff plus admission cap alone is classical Denning working-set / multiprogramming-level control.
- **Honeymoon goodput: short-run LLM serving benchmarks overstate sustainable capacity, and the bias differs by configuration**: Merged into [3]: the 'honeymoon' is the metastable high-hit branch seen from an empty start; standalone it is a 'run longer, delete warm-up' measurement note with known remedies (Welch/MSER) and only moderate ranking flips (tau 0.79).
- **Locally sensible, globally unstable: virtual-station instability of prefill/decode-disaggregated serving for multi-turn agents**: The mechanism is textbook Lu-Kumar/Rybko-Stolyar by its own admission, Dai et al. 2504.07347 already gives an agent Rybko-Stolyar example, and no deployed inconsistent P/D priority pair has been shown.
- **Efficiency claims are first-passage times: the null distribution of 'X× faster to target/peak' in RL post-training, and a stochastic-root-finding estimator of cost-to-quality**: Self-rated novelty about 2.5/5 (FID Lottery, statistical precipice); it needs 8+ GRPO seed replicates per config on Nova, and the PBA cost saving is untested; better as a section of the [0]/VAT paper.
- **Chunked delta-rule attention is uniformly well-conditioned: an Ostrowski-Reich bound for the UT transform (DeltaNet, Gated DeltaNet, KDA) and what it licenses for low-precision kernels**: A clean but small, workshop-scale theorem close to Sobczyk et al. 2605.21325, with modest GPU efficiency payoff; it can be finished as a side note tonight without a deep novelty check.

## Synthesis (verbatim from the synthesis agent)

# Chief-of-staff ranking: six deep-checked candidates (2026-10-20)

**Evidence labels used below.**
- **[V-page]** means a scout or refuter opened that page. The depth they read is noted.
- **[V-run]** means someone ran code tonight: the proposer, a refuter, or me.
- **[U]** means unverified: recalled from memory, relayed by a summarizer, or inferred.

Every scout and refuter ran out of web-search budget. Any "nobody has done X" statement below means only that nothing turned up in the pages that were opened. The listed searches need to be re-run before any novelty sentence goes into a paper.

| Rank | Candidate | Verdict | One line |
|---|---|---|---|
| 1 | C1 Prefix-cache metastability, **reframed** | **PURSUE** | The queue's ordering sets the stability region, not admission control. SGLang's shipped LPM switches itself off once more than 128 requests wait, which brings back the FCFS trap. |
| 2 | C0 Delay vs. edge of stability, **reframed** | SALVAGE-VARIANT | Measure sharpness and Adam's v under delay. Two new closed forms back the test. The decisive run needs GPUs. |
| 3 | C4 Agent swarms as oscillators, reframed | SALVAGE-VARIANT (park) | This is Floyd–Jacobson on a batching server. It only applies when tool-time jitter is low. It shares infrastructure with C1. |
| 4 | C3 Pseudoreplication floor / VAT fix | SALVAGE-VARIANT (low; fix VAT anyway) | The theory is prior art, and Lindon posted a related paper yesterday. What is left is a GPU measurement note. |
| 5 | C5 Godambe–Joshi straggler cutting | KILL | The headline theorem is false: a shared coin beats it. The capacity leak is second-order in accuracy, and masking fixes it. |
| 6 | C2 The 2^p ring law | KILL | Adam is blind to the bias, and the default setups already reduce in fp32. |

---

## 1. C1, reframed: ordering decides stability, and production LPM disables itself under load. PURSUE

**Sharpest surviving claim.** This is a falsifiable claim about real engines. In open, multi-turn agent serving with prefix caching:
- **Cache-oblivious FCFS** (SGLang's default, and vLLM's [U]) is stable only below the all-miss capacity. Above it the system is metastable and shows hysteresis.
- **A work-conserving hit-first order (pure LPM)** stays stable up to roughly the hit/memory-time capacity with no admission cap. So "admission control is needed" is false here.
- **SGLang's LPM falls back to FCFS** whenever more than 128 requests are waiting (`WAITING_QUEUE_PREFIX_MATCH_MAX = 128`). It therefore inherits the FCFS trap. Any burst that pushes the queue past 128 locks the server onto the all-miss branch until load drops below all-miss capacity.

This is the "a method's guarantee silently fails under a condition that holds in practice" pattern, and the condition is set by a constant in the code. The escape time from the good state is the hitting time of a fixed queue threshold. That is a rare-event quantity, which fits Akshat's splitting and importance-sampling background.

**Verified**
- [V-run] Proposer's discrete-event sim (one FCFS GPU, additive work, LRU):
  - λ_miss = 0.0545 sessions/s.
  - At λ = 0.08, 20/20 runs from an empty start stayed good for 50k s. A start with 300 sessions never recovered.
  - The recovery threshold from a congested start (0.045–0.055) matches the predicted all-miss rate of 0.0545.
- [V-run] Refuter 2's independent sim:
  - Pure LPM recovered from a cold start with 300 sessions at λ = 0.24 (ρ_hit = 0.72) in 3/3 seeds. FCFS is stuck for every λ > 0.051.
  - **LPM with the 128 fallback failed to recover even at λ = 0.08** (queues 1060–1102, hit rate 0).
  - Escape time scales with system size: 2.9 ks rising to 28 ks when M, λ and speed are doubled.
- [V-page] SGLang main-branch source (refuter 2): the default `schedule_policy` is `"fcfs"`, and the 128 constant is hard-coded.

**Unverified or at risk**
- [U] Both sims use additive single-server work. Neither models continuous batching, memory-gated admission or batch amortisation. This is the main open risk.
- [U] The source was read on `main`. The version that would run on Nova has not been pinned.
- [U] That vLLM V1 defaults to FCFS. Nobody opened vLLM's source.
- [U] Whether CPU/SSD KV offload (HiCache, LMCache) is on by default. Refuter 2's back-of-envelope says offload makes a miss cost about 35–45 ms instead of about 0.7 s, which would erase the window for an 8B model with roughly 10k-token agents.
- [U, hypothesis] CONCUR's "middle-phase thrashing" (SGLang, batches of 16–256 agents) might be this fallback, since batches above 128 would disable LPM. Check which schedule policy CONCUR used and whether the thrashing appears only above 128.

**Closest prior work**
- Bronson et al., HotOS'21 [V-page: PDF, Sec. 2.2 and Fig. 2 read]. States the cold-cache vulnerable state and the two goodput branches for look-aside caches, so the FCFS trap is folklore. https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf
- Ao, Dong, Luo, Simchi-Levi [V-page: pp. 1–5 and 18–25]. An empirical open-arrival threshold in Sec. 6.1. No sessions, no prefix hits, no ramp-down. v3 is dated today, so the group is active and scoop risk is real. https://arxiv.org/abs/2606.15555
- Ao, Luo, Simchi-Levi, Wang [V-page: partial HTML]. The eviction-only stability region. WAIT is a non-work-conserving admission rule. https://arxiv.org/abs/2504.11320
- Nie, Si, Zhou [V-page: HTML]. Memory-time capacity for one-shot requests. https://arxiv.org/abs/2605.04595
- Dai et al. [V-page: partial]. Work-conserving policies are throughput-optimal when there is no cache-dependent service. https://arxiv.org/abs/2504.07347
- CONCUR [V-page: full text]. Empirical thrashing plus AIMD admission. No theory. https://proceedings.mlr.press/v306/chen26fs.html
- XPerf [V-page: HTML via summarizer]. Hit rate falls from 91% to under 4% on an up-sweep only. https://arxiv.org/abs/2608.20370
- DLPM [V-page: abstract]. Prefix locality plus fairness, no stability theory. https://arxiv.org/abs/2501.14312
- Gibbens–Hunt–Kelly [V-page: pp. 1–6] and Denning [V-page: pp. 1–6]. The mechanism and the cap-style fix. https://www.statslab.cam.ac.uk/~grg1000//books/hammfest/8-rjg.pdf and https://cs.uwaterloo.ca/~brecht/courses/epfl/Possible-Readings/vm-and-gc/thrashing-denning-afips-1968.pdf
- Alvaro et al. [V-page: HTML]. CTMC models of metastability and escape times for generic software. https://arxiv.org/abs/2510.03551
- SGLang source [V-page]: https://raw.githubusercontent.com/sgl-project/sglang/main/python/sglang/srt/managers/schedule_policy.py

**Key risks**
1. Continuous batching may shrink the window λ_hit/λ_miss. Refuter 2's estimate is 3–6× for an 8B model on an A100 [U].
2. Reviewers may call the fallback a configuration bug. The paper needs the general statement: any cache-aware order that drops to cache-oblivious above a queue threshold inherits the all-miss region. It also needs a fairness-bounded hit-first policy that keeps the larger region, because pure hit-first starves cold sessions.
3. KV offload removes the window in the short-context, small-model regime. Scope the claim to that.
4. Scoop risk from the Simchi-Levi group.

**Tonight's pilot.** Spec in the final section (P-A).

---

## 2. C0, reframed: is AdamW's one-step-delay penalty a stability cap? SALVAGE-VARIANT

**Sharpest surviving claim.** Two pieces of math are already settled. At τ = 1, every EMA-momentum method's stable preconditioned sharpness is exactly 1/η, which is a two-line Jury-test corollary of Giladi's Eq. 26. EF, or linear weight prediction, raises the cap to c\* with c\*(c\*+1) = 1/(1−β₁), i.e. c\* = (−1+√(1+4/(1−β₁)))/2. That is a new closed form for a boundary Kosson already plotted.

The open, falsifiable claim is about LM scale:
- Sync AdamW's preconditioned sharpness sits only modestly above the delayed cap, roughly η·S_P ≈ 2–4.5. That range is my inference from Zmushko's 90% EF recovery: an EF cap of 2.7 can recover most of the gap only if sync sits near 3.
- Delayed AdamW pins at η·S_P ≈ 1, and EF at about 2.7.
- β₁'s benefit under delay comes from slower instability growth, not a higher threshold. The e-fold time is about 12.7 steps at β₁ = 0.9 and about 119 at β₁ = 0.99 (c = 2.7). That would explain Zmushko's Fig. 4, which threshold theory alone cannot.

Drop the "38× collapse" headline and the "Muon has no boundary" claim.

**Verified**
- [V-run] Threshold table, checked independently by refuter 2:
  - Sync caps: 2, 6, 38, 78, 398.
  - τ = 1 cap: 1.0000 for every b.
  - τ = 2 caps: 0.618 to 0.501.
  - EF closed form matches 0.618, 1.000, 2.7016, 4.000, 9.5125. I re-did the algebra for b = 0.5, 0.9, 0.99.
- [V-run] Single-seed digits MLP, full batch: η·S = 2.00 for sync GD, 1.01–1.03 for delayed GD, 1.03–1.07 for delayed EMA (b = 0.9). EF reached 1.93 and was still rising. **Sync b = 0.9 never reached 38.**
- [V-page] Zmushko Table 2 at 360M: AdamW 2.612 sync, 2.890 delayed, 2.640 with EF. Refuter 2 notes the columns were partly misaligned, so EF could be 2.64–2.66. Fig. 4 shows higher β₁ shrinks the delay penalty, but AdamW is not in Fig. 4.
- [V-run] Muon's polar factor has a nonzero linearisation on the antisymmetric part (refuter 2: 0.5677 predicted, 0.5677 measured). So "no linear boundary" is false.
- Adam's per-coordinate step is bounded by about 1.165·η at (0.9, 0.95). This is a Cauchy–Schwarz derivation by refuter 2, not a run.

**Unverified**
- [U] Whether minibatch LM AdamW is limited by edge-of-stability at all. Cai et al. and Andreyev et al. suggest often not.
- [U] Whether v inflation, rather than sharpness collapse, absorbs the delay. With β₂ = 0.95 the averaging window is about 20 steps, which is about one oscillation period.
- [U] PipeMare App. B.3 and Kosson App. I were never read as rendered pages.

**Closest prior work**
- Giladi et al., ICLR 2020 [V-page: PDF pp. 3–5 and 14–19 by the scout, pp. 1–20 by refuter 1]. Same polynomial (Eq. 26), Fig. 10 shows the momentum penalty, and its future-work section poses the dynamic (in-training) question. https://arxiv.org/abs/1909.12340
- Kosson et al., MLSys 2021 [V-page: refuter 1 read pp. 1–10]. Delayed-momentum stability maps (Fig. 6) and the linear-weight-prediction cubic (Eq. 22). https://arxiv.org/abs/2003.11666
- Zmushko et al. 2026 [V-page: pp. 3–9]. The phenomenon, with no mechanism. https://arxiv.org/abs/2606.30634
- PipeMare [V-page: Lemma 1]. https://arxiv.org/abs/1910.05124
- Jung et al. [V-page: HTML via summarizer]. The competing basis-misalignment mechanism. https://arxiv.org/abs/2602.03515
- Andreyev et al. 2026 [V-page: abstract]. Momentum lowers the batch-sharpness plateau at small batch. https://arxiv.org/abs/2604.14108
- Cai et al., ICLR 2026 [V-page: abstract]. Edge of stability in LLM pretraining is not universal. https://iclr.cc/virtual/2026/10016041
- Muon Sublates EoS [V-page: partial HTML]. https://arxiv.org/abs/2609.34915
- Cohen et al. 2022 [V-page: abstract]. The 38/η threshold for Adam. https://arxiv.org/abs/2207.14484

**Key risks**
- Kill criterion (c) is likely to fire: minibatch AdamW may not sit at any stability cap.
- The edge-of-stability coupling is the field's default expectation, so the value of this work is almost entirely in the measurement.
- The decisive experiment is a 135M sharpness and v probe at under 100 GPU-h. A CPU run cannot settle it.

**Tonight's pilot.** Spec in the final section (P-B).

---

## 3. C4, reframed: Floyd–Jacobson locking on batching servers. SALVAGE-VARIANT (park)

**Sharpest surviving claim** (refuter 2's salvage).
- Closed-loop agent swarms phase-lock on any engine where an arriving prefill stalls in-flight decodes. That includes chunked prefill at default budgets, because chunking spreads the roughly P-sized stall but does not remove it.
- Locking needs core tool-time dispersion below √(αNPT), with α ≈ 0.1 in simulation. N is the number of agents, P the stall length per prefill, T the cycle time.
- Near the closed-network knee it costs 10–35% throughput.
- The only scheduler-side desynchroniser is a nearly saturated FIFO prefill channel. So the closed-loop-optimal token budget sits at the prefill-saturation edge, which is the opposite of open-loop tuning.

The proposer's crossover C\* ≈ τ_iter × prefill rate is **wrong**. Both refuters derived a different crossover, and the simulated transition tracks prefill-queue backlog.

**Verified [V-run, simulation with assumed A100/8B constants]**
- r₁ = 1.0 with 36% GPU idle at N = 32 with 2k-token prompts.
- σ_c²/(NPT) = 0.084, 0.090 and 0.13 (only three bracketed points).
- Mixed scheduling at the default chunk couples as strongly as prefill-priority (r₁ 0.87 vs 0.87).
- A tool-time CV of 0.5 or more kills the locking. A tight core with outliers still locks.

**Unverified**
- [U] Real-engine behaviour.
- [U] Real tool-time core dispersion. The TraceLab statistics (mean 18.4 s, median 0.3 s) are relayed by a fetch tool, and the abstract does not confirm per-call timestamps.

**Closest prior work**
- Floyd & Jacobson 1994 [V-page: pp. 1–20]. The mechanism, cluster absorption, the Tr/Tc thresholds, and randomisation as the cure. https://ee.lbl.gov/papers/sync_94.pdf
- Afzal, Hager, Wellein [V-page: partial HTML]. Contention sets the sign of coupling; uses the Kuramoto R(t). https://arxiv.org/html/2506.02792v1
- Ao et al. [V-page]. Completion synchronisation in continuous batching, a different mechanism. https://arxiv.org/abs/2606.15555
- Human-Less LLM Serving [V-page: abstract]. https://arxiv.org/abs/2606.20577
- TraceLab [V-page: abstract]. https://arxiv.org/abs/2606.30560
- Sarathi-Serve [V-page: abstract]. https://arxiv.org/abs/2403.02310

**Key risk.** Realism. Every real agentic workload may sit outside the locking region. Novelty is limited to "an instance of Floyd–Jacobson".

**Tonight's pilot, if it is run.** Add at least 6 more bracketed points: N ∈ {8, 16, 64}, P ∈ {0.06, 0.23, 0.9} s, T ∈ {10, 30} s. Then sweep C at prompt sizes p_new ∈ {512, 2048, 8192}.
- Go if α stays within ±50%, and the throughput-optimal C moves with prefill demand.

It reuses C1's session-generator infrastructure, so it is a cheap fallback if C1 dies. It is not tonight's priority.

---

## 4. C3: pseudoreplication floor, "certifies the session, not the code". SALVAGE-VARIANT (low)

**Sharpest surviving claim** (refuter 2's salvage).
- For agent-generated GPU kernels, the paired candidate-by-session variance σ_u matters for decisions only for autotuned and launch-bound kernels.
- If in-process re-randomisation (fresh autotune, random allocation offsets, new streams) reproduces most of the fresh-process and fresh-job σ_u², then an iid confidence sequence over re-randomised blocks is valid for the deployment estimand at about 1× cost.
- Fresh-process sessions cost (√(c₀/c₁)·r + 1)², which exceeds 3× whenever the type-I floor exceeds 10% and c₀/c₁ > 83. So the original claim's two halves contradict each other on GPU.

Skeptical note on refuter 2's proposed metric: "fast_1 ≈ 50% for reference-equivalent kernels" is close to tautological. A kernel equivalent to the reference has a true speedup of 1, so any symmetric noise gives about 50%. The informative number is a *systematic* offset under the stored-baseline protocol.

**Verified**
- [V-run] Refuter 2 reproduced the CPU numbers: 85% of candidates have F-test p < 0.01; median σ_u = 0.079 and σ_w = 0.099. The confounds are also verified: "process" coincides with a time window on a shared machine, and the baseline's log-SD in process 5 is 0.22.
- [V-run, I read the repo summary] `results/vat_alignment/20261020-234301/summary.txt`: the cross-process correlation of the 36 alignment-cell means is 0.764 and 0.666 for col-order tiles 32 and 64, versus 0.060 and 0.122 for row-order. Alignment therefore explains the large CPU swings, which are the Mytkowicz/Stabilizer layout pathology. I did not check the units or the script.
- [V-page] KernelBench source (refuter 2): the canonical speedup uses stored baseline times, so it is unpaired, and the code default is `num_perf_trials` = 10. The paper's App. B says 100 trials (scout). The paper and the code disagree.
- [V-page] CUDABeaver App. G: outer-run CV median 0.8%, p90 9.3%.

**Unverified**
- [U] All GPU magnitudes.
- [U] Whether CUDABeaver's CV is of time or of speedup.

**Closest prior work**
- Kalibera & Jones 2013 [V-page: full text]. Eq. 3 is the m\* allocation rule, and Sec. 8 makes the estimand split. https://kar.kent.ac.uk/33611/
- Lindon 2026, submitted 19 Oct [V-page: about 200k characters]. Cluster-level e-processes. https://arxiv.org/abs/2610.25613
- Hait 2026 [V-page]. Predictable cost-aware allocation; explicitly leaves clustered e-processes open. https://arxiv.org/abs/2609.37873
- CUDABeaver [V-page: App. G]. https://arxiv.org/abs/2605.08455
- KernelBench source [V-page]. https://github.com/ScalingIntelligence/KernelBench
- KernelBench-Verified [V-page: partial]. https://arxiv.org/abs/2607.16241
- Standard Kernel blog [V-page]. https://standardkernel.com/blog/in-pursuit-of-high-fidelity-gpu-kernel-benchmarking/
- Miller 2024 [V-page: Sec. 2.2]. https://arxiv.org/abs/2411.00640

**Key risks.** The theorems are prior art or corollaries. Kill criterion as written cannot fire. The CPU evidence is pathological and confounded, and the GPU contribution is workshop tier.

**Action regardless of ranking.** Change the VAT design so that blocks are re-randomised (alignment) or session means are the unit of inference. The current within-process confidence-sequence racing targets the wrong estimand for the col-order candidates.

**Tonight's pilot, if it is run.** Run it only when no other timing job is active. Compare in-process per-block re-allocation at random 64 B offsets (0–4096 B) against 12 short interleaved fresh processes, and report the fraction of σ_u² captured. This is CPU-only, and the result does not transfer to GPU.

---

## 5. C5: Godambe–Joshi straggler cutting. KILL

**Sharpest surviving claim.**
- For design-unbiased tail cutters with fixed marginals, the comonotone coupling minimises expected step time pointwise, by the Fréchet bound. In practice that is one shared coin, i.e. a randomised step deadline with 1/p reweighting.
- The same coupling maximises pairwise inclusion, π_ij = min(π_i, π_j).
- Independent per-rollout coins therefore lose a factor of about εN.

This is classical single-truncation Rhee–Glynn, and it must beat APRIL-style deferral, which adds no variance.

**Verified [V-run, refuter 2 toy]**
- Shared coin at p = 0.5: variance ×1.16, time ×0.64, MSE×time 0.74. Independent coins: 1.005 or worse. So "cannot beat full sync" is false.
- Under independent coins, the Godambe–Joshi prediction matches (×15.0 measured vs ×15.4 predicted).
- Capacity leak at 5% timeouts or fewer: usage shifts 1–5 points and accuracy only 0.07–0.12 points. Masking removes it.
- [V-run, refuter 2] The stated bound is also invalid with heterogeneous v_i. It needs (mean √v)².

**Unverified.** [U] The full text of LCSB (kill criterion d).

**Closest prior work**
- PAIR [V-page: pp. 1–14]. Design-unbiased prefix continuation with 1/π_ij weights. https://arxiv.org/abs/2608.11368
- LCSB [V-page: abstract only]. https://neurips.cc/virtual/2026/loc/sydney/poster/148493
- Rhee–Glynn [V-page: abstract]. https://ideas.repec.org/a/inm/oropre/v63y2015i5p1026-1043.html
- APRIL [V-page: abstract]. https://arxiv.org/abs/2509.18521
- Performative RL [V-page: abstract]. https://proceedings.mlr.press/v202/mandal23a.html

**Key risk.** Async and deferral methods dominate, and scoop density is high (PAIR, DPPO, NAT).

**Discriminating pilot, not recommended.** A toy comparing the comonotone design with APRIL-style deferral under a staleness-penalty model. Kill entirely if deferral dominates at every realistic staleness level.

---

## 6. C2: the 2^p ring law. KILL

**Sharpest surviving claim.**
- Low-precision ring reductions have two onsets: coherent stagnation at P ~ 2^p·CV, and a CV-independent noise onset at P ~ 2^{2p}.
- Adam is blind to the first: with per-coordinate scale invariance, its step changes by less than 1–2% up to 10⁴ ranks.
- So bf16 data-parallel reduce-scatter is "safe for AdamW". Only Muon, Shampoo or SGD could notice.

That is a harmless-law result with narrow exposure: Megatron defaults to fp32 reduction [V-page: arguments.py].

**Verified [V-run]**
- Refuter 2's emulator reproduces the bias (bf16 at CV = 0.1: −58% at P = 1024; tree reduction 0.00%).
- Adam step ratio is 1.000 at P = 1024–4096.
- e4m3 is about −15% at P = 256 even at CV = 30–100, so the proposer's FP8 math core is wrong.

**Closest prior work**
- Mary–Riccietti slides [V-page]. Nonzero-mean stagnation near 2^p. https://perso.ens-lyon.fr/elisa.riccietti/doc/slides_M2/prob_err.pdf
- Han–Demmel–You [V-page: full]. https://arxiv.org/abs/1911.08907
- Sakr et al. [V-page: full]. https://arxiv.org/abs/1901.06588
- Megatron-LM issue #6199 [V-page]. https://github.com/NVIDIA/Megatron-LM/issues/6199
- Megatron-LM arguments.py [V-page]. https://raw.githubusercontent.com/NVIDIA/Megatron-LM/main/megatron/training/arguments.py
- Widrow et al. 1996 [V-page: pp. 1–3]. https://isl.stanford.edu/people/widrow/papers/j1996statisticaltheory.pdf

**Discriminating pilot, if anyone wants to revive it.** A two-minute check: the polar-factor deviation of msign(G) under an emulated bf16 ring at P ∈ {1024, 4096}. Kill completely if it is under 1%.

---

# Final recommendation

Pilot **C1, reframed** tonight as the main bet: it is the most likely route to a novel result. Run **C0, reframed** as an orthogonal hedge. The two pilots touch different code and run in parallel on the CPU. C4 is the fallback if C1 dies, since it uses the same agent-session generator. Shelve C3 except for the VAT design fix. Kill C2 and C5.

## P-A (primary): ordering vs. fallback under continuous batching (CPU, NumPy/Numba, under 2 h)

**Location.** A new folder, `/private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/p1_cb/`, extending `p1_thrash.py`. Seed every run, and log the config and seed.

**Model.** The cost constants below are assumptions of A100/8B order (refuter 2's values from the C4 review), not measurements.
- Iteration time: τ = 2 ms + max(9.5 ms, 0.084 ms × (prefill tokens + decode seqs)) + Σ_running 0.71 ms × ctx_i/8192 + 3.5e-9 s × Σ new_i × ctx_i.
- Prefill chunk budget 8192 tokens per iteration; at most 256 running sequences.
- KV memory M = 300k tokens.
- Sessions: Poisson(λ) arrivals; T ~ Geometric with mean 15 (cap 60); L₀ = 2000 tokens; each turn adds Δ = 550 prompt tokens plus d = 100 decode tokens. Tool time Z ~ Exp(5 s), with a lognormal variant at CV 1.5.
- Hit: the session's KV is still resident, so only Δ tokens are prefilled. Miss: L_t tokens are prefilled.
- Memory-gated admission. The KV of idle (in-tool) sessions is evicted LRU.

**Policies**
1. FCFS.
2. Pure LPM: sort the waiting queue by matched-prefix length, ties broken FCFS.
3. **LPM-128**: FCFS for any scheduling pass in which more than 128 requests are waiting (mirrors SGLang).
4. Aging-LPM: any request waiting longer than W_max ∈ {10, 30} s goes first, FCFS.
5. FCFS with a session cap N\* = M / L_q (CONCUR-like baseline).

**Runs**
1. **Calibrate.**
   - λ_miss: the saturated session throughput with caching off.
   - λ_cap: the largest λ at which pure LPM stays stable from an empty start for 20k s, found by bisection.
   - R = λ_cap / λ_miss.
2. **Recovery** from 300 cold queued sessions. λ ∈ {1.25, 1.5, 2, 3, 4} × λ_miss (below λ_cap), all 5 policies, 3 seeds, 30k s. "Recovered" means waiting queue < 20 and hit rate > 0.8 over the last 5k s.
3. **Burst.** λ = 2λ_miss from empty; warm up 5k s; inject 200 sessions within 60 s; run 25k s more; 5 seeds. Report the hit rate over the window [t+10k s, t+25k s].
4. **Ramp.** A triangle from 0.5λ_miss up to 0.9λ_cap and back down, 30k s each way, 3 seeds. Report throughput and hit rate against λ on both legs, and the hysteresis area.
5. **If time remains:** escape from an empty start under LPM-128 at λ ∈ {2, 3} × λ_miss, 10 seeds, 50k s. Also log the maximum waiting-queue length seen in the good state, to see how far 128 is from typical operation.

**Metrics per 1000 s window:** hit rate, waiting queue, sessions/s, p50 and p99 per-turn latency, first-turn wait for cold sessions.

**Decision rule**
- **GO.** Draft the one-A100 Nova job for SGLang (pinned; stock vs. fallback patched to ∞ with an O(1) session→radix-node lookup) vs. vLLM FCFS. Ask Akshat before any sbatch, and pass `--account=f2026.coms.6250.02` explicitly. All of the following must hold:
  - R ≥ 2.
  - Some λ ≥ 1.5λ_miss exists where pure LPM recovers 3/3, FCFS 0/3, and LPM-128 at most 1/3.
  - The burst traps LPM-128 (hit < 0.2 for at least 10k s) in at least 3/5 seeds, while pure LPM returns to hit > 0.8 in at least 4/5.
  - Aging-LPM with W_max = 30 s keeps at least 70% of pure LPM's largest recovered λ.
- **REFRAME** to a paper on measured FCFS hysteresis only if R ≥ 2 but pure LPM fails to recover under continuous batching.
- **KILL** if R < 1.5 (batch amortisation closes the window), or if LPM-128 is never trapped.

**Also tonight, read-only, no GPU**
- Pin the SGLang and vLLM versions intended for Nova. Read `schedule_policy.py` at that tag, and vLLM V1's scheduler policies.
- Check whether HiCache is on by default.
- Re-read CONCUR for its schedule policy, and for whether its thrashing appears only with more than 128 agents.

## P-B (hedge): does a toy reproduce Zmushko's signature, and does it co-occur with a sharpness cap? (CPU, under 2 h)

**Setup.** Extend `p3c_eos_delay_mlp.py`.
- Data and model: sklearn digits, n = 1000, standardised; 64-64-10 tanh MLP; MSE loss.
- Optimisers:
  - Adam with β₂ = 0.95, ε = 1e-8, bias correction, no weight decay, β₁ ∈ {0.9, 0.99}.
  - Muon-like: momentum 0.95; update = polar(M) via `np.linalg.svd` on W1 and W2; biases updated with Adam.
- Modes:
  - Sync.
  - τ = 1: the update uses the gradient at x_{t−1}.
  - EF: x_{t+1} = x_t − 2u_{t−1} + u_{t−2}.
- Batch: full (1000), and B = 64 with a fixed probe batch.
- η ∈ {3e-3, 1e-2, 3e-2}; 6000 steps; seeds {0, 1, 2}.

**Measure every 100 steps**
- η·λ_max(D^{−1/2} H D^{−1/2}) with D = diag(√v̂ + ε). Use central finite-difference HVPs and 30 power iterations.
- η·λ_max(H), and the median v̂ on the top eigenvector's largest coordinates.
- Final loss as the mean over the last 500 steps.

**Pre-registered predictions and decision rule**
- (a) Full batch, Adam β₁ = 0.9: delayed η·S_P ∈ [0.75, 1.25] and EF ∈ [2.0, 3.4] in at least 2/3 seeds at at least 2 values of η. Delayed with β₁ = 0.99 also lands in [0.75, 1.25].
  - If sync never exceeds 10, the toy has not reached Adam's edge of stability. That is inconclusive, not a kill.
- (b) Minibatch B = 64: if sync η·S_P ≤ 1.5 at the best-loss η while delay still costs at least 10% in loss, the delay penalty is not a stability effect in this regime. Downgrade C0 to a full-batch workshop note.
- (c) β₁ = 0.99 vs. 0.9 under delay: the growth-rate account predicts a smaller penalty at 0.99 despite the identical cap. Threshold-only theory predicts no difference.
- (d) If the Muon-like delay penalty is at least Adam's at tuned η, the asymmetry does not reproduce in the toy. Record it as a negative.

**GO** to the 135M GPU probe (under 100 GPU-h; ask before any sbatch) if (a) passes for both delayed and EF, and (b) shows sync η·S_P ≥ 2 with delayed ≈ 1 exactly where the penalty appears.

Pre-registered LM-scale prediction for that probe: sync η·S_P ∈ [2, 4.5], delayed ∈ [0.75, 1.25], EF ∈ [2, 3.4]. This is inferred from Zmushko's 90% EF recovery and is not verified.

## Before writing any novelty claim

Every literature agent ran out of search budget. These searches still need to run:
- For C1: "metastable" or "hysteresis" with prefix cache or agent serving; forward citations of 2606.15555, 2605.04595, 2504.11320 and 2601.22705; the original SGLang paper's justification for LPM (nobody opened it).
- For C0: "edge of stability" with stale, delayed or asynchronous gradients; Kosson App. I and PipeMare App. B.3, read as rendered pages.