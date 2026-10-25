# Related work draft: metastability in agentic prefix-cache serving (current leader)

Status: DRAFT, 2026-10-21. Citations audited on 2026-10-25: see `notes/lit/CITATION_AUDIT_2026-10-25.md` for the evidence behind every change. Bibliography keys in `paper/refs.bib` are given in brackets.

How this file was checked: every entry below was re-opened on a primary page on 2026-10-25. For 18 works the paper text was read and searched for the specific claim; the others were checked at abstract or metadata level, as the audit table records. Changes made in that pass are marked **[fixed]** (a wrong or overstated claim) or **[added]** (a verified fact or work that was missing). Lines marked *Our sim* are our own results and were not touched. Nothing here may be cited in `paper/` beyond the evidence class recorded in the audit.

Earlier sources: `notes/lit/engine-sources-prefix-cache.md`, `notes/lit/kv-mechanisms-continuum-peek-concur-wait.md`, `notes/lit/lru-cyclic-agent-kv.md`, `notes/DIRECTION_SEARCH_2.md`.

## 1. Metastable failures and thrashing (the classical frame)
- **Bronson et al., "Metastable Failures in Distributed Systems," HotOS'21** [bronson2021metastable].
  - Content: defines a metastable failure as a bad state that persists after the trigger is removed, sustained by a feedback loop, in open systems with uncontrolled load; gives the stable, vulnerable, metastable lifecycle. The cold look-aside cache (s2.2) is one of four case studies; the lifecycle figure (Fig. 2) uses the retry case of s2.1. **[fixed: the earlier text called the cache "a canonical example" and tied it to Fig. 2.]**
  - Read depth: full text.
  - Link: https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf
  - **[added]** Companion survey of 21 real incidents: Huang et al., "Metastable Failures in the Wild," OSDI'22 [huang2022metastable].
- **Denning, "Thrashing: Its Causes and Prevention," AFIPS Fall Joint Computer Conference 1968** [denning1968thrashing].
  - Content: shows analytically that when memory is at the verge of saturation, admitting one more program collapses processor efficiency, and that thrashing is prevented by keeping the active programs' working sets within memory (the condition n <= n0, Eq. 19), i.e. by a working-set strategy that limits the number of resident programs. **[fixed: the earlier text said this paper "introduces the working set, the thrashing curve, and the multiprogramming-level cap".]** The working-set model is Denning, "The Working Set Model for Program Behavior," CACM 11(5), 1968 [denning1968working], which this paper reviews and cites. The paper has no plotted throughput-versus-multiprogramming curve and no hysteresis analysis; the mu(n) thrashing curve is our framing of its collapse result.
  - Read depth: full text.
  - Link: https://cs.uwaterloo.ca/~brecht/courses/epfl/Possible-Readings/vm-and-gc/thrashing-denning-afips-1968.pdf
- **Gibbens, Hunt & Kelly, "Bistability in Communication Networks"** (in Grimmett and Welsh (eds.), *Disorder in Physical Systems*, OUP 1990) [gibbens1990bistability].
  - Content: bistability and hysteresis under random alternative routing in a symmetric loss network; trunk reservation "removes the bistability". It also proves a functional law of large numbers (fluid limit) and uses a one-dimensional diffusion to describe bistable and tunnelling behaviour. **[added: the fluid-limit and diffusion parts.]**
  - Read depth: full text.
  - Link: https://www.statslab.cam.ac.uk/~grg1000//books/hammfest/8-rjg.pdf
- **Alvaro et al., "Formal Analysis of Metastable Failures in Software Systems"** [alvaro2025formal]. **[fixed: title added.]** Continuous-time Markov chain models of request-response servers; metastability defined through escape probabilities and the chain's eigenvalue structure; algorithms for recovery times. arXiv preprint (2510.03551, Oct 2025); no venue found. Read depth: abstract. Link: https://arxiv.org/abs/2510.03551
- **Classical LRU failure on looping access:**
  - EELRU, Smaragdakis, Kaplan & Wilson, SIGMETRICS 1999 [smaragdakis1999eelru]: targets LRU's weakness on loop-like patterns over more pages than fit in memory (abstract level; the journal version was not re-opened).
  - Chou & DeWitt, VLDB 1985 [chou1985evaluation]: for a looping reference pattern (nested-loops join) MRU is the right replacement and LRU is inappropriate (full text).
  - LIRS, Jiang & Zhang, SIGMETRICS 2002 [jiang2002lirs]: a low-inter-reference-recency policy for weak-locality patterns where LRU does badly (metadata and abstract; the loop-size detail was not checked). **[fixed: the earlier text said "LRU on loops slightly larger than the cache".]**
  - ARC, Megiddo & Modha, FAST 2003 [megiddo2003arc]: scan resistance and recency/frequency adaptivity, **not** a fix for cyclic re-reference of a too-large working set. **[fixed: it was listed under the looping failure.]**

## 2. Stability and queueing theory of LLM serving (closest theory)
- **Ao, Luo, Simchi-Levi, Wang, "Optimizing LLM Inference: Fluid-Guided Online Scheduling with Memory Constraints" (WAIT)** (arXiv 2504.11320, v4 June 2026; no venue found) [ao2025wait].
  - Model: KV growth during decode, no prefix caching.
  - Results: fluid throughput bounds; a threshold admission rule, WAIT, that holds the server idle until enough requests accumulate (so it is non-work-conserving; this is our characterisation, the paper does not use the term), with an O((zeta T)^-1/2) throughput gap (O(1/(zeta T)) under strict slack); greedy FCFS with LIFO restarts has an Omega(1) gap when C = M. Experiments: Vidur simulation, Llama-2-7B, A100.
  - Covers no multi-turn sessions and no tool calls.
- **Ao, Dong, Luo, Simchi-Levi, "Service-Induced Congestion in Memory-Constrained LLM Serving"** (arXiv 2606.15555; v1 14 Jun 2026, v2 19 Oct, v3 20 Oct 2026; no venue found) [ao2026service].
  - Result: in a decode-only model with deterministic lengths, the eviction-free fixed point is unstable and the maximal-eviction cycle is stable (throughput loss up to 50%). For two classes, instability depends on a gcd/coprime condition on decode lengths in an input-dominated scaling regime. The remedies are a rate-limited admission cap and length mixing.
  - No prefix caching: the model explicitly abstracts away prefix-cache reuse, and the SGLang benchmark-workload experiments added in v2 (Appendix D.4) state that prefix caching is disabled. Agents, multi-turn and tool calls appear only as motivation. **[added: the explicit statements.]**
  - **Most direct theoretical neighbour. The group is active, so scoop risk is real.**
- **Dai, Deng, Li & Peng, "Throughput-Optimal Scheduling Algorithms for LLM Inference and AI Agents"** (arXiv 2504.07347, v3 May 2026; v1 listed the authors as Li, Dai, Peng) [dai2025throughput].
  - Result: a large class of work-conserving policies is throughput-optimal for single servers with several request classes and for agent DAG and fork-join workflows, in a model with no cache state. **[added]** The paper also constructs an example where work-conserving scheduling fails under cyclic routing, which is relevant to sessions that return to the server.
- **Nie, Si & Zhou, "A Queueing-Theoretic Framework for Stability Analysis of LLM Inference with KV Cache Memory Constraints"** (arXiv 2605.04595; ICML 2026) [nie2026queueing]. Stability and instability conditions with both computation and KV memory constraints for single requests (prompt, then decode); no prefix reuse, no sessions. **[fixed: the earlier text described it as "memory-time capacity for one-shot requests", which is our paraphrase, not their framing.]**
- **[added] Yao, Gao, Lyu, Grosof & Simchi-Levi, "Multi-Turn LLM Conversations under the Least-Recently-Used Policy: Mean-Field Asymptotics and Hit Ratio Approximation"** (arXiv 2609.02027, Sep 2026; no venue found) [yao2026multiturn]. An analytic hit-ratio model for multi-turn serving under LRU: Poisson conversation arrivals, i.i.d. inter-turn gaps, and a closed-form hit-ratio limit as arrival rate and memory capacity grow together. The inter-turn gap is exogenous, and the appendix notes that raising the arrival rate until compute is the bottleneck would let latency change the gaps, so the theory avoids that regime; the paper does not discuss thrashing, hysteresis or admission control. The feedback from load to gap length is the loop our model is about. See the audit's Scoop check. Read depth: full text (model and assumptions).

## 3. Prefix and KV-cache mechanisms for agents (what we evaluate)
- **SGLang (Zheng et al., NeurIPS 2024, arXiv 2312.07104)** [zheng2024sglang].
  - Design: longest-shared-prefix-first (LPM) scheduling, equal to DFS order of the radix tree, with an optimality theorem (Thm 3.1: a batch visited in DFS order gets the optimal hit rate when the cache holds at least the longest request). **[fixed: scope added; the theorem is offline, "in the online case, the DFS order will be disrupted".]** The paper says greedy cache-aware scheduling "can lead to starvation" and leaves fair scheduling to future work.
  - Engine source at v0.5.22 (read twice through a page summariser; no line numbers):
    - Default `schedule_policy` is `fcfs`.
    - LPM (or HRRN) falls back to FCFS when more than 128 requests are waiting (`WAITING_QUEUE_PREFIX_MATCH_MAX = 128`).
    - Waiting requests do not lock prefixes; the persistent lock is taken at admission.
    - A waiting-prefix LRU refresh exists and is on by default. **[fixed: detail added.]** It refreshes up to 128 waiting requests every 32 scheduling passes, is gated by `SGLANG_ENABLE_WAITING_PREFIX_REFRESH`, and does nothing for cache-aware policies, non-LRU eviction, decode disaggregation, or when the tree cache reports fast match. So it acts under FCFS, including the LPM-to-FCFS fallback.
- **vLLM v0.32.0** (PagedAttention paper: Kwon et al., SOSP 2023 [kwon2023vllm]). FCFS or priority scheduling only (`policy` is `fcfs` or `priority`, default `fcfs`). A freed cached block keeps its hash at the tail of the free queue and is evicted only when the block is reallocated, so a waiting request's cached blocks can be lazily evicted before admission.
- **PEEK (Xie et al., arXiv 2607.02525, v2 Sep 2026; under review)** [xie2026peek].
  - Mechanism: eviction ranking that protects prefixes needed by queued requests (a ranking, not a pin), plus a two-lane cLPM scheduler.
  - "Scheduling-induced thrashing" is PEEK's name for stock LPM breaking hit-length ties by arrival order, which interleaves cold prefix groups so that a cache holding one prompt reloads each group repeatedly; it is **not** the LPM-to-FCFS fallback. PEEK mentions the 128 fallback only as an existing exit (sec 3.3) and sets its "heavy" load so the queue reaches 128; it does not analyse the fallback as a failure. **[fixed: the earlier text said it "reports ... the 128 fallback empirically".]**
  - Tested on SGLang 0.5.9 and vLLM 0.19.1. Its one multi-turn workload (W4) replays a Mooncake conversation trace with 50 ms between turns, with no tool-time model; it is near parity with the baselines. **[added]**
  - No dynamics or hysteresis analysis.
  - *Our sim:* PEEK-like protection does not escape the congested state (P2).
- **Continuum (Li et al., arXiv 2511.02230, v7 Sep 2026; no venue)** [li2025continuum].
  - Mechanism: tool-call-aware TTL pinning, with tau chosen from the empirical CDF of tool durations (Exp(1) assumed at cold start).
  - No formal guarantees.
  - **[added]** Its measured mean tool times are 925 ms (SD 3550) for SWE-Bench and 1923 ms (SD 2133) for BFCL v4, heavy-tailed, against our Exp(5 s) workload of record.
  - *Our sim:* blocking pins with program priority recover only at tau = 5-10 s. They fail at 20 s and with FCFS order (P3).
- **CONCUR (Chen et al., ICML 2026, PMLR 306:17881-17891; arXiv 2601.22705)** [chen2026concur].
  - Mechanism: AIMD cap on active agents driven by KV usage and hit rate (window +2 if usage < 0.2; window x0.5 if usage > 0.5 and hit rate < 0.2). It reports "middle-phase thrashing" on SGLang: DeepSeek-V3 hit rate 80.4% at batch 16, 77.7% at 32, 35.4% at 40.
  - Its convergence argument is informal (a prose argument about a convex recompute penalty).
  - *Our sim:* the CONCUR-style cap recovers (P5). This is the strongest prior mechanism, and our theory explains why it works.
- **Related systems:**
  - XPerf (arXiv 2608.20370; submitted 19 Jun 2026) [wang2026xperf]: a benchmarking and profiling framework, not a mechanism. It observes the prefix-cache hit rate dropping as request rate approaches saturation and throughput falling with fixed concurrency (vLLM v0.19.0), measured on rate up-sweeps and fixed-concurrency runs only, with no down-sweep or burst. **[fixed]**
  - CacheWise (arXiv 2606.16824) [tiwari2026cachewise]: prefix-aware scheduling plus reuse-aware eviction for coding agents in vLLM; closed-load evaluation (N sessions started together), systems differ for N > 10.
  - ThunderAgent (arXiv 2602.13692, v3 Jun 2026) [kang2026thunderagent]. **[fixed: it was listed with no description.]** A program-aware scheduler that detects thrashing (total program memory demand above the KV capacity) and pauses and restores programs with a high/low-watermark hysteresis window; evaluated with a fixed number of parallel workflows, where baselines "suffer from severe throughput collapse once the workload exceeds memory limits"; compared with Continuum; adopted by SkyRL and NVIDIA Dynamo. No open-arrival burst, no metastability analysis.
  - KVFlow (NeurIPS 2025, arXiv 2507.07400) [pan2025kvflow]; MORI (arXiv 2606.00866) [xia2026mori]; InferCept (ICML 2024) [abhyankar2024infercept]; TokenCake (arXiv 2510.18586, accepted at EuroSys '27) [bian2025tokencake].
  - DLPM (arXiv 2501.14312) [cao2025dlpm]: fair scheduling that adds a fairness guarantee to longest-prefix-match locality (client fairness, not agent sessions). **[fixed: description added.]**
- **Eviction-order fixes:**
  - RR-Evict (arXiv 2609.32278; under review) [pan2026rrevict]: recency synchronization; round-robin tail-chunk eviction for graceful degradation; its analysis assumes n_a < m < n (active trajectories fit in the cache) and treats m <= n_a as thrashing outside its scope; baselines LRU and completion-aware LRU.
  - Randomization Boosts KV Caching (ICLR 2026, arXiv 2601.18999) [wu2026randomization]: Leaf-LRU (SGLang) is O(n)-competitive in the worst case, a randomized marking variant O(log n); experiments include a worst-case round-robin query order. Multi-LLM routing setting, not agent tool calls.
  - When Fancy Eviction Fails (arXiv 2609.28870) [liu2026fancy]: on two production agentic traces replayed in a trace-driven simulator, most of 14 policies only reproduce LRU's hit ratio, quick-demotion policies are trace-dependent, and Belady's oracle is far above all of them. It does not model overload or queueing feedback, so "LRU is hard to beat in non-overload regimes" is our reading, not their claim; on the Qwen To-B trace S3-FIFO beats LRU (0.491 vs 0.403 at 24 GiB). **[fixed]**

## Positioning (draft paragraph)
Prior agent-serving systems (PEEK, CONCUR, ThunderAgent, CacheWise) report prefix-cache thrashing empirically and propose mechanisms against it; XPerf is a benchmark that observes it. **[fixed: XPerf does not propose a mechanism; ThunderAgent added.]** Queueing analyses (Ao et al.; Dai et al.; Nie et al.) establish instability and admission caps for KV growth without prefix reuse, and Yao et al. give a mean-field hit-ratio model of multi-turn LRU in which the gaps between turns do not depend on load. **[added]** We connect the two. In simulation, prefix caching combined with multi-turn tool-calling sessions gives the serving system a metastable good state over a wide window of arrival rates above λ_miss. A transient burst moves the system into a congested regime that persists for the whole simulated horizon. The congested-state throughput μ_∞ predicts each policy's recovery threshold:
- **FCFS-type orders and queued-prefix protection:** μ_∞ = λ_miss under any eviction rule (Prop. A).
- **Resident-first ordering (LPM):** helps only through tool calls shorter than the congested idle-KV lifetime.
- **Working-set caps (CONCUR-style AIMD, static caps near the peak of μ(n)) and short TTL pins with program priority:** raise μ_∞ well above λ_miss.

This view explains which existing fixes work and why static caps are fragile. *Every claim in this paragraph rests on simulation as of 2026-10-21. The real-engine validation is pending (Nova plan).*
