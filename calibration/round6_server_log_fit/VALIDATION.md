# Round 6 validation: does the calibrated simulator reproduce the REAL Stage C closed-population curve?

Status: registered run finished; tables below are generated from `results/r6_validate_stagec/20261024-025222/` (nothing retyped). Written on branch `r6/validation`.
Stage: Validate (round 6). The simulator constants are `calibration/round6_server_log_fit/calibration.yaml` (fitted ONLY from SGLang server-log timing,
never from mu(n)); the real data are the Stage C `sglang-fcfs-r1` / `sglang-lpm-r1` cells (Qwen2.5-7B, A100 80GB, KV cap 300k tokens, single run per cell,
seed 0, window [900, 2700) s).

## 0. Result in six lines

1. **Level (the declared test): NO for both batching modes.** Primary arm, 3 registered seeds, 8 judged cells: mixed reproduces mu within 15% in
   7/8 cells (fails FCFS n=48, +42.4%), separate in 6/8
   (fails FCFS n=48 +43.2% and LPM(128) n=48 +25.6%).
   Plateau (n=16, 20, 24) agrees within 9% (3 seeds; within 3% with 20 seeds) and the n=300 tail within 2% (3 seeds; 6% with 20 seeds);
   the intermediate cells n=48 and n=96 are over-predicted (the real run dips below the simulated all-miss floor).
2. **Which mode is closer (pre-declared metric, mean |rel.err| of seed-mean mu_sessions over the judged cells): mixed**, 0.104 vs 0.127
   (20-seed supplement: 0.120 vs 0.142; sensitivity arms S1, S2, S4 agree). The margin is carried by ONE cell,
   LPM(128) n=48 (mixed -8.8%, separate +25.6%); there separate reproduces the hit fraction (0.416 vs real 0.385) and mixed does not (0.156). On the lower-variance
   turns-based estimator the two modes are tied (0.053 vs 0.053). Except at LPM(128) n=48 (and FCFS n=32, not judged) the two modes differ by at most about 1.3% in mu.
3. **Shape: reproduced.** Hit-fraction curve and the 0.5-hit crossing (real 32.2; mixed 32.5, separate 33.8), the plateau,
   the collapse and the non-monotone tail (mu(300) > mu(96)) all appear. The peak sits in the flat top n=20..24 in both systems and is not resolvable more finely
   than that (flagged ambiguous). Collapse ratio mu(300)/mu*: real 0.462, sim 0.500 / 0.502 (mixed / separate).
4. **Level at the cells that fail is a data-side question as much as a model-side one.** For the same real runs, the turns-based estimator is 29% (n=48: 0.063 vs 0.049) and 19% (n=96: 0.073 vs 0.061) higher
   than mu_sessions, and mu_sessions lies below the simulator's all-miss level (0.070 to 0.077). Against the turns-based real values the simulator
   is within 15% in 7/8 judged cells for both modes (misses only LPM(128) n=48: mixed -17.9%, separate +15.3%). The declared metric is mu_sessions; this is reported, not used to re-judge.
5. **Pick for the predictions: mixed** by the declared rule (reasons and the caveat in section 6). Because the two modes agree everywhere except the hit-retention
   transition (LPM(128) mid-n, FCFS n~32), I recommend running the transition-sensitive predictions (B3 E2 arms, B4) in BOTH modes and reporting the pair.
6. Everything took 79 s of wall time on the PC (663 simulated runs, 6 workers), not the ~1 h budgeted; every number is reproducible bit for bit (section 11).

## 1. What was run

| item | value |
|---|---|
| branch / validated code commit | `r6/validation` @ `cda031449d5c2d2c5e8339ebff70c1a76bc7126b` (clean tree, dirty = False); parents: 58451c8 (unreviewed WIP), 1cdec96 (harness), 772b08f (Port stage) |
| result dir (registered run) | `results/r6_validate_stagec/20261024-025222/` (meta.json, config.yaml, config_effective.yaml, runs.csv, cell_table.csv, summary.json, tables.md, supplementary CSVs, report.md, z-score CSVs, reserved_trace_seed0.txt) |
| spec (declared before any run, unchanged) | `configs/r6_validate_stagec.yaml` (sha256 of calibration.yaml: `284c2dee1a08c8735cf026508808b72ad7b4005939fa25403912d8d8b6b9da8c`) |
| registered seeds | [0, 1, 2] (3 seeds x 9 cells x 9 (arm, batching) combinations = 243 runs); fine grid: 10 extra FCFS n x seeds 0, 1, 2 x 2 modes = 60 runs; 20-seed supplement: seeds 100-119 x 9 cells x 2 modes = 360 runs; total 663 runs |
| wall time | 78.9 s (2026-10-24T02:52:22 to 2026-10-24T02:53:41) |
| machine | Windows 11 Home 10.0.26200 PC (hostname Akshat-PC, 10 cores), Python 3.12.10, NumPy 1.26.4, SciPy 1.13.1, pandas 2.2.2, PyYAML 6.0.1, Numba 0.60.0, pytest 7.4.4; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`. (meta.json's `hardware` field reads "Apple M3 Max CPU (simulation)": that is a hard-coded constant in `runner.HARDWARE` (src/prefixmeta/runner.py) and is wrong for this run; `hostname` and `versions.platform` are right.) |

Commands (from the worktree root, Git Bash):

```
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
$PY experiments/prefix_meta_r6_validate_stagec.py run --spec configs/r6_validate_stagec.yaml --quick --workers 2 --tag smoke      # smoke only, results/r6_validate_stagec_smoke_quick/, not cited
$PY experiments/prefix_meta_r6_validate_stagec.py run --spec configs/r6_validate_stagec.yaml --workers 6 --set parallel.max_workers=6   # REGISTERED
$PY experiments/prefix_meta_r6_validate_stagec.py report --run-dir results/r6_validate_stagec/20261024-025222
$PY calibration/round6_server_log_fit/validate_stagec_reserved_trace.py --seed 0 --n 48 300 --out results/r6_validate_stagec/20261024-025222/reserved_trace_seed0.txt
```

Deviations from the task as written (none changes the declared protocol, cells, seeds, arms or criteria):
- `--set parallel.max_workers=6`: the spec's `parallel.max_workers: 4` silently caps `--workers` (Runner takes the minimum), so `--workers 6` alone would have used 4 processes. Results do not depend on the worker count: the smoke
  run (2 workers) and the registered run (6 workers) are bit-identical on all 6 shared runs (mu, hit rate, reserved tokens).
- Review of 58451c8 found and fixed three defects in the report code (commit `cda0314`, made BEFORE the registered run so that meta.json records a clean commit): `zscore_table` produced z ~ 3e14 for a zero-spread column
  (identical values give a float sd of ~1e-17, which was truthy), `md_zscore_table` printed "+nan" for an undefined z, and `report` accepted an unfinished run dir. Two tests added. The rest of 58451c8 (n/a handling for arms without a batching
  mode, the report tables, the reserved-trace script) was reviewed against 1cdec96 and left unchanged; the trace script's engine matches the registered runs (reserved-KV means agree with runs.csv to <0.1% at n=48 and n=300, seed 0: mixed 285047 vs 285044 and 294657 vs 294657; separate 224313 vs 224352 and 169507 vs 169373).

## 2. The declared question and criteria (quoted from `configs/r6_validate_stagec.yaml`)

```yaml
research_question: >-
  Out of sample (the cost model was fitted to SGLang server-log timing only, never to mu(n)), do the simulator's mixed and separate
  (SGLang prefill-priority) batching modes reproduce the real Stage C mu(n) and hit-fraction curves of sglang-fcfs-r1 / sglang-lpm-r1
  within 15% in level, and which mode is closer?
```

```yaml
  # ---- decision rules, declared in advance
  criteria:
    level_rel_tol: 0.15                       # |sim seed-mean mu - real mu_sessions| / real <= 0.15
    level_excluded_cells: [[fcfs_lru, 32]]    # the single-seed bistable cell (real hit 0.51 mixes two regimes): reported, not judged
    closeness_metric: mean_abs_rel_err_mu     # mean over the judged cells of |relative error| of the seed-mean mu_sessions; lower = closer mode
    peak_runner_up_flag_frac: 0.05            # argmax is flagged when the runner-up mean is within 5% of the max (as in the Stage C plan)
    hit_crossing_level: 0.5                   # linear interpolation in n between adjacent grid points of the seed-mean hit fraction
    collapse: mu_300_over_mu_star             # mu(300) / max over the FCFS grid of the seed-mean mu (the Stage C analysis-plan definition)
    level_judged_on: mu_sessions              # real estimator used for the errors; mu_turns_based is reported alongside
```

Protocol: closed population, all n sessions start at t = 0 (synchronized start), a finished session is replaced at once; measured window [900, 2700) s; mu = sessions completed in the window / 1800 s;
hit = hits / admitted turns in the window (real: fraction of ok turns completing in the window with cached/prompt > 0.5); workload 2000-token first prompt, +550 tool tokens, 100 decoded tokens, T ~ min(Geometric(1/15), 60) turns
(E[T] = 14.76), tool time Exp(5 s); KV cap 300k tokens; FCFS at n = 16, 20, 24, 32, 48, 96, 300 and LPM with the SGLang >128-waiting FCFS fallback (`lpm128_lru`) at n = 48, 300. The judged cells are the 8 cells other than FCFS n=32.
Note that FCFS n=300 and LPM(128) n=300 are the SAME simulation (with far more than 128 sessions waiting, the >128 fallback is always active; the real LPM n=300 run had a mean queue of 269), so the judged set has 7 independent simulated cells.

The registered arms (the PRIMARY arm is calibration.yaml unchanged with only `batching` set; every other arm is a labelled sensitivity):

```yaml
  # ---- arms. `primary` = calibration.yaml's engine block unchanged (alloc_mode full_reserve, free_kv_on_session_end true), only `batching` set.
  # Sensitivities change ONE modelling choice each (S4 changes two) and are reported separately.
  arms:
    primary:
      note: calibration.yaml unchanged (full_reserve, finished-session KV freed at once); the pre-declared primary arm
      engine: {}
      batching_modes: [mixed, separate_prefill_priority]
    S1_ratio_reserve:
      note: SGLang-like new_token_ratio reservation with retraction (constants = configs/prefix_meta_r5.yaml modes.engine_overrides.ratio_reserve, unverified scout reading)
      engine_from: modes.engine_overrides.ratio_reserve
      engine: {}
      batching_modes: [mixed, separate_prefill_priority]
    S2_keep_finished_kv:
      note: a finished session's KV stays as evictable idle KV (the real radix cache cannot know a session ended)
      engine: {free_kv_on_session_end: false}
      batching_modes: [mixed, separate_prefill_priority]
    S3_decode_per_seq:
      note: calibration caveat 2 -- decode per-sequence slope 4.351e-5 s (decode-only fit, calibration.yaml alternatives.decode_only_linear); separate mode only, the key is ignored in mixed mode
      engine: {decode_per_seq_s: 4.351e-05}
      batching_modes: [separate_prefill_priority]
    S4_sglang_like:
      note: S1 + S2 (ratio_reserve and finished-session KV kept), the most engine-faithful combination of the simulator's existing switches
      engine_from: modes.engine_overrides.ratio_reserve
      engine: {free_kv_on_session_end: false}
      batching_modes: [mixed, separate_prefill_priority]
```

## 3. Primary arm: mu(n), real vs simulator (3 registered seeds; seed-mean, se = sd/sqrt(3))

Real values are single runs. "rel.err" = (sim seed-mean - real) / real. Judged (declared) estimator: mu_sessions (columns 3 to 7); the turns-based real estimator is shown alongside (last three columns).

| policy | n | real mu | mixed mu (se) | rel.err | separate mu (se) | rel.err | real mu (turns) | mixed rel.err (turns) | separate rel.err (turns) |
|---|---|---|---|---|---|---|---|---|---|
| FCFS | 16 | 0.176 | 0.177 (0.005) | +0.6% | 0.176 (0.005) | +0.1% | 0.176 | +0.1% | -0.6% |
| FCFS | 20 | 0.224 | 0.213 (0.006) | -5.0% | 0.211 (0.006) | -5.8% | 0.215 | -0.3% | -1.4% |
| FCFS | 24 | 0.233 | 0.212 (0.014) | -9.1% | 0.209 (0.013) | -10.3% | 0.226 | -5.6% | -6.3% |
| FCFS | 32 | 0.115 | 0.123 (0.021) | +6.9% | 0.131 (0.022) | +14.0% | 0.116 | +5.9% | +12.8% |
| FCFS | 48 | 0.049 | 0.070 (0.004) | +42.4% | 0.070 (0.004) | +43.2% | 0.063 | +13.5% | +14.6% |
| FCFS | 96 | 0.061 | 0.070 (0.001) | +14.5% | 0.070 (0.001) | +13.9% | 0.073 | +3.9% | +3.3% |
| FCFS | 300 | 0.108 | 0.106 (0.001) | -1.4% | 0.106 (0.002) | -1.7% | 0.111 | -0.2% | -0.5% |
| LPM(128) | 48 | 0.087 | 0.079 (0.006) | -8.8% | 0.109 (0.005) | +25.6% | 0.097 | -17.9% | +15.3% |
| LPM(128) | 300 | 0.105 | 0.106 (0.001) | +1.2% | 0.106 (0.002) | +0.9% | 0.110 | +0.8% | +0.5% |

Cells over the 15% tolerance on mu_sessions: mixed: fcfs_lru@48:+0.424; separate: fcfs_lru@48:+0.432, lpm128_lru@48:+0.256. FCFS n=32 is reported, not judged (the single-seed bistable cell: real hit 0.51 mixes two regimes).

The two real estimators of the same runs (they disagree most where few sessions complete, n=48 and n=96):

| policy | n | mu (sessions completed / s) | mu (turns-based) | turns-based / sessions - 1 | real hit | real cached-token fraction |
|---|---|---|---|---|---|---|
| FCFS | 16 | 0.1756 | 0.1758 | +0.1% | 0.932 | 0.936 |
| FCFS | 20 | 0.2239 | 0.2150 | -4.0% | 0.927 | 0.930 |
| FCFS | 24 | 0.2333 | 0.2255 | -3.3% | 0.888 | 0.883 |
| FCFS | 32 | 0.1150 | 0.1158 | +0.7% | 0.505 | 0.463 |
| FCFS | 48 | 0.0489 | 0.0629 | +28.7% | 0.000 | 0.000 |
| FCFS | 96 | 0.0611 | 0.0730 | +19.4% | 0.000 | 0.000 |
| FCFS | 300 | 0.1078 | 0.1114 | +3.4% | 0.000 | 0.000 |
| LPM(128) | 48 | 0.0867 | 0.0966 | +11.4% | 0.385 | 0.374 |
| LPM(128) | 300 | 0.1050 | 0.1103 | +5.1% | 0.000 | 0.000 |

## 4. Primary arm: hit fraction (absolute differences; real hit is 0 at n >= 48 except LPM n=48)

| policy | n | real hit | mixed hit | diff | separate hit | diff |
|---|---|---|---|---|---|---|
| FCFS | 16 | 0.932 | 0.932 | -0.000 | 0.932 | -0.000 |
| FCFS | 20 | 0.927 | 0.931 | +0.004 | 0.930 | +0.003 |
| FCFS | 24 | 0.888 | 0.883 | -0.005 | 0.884 | -0.003 |
| FCFS | 32 | 0.505 | 0.517 | +0.012 | 0.560 | +0.055 |
| FCFS | 48 | 0.000 | 0.000 | +0.000 | 0.023 | +0.023 |
| FCFS | 96 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |
| FCFS | 300 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |
| LPM(128) | 48 | 0.385 | 0.156 | -0.229 | 0.416 | +0.031 |
| LPM(128) | 300 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |

Mean absolute hit error over the 9 cells: mixed 0.028, separate 0.013. Separate is much closer on LPM(128) n=48 (+0.031 vs -0.229); mixed is closer at FCFS n=32 (+0.012 vs +0.055) and n=48 (0.000 vs +0.023).

## 5. Curve landmarks: peak location, 0.5-hit crossing, collapse ratio

| curve | argmax n (mu*) | runner-up n (gap to max) | peak ambiguous (<5%)? | 0.5-hit crossing n | mu(300)/mu* | mu(48)/mu* |
|---|---|---|---|---|---|---|
| REAL Stage C (single run, 7-point grid) | 24 (0.233) | 20 (4.0%) | yes | 32.2 | 0.462 | 0.210 |
| sim mixed, 7-point grid, 3 seeds (registered) | 20 (0.213) | 24 (0.3%) | yes | 32.5 | 0.500 | 0.328 |
| sim separate, 7-point grid, 3 seeds (registered) | 20 (0.211) | 24 (0.8%) | yes | 33.8 | 0.502 | 0.332 |
| sim mixed, fine grid (17 points), 3 seeds (supplementary) | 22 (0.222) | 20 (4.1%) | yes | 32.2 | 0.480 | 0.314 |
| sim separate, fine grid (17 points), 3 seeds (supplementary) | 22 (0.219) | 20 (3.7%) | yes | 32.7 | 0.484 | 0.320 |
| sim mixed, 7-point grid, 20 seeds (supplementary) | 24 (0.228) | 20 (5.0%) | no | 31.6 | 0.486 | 0.314 |
| sim separate, 7-point grid, 20 seeds (supplementary) | 24 (0.228) | 20 (5.8%) | no | 32.8 | 0.484 | 0.317 |

Peak: the argmax over a grid with a flat top (mu varies by <5% over n = 20..24 in the real data too: 0.224, 0.233). Real: n=24, runner-up n=20 within 4.0%, so it is flagged. The simulator's peak is n=20 (3 seeds, gap 0.3% / 0.8%),
n=22 (fine grid, gap 4.1% / 3.7%) or n=24 (20 seeds, gap 5.0% / 5.8%): all inside the same plateau; the location is NOT resolved better than "20 to 24" in either system. Crossing: within 1.6 (in n) of the real 32.2 in every
version (0.0 to 1.6). Collapse: the simulator's mu(300)/mu* is 0.48 to 0.50, real 0.46; the dip at n=48 is shallower in the simulator (mu(48)/mu* = 0.31 to 0.33 vs real 0.21) because of the n=48 over-prediction.

Fine grid (supplementary, seeds 0 to 2; registered points interleaved):

| n | source | real mu | real hit | mixed mu (se) | mixed hit | separate mu (se) | separate hit |
|---|---|---|---|---|---|---|---|
| 16 | registered | 0.176 | 0.932 | 0.177 (0.005) | 0.932 | 0.176 (0.005) | 0.932 |
| 18 | fine grid | - | - | 0.195 (0.005) | 0.932 | 0.194 (0.005) | 0.932 |
| 20 | registered | 0.224 | 0.927 | 0.213 (0.006) | 0.931 | 0.211 (0.006) | 0.930 |
| 22 | fine grid | - | - | 0.222 (0.006) | 0.919 | 0.219 (0.005) | 0.918 |
| 24 | registered | 0.233 | 0.888 | 0.212 (0.014) | 0.883 | 0.209 (0.013) | 0.884 |
| 26 | fine grid | - | - | 0.183 (0.031) | 0.806 | 0.197 (0.026) | 0.832 |
| 28 | fine grid | - | - | 0.176 (0.025) | 0.769 | 0.178 (0.024) | 0.777 |
| 30 | fine grid | - | - | 0.161 (0.035) | 0.671 | 0.171 (0.030) | 0.717 |
| 32 | registered | 0.115 | 0.505 | 0.123 (0.021) | 0.517 | 0.131 (0.022) | 0.560 |
| 34 | fine grid | - | - | 0.094 (0.019) | 0.295 | 0.103 (0.018) | 0.382 |
| 36 | fine grid | - | - | 0.084 (0.012) | 0.190 | 0.094 (0.011) | 0.297 |
| 40 | fine grid | - | - | 0.071 (0.006) | 0.032 | 0.080 (0.010) | 0.128 |
| 44 | fine grid | - | - | 0.069 (0.005) | 0.007 | 0.070 (0.006) | 0.034 |
| 48 | registered | 0.049 | 0.000 | 0.070 (0.004) | 0.000 | 0.070 (0.004) | 0.023 |
| 64 | fine grid | - | - | 0.068 (0.003) | 0.000 | 0.068 (0.003) | 0.000 |
| 96 | registered | 0.061 | 0.000 | 0.070 (0.001) | 0.000 | 0.070 (0.001) | 0.000 |
| 300 | registered | 0.108 | 0.000 | 0.106 (0.001) | 0.000 | 0.106 (0.002) | 0.000 |

## 6. Which mode is closer, and does the LEVEL match within 15%?

| data | mean abs rel.err mu: mixed | separate | cells within 15%: mixed | separate | level_ok: mixed | separate | max abs: mixed | separate | mean abs rel.err mu (turns): mixed | separate | mean abs hit err: mixed | separate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **primary arm, 3 registered seeds (the declared test)** | 0.104 | 0.127 | 7/8 | 6/8 | False | False | 0.424 | 0.432 | 0.053 | 0.053 | 0.028 | 0.013 |
| supplementary, 20 seeds (100-119) | 0.120 | 0.142 | 6/8 | 5/8 | False | False | 0.469 | 0.479 | 0.053 | 0.046 | 0.028 | 0.006 |

- **Level verdict: NO for both modes** on the declared criterion (all 8 judged cells within 15% of the real mu_sessions). It is an honest NO, and it is a localized NO: the failing cell is FCFS n=48
  (sim 0.070 vs real 0.049, +42% mixed, +43% separate), plus LPM(128) n=48 for separate (+25.6%). With 20 seeds the picture is the same but sharper (mixed fails FCFS n=48 +46.9% and n=96 +26.3%; separate additionally LPM n=48 +27.0%)
  and the plateau improves (every plateau cell within 3.1% mixed / 4.1% separate of the real value; the 3-seed plateau errors up to -9.1% at n=24 are mostly seed noise: the per-seed sd of mu is 0.02 there).
- **Closer mode under the pre-declared metric: mixed** (0.104 vs 0.127; 20 seeds 0.120 vs 0.142). Sensitivity arms (reported as sensitivities, section 8) agree: S1 0.096 vs 0.120, S2 0.118 vs 0.146, S4 0.108 vs 0.121 (mixed
  first); S3 has no mixed arm. The primary arm and the sensitivities agree, so the rule allows using it for the pick.
- **How much that is worth.** Paired by seed (the two modes see identical workloads for a given seed), the modes differ materially (more than 1.3% of mu) in only two cells (LPM(128) n=48 and FCFS n=32); a few other cells show statistically detectable but tiny differences (t of -3.6 to -5.9 at n=16, 20, 96, never above 1.3% of mu). 20 seeds:

| policy | n | seeds | mixed mu | separate mu | paired diff (separate - mixed) | se | t | hit diff |
|---|---|---|---|---|---|---|---|---|
| FCFS | 16 | 20 | 0.1771 | 0.1759 | -0.0013 | 0.0002 | -5.87 | +0.000 |
| FCFS | 20 | 20 | 0.2169 | 0.2148 | -0.0021 | 0.0006 | -3.58 | +0.000 |
| FCFS | 24 | 20 | 0.2284 | 0.2281 | -0.0003 | 0.0010 | -0.31 | +0.002 |
| FCFS | 32 | 20 | 0.1181 | 0.1257 | +0.0076 | 0.0022 | +3.50 | +0.043 |
| FCFS | 48 | 20 | 0.0718 | 0.0723 | +0.0005 | 0.0004 | +1.32 | +0.011 |
| FCFS | 96 | 20 | 0.0772 | 0.0763 | -0.0009 | 0.0002 | -4.56 | +0.000 |
| FCFS | 300 | 20 | 0.1109 | 0.1103 | -0.0006 | 0.0004 | -1.50 | +0.000 |
| LPM(128) | 48 | 20 | 0.0796 | 0.1101 | +0.0305 | 0.0018 | +16.56 | +0.230 |
| LPM(128) | 300 | 20 | 0.1109 | 0.1103 | -0.0006 | 0.0004 | -1.50 | +0.000 |

  (3 registered seeds, same quantity:)

| policy | n | seeds | mixed mu | separate mu | paired diff (separate - mixed) | se | t | hit diff |
|---|---|---|---|---|---|---|---|---|
| FCFS | 16 | 3 | 0.1767 | 0.1757 | -0.0009 | 0.0002 | -5.00 | -0.000 |
| FCFS | 20 | 3 | 0.2126 | 0.2109 | -0.0017 | 0.0006 | -2.60 | -0.001 |
| FCFS | 24 | 3 | 0.2120 | 0.2093 | -0.0028 | 0.0025 | -1.11 | +0.002 |
| FCFS | 32 | 3 | 0.1230 | 0.1311 | +0.0081 | 0.0038 | +2.17 | +0.043 |
| FCFS | 48 | 3 | 0.0696 | 0.0700 | +0.0004 | 0.0013 | +0.29 | +0.023 |
| FCFS | 96 | 3 | 0.0700 | 0.0696 | -0.0004 | 0.0002 | -2.00 | +0.000 |
| FCFS | 300 | 3 | 0.1063 | 0.1059 | -0.0004 | 0.0010 | -0.36 | +0.000 |
| LPM(128) | 48 | 3 | 0.0791 | 0.1089 | +0.0298 | 0.0082 | +3.63 | +0.260 |
| LPM(128) | 300 | 3 | 0.1063 | 0.1059 | -0.0004 | 0.0010 | -0.36 | +0.000 |

  At FCFS n=16 to 24, n=48 and n>=96 the mode effect on mu is at most 1.3%. The mode effect is the hit-retention transition: separate retains more cache at n=32 (+0.043 hit) and under LPM at n=48 (+0.23 hit), which raises mu (+0.008 and +0.030).
  So "which mode is closer" is decided by LPM(128) n=48 alone: mixed under-predicts hits (0.16 vs 0.385) yet lands near the real mu (-8.8%); separate matches the hit fraction (0.416) but over-predicts mu (+25.6%; the cause was not isolated here. Candidates: the cost of a hit prefill, for which the calibration report found the model off by +17% to -11%
  depending on prefix length; the unmodelled waiting-prefix refresh and partial prefixes; single-run noise, since the turns-based real value for this cell is 11% higher, 0.097, and separate is then +15.3%). On the turns-based estimator the modes are tied (0.053 vs 0.053; 20 seeds 0.053 vs 0.046,
  separate slightly closer). **Pick: mixed**, because that is what the pre-declared metric and its sensitivity checks say, with the caveat that the evidence rests on one cell and that mixed's hit retention under LPM is wrong
  while separate's cost level is wrong. For the predictions that depend on the hit-retention transition (E2 burst arms, native-pool curves), run both modes and report the pair; for all-miss quantities (B1 lambda_miss and the all-miss token rate) the
  modes are identical to <1% and the pick is immaterial.

## 7. Position of the real value in the simulator's seed distribution (primary arm)

z = (real - sim mean) / sim sd across seeds; "frac" = fraction of seeds with sim <= real. The real value is one draw of the real engine's own distribution, so |z| of 1 to 2 is expected for some cells; sd is the simulator's, not the real run's.

3 registered seeds (sd estimated from 3 values, so z is very unstable; n/a where undefined):

| batching | policy | n | real mu | sim mean (sd) | z | frac sims <= real | real mu (turns) | sim mean (sd) | z |
|---|---|---|---|---|---|---|---|---|---|
| mixed | FCFS | 16 | 0.176 | 0.177 (0.009) | -0.12 | 0.33 | 0.176 | 0.176 (0.002) | -0.04 |
| mixed | FCFS | 20 | 0.224 | 0.213 (0.010) | +1.12 | 1.00 | 0.215 | 0.214 (0.002) | +0.28 |
| mixed | FCFS | 24 | 0.233 | 0.212 (0.024) | +0.89 | 1.00 | 0.226 | 0.213 (0.020) | +0.64 |
| mixed | FCFS | 32 | 0.115 | 0.123 (0.036) | -0.22 | 0.33 | 0.116 | 0.123 (0.027) | -0.26 |
| mixed | FCFS | 48 | 0.049 | 0.070 (0.007) | -2.83 | 0.00 | 0.063 | 0.071 (0.002) | -4.90 |
| mixed | FCFS | 96 | 0.061 | 0.070 (0.001) | -6.05 | 0.00 | 0.073 | 0.076 (0.002) | -1.29 |
| mixed | FCFS | 300 | 0.108 | 0.106 (0.002) | +0.76 | 0.67 | 0.111 | 0.111 (0.001) | +0.19 |
| mixed | LPM(128) | 48 | 0.087 | 0.079 (0.010) | +0.74 | 0.67 | 0.097 | 0.079 (0.003) | +6.27 |
| mixed | LPM(128) | 300 | 0.105 | 0.106 (0.002) | -0.67 | 0.33 | 0.110 | 0.111 (0.001) | -0.60 |
| separate_prefill_priority | FCFS | 16 | 0.176 | 0.176 (0.009) | -0.02 | 0.33 | 0.176 | 0.175 (0.002) | +0.50 |
| separate_prefill_priority | FCFS | 20 | 0.224 | 0.211 (0.011) | +1.18 | 1.00 | 0.215 | 0.212 (0.003) | +1.07 |
| separate_prefill_priority | FCFS | 24 | 0.233 | 0.209 (0.022) | +1.10 | 1.00 | 0.226 | 0.211 (0.018) | +0.79 |
| separate_prefill_priority | FCFS | 32 | 0.115 | 0.131 (0.039) | -0.42 | 0.33 | 0.116 | 0.131 (0.029) | -0.52 |
| separate_prefill_priority | FCFS | 48 | 0.049 | 0.070 (0.007) | -2.92 | 0.00 | 0.063 | 0.072 (0.004) | -2.56 |
| separate_prefill_priority | FCFS | 96 | 0.061 | 0.070 (0.002) | -5.02 | 0.00 | 0.073 | 0.075 (0.002) | -1.35 |
| separate_prefill_priority | FCFS | 300 | 0.108 | 0.106 (0.004) | +0.52 | 0.67 | 0.111 | 0.111 (0.001) | +0.40 |
| separate_prefill_priority | LPM(128) | 48 | 0.087 | 0.109 (0.009) | -2.55 | 0.00 | 0.097 | 0.111 (0.004) | -3.46 |
| separate_prefill_priority | LPM(128) | 300 | 0.105 | 0.106 (0.004) | -0.26 | 0.67 | 0.110 | 0.111 (0.001) | -0.37 |

20 seeds (100-119):

| batching | policy | n | real mu | sim mean (sd) | z | frac sims <= real | real mu (turns) | sim mean (sd) | z |
|---|---|---|---|---|---|---|---|---|---|
| mixed | FCFS | 16 | 0.176 | 0.177 (0.013) | -0.12 | 0.40 | 0.176 | 0.177 (0.002) | -0.41 |
| mixed | FCFS | 20 | 0.224 | 0.217 (0.015) | +0.46 | 0.70 | 0.215 | 0.214 (0.005) | +0.17 |
| mixed | FCFS | 24 | 0.233 | 0.228 (0.032) | +0.15 | 0.65 | 0.226 | 0.226 (0.021) | -0.00 |
| mixed | FCFS | 32 | 0.115 | 0.118 (0.032) | -0.10 | 0.55 | 0.116 | 0.117 (0.024) | -0.04 |
| mixed | FCFS | 48 | 0.049 | 0.072 (0.010) | -2.28 | 0.00 | 0.063 | 0.072 (0.005) | -1.68 |
| mixed | FCFS | 96 | 0.061 | 0.077 (0.010) | -1.65 | 0.05 | 0.073 | 0.079 (0.004) | -1.62 |
| mixed | FCFS | 300 | 0.108 | 0.111 (0.010) | -0.32 | 0.35 | 0.111 | 0.112 (0.002) | -0.41 |
| mixed | LPM(128) | 48 | 0.087 | 0.080 (0.011) | +0.63 | 0.70 | 0.097 | 0.080 (0.006) | +2.69 |
| mixed | LPM(128) | 300 | 0.105 | 0.111 (0.010) | -0.60 | 0.20 | 0.110 | 0.112 (0.002) | -1.01 |
| separate_prefill_priority | FCFS | 16 | 0.176 | 0.176 (0.013) | -0.03 | 0.50 | 0.176 | 0.175 (0.002) | +0.18 |
| separate_prefill_priority | FCFS | 20 | 0.224 | 0.215 (0.015) | +0.62 | 0.80 | 0.215 | 0.213 (0.004) | +0.61 |
| separate_prefill_priority | FCFS | 24 | 0.233 | 0.228 (0.031) | +0.17 | 0.65 | 0.226 | 0.225 (0.019) | +0.03 |
| separate_prefill_priority | FCFS | 32 | 0.115 | 0.126 (0.036) | -0.29 | 0.40 | 0.116 | 0.125 (0.028) | -0.33 |
| separate_prefill_priority | FCFS | 48 | 0.049 | 0.072 (0.011) | -2.10 | 0.00 | 0.063 | 0.072 (0.006) | -1.41 |
| separate_prefill_priority | FCFS | 96 | 0.061 | 0.076 (0.010) | -1.57 | 0.05 | 0.073 | 0.078 (0.003) | -1.44 |
| separate_prefill_priority | FCFS | 300 | 0.108 | 0.110 (0.011) | -0.24 | 0.35 | 0.111 | 0.112 (0.002) | -0.18 |
| separate_prefill_priority | LPM(128) | 48 | 0.087 | 0.110 (0.016) | -1.50 | 0.00 | 0.097 | 0.109 (0.010) | -1.20 |
| separate_prefill_priority | LPM(128) | 300 | 0.105 | 0.110 (0.011) | -0.50 | 0.35 | 0.110 | 0.112 (0.002) | -0.81 |

20-seed means against the real values (the best available estimate of the simulator's own level):

| policy | n | real mu | mixed mu (se) | rel.err | separate mu (se) | rel.err | real mu (turns) | mixed rel.err (turns) | separate rel.err (turns) |
|---|---|---|---|---|---|---|---|---|---|
| FCFS | 16 | 0.176 | 0.177 (0.003) | +0.9% | 0.176 (0.003) | +0.2% | 0.176 | +0.5% | -0.2% |
| FCFS | 20 | 0.224 | 0.217 (0.003) | -3.1% | 0.215 (0.003) | -4.1% | 0.215 | -0.4% | -1.2% |
| FCFS | 24 | 0.233 | 0.228 (0.007) | -2.1% | 0.228 (0.007) | -2.3% | 0.226 | +0.0% | -0.2% |
| FCFS | 32 | 0.115 | 0.118 (0.007) | +2.7% | 0.126 (0.008) | +9.3% | 0.116 | +0.8% | +7.8% |
| FCFS | 48 | 0.049 | 0.072 (0.002) | +46.9% | 0.072 (0.002) | +47.9% | 0.063 | +14.4% | +14.4% |
| FCFS | 96 | 0.061 | 0.077 (0.002) | +26.3% | 0.076 (0.002) | +24.9% | 0.073 | +7.8% | +6.8% |
| FCFS | 300 | 0.108 | 0.111 (0.002) | +2.9% | 0.110 (0.002) | +2.3% | 0.111 | +0.7% | +0.3% |
| LPM(128) | 48 | 0.087 | 0.080 (0.002) | -8.1% | 0.110 (0.004) | +27.0% | 0.097 | -17.1% | +12.7% |
| LPM(128) | 300 | 0.105 | 0.111 (0.002) | +5.6% | 0.110 (0.002) | +5.1% | 0.110 | +1.7% | +1.3% |

20-seed hit fractions:

| policy | n | real hit | mixed hit | diff | separate hit | diff |
|---|---|---|---|---|---|---|
| FCFS | 16 | 0.932 | 0.932 | -0.000 | 0.932 | -0.000 |
| FCFS | 20 | 0.927 | 0.928 | +0.001 | 0.929 | +0.002 |
| FCFS | 24 | 0.888 | 0.895 | +0.007 | 0.897 | +0.010 |
| FCFS | 32 | 0.505 | 0.481 | -0.024 | 0.524 | +0.019 |
| FCFS | 48 | 0.000 | 0.001 | +0.001 | 0.013 | +0.013 |
| FCFS | 96 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |
| FCFS | 300 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |
| LPM(128) | 48 | 0.385 | 0.168 | -0.217 | 0.398 | +0.013 |
| LPM(128) | 300 | 0.000 | 0.000 | +0.000 | 0.000 | +0.000 |

Reading: with 20 seeds the real values at n = 16 to 32 and n = 300 sit within |z| < 0.7 of the simulator's mean in both modes (the plateau and the all-miss tail level are reproduced); n=48 (z = -2.3 mixed / -2.1 separate),
n=96 (-1.65 / -1.57) and, for separate, LPM n=48 (-1.5; turns-based -1.2) are the exceptions; mixed LPM n=48 is z = +0.63 on mu_sessions but +2.69 on the turns-based real value. The simulator's seed sd of mu_sessions
is about 9% to 15% of the mean at n = 24 to 300 (20 seeds), i.e. the single real run (and any 3-seed mean) carries a noise of the same size as the 15% tolerance; the criterion as declared (point comparison with a 15% band) is therefore a strict test
of a noisy quantity at n = 20..48.

## 8. Sensitivity arms (reported as sensitivities; none is used to pick the mode, the primary arm decides and the arms agree)

Relative error of the 3-seed mean mu_sessions against the real single run, per arm and mode. S1 = ratio_reserve (SGLang-like new_token_ratio with retraction, unverified scout constants); S2 = finished-session KV kept as evictable idle KV;
S3 = decode per-sequence slope 4.351e-5 s (separate only); S4 = S1 + S2.

| policy | n | real mu | primary mix | primary sep | S1 mix | S1 sep | S2 mix | S2 sep | S3 sep | S4 mix | S4 sep |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FCFS | 16 | 0.176 | +0.6% | +0.1% | +0.6% | +0.1% | +0.6% | -0.1% | +0.1% | +0.6% | -0.1% |
| FCFS | 20 | 0.224 | -5.0% | -5.8% | -4.8% | -5.7% | -7.2% | -7.8% | -5.8% | -6.5% | -7.0% |
| FCFS | 24 | 0.233 | -9.1% | -10.3% | -7.1% | -4.9% | -15.5% | -14.8% | -10.2% | -13.1% | -13.5% |
| FCFS | 32 (not judged) | 0.115 | +6.9% | +14.0% | +10.6% | +17.1% | -0.5% | +8.7% | +8.7% | +2.1% | +5.8% |
| FCFS | 48 | 0.049 | +42.4% | +43.2% | +42.0% | +39.4% | +42.8% | +43.6% | +43.9% | +41.3% | +40.9% |
| FCFS | 96 | 0.061 | +14.5% | +13.9% | +14.5% | +13.9% | +15.5% | +14.2% | +14.5% | +14.8% | +13.9% |
| FCFS | 300 | 0.108 | -1.4% | -1.7% | -1.5% | -2.4% | -1.4% | -1.7% | -3.1% | -1.5% | -2.4% |
| LPM(128) | 48 | 0.087 | -8.8% | +25.6% | -4.5% | +29.3% | -10.0% | +33.5% | +37.8% | -6.6% | +18.4% |
| LPM(128) | 300 | 0.105 | +1.2% | +0.9% | +1.8% | +0.2% | +1.2% | +0.9% | -0.5% | +1.8% | +0.2% |
| **mean abs rel.err (8 judged cells)** | | | 0.104 | 0.127 | 0.096 | 0.120 | 0.118 | 0.146 | 0.145 | 0.108 | 0.121 |
| **cells within 15%** | | | 7/8 | 6/8 | 7/8 | 6/8 | 5/8 | 6/8 | 6/8 | 7/8 | 6/8 |
| mean abs rel.err (turns-based real) | | | 0.053 | 0.053 | 0.045 | 0.046 | 0.065 | 0.065 | 0.066 | 0.057 | 0.045 |
| mean abs hit error | | | 0.028 | 0.013 | 0.025 | 0.010 | 0.038 | 0.009 | 0.012 | 0.031 | 0.008 |
| 0.5-hit crossing n (real 32.2) | | | 32.5 | 33.8 | 32.8 | 34.0 | 30.9 | 32.1 | 32.9 | 31.3 | 31.9 |
| argmax n (runner-up gap) | | | 20 (0.3%) | 20 (0.8%) | 24 (1.6%) | 24 (4.8%) | 20 (5.1%) | 20 (3.8%) | 20 (0.7%) | 20 (3.2%) | 20 (3.0%) |
| mu(300)/mu* (real 0.462) | | | 0.500 | 0.502 | 0.490 | 0.474 | 0.512 | 0.513 | 0.495 | 0.507 | 0.505 |

Reading: no sensitivity arm changes the verdict (every arm and mode has level_ok = False). The n=48 over-prediction (+39% to +44%) is invariant to all four modelling choices, so its cause is not any of them (the real dip
below the all-miss level, see caveats). S2 degrades the plateau (n=24: -15.5% mixed; presumably because finished-session KV then competes with live KV for the pool, not tested), and S1 improves it slightly. Mixed is closer than separate in every arm that has both.

## 9. Reserved-KV trace (why the modes differ), seed 0, FCFS, primary arm

Output of `calibration/round6_server_log_fit/validate_stagec_reserved_trace.py --seed 0 --n 48 300` (saved as `results/r6_validate_stagec/20261024-025222/reserved_trace_seed0.txt`; the numbers match the recorder's `reserved_tokens` in runs.csv):

```
# reserved-KV trace, primary arm (calibration.yaml unchanged, full_reserve), FCFS, seed 0, window [900, 2700) s
n=48 mixed: reserved mean 285047 min 247600 max 300000; time share with reserved<100k 0.00; time share in prefill calls 0.95; mean decode batch (time-weighted over decode calls) 25.9; calls P/D 2664/541
n=48 separate_prefill_priority: reserved mean 224313 min 69300 max 299850; time share with reserved<100k 0.02; time share in prefill calls 0.92; mean decode batch (time-weighted over decode calls) 17.3; calls P/D 2484/167
n=300 mixed: reserved mean 294657 min 282200 max 300000; time share with reserved<100k 0.00; time share in prefill calls 0.94; mean decode batch (time-weighted over decode calls) 38.1; calls P/D 3252/754
n=300 separate_prefill_priority: reserved mean 169507 min 8600 max 299850; time share with reserved<100k 0.28; time share in prefill calls 0.90; mean decode batch (time-weighted over decode calls) 3.8; calls P/D 2729/93
```

Mechanism (read from the trace and from the primary-arm diagnostics in `report.md`; the causal link to the hit fraction is consistent with the numbers but was not isolated by an intervention): in the all-miss regime the engine spends 90 to 95% of its time in iterations that carry
prefill in both modes, so mu is set by the prefill token rate (11.4k to 12.4k tok/s at n >= 96 in both modes) and the modes agree there. They differ in how long a request holds its full-reserve KV. In mixed mode each of a request's 100 decode steps rides on an
iteration that also carries a prefill chunk; the average prefill-carrying iteration lasts 0.64 s at n=48 (0.95 x 1800 s / 2664 calls) and 0.52 s at n=300 (0.94 x 1800 / 3252), so a reservation can be held for about a minute, and reserved KV stays at 285k (n=48) to 295k (n=300)
of 300k tokens, leaving idle cached prefixes 5.5k and 1.5k tokens (FCFS, 3-seed means from runs.csv). In separate mode decode runs only when no prefill is admissible, in pure-decode iterations that the calibrated model prices at 12 to 25 ms (calibration report table),
so reservations are released within seconds: reserved KV averages 224k (n=48) and 169k (n=300; 28% of the time below 100k) and idle cached KV averages 75k and 126k tokens. That extra idle cache is what the separate mode's higher hit fraction at FCFS n=32 and LPM n=48 would need.
Whether the real engine's held KV resembles the mixed or the separate trace was NOT tested here (SGLang allocates KV as tokens are produced, the simulator's full_reserve reserves the whole turn at admission; arm S1 is the closest switch and does not change the conclusion).

## 10. Caveats

- **Not modelled by the simulator** (declared in the spec): SGLang's waiting-prefix LRU refresh (`SGLANG_ENABLE_WAITING_PREFIX_REFRESH`, part of the `sglang-fcfs-r1` cell label; `meta.json` records `refresh_modelled: false`), radix-tree partial prefixes, page-size
  rounding, the overlap scheduler (and, per the engine docstring, `max_prefill_tokens`, the prefill delayers). Any of these could explain the real dip at n=48; this run does not test which.
- **Single-run real values.** Every real number is one run (seed 0). For the same runs the turns-based estimate is 29% (n=48) and 19% (n=96) higher than mu_sessions; the simulator's seed-to-seed sd of mu_sessions is about 14% of the mean there (20 seeds).
  The criterion compares a 3-seed simulator mean (se ~ 0.004 to 0.021) with that single value.
- **3 vs 20 seeds.** The registered result is the 3-seed one. The 20-seed supplement is labelled supplementary and was not used to change any verdict; it is shown because the 3-seed means at n = 24 and 32 carry se of 0.014 and 0.021.
- **Hit definitions** differ slightly (real: cached/prompt > 0.5 for turns completing in the window; sim: a resident session KV at admission, i.e. cached/prompt >= 0.79); the harness docstring argues they agree up to the time stamp; not tested separately here.
- **Cost model.** Calibration caveats stand: hit prefills cost more per attention pair than chunks (+17% to -11% error on hits), the shared per_token_s forces a decode per-sequence slope above the decode-only fit (arm S3 tested it: no effect on the verdict).
  LPM(128) n=48 depends on exactly that hit cost.
- The bistable cell FCFS n=32 is reported but not judged; its simulated mu has a per-seed sd of 0.03 to 0.04 (20 seeds), i.e. 27% to 29% of the mean.
- No waiting-time or latency quantity was validated; only mu(n) and the hit fraction.
- meta.json `hardware` string is wrong (see section 1). The smoke run `results/r6_validate_stagec_smoke_quick/20261024-025148/` is not cited and not committed.

## 11. Reproduction and tests

Re-running the commands in section 1 on commit `cda031449d5c2d2c5e8339ebff70c1a76bc7126b` reproduces `runs.csv` bit for bit (deterministic given spec and seed, independent of the worker count; checked 2 vs 6 workers).

Tests (this machine, `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe -m pytest -p no:cacheprovider`, full suite, log `results/r6_validate_stagec/full_suite_pytest.log`):

- totals: **32 failed, 1005 passed, 2 skipped, 3058 warnings in 858.67s (0:14:18)**
- FAILED on the known list: 6 of the 6 `test_full_reserve_is_bit_identical_to_the_round4_engine[*]`, 12 of the 12 `test_mixed_mode_is_bit_identical_to_the_engine_before_the_option[*]` parametrizations (the brief says 13; the test file defines 12, and all 12 fail here, so 18 bit-identity failures in total, not 19), 14 POSIX-glue failures (tests/test_agentload_e2e.py, tests/test_agentload_gate.py, tests/test_agentload_robustness.py, tests/test_mech_runner.py, tests/test_slurm_scripts.py).
- FAILED outside the known list: none.
- On the known list but PASSING here: `tests/test_analysis_pipeline.py::test_stable_cli` (re-run alone: passed). The known-failure list otherwise matches the observed failures family for family (32 failed = 6 + 12 bit-identity + 8 `test_slurm_scripts.py` + 2 `test_agentload_e2e.py` + 1 `test_agentload_gate.py` + 2 `test_agentload_robustness.py` + 1 `test_mech_runner.py`).
- Targeted check on cda0314 (the 18 bit-identity failures were seen before the registered run; the totals below are from a re-run after it): `tests/test_r6_validate.py` alone 19 passed; `tests/test_r6_validate.py tests/test_batching.py tests/test_r5_engine.py` gave 18 failed, 246 passed (the 18 failures are exactly the bit-identity ones above).
