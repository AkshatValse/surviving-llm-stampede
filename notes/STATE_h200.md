# H200 cell: live state (branch `r12/h200`)

Cell `sglang-fcfs-r1-h200` (E0a `sglang-nocache-h200`):
- **Engine and model:** SGLang 0.5.22, Qwen2.5-7B-Instruct a09a3545.
- **Configuration:** 300k-token KV pool, FCFS with waiting-prefix refresh.
- **Hardware:** nova25-gpu-3 ("NVIDIA H200 NVL, 143771 MiB", driver 580.178.04), attention backend fa3 (the Hopper default).
- **On Nova:** clone `/work/classtmp/avalse/swapp/repo_h200` at `5a6fbcd`; job IDs in `/work/classtmp/avalse/swapp/h200_jobs.env`.

## Outcome (2026-10-31 ~03:00 CDT)
- **Window (1, 1.3) × λ_ref: not registrable.** The rule's points 1.10 and 1.20 fall outside the margin band (1.1, 1.17), and `fill` returns INCOMPLETE. No registration, no E2, no exploratory pair (`derive-exploratory` cannot use the A100 parent with the H200 calibration). LOG entry 2026-10-31 "H200 cell"; paper input `notes/PAPER_INPUT_h200.md`.
- **Wave 1 is pulled and committed:** `results/nova/h200_wave1_pulled_20261031-023416/` (`d108056`). It holds smoke 17166807, E0a 17166810–12, POP-64 17166813, Stage C 17166818–22, 828, 830, 832, 834 and E0b 17168377–82.
- **Registration inputs and rule check:** `prereg/inputs/2026-10-31-h200/`.
- **Extra Stage C 17169612–14 (n = 36, 44, 52): pulled.** `results/nova/h200_stageC_extra_1716961x_pulled_20261031-040933/`; supplementary 12-point curve `agentload_analysis_closed_supp12/20261031-040909`; LOG entry "three extra Stage C points".

## Blindness scope (agreed with the lead)
The per-job n = 16–32 μ values (Stage C 17166818–22) were seen by the cell operator and Akshat at about 22:28 CDT, and not by the lead or the theory agents. n ≥ 40 and the E0b edge are fully blind. The read hold (lead, ~22:40 CDT Fri) lasted until "theory predictions frozen" (~02:25 CDT Sat; tag `r13-theory-pred` pushed 02:05:30). Only `sacct` states were read during the hold.

- **E0b reseeds 17169668–71 (1.3 / 1.4 ×, seeds 1, 2): pulled.** `results/nova/h200_e0b_reseeds_1716966x_pulled_20261031-050308/`; ten-run bracket `agentload_analysis_stable_supp10/20261031-050254`. 1.3 × is stable 3/3 and 1.4 × is stable 2/3; hi stays 1.3. LOG entry "E0b reseeds".

- **600k-pool cell `sglang-fcfs-r1-h200-p600k` (lead's request (b), the 2×2 test of the r13 window law): Stage C 17169672–80 and E0b 17169682–87 pulled** into `results/nova/h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/`; curve `agentload_analysis_closed/20261031-092435`, bracket `agentload_analysis_stable/20261031-092436`.
  - Window (1, 2.5) × λ_ref; μ_max/λ_ref 3.05.
  - **Registered:** `configs/agentload_prereg_2026-10-31_h200_p600k.yaml`, commit `4d1d431` on `r12/h200-prereg` (pushed 09:26:41 CDT; merged into `r12/h200`), PREREG_SHA256 `6be6e232…578e`. Points 1.5 and 2.0 ×, n_cap 48.
  - E0b grid reasoning (the lead's, recorded as asked): the grid is a design choice, not a prediction. The default grid applies when R_bound = (n_peak/68.8)/λ_ref ≥ 3, i.e. n_peak ≥ 3 × 68.8 × 0.19388 = 40.0. The frozen closed form n_b = λ_miss·z̄′·(E[T]−1) + M/E_S gives 13.55 + 2 × 27.76 ≈ 69 at 600k, and the 300k H200 peak was already at n = 32, so n_peak ≥ 40 comfortably.
  - Blindness: tag `r13-theory-pred2` (tag object `6f0b504`, commit `cfa7712`) was pushed at 04:20:20 CDT (GitHub, per the lead; seen by `git ls-remote` at 04:21:51), before the p600k `--begin` of 05:00. Its files were read only after the p600k combine. The lead's message of ~04:25 quoted the H200-600k headline predictions, so the operator knew them before any p600k result existed. That does not affect blindness in time, and the registration is mechanical (rule of `836063a`).
- The n = 36/44/52 points (17169612–14) are blind in time against `r13-theory-pred`, whose curve already covered them.

## Still on Nova (not pulled) — as of 12:25 CDT Sat, before the ~14:00 VPN drop
- **p600k E2: 18 one-arm jobs 17171020–17171037**, submitted 09:27:44 CDT, seed-major:
  - seed 0 = 17171020–25 (1.5 × BURST, NOBURST, CAPPED, then 2.0 ×);
  - seed 1 = 17171026–31;
  - seed 2 = 17171032–37.
  - Each runs with `--time=03:10:00 --deadline=2026-11-01T11:40:00`, nice 0, `--gres=gpu:h200:1`; about 2 h 29 min per job. Slurm drops any job not started by Sun 08:30.
  - Submit script `$W/submit_h200p600k_e2.sh`; IDs `E2P6_*` in `$W/h200_jobs.env`. Each job's run dir is listed in `results/nova_job_logs/<job>-*/run_dirs_burst.txt`.
  - **Pulled already (part A):** 17171020–22 (seed 0, 1.5 ×, all three arms; COMPLETED 0:0, ended 11:56–12:03) in `results/nova/h200p600k_e2_partA_1717102x_pulled_20261031-120927/` (archive sha256 `c492385e…`; each run's `meta.json` carries PREREG_SHA256 `6be6e232…`). Not yet analysed.
  - **Pulled (part A2):** 17171023–25 (seed 0, 2.0 ×; COMPLETED 0:0, ended 14:26–14:33) in `results/nova/h200p600k_e2_partA2_1717102x_pulled_20261031-154207/` (archive sha256 `b867996b…`; PREREG_SHA256 `6be6e232…` in each `meta.json`).
  - **Still on Nova (15:50 CDT):** 17171026–28 running since 14:27 / 14:27 / 14:33; 17171029–37 pending.
  - [redacted: third-party cluster usernames and storage; see provenance/REDACTIONS.md]
- **Staging dirs** `/work/classtmp/avalse/swapp/pull_staging_h200*` (uncompressed copies; each archive deleted after its hash check).

## Sunday resume plan (VPN back ~08:00 CDT; results freeze 12:00)
1. **Check the jobs:** `ssh nova 'sacct -X -n -j 17171020,...,17171037 -o JobID,State,ExitCode,Start,End'`. Any job dropped by its deadline or failed is reported as not run.
2. **Verdict on the login node** (in `repo_h200`, which is at `4d1d431`, clean). Take RUNS_E from `results/nova_job_logs/<id>-*/run_dirs_burst.txt` of the 18 IDs, then run:
   `PYTHONPATH=src:. $PYG -m analysis.summarize burst2 --run-dirs $RUNS_E --out-root results --set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500 --prereg configs/agentload_prereg_2026-10-31_h200_p600k.yaml`
   Parse the printed `out_dir`.
3. **Pull read-only:** the remaining 15 run dirs (17171023–37; part A already holds 17171020–22), their job-log dirs, `logs/pm-e2h6-*.out`, `sacct` for all 18 and the verdict dir. Use tar + `xz -T2`, sha256 on both ends, `tar --force-local`, then delete the remote archive. Put it in `results/nova/h200p600k_e2_partB_1717102x_pulled_<ts>/`, before 11:30. If some jobs have not finished, pull what has and say which are missing; the verdict needs all 18.
4. **Write it up:** a LOG entry (verdict table, against the pred2 E2 block, verified vs. not), a verdict section in `notes/PAPER_INPUT_h200.md`, and an update here. Commit, push `r12/h200`, and message the lead.

## Lead change and reconnect (2026-10-31 ~15:40 CDT)
- Report to the new lead session **nova-lead-2** (`local_8c823c00-db19-4b39-b611-f9ce5f65891f`) from now on; the old lead ran out of context.
- Nova's VPN was reconnected Sat 15:38 CDT. Assuming the same ~12 h window, it drops around 03:38 Sun. E2 jobs are pulled in batches as they finish, and the verdict runs once all 18 have ended (expected ≈ 00:30 Sun).

## Missing-seed rule and finish estimate (15:50 CDT Sat)
- **Expected finish:** at the measured 2 h 29 min per job with three H200s, waves end ≈ 17:00, 19:30, 22:00 and 00:30 Sun.
- **Slurm's estimates** (17171035 at 11:44 Sun; 036/037 N/A) are serial and use the 3:10 limit. Real starts have not been serial: 17171023/24 both started at 11:57:17.
- **Registered rule** (trap_v2): pass_fraction_min 2/3 and min_seeds 3, per λ cell. A seed with an arm missing counts as a failure (listed under `incomplete`). A cell whose seed is missing entirely has n_seen = 2 and prints INSUFFICIENT, so it is not decisive.
- **Pending jobs are not reordered or touched.**

## Nova access window
- Lead, 2026-10-31 ~02:10 CDT: Nova is reachable over a VPN that Akshat reconnected. It drops automatically around 14:00 CDT Sat. Pull every finished result before 13:30; anything that ends later waits for the next reconnect.
- Lead, ~03:20 CDT Sat: Akshat reconnects on Sun ~08:00 CDT. Results that finish after Saturday's ~14:00 drop are pulled Sun 08:00–11:30; results freeze at 12:00. Every submission, including any p600k E2, must go in before ~14:00 Sat, because submitting needs the VPN.
