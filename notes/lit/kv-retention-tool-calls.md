# Lit-check: KV retention during agent tool calls (rent-or-buy)

Scout (sonnet), 2026-10-20. URLs were opened by the scout; abstracts mostly, Continuum full text partly. Not independently re-verified by the main session.

**Verdict: NARROW.** Systems side is crowded. Open sliver is the theory: an explicit ski-rental / optimal-stopping model with competitive-ratio or optimality guarantees, three-way hold/swap/recompute decision, and a real queueing model of memory pressure.

Closest work:
- Continuum (Li et al., arXiv 2511.02230, v7 Sep 2026): TTL τ* = argmax P(τ)·Benefit − Cost(τ) from per-tool empirical latency CDF. No competitive ratio / stopping proof. **Closest.** https://arxiv.org/abs/2511.02230
- InferCept (Abhyankar et al., ICML 2024): discard/preserve/swap for intercepted requests. https://arxiv.org/abs/2402.01869
- TokenCake (Bian et al., arXiv 2510.18586, page says EuroSys '27): offload during function-call stalls when predicted stall > transfer RTT. https://arxiv.org/abs/2510.18586
- MORI (Xia et al., arXiv 2606.00866, May 2026): idleness ranking, CPU offload, real Claude Code traces. https://arxiv.org/abs/2606.00866
- "Ask the Tool, Don't Guess" (Liu et al., arXiv 2609.18849, Sep 2026): argues pre-call duration prediction fails; tools should report progress. https://arxiv.org/abs/2609.18849
- Autellix (Luo et al., arXiv 2502.13965): program-level scheduling. https://arxiv.org/abs/2502.13965
- KVFlow (Pan et al., arXiv 2507.07400): workflow-aware eviction/prefetch. https://arxiv.org/abs/2507.07400
- Pensieve (arXiv 2312.05516), CachedAttention (ATC 2024, arXiv 2403.19708).

Risks: Continuum authors could add theory; 2026 papers attack the learned-distribution premise; real agent traces needed; baselines must include Continuum, InferCept, MORI.
Unchecked: Parrot; arXiv 2601.06007; learning-augmented ski-rental theory papers (leads only).
