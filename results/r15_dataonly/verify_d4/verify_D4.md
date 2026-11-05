# D4: independent check of the head-to-head with Lu et al. (arXiv:2611.02543)

Checker: independent agent, 2026-11-05. Read-only. Nothing in the repository was edited, committed or deleted, and Nova was not contacted. Every number below was recomputed from committed files by the scripts in this folder (listed in section 7).

**Concurrent edits.** While I worked, another session changed this worktree: `paper/main.tex`, `limitations.tex`, `results.tex` and `theory.tex` are modified and new `paper/sections/v2_*.tex` files exist. All my citations of paper text refer to commit `e38735f` (HEAD). The data and the frozen JSONs are untouched. `git diff r13-theory-pred HEAD -- results/theory/merged` is empty, and `results/theory/pred2/h200_600k.json` is identical to tag `r13-theory-pred2`. The v2 draft has D4 placeholders at `v2_entry.tex:61-64`, `v2_app_dataonly.tex:43-45` and `v2_intro.tex:57`, and it cites the paper as `\citep{lu2026cachetrap}`.

## 1. Verdicts

| # | Claim | Verdict | Why |
|---|---|---|---|
| 1 | Eq. 2 in colocated serving reduces to f ≲ 0.5 (0.53 with 1.9); f at the model peak; flags 7 of 8; "nearly vacuous" | **Numbers CONFIRMED** (one rounding fix). **Reading UNFAIR-REWORD.** Do not print "nearly vacuous". | f at the fluid peak recomputes to 0.308, **0.315** (claim says 0.31; 0.315 rounds to 0.32), 0.401, 0.529, 0.207, 0.188, 0.311 and 0.370. Eq. 2 compares a dedicated prefix cache with decode memory. In one pool, running KV filling the pool *is* the cliff (K_run/M = 0.89 at n = 32 on 300k, `theory.tex:49`), so the two limits coincide. In our cells f is not a deployment constant: 0.19-0.53 at the peak, 0.38-0.90 at the 0.5 crossing, 0.67-0.95 at n_b. The verdict therefore goes from 7/8 to 1/8 to 0/8 flagged depending on where f is read. The native cell flips with the estimator (fluid 0.529; F1 0.510 < 1/1.9; measured 0.500). All 8 cells have a measured window and 5 trapped in registered tests, so 7/8 flagged is 7/8 correct; specificity cannot be tested here. Their actual classifier (Fig. 9b) uses throughput bounds, not Eq. 2. |
| 2 | Onset table, MAEs, GPU independence, affine-in-M | **CONFIRMED, with 4 corrections.** The fitted-h reading is **fair** (and robust). The 1.9 column is a **straw man** if presented as their prediction. | (a) Native Lu-fit is 102.47, so print **102.5**, not 102.4. (b) The intercept is **2.97 ± 0.71** (95% CI −0.08 to 6.02, four A100 pools), not "about +2". It is not literally "= the tool-call term": that term is 4.7-5.1, less the 1.1-1.4 sessions by which n½ precedes n_b and about 0.6 from E_S > Ē. The frozen n½ itself gives 2.77 + 1.007 M/Ē. (c) "Ours (no fit)" should say: no parameter fitted to any curve point; H200 and vLLM use one speed factor fitted to their all-miss token rate. (d) Of the "5 blind" cells, 3 are blind in time (150k, 600k, H200 600k) and 2 blind by access only (H200 300k; Llama). For H200 300k the first author had seen n ≤ 32, and the crossing lies between n = 36 (blind in time) and 40 (by access only). All MAEs reproduce: 4.66 / 1.53 (7 cells) and 4.11 / 1.55 (5 cells). Robustness: (i) κ fitted by least squares to all 8 cells, in sample for Lu: MAE 3.74 vs ours 1.42. (ii) Leave-one-out: 4.72. (iii) Token-hit crossings: 4.05 vs 1.53 on the 5 cells. (iv) h refitted on the H200 300k cell gives H200 600k = 77.7 (meas 71.0, ours 66.6). |
| 3 | Window: native/300k peak-ratio ratio measured 2.06, Lu 3.19, ours 2.11 | **Numbers CONFIRMED** (2.057, 3.186 = pool ratio, 2.110). **Comparison UNFAIR-REWORD / NOT VERIFIABLE.** Omit the "Lu 3.19" number. | 3.19 is what you get with the closed-loop bound alone. Their X(N) also contains a prefill bound μ_p/u(N) and a decode bound, combined by a smooth minimum whose form the paper does not give. On one GPU, prefill and decode share compute. Any compute bound lowers the native peak. For example, capping it at our model's own compute bound (`window.compute_cap` = 8.49 λref, native JSON) with the 300k peak at its measured 3.15 already gives a ratio of at most 8.49/3.15 = 2.69, and a smooth minimum gives less. The 3.19 therefore rests on choices that would be ours, not theirs. Our 2.11 is **in sample** (both cells were known to the agents that derived the model). |
| 4 | Eq. 4 drain: R1 1.35 ~3200 s (−20 to −30%), R1 1.65 ~3550, R4 ~3875 (−35 to −37%); ours 3830/4360/5040 (−4 to −16, −1.6 to −11, −16 to −18%) | **Numbers CONFIRMED, one correction.** **Comparison UNFAIR-REWORD.** | Correction: per run, R4 is **−34% to −39%** (3740-3942 s), not −35 to −37%. Over the input choices (n_on, μ estimator, peak vs cap), errors are −17 to −34% (R1 1.35), −16 to −31% (R1 1.65) and −34 to −41% (R4). Their Eq. 4 is stated for resident-first ordering near N* "even with healthy cache reuse". Its Q counts sessions *waiting for their first call* (Lu l. 257). Most of the rescue backlog is instead admitted sessions paused at tool boundaries, whose next turn misses. Lu et al. themselves describe low reuse after collapse (hysteresis, l. 249-251). The like-for-like fact: **our own frozen single-phase variant** (`stationary`, 3441/3890/4072 s, same JSON, not a declared prediction) is also 12-34% early. The gain comes from the two-phase structure, not from a different departure peak. |

## 2. Sources (committed files)

**Lu et al.** (`Nova-Research-wt/COORD/scoop-2611.02543/other_paper.txt`, untrusted; read as data):
- Eq. 1: l. 208.
- Smooth minimum of the closed-loop, prefill and decode bounds: l. 212.
- u(N) = max(n_new, (1−h(W/C))P); "the model uses the real-system hit-rate curve in Fig. 6b": l. 214.
- Cliff near 1.9 C/c̄ and N_d = D_KV/(f c̄): l. 226.
- Eq. 2: l. 229.
- Classifier by throughput-bound ratio: l. 237.
- Hysteresis, and the collapsed-state departures that set the recovery scale: l. 249-251.
- Q = sessions waiting for their first call: l. 257.
- Resident-first ordering: l. 264.
- Eq. 4: l. 269.
- Drain S/(D(N*)−λ), "even with healthy cache reuse": l. 273.
- Their setup (PD-disaggregated, H100 NVL, 1.09M-token prefix cache, 1.66M decode KV): l. 124.
- Cliff at W ≈ 2C, h ≈ 0.3: l. 158.

**Measured 0.5-hit crossings.** Each is a linear interpolation in `hit_frac_turns`; the bracketing points are given in parentheses.

| cell | value | committed source |
|---|---|---|
| A100 150k | 16.525 | `results/nova/pool_sweep_1716886x_pulled_20261031-112342/derived/pool_sweep_scored.json:80` (`cells.150k.measured.n_half`). Raw: `.../agentload_analysis_closed/20261031-112201/mu_curve.csv` (n=16: 0.5555; n=20: 0.1326). `paper/NUMBERS.md:933` |
| A100 300k | 32.165 | `results/theory/merged/validation_table.csv:11` (measured column). Raw: SC `results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv` (32: 0.5052; 48: 0.0). `NUMBERS.md:616` |
| A100 600k | 60.141 | `pool_sweep_scored.json:347` (`cells.600k.measured.n_half`). Raw: `.../20261031-112200/mu_curve.csv` (56: 0.7754; 64: 0.2433). `NUMBERS.md:933` |
| A100 native | 93.421 | `validation_table.csv:88`. Raw: NAT `results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv` (80: 0.9222; 96: 0.4189). `NUMBERS.md:221` |
| H200 300k | 38.876 | Raw: MU12 `results/nova/h200_stageC_extra_1716961x_pulled_20261031-040933/results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.csv` (36: 0.6132; 40: 0.4558). `NUMBERS.md:735,779` |
| H200 600k | 71.007 | Raw: `results/nova/h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/results/agentload_analysis_closed/20261031-092435/mu_curve.csv` (64: 0.6544; 72: 0.4781). `NUMBERS.md:958` |
| vLLM 300k | 29.101 | `validation_table.csv:165`. Raw: VSC `results/nova/stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv` (28: 0.6584; 32: 0.0830). `NUMBERS.md:554` |
| Llama 300k | 29.653 | Raw: L2 `results/nova/llama31_e0b_registration_pulled_20261031-075313/results/agentload_analysis_closed/20261031-074803/mu_curve.csv` (28: 0.7006; 32: 0.2153). `NUMBERS.md:987,1022` |

**Frozen predictions.** Fluid n½ is `closed_curve.fluid.n_half` and M/E_S is `all_miss.threshold.pool_part`. The files are at tag `r13-theory-pred` (H200 600k at `r13-theory-pred2`).
- `results/theory/merged/a100_pool150k.json`: n½ 16.905 (l.40); M/E_S 13.589 (l.20).
- `a100_300k.json`: 31.492 (l.40); 27.755 (l.20).
- `a100_pool600k.json`: 60.026 (l.40); 56.129 (l.20).
- `a100_native.json`: 93.737 (l.40); 89.786 (l.20).
- `h200_300k.json`: 37.322 (l.41); 27.755 (l.21).
- `results/theory/pred2/h200_600k.json`: 66.579 (l.41); 56.129 (l.21).
- `vllm_300k.json`: 31.751 (l.41); 28.219 (l.21).
- `llama31_8b_300k.json`: 30.921 (l.47); 27.763 (l.27).
- Ē = `all_miss.threshold.E_bar` = 10,568.69 in every cell.
- z̄' = `tool_call_part`/`nu_b` = 4.661 s; E[T] = `nu_b`/`mu_b` = 14.76.

**Rescue.**
- Measured releases are column `t_release` of `results/nova/rescue_1716896x_pulled_20261031-070502/results/agentload_analysis_rescue_r1/20261031-071720/rescue_runs.csv` and `.../agentload_analysis_rescue_r4/20261031-071748/rescue_runs.csv`. n_on is `sessions_in_system_at_t_on` (or `outstanding_at_t_on`).
- Frozen two-phase: `r1_rescue_300k.json:1511` (3830), `:1592` (4360); `r4_rescue_native.json:1163` (5040) (`tests.R*.result.<mult>.two_phase.t_release`).
- Single-phase variant (`stationary.t_release`): `r1:1489` (3440.7), `:1570` (3889.8); `r4:1142` (4071.8).
- λ = `tests.R*.result.<mult>.lam` (0.0965709, 0.1180311, 0.2871896).
- Paper record: `frozen.tex:48`, `frozen_app.tex:79-81,116`, `results.tex:85` (HEAD). Freeze push 02:05:30 CDT; first rescue start 02:23:44 (`frozen.tex:48`).

**Window.**
- `frozen_app.tex:19-24` (Table windowlaw).
- `window.annealed_vs_lambda_ref` in each JSON.
- λref: 300k = 0.0715340, from R1 `lam`/1.35; native = 0.0717974, from R4 `lam`/4.0.

## 3. Recomputed numbers

### 3.1 Onset (claim 2)

The Lu-fit column fixes κ = W/C at the measured A100 300k crossing = 1.13313 and predicts N½ = κM/Ē. The Lu 1.9 column is 1.9 M/Ē.

| cell | meas | Lu 1.9 | Lu-fit | ours n½ (fluid) | ours F1 | M/E_S | n_b | W/C at meas |
|---|---|---|---|---|---|---|---|---|
| A100 150k | 16.525 | 26.97 | 16.08 | 16.905 | 16.35 | 13.589 | 18.32 | 1.164 |
| A100 300k | 32.165 | 53.93 | (32.165) | 31.492 | 30.47 | 27.755 | 32.70 | 1.133 |
| A100 600k | 60.141 | 107.87 | 64.33 | 60.026 | 58.93 | 56.129 | 61.17 | 1.059 |
| A100 native | 93.421 | 171.82 | **102.47** | 93.737 | 92.04 | 89.786 | 94.86 | 1.033 |
| H200 300k | 38.876 | 53.93 | 32.17 | 37.322 | 36.52 | 27.755 | 41.31 | 1.370 |
| H200 600k | 71.007 | 107.87 | 64.33 | 66.579 | 64.78 | 56.129 | 69.94 | 1.251 |
| vLLM 300k | 29.101 | 53.93 | 32.17 | 31.751 | 30.69 | 28.219 | 32.83 | 1.025 |
| Llama 300k | 29.653 | 53.93 | 32.17 | 30.921 | 30.06 | 27.763 | 32.02 | 1.045 |

Mean absolute error (sessions):

| set | Lu-fit | ours n½ | ours F1 | M/E_S | Lu 1.9 |
|---|---|---|---|---|---|
| 7 cells (all but the anchor) | **4.66** | **1.53** | 1.91 | 5.62 | 33.9 |
| 5 frozen-before-read cells (150k, 600k, H200 300k, H200 600k, Llama) | **4.11** | **1.55** | 2.08 | 6.97 | 26.9 |
| 3 blind-in-time cells (150k, 600k, H200 600k) | 3.77 | 1.64 | | | |
| all 8 | 4.08 | 1.42 | 1.88 | 5.47 | 32.4 |

Signed errors (pred − meas):
- Lu-fit: −0.44, 0, +4.19, +9.05, −6.71, −6.68, +3.06, +2.51.
- Ours: +0.38, −0.67, −0.11, +0.32, −1.55, −4.43, +2.65, +1.27.

Robustness, all charitable to Lu:
- κ by least squares on all 8 (= 1.0977, in sample): MAE 3.74 (8 cells) and 4.21 (5 cells), against ours 1.42 and 1.55.
- κ fitted on the four A100 Qwen pools (= 1.0485): MAE 3.57 (7) and 4.59 (5).
- Leave-one-out proportional model: MAE 4.72 over 8.
- Crossings in the cached-token fraction (their h is a token hit rate): Lu-fit 4.26 / 4.05 against ours 1.66 / 1.53 (7 / 5 cells).
- h refitted on each GPU's own 300k cell: H200 600k = 2 × 38.876 = 77.75 (error +6.74; ours −4.43).

H200 shift (H200 minus A100 at the same pool):

| | 300k | 600k |
|---|---|---|
| measured | +6.711 | +10.866 |
| ours n½ | +5.830 | +6.553 |
| ours n_b | +8.610 | +8.773 |
| proportional h | 0 | 0 |

Affine fit on the four A100 pools:
- Measured crossing = 2.973 (SE 0.709) + 1.0030 (SE 0.0127) · M/Ē. Residuals −0.68, +0.72, +0.22, −0.26. The 95% CI for the intercept is [−0.08, 6.02] (2 df).
- A fit through the origin leaves residuals +1.64, +2.40, +0.62, −1.40.
- Without the native pool: 2.54 + 1.019 M/Ē.
- Frozen n½: 2.77 + 1.007 M/Ē.
- Tool-call part ν_b z̄': 4.73, 4.94, 5.04 and 5.07 (A100); 13.55 and 13.81 (H200).

### 3.2 f and Eq. 2 (claim 1)

f = 1 − ν z̄'/n on the queue-free branch, which equals S̄/(S̄ + z̄'). With C = D_KV = M, Eq. 2 becomes f ≲ 1/2. With the 1.9 constant it becomes f < 1/1.9 = 0.526, which is equivalent to S̄ < 5.18 s.

| cell | f, fluid peak | f, F1 peak | f, measured peak | S̄ at fluid peak (s) | f at fluid n½ | f at n_b = (M/E_S)/n_b |
|---|---|---|---|---|---|---|
| A100 150k | 0.308 | 0.342 | 0.312 | 2.07 | 0.539 | 0.742 |
| A100 300k | 0.315 | 0.330 | 0.353 | 2.15 | 0.716 | 0.849 |
| A100 600k | 0.401 | 0.402 | 0.415 | 3.13 | 0.844 | 0.918 |
| A100 native | **0.529** | **0.510** | **0.500** | 5.24 | 0.899 | 0.947 |
| H200 300k | 0.207 | 0.214 | 0.210 | 1.22 | 0.379 | 0.672 |
| H200 600k | 0.188 | 0.196 | 0.173 | 1.08 | 0.618 | 0.803 |
| vLLM 300k | 0.311 | 0.325 | 0.275 | 2.10 | 0.735 | 0.860 |
| Llama 300k | 0.370 | 0.376 | 0.328 | 2.74 | 0.758 | 0.867 |

- Sanity check: f·n*·E_S/M at the 300k peak is 0.283, matching the paper's K_run/M = 0.28 at the fluid peak (`theory.tex:49`).
- Flags at the fluid peak: 7 of 8 under either threshold (native not flagged). At the F1 peak, native is flagged under 1/1.9, giving 8 of 8. At n½: 1 of 8. At n_b: 0 of 8.
- Window and trap evidence:
  - Every cell has a from-empty edge above λref: 150k [1.2,1.3), 300k [2.0,2.5), 600k [4.5,5.0), native [5.5,6.5), H200 300k [1.3,1.4), H200 600k [2.5,3.0), vLLM [2.0,2.5), Llama [2.0,2.5).
  - Registered paired tests trapped on 300k, native, vLLM and H200 600k, and on Llama at 1.65 λref.

### 3.3 Window (claim 3)

Peak ratios μ*/λref, turns-based:

| cell | measured | F1 | fluid |
|---|---|---|---|
| A100 150k | 1.678 | 1.872 | 1.969 |
| A100 300k | 3.153 | 3.267 | 3.464 |
| A100 600k | 5.709 | 5.471 | 5.718 |
| A100 native | 6.484 | 6.893 | 7.070 |
| H200 300k | 1.894 | 1.916 | 1.949 |
| H200 600k | 2.977 | 3.196 | 3.268 |

Ratios of peak ratios:

| pair | measured (sessions-based) | ours F1 | ours fluid | proportional (pool ratio) |
|---|---|---|---|---|
| native / 300k | **2.057** (2.045) | **2.110** (in sample) | 2.041 | **3.186** |
| 600k / 300k | 1.811 (1.833) | 1.675 | — | 2.0 |
| 150k / 300k | 0.532 (0.507) | 0.573 | — | 0.5 |
| H200 600k / 300k | 1.572 (1.532) | 1.668 | — | 2.0 |

### 3.4 Drain (claim 4)

Lu Eq. 4 is evaluated as release = t_on + (n_on − cap)/(μ* − λ) + 300 s. The main reading uses n_on = sessions in system at t_on and μ* = measured turns-based peak (0.22552 at n=24, 300k; 0.46552 at n=64, native).

| test | seed | S | Lu t_rel | measured | pred vs meas | meas late vs Lu |
|---|---|---|---|---|---|---|
| R1 1.35 | 0 / 1 / 2 | 138 / 142 / 135 | 3170 / 3201 / 3147 | 4550 / 3980 / 4400 | −30.3 / −19.6 / −28.5% | +44 / +24 / +40% |
| R1 1.65 | 0 / 1 / 2 | 156 / 159 / 146 | 3551 / 3579 / 3458 | 4920 / 4430 / 4570 | −27.8 / −19.2 / −24.3% | +39 / +24 / +32% |
| R4 4.0 | 0 / 1 / 2 | 275 / 260 / 239 | 3942 / 3858 / 3740 | 6000 / 5980 / 6140 | −34.3 / −35.5 / −39.1% | +52 / +55 / +64% |

Our frozen predictions:

| prediction | t_rel (R1 1.35 / R1 1.65 / R4) | pred vs meas | measured late |
|---|---|---|---|
| two-phase (primary) | 3830 / 4360 / 5040 | −3.8..−15.8 / −1.6..−11.4 / −15.7..−17.9% | +3.9..+18.8 / +1.6..+12.8 / +18.7..+21.8% (matches `frozen_app.tex:116`) |
| two-phase F1 | 3920 / 4480 / 5250 | | |
| single-phase `stationary` (in the frozen file, not declared) | 3441 / 3890 / 4072 | −13.5..−24.4 / −12.2..−20.9 / −31.9..−33.7% | +15.7..+32.2 / +13.9..+26.5 / +46.9..+50.8% |

The model's own n_on was 161.3 / 175.5 / 326.6, against measured sessions in system of 155-162 / 166-179 / 303-339. The Lu numbers therefore get the measured backlog, which is an advantage over ours.

## 4. Fairness: what a careful referee would accept

**Would accept:**
- **Fitted-h onset comparison** (claim 2), if stated as follows:
  1. Our post-hoc reading of a model built for PD-disaggregated serving, whose h is empirical and system-specific, and which aims to classify deployments and explain mitigations, not to predict h.
  2. C = M (literal); h fixed on one of our cells.
  3. "GPU-independent" means "with one hit curve carried across GPUs".
  4. The MAE quoted on the five cells frozen before their runs were read (3 blind in time, 2 by access only).
  5. The robustness check (best-fit κ on all 8 still 3.7 vs 1.4) given, so the anchor choice cannot be blamed.
- **The H200 shift** (+6.7/+10.9 measured, +5.8/+6.6 ours, 0 for a W/C-only h) is the strongest structural discriminator. Our model needs the H200's all-miss token rate (one E0a input); the proportional reading would need a re-measured h. Even refitted per GPU, it misses H200 600k by +6.7.
- **Scope statement**, without numbers: Eq. 2 and their throughput bounds are formulated for separate prefill and decode instances, and in one pool the cache-first / decode-first distinction collapses (as `v2_entry.tex:46-47` already says).
- **A like-for-like drain statement:** a single-phase drain at the peak rate is 19-39% early in Eq. 4's form and 12-34% early in our model's own single-phase variant (the engine released 24-64% and 14-51% after them). The frozen two-phase drain is 2-18% early (released 2-22% after it). Use one convention in the paper; the frozen scoring uses "late relative to the prediction".

