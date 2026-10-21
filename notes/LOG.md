# Research log

## 2026-10-20 — KV rent-or-buy pilot (direction #2): kill criterion met in small-context model
**Question:** When an agent pauses for a tool call, how close do distribution-based (Continuum-style TTL) and prediction-free (ski-rental) KV retention policies get to a clairvoyant per-call oracle, in-distribution and under tool-latency shift?
**Setup:** `configs/kvrent_pilot.yaml` on branch `pilot/kvrent` (code commit 2f15a3b; the sweep ran from a dirty tree based on 1565403, which is recorded in meta.json). Seeds 0–4, discrete-event simulation, 2 h simulated horizon, 1125 runs, 85 s wall on the M3 Max CPU. Costs are assumed A100-class numbers, not measurements. Results are in `results/kvrent_pilot/20261020-221854/` (`summary.csv`, `fig1_latency_vs_util_default.pdf`, `fig2_ratio_to_oracle_shift.pdf`).
**Result:** With η=4, below overload, the mean latency ratio to the oracle was:
- CONTINUUM_TTL: 1.002–1.004
- SKI_DET: 1.000
- SKI_RAND: 1.005–1.009
- ALWAYS_DISCARD: ~1.08–1.11
- ALWAYS_SWAP: 1.03–1.31

These ranges hold across the default, heavy-tail and shift mixes. Policies differ by more than 5% only in overload (λ=0.40) or at η=1, where seed-to-seed CIs are huge (e.g., ALWAYS_HOLD 9.57 ± 13.8). Sustained ALWAYS_HOLD utilization above ~85% was not reachable, because the system collapses through hold-and-wait.
**Verified vs. not:**
- Verified: 22 tests pass (the implementer's report), and the summary numbers come from `summary.csv`.
- Not verified: whether the model represents coding agents. Contexts are small (median 2k-token initial context), and running calls reserve most memory. Swap is always cheaper than discard under these costs. The shift test barely stresses per-tool CDFs. Rent is endogenous, and η is only a proxy for it.
**Interpretation:** Under this model, retention policy barely matters, so there is no headroom for a new policy. The pre-stated kill criterion (TTL within 5% of the oracle) is met. This is a negative result for the pilot model, not proof that the problem is solved in production, where held KV of 50–100k-token agent contexts could dominate memory. Even so, the area is crowded (Continuum, MORI, TokenCake), so it is deprioritized.
**Next:** Drop direction #2 unless the new direction search finds a sharp phenomenon in this space.

## 2026-10-20 — VAT pilot (direction #1): candidate set mis-designed; strong candidate×process variance found
**Question:** How much does noisy benchmarking inflate select-the-best speedups, and does CS-racing control false improvements at lower cost than fixed repetitions?
**Setup:** Branch `pilot/vat` (commit 30e09bc). Collection used `configs/vat_pilot.yaml`: 48 Numba 5-point-stencil candidates plus a NumPy baseline, N=2048, iters=4, 6 fresh processes × 60 paired interleaved blocks per candidate, NUMBA_NUM_THREADS=4, ~45 min on the M3 Max CPU while the machine was shared with other processes. Results are in `results/vat_collect/20261020-221946/`, `results/vat_analyze/20261020-233930/`, and `results/vat_analyze_clip16/20261020-234012/`.
**Result:**
- **(a) Protocol comparison is uninformative.** The candidate family has huge effects: 14 candidates sit at or above the +300% clip, and 12 are 55–75% slower. Clipping at log 4 therefore dominates the "inflation" numbers. NAIVE FWER was 0.84, 0.73 and 0.43 at r = 3, 10 and 40. BONF-T was ≤0.05. CS-RACE at α/48 on a 2.77-wide log range accepted nothing before 40 blocks per candidate, so it saved nothing.
- **(b) Main finding: variance components of the *paired* log-ratio** (my re-analysis, one-way random effects, unclipped):
  - Serial column-major tiled candidates (t16/t32/t64) have between-process SD 0.12–0.19 in log units and ICC 0.69–0.87. Their process-mean range is 0.29–0.42, i.e. a 35–52% swing in measured speedup depending on the process.
  - Serial row-major candidates have between-process SD 0.00–0.03.
  - By comparison, the naive within-process SE of the mean for one candidate is ~0.004, so in-session CIs would be up to ~45× too narrow for these candidates.
  - Baseline median time was 57–58 ms in processes 0–4 and 64.8 ms in process 5, which is machine-state drift.
**Verified vs. not:**
- Verified: the variance decomposition was computed directly from `timings.parquet`, and the 5 tests pass (implementer's report).
- Not verified:
  - The cause of the process effect. Hypotheses are power-of-two grid aliasing that depends on allocation address, or time-varying load from other sessions, since the processes ran sequentially.
  - The PrPl-EB implementation has not been checked against the paper's code.
  - The CS validity assumption is violated by construction (process effects).
**Interpretation:**
- The planned headline, "CS-racing saves time," is not supported by this pilot. That is mostly a design flaw: effect sizes are unrealistic and the bounded-range CS is very conservative.
- The pilot did surface a sharper phenomenon. Paired, interleaved, randomized in-session measurement does **not** remove candidate×process interaction. For some kernels the between-process variance dwarfs the within-process variance.
- Any in-session test, sequential or not, then certifies process luck. For sequential tests the false-certification probability rises toward 1/2 per null candidate, and toward $1-2^{-K}$ across K null candidates, as samples accumulate.
**Next:** A placement-offset mechanism test (`experiments/vat_alignment.py`, running now). If placement explains the effect, cheap within-session re-randomization of placement could restore validity. Then decide between this and the new direction-search workflow.

## 2026-10-21 — Prefix-cache metastability pilot (round-2 leader): REFRAME
**Question:** In open multi-turn agent serving with prefix caching on a continuous-batching engine, does FCFS have a metastable congested state above the all-miss capacity? Does hit-first LPM remove it? Does LPM-128 (SGLang's fallback) inherit the trap?
**Setup:** Branch `pilot/prefix-meta`. Experiments ran at commit 7e9704e on a clean tree; results are committed in 8e71275. `configs/prefix_meta.yaml` uses assumed A100/8B-order constants (M=300k tokens, chunk 8192, 256 max running, L0=2000, Δ=550, d=100, mean 15 turns, Exp(5 s) tools). The workflow was implement → 2 adversarial reviews (18 findings, blockers/majors fixed) → run → independent verification. The verifier recomputed every number from raw CSVs and re-ran 17 runs bit-identically. 121 tests pass. The expected REFRAME outcome was pre-registered in 9134f6c before the full runs. Results: `results/prefix_meta*/2026102[01]-*` (report in `results/prefix_meta/20261021-010411`).
**Result:**
- **E0.** λ_miss = 0.0474 sessions/s and λ_cap = 0.1156, so R = 2.44. Sensitivity runs give R = 2.25 (mid attention) and 2.44 (dead KV).
- **E1, 300 cold sessions at 1.25, 1.5 and 2× λ_miss.** FCFS, LPM, LPM-128, and AGING-LPM(10 s and 30 s) recover in 0/3 at every λ. LPM's tail hit rate is 0.19–0.23 and its queue is 280–934. FCFS-CAP with N\*=45 also recovers in 0/3. FCFS-CAP with N\*=28 (length-biased working set) recovers 3/3, 3/3 and 2/3.
  - Cap sweep: caps ≤24 recover; 28 is borderline; 32 recovers 2/0/0 of 3; caps ≥35 recover 0.
  - Cold-size sweep: every work-conserving policy recovers from 25–50 cold sessions and from none at 100 or more.
- **E2, burst of 200 at 2× λ_miss.** Hit rate over [t+10k, t+25k] is 0.000 for FCFS, LPM-128 and AGING in all 5/5 seeds; LPM gets 0.198 and CAP-28 gets 0.896. Every seed was in the good state before the burst (hit 0.93, max queue 3). Bursts of 25 recover; bursts of 100 or more trap every work-conserving policy.
- **E3, spec ramp up to 2.19×.** No hysteresis and no escapes. Above-cap runs escape near 2.9× and never re-enter.
- **E4, LPM-128 from empty.** At 2×, 0/10 runs escape in 50k s. At 3× (above cap), 10/10 escape.
**Verified vs. not:**
- Verified: every number above was recomputed from raw data, with provenance clean.
- Not verified:
  - Real-engine behaviour. Partial radix prefixes, SGLang v0.5.22's waiting-prefix LRU refresh, and vLLM's lazy block eviction are not modelled.
  - The cap N\*=28 was chosen post hoc after review scratch runs.
  - The trap mechanism diagnostic (288k of 300k reserved by running requests, 6.5k idle KV) is not in any results dir.
**Interpretation:**
- The metastability itself is real in this model. The good and congested states coexist for λ ∈ (λ_miss, ~2.4 λ_miss), and a finite burst switches the system to the congested state permanently.
- **But ordering does not help.** LPM and aging behave like FCFS once congested. The mechanism is that work-conserving admission of misses evicts the idle KV of sessions in tool calls. So "LPM-128 inherits the trap" is vacuous, because LPM is trapped too.
- Only non-work-conserving admission (a session cap within a narrow band) restores the good state.
- Engine-source check (`notes/lit/engine-sources-prefix-cache.md`): PEEK (arXiv 2607.02525) already reports scheduling-induced thrashing and the 128 fallback empirically. No paper found uses metastability or hysteresis framing, or gives a stability region for prefix-cache serving.
**Next:** Reframe the claim around admission rather than ordering. Test which deployed mechanisms (Continuum TTL pin, PEEK queued-prefix protection, CONCUR AIMD cap, length-biased static cap) restore the good state. Map the λ phase diagram, including recovery below λ_miss. Measure how escape time scales with system size.

## 2026-10-21 — Delay-EoS hedge: KILL (pre-registered)
**Question:** Under a one-step gradient delay, does Adam's preconditioned sharpness self-stabilize at η·S_P≈1 (≈2.7 with EF), and does that co-occur with the delay loss penalty?
**Setup:** Branch `pilot/delay-eos` (868d1cc code, 9810be9 results). 64-64-10 tanh MLP on digits (n=1000), Adam β1∈{0.9,0.99}, Muon-like optimizer, sync/delay/EF, full batch and B=64, η∈{3e-3,1e-2,3e-2}, 3 seeds, 144 runs. Results: `results/delay_eos/20261021-001318/`. Independently verified, including HVP vs. exact Lanczos and bitwise reruns.
**Result:** Sync Adam sits at its cap (η·S_P 37.6–39.6 vs. 38). Delayed β1=0.9 plateaus at **2.14** (η=3e-3, seeds 2.14/2.14/2.30), not at 1. EF plateaus at **4.25**, not 2.70. Delayed β1=0.99 gives 3.7–5.0. In a 1-D model the frozen-D theory holds (delay 0.955, EF 2.63), so the MLP's offset is an unexplained multi-dimensional effect. β1=0.99 *increases* the delay penalty (+3888% vs. +515%), contradicting prediction (c). Muon's penalty is smaller than Adam's.
**Interpretation:** The pre-registered GO rule fails, so this direction is killed. The post-hoc observation that delay lowers the equilibrium about 18× was not pre-registered and is not pursued tonight.

## 2026-10-21 — Prefix-meta round 3: which KV mechanisms escape metastability (sim)
**Question:** Is metastability caused by work-conserving admission rather than ordering (H1)? Do mechanisms that bound the working set restore stability (H2)? Does escape time scale with size (H3)? Is the effect robust across workloads (H4)? Predictions P1–P8 were pre-registered.
**Setup:** Branch `pilot/prefix-meta`. Pre-registration is in `configs/prefix_meta_mech_prereg.yaml` (a8b2da7, append-only amendments cb9d0ce and 2215f5e). All runs used commit 47f2859 with a clean tree; 268 tests pass.
- Policies: Continuum, PEEK and CONCUR were re-implemented from scout-extracted specs (`notes/lit/kv-mechanisms-continuum-peek-concur-wait.md`). These specs were not checked against their code.
- Results: `results/prefix_meta_{phase,mech,escape,escape_inwindow,robust}/2026102[1]-0[23]*` and report `results/prefix_meta_r3/20261021-033725` (PDFs, `prediction_eval.csv`).
- Verification: an independent verifier recomputed every flag with its own code (0 mismatches) and re-ran all experiments from `git archive 47f2859`. Outputs were bit-identical.
**Result.** The registered-first scorecard is 5 PASS / 3 FAIL.
- **P1 (FCFS recovers below λ_miss): FAIL at the registered 30k-s horizon** (0.8× 1/3, 0.9× 0/3). It PASSes at 150k s: 3/3 at ≤0.9× and 0/3 at ≥1.0×. LPM recovers up to 1.1× and fails at 1.25×.
- **P2 (PEEK-like protection does not help): PASS.** It is trapped 5/5 and recovers 0/3. In congestion it is indistinguishable from FCFS.
- **P3 (TTL pin restores stability): FAIL in every family.**
  - Only blocking pins with program priority at τ=5–10 s recover. τ=20 s fails.
  - FCFS-ordered pins and eager unpin fail.
- **P4 (length-biased cap N_lb=28): PASS, but marginal.** It recovers 3/3 at 1.5× and 2/3 at 2×, and a cap of 1.3·N_lb fails. The cliff is sharp: cap 25 recovers 3/3, 28 recovers 2/3, 30 recovers 0/3. This was a non-blind confirmation.
- **P5 (AIMD/CONCUR caps): PASS.** 3/3 at both multiples; burst-recovered 5/5.
- **P6 (price of stability small): PASS** on the measured readings. The verifier notes the ceiling sits at N=24, where the caps do not bind, so the cost of the cap was not measured.
- **P7 (escape time grows with size): FAIL as registered**, and the amended in-window design is not evaluable. At 2.25× collapses were 12/20, 0/20, 0/20 for k=1, 2, 4. The k=1 mean is 4.2e5 s; the k=2 95% lower bound is 2.2e6 s.
- λ_cap(k)/λ_miss = 1.25, 1.36, 2.41, 3.25, 4.31 for k = 0.25 → 4. The finite-size from-empty limit grows with system size.
- **P8 (robustness): PASS.** 7 of 8 workload variants hold, with R_LPM 1.84–2.72 and FCFS trapped 5/5 everywhere. decode400 fails with R=1.31.
**Verifier's post-hoc observation (not pre-registered):** congested-state throughput (closed N=300, in units of λ_miss) closely tracks each policy's recovery threshold:

| Policy | Congested throughput (× λ_miss) |
|---|---|
| FCFS | 1.01 |
| PEEK | 1.01 |
| LPM | 1.16 |
| ttl20 | 1.65 |
| lb_cap | 2.21 |
| ttl5 | 2.58 |
| AIMD | 3.01 |
| CONCUR | 3.03 |
| ttl10 | 3.32 |

**Interpretation:** Recovery happens iff λ is below the policy's congested-state throughput. This is the classical thrashing curve: open-system bistability whenever μ(∞) < λ < peak μ(n). It unifies the results:
- Ordering and PEEK leave μ(∞) ≈ λ_miss.
- Caps and well-tuned pins raise it.
- The narrow cap band is the LRU cyclic cliff in μ(n).

Novelty sits in the agent-serving application and in the evaluation of deployed mechanisms, not in the thrashing theory itself (Denning 1968).
**Harness (branch `harness/prefix-meta`, ff30257/cecc420):**
- Contents: an open-loop agent-session load generator (aiohttp), a mock engine, a canary flush check, analysis, DRAFT SLURM scripts for SGLang v0.5.22 and vLLM v0.32.0 on one A100, and `notes/NOVA_PLAN_prefix_meta.md`.
- 189 mock tests pass. Nothing has been verified against a real engine, and nothing was submitted.
**Next:** Round 4 makes quantitative fluid predictions from measured closed-population μ(n) curves. It also covers eviction policy versus cap robustness and the size scaling of λ_cap toward the fluid μ\*. Then real-engine validation on Nova, which needs Akshat's approval.

## 2026-10-21 — Prefix-meta round 4: thrashing curves and fluid predictions (sim)
**Question:** Does the measured closed-population curve μ(n) quantitatively predict the open system: critical burst, recovery threshold, and the cap band? Does eviction order (LRU, RANDOM, MRU_IDLE) explain the cliff?
**Setup:** Branch `pilot/prefix-meta`.
- **Pre-registration:** `configs/prefix_meta_r4_prereg.yaml` (db30e76). Amendment 1 (7f9c77d) was committed before all full runs and relabels R3 as non-blind after review. Amendment 2 (67467dc) was written post-run, is disclosed, and adds one post-hoc row.
- **Runs:** at 01252cd from a clean tree. Seeds are fresh: curve 2000–2002, burst 2100–2104, cap 2200–2202.
- **Tests:** 360 pass.
- **Verifier:** recomputed everything with its own code and re-ran all 761 cells bit-identically from `git archive`. It found one undisclosed scratch look (`s3/little.py` on unregistered seeds). That look had negligible impact.
- **Results:** `results/prefix_meta_r4_{curve,burst,burst_info,cap}/20261021-05*` and report `results/prefix_meta_r4/20261021-051550`.
**Result** (units of λ_miss; registered readings):

| | Verdict | Numbers |
|---|---|---|
| R1 | PASS, coin flip | n\*=22 (n=20 is statistically equal), μ\*=4.07. The tail max at n≥1.5n\* is 1.186, against a limit of 1.2. Bootstrap P(pass)=0.64. |
| R2 | **FAIL** | RANDOM/LRU at n=33 is 1.018 (limit 1.25). The largest ratio anywhere on the grid is 1.034, and 1.053 for MRU. |
| R3 | PASS, fragile | b_c=20.5, b_emp=40, ratio 0.512 (limit 0.5). The t-interval on b_c crosses the verdict boundary. Seed 2103 is trapped even with no burst; excluding it (post hoc) gives a ratio of 0.256. At 1.5× the ratio is 0.31 (would FAIL). |
| R4 | PASS (non-blind) | r_FCFS=0.989 and r_LPM=1.136, consistent with the round-3 brackets. The FCFS half is nearly an identity. |
| R5 | **FAIL** | Every eviction rule recovers 3/3 at caps 24 and 28, and 0/3 at caps 32, 36 and 40. Eviction counts are within 2% across rules. |
| R6 | PASS | ρ = 0.41, 0.59, 0.69 for k = 0.5, 1, 2. The beyond-null test fails, because c(k) rises with k. |

**Mechanism** (from the curve table):
- At n≥40, KV reserved by running requests fills about 284–286k of the 300k tokens, and idle KV is about 6–9k tokens.
- **The cliff is reservation crowd-out under admission, not LRU's cyclic pathology.** Eviction order has nothing left to choose from. This refutes my Claim 3′ conjecture (THEORY_prefix_meta).
- Noise-driven escapes happen well below the fluid saddle-node. 1/5 seeds trap with no burst at 2×, and 2/5 at 2.5×. The measured λ_cap(1) is 2.41, against a fluid μ\* of 4.07.
**Verified vs. not:**
- Everything above is verified (independent recompute plus full re-run).
- **Not verified, and the key threat:** the simulator reserves the full end-of-turn context at admission. That is an upper bound on what paged engines hold. vLLM allocates on demand and preempts; SGLang reserves via `new_token_ratio`, an estimate of max-new-tokens (from memory, so check this). The crowd-out mechanism may be weaker on real engines.
**Interpretation:** The story is now coherent and simpler.
- Admission crowd-out makes μ(n) sharply unimodal.
- Congested throughput μ_∞ predicts recovery. FCFS gets 0.99 and LPM 1.14.
- Caps at or below the curve's peak, roughly 20–28 sessions, restore stability regardless of eviction policy.
- The fluid model gives qualitative structure and recovery thresholds. It does **not** predict burst sizes or noise-driven escape reliably.
**Next:** Real-engine test with the referee's paired-arm design, measuring real μ(n) first. Add a simulator sensitivity run with on-demand allocation and preemption (no full reservation) before Nova, to see whether the cliff survives.
