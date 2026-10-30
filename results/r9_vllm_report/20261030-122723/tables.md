## Overview

Landmarks per variant and mode:

| variant | mode | lambda_miss turns-based (sessions/s) | all-miss token rate (tok/s) | peak n | peak mu (sessions/s) | peak mu / lambda_miss | cap n (B4v rule) | n at hit 0.5 | edge hi (x lambda_miss) | edge in real units (hi x 0.0657) | edge censored |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 0.07219 | 1.122e+04 | 24 | 0.2217 | 3.071 | 20 | 31.46 | 2 | 0.1314 | False |
| V0 | separate | 0.07136 | 1.115e+04 | 24 | 0.2208 | 3.095 | 20 | 32.6 | 2 | 0.1314 | False |
| V1 | mixed | 0.06623 | 1.036e+04 | 24 | 0.2154 | 3.253 | 20 | 31.42 | 2 | 0.1314 | False |
| V1 | separate | 0.06633 | 1.034e+04 | 24 | 0.2151 | 3.243 | 20 | 32.41 | 2 | 0.1314 | False |

B3v at the cap the B4v rule picks, every candidate multiple (the full tables, with the other caps, are in the blocks below):

| variant | mode | x lambda_miss | picked cap | BURST trapped | NOBURST good | CAPPED recovered | PASS per-arm | same-seed count | PASS same-seed |
|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 1.1 | 20 | 4/10 | 10/10 | 10/10 | FAIL | 4/10 | FAIL |
| V0 | mixed | 1.15 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.5 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V0 | mixed | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2 | 20 | 10/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.1 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.15 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.25 | 20 | 10/10 | 10/10 | 10/10 | PASS | 10/10 | PASS |
| V0 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 1.5 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V1 | mixed | 1.1 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | mixed | 1.15 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.5 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.65 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | mixed | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 2.35 | 20 | 10/10 | 7/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | separate | 1.1 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.15 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.5 | 20 | 10/10 | 10/10 | 10/10 | PASS | 10/10 | PASS |
| V1 | separate | 1.65 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | separate | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 2.35 | 20 | 10/10 | 7/10 | 10/10 | PASS | 7/10 | PASS |

## V0 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 0.071986 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 11,219.7 tok/s = 1.0841 x the vLLM rate; lambda_miss 0.07219 sessions/s = 1.0987 x the vLLM value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

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

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2217 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.071 |
| hit fraction at the peak n | 0.8898 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.222 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.46 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.99 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 36.9 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.6, s1: 32.8, s2: 30.5, s3: 30.4, s4: 30.4, s5: 32.8, s6: 31.3, s7: 32.1, s8: 33.3, s9: 30.0 |
| mu(300) / peak mu | 0.5047 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0239; -0.1607 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1735 / 0.1774 / 0.1766 / 0.1733 / 0.1790 / 0.1787 / 0.1769 / 0.1776 / 0.1761 / 0.1784 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2130 / 0.2170 / 0.2132 / 0.2137 / 0.2201 / 0.2108 / 0.2156 / 0.2179 / 0.2174 / 0.2176 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2261 / 0.2224 / 0.1904 / 0.2063 / 0.2435 / 0.1813 / 0.2105 / 0.2476 / 0.2473 / 0.2413 | 0.91 / 0.89 / 0.85 / 0.88 / 0.91 / 0.84 / 0.87 / 0.92 / 0.92 / 0.91 |
| 28 | 0.2032 / 0.1871 / 0.1413 / 0.1462 / 0.1729 / 0.1244 / 0.1241 / 0.1979 / 0.2083 / 0.1667 | 0.82 / 0.79 / 0.70 / 0.70 / 0.76 / 0.65 / 0.62 / 0.81 / 0.82 / 0.75 |
| 32 | 0.1458 / 0.1285 / 0.0935 / 0.0959 / 0.0866 / 0.1246 / 0.1081 / 0.1184 / 0.1415 / 0.0786 | 0.62 / 0.55 / 0.38 / 0.37 / 0.33 / 0.55 / 0.48 / 0.51 / 0.60 / 0.25 |
| 40 | 0.0735 / 0.0699 / 0.0765 / 0.0704 / 0.0643 / 0.0830 / 0.0744 / 0.0735 / 0.0738 / 0.0674 | 0.02 / 0.00 / 0.07 / 0.03 / 0.00 / 0.07 / 0.05 / 0.05 / 0.01 / 0.03 |
| 48 | 0.0706 / 0.0702 / 0.0734 / 0.0698 / 0.0637 / 0.0775 / 0.0739 / 0.0749 / 0.0725 / 0.0650 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0750 / 0.0741 / 0.0783 / 0.0788 / 0.0743 / 0.0784 / 0.0785 / 0.0880 / 0.0793 / 0.0817 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1128 / 0.1102 / 0.1105 / 0.1142 / 0.1103 / 0.1098 / 0.1104 / 0.1148 / 0.1145 / 0.1113 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

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

**Edge hi = 2 x lambda_miss = 0.1444 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07219; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.06 x and through 0.5 at 2.6 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07941 | hi = 1.25 (low) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.996 to 1.010 | 148.8 | 0 | 0.007708 | IITTIITTII | RRRRRRRRRR |
| 1.15 | 0.08301 | hi = 1.25 (high); hi = 1.5 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.994 to 1.015 | 152.3 | 0 | 0.008271 | ITTTIITTTI | RRRRRRRRRR |
| 1.25 | 0.09023 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.999 to 1.020 | 170.5 | 0 | 0.0097 | TTTTITTTTT | RRRRRRRRRR |
| 1.35 | 0.09745 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.006 to 1.026 | 198.4 | 0 | 0.01067 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.1083 | hi = 1.75 (high); hi = 2.5 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.018 to 1.034 | 249.9 | 0 | 0.01289 | TTTTIITTTI | RRRRRRRRRR |
| 1.65 | 0.1191 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.027 to 1.043 | 290.2 | 0 | 0.01506 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1444 | hi = 2.5 (high) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.048 to 1.059 | 399.1 | 0 | 19.56 | TTTTTTTTTT | RRRRRTRRRR |
| 2.35 | 0.1696 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.063 to 1.073 | 522.5 | 0 | 120.4 | TTTTTTTTTT | RRTRRTRTRT |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.01176 | 0.9312 |
| 1.1 (extra) | 20 * | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00771 | 0.9312 |
| 1.1 (extra) | 24 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00769 | 0.9312 |
| 1.1 (extra) | 28 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.007709 | 0.9312 |
| 1.1 (extra) | 32 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 19.21 | 0.7532 |
| 1.1 (extra) | 40 (extra) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.8 | 0.08885 |
| 1.15 | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01589 | 0.9314 |
| 1.15 | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008452 | 0.9314 |
| 1.15 | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008271 | 0.9314 |
| 1.15 | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00829 | 0.9314 |
| 1.15 | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 25.26 | 0.7722 |
| 1.15 | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.8 | 0.08945 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.04198 | 0.9308 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01006 | 0.9308 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0097 | 0.9308 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009669 | 0.9308 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 36.17 | 0.7766 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 235.1 | 0.08596 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06429 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0184 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01068 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01074 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 60.62 | 0.6711 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 276.3 | 0.08874 |
| 1.5 | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.09209 | 0.9313 |
| 1.5 | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01914 | 0.9314 |
| 1.5 | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01313 | 0.9314 |
| 1.5 | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.8441 | 0.9234 |
| 1.5 | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 128.3 | 0.4841 |
| 1.5 | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 345.5 | 0.08463 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1464 | 0.9313 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01706 | 0.9313 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01505 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 6.718 | 0.9098 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.6 | 0.4838 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 417 | 0.08505 |
| 2 | 16 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 21.95 | 0.9331 |
| 2 | 20 * | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2795 | 0.9332 |
| 2 | 24 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06608 | 0.9319 |
| 2 | 28 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 5/10 (0.50) [0.24, 0.76] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 55.58 | 0.834 |
| 2 | 32 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 358.9 | 0.4929 |
| 2 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 585.8 | 0.07931 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 174.9 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.569 | 0.9317 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.028 | 0.9242 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 165 | 0.79 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 528.2 | 0.4758 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 760.2 | 0.07562 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTIITTII | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | ITTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTTTTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RRTRRTRTRT | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V0 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.071359 | 0.0012945 | 0.068889 | 11147 | 0.99999 | 0.071221 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 11,146.8 tok/s = 1.0771 x the vLLM rate; lambda_miss 0.07136 sessions/s = 1.0861 x the vLLM value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1755 / 0.93 |
| 20 | 0.2137 / 0.93 |
| 24 | 0.2208 / 0.89 |
| 28 | 0.1797 / 0.77 |
| 32 | 0.1222 / 0.53 |
| 40 | 0.0767 / 0.11 |
| 48 | 0.0710 / 0.01 |
| 96 | 0.0781 / 0.00 |
| 300 | 0.1115 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2208 | 20 | 0.5051 | 0 | 24 | 0.2215 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2208 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.095 |
| hit fraction at the peak n | 0.8917 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2215 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 32.6 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 23.14 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 38.22 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 34.6, s1: 33.4, s2: 31.1, s3: 32.4, s4: 31.2, s5: 33.2, s6: 31.8, s7: 32.6, s8: 33.6, s9: 32.1 |
| mu(300) / peak mu | 0.5051 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0184; -0.1633 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1724 / 0.1764 / 0.1754 / 0.1721 / 0.1777 / 0.1773 / 0.1755 / 0.1766 / 0.1750 / 0.1771 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2099 / 0.2152 / 0.2110 / 0.2118 / 0.2177 / 0.2100 / 0.2134 / 0.2161 / 0.2157 / 0.2158 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2248 / 0.2183 / 0.1910 / 0.2204 / 0.2358 / 0.1933 / 0.2144 / 0.2453 / 0.2385 / 0.2267 | 0.91 / 0.89 / 0.85 / 0.89 / 0.91 / 0.86 / 0.88 / 0.91 / 0.91 / 0.90 |
| 28 | 0.2015 / 0.1939 / 0.1445 / 0.1490 / 0.1932 / 0.1313 / 0.1476 / 0.2251 / 0.2204 / 0.1903 | 0.82 / 0.80 / 0.71 / 0.70 / 0.79 / 0.67 / 0.69 / 0.84 / 0.84 / 0.79 |
| 32 | 0.1520 / 0.1417 / 0.0980 / 0.1185 / 0.1017 / 0.1256 / 0.1101 / 0.1218 / 0.1415 / 0.1112 | 0.65 / 0.60 / 0.44 / 0.52 / 0.43 / 0.57 / 0.49 / 0.53 / 0.60 / 0.50 |
| 40 | 0.0871 / 0.0723 / 0.0801 / 0.0753 / 0.0694 / 0.0829 / 0.0771 / 0.0754 / 0.0802 / 0.0670 | 0.20 / 0.06 / 0.13 / 0.12 / 0.09 / 0.09 / 0.10 / 0.11 / 0.11 / 0.05 |
| 48 | 0.0701 / 0.0700 / 0.0763 / 0.0694 / 0.0627 / 0.0774 / 0.0733 / 0.0741 / 0.0718 / 0.0647 | 0.01 / 0.00 / 0.05 / 0.01 / 0.00 / 0.01 / 0.01 / 0.00 / 0.00 / 0.01 |
| 96 | 0.0752 / 0.0737 / 0.0772 / 0.0777 / 0.0743 / 0.0778 / 0.0781 / 0.0871 / 0.0784 / 0.0814 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1125 / 0.1099 / 0.1102 / 0.1137 / 0.1102 / 0.1098 / 0.1100 / 0.1144 / 0.1139 / 0.1109 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.0892 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001459 | 0.9314 | 0 |
| Exp(5 s) (record) | 1.5 | 0.107 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006232 | 0.9297 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1249 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0009475 | 0.9294 | 0 |
| Exp(5 s) (record) | 2 | 0.1427 | 10/10 (1.00) [0.72, 1.00] | True | 0.4 | 4 | 0.4368 | 0.9257 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1784 | 8/10 (0.80) [0.49, 0.94] | False | 18.6 | 115 | 16.01 | 0.801 | 0 |
| Exp(5 s) (record) | 3 | 0.2141 | 1/10 (0.10) [0.02, 0.40] | False | 177 | 283 | 124.2 | 0.2039 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.071359 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1427 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07136; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.12 x and through 0.5 at 2.71 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07849 | hi = 1.25 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.005 | 149.7 | 0 | 0.007337 | IITTTITTIT | RRRRRRRRRR |
| 1.15 | 0.08206 | hi = 1.25 (high); hi = 1.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.015 | 161.3 | 0 | 0.008262 | TTTTTITTTI | RRRRRRRRRR |
| 1.25 | 0.0892 | hi = 1.75 (low) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.995 to 1.015 | 179.5 | 0 | 0.009333 | TTTTTTTTTT | RRRRRRRRRR |
| 1.35 | 0.09633 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.021 | 206.9 | 0 | 0.01043 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.107 | hi = 1.75 (high); hi = 2.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.014 to 1.027 | 252.4 | 0 | 0.0124 | TTTTIITTTT | RRRRRRRRRR |
| 1.65 | 0.1177 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.022 to 1.038 | 295.4 | 0 | 0.01452 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1427 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.043 to 1.051 | 409.2 | 0 | 20.24 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1677 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.066 | 521.4 | 0 | 125.5 | TTTTTTTTTT | RTTRRTRTRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01119 | 0.9313 |
| 1.1 (extra) | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007326 | 0.9313 |
| 1.1 (extra) | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007339 | 0.9313 |
| 1.1 (extra) | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00732 | 0.9313 |
| 1.1 (extra) | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 6.446 | 0.8805 |
| 1.1 (extra) | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 140.2 | 0.1696 |
| 1.15 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02577 | 0.9316 |
| 1.15 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008418 | 0.9316 |
| 1.15 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008245 | 0.9316 |
| 1.15 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008253 | 0.9316 |
| 1.15 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 5/10 (0.50) [0.24, 0.76] | FAIL | 11.26 | 0.8277 |
| 1.15 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 167.9 | 0.1429 |
| 1.25 | 16 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.04704 | 0.9307 |
| 1.25 | 20 * | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01016 | 0.9307 |
| 1.25 | 24 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009299 | 0.9307 |
| 1.25 | 28 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009296 | 0.9307 |
| 1.25 | 32 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 1 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 18.64 | 0.8112 |
| 1.25 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 211.2 | 0.1688 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06025 | 0.9308 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01775 | 0.9308 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0105 | 0.9308 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01043 | 0.9308 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 29.79 | 0.7971 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 249 | 0.1521 |
| 1.5 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.09019 | 0.9313 |
| 1.5 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02162 | 0.9313 |
| 1.5 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.014 | 0.9313 |
| 1.5 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01245 | 0.9313 |
| 1.5 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 79.29 | 0.6274 |
| 1.5 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 313.1 | 0.1551 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1452 | 0.9312 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01615 | 0.9312 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01464 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2905 | 0.9286 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 134.6 | 0.5421 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 386.9 | 0.1566 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 19.74 | 0.9331 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2189 | 0.9331 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05659 | 0.9323 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 27.86 | 0.8781 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 306.7 | 0.5455 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 561.4 | 0.1339 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.3 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.461 | 0.9321 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.2392 | 0.9277 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 121.2 | 0.8169 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 457.7 | 0.5362 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 724.6 | 0.1379 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRTRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.066228 | 0.00073592 | 0.065926 | 10358 | 1 | 0.066805 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 10,358.3 tok/s = 1.0009 x the vLLM rate; lambda_miss 0.06623 sessions/s = 1.0080 x the vLLM value. V1 factor f = 1.0882 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 10,358.30 tok/s, +0.09% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

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

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2154 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.253 |
| hit fraction at the peak n | 0.8883 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2153 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.42 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.87 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 36.79 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.3, s1: 31.4, s2: 30.6, s3: 30.8, s4: 30.5, s5: 32.9, s6: 31.6, s7: 31.1, s8: 33.6, s9: 30.1 |
| mu(300) / peak mu | 0.4934 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0393; -0.1433 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1724 / 0.1763 / 0.1752 / 0.1719 / 0.1777 / 0.1770 / 0.1750 / 0.1763 / 0.1747 / 0.1768 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2096 / 0.2152 / 0.2100 / 0.2115 / 0.2175 / 0.2040 / 0.2126 / 0.2158 / 0.2153 / 0.2156 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2275 / 0.2162 / 0.1734 / 0.2155 / 0.2372 / 0.1707 / 0.2084 / 0.2422 / 0.2382 / 0.2251 | 0.91 / 0.89 / 0.83 / 0.89 / 0.91 / 0.83 / 0.88 / 0.91 / 0.91 / 0.90 |
| 28 | 0.2164 / 0.1843 / 0.1301 / 0.1424 / 0.1592 / 0.1234 / 0.1263 / 0.1885 / 0.1918 / 0.1551 | 0.85 / 0.80 / 0.69 / 0.70 / 0.74 / 0.67 / 0.65 / 0.80 / 0.81 / 0.74 |
| 32 | 0.1328 / 0.1006 / 0.0920 / 0.0944 / 0.0847 / 0.1212 / 0.1019 / 0.0981 / 0.1431 / 0.0759 | 0.60 / 0.45 / 0.40 / 0.42 / 0.36 / 0.56 / 0.48 / 0.41 / 0.63 / 0.28 |
| 40 | 0.0662 / 0.0647 / 0.0712 / 0.0642 / 0.0586 / 0.0718 / 0.0707 / 0.0696 / 0.0664 / 0.0598 | 0.00 / 0.00 / 0.07 / 0.01 / 0.00 / 0.02 / 0.06 / 0.08 / 0.00 / 0.02 |
| 48 | 0.0647 / 0.0643 / 0.0670 / 0.0647 / 0.0580 / 0.0714 / 0.0688 / 0.0704 / 0.0668 / 0.0589 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0709 / 0.0694 / 0.0725 / 0.0747 / 0.0707 / 0.0737 / 0.0741 / 0.0823 / 0.0754 / 0.0770 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1072 / 0.1048 / 0.1049 / 0.1089 / 0.1050 / 0.1041 / 0.1047 / 0.1093 / 0.1083 / 0.1056 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

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

**Edge hi = 2 x lambda_miss = 0.1325 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.06623; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.08 x and through 0.5 at 2.75 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07285 | hi = 1.25 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.991 to 1.004 | 135.5 | 0 | 0.007196 | ITTTTITTIT | RRRRRRRRRR |
| 1.15 | 0.07616 | hi = 1.25 (high); hi = 1.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.992 to 1.012 | 142.9 | 0 | 0.007817 | TTTTTITTTT | RRRRRRRRRR |
| 1.25 | 0.08278 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.019 | 169.2 | 0 | 0.009012 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.08941 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.009 to 1.024 | 193.6 | 0 | 0.01022 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.09934 | hi = 1.75 (high); hi = 2.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.017 to 1.034 | 233.2 | 0 | 0.01195 | TTTTTITTTT | RRRRRRRRRR |
| 1.65 | 0.1093 | hi = 2 (high); hi = 3 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.028 to 1.044 | 277 | 0 | 0.01425 | TTTTIITTTI | RRRRRRRRRR |
| 2 | 0.1325 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.047 to 1.056 | 375.8 | 0 | 15.82 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1556 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 1.058 to 1.068 | 480.7 | 0 | 91.22 | TTTTTTTTTT | RTTRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.009176 | 0.9313 |
| 1.1 (extra) | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007184 | 0.9313 |
| 1.1 (extra) | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007184 | 0.9313 |
| 1.1 (extra) | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007183 | 0.9313 |
| 1.1 (extra) | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 21.54 | 0.7221 |
| 1.1 (extra) | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.9 | 0.08154 |
| 1.15 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007817 | 0.9312 |
| 1.15 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007805 | 0.9312 |
| 1.15 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007806 | 0.9312 |
| 1.15 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007789 | 0.9312 |
| 1.15 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 31.16 | 0.728 |
| 1.15 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 189.2 | 0.08148 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.02014 | 0.9314 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009294 | 0.9314 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009014 | 0.9314 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008967 | 0.9314 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 5/10 (0.50) [0.24, 0.76] | 1 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 46.82 | 0.6594 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 232.2 | 0.08693 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05307 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01129 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01016 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01015 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 1 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 69.13 | 0.6218 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 271.6 | 0.08946 |
| 1.5 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.07421 | 0.931 |
| 1.5 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01885 | 0.931 |
| 1.5 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01198 | 0.931 |
| 1.5 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.7261 | 0.9134 |
| 1.5 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 125.7 | 0.504 |
| 1.5 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 329.9 | 0.07164 |
| 1.65 | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.07807 | 0.9312 |
| 1.65 | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01426 | 0.9312 |
| 1.65 | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01406 | 0.9312 |
| 1.65 | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 6.811 | 0.9034 |
| 1.65 | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 196.7 | 0.4314 |
| 1.65 | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 393.1 | 0.07283 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 2.242 | 0.9318 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1283 | 0.9318 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.03132 | 0.9312 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 61.65 | 0.8177 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 353 | 0.431 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 548 | 0.08567 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 1/10 (0.10) [0.02, 0.40] | 0 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 88.6 | 0.9329 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.4853 | 0.9328 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.06998 | 0.9327 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 161.5 | 0.801 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 503.5 | 0.4466 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 702.6 | 0.07068 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | ITTTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.066328 | 0.00040244 | 0.06537 | 10342 | 0.9999 | 0.065601 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 10,341.9 tok/s = 0.9993 x the vLLM rate; lambda_miss 0.06633 sessions/s = 1.0096 x the vLLM value. V1 factor f = 1.0806 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 10,341.87 tok/s, -0.07% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1742 / 0.93 |
| 20 | 0.2114 / 0.93 |
| 24 | 0.2151 / 0.89 |
| 28 | 0.1650 / 0.75 |
| 32 | 0.1152 / 0.52 |
| 40 | 0.0709 / 0.10 |
| 48 | 0.0656 / 0.01 |
| 96 | 0.0738 / 0.00 |
| 300 | 0.1048 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2151 | 20 | 0.4869 | 0 | 24 | 0.2159 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2151 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.243 |
| hit fraction at the peak n | 0.8897 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2159 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 32.41 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.98 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 38.17 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 34.3, s1: 33.7, s2: 31.5, s3: 32.2, s4: 31.1, s5: 33.2, s6: 31.9, s7: 33.0, s8: 33.7, s9: 30.3 |
| mu(300) / peak mu | 0.4869 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0342; -0.1475 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1717 / 0.1750 / 0.1742 / 0.1705 / 0.1766 / 0.1755 / 0.1739 / 0.1753 / 0.1740 / 0.1757 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2087 / 0.2133 / 0.2101 / 0.2096 / 0.2156 / 0.2045 / 0.2110 / 0.2134 / 0.2141 / 0.2135 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2132 / 0.2173 / 0.1764 / 0.2102 / 0.2334 / 0.1795 / 0.2122 / 0.2386 / 0.2394 / 0.2311 | 0.90 / 0.89 / 0.84 / 0.89 / 0.91 / 0.84 / 0.89 / 0.91 / 0.92 / 0.91 |
| 28 | 0.2018 / 0.1880 / 0.1428 / 0.1466 / 0.1540 / 0.1238 / 0.1287 / 0.1997 / 0.2021 / 0.1622 | 0.83 / 0.81 / 0.72 / 0.71 / 0.73 / 0.67 / 0.66 / 0.82 / 0.82 / 0.75 |
| 32 | 0.1413 / 0.1328 / 0.0979 / 0.1120 / 0.0959 / 0.1247 / 0.1044 / 0.1228 / 0.1402 / 0.0796 | 0.63 / 0.60 / 0.47 / 0.51 / 0.44 / 0.58 / 0.49 / 0.55 / 0.62 / 0.31 |
| 40 | 0.0779 / 0.0716 / 0.0743 / 0.0658 / 0.0625 / 0.0718 / 0.0788 / 0.0721 / 0.0683 / 0.0661 | 0.17 / 0.11 / 0.12 / 0.06 / 0.09 / 0.02 / 0.19 / 0.12 / 0.04 / 0.12 |
| 48 | 0.0645 / 0.0642 / 0.0686 / 0.0638 / 0.0586 / 0.0716 / 0.0684 / 0.0710 / 0.0666 / 0.0584 | 0.02 / 0.00 / 0.02 / 0.00 / 0.01 / 0.01 / 0.00 / 0.02 / 0.00 / 0.00 |
| 96 | 0.0710 / 0.0689 / 0.0726 / 0.0748 / 0.0701 / 0.0733 / 0.0739 / 0.0816 / 0.0753 / 0.0769 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1059 / 0.1033 / 0.1035 / 0.1070 / 0.1037 / 0.1028 / 0.1030 / 0.1080 / 0.1064 / 0.1040 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.08291 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001759 | 0.9326 | 0 |
| Exp(5 s) (record) | 1.5 | 0.09949 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -1.641e-05 | 0.9308 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1161 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0008713 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1327 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.004477 | 0.9304 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1658 | 7/10 (0.70) [0.40, 0.89] | False | 18.9 | 117 | 14.22 | 0.7959 | 0 |
| Exp(5 s) (record) | 3 | 0.199 | 3/10 (0.30) [0.11, 0.60] | False | 137.5 | 252 | 98.87 | 0.3172 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.066328 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1327 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.06633; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.08 x and through 0.5 at 2.75 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07296 | hi = 1.25 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.988 to 1.008 | 139 | 0 | 0.007273 | TTTTTITTTT | RRRRRRRRRR |
| 1.15 | 0.07628 | hi = 1.25 (high); hi = 1.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.991 to 1.008 | 151.6 | 0 | 0.007641 | TTTTTITTTT | RRRRRRRRRR |
| 1.25 | 0.08291 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.999 to 1.017 | 178.4 | 0 | 0.00875 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.08954 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.008 to 1.023 | 203.2 | 0 | 0.009878 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.09949 | hi = 1.75 (high); hi = 2.5 (low) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.015 to 1.035 | 238.3 | 0 | 0.01166 | TTTTTTTTTT | RRRRRRRRRR |
| 1.65 | 0.1094 | hi = 2 (high); hi = 3 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.026 to 1.042 | 280.9 | 0 | 0.01389 | TTTTIITTTT | RRRRRRRRRR |
| 2 | 0.1327 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.044 to 1.054 | 386.4 | 0 | 17.07 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1559 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.065 | 492.5 | 0 | 100.4 | TTTTTTTTTT | RTTRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01047 | 0.9313 |
| 1.1 (extra) | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007273 | 0.9313 |
| 1.1 (extra) | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007274 | 0.9313 |
| 1.1 (extra) | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007273 | 0.9313 |
| 1.1 (extra) | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 7.845 | 0.8713 |
| 1.1 (extra) | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 143.5 | 0.1914 |
| 1.15 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.00765 | 0.9311 |
| 1.15 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007641 | 0.9311 |
| 1.15 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007641 | 0.9311 |
| 1.15 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007658 | 0.9311 |
| 1.15 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 9.852 | 0.8371 |
| 1.15 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 167.7 | 0.1674 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01882 | 0.9314 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008982 | 0.9315 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008757 | 0.9315 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008637 | 0.9315 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 27.68 | 0.7915 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 206.1 | 0.1703 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05013 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01112 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009751 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009981 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 42.74 | 0.7564 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 250.9 | 0.1641 |
| 1.5 | 16 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.08075 | 0.931 |
| 1.5 | 20 * | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.02031 | 0.931 |
| 1.5 | 24 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01168 | 0.931 |
| 1.5 | 28 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01161 | 0.931 |
| 1.5 | 32 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 1 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 83.09 | 0.5837 |
| 1.5 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 305.1 | 0.1671 |
| 1.65 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.08731 | 0.9311 |
| 1.65 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01422 | 0.9312 |
| 1.65 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01391 | 0.9312 |
| 1.65 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 1.55 | 0.9149 |
| 1.65 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 153.9 | 0.5167 |
| 1.65 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 370.7 | 0.1359 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 2.864 | 0.9319 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1254 | 0.9319 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.04568 | 0.9311 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 31.1 | 0.8733 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 308.1 | 0.5091 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 518.1 | 0.1532 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 97.11 | 0.9329 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.4858 | 0.9329 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.06635 | 0.9326 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 117.3 | 0.8218 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 435.5 | 0.534 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 672.9 | 0.1563 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.
