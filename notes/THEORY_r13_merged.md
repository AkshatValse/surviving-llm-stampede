# Round 13 theory, merged: one model, one prediction code path

Written 2026-10-31 00:20-01:20 CDT on branch `r13/theory` (worktree base `582c2a6`); **revised 01:45-02:30 CDT after two adversarial reviews and frozen under tag `r13-theory-pred`** (the post-review changes are listed in section 10; the frozen predictions are in `notes/PREDICTIONS_r13_theory.md` and `configs/r13_theory_predict.yaml`). Inputs: the two independent derivations `notes/THEORY_r13_che_endogenous.md` (approach A, code `analysis/theory/che_endogenous/`) and `notes/THEORY_r13_fluid_rigorous.md` (approach B, code `analysis/theory/fluid_rigorous/`). Both are left unchanged as records.

- **Code path:** `analysis/theory/predict.py`, which turns a cell spec YAML into a predictions JSON. Spec loading and the fitting audit live in `analysis/theory/merged/spec.py`. The grafts and the new layers live in `analysis/theory/merged/extras.py`. The model itself is B's `analysis/theory/fluid_rigorous/{model,edge,trapped,oos}.py`, unchanged.
- **Specs:** `analysis/theory/cells/`. The three measured cells are `a100_300k`, `a100_native` and `vllm_300k`. The blind cells are `h200_300k`, `h200_300k_decode2`, `h200_300k_e0a2`, `llama31_8b_300k`, `a100_pool150k` and `a100_pool600k`. The registered tests are `b1_basin_300k`, `r1_rescue_300k` and `r4_rescue_native`.
- **Validation:** `analysis/theory/validate.py` writes `results/theory/merged/validation_table.{csv,md}` and `validation.json`, 183 rows.
- **Summary and figures:** `analysis/theory/merged/summarize.py` writes `results/theory/merged/summary.md`. `analysis/theory/merged/plots.py` writes `figures/theory/merged_validation.{png,pdf}` and `merged_blind.{png,pdf}`.
- **Tests:** `tests/test_theory_predict.py` has 13 tests. With the 23 tests of A and B, 36 pass in about 70 s.

Reproduce:

```
PYTHONPATH="src;." python -m analysis.theory.validate                      # three measured cells, ~3 min
PYTHONPATH="src;." python -m analysis.theory.predict analysis/theory/cells/{h200_300k,h200_300k_decode2,h200_300k_e0a2,llama31_8b_300k,a100_pool150k,a100_pool600k,b1_basin_300k,r1_rescue_300k,r4_rescue_native}.yaml
PYTHONPATH="src;." python -m analysis.theory.merged.summarize && python -m analysis.theory.merged.plots
```

Everything is deterministic: fixed grids and seeded Monte Carlo. Every predictions JSON records the SHA-256 of the code files, the spec, the calibration and the workload config.

**Blindness of this step.** I read the committed data of the three measured cells: Stage C curves, E0a, E0b brackets, E2 `trap_v2_runs.csv`, and the frozen-loopvars values and capped drains that A typed in `che_endogenous/measured.py`. I also read the registered B1, R1 and R4 protocols (configs and the verdict code in the rescue worktree, not results). I did not ssh to Nova. I opened nothing of the H200 or Llama cells, the pool sweep, B1, R1/R4 results, or any `results/nova` directory whose name contains h200, llama31, r11, b100/b25, e0bfresh, lpminf or rescue. The H200 E0a numbers (29,866 tok/s, 0.19388, POP-64 ratio 1.046) come from the task brief, where they are listed as allowed inputs.

## 0. Decision

**Base model: approach B** (the fluid mean-field model). The reasons follow; scores are from `results/theory/merged/summary.md`.

| cell | μ(n) RMS rel. err. at measured n < n_b: A mean field / A smoothed / B fluid / B annealed | μ_max err.: A MF / A SM / B fluid / B annealed | 0.5-hit crossing err. (sessions): A / B | E0b log-likelihood: A / B (F2) / B curve with A's criterion | trapped-state mean abs. rel. err.: A / B |
|---|---|---|---|---|---|
| A100 300k (n = 16, 20, 24, 32) | 0.093 / 0.174 / **0.045** / 0.117 | +6.6% / +1.1% / +6.2% / **+0.2%** (turns-based: B +9.9% / +3.6%) | -0.1 / -0.7 | -1.17 / **-0.61** / -1.08 | 0.044 / **0.020** |
| A100 native (24, 48, 64, 80) | 0.027 / 0.032 / **0.026** / 0.037 | +6.1% / +3.3% / +6.0% / +3.3% | +1.1 / **+0.3** | -0.95 / **-0.44** / -1.07 | 0.035 / **0.029** |
| vLLM 300k (16-32) | 0.885 / 1.107 / **0.813** / 1.056 | +11.8% / **+5.6%** / +13.5% / +7.2% | +2.8 / +2.7 | -1.98 / **-1.06** / -2.11 | **0.018** / 0.020 |
| total | | | | -4.11 / **-2.10** / -4.26 | |

Notes on the table:
- **Post-review caveats (2026-10-31).** (i) The μ columns score against μ_sessions. The model's μ is ν/E[T], the quantity the turns-based estimator measures; against it B's μ_max errors are +9.9% / +3.6% (300k, fluid / F1), +9.0% / +6.3% (native), +18.1% / +11.6% (vLLM), and the 300k window is 3.27 (F1) against 3.15 turns-based. The "+0.2%" headline is the most favourable estimator-and-variant pair. (ii) "RMS below n_b" keeps only measured n below the model's own n_b and so drops the points it misses; over all measured n < 300 the B fluid RMS is 0.208 / 0.170 (300k / native, vs sessions) and 0.075 / 0.152 (vs turns-based). Both are in `validation_table.md`. (iii) The trapped-state score averages backlog, token ratio, gap/R and R, which carry about two independent quantities (gap/R = backlog x (P̄+d)/M in the round robin; R and the token ratio both follow from the all-miss composition cost). The predicted token ratio is below all three seeds in 3 of 4 SGLang cells. (iv) "35 of 70 rows inside the 3-seed range" is the 50% an unbiased model attains, and the rows are correlated. (v) F2's exact match to both SGLang brackets is in-sample: its target n_b, noise form and escape law were chosen with those brackets known, and most neighbouring F2 variants also land inside these 0.5x/1.0x-wide brackets.
- The E0b log-likelihood is that of the observed stable/unstable outcomes at the registered multiples, with probabilities floored at 1e-3.
- "Trapped state" means backlog, token ratio, gap/R and R of the six E2 BURST cells.

1. **Accuracy.** On the same measured data, B is at least as accurate as A for the closed curves and the trapped state.
2. **From-empty edge.** B is clearly better on the edges, with log-likelihood -2.10 against -4.11. The gap comes from the criterion, not the curve: A's level-crossing criterion run on B's curve scores -4.26 (`edge_level_crossing` in `extras.py`).
3. **Free parameters.** B has no free parameter. A carries η, the unpinned headroom when admission blocks. η is a judgment informed by the Stage C trap gauges; it does not move the landmarks, but it does move A's trapped R and B_S.
4. **Proofs.** B carries complete proofs, given stated assumptions, for the server lemma, the LRU frontier, the stationary states, the window-opening criterion, the open phase line, the scaling law, the cap rescue and the trapped identities. A proves existence, the trap threshold, the open phase line, the trapped identity and time rescaling. Section 2 grafts A's threshold result into B, where it becomes an exact identity.

**Selection-level fitting, disclosed.** Choosing B over A is one discrete choice between two pre-existing models, made on the measured values of the three cells. Keeping B's F2 edge rather than A's level crossing is a second such choice. Neither changes a parameter. Both were made knowing the targets, as were the original specifications of A and B, which both authors disclose.

**Grafted from A**, re-derived inside B's model so that every number comes from one model:
- the closed-form all-miss threshold (A's R2; T3 below);
- the cost-model independence of the trapped identity, and the good-state gap/R formula (A's R5; T10);
- the Stage C synchronized-start transient at large n (A's `closed_trap_transient`, on B's costs). It predicts the measured μ(300) to +0.7% (300k) and -1.3% (vLLM);
- the static CAPPED-arm drain (A's `capped_drain_from_t0`);
- the registration-consequence rule (A's `predict_cell`);
- A's level-crossing edge, kept only as a secondary prediction. The pool sweep and the H200 E0b test it against F2.

**New in the merge:**
- a burst-trapping probability from the committor of B's own F2 diffusion, so the from-empty edge and the burst basin use one fluctuation model;
- the exact speed corollary of the threshold (T3(c));
- a two-phase drain for the registered RESCUE gate. It corrects B's F4 conclusion that "R4 likely FAILS" (section 3).

## 1. The model (B's, stated briefly; full statement in THEORY_r13_fluid_rigorous.md §1)

**Workload.**
- A session has T = min(Geom(1/15), 60) turns; G_k = P(T ≥ k), E[T] = 14.761, and the turn mix is w_k = G_k/E[T].
- Turn k sends P_k = 2000 + 650(k-1) tokens. The KV after turn k is E_k = P_k + 100.
- A hit prefills x_h = 551 tokens (559 on vLLM); a miss prefills P_k. Turn 1 always misses.
- Tool times are Z ~ Exp(z̄ = 5 s).
- Derived constants: A1 = Σ_k G_{k+1} E_k = 144,960, E[E_T] = 11,045 and Ē = 10,569. At 300k the service-weighted reservation is E_S = 10,809; it is the same on the H200, since E_S is speed-invariant.

**Server.** The calibrated iteration-cost model of `calibration/round6_server_log_fit/calibration.yaml` is used as a fluid server.
- SGLang (separate iterations, prefill priority): the prefill share is p = ν Σ_k w_k t_P,k(h). The decoders R_D solve R_D (1 - p) = ν (d-1) τ_D(R_D). The service time is S_k = t_P,k + R_D/ν. The running reservations are K_run = ν Σ_k w_k E_k S_k.
- vLLM: mixed iterations.

**Memory.** LRU over idle KV. Dead KV of finished sessions is evictable and never reused. The pool is full in steady state, so
  M = K_run(ν, h) + μ D(R; W), with D = A1 E[min(Z+W, R)] + E[E_T] R, h = F_Z(R - W) and μ = ν/E[T].

**Closed system (Little).** n = μ [E[T](W + S̄) + (E[T]-1) z̄]. A queue (W > 0) exists only when K_run = M; this is assumption A4.

**Open system.** Quasi-static: ṅ = λ - μ(n) (A5).

**Fluctuation and composition layers.** These are heuristics: F1 (annealed curve), F2 (from-empty edge), F3 (fresh-cohort burst), F4 (rescue footprint), plus the two new layers of section 3.

## 2. Results

The following are proved, as statements about the deterministic model. Proofs not given here are in THEORY_r13_fluid_rigorous.md §2; the section number is in brackets.

**T1 (fluid server) [§2.1].**
- The decode equation has a unique root for ν < ν_cap(h) = 1/(t̄_P(h) + (d-1)(b+β_c)).
- S_D and K_run are continuous and strictly increasing in ν.
- K_run is strictly decreasing in h and blows up at ν_cap.
- So in separate mode the pool always fills before the GPU saturates.

**T2 (LRU frontier) [§1.3].**
- (a) *Lemma, proved.* The resident idle items are those whose last use is later than a non-decreasing frontier.
- (b) *Assumption MF (Che / mean field), not proved.* In stationarity the frontier is t - R with R deterministic, so an idle item is evicted at idle age exactly R and the memory balance holds. This is a law-of-large-numbers statement for many small objects (Yao et al. prove it as N → ∞; their experiment has about 176 final contexts per pool). Here one session is 3.5% of a 300k pool (about 28 contexts per pool). Validity diagnostic, the free margin at the fluid peak in composition standard deviations, (M - D_live)/(√(CV² n*) Ē): 300k 0.91, vLLM 0.95, 150k 0.01, H200 -1.08 (live demand already exceeds the pool at the peak, h* = 0.72), native 2.5, 600k 1.9. Because h = F_Z(R) is concave, a deterministic R biases hits and μ upward near the peak (Jensen), the sign of the +6% μ_max miss; F1 is a first-order correction for this, and MF is least reliable in the 300k, vLLM, 150k and H200 cells.

**T3 (stationary closed states; all-miss threshold).**
- (a) [B, §2.2] Every R > 0 gives exactly one W = 0 state. The W > 0 states are exactly (h = 0, R = 0, ν = ν_b, W = (n - n_b)/ν_b). μ(n) → μ_b, the model's λ_miss.
- (b) [graft of A's R2; exact] **n_b = ν_b z̄ (1 - 1/E[T]) + M/E_S**, where E_S = Σ_k w_k E_k S_k / Σ_k w_k S_k at (ν_b, 0). That is the sessions in tool calls at the all-miss rate plus one pool's worth of running sessions.
  - *Proof.* By definition K_run(ν_b, 0) = ν_b Σ_k w_k E_k S_k = M, so ν_b S̄ = M/E_S. Little's law at W = 0 gives n_b = ν_b S̄ + ν_b (1 - 1/E[T]) z̄. ∎
  - Values: 32.70 = 4.94 + 27.76 (300k); 94.86 (native); 32.83 (vLLM).
  - This is an **identity** (algebra on K_run(ν_b, 0) = M plus Little's law), and n_b is the **onset of the all-miss branch**; it is the collapse point only when the curve has no fold (Proposition F below; true for every predicted cell).
  - A's derivation reaches the same structure, ν_0 z̄' + (1-η)M/c̄_run + ηM/c̃, giving 33.46 at η → 0 and 33.42 at η = 0.1 (c̄_run = 10,519 against E_S = 10,809), against 32.70 at 300k. A and B share inputs and structure, so this agreement is a consistency check, not independent evidence.
  - Prior work: the pool part M/E_S is MISA-T's capacity-over-session-footprint cap ⌊C_w/k̄_w⌋ (their §4.1). New here are the tool-call term ν_b z̄' and the identification of n_b as the all-miss onset.
- (c) [new; exact] **Under a uniform speed-up s at a fixed pool and workload, n_b(s) = n_b(1) + (s - 1) ν_b(1) z̄ (1 - 1/E[T])**, and the pool part M/E_S does not depend on s.
  - *Proof.* The all-miss state solves K_run(ν, 0) = M, which does not involve z̄. Rescaling time by s (T8(a)) maps it to the same KV with ν multiplied by s and every S_k divided by s. So ν_b(s) = s ν_b(1), and E_S, a ratio of S-weighted sums, is invariant. Substitute into (b). ∎
  - H200 (s = 2.742 from its E0a): n_b = 32.70 + 1.742 × 4.94 = 41.31. Faster hardware moves the cliff **outward** by exactly the extra all-miss sessions held in tool calls, while (T8) the window **narrows**.

**T4 (rise) [§2.3, proof sketch].** μ(n) is increasing near n = 0, and at fixed h throughput increases with population.

**T5 (window opening) [§2.3]; a sufficient condition only.** If f_Z(0+) > 0, then μ_max > μ_b whenever Δ_S := Σ_k w_k E_k |∂S_k/∂h| / Ē > 1/f_Z(0+) (= z̄). Values of Δ_S: 595 s (300k), 6,304 s (native), 679 s (vLLM), 217 s (H200), 124 s (150k), 2,458 s (600k).
- The condition is **not necessary**: gamma tool times of mean 5 s with shapes 2, 4, 16 have f_Z(0+) = 0, yet the model's windows are 3.53, 3.62, 3.75 (no fold). Within the exponential z̄-family it is numerically sharp (window 1.0058 at z̄ = 300 s, 1.0000 at 600 s; Δ_S = 594.6 s independent of z̄). Δ_S/z̄ ranges from 25 to 1,260 over the cells, so it does not discriminate among them.

**T6 (stability; closed-system uniqueness) [§2.4], as restricted by Proposition F.**
- A fixed point of the feedback map is stable if Φ_n' < 1 and unstable if Φ_n' > 1 (Φ_n' = 1 is undetermined).
- Under condition C2 (checked numerically: dΦ/dn between -0.0007 and -0.140 at n = 20-32.3, 300k), stability is equivalent to dn/dR < 0.
- If n(R) is strictly decreasing, every n has exactly one stationary state and μ(n) is continuous.
- **Monotonicity is NOT a general property of the model.** It holds for the exponential tool times of every predicted cell, with a 17-33% margin certified by one scalar inequality (Proposition F, Corollary F.2). For dispersed (decreasing-failure-rate) tool times the closed system folds and is bistable on its own (Corollaries F.1, F.3).

**Proposition F (fold identity) [new, exact; `analysis/theory/merged/fold.py`, `tests/test_theory_r13_freeze.py`].**
Scope: separate mode, the W = 0 branch parametrised by R, any tool-time law with density f = F_Z'. Notation: h = F_Z(R); S_k = t_k(h) + S_D(ν,h), t_k(h) = t^m_k - h·1{k≥2}(t^m_k - t^h_k); S̄ = Σ w_k S_k, S_E = Σ w_k E_k S_k, Ē = Σ w_k E_k; β_P = Σ_{k≥2} w_k(t^m_k - t^h_k), β_E = Σ_{k≥2} w_k E_k(t^m_k - t^h_k), C_E = β_E - Ē β_P; z̄' = E[Z](1 - 1/E[T]); D = A1 E[min(Z,R)] + E[E_T] R, so D' = A1 P(Z>R) + E[E_T]; ρ = -∂_hS_D/(ν∂_νS_D) = β_P/(t̄_P(h) + (d-1)τ_D'(R_D)); n_ν = S̄ + z̄' + ν∂_νS_D; Φ_ν = S_E + νĒ∂_νS_D + D/E[T] > 0. Then

    dn/dR = (ν/Φ_ν)·[ f(R)·I(R) - n_ν D'(R)/E[T] ],
    I = ν∂_νS_D·[C_E + ρ(Ē(S̄+z̄') - S_E - D/E[T])] + β_E(S̄+z̄') - β_P(S_E + D/E[T]).

*Proof (sketch of the algebra; the reviewer's full derivation is the scratch file mathcheck/check9.py).* Differentiate the memory balance M = ν S_E + (ν/E[T]) D(R) and Little's law n = ν(S̄ + z̄') along the branch, as in B's Prop 3, using ∂_h S_k = -1{k≥2}(t^m_k - t^h_k) + ∂_hS_D and dh/dR = f(R). The decode equation R_D(1-p) = ν(d-1)τ_D(R_D) depends on h only through t̄_P(h), which gives -∂_hS_D = ρ·ν∂_νS_D. Eliminating dν/dR, the cross terms in ν∂_νS_D·∂_hS_D cancel and the numerator collects into f·I - n_ν D'/E[T] over the positive denominator Φ_ν. Valid on each side of the decode kink. ∎ Numerical check: the sign of the bracket agrees with the finite difference of n on 400 R points in every cell (100%), and pointwise for a folding mixture (test).

- **F.1 (exact, local).** If f_Z(0+)·I(0+) > n_ν(ν_b,0)·Ē, i.e. the ratio r = f I/(n_ν D'/E[T]) exceeds 1 at R → 0+, then n(R) > n_b for small R, so n_fold := max n(R) > n_b and the closed system has at least three stationary states for n ∈ (n_b, n_fold): the good and the all-miss states both stable, the middle one unstable.
- **F.2 (the registered workload).** max_R r(R) is attained at R → 0+ in every cell: 0.805 (300k), 0.826 (native), 0.784 (H200), 0.749 (H200 decode2), 0.675 (H200 e0a2), 0.781 (Llama), 0.761 (150k), 0.821 (600k). Hence n(R) is strictly decreasing and T6 holds, with margin 17-33%.
- **F.3 (dispersion).** To leading order the R → 0+ ratio is f_Z(0+)[C_E + ρ0(Ē z̄' - c_t)]/Ē with c_t = Σ w_k(E_k - Ē)t^m_k; at 300k ρ0 = 0.881, C_E = 6,259 token·s, c_t = 6,284 token·s, giving 0.835 against the exact 0.805. A fold appears when f_Z(0+)E[Z] ≳ 1/(ρ0(1 - 1/E[T])) ≈ 1.22: none at 1.190, a fold at 1.254 (two-phase mixtures with CV 1.15 and 1.19). Exponential tools (f_Z(0+)E[Z] = 1) stay below the bound for every pool and speed here. Lognormal tools (f_Z(0+) = 0) fold at interior R once CV ≥ 2 (reviewer's check; not in the committed code).
- **Fold bands at 300k (n_b = 32.70):** 0.5·Exp(1 s) + 0.5·Exp(9 s) (CV 1.5): n_fold 34.18; 0.8/1 s + 0.2/21 s (CV 2.5): 38.16; 0.95/1 s + 0.05/81 s (CV 5.0): 44.63; 0.76/0.3 s + 0.24/20 s: 40.35. Lognormal (reviewer's scan): 33.37 / 34.83 / 35.77 at CV 2 / 3 / 3.84 (300k); 95.77 / 97.47 / 98.58 (native, n_b 94.86). The paper cites agent tool times with CV ≈ 3.8 (Continuum), so the fold is a realistic regime.
- **Consequences.** With a fold, n_b is the lower end of the bistable band, not the collapse point; the good branch ends at n_fold; and the cap condition of T9 becomes n1 < c < min(n_u, n_b), because a cap c ∈ (n_b, n_fold) is good from empty but stays all-miss when engaged inside the trap. Bistability is then a closed-system property too; for the registered (exponential) workload it is an open-system property only.
- **Optional real-engine test** (the lead decides; after the freeze): Stage C closed runs with `tool_time_dist: lognormal`, `tool_time_cv: 3` at n ∈ [33, 35] (300k), from empty and from a trapped start; the fluid band (32.70, 34.83) is narrow relative to finite-size noise. A mixture law (a small load-generator change) gives a decisive band up to 44.6.

**T7 (open-system metastability) [§2.5].**
- For λ ∈ (μ_b, μ_max), given a unimodal curve (numerical), ṅ = λ - μ(n) has a stable n1 and an unstable n_u.
- From n > n_u, n grows exactly linearly at λ - μ_b once n ≥ n_b.
- n_u(λ) decreases from n_b to n*. The stationary critical burst n_u - n1 vanishes at μ_max.

**T8 (window scaling law) [§2.6].**
- (a) Exact time rescaling: ω(C/s, z̄) = ω(C, s z̄).
- (b) ω strictly decreases in z̄ and in GPU speed s.
- (c) ω → 1 as s z̄ → ∞.
- (d) An explicit upper bound.
- (e) *Peak accounting identity (requires the solved peak h*, R*, S̄*).* ω ≈ (M/Ē) c_miss / (S̄* + h* z̄ (1-1/E[T]) + R*/E[T]) is within 1% only when evaluated at the model's own solved peak, where it is accounting, not a law. With a rule R* ≈ 3z̄, h* ≈ 0.96 it errs +1.6% (300k), +12.5% (native), -24% (H200), -10% (150k), +9% (600k), +5% (Llama); R*/z̄ ranges from 1.28 (H200) to 6.2 (native).
- The predicted H200 window is 1.95 (A100: 3.46 model, 3.26 measured). The frozen refutation rules (window ≥ 2.4 refutes T8 under uniform scaling; hit(32) < 0.5 refutes T3(c); hit(48) ≥ 0.5 refutes T3(b)/(c)) are in `analysis/theory/merged/scoring.yaml` and `notes/THEORY_r13_scoring.md`.

**T9 (cap rescue; hysteresis) [§2.7; equals A's R8 C1-C3].**
- A FIFO cap c engaged in any state, including the trap, drains the gate and leaves the system good iff n1(λ) < c < n_u(λ), **for fold-free curves**; with a fold (Proposition F) the condition is n1 < c < min(n_u, n_b).
- The upper end n_u is a **quasi-static heuristic**: at 300k n_u = 31.8-32.2 lies within 0.5-0.9 sessions of n_b, where Φ' = 0.56-0.72 slows relaxation 2.3-3.6x and 1/|μ'(n_u)| ≈ 20 s is comparable to one tool cycle, so μ(n) does not determine n_u, b_stat = n_u - n1, the committor's starting points near n_u, or c < n_u. The registered caps 20 and 64 lie far below n_u; for them only n1 < c < n_b matters.
- Releasing the cap afterwards keeps the state good in the fluid limit.
- Registered caps: 20 ∈ (8.5, 32.2) at 1.35× and 20 ∈ (10.4, 31.8) at 1.65× (300k); 64 ∈ (27.8, 90.0) at native 4.0×.

**T10 (trapped round-robin identities) [§2.8 + A's R5].**
- In the all-miss FCFS regime every present session completes one turn per cycle c = Σ_i g(k_i).
- **gap/R_M = Σ_i (P_{k_i} + d)/M** (R_M = M/churn), for **any** cost model, since c cancels.
- Good state: gap/R_M = (z̄ ln 2 + S̄) · churn/M, where churn = λ (L0 + x_h(E[T]-1) + d E[T]) at h → 1 (= λ · 11,058).
- The trapped/good ratio is 300-500×.

## 3. Heuristic layers (not theorems; nothing fitted)

**F1, annealed curve.** At closed population n the KV-demand ratio is θ ~ N(1, CV²/n), with CV² = 0.570 from the turn mix. The curve is averaged over pools M/θ.

**F2, from-empty edge (primary).**
- The demand in session units follows dX = (λ - μ(X)) dt + √(I_D (λ + μ(X))) dW, with I_D = 1.567 from Campbell's theorem.
- P(escape to n_b in 3000 s) = 1 - exp(-H/T), with T the mean first-passage time.
- Secondary (A's criterion, on this curve): the live KV volume of the Poisson session shot noise first reaches D_live(n_u(λ)) early enough for the queue to reach 50 (`edge_level_crossing`, 400 runs per multiple).

**F3 + committor, bursts (new).**
- A burst of b fresh sessions is mapped at its demand peak (turn 12, max_j G_j E_j = 4,331 tokens per session) to X0 = D_live⁻¹(D_live(n1) + b · 4,331). This gives X0 = n_u exactly at F3's deterministic critical burst.
- P(trapped) = q(X0) + (1 - q(X0)) · P_esc(H).
- q is the F2 committor ∫_{n1}^{X0} s / ∫_{n1}^{n_b} s, with s = exp(-∫ 2(λ - μ)/σ²) the scale density (standard splitting probability of a 1-D diffusion).
- P_esc is the F2 background escape before the latest time that still makes the registered window's hit fall below 0.2 (6,344 s for B1).

**F4 + two-phase drain, rescue (new; corrects B's F4).**
- The registered gate pauses sessions at tool-call boundaries and serves the **resume deque before new arrivals**.
- Phase 1: the n_on - c paused mid-session sessions are admitted as slots free up. Throughput is μ_1, the capped rate of resumed sessions: B's composition adjustment, where the footprint is inflated by 1 + 650(k0 - 1)/E_lb and the first resumed turn misses. Phase 1 lasts T1 = (n_on - c)/μ_1.
- Phase 2: the gate holds only fresh arrivals and drains at μ(c) - λ.
- Release time: t_rel = first 10-s tick ≥ max(t_on + c_on + T1 + λ(c_on + T1)/(μ(c) - λ) + 300, t_on + 600).
- B's F4 drained everything at μ_adj - λ. That wrongly requires μ_adj > λ, because fresh arrivals do not carry the inflated footprint. The phase-1 rate affects **when** the gate empties, not **whether**. In the fluid model release happens iff n1 < c < n_u (T9).
- Reported bounds:
  - the F1-annealed phase-1 rate;
  - B's stationary and single-queue bounds;
  - pessimistic "phase 1 collapsed" bounds. **Post-review fix (2026-10-31):** the frozen code uses the all-miss rate of a CLOSED population of c resumed sessions (resumed mix: prompts shifted by 650(k0 - 1), k0 = 7.82 / 7.47; 0.0487 / 0.0495 sessions/s at 1.35x / 1.65x) and of the stationary mix (0.0695), not μ_b = 0.0718 of a population ≥ n_b. The earlier claim "R1 still released even if phase 1 collapses" is **withdrawn**: R1 RESCUED requires a phase-1 rate ≥ 0.052 (1.35x) / 0.070 (1.65x), i.e. 32% / 42% of the fluid rate; with the resumed-mix collapsed rate the release misses 7,200 s at both rates (7,510 s; 9,240 s), and with the stationary-mix rate it is 5,940 s / 7,240 s;
  - the smallest phase-1 rate that still releases by 7,200 s.

## 4. Fitting audit (every parameter, its source, and whether a measured curve point was used)

| parameter | value | source | kind | fitted to | measured μ(n), E0b or E2 outcome used? |
|---|---|---|---|---|---|
| pool M | 300,000; 955,757; 300,000 (18,750 × 16) | job scripts; SGLang server log of the native cell; vLLM block count | input | - | no |
| workload L0, Δ, d, mean T, cap, z̄, law | 2000, 550, 100, 15, 60, 5 s, Exp | `configs/agentload_e2_burst.yaml` (read by the spec loader) | protocol | - | no |
| hit prefill x_h | 551 (vLLM 559) | Δ + 1, the last decoded token having no KV (+ 8, the mean unfilled 16-token block); equals the Stage C fact "cached = prompt - 551" | structural | - | no |
| iteration costs a, f, b, c_d, c_p, chunk, norm | 9.24 ms, 1.26 ms, 62.6 µs, 0.31 ms, 2.24 ns, 8192, 8192 | `calibration/round6_server_log_fit/calibration.yaml` | input | SGLang server-log iteration timing only (jobs 17060165, 17062103-05), never μ(n), hits, E0b or E2 | no; but the 300k Stage C jobs' **server logs** are among its data (same runs, different observable) |
| engine mode | separate (SGLang); mixed (vLLM) | engine design | structural | - | no |
| vLLM speed factor | 0.9183 (costs ÷) | vLLM E0a, 10,349 tok/s | **fitted** (1 parameter) | E0a all-miss token rate (so vLLM's λ_miss is not independent; λ_miss in turns is then +2.0%) | no |
| λ_ref | 0.071534; 0.0717974; 0.065663 | each cell's E0a `lambda_miss_turns_based` | protocol | - | no; it places the E0b/E2 rates where the experiments put them (mult × λ_ref) |
| E0b multiples, H = 3000 s; E2 burst 200 in 60 s at 1200 s, window [5700, 8700) s | | the registered protocols | protocol | - | no |
| CAPPED-arm caps 20 / 64 / 20 | | the registrations | protocol | - | the cap **values** were chosen by the registration rule from the measured Stage C curves; used here only as the experimental condition |
| F1 CV² | 0.570 | workload turn mix | derived | - | no |
| F2 I_D, target, horizon | 1.567; n_b; 3000 s | workload (Campbell); model; E0b protocol | derived/protocol | - | no; B chose F2 knowing the 300k and native brackets (disclosed by B) |
| F3 / committor peak KV | 4,331 tokens at turn 12 | workload | derived | - | no |
| F4 inflation k0 | 7.8 / 7.5 / 6.5 | the model's trapped composition at t_on | derived | - | no (no rescue data exist) |
| grids | n step 0.5-1.5; 41 θ nodes; R grid 1,000 points; 400 Monte Carlo runs per multiple (secondary edge) | numerics | - | - | no |

Blind cells:
- **H200:** one fitted factor, s_H = 2.742, from its E0a tokens (29,866).
  - `decode2` assumes a decode/memory-side factor of 2.0 and fits the compute side.
  - `e0a2` fits a second parameter to the H200 E0a POP-64/POP-32 ratio 1.046: decode side 1.27, compute side 3.23. The model under-predicts the A100's POP-64 ratio by 1.6 points (1.001 against 1.017), so this variant over-attributes the ratio to slow overheads. It is a pessimistic bracket. Corrected for that bias, the ratio points to a decode-side factor of about 2.0, which is `decode2`.
- **Llama:** architecture ratios, with no data.
- **Pools 150k and 600k:** zero fitted parameters.

**No measured μ(n) point, E0b outcome or E2 outcome enters any prediction.** Every predictions JSON carries `audit`, `fitted_parameters`, `uses_measured_mu_curve: false` and `uses_e0b_or_e2_outcome: false`.

## 5. Validation (predicted vs measured)

Full table: `results/theory/merged/validation_table.md`. The excerpt below covers the closed curves, the edge, the trapped and good states and the capped drains. "In range" means within the three seeds' range.

**Closed curve, all-miss level, window, edge**

| cell | λ_miss (turns) | μ_max fluid / F1 (meas.) | peak n fluid / F1 (meas., flat top) | 0.5-hit n (meas.) | window fluid / F1 (meas.) | μ(300), Stage C sync start (meas.) | E0b bracket (meas.) |
|---|---|---|---|---|---|---|---|
| A100 300k | 0.0718 (0.0715, +0.3%) | 0.2478 / 0.2337 (0.2333): +6.2% / +0.2% | 24.9 / 24 (24; 20-24) | 31.5 (32.2) | 3.46 / 3.27 (3.26) | 0.1085 (0.1078, +0.7%) | [2.0, 2.5] ([2.0, 2.5]), 50% edge 2.34 |
| A100 native | 0.0718 (0.0718, 0.0%) | 0.5076 / 0.4949 (0.4789): +6.0% / +3.3% | 74.1 / 69.5 (64; 64-80) | 93.7 (93.4) | 7.07 / 6.89 (6.67) | 0.1108 (0.1006, +10%; not trapped from t = 0) | [5.5, 6.5] ([5.5, 6.5]), 6.26 |
| vLLM 300k | 0.0670 (0.0657, +2.0%; tokens fitted) | 0.2490 / 0.2353 (0.2194): +13.5% / +7.2% **miss** | 24.9 / 24 (20; 20-24) | 31.8 (29.1) **miss** | 3.79 / 3.58 (3.34) | 0.1036 (0.1050, -1.3%) | [2.5, 3.0] ([2.0, 2.5]) **one step high** |

Pointwise, 300k, measured against fluid (annealed):
- n = 16: 0.1756 vs 0.1765 (0.1765);
- n = 20: 0.2239 vs 0.2161 (0.2139);
- n = 24: 0.2333 vs 0.2462 (0.2337);
- n = 32: 0.1150 vs 0.1078 (0.1415); hit 0.505 vs 0.371 (0.357).

Native, measured against fluid (annealed):
- n = 64: 0.4789 vs 0.4882 (0.4867);
- n = 80: 0.4772 vs 0.4871 (0.4499);
- n = 96: 0.1228 vs 0.0737 (0.1688).

The measured sessions-based μ(48) and μ(96) at 300k (0.049, 0.061) lie below λ_miss. That is a synchronized-start artefact the model does not reproduce: its sync-start values are 0.071 and 0.078, where it is not valid because those populations are not trapped from t = 0.

**E2 (BURST trapped, NOBURST good, CAPPED drain)**

| cell, rate | backlog pred. (meas.) | token rate / E0a pred. (meas.) | gap/R pred. (meas.) | R_M s pred. (meas.) | post-burst minimum pred. (meas.) | NOBURST hit; n1 pred. (meas.) | NOBURST gap/R pred. (meas.) | CAPPED drain s pred. (meas.) |
|---|---|---|---|---|---|---|---|---|
| 300k 1.35× | 215 (200-232) in range | 1.006 (1.009-1.025) | 6.93 (6.35-6.92) | 26.6 (25.8-26.2) | 153 (135-147) | 0.932 (0.930-0.934); 8.5 (7.9-9.7) | 0.017 (0.016-0.020) | 1576 (1547-1904) in range |
| 300k 1.65× | 304 (283-332) in range | 1.016 (1.025-1.029) | 8.98 (8.18-9.67) in range | 26.3 (25.6-25.7) | 174 (162-172) | 0.932 (0.921-0.934); 10.4 (10.9-11.8) | 0.021 (0.022-0.028) | 1941 (2021-2693) -15% |
| native 2.5× | 565 (557-601) in range | 1.067 (1.074-1.078) | 4.45 (4.14-4.57) in range | 79.7 (77.5-77.9) | 206 (155-168) **+28%** | 0.932 (0.929-0.935); 16.3 (15.6-18.5) | 0.010 (0.010-0.012) | 493 (512-583) -10% |
| native 4.0× | 1089 (1098-1139) -2.5% | 1.079 (1.106-1.124) -3% | 7.06 (6.68-6.96) +3% | 78.6 (74.2-75.4) | 233 (202-231) | 0.932 (0.929-0.935); 27.8 (28.2-33.6) | 0.017 (0.018-0.022) | 815 (837-937) -9% |
| vLLM 1.35× | 206 (203-227) in range | 0.992 (0.997-1.007) | 6.64 (6.51-6.72) in range | 28.9 (28.5-28.8) | - | - | - | - |
| vLLM 1.65× | 288 (277-309) in range | 1.002 (1.025-1.031) | 8.52 (8.05-8.63) in range | 28.6 (27.8-28.0) | - | - | - | - |

**Misses, stated plainly.**
1. The vLLM cliff is earlier and steeper than predicted: crossing 29.1 against 31.8, μ(28) 0.119 against 0.225. Its post-cliff plateau below λ_miss is not reproduced, and its E0b bracket is predicted one grid step high.
2. The fluid μ_max is 6% high on both SGLang cells. F1 brings 300k to +0.2% and native to +3.3%, but F1 worsens the 300k n = 32 point (+23%).
3. The native peak location (fluid 74, F1 69.5) is above the measured argmax of 64, though inside the flat top 64-80.
4. The trapped token ratio is low by 1-3 points, and by 3 points at native 4.0×. R_M is 1-5% high. The native post-burst minimum is 28% high at 2.5×.
5. CAPPED drains are 9-15% fast.
6. μ(300) at the native pool is +10%; the synchronized-start model is not valid there.
7. No convergence theorem links the engine to the fluid limit.

## 6. Blind predictions (out of sample; to be frozen before any H200, Llama, pool-sweep, B1 or R1/R4 result is read)

Machine-readable versions are in `results/theory/merged/<spec>.json`; the generated tables are in `summary.md`. Every value comes from `analysis/theory/predict.py` at the code hashes recorded in each JSON.

| cell | λ_miss (turns) | n_b | peak n fluid / F1 | μ_max fluid / F1 | hit at peak | 0.5-hit n | window fluid / F1 | edge F2 (A's criterion) | P(unstable) F2 at 1.25, 1.5, 1.75, 2.0× | registration consequence |
|---|---|---|---|---|---|---|---|---|---|---|
| H200, uniform (primary) | 0.1933 | 41.3 | 32.8 / 32.5 | 0.378 / 0.371 | 0.67 | 37.3 | 1.95 / 1.92 | 1.39 (1.57) | 0.19, 0.75, 0.98, 1.00 | hi 1.25; points 1.10, 1.15; cap 32 |
| H200, decode side 2.0 | 0.1933 | 41.5 | 32.4 / 32.0 | 0.357 / 0.352 | 0.68 | 37.0 | 1.84 / 1.82 | 1.34 (1.52) | 0.28, 0.85, 0.99, 1.00 | hi 1.25; 1.10, 1.15; cap 28 |
| H200, two E0a parameters (pessimistic) | 0.1933 | 41.7 | 31.9 / 32.0 | 0.322 / 0.320 | 0.68 | 36.4 | 1.66 / 1.65 | 1.24 (1.42) | 0.52, 0.95, 1.00, 1.00 | no stable grid multiple; cap 28 |
| Llama-3.1-8B (a priori; multiples of its model λ_miss) | 0.0619 | 32.0 | 24.3 / 23.0 | 0.222 / 0.208 | 0.91 | 30.9 | 3.59 / 3.37 | 2.46 (2.73) | 0.00, 0.00, 0.02, 0.09 (2.5×: 0.55) | hi 2.0; 1.35, 1.65; cap 24 |
| A100 pool 150k (× 0.071534) | 0.0688 | 18.3 | 14.0 / 14.0 | 0.141 / 0.134 | 0.80 | 16.9 | 1.97 / 1.87 | **1.09** (1.47) | 1.1×: 0.51; 1.25×: 0.76; 1.5×: 0.96 | **no stable grid multiple under F2**; cap 12 |
| A100 pool 600k (× 0.071534) | 0.0718 | 61.2 | 47.0 / 45.0 | 0.409 / 0.391 | 0.92 | 60.0 | 5.72 / 5.47 | 4.53 (4.82) | 4.0×: 0.11; 4.5×: 0.47; 5.0×: 0.85; 5.5×: 0.98 | hi 4.5; 2.15, 3.35; cap 40 |

Closed-curve points (sessions/s; F1 in brackets):

- **H200 (primary):**
  - n = 16: 0.212 (0.212), hit 0.93;
  - n = 20: 0.264 (0.264);
  - n = 24: 0.314 (0.312);
  - n = 28: 0.354 (0.351);
  - n = 32: 0.377 (0.371), hit 0.70;
  - n = 40: 0.257 (0.278), hit 0.27;
  - n = 48: 0.197 (0.201), hit 0;
  - n = 96: 0.197;
  - n = 300: Stage C synchronized start 0.221 (stationary 0.197).
- **Pool 150k:**
  - n = 8: 0.091; 10: 0.113; 12: 0.133 (0.128); 14: 0.141 (0.134); 16: 0.129 (0.124); 20: 0.069 (0.085); 24: 0.069 (0.071);
  - n = 300: sync 0.105.
- **Pool 600k:**
  - n = 32: 0.322; 40: 0.379 (0.376); 48: 0.408 (0.383); 56: 0.285 (0.267); 64: 0.073 (0.121); 80: 0.073;
  - n = 300: sync 0.110.
- **Llama:**
  - n = 16: 0.166; 20: 0.199 (0.197); 24: 0.222 (0.208); 28: 0.189 (0.174); 32: 0.063 (0.116); 40: 0.062.

Falsifiable statements from the theorems:
- **H200 (T8, T3(c)):** the window shrinks to about 1.7-1.95 × λ_ref from 3.26. The cliff moves **out** to n_b ≈ 41 (A100: 32.7), with the peak at n ≈ 32-33 and a hit fraction of only about 0.67-0.70 at the peak. The from-empty edge falls to 1.24-1.39× under F2 (1.42-1.57× under A's criterion).
- **Pool sweep (T8(e)):** the window grows with the pool (1.97, 3.46, 5.72 at 150k, 300k, 600k). The cliff n_b = ν_b z̄' + M/E_S grows almost linearly in M (18.3, 32.7, 61.2).
- **150k edge: F2 and A's criterion disagree.** F2 says the 150k cell is unstable from empty at every grid multiple (edge 1.09×). A's criterion says 1.47×. The pool-sweep E0b decides between the two fluctuation heuristics.

**B1 (300k, 1.65×, bursts of 100 and 25 in 60 s at 1200 s)**
- Deterministic critical burst: 53.4 (stationary-composition 21.3); n1 = 10.4, n_u = 31.8.
- Committor P(STUCK) per seed: 0.042 for 25, 0.139 for 40, 0.547 for 50, 1.000 for ≥ 60 and for 100.
- Background escape before 6,344 s: 0.032.
- **Predicted verdict: PASS** (100 STUCK 3/3, 25 GOOD), P(PASS) = 0.995.

**R1 (300k, cap 20 at 1800 s, release after 300 s with both queues empty, deadline 7200 s)**

| rate | n in system at t_on | footprint inflation | phase-1 rate fluid / F1 | release two-phase fluid / F1 | bounds: B stationary / B single-queue / phase 1 collapsed | phase-1 rate needed (fraction of fluid) | P(relapse) |
|---|---|---|---|---|---|---|---|
| 1.35× | 161 | 1.42 | 0.163 / 0.154 | **3,830 / 3,920 s** | 3,441 / 4,432 / 5,820 | 0.052 (0.32) | 0.002 |
| 1.65× | 176 | 1.40 | 0.167 / 0.158 | **4,360 / 4,480 s** | 3,890 / 5,568 / 7,080 | 0.070 (0.42) | 0.025 |

Predicted: RESCUED at both rates. Release happens even if phase 1 collapses to the all-miss rate.

**R4 (native 4.0×, cap 64 at 2100 s)**

| n in system at t_on | inflation | phase-1 rate fluid / F1 | release two-phase fluid / F1 | bounds: stationary / single-queue / collapsed | phase-1 rate needed | P(relapse) |
|---|---|---|---|---|---|---|
| 327 | 1.34 | 0.282 / 0.257 | **5,040 / 5,250 s** | 4,072 / never / 11,420 | 0.144 (0.51 of fluid) | ≈ 0 |

Predicted: RESCUED, with release about 5,000-5,300 s. This is the least robust prediction:
- The 64 resumed sessions act like an effective 85.6 sessions against n_b = 94.9.
- If finite-size fluctuations drive phase 1 below about half its fluid rate, the release misses 7,200 s.
- B's original "R4 likely FAILS" came from the single-queue bound that this merge corrects (section 3).

## 7. Weaknesses (beyond the misses in section 5)

1. **Every proved statement is about the deterministic model.** No limit theorem links the engine or the simulator to it.
   - T6 and T7 rest on numerical monotonicity and unimodality.
   - A2a (no prefill queueing): a probe adding an M/G/1 prefill wait W_q = ν E[t_P²]/(2(1 - p)) (at 1x and 2x) to the idle time and the lifetime keeps n(R) monotone at 150k, 300k and native; μ_max falls 0.1-5% (300k: 0.2478 → 0.2441 / 0.2413), so A2a hides no fold and explains at most half of the +6% bias.
   - A2c (no retraction/preemption): SGLang retracts decode requests under memory pressure and re-prefills them; a candidate cause of the 1-3 point trapped token-ratio deficit (test: retract counts in the server logs).
   - Lemma 1's "the pool fills before the GPU saturates" ignores max_running = 256; it holds for M < 256·E_S ≈ 2.8M tokens (all cells qualify).
   - The fluid release rule ignores re-queueing just after the gate empties (active = cap while arrivals continue), which restarts the 300 s hold and delays R1/R4 release beyond the fluid tick.
   - Assumption MF (T2(b)) does not concentrate in the 300k, vLLM, 150k and H200 cells (margin ≤ 1 s.d.).
2. **F1, F2, F3, F4 and the two new layers are heuristics.**
   - F2's success on the two SGLang brackets was obtained by an author who knew them.
   - The committor maps a time-dependent cohort onto a 1-D diffusion at its peak.
   - The two-phase drain uses B's footprint inflation and one forced miss, and ignores the transition between the phases.
3. **Uncalibrated or partly calibrated costs.**
   - The H200 predictions rest on cost scaling from one or two E0a numbers; the three variants span window 1.66-1.95 and edge 1.24-1.39×.
   - The Llama costs are roofline ratios with no data.
   - The vLLM model has no block-level eviction, preemption or recompute.
4. **Provenance of the 300k comparison.** The cost model was fitted to iteration timings from the server logs of the 300k Stage C runs. So the 300k comparison is out of sample in its target but not in its data source. The native, vLLM and open-system comparisons are cleaner.
5. **Model selection on the validation cells.** The choice of B (and of F2 over A's criterion) used the validation cells, as disclosed in section 0.

## 8. Position against prior work

This section condenses A §6 and B §6. Yao et al. was read in full by both. MISA-T was read in sections by B. The other works are known from abstracts and search summaries only.

**Yao, Gao, Lyu, Grosof, Simchi-Levi (arXiv 2609.02027).**
- Their model: a Che-type characteristic time for multi-turn LRU, with exogenous i.i.d. inter-turn gaps (their Assumption B.4). Rate and memory scale together, so compute never binds (their Remark B.6). The characteristic-time equation is strictly increasing, so the fixed point is unique. They model no server, queue or running KV.
- Yao et al.'s equation already contains the dead-content term λ0 E[B] t; ours equals theirs at K_run = 0, W = 0 (term for term: E[E_T] = E[B], A1 = A_H, E[min(Z,R)] = ∫_0^R F̄). Their experiments use gap = max(exponential clock, decode completion).
- What this model adds (post-review wording):
  - (i) running reservations K_run(ν, h) in a co-located engine, which Yao et al. exclude by assuming prefill/decode disaggregation (their Remark B.1). Their size depends on h because misses starve decode under prefill priority (Δ_S);
  - (ii) a server and a closed population (Lemma 1, Little's law) in place of an exogenous arrival rate;
  - (iii) the memory-gated all-miss branch (A4). On it the queue, not the tool time, sets the reuse gap (T10). **On every partially hitting state the reuse gap remains the exogenous tool time**: under A4, W > 0 forces K_run = M, hence R = 0 and h = 0. Yao et al. note that overload latency would affect inter-arrival times (Remark B.6) and set it aside by scaling; the loop closed here runs through service time and reserved KV, not through the gap. (A genuinely endogenous-gap closure with W > 0 and h > 0 is approach A's η-regime, which the merge did not adopt.)
  - Recommendation for paper/ (lead): replace "so that inter-turn gaps depend on load" with "so that the KV held by running requests, and their service time, depend on the hit rate".
- Together these turn the unique fixed point into a predicted thrashing curve with a rise, a peak, a cliff at the closed-form n_b (T3) and an all-miss branch.
- The new consequences that are proved within the model:
  - the speed laws T3(c) and T8;
  - the opening criterion T5;
  - the cap condition T9;
  - the trapped identity T10;
  - Proposition F: the exact fold criterion, which says when the closed system itself is bistable (dispersed tool times) and certifies uniqueness for the registered workload.

**MISA-T (hong2026misat, arXiv 2608.11152; full text read by the reviewer).** Its §2.5 describes the eviction / cold-prefill / queue loop in words, including lengthened session overlap (the service-time swelling that drives this model's cliff); §4.1 gives an informal prefill-saturation bound F/E[L_r - H_r] and a baseline cap K_w = ⌊C_w/k̄_w⌋ (capacity over a reference session KV length), which is the pool part M/E_S of T3(b). It measures the collapse empirically (hit rate 92.4% → 4.5%, throughput -52.5%) and contracts its cap on a confirmed hit-rate decline or persistent queue before recovering gradually, an engineered rescue. It has no equilibria, hysteresis, burst basin or rescue condition. Claimed here relative to it: the rescue condition and hysteresis (T9), and the quantified loop (T5, T8, Proposition F).

**Che approximation; Denning; Courtois (1975).**
- The Che approximation enters as Assumption MF (T2(b)), a mean-field step that is not exact at these pool sizes (diagnostic in T2).
- The closed curve is a Denning thrashing curve. T7 is the classical decomposition argument (Courtois) applied to a predicted μ(n); with dispersed tool times the closed system itself folds (Proposition F). (The project has read only a search-result summary of Courtois, so no finer contrast is claimed.)

**Metastable-failure models.** These are Isaacs et al. (HotOS '25), Habibi et al. (SRDS '24), Farahbakhsh et al. (HotNets '25) and Bronson et al.
- They use retry or timeout sustaining effects and generic CTMC or token-flow models.
- Here the sustaining effect is cache loss. The basin boundary is a KV demand level. The thresholds and rates are predicted from first principles and checked against real engines with zero fitted parameters on the SGLang cells.

**Not claimed.** Novelty of an endogenous-gap Che closure in the general caching literature is not claimed: neither derivation searched it.

## 9. Files

- `analysis/theory/predict.py`, `analysis/theory/validate.py`
- `analysis/theory/merged/{__init__,spec,extras,summarize,plots}.py`
- `analysis/theory/cells/*.yaml` (12 specs)
- `tests/test_theory_predict.py`
- `results/theory/merged/` (git-ignored; force-add):
  - `a100_300k.json`, `a100_native.json`, `vllm_300k.json`;
  - `h200_300k.json`, `h200_300k_decode2.json`, `h200_300k_e0a2.json`, `llama31_8b_300k.json`, `a100_pool150k.json`, `a100_pool600k.json`;
  - `b1_basin_300k.json`, `r1_rescue_300k.json`, `r4_rescue_native.json`;
  - `validation_table.{csv,md}`, `validation.json`, `summary.md`, stdout logs.
- `figures/theory/merged_validation.{png,pdf}`, `figures/theory/merged_blind.{png,pdf}`

## 10. Post-review changes before the freeze (2026-10-31, 01:45-02:30 CDT)

Two adversarial reviews (a math/novelty check and a freeze/leakage audit; their scratch scripts are under the session scratchpad `theory/mathcheck/` and `theory/adv2/`) found the issues below. Each fix was verified by re-running the reviewer's check against the changed code.

- **Code changes that move frozen numbers** (MODEL_VERSION r13-merged-2):
  - `extras.rescue_two_phase`: the collapsed phase-1 bound is the closed-cap all-miss rate (resumed mix and stationary mix), not μ_b (P6). R1 "released even if phase 1 collapses" is withdrawn.
  - `extras.burst_trap_probability`: the burst cohort's per-turn cycle uses the model's S̄ at n1 (1.33 s at 1.65x), not a hard-coded 1.5 s; `predict.py` no longer falls back to hit 0.93 when computing the stuck-by time. B1 numbers change in the third decimal.
- **New outputs (no change to existing numbers):** the F2 escape probability as a function of absolute λ (sessions/s) and the edge in sessions/s; `fold_identity` (Proposition F margin) in every separate-mode JSON; a frozen `scoring` block (`analysis/theory/merged/scoring.yaml`) in every JSON; two H200 ratio-fit sensitivity variants (`h200_300k_ratiofit`, `h200_300k_lamratiofit`); a Llama speed-conditional table (`analysis/theory/merged/speed_table.py`, `results/theory/merged/llama31_8b_300k_speed_table.json`).
- **Validation table:** turns-based columns for every μ row, μ_max and the window; all-points RMS with both estimators.
- **Theory text:** Proposition F added and T6 restricted (P1); T2 split into a lemma and Assumption MF (P4); T5 marked sufficient only (P5); T8(e) renamed an accounting identity (P10); T3(b) called an identity, A's η values corrected, MISA-T credited (P8, P11); T9's upper bound labelled quasi-static (P9); the "dead KV" and "endogenous gap" novelty claims withdrawn and replaced (P2, P3); the Courtois contrast deleted (P7); scoring caveats (P12); hidden assumptions listed (P13).
- **Tests:** `tests/test_theory_r13_freeze.py`: a real leakage guard (monkeypatched `open` / `os.path.exists` raising on any results/nova or out-of-sample path while `predict` runs on blind specs), Proposition F checks, and the corrected rescue bound.
- **Not changed:** the model, its parameters, F1/F2/F3, and every closed-curve, edge and E2 prediction.
