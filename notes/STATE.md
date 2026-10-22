# STATE

_Last updated: 2026-10-22 ~14:00 CDT (moving to an always-on PC)_

## Phase
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 5 verified rounds.
- **Now:** Stages 0 and C are done (real thrashing curve verified). Next GPU batch awaiting approval.

## RESUME HERE (written 2026-10-22 ~14:00, just before moving to an always-on PC)

### 0. Migrating to the new machine (do this first)
- **Nothing has a remote; every branch is local only.** Copy the WHOLE directory `/Users/akshat/research/jannesari-swapp`, including:
  - `.git/` (all branches);
  - `results/` (gitignored: about 200+ MB of pulled Nova data and simulator outputs);
  - `.claude/` (project agents and settings).
- After copying to a new path, run `git worktree repair` from the repo root, or delete `.claude/worktrees/` and run `git worktree prune`. Recreate worktrees as needed from these branches:
  - `harness/prefix-meta`: the real-engine harness. It is the source of the Nova clone.
  - `pilot/prefix-meta`: the simulator, rounds 1–5, clean.
  - `wip/r6-separate-batching`: the simulator's SGLang-style separate prefill/decode batching mode. **UNREVIEWED, interrupted mid-implementation, tests not run.**
  - Killed directions: `pilot/kvrent`, `pilot/vat`, `pilot/delay-eos`.
- **Optional, Akshat's call:** create a private GitHub remote and push every branch, so future moves are trivial.
- On the new PC, check these:
  - **Python.** This Mac used `/opt/anaconda3/bin/python` with NumPy 1.26, SciPy, pandas 2.2, Numba, matplotlib, PyYAML, pytest and aiohttp. Update the paths in CLAUDE.md.
  - **SSH.** The `ssh nova` alias must work non-interactively (`ssh -o BatchMode=yes nova true`). A ControlMaster session or keys is fine; never handle passwords.
  - **Lost on the move:** the scratchpad (`/private/tmp/...`) and the workflow journals (`~/.claude/projects/...`). Everything needed from them has been copied into the repo.

### 1. Nova: E0a is in flight
- **Jobs.** 17072634 (POP=32, seed 0) was RUNNING at 13:49. 17072635 (seed 1), 17072636 (seed 2) and 17072637 (POP=64 check) were PENDING. All have a 1.5 h limit.
  ```bash
  ssh nova 'sacct -j 17072634,17072635,17072636,17072637 -X -o JobID,State,ExitCode,Elapsed,NodeList'
  ```
- **When all four are done:**
  1. Pull the run dirs read-only (`results/agentload_e0_miss/<ts>/` × 4, `results/agentload_analysis_miss/<ts>/`, `results/nova_job_logs/1707263[4-7]-*`) to a new local dir.
  2. Check: the 3 seeds agree within about 5%; POP=64 is within about 5% of POP=32; there is no trend across 300 s bins.
  3. Build the combined `calibration.json` from the 3 POP=32 run dirs. On the Nova login node with nice: `$W/envs/swapp/bin/python -m analysis.summarize miss --run-dirs <3 dirs> --warmup-s 900 --out-root results`.
- **Then E0b** (Akshat authorized "submit everything you think is best"): 6 parallel one-run jobs, `--time=01:30:00`, `MULTS` = each of 1.25 1.5 1.75 2.0 2.5 3.0, with `CALIB_FILE` set to the combined file. Commands are in `notes/E2_RUNBOOK.md` on `harness/prefix-meta`; split `MULTS` into one value per job.
- **Then pre-registration** (runbook Stage 3):
  - Use `--n-cap-rule smallest_within_margin`, which gives n_cap=20. It was added in harness commit fe48315.
  - 2 λ points at ⅓ and ⅔ of the window.
  - Copy the inputs into `prereg/inputs/<date>/`, commit, and sync to Nova.
- **Then E2:** 18 one-arm jobs, each with `--time=03:10:00`.

### 2. Local round 6: timing-calibrated simulator plus blind predictions (INTERRUPTED)
- **Done:** calibration from SGLang server-log timing only. Decode R² 0.992, prefill R² 0.998, median error about 1%; the assumed constants were about 55% too high. Files: `calibration/round6_server_log_fit/` (`calibration.yaml`, scripts, `CALIBRATION_REPORT.md`). Large parsed pickles: `results/sim_calibration_round6/`.
- **Not done:**
  - Finish and test `wip/r6-separate-batching`.
  - Validate against Stage C μ(n), out of sample.
  - Make blind predictions (B1 E0a, B2 E0b, B3 E2 arms, B4 native pool) and commit `PREDICTIONS.md` **before** looking at the matching real results.
  - Independent verification.
  - The original workflow script is described in `notes/LOG.md` (round-6 entry). Rerun those stages on the new PC.
- **Blindness after the move:**
  - B1 (E0a) can no longer be time-blind. E0a will finish first, so treat B1 as non-blind unless the prediction agents are provably walled off from E0a data.
  - B2–B4 stay blind if `PREDICTIONS.md` is committed before E0b and E2 results are read.
  - **Suggested order:** commit predictions before submitting E0b, or at least before pulling its results.

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
