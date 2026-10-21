# Math check: `THEORY_v3_thrashing_curve.md` (plus a brief check of `THEORY_session_effects.md` Claims 1–2)

Checked 2026-10-21 by the math-checker subagent. Key: ✓ valid; ⚠ valid only under the stated extra assumptions, or needs justification; ✗ wrong as stated.

## 0. What I did, and what is verified vs. not

- I read the note, the engine on `pilot/prefix-meta` (`engine.py`, `policies.py`, `workload.py`), the round-1 and round-3 result tables, and the committed round-4 pre-registration (`configs/prefix_meta_r4_prereg.yaml`, db30e76).
- **Analytic checks:** `analytic.py` and `analytic2.py` in the scratchpad (Appendix A).
- **Sanity simulations.** These are not project results. I ran small closed-population runs with the existing engine, imported from the `prefix-meta` worktree as it stood during this check: HEAD db30e76 plus uncommitted round-4 edits (diff sha1 prefix `06c9e0fb276e`), default LRU path.
  - At the four grid points shared with round 3 (n = 16, 24, 28, 32; seeds 0–2), they reproduce the round-3 values exactly (3.43, 3.57, 2.21, 1.38 λ_miss). So the default code path is unchanged.
  - **Do not cite these numbers in the paper.** Re-run them from a clean tree if they are needed.
  - They used the round-1–3 seeds, not the registered round-4 seeds (2000–2202). They used no RANDOM or MRU eviction, and no k ≠ 1. R2, the RANDOM/MRU clauses of R5, and μ*(k≠1) in R6 therefore stay blind.
  - **Disclosure:** these runs do make the R1 outcome and the fluid side of R3 foreseeable (§7).
- I did not prove any of the "proposition" statements below beyond the sketches given. Where I say "standard", I mean the argument pattern is standard; I have not written out the proof for this model.

## Summary of verdicts

| Item | Verdict | Corrected statement / reason |
|---|---|---|
| Fluid ODE $\dot n=\lambda-\mu(n)$ | ⚠ heuristic | Fixed points, the bistability window and the recovery threshold from deep congestion are robust. There is **no timescale separation near the cliff**: $\epsilon=\tau_{\rm mix}\lvert\mu'\rvert\approx 6$. Transients and basin geometry are not determined by $\mu(n)$. |
| (i) unique global attractor | ⚠ → ✓ with fix | The condition is $\lambda<\inf_{n\ge n^*}\mu(n)$. It equals $\lambda<\mu_\infty$ only if the tail is non-increasing. |
| (ii) bistability, $n_1$ stable / $n_2$ unstable | ✓ for the ODE | Requires continuity, unimodality and a transversal crossing at $n_2$. |
| (ii) $b_c\approx n_2-n_1$ as the critical *burst* | ✗ | A burst adds *fresh* sessions with about 2.4× smaller memory footprint. The data put $b_{\rm emp}\in(25,50]$ against $n_2-n_1\approx 20$. |
| (iii) | ✓ for the ODE | |
| $E_{lb}[L]$ formula | ⚠ | The identity is correct via $H=\lambda G$ (not PASTA). The note's $L_t$ pairing is off by $\Delta+d$ (it gives $N_{lb}\approx30$; the correct value is 28.4). The mean is not the right cap: $n^*$ is set by fluctuations. |
| $\mu_\infty=\lambda_{\rm miss}$ "for every eviction rule" | ✗ as stated | **True for FCFS-type orders under any eviction rule** (clean proof, Prop. A). **False for LPM:** $\mu_\infty^{\rm LPM}\approx1.16\,\lambda_{\rm miss}$ at the limit, with the mechanism verified (Prop. B). |
| Cap $\mu_{\rm cap}(n)=\mu(\min(n,N))$, stable iff $\lambda<\mu(N)$ | ✓ | This is an exact identity in law, verified in the data. |
| "Best cap $N=n^*\approx N_{lb}$" | ✗ | At k = 1, $n^*\approx20$–22 with $\mu^*\approx4.0$, while $\mu(N_{lb}=28)=2.21$. |
| Escape $\sim\exp(kV)$ | ⚠ conjecture | The regularity needed for Freidlin–Wentzell fails or is unverified. A 1D birth–death heuristic matches the k = 1 escape times within about 2×. |
| $\lambda_{\rm cap}(k;H)\uparrow\mu^*$ | ⚠ | It holds asymptotically, with gap $\propto\sqrt{\ln H/k}$, toward the *fluid* peak. Monotonicity in k is not implied. |
| R1 | well-posed; clause 2 not implied | Likely FAIL: $\mu(30)\approx1.69$ and $\mu(34)\approx1.25$. |
| R2 | well-posed; not implied by the fluid theory | Comes from a caching heuristic; outcome uncertain. |
| R3 | well-posed; knife-edge | $b_c\approx19.9$, so PASS needs $b_{\rm emp}\le39.8$. Partly non-blind (round-1 burst sweep). |
| R4 | well-posed; implied (given monotone tail and the 150k-s horizon) | Non-blind. Its LPM half *contradicts* the note's own $\mu_\infty$ claim. |
| R5 | well-posed; redundant with the E-curve via the cap identity | The LRU clause is near-certain. |
| R6 | well-posed; asymptotically implied, monotonicity not | There are small-k biases in both directions. |

---

## 1. Is $\dot n=\lambda-\mu(n)$ justified? (quasi-stationarity)

**Exact starting point.** Write the open system as $(N(t),Y(t))$. Here $Y$ is everything else: each session's turn index and phase, residual tool times, queue order, LRU stack, running set and prefill progress. Departures occur at an instantaneous rate $d(N,Y)$, so exactly
$$\tfrac{d}{dt}\mathbb E N=\lambda-\mathbb E\,d(N,Y).$$
The ODE replaces $\mathbb E[d\mid N=n]$ by $\mu(n):=\mathbb E_{\pi_n}[d]$, where $\pi_n$ is the stationary law of $Y$ in the closed system with $n$ sessions and replacement.

**Assumptions this needs, stated precisely.**
- **(Q1)** For each $n$, the closed system is ergodic with a unique stationary law $\pi_n$. In a $k\to\infty$ fluid limit it must also have a unique attracting internal equilibrium; otherwise $\mu(n)$ is multivalued.
- **(Q2) Timescale separation.** Let $\tau_{\rm mix}(n)$ be the relaxation time of $Y$ with $n$ frozen. Linearising the ODE at a point gives its own timescale $1/\lvert\mu'(n)\rvert$. Adiabatic elimination (Tikhonov / Khasminskii averaging) needs
  $$\epsilon(n):=\tau_{\rm mix}(n)\,\lvert\mu'(n)\rvert\ll1 .$$
  Equivalently, the lag error in the departure rate, about $\mu'\,\dot n\,\tau_{\rm mix}$, must be small compared with the drift $\lambda-\mu$. Then $\dot n=\lambda-\mu(n)+O(\epsilon)$.
- **(Q3) Composition.** At a fixed point the inflow of fresh sessions equals the outflow, exactly as in the closed system with replacement. The fixed points therefore coincide with stationary states of the open system (✓). Off the fixed points, the open system's composition differs from $\pi_n$; for example, it has an excess of fresh turn-1 sessions when $\dot n>0$.

**Does the k-scaling produce separation?** No. Round 3 scales M, chunk budget and the running cap by k, and divides per-token costs by k. Under that scaling, tool times (5 s), service times and lifetimes stay $O(1)$, and $\dot n/k=O(1)$. So $\epsilon$ does not shrink with k. The true fluid limit of the k-family is measure-valued (sessions × turn × phase × cache state). The 1D ODE is its adiabatic reduction, not its limit.

**Is (Q2) plausible here? Measured.** I used the integrated autocorrelation time of the 100-s-window hit rate as a proxy for $\tau_{\rm mix}$: closed FCFS-LRU, k = 1, 150k s, seed 0 (`closed_acf.py`).

| n | 16 | 22 | 26 | 28 | 30 | 36 |
|---|---|---|---|---|---|---|
| $\tau_{\rm int}$ (s) | ~200 (at the 100-s resolution floor) | 640 | 440 | 450 | 460 | 370 |
| lifetime $n/\mu(n)$ (s) | 98 | 117 | 191 | 267 | 374 | 678 |
| $\lvert\mu'\rvert$ (1/s) | ≈0.009 | ≈0.005 | ≈0.016 | ≈0.014 | ≈0.010 | ≈0.003 |

- **Near the cliff** (n = 24–30, where $\lvert\mu'\rvert$ = 0.012–0.017/s): $\epsilon\approx 450\times0.015\approx6\gg1$ (range about 5–8). The assumption that the internal state equilibrates on the ~100 s lifetime does not hold near the cliff, because relaxation takes 1–5 lifetimes (about 5 at n = 22, 1.2 at n = 30) and, more importantly, is slow compared with $1/\lvert\mu'\rvert\approx60$–80 s. This is exactly the region $n\in[22,32]$ that determines $n_2$ and $b_c$.
- **Deep congestion:** $\mu$ is flat, so $\epsilon\to0$. The recovery dynamics and the recovery threshold are fine.
- **Good state ($n\approx n_1$):** $\epsilon\approx2$. However, sessions there interact only through the batching speed, so the system is M/G/∞-like. Little's law then makes the fixed point $n_1=\lambda\,\mathbb E[\text{lifetime}(n_1)]$ and its stability correct regardless of $\epsilon$; only the transient shape is wrong.

**Direct evidence that $N$ alone does not determine the basin (composition matters).**
- **Cold start.** A cold start of 50 fresh sessions at 2λ_miss recovers 5/5 (round-1 E1 cold sweep), although $50\gg n_2\approx29$.
- **PEEK hard-pin.** It recovers 2/3 from a cold 300 at λ = 1.0 λ_miss, although $\mu_{\rm peek}(300)=0.90<1.0$ (round-3 phase and capacity tables). Fresh sessions have no KV to pin.

**On (Q1).** Near the cliff, the closed k = 1 system wanders widely. The 5–95% range of the 1000-s-window hit rate is 0.13–0.87 at n = 28 and 0.03–0.80 at n = 30 (150k-s runs, 2 seeds). I did not see clear bimodality, but I cannot exclude internal bistability in the k → ∞ limit. Cheap test: compare the window-hit distributions on the k = 2 curve with k = 1. Narrowing suggests a unimodal equilibrium; splitting suggests internal bistability.

**Verdict ⚠.** Use the ODE as a quasi-static approximation.
- **Robust:**
  - (a) the fixed points are stationary states, given (Q1);
  - (b) the window $\mu_\infty<\lambda<\mu^*$: a good stationary state exists iff $\lambda<\mu^*$, and deep congestion drifts up iff $\lambda>\mu_\infty$;
  - (c) the recovery threshold from deep congestion.
- **Not robust:**
  - (d) the basin boundary, which is a hypersurface in $(N,Y)$ space; $n_2$ is only its intersection with the closed-stationary manifold;
  - (e) transit times near the cliff;
  - (f) burst responses.

## 2. Fixed-point classification

Let $f(n)=\lambda-\mu(n)$ with $\mu$ continuous and $\mu(0)=0$.

**General rule (no monotonicity needed).**
- Zeros of $f$ are fixed points.
- A zero where $\mu$ crosses $\lambda$ upward ($f$ goes from + to −) is stable. A downward crossing is unstable.
- The basin of a stable zero is the interval between its neighbouring unstable zeros.
- From $x_0$, $x(t)\to\infty$ iff $f>0$ on $[x_0,\infty)$. Proof: $x$ is then increasing, and a finite limit would have to be a zero of $f$. This also holds if $f\to0$ at ∞; the divergence is then sublinear.

**(i)** ✓ for unimodal $\mu$ (strictly increasing on $[0,n^*]$, non-increasing after). In general the condition is $\lambda<\inf_{n\ge n^*}\mu(n)$.
- The note's ⚠ wording is slightly off. "$\mu>\lambda$ for all large n" follows automatically from $\mu_\infty>\lambda$. What is needed is $\mu(n)>\lambda$ for every $n>n_1$.
- A real non-monotone tail exists: PEEK-pin, with $\mu(150)=1.05$ and $\mu(300)=0.90$. FCFS and LPM tails are flat from n ≈ 48.

**(ii)** ✓ for the ODE. It needs:
- continuity;
- strict increase on $[0,n^*]$;
- a transversal crossing at $n_2$;
- a non-increasing tail.

Edge cases:
- If $\mu$ has a plateau at level λ, the fixed set is an interval (neutral).
- In the k → ∞ limit the cliff may become a jump. Then use sign changes in the Filippov sense. The classification is unchanged, but $n_2$ is then λ-independent over a range of λ.

**Wording.** For $\lambda>\mu_\infty$ the stochastic system is transient, with no second stationary state. The paper should say "metastable good state plus a transient congested regime" rather than "bistable".

**Recovery threshold.**
- From $x_0$, the ODE recovers iff $\lambda<\min_{[n_1,x_0]}\mu$. With a monotone tail this is $\mu(x_0)$, and it tends to $\mu_\infty$ as $x_0\to\infty$ ✓.
- **Finite-horizon bias.** The measured threshold from 300 is biased low by about $(300-n^*)/H$ sessions/s:
  - H = 30k s: −0.19 λ_miss (−19% for FCFS). This is why P1 failed at 30k s.
  - H = 150k s: −0.04 λ_miss.

**Critical burst ✗.** $b_c=n_2-n_1$ counts *stationary-composition* sessions. A burst adds fresh turn-1 sessions.
- **Footprint of a fresh cohort.** Context starts at $E_1=2{,}100$ tokens. The expected cohort context per initial session, $\max_t P(T\ge t)E_t$, peaks at $c_{\rm peak}=4{,}331$ tokens (turn 12). For comparison, $E_{lb}=10{,}569$, a ratio of 2.44.
- **Memory accounting at 2λ_miss.**
  - $n_1=8.9$, $n_2=28.8$ (fine-grid curve), so $n_2-n_1=19.9$.
  - Slack $M-n_1E_{lb}=206$k tokens.
  - Stationary-equivalent burst: 19.5. Fresh-equivalent burst: 47.6.
- **Data** (round-1 E2 burst sweep, FCFS-LRU, 2×, 60-s burst, seeds 0–4):
  - burst 25: 0/5 trapped; burst 50: 4/5 trapped; burst 100: 5/5 trapped.
  - Cold-start sweep: 50 → 0/5 trapped; 75 → 5/5 trapped.
  - So $b_{\rm emp}\in(25,50]$, about 1.3–2.5 × $(n_2-n_1)$.
- **Corrected heuristic.** $b_c^{\rm burst}\approx(n_2-n_1)\,E_{lb}/c_{\rm peak}$. This is an upper estimate: it ignores the fluctuation margin of §3 and the first-turn prefill pulse. The 1D value is a lower estimate. Neither is a theorem. The burst also lasts 60 s, about half a lifetime, so it is not instantaneous.

**(iii)** ✓ for the ODE. For the stochastic system, transience for $\lambda>\mu^*$ would follow from fluid-limit transience criteria (Meyn 1995 style). Those criteria require the true measure-valued fluid limit, which has not been established.

## 3. Length-biased resident context $E_{lb}[L]$

**Identity ✓, but with the wrong justification in the note.** Let $c_i(t)$ be the KV demand of session i at time t. In the stationary closed system, the $H=\lambda G$ relation (Brumelle 1971; Heyman & Stidham 1980; *verify the exact references*) gives
$$\mathbb E\Big[\sum_{i\ \rm present}c_i(t)\Big]=\mu(n)\,\mathbb E^0\Big[\int_{\rm lifetime}c\Big].$$
Little's law gives $n=\mu(n)\,\mathbb E^0[\text{lifetime}]$. Dividing:
$$\mathbb E\Big[\sum c_i\Big]=n\,\frac{\mathbb E^0[\int c]}{\mathbb E^0[\text{lifetime}]}=n\,E_{lb}.$$
- This needs only stationarity and finite means, and no independence across sessions.
- "PASTA-like" is the wrong tool: the closed system has no Poisson stream.
- Renewal-reward per slot works only in its sample-path form, because cycles in different slots are not iid.

**Subtleties.**

1. **✗ Off-by-one in the note.** The note pairs $L_t$ (context *before* turn t; a miss prefills $L_t+\Delta$) with $\tau_t=$ service$_t+Z_t$. During $Z_t$, however, the session holds its end-of-turn KV $E_t=L_t+\Delta+d$.
   - The literal formula gives $E_{lb}\approx9{,}919$ and $N_{lb}\approx30.2$.
   - The code (`length_biased_mean_context`, using $E_t$) gives 10,569 and **28.4**.
   - Cap 30 recovers 0/3 at 2× while cap 28 recovers 2/3, so this off-by-one is exactly the width of the cliff.

   The correct phase-resolved formula is
   $$E_{lb}=\frac{\mathbb E\big[\sum_{t\le T}(E_{t-1}W_t+E_tS_t)+\sum_{t<T}E_tZ_t\big]}{\mathbb E\big[\sum_{t\le T}(W_t+S_t)+\sum_{t<T}Z_t\big]},\qquad E_0:=0 .$$
   - $W$ is the queue wait and $S$ the service time.
   - Nothing is cached while turn 1 waits.
   - There is no tool call after the last turn, and the KV is freed at session end (the engine's oracle).
   - With $\bar z=5$ s, $S\in[0.5,2]$ s and $W\in[0,1]$ s, this gives 10,450–10,537 ($N_{lb}$ = 28.5–28.7). So the code's equal-weight-per-turn proxy is accurate to about 1% in the good state.
2. **⚠ Policy dependence.** $W_t,S_t$ depend on n and the policy, so $E_{lb}$ is a workload constant only where $Z$ dominates the cycle (the good state).
3. **⚠ Mean vs. fluctuations.** $nE_{lb}$ is the *mean* demand.
   - The per-session stationary context has SD ≈ 7,982 tokens (CV 0.76). The total over N roughly independent sessions therefore has SD ≈ $7{,}982\sqrt N$, about 14% of M at N = 28.
   - Largest N with $NE_{lb}+z\sqrt N\sigma\le M$: z = 1 → 24; z = 1.5 → 22; z = 2 → 21.
   - The measured peak of the FCFS-LRU curve is at n ≈ 20–22, i.e. the z ≈ 1.5–2 level.
   - **$N_{lb}$ is an upper bound for $n^*$, not $n^*$.**
   - My heuristic prediction for the k-scaled curves: $n^*(k)/N_{lb}(k)\approx$ 0.63–0.78 (k = 0.5), 0.74–0.85 (k = 1), 0.81–0.90 (k = 2), 0.86–0.92 (k = 4).
4. **Real engines.** "First turn always a miss" only affects $W_1$ and is negligible in the good state. The bigger issue: with `free_kv_on_session_end=false`, dead KV of finished sessions sits at the MRU end of LRU and adds to demand. It must be included for real-engine caps.

## 4. "$\mu_\infty=\lambda_{\rm miss}$ for every eviction rule under work-conserving admission"

**Holes.**
- **(H1) ✗ The wait does not always grow.** "A session's wait between turns grows without bound" is true for FCFS-type orders only.
  - Under LPM, a returning session whose KV is still resident goes first. Its wait is $O(1)$ for every n.
  - The relevant quantity is then a race between the tool time $Z$ and the idle-KV lifetime $R$ in the congested regime.
  - $R$ does not depend on n once running reservations saturate M.
- **(H2) Wrong resource bound.** The shielded-set bound $M/L_{\min}$ is not the binding resource in congestion. The idle pool is at most the slack $M-$reserved. Under memory-bound work-conserving admission this is less than one request's reservation (the round-1 diagnostic shows about 6.5k idle tokens). This makes shielding even weaker for FCFS, and is irrelevant for LPM, which needs no long-term shielding.
- **(H3) Memory must bind.** "Running KV saturates M" requires memory, not the running cap, to bind: $M<R_{\max}\cdot$ typical $E_t$. That holds here, but not for short-context or long-decode workloads (decode400 has R = 1.31).
- **(H4) Calibration match.** $\mu_\infty=\lambda_{\rm miss}$ also needs the congested per-miss work to equal that of the cache-disabled calibration. That is true in this engine; measured values are 1.00–1.05.

**LPM's limit is reached; it is not an n = 300 artifact.**
- **Round 3:** $\mu_{\rm LPM}$ = 1.17, 1.17, 1.16, 1.17, 1.16 at n = 48, 64, 96, 150, 300, with hit rate 0.21–0.24.
- **My runs** (`lpm_mech.py`; Exp(5 s) tools; window [10k, 30k] s):
  - Follow-up hit rate 0.24–0.26 at n = 96, 150, 300, flat in n. Here μ = 1.18, 1.22 and 1.13–1.22.
  - Hit probability by tool time Z at n = 300:

    | Z (s) | <0.5 | 0.5–1 | 1–2 | 2–3 | 3–5 | 5–10 | ≥10 |
    |---|---|---|---|---|---|---|---|
    | LPM hit probability | 0.61 | 0.58 | 0.44 | 0.30 | 0.16 | 0.02 | 0.00 |

  - FCFS at n = 300: 0.00 in every Z bin.
  - Idle lifetime of evicted KV under LPM: median 0.07–0.2 s (an atom near 0: KV freed and immediately evicted by the next admission), 90th percentile 3.2–3.4 s.
- **Changing the tool distribution at the same 5 s mean:**

  | Tool times | LPM μ(300) | LPM follow-up hit | FCFS μ(300) | FCFS hit |
  |---|---|---|---|---|
  | {0.3 s w.p. 0.76, 20 s} | **1.44 λ_miss** | 0.47 | 1.05 | 0 |
  | {3 s, 7 s} | 1.12 λ_miss | 0.13 | 1.05 | 0 |

**Corrected statements.**

**Proposition A (FCFS-type orders; any eviction rule, including Belady, MRU or random).** Assume:
- (A1) every resident context is at least $L_{\min}>0$;
- (A2) every follow-up request waits in queue at least $w_n$, with $w_n\to\infty$ in probability as $n\to\infty$;
- (A3) the congested per-miss work equals the cache-disabled reference.

Then
$$\text{hit-turn rate}\le\frac{M}{L_{\min}\,w_n}\to0,\qquad\mu(n)\to\lambda_{\rm miss}.$$

*Proof.*
- A hit at turn t+1 requires at least $L_{\min}$ tokens of the session's KV to stay resident over [end of turn t, admission of turn t+1].
- That interval has length at least $w_n$.
- Resident token-time accrues at rate at most M.
- Hence (hit rate)·$L_{\min}w_n\le M$.
- A vanishing hit fraction together with (A3) gives the all-miss rate. ∎

*Notes.*
- (A2) holds for FCFS and program-FCFS. Turn throughput is bounded, so by Little's law the mean cycle time is $n/\nu(n)\to\infty$, and under FCFS each request waits for essentially the whole queue.
- Work-conservation is not needed for the upper bound. It matters only for $\mu_\infty\ge\lambda_{\rm miss}$: PEEK hard-pin reaches 0.90.

**Proposition B (resident-first orders such as LPM; heuristic, numerically supported).** In congestion with memory-bound admission:
- The follow-up hit fraction tends to $h_\infty=P(Z<R_\infty)$.
- $R_\infty$ is the congested idle-KV lifetime. It depends on the slack, the admission token flux and the eviction rule, but not on n.
- Hence $\mu^{\rm LPM}_\infty=\mu_{\rm cong}(h_\infty)\ge\lambda_{\rm miss}$, with equality iff $P(Z<R_\infty)=0$ (for example, tool times bounded below by $\operatorname{ess\,sup}R_\infty$).
- What is cheap to prove: $\lambda_{\rm miss}\le\mu_\infty^{\rm LPM}$ (hits only remove work). Also a token-time bound: the rate of hits weighted by $E_tZ_t$ is at most $\mathbb E[M-\text{reserved}]$, so only turns with short tool calls and small contexts can hit.
- I did not derive the law of $R_\infty$. The natural tool is a Che-type "characteristic time" for a tiny LRU fed by completions and drained by admissions.

**Consequence for positioning (a).** "μ_∞ ≈ λ_miss for every work-conserving policy, including LPM" is false in this model. How far LPM sits above λ_miss depends on how much tool-time mass lies below a few seconds. Real agent traces have many sub-second tool calls, so this claim is risky for real engines. A defensible version:
- Ordering cannot change $\mu_\infty$ under FCFS-type service.
- Resident-first ordering raises it by an amount governed by $P(Z<R_\infty)$: 16% here, 44% with 76% of calls at 0.3 s.

## 5. Admission cap

**✓ Identity (exact in law, not just fluid).** In the closed system with a FIFO gate, for $n\ge N$ the in-system process is in law a closed N-system: a completion admits the gate's head immediately, and the replacement joins the gate. Hence $\mu_{\rm cap}(n)=\mu(\min(n,N))$.

Verified in the data:
- Round-3 lb_cap (N = 28) closed throughput at n ≥ 28 is 2.21, which equals $\mu_{\rm FCFS}(28)$.
- Trapped open capped runs at 2×: tail throughput vs. closed μ(N):

  | Cap N | 30 | 33 | 36 | 42 | 49 |
  |---|---|---|---|---|---|
  | open tail throughput (× λ_miss) | 1.71 | 1.25 | 1.15 | 1.06 | 1.04 |
  | closed μ(N) (× λ_miss) | 1.69 | ≈1.32 | 1.12 | ≈1.02 | 1.00 |

**✓ Stability.**
- **Fluid:** if $N\le n^*$, there is a unique global attractor iff $\lambda<\mu(N)$. If $N>n^*$, the system is still bistable for $\lambda\in(\mu(N),\mu^*)$, but it recovers from any state for $\lambda<\mu(N)$. A cap above $n^*$ raises the congested level; it does not remove metastability.
- **Stochastic:** while the gate is non-empty, the gate is a queue served by the departure process of a stationary ergodic closed-N system with rate $\mu(N)$. Positive recurrence for $\lambda<\mu(N)$ and transience for $\lambda>\mu(N)$ should follow by standard Loynes-type or regenerative arguments, given ergodicity of the closed-N system. **I have not written the proof.**
- **Predictive check.**
  - "Recover iff $\lambda<\mu(N)$" at 2×: caps 25, 28, 30 have μ ≈ 3.2, 2.21, 1.69. Observed recoveries: 3/3, 2/3, 0/3 ✓.
  - The cap-28 result is a finite-horizon effect: drain time ≈ (300 − 28)/((2.21 − 2)λ_miss) ≈ 27k s, against a 30k-s horizon.
  - Round 1, cap 32 ($\mu=1.38$): 2/3 at 1.25× and 0/3 at 1.5× ✓.

**✗ "Best cap $N=n^*\approx N_{lb}$".**
- The best static cap is $n^*\approx20$–22 with $\mu^*\approx4.0\,\lambda_{\rm miss}$, against $\mu(28)=2.21$.
- So the length-biased cap as defined is about 45% below the best static cap in from-any-state stability limit.
- Use the measured $n^*$, or the fluctuation-margin cap of §3.

## 6. Finite-size escape

**Form.** For density-dependent Markov jump processes on a finite-dimensional state space with Lipschitz, bounded-below rates, a sample-path LDP holds (Shwartz–Weiss). The mean exit time from a basin then satisfies $\tfrac1k\log\mathbb E\tau_k\to V$. These are logarithmic asymptotics only; there is no prefactor.

**Why it doesn't apply directly here.**
- (a) The state is infinite-dimensional: FCFS order, the LRU stack, residual tool times for non-exponential Z, and per-request prefill progress.
- (b) The statistics are discontinuous: memory-threshold admission and head-of-line blocking. LDPs with discontinuous statistics exist only in special cases (Dupuis–Ellis–Weiss 1991; *verify*).
- (c) The server is iteration-based with deterministic step times, not a jump process with rates.
- (d) The k-family is not exactly self-similar. $\lambda_{\rm miss}(k)/k$ drifts by −9% at k = 4 and +5% at k = 0.25 (round-3 calibration), so whether $\mu_k(kx)/k$ converges has to be checked.
- (e) The fluid limit is not the 1D ODE (§1).
- (f) Escapes can also be triggered by fluctuations of the internal resident-KV composition at fixed N, which a 1D N-only picture omits.

So "$\tau_{\rm esc}=e^{kV+o(k)}$" is a reasonable conjecture, not the consequence of a known theorem.

**1D birth–death check.** Births at rate kλ, deaths at rate $k\mu(n/k)$, using the fine k = 1 curve:

| λ (× λ_miss) | $V_{1D}=\int_{n_1}^{n_2}\ln(\mu/\lambda)$ | BD mean passage $n_1\to n_2$ (→112) | Round-3 k = 1 empirical (exp-MLE mean, 95% CI) |
|---|---|---|---|
| 2.0 | 8.8 | 2.0e6 s (3.8e6) | 3.8e6 (6.9e5–1.5e8) |
| 2.25 | 6.5 | 2.0e5 s (3.9e5) | 4.2e5 (2.4e5–8.1e5) |
| 2.5 | 4.8 | 4.2e4 s (6.7e4) | 1.2e5 (7.9e4–2.0e5) |
| 2.75 | 3.4 | 1.0e4 s (1.7e4) | 3.3e4 (2.1e4–5.4e4) |

The quasi-static 1D picture gets k = 1 escape times right within about 2× over two decades. This supports it for slow, fluctuation-driven escape (unlike bursts). It says nothing about k-scaling: k ≥ 2 is censored.

**"$\lambda_{\rm cap}(k;H)$ increases toward $\mu^*$."**
- The round-3 rule is that all 5 seeds survive H. So $\lambda_{\rm cap}$ solves $\tau\approx5H/\ln2\approx7H$.
- At k = 1 and H = 2e4 s, that means τ ≈ 1.4e5 s. The BD curve puts this at λ ≈ 2.35–2.45; the measured value is 2.41 ✓.
- If $\tau\approx Ce^{kV(\lambda)}$, then $V(\lambda_{\rm cap})\approx\ln(7H/C)/k\to0$, so $\lambda_{\rm cap}\to\bar\mu^*$, the *fluid* peak $\lim\mu^*(k)/k$.
- Near the peak, $n_2-n_1\propto\mu^*-\lambda$ and the integrand $\propto\mu^*-\lambda$, so $V\propto(\mu^*-\lambda)^2$. Hence $\bar\mu^*-\lambda_{\rm cap}\propto\sqrt{\ln H/k}$.
- **Monotonicity in k is not implied**, because $\mu^*(k)/k$ itself moves with k.
- The k = 4 datum fits the asymptotic picture: $\lambda_{\rm cap}(4)=0.743$/s $=0.975\times4\mu^*(1)$.

## 7. Round-4 predictions (registered readings in `prefix_meta_r4_prereg.yaml`)

**R1 — well-posed; clause 2 not implied; likely FAIL.**
- The fine-grid k = 1 curve (seeds 0–2; round-3 values reproduced) is:

  | n | 14 | 16 | 18 | 20 | 22 | 24 | 26 | 28 | 30 | 32 | 36 |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | μ (× λ_miss) | 3.06 | 3.43 | 3.79 | **4.02** | 3.96 | 3.57 | 2.87 | 2.21 | 1.69 | 1.38 | 1.12 |
  | seed SD | | | | 0.14 | 0.16 | 0.22 | 0.34 | | | | |

- **Clause 1** passes only at its lower edge. The theory said $n^*\approx28$.
- **Clause 2** fails either way:
  - if $n^*=20$, n ≥ 30 includes 1.69;
  - if $n^*=22$, n ≥ 33 includes $\mu(34)\approx1.25$.
  - The tail first reaches 1.2 only around n ≈ 35–36 (≈1.7 n*, ≈1.25 $N_{lb}$).
- The clause depends on the argmax of a flat-topped noisy curve. A clause tied to $N_{lb}$ (n ≥ 42) would pass.

**R2 — well-posed; not implied by the fluid theory.**
- It imports a fixed-cache caching heuristic. Here the effective idle cache $M-$reserved shrinks as misses grow, and items vary in size.
- The random-replacement fixed point $h=e^{-r(1-h)}$ with $r=W/C_{\rm eff}$ gives h ≈ 0.4–0.6 at n = 30–33, for $C_{\rm eff}$ = 200–250k. LRU's hit rate is 0.31–0.44 there, so a 1.25× gap in μ is uncertain.
- By Prop. A, RANDOM also has $\mu_\infty=\lambda_{\rm miss}$. R2 probes only the transition region.
- It inherits the $n^*$ fragility ($n_{R2}$ = 30 vs. 33).

**R3 — well-posed; at its tolerance edge by construction.**
- PASS iff $0.5\le b_c/b_{\rm emp}$, i.e. $b_{\rm emp}\le2b_c$. From the fine-grid curve, $b_c\approx19.9$, so $2b_c\approx39.8$. With fresh seeds and the registered PAV curve, $b_c$ plausibly lies in about [19, 20.7].
- **The outcome is a knife-edge:**
  - $b_{\rm emp}=30$: PASS. This is unlikely, since round 1 had 25 → 0/5 trapped.
  - $b_{\rm emp}=40$: PASS only if the registered $b_c\ge20.0$.
  - $b_{\rm emp}=50$: FAIL.
- The composition correction (§2) predicts $b_{\rm emp}/b_c\approx1.3$–2.4, and the round-1 data already give $b_{\rm emp}\in(25,50]$.
- A PASS would therefore be weak evidence.
- **Disclosure gap:** the prereg lists R3's burst side as blind, but the round-1 E2 burst sweep at 2× (FCFS-LRU: 25 → 0/5 trapped, 50 → 4/5, 100 → 5/5) was known. See `results/prefix_meta_e2/20261021-010106/e2_summary.csv` and LOG.md.

**R4 — well-posed; implied given conditions; non-blind (disclosed).**
- Conditions:
  - a flat or non-increasing tail on $[n^*,300]$ (true for FCFS and LPM);
  - H = 150k s (fluid bias ≈ −4% for FCFS, −3% for LPM);
  - a small cold-start composition effect where μ is flat (true for FCFS and LPM; false for PEEK-pin).
- Expected outcome: FCFS t = 0.95 vs. r ≈ 1.01; LPM t = 1.175 vs. r ≈ 1.16. Expected PASS.
- **The LPM half confirms $\mu_\infty^{\rm LPM}\approx1.16\ne\lambda_{\rm miss}$.** It therefore supports Prop. B and contradicts the note's §3 "for any eviction rule" claim.
- **Measurement caveat.** Closed runs start synchronised with 300 fresh sessions. The lifetime (≈6,000 s) exceeds the 5,000-s warmup, and fresh contexts make early misses cheaper, which biases μ(300) up. My LPM run over [2k, 6k] s gave 1.32, against 1.13–1.22 over [10k, 30k]. Check the registered stationarity diagnostic before reading R4.

**R5 — well-posed; redundant with the E-curve.**
- By the exact cap identity (§5), "cap N recovers at 2×" is equivalent to $\mu_e(N)>2\lambda_{\rm miss}$.
- There is also a horizon margin: drain time from 300 ≤ 150k s needs $\mu_e(N)\gtrsim2.04$.
- So R5 must agree with the E-curve at n = 32, 36, 40. **A disagreement would refute the cap identity, not the eviction hypothesis.**
- The LRU clause is near-certain: μ = 1.38, 1.12, 1.03, all below 2.
- Report the E-curve-implied verdict alongside.

**R6 — well-posed; asymptotically implied; monotonicity over {0.5, 1, 2} not implied but likely.**
- $\rho(1)\approx2.41/4.02=0.60$.
- Biases:
  - $\lambda_{\rm cap}(0.5)$ used absolute backlog thresholds scaled by $\max(1,k)=1$, so it is relatively 2× more lenient at k = 0.5. This biases $\rho(0.5)$ up, which works against a PASS.
  - $\mu^*(k)$ is a maximum over noisy seed means, biased up more at small k. This biases $\rho$ down at small k, which works toward a PASS.
  - $\lambda_{\rm cap}$ comes from a 5-seed bisection.

## 8. Other remarks on §3 and positioning

- **Little's law.** $\mu(n)=n/\mathbb E^0[\text{lifetime}]$ is exact ✓.
- **"λ_hit" is not a constant.** All-hit throughput rises with batch size: μ(16) = 3.43 at busy 0.99, μ(20) = 4.02 at hit 0.927. The peak is a kink set by memory, not by λ_hit saturation.
- **LRU-cyclic.** ✓ classically, for strictly cyclic, unit-size references.
  - Here Z is Exp with CV 1, so the reference string is cyclic only when the FCFS wait dominates Z. Congestion makes the string cyclic, so the effect is self-reinforcing.
  - The drop spans n ≈ 22 → 36 (0.8–1.3 $N_{lb}$), not "just past $N_{lb}$".
  - "Roughly synchronous cycles" is not needed; a stable reference order is.
- **Positioning:**
  - (a) Revise per §4.
  - (b) $N_{lb}$ is an upper bound on the right cap. The right cap is about $n^*\approx N_{lb}-z\sqrt{N_{lb}}\,\sigma/E_{lb}$.
  - (c) The μ(300)-vs-capacity diagnostic is sound: it follows from Props. A/B and the cap identity.
  - (d) The escape picture is a conjecture.

## 9. `THEORY_session_effects.md`, Claims 1–2 (brief)

**Claim 1 — ✓ structure, with fixes.**
- ⚠ "Conditionally mean-zero given the past" must include $U_{ks}$ in the conditioning σ-field, or assume $\varepsilon\perp U$.
- ⚠ PrPl-EB needs a known bounded range. Gaussian U is unbounded, so assume a truncated U or use a sub-Gaussian CS.
- ⚠ The EB width is random. The lower bound needs $P(U>c+W_t,\text{cover})$ plus dominated convergence ($W_t\to0$ a.s.). This is fine. The $w_t$ rate is not needed, and I could not confirm the exact PrPl-EB rate from memory.
- **✗ "The limit does not depend on α".** The limit exists because "accept by t" is monotone in t. Using $P(\text{cover}\mid U)\ge1-\alpha$ for every U, it lies in
  $$[(1-\alpha)(1-G(c)),\ (1-G(c))+\alpha G(c)] .$$
  It equals $1-G(c)$ only as α → 0.
- "Increases with t" ✓ (trivially non-decreasing). δ = 0 with symmetric continuous U gives $1/2\pm O(\alpha)$ ✓.

**Claim 2 — ✓ under independence of $(U_k)$ across k.**
- The ε's may be correlated across k, because they wash out in the limit.
- The ±Kα band is correct ($\lvert\prod a-\prod b\rvert\le\sum\lvert a-b\rvert$) but vacuous for K ≥ 10 at α = 0.05.
- A sharper band under independence: $[1-\prod(G_k+\alpha(1-G_k)),\ 1-(1-\alpha)^K\prod G_k]$. At K = 10 this is [0.9940, 0.9975].
- Numbers ✓: $G=\Phi(0.1971)=0.5781$; K = 10 → 0.9958; K = 48 → $1-3.8\times10^{-12}$.
- **The careful statement, valid for any dependence:**
  $$\lim\text{FWER}\ge\max_k\big(1-G_k(c)\big)-\alpha\ (\ge0.37\text{ here}).$$
  Positive dependence pulls the limit toward this bound; comonotone U gives $0.42\pm\alpha$.

## 10. What is safe to put in a paper

**Safe, with the stated assumptions:**
1. **Cap identity and stability.** $\mu_{\rm cap}(n)=\mu(\min(n,N))$, stable iff $\lambda<\mu(N)$. It is exact and verified in the data.
2. **Prop. A.** Under FCFS-type ordering, $\mu_\infty=\lambda_{\rm miss}$ for every eviction rule, with the token-time proof under (A1)–(A3).
3. **The operating map.** The fluid fixed-point classification and the window $\mu_\infty<\lambda<\mu^*$, plus the recovery threshold $\mu(x_0)$ from congestion. Label this a quasi-static approximation and pair it with the R4-type empirical check.
4. **The $E_{lb}$ identity** via $H=\lambda G$, using the phase-resolved formula. Cap recommendations must include the fluctuation margin.

**Not safe:**
- "$\mu_\infty\approx\lambda_{\rm miss}$ for every work-conserving policy, including LPM."
- "Best cap ≈ $N_{lb}$."
- "$b_c\approx n_2-n_1$" for bursts.
- $\exp(kV)$ stated as a theorem, or any claim of Freidlin–Wentzell rigor.
- Prop. B can be presented as an empirically supported mechanism: the hit-vs-Z table and the tool-distribution sweep need to be re-run as a registered experiment from a clean tree.

---

## Appendix A — scripts and raw outputs (scratchpad, not in the repo)

Scratchpad root: `/private/tmp/claude-501/-Users-akshat--claude-spares-spare-s4RBTK/35e553dd-58fc-4519-895b-5660310d7f7b/scratchpad/`

| File | Contents |
|---|---|
| `analytic.py`, `analytic2.py` | $E_{lb}$ variants, CLT caps, cohort peak, fixed points, BD escape, horizon bias, session-effects numbers |
| `lpm_mech.py` → `lpm_mech_out.jsonl` | LPM/FCFS closed n = 96–300, hit by Z, evicted-KV lifetimes, tool-distribution variants |
| `closed_curve.py` → `fcfs_curve.jsonl` | Fine k = 1 FCFS-LRU curve, seeds 0–2 |
| `closed_curve.py` → `fcfs_bistab.jsonl` | 150k-s window-hit distributions |
| `closed_acf.py` | Hit-rate autocorrelation; output printed in the session only, numbers in §1 |

Environment: `/opt/anaconda3/bin/python`, NumPy 1.26.4, SciPy 1.13.1. Engine imported from `.claude/worktrees/prefix-meta/src` at HEAD db30e76 plus uncommitted diff `06c9e0fb276e`. Each run takes under 1 s of wall time.
