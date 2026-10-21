# Metastability in agentic prefix-cache serving: thrashing-curve theory (v3, DRAFT)

Status: written 2026-10-21 ~04:15 by the main session. It supersedes the claims in `THEORY_prefix_meta.md`. **Not yet checked**; it is being sent to `math-checker`. Steps I'm unsure of are marked ⚠.

## 1. Setup
- **Sessions.** Each session has $T$ turns. Before turn $t$ its context is $L_t$. Between turns it spends a tool time $Z_t$, iid with mean $\bar z$.
- **Server.** One server has KV capacity $M$ tokens.
- **Work per turn.**
  - A hit costs prefill of $\Delta$ tokens plus decode.
  - A miss costs prefill of the full $L_t+\Delta$ plus decode.
  - The cost is in GPU-time under continuous batching at the prevailing batch size.
- **Closed system with $n$ sessions.** Whenever a session finishes, a fresh session (turn 1) replaces it. $\mu(n)$ is the long-run session completion rate. This is the thrashing curve, i.e. throughput as a function of the multiprogramming level (Denning 1968).
- **Open system.** Arrivals are Poisson($\lambda$). $N(t)$ is the number of sessions in the system, counting queued and in-tool sessions.

## 2. Fluid picture
*Heuristic; assumes the internal state equilibrates quickly at fixed $n$.*

$$\dot n=\lambda-\mu(n).$$

Suppose $\mu$ rises to a maximum $\mu^\*=\mu(n^\*)$ and then decreases to $\mu_\infty=\lim_{n\to\infty}\mu(n)$, with $\mu_\infty<\mu^\*$. Then:
- **(i)** If $\lambda<\mu_\infty$, there is a unique globally attracting fixed point. ⚠ This also needs $\mu(n)>\lambda$ for all large $n$, which holds if $\mu$ is non-increasing past $n^\*$.
- **(ii)** If $\mu_\infty<\lambda<\mu^\*$, there are two fixed points, $n_1<n^\*<n_2$. Here $n_1$ is stable and $n_2$ is unstable. For $n>n_2$, $n\to\infty$. The system is bistable.
  - The critical burst that pushes the system from the good state into divergence has size $b_c(\lambda)\approx n_2(\lambda)-n_1(\lambda)$.
  - The recovery threshold from congestion is $\mu_\infty$.
  - ⚠ This only applies if $\mu$ is monotone on each side of $n^\*$. Real $\mu(n)$ may have a plateau or a non-monotone tail.
- **(iii)** If $\lambda>\mu^\*$, the system is transient from every state.
- **Finite size.** In a finite system, Poisson fluctuations eventually carry $N(t)$ past $n_2$. The escape time behaves like $\exp(k\,V(\lambda))$, where $k$ is the system size and $V$ is a quasi-potential (Freidlin–Wentzell type). ⚠ That form is standard for density-dependent jump processes, but I have not checked its regularity conditions here.
  - Consequence: the "stable for horizon $H$ from empty" limit $\lambda_{\rm cap}(k;H)$ increases toward $\mu^\*$ as $k$ grows.
  - Round 3 is consistent with this: $\lambda_{\rm cap}(k)/\lambda_{\rm miss}$ = 1.25, 1.36, 2.41, 3.25, 4.31 for $k$ = 0.25 → 4. The fluid $\mu^\*(k)$ has not been measured yet; round 4 measures it.

## 3. The thrashing curve for agent sessions
- **Resident KV.** In the closed system, the expected total context of the $n$ sessions present is $n\,E_{lb}[L]$, where
  $$E_{lb}[L]=\frac{\mathbb E\big[\sum_{t\le T}L_t\,\tau_t\big]}{\mathbb E\big[\sum_{t\le T}\tau_t\big]},\qquad \tau_t=\text{time spent at turn }t\ (\text{service} + Z_t).$$
  This follows from renewal-reward plus PASTA-like time averaging over the replacement process. It is length-biased: long sessions are over-represented, and late turns weigh more.
- **Below the working-set level.** If $n\,E_{lb}[L]\le M$ (with slack for fluctuations), no idle KV needs eviction. Almost every follow-up turn hits, and
  $$\mu(n)\approx\min\big(n/\mathbb E[\text{lifetime}_{\rm hit}(n)],\ \lambda_{\rm hit}\big).$$
  Lifetime grows with $n$ through batching slowdown.
- **Above the working-set level, under LRU.** Each session re-references its KV once per cycle (tool time plus queueing). With roughly synchronous cycles, the reference string is close to cyclic, and LRU on a cyclic string whose working set exceeds the cache yields zero hits. Classical sources: LIRS (Jiang & Zhang 2002), EELRU (Smaragdakis et al.), Chou & DeWitt (1985).
  - So $\mu(n)$ drops sharply to about the all-miss rate $\lambda_{\rm miss}$ just past $N_{lb}=M/E_{lb}[L]$.
  - ⚠ Heavy-tailed $Z$ breaks the cyclic structure. RR-Evict (2609.32278) models returns as uniformly random, and under that model LRU degrades more gracefully.
- **Large $n$.** For any eviction rule under work-conserving admission, $\mu_\infty=\lambda_{\rm miss}$.
  - **Argument.** With $n\to\infty$ and FCFS-like service, a session's wait between turns grows without bound. In the meantime, unboundedly many other sessions are admitted, each reserving $\ge L_{\min}$. The KV in use by running requests saturates $M$, so the idle KV of any particular session is evicted before its next admission, unless the eviction rule shields a set of at most $M/L_{\min}$ sessions.
  - **⚠ Gap: MRU-idle.** A rule like MRU-idle could shield a fixed set of sessions forever. Those sessions hit, but their share of admissions is $O(M/(L\,n))\to0$, so $\mu_\infty=\lambda_{\rm miss}$ still holds. With LPM ordering the shielded sessions could be served more often. I don't have a proof that LPM's $\mu_\infty$ equals $\lambda_{\rm miss}$, and round 3 measured LPM's congested throughput at **1.16** $\lambda_{\rm miss}$. So either the limit is not reached at $n=300$, or LPM keeps a hit fraction of about 0.2. **This needs care.**
- **Admission cap at $N$.** With a cap, $\mu_{\rm cap}(n)=\mu(\min(n,N))$, which is non-decreasing in $n$ when $N\le n^\*$. Then $\mu_\infty^{\rm cap}=\mu(N)$, the system is stable for $\lambda<\mu(N)$, and the best cap is $N=n^\*\approx N_{lb}$.
  - Under LRU, $\mu$ drops sharply just past $N_{lb}$, so a cap slightly above $n^\*$ is catastrophic. That is the observed cliff: caps of 25, 28 and 30 recovered 3/3, 2/3 and 0/3.
  - **Prediction.** Under random or MRU-idle eviction, $\mu$ decays gradually past $N_{lb}$, so the safe cap band widens. Round 4 tests this as R5.

## 4. What the theory predicts, and how round 4 tests it (pre-registered there)
- **R1.** The FCFS-LRU closed curve peaks at $n^\*\in[20,32]$, and $\mu(n)\le1.2\lambda_{\rm miss}$ for $n\ge1.5n^\*$.
- **R2.** Random eviction degrades gracefully: at $n=1.5n^\*$ its $\mu$ is at least 1.25× that of LRU.
- **R3.** The fluid critical burst $n_2-n_1$ at $2\lambda_{\rm miss}$ is within a factor of 2 of the empirical critical burst.
- **R4.** Each policy's recovery threshold from congestion is within ±15% of its $\mu(300)$.
- **R5.** With a cap, random or MRU eviction recovers at caps above $N_{lb}$, where LRU fails.
- **R6.** $\lambda_{\rm cap}(k)/\mu^\*(k)$ increases with $k$.

## 5. Positioning
- **Classical.** Thrashing and working sets (Denning 1968) and metastable failures (Bronson et al., HotOS'21) are known. So is LRU's failure on loops (LIRS, EELRU, Chou-DeWitt).
- **Plausibly new** (provisional; based on the lit checks in `notes/lit/`):
  - **(a)** Identifying that multi-turn agent serving with prefix caches has this bistable structure, with $\mu_\infty\approx\lambda_{\rm miss}$ for every work-conserving policy. That includes ordering-based (LPM) and queued-prefix-protection (PEEK) fixes.
  - **(b)** The length-biased working set $N_{lb}=M/E_{lb}[L]$ as the right admission cap, and the LRU-cyclic cliff that makes it fragile.
  - **(c)** A diagnostic: measure closed-population $\mu(300)$ against open-loop capacity to detect metastability in a deployed engine.
  - **(d)** The finite-size escape picture.
- **Closest prior work.**
  - CONCUR (AIMD caps, empirical).
  - Continuum (TTL pins).
  - PEEK (queued-prefix protection, empirical thrashing).
  - Ao et al. 2606.15555 (instability of greedy admission with KV growth and no prefix caching, plus an admission cap).
  - RR-Evict and "Randomization Boosts KV Caching" (eviction-order fixes).
