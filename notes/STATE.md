# STATE

_Last updated: 2026-10-23 ~14:45 CDT (E0b submitted)_

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
