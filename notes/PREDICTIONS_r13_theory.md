# Round-13 theory: frozen blind predictions (tag `r13-theory-pred`)

Frozen 2026-10-31 around 02:10 CDT on branch `r13/theory`. The commit hash and GitHub push time are in the tag message and in the follow-up section at the end. Machine-readable version: `configs/r13_theory_predict.yaml`. Full per-cell records: `results/theory/merged/<cell>.json`. Scoring rules, frozen with the predictions: `notes/THEORY_r13_scoring.md` and `analysis/theory/merged/scoring.yaml`. Theory: `notes/THEORY_r13_merged.md`.

## Headline

| target | primary prediction | band / alternatives | falsified if |
|---|---|---|---|
| **H200** (SGLang, Qwen2.5-7B, 300k pool) | window 1.92 (F1; fluid 1.95); μ_max 0.372 sessions/s; peak at n ≈ 32.5 with hit ≈ 0.69; 0.5-hit crossing n 37.3; all-miss onset n_b 41.3, against 32.7 on the A100, so the cliff moves **out** while the window **narrows**; F2 edge 1.39× (bracket [1.25, 1.5]) | window 1.65-1.96, edge 1.24-1.40× (five cost variants); A's level-crossing edge 1.42-1.58×; e0a2 predicts even 1.25× unstable (P = 0.5+) | window ≥ 2.4; hit(32) < 0.5; hit(48) ≥ 0.5 |
| **Llama-3.1-8B** (A100, 300k) | a priori λ_miss 0.0619; μ_max 0.208 (F1) at n ≈ 23; 0.5-hit crossing 30.9; n_b 32.0; window 3.37 (F1; fluid 3.59); edge 2.46× | conditional on the measured E0a through the speed table (below) | n_half outside the table's value ± 3; no collapse by n = 48 |
| **Pool sweep** (A100, 150k / 600k) | window 1.87 / 5.47 (F1); n_b 18.3 / 61.2; 0.5-hit crossing 16.9 / 60.0; F2 edge 1.09× (no stable registered multiple) / 4.53× | A's criterion: 1.47× / 4.82× (150k discriminates the two edge heuristics) | 150k window ≥ 2.5 or hit(24) ≥ 0.5; 600k window < 4.5 or hit(48) < 0.5 |
| **B1** (1.65×, 300k) | P(STUCK) per seed: burst of 100 → 1.000, burst of 25 → 0.042; **P(PASS) = 0.995** | N_crit (deterministic / 50% committor): 59.4 / 56 at 1.35×, 53.4 / 50 at 1.65×, 46.1 / 42 at 2.0× | FAIL; the theory-specific content is N_crit ≈ 50-53 at 1.65× |
| **R1** (cap 20 at 1800 s, 300k) | **RESCUED** at both rates; release 3,830 s (1.35×) and 4,360 s (1.65×); relapse probability 0.002 / 0.025 | F1 phase 1: 3,920 / 4,480 s. Release by 7,200 s needs the phase-1 rate ≥ 32% / 42% of its fluid value. A collapsed phase 1 misses the deadline at both rates (7,510 / 9,240 s with the resumed mix) | NOT RESCUED; release time outside ±15% |
| **R4** (native, 4.0×, cap 64 at 2100 s) | **RESCUED**; release 5,040 s; relapse ≈ 0 | F1 phase 1: 5,250 s. Least robust: it needs the phase-1 rate ≥ 51% of its fluid value; a collapsed phase 1 gives no release | release time outside ±15% |

Model-consistent estimator: every μ above is a turns-based rate (completed turns per second / E[T]), and blind cells are scored against the turns-based estimator (`notes/THEORY_r13_scoring.md`). On the three measured cells the F1 μ_max is high by +3.6% (300k), +6.3% (native) and +11.6% (vLLM) on that estimator. A similar upward bias is expected on the blind cells.

## Inputs, per target (and what each prediction does NOT use)

No prediction uses any measured μ(n) point, E0b outcome or E2 outcome. Each JSON's `audit` list gives every parameter with its source. The leakage guard `tests/test_theory_r13_freeze.py` runs the prediction code on blind specs with `open` and `os.path.exists` patched to fail on any `results/nova` or out-of-sample path, and it passes.

- **Common inputs:**
  - the workload section of `configs/agentload_e2_burst.yaml`;
  - the SGLang A100 iteration-cost calibration `calibration/round6_server_log_fit/calibration.yaml`. It was fitted to server-log timing only, but the 300k Stage C runs' server logs are among its data;
  - the pool M.
- **H200:** M = 300,000, plus the H200 E0a (an allowed input): λ_miss 0.19388 sessions/s (turns-based) and 29,866 all-miss tok/s.
  - **Service-cost assumption (primary):** every A100 iteration cost is divided by one uniform speed factor s, fitted so that the model's E0a analogue (closed POP 32, cache off) reproduces 29,866 tok/s. This gives s = 2.742.
  - **Bands:**
    - s fitted to the H200/A100 token ratio (2.703) or to the λ ratio (2.761);
    - a decode/memory-side factor of 2.0 with the compute side fitted;
    - two factors fitted to the E0a tokens and the POP-64/POP-32 ratio of 1.046.
  - **Pre-freeze warning:** uniform scaling predicts a POP-64/POP-32 ratio of 1.019 against the measured 1.046.
- **Llama-3.1-8B:** M = 300,000 tokens and the same token workload.
  - **Cost assumption (point predictions):** the Qwen costs are multiplied by published-architecture roofline ratios: weights ×1.05, per-token GEMM ×1.06, decode attention ×2.286 (layers × KV heads), prefill attention ×1.306 (layers × query heads). λ_ref is the model's own λ_miss, 0.0619.
  - **Conditional rule (frozen):** once the Llama E0a is measured, set s = T_meas / 9,559 and read every quantity from `results/theory/merged/llama31_8b_300k_speed_table.json` by linear interpolation in s. Then express windows and edges as μ / λ_miss,meas. Selected rows:

    | s | E0a tok/s | λ_miss (model) | μ_max fluid / F1 | peak n | n_half | n_b | F2 edge (sessions/s) |
    |---|---|---|---|---|---|---|---|
    | 0.80 | 7,647 | 0.0495 | 0.196 / 0.182 | 24.1 | 30.3 | 31.17 | 0.135 |
    | 0.90 | 8,603 | 0.0557 | 0.210 / 0.196 | 24.2 | 30.6 | 31.59 | 0.144 |
    | 1.00 | 9,559 | 0.0619 | 0.222 / 0.208 | 24.3 | 30.9 | 32.02 | 0.152 |
    | 1.10 | 10,509 | 0.0680 | 0.233 / 0.220 | 24.5 | 31.2 | 32.44 | 0.159 |
    | 1.20 | 11,459 | 0.0742 | 0.244 / 0.230 | 24.7 | 31.5 | 32.87 | 0.166 |

  - **Independent of service speed:** the pool part of the cliff, M/E_S = 27.76 sessions, and the fold-freeness (Proposition F margin 0.78).
  - **Weakly dependent:** the cliff (n_half 30.0-32.4 and n_b 30.7-34.2 over s = 0.7-1.5) and the peak location (24.1-25.6).
  - **Strongly dependent:** μ_max, the window and the edge, in absolute units.
- **Pool sweep:** M = 150,000 or 600,000. Everything else is as in the A100 300k cell, with no fitted parameter. λ_ref is the 300k E0a value 0.071534. The model's 150k all-miss state is already memory-bound at POP 32 (0.0688).
- **B1:** the a100_300k cell, 1.65 × 0.071534, the registered burst sizes and the evaluation window. The committor and the stuck-by time (6,344 s) are derived from the model.
- **R1 / R4:** the a100_300k and native cells and the registered rescue protocol: cap, t_on, the 600 s minimum, the 300 s hold, the 10 s tick and the 7,200 s deadline.

## Blindness scope

- **Known to the theory authors before the freeze:** every committed result of the three measured cells:
  - the A100 300k cell: Stage C, E0a, E0b, E2 and the loop variables;
  - the A100 native-pool cell: Stage C, E0a, E0b and E2;
  - the exploratory vLLM 0.32.0 cell: Stage C, E0a, E0b and E2, used for validation;
  - the registered B1, R1 and R4 protocols (configs and verdict code, no results);
  - the round-7 simulator sweeps behind B1's design (in the simulator, 25 never trapped, 50 trapped about half the time and 100 always trapped);
  - the registered simulator prediction R1 RESCUED 20/20.
  - The model and its selection were scored on the measured cells, as disclosed in `notes/THEORY_r13_merged.md` §0.
- **Allowed inputs:** the H200 E0a numbers (λ_miss 0.19388, 29,866 tok/s, POP-64 ratio 1.046), from the task brief.
- **Not read by anyone writing this theory:**
  - the H200 Stage C curve (any n), the H200 E0b and E2;
  - any Llama-3.1-8B result (none existed);
  - the pool-sweep results (jobs begin at 04:00 CDT);
  - the B1, R1 and R4 results.
  - Nobody in this workflow connected to Nova by ssh, and no `results/nova` directory whose name contains h200, llama31, r11, b100, b25, e0bfresh, lpminf or rescue was opened.
- **Known exception (from COORD/COORDINATION.md, lead note 2026-10-30 23:00):** the H200 operator session read the per-job Stage C μ values for n = 16-32 (jobs 17166818-22) at about 22:28 CDT Friday, before the hold, and showed them to Akshat. The lead and the theory agents never saw them. For the H200 cell, n ≥ 40 and the E0b edge are therefore fully blind. n = 16-32 are blind with respect to the theory's authors, but not with respect to the project as a whole.

## What the post-review fixes changed (before this freeze)

- **R1 collapsed-phase bound:** "released even if phase 1 collapses" is withdrawn. The bound now uses the closed-cap all-miss rate.
- **B1:** the burst's per-turn cycle now uses the model's S̄ at n1 instead of a hard-coded 1.5 s. The probabilities change in the third decimal.
- **Theory text:**
  - Proposition F (fold identity) is added;
  - T6 is restricted to fold-free laws;
  - the novelty claims ("dead KV", "endogenous gap") are corrected;
  - MISA-T is credited.
- **Model, parameters, curve, edge and E2 predictions:** none changed.

Full list: `notes/THEORY_r13_merged.md` §10.

## Open problems stated at the freeze

1. **No limit theorem** links the engine to the fluid model. Every proved statement is about the deterministic model.
2. **Assumption MF (Che) does not concentrate** at the H200, 300k, vLLM and 150k pool sizes: the margin at the peak is at most 1 composition s.d., and the H200 margin is negative. A deterministic eviction age biases μ_max upward. This is the likeliest failure mode of the H200 μ_max and window prediction.
3. **Uniform speed scaling misfits the H200 POP-64 ratio** (1.019 against 1.046). The e0a2 variant, which fits that ratio, gives the low end of the band (window 1.65, edge 1.24×).
4. **R4 depends on the phase-1 rate** staying at least 51% of its fluid value. R1 at 1.65× needs at least 42%.
5. **Quasi-static quantities near n_u** (b_stat, the committor's starting points near n_u, T9's upper end) are heuristics; μ(n) does not determine them.
6. **The registered workload is fold-free,** but dispersed tool times (CV ≳ 1.2 for two-phase mixtures, lognormal CV ≥ 2) fold the closed curve (Proposition F). The paper's experiments use exponential tool times only.
7. **The relapse probability** is F2 escape to n_b. It is mapped to the registered relapse event (any 300 s window with follow-up hit < 0.2 after t_rel + 300 s) by identification, not derived.
8. **H200 and Llama E2 predictions** use the model's own registration consequence (H200 points 1.10/1.15× and cap 32; Llama 1.35/1.65× and cap 24), not the cells' actual registrations. Predictions at the registered rates follow by the frozen conditional rule in `notes/THEORY_r13_scoring.md`.

## Freeze record (follow-up commit; nothing above this section changed after the tag)

- Freeze commit `997d2c4d9d25b1d2ef26fdbc8c7b35a9860ceff0` (committer time 2026-10-31T02:04:55-05:00), annotated tag `r13-theory-pred` (tag object `b900d1926d82d11a79156c1bd28ebc7824699088`).
- GitHub push time of branch `r13/theory` at that commit: **2026-10-31T07:05:30Z (02:05:30 CDT)**, from `gh api repos/AkshatValse/Nova-Research/activity` (activity_type branch_creation, after = 997d2c4). The tag was pushed immediately afterwards (02:05:31 CDT local clock); the activity API does not list tag pushes, and `gh api repos/AkshatValse/Nova-Research/git/refs/tags/r13-theory-pred` resolves to the tag object above.
- Tests at the freeze: tests/test_theory_{r13_freeze,predict,fluid_rigorous,che_endogenous}.py, 51 passed.
