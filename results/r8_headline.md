Written on branch `r8/native-predict` (never pushed, never merged). These are the predictions of the calibrated simulator for the real-engine native-KV-pool experiments, made **before any real native-pool result was seen**: the only real fact used is SGLang's own pool size with no KV cap, `max_total_num_tokens = 955,757` tokens (A100 80GB PCIe, Qwen2.5-7B, the record workload's 49,152-token context). Everything else is the round-7 calibrated simulator unchanged (round-6 cost constants, `full_reserve`, finished-session KV freed at once, record workload: 2000-token first prompt, +550 tool tokens, 100 decoded tokens, turns min(Geometric(1/15), 60), tool times Exp(5 s)); the one edit to the engine block is `kv_memory_tokens` 300000 -> 955757. The spec `configs/r8_native_predict.yaml` was committed (`29728e3`, sha256 `b808dd76a5cbd7891f13aeef731ce6cb740ffb49800f478ab65eeb6305fe5c0d`) **before any run**; the driver, report module and tests were committed next (`0336c91`), and all ten simulation stages (five per batching mode) ran on that clean commit. A later commit (`09b541d`) only added a run-by-run consistency check to the report module and regenerated the tables from the same stage dirs. Everything the task asked for ran in full, nothing was cut: the whole driver took 53 s of wall time (recorded stage wall time 19 s mixed, 18 s separate).

* **PRIMARY column: `mixed` batching** (the mode the round-6 validation picked). **SECONDARY: `separate_prefill_priority`**, the same spec with `--set engine.batching=separate_prefill_priority`. Each mode uses its own multiples of its own lambda_miss.
* All sessions-per-second values are completed sessions per second. "Turns-based" = completed turns per second divided by E[T] = 14.761 (the low-variance estimator, used for every multiple, the argmax and the cap).
* Every fraction in the tables carries a Wilson 95% interval; B2n and B3n use 10 seeds, B1n and B4n 3 seeds.

## 0. Headline predictions

### B1n. All-miss capacity (cache off, closed POP 32, 900 s warm-up + 1800 s window, 3 seeds)

| quantity | PRIMARY (mixed) | SECONDARY (separate) |
|---|---|---|
| **lambda_miss, turns-based (sessions/s)** (sd over 3 seeds) | **0.0720** (0.0013) | 0.0714 (0.0006) |
| lambda_miss, sessions-based (sessions/s) | 0.0698 | 0.0700 |
| all-miss prefill token rate (tokens/s) | 11 239 | 11 180 |
| GPU busy fraction | 1.00 | 1.00 |
| POP 64, turns-based (sessions/s) | 0.0737 | 0.0731 |

The larger pool does not move the all-miss capacity: round 6 gave 0.0722 (mixed) and 0.0714 (separate) at the 300k pool (`notes/PREDICTIONS.md` section 0, B1).

### B4n. Closed curve mu(n) and hit fraction (cache on, 3 seeds, window [900, 2700) s, synchronized start)

mu = turns-based sessions/s (mean of 3 seeds) / hit fraction, from the generated table below:

| n | 16 | 24 | 32 | 48 | 64 | 72 | 80 | 88 | 96 | 112 | 128 | 160 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed | 0.176 / 0.93 | 0.254 / 0.93 | 0.325 / 0.93 | 0.438 / 0.93 | 0.512 / 0.93 | **0.537 / 0.93** | 0.509 / 0.92 | 0.269 / 0.79 | 0.143 / 0.42 | 0.074 / 0.00 | 0.077 / 0.00 | 0.084 / 0.00 | 0.111 / 0.00 |
| separate | 0.175 / 0.93 | 0.251 / 0.93 | 0.319 / 0.93 | 0.425 / 0.93 | 0.491 / 0.93 | **0.513 / 0.93** | 0.498 / 0.92 | 0.295 / 0.81 | 0.159 / 0.49 | 0.078 / 0.06 | 0.076 / 0.00 | 0.083 / 0.00 | 0.108 / 0.00 |

| landmark | PRIMARY (mixed) | SECONDARY (separate) |
|---|---|---|
| **peak n** (first argmax of the seed-mean turns-based mu) | **72** | 72 |
| **peak mu** (turns-based sessions/s; sessions-based in brackets) | **0.537** (0.532) | 0.513 (0.507) |
| hit fraction at the peak | 0.933 | 0.933 |
| **n at which the seed-mean hit fraction falls through 0.5** | **94.2** (per seed 97.4, 100.3, 90.7) | 95.7 (99.9, 101.6, 91.1) |
| n at which it falls through 0.9 / through 0.2 | 81.2 / 104.3 | 81.7 / 106.7 |
| largest grid n with seed-mean hit >= 0.9 | 80 | 80 |
| cap n (smallest grid n within 5% of the peak; used by the CAPPED arm) | **64** | 64 |
| all-miss floor right after the cliff, mu(112) (hit) | 0.074 (0.00) | 0.078 (0.06) |
| mu(300) / peak mu | 0.207 (mu(300) = 0.111, hit 0) | 0.211 (0.108) |

* Shape: mu rises concavely with n at 93% hits (0.176 at n = 16, 0.325 at 32, 0.512 at 64, 0.537 at 72: the GPU saturates), then collapses within about 30 sessions: seed-mean hit 0.92 at n = 80, 0.79 at 88, 0.42 at 96, 0.00 at 112. The cliff is steep, not a gentle roll-off.
* **The cliff cell is bistable.** At n = 80 the seeds give mu 0.543 / 0.557 / 0.427 (hit 0.93 / 0.93 / 0.90): two seeds are still on the plateau and are *higher* than at n = 72, one has started to collapse. At n = 96 the hit fractions are 0.55 / 0.68 / 0.01. So the seed-mean argmax (72) is partly a seed-2 effect; a single real curve can peak at n = 72 or 80, and the real peak mu (best seeds) is about 0.54 to 0.56 sessions/s in the model.
* **The cap n = 64 is knife-edge.** mu(64) = 0.5122 against the 5% threshold 0.9500 x 0.5373 = 0.5104 (margin 0.35%; separate: 0.4910 against 0.4876, margin 0.7%). A slightly lower mu(64) would give cap 72 (still on the plateau, hit 0.93). Both caps lie below the cliff (n = 80 and above); I expect, but did not test, that a cap of 72 would behave like 64. The printed "cap = 64" is not a robust number.
* Earlier round-6 coarse-grid numbers at the 900k pool (`notes/PREDICTIONS.md`, B4: grid 48, 64, 96, 300; peak "0.52 at n = 64", hit-0.5 crossing 79.7 for seed 0) were interpolation artifacts of a grid with no point between 64 and 96. With 72, 80 and 88 on the grid the crossing moves to 94 and the peak to 72 (seed 0, sessions-based mu(64) is 0.523 in both, so the plateau is the same; only the resolution of the edge differs).

### B2n. From-empty open-loop stability (cache on, FCFS, Poisson from an empty cache and queue, 3000 s, 10 seeds, B2 rule)

Stable runs out of 10 at multiples of the mode's own turns-based lambda_miss (the tables below have the Wilson intervals):

| multiple | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 | 5 | 5.5 | 6 | 6.5 | 7 | 7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixed (lambda_miss 0.07204) | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | **7** | **2** |
| separate (lambda_miss 0.07137) | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | **8** | **3** | **0** |

| quantity | PRIMARY (mixed) | SECONDARY (separate) |
|---|---|---|
| **predicted all-stable edge hi (contiguous rule), in multiples of lambda_miss** | **6.5** | **6.0** |
| edge in sessions/s (hi x lambda_miss) | **0.468** | **0.428** |
| edge censored at the grid top (7.5)? | no | no |
| stable fraction falls through 0.95 / 0.5 (linear interpolation, supplementary) | 6.6 x / 7.2 x | 6.1 x / 6.8 x |
| **stable fraction at exactly the real E0b grid {1.5, 2.5, 3.5, 4.5, 5.5, 6.5}** | **1.0 at all six** (60/60, Wilson [0.94, 1.00]) | 1.0 at 1.5 to 5.5, **0.8 at 6.5** (58/60 pooled, [0.89, 0.99]) |

* The hysteresis band is wide: the system is stable from empty up to about 6 to 6.5 x its own all-miss capacity (0.43 to 0.47 sessions/s), against 1.94 x (mixed) and 2.10 x (separate) at the 300k pool (round 6, B2). In sessions/s that is 0.468 (mixed) and 0.428 (separate) against 0.14 and 0.15 at the 300k pool (3-seed edges of round 6; 0.15 in both modes with 20 seeds), a factor 2.9 to 3.3 for a factor 3.19 in the pool.
* **The last E0b point (6.5 x) is on the edge, not safely inside it.** The model goes 10/10, 7/10, 2/10 (mixed) and 8/10, 3/10, 0/10 (separate) over 6.5, 7, 7.5 x; the contiguous all-stable edge on a 0.5 x grid with 10 seeds is accurate to about one grid step (round 6 saw the 3-seed edge one step below the 20-seed edge). Read the prediction as "stable through 6 x, borderline at 6.5 x (80 to 100% stable), unstable from 7 x", not as a sharp line. A real run whose lambda_miss is lower than the simulated 0.072 shifts the edge in sessions/s down in proportion if the multiples are taken of the real lambda_miss (the multiples, not the absolute rates, are the better-supported prediction, see the trust paragraph at the end of `notes/PREDICTIONS.md` section 0).

### B3n. Paired NOBURST / BURST / CAPPED test (burst of 200 sessions in 60 s at t = 1200 s, 7500 s after, cap 64, 10 seeds, Wilson 95%, PASS by >= 7/10 on all three arms)

Test points lo + (hi - lo)/3 and lo + 2 (hi - lo)/3 of [1, hi], rounded to 0.05 (these points follow from each mode's own hi):

| mode | x lambda_miss | lambda (sessions/s) | BURST trapped | NOBURST good | CAPPED recovered | PASS |
|---|---|---|---|---|---|---|
| mixed | 2.85 | 0.2053 | 9/10 [0.60, 0.98] (the other seed, seed 1, recovers) | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | **PASS** |
| mixed | 4.65 | 0.3350 | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | **PASS** |
| separate | 2.65 | 0.1891 | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | **PASS** |
| separate | 4.35 | 0.3105 | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | 10/10 [0.72, 1.00] | **PASS** |

* **Prediction: the kill test PASSES at both points in both modes.** In the evaluation window (the last 2500 s of the run) NOBURST and CAPPED (cap 64) runs sit at hit 0.93 (0.9275 to 0.9363) with mean backlog below 0.11 request and are indistinguishable from each other; trapped BURST runs sit at hit 0 with mean backlog 460 to 1333 requests (mixed 2.85 x: 0.04 to 643 because of the recovered seed). No BURST run was INDETERMINATE and no NOBURST or CAPPED run was trapped.
* **The token-rate criterion of TRAPPED is close to its limit at the high points.** The trapped runs process 1.09 to 1.14 x the all-miss prefill token rate (mixed 4.65 x: 1.132 to 1.140; separate 4.35 x: 1.119 to 1.126), against a tolerance of 1.15. At a higher arrival rate than these points the registered rule (token rate within 15% of all-miss) would stop labelling a run that is stuck at hit 0 as TRAPPED; the 'stuck (hit < 0.2)' column of the tables is the rate-free reading.
* The one weak spot is the low point of the mixed mode (2.85 x, 9/10): with the 200-session burst, one seed lies on the good side of the pool cliff and recovers. This is the point where a real run is most likely to deviate from the PASS.

### B3n burst-size sensitivity (NOT the registered burst): the same two points with 400 sessions in 60 s

| mode | x lambda_miss | BURST 200 (registered) trapped | BURST 400 trapped | BURST 400 hit (mean) | BURST 400 mean backlog in the evaluation window |
|---|---|---|---|---|---|
| mixed | 2.85 | 9/10 | **10/10** [0.72, 1.00] | 0 | 742 |
| mixed | 4.65 | 10/10 | **10/10** [0.72, 1.00] | 0 | 1410 |
| separate | 2.65 | 10/10 | **10/10** [0.72, 1.00] | 0 | 669 |
| separate | 4.35 | 10/10 | **10/10** [0.72, 1.00] | 0 | 1285 |

Flagged: this is a sensitivity run, not the registered burst. The registered 200-session burst is already large enough in the model (the larger pool does not need a larger burst), and the 400-session burst moves the one 9/10 point to 10/10. The 200-session and NOBURST arms of this stage are bit-identical to the pairs stage (40 of 40 runs, largest difference 0 in hit, backlog, slope and token rate, in both modes), so the sensitivity adds only the 400 arm.

### How far to trust these (read before comparing with the real runs)

* The calibrated simulator over-predicted the all-miss level of the real engine in the 300k validation (floor 0.070 sessions/s simulated against 0.049 real at FCFS n = 48; `notes/PREDICTIONS.md` section 0, last paragraph, from the Validate stage). Quantities that depend on the absolute all-miss level (B1n, the sessions/s values of the edge and the peak, B4n values at n >= 112) can sit tens of percent above the real engine; quantities fixed by the cache and pool geometry (the hit-fraction crossing, the shape of the cliff, the ratio of edge to lambda_miss) are the better-supported predictions. The 300k validation matched the hit-crossing position (32.5 vs 32.2).
* The only real input here is the pool size. Whether SGLang's real eviction and admission behave like the model's near the 955,757-token boundary at n = 80 to 96 is exactly what the real native-pool runs test.
* Fragility, stated plainly: (a) cap n = 64 rests on a 0.4% margin; (b) the cliff cells n = 80 to 96 are bistable across seeds; (c) the from-empty edge is resolved to one 0.5 x step and 10 seeds; (d) the low mixed B3n point (2.85 x) is 9/10, not 10/10.

## What was and was not used

**Used (read).** Inside the worktree `Nova-Research-wt/native-predict` (branch `r8/native-predict`, cut from `main` at `fb3510e`):

* `configs/r7_robustness.yaml`, `experiments/r7_robustness_run.py`, `experiments/r7_robustness_run.sh` (all in full); `notes/ROBUSTNESS_r7.md` (in full); `src/prefixmeta/r7_robustness.py` and `src/prefixmeta/r7_report.py` (in full).
* `notes/PREDICTIONS.md`: the heading list and lines 1 to 146 (the header, section 0 headline predictions, sections 1 to 3). Its B4 tables at the 600k and 900k pool are earlier *simulator* predictions (round 6), not real results; they are quoted above only to compare the grid resolution.
* `configs/r6_predict.yaml` lines 1 to 114; `src/prefixmeta/r6_predict.py` (the list of function names; lines 40 to 60 and 221 to 245: `df_md`, `b4_table`, `b4_landmarks`); `src/prefixmeta/r6_validate.py` lines 116 to 157 (`first_argmax`, `crossing`, `collapse_ratio`, the head of `summarize_curve`); `src/prefixmeta/probe.py` lines 109 to 149 (`load_probe_config` and neighbours); `src/prefixmeta/runner.py` lines 68 to 109 (`wilson_ci`, `apply_overrides`, result-dir helpers); `src/prefixmeta/mech_runner.py` lines 69 to 110 (`begin`, `finish`).
* `tests/test_r7_traces_sim.py` (in full, as the model for the spec-pinning and tiny end-to-end tests); `.gitignore` (first 30 lines, for the data policy).
* `configs/r7_traces_sim.yaml`, `experiments/r7_traces_sim_run.sh`, `experiments/r6_predict_run.sh`: printed together into one 33 KB tool-output file of which only the first 2 KB (the head of `r7_traces_sim.yaml`) was shown to me; the rest was not read.
* Directory listings (names only) of the worktree root, `configs/`, `src/prefixmeta/`, `experiments/`, `notes/`, `tests/` and `results/`, and the one-line subjects of the top five commits of `main` at worktree creation (none mentions a native-pool result).
* Context injected by the harness into the session (not opened by a tool call): `CLAUDE.md` of the repository and the user's auto-memory index. Neither contains a native-pool number (the memory index describes the project workflow and unrelated projects).
* My own outputs: everything under `results/r8_native_mixed/`, `results/r8_native_separate/` and `results/r8_native_report/`.
* **The one real number used:** `max_total_num_tokens = 955,757` (given in the task).

**Not used (not read).** Nothing under `results/nova/` (not even the two directories the task allowed, `stageC_1706210x_pulled_20261022-125454` and `s0_smoke_17060165_pulled_20261021-152347`: they were not needed); `notes/LOG.md`; `notes/STATE.md`; `calibration/round6_server_log_fit/calibration.yaml` and `VALIDATION.md` (the cost constants enter only through the engine block copied from `configs/r7_robustness.yaml`); the main checkout, any other worktree, the scratchpad. No `ssh`, `scp`, `sbatch`, `squeue` or `sacct` was run, the Nova cluster was not contacted, and no real native-pool number (labels containing `-native`, jobs 17096856-58 or 17100938-39) was seen.

## What did not run

* The horizon (30000 s) and low-lambda stages of round 7, other tool-time workloads and the burst-size sweep below 200 sessions were not part of this round and did not run.
* No 20-seed supplement of the from-empty edge (round 6 had one for the 300k pool) and no CAPPED arm for the 400-session sensitivity.
* The conditional refinement grid (1.05 to 1.20 x) of the edge stage was declared but never triggered (the lowest multiple, 1.5 x, is all-stable).
* The burst-size sensitivity multiples are not values of the spec: they are the edge stage's own test points, set by the driver with `--set r7.burst_sizes.multiples=[...]` and recorded in the `meta.json` of that stage (the spec declares them as `null` so that a run without the driver fails loudly; this is tested).

## Commands, seeds, commits, result dirs

* Order of events: `29728e3` (spec, nothing else) -> `0336c91` (driver `experiments/r8_native_predict_run.sh`, report module `src/prefixmeta/r8_native_report.py`, tests `tests/test_r8_native_predict.py`) -> all simulation runs on `0336c91`, clean tree (`dirty = False` in all ten stage `meta.json`) -> `09b541d` (report-only consistency check; tables regenerated) -> the commit that adds this file and the force-added result summaries.
* The whole prediction set is one driver call, from the worktree root in Git Bash (driver log `results/r8_native_run_all.log`, 14:54:38 to 14:55:31 on 2026-10-25), followed by the regenerated tables and this file:

```
bash experiments/r8_native_predict_run.sh > results/r8_native_run_all.log 2>&1
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" -m prefixmeta.r8_native_report report --spec configs/r8_native_predict.yaml
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" -m prefixmeta.r8_native_report assemble --spec configs/r8_native_predict.yaml --headline results/r8_headline.md --notes notes/PREDICTIONS_native.md
```

* The driver expands into the ten stage commands listed per mode in the provenance below (the r7 CLI `experiments/r7_robustness_run.py {lambda_miss,curves,edge,pairs,burst_sizes}`, `--workers 6`, one stage at a time, so never more than 6 worker processes), the two `prefixmeta.r7_report report` calls and the r8 report.
* Seeds: lambda_miss and closed curve 0, 1, 2; edge, pairs and burst-size stages 0 to 9. Common random numbers: for a seed, the Poisson arrival stream, turn counts and tool times are shared by the NOBURST, BURST and CAPPED arms; the burst is an extra stream.
* Result dirs: `results/r8_native_mixed/` and `results/r8_native_separate/` (per-stage dirs `r7_<stage>/<timestamp>/` with config copies, `meta.json`, `summary.json` and CSVs; manifest `r7_robustness/manifest.tsv`; the r7-style report `r7_report/<timestamp>/`), and the final r8 report `results/r8_native_report/20261025-150146/` (`tables.md`, `summary.json`, `provenance.md`, copies of the per-stage CSVs). The window-level CSVs (`windows.csv`, 1.2 to 1.6 MB each) are kept locally and are not committed; every number regenerates bit-identically from the commit and the spec.
* `meta.json` `hardware` reads "Apple M3 Max CPU (simulation)": a hard-coded constant of the runner, wrong for this PC; `hostname` and `versions.platform` are right (known since round 6). In the provenance below, "spec copy identical to the committed file" compares the stage's `config.yaml` (a raw copy of the spec) with the spec; the secondary mode's `--set engine.batching=...` override is in the `overrides` column and in each stage's `config_effective.yaml`.

## Tests

* The new test file `tests/test_r8_native_predict.py` (10 tests; run on `09b541d`, the code commit; nothing under `src/` or `tests/` changed after it): **10 passed**. It pins the spec to its declaration (the only engine change is `kv_memory_tokens` 955757; everything else of the r7 block is the round-7 declaration except the listed grids, the single workload and the stages), checks the report helpers on synthetic frames (landmarks, censoring of the edge, E0b rows, burst sensitivity, the pairs-vs-sizes consistency check), and runs every stage of both batching modes, the burst-size sensitivity at the edge stage's points, the r7 and r8 reports and the assembly end to end on a tiny scaled-down copy of the real spec.
* Together with the neighbouring suites `tests/test_r7_robustness.py`, `tests/test_r7_traces_sim.py`, `tests/test_r7_workload.py`, `tests/test_r6_predict.py`: **71 passed, 0 failed** (those four suites are unchanged; no `src/` default was touched, `src/prefixmeta/r8_native_report.py` is a new module that imports from the r7 and r6 modules).
* The full suite was not part of this task's reporting (this round adds files only, and the existing suites that scan `configs/`, `experiments/` or `slurm/` do not look at the new files); the known Windows-only failures listed in the repository's `CLAUDE.md` are in suites that this round does not touch.
