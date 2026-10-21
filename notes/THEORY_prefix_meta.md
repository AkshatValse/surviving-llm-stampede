# Prefix-cache metastability in agent serving: theory sketch (DRAFT)

Status: my sketch, 2026-10-21 overnight. **Not math-checked.** Statements marked (conj.) are conjectures that the simulator is testing. The fluid limits are heuristic: no proofs yet.

## Setup and notation
- **Sessions.** Sessions arrive as Poisson($\lambda$). Session $i$ has $T_i$ turns, iid with mean $\bar T$. Between turns it makes a tool call of length $Z$, iid with mean $\bar z$. Its context before turn $t$ is $L_t=L_0+(t-1)(\Delta+d)$.
- **Work per turn**, in GPU-seconds on one server with unit capacity:
  - miss: $w_m(L_t)$, i.e. prefill of $L_t+\Delta$ tokens plus decode;
  - hit: $w_h$, i.e. prefill of $\Delta$ plus decode.
  - Assume $w_h\ll w_m(L)$ for agent-sized $L$. Continuous batching makes decode cost load-dependent; in the fluid sketch we take the per-turn work at the saturated batch size.
- **Memory.** A KV pool of $M$ tokens. A waiting request does not lock its session's KV. Idle KV (a session in a tool call or in the queue) is evictable.
- **Per-session work**:
  - all-miss: $W_m=\sum_{t\le T}w_m(L_t)$;
  - ideal-hit: $W_h=w_m(L_1)+\sum_{2\le t\le T}w_h$, where the first turn is always cold.
- **Rates**:
  - all-miss capacity: $\lambda_{\rm miss}=1/\mathbb E[W_m]$;
  - hit capacity: $\lambda_{\rm hit}=1/\mathbb E[W_h]$;
  - memory-time capacity: $\lambda_{\rm mem}=M/\mathbb E[\int_{\text{lifetime}}L(s)\,ds]$. In the good state each session's KV occupies memory over its whole lifetime, which is about $\sum_t(\text{service}_t+Z_t)$, because the KV must survive the tool calls.
  - $\lambda_{\rm cap}=\min(\lambda_{\rm hit},\lambda_{\rm mem})$, and the window ratio is $R=\lambda_{\rm cap}/\lambda_{\rm miss}$.

## Claim 1 (FCFS; any eviction rule): positive recurrent iff $\lambda<\lambda_{\rm miss}$
**Sketch.**
- **Sufficiency.** A miss is the worst case for every turn, so if $\lambda\mathbb E[W_m]<1$ the workload is dominated by an all-miss M/G/1-type system, which is stable. A coupling argument should make this precise. Caveat: it needs work-conservation plus the 256-sequence cap. **Check.**
- **Necessity.** Suppose $\lambda\ge\lambda_{\rm miss}$, and condition on a state with $Q$ waiting requests, where $Q\bar L\gg M$.
  - A request that joins the back of an FCFS queue is admitted only after the roughly $Q$ requests ahead of it.
  - Each of those admissions needs memory. While our request waits, more than $M/\min L$ distinct sessions are admitted, and they hold KV at the same time or in sequence. So any eviction rule must evict our session's idle KV before its admission. This holds even for Belady, whose furthest-next-use rule is exactly the back of the queue.
  - So once $Q>Q^\*\approx M/\bar L$, every admission is a miss. The queue then has drift $\lambda\mathbb E[W_m]-1\ge0$, which means null-recurrent or transient behavior from such states.
  - The process reaches such states with positive probability through an arrival burst, so it is not positive recurrent.
  - **Flagged:** making "all-miss above $Q^\*$" rigorous needs care. Partial (radix) prefixes, $\Delta$-tail hits, and the 256-running cap all matter.
