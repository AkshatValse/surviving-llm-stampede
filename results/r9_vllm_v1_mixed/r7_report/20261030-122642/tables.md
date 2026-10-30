### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.066228 | 0.00073592 | 0.065926 | 10358 | 1 | 0.066805 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-9) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1753 / 0.93 |
| 20 | 0.2127 / 0.93 |
| 24 | 0.2154 / 0.89 |
| 28 | 0.1617 / 0.74 |
| 32 | 0.1045 / 0.46 |
| 40 | 0.0663 / 0.03 |
| 48 | 0.0655 / 0.00 |
| 96 | 0.0741 / 0.00 |
| 300 | 0.1063 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2154 | 20 | 0.4934 | 0 | 24 | 0.2153 | 20 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.08278 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002517 | 0.9325 | 0 |
| Exp(5 s) (record) | 1.5 | 0.09934 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002635 | 0.9309 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1159 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 4.653e-05 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1325 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002491 | 0.9303 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1656 | 7/10 (0.70) [0.40, 0.89] | False | 14 | 95 | 11.93 | 0.7955 | 0 |
| Exp(5 s) (record) | 3 | 0.1987 | 3/10 (0.30) [0.11, 0.60] | False | 131.8 | 241 | 96.89 | 0.3171 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.066228 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
