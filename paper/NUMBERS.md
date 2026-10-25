# Numbers in the paper and where each comes from

One row per number in `paper/main.tex` and `paper/sections/*.tex` (abstract, body, figure and table captions, appendix). A value used in several places has one row that lists every place. "Where" uses section numbers of the built PDF (Abs = abstract, F = figure caption, T = table, A-D = appendices). "Derived" means arithmetic on committed values; the arithmetic is given. Paths are relative to the repository root. Commits are on `main` (or its ancestors) unless noted; job IDs are SLURM IDs on Nova. Results still running, or planned and not yet submitted, are not numbers in the paper: they appear only as `\pending{...}` (listed at the end).

Short names for the sources used most often:

| Key | Path | Commit | Jobs |
|---|---|---|---|
| SC | `results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv` | d0235a7 | 17062103-05 |
| SCV | `results/nova/stageC_1706210x_pulled_20261022-125454/verification/` (`review/review_calc_log.txt`, `recompute/bins.csv`, `artifact/s2_metrics_out.csv`) and `notes/STAGEC_VERIFICATION.md` | d0235a7, 155c7af | 17062103-05 |
| E0A | `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/{calibration.json, lambda_miss_runs.csv}` | a76f5e5 | 17072634-36 |
| E0A64 | `results/nova/e0a_1707263x_pulled_20261023-142037/agentload_analysis_miss/20261022-163440/lambda_miss_runs.csv` | a76f5e5 | 17072637 |
| E0B | `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/{stable_runs.csv, lambda_cap_bracket.json}` | cfbc702 | 17084750-55 |
| REG | `configs/agentload_prereg_2026-10-24.yaml` | d279b7b | - |
| E2 | `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/{trap_v2_runs.csv, kill_verdict_v2.json}` | 49fbc7b | 17093387-404 |
| F1R | `paper/figs/README.md` (F1 section; computed by `figures/paper/fig1_e2_timeseries.py` from the E2 run dirs) | e098e1c, c974070 | 17093387-404 |
| NAT | `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv` | fa265c2 | 17096856-57 |
| NATM | `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json` | fa265c2 | 17096858 |
| NATLOG | `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/nova_job_logs/17096856-20261025-022855/server.log` (`max_total_num_tokens=955757`) | fa265c2 | 17096856 |
| GRID | `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/{20261025-144230, 20261025-144233, 20261025-144236}/trap_v2_runs.csv` | fa265c2 | 17097086-103 |
| WL | `configs/agentload_e2_burst.yaml` (workload, arrivals, canary sections) | 4cb8c01 | - |
| LOG | `notes/LOG.md` (entry named in the row) | beb60dc | - |
| CAL | `calibration/round6_server_log_fit/CALIBRATION_REPORT.md` and `calibration.yaml` | 4435c51 | logs of 17060165, 17062103-05 |
| VAL | `calibration/round6_server_log_fit/VALIDATION.md`; `results/r6_validate_stagec/20261024-025222/` | 813cfc1 | - |
| PRED | `notes/PREDICTIONS.md`; `results/r6_predict_report/20261024-034707/` (`b2_table.csv`, `b2_supp20_table.csv`, `b3_verdicts.csv`, `b4_landmarks.csv`) | 64bc4e3 | - |
| VER | `notes/PREDICTIONS_VERIFICATION.md` | 877b936 | - |
| R7 | `notes/ROBUSTNESS_r7.md`; `results/r7_report/20261024-233554/` | c653498 | - |
| R7T | `notes/ROBUSTNESS_r7_traces.md`; `results/r7_traces_sim/r7_report/20261025-012451/`, `results/r7_traces_sim_adj/r7_report/20261025-012453/` | b530e55 | - |
| TR | `notes/lit/AGENT_TRACES.md` (from `results/traces_summary/`) | 1556630 | - |
| AUD | `notes/BASELINES_AUDIT.md`; `results/prefix_meta_baselines_audit_summary/20261025-001850/{curve_baselines_audit_s10.csv, curve_baselines_audit_deadkv.csv, meta.json, tables.md}` | 3ce37c9, dc76032 | - |
| R4 | `results/prefix_meta_r4_curve/20261021-050856/curve_runs.csv`; `results/prefix_meta_r4/20261021-051550/prediction_eval.csv` | a1d485b | - |
| CIT | `notes/lit/CITATION_AUDIT_2026-10-25.md` | f0e2e19 | - |
| TRAP | `results/agentload_trap_sim_traces/20261021-070449/summary_by_lambda.csv` | 8452338 | - |
| DER | `paper/derived/{e2_burst_backlog.csv, e2_capped_drain.csv, e0b_hit.csv, e2_counts.csv}`, written read-only from the E2 and E0b run data (and REG) by `figures/paper/derived_numbers.py` | 38bf22b (r8/paper) | 17093387-404; 17084750-55 |
| RB | `notes/E2_RUNBOOK.md` as committed in 288b801 (Stage 3 items 4-5: rate rule and proposed cap n=20) | 288b801 | - |

## Setup, engine and workload

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 0.5.22 | Abs, 1, 2, 4.1, 10, A | SGLang version | LOG (2026-10-21, Nova setup: ENV_SGLANG); `results/nova/s0_smoke_17060165_pulled_20261021-152347/` | d0235a7; 17059856, 17060165 |
| 0.32.0 | 2, 5.6 | vLLM version | `results/nova/r7_native_grid_vllm_pulled_20261025-145126/envs/vllm.lock.txt` | fa265c2; 17097972 |
| Qwen2.5-7B-Instruct, rev. a09a3545 | Abs, 1, 4.1, 10, A | model and revision | LOG (Nova setup); CAL (`calibration.yaml` engine line) | d0235a7, 4435c51 |
| A100 80GB PCIe, 81,920 MiB | Abs, 1, 4.1, 10, A, B | GPU | E0A `calibration.json` (`hardware`); REG (`hardware`) | a76f5e5, d279b7b |
| 580.178.04 | A | GPU driver | LOG (Stage 0 entry, item (j)) | 17060165 |
| 300,000 / 300k tokens | Abs, 1, 4.1, 5.1, 5.6, 8, 10, F2-F6, A | KV pool cap | LOG (Stage 0: pool allocated at exactly 300,000); CAL (`max_total_tokens 300000`) | 17060165 |
| 955,757 tokens | Abs (implicit), 1, 4.1, 5.1, 8, F2, A | native pool sized by SGLang | NATLOG | fa265c2; 17096856 |
| 3.19 | 5.1 | native pool / cap | derived: 955,757 / 300,000 = 3.186 | - |
| 8192 | 4.1, 4.4, A | chunked prefill tokens (engine and simulator) | CAL (`chunked_prefill_size 8192`; `prefill_chunk_budget: 8192`) | 4435c51 |
| 256 | 4.1, 4.4, A | max running requests / sequences | CAL (`max_running_requests 256`; `max_running_seqs: 256`) | 4435c51 |
| 49,152 | A | context limit | LOG (Stage 0 attempt 2); `notes/STAGEC_VERIFICATION.md` caveat 4 | 17060022, 17060165 |
| 2000 | 1 (via 9,600), 3.1, A | first prompt L0 (tokens) | WL (`initial_context_tokens: 2000`) | 4cb8c01 |
| 550 | 3.1, 4.1, 10 (fixed tool outputs), A | tool tokens appended per turn | WL (`new_prompt_tokens: 550`) | 4cb8c01 |
| 100 | 3.1, 4.1, A | decoded tokens per turn | WL (`decode_tokens: 100`) | 4cb8c01 |
| 1/15, 60 | 3.1, A | turns: min(Geometric(1/15), 60) | WL (`mean_turns: 15`, `max_turns: 60`) | 4cb8c01 |
| 14.761 | 3.1, A, 8 (E[T]) | E[T] | E0A `lambda_miss_runs.csv` (`effective_mean_turns` 14.761055); SCV `review_calc_log.txt` | a76f5e5 |
| 5 s | Abs (implicit), 1, 3.1, 7, 10, A | tool time Exp mean 5 s | WL (`tool_time_mean_s: 5.0`, `tool_time_dist: exp`) | 4cb8c01 |
| 650 | A | prompt growth per turn (2000 + 650(k-1)) | derived: 550 + 100; LOG (E0a entry: "Prompt length is exactly 2000 + 650(k-1)") | a76f5e5 |
| 551 | 1, 3.1 | tokens prefilled by a hit (cached = prompt - 551) | SCV (`notes/STAGEC_VERIFICATION.md`, check 2: "Cached is always prompt - 551") | 155c7af |
| 0.93 | 3.1, 10 (93%) | hit-fraction ceiling 1 - 1/E[T]; good-state hit fraction | derived: 1 - 1/14.761 = 0.932; observed: SC hit 0.932 (n=16); E2 NOBURST 0.921-0.934 | d0235a7, 49fbc7b |
| 91-93% | 1, 5.2 | E0b hit fraction over the whole 3000 s run at 1.25, 1.5, 1.75, 2.0 x lambda_ref (from empty) | DER `e0b_hit.csv` (`hit_whole_run` 0.9325, 0.9324, 0.9281, 0.9149) | 38bf22b; 17084750-55 |
| 2000T + 325T(T-1) | 3.1 | all-miss prefill work per session | LOG (E0a entry); derived: sum over k of 2000 + 650(k-1) | a76f5e5 |
| 154,529 | 3.1 | E[W], all-miss tokens per session | SCV `review_calc_log.txt` (`tok_allmiss=154529`); LOG (E0a) | d0235a7 |
| 9,600 | 3.1 | all-hit prefill tokens per session (2000 + 551(T-1)) | SCV `review_calc_log.txt` (`tok_allhit=9582`) | d0235a7 |
| 16 | 1 | all-miss / all-hit prefill per session | SCV `review_calc_log.txt` (`ratio=16.1`) | d0235a7 |
| 10,500 | 1 | mean miss prompt per turn | derived: E[W]/E[T] = 154,529 / 14.761 = 10,469 | - |
| 10.6k | 3.2 | length-biased footprint E_lb | SCV `review_calc_log.txt` (`mean live footprint=10568`); `notes/MATHCHECK_thrashing_curve.md` s3 (10,569) | d0235a7, 4e64a0d |
| 28.4 | 3.2, 5.1, 7 (c = 28 = N_lb) | N_lb = M / E_lb | SCV `review_calc_log.txt` (`n_fit=28.4`) | d0235a7 |
| 1024, 1023, 15, 0 | 4.1, A | canary size, reuse before flush, allowed after, observed after | WL (`canary.tokens: 1024`, `max_cached_after_flush: 15`); `notes/STAGEC_VERIFICATION.md` (canaries 1023 then 0); LOG (Stage 0, item h) | 4cb8c01, 155c7af |
| 63 of 64 | A | Stage 0 repeated-prompt cache check | LOG (Stage 0 table, item b) | 17060165 |
| 40,350 | A | longest context accepted in Stage 0 | LOG (Stage 0 table, item e) | 17060165 |
| 3191, 0 | A | requests checked for prompt-length agreement, mismatches | LOG (Stage 0 table, item g) | 17060165 |

## Model (Section 3)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 20.5 vs 40 | 3.3 | fluid critical burst n2 - n1 vs empirical critical burst at 2 lambda_miss (round-4 simulator) | R4 `prediction_eval.csv` row R3 (`b_c` 20.487, `b_emp` 40) | a1d485b |
| 2 (x lambda_miss) | 3.3 | rate of that comparison | R4 `prediction_eval.csv` row R3 | a1d485b |
| 1571 s, 1889 s | 3.4, 5.3, B | predicted CAPPED drain times at 1.35 and 1.65 x lambda_ref | REG (`predicted_drain_s_by_mult`: 1570.9, 1889.4) | d279b7b |
| 0.919 | 3.4, 7 | FCFS-order hard pin of queued prefixes (earlier simulator), below lambda_miss | AUD (`peek` 0.919295) | dc76032 |

