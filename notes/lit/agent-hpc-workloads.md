# Lit-check: scheduling AI-agent-driven experimentation on shared HPC clusters

Scout (sonnet), 2026-10-20. Standard-mode search; abstracts.

**Verdict: NARROW, window closing.** No trace characterization of agent-submitted job streams; no agent-agnostic queueing-theoretic admission layer between agent and SLURM. But several 2026 agent frameworks embed their own job controllers.

Closest:
- RASER (Attar-Khorasani et al., arXiv 2609.03598, 2026): agentic workflows on Slurm via job arrays + work stealing + checkpoint/requeue; 39% lower makespan. **Most direct competitor.** https://arxiv.org/abs/2609.03598
- ScienceFlow (Zhao et al., arXiv 2608.14354): evidence-aware execution controller inside the agent. https://arxiv.org/abs/2608.14354
- AlphaLab (Hogan et al., arXiv 2604.08590). https://arxiv.org/abs/2604.08590
- AI Research Preference Models (Foster et al., arXiv 2608.13940): rank experiments before spending GPU time. https://arxiv.org/abs/2608.13940
- Long-Horizon Autonomous Architecture Research (arXiv 2608.01995): snippet (unconfirmed) says queue wait dominated.
- HyperSched (2001.02338); ASHA MLSys 2020 (1810.05934); LLM-based HPC job scheduling (2506.02025); Agentic CPU-GPU Scheduling (2607.22242); AI Scientist (2408.06292); MLS-Bench (2605.08678).

Risks: real agent traces needed (simulation otherwise); cluster-specific; reviewers ask why a separate layer.
