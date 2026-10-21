# Related work draft: metastability in agentic prefix-cache serving (current leader)

Status: DRAFT, 2026-10-21. Every entry below was opened by a `scout` subagent (sonnet) or a workflow literature agent, and most were read through a fetch summarizer. The main session has **not** re-opened these pages. Before anything goes into `paper/`, re-verify it: authors, venue and year against the actual page. Sources: `notes/lit/engine-sources-prefix-cache.md`, `notes/lit/kv-mechanisms-continuum-peek-concur-wait.md`, `notes/lit/lru-cyclic-agent-kv.md`, `notes/DIRECTION_SEARCH_2.md`. Items marked *(unconfirmed)* must not be cited yet.

## 1. Metastable failures and thrashing (the classical frame)
- **Bronson et al., "Metastable Failures in Distributed Systems," HotOS'21.**
  - Content: names metastable failures and uses the cold-cache vulnerable state as a canonical example.
  - Read depth: PDF §2.2 and Fig. 2.
  - Link: https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf
- **Denning, "Thrashing: Its Causes and Prevention," AFIPS 1968.**
  - Content: introduces the working set, the thrashing curve, and the multiprogramming-level cap. This is our μ(n) frame.
  - Read depth: pp. 1–6.
  - Link: https://cs.uwaterloo.ca/~brecht/courses/epfl/Possible-Readings/vm-and-gc/thrashing-denning-afips-1968.pdf
- **Gibbens, Hunt & Kelly** (bistability in networks with alternative routing; trunk reservation as the fix). Read depth: pp. 1–6. Link: https://www.statslab.cam.ac.uk/~grg1000//books/hammfest/8-rjg.pdf
- **Alvaro et al.** (CTMC models of metastability and escape times for software systems). Read via HTML. Link: https://arxiv.org/abs/2510.03551
- **Classical LRU looping failure:**
  - LIRS, Jiang & Zhang, SIGMETRICS 2002.
  - EELRU, Smaragdakis, Kaplan & Wilson. The extended version was opened.
  - Chou & DeWitt, VLDB 1985 (MRU for looping scans).
  - ARC, Megiddo & Modha, FAST 2003.

## 2. Stability and queueing theory of LLM serving (closest theory)
- **Ao, Luo, Simchi-Levi, Wang, "WAIT"** (arXiv 2504.11320).
  - Model: KV growth during decode, no prefix caching.
  - Results: fluid throughput bounds; a non-work-conserving WAIT admission rule with an O((ζT)^-1/2) gap; greedy FCFS with LIFO restarts has an Ω(1) gap.
  - Covers no multi-turn sessions and no tool calls.
- **Ao, Dong, Luo, Simchi-Levi, "Service-Induced Congestion"** (arXiv 2606.15555; v3 dated 2026-10-20).
  - Result: in a decode-only model with deterministic lengths, the eviction-free fixed point is unstable and the maximal-eviction cycle is stable. Instability for two classes depends on a gcd condition. The remedy is a rate-limited admission cap.
  - No prefix caching.
  - **Most direct theoretical neighbour. The group is active, so scoop risk is real.**
- **Dai et al., throughput-optimal scheduling for LLM inference and agents** (arXiv 2504.07347). Work-conserving policies are throughput-optimal when service does not depend on cache state.
- **Nie, Si & Zhou** (arXiv 2605.04595). Memory-time capacity for one-shot requests.

## 3. Prefix and KV-cache mechanisms for agents (what we evaluate)
- **SGLang (Zheng et al., NeurIPS 2024, arXiv 2312.07104).**
  - Design: LPM / DFS-order scheduling with an optimality theorem. The paper notes that LPM "can lead to starvation."
  - Engine source at v0.5.22:
    - Default `schedule_policy` is `fcfs`.
    - LPM falls back to FCFS when more than 128 requests are waiting.
    - Waiting requests do not lock prefixes.
    - A waiting-prefix LRU refresh exists and is enabled by default.
- **vLLM v0.32.0.** FCFS or priority scheduling only. Waiting requests' cached blocks can be lazily evicted.
- **PEEK (Xie et al., arXiv 2607.02525).**
  - Mechanism: eviction ranking that protects prefixes needed by queued requests, plus a two-lane cLPM.
  - Reports "scheduling-induced thrashing" and the 128 fallback empirically.
  - No dynamics or hysteresis analysis.
  - *Our sim:* PEEK-like protection does not escape the congested state (P2).
- **Continuum (Li et al., arXiv 2511.02230).**
  - Mechanism: tool-call-aware TTL pinning, with τ chosen from the empirical CDF of tool durations.
  - No formal guarantees.
  - *Our sim:* blocking pins with program priority recover only at τ = 5–10 s. They fail at 20 s and with FCFS order (P3).
- **CONCUR (Chen et al., ICML 2026, PMLR v306; arXiv 2601.22705).**
  - Mechanism: AIMD cap on active agents driven by KV usage and hit rate. It reports "middle-phase thrashing" on SGLang.
  - Its convergence argument is informal.
  - *Our sim:* the CONCUR-style cap recovers (P5). This is the strongest prior mechanism, and our theory explains why it works.
- **Related systems:**
  - XPerf (arXiv 2608.20370): hit-rate collapse past a rate threshold, measured on an up-sweep only.
  - CacheWise (arXiv 2606.16824).
  - ThunderAgent (arXiv 2602.13692).
  - KVFlow (arXiv 2507.07400).
  - MORI (arXiv 2606.00866).
  - InferCept (ICML 2024).
  - TokenCake (arXiv 2510.18586).
  - DLPM (arXiv 2501.14312).
- **Eviction-order fixes:**
  - RR-Evict (arXiv 2609.32278): recency synchronization; round-robin eviction for graceful degradation; excludes overload.
  - Randomization Boosts KV Caching (ICLR 2026, arXiv 2601.18999): randomized eviction under round-robin arrivals.
  - When Fancy Eviction Fails (arXiv 2609.28870): LRU is hard to beat on production agent traces in non-overload regimes.

## Positioning (draft paragraph)
Prior agent-serving systems (PEEK, CONCUR, XPerf, CacheWise) report prefix-cache thrashing empirically and propose mechanisms against it. Queueing analyses (Ao et al.; Dai et al.; Nie et al.) establish instability and admission caps for KV growth without prefix reuse. We connect the two. In simulation, prefix caching combined with multi-turn tool-calling sessions gives the serving system a metastable good state over a wide window of arrival rates above λ_miss. A transient burst moves the system into a congested regime that persists for the whole simulated horizon. The congested-state throughput μ_∞ predicts each policy's recovery threshold:
- **FCFS-type orders and queued-prefix protection:** μ_∞ = λ_miss under any eviction rule (Prop. A).
- **Resident-first ordering (LPM):** helps only through tool calls shorter than the congested idle-KV lifetime.
- **Working-set caps (CONCUR-style AIMD, static caps near the peak of μ(n)) and short TTL pins with program priority:** raise μ_∞ well above λ_miss.

This view explains which existing fixes work and why static caps are fragile. *Every claim in this paragraph rests on simulation as of 2026-10-21. The real-engine validation is pending (Nova plan).*
