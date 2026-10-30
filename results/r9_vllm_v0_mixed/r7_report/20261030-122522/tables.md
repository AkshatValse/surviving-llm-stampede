### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 0.071986 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-9) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1767 / 0.93 |
| 20 | 0.2156 / 0.93 |
| 24 | 0.2217 / 0.89 |
| 28 | 0.1672 / 0.74 |
| 32 | 0.1122 / 0.46 |
| 40 | 0.0727 / 0.03 |
| 48 | 0.0711 / 0.00 |
| 96 | 0.0786 / 0.00 |
| 300 | 0.1119 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2217 | 20 | 0.5047 | 0 | 24 | 0.222 | 20 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
