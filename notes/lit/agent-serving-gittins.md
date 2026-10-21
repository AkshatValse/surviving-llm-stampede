# Lit-check: queueing-theoretic (Gittins) scheduling of multi-step agent programs

Scout (sonnet), 2026-10-20. Abstract-level.

**Verdict: NARROW (headline taken).** Hermes (Liu et al., arXiv 2506.14851, ACM TACO 2026) already ranks whole LLM applications by a Gittins index over a probabilistic demand graph; >70% mean / >80% P95 completion-time reduction (their numbers). No batching/KV/processor-sharing capacity model; baselines vLLM, Parrot, VTC, EDF (not Autellix, not learned SJF). https://arxiv.org/abs/2506.14851

Open sliver: Gittins with batching/KV capacity (processor sharing with batch-dependent capacity); heavy-tailed unbounded agent loops; comparisons vs Autellix/PLAS and learned SJF; latency (not throughput) optimality in the batched model — extending Dai et al. (arXiv 2504.07347, throughput-optimal scheduling for LLM inference and agents). Needs real proofs.

Other: Autellix (2502.13965; NSDI '26 as "Agentix" per scout, unopened); Learning-to-Rank scheduling NeurIPS 2024 (2408.15792); SSJF (2404.08509); FastServe (2305.05920); Chen, Ye, Zhou robust scheduling (2508.14544); Teola (2407.00326); KVFlow NeurIPS 2025; Parrot OSDI 2024; Andes (2404.16283); Scully & Harchol-Balter Gittins M/G/1 (2111.10703).
