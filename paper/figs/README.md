# Paper figures

Ten vector PDFs, one script each under `figures/paper/` (F7 reuses F1's drawing function; one script, `fig8_10_theory.py`, writes F8-F10
with the drawing functions of `analysis/theory/paper/figs.py`). Every F1-F7 script reads only git-tracked, unmodified files
(`figures/paper/_style.py::src` refuses anything else) and writes `paper/figs/<name>.pdf`; F8-F10 read the frozen theory JSONs and the
measured files listed in their section below, without that check. Rebuild all:

```
PY=python bash figures/paper/build_all.sh
```

(Point `PY` at the interpreter of an environment built from `env/requirements-local.txt`. `PYTHONPATH="src;."` is set by the script; the `;` separator is the Windows one, so on Linux or macOS change it to `src:.`; only F1 imports repo code, `analysis.*`.) `FIG_SOURCES=1` makes a script print the files it read. PDFs carry no timestamp, so a rebuild is byte-identical.
Style (`_style.py`): matplotlib 3.9.2, STIXGeneral serif, 8-9 pt at final size, TrueType fonts embedded, no raster content;
single column 3.4 in, double column 7.0 in. One Okabe-Ito palette. The same colour means the same thing everywhere:
BURST vermillion, NOBURST blue, CAPPED green (a static session cap is also green); FCFS near-black, LPM purple, PEEK orange,
Continuum pins sky blue, CONCUR dark yellow; real engine = black and filled, simulator = gray, open, dashed;
per-run states (F6): trapped vermillion, recovered green, draining sky blue, indeterminate gray.
F8-F10 keep the style of `analysis/theory/paper/figs.py` (matplotlib default DejaVu Sans, 6-8 pt, TrueType fonts embedded, 7.2 in wide,
their own palette); restyling them to `_style.py` is optional and would change no plotted value.

