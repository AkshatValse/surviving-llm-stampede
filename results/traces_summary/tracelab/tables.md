## tracelab

### Tool time (seconds; wall clock between request and result unless 'internal')

| series | n | mean (s) | median | p90 | p99 | CV | mean cap600 | CV cap600 | <1 s | >60 s | share of time >60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| call_wall_nohuman/all | 740,637 | 11.3 | 0.216 | 10.0 | 131 | 39.9 | 7.13 | 5.03 | 66% | 2.7% | 77% |
| call_wall_nohuman/claude | 301,942 | 18.2 | 0.113 | 9.00 | 197 | 37.3 | 9.39 | 5.08 | 72% | 3.8% | 88% |
| call_wall_nohuman/codex | 438,695 | 6.48 | 0.384 | 10.1 | 99.7 | 23.6 | 5.58 | 4.42 | 63% | 1.8% | 55% |
| round_z_nohuman/all | 571,612 | 13.6 | 0.237 | 12.4 | 171 | 37.4 | 8.47 | 4.66 | 63% | 3.2% | 78% |
| round_z_nohuman/claude | 259,736 | 19.9 | 0.118 | 10.0 | 216 | 36.6 | 10.1 | 4.94 | 71% | 4.1% | 89% |
| round_z_nohuman/codex | 311,876 | 8.34 | 0.588 | 14.9 | 120 | 21.7 | 7.15 | 3.93 | 55% | 2.3% | 56% |
| call_wall_exec_only/all | 642,695 | 9.55 | 0.188 | 5.50 | 118 | 49.7 | 5.03 | 6.44 | 71% | 1.7% | 81% |
| call_wall_shell/all | 469,947 | 11.6 | 0.332 | 7.45 | 121 | 46.9 | 6.08 | 5.89 | 65% | 2.1% | 81% |
| call_wall_all_logged/all | 743,050 | 15.6 | 0.218 | 10.1 | 152 | 50.6 | 7.65 | 5.06 | 66% | 2.8% | 83% |
| call_internal_nohuman/all | 345,523 | 5.07 | 0.078 | 6.41 | 110 | 4.58 | 5.07 | 4.52 | 70% | 1.9% | 51% |
| call_internal_nohuman/codex | 343,549 | 5.06 | 0.074 | 5.57 | 112 | 4.61 | 5.06 | 4.54 | 70% | 1.9% | 52% |
| call_internal_nohuman/claude | 1,974 | 6.90 | 5.88 | 14.2 | 35.3 | 1.08 | 6.90 | 1.08 | 23% | 0.1% | 0% |
| call_best_nohuman/all | 740,637 | 10.6 | 0.122 | 10.0 | 126 | 42.0 | 6.75 | 5.18 | 69% | 2.5% | 77% |
| round_gap_next_nohuman/all | 561,940 | 42.9 | 1.16 | 30.1 | 241 | 88.6 | 14.5 | 3.53 | 48% | 5.2% | 87% |

### Fits

| series (capped 600 s) | atom <10 ms | LN MLE mu / sigma (all) | KS | mean-preserving LN: mean, CV, KS | LN mu / sigma (positive part) | KS | mix comp 1: weight: median, sigma | mix comp 2 | KS mix | KS Exp(5 s) | KS Exp(mean-matched) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| call_wall_nohuman/all | 5.3% | -1.01 / 2.34 | 0.089 | 7.13 s, 20.6, 0.077 | -0.81 / 2.23 | 0.099 | 0.43: 0.0782 s, 0.88 | 0.57: 1.7 s, 2.01 | 0.037 | 0.514 | 0.573 |
| call_wall_nohuman/claude | 6.1% | -1.41 / 2.48 | 0.140 | 9.39 s, 40.8, 0.127 | -1.20 / 2.42 | 0.148 | 0.59: 0.0607 s, 0.87 | 0.41: 2.89 s, 2.09 | 0.018 | 0.598 | 0.635 |
| call_wall_nohuman/codex | 4.8% | -0.74 / 2.19 | 0.064 | 5.59 s, 12.6, 0.055 | -0.54 / 2.06 | 0.078 | 0.25: 0.0925 s, 0.59 | 0.75: 1.07 s, 2.00 | 0.070 | 0.511 | 0.532 |
| round_z_nohuman/all | 5.8% | -0.89 / 2.46 | 0.090 | 8.47 s, 22.9, 0.075 | -0.66 / 2.35 | 0.100 | 0.42: 0.0688 s, 0.85 | 0.58: 2.26 s, 1.99 | 0.032 | 0.480 | 0.558 |
| round_z_nohuman/claude | 5.6% | -1.34 / 2.49 | 0.144 | 10.1 s, 42.6, 0.125 | -1.15 / 2.43 | 0.153 | 0.59: 0.0646 s, 0.85 | 0.41: 3.16 s, 2.10 | 0.020 | 0.596 | 0.636 |
| round_z_nohuman/codex | 6.0% | -0.52 / 2.38 | 0.065 | 7.15 s, 11.3, 0.078 | -0.26 / 2.21 | 0.067 | 0.29: 0.0774 s, 0.84 | 0.71: 1.97 s, 1.90 | 0.066 | 0.444 | 0.505 |
| call_wall_exec_only/all | 5.3% | -1.27 / 2.12 | 0.080 | 5.03 s, 17.3, 0.081 | -1.08 / 2.03 | 0.092 | 0.45: 0.0806 s, 0.89 | 0.55: 1.1 s, 1.95 | 0.040 | 0.570 | 0.571 |
| call_wall_shell/all | 2.6% | -0.77 / 1.97 | 0.082 | 6.08 s, 12.9, 0.085 | -0.67 / 1.89 | 0.093 | 0.37: 0.109 s, 0.63 | 0.63: 1.25 s, 1.80 | 0.061 | 0.530 | 0.565 |
| call_internal_nohuman/all | 40.8% | -1.96 / 2.75 | 0.241 | 5.07 s, 50.6, 0.205 | -0.14 / 2.15 | 0.142 | 0.07: 0.0508 s, 0.20 | 0.93: 1.09 s, 2.07 | 0.148 | 0.622 | 0.624 |

