# Lit-check: time-to-quality-optimal checkpointing on preemptible SLURM queues

Scout (sonnet), 2026-10-20. Abstract-level; several PDFs unreadable.

**Verdict: NARROW.** Non-exponential Young/Daly extensions, history-driven interval tuning, and DL checkpoint systems are covered. Open sliver: hazard fitted from the cluster's own sacct logs + random requeue wait in the renewal objective + time-to-target-quality objective (diminishing returns) + instruction-vs-scavenger partition choice.

**Scout warning (important):** if progress is linear and wait is iid, the result may reduce to Daly + an additive constant → check analytically before building anything.

Closest:
- Desai, Pei, Bhimani, Kim, *Cost-Efficient Training and Checkpointing for Large Models on Preemptible Cloud VMs*, EuroMLSys 2026, DOI 10.1145/3805621.3807617 (page: https://discovery.fiu.edu/display/pub551034). Snippet (unconfirmed): predicts spot preemption from history, dynamic interval. **Closest threat; read first.**
- Bautista-Gomez et al., survey "Should we always checkpoint à la Young/Daly?", FGCS 2024. https://icl.utk.edu/node/1837
- Bougeret et al., INRIA RR-7520 (2011), non-exponential DP schedules (content from snippet).
- Aupy et al., JPDC 2013, checkpointing + fault prediction. https://arxiv.org/abs/1302.3752
- CheckFreq FAST 2021; Kokolis et al. 2024 (ETTR, arXiv 2410.21680); Parcae NSDI 2024 (2403.14097); Bamboo (2204.12013); Oobleck SOSP 2023; Varuna (2111.04007); Gemini SOSP 2023; Check-N-Run (2010.08679).
- Unconfirmed: INRIA RR-9465; FTXS 2023 fixed-length reservation paper.
