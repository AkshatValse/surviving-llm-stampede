# Stage C verification (workflow stagec-verify, run wf_c2f85054-e33, 2026-10-22)

Four agents (default model): independent recomputation + stationarity; measurement-artifact hunt; simulator comparison; adversarial critic. Inputs: `results/nova/stageC_1706210x_pulled_20261022-125454`. Their scripts and outputs are copied to `results/nova/stageC_1706210x_pulled_20261022-125454/verification/`. The reports below are verbatim.


---
## recompute

## Stage C independent recomputation (9 runs, own code; harness packages not imported)

**Time convention.** All `t_*` values are seconds since run start on the event-loop monotonic clock (`meta.time_convention`). The first sends are at about 0.012 s. A turn counts toward the window by `requests.t_complete`, and a session by `sessions.t_end` with status `completed`. `t_end` equals the last turn's `t_complete` to within 0.6 ms. My window is [900, 2700) with a divisor of 1800 s. The harness uses [900, t_end_s] and divides by `measure_s` = t_end_s − 900, which is 1800.008–1800.023 s.

**mu_turns_based** = turns/s ÷ E[T]. Here T = min(Geom(1/15), 60), so E[T] = Σ_{k=1}^{60}(14/15)^{k−1} = 15(1−(14/15)^{60}) = 14.7611, which matches `meta.expected_turns_per_session` (assert passed). The justification is renewal-reward: at stationarity, turns/s = μ_sessions·E[T]. This has much lower variance than counting completions. I used the population E[T] rather than the per-run sample mean of drawn `n_turns` (14.45–15.29); the sample mean would shift the result by up to 3.6%. The estimator is only unbiased at stationarity.

### 1. Recomputed points

| pol | n | sess | turns | μ_sess | μ_turns | hit | hit (turn≥2) | cached tok | mean T of completed sessions |
|---|---|---|---|---|---|---|---|---|---|
|FCFS|16|316|4670|0.1756|0.1758|0.9321|1.0000|0.9356|14.89|
|FCFS|20|403|5713|0.2239|0.2150|0.9268|0.9972|0.9303|14.33|
|FCFS|24|420|5992|0.2333|0.2255|0.8877|0.9546|0.8829|14.50|
|FCFS|32|207|3076|0.1150|0.1158|0.5052|0.5418|0.4633|15.33|
|FCFS|48|88|1672|0.0489|0.0629|0|0|0|17.74|
|FCFS|96|110|1939|0.0611|0.0730|0|0|0|13.62|
|FCFS|300|194|2961|0.1078|0.1114|0|0|1.8e-7|9.45|
|LPM|48|156|2566|0.0867|0.0966|0.3850|0.4100|0.3744|17.37|
|LPM|300|189|2932|0.1050|0.1104|0|0|0|9.34|

**Max abs difference vs `mu_points.csv`.** With the harness window and divisor: at most 8.3e-17 for the μ values and at most 1.1e-16 for the fractions, and the counts are identical. With [900, 2700)/1800: at most 2.1e-6, from the divisor only. No turn or session completed in [2700, t_end].

### 2. Stationarity (six 300 s bins)

Below: turns/s per bin, then hit per bin, then mean prompt in bin 0 → bin 5. ρ is the Spearman correlation of turns/s with bin index. f→l is the change from the first to the last bin.

| run | turns/s per bin | hit per bin | prompt b0→b5 | ρ(tps) | f→l tps | flag |
|---|---|---|---|---|---|---|
|F16|2.46 2.64 2.61 2.61 2.59 2.65|.96 .93 .92 .93 .93 .93|12422→8839|0.43|+8%|sessions/s only (+87%, bin0 = 30 sessions)|
|F20|3.07 3.21 3.15 3.27 3.15 3.19|.93 .92 .92 .92 .93 .93|11656→9324|0.26|+4%|no|
|F24|1.93 3.73 3.64 3.53 3.68 3.47|.66 .91 .92 .89 .93 .92|12716→9615|0.03|+80%|degraded excursion in bin 0|
|F32|1.39 1.18 0.83 1.47 1.64 3.74|.33 .26 .12 .41 .43 .80|11354→8566|0.77|+169%|**regime switch**|
|F48|1.09 .96 .93 .93 .81 .86|0|10545→12554 (ρ .94)|−0.93|−21%|trend|
|F96|1.28 1.16 1.09 1.03 .95 .95|0|9270→11775 (ρ .94)|−0.99|−26%|trend|
|F300|1.89 1.78 1.71 1.59 1.42 1.48|0|6674→8603 (ρ 1.0)|−0.94|−22%|trend|
|L48|1.26 1.38 1.26 1.32 1.46 1.87|.28 .38 .36 .41 .41 .44 (ρ .94)|11592→9857|0.78|+49%|trend|
|L300|1.90 1.77 1.71 1.46 1.54 1.38|0|6651→8462 (ρ 1.0)|−0.94|−27%|trend|

Mean turn index rises in the same way: F48 14.1→17.2, F96 12.2→16.0, F300 8.2→11.2.

Looking at 150 s bins over the whole run:
- **F32** has been degraded since about 450 s (hit 0.12–0.5, median latency 13–33 s). It recovers at about 2400 s (3.96 turns/s, hit 0.81, median latency 3 s). μ(32) = 0.115 is therefore an average of two regimes.
- **F24** has a degraded excursion at 750–1050 s (hit 0.48, median latency 12 s), then recovers.
- **F48 and F96** have overshot the stationary turn mix. F48's in-flight mean k is 16.5 against a stationary 14.2, which looks like a damped cohort oscillation.

**How far n=300 is from steady state.**
- At stationarity with iid T, the rate of completed turns with index k is proportional to P(T≥k). That gives a mean index E[T(T+1)/2]/E[T] = 14.03 and a mean prompt of 2000+650(k−1) = **10,469 tokens**.
- For in-flight requests, weighting by the fitted latency L(k) = 166.5+0.85k s gives E[k] = 14.75 and a prompt of 10,937.
- What F300 actually shows:
  - In-flight requests over the window average k = 9.88 and a prompt of 7,770, about 71% of the stationary length.
  - Sessions completing in the window have mean T = 9.45 against 14.76, so short sessions are over-represented.
  - At 2699 s, 29% of the live sessions are still from the t=0 cohort.
  - The mean age of live sessions climbs linearly from 725 s to 1742 s with no plateau.
- Uncached prefill throughput is flat at about 12.6k tok/s in every bin (11.7–12.7k).
- **Projection (assumes that throughput holds at the longer stationary mix, which is not verified):** μ_ss ≈ 12.6k / 154,529 tokens per session ≈ **0.082**. On that basis the measured 0.108–0.111 is about 32–36% too high, and Little's law gives a session lifetime of about 3,700 s, longer than the run.
- L300 behaves the same way. Its first three bins have the same session counts as F300 (32/49/31).

### 3. Batch-means standard errors (6 bins)

Values are mean ± SE, with the lag-1 autocorrelation of the bin values in parentheses.

| run | μ_turns | hit |
|---|---|---|
|F16|0.176±0.002 (−0.55)|0.932±0.006|
|F20|0.215±0.002 (−0.62)|0.927±0.002|
|F24|0.226±0.019 (−0.65)|0.870±0.042|
|F32|0.116±0.029 (+0.59)|0.392±0.094 (pooled 0.505)|
|F48|0.063±0.003 (+0.63)|0±0|
|F96|0.073±0.004 (+0.97)|0±0|
|F300|0.111±0.005 (+0.89)|0±0|
|L48|0.097±0.006 (+0.71)|0.380±0.022 (+0.53)|
|L300|0.110±0.005 (+0.75)|0±0|

Caveat: with only 6 batches the lag-1 estimates are crude. Positive autocorrelation (F32 onward, L48) means these SEs are too small. For the trending runs the bias is larger than the SE, so the SE is not a steady-state uncertainty. The bin-mean hit fraction is not the pooled ratio: F32 gives 0.392 against 0.505 pooled.

### 4. Request-level checks
- 0 errors, 0 non-null `error`/`error_kind`, 0 non-200 among ok requests, and no status other than ok or cancelled.
- Every cancellation happens at run end. Cancelled requests per run: 5 / 1 / 20 / 16 / 46 / 87 / 296 / 41 / 299, in the row order of the latency table, and all were sent at or after 2492 s. Cancelled sessions equal n in every run.
- `output_ids_source` is `server_ids` for every ok request and NaN for cancelled ones.
- `completion_tokens` = 100 for all ok requests. `prompt_tokens` equals `prompt_tokens_client` and equals 2000+650(k−1) for every ok request.

In-window latency for ok requests (seconds):

| run | p50 | p90 | p99 | max |
|---|---|---|---|---|
|F16|1.57|1.86|2.21|2.55|
|F20|1.72|2.07|2.82|7.16|
|F24|1.94|3.58|16.5|30.7|
|F32|13.3|28.3|43.9|47.9|
|F48|47.6|52.7|64.1|69.6|
|F96|83.8|98.2|102.5|104.3|
|F300|179|205|214|215|
|L48|27.3|46.9|56.4|59.2|
|L300|180|205|214|216|

### Discrepancies with the harness
1. **Numerical:** none. The only convention difference is the divisor (t_end_s − 900 rather than 1800), worth at most 2.1e-6.
2. F300's cached_frac of 1.8e-7 comes from 4 in-window requests that each had `cached_tokens` = 1. Across the whole n=300 runs, no request has hit > 0.5.
3. **Interpretation, not arithmetic:**
   - μ(32) mixes the degraded and recovered regimes.
   - μ(24)'s bin 0 contains a degraded excursion.
   - μ(48), μ(96), μ(300) and LPM 48 are still trending.
   - μ(300) is an early-cohort transient. My projection (assumption-based) puts it roughly 32–36% too high.
4. All 9 runs reuse the same `n_turns` sequence for each session index (seed 0), so they are not independent replicates. LPM-300 is aggregate-equivalent to FCFS-300, consistent with LPM falling back to FCFS at that queue depth.
5. I did not recompute the engine waiting-queue means from `metrics.csv`, so I can neither confirm nor dispute them.

Files are in /private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/verify_stageC/recompute/:
- recompute.py
- extra.py
- recompute_points.csv
- bins.csv
- stationarity.csv
- misc.csv
- snapshots.csv
- run1.txt
- run2.txt
---
## artifact

## Verdict: the hit fraction really is 0 at n ≥ 48, and the engine confirms it

The 0.000 is not a reporting artifact. Three independent sources agree: the client usage JSON, the engine Prometheus counters, and the server.log prefill lines. It holds for FCFS at n = 48, 96 and 300, and for LPM at n = 300. LPM at n = 48 is not zero (0.374). All numbers are over the measured window [900, 2700) s.

### 1. Engine counters vs client (window deltas)

| run | n | engine cached/prompt | prefill_effective device_hit/(hit+input) | uncached-hist 1−Σunc/Σprompt | client Σcached/Σprompt | evicted tok |
|---|---|---|---|---|---|---|
| FCFS | 16 | 0.9355 | 0.9356 | 0.9355 | 0.9356 | 3.48M |
| FCFS | 20 | 0.9306 | 0.9306 | 0.9306 | 0.9303 | 4.43M |
| FCFS | 24 | 0.8829 | 0.8843 | 0.8829 | 0.8829 | 7.39M |
| FCFS | 32 | 0.4610 | 0.4662 | 0.4610 | 0.4633 | 17.56M |
| FCFS | 48 | **0 (Δcached = 0 of 20.02M)** | 0 | 0 | 0 | 20.14M |
| FCFS | 96 | **0 (0 of 20.80M)** | 0 | 0 | 0 | 21.03M |
| FCFS | 300 | 1.8e-7 (4 tokens) | 1.8e-7 | 1.8e-7 | 1.8e-7 | 22.55M |
| LPM | 48 | 0.3744 | 0.3748 | 0.3744 | 0.3744 | 18.85M |
| LPM | 300 | 0 | 0 | 0 | 0 | 22.45M |

- No counter went backwards inside any window.
- The client prompt-token sum matches the engine delta to within boundary effects (exactly, at n = 48 FCFS).
- In the n ≥ 48 zero runs, evicted tokens are roughly equal to prefilled tokens.
- The `cache_hit_rate` gauge is 0.0 at every scrape (mean, min and max) for FCFS 48, 96 and 300 and for LPM 300. At n = 16 its mean is 0.867.
- `num_retracted_reqs` and `num_paused_reqs` are 0 at every scrape in every run.
- Mean token_usage / kv_evictable_tokens / num_queue_reqs / num_running_reqs:
  - FCFS 48: 0.75 / 71k / 23.9 / 17.3
  - FCFS 96: 0.88 / 34k / 66.1 / 22.5
  - FCFS 300: 0.57 / 125k / 269 / 20.3
  - LPM 48: 0.84 / 45k / 19.2 / 19.3
  - FCFS 16: 0.15 / 255k / 0 / 3.9

### 2. server.log "Prefill batch" lines (mapped by t0_utc; local time is UTC−5)

| run | lines | #cached share | lines with cached > 0 | decode token-usage p50 / p95 | decode lines with usage ≥ 0.95 |
|---|---|---|---|---|---|
| FCFS 16 | 4557 | 0.9355 | 4250 | 0.11 / 0.29 | 0% |
| FCFS 32 | 3074 | 0.468 | 1160 | 0.56 / 0.99 | 32% |
| FCFS 48 | 2538 | **0.0000** | **0** | 0.97 / 1.00 | 77% |
| FCFS 96 | 2684 | 0.0000 | 0 | 0.98 / 0.99 | 90% |
| FCFS 300 | 2766 | 4 tokens | 4 | 0.98 / 0.99 | 99.5% |
| LPM 48 | 2419 | 0.376 | 682 | 0.97 / 0.99 | 81% |
| LPM 300 | 2751 | 0 | 0 | 0.98 / 0.99 | 99.5% |

The server log agrees with the counters.

### 3. Raw usage JSON

- In every run, `prompt_tokens_details.cached_tokens` is present for 100% of OK requests (cached_source is `usage.prompt_tokens_details`).
- It equals the CSV `cached_tokens` column for 100% of rows, and `cached_tokens` is never greater than `prompt_tokens`.
- Sample at n = 16: turn 4 has prompt 3950 and cached 3399; turn 15 has 11100 and 10549. Cached is always prompt − 551, which is the previous prompt plus 99 of the 100 output tokens (the last generated token has no KV).
- Sample at n = 48: prompts 4600, 18900, 10450 and 16950 all show `"cached_tokens":0`.

### 4. Confounds

**Ruled out:**
- **Prompt continuity:** `prompt_tokens` = 2000 + 650·(turn−1) for 100% of requests. The step between consecutive turns is exactly 650 in 100% of cases. `prompt_tokens_client` equals the server's `prompt_tokens`, and `completion_tokens` = 100 throughout.
- **Output feedback:** `output_ids_source` is `server_ids` for 100% of OK requests in all 9 runs.
- **All-or-nothing hits:** in the window, every turn > 1 request is either a full-prefix hit (cached = prompt − 551) or exactly 0. Partial hits occur only at FCFS 20 (0.1%), FCFS 24 (0.8%), FCFS 32 (2.5%) and LPM 48 (7.9%).
- **Does the cache work on the n ≥ 48 server?** Yes. In FCFS 48 on nova22-gpu-3, 63% of turn > 1 requests completed before 300 s were full hits. The hit fraction by 300-s bin was 0.438, 0.021, 0.003, then 0. The last increase of `cached_tokens_total` was at t = 850 s, before the window opened. FCFS 96 had its last cached-token increase at t = 115 s.
- **Canaries:** all 12 passed. After priming, the second request was cached 1023/1024; after the flush it was cached 0, with token_usage 0 and the engine idle.
- **Client throttling:** the in-flight cap is 4000 and `max_inflight_seen` equals n. `gate n_waited` is 0 everywhere.
- **Errors:** zero errors in every run, and no retract, OOM or traceback lines in any server.log.
- **Server config:** `enable_cache_report` is True and `disable_radix_cache` is False on all three servers. Settings: page_size 1, LRU eviction, max_total_tokens 300000, FlashInfer.

**The mechanism is consistent (rough check, a ratio of means):** I estimated how long cached, evictable tokens survive before eviction as mean kv_evictable / eviction rate, and compared it with the reuse gap (5 s of tool time plus the engine's mean queue time).

| run | survival time | reuse gap |
|---|---|---|
| FCFS 16 | 131 s | ≈5 s |
| FCFS 24 | 50 s | 5.1 s |
| FCFS 32 | 10.5 s | 9.1 s |
| FCFS 48 | 6.3 s | 30.6 s |
| FCFS 96 | 2.9 s | 66 s |

At n ≥ 48 a session's prefix is evicted long before its next turn reaches the scheduler, so the zero comes from real LRU thrash.

**Caveats to fix or disclose:**
1. **The node and job changed at the cliff.** FCFS n ≤ 32 ran on nova22-gpu-1 (job 17062103) and FCFS n ≥ 48 on nova22-gpu-3 (job 17062104). The early-run hits and canaries on gpu-3, and LPM 48 on gpu-2 still getting hits, argue against a server fault. Still, the n = 32→48 comparison crosses servers. nvidia-smi in banner.txt shows an A100 80GB PCIe on all three nodes. The `meta.hardware` field is a job-script `--set`, not a measurement.
2. **One seed per n, and the runs are not stationary.** FCFS 32 swings 0.80→0.11→0.80 across 300-s bins and FCFS 24 dips to 0.68. LPM 48 climbs from 0.20 to 0.44 across the window, so its 0.374 is not steady state.
3. **Server seed not pinned.** The SGLang `random_seed` was left at its default and differs per job.
4. **Context length.** `--context-length 49152` is above the derived 32768 (the server logs a warning), and prompts reach 40350 tokens. This has no effect on caching but matters for any claim about model outputs.
5. **Missing records.** `events.log` is 0 bytes in every run dir, so I used `meta.json` t0_utc instead. The value of `SGLANG_ENABLE_WAITING_PREFIX_REFRESH` is not recorded anywhere, only that the variable exists.

Scripts and outputs are in /private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/verify_stageC/artifact/:
- s1_meta.py
- s2_metrics.py, output s2_metrics_out.csv
- s3_serverlog.py, output s3_serverlog_out.csv
- s4_requests.py
- s5_timeline.py
- s6_confounds.py
---
## simcmp

**Simulator vs real Stage C: FCFS closed-population curve, M = 300k tokens**

λ_miss in the sim files: r4 0.04742 sessions/s, r5 ratio_reserve 0.04732. All μ values below are sessions/s. The sim is the mean of 3 seeds over [5000, 35000) s. Sim values at n=48 and n=96 are interpolated in log n (n* in the second table). "Same protocol" means sim r4 with a synchronized start, read over the window [1000, 3000) s and normalized by that window's own maximum. Real values are 1 seed over [900, 2700) s. Real μ and hit values match the harness output to within 2e-6.

| n | real μ | sim r4 μ | sim r5 μ | real/r4 | real/r5 | real μ/μmax | r4 μ/μmax | same-protocol μ/μmax | real hit | sim hit r4/r5 |
|---|---|---|---|---|---|---|---|---|---|---|
| 16 | 0.176 | 0.163 | 0.161 | 1.08 | 1.09 | 0.75 | 0.84 | 0.85 | 0.932 | 0.932/0.933 |
| 20 | 0.224 | 0.192 | 0.188 | 1.17 | 1.19 | 0.96 | 0.99 | 1.00 | 0.927 | 0.927/0.929 |
| 24 | 0.233 | 0.175 | 0.170 | 1.33 | 1.38 | 1.00 | 0.91 | 0.84 | 0.888 | 0.883/0.878 |
| 32 | 0.115 | 0.066 | 0.064 | 1.75 | 1.81 | 0.49 | 0.34 | 0.34 | 0.505 | 0.379/0.385 |
| 48* | 0.049 | 0.047 | 0.046 | 1.04 | 1.06 | 0.21 | 0.24 | 0.26 | 0.000 | 0.002/0.022 |
| 96* | 0.061 | 0.047 | 0.046 | 1.31 | 1.34 | 0.26 | 0.24 | 0.29 | 0.000 | 0/0 |
| 300 | 0.108 | 0.047 | 0.046 | 2.30 | 2.34 | 0.46 | 0.24 | 0.41 | 0.000 | 0/0 |

The real/sim ratio is not constant. It runs from about 1.1 where tool time dominates (n=16), to 1.3 at the peak, 1.8 at the cliff, and 2.3 at n=300.

**All-miss level (my own check, not in the harness).** Real uncached prefill runs at 11.1k, 11.6k and 12.5k tokens/s at n = 48, 96 and 300, against the sim's 7.3k. On misses the real engine is about 1.5× faster than the sim's assumed costs. At the peak it is only about 1.2× faster.

The n=48 window is not stationary:
- turns/s fell from 1.09 to 0.86 across the measured windows;
- mean prompt rose from 10.5k to 12.5–13.1k tokens, while the steady-state value is 10.5k;
- completed sessions averaged 17.7 turns, against E[T] = 14.76.

Dividing uncached tokens/s by the 154.5k tokens a session needs when every turn misses gives a real λ_miss proxy of about 0.072–0.075. That is 1.5–1.6× the sim's λ_miss and about 0.31 of μmax. So the near-match of real μ(48) to the sim's λ_miss (1.03×) is probably a coincidence. This is untested until E0a measures λ_miss directly.

| Feature | Real | Sim |
|---|---|---|
| Peak n* | 24 (n=20 within 4%, flagged ambiguous) | 22 (r4), 20 (r5); 20 on the real grid |
| μ(24)/μ(20) | 1.04 | 0.92 / 0.90 |
| n where hit crosses 0.5 | 32.2 | 30.6 on the fine grid, 30.1 on the real grid |
| Drop from n=24 to 32 | 51% | 62% |
| μ(48)/μmax | 0.21 | 0.24–0.25, or 0.26–0.32 same protocol |
| μ(96)/μmax | 0.26 | 0.24, or 0.29–0.35 same protocol |
| μ(300)/μmax | 0.46 | 0.24, or 0.41 (r4) / 0.46 (r5) same protocol |
| LPM/FCFS at n=48 | 1.77 by sessions, 1.54 by turns; hit 0.385 (0.28 rising to 0.44) | ideal LPM 1.17 / 1.22, hit 0.25 / 0.29 |
| LPM/FCFS at n=300 | 0.97 by sessions, 0.99 by turns; hit 0 for both | ideal LPM 1.15 / 1.20, hit 0.21 / 0.26; LPM-128 1.000, hit 0 |
| Partial hits (cached fraction between 0 and 0.5) | ≤1.6% of turns under FCFS, 5.1% under LPM at n=48 | none (whole-session eviction) |

**Agreements**

Strong:
- Hit fraction for n ≤ 24 matches to within 0.01.
- Hit is exactly 0.000 at n = 48, 96 and 300. This confirms the pre-registered "all-miss for n ≥ ~40".
- Deployed LPM-128 behaves like FCFS when more than 128 requests wait (real queue at n=300 was 269). This holds by construction.
- The real n=300 value matches the sim's own prediction of the start-up bias (0.46 against 0.41–0.46). The real sessions completed at n=300 average 9.4 turns and 7.6k-token prompts, so the n=300 point cannot be compared with the sim's steady state. The sim says the [1000, 3000) s window inflates μ by 65–67% at n=300 and by 18–31% at n=100.
- Bistability near the cliff: at n=24 the hit fraction dipped to 0.66 and recovered; at n=32 it swung between 0.12 and 0.80 across 300 s windows.

Weak:
- "Sharply unimodal with n* ≈ 20–22". The shape holds, but the real peak is at 24 and is ambiguous. On the real grid the cliff sits about 2 sessions to the right.
- Collapse depth is right to within about 1.3× (real 0.21–0.26 against sim 0.24–0.32). The steady-state real value is uncertain (0.21 to about 0.31 using the λ_miss proxy).

Contradicted or not testable:
- At n=32 the real system holds more hits and more throughput than the sim (0.49 of μmax against 0.29–0.34).
- Ideal LPM at n=48 gets a hit fraction of 0.385, against the predicted ~0.2 (recomputed 0.21–0.29). Its advantage of 1.54–1.77× over FCFS is larger than the sim's 1.17–1.22×. Measured against the λ_miss proxy instead, it is 1.20–1.34× λ_miss, close to the sim's 1.14–1.19. So this contradiction depends on the FCFS n=48 baseline, which has the transient bias described above.
- The ideal-LPM large-n tail (1.14–1.16 λ_miss) cannot be tested on the real engine, because the 128-waiting fallback is active at n=300.
- "μ ≈ λ_miss" is unresolved until E0a.

Caveats: one seed per point, a synchronized start, and sim cost constants that are assumed rather than measured.

Files are in /private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/verify_stageC/simcmp/:
- simcmp_stageC.pdf (the overlay figure)
- simcmp.py
- run_log.txt
- main_table_fcfs.csv
- real_recomputed.csv
- real_windows300.csv
- sim_sync_*.csv
---
## critic

## Verdict
The headline survives in qualitative form, but it overstates three things: the shape of the tail, the novelty (is this "metastable" or just oversubscription?), and the LPM causal claim. "Computed" below means I recomputed it in `review_calc.py`. Other numbers are attributed to the check that produced them.

### (a) Verified on the real engine
- **All-miss at n≥48 (FCFS) and n=300 (LPM) is real.** The three sources in Check 2 agree. I also find that the system falls into it starting from a cached state. The fraction of turn≥2 requests that hit before 300 s is 0.64 at F48, 0.28 at F96 and 0.002 at F300. So the cached state does not last at n=48 under this workload, and the collapse is not a measurement artifact.
- **Hit fraction declines as n grows:** 0.93, 0.89, 0.51, 0 at n=20/24/32/48. On the tested grid, μ is unimodal (one seed per point).
- **The workload ran as specified (Checks 1 and 2):** exact prefix continuity (cached = prompt−551), server token IDs, 100 decode tokens, and zero errors or retractions.
- **LPM-300 and FCFS-300 are indistinguishable in aggregate:** μ_turns 0.110 vs 0.111, both with hit 0, and a mean queue of 269 (above 128).

### (b) Plausible but unverified
- **Bistability near the cliff.** F24 has one excursion and recovers. F32 is degraded for about 2000 s, then recovers. There is one run each, and both triggers coincide with the synchronized t=0 cohort, so they may be start-up artifacts rather than spontaneous switches.
- **Peak location, n* between 20 and 28.** The grid (16/20/24/32) is coarse, n=28 was never run, and μ(24) contains a degraded bin.
- **Collapse depth.** I divided the in-window uncached prefill rate by the all-miss tokens per session (154,529; E[T]=14.761). That gives a throughput-implied floor of **0.072 / 0.075 / 0.081 sessions/s** at n=48/96/300, which is 0.32–0.36 of μ_turns(24)=0.226. The measured values are 0.063 / 0.073 / 0.111. If the floor holds at the stationary turn mix, the collapse is about 3×, not about 4.5×. That is unverified, because attention cost grows with prompt length.
- **LPM fallback as the cause at n=300.** At t=0, 300×2000 = 600k tokens already exceeds the 300k pool, so even LPM without the fallback might be all-miss. Only the simulator says it would not be.
- **LPM/FCFS at n=48 = 1.54× by turns.** The two runs were on different nodes (gpu-2 vs gpu-3). LPM-48 is still trending upward, and the FCFS-48 baseline is biased low by the transient.

### (c) Contradicted or unsupported
- **The non-monotone tail (μ(48) < μ(96) < μ(300)) as a property of the system: unsupported.** The throughput-implied floor is nearly flat (0.072 to 0.081). The measured ordering follows which sessions happen to be in flight: the mean in-window prompt is 11,974 tokens at F48 and 7,583 at F300. μ(300) is a start-up transient.
- **"Matching the simulator."** The shape matches, and so do the hit fractions at n≤24. The levels do not: the real/sim ratio ranges from 1.1 to 2.3 (Check 3). The real engine also keeps more hits at n=32 and under LPM-48.
- **The cliff comparison is not on one server.** Going from n=32 to 48 also moves from nova22-gpu-1 to gpu-3.

### The attack a systems reviewer will make
"This is memory oversubscription plus LRU on a cyclic reuse pattern."
- **The cliff location follows from memory alone.** I computed the mean live footprint per session at the stationary mix as 10,568 tokens, so the pool holds M/footprint = **28.4 sessions** (call this n_fit). Hit crosses 0.5 at about 32 (Check 3), 1.13× n_fit. No queueing model is needed to predict where the cliff is.
- **It is Denning's thrashing curve.** This is the multiprogramming thrashing curve (Denning, AFIPS 1968), and the expected baseline is working-set admission control, i.e. the planned capped arm.
- **Where a "metastable" claim has to live.** Oversubscription does not explain behaviour below n_fit (the n=24 excursion, at 0.85 n_fit) or hysteresis. Any metastability claim has to rest on those.
- **The 300k cap is what makes memory the binding limit.**
  - At n=24 the engine prefills only 3.8k uncached tok/s, against 11.1–12.5k in the all-miss runs.
  - The native pool would be roughly 0.9M tokens. That is a rough estimate from logged free memory at 53.4 kB/token, not measured.
  - With that pool, n_fit ≈ 85. By a back-of-envelope estimate the cached state there would demand about 12 turns/s, or about 8k uncached tok/s, close to compute capacity. Whether the cliff survives on the native pool is untested.
  - The hierarchical cache (host offload) was off (`enable_hierarchical_cache: False`).
- **Fidelity.**
  - Prompts are random token IDs with a per-session salt, so sessions share nothing (no common system prompt).
  - Feeding back server token IDs gives perfect prefix reuse, which is optimistic compared with real chat agents that retokenize text.
  - Prompts reach 40,350 tokens, beyond Qwen2.5-7B's native 32k window, so the results only speak to systems behaviour, not model outputs.

### Next experiments (ranked by information per GPU-hour)
Each 2700 s run costs about 0.8 GPU-h on one A100.

1. **All-miss calibration at the stationary mix (an E0a variant), about 0.5–1 GPU-h.** Cache disabled, prompt lengths drawn from the stationary turn-index distribution, about 30 min. This pins the floor and λ_miss, and settles the tail question.
2. **Hysteresis test plus replicates, about 9–10 GPU-h (about 3 h wall on 3 GPUs).** Run n ∈ {24, 28, 32} with 3 seeds each, all on one node, with the server seed pinned. In one replicate per n, inject an eviction burst (a few long one-off prompts) at about 1500 s and see whether hits recover. This is the direct evidence for metastability, and nothing else can stand in for it.
3. **Staggered-start (pre-aged) sessions at n ∈ {48, 96, 300}, about 2.4 GPU-h plus harness work (not implemented yet).** This removes the cohort bias. The alternative, longer runs at n=300, would need more than three session lifetimes (3–4 h per run), which is worse value.
4. **Scaling M, about 5 GPU-h.** Use M ∈ {150k, native}, with n at 0.8, 1.1 and 1.7× n_fit(M). This tests whether hit vs n/n_fit falls on one curve, and whether compute limits arrive before the cliff at native M.
5. **LPM causality, about 4 GPU-h.** Run LPM-300 with the 128-request threshold patched out, plus LPM at n ∈ {96, 128, 160}, plus LPM-48 and FCFS-48 on the same node. Without the patched run, "the fallback causes the degeneration" rests only on reading the code.

The total is about 22 GPU-h, which fits within the 11-GPU per-user cap shared with COMS 6720. Each item needs your approval before any `sbatch`.

Files are in `/private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/verify_stageC/review/`:
- review_calc.py
- review_calc_out.csv
- review_calc_log.txt