# STATE

_Last updated: 2026-10-22 ~13:20 CDT_

## Phase
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 5 verified rounds.
- **Now:** Stages 0 and C are done (real thrashing curve verified). Next GPU batch awaiting approval.

## RESUME HERE
- **Stage C is done and verified.** Results are in `notes/LOG.md` (2026-10-22 entry) and `notes/STAGEC_VERIFICATION.md`. Data: `results/nova/stageC_1706210x_pulled_20261022-125454/`.
- **Headline:**
  - The real SGLang thrashing curve is unimodal. Peak n≈20–24, at about 0.23 sessions/s.
  - Hit rate falls to 0 at n≥48 (engine-confirmed). The all-miss floor is about 0.075 sessions/s, roughly 3× below the peak.
  - Hit fractions at n≤24 match the simulator within 0.01.
  - Metastability is not yet tested.
- **Akshat chose (2026-10-22):** skip the closed-system follow-ups. Go E0a, then E0b, then pre-registration, then the E2 paired-arm kill test. Runbook with exact commands and GPU-h: `notes/E2_RUNBOOK.md` on `harness/prefix-meta`, about 59 GPU-h total with 2 λ points. **Awaiting OK to submit E0a.**
- (Superseded) choose and approve the next GPU batch. The ranked list is in the LOG entry. My suggested order:
  1. Pre-aged-start harness work (local, no GPU).
  2. E0a λ_miss at the stationary mix.
  3. Replicates plus hysteresis at n=24/28/32.
  4. E0b, pre-registration, then the E2 paired-arm kill test.

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
