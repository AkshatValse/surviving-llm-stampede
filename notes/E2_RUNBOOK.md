# E0a → E0b → pre-registration → E2 paired-arm kill test (runbook; nothing below has been submitted)

- Drafted: 2026-10-22.
- Requested by: Akshat ("skip the closed-system follow-ups; go to E0a, E0b, pre-registration, and the paired-arm burst kill test").
- Approval: each stage needs Akshat's OK before its `sbatch`. The stages are sequential, because each one's inputs come from the previous one.

## Prerequisites (already satisfied)
**Engine and environment:**
- SGLang 0.5.22.
- Qwen2.5-7B-Instruct at revision a09a3545….
- CUDA_HOME shim.
- Envs under `/work/classtmp/avalse/swapp`.

**Stage 0 verified:**
- `OUTPUT_FEEDBACK=server`.
- KV cap 300k honored.
- Canary flush works.

**Stage C (`sglang-fcfs-r1`, the registered cell):**
- `mu_curve.json` is in `results/agentload_analysis_closed/` on Nova and in `results/nova/stageC_…/analysis_local/` locally.
- μ_max = 0.233 sessions/s, at n=24 (ambiguous: n=20 is within 4%).
- The throughput-implied all-miss floor is about 0.072–0.081 sessions/s (verification critic).
- So the metastable window (λ_miss, min(μ_max, E0b edge)) is expected to lie between about 1.0 and 3.1 × λ_miss. E0b sets the upper end.

**Shared exports.** Run every `sbatch` below on Nova from `/work/classtmp/avalse/swapp/repo` (sync it to the harness HEAD first). First check that `env | grep ^SBATCH_` prints nothing. Then:
```bash
W=/work/classtmp/avalse/swapp
COMMON="ALL,ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28,OUTPUT_FEEDBACK=server,KV_TOKENS=300000"
```

## Stage 1: E0a, the all-miss capacity λ_miss (1 job, ≈3.6 GPU-h, ≈3.6 h wall)
```bash
sbatch --export="$COMMON,MODE=miss,SEEDS=0 1 2" slurm/sglang_job.sbatch
```
**What it runs.**
- Prefix caching is **disabled** in the engine (`--disable-radix-cache`). The engine label is `sglang-nocache`.
- Closed population POP=32. Seeds 0, 1, 2, each 2700 s (900 s warmup plus 1800 s measured).
- One population check at POP=64 (seed 0), kept out of the average.
- The job's post-analysis writes `results/agentload_analysis_miss/<ts>/calibration.json`, which holds:
  - `lambda_miss`;
  - `lambda_miss_turns_based`, the λ reference for E0b and E2;
  - `all_miss_uncached_tokens_per_s`, the reference for trap criterion (a).

**Expected value.** About 0.07–0.08 sessions/s, from Stage C's throughput-implied floor.

**Checks before moving on:**
- Seeds agree within about 5%.
- POP=64 is within about 5% of POP=32, which confirms saturation.
- Six 300 s bins per run show no trend. At n=32 a session lives about 400 s, so the 900 s warmup should be enough. If a trend shows up, report it before using the value.

## Stage 2: E0b, the from-empty stability edge (2 jobs in parallel, ≈6.1 GPU-h, ≈3 h wall)
Run after E0a. Set `CAL` to the E0a calibration file on Nova.
```bash
CAL=results/agentload_analysis_miss/<ts>/calibration.json
sbatch --export="$COMMON,MODE=cap,POLICY=fcfs,REFRESH=1,MULTS=1.25 1.5 1.75,CALIB_FILE=$CAL" slurm/sglang_job.sbatch
sbatch --export="$COMMON,MODE=cap,POLICY=fcfs,REFRESH=1,MULTS=2.0 2.5 3.0,CALIB_FILE=$CAL" slurm/sglang_job.sbatch
```
**What it runs.**
- The registered cell: SGLang FCFS with waiting-prefix refresh on (label `sglang-fcfs-r1`).
- Open-loop Poisson sessions at `mult × lambda_miss_turns_based`, starting from an empty cache and queue.
- Each run is 3000 s with one seed, and runs are flushed and verified between multiples.

**Stability rule.** This is the simulator's rule: a run is stable if its final queue is below 50 and there is no upward trend over the last 1500 s.
- Afterwards, `analysis.summarize stable` over all six runs writes `lambda_cap_bracket.json`.
- If everything is stable up to 3.0, the upper edge comes from μ_max instead.
- Caveat: 3000 s is a finite horizon, so this is a lifetime criterion. Slow escapes are invisible to it.

## Stage 3: pre-registration (local, no GPU)
1. **Copy inputs.** Put the three input files into the repo so their paths are identical locally and on Nova, then commit them:
   `prereg/inputs/<date>/{mu_curve.json, calibration.json, lambda_cap_bracket.json}`.
