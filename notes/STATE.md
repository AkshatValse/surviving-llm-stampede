# STATE

_Last updated: 2026-10-21 ~15:35 CDT_

## Phase
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 5 verified rounds.
- **Now:** Stage 0 passed. Stage C is next and is awaiting approval.

## RESUME HERE
- **Stage 0 PASSED** (job 17060165). See `notes/LOG.md`, plan §"Stage 0 result" on `harness/prefix-meta`, and local results in `results/nova/s0_smoke_17060165_pulled_20261021-152347/`.
- **Stage C SUBMITTED** (approved). Jobs: 17062103 (FCFS, n=16/20/24/32), 17062104 (FCFS, n=48/96/300), 17062105 (LPM, n=48/300). When all three finish, pull `results/agentload_c_closed*/`, `results/agentload_analysis_closed*/` and `results/nova_job_logs/1706210[345]-*` to a new local dir, then run `analysis.summarize closed` over all run dirs.
- Sync the Nova clone to harness 89a3c7d or later before submitting.

Stage C commands. Run them on Nova from `/work/classtmp/avalse/swapp/repo` after `env | grep ^SBATCH_` prints nothing:
```bash
W=/work/classtmp/avalse/swapp; COMMON="ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28,OUTPUT_FEEDBACK=server,MODE=closed"
sbatch --export=ALL,$COMMON,POLICY=fcfs,N_LIST="16 20 24 32" slurm/sglang_job.sbatch
sbatch --export=ALL,$COMMON,POLICY=fcfs,N_LIST="48 96 300" slurm/sglang_job.sbatch
sbatch --export=ALL,$COMMON,POLICY=lpm,N_LIST="48 300" slurm/sglang_job.sbatch
```
- Shape: 3 jobs, each 1×A100 with a 4 h limit. Plan arithmetic is about 8.5 GPU-h.
- Each run is 900 s of warmup plus 1800 s measured.
- [redacted: other course; see provenance/REDACTIONS.md]

## Nova setup (done)
- **Project root:** `/work/classtmp/avalse/swapp`, class storage. It is deleted at semester end. Never touch the sibling `hpcml-*` dirs.
- **Repo:** `repo/` is a clone of the `harness/prefix-meta` git bundle, at bbb6a12.
  - To update it: run `git bundle create` locally, `scp` it to `swapp-harness.bundle`, then `git pull --ff-only ../swapp-harness.bundle harness/prefix-meta`.
- **Envs:**
  - `envs/swapp` (generator): pandas 3, numpy 2.4; 113 analysis tests pass.
  - `envs/sglang`: sglang 0.5.22, torch 2.14.1+cu130. The compiler-side CUDA wheels are pinned to 13.0 to match the runtime.
  - Lock files: `envs/*.lock.txt`.
- **CUDA_HOME shim:** `cuda13-home/`, built by `slurm/make_cuda_shim.sh`, for FlashInfer's JIT.
- **Model:** Qwen/Qwen2.5-7B-Instruct at revision `a09a35458c702b33eeacc393d103063234e8bc28`, in `hf/`.
- **Caches:** `cache/`. Home has a 10 GB quota.
- **Jobs so far.** All used account `f2026.coms.6250.02`; see `notes/LOG.md`.
  - 17059856: setup, OK.
  - 17060003, 17060022, 17060085: smoke attempts 1–3. Each failed at startup on a harness or toolchain issue, and each was fixed.
  - 17060165: smoke attempt 4. **PASSED.**

## Branches (local only; nothing pushed)
- `main`: notes, CLAUDE.md, LOG, MORNING.
- `pilot/prefix-meta` (worktree `.claude/worktrees/prefix-meta`): the simulator, rounds 1–5.
- `harness/prefix-meta` (worktree `.claude/worktrees/pm-harness`): the real-engine harness and SLURM scripts. This is the source of the Nova clone.
- Killed: `pilot/kvrent`, `pilot/vat`, `pilot/delay-eos`.

## Open decisions (Akshat)
- KV pool: 300k-token cap vs. native.
- ~~`OUTPUT_FEEDBACK`~~: set to **server** (Stage 0 verified that token ids are returned).
- [redacted: third-party cluster usernames and storage; see provenance/REDACTIONS.md]
- The Codex-folder read rule in `.claude/settings.local.json`.

## Next steps after Stage 0
1. Stage C: the real closed-population μ(n).
2. E0a and E0b.
3. Fill and commit the pre-registration (`configs/agentload_prereg_template.yaml`).
4. The paired-arm kill test.
5. Optional simulation round 6: block-wise partial-prefix eviction plus a d-sweep.
6. Re-verify every citation in `notes/RELATED_WORK_prefix_meta.md` before writing paper text.

Each `sbatch` needs explicit OK unless Akshat has said otherwise. For Stage 0 he said "just get everything done" (2026-10-21).
