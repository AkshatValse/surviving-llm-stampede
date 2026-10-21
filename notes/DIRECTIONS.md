# Phase 0: candidate directions (2026-10-20 overnight)

Scope: ML systems / efficiency, with an agentic angle where possible. Novelty checks were run by `scout` (sonnet) on the 6 most promising; summaries with URLs are in `notes/lit/*.md`. Scout reads were mostly **abstract-level**, so "no prior work found" means "not found by a one-pass search," not "absent."

## All candidates

| # | Direction | Lit-checked? | Verdict |
|---|---|---|---|
| 1 | **Statistically valid agentic performance tuning (VAT):** anytime-valid racing + selection-bias control for agent-driven kernel/config tuning | yes (`valid-agentic-tuning.md`) | NARROW, clear sliver |
| 2 | **KV retention during agent tool calls as rent-or-buy:** ski-rental/optimal-stopping with guarantees, hold/swap/recompute, memory pressure | yes (`kv-retention-tool-calls.md`) | NARROW (theory sliver; systems side crowded: Continuum, InferCept, TokenCake, MORI) |
| 3 | **Joint stratified length sampling + DP scheduling for LLM training:** unbiased per-token/per-sequence objective, Neyman allocation per unit of *max-over-ranks* time | yes (`stratified-length-sampling.md`) | NARROW (Cost-Aware Learning, arXiv 2604.28020, is close) |
| 4 | Batched Gittins scheduling of agent programs (latency-optimal, KV/batch capacity model) | yes (`agent-serving-gittins.md`) | NARROW (Hermes took the headline; sliver needs hard proofs) |
| 5 | Scheduling agent-driven experimentation on shared HPC (trace study + admission layer) | yes (`agent-hpc-workloads.md`) | NARROW, window closing (RASER, ScienceFlow, AlphaLab); needs real agent traces |
| 6 | Time-to-quality-optimal checkpointing on preemptible SLURM queues | yes (`preemptible-checkpointing.md`) | **KILLED** by derivation below |
| 7 | Importance sampling for rare SLO-violation (p99.9) estimation in LLM serving simulators | no | untested |
| 8 | Stratified / control-variate LLM benchmark evaluation (fewer eval samples per accuracy CI) | no | likely crowded (tinyBenchmarks, active eval); untested |
| 9 | Adaptive per-query sample allocation for self-consistency / best-of-n (bandit) | no | likely crowded (adaptive-consistency, compute-optimal TTS); untested |
| 10 | Speculative tool execution for agents | no | likely partly done; untested |
| 11 | Speculative decoding draft length as a renewal/stopping problem under batching | no | likely crowded (SpecDec++, dynamic draft); untested |
| 12 | Goodput-optimal elastic batch size + GPU allocation | no | known prior (Pollux, OSDI 2021): not pursued |
| 13 | Honest time-to-accuracy accounting for data-pruning/coreset methods (selection overhead included) | no | untested; measurement paper |

### Why #6 is killed (my derivation, not yet math-checked)
Let preemptions be Poisson with rate $\lambda$ while running. A segment is $\tau$ work plus a checkpoint of cost $C$, so $a=\tau+C$. After each preemption we pay a requeue wait $W$ (iid, mean $\bar W$) plus restart $R$, and preemption during $W$ and $R$ is ignored. The number of failed attempts is geometric with mean $e^{\lambda a}-1$. Each failure loses $\mathbb E[X\mid X<a]=\frac1\lambda-\frac{a e^{-\lambda a}}{1-e^{-\lambda a}}$. That gives
$$\mathbb E[T(\tau)] = a + (e^{\lambda a}-1)\Big(\mathbb E[X\mid X<a]+\bar W+R\Big) = (e^{\lambda a}-1)\Big(\tfrac1\lambda+\bar W+R\Big).$$
Expected time per unit work is $\big(\tfrac1\lambda+\bar W+R\big)\,\frac{e^{\lambda(\tau+C)}-1}{\tau}$, so **$\tau^\*$ does not depend on $\bar W$ or $R$**. The wait only scales the cost. A time-to-target-quality objective with quality a function of completed work does not change $\tau^\*$ either, because it still minimizes time for a fixed amount of work. What remains is non-exponential hazards, which Bougeret/Benoit/Robert et al. already cover, plus a two-option partition choice. That is too thin. A non-Poisson, load-dependent hazard could revive it, but the HPC checkpointing community already owns that.

## Scores (1–5, higher is better) for the lit-checked survivors

