# Paper figures

Six vector PDFs, one script each under `figures/paper/`. Every script reads only git-tracked, unmodified files
(`figures/paper/_style.py::src` refuses anything else) and writes `paper/figs/<name>.pdf`. Rebuild all:

```
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" bash figures/paper/build_all.sh
```

(`PYTHONPATH="src;."` is set by the script; only F1 imports repo code, `analysis.*`.) `FIG_SOURCES=1` makes a script print the files it read. PDFs carry no timestamp, so a rebuild is byte-identical.
Style (`_style.py`): matplotlib 3.9.2, STIXGeneral serif, 8-9 pt at final size, TrueType fonts embedded, no raster content;
single column 3.4 in, double column 7.0 in. One Okabe-Ito palette. The same colour means the same thing everywhere:
BURST vermillion, NOBURST blue, CAPPED green (a static session cap is also green); FCFS near-black, LPM purple, PEEK orange,
Continuum pins sky blue, CONCUR dark yellow; real engine = black and filled, simulator = gray, open, dashed;
per-run states (F6): trapped vermillion, recovered green, draining sky blue, indeterminate gray.

Checked for every figure: `pdfinfo` page size (below), `pdftoppm` render, and a `pdflatex` test page placing all six at their
native widths.

| file | width x height (in) | column |
|---|---|---|
| `fig1_e2_timeseries.pdf` | 7.00 x 3.90 | double |
| `fig2_thrashing_curve.pdf` | 7.00 x 4.00 | double |
| `fig3_from_empty_stability.pdf` | 3.40 x 2.45 | single |
| `fig4_mechanisms.pdf` | 7.00 x 3.47 | double |
| `fig5_robustness.pdf` | 3.40 x 4.09 | single |
| `fig6_policy_grid.pdf` | 3.40 x 2.90 | single |

---

## F1 `fig1_e2_timeseries.pdf` (script `figures/paper/fig1_e2_timeseries.py`)

**Shows.** The real pre-registered paired kill test (E2, SGLang 0.5.22, Qwen2.5-7B-Instruct, A100 80GB, 300k-token KV cap) at
1.35 x lambda_ref (0.0966 sessions/s, left) and 1.65 x (0.1180, right). Top: prefix-cache hit fraction against time. Bottom: backlog
against time (log scale). Per arm (BURST, NOBURST, CAPPED) one thin line per seed (0, 1, 2). Dashed vertical line: the burst
(200 sessions in 60 s at t = 1200 s). Gray band: the registered evaluation window (t_b + 4500 s = 5700 s to the end, 8700 s).

**How computed.** Hit fraction = the registered hit metric (`windows.hit_metric` = `frac_turns_cached_gt50`: fraction of ok turns with
cached_tokens / prompt_tokens > 0.5, first turns included, attributed by completion time), in 100 s windows from
`analysis.windows.window_table` (engine-metrics file not loaded; client-side columns only). Check: the turn-weighted mean of these
windows over [5700, 8700] reproduces `hit_eval` of `trap_v2_runs.csv` for all 18 runs (equal to 4 decimals). Backlog = the verdict's
`backlog_trace.csv` (sessions in the system = arrived minus ended, 50 s bins, `analysis.throughput.backlog_trace`; recomputing
one run from `sessions.csv` matches it to 6e-14). This is the verdict's "backlog" series, not the engine's waiting queue and not the
"outstanding" series of the registered RECOVERED test; in the good state it is 5-15 because sessions asleep in tool time count.
Run to (lambda multiple, seed, arm) comes from `trap_v2_runs.csv`.

**Sources.**
- `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/trap_v2_runs.csv`
- `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/backlog_trace.csv`
- `configs/agentload_analysis.yaml` (with the verdict's overrides `burst.trap_min_s=3000`, `burst.hit_eval_from_s=4500`, `trap_v2.eval_from_s=4500`)
- for each of the 18 run dirs `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/<ts>/`, the files `meta.json`,
  `config_effective.yaml`, `requests.csv`, `sessions.csv` (72 files):

| x lambda_ref | seed | BURST `<ts>` | NOBURST `<ts>` | CAPPED `<ts>` |
|---|---|---|---|---|
| 1.35 | 0 | 20261024-153951 | 20261024-155125 | 20261024-155130 |
| 1.35 | 1 | 20261024-161333 | 20261024-161834 | 20261024-182448 |
| 1.35 | 2 | 20261024-211100 | 20261024-211253 | 20261024-213121 |
| 1.65 | 0 | 20261024-155120 | 20261024-160218 | 20261024-161207 |
| 1.65 | 1 | 20261024-184132 | 20261024-184259 | 20261024-184758 |
| 1.65 | 2 | 20261025-000043 | 20261025-000053 | 20261025-000819 |

**What to read off it.** Every BURST run is at hit 0.00 from the 100 s window starting at 1300 s (0.21-0.33 in the window that contains the burst) and in every
later window to the end; its backlog is about 200 right after the burst, falls to 135-172 sessions 300-1300 s after it as short burst sessions finish, then rises
(206-369 over the last 300 s): still growing at the end in five runs, flat near 206 in the sixth (1.35 x, seed 1; `paper/derived/e2_burst_backlog.csv`). Every NOBURST and CAPPED run is at hit ~0.93 and
backlog ~10 in the evaluation window. Registered per-run states:
BURST trapped / indeterminate / trapped at 1.35 x (seed 1 is stuck at hit 0 but its slope is under the threshold) and trapped x3 at 1.65 x.
Not in the notes, visible here: while the gate drains the 200-session burst, the CAPPED arm's hit fraction dips transiently
(minimum 100 s window between 1300 s and 5000 s: 0.76, 0.63, 0.77, 0.48 in seed 0 and 2 at 1.35 x and seed 0 and 2 at 1.65 x; 0.88 and 0.90 in seed 1; the NOBURST minimum is 0.82-0.89).

## F2 `fig2_thrashing_curve.pdf` (script `figures/paper/fig2_thrashing_curve.py`)

**Shows.** The closed-population thrashing curve of the real engine, mu(n) in completed sessions/s (top; filled circles; small plus signs =
the lower-variance turns-based estimate) and hit fraction (bottom), against the simulator. Left: 300k-token pool (Stage C), simulator =
round-6 calibrated simulator, mixed batching, 17-point grid, mean of the 3 registered seeds +- 1 s.e. (VALIDATION.md section 5, fine grid).
Right: native pool (955,757 tokens as sized by SGLang), simulator = blind prediction B4 at the nearest simulated pool (900k tokens,
registered seed 0, frozen before any native run; the real pool is 6% larger, so the simulated cliff sits slightly to the left).
Horizontal dotted line: lambda_miss (E0a all-miss capacity, turns-based: 0.0715 sessions/s at 300k, 0.0718 native). Green dashed line:
n_cap = 20, the registered E2 cap. Log n axis; same y-limits in both columns so the shift of the cliff (hit-fraction crossing
~32 at 300k, between 80 and 96 native) and the unchanged lambda_miss are visible.

**Sources.**
- `results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv` (label `sglang-fcfs-r1`, n = 16, 20, 24, 32, 48, 96, 300)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv` (label `sglang-fcfs-r1-native`, n = 24, 48, 64, 80, 96, 128, 300)
- `results/r6_validate_stagec/20261024-025222/supp_fine_curve_mixed.csv`
- `results/r6_predict_report/20261024-034707/b4_runs.csv` (mixed, kv_k 900, set `registered(seed 0)`)
- `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json` (`lambda_miss_turns_based`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json` (`lambda_miss_turns_based`)

## F3 `fig3_from_empty_stability.pdf` (script `figures/paper/fig3_from_empty_stability.py`)

**Shows.** From-empty stability of the open system, 300k pool. Real engine (E0b): one 3000 s run per rate at 1.25, 1.5, 1.75, 2.0, 2.5, 3.0 x
lambda_ref; black dot at 1 = stable, cross at 0 = unstable (final queue < 50 and no upward trend; the same operational rule as B2).
Gray: blind prediction B2 of the simulator (mixed batching), fraction of runs stable at each lambda of the B2 grid, 3 registered
seeds (dashed) and the 20-seed supplement (dotted). x axis in sessions/s with a second axis in multiples of lambda_ref (0.0715; the
simulator's own lambda_miss is 0.0722, so the top axis is exact for the real runs and approximate for the simulator).
Reading: real stable at 2.0 x (0.143), unstable at 2.5 x (0.179) and 3.0 x (0.215); simulator all-stable edge 0.14 (3 seeds) / 0.15 (20 seeds).

**Sources.**
- `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/stable_runs.csv`
- the six `meta.json` (key `resolved_rate_sessions_per_s`) under `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_e0_cap/`:
  `20261023-144337`, `20261023-144407`, `20261023-145616`, `20261023-151551`, `20261023-151551-1`, `20261023-151556`
- `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json`
- `results/r6_predict_report/20261024-034707/b2_table.csv`, `results/r6_predict_report/20261024-034707/b2_supp20_table.csv`

## F4 `fig4_mechanisms.pdf` (script `figures/paper/fig4_mechanisms.py`)

**Shows.** Mechanism comparison in the simulator: closed-population service rate mu(300) / lambda_miss, in units of the audit's lambda_miss
(0.047419 sessions/s, the round-1 calibration used by the rounds-3/4 simulator and the baselines audit, not the 0.0722 of the calibrated
round-6 simulator). Mean over seeds 0-9 with the 95% Student-t interval. Rows: FCFS; LPM; PEEK (historical FCFS queued-session-protection
ablations `peek_rank` and `peek`, hollow, against the audited released-scheduler ordering + eviction-score projection
`peek_singleton_audit`, filled); Continuum-style TTL pins tau = 5, 10, 20 s (hollow = old idle-only release rule `ttl*`, filled = the released
preview's waiting-allocation rule `ttl*cw`); the CONCUR-equation session-gate **surrogate** `concur_cap`, and below it all 18 cells (6 variants
x seeds 0-2, small dots) of the same surrogate when finished sessions' KV counts as usage (`free_kv_on_session_end=false`: 12 of 18 stall at
~0.93, 6 reach ~3.0); static session caps c = 20, 28, 36 (green).
Static caps: the audit does not recompute them (code path unchanged), so they are mu(c) / lambda_miss from the round-4 closed FCFS-LRU curve,
seeds 2000-2002 (3 seeds, t interval, per-seed dots shown), because a cap c on a large population holds the engine at c sessions. c = 20 is the
registered E2 cap and the curve's peak region (mu* is at n = 22), c = 28 = N_lb, c = 36 = floor(1.3 N_lb).

**Sources.**
- `results/prefix_meta_baselines_audit_summary/20261025-001850/curve_baselines_audit_s10.csv`
- `results/prefix_meta_baselines_audit_summary/20261025-001850/curve_baselines_audit_deadkv.csv`
- `results/prefix_meta_baselines_audit_summary/20261025-001850/meta.json` (lambda_miss)
- `results/prefix_meta_r4_curve/20261021-050856/curve_runs.csv` (policy `fcfs_lru`, k = 1.0, n = 20, 28, 36)

## F5 `fig5_robustness.pdf` (script `figures/paper/fig5_robustness.py`)

**Shows.** Robustness of the paired kill test in the simulator across tool-time laws (calibrated simulator, mixed batching, record workload with
only the tool-time law replaced). Gray bar = measured from-empty window [1, hi] in multiples of the law's own lambda_miss (hi = largest all-stable
multiple, 10 seeds, B2 rule). The two markers are the test points at lo + (hi - lo)/3 and lo + 2(hi - lo)/3; filled dot = PASS, crossed open circle
= FAIL under the declared rule (BURST trapped, NOBURST good, CAPPED recovered each in >= 7 of 10 seeds). Number above a marker = BURST trapped /
seeds; gray note = a non-BURST criterion that failed. Rows: real engine E2 for reference (3 seeds, need 2 seeds in which all three arms succeed, the registered rule; window = last all-stable multiple of
E0b); synthetic laws Exp(1 s), Exp(2 s), Exp(5 s) (record), lognormal CV 2, bimodal 1 s / 20 s; real-trace laws TraceLab per turn, TraceLab idle gap,
mini-SWE-agent tool time, and mini-SWE-agent full workload (declared protocol); last row (gray label) = the labelled post-hoc rerun of the full
workload with the protocol adjusted (converged lambda_miss, edge horizon = paired horizon, 20000 s after the burst).
Reading: all 10 synthetic points PASS; of the 8 declared trace points 6 PASS; the two FAILs are TraceLab per turn at 1.40 x (BURST trapped 6/10, all 10 are stuck at
hit 0, 4 are indeterminate by the slope rule) and the full mini-SWE workload at 2.35 x (CAPPED 0/10: the cap does not drain the 200-session burst within the
evaluation window; NOBURST 8/10 still passes). The Exp(5 s) control row of `ROBUSTNESS_r7_traces` is identical to the record row and not repeated.

**Sources.**
- `results/r7_report/20261024-233554/pairs_summary.json` (synthetic laws; hi and test points from the same file)
- `results/r7_traces_sim/r7_report/20261025-012451/pairs_summary.json` (trace laws)
- `results/r7_traces_sim_adj/r7_report/20261025-012453/pairs_summary.json` (post-hoc adjusted rerun)
- `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/kill_verdict_v2.json` (real E2 points)
- `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/lambda_cap_bracket.json` (real window edge)

## F6 `fig6_policy_grid.pdf` (script `figures/paper/fig6_policy_grid.py`)

**Shows.** The real exploratory policy grid, BURST arm only: rows = FCFS refresh on (the registered, decisive E2 BURST arm), FCFS refresh off, LPM
refresh on, LPM refresh off; columns = 1.35 and 1.65 x lambda_ref x seeds 0, 1, 2. Square colour = per-run state from the trap analysis over the
evaluation window (trapped / indeterminate / draining / recovered); upper number = hit fraction, lower number = mean backlog (sessions in system)
over the window. Rows 2-4 are exploratory registrations derived from the E2 one (same lambda points, seeds, windows; no paired NOBURST/CAPPED arms).
Reading: FCFS has the same state in all 6 runs with refresh on and off. LPM changes some individual runs between refresh on and off (seed 0 at 1.35 x is recovered
with refresh on, trapped with it off), but 5 of its 6 runs at 1.35 x recover or drain (on: 3 of 3, off: 2 of 3); at 1.65 x refresh on has 0 of 3 recovered
(two trapped, one indeterminate) and refresh off 1 of 3.

**Sources.**
- `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/trap_v2_runs.csv` (arm `burst` rows, label `sglang-fcfs-r1`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144230/trap_v2_runs.csv` (`sglang-fcfs-r0`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144233/trap_v2_runs.csv` (`sglang-lpm-r1`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144236/trap_v2_runs.csv` (`sglang-lpm-r0`)

(The directory name `r7_native_grid_vllm_pulled_...` is the pull's name; the grid runs themselves used the 300k-token cap, not the native pool.)

---

## Data notes (disagreements and limits met while building the figures; no data was changed)

1. **LOG hit values vs the verdict CSVs (F6).** `notes/LOG.md` (policy-grid entry) rounds three hit fractions one hundredth above the CSV: LPM refresh on, 1.35 x, seed 2 "0.52"
   (CSV `hit_eval` 0.5146); LPM refresh on, 1.65 x, seed 2 "0.45" (0.4446); LPM refresh off, 1.65 x, seed 2 "0.83" (0.8250, 0.824996 unrounded). The figure prints the CSV values (0.51, 0.44, 0.82); the states agree with the LOG.
   LPM refresh on, 1.35 x, seed 0 backlog: LOG "48", CSV 47.49.
2. **"Backlog" is not one thing (F1).** The LOG calls 200-332 "waiting sessions". The verdict's `backlog_trace.csv` and `backlog_eval_mean` count every session in the system
   (including those in tool-time sleep: 5-15 in the healthy state); the registered RECOVERED test uses `outstanding` (requests in flight + gate queue), a separate series (`outstanding_eval_mean`, e.g. 226 vs 232 for the first trapped run). F1 plots the
   first and says so on the axis. If the paper wants the waiting queue, `metrics.csv` (SGLang `num_queue_reqs`) is in the pull but F1 does not read it.
3. **Pool size in the native comparison (F2).** The simulator has no 955,757-token pool; B4 was run at 600k and 900k. The right panel overlays 900k (registered seed 0, the frozen prediction; the 5-seed mean of the supplement
   is within 0.01 sessions/s at n = 64 and 96 but is not drawn). The predicted cliff therefore sits slightly left of the real one (crossing ~80 vs ~93), partly the 6% pool difference.
4. **Estimator spread (F2).** At 300k, mu(48) is 0.049 (sessions/s) vs 0.063 (turns-based) and mu(96) 0.061 vs 0.073: single runs, heavy-tailed session work (see the E0a entry). Both are drawn; the simulator line is the
   sessions-based mean. VALIDATION.md's level test is NO in both modes; the figure shows the shape agreement, not a level pass.
5. **lambda_miss differs between the simulators (F3, F4).** Simulator B2 is built around lambda_miss = 0.0722; the real lambda_ref is 0.0715 (F3's top axis uses the real value). The baselines audit (F4) is in units of 0.047419
   (older calibration); its ratios are comparable within the figure only, not with F2/F3 absolute rates.
6. **Static caps (F4).** Taken from the round-4 curve (3 seeds, 95% t interval half-width 0.17-0.35), not from the audit tables. The round-3 rows `lb_cap` (cap 28) and `cap_1p3` (cap 36) give 2.21 and 1.12
   (`results/prefix_meta_mech/20261021-025902/mech_capacity_by_population.csv`, seeds 0-2), inside the round-4 intervals (2.39 +- 0.35, 1.08 +- 0.17); the round-4 values were used so that all three caps share one source and seeds.
   The old-rule Continuum tau = 20 s row (1.72) is the idle-GPU artefact (GPU busy 0.34), as the audit says.
7. **Secondary mini-SWE-agent workload (F5).** The declared row's lambda_miss is not converged (0.0120 vs 0.0141 sessions/s with a long window) and its hi = 3.0 came from a 3000 s edge horizon that is too short for it; the
   x positions of that row and of the post-hoc row are therefore in different units (declared vs converged lambda_miss). Shown as declared, with the post-hoc row labelled.
8. **Real-engine reference row (F5).** E2 has 3 seeds and the 2-of-3 rule; the simulator rows have 10 seeds and 7-of-10. The E2 window edge drawn (2.0 x) is E0b's largest all-stable multiple (2.5 x was unstable, one run each).
9. **F1 hit series are computed, not read.** No committed time series of the hit fraction exists, so F1 recomputes it from `requests.csv` with the repo's `window_table` (checked against the registered per-run `hit_eval`, see above); only the backlog is read from a committed series.