### Percentiles (seconds)

| series | p1 | p5 | p10 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| round_z_nohuman/all | 0 | 0.008 | 0.021 | 0.062 | 0.237 | 2.61 | 12.4 | 30.0 | 171 |
| call_wall_nohuman/all | 0 | 0.009 | 0.023 | 0.066 | 0.216 | 1.57 | 10.0 | 30.0 | 131 |
| call_wall_shell/all | 0 | 0.039 | 0.056 | 0.104 | 0.332 | 1.24 | 7.45 | 15.3 | 121 |
| call_wall_exec_only/all | 0 | 0.009 | 0.023 | 0.063 | 0.188 | 1.17 | 5.50 | 11.3 | 118 |
| call_internal_nohuman/all | 0 | 0 | 0 | 0 | 0.078 | 1.00 | 6.41 | 30.0 | 110 |
| round_z_nohuman/claude | 0.003 | 0.009 | 0.018 | 0.044 | 0.118 | 1.60 | 10.0 | 41.9 | 216 |
| round_z_nohuman/codex | 0 | 0.007 | 0.028 | 0.083 | 0.588 | 5.00 | 14.9 | 30.0 | 120 |
| Exp(5 s) (current simulator) | 0.0503 | 0.256 | 0.527 | 1.44 | 3.47 | 6.93 | 11.5 | 15.0 | 23.0 |

### By tool class (wall clock)

| series | n | mean (s) | median | p90 | p99 | CV | mean cap600 | CV cap600 | <1 s | >60 s | share of time >60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| class_shell/all | 469,947 | 11.6 | 0.332 | 7.45 | 121 | 46.9 | 6.08 | 5.89 | 65% | 2.1% | 81% |
| class_file/all | 146,304 | 3.29 | 0.044 | 0.982 | 26.4 | 53.7 | 1.62 | 11.7 | 90% | 0.5% | 81% |
| class_web/all | 5,345 | 32.6 | 7.70 | 48.5 | 248 | 12.9 | 23.2 | 2.27 | 5% | 8.7% | 70% |
| class_poll/all | 91,639 | 20.1 | 5.01 | 30.6 | 300 | 4.44 | 19.6 | 2.37 | 31% | 8.0% | 59% |
| class_deleg/all | 6,303 | 57.2 | 0.15 | 120 | 600 | 14.7 | 39.7 | 2.39 | 57% | 19.2% | 92% |
| class_book/all | 20,652 | 2.15 | 0.037 | 0.339 | 11.6 | 93.2 | 0.721 | 11.6 | 93% | 0.2% | 78% |
| class_other/all | 447 | 6.91 | 0.098 | 3.00 | 91.3 | 8.72 | 5.73 | 7.64 | 83% | 2.0% | 83% |
| class_human/all | 2,413 | 1,350 | 79.3 | 875 | 30,116 | 8.38 | 167 | 1.19 | 8% | 57.1% | 99% |

### By tool (wall clock, 14 most frequent)