## Methodology (Section 4)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 200, 60 s, 1200 s | Abs, 1, 4.1, 5.3, F1, A, B | burst size, width, time | REG (`protocol`); WL (`burst: {n: 200, t_s: 1200, width_s: 60}`) | d279b7b |
| 900 s, 1800 s | 4.2, 5.2, A | Stage C / E0a warmup and measured window | `configs/agentload_c_closed.yaml` (warmup 900, measured 1800); `configs/agentload_e0_miss.yaml`; LOG (Stage C, E0a) | c63ae2c, 1a70a40 |
| 0.0715 (lambda_ref) | Abs, 4.2, 5.1, 5.2, F1, F3, T2, B | E0a turns-based lambda_miss | E0A `calibration.json` (`lambda_miss_turns_based` 0.071534) | a76f5e5 |
| 3000 s | 4.2, 5.2, 6, 10, F3, A | E0b run length (from-empty horizon) | LOG (E0b entry); E0B run dirs | cfbc702 |
| 50, 10, 1500 s | 4.2, A | E0b stability rule: final queue < 50, rise <= 10 over last 1500 s | `notes/PREDICTIONS.md` s3 item 7 (rule shared with B2); `notes/E2_RUNBOOK.md` Stage 2; E0B | 64bc4e3, cfbc702 |
| 8700 s, 4500 s, 7500 s | Abs, 1, 4.3, 5.3, 6, 10, A, B | E2 run length, evaluation start after the burst, time after the burst | REG (`duration_s: 8700`, `eval_from_s: 4500`); 8700 - 1200 = 7500 | d279b7b |
| 5700 s | F1, T1 (window), A | evaluation window start (1200 + 4500) | E2 `trap_v2_runs.csv` (`eval_from` 5700) | 49fbc7b |
| +-15% | 4.3, A (T5) | trap rate tolerance | REG (`rate_tolerance: 0.15`) | d279b7b |
| 11,243 tokens/s | 4.3, 5.1, 5.2, T2, A, B | E0a all-miss uncached prefill rate | E0A `calibration.json` (`all_miss_uncached_tokens_per_s` 11243.18) | a76f5e5 |
| 0.5 | 4.3, 5.4, 6, A | slope fraction | REG (`slope_frac: 0.5`) | d279b7b |
| 300 s, 0.8, 20 | 4.3, A | RECOVERED: last 300 s, hit > 0.8, outstanding < 20 | REG (`end_window_s: 300`, `recovered_hit_above: 0.8`, `recovered_backlog_below: 20`) | d279b7b |
| two of three seeds | 4.3, A | pass fraction | REG (`pass_fraction_min: 0.667`, `min_seeds: 3`) | d279b7b |
| 600 s, 10 s | A | minimum window, slope bin | REG (`min_eval_s: 600`, `slope_dt_s: 10`) | d279b7b |
| 1 of 29, 0 of 39, 84, 1.5-2.5 | 4.3 | session-rate test fires on at most 1 of 29 traps at 2x and 0 of 39 at 2.5x; token test fires on all 84 (16 + 29 + 39) | TRAP (`a_fires_sessions` 0.0345 / 0 at 2.0, 0 at 2.5; `a_fires_tokens` 1.0; `n_trapped_runs` 16, 29, 39) | 8452338 |
| (1, 2.0) | 4.3, 5.2, B | registered window in multiples of lambda_ref | REG (`metastable_window: lo_mult 1.0, hi_mult 2.0`) | d279b7b |
| 288b801, 2026-10-22, 13:13 CDT | 4.3, B, C (T6) | commit that put the rate rule and the cap n=20 in the runbook, before E0b was submitted (2026-10-23 ~14:40) | `git log --format=%ci 288b801` (2026-10-22 13:13:19 -0500); RB | 288b801 |
| 3.26 | 4.3, 5.1, 5.2, 8 (as 31%) | mu*/lambda_ref at 300k | derived: 0.23333 / 0.071534 = 3.262; REG `lambda_selection.rule` ("mu_max/lambda_ref = 3.26") | d279b7b |
| 1/3, 2/3, 0.05 | 4.3, B | rate rule and rounding | REG (`lambda_selection.rule`) | d279b7b |
| 1.35, 1.65 | Abs, 1, 4.3, 5.3, 5.5, 6, F1, F4, T1, B | registered multiples of lambda_ref | REG (`lambda_mults`) | d279b7b |
| 0.0966, 0.1180 | 4.3, T2 | registered rates (sessions/s) | REG; E2 `trap_v2_runs.csv` (`lambda` 0.096571, 0.118031) | d279b7b, 49fbc7b |
| 0.95 | 4.3 | cap rule: smallest n with mu(n) >= 0.95 mu* | REG (`n_cap_rule`) | d279b7b |
| 20 | Abs, 1, 4.3, 5.3 (via cap), 6, 7, 8, F2, F4, A, B | registered cap n_cap | REG (`n_cap: 20`) | d279b7b |
| 0.224, 0.233, 4% | 4.3, 5.1, Abs (0.233) | mu(20), mu(24) at 300k and their gap | SC (0.22389, 0.23333); REG (`n_cap_ambiguous` message: within 0.0405) | d0235a7, d279b7b |
| d279b7b | 4.3, B, C | registration commit | `git log` | d279b7b |
| 5 (parameters) | 4.4 | fitted cost parameters | CAL (fit table: iter_fixed_s, iter_floor_s, per_token_s, decode_attn_s, prefill_attn_s) | 4435c51 |
| 0.992, 0.75%; 0.998, 1.3% | 4.4 | decode R^2 and median error; prefill R^2 and median error | CAL ("Fit quality") | 4435c51 |
| 15%, 8 cells | 4.4 | declared level test | VAL s2 (`level_rel_tol: 0.15`; 8 judged cells) | 813cfc1 |
| 7 of 8 (missed one), 6 of 8 (two) | 4.4 | cells within 15%: mixed, separate | VAL s0 item 1 | 813cfc1 |
| +42%, 0.070 vs 0.049 | 4.4 | FCFS n=48: simulator vs real | VAL s3 table (+42.4%; 0.070 vs 0.049) | 813cfc1 |
| 32.5 vs 32.2 | 4.4, 5.1 (32.2) | 0.5-hit crossing, simulator (mixed) vs real | VAL s5 | 813cfc1 |
| 9.2%, 2% | 4.4 | plateau (largest error 9.13%, mixed n=24) and n=300 agreement | VER ("within 9.2%", actual 9.1266%); `results/r6_validate_stagec/20261024-025222/cell_table.csv` (mixed fcfs n=24: 0.21204 vs 0.23333); VAL s0 item 1 (n=300 within 2%) | 877b936, 813cfc1 |
| 0.104 vs 0.127; one cell | 4.4 | pre-declared mode-choice metric (mean relative error of mu, mixed vs separate); margin carried by LPM(128) n=48 | VAL s0 item 2 | 813cfc1 |
| 0.50 vs 0.46 | 4.4 | mu(300)/mu*, simulator vs real | VAL s5 (0.500 vs 0.462) | 813cfc1 |
| 0.063 | 4.4 | real turns-based mu(48) | SC (`mu_turns_based` 0.062928) | d0235a7 |
| 0.09-0.16 | 4.4, T2 | B3 rate grid (sessions/s) | PRED s0 B3 | 64bc4e3 |
| 600k, 900k | 4.4, F2, T2 | B4 simulated pools | PRED s0 B4 | 64bc4e3 |
| 64bc4e3 | 4.4, C | prediction commit | `git log` | 64bc4e3 |
| 0.0474 | 4.4, 7, F6 | all-miss capacity of the earlier simulator | AUD `meta.json` (`lambda_miss` 0.047419) | dc76032 |
| 1-5; round 5 | 4.4, 5.5 | earlier simulator rounds; round 5 (allocation variants, `lpm128` fallback: LPM advantage about 0 in congestion) | LOG (round entries 2026-10-21; round-5 entry: "`lpm128` ... the LPM advantage is about 0 with hit rate 0") | beb60dc |

## Results on the real engine (Section 5)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 0.176, 0.224, 0.233 | 5.1 (Abs: 0.233) | mu(16), mu(20), mu(24) sessions/s, 300k | SC (`mu_sessions` 0.17555, 0.22389, 0.23333) | d0235a7; 17062103 |
| 20-24 | Abs, 5.1 | location of the 300k peak | SC (argmax 24, n=20 within 4%) | d0235a7 |
| 0.93, 0.93, 0.89 | 5.1 | hit fraction at n=16, 20, 24 | SC (`hit_frac_turns` 0.932, 0.927, 0.888) | d0235a7 |
| 450 s, 2400 s, 0.80, 0.51 | 5.1 | n=32 degraded episode, recovered hit, window hit | SCV `notes/STAGEC_VERIFICATION.md` (F32: degraded since ~450 s, recovers ~2400 s); `recompute/bins.csv` (last bin 0.803); SC (0.505) | d0235a7 |
| 48 | Abs, 5.1 | n at which no turn hits | SC (`hit_frac_turns` 0.0 at n=48) | d0235a7; 17062104 |
| 20.0M | 5.1 | prompt tokens in the n=48 window, none cached | SCV `artifact/s2_metrics_out.csv` (`d_prompt` 20,021,050; `d_cached` 0) | d0235a7 |
| 6.3 s vs 30.6 s; 2.9 s vs 66 s | 5.1 | evictable-token survival (ratio of means: mean kv_evictable / eviction rate) vs reuse gap, n=48 and n=96 | SCV (`notes/STAGEC_VERIFICATION.md`, mechanism table and "rough check, a ratio of means") | 155c7af |
| 0.049, 0.061, 0.108 | 5.1, 8 (0.108), B (4 decimals) | mu(48), mu(96), mu(300), 300k | SC (0.048888, 0.061111, 0.107776) | d0235a7 |
| 71% | 5.1 | in-flight prompt length at n=300 vs stationary | SCV (`notes/STAGEC_VERIFICATION.md` line 58) | 155c7af |
| 0.072-0.081 | 5.1 | throughput-implied all-miss level | SCV `review_calc_log.txt` (`mu_allmiss_proj` 0.0720-0.0807) | d0235a7 |
| threefold | 5.1 | collapse from the peak | derived: 0.233 / (0.072-0.081) = 2.9-3.2; LOG (Stage C "about 3x") | - |
| 39%, 0.087, 0.28 -> 0.44 | 5.1 | LPM n=48 hit fraction, mu, within-window hit by 300 s bin | SC (`hit_frac_turns` 0.385, `mu_sessions` 0.0867); SCV `recompute/bins.csv` (0.283 ... 0.440) | d0235a7; 17062105 |
| 269, 128 | 5.1 | LPM n=300 mean waiting queue; SGLang fallback threshold | SC (`queue_mean` 269.0); CIT (SGLang v0.5.22 row: `WAITING_QUEUE_PREFIX_MATCH_MAX = 128`) | d0235a7, f0e2e19 |
| 0.479 (n=64), 0.477 (n=80) | Abs (threefold), 5.1, T2 | native peak | NAT (`mu_sessions` 0.47889, 0.47722) | fa265c2; 17096856 |
| 92-93% | 5.1 | native hit fraction n <= 80 | NAT (0.929, 0.929, 0.930, 0.922) | fa265c2 |
| 0.123 (0.42), 0.067 (0.007), 0.101 | 5.1, 5.4, T2 | native mu (hit) at n=96, 128, 300 | NAT (0.12278/0.4189, 0.06667/0.0072, 0.10055) | fa265c2; 17096857 |
| 0.92 (n=80), 0.42 (n=96) | 5.1 | native hit fraction on either side of the 0.5 crossing | NAT (`hit_frac_turns` 0.922, 0.4189) | fa265c2 |
| 93 | 5.1, T2 | native 0.5-hit crossing | derived: linear interpolation between n=80 (0.922) and 96 (0.419): 80 + 16 (0.922-0.5)/(0.922-0.419) = 93.4 | fa265c2 |
| just above 32 | 5.1 | 300k 0.5-hit crossing (32.2 by interpolation; hit 0.505 at n=32, 0 at n=48) | SC; VAL s5 (32.2) | d0235a7, 813cfc1 |
| roughly threefold | Abs, 1, 5.1 | outward shift of the cliff | derived: crossing in (80, 96) vs 32.2, ratio 2.5-3.0; peak 64-80 vs 20-24, about 3x; pool ratio 3.19; one run per n | - |
| 0.0718 +- 0.0037, 11,282 +- 51 | Abs ("within its standard error"), 1, 5.1 | native lambda_miss (turns-based), all-miss tokens/s, SE over seeds | NATM (`lambda_miss_turns_based` 0.071797, `_se` 0.003703; `all_miss_uncached_tokens_per_s` 11282.0, `_se` 50.79) | fa265c2; 17096858 |
| 6.7 | 5.1, 5.6 | native mu*/lambda_miss | derived: 0.47889 / 0.071797 = 6.67 | - |
| 0.0715 +- 0.0038; 0.0717 +- 0.0076; 11,243 +- 84 | 5.1, 5.2 | E0a turns-based, sessions-based, tokens (SE over 3 seeds) | E0A `calibration.json` | a76f5e5 |
| +-1.2%, +-17% | 5.2 | seed spread of token rate and session rate (half-range / mean) | derived from E0A `lambda_miss_runs.csv`: tokens (11342.0-11075.7)/2/11243 = 1.18%; sessions (0.08167-0.05667)/2/0.07167 = 17.4%; LOG (E0a) | a76f5e5 |
| 0.0728, 2% | 5.2 | token rate / E[W]; agreement with turns-based | derived: 11,243 / 154,529 = 0.07276; LOG (E0a) | - |
| 1.25, 1.5, 1.75, 2.0, 2.5, 3.0 | 1 (1.25 and 2), 5.2, A | E0b rates (x lambda_ref) | E0B `stable_runs.csv` | cfbc702 |
| 127, 146; 289, 196 | 5.2 | E0b final queue and rise at 2.5x and 3.0x | E0B `stable_runs.csv` (127.0/146.2; 288.55/196.2) | cfbc702; 17084751, 17084754-55 |
| 2.0 / 2.5 edge | Abs, 1, 5.2, 10, 11, B | largest all-stable / first unstable multiple | E0B `lambda_cap_bracket.json` | cfbc702 |
| 0.934, 0.903; [300, 1500) s | 5.2 | E0b hit fraction at 2.0 x in [300, 1500) s and [1500, 3000) s | DER `e0b_hit.csv` (0.93371, 0.90325) | 38bf22b; 17084753 |
| (0.0715, 0.143), 0.1431 | 5.2, B | registered window in sessions/s | REG (`metastable_window.hi` 0.143068) | d279b7b |
| 18 | 5.3 | runs in the verdict | E2 (`trap_v2_runs.csv`, 18 rows) | 49fbc7b; 17093387-404 |
| T I T / T T T; G G G; R R R | T1, 5.3, Abs (5 of 6, 6 of 6) | per-seed states | E2 `trap_v2_runs.csv` (`state`); `kill_verdict_v2.json` (`kill_test_pass_decisive: true`) | 49fbc7b |
| 0.000 | Abs (zero hits), 1, 5.3, T1 | BURST hit fraction over the window | E2 (`hit_eval` 0.0 for all 6 BURST rows) | 49fbc7b |
| 1.009-1.029 (1.009-1.025; 1.025-1.029) | 5.3, T1, T2 | BURST uncached token rate / all-miss | E2 (`rate_uncached_tokens` / 11243.18: 1.0250, 1.0092, 1.0191; 1.0252, 1.0294, 1.0256) | 49fbc7b |
| 200-332 (200-232; 283-332) | 5.3, T1 | BURST mean backlog (sessions in system) | E2 (`backlog_eval_mean` 232.2, 199.7, 221.4; 331.8, 282.7, 311.0) | 49fbc7b |
| 0.0036-0.0222; 0.0277-0.0362 | T1 | BURST backlog slopes | E2 (`backlog_slope` 0.02222, 0.00360, 0.01861; 0.03201, 0.02766, 0.03621) | 49fbc7b |
| 0.0125, 0.0232 | T1 | slope thresholds 0.5(lambda - lambda_miss) | E2 (`slope_threshold` 0.012518, 0.023249) | 49fbc7b |
| 0.0036 | 5.3 | indeterminate run's slope (1.35x, seed 1) | E2 (0.003596) | 49fbc7b; 17093393 |
| 207, 206 (near 206) | Abs, 1, 5.3 | indeterminate run's backlog at the start and end of the evaluation window | E2 (`backlog_eval_start` 207.0, `backlog_end` 205.68); DER `e2_burst_backlog.csv` (first 300 s 206.8, last 300 s 205.7) | 49fbc7b, 38bf22b |
| [0.61, 1.00]; [0.44, 0.97]; 6 of 6, p = 1/64 | 5.3 | Wilson 95% intervals for 6/6 and 5/6; one-sided sign test over the 6 seed-and-rate pairs (BURST hit < NOBURST hit) | DER `e2_counts.csv` (0.6097-1.0; 0.4365-0.9699; p 0.015625) | 38bf22b |
| 135-172; 300-1300 s | 5.3, F1 README | BURST backlog minimum after the burst and its time after the burst | DER `e2_burst_backlog.csv` (`backlog_min_after_burst` 146.7, 146.8, 135.2, 172.1, 170.4, 162.4; `t_min_after_burst_s` 1050, 1300, 900, 300, 1200, 900) | 38bf22b |
| five ... growing, sixth flat | Abs, 1, 5.3 | BURST backlog over the window | E2 (`state`, `backlog_slope`); DER `e2_burst_backlog.csv` | 49fbc7b, 38bf22b |
| 0.081-0.097 | 5.3 | BURST session completion rate over the window (above lambda_miss 0.0715, below lambda 0.0966 / 0.1180) | E2 (`rate_sessions` 0.0810, 0.0913, 0.0840; 0.0897, 0.0967, 0.0960) | 49fbc7b |
| 1547-1904 s; 2021-2693 s; 2% shorter to 43% longer | 5.3, 10 (43%) | time after the burst at which the CAPPED gate queue first empties, 1.35x and 1.65x; ratio to the fluid estimate | DER `e2_capped_drain.csv` (1546.7, 1846.7, 1904.1; 2693.2, 2020.6, 2127.1; ratio 0.985-1.425) | 38bf22b; 17093389, 92, 95, 98, 401, 404 |
| 0.921-0.934 (0.930-0.934; 0.921-0.934; 0.929-0.934) | 5.3, T1, T2 | NOBURST / CAPPED hit fraction | E2 (`hit_eval`) | 49fbc7b |
| 0.08-0.09; 0.10-0.13; 0.10-0.11 | T1 | NOBURST / CAPPED token rate / all-miss | E2 (1 + `rate_rel_dev_tokens`: 0.087, 0.075, 0.091; 0.108, 0.101, 0.126; 0.108, 0.101, 0.112) | 49fbc7b |
| 8-12 (7.9-9.7; 10.9-11.8; 10.9-11.7) | 5.3, T1, A | NOBURST / CAPPED mean backlog | E2 (`backlog_eval_mean` 9.22, 7.91, 9.66 / 9.24, 7.90, 9.66; 11.56, 10.92, 11.83 / 11.54, 10.93, 11.69) | 49fbc7b |
| < 0.001, < 0.002 | T1 | NOBURST / CAPPED slopes | E2 (`backlog_slope` between -0.00047 and 0.00107) | 49fbc7b |
| 1300 s; 100 s after the burst | Abs, 1, 5.3 | first all-zero-hit 100 s window of every BURST run (1300 - 1200 = 100 s after the burst) | F1R ("from the 100 s window starting at 1300 s") | c974070 |
| 206-369 | 5.3 | BURST backlog over the last 300 s | F1R; DER `e2_burst_backlog.csv` (`backlog_eval_last300` 205.7-369.4) | c974070, 38bf22b |
| 0.48-0.77 in 4 of 6; 0.82-0.89 | 5.3 | lowest 100 s CAPPED hit window during the drain; NOBURST minimum | F1R (0.76, 0.63, 0.77, 0.48; NOBURST 0.82-0.89) | c974070 |
| 100 s | F1, 5.3, 6 | window length of the hit series | F1R | c974070 |
| four decimals | F1 | agreement of recomputed hit with registered `hit_eval` | F1R | c974070 |
| order of magnitude; about 20 times | 5.3, 8 | 200 burst sessions vs 8-12 in the good state | derived: 200 / 12 = 17, 200 / 10 = 20 | - |
| 0.0722, 11,220, 0.0694 | 4 (F3: 0.0722), T2 | B1 predictions (turns-based, tokens/s, sessions/s; mixed) | PRED s0 B1 | 64bc4e3 |
| +0.9%, -0.2%, -3.2%; 3.2% | T2, 5.4 | B1 errors | derived: 0.0722/0.0715 - 1; 11220/11243 - 1; 0.0694/0.0717 - 1; LOG (E0b entry) | - |
| 0.14 (3 seeds), 0.15 (20 seeds) | T2, 5.4 | B2 all-stable edge | PRED s0 B2 | 64bc4e3 |
| [0.143, 0.179) | T2, 5.4 | real edge in sessions/s (2.0x and 2.5x lambda_ref) | LOG (E0b table: 0.1431, 0.1788); E0B run `meta.json` (`resolved_rate_sessions_per_s`) | cfbc702 |
| 2/3 (15/20) at 0.18 | T2, 5.4 | B2 stable fraction at 0.18 | PRED s0 B2 table and supplement | 64bc4e3 |
| PASS at 0.09-0.16 | T2, 5.4 | B3 | PRED s0 B3 | 64bc4e3 |
| 0.999-1.065 | T2 | B3 trapped token ratio | PRED s0 B3 | 64bc4e3 |
| 171-523 | T2 | B3 trapped backlog (waiting requests) | PRED s0 B3 | 64bc4e3 |
| 194-325 | T2 | real BURST outstanding backlog (requests) | E2 (`outstanding_eval_mean` 226.3, 194.3, 215.5, 325.5, 276.7, 304.5) | 49fbc7b |
| 0.929-0.937 | T2 | B3 good-arm hit | PRED s0 B3 | 64bc4e3 |
| 3/3 at 0.09 and 0.10; 14/20, 18/20; 10-30% | T2, 5.4 | B3 BURST trapped at 0.09 and 0.10: registered 3 seeds; 20-seed supplement; share not certified trapped (6/20, 2/20) | PRED s0 B3 table (mixed 3, 3); `results/r6_predict_report/20261024-034707/b3_supp20_verdicts.csv` (mixed 0.09: 14, 0.1: 18 of 20) | 64bc4e3 |
| 2/3 at 0.0966 | T2 | real BURST trapped at 1.35x | E2 | 49fbc7b |
| per-arm rule | T2 caption, 6, F5 | B3 and the simulator robustness runs count each arm separately; the registration counts seeds where all three arms succeed | PRED s0 B3 ("each in >= 2 of 3 seeds"); R7 ("each arm in at least 7 seeds"); REG `pass_rule.statement`; `analysis/trap_v2.py` `seed_verdict` | 64bc4e3, c653498, d279b7b |
| 1 of 3 | T2, 6 ("one in three") | real indeterminate count at 1.35x | E2 | 49fbc7b |
| n=64, 0.523 (seed 0) | T2 | B4 peak, 900k, mixed, registered seed 0 | PRED `b4_landmarks.csv` (mixed, 900, seed 0: peak_n 64, peak_mu 0.52278) | 64bc4e3 |
| 0.514, 0.085, 0.108 (5-seed means) | T2 caption | B4 supplementary seeds 0-4 means: peak, mu(96), mu(300) | PRED `b4_landmarks.csv` (0.51389, 0.08456, 0.10778) | 64bc4e3 |
| -8%; 9% | T2, 5.4 | real vs predicted peak; predicted above real | derived: 0.47889 / 0.52278 - 1 = -8.4%; 0.52278 / 0.47889 = 1.092 | - |
| 48, 64, 96 | T2 caption | B4 grid points around the peak | PRED (caveats: "The B4 grid is the registered coarse one (16, 24, 32, 48, 64, 96, 300)") | 64bc4e3 |
| approx. 80 | T2 | B4 0.5-hit crossing (900k) | PRED `b4_landmarks.csv` (79.65 seed 0; 80.71 5-seed mean) | 64bc4e3 |
| 0.079, 0.109 | T2 | B4 mu(96), mu(300), 900k, registered seed 0 | PRED `b4_landmarks.csv` (0.07944, 0.10889) | 64bc4e3 |
| 42% | 5.4 | real native hit fraction at n=96 | NAT (0.4189) | fa265c2 |
| 6% | 5.4 | real native pool vs 900k | derived: 955,757 / 900,000 = 1.062 | - |
| 2 of 3 | 5.4 | B3 seed requirement | PRED s3 item 6 | 64bc4e3 |
| 13 minutes | 5.4 | tag push (14:53) to E0b pull (15:06) | LOG (2026-10-24 round-6 and E0b entries); tag `r6-predictions-frozen` tagger date 14:52:56 | - |
| 200-231; 282-328 | 5.5 | FCFS refresh-off BURST backlog | GRID 20261025-144230 (231.2, 200.9, 221.2; 327.8, 281.8, 310.1) | fa265c2 |
| 4 of 6 (and draining in a fifth); 0.71, 0.81, 0.51; 0.80, 0.93 | 5.5, 8, 1 | LPM at 1.35x: recovered 4, draining 1, trapped 1; hit fractions | GRID 20261025-144233 (recovered 0.7143, 0.8098; draining 0.5146), 20261025-144236 (recovered 0.7958, 0.9342; seed 0 trapped) | fa265c2 |
| 4 of 6; 0.44; 0.82 | 5.5 | LPM at 1.65x | GRID 144233 (seed 2 indeterminate 0.4446), 144236 (seed 2 recovered 0.825) | fa265c2 |
| 1.17, 1.1 | 5.5 | simulator LPM congested rate; cold-start recovery limit | AUD (`lpm` 1.174 +- 0.023; recovers 3/3 up to 1.1x) | dc76032 |
| 128 | 2, 5.1, 5.5, 9 | SGLang LPM fallback and refresh limit | CIT (SGLang v0.5.22 row) | f0e2e19 |

