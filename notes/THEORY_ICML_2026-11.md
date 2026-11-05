# The trap obeys a supercritical renewal equation: exact dynamics of a thrashed prefix-cached engine

Written 2026-11-05 on branch `claude/theory-icml-2164a9` (cut from `r10/arxiv` at `8aaabdb`) by a theory session started
from the lead session "Nova preprint scoop assessment". Code: `analysis/theory/icml/`. Frozen predictions:
tag `icml-trap-pred` (`6b47a6c`), `configs/icml_trap_predict.yaml`, `notes/PREDICTIONS_icml_trap.md`.
Draft LaTeX (not wired into `main.tex`): `paper/sections/theory_icml.tex`, `paper/sections/appendix_icml.tex`.

**Blindness and inputs.** Only committed data pulled on or before 2026-11-01 (`results/nova/`), the paper at `8aaabdb`, our
theory notes and code, and the text of Lu et al. (arXiv:2611.02543, read as data) were read. No Nova result newer than
2026-11-04 was opened; nothing on Nova was touched.

## 0. Summary

**What is proven (complete proofs in section 4).** Model the trapped engine as the paper already describes it in words:
every turn misses, the GPU never idles, and requests are served in the order they join (request-level FCFS). Turn k of a
session costs c_k all-miss GPU seconds, and a session has T turns, with G_k = P(T >= k).

- **Theorem 1 (the trap obeys a renewal equation).** Along every FIFO orbit u, f(u), f(f(u)), ... (a request that joins at u
  completes at f(u) = u + V(u), V being the pending work), the cycle Delta_n = V(u_n) solves the *linear* renewal recursion
  Delta_n = sum_k lambda c_k G_k Delta_{n-k} + h_n, with h_n = 0 for n >= K.
  Let rho = lambda / lambda_miss (lambda_miss = 1 / sum_k c_k G_k), and let z solve lambda sum_k c_k G_k z^{-k} = 1.
  - **Trichotomy.** The trap drains in finite time iff rho < 1 (a busy period V_tot / (1 - rho)), stays bounded at rho = 1,
    and grows for rho > 1.
  - **Growth (rho > 1).** The cycle grows linearly at slope gamma = z - 1. More precisely, it becomes proportional to
    the total remaining work, V ~ (gamma/(rho - 1)) V_tot, i.e. to the trap's age counted from its virtual origin
    -V_tot(0)/(rho - 1). In our cells the error vanishes absolutely. The backlog grows at alpha = lambda (1 - E z^{-T}).
    Sessions complete at D = lambda E z^{-T}.
  - **Composition (rho > 1).** The sessions present, and the turns served, follow the z-tilted turn mix G_k z^{-k}.
  - **Self-similarity.** With c = V_tot(0)/(rho - 1), a session that arrives at time u finishes at about
    (u + c) z^T - c.
  - **Near the threshold.** alpha / (lambda - lambda_miss) -> E[T] / kbar_c, with kbar_c the cost-weighted mean turn index.
- **Theorem 2 (youth premium).** D / lambda_miss = H(z) Gamma(z).
  - H depends only on the turn-count law: H = 1 for a geometric T, and lies in [1 - q^K, 1] for the truncated geometric.
  - Gamma depends on the cost growth: Gamma >= 1 for non-decreasing costs, with equality only for constant costs.
  - Near the threshold, D / lambda_miss - 1 = (rho - 1)(1 - E[T] / kbar_c) + O((rho - 1)^2).
  - So a trapped engine completes sessions *faster* than its all-miss capacity while its backlog diverges. This is not
    automatic: under truncation, slowly growing costs can reverse it (Theorem 2(v)).
  - For the paper's workload, in all eight cells, the premium is positive at every z >= z_1 (rho >= 1.04), by
    Theorem 2(vi). On [1 + 10^{-12}, z_1] a monotone bracket gives it too (H falls and Gamma rises in z; evaluated in
    floating point, not interval arithmetic). Below that it holds to first order (section 6.1).
- **Corollary 3 (what trapped throughput does not tell; fluid).** Only an arrival rate below lambda_miss clears the trap,
  after a busy period V_tot / (1 - lambda'/lambda_miss). A cut to anything in (lambda_miss, D(lambda)) does not clear it,
  even though that rate is below the throughput an operator measures in the trap. In the all-miss fluid at 1.65x on the
  300k cell, such a cut makes the backlog dip by 0.3-5.5% and then grow again. A cut to exactly lambda_miss undershoots by
  6.7% and settles 5.1% below the starting backlog.
- **Corollary 4 (invariance).** z, gamma, alpha / lambda_miss, D / lambda_miss and the trapped composition depend on the
  cell only through rho, the turn-count law G and the cost-weighted turn mix omega_k = c_k G_k / sum_j c_j G_j. They are
  invariant under a uniform GPU speed-up, and the pool enters only through the all-miss decode share in c_k.

**What is checked (section 6; retrospective, no parameter fitted to any trap measurement).** vLLM, the H200 and Llama
each take one speed factor fitted to their own E0a token rate, as in the paper. The check covers 57 *stuck* E2-protocol
runs (follow-up hit below 0.2 over the evaluation window, the paper's STUCK) in 20 (cell, rate) groups, and 13 unstable
E0b runs. These span eight cells: SGLang 300k (FCFS with and without waiting-prefix refresh; BASIN; SHED; TOOLSLOW; LPM
past its 128-request fallback), the native pool, vLLM, the H200 at 300k and 600k, Llama-3.1-8B, and the 150k/600k pool sweep.
- The mean prompt of the turns served in the trap matches the tilted-mix prediction within -6.6% to +7.7%: within +-3%
  in 50 of the 57 runs and within +-5% in 54. The prediction spans 6,115 to 9,393 tokens in the E2-protocol runs, and
  5,064 to 9,233 in the E0b runs: young, short turns, with no free parameter.
- The gap between a session's consecutive turns grows linearly in time at the predicted slope gamma, from 0.012 to 0.13
  per second across cells. Measured over predicted, the ratio has mean 0.94 and median 0.98 in the E2 runs, and spans
  0.62-1.30 in the E0b runs.
- Every stuck run completes sessions above lambda_ref, at 1.10-2.40 lambda_ref. The paper noted this excess
  qualitatively; Theorem 2 quantifies it (the youth premium).
- Across the 57 runs the backlog slope averages 0.63 of lambda - lambda_ref, as alpha predicts. The paper's heuristic RR
  layer already gave 0.63-0.64 numerically at 300k. The paper does not use Eq. (fluid), which would give 1.0, for growth in
  congestion. What is new is the exact law and its extension to every cell.
- The registered trap test's fragility at the low rate is explained, post hoc. The true slope (about 0.63
  (lambda - lambda_miss)) sits just above the rule's threshold of 0.5 (lambda - lambda_ref).
  - Under common random numbers, seed 1's plan has a window arrival rate 5.8% (300k), 7.9% (vLLM) and 8.9% (Llama) below
    nominal at 1.35x.
  - The per-seed plug-in lambda_window(plan) - D, computable before any run, falls on the same side of the registered
    threshold as the measured slope for 27 of 30 independent plans (33 of 36 runs counting the vLLM exploratory
    repeats). Always predicting "trapped" scores 23 of 30.
  - Two of the three exceptions have a plug-in within 0.0001 /s of the threshold. The third is Llama 1.35x seed 0, at the
    registered FAIL point.

**Why this direction (section 1).** It is the only one of the candidates whose central object, the trapped state, neither
our paper nor Lu et al. nor the classical metastability literature characterizes. It is provable with elementary tools,
and it is tested by existing data across eight cells, with no parameter fitted to any trap measurement.

## 1. Choice of direction

The four candidates from the brief, judged on novelty x rigor x testability:

1. *Stochastic metastability (LDP / Eyring-Kramers / committor).* For the one-dimensional birth-death chain with rates
   lambda and mu(n), the exit-time asymptotics are textbook (Freidlin-Wentzell, the birth-death quasi-potential
   sum log(mu/lambda)). Bistable ALOHA channels were analysed this way by Carleial-Hellman and Kleinrock-Lam. A theorem at
   that level would not be clearly distinct from the classical results the brief excludes. A version that is distinct would
   need an LDP for the full KV-composition dynamics, which is a research programme, not a proof for this session. The
   paper's heuristics F2/F3 already carry the diffusion and committor ideas.
2. *Optimal rescue control.* In the quasi-static one-dimensional model the time-optimal cap is trivially the argmax of
   mu: Denning-style load control at the knee, which is classical. The non-trivial parts (composition inflation of resumed
   sessions, R4's late release) are messy and would be hard to make rigorous in a session.
3. *Phase diagram.* In colocated prefill-priority serving, decode saturation and cache eviction share one pool, so Lu et
   al.'s cache-first/decode-first split collapses. That is interesting but modest; the window-opening criterion is already
   Proposition 7 / T5.
4. *Learning the cap.* Safe unimodal bandits are a fit for ICML, but disconnected from our data.

**Chosen instead: the trapped state itself.** The paper says Eq. (fluid) "is not quantitative in congestion, and not only
transiently"; it explains the trapped engine's above-capacity completions in words ("for as long as the backlog grows")
and handles the trap with a numerical heuristic (the round-robin layer RR). Lu et al. measure a trapped departure rate
D_low in simulation and treat it as a property of the curve. Classical metastable-failure models have a bad *state*, not a
bad *growth law*. The renewal structure below is exact within its model, provable in a page, has no parameter fitted to
any trap measurement, and can be checked on every stuck run we have.

## 2. Model F (the trap)

Constants:
- K, the largest turn count (60 in the workload).
- c_1, ..., c_K > 0: all-miss GPU seconds of turn k. In the code (`trap_costs`), c_k is the calibrated miss prefill of P_k
  tokens plus the all-miss per-turn decode share delta. delta is chosen so that sum_k (G_k / E[T]) c_k = 1 / nu_b (the GPU
  is fully used at the all-miss rate); in separate mode delta = (1 - p_b) / nu_b, exactly the RR layer's decode share. Then
  1 / sum_k c_k G_k equals the model's mu_b, the all-miss capacity of Proposition 2(a) of the paper.
- G_1 = 1 >= G_2 >= ... >= G_K > 0, G_{K+1} = 0, with G_k = P(T >= k). Write p_k = G_k - G_{k+1} = P(T = k) and
  r_k = G_{k+1} / G_k for the continuation probability after turn k.
- lambda > 0; a_k = lambda c_k G_k; rho = sum_k a_k = lambda / lambda_miss, with lambda_miss = 1 / sum_k c_k G_k.
- Remaining all-miss work of a session whose next turn is k: R_k = sum_{j >= k} c_j G_j / G_k (so R_1 = 1 / lambda_miss and
  R_k = c_k + r_k R_{k+1}).

Assumptions (fluid; time 0 is any instant at which the engine is trapped):
- **(F1) All-miss.** Every turn misses: turn k costs c_k.
- **(F2) Work conservation.** The GPU does one GPU-second of work per second while work is pending.
- **(F3) Request-level FIFO.** Requests complete in the order they join the queue.
- **(F4) Zero think time.** When turn k < T completes, turn k+1 of the same session joins at once. A fraction r_k of the
  class-k mass completing at any time re-joins as class k+1.
- **(F5) Arrivals.** New sessions join as class-1 mass at constant rate lambda.
- **(F6) Initial state.** At time 0 a pending mass m_k^0 >= 0 of class-k requests (k = 1..K), with
  V_0 = sum_k c_k m_k^0 > 0. It is served first, in a fixed order: absolutely continuous non-decreasing class-completion
  functions C_k^0 on [0, V_0] with sum_k c_k C_k^0(t) = t and C_k^0(V_0) = m_k^0.

Definition (solution). Non-decreasing absolutely continuous J_k, C_k on [0, tau) (joins and completions after time 0,
k = 1..K, with C_k^0(0) = 0) and f(u) = u + V(u) such that:
- J_1(t) = lambda t and J_{k+1} = r_k C_k;
- C_k = C_k^0 on [0, V_0], and C_k(f(u)) = m_k^0 + J_k(u) for u >= 0 (FIFO);
- sum_k c_k C_k(t) = t for t < tau (F2, work conservation);
- V(u) = sum_k c_k (m_k^0 + J_k(u) - C_k(u)) > 0 on [0, tau) (busy);
- maximality: either tau = infinity or V(t) -> 0 as t increases to tau.

Here tau <= infinity is thus the time the queue first empties, and the last condition excludes restrictions of a solution
to a shorter interval. Sessions present: with zero think time every session present has
exactly one pending request, so N(t) = sum_k pi_k(t) with pi_k = m_k^0 + J_k - C_k. Total remaining work:
V_tot(t) = sum_k pi_k(t) R_k. Departures: Dep(t) = sum_k m_k^0 + lambda t - N(t).

What model F leaves out:
- Concurrency: the engine runs about M/E_S ~ 28 requests at once, so completion order is not exactly FIFO.
- The 5 s tool time (Remark 7: no visible effect).
- Retraction and preemption (vLLM preempts).
- The transition into and out of the trap: hits return when the backlog falls toward n_b.

There is no limit theorem from the engine to model F; the same caveat applies to every proposition in the paper.

## 3. Statements

**Lemma 1 (Perron root).** phi(x) = sum_k a_k x^{-k} is continuous and strictly decreasing on (0, infinity), with
phi(0+) = infinity, phi(infinity) = 0 and phi(1) = rho. So phi(z) = 1 has a unique root z > 0, with z > 1 iff rho > 1 and
z = 1 iff rho = 1.

**Lemma 2 (well-posedness, work identity, orbit recursion).** Under (F1)-(F6):
- (i) Model F has exactly one solution.
- (ii) While busy, f(u) = V_0 + W(u), where W(u) = sum_k c_k J_k(u) is the work that has joined since time 0. f is
  continuous and strictly increasing, and f(u) >= V_0.
- (iii) While busy, V_tot(t) = V_tot(0) + (rho - 1) t.
- (iv) Fix u_0 in [0, V_0), let u_{n+1} = f(u_n) and Delta_n = u_{n+1} - u_n = V(u_n). Then for n >= 0
  Delta_n = sum_{k=1}^{min(n, K)} a_k Delta_{n-k} + h_n(u_0), with
  h_n(u_0) = sum_{k=n+1}^{K} c_k (G_k / G_{k-n}) pi_{k-n}(u_0) for n <= K - 1 (in particular h_0 = V(u_0)), and h_n = 0 for
  n >= K. Each h_n(u_0) >= 0 depends continuously on u_0, and sum_{n >= 0} h_n(u_0) = V_tot(u_0).
- (v) The pending class-k mass at u_n (n >= 1) is pi_k(u_n) = lambda G_k Delta_{n-k} if k <= n, and
  (G_k / G_{k-n}) pi_{k-n}(u_0) if k > n. The requests completed in (u_n, u_{n+1}] are exactly those pending at u_n.

**Theorem 1 (the trap obeys a renewal equation).** Under (F1)-(F6):
- (a) **Subcritical.** If rho < 1, the queue empties at tau = V_tot(0) / (1 - rho) and is busy before. This is the fluid
  busy period.
- (b) **Critical.** If rho = 1, V(t) -> V_tot(0) / kbar_c and N(t) -> lambda E[T] V_tot(0) / kbar_c as t -> infinity,
  where kbar_c = sum_k k c_k G_k / sum_k c_k G_k.
- (c) **Supercritical growth.** If rho > 1, let z > 1 be the Perron root and gamma = z - 1. Then as t -> infinity:
  - V(t) / t -> gamma (the cycle, i.e. the FIFO wait of a request that joins at t);
  - N(t) / t -> alpha = lambda (1 - E[z^{-T}]);
  - Dep(t) / t -> D = lambda E[z^{-T}];
  - the class mix of the pending requests, and of the requests completed in (t, f(t)], tends to
    pi^z_k = G_k z^{-k} / sum_j G_j z^{-j};
  - for any per-turn weights P_k (e.g. prompt tokens), the P-weighted work completed over a cycle (t, f(t)], divided by
    the cycle's length, tends to sum_k P_k G_k z^{-k} / sum_k c_k G_k z^{-k}.
- (d) **Self-similarity.** f(u)/u -> z, and f^m(u)/u -> z^m for each fixed m. A session that arrives at u with T = m
  turns completes at f^m(u). More precisely, with c = V_tot(0)/(rho - 1), f^m(u) + c = z^m (u + c)(1 + o(1)).
- (e) **Near the threshold.** As rho -> 1+: gamma = (rho - 1)/kbar_c + O((rho - 1)^2), and
  alpha = lambda_miss (E[T]/kbar_c)(rho - 1) + O((rho - 1)^2). In particular alpha / (lambda - lambda_miss) -> E[T]/kbar_c.
- (f) **The cycle is proportional to the remaining work** (pointed out by the Theorem 1 referee). For u >= b_{K-1} (all
  descendants of the initial requests have joined),
  f(u) = V_tot(0) + sum_k a_k f^{-(k-1)}(u),
  so along every orbit u_{n+1} = V_tot(0) + sum_k a_k u_{n+1-k}. For rho != 1, w_n = u_n - V_tot(0)/(1 - rho) solves the
  homogeneous recursion. Hence:
  - if rho < 1, u_n -> V_tot(0)/(1 - rho) = tau, which is part (a) again;
  - if rho > 1, V(u_n) = (gamma/(rho - 1)) V_tot(u_n) + O((r + epsilon)^n) for every epsilon > 0, where r is the largest
    modulus among the non-Perron roots of x^K = sum_k a_k x^{K-k}.

  In all eight cells, over rho in [1.01, 6.6], numerical root-finding gives r = 0.946-0.966 < 1. So the deviation from
  proportionality vanishes absolutely. In the exact fluid, the ratio V/((gamma/(rho - 1)) V_tot) over the registered window
  is 0.99-1.03 at 1.35x and 0.99-1.01 at 1.65x (300k).

**Theorem 2 (youth premium).** In Theorem 1(c), let nu_k = G_k / E[T] (the stationary turn mix) and nu^z_k = pi^z_k (the
trapped mix).
- (i) **Decomposition.** D / lambda_miss = H(z) Gamma(z), where
  H(z) = E[T] E[z^{-T}] / sum_k G_k z^{-k} = E[T](z - 1) E[z^{-T}] / (1 - E[z^{-T}]) and
  Gamma(z) = E_nu[c] / E_{nu^z}[c].
- (ii) **Cost growth.** If c is non-decreasing in k and z > 1, then Gamma(z) >= 1, with equality iff c is constant. The
  strictness uses the strict likelihood ratio (z > 1) and the full support of nu, which holds because G_K > 0.
- (iii) **Turn-count law.** H(z) >= 1 iff E[z^{-T}] >= 1 / (1 + E[T](z - 1)), which is the value for a geometric turn
  count on {1, 2, ...} with the same mean. For T = min(Geometric(1 - q), K):
  H(z) = 1 - q^K (1 - E[T] z^{-K} / sum_k G_k z^{-k}). For z > 1 and K >= 2 this lies strictly in (1 - q^K, 1), and it is
  non-increasing in z.
- (iv) **Near the threshold.** D / lambda_miss - 1 = (rho - 1)(1 - E[T]/kbar_c) + O((rho - 1)^2). So, close to the
  threshold, the trapped completion rate exceeds lambda_miss if kbar_c > E[T] and falls below it if kbar_c < E[T]. If
  kbar_c = E[T], the sign is set by higher-order terms and can go either way.
- (v) For geometric T on {1, 2, ...} (taking K = infinity when the sums converge) and costs that are non-decreasing and
  not constant, the formulas give D > lambda_miss and alpha < lambda - lambda_miss for every lambda > lambda_miss.
  Theorem 1 itself is proved for finite K. **This does not survive truncation in general.** With
  T = min(Geometric(1/15), 60) and the slowly growing costs c_k = 1 + 10^{-3}(k - 1), the premium is negative at every rho
  the Theorem 2 referee checked: -4e-4 at 1.01, -9.4e-3 at 1.65, -3.3e-3 at 100. For the workload, see (vi).
- (vi) **Monotonicity.** If c is non-decreasing, Gamma(z) is non-decreasing in z, and strictly increasing if c is not
  constant. Its supremum, approached as z -> infinity, is E_nu[c]/c_1. Take T = min(Geometric(1 - q), K) and suppose
  E_nu[c]/c_1 > 1/(1 - q^K). Then there is a unique z_1 with Gamma(z_1) = 1/(1 - q^K), and the premium
  D/lambda_miss - 1 is positive for every z >= z_1. Strictness comes from H > 1 - q^K.

**Corollary 3 (recovery threshold; what trapped throughput does not tell; fluid).** Let the engine be in model F at load
lambda from time 0, and switch the arrival rate to lambda' at a time t_0 with V(t_0) > 0. Put rho' = lambda' / lambda_miss.
- If lambda' < lambda_miss, the queue empties at t_0 + V_tot(t_0) / (1 - rho').
- If lambda' > lambda_miss, N(t)/t -> alpha(lambda') > 0.
- If lambda' = lambda_miss, N(t) -> lambda_miss E[T] V_tot(t_0)/kbar_c > 0, and V >= eta V_tot(t_0) > 0 throughout.

The threshold is lambda_miss, the closed-system all-miss capacity at the *stationary* turn mix. It is not the trapped
departure rate D(lambda) that an operator observes. Whenever the premium is positive, a cut to lambda' in
(lambda_miss, D(lambda)) does not clear the trap, although lambda' is below the throughput measured in it. The closed
endpoint lambda' = lambda_miss belongs only to the fluid. There the fluid backlog stays positive, but a stochastic queue at
rho' = 1 empties almost surely, and just above it emptying is not rare (Remark 5).

**Corollary 4 (invariance).** z solves rho sum_k omega_k z^{-k} = 1 with omega_k = c_k G_k / sum_j c_j G_j. Therefore z, gamma,
the trapped composition, alpha / lambda_miss and D / lambda_miss are functions of (rho, omega, G) alone. They do not change
when every c_k is divided by s (a uniform GPU speed-up) and lambda is scaled to keep rho. gamma is dimensionless (seconds
of wait per second of trap age). So at equal rho, two engines whose cost vectors are proportional have gaps that grow at
the same slope. Our H200 cell models are a uniform speed-up of the A100 costs, so this holds for them, but it is not a
general hardware claim.

**Remark 5 (stochastic version; classical).** Take Poisson arrivals, i.i.d. T, deterministic costs c_k, any
work-conserving order and zero think time.
- The all-miss server's busy period, started from realized remaining works w_1, ..., w_n, is the total work of a
  Galton-Watson tree. Each ancestor begets Poisson(lambda w_i) sessions, and each later session Poisson(lambda W(T)) more,
  W(T) being its total work. The busy period is finite iff the tree's progeny is.
- So the queue ever empties with probability exp(-lambda (1 - q) sum_i w_i), where q is the least root in [0, 1] of
  q = E[exp(-lambda W(T) (1 - q))] (Kendall 1951; Takacs 1962). With rho > 1, q < 1.
- The workload ever falls to a level w_b with probability exp(-lambda (1 - q)(sum_i w_i - w_b)). This is the better proxy
  for a spontaneous exit from the trap, since hits return once the backlog is small, before the queue empties.
- If only the sessions' current turns are known, not their realized remaining works, the probability is a product of
  transforms over the remaining turn counts.

For the 300k cell, take w = V_tot of the exact fluid 3000 s after the registered burst (`support.py`, `kendall_numbers`).
In the fluid, that is V_tot(0) + (rho - 1)t by Lemma 2(iii). The probability that the queue ever empties is then:

| rho | 1.01 | 1.02 | 1.05 | 1.10 | 1.35 | 1.65 |
|---|---|---|---|---|---|---|
| P(empties) | 0.35 | 0.12 | 4e-3 | 1e-5 | 4e-23 | 3e-54 |

These are orders of magnitude: a realized w fluctuates around the fluid value. A spontaneous exit therefore matters only
within a few percent of lambda_miss. We state this for orientation and claim nothing new.

**Remark 6 (processor-sharing variant = the paper's RR layer).** The paper's RR layer advances every session continuously,
1/theta(t) turns per second; this is processor sharing in the turn clock.
- With the time change x = Phi(t) = int_0^t ds / V(s), the analogous argument gives the continuous renewal (Euler-Lotka)
  equation lambda sum_k c_k G_k int_{k-1}^{k} e^{-g a} da = 1 and alpha_PS = lambda (1 - E e^{-g T}).
- This argument needs the continuous renewal theorem, not the finite-memory lemma: the kernel is a step function with
  compact support, hence non-lattice. We do not write it out.
- This is the Grishechkin/Crump-Mode-Jagers structure of overloaded processor sharing, with an age-dependent reproduction
  rate lambda c_{floor(a)+1}.
- Its cycle slope is gamma_PS = g. Near the threshold, alpha_PS / (lambda - lambda_miss) -> E[T]/(kbar_c - 1/2).

The roughly 2% difference from model F is this half-turn offset, kbar_c/(kbar_c - 1/2) = 1.02. On the 300k cell,
alpha / (lambda - lambda_miss) is 0.647 vs 0.634 at 1.35x and 0.666 vs 0.653 at 1.65x. The Theorem 2 referee confirmed
both numbers with an independent event-driven processor-sharing simulation. Model F, with atomic turns in FIFO order, is
the closer description of request-level FCFS.

**Remark 7 (think time).** With a 5 s think time (the workload's mean tool time) the exact fluid's statistics over the
registered window agree with zero think time: backlog slope, completion rate and mean served prompt to 4 significant
digits. The mean cycle is 5 s shorter, the cycle slope the same (`numerics_support` in section 7).

**Remark 8 (how fast the limits are reached).** The limits of Theorem 1(c) are approached geometrically in the generation
index. The transient shrinks by the factor theta = r/z per generation, where r is the largest modulus among the non-Perron
roots.
- For our cells theta = 0.84-0.95 over rho in [1.01, 6.6].
- At 300k (the FIFO-orbit probe of the exact fluid), the registered window starts about 33 (1.65x) or 37 (1.35x)
  generations after the burst, so a transient of order theta^35, about 0.1, remains.
- That is why section 6 reports both the asymptotic values and the exact fluid over the window. The two differ by about 1%
  for the composition and by 4-12% for the backlog slope (1.65x / 1.35x on 300k).
- No general rate is claimed. A nearly periodic kernel converges very slowly: the Theorem 1 referee's toy with T = 4
  always is still 3% off after 1000 generations.

## 4. Proofs

**Proof of Lemma 1.** Each term a_k x^{-k} is positive, continuous and strictly decreasing on (0, infinity), and
a_1 x^{-1} -> infinity as x -> 0+. Every term tends to 0 as x -> infinity, and phi(1) = sum_k a_k = rho. So phi is a
strictly decreasing bijection (0, infinity) -> (0, infinity). Its unique root z satisfies z > 1 iff phi(1) > 1, and
z = 1 iff rho = 1.

**Proof of Lemma 2.**

*(ii) and the construction.* Suppose the server is busy on [0, f(u)]. By (F2), the work completed by any time s in
that interval is exactly s. Under FIFO, the request joining at u completes once all work that joined before it is done:
the initial V_0 plus W(u). Hence f(u) = V_0 + W(u). Since J_1(u) = lambda u and the other J_k are non-decreasing,
W' >= lambda c_1 > 0 a.e. So f is continuous and strictly increasing, and f(0) = V_0.

Define the generations b_0 = 0, b_1 = V_0, b_{n+1} = f(b_n). We build the solution generation by generation.
- *Generation 0 ([0, V_0]).* Completions are the initial ones, C_k = C_k^0. Re-entries are J_{k+1} = r_k C_k^0 and
  J_1 = lambda t. So W, and with it f = V_0 + W, is determined on [0, V_0]. It maps [0, V_0] onto [V_0, b_2].
- *Induction step.* Suppose the J_k are known on [0, b_n] and f is known on [0, b_{n-1}], mapping onto [b_1, b_n]. Then f
  on [b_{n-1}, b_n] is V_0 + W, which is known. FIFO gives the completions on [b_n, b_{n+1}]: C_k(f(u)) = m_k^0 + J_k(u)
  for u in [b_{n-1}, b_n]. Re-entry then extends J_{k+1} = r_k C_k to [b_n, b_{n+1}], and J_1 is explicit.

*Uniqueness.* Every step is forced by the definition: FIFO, re-entry, the arrival rate and (F2), which gives f = V_0 + W
by the argument above. So the solution is unique, generation by generation.

*Existence.* Each step involves only finitely many continuous monotone functions. Two facts make the constructed object a
solution:
- sum_k c_k C_k(f(u)) = V_0 + W(u) = f(u), so the constructed completions satisfy sum_k c_k C_k(t) = t. That is, the
  constructed f equals u + V(u).
- V(f(v)) = W(f(v)) - W(v) >= lambda c_1 V(v) > 0, so b_{n+1} > b_n, and the server stays busy as long as V_tot > 0 (below).

Absolute continuity holds by induction: C_k(f(u)) = m_k^0 + J_k(u) gives C_k' = J_k'(u) / f'(u) <= J_k'(u) / (lambda c_1).

*Busy throughout, and tau.* While the server is busy, (iii) below holds; it needs only sum_k c_k kappa_k = 1, which the
construction builds in, so the argument is not circular. Also V(t) >= eta V_tot(t), where eta = min_k c_k / R_k > 0: V and
V_tot are linear in the pending masses, with coefficients c_k and R_k.
- If rho >= 1, then V_tot(t) >= V_tot(0) > 0, so V >= eta V_tot(0) > 0 throughout. Each generation then lasts at least
  eta V_tot(0), so b_n -> infinity and the construction covers [0, infinity).
- If rho < 1, V_tot reaches 0 at V_tot(0)/(1 - rho). Part (a) of Theorem 1 shows that this is the limit of the b_n.

*(iii) The work identity.* Write j_k = J_k' and kappa_k = C_k' (a.e.); then pi_k' = j_k - kappa_k. While busy,
sum_k c_k kappa_k = 1. Since j_1 = lambda, j_{k+1} = r_k kappa_k and R_k = c_k + r_k R_{k+1},
V_tot' = sum_k R_k (j_k - kappa_k) = lambda R_1 + sum_k kappa_k (r_k R_{k+1} - R_k) = lambda R_1 - sum_k c_k kappa_k
= rho - 1.

*(iv) and (v).* Write DeltaJ_k(n) = J_k(u_n) - J_k(u_{n-1}) for the class-k mass joining in (u_{n-1}, u_n].
- By (ii), for n >= 1, Delta_n = f(u_n) - f(u_{n-1}) = W(u_n) - W(u_{n-1}) = sum_k c_k DeltaJ_k(n). Also
  Delta_0 = V(u_0) = sum_k c_k pi_k(u_0).
- Class 1: DeltaJ_1(n) = lambda Delta_{n-1}.
- Class k >= 2, n >= 2: FIFO gives C_{k-1}(u_n) = C_{k-1}(f(u_{n-1})) = m_{k-1}^0 + J_{k-1}(u_{n-1}), and likewise at
  u_{n-1}. So DeltaJ_k(n) = r_{k-1} DeltaJ_{k-1}(n-1).
- Class k >= 2, n = 1: C_{k-1}(u_1) - C_{k-1}(u_0) = m_{k-1}^0 + J_{k-1}(u_0) - C_{k-1}(u_0) = pi_{k-1}(u_0). So
  DeltaJ_k(1) = r_{k-1} pi_{k-1}(u_0).
- Iterating, and using prod_{j=k-n}^{k-1} r_j = G_k / G_{k-n}:
  DeltaJ_k(n) = lambda G_k Delta_{n-k} if k <= n, and DeltaJ_k(n) = (G_k / G_{k-n}) pi_{k-n}(u_0) if k > n.
  Substituting into Delta_n = sum_k c_k DeltaJ_k(n) gives (iv).
- For (v): the requests pending at u_n (n >= 1) are those that joined by u_n minus those completed by u_n. The completed
  ones are the initial requests plus the joins by u_{n-1}, since u_n = f(u_{n-1}). So pi_k(u_n) = DeltaJ_k(n). The
  requests completed in (u_n, u_{n+1}] = (f(u_{n-1}), f(u_n)] are the joins in (u_{n-1}, u_n], by FIFO.
- *Continuity.* Each pi_j(u_0) is continuous in u_0, so each h_n is too.
- *Total.* Reindexing with j = k - n,
  sum_n h_n(u_0) = sum_j pi_j(u_0) sum_{n >= 0} c_{j+n} G_{j+n} / G_j = sum_j pi_j(u_0) R_j = V_tot(u_0).

**A renewal lemma (finite memory).** Let A(s) = sum_{k=1}^K b_k s^k with b_k >= 0, b_1 > 0 and A(1) = 1, and put
m_b = A'(1) = sum_k k b_k. Let y_n = sum_{k=1}^{min(n, K)} b_k y_{n-k} + g_n (n >= 0), with g_n >= 0, g_0 > 0 and
g_n = 0 for n >= K. Then y_n = L + epsilon_n with L = (sum_n g_n) / m_b > 0 and |epsilon_n| <= C_r theta^n for some
theta < 1. Here theta depends only on (b_k), and C_r is linear in (g_0, ..., g_{K-1}).

*Proof.* As formal power series, Y(s) = Gp(s) / (1 - A(s)), with Gp(s) = sum_{n<K} g_n s^n. The polynomial 1 - A(s) has
the root s = 1, and it is simple because A'(1) = m_b > 0.
- For |s| < 1: |A(s)| <= A(|s|) < A(1) = 1, so there is no root.
- For |s| = 1 and s != 1: A(s) = 1 = sum_k b_k forces s^k = 1 for every k with b_k > 0, including k = 1. So s = 1, a
  contradiction.

Hence every other root has modulus > 1; let theta_0^{-1} > 1 be the smallest such modulus (if there are none, every
theta_0 in (0, 1) works), and fix any theta in (theta_0, 1). Partial fractions give
Gp(s)/(1 - A(s)) = L/(1 - s) + Q(s). Here L = Gp(1)/A'(1) is the coefficient of 1/(1 - s), which is minus the residue
at s = 1. Q is a rational function with no poles in |s| < theta_0^{-1}, plus possibly a polynomial, which affects only
finitely many coefficients. Cauchy estimates on the circle |s| = theta^{-1} give |[s^n] Q| <= C_r theta^n, with C_r linear
in the coefficients of Gp. Finally L > 0 because g_0 > 0. []

(This is the finite-memory case of the discrete renewal theorem, Feller Vol. I, chapter on recurrent events; it is proved
here in full because K is finite.)

**Proof of Theorem 1.**

*(a) Subcritical.* Take u_0 = 0. By Lemma 2(iv), Delta_n = sum_k a_k Delta_{n-k} + h_n with all terms >= 0. Summing up to
M gives S_M := sum_{n<=M} Delta_n <= sum_n h_n + rho S_M. So S_M <= V_tot(0)/(1 - rho), and S_M converges. Summing the
whole recursion then gives sum_n Delta_n = V_tot(0)/(1 - rho) exactly. Hence b_n increases to
tau = V_tot(0)/(1 - rho) < infinity.

For every orbit start u_0 in [0, V_0), each Delta_n(u_0) > 0, because Delta_0 = V(u_0) > 0 and Delta_n >= a_1 Delta_{n-1}.
Every t < tau lies on such an orbit, so the server is busy on [0, tau), and V(b_n) = Delta_n -> 0. The work identity
confirms the value: V_tot(tau) = V_tot(0) + (rho - 1) tau = 0.

*No arrivals (lambda = 0; used for SHED and Corollary 3).* The orbit argument needs lambda > 0 (a_1 > 0, f strictly
increasing), so treat this case directly. While busy, V_tot' = -1 by (iii), and V >= eta V_tot > 0 while V_tot > 0. So the
queue empties exactly at tau = V_tot(0).

*(b) Critical.* Here z = 1. Apply the renewal lemma with b_k = a_k (sum = rho = 1) and g_n = h_n(u_0). Then
Delta_n(u_0) -> V_tot(u_0)/sum_k k a_k uniformly in u_0 in [0, V_0], because C_r is linear in the bounded, continuous h.
Since rho = 1, V_tot(u_0) = V_tot(0) by Lemma 2(iii), and sum_k k a_k = kbar_c at lambda = lambda_miss.

Every t >= V_0 equals u_n(u_0) for a unique u_0 in [0, V_0) and n >= 1: f^n maps [0, V_0) onto [b_n, b_{n+1}). So
V(t) -> V_tot(0)/kbar_c. By Lemma 2(v), N(u_n) = sum_k lambda G_k Delta_{n-k} for n >= K, which tends to
lambda E[T] V_tot(0)/kbar_c.

*(c) Supercritical.* Put y_n = Delta_n z^{-n}, b_k = a_k z^{-k} (sum = 1 by Lemma 1) and g_n = h_n(u_0) z^{-n}. The
renewal lemma gives y_n = L(u_0) + epsilon_n(u_0), with:
- L(u_0) = sum_n h_n(u_0) z^{-n} / sum_k k a_k z^{-k} > 0, continuous on [0, V_0];
- L >= L_min > 0, because h_0 = V(u_0) >= eta V_tot(0) > 0;
- |epsilon_n| <= C_r theta^n uniformly in u_0, since C_r is bounded in terms of V_tot(V_0).

For t = u_n(u_0):
- V(t) = Delta_n = z^n (L + epsilon_n).
- t = u_0 + sum_{j<n} z^j (L + epsilon_j) = L (z^n - 1)/(z - 1) + O(1 + n max(1, z theta)^n)
  = (L z^n / (z - 1)) (1 + O(n max(theta, 1/z)^n)).

So V(t)/t -> z - 1 = gamma uniformly in u_0. As t -> infinity, the generation index n of t tends to infinity, because
every b_n is finite. The lower bound on generation lengths only shows that the orbits cover [0, infinity).

*Population.* N(t) = sum_k lambda G_k Delta_{n-k} = lambda z^n sum_k G_k z^{-k} (L + o(1)), so
N(t)/t -> lambda (z - 1) sum_k G_k z^{-k}. The identity (z - 1) sum_k G_k z^{-k} = 1 - E[z^{-T}] follows from
sum_k G_k z^{-k} = E[sum_{k=1}^T z^{-k}] = E[(1 - z^{-T})/(z - 1)].

*Departures.* Dep(t) = sum_k m_k^0 + lambda t - N(t), so Dep(t)/t -> lambda - alpha = lambda E[z^{-T}].

*Composition.* By Lemma 2(v), pi_k(t) / N(t) = G_k Delta_{n-k} / sum_j G_j Delta_{n-j} -> G_k z^{-k} / sum_j G_j z^{-j}.
By (v), the requests completed in (t, f(t)] are the ones pending at t, so they have the same mix.

*Processing rate.* The P-weighted work completed in (t, f(t)] is sum_k P_k pi_k(t), and the elapsed time is
f(t) - t = V(t) = sum_k c_k pi_k(t). The ratio tends to sum_k P_k G_k z^{-k} / sum_k c_k G_k z^{-k}.

*(d) Self-similarity.* f(u)/u = 1 + V(u)/u -> 1 + gamma = z. Then
f^m(u)/u = prod_{i<m} f(f^i(u))/f^i(u) -> z^m, since f^i(u) -> infinity. A session that arrives at u joins as class 1 at u
and completes turn m at f^m(u) (zero think time, FIFO). The centred form follows from (f): u_n + c = w_n with
c = V_tot(0)/(rho - 1), and w_{n+m}/w_n -> z^m.

*(e) Near the threshold.* Write omega_k = c_k G_k / sum_j c_j G_j (the cost-weighted turn mix) and
F(x, rho) = rho sum_k omega_k x^{-k} - 1. Then F(1, 1) = 0 and d_x F(1, 1) = -sum_k k omega_k = -kbar_c != 0. By the
implicit function theorem z(rho) is analytic near rho = 1, with z'(1) = (sum_k omega_k)/kbar_c = 1/kbar_c. So
gamma = (rho - 1)/kbar_c + O((rho - 1)^2). Next, E[z^{-T}] = 1 - gamma E[T] + O(gamma^2), so
alpha = lambda gamma E[T] + O(gamma^2) = lambda_miss (E[T]/kbar_c)(rho - 1) + O((rho - 1)^2). Dividing by
lambda - lambda_miss = lambda_miss (rho - 1) gives alpha / (lambda - lambda_miss) -> E[T]/kbar_c.

*(f) The cycle is proportional to the remaining work.* Take u >= b_{K-1} = f^{K-1}(0). The class-k descendants of the
initial requests have then all joined: those of initial class j < k need k - j generations. So their contribution to
J_k(u) is the constant sum_{j<k} (G_k/G_j) m_j^0. The arrivals' class-k requests joined by u are those whose class-1
request joined by f^{-(k-1)}(u), so they contribute lambda G_k f^{-(k-1)}(u). Hence
W(u) = sum_k c_k sum_{j<k} (G_k/G_j) m_j^0 + sum_k a_k f^{-(k-1)}(u), and
f(u) = V_0 + W(u) = V_tot(0) + sum_k a_k f^{-(k-1)}(u), using sum_j m_j^0 R_j = V_tot(0).
At u = u_n this reads u_{n+1} = V_tot(0) + sum_k a_k u_{n+1-k}.

The constant V_tot(0)/(1 - rho) is a particular solution, so w_n = u_n - V_tot(0)/(1 - rho) solves the homogeneous
recursion, whose characteristic roots are the roots of x^K = sum_k a_k x^{K-k}.
- If rho < 1, all roots have modulus < 1 and u_n -> V_tot(0)/(1 - rho).
- If rho > 1, w_n = B z^n + O((r + epsilon)^n), because the other roots may repeat. Then
  V(u_n) = u_{n+1} - u_n = (z - 1) w_n + O((r + epsilon)^n), and V_tot(u_n) = V_tot(0) + (rho - 1) u_n = (rho - 1) w_n. []

**Proof of Theorem 2.**

*(i) Decomposition.* By Lemma 1, lambda = 1/sum_k c_k G_k z^{-k}, and lambda_miss = 1/sum_k c_k G_k. So
D / lambda_miss = E[z^{-T}] sum_k c_k G_k / sum_k c_k G_k z^{-k}. Multiply and divide by S(z) = sum_k G_k z^{-k} and by
E[T] = sum_k G_k:
D / lambda_miss = [E[T] E[z^{-T}] / S(z)] x [(sum c G / sum G) / (sum c G z^{-k} / sum G z^{-k})] = H(z) Gamma(z).
The second form of H uses S(z) = (1 - E z^{-T})/(z - 1).

*(ii) Cost growth.* nu^z_k / nu_k is proportional to z^{-k}, which is strictly decreasing for z > 1. So nu^z is smaller
than nu in the likelihood-ratio order, hence in the usual stochastic order, and E_{nu^z}[c] <= E_nu[c] for non-decreasing
c. For equality: by Abel summation,
E_nu[c] - E_{nu^z}[c] = sum_{k<K} (F_{nu^z}(k) - F_nu(k)) (c_{k+1} - c_k), where F denotes a CDF. With full support and
strict likelihood-ratio order, F_{nu^z}(k) > F_nu(k) for every k < K. So the difference is 0 iff every c_{k+1} - c_k = 0.

*(iii) Turn-count law.* H >= 1 iff E[T](z - 1) E[z^{-T}] >= 1 - E[z^{-T}], i.e. E[z^{-T}] (1 + E[T](z - 1)) >= 1. For a
geometric T on {1, 2, ...} with mean m, E[z^{-T}] = (1/m)/(z - 1 + 1/m) = 1/(1 + m(z - 1)), so H = 1.

For T = min(Geometric(1 - q), K) we have G_k = q^{k-1}, P(T = k) = (1 - q) G_k for k < K, and P(T = K) = G_K. So
E[z^{-T}] = (1 - q) S(z) + q G_K z^{-K}, and E[T] = (1 - q^K)/(1 - q). Substituting,
H = 1 - q^K + q^K E[T] z^{-K} / S(z) = 1 - q^K (1 - E[T] z^{-K}/S(z)). The ratio E[T] z^{-K}/S(z) equals
E[T] / sum_k G_k z^{K-k}. For z > 1 and K >= 2 its denominator exceeds E[T], and the denominator increases with z. So the
ratio lies in (0, 1) and decreases in z. Hence H lies strictly in (1 - q^K, 1) and is non-increasing in z.

*(iv) Near the threshold.* By Theorem 1(e), D / lambda_miss = rho - alpha/lambda_miss
= rho - (E[T]/kbar_c)(rho - 1) + O((rho - 1)^2). This uses the expansion of alpha stated in 1(e), which follows from
gamma = (rho - 1)/kbar_c + O((rho - 1)^2) and E[z^{-T}] = 1 - (z - 1)E[T] + O((z - 1)^2) (finite K). When
kbar_c = E[T] the first-order term vanishes, and the premium's sign is decided at second order; the Theorem 2 referee
found positive examples, e.g. constant costs with T in {1, 10}.

*(vi) Monotonicity.* For z' > z > 1, nu^{z'}_k / nu^z_k is proportional to (z/z')^k, which is strictly decreasing. So
nu^{z'} lies below nu^z in the likelihood-ratio order, and E_{nu^{z'}}[c] <= E_{nu^z}[c] for non-decreasing c. The Abel
argument of (ii) makes this strict for non-constant c, so Gamma is strictly increasing. As z -> infinity, nu^z
concentrates on k = 1, so Gamma -> E_nu[c]/c_1. If this exceeds 1/(1 - q^K), the root z_1 exists and is unique. For
z >= z_1, H Gamma > (1 - q^K) Gamma(z_1) = 1, where the strict inequality comes from H > 1 - q^K in (iii).

*(v) Geometric T with growing costs.* Use (i)-(iii) with H = 1 and Gamma > 1; this needs z > 1, i.e. rho > 1. For K =
infinity, Lemma 1 and the formulas hold whenever sum_k c_k G_k z^{-k} converges near z = 1. With geometric G and costs of
polynomial growth this is true for every z > q. Theorem 1 itself was proved for finite K; (v) is a statement about the
formulas. []

**Proof of Corollary 3.** At t_0 the state is a finite pending mass, which is an admissible initial condition (F6). Apply
Theorem 1 from t_0 with rate lambda'. The threshold and the busy-period value come from 1(a)-(c).

For the second sentence: whenever D(lambda) > lambda_miss (Theorem 2), the interval (lambda_miss, D(lambda)) is
non-empty. Any lambda' in it has rho' > 1. By Lemma 2(iii) the remaining work then never decreases,
V_tot(t) >= V_tot(t_0), and the proof of Lemma 2(i) gives V >= eta V_tot(t_0) > 0, so the queue never empties.
Theorem 1(c) adds that it grows linearly. At rho' = 1 the same bound holds, and Theorem 1(b) gives the limit. []

**Proof of Corollary 4.** Divide Lemma 1's equation by sum_j c_j G_j. The rest are formulas in z, G and omega. Under
c -> c/s, omega is unchanged and lambda_miss -> s lambda_miss. []

## 5. What is new, and what is not

**Against our paper** (`8aaabdb`):
- Taken literally in congestion, the paper's Eq. (fluid) would put the trap's growth at lambda - mu_b. The paper says it
  does not use Eq. (fluid) for backlog growth in congestion, and it measures 18-78% of lambda - lambda_miss (appendix,
  "The quasi-static model in congestion"). Theorem 1 gives alpha = lambda (1 - E z^{-T}): 0.63-0.79 of
  lambda - lambda_miss at the measured cells and rates, tending to 0.60-0.62 as rho -> 1.
- The paper's heuristic RR layer integrates the processor-sharing version of this fluid numerically. It already gives 64%
  and 63% of lambda - mu_b at 300k for 1.35x and 1.65x, plus the trapped backlog and token rows of Table tab:fpval.
  Remark 6 identifies RR's long-run behaviour. Theorem 1 gives the FIFO version exactly, in closed form, for any cell.
- The paper argues for lambda_miss as the recovery threshold through a closed-system limit (Proposition A) plus a work
  balance "which we do not make rigorous for the open system". Theorem 1(a)-(c) and Corollary 3 make it rigorous for the
  open trapped system within model F, from any trapped state.
- The paper explains, in words, why a trapped engine completes sessions above lambda_miss, adding "for as long as the
  backlog grows". Theorem 2 quantifies this youth premium. It shows the premium does not fade while the trap lasts: it
  holds for every rho > 1 for geometric T with growing costs, and for the workload at every z >= 1 + 10^{-12} (section
  6.1). It is not universal under truncation (Theorem 2(v)).
- Proposition 5 (the cycle identity, gap/R_M = V_I/M) is an accounting relation. Theorem 1(c)-(d) gives the cycle's growth
  law and composition, so gap/R_M = sum_i (P_{k_i} + d)/M grows like alpha t (P_z + d)/M.
- The paper states these phenomena qualitatively (the young backlog, the above-capacity completions) and computes RR
  numerically. New here: the exact growth law (the Perron root of a renewal recursion), the closed forms for D, gamma and
  the trapped composition, the H x Gamma decomposition, the open-system threshold theorem, and the check across every cell.

**Against Lu et al. (arXiv:2611.02543):**
- They define D_low as the low-reuse departure rate that their curve approaches once reuse has collapsed, and they state
  that "arrivals below D_low let the population drain". That is the qualitative counterpart of our lambda_miss threshold,
  so the threshold itself is not new against them.
- Their §5.2 adds that departures measured in trapped (simulated) runs "set the scale" of the arrival reduction needed:
  0.20-0.31 lambda_ref GPU-only, 0.20-0.24 with the host tier.
- Theorem 2 and Corollary 3 sharpen that remark for FIFO traps. The throughput measured in a trap,
  D(lambda) = lambda E z^{-T}, depends on the load and exceeds the drain threshold lambda_miss by the youth premium. So a
  cut to just below the measured throughput does not drain.
- Their own simulations are consistent with this. GPU-only 1P3D recovered at 0.1 lambda_ref and stayed trapped at 0.2, while
  trapped departures were 0.20-0.31. With the host tier it recovered at 0.2 and stayed trapped at 0.3-0.5, with departures of
  0.20-0.24. Their engine is PD-disaggregated, with HiCache, and not plain FCFS, so this is consistency only.
- They have no theorem; their model uses an empirical h(W/C) and has no trap dynamics.

**Against classical work and other LLM-serving theory:**
- Metastable-failure models (Bronson et al.; Huang et al.; Isaacs et al. 2025; Habibi et al.), bistable channels
  (Carleial-Hellman; Kleinrock-Lam) and fluid metastability of queues with load-dependent service (Dong 2022, "Metastability
  in queues", Queueing Systems 100:413-415) treat the bad regime as a state, or as an absorbing or diverging region. None
  that we found gives a growth law of the bad regime, or the composition of its population.
- Ao, Dong, Luo & Simchi-Levi (arXiv:2606.15555, already in refs.bib) analyse a different instability: within-request KV
  growth under saturated continuous batching, with fixed points and limit cycles. They do not study multi-turn prefix-cache
  traps or their growth.
- The closest mathematics:
  - Overloaded processor sharing: Jean-Marie & Robert (1994) for the growth rate; Grishechkin (1992) for the
    Crump-Mode-Jagers correspondence; Puha, Stolyar & Williams (2006) for the fluid limit.
  - Overloaded multiclass FIFO, without re-entry and with abandonment instead: Jennings & Puha (2013).
- Model F is a single-station FIFO re-entrant line in the sense of Kumar (1993), in overload, with visit-dependent service.
  The reduction of its nonlinear fluid to a linear renewal recursion along FIFO orbits, the Perron-root growth law and the
  H x Gamma decomposition are, as far as a targeted search found, new.
- The scout search (2026-11-05) found no renewal or Perron characterization along FIFO orbits for overloaded re-entrant
  multiclass FIFO, and no result on growing per-visit service in overload. This search is limited, not exhaustive.
- Kendall's busy-period branching (Remark 5) is classical and claimed as such.

**Not claimed:**
- That the engine converges to model F.
- That the trap's *entry* (the cliff, the basin) is covered. Those remain the paper's fluid and heuristic layers.
- Any stochastic result beyond Remark 5.
- Optimality of any control.

## 6. Numerical check against existing data (retrospective; nothing fitted to trap data)

Inputs:
- The frozen cell models (`analysis/theory/cells/*.yaml`; `run_check.cell_model`). Each c_k comes from the calibrated cost
  model, which was fitted to server-log iteration timings only, plus the all-miss decode share.
- Speed factors:
  - vLLM: one speed factor fitted to its E0a token rate (as in the paper).
  - H200: one speed factor fitted to its E0a token rate (as in the paper).
  - Llama: one speed factor fitted to its E0a token rate (pred2's conditional "fit" variant).
- Measured windows: [5700, 8700) s for E2-protocol runs, and [1500, 3000) s for unstable E0b runs. A run counts as trapped
  if its follow-up hit fraction in the window is below 0.2.
- Full tables: `results/theory/icml/trap_check.md` (and `.json`, `universality.csv`).

### 6.1 Theorem 2 on the workload (all eight cells)

From `support.py` (section 7). Every per-turn cost is increasing (c_60/c_1 = 17-23).

Where the premium H Gamma - 1 is proved positive and where it is only checked:
- *Proof, z >= z_1.* Theorem 2(vi) applies: sup Gamma = E_nu[c]/c_1 = 3.8-4.6 exceeds 1/(1 - q^K) = 1.0162, and
  z_1 = 1.00154-1.00165 (rho_1 = 1.038-1.040). So the premium is positive at every rho >= rho_1.
- *Monotone bracket, z in [1 + 10^{-12}, z_1].* H is non-increasing and Gamma non-decreasing in z, so on
  [z_i, z_{i+1}] the premium is at least H(z_{i+1}) Gamma(z_i) - 1 (`support.py`, `premium_certificate`, after the Theorem 2
  referee's suggestion). On a geometric grid of z - 1 with ratio 1.5 (53 brackets per cell), every lower bound is positive
  in all eight cells; normalized by z_{i+1} - 1 the smallest is 5.8. This is a floating-point evaluation, not interval
  arithmetic.
- *Expansion, z in (1, 1 + 10^{-12}).* The first-order coefficient of Theorem 2(iv), 1 - E[T]/kbar_c = 0.38-0.40, is
  positive. No remainder bound is given.
- *Numerical cross-checks.* A 4,000-point grid on (1, rho_1) gives premium/(rho - 1) >= 0.378. On 120 values in (1, 10]
  the premium is positive, with minimum 4e-5 at rho = 1.0001. The near-threshold slope matches 1 - E[T]/kbar_c to 4
  decimals; the Theorem 2 referee's Richardson extrapolation matches to 8 digits.

Also: inf H = 1 - (14/15)^60 = 0.98407. This is the infimum over z > 1, not attained, and the grid minimum is 8e-7 above
it. D(lambda) increases over (1, 10] in all cells (on the grid).

| cell | lambda_miss model | kbar_c | E[T]/kbar_c (alpha/(lambda - lambda_miss) at rho -> 1) | premium slope at rho = 1 |
|---|---|---|---|---|
| A100 300k | 0.07184 | 24.28 | 0.608 | 0.392 |
| A100 native | 0.07370 | 24.55 | 0.601 | 0.399 |
| vLLM 300k | 0.06704 | 24.45 | 0.604 | 0.396 |
| Llama-3.1-8B (fit) | 0.06053 | 24.16 | 0.611 | 0.389 |
| H200 300k | 0.19698 | 24.28 | 0.608 | 0.392 |
| H200 600k | 0.20071 | 24.48 | 0.603 | 0.397 |
| A100 150k | 0.06881 | 23.85 | 0.619 | 0.381 |
| A100 600k | 0.07320 | 24.48 | 0.603 | 0.397 |

At the registered points of the 300k cell: rho = 1.34 gives alpha/(lambda - lambda_miss) = 0.634, D = 1.126 lambda_miss,
and a served prompt of 0.891 x the stationary mean; rho = 1.64 gives 0.653, 1.223 and 0.822.

### 6.2 Composition (Theorem 1(c)): mean prompt of the turns served in the window

Measured per seed vs predicted, asymptotic / exact E2 fluid:

| cell, rate | measured | predicted |
|---|---|---|
| SGLang 300k 1.35x | 9,249 / 9,556 / 9,125 | 9,324 / 9,439 |
| SGLang 300k 1.65x | 8,576 / 8,830 / 8,417 | 8,606 / 8,678 |
| native 2.5x | 7,484 / 7,366 / 7,264 | 7,374 / 7,401 |
| native 4.0x | 6,127 / 6,213 / 6,141 | 6,115 / 6,116 |
| H200 600k 1.5x | 9,015 / 9,177 / 9,113 | 9,062 / 9,056 |
| H200 600k 2.0x | 8,058 / 8,230 / 8,200 | 8,082 / 8,083 |
| Llama 1.35x | 9,075 / 9,512 / 9,216 | 9,356 / 9,484 |
| Llama 1.65x | 8,465 / 8,757 / 8,459 | 8,631 / 8,710 |
| vLLM 1.35x (6 runs) | 9,097-9,547 | 9,393 / 9,514 |
| vLLM 1.65x (6 runs) | 8,104-8,778 | 8,676 / 8,755 |

The stationary means are 10,469-10,600, so the trap's turns are 10-42% shorter, and the tilted mix predicts by how much.

- 50 of the 57 E2-protocol runs lie within +-3% and 54 within +-5%.
- Largest deviations: +7.7% (BASIN b60 seed 1, whose trap formed late after a smaller burst), +6.0% (b50 seed 1) and
  -6.6% (one vLLM 1.65x run).
- The unstable E0b runs, whose traps are younger: -5.7% to +6.6%.

### 6.3 Cycle growth (Theorem 1(c), V(t)/t -> gamma)

The statistic is the OLS slope, over the window, of the 300 s medians of the gap (turn completion minus the same
session's previous turn completion).

| cell, rate | measured (per seed) | gamma | exact fluid |
|---|---|---|---|
| 300k 1.35x | 0.0198 / 0.0039 / 0.0095 | 0.0130 | 0.0153 |
| 300k 1.65x | 0.0265 / 0.0151 / 0.0225 | 0.0230 | 0.0246 |
| native 2.5x | 0.0510 / 0.0441 / 0.0466 | 0.0453 | |
| native 4.0x | 0.0708 / 0.0758 / 0.0662 | 0.0806 | |
| H200 1.5x | 0.0215 / 0.0168 / 0.0152 | 0.0165 | |
| H200 2.0x | 0.0305 / 0.0230 / 0.0244 | 0.0315 | |
| Llama 1.35x | 0.0110 / 0.0031 / 0.0157 | 0.0126 | |
| Llama 1.65x | 0.0206 / 0.0128 / 0.0190 | 0.0226 | |
| vLLM 1.35x | 0.0154 / 0.0162 / 0.0008 / 0.0005 / 0.0124 / 0.0135 | 0.0122 | |
| vLLM 1.65x | 0.0269 / 0.0275 / 0.0128 / 0.0143 / 0.0218 / 0.0217 | 0.0220 | |

Unstable E0b runs, measured vs gamma:

| cell, rate | measured | gamma |
|---|---|---|
| 300k 2.5x | 0.058 | 0.048 |
| 300k 3.0x | 0.078 | 0.060 |
| Llama 3.0x | 0.060 | 0.061 |
| vLLM 3.0x | 0.063 | 0.059 |
| 150k 1.45x | 0.020 | 0.019 |
| 150k 1.8x | 0.033 | 0.031 |
| 600k 5.0x | 0.089 | 0.103 |
| native 6.5x | 0.109 | 0.131 |
| H200 300k 1.75x | 0.031 | 0.026 |

- The ratio of measured to gamma has mean 0.94 and median 0.98 over the 57 E2-protocol runs, and mean 0.98 (range
  0.62-1.30) over the 13 E0b runs.
- The near-zero values are seed 1 at 1.35x (see 6.5): when arrivals dip, the trap stops growing for the window.
- The gap is the quantity the paper's Table tab:gapR reports as a median (166-516 s). Theorem 1(f) says it is not a
  constant of the trap. It is proportional to the remaining work, i.e. to the trap's age counted from its virtual origin.

### 6.4 Youth premium and backlog slope (Theorems 1(c), 2)

Every stuck run completes sessions faster than lambda_ref:
- 1.10-1.35 lambda_ref at 300k (1.13-1.35 for the r1 E2 runs; the BASIN, LPM and SHED runs included);
- 1.44-2.03 native;
- 1.20-1.45 H200;
- 1.18-1.42 vLLM;
- 1.22-1.49 Llama;
- 1.24-2.40 in the E0b runs.

The paper noted this excess qualitatively ("for as long as the backlog grows"); the numbers below quantify it
retrospectively.

Measured vs predicted D/lambda_ref:

| cell, rate | measured | D/lambda_ref |
|---|---|---|
| 300k 1.35x | 1.13 / 1.28 / 1.17 | 1.13 |
| 300k 1.65x | 1.25 / 1.35 / 1.34 | 1.23 |
| native 2.5x | 1.52 / 1.44 / 1.56 | 1.49 |
| native 4.0x | 1.87 / 1.91 / 2.03 | 1.81 |
| H200 1.5x | 1.23 / 1.20 / 1.27 | 1.20 |
| H200 2.0x | 1.40 / 1.44 / 1.45 | 1.36 |
| vLLM 1.35x | 1.18-1.28 | 1.14 |
| vLLM 1.65x | 1.30-1.42 | 1.24 |
| Llama 1.35x | 1.22-1.33 | 1.14 |
| Llama 1.65x | 1.34-1.49 | 1.23 |

Across the E2-protocol runs the engine completes between 0.90 and 1.21 times D, 1.055 times on average. Seven runs are below
D (0.90-0.998):
- the late-forming BASIN traps b50 and b60, seed 1 (0.90 and 0.91);
- native 2.5x seed 1 (0.97);
- H200 1.5x seed 1 (0.998);
- three LPM runs (0.98-0.99).

The excess elsewhere is consistent with the paper's (A3)/(A4) checks: congested engines compute prompt tokens 1-12% faster
than E0a's 32-session reference. The measured token ratios are 0.95-1.12, against 1.01-1.05 from the composition alone.
So the model's lambda_miss is a few percent low in congestion, most for Llama and vLLM.

Backlog slope as a fraction of lambda - lambda_ref, measured per seed vs predicted alpha/(lambda - lambda_miss):

| cell, rate | measured | predicted |
|---|---|---|
| 300k 1.35x | 0.89 / 0.14 / 0.74 | 0.63 |
| 300k 1.65x | 0.69 / 0.59 / 0.78 | 0.65 |
| native 2.5x | 0.79 / 0.77 / 0.74 | 0.69 |
| native 4.0x | 0.76 / 0.68 / 0.72 | 0.74 |
| H200 1.5x | 0.78 / 0.49 / 0.62 | 0.64 |
| H200 2.0x | 0.66 / 0.51 / 0.58 | 0.66 |
| vLLM 1.35x | 0.61 / 0.62 / 0.01 / -0.00 / 0.71 / 0.74 | 0.63 |
| vLLM 1.65x | 0.75 / 0.76 / 0.41 / 0.43 / 0.76 / 0.80 | 0.65 |
| Llama 1.35x | 0.25 / 0.00 / 0.75 | 0.64 |
| Llama 1.65x | 0.63 / 0.29 / 0.63 | 0.66 |

The mean over the 57 E2-protocol runs is 0.63. Read literally, the quasi-static Eq. (fluid) would give 1.0, but the paper
does not use it for growth in congestion; its heuristic RR layer gave 0.64 and 0.63 at 300k. The stochastic FIFO simulation
(400 replicates per group) gives a per-run sd of 0.007-0.015 /s for this statistic, comparable to the seed spread.

### 6.5 The seed effect and the registered slope rule (S5)

The client's constant-rate plan fixes each seed's base-arrival times before any run (`agentload.workload.poisson_times`,
stream S_ARRIVALS). It reproduces the measured window arrival rates exactly. Because the plans are common random numbers,
seed 1's window rate is below nominal in every cell and rate, by 0.8-8.9%. The dip is largest at 1.35x: 5.8% at 300k,
7.9% on vLLM, 8.9% on Llama.

The plug-in lambda_window(plan) - D tracks the measured slope; 49 of 57 runs lie within 0.01 /s and 18 within 0.002 /s.
For example:

| run group | measured slope | plug-in |
|---|---|---|
| 300k 1.35x | 0.0222 / 0.0036 / 0.0186 | 0.0228 / 0.0101 / 0.0208 |
| H200 1.5x | 0.0759 / 0.0478 / 0.0601 | 0.0765 / 0.0485 / 0.0645 |

The residuals have median -0.0022 /s, because the engine completes slightly more than D (6.4). The largest are Llama
1.35x seed 0 (0.0052 measured vs 0.0205) and the H200 2.0x runs (about -0.015 to -0.02).

The registered slope rule calls a run trapped only if its slope exceeds 0.5 (lambda - lambda_ref).

*Counts.* There are 36 runs on registered protocols (SGLang 300k, native, vLLM, H200 600k, Llama). The 12 vLLM runs are 6
plans run twice, registered and exploratory, so there are 30 independent plans. The plug-in falls on the same side of the
threshold as the measured slope in 33 of the 36 runs, and for 27 of the 30 independent plans. The baseline "always
trapped" scores 23 of 30.

*Exceptions:*
- H200 1.5x seed 1: plug-in 0.04849 against a threshold of 0.04847 (distance 0.00002); measured 0.04784.
- Llama 1.65x seed 1: plug-in above the threshold by 0.00005; measured 0.0114.
- Llama 1.35x seed 0: plug-in 0.0205, measured 0.0052. This is the registered FAIL point, where the account gets 1 of 3
  seeds wrong.

One agreement is also marginal: vLLM 1.65x seed 1, plug-in 0.0207 against 0.0213 (two runs).

*The nine below-threshold runs.* The registered labels are in parentheses.
- 300k 1.35x seed 1 (indeterminate);
- vLLM 1.35x seed 1, registered (draining);
- vLLM 1.35x seed 1, exploratory (indeterminate);
- vLLM 1.65x seed 1, registered (indeterminate);
- vLLM 1.65x seed 1, exploratory (indeterminate);
- H200 1.5x seed 1 (indeterminate);
- Llama 1.35x seed 0 (indeterminate);
- Llama 1.35x seed 1 (draining);
- Llama 1.65x seed 1 (indeterminate).

All are seed 1 except Llama 1.35x seed 0.

The theorem therefore explains why the registered slope criterion is fragile. The true slope is about 0.63
(lambda - lambda_miss), only about 25% above the threshold. A plan whose window arrivals dip by a few percent falls below
it. A finite engine-side completion excess of 5-17% (Llama, vLLM) lowers the slope further. This is post hoc and is
reported as such. It does not change any registered verdict.

### 6.6 SHED (retrodiction; the SHED runs ended 2026-11-01, before this note)

In the exact all-miss fluid at 1.35x, with arrivals stopped at 1800 s, the backlog falls from 164.9 to n_b = 32.7 after
2,020 s. The queue empties after 3,180 s, the busy period V_tot(1800). So a 600 s stop leaves 106 sessions (stuck) and a
3600 s stop drains completely (good). These are the registered SHED outcomes. pred2's frozen tau_min was 1,795 s
(quasi-static) or 1,928 s (round robin). The check does not discriminate: any drain time between 600 and 3,600 s fits
the two registered stop lengths.

### 6.7 Corollary 3 illustrated (all-miss fluid, 300k, 1.65x, cut at 5000 s; prediction for a future test)

D(1.65x) = 1.223 lambda_miss.

| cut to | backlog (from 251 at the cut) |
|---|---|
| 1.18 lambda_miss | dips to 250.7 at 5,250 s (-0.3%), then grows to 445 by 30,000 s |
| 1.10 lambda_miss | dips to 246 at 6,200 s (-2%), then grows to 352 |
| 1.05 lambda_miss | dips to 241 at 6,850 s (-4%), then grows to 295 |
| 1.02 lambda_miss | dips to 237.6 at 7,450 s (-5.5%), then grows to 261 |
| 1.00 lambda_miss | undershoots to 234.6 at 7,700 s (-6.7%), then settles at 238.7 by 80,000 s, which equals Theorem 1(b)'s limit lambda_miss E[T] V_tot(5000)/kbar_c (-5.1%) |
| 0.90 lambda_miss | drains, slowly: 128 by 30,000 s. The queue empties at 59,655 s, exactly the busy period V_tot/(1 - rho'); 1/(1 - rho') = 10 stretches it |

So an operator who sets arrivals between lambda_miss and the trapped throughput sees at most a brief dip of a few percent,
then renewed growth. A cut below lambda_miss drains, but near the threshold only over a busy period that 1/(1 - rho') makes
long. The Theorem 2 referee reproduced every row with independent code.

### 6.8 Self-similarity (Theorem 1(d)): sojourn grows with the arrival time

A session that joins the trap at u finishes near u z^T. So, among completed base sessions with similar T that arrive in
[2500, 7000) s, the sojourn should grow linearly in the arrival time with slope about E[z^T - 1]. The ratios below are
measured over predicted slopes, per seed; source: `support.json`, key `self_similarity`.

| cells | sessions per bin | ratio | reading |
|---|---|---|---|
| H200 600k, both rates | 160-400 | 0.86-1.19 in every T bin (3-6, 8-12, 13-18) | consistent |
| native 2.5x, T 3-6 | | 0.85-0.96 | consistent |
| SGLang 300k, vLLM, Llama | 40-120 | 0.2-1.6 | noisy |
| long T at high z (e.g. native 4.0x) | | 0.1-0.8 | biased low |

The last row is biased by right-censoring at 8,700 s: a late long session there needs more than the remaining run time,
so the completed ones are the faster ones. This check is descriptive and supports Theorem 1(d) where samples are large
and censoring is small. It is not a test.

## 7. Reproduce

All commands use Windows Git Bash with the shared venv.

```
PYTHONPATH="src;." python -m analysis.theory.icml.run_check --reps 400          # section 6 tables (~5 min)
PYTHONPATH="src;." python -m analysis.theory.icml.support                       # every summary number of section 6 (~3 min)
PYTHONPATH="src;." python -m analysis.theory.icml.freeze_predictions --reps 200 # the frozen predictions (~4 min)
PYTHONPATH="src;." python -m pytest -q tests/test_theory_icml.py               # 20 tests, ~2 min
```

The tests cover:
- Lemma 1 and the Perron root;
- Theorem 2(i)-(iv): the decomposition, the H formula, Gamma >= 1, no premium for geometric T with constant costs, and
  the near-threshold coefficients;
- Lemma 2(iv), sum_n h_n = V_tot;
- Theorem 1(b), the critical limit;
- the orbit recursion on the simulated fluid (residual < 2e-3, from packet discretisation);
- convergence of the fluid to the asymptotics;
- Theorem 1(a), the busy period.

`results/theory/icml/support.json` holds the outputs of `support.py`.

## 8. Predictions for new experiments

Tag `icml-trap-pred` (`6b47a6c`) was pushed to the private origin on 2026-11-05 at about 00:25 CST, with the branch
`claude/theory-icml-2164a9`. Whether it precedes a given new run must be checked against that run's submission time
(Slurm), and the push time against GitHub's activity log.

- `configs/icml_trap_predict.yaml` gives, for each cell, the asymptotic table, the E2-protocol fluid and stochastic
  slope-test power, and per-seed plug-ins.
- Scoring rules S1-S5 are in `notes/PREDICTIONS_icml_trap.md`.
- Additional, not frozen under the tag, for the lead to register if useful:
  - a server-side running-request cap. If the engine stays all-miss under the cap, the FCFS trap persists iff
    lambda > lambda_miss(cap), the all-miss capacity under the cap's own costs c_k'. A cap that only lowers batching
    efficiency has c_k' >= c_k, hence lambda_miss(cap) <= lambda_miss < lambda, and it cannot clear the trap. A cap that
    restores hits leaves model F, and the corollary is then silent;
  - an arrival cut to lambda' in (lambda_miss, D(lambda)) does not clear the trap (6.7);
  - at equal rho, A100 and H200 trapped gaps grow at the same slope gamma, to the extent that their cost vectors are
    proportional.

## 9. How this changes the paper

**Claims gained:**
- (1) An exact characterization of the trapped state within a stated model. The paper lacked one: it had a numerical
  heuristic (RR) and qualitative statements. The tilted composition, the cycle-growth law and the youth premium are
  quantified retrospectively on every stuck run across eight cells, with no parameter fitted to any trap measurement.
- (2) Proposition A's threshold becomes an open-system statement (Corollary 3).
- (3) A sharper statement than Lu et al.'s §5.2 remark that trapped departures "set the scale" of the needed cut. The
  measured trapped throughput exceeds the drain threshold.
- (4) A post-hoc account of the registered low-rate fragility.

**Suggested abstract sentence (about 360 characters):** "We prove that a trapped engine is an overloaded re-entrant FIFO
queue whose cycle obeys a linear renewal recursion; with no parameter fitted to trap data, its Perron root gives the trapped
turn mix within a few percent, the linear growth of the turn gap and a completion rate above all-miss capacity, so throughput
measured in a trap overstates the recovery threshold."

**Integration time (lead):** about one working day for the theory section (half to one page in the main text plus the
appendix proofs), one figure (universality: the measured composition, gap slope and completion rate against rho with the
predicted curves), the abstract and intro sentences, related work (overloaded PS/FIFO), and a review pass. No new
experiment is needed; tonight's runs can add blind checks via the tag.

## 10. Adversarial check (record)

Three independent referees (subagents), 2026-11-05. None imported `analysis/theory/icml`; each wrote its own code (scratch
under the session scratchpad: `skepticA/`, `skepticB/`, `skepticC/`).

**Outcome: no statement was found wrong, no proof has a remaining gap, and every flagged fix and overclaim was applied**
(commits `e53c0ce` and the one recording this section).

**Referee A (Lemmas 1-2, the renewal lemma, Theorem 1).**
- Verdicts:
  - Lemma 1: CORRECT.
  - Lemma 2(i): CORRECT WITH MINOR FIX. The definition now includes (F2), C^0(0) = 0 and maximality of tau. The existence
    facts sum c C(f(u)) = f(u) and V(f(v)) >= lambda c_1 V(v) are stated, and uniqueness is derived from (F2).
  - (ii): CORRECT; "busy on [0, f(u)]".
  - (iii)-(v): CORRECT.
  - Renewal lemma: CORRECT WITH MINOR FIX. L is the coefficient of 1/(1 - s), not the residue; theta and theta' are
    now consistent.
  - Theorem 1(a): CORRECT WITH MINOR FIX. The proof now covers all orbits, and the lambda = 0 case is treated directly.
  - 1(b): CORRECT.
  - 1(c): CORRECT WITH MINOR FIX. The proof of n -> infinity is corrected, the relative error is O(n max(theta, 1/z)^n),
    and the processing rate is stated per cycle.
  - 1(d), 1(e): CORRECT.
- Numerics: a numba many-packet FIFO simulation of model F on three toys (one with non-monotone costs, one nearly
  periodic).
  - Orbit-recursion residual <= 1.3e-4, shrinking with packet size. Lemma 2(v) <= 9e-5. sum h_n = V_tot to 6 digits.
  - Busy-period relative error about 1e-5. The critical limits hold to 4 digits.
  - Supercritical V/t, N/t, Dep/t, composition and P ratio all within 2e-4. The near-threshold coefficient converges
    linearly.
- Contributed:
  - Theorem 1(f): the cycle is proportional to the remaining work, with an exact virtual origin.
  - The convergence-rate caveat, now Remark 8.
- Overclaims fixed:
  - "renewal process" became "renewal equation".
  - "proportional to the trap's age" now reads remaining work / virtual origin.
  - Notation clashes resolved: omega for the cost mix, eta, C_r, m_b.

**Referee B (Theorem 2, Corollaries 3-4, Remarks 5-6, sections 6.1 and 6.7).**
- Verdicts:
  - 2(i)-(iii): CORRECT. Clarified: strictness needs z > 1 and G_K > 0; H lies strictly in (1 - q^K, 1).
  - 2(iv): CORRECT WITH MINOR FIX. The "iff" became one-sided statements; the sign at kbar_c = E[T] is decided at second
    order.
  - 2(v): CORRECT as worded.
  - 2(vi): GAP, fixed. It now has the existence condition E_nu[c]/c_1 > 1/(1 - q^K) and uniqueness, and the strictness
    comes from H > 1 - q^K.
  - Corollary 3: CORRECT WITH MINOR FIX. Open interval, fluid-only endpoint, the rho' = 1 limit, and an explicit
    V >= eta V_tot.
  - Corollary 4: CORRECT. The dependence on G is now stated, and proportional costs are needed for cross-hardware claims.
  - Remark 5: CORRECT. The Kendall/Takacs attribution is right, and a 1e5-replication Monte Carlo agrees with the formula.
  - Remark 6: CORRECT. An independent event-driven processor-sharing simulation matches exactly; gamma_PS = g, and the
    half-turn offset explains the 2%.
- Contributed:
  - The truncation counterexample, now in Theorem 2(v).
  - The monotone-bracket certificate, now in `support.py`.
  - Cuts at 1.02 and 1.00 lambda_miss in 6.7, which this session then verified itself.
- Independently reproduced: every number in 6.1 and 6.7.

**Referee C (data, novelty, honesty).**
- Recomputation: it recomputed 22 stuck runs from the raw files with independent code. All six statistics matched
  `trap_check.json` to 5 or more digits, and it confirmed the registered labels.
- Corrections applied:
  - "two runs below D" became seven runs.
  - Ranges: completions 1.10-1.35 at 300k; E0b minimum 1.24; gamma 0.012-0.13; alpha fraction 0.63-0.79 at the measured
    points.
  - Eight cells, not nine.
  - The plug-in is scored on independent plans: 27/30, against a baseline of 23/30.
  - "Nothing fitted" became "no parameter fitted to any trap measurement".
  - "Trapped" runs became "stuck" runs.
  - SHED is labelled non-discriminating.
  - Novelty claims were reworded against the paper's RR layer (which already gave about 0.63) and against Lu et al.
    (whose D_low drain statement is qualitatively our threshold).
- Blindness confirmed: every run directory used was pulled between 2026-10-24 and 2026-11-01.
