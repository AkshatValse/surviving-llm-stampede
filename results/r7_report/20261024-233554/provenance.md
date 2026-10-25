Spec: `configs/r7_robustness.yaml` (sha256 `75113280c3f41704c4f3523e8e509bfe3436293d3f02df5621f6bcd2cb16cfc0`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_lambda_miss/20261024-232728 | 1140104d1 | False | 0..2 (3) | 2026-10-24T23:27:28 | 13.1 | True |
| curves | results/r7_curves/20261024-232744 | 1140104d1 | False | 0..2 (3) | 2026-10-24T23:27:44 | 15.9 | True |
| edge | results/r7_edge/20261024-232802 | 1140104d1 | False | 0..9 (10) | 2026-10-24T23:28:02 | 22.6 | True |
| pairs | results/r7_pairs/20261024-232827 | 1140104d1 | False | 0..9 (10) | 2026-10-24T23:28:27 | 51.4 | True |
| burst_sizes | results/r7_burst_sizes/20261024-232921 | 1140104d1 | False | 0..9 (10) | 2026-10-24T23:29:21 | 12.8 | True |
| horizon | results/r7_horizon/20261024-232936 | 1140104d1 | False | 0..9 (10) | 2026-10-24T23:29:36 | 12.4 | True |
| lowlam | results/r7_lowlam/20261024-232951 | 1140104d1 | False | 100..119 (20) | 2026-10-24T23:29:51 | 3.5 | True |

Total recorded stage wall time: 132 s (2.2 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py curves --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py pairs --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py burst_sizes --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py horizon --spec configs/r7_robustness.yaml --workers 6
experiments/r7_robustness_run.py lowlam --spec configs/r7_robustness.yaml --workers 6
```
