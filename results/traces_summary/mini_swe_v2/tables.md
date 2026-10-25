## mini_swe_v2

### Tool time (seconds; wall time of the shell command(s) of one step in the SWE-bench container; 60 s timeout)

| series | n | mean (s) | median | p90 | p99 | CV | mean cap600 | CV cap600 | <1 s | >60 s | share of time >60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| phase_wall/all | 17,963 | 1.39 | 0.104 | 1.82 | 33.8 | 4.30 | 1.39 | 4.30 | 85% | 0.6% | 24% |
| phase_wall/claude-4-5-opus-high | 3,167 | 1.77 | 0.156 | 2.13 | 48.6 | 4.08 | 1.77 | 4.08 | 83% | 0.9% | 31% |
| phase_wall/claude-4-5-sonnet-high | 4,882 | 0.903 | 0.1 | 1.26 | 13.8 | 4.69 | 0.903 | 4.69 | 88% | 0.3% | 20% |
| phase_wall/gpt-5-2-high | 3,468 | 0.815 | 0.0838 | 1.42 | 12.8 | 4.19 | 0.815 | 4.19 | 88% | 0.1% | 4% |
| phase_wall/gpt-5-mini | 1,875 | 1.69 | 0.0686 | 3.11 | 36.3 | 3.80 | 1.69 | 3.80 | 85% | 0.5% | 17% |
| phase_wall/kimi-k2-5-high | 4,571 | 1.97 | 0.128 | 2.72 | 59.9 | 3.90 | 1.97 | 3.90 | 83% | 1.0% | 31% |
| phase_wall_uncensored/all | 17,862 | 1.06 | 0.103 | 1.69 | 20.8 | 3.84 | 1.06 | 3.84 | 86% | 0.0% | 0% |
| phase_wall_single_cmd/all | 16,861 | 1.43 | 0.0913 | 1.82 | 36.1 | 4.31 | 1.43 | 4.31 | 86% | 0.6% | 25% |
| llm_latency/all | 17,963 | 5.90 | 3.37 | 11.7 | 40.1 | 1.60 | 5.90 | 1.60 | 0% | 0.4% | 8% |

### Fits

| series (capped 600 s) | atom <10 ms | LN MLE mu / sigma (all) | KS | mean-preserving LN: mean, CV, KS | LN mu / sigma (positive part) | KS | mix comp 1: weight: median, sigma | mix comp 2 | KS mix | KS Exp(5 s) | KS Exp(mean-matched) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| phase_wall/all | 0.0% | -1.65 / 1.56 | 0.155 | 1.39 s, 5.83, 0.173 | -1.65 / 1.56 | 0.155 | 0.43: 0.0581 s, 0.20 | 0.57: 0.475 s, 1.52 | 0.058 | 0.692 | 0.496 |
| phase_wall/claude-4-5-opus-high | 0.0% | -1.42 / 1.59 | 0.134 | 1.77 s, 5.83, 0.145 | -1.42 / 1.59 | 0.134 | 0.31: 0.0576 s, 0.20 | 0.69: 0.46 s, 1.52 | 0.073 | 0.659 | 0.486 |
| phase_wall/claude-4-5-sonnet-high | 0.0% | -1.76 / 1.41 | 0.163 | 0.903 s, 4.23, 0.170 | -1.76 / 1.41 | 0.163 | 0.44: 0.0577 s, 0.20 | 0.56: 0.407 s, 1.36 | 0.063 | 0.721 | 0.435 |
| phase_wall/gpt-5-2-high | 0.0% | -1.83 / 1.40 | 0.184 | 0.815 s, 4.32, 0.185 | -1.83 / 1.40 | 0.184 | 0.49: 0.059 s, 0.20 | 0.51: 0.419 s, 1.39 | 0.046 | 0.725 | 0.454 |
| phase_wall/gpt-5-mini | 0.0% | -1.83 / 1.70 | 0.227 | 1.69 s, 9.53, 0.236 | -1.83 / 1.70 | 0.227 | 0.57: 0.0576 s, 0.20 | 0.43: 0.627 s, 1.85 | 0.067 | 0.718 | 0.623 |
| phase_wall/kimi-k2-5-high | 0.0% | -1.47 / 1.69 | 0.149 | 1.97 s, 7.06, 0.160 | -1.47 / 1.69 | 0.149 | 0.40: 0.0581 s, 0.20 | 0.60: 0.575 s, 1.61 | 0.068 | 0.660 | 0.523 |
| phase_wall_uncensored/all | 0.0% | -1.68 / 1.50 | 0.157 | 1.06 s, 4.81, 0.167 | -1.68 / 1.50 | 0.157 | 0.43: 0.058 s, 0.20 | 0.57: 0.453 s, 1.45 | 0.056 | 0.696 | 0.448 |

### Percentiles (seconds)

| series | p1 | p5 | p10 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| phase_wall/all | 0.0411 | 0.0477 | 0.0504 | 0.0572 | 0.104 | 0.427 | 1.82 | 5.14 | 33.8 |
| phase_wall/claude-4-5-opus-high | 0.0442 | 0.0491 | 0.0516 | 0.0609 | 0.156 | 0.57 | 2.13 | 5.46 | 48.6 |
| phase_wall/claude-4-5-sonnet-high | 0.0419 | 0.0482 | 0.0504 | 0.0566 | 0.1 | 0.366 | 1.26 | 3.31 | 13.8 |
| phase_wall/gpt-5-2-high | 0.0407 | 0.0471 | 0.0502 | 0.0567 | 0.0838 | 0.334 | 1.42 | 3.18 | 12.8 |
| phase_wall/gpt-5-mini | 0.0409 | 0.0464 | 0.0489 | 0.0542 | 0.0686 | 0.244 | 3.11 | 9.76 | 36.3 |
| phase_wall/kimi-k2-5-high | 0.0407 | 0.0474 | 0.0506 | 0.0583 | 0.128 | 0.513 | 2.72 | 7.94 | 59.9 |
| llm_latency/all | 1.11 | 1.42 | 1.76 | 2.47 | 3.37 | 5.79 | 11.7 | 17.5 | 40.1 |
| Exp(5 s) (current simulator) | 0.0503 | 0.256 | 0.527 | 1.44 | 3.47 | 6.93 | 11.5 | 15.0 | 23.0 |

### Tokens and turns (per trajectory = session)

| group | quantity | n | mean | mean (winsorised p99.9) | median | p90 | p99 | CV |
|---|---|---|---|---|---|---|---|---|
| all | first call prompt of a session (tokens) | 500 | 1,862 | 1,862 | 1,784 | 2,604 | 3,920 | 0.354 |
| all | prompt at every call (tokens) | 18,463 | 17,939 | 17,933 | 15,067 | 35,576 | 57,878 | 0.708 |
| all | output tokens per call | 18,463 | 271 | 269 | 116 | 659 | 2,110 | 1.67 |
| all | tokens appended between calls (delta_ctx >= 0) | 17,782 | 434 | 429 | 198 | 1,066 | 2,912 | 1.85 |
| all | model calls per agentic episode | 500 | 36.9 | 36.9 | 32.0 | 63.0 | 104 | 0.556 |
| claude-4-5-opus-high | first call prompt of a session (tokens) | 100 | 2,404 | 2,404 | 2,292 | 2,908 | 5,056 | 0.228 |
| claude-4-5-opus-high | prompt at every call (tokens) | 3,267 | 19,024 | 19,023 | 16,507 | 35,234 | 56,344 | 0.633 |
| claude-4-5-opus-high | output tokens per call | 3,267 | 293 | 292 | 161 | 667 | 1,816 | 1.23 |
| claude-4-5-opus-high | tokens appended between calls (delta_ctx >= 0) | 3,167 | 472 | 470 | 238 | 1,215 | 3,009 | 1.34 |
| claude-4-5-opus-high | model calls per agentic episode | 100 | 32.7 | 32.6 | 30.0 | 51.2 | 74.4 | 0.474 |
| claude-4-5-sonnet-high | first call prompt of a session (tokens) | 100 | 2,404 | 2,404 | 2,292 | 2,908 | 5,056 | 0.228 |
| claude-4-5-sonnet-high | prompt at every call (tokens) | 4,982 | 21,443 | 21,441 | 18,892 | 40,034 | 63,877 | 0.638 |
| claude-4-5-sonnet-high | output tokens per call | 4,982 | 295 | 295 | 127 | 764 | 1,922 | 1.31 |
| claude-4-5-sonnet-high | tokens appended between calls (delta_ctx >= 0) | 4,882 | 376 | 375 | 215 | 927 | 2,779 | 1.30 |
| claude-4-5-sonnet-high | model calls per agentic episode | 100 | 49.8 | 49.8 | 46.0 | 74.2 | 108 | 0.384 |
| gpt-5-2-high | first call prompt of a session (tokens) | 100 | 1,504 | 1,504 | 1,406 | 1,942 | 3,482 | 0.299 |
| gpt-5-2-high | prompt at every call (tokens) | 3,568 | 18,097 | 18,095 | 14,746 | 38,807 | 58,657 | 0.773 |
| gpt-5-2-high | output tokens per call | 3,568 | 370 | 368 | 121 | 905 | 3,736 | 1.99 |
| gpt-5-2-high | tokens appended between calls (delta_ctx >= 0) | 3,467 | 334 | 333 | 90.0 | 914 | 2,179 | 1.48 |
| gpt-5-2-high | model calls per agentic episode | 100 | 35.7 | 35.7 | 30.5 | 60.2 | 102 | 0.516 |
| gpt-5-mini | first call prompt of a session (tokens) | 100 | 1,504 | 1,504 | 1,406 | 1,942 | 3,482 | 0.299 |
| gpt-5-mini | prompt at every call (tokens) | 1,975 | 12,558 | 12,557 | 11,321 | 23,721 | 38,622 | 0.667 |
| gpt-5-mini | output tokens per call | 1,975 | 209 | 209 | 93.0 | 491 | 1,440 | 1.56 |
| gpt-5-mini | tokens appended between calls (delta_ctx >= 0) | 1,850 | 662 | 661 | 278 | 2,078 | 2,706 | 1.20 |
| gpt-5-mini | model calls per agentic episode | 100 | 19.8 | 19.7 | 17.5 | 28.2 | 44.1 | 0.413 |
| kimi-k2-5-high | first call prompt of a session (tokens) | 100 | 1,495 | 1,494 | 1,400 | 1,916 | 3,450 | 0.295 |
| kimi-k2-5-high | prompt at every call (tokens) | 4,671 | 15,598 | 15,597 | 12,893 | 31,593 | 50,958 | 0.719 |
| kimi-k2-5-high | output tokens per call | 4,671 | 180 | 179 | 68.0 | 479 | 1,341 | 1.58 |
| kimi-k2-5-high | tokens appended between calls (delta_ctx >= 0) | 4,416 | 455 | 454 | 185 | 839 | 5,157 | 2.73 |
| kimi-k2-5-high | model calls per agentic episode | 100 | 46.7 | 46.7 | 42.5 | 69.9 | 119 | 0.494 |

Exit status: {'Submitted': 500}; format-error retries: 0; commands hitting the 60 s limit: 101