**Would call a straw man:**
- **"Lu with 1.9 C/c̄" as their prediction.** It is a constant measured on a different system: disaggregated H100, hybrid MoE, Terminal-Bench, cliff defined near h ≈ 0.3. Their model prescribes the deployment's own hit curve. At most one clause: "their measured constant would put our crossings 1.4-1.9 times further out, so we fix h on one of our cells".
- **"Eq. 2 is nearly vacuous".** With one pool, the comparison is between the same memory. f moves along the curve, and the verdict depends on where it is read. Our cells have no negative case.
- **"Lu's window grows ∝ C (3.19 vs 2.06)".** This drops their prefill and decode bounds and an unspecified smooth minimum. Our 2.11 is in sample anyway.
- **"Lu's Eq. 4 misses the rescue by 20-37%" without the premise caveat.** Eq. 4 is for resident-first ordering, healthy reuse and a queue of first calls. The rescue backlog is mostly paused sessions whose next turn misses, which Lu et al. discuss as hysteresis. Pair it with our own single-phase variant.

## 5. Blind or in sample (our predictions)

- **Onset n½:**
  - Blind in time: A100 150k and 600k (`r13-theory-pred`, runs first started 06:50:13); H200 600k (pred2, 04:20:20; first start 05:27).
  - Blind by access only:
    - H200 300k: blind to the model's agents. The crossing lies between n=36 (blind in time) and n=40 (by access only). The first author had seen n ≤ 32.
    - Llama: the a priori costs were pushed while the closed runs were in progress.
  - In sample: A100 300k, native, vLLM (vLLM with a speed factor fitted to its all-miss rate).
- **Window ratio native/300k:** in sample (both cells). The pool doubling is blind in time on the 600k cells only.
- **Rescue two-phase releases:** blind in time (02:05:30 push; first rescue start 02:23:44). The single-phase variant sits in the same frozen file but was not a declared prediction.
- **f:** a model output, not a tested prediction.
- **Every Lu reading is post hoc:**
  - Lu-fit uses one parameter from A100 300k.
  - Eq. 4 uses the measured μ* (Stage C and native grid) and n_on measured in the rescue runs themselves.

**Side note on the v2 draft.** `v2_entry.tex` ("Out-of-sample record"): "The 0.5-hit crossings, predicted for eight cells, lie within 0.1-4.4 sessions". This includes three in-sample cells. The five frozen-before-read cells also lie within 0.1-4.4 (0.11, 0.38, 1.27, 1.55, 4.43), so say "five" in an out-of-sample paragraph. Separately, Lu et al.'s system is called *Basin*, which collides with our BASIN-1/2 test names; disambiguate.

## 6. Proposed text and table

**Main text** (replaces the D4 placeholder in `v2_entry.tex:61-64`):

> Lu et al.'s fluid model takes its hit rate $h(W/C)$, a function of the working set $W=N\bar c$ over the prefix-cache capacity $C$ alone, from measurements of the deployed, prefill--decode-disaggregated system, and uses it to classify deployments and explain mitigations rather than to predict it~\citep{lu2026cachetrap}. Read post hoc on our colocated cells with $C=M$, $\bar c=\bar E$ and one $h$ fixed by the A100 300k crossing ($W/C=1.13$), it puts the 0.5-hit crossing in proportion to the pool and, with that curve carried across GPUs, at the same population on the H200: on the five cells whose crossings were frozen before their runs were read it errs by 4.1 sessions on average against 1.5 for our frozen crossings (Table~\ref{tab:lu}), and the measured crossing moved out on the H200 by 6.7 and 10.9 sessions against 5.8 and 6.6 from the tool-call term. Their vulnerability condition and throughput bounds are stated for separate prefill and decode instances and their drain estimate for resident-first ordering with healthy reuse, so we do not score them as predictions; with one pool the first reduces to $f\lesssim1/1.9$ for the fraction $f$ of sessions in service, which here moves along the curve (0.19--0.53 at our model's peak, 0.67--0.95 at $n_b$), and the second, applied to the rescue tests with the measured peak rate and backlog, has the single-phase form of our model's own stationary drain: the engine released 24--64\% after it and 14--51\% after that variant, against 2--22\% after the frozen two-phase drain, in which every paused session's next turn misses.

**Intro sentence** (`v2_intro.tex:57`):

