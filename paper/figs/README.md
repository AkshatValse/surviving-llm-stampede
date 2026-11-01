# Paper figures

Seven vector PDFs, one script each under `figures/paper/` (F7 reuses F1's drawing function). Every script reads only git-tracked, unmodified files
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

Checked for every figure: `pdfinfo` page size (below), `pdftoppm` render, and the paper build placing all seven at their
native widths.

File names are not the paper's figure numbers. In the 2026-10-26 build: Fig. 1 = F1, Fig. 2 = F2, Fig. 3 = F3, Fig. 4 = F7 (native E2),
Fig. 5 = F6 (policy grid), Fig. 6 = F5 (robustness), Fig. 7 = F4 (mechanisms).

| file | width x height (in) | column |
|---|---|---|
| `fig1_e2_timeseries.pdf` | 7.00 x 3.90 | double |
| `fig2_thrashing_curve.pdf` | 7.00 x 4.00 | double |
| `fig3_from_empty_stability.pdf` | 3.40 x 4.75 | single |
| `fig4_mechanisms.pdf` | 7.00 x 3.47 | double |
| `fig5_robustness.pdf` | 3.40 x 4.09 | single |
| `fig6_policy_grid.pdf` | 3.40 x 3.32 | single |
| `fig7_e2_native_timeseries.pdf` | 7.00 x 3.60 | double |

Changed on 2026-10-26 (native pool and vLLM results): F2 gains the B4n curve and the native cap; F3 gains a native-pool panel
(native E0b against B2n); F6 gains a vLLM row; F7 is new. F1 was refactored into a function (`draw`) that F7 calls; F1's PDF is
byte-identical to the previous build. F4 and F5 are unchanged.

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
Added 2026-10-26 to the right column: light gray dotted squares = B4n, the round-8 simulator curve at the real pool (955,757 tokens,
mixed batching, mean of seeds 0-2 of `mu` (sessions-based) and `hit_rate`). B4n is NOT a blind prediction: the native curve had been
measured and summarised in `notes/STATE.md` (6793fb7, 14:47) before its spec (29728e3, 14:49) was written; the figure labels it so.
Green dashed line in the right column: the registered native cap n_cap = 64 (`configs/agentload_prereg_2026-10-25_native.yaml`).
The right column's legend moved into the empty lower-left of the hit panel.

**Sources.**
- `results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv` (label `sglang-fcfs-r1`, n = 16, 20, 24, 32, 48, 96, 300)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv` (label `sglang-fcfs-r1-native`, n = 24, 48, 64, 80, 96, 128, 300)
- `results/r6_validate_stagec/20261024-025222/supp_fine_curve_mixed.csv`
- `results/r6_predict_report/20261024-034707/b4_runs.csv` (mixed, kv_k 900, set `registered(seed 0)`)
- `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json` (`lambda_miss_turns_based`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json` (`lambda_miss_turns_based`)
- `results/r8_native_report/20261025-150146/mixed_curves_curve_runs.csv` (B4n, seeds 0-2)

**Reading of B4n (right column).** Seed-mean peak at n = 72 (0.532 sessions/s; the real grid has no 72), hit 0.92 at 80, 0.79 at 88,
0.42 at 96, 0 from 112: it lies on the real curve's cliff between 80 and 96 more closely than B4 (900k), but see the blindness note.

## F3 `fig3_from_empty_stability.pdf` (script `figures/paper/fig3_from_empty_stability.py`)

**Shows.** From-empty stability of the open system, 300k pool. Real engine (E0b): one 3000 s run per rate at 1.25, 1.5, 1.75, 2.0, 2.5, 3.0 x
lambda_ref; black dot at 1 = stable, cross at 0 = unstable (final queue < 50 and no upward trend; the same operational rule as B2).
Gray: blind prediction B2 of the simulator (mixed batching), fraction of runs stable at each lambda of the B2 grid, 3 registered
seeds (dashed) and the 20-seed supplement (dotted). x axis in sessions/s with a second axis in multiples of lambda_ref (0.0715; the
simulator's own lambda_miss is 0.0722, so the top axis is exact for the real runs and approximate for the simulator).
Reading: real stable at 2.0 x (0.143), unstable at 2.5 x (0.179) and 3.0 x (0.215); simulator all-stable edge 0.14 (3 seeds) / 0.15 (20 seeds).
That is the top panel. Bottom panel (added 2026-10-26): native pool (955,757 tokens). Real native E0b, one 3000 s run at 1.5, 2.5, 3.5,
4.5, 5.5, 6.5 x the native lambda_ref (0.07180, native E0a turns-based; each run's rate from its `meta.json`, checked against
multiple x lambda_ref); gray = blind prediction B2n (`notes/PREDICTIONS_native.md`, pushed 15:08 on 2026-10-25 before any native
E0b run had finished), stable fraction of 10 seeds at each multiple of the mode's own lambda_miss, mixed (primary, dashed) and separate
(secondary, dotted); refinement rows (none ran) excluded. Reading: real stable through 5.5 x (0.395), unstable at 6.5 x (0.467);
B2n mixed 10/10 stable through 6.5 x (0.468), 7/10 at 7.0, 2/10 at 7.5; separate 10/10 through 6.0 x, 8/10 at 6.5, 3/10 at 7.0, 0/10 at 7.5.

**Sources.**
- `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_analysis_stable/20261024-150720/stable_runs.csv`
- the six `meta.json` (key `resolved_rate_sessions_per_s`) under `results/nova/e0b_1708475x_pulled_20261024-150639/results/agentload_e0_cap/`:
  `20261023-144337`, `20261023-144407`, `20261023-145616`, `20261023-151551`, `20261023-151551-1`, `20261023-151556`
- `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json`
- `results/r6_predict_report/20261024-034707/b2_table.csv`, `results/r6_predict_report/20261024-034707/b2_supp20_table.csv`
- `results/nova/e0b_native_1710093x_pulled_20261025-173038/results/agentload_analysis_stable/20261025-172934/stable_runs.csv`
- the six `meta.json` under `results/nova/e0b_native_1710093x_pulled_20261025-173038/results/agentload_e0_cap/`:
  `20261025-144656` (1.5), `20261025-153959` (2.5), `20261025-163302` (3.5), `20261025-144709` (4.5), `20261025-154012` (5.5), `20261025-163315` (6.5)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json`
- `results/r8_native_report/20261025-150146/mixed_edge_edge_verdicts.csv`, `results/r8_native_report/20261025-150146/separate_edge_edge_verdicts.csv`

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
Row 5 (added 2026-10-26, below a dashed line): vLLM 0.32.0, FCFS (default), prefix caching on, 300k-token pool (18,750 blocks of 16),
BURST arm only, exploratory registration `configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml` (window and multiples inherited
from the SGLang cell, not measured); the column multiples are of vLLM's own lambda_ref (0.06566 sessions/s, vLLM E0a turns-based), so
the rates are 0.0886 and 0.1083 sessions/s, not the SGLang rows' 0.0966 and 0.1180. Reading: hit 0.00 in all six; trapped / indeterminate
/ trapped at both multiples (seed 1 indeterminate by the slope test both times).

**Sources.**
- `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_analysis_burst2/20261025-144012/trap_v2_runs.csv` (arm `burst` rows, label `sglang-fcfs-r1`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144230/trap_v2_runs.csv` (`sglang-fcfs-r0`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144233/trap_v2_runs.csv` (`sglang-lpm-r1`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_burst2/20261025-144236/trap_v2_runs.csv` (`sglang-lpm-r0`)

- `results/nova/e2_native_vllm_burst_pulled_20261026-101256/results/agentload_analysis_burst2/20261026-100701/trap_v2_runs.csv` (`vllm-fcfs`)

(The directory name `r7_native_grid_vllm_pulled_...` is the pull's name; the grid runs themselves used the 300k-token cap, not the native pool.)

## F7 `fig7_e2_native_timeseries.pdf` (script `figures/paper/fig7_e2_native_timeseries.py`)

**Shows.** The real pre-registered paired kill test with the native KV pool (native E2, SGLang 0.5.22, Qwen2.5-7B-Instruct, A100 80GB,
pool 955,757 tokens sized by SGLang; registration `configs/agentload_prereg_2026-10-25_native.yaml`) at 2.5 x the native lambda_ref
(0.1795 sessions/s, left) and 4.0 x (0.2872, right). Same layout, metric and computation as F1 (the script calls
`fig1_e2_timeseries.draw`): top, the registered hit metric in 100 s windows (`analysis.windows.window_table`, the verdict's overrides);
bottom, the verdict's backlog series (sessions in the system, 50 s bins), log scale to 3000; one thin line per seed and arm;
CAPPED gate n_cap = 64; dashed line = the burst at 1200 s; gray band = the registered evaluation window (5700 s to 8700 s).
The burst label is shifted right (700 s instead of 90 s) so that it does not cover the falling BURST lines.

**Sources.**
- `results/nova/e2_native_vllm_burst_pulled_20261026-101256/results/agentload_analysis_burst2/20261026-100653/trap_v2_runs.csv`
- `results/nova/e2_native_vllm_burst_pulled_20261026-101256/results/agentload_analysis_burst2/20261026-100653/backlog_trace.csv`
- `configs/agentload_analysis.yaml` (with the verdict's overrides, as for F1)
- for each of the 18 run dirs `results/nova/e2_native_vllm_burst_pulled_20261026-101256/results/agentload_e2_burst/<ts>/`, the files `meta.json`,
  `config_effective.yaml`, `requests.csv`, `sessions.csv` (72 files):

| x lambda_ref | seed | BURST `<ts>` | NOBURST `<ts>` | CAPPED `<ts>` |
|---|---|---|---|---|
| 2.5 | 0 | 20261025-174410 | 20261025-174405 | 20261025-174402 |
| 2.5 | 1 | 20261025-182014 | 20261025-182234 | 20261025-201333 |
| 2.5 | 2 | 20261025-201414 | 20261025-202740 | 20261025-204942 |
| 4.0 | 0 | 20261025-174409 | 20261025-174445 | 20261025-175810 |
| 4.0 | 1 | 20261025-201340 | 20261025-201333-1 | 20261025-201337 |
| 4.0 | 2 | 20261025-205154 | 20261025-224309 | 20261025-224304 |

**What to read off it.** Every BURST run keeps hitting for a few hundred seconds after the burst (0.63-0.76 in the 100 s window that
contains it, against 0.21-0.33 at 300k), then is at hit 0 from 300-600 s after the burst to the end; its backlog barely dips after the
burst (155-231 sessions 100-200 s after it) and then grows without a plateau to 658-1379 over the last 300 s (`paper/derived/burst_hit_onset.csv`,
`paper/derived/e2_native_burst_backlog.csv`). NOBURST and CAPPED sit at hit ~0.93 and backlog 16-34; the CAPPED gate's queue empties
512-937 s after the burst (`paper/derived/e2_native_capped_drain.csv`).

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
9. **F1 hit series are computed, not read.** No committed time series of the hit fraction exists, so F1 recomputes it from `requests.csv` with the repo's `window_table` (checked against the registered per-run `hit_eval`, see above); only the backlog is read from a committed series. The same holds for F7; `paper/derived/burst_hit_onset.csv` recomputes the evaluation-window hit of every BURST run of E2, native E2 and vLLM from `requests.csv` and matches the verdict's `hit_eval` (0.0 in all 18).
10. **B4n is not blind (F2).** `notes/PREDICTIONS_native.md` says its predictions were made "before any real native-pool result was seen"; that is true of the agent that ran them, but the native Stage C curve and lambda_miss had been analysed on the cluster (14:42) and written into `notes/STATE.md` (6793fb7, 14:47) before the round-8 spec was committed (29728e3, 14:49), and the spec's grid adds 72, 80 and 88 near the real cliff. B2n and B3n (F3) are blind in time.
11. **Native pool size (F7).** Two of the 18 native E2 servers (jobs 17102173 and 17102184) report `max_total_num_tokens=955756`, one token below the 955,757 of the other 16 and of native Stage C, E0a and E0b; the figures and the paper use 955,757.
12. **Native E2 run times.** The LOG entry gives the native E2 runs as "2026-10-25 17:43 - 2026-10-26 ~10:00"; the runs' own `meta.json` start and end times span 17:44:02 to 01:08:10 (the six vLLM runs end at 03:20:42; ~10:00 is when the archive was pulled). The paper uses the `meta.json` times.
13. **"About 2.75 x wider" (LOG).** The native E0b LOG entry calls the native window "about 2.75 x wider than at the 300k cap (in units of lambda_miss)". 2.75 is the ratio of the upper edges (5.5 / 2.0); the window widths are 4.5 and 1.0 lambda_miss. The paper states both.
