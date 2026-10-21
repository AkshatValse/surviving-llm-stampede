# STATE

_Last updated: 2026-10-21 ~10:45 CDT (laptop going to sleep; the Nova job keeps running)_

## Phase
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 5 verified rounds.
- **Now:** Nova Stage 0, the SGLang smoke test. Attempt 4 is submitted.

## RESUME HERE
1. **Check the smoke job.** Job **17060165** was PENDING at 10:45.
   ```bash
   ssh nova 'sacct -j 17060165 -X -o JobID,State,ExitCode,Start,Elapsed,NodeList,Account%22'
   ```
   - Log: `/work/classtmp/avalse/swapp/repo/logs/pm-sglang-17060165.out`.
   - Run dir: `/work/classtmp/avalse/swapp/repo/results/nova_job_logs/17060165-*/`. It holds `server.log`, `probe.txt`, `flag_check.txt` and `banner.txt`.
   - Smoke results: `/work/classtmp/avalse/swapp/repo/results/agentload_s0_smoke/<ts>/` and `agentload_analysis_windows/<ts>/`.
2. **If it COMPLETED:**
   - `rsync` the run dir and results back to a NEW local timestamped dir under `results/nova/`. This is read-only on the Nova side. Class storage is wiped at semester end.
   - Go through plan §4 items a–m. Three are already verified:
     - (a) flags exist;
     - (e) a 49152-token context is accepted, with a warning;
     - (f) the KV cap of 300000 tokens is honored.
   - Still open:
     - where `cached_tokens` appears (`probe.txt`);
     - whether output token ids come back (`PROBE_SUMMARY.output_ids_present`), which decides `OUTPUT_FEEDBACK`;
     - metric names (`metrics_first.txt`);
     - whether the canary flush works;
     - startup time and the GPU name.
   - Then fill in the unverified items in `notes/NOVA_PLAN_prefix_meta.md` (branch `harness/prefix-meta`) and propose Stage C.
3. **If it FAILED:**
   - Read `server.log`.
   - If FlashInfer's JIT still fails, resubmit the same command with `ATTN_BACKEND=triton` added to `--export`. It needs no external compiler; record the deviation from SGLang's default.
   - Each failed attempt has cost about 1–2 GPU-minutes.

**Exact resubmit command.** Run it on Nova from `/work/classtmp/avalse/swapp/repo`. Check `env | grep ^SBATCH_` first; it must print nothing.
```bash
W=/work/classtmp/avalse/swapp; sbatch --time=01:30:00 --export=ALL,MODE=smoke,ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28 slurm/sglang_job.sbatch
```

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
  - 17060165: smoke attempt 4.

## Branches (local only; nothing pushed)
- `main`: notes, CLAUDE.md, LOG, MORNING.
- `pilot/prefix-meta` (worktree `.claude/worktrees/prefix-meta`): the simulator, rounds 1–5.
- `harness/prefix-meta` (worktree `.claude/worktrees/pm-harness`): the real-engine harness and SLURM scripts. This is the source of the Nova clone.
- Killed: `pilot/kvrent`, `pilot/vat`, `pilot/delay-eos`.

## Open decisions (Akshat)
- KV pool: 300k-token cap vs. native.
- `OUTPUT_FEEDBACK`: decided from the Stage 0 probe.
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
