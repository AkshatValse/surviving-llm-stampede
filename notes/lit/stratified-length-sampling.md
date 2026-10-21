# Lit-check: joint stratified (length) sampling + GPU scheduling for LLM training

Scout (sonnet), 2026-10-20. Abstract-level reads; Pollux, Katharopoulos & Fleuret, Zhao & Zhang seen via search snippets only.

**Verdict: NARROW.** System half (DP load balance, balanced packing) is well covered. Statistics half has a very close 2026 prior: **Cost-Aware Learning** (Mohri, Globerson, Kaplan, Koren, Mansour, arXiv 2604.28020): sampling from gradient-norm × cost distribution, applied to GRPO with cost = token count. https://arxiv.org/abs/2604.28020

Open sliver: length-stratified sampler with explicit unbiasedness for per-token vs per-sequence objective + allocation minimizing variance per unit of **parallel completion time (max over DP ranks, quadratic attention cost)** + SFT/pretraining time-to-quality evaluation.

Other close work: Zhao & Zhang 2014 (arXiv 1405.3080); Katharopoulos & Fleuret ICML 2018; Pollux OSDI 2021; WLB-LLM OSDI 2025 (arXiv 2503.17924); Zeppelin (2509.21841); SlimPack (2509.26246); Hierarchical Balance Packing NeurIPS 2025 (2503.07680); Krell et al. packing (2107.02027); Dataset Decomposition NeurIPS 2024 (2405.13226); Sequence Length Warmup NeurIPS 2022 (2108.06084). Gradient-accumulation normalization bug: blogs only (Unsloth, HF), unopened.

Risks: must beat Cost-Aware Learning on max-over-ranks cost; Neyman gain small if within-stratum length weakly predicts gradient variance (measure early); 2026 follow-ups not exhaustively searched.
