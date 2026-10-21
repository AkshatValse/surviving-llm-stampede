# Related work draft: VAT (leading candidate)

Status: DRAFT, 2026-10-20 overnight. Every entry was opened by the `scout` subagent (sonnet). The tag in brackets says how deeply it was read. The main session has not independently re-opened these pages. Verify each one before it goes into `paper/` (bib entries + DOIs). Items marked *(unconfirmed)* must not be cited until checked.

## 1. Anytime-valid / statistical gating of agent changes (closest)
- **PACE: Anytime-Valid Acceptance Tests for Self-Evolving Agents.** ZayxShawn, arXiv 2606.08106, 2026. [full text via fetch summary] https://arxiv.org/html/2606.08106
  - What it does: a paired betting e-process on discordant pairs. It gives per-candidate validity and explicitly no family-wise guarantee.
  - Data and scale: binary correctness only, prompt edits, a few seeds.
  - *Our difference:* continuous timing data, FWER over K candidates, racing, systems targets.
- **The Winner's Curse in LLM Self-Improvement Loops.** Hu & Tang, arXiv 2610.09239, 2026. [~60% of full text]
  - It tests greedy, McNemar, Bayes, select-then-confirm, empirical-Bayes, and PACE gates. No rule beats greedy end to end.
  - **Key cautionary result:** we must show an end-to-end benefit, not only validity.
- **AutoTuneBench.** L. Chen, arXiv 2609.18123, 2026. [full text]
  - Kernel protocol: 25 warmup iterations, 100 reps, L2 flush. Paired seeds, a 5% CV cap, binned speedups, pre-registration.
  - Its own limitations section lists no CIs, no formal tests, and no multiplicity correction.
- **KernelBrain.** Che & Peng, arXiv 2608.02611, 2026. [full text via fetch summary] Informal successive-halving racing on mean latency, with no tests and no CIs.
- **ATTUNE.** Fan et al., arXiv 2610.17528, 2026. [abstract] Ships a change only if it clears a "noise band". How that band is computed is *(unconfirmed)*.
- **SIREN.** Xu et al., arXiv 2605.05973, 2026. [abstract] Post-search winner's-curse correction with a bootstrap and simultaneous CIs. Not sequential.
- **Efficient Sequential Evaluation of LLMs.** Hsu & Shekhar, arXiv 2607.17409. [abstract] Also **CELEUS**, Zhou et al., arXiv 2606.20820. [abstract] Both build anytime-valid CIs for a single model's score.

## 2. Kernel / code optimization agents (timing practice)
- KernelBench, Ouyang et al., arXiv 2502.10517 (2025). [abstract] Timing protocol *(unconfirmed)*.
- KernelBench-Verified, Zhang et al., arXiv 2607.16241. [~60% full text]
  - Timing: 3 warmup iterations, 10 CUDA-event trials, mean.
  - Against a TF32 baseline, the best geomean falls from 1.43× to 0.88×.
- AlphaEvolve, Novikov et al., arXiv 2506.13131 (2025). [abstract]
- robust-kbench, Lange et al., arXiv 2509.14279 (2025). [abstract]
- TUNA, Freischuetz et al., EuroSys '25, arXiv 2503.01801. [abstract] Noise leads tuners to choose unstable configs.

## 3. Benchmarking methodology
- Kalibera & Jones, *Rigorous Benchmarking in Reasonable Time*, ISMM 2013, doi 10.1145/2464157.2464160. [page] Our nearest classical precedent: valid CIs for less benchmark time.
- Hoefler & Belli, *Scientific Benchmarking of Parallel Computing Systems*, SC15. [page]
- Georges, Buytaert & Eeckhout, *Statistically Rigorous Java Performance Evaluation*, OOPSLA 2007. [PDF p.1]
- Mytkowicz et al., *Producing Wrong Data Without Doing Anything Obviously Wrong!*, ASPLOS 2009. [page] Measurement bias from setup factors, which motivates our interleaving and process/node randomization.
- Sequential and changepoint performance-regression detection:
  - Lindon, Sanden & Shirikian (Netflix), *Rapid Regression Detection in Software Deployments through Sequential Testing*, KDD 2022, arXiv 2205.14762. [abstract] The closest anytime-valid benchmarking precedent, applied to canaries rather than candidate selection.
  - Hunter, Fleming et al., arXiv 2301.03034. [abstract]; venue *(unconfirmed)*.
  - Daly et al. (MongoDB), arXiv 2003.00584. [abstract]; venue *(unconfirmed)*.

## 4. Racing, best-arm identification, confidence sequences
- F-Race: Birattari et al., 2002. [PDF] The GECCO venue is semi-confirmed.
- irace: López-Ibáñez et al., *Operations Research Perspectives* 2016, doi 10.1016/j.orp.2016.09.002. [CRAN page]
  - Its elimination tests are Friedman, t, Bonferroni-t, and Holm-t. These are fixed-level tests repeated over time, so they are **not anytime-valid**.
- lil'UCB: Jamieson, Malloy, Nowak & Bubeck, COLT 2014. [PMLR page] **It avoids the K union bound, and reviewers will ask why we pay α/K.** We should compare against it or adopt its approach.
- Howard, Ramdas, McAuliffe & Sekhon, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Ann. Stat. 49(2), 2021, arXiv 1810.08240.
- Howard & Ramdas, *Sequential estimation of quantiles with applications to A/B-testing and best-arm identification*, Bernoulli 28(3), 2022, arXiv 1906.09712. Possibly useful for a median-speedup estimand, which avoids clipping.
- Waudby-Smith & Ramdas, *Estimating means of bounded random variables by betting*, JRSSB 86(1), 2024, arXiv 2010.09686. This is the PrPl-EB CS we implement.
  - Validity holds for **any** predictable $\lambda_t\in(0,1)$. The paper requires only a conditional mean, not iid data.
  - Scout read eq. (15) as $t\log t$. We use $t\log(1+t)$, which avoids a division by zero at $t=1$. Validity is unaffected either way; only the width changes slightly. Check this against the `confseq` code.

## Positioning (one paragraph, draft)
Recent work has started to treat the winner's curse in self-improving agents and tuning loops, through post-hoc correction (SIREN), per-candidate anytime-valid gates on correctness (PACE), and careful but test-free protocols (AutoTuneBench, KernelBrain). Classical racing (F-Race, irace) eliminates candidates with repeated fixed-level tests and so has no optional-stopping guarantee. We target the systems setting, where the evidence is continuous, heavy-tailed, drifting wall-clock time. Our approach combines paired interleaved measurement with family-wise anytime-valid confidence sequences and racing. We will report both validity and benchmark-time savings, plus an end-to-end agent-loop evaluation, because Hu & Tang show that valid gates alone do not guarantee better loops.
