# STATE

_Last updated: 2026-10-23 ~15:15 CDT (hand-off to the always-on PC)_

## HAND-OFF 2026-10-23 ~15:15 CDT (laptop → always-on PC). Read this first; where it conflicts with older sections below, this wins.
**Everything is pushed to `origin` (GitHub `AkshatValse/Nova-Research`):** `main`, `r6/separate-batching`, `r6/validation`. The laptop's `.claude/worktrees/` and the user-level `~/.claude` memory/agents/skills are NOT in the repo.

**E0b is running on Nova** (jobs 17084750–17084755; at 15:05 CDT three were RUNNING on nova22-gpu-[1-3] since ~14:40–15:00 and three PENDING with Slurm start estimates 16:12–16:25). Each finishes ~55 min after it starts, so all six should be done by about 17:30 CDT. Check:
```bash
ssh nova 'sacct -j 17084750,17084751,17084752,17084753,17084754,17084755 -X -o JobID,State,ExitCode,Elapsed,NodeList'
```
The local watcher that polled them was stopped with the laptop session; nothing else was watching.

**Round 6 (timing-calibrated simulator, blind predictions) was interrupted by the transfer.** Status:
- Stage 1 Port: **done**, commit `772b08f` on `r6/separate-batching` (cut from `bf20ed4`). Config key `engine.batching: mixed | separate_prefill_priority` (default mixed, bit-identical). Full suite 1019 passed, 1 skipped.
- Stage 2 Validate: **in progress, interrupted.** Branch `r6/validation` (from `r6/separate-batching`): `1cdec96` (validation harness, decision rules declared) and `58451c8` (**WIP, unreviewed, tests not run**: `src/prefixmeta/r6_validate.py`, `tests/test_r6_validate.py`, `calibration/round6_server_log_fit/validate_stagec_reserved_trace.py`). No `VALIDATION.md` yet; outputs in the laptop worktree's `results/r6_validate_stagec/` were not pulled.
- Stages 3 Predict and 4 Verify: **not started.**
- The frozen workflow script (prompts, blindness rules, protocol) is `notes/workflows/r6-blind-predictions.js`. Re-run it on the PC as a new Workflow from the Validate stage (the Port stage's result text is in that file's structure; the branch already exists), or do the stages by hand following its prompts.

**Blindness gate (decide before touching E0b results):** prediction B2 (E0b from-empty stable fractions) is blind only if `notes/PREDICTIONS.md` is committed on the r6 branch *before* anyone reads E0b results. Options: (a) finish Validate → Predict → Verify first (a few hours of local Sonnet work), then pull E0b; or (b) pull E0b now and record in `notes/LOG.md` that B2 is non-blind, keeping B3 (E2 arms) and B4 blind by committing predictions before E2 runs. (a) is preferred; (b) is acceptable if time is short. B1 (E0a) is already non-blind in time.

**Then** follow §1 below: pull E0b read-only → `analysis.summarize stable` over the six runs → `lambda_cap_bracket.json` into `prereg/inputs/2026-10-23/` → pre-registration (`--n-cap-rule smallest_within_margin`, two λ points at ⅓ and ⅔ of the window; a dry run with the real `calibration.json` and `mu_curve.json` already FILLED and validated with warnings only: n_cap=20, λ_ref=0.0715, CAPPED-arm drain limit 2.64×λ_ref) → commit → bundle to Nova → **ask Akshat before E2** (18 jobs, ≈50 GPU-h).

[redacted: unrelated unpublished project; see provenance/REDACTIONS.md]


## Phase
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 5 verified rounds; Stage 0, Stage C and E0a are done on the real engine.
- **Now:** E0b (from-empty stability edge) is in the Nova queue. Round 6 (timing-calibrated simulator, blind predictions) is running locally in the background.

## RESUME HERE (written 2026-10-23)

### 1. Nova: E0b in flight
- Jobs **17084750–17084755** (MULTS 1.25, 1.5, 1.75, 2.0, 2.5, 3.0; one run each; `--time=01:30:00`; account `f2026.coms.6250.02`), submitted 2026-10-23 ~14:40 CDT from `/work/classtmp/avalse/swapp/repo` at commit bf20ed4. `CALIB_FILE=results/agentload_analysis_miss/20261023-142433/calibration.json` (the combined 3-seed E0a calibration; λ_ref = `lambda_miss_turns_based` = 0.0715 sessions/s).
  ```bash
  ssh nova 'sacct -j 17084750,17084751,17084752,17084753,17084754,17084755 -X -o JobID,State,ExitCode,Elapsed,NodeList'
  ```
- **Blindness gate.** Do NOT pull or read E0b results until `notes/PREDICTIONS.md` is committed on branch `r6/separate-batching` (see §2), or until you decide explicitly that prediction B2 is non-blind and record that in `notes/LOG.md`.
- **When all six are done and the gate is cleared:**
  1. Pull `results/agentload_e0_cap/<ts>/` × 6, `results/agentload_analysis_stable/<ts>/` × 6 (one per job), `results/nova_job_logs/1708475[0-5]-*`, `logs/pm-sglang-1708475[0-5].out` read-only into `results/nova/e0b_1708475x_pulled_<ts>/`.
  2. Build the bracket over all six runs (login node, nice): `PYTHONPATH=src:. nice -n 19 $W/envs/swapp/bin/python -m analysis.summarize stable --run-dirs <6 run dirs> --out-root results` → `lambda_cap_bracket.json`. Copy it to `prereg/inputs/2026-10-23/`.
  3. Check: a monotone stable→unstable transition; final queues; no run aborted; canary checks passed.
