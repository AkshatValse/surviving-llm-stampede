# Round-6 Predict: tables (report 20261024-034707, code commit ab02e705956dba4d07d57e9786af7ef613394c1c, dirty=False)

## B1. All-miss capacity (cache disabled, closed population, FCFS, window [900, 2700) s)

| mode | n | n_seeds | mu_mean | mu_sd | mu_turns_mean | mu_turns_sd | token_rate_mean | token_rate_sd | busy_mean | busy_sd |
|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 32 | 3 | 0.069444 | 0.01148 | 0.072187 | 0.0018897 | 11220 | 93.988 | 1 | 0 |
| mixed | 64 | 1 | 0.074444 | n/a | 0.071886 | n/a | 11280 | n/a | 1 | n/a |
| separate_prefill_priority | 32 | 3 | 0.068889 | 0.011153 | 0.071359 | 0.0012945 | 11147 | 101.13 | 0.99999 | 1.5034e-05 |
| separate_prefill_priority | 64 | 1 | 0.073333 | n/a | 0.071095 | n/a | 11153 | n/a | 1 | n/a |

Per seed:

| mode | n | seed | mu | mu_turns | token_rate | busy | hit_rate |
|---|---|---|---|---|---|---|---|
| mixed | 32 | 0 | 0.08 | 0.072751 | 11120 | 1 | 0 |
| mixed | 32 | 1 | 0.057222 | 0.070079 | 11306 | 1 | 0 |
| mixed | 32 | 2 | 0.071111 | 0.07373 | 11233 | 1 | 0 |
| mixed | 64 | 0 | 0.074444 | 0.071886 | 11280 | 1 | 0 |
| separate_prefill_priority | 32 | 0 | 0.079444 | 0.071585 | 11042 | 0.99997 | 0 |
| separate_prefill_priority | 32 | 1 | 0.057222 | 0.069966 | 11243 | 1 | 0 |
| separate_prefill_priority | 32 | 2 | 0.07 | 0.072526 | 11156 | 1 | 0 |
| separate_prefill_priority | 64 | 0 | 0.073333 | 0.071095 | 11153 | 1 | 0 |

B3 reference values used below (POP = 32, seeds 0-2, 3-seed means):

| mode | lambda_miss_turns | lambda_miss_sessions | token_rate_tok_per_s |
|---|---|---|---|
| mixed | 0.072187 | 0.069444 | 11220 |
| separate_prefill_priority | 0.071359 | 0.068889 | 11147 |

## B2. From-empty open-loop stability (cache on, FCFS, horizon 3000 s, seeds 0-2)

| mode | lam | stable | final_backlog_mean | final_backlog_max | trend_rise_mean | tail_hit_mean | tail_busy_mean |
|---|---|---|---|---|---|---|---|
| mixed | 0.07 | 3/3 | 0 | 0 | 0.002916 | 0.9362 | 0.7635 |
| mixed | 0.08 | 3/3 | 0 | 0 | 0.001791 | 0.9351 | 0.8 |
| mixed | 0.09 | 3/3 | 0 | 0 | 0.0009732 | 0.9331 | 0.8286 |
| mixed | 0.1 | 3/3 | 0 | 0 | 0.002112 | 0.9339 | 0.8545 |
| mixed | 0.11 | 3/3 | 0 | 0 | 0.0006819 | 0.9308 | 0.8585 |
| mixed | 0.12 | 3/3 | 0 | 0 | -0.003119 | 0.9298 | 0.8858 |
| mixed | 0.13 | 3/3 | 0 | 0 | -0.01986 | 0.9296 | 0.9078 |
| mixed | 0.14 | 3/3 | 2.667 | 8 | 0.8676 | 0.9213 | 0.9243 |
| mixed | 0.15 | 2/3 | 17.33 | 44 | 12.63 | 0.5987 | 0.9697 |
| mixed | 0.16 | 2/3 | 25.33 | 76 | 19.51 | 0.5839 | 0.9745 |
| mixed | 0.18 | 2/3 | 38.33 | 115 | 25.09 | 0.617 | 0.983 |
| mixed | 0.2 | 0/3 | 191.3 | 234 | 138.7 | 0 | 1 |
| mixed | 0.22 | 0/3 | 256 | 275 | 162 | 0 | 1 |
| separate_prefill_priority | 0.07 | 3/3 | 0 | 0 | 0.00331 | 0.9362 | 0.7654 |
| separate_prefill_priority | 0.08 | 3/3 | 0 | 0 | 0.002109 | 0.9351 | 0.7965 |
| separate_prefill_priority | 0.09 | 3/3 | 0 | 0 | -0.0005492 | 0.9331 | 0.8304 |
| separate_prefill_priority | 0.1 | 3/3 | 0 | 0 | 0.002818 | 0.9339 | 0.855 |
| separate_prefill_priority | 0.11 | 3/3 | 0 | 0 | -0.001334 | 0.9309 | 0.861 |
| separate_prefill_priority | 0.12 | 3/3 | 0 | 0 | -0.001931 | 0.9298 | 0.8891 |
| separate_prefill_priority | 0.13 | 3/3 | 0 | 0 | -0.02046 | 0.9295 | 0.9082 |
| separate_prefill_priority | 0.14 | 3/3 | 2 | 6 | 1.008 | 0.9219 | 0.9251 |
| separate_prefill_priority | 0.15 | 3/3 | 2 | 6 | 2.286 | 0.9115 | 0.9388 |
| separate_prefill_priority | 0.16 | 1/3 | 37 | 81 | 27.29 | 0.5732 | 0.9742 |
| separate_prefill_priority | 0.18 | 2/3 | 43 | 129 | 26.82 | 0.6111 | 0.9848 |
| separate_prefill_priority | 0.2 | 0/3 | 215.7 | 253 | 141.9 | 0 | 1 |
| separate_prefill_priority | 0.22 | 0/3 | 267.7 | 285 | 162.2 | 0 | 1 |

| mode | edge (largest lambda with every smaller grid lambda all-stable), sessions/s | x B1 turns-based lambda_miss | largest all-stable grid lambda | x B1 turns-based (largest) |
|---|---|---|---|---|
| mixed | 0.14 | 1.939 | 0.14 | 1.939 |
| separate_prefill_priority | 0.15 | 2.102 | 0.15 | 2.102 |

Supplementary (labelled, not part of the prediction): stable fraction with 20 fresh seeds (100-119):

| mode | lam | stable | stable_frac | final_backlog_mean | trend_rise_mean |
|---|---|---|---|---|---|
| mixed | 0.07 | 20/20 | 1 | 0 | 0.001371 |
| mixed | 0.08 | 20/20 | 1 | 0 | 0.001384 |
| mixed | 0.09 | 20/20 | 1 | 0 | 0.0008565 |
| mixed | 0.1 | 20/20 | 1 | 0 | 0.001027 |
| mixed | 0.11 | 20/20 | 1 | 0 | 0.003298 |
| mixed | 0.12 | 20/20 | 1 | 0 | 0.001354 |
| mixed | 0.13 | 20/20 | 1 | 0 | 0.002563 |
| mixed | 0.14 | 20/20 | 1 | 0 | 0.003827 |
| mixed | 0.15 | 20/20 | 1 | 0 | -0.02345 |
| mixed | 0.16 | 19/20 | 0.95 | 3.1 | 2.902 |
| mixed | 0.18 | 15/20 | 0.75 | 18.65 | 14.67 |
| mixed | 0.2 | 6/20 | 0.3 | 84.15 | 66.79 |
| mixed | 0.22 | 4/20 | 0.2 | 144.4 | 107 |
| separate_prefill_priority | 0.07 | 20/20 | 1 | 0 | 0.001075 |
| separate_prefill_priority | 0.08 | 20/20 | 1 | 0 | 0.001129 |
| separate_prefill_priority | 0.09 | 20/20 | 1 | 0 | 0.0008176 |
| separate_prefill_priority | 0.1 | 20/20 | 1 | 0 | 0.0009392 |
| separate_prefill_priority | 0.11 | 20/20 | 1 | 0 | 0.003347 |
| separate_prefill_priority | 0.12 | 20/20 | 1 | 0 | 0.002031 |
| separate_prefill_priority | 0.13 | 20/20 | 1 | 0 | 0.002325 |
| separate_prefill_priority | 0.14 | 20/20 | 1 | 0 | 0.00256 |
| separate_prefill_priority | 0.15 | 20/20 | 1 | 0.2 | -0.04504 |
| separate_prefill_priority | 0.16 | 19/20 | 0.95 | 3.05 | 3.254 |
| separate_prefill_priority | 0.18 | 15/20 | 0.75 | 20.35 | 15.75 |
| separate_prefill_priority | 0.2 | 6/20 | 0.3 | 96.3 | 74.14 |
| separate_prefill_priority | 0.22 | 4/20 | 0.2 | 161.3 | 113.3 |

| mode | lambda_stable_frac_crosses_0.5 | lambda_stable_frac_crosses_0.95 | edge_all_stable_contiguous |
|---|---|---|---|
| mixed | 0.1911 | 0.16 | 0.15 |
| separate_prefill_priority | 0.1911 | 0.16 | 0.15 |

## B3. E2 paired arms (lambda grid, seeds 0-2; eval window = last 2500 s)

Per-lambda verdict (counts out of the seeds; PASS needs each of the first three counts >= `need`):

| mode | lam | n_seeds | need | burst_trapped | noburst_good | cap_recovered | burst_recovered | noburst_trapped | cap_trapped | PASS | PASS_all_seeds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0.09 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.1 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.11 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.12 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.13 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.14 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| mixed | 0.16 | 3 | 2 | 3 | 2 | 3 | 0 | 1 | 0 | True | False |
| separate_prefill_priority | 0.09 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.1 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.11 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.12 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.13 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.14 | 3 | 2 | 3 | 3 | 3 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.16 | 3 | 2 | 3 | 2 | 3 | 0 | 1 | 0 | True | False |

Per run:

| mode | lam | seed | arm | label | token_ratio | slope | slope_threshold | rise_over_window | hit | backlog | token_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0.09 | 0 | burst | TRAPPED | 1.019 | 0.01196 | 0.008907 | 29.91 | 0 | 170.8 | 1.143e+04 |
| mixed | 0.09 | 1 | burst | TRAPPED | 1.003 | 0.01628 | 0.008907 | 40.7 | 0 | 173.2 | 1.126e+04 |
| mixed | 0.09 | 2 | burst | TRAPPED | 1.011 | 0.02006 | 0.008907 | 50.15 | 0 | 196.9 | 1.134e+04 |
| mixed | 0.09 | 0 | burst_cap | RECOVERED | 0.08283 | -6.664e-07 | 0.008907 | -0.001666 | 0.9335 | 0.01063 | 929.3 |
| mixed | 0.09 | 1 | burst_cap | RECOVERED | 0.07796 | -3.121e-07 | 0.008907 | -0.0007802 | 0.9359 | 0.009984 | 874.7 |
| mixed | 0.09 | 2 | burst_cap | RECOVERED | 0.08312 | -9.778e-07 | 0.008907 | -0.002444 | 0.9338 | 0.01098 | 932.6 |
| mixed | 0.09 | 0 | no_burst | RECOVERED | 0.08283 | -6.664e-07 | 0.008907 | -0.001666 | 0.9335 | 0.01063 | 929.3 |
| mixed | 0.09 | 1 | no_burst | RECOVERED | 0.07796 | -8.624e-07 | 0.008907 | -0.002156 | 0.9359 | 0.01026 | 874.7 |
| mixed | 0.09 | 2 | no_burst | RECOVERED | 0.08312 | -9.778e-07 | 0.008907 | -0.002444 | 0.9338 | 0.01098 | 932.6 |
| mixed | 0.1 | 0 | burst | TRAPPED | 1.027 | 0.01753 | 0.01391 | 43.81 | 0 | 216.6 | 1.153e+04 |
| mixed | 0.1 | 1 | burst | TRAPPED | 1.015 | 0.02132 | 0.01391 | 53.29 | 0 | 211.6 | 1.139e+04 |
| mixed | 0.1 | 2 | burst | TRAPPED | 1.024 | 0.02185 | 0.01391 | 54.63 | 0 | 234.3 | 1.148e+04 |
| mixed | 0.1 | 0 | burst_cap | RECOVERED | 0.08814 | 1.656e-07 | 0.01391 | 0.0004139 | 0.9314 | 0.01191 | 988.9 |
| mixed | 0.1 | 1 | burst_cap | RECOVERED | 0.08584 | -2.849e-05 | 0.01391 | -0.07122 | 0.935 | 0.05508 | 963.1 |
| mixed | 0.1 | 2 | burst_cap | RECOVERED | 0.08657 | -5.372e-07 | 0.01391 | -0.001343 | 0.929 | 0.01173 | 971.3 |
| mixed | 0.1 | 0 | no_burst | RECOVERED | 0.08814 | 1.122e-06 | 0.01391 | 0.002804 | 0.9314 | 0.01185 | 988.9 |
| mixed | 0.1 | 1 | no_burst | RECOVERED | 0.08584 | -2.801e-06 | 0.01391 | -0.007002 | 0.935 | 0.01191 | 963.1 |
| mixed | 0.1 | 2 | no_burst | RECOVERED | 0.08657 | -1.356e-07 | 0.01391 | -0.000339 | 0.929 | 0.01143 | 971.3 |
| mixed | 0.11 | 0 | burst | TRAPPED | 1.038 | 0.02782 | 0.01891 | 69.56 | 0 | 252.6 | 1.164e+04 |
| mixed | 0.11 | 1 | burst | TRAPPED | 1.025 | 0.0299 | 0.01891 | 74.76 | 0 | 253.1 | 1.15e+04 |
| mixed | 0.11 | 2 | burst | TRAPPED | 1.029 | 0.0384 | 0.01891 | 96 | 0 | 269.7 | 1.155e+04 |
| mixed | 0.11 | 0 | burst_cap | RECOVERED | 0.09956 | 2.877e-06 | 0.01891 | 0.007192 | 0.9341 | 0.01494 | 1117 |
| mixed | 0.11 | 1 | burst_cap | RECOVERED | 0.09519 | -4.162e-06 | 0.01891 | -0.0104 | 0.9348 | 0.01525 | 1068 |
| mixed | 0.11 | 2 | burst_cap | RECOVERED | 0.09949 | 1.836e-06 | 0.01891 | 0.004589 | 0.9316 | 0.01431 | 1116 |
| mixed | 0.11 | 0 | no_burst | RECOVERED | 0.09956 | 3.184e-06 | 0.01891 | 0.00796 | 0.9341 | 0.0145 | 1117 |
| mixed | 0.11 | 1 | no_burst | RECOVERED | 0.09519 | -2.747e-06 | 0.01891 | -0.006868 | 0.9348 | 0.01361 | 1068 |
| mixed | 0.11 | 2 | no_burst | RECOVERED | 0.09949 | 1.55e-06 | 0.01891 | 0.003874 | 0.9316 | 0.01446 | 1116 |
| mixed | 0.12 | 0 | burst | TRAPPED | 1.043 | 0.03437 | 0.02391 | 85.92 | 0 | 297.3 | 1.17e+04 |
| mixed | 0.12 | 1 | burst | TRAPPED | 1.034 | 0.03882 | 0.02391 | 97.04 | 0 | 291.3 | 1.16e+04 |
| mixed | 0.12 | 2 | burst | TRAPPED | 1.035 | 0.04903 | 0.02391 | 122.6 | 0 | 312.8 | 1.161e+04 |
| mixed | 0.12 | 0 | burst_cap | RECOVERED | 0.1034 | -3.293e-06 | 0.02391 | -0.008233 | 0.9318 | 0.01507 | 1160 |
| mixed | 0.12 | 1 | burst_cap | RECOVERED | 0.1062 | 1.39e-06 | 0.02391 | 0.003476 | 0.9347 | 0.01556 | 1192 |
| mixed | 0.12 | 2 | burst_cap | RECOVERED | 0.1135 | 1.427e-05 | 0.02391 | 0.03568 | 0.935 | 0.02479 | 1273 |
| mixed | 0.12 | 0 | no_burst | RECOVERED | 0.1034 | -3.063e-06 | 0.02391 | -0.007658 | 0.9318 | 0.01492 | 1160 |
| mixed | 0.12 | 1 | no_burst | RECOVERED | 0.1062 | 1.7e-06 | 0.02391 | 0.00425 | 0.9347 | 0.01594 | 1192 |
| mixed | 0.12 | 2 | no_burst | RECOVERED | 0.1135 | 3.459e-06 | 0.02391 | 0.008647 | 0.935 | 0.01846 | 1274 |
| mixed | 0.13 | 0 | burst | TRAPPED | 1.05 | 0.03703 | 0.02891 | 92.58 | 0 | 343.4 | 1.178e+04 |
| mixed | 0.13 | 1 | burst | TRAPPED | 1.044 | 0.04296 | 0.02891 | 107.4 | 0 | 330 | 1.171e+04 |
| mixed | 0.13 | 2 | burst | TRAPPED | 1.041 | 0.0579 | 0.02891 | 144.7 | 0 | 359.5 | 1.168e+04 |
| mixed | 0.13 | 0 | burst_cap | RECOVERED | 0.1132 | -6.045e-07 | 0.02891 | -0.001511 | 0.9329 | 0.0209 | 1270 |
| mixed | 0.13 | 1 | burst_cap | RECOVERED | 0.1163 | -6.547e-05 | 0.02891 | -0.1637 | 0.935 | 0.09464 | 1304 |
| mixed | 0.13 | 2 | burst_cap | RECOVERED | 0.1234 | 0.0001017 | 0.02891 | 0.2542 | 0.9353 | 0.3343 | 1385 |
| mixed | 0.13 | 0 | no_burst | RECOVERED | 0.1132 | -4.976e-07 | 0.02891 | -0.001244 | 0.9329 | 0.01776 | 1270 |
| mixed | 0.13 | 1 | no_burst | RECOVERED | 0.1162 | 1.896e-07 | 0.02891 | 0.0004739 | 0.935 | 0.01874 | 1304 |
| mixed | 0.13 | 2 | no_burst | RECOVERED | 0.1233 | 4.052e-06 | 0.02891 | 0.01013 | 0.9352 | 0.02199 | 1384 |
| mixed | 0.14 | 0 | burst | TRAPPED | 1.055 | 0.04122 | 0.03391 | 103 | 0 | 391.6 | 1.184e+04 |
| mixed | 0.14 | 1 | burst | TRAPPED | 1.052 | 0.04909 | 0.03391 | 122.7 | 0 | 378.9 | 1.18e+04 |
| mixed | 0.14 | 2 | burst | TRAPPED | 1.051 | 0.06042 | 0.03391 | 151 | 0 | 409.1 | 1.179e+04 |
| mixed | 0.14 | 0 | burst_cap | RECOVERED | 0.1226 | 1.878e-06 | 0.03391 | 0.004695 | 0.9341 | 0.01991 | 1376 |
| mixed | 0.14 | 1 | burst_cap | RECOVERED | 0.1247 | -9.07e-05 | 0.03391 | -0.2268 | 0.9361 | 0.2259 | 1400 |
| mixed | 0.14 | 2 | burst_cap | RECOVERED | 0.1365 | 0.0002373 | 0.03391 | 0.5933 | 0.9368 | 0.2866 | 1531 |
| mixed | 0.14 | 0 | no_burst | RECOVERED | 0.1227 | 1.924e-06 | 0.03391 | 0.004809 | 0.9342 | 0.01987 | 1376 |
| mixed | 0.14 | 1 | no_burst | RECOVERED | 0.1247 | -8.12e-07 | 0.03391 | -0.00203 | 0.9361 | 0.02046 | 1400 |
| mixed | 0.14 | 2 | no_burst | RECOVERED | 0.154 | 0.0001952 | 0.03391 | 0.4879 | 0.9306 | 0.1259 | 1727 |
| mixed | 0.16 | 0 | burst | TRAPPED | 1.065 | 0.06649 | 0.04391 | 166.2 | 0 | 490.7 | 1.195e+04 |
| mixed | 0.16 | 1 | burst | TRAPPED | 1.065 | 0.068 | 0.04391 | 170 | 0 | 476.1 | 1.194e+04 |
| mixed | 0.16 | 2 | burst | TRAPPED | 1.06 | 0.0753 | 0.04391 | 188.3 | 0 | 506.4 | 1.189e+04 |
| mixed | 0.16 | 0 | burst_cap | RECOVERED | 0.14 | -5.525e-05 | 0.04391 | -0.1381 | 0.9307 | 0.08244 | 1570 |
| mixed | 0.16 | 1 | burst_cap | RECOVERED | 0.148 | -0.001334 | 0.04391 | -3.335 | 0.932 | 0.9791 | 1661 |
| mixed | 0.16 | 2 | burst_cap | RECOVERED | 0.1482 | -0.000512 | 0.04391 | -1.28 | 0.9322 | 0.5477 | 1662 |
| mixed | 0.16 | 0 | no_burst | RECOVERED | 0.1398 | -4.298e-07 | 0.04391 | -0.001074 | 0.9306 | 0.0248 | 1568 |
| mixed | 0.16 | 1 | no_burst | RECOVERED | 0.1488 | 1.808e-05 | 0.04391 | 0.0452 | 0.9316 | 0.04197 | 1670 |
| mixed | 0.16 | 2 | no_burst | TRAPPED | 1.052 | 0.07647 | 0.04391 | 191.2 | 0 | 292.3 | 1.18e+04 |
| separate_prefill_priority | 0.09 | 0 | burst | TRAPPED | 1.013 | 0.01802 | 0.009321 | 45.05 | 0 | 184 | 1.129e+04 |
| separate_prefill_priority | 0.09 | 1 | burst | TRAPPED | 0.999 | 0.01766 | 0.009321 | 44.16 | 0 | 187.7 | 1.114e+04 |
| separate_prefill_priority | 0.09 | 2 | burst | TRAPPED | 1.007 | 0.02105 | 0.009321 | 52.62 | 0 | 204.3 | 1.123e+04 |
| separate_prefill_priority | 0.09 | 0 | burst_cap | RECOVERED | 0.08337 | -1.711e-06 | 0.009321 | -0.004277 | 0.9335 | 0.009992 | 929.3 |
| separate_prefill_priority | 0.09 | 1 | burst_cap | RECOVERED | 0.07847 | -1.197e-06 | 0.009321 | -0.002992 | 0.9359 | 0.01025 | 874.7 |
| separate_prefill_priority | 0.09 | 2 | burst_cap | RECOVERED | 0.08367 | -1.623e-06 | 0.009321 | -0.004058 | 0.9338 | 0.01141 | 932.6 |
| separate_prefill_priority | 0.09 | 0 | no_burst | RECOVERED | 0.08337 | -1.761e-06 | 0.009321 | -0.004404 | 0.9335 | 0.00998 | 929.3 |
| separate_prefill_priority | 0.09 | 1 | no_burst | RECOVERED | 0.07847 | -9.978e-07 | 0.009321 | -0.002494 | 0.9359 | 0.01015 | 874.7 |
| separate_prefill_priority | 0.09 | 2 | no_burst | RECOVERED | 0.08367 | -1.623e-06 | 0.009321 | -0.004058 | 0.9338 | 0.01141 | 932.6 |
| separate_prefill_priority | 0.1 | 0 | burst | TRAPPED | 1.022 | 0.01907 | 0.01432 | 47.69 | 0 | 232.8 | 1.139e+04 |
| separate_prefill_priority | 0.1 | 1 | burst | TRAPPED | 1.009 | 0.02303 | 0.01432 | 57.58 | 0 | 221.6 | 1.125e+04 |
| separate_prefill_priority | 0.1 | 2 | burst | TRAPPED | 1.02 | 0.02296 | 0.01432 | 57.4 | 0 | 246.3 | 1.137e+04 |
| separate_prefill_priority | 0.1 | 0 | burst_cap | RECOVERED | 0.0887 | 1.424e-07 | 0.01432 | 0.0003561 | 0.9314 | 0.01195 | 988.7 |
| separate_prefill_priority | 0.1 | 1 | burst_cap | RECOVERED | 0.0864 | -3.121e-05 | 0.01432 | -0.07802 | 0.935 | 0.06011 | 963.1 |
| separate_prefill_priority | 0.1 | 2 | burst_cap | RECOVERED | 0.08716 | -2.204e-07 | 0.01432 | -0.000551 | 0.929 | 0.0118 | 971.5 |
| separate_prefill_priority | 0.1 | 0 | no_burst | RECOVERED | 0.0887 | 3.578e-07 | 0.01432 | 0.0008944 | 0.9314 | 0.01184 | 988.7 |
| separate_prefill_priority | 0.1 | 1 | no_burst | RECOVERED | 0.0864 | -2.601e-06 | 0.01432 | -0.006502 | 0.935 | 0.01151 | 963.1 |
| separate_prefill_priority | 0.1 | 2 | no_burst | RECOVERED | 0.08716 | -9.132e-07 | 0.01432 | -0.002283 | 0.929 | 0.01139 | 971.5 |
| separate_prefill_priority | 0.11 | 0 | burst | TRAPPED | 1.032 | 0.02809 | 0.01932 | 70.23 | 0 | 270.3 | 1.151e+04 |
| separate_prefill_priority | 0.11 | 1 | burst | TRAPPED | 1.022 | 0.03066 | 0.01932 | 76.64 | 0 | 263.2 | 1.139e+04 |
| separate_prefill_priority | 0.11 | 2 | burst | TRAPPED | 1.025 | 0.03895 | 0.01932 | 97.38 | 0 | 285.6 | 1.143e+04 |
| separate_prefill_priority | 0.11 | 0 | burst_cap | RECOVERED | 0.1002 | 2.11e-06 | 0.01932 | 0.005274 | 0.9341 | 0.01378 | 1117 |
| separate_prefill_priority | 0.11 | 1 | burst_cap | RECOVERED | 0.0958 | -4.958e-06 | 0.01932 | -0.01239 | 0.9348 | 0.01603 | 1068 |
| separate_prefill_priority | 0.11 | 2 | burst_cap | RECOVERED | 0.1001 | 1.713e-06 | 0.01932 | 0.004282 | 0.9316 | 0.01401 | 1116 |
| separate_prefill_priority | 0.11 | 0 | no_burst | RECOVERED | 0.1002 | 2.424e-06 | 0.01932 | 0.006059 | 0.9341 | 0.01381 | 1117 |
| separate_prefill_priority | 0.11 | 1 | no_burst | RECOVERED | 0.0958 | -3.117e-06 | 0.01932 | -0.007793 | 0.9348 | 0.01323 | 1068 |
| separate_prefill_priority | 0.11 | 2 | no_burst | RECOVERED | 0.1001 | 1.761e-06 | 0.01932 | 0.004402 | 0.9316 | 0.01396 | 1116 |
| separate_prefill_priority | 0.12 | 0 | burst | TRAPPED | 1.038 | 0.03577 | 0.02432 | 89.44 | 0 | 310.9 | 1.157e+04 |
| separate_prefill_priority | 0.12 | 1 | burst | TRAPPED | 1.03 | 0.04134 | 0.02432 | 103.3 | 0 | 303.6 | 1.148e+04 |
| separate_prefill_priority | 0.12 | 2 | burst | TRAPPED | 1.031 | 0.04686 | 0.02432 | 117.1 | 0 | 324.9 | 1.149e+04 |
| separate_prefill_priority | 0.12 | 0 | burst_cap | RECOVERED | 0.1041 | -1.989e-06 | 0.02432 | -0.004973 | 0.9318 | 0.01511 | 1161 |
| separate_prefill_priority | 0.12 | 1 | burst_cap | RECOVERED | 0.1069 | 1.65e-06 | 0.02432 | 0.004124 | 0.9347 | 0.01575 | 1192 |
| separate_prefill_priority | 0.12 | 2 | burst_cap | RECOVERED | 0.1142 | 1.494e-05 | 0.02432 | 0.03736 | 0.935 | 0.02443 | 1273 |
| separate_prefill_priority | 0.12 | 0 | no_burst | RECOVERED | 0.1041 | -1.193e-06 | 0.02432 | -0.002982 | 0.9318 | 0.01495 | 1160 |
| separate_prefill_priority | 0.12 | 1 | no_burst | RECOVERED | 0.1069 | 1.057e-06 | 0.02432 | 0.002641 | 0.9347 | 0.01586 | 1192 |
| separate_prefill_priority | 0.12 | 2 | no_burst | RECOVERED | 0.1142 | 2.379e-06 | 0.02432 | 0.005949 | 0.935 | 0.01757 | 1273 |
| separate_prefill_priority | 0.13 | 0 | burst | TRAPPED | 1.045 | 0.0406 | 0.02932 | 101.5 | 0 | 360.4 | 1.164e+04 |
| separate_prefill_priority | 0.13 | 1 | burst | TRAPPED | 1.039 | 0.04452 | 0.02932 | 111.3 | 0 | 343.2 | 1.159e+04 |
| separate_prefill_priority | 0.13 | 2 | burst | TRAPPED | 1.037 | 0.05931 | 0.02932 | 148.3 | 0 | 369.1 | 1.156e+04 |
| separate_prefill_priority | 0.13 | 0 | burst_cap | RECOVERED | 0.114 | -5.892e-07 | 0.02932 | -0.001473 | 0.933 | 0.02152 | 1270 |
| separate_prefill_priority | 0.13 | 1 | burst_cap | RECOVERED | 0.117 | -7.249e-05 | 0.02932 | -0.1812 | 0.935 | 0.1043 | 1304 |
| separate_prefill_priority | 0.13 | 2 | burst_cap | RECOVERED | 0.1242 | 0.0001059 | 0.02932 | 0.2648 | 0.9353 | 0.3607 | 1385 |
| separate_prefill_priority | 0.13 | 0 | no_burst | RECOVERED | 0.1139 | -1.369e-08 | 0.02932 | -3.422e-05 | 0.9329 | 0.01712 | 1270 |
| separate_prefill_priority | 0.13 | 1 | no_burst | RECOVERED | 0.117 | -1.508e-07 | 0.02932 | -0.000377 | 0.935 | 0.01904 | 1304 |
| separate_prefill_priority | 0.13 | 2 | no_burst | RECOVERED | 0.1242 | 2.784e-06 | 0.02932 | 0.006961 | 0.9352 | 0.0212 | 1384 |
| separate_prefill_priority | 0.14 | 0 | burst | TRAPPED | 1.049 | 0.0413 | 0.03432 | 103.2 | 0 | 404.3 | 1.169e+04 |
| separate_prefill_priority | 0.14 | 1 | burst | TRAPPED | 1.047 | 0.05092 | 0.03432 | 127.3 | 0 | 391.1 | 1.167e+04 |
| separate_prefill_priority | 0.14 | 2 | burst | TRAPPED | 1.046 | 0.06147 | 0.03432 | 153.7 | 0 | 418.6 | 1.166e+04 |
| separate_prefill_priority | 0.14 | 0 | burst_cap | RECOVERED | 0.1234 | 1.645e-06 | 0.03432 | 0.004112 | 0.9341 | 0.02027 | 1376 |
| separate_prefill_priority | 0.14 | 1 | burst_cap | RECOVERED | 0.1256 | -0.0001001 | 0.03432 | -0.2502 | 0.9361 | 0.2486 | 1400 |
| separate_prefill_priority | 0.14 | 2 | burst_cap | RECOVERED | 0.1376 | 0.0002436 | 0.03432 | 0.609 | 0.9367 | 0.3158 | 1533 |
| separate_prefill_priority | 0.14 | 0 | no_burst | RECOVERED | 0.1234 | 8.029e-07 | 0.03432 | 0.002007 | 0.9341 | 0.0201 | 1376 |
| separate_prefill_priority | 0.14 | 1 | no_burst | RECOVERED | 0.1256 | -1.763e-06 | 0.03432 | -0.004408 | 0.9361 | 0.02068 | 1400 |
| separate_prefill_priority | 0.14 | 2 | no_burst | RECOVERED | 0.1519 | 8.708e-05 | 0.03432 | 0.2177 | 0.9318 | 0.06871 | 1694 |
| separate_prefill_priority | 0.16 | 0 | burst | TRAPPED | 1.059 | 0.06714 | 0.04432 | 167.8 | 0 | 503.3 | 1.18e+04 |
| separate_prefill_priority | 0.16 | 1 | burst | TRAPPED | 1.06 | 0.07025 | 0.04432 | 175.6 | 0 | 497.2 | 1.182e+04 |
| separate_prefill_priority | 0.16 | 2 | burst | TRAPPED | 1.055 | 0.07733 | 0.04432 | 193.3 | 0 | 522.7 | 1.176e+04 |
| separate_prefill_priority | 0.16 | 0 | burst_cap | RECOVERED | 0.141 | -5.773e-05 | 0.04432 | -0.1443 | 0.9308 | 0.08554 | 1571 |
| separate_prefill_priority | 0.16 | 1 | burst_cap | RECOVERED | 0.148 | -0.001416 | 0.04432 | -3.54 | 0.9323 | 1.032 | 1650 |
| separate_prefill_priority | 0.16 | 2 | burst_cap | RECOVERED | 0.1498 | -0.0006052 | 0.04432 | -1.513 | 0.9323 | 0.6186 | 1670 |
| separate_prefill_priority | 0.16 | 0 | no_burst | RECOVERED | 0.1407 | 1.084e-06 | 0.04432 | 0.002711 | 0.9306 | 0.02485 | 1568 |
| separate_prefill_priority | 0.16 | 1 | no_burst | RECOVERED | 0.1471 | 1.758e-05 | 0.04432 | 0.04394 | 0.9325 | 0.0402 | 1640 |
| separate_prefill_priority | 0.16 | 2 | no_burst | TRAPPED | 1.047 | 0.07814 | 0.04432 | 195.4 | 0 | 310.4 | 1.167e+04 |

