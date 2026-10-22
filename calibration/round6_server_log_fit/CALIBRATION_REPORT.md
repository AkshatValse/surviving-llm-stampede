# Calibration agent report (workflow wf_62e1fc6c-410, stage 'calibrate-from-logs', verbatim)

## SGLang 0.5.22 iteration-time calibration (Qwen2.5-7B, A100-80GB PCIe)

The assumed cost constants are too high. On the same clean observations they overpredict decode by a median 56% and prefill by a median 55%. The calibrated model has a median error of 0.75% on decode and 1.3% on prefill.

**1. What the log fields mean (read from SGLang source on Nova, `.../site-packages/sglang/srt/managers/`)**
- **Prefill line** (`scheduler_components/metrics_reporter.py`, `report_prefill_stats`): written each time a prefill batch's result is processed. The interval is `gap_latency = now - self.last_prefill_stats_tic` and the numerator is #new-token plus replay tokens. So #new-token / throughput is the time since the previous Prefill line, and it includes any decode iterations or idle time in between.
- **Decode line** (`report_decode_stats`): written only when `forward_ct_decode % decode_log_interval` is 0, i.e. every 40 decode batches. It computes `self.last_gen_throughput = self.num_generated_tokens / gap_latency`. The numerator is the sum of decode batch sizes, incremented only in `batch_result_processor.py` (`process_batch_result_decode`). The interval includes any prefills run in between.
- **#token** (`pool_stats_observer.py`) is total pool size minus (available + evictable), i.e. KV tokens pinned by running requests. I verified it: usage equals #token/300000 to rounding on all 14,649 decode lines, and #token grows by exactly 40·R in 1144 of 1183 candidate windows.
- **#cached-token** is 0 for continuation chunks, because `schedule_policy.py:add_chunked_req` passes prefix_len 0. I rebuilt those prefixes from the chunk chains.
- **Scheduler** (`scheduler.py`): "Run prefill first if possible"; a chunked request's next chunk is always scheduled next.

**Clean observations** (everything else dropped):
- **Decode:** two adjacent Decode lines with no Prefill between, equal R, and #token growth of 40·R. Step time is R/throughput. n=1144 windows, R from 1 to 142.
- **Prefill:** the line directly after a full 8192-token chunk, single sequence, prefix known. n=1355; new tokens X from 159 to 8192; prefix 8.2k to 35k.

**2. Fit** (simulator form, applied to separate prefill and decode iterations; least squares on relative residuals; 95% CIs from a 120 s block bootstrap, B=500, seed 20261022)

| param | calibrated | 95% CI | assumed |
|---|---|---|---|
| iter_fixed_s | 9.24e-3 | [9.00e-3, 1.04e-2] | 2e-3 |
| iter_floor_s | 1.26e-3 | [1.0e-4, 1.47e-3] | 9.5e-3 |
| per_token_s | 6.26e-5 | [6.15e-5, 6.34e-5] | 8.4e-5 |
| decode_attn_s | 3.10e-4 | [2.76e-4, 3.16e-4] | 7.1e-4 |
| prefill_attn_s | 2.24e-9 (mid) | [2.19e-9, 2.30e-9] | 3.5e-9 (end) |

- **Fit quality:** decode R² 0.992, median |rel err| 0.75%, p95 4.3%. Prefill R² 0.998, median 1.3%, p95 8.3%. The assumed values on the same data give R² −3.2 (decode) and −1.4 (prefill).
- **What is identifiable:** the decode data only pin iter_fixed + iter_floor = 10.51 ms [10.46, 10.56]; the prefill intercept sets the split, which is why iter_floor's CI is wide. per_token_s comes from the spread in prefill sizes, and prefill_attn_s from the spread in prefix length of 8192-token chunks. The exact causal pair count ("mid") fits better than "end" (median error 1.3% vs 2.7%), so the YAML switches `prefill_attn_ctx` from end to **mid**. The end-convention values are in the provenance block.
- **Unconstrained fits (for comparison):**
  - Decode: 10.40 ms + 43.5 µs·R [39, 51] + 0.296 ms per 8192 context tokens.
  - Prefill: 9.9 ms + 62.9 µs·X + 2.21e-9 per attention pair.
  - Across the three nodes: per_token 61–65 µs, decode intercept 9.0–10.5 ms.
- **Out-of-sample checks:**
  - 6650 continuation chunks whose prefix is only known within a range: 95.4% fall inside the predicted interval ±2%.
  - Hit prefills (551 new tokens) that follow another prefill: their gaps cluster at multiples of one decode step. Clusters 2 to 6 are spaced 0.988× the model's decode step, so the decode model holds to about 1% at light load.
  - The zero-decode cluster gives hit cost = 35.3 ms [35.1, 35.7] + 2.10 µs [2.08, 2.13]·prefix, i.e. 3.8e-9 s per attention pair, 1.7× the chunk value. The calibrated model is off on hits by +17% (prefix under 4k) to −11% (over 16k), and close to 0 near 10k.
  - Clusters 1 and up sit about 0.35 decode steps (~4 ms) below the integers. I can't explain that offset.

**3. Derived quantities**
- **All-miss prefill:**
  - A fresh 8192-token chunk takes 0.597 s, about 13.7k tok/s (assumed: 0.925 s, 8.9k tok/s).
  - A full miss of P tokens: 2000 → 14.4k tok/s, 8000 → 13.8k, 16000 → 12.3k, 32000 → 10.0k (assumed: 10.9k / 8.9k / 7.9k / 6.5k).
  - Without the model: all clean prefill batches with no cached tokens averaged 12.1k tok/s (168M tokens in 13,861 s; 11.3k–12.6k per job).
- **Decode step, calibrated** (assumed in parentheses):

| R | context per sequence | calibrated (ms) | assumed (ms) | observed (ms) |
|---|---|---|---|---|
| 16 | 2.65k | 12.1 | 15.2 | |
| 16 | 8k | 15.4 | 22.9 | |
| 16 | 16k | 20.4 | 34.2 | 21.4 (R 13–20, 286k total context) |
| 32 | 2.65k | 14.4 | 18.8 | |
| 32 | 8k | 21.1 | 34.2 | |
| 32 | pool full (295k) | 22.4 | 37.1 | 23.0 (R 26–40) |
| 64 | 2.65k | 19.7 | 26.2 | |
| 64 | pool full (295k) | 24.4 | 37.1 | 24.0 (R 52–79) |

**Problems parameters can't fix:**
1. SGLang runs prefill and decode as separate iterations and holds decode back while any prefill can run; the simulator mixes them in one iteration. With these values, a simulator iteration with n_D decoding sequences costs about (10.5 − 0.063·n_D) ms less than SGLang's prefill-plus-decode pair. Fixing this needs an engine switch.
2. The shared per_token_s forces a decode slope of 62.6 µs/seq above R≈20, against 43.5 µs measured. That gives +5–12% decode error at R≥80 and −6% near R≈32. A separate per-sequence decode parameter would fix it.
3. Hit prefills cost more per attention pair than chunks, as above.

Overall, the assumed constants overcharge miss prefill by 1.3–1.55× and decode by 1.1–1.7×. Simulated rates (λ_miss, λ_cap) in absolute units are probably biased low by a similar factor; I did not re-run the simulator, so that is untested.

**Blindness:** I used only the Stage 0 and Stage C server logs and pulled metadata, and SGLang source on Nova. I read nothing under Nova `results/` or `logs/`, ran no squeue/sacct, and touched no E0a/E0b/E2 data. The worktree has uncommitted `engine.py` and test changes that are not mine, so the provenance block records the repo as dirty. I did not modify the repo.

Files are in /private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/simcal/calib/:
- calibration.yaml
- residuals_calibrated.pdf
- assumed_vs_calibrated.pdf
- hit_prefill_comb.pdf
- fit_results.json
- validation.json
- hits.json
- parse_logs.py
- build_datasets.py
- fit.py
- validate.py
- hits.py
- make_yaml.py