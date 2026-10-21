# Session random effects break in-session (sequential) benchmark tests: derivation sketch

Status: my derivation, 2026-10-20 overnight. **Not math-checked.** I flag the steps I'm least sure of.

## Model
Candidate $k\in\{1,\dots,K\}$ and session $s$ (a fresh process plus memory placement; on GPUs a node, a job, or a clock/thermal state). Paired block $j$ gives the log-speedup
$$X_{ksj}=\theta_k+U_{ks}+\varepsilon_{ksj},$$
where:
- $U_{ks}$ is iid over sessions, with mean 0, variance $\tau_k^2$, and a continuous distribution $G_k$. This is the candidate×session interaction left after pairing.
- $\varepsilon_{ksj}$ is conditionally mean-zero given the past and bounded, with variance $\sigma^2$.

Estimand: $\theta_k$, the speedup averaged over sessions/placements. "Real improvement" means $\theta_k>\log(1+\delta)$.

**Pilot evidence that $\tau_k>0$ matters.** On the M3 Max CPU (`results/vat_collect/20261020-221946`), serial column-major tiled stencils have $\hat\tau\approx0.12$–$0.19$ against $\hat\sigma\approx0.07$–$0.09$. The placement experiment (`results/vat_alignment/`) shows this is largely deterministic in the relative alignment of the two grids. Equal offsets give a log-ratio of −1.38, unequal offsets give −0.78, and the pattern is reproducible across processes (cell-mean correlation 0.67–0.76).

## Claim 1: in-session tests certify session luck with probability not vanishing in $t$, at any $\alpha$
Let $(C_t)$ be any level-$\alpha$ confidence sequence for the conditional mean, built from blocks of a single session $s$. The PrPl-EB CS (Waudby-Smith & Ramdas) is valid under conditional-mean assumptions, so it covers $\mu_{ks}=\theta_k+U_{ks}$ (not $\theta_k$) with $P(\exists t:\mu_{ks}\notin C_t)\le\alpha$. Its width $w_t\to0$ a.s. (for PrPl-EB, $w_t=\tilde O(\sigma\sqrt{\log(1/\alpha)\log t/t})$; **check the rate**).

Take the decision "accept $k$ at time $t$ if $\inf C_t>\log(1+\delta)$".
- On the coverage event, accept by $t$ $\Rightarrow$ $\mu_{ks}>\log(1+\delta)$.
- If $\mu_{ks}>\log(1+\delta)+w_t$ on the coverage event, then acceptance has happened by $t$, using the running intersection.

So for a null candidate ($\theta_k\le\log(1+\delta)$, say $\theta_k=0$):
$$P(U_{ks}>\log(1+\delta)+w_t)-\alpha\;\le\;P(\text{accept by }t)\;\le\;P(U_{ks}>\log(1+\delta))+\alpha .$$
As $t\to\infty$ the probability tends to $1-G_k(\log(1+\delta))$, up to $\pm\alpha$. **The limit does not depend on $\alpha$, and the probability increases with $t$**: more sampling makes false certification more likely. When $\delta=0$ and $U$ is symmetric, the limit is $1/2$.

## Claim 2: with $K$ null candidates in one session, FWER tends to $1-\prod_k G_k(\log(1+\delta))$
If the $U_{ks}$ are independent across $k$, then by the same argument
$$\lim_{t\to\infty}\text{FWER}\in\Big[1-\prod_k G_k(\log(1+\delta))\;\pm\;K\alpha\Big].$$
With a Bonferroni level $\alpha/K$, the $\pm$ term becomes $\alpha$, and the limit is unchanged. Numerical example: Gaussian $U$, $\tau=0.15$, $\delta=0.03$ gives $G=\Phi(0.0296/0.15)\approx0.578$. Then $K=10$ gives FWER$\to\approx0.996$, and $K=48$ gives FWER$\to\approx1-4\times10^{-12}$. **Caveat:** independence across $k$ is an assumption. In the placement experiment, candidates with similar access patterns share the same $U$ structure, so the $U_{ks}$ are correlated. Positive correlation lowers the limit but leaves it far above $\alpha$. This needs a careful statement.

## Claim 3: valid fix, cluster-level CS with cost-optimal blocks per session
- Sample sessions iid, e.g. a fresh process with randomized placement, or a fresh node/job on a GPU cluster.
- Let $\bar X_{ks}$ be the mean of $m$ blocks in session $s$. Then $\bar X_{ks}$ is iid over $s$, with mean $\theta_k$ and variance $\tau_k^2+\sigma^2/m$.
- Build the CS on the sequence $(\bar X_{ks})_s$. It is valid for $\theta_k$ under optional stopping and racing, with $\alpha/K$ for family-wise control.
- Let the cost per session be $c_s+m c_b$. Minimizing cost per unit Fisher information $(c_s+mc_b)(\tau^2+\sigma^2/m)$ gives $m^*=\sqrt{c_s\sigma^2/(c_b\tau^2)}$. This is two-stage sampling (Cochran), and in benchmarking Kalibera & Jones (ISMM 2013) derive the fixed-$n$ analogue. **This part is not new; cite it.**
- **Cheaper variant (needs care).** Suppose $U_{ks}=g_k(Z_s)$ for a placement variable $Z$ that can be re-drawn inside a session at cost $c_z\ll c_s$, e.g. allocation offsets as in STABILIZER (Curtsinger & Berger, ASPLOS 2013; **verify the citation**). Then re-drawing $Z$ per block makes the blocks conditionally mean $\theta_k+\mathbb E[g_k(Z)\mid\text{session}]$. That is only valid if the remaining session effect (JIT state, node, clock) is negligible, which is an empirical question.

## What would be new (if the lit check agrees)
1. The sharp statement that anytime-valid / sequential acceptance gates of the kind now proposed for self-improving agents (PACE-style, or CS racing) are **asymptotically certain to accept** null candidates when evidence comes from one session. More data makes it worse.
2. Measurements of $\tau_k$ for agent-relevant workloads on GPUs (A100/H200 on Nova). The specific quantity is the *paired* candidate×node/process interaction, not just node-to-node variability, which is known (e.g. "Not All GPUs Are Created Equal", SC22; **verify the citation**).
3. A protocol that is valid for $\theta_k$, plus its cost, measured end to end in an agent loop.
