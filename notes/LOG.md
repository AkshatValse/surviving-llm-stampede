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

## 2026-10-21 — Real-engine harness: referee-requested kill-test redesign (no runs)
**Setup:** Branch `harness/prefix-meta`. Code is at f1f001e and recorded outputs at 2f22e08. Workflow: implement, adversarial review (11 findings), fix. 307 mock tests pass (`results/agentload_tests/20261021-070445` in that worktree). **Nothing was sent to Nova or any real engine.**
**What changed:**
- **Stage C:** closed-population μ(n) measured on the real engine before anything else.
- **Paired arms:** BURST, NOBURST, and CAPPED (a client-side FIFO session gate at the measured argmax n), all with common random numbers.
- **Pre-registration:** a template plus enforcement. A decisive verdict requires a committed prereg file bound by sha256.
- **Trap criterion v2.**
  - The reviewer found that the first version's session-rate test fired on 0% of the simulator's own traps at 2× and 2.5× λ_miss. Trapped systems complete young sessions faster than the closed λ_miss, which would have biased the test toward a false KILL.
  - The criterion now compares uncached prefill tokens/s with E0a's all-miss rate. On the 84 simulated traps it fires 100% of the time.
  - Weak spot: (a and b) is only 69% at 1.5×, which affects the `slope_frac` decision.
- **Recovery threshold:** registered as λ_miss. μ(300) from a short synchronized start is biased by up to +70%, so it is now only a check.
**GPU-h** (plan arithmetic, not measured):
- The cheap stages before pre-registration total about **26.6**: S0 1.68, C 8.47, E0a 7.24, E0b 9.22.
- The paired kill test is about 75.8.
- The total plan is about 236.
**Open:** The ±15% token band has only been validated on the simulator. `slope_frac` is still to be decided. Staggered starts for Stage C are not implemented.

## 2026-10-21 — Prefix-meta round 5: does metastability survive realistic KV allocation? (sim)
**Question:** Is the collapse an artifact of reserving each request's full end-of-turn KV at admission?
**Setup:**
- Branch `pilot/prefix-meta`.
- Pre-registration `configs/prefix_meta_r5_prereg.yaml` (e24e3cd), with amendments 7ab10f4 and 12459fc. All amendments are append-only and were committed before the registered runs.
- Runs at 12459fc on a clean tree; results committed in 44dd21f. 546 tests pass.
- Engine semantics come from a scout's summarized read of the vLLM v0.32.0 and SGLang v0.5.22 sources (`notes/lit/engine-alloc-semantics-vllm-sglang.md`). They are unverified.
- Modes:
  - ONDEMAND_PREEMPT (vLLM-like): admission requires the full prompt to fit; decode grows per step; on OOM the last-running request is preempted with recompute, and its KV is trimmed tail-first.
  - RATIO_RESERVE (SGLang-like): new_token_ratio 0.7 decaying to 0.098, with retraction on decode OOM.
- Verifier: recomputed everything from raw data (stdlib only) and re-ran sample cells bit-identically from `git archive`.
- Results: `results/prefix_meta_r5_{calib,curve,burst,cap}/20261021-070[3-4]*`, report `results/prefix_meta_r5/20261021-070550`.
**Result:**
- S1–S4 PASS in both modes (registered readings). KILL is FALSE.
- Thrashing curve (λ_miss units):

  | Mode | μ\*/μ(300) | μ(300) FCFS | Max deviation from FULL_RESERVE |
  |---|---|---|---|
  | ONDEMAND | 4.07 | 0.977 | 1.2% |
  | RATIO | 4.10 | 0.972 | 3.3% |

  - n\*=20 in every mode.
  - FCFS hit rate at n=300 is exactly 0.
- Burst 200 at 2×: 5/5 not recovered. No-burst: 5/5 good.
- Cap at n\*=20: 3/3 recover; no cap: 0/3.
- LPM advantage over FCFS: 0.157 and 0.192 λ_miss.
- Preemption is 0.002–0.008 per admitted turn.
**Variants:**
- `ondemand_first_chunk` (an alternative reading of vLLM admission): heavy preemption thrash (0.18–0.49 per turn) and λ_miss −28%. The absolute collapse is unchanged, but the normalized C1 fails, so the verdict is "mixed".
- `lpm128` (SGLang's FCFS fallback above 128 waiting): the LPM advantage is about 0 with hit rate 0. In congestion, **deployed SGLang LPM behaves like FCFS**.
**Verified vs. not:**
- Verified: everything above.
- Caveats:
  - Not a severe test. The pre-registration predicted the null, and the reservation excess is only about 2–4% of M.
  - Real-engine semantics are summarized from source, not verified.
- **Untested and probably larger gaps:**
  - Whole-session all-or-nothing eviction, versus block-wise or radix-leaf eviction with partial prefix hits.
  - Long-decode workloads (d-sweep).
**Interpretation:** The reservation-artifact threat is retired *in simulation*. The mechanism is idle-KV crowd-out, which full reservation only marginally amplifies. Partial-prefix eviction is the remaining simulator-side threat. It is best settled on the real engine (Stage C, measured μ(n)) rather than by more simulation.
**Next:** Real-engine Stage C, pending Akshat's approval. Optionally, a round-6 simulation adds block-level partial-prefix eviction plus a d-sweep.

## 2026-10-21 — Decision: direction approved
**Decision (Akshat, in chat):** pursue prefix-cache metastability in agent serving. Akshat will run the "Needs Akshat" commands first (account and QoS, quotas, modules, HF reachability). Next I prepare the Stage 0 smoke job and show the exact sbatch before any submission.
**Next:** review the Stage 0 smoke scripts on `harness/prefix-meta`. List the prerequisites: env build and model weights, both needing approval. Draft the exact submission.

## 2026-10-21 — Nova setup (steps A–C) done; Stage 0 smoke submitted
**Authorization:** Akshat said "Just get everything done" after reviewing the runbook (steps A–D).
**Read-only checks (via SSH):**
- **Account:** verified. `f2026.coms.6250.02` with QoS `instruction,scavenger`.
- **Storage:** class storage `/work/classtmp/avalse/swapp`. ISU deletes it at semester end. Details are in CLAUDE.md.
- **Internet:** compute nodes have outbound access (pypi and huggingface returned HTTP 200 from nova22-25).
**Step A:** the `harness/prefix-meta` git bundle was cloned to `/work/classtmp/avalse/swapp/repo` at fea94d1, clean tree.
**Steps B+C:** CPU job **17059856** (`slurm/setup_nova.sbatch`, account 6250, nova22-25) COMPLETED 0:0 in 18:54.
- ENV_GEN: Python 3.11, aiohttp 3.14.5, numpy 2.4.6, pandas 3.0.6, huggingface_hub 2.2.0.
- ENV_SGLANG: sglang 0.5.22 with torch 2.14.1+cu130 (a CUDA 13.0 build, which needs driver ≥ 580).
- Model: Qwen/Qwen2.5-7B-Instruct at revision a09a35458c702b33eeacc393d103063234e8bc28 (14 GB).
- Lock files: `/work/classtmp/avalse/swapp/envs/*.lock.txt`.
- **Version check:** ENV_GEN's pandas 3 / numpy 2 differ from local (pandas 2.2 / numpy 1.26). All 113 parser/workload/config/analysis tests pass on Nova's env, run on the login node with nice, under 1 min.
**Step D:** smoke job **17060003** submitted (1×A100, 1.5 h, account 6250). It was PENDING (Resources) at submission.
- **Smoke attempt 1, job 17060003:** FAILED after 28 s on nova22-gpu-3 (A100 80GB PCIe, driver 580.178.04, CUDA 13.0). The pre-launch flag check reported every SGLang flag missing, so the server never started and less than one GPU-minute was used.
  - Cause: a bug in my harness, not in SGLang. `help_has_flag` piped `printf` into `grep -q` under `set -o pipefail`. SGLang 0.5.22's `--help` runs to about 2700 lines, more than the pipe buffer, so `grep -q` exits at the first match and `printf` gets SIGPIPE, failing the whole pipeline.
  - Fixed in 636da1b with a here-string, plus a regression test that fails on the old code and passes on the fix.
  - Verified on the real captured help: all 11 required flags plus `--sampling-defaults` are found.
  - SGLang notes `python -m sglang.launch_server` as still supported; `sglang serve` is the recommended entrypoint.
- **Smoke attempt 2, job 17060022:** submitted with the same command.
- **Smoke attempt 2, job 17060022:** FAILED after 1:49 on nova22-gpu-1. This time every flag passed.
  - What worked:
    - The model loaded.
    - **The KV pool was allocated at exactly 300,000 tokens (K and V 8.01 GB each), so the cap is honored.** That is plan item (f).
    - 48 GB of GPU memory was still free after the pool.
    - Peak host RSS was 20 GB.
    - The context-length override to 49152 was accepted with a warning: "greater than the derived context_length (32768)". That is plan item (e), partly verified.
  - Why it died: FlashInfer's JIT, during prefill CUDA-graph capture, raised `FileNotFoundError: 'ninja'`. The env is never activated, so its `bin/` was not on PATH.
  - Further problem: FlashInfer links with `-L$CUDA_HOME/lib64{,/stubs} -lcudart -lcuda`, but the pip CUDA 13 toolkit ships `lib/` with only versioned `.so` files and no libcuda stub.
  - Fix (7cc31fb):
    - `slurm/make_cuda_shim.sh` builds a symlink-only `CUDA_HOME` at `/work/classtmp/avalse/swapp/cuda13-home`. nvcc 13.4.92 resolves through it, `libcudart.so` points to the pip runtime, and `stubs/libcuda.so` points to `/usr/lib64/libcuda.so.1`, the node's driver 580.
    - The launcher exports the env's `bin/` and the shim, and points the FlashInfer/Triton JIT caches at class storage.
    - A fail-fast pre-launch toolchain check was added.
    - `ATTN_BACKEND=triton` is available as a fallback. Not used yet, because FlashInfer is SGLang's A100 default.
- **Smoke attempt 3, job 17060085:** submitted with `CUDA_HOME_SHIM` set.
- **Smoke attempt 3, job 17060085:** FAILED after 1:04. The toolchain checks passed (ninja, nvcc, shim libraries) and FlashInfer started its JIT build. Every kernel then failed with `#error "CUDA compiler and CUDA toolkit headers are incompatible"`.
  - Cause: the `sglang[all]` resolve mixed CUDA minor versions across the split pip toolkit. Torch's runtime is 13.0, but the compiler-side wheels resolved newer:

    | Wheel | Resolved | Pinned to |
    |---|---|---|
    | nvidia-cuda-nvcc | 13.4.92 | 13.0.88 |
    | nvidia-nvvm (cicc) | 13.4.92 | 13.0.88 |
    | nvidia-cuda-crt | 13.4.92 | 13.0.88 |
    | nvidia-cuda-cccl | 13.3 | 13.0.85 |
    | nvidia-cuda-runtime | 13.0.96 | (unchanged) |

  - Fix: the four compiler-side wheels were pinned on the login node, run with `nice`. `pip check` is clean.
  - Verified on the login node: a test `.cu` that includes FlashInfer's CCCL and cub compiles for sm_80 (COMPILE_OK). An intermediate attempt that pinned only nvcc failed with `ptxas: Unsupported .version 9.4`. torch still imports.
  - The pins are now in `setup_nova.sbatch` (bbb6a12) so a rebuild reproduces them.
- **Smoke attempt 4, job 17060165:** submitted.

## 2026-10-21 — Stage 0 SGLang smoke: PASSED (job 17060165)
**Setup:**
- Engine: SGLang 0.5.22, Qwen2.5-7B-Instruct at revision a09a3545…, FCFS, 300k-token KV cap, `--context-length 49152`, FlashInfer backend.
- Hardware: one A100 80GB PCIe on nova22-gpu-1, account `f2026.coms.6250.02`.
- Harness bbb6a12. Closed population of 32 sessions for 1800 s, synthetic output feedback (smoke auto mode).
- Pulled read-only to `results/nova/s0_smoke_17060165_pulled_20261021-152347/`.

**Result:** COMPLETED 0:0 in 32:26. Healthy after 101 s, which includes first-time FlashInfer JIT and 61 s of CUDA-graph capture.

| Plan §4 item | Status | Detail |
|---|---|---|
| (a) flags | verified | all present |
| (b) cached tokens | verified | `usage.prompt_tokens_details`; repeated prompt 63/64 cached |
| (c) output token ids | verified | `choices.0.token_ids` |
| (d) metrics | verified | 90 names |
| (e) context > 32k | verified | up to 40,350 tokens, no errors |
| (f) KV cap | verified | exactly 300,000 |
| (g) prompt-token agreement | verified | 0 mismatches over 3191 requests |
| (h) flush | verified | canary 1023 → 0 cached tokens |
| (j) hardware | verified | A100 80GB PCIe, driver 580.178.04 |
| (l) request fields | verified | accepted |
| (m) node classes | open | nova22-amp-7 excluded and untested |
| run-to-run gap | open | not yet measured |

- Run counts: 236 sessions started, 204 completed, 0 failed; 3191 requests OK, 0 errors. 0 retractions.
- KV usage: mean 0.61, peak 0.99. Queue: mean 7.4, peak 23.
- First 1000 s window: 0.69 of follow-up turns had more than 50% of tokens cached; token hit rate 0.57.

**Interpretation:** the harness and engine path work end to end, and every precondition for Stage C is met. Decision: pin `OUTPUT_FEEDBACK=server` for all SGLang cells. With 32 closed sessions the engine is memory-pressured, with partial hits. That is consistent with the simulator's μ(n) peak near n≈20–22, but it is **not** a measurement of μ(n).

**GPU cost of Stage 0 so far:** about 0.55 GPU-h for the passing job, plus about 4 GPU-min across the three failed attempts.

**Next:** Stage C, the closed μ(n) on the real engine. Awaiting Akshat's OK.

## 2026-10-21 — Stage C submitted: real closed-population μ(n) on SGLang
**Authorization:** Akshat approved the three Stage C jobs in chat: OUTPUT_FEEDBACK=server, 300k-token KV cap.

**Setup:**
- Harness 89a3c7d, synced to the Nova clone.
- Each job: 1×A100, 4 h limit, account `f2026.coms.6250.02`.
- MODE=closed: one run per n. Each run is 900 s of warmup plus 1800 s measured, with a flush and canary-verify between runs.

| Job | Policy | n values |
|---|---|---|
| 17062103 | FCFS | 16, 20, 24, 32 |
| 17062104 | FCFS | 48, 96, 300 |
| 17062105 | LPM | 48, 300 |

**Plan arithmetic:** about 8.5 GPU-h.

**Analysis plan.** The real λ_miss is not measured yet; that is E0a. So the comparison with the simulator is on shape:
- the peak location n\*;
- the collapse ratio μ(300)/μ\*;
- hit rate against n;
- the LPM tail versus the FCFS tail.

Known bias: μ(300) is biased upward because all sessions start at the same time and the run is short. It serves only as a check (see the harness review).

## 2026-10-22 — Stage C: the real-engine closed-population thrashing curve (SGLang)
**Question.** On a real engine, does the closed-population throughput μ(n) for this agent workload have the simulator's unimodal shape with a cliff, and an all-miss collapse caused by KV crowd-out?

**Setup.**
- Jobs 17062103, 17062104 and 17062105, all COMPLETED 0:0. Total wall time 7.3 GPU-h.
- Hardware: three A100 80GB PCIe nodes (nova22-gpu-1, gpu-3, gpu-2) on account `f2026.coms.6250.02`. Harness commit 89a3c7d.
- Engine: SGLang 0.5.22 serving Qwen2.5-7B, with a 300k-token KV cap, FlashInfer, and `OUTPUT_FEEDBACK=server`.
- Protocol: one closed run per n, seed 0, 900 s warmup plus 1800 s measured. The canary check passed for all 12.
- Data pulled read-only to `results/nova/stageC_1706210x_pulled_20261022-125454/`. Harness analysis is in `analysis_local/…/20261022-125619/`.
- Verification ran as a 4-agent workflow; reports are in `notes/STAGEC_VERIFICATION.md` and scripts in `verification/`.

**Result (sessions/s).** "Hit" is the fraction of turns with more than 50% of tokens cached. "SE" is the batch-means standard error over 300 s bins and understates uncertainty where bins are autocorrelated.

| Policy | n | μ (sessions/s) | Hit | Engine cached share | Note |
|---|---|---|---|---|---|
| FCFS | 16 | 0.176 | 0.93 | | |
| FCFS | 20 | 0.224 | 0.93 | | |
| FCFS | 24 | 0.233 | 0.89 | | turns-based 0.226 ± 0.019 SE; contains one degraded excursion |
| FCFS | 32 | 0.115 | 0.51 | | mixes regimes: degraded about 450–2400 s, then recovered to hit 0.80 |
| FCFS | 48 | 0.049 | **0.000** | 0 of 20.0M tokens | |
| FCFS | 96 | 0.061 | 0.000 | | |
| FCFS | 300 | 0.108 | 0.000 | | |
| LPM | 48 | 0.087 | 0.385 | | rising 0.28 → 0.44; not stationary |
| LPM | 300 | 0.105 | 0.000 | | queue 269 > 128, so SGLang's LPM has fallen back to FCFS |

**Verified.** Three sources agree that hit is 0 at n≥48: client usage, engine Prometheus counters, and server-log prefill lines. Nothing in the runs points to a fault:
- Eviction survival is about 3–6 s against a 31–66 s reuse gap, so this is real LRU thrash.
- Prompt continuity is exact (cached = prompt − 551), and every response returned server token ids.
- There were 0 errors and 0 retractions.

Comparison with the simulator's FCFS curve:
- Hit fractions at n≤24 match within 0.01.
- The 0.5-hit crossing is at about 32.2 (simulator about 30.6).
- The peak is at n≈20–24 (simulator 20–22).

**Corrections and caveats.**
- The tail ordering μ(48) < μ(96) < μ(300) is a **synchronized-start transient**, not a property of the system. The throughput-implied all-miss floor is roughly flat at 0.072–0.081 sessions/s, so the real collapse is about 3× (μ\*/floor), not 4.5×. At n=300, in-flight prompts are only 71% of the stationary length.
- Real/simulator μ ratios range from 1.1 to 2.3, because the simulator's constants were assumed. The shape matches; the levels do not.
- One seed per n. The n=32→48 step crosses nodes. The server seed was not pinned.
- The critic's main point: the cliff location follows from memory alone (n_fit = M / E_lb = 28.4). That is Denning's thrashing curve. Novelty therefore has to come from metastability and hysteresis in the open system, from degraded episodes below n_fit, and from the evaluation of the mechanisms that are actually deployed.
- The degraded-then-recovered episodes at n=24 and n=32 hint at metastable switching. They may also be start-up cohort artifacts, since each run has a single seed.
- "Deployed LPM falls back to FCFS and therefore loses its benefit at n=300" still rests on reading the code. At n=300 the pool may be oversubscribed whatever the ordering. Testing it needs a patched-threshold run.

**Interpretation.** The simulator's mechanism transfers qualitatively, and partly quantitatively, to a real engine. The thrashing curve is real. The metastability claim is not tested yet.

**Next** (critic's ranking by information per GPU-hour; each needs Akshat's OK):
1. All-miss calibration (E0a) at the stationary mix: about 1 GPU-h.
2. Replicates plus a hysteresis test at n ∈ {24, 28, 32}, 3 seeds, one node, server seed pinned, with an injected eviction burst: about 10 GPU-h.
3. Staggered (pre-aged) starts. Needs harness work first.
4. M-scaling, including the native pool: about 5 GPU-h.
5. Patched-threshold LPM to test causality: about 4 GPU-h.
6. Then E0b, pre-registration, and the paired-arm open-system kill test.

## 2026-10-22 — Local (M3 Max) round 6 launched: calibrate the simulator from engine timing, then make blind predictions
**Why.** Turn the simulator from a qualitative match into an out-of-sample quantitative test of the real engine.

**Design.** Fixed in workflow `sim-calibration-predictions` (run wf_62e1fc6c-410). The prompts were frozen at launch, before any E0a/E0b/E2 result existed.
1. **Calibrate.** Fit the iteration-time cost model *only* from SGLang server-log per-batch timing (Stage 0 and Stage C logs), using the metric definitions read from the SGLang source. It is not fitted to μ(n).
2. **Add an SGLang-faithful batching mode.** SGLang runs prefill and decode as separate iterations with prefill priority (`enable_mixed_chunk=False`). The default mixed mode stays bit-identical.
3. **Validate.** Compare the simulated μ(n) and hit fraction against real Stage C, out of sample, using the same protocol: synchronized start, window [900, 2700).
4. **Make blind predictions.**
   - (B1) E0a λ_miss and the all-miss token rate.
   - (B2) E0b from-empty stable fractions per multiple.
   - (B3) E2 per-arm TRAPPED / RECOVERED / PASS at λ ∈ {1.3, 1.6, 2.0, 2.4}× the predicted λ_ref, in both absolute and relative units.
   - (B4) Native-pool curves at M = 600k and 900k.
5. **Verify independently,** including a check that no data leaked in.

**Blindness rule.** The agents may read only Stage 0/C data and SGLang source. They are forbidden from Nova `results/` and `logs/`, and from squeue/sacct. The main session will not change the workflow after any E0a/E0b/E2 result appears. Predictions count as blind if the PREDICTIONS.md commit timestamp precedes the corresponding real result, or if the agents demonstrably could not access it.

## 2026-10-23 — E0a: the real all-miss capacity λ_miss (SGLang, prefix cache disabled)
**Question:** What is the all-miss capacity λ_miss (sessions/s) of Qwen2.5-7B on one A100 80GB PCIe under the agent workload, and is it stable across seeds and population size?

**Setup:**
- Nova jobs 17072634 (POP=32, seed 0), 17072635 (seed 1), 17072636 (seed 2), 17072637 (POP=64, seed 0), all COMPLETED 0:0 on nova22-gpu-1, about 49.5 min each (1.5 h limit), account `f2026.coms.6250.02`. Submitted 2026-10-22 by the previous session.
- Harness at old commit 89a3c7d (= 69e91de after the history rewrite), MODE=miss, `--disable-radix-cache`, engine label `sglang-nocache`, `OUTPUT_FEEDBACK=server`, `KV_TOKENS=300000`, config `configs/agentload_e0_miss.yaml`: closed population, 2700 s per run, analysis window [900, 2700).
- Data pulled read-only to `results/nova/e0a_1707263x_pulled_20261023-142037/` (run dirs, per-job analyses, job logs). Combined 3-seed calibration: on Nova `results/agentload_analysis_miss/20261023-142433/calibration.json` (login node, nice), bit-identical to the local run in `.../analysis_local_combined/`. Copied to `prereg/inputs/2026-10-23/calibration.json`.
- The per-bin and token-based checks are the scripts `e0a_bins.py` and `e0a_tok.py` in `analysis_local_combined/`.

**Result (window [900, 2700) s, 1800 s measured):**

| Run | POP | seed | sessions | turns | λ sessions/s | λ turns-based | uncached tok/s |
|---|---|---|---|---|---|---|---|
| 17072634 | 32 | 0 | 102 | 1709 | 0.0567 | 0.0643 | 11076 |
| 17072635 | 32 | 1 | 147 | 2053 | 0.0817 | 0.0773 | 11342 |
| 17072636 | 32 | 2 | 138 | 1940 | 0.0767 | 0.0730 | 11312 |
| 17072637 | 64 | 0 | 98 | 1796 | 0.0544 | 0.0676 | 11431 |

- Combined (3 × POP=32): λ_miss = 0.0717 ± 0.0076 (SE over seeds), **λ_miss_turns_based = 0.0715 ± 0.0038**, all-miss uncached prefill rate **11243 ± 84 tok/s**. Max cached tokens 0 in every run; guards report 0 errors.
- **Runbook checks.** (i) Seeds within 5%: **fails for the session rate** (0.057–0.082, ±17% around the mean) and for turns-based (±9%); **passes for the token rate** (±1.2%). (ii) POP=64 within 5% of POP=32: token rate +3.2% vs seed 0 (inside the seed spread), session rate −4%; saturation confirmed. (iii) No trend across the six 300 s bins: the token rate is flat in all four runs (OLS |t| ≤ 1.4), but the turn and session rates trend within runs (seed 0 falling, t = −2.7 and −2.9; seed 1 rising, t = 5.4 and 3.2; seed 2 flat; POP=64 turns falling t = −3.3).
- **Cause of the spread:** in-flight composition. Prompt length is exactly 2000 + 650(k−1) tokens at turn k (zero residual), so a session's all-miss work is W(T) = 2000T + 325T(T−1), heavy-tailed in T. The mean turn index of in-window requests was 15.9 / 13.2 / 14.1 for seeds 0/1/2 (mean n_turns of those requests 31.1 / 25.1 / 28.2), so seed 0 spent its window on deeper, costlier turns. The engine is token-bound; session counts over 1800 s are a small sample of a heavy-tailed quantity.
- **Token-based cross-check:** with E[T] = 14.761 and E[W] = 154,529 tokens per session (exact, geometric(1/15) capped at 60), λ_tok = 11243 / 154529 = **0.0728 sessions/s** (per seed 0.0717–0.0734). It agrees with the turns-based mean within 2% and has a CV under 1%.

**Verified vs. not:** Verified: job states and exit codes (sacct), 0 cached tokens, local and Nova combined analyses identical, the deterministic prompt growth, the bin trends. Not verified: whether a longer window would shrink the session-rate spread (expected, not measured); the server seed was not pinned; one node for all four runs.

**Interpretation:** λ_ref for E0b and E2 stays `lambda_miss_turns_based` = 0.0715 sessions/s as pre-planned; the three estimators agree at the mean (0.0717 / 0.0715 / 0.0728) and the pre-registration's 10% boundary margin covers the SE (5%). The value sits at the low end of the Stage C throughput-implied floor (0.072–0.081). The seed check "fails" only because sessions/s is the wrong unit for a token-bound regime; report the token rate as the primary all-miss capacity in the paper and sessions/s as derived.

**Next:** E0b, six one-run jobs at 1.25–3.0 × λ_ref with `CALIB_FILE=results/agentload_analysis_miss/20261023-142433/calibration.json` (authorized 2026-10-22: "submit everything you think is best"). Then pre-registration from `prereg/inputs/2026-10-23/`.

## 2026-10-23 — [redacted: unrelated unpublished project, cluster-wide accounting data; see provenance/REDACTIONS.md]

## 2026-10-23 — Round 6 resumed as a Sonnet workflow; Stage 1 done, Stage 2 interrupted by the machine transfer
**Question:** Can the interrupted round-6 work (SGLang-faithful separate batching; calibrated-simulator validation; blind predictions) be completed before E0b results are read?
**Setup:** Workflow `r6-blind-predictions` (script frozen in `notes/workflows/r6-blind-predictions.js`), four Sonnet stages in isolated worktrees cut from `bf20ed4`, forbidden from ssh, from `results/nova/e0a_*`, and from LOG entries dated 2026-10-23+.
**Result:** Stage 1 (Port) finished: commit `772b08f` on `r6/separate-batching` adds `engine.batching: mixed | separate_prefill_priority` (mixed default bit-identical; refused with `ondemand_preempt` and with k-scaling); full suite 1019 passed, 0 failed, 1 skipped (agent-reported; not re-run by the main session). Stage 2 (Validate) committed its harness (`1cdec96` on `r6/validation`) and was interrupted mid-implementation; its uncommitted edits were committed as WIP `58451c8` (unreviewed, tests not run). Stages 3–4 did not start. Both branches pushed.
**Verified vs. not:** Verified: the commits exist and are pushed. Not verified: the 1019-test count, the separate-batching semantics, anything in the WIP commit.
**Interpretation:** No real E0b/E2 data was read by any agent (E0b was still running). Blindness for B2 is still achievable if predictions are committed before E0b results are pulled; see STATE → HAND-OFF.
**Next:** on the PC, resume at Validate; or pull E0b and log B2 as non-blind.

## 2026-10-24 — Round 6 finished on the PC: Stage C validation, blind predictions B1–B4, independent verification
**Question:** Does the timing-calibrated simulator (cost model fitted to SGLang server-log timing only) reproduce the real Stage C μ(n) out of sample, and what does it predict, blind, for E0a, E0b, E2 and the native pool?
**Setup:** Workflow `r6-blind-predictions-pc` (run wf_0a9e7d81-acb; the frozen laptop prompts adapted to the PC), Sonnet agents in worktrees `Nova-Research-wt/{validate,predict}` on `r6/validation`, forbidden from ssh, from the main checkout and from `results/nova/e0a_*`/`e0b_*`. Validate: reviewed the unreviewed laptop WIP (`58451c8`), fixed three report-code defects (`cda0314`) before the registered run, ran the declared spec `configs/r6_validate_stagec.yaml` unchanged (663 runs, 79 s), wrote `calibration/round6_server_log_fit/VALIDATION.md` (`813cfc1`). Predict: committed its spec, driver and tests before any prediction run (`630ab9e`), ran B1–B4 in both batching modes (48 calls, 4 min 39 s), wrote `notes/PREDICTIONS.md` (`64bc4e3`, 03:49 CDT; tag `r6-predictions-frozen`, pushed to GitHub 14:53 CDT, before any E0b result was read). Verify: the Sonnet verifier hit the session limit at launch; a Codex session Akshat had started as a stand-in did the Verify stage (six reruns, independent stdlib recomputation of all 78 B2 and 126 B3 classifications, a diff-wide leak scan) and committed `notes/PREDICTIONS_VERIFICATION.md` append-only (`877b936`). Merged into `main` (`78ebbee`).
**Result:** Validation: the declared level test is **NO** in both modes. Mixed is within 15% of the real μ_sessions in 7/8 judged cells and fails FCFS n=48 (+42%); separate is 6/8 (also LPM n=48, +26%). The plateau (n=16–24) and the n=300 tail match; the shape matches (0.5-hit crossing 32.5 mixed vs 32.2 real; collapse ratio 0.50 vs 0.46). Mixed is closer on the pre-declared metric (0.104 vs 0.127), a margin carried by LPM n=48 alone; against the turns-based real estimator both modes are within 15% in 7/8 cells. Predictions (primary = mixed): **B1** λ_miss(turns) 0.0722 sessions/s, all-miss 11 220 tok/s; **B2** from-empty all-stable edge 0.14 sessions/s with 3 seeds (0.15 with 20 seeds), a soft transition from 0.15 to 0.20; **B3** the E2 kill test PASSES at every λ in 0.09–0.16 in both modes, fragile at 0.09 (slope margin) and 0.16 (NOBURST 15/20); **B4** a larger pool lifts the plateau (n=24: 0.226 → 0.254). Verification: every rerun matches exactly; every classification recomputes; no leak found; B1 < B2 edge < B4 peak holds; **strict containment fails** (B3 PASS at λ = 0.16 lies above the B2 all-stable edge, explained by B3's ≥ 2/3-seed rule and longer horizon, not a code defect).
**Verified vs. not:** Verified by the main session: the commit order and times (reflog), the GitHub push of the tag before E0b was read, that no Codex or Claude session ran ssh/scp/sacct or read E0b before then, the merged full suite (the 32 documented Windows-only failures, none new). Not verified by the main session: the agents' tables beyond reading them (Codex re-derived them). The B1 prediction is non-blind in time (E0a finished 2026-10-22); its agents could not read E0a, which is an access control, not a timestamp. Codex's verifier had read `main`'s STATE (E0a context), so it is independent, not blind. Its proposed wording patch to PREDICTIONS.md (B2 headline states the operational trend rule, rise ≤ 10 over 1500 s, not "no upward trend") is not applied; the B2 comparison below uses the operational rule.
**Interpretation:** The calibrated simulator is good at the plateau, the tail and the shape, and over-predicts the real dip at n=48–96 by 15–45%, a dip the turns-based estimator says is partly single-run noise. Predictions that depend on the hit-retention transition should be read as a pair of modes.
**Next:** compare B2 with E0b (below), then B3 with E2.

## 2026-10-24 — E0b read (after the predictions were frozen): from-empty edge between 2.0 and 2.5 × λ_ref; pre-registration filled; E2 submitted
**Question:** Up to which arrival rate does the real engine stay good from an empty start (the upper edge of the metastable window), and does it match the blind B2 prediction?
**Setup:** Jobs 17084750–17084755 (submitted 2026-10-23 ~14:40 CDT from `repo/` at bf20ed4; all COMPLETED 0:0, 54.5 min each, nova22-gpu-[1-3]), MODE=cap, registered cell `sglang-fcfs-r1` (FCFS, waiting-prefix refresh on), open-loop Poisson sessions at mult × λ_ref (λ_ref = 0.07153 sessions/s, E0a turns-based), one 3000 s run per mult from an empty cache and queue. Pulled read-only on 2026-10-24 15:06 CDT as an xz archive (sha256 checked at both ends) into `results/nova/e0b_1708475x_pulled_20261024-150639/` (`cfbc702`), i.e. after `r6-predictions-frozen` reached GitHub (14:53). Bracket over all six runs on the login node (nice, `envs/swapp`): `analysis.summarize stable` → `results/agentload_analysis_stable/20261024-150720/` (copied into the pull dir; `lambda_cap_bracket.json` also in `prereg/inputs/2026-10-23/`).
**Result:**

| mult × λ_ref | λ (sessions/s) | stable | final queue | trend rise (last 1500 s) |
|---|---|---|---|---|
| 1.25 | 0.0894 | yes | 0 | 0.0 |
| 1.50 | 0.1073 | yes | 0 | 0.0 |
| 1.75 | 0.1252 | yes | 0 | 0.0 |
| 2.00 | 0.1431 | yes | 0 | −0.5 |
| 2.50 | 0.1788 | **no** | 127 | +146 |
| 3.00 | 0.2146 | **no** | 289 | +196 |

Bracket: largest all-stable 2.0 ×, first unstable 2.5 ×, monotone, no guard errors or warnings; no run aborted. The metastable window is therefore (λ_miss, min(μ_max, 2.0 λ_ref)) = (0.0715, 0.1431) sessions/s; μ_max/λ_ref = 3.26 does not bind.
**Against the blind predictions (operational stability rule; see the round-6 entry):** B2 put the all-stable edge at 0.14 (3 seeds) to 0.15 (20 seeds) sessions/s, about 2 × λ_miss; the real edge lies in [0.143, 0.179). Every real stable run sits where the model gives 3/3 (20/20) stable; at 0.179 the model gives 2/3 (15/20) stable and the single real run is unstable (probability about 0.25–0.33 under the model, not a contradiction); at 0.215 the model gives 0/3 (4/20 at 0.22) and the real run is unstable. **B2 is consistent with E0b.** B1 against E0a (non-blind in time, access-controlled): λ_miss turns-based 0.0722 predicted vs 0.0715 real (+0.9%), all-miss tokens 11 220 vs 11 243 tok/s (−0.2%), sessions/s 0.0694 vs 0.0717 (−3.2%).
**Pre-registration** (`configs/agentload_prereg_2026-10-24.yaml`, `d279b7b`, FILLED, `validate` exit 0, PREREG_SHA256 `2a6d680a…`): λ points 1.35 and 1.65 × λ_ref (0.0966 and 0.1180 sessions/s) by the ⅓/⅔ rule written in the runbook before E0b was read, inside the 10% margin band (1.1, 1.8); n_cap 20 by `smallest_within_margin` (μ(20) = 0.224, within 4% of μ(24) = 0.233; warning `n_cap_ambiguous` recorded); CAPPED drain limit 2.64 × λ_ref. Warnings only: `mu300_far_from_lambda_miss` (informational), `n_cap_ambiguous`. The two calibration copies (prereg input vs Nova's E0a analysis) differ only in the last bit of one standard error; the reference rates are identical.
**E2 submitted** 2026-10-24 15:13 CDT under Akshat's explicit authorization in chat ("You have me permission for E2 as well as any other NOVA requirements"): 18 one-arm jobs **17093387–17093404** (seed-major: for seed 0, 1, 2 → for mult 1.35, 1.65 → arms burst, noburst, capped; capped with N_CAP=20), `--time=03:10:00`, account `f2026.coms.6250.02`, from `repo/` at `d279b7b` (synced by an incremental bundle `bf20ed4..main`, sha256-checked), `CALIB_FILE=prereg/inputs/2026-10-23/calibration.json`, `PREREG_FILE=configs/agentload_prereg_2026-10-24.yaml`, `ENGINE_LABEL=sglang-fcfs-r1`. `check-job` passed on the login node for both mults with the job's own overrides before submission. At submission the `instruction` partition had 120 pending jobs; Slurm's start estimates run from 19:20 tonight (first triple) to 11:11 on 2026-10-25 (last triple).
**Verified vs. not:** Verified: the pull's checksums, the bracket (login node), the filled file's validity, `check-job` for both mults, the 18 job IDs. Not yet: anything about E2's outcome.
**Interpretation:** The window is about 2 × λ_miss wide, as the simulator predicted blind. The kill test now runs at 1.35 and 1.65 × λ_ref, where the model predicts PASS in all three seeds in both modes (B3 at 0.10 and 0.12 sessions/s); the fragile end (0.09, slope margin) and the edge (0.16) are outside the registered points.
**Next:** do not update `repo/` on Nova until all 18 jobs have finished (each job runs the code checked out when it starts). When they finish: pull the runs, run `analysis.summarize burst2 --prereg configs/agentload_prereg_2026-10-24.yaml` over all 18, and compare with B3.

## 2026-10-25 — E2, the pre-registered paired-arm kill test: decisive PASS at both registered points
**Question:** At arrival rates inside the measured metastable window, does a finite burst trap SGLang FCFS prefix-cached agent serving (post-burst prefill-token rate stuck at the all-miss rate with a growing backlog), while the paired no-burst arm stays good and a client-side session cap recovers?
**Setup:** Registration `configs/agentload_prereg_2026-10-24.yaml` (committed `d279b7b` before any E2 job; PREREG_SHA256 `2a6d680a…`). Cell `sglang-fcfs-r1` (FCFS, waiting-prefix refresh on), KV cap 300k, Qwen2.5-7B on A100 80GB PCIe; λ points 1.35 and 1.65 × λ_ref (0.0966 and 0.1180 sessions/s; λ_ref = 0.07153, E0a turns-based); seeds 0-2; three arms per (λ, seed) on common random numbers: BURST (200 fresh sessions in 60 s at t = 1200 s), NOBURST, CAPPED (FIFO session cap n_cap = 20); one 8700 s arm per job. Jobs 17093387–17093404, all COMPLETED 0:0 (2026-10-24 15:38 – 2026-10-25 ~02:40), each run bound to the registration by sha256 and started after its last commit. Verdict: `analysis.summarize burst2 --prereg` over all 18 runs on Nova with the frozen code (`repo/` at `d279b7b`) and the jobs' own overrides (`trap_min_s` 3000, `hit_eval_from_s` 4500, `trap_v2.eval_from_s` 4500) → `results/agentload_analysis_burst2/20261025-144012/`. Pulled read-only as one sha256-checked archive into `results/nova/e2_170933xx_pulled_20261025-144558/` (`49fbc7b`).
**Result:** `pre_registered: true`, `kill_test_pass_decisive: true`, decisive cells: both (1.35 ×, 1.65 ×), both inside the registered window with valid pairing.

| λ (× λ_ref) | arm | seed 0 | seed 1 | seed 2 | count |
|---|---|---|---|---|---|
| 1.35 | BURST | trapped | indeterminate | trapped | trapped 2/3 |
| 1.35 | NOBURST | good | good | good | 3/3 |
| 1.35 | CAPPED | recovered | recovered | recovered | 3/3 |
| 1.65 | BURST | trapped | trapped | trapped | 3/3 |
| 1.65 | NOBURST | good | good | good | 3/3 |
| 1.65 | CAPPED | recovered | recovered | recovered | 3/3 |

Every BURST run sits at hit 0.000 over the evaluation window (t_b + 4500 s to the end), with an uncached-prefill-token rate of 1.009–1.029 × E0a's all-miss rate and a mean backlog of 200–332 waiting sessions; the trapped runs' backlog slope is 0.019–0.036 against thresholds 0.0125 / 0.0232. The one indeterminate run (1.35 ×, seed 1) is stuck in the same way (hit 0.000, token rate 1.009 ×, backlog 200) but its slope 0.0036 is below the 0.0125 threshold. Every NOBURST and CAPPED run is good: hit 0.921–0.934, backlog 8–12, slope ≈ 0. In the evaluation window the CAPPED arm is indistinguishable from NOBURST: the gate drained the burst before t_b + 4500 s.
**Against the blind predictions (B3, `notes/PREDICTIONS.md`, frozen at `64bc4e3` before E0b and E2):** B3 predicted PASS at every λ in 0.09–0.16 sessions/s in both batching modes, including 0.10 and 0.12 (the grid points nearest the registered 0.0966 and 0.1180); trapped token-rate ratio 0.999–1.065 (real 1.009–1.029); trapped backlog 171–523 across λ (real 200–332); NOBURST/CAPPED hit 0.929–0.937 (real 0.921–0.934). B3 also flagged the low-λ end as fragile because the slope margin 0.5 (λ − λ_miss) is small there (20-seed supplement at 0.09: 14/20 trapped by the rule); round 7 put the stuck-but-indeterminate rate at about 1 in 7 at 1.35 ×. The real 1-in-3 at 1.35 × is that failure mode. **Every directional prediction held; the levels are within the predicted ranges.**
**Verified vs. not:** Verified: registration binding and validity (check-job before submission; burst2's provenance checks), the 18 accounting records, the archive checksum, the per-run table. Not verified: anything beyond this protocol (one model, one GPU type, synthetic sessions with Exp(5 s) tools, the 300k-token cap; native pool, other policies and vLLM are separate runs, see below and STATE).
**Interpretation:** The mechanism transfers to a real engine: at a load the server handles indefinitely from empty (NOBURST good in 6/6), a 200-session burst leaves it in an all-miss state with a growing backlog for the remaining 7500 s (5/6 by the registered rule, 6/6 stuck), and a client-side session cap at the measured peak of μ(n) prevents it (6/6). By the outline's own kill rule the paper's framing survives; the referee's "decisive result" condition is met.
**Next:** native-pool E0b (17100938–39) after the blind native predictions are committed; vLLM E0a (17100940); the exploratory policy grid and native Stage C are logged separately; then the paper.

## 2026-10-25 — Native KV pool: the thrashing curve moves out ~3x, λ_miss does not move (Stage C and E0a without the 300k cap)
**Question:** Does the 300k-token cap manufacture the cliff ("you shrank the cache")? With SGLang sizing its own pool, where is the knee of μ(n), and is λ_miss pool-independent?
**Setup:** `KV_TOKENS=native` (no `--max-total-tokens`), label `sglang-fcfs-r1-native`, same model, GPU, workload and closed protocol as Stage C (synchronized start, window [900, 2700) s, one run per n). Stage C jobs 17096856 (n = 24, 48, 64, 80) and 17096857 (96, 128, 300); E0a job 17096858 (cache disabled, POP 32 × 3 seeds + POP 64), all COMPLETED 0:0 from `repo_next/` (commit `5e0ed83`; closed/miss code paths identical to `d279b7b`). SGLang sized the pool at **max_total_num_tokens = 955,757** (3.19 × the cap). Combined curve: `summarize closed --primary-label sglang-fcfs-r1-native` on the login node → `agentload_analysis_closed/20261025-144228/`; E0a calibration from the job's own analysis `agentload_analysis_miss/20261025-054653/`. Data: `results/nova/r7_native_grid_vllm_pulled_20261025-145126/`.
**Result:**

| n | 24 | 48 | 64 | 80 | 96 | 128 | 300 |
|---|---|---|---|---|---|---|---|
| μ sessions/s | 0.265 | 0.431 | **0.479** | 0.477 | 0.123 | 0.067 | 0.101 |
| μ turns-based | 0.252 | 0.414 | 0.466 | 0.464 | 0.116 | 0.073 | 0.107 |
| hit fraction | 0.929 | 0.929 | 0.930 | 0.922 | 0.419 | 0.007 | 0.000 |

Peak 0.479 at n = 64 (n = 80 within 0.4%), 0.5-hit crossing ≈ 93 (linear interpolation), μ(96)/μ* = 0.26, μ(300)/μ* = 0.21. E0a native: λ_miss 0.0720 sessions/s (turns-based **0.0718** ± 0.0037), all-miss uncached tokens 11,282 tok/s; the 300k E0a gave 0.0715 and 11,243. POP 64 check: tokens 11,416 (+1.2%), turns-based 0.0674 (−6.1%), sessions-based 0.0533 (−26%, the transient of a short window at a larger population).
**Against the blind B4 prediction** (round 6, frozen 2026-10-24 before any native run; nearest simulated pool 900k): peak n = 64 predicted (μ 0.514, five seeds) vs 64 real (0.479, −7%); hit crossing predicted ≈ 80 vs ≈ 93 real (the real pool is 6% larger than 900k); collapse by n = 96 predicted (μ 0.08) vs real 0.123 with hit 0.42 still falling (the real cliff is a little further out); μ(300) predicted 0.108 vs 0.101.
**Verified vs. not:** Verified: the pool size from the server log, the curve and calibration (login-node analysis, one run per n). Not verified: n between 80 and 96 (the cliff's exact location), seed-to-seed spread.
**Interpretation:** The cap did not create the cliff: with the native pool the same collapse appears (−74% from n = 80 to 96), shifted out roughly in proportion to the pool, and λ_miss (an all-miss property of the server) is unchanged. The native metastable window can be much wider (μ*/λ_miss ≈ 6.7 vs 3.3); native E0b (17100938–39) measures its from-empty edge.

## 2026-10-25 — Exploratory policy grid on the real engine (BURST arm only): refresh does not matter, LPM partly does
**Question:** Does SGLang's waiting-prefix refresh or longest-prefix-match ordering change the E2 outcome?
**Setup:** Exploratory registrations derived from the E2 registration (`prereg derive-exploratory`; status EXPLORATORY, never decisive; BURST arm only; same λ points 1.35 / 1.65 × λ_ref, seeds 0–2, 300k cap): `sglang-fcfs-r0` (refresh off), `sglang-lpm-r1` (stock LPM, refresh on), `sglang-lpm-r0`. Jobs 17097086–17097103, all COMPLETED 0:0 (`--nice=5000`, from `repo_next/`). Per-cell `burst2 --prereg <grid file>` → `agentload_analysis_burst2/20261025-144230` / `-144233` / `-144236`.
**Result (per run: state, hit in the evaluation window, mean backlog):**
- FCFS refresh off: 1.35 × trapped / indeterminate / trapped (all hit 0.000, backlog 200–231); 1.65 × trapped 3/3 (hit 0.000, backlog 282–328). Run for run within a few percent of the registered FCFS refresh-on runs (same seeds, same arrivals).
- LPM refresh on: 1.35 × recovered (hit 0.71, backlog 48) / recovered (0.81, 23) / draining (0.52, 96); 1.65 × trapped (0.000, 305) / trapped (0.000, 276) / indeterminate (0.45, 106).
- LPM refresh off: 1.35 × trapped (0.000, 225) / recovered (0.80, 27) / recovered (0.93, 10); 1.65 × trapped (0.000, 315) / trapped (0.000, 273) / recovered (0.83, 19).
**Verified vs. not:** Exploratory (BURST arm only, no paired NOBURST/CAPPED, windows and λ points inherited from the FCFS cell, three seeds). Not a kill-test verdict for any of these cells.
**Interpretation:** Waiting-prefix refresh is irrelevant to the trap (as the engine notes predicted: a recency bump, not a pin). LPM ordering helps on the real engine at 1.35 × (recovery or draining in 5 of 6 LPM runs) but not reliably at 1.65 × (4 of 6 trapped or stuck): its recovery threshold lies between 1.35 and 1.65 × λ_miss, above the simulator's LPM (about 1.17 ×; recovery to ~1.1 × in the baseline audit). The simulator therefore understates LPM on the real engine; the paper should say so and not claim LPM fails.

## 2026-10-25 — vLLM 0.32.0 on Nova: env built, GPU check and smoke passed
**Setup:** From `repo_next/` (`6d0dad7`): install 17097972 (CPU, 8 min), GPU check 17097973, smoke 17097974 (closed POP 32, 1800 s, 300k-token pool via `--num-gpu-blocks-override 18750`, block 16, context 49,152 with the rotary `--hf-overrides`), all COMPLETED 0:0. Provenance pulled: `envs/vllm.lock.txt` (199 lines; vllm==0.32.0, torch==2.13.0), `vllm.micromamba.yml`, `vllm_serve_help_0.32.0.txt`.
**Result:** `pip check` clean, `VERSIONS_OK`, `CHECK_DONE` on an A100 80GB PCIe; probe: token ids returned (`choices.0.token_ids`), cached tokens in `usage.prompt_tokens_details`; flush `/reset_prefix_cache` answered `success=true` and the canary verified the cache empty. Decision: vLLM runs use `OUTPUT_FEEDBACK=server` like the SGLang cell. vLLM E0a (17100940) submitted.

## 2026-10-25 — Correction to the policy-grid entry above (rounding)
Four values in the "Exploratory policy grid" entry were rounded wrongly when transcribed from the verdict CSVs (`agentload_analysis_burst2/20261025-144233` and `-144236` in `results/nova/r7_native_grid_vllm_pulled_20261025-145126/`): LPM refresh on, 1.35 ×, seed 0 backlog **47.5** (written 48); seed 2 hit **0.51** (written 0.52; 0.5146); LPM refresh on, 1.65 ×, seed 2 hit **0.44** (written 0.45; 0.4446); LPM refresh off, 1.65 ×, seed 2 hit **0.82** (written 0.83; 0.824996). No state, count or conclusion changes. Found by the paper's figure agent, which plots the CSV values. Also note: the backlog quoted in the E2 and grid entries is the verdict's sessions-in-system series (it includes sessions in tool time, 5–15 when healthy); the registered RECOVERED test uses the "outstanding" series.

## 2026-10-25 — Native-pool E0b: from-empty edge between 5.5 and 6.5 × λ_ref; native pre-registration filled
**Question:** With the KV pool SGLang sizes itself (955,757 tokens), up to which arrival rate does the engine stay good from empty, and does the blind native prediction (B2n) hold?
**Setup:** Jobs 17100938 (mults 1.5, 2.5, 3.5) and 17100939 (4.5, 5.5, 6.5) of the native λ_ref (0.07180 sessions/s, native E0a turns-based), MODE=cap, label `sglang-fcfs-r1-native`, `KV_TOKENS=native`, one 3000 s run per mult from an empty cache and queue; both COMPLETED 0:0 (2026-10-25 14:45–17:27) from `repo_next/` at `fb3510e`. The blind predictions `notes/PREDICTIONS_native.md` were pushed at 15:08 (tag `r8-native-predictions-frozen`), before these runs finished. Bracket on the login node → `agentload_analysis_stable/20261025-172934/`; pulled read-only into `results/nova/e0b_native_1710093x_pulled_20261025-173038/` (`f3f55ab`).
**Result:** stable at 1.5, 2.5, 3.5, 4.5 and 5.5 × (final queue 0, no trend); **unstable at 6.5 ×** (final queue 505, fitted rise +477 over the last 1500 s). Bracket: largest all-stable 5.5 × (0.395 sessions/s), first unstable 6.5 × (0.467), monotone, no guard warnings. μ*/λ_ref = 6.67, so the native window's upper edge is E0b's 5.5 ×: the native window is (1, 5.5) × λ_ref, against (1, 2.0) × at the 300k cap.
**Against the blind B2n prediction:** mixed (primary) put the edge at 6.5 × and predicted 6.5 × stable in 10/10 seeds; the real 6.5 × run is unstable, so the mixed edge is about one grid step (one λ_ref) too high. Separate (secondary) put the edge at 6.0 × with 8/10 stable at 6.5 ×, consistent with the real bracket. All five real stable multiples were predicted stable (60/60 seeds) in both modes.
**Pre-registration** (`configs/agentload_prereg_2026-10-25_native.yaml`, `b8c19ec`, FILLED, valid): cell `sglang-fcfs-r1-native`, window (1, 5.5) × λ_ref, λ points **2.5 and 4.0 ×** (0.179 and 0.287 sessions/s) by the ⅓/⅔ rule written in STATE (`6cb43e9`) before native E0b was read, n_cap **64** (`smallest_within_margin`; warning: n = 80 within 0.35%), CAPPED drain limit 6.19 ×, the 300k registration's trap rules unchanged. Warnings only: `n_cap_ambiguous`, `grid_incomplete` (the native grid has no n = 16, 20, 32), `mu300_far_from_lambda_miss`. Inputs in `prereg/inputs/2026-10-25-native/`.
**Interpretation:** The native window is about 2.75 × wider than at the 300k cap (in units of λ_miss), and its edge is again well below the curve's peak (5.5 vs 6.67), as at 300k (2.0 vs 3.26). B3n predicts PASS inside it with cap 64; the native kill test (18 one-arm jobs, both registered points, 3 seeds × 3 arms) is submitted once `repo_next/` holds the registration.

## 2026-10-25 — vLLM 0.32.0 all-miss capacity (E0a) and its exploratory BURST runs submitted
**Setup:** Job 17100940 (COMPLETED 0:0, 3 h 11 min, nova22-gpu-3) from `repo_next/` at `fb3510e`: MODE=miss, prefix caching off (`--no-enable-prefix-caching`), label `vllm-nocache`, `OUTPUT_FEEDBACK=server` (the smoke showed token ids returned), KV pool 300k tokens (18,750 blocks of 16), closed POP 32 × seeds 0–2 (900 s warm-up + 1800 s window) + POP 64. Data: `results/nova/e0a_vllm_17100940_pulled_20261025-180814/`.
**Result:** λ_miss = 0.0656 sessions/s, **turns-based 0.0657 ± 0.0030**; all-miss uncached tokens **10,349 ± 81 tok/s** (per seed, turns-based 0.0603 / 0.0705 / 0.0662, tokens 10,208 / 10,487 / 10,352). POP 64: tokens 10,531 (+1.8%), turns-based 0.0631 (−4%), sessions-based 0.0467 (the short-window transient again). vLLM's all-miss capacity is about 8% below SGLang's (0.0715, 11,243 tok/s) on the same GPU, model and workload.
**Exploratory registration and runs:** `configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml` (`a78ce07`, `prereg derive-exploratory --engine-cell-label vllm-fcfs --calibration prereg/inputs/2026-10-25-vllm/calibration.json --arms burst`; status EXPLORATORY, never decisive; window and λ multiples inherited from the SGLang cell, reference rates vLLM's own; PREREG_SHA256 `c5037cac…`). Six BURST-only jobs **17102318–17102323** (1.35 and 1.65 × vLLM's λ_ref = 0.0886 and 0.1083 sessions/s, seeds 0–2) submitted 18:07 from `repo_next/` at `a78ce07` after check-job (that sync added only this registration and its input; the pending native kill test is unaffected).

## 2026-10-26 — Native-pool E2: decisive PASS at both registered points; vLLM traps too (exploratory)
**Question:** Does the kill test pass on the KV pool SGLang sizes itself (955,757 tokens), where the cliff sits ~3x further out; and does the trap appear on a second engine?
**Setup (native):** Registration `configs/agentload_prereg_2026-10-25_native.yaml` (`b8c19ec`, committed before any native E2 job; PREREG_SHA256 `21bf7c03…`), cell `sglang-fcfs-r1-native`, λ points 2.5 and 4.0 × the native λ_ref (0.179 and 0.287 sessions/s), cap N_CAP = 64, seeds 0–2, BURST (200 sessions in 60 s at t = 1200 s) / NOBURST / CAPPED, one 8700 s arm per job. Jobs 17102173–17102190, all COMPLETED 0:0 (2026-10-25 17:43 – 2026-10-26 ~10:00), from `repo_next/` at `b8c19ec` (the later sync to `a78ce07` added only a config and an input file). Verdict on the login node: `burst2 --prereg` native with the E2 overrides → `agentload_analysis_burst2/20261026-100653/`. The blind predictions B3n (`notes/PREDICTIONS_native.md`, tag `r8-native-predictions-frozen`, pushed 2026-10-25 15:08) predate every native E2 job.
**Result (native):** `pre_registered: true`, `kill_test_pass_decisive: true`, decisive cells: both. BURST trapped **3/3 at 2.5 × and 3/3 at 4.0 ×** (hit 0.000 in the evaluation window; uncached-token rate 1.074–1.078 × the native all-miss rate at 2.5 ×, 1.106–1.124 × at 4.0 ×; backlog 557–601 and 1098–1139 sessions; slopes 0.079–0.085 vs threshold 0.054 and 0.147–0.164 vs 0.108); NOBURST good 6/6 (hit 0.929–0.935, backlog 16–34); CAPPED recovered 6/6 (same evaluation-window values as NOBURST).
**Against the blind B3n prediction:** PASS predicted at the predicted window's ⅓ and ⅔ points in both modes (mixed 2.85 ×, 4.65 ×; separate 2.65 ×, 4.35 ×) with BURST trapped 9–10/10, NOBURST and CAPPED 10/10; the registered points (2.5, 4.0 ×) are lower because the real edge came in one step below the mixed prediction. B3n's warning held: the trapped token rate sits close to the 15% tolerance at the higher point (predicted 1.09–1.14 ×; real 1.106–1.124 × at 4.0 ×), inside it. Every directional prediction held.
**vLLM (exploratory, BURST arm only):** registration `configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml` (EXPLORATORY, inherited multiples, vLLM's own references); jobs 17102318–17102323, all COMPLETED 0:0; verdict → `agentload_analysis_burst2/20261026-100701/`. All six runs at hit 0.000 in the evaluation window with an uncached-token rate of 0.997–1.031 × vLLM's all-miss rate: **1.35 ×** trapped / indeterminate (slope 0.0002 vs 0.0115, backlog 203) / trapped (backlog 217–227); **1.65 ×** trapped / indeterminate (slope 0.0175 vs 0.0213, backlog 277) / trapped (backlog 300–309). Stuck in 6/6; trapped by the registered rule in 4/6, the other two "indeterminate" by the slope test, as on SGLang.
**Verified vs. not:** Verified: both registrations' binding (check-job before submission, burst2 provenance), the 24 accounting records, the archive checksum (`d0b2a58b…`), the per-run tables. Not verified for vLLM: NOBURST and CAPPED (not run; the vLLM cell is exploratory, window inherited from SGLang, not measured).
**Interpretation:** The metastable trap is not an artefact of the 300k cap: with the native pool the registered kill test passes cleanly at both points (6/6 trapped, 6/6 good, 6/6 recovered), with a window ~2.75 × wider. A second engine, vLLM 0.32.0, gets stuck in the same all-miss state after the same burst in every run. Together with E2, both registered kill tests pass and every blind directional prediction (B2, B3, B2n, B3n) held; the mixed-mode simulator overestimates the native edge by about one λ_ref.

## 2026-10-26 — Correction to the native-pool entries above (blindness scope and the B3n comparison)
Found by the paper's update agent and its reviewers; the frozen `notes/PREDICTIONS_native.md` is left as it was.
- **B1n and B4n are not blind in time.** The STATE commit `6793fb7` (2026-10-25 ~14:47) recorded the real native curve (peak 0.479 at n = 64, collapse to 0.123 at n = 96) and native λ_miss two minutes before the prediction spec was committed (`29728e3`, 14:49), and the n grid the lead gave the predicting agent (adding 72, 80, 88) was chosen knowing where the real cliff was. The agent was instructed not to read real native data and reports that it did not, but that is an access control, not a timestamp. **B2n and B3n are blind to their outcomes** (native E0b and E2 had not finished / not started when the predictions were pushed at 15:08), though specified after the native curve was known; B3n's cap of 64 is B4n's output.
- **B3n did not simulate the registered rates.** B3n predicted PASS at its own ⅓ and ⅔ points (mixed 2.85, 4.65 ×; separate 2.65, 4.35 ×), 6–16% above the registered 2.5 and 4.0 × in multiples of λ_miss; the registered 2.5 × lies below all four simulated points and 4.0 × between them. Per point, the real trapped token ratios lie just below the predicted range at 2.5 × (1.074–1.078 vs 1.086–1.109) and overlap its low end at 4.0 × (1.106–1.124 vs 1.119–1.140). "Every directional prediction held" stands for pass/fail; the level comparison is approximate.
- The "~2.75 ×" in the native E0b entry is the ratio of the upper edges (5.5 / 2.0); the window widths are 4.5 vs 1.0 λ_miss.

## 2026-10-30 — Full vLLM paired kill test started; blind simulator predictions frozen first (round 9)
**Why:** the vLLM cell has been exploratory: its window and multiples were inherited from SGLang, and only the BURST arm ran. Akshat approved the full test ("Yes, run it", 2026-10-30): vLLM's own Stage C curve and from-empty edge, its own registration, then the paired NOBURST / BURST / CAPPED test (3 seeds × 2 points), as for SGLang (E2) and the native pool.
**Running (from `repo_next/` at `a78ce07`, job code unchanged since the exploratory runs):** Stage C 17162959 (n 16 20 24), 17162960 (28 32 40), 17162961 (48 96 300), MODE=closed, label `vllm-fcfs`, `KV_TOKENS=300000`; E0b 17162962–17162963. The registration rule was committed in STATE (`836063a`) before any result existed: cap = smallest n within 5% of the turns-based peak; points ⅓ and ⅔ of (1, hi), rounded to 0.05, hi = the largest all-stable E0b multiple capped by μ*/λ_ref.
**Blind predictions (round 9, `notes/PREDICTIONS_vllm.md`, spec `configs/r9_vllm_predict.yaml`):** spec `5806460` (12:18), V1 factors `fd92caf` (12:19), all runs on `29746a9`, notes `cc01dbf`; tag `r9-vllm-predictions-frozen` pushed 12:32 CDT, merged `40d8e14`. At push time Stage C 17162959–60 had run ~20 min and the other three jobs were pending, so B4v, B2v and B3v are blind in time. Two variants, both modes: V0 = the SGLang-calibrated engine unchanged, results in multiples of its own λ_miss; V1 = token-proportional costs × 1.0882 (mixed) / 1.0806 (separate) so the all-miss rate matches vLLM's 10,349 tok/s (fitted, not predicted). Neither models vLLM's block-level lazy eviction, missing waiting-prefix refresh or chunked-prefill budget.
- B1v: V0 λ_miss 0.0722 / 0.0714 (1.09–1.10 × the real 0.0657); V1 0.0662 / 0.0663 (a by-product of the fit; not blind, E0a was known).
- B4v (10 seeds): peak at n = 24 in all four configurations (μ* = 3.07–3.25 × λ_miss), hit 0.93 at n ≤ 20, 0.89 at 24, 0.74–0.77 at 28, 0.46–0.53 at 32, ≤ 0.11 at 40; 0.5-hit crossing n = 31.4–32.6; cap 20 (1.8–3.9% above the 95% line; n = 24 bistable across seeds).
- B2v (10 seeds): 10/10 stable at 1.25–2.0 ×; 6–8/10 at 2.5 ×; 1–3/10 at 3.0 ×; edge hi = 2.0 × in all four. A real edge of 2.0 × registers 1.35 × and 1.65 ×.
- B3v (10 seeds, cap 20): PASS at 1.35 × and 1.65 × in all four configurations under both the per-arm and the same-seed rule (BURST trapped 7–9/10, NOBURST good 10/10, CAPPED recovered 10/10); PASS from 1.25 to 2.0 ×; V0 fails at 1.10–1.15 × (the slope test, not recovery) and at 2.35 × (NOBURST collapses from empty in 4/10). Trapped runs process 0.99–1.07 × the all-miss token rate. Cap sensitivity: caps 16–24 recover 10/10 up to 1.65 ×; 28 is marginal at 2.0 ×; 32 sits on the cliff; 40 never recovers.
**Blindness scope:** the predicting worker read no `results/nova/` data and none of LOG, STATE or the paper; the two real vLLM numbers (λ_miss 0.0657, 10,349 tok/s) were given in its task. The lead knew the exploratory vLLM BURST outcome (stuck 6/6 at 1.35 and 1.65 ×, LOG 2026-10-26) and chose the candidate multiples, so the BURST-arm predictions at those points are blind on the worker's side only. The n grid was set when the jobs were submitted, from the SGLang curve, before any vLLM curve existed. The notes' first line ("never pushed, never merged") was true when written; the branch was pushed and merged after the tag.

## 2026-10-30 — vLLM's own thrashing curve and from-empty edge; vLLM pre-registration filled and the paired test submitted
**Question:** Measured on vLLM 0.32.0 itself (not inherited from SGLang), where are the peak and the cliff of μ(n), where is the from-empty edge, and do the blind round-9 predictions (B4v, B2v) hold?
**Setup:** Stage C 17162959 (n = 16, 20, 24), 17162960 (28, 32, 40), 17162961 (48, 96, 300), MODE=closed, label `vllm-fcfs`, `KV_TOKENS=300000`, one run per n, all COMPLETED 0:0; combined curve on the login node `summarize closed --primary-label vllm-fcfs` → `agentload_analysis_closed/20261030-153533`. E0b 17162962 (mults 1.25, 1.5, 1.75 of vLLM λ_ref = 0.06566, COMPLETED 0:0) and 17162963 (2.0, 2.5, 3.0; the 3.0 × run still running at registration), one 3000 s run per mult from an empty cache and queue; bracket over the five finished runs on the login node → `agentload_analysis_stable/20261030-162319`. All from `repo_next/` at `a78ce07`. Data: `results/nova/stageC_vllm_1716295x_pulled_20261030-153621/` (archive sha256 `3ff948dd…`); the E0b pull follows when 17162963 ends. The blind predictions (tag `r9-vllm-predictions-frozen`, pushed 12:32) predate every one of these results.
**Result (Stage C):**

| n | 16 | 20 | 24 | 28 | 32 | 40 | 48 | 96 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| μ sessions/s | 0.175 | **0.219** | 0.218 | 0.119 | 0.043 | 0.041 | 0.044 | 0.057 | 0.105 |
| μ turns-based | 0.174 | 0.211 | 0.210 | 0.123 | 0.054 | 0.056 | 0.059 | 0.069 | 0.105 |
| hit fraction | 0.932 | 0.926 | 0.879 | 0.658 | 0.083 | 0.007 | 0.000 | 0.000 | 0.000 |

Peak 0.2194 sessions/s at n = 20 (n = 24 within 0.5 %; n = 16 is 20 % lower), μ_max/λ_ref = 3.34 (turns-based 3.21); 0.5-hit crossing ≈ 29.1 (linear between 28 and 32); μ falls 80 % from n = 24 to 32, and at n = 32–48 the turns-based μ (0.054–0.059) is 0.83–0.90 × λ_miss, below the all-miss rate. No guard warnings.
**Result (E0b):** stable at 1.25, 1.5, 1.75, 2.0 × (final queue 0, trend ≤ 0.02); **unstable at 2.5 ×** (final queue 81.6, fitted rise +94 over the last 1500 s). Bracket: largest all-stable 2.0 ×, first unstable 2.5 ×, monotone, no guard warnings. Window (1, 2.0) × λ_ref (μ_max/λ_ref = 3.34 is not binding).
**Against the blind predictions:** B4v peak at n = 24 with μ* 3.07–3.25 × λ_miss: real peak at 20 with 24 within 0.5 % (a tie at one run per n), μ* 3.21 × turns-based / 3.34 × sessions-based; cap 20 predicted and registered. Hit 0.93 at n ≤ 20 and 0.89 at 24 predicted, 0.93 and 0.88 real; at 28 and 32 the real cliff is steeper and earlier (0.66 vs 0.74–0.77; 0.08 vs 0.46–0.53), crossing ≈ 29 vs 31.4–32.6 predicted. B2v edge 2.0 × in all four configurations: real edge 2.0 × (2.5 × predicted 6–8/10 stable; the single real run is unstable). So the registered points equal the predicted ones (1.35, 1.65 ×).
**Pre-registration** (`configs/agentload_prereg_2026-10-30_vllm.yaml`, commit `5a6fbcd` on `r9/vllm-register`, parent `a78ce07`; FILLED, valid; PREREG_SHA256 `8f2d5b44…`): cell `vllm-fcfs`, λ_ref 0.06566 (vLLM E0a `prereg/inputs/2026-10-25-vllm/calibration.json`), window (1, 2.0) ×, λ points 1.35 and 1.65 × by the ⅓/⅔ rule written in STATE (`836063a`) before any vLLM Stage C or E0b result existed, n_cap 20 (`smallest_within_margin`), the 300k registration's trap rules unchanged. Warnings only: `n_cap_ambiguous` (n = 24 within 0.0051), `mu300_far_from_lambda_miss`. Inputs in `prereg/inputs/2026-10-30-vllm/` (copied byte-exact; hashes checked on both ends). **Deviation, disclosed:** registered from five of the six E0b runs (the 3.0 × run was still running); the rule's hi is the largest multiple at and below which every run is stable, so with 2.5 × unstable the 3.0 × run cannot change it. If the 3.0 × run turns out stable the bracket becomes non-monotone; record that, the registration stands.
**Submitted 16:30 CDT** (Akshat: "Yes, submit tonight", then "Actually submit right now if possible lets do it concurrently"): 18 one-arm jobs **17166121–17166138** (seed-major; 1.35 and 1.65 ×; BURST / NOBURST / CAPPED with N_CAP=20; `--time=03:10:00`) from `repo_next/` at `5a6fbcd` after check-job passed for every arm at both points.
**Verified vs. not:** Verified: the combined curve and bracket (login-node analyses, no guard warnings), input hashes on both ends, the registration's validity and check-job for all six (λ, arm) pairs. Not verified: seed-to-seed spread of the curve (one run per n) and of the edge (one run per multiple); the 3.0 × E0b run.
**Interpretation:** vLLM has the same shape as SGLang at the same 300k-token pool: a peak near n = 20–24 at about 3.2–3.3 × the all-miss rate, a cliff to below the all-miss rate, and a from-empty edge (2.0 ×) far below the peak. Its cliff is steeper than the simulator predicted. The paired test now runs at vLLM's own measured window, so §5.7 can become a registered result.

## 2026-10-30 — vLLM E0b complete: the 3.0 × run is unstable too; the six-run bracket equals the registered one
**Setup:** Job 17162963's last run (3.0 × vLLM λ_ref, `agentload_e0_cap/20261030-162428`) finished after the registration; both E0b jobs COMPLETED 0:0. Six-run bracket on the login node → `agentload_analysis_stable/20261030-172042` (the jobs' own per-job brackets: `-155754` for 17162962, `-171731` for 17162963). Data: `results/nova/e0b_vllm_1716296x_pulled_20261030-172810/` (archive sha256 `4f982631…`; the five-run bracket used by the registration is byte-identical to `prereg/inputs/2026-10-30-vllm/lambda_cap_bracket.json`).
**Result:** 3.0 × unstable (final queue 247.1, fitted rise +175). Six-run bracket: largest all-stable 2.0 ×, first unstable 2.5 ×, monotone, no guard warnings, the same as the five-run bracket the registration used. The registration's disclosed deviation (registered before the 3.0 × run ended) had no effect.

## 2026-10-31 — vLLM registered paired test: PASS at both registered points; frozen mechanism checks met except two detector false alarms in CAPPED
**Question:** On vLLM 0.32.0, at the rates its own window registers (1.35 and 1.65 × λ_ref), does a 200-session burst trap the server while the paired NOBURST arm stays good and a client-side cap of 20 recovers? And do the frozen round-11 mechanism predictions (refill-then-evict, online detector) hold?
**Setup:** Registration `configs/agentload_prereg_2026-10-30_vllm.yaml` (`5a6fbcd`, committed 16:23:59 CDT on 2026-10-30; PREREG_SHA256 `8f2d5b44…5f84`, carried by every run's `meta.json`). Cell `vllm-fcfs`, 300k-token pool (18,750 blocks of 16), Qwen2.5-7B on A100 80GB PCIe (nova22-gpu-[1-3], hardware string checked by each job), λ_ref = 0.06566 sessions/s, cap 20, seeds 0–2; BURST (200 sessions in 60 s at t = 1200 s) / NOBURST / CAPPED on common random numbers, one 8700 s arm per job. Jobs **17166121–17166138** (submitted 16:24:36, all COMPLETED 0:0; starts 16:25:42 – 21:51:12, ends 18:55:07 on 10-30 – 00:20:24 on 10-31) from `repo_next/` at `5a6fbcd`, unchanged throughout. **Memory request change (scheduling only):** at 18:21 CDT on 10-30 the then-pending jobs 17166124–17166138 had MinMemoryNode lowered from 128G to 48G (sacct ReqMem: 128G for 17166121–23, 48G for the rest) so that they could start on A100 nodes held back by other users' host-memory use; the job script, its arguments and the registration are unchanged, and a vLLM job peaks at about 20 GB of host memory. Verdict on the login node in `repo_next/` (2026-10-31 02:08): `summarize burst2` over the 18 run dirs listed in `results/nova_job_logs/<job>-*/run_dirs_burst.txt` with `--set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500 --prereg configs/agentload_prereg_2026-10-30_vllm.yaml` → `agentload_analysis_burst2/20261031-020837/` (no guard errors or warnings). Pulled read-only as one xz archive (sha256 `aedfb5b2…` checked at both ends; remote archive deleted) into `results/nova/e2_vllm_1716612x_pulled_20261031-020956/` (`cacf833`): 18 run dirs, 18 job-log dirs, the verdict dir, `logs/pm-e2v-17166121..38.out`, `sacct_17166121-17166138.txt`. Then the frozen r11 scripts (copied unchanged from `f1338e3`; hashes in the pull's `r11_mechanism/frozen/SHA256SUMS`) on the pulled runs, and `analysis/r9_vllm_e2_derived.py` for the bands and the client-side numbers (pull's `derived/`).
**Result (registered rule):** the registered analysis gives PASS at both cells (`kill_test_pass_rule_only: true`; both cells in the registered window, valid pairing). The tool also prints `pre_registered: true` and `kill_test_pass_decisive: true`, which it assigns by commit order (see "Verified vs. not").

| λ (× λ_ref) | arm | seed 0 | seed 1 | seed 2 | count |
|---|---|---|---|---|---|
| 1.35 | BURST | trapped | draining | trapped | trapped 2/3 |
| 1.35 | NOBURST | good | good | good | 3/3 |
| 1.35 | CAPPED | recovered | recovered | recovered | 3/3 |
| 1.65 | BURST | trapped | indeterminate | trapped | trapped 2/3 |
| 1.65 | NOBURST | good | good | good | 3/3 |
| 1.65 | CAPPED | recovered | recovered | recovered | 3/3 |

Every BURST run has hit 0.000 over the evaluation window (t_b + 4500 s to 8700 s) and an uncached-prefill rate of 0.948–1.018 × vLLM's all-miss rate (1.35 ×: 1.012, 1.007, 0.995; 1.65 ×: 1.018, 1.014, 0.948). Trapped runs: backlog slope 0.0142 and 0.0170 against the threshold 0.0115 (1.35 ×), 0.0324 and 0.0341 against 0.0213 (1.65 ×); mean backlog 221.6, 220.5 and 314.2, 330.1 sessions. The two non-trapped BURST runs are both seed 1, the seed with the fewest arrivals, and both are stuck: 1.35 × seed 1 is labelled DRAINING because its slope is −0.00005 sessions/s (flat; backlog 200.5, hit 0.000, token rate 1.007 ×), and 1.65 × seed 1 is INDETERMINATE (slope 0.0183 < 0.0213; backlog 281.3). NOBURST and CAPPED: hit 0.930–0.933, mean backlog 7.0–10.9, |slope| ≤ 0.001; in the evaluation window the two arms are indistinguishable (the gate had drained). The pattern (trapped, stuck, trapped at both rates, seed 1 the odd one) repeats the six exploratory vLLM BURST runs (17102318–23), whose arrival plans these runs share: base arrivals in [5700, 8700) are 285, 245, 278 (1.35 ×) and 347, 307, 342 (1.65 ×), identical across the three arms of a seed and to the exploratory runs.
**Against the blind predictions (B3v, `notes/PREDICTIONS_vllm.md`, tag `r9-vllm-predictions-frozen` pushed 12:32 CDT 10-30, before any of these jobs existed):** B3v predicted PASS at both points in all four configurations; the real result is PASS at both. BURST trapped was predicted 7–9/10 per point, real 2/3 at each (consistent at three seeds). The stuck-but-not-trapped runs, predicted as INDETERMINATE, appear once as INDETERMINATE and once as DRAINING by a slope of −5 × 10⁻⁵ sessions/s, a label B3v did not produce; no BURST run recovered, as predicted. NOBURST good and CAPPED recovered were predicted 10/10, real 6/6 and 6/6. Trapped token rate predicted 0.99–1.07 ×, real 0.995–1.018 × in three trapped runs and **0.948 × in the fourth (1.65 ×, seed 2), below the predicted range** (inside the registered ±15 %).
**Frozen mechanism predictions (`configs/r11_mechanism_predict.yaml`, `f1338e3`, pushed 18:20:13 CDT 10-30):** all 18 runs are blind by the frozen rule (earliest sacct End 18:55:07 > 18:20:13). (a) NOBURST/CAPPED: follow-up hit 1.000 (3 dp) and gap/R 0.014–0.022 (< 0.05) in 12/12; BURST: hit 0.000 and gap/R 6.44–8.78 (> 2; R = 28.1–30.2 s, median gap 183–261 s) in 6/6. (b) BURST: mean `vllm:kv_cache_usage_perc` 0.920–0.937 (≥ 0.90) and uncached-token rate 0.871–0.955 × 10,348.6 tok/s (in [0.85, 1.15]) in 6/6; the lowest ratio is again 1.65 × seed 2. (c) Detector: BURST first alarm 100–120 s after the burst in 6/6 (≤ 300 s); **two false alarms in good arms, both CAPPED seed 2**: 1.35 × at 2080 s (2 ticks) and 1.65 × at 2020 s (4 ticks), 880 and 820 s after the burst; hits back (H > 0.8 for 300 s) from 2190 and 2180 s; no alarm in the other 10 good-arm runs. (d) Engine-TTFT rule: BURST 170–210 s after the burst in 6/6, no alarm in 12/12 good arms. **Frozen decision rule: not met**: it allows at most one good-arm run failing (a) or (c), and two fail (c). No BURST run failed (b), so the b_failure clause (drop refill-then-evict for vLLM) is not triggered; the two alarms are reported as detector false alarms, as the frozen file directs. Post hoc (`derived/r11_detector_false_alarm_context_posthoc.csv`): both alarms fall during the CAPPED drain, with 20 sessions admitted and 123–143 waiting at the gate; the 60 s follow-up hit fell from about 0.7–0.95 to 0.06–0.17 for 20–40 s and was above 0.8 again about 110–160 s later. That is a short excursion of the capped engine at n = 20, the cap that sits within 0.5 % of n = 24 on vLLM's steep cliff.
**Client side (post hoc, computed as for the 300k E2; pull's `derived/e2_vllm_client_side.csv`, `e2_vllm_client_side_summary.csv`, `e2_vllm_capped_drain.csv`):** CAPPED gate: 322, 334, 404 (1.35 ×) and 499, 402, 462 (1.65 ×) sessions waited; the base-stream share among them was 43–53 % and 53–63 % (17–26 % and 22–31 % of all base arrivals); mean wait 435–501 s and 413–526 s; longest 859–1053 s and 892–1052 s; none censored; at most 3 gated sessions per run arrived before the burst (≤ 9.2 s) and at most 9 after the gate first emptied (≤ 9.8 s). The gate queue first emptied 1521–2027 s (1.35 ×) and 1848–2735 s (1.65 ×) after the burst, 0.99–1.52 × the registration's estimate (1529, 1800 s) and 1.05–1.63 × the fluid estimate from the population at the burst. Mean turn latency of ok requests completed in [5700, 8700): BURST 179.5–188.1 s (1.35 ×) and 226.9–261.4 s (1.65 ×); NOBURST 1.38–1.53 s; CAPPED 1.37–1.58 s; before the burst ([300, 1200)) 1.42–1.67 s in every arm. Sessions unfinished at 8700 s: BURST 20.2–24.2 % and 25.8–31.2 %; NOBURST 0.7–1.1 %; CAPPED 0.6–0.9 %. Realized base arrival rates in the window: 1.447, 1.244, 1.411 × λ_ref (nominal 1.35) and 1.762, 1.558, 1.736 × (nominal 1.65); BURST runs completed 1.18–1.28 × and 1.30–1.42 × λ_ref, the good arms as many sessions as arrived.
**Blindness scope:** B3v is blind in time to every one of these runs; its BURST-arm predictions at 1.35 and 1.65 × are blind on the predicting worker's side only (the lead knew the exploratory BURST outcome). r11: all 18 runs are blind in time; the bands were chosen on committed SGLang E2 runs and the six exploratory vLLM BURST runs, whose arrival plans the registered BURST arms repeat, so the BURST checks are a replication on new executions and only NOBURST and CAPPED are out of sample. Before the verdict was run (2026-10-31 02:08), this session had opened no run dir, per-job analysis or `pm-e2v` `.out` file of these jobs, only `sacct` states. The freeze note's statement that no output had been opened by 18:20 is its author's, not checked here. The memory change above was made after the first three jobs had started and before any ended, and it does not touch the code or arguments of any job.
**Verified vs. not:** Verified: the 18 accounting records (all COMPLETED 0:0, nodes nova22-gpu-[1-3]); `repo_next/` HEAD `5a6fbcd` with a clean tree; the registration hash on Nova and in all 18 `meta.json`; the archive checksum; the frozen scripts byte-identical to `f1338e3` and to `origin/r11/strengthen`, and `analysis/load.py` unchanged since the freeze; zero request errors and no guard warnings. Commit order: `5a6fbcd` was committed 37 s before the submission but first reached GitHub at 16:26:35 CDT (the creation of branch `r9/vllm-register` in GitHub's activity log), 1 min 59 s after the submission and after the first two jobs started (16:25:42, 16:26:17), before any job ended. So the decisive label the tool prints rests on commit order, not on the push log, and the paper should report the registered analysis's PASS. Not verified: anything beyond one model, one GPU type, the 300k pool and three seeds; the TTFT rule's alarm-free window in good arms is checked from the first alarm only (none occurred).
**Interpretation:** vLLM, a second engine with its own measured window, fails the way SGLang does: at a load it carries indefinitely from empty (NOBURST good 6/6), a 200-session burst leaves it all-miss for the remaining 7500 s (stuck 6/6, trapped by the registered rule 4/6), and a client-side cap at its measured peak prevents that (6/6). The trapped pool is full (KV usage 0.92–0.94) and rewritten at about the all-miss rate, as refill-then-evict predicts. The frozen prediction that missed is the detector's specificity: during the CAPPED drain at cap 20 the follow-up hit dips below 0.2 for a few ticks in one seed at each rate, which a deployed alarm on this rule would report.
## 2026-10-31 — B1 basin test PASS: a burst of 25 is absorbed, a burst of 100 traps (3/3 seeds each); E0F not replicated (2.5 × stable on fresh seeds)
**Question:** Does the good state have a finite basin on the real engine (registered B1: at 1.65 × λ_ref, does a burst of 100 trap and one of 25 not)? And does the from-empty edge (2.0 × stable, 2.5 × unstable on seed 0) replicate on fresh seeds 3-5 (exploratory E0F)?
**Setup:** B1 jobs 17168500-02 (n = 100, seeds 0-2) and 17168503-05 (n = 25, seeds 0-2), one BURST arm each, 1.65 ×, 60 s burst at 1200 s, 8700 s runs, labels `sglang-fcfs-r1-b100` / `-b25`, registrations `configs/agentload_prereg_2026-10-30_b100.yaml` / `_b25.yaml` (tag `r11-basin-reg` `9b67c26`, GitHub push 20:04:30 CDT Fri; submitted 21:12:45). E0F jobs 17168506 (2.0 ×) and 17168507 (2.5 ×), seeds 3 4 5, 3000 s from empty, label `sglang-fcfs-r1-e0bfresh`. All from `repo_r11_basin` at `9b67c26`, COMPLETED 0:0 (sacct End 00:31:05 to 04:01:04 Sat), A100 80GB PCIe on nova22-gpu-1/2/3, start state verified and canaries rc 0 in every run. Pulled read-only to `results/nova/b1_e0f_1716850x_pulled_20261031-040517/` (archive sha256 `aaa04afb…` on both ends, remote deleted). Verdict: `analysis.basin classify --endpoints configs/r11_basin_predict.yaml --run-dirs <6> --prereg <b100, b25>` at `19c58e9` (baselines n = 0 / 200 found by the tool: the committed 1.65 × runs of jobs 17093387-404) → `analysis/agentload_analysis_basin/20261031-040758`; re-run with `analysis/basin.py` as tagged (`9b67c26`): identical decision and per-run numbers. E0F: `summarize stable` over the six runs → `analysis/agentload_analysis_stable/20261031-040957`; realized rates and a descriptive B1 time course by `analysis/r11_b1_e0f_derived.py` → `analysis/derived/`.
**Result (B1):**

| n | seed 0 | seed 1 | seed 2 | hit_eval | backlog slope /s |
|---|---|---|---|---|---|
| 0 (committed) | GOOD | GOOD | GOOD | 0.934 / 0.934 / 0.921 | ≈ 0 |
| **25** | **GOOD** (recovered) | **GOOD** | **GOOD** | 0.933 / 0.934 / 0.923 | -0.0005 / 0.0011 / 0.0001 |
| **100** | **STUCK** (trapped) | **STUCK** (trapped) | **STUCK** (trapped) | 0.000 ×3 | 0.0318 / 0.0344 / 0.0361 (threshold 0.0232) |
| 200 (committed) | STUCK | STUCK | STUCK | 0.000 ×3 | 0.028-0.036 |

n100 STUCK 3/3 and TRAPPED 3/3, n25 GOOD 3/3: **`basin_pass` true (PASS)**; no pre-stated alternative outcome, no endpoint problem, every run bound to its registration, `registration_diff` forbidden list empty. n = 100 has hit < 0.2 in every 100 s window from 1300 s on; n = 25 never drops below 0.83 in any 100 s window and its hit_eval is within 0.002 of the n = 0 run of the same seed.
**Result (E0F):** all six stable (final queue 0, rise ≤ 0): 2.0 × seeds 3/4/5 (realized 2.01 / 2.15 / 1.97 ×), 2.5 × seeds 3/4/5 (2.51 / 2.67 / 2.47 ×). Replication rule (2.0 × 3/3 stable AND 2.5 × ≥ 2/3 unstable): **not replicated**. Fallback: over all 12 from-empty runs (seeds 0, 3, 4, 5), stable at every realized rate ≤ 2.665 ×, unstable at 2.726 × (seed 0's 2.5 ×) and 3.25 ×; monotone in realized rate. Pooled nominal bracket unchanged (2.5 × stable 3/4).
**Against predictions:** Simulator bundle 1 (`notes/PREDICTIONS_r11_basin.md`, blind in time for all 12 runs): PASS, every per-run call (n100 STUCK+TRAPPED ×3, n25 GOOD ×3, E0F stable ×6) and NOT replicated all match; hit within 0.006, n100 slopes within 0.0005 /s per seed; token ratio 1.013-1.037 against a descriptive 1.03-1.05. Theory (`r13-theory-pred`, pushed 02:05:30 Sat): P(STUCK) 1.000 / 0.042 and P(PASS) 0.995 match (P of this exact outcome 0.88); its specific N_crit 53.4 / committor-50% at n ≈ 50 is untested by B1 (B2 tests it). The n = 100 runs ended 00:28-01:51, before the theory push: blind by access only. The theory froze no E0F prediction; its JSON's F2 escape probabilities (0.150 / 0.691 at 2.0 / 2.5 ×) imply P(2.5 × stable 3/3) = 0.03.
**Verified vs. not:** Verified: the registered verdict at HEAD and at the tag, agreement with the jobs' in-job trap_v2 and stable analyses, archive hash, run identities (label, seed, rate, burst n, prereg sha) from meta.json. Not verified: that nobody read the n = 100 in-job summaries before 02:05:30 Sat (`/work/classtmp` is `noatime`; no commit references them). `analysis/seed_effects.py`, which the frozen endpoints name for realized rates, does not exist; the same quantity (n_base / duration / λ_ref) was computed instead. `r13-theory-pred2` (E0F theory predictions) is not on GitHub as of 04:13 CDT; any E0F prediction pushed later is not blind.
**Interpretation:** The good state at 1.65 × is metastable with a finite basin: it absorbs a 25-session burst without trace and tips within 100 s after a 100-session burst, a critical size between 25 and 100 in every seed. The seed-0 2.5 × instability that set the from-empty edge is an arrival-count effect; the registered window (hi 2.0 ×) stands as frozen. Paper input: `notes/PAPER_INPUT_basin.md`.
## 2026-10-31 — LPM-INF (L1 step 2): stock LPM without its 128-request FCFS fallback does not collapse on the seeds where stock LPM did (exploratory)
**Question:** At 1.65 × λ_ref, stock SGLang 0.5.22 LPM collapsed to the all-miss trap on seeds 0 and 1 in both grid replicates. The post-hoc crossing analysis (`analysis/lpm_crossing.py`, `notes/LPM_CROSSING_r11.md` on `r11/strengthen`) found every collapse coincided with the waiting queue passing 128. Above 128, `_determine_active_policy` silently switches LPM to FCFS order. If the fallback is removed, does LPM still collapse?
**Setup:** Cell `sglang-lpminf`: POLICY=lpm, REFRESH=1, LPM_INF=1. That is the stock `envs/sglang` plus the job-local hook `slurm/hooks/lpm_inf/sitecustomize.py` (md5 `be788ae7…`), which raises `schedule_policy.WAITING_QUEUE_PREFIX_MATCH_MAX` from 128 to 1e9 in every process that imports it. BURST arm only, E2 protocol (200 sessions in 60 s at 1200 s, 8700 s run), 300k pool, 1.65 × λ_ref = 0.11803 sessions/s, seeds 0–2.
- Frozen inputs, all on `r11/lpminf` at `5064580` (tag `r11-lpminf-pred`): the exploratory registration `configs/agentload_prereg_2026-10-30_grid_sglang-lpminf.yaml` (`derive-exploratory`, PREREG_SHA256 `f4454c5b…`), the endpoints and decision rule `configs/r11_lpminf_predict.yaml`, and the blind simulator predictions `notes/PREDICTIONS_r11_lpminf.md` (S1 bundle 2). Pushed to GitHub 2026-10-31 02:02:46 UTC (21:02:46 CDT Fri; `gh api …/activity`, branch creation at `5064580`), before submission.
- Jobs **17168743 / 17168744 / 17168745** (seeds 0 / 1 / 2), submitted 2026-10-30 22:07:40 with `--nice=56` from `$W/repo_r11_lpm` (HEAD `5064580`, clean, untouched since). sacct: all COMPLETED 0:0, elapsed 2:29:41–2:29:45, on nova22-gpu-2 / -1 / -1, ended 03:51:56, 04:12:05 and 04:23:48 CDT Sat. MaxRSS 6.1–6.6 GB of 48 G.
- Verdict on the login node: `summarize burst2 --run-dirs <3> --out-root results --set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500 --prereg configs/agentload_prereg_2026-10-30_grid_sglang-lpminf.yaml` → `agentload_analysis_burst2/20261031-042736`. No guard warnings; `pre_registered: false`, exploratory as designed.
- Pulled read-only into `results/nova/lpminf_1716874x_pulled_20261031-042548/` (`fc8b028`). Archive sha256 `ce1eb62d…`, verdict-dir archive `7903a474…`; both checked on both ends, and the remote archives deleted.
- Endpoints: `analysis/r11_lpminf_eval.py` (constants read from the frozen file) → `results/r11_lpminf_eval/20261031-eval/`.
- Controls. All five cells have the same `plan.csv` sha256 per seed (common random numbers).
  - Stock LPM `sglang-lpm-r1`: 17097090 / 096 / 102. `-r0`: 17097091 / 097 / 103. Grid pull `r7_native_grid_vllm_pulled_20261025-145126`.
  - FCFS `sglang-fcfs-r1`, E2 BURST: 17093390 / 396 / 402 (`e2_170933xx_pulled_20261025-144558`). `-r0`: 17097089 / 095 / 101.

**Manipulation check (frozen):**
- **Hook items: all three runs pass.** `lpm_inf_markers.txt` holds `128 -> 1000000000` from the server pid and from exactly one child of it (pids 3826316, 3327643, 3330171, each with parent = the server pid the job printed). The CPU self-test in `flag_check.txt` reported value 1e9, `schedule_policy.py` md5 `b8ec334a…`, hook md5 `be788ae7…`, and LPM active at a queue of 300. The control without the variable gave 128 and FCFS.
- **Scheduler cost** (`get_next_batch_to_run` s/s in 60-s bins whose mean queue is > 128):
  - seed 0: 42 of 42 bins ≥ 0.008 (median 0.0130, min 0.0107);
  - seed 1: 94 of 94 bins (median 0.0144, min 0.0119).
  - Both **PASS**: the queue did pass 128, and LPM's prefix matching kept running there. Stock LPM and FCFS sit at 0.0027–0.0031 s/s in such bins (the fallback level).
- **Seed 2:** the queue never passed 128 (max 120), so the scheduler-cost item is **UNINFORMATIVE**, not failed. The patched constant was never consulted at a value where it matters, so this run is in effect a third stock-LPM replicate.
- **Not proven:** that the marking child is the scheduler. It is inferred: it is the only spawned child that imports `schedule_policy`, and the scheduler cost shows LPM active above 128. The log does not name the process.

**Result (W = [5700, 8700) s):**

| seed | cell | token hit W | collapse | trap_v2 | uncached / all-miss | slope (thr 0.0232) | p50 / p99 latency W (s) | unfinished | queue max | longest > 128 (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | **LPM-INF** | **0.595** | no | draining | 0.84 | −0.025 | 12.0 / 210.7 | 104 | 165 | 1150 |
| 0 | stock LPM r1 / r0 | 0.000 / 0.000 | yes / yes | trapped / trapped | 1.05 / 1.00 | 0.032 / 0.035 | 218 / 263; 229 / 279 | 354 / 361 | 334 / 345 | 5820 / 5650 |
| 0 | FCFS r1 / r0 | 0.000 / 0.000 | yes / yes | trapped / trapped | 1.03 / 1.04 | 0.032 / 0.031 | 241 / 278; 235 / 271 | 370 / 366 | 356 / 342 | 6250 / 6265 |
| 1 | **LPM-INF** | **0.419** | no | indeterminate | 0.92 | 0.016 | 149.0 / 230.8 | 194 | 184 | 2780 |
| 1 | stock LPM r1 / r0 | 0.000 / 0.000 | yes / yes | trapped / trapped | 1.02 / 1.02 | 0.030 / 0.031 | 200 / 238; 199 / 238 | 318 / 317 | 290 / 287 | 6005 / 5800 |
| 1 | FCFS r1 / r0 | 0.000 / 0.000 | yes / yes | trapped / trapped | 1.03 / 1.03 | 0.028 / 0.028 | 202 / 240; 202 / 240 | 320 / 320 | 299 / 298 | 6210 / 6130 |
| 2 | LPM-INF (hook inert: queue ≤ 120) | 0.557 | no | draining | 0.88 | −0.015 | 13.5 / 113.9 | 59 | 120 | 0 |
| 2 | stock LPM r1 / r0 | 0.442 / 0.816 | no / no | indeterminate / recovered | 0.92 / 0.34 | 0.004 / −0.011 | 73 / 118; 1.6 / 31 | 105 / 11 | 122 / 121 | 0 / 0 |
| 2 | FCFS r1 / r0 | 0.000 / 0.000 | yes / yes | trapped / trapped | 1.03 / 1.03 | 0.036 / 0.036 | 213 / 256; 214 / 256 | 361 / 360 | 338 / 336 | 6475 / 6385 |

- **Latency and starvation.** No turn waited more than 600 s in any run (the INF maximum is 241 s). INF miss-turn latency over W, p50 / p99: 131 / 215 s (s0), 183 / 234 s (s1), 89 / 118 s (s2). Every unfinished INF session is a base session; all 200 burst sessions finished.
- **Token hit over time** (900-s bins, s0 / s1):
  - INF: 0.93; 0.51; 0.23 / 0.19; 0.30 / 0.29; then 0.51–0.60 / 0.30–0.44.
  - Stock r1: 0.93; 0.51 / 0.49; 0.30 / 0.12; 0.08 / 0.00; then 0.00 to the end.
- **Queue.** It first passed 128 at almost the same time in INF and stock r1 (s0: 2475 vs 2525 s; s1: 1855 vs 1865 s) and stayed above it for at least 300 s in both (INF's sustained crossings begin at 3245 and 3270 s). After that, INF's 900-s mean queue stayed at 82–168, while stock's kept growing to 255–294.
- **Timing.** The hit dip to 0.19–0.23 at 1800–2700 s comes before either queue reaches 128. So the fallback does not start the decline; it turns the decline into a collapse.

**Decision rule (frozen, exploratory):** INF does not collapse on seed 0 and does not collapse on seed 1, so the outcome is **consistent** with the 128-request fallback causing stock LPM's collapse.
- Trade-off clause, against the same-seed stock run with the same refresh flag (r1): INF has fewer unfinished sessions on all three seeds (104 vs 354, 194 vs 318, 59 vs 105) and a lower p99 over W (211 vs 263, 231 vs 238, 114 vs 118 s). No trade-off.
- Against r0, the rule's literal test fires on seed 2 only (59 vs 11 unfinished, p99 114 vs 31 s). On that seed the queue never reached 128 in any LPM run, so the hook was inert, and the difference is replicate-to-replicate variation (see below).

**Against the blind predictions** (`PREDICTIONS_r11_lpminf.md`, mixed primary):
- Collapse flag: no collapse predicted on 3/3, and the engine did not collapse on 3/3 (**match 3/3**). The predicted decision outcome, "consistent", also matches.
- Token hit: predicted 0.093 / 0.080 / 0.100, engine 0.595 / 0.419 / 0.557. The differences, 0.50 / 0.34 / 0.46, all exceed the 0.1 tolerance (**numeric miss 3/3**).
- trap_v2: trapped predicted 3/3, engine draining / indeterminate / draining (**state miss 3/3**). The predicted disagreement between the primary endpoint and trap_v2 did not occur, because the engine did not stay near the all-miss rate.
- The labelled secondary (separate batching: 0.38–0.42; s0 indeterminate, s1 trapped, s2 indeterminate) is closer. Seed 1's 0.419 lies inside its range and s0 and s2 lie above it, but it also misses the states.
- The simulator was expected to be pessimistic about LPM: it has no partial hits and no LRU touch of waiting prefixes by LPM's matching. It turned out far more pessimistic than the 0.1 tolerance allows. Its predicted unfinished counts (334 / 295 / 321) are also far off (engine 104 / 194 / 59).

**Verified vs. not:**
- Verified: the sacct records; the archive hashes on both ends; the clone's HEAD `5064580` and clean status; the hook markers and self-tests; the scheduler-cost check on seeds 0–1; identical `plan.csv` across all five cells per seed; the burst2 verdict (no guard warnings); and the evaluator (5 tests in `tests/test_r11_lpminf_eval.py` pin the numbers).
- Not verified: that the marking child is the scheduler by name (inferred, see above).
- Not verified: the run-to-run variation of the engine at a fixed configuration. Only seed 2 gives a glimpse: three LPM runs that all stayed below 128, and so all ran effectively the same configuration, gave token hit 0.44, 0.56 and 0.82.
- Not tested: any rate other than 1.65 ×, or any other seed.

**Interpretation:** Exploratory: three seeds, one rate, two informative seeds.
- On the two arrival streams where stock LPM collapsed in 4 of 4 runs, the same engine with only the 128-request switch disabled (verified active above 128) did not collapse. Token hit over the last 3000 s was 0.59 and 0.42, against 0.000, with a bounded queue and fewer unfinished sessions.
- This is the causal step the post-hoc crossing analysis could not take. It supports the reading that stock LPM's collapse at 1.65 × is caused by its silent FCFS fallback, not by LPM ordering as such.
- It does not show that pure LPM restores the good state. Seed 1 is indeterminate, with 189 requests outstanding at the end and an uncached-token rate at 0.92 × the all-miss rate, and no INF run recovers by the registered rule.
- It cannot separate the two things the fallback switches off together: LPM's ordering, and the LRU touch of waiting requests' prefixes by LPM's matching.
- It does not support a claim at other rates or a pooled estimate. With n = 2 informative seeds the result is directional only.

## 2026-10-31 — H200 cell (SGLang, 300k pool): the window compresses to (1, 1.3) × λ_ref, too narrow to register; no kill test on H200
**Question:** Does the SGLang 300k cell replicate on a different GPU (one H200 NVL instead of one A100 80GB PCIe), with the same model, revision, engine, pool and protocol? And what happens to the metastable window when the GPU is faster but the pool and the tool time stay fixed?
**Setup:** Cell `sglang-fcfs-r1-h200` (E0a `sglang-nocache-h200`): SGLang 0.5.22, Qwen2.5-7B-Instruct `a09a3545`, `KV_TOKENS=300000` (server log: `max_total_num_tokens=300000`, `context_len=49152`), FCFS with waiting-prefix refresh, `OUTPUT_FEEDBACK=server`. Hardware: nova25-gpu-3, "NVIDIA H200 NVL, 143771 MiB", driver 580.178.04. Attention backend `fa3`, SGLang's Hopper default (server log of all 20 jobs). The A100 cells ran FlashInfer. The job log's `attn=flashinfer` text is only the script default. All jobs ran from the dedicated clone `repo_h200/` at `5a6fbcd` (clean tree, push URL disabled), with `--gres=gpu:h200:1` and one run per job. All COMPLETED 0:0:
- smoke 17166807 (900 s);
- E0a 17166810–12 (POP 32, seeds 0–2) and the POP-64 check 17166813;
- Stage C 17166818–22, 828, 830, 832, 834 (n = 16, 20, 24, 28, 32, 40, 48, 96, 300; same closed protocol as the A100 Stage C: synchronized start, window [900, 2700) s);
- E0b 17168377–82 (one 3000 s from-empty run each at 1.1, 1.2, 1.3, 1.4, 1.55 and 1.75 × λ_ref).

The E0b grid was chosen after E0a by the plan's rule (`commands_corrected.sh`: R_bound = (24/68.8)/λ_ref = 1.80 < 2.2 gives "1.1 1.2 1.3 1.4 1.55 1.75"), before any Stage C or E0b result was read. Combines ran on the login node (`envs/swapp`, nice), each output dir taken from the tool's printed `out_dir`:
- calibration `agentload_analysis_miss/20261030-204701` (3 runs);
- POP-64 check `agentload_analysis_miss_popcheck/20261030-204702`;
- curve: `summarize closed --primary-label sglang-fcfs-r1-h200` over the nine runs → `agentload_analysis_closed/20261031-023040` (no guard warnings);
- bracket: `summarize stable` over the six → `agentload_analysis_stable/20261031-023042` (no guard warnings).

Data: `results/nova/h200_wave1_pulled_20261031-023416/` (`d108056`; archive sha256 `ff2f6951…` checked at both ends, remote archive deleted). Inputs copied byte-exact into `prereg/inputs/2026-10-31-h200/`, hashes checked at both ends. Cost: 16.3 GPU-h (sacct elapsed).
**Result (E0a):** λ_miss 0.1933 sessions/s, **turns-based 0.19388 ± 0.0062**; all-miss uncached tokens **29,866 ± 23 tok/s**: 2.71 × and 2.66 × the A100 cell (0.07153, 11,243). POP-64 check: tokens 31,232 (ratio 1.046, inside the runbook's 5 %); turns-based 0.2132 (ratio 1.100, outside 5 %). On the A100 300k cell the POP-64 check gave tokens +3.2 % and sessions −4 %; on the A100 native cell, turns-based −6 %. POP 32 is therefore close to saturation on the H200 but not certainly at it, and λ_ref may be a few percent low.
**Result (Stage C, one run per n):**

| n | 16 | 20 | 24 | 28 | 32 | 40 | 48 | 96 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| μ sessions/s | 0.219 | 0.279 | 0.327 | 0.369 | **0.386** | 0.329 | 0.274 | 0.218 | 0.225 |
| μ turns-based | 0.211 | 0.262 | 0.311 | 0.350 | **0.367** | 0.312 | 0.259 | 0.211 | 0.226 |
| hit fraction (turns) | 0.929 | 0.925 | 0.901 | 0.839 | 0.744 | 0.456 | 0.215 | 0.000 | 0.000 |

- Peak 0.3861 sessions/s at n = 32; n = 28 is within 4.3 % (`n_cap_ambiguous`).
- μ_max/λ_ref = **1.99** (turns-based 1.89).
- 0.5-hit crossing ≈ 38.8 (linear between 32 and 40).
- μ falls 43 % from n = 32 to n = 96, and never below 1.13 × λ_miss (sessions-based).
- Against the A100 300k cell (peak 0.233 at n = 24, μ_max/λ_ref 3.26, 0.5-hit crossing ≈ 32.1, hit 0.000 by n = 48, minimum μ 0.68 × λ_miss), the H200's cliff sits further out and is shallower.

**Result (E0b):**
- Stable at 1.1, 1.2 and 1.3 ×: final queue 0, trend −0.01, −0.03 and −2.3.
- **Unstable at 1.4 ×** (final queue 50.4, fitted rise +48.6 over the last 1500 s), 1.55 × (177.7, +115.6) and 1.75 × (272.6, +170.7).
- Bracket: largest all-stable 1.3 × (0.252 sessions/s), first unstable 1.4 × (0.271), monotone.
- The 1.4 × run sits just above the queue threshold of 50, with a clear rising trend.

**Registration rule (`836063a`, restated in the weekend's COORD rules before any H200 Stage C or E0b result was read):**
- Window (1, hi) with hi = min(μ_max/λ_ref, largest all-stable E0b multiple) = min(1.99, 1.3) = **1.3** (`hi_source: lambda_cap_e0b`).
- Points m1 = 1 + (hi − 1)/3 = 1.10 and m2 = 1 + 2(hi − 1)/3 = 1.20, rounded to 0.05.
- The `boundary_margin_rel` band is (1.1, 1.17), and neither point lies inside it. `analysis.prereg fill` therefore returns **INCOMPLETE** (`prereg/inputs/2026-10-31-h200/fill_rulecheck_INCOMPLETE.yaml`: `lambda_outside_window` for both points).
- The cap rule would have given n_cap 28 (μ(28) within 5 % of μ(32)) and a capped-drain limit of 1.73 ×. Neither of those binds; the window does.
- **No registration and no E2 for this cell**, as the rules require.
- An exploratory pair was considered and is not possible with the frozen code. `prereg derive-exploratory` needs a FILLED parent. The only FILLED 300k SGLang parent is the A100 registration, and its hardware check refuses the H200 calibration (`calibration hardware must equal the registered hardware`). Making it work would need a code change, so no BURST run was made.

**Window compression (the measurement this cell delivers):** pool (300k) and tool time (Exp(5 s)) are the same as on the A100. The H200 raises the all-miss rate 2.71 ×, but the curve's peak only 1.66 × and the from-empty edge 1.76 × (0.143 → 0.252 sessions/s).
- In units of λ_miss, the window shrinks from (1, 2.0) to (1, 1.3), i.e. from 1.0 to 0.3 λ_miss wide.
- In absolute terms it shrinks from 0.072 to 0.058 sessions/s wide.
- μ_max/λ_ref falls from 3.26 to 1.99.
- The edge as a fraction of the peak stays similar: 2.0/3.26 = 0.61 on the A100, 1.3/1.99 = 0.65 on the H200.

**Against predictions:**
1. **Simulator:** no blind simulator prediction exists for this cell.
2. **The checker's a-priori estimate** (`COORD/h200_scope_and_check.md`, written 2026-10-30 ~18:20, before any H200 job ran; not committed, so not blind by the project's standard). It expected a pool-set cliff at n ≈ 24–28 on either GPU, and put μ_max/λ_ref at 1.2–1.7 and hi at 1.1–1.5.
   - The real hi (1.3) lies inside its range.
   - The real μ_max/λ_ref (1.99) and peak (n = 32) lie above it, and above the plan's R_bound of 1.80, because the cliff moved out.
3. **The round-13 first-principles theory:** tag `r13-theory-pred`, commit `997d2c4`, pushed 02:05:30 CDT 2026-10-31, before the combine; files `notes/PREDICTIONS_r13_theory.md` and `results/theory/merged/h200_300k.json`. I read it only after the combine and the registration check. Predictions on the turns-based estimator, against the measurements:

   | quantity | predicted | measured |
   |---|---|---|
   | μ_max | 0.372 | 0.367 (−1.3 %) |
   | window | 1.92 | 1.89 |
   | peak n | ≈ 32.5 | 32 |
   | 0.5-hit crossing | 37.3 | ≈ 38.8 |
   | hit at the peak | ≈ 0.69 | 0.74 |
   | F2 edge | 1.39 × | bracket [1.3, 1.4) |

   - It also predicted that the cliff would move out while the window narrowed; it did.
   - None of its three H200 refutation conditions fires: window 1.89 < 2.4; hit(32) 0.744 ≥ 0.5; hit(48) 0.215 < 0.5.
   - Its F2 escape probabilities at the six E0b multiples (0.04, 0.12, 0.28, 0.52, 0.84, 0.98) give a log-likelihood of −1.36 for the observed outcomes.
   - Beyond the peak the real cliff is softer than predicted (fluid / annealed): μ(40) 0.312 vs 0.257 / 0.278; μ(48) 0.259 vs 0.197 / 0.201; hit(48) 0.215 vs 0.000 / 0.013.
   - The official scoring is the theory session's; these are this session's readings of the frozen file.

**Blindness scope:** the per-job n = 16–32 μ values (Stage C 17166818–22) were seen by the cell operator and Akshat at about 22:28 CDT, and not by the lead or the theory agents. n ≥ 40 and the E0b edge are fully blind. After the lead's hold (~22:40 CDT 2026-10-30), only `sacct` states were read until "theory predictions frozen" arrived (~02:25 CDT 2026-10-31).
**Verified vs. not:**
- Verified:
  - the 20 accounting records;
  - `repo_h200/` HEAD `5a6fbcd`, clean;
  - the hardware string in every banner and every analysis;
  - `fa3` and the 300k pool in every server log;
  - no Traceback, OOM or CUDA error in any server log, only SGLang's context-length warning (49,152 > 32,768), as on the A100;
  - the archive and input hashes;
  - the rule check by `fill`.
- Not verified:
  - the seed-to-seed spread of the curve and of the edge (one run per n and per multiple; the 1.4 × run is close to the stability threshold);
  - whether POP 32 saturates the H200 in turns (ratio 1.10);
  - the effect of the attention backend (fa3 here, FlashInfer on the A100) separately from the GPU.

**Interpretation:** The H200 neither refutes nor tests the mechanism. At this pool the window is too narrow for the registered rule to place two λ points at least 10 % from its edges, so no paired kill test was run. What the cell does show is that the window is not a property of the engine alone. It depends on the ratio of the pool-limited peak to the compute-limited all-miss rate. At a fixed pool and tool time, a faster GPU raises λ_miss more than it raises the peak, and the window compresses from 1.0 to 0.3 λ_miss. A larger pool widens it: 5.5 × for the A100 native pool.
**Extra Stage C (submitted after this entry's data, at the lead's request):** 17169612–14 (n = 36, 44, 52, one n per job, same protocol and label, nice 0), to bracket the theory's predicted cliff. Their predictions are frozen in `r13-theory-pred`, so they are blind. They are not part of the nine-point curve above or of the registration check.

## 2026-10-31 — H200 300k: three extra Stage C points (n = 36, 44, 52) are a blind test of the r13 cliff; the real cliff past n ≈ 38 is gradual, not abrupt
**Question:** Where exactly does the H200 300k curve fall, and does the frozen r13 theory's predicted all-miss onset (n_b 41.3; n_half 37.3) hold between the measured grid points 32, 40 and 48?
**Setup:** Jobs 17169612 (n = 36), 17169613 (44) and 17169614 (52), at the lead's request. They are one n per job, with the same protocol, label (`sglang-fcfs-r1-h200`), clone (`repo_h200` at `5a6fbcd`) and `--time=01:30:00` as the nine Stage C jobs, at nice 0. All COMPLETED 0:0 on nova25-gpu-3 (starts 02:39, 02:50, 03:15 CDT). The theory's predictions were pushed at 02:05:30 (`r13-theory-pred`), before submission (02:33), so these points are blind on everyone's side. Supplementary 12-point curve on the login node: `summarize closed --primary-label sglang-fcfs-r1-h200 --name agentload_analysis_closed_supp12` over the nine runs plus these three → `agentload_analysis_closed_supp12/20261031-040909` (no guard warnings). Data: `results/nova/h200_stageC_extra_1716961x_pulled_20261031-040933/` (archive sha256 `c069b0b8…` checked at both ends, remote archive deleted). The registration check (nine-point curve, `prereg/inputs/2026-10-31-h200/`) is unchanged.
**Result:**

| n | 32 | 36 | 40 | 44 | 48 | 52 |
|---|---|---|---|---|---|---|
| μ sessions/s | 0.386 | **0.374** | 0.329 | **0.299** | 0.274 | **0.269** |
| μ turns-based | 0.367 | **0.354** | 0.312 | **0.280** | 0.259 | **0.250** |
| hit fraction (turns) | 0.744 | **0.613** | 0.456 | **0.318** | 0.215 | **0.156** |
| r13 μ turns-based, fluid / annealed | 0.377 / 0.371 | 0.359 / 0.348 | 0.257 / 0.278 | 0.197 / 0.221 | 0.197 / 0.201 | 0.197 / 0.198 |
| r13 hit, fluid / annealed | 0.70 / 0.69 | 0.56 / 0.53 | 0.27 / 0.28 | 0.00 / 0.08 | 0.00 / 0.01 | 0.00 / 0.00 |

The peak stays at n = 32; n = 36 is the new runner-up, within 3.2 %. The 0.5-hit crossing is ≈ 38.9 (linear between 36 and 40; 38.8 from the nine-point curve).
**Against the frozen theory:**
- Up to n = 36 the theory is close: μ within 2 % (annealed −1.6 %), hit 0.53–0.56 against 0.61.
- From n = 40 on, the real curve falls gradually and the theory falls abruptly. At n = 44, 48 and 52 the theory is all-miss (hit ≤ 0.08), but the real hit is still 0.32, 0.22 and 0.16. Real μ is 1.27–1.29 × the annealed prediction at the three points, 1.29–1.45 × λ_miss (turns-based) against the theory's floor of 1.0.
- The predicted all-miss onset n_b = 41.3 is therefore too early. Measured hit only reaches 0 somewhere between n = 52 and 96.
- No refutation rule fires: the rules test the window, hit(32) and hit(48), and these points do not change any of them.
- This matches the theory's own stated likeliest failure mode (open problem 2 in `PREDICTIONS_r13_theory.md`): its eviction-age assumption does not concentrate at this pool on the H200.

**Verified vs. not:** Verified: the three accounting records, the archive hash, the 12-run combine (no guards). Not verified: seed-to-seed spread (one run per n).
**Interpretation:** The fluid model gets the rising branch and the peak of the H200 curve right blind, and the cliff's midpoint to within about 1.5 sessions. It does not get the tail past the midpoint. The real engine keeps a partial hit rate (0.16–0.32) well past the model's all-miss onset. The model treats eviction as a sharp threshold; on the real engine it is spread out. For the window this matters little, because the window is set by the peak and the E0b edge. For the paper's mechanism text, the all-miss collapse is a gradual slide on the H200 (hit 0.74 → 0.16 over n = 32–52), not a cliff at a single n.

## 2026-10-31 — H200 300k E0b reseeds at 1.3 and 1.4 ×: 1.3 × is stable in 3/3; 1.4 × is stable in 2/3, so the edge is stochastic there; the registration check is unchanged
**Question:** How firm is the H200 300k from-empty edge? The single seed-0 run at 1.4 × ended at queue 50.4, just over the threshold of 50.
**Setup:** At the lead's request, jobs 17169668 (1.3 ×, seed 1), 17169669 (1.3 ×, seed 2), 17169670 (1.4 ×, seed 1) and 17169671 (1.4 ×, seed 2). They use the same protocol (MODE=cap, one 3000 s from-empty run each), label `sglang-fcfs-r1-h200`, `CALIB_FILE` (`agentload_analysis_miss/20261030-204701`) and clone (`repo_h200` at `5a6fbcd`) as E0b 17168377–82. Nice 0, `--deadline`; all COMPLETED 0:0 on nova25-gpu-3 (starts 03:28–04:04 CDT). Supplementary 10-run bracket on the login node: `summarize stable --name agentload_analysis_stable_supp10` over the six original and four new runs → `agentload_analysis_stable_supp10/20261031-050254` (no guard warnings). Data: `results/nova/h200_e0b_reseeds_1716966x_pulled_20261031-050308/` (archive sha256 `dadb1f4f…` checked at both ends, remote archive deleted).
**Result:**
- 1.3 ×: seed 1 stable (final queue 0, trend +0.03); seed 2 stable (0, +0.26). With seed 0, **3/3 stable**.
- 1.4 ×: seed 1 stable (final queue 0, trend −0.01); seed 2 stable (0, −2.3). With seed 0 (unstable: 50.4, +48.6), **2/3 stable**.
- Ten-run bracket: largest all-stable 1.3 ×, first rate not all-stable 1.4 ×, monotone. This is the same as the six-run bracket that the registration check used.

**Against predictions:** the frozen r13 F2 escape probability (tag `r13-theory-pred`) is 0.28 at 1.3 × and 0.52 at 1.4 ×, i.e. P(stable) 0.72 and 0.48. Observed: 3/3 and 2/3. Both are consistent at three seeds. No simulator prediction exists.
**Interpretation:** The registration conclusion does not change. hi is the largest multiple at which every run is stable: still 1.3, so the rule's points stay 1.10 and 1.20, outside the margin band. But the edge is not a hard threshold. At 1.4 × an empty engine stays good in two of three seeds and escapes in one, so the edge lies in the stochastic band 1.3–1.4 ×. That is what a first-passage (escape) edge looks like, not a deterministic stability boundary. The paper should quote the H200 edge as "stable at 1.3 × in 3/3 seeds, at 1.4 × in 2/3".
## 2026-10-31 — Rescue of an established trap (R1, R4): decisive PASS in both cells, 9/9 RESCUED, no relapse, nothing shed
**Question:** Once the burst has trapped the engine (all-miss, backlog growing), does a client-side session cap at the knee of μ(n), engaged late and removed after the gate drains, bring the engine back to the good state, and does that state then persist with the cap removed at the same load (plans R1, R4)?
**Setup:** Registrations (tag `r11-rescue-reg`, `f0bc3ad`, GitHub push 22:39:02 CDT Fri): R1 `configs/agentload_prereg_2026-10-31_rescue.yaml` (cell `sglang-fcfs-r1-rescue`, 300k pool, 1.35 and 1.65 × λ_ref, cap 20 engaged at 1,800 s), R4 `configs/agentload_prereg_2026-10-31_rescue_native.yaml` (`sglang-fcfs-r1-rescue-native`, native pool, 4.0 ×, cap 64 at 2,100 s), seeds 0–2; the E2 burst (200 in [1200, 1260)), 8,700-s runs; over-cap sessions pause at the next tool call and resume before new arrivals; release at the first 10-s tick ≥ t_on + 600 s after both queues have been empty for 300 s. Per-run rule and decision rule frozen in `analysis/rescue.py` (RULE, STUCK, PROFILES, CHECK) and in the rule text. Jobs (submitted 23:01 CDT Fri, all COMPLETED 0:0, from the frozen clone `repo_r11_rescue` at `f0bc3ad`): smoke 17168965; R1 17168966–71; R4 17168972–74. In-job `analysis.rescue check-run` ok in all 10. Data `results/nova/rescue_1716896x_pulled_20261031-070502/` (archive sha256 `2ac2309c…`, `c6ea41e`). Verdicts on a clean tree with the registrations as `--prereg` and bundle 3 as `--predictions`: `…/results/agentload_analysis_rescue_r1/20261031-071720` (`be50593`), `…_r4/20261031-071748` (`454ff7a`). Controls: the committed same-seed E2 BURST / NOBURST runs (common random numbers; pairing checks clean).
**Result:** R1 **PASS at both test points** (1.35 ×: 3/3 RESCUED; 1.65 ×: 3/3), R4 **PASS** (3/3); decisive; 0 relapses, 0 late releases (so REFUTED does not apply), 0 failed sessions (the no-shed claim stands), every same-seed BURST control stuck (FU-hit 0.000 after t_on). Every run VALID: FU-hit 0.000–0.002 over the 300 s before the engage with 139–172 (R1) and 298–324 (R4) outstanding. Releases 4,550 / 3,980 / 4,400 s (1.35 ×), 4,920 / 4,430 / 4,570 s (1.65 ×), 6,000 / 5,980 / 6,140 s (R4). Post-release FU-hit 0.994–1.000, every 300-s window ≥ 0.93, uncached-token rate 0.08–0.12 × (R1) and 0.23–0.27 × (R4) the all-miss rate, RECOVERED at 8,700 s in 9/9. Hits come back within three minutes of the engage (first 60-s bin ≥ 0.8 at t_on + 120 s in 9/9); the drain of the backlog takes the rest (t_recovered 3,300–4,330 s and 5,670–5,790 s).
**Persistence (descriptive, `…/results/rescue_paper_data/20261031-071938/persistence.csv`):** with the cap removed the runs stayed good for the remaining 3,780–4,720 s (R1) and 2,560–2,720 s (R4): mean outstanding 1.9–2.8 and 8.8–11.8, in-system above the cap 0–4.5% of the time (max 27 against 20; 43–55 against 64). Over the same interval the same-seed BURST controls sat at FU-hit 0.000 with 195–317 and 1,133–1,178 outstanding; each rescue run matched its NOBURST control (follow-up counts within 7, same hit, backlog, latency and unfinished count at 8,700 s; every burst session completed).
**Costs (descriptive, `costs.csv`):** no session shed; 121–143 (R1) and 220–251 (R4) sessions paused, 386–569 s per paused session; 196–344 and 1,050–1,101 sessions waited at admission, 408–683 s on average (max 1,318 s); delay 38–78 session-h (R1) and 222–230 (R4); completed share 0.987–0.995, equal to NOBURST's; BURST: 0.50–0.81 completed and 206–1,404 sessions unfinished, 377–1,588 session-h of engine queueing. The E2 CAPPED arm (cap from t = 0, prevention) costs about the same at 300k (40–65 delay session-h) and much less at the native pool (18–21).
**Against predictions (both pushed before any rescue run started; the nine jobs started 02:23–04:27 CDT and ended 04:53–06:57 CDT Sat, after bundle 3 at 21:30:40 CDT Fri and the theory at 02:05:30 CDT Sat):** bundle 3 predicted PASS in both cells (R1 20/20 per rate, R4 `R4s_t2100` 16/20, exact plans 9/9) and 0 relapses: held. Release times inside the 20-seed band 9/9; within ±600 s of the seed's exact-plan prediction 6/6 at 300k (median +375 s, all late at 1.35 ×) and 0/3 native (+800 to +1,750 s: the GPU drains the native gate slower, as the non-blind CAPPED check warned; delay session-h 1.5–3 × predicted). Pause counts within 3 (300k) and 13 (native) of the exact predictions; completed shares equal to four decimals in 6/9. Theory (`r13-theory-pred`): RESCUED everywhere (not refuted); release within ±15% in 2/3 (1.35 ×: +18.8, +3.9, +14.9%), 3/3 (1.65 ×: +12.8, +1.6, +4.8%) and 0/3 (R4: +19.0, +18.7, +21.8% vs 5,040 s); relapse 0/9, consistent with P = 0.002 / 0.025 / ≈ 0.
**Verified vs. not:** Verified: sacct and exit codes, the check-run JSONs, archive checksum, registration binding (decisive needs every run bound to the committed file and started after its last commit: no blockers), pairing with the controls, the hardware rule. Not verified: behaviour after a release while the cap still binds (release only happens after 300 s with empty queues); other caps, engage times or an online trigger (AIMD-pause is simulation only); more than three seeds.
**Interpretation:** The trap is metastable, not absorbing: removing load by session count, at the curve's knee and without dropping anyone, moves the engine back to the high-hit branch, and the good state then sustains itself at the same arrival rate that the uncapped control cannot escape. That is the operational complement of the kill test: the same μ(n) curve that predicts the trap gives the cap that cures it. The cure costs explicit waiting (minutes per affected session), roughly 4–5 × less than the engine queueing of doing nothing; preventing the trap with the cap from the start is cheaper still at the native pool. Paper input: `notes/PAPER_INPUT_rescue.md`.

## 2026-10-31 — KV-pool sweep (A100, 150k and 600k tokens): the frozen theory hits every 600k quantity; at 150k it finds the cliff but overstates the peak by 11.5% and puts the from-empty edge too low
**Question:** Does the frozen round-13 theory (tags `r13-theory-pred` and `r13-theory-pred2`) predict, out of sample and with nothing refitted, the thrashing curve, window and from-empty edge of the calibrated A100 SGLang cell when only the KV pool changes (halved to 150,000 tokens, doubled to 600,000)? And which predictor of the cliff wins: the theory's n_half (with the tool-call term), the capacity ratio M/E_S, or the exogenous-gap closures (Che, Yao)?
**Setup:**
- Engine and clone: SGLang 0.5.22, Qwen2.5-7B, FCFS with the waiting-prefix refresh, `--max-total-tokens` 150000 / 600000, labels `sglang-fcfs-r1-p150k` / `-p600k`, from the lead's clone `$W/repo_r13_pool` at `5a6fbcd` (clean; all 30 `meta.json` record it). λ_ref 0.07153 (300k E0a, pool-independent).
- Stage C (closed, synchronized start, 900 s warmup + 1800 s, one run per n): 600k 17168864–66 (n 24–96, 300); 150k 17168867–69 (n 6–24, 300).
- E0b (from empty, 3000 s, seed 0): 600k 17168870–75 (2.5–5.0 ×); 150k 17168876–81 (1.1–1.8 ×).
- All 18 jobs COMPLETED 0:0 on nova22-gpu-[1-3]. Every server log has `max_total_num_tokens` equal to the requested pool, and the hardware string is `NVIDIA A100 80GB PCIe, 81920 MiB` in every run.
- Combined analyses on the login node: `summarize closed --primary-label <label>` gives `agentload_analysis_closed/20261031-112200` (600k) and `-112201` (150k); `summarize stable` gives `agentload_analysis_stable/20261031-112202` (600k) and `-112204` (150k). No guard warnings.
- Pulled read-only as an xz archive (sha256 `fcf51ad6…0035`, checked at both ends; remote archive deleted) into `results/nova/pool_sweep_1716886x_pulled_20261031-112342/`: run dirs, job logs (server logs), per-job and combined analyses, `logs/pm-pool-*.out`, sacct with Start/End, the submit log.
- Scoring: `experiments/r13_pool_score.py` (reads the frozen JSONs from the git tags) writes `derived/`.
**Result:**
- **600k:** μ_max 0.408 turns / 0.428 sessions at n = 48, a peak ratio of **5.71 / 5.98**. Hit is 0.92 up to n = 48, then 0.78 (56), 0.24 (64), 0.13 (80), 0.006 (96). The 0.5-hit crossing is **60.1**. E0b is stable at 2.5–4.5 × (final queue 0) and unstable at 5.0 × (queue 538, rise 321): bracket **[4.5, 5.0)**, or [4.80, 5.32) at the realized rates.
- **150k:** μ_max 0.120 / 0.118 at n = 12, a peak ratio of **1.68 / 1.65**. Hit is 0.93 at n ≤ 10, then 0.84 (12), 0.71 (14), 0.56 (16), 0.13 (20), 0.05 (24). The crossing is **16.5**. The all-miss branch gives 0.066 / 0.063 turns at 20 / 24, but 0.108 at n = 300, so the closed collapse is shallow. E0b is stable at 1.1 × and 1.2 × (queue 3.3, rise 1.4) and unstable from 1.3 × (queue 24, rise 12): bracket **[1.2, 1.3)**, or [1.36, 1.46) at the realized rates.
- The seed-0 plans arrive 6–14% above nominal.
**Against predictions** (frozen rules: turns-based, F1 μ_max/window ±10%, fluid n_half ±3, bracket steps):
- **600k: all hits.** Window 5.47 vs 5.71 (−4.2%); peak n 45 vs 48; n_half 60.03 vs 60.14; F2 edge 4.53 brackets [4.5, 5.0) exactly (A's crossing, 4.82, too). Log-likelihood of the six outcomes: F2 −0.93, A −0.54.
- **150k:**
  - Cliff: hit. n_half 16.91 vs 16.52; peak n 14, next to the measured 12; F1 hit(20) 0.133 vs 0.133 measured.
  - Height: **miss.** F1 μ_max and window +11.5% (1.87 vs 1.68). This is the declared upward bias, and the freeze lists 150k's MF margin as 0.01 s.d.
  - E0b edge: **miss** by two grid steps. F2 1.09 × predicts 1.1 × unstable (P = 0.51), but it was stable. A's crossing, 1.47 ×, is two steps the other way. Log-likelihood: F2 −2.14, A −2.95, F2 at the realized rates −3.59.
- **Refutation rules:** neither fired (150k window 1.68 < 2.5 and hit(24) 0.049 < 0.5; 600k window 5.71 ≥ 4.5 and hit(48) 0.921 ≥ 0.5).
- **Rivals (pred2 rule, nearest crossing):** the frozen n_half wins at both pools (errors +0.38 / −0.11). M/E_S errs −2.94 / −4.01 and M/E_lb −2.30 / −3.26. The T3(b) tool-call term is supported at both pools (16.52 > 15.96, 60.14 > 58.65), with only a 0.56-session margin at 150k. Che W = Z and Yao-Little cross at 26.5 / 23.9 (150k) and 105.9 / 95.7 (600k), 7–46 sessions late. At the measured near-zeros they still give hit ≈ 0.5–0.55.
- **Window law (A100/H200 × 300k/600k, plus 150k and native):**
  - Measured peak ratios (turns): A100 1.68 / 3.15 / 5.71 / 6.48 at 150k / 300k / 600k / native; H200 1.89 / 2.98 at 300k / 600k (the H200 values are as given to this cell by the H200 session, not read here).
  - Pool-doubling factor 1.81 (A100) and 1.58 (H200), against 1.67 predicted for both. H200/A100 speed ratio 0.60 at 300k and 0.52 at 600k, against 0.59 / 0.58.
  - The edge-bracket midpoint is 0.71–0.93 of the window in all six cells. The F2 bracket is right in 5 of 6; 150k is the miss.
**Verified vs. not:**
- *Verified:* 18 sacct records; clone hash and clean `meta.json`; pool size in every server log; hardware string; archive hash; no guard warnings; the frozen JSONs read from the tag objects (not a worktree); the pred2 lookups equal the frozen JSON at its points (pred2's own check; 600k n = 96 is outside the lookup and is read from the frozen JSON grid).
- *Blindness, verified from sacct and GitHub's activity log:* every job Start (06:50:13 to 10:08:26 CDT) is after both pushes (02:05:30 and 04:20:20 CDT). Eligible was 02:30:32, but nothing started before 06:50. Both prediction sets are blind in time for all 30 runs.
- *Not verified / limits:* one run per n and one seed per multiple, so the brackets are single-path outcomes (the F2 P(unstable) at 4.5 × is 0.47). The E0b grid steps differ between pools. The H200 numbers in the law table were not checked here.
**Interpretation:**
- The pool enters the theory where it says it does. The cliff position follows M/E_S plus the tool-call sessions at both pools to within half a session, and at 600k the window and edge follow too.
- The weak side is the small pool. The model's good-state height and its from-empty escape (F2) are both off at 150k, in opposite senses: the height is too high, yet the edge is too low. So F2's escape rate is too fast where the window is narrow.
- Capacity-ratio predictors of the collapse are early by 2–4 sessions, and exogenous-gap closures miss the collapse entirely, as Proposition E said.
- Numbers, scoring table, suggested paragraph and figure spec: `notes/PAPER_INPUT_pool.md`.

## 2026-10-31 — H200 at a 600k-token pool: the window reopens to (1, 2.5) × λ_ref; pre-registration filled and the paired test submitted
**Question:** On the same H200, does doubling the KV pool (300k → 600k) restore a registrable window, as the window law predicts? That completes the 2×2 (A100 / H200 × 300k / 600k). And do the frozen pred2 predictions for this cell hold?
**Setup:** The lead asked for this cell at ~03:00 CDT (Akshat's authorization for Nova use covers it).
- **Cell:** `sglang-fcfs-r1-h200-p600k`, `KV_TOKENS=600000` (server log of all 15 jobs: `max_total_num_tokens=600000`). Everything else is as in the H200 300k cell: SGLang 0.5.22, Qwen2.5-7B `a09a3545`, fa3, FCFS with refresh, nova25-gpu-3, clone `repo_h200` at `5a6fbcd`, one run per job, nice 0.
- **λ_ref:** reused from the H200 300k E0a (17166810–12; λ_miss is pool-independent: A100 300k 0.0715 vs native 0.0718).
- **Stage C:** 17169672–80 (n = 32, 40, 48, 56, 64, 72, 80, 96, 300).
- **E0b:** 17169682–87 (1.25, 1.5, 1.75, 2.0, 2.5, 3.0 ×). The default grid was chosen by the plan's rule R_bound = (n_peak/68.8)/λ_ref ≥ 3, i.e. n_peak ≥ 40. The lead's reasoning, from the frozen closed form, was n_b ≈ 13.55 + 2 × 27.76 ≈ 69 at 600k, with the 300k peak already at 32.
- **Timing:** all 15 jobs were held by `--begin=2026-10-31T05:00:00` and carried `--deadline`. All COMPLETED 0:0 (starts 05:27–08:25). The blind predictions `r13-theory-pred2` (commit `cfa7712`) were pushed at 04:20:20 CDT, before any of these jobs could start.
- **Combines** (login node; out_dirs parsed from the tools' output):
  - curve: `summarize closed --primary-label sglang-fcfs-r1-h200-p600k` → `agentload_analysis_closed/20261031-092435`;
  - bracket: `summarize stable` → `agentload_analysis_stable/20261031-092436`;
  - no guard warnings in either.
- **Data:** `results/nova/h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/` (archive sha256 `10682cc6…` checked at both ends, remote archive deleted).

**Result (Stage C, one run per n):**

| n | 32 | 40 | 48 | 56 | 64 | 72 | 80 | 96 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| μ sessions/s | 0.427 | 0.522 | **0.592** | 0.581 | 0.477 | 0.403 | 0.298 | 0.269 | 0.232 |
| μ turns-based | 0.412 | 0.505 | **0.577** | 0.569 | 0.466 | 0.379 | 0.281 | 0.254 | 0.231 |
| hit fraction (turns) | 0.930 | 0.927 | 0.897 | 0.804 | 0.654 | 0.478 | 0.227 | 0.140 | 0.000 |

- Peak 0.5917 sessions/s at n = 48; n = 56 is within 1.8 % (`n_cap_ambiguous`).
- μ_max/λ_ref = **3.05** (turns-based 2.98).
- 0.5-hit crossing ≈ 71.0 (linear between 64 and 72).
- The grid has no n = 16, 20 or 24 (`grid_incomplete`, a warning only).

**Result (E0b):** stable at 1.25, 1.5, 1.75, 2.0 and 2.5 × (final queue 0; trend 0.0 to −0.10); **unstable at 3.0 ×** (final queue 620.2, fitted rise +433). Bracket: largest all-stable 2.5 × (0.485 sessions/s), first unstable 3.0 ×, monotone.
**Pre-registration:** `configs/agentload_prereg_2026-10-31_h200_p600k.yaml`, FILLED and valid, PREREG_SHA256 `6be6e232…578e`.
- **Commit:** `4d1d431` on `r12/h200-prereg` (parent `5a6fbcd`; committed 09:26:38 CDT; GitHub `branch_creation` at 14:26:41Z = 09:26:41 CDT); merged into `r12/h200` (`e12138f`, a merge).
- **Window:** (1, 2.5) × λ_ref, with hi from E0b (`lambda_cap_e0b`; μ_max/λ_ref = 3.05 does not bind).
- **λ points:** 1.5 and 2.0 × by the ⅓/⅔ rule of `836063a`, no rounding needed, inside the band (1.1, 2.25).
- **Cap:** n_cap **48** (`smallest_within_margin`); capped-drain limit 2.87 ×.
- **Warnings only:** `n_cap_ambiguous`, `grid_incomplete`.
- **Inputs:** `prereg/inputs/2026-10-31-h200-p600k/`, copied byte-exact, hashes checked at both ends; `calibration.json` is a byte copy of the H200 300k E0a calibration.
- **Sync to Nova:** an 8 KB bundle `5a6fbcd..r12/h200-prereg`, pulled `--ff-only` into `repo_h200` while no H200 job was running. `repo_h200` is at `4d1d431`, clean.

**E2 submitted** at 09:27:44 CDT (Nova clock), after `check-job` passed for all six (λ, arm) with `--duration-s 8700 --t-burst-s 1200 --set trap_v2.eval_from_s=4500`.
- **Jobs:** 18 one-arm jobs, **17171020–17171037**, seed-major: for seed 0, 1, 2 → for 1.5 then 2.0 × → BURST, NOBURST, CAPPED.
- **Arguments:** `KV_TOKENS=600000`; `N_CAP=48` on CAPPED; `CALIB_FILE=prereg/inputs/2026-10-31-h200-p600k/calibration.json`; `--gres=gpu:h200:1 --time=03:10:00 --deadline=2026-11-01T11:40:00`; nice 0. The lead revised nice 58 → 0 because an H200 job can hold at most 4 of the 11 cap slots.
- **Script:** `$W/submit_h200p600k_e2.sh`; IDs `E2P6_*` in `h200_jobs.env`.

**Against the blind pred2 predictions** (`results/theory/pred2/h200_600k.json` at `r13-theory-pred2`; read after the combine and the registration check; turns-based estimator; tolerances of `notes/THEORY_r13_scoring.md`):

| quantity | predicted | measured | result |
|---|---|---|---|
| μ_max (annealed / F1) | 0.620 | 0.577 | +7.3 %, inside ±10 %; the freeze note expected 4–12 % high on the H200 |
| window | 3.20 (fluid 3.27) | 2.98 | +7.3 %, a hit |
| peak n | ≈ 53 (fluid 53.7) | flat top {48, 56} | a hit |
| 0.5-hit crossing | 66.6 (fluid) / 64.8 (F1) | ≈ 71.0 | +4.4 / +6.2, outside ±3: **a miss** |
| E0b bracket | [2.5, 3.0) (F2 edge 2.57 ×) | [2.5, 3.0) | equal, a hit |
| registration consequence | 1.5 / 2.0 ×, cap 48 | 1.5 / 2.0 ×, cap 48 | **exactly as registered** |

- F2 log-likelihood of the six E0b outcomes: −0.50.
- Up to n = 64 the curve matches the frozen prediction to within 7 % in μ (0.412–0.577 vs 0.419–0.609 annealed; largest gap −6.5 % at n = 56). hit is 0.93–0.65 vs 0.93–0.55.
- Past the midpoint the same soft tail as at 300k appears. hit(72) is 0.478 vs 0.147 (annealed), hit(80) 0.227 vs 0.019, hit(96) 0.140 vs 0.000. μ(72) is 0.379 vs 0.262; μ(80–96) is 0.25–0.28 vs 0.20.
- Rival scoring (pred2 §6): the frozen n_half (66.6) beats the rival M/E_S (≈ 55.5) for the measured crossing of 71.0. T3(b)'s tool-call term is supported, since 71.0 > M/E_S + (n_b − M/E_S)/2 ≈ 62.7.
- pred2's N2 rule for the 300k cell (`hit(36) ≥ 0.5 and hit(44) < 0.5`, P = 0.80) holds on the measured 0.613 and 0.318. The 300k crossing (38.9) also beats its rival (27.8).

**The 2×2 window law (μ_max/λ_ref, sessions-based; from-empty edge):**

| pool | A100 | H200 |
|---|---|---|
| 300k | 3.26; 2.0 × | 1.99; 1.3 × (1.4 × 2/3) |
| 600k | (pool-sweep cell, another session) | 3.05; 2.5 × |

On the H200, doubling the pool raises the peak 1.53 × (0.386 → 0.592), moves it out 1.5 × in n (32 → 48), and moves the edge from 1.3 to 2.5 ×.
**Verified vs. not:**
- Verified:
  - the 15 accounting records;
  - the pool size in every server log;
  - the input hashes at both ends;
  - the registration's validity, commit and push time;
  - check-job for all six (λ, arm);
  - the 18 job IDs and their submit lines (sampled with `scontrol`/`sacct`: label, pool, arm, cap, deadline, gres).
- Not verified:
  - seed-to-seed spread of the curve and of the edge (one run per n and per multiple);
  - n < 32 (not run);
  - anything about E2's outcome.

**Interpretation:** The window is set by pool and speed together. The faster GPU closes it at 300k, and doubling the pool reopens it, to an edge (2.5 ×) above the A100 300k cell's (2.0 ×). The frozen fluid model predicted the registration this cell actually produced, blind. As at 300k, it gets the rising branch, the peak and the edge, but misplaces the tail past the midpoint, where the real engine keeps a partial hit rate. The kill test now runs at 1.5 and 2.0 × λ_ref, where the frozen pred2 E2 block predicts a good NOBURST state (hit 0.932) and a trapped BURST arm (backlog ≈ 458 and 867 sessions).
**Next:** the 18 E2 jobs, about 4.5 waves of 2.5 h on the 4 H200s; first ends ≈ 12:00 Sat, last ≈ 22:00 Sat if the cap allows four at once. Pull what has finished before the VPN drops (~14:00 Sat), the rest on Sun 08:00–11:30. Then run `summarize burst2 --prereg configs/agentload_prereg_2026-10-31_h200_p600k.yaml` with the E2 overrides (`--set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500`).

## 2026-10-31 — BASIN-2 bracketed: 40 sessions absorbed, 60 trap (3/3 seeds each), 50 traps seed 1 only; pred2's rule held, its per-seed probabilities missed seed 0
**Question:** Where on the engine is the edge of the good state's basin at 1.65 × λ_ref? Registered B2: is a burst of 40 GOOD and a burst of 60 STUCK, each in ≥ 2/3 seeds (n = 50 reported, not in the rule)? And how do the frozen theory predictions (pred2: per-seed P(STUCK) from each seed's burst composition; b_c = 53.4) score?
**Setup:** Jobs 17169893-95 (n = 40), 17169896-98 (n = 60), 17169899-901 (n = 50), seeds 0-2 each, one BURST arm per job at 1.65 × (λ = 0.118031), burst uniform in [1200, 1260) s, 8700 s runs, W = [5700, 8700) s. Labels `sglang-fcfs-r1-b40/-b50/-b60`. Registrations `configs/agentload_prereg_2026-10-31_b{40,50,60}.yaml` (FILLED; tag `r14-basin2-reg` = `621d88f`, committed 01:58:38, GitHub push 02:10:48 CDT); the analysis-only fix `19c58e9` was pushed at 03:12:59, before any job. Submitted 04:21:40-41; all from `repo_r14_basin2` at `621d88f`, COMPLETED 0:0 (sacct End 12:39:49-15:10:34), A100 80GB PCIe on nova22-gpu-1/2/3; every run start-state verified, not aborted, git clean, canaries exit 0, config sha256 equal to the tagged cell configs. Pulled read-only to `results/nova/b2_1716989x_pulled_20261031-154500/` (archive sha256 `58e77d7e…`, 22,205,520 bytes, on both ends; remote deleted). Verdict: `analysis.basin classify --endpoints configs/r11_basin_predict.yaml --run-dirs <9 B2 + 6 B1> --prereg <b40 b50 b60 b100 b25>` at `4dd21e0` → `analysis/agentload_analysis_basin/20261031-154526` (baselines n = 0 / 200 found by the tool). Descriptive time course: `experiments/r14_b2_derived.py` → `analysis/derived/b2_time_course_*.csv`. Scoring against the frozen pred2 files (read from git at tag `r13-theory-pred2`): `experiments/r14_b2_score.py` → `analysis/derived/b2_scoring.{json,csv}`.
**Result:**

| n | seed 0 | seed 1 | seed 2 | hit_eval | backlog slope /s |
|---|---|---|---|---|---|
| 0 (committed) | GOOD | GOOD | GOOD | 0.934 / 0.934 / 0.921 | ≈ 0 |
| 25 (B1) | GOOD | GOOD | GOOD | 0.933 / 0.934 / 0.923 | ≈ 0 |
| **40** | **GOOD** (recovered) | **GOOD** | **GOOD** | 0.934 / 0.934 / 0.925 | -0.0005 / 0.0011 / 0.0001 |
| **50** | **GOOD** (recovered) | **STUCK** (trapped) | **GOOD** (recovered) | 0.933 / 0.000 / 0.924 | -0.0005 / 0.0456 / 0.0001 |
| **60** | **STUCK** (trapped) | **STUCK** (trapped) | **STUCK** (trapped) | 0.000 ×3 | 0.0295 / 0.0435 / 0.0396 (threshold 0.0232) |
| 100 (B1) | STUCK | STUCK | STUCK | 0.000 ×3 | 0.032-0.036 |
| 200 (committed) | STUCK | STUCK | STUCK | 0.000 ×3 | 0.028-0.036 |

n40 GOOD 3/3, n60 STUCK 3/3: **`bracketed` true**; every run bound to its registration and counted, `b2_not_counted`, endpoint problems and window mismatches empty, `registration_diff` forbidden lists empty. Seven-point curve, STUCK counts 0/3, 0/3, 0/3, 1/3, 3/3, 3/3, 3/3 at n = 0, 25, 40, 50, 60, 100, 200; each seed's chain is monotone, with the edge in (50, 60] for seeds 0 and 2 and (40, 50] for seed 1. Descriptive: the stuck runs have hit < 0.2 in every window from 1400 s (n50 s1, n60 s1) or 1500 s (n60 s0, s2), against 1300 s at n = 100; the GOOD runs' lowest 100 s window is 0.70-0.83, back above 0.8 the next window, and their hit_eval is within 0.004 of the same seed's n = 0 run; in every run all burst turns completed before W (last at 1510-1680 s in GOOD runs, 2454-4719 s in STUCK runs).
**Against predictions:** pred2 (`r13-theory-pred2` = `cfa7712`, pushed 04:20:20, 80 s before submission; blind in time). Rule: P = 0.66 (uncalibrated 0.42; frozen exchangeable layer 0.94); it held. pred2's secondary prediction, A's deterministic level crossing on the exact plans (b40 G/G/G, b50 G/S/G, b60 S/S/S), is right in 9 of 9. Primary per-seed P(STUCK) (seeds 0/1/2): b40 0.78 / 0.36 / 0.09, b50 0.86 / 1.00 / 0.22, b60 1.00 / 1.00 / 0.81. **Misses: seed 0 at n = 40 (P(STUCK) 0.78, GOOD) and seed 0 at n = 50 (0.86, GOOD).** The declared claim that seed 0 is the most trap-prone and seed 2 the least is not borne out (STUCK counts over 40-60: 1 / 2 / 1; seed 1 is the most trap-prone); seed 2's b40 GOOD and b60 STUCK both held. Mean Brier over the nine STUCK outcomes, declared predictors: primary 0.174, uncalibrated 0.259, frozen exchangeable layer 0.096, realized-background band 0.062, A's labels 0.000; not declared, scored after the fact: the frozen composition-averaged column 0.111 (not a band, so not among the declared predictors) and P = 0.5 0.250. pred2's rows for the BASIN-1 sizes (all six right) are not blind: pred2 was pushed at 04:20:20, after the B1 outcomes were first read at about 04:07. Frozen critical sizes against the per-seed edges: b_c = 53.4 lies in seeds 0 and 2's (50, 60], not in seed 1's (40, 50]; the committor 50% (49.5) and composition-averaged 50% (48.4) lie only in seed 1's. The first theory set (`r13-theory-pred`, 0.139 / 0.547 / 1.000 per seed) is the exchangeable layer. The round-7 simulator sweep (not a B2 prediction) had 50 sessions TRAPPED in 6/10 at 1.65 × its λ_miss; the engine trapped 1/3.
**Verified vs. not:** Verified: the archive hash and size of the local copy (kept only in the session scratchpad, `b2pull/b2_pull_lead.tar.xz`, not committed), re-checked again at ~16:20 together with its 388 files extracting byte-identical (cmp) to the pull dir; run identities (job, seed, burst n, label, prereg file) from meta.json, config.yaml and run_dirs_burst.txt; the jobs' in-job trap_v2 analyses agree with the registered classification run by run; the classification re-run at `4dd21e0` is identical, and `analysis/basin.py` as tagged (`621d88f`, git-less export) gives the same bracket, curve and per-run numbers (only `prereg_bound` reads False there); branch-push times from the GitHub activity API; the pred2 json and yaml at the tag are byte-identical to the `r13/pred2` worktree copies. An independent recompute from the raw `requests.csv` / `sessions.csv` / `meta.json` with no repo code (session scratchpad `b2_recompute/`, not committed) agrees: hit_eval and STUCK identical in all 21 runs (9 B2, 6 B1, 6 baselines), slope within 2e-17 /s, and for the B2 runs GOOD identical, outstanding within 5e-4, uncached-token deviation within 5e-6; every B2 config.yaml byte-identical to `621d88f` and every prereg sha256 equal to the registration at `621d88f`; no failures. Checked at pull time on Nova and recorded in `COMMANDS.txt`, not re-checkable now (the remote archive is deleted and this session does not access Nova): the Nova-side archive sha256 (same as the local copy) and the clone's clean `git status` at `621d88f`; each run's meta.json also records commit `621d88f`, dirty False. Provenance caveats: (1) the tags' own push times cannot be observed (the activity API shows no tag events), so the timing rests on the branch pushes of the tagged commits; `git ls-remote` shows the remote tags on the same tag objects as the local ones (`r14-basin2-reg` 692450e → 621d88f, `r13-theory-pred2` 6f0b504 → cfa7712), tagger dates 02:10:35 and 04:20:17; (2) the classification's meta.json says dirty = true at `4dd21e0` because `git status --porcelain` counts the untracked pull dir; `git diff HEAD` is empty for analysis/, src/ and configs/; (3) trap_v2's "outstanding" backlog is the time-mean number of requests in flight over [8400, 8700) s (`analysis/throughput.py` `outstanding_mean`), not sessions in system; the RECOVERED labels hold under either (GOOD runs' sessions in system 8.55-12.8, < 20). The baselines are six runs of the e2_170933xx pull (n = 0: jobs 17093391/97/403; n = 200: 17093390/96/402), not all 18.
**Interpretation:** At 1.65 × the basin boundary lies between 40 and 60 sessions on the engine, and it differs between seeds: seed 1 tips by 50, seeds 0 and 2 only above 50 (by 60). The theory's coarse claims hold (the bracket, and pred2's secondary deterministic crossing on the exact plans for all nine runs). The deterministic b_c = 53.4 fits only two of three seeds: it lies inside the edge interval of seeds 0 and 2 but not of seed 1, and the model's 50% points (48.4-49.5) lie inside seed 1's only, so no single frozen size fits every seed. Its primary per-seed probabilities, built on the burst cohort's peak alone, pointed at the wrong seed: seed 0's heavy burst (calibrated 53.0 and 54.1 cohorts' worth at 40 and 50) did not trap, while seed 1 at 50 did. The plan statistics that also count the realized background (A's crossing; the realized-background band) separate or score the outcomes best. The B2 stuck runs stay at zero hits through W on base sessions alone: every burst turn had completed by 4719 s. At n = 100 and 200, by contrast, burst turns still complete inside W (each run's `requests.csv`). Paper input: `notes/PAPER_INPUT_basin2.md`.
