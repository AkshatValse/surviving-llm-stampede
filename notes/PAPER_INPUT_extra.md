# Paper input: TOOLSLOW and SHED (registered), scored against frozen pred2

Written 2026-11-01 by the lead. Pull: `results/nova/toolslow_shed_1716990x_pulled_20261101-154800/` (TP); commands, archive hash and the job-to-run map in `TP/COMMANDS.txt`. Registered analysis: `TP/analysis/agentload_analysis_r14/20261101-154909/` (`r14_runs.csv`, `r14_verdict.json`), `analysis/r14_cells.py` at `db24efa`. Registrations: `configs/agentload_prereg_2026-10-31_{toolslow_d10,toolslow_d30,shed_t600,shed_t3600}.yaml`, FILLED, tag `r14-extra-reg` (`b006291`, committed 02:27:40, pushed 02:28:09 CDT on 10-31); analysis-only review fix `db24efa` before any job. Jobs submitted 04:21:41-43 CDT, after pred2's push (04:20:20), so blind in time to pred2. Every run is bound to its registration, paired with its committed 1.35 x control of the same seed, and counted (manipulation present).

Cell: SGLang FCFS, 300k pool, Qwen2.5-7B-Instruct, one A100 80GB PCIe, 1.35 x lambda_ref (0.096571 sessions/s), 8700 s runs, evaluation window [5700, 8700) s; STUCK := hit < 0.2; GOOD := RECOVERED, or hit > 0.8 and backlog slope <= 0.5 (lambda - lambda_ref) (the frozen B1 endpoints).

## SHED: PASS

Burst of 200 at 1200 s, then arrivals stopped over [1800, 1800 + tau) s; seeds 0-1. Rule: tau = 600 STUCK in 2 of 2 and tau = 3600 GOOD in 2 of 2.

| tau | seed | job | run | state | trap_v2 | hit_eval | slope /s | outstanding end | sessions refused |
|---|---|---|---|---|---|---|---|---|---|
| 600 | 0 | 17169908 | `20261031-224614` | STUCK | trapped | 0.000 | 0.0180 | 219 | 59 |
| 600 | 1 | 17169909 | `20261031-230929` | STUCK | indeterminate | 0.000 | 0.0034 | 168 | 56 |
| 3600 | 0 | 17169910 | `20261031-232800` | GOOD | recovered | 0.933 | -0.0016 | 1.6 | 355 |
| 3600 | 1 | 17169911 | `20261031-233231` | GOOD | recovered | 0.930 | 0.0004 | 1.3 | 378 |

- The same-seed BURST controls (no stop) are stuck, as committed. The registered R1 cap at the same rate refused no session.
- Against pred2 (`notes/PREDICTIONS_r13_pred2.md`, section 4): tau = 600 STUCK (P 1.00) and tau = 3600 GOOD (P 0.998), rule P 0.997. All held. Proposition S's tau_min = 1,795 s lies between the two stop lengths: consistent, not tested more finely.
- The refused counts equal pred2's protocol check exactly (59 / 56 and 355 / 378). They are fixed by the client plans, so this is a protocol check, not a model prediction.
- Reading: a long enough arrival stop drains the trap, as the cap does, but refuses 355-378 sessions; a 600 s stop refuses 56-59 and does not drain it.

## TOOLSLOW: rule NOT met

No burst; every tool call starting in [1200, 2100) s lasts Z + delta. Rule: delta = 10 GOOD in >= 2 of 3 and delta = 30 STUCK in >= 2 of 3.

| delta | seed | job | run | state | trap_v2 | hit_eval | slope /s | outstanding end | slowed calls |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 17169902 | `20261031-210448` | GOOD | recovered | 0.931 | 0.0004 | 1.8 | 1034 |
| 10 | 1 | 17169903 | `20261031-210648` | GOOD | recovered | 0.930 | 0.0008 | 1.2 | 923 |
| 10 | 2 | 17169904 | `20261031-215143` | GOOD | recovered | 0.934 | 0.0001 | 1.4 | 975 |
| 30 | 0 | 17169905 | `20261031-220113` | GOOD | recovered | 0.931 | 0.0004 | 1.8 | 770 |
| 30 | 1 | 17169906 | `20261031-220954` | GOOD | recovered | 0.930 | 0.0008 | 1.2 | 664 |
| 30 | 2 | 17169907 | `20261031-224211` | STUCK | trapped | 0.000 | 0.0233 | 127 | 706 |

- delta = 10: GOOD 3/3 (holds). delta = 30: STUCK 1/3 (fails). The GOOD runs have the same window hit fraction as their same-seed NOBURST control (common random numbers; the system had recovered by 5700 s).
- Against pred2 (section 3): delta = 10 GOOD with P 0.71 per seed: held 3/3. delta = 30 STUCK with P 1.00 per seed (no good state exists while slowed; fluid n(2100) = 46.9): wrong for seeds 0 and 1. Rule P 0.80 (band 0.63): the rule failed.
- pred2's per-seed plan walk put seed 0 highest (49, 37, 39 sessions at 2100 s), yet seed 0 recovered and seed 2 trapped.
- A 30 s slowdown of every tool call for 900 s, with no burst, trapped the engine in 1 of 3 seeds. The critical delta (frozen 16.4-16.8 s) is not bracketed by this test.

## Caveats

- Two seeds per SHED cell, three per TOOLSLOW cell; one rate (1.35 x), one model, one GPU.
- SHED t600 seed 1 is STUCK at zero hits but trap_v2 "indeterminate" (slope 0.0034 below the 0.0125 threshold); the registered rule uses STUCK.
- Independent check: hit_eval of all 10 runs reproduced exactly from requests.csv; slopes and trap_v2 labels were not recomputed independently.

## Suggested text

Results or frozen-section paragraph: "Two registered tests at 1.35 lref probed another exit and another trigger. SHED stopped arrivals after a burst of 200: a 600 s stop left 2 of 2 runs stuck and a 3600 s stop recovered 2 of 2, as pred2 predicted (probability 0.997), at the cost of 56-59 and 355-378 refused sessions, against none for the cap. TOOLSLOW lengthened every tool call starting in a 900 s interval, with no burst: 10 s more left 3 of 3 runs good, but 30 s more trapped only 1 of 3, so its registered rule was not met; pred2 had predicted a trap in every seed at 30 s."

Frozen-table outcome cells: SHED "PASS: 600 s stuck 2 of 2, 3600 s good 2 of 2; 59/56 and 355/378 sessions refused (cap: none)". TOOLSLOW "Rule not met: 10 s good 3 of 3; 30 s stuck 1 of 3 (pred2: stuck in every seed)".
