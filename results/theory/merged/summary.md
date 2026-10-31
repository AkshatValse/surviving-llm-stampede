# Merged theory: generated summary

## Selection scores (approach A vs approach B, the three measured cells)

| cell | curve RMS rel. err. at measured n < n_b: A mean field / A smoothed / B fluid / B annealed | mu_max err. A MF / A SM / B fluid / B annealed | 0.5-hit crossing err. (sessions) A / B | E0b log-likelihood A / B (F2) / B with A's criterion | trapped-state mean abs. rel. err. A / B |
|---|---|---|---|---|---|
| a100_300k (4 pts) | 0.093 / 0.174 / 0.045 / 0.117 | +6.6% / +1.1% / +6.2% / +0.2% | -0.1 / -0.7 | -1.17 / -0.61 / -1.08 | 0.044 / 0.020 |
| a100_native (4 pts) | 0.027 / 0.032 / 0.026 / 0.037 | +6.1% / +3.3% / +6.0% / +3.3% | +1.1 / +0.3 | -0.95 / -0.44 / -1.07 | 0.035 / 0.029 |
| vllm_300k (5 pts) | 0.885 / 1.107 / 0.813 / 1.056 | +11.8% / +5.6% / +13.5% / +7.2% | +2.8 / +2.7 | -1.98 / -1.06 / -2.11 | 0.018 / 0.020 |
| total | | | | -4.11 / -2.10 / -4.26 | |

## Blind predictions: cells

| cell | lambda_miss (turns) | n_b (closed form) | peak n fluid / F1 | mu_max fluid / F1 | hit at peak | 0.5-hit n | window mu_max/lambda_ref fluid / F1 | edge F2 (x lambda_ref) | edge, A's criterion | P(unstable) F2 at the E0b grid | registration consequence (hi, points, cap) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| h200_300k | 0.1933 | 41.3 | 32.8 / 32.5 | 0.378 / 0.371 | 0.67 | 37.3 | 1.95 / 1.92 | 1.39 | 1.57 | 1.25: 0.19, 1.5: 0.75, 1.75: 0.98, 2.0: 1.00, 2.5: 1.00, 3.0: 1.00 | 1.25, [1.10, 1.15], 32 |
| h200_300k_decode2 | 0.1933 | 41.5 | 32.4 / 32.0 | 0.357 / 0.352 | 0.68 | 37.0 | 1.84 / 1.82 | 1.34 | 1.52 | 1.25: 0.28, 1.5: 0.85, 1.75: 0.99, 2.0: 1.00, 2.5: 1.00, 3.0: 1.00 | 1.25, [1.10, 1.15], 28 |
| h200_300k_e0a2 | 0.1933 | 41.7 | 31.9 / 32.0 | 0.322 / 0.320 | 0.68 | 36.4 | 1.66 / 1.65 | 1.24 | 1.42 | 1.25: 0.52, 1.5: 0.95, 1.75: 1.00, 2.0: 1.00, 2.5: 1.00, 3.0: 1.00 | n/a, n/a, 28 |
| llama31_8b_300k | 0.0619 | 32.0 | 24.3 / 23.0 | 0.222 / 0.208 | 0.91 | 30.9 | 3.59 / 3.37 | 2.46 | 2.73 | 1.25: 0.00, 1.5: 0.00, 1.75: 0.02, 2.0: 0.09, 2.5: 0.55, 3.0: 0.93 | 2.00, [1.35, 1.65], 24 |
| a100_pool150k | 0.0688 | 18.3 | 14.0 / 14.0 | 0.141 / 0.134 | 0.80 | 16.9 | 1.97 / 1.87 | 1.09 | 1.47 | 1.1: 0.51, 1.25: 0.76, 1.5: 0.96, 1.75: 1.00, 2.0: 1.00, 2.5: 1.00 | n/a, n/a, 12 |
| a100_pool600k | 0.0718 | 61.2 | 47.0 / 45.0 | 0.409 / 0.391 | 0.92 | 60.0 | 5.72 / 5.47 | 4.53 | 4.82 | 1.5: 0.00, 2.0: 0.00, 2.5: 0.00, 3.0: 0.00, 3.5: 0.01, 4.0: 0.11, 4.5: 0.47, 5.0: 0.85, 5.5: 0.98, 6.0: 1.00 | 4.50, [2.15, 3.35], 40 |

Closed-curve points (sessions/s; annealed F1 in brackets; Stage C synchronized-start value for n >= n_b):

- h200_300k: n=16: 0.212 (0.212), hit 0.93; n=20: 0.264 (0.264), hit 0.93; n=24: 0.314 (0.312), hit 0.89; n=28: 0.354 (0.351), hit 0.80; n=32: 0.377 (0.371), hit 0.70; n=40: 0.257 (0.278), hit 0.27; n=48: 0.197 (0.201), hit 0.00, sync 0.197; n=96: 0.197 (0.197), hit 0.00, sync 0.195; n=300: 0.197 (0.197), hit 0.00, sync 0.221
- h200_300k_decode2: n=16: 0.205 (0.205), hit 0.93; n=20: 0.255 (0.255), hit 0.93; n=24: 0.302 (0.300), hit 0.90; n=28: 0.339 (0.336), hit 0.80; n=32: 0.357 (0.352), hit 0.69; n=40: 0.252 (0.270), hit 0.26; n=48: 0.199 (0.202), hit 0.00, sync 0.199; n=96: 0.199 (0.199), hit 0.00, sync 0.197; n=300: 0.199 (0.199), hit 0.00, sync 0.223
- h200_300k_e0a2: n=16: 0.192 (0.192), hit 0.93; n=20: 0.238 (0.237), hit 0.93; n=24: 0.280 (0.278), hit 0.90; n=28: 0.311 (0.308), hit 0.81; n=32: 0.322 (0.320), hit 0.68; n=40: 0.245 (0.258), hit 0.24; n=48: 0.202 (0.205), hit 0.00, sync 0.202; n=96: 0.202 (0.202), hit 0.00, sync 0.200; n=300: 0.202 (0.202), hit 0.00, sync 0.226
- llama31_8b_300k: n=16: 0.166 (0.166), hit 0.93; n=20: 0.199 (0.197), hit 0.93; n=24: 0.222 (0.208), hit 0.92; n=28: 0.189 (0.174), hit 0.80; n=32: 0.063 (0.116), hit 0.02; n=40: 0.062 (0.065), hit 0.00, sync 0.061; n=48: 0.062 (0.062), hit 0.00, sync 0.062; n=96: 0.062 (0.062), hit 0.00, sync 0.070; n=300: 0.062 (0.062), hit 0.00, sync 0.098
- a100_pool150k: n=8: 0.091 (0.091), hit 0.93; n=10: 0.113 (0.112), hit 0.93; n=12: 0.133 (0.128), hit 0.91; n=14: 0.141 (0.134), hit 0.80; n=16: 0.129 (0.124), hit 0.63; n=20: 0.069 (0.085), hit 0.00, sync 0.069; n=24: 0.069 (0.071), hit 0.00, sync 0.069; n=48: 0.069 (0.069), hit 0.00, sync 0.068; n=300: 0.069 (0.069), hit 0.00, sync 0.105
- a100_pool600k: n=32: 0.322 (0.322), hit 0.93; n=40: 0.379 (0.376), hit 0.93; n=48: 0.408 (0.383), hit 0.92; n=56: 0.285 (0.267), hit 0.81; n=64: 0.073 (0.121), hit 0.00, sync 0.074; n=80: 0.073 (0.073), hit 0.00, sync 0.076; n=96: 0.073 (0.073), hit 0.00, sync 0.079; n=192: 0.073 (0.073), hit 0.00, sync 0.096; n=300: 0.073 (0.073), hit 0.00, sync 0.110

## Blind predictions: registered tests

B1 (300k, 1.65 x, burst in 60 s at 1200 s; STUCK if the [5700, 8700) hit < 0.2): deterministic critical burst 53.4 (stationary-composition 21.3); n1 = 10.4, n_u = 31.8; background escape before 6344 s: 0.032.

| burst | X0 (session equiv.) | committor q | P(STUCK) per seed | deterministic |
|---|---|---|---|---|
| 10 | 14.5 | 0.002 | 0.033 | not trapped |
| 25 | 20.7 | 0.011 | 0.042 | not trapped |
| 40 | 26.7 | 0.111 | 0.139 | not trapped |
| 50 | 30.5 | 0.533 | 0.547 | not trapped |
| 60 | 32.7 | 1.000 | 1.000 | trapped |
| 75 | 32.7 | 1.000 | 1.000 | trapped |
| 100 | 32.7 | 1.000 | 1.000 | trapped |
| 150 | 32.7 | 1.000 | 1.000 | trapped |
| 200 | 32.7 | 1.000 | 1.000 | trapped |

P(B1 PASS: 100 STUCK in >= 2/3 and 25 not STUCK in >= 2/3, treating not-STUCK as GOOD) = 0.995.

R1:

| rate | n in system at t_on | cycle at t_on (s) | footprint inflation | phase-1 rate fluid / F1 (sessions/s) | mu(cap) fresh | release, two-phase fluid / F1 (s) | release, B stationary / B single-queue adjusted / phase-1 collapsed (s) | phase-1 rate needed for release by 7200 s | P(relapse) after release |
|---|---|---|---|---|---|---|---|---|---|
| 1.35 x | 161 | 88 | 1.42 | 0.163 / 0.154 | 0.216 | 3830 / 3920 | 3441 / 4432 / 7510 | 0.052 (0.32 of fluid) | 0.002 |
| 1.65 x | 176 | 93 | 1.40 | 0.167 / 0.158 | 0.216 | 4360 / 4480 | 3890 / 5568 / 9240 | 0.070 (0.42 of fluid) | 0.025 |

R4:

| rate | n in system at t_on | cycle at t_on (s) | footprint inflation | phase-1 rate fluid / F1 (sessions/s) | mu(cap) fresh | release, two-phase fluid / F1 (s) | release, B stationary / B single-queue adjusted / phase-1 collapsed (s) | phase-1 rate needed for release by 7200 s | P(relapse) after release |
|---|---|---|---|---|---|---|---|---|---|
| 4.0 x | 327 | 150 | 1.34 | 0.282 / 0.257 | 0.488 | 5040 / 5250 | 4072 / never / 14640 | 0.144 (0.51 of fluid) | 0.000 |

