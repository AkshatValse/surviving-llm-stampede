# One-page outline: VAT (DRAFT; depends on pilot and Nova results)

**Working title:** *Don't Trust the Winner: Anytime-Valid Racing for Agent-Driven Performance Tuning*

## Claim
Agent-driven tuning loops select a winner from many candidates that were measured with noisy benchmarks. They report the winner's measured speedup, which overstates the true speedup. They also accept false "improvements" at rates far above any nominal level. A paired, interleaved measurement protocol fixes both. It uses per-candidate anytime-valid confidence sequences at level $\alpha/K$, and it applies racing elimination over them. The result is a family-wise false-improvement rate of at most $\alpha$ and an unbiased lower bound on the reported speedup, and it needs less benchmark time than fixed-repetition testing with the same guarantee.

## Notation
$K$ candidates; paired block $j$ of candidate $k$ gives $x_{kj}=\log(t^{\text{base}}_{kj}/t^{(k)}_{kj})$; target $\theta_k=\mathbb E[x_{kj}]$, or the mean of the clipped version; real improvement means $\theta_k>\log(1+\delta)$.

## Contributions
1. **Measurement study.** We quantify noise structure on CPU (M3 Max) and on Nova GPUs (A100-PCIe, H200): within-process CV, between-process and between-node variance components, autocorrelation, and heavy tails. We then measure the resulting winner's-curse inflation and false-improvement rate of naive select-the-best as functions of $K$ and $r$.
2. **Protocol.** We combine paired, interleaved blocks with PrPl-EB confidence sequences (Waudby-Smith & Ramdas) at $\alpha/K$ and racing. We prove (short; it mostly assembles known results) family-wise control under optional stopping and adaptive candidate generation. Candidates proposed adaptively by an agent are handled by α-spending over an unbounded stream, $\alpha_k=\alpha\cdot 6/(\pi^2k^2)$ or similar. **This needs math-checking.**
3. **Cost.** We compare benchmark-time savings with Bonferroni-t at fixed $r$ and with irace/F-Race-style racing, at equal power.
4. **Agent loop case study.** An LLM agent (Claude) iteratively proposes kernel variants for 2–3 kernels. We contrast the reported speedups under naive and VAT protocols against held-out re-measurement on fresh nodes.

## Experiments
- E1 noise characterization: CPU pilot, then A100/H200, with multiple nodes.
- E2 offline resampling: inflation, FWER, power, and cost vs. $K$, $r$, $\delta$, $\alpha$.
- E3 synthetic-null stress: all candidates equal, giving FWER vs. $K$ for naive.
- E4 online agent loop: naive vs. VAT, with end-to-end tuning wall-clock and the true speedup achieved.
- E5 robustness to autocorrelation and drift: blocked vs. unblocked, interleaving vs. not.

## Figures
1. Inflation vs. $r$ for several $K$, with VAT points at their mean cost.
2. FWER vs. benchmark cost (naive, Bonferroni-t, racing variants).
3. Noise variance decomposition by platform.
4. Agent loop: reported vs. re-measured speedup per iteration.

## Threats (reviewer questions)
- "Noise is small on GPUs, so who cares?" Answer with E1/E2 numbers on Nova. If they are small, report that honestly and pivot to the "cost savings at equal guarantee" framing.
- "Isn't this just racing?" Classical racing (F-Race) uses non-anytime-valid tests repeatedly, and its error control is heuristic. We should verify that claim from the irace paper before making it.
- "Clipping changes the estimand." State the target explicitly, or use a betting CS on raw bounded times.
- "The truth is not observable." Use held-out processes and nodes, and report sensitivity to that choice.