- **Then pre-registration** (runbook Stage 3, `notes/E2_RUNBOOK.md`): `--n-cap-rule smallest_within_margin` (n_cap=20); 2 λ points at ⅓ and ⅔ of the window, rounded to 0.05, inside `boundary_margin_rel`; `analysis.prereg fill` then `validate`; commit; bundle to Nova (`git bundle create ... main`, `scp`, `git pull --ff-only ../swapp-main.bundle main` in `repo/`).
- **Then E2:** 18 one-arm jobs, `--time=03:10:00`, ≈50 GPU-h. **Needs Akshat's explicit OK** (large batch).

### 2. Local round 6: calibrated simulator + blind predictions (RUNNING, workflow wf_0d365a6d-17a)
- Four sonnet stages in isolated worktrees from bf20ed4: port `wip/r6-separate-batching` → branch `r6/separate-batching`; validate against Stage C; predictions B1–B4 into `notes/PREDICTIONS.md`; independent verification + leak check into `notes/PREDICTIONS_VERIFICATION.md`. Agents are forbidden from ssh, from `results/nova/e0a_*`, and from LOG entries dated 2026-10-23+.
- B1 (E0a) is non-blind in time (E0a finished 2026-10-22) but the agents could not read it; B2–B4 are blind if PREDICTIONS.md lands before E0b results are pulled.
- When it finishes: review `notes/PREDICTIONS.md`, merge `r6/separate-batching` into `main` if the full suite passes, log it.

### [redacted: unrelated unpublished project, cluster-wide accounting data; see provenance/REDACTIONS.md]

## Nova setup (updated 2026-10-23)
- **Project root:** `/work/classtmp/avalse/swapp`, class storage (deleted at semester end). Never touch the sibling `hpcml-*` dirs.
- **Repo:** `repo/` is now a clone of the NEW history (bundle `swapp-main.bundle`, main at bf20ed4). The old clone with the old hashes is kept as `repo_old_history/` (its `results/` and `logs/` were copied into `repo/`; file lists and E0a data verified identical). To update: `git bundle create swapp-main.bundle main` locally, `scp` it to `$W/swapp-main.bundle`, then in `repo/`: `git pull --ff-only ../swapp-main.bundle main`.
- **Tests on Nova's env:** `tests/test_slurm_scripts.py::test_help_has_flag_large_help_under_pipefail` fails on the login node with `OSError: Argument list too long` (ARG_MAX, not a harness bug); deselect it. The remaining 258 harness/analysis tests pass (2026-10-23).
- **Envs:** `envs/swapp` (generator; pandas 3, numpy 2.4), `envs/sglang` (sglang 0.5.22, torch 2.14.1+cu130). Lock files `envs/*.lock.txt`. CUDA_HOME shim `cuda13-home/`. Model Qwen/Qwen2.5-7B-Instruct @ a09a3545… in `hf/`. Caches in `cache/`.
- **Jobs so far** (all on account `f2026.coms.6250.02`; details in `notes/LOG.md`): setup 17059856; smoke 17060003/17060022/17060085 (failed, fixed) and 17060165 (PASSED); Stage C 17062103–17062105; E0a 17072634–17072637; E0b 17084750–17084755 (in flight).

## Multi-machine setup
- **Canonical repo:** private GitHub `AkshatValse/Nova-Research`, default branch `main`; `origin` on the laptop was missing and was re-added 2026-10-23. `jannesari-swapp` is the provenance archive (remote `archive`). **Do not delete it.** `provenance/commit-map.tsv` maps old → new hashes.
- **Commits:** no AI attribution trailers.
- **New machine:** `git clone https://github.com/AkshatValse/Nova-Research.git`, then README → "Setting up a machine". Copy the user-level `~/.claude` agents and skills, which are not in the repo.

## Branches and tags
- `main`: everything active. `r6/separate-batching`: round-6 work in progress (created 2026-10-23 by the workflow). `wip/r6-separate-batching`: the interrupted original (superseded once r6/separate-batching is merged).
- Tags `archive/*`: earlier lines and killed directions (see README).

## Open decisions (Akshat)
- E2 submission (≈50 GPU-h, 18 jobs) once the pre-registration is committed.
- KV pool: 300k-token cap vs. native (native-pool replication ≈30–40 GPU-h, not included).
- [redacted: third-party cluster usernames and storage; see provenance/REDACTIONS.md]
- The Codex-folder read rule in `.claude/settings.local.json`.
- [redacted: unrelated unpublished project, cluster-wide accounting data; see provenance/REDACTIONS.md]

## Next steps
1. E0b results → bracket → pre-registration → E2 (OK needed).
2. Round 6 predictions committed before E0b results are read.
3. Re-verify every citation in `notes/RELATED_WORK_prefix_meta.md` before writing paper text.
4. Optional: native-pool replication; patched-threshold LPM causality test.
