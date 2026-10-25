Spec: `configs/r8_native_predict.yaml` (sha256 `b808dd76a5cbd7891f13aeef731ce6cb740ffb49800f478ab65eeb6305fe5c0d`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r8_native_separate/r7_lambda_miss/20261025-145505 | 0336c91d2 | False | 0..2 (3) | 2026-10-25T14:55:05 | 1.2 | True |
| curves | results/r8_native_separate/r7_curves/20261025-145507 | 0336c91d2 | False | 0..2 (3) | 2026-10-25T14:55:07 | 1.9 | True |
| edge | results/r8_native_separate/r7_edge/20261025-145510 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:55:10 | 4.1 | True |
| pairs | results/r8_native_separate/r7_pairs/20261025-145515 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:55:15 | 5.7 | True |
| burst_sizes | results/r8_native_separate/r7_burst_sizes/20261025-145523 | 0336c91d2 | False | 0..9 (10) | 2026-10-25T14:55:23 | 5.2 | True |

Total recorded stage wall time: 18 s (0.3 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py curves --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py edge --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py pairs --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py burst_sizes --spec configs/r8_native_predict.yaml --workers 6 --out-root results/r8_native_separate --set engine.batching=separate_prefill_priority --set r7.burst_sizes.multiples=[2.65, 4.35]
```
