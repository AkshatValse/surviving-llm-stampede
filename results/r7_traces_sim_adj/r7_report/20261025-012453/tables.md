### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [18000, 54000) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | E[T] (turns per session) | lambda_miss x E[T] (turns/s) | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 5 | 1 | 0.072682 | 0.0010673 | 0.072722 | 11208 | 0.99998 | 14.761 | 1.0729 | 0.073106 | 1 |
| mini-SWE-agent v2 full workload (empirical) | 1.3982 | 4.2923 | 0.014093 | 0.00020632 | 0.013991 | 8958.8 | 1 | 34.787 | 0.49026 | 0.01406 | 1 |

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

Stable runs per multiple of the workload's own lambda_miss (from empty, 8700 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.25 | 0.01762 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00172 | 0.972 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.5 | 0.02114 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0008639 | 0.9709 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.75 | 0.02466 | 9/10 (0.90) [0.60, 0.98] | False | 7 | 70 | 2.709 | 0.8737 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2 | 0.02819 | 8/10 (0.80) [0.49, 0.94] | False | 13.8 | 96 | 4.408 | 0.7761 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.25 | 0.03171 | 9/10 (0.90) [0.60, 0.98] | False | 11.6 | 116 | 2.693 | 0.8719 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.5 | 0.03523 | 4/10 (0.40) [0.17, 0.69] | False | 55.2 | 141 | 18.11 | 0.3877 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3 | 0.04228 | 3/10 (0.30) [0.11, 0.60] | False | 109.1 | 202 | 26.88 | 0.3309 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3.5 | 0.04933 | 0/10 (0.00) [0.00, 0.28] | False | 218.3 | 276 | 51.67 | 0 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 0.014093 | 1.5 | 1.5 | True | False | [1, 1.5] | 1.15, 1.35 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.15 | 0.01621 | 12 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | FAIL | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 1.35 | 0.01903 | 12 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.15 | TITIIITIII | RRRRRRRRRR | RRRRRRRRRR | 7 | 0 | 0 | 0 | 0.9709 | 0.003858 |
| mini-SWE-agent v2 full workload (empirical) | 1.35 | TITTITTTTI | RRRRRRRRRR | RRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9724 | 0.00527 |

### 5. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (1 workloads, 2 points, seeds 0-9) | 20 | 10/20 (0.50) [0.30, 0.70] | 10/20 (0.50) [0.30, 0.70] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |
