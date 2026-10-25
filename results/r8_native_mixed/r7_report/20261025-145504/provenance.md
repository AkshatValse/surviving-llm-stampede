Spec: `configs/r8_native_predict.yaml` (sha256 `b808dd76a5cbd7891f13aeef731ce6cb740ffb49800f478ab65eeb6305fe5c0d`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r8_native_mixed/r7_lambda_miss/20261025-145439 | 0336c91d2 | False | 0..2 (3) | 2026-10-25T14:54:39 | 1.3 | True |
| curves | results/r8_native_mixed/r7_curves/20261025-145441 | 0336c91d2 | False | 0..2 (3) | 2026-10-25T14:54:41 | 2.1 | True |
| edge | results/r8_native_mixed/r7_edge/20261025-145445 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:54:44 | 4.5 | True |
| pairs | results/r8_native_mixed/r7_pairs/20261025-145450 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:54:50 | 5.9 | True |
| burst_sizes | results/r8_native_mixed/r7_burst_sizes/20261025-145458 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:54:58 | 5 | True |

Total recorded stage wall time: 19 s (0.3 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_mixed
experiments/r7_robustness_run.py curves --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_mixed
experiments/r7_robustness_run.py edge --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_mixed
experiments/r7_robustness_run.py pairs --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_mixed
experiments/r7_robustness_run.py burst_sizes --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_mixed --set r7.burst_sizes.multiples=[2.85, 4.65]
```
