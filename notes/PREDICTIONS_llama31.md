# Round 12: blind predictions of the calibrated simulator for the real SGLang 0.5.22 + Llama-3.1-8B-Instruct experiments (KV pool 300,000 tokens)

Written on branch `r12/llama31-predict` (from `origin/main` 582c2a6) by the Llama-cell session, 2026-10-31 ~02:15 CDT. These are blind predictions of the **calibrated SGLang/Qwen-fitted simulator** (`src/prefixmeta/`, cost constants fitted to SGLang 0.5.22 server logs with Qwen2.5-7B-Instruct) for the real Llama-3.1-8B cell: SGLang 0.5.22 + NousResearch/Meta-Llama-3.1-8B-Instruct @ d10aef7 (shards byte-identical to meta-llama 0e9e39f2), KV pool capped at 300,000 tokens, one A100 80GB PCIe, label `sglang-fcfs-r1-llama31`. The machinery is round 9's (vLLM cell) under renamed files; the spec's engine, workload, metrics and r7 blocks are round 9's verbatim.

* **V0**: the calibrated engine unchanged, every result in multiples of its own lambda_miss. It reproduces round 9's V0 exactly: every simulated column of the lambda_miss, curve, edge and paired-arm tables is identical to `results/r9_vllm_report/20261030-122723/` (only wall-clock times and the conversions to real units, which use Llama's lambda_miss here, differ). V0 is the "dimensionless" reference.
* **V1 (headline)**: `per_token_s`, `prefill_attn_s`, `decode_attn_s` multiplied by one factor per mode so that the all-miss uncached token rate equals Llama's measured **9,353 tok/s** (E0a, 3 seeds): **f = 1.2121 (mixed), 1.2040 (separate)**; accepted check rates 9,348.2 and 9,340.4 tok/s (-0.05%, -0.13%). V1's lambda_miss (0.05963 / 0.05969 sessions/s) is a by-product that matches the real 0.05964, but the real value was known when V1 was fitted: a consistency check, not a blind output.
* **Commits.** Spec declared and pushed before any Llama GPU job started: `cce2d0b` (2026-10-30 22:31:57 CDT; spec sha256 `f78e6963...`). Real inputs filled from the E0a calibration: `cec7043` (02:07:11). Factors frozen from the quick B1 check run on clean `cec7043`: `6847dde` (02:07:45; spec sha256 `95c4b6ca...`). All four trees and the report ran on clean `6847dde` (02:07:53 to 02:10:57; `bash experiments/r12_llama31_predict_run.sh`); `tests/test_r12_llama31_predict.py` 17 passed.
* **Nothing was cut**: both variants, both modes, every candidate multiple (1.10 extra, 1.15 to 2.35) and every cap (16 to 32, 40 extra) ran in full.

## 0. Headline predictions (V1 mixed primary; V1 separate and V0 alongside)

| quantity | V1 mixed | V1 separate | V0 mixed | V0 separate |
|---|---|---|---|---|
| lambda_miss turns-based (sessions/s) | 0.0596 (fitted) | 0.0597 (fitted) | 0.0722 | 0.0714 |
| peak n of mu(n) | **20** | **20** | 24 | 24 |
| peak mu (turns-based, sessions/s) | 0.210 | 0.208 | 0.222 | 0.221 |
| peak mu / lambda_miss | **3.52** | **3.48** | 3.07 | 3.10 |
| cap n (smallest_within_margin, 5%) | **20** | **20** | 20 | 20 |
| n at hit 0.5 (cliff) | **30.6** | **31.6** | 31.5 | 32.6 |
| from-empty edge hi (x lambda_miss) | **2.5** | **2.0** | 2.0 | 2.0 |
| stable runs at 2.5 x / 3.0 x (of 10) | 10 / 5 | 8 / 4 | 6 / 1 | 8 / 1 |
| registered points the edge would give | 1.5, 2.0 | 1.35, 1.65 | 1.35, 1.65 | 1.35, 1.65 |
| paired test at those points, cap 20 | PASS, PASS | PASS, PASS | PASS, PASS | PASS, PASS |

Closed curve, V1 mixed, seed-mean turns-based mu / hit (10 seeds): n = 16: 0.173 / 0.93; 20: 0.210 / 0.93; 24: 0.200 / 0.88; 28: 0.145 / 0.72; 32: 0.086 / 0.38; 40: 0.059 / 0.01; 48: 0.059 / 0.00; 96: 0.068 / 0.00; 300: 0.099 / 0.00. V1 separate: 0.172 / 0.93, 0.208 / 0.93, 0.206 / 0.89, 0.151 / 0.74, 0.099 / 0.47, 0.063 / 0.08, 0.060 / 0.01, 0.068 / 0.00, 0.099 / 0.00.

**Readings.**
* **The shape transfers; the scale shifts slightly.** With Llama's slower clock (f about 1.21) and the same pool in tokens, V1 predicts the same curve as Qwen with the peak one grid step earlier (n = 20 instead of 24; n = 24 is 4.8% (mixed) and 1.0% (separate) below the peak, so the argmax is a near-tie), the cliff about one session earlier (0.5-hit crossing 30.6 / 31.6 vs 31.5 / 32.6), the plateau hit 0.93, and the post-cliff floor at about lambda_miss (0.059-0.060 at n = 40-48). The pool's session capacity does not change (the pool is in tokens), so the knee stays near n = 20-30.
* **The peak is higher in units of lambda_miss** (3.52 / 3.48 vs 3.07 / 3.10): with fixed Exp(5 s) tool time, a slower engine lowers lambda_miss (all service) more than the peak (mostly tool time). This is the dimensional effect the V0 / V1 contrast isolates.
* **From-empty edge (B2v, the real E0b grid):** V1 mixed stable 10/10 at 1.25-2.5 x and 5/10 at 3.0 x (edge 2.5; 0.95 stable-fraction crossing at 2.55 x); V1 separate 10/10 at 1.25-2.0 x, 8/10 at 2.5 x, 4/10 at 3.0 x (edge 2.0; crossings 0.95 at 2.13 x, 0.5 at 2.88 x). V0 (both modes): edge 2.0, 2.5 x stable 6/10 (mixed) and 8/10 (separate), 3.0 x 1/10. The real E0b runs one seed per multiple, so: the single 2.5 x run is predicted stable with probability 0.8-1.0 under V1 (0.6-0.8 under V0), the single 3.0 x run with probability 0.4-0.5 under V1 (0.1 under V0). **Predicted real edge: 2.5 x most likely under V1 (2.0 x under V0); 3.0 x possible under V1.** The edge moves up against Qwen's 2.0 x for the same reason the peak ratio does.
* **Paired test (B3v), cap 20:** PASS at every candidate multiple from 1.10 to 2.35 x in both V1 modes under both rules (BURST trapped 7-9/10, NOBURST good 9-10/10, CAPPED recovered 10/10). In particular PASS at **1.35 / 1.65 x** (V1 mixed 9/10/10 and 8/10/10; separate 9/10/10 and 9/10/10) and at **1.5 / 2.0 x** (mixed 9/10/10 and 9/10/10; separate 8/10/10 and 9/10/10), the two pairs a real edge of 2.0 or 2.5 x registers, and at **1.65 / 2.35 x** (hi = 3.0; mixed 8/10/10 and 9/9/10, separate 9/10/10 and 9/9/10). V0 fails at 1.10-1.15 x (the slope test) and 2.35 x (NOBURST collapses from empty), exactly as in round 9. Every BURST run ends at hit 0.000 in every configuration; trapped runs process 0.985-1.068 x the all-miss token rate; the BURST backlog in the evaluation window grows from about 123-132 (1.10 x) to 216-223 (1.5 x), 341-351 (2.0 x) and 440-450 (2.35 x).
* **Cap sensitivity (V1):** caps 16, 20 and 24 recover 10/10 at every multiple up to 2.0 x (cap 16: 6/10 at 2.35 x); cap 28 recovers 8-10/10 up to 1.65 x and 4/10 (mixed) / 7/10 (separate) at 2.0 x; cap 32 sits on the cliff (0-8/10, 0/10 from 1.5-1.65 x up); cap 40 never recovers.

## Blindness: what was and was not used

* **Read before the freeze (inputs):** this cell's E0a 3-seed calibration (`results/cal_llama31/calibration.json`, sha256 `7c2cb2de...`, job 17168803 over E0a jobs 17166823/29/31), the POP-64 check job's printed calibration (17166833: 9,518 tok/s), the banners, the smoke's canary / probe lines, sacct states and MaxRSS, and the `max_total_num_tokens=300000` line of every server.log. Prior knowledge of the other cells (the Qwen 300k and native cells, vLLM) from LOG.md, which the predictor had read.
* **Not read before the tag was pushed:** any Llama Stage C or E0b output (`logs/pm-l31-c-*.out`, `logs/pm-l31-e0b-*.out`, any run directory, any `agentload_analysis_closed` / `agentload_analysis_stable` of this cell), and the lead's separate first-principles theory predictions for this cell (not opened; the lead asked that neither prediction see the other).
* **Blind in time:** at the push, Stage C jobs 17166814-16 were still RUNNING (started 00:48 and 01:08 CDT), the E0b jobs 17169565-70 were PENDING (not started), and no E2 job existed. The E0b grid (default) was chosen by the fixed R_bound rule from E0a alone (R_bound = 5.85) before this prediction ran.
* **Not modelled:** the single factor scales prefill and decode costs together; Llama's decode attention reads 2.29 x more KV bytes per token than Qwen's, so the real decode slow-down is probably larger than f, which the simulator does not capture.

## Provenance: what was run

Generated by `python -m prefixmeta.r12_llama31_predict assemble` from the report `results/r12_llama31_report/20261031-021057` (the tables below are that report's `tables.md`, verbatim; nothing is retyped).

Spec: `configs/r12_llama31_predict.yaml` (sha256 `95c4b6ca3d1df26b4d0a0c31a448abe2fec843a581488edfc8a77cdd4c6ae53b`; the first commit of the spec, before any run, had sha256 recorded in the notes); KV pool 300,000 tokens; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes (the stages run one after the other).

**V0 / mixed** (`engine.batching` = `mixed`, out-root `results/r12_llama31_v0_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r12_llama31_v0_mixed/r7_lambda_miss/20261031-020754 | 6847dde87 | False | 0..2 (3) | 2026-10-31T02:07:54 | 1.3 | True | - |
| curves | results/r12_llama31_v0_mixed/r7_curves/20261031-020756 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:07:56 | 2.3 | True | - |
| edge | results/r12_llama31_v0_mixed/r7_edge/20261031-020800 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:08:00 | 2 | True | - |
| pairs_all | results/r12_llama31_v0_mixed/r7_pairs_all/20261031-020803 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:08:03 | 34.5 | True | - |

Recorded stage wall time: 40 s (0.7 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_mixed
experiments/r7_robustness_run.py curves --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_mixed
experiments/r7_robustness_run.py edge --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_mixed
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\llama31-predict\src\prefixmeta\r12_llama31_predict.py pairs_all --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_mixed
```

**V0 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r12_llama31_v0_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r12_llama31_v0_separate/r7_lambda_miss/20261031-020841 | 6847dde87 | False | 0..2 (3) | 2026-10-31T02:08:40 | 1.5 | True | engine.batching=separate_prefill_priority |
| curves | results/r12_llama31_v0_separate/r7_curves/20261031-020843 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:08:43 | 2.7 | True | engine.batching=separate_prefill_priority |
| edge | results/r12_llama31_v0_separate/r7_edge/20261031-020847 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:08:47 | 2.5 | True | engine.batching=separate_prefill_priority |
| pairs_all | results/r12_llama31_v0_separate/r7_pairs_all/20261031-020851 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:08:51 | 34.1 | True | engine.batching=separate_prefill_priority |

Recorded stage wall time: 41 s (0.7 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py curves --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py edge --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_separate --set engine.batching=separate_prefill_priority
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\llama31-predict\src\prefixmeta\r12_llama31_predict.py pairs_all --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v0_separate --set engine.batching=separate_prefill_priority
```

**V1 / mixed** (`engine.batching` = `mixed`, out-root `results/r12_llama31_v1_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r12_llama31_v1_mixed/r7_lambda_miss/20261031-020928 | 6847dde87 | False | 0..2 (3) | 2026-10-31T02:09:28 | 1.2 | True | engine.per_token_s=7.5877460000e-05 engine.prefill_attn_s=2.7151040000e-09 engine.decode_attn_s=3.7575100000e-04 |
| curves | results/r12_llama31_v1_mixed/r7_curves/20261031-020930 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:09:30 | 2.5 | True | engine.per_token_s=7.5877460000e-05 engine.prefill_attn_s=2.7151040000e-09 engine.decode_attn_s=3.7575100000e-04 |
| edge | results/r12_llama31_v1_mixed/r7_edge/20261031-020933 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:09:33 | 1.9 | True | engine.per_token_s=7.5877460000e-05 engine.prefill_attn_s=2.7151040000e-09 engine.decode_attn_s=3.7575100000e-04 |
| pairs_all | results/r12_llama31_v1_mixed/r7_pairs_all/20261031-020936 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:09:36 | 32 | True | engine.per_token_s=7.5877460000e-05 engine.prefill_attn_s=2.7151040000e-09 engine.decode_attn_s=3.7575100000e-04 |

Recorded stage wall time: 38 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_mixed --set engine.per_token_s=7.5877460000e-05 --set engine.prefill_attn_s=2.7151040000e-09 --set engine.decode_attn_s=3.7575100000e-04
experiments/r7_robustness_run.py curves --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_mixed --set engine.per_token_s=7.5877460000e-05 --set engine.prefill_attn_s=2.7151040000e-09 --set engine.decode_attn_s=3.7575100000e-04
experiments/r7_robustness_run.py edge --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_mixed --set engine.per_token_s=7.5877460000e-05 --set engine.prefill_attn_s=2.7151040000e-09 --set engine.decode_attn_s=3.7575100000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\llama31-predict\src\prefixmeta\r12_llama31_predict.py pairs_all --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_mixed --set engine.per_token_s=7.5877460000e-05 --set engine.prefill_attn_s=2.7151040000e-09 --set engine.decode_attn_s=3.7575100000e-04
```

**V1 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r12_llama31_v1_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r12_llama31_v1_separate/r7_lambda_miss/20261031-021012 | 6847dde87 | False | 0..2 (3) | 2026-10-31T02:10:11 | 1.4 | True | engine.batching=separate_prefill_priority engine.per_token_s=7.5370400000e-05 engine.prefill_attn_s=2.6969600000e-09 engine.decode_attn_s=3.7324000000e-04 |
| curves | results/r12_llama31_v1_separate/r7_curves/20261031-021014 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:10:14 | 2.7 | True | engine.batching=separate_prefill_priority engine.per_token_s=7.5370400000e-05 engine.prefill_attn_s=2.6969600000e-09 engine.decode_attn_s=3.7324000000e-04 |
| edge | results/r12_llama31_v1_separate/r7_edge/20261031-021018 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:10:18 | 2.1 | True | engine.batching=separate_prefill_priority engine.per_token_s=7.5370400000e-05 engine.prefill_attn_s=2.6969600000e-09 engine.decode_attn_s=3.7324000000e-04 |
| pairs_all | results/r12_llama31_v1_separate/r7_pairs_all/20261031-021021 | 6847dde87 | False | 0..9 (10) | 2026-10-31T02:10:21 | 33.3 | True | engine.batching=separate_prefill_priority engine.per_token_s=7.5370400000e-05 engine.prefill_attn_s=2.6969600000e-09 engine.decode_attn_s=3.7324000000e-04 |

Recorded stage wall time: 40 s (0.7 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=7.5370400000e-05 --set engine.prefill_attn_s=2.6969600000e-09 --set engine.decode_attn_s=3.7324000000e-04
experiments/r7_robustness_run.py curves --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=7.5370400000e-05 --set engine.prefill_attn_s=2.6969600000e-09 --set engine.decode_attn_s=3.7324000000e-04
experiments/r7_robustness_run.py edge --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=7.5370400000e-05 --set engine.prefill_attn_s=2.6969600000e-09 --set engine.decode_attn_s=3.7324000000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\llama31-predict\src\prefixmeta\r12_llama31_predict.py pairs_all --spec configs/r12_llama31_predict.yaml --workers 6 --out-root results/r12_llama31_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=7.5370400000e-05 --set engine.prefill_attn_s=2.6969600000e-09 --set engine.decode_attn_s=3.7324000000e-04
```

Total recorded stage wall time over the four trees: 158 s (2.6 min).

## Tables (generated)

## Overview

Landmarks per variant and mode:

| variant | mode | lambda_miss turns-based (sessions/s) | all-miss token rate (tok/s) | peak n | peak mu (sessions/s) | peak mu / lambda_miss | cap n (B4v rule) | n at hit 0.5 | edge hi (x lambda_miss) | edge in real units (hi x 0.05964) | edge censored |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 0.07219 | 1.122e+04 | 24 | 0.2217 | 3.071 | 20 | 31.46 | 2 | 0.1193 | False |
| V0 | separate | 0.07136 | 1.115e+04 | 24 | 0.2208 | 3.095 | 20 | 32.6 | 2 | 0.1193 | False |
| V1 | mixed | 0.05963 | 9348 | 20 | 0.21 | 3.522 | 20 | 30.62 | 2.5 | 0.1491 | False |
| V1 | separate | 0.05969 | 9340 | 20 | 0.208 | 3.485 | 20 | 31.58 | 2 | 0.1193 | False |

B3v at the cap the B4v rule picks, every candidate multiple (the full tables, with the other caps, are in the blocks below):

| variant | mode | x lambda_miss | picked cap | BURST trapped | NOBURST good | CAPPED recovered | PASS per-arm | same-seed count | PASS same-seed |
|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 1.1 | 20 | 4/10 | 10/10 | 10/10 | FAIL | 4/10 | FAIL |
| V0 | mixed | 1.15 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.5 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V0 | mixed | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2 | 20 | 10/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.1 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.15 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.25 | 20 | 10/10 | 10/10 | 10/10 | PASS | 10/10 | PASS |
| V0 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 1.5 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V1 | mixed | 1.1 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | mixed | 1.15 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.5 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.65 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | mixed | 2 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 2.35 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.1 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | separate | 1.15 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | separate | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.5 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | separate | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 2 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 2.35 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |

## V0 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 0.071986 | 1 |

Reference values (the two real Llama-3.1-8B numbers from this cell's E0a 3-seed combine, not outputs of the simulator): measured all-miss uncached rate 9,353 tok/s, measured lambda_miss 0.05964 sessions/s. This block: token rate 11,219.7 tok/s = 1.1996 x the Llama rate; lambda_miss 0.07219 sessions/s = 1.2104 x the Llama value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1767 / 0.93 |
| 20 | 0.2156 / 0.93 |
| 24 | 0.2217 / 0.89 |
| 28 | 0.1672 / 0.74 |
| 32 | 0.1122 / 0.46 |
| 40 | 0.0727 / 0.03 |
| 48 | 0.0711 / 0.00 |
| 96 | 0.0786 / 0.00 |
| 300 | 0.1119 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2217 | 20 | 0.5047 | 0 | 24 | 0.222 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2217 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.071 |
| hit fraction at the peak n | 0.8898 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.222 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.46 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.99 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 36.9 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.6, s1: 32.8, s2: 30.5, s3: 30.4, s4: 30.4, s5: 32.8, s6: 31.3, s7: 32.1, s8: 33.3, s9: 30.0 |
| mu(300) / peak mu | 0.5047 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0239; -0.1607 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1735 / 0.1774 / 0.1766 / 0.1733 / 0.1790 / 0.1787 / 0.1769 / 0.1776 / 0.1761 / 0.1784 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2130 / 0.2170 / 0.2132 / 0.2137 / 0.2201 / 0.2108 / 0.2156 / 0.2179 / 0.2174 / 0.2176 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2261 / 0.2224 / 0.1904 / 0.2063 / 0.2435 / 0.1813 / 0.2105 / 0.2476 / 0.2473 / 0.2413 | 0.91 / 0.89 / 0.85 / 0.88 / 0.91 / 0.84 / 0.87 / 0.92 / 0.92 / 0.91 |
| 28 | 0.2032 / 0.1871 / 0.1413 / 0.1462 / 0.1729 / 0.1244 / 0.1241 / 0.1979 / 0.2083 / 0.1667 | 0.82 / 0.79 / 0.70 / 0.70 / 0.76 / 0.65 / 0.62 / 0.81 / 0.82 / 0.75 |
| 32 | 0.1458 / 0.1285 / 0.0935 / 0.0959 / 0.0866 / 0.1246 / 0.1081 / 0.1184 / 0.1415 / 0.0786 | 0.62 / 0.55 / 0.38 / 0.37 / 0.33 / 0.55 / 0.48 / 0.51 / 0.60 / 0.25 |
| 40 | 0.0735 / 0.0699 / 0.0765 / 0.0704 / 0.0643 / 0.0830 / 0.0744 / 0.0735 / 0.0738 / 0.0674 | 0.02 / 0.00 / 0.07 / 0.03 / 0.00 / 0.07 / 0.05 / 0.05 / 0.01 / 0.03 |
| 48 | 0.0706 / 0.0702 / 0.0734 / 0.0698 / 0.0637 / 0.0775 / 0.0739 / 0.0749 / 0.0725 / 0.0650 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0750 / 0.0741 / 0.0783 / 0.0788 / 0.0743 / 0.0784 / 0.0785 / 0.0880 / 0.0793 / 0.0817 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1128 / 0.1102 / 0.1105 / 0.1142 / 0.1103 / 0.1098 / 0.1104 / 0.1148 / 0.1145 / 0.1113 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1444 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07219; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.05964 sessions/s) the same multiple is 0.1193 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.06 x and through 0.5 at 2.6 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07941 | hi = 1.25 (low) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.996 to 1.010 | 148.8 | 0 | 0.007708 | IITTIITTII | RRRRRRRRRR |
| 1.15 | 0.08301 | hi = 1.25 (high); hi = 1.5 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.994 to 1.015 | 152.3 | 0 | 0.008271 | ITTTIITTTI | RRRRRRRRRR |
| 1.25 | 0.09023 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.999 to 1.020 | 170.5 | 0 | 0.0097 | TTTTITTTTT | RRRRRRRRRR |
| 1.35 | 0.09745 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.006 to 1.026 | 198.4 | 0 | 0.01067 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.1083 | hi = 1.75 (high); hi = 2.5 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.018 to 1.034 | 249.9 | 0 | 0.01289 | TTTTIITTTI | RRRRRRRRRR |
| 1.65 | 0.1191 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.027 to 1.043 | 290.2 | 0 | 0.01506 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1444 | hi = 2.5 (high) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.048 to 1.059 | 399.1 | 0 | 19.56 | TTTTTTTTTT | RRRRRTRRRR |
| 2.35 | 0.1696 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.063 to 1.073 | 522.5 | 0 | 120.4 | TTTTTTTTTT | RRTRRTRTRT |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.01176 | 0.9312 |
| 1.1 (extra) | 20 * | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00771 | 0.9312 |
| 1.1 (extra) | 24 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00769 | 0.9312 |
| 1.1 (extra) | 28 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.007709 | 0.9312 |
| 1.1 (extra) | 32 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 19.21 | 0.7532 |
| 1.1 (extra) | 40 (extra) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.8 | 0.08885 |
| 1.15 | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01589 | 0.9314 |
| 1.15 | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008452 | 0.9314 |
| 1.15 | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008271 | 0.9314 |
| 1.15 | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00829 | 0.9314 |
| 1.15 | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 25.26 | 0.7722 |
| 1.15 | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.8 | 0.08945 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.04198 | 0.9308 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01006 | 0.9308 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0097 | 0.9308 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009669 | 0.9308 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 36.17 | 0.7766 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 235.1 | 0.08596 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06429 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0184 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01068 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01074 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 60.62 | 0.6711 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 276.3 | 0.08874 |
| 1.5 | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.09209 | 0.9313 |
| 1.5 | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01914 | 0.9314 |
| 1.5 | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01313 | 0.9314 |
| 1.5 | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.8441 | 0.9234 |
| 1.5 | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 128.3 | 0.4841 |
| 1.5 | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 345.5 | 0.08463 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1464 | 0.9313 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01706 | 0.9313 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01505 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 6.718 | 0.9098 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.6 | 0.4838 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 417 | 0.08505 |
| 2 | 16 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 21.95 | 0.9331 |
| 2 | 20 * | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2795 | 0.9332 |
| 2 | 24 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06608 | 0.9319 |
| 2 | 28 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 5/10 (0.50) [0.24, 0.76] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 55.58 | 0.834 |
| 2 | 32 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 358.9 | 0.4929 |
| 2 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 585.8 | 0.07931 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 174.9 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.569 | 0.9317 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.028 | 0.9242 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 165 | 0.79 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 528.2 | 0.4758 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 760.2 | 0.07562 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTIITTII | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | ITTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTTTTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RRTRRTRTRT | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V0 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.071359 | 0.0012945 | 0.068889 | 11147 | 0.99999 | 0.071221 | 1 |

Reference values (the two real Llama-3.1-8B numbers from this cell's E0a 3-seed combine, not outputs of the simulator): measured all-miss uncached rate 9,353 tok/s, measured lambda_miss 0.05964 sessions/s. This block: token rate 11,146.8 tok/s = 1.1918 x the Llama rate; lambda_miss 0.07136 sessions/s = 1.1965 x the Llama value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1755 / 0.93 |
| 20 | 0.2137 / 0.93 |
| 24 | 0.2208 / 0.89 |
| 28 | 0.1797 / 0.77 |
| 32 | 0.1222 / 0.53 |
| 40 | 0.0767 / 0.11 |
| 48 | 0.0710 / 0.01 |
| 96 | 0.0781 / 0.00 |
| 300 | 0.1115 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2208 | 20 | 0.5051 | 0 | 24 | 0.2215 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2208 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.095 |
| hit fraction at the peak n | 0.8917 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2215 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 32.6 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 23.14 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 38.22 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 34.6, s1: 33.4, s2: 31.1, s3: 32.4, s4: 31.2, s5: 33.2, s6: 31.8, s7: 32.6, s8: 33.6, s9: 32.1 |
| mu(300) / peak mu | 0.5051 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0184; -0.1633 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1724 / 0.1764 / 0.1754 / 0.1721 / 0.1777 / 0.1773 / 0.1755 / 0.1766 / 0.1750 / 0.1771 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2099 / 0.2152 / 0.2110 / 0.2118 / 0.2177 / 0.2100 / 0.2134 / 0.2161 / 0.2157 / 0.2158 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2248 / 0.2183 / 0.1910 / 0.2204 / 0.2358 / 0.1933 / 0.2144 / 0.2453 / 0.2385 / 0.2267 | 0.91 / 0.89 / 0.85 / 0.89 / 0.91 / 0.86 / 0.88 / 0.91 / 0.91 / 0.90 |
| 28 | 0.2015 / 0.1939 / 0.1445 / 0.1490 / 0.1932 / 0.1313 / 0.1476 / 0.2251 / 0.2204 / 0.1903 | 0.82 / 0.80 / 0.71 / 0.70 / 0.79 / 0.67 / 0.69 / 0.84 / 0.84 / 0.79 |
| 32 | 0.1520 / 0.1417 / 0.0980 / 0.1185 / 0.1017 / 0.1256 / 0.1101 / 0.1218 / 0.1415 / 0.1112 | 0.65 / 0.60 / 0.44 / 0.52 / 0.43 / 0.57 / 0.49 / 0.53 / 0.60 / 0.50 |
| 40 | 0.0871 / 0.0723 / 0.0801 / 0.0753 / 0.0694 / 0.0829 / 0.0771 / 0.0754 / 0.0802 / 0.0670 | 0.20 / 0.06 / 0.13 / 0.12 / 0.09 / 0.09 / 0.10 / 0.11 / 0.11 / 0.05 |
| 48 | 0.0701 / 0.0700 / 0.0763 / 0.0694 / 0.0627 / 0.0774 / 0.0733 / 0.0741 / 0.0718 / 0.0647 | 0.01 / 0.00 / 0.05 / 0.01 / 0.00 / 0.01 / 0.01 / 0.00 / 0.00 / 0.01 |
| 96 | 0.0752 / 0.0737 / 0.0772 / 0.0777 / 0.0743 / 0.0778 / 0.0781 / 0.0871 / 0.0784 / 0.0814 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1125 / 0.1099 / 0.1102 / 0.1137 / 0.1102 / 0.1098 / 0.1100 / 0.1144 / 0.1139 / 0.1109 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.0892 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001459 | 0.9314 | 0 |
| Exp(5 s) (record) | 1.5 | 0.107 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006232 | 0.9297 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1249 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0009475 | 0.9294 | 0 |
| Exp(5 s) (record) | 2 | 0.1427 | 10/10 (1.00) [0.72, 1.00] | True | 0.4 | 4 | 0.4368 | 0.9257 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1784 | 8/10 (0.80) [0.49, 0.94] | False | 18.6 | 115 | 16.01 | 0.801 | 0 |
| Exp(5 s) (record) | 3 | 0.2141 | 1/10 (0.10) [0.02, 0.40] | False | 177 | 283 | 124.2 | 0.2039 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.071359 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1427 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07136; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.05964 sessions/s) the same multiple is 0.1193 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.12 x and through 0.5 at 2.71 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07849 | hi = 1.25 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.005 | 149.7 | 0 | 0.007337 | IITTTITTIT | RRRRRRRRRR |
| 1.15 | 0.08206 | hi = 1.25 (high); hi = 1.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.015 | 161.3 | 0 | 0.008262 | TTTTTITTTI | RRRRRRRRRR |
| 1.25 | 0.0892 | hi = 1.75 (low) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.995 to 1.015 | 179.5 | 0 | 0.009333 | TTTTTTTTTT | RRRRRRRRRR |
| 1.35 | 0.09633 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.021 | 206.9 | 0 | 0.01043 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.107 | hi = 1.75 (high); hi = 2.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.014 to 1.027 | 252.4 | 0 | 0.0124 | TTTTIITTTT | RRRRRRRRRR |
| 1.65 | 0.1177 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.022 to 1.038 | 295.4 | 0 | 0.01452 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1427 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.043 to 1.051 | 409.2 | 0 | 20.24 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1677 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.066 | 521.4 | 0 | 125.5 | TTTTTTTTTT | RTTRRTRTRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01119 | 0.9313 |
| 1.1 (extra) | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007326 | 0.9313 |
| 1.1 (extra) | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007339 | 0.9313 |
| 1.1 (extra) | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00732 | 0.9313 |
| 1.1 (extra) | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 6.446 | 0.8805 |
| 1.1 (extra) | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 140.2 | 0.1696 |
| 1.15 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02577 | 0.9316 |
| 1.15 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008418 | 0.9316 |
| 1.15 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008245 | 0.9316 |
| 1.15 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008253 | 0.9316 |
| 1.15 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 5/10 (0.50) [0.24, 0.76] | FAIL | 11.26 | 0.8277 |
| 1.15 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 167.9 | 0.1429 |
| 1.25 | 16 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.04704 | 0.9307 |
| 1.25 | 20 * | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01016 | 0.9307 |
| 1.25 | 24 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009299 | 0.9307 |
| 1.25 | 28 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009296 | 0.9307 |
| 1.25 | 32 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 1 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 18.64 | 0.8112 |
| 1.25 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 211.2 | 0.1688 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06025 | 0.9308 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01775 | 0.9308 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0105 | 0.9308 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01043 | 0.9308 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 29.79 | 0.7971 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 249 | 0.1521 |
| 1.5 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.09019 | 0.9313 |
| 1.5 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02162 | 0.9313 |
| 1.5 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.014 | 0.9313 |
| 1.5 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01245 | 0.9313 |
| 1.5 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 79.29 | 0.6274 |
| 1.5 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 313.1 | 0.1551 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1452 | 0.9312 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01615 | 0.9312 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01464 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2905 | 0.9286 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 134.6 | 0.5421 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 386.9 | 0.1566 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 19.74 | 0.9331 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2189 | 0.9331 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05659 | 0.9323 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 27.86 | 0.8781 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 306.7 | 0.5455 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 561.4 | 0.1339 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.3 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.461 | 0.9321 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.2392 | 0.9277 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 121.2 | 0.8169 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 457.7 | 0.5362 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 724.6 | 0.1379 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRTRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.059629 | 0.001229 | 0.058704 | 9348.2 | 1 | 0.060783 | 1 |

Reference values (the two real Llama-3.1-8B numbers from this cell's E0a 3-seed combine, not outputs of the simulator): measured all-miss uncached rate 9,353 tok/s, measured lambda_miss 0.05964 sessions/s. This block: token rate 9,348.2 tok/s = 0.9995 x the Llama rate; lambda_miss 0.05963 sessions/s = 0.9998 x the Llama value. V1 factor f = 1.2121 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 9,348.22 tok/s, -0.05% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1733 / 0.93 |
| 20 | 0.2100 / 0.93 |
| 24 | 0.2005 / 0.88 |
| 28 | 0.1454 / 0.72 |
| 32 | 0.0863 / 0.38 |
| 40 | 0.0592 / 0.01 |
| 48 | 0.0592 / 0.00 |
| 96 | 0.0685 / 0.00 |
| 300 | 0.0995 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 20 | 0.21 | 20 | 0.4738 | 0 | 20 | 0.2108 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 20 |
| peak mu (turns-based sessions/s) | 0.21 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.522 |
| hit fraction at the peak n | 0.9301 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 20 / 0.2108 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 30.62 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.23 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 35.96 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 32.9, s1: 29.9, s2: 30.2, s3: 30.4, s4: 29.3, s5: 33.1, s6: 29.6, s7: 31.4, s8: 32.5, s9: 29.8 |
| mu(300) / peak mu | 0.4738 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0526; -0.1312 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1708 / 0.1742 / 0.1727 / 0.1696 / 0.1756 / 0.1748 / 0.1734 / 0.1745 / 0.1731 / 0.1747 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2078 / 0.2120 / 0.2067 / 0.2082 / 0.2142 / 0.2036 / 0.2096 / 0.2130 / 0.2126 / 0.2124 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2126 / 0.2043 / 0.1502 / 0.2017 / 0.2241 / 0.1391 / 0.1829 / 0.2352 / 0.2322 / 0.2226 | 0.90 / 0.88 / 0.81 / 0.88 / 0.91 / 0.79 / 0.86 / 0.91 / 0.92 / 0.90 |
| 28 | 0.2074 / 0.1728 / 0.1016 / 0.1362 / 0.1148 / 0.1304 / 0.1174 / 0.1810 / 0.1709 / 0.1218 | 0.85 / 0.80 / 0.62 / 0.72 / 0.64 / 0.71 / 0.65 / 0.80 / 0.79 / 0.67 |
| 32 | 0.1138 / 0.0640 / 0.0877 / 0.0785 / 0.0633 / 0.1164 / 0.0690 / 0.0912 / 0.1100 / 0.0693 | 0.56 / 0.17 / 0.40 / 0.36 / 0.21 / 0.57 / 0.27 / 0.45 / 0.53 / 0.29 |
| 40 | 0.0589 / 0.0584 / 0.0621 / 0.0572 / 0.0525 / 0.0658 / 0.0631 / 0.0623 / 0.0604 / 0.0514 | 0.00 / 0.00 / 0.04 / 0.01 / 0.00 / 0.03 / 0.03 / 0.03 / 0.00 / 0.00 |
| 48 | 0.0586 / 0.0578 / 0.0594 / 0.0581 / 0.0529 / 0.0647 / 0.0625 / 0.0656 / 0.0599 / 0.0528 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0656 / 0.0638 / 0.0670 / 0.0698 / 0.0653 / 0.0686 / 0.0684 / 0.0746 / 0.0706 / 0.0710 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1008 / 0.0980 / 0.0980 / 0.1021 / 0.0980 / 0.0980 / 0.0978 / 0.1027 / 0.1011 / 0.0986 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.07454 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003825 | 0.9333 | 0 |
| Exp(5 s) (record) | 1.5 | 0.08944 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0001358 | 0.9313 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1044 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006897 | 0.93 | 0 |
| Exp(5 s) (record) | 2 | 0.1193 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0003255 | 0.9294 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1491 | 10/10 (1.00) [0.72, 1.00] | True | 1.8 | 12 | 1.559 | 0.9118 | 0 |
| Exp(5 s) (record) | 3 | 0.1789 | 5/10 (0.50) [0.24, 0.76] | False | 70.1 | 225 | 53.93 | 0.523 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.059629 | 2.5 | 2.5 | True | False | [1, 2.5] | 1.5, 2 |

**Edge hi = 2.5 x lambda_miss = 0.1491 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.05963; largest all-stable multiple irrespective of contiguity: 2.5). In multiples of the REAL lambda_miss (0.05964 sessions/s) the same multiple is 0.1491 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.55 x and through 0.5 at nan x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.06559 | hi = 1.25 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.986 to 1.005 | 127.1 | 0 | 0.006522 | TTTTTITTIT | RRRRRRRRRR |
| 1.15 | 0.06857 | hi = 1.25 (high); hi = 1.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.993 to 1.009 | 139 | 0 | 0.006982 | TTTTTITTIT | RRRRRRRRRR |
| 1.25 | 0.07454 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.003 to 1.015 | 159.6 | 0 | 0.008116 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.0805 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.010 to 1.020 | 183.9 | 0 | 0.009191 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.08944 | hi = 1.75 (high); hi = 2.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.019 to 1.033 | 218.5 | 0 | 0.01106 | TTTTTITTTT | RRRRRRRRRR |
| 1.65 | 0.09839 | hi = 2 (high); hi = 3 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.028 to 1.040 | 254.2 | 0 | 0.01303 | TTTTIITTTT | RRRRRRRRRR |
| 2 | 0.1193 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.041 to 1.056 | 345.2 | 0 | 0.01804 | TTTTTITTTT | RRRRRRRRRR |
| 2.35 | 0.1401 | hi = 3 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.057 to 1.068 | 444.3 | 0 | 21.57 | TTTTTITTTT | RRRRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006536 | 0.932 |
| 1.1 (extra) | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006522 | 0.932 |
| 1.1 (extra) | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006522 | 0.932 |
| 1.1 (extra) | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006578 | 0.932 |
| 1.1 (extra) | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 2 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 30.07 | 0.7152 |
| 1.1 (extra) | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 168.4 | 0.06379 |
| 1.15 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.007504 | 0.9319 |
| 1.15 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006982 | 0.9319 |
| 1.15 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.006982 | 0.9319 |
| 1.15 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.00703 | 0.9319 |
| 1.15 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 2 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 37.07 | 0.7036 |
| 1.15 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 186.8 | 0.06365 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008123 | 0.9315 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008118 | 0.9315 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.00811 | 0.9315 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008089 | 0.9315 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 5/10 (0.50) [0.24, 0.76] | 2 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 56.07 | 0.6346 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 227.6 | 0.06566 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01831 | 0.9311 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009181 | 0.9311 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009156 | 0.9311 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.9921 | 0.9166 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 3 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 87.58 | 0.5361 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 266.6 | 0.06544 |
| 1.5 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05686 | 0.9307 |
| 1.5 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01232 | 0.9307 |
| 1.5 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01115 | 0.9307 |
| 1.5 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 1.562 | 0.9228 |
| 1.5 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 137.1 | 0.4216 |
| 1.5 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 320.2 | 0.07409 |
| 1.65 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.07339 | 0.9309 |
| 1.65 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01914 | 0.9309 |
| 1.65 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01305 | 0.9309 |
| 1.65 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 10.69 | 0.8861 |
| 1.65 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 198.6 | 0.4116 |
| 1.65 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 370.4 | 0.07373 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1729 | 0.9313 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.02077 | 0.9313 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01806 | 0.9313 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 60.68 | 0.7995 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 328.8 | 0.4156 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 505.6 | 0.07227 |
| 2.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 17.39 | 0.9329 |
| 2.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1933 | 0.9327 |
| 2.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.07225 | 0.9321 |
| 2.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 172.7 | 0.757 |
| 2.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 473.3 | 0.4055 |
| 2.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 645.2 | 0.0718 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | TTTTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2.5): test points 1.5, 2; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.059692 | 0.0014435 | 0.058704 | 9340.4 | 0.99998 | 0.06052 | 1 |

Reference values (the two real Llama-3.1-8B numbers from this cell's E0a 3-seed combine, not outputs of the simulator): measured all-miss uncached rate 9,353 tok/s, measured lambda_miss 0.05964 sessions/s. This block: token rate 9,340.4 tok/s = 0.9987 x the Llama rate; lambda_miss 0.05969 sessions/s = 1.0009 x the Llama value. V1 factor f = 1.204 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 9,340.44 tok/s, -0.13% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1722 / 0.93 |
| 20 | 0.2080 / 0.93 |
| 24 | 0.2056 / 0.89 |
| 28 | 0.1513 / 0.74 |
| 32 | 0.0986 / 0.47 |
| 40 | 0.0630 / 0.08 |
| 48 | 0.0597 / 0.01 |
| 96 | 0.0684 / 0.00 |
| 300 | 0.0992 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 20 | 0.208 | 20 | 0.4769 | 0 | 20 | 0.2096 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 20 |
| peak mu (turns-based sessions/s) | 0.208 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.485 |
| hit fraction at the peak n | 0.9297 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 20 / 0.2096 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.58 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.69 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 37.6 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.8, s1: 30.9, s2: 30.7, s3: 31.7, s4: 29.6, s5: 33.3, s6: 31.9, s7: 32.2, s8: 33.9, s9: 30.3 |
| mu(300) / peak mu | 0.4769 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0526; -0.1284 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1699 / 0.1728 / 0.1720 / 0.1681 / 0.1746 / 0.1735 / 0.1725 / 0.1731 / 0.1723 / 0.1735 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2056 / 0.2099 / 0.2063 / 0.2069 / 0.2122 / 0.2009 / 0.2060 / 0.2112 / 0.2107 / 0.2103 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.93 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2159 / 0.2157 / 0.1634 / 0.2018 / 0.2246 / 0.1624 / 0.1924 / 0.2310 / 0.2298 / 0.2194 | 0.91 / 0.90 / 0.83 / 0.89 / 0.91 / 0.83 / 0.87 / 0.91 / 0.92 / 0.90 |
| 28 | 0.2061 / 0.1890 / 0.1047 / 0.1435 / 0.1268 / 0.1270 / 0.1234 / 0.1784 / 0.1721 / 0.1417 | 0.85 / 0.83 / 0.63 / 0.74 / 0.68 / 0.71 / 0.67 / 0.80 / 0.79 / 0.73 |
| 32 | 0.1239 / 0.0828 / 0.0903 / 0.0970 / 0.0653 / 0.1192 / 0.0936 / 0.1029 / 0.1384 / 0.0729 | 0.62 / 0.38 / 0.44 / 0.48 / 0.23 / 0.58 / 0.49 / 0.51 / 0.65 / 0.33 |
| 40 | 0.0634 / 0.0600 / 0.0683 / 0.0643 / 0.0569 / 0.0663 / 0.0672 / 0.0647 / 0.0615 / 0.0571 | 0.09 / 0.04 / 0.14 / 0.12 / 0.08 / 0.06 / 0.10 / 0.09 / 0.03 / 0.09 |
| 48 | 0.0589 / 0.0598 / 0.0599 / 0.0587 / 0.0527 / 0.0659 / 0.0621 / 0.0653 / 0.0621 / 0.0520 | 0.01 / 0.03 / 0.01 / 0.02 / 0.00 / 0.02 / 0.00 / 0.00 / 0.03 / 0.01 |
| 96 | 0.0657 / 0.0636 / 0.0670 / 0.0696 / 0.0652 / 0.0683 / 0.0685 / 0.0743 / 0.0708 / 0.0710 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1005 / 0.0976 / 0.0980 / 0.1017 / 0.0982 / 0.0976 / 0.0974 / 0.1022 / 0.1005 / 0.0983 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.07461 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003023 | 0.9334 | 0 |
| Exp(5 s) (record) | 1.5 | 0.08954 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 1.443e-05 | 0.9313 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1045 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -6.915e-06 | 0.9299 | 0 |
| Exp(5 s) (record) | 2 | 0.1194 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0003905 | 0.9294 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1492 | 8/10 (0.80) [0.49, 0.94] | False | 8.5 | 52 | 7.08 | 0.8217 | 0 |
| Exp(5 s) (record) | 3 | 0.1791 | 4/10 (0.40) [0.17, 0.69] | False | 93.6 | 239 | 71.52 | 0.4323 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.059692 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1194 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.05969; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.05964 sessions/s) the same multiple is 0.1193 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.12 x and through 0.5 at 2.88 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.06566 | hi = 1.25 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.985 to 1.003 | 135.8 | 0 | 0.006419 | TITTTITTIT | RRRRRRRRRR |
| 1.15 | 0.06865 | hi = 1.25 (high); hi = 1.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.991 to 1.007 | 148.8 | 0 | 0.007048 | TTTTTITTIT | RRRRRRRRRR |
| 1.25 | 0.07461 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.012 | 166.5 | 0 | 0.008138 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.08058 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.008 to 1.018 | 193.1 | 0 | 0.009274 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.08954 | hi = 1.75 (high); hi = 2.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.019 to 1.030 | 225.1 | 0 | 0.01084 | TTTTIITTTT | RRRRRRRRRR |
| 1.65 | 0.09849 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.025 to 1.038 | 263.8 | 0 | 0.01253 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1194 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.038 to 1.054 | 354.5 | 0 | 0.01784 | TTTTTITTTT | RRRRRRRRRR |
| 2.35 | 0.1403 | hi = 3 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.065 | 454.2 | 0 | 22.41 | TTTTTITTTT | RRRRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.006436 | 0.9319 |
| 1.1 (extra) | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.006389 | 0.9319 |
| 1.1 (extra) | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.006419 | 0.9319 |
| 1.1 (extra) | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.006419 | 0.9319 |
| 1.1 (extra) | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 1 | PASS | 5/10 (0.50) [0.24, 0.76] | FAIL | 10.68 | 0.8205 |
| 1.1 (extra) | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 142.8 | 0.1518 |
| 1.15 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.007331 | 0.9318 |
| 1.15 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.007058 | 0.9318 |
| 1.15 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.007048 | 0.9318 |
| 1.15 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.00708 | 0.9318 |
| 1.15 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 20.21 | 0.7469 |
| 1.15 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 158.5 | 0.1888 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008127 | 0.9315 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008129 | 0.9315 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.00812 | 0.9315 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008115 | 0.9315 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 34.93 | 0.7351 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 203.1 | 0.1644 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01855 | 0.9311 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009214 | 0.9311 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009264 | 0.9311 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009226 | 0.9311 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 5/10 (0.50) [0.24, 0.76] | 1 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 49.44 | 0.7107 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 237.4 | 0.1556 |
| 1.5 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.05457 | 0.9307 |
| 1.5 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01228 | 0.9307 |
| 1.5 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01083 | 0.9307 |
| 1.5 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.4288 | 0.9277 |
| 1.5 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 2 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 80.37 | 0.5491 |
| 1.5 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 300.7 | 0.1268 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.07792 | 0.931 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01634 | 0.931 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01261 | 0.931 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 3.946 | 0.9016 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 146.1 | 0.4966 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 353.8 | 0.14 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1738 | 0.9313 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0208 | 0.9313 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01766 | 0.9313 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 30.19 | 0.8656 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 280.6 | 0.4946 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 477 | 0.1627 |
| 2.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 21.34 | 0.9329 |
| 2.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2077 | 0.9327 |
| 2.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06847 | 0.9315 |
| 2.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 122 | 0.8017 |
| 2.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 418.6 | 0.5131 |
| 2.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 617 | 0.1643 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | TITTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.