- **Consequence.** For $\lambda\in(\lambda_{\rm miss},\lambda_{\rm cap})$ the system is metastable. From empty it sits in a good state where hits are frequent and the queue is $O(1)$. The escape time is the hitting time of level $\sim Q^\*$ by the good-state queue. For a queue whose good-state stationary tail decays geometrically at rate $\rho_h$, that time is $\approx\exp(Q^\*\log(1/\rho_h))$ (conj.). After escape it never recovers unless $\lambda$ drops below $\lambda_{\rm miss}$, which is the hysteresis.

## Claim 2 (work-conserving hit-first / LPM): stable up to about $\lambda_{\rm cap}$ (conj.)
- **Mechanism.** Under LPM, a session returning from a tool with resident KV is served before any cold request, so its idle time is $Z$ plus $O(\text{hit service})$, independent of $Q$.
- Cold requests use only the leftover capacity $1-\lambda\mathbb E[W_h-w_m(L_1)]$, and each one admitted becomes hot.
- Evictions are needed only if the hot set's memory-time exceeds $M$, which is the $\lambda_{\rm mem}$ constraint.
- So the drift of the cold queue is negative whenever $\lambda<\lambda_{\rm hit}$ and the hot set fits, i.e. $\lambda<\lambda_{\rm mem}$, modulo whether evictions are fair.
- **Risk.** If $\lambda_{\rm mem}<\lambda_{\rm hit}$, a work-conserving LPM may still thrash near $\lambda_{\rm mem}$. A cap or WAIT rule (Ao et al.) may then be necessary, and then "ordering suffices" only holds when $\lambda_{\rm hit}<\lambda_{\rm mem}$. The simulator's E0 reports both quantities, so we will see which regime holds.
- **Fairness.** Pure LPM can starve cold sessions in transients. Aging-LPM, which serves any request that has waited longer than $W_{\max}$ FCFS-first, bounds the wait. (conj.) It keeps a stability region close to LPM's when $W_{\max}\gg\bar z$.

## Claim 3 (threshold fallback): any cache-aware order that becomes cache-oblivious when $Q>q$ has the FCFS stability region
- With fallback threshold $q$ and $\lambda\in(\lambda_{\rm miss},\lambda_{\rm cap})$, a burst of $q$ arrivals, which has positive probability per unit time, switches the system to FCFS.
- **Claim:** if $q\bar L\gtrsim M$, then while $Q>q$ the admissions are all-miss by Claim 1's argument, and the queue drifts upward, so the system is transient.
- For SGLang, $q=128$. With agent contexts of 2–10k tokens, $q\bar L\approx0.26$–$1.3$M tokens, which exceeds a typical $M$ of about 300k tokens for an 8B model on an 80 GB GPU.
- **(conj.)** Even when $q\bar L<M$, the switch can still trap the system: under FCFS, waits grow, so idle times exceed the KV lifetime. **Check this regime in the simulator.**
- **Practical point.** The threshold exists because computing prefix matches for a long queue is costly. A per-session O(1) handle to the session's radix node removes the need for the fallback. That is a one-line engineering fix with a large stability consequence.

## What is (probably) new versus prior work (provisional; lit agents ran out of budget)
- **Bronson et al. HotOS'21.** Metastable failures in general, with look-aside caches as the canonical example. It gives no LLM or agent model and no ordering result.
- **Ao, Luo, Simchi-Levi, Wang (2504.11320).** The eviction-only stability region, with WAIT as non-work-conserving admission. We need to read whether they treat ordering by cache state.
- **Ao, Dong, Luo, Simchi-Levi (2606.15555).** An empirical open-arrival threshold, with no sessions or prefix hits.
- **Nie, Si & Zhou (2605.04595).** Memory-time capacity for one-shot requests.
- **CONCUR.** Empirical thrashing and AIMD admission control.
- **Our contribution:**
  1. The FCFS stability region is exactly the all-miss region for multi-turn sessions, for any eviction rule.
  2. Ordering, not admission control, recovers the larger region (when $\lambda_{\rm hit}\le\lambda_{\rm mem}$).
  3. Threshold fallbacks in shipped engines inherit the trap, measured on a real engine.
  4. Escape-time asymptotics, as a rare-event problem.

---
## Revision 2026-10-21 ~02:00, after the REFRAME pilot. Claims 2 and 3 above are superseded.

**What the pilot showed.**
- In the congested state, running requests reserve about 288k of the 300k tokens. Idle KV for sessions in tool calls gets evicted to admit misses. *This diagnostic is not yet stored in a results directory.*
- LPM therefore cannot help: by the time a session returns from its tool, its KV is already gone.
- The decisive variable is **admission**, not ordering.

**Claim 1′ (work-conserving admission).** Call an admission rule work-conserving if it admits a waiting request whenever memory can be freed by evicting idle KV.
- Suppose $\lambda>\lambda_{\rm miss}$ and the queue holds misses whose total reservations exceed $M$.
- Then each admission evicts idle KV, and every returning session is cold.
- So the congested state is absorbing, whatever the ordering or eviction rule. This holds once running reservations saturate $M$.
- The good state exists when $\lambda\,\mathbb E[\text{lifetime}]\,E_{lb}[L]<M$ and $\lambda<\lambda_{\rm hit}$. In that regime no eviction of in-tool KV is needed.
- Round 3 tests this as H1/P1/P2.

**Claim 2′ (working-set bound).** Define the length-biased (time-weighted) resident context
$$E_{lb}[L]=\frac{\mathbb E\big[\sum_t L_t(s_t+Z_t)\big]}{\mathbb E\big[\sum_t(s_t+Z_t)\big]} .$$
It exceeds the "mid-session" context because long sessions stay longer and hold more KV. This is why $N^\*=45$ failed and $28\approx M/E_{lb}$ worked.
- A session cap $N\le M/E_{lb}[L]$ keeps the expected resident KV at or below $M$. Follow-up turns then hit, and the stable region becomes $\lambda<\min(\lambda_{\rm hit},N/\mathbb E[\text{lifetime}])$.
- **Open:** the $E_{lb}$ bound holds in expectation, not pathwise. Fluctuations of resident KV around $N\cdot E_{lb}$ need a safety margin. A CLT-style margin $M/(E_{lb}+z\,\mathrm{sd}/\sqrt N)$ could explain why caps of 24 and below are robust.

**Claim 3′ (the cliff is LRU on cyclic access; conjecture).**
- Agent sessions re-reference their KV once per tool cycle. Across $N$ sessions with similar tool times, the access pattern is roughly cyclic.
- Classical caching result: LRU on a cyclic reference string whose working set $W$ exceeds the cache $C$ gives **zero hits**. MRU and random eviction degrade gracefully, with hit rates on the order of $C/W$.
- So above $N_{lb}$, LRU collapses hit rate abruptly, which is the cliff at 28→32. LRU is the default in both SGLang (`radix_eviction_policy="lru"`) and vLLM (free-queue LRU).
- **Prediction (round 4, not yet run):**
  - Replacing LRU with MRU-of-idle or random eviction turns the cap cliff into gradual degradation.
  - It might also enlarge the basin of the good state for work-conserving engines, since bursts could be survivable.
  - It cannot remove the absorbing congested state of Claim 1′, because once running reservations saturate $M$ no idle KV survives.
- Related prior work: "When Fancy Eviction Fails" (arXiv 2609.28870) finds LRU hard to beat on production traces. Those traces are presumably not overloaded or cyclic. **Check its regime.**

**Escape-time angle (Akshat's rare-event background).**
- Below the burst threshold, collapse needs a rare excursion of the queue or of resident KV.
- The mean time to collapse should grow roughly exponentially in the system size $k$. Round 3 tests this as H3.
- The natural estimator is multilevel splitting on queue length or resident-KV level, giving a large-deviations rate for the escape.
