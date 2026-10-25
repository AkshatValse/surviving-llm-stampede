Spec: `configs/r7_traces_sim.yaml` (sha256 `b1619c0618b6331fa94bc23708d4be8b2279f8c073400430488e0f92d92b0c4b`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim/r7_lambda_miss/20261025-011208 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:07 | 5.7 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim/r7_edge/20261025-011223 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:23 | 10.1 | True |
| pairs | results/r7_traces_sim_ext/r7_pairs/20261025-011657 | a83bdde4f | False | 100..119 (20) | 2026-10-25T01:16:57 | 28.8 | True |

Total recorded stage wall time: 52 s (0.9 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_ext --workers 6 --set r7.pairs.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]
```
