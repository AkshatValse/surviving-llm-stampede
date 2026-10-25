Spec: `configs/r7_traces_sim.yaml` (sha256 `b1619c0618b6331fa94bc23708d4be8b2279f8c073400430488e0f92d92b0c4b`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim_lmcheck/r7_lambda_miss/20261025-012241 | 85f739837 | False | 0..2 (3) | 2026-10-25T01:22:41 | 3.3 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim_adj/r7_edge/20261025-012331 | 85f739837 | False | 0..9 (10) | 2026-10-25T01:23:31 | 2.6 | True |
| pairs | results/r7_traces_sim_adj/r7_pairs/20261025-012341 | 85f739837 | False | 0..9 (10) | 2026-10-25T01:23:41 | 4.7 | True |

Total recorded stage wall time: 18 s (0.3 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_lmcheck --workers 6 --only exp5 mini_full --set r7.lambda_miss.warmup_s=18000.0 --set r7.lambda_miss.horizon_s=54000.0
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full --set r7.edge.horizon_s=8700.0
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full --set r7.pairs.after_s=20000.0 --set r7.classify.eval_window_rel_to_burst_s=[17500.0, 20000.0]
```
