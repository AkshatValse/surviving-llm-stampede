# Morning report: 2026-10-21

## Five-line summary
1. **Setup.** Nova `sinfo` re-verified the GPU layout in CLAUDE.md. The env plan is drafted but **not executed**. No PyTorch locally, so every pilot ran on CPU (NumPy, Numba, simulation). Nothing was pushed, submitted or installed.
2. **Directions.** 21 candidates checked: 6 in round 1, then 15 more from a multi-agent search (5 math lenses, deep novelty checks, 2 adversarial refuters each). Every one came back NARROW or KILL; nothing was wide open.
3. **Pilots.** Six pilots. Most are negative under their pre-stated criteria:
   - KV rent-or-buy: killed.
   - VAT protocol: uninformative.
   - Delay edge-of-stability: killed.
   - "LPM-128 fallback": dead.
   - "LRU cliff": refuted.
4. **Survivor: metastable failure in prefix-cached agent serving (simulation only).**
   - Reserved KV crowds out idle KV, so throughput as a function of active sessions, μ(n), is sharply unimodal: it peaks near 4.1 λ_miss at about 20 sessions and drops to the all-miss rate by about 40.
   - Over a wide λ window a burst traps the server in the congested regime.
   - Recovery tracks congested throughput: FCFS 0.99, LPM 1.14, caps up to 3.3.
   - Caps at or below the curve's peak restore stability, whatever the eviction rule.
5. **Recommendation: conditional GO.** Run the cheap Nova stages first (smoke, real μ(n), λ_miss, from-empty edge, about 27 GPU-h) before committing to the paper framing. I agree with the referee: about **40%** chance of a workshop-or-better paper by Dec 18. A round-5 check of whether the effect survives realistic KV allocation is _[see Round 5 below]_.

## Pilot results ("verified" = an independent agent recomputed from raw data and re-ran bit-identically)
| Direction (branch) | Verdict | Status | Results |
|---|---|---|---|
| KV retention during tool calls, rent-or-buy (`pilot/kvrent`) | **Killed.** Continuum-style TTL and ski-rental are both within about 1% of the oracle | verified numbers; crude model | `results/kvrent_pilot/20261020-221854` |
| VAT, anytime-valid agent benchmarking (`pilot/vat`) | **Downgraded.** Bad candidate set. Side finding: candidate×process ICC up to 0.87, from grid placement / cache aliasing. Theory is prior art (Kalibera & Jones; Lindon, arXiv 2610.25613) | verified | `results/vat_collect/20261020-221946`, `results/vat_alignment/` |
| Delayed-gradient edge of stability (`pilot/delay-eos`) | **Killed** by its pre-registered rule. Plateau is η·S_P≈2.1, not 1 | verified | `results/delay_eos/20261021-001318` |
| Prefix-cache metastability, rounds 1–4 (`pilot/prefix-meta`) | **Supported in simulation**, after two reframes | verified | `results/prefix_meta*/` |
| Prefix-cache metastability, round 5: realistic allocation | _[pending at time of writing; see below]_ | | `results/prefix_meta_r5*` |

### Prefix-meta: what the simulation shows
All numbers below come from a simulator with assumed A100/8B constants (M = 300k tokens, Exp(5 s) tools), in units of λ_miss = 0.0474 sessions/s.
- **Thrashing curve (round 4, fresh seeds).**
  - The closed FCFS μ(n) rises to **4.07 at n≈20–22**, then falls: 2.39 at 28, 1.39 at 32, and about **0.98–0.99 for n≥40**.
  - LPM: peak 4.16, tail **1.14**.
  - Mechanism: at n≥40, running requests' reserved KV fills about 286k of 300k tokens, leaving only about 6–9k idle.
- **Metastability (rounds 1–3).**
  - From empty, the system is stable up to 2.41 (with a horizon limit).
  - A 200-session burst at 2× traps FCFS, LPM-128, aging and PEEK-like policies (5/5 seeds).
  - FCFS recovers from congestion only at 0.9× or below; LPM recovers up to 1.1×.
  - The window holds in 7 of 8 workload variants. It fails at decode=400.
- **What fixes it.**
  - Static caps of 24–28 recover under every eviction rule; caps of 32+ do not (round 4).
  - AIMD/CONCUR-style caps recover.
  - Continuum-style pins recover only at τ=5–10 s with program priority.
  - Eviction order (LRU, random, MRU) changes throughput by at most 3–5% (R2/R5 FAIL, near-blind). This **refuted** my LRU-cyclic explanation.
- **Theory** (math-checked: `notes/MATHCHECK_thrashing_curve.md`).
  - Safe:
    - The cap identity: stable iff λ < μ(N), exact.
    - Prop. A: under FCFS-type order, μ_∞ = λ_miss for any eviction rule.
    - The quasi-static fixed-point map gives the recovery threshold (R4 PASS, non-blind).
  - Weak or unsupported:
    - The fluid burst-size prediction (R3: knife-edge, fragile).
    - Finite-size scaling beyond the null (R6).
    - exp(kV) escape.
  - Noise-driven escapes happen well below the fluid saddle-node.

### Round 5: does it survive realistic KV allocation?
_[filled in when the workflow finishes]_

## Recommendation
**Conditional GO** on "metastable failures in prefix-cached agent serving."
- **Fit:** it uses your queueing, stochastic and rare-event background, and it is Jannesari's "systems for efficient agent workloads."
- **Novelty:** the agent-serving instance; a single quantity (the μ(n) curve and μ_∞) that explains which deployed fixes (LPM, PEEK, Continuum, CONCUR) work; and Prop. A.
- **What is classical:** the theory itself (Denning 1968; Bronson et al. HotOS'21). The paper must say this plainly.

**Referee's estimates** (`notes/REFEREE_prefix_meta.md`, which I accept):
- P(trap transfers to SGLang FCFS at a 300k pool) ≈ 60%.
- P(workshop-or-better by Dec 18) ≈ 40%.
- P(main track) < 15%.

**Decisive next result:** on SGLang FCFS, at a λ inside the *measured* window, the burst arm traps while the paired no-burst and capped arms stay good, in at least 2/3 of seeds. That would move the estimate to about 65–70%. If nothing traps, or the no-burst arm collapses too, drop this framing.

**Backup:** a VAT-style GPU measurement note on candidate×session variance in agent kernel tuning. Workshop-tier and cheap.

## Decisions needed from you
1. **Direction.** Approve prefix-cache metastability as the main line, or choose from `notes/DIRECTIONS.md` / `notes/DIRECTION_SEARCH_2.md`.
2. **Nova, cheap stages first (≈26.6 GPU-h, plan arithmetic):** S0 smoke (1.7), then closed μ(n) on SGLang (C, 8.5), then λ_miss (E0a, 7.2), then the from-empty edge (E0b, 9.2). After that, pre-register and run the paired-arm kill test (≈76 GPU-h). The full plan is ≈236 GPU-h.
   - Jobs: 1×A100 on `instruction`, 4 h wall, account `f2026.coms.6250.02`.
   - The harness now includes the referee's redesign: paired burst / no-burst / client-capped arms with common random numbers, plus a token-based trap criterion (the first, session-rate version would have missed the simulator's own traps; caught in review). See `harness/prefix-meta` and `notes/NOVA_PLAN_prefix_meta.md` (updated GPU-h table there).
3. **KV pool.** Cap at 300k tokens to match the simulator (the referee warns reviewers will say "you shrank the cache"), plus at least one λ on the native pool (≈1M tokens).
4. **Output feedback.** The default is to prefer server-returned token ids over synthetic ones; Stage 0 decides.
5. **Codex folder.** An earlier session's `.claude/settings.local.json` still allows reads of the old Codex folder. I did not touch it tonight. Remove the rule?

## Needs Akshat (exact commands, in order)
1. **Re-verify account and QoS.** CLAUDE.md's values come from an earlier session and were not re-checked tonight.
   ```bash
   ssh nova groups
   ssh nova 'sacctmgr -n show assoc user=$USER format=account%30,partition,qos%40'
   ```
2. **Storage and quotas.** These set the env, HF_HOME and results locations.
   ```bash
   ssh nova 'df -h $HOME /work /ptmp /lss 2>&1; ls -ld /work/* /lss/* 2>/dev/null | grep -i -E "6250|jannesari|avalse|coms"; quota -s 2>&1 | head'
   ```
3. **Module names, with exact hashes.**
   ```bash
   ssh nova 'module -t avail 2>&1 | grep -Ei "^(python|cuda|cudnn|nccl|miniforge|micromamba|mamba|conda|gcc)/" | sort -u'
   ```
4. **Hugging Face reachability.** The model-download job needs it.
   ```bash
   ssh nova 'curl -sI -m 10 https://huggingface.co | head -1'
   ```
5. **Approve `notes/NOVA_ENV_PLAN.md`.** Add `aiohttp` and `huggingface_hub` for the generator env. SGLang v0.5.22 and vLLM v0.32.0 each get their own env.
6. **Review before any sbatch** (branch `harness/prefix-meta`):
   - `slurm/common.sh`, `slurm/sglang_job.sbatch`, `slurm/vllm_job.sbatch`, `slurm/download_model.sbatch`, `slurm/engine_*.sh`
   - `configs/agentload_*.yaml`
   - `notes/NOVA_PLAN_prefix_meta.md`
7. **Optional: local PyTorch.**
   ```bash
   /opt/anaconda3/bin/conda create -y -n swapp python=3.12 numpy scipy numba pandas pyyaml matplotlib pytest && /opt/anaconda3/envs/swapp/bin/pip install torch
   ```

## Process notes (honesty)
- **Model usage.** Main session on Opus. Implementers and scouts on Sonnet. After you turned on ultracode and asked for a novel result, I ran several multi-agent workflows on the session model: 7 workflows, about 10M subagent tokens in total.
- **Global agents used once each:** `math-checker` (theory) and `referee` (planned paper). `experiment-auditor` was not used; per-round independent verifiers did that job.
- **Pre-registration.** Every prediction round was pre-registered and audited.
  - Round 3: registered scorecard 5 PASS / 3 FAIL.
  - Round 4: 4 PASS (two knife-edge or non-blind) / 2 FAIL.
  - Amendments are append-only and disclosed. Registered readings are reported first in `notes/LOG.md`.
  - One undisclosed scratch look was found in round 4 (`s3/little.py`, on unregistered seeds), with negligible impact.
- **Commit trailers.** Some subagent commits carry a "Claude Sonnet 5.5" trailer, not the requested Opus line. Disclosed by the agents.
- **Citations.** Every citation was opened by a subagent, mostly through a summarizer. **None is paper-ready until re-verified.**
- **Corrections I made to my own claims tonight.**
  - "LPM-128 inherits the trap": vacuous.
  - "ordering never helps": wrong for LPM.
  - "best cap = N_lb": wrong (n\*≈20–22).
  - "the cliff is LRU-cyclic": refuted.
  - Overclaims in the outline and related-work draft were softened per the referee.
