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

## Still on Nova (not pulled)
- **E0b reseeds** (lead's request (a), 2026-10-31 ~03:05 CDT), label `sglang-fcfs-r1-h200`, same CALIB_FILE, nice 0:
  - 17169668: 1.3 ×, seed 1
  - 17169669: 1.3 ×, seed 2
  - 17169670: 1.4 ×, seed 1
  - 17169671: 1.4 ×, seed 2

  They are supplementary: 1.4 × seed 0 is unstable, so hi cannot rise above 1.3.
- **New cell `sglang-fcfs-r1-h200-p600k`** (lead's request (b): the 2×2 test of the r13 window law; KV_TOKENS=600000; reuses the H200 E0a calibration):
  - Stage C 17169672–80 (n = 32, 40, 48, 56, 64, 72, 80, 96, 300), `--begin=2026-10-31T05:00:00`, nice 0.
  - E0b 17169682–87 (1.25, 1.5, 1.75, 2.0, 2.5, 3.0 ×, one multiple per job, same `--begin`, nice 0). Submitted ~03:15 CDT on the lead's instruction without waiting for `r13-theory-pred2`.
  - Grid reasoning (the lead's, recorded as asked): the grid is a design choice, not a prediction. The default grid applies when R_bound = (n_peak/68.8)/λ_ref ≥ 3, i.e. n_peak ≥ 3 × 68.8 × 0.19388 = 40.0. The frozen closed form n_b = λ_miss·z̄′·(E[T]−1) + M/E_S gives 13.55 + 2 × 27.76 ≈ 69 at 600k, and the 300k H200 peak was already at n = 32, so n_peak ≥ 40 comfortably.
  - The `--begin` keeps every p600k result after the pred2 freeze; the lead will say if pred2 slips past 05:00.
  - If the window registers: register on `r12/h200` and submit the 18 E2 jobs at nice 58, `--time=03:10:00`, `--deadline=2026-11-01T11:40:00`, before ~14:00 Sat.
- **`--deadline` on every job submitted from 03:00 Sat on** (2026-11-01T10:00 for the 1:30 jobs), so Slurm drops any that have not started by Sun 08:30.
- **Staging dirs** `/work/classtmp/avalse/swapp/pull_staging_h200_*` (uncompressed copies; each archive deleted after its hash check).

## Nova access window
- Lead, 2026-10-31 ~02:10 CDT: Nova is reachable over a VPN that Akshat reconnected. It drops automatically around 14:00 CDT Sat. Pull every finished result before 13:30; anything that ends later waits for the next reconnect.
- Lead, ~03:20 CDT Sat: Akshat reconnects on Sun ~08:00 CDT. Results that finish after Saturday's ~14:00 drop are pulled Sun 08:00–11:30; results freeze at 12:00. Every submission, including any p600k E2, must go in before ~14:00 Sat, because submitting needs the VPN.