Sensitivity of the verdicts to the evaluation window (labelled; never used for the verdict):

| mode | eval_window_rel_to_burst | lam | burst_trapped | noburst_good | cap_recovered | PASS |
|---|---|---|---|---|---|---|
| mixed | [6000, 7500] | 0.09 | 1 | 3 | 3 | False |
| mixed | [6000, 7500] | 0.1 | 2 | 3 | 3 | True |
| mixed | [6000, 7500] | 0.11 | 2 | 3 | 3 | True |
| mixed | [6000, 7500] | 0.12 | 3 | 3 | 3 | True |
| mixed | [6000, 7500] | 0.13 | 3 | 3 | 3 | True |
| mixed | [6000, 7500] | 0.14 | 3 | 3 | 3 | True |
| mixed | [6000, 7500] | 0.16 | 3 | 2 | 3 | True |
| mixed | [2500, 7500] | 0.09 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.1 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.11 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.12 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.13 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.14 | 3 | 3 | 3 | True |
| mixed | [2500, 7500] | 0.16 | 3 | 2 | 2 | True |
| separate_prefill_priority | [6000, 7500] | 0.09 | 2 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.1 | 2 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.11 | 2 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.12 | 3 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.13 | 3 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.14 | 3 | 3 | 3 | True |
| separate_prefill_priority | [6000, 7500] | 0.16 | 3 | 2 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.09 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.1 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.11 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.12 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.13 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.14 | 3 | 3 | 3 | True |
| separate_prefill_priority | [2500, 7500] | 0.16 | 3 | 2 | 2 | True |

Supplementary (labelled, not part of the prediction): the same per-lambda verdict with 20 fresh seeds (100-119), counts out of 20 (need = 14):

| mode | lam | n_seeds | need | burst_trapped | noburst_good | cap_recovered | burst_recovered | noburst_trapped | cap_trapped | PASS | PASS_all_seeds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0.09 | 20 | 14 | 14 | 20 | 20 | 0 | 0 | 0 | True | False |
| mixed | 0.1 | 20 | 14 | 18 | 20 | 20 | 0 | 0 | 0 | True | False |
| mixed | 0.11 | 20 | 14 | 19 | 20 | 20 | 0 | 0 | 0 | True | False |
| mixed | 0.12 | 20 | 14 | 19 | 20 | 20 | 0 | 0 | 0 | True | False |
| mixed | 0.13 | 20 | 14 | 19 | 20 | 20 | 0 | 0 | 0 | True | False |
| mixed | 0.14 | 20 | 14 | 20 | 20 | 20 | 0 | 0 | 0 | True | True |
| mixed | 0.16 | 20 | 14 | 19 | 15 | 20 | 0 | 4 | 0 | True | False |
| separate_prefill_priority | 0.09 | 20 | 14 | 15 | 20 | 20 | 0 | 0 | 0 | True | False |
| separate_prefill_priority | 0.1 | 20 | 14 | 18 | 20 | 20 | 0 | 0 | 0 | True | False |
| separate_prefill_priority | 0.11 | 20 | 14 | 18 | 20 | 20 | 0 | 0 | 0 | True | False |
| separate_prefill_priority | 0.12 | 20 | 14 | 19 | 20 | 20 | 0 | 0 | 0 | True | False |
| separate_prefill_priority | 0.13 | 20 | 14 | 19 | 20 | 20 | 0 | 0 | 0 | True | False |
| separate_prefill_priority | 0.14 | 20 | 14 | 20 | 20 | 20 | 0 | 0 | 0 | True | True |
| separate_prefill_priority | 0.16 | 20 | 14 | 20 | 13 | 20 | 0 | 5 | 0 | False | False |

## B4. Closed-population curves with a larger KV pool (cache on, FCFS)

Registered (seed 0; each cell is `mu sessions/s / mu turns-based sessions/s / hit fraction`; the 300k column is the validation's own cell rerun in the same code):

mixed:

| n | 300k pool | 600k pool | 900k pool |
|---|---|---|---|
| 16 | 0.1828 / 0.1735 / 0.929 | 0.1828 / 0.1735 / 0.929 | 0.1828 / 0.1735 / 0.929 |
| 24 | 0.2261 / 0.2261 / 0.907 | 0.2544 / 0.2516 / 0.932 | 0.2544 / 0.2516 / 0.932 |
| 32 | 0.1539 / 0.1458 / 0.618 | 0.3294 / 0.3236 / 0.931 | 0.3294 / 0.3236 / 0.931 |
| 48 | 0.0761 / 0.0706 / 0.000 | 0.4061 / 0.4068 / 0.921 | 0.4383 / 0.4392 / 0.932 |
| 64 | 0.0722 / 0.0711 / 0.000 | 0.1050 / 0.1006 / 0.315 | 0.5228 / 0.5154 / 0.931 |
| 96 | 0.0711 / 0.0750 / 0.000 | 0.0733 / 0.0742 / 0.000 | 0.0794 / 0.0763 / 0.050 |
| 300 | 0.1061 / 0.1128 / 0.000 | 0.1078 / 0.1145 / 0.000 | 0.1089 / 0.1132 / 0.000 |

separate_prefill_priority:

| n | 300k pool | 600k pool | 900k pool |
|---|---|---|---|
| 16 | 0.1822 / 0.1724 / 0.928 | 0.1822 / 0.1724 / 0.928 | 0.1822 / 0.1724 / 0.928 |
| 24 | 0.2256 / 0.2248 / 0.908 | 0.2478 / 0.2479 / 0.932 | 0.2478 / 0.2479 / 0.932 |
| 32 | 0.1594 / 0.1520 / 0.646 | 0.3228 / 0.3181 / 0.931 | 0.3228 / 0.3181 / 0.931 |
| 48 | 0.0744 / 0.0701 / 0.013 | 0.3967 / 0.4009 / 0.923 | 0.4261 / 0.4251 / 0.932 |
| 64 | 0.0711 / 0.0704 / 0.000 | 0.1283 / 0.1269 / 0.491 | 0.4989 / 0.4948 / 0.932 |
| 96 | 0.0711 / 0.0752 / 0.000 | 0.0722 / 0.0730 / 0.000 | 0.0878 / 0.0845 / 0.180 |
| 300 | 0.1044 / 0.1125 / 0.000 | 0.1094 / 0.1122 / 0.000 | 0.1111 / 0.1129 / 0.000 |

Landmarks of the B4 curves (peak = first argmax of mu over the grid; hit crossing = n at which the hit fraction falls through 0.5, linear interpolation between adjacent grid points; coarse grid: 16, 24, 32, 48, 64, 96, 300):

| mode | kv_k | seeds | n_seeds | peak_n | peak_mu | hit_crossing_n | mu_48 | mu_64 | mu_96 | mu_300 |
|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 300 | seed 0 | 1 | 24 | 0.2261 | 35.05 | 0.07611 | 0.07222 | 0.07111 | 0.1061 |
| mixed | 300 | seeds 0-4 mean | 5 | 24 | 0.2181 | 31.07 | 0.06778 | 0.06733 | 0.07022 | 0.1067 |
| mixed | 600 | seed 0 | 1 | 48 | 0.4061 | 59.11 | 0.4061 | 0.105 | 0.07333 | 0.1078 |
| mixed | 600 | seeds 0-4 mean | 5 | 48 | 0.4189 | 58.11 | 0.4189 | 0.09633 | 0.07056 | 0.108 |
| mixed | 900 | seed 0 | 1 | 64 | 0.5228 | 79.65 | 0.4383 | 0.5228 | 0.07944 | 0.1089 |
| mixed | 900 | seeds 0-4 mean | 5 | 64 | 0.5139 | 80.71 | 0.4392 | 0.5139 | 0.08456 | 0.1078 |
| separate_prefill_priority | 300 | seed 0 | 1 | 24 | 0.2256 | 35.7 | 0.07444 | 0.07111 | 0.07111 | 0.1044 |
| separate_prefill_priority | 300 | seeds 0-4 mean | 5 | 24 | 0.2183 | 32.83 | 0.06789 | 0.06667 | 0.06944 | 0.106 |
| separate_prefill_priority | 600 | seed 0 | 1 | 48 | 0.3967 | 63.65 | 0.3967 | 0.1283 | 0.07222 | 0.1094 |
| separate_prefill_priority | 600 | seeds 0-4 mean | 5 | 48 | 0.4069 | 60.45 | 0.4069 | 0.1103 | 0.07056 | 0.107 |
| separate_prefill_priority | 900 | seed 0 | 1 | 64 | 0.4989 | 82.37 | 0.4261 | 0.4989 | 0.08778 | 0.1111 |
| separate_prefill_priority | 900 | seeds 0-4 mean | 5 | 64 | 0.4916 | 81.92 | 0.4267 | 0.4916 | 0.08478 | 0.1088 |

Supplementary: mean over seeds 0-4 (registered seed 0 plus supplementary seeds 1-4):

| mode | kv_k | n | n_seeds | mu_mean | mu_sd | mu_turns_mean | hit_mean |
|---|---|---|---|---|---|---|---|
| mixed | 300 | 16 | 5 | 0.1758 | 0.008594 | 0.176 | 0.9323 |
| mixed | 300 | 24 | 5 | 0.2181 | 0.02583 | 0.2177 | 0.8875 |
| mixed | 300 | 32 | 5 | 0.1099 | 0.03109 | 0.1101 | 0.4492 |
| mixed | 300 | 48 | 5 | 0.06778 | 0.005984 | 0.06954 | 0 |
| mixed | 300 | 64 | 5 | 0.06733 | 0.005022 | 0.07018 | 0 |
| mixed | 300 | 96 | 5 | 0.07022 | 0.001601 | 0.07611 | 0 |
| mixed | 300 | 300 | 5 | 0.1067 | 0.004938 | 0.1116 | 0 |
| mixed | 600 | 16 | 5 | 0.1758 | 0.008594 | 0.176 | 0.9323 |
| mixed | 600 | 24 | 5 | 0.2574 | 0.007882 | 0.255 | 0.9317 |
| mixed | 600 | 32 | 5 | 0.3308 | 0.01224 | 0.3264 | 0.9314 |
| mixed | 600 | 48 | 5 | 0.4189 | 0.02804 | 0.4156 | 0.9227 |
| mixed | 600 | 64 | 5 | 0.09633 | 0.04059 | 0.09761 | 0.2539 |
| mixed | 600 | 96 | 5 | 0.07056 | 0.004615 | 0.07491 | 0 |
| mixed | 600 | 300 | 5 | 0.108 | 0.004385 | 0.1135 | 0 |
| mixed | 900 | 16 | 5 | 0.1758 | 0.008594 | 0.176 | 0.9323 |
| mixed | 900 | 24 | 5 | 0.2574 | 0.007882 | 0.255 | 0.9317 |
| mixed | 900 | 32 | 5 | 0.3308 | 0.01224 | 0.3264 | 0.9314 |
| mixed | 900 | 48 | 5 | 0.4392 | 0.01879 | 0.4388 | 0.9322 |
| mixed | 900 | 64 | 5 | 0.5139 | 0.01569 | 0.5124 | 0.9321 |
| mixed | 900 | 96 | 5 | 0.08456 | 0.03341 | 0.08394 | 0.1047 |
| mixed | 900 | 300 | 5 | 0.1078 | 0.005167 | 0.1122 | 0 |
| separate_prefill_priority | 300 | 16 | 5 | 0.175 | 0.008425 | 0.1748 | 0.9322 |
| separate_prefill_priority | 300 | 24 | 5 | 0.2183 | 0.02155 | 0.218 | 0.8909 |
| separate_prefill_priority | 300 | 32 | 5 | 0.1237 | 0.03019 | 0.1223 | 0.5264 |
| separate_prefill_priority | 300 | 48 | 5 | 0.06789 | 0.006129 | 0.06967 | 0.01468 |
| separate_prefill_priority | 300 | 64 | 5 | 0.06667 | 0.004598 | 0.06972 | 0 |
| separate_prefill_priority | 300 | 96 | 5 | 0.06944 | 0.001843 | 0.07561 | 0 |
| separate_prefill_priority | 300 | 300 | 5 | 0.106 | 0.005698 | 0.1113 | 0 |
| separate_prefill_priority | 600 | 16 | 5 | 0.175 | 0.008425 | 0.1748 | 0.9322 |
| separate_prefill_priority | 600 | 24 | 5 | 0.2533 | 0.008854 | 0.2519 | 0.9319 |
| separate_prefill_priority | 600 | 32 | 5 | 0.3248 | 0.01357 | 0.3206 | 0.9314 |
| separate_prefill_priority | 600 | 48 | 5 | 0.4069 | 0.02941 | 0.4043 | 0.9231 |
| separate_prefill_priority | 600 | 64 | 5 | 0.1103 | 0.03833 | 0.1109 | 0.3792 |
| separate_prefill_priority | 600 | 96 | 5 | 0.07056 | 0.003356 | 0.0742 | 0 |
| separate_prefill_priority | 600 | 300 | 5 | 0.107 | 0.006244 | 0.1111 | 0 |
| separate_prefill_priority | 900 | 16 | 5 | 0.175 | 0.008425 | 0.1748 | 0.9322 |
| separate_prefill_priority | 900 | 24 | 5 | 0.2533 | 0.008854 | 0.2519 | 0.9319 |
| separate_prefill_priority | 900 | 32 | 5 | 0.3248 | 0.01357 | 0.3206 | 0.9314 |
| separate_prefill_priority | 900 | 48 | 5 | 0.4267 | 0.02034 | 0.4258 | 0.9321 |
| separate_prefill_priority | 900 | 64 | 5 | 0.4916 | 0.01707 | 0.4915 | 0.9322 |
| separate_prefill_priority | 900 | 96 | 5 | 0.08478 | 0.02507 | 0.08486 | 0.1606 |
| separate_prefill_priority | 900 | 300 | 5 | 0.1088 | 0.006078 | 0.1118 | 0 |
