Spec: `configs/r7_traces_sim.yaml` (sha256 `b1619c0618b6331fa94bc23708d4be8b2279f8c073400430488e0f92d92b0c4b`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim/r7_lambda_miss/20261025-011208 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:07 | 5.7 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim/r7_edge/20261025-011223 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:23 | 10.1 | True |
| pairs | results/r7_traces_sim/r7_pairs/20261025-011234 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:34 | 21.1 | True |

Total recorded stage wall time: 44 s (0.7 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
```
