# A mean-field model that predicts the thrashing curve, the metastable window and the trapped state (round 13, approach B)

Status: 2026-10-30/31, worktree `r13/theory` (base `582c2a6`), nothing committed. Code `analysis/theory/fluid_rigorous/`, test `tests/test_theory_fluid_rigorous.py` (13 tests, 12 s), numbers `results/theory/fluid_rigorous/`, figures `figures/theory/fluid_rigorous_*.{png,pdf}`. Reproduce: `PYTHONPATH="src;." python -m analysis.theory.fluid_rigorous.run_all` (about 6 minutes on the PC).

Labels used below. **Proved**: a statement about the model with a complete proof here. **Numerical**: a property of the model checked by computation for the stated parameters (not proved in general). **Heuristic**: an approximation layered on top of the model, with stated assumptions; not a theorem. The model itself (Section 1) is a deterministic fluid model; I do not prove that the stochastic engine converges to it.

## 0. What is new, in five lines

1. **The thrashing curve is predicted, not measured.** A fluid model with zero parameters fitted to any Stage C, E0b or E2 number (pool size, workload, tool-time law and the server-log cost model only) gives, for SGLang on the A100 at 300k: peak 0.248 sessions/s at n = 24.9 (measured 0.233 at 24, flat top 20–24), 0.5-hit crossing at n = 31.5 (32.2), all-miss level 0.0718 (E0a 0.0715); at the native pool (955,757): peak 0.508 at n = 74 (0.479 at 64, flat top 64–80), crossing 93.7 (93.4). The existing paper takes μ(n) as measured (model.tex, "quasi-static model taking μ(n) as MEASURED").
2. **The mechanism is closed in one equation.** The LRU memory balance `M = K_run(ν, h) + μ D(R; W)` with `h = F_Z(R − W)` is the characteristic-time equation of Yao et al. (2609.02027) with two additions that Yao et al. leave out by construction: the running reservations `K_run` and an endogenous gap (queue wait `W` and service time that depend on `h` through the server). Their fixed point is unique because the gap is exogenous; closing the loop gives the rise, the peak, the cliff and the all-miss branch.
3. **Window law (proved scaling, explicit approximation within 1%).** λ_miss scales exactly with GPU speed `s`; the window μ_max/λ_miss depends on speed and tool time only through `s·z̄` and strictly decreases in it. Approximately μ_max ≈ M / (Ē (L + R*)), the memory-limited Little's-law rate. Consequence, made blind before any H200 Stage C or E0b result is read: on the H200 (s = 2.74 from its E0a) the window shrinks from 3.3 to about 1.8–1.95, the peak moves OUT to n ≈ 32–33 at a hit fraction of only about 0.67, and the from-empty edge falls to about 1.34–1.39 λ_ref.
4. **Trapped state, from one identity.** In the trapped regime FCFS serves every session once per cycle, so `gap/R = Σ_{sessions present}(P_k + d) / M`, the total next-turn context in the system divided by the pool. A round-robin fluid driven only by λ and the burst predicts measured gap/R 6.4–9.7 (300k), 4.1–7.0 (native) and 6.5–8.6 (vLLM) to within about 5–10%, the backlog to within about 10%, and the token rate to within 2–6%.
5. **Finite-size layer (heuristic, nothing fitted).** A one-dimensional diffusion for the KV demand around the predicted curve puts the from-empty edge between 2.0 and 2.5 λ_ref at 300k and between 5.5 and 6.5 at the native pool, both exactly the measured brackets. For vLLM it is one grid step too high (predicts 2.5 stable; measured unstable).

Misses, stated up front: μ_max is 6% high on both SGLang cells (sessions/s; 9–10% against the turns-based estimator), the native peak location is 74 against a measured flat top 64–80 (inside it, but above the argmax), and the vLLM cell is a partial miss (peak +13.5%, crossing 31.8 against 29.1, edge one step high, and the measured sub-λ_miss dip at n = 32–48 is outside the model). The fluid model has no internal bistability (Section 2.4); the degraded excursions at n = 24 and 32 are explained only as finite-size fluctuations near a weakly stable state, not proved.

## 1. The model

### 1.1 Primitives [S1]
- A session has `T` turns with `G_k = P(T ≥ k) = q^{k−1}` for `k ≤ K` (q = 14/15, K = 60), `E[T] = Σ_k G_k = 14.761`. Turn mix `w_k = G_k / E[T]`.
- Turn k sends `P_k = L0 + (k−1)(Δ + d)` tokens (2000 + 650(k−1)) and decodes d = 100. After it the session's KV is `E_k = P_k + d`.
- A miss prefills `P_k`; a hit (k ≥ 2) prefills `x_h = Δ + 1 = 551` (the SGLang Stage C fact "cached = prompt − 551"; for vLLM 559, the mean unfilled 16-token block added). Turn 1 always misses.
- Tool times `Z` i.i.d., independent of everything, continuous law `F_Z` with `F_Z(0) = 0` (record: Exp, mean z̄ = 5 s). For the scaling results, `Z = z̄ Y` with `Y` fixed.
- Per-session KV constants: `A1 = Σ_k G_{k+1} E_k` (KV carried through tool calls, 144,960 tokens), `E[E_T] = Σ_k (G_k − G_{k+1}) E_k` (final KV, 11,045), `Ē = Σ_k w_k E_k` (10,569).

### 1.2 Service [S2] (the calibrated cost model as a fluid server)
Iteration costs from `calibration/round6_server_log_fit/calibration.yaml` (fitted to SGLang server-log timing only): `a = 9.24 ms`, `f = 1.26 ms`, `b = 62.6 µs/token`, `c_d = 0.31 ms` per 8192 context tokens per decode step, `c_p = 2.24 ns` per causal pair, chunk B = 8192.
- Prefill GPU time of a turn: `t_P(x, c) = a·max(1, x/B) + max(f, b x) + c_p x (c + (x+1)/2)` (fixed cost amortised per full chunk). Miss: `t^m_k = t_P(P_k, 0)`; hit: `t^h_k = t_P(x_h, P_k − x_h)`.
- **Separate iterations (SGLang).** Prefill has priority and stalls decode. With admission (= completion) rate ν turns/s and follow-up hit probability h: prefill fraction `p = ν Σ_k w_k [h_k t^h_k + (1−h_k) t^m_k]`; decoding count `R_D` solves `R_D (1 − p) = ν (d−1) τ_D(R_D)`, `τ_D(R) = a + max(f, bR) + β_c R`, `β_c = c_d c̄_D / 8192` (c̄_D the mean decode context); decode duration `S_D = R_D/ν`; service time `S_k = t_P,k + S_D`; running reservations `K_run = ν Σ_k w_k E_k S_k`.
- **Mixed iterations (vLLM-like).** Iterations per second `I = (1 − ν c_turn)/a` with `c_turn = b x̄ + c_p π̄ + (b + β_c)(d−1)`, chunk budget `ν(x̄ + d − 1)/I ≤ B`; `S_D = (d−1)/I`.
- Assumptions: (A2a) a turn's prefill latency is its own prefill GPU time (no queueing behind other prefills; exact in a fluid limit where a request's work is small against capacity; it drops an M/G/1 wait of about 10 ms in the good state and more near the cliff), (A2b) the GPU is busy whenever a request runs, (A2c) a running request reserves `E_k` from admission to completion (the simulator's `full_reserve`).

### 1.3 Memory [S3]
- Pool M tokens; idle KV (sessions in a tool call or queued, and the dead KV of finished sessions, which the engine cannot know is dead) is evicted least-recently-used first, whole session at a time, only when space is needed.
- **Lemma (LRU frontier; proved).** At every time the resident idle items are exactly those whose last use is later than a non-decreasing frontier θ(t). *Proof.* If idle item i is resident at t and idle item j became idle later than i, then j was never evicted in between: LRU would have evicted i first, and i, once evicted, can only return through a new use, which would move its last-use time. Evicted items stay evicted until used, so θ never decreases. ∎ In a stationary regime θ(t) = t − R: an idle item is evicted exactly when its idle age reaches R.
- **Memory balance.** By H = λG (rate of idle episodes × expected KV-time of each), the expected resident idle KV is `μ D(R; W)` with
  `D(R; W) = A1 · E[min(Z + W, R)] + E[E_T] · R`,
  the first term for idle periods of continuing sessions (tool call plus queue wait W), the second for dead KV, which stays until evicted at age R. The pool is full in any stationary regime (dead KV accumulates until it is), so
  **`M = K_run(ν, h) + μ D(R; W)`,  `h = P(Z + W < R) = F_Z(R − W)`  (0 if R ≤ W).**
- With `K_run = 0` and exogenous W this has the form of Yao et al.'s characteristic-time equation `d(T) = λ₀E[B]T + λ₀A_H∫₀^T F̄` (their Theorem: unique T_C, because `d` is strictly increasing and nothing feeds back). Here ν, W and the S_k inside K_run depend on h.

### 1.4 Closed and open system [S4]
- Closed population n, finished sessions replaced at once. Little's law: `n = μ [E[T](W + S̄) + (E[T] − 1) z̄]`, `μ = ν/E[T]`, `S̄ = Σ_k w_k S_k`.
- (A4) FCFS admission is work-conserving and memory-gated: a queue (W > 0) exists only if the running reservations fill the pool, `K_run = M`. That leaves no room for idle KV, so R = 0 and h = 0 (the all-miss branch).
- (A5) Open system (quasi-static): `ṅ = λ − μ(n)` with μ the closed curve. (A6) Internal relaxation at fixed n: `ḣ = κ(Φ_n(h) − h)`, with `Φ_n` the feedback map of Section 2.4.

## 2. Results

### 2.1 The fluid server (proved)
**Lemma 1.** Fix h. Let `t̄_P(h)` be the mean prefill time per turn and `β = b + β_c`. For `ν < ν_cap(h) := 1/(t̄_P(h) + (d−1)β)` the decode equation has exactly one positive root R_D; for ν ≥ ν_cap(h) none. `S_D(ν, h)` is continuous, strictly increasing in ν, non-increasing in h, equals `(d−1)(a+f)` at ν → 0 and tends to ∞ as ν ↑ ν_cap(h). `K_run(ν, h)` is continuous, strictly increasing in ν from 0 to ∞ on `[0, ν_cap(h))`, and strictly decreasing in h for ν > 0.

*Proof.* `ψ(R) = R/τ_D(R)` is continuous and strictly increasing (τ_D is affine on each side of the kink f/b with positive intercept, and `d/dR [R/(α + β'R)] = α/(α + β'R)² > 0`), with ψ(0) = 0 and ψ(∞) = 1/β. The decode equation reads `ψ(R) = ν(d−1)/(1 − p)`: one root iff the right side is below 1/β, i.e. ν < ν_cap(h), and it is unique. The right side increases with ν and does not increase with h (t^h_k ≤ t^m_k for every k), so R_D does the same, and `R_D → ∞` at ν_cap. From the equation, `S_D = R_D/ν = (d−1) τ_D(R_D)/(1 − p)`, a product of two positive factors that increase in ν and do not increase in h. Then `K_run = ν Σ w_k E_k (t_P,k(h) + S_D)`. ∎

Consequence: in separate mode the pool always fills before the GPU saturates (K_run → ∞ at capacity), for every finite M. In mixed mode the chunk budget can saturate the server at finite K_run; that compute-gated case is outside the statements below. It occurs in the model only for large pools with z̄ ≈ 1 s, not in the validated cells.

### 2.2 Stationary states of the closed system (proved)
**Proposition 1.** Let ν_b solve `K_run(ν, 0) = M` (unique by Lemma 1), `μ_b = ν_b/E[T]`, `n_b = μ_b [E[T] S̄(ν_b, 0) + (E[T]−1) z̄]`.
(a) For each R > 0 there is exactly one `ν(R) ∈ (0, ν_cap(F_Z(R)))` with `K_run(ν, F_Z(R)) + (ν/E[T]) D(R; 0) = M`, and R ↦ ν(R) is continuous. The W = 0 stationary states are exactly the points `(n(R), μ(R), h(R) = F_Z(R))` with n(R) from Little's law.
(b) `ν(R), n(R) → 0` as R → ∞, and `ν(R) → ν_b`, `n(R) → n_b` as R ↓ 0.
(c) The W > 0 stationary states are exactly `h = 0, R = 0, ν = ν_b, W = (n − n_b)/ν_b` for n > n_b.
(d) `n̄ := sup_R n(R) < ∞`. For n > max(n̄, n_b) the all-miss state is the only stationary state, so **μ(n) → μ_∞ = μ_b**, and μ_b is the memory-saturated throughput of the same server with every turn missing (the model's λ_miss; the cache-off E0a protocol at a population above n_b measures exactly this).

*Proof.* (a) For fixed R the left side is continuous and strictly increasing in ν, equal to 0 < M at ν = 0 and unbounded at ν_cap (Lemma 1): one root. Continuity in R holds because the left side is jointly continuous and strictly monotone in ν: if `Φ(ν(R₀) ± ε, R₀)` have opposite signs, they keep them for R near R₀. (b) From `(ν/E[T]) D(R) ≤ M` and `D(R) ≥ E[E_T] R`, `ν(R) ≤ M E[T]/(E[E_T] R) → 0`, and S̄ stays bounded, so n(R) → 0. As R ↓ 0, D → 0 and h → 0. A limit point ν* of ν(R) cannot be ν_cap(0), where K_run is unbounded while it stays ≤ M along the sequence, so by continuity `K_run(ν*, 0) = M` and ν* = ν_b; n(R) → n_b by continuity. (c) W > 0 forces `K_run = M` (A4), so `μ D(R; W) = 0`, hence R = 0 and h = 0, so ν = ν_b and Little's law gives W. (d) n(·) is continuous on (0, ∞) with finite limits at both ends, hence bounded. Above max(n̄, n_b) no W = 0 state exists and the all-miss one does. ∎

### 2.3 Rise and window opening (proved)
**Proposition 2 (rise).** (a) At any fixed hit probability, Little's law `n = (ν/E[T])(E[T] S̄(ν, h) + (E[T]−1) z̄)` is a strictly increasing bijection ν ↦ n, so throughput at a fixed hit rate strictly increases with the population (batching amortises the per-iteration cost). (b) There is R₀ with ν(R) and n(R) both strictly decreasing on R > R₀: near n = 0 the stationary states form the graph of a strictly increasing μ(n).
*Proof of (b).* Differentiate `Φ(ν, R) := K_run(ν, F_Z(R)) + (ν/E[T]) D(R) − M = 0`. `∂Φ/∂ν > 0` (Lemma 1). `∂Φ/∂R = (∂K_run/∂h) f_Z(R) + (ν/E[T])(A1 P(Z > R) + E[E_T])`. Here `∂K_run/∂h = −ν Σ w_k E_k |∂S_k/∂h| = O(ν)` and `f_Z(R), P(Z > R) → 0`, so `∂Φ/∂R = ν (E[E_T]/E[T] + o(1)) > 0` for large R. Hence dν/dR < 0; and `dn/dR = (∂n/∂ν)(dν/dR) + (∂n/∂h) f_Z(R) < 0` for large R, since the second term vanishes exponentially. The server functions are smooth except at the kink R_D = f/b, which is crossed at isolated points. ∎

**Proposition 3 (when a peak above λ_miss exists).** If `f_Z(0+) > 0` and the server is differentiable at (ν_b, 0), then dν/dR(0+) > 0, and hence `μ_max := sup_R μ(R) > μ_b`, whenever
**`Δ_S := Σ_k w_k E_k |∂S_k/∂h|(ν_b, 0) / Ē  >  1/f_Z(0+)`  (= z̄ for exponential tool times).**
In words, at the all-miss state a marginal hit must save more KV-weighted reservation time than the idle time it costs.
*Proof.* At R ↓ 0, `D'(0+) = A1 + E[E_T] = Σ_k G_k E_k = E[T] Ē` and `∂K_run/∂h = −ν_b Ē Δ_S`, so `∂Φ/∂R = ν_b Ē (1 − f_Z(0) Δ_S)`; dν/dR = −(∂Φ/∂R)/(∂Φ/∂ν) > 0 exactly when the bracket is negative. ∎
Numbers: Δ_S = 595 s (300k), 6,304 s (native), 679 s (vLLM), against z̄ = 5 s. At the all-miss state decode gets only 1 − p ≈ 8% of the GPU (S_D ≈ 25 s at 300k), so one hit, which removes about 0.9 s of exclusive prefill, un-starves every decoding request. That is why the curve leaves the all-miss end so steeply.

### 2.4 Stability, uniqueness and the absence of a fold
**Feedback map.** For population n and a trial follow-up hit probability h, `Φ_n(h)` is the hit probability that the stationary flows at (n, h) produce. Little's law with W = 0 gives ν; if `K_run(ν, h) ≥ M` the system is memory-gated and Φ_n(h) = 0. Otherwise R solves `μ D(R) = M − K_run` and `Φ_n(h) = F_Z(R)` (code: `model.feedback_map`).

**Proposition 4 (proved, given A6).** (a) Stationary states at population n are the fixed points of Φ_n. (b) A fixed point is asymptotically stable for `ḣ = κ(Φ_n(h) − h)` iff `Φ_n'(h*) < 1`. (c) If `∂Φ_n/∂n < 0` at the fixed point (C2: at a given hit rate, more sessions leave a shorter eviction age), then `Φ_n'(h*) < 1` ⟺ `dn/dR < 0` along the solution curve at that point. (d) If n(R) is strictly decreasing on (0, ∞), the closed system has exactly one stationary state for every n. It lies on the W = 0 curve for n < n_b and is the all-miss state for n ≥ n_b; all are stable, and μ(n) is continuous: **no internal bistability**.
*Proof.* (a) is the construction; (b) is the one-dimensional ODE criterion. (c) Along the curve, `h(R) = Φ_{n(R)}(h(R))`; differentiating gives `n'(R) = f_Z(R) (1 − ∂_hΦ) / ∂_nΦ`, whose sign is that of `−(1 − ∂_hΦ)` when ∂_nΦ < 0. (d) A strictly monotone continuous n(R) is a bijection (0, ∞) → (0, n_b), so the W = 0 curve meets each n < n_b once and never reaches n ≥ n_b. ∎

**Numerical facts.**
- n(R) is strictly decreasing for all three cells. It is also strictly decreasing for SGLang separate mode at every M ∈ {150k, 300k, 955,757} × z̄ ∈ {1, 2, 5, 10, 20, 40} s (`fold_scan_separate.csv`), so the model's closed thrashing curve has no fold.
- C2 holds at the checked points (`dΦ/dn` = 0 at small n, where h saturates, and −0.04 to −0.10 near the cliff).
- The slope Φ' rises from about −0.05 at the peak (the dead-KV churn gives negative feedback) to about 0.8 at the all-miss end. The cliff is therefore a *near*-fold: relaxation slows by 1/(1 − Φ') ≈ 5 tool cycles.

The task's "≥ 2 stable equilibria" therefore holds for the open system (Section 2.5), not for the closed system at fixed n. Courtois (CACM 1975) located unstable operating regimes of multiprogrammed paging by decomposition; the mechanism here does not produce one in the closed system.

### 2.5 The open system: metastability, basin boundary, trap (proved, given A5)
**Proposition 5.** Assume the single-valued closed curve is unimodal: strictly increasing on [0, n*], strictly decreasing on [n*, n_b], equal to μ_b on [n_b, ∞) (numerical: true in all three cells). For every λ ∈ (μ_b, μ_max):
(a) `ṅ = λ − μ(n)` has exactly two finite equilibria `n_1(λ) < n* < n_2(λ) < n_b`.
(b) n_1 is asymptotically stable with basin [0, n_2), and n_2 is unstable.
(c) From any n(0) > n_2, n(t) → ∞. After the first time t_b with n ≥ n_b, `n(t) = n(t_b) + (λ − μ_b)(t − t_b)` exactly: the trapped regime, with a linearly growing backlog and zero hits.
(d) The basin boundary `n_u(λ) := n_2(λ)` is continuous and strictly decreasing, from n_b at λ ↓ μ_b to n* at λ ↑ μ_max. The critical instantaneous burst of stationary-composition sessions, `b_c(λ) = n_2(λ) − n_1(λ)`, is strictly decreasing and vanishes at μ_max.
(e) For λ < μ_b, n_1 is the only equilibrium and is globally attracting. For λ > μ_max there is no equilibrium.

On the compactified line [0, ∞] the two attractors are n_1 and +∞ (the trap), separated by the unstable n_2. That is the "two stable equilibria and an unstable one" picture, with the trapped one at infinity because the backlog grows; with a finite client population it would be a genuine equilibrium.

*Proof.* The phase line of the continuous `f(n) = λ − μ(n)`: f(0) > 0. Strict increase on [0, n*] past λ < μ_max gives one zero n_1 with f > 0 below and f < 0 above. Strict decrease on [n*, n_b] down to μ_b < λ gives one zero n_2 with f < 0 below and f > 0 above. On [n_b, ∞), f = λ − μ_b > 0. (d) `n_2 = (μ|[n*, n_b])^{-1}(λ)` and `n_1 = (μ|[0, n*])^{-1}(λ)` are continuous and strictly monotone. ∎

| cell | λ/λ_ref | n_1 | n_u = n_2 | b_c (stationary) | b_c (fresh, heuristic F3) | trap drift λ − μ_b |
|---|---|---|---|---|---|---|
| 300k | 1.35 | 8.5 | 32.2 | 23.8 | 59 | 0.025 /s |
| 300k | 1.65 | 10.4 | 31.8 | 21.3 | 53 | 0.046 /s |
| 300k | 2.0 | 12.8 | 31.2 | 18.4 | 46 | 0.071 /s |
| native | 2.5 | 16.3 | 92.9 | 76.6 | 188 | 0.106 /s |
| native | 4.0 | 27.8 | 90.0 | 62.2 | 153 | 0.214 /s |
| vLLM | 1.35 | 7.6 | 32.5 | 24.8 | 61 | 0.022 /s |
| vLLM | 1.65 | 9.4 | 32.1 | 22.7 | 56 | 0.041 /s |

### 2.6 Window scaling (proved, plus an explicit approximation)
**Proposition 6.** Write ω = μ_max/μ_b (the window). Let `C/s` denote every GPU cost divided by s, and let `Z = z̄Y`.
(a) *Time rescaling.* (n, ν, h) is a stationary state of the model (C/s, z̄) iff (n, ν/s, h) is one of (C, s z̄). Hence `λ_miss(C/s) = s λ_miss(C)`, `μ_max(C/s, z̄) = s μ_max(C, s z̄)` and **`ω(C/s, z̄) = ω(C, s z̄)`**: GPU speed and tool time enter only through s·z̄, the tool time in units of the GPU's own clock.
(b) *Monotonicity.* For each h ∈ (0, 1) the W = 0 state's ν(h; z̄) is strictly decreasing in z̄, and μ_b does not depend on z̄. So μ_max is non-increasing in z̄ (strictly while ω > 1), and **ω is strictly decreasing in the GPU speed s**.
(c) *Limit.* ω → 1 as s·z̄ → ∞.
(d) *Explicit bound.* `ω ≤ max_h min{ν_cap(h), M E[T] / (E[T] κ₀(h) + A1 E[min(Z, F_Z^{-1}(h))] + E[E_T] F_Z^{-1}(h))} / ν_b`, where `κ₀(h) = Σ_k w_k E_k (t_P,k(h) + (d−1)(a+f))`.
*Proof.* (a) Rescale time by s: every GPU time and service time scales by s, rates by 1/s, and R, W by s. Every equation is invariant. Little's law, `K_run = ν Σ w E S` and `μ D` are rate × time. Using `E[min(z̄Y + W/s, R/s)] = (1/s) E[min(s z̄ Y + W, R)]`, h compares times. In the decode equation p and R_D are invariant. (b) Parametrise the W = 0 states by h. With `r(h) = F_Y^{-1}(h)` and `m(h) = E[min(Y, r(h))]`, the memory balance reads `K_run(ν, h) + (ν z̄/E[T])(A1 m(h) + E[E_T] r(h)) = M`. Its left side increases strictly in ν and in z̄, so the root decreases strictly in z̄. ν_b solves `K_run(ν, 0) = M`, which has no z̄ in it. (c) For h ≥ h₀, `ν(h; z̄) ≤ M E[T]/(z̄ (A1 m(h₀) + E[E_T] r(h₀))) → 0`. For h < h₀, `ν(h; z̄) ≤ ν_K(h)`, the root of `K_run(ν, h) = M`, which is continuous with ν_K(0) = ν_b. Let h₀ → 0. (d) `S_D(ν, h) ≥ S_D(0, h)` (Lemma 1) gives `K_run ≥ ν κ₀(h)`; substitute into the balance. ∎

**Approximate window law (numerical, within 1%).** At the peak the memory balance reads `M ≈ μ Ē (E[T] S̄* + (E[T]−1) h* z̄ + R*)`, so
**`μ_max ≈ M / (Ē (L* + R*))`, `ω ≈ (M/Ē) · c_m / (S̄* + h* z̄ (1 − 1/E[T]) + R*/E[T])`**,
where `L* = E[T] S̄* + (E[T]−1) h* z̄` is the session lifetime at the peak, `R* ≈ 3 z̄` (h* ≈ 0.96) is the eviction age at the peak (dead KV plus the margin that keeps the hit rate), and `c_m = 1/ν_b` is the GPU time per all-miss turn. Equivalently: the pool holds M/Ē sessions' worth of KV, each occupying it for its lifetime plus R*; λ_miss is compute-limited. Exact against approximate: 3.450 vs 3.477 (300k), 6.888 vs 6.935 (native), 3.714 vs 3.731 (vLLM). The compute cap `c_m/c_h` (the all-hit capacity over the all-miss capacity) is 8.7, 8.5 and 9.2. The native window (6.9) is approaching it, which is why it is less than 3.19 × 3.45. The explicit bound (d) gives 4.43, 8.34 and 4.85.

Consequences (`window_scaling.csv`, `fold_scan_separate.csv`, `fluid_rigorous_window_scaling.png`):
- **Faster GPUs.** ω drops as `ω(1, s z̄)`: 3.45 (A100), 2.28 at s = 2, about 1.95 at s = 2.74 (the H200 E0a factor), 1.60 at s = 4, and → 1. λ_miss grows ∝ s, but the good state's peak is bound by memory and tool time, which do not speed up.
- **Larger pools.** ω grows roughly ∝ M until the compute cap: 2.05 at 150k, 3.45 at 300k, 6.89 at 955,757 (z̄ = 5).
- **Tool time.** At 300k, ω = 5.99, 5.18, 3.45, 2.28, 1.60, 1.26 for z̄ = 1, 2, 5, 10, 20, 40 s. As z̄ (or s) grows, the peak moves out and its hit fraction drops: n* = 25 → 59, h* = 0.93 → 0.32. At long tool times the optimum trades hits for population, because a miss is cheap relative to a tool call.

### 2.7 Rescue and hysteresis with a cap (proved, given A5 and A6, fold-free curve)
**Proposition 7.** A client FIFO cap c holds the population in the system at n_in ≤ c; arrivals beyond it wait at the gate, holding no KV. Assume the closed curve is single-valued (Prop. 4(d)) and unimodal (Prop. 5), and λ ∈ (μ_b, μ_max).
(a) If c < n_b, the capped system has a unique, good stationary state once n_in ≤ c, with throughput μ(c), from any initial condition, including the trap.
(b) If moreover `n_1(λ) < c < n_2(λ)` (equivalently μ(c) > λ with c < n_b), the gate empties by `t_0 + G(t_0)/(μ(c) − λ)`. Then n_in relaxes to n_1(λ) < c and the cap stops binding.
(c) Hysteresis: releasing the cap after (b) leaves the state at n_1, which lies in the basin [0, n_2) of the uncapped system. So the system stays good for all time (fluid limit), although the same λ also sustains the trap.
(d) If c ≥ n_b, the capped system at population c is all-miss, and the trap persists. If n_2(λ) ≤ c < n_b, the capped state is good but μ(c) ≤ λ, so the gate never drains. Hence **a cap rescues iff n_1(λ) < c < n_2(λ)**: the cap must lie in the good basin itself.
*Proof.* With n ≥ c the capped system is the closed c-system (cap identity, paper Prop. 2). (a) and (d) follow from Prop. 4(d): a unique stationary state at each population, all-miss exactly for n ≥ n_b. (b) While the gate is non-empty, `Ġ = λ − μ(c)`. (c) follows from Prop. 5(b). ∎
For the registered caps: 300k c = 20 against (n_1, n_2) = (8.5, 32.2) at 1.35× and (10.4, 31.8) at 1.65×; native c = 64 against (27.8, 90.0) at 4.0×. All lie inside, so the fluid model with stationary composition predicts rescue. The composition correction (heuristic F4, Section 4) narrows this.

### 2.8 The trapped regime as an FCFS round robin (identities proved; dynamics a fluid model)
**Proposition 8.** In the all-miss regime with a saturated GPU and FCFS, where every session in the system is queued for its next turn when that turn comes up (tool calls shorter than the cycle), each session completes exactly one turn per cycle, and the cycle is the GPU work of one round, `c(t) = Σ_{i ∈ sys} g(k_i)` with `g(k) = t^m_k + δ_dec` (δ_dec = (1 − p_b)/ν_b, the per-turn decode share of the saturated all-miss state). Then:
(a) gap (end of turn k to end of turn k+1) = c;
(b) churn (uncached prompt + completion tokens per second) = `Σ_i (P_{k_i} + d)/c`, so `R_M := M/churn` and **`gap/R_M = Σ_{i ∈ sys}(P_{k_i} + d) / M`**;
(c) the uncached token rate is `Σ_i P_{k_i} / Σ_i g(k_i)`, which depends only on the turn mix of the sessions present;
(d) LRU evicts an idle item before more than M newer tokens have been written, so its eviction age is at most R_M. The trap is therefore self-consistent whenever the next admission comes later than R_M, roughly `Σ_{sys}(P + d) > M (1 + S/R_M)`. The total next-turn context of the sessions present must exceed the pool. For the stationary turn mix this happens at `n_sys ≈ M/(P̄ + d) ≈ 32` (300k), consistent with n_b = 32.7.
*Proof.* (a)–(c) are definitions under one-turn-per-cycle. (d) Tokens are freed only by eviction, and newer tokens are evicted after older ones, so an item is gone by the time M newer tokens exist. ∎
The dynamics: each cohort advances its turn index at rate 1/c(t) and survives to turn K with `q^{K−1}`. The good-state population n_1(λ) and the burst (200 in 60 s) are present at the burst time (`trapped.round_robin_trap`). Nothing is fitted.

## 3. Validation on the measured cells (independent inputs only)

**Inputs used.** The pool M (300,000; 955,757; 18,750 × 16), the workload of `configs/agentload_e2_burst.yaml` (L0, Δ, d, Geometric(1/15) capped at 60, Exp(5 s)), the calibrated costs (SGLang cells, unchanged), and x_h = 551.
- **vLLM.** Mixed iterations and ONE factor s_v = 0.918, fitted so that the model's E0a (closed POP 32, cache off) token rate equals vLLM's measured 10,349 tok/s (allowed input; the model's all-miss rate is exactly ∝ s).
- **Validation targets only, never fed in.** No Stage C, E0b or E2 number is used anywhere. λ_ref is the E0a turns-based rate; it is used only to place the E0b and E2 rates (mult × λ_ref) where the protocol placed them.
- **Blindness, stated plainly.** The measured values of the three cells were in my brief while I built the model, so this validation is not blind. No parameter was tuned to them, and the specification was not changed after the comparisons: calibrated costs, separate iterations for SGLang, mixed iterations for vLLM (its scheduler is mixed by construction), x_h = 551, and for F2 the choices H = 3000 s, target n_b and I_D from the workload. Section 5 is blind.
- **Provenance of the cost model.** It was fitted to iteration timings from the server logs of the Stage 0 and 300k Stage C jobs (17060165, 17062103–05). So the 300k prediction is out of sample in its target (μ(n) was never used) but not in its data source. The native pool, vLLM and all open-system quantities use no timing from their own runs.

**Closed curve and window** (`cells_comparison.csv`; "annealed" = heuristic F1, fluid averaged over demand fluctuations):

| quantity | 300k: measured | 300k: fluid (annealed) | native: measured | native: fluid (annealed) | vLLM: measured | vLLM: fluid (annealed) |
|---|---|---|---|---|---|---|
| peak n | 24 (flat 20–24) | 24.9 (24) | 64 (flat 64–80) | 74.1 (70) | 20 (flat 20–24) | 24.9 (24) |
| μ_max sessions/s (turns-based) | 0.2333 (0.2255) | 0.2478 (0.2337) | 0.4789 (0.4655) | 0.5076 (0.4949) | 0.2194 (0.2108) | 0.2490 (0.2353) |
| error of fluid μ_max | | +6.2% (+9.9% vs turns) | | +6.0% (+9.0%) | | +13.5% (+18.1%) |
| 0.5-hit crossing | 32.2 | 31.5 (30.6) | 93.4 | 93.7 (92.0) | 29.1 | 31.8 (30.8) |
| μ at large n, turns-based | 0.0730 (n=96) | 0.0718 (flat from n_b = 32.7) | 0.0730 (n=128) | 0.0737 (flat from 94.9) | 0.0686 (n=96) | 0.0670 (flat from 32.8) |
| λ_miss: E0a turns-based / model POP 32 | 0.0715 | 0.0718 (+0.3%) | 0.0718 | 0.0718 (0.0%) | 0.0657 | 0.0670 (+2.0%) |
| E0a uncached tok/s | 11,243 | 11,091 (−1.4%) | 11,282 | 11,091 (−1.7%) | 10,349 | fitted |
| POP-64 / POP-32 tokens | 1.017 | 1.001 | 1.012 | 1.021 | 1.018 | 1.001 |
| window μ_max/λ_ref | 3.26 (3.15) | 3.46 | 6.67 (6.48) | 7.07 | 3.34 (3.21) | 3.79 |
| from-empty edge (× λ_ref) | stable 2.0, unstable 2.5 | stable 2.0, unstable 2.5 (edge 2.34) | stable 5.5, unstable 6.5 | stable 5.5, unstable 6.5 (6.26) | stable 2.0, unstable 2.5 | stable 2.5, unstable 3.0 (2.57) MISS |

The predicted edge uses heuristic F2 with H = 3000 s. P(escape) at the E0b multiples: 300k 0.001, 0.006, 0.04, 0.15 | 0.69, 0.97; native ≈0, ≈0, ≈0, ≈0, 0.05 | 0.68; vLLM ≈0, 0.002, 0.012, 0.06, 0.42 | 0.88. The fluid limit alone (no fluctuations) puts the edge at μ_max: 3.46, 7.07 and 3.79 λ_ref, the measured gap that motivated the paper's measured-edge definition.

Pointwise (`measured_vs_predicted_<cell>.csv`), 300k, sessions/s measured against fluid: n = 16: 0.1756 vs 0.1765; 20: 0.2239 vs 0.2161; 24: 0.2333 vs 0.2462; 32: 0.1150 vs 0.1078 (hit 0.505 vs 0.371). The single n = 32 run mixes a degraded and a recovered phase (LOG 2026-10-22). Native: 24: 0.265 vs 0.254; 48: 0.431 vs 0.426; 64: 0.479 vs 0.488; 80: 0.477 vs 0.464; 96: 0.123 vs 0.074 (hit 0.42 vs 0, a mixed-regime run just past n_b = 94.9).

**Trapped and good runs of E2** (`trapped_and_good_runs.csv`; measured gap/R recomputed from the committed request logs with the definitions of `analysis/r11/loopvars_frozen.py`, median gap and R = M/churn over [5700, 8700) s; predicted by the round-robin fluid from λ, the burst and the model's good state, nothing fitted):

| cell, λ/λ_ref | measured gap/R (3 seeds) | predicted | measured R (s) | predicted | measured backlog (sessions) | predicted | measured tokens/E0a | predicted |
|---|---|---|---|---|---|---|---|---|
| 300k, 1.35 | 6.92, 6.35, 6.79 | 6.93 | 25.8–26.2 | 26.6 | 232, 200, 221 | 215 | 1.025, 1.009, 1.019 | 0.992 |
| 300k, 1.65 | 9.67, 8.18, 8.48 | 8.98 | 25.6–25.7 | 26.3 | 332, 283, 311 | 304 | 1.025, 1.029, 1.026 | 1.002 |
| native, 2.5 | 4.57, 4.14, 4.27 | 4.45 | 77.5–77.9 | 79.7 | 601, 557, 583 | 565 | 1.078, 1.074, 1.074 | 1.049 |
| native, 4.0 | 6.86, 6.68, 6.96 | 7.06 | 74.2–75.4 | 78.6 | 1139, 1098, 1114 | 1089 | 1.110, 1.106, 1.124 | 1.060 |
| vLLM, 1.35 | 6.71, 6.51, 6.72 | 6.64 | 28.5–28.8 | 28.9 | 227, 203, 218 | 206 | 0.997, 1.000, 1.007 | 0.992 |
| vLLM, 1.65 | 8.63, 8.05, 8.30 | 8.52 | 27.8–28.0 | 28.6 | 309, 277, 300 | 288 | 1.031, 1.025, 1.026 | 1.002 |

Backlog slope: 300k measured 0.022, 0.004, 0.019 against 0.016 at 1.35×, and 0.032, 0.028, 0.036 against 0.029 at 1.65×. The naive fluid drift λ − μ_b gives 0.025 and 0.046; the round robin's younger turn mix lowers it.

Shape of the 300k trap after the burst. The burst cohort first drains, because its early turns are cheap, and the backlog then grows.

| λ/λ_ref | quantity | predicted | measured (3 seeds) |
|---|---|---|---|
| 1.35 | minimum backlog after the burst | 153.5 | 146.7, 146.8, 135.2 |
| 1.35 | time of the minimum after the burst | 1290 s | 1050, 1300, 900 s |
| 1.35 | backlog at the start of the window (5700 s) | 192 | 202, 207, 203 |
| 1.65 | minimum backlog after the burst | 174.3 | 172.1, 170.4, 162.4 |
| 1.65 | time of the minimum after the burst | 800 s | 300, 1200, 900 s |
| 1.65 | backlog at the start of the window (5700 s) | 260 | 267, 265, 274 |

Measured values are from `paper/derived/e2_burst_backlog.csv` and `trap_v2_runs.csv`.
- **Token rate.** The predicted trapped token rate is low by 2–3% (300k, vLLM) and 3–6% (native). Against the model's own E0a the ratios are 1.006–1.016 and 1.067–1.079 (measured 1.009–1.029 and 1.074–1.124). The direction and most of the native excess (a memory-saturated batch of 89 decoders, and a younger turn mix) are predicted.
- **Identity check on real data.** `backlog × (P̄ + d)/M`, from measured backlog and measured P̄, gives 7.24, 6.43, 6.81 for the 300k 1.35× runs, against measured gap/R 6.92, 6.35, 6.79.
- **Good runs (NOBURST and CAPPED).** Predicted hit 0.932 (measured 0.921–0.935). Predicted gap/R 0.017 and 0.021 (measured 0.016–0.028) at 300k, and 0.010 and 0.017 (measured 0.010–0.022) at the native pool.

**Numerical validation of the fluid approximation** (`fluid_vs_stochastic_simulator_300k.csv`). This compares against the finite stochastic simulator with the same calibrated costs (round 6, separate mode, k = 1, 3 seeds, synchronized start; simulator, not engine). At n = 16, 20, 24, 28, 32, 36, 40, the simulator's turns-based μ is 0.175, 0.212, 0.211, 0.180, 0.131, 0.095, 0.080. The fluid gives 0.177, 0.216, 0.246, 0.225, 0.108, 0.072, 0.072, and the annealed fluid 0.176, 0.214, 0.234, 0.208, 0.141, 0.092, 0.077. Hit fractions (simulator / fluid / annealed) at n = 24, 28, 32, 36: 0.884/0.910/0.872, 0.777/0.802/0.702, 0.560/0.371/0.357, 0.297/0/0.104. The deterministic limit is sharper than the finite system. The demand-fluctuation layer F1 recovers the tail (n ≥ 32) and halves the excess at the peak.

## 4. Heuristic layers (not theorems)
- **F1, annealed finite-size curve.** At closed population n the total KV of the sessions present has relative variance CV²/n, with CV² = Var_w(E)/Ē² = 0.570 from the turn mix (`model.kv_dispersion`). Averaging the fluid curve over pools M/θ with θ ~ N(1, CV²/n) gives μ̃(n). It assumes demand fluctuates slowly relative to internal relaxation. That is only partly true near the cliff, where relaxation is slow (Φ' ≈ 0.8).
- **F2, from-empty edge.** The demand in session units, X = D/E_lb, is modelled as `dX = (λ − μ(X))dt + √(I_D(λ + μ(X))) dW`, reflected at 0, with μ the fluid curve and `I_D = E[∫c²]/(E[∫c] E_lb) = 1.567`, the dispersion index of the Poisson shot noise (Campbell). Escape means reaching n_b, with mean first-passage time T from the standard double integral and `P(escape in H) = 1 − e^{−H/T}`. Its stated inputs are H = 3000 s, the target n_b and I_D; all are computed, none fitted. The 1-D reduction is the weak point (MATHCHECK §1: the basin is a hypersurface, not a point). It still reproduces both SGLang brackets, and the edge sits closer to μ_max for the larger pool, as measured (0.68 μ_max at 300k, 0.89 at native).
- **F3, fresh-cohort critical burst.** A burst of b fresh sessions survives iff `D_live(n_1) + b · max_j G_j E_j < D_live(n_u)`, with D_live the live KV demand on the curve and max_j G_j E_j = 4,331 tokens at turn 12. This is the cohort's expected KV per initial session, about 2.4 times smaller than a stationary session's. It gives b_c = 59 and 53 at 1.35× and 1.65× (300k). The round-7 simulator burst sweep had 25 never trapping, 50 trapping about half the time, and 100 always.
- **F4, rescue with a pause-cap.** The registered RESCUE gate pauses sessions at tool-call boundaries. In the round robin every session reaches one within a cycle c(t_on) (88 s at 300k, 150 s native), so the active set drops to the cap within about one cycle. The resumed sessions are mid-session; with memoryless T their footprint is `E_lb + 650(k₀ − 1)` (inflation 1.42 at 300k, 1.34 native), and the first resumed turn misses. The capped system therefore sees an effective pool M/1.42 and one extra miss per session. Two bounds are reported: stationary composition (cap identity) and composition-adjusted.

## 5. Blind predictions for the out-of-sample targets (made before any of their results exist or were read)
Freeze these before reading any H200, Llama, B1 or rescue output (`blind_predictions.json`). Inputs: the H200 E0a (29,866 tok/s, 0.19388 turns-based) and the registered protocols. The POP-64 ratio of 1.046 was only checked: the model gives 1.019 (uniform) and 1.029 (decode-side 2×), so it under-predicts this ratio.

**H200 cell** (SGLang, Qwen2.5-7B, 300k, H200 NVL). Primary: every A100 cost divided by s_H = 2.742, fitted to the H200 E0a token rate. Sensitivity: iteration, floor and decode-attention costs divided by 2.0, compute costs by 2.88. Values are primary (sensitivity):
- Peak n* = 32.8 (32.4), μ_max = 0.378 (0.357) sessions/s, hit fraction at the peak only 0.67 (0.68).
- 0.5-hit crossing at n ≈ 37.3 (37.0); all-miss from n_b = 41.3 (41.5); μ_∞ = 0.197 (0.199), memory-saturated.
- μ(n) at n = 16, 20, 24, 28, 32, 40, 48: 0.212, 0.264, 0.314, 0.354, 0.377, 0.257, 0.197. Hit: 0.932, 0.930, 0.895, 0.803, 0.696, 0.265, 0.
- **Window μ_max/λ_ref ≈ 1.95 (1.84)**, against 3.26 on the A100.
- **From-empty edge ≈ 1.39 (1.34) × λ_ref.** P(escape in 3000 s) at 1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.75, 2.0×: 0.04, 0.12, 0.19, 0.28, 0.52, 0.75, 0.98, 1.0 (sensitivity: 0.07, 0.19, 0.28, 0.40, 0.65, 0.85, 0.99, 1.0).
- Critical fresh burst ≈ 50 at 1.35×, ≈ 34 at 1.65×.
- What a miss would mean: a peak at n ≈ 24 with hit ≥ 0.85 and a window ≥ 2.5 would refute the speed law or the uniform-speed costs.

**Llama-3.1-8B cell** (A100, SGLang, 300k; a priori, no data exist). The calibrated costs are rescaled by architecture ratios, an assumption: GEMM per token 1.06, weight streaming per iteration 1.05, prefill attention 32·32/(28·28) = 1.31, decode attention 32·8/(28·4) = 2.29.
- λ_miss ≈ 0.0619 (E0a tokens ≈ 9,560).
- μ_max ≈ 0.222 at n* ≈ 24.3; crossing ≈ 30.9; n_b ≈ 32.0.
- Window ≈ 3.59; from-empty edge ≈ 2.46 λ_miss (2.0× stable, 2.5× unstable with P = 0.55); fresh critical burst ≈ 60 / 55 at 1.35× / 1.65×.
- Once Llama's own E0a exists, rescale all costs by its ratio to 9,560 tok/s and use Prop. 6(a).

**B1 (300k, 1.65 × λ_ref, bursts in 60 s).** b_c(fresh) ≈ 53 (stationary 21): burst 100 → trapped, burst 25 → not trapped.

**R1 (300k, cap 20 engaged at 1800 s by pause, release after 300 s of empty queues).** The trap holds about 161 sessions (1.35×) and 176 (1.65×) at 1800 s. Cap 20 < n_b = 32.7, so the fluid predicts rescue at both rates. Release times:

| λ/λ_ref | stationary composition: μ(20) | release (s) | composition-adjusted: μ_cap | hit during drain | release (s) | registered limit |
|---|---|---|---|---|---|---|
| 1.35 | 0.216 | ≈ 3440 | 0.163 | 0.77 | ≈ 4430 | 7200 s |
| 1.65 | 0.216 | ≈ 3890 | 0.167 | 0.79 | ≈ 5570 | 7200 s |

After release the state is n_1 = 8.5 and 10.4, inside the basin, so it stays good (fluid). Predicted R1: PASS at both rates. Finite-size caveat: the composition-adjusted capped system runs at an effective population of about 28, close to n_u ≈ 32, so some runs could re-collapse during the drain.

**R4 (native, 4.0 × λ_ref, cap 64 at 2100 s).** About 327 sessions in the trap at 2100 s.
- Stationary composition: μ(64) = 0.488 > λ = 0.287, gate empty ≈ 3770 s, release ≈ 4070 s.
- Composition-adjusted: footprint inflation 1.34 puts 64 resumed sessions at an effective 86, near the native cliff, with μ_cap ≈ 0.282 < λ: no drain and no release by 7200 s.
- **Prediction: R4 is marginal.** Release by 7200 s is predicted only if resumed sessions behave like stationary ones; I put more weight on the adjusted bound, i.e. R4 likely FAILS the release criterion. This is the least reliable prediction here (heuristic F4).

## 6. Position against prior work
- **Yao, Gao, Lyu, Grosof, Simchi-Levi (arXiv 2609.02027).** Mean-field LRU for multi-turn conversations: Poisson arrivals, i.i.d. exogenous inter-turn gaps, capacity and arrival rate scaled together. Their characteristic time solves a strictly increasing equation of the same form as `μ D(R)` here (a linear term for all content plus a live term with ∫F̄), hence a unique fixed point and a closed-form hit ratio. They model no server, no queue and no running KV, and their Remark B.6 avoids the compute-bound regime by rescaling gaps. This model adds the running reservations `K_run(ν, h)` and the endogenous gap (W and S depend on h), which turns their unique fixed point into a curve with a rise, a peak, a cliff and an all-miss branch. Propositions 1–3, 5 and 6 are about exactly that loop.
- **MISA-T (Hong et al., 2608.11152).** §2.5 describes the eviction / cold-prefill / queue loop in words ("positive feedback loop"). §4.1 gives an informal prefill-saturation bound `F/E[L_r − H_r]`. Its adaptive session cap follows session length and a hit-rate gap. It has no model of equilibria, hysteresis or bursts; Prop. 3 and Prop. 6 quantify the loop it describes, and Prop. 7 states when a cap rescues.
- **Che approximation.** Used here only in its exact LRU-frontier form (Lemma in §1.3). The eviction age R is set by a memory balance with running reservations and dead KV, not by an IRM popularity law.
- **Denning thrashing; Courtois (CACM 1975).** The closed curve is a thrashing curve. Courtois, per the abstract we could read, located unstable operating regimes and critical loads of multiprogrammed paging systems by decomposition; in this model the closed system has no fold (Prop. 4 with the numerical check). The instability is in the open system, as in Prop. 5, and it comes from the FCFS queue making the reuse gap grow with the backlog (Prop. 8: gap/R = total context / pool). The specific new content: a predicted curve from independent inputs, the s·z̄ window law with its GPU-speed consequence, and the round-robin identity.
- **Metastable-failure models.** Bronson et al.; Isaacs et al. (HotOS '25: stress tests, DES and CTMCs, metastability as a CTMC that stays in a subset for long); Habibi et al. (SRDS '24, MSF-Model: queueing, Markov chains and Monte Carlo for retry-driven failures, "orbit space"); Farahbakhsh et al. (HotNets '25: token-flow components, weakly and strongly metastable states). All are generic or retry-centred, none models cache-hit feedback quantitatively, and none predicts a measured threshold from first principles. Prop. 5 is a standard phase-line result once μ(n) is known; the novelty is that μ(n), the trap growth rate and the trapped gap/R are predicted for this system.

## 7. Weaknesses (honest list)
1. No convergence theorem connects the stochastic engine (or the simulator) to the fluid model. Every "proved" statement is about the model.
2. The prefill latency ignores queueing behind other prefills (A2a). At k = 1 near the cliff the M/G/1 wait is seconds, which would add to the idle time and steepen the cliff. It might even create a fold; this was not explored.
3. Whole-session LRU, full reservation and stationary turn mix are simplifications. SGLang evicts radix leaves and reserves decode tokens by a ratio; vLLM allocates on demand, preempts and recomputes, and evicts blocks tail-first. The vLLM cliff (earlier and steeper, with a sub-λ_miss dip at n = 32–48) is not reproduced and is attributed, untested, to those mechanisms.
4. μ_max is 6% high in sessions/s and 9–10% in turns-based units on both SGLang cells. The F1 fluctuation layer fixes most of that, but it is a heuristic.
5. F2 (edge) and F3 (burst) rest on a one-dimensional reduction that the math check showed is not valid near the cliff as a dynamical statement. Their success on two of three cells may partly be luck. The H200 and Llama predictions test them out of sample.
6. The H200 prediction assumes uniform cost scaling, fitted to a single E0a number. A decode-side sensitivity changes the window by 6% and the edge by 4%. Under-predicting the POP-64 ratio (1.019 vs 1.046) suggests the H200's real decode speed-up is smaller than its prefill speed-up; the decode2 variant (1.029) points that way.
7. The rescue predictions (F4) depend on the paused sessions' age through a crude footprint estimate. R4 is called "marginal" for that reason.
8. "No internal bistability" is numerical, for separate mode over a grid of M and z̄. The measured degraded excursions at n = 24 and 32 are not explained by a theorem.
9. The fluid curve is flat at μ_b beyond n_b. The measured n = 300 values are higher (a synchronized-start transient, LOG 2026-10-22), and the turns-based values at n = 48 (0.063, against 0.072) are below; neither is modelled.

## 8. Files
- `analysis/theory/fluid_rigorous/model.py`: workload, costs, fluid server (separate and mixed), LRU balance, solution curve, feedback map, open equilibria, critical burst, rescue (attrition cap), window bounds and law, annealed curve.
- `edge.py`: F2. `trapped.py`: round-robin trap and the loopvars re-implementation. `cells.py`: inputs and measured targets. `oos.py`: blind predictions. `run_all.py`: everything.
- `tests/test_theory_fluid_rigorous.py`: constants equal calibration.yaml; workload moments; Lemma 1 monotonicity and the blow-up at capacity; LRU KV-time monotone; curve end points; the stability criterion against the feedback map, and C2; exact time rescaling; window decreasing in z̄ and s; upper bound ≥ window; phase-line ordering; round-robin identity; escape probability increasing in λ; regression of the quoted 300k numbers.
- Results: `results/theory/fluid_rigorous/{cells_comparison.csv,json, curve_*.csv, measured_vs_predicted_*.csv, edge_*.csv, trapped_and_good_runs.csv, window_scaling.csv, fold_scan_separate.csv, fluid_vs_stochastic_simulator_300k.csv, diagnostics.json, blind_predictions.json, meta.json}`.
- Figures: `figures/theory/fluid_rigorous_{closed_curves, from_empty_edge, window_scaling, trapped, feedback_map, blind_cells}.{png,pdf}`.
