# Round 6 Predict: blind simulator predictions for the real-engine experiments (B1 to B4)

Written on branch `r6/validation` by the Predict stage. These are predictions of the calibrated simulator (`calibration/round6_server_log_fit/calibration.yaml`
cost constants, Stage C workload, SGLang-like KV cap 300k unless stated) made **before** seeing any E0a / E0b / E2 real result. The numbers in section 0 were copied from the generated tables in section 4 and checked against them
(section 4 itself is the unedited output of the report script); the tables come from `results/r6_predict_report/20261024-034707/` (code commit `ab02e705956dba4d07d57e9786af7ef613394c1c`)
and the simulation result dirs listed in appendix A.

* **PRIMARY column: `mixed` batching**, the mode the Validate stage picked (lower mean |relative error| of mu, 0.104 vs 0.127; the pick rests on one cell, LPM n = 48).
* **SECONDARY column: `separate_prefill_priority`** (SGLang prefill priority). Both columns are produced by the same spec; only `engine.batching` differs.
* Every simulation call ran on the clean commit **`630ab9edc7f40b33718771b4efb6a52da66b8eb6`** (`meta.json`: `dirty = false` in all 48 dirs). Later commits on this branch changed only the report code,
  the test file and line endings (section 1).
* Registered sizes were run in full (nothing was reduced; the whole set of 48 simulation calls took 4 min 39 s of wall time on the PC). Labelled supplementary runs (more seeds)
  were added because they were cheap; they never enter a headline number.

## 0. Headline predictions

All sessions-per-second values are completed sessions per second. "turns-based" = completed turns per second divided by E[T] = 14.761.

### B1. All-miss capacity (prefix cache disabled, closed population, FCFS, window [900, 2700) s)

| quantity | PRIMARY (mixed) POP = 32, seeds 0-2 | SECONDARY (separate) POP = 32, seeds 0-2 | mixed POP = 64, seed 0 | separate POP = 64, seed 0 |
|---|---|---|---|---|
| completed sessions / s (mean, sd over seeds) | **0.0694** (0.0115) | 0.0689 (0.0112) | 0.0744 | 0.0733 |
| turns / s divided by E[T] = 14.761 (mean, sd) | **0.0722** (0.0019) | 0.0714 (0.0013) | 0.0719 | 0.0711 |
| uncached prefill tokens / s (mean, sd) | **11 220** (94) | 11 147 (101) | 11 280 | 11 153 |
| GPU busy fraction | 1.00 | 1.00 | 1.00 | 1.00 |

Reading: the turns-based value is the low-variance estimator (sd 2.6% against 16.5% for sessions/s over three seeds). **lambda_miss(turns-based, mixed) = 0.0722 sessions/s**
is the reference used for the multiples below and in the B3 trap threshold; the all-miss token rate is 11.2k tokens/s. The two batching modes differ by 1.2% (turns-based) and 0.7% (tokens), POP = 64 is within 0.5% of POP = 32 (turns-based).

### B2. From-empty open-loop stability (cache on, FCFS, Poisson arrivals from an empty cache and queue, horizon 3000 s, seeds 0-2)

Stable runs out of 3 (stable := final backlog < 50 and no upward backlog trend over the last 1500 s):

| lambda (sessions/s) | 0.07 | 0.08 | 0.09 | 0.10 | 0.11 | 0.12 | 0.13 | 0.14 | 0.15 | 0.16 | 0.18 | 0.20 | 0.22 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRIMARY mixed | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 | 2/3 | 2/3 | 0/3 | 0/3 |
| SECONDARY separate | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 1/3 | 2/3 | 0/3 | 0/3 |

* **Predicted from-empty edge (largest lambda with every smaller grid lambda all-stable): 0.14 sessions/s = 1.94 x the B1 turns-based value (mixed)**; separate: 0.15 sessions/s = 2.10 x its own B1 value (0.0714).
* Supplementary, 20 fresh seeds (100-119), labelled: both modes are 20/20 stable from 0.07 to 0.15, 19/20 at 0.16, 15/20 at 0.18, 6/20 at 0.20, 4/20 at 0.22. So with more seeds the all-stable edge is **0.15 in both modes
  (2.08 x / 2.10 x)**, the stable fraction crosses 0.95 at about 0.16 and 0.5 at about 0.191 sessions/s (2.65 x the mixed B1 value). The 3-seed edge of the mixed mode (0.14) is one grid step below
  the 20-seed edge because seed 1 collapses at 0.15 (and again at 0.16 and 0.18); read the edge as "0.14 to 0.15, i.e. about 2 x lambda_miss, with a soft transition from 0.15 to 0.20".
* Every lambda from 0.09 on lies above lambda_miss (0.0722); in the model the system is nonetheless stable from empty up to about twice that rate (hysteresis band), which is exactly what B3 probes.

### B3. E2 paired-arm kill test (lambda in {0.09 ... 0.16}, seeds 0-2, burst of 200 sessions in 60 s at t = 1200 s, cap 20 FIFO gate, evaluation window = last 2500 s of the run)

Counts out of 3 seeds. PASS := BURST trapped, NOBURST good and CAPPED recovered each in >= 2 of 3 seeds.

| lambda | BURST trapped (mixed) | NOBURST good (mixed) | CAPPED recovered (mixed) | **PASS mixed** | BURST trapped (sep) | NOBURST good (sep) | CAPPED recovered (sep) | **PASS sep** |
|---|---|---|---|---|---|---|---|---|
| 0.09 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.10 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.11 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.12 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.13 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.14 | 3 | 3 | 3 | **PASS** | 3 | 3 | 3 | **PASS** |
| 0.16 | 3 | 2 | 3 | **PASS** | 3 | 2 | 3 | **PASS** |

* **Prediction: the kill test PASSES at all seven lambda in both modes** (6 of 7 with all three seeds; at 0.16 one NOBURST seed, seed 2, is itself trapped from empty, in both modes).
* Trapped BURST runs (both modes, all 42 registered BURST runs): hit rate 0, uncached-prefill token rate 0.999 to 1.065 x the B1 all-miss rate of the same mode (the ratio grows with lambda: about 1.00 at 0.09 to 1.06 at 0.16),
  backlog slope 0.012 to 0.077 requests/s (always above the 0.5 (lambda - lambda_miss) threshold, which runs from 0.009 at 0.09 to 0.044 at 0.16), mean backlog over the evaluation window 171 to 523 waiting requests (rising with lambda). The slope margin is smallest at lambda = 0.09.
* NOBURST-good and CAPPED-recovered runs: hit rate 0.929 to 0.937, mean backlog at most 0.13 (NOBURST) and 1.03 (CAPPED) requests; the CAPPED arm is indistinguishable from NOBURST in the evaluation window.
* Fragility, stated plainly (supplementary runs and window sensitivities are in section 4): (a) the lambda = 0.09 verdict depends on the evaluation window (on the last 1500 s only 1 of 3 mixed BURST runs satisfies the slope test, PASS False; 20-seed supplement: BURST trapped 14/20 mixed, 15/20 separate, because
  the slope margin 0.5 (0.09 - 0.0722) is only 0.009 requests/s); (b) at lambda = 0.16 NOBURST good is 15/20 (mixed) and 13/20 (separate) with 20 seeds, so the separate column would **fail** PASS there in the 20-seed supplement (need 14).
  No BURST run recovered and no CAPPED run was trapped in any of the 840 + 126 runs.

### B4. Native-pool curves (Stage C closed protocol, FCFS, seed 0; hit = hits / admitted turns)

`mu sessions/s (hit)`, mixed (primary); the separate column and the turns-based values are in section 4. 300k is the validation cell rerun (bit-identical to the validated numbers).

| n | 300k | 600k | 900k |
|---|---|---|---|
| 16 | 0.183 (0.93) | 0.183 (0.93) | 0.183 (0.93) |
| 24 | 0.226 (0.91) | 0.254 (0.93) | 0.254 (0.93) |
| 32 | 0.154 (0.62) | 0.329 (0.93) | 0.329 (0.93) |
| 48 | 0.076 (0.00) | 0.406 (0.92) | 0.438 (0.93) |
| 64 | 0.072 (0.00) | 0.105 (0.315) | 0.523 (0.93) |
| 96 | 0.071 (0.00) | 0.073 (0.00) | 0.079 (0.05) |
| 300 | 0.106 (0.00) | 0.108 (0.00) | 0.109 (0.00) |

* The collapse point scales roughly with the pool: 0.5-hit crossing n = 35.1 / 59.1 / 79.7 for 300k / 600k / 900k (seed 0, mixed; 5-seed means 31.1 / 58.1 / 80.7; separate 35.7 / 63.7 / 82.4). The cliff is steep: the hit fraction goes from 0.92 to 0.3 between n = 48 and 64 at 600k,
  and from 0.93 to 0.05 between n = 64 and 96 at 900k (grid is coarse; the cliff lies inside those intervals).
* Peak sessions/s on this grid: 600k about 0.41 at n = 48 (5-seed mean 0.42), 900k about 0.52 at n = 64 (0.51); 300k 0.23 at n = 24. The peak is the last grid point before the cliff, so it is a lower bound of the true peak.
* The cliff cell is bistable (n = 64 at 600k: 5-seed mu 0.096 +- 0.041 (sd), hit 0.25; n = 96 at 900k: 0.085 +- 0.033, hit 0.10), so a single real run there can land on either side; at 300k n = 32 is the same kind of cell.
* All-miss tail: mu(n = 300) = 0.106 to 0.109 sessions/s regardless of the pool (all-miss; 0.104 to 0.111 for separate).
* Mode effect (separate vs mixed, seed 0): within 5% of mu everywhere except the cliff cells: 600k n = 64 (separate 0.128 vs mixed 0.105; hit 0.49 vs 0.31) and 900k n = 96 (0.088 vs 0.079; hit 0.18 vs 0.05); the separate mode keeps more cache near the cliff, as in the validation.

### How far to trust the levels (from the Validate stage, `calibration/round6_server_log_fit/VALIDATION.md`)

The validation said NO on the declared level test for both modes (FCFS n = 48 over-predicted by 42%: simulated all-miss floor 0.070 sessions/s vs real 0.049; n = 96 by 14.5%), while the plateau (n = 16 to 24, within 9%) and the n = 300 tail (within 2%)
matched, and the hit-fraction curve and its 0.5 crossing (32.5 vs 32.2) matched. Consequences for reading B1 to B4: quantities that depend on the all-miss level (B1, the B2 multiples, B3 trap threshold, B4 values at n >= 96 and 300k n >= 48) can
sit up to tens of percent above the real engine when the real run dips below the all-miss floor; quantities fixed by the cache/pool geometry (hit crossings, the factor-of-two growth of the cliff with the pool) are the better-supported predictions.

## 1. What was run

| item | value |
|---|---|
| branch | `r6/validation` (never pushed; HEAD detached at the end of the stage) |
| commits | `630ab9e` = spec `configs/r6_predict.yaml`, driver `experiments/r6_predict_run.sh`, analysis `src/prefixmeta/r6_predict.py`, tests `tests/test_r6_predict.py`; **all 48 simulation calls ran on it, clean tree**. `24d1fcf` = report code only (B4 landmarks table, compact B4 layout). `22852f1` = line endings of the driver and the test file normalised to LF (the driver ran with CRLF line endings under Git Bash and worked; no content change). `ab02e70` = the per-run CSV of the 20-seed B3 supplement written by the report (analysis only). The commit that adds this file also force-adds the result summaries. The report dir records the commit it ran on (`ab02e705956dba4d07d57e9786af7ef613394c1c`, clean tree). |
| spec | `configs/r6_predict.yaml` (base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; engine = `calibration/round6_server_log_fit/calibration.yaml` engine block, sha256 `284c2dee1a08c8735cf026508808b72ad7b4005939fa25403912d8d8b6b9da8c`) |
| result dirs | the 48 simulation dirs of appendix A under `results/prefix_meta_probe_<cmd>_<tag>/<timestamp>/`; the report `results/r6_predict_report/20261024-034707/` (tables.md, summary.json, CSV tables, meta.json); `results/r6_predict/manifest.tsv` (tag to dir), `run_all.log` (driver log), `report_stdout.txt`, `full_suite_pytest.log` |
| wall time | driver 2026-10-24 03:23:56 to 03:28:35 (4 min 39 s) for all 48 calls (about 166 s of recorded run wall time), at most 6 worker processes per call |
| machine | Windows 11 Home PC (hostname Akshat-PC, 10 cores), Python 3.12.10, NumPy 1.26.4, SciPy 1.13.1, pandas 2.2.2, interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`. (`meta.json` `hardware` reads "Apple M3 Max CPU (simulation)": a hard-coded constant in `runner.HARDWARE`, wrong for this PC; `hostname` and `versions.platform` are right.) |

Seeds: B1 POP = 32: 0, 1, 2; B1 POP = 64: 0. B2: 0, 1, 2 (supplement 100-119). B3: 0, 1, 2 (supplement 100-119). B4: 0 (supplement 1-4, shown as "seeds 0-4 mean").
Common random numbers: for a seed the Poisson arrival stream and the sessions' turn counts and tool times are shared by the three B3 arms; the burst is an extra stream, so NOBURST and BURST differ by exactly the burst, and CAPPED differs from BURST only by the cap.

Commands (from the worktree root in Git Bash; `PY` is the interpreter above). The whole prediction set is one driver call, whose expansion into the 48 exact probe commands is appendix A:

```
bash experiments/r6_predict_run.sh > results/r6_predict/run_all.log 2>&1
PYTHONPATH="src;." $PY -m prefixmeta.r6_predict report --spec configs/r6_predict.yaml --manifest results/r6_predict/manifest.tsv
```

## 2. Setup: what is identical to the Validate stage and what is not

Identical (a test, `tests/test_r6_predict.py::test_engine_is_the_validation_primary_arm_engine_in_both_batching_modes`, asserts the effective engine of the spec equals the validation's PRIMARY arm for both batching modes, and the workload and metric windows): base config chain,
the calibration engine block (`full_reserve`, finished-session KV freed at once, `kv_memory_tokens` 300000 unless stated), the Stage C workload (2000-token first prompt, +550 tool tokens, 100 decoded tokens, T ~ min(Geom(1/15), 60), tool time Exp(5 s)), FCFS with LRU eviction,
100 s metric windows, closed protocol [900, 2700) s with synchronized start and a 5000-session replacement pool. The B4 300k column reproduces the validation's seed-0 cells **bit for bit** (mu and hit rate, n = 16, 24, 32, 48, 96, 300, both modes; compared against
`results/r6_validate_stagec/20261024-025222/runs.csv`).

Differences (all deliberate):
1. B1 runs with `cache_enabled: false` (all-miss capacity). B4 runs with `engine.kv_memory_tokens` 600000 and 900000 (the validation only used 300000).
2. `metrics.tail_window_s: 2500` (the base has 5000): it only changes the `tail_*` summary columns of the runs, not the dynamics; it makes the probe's own tail columns coincide with the B3 evaluation window (checked: the classification code's hit rate and backlog agree with the probe's `hit_eval` and `tail_backlog_mean` to 1e-13).
3. `parallel.max_workers: 6` in the spec (the validation needed `--set parallel.max_workers=6` for the same effect).
4. The secondary column is selected with `--set engine.batching=separate_prefill_priority` instead of the validation's arm table; the PRIMARY column has `batching: mixed` written explicitly in the spec (the default, bit-identical).
5. The open-loop (B2) and burst (B3) runs use the probe runner's `open` and `burst` commands, which the validation did not exercise; the validation validated only the closed curve.

## 3. Definitions fixed before any prediction run (declared in `configs/r6_predict.yaml`, `predict:` block)

The brief leaves a few operational details open. I fixed them before the runs (the spec and code were committed first, `630ab9e`), did not change them afterwards, and report sensitivities where a choice could matter. If the lead researcher reads any of these differently,
the per-run CSVs (`b3_runs.csv`, `b3_supp20_runs.csv`) allow re-classification without a new simulation.

1. **"Post-burst" evaluation window** = the last 2500 s of the run, i.e. [t_burst + 5000, t_burst + 7500) = [6200, 8700) s; the NOBURST arm is evaluated on the same absolute window. Sensitivity windows (last 1500 s, last 5000 s) are reported but never used for the verdict.
2. **lambda_miss** in the TRAPPED slope threshold = the B1 turns-based value (POP = 32, 3-seed mean) of the same batching mode: 0.072187 (mixed), 0.071359 (separate) sessions/s. The **all-miss token rate** = the B1 POP = 32 3-seed mean of the mean per-window `prefill_tok_per_s`
   (prefill tokens processed per second; with the cache off these are all uncached): 11 219.7 (mixed), 11 146.8 (separate) tokens/s. The B3 token rate is the same quantity over the evaluation window (it counts the new-token prefills of hits too, so it is "uncached prefill tokens").
3. **Backlog** = waiting queue + gate queue (mean per 100 s window); **backlog slope** = OLS slope of that series against the window centre over the 25 windows of the evaluation window, in requests per second, compared with 0.5 (lambda - lambda_miss) in sessions per second
   (in the trapped state one waiting request corresponds to one session). The slope must exceed the threshold.
4. **TRAPPED** := |token rate / B1 all-miss token rate - 1| <= 0.15 AND backlog slope > 0.5 (lambda - lambda_miss). **RECOVERED** := hit rate in the window > 0.8 AND mean backlog < 20 (the probe's `recovered` thresholds). Neither: "neither". In the 126 registered B3 runs 44 are TRAPPED, 82 RECOVERED, none "neither" or both.
5. **NOBURST "good"** := the RECOVERED test on the NOBURST arm.
6. **">= 2/3 seeds"** is applied to each of the three conditions separately (>= ceil(2/3 x 3) = 2 of 3 seeds); `PASS_all_seeds` (all three seeds for every condition) is reported next to it.
7. **B2 stable** = not early-stopped, final backlog < 50 and the OLS rise of the 100 s backlog means over the last 1500 s <= 10 requests (the probe's default `stable_trend_max_rise`); the **edge** = the largest grid lambda such that every smaller grid lambda is all-stable (3 of 3). The largest all-stable lambda irrespective of contiguity is also reported (identical here).
8. **B4**: hit = hits / admitted turns in the window; `mu` = sessions completed in [900, 2700) / 1800; turns-based `mu` = completed turns / s / 14.761.

## 4. Tables (generated by `python -m prefixmeta.r6_predict report`; nothing retyped)


### B1. All-miss capacity (cache disabled, closed population, FCFS, window [900, 2700) s)

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

### B2. From-empty open-loop stability (cache on, FCFS, horizon 3000 s, seeds 0-2)

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

### B3. E2 paired arms (lambda grid, seeds 0-2; eval window = last 2500 s)

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

### B4. Closed-population curves with a larger KV pool (cache on, FCFS)

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


## 5. How to read the predictions

* The registered statistics use 3 seeds (B1 to B3) or 1 seed (B4), as specified. For single cells that sit near a transition the 3-seed answer is noisy by construction; the labelled 20-seed (B2, B3) and 5-seed (B4) supplements say how much. They never replaced a registered number.
* B2 and B3 are about the same hysteresis: the from-empty system is stable up to about 2 x lambda_miss (B2), while a 200-session burst traps it at every lambda from 0.09 (1.25 x lambda_miss) to 0.16 (2.2 x), and a cap of 20 releases it (B3). A real run that shows a trap
  at lambda < 0.14 with a stable no-burst arm is the predicted outcome; a real NOBURST arm that is already unstable at or below 0.12, or a BURST arm that recovers, would contradict the model.
* The mixed and separate columns agree on B1 (1%), on the B3 verdicts (registered seeds), and on B4 (5%) except at the cliff cells; they differ by one grid step in the 3-seed B2 edge (0.14 vs 0.15), which the 20-seed supplement removes (0.15 in both).
* The Validate stage found the simulator's all-miss level above the real FCFS n = 48 and n = 96 cells (see "How far to trust the levels" above). If the real all-miss capacity is lower than B1, the B2 edge multiple and the B3 trap threshold shift with it; B3's trapped-versus-recovered
  contrast needs lambda above the real lambda_miss; the grid starts at 0.09, so it holds at every grid point if the real all-miss capacity is below 0.09 sessions/s.

## 6. Blindness: what was and was not used

**Not used, not read:** any E0a, E0b or E2 data (no `results/nova/e0a_*`, `e0b_*`, no E2 dir, no number from them seen); no real-engine result of any kind was opened in this stage (not even Stage 0 or Stage C: the real Stage C numbers that appear in this
document are those quoted in the task text and in `VALIDATION.md`); `notes/LOG.md` and `notes/STATE.md` were not opened and are unchanged (so no log entry dated 2026-10-23 or later was read); the main checkout
`C:/Users/Akshat/Desktop/Claude Code/Nova-Research` and every other worktree were not entered or read; `~/.ssh` was not read; nothing touched the Nova cluster (no ssh, scp, rsync, squeue, sacct or sbatch).

**Every file I read** (in the worktree `C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/predict`; all by `cat`, `sed -n`, `grep` or the Read tool unless stated):
`CLAUDE.md`; `pytest.ini`; `calibration/round6_server_log_fit/VALIDATION.md`; `calibration/round6_server_log_fit/calibration.yaml`; `configs/r6_validate_stagec.yaml`; `configs/prefix_meta_probe.yaml`; `configs/prefix_meta_r5.yaml`; `configs/prefix_meta.yaml`;
`experiments/prefix_meta_probe_run.py`; `experiments/prefix_meta_r6_validate_stagec.py`; `src/prefixmeta/probe.py`; `src/prefixmeta/r6_validate.py` (lines 1 to 260, 364 to 390 and 440 to 551); `src/prefixmeta/mech_runner.py` (lines 30 to 275);
`src/prefixmeta/metrics.py`; `src/prefixmeta/sim.py`; `src/prefixmeta/workload.py` (lines 1 to 200); `src/prefixmeta/runner.py` (lines 20 to 200); `src/prefixmeta/r4_runner.py` (lines 51 to 110); `src/prefixmeta/r5_runner.py` (lines 275 to 325);
`src/prefixmeta/engine.py` (grep for gate / session cap / prefill-token lines, then lines 1055 to 1100 and 1810 to 1870); `tests/test_r6_validate.py` (lines 1 to 200); the persisted copy of the `VALIDATION.md` listing under `C:/Users/Akshat/.claude/projects/.../tool-results/`.
Directory listings (names only, no content) of the repository root, `notes/`, `configs/` and `calibration/round6_server_log_fit/`; a function-name grep of `src/prefixmeta/{mech_runner,metrics,r5_runner,runner,workload,sim}.py`.
Simulation outputs read (all produced in this stage): the 48 result dirs of appendix A and the report dir. One earlier simulation output was read for a bit-identity check: `results/r6_validate_stagec/20261024-025222/runs.csv` (the Validate stage's own run, seed-0 primary-arm FCFS cells).
Files written by me: `configs/r6_predict.yaml`, `experiments/r6_predict_run.sh`, `src/prefixmeta/r6_predict.py`, `tests/test_r6_predict.py`, this file, and the result dirs.

**Disclosure about a pilot.** Before the registered runs I ran the B3 burst command once at lambda = 0.16 (mixed, 3 seeds, 9 runs) into the session scratchpad, only to time it (3 s of wall time). The command printed the probe's own arm table, which I saw; it showed the same counts as the registered
lambda = 0.16 mixed row (NOBURST trapped in 1 of 3, BURST trapped 3 of 3, CAPPED recovered 3 of 3). All definitions in section 3 were fixed before that pilot; nothing was changed after it. The pilot output is not cited. The tests also run tiny simulations in temporary directories.

## 7. Tests

* New: `tests/test_r6_predict.py` (12 tests): spec equals the Validate stage's primary-arm engine in both batching modes, workload and windows equal, driver grids, hand-computed cases for edge, `eval_stats`, `classify`, the PASS rule, the manifest check, B4 landmarks, and a tiny end-to-end run
  (probe calls for every tag of the report in both modes, then `report`, including the cross-check against the probe's own columns). 12 passed, also after the last code commit (`ab02e70`).
* Full suite (`$PY -m pytest -q -p no:cacheprovider`, commit `22852f1`, log `results/r6_predict/full_suite_pytest.log`, about 14 min): **1017 passed, 32 failed, 2 skipped, 0 errors**. The summary line itself is not printed (`pytest.ini` adds `-q` and the command added another), so the counts come from the progress characters and the 32 `FAILED` lines
  (1017 = the Validate stage's 1005 passed + the 12 new tests; the 32 failed and 2 skipped are exactly the Validate stage's).
* All 32 failures are on the known platform list and are the same families as in the Validate stage: 6 `test_full_reserve_is_bit_identical_to_the_round4_engine[*]`, 12 `test_mixed_mode_is_bit_identical_to_the_engine_before_the_option[*]` (the brief says 13; the file defines 12 and all 12 fail, so 18 bit-identity failures, not 19),
  8 `test_slurm_scripts.py` (5 `test_job_glue_runs_locally_against_the_mock_server`, `test_cap_and_burst_refuse_hardware_that_differs_from_the_calibration`, `test_burst_refuses_to_start_without_a_valid_prereg`, `test_a_flush_that_answers_200_but_does_not_empty_the_cache_is_caught`),
  2 `test_agentload_e2e.py` (`test_burst_timing_in_the_log`, `test_sessions_and_planned_turns`), 1 `test_agentload_gate.py::test_gate_waits_are_logged_and_fifo`, 2 `test_agentload_robustness.py` (`test_sigterm_finalizes_meta_and_sessions`, `test_raise_nofile_reports_what_happened`),
  1 `test_mech_runner.py::test_pre_full_run_table_marks_runs_before_and_after_the_amendment_commit`. `test_analysis_pipeline.py::test_stable_cli` is on the brief's list but passed here (as in the Validate stage). No failure outside the known list.

## 8. Deviations and open issues

* Nothing in the registered design was reduced or dropped: B1 (POP = 32 seeds 0 to 2, POP = 64 seed 0), B2 (13 lambda x 3 seeds), B3 (7 lambda x 3 seeds x 3 arms), B4 (7 populations x 2 pools, seed 0), each in both batching modes; plus the B4 300k reference, the 20-seed B2 and B3 supplements and B4 seeds 1 to 4.
* Interpretation choices where the brief was open (section 3): evaluation window, lambda_miss for the slope threshold, NOBURST "good", the reading of ">= 2/3 seeds", the contiguous edge. I did not stop to ask because they are operational details and the per-run CSVs allow any other reading to be recomputed, but they are the lead researcher's to overrule.
* The report entry point has no `experiments/` wrapper; run it as `PYTHONPATH="src;." $PY -m prefixmeta.r6_predict report ...`.
* The simulation driver was committed with CRLF line endings under Git Bash and still ran correctly; it was normalised to LF afterwards (`22852f1`). The report code was extended after the simulations (B4 landmarks, per-run CSV of the 20-seed B3 supplement); the simulation code and engine were untouched by this stage.
* `meta.json` `hardware` is the wrong hard-coded string (see section 1).
* Not committed because of size: `windows.csv` of the two 20-seed supplement parts (b2s, b3s; 25 MB) and all `qtrace.csv` files. Everything the tables need is committed: the supplement verdicts and per-run classification are in the report dir (`b3_supp20_runs.csv`, `b2_supp20_table.csv`), the stable verdicts in each `open_verdicts.csv`.
* The B4 grid is the registered coarse one (16, 24, 32, 48, 64, 96, 300), so peaks and cliff positions are known only to within the grid; a finer grid (as in the Validate stage's supplement) was not requested and not run.

## Appendix A. Simulation result dirs, seeds, wall time, and the exact commands

Manifest: `results/r6_predict/manifest.tsv`. Each call: `$PY experiments/prefix_meta_probe_run.py <cmd> --spec configs/r6_predict.yaml --workers 6 --tag <tag> [--set ...]` from the worktree root, on the clean commit `630ab9e`.

| part | probe cmd | tag | result dir (under the worktree root) | commit | dirty | seeds | wall s |
|---|---|---|---|---|---|---|---|
| b1 | curve | `r6pred_b1pop32_mixed` | `results/prefix_meta_probe_curve_r6pred_b1pop32_mixed/20261024-032359` | 630ab9e | False | [0, 1, 2] | 2.4 |
| b1 | curve | `r6pred_b1pop64_mixed` | `results/prefix_meta_probe_curve_r6pred_b1pop64_mixed/20261024-032403` | 630ab9e | False | [0] | 2.3 |
| b4 | curve | `r6pred_b4_kv300k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4_kv300k_mixed/20261024-032408` | 630ab9e | False | [0] | 2.7 |
| b4 | curve | `r6pred_b4_kv600k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4_kv600k_mixed/20261024-032413` | 630ab9e | False | [0] | 2.7 |
| b4 | curve | `r6pred_b4_kv900k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4_kv900k_mixed/20261024-032418` | 630ab9e | False | [0] | 2.9 |
| b4s | curve | `r6pred_b4s_kv300k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4s_kv300k_mixed/20261024-032423` | 630ab9e | False | [1, 2, 3, 4] | 2.8 |
| b4s | curve | `r6pred_b4s_kv600k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4s_kv600k_mixed/20261024-032429` | 630ab9e | False | [1, 2, 3, 4] | 3.1 |
| b4s | curve | `r6pred_b4s_kv900k_mixed` | `results/prefix_meta_probe_curve_r6pred_b4s_kv900k_mixed/20261024-032434` | 630ab9e | False | [1, 2, 3, 4] | 3.3 |
| b2 | open | `r6pred_b2_mixed` | `results/prefix_meta_probe_open_r6pred_b2_mixed/20261024-032440` | 630ab9e | False | [0, 1, 2] | 3.1 |
| b2s | open | `r6pred_b2s20_mixed` | `results/prefix_meta_probe_open_r6pred_b2s20_mixed/20261024-032445` | 630ab9e | False | 100..119 (20) | 5.7 |
| b3 | burst | `r6pred_b3_lam0.09_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.09_mixed/20261024-032453` | 630ab9e | False | [0, 1, 2] | 3.0 |
| b3 | burst | `r6pred_b3_lam0.10_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.10_mixed/20261024-032459` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.11_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.11_mixed/20261024-032504` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.12_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.12_mixed/20261024-032509` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.13_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.13_mixed/20261024-032515` | 630ab9e | False | [0, 1, 2] | 3.0 |
| b3 | burst | `r6pred_b3_lam0.14_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.14_mixed/20261024-032520` | 630ab9e | False | [0, 1, 2] | 3.0 |
| b3 | burst | `r6pred_b3_lam0.16_mixed` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.16_mixed/20261024-032525` | 630ab9e | False | [0, 1, 2] | 3.1 |
| b3s | burst | `r6pred_b3s20_lam0.09_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.09_mixed/20261024-032531` | 630ab9e | False | 100..119 (20) | 4.2 |
| b3s | burst | `r6pred_b3s20_lam0.10_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.10_mixed/20261024-032537` | 630ab9e | False | 100..119 (20) | 4.4 |
| b3s | burst | `r6pred_b3s20_lam0.11_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.11_mixed/20261024-032544` | 630ab9e | False | 100..119 (20) | 4.5 |
| b3s | burst | `r6pred_b3s20_lam0.12_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.12_mixed/20261024-032551` | 630ab9e | False | 100..119 (20) | 4.8 |
| b3s | burst | `r6pred_b3s20_lam0.13_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.13_mixed/20261024-032558` | 630ab9e | False | 100..119 (20) | 4.8 |
| b3s | burst | `r6pred_b3s20_lam0.14_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.14_mixed/20261024-032605` | 630ab9e | False | 100..119 (20) | 4.8 |
| b3s | burst | `r6pred_b3s20_lam0.16_mixed` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.16_mixed/20261024-032612` | 630ab9e | False | 100..119 (20) | 5.0 |
| b1 | curve | `r6pred_b1pop32_sep` | `results/prefix_meta_probe_curve_r6pred_b1pop32_sep/20261024-032620` | 630ab9e | False | [0, 1, 2] | 2.4 |
| b1 | curve | `r6pred_b1pop64_sep` | `results/prefix_meta_probe_curve_r6pred_b1pop64_sep/20261024-032625` | 630ab9e | False | [0] | 2.3 |
| b4 | curve | `r6pred_b4_kv300k_sep` | `results/prefix_meta_probe_curve_r6pred_b4_kv300k_sep/20261024-032629` | 630ab9e | False | [0] | 2.6 |
| b4 | curve | `r6pred_b4_kv600k_sep` | `results/prefix_meta_probe_curve_r6pred_b4_kv600k_sep/20261024-032634` | 630ab9e | False | [0] | 2.7 |
| b4 | curve | `r6pred_b4_kv900k_sep` | `results/prefix_meta_probe_curve_r6pred_b4_kv900k_sep/20261024-032639` | 630ab9e | False | [0] | 2.7 |
| b4s | curve | `r6pred_b4s_kv300k_sep` | `results/prefix_meta_probe_curve_r6pred_b4s_kv300k_sep/20261024-032644` | 630ab9e | False | [1, 2, 3, 4] | 2.9 |
| b4s | curve | `r6pred_b4s_kv600k_sep` | `results/prefix_meta_probe_curve_r6pred_b4s_kv600k_sep/20261024-032650` | 630ab9e | False | [1, 2, 3, 4] | 2.9 |
| b4s | curve | `r6pred_b4s_kv900k_sep` | `results/prefix_meta_probe_curve_r6pred_b4s_kv900k_sep/20261024-032655` | 630ab9e | False | [1, 2, 3, 4] | 3.1 |
| b2 | open | `r6pred_b2_sep` | `results/prefix_meta_probe_open_r6pred_b2_sep/20261024-032700` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b2s | open | `r6pred_b2s20_sep` | `results/prefix_meta_probe_open_r6pred_b2s20_sep/20261024-032706` | 630ab9e | False | 100..119 (20) | 5.3 |
| b3 | burst | `r6pred_b3_lam0.09_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.09_sep/20261024-032713` | 630ab9e | False | [0, 1, 2] | 2.8 |
| b3 | burst | `r6pred_b3_lam0.10_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.10_sep/20261024-032718` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.11_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.11_sep/20261024-032724` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.12_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.12_sep/20261024-032729` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.13_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.13_sep/20261024-032734` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.14_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.14_sep/20261024-032739` | 630ab9e | False | [0, 1, 2] | 2.9 |
| b3 | burst | `r6pred_b3_lam0.16_sep` | `results/prefix_meta_probe_burst_r6pred_b3_lam0.16_sep/20261024-032745` | 630ab9e | False | [0, 1, 2] | 3.0 |
| b3s | burst | `r6pred_b3s20_lam0.09_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.09_sep/20261024-032750` | 630ab9e | False | 100..119 (20) | 4.1 |
| b3s | burst | `r6pred_b3s20_lam0.10_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.10_sep/20261024-032756` | 630ab9e | False | 100..119 (20) | 4.2 |
| b3s | burst | `r6pred_b3s20_lam0.11_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.11_sep/20261024-032803` | 630ab9e | False | 100..119 (20) | 4.4 |
| b3s | burst | `r6pred_b3s20_lam0.12_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.12_sep/20261024-032810` | 630ab9e | False | 100..119 (20) | 4.5 |
| b3s | burst | `r6pred_b3s20_lam0.13_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.13_sep/20261024-032816` | 630ab9e | False | 100..119 (20) | 4.6 |
| b3s | burst | `r6pred_b3s20_lam0.14_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.14_sep/20261024-032823` | 630ab9e | False | 100..119 (20) | 4.6 |
| b3s | burst | `r6pred_b3s20_lam0.16_sep` | `results/prefix_meta_probe_burst_r6pred_b3s20_lam0.16_sep/20261024-032830` | 630ab9e | False | 100..119 (20) | 4.9 |

```
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b1pop32_mixed --set engine.batching=mixed
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b1pop64_mixed --set engine.batching=mixed --set 'probe.curve.n_grid=[64]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv300k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=300000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv600k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=600000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv900k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=900000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv300k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=300000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv600k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=600000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv900k_mixed --set engine.batching=mixed --set engine.kv_memory_tokens=900000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py open --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b2_mixed --set engine.batching=mixed
$PY experiments/prefix_meta_probe_run.py open --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b2s20_mixed --set engine.batching=mixed --set 'probe.open.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.09_mixed --set engine.batching=mixed --set probe.burst.lambda=0.09
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.10_mixed --set engine.batching=mixed --set probe.burst.lambda=0.10
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.11_mixed --set engine.batching=mixed --set probe.burst.lambda=0.11
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.12_mixed --set engine.batching=mixed --set probe.burst.lambda=0.12
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.13_mixed --set engine.batching=mixed --set probe.burst.lambda=0.13
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.14_mixed --set engine.batching=mixed --set probe.burst.lambda=0.14
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.16_mixed --set engine.batching=mixed --set probe.burst.lambda=0.16
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.09_mixed --set engine.batching=mixed --set probe.burst.lambda=0.09 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.10_mixed --set engine.batching=mixed --set probe.burst.lambda=0.10 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.11_mixed --set engine.batching=mixed --set probe.burst.lambda=0.11 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.12_mixed --set engine.batching=mixed --set probe.burst.lambda=0.12 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.13_mixed --set engine.batching=mixed --set probe.burst.lambda=0.13 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.14_mixed --set engine.batching=mixed --set probe.burst.lambda=0.14 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.16_mixed --set engine.batching=mixed --set probe.burst.lambda=0.16 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b1pop32_sep --set engine.batching=separate_prefill_priority
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b1pop64_sep --set engine.batching=separate_prefill_priority --set 'probe.curve.n_grid=[64]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv300k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=300000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv600k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=600000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4_kv900k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=900000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[0]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv300k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=300000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv600k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=600000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py curve --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b4s_kv900k_sep --set engine.batching=separate_prefill_priority --set engine.kv_memory_tokens=900000 --set probe.curve.cache_enabled=true --set 'probe.curve.n_grid=[16,24,32,48,64,96,300]' --set 'probe.curve.seeds=[1,2,3,4]'
$PY experiments/prefix_meta_probe_run.py open --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b2_sep --set engine.batching=separate_prefill_priority
$PY experiments/prefix_meta_probe_run.py open --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b2s20_sep --set engine.batching=separate_prefill_priority --set 'probe.open.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.09_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.09
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.10_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.10
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.11_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.11
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.12_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.12
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.13_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.13
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.14_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.14
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3_lam0.16_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.16
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.09_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.09 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.10_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.10 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.11_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.11 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.12_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.12 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.13_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.13 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.14_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.14 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
$PY experiments/prefix_meta_probe_run.py burst --spec configs/r6_predict.yaml --workers 6 --tag r6pred_b3s20_lam0.16_sep --set engine.batching=separate_prefill_priority --set probe.burst.lambda=0.16 --set 'probe.burst.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
```
