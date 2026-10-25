# Baselines audit: measured tables

lambda_miss = 0.047418947368421054 sessions/s. Generated 20261025-001850.

### Closed-population service rate, seeds 0-2 (the round-3 seeds)

mu(300) / lambda_miss, mean +- 95% t half-width over seeds (sd in brackets); hit = mean steady-state hit rate.

| group | policy | seeds | mu/lambda_miss | sd | min..max | hit rate | GPU busy |
|---|---|---|---|---|---|---|---|
| PEEK | fcfs | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_rank | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek | 3 | 0.895 +- 0.130 | 0.052 | 0.85..0.95 | 0.125 | 1.000 |
| PEEK | peek_order_audit | 3 | 1.169 +- 0.071 | 0.029 | 1.14..1.20 | 0.217 | 1.000 |
| PEEK | peek_score_audit | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_singleton_audit | 3 | 1.163 +- 0.069 | 0.028 | 1.13..1.19 | 0.209 | 1.000 |
| PEEK | lpm | 3 | 1.161 +- 0.114 | 0.046 | 1.13..1.21 | 0.206 | 1.000 |
| Continuum pins | ttl5 | 3 | 2.581 +- 0.088 | 0.035 | 2.55..2.62 | 0.662 | 0.986 |
| Continuum pins | ttl5cw | 3 | 2.573 +- 0.108 | 0.044 | 2.54..2.62 | 0.655 | 1.000 |
| Continuum pins | ttl5cwr | 3 | 2.582 +- 0.107 | 0.043 | 2.55..2.63 | 0.657 | 1.000 |
| Continuum pins | ttl10 | 3 | 3.324 +- 0.216 | 0.087 | 3.26..3.42 | 0.817 | 0.903 |
| Continuum pins | ttl10e | 3 | 1.153 +- 0.075 | 0.030 | 1.12..1.18 | 0.135 | 1.000 |
| Continuum pins | ttl10ef | 3 | 1.151 +- 0.168 | 0.068 | 1.09..1.23 | 0.141 | 1.000 |
| Continuum pins | ttl10cw | 3 | 3.527 +- 0.315 | 0.127 | 3.45..3.67 | 0.807 | 1.000 |
| Continuum pins | ttl10cwr | 3 | 3.520 +- 0.330 | 0.133 | 3.43..3.67 | 0.807 | 1.000 |
| Continuum pins | ttl20 | 3 | 1.653 +- 0.084 | 0.034 | 1.63..1.69 | 0.895 | 0.331 |
| Continuum pins | ttl20e | 3 | 1.139 +- 0.095 | 0.038 | 1.10..1.17 | 0.133 | 1.000 |
| Continuum pins | ttl20ef | 3 | 1.145 +- 0.086 | 0.035 | 1.12..1.18 | 0.137 | 1.000 |
| Continuum pins | ttl20cw | 3 | 4.374 +- 0.204 | 0.082 | 4.29..4.45 | 0.892 | 1.000 |
| Continuum pins | ttl20cwr | 3 | 4.375 +- 0.204 | 0.082 | 4.29..4.45 | 0.891 | 1.000 |
| CONCUR | concur_cap | 3 | 3.027 +- 0.233 | 0.094 | 2.93..3.12 | 0.932 | 0.977 |
| CONCUR | concur_lpm | 3 | 3.115 +- 0.165 | 0.067 | 3.06..3.19 | 0.932 | 0.980 |
| CONCUR | concur_i5 | 3 | 3.183 +- 0.540 | 0.217 | 3.02..3.43 | 0.932 | 0.981 |
| CONCUR | concur_i20 | 3 | 2.936 +- 0.457 | 0.184 | 2.72..3.06 | 0.932 | 0.972 |
| CONCUR | concur_s8 | 3 | 3.190 +- 0.536 | 0.216 | 3.02..3.43 | 0.932 | 0.982 |
| CONCUR | concur_s56 | 3 | 3.024 +- 0.244 | 0.098 | 2.93..3.13 | 0.932 | 0.977 |

Paired differences (same seeds), audited minus reference, in units of lambda_miss:

| audited | reference | mean diff +- 95% half-width | relative to reference | seeds > 0 / = 0 / n |
|---|---|---|---|---|
| peek_order_audit | peek_rank | +0.155 +- 0.037 | +15.3% | 3 / 0 / 3 |
| peek_score_audit | peek_rank | +0.000 +- 0.000 | +0.0% | 0 / 3 / 3 |
| peek_singleton_audit | peek_rank | +0.149 +- 0.048 | +14.7% | 3 / 0 / 3 |
| peek_singleton_audit | lpm | +0.002 +- 0.065 | +0.1% | 1 / 1 / 3 |
| ttl5cw | ttl5 | -0.008 +- 0.053 | -0.3% | 2 / 0 / 3 |
| ttl5cwr | ttl5cw | +0.010 +- 0.018 | +0.4% | 3 / 0 / 3 |
| ttl5cwr | ttl5 | +0.001 +- 0.038 | +0.0% | 2 / 0 / 3 |
| ttl10cw | ttl10 | +0.202 +- 0.105 | +6.1% | 3 / 0 / 3 |
| ttl10cwr | ttl10cw | -0.007 +- 0.030 | -0.2% | 0 / 2 / 3 |
| ttl10cwr | ttl10 | +0.195 +- 0.115 | +5.9% | 3 / 0 / 3 |
| ttl20cw | ttl20 | +2.721 +- 0.140 | +164.6% | 3 / 0 / 3 |
| ttl20cwr | ttl20cw | +0.001 +- 0.001 | +0.0% | 2 / 1 / 3 |
| ttl20cwr | ttl20 | +2.722 +- 0.140 | +164.6% | 3 / 0 / 3 |
| concur_lpm | concur_cap | +0.088 +- 0.230 | +2.9% | 2 / 0 / 3 |
| concur_i5 | concur_cap | +0.156 +- 0.735 | +5.2% | 1 / 0 / 3 |
| concur_i20 | concur_cap | -0.091 +- 0.674 | -3.0% | 1 / 1 / 3 |
| concur_s8 | concur_cap | +0.163 +- 0.724 | +5.4% | 1 / 0 / 3 |
| concur_s56 | concur_cap | -0.003 +- 0.029 | -0.1% | 1 / 0 / 3 |

### Closed-population service rate, seeds 0-9

mu(300) / lambda_miss, mean +- 95% t half-width over seeds (sd in brackets); hit = mean steady-state hit rate.

| group | policy | seeds | mu/lambda_miss | sd | min..max | hit rate | GPU busy |
|---|---|---|---|---|---|---|---|
| PEEK | fcfs | 10 | 1.024 +- 0.020 | 0.028 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_rank | 10 | 1.024 +- 0.020 | 0.028 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek | 10 | 0.919 +- 0.024 | 0.033 | 0.85..0.96 | 0.126 | 1.000 |
| PEEK | peek_order_audit | 10 | 1.176 +- 0.021 | 0.030 | 1.12..1.22 | 0.216 | 1.000 |
| PEEK | peek_score_audit | 10 | 1.024 +- 0.020 | 0.028 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_singleton_audit | 10 | 1.176 +- 0.021 | 0.029 | 1.12..1.21 | 0.214 | 1.000 |
| PEEK | lpm | 10 | 1.174 +- 0.023 | 0.032 | 1.13..1.21 | 0.212 | 1.000 |
| Continuum pins | ttl5 | 10 | 2.587 +- 0.031 | 0.043 | 2.49..2.64 | 0.661 | 0.986 |
| Continuum pins | ttl5cw | 10 | 2.584 +- 0.035 | 0.049 | 2.48..2.64 | 0.654 | 1.000 |
| Continuum pins | ttl5cwr | 10 | 2.584 +- 0.033 | 0.046 | 2.48..2.64 | 0.655 | 1.000 |
| Continuum pins | ttl10 | 10 | 3.317 +- 0.058 | 0.081 | 3.15..3.42 | 0.816 | 0.905 |
| Continuum pins | ttl10e | 10 | 1.162 +- 0.026 | 0.036 | 1.12..1.22 | 0.129 | 1.000 |
| Continuum pins | ttl10ef | 10 | 1.168 +- 0.036 | 0.050 | 1.09..1.23 | 0.139 | 1.000 |
| Continuum pins | ttl10cw | 10 | 3.505 +- 0.064 | 0.089 | 3.33..3.67 | 0.806 | 1.000 |
| Continuum pins | ttl10cwr | 10 | 3.503 +- 0.066 | 0.092 | 3.32..3.67 | 0.806 | 1.000 |
| Continuum pins | ttl20 | 10 | 1.719 +- 0.058 | 0.081 | 1.63..1.88 | 0.895 | 0.343 |
| Continuum pins | ttl20e | 10 | 1.163 +- 0.033 | 0.046 | 1.10..1.23 | 0.132 | 1.000 |
| Continuum pins | ttl20ef | 10 | 1.168 +- 0.026 | 0.036 | 1.12..1.23 | 0.140 | 1.000 |
| Continuum pins | ttl20cw | 10 | 4.376 +- 0.048 | 0.067 | 4.23..4.45 | 0.891 | 1.000 |
| Continuum pins | ttl20cwr | 10 | 4.374 +- 0.047 | 0.066 | 4.23..4.45 | 0.891 | 1.000 |
| CONCUR | concur_cap | 10 | 3.009 +- 0.081 | 0.113 | 2.87..3.23 | 0.932 | 0.975 |
| CONCUR | concur_lpm | 10 | 3.024 +- 0.081 | 0.113 | 2.77..3.19 | 0.932 | 0.977 |
| CONCUR | concur_i5 | 10 | 3.192 +- 0.123 | 0.173 | 3.02..3.47 | 0.932 | 0.982 |
| CONCUR | concur_i20 | 10 | 2.966 +- 0.104 | 0.146 | 2.68..3.09 | 0.932 | 0.974 |
| CONCUR | concur_s8 | 10 | 3.109 +- 0.091 | 0.127 | 2.96..3.43 | 0.932 | 0.979 |
| CONCUR | concur_s56 | 10 | 2.998 +- 0.080 | 0.111 | 2.74..3.13 | 0.932 | 0.975 |

Paired differences (same seeds), audited minus reference, in units of lambda_miss:

| audited | reference | mean diff +- 95% half-width | relative to reference | seeds > 0 / = 0 / n |
|---|---|---|---|---|
| peek_order_audit | peek_rank | +0.152 +- 0.016 | +14.9% | 10 / 0 / 10 |
| peek_score_audit | peek_rank | +0.000 +- 0.000 | +0.0% | 0 / 10 / 10 |
| peek_singleton_audit | peek_rank | +0.152 +- 0.015 | +14.8% | 10 / 0 / 10 |
| peek_singleton_audit | lpm | +0.001 +- 0.014 | +0.1% | 4 / 1 / 10 |
| ttl5cw | ttl5 | -0.003 +- 0.012 | -0.1% | 5 / 0 / 10 |
| ttl5cwr | ttl5cw | +0.001 +- 0.008 | +0.0% | 7 / 0 / 10 |
| ttl5cwr | ttl5 | -0.003 +- 0.009 | -0.1% | 4 / 0 / 10 |
| ttl10cw | ttl10 | +0.188 +- 0.027 | +5.7% | 10 / 0 / 10 |
| ttl10cwr | ttl10cw | -0.002 +- 0.007 | -0.1% | 3 / 2 / 10 |
| ttl10cwr | ttl10 | +0.185 +- 0.026 | +5.6% | 10 / 0 / 10 |
| ttl20cw | ttl20 | +2.658 +- 0.068 | +154.6% | 10 / 0 / 10 |
| ttl20cwr | ttl20cw | -0.003 +- 0.004 | -0.1% | 2 / 4 / 10 |
| ttl20cwr | ttl20 | +2.655 +- 0.070 | +154.5% | 10 / 0 / 10 |
| concur_lpm | concur_cap | +0.015 +- 0.117 | +0.5% | 5 / 1 / 10 |
| concur_i5 | concur_cap | +0.184 +- 0.167 | +6.1% | 6 / 0 / 10 |
| concur_i20 | concur_cap | -0.043 +- 0.153 | -1.4% | 5 / 1 / 10 |
| concur_s8 | concur_cap | +0.101 +- 0.120 | +3.4% | 6 / 0 / 10 |
| concur_s56 | concur_cap | -0.010 +- 0.105 | -0.3% | 5 / 0 / 10 |

### Closed-population service rate, seeds 0-2, finished sessions keep their KV (engine.free_kv_on_session_end=false)

mu(300) / lambda_miss, mean +- 95% t half-width over seeds (sd in brackets); hit = mean steady-state hit rate.

| group | policy | seeds | mu/lambda_miss | sd | min..max | hit rate | GPU busy |
|---|---|---|---|---|---|---|---|
| PEEK | fcfs | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_rank | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek | 3 | 0.905 +- 0.120 | 0.048 | 0.86..0.96 | 0.126 | 1.000 |
| PEEK | peek_order_audit | 3 | 1.156 +- 0.078 | 0.032 | 1.13..1.19 | 0.206 | 1.000 |
| PEEK | peek_score_audit | 3 | 1.014 +- 0.099 | 0.040 | 0.99..1.06 | 0.000 | 1.000 |
| PEEK | peek_singleton_audit | 3 | 1.156 +- 0.078 | 0.032 | 1.13..1.19 | 0.207 | 1.000 |
| PEEK | lpm | 3 | 1.161 +- 0.072 | 0.029 | 1.14..1.19 | 0.206 | 1.000 |
| Continuum pins | ttl5 | 3 | 2.565 +- 0.119 | 0.048 | 2.53..2.62 | 0.660 | 0.986 |
| Continuum pins | ttl5cw | 3 | 2.565 +- 0.120 | 0.048 | 2.52..2.62 | 0.653 | 1.000 |
| Continuum pins | ttl5cwr | 3 | 2.582 +- 0.129 | 0.052 | 2.55..2.64 | 0.655 | 1.000 |
| Continuum pins | ttl10 | 3 | 3.334 +- 0.251 | 0.101 | 3.27..3.45 | 0.815 | 0.908 |
| Continuum pins | ttl10e | 3 | 1.156 +- 0.133 | 0.054 | 1.11..1.21 | 0.137 | 1.000 |
| Continuum pins | ttl10ef | 3 | 1.146 +- 0.106 | 0.043 | 1.10..1.19 | 0.141 | 1.000 |
| Continuum pins | ttl10cw | 3 | 3.502 +- 0.312 | 0.125 | 3.43..3.65 | 0.805 | 1.000 |
| Continuum pins | ttl10cwr | 3 | 3.518 +- 0.333 | 0.134 | 3.44..3.67 | 0.805 | 1.000 |
| Continuum pins | ttl20 | 3 | 1.670 +- 0.066 | 0.027 | 1.64..1.70 | 0.894 | 0.334 |
| Continuum pins | ttl20e | 3 | 1.160 +- 0.108 | 0.043 | 1.11..1.20 | 0.139 | 1.000 |
| Continuum pins | ttl20ef | 3 | 1.146 +- 0.106 | 0.043 | 1.11..1.19 | 0.140 | 1.000 |
| Continuum pins | ttl20cw | 3 | 4.367 +- 0.227 | 0.091 | 4.26..4.44 | 0.891 | 1.000 |
| Continuum pins | ttl20cwr | 3 | 4.384 +- 0.179 | 0.072 | 4.30..4.44 | 0.892 | 1.000 |
| CONCUR | concur_cap | 3 | 2.335 +- 3.019 | 1.215 | 0.93..3.06 | 0.933 | 0.865 |
| CONCUR | concur_lpm | 3 | 1.627 +- 2.987 | 1.202 | 0.93..3.02 | 0.933 | 0.751 |
| CONCUR | concur_i5 | 3 | 0.927 +- 0.026 | 0.011 | 0.92..0.93 | 0.933 | 0.638 |
| CONCUR | concur_i20 | 3 | 0.929 +- 0.020 | 0.008 | 0.92..0.93 | 0.933 | 0.638 |
| CONCUR | concur_s8 | 3 | 3.063 +- 0.145 | 0.058 | 3.00..3.12 | 0.932 | 0.979 |
| CONCUR | concur_s56 | 3 | 0.928 +- 0.016 | 0.006 | 0.92..0.93 | 0.933 | 0.637 |

Paired differences (same seeds), audited minus reference, in units of lambda_miss:

| audited | reference | mean diff +- 95% half-width | relative to reference | seeds > 0 / = 0 / n |
|---|---|---|---|---|
| peek_order_audit | peek_rank | +0.143 +- 0.028 | +14.1% | 3 / 0 / 3 |
| peek_score_audit | peek_rank | +0.000 +- 0.000 | +0.0% | 0 / 3 / 3 |
| peek_singleton_audit | peek_rank | +0.143 +- 0.028 | +14.1% | 3 / 0 / 3 |
| peek_singleton_audit | lpm | -0.005 +- 0.030 | -0.4% | 1 / 0 / 3 |
| ttl5cw | ttl5 | -0.000 +- 0.018 | -0.0% | 1 / 0 / 3 |
| ttl5cwr | ttl5cw | +0.018 +- 0.024 | +0.7% | 3 / 0 / 3 |
| ttl5cwr | ttl5 | +0.017 +- 0.010 | +0.7% | 3 / 0 / 3 |
| ttl10cw | ttl10 | +0.168 +- 0.062 | +5.0% | 3 / 0 / 3 |
| ttl10cwr | ttl10cw | +0.016 +- 0.026 | +0.5% | 3 / 0 / 3 |
| ttl10cwr | ttl10 | +0.184 +- 0.085 | +5.5% | 3 / 0 / 3 |
| ttl20cw | ttl20 | +2.697 +- 0.165 | +161.6% | 3 / 0 / 3 |
| ttl20cwr | ttl20cw | +0.017 +- 0.049 | +0.4% | 3 / 0 / 3 |
| ttl20cwr | ttl20 | +2.714 +- 0.117 | +162.6% | 3 / 0 / 3 |
| concur_lpm | concur_cap | -0.708 +- 3.046 | -30.3% | 1 / 0 / 3 |
| concur_i5 | concur_cap | -1.408 +- 3.029 | -60.3% | 0 / 1 / 3 |
| concur_i20 | concur_cap | -1.406 +- 3.026 | -60.2% | 0 / 1 / 3 |
| concur_s8 | concur_cap | +0.728 +- 3.140 | +31.2% | 2 / 0 / 3 |
| concur_s56 | concur_cap | -1.408 +- 3.028 | -60.3% | 0 / 1 / 3 |

### Cold-start recovery (300 cold sessions, open arrivals at m x lambda_miss, horizon 30000 s): recovered runs / 3

| group | policy | 1.1x | 1.25x | 1.5x | 1.75x | 2x | 2.5x | 3x | 3.5x | highest m with all recovered |
|---|---|---|---|---|---|---|---|---|---|---|
| PEEK | fcfs | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | peek_rank | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | peek | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | peek_order_audit | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | peek_score_audit | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | peek_singleton_audit | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| PEEK | lpm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl5 | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 2x |
| Continuum pins | ttl5cw | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 2x |
| Continuum pins | ttl5cwr | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 2x |
| Continuum pins | ttl10 | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 0 | 2.5x |
| Continuum pins | ttl10e | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl10ef | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl10cw | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 3x |
| Continuum pins | ttl10cwr | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 3x |
| Continuum pins | ttl20 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1.25x |
| Continuum pins | ttl20e | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl20ef | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl20cw | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3.5x |
| Continuum pins | ttl20cwr | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3.5x |
| CONCUR | concur_cap | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 2.5x |
| CONCUR | concur_lpm | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 2.5x |
| CONCUR | concur_i5 | 3 | 3 | 3 | 3 | 3 | 3 | 1 | 0 | 2.5x |
| CONCUR | concur_i20 | 3 | 3 | 3 | 3 | 3 | 2 | 0 | 0 | 2x |
| CONCUR | concur_s8 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 | 2.5x |
| CONCUR | concur_s56 | 3 | 3 | 3 | 3 | 3 | 2 | 0 | 0 | 2x |

### Cold-start recovery, higher multiples for the rows that still recovered at 3.5x (300 cold sessions, open arrivals at m x lambda_miss, horizon 30000 s): recovered runs / 3

| group | policy | 3.25x | 4x | 4.5x | 5x | highest m with all recovered |
|---|---|---|---|---|---|---|
| Continuum pins | ttl10 | 0 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl10cw | 2 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl10cwr | 2 | 0 | 0 | 0 | none in range |
| Continuum pins | ttl20cw | 3 | 3 | 0 | 0 | 4x |
| Continuum pins | ttl20cwr | 3 | 3 | 0 | 0 | 4x |

### Cold-start recovery near lambda_miss at the registered long horizon (300 cold sessions, open arrivals at m x lambda_miss, horizon 150000 s): recovered runs / 3

| group | policy | 0.9x | 1x | 1.1x | 1.25x | highest m with all recovered |
|---|---|---|---|---|---|---|
| PEEK | fcfs | 3 | 0 | 0 | 0 | 0.9x |
| PEEK | peek_rank | 3 | 0 | 0 | 0 | 0.9x |
| PEEK | peek_order_audit | 3 | 3 | 2 | 0 | 1x |
| PEEK | peek_score_audit | 3 | 0 | 0 | 0 | 0.9x |
| PEEK | peek_singleton_audit | 3 | 3 | 2 | 0 | 1x |
| PEEK | lpm | 3 | 3 | 3 | 0 | 1.1x |

### Burst (200 extra sessions in 60 s at t = 5000 s, open arrivals at 2 x lambda_miss, horizon 30000 s, seeds 0-4)

| group | policy | trapped | recovered | tail hit rate | tail backlog |
|---|---|---|---|---|---|
| PEEK | fcfs | 5 / 5 | 0 / 5 | 0.000 | 823.4 |
| PEEK | peek_rank | 5 / 5 | 0 / 5 | 0.000 | 823.5 |
| PEEK | peek | 5 / 5 | 0 / 5 | 0.044 | 971.1 |
| PEEK | peek_order_audit | 3 / 5 | 0 / 5 | 0.182 | 709.1 |
| PEEK | peek_score_audit | 5 / 5 | 0 / 5 | 0.000 | 823.4 |
| PEEK | peek_singleton_audit | 3 / 5 | 0 / 5 | 0.189 | 708.5 |
| PEEK | lpm | 2 / 5 | 0 / 5 | 0.185 | 711.6 |
| Continuum pins | ttl5 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl5cw | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl5cwr | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl10 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl10e | 4 / 5 | 0 / 5 | 0.125 | 1101.5 |
| Continuum pins | ttl10ef | 5 / 5 | 0 / 5 | 0.144 | 1096.5 |
| Continuum pins | ttl10cw | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl10cwr | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl20 | 0 / 5 | 0 / 5 | 0.894 | 568.1 |
| Continuum pins | ttl20e | 5 / 5 | 0 / 5 | 0.134 | 1106.6 |
| Continuum pins | ttl20ef | 5 / 5 | 0 / 5 | 0.125 | 1101.4 |
| Continuum pins | ttl20cw | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| Continuum pins | ttl20cwr | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_cap | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_lpm | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_i5 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_i20 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_s8 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
| CONCUR | concur_s56 | 0 / 5 | 5 / 5 | 0.932 | 0.0 |
