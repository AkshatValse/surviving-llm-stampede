# Round 13, approach A: Che characteristic time with endogenous inter-turn gaps

Written 2026-10-30/31 (23:00-01:00 CDT) on branch `r13/theory` (worktree base `582c2a6`), by the theory agent for approach A. Nothing here is committed by this agent. Code: `analysis/theory/che_endogenous/` (`model.py`, `open_system.py`, `measured.py`, `run_che.py`, `plots.py`); test: `tests/test_theory_che_endogenous.py` (10 tests, pass); outputs: `results/theory/che_endogenous/` (`validation.json`, `predictions.json`, `curves_*.csv`, `scaling.csv`, `sensitivity_eta.json`, `meta.json` with the code SHA-256s); figures: `figures/theory/che_*.png`. Reproduce: `PYTHONPATH="src;." python -m analysis.theory.che_endogenous.run_che` (about 14 min on the PC, all seeds fixed), then `python -m analysis.theory.che_endogenous.plots`.

**Blindness of this work.** I read the committed Stage C, E0a, E0b and E2 data of the three measured cells (A100 300k, A100 native, vLLM 300k), the E2 request logs (to rerun the frozen `loopvars` script, below) and the r11 prediction notes. I did not ssh to Nova and did not open anything of the H200 cell, the Llama cell, B1, R1/R4 or the pool sweep (no `results/nova` dir with h200, llama31, r11, b100/b25, e0bfresh, lpminf or rescue in its name; no Nova logs). The out-of-sample numbers in section 5 are therefore blind on my side, as of the time this file was written; they are blind in the project's sense only once they are committed and pushed before the corresponding results are read (the lead's tag `r13-theory-pred`).

## 0. Summary

A mean-field model with **no parameter fitted to any μ(n) curve** reproduces the closed thrashing curve, the all-miss capacity, the trapped state and the from-empty edge of the two SGLang cells; it misses the shape of vLLM's cliff. Its inputs are the workload, the pool size, and the iteration-time cost model fitted to SGLang server-log batch timing only (`calibration/round6_server_log_fit/`); for vLLM one time-scale factor is fitted to vLLM's own E0a token rate.

- **Closed curve, A100 300k:** predicted peak 0.236 sessions/s at n ≈ 24-25 (measured 0.233 at 24), 0.5-hit crossing 31.2-32.1 (measured 32.2), λ_miss 0.0716 (measured 0.0715), μ(16) 0.1765 (0.1756). **Native pool:** peak 0.495-0.508 at n ≈ 69-74 (0.479 at 64, 0.477 at 80), crossing 93.9-94.5 (93.4). The measured μ(300) = 0.108, a "synchronized-start transient", is predicted to 0.1% (0.1079) by the trapped-state fluid.
- **Trapped state (E2 BURST arms):** backlog, backlog slope, session rate, uncached-token ratio and the loopvars ratio gap/R are predicted within the seed spread or within ~10% in all four SGLang cells (table in section 4). New exact identity: in the trap, **gap/R = (total context of the sessions in the system)/M**.
- **The closed system is not bistable** (one fixed point at every n, for every tool-time law from exponential to deterministic and every headroom η tested), but near-critical at the cliff (slope of the fixed-point map up to ≈ 0.7). The trapped state exists exactly for n ≥ **n_trap = λ_miss E[T] z̄' + (1-η)M/c̄_run + ηM/c̃ ≈ λ_miss E[T] z̄' + M/c̄** (closed form, exact in the model): the sessions in tool calls at the all-miss rate plus one pool's worth of sessions. Metastability is an open-system property: a stable good node, a saddle N2(λ), and a trapped attractor at infinity.
- **From-empty edge as a level-crossing problem** (live KV volume, an M/G/∞ shot noise, reaching the saddle volume N2(λ)E_lb): 50% edge 2.61 × λ_ref at 300k (measured bracket 2.0-2.5), 6.59 × native (5.5-6.5), 2.76 × vLLM (2.0-2.5; partial miss).
- **Window scaling law:** the window depends on hardware speed s and tool time z̄ only through s·z̄ (exact time-rescaling invariance), so faster hardware at a fixed pool narrows it (3.47 → 2.01 for 2.66× speed at 300k) and a larger pool widens it toward the compute bound τ̄_miss/τ̄_hit ≈ 8.8 (75k: 1.31, 150k: 2.06, 300k: 3.47, 600k: 5.72, 955k: 7.10, 1.5M: 7.89).
- **Blind predictions (section 5):** H200 300k: peak moves OUT to n ≈ 32-34 in a partial-hit regime (hit ≈ 0.70 at the peak), μ_max ≈ 0.37-0.38 (1.9-2.0 × λ_ref), crossing ≈ 37, window ≈ 1.9, E0b edge ≈ 1.56 ×; Llama-3.1-8B: λ_miss ≈ 0.061, peak ≈ 0.21 at 24, edge ≈ 2.8 ×; pool 150k: peak 0.137 at 14, edge ≈ 1.45 ×; pool 600k: peak ≈ 0.39-0.41 at 45-48, edge ≈ 4.8 ×; B1: 100 STUCK (P = 1.00), 25 GOOD (P(stuck) = 0.055); R1/R4: rescued, release ≈ 3,400 / 3,830 / 4,020 s.

## 1. Model

**Workload** (`configs/agentload_e2_burst.yaml`): T = min(Geom(1/15), 60), E[T] = 14.761; turn-k prompt L_k = 2000 + 650(k-1); a hit prefills δ = 551 tokens, a miss L_k; d = 100 decoded tokens per turn; after turn k the radix cache holds c_k = L_k + d - 1 tokens of the session; a running turn-k request pins c^run_k ≈ L_k + d/2. Tool time Z ~ Exp(z̄ = 5 s) (gamma laws for the sensitivity). Turn mix π_k = P(T ≥ k)/E[T]; completions followed by another turn π→_k = P(T ≥ k+1)/E[T]; z̄' = z̄(1 - 1/E[T]) is the mean tool time per turn. E[c_T] = 11,044 (final KV), c̄_run = 10,519, c̃ = Σπ→c + E[c_T]/E[T] = mean KV per turn completion.

**Pool:** M tokens; LRU over unpinned KV; dead KV of finished sessions is not freed (the engines do not know a session ended), so the pool is always full in steady state and a Che characteristic time R always exists.

**Server (SGLang: FCFS, separate prefill and decode iterations, prefill priority).** Iteration costs from the server-log fit: τ_P(u, p) = ⌈u/8192⌉ a_f + max(⌈u/8192⌉ a_fl, κu) + β(up + u²/2), τ_D(B) = a_f + max(a_fl, κB) + γB c̄/8192 (a_f = 9.24 ms, a_fl = 1.26 ms, κ = 62.6 µs, γ = 0.31 ms, β = 2.24e-9 s). τ̄_P(h) = Σ_k π_k [h τ_P(δ, L_k - δ) + (1-h) τ_P(L_k, 0)] (turn 1 always the miss term).