> Read on our cells with one fitted hit curve, Lu et al.'s concurrent model puts the hit-rate cliff in proportion to the pool and at the same population on a faster GPU; the measured cliff moved out on the H200, as our tool-call term predicts, and on five cells frozen before their runs were read our crossings err by 1.5 sessions on average against 4.1.

**Table** (main text or the D4 appendix):

```latex
\begin{table}[t]\centering\footnotesize
\caption{The 0.5-hit crossing (sessions) against Lu et al.'s hit curve $h(W/C)$, read post hoc with $C=M$, $\bar c=\bar E=10{,}569$ tokens and $h$ fixed by the measured A100 300k crossing ($W/C=1.133$), so that it predicts $1.133\,M/\bar E$ on every engine and GPU; our frozen crossing $n_{1/2}$ (fluid; no parameter fitted to any curve point; the H200 and vLLM cells use one speed factor fitted to their all-miss token rate); and the capacity ratio $M/E_S$. Status of our prediction: b, blind in time; a, blind by access only ($^\ast$the crossing lies between $n=36$, blind in time, and 40; the first author had seen $n\le32$); i, in sample. Lu et al.'s measured constant $N_c\approx1.9\,C/\bar c$, from a disaggregated H100 deployment, would put every crossing 1.4--1.9 times further out. With its constant fitted to all eight crossings ($W/C=1.098$) the $h(W/C)$ reading errs by 3.7 sessions on average, against 1.4 for $n_{1/2}$. Sources: \fpath{results/theory/merged/*.json}, \fpath{results/theory/pred2/h200_600k.json}; measured crossings as in Table~\ref{tab:frozensum}.}\label{tab:lu}
\begin{tabular}{@{}lccccc@{}}\toprule
cell & status & measured & $h(W/C)$ & $n_{1/2}$ & $M/E_S$\\\midrule
A100, 150k & b & 16.5 & 16.1 & 16.9 & 13.6\\
A100, 300k & i & 32.2 & (32.2) & 31.5 & 27.8\\
A100, 600k & b & 60.1 & 64.3 & 60.0 & 56.1\\
A100, native & i & 93.4 & 102.5 & 93.7 & 89.8\\
H200, 300k & a$^\ast$ & 38.9 & 32.2 & 37.3 & 27.8\\
H200, 600k & b & 71.0 & 64.3 & 66.6 & 56.1\\
vLLM, 300k & i & 29.1 & 32.2 & 31.8 & 28.2\\
Llama-3.1-8B, 300k & a & 29.65 & 32.2 & 30.9 & 27.8\\\midrule
mean error, b and a cells (5) & & & 4.1 & 1.5 & 7.0\\
mean error, all but A100 300k (7) & & & 4.7 & 1.5 & 5.6\\\bottomrule
\end{tabular}
\end{table}
```

**Optional appendix additions** (`v2_app_dataonly.tex:43`, D4):
- The robustness checks of 3.1: least-squares κ 3.74 vs 1.42; leave-one-out 4.72; token-hit 4.05 vs 1.53; per-GPU refit gives H200 600k at 77.7.
- The affine fit, 2.97 + 1.003 M/Ē, with the intercept CI [−0.1, 6.0] (do not call the intercept established).
- The f table of 3.2.
- The drain table of 3.4: Eq. 4 measured-late +24% to +64%, our single-phase +14% to +51%, two-phase +2% to +22%, in the paper's "late" convention.
- No window comparison.

## 7. Files in this folder

- `onset.py`, `onset_stdout.txt`, `onset_out.json`: claim 2.
- `fcheck.py`, `fcheck_stdout.txt`: claim 1.
- `window_and_extra.py`, `window_stdout.txt`: claim 3, intercept CI, token-hit robustness.
- `drain.py`, `drain_stdout.txt`, `drain_out.csv`: claim 4.
- `extract.py`: dump of the frozen JSON keys.