## Robustness in the simulator (Section 6)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 10 seeds; 7 of 10 | 6, F5 | seeds per point; pass rule | R7 (interpretation choices; Wilson, "need 7") | c653498 |
| 3 seeds, need 2 | F5 | real-engine row | E2 / REG | 49fbc7b |
| 1, 2, 5 s; mean 5 s CV 2; 80% at 1 s, 20% at 20 s | 6 | synthetic tool-time laws | R7 table 1 | c653498 |
| 0.0718-0.0730 | 6 | lambda_miss across the five laws | R7 (bullet 1: 0.0718 to 0.0730) | c653498 |
| 0.0120 vs 0.0718 | 6 | lambda_miss depends on the token profile (secondary workload) | R7T headline (0.011962) | b530e55 |
| 5.25, 4.57, 2.97 | 6 | mu*/lambda_miss for Exp(1, 2, 5 s) | R7 bullet 1 | c653498 |
| 3.0, 2.5, 2.0 | 6 | window edge hi for Exp(1, 2, 5 s); 2.0 for heavy-tailed laws | R7 table 3 | c653498 |
| 10 points; 10 of 10; 7 to 10 of 10 | 6 | paired test results | R7 table 4 | c653498 |
| 52 developers | 6 | TraceLab population | TR ("52 pseudonymous developers") | 1556630 |
| 8.51 s, 600 s, 0.237 s, 4.65 | 6 | TraceLab per-turn table: mean, cap, median, CV | R7T design paragraph (mean 8.51, CV 4.65, median 0.237); TR (cap 600 s) | b530e55, 1556630 |
| 14.52 s | 6 | TraceLab idle-gap mean | R7T | b530e55 |
| 1.40 s, 0.104 s, 4.29 | 6 | mini-SWE-agent: mean, median, CV | R7T | b530e55 |
| v2.0.0 | 6 | mini-SWE-agent version | TR | 1556630 |
| -0.8% to +1.3% | 6 | lambda_miss shift under trace laws | R7T headline table | b530e55 |
| 32, 40 | 6, 8 | new peak / cap for TraceLab per-turn and idle gap | R7T headline table | b530e55 |
| 24 (cap 20); 20-24 | 6, 8 | mini-SWE-agent tool-time law: peak n and cap | R7T headline table (peak n 24, cap n 20) | b530e55 |
| 2 of 2; five of six | 6 | exponential control passes; primary-law points that pass | R7T ("The control: 2 of 2 PASS. The six points of the three primary laws: 5 PASS, 1 FAIL") | b530e55 |
| 1.65 pass; 2.35 fail; cap 12; CAPPED 0 of 10; NOBURST 8 of 10 | 6 | secondary mini-SWE-agent full workload, declared protocol | R7T headline table and s4 (iii) | b530e55 |
| 1.15; 3 of 10; all 10 stuck | 6 | post-hoc adjusted rerun, lower point | R7T s4 (adjusted rerun: "At 1.15 x: BURST trapped 3/10 ... with 10/10 stuck at hit < 0.2") | b530e55 |
| 1.40 x; 6 of 10; 20 fresh seeds, 17 | 6 | the slope-rule failure and its post-hoc replication | R7T s3 | b530e55 |
| 0.0120, 0.0141, 20 times | 6 | secondary workload lambda_miss declared vs long window | R7T s4 (i) | b530e55 |
| [1, 1.5], 1.35 | 6 | post-hoc adjusted window and passing point | R7T s4 (adjusted rerun) | b530e55 |
| 25 (0 of 10), 50 (5 and 6 of 10), 100 | 6 | burst-size sweep | R7 table 5 | c653498 |
| 30,000 s | 6, 10 | horizon after the burst (31,200 s runs) | R7 table 6 | c653498 |
| 0.5, 20, 468-1065, 50 | 6 | no release above hit 0.5; 20 runs; final backlog range; NOBURST never above 50 | R7 table 6 and per-run tables | c653498 |
| 100, 90, 10 | 6 | BURST runs, trapped, indeterminate (pooled) | R7 table 8 | c653498 |
| 31,200 s; 10 to 12 of 20 | 6 | long runs: share of stuck BURST runs the rule labels trapped | R7 s2 ("only 10/20 to 12/20 (the 31200 s runs ...) TRAPPED") | c653498 |
| 25 never, 50 about half | 8 | burst-size sweep, quoted in the diagnostic | R7 s3 (0/10; 5/10 and 6/10) | c653498 |
| 20 fresh seeds, 3; [0.05, 0.36]; 0.77; 0.5 | 6 | low-lambda stage at 1.35x | R7 table 7 | c653498 |
| six | 6 | real BURST runs at hit 0 | E2 | 49fbc7b |
| 64-80 | 5.1, 6, 8 | native peak region | NAT (0.479 at 64, 0.477 at 80) | fa265c2 |

## Deployed mechanisms (Section 7)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 300 | 7, F6 | closed population for mu(300) | AUD | dc76032 |
| 10 seeds, 95% | 7 (F6) | seeds and interval | AUD `curve_baselines_audit_s10.csv` (`n_seeds` 10, `ci95_half`) | dc76032 |
| 1.024 +- 0.020 | 7 | FCFS | AUD (`fcfs` 1.024148, 0.019771) | dc76032 |
| 1.174 +- 0.023 | 7 | LPM | AUD (`lpm` 1.174383, 0.022806) | dc76032 |
| 300 cold sessions, 150,000 s, 1.1, 1.25 | 7 | LPM cold-start recovery | AUD (Measured results, PEEK: "lpm recovers 3/3 up to 1.1x and 0/3 at 1.25x" at the 150000 s horizon) | dc76032 |
| 0.919 | 7 | PEEK hard-pin ablation | AUD (`peek` 0.919295) | dc76032 |
| 1.176 +- 0.021 | 7 | PEEK audited projection | AUD (`peek_singleton_audit` 1.175733, 0.020646) | dc76032 |
| 0.001 +- 0.014 | 7 | PEEK projection minus LPM | AUD (paired difference) | dc76032 |
| none of 5 bursts at 2 | 7 | PEEK projection burst recovery | AUD ("peek_singleton_audit trapped 3/5, recovered 0/5") | dc76032 |
| 5, 10, 20 s | 7 | TTL values | AUD | dc76032 |
| 2.584 +- 0.035, 3.505 +- 0.064, 4.376 +- 0.048 | 7 | pins under the preview rule | AUD (`ttl5cw`, `ttl10cw`, `ttl20cw`) | dc76032 |
| 4.0, 5 of 5 | 7 | tau = 20 s cold-start and burst recovery | AUD (Continuum recovery paragraph) | dc76032 |
| 1.719 | 7 | old idle-only rule at tau = 20 s | AUD (`ttl20` 1.718638) | dc76032 |
| 1.16 | 7 | eager-release rows | AUD (`ttl10e` 1.162, `ttl20e` 1.163, `ttl10ef` 1.168, `ttl20ef` 1.168) | dc76032 |
| +2, 0.2, 0.5, 0.2, halve | 7 | CONCUR rule | CIT (CONCUR row); AUD (Eq. 1) | f0e2e19 |
| 3.009 +- 0.081; 3.0 | 7 | CONCUR-equation surrogate | AUD (`concur_cap` 3.008502, 0.080645) | dc76032 |
| 5 of 5 | 7 | CONCUR surrogate burst recovery | AUD ("recovered 5/5 for all six rows") | dc76032 |
| 12 of 18; 4; 0.915-0.935 | 7, F6 (18 cells) | dead-KV usage sensitivity | AUD (CONCUR paragraph); `curve_baselines_audit_deadkv.csv` | dc76032 |
| 5 s vs 10 s; 0.184 +- 0.167; five sensitivities | 7 | control-interval sensitivity, unadjusted pointwise interval, one of five exploratory sensitivities | AUD (`concur_i5` paired difference; "Four of the five paired sensitivity intervals include zero ... not ... a multiplicity-adjusted discovery") | dc76032 |
| 4.04 +- 0.25; 2.39 +- 0.35; 1.08 +- 0.17; 3 seeds | 7 (also in the memory-demand paragraph), F6 | static caps c = 20, 28, 36 | R4 `curve_runs.csv` (fcfs_lru, k = 1, seeds 2000-2002; mean and t half-width computed as in `figures/paper/fig4_mechanisms.py`) | a1d485b |
| 4.07 at n = 22 | 7 | peak of the round-4 curve | R4 `prediction_eval.csv` (R1: n* 22, mu*/lambda_miss 4.068) | a1d485b |
| 30% | 7 | 36 = floor(1.3 x 28.4) | derived; paper/figs/README.md (F4 note: "c = 36 = floor(1.3 N_lb)") | - |

## Diagnostic, related work, limitations, conclusion (Sections 8-11)

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| 51% | 8 | mu(300) above lambda_miss | REG (`mu_300_vs_lambda_miss_rel_dev` 0.5066) | d279b7b |
| 0.507 | B | same, as recorded at filling | REG (`fill_problems`) | d279b7b |
| 31% | 8 | lambda_miss / peak at 300k | derived: 1 / 3.262 = 0.307 | - |
| 150,000 s; 0.9, 1.0 | 8 | earlier simulator: FCFS recovers from congestion at <= 0.9 x lambda_miss, not at >= 1.0, over 150k s | LOG (round-3 entry, P1: "It PASSes at 150k s: 3/3 at <=0.9x and 0/3 at >=1.0x") | beb60dc |
| 55% | 10 | cross-turn hit rate in production agent traces (abstract level, TODO cite) | CIT (scoop table: Copilot traces 2608.00101, 2605.26297: "about 55% across turn boundaries") | f0e2e19 |
| 925 ms (sd 3550 ms), 1923 ms | 9 | Continuum's mean tool times (SWE-Bench, BFCL); heavy tail for SWE-Bench only | CIT (Continuum row, Table 2: "925 ms (sd 3550) ... 1923 ms (sd 2133)") | f0e2e19 |
| 77.7% at 32, 35.4% at 40 | 9 | CONCUR's reported SGLang hit rates | CIT (CONCUR row, Table 2) | f0e2e19 |
| 7500 s, 30,000 s | 10 | horizons | REG; R7 | d279b7b, c653498 |
| 2.0 | 10 | E0b largest all-stable multiple | E0B | cfbc702 |
| twice; 2.0 | Abs, 1, 11 | from empty: stable in single 3000 s runs up to 2.0 x lambda_miss, unstable at 2.5 | E0B (stable at 2.0, unstable at 2.5) | cfbc702 |

## Appendices

| Value | Where | What | Source | Commit / job |
|---|---|---|---|---|
| job IDs 17060165; 17062103-05; 17072634-37; 17084750-55; 17093387-404; 17096856-57; 17096858; 17097086-103; 17097972-74 | 4 (via A), A (T3), C | real-engine jobs | LOG entries for each stage; `results/nova/*/` job-log directories | as listed |
| 16, 20, 24, 32, 48, 96, 300; 48, 300 | A (T3) | Stage C n grids (FCFS, LPM) | SC | d0235a7 |
| 24, 48, 64, 80, 96, 128, 300 | A (T3) | native n grid | NAT | fa265c2 |
| 2 rates x 3 seeds x 3 arms | A (T3) | E2 design | REG; E2 | d279b7b |
| 32 and 64 sessions; seeds 0, 1, 2 | A | E0a populations | E0A, E0A64 | a76f5e5 |
| 0.0567, 0.0643, 11,076; 0.0817, 0.0773, 11,342; 0.0767, 0.0730, 11,312 | A | E0a per-run (sessions/s, turns-based, tokens/s) | E0A `lambda_miss_runs.csv` | a76f5e5; 17072634-36 |
| 0.0544, 0.0676, 11,431 | A | E0a, 64 sessions | E0A64 | a76f5e5; 17072637 |
| 15.9, 13.2, 14.1 | A | mean turn index of in-window requests, seeds 0-2 | LOG (E0a entry); script `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/e0a_bins.py` | a76f5e5 |
| 0.1756, 0.2239, 0.2333, 0.1150, 0.0489, 0.0611, 0.1078 | B | registered mu(n) | REG (`mu_by_n`) | d279b7b |
| 0.07167, 0.07153 | B | registered lambda_miss (sessions, turns) | REG (`lambda_miss`, `lambda_miss_turns_based`) | d279b7b |
| 80%, 7200 s, 5760 s, 2.64 | B | CAPPED drain rule | REG (`capped_drain`: drain_fit_frac 0.8, post_burst_available_s 7200, max_drain_s 5760, max_lambda_mult 2.644) | d279b7b |
| (1.1, 1.8) | B | margin band | REG (`lambda_selection.rule`; `boundary_margin_rel: 0.1`) | d279b7b |
| 2026-10-23 | B | date the registration's own text gives for the rate and cap rules (the commit is 288b801, 2026-10-22) | REG (`lambda_selection.rule`) | d279b7b |
| 2a6d680a...0ac6 | B | registration SHA-256 | E2 `kill_verdict_v2.json` (`prereg.provenance.sha256`) | 49fbc7b |
| 15:09 CDT, 2026-10-24 | B, C | registration commit time | `git log d279b7b`; `kill_verdict_v2.json` (`git_last_commit_time`) | d279b7b |
| 20261025-144012 | B | verdict directory | E2 | 49fbc7b |
| C timeline: 10-22 13:13 (288b801); 10-23 14:32 (a76f5e5); 10-23 ~14:40 (E0b submitted); 10-24 03:13 (813cfc1); 03:23 (630ab9e); 03:49 (64bc4e3); 04:05 (877b936); 14:52 tag, pushed 14:53; 15:06 pull (cfbc702); 15:09 (d279b7b); 15:13 E2 submitted; 15:38 to 10-25 ~02:40 E2 runs; 10-25 02:28 native start; 10-25 14:40 verdict (49fbc7b) | C (T6) | order of events | `git log --format=%ci` for each commit; `git for-each-ref refs/tags/r6-predictions-frozen` (14:52:56); LOG (2026-10-24 entries: push 14:53, pull 15:06, E2 submission 15:13, E0b submission ~14:40; 2026-10-25 E2 entry: 15:38 to ~02:40); NATLOG directory name (20261025-022855); E2 verdict directory name (20261025-144012) | as listed |

## Pending (not numbers; rendered in red by `\pending{}`)

| Where | Item | Jobs |
|---|---|---|
| 1, 5.6, A (T3) | running: native-pool from-empty edge (native E0b) | 17100938-39 (running; STATE 2026-10-25 ~15:00) |
| 1, 5.6 | planned, not yet submitted: native blind prediction, registration and native E2 kill test | not yet submitted |
| 1, 5.6, A (T3) | running: vLLM all-miss capacity (vLLM E0a) | 17100940 (running) |
| 1, 5.6 | planned, not yet submitted: six vLLM BURST runs under an exploratory registration | not yet submitted |

## References that are needed but not in `paper/refs.bib` (rendered as blue TODO)

| Where | Missing reference |
|---|---|
| 6 | TraceLab (Zhu et al., arXiv:2606.30560), the trace source (see `notes/lit/AGENT_TRACES.md`) |
| 6 | mini-SWE-agent (software) |
| 1, 2, 7, 9 | NVIDIA Dynamo engineering post on session-aware admission (read in full in CIT, not in refs.bib) |
| 2 | ALOHA bistability and network congestion collapse (classical analogues of the fluid picture) |
| 2 | Courtois, "Decomposability, instabilities, and saturation in multiprogramming systems", CACM 18(7), 1975 (seen only through a web-search summary) |
| 2, 8 | Multiprogramming-level load control: Denning et al., Acta Informatica 1976; Heiss and Wagner, VLDB 1991; Schroeder et al., ICDE 2006 (web-search summaries only) |
| 3.2 | H = lambda G (Heyman and Stidham 1980; Brumelle 1971; from memory, unchecked) |
| 6 | SWE-bench Verified release (jimenez2024swebench is the ICLR 2024 paper, which predates the Verified subset) |
| 8 | KVSET (arXiv:2609.27746) and EfficientAgent (arXiv:2609.33762), abstract level in CIT |
| 9 | Metronome (2607.02640), MISA-T (2608.11152), AgentServeSim (2606.09613), ServeTwin (2610.02732), abstract level in CIT |
| 10 | Copilot traces (2608.00101) and Agentic AI Workload Characteristics (2605.26297), abstract level in CIT |
