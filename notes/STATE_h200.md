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

## Blindness scope (agreed with the lead)
The per-job n = 16–32 μ values (Stage C 17166818–22) were seen by the cell operator and Akshat at about 22:28 CDT, and not by the lead or the theory agents. n ≥ 40 and the E0b edge are fully blind. The read hold (lead, ~22:40 CDT Fri) lasted until "theory predictions frozen" (~02:25 CDT Sat; tag `r13-theory-pred` pushed 02:05:30). Only `sacct` states were read during the hold.

## Still on Nova (not pulled)
- Extra Stage C jobs 17169612 (n=36), 17169613 (n=44) and 17169614 (n=52): submitted 02:33 CDT Sat at the lead's request, one n per job, `--time=01:30:00`, nice 0, label `sglang-fcfs-r1-h200`. They are blind tests of the r13 theory's cliff, not part of the registration check. Pull them before 13:30 CDT Sat, when the VPN window closes around 14:00.
- The staging dir `/work/classtmp/avalse/swapp/pull_staging_h200_wave1_pulled_20261031-023416/` (uncompressed copy; archive deleted after the hash check).

## Nova access window (lead, 2026-10-31 ~02:10 CDT)
Nova is reachable over a VPN that Akshat reconnected. It drops automatically around 14:00 CDT Sat. Pull every finished result before 13:30; anything that ends later waits for the next reconnect.
