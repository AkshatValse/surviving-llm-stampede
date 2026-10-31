# Llama-3.1-8B cell: live state (branch `r12/llama31`)

Cell: SGLang 0.5.22 + NousResearch/Meta-Llama-3.1-8B-Instruct @ d10aef7 (shards byte-identical to meta-llama 0e9e39f2), 300k-token pool, one A100 80GB PCIe, label `sglang-fcfs-r1-llama31`. Owner: the Llama session started 2026-10-30 22:15 CDT by the lead ("arXiv paper draft for NOVA"). Rules: `Nova-Research-wt/COORD/COORDINATION.md`; plan: `COORD/llama31_wave1_handoff.md`, `COORD/model2/commands_corrected.sh` (step by step), checker problems in `COORD/model2_scope_and_check.md`.

## Nova
- Clone `$W/repo_llama31` at `5a6fbcd` (branch `gen/llama31`, push URL disabled). Submit log `$W/submit_llama31.log` (PD=2026-10-30-llama31).
- Download 17166805 COMPLETED (refs/main d10aef7, four shard sha256 OK).
- GPU jobs, all `--mem=48G`, pending at 22:30 Fri (QOSMaxGRESPerUser, every one of the 11 per-user GPUs busy):
  - E0a POP 32 seeds 0/1/2: 17166823, 17166829, 17166831; POP-64 check 17166833 (nice 62)
  - Stage C 17166814 (n 16 20 24), 17166815 (28 32 40), 17166816 (48 96 300) (nice 63)
  - smoke 17166808 (nice 64)
- Calibration (CPU) 17168803, afterok 17166823:29:31, kill-on-invalid-dep, script `$W/gen_llama31_calib.sh` (the corrected file's heredoc, sha256 40a30d59...), writes `results/cal_llama31/calibration.json`.
- Nice: the brief said 54, but job age adds about 3 priority points per hour and these jobs were 4 h older than the basin/rescue jobs, so at 54 they ranked above B1/R1 (nice 50-52), against COORDINATION's order. Set to 62-64 instead: below B1/R1 (188088-188090), above LPM-INF and fresh-seed E0b (188081-188082). Within the cell, E0a first (it feeds the calibration, E0b and the blind prediction), then Stage C, then the smoke.

## Blind prediction (round 12)
- Branch `r12/llama31-predict` (from `origin/main` 582c2a6), worktree `Nova-Research-wt/llama31-predict`. Spec declared and pushed before any Llama GPU job started: `cce2d0b` (22:31:57 CDT), `configs/r12_llama31_predict.yaml` (sha256 f78e6963...), real inputs and V1 factors null.
- Next: when E0a's 3-seed calibration exists, fill real inputs, run the factor check, freeze the factors (second commit), run V0 + V1 in both modes, write `notes/PREDICTIONS_llama31.md`, tag `r12-llama31-predictions-frozen`, push. Until the tag is pushed: no reading of `logs/pm-l31-c-*.out`, `logs/pm-l31-e0b-*.out`, `results/agentload_analysis_{closed,stable}` or any Stage C / E0b run directory.

## Next steps
1. Pool check on the first running job (`max_total_num_tokens=300000` in every server.log; banner model/revision/hardware; MaxRSS).
2. Calibration (n_runs 3, label, hardware, cached 0) + POP-64 token ratio <= 1.05.
3. E0b grid: default 1.25 1.5 1.75 2.0 2.5 3.0 unless R_bound = (24/68.8)/lambda_ref < 3.0; one multiple per job, `--mem=48G`.
4. Registration on `r12/llama31` (label sglang-fcfs-r1-llama31, smallest_within_margin, 1/3-2/3 rule), push, bundle into repo_llama31, check-job, 18 jobs seed-major `--time=03:10:00`.
5. Verdict: burst2 --prereg with the E2 overrides; LOG; `notes/PAPER_INPUT_llama31.md`.
Deadline: results by Sun 2026-11-01 12:00 CDT; cancel unstarted jobs at Sun 08:30.
