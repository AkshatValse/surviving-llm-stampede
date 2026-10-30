Spec: `configs/r9_vllm_predict.yaml` (sha256 `98aa0f228e1df1e49d3910035c62ef41b3b457eca875ab148379cbea437d55ca`; the first commit of the spec, before any run, had sha256 recorded in the notes); KV pool 300,000 tokens; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes (the stages run one after the other).

**V0 / mixed** (`engine.batching` = `mixed`, out-root `results/r9_vllm_v0_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v0_mixed/r7_lambda_miss/20261030-122443 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:24:43 | 1.2 | True | - |
| curves | results/r9_vllm_v0_mixed/r7_curves/20261030-122445 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:45 | 2.2 | True | - |
| edge | results/r9_vllm_v0_mixed/r7_edge/20261030-122448 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:48 | 1.9 | True | - |
| pairs_all | results/r9_vllm_v0_mixed/r7_pairs_all/20261030-122451 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:51 | 29.1 | True | - |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
```

**V0 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r9_vllm_v0_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v0_separate/r7_lambda_miss/20261030-122524 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:25:23 | 1.3 | True | engine.batching=separate_prefill_priority |
| curves | results/r9_vllm_v0_separate/r7_curves/20261030-122526 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:26 | 2.2 | True | engine.batching=separate_prefill_priority |
| edge | results/r9_vllm_v0_separate/r7_edge/20261030-122529 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:29 | 2 | True | engine.batching=separate_prefill_priority |
| pairs_all | results/r9_vllm_v0_separate/r7_pairs_all/20261030-122532 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:32 | 28.8 | True | engine.batching=separate_prefill_priority |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
```

**V1 / mixed** (`engine.batching` = `mixed`, out-root `results/r9_vllm_v1_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v1_mixed/r7_lambda_miss/20261030-122604 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:26:04 | 1.2 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| curves | results/r9_vllm_v1_mixed/r7_curves/20261030-122606 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:06 | 2.2 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| edge | results/r9_vllm_v1_mixed/r7_edge/20261030-122609 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:09 | 1.9 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| pairs_all | results/r9_vllm_v1_mixed/r7_pairs_all/20261030-122612 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:12 | 28.9 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
```

**V1 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r9_vllm_v1_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v1_separate/r7_lambda_miss/20261030-122644 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:26:44 | 1.2 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| curves | results/r9_vllm_v1_separate/r7_curves/20261030-122647 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:47 | 2.1 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| edge | results/r9_vllm_v1_separate/r7_edge/20261030-122650 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:50 | 1.8 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| pairs_all | results/r9_vllm_v1_separate/r7_pairs_all/20261030-122653 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:53 | 28 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |

Recorded stage wall time: 33 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
```

Total recorded stage wall time over the four trees: 136 s (2.3 min).
