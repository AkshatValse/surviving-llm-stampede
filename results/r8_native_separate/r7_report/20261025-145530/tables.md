### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.071371 | 0.00063128 | 0.07 | 11180 | 0.99941 | 0.073065 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-2) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1747 / 0.93 |
| 24 | 0.2509 / 0.93 |
| 32 | 0.3187 / 0.93 |
| 48 | 0.4246 / 0.93 |
| 64 | 0.4910 / 0.93 |
| 72 | 0.5133 / 0.93 |
| 80 | 0.4981 / 0.92 |
| 88 | 0.2949 / 0.81 |
| 96 | 0.1593 / 0.49 |
| 112 | 0.0781 / 0.06 |
| 128 | 0.0759 / 0.00 |
| 160 | 0.0828 / 0.00 |
| 300 | 0.1083 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 72 | 0.5133 | 64 | 0.211 | 0 | 72 | 0.5067 | 64 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.5 | 0.1071 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0003958 | 0.9297 | 0 |
| Exp(5 s) (record) | 2 | 0.1427 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.005458 | 0.931 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1784 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003932 | 0.9318 | 0 |
| Exp(5 s) (record) | 3 | 0.2141 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001043 | 0.9325 | 0 |
| Exp(5 s) (record) | 3.5 | 0.2498 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.003824 | 0.9324 | 0 |
| Exp(5 s) (record) | 4 | 0.2855 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.004663 | 0.9317 | 0 |
| Exp(5 s) (record) | 4.5 | 0.3212 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00319 | 0.9313 | 0 |
| Exp(5 s) (record) | 5 | 0.3569 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001957 | 0.9314 | 0 |
| Exp(5 s) (record) | 5.5 | 0.3925 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.007258 | 0.9315 | 0 |
| Exp(5 s) (record) | 6 | 0.4282 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.007775 | 0.9318 | 0 |
| Exp(5 s) (record) | 6.5 | 0.4639 | 8/10 (0.80) [0.49, 0.94] | False | 106.3 | 537 | 86.91 | 0.7452 | 0 |
| Exp(5 s) (record) | 7 | 0.4996 | 3/10 (0.30) [0.11, 0.60] | False | 281.8 | 720 | 230.8 | 0.5208 | 0 |
| Exp(5 s) (record) | 7.5 | 0.5353 | 0/10 (0.00) [0.00, 0.28] | False | 595.2 | 907 | 483.2 | 0.17 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.071371 | 6 | 6 | True | False | [1, 6] | 2.65, 4.35 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 2.65 | 0.1891 | 64 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(5 s) (record) | 4.35 | 0.3105 | 64 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 2.65 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9323 | 0.03205 |
| Exp(5 s) (record) | 4.35 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9325 | 0.07431 |

### 5. Burst-size sweep (record workload, 10 seeds)

**lambda = 2.65 x lambda_miss = 0.18913 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **200**; smallest burst from which every larger burst also does: 200; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 200

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.932 |
| 200 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |
| 400 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |

**lambda = 4.35 x lambda_miss = 0.31047 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **200**; smallest burst from which every larger burst also does: 200; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 200

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.932 |
| 200 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |
| 400 | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 0 | 10/10 (1.00) [0.72, 1.00] | TTTTTTTTTT | 0 |

### 6. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (1 workloads, 2 points, seeds 0-9) | 20 | 20/20 (1.00) [0.84, 1.00] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| pairs, record workload only (2.65 and 4.35 x, seeds 0-9) | 20 | 20/20 (1.00) [0.84, 1.00] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| burst_sizes, 200 sessions (bit-identical to the record-workload rows of pairs) | 20 | 20/20 (1.00) [0.84, 1.00] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |
