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
