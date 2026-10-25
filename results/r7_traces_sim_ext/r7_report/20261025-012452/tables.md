### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | E[T] (turns per session) | lambda_miss x E[T] (turns/s) | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 14.761 | 1.0656 | 0.071986 | 1 |
| TraceLab per-turn (empirical) | 8.5099 | 4.6533 | 0.073153 | 0.0036179 | 0.07037 | 11248 | 1 | 14.761 | 1.0798 | 0.073266 | 1 |
| TraceLab idle gap (empirical, upper bound) | 14.523 | 3.5296 | 0.071585 | 0.0020638 | 0.068333 | 11018 | 0.99997 | 14.761 | 1.0567 | 0.07373 | 1 |
| mini-SWE-agent v2 tool time (empirical) | 1.3982 | 4.2923 | 0.07294 | 0.0014784 | 0.070556 | 11292 | 1 | 14.761 | 1.0767 | 0.072262 | 1 |
| mini-SWE-agent v2 full workload (empirical) | 1.3982 | 4.2923 | 0.011962 | 0.00022187 | 0.0088889 | 8894.1 | 1 | 34.787 | 0.41611 | 0.016588 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-2) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record, control) | TraceLab per-turn (empirical) | TraceLab idle gap (empirical, upper bound) | mini-SWE-agent v2 tool time (empirical) | mini-SWE-agent v2 full workload (empirical) |
|---|---|---|---|---|---|
| 8 | 0.0905 / 0.93 | 0.0581 / 0.93 | 0.0340 / 0.93 | 0.1928 / 0.93 | 0.0406 / 0.97 |
| 12 | 0.1341 / 0.93 | 0.0880 / 0.93 | 0.0534 / 0.93 | 0.2638 / 0.93 | 0.0503 / 0.96 |
| 16 | 0.1759 / 0.93 | 0.1148 / 0.93 | 0.0701 / 0.93 | 0.3285 / 0.93 | 0.0274 / 0.70 |
| 20 | 0.2144 / 0.93 | 0.1387 / 0.93 | 0.0903 / 0.93 | 0.3802 / 0.93 | 0.0173 / 0.35 |
| 24 | 0.2130 / 0.88 | 0.1672 / 0.93 | 0.1079 / 0.93 | 0.3913 / 0.92 | 0.0134 / 0.15 |
| 28 | 0.1772 / 0.77 | 0.1944 / 0.93 | 0.1252 / 0.92 | 0.2206 / 0.77 | 0.0107 / 0.00 |
| 32 | 0.1226 / 0.52 | 0.2178 / 0.92 | 0.1404 / 0.92 | 0.1179 / 0.40 | 0.0113 / 0.00 |
| 40 | 0.0733 / 0.03 | 0.1982 / 0.73 | 0.1694 / 0.88 | 0.0720 / 0.00 | 0.0127 / 0.00 |
| 48 | 0.0714 / 0.00 | 0.1002 / 0.23 | 0.1259 / 0.55 | 0.0721 / 0.00 | 0.0140 / 0.00 |
| 64 | 0.0715 / 0.00 | 0.0726 / 0.00 | 0.0715 / 0.00 | 0.0720 / 0.00 | 0.0163 / 0.00 |
| 96 | 0.0758 / 0.00 | 0.0763 / 0.00 | 0.0765 / 0.00 | 0.0758 / 0.00 | 0.0203 / 0.00 |
| 300 | 0.1112 / 0.00 | 0.1116 / 0.00 | 0.1120 / 0.00 | 0.1114 / 0.00 | 0.0354 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 20 | 0.2144 | 20 | 0.5186 | 0 | 20 | 0.2126 | 20 |
| TraceLab per-turn (empirical) | 32 | 0.2178 | 32 | 0.5125 | 0 | 32 | 0.2183 | 32 |
| TraceLab idle gap (empirical, upper bound) | 40 | 0.1694 | 40 | 0.6612 | 0 | 40 | 0.1693 | 40 |
| mini-SWE-agent v2 tool time (empirical) | 24 | 0.3913 | 20 | 0.2846 | 0 | 24 | 0.3883 | 20 |
| mini-SWE-agent v2 full workload (empirical) | 12 | 0.05035 | 12 | 0.704 | 0 | 12 | 0.0513 | 12 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record, control) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record, control) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record, control) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record, control) | 2.25 | 0.1624 | 7/10 (0.70) [0.40, 0.89] | False | 10.5 | 78 | 9.203 | 0.7995 | 0 |
| Exp(5 s) (record, control) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record, control) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |
| Exp(5 s) (record, control) | 3.5 | 0.2527 | 0/10 (0.00) [0.00, 0.28] | False | 292.4 | 361 | 188.3 | 0.06604 | 0 |
| TraceLab per-turn (empirical) | 1.25 | 0.09144 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002288 | 0.9308 | 0 |
| TraceLab per-turn (empirical) | 1.5 | 0.1097 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.002298 | 0.93 | 0 |
| TraceLab per-turn (empirical) | 1.75 | 0.128 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0141 | 0.9282 | 0 |
| TraceLab per-turn (empirical) | 2 | 0.1463 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00265 | 0.9276 | 0 |
| TraceLab per-turn (empirical) | 2.25 | 0.1646 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003882 | 0.9244 | 0 |
| TraceLab per-turn (empirical) | 2.5 | 0.1829 | 8/10 (0.80) [0.49, 0.94] | False | 20.5 | 144 | 18.7 | 0.7942 | 0 |
| TraceLab per-turn (empirical) | 3 | 0.2195 | 5/10 (0.50) [0.24, 0.76] | False | 83.1 | 246 | 70.53 | 0.5282 | 0 |
| TraceLab per-turn (empirical) | 3.5 | 0.256 | 2/10 (0.20) [0.06, 0.51] | False | 173 | 314 | 133.8 | 0.3331 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.25 | 0.08948 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.003263 | 0.9289 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.5 | 0.1074 | 10/10 (1.00) [0.72, 1.00] | True | 0.1 | 1 | 0.002057 | 0.9216 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.75 | 0.1253 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.02342 | 0.9146 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2 | 0.1432 | 10/10 (1.00) [0.72, 1.00] | True | 0.5 | 5 | 0.3725 | 0.8963 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2.25 | 0.1611 | 7/10 (0.70) [0.40, 0.89] | False | 27.8 | 114 | 23.12 | 0.6725 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2.5 | 0.179 | 4/10 (0.40) [0.17, 0.69] | False | 63.5 | 156 | 51.08 | 0.5005 | 0 |
| TraceLab idle gap (empirical, upper bound) | 3 | 0.2148 | 1/10 (0.10) [0.02, 0.40] | False | 176.2 | 251 | 133.5 | 0.09072 | 0 |
| TraceLab idle gap (empirical, upper bound) | 3.5 | 0.2505 | 0/10 (0.00) [0.00, 0.28] | False | 290.7 | 345 | 197.2 | 0 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.25 | 0.09117 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.001808 | 0.9306 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.5 | 0.1094 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001299 | 0.9297 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.75 | 0.1276 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002736 | 0.9295 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2 | 0.1459 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006165 | 0.931 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2.25 | 0.1641 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006351 | 0.9319 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2.5 | 0.1823 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.001891 | 0.9327 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 3 | 0.2188 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00479 | 0.9324 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 3.5 | 0.2553 | 9/10 (0.90) [0.60, 0.98] | False | 27.1 | 271 | 15.36 | 0.8385 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.25 | 0.01495 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001371 | 0.9701 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.5 | 0.01794 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002028 | 0.9704 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.75 | 0.02093 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0008958 | 0.9702 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2 | 0.02392 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006773 | 0.9705 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.25 | 0.02691 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.01228 | 0.9702 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.5 | 0.0299 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002682 | 0.9714 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3 | 0.03589 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.004188 | 0.9707 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3.5 | 0.04187 | 7/10 (0.70) [0.40, 0.89] | False | 8.3 | 36 | 8.979 | 0.7607 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| TraceLab per-turn (empirical) | 0.073153 | 2.25 | 2.25 | True | False | [1, 2.25] | 1.4, 1.85 |
| TraceLab idle gap (empirical, upper bound) | 0.071585 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| mini-SWE-agent v2 tool time (empirical) | 0.07294 | 3 | 3 | True | False | [1, 3] | 1.65, 2.35 |
| mini-SWE-agent v2 full workload (empirical) | 0.011962 | 3 | 3 | True | False | [1, 3] | 1.65, 2.35 |

### 4. Paired-arm test at the two window points (20 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 14) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | 0.09745 | 20 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| Exp(5 s) (record, control) | 1.65 | 0.1191 | 20 | 18/20 (0.90) [0.70, 0.97] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab per-turn (empirical) | 1.4 | 0.1024 | 32 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab per-turn (empirical) | 1.85 | 0.1353 | 32 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.35 | 0.09664 | 40 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.65 | 0.1181 | 40 | 16/20 (0.80) [0.58, 0.92] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | 0.1204 | 20 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | 0.1714 | 20 | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | 0.01974 | 12 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 14/20 (0.70) [0.48, 0.85] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 0.02811 | 12 | 19/20 (0.95) [0.76, 0.99] | 18/20 (0.90) [0.70, 0.97] | 2/20 (0.10) [0.03, 0.30] | FAIL | 20/20 (1.00) [0.84, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | TTTTTTTTTITTTTTTTITI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9324 | 0.01083 |
| Exp(5 s) (record, control) | 1.65 | TTTTTTTITITTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 2 | 0 | 0 | 0 | 0.9319 | 0.01488 |
| TraceLab per-turn (empirical) | 1.4 | TITTTTTTTITTTTTTTTTI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9316 | 0.0119 |
| TraceLab per-turn (empirical) | 1.85 | TTTTTTTTTTTTTTTTTITT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9308 | 0.02268 |
| TraceLab idle gap (empirical, upper bound) | 1.35 | TTTTTTTTIITTTTTTTITT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9279 | 0.01557 |
| TraceLab idle gap (empirical, upper bound) | 1.65 | ITTTTTTTTITTTTTTTITI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 4 | 0 | 0 | 0 | 0.9216 | 0.03035 |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | TTTTTTTTTITTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9321 | 0.01616 |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | TTTTTTTTTTTTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9326 | 0.02973 |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | TTTTTTTTTTTTTTTITTTT | RRRRRRRRRRRRRRRRRRRR | ORRRRRRRORORRRRROORO | 1 | 0 | 0 | 0 | 0.9711 | 0.004959 |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | TTTTTTTTTTTTTTTITTTT | RRRRRRRRRRRRRRRRRTOR | OOROOOOOOOOOROOOOOOO | 1 | 0 | 1 | 0 | 0.8944 | 4.197 |

### 5. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (5 workloads, 10 points, seeds 100-119) | 200 | 181/200 (0.91) [0.86, 0.94] | 19/200 (0.10) [0.06, 0.14] | 0/200 (0.00) [0.00, 0.02] | 0/200 (0.00) [0.00, 0.02] | 200/200 (1.00) [0.98, 1.00] |
| pairs, record workload only (1.35 and 1.65 x, seeds 100-119) | 40 | 35/40 (0.88) [0.74, 0.95] | 5/40 (0.12) [0.05, 0.26] | 0/40 (0.00) [0.00, 0.09] | 0/40 (0.00) [0.00, 0.09] | 40/40 (1.00) [0.91, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |
