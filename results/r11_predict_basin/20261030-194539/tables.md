# r11 predict basin: generated tables

result dir `results/r11_predict_basin/20261030-194539`

## Plan reproduction

| kind | seed | mult | burst_n | n_sessions | n_sessions_committed | rate_equal | arrivals_turns_exact | tool_total_max_abs_diff_s | tool_total_n_last_bit_diff | exact |
|---|---|---|---|---|---|---|---|---|---|---|
| basin | 0 | 1.65 | 200 | 1294 | 1294 | yes | yes | 1.705e-13 | 467 | yes |
| basin | 1 | 1.65 | 200 | 1246 | 1246 | yes | yes | 1.705e-13 | 468 | yes |
| basin | 2 | 1.65 | 200 | 1289 | 1289 | yes | yes | 1.705e-13 | 456 | yes |
| basin | 0 | 1.65 | 0 | 1094 | 1094 | yes | yes | 1.705e-13 | 406 | yes |
| basin | 1 | 1.65 | 0 | 1046 | 1046 | yes | yes | 1.705e-13 | 385 | yes |
| basin | 2 | 1.65 | 0 | 1089 | 1089 | yes | yes | 1.705e-13 | 384 | yes |
| e0b | 0 | 2 | 0 | 472 | 472 | yes | yes | 1.705e-13 | 177 | yes |
| e0b | 0 | 2.5 | 0 | 585 | 585 | yes | yes | 1.705e-13 | 217 | yes |

| seed | burst_n | base_identical_to_n200 | n_burst | burst_times_subset_of_n200 | plan_equals_cell_config_plan |
|---|---|---|---|---|---|
| 0 | 25 | yes | 25 | yes | yes |
| 0 | 100 | yes | 100 | yes | yes |
| 1 | 25 | yes | 25 | yes | yes |
| 1 | 100 | yes | 100 | yes | yes |
| 2 | 25 | yes | 25 | yes | yes |
| 2 | 100 | yes | 100 | yes | yes |

## B1 summary (counts; engine = seeds 0-2 on the exact client plans, extra = 30 seeds)

| mode | burst_n | engine_states | engine_stuck | engine_good | engine_trapped | engine_hit_eval_mean | extra_n | extra_stuck | extra_good | extra_trapped | extra_recovered | extra_hit_eval_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0 | s0:recovered s1:recovered s2:recovered | 0 | 3 | 0 | 0.9323 | 30 | 0 | 30 | 0 | 30 | 0.9323 |
| mixed | 25 | s0:recovered s1:recovered s2:recovered | 0 | 3 | 0 | 0.9322 | 30 | 2 | 28 | 2 | 28 | 0.8702 |
| mixed | 100 | s0:trapped s1:trapped s2:trapped | 3 | 0 | 3 | 0 | 30 | 30 | 0 | 24 | 0 | 0 |
| mixed | 200 | s0:trapped s1:trapped s2:trapped | 3 | 0 | 3 | 0 | 30 | 30 | 0 | 24 | 0 | 0 |
| separate | 0 | s0:recovered s1:recovered s2:recovered | 0 | 3 | 0 | 0.9328 | 30 | 0 | 30 | 0 | 30 | 0.9323 |
| separate | 25 | s0:recovered s1:recovered s2:recovered | 0 | 3 | 0 | 0.9326 | 30 | 2 | 28 | 2 | 28 | 0.8702 |
| separate | 100 | s0:trapped s1:trapped s2:trapped | 3 | 0 | 3 | 0 | 30 | 30 | 0 | 25 | 0 | 0 |
| separate | 200 | s0:trapped s1:trapped s2:trapped | 3 | 0 | 3 | 0 | 30 | 30 | 0 | 25 | 0 | 0 |

## B1 engine-seed runs

| mode | burst_n | seed | n_base | realized_base_mult | hit_pre_burst | hit_eval | token_ratio | backlog_slope | slope_threshold | crit_a | crit_b | hit_end | outstanding_end_qg | state | stuck | good | trap_onset_s | release_s | max_queue_gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0 | 0 | 1094 | 1.758 | 0.9293 | 0.9339 | 0.108 | -0.0006763 | 0.02325 | no | no | 0.943 | 0.01862 | recovered | no | yes | nan | nan | 0.1868 |
| mixed | 0 | 1 | 1046 | 1.681 | 0.9229 | 0.9344 | 0.1008 | 0.0008665 | 0.02325 | no | no | 0.9322 | 0.009206 | recovered | no | yes | nan | nan | 0.03662 |
| mixed | 0 | 2 | 1089 | 1.75 | 0.9286 | 0.9287 | 0.111 | 0.0002881 | 0.02325 | no | no | 0.9379 | 0.0118 | recovered | no | yes | nan | nan | 0.252 |
| mixed | 25 | 0 | 1094 | 1.758 | 0.9293 | 0.9339 | 0.108 | -0.0006763 | 0.02325 | no | no | 0.9429 | 0.0171 | recovered | no | yes | nan | nan | 0.1898 |
| mixed | 25 | 1 | 1046 | 1.681 | 0.9229 | 0.9344 | 0.1008 | 0.0008665 | 0.02325 | no | no | 0.9322 | 0.009046 | recovered | no | yes | nan | nan | 0.05276 |
| mixed | 25 | 2 | 1089 | 1.75 | 0.9286 | 0.9284 | 0.1124 | 0.0003281 | 0.02325 | no | no | 0.938 | 0.01174 | recovered | no | yes | nan | nan | 0.4061 |
| mixed | 100 | 0 | 1094 | 1.758 | 0.9293 | 0 | 1.032 | 0.03139 | 0.02325 | yes | yes | 0 | 273.8 | trapped | yes | no | 1400 | nan | 275.6 |
| mixed | 100 | 1 | 1046 | 1.681 | 0.9229 | 0 | 1.041 | 0.03485 | 0.02325 | yes | yes | 0 | 230.8 | trapped | yes | no | 1400 | nan | 234.2 |
| mixed | 100 | 2 | 1089 | 1.75 | 0.9286 | 0 | 1.049 | 0.03598 | 0.02325 | yes | yes | 0 | 236.9 | trapped | yes | no | 1400 | nan | 238.5 |
| mixed | 200 | 0 | 1094 | 1.758 | 0.9293 | 0 | 1.04 | 0.03083 | 0.02325 | yes | yes | 0 | 322.3 | trapped | yes | no | 1400 | nan | 326 |
| mixed | 200 | 1 | 1046 | 1.681 | 0.9229 | 0 | 1.039 | 0.02741 | 0.02325 | yes | yes | 0 | 276.9 | trapped | yes | no | 1400 | nan | 278.9 |
| mixed | 200 | 2 | 1089 | 1.75 | 0.9286 | 0 | 1.043 | 0.03602 | 0.02325 | yes | yes | 0 | 311.5 | trapped | yes | no | 1400 | nan | 312.2 |
| separate | 0 | 0 | 1094 | 1.758 | 0.9293 | 0.9339 | 0.1087 | -0.0007253 | 0.02325 | no | no | 0.943 | 0.01896 | recovered | no | yes | nan | nan | 0.03829 |
| separate | 0 | 1 | 1046 | 1.681 | 0.9229 | 0.9344 | 0.1014 | 0.0008443 | 0.02325 | no | no | 0.9325 | 0.008603 | recovered | no | yes | nan | nan | 0.03682 |
| separate | 0 | 2 | 1089 | 1.75 | 0.9286 | 0.9302 | 0.1081 | 0.0003192 | 0.02325 | no | no | 0.938 | 0.01089 | recovered | no | yes | nan | nan | 0.09487 |
| separate | 25 | 0 | 1094 | 1.758 | 0.9293 | 0.9339 | 0.1087 | -0.0007297 | 0.02325 | no | no | 0.943 | 0.01873 | recovered | no | yes | nan | nan | 0.1677 |
| separate | 25 | 1 | 1046 | 1.681 | 0.9229 | 0.9344 | 0.1014 | 0.0008443 | 0.02325 | no | no | 0.9325 | 0.00897 | recovered | no | yes | nan | nan | 0.04932 |
| separate | 25 | 2 | 1089 | 1.75 | 0.9286 | 0.9295 | 0.1094 | 0.0003515 | 0.02325 | no | no | 0.938 | 0.01254 | recovered | no | yes | nan | nan | 0.1559 |
| separate | 100 | 0 | 1094 | 1.758 | 0.9293 | 0 | 1.028 | 0.03208 | 0.02325 | yes | yes | 0 | 285.2 | trapped | yes | no | 1400 | nan | 289.1 |
| separate | 100 | 1 | 1046 | 1.681 | 0.9229 | 0 | 1.035 | 0.03433 | 0.02325 | yes | yes | 0 | 246.4 | trapped | yes | no | 1400 | nan | 250 |
| separate | 100 | 2 | 1089 | 1.75 | 0.9286 | 0 | 1.044 | 0.0363 | 0.02325 | yes | yes | 0 | 250.7 | trapped | yes | no | 1400 | nan | 252.8 |
| separate | 200 | 0 | 1094 | 1.758 | 0.9293 | 0 | 1.036 | 0.03186 | 0.02325 | yes | yes | 0 | 333 | trapped | yes | no | 1400 | nan | 334.4 |
| separate | 200 | 1 | 1046 | 1.681 | 0.9229 | 0 | 1.033 | 0.02764 | 0.02325 | yes | yes | 0 | 290.7 | trapped | yes | no | 1400 | nan | 293.8 |
| separate | 200 | 2 | 1089 | 1.75 | 0.9286 | 0 | 1.038 | 0.03563 | 0.02325 | yes | yes | 0 | 330.8 | trapped | yes | no | 1400 | nan | 332 |

## E0b summary (engine = seeds 3-5 exact plans; reference = committed seed 0; extra = 20 seeds)

| mode | mult | engine_by_seed | engine_stable | reference_by_seed | extra_n | extra_stable | extra_stable_r6_rule |
|---|---|---|---|---|---|---|---|
| mixed | 2 | s3:stable s4:stable s5:stable | 3 | s0:stable | 20 | 18 | 18 |
| mixed | 2.5 | s3:stable s4:stable s5:stable | 3 | s0:UNSTABLE | 20 | 11 | 11 |
| separate | 2 | s3:stable s4:stable s5:stable | 3 | s0:stable | 20 | 19 | 19 |
| separate | 2.5 | s3:stable s4:stable s5:stable | 3 | s0:UNSTABLE | 20 | 12 | 12 |

## E0b engine-seed and reference runs

| mode | mult | seed | seed_kind | n_base | realized_base_mult | base_count_z | stable | final_queue_lastwin | trend_rise | stopped_early | stop_time | tail_hit | max_queue |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 2 | 0 | reference | 472 | 2.199 | 2.066 | yes | 0.04952 | -0.3231 | 0 | nan | 0.922 | 10 |
| mixed | 2 | 3 | engine | 432 | 2.013 | 0.135 | yes | 0.01509 | 0.005365 | 0 | nan | 0.9361 | 3 |
| mixed | 2 | 4 | engine | 461 | 2.148 | 1.535 | yes | 0.01065 | -0.0122 | 0 | nan | 0.9232 | 3 |
| mixed | 2 | 5 | engine | 423 | 1.971 | -0.2995 | yes | 0.005939 | -0.01379 | 0 | nan | 0.9348 | 3 |
| mixed | 2.5 | 0 | reference | 585 | 2.726 | 2.094 | no | 121.3 | 134.1 | 0 | nan | 0.03356 | 128 |
| mixed | 2.5 | 3 | engine | 539 | 2.512 | 0.1077 | yes | 0.04225 | 0.007077 | 0 | nan | 0.9355 | 5 |
| mixed | 2.5 | 4 | engine | 572 | 2.665 | 1.532 | yes | 0.04604 | -0.01619 | 0 | nan | 0.9221 | 4 |
| mixed | 2.5 | 5 | engine | 530 | 2.47 | -0.2808 | yes | 0.01472 | -0.005016 | 0 | nan | 0.9363 | 4 |
| separate | 2 | 0 | reference | 472 | 2.199 | 2.066 | yes | 0.06661 | -0.4374 | 0 | nan | 0.9081 | 16 |
| separate | 2 | 3 | engine | 432 | 2.013 | 0.135 | yes | 0.01523 | 0.005179 | 0 | nan | 0.9362 | 4 |
| separate | 2 | 4 | engine | 461 | 2.148 | 1.535 | yes | 0.008914 | -0.01088 | 0 | nan | 0.9233 | 3 |
| separate | 2 | 5 | engine | 423 | 1.971 | -0.2995 | yes | 0.006693 | -0.01557 | 0 | nan | 0.9349 | 3 |
| separate | 2.5 | 0 | reference | 585 | 2.726 | 2.094 | no | 114.5 | 131.8 | 0 | nan | 0.06737 | 128 |
| separate | 2.5 | 3 | engine | 539 | 2.512 | 0.1077 | yes | 0.03708 | 0.002966 | 0 | nan | 0.9351 | 7 |
| separate | 2.5 | 4 | engine | 572 | 2.665 | 1.532 | yes | 0.03527 | -0.02163 | 0 | nan | 0.9222 | 7 |
| separate | 2.5 | 5 | engine | 530 | 2.47 | -0.2808 | yes | 0.0147 | -0.005762 | 0 | nan | 0.9361 | 3 |
