# Lit-check: statistically valid agentic performance tuning

Scout (sonnet), 2026-10-20. Abstract-level reads; URLs opened by the scout, not independently re-verified by the main session.

**Verdict: NARROW.** No work combines anytime-valid inference + selection-bias correction + adaptive benchmark-time allocation for agent-driven performance tuning. Pieces exist separately. Evidence that agents overstate speedups *from timing noise* (vs. hacking/baselines) is thin — this is both the opportunity and the main risk.

Closest work:
- AutoTuneBench (arXiv 2609.18123, 2026): trustworthy measurement for agent auto-tuning of LLM serving engines; paired-seed stats, 5% CV cap, pre-registration; abstract mentions no CIs/sequential/multiplicity. **Closest threat — read full text.** https://arxiv.org/abs/2609.18123
- Hu & Tang, Winner's Curse in LLM Self-Improvement Loops (arXiv 2610.09239, Oct 2026): keep-if-better as selection under noise; prompts, not code. https://arxiv.org/abs/2610.09239
- SIREN, Xu et al. (arXiv 2605.05973): winner's-curse correction in adaptive benchmarking; non-sequential. https://arxiv.org/abs/2605.05973
- Hsu & Shekhar, Efficient Sequential Evaluation of LLMs (arXiv 2607.17409): confidence sequences for capability eval. https://arxiv.org/abs/2607.17409
- Pilditch, Bayesian optimal stopping for LLM evals (arXiv 2608.14425). https://arxiv.org/abs/2608.14425
- TUNA (Freischuetz et al., EuroSys '25, arXiv 2503.01801): noise makes tuners pick unstable configs; heuristic fix. https://arxiv.org/abs/2503.01801
- KernelBench-Verified (arXiv 2607.16241): overclaiming via baselines/hacking. https://arxiv.org/abs/2607.16241
- R³ (arXiv 2604.11109): LLM evolutionary search + BO for kernels. https://arxiv.org/abs/2604.11109
- Hoefler & Belli, SC15 scientific benchmarking (DOI 10.1145/2807591.2807644).
- Howard, Ramdas et al., confidence sequences (Ann. Stat. 2021, arXiv 1810.08240).
- Unopened leads: Kalibera & Jones ISMM 2013; irace/F-Race; KernelBand (2511.18868); Kevin (2507.11948).

Risks: GPU timing noise may be small relative to hacking/baseline effects → "overstatement from noise" may be modest; timing samples autocorrelated (non-iid) complicates CS validity.