2. **Fill (the formulas compute every boundary):**
   ```bash
   PYTHONPATH=src:. python -m analysis.prereg fill --template configs/agentload_prereg_template.yaml \
     --mu-curve prereg/inputs/<date>/mu_curve.json --calibration prereg/inputs/<date>/calibration.json \
     --e0b-bracket prereg/inputs/<date>/lambda_cap_bracket.json --e2-config configs/agentload_e2_burst.yaml \
     --lambda-mults <m1> <m2> --rule "<how the points were chosen>" --out configs/agentload_prereg_<date>.yaml
   PYTHONPATH=src:. python -m analysis.prereg validate configs/agentload_prereg_<date>.yaml
   ```
3. **Commit, then sync.** Commit the filled file **before** the first E2 job, then bundle and pull it on Nova. The E2 job script refuses to start unless the file is valid, committed, clean and matches the job's label, multiples, cap, reference rates, hardware and protocol.
4. **Choosing the λ points.** This is the lead's decision. Proposed rule: with lo=1 and hi = the window's upper edge in multiples of λ_ref:
   - m1 = lo + ⅓(hi − lo);
   - m2 = lo + ⅔(hi − lo);
   - both rounded to 0.05 and both at least the template's `boundary_margin_rel` from each edge.
5. **Choosing the CAPPED arm's cap.** Proposed cap: **n=20**, the smallest n whose μ is within the 5% argmax noise margin. That is μ(20)=0.224 against μ(24)=0.233; n=24 showed one degraded excursion and is closer to n_fit=28.4.
   - Implementing it needs a small change: an explicit, recorded `--n-cap-rule smallest_within_margin` option in `analysis.prereg fill`. Today the tool always takes the argmax, which is 24.
   - The alternative is to keep 24 with no code change.

## Stage 4: E2, the paired-arm kill test (one arm per job: 18 jobs for 2 λ points, ≈49.6 GPU-h)
```bash
CAL=prereg/inputs/<date>/calibration.json; PRE=configs/agentload_prereg_<date>.yaml
for m in <m1> <m2>; do for s in 0 1 2; do for arm in burst noburst capped; do
  EXTRA=""; [ "$arm" = capped ] && EXTRA=",N_CAP=<registered n_cap>"
  sbatch --export="$COMMON,MODE=burst,POLICY=fcfs,REFRESH=1,MULTS=$m,SEEDS=$s,ARMS=$arm,CALIB_FILE=$CAL,PREREG_FILE=$PRE,ENGINE_LABEL=sglang-fcfs-r1$EXTRA" slurm/sglang_job.sbatch
done; done; done
```
**What each job runs.** One 8700 s run:
- warmup to t_b = 1200 s;
- the BURST and CAPPED arms add 200 fresh sessions within 60 s;
- 7500 s after the burst.

The three arms for one (m, seed) share arrivals and session specs. That is the common-random-numbers design.

**Verdict.** `analysis.summarize burst2 --prereg $PRE` reports per λ point:
- **TRAPPED:** the post-burst uncached prefill-token rate is within ±15% of E0a's all-miss rate, **and** the backlog slope is above 0.5 × (λ − λ_miss).
- **PASS:** BURST trapped, NOBURST good, CAPPED recovered, in at least 2/3 seeds.
- **Kill:** no registered λ passes. The mechanism does not transfer under this protocol.

**Concurrency.** 18 jobs at 1 GPU each. The per-user cap is 11 GPUs, shared with the COMS 6720 project, so this means about 2 waves, roughly 6 h wall plus queue time.

## GPU-hour summary
These use the plan's formula: 0.25 h startup + runs + 180 s gaps + 150 s per-run overhead + 0.05 h teardown.

| Stage | Jobs | GPU-h | Wall time (if not queued) |
|---|---|---|---|
| E0a (λ_miss) | 1 | 3.6 | ≈3.6 h |
| E0b (from-empty edge) | 2 | 6.1 | ≈3 h, in parallel |
| Pre-registration | 0 | 0 | local |
| E2, 2 λ × 3 seeds × 3 arms | 18 | 49.6 | ≈6 h, 2 waves |
| **Total (2 λ)** | 21 | **59.3** | ≈13 h plus queue |
| *Alternative: E2 with 3 λ* | 27 | 74.5 (total 84.1) | ≈8–9 h for E2 |

**Remaining budget questions:**
- **Native-pool replication** (about 1M tokens, which answers the "you shrank the cache" objection): not included. It needs its own Stage C, E0b and E2 point, about 30–40 GPU-h.
- **vLLM:** not included; it needs its own env and calibration.
