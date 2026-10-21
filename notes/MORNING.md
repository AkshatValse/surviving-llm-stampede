# Morning report: 2026-10-21

## Five-line summary
1. Setup is done. Nova `sinfo` re-verified the CLAUDE.md GPU layout. The env plan is drafted but **not executed**. PyTorch is not installed locally, so every pilot was CPU (NumPy/Numba/simulation).
2. I checked **21 candidate directions**: 6 in round 1, then 15 more from a multi-agent search (5 math lenses → deep novelty checks → 2 adversarial refuters each). Every one came back NARROW or KILL. Nothing was wide open.
3. Five pilots ran. Four were **negative or killed** under their pre-stated criteria:
   - KV rent-or-buy
   - VAT protocol comparison (badly designed candidate set)
   - delay–edge-of-stability
   - the first form of the prefix-cache claim (the "LPM-128 fallback")
4. The survivor is **metastable failure in prefix-cached agent serving.**
   - In a continuous-batching simulator, a finite burst permanently flips the server from a high-hit state to an all-miss state, across a wide λ window.
   - FCFS-type orderings provably cannot escape. LPM helps only for tool calls shorter than the congested KV lifetime.
   - Only working-set caps restore stability, and under LRU they sit on a cliff.
   - Every number was independently re-computed and re-run bit-identically. **It is simulation only.**
5. **Recommendation:** pursue it, conditional on a cheap real-engine kill test on Nova (≈42 GPU-h through the decisive gate). The harness and job scripts are written but **not submitted**.

## Pilot results (verified = recomputed from raw data and re-run by an independent verifier)
| Direction | Verdict | Status | Where |
|---|---|---|---|
| KV retention during tool calls, rent-or-buy (branch `pilot/kvrent`) | **Killed** (pre-stated criterion met: Continuum-TTL and ski-rental within ~1% of the oracle) | verified numbers, crude model | `results/kvrent_pilot/20261020-221854` |
| VAT: anytime-valid tuning of agent benchmarks (`pilot/vat`) | **Downgraded.** Protocol comparison was uninformative (candidate set badly designed). Side finding: candidate×process variance with ICC up to 0.87, explained by grid placement / cache aliasing. The stats theory is prior art (Kalibera & Jones; Lindon arXiv 2610.25613) | verified | `results/vat_collect/20261020-221946`, `results/vat_alignment/` |
| Delayed-gradient edge of stability (`pilot/delay-eos`) | **Killed** by its pre-registered rule: delayed Adam plateaus at η·S_P≈2.1, not 1; β₁=0.99 *increases* the penalty | verified (HVP vs exact Lanczos, bitwise reruns) | `results/delay_eos/20261021-001318` |
| Prefix-cache metastability, rounds 1–3 (`pilot/prefix-meta`) | **Reframed, then supported in simulation** | verified | `results/prefix_meta*/` |
| Prefix-cache metastability, round 4 (thrashing curves, fluid predictions) | see "Round 4" below | — | `results/prefix_meta_r4*/` |

**Key simulation numbers** (assumed A100/8B-order constants, M = 300k tokens):
- λ_miss = 0.0474 sessions/s.
- From-empty stable limit 2.44 λ_miss.
- After a 200-session burst at 2 λ_miss, hit rate is 0.000 for FCFS, LPM-128 and aging in 5/5 seeds. The length-biased cap gives 0.90.
- Recovery from congestion:
  - FCFS recovers only below about 1.0 λ_miss (150k-s horizon; **it fails at the registered 30k-s horizon**).
  - LPM recovers up to about 1.1 λ_miss.
  - AIMD/CONCUR-style caps recover at 2 λ_miss.
  - Continuum-style pins recover only at τ = 5–10 s with program priority.
- The metastable window holds in 7 of 8 workload variants (it fails at decode = 400).

**Round 4** (thrashing curves μ(n), eviction variants, fluid predictions R1–R6): _[filled in below when it finishes]_

**Theory** (`notes/THEORY_v3_thrashing_curve.md` plus `notes/MATHCHECK_thrashing_curve.md`, checked by `math-checker`):
- Safe to state:
  - The cap identity μ_cap(n) = μ(min(n,N)), which is exact.
  - Statement A: under FCFS-type order with any eviction rule, congested throughput equals λ_miss.
  - The quasi-static fixed-point map.
  - The length-biased working set (formula corrected).
- **Not safe** without more work:
  - "ordering never helps" (wrong for LPM when tool calls are short);
  - best cap = N_lb (the peak is at n*≈20–22);
  - the burst-size predictor;
  - exp(kV) escape as a theorem.
- A birth–death model built from the measured μ(n) predicts escape times within about 2× across two decades. That was a math-checker sanity run on an uncommitted tree; it must be re-run cleanly before citing.

## Recommendation (confidence: moderate, about 55–60% that this becomes a workshop-or-better paper by Dec 18)
**Pursue "metastable failures in prefix-cached agent serving."**

Reasons to pursue:
- It uses your queueing, stochastic-process and rare-event strengths: the thrashing curve, metastability, and escape times.
- It sits squarely in Jannesari's "systems for efficient agent workloads".
- The decisive experiment is cheap.

