# STATE

_Last updated: 2026-10-24 ~15:25 CDT (always-on PC; the primary host since 2026-10-24)_

## NOW (2026-10-24 ~15:25 CDT). Read this first; it supersedes the 2026-10-23 hand-off below.
**E2 is in the Nova queue: jobs 17093387–17093404** (18 one-arm jobs, submitted 15:13 CDT under Akshat's explicit authorization in chat, 2026-10-24). Order is seed-major (seed 0: mult 1.35 burst/noburst/capped = 17093387–89, mult 1.65 = 17093390–92; seed 1 = 17093393–98; seed 2 = 17093399–404). `--time=03:10:00`, one 8700 s arm each. At submission Slurm estimated starts from 19:20 tonight to 11:11 on 2026-10-25 (the partition had 120 pending jobs), so all should finish by about 14:00 on 2026-10-25. Check:
```bash
ssh -F ~/.ssh/isu_nova_config nova 'sacct -j 17093387,17093388,17093389,17093390,17093391,17093392,17093393,17093394,17093395,17093396,17093397,17093398,17093399,17093400,17093401,17093402,17093403,17093404 -X -o JobID,State,ExitCode,Elapsed,NodeList'
```
**HARD RULE until all 18 have finished: do not change `repo/` on Nova** (no bundle pull, no edits). Each job validates the pre-registration and runs whatever code is checked out when it *starts*; `repo/` is clean at `d279b7b`. If a job FAILS at its pre-engine checks, read its `logs/pm-sglang-<id>.out`, fix locally, and only then decide about the rest.

**Round 7 started 2026-10-24 ~23:10 CDT ("complete everything ASAP"; Akshat authorized multiple jobs and Codex agents):**
- **Second Nova clone `repo_next/`** (`/work/classtmp/avalse/swapp/repo_next`, cloned from `repo/` at `d279b7b`) is where every NEW job is submitted, so `repo/` stays frozen for E2. Results of new jobs land in `repo_next/results/`.
- **Native-pool pipeline (required by the plan):** Stage C closed μ(n) with `KV_TOKENS=native` (label `sglang-fcfs-r1-native`) on n = 24, 48, 64, 80 (job **17096856**) and 96, 128, 300 (**17096857**); E0a native (`sglang-nocache-native`, 3 seeds + POP 64, **17096858**). Next: native E0b (mults of the native λ_ref, wide grid up to ~6.5 ×, since the simulator puts the native knee near n = 64-80), a blind simulator prediction for the native window committed before native E0b is read, native pre-registration (`prereg fill --engine-cell-label sglang-fcfs-r1-native`), native E2.
- **`repo_next/` moved to `5e0ed83` at 23:30** (exploratory grid registrations merged). The three native jobs above were still pending, so they run on `5e0ed83`; the change touches only burst-mode validation and `burst2`, which closed/miss modes never reach (each run's meta.json records its commit). Rule from now on: update `repo_next/` only when no pending job's mode is affected, and say so here.
- **Exploratory policy grid submitted 23:33** (merged `r7/grid-prereg`: `prereg derive-exploratory`, registrations `configs/agentload_prereg_2026-10-24_grid_{sglang-fcfs-r0,sglang-lpm-r1,sglang-lpm-r0}.yaml`, BURST arm only, mults 1.35/1.65, seeds 0-2): jobs **17097086–17097103** on `instruction` with `--nice=5000` so later native-pool jobs schedule ahead. Verdict per cell: `summarize burst2 --prereg <grid file>` over its 6 runs (exploratory, per-run TRAPPED/RECOVERED/neither). **Scavenger is unusable:** the site's submit filter rejects `f2026.coms.6250.02` on `scavenger` ("Invalid account or account/partition combination") although `sacctmgr` lists the QoS.
- **Local, in worktrees `Nova-Research-wt/<name>` on branches `r7/<name>`:** Codex: `grid-prereg` (exploratory per-cell registrations so the BURST-only policy grid sglang-fcfs-r0 / sglang-lpm-r1 / sglang-lpm-r0 can run), `baselines` (PEEK / Continuum / CONCUR re-implementations vs released code). Sonnet workflow `r7-paper-evidence` (wf_988bfde1-955): `robustness` (tool-time sweep incl. heavy tails, burst-size sweep, horizon, low-λ fragility, Wilson CIs), `citations` (audit, `paper/refs.bib`, scoop check), `traces` (real agent-trace workload statistics), `vllm-prep` (vLLM env and job scripts, `notes/VLLM_RUNBOOK.md`). Review each branch before merging into `main`.
- **Peek at E2 (per-job analyses, 12 of 18 runs, the registered rule unchanged):** BURST trapped in 3 of 4 (hit 0.000, token rate 1.01-1.03 × all-miss, backlog 200-330); the fourth (1.35 ×, seed 1) is stuck at zero hits but its slope 0.0036 is under the 0.0125 threshold, so "indeterminate". Every NOBURST and CAPPED run recovered (hit 0.93, backlog ~10). The verdict waits for all 18.

**Recovery 2026-10-25 ~00:15 CDT** (Claude desktop exited about 23:57–00:04 CDT and stopped two local workers; recovery under the instruction "continue interrupted work; no resubmission, no duplicate workers, no merge, no push"):
- Nothing remote was lost or resubmitted. At 00:12: E2 15/18 COMPLETED (0:0), 17093402–04 RUNNING (from ~23:58); native 17096856–58 and grid 17097086–103 PENDING. `repo/` clean at `d279b7b`, `repo_next/` clean at `5e0ed83`.
- The orphaned E2 watcher (PID 30288, could no longer notify) was stopped and replaced by one watcher for all 24 outstanding jobs (`watch_r7.sh` in the session scratchpad): it wakes the session on any job failure, on E2 all done, on each native job done, and on the grid all done.
- Local workers: `robustness` had FINISHED (result in the workflow journal; branch `r7/robustness`, 6 commits); the baseline-verification agent was resumed with its context (branch `r7/baselines`: reviewed switches committed as `d80519c`, many audit cells already done); `citations`, `traces`, `vllm-prep` were restarted from their worktree checkpoints by resuming workflow `wf_988bfde1-955` (robustness replayed from cache, not re-run). No `r7/*` branch is merged or pushed yet; each needs review first.
- **Baseline audit finished 00:25** (`r7/baselines`: `d80519c` switches, `dc76032` numbers; summary `results/prefix_meta_baselines_audit_summary/20261025-001850/tables.md`; default path bit-identical to `main` on all golden digests and 180 extra cells). Verdicts for the paper: PEEK is not "= FCFS at 1.01x": with the released warm-first order it equals LPM at ~1.17x (still no recovery above 1.1x); Continuum pins become 2.6 / 3.5 / 4.4x for tau = 5 / 10 / 20 under the preview's waiting-allocation rule (the old tau = 20 failure was an idle-GPU artefact; "eager unpin fails" tested a rule the preview lacks); CONCUR's 3.03x holds only as a surrogate of its equation and is sensitive to the usage signal. The static-cap result is untouched. Not merged.
- **The other round-7 branches finished ~00:45 (none merged or pushed; each passed its own tests):** `r7/robustness` (`notes/ROBUSTNESS_r7.md`: kill test PASS at all 10 points of five tool-time laws; no trap releases over 31,200 s; bursts of 25 never trap, 100+ always stick; the declared slope test, not the trap, is the fragile part: 1 in ~7 stuck runs at 1.35x is "indeterminate"); `r7/traces` (`notes/lit/AGENT_TRACES.md`: TraceLab and mini-SWE-agent v2; real tool times have medians 15-33x shorter than Exp(5 s) and CV 4-5; configs `configs/workload_trace_*.yaml` need 8c08883); `r7/citations` (`notes/lit/CITATION_AUDIT_2026-10-25.md`, `paper/refs.bib` 48 verified entries; 1 misattribution and 5 overstatements fixed in RELATED_WORK; scoop risks: Yao et al. arXiv 2609.02027 mean-field LRU for multi-turn sessions; ThunderAgent and NVIDIA Dynamo already ship session-aware admission with hysteresis, so the cap must be compared with them); `r7/vllm-prep` (`notes/VLLM_RUNBOOK.md`, vLLM 0.32.0, ~21 GPU-h; found a Qwen2 rotary-cache overflow past 32k and that vLLM's flush returns 200 with success:false: `flush_cache` in `common.sh` should check the body). **Hold lifted by Akshat 2026-10-25 ~01:50 ("you are free to do as you see fit"). At 01:53 all five branches were merged into `main` without conflicts (robustness, traces, baselines, citations, vllm-prep; grid-prereg earlier); merged suite 1288 passed / 32 failed (exactly the documented Windows set) / 2 skipped; `main` and the `r7/*` branches pushed. `repo_next/` synced to `6d0dad7` (job code paths unchanged: only a new analysis table script). vLLM chain submitted from `repo_next/` at 01:56: install (CPU) **17097972** → GPU check **17097973** (afterok) → smoke **17097974** (afterok); next per `notes/VLLM_RUNBOOK.md`: read the smoke logs, then E0a (MODE=miss), `derive-exploratory --engine-cell-label vllm-fcfs --calibration <vLLM E0a>`, 6 BURST jobs. (Historical:)** Merge order when allowed: robustness and traces first (traces configs need 8c08883), then citations (rebase; reconcile its PEEK wording with the baseline audit), baselines, vllm-prep.
- **Real-trace tool-time laws in the simulator finished 01:34** (on `r7/robustness`, `ca165a0`..`b530e55`; spec `configs/r7_traces_sim.yaml` committed before the runs, all declared stages on clean `c515f0c`; `notes/ROBUSTNESS_r7_traces.md`). Record workload with only the tool-time law replaced by each trace's empirical table: lambda_miss unchanged within ~1% for every law; windows non-empty ([1, 2.25] TraceLab per-turn, [1, 2.0] TraceLab idle gap, [1, 3.0] mini-SWE-agent); the closed-curve peak (and so the right cap) moves to n = 32 / 40 for TraceLab, and CAPPED recovers at those caps. Declared paired test: PASS at 8 of the 10 points; the TraceLab per-turn 1.40x FAIL is the slope rule (all 10 BURST runs stuck at hit 0, 4 indeterminate; 17/20 trapped on fresh seeds, post hoc); 100/100 BURST runs stuck. The secondary mini-SWE-agent FULL workload breaks the declared protocol (sessions outlive the 1800 s lambda_miss window and the 3000 s edge horizon); a labelled post-hoc adjusted rerun gives a narrower window [1, 1.5] and PASS at 1.35x. For the paper: the cap must be set from the measured curve of the actual workload, not fixed at 20.

**Done since the laptop hand-off (details: `notes/LOG.md`, three 2026-10-24 entries):**
- Round 6 finished and merged (`78ebbee`): VALIDATION.md (level test NO in both modes, shape reproduced, mixed picked), PREDICTIONS.md frozen at `64bc4e3` (tag `r6-predictions-frozen`, pushed 14:53 CDT before E0b was read), independent verification by a Codex stand-in (`877b936`; strict B3-inside-B2 containment fails, explained).
- E0b read (`cfbc702`): stable through 2.0 × λ_ref, unstable at 2.5 × and 3.0 ×. B2 is consistent; B1 matches E0a to 1–3%.
- Pre-registration `configs/agentload_prereg_2026-10-24.yaml` (`d279b7b`): λ points 1.35, 1.65 × λ_ref; n_cap 20; PREREG_SHA256 `2a6d680a…`.

**When all 18 E2 jobs have finished (the next session's job):**
1. Pull read-only, as for E0b: on Nova `tar` the 18 run dirs (`results/agentload_e2_burst/<ts>/`), the per-job analyses, `results/nova_job_logs/170933*`, `logs/pm-sglang-170933*.out` into one archive, `xz` it, `sha256sum`, `scp` it (the PC's link is ~100 KB/s: always compress), check the hash, extract with `tar --force-local` into `results/nova/e2_170933xx_pulled_<ts>/`, delete the remote archive.
2. Verdict on the login node (nice, `envs/swapp`), with exactly the overrides the jobs used (the registered rule must equal the applied one): `PYTHONPATH=src:. nice -n 19 $W/envs/swapp/bin/python -m analysis.summarize burst2 --run-dirs <all 18> --out-root results --set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500 --prereg configs/agentload_prereg_2026-10-24.yaml`. The 18 run dirs are listed in `results/nova_job_logs/170933*/run_dirs_burst.txt`. The jobs' own per-job burst2 sees one arm each and is not the verdict. Pull the verdict dir too.
3. Compare with B3 in `notes/PREDICTIONS.md` (predicted PASS at both points, both modes), log it, commit, push. Then decide with Akshat what follows (paper figures; the native-pool replication; LPM cells).

## HAND-OFF 2026-10-23 ~15:15 CDT (laptop → always-on PC). SUPERSEDED by the block above; kept for the record.
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
- **Direction:** approved 2026-10-21. Metastable failures in prefix-cached agent serving. Simulation evidence covers 6 rounds (round 6: calibrated simulator, validated against Stage C, blind predictions B1–B4); Stage 0, Stage C, E0a and E0b are done on the real engine.
- **Now (2026-10-24):** E2, the pre-registered paired-arm kill test, is in the Nova queue (jobs 17093387–17093404). See NOW above.

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
- **Repo:** `repo/` is a clone of the NEW history, at **`d279b7b`** since 2026-10-24 15:12 CDT (do not move it while E2 runs). The old clone with the old hashes is kept as `repo_old_history/` (its `results/` and `logs/` were copied into `repo/`; file lists and E0a data verified identical). To update from the PC (slow link, ~100 KB/s up and down): an **incremental** bundle `git bundle create swapp-main-incr.bundle <nova HEAD>..main`, `scp` it to `$W/`, `sha256sum` both ends, then in `repo/`: `git pull --ff-only ../swapp-main-incr.bundle main`. The full bundle is `swapp-main.bundle` (2026-10-23).
- **Tests on Nova's env:** `tests/test_slurm_scripts.py::test_help_has_flag_large_help_under_pipefail` fails on the login node with `OSError: Argument list too long` (ARG_MAX, not a harness bug); deselect it. The remaining 258 harness/analysis tests pass (2026-10-23).
- **Envs:** `envs/swapp` (generator; pandas 3, numpy 2.4), `envs/sglang` (sglang 0.5.22, torch 2.14.1+cu130). Lock files `envs/*.lock.txt`. CUDA_HOME shim `cuda13-home/`. Model Qwen/Qwen2.5-7B-Instruct @ a09a3545… in `hf/`. Caches in `cache/`.
- **Jobs so far** (all on account `f2026.coms.6250.02`; details in `notes/LOG.md`): setup 17059856; smoke 17060003/17060022/17060085 (failed, fixed) and 17060165 (PASSED); Stage C 17062103–17062105; E0a 17072634–17072637; E0b 17084750–17084755 (done, pulled 2026-10-24); E2 17093387–17093404 (queued 2026-10-24 15:13).

## Multi-machine setup
- **Canonical repo:** private GitHub `AkshatValse/Nova-Research`, default branch `main`; `origin` on the laptop was missing and was re-added 2026-10-23. `jannesari-swapp` is the provenance archive (remote `archive`). **Do not delete it.** `provenance/commit-map.tsv` maps old → new hashes.
- **Commits:** no AI attribution trailers.
- **New machine:** `git clone https://github.com/AkshatValse/Nova-Research.git`, then README → "Setting up a machine". Copy the user-level `~/.claude` agents and skills, which are not in the repo.

## Branches and tags
- `main`: everything active. `r6/separate-batching`: round-6 work in progress (created 2026-10-23 by the workflow). `wip/r6-separate-batching`: the interrupted original (superseded once r6/separate-batching is merged).
- Tags `archive/*`: earlier lines and killed directions (see README).

## Open decisions (Akshat)
- ~~E2 submission~~: authorized 2026-10-24 and submitted (17093387–17093404).
- Whether to merge-review round 6 further: the Codex verifier's unapplied wording patch for PREDICTIONS.md (B2 headline should state the operational trend rule) is in `C:\Users\Akshat\Documents\Codex\2026-10-24\cl\work\prediction-fixes.patch`; apply only as an explicit amendment, never by rewriting the frozen file.
- KV pool: 300k-token cap vs. native (native-pool replication ≈30–40 GPU-h, not included).
- [redacted: third-party cluster usernames and storage; see provenance/REDACTIONS.md]
- The Codex-folder read rule in `.claude/settings.local.json`.
- [redacted: unrelated unpublished project, cluster-wide accounting data; see provenance/REDACTIONS.md]

## Next steps
1. E2 results → `summarize burst2` verdict over all 18 → compare with B3 (see NOW).
2. ~~Round 6 predictions committed before E0b results are read~~ (done: tag `r6-predictions-frozen`).
3. Re-verify every citation in `notes/RELATED_WORK_prefix_meta.md` before writing paper text.
4. Optional: native-pool replication; patched-threshold LPM causality test.