Checked for every figure: `pdfinfo` page size (below), `pdftoppm` render, and the paper build placing all seven at their
native widths (F1-F7; F8-F10 were checked with `pdfinfo` and `pdftoppm` on 2026-10-31, and the paper build that places them is the
lead's).

File names are not the paper's figure numbers. In the 2026-10-26 build: Fig. 1 = F1, Fig. 2 = F2, Fig. 3 = F3, Fig. 4 = F7 (native E2),
Fig. 5 = F6 (policy grid), Fig. 6 = F5 (robustness), Fig. 7 = F4 (mechanisms). In the 2026-10-31 build planned by the integration:
Fig. 1 = F1 (`fig:e2`), 2 = F8 (`fig:fpmu`), 3 = F2 (`fig:curve`), 4 = F3 (`fig:edge`), 5 = F7 (`fig:e2native`), 6 = F6 (`fig:grid`),
7 = F9 (`fig:fpscale`), 8 = F5 (`fig:robust`), 9 = F4 (`fig:mech`), 10 = F10 (`fig:fixed`); check against the built PDF.
In the fill-3 build (fix round 3, 2026-10-31): Fig. 1 = F1 (`fig:e2`, Sec. 1), 2 = F2 (`fig:curve`, Sec. 5), 3 = `fig_rescue.pdf`
(`fig:rescue`, Sec. 5; script `figures/paper/fig_rescue.py`), 4 = F8 (`fig:fpmu`, Sec. 6), 5 = F10 (`fig:fixed`, Appendix F),
6 = F3 (`fig:edge`), 7 = F7 (`fig:e2native`) and 8 = F6 (`fig:grid`) in Appendix G, 9 = F9 (`fig:fpscale`, Appendix H),
10 = F5 (`fig:robust`) and 11 = F4 (`fig:mech`) in Appendix I.

| file | width x height (in) | column |
|---|---|---|
| `fig1_e2_timeseries.pdf` | 7.00 x 3.90 | double |
| `fig2_thrashing_curve.pdf` | 7.00 x 4.55 | double |
| `fig3_from_empty_stability.pdf` | 3.40 x 4.30 | single |
| `fig4_mechanisms.pdf` | 7.00 x 3.47 | double |
| `fig5_robustness.pdf` | 3.40 x 4.09 | single |
| `fig6_policy_grid.pdf` | 3.40 x 3.32 | single |
| `fig7_e2_native_timeseries.pdf` | 7.00 x 3.60 | double |
| `fig8_theory_curves.pdf` | 7.00 x 2.45 | double |
| `fig9_theory_scaling.pdf` | 7.20 x 2.50 | double |
| `fig10_theory_fixed_points.pdf` | 7.20 x 2.45 | double |

F8-F10 are 7.20 in wide, so `\includegraphics[width=\textwidth]` scales them by 7.0 / 7.2 = 0.97 on a 7.0 in text block.

Changed on 2026-10-26 (native pool and vLLM results): F2 gains the B4n curve and the native cap; F3 gains a native-pool panel
(native E0b against B2n); F6 gains a vLLM row; F7 is new. F1 was refactored into a function (`draw`) that F7 calls; F1's PDF is
byte-identical to the previous build. F4 and F5 are unchanged.

Changed on 2026-10-30 (vLLM's own curve and edge, inputs at `582c2a6`): F2 gains a third column, vLLM 0.32.0 at the 300k-token pool
(vLLM Stage C against the blind prediction B4v), and F3 a third panel (vLLM E0b against the blind prediction B2v). The SGLang data in
both figures are unchanged; only their layout changed (details under F2 and F3). F3 is shorter than before (4.30 in against 4.75 in)
although it has three panels: with the default `\topfraction` of 0.7, a single-column top float may be at most 0.7 x 9.5 in = 6.65 in
including its caption, and a 4.75 in figure with a ten-line caption is pushed to the end of the paper (checked in a scratch build).

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

**Shows.** The closed-population thrashing curve of the real engine in three cells, against the simulator: mu(n) in completed
sessions/s (top; black filled circles, one run per n; black plus signs = the lower-variance turns-based estimate, completed turns/s
divided by E[T]) and the hit fraction (bottom; fraction of turns with cached/prompt > 0.5), against the closed population n
(log axis, the same in all columns; same y-limits along each row). Closed population of n sessions, synchronized start, window
[900, 2700) s, FCFS, Qwen2.5-7B-Instruct, one A100 80GB PCIe.
- Left, SGLang 0.5.22, 300k-token pool (Stage C): simulator = round-6 calibrated simulator, mixed batching, 17-point grid, mean of the
  3 registered seeds +- 1 s.e. (gray band; VALIDATION.md section 5, fine grid). This simulator was calibrated with this curve in view,
  so the left column is a validation, not a blind prediction.
- Middle, SGLang 0.5.22, native pool (955,757 tokens as sized by SGLang): gray dashed diamonds = blind prediction B4 at the nearest
  simulated pool (900k tokens, registered seed 0, frozen before any native run; the real pool is 6% larger, so the simulated cliff
  sits slightly to the left); light gray dotted squares = B4n, the round-8 simulator curve at the real pool (955,757 tokens, mixed
  batching, mean of seeds 0-2 of `mu` (sessions-based) and `hit_rate`). B4n is NOT a blind prediction: the native curve had been
  measured and summarised in `notes/STATE.md` (6793fb7, 14:47) before its spec (29728e3, 14:49) was written; the legend says so.
- Right (added 2026-10-30), vLLM 0.32.0, 300k-token pool (18,750 blocks of 16), prefix caching on, FCFS: vLLM's own Stage C, jobs
  17162959 (n = 16, 20, 24), 17162960 (28, 32, 40), 17162961 (48, 96, 300), label `vllm-fcfs`, one run per n. Gray dashed triangles
  with a gray band = blind prediction B4v (`notes/PREDICTIONS_vllm.md`, frozen at tag `r9-vllm-predictions-frozen` = `cc01dbf`,
  pushed 12:32 CDT on 2026-10-30 before any vLLM Stage C or E0b result was read), variant V1 (the SGLang-calibrated engine with its
  token-proportional costs scaled by 1.0882 so that its all-miss token rate equals vLLM's measured 10,349 tok/s; its sessions/s are
  therefore in vLLM's units), mixed batching (the primary mode), mean of seeds 0-9 of `mu` (sessions-based) and `hit_rate`, band
  +- 1 s.e. Neither B4v variant models vLLM's block-level lazy eviction, its missing waiting-prefix refresh or its scheduler.

Horizontal dotted line: lambda_miss of the cell (E0a all-miss capacity, turns-based: 0.0715 sessions/s at 300k, 0.0718 native,
0.0657 vLLM), labelled at the right end. Green dashed line: the cell's registered session cap n_cap (20 at 300k,
`configs/agentload_prereg_2026-10-24.yaml`; 64 native, `configs/agentload_prereg_2026-10-25_native.yaml`; 20 vLLM, read from
`measured.n_cap` of `configs/agentload_prereg_2026-10-30_vllm.yaml`). One legend for all columns, below the panels; each simulator
entry names its column.

Layout changes of 2026-10-30, applied to all columns: third column added (figure height 4.00 -> 4.55 in); column titles name the
engine and the pool ("Stage C" dropped from the title); the turns-based plus signs are drawn larger (6.5 pt over 3.4 pt circles)
and on top, because the review (referee R12) found them hidden under the circles; the cap labels are rotated along the cap line
in the hit panels and read "n_cap = 20 / 64 / 20" (the "(E2 cap)" and "(native cap)" tags are gone, SF18); the lambda_miss labels
moved to the right end below the line, where no curve passes in any column; the x label is "closed population n".

**Sources.**
- `results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv` (label `sglang-fcfs-r1`, n = 16, 20, 24, 32, 48, 96, 300)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv` (label `sglang-fcfs-r1-native`, n = 24, 48, 64, 80, 96, 128, 300)
- `results/nova/stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv` (label `vllm-fcfs`, n = 16, 20, 24, 28, 32, 40, 48, 96, 300; added in `276c5f0`)
- `results/r6_validate_stagec/20261024-025222/supp_fine_curve_mixed.csv`
- `results/r6_predict_report/20261024-034707/b4_runs.csv` (mixed, kv_k 900, set `registered(seed 0)`)
- `results/r8_native_report/20261025-150146/mixed_curves_curve_runs.csv` (B4n, seeds 0-2)
- `results/r9_vllm_report/20261030-122723/v1_mixed_curves_curve_runs.csv` (B4v, V1 mixed, workload `exp5`, seeds 0-9; added in `cc01dbf`)
- `results/nova/e0a_1707263x_pulled_20261023-142037/analysis_local_combined/20261023-142416/calibration.json` (`lambda_miss_turns_based`)
- `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_miss/20261025-054653/calibration.json` (`lambda_miss_turns_based`)
- `prereg/inputs/2026-10-25-vllm/calibration.json` (`lambda_miss_turns_based` = 0.06566287289032151, the vLLM registration's input; `65b65e2`),
  asserted byte-identical to `results/nova/e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json` (`b273241`)
- `configs/agentload_prereg_2026-10-30_vllm.yaml` (`measured.n_cap` = 20; `measured.lambda_ref` asserted equal to the calibration; `5a6fbcd`)

**Reading of B4n (middle column).** Seed-mean peak at n = 72 (0.532 sessions/s; the real grid has no 72), hit 0.92 at 80, 0.79 at 88,
0.42 at 96, 0 from 112: it lies on the real curve's cliff between 80 and 96 more closely than B4 (900k), but see the blindness note.

**Reading of the vLLM column (right).** Real, sessions/s (turns-based) / hit fraction:

| n | 16 | 20 | 24 | 28 | 32 | 40 | 48 | 96 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| mu sessions/s | 0.175 | **0.219** | 0.218 | 0.119 | 0.043 | 0.041 | 0.044 | 0.057 | 0.105 |
| mu turns-based | 0.174 | 0.211 | 0.210 | 0.123 | 0.054 | 0.056 | 0.059 | 0.069 | 0.105 |
| hit fraction | 0.932 | 0.926 | 0.879 | 0.658 | 0.083 | 0.007 | 0.000 | 0.000 | 0.000 |
| B4v (V1 mixed) mu | 0.177 | 0.213 | 0.215 | 0.163 | 0.106 | 0.067 | 0.066 | 0.073 | 0.102 |
| B4v (V1 mixed) hit | 0.932 | 0.930 | 0.888 | 0.744 | 0.459 | 0.026 | 0.000 | 0.000 | 0.000 |

Real peak 0.2194 sessions/s at n = 20 (n = 24 is 0.5% lower, n = 16 20% lower), 3.34 x lambda_miss (turns-based 0.2108, 3.21 x);
the hit fraction crosses 0.5 at n = 29.1 (linear between 28 and 32); mu falls 80% from n = 24 to n = 32, and at n = 32-48 the
turns-based mu is 0.83-0.90 x lambda_miss. B4v (V1 mixed) peaks at n = 24 (0.2153 sessions/s), crosses hit 0.5 at n = 31.4 and has
hit 0.74 at 28 and 0.46 at 32 where the real engine has 0.66 and 0.08: the peak level and the cap (20) match, the real cliff is
steeper and earlier. The three B4v configurations not drawn (V0 mixed, V0 separate, V1 separate) differ from V1 mixed by at most
0.018 sessions/s in seed-mean mu (V0 separate at n = 32) and 0.079 in hit fraction (n = 40); across all four, the hit fraction at
n = 32 is 0.46-0.53 and the 0.5 crossing 31.4-32.6 (`notes/PREDICTIONS_vllm.md`; linear interpolation of the seed means gives
31.42-32.55).

## F3 `fig3_from_empty_stability.pdf` (script `figures/paper/fig3_from_empty_stability.py`)

**Shows.** From-empty stability of the open system in three cells. Real engine: one 3000 s run per rate from an empty cache and
queue, black dot at 1 = stable, cross at 0 = unstable (final queue < 50 and no upward trend; the same operational rule as the
simulator's). Gray: blind simulator predictions, the fraction of simulated runs stable at each rate. Bottom axes: arrival rate in
sessions/s (one shared label under the last panel); top axes: multiples of that cell's lambda_ref. Every real run is plotted at its
nominal rate (`resolved_rate_sessions_per_s` of its `meta.json`, asserted equal to multiple x lambda_ref); every real run used
arrival seed 0 (see data note 14).
- Top, SGLang 0.5.22, 300k pool: E0b at 1.25, 1.5, 1.75, 2.0, 2.5, 3.0 x lambda_ref (0.0715). Gray: blind prediction B2 (mixed
  batching), stable fraction at each lambda of the B2 grid, 3 registered seeds (dashed) and the 20-seed supplement (dotted); the
  simulator's own lambda_miss is 0.0722, so the top axis is exact for the real runs and approximate for the simulator.
  Reading: real stable at 2.0 x (0.143), unstable at 2.5 x (0.179) and 3.0 x (0.215); simulator all-stable edge 0.14 (3 seeds) / 0.15 (20 seeds).
- Middle, SGLang 0.5.22, native pool (955,757 tokens): native E0b at 1.5, 2.5, 3.5, 4.5, 5.5, 6.5 x the native lambda_ref (0.07180,
  native E0a turns-based); gray = blind prediction B2n (`notes/PREDICTIONS_native.md`, pushed 15:08 on 2026-10-25 before any native
  E0b run had finished), stable fraction of 10 seeds at each multiple of the mode's own lambda_miss, mixed (primary, dashed) and
  separate (secondary, dotted); refinement rows (none ran) excluded. Reading: real stable through 5.5 x (0.395), unstable at 6.5 x
  (0.467); B2n mixed 10/10 stable through 6.5 x (0.468), 7/10 at 7.0, 2/10 at 7.5; separate 10/10 through 6.0 x, 8/10 at 6.5, 3/10 at 7.0, 0/10 at 7.5.
- Bottom (added 2026-10-30), vLLM 0.32.0, 300k pool (18,750 blocks of 16): vLLM E0b, jobs 17162962 (1.25, 1.5, 1.75 x) and 17162963
  (2.0, 2.5, 3.0 x) of vLLM's own lambda_ref (0.06566, vLLM E0a turns-based), label `vllm-fcfs`, the six-run bracket
  `agentload_analysis_stable/20261030-172042`. Same x range as the top panel (0.06-0.232 sessions/s), so the two 300k cells can be
  compared directly. Gray dashed = blind prediction B2v (`notes/PREDICTIONS_vllm.md`, tag `r9-vllm-predictions-frozen` = `cc01dbf`,
  pushed before any vLLM E0b run), variant V1 (token costs scaled to vLLM's all-miss token rate, own lambda_miss 0.06623, so its
  rates are in vLLM's units to within 0.9%), mixed batching (primary), stable fraction of 10 seeds at 1.25, 1.5, 1.75, 2.0, 2.5,
  3.0 x its own lambda_miss (0.0828 ... 0.1987 sessions/s); no refinement rows exist.
  Reading: real stable at 1.25, 1.5, 1.75 and 2.0 x (0.0821, 0.0985, 0.1149, 0.1313 sessions/s; final queue 0, trend rise at most
  0.02), unstable at 2.5 x (0.1642; final queue 81.6, fitted rise +94 over the last 1500 s) and 3.0 x (0.1970; 247.1, +175): the
  edge lies between 2.0 and 2.5 x, as at 300k with SGLang. B2v (V1 mixed): 10/10 stable through 2.0 x, 7/10 at 2.5 x, 3/10 at
  3.0 x, hence the predicted edge 2.0 x. The three configurations not drawn: all 10/10 through 2.0 x; 6/10 (V0 mixed), 8/10
  (V0 separate), 7/10 (V1 separate) at 2.5 x; 1/10, 1/10, 3/10 at 3.0 x.

Layout changes of 2026-10-30: third panel added; the real-run legend moved to the top of the figure (it applies to all panels);
one y label for the figure; one x label (under the last panel); y ticks 0, 0.5, 1 (minor ticks at 0.25, 0.75); each top-axis label
names the engine and the pool. The figure is 4.30 in tall, so that figure and a caption of about ten lines still fit the 0.7
`\topfraction` of a single-column top float (a scratch build placed it on the page of its section with a ten-line caption; at
4.4 in it went to the end of the paper).

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
- `results/nova/e0b_vllm_1716296x_pulled_20261030-172810/results/agentload_analysis_stable/20261030-172042/stable_runs.csv` (added in `582c2a6`)
- the six `meta.json` under `results/nova/e0b_vllm_1716296x_pulled_20261030-172810/results/agentload_e0_cap/`:
  `20261030-131849` (1.25), `20261030-141150` (1.5), `20261030-150452` (1.75), `20261030-143825` (2.0), `20261030-153127` (2.5), `20261030-162428` (3.0)
- `prereg/inputs/2026-10-25-vllm/calibration.json` (asserted byte-identical to the vLLM E0a analysis
  `results/nova/e0a_vllm_17100940_pulled_20261025-180814/results/agentload_analysis_miss/20261025-175648/calibration.json`)
- `results/r9_vllm_report/20261030-122723/v1_mixed_edge_edge_verdicts.csv` (B2v, V1 mixed, seeds 0-9; added in `cc01dbf`)

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

## F8-F10 `fig8_theory_curves.pdf`, `fig9_theory_scaling.pdf`, `fig10_theory_fixed_points.pdf` (script `figures/paper/fig8_10_theory.py`)

**Script.** `figures/paper/fig8_10_theory.py` calls `fig_mu_validation`, `fig_fixed_points` and `fig_scaling` of
`analysis/theory/paper/figs.py` (commit 5271ff6, written after the freeze tag `r13-theory-pred`) and saves their figures here, with
no creation date (a rebuild is byte-identical; checked twice on 2026-10-31) and without rewriting the data CSVs. The same functions
write `figures/theory/paper_{mu_validation,scaling,fixed_points}.{pdf,png}` when `python -m analysis.theory.paper.figs` is run; the
three PDFs here render identically to those (`pdftoppm` at 100 dpi, byte-equal PNGs).

**Label edit of 2026-10-31.** In `analysis/theory/paper/figs.py` only labels changed, no plotted value: the internal names "(T8)"
and "(Proposition F)" left the panel titles, "result not read" left the legends of the frozen predictions, "window" became "peak
ratio" (the paper's window is the interval of rates, bounded on the A100 at 300k by the from-empty edge), and the cost model is
written $\mathcal{C}$ as in the paper. The script was rerun after the edit: `results/theory/paper/{mu_validation,scaling,fixed_points}.csv`
are byte-identical to their committed versions (SHA-256 checked before and after).

**Data.** `results/theory/paper/{mu_validation,scaling,fixed_points}.csv`, computed from the frozen theory at tag `r13-theory-pred`
(`results/theory/merged/<cell>.json`; no frozen number changed after the tag) and, for the measured points, the files that
`analysis/theory/fluid_rigorous/cells.py` names: the Stage C curves (SC, NAT, VSC of `paper/NUMBERS.md`) and the E0a calibrations
(E0A, NATM, VE0A).

**Shows.**
- F8 (`fig:fpmu`, Section 6; Section 4 before fill 2): the predicted closed curve mu(n), fluid and F1, against the measured Stage C points (sessions/s and
  turns-based) for SGLang 300k, SGLang with the native pool and vLLM 300k; dotted line at the predicted all-miss onset n_b,
  dash-dotted at lambda_ref. n = 300 is not drawn (a synchronized-start transient). No measured mu(n) point is an input of the curve.
  Fix-up 1 of fill 2 (2026-10-31): a fourth panel shows the frozen H200 300k prediction (`results/theory/merged/h200_300k.json`)
  against the measured H200 curve (`results/nova/h200_stageC_extra_1716961x_pulled_20261031-040933/results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.csv`),
  with n <= 32 shaded (seen by the first author before the freeze) and n = 36, 44, 52 ringed (blind in time); F8 now uses the serif
  style of `_style.py` and F2's logarithmic n axis (ticks 16-96, cut at 140), and is 7.00 x 2.45 in. F9 (a) also plots the measured
  H200 peak ratio (0.367218 and 0.386109 sessions/s over lambda_ref 0.193877). F10 is byte-identical.
- F9 (`fig:fpscale`, Appendix H since fix round 1 of fill 3; Section 7 before): (a) the fluid peak ratio in model units, mu* / mu_b,
  against s zbar, with the A100's measured ratios (turns-based and sessions/s; measured in units of lambda_ref = 0.07153 from E0a, which
  lies 0.4% below the model's mu_b = 0.07184), the frozen H200 prediction (s = 2.742) and the measured H200 peak ratio (turns-based and
  sessions/s, over its lambda_ref 0.193877; seen by the first author before the freeze); (b) the peak ratio against the pool M: the model
  with A100 costs (solid) and, since fill 3, with the frozen H200 costs (green, dashed; s = 2.742); the A100 300k and native cells,
  measured (open squares, in sample); since fill 3, the A100 pool-sweep peak ratios at 150k and 600k, measured (filled squares, blind in
  time; `results/nova/pool_sweep_1716886x_pulled_20261031-112342/derived/pool_sweep_scored.json`), and their frozen predictions (purple
  diamonds); since fill 3, the H200 frozen predictions at 300k (`r13-theory-pred`) and 600k (pred2, `results/theory/pred2/h200_600k.json`)
  (green diamonds) and the measured H200 peak ratios at 300k (open triangle, seen before the freeze) and 600k (filled triangle, blind in
  time; `results/nova/h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/.../20261031-092435/mu_curve.json`), all turns-based. The
  diamonds are frozen predictions; no outcome of a pending test is plotted. The diamonds are at the fluid model-unit ratio; the F1
  values the paper quotes (`tab:windowlaw`, `tab:frozen`) differ from them by -8.6% (150k) to +1.2% (H200, 600k), as the caption says
  (`paper/NUMBERS.md`, row "-8.6% (1.8720 / 2.0473 - 1), +1.2% (3.1956 / 3.1565 - 1)").
- F10 (`fig:fixed`, Appendix F): (a) the open-system phase line dn/dt = lambda - mu(n) of the predicted 300k curve at 1.65 lambda_ref,
  with n_1 = 10.4, n_2 = 31.8, n_b = 32.7 and the trap (n grows at lambda - mu_b); (b) the closed-system feedback map Phi_n(h) at
  n = 33.5 > n_b for exponential 5 s tool times (one stationary state, all-miss) and for 0.5 Exp(1 s) + 0.5 Exp(9 s) of the same mean
  (three: all-miss and good stable, one unstable); (c) the two closed curves, with the fold of the mixture above n_b (band
  32.698-34.177 in `fixed_points.csv`). Panel (c) labels the band "bistable band", which is the closed system of Proposition 7, the fold identity (Proposition 5 before fix-up 2 of fill 2,
  which moved it to Appendix F; a proof sketch in the paper), not the open system.

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
14. **Every E0b run used arrival seed 0 (F3).** The plan draws the session count from the same seed-0 stream at every rate, so in all 18 E0b runs (three cells) the count lies about 2.1 standard deviations above lambda T (z = 2.06-2.11) and the realized rate is 6-13% above the nominal one. Counts in [0, 3000) s from each run's `plan.csv` (= `sessions.csv` rows, all `base`): SGLang 300k 302, 359, 416, 472, 585, 697 (8.3-12.6% above lambda T; realized 1.41, 1.67, 1.94, 2.20, 2.73, 3.25 x lambda_ref); native 361, 587, 811, 1034, 1257, 1478 (5.6-11.7%; realized 1.68, 2.73, 3.77, 4.80, 5.84, 6.86 x); vLLM 279, 331, 383, 435, 539, 642 (8.6-13.3%; realized 1.42, 1.68, 1.94, 2.21, 2.74, 3.26 x). F3 plots the nominal rates. For vLLM the unstable 2.5 x run received 0.180 sessions/s, below the measured peak (0.219 sessions-based, 0.211 turns-based), so its edge lies below the peak in realized terms too, as at 300k with SGLang (0.195 against 0.233) and unlike the native pool (0.493 against 0.479).
15. **Which blind vLLM prediction is drawn (F2, F3).** `notes/PREDICTIONS_vllm.md` has four configurations (V0 = SGLang-calibrated engine unchanged, V1 = token costs scaled to vLLM's all-miss token rate; each in mixed and separate batching) and names no single one the prediction; mixed is the primary mode. The figures draw V1 mixed because its sessions/s are in vLLM's units (V0's own lambda_miss is 0.0722, 10% above vLLM's 0.0657, so its rates and mu would sit 10% high on a sessions/s axis). The spread of the other three is in the F2 and F3 readings; the text quotes the range over all four (hit 0.46-0.53 at n = 32; 6-8/10 stable at 2.5 x).
16. **Estimator spread in the vLLM curve (F2).** As at 300k with SGLang (note 4), the sessions-based and turns-based mu differ past the cliff: at n = 32, 40, 48 the sessions-based mu is 0.043, 0.041, 0.044 (0.66, 0.63, 0.67 x lambda_miss), the turns-based 0.054, 0.056, 0.059 (0.83, 0.85, 0.90 x). Single runs; the plus signs show the turns-based values.