The novelty is the *agent-serving instance* plus the unified explanation of why deployed fixes (LPM, PEEK, Continuum, CONCUR) do or don't work. The underlying theory is classical (Denning 1968; Bronson et al. HotOS'21), and the paper must say so.

**What would change my mind:**
- **The real-engine kill test fails.** SGLang FCFS is not trapped by a burst in ≥2/3 runs at any λ in (1.2, 2)·λ_miss. Causes could be partial radix prefixes, SGLang's waiting-prefix refresh, or vLLM's lazy eviction.
- **Scoop risk.** The Ao/Simchi-Levi group (arXiv 2606.15555, v3 posted 2026-10-20) works on instability of LLM serving. They don't yet cover prefix caching.

**Backup if the kill test fails:** the VAT measurement note, a workshop-tier GPU measurement of candidate×session variance in agent kernel tuning. It is weaker but cheap.

## Decisions needed from you
1. **Direction:** approve prefix-cache metastability as the main line, or pick another from `notes/DIRECTIONS.md` and `notes/DIRECTION_SEARCH_2.md`.
2. **Nova Stage 0 → gate 2:** approve about 42 GPU-h. Stage 0 smoke is 1.6 GPU-h, then calibration about 15.6, then the kill test about 24.5. Each job uses 1×A100 on `instruction`, 4 h wall, account `f2026.coms.6250.02`. The full grid would add about 90 GPU-h after gate 2.
3. **E2 timing (deviation D1):** use the short protocol (4 h jobs; trap judged over 3000 s, and may confuse slow drain with trap) or the literal one (9 h jobs, about 356 GPU-h total).
4. **KV pool:** cap it at 300k tokens to match the simulator (current plan), or use the native pool (about 1M tokens; needs proportionally bigger bursts).
5. **Pre-register the real-engine predictions** (recommended). I'll write them before any run.
6. **Prior session's Codex folder:** CLAUDE.md previously pointed to it, and `.claude/settings.local.json` still allows reads of it. I did not touch it tonight. Should the allow-rule be removed?

## Needs Akshat (exact commands, in order)
1. **Re-verify the account and QoS.** They come from an earlier session and were not re-checked tonight.
   ```bash
   ssh nova groups
   ssh nova 'sacctmgr -n show assoc user=$USER format=account%30,partition,qos%40'
   ```
2. **Storage and quotas.** These decide the env, HF_HOME and results locations.
   ```bash
   ssh nova 'df -h $HOME /work /ptmp /lss 2>&1; ls -ld /work/* /lss/* 2>/dev/null | grep -i -E "6250|jannesari|avalse|coms"; quota -s 2>&1 | head'
   ```
3. **Module names with exact hashes.**
   ```bash
   ssh nova 'module -t avail 2>&1 | grep -Ei "^(python|cuda|cudnn|nccl|miniforge|micromamba|mamba|conda|gcc)/" | sort -u'
   ```
4. **Can compute nodes reach huggingface.co?** This is needed for the model download job.
   ```bash
   ssh nova 'curl -sI -m 10 https://huggingface.co | head -1'
   ```
5. **Approve `notes/NOVA_ENV_PLAN.md`.** Add `aiohttp` and `huggingface_hub` to the generator env. SGLang v0.5.22 and vLLM v0.32.0 each get their own env.
6. **Review before any sbatch.** All of these are on branch `harness/prefix-meta`:
   - `slurm/common.sh`
   - `slurm/sglang_job.sbatch`, `slurm/vllm_job.sbatch`, `slurm/download_model.sbatch`
   - `slurm/engine_*.sh`
   - `configs/agentload_*.yaml`
   - `notes/NOVA_PLAN_prefix_meta.md`
7. **Local PyTorch (optional).** Only needed if we revive an MPS-based direction.
   ```bash
   /opt/anaconda3/bin/conda create -y -n swapp python=3.12 numpy scipy numba pandas pyyaml matplotlib pytest && /opt/anaconda3/envs/swapp/bin/pip install torch
   ```

## Process notes (honesty)
- **Model usage:**
  - The main session used Opus.
  - Implementers and scouts used Sonnet.
  - Several multi-agent workflows ran on the default (session) model, after you turned on ultracode and asked for novelty. That spent heavily: roughly 7–8M subagent tokens in total.
  - `math-checker` was used once. `referee` was used once (see below). `experiment-auditor` was not used; the workflow verifiers did that job.
- **Commit trailers:** some subagent commits carry a "Claude Sonnet 5.5" trailer instead of the requested Opus line. The subagents disclosed this.
- **Pre-registration integrity** was audited each round. Two round-3 predictions flip between their registered and amended readings (P1: FAIL→PASS on horizon; P7: FAIL→not evaluable). The registered readings are what count, and they are reported first in `notes/LOG.md`.
- **Unverified pages:** every literature citation was opened by a subagent, mostly through a summarizer. None is paper-ready until re-verified.
- **Nothing pushed, nothing submitted, nothing installed.**