| provider:tool | n | mean | median | p90 | p99 | CV |
|---|---|---|---|---|---|---|
| codex:exec_command | 251,607 | 2.58 | 0.265 | 1.60 | 30.2 | 50.8 |
| claude:Bash | 158,471 | 28.3 | 0.329 | 20.4 | 300 | 32.0 |
| codex:write_stdin | 75,952 | 20.4 | 5.01 | 44.7 | 300 | 2.23 |
| claude:Read | 63,703 | 0.896 | 0.027 | 0.245 | 3.01 | 57.5 |
| codex:exec | 46,753 | 6.01 | 1.46 | 10.1 | 10.1 | 45.5 |
| claude:Edit | 36,533 | 6.15 | 0.075 | 2.00 | 62.2 | 38.3 |
| codex:apply_patch | 32,330 | 3.06 | 0.045 | 1.22 | 10.3 | 75.8 |
| codex:wait | 11,404 | 15.2 | 11.9 | 18.4 | 47.5 | 13.9 |
| claude:TaskUpdate | 8,824 | 0.898 | 0.05 | 0.327 | 13.5 | 24.3 |
| claude:Write | 8,602 | 10.8 | 0.068 | 2.10 | 83.9 | 25.2 |
| codex:shell_command | 7,623 | 2.52 | 0.051 | 0.867 | 19.2 | 18.7 |
| codex:shell | 5,416 | 0.000175 | 0 | 0.001 | 0.001 | 2.35 |
| claude:TaskCreate | 4,877 | 0.892 | 0.045 | 2.66 | 15.5 | 3.31 |
| claude:WebFetch | 3,636 | 30.2 | 6.26 | 22.6 | 206 | 16.9 |

### Wall minus runner-reported duration, rows where both are logged (seconds)

| provider | n | mean | median | p90 | p99 |
|---|---|---|---|---|---|
| claude | 1,974 | 30.2 | 0.005 | 2.30 | 91.7 |
| codex | 343,549 | 1.21 | 0.154 | 0.301 | 10.1 |

### Tokens and turns

| group | quantity | n | mean | mean (winsorised p99.9) | median | p90 | p99 | CV |
|---|---|---|---|---|---|---|---|---|
| all | first call prompt of a session (tokens) | 8,058 | 23,308 | 23,273 | 17,718 | 36,044 | 169,133 | 1.07 |
| all | prompt at every call (tokens) | 665,453 | 171,576 | 171,566 | 132,092 | 338,662 | 856,464 | 0.929 |
| all | output tokens per call | 665,453 | 589 | 583 | 249 | 1,332 | 5,542 | 1.99 |
| all | tokens appended between calls (delta_ctx >= 0) | 565,771 | 1,268 | 1,251 | 210 | 3,243 | 15,323 | 2.65 |
| all | model calls per agentic episode | 47,887 | 13.0 | 12.7 | 5.00 | 28.0 | 116 | 2.53 |
| all | model calls per whole session | 8,058 | 82.6 | 78.6 | 16.0 | 145 | 1,130 | 4.95 |
| claude | first call prompt of a session (tokens) | 5,319 | 25,718 | 25,715 | 18,822 | 38,603 | 168,922 | 0.985 |
| claude | prompt at every call (tokens) | 305,445 | 226,228 | 226,224 | 149,779 | 543,374 | 925,151 | 0.942 |
| claude | output tokens per call | 305,445 | 840 | 834 | 354 | 2,064 | 7,163 | 1.81 |
| claude | tokens appended between calls (delta_ctx >= 0) | 258,379 | 1,124 | 1,106 | 274 | 2,628 | 13,638 | 2.89 |
| claude | model calls per agentic episode | 31,590 | 9.28 | 9.10 | 3.00 | 20.0 | 91.0 | 2.32 |
| claude | model calls per whole session | 5,319 | 57.4 | 55.5 | 14.0 | 107 | 885 | 3.93 |
| codex | first call prompt of a session (tokens) | 2,739 | 18,628 | 18,523 | 14,642 | 26,391 | 199,042 | 1.26 |
| codex | prompt at every call (tokens) | 360,008 | 125,207 | 125,197 | 123,895 | 208,960 | 240,111 | 0.491 |
| codex | output tokens per call | 360,008 | 375 | 371 | 188 | 831 | 3,068 | 1.87 |
| codex | tokens appended between calls (delta_ctx >= 0) | 307,392 | 1,389 | 1,373 | 158 | 3,943 | 15,936 | 2.48 |
| codex | model calls per agentic episode | 16,297 | 20.1 | 19.9 | 9.00 | 41.0 | 183 | 2.32 |
| codex | model calls per whole session | 2,739 | 131 | 124 | 24.0 | 241 | 1,664 | 4.74 |

Human response time between agent runs (context only): {"n": 70197, "mean": 2712.39, "median": 129.47, "p90": 1107.53, "p99": 45713.22}