- Unsaturated (U, queue empty, W = 0): GPU time per second ν τ̄_P(h) + r_D τ_D(B) = 1, and each request needs D = 99 decode iterations while all B in flight advance together (r_D B = Dν). Hence **B = Dν τ_D(B)/(1 - ν τ̄_P(h))** (linear in B on each branch of τ_D), running time S = τ̄_P(h) + B/ν, and Little: **n = ν(z̄' + S)**. Prefill priority makes misses starve decode, so S and the pinned KV A = (B + ν τ̄_P) c̄_run swell when misses rise.
- Saturated (S): pinned KV cannot exceed (1-η)M (η = unpinned headroom when admission is memory-blocked). If the U solution would pin more, B = B_S with (B_S + ν τ̄_P) c̄_run = (1-η)M, **ν = ν_S(h) = [τ̄_P(h) + D τ_D(B_S)/B_S]⁻¹**, and the remaining sessions queue: **W = [n - ν(z̄' + S)]/ν**. U and S join continuously.
- vLLM (mixed batching): every iteration advances all B and carries the prefill tokens, so B = (D+1)ν a/(1 - ν w̄_p - (D+1)ν b) with w̄_p the per-request prefill compute; same memory and Che parts.

**Che equation (endogenous gap):**

  M - A = ν Σ_k π→_k c_k E[min(Z + W, R)] + ν (E[c_T]/E[T]) R,

i.e. idle KV of live sessions is resident while its age is below R, and the age at reuse is the tool time **plus the queue wait W** (which depends on h through the server); dead KV stays R after the last turn.

**Fixed-point map:** h' = Φ_n(h) = P(Z + W_n(h) < R_n(h)); μ(n) = ν/E[T]; all-turn hit fraction h(1 - 1/E[T]).

**Headroom η:** an engine-behaviour parameter, not derived. I use η = 0.10. Stage C's trap gauges (mean evictable 34k-71k of 300k at n = 96 and 48; 17-22 running requests) suggest 0.1-0.25; SGLang's greedy admission and the decode-phase usage p50 0.97 suggest ~0.03. `sensitivity_eta.json`: η ∈ {0.03, 0.10, 0.25} changes no landmark of the curve by more than 0.2% (300k and native; one fixed point at every n for all three values); it moves only the trapped-state R_che (0.8 / 2.7 / 6.8 s at 300k; measured survival 2.9-6.3 s) and B_S (26.7 / 24.8 / 20.5; measured running 17-22).

**Live-volume fluctuation (finite n).** In the good state sessions interact only through batching, so the live KV volume V of n sessions is a sum of n roughly independent slot processes: mean n E_lb, relative SD CV/√n with E_lb = 10,530 and CV = 0.753 computed from the workload (time-weighted KV per session, `Workload.lb_moments`). The "smoothed" curve averages the mean-field throughput over V (equivalently over M/(1+ε), ε ~ N(0, CV²/n)), quasi-statically. In the open good state V is M/G/∞ shot noise with mean λE[∫c dt] and variance λE[∫c² dt] (Campbell); its integrated correlation time is ≈ 119 s at 2 × λ_ref.

**Trapped state (fluid).** With a long FCFS queue every present session gets one turn per round and every turn misses; the server is busy, so the per-session turn rate is r = 1/Σ_k n_k τ^trap_k with τ^trap_k = τ_P(L_k, 0) + Dτ_D(B_S)/B_S. dn_1/dt = λ - r n_1, dn_k/dt = r n_{k-1}(1 - haz_{k-1}) - r n_k, completions r Σ_k n_k haz_k (haz_k = P(T = k)/P(T ≥ k)). A burst enters as fresh sessions at k = 1 on top of the good-state composition N1 π.

## 2. Results

**R1 (fixed-point equation; existence) — proved.** For every n, Φ_n is continuous on [0,1] (U and S agree on their boundary: there B_U = B_S, ν_U = ν_S, W = 0), Φ_n(0) ≥ 0 and Φ_n(1) < 1 for any tool-time law with P(Z ≥ x) > 0 for all x (exponential, gamma); by the intermediate value theorem h = Φ_n(h) has a solution. For a deterministic tool time Φ_n is a step in R and the solution may be a Filippov (sliding) equilibrium at R = z̄.

**R2 (trap threshold and μ_∞ = λ_miss) — proved within the model.** At h = 0 in the S regime, W = [n - ν_0 z̄' - (1-η)M/c̄_run]/ν_0 (ν_0 = ν_S(0)). For R ≤ W the Che equation is linear, ηM = ν_0 c̃ R, so R_trap = ηM/(ν_0 c̃). Φ_n(0) = P(Z + W < R_trap) = 0 iff W ≥ R_trap, i.e. iff

  n ≥ n_trap := ν_0 z̄' + (1-η)M/c̄_run + ηM/c̃ ≈ λ_miss E[T] z̄' + M/c̄   (c̄_run ≈ c̃ ≈ 10.5k).

So the all-miss state is self-consistent exactly when the population exceeds the sessions in tool calls at the all-miss rate plus one pool's worth of sessions; η cancels to first order. Values: 33.42 (A100 300k), 95.87 (native), 33.10 (vLLM), 42.02 (H200), 32.72 (Llama), 18.95 (150k), 62.03 (600k); the numerical collapse point of each curve equals n_trap to 2 decimals. For n → ∞, W_n(h) → ∞ for every h (the queue grows linearly in n, ν ≤ ν_S(1)) while R ≤ ηM/(ν_0 c̃) once W exceeds ηM/(ν_0 Σπ→c), so Φ_n → 0 uniformly and μ(n) → λ_miss^model = ν_0/E[T]: the paper's Proposition A, recovered inside the model.

**R3 (one versus three solutions: the closed system is monostable) — numerical.** Φ_n has exactly one fixed point at every n of the scanned grids, and it is stable, for: the three measured cells (n = 16-40 step 0.5 at 300k, 60-104 step 1 native), η ∈ {0.03, 0.10, 0.25}, and gamma tool-time shapes 1, 4, 16 and ∞ (deterministic) (`uniqueness_scan.json`; also shapes 64 at 300k, n = 22-36). The steepest crossing has Φ'_n ≈ 0.69-0.71 (300k, n ≈ 33), 0.62-0.65 (native, n ≈ 95) and 0.77-0.78 (vLLM) for exponential tools, ≈ 0.41-0.43 for gamma shape 4: near-critical, so the closed relaxation is slowed ~1/(1-Φ') ≈ 3×, consistent with the long degraded episodes of the n = 24 and 32 Stage C runs, but there is no fold. Mechanism: two feedbacks of opposite sign act on R. Positive: misses → prefill → decode starvation → pinned swelling → shorter R. Negative: hits → more turns per second → more sessions holding idle KV in tool calls and more dead-KV inflow → shorter R (with a deterministic tool time this one dominates below the cliff and the map is a decreasing step). The positive loop only wins once admission is memory-blocked, and that happens at n_trap, beyond the point where the good branch has already run down. **So the answer to "bistability already in the closed system?" is no in this model**; the trapped state needs a queue whose sessions hold no KV, which a closed population can only supply above n_trap.

**R4 (open system: two attractors and a saddle) — standard for the ODE.** With the unimodal closed curve, dN/dt = λ - μ(N) has, for λ_miss < λ < μ_max, a stable node N1 (ascending crossing), a saddle N2 (descending crossing), and for N > N2 the trapped regime: h → 0 and dN/dt → λ - λ_miss^eff > 0 (λ_miss^eff from the trapped composition, R5). In the compactified coordinate u = N/(1+N) the trapped regime is the stable equilibrium u = 1, so the phase line has two stable equilibria (good, trapped) separated by the unstable N2. For λ < λ_miss there is one attractor (the trap drains); for λ > μ_max none is good. Basin boundary as a KV volume: V2(λ) = N2(λ)E_lb (e.g. 347k, 342k, 334k, 322k at 1.35, 1.65, 2.0, 2.5 × λ_ref, 300k).

**R5 (trapped-state identities) — exact in the trapped fluid.** One round lasts C = Σ_k n_k τ^trap_k; it is the follow-up gap (tool call included, since the server serves the others meanwhile). New KV per second = r Σ_k n_k (L_k + d). With the loopvars definition R = M/churn:

  **gap/R = C · churn/M = Σ_{sessions in system} (L_i + d) / M**,

independent of the cost model: the trapped server rewrites the whole pool gap/R times between two uses of any session's KV. In the good state, with gap = z̄ ln 2 + S_good (median of Z plus latency) and churn = λ(L_0 + δ(E[T]-1) + dE[T]) = λ·11,058 tokens/s, **gap/R = (z̄ ln 2 + S_good) λ · 11,058/M** (0.017 at 1.35 × λ_ref, 300k). The trapped/good ratio is 300-500×. The trapped token rate relative to E0a is Σ n_k L_k/C over the E0a analogue (POP 32, h = 0): above 1 when the trapped composition is younger than stationary (cheaper attention per token) or the trapped batch B_S is larger than E0a's (native pool), and increasing in λ (more fresh sessions).

**R6 (from-empty edge as a level-crossing problem).** A run from empty at rate λ escapes when V(t) first reaches V2(λ); it fails the E0b rule if the escape happens early enough for the queue to reach 50 by 3000 s (t_esc < 3000 - 50/(λ - λ_miss)). Gaussian/Poisson-clumping form: P_esc ≈ 1 - exp[-(H/τ_c) Φ̄((V2 - V̄)/σ_V)], with V̄ = λE[∫c], σ_V² = λE[∫c²]; since σ_V/V̄ ∝ (λ·lifetime)^(-1/2) ∝ M^(-1/2) at fixed λ/λ_miss, **the edge approaches μ_max as the pool grows** (model edge/μ_max: 0.76 at 150k, 0.79 at 300k, 0.87 at 600k, 0.96 at the native pool; measured 0.61-0.77 at 300k and 0.82-0.97 native). The probabilities are computed by Monte Carlo of the shot noise (400 runs per rate).

**R7 (critical burst).** A burst of b fresh sessions adds b fresh cohorts whose expected KV per session peaks at c_peak = max_k P(T ≥ k) c_k = 4,330 tokens (turn 12, ≈ 70 s after the burst). Deterministic size: **N_crit(λ) = (V2(λ) - N1(λ)E_lb)/c_peak** = 59.5, 53.5, 46.2 at 1.35, 1.65, 2.0 × λ_ref (300k); with fluctuations (Monte Carlo) P(stuck) = 1/2 at b ≈ 57, 48, 37. It ignores the burst's prefill pulse (200 × 2000 tokens), which can only make the real N_crit smaller.

**R8 (cap engaged inside the trap).** A pause cap N_c engaged at t_on drains the trap and the good state persists after release iff (C1) N_c < n_trap (the capped closed system has no self-consistent all-miss state, R2, and by R3 its unique state is good, so it leaves the trap from any initial composition), (C2) λ < μ(N_c) (the gate drains), and (C3) after release N ≤ N_c sessions with V < V2(λ), which holds when N_c E_lb < V2(λ) (true for N_c ≤ n*); persistence then has probability 1 - P_esc(λ, remaining horizon). Release time: t_rel ≈ t_on + C(t_on) + [N(t_on) + (λ - μ_trap)C(t_on) - N_c]/(μ(N_c) - λ) + hold, with C(t_on) the trapped round at engagement (attrition takes one round) and N(t_on) from the trapped fluid.

**R9 (window scaling law).** (a) Exact: every rate in the model scales as 1/t under a common rescaling of all times, so W := μ_max/λ_miss depends on hardware speed s and tool time z̄ only through **s·z̄** (equivalently through κ = z̄ λ_miss E[T], the number of all-miss turns served during one tool call: 5.3 on the A100, 14.0 on the H200). Checked in `scaling.csv` (speed 2 & z̄ = 5 equals speed 1 & z̄ = 10 to 3 digits). (b) Approximation when the peak is in the hit regime: requiring R ≥ 3z̄ at the peak gives n* ≈ M/(E_lb + 3z̄E[c_T]/(E[T](z̄' + S*))) and

  **W ≈ M τ̄_miss / [(z̄' + S*) E_lb + 3 z̄ E[c_T]/E[T]]**,  τ̄_miss = 1/(E[T]λ_miss),

within 1-8% of the model for A100 300k (3.43 vs 3.47), native (7.66 vs 7.10), vLLM, Llama and 600k. It fails when misses are cheap relative to the cycle (H200: 1.40 vs 1.97; 150k: 1.78 vs 2.06): there the peak moves into the partial-hit regime toward n_trap. (c) Bounds: W ≤ τ̄_miss/τ̄_hit ≈ 8.8 (compute), approached as M grows. Model values (z̄ = 5): 300k: 3.47 (speed ×1), 2.33 (×2), 2.01 (×2.66), 1.70 (×4); speed ×1: 1.31 (75k), 2.06 (150k), 3.47 (300k), 5.72 (600k), 7.10 (955k), 7.89 (1.5M); 300k speed ×1: 6.0 (z̄ = 1 s), 5.2 (2 s), 3.47 (5 s), 2.33 (10 s). The from-empty edge narrows faster than W on small pools (R6).

## 3. Inputs used and quantities predicted

Inputs, all independent of the predicted curves: the workload constants (above); M = 300,000 / 955,757 tokens; the SGLang iteration-time fit (5 constants + chunk 8192, 256 running), fitted only to Stage 0/C server-log batch timing, not to μ(n), hit fractions or any open-system run; the decode-iteration count (99); η = 0.10 (judgment, see section 1; landmarks insensitive). For vLLM one factor (1.0886 on every cost constant) fitted to vLLM's own E0a token rate (10,349 tok/s); the λ_miss in turns that this implies (0.0670) is then a prediction (measured 0.0657). For H200 one factor (0.3637) fitted to the H200 E0a token rate (29,866 tok/s); variant: memory-bound terms scaled by the spec-sheet HBM-bandwidth ratio 1.935/4.8 and compute terms fitted. For Llama no data: Qwen costs times architecture ratios (per-token ×1.069 non-embedding parameters, prefill attention ×1.306 query-heads×layers, decode attention ×2.286 KV bytes per token, iteration overhead ×1.054 weight bytes). The E0b reference λ_ref of each measured cell is used only to express rates as multiples. Predicted: everything else, including λ_miss of the SGLang cells, the whole μ(n) curve, hit fractions, the trapped backlog path, token ratios, R and gap/R, the edges and the drain times.

## 4. Validation (predicted vs measured; measured sources in `measured.py`)

MF = mean field; SM = with the live-KV fluctuation (no extra parameter). Measured curve: one run per n.

| Cell | quantity | predicted | measured | error |
|---|---|---|---|---|
| A100 300k | λ_miss (turns-based) | 0.0716 | 0.0715 | +0.1% |
| | all-miss tok/s (E0a) | 11,061 | 11,243 | -1.6% |
| | μ(16), μ(20), μ(24), μ(32) | SM 0.1765, 0.2141, 0.2357, 0.1546 | 0.1756, 0.2239, 0.2333, 0.1150 | +0.5%, -4.4%, +1.0%, +34% |
| | peak n | SM 24.6 (grid argmax 24), MF 25 | 24 (20 within 4%) | ok |
| | μ_max | SM 0.2359, MF 0.2487 | 0.2333 | +1.1%, +6.6% |
| | 0.5-hit crossing | SM 31.2, MF 32.1 | 32.2 | -1.0, -0.1 |
| | hit at 24 / 32 | SM 0.879 / 0.458 | 0.888 / 0.505 | |
| | μ at large n | stationary 0.0714 = λ_miss; Stage C window (synchronized start) μ(300) 0.1079, μ(96) 0.0780, μ(48) 0.0708 | 0.1078, 0.0611, 0.0489 | +0.1%, +28%, +45% (turns-based 48: 0.0713 vs 0.0629) |
| | window μ_max/λ_miss | SM 3.30, MF 3.47 | 3.26 | +1%, +6% |
| | from-empty edge | P(unstable) 1.5% at 2.0×, 33% at 2.5×, 96% at 3.0×; 50% at 2.61× | stable ≤ 2.0×, unstable 2.5× (realized 2.73×), 3.0× | consistent |
| | trapped gap/R (1.35×, 1.65×) | 7.31, 9.41 (R = M/churn 26.7, 26.5 s) | 6.35-6.92, 8.18-9.67 (R 25.6-26.2 s) | +6-15%, in range |
| | good gap/R (1.35×, 1.65×) | 0.017, 0.021 (R 281, 230 s) | 0.016-0.020, 0.022-0.028 (R 188-307 s) | in range / -10% |
| | trapped token ratio | 1.005, 1.014 | 1.009-1.025, 1.025-1.029 | -0.4 to -2 points |
| | trapped backlog, slope | 231, 0.017; 323, 0.032 | 200-232, 0.004-0.022; 283-332, 0.028-0.036 | in range |
| | trapped session rate | 0.079, 0.087 | 0.081-0.091, 0.090-0.097 | -3 to -10% |
| | backlog minimum after burst | 161 at +1194 s; 181 at +724 s | 135-147 at +900-1300 s; 162-172 at +300-1200 s | +10-20% |
| | CAPPED (cap 20) drain | 1576 s, 1941 s | 1547-1904 s, 2021-2693 s | ok, -4 to -28% |
| A100 native | λ_miss, tok/s | 0.0716, 11,061 | 0.0718, 11,282 | -0.3%, -2.0% |
| | μ(24), μ(48), μ(64), μ(80), μ(96) | SM 0.254, 0.426, 0.487, 0.456, 0.169 | 0.265, 0.431, 0.479, 0.477, 0.123 | -4%, -1%, +2%, -4%, +38% |
| | peak n, μ_max | SM 69 (0.495), MF 74 (0.508) | 64 (0.479), 80 within 0.4% | +3%, +6% |
| | 0.5-hit crossing | SM 93.9, MF 94.5 | 93.4 | +0.5, +1.1 |
| | μ(128), μ(300) Stage C window | 0.0854, 0.1104 | 0.0667, 0.1006 | +28%, +10% |
| | window | SM 6.91, MF 7.10 | 6.67 | +4%, +6% |
| | from-empty edge | 0.25% at 5.5×, 39% at 6.5×, 100% at 7.0×; 50% at 6.59× | stable ≤ 5.5×, unstable 6.5× | consistent |
| | trapped gap/R (2.5×, 4.0×) | 4.61, 7.30 | 4.14-4.57, 6.68-6.96 | +1-11%, +5-9% |
| | good gap/R | 0.010, 0.018 | 0.010-0.012, 0.018-0.022 | in range |
| | trapped token ratio | 1.066, 1.076 | 1.074-1.078, 1.106-1.124 | -0.8, -3.3 points |
| | trapped backlog, slope | 589, 0.073; 1125, 0.157 | 557-601, 0.079-0.085; 1098-1139, 0.147-0.164 | in range / -10% |
| | CAPPED (cap 64) drain | 493 s, 815 s | 512-583 s, 837-937 s | -4 to -15%, -3 to -13% |
| vLLM 300k (1 factor fitted on its E0a) | λ_miss | 0.0670 | 0.0657 | +2.0% |
| | μ(16), μ(20), μ(24), μ(28), μ(32) | SM 0.1745, 0.2115, 0.2317, 0.2089, 0.1454 | 0.175, 0.219, 0.218, 0.119, 0.043 | ok, -3%, +6%, **+76%, +236% (miss)** |
| | peak, μ_max, crossing | 24, 0.2317, 31.1 | 20 (24 within 0.5%), 0.2194, 29.1 | +6%, **+2 sessions (miss)** |
| | plateau after the cliff | λ_miss (1.0×) | 0.83-0.90 × λ_miss at n = 32-48 | **miss** |
| | from-empty edge | 0.5% at 2.0×, 19% at 2.5×, 74% at 3.0×; 50% at 2.76× | stable ≤ 2.0×, unstable 2.5×, 3.0× | partial miss (2.5× had P = 0.19) |
| | trapped gap/R | 6.90, 8.82 | 6.51-6.72, 8.05-8.63 | +3-6%, +2-10% |
| | trapped token ratio, backlog | 1.006, 216; 1.015, 300 | 0.997-1.007, 203-227; 1.025-1.031, 277-309 | ok |
| | μ(300) Stage C window | 0.1033 | 0.105 | -2% |

E0a population check (cache disabled, POP 64 vs POP 32 token rate; not used in any fit): model 1.003 (A100 300k), 1.021 (native), 1.001 (vLLM), 1.021-1.025 (H200) against measured 1.017 (single POP-64 seed; seed spread ±1.2%), 1.012, 1.018 and 1.046 (H200, an allowed input). The H200 gap (2 points) says the real POP-32 E0a is a little further from saturation than the model's; fitting the H200 scale to the POP-64 rate instead would make the H200 model about 2.5% faster.

Measured trapped and good gap/R and R are from the frozen `analysis/r11/loopvars_frozen.py` (commit `f1338e3`, unchanged) run here on the committed E2 runs over [5700, 8700) s (A100 300k: 18 runs; native: 18; vLLM BURST: 6); per-run values are in `measured.py`.

**Misses, stated plainly.** (1) vLLM's cliff is earlier and steeper than predicted (hit 0.66 at n = 28 and 0.08 at 32 against 0.79 and 0.52 predicted) and its congested plateau is below λ_miss; the model has no block-level eviction, no preemption-recompute and no vLLM scheduler detail. (2) The mean field puts both SGLang peaks 6% high; the fluctuation average fixes 300k (+1%) but leaves native +3%. (3) μ in the Stage C window at moderate n (48, 96, 128) is over-predicted by 10-45%: those runs had early hits and smaller running batches than B_S. (4) The native trapped token ratio at 4.0× is 3 points low. (5) The from-empty edge criterion (escape when V reaches V2) was adopted after a first, hand-computed criterion (escape when the hit fraction falls below the value at which the GPU saturates, with the good-state pinned volume held fixed) gave edges far too high; the second is the mean-field saddle itself, but the choice was made knowing the 300k and native brackets (section 7).

## 5. Out-of-sample predictions (to be frozen; machine-readable in `predictions.json`)

All SGLang cells: η = 0.10, 400 Monte Carlo runs per rate (escape), 600 per burst size. SM = with fluctuation; MF = mean field. "P(unstable)" = probability that a single 3000 s from-empty run fails the E0b rule.

**(a) H200 NVL, SGLang, Qwen2.5-7B, 300k pool.** Inputs: H200 E0a token rate only (uniform speed-up 2.75×, i.e. all costs × 0.3637); variant in brackets: HBM-bandwidth ratio on the memory-bound terms.
- E0a analogue: λ_miss 0.1933 turns-based (measured input 0.19388, not fitted; the fit is to tokens).
- μ(n), sessions/s, SM [variant]: n = 16: 0.212 [0.210]; 20: 0.264 [0.261]; 24: 0.312 [0.309]; 28: 0.352 [0.348]; 32: 0.375 [0.369]; 40: 0.293 [0.290]; 48: 0.203 [0.203]; 96 and 300 (stationary): 0.196 [0.197]. All-turn hit fraction: 0.931, 0.919, 0.876, 0.800, 0.702, 0.324, 0.024 at 16-48.
- **Peak at n ≈ 32-34 (grid argmax 32), μ_max ≈ 0.37-0.38 = 1.91-1.97 × λ_ref; the peak sits in a partial-hit regime (hit ≈ 0.70); 0.5-hit crossing ≈ 37 (A100: 32); collapse to λ_miss by n_trap = 42.** Mechanism: on faster hardware the running requests pin less KV at a given n, so the miss load that would collapse the A100 at n ≈ 25-33 is absorbed until n_trap = λ_miss E[T]z̄' + M/c̄ moves out with λ_miss.
- Stage C window (synchronized start) at large n: μ(300) ≈ 0.221 sessions/s (turns-based 0.2245), μ(96) ≈ 0.195, μ(48) ≈ 0.197.
- Window μ_max/λ_miss ≈ 1.94 (A100: 3.26 measured).
- E0b P(unstable): 1.25×: 0.03; 1.5×: 0.33 [0.37]; 1.75×: 0.92 [0.95]; ≥ 2.0×: 1.00 (above μ_max). 50% edge ≈ 1.56×.
- Registration consequence under the registered rules (if the E0b grid is 1.25, 1.5, 1.75, 2.0, 2.5, 3.0): most likely (P ≈ 0.6) hi = 1.5, points 1.15 and 1.35, cap 32 (smallest grid n within 5% of the peak; n = 28 is predicted 6% below the peak, so 28 vs 32 is close); with P ≈ 0.33 the 1.5× run is unstable, hi = 1.25 and the window is too narrow for a decisive test; with P ≈ 0.05 the 1.75× run is also stable (hi = 1.75).
- If a paired test runs at 1.35 × λ_ref: BURST trapped with backlog ≈ 396 over [5700, 8700), uncached-token ratio ≈ 1.03, gap/R ≈ 12.5; good arms gap/R ≈ 0.038 (R ≈ 104 s); deterministic critical burst ≈ 51 sessions; a static CAPPED arm with cap 32 drains the 200-session burst in ≈ 1,590 s [1,680 s] (a cap of 20 would barely drain: μ(20) ≈ 0.264 vs λ = 0.262).
- Stage C protocol caveat: values below the cliff are stationary (reached within the 900 s warm-up); values at n ≥ 40 are for the stationary state except μ(96) and μ(300), given for the synchronized-start window.

**(b) Llama-3.1-8B, SGLang, A100, 300k pool** (architecture-scaled costs, uncalibrated; largest uncertainty of this list).
- E0a: λ_miss ≈ 0.0614 turns-based, all-miss ≈ 9,480 tok/s (0.84 × Qwen's measured).
- μ(16, 20, 24, 28, 32, 40, 48), SM: 0.166, 0.197, 0.209, 0.181, 0.122, 0.065, 0.061; hit 0.932, 0.924, 0.878, 0.721, 0.406, 0.037, 0. Peak at n ≈ 24 (μ_max ≈ 0.21; MF 0.222), crossing ≈ 31, window ≈ 3.4 (MF 3.6), n_trap = 32.7.
- E0b (multiples of its own λ_miss): P(unstable) 0.02 at 2.0×, 0.21 at 2.5×, 0.82 at 3.0×; edge ≈ 2.8×. On a 1.25-3.0 grid: hi = 2.5 most likely (P ≈ 0.6; 2.0 with P ≈ 0.2) → points 1.5 and 2.0, cap 24.
- Trapped at 1.35 / 1.65×: backlog ≈ 216 / 296, gap/R ≈ 6.8 / 8.6, token ratio ≈ 1.01; static CAPPED (cap 24) drain ≈ 1,320 / 1,530 s.

**(c) Pool sweep (SGLang, A100, Qwen; λ_ref = 0.071534).**
- 150k: μ(8, 10, 12, 14, 16, 20, 24) SM 0.091, 0.112, 0.129, 0.137, 0.130, 0.091, 0.072; peak n ≈ 14 (0.137-0.142), crossing ≈ 17, n_trap = 19.0, window ≈ 2.0; λ_miss at 150k ≈ 0.0693 (3% below 300k: the all-miss running batch is memory-limited to ~14); E0b P(unstable) 0.04 at 1.25×, 0.61 at 1.5×, 0.94 at 1.75×, 1.0 at ≥ 2.0×; edge ≈ 1.45× (the window shrinks to (1, ~1.25-1.5)); Stage C window μ(300) ≈ 0.104.
- 600k: μ(32, 40, 48, 56, 64, 80) SM 0.322, 0.376, 0.386, 0.281, 0.135, 0.073; peak n ≈ 45-48 (0.39-0.41), crossing ≈ 60, n_trap = 62.0, window ≈ 5.5-5.7; E0b P(unstable) 0.03 at 4.0×, 0.17 at 4.5×, 0.75 at 5.0×, 0.99 at 5.5×; edge ≈ 4.8×; cap 40 (SM) or 48 (MF); Stage C window μ(300) ≈ 0.110.
- Scaling check: peak n ∝ M only roughly (SM 14, 25, 45, 69 for 150k, 300k, 600k, 955k), window 2.0, 3.3-3.5, 5.5-5.7, 6.9-7.1, edge 1.45, 2.6, 4.8, 6.6 × λ_ref.

**(d) B1 basin (300k, 1.65 × λ_ref, burst in 60 s at 1200 s).** P(stuck by 5700 s): burst 100: **1.00**; burst 25: **0.055** (per seed). Predicted B1 verdict: PASS (n100 STUCK 3/3; n25 GOOD 3/3 with probability 0.84, ≥ 2/3 with 0.99). Critical burst (P = 1/2): ≈ 48 at 1.65× (deterministic 53.5); ≈ 57 at 1.35×; ≈ 37 at 2.0×. Full curve: `predictions.json` B1_basin (b = 10-200).

**(e) Rescue.** R1 (300k, pause cap 20 at 1800 s, release after the gate has been empty 300 s): at 1.35×, backlog at engagement ≈ 167, trapped round ≈ 92 s, μ(20) = 0.216, gate empty ≈ 3,100 s, **release ≈ 3,400 s**; at 1.65×, backlog ≈ 181, gate empty ≈ 3,530 s, **release ≈ 3,830 s**; post-release relapse probability ≤ 0.01 → RESCUED in every seed. R4 (native, 4.0×, cap 64 at 2100 s): backlog ≈ 335, μ(64) = 0.488, gate empty ≈ 3,720 s, **release ≈ 4,020 s**, relapse ≈ 0 → RESCUED. Conditions C1-C3 hold with margin (20 < 33.4, 64 < 95.9). Expected bias: the same drain machinery under-predicts the measured static CAPPED drains at 1.65× by 4-28% and at native 4.0× by 3-13%, so releases may come 10-30% later; the calibrated simulator's releases (r11: 3,490-5,830 s at 1.35×, 4,050-6,050 s at 1.65×, 4,250-5,180 s for R4) are later than mine. Not registered, a disagreement with the simulator: the model says a cap of 80 at native 4.0× also rescues (80 < n_trap = 95.9), where the simulator gives 0/20.

## 6. Novelty against prior work (checked 2026-10-31)

- **Yao, Gao, Lyu, Grosof, Simchi-Levi, arXiv:2609.02027** (read: abstract page and HTML full text): a Che-type characteristic time T_C = d⁻¹(1) for multi-turn LRU, unique because d(t) is increasing; inter-turn gaps are exogenous i.i.d. (their Assumption B.4); no service time, queue or throughput; rate and memory scaled together so that compute never binds (their Remark B.6 says raising the physical rate could make computation the bottleneck and let latency change the gaps; their experiments do couple the next prompt to the end of decoding). Here the gap includes the queue wait, the pool also holds KV pinned for a service time that itself depends on the miss rate (prefill-priority decode starvation), and dead KV; the fixed point is in h, not in R, and the map has feedbacks of both signs, so uniqueness is not given by monotonicity (R3 establishes it numerically and R2 gives the closed-form trap threshold); and the model outputs the throughput curve, the open-system basin, the edge, the burst size and the cap condition, validated against a real engine.
- **Che approximation** (Che, Tung and Wang 2002; Fricker, Robert and Roberts 2012): exogenous request processes (IRM or renewal). The endogenous-gap closure (the cache's miss rate sets the queueing delay that sets the reuse age) is, to my knowledge, new for LLM serving; I did not search the general caching literature for an endogenous-gap Che model and would not claim novelty there without that search.
- **Denning (1968) and Courtois (1975):** the thrashing curve and the working set; Courtois finds unstable regimes of multiprogrammed paging by aggregation. The new pieces are agent-specific: KV idle across tool calls, dead KV never freed, prefill-priority pinning, the closed-form n_trap, and the result that the closed population is monostable while the open system is metastable.
- **MISA-T (hong2026misat):** an adaptive admission cap from observed KV demand and overload; a mechanism without a model. R8 gives conditions and a release-time formula for a cap engaged inside the trap.
- **Metastable-failure models.** Isaacs et al. (HotOS '25) and Alvaro et al. (arXiv:2510.03551): CTMC models of request-response servers with retries; metastability via escape probabilities and the chain's eigenvalue structure. Habibi et al. (SRDS '24, MSF-Model): queueing + Markov chains + Monte Carlo for retry-amplified replicated storage. Farahbakhsh et al. (HotNets '25, "Modeling Metastability"): retransmissions exceeding the service rate make the request count grow without bound. Those sustaining effects are retries and timeouts; here it is cache loss (evicted KV, 16× prefill per session), the basin boundary is a KV volume V2(λ), and the escape is a shot-noise level crossing whose parameters come from the workload. This is the first quantitative, engine-validated model of a cache-loss metastable failure in LLM serving that I know of, with the same caveat on search depth (web search of titles and abstracts only).

## 7. Weaknesses and what is not shown

- η is not derived; it does not move the curve or the edges, only R_che and B_S in the trap.
- The escape criterion (R6) is a reduction: quasi-static in composition, the barrier from the mean-field saddle expressed as a KV volume, a one-dimensional crossing of a multi-dimensional state. It was chosen after a first criterion failed against the A100 brackets (section 4, miss 5), so its agreement with the 300k and native edges is in-sample for the choice of criterion; its vLLM, H200, Llama and pool-sweep edges are the out-of-sample test. The criterion has no free parameter, but its 50% edges depend on the mean-field peak, which is 3-6% high.
- The fluctuation smoothing is annealed (quasi-static); it cannot produce the long degraded episodes seen at n = 24 and 32 (the closed system is near-critical but not bistable in this model, so those episodes are fluctuations slowed by Φ' ≈ 0.7, a claim not tested here).
- The trapped fluid is round-robin with deterministic per-turn costs; it ignores hits inside the trap and the 60-turn cap's minor effects; its composition argument explains the token-ratio trend but under-predicts the native 4.0× ratio by 3 points.
- The burst model ignores the burst's own prefill pulse; N_crit may be smaller than predicted.
- vLLM is outside the model's validity (section 4, miss 1). The Llama costs are FLOP/byte extrapolations; the H200 predictions assume the iteration overhead speeds up with the GPU (variant: bandwidth-bound terms by the HBM ratio; the two variants agree within 2%), and the CPU part of SGLang's iteration overhead may not speed up at all (not modelled; it would lower the H200 good-state throughput, peak and window).
- Proved: R1, R2 (within the model), R4 (for the ODE), R5 (identity within the fluid), R9(a). Numerical: R3, R6-R8 values, R9(b).

## 8. Files

- `analysis/theory/che_endogenous/model.py`: workload, cost model, U/S server, Che equation, map Φ_n, fixed points, E0a analogue, scale calibration.
- `analysis/theory/che_endogenous/open_system.py`: closed curves, fluctuation smoothing, landmarks, N1/N2, shot-noise escape Monte Carlo, trapped fluid, synchronized-start transient, burst, capped drain, rescue.
- `analysis/theory/che_endogenous/measured.py`: measured targets with sources (not inputs).
- `analysis/theory/che_endogenous/run_che.py`, `plots.py`: driver and figures.
- `tests/test_theory_che_endogenous.py`: identities, existence/uniqueness, all-miss limit, trapped identity, scale fit, Campbell check of the Monte Carlo, scaling directions.
- `results/theory/che_endogenous/`: `validation.json` (with a `comparison` block per cell), `predictions.json`, `curves_<cell>.csv`, `scaling.csv`, `sensitivity_eta.json`, `meta.json`.
- `figures/theory/che_closed_curves.png`, `che_from_empty_edge.png`, `che_trapped_state.png`, `che_window_scaling.png`, `che_predicted_curves.png`, `che_burst_basin.png`, `che_feedback_map.png`.
