Spec: `configs/r9_vllm_predict.yaml` (sha256 `98aa0f228e1df1e49d3910035c62ef41b3b457eca875ab148379cbea437d55ca`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v0_mixed/r7_lambda_miss/20261030-122443 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:24:43 | 1.2 | True |
| curves | results/r9_vllm_v0_mixed/r7_curves/20261030-122445 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:45 | 2.2 | True |
| edge | results/r9_vllm_v0_mixed/r7_edge/20261030-122448 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:48 | 1.9 | True |

Total recorded stage wall time: 5 s (0.1 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
```
