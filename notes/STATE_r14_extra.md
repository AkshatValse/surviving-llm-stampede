# r14 extra cells: TOOLSLOW (remedy N3) and SHED (remedy N4), live state

Branch `r14/extra`, registration tag `r14-extra-reg`. Written 2026-10-31 (Sat) while Nova was unreachable (DNS/SSH outage since ~01:15 CDT).

## What is registered
Four FILLED registrations, filled by `python -m analysis.r14_prereg fill --cell CELL` from the 2026-10-24 registration's inputs (`prereg/inputs/2026-10-23`; measured cell `sglang-fcfs-r1`, n_cap 20 by smallest_within_margin, hardware "NVIDIA A100 80GB PCIe, 81920 MiB"), single point 1.35 x lambda_ref (the m1 point of `configs/agentload_prereg_2026-10-24.yaml`). Each records `protocol.e2_config_sha256` (check-job refuses other bytes; a run whose `config.yaml` differs is not bound) and `protocol.arms` (the only arm it authorises).

| Cell (label) | Registration | E2 config | Arm | Seeds |
|---|---|---|---|---|
| sglang-fcfs-r1-toolslow-d10 | configs/agentload_prereg_2026-10-31_toolslow_d10.yaml | configs/agentload_e2_toolslow_d10.yaml | noburst | 0, 1, 2 |
| sglang-fcfs-r1-toolslow-d30 | configs/agentload_prereg_2026-10-31_toolslow_d30.yaml | configs/agentload_e2_toolslow_d30.yaml | noburst | 0, 1, 2 |
| sglang-fcfs-r1-shed-t600 | configs/agentload_prereg_2026-10-31_shed_t600.yaml | configs/agentload_e2_shed_t600.yaml | burst | 0, 1 |
| sglang-fcfs-r1-shed-t3600 | configs/agentload_prereg_2026-10-31_shed_t3600.yaml | configs/agentload_e2_shed_t3600.yaml | burst | 0, 1 |

- TOOLSLOW: the E2 NOBURST protocol at 1.35 x (8700 s), every tool call whose sleep starts in [1200, 2100) s takes +10 s resp. +30 s (client option `workload.tool_slowdown {t_s: 1200, width_s: 900, add_s}`, logged in `tool_calls.csv`). plan.csv = the committed NOBURST run's of the same seed.
- SHED: the E2 BURST protocol at 1.35 x (200 sessions in [1200, 1260)), arrivals stopped over [1800, 1800 + tau), `arrivals.kind: ramp`, `ramp_is_mult: true`, knots `[[0,1.35],[1800,1.35],[1800.001,0],[1800+tau,0],[1800+tau+0.001,1.35],[8700,1.35]]`. Arrivals outside the stop and the burst = the committed BURST run's of the same seed (tests/test_r14_extra.py).
- Frozen endpoints: STUCK / GOOD exactly as `configs/r11_basin_predict.yaml` defines them (unchanged), over [5700, 8700) s.
- Rules (verbatim): TOOLSLOW "causal test of the gap: d10 GOOD in >=2/3 seeds and d30 STUCK in >=2/3"; SHED "tau600 STUCK in >=2/3 and tau3600 GOOD in >=2/3; sessions shed reported; compared with R1 (0 shed)". With seeds {0, 1} the SHED majority is 2 of 2.
- Controls (CRN, by seed): the committed 300k E2 runs at 1.35 x, jobs 17093387-404, `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/`.
- Analysis: `python -m analysis.r14_cells classify --run-dirs ... --prereg <the four files>` (pairs with the controls, counts sessions shed, applies both rules).

## Blindness
The theory predictions for these cells ('pred2', branch `r13/pred2`) are committed separately and must be pushed before the first job is submitted. This branch did not compute or read them. `submit_extra.sh --submit` requires the pred2 commit.

## Status
- Registered and pushed (see the tag message and the commit for the GitHub push time). No job submitted.
- Nova-side steps (bundle, frozen clone `$W/repo_r14_extra`, mock glue tests on the login node, check-job from the clone, dry run): scratchpad `r14/nova_steps_extra.sh`, run when Nova is back. Submission: scratchpad `r14/submit_extra.sh` (10 jobs: toolslow d10 s0-2, d30 s0-2 at nice 56; shed t600 s0-1, t3600 s0-1 at nice 57; `--time=03:10:00 --mem=48G --cpus-per-task=16`).
- Cost: 10 one-arm 8700-s jobs, about 28 A100-h.
