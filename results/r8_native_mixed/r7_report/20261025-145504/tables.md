### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.072036 | 0.0013124 | 0.069815 | 11239 | 0.99993 | 0.073718 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-2) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1759 / 0.93 |
| 24 | 0.2541 / 0.93 |
| 32 | 0.3249 / 0.93 |
| 48 | 0.4375 / 0.93 |
| 64 | 0.5122 / 0.93 |
| 72 | 0.5373 / 0.93 |
| 80 | 0.5088 / 0.92 |
| 88 | 0.2693 / 0.79 |
| 96 | 0.1431 / 0.42 |
| 112 | 0.0736 / 0.00 |
| 128 | 0.0768 / 0.00 |
| 160 | 0.0838 / 0.00 |
| 300 | 0.1114 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 72 | 0.5373 | 64 | 0.2073 | 0 | 72 | 0.5317 | 64 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.5 | 0.1081 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001151 | 0.9295 | 0 |
| Exp(5 s) (record) | 2 | 0.1441 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006281 | 0.9311 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1801 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003856 | 0.9319 | 0 |
| Exp(5 s) (record) | 3 | 0.2161 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0008061 | 0.9325 | 0 |
| Exp(5 s) (record) | 3.5 | 0.2521 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.005482 | 0.9324 | 0 |
| Exp(5 s) (record) | 4 | 0.2881 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.006895 | 0.9316 | 0 |
| Exp(5 s) (record) | 4.5 | 0.3242 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.004799 | 0.9314 | 0 |
| Exp(5 s) (record) | 5 | 0.3602 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0003752 | 0.9313 | 0 |
| Exp(5 s) (record) | 5.5 | 0.3962 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0007359 | 0.9315 | 0 |
| Exp(5 s) (record) | 6 | 0.4322 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.01993 | 0.9318 | 0 |
| Exp(5 s) (record) | 6.5 | 0.4682 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006884 | 0.9317 | 0 |
| Exp(5 s) (record) | 7 | 0.5043 | 7/10 (0.70) [0.40, 0.89] | False | 177.6 | 674 | 148.7 | 0.6514 | 0 |
| Exp(5 s) (record) | 7.5 | 0.5403 | 2/10 (0.20) [0.06, 0.51] | False | 460.4 | 844 | 371.4 | 0.3729 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.072036 | 6.5 | 6.5 | True | False | [1, 6.5] | 2.85, 4.65 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 2.85 | 0.2053 | 64 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 9/10 (0.90) [0.60, 0.98] |
| Exp(5 s) (record) | 4.65 | 0.335 | 64 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 2.85 | TRTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 1 | 0 | 0 | 0.9316 | 0.03714 |
| Exp(5 s) (record) | 4.65 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9323 | 0.0921 |

### 5. Burst-size sweep (record workload, 10 seeds)

**lambda = 2.85 x lambda_miss = 0.20530 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **200**; smallest burst from which every larger burst also does: 200; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 200

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.932 |
| 200 | 9/10 (0.90) [0.60, 0.98] | 1/10 (0.10) [0.02, 0.40] | 0 | 9/10 (0.90) [0.60, 0.98] | TRTTTTTTTT | 0.0935 |
| 400 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |

**lambda = 4.65 x lambda_miss = 0.33497 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **200**; smallest burst from which every larger burst also does: 200; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 200

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.932 |
| 200 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |
| 400 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |

### 6. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (1 workloads, 2 points, seeds 0-9) | 20 | 19/20 (0.95) [0.76, 0.99] | 0/20 (0.00) [0.00, 0.16] | 1/20 (0.05) [0.01, 0.24] | 0/20 (0.00) [0.00, 0.16] | 19/20 (0.95) [0.76, 0.99] |
| pairs, record workload only (2.85 and 4.65 x, seeds 0-9) | 20 | 19/20 (0.95) [0.76, 0.99] | 0/20 (0.00) [0.00, 0.16] | 1/20 (0.05) [0.01, 0.24] | 0/20 (0.00) [0.00, 0.16] | 19/20 (0.95) [0.76, 0.99] |
| burst_sizes, 200 sessions (bit-identical to the record-workload rows of pairs) | 20 | 19/20 (0.95) [0.76, 0.99] | 0/20 (0.00) [0.00, 0.16] | 1/20 (0.05) [0.01, 0.24] | 0/20 (0.00) [0.00, 0.16] | 19/20 (0.95) [0.76, 0.99] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |
