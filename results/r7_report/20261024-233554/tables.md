### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(1 s) | 1 | 1 | 0.072777 | 0.00138 | 0.070556 | 11288 | 1 | 0.072187 | 1 |
| Exp(2 s) | 2 | 1 | 0.072651 | 0.0015782 | 0.07037 | 11279 | 1 | 0.072199 | 1 |
| Exp(5 s) (record) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 0.071986 | 1 |
| lognormal(mean 5 s, CV 2) | 5 | 2 | 0.072965 | 0.001229 | 0.071111 | 11250 | 1 | 0.072024 | 1 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 4.8 | 1.5833 | 0.071773 | 0.0012945 | 0.07 | 11199 | 0.99982 | 0.072099 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-2) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(1 s) | Exp(2 s) | Exp(5 s) (record) | lognormal(mean 5 s, CV 2) | bimodal (80% 1 s, 20% 20 s; mean 4.8 s) |
|---|---|---|---|---|---|
| 8 | 0.2184 / 0.93 | 0.1644 / 0.93 | 0.0905 / 0.93 | 0.0918 / 0.93 | 0.0929 / 0.93 |
| 12 | 0.2964 / 0.93 | 0.2328 / 0.93 | 0.1341 / 0.93 | 0.1321 / 0.93 | 0.1374 / 0.93 |
| 16 | 0.3579 / 0.93 | 0.2938 / 0.93 | 0.1759 / 0.93 | 0.1733 / 0.93 | 0.1804 / 0.93 |
| 20 | 0.3818 / 0.92 | 0.3321 / 0.93 | 0.2144 / 0.93 | 0.2093 / 0.93 | 0.2182 / 0.93 |
| 24 | 0.2685 / 0.85 | 0.2689 / 0.86 | 0.2130 / 0.88 | 0.2177 / 0.89 | 0.2169 / 0.88 |
| 28 | 0.1663 / 0.63 | 0.1723 / 0.68 | 0.1772 / 0.77 | 0.1834 / 0.79 | 0.1772 / 0.76 |
| 32 | 0.0871 / 0.19 | 0.0924 / 0.25 | 0.1226 / 0.52 | 0.1771 / 0.74 | 0.1418 / 0.59 |
| 40 | 0.0719 / 0.00 | 0.0718 / 0.00 | 0.0733 / 0.03 | 0.0738 / 0.04 | 0.0726 / 0.03 |
| 48 | 0.0718 / 0.00 | 0.0717 / 0.00 | 0.0714 / 0.00 | 0.0720 / 0.01 | 0.0719 / 0.00 |
| 64 | 0.0717 / 0.00 | 0.0717 / 0.00 | 0.0715 / 0.00 | 0.0718 / 0.00 | 0.0716 / 0.00 |
| 96 | 0.0756 / 0.00 | 0.0756 / 0.00 | 0.0758 / 0.00 | 0.0750 / 0.00 | 0.0754 / 0.00 |
| 300 | 0.1112 / 0.00 | 0.1113 / 0.00 | 0.1112 / 0.00 | 0.1111 / 0.00 | 0.1112 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(1 s) | 20 | 0.3818 | 20 | 0.2912 | 0 | 20 | 0.3761 | 20 |
| Exp(2 s) | 20 | 0.3321 | 20 | 0.3351 | 0 | 20 | 0.328 | 20 |
| Exp(5 s) (record) | 20 | 0.2144 | 20 | 0.5186 | 0 | 20 | 0.2126 | 20 |
| lognormal(mean 5 s, CV 2) | 24 | 0.2177 | 20 | 0.5103 | 0 | 24 | 0.2196 | 20 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 20 | 0.2182 | 20 | 0.5097 | 0 | 20 | 0.2156 | 20 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(1 s) | 1.25 | 0.09097 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0006884 | 0.931 | 0 |
| Exp(1 s) | 1.5 | 0.1092 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004317 | 0.9296 | 0 |
| Exp(1 s) | 1.75 | 0.1274 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002892 | 0.9299 | 0 |
| Exp(1 s) | 2 | 0.1456 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006201 | 0.931 | 0 |
| Exp(1 s) | 2.25 | 0.1637 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003306 | 0.9319 | 0 |
| Exp(1 s) | 2.5 | 0.1819 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0005528 | 0.9328 | 0 |
| Exp(1 s) | 3 | 0.2183 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.004928 | 0.9325 | 0 |
| Exp(1 s) | 3.5 | 0.2547 | 9/10 (0.90) [0.60, 0.98] | False | 28.2 | 282 | 19.96 | 0.8389 | 0 |
| Exp(2 s) | 1.25 | 0.09081 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -7.036e-05 | 0.9309 | 0 |
| Exp(2 s) | 1.5 | 0.109 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -2.008e-05 | 0.9296 | 0 |
| Exp(2 s) | 1.75 | 0.1271 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003104 | 0.9299 | 0 |
| Exp(2 s) | 2 | 0.1453 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006273 | 0.931 | 0 |
| Exp(2 s) | 2.25 | 0.1635 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.004572 | 0.9318 | 0 |
| Exp(2 s) | 2.5 | 0.1816 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 5.902e-05 | 0.9325 | 0 |
| Exp(2 s) | 3 | 0.218 | 7/10 (0.70) [0.40, 0.89] | False | 49.5 | 215 | 38.99 | 0.6886 | 0 |
| Exp(2 s) | 3.5 | 0.2543 | 5/10 (0.50) [0.24, 0.76] | False | 139.3 | 359 | 95.68 | 0.4677 | 0 |
| Exp(5 s) (record) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record) | 2.25 | 0.1624 | 7/10 (0.70) [0.40, 0.89] | False | 10.5 | 78 | 9.203 | 0.7995 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |
| Exp(5 s) (record) | 3.5 | 0.2527 | 0/10 (0.00) [0.00, 0.28] | False | 292.4 | 361 | 188.3 | 0.06604 | 0 |
| lognormal(mean 5 s, CV 2) | 1.25 | 0.09121 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002778 | 0.9306 | 0 |
| lognormal(mean 5 s, CV 2) | 1.5 | 0.1094 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0002761 | 0.9299 | 0 |
| lognormal(mean 5 s, CV 2) | 1.75 | 0.1277 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0007762 | 0.9299 | 0 |
| lognormal(mean 5 s, CV 2) | 2 | 0.1459 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.1907 | 0.9263 | 0 |
| lognormal(mean 5 s, CV 2) | 2.25 | 0.1642 | 8/10 (0.80) [0.49, 0.94] | False | 9.1 | 65 | 8.03 | 0.8116 | 0 |
| lognormal(mean 5 s, CV 2) | 2.5 | 0.1824 | 7/10 (0.70) [0.40, 0.89] | False | 29.5 | 130 | 25.32 | 0.7076 | 0 |
| lognormal(mean 5 s, CV 2) | 3 | 0.2189 | 3/10 (0.30) [0.11, 0.60] | False | 126.1 | 256 | 97.77 | 0.4002 | 0 |
| lognormal(mean 5 s, CV 2) | 3.5 | 0.2554 | 0/10 (0.00) [0.00, 0.28] | False | 277.5 | 360 | 184.2 | 0.07345 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.25 | 0.08972 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001183 | 0.9312 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.5 | 0.1077 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.003326 | 0.9297 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.75 | 0.1256 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.002139 | 0.9302 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 2 | 0.1435 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.2368 | 0.9276 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 2.25 | 0.1615 | 9/10 (0.90) [0.60, 0.98] | False | 2.2 | 22 | 2.354 | 0.907 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 2.5 | 0.1794 | 6/10 (0.60) [0.31, 0.83] | False | 43 | 156 | 37.4 | 0.6191 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 3 | 0.2153 | 2/10 (0.20) [0.06, 0.51] | False | 160.2 | 266 | 112.7 | 0.2765 | 0 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 3.5 | 0.2512 | 0/10 (0.00) [0.00, 0.28] | False | 270.4 | 357 | 173.9 | 0.124 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(1 s) | 0.072777 | 3 | 3 | True | False | [1, 3] | 1.65, 2.35 |
| Exp(2 s) | 0.072651 | 2.5 | 2.5 | True | False | [1, 2.5] | 1.5, 2 |
| Exp(5 s) (record) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| lognormal(mean 5 s, CV 2) | 0.072965 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 0.071773 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(1 s) | 1.65 | 0.1201 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(1 s) | 2.35 | 0.171 | 20 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(2 s) | 1.5 | 0.109 | 20 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(2 s) | 2 | 0.1453 | 20 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(5 s) (record) | 1.35 | 0.09745 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(5 s) (record) | 1.65 | 0.1191 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| lognormal(mean 5 s, CV 2) | 1.35 | 0.0985 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| lognormal(mean 5 s, CV 2) | 1.65 | 0.1204 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.35 | 0.09689 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.65 | 0.1184 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(1 s) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.931 | 0.01509 |
| Exp(1 s) | 2.35 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9327 | 0.02838 |
| Exp(2 s) | 1.5 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR | 3 | 0 | 0 | 0 | 0.931 | 0.013 |
| Exp(2 s) | 2 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9334 | 0.02195 |
| Exp(5 s) (record) | 1.35 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9307 | 0.01067 |
| Exp(5 s) (record) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9313 | 0.01506 |
| lognormal(mean 5 s, CV 2) | 1.35 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.931 | 0.01078 |
| lognormal(mean 5 s, CV 2) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9312 | 0.01523 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.35 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9307 | 0.01787 |
| bimodal (80% 1 s, 20% 20 s; mean 4.8 s) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9312 | 0.02666 |

### 5. Burst-size sweep (record workload, 10 seeds)

**lambda = 1.35 x lambda_miss = 0.09745 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **200**; smallest burst from which every larger burst also does: 200; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 100

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.931 |
| 25 | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.931 |
| 50 | 5/10 (0.50) [0.24, 0.76] | 4/10 (0.40) [0.17, 0.69] | 1 | 6/10 (0.60) [0.31, 0.83] | RRTTRRTTTI | 0.373 |
| 100 | 5/10 (0.50) [0.24, 0.76] | 0/10 (0.00) [0.00, 0.28] | 5 | 10/10 (1.00) [0.72, 1.00] | TTTIITIITI | 0 |
| 200 | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 1 | 10/10 (1.00) [0.72, 1.00] | TTTTITTTTT | 0 |
| 400 | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 3 | 10/10 (1.00) [0.72, 1.00] | TTTITITTTI | 0 |

**lambda = 1.65 x lambda_miss = 0.11911 sessions/s** (need 7 of 10 seeds): smallest burst trapping in >= 7/10 seeds (declared TRAPPED rule): **100**; smallest burst from which every larger burst also does: 100; [sensitivity] smallest burst with hit < 0.2 in >= 7/10 seeds (stuck, slope test ignored): 50

| burst size | trapped | recovered (good) | indeterminate | [sensitivity] stuck (hit < 0.2) | classes by seed | hit (mean) |
|---|---|---|---|---|---|---|
| 0 (NOBURST) | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.931 |
| 25 | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0 | 0/10 (0.00) [0.00, 0.28] | RRRRRRRRRR | 0.931 |
| 50 | 6/10 (0.60) [0.31, 0.83] | 3/10 (0.30) [0.11, 0.60] | 1 | 7/10 (0.70) [0.40, 0.89] | RTTTRRTTTI | 0.279 |
| 100 | 8/10 (0.80) [0.49, 0.94] | 0/10 (0.00) [0.00, 0.28] | 2 | 10/10 (1.00) [0.72, 1.00] | TTTTITTTTI | 0 |
| 200 | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 1 | 10/10 (1.00) [0.72, 1.00] | TTTTTITTTT | 0 |
| 400 | 8/10 (0.80) [0.49, 0.94] | 0/10 (0.00) [0.00, 0.28] | 2 | 10/10 (1.00) [0.72, 1.00] | TTTTIITTTT | 0 |

### 6. Horizon: 30000 s after the burst (record workload, 10 seeds)

**lambda = 1.35 x lambda_miss = 0.09745 sessions/s**, 30000 s after the burst (run length 31200 s):

| arm | runs | backlog > 50 at some window (collapse) | hit < 0.2 after the burst (trap onset) | released (hit > 0.5 after onset) | last window: backlog > 50 | last window: hit < 0.2 | TRAPPED in [5000, 7500] | TRAPPED in [27500, 30000] | RECOVERED in [5000, 7500] | RECOVERED in [27500, 30000] |
|---|---|---|---|---|---|---|---|---|---|---|
| NOBURST | 10 | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] |
| BURST | 10 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 4/10 (0.40) [0.17, 0.69] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] |

Per run, NOBURST (times are window END times in absolute seconds; `n/a` = the event did not happen):

| seed | collapse_s (backlog > 50) | trap_onset_s | release_s | min hit after burst | final hit | max backlog | final backlog | class [27500, 30000] | class [5000, 7500] |
|---|---|---|---|---|---|---|---|---|---|
| 0 | n/a | n/a | n/a | 0.8472 | 0.9277 | 0.03442 | 0.01301 | RECOVERED | RECOVERED |
| 1 | n/a | n/a | n/a | 0.8025 | 0.9231 | 0.03271 | 0.007025 | RECOVERED | RECOVERED |
| 2 | n/a | n/a | n/a | 0.8491 | 0.9074 | 0.03149 | 0.006106 | RECOVERED | RECOVERED |
| 3 | n/a | n/a | n/a | 0.8194 | 0.8803 | 0.02677 | 0.009045 | RECOVERED | RECOVERED |
| 4 | n/a | n/a | n/a | 0.8353 | 0.9307 | 0.03029 | 0.00621 | RECOVERED | RECOVERED |
| 5 | n/a | n/a | n/a | 0.6479 | 0.8943 | 1.74 | 0.01062 | RECOVERED | RECOVERED |
| 6 | n/a | n/a | n/a | 0.8478 | 0.9286 | 0.02736 | 0.0154 | RECOVERED | RECOVERED |
| 7 | n/a | n/a | n/a | 0.8354 | 0.9389 | 0.03423 | 0.01427 | RECOVERED | RECOVERED |
| 8 | n/a | n/a | n/a | 0.8356 | 0.913 | 0.03311 | 0.002073 | RECOVERED | RECOVERED |
| 9 | n/a | n/a | n/a | 0.7843 | 0.9172 | 0.03906 | 0.007925 | RECOVERED | RECOVERED |

Per run, BURST (times are window END times in absolute seconds; `n/a` = the event did not happen):

| seed | collapse_s (backlog > 50) | trap_onset_s | release_s | min hit after burst | final hit | max backlog | final backlog | class [27500, 30000] | class [5000, 7500] |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1400 | 1400 | n/a | 0 | 0 | 581.4 | 572.7 | TRAPPED | TRAPPED |
| 1 | 1300 | 1300 | n/a | 0 | 0 | 573.6 | 572.3 | INDETERMINATE | INDETERMINATE |
| 2 | 1400 | 1400 | n/a | 0 | 0 | 669 | 667.8 | TRAPPED | TRAPPED |
| 3 | 1400 | 1400 | n/a | 0 | 0 | 603.6 | 583.4 | INDETERMINATE | INDETERMINATE |
| 4 | 1300 | 1300 | n/a | 0 | 0 | 576.4 | 576.4 | INDETERMINATE | INDETERMINATE |
| 5 | 1400 | 1400 | n/a | 0 | 0 | 517.8 | 517.8 | TRAPPED | TRAPPED |
| 6 | 1300 | 1400 | n/a | 0 | 0 | 638.8 | 624.8 | INDETERMINATE | TRAPPED |
| 7 | 1400 | 1400 | n/a | 0 | 0 | 542.2 | 542.2 | INDETERMINATE | TRAPPED |
| 8 | 1400 | 1400 | n/a | 0 | 0 | 518.4 | 506.9 | TRAPPED | TRAPPED |
| 9 | 1300 | 1400 | n/a | 0 | 0 | 479.2 | 468.2 | INDETERMINATE | INDETERMINATE |

**lambda = 1.65 x lambda_miss = 0.11911 sessions/s**, 30000 s after the burst (run length 31200 s):

| arm | runs | backlog > 50 at some window (collapse) | hit < 0.2 after the burst (trap onset) | released (hit > 0.5 after onset) | last window: backlog > 50 | last window: hit < 0.2 | TRAPPED in [5000, 7500] | TRAPPED in [27500, 30000] | RECOVERED in [5000, 7500] | RECOVERED in [27500, 30000] |
|---|---|---|---|---|---|---|---|---|---|---|
| NOBURST | 10 | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] |
| BURST | 10 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0/10 (0.00) [0.00, 0.28] |

Per run, NOBURST (times are window END times in absolute seconds; `n/a` = the event did not happen):

| seed | collapse_s (backlog > 50) | trap_onset_s | release_s | min hit after burst | final hit | max backlog | final backlog | class [27500, 30000] | class [5000, 7500] |
|---|---|---|---|---|---|---|---|---|---|
| 0 | n/a | n/a | n/a | 0.8471 | 0.9215 | 0.0351 | 0.01856 | RECOVERED | RECOVERED |
| 1 | n/a | n/a | n/a | 0.5765 | 0.9415 | 2.98 | 0.01437 | RECOVERED | RECOVERED |
| 2 | n/a | n/a | n/a | 0.8636 | 0.9497 | 0.04603 | 0.02135 | RECOVERED | RECOVERED |
| 3 | n/a | n/a | n/a | 0.8455 | 0.9167 | 0.04661 | 0.01929 | RECOVERED | RECOVERED |
| 4 | n/a | n/a | n/a | 0.8444 | 0.9453 | 0.03607 | 0.01893 | RECOVERED | RECOVERED |
| 5 | n/a | n/a | n/a | 0.8364 | 0.8954 | 0.1494 | 0.01591 | RECOVERED | RECOVERED |
| 6 | n/a | n/a | n/a | 0.8434 | 0.9175 | 0.08867 | 0.01606 | RECOVERED | RECOVERED |
| 7 | n/a | n/a | n/a | 0.8551 | 0.945 | 0.04439 | 0.02229 | RECOVERED | RECOVERED |
| 8 | n/a | n/a | n/a | 0.8228 | 0.9358 | 0.4001 | 0.004795 | RECOVERED | RECOVERED |
| 9 | n/a | n/a | n/a | 0.8571 | 0.9133 | 0.04308 | 0.01147 | RECOVERED | RECOVERED |

Per run, BURST (times are window END times in absolute seconds; `n/a` = the event did not happen):

| seed | collapse_s (backlog > 50) | trap_onset_s | release_s | min hit after burst | final hit | max backlog | final backlog | class [27500, 30000] | class [5000, 7500] |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1300 | 1300 | n/a | 0 | 0 | 1014 | 1012 | TRAPPED | TRAPPED |
| 1 | 1400 | 1300 | n/a | 0 | 0 | 981.6 | 981.6 | INDETERMINATE | INDETERMINATE |
| 2 | 1300 | 1300 | n/a | 0 | 0 | 1066 | 1065 | INDETERMINATE | TRAPPED |
| 3 | 1300 | 1300 | n/a | 0 | 0 | 1011 | 1011 | TRAPPED | INDETERMINATE |
| 4 | 1300 | 1400 | n/a | 0 | 0 | 975.8 | 975.7 | TRAPPED | INDETERMINATE |
| 5 | 1400 | 1400 | n/a | 0 | 0 | 902.3 | 898.9 | INDETERMINATE | INDETERMINATE |
| 6 | 1300 | 1300 | n/a | 0 | 0 | 1050 | 1049 | TRAPPED | TRAPPED |
| 7 | 1400 | 1400 | n/a | 0 | 0 | 982.7 | 979 | TRAPPED | TRAPPED |
| 8 | 1400 | 1400 | n/a | 0 | 0 | 913.1 | 902.9 | TRAPPED | TRAPPED |
| 9 | 1400 | 1400 | n/a | 0 | 0 | 870.6 | 869.4 | INDETERMINATE | TRAPPED |

### 7. Low-lambda fragility (record workload, 1.35 x lambda_miss, 20 seeds, BURST)

lambda = 1.35 x lambda_miss = 0.09745 sessions/s; threshold 0.5 (lambda - lambda_miss) = 0.01263 requests/s; 20 BURST runs.

Slope exceeds the threshold in 17/20 (0.85) [0.64, 0.95]; token rate within 15% of all-miss in 20/20 (1.00) [0.84, 1.00]; hit < 0.05 in 20/20 (1.00) [0.84, 1.00].

Quantiles over the runs:

| quantity | q000 | q005 | q025 | q050 | q075 | q095 | q100 |
|---|---|---|---|---|---|---|---|
| backlog slope over the last 2500 s (requests/s) | 0.005997 | 0.006275 | 0.01497 | 0.01949 | 0.02324 | 0.02625 | 0.0281 |
| slope / threshold | 0.4747 | 0.4967 | 1.185 | 1.543 | 1.84 | 2.078 | 2.224 |
| slope / (lambda - lambda_miss) | 0.2374 | 0.2484 | 0.5924 | 0.7714 | 0.9199 | 1.039 | 1.112 |
| uncached-token rate / all-miss rate | 1.006 | 1.006 | 1.013 | 1.016 | 1.022 | 1.029 | 1.031 |
| hit rate over the last 2500 s | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Classes:

| class | runs |
|---|---|
| TRAPPED | 17/20 (0.85) [0.64, 0.95] |
| INDETERMINATE | 3/20 (0.15) [0.05, 0.36] |

Per run, sorted by slope:

| seed | hit | backlog | token_ratio | slope | slope / threshold | slope_threshold | rate_ok | slope_ok | label |
|---|---|---|---|---|---|---|---|---|---|
| 119 | 0 | 116.4 | 1.019 | 0.005997 | 0.4747 | 0.01263 | True | False | INDETERMINATE |
| 109 | 0 | 181.5 | 1.017 | 0.00629 | 0.4979 | 0.01263 | True | False | INDETERMINATE |
| 117 | 0 | 189.5 | 1.015 | 0.0115 | 0.9107 | 0.01263 | True | False | INDETERMINATE |
| 101 | 0 | 151.9 | 1.017 | 0.01291 | 1.022 | 0.01263 | True | True | TRAPPED |
| 108 | 0 | 158.4 | 1.01 | 0.01309 | 1.036 | 0.01263 | True | True | TRAPPED |
| 118 | 0 | 211.8 | 1.028 | 0.01559 | 1.234 | 0.01263 | True | True | TRAPPED |
| 113 | 0 | 190.3 | 1.022 | 0.01647 | 1.304 | 0.01263 | True | True | TRAPPED |
| 105 | 0 | 186.2 | 1.014 | 0.01663 | 1.316 | 0.01263 | True | True | TRAPPED |
| 106 | 0 | 153.3 | 1.006 | 0.01775 | 1.405 | 0.01263 | True | True | TRAPPED |
| 100 | 0 | 211.5 | 1.012 | 0.01882 | 1.49 | 0.01263 | True | True | TRAPPED |
| 102 | 0 | 192.4 | 1.013 | 0.02016 | 1.595 | 0.01263 | True | True | TRAPPED |
| 104 | 0 | 187.1 | 1.026 | 0.02022 | 1.601 | 0.01263 | True | True | TRAPPED |
| 115 | 0 | 197.8 | 1.015 | 0.02135 | 1.69 | 0.01263 | True | True | TRAPPED |
| 111 | 0 | 202.8 | 1.016 | 0.02292 | 1.815 | 0.01263 | True | True | TRAPPED |
| 110 | 0 | 225.3 | 1.031 | 0.02303 | 1.823 | 0.01263 | True | True | TRAPPED |
| 112 | 0 | 199.6 | 1.013 | 0.02388 | 1.891 | 0.01263 | True | True | TRAPPED |
| 103 | 0 | 212.8 | 1.006 | 0.02517 | 1.992 | 0.01263 | True | True | TRAPPED |
| 116 | 0 | 181 | 1.021 | 0.02521 | 1.995 | 0.01263 | True | True | TRAPPED |
| 114 | 0 | 235.9 | 1.023 | 0.02615 | 2.07 | 0.01263 | True | True | TRAPPED |
| 107 | 0 | 173.7 | 1.01 | 0.0281 | 2.224 | 0.01263 | True | True | TRAPPED |

### 8. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (5 workloads x 2 points, seeds 0-9) | 100 | 90/100 (0.90) [0.83, 0.94] | 10/100 (0.10) [0.06, 0.17] | 0/100 (0.00) [0.00, 0.04] | 0/100 (0.00) [0.00, 0.04] | 100/100 (1.00) [0.96, 1.00] |
| pairs, record workload only (1.35 and 1.65 x, seeds 0-9) | 20 | 18/20 (0.90) [0.70, 0.97] | 2/20 (0.10) [0.03, 0.30] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| burst_sizes, 200 sessions (bit-identical to the record-workload rows of pairs) | 20 | 18/20 (0.90) [0.70, 0.97] | 2/20 (0.10) [0.03, 0.30] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| horizon, window [27500, 30000] of the 31200 s runs (new realisations, seeds 0-9) | 20 | 10/20 (0.50) [0.30, 0.70] | 10/20 (0.50) [0.30, 0.70] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| horizon, window [5000, 7500] of the 31200 s runs (new realisations, seeds 0-9) | 20 | 12/20 (0.60) [0.39, 0.78] | 8/20 (0.40) [0.22, 0.61] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |
| lowlam, 1.35 x, seeds 100-119 | 20 | 17/20 (0.85) [0.64, 0.95] | 3/20 (0.15) [0.05, 0.36] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |
