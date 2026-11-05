# PAPER_INPUT: theory (round 13, branch `r13/theory`)

For the lead. Written 2026-10-31 after the freeze. Nothing in `paper/` was edited.

## 0. Status, scope, and what this pass changed

**Frozen predictions.** These are unchanged here.
- Freeze commit: `997d2c4d9d25b1d2ef26fdbc8c7b35a9860ceff0`.
- Tag: `r13-theory-pred` (tag object `b900d19...`).
- GitHub push: branch at 07:05:30Z (02:05:30 CDT), followed by the provenance commit `369e337`.
- Record: `notes/PREDICTIONS_r13_theory.md`, `configs/r13_theory_predict.yaml`, `results/theory/merged/*.json`.
- Scoring: `notes/THEORY_r13_scoring.md`.

This file builds on `369e337` without amending or rebasing it, and it changes no frozen number. The H200, Llama-3.1-8B, pool-sweep, B1 and R1/R4 outcomes were **not read** for this write-up. The tables below therefore give predictions only, and each outcome cell is marked *pending*. The paper's results section should fill them in by the frozen scoring rules.

**Blindness of this pass.**
- **Read:** the frozen theory files, the committed data of the three measured cells (through `analysis/theory/fluid_rigorous/cells.py`; no directory whose name contains h200, llama31, r11, b100, b25, e0bfresh, lpminf or rescue), `paper/` (read-only), and literature on the web.
- **Not done:** no ssh to Nova.

**New in this pass, all post-freeze and none moving a prediction:**
1. **Proposition F now has a complete proof** (Appendix, Proof of Proposition F). I re-derived the identity by hand. It is now checked **in magnitude**, not only in sign: `tests/test_theory_paper.py::test_prop_F_identity_in_magnitude` compares the closed form with the finite-difference dn/dR. It agrees to a relative error of 2e-3 at 5 frontier values R, for both the exponential law and a folding mixture. A second test checks the decode-equation identity `-dS_D/dh = rho nu dS_D/dnu` that the proof uses. This settles open problem 10 of the freeze record, which said the proof was only an algebra sketch.
2. **The window-opening condition (T5) is now a corollary of the same derivative.** The Proposition F proof gives dν/dR in closed form, and its sign at R → 0+ is exactly T5.
3. **Adversarial novelty check (section 7).** It found one new uncredited overlap, Yuan et al. (IISWC 2026, arXiv:2605.26297). They measure "context thrashing" under rising agent concurrency (prefix-cache hit rate about 98% → 16-26%) and state the mechanism that drives our cliff: extra prefill slows decode for requests in generation, cutting generation throughput by up to 66%. They give no model. The novelty paragraph credits them, and a BibTeX entry is in section 4. Three other recent preprints were checked and do not overlap (section 7).
4. **Paper figures:** `analysis/theory/paper/figs.py` writes `figures/theory/paper_{mu_validation,fixed_points,scaling}.{pdf,png}`, with the plotted data in `results/theory/paper/*.csv`.
5. **Tests:** `tests/test_theory_paper.py` has 21 tests: the Proposition F magnitude check, the ρ identity, T3(b)/(c), the quoted numbers against the frozen JSONs, and the three-state fold example. All pass.

**Two rounding inconsistencies in the frozen prose.** The frozen JSONs are authoritative, and the LaTeX below uses their values.
- The H200 F1 μ_max is 0.3715 in `h200_300k.json`. `PREDICTIONS_r13_theory.md` rounds it to "0.372"; correctly rounded it is 0.371.
- "Hit ≈ 0.69 at the peak" is the F1 hit at the grid point n = 32 (0.690). At the F1 peak n = 32.5 the hit is 0.674.
- The vLLM F1 μ_max error on the turns-based estimator is +11.7% in `validation_table.md`. The freeze text says +11.6%.

None of these changes a scoring rule.

## 1. Main-text LaTeX: subsection for `sections/model.tex` (after `\ref{sec:props}`) or a new section

Preamble additions needed (main.tex already has `proposition` and `remark*`):

```latex
\newtheorem{lemma}[proposition]{Lemma}
\newtheorem{corollary}[proposition]{Corollary}
\newtheorem*{assumption}{Assumption MF}
```

```latex
\subsection{A first-principles model of the thrashing curve}\label{sec:fp}
Section~\ref{sec:fluid} takes $\mu(n)$ as measured. Here we \emph{predict} it, together with the window, the all-miss level,
the trapped state and the cap condition, from the pool size $M$, the workload of \S\ref{sec:notation}, the tool-time law,
and the iteration-cost model of our simulator (\S\ref{sec:sim}), which was fitted only to server-log iteration timings. No
parameter is fitted to any $\mu(n)$ point, from-empty outcome or trap measurement. Every statement below is about a
deterministic fluid model; we do not prove that the engine converges to it.

\paragraph{Model.} Let $w_k=P(T\ge k)/E[T]$ be the turn mix, $E_k=L_k+d$ the KV of a session after turn $k$,
$\bar E=\sum_k w_kE_k=10{,}569$ tokens, $A_1=\sum_k P(T\ge k+1)E_k=144{,}960$ the KV a session carries into tool calls over
its life, $E[E_T]=11{,}045$ its final KV, and $\bar z'=E[Z](1-1/E[T])$ its tool time per turn. The tool time $Z$ has
distribution $F_Z$ and density $f$. \emph{Server.} At turn completion rate $\nu$ (turns/s) and follow-up hit probability
$h$, turn $k$ needs prefill GPU time $t_k(h)=t^m_k-h\,\mathbb 1\{k\ge2\}(t^m_k-t^h_k)$, with $t^m_k,t^h_k$ the miss and
hit prefill times of the cost model (a hit prefills $\Delta+1=551$ tokens). SGLang runs prefill and decode in separate
iterations with prefill priority, so prefill takes a fraction $p=\nu\sum_kw_kt_k(h)$ of the GPU and the number $R_D$ of
decoding requests solves $R_D(1-p)=\nu(d-1)\tau_D(R_D)$, where $\tau_D$ is the cost model's decode iteration time. A turn
occupies the engine for $S_k=t_k(h)+S_D$ with $S_D=R_D/\nu$ and reserves its KV $E_k$ throughout, so running requests hold
$K_{\mathrm{run}}(\nu,h)=\nu\sum_kw_kE_kS_k$ tokens. \emph{Memory.} Idle KV (sessions in tool calls, and the KV of finished
sessions, which the engine cannot know is dead) is evicted least recently used first.
\begin{assumption}[Che~\citep{che2002hierarchical,fricker2012versatile}]
In stationarity an idle item is evicted at a deterministic idle age $R$.
\end{assumption}
\noindent By $H=\lambda G$ the idle KV is then $\mu D(R)$ with $D(R)=A_1E[\min(Z,R)]+E[E_T]R$, and the pool is full, so
\begin{equation}\label{eq:balance}
\begin{gathered}
M=K_{\mathrm{run}}(\nu,h)+\frac{\nu}{E[T]}D(R),\qquad h=F_Z(R),\\
n=\nu\,(\bar S+\bar z'),\qquad \mu=\nu/E[T],
\end{gathered}
\end{equation}
the last two being Little's law with $\bar S=\sum_kw_kS_k$. Requests queue only when running reservations alone fill the
pool ($K_{\mathrm{run}}=M$, hence $R=0$ and $h=0$). With $K_{\mathrm{run}}=0$ and no queue, Eq.~\eqref{eq:balance} is the
characteristic-time equation of Yao et al.~\citep{yao2026multiturn} term for term. Three additions make the hit rate feed
back on itself. Running reservations depend on $h$, because under prefill priority misses starve decode. Throughput is set
by a server and a closed population, not by an exogenous arrival rate. And there is a memory-gated all-miss branch.

\begin{proposition}[stationary states and the all-miss onset]\label{prop:nb}
Let $\nu_b$ solve $K_{\mathrm{run}}(\nu,0)=M$, $\mu_b=\nu_b/E[T]$, and
$E_S=\sum_kw_kE_kS_k/\sum_kw_kS_k$ at $(\nu_b,0)$.
(a) Each $R>0$ gives exactly one queue-free stationary state; the states with a queue are exactly the all-miss states
$(h=0,\nu=\nu_b)$; $\mu(n)=\mu_b$ for all large $n$, so $\mu_b$ is the model's $\lmiss$ and $\muinf$.
(b) All-miss states exist exactly for $n\ge n_b$, where
\begin{equation}\label{eq:nb}
n_b=\nu_b\,\bar z'+M/E_S,
\end{equation}
the sessions in tool calls at the all-miss rate plus one pool's worth of running sessions.
(c) If every GPU cost is divided by $s$ (a uniformly faster GPU), then $\nu_b\mapsto s\nu_b$, $E_S$ is unchanged, and
$n_b(s)=n_b(1)+(s-1)\,\nu_b(1)\,\bar z'$.
\end{proposition}
\noindent At 300k, $n_b=4.94+27.76=32.70$ (native pool: 94.86). The pool part $M/E_S$ is the capacity-over-session-footprint
cap of MISA-T~\citep{hong2026misat}. What is new is the tool-call term and the identification of $n_b$ as the onset of the
all-miss branch. Part (c) says that a faster GPU moves the onset \emph{outward}: on the H200 ($s=2.742$, fitted to its
all-miss token rate) $n_b=41.3$.

\begin{proposition}[speed and tool time enter only through $s\bar z$]\label{prop:scaling}
Write $\omega=\mu^*/\mu_b$ for the window and $Z=\bar zY$ with $Y$ fixed. (a) $\lmiss(C/s)=s\,\lmiss(C)$ and
$\omega(C/s,\bar z)=\omega(C,s\bar z)$ exactly, for cost model $C$. (b) $\omega$ is non-increasing in $s\bar z$, strictly
while $\omega>1$. (c) $\omega\to1$ as $s\bar z\to\infty$.
\end{proposition}
\noindent Faster GPUs therefore narrow the window: the good state is limited by memory and tool time, neither of which
speeds up. The same holds for slower tools.

\begin{proposition}[fold identity]\label{prop:fold}
On the queue-free branch parametrized by $R$, with $a=\nu\,\partial_\nu S_D\ge0$, the exact identity
\[
\frac{dn}{dR}=\frac{\nu}{\Phi_\nu}\Big[f(R)\,I(R)-\frac{n_\nu\,D'(R)}{E[T]}\Big]
\]
holds, where $\Phi_\nu=S_E+\bar Ea+D/E[T]>0$, $n_\nu=\bar S+\bar z'+a$, $S_E=\sum_kw_kE_kS_k$, and
$I=a[C_E+\rho(\bar E(\bar S+\bar z')-S_E-D/E[T])]+\beta_E(\bar S+\bar z')-\beta_P(S_E+D/E[T])$, with
$\beta_P=\sum_{k\ge2}w_k(t^m_k-t^h_k)$, $\beta_E=\sum_{k\ge2}w_kE_k(t^m_k-t^h_k)$, $C_E=\beta_E-\bar E\beta_P$ and
$\rho=\beta_P/(\bar t_P(h)+(d-1)\tau_D'(R_D))$. Consequently:
(a) if $f(0^+)I(0^+)>n_\nu\bar E$ at the all-miss end, then $n(R)>n_b$ for small $R$. The closed system then has at least
three stationary states for $n\in(n_b,n_{\mathrm{fold}})$, $n_{\mathrm{fold}}=\max_Rn(R)$: the all-miss state, which is
locally stable, and two queue-free states.
(b) If the bracket is negative for every $R$, then $n(R)$ is strictly decreasing, every $n$ has exactly one stationary
state, and $\mu(n)$ is continuous.
\end{proposition}
\noindent For the registered exponential tool times the ratio $f I/(n_\nu D'/E[T])$ peaks at the all-miss end at 0.805
(300k), 0.826 (native), 0.784 (H200), 0.781 (Llama), 0.761 (150k) and 0.821 (600k). This is checked numerically on 400
values of $R$ per cell. Every cell is therefore fold-free with a 17--24\% margin, and its bistability is an open-system
property. The same identity at $R\to0^+$ gives the window-opening condition: $\mu^*>\mu_b$ if
$f(0^+)\,\Delta_S>1$ with $\Delta_S=(\beta_E+\bar E\rho a)/\bar E$ (595\,s at 300k against $1/f(0^+)=\bar z=5$\,s).
Dispersed tool times reverse the conclusion. With the same 5\,s mean, $0.5\,\mathrm{Exp}(1\,\mathrm s)+0.5\,\mathrm{Exp}(9\,\mathrm s)$
folds the 300k curve up to $n_{\mathrm{fold}}=34.2>n_b=32.7$, where the all-miss state and a good state ($h=0.69$) are both
stable (Fig.~\ref{fig:fixed}b,c); mixtures with coefficient of variation 2.5 and 5 fold up to 38.2 and 44.6. Agent tool
times are this dispersed (CV $\approx3.8$ on SWE-Bench~\citep{li2025continuum}). In that regime $n_b$ is the lower edge of a
bistable band, not the collapse point.

\begin{proposition}[open system and cap rescue; fold-free curve, quasi-static]\label{prop:capfp}
Assume Proposition~\ref{prop:fold}(b) and a unimodal $\mu(n)$, and let $\mu_b<\lambda<\mu^*$. Then
$\dot n=\lambda-\mu(n)$ has a stable $n_1$ and an unstable $n_2\le n_b$; from $n>n_2$, $N$ grows without bound and, once
$n\ge n_b$, exactly linearly at $\lambda-\mu_b$. A FIFO cap $c$ engaged in any state, the trap included, empties its gate
and leaves the system good after release if and only if $n_1(\lambda)<c<n_2(\lambda)$. If the curve folds, the condition is
$n_1<c<\min(n_2,n_b)$.
\end{proposition}
\noindent The condition $c<n_2$ inherits the quasi-static assumption, which is weakest near $n_b$ (\S\ref{sec:fluid}); the
registered caps (20 at 300k, 64 native) lie far below $n_2$ ($\approx32$ and 90), where only $n_1<c<n_b$ matters.

\begin{proposition}[trapped identity]\label{prop:trapid}
In the all-miss FCFS regime, where every present session completes one turn per scheduler cycle, the follow-up gap
divided by $R_M=M/\text{churn}$ (churn = uncached prompt plus completion tokens per second) equals
$\sum_{i}(L_{k_i}+d)/M$ over the sessions present, for any cost model.
\end{proposition}
\noindent Trapped runs therefore have gap$/R_M$ equal to the total next-turn context in the system over the pool (measured
4--10), and good runs have $(\bar z\ln 2+\bar S)\,\text{churn}/M$ (0.01--0.03).

\paragraph{Fluctuation layers (heuristics, nothing fitted).} Two layers sit on top of the deterministic model.
\emph{F1} averages the curve over the KV-demand fluctuation of $n$ sessions: relative variance $0.570/n$, from the turn mix.
\emph{F2} predicts the from-empty edge: demand follows a one-dimensional diffusion with drift $\lambda-\mu(x)$ and noise
intensity $1.567(\lambda+\mu(x))$, the dispersion index of the session shot noise (Campbell), and the run counts as
unstable if it reaches $n_b$ within the 3000\,s horizon. The probability that a burst traps the system is the splitting
probability~\citep{karlin1981second} of the same diffusion, started at the burst cohort's peak live demand. The rescue
release time adds a two-phase drain: resumed sessions first, then fresh arrivals.

\paragraph{Validation.} Table~\ref{tab:fpval} compares the predictions with the three measured cells. Inputs and outputs
are separated: for the SGLang cells the model receives $M$, the workload and the cost model, and predicts everything else;
for vLLM it also receives one speed factor fitted to vLLM's own all-miss token rate, so its $\lmiss$ is not a prediction.
On the turns-based estimator, which measures the model's $\nu/E[T]$, the F1 peak is 3.6\% and 6.3\% high on the SGLang
cells, and the fluid peak 9.9\% and 9.0\% high. Assumption MF is the likeliest cause. One session is 3.5\% of a 300k pool,
so the eviction age does not concentrate, and because the hit probability is concave in $R$, a deterministic $R$
overstates hits near the peak. The vLLM cell is a partial miss: its cliff comes earlier and steeper than predicted.

\begin{table*}[t]\centering\small
\caption{First-principles predictions against measurements (\fpath{results/theory/merged/validation_table.md}).
Inputs: pool, workload, server-log cost model; vLLM also one speed factor fitted to its own $\lmiss$ token rate.
Measured $\mu$ is turns-based. $^\dagger$The F2 edge criterion was chosen knowing these two brackets (in-sample).}\label{tab:fpval}
\begin{tabular}{@{}lccc@{}}\toprule
 & SGLang 300k & SGLang native & vLLM 300k\\\midrule
$\lmiss$ (turns), pred / meas & 0.0718 / 0.0715 & 0.0718 / 0.0718 & fitted (0.0670 / 0.0657)\\
$\mu^*$ F1 (fluid), pred / meas & 0.234 (0.248) / 0.226 & 0.495 (0.508) / 0.466 & 0.235 (0.249) / 0.211\\
peak $n$ F1, pred / meas flat top & 24 / 20--24 & 69.5 / 64--80 & 24 / 20--24\\
0.5-hit crossing $n$, pred / meas & 31.5 / 32.2 & 93.7 / 93.4 & 31.8 / 29.1\\
window $\mu^*/\lref$ F1, pred / meas & 3.27 / 3.15 & 6.89 / 6.48 & 3.58 / 3.21\\
from-empty bracket, pred / meas & $[2.0,2.5]^\dagger$ / $[2.0,2.5]$ & $[5.5,6.5]^\dagger$ / $[5.5,6.5]$ & $[2.5,3.0]$ / $[2.0,2.5]$\\
trapped backlog, pred / meas & 215, 304 / 200--232, 283--332 & 565, 1089 / 557--601, 1098--1139 & 206, 288 / 203--227, 277--309\\
trapped token rate$/\lmiss$ & 1.006, 1.016 / 1.009--1.029 & 1.067, 1.079 / 1.074--1.124 & 0.992, 1.002 / 0.997--1.031\\
good-state hit, pred / meas & 0.932 / 0.921--0.934 & 0.932 / 0.929--0.935 & --\\
capped drain (s), pred / meas & 1576, 1941 / 1547--2693 & 493, 815 / 512--937 & --\\\bottomrule
\end{tabular}
\end{table*}

\paragraph{Out-of-sample predictions.} Frozen and pushed before any result was read (tag \texttt{r13-theory-pred},
\fpath{notes/PREDICTIONS_r13_theory.md}), with primaries, estimators, tolerances and refutation rules fixed in advance
(\fpath{notes/THEORY_r13_scoring.md}):
\begin{itemize}[leftmargin=*,itemsep=1pt,topsep=2pt]
\item \emph{H200} (same engine, model and 300k pool). Its only input beyond the A100 cell is its all-miss token rate, which
fixes $s=2.742$. Proposition~\ref{prop:scaling} predicts that the window narrows to $1.92$ (A100: 3.27 predicted, 3.15
measured). Proposition~\ref{prop:nb}(c) predicts that the onset moves out to $n_b=41.3$, with the 0.5-hit crossing at 37.3
and only 67\% hits at the peak $n\approx32.5$. The F2 edge is $1.39\lref$, against 2.0--2.5 on the A100. Refuted by: window
$\ge2.4$, hit$(32)<0.5$, or hit$(48)\ge0.5$. [\pending{H200 outcome}]
\item \emph{Pool sweep} (A100, zero fitted parameters). Window 1.87 / 5.47 at 150k / 600k tokens; $n_b=18.3$ / 61.2; F2
edge $1.09$ / $4.53\lref$. [\pending{pool-sweep outcome}]
\item \emph{Llama-3.1-8B} (A100, 300k, a priori). The pool part of $n_b$ ($M/E_S=27.8$) does not depend on the model's
speed. With roofline cost ratios: window 3.37, $n_b=32.0$, edge $2.46\lambda_{\mathrm{miss}}$. A conditional rule
re-scales these once its own $\lmiss$ is measured. [\pending{Llama outcome}]
\item \emph{Critical burst} (300k). Deterministic critical fresh burst 59.4 / 53.4 / 46.1 sessions at 1.35 / 1.65 /
2.0$\lref$; the 50\% committor point is 56 / 50 / 42. For the registered basin test (1.65$\lref$), P(trapped) is 1.000 for a
burst of 100 and 0.042 for 25. [\pending{B1 outcome}]
\item \emph{Rescue} (cap 20 at 1800\,s in the 300k trap). Gate released at 3830\,s (1.35$\lref$) and 4360\,s (1.65$\lref$);
relapse probability 0.002 / 0.025. Release by the 7200\,s deadline needs the resumed sessions to run at $\ge$32\% / 42\% of
their fluid rate. If they run at their all-miss rate, the deadline is missed (7510\,s / 9240\,s). Native pool, cap 64 at
4.0$\lref$: release at 5040\,s, needing $\ge$51\% of the fluid rate. [\pending{R1/R4 outcome}]
\end{itemize}
The rescue and B1 verdicts are also what the simulator predicts; the release times and the critical burst are the theory's
own.

\paragraph{Relation to prior models.} Yao et al.~\citep{yao2026multiturn} give a mean-field (Che-type) LRU hit ratio for
multi-turn sessions with exogenous gaps between turns, a rate scaled with memory, and prefill/decode disaggregation. Their
characteristic-time equation already contains the term for content that is never reused, and it has a unique fixed point.
Eq.~\eqref{eq:balance} reduces to it when nothing runs and nothing queues. On every partially hitting state our reuse gap is
still the exogenous tool time. The feedback runs instead through service time and reserved KV: misses starve decode under
prefill priority, which swells running reservations and squeezes idle KV. That turns their unique fixed point into a curve
with a rise, a peak, a cliff at Eq.~\eqref{eq:nb} and an all-miss branch, on which the queue sets the reuse gap
(Proposition~\ref{prop:trapid}). Yuan et al.~\citep{yuan2026agentic} measure this decode slow-down under ``context
thrashing'' as agent concurrency rises. MISA-T~\citep{hong2026misat} describes the eviction--cold-prefill--queue loop in
words, measures the collapse, derives a session cap equal to the pool part of Eq.~\eqref{eq:nb}, and contracts that cap on a
hit-rate decline. Neither gives equilibria, a rescue condition or a fold criterion. The Che approximation and its
analyses~\citep{che2002hierarchical,fricker2012versatile,martina2014unified} take request processes as exogenous. Here it
enters as Assumption MF, and the pool sizes here sit at the edge of its validity. The closed curve is a Denning thrashing
curve~\citep{denning1968thrashing}, and Proposition~\ref{prop:capfp} is the classical decomposition
argument~\citep{courtois1975decomposability} applied to a \emph{predicted} $\mu(n)$. Metastable-failure
models~\citep{bronson2021metastable,isaacs2025analyzing,alvaro2025formal,habibi2024msf,farahbakhsh2025modeling} study
retry- and timeout-sustained metastability with Markov chains, simulation or stress tests. Here the sustaining effect is
cache loss, and the thresholds are predicted from independent inputs. What we believe is new: a predicted thrashing curve
for prefix-cached agent serving, the onset identity and its speed corollary, the $s\bar z$ window law, the exact fold
criterion showing that dispersed tool times make even the closed system bistable, the cap condition with hysteresis, and
the trapped identity. Our literature search was targeted, not exhaustive.
```

Suggested figure environments (files in `figures/theory/`; the lead copies them into `paper/figs/`):

```latex
\begin{figure*}[t]\centering
\includegraphics[width=\textwidth]{figs/paper_mu_validation.pdf}
\caption{Predicted thrashing curves against the engine. Lines: the first-principles model (solid, fluid; dashed, with the
demand-fluctuation layer F1). Its inputs are the pool, the workload and a cost model fitted to server-log timing only; vLLM
also gets one speed factor fitted to its all-miss token rate. Points: measured $\mu(n)$, sessions/s (filled) and turns-based
(open). The dotted line marks the predicted all-miss onset $n_b$ (Eq.~\ref{eq:nb}); the dash-dotted line marks the measured
$\lmiss$. No measured $\mu(n)$ point enters the prediction.}\label{fig:fpmu}
\end{figure*}

\begin{figure*}[t]\centering
\includegraphics[width=\textwidth]{figs/paper_fixed_points.pdf}
\caption{Fixed points. (a) Open system, predicted 300k curve at $1.65\lref$: stable good state $n_1$, basin boundary
$n_2$ ($n_u$), all-miss onset $n_b$, and the trap, where $N$ grows at $\lambda-\mu_b$. (b) Closed system at $n=33.5>n_b$:
the feedback map $\Phi_n(h)$ (hit probability produced at hit probability $h$). With the registered exponential tool times
the all-miss state is the only fixed point. With a two-phase law of the same 5\,s mean (CV 1.5), the all-miss state and a
good state ($h=0.69$) are both stable, and an unstable state ($h=0.29$) separates them. (c) The two closed curves: the
dispersed law folds above $n_b$ (shaded band), as Proposition~\ref{prop:fold} predicts.}\label{fig:fixed}
\end{figure*}

\begin{figure}[t]\centering
\includegraphics[width=\columnwidth]{figs/paper_scaling.pdf}
\caption{The window law. (a) $\omega=\mu^*/\mu_b$ of the 300k model against $s\bar z$, the tool time in A100-equivalent
seconds (Proposition~\ref{prop:scaling}). A100 measured; H200 frozen prediction, whose outcome is reported in
\S\ref{sec:results}. (b) $\omega$ against the pool size. Measured cells and the frozen pool-sweep predictions are shown.}\label{fig:fpscale}
\end{figure}
```

(`paper_scaling.pdf` is 7.2 in wide; use `figure*`, or ask me for a one-column version.)

## 2. Appendix LaTeX: model details and proofs

```latex
\section{First-principles model: details and proofs}\label{app:fp}

\paragraph{Cost model and server.} The prefill GPU time of $x$ new tokens on a cached prefix of $c$ tokens is
$t_P(x,c)=a\max(1,x/B)+\max(f_0,bx)+c_p\,x\,(c+(x+1)/2)$, with $a=9.24$\,ms, $f_0=1.26$\,ms, $b=62.6\,\mu$s/token,
$c_p=2.24$\,ns per causal pair and chunk $B=8192$
(\fpath{calibration/round6_server_log_fit/calibration.yaml}). For a miss, $t^m_k=t_P(L_k,0)$; for a hit,
$t^h_k=t_P(551,L_k-551)$; turn~1 always misses. A decode iteration over $R_D$ requests takes
$\tau_D(R_D)=a+\max(f_0,bR_D)+\beta_cR_D$, with $\beta_c=c_d\bar c_D/8192$, $c_d=0.31$\,ms and $\bar c_D$ the mean decode
context. We assume: (A2a) a turn's prefill latency is its own prefill GPU time, with no queueing behind other prefills;
(A2b) the GPU is busy whenever a request runs; (A2c) a running request reserves $E_k$ from admission to completion, with no
retraction. For vLLM, prefill and decode share iterations: $S_D=(d-1)/I$, with iteration rate
$I=(1-\nu c_{\mathrm{turn}})/a$.

\begin{lemma}[fluid server]\label{lem:server}
Fix $h$, and let $\nu_{\mathrm{cap}}(h)=1/(\bar t_P(h)+(d-1)(b+\beta_c))$. For $\nu<\nu_{\mathrm{cap}}(h)$ the decode
equation has exactly one positive root; for $\nu \ge \nu_{\mathrm{cap}}(h)$ it has none. $S_D$ is continuous, strictly increasing in
$\nu$, non-increasing in $h$, and $S_D\to\infty$ as $\nu\uparrow\nu_{\mathrm{cap}}(h)$. $K_{\mathrm{run}}(\nu,h)$ increases
strictly in $\nu$ from $0$ to $\infty$ and decreases strictly in $h$.
\end{lemma}
\begin{proof}
$\psi(R)=R/\tau_D(R)$ is continuous and strictly increasing, since $\tau_D$ is affine with positive intercept on each side
of the kink $f_0/b$. Moreover $\psi(0)=0$ and $\psi(\infty)=1/(b+\beta_c)$. The decode equation reads
$\psi(R_D)=\nu(d-1)/(1-p)$, which has a unique root iff the right side is below $1/(b+\beta_c)$, i.e.
$\nu<\nu_{\mathrm{cap}}(h)$. The right side increases in $\nu$ and does not increase in $h$, because $t^h_k\le t^m_k$; so
does $R_D$, which diverges at $\nu_{\mathrm{cap}}$. Then $S_D=R_D/\nu=(d-1)\tau_D(R_D)/(1-p)$ is a product of positive
factors with the same monotonicity. $K_{\mathrm{run}}=\nu\sum_kw_kE_k(t_k(h)+S_D)$ inherits it; strict decrease in $h$
follows from $\partial_hK_{\mathrm{run}}=-\nu(\beta_E+\bar E\rho a)<0$ (Lemma~\ref{lem:rho}).
\end{proof}

\begin{lemma}[decode sensitivity]\label{lem:rho}
Away from the kink, $-\partial_hS_D=\rho\,\nu\partial_\nu S_D$, with $\rho=\beta_P/(\bar t_P(h)+(d-1)\tau_D'(R_D))$ and
$\nu\partial_\nu S_D=R_D(\bar t_P+(d-1)\tau_D')/J>0$, where $J=(1-p)-\nu(d-1)\tau_D'>0$.
\end{lemma}
\begin{proof}
Write $G(R_D,\nu,h)=R_D(1-\nu\bar t_P(h))-\nu(d-1)\tau_D(R_D)$. Then $\partial_{R_D}G=J$; at the root,
$J=(1-p)\alpha/\tau_D>0$, with $\alpha>0$ the intercept of $\tau_D$. Next, $\partial_\nu G=-R_D\bar t_P-(d-1)\tau_D$ and
$\partial_hG=\nu R_D\beta_P$, since $\partial_h\bar t_P=-\beta_P$. Hence $\partial_hS_D=\partial_hR_D/\nu=-R_D\beta_P/J$ and
$\nu\partial_\nu S_D=\partial_\nu R_D-R_D/\nu=[R_D\bar t_P+(d-1)\tau_D-JR_D/\nu]/J$. Substituting
$JR_D/\nu=R_D/\nu-R_D\bar t_P-R_D(d-1)\tau_D'$ and $R_D/\nu=(d-1)\tau_D/(1-p)$ gives
$(d-1)\tau_D-R_D/\nu=-pR_D/\nu=-\bar t_PR_D$, so the numerator equals $R_D(\bar t_P+(d-1)\tau_D')$.
\end{proof}

\begin{proof}[Proof of Proposition~\ref{prop:nb}]
(a) Fix $R>0$ and $h=F_Z(R)$. The function $\nu\mapsto K_{\mathrm{run}}(\nu,h)+\nu D(R)/E[T]-M$ is continuous and strictly
increasing (Lemma~\ref{lem:server}). It equals $-M$ at $\nu=0$ and is unbounded at $\nu_{\mathrm{cap}}$, so it has exactly
one root $\nu(R)$, which is continuous in $R$. A state with a queue has $K_{\mathrm{run}}=M$, so $\mu D=0$, hence $R=0$,
$h=0$ and $\nu=\nu_b$. From $\nu D(R)/E[T]\le M$ and $D(R)\ge E[E_T]R$ we get $\nu(R)\to0$ as $R\to\infty$. As $R\downarrow0$,
$\nu(R)\to\nu_b$ by continuity, since $\nu_{\mathrm{cap}}(0)$ is excluded. So $n(R)$ is bounded on $(0,\infty)$, and beyond
its supremum and $n_b$ only the all-miss state remains.
(b) $K_{\mathrm{run}}(\nu_b,0)=\nu_b\sum w_kE_kS_k=M$ gives $\nu_b\bar S=M/E_S$; Little's law at $W=0$ gives
$n_b=\nu_b\bar S+\nu_b\bar z'$. For $n>n_b$ the all-miss state carries a queue of $(n-n_b)/\nu_b$ seconds.
(c) Divide every cost by $s$ and time by $s$: every service time scales by $1/s$ and every rate by $s$, and the decode
equation and $p$ are invariant. So $(\nu,h)$ solves $K_{\mathrm{run}}=M$ for costs $C$ iff $(s\nu,h)$ does for $C/s$. Hence
$\nu_b(s)=s\nu_b(1)$; $E_S$, a ratio of $S$-weighted sums, is invariant; substitute into (b).
\end{proof}

\begin{proof}[Proof of Proposition~\ref{prop:scaling}]
(a) Rescaling time by $s$ maps a stationary state $(n,\nu,h,R)$ of $(C/s,\bar z)$ to $(n,\nu/s,h,sR)$ of $(C,s\bar z)$. Each
equation of Eq.~\eqref{eq:balance} is invariant: Little's law and $K_{\mathrm{run}}$ are rate$\times$time,
$E[\min(\bar zY,R)]=s^{-1}E[\min(s\bar zY,sR)]$, and $h$ compares times. Both $\mu^*$ and $\mu_b$ scale by $s$, so their
ratio depends on $s\bar z$ only.
(b) Parametrize the queue-free states by $h\in(0,1)$, with $r(h)=F_Y^{-1}(h)$ and $m(h)=E[\min(Y,r(h))]$. The balance reads
$K_{\mathrm{run}}(\nu,h)+\nu\bar z(A_1m(h)+E[E_T]r(h))/E[T]=M$. Its left side increases strictly in $\nu$ and in $\bar z$,
so $\nu(h;\bar z)$ decreases strictly in $\bar z$, while $\nu_b$ (the equation at $h=0$) does not involve $\bar z$. Take
the supremum over $h$, and apply (a) for $s$.
(c) For $h\ge h_0>0$, $\nu(h;\bar z)\le ME[T]/(\bar z(A_1m(h_0)+E[E_T]r(h_0)))\to0$. For $h<h_0$, $\nu(h;\bar z)$ is below
the root of $K_{\mathrm{run}}(\nu,h)=M$, which tends to $\nu_b$ as $h_0\to0$.
\end{proof}

\begin{proof}[Proof of Proposition~\ref{prop:fold}]
On the branch, $\Gamma(\nu,R)=\nu S_E(\nu,h)+\nu D(R)/E[T]-M=0$ and $n=\nu(\bar S+\bar z')$, with $h=F_Z(R)$ and
$dh/dR=f(R)$. From $S_k=t_k(h)+S_D(\nu,h)$ we have $\partial_h\bar S=-\beta_P+\partial_hS_D$,
$\partial_hS_E=-\beta_E+\bar E\partial_hS_D$, $\partial_\nu\bar S=\partial_\nu S_D$ and $\partial_\nu S_E=\bar E\partial_\nu S_D$.
By Lemma~\ref{lem:rho}, $\partial_hS_D=-\rho a/\nu$ with $a=\nu\partial_\nu S_D$. Then
$\partial_\nu\Gamma=S_E+\bar Ea+D/E[T]=\Phi_\nu>0$ and $\partial_R\Gamma=-\nu f(\beta_E+\bar E\rho a)+\nu D'/E[T]$, so
\[\frac{d\nu}{dR}=\frac{\nu}{\Phi_\nu}\Big[f(\beta_E+\bar E\rho a)-\frac{D'}{E[T]}\Big].\]
Next, $dn/dR=n_\nu\,d\nu/dR+\nu f\,\partial_h\bar S=n_\nu\,d\nu/dR-\nu f(\beta_P+\rho a)$, with $n_\nu=\bar S+\bar z'+a$.
Put both over $\Phi_\nu$: the coefficient of $\nu f/\Phi_\nu$ is
$I=n_\nu(\beta_E+\bar E\rho a)-(\beta_P+\rho a)\Phi_\nu$. Expanding, the terms $\bar E\rho a^2$ cancel. Collecting the terms
linear in $a$ gives $a[\beta_E-\bar E\beta_P+\rho(\bar E(\bar S+\bar z')-S_E-D/E[T])]$, and the remainder is
$\beta_E(\bar S+\bar z')-\beta_P(S_E+D/E[T])$. This is the stated $I$. The term in $D'$ is $-n_\nu D'/E[T]$.
(a) As $R\to0^+$, $n(R)\to n_b$ (Proposition~\ref{prop:nb}), $D\to0$ and $D'(0^+)=A_1+E[E_T]=E[T]\bar E$. If the bracket is
positive at $0^+$, then by continuity $n$ increases on some $(0,\delta)$. Since $n(R)\to0$ as $R\to\infty$, $n$ attains a
maximum $n_{\mathrm{fold}}>n_b$, and by the intermediate value theorem every $n\in(n_b,n_{\mathrm{fold}})$ is reached on
both sides of the maximizer. Together with the all-miss state this gives at least three stationary states. For $n>n_b$,
Little's law at $h=0$ and $W=0$ forces $\nu>\nu_b$, so $K_{\mathrm{run}}>M$; by continuity the feedback map is
memory-gated ($\Phi_n\equiv0$) near $h=0$, and the all-miss state is locally stable under relaxation of $h$ at fixed $n$.
(b) A strictly decreasing continuous $n(R)$ is a bijection onto $(0,n_b)$.
\emph{Window opening.} At $R\to0^+$ the formula for $d\nu/dR$ has the sign of $f(0^+)\Delta_S-1$, with
$\Delta_S=(\beta_E+\bar E\rho a)/\bar E$. If it is positive, $\mu=\nu/E[T]$ rises above $\mu_b$ as $R$ leaves 0.
\end{proof}
\noindent The stability of the queue-free states is a further statement. Under relaxation $\dot h=\kappa(\Phi_n(h)-h)$ and
the condition $\partial_n\Phi_n<0$ (checked numerically: $-0.0007$ to $-0.14$ at $n=20$--$32.3$, 300k), a queue-free state
is stable iff $dn/dR<0$ there, because along the curve $n'(R)=f(R)(1-\partial_h\Phi_n)/\partial_n\Phi_n$. That the
registered cells are fold-free is a numerical statement. The ratio $fI/(n_\nu D'/E[T])$ was evaluated on 400 values of $R$
per cell, with 100\% sign agreement against finite differences of $n$
(\fpath{analysis/theory/merged/fold.py}). The identity itself is also checked in magnitude
(\fpath{tests/test_theory_paper.py}).

\begin{proof}[Proof of Proposition~\ref{prop:capfp}]
Under Proposition~\ref{prop:fold}(b) and unimodality, $g(n)=\lambda-\mu(n)$ is positive at 0. It crosses zero downward once
on $[0,n^*]$ (at $n_1$) and upward once on $[n^*,n_b]$ (at $n_2$), and equals $\lambda-\mu_b>0$ on $[n_b,\infty)$. This is
the phase line of \S\ref{sec:fluid}. With $n\ge c$, the capped system is the closed system with $c$ sessions
(Proposition~\ref{prop:cap}), whose stationary state is unique. That state is good iff $c<n_b$. While the gate is
non-empty it drains at $\mu(c)-\lambda$, which is positive iff $n_1<c<n_2$. Once it empties, $N$ relaxes to $n_1<c$ and the
cap stops binding; releasing it leaves $N$ in the basin $[0,n_2)$. With a fold, a cap
$c\in(n_b,n_{\mathrm{fold}})$ engaged in the trap keeps the all-miss state, so $c<n_b$ is also needed.
\end{proof}

\begin{proof}[Proof of Proposition~\ref{prop:trapid}]
If each present session completes one turn per cycle of length $c$, the gap between a session's consecutive turns is $c$.
The churn is $\sum_i(L_{k_i}+d)/c$, so $R_M=M/\text{churn}=Mc/\sum_i(L_{k_i}+d)$, and $c/R_M=\sum_i(L_{k_i}+d)/M$; the cost
model cancels. LRU evicts an idle item before $M$ newer tokens exist, so its eviction age is at most $R_M$: the trap is
self-consistent when the next admission comes later than that.
\end{proof}

\paragraph{Heuristic layers.}
\emph{F1}: at population $n$ the KV demand ratio is $\theta\sim N(1,0.570/n)$, and
$\tilde\mu(n)=E_\theta[\mu_{\mathrm{fluid}}(n;M/\theta)]$.
\emph{F2}: $dX=(\lambda-\mu(X))dt+\sqrt{I_D(\lambda+\mu(X))}\,dW$, reflected at 0, with $I_D=1.567$, the shot-noise
dispersion index by Campbell's theorem. P(unstable) is $1-e^{-H/\mathcal T}$ with $\mathcal T$ the mean first-passage
time from 0 to $n_b$ and $H=3000$\,s.
\emph{Burst}: a burst of $b$ fresh sessions starts the diffusion at
$X_0=D_{\mathrm{live}}^{-1}(D_{\mathrm{live}}(n_1)+4331\,b)$, where 4331 tokens is a fresh cohort's peak expected KV per
session (turn 12). P(trapped) is $q(X_0)+(1-q(X_0))P_{\mathrm{esc}}$, with $q$ the splitting probability between $n_1$ and
$n_b$~\citep{karlin1981second}.
\emph{Rescue}: the gate serves the resumed sessions first. Phase 1 lasts $(n_{\mathrm{on}}-c)/\mu_1$, with $\mu_1$ the capped
rate of resumed sessions: footprint inflated by $1+650(k_0-1)/\Elb$ and one forced miss. Phase 2 drains fresh arrivals at
$\mu(c)-\lambda$. Release comes at the first 10\,s tick after 300\,s with an empty gate.

\paragraph{Assumptions not modelled.} SGLang retraction under memory pressure (a candidate cause of the 1--3 point deficit
in the trapped token rate); prefill queueing (A2a). Adding an M/G/1 prefill wait keeps every curve fold-free and lowers
$\mu^*$ by 0.1--5\%, so it explains at most half of the peak excess. Also not modelled: $\mathrm{max\_running}=256$
(Lemma~\ref{lem:server} needs $M<256E_S\approx2.8$M tokens, which every cell satisfies), and the hold-reset delay of the
release rule.
```

## 3. Figures

| file | content | script | data |
|---|---|---|---|
| `figures/theory/paper_mu_validation.{pdf,png}` | predicted (fluid, F1) vs measured μ(n), sessions and turns-based, for the three measured cells; n_b and λ_miss marked | `analysis/theory/paper/figs.py::fig_mu_validation` | `results/theory/paper/mu_validation.csv` |
| `figures/theory/paper_fixed_points.{pdf,png}` | (a) open-system phase line, 300k at 1.65×: n1 = 10.4, n_u = 31.8, n_b = 32.7, trap; (b) closed feedback map at n = 33.5: exponential law (one fixed point, h = 0) and a two-phase law (h = 0 stable, 0.290 unstable, 0.694 stable); (c) the two closed curves, with the fold band (32.70, 34.18) shaded | `fig_fixed_points` | `results/theory/paper/fixed_points.csv` |
| `figures/theory/paper_scaling.{pdf,png}` | ω against s·z̄ (300k model; A100 measured; H200 frozen prediction at s·z̄ = 13.7 s) and ω against M (model; measured 300k and native; frozen 150k and 600k predictions) | `fig_scaling` | `results/theory/paper/scaling.csv` |

Reproduce with `PYTHONPATH="src;." python -m analysis.theory.paper.figs` (about 1 minute). In panel (a), the measured A100 window is μ*/λ_miss(E0a) and the model's is μ*/μ_b; the two differ by 0.3%. The earlier `merged_validation` and `merged_blind` figures stay as diagnostics.

## 4. BibTeX for new references (verified 2026-10-31)

Every entry below is checked against Crossref (DOI, title, authors, venue, pages) or the arXiv abstract page. Keys already in `paper/refs.bib` are reused unchanged: `yao2026multiturn`, `hong2026misat`, `courtois1975decomposability`, `denning1968thrashing`, `bronson2021metastable`, `alvaro2025formal`, `li2025continuum` and `ao2026service`.

```bibtex
% META (Crossref 10.1109/jsac.2002.801752): the Che approximation
@article{che2002hierarchical,
  author  = {Che, Hao and Tung, Ye and Wang, Zhijun},
  title   = {Hierarchical {Web} Caching Systems: Modeling, Design and Experimental Results},
  journal = {IEEE Journal on Selected Areas in Communications},
  volume  = {20},
  number  = {7},
  pages   = {1305--1314},
  year    = {2002},
  doi     = {10.1109/JSAC.2002.801752},
}

% META (arXiv abs page 1202.3974, v1 17 Feb 2012; ITC 24, Krakow, per the ITC archive copy and later citations)
@misc{fricker2012versatile,
  author       = {Fricker, Christine and Robert, Philippe and Roberts, James},
  title        = {A Versatile and Accurate Approximation for {LRU} Cache Performance},
  year         = {2012},
  howpublished = {24th International Teletraffic Congress (ITC 24); arXiv:1202.3974},
}

% META (Crossref 10.1109/infocom.2014.6848145): Che approximation for renewal (non-IRM) request processes
@inproceedings{martina2014unified,
  author    = {Martina, Valentina and Garetto, Michele and Leonardi, Emilio},
  title     = {A Unified Approach to the Performance Analysis of Caching Systems},
  booktitle = {IEEE INFOCOM 2014 -- IEEE Conference on Computer Communications},
  pages     = {2040--2048},
  year      = {2014},
  doi       = {10.1109/INFOCOM.2014.6848145},
}

% META (Crossref 10.1145/3713082.3730380); content known from the abstract and a lecture summary only
@inproceedings{isaacs2025analyzing,
  author    = {Isaacs, Rebecca and Alvaro, Peter and Majumdar, Rupak and Muniswamy-Reddy, Kiran-Kumar and Salamati, Mahmoud and Soudjani, Sadegh},
  title     = {Analyzing Metastable Failures},
  booktitle = {Proceedings of the Workshop on Hot Topics in Operating Systems (HotOS '25)},
  pages     = {172--178},
  year      = {2025},
  doi       = {10.1145/3713082.3730380},
}

% META (Crossref 10.1109/srds64841.2024.00013); abstract-level
@inproceedings{habibi2024msf,
  author    = {Habibi, Farzad and Lorido-Botran, Tania and Showail, Ahmad and Sturman, Daniel C. and Nawab, Faisal},
  title     = {{MSF-Model}: Queuing-Based Analysis and Prediction of Metastable Failures in Replicated Storage Systems},
  booktitle = {2024 43rd International Symposium on Reliable Distributed Systems (SRDS)},
  pages     = {12--22},
  year      = {2024},
  doi       = {10.1109/SRDS64841.2024.00013},
}

% META (Crossref 10.1145/3772356.3772426); title-level only
@inproceedings{farahbakhsh2025modeling,
  author    = {Farahbakhsh, Ali and Haeberlen, Andreas and Lu, Qingjie and Alvisi, Lorenzo and van Renesse, Robbert and Cohen, Shir},
  title     = {Modeling Metastability},
  booktitle = {Proceedings of the 24th ACM Workshop on Hot Topics in Networks (HotNets '25)},
  pages     = {19--24},
  year      = {2025},
  doi       = {10.1145/3772356.3772426},
}

% FULL for the claim (arXiv abs page: v2 21 Sep 2026, "IISWC 2026"; Section V "Impact of Context Thrashing" read in the
% v2 PDF text): context thrashing under rising agent concurrency (Qwen3.6-27B on H100), prefix-cache hit ~98% -> 16-26%,
% extra prefill slows decode, generation throughput down by up to 66%; measurement only, no model.
@misc{yuan2026agentic,
  author       = {Yuan, Yichao and Nayak, Ankita and Kundu, Souvik and Talati, Nishil},
  title        = {Agentic {AI} Workload Characteristics},
  year         = {2026},
  howpublished = {IEEE International Symposium on Workload Characterization (IISWC 2026); arXiv:2605.26297 (v2, 21 September 2026)},
}

% META (publisher and library catalogues: Academic Press, 1981, ISBN 978-0-12-398650-4); splitting probabilities of
% one-dimensional diffusions (Chapter 15)
@book{karlin1981second,
  author    = {Karlin, Samuel and Taylor, Howard M.},
  title     = {A Second Course in Stochastic Processes},
  publisher = {Academic Press},
  address   = {New York},
  year      = {1981},
  isbn      = {978-0-12-398650-4},
}
```

Notes for the bib audit:
- Fricker et al. has no DOI in Crossref. The ITC 24 proceedings entry exists in the ITC archive (`archive.itc-conference.org/itc24/uploads/media/ITC24S2P4.pdf`).
- For Karlin & Taylor, the chapter number (15, diffusion processes) is from memory and was not checked. The citation in the LaTeX does not depend on it.

## 5. Provenance: every number in the LaTeX above

Shorthand used below:
- **F** = frozen at tag `r13-theory-pred` (commit 997d2c4), file `results/theory/merged/<cell>.json`.
- **V** = `results/theory/merged/validation_table.md` (also frozen).
- **S** = `results/theory/merged/summary.md` (frozen).
- **M[cell]** = the measured files of `analysis/theory/fluid_rigorous/cells.py::PATHS[cell]`:
  - 300k: `results/nova/stageC_1706210x_pulled_20261022-125454` (Stage C), `e0a_1707263x_pulled_20261023-142037` (E0a), `e0b_1708475x_pulled_20261024-150639` (E0b), `e2_170933xx_pulled_20261025-144558` (E2);
  - native: `r7_native_grid_vllm_pulled_20261025-145126`, `e0b_native_1710093x_pulled_20261025-173038`, `e2_native_vllm_burst_pulled_20261026-101256`;
  - vLLM: `stageC_vllm_1716295x_pulled_20261030-153621`, `e0a_vllm_17100940_pulled_20261025-180814`, `e0b_vllm_1716296x_pulled_20261030-172810`, `e2_native_vllm_burst_pulled_20261026-101256`.
- **P** = this commit: `tests/test_theory_paper.py` or `results/theory/paper/*.csv`.

| number in text | value | source | kind |
|---|---|---|---|
| Ē, A_1, E[E_T] | 10,569; 144,960; 11,045 | F a100_300k `all_miss.threshold.E_bar`; `analysis/theory/fluid_rigorous/model.py` Workload (A1, EET) from `configs/agentload_e2_burst.yaml` | derived from workload |
| hit prefill 551 | Δ + 1 | spec/workload (`x_hit`) | structural |
| cost constants a, f0, b, c_p, c_d, B | 9.24 ms, 1.26 ms, 62.6 µs, 2.24 ns, 0.31 ms, 8192 | `calibration/round6_server_log_fit/calibration.yaml` (server-log fit, jobs 17060165, 17062103-05) | input |
| n_b 300k = 4.94 + 27.76 = 32.70 | | F a100_300k `all_miss.threshold.{tool_call_part,pool_part,n_b}` | predicted |
| n_b native 94.86 | | F a100_native `all_miss.n_b` | predicted |
| H200 s = 2.742; n_b 41.3 | 2.742; 41.31 | F h200_300k `window.speed_factor_vs_a100`, `all_miss.n_b`; T3(c) checked in P `test_speed_corollary_T3c` | s fitted to H200 E0a tokens 29,866 (brief); n_b predicted |
| Prop F ratios 0.805 / 0.826 / 0.784 / 0.781 / 0.761 / 0.821 | | F `<cell>.fold_identity.max_ratio`; `tests/test_theory_r13_freeze.py::CELL_MARGINS` | numerical |
| margin 17-24% | 1 - ratio over the six cells | as above | derived |
| Δ_S 595 s | 594.6 | F a100_300k `window.local_condition.Delta_S` | predicted |
| fold example n_fold 34.2, CV 2.5 → 38.2, CV 5 → 44.6; h = 0.69 / 0.29 | 34.18, 38.16, 44.63; 0.694, 0.290 | `tests/test_theory_r13_freeze.py` (freeze), P `test_fold_example_three_states`, `results/theory/paper/fixed_points.csv` | model diagnostic |
| CV ≈ 3.8 SWE-Bench tool times | 3550/925 ms | `paper/sections/related.tex` (Continuum, li2025continuum) | literature |
| C2 range -0.0007 to -0.14 | | mathcheck scratch check13 (reviewer), quoted in `notes/THEORY_r13_merged.md` T6 | numerical, not in committed code |
| registered caps 20 / 64; n_2 ≈ 32 / 90 | n_u 31.8-32.2 (300k), 90.0 (native 4.0×) | registration; F r1/r4 JSON `open_equilibria`; S | protocol / predicted |
| measured gap/R 4-10 trapped, 0.01-0.03 good | 4.14-9.67; 0.010-0.028 | V (E2 rows); M[cells] trap_v2_runs.csv | measured |
| F1 variance 0.570/n; I_D 1.567 | 0.5703; 1.567 | F `closed_curve.annealed.cv2`, `from_empty_edge.I_D` | derived from workload |
| μ* errors, turns-based: F1 +3.6 / +6.3%, fluid +9.9 / +9.0% | | V rows "mu_max turns-based" | validation |
| one session is 3.5% of the 300k pool | 10,569 / 300,000 | derived | derived |
| Table: λ_miss 0.0718/0.0715, 0.0718/0.0718, 0.0670/0.0657 | | F `all_miss.e0a_pop32_lambda_turns`; M[cell] E0a calibration.json `lambda_miss_turns_based` | predicted / measured (vLLM fitted) |
| Table: μ* F1 (fluid) / measured turns-based | 0.2337 (0.2478) / 0.2255; 0.4949 (0.5076) / 0.4655; 0.2353 (0.2490) / 0.2108 | F `closed_curve.{annealed,fluid}.mu_max`; V | predicted / measured |
| Table: peak n, flat top | 24 / 20-24; 69.5 / 64-80; 24 / 20-24 | F `closed_curve.annealed.peak_n`; V "peak n" note | predicted / measured |
| Table: 0.5-hit crossing | 31.5 / 32.2; 93.7 / 93.4; 31.8 / 29.1 | F `closed_curve.fluid.n_half`; V | predicted / measured |
| Table: window F1 / turns | 3.27 / 3.15; 6.89 / 6.48; 3.58 / 3.21 | F `window.annealed_vs_lambda_ref`; V | predicted / measured |
| Table: E0b brackets | | F `from_empty_edge.predicted_bracket`; M[cell] `lambda_cap_bracket.json` | predicted (in-sample choice of criterion) / measured |
| Table: trapped backlog, token ratio, good hit, capped drain | | V E2 rows; measured from M[cell] trap_v2_runs.csv and `analysis/theory/che_endogenous/measured.py` (capped drains, from `paper/derived/e2_*capped_drain.csv`) | predicted / measured |
| H200 window 1.92, n_half 37.3, peak 32.5 with hit 0.67, edge 1.39 | 1.916; 37.32 (fluid); 32.5, 0.674 (F1); 1.392 | F h200_300k; P `test_quoted_numbers_match_frozen_jsons` | blind prediction |
| H200 refutation rules | | `notes/THEORY_r13_scoring.md` | frozen |
| pool sweep: windows 1.87 / 5.47, n_b 18.3 / 61.2, edges 1.09 / 4.53 | 1.872, 5.471; 18.32, 61.17; 1.094, 4.533 | F a100_pool150k, a100_pool600k | blind prediction |
| Llama: M/E_S 27.8, window 3.37, n_b 32.0, edge 2.46 | 27.76; 3.370; 32.02; 2.457 | F llama31_8b_300k | blind prediction (a priori costs) |
| critical burst 59.4 / 53.4 / 46.1; committor 50% 56 / 50 / 42 | | `notes/PREDICTIONS_r13_theory.md` headline (from `fluid_rigorous` Prop. 5 table and F b1_basin_300k) | blind prediction |
| B1 P(trapped) 1.000 / 0.042 | | S B1 table; F b1_basin_300k | blind prediction |
| R1 release 3830 / 4360 s; relapse 0.002 / 0.025; needs 32% / 42%; collapsed 7510 / 9240 s | | S R1 table; F r1_rescue_300k `tests.R1.result.*` | blind prediction |
| R4 release 5040 s; needs 51% | 5040; 0.511 | S R4 table; F r4_rescue_native | blind prediction |
| A2a probe: μ* −0.1 to −5% | | reviewer scratch check3, quoted in `notes/THEORY_r13_merged.md` §7 | numerical, not in committed code |
| max_running 256; 256 E_S ≈ 2.8M | | calibration.yaml; derived | structural |
| burst peak 4331 tokens at turn 12 | | `model.cohort_peak_kv` (workload) | derived |
| Yuan et al.: 98% → 16-26%, up to 66% | | arXiv:2605.26297 v2, Sec. V | literature |

## 6. Suggested related-work and model-text edits (lead's call)

- **related.tex, last sentence of "Position".** Replace "Extending the models of Ao et al. or Yao et al. so that inter-turn gaps depend on load would cover our setting; neither does so." with: "Extending Yao et al.'s model so that the KV held by running requests, and their service time, depend on the hit rate covers our setting; §\ref{sec:fp} does this." The old sentence misdescribes the adopted theory: on partially hitting states the gaps stay exogenous.
- **related.tex, the "Prefix and KV mechanisms" paragraph.** Add Yuan et al. next to CONCUR: "Yuan et al. measure the same collapse ('context thrashing') as agent concurrency rises and note that the extra prefill slows decode~\citep{yuan2026agentic}."
- **model.tex §\ref{sec:theory-curve}.** It says N_lb = M/E_lb ≈ 28.4 and "the peak n* lies below N_lb". The first-principles counterpart is the pool part M/E_S = 27.76 of Eq. (nb). Its E_S = 10,809 is service-weighted, not length-biased. The collapse onset is n_b = 32.7, not N_lb. One sentence linking the two would avoid two near-equal numbers with different definitions.
- **Do not claim:** novelty of an endogenous-gap Che closure in general caching (not searched); finer contrasts with Courtois (abstract only); any H200, Llama, pool, B1 or rescue outcome until the cells report.

## 7. Adversarial novelty check (this pass)

Question: do any recent works already contain the model's claimed contributions? Searches (web, 2026-10-31):
- (a) arXiv 2026 analytical models of multi-turn/agent KV thrashing with fixed points or bistability;
- (b) Che/TTL approximations coupled to a service time that depends on the hit ratio;
- (c) analytical models of agentic serving with tool-call idle KV.

Findings:
1. **Yuan et al., "Agentic AI Workload Characteristics" (IISWC 2026, arXiv:2605.26297). New overlap, now credited.** They measure context thrashing under increasing concurrency and state the decode slow-down mechanism. They give no model, threshold, equilibria or open-system behaviour. Our claim narrows to the quantified loop; the mechanism has been observed before.
2. **Ao et al., "Service-Induced Congestion in Memory-Constrained LLM Serving" (arXiv:2606.15555; `ao2026service`, already cited).** A decode-only dynamical model in which the eviction-free fixed point can be unstable; it abstracts away prefix reuse. **No change is needed.** The related-work text already says this. Our instability comes from losing reusable prefixes, not from eviction of running KV.
3. **TraceLab (`zhu2026tracelab`, already cited).** It gives an analytic decoding fraction and a hit rate as a function of an eviction timeout. Both are exogenous-gap, single-fixed-point quantities. **No overlap** with the feedback results.
4. **Other recent preprints (MORI, adaptive KV retention at human-approval timescales, UNISON).** These are systems, with admission throttling near zero free KV. **No overlap** with the theory: they contain no curve prediction, threshold identity or rescue condition.
5. **Caching theory (Che, Fricker et al., Martina et al., Gast and Van Houdt).** The searched works take request rates as exogenous. We found no LRU characteristic-time model whose hit ratio feeds back through service time into the characteristic time. The search was targeted, not exhaustive, and the LaTeX says so.

**Residual risk.** The classical multiprogramming literature after Courtois (decomposition with load-dependent paging) may contain a fold criterion analogous to Proposition F for page-fault service; we have not read it. Proposition F is new in what it says about dispersed tool times and prefix caching, but the authors should check Courtois (1975) and Brandwajn's equivalence-decomposition models before calling the fold mechanism new in general.

## 8. Caveats that must survive into the paper

1. Every proposition is about the deterministic model. Propositions 1, 2 and 4-6 and the identity of Proposition 3 are proved under the stated assumptions. Fold-freeness of the registered cells, unimodality and C2 are numerical. No limit theorem links the engine to the model.
2. **Assumption MF does not concentrate at these pool sizes.** The validity margin at the peak, in composition standard deviations, is 0.91 (300k), 0.95 (vLLM), 0.01 (150k), −1.08 (H200), 2.5 (native) and 1.9 (600k). This is the likeliest failure mode for the H200 μ* and window: expect them about 4-12% high on the turns-based estimator.
3. **Provenance of the 300k cell.** The cost model's data include the 300k Stage C server logs, so the 300k comparison is out of sample in its target but not in its data source.
4. **Selection was done on the measured cells.** Both choices were made on the three measured cells: model B over model A, and F2 over the level-crossing criterion. F2's bracket matches are in-sample, and most neighbouring F2 variants also land inside these wide brackets.
5. **vLLM is a partial miss.** The cliff comes earlier and steeper than predicted (crossing 29.1 vs 31.8), and the plateau below λ_miss is not reproduced.
6. The trapped token rate is 1-3 points low; retraction is not modelled. The CAPPED drains come out 9-15% fast.
7. **Rescue predictions depend on phase 1.** They need the resumed sessions to run at least at 32% / 42% (R1) or 51% (R4) of their fluid rate. A collapsed phase 1 misses the deadline.
8. **H200 and Llama E2 predictions are at the model's own registration consequence.** Predictions at the cells' registered rates come from the frozen conditional rule.
9. **H200 blindness scope.** n = 16-32 was seen by the H200 operator session and by Akshat, not by the theory authors. n ≥ 40 and the E0b are fully blind.