| # | Novelty | Feasibility (Nova + Mac by Dec 18) | Claim strength | Publishability | SwaPP fit | Notes |
|---|---|---|---|---|---|---|
| 1 VAT | 3 | **5** | 3 (depends on measured effect size) | 4 | **5** (agents as method + HPC benchmarking rigor) | uses Akshat's stats directly; cheap GPU-hours |
| 2 KV rent-or-buy | 3 | 3 | 3 | 3 | 4 (agentic workloads as subject) | strong competitors (Stoica/Gonzalez groups); needs serving traces |
| 3 Stratified length sampling | 2–3 | 3 | 3 | 3 | 3 | Akshat's prior idea; needs real GPU training |
| 4 Batched Gittins | 2–3 | 2 | 4 if proofs land | 3 | 4 | proof risk too high for Dec 18 |
| 5 Agent HPC workloads | 3 | 2 | 2 | 3 | 5 | trace data is the blocker |

Venues (all candidates are ML-systems, so roughly the same list): MLSys main track or workshops, NeurIPS/ICLR workshops (ML for Systems, efficient ML), SC workshops (PMBS for benchmarking work, MLHPC), ICPE (performance engineering, a strong fit for #1), EuroMLSys. I have not checked 2027 deadlines; verify them before committing.

## Top 3

### 1. VAT: statistically valid agentic performance tuning (recommended)
- **Claim:** Agent-style select-the-best tuning loops judged by noisy benchmarks systematically overstate speedups and accept false improvements. A paired, interleaved protocol with per-candidate anytime-valid confidence sequences at level $\alpha/K$, used for racing, gives family-wise control of false improvements at $\alpha$ and needs less benchmark time than fixed-repetition testing with the same guarantee.
- **Minimum experiment:** K≈40–200 candidate implementations of a few kernels (stencil, GEMM-like, attention-like via Triton), with paired timings on one A100 and one H200, across several processes and nodes. Measure the winner's-curse inflation of NAIVE-FIXED(r), and the false-improvement rate and power vs. cost for Bonferroni-t and CS-racing. The truth for each candidate comes from held-out processes and nodes. Second stage: an actual agent loop (Claude generating candidates) with and without the protocol.
- **GPU-hours:** ~30–80 (single-GPU timing jobs).
- **Biggest risk:** GPU timing noise may be small relative to effect sizes, which would make naive inflation small and the paper an "it doesn't matter" result. Second risk: AutoTuneBench (arXiv 2609.18123) may already do enough statistics. A full-text read is running.
- **Kill criterion:** kill or reframe if, on Nova GPUs with realistic candidate sets (K≥40), naive inflation is under 2 percentage points of speedup **and** the naive family-wise false-improvement rate is under 10%, **or** CS-racing saves under 20% of benchmark time vs. Bonferroni-fixed at equal power.

### 2. KV retention during tool calls as rent-or-buy
- **Claim:** A prediction-robust (ski-rental-style) retention policy with a stated competitive guarantee matches distribution-fitted TTL policies (Continuum-style) in-distribution and beats them under tool-latency distribution shift, on end-to-end agent latency.
- **Minimum experiment:** discrete-event simulation (tonight's pilot), then vLLM on one A100 with trace-driven agent programs, compared against hold/swap/discard, Continuum-TTL, and a clairvoyant per-call oracle.
- **GPU-hours:** ~100–200.
- **Biggest risk:** heavyweight competitors and missing public agent traces. Rent is endogenous (queueing), so clean ski-rental guarantees may not transfer.
- **Kill criterion:** kill if, in simulation, Continuum-TTL sits within 5% of the clairvoyant oracle on mean and p95 latency in all regimes **and** under shift, which would leave no headroom.

### 3. Joint stratified length sampling + parallel completion time
- **Claim:** For LLM fine-tuning with variable lengths, a length-stratified sampler with Neyman allocation per unit of max-over-ranks completion time reaches target loss in less GPU time than random, length-grouped, packed, and cost-aware (sum-cost) sampling, while staying unbiased for the chosen objective.
- **Minimum experiment:** fine-tune a 125M–1B model on a variable-length SFT set on 4–8 A100s, measuring time-to-target-loss over 3 seeds.
- **GPU-hours:** ~300–600.
- **Biggest risk:** Cost-Aware Learning (Mohri et al. 2026) plus the balanced-packing systems papers. The within-stratum gradient-variance gain may be small.
- **Kill criterion:** kill if the measured per-stratum gradient-variance heterogeneity predicts less than 10% variance reduction over proportional allocation at equal cost.

## Pilots tonight
- #1 → branch `pilot/vat` (CPU Numba stencil candidates on the M3 Max; real timings, offline protocol resampling).
- #2 → branch `pilot/kvrent` (discrete-event simulation).
- #3: no local pilot is possible (no PyTorch installed locally).
