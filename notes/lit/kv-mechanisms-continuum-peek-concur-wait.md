**Method note.** I opened the arXiv abs pages for all five papers. The PDFs did not decode, so body text came from the arXiv HTML versions through a summarizing fetch. The numbers below are therefore summarizer-extracted, not read verbatim. Spot-check them before they go into a paper. I did not read the last portions of the WAIT and Service-Induced Congestion HTML (from about char 200k) or the Continuum tail (references only).

## 1. Continuum (Li et al., 2025, arXiv preprint v7) https://arxiv.org/abs/2511.02230
**Implementable spec**
- **What is pinned and when:** At request finish, if the request is not the program's last, its KV blocks are not freed. The simulator should record `pin[program] = now + tau*`. The last request's KV is freed immediately. The tool name is parsed from the function-call response.
- **Choosing tau (Eq. 2):** `tau* = argmax_tau P(tau,f)·(T·eta + PrefillReload(r)) − tau`.
  - Candidates are 0 plus the unique observed durations for tool f.
  - P is the empirical CDF of the gap from request finish to the next arrival of the same program.
  - T is the sliding-window mean queueing delay of evicted requests, initialized to 0.
  - eta = −Corr(k, N−k), where k is the number of requests served so far and N is the program's total number of requests.
  - PrefillReload comes from a quadratic fit of prefill time against context length, or from GPU–CPU bandwidth when offload is on.
- **Cold start:** K = 100.
  - If the total history |S| ≤ K, use T_default, the optimal tau under Exp(1) durations with eta = 1.
  - Else if |S[f]| ≤ K, use the global CDF.
  - Else use the per-tool CDF.
  - The paper's text mixes the symbols M and K, and |S| is not defined precisely.
- **Expiry:** At each scheduling step, a pin is freed if now > expiry and the program has no request waiting. The pin is removed when the follow-up request is scheduled.
- **Pinned memory and admission:** Pinned blocks occupy capacity. The paper says deadlock can occur when pins fill memory. The fix is in prose (Sec. 5.2), not in Algorithm 1. If the head waiting request does not fit, the scheduler unpins victims in order of latest program arrival until it fits, and the victims are re-queued.
- **Priority:** The tuple is (preempted, TTL-pinned before unpinned, program arrival time FCFS). The loop picks the top request and stops if it does not fit, so there is no skip-ahead.
- **Defaults:** There is no global default TTL. Mean tool times are about 0.9 s (SWE-Bench) and 1.9 s (BFCL v4). Experiments use vLLM 0.10.2 with 2048-token chunks and LMCache DRAM offload (100 GB per GPU on A100).

**Claims**
- The paper states no formal proof or regret bound. The cost model assumes the waiting queue is always full enough for the blocking effect to occur.
- The abstract claims over 8x lower average job completion time, empirically.

## 2. PEEK (Xie et al., 2026, arXiv preprint under review, v2) https://arxiv.org/abs/2607.02525
**Implementable spec**
- **Protection is a ranking, not a pin.** The paper describes no lease, TTL, or hard exclusion from eviction.
- **Pending tree:** `pending_count(v)` is the number of waiting prompts through node v. It goes up on arrival and down on admission or completion.
- **Eviction order:** `evict_score(b) = max over ancestors v of pending_count(v)·depth(v)`, and the lowest score is evicted first. Zero-demand blocks go first. On vLLM the hook scans up to 4N free-block entries and prefers a zero-demand victim over the LRU pick.
- **There is no fixed peek window.** The whole waiting queue is re-sorted every cycle, at cost O(C·D + N log N).
- **cLPM key:** (section, −h, −score, −|cluster|, arrival).
  - Section 0 is warm (h > tau).
  - Section 1 is a cold pioneer, whose first theta = 32 tokens are unclaimed this cycle.
  - Section 2 is a cold sibling.
- **Fallback and fairness:**
  - Two lanes are stride-interleaved. Lane A (cLPM) has share alpha = 0.7. Lane B is keyed (section, arrival, −h).
  - The paper states the oldest request advances at least every ⌈1/(1−alpha)⌉ cycles, which is 4 at the default.
  - An optional dynamic-lane controller sets the lane share from an EMA (beta = 0.3) clamped to [0.10, 0.60].
  - The stock SGLang LPM-to-FCFS fallback at queue > 128 is described as an existing exit path.
  - A `has_sharing` guard skips cLPM when no root child has pending_count ≥ 2.

**Claims**
- The theory is complexity only. There is no optimality or starvation proof.
- There is no session-specific or tool-call logic. The one multi-turn workload (W4, a Mooncake trace) is near parity with baselines.
- Gains grow with cache pressure, empirically.

## 3. CONCUR (Chen et al., 2026, arXiv preprint) https://arxiv.org/abs/2601.22705
**Implementable spec**
- **What W counts:** W_t is the cap on concurrently active agents, not requests. Agents over the cap stay pending and issue no requests.
- **Signals:** U_t is KV usage and H_t is cache hit rate.
- **Rule (Eq. 1):**
  - If U < U_low (0.2), then W += 2.
  - If U > U_high (0.5) and H < H_thresh (0.2), then W *= 0.5.
  - Otherwise hold. High U with a healthy hit rate is tolerated.
  - There is no slow-start.
- **Pausing:** Agents pause at generation/tool boundaries, and resume is gated by admission. Paused agents "retain logical KV associations", and the controller restricts new admissions under pressure to protect them. No pinning mechanism is described, and the engine's SGLang LRU is not stated to be modified.
- **Sensitivity:** U_high is robust at about 0.5–0.6, and U_low is sensitive. The paper did not sweep alpha or beta.

**Claims**
- The argument is informal: recompute cost is convex (O(L²)), so a multiplicative cut exits thrashing in O(log N) steps. There is no proof.
- It reports up to 4.09x on Qwen3-32B.
- Continuum appears only in Related Work, with no experimental comparison.

## 4. WAIT (Ao et al., arXiv v4, 2026) https://arxiv.org/abs/2504.11320 and Service-Induced Congestion (Ao et al., 2026) https://arxiv.org/abs/2606.15555
**WAIT model**
- Poisson arrivals per type on a single GPU, with KV growing +1 per decode step under capacity C.
- Iteration time is linear: d0 + d1·Σ.
- Eviction is LIFO with a restart from prefill.

**WAIT results**
- Prop 1: if λ_j·d1(l'+1)(l+l'/2) ≥ 1, any policy has Ω(T) latency.
- Prop 2: fluid throughput upper bound.
- Prop 3: a specified greedy-FCFS-with-LIFO-restart variant has an Ω(1) throughput gap at C = M*.
- Thm 4: WAIT has throughput gap O((ζT)^−1/2), improving to O(1/(ζT)) under strict slack.
- Props 5 and 6: lower bounds for non-predictive policies at C = M*.
- Thm 7: Nested WAIT has gap O((ζT)^−1) with eviction probability ≤ δ, given a log safety buffer.
- vLLM and Sarathi are shown unstable only empirically (Vidur). The words "work-conserving" and "unstable" do not appear in the text I read.
- Prefix caching, multi-turn, tool calls, and KV reuse are absent.

**SIC model**
- Single GPU, decode-only, with deterministic lengths per class.
- Each step runs Execute, Arrive, Evict (least-progressed-first), Admit (greedy one-step feasibility).
- The theory uses saturated backlog; the simulations use Poisson arrivals.

**SIC results**
- Thm 2: the eviction-free fixed point x* = 2M/(l1(2l0+l1+1)) is unstable. The maximal-eviction cycle is asymptotically stable. Lemma 1 gives the worst-case throughput ratio, which approaches 1/2.
- Thm 3: for two classes, instability depends on the gcd of the decode lengths (gcd > 1 is unstable, gcd = 1 is globally stable).
- Prop 4: the minimum stable input length scales like l1,2³.
- The proposed policy is the rate-limited admission cap `a = min(Q, S/Σp(l0+1), x*)`.
- The instability is for the greedy admission baseline. The paper does not claim that all work-conserving policies are unstable.
- Prefix caching is not modeled. Multi-turn sessions and tool calls appear only as motivation.

## Unconfirmed
- **PEEK:**
  - The warm threshold tau has no stated value.
  - The vLLM fallback when every scanned block has demand is unstated.
  - It is unstated whether cLPM runs when the queue exceeds 128.
  - The online "peek" mechanism may have a lookahead I did not see. The portion I read had none.
- **Continuum:**
  - Whether normal engine eviction can reclaim a pinned block before its TTL expires is not stated.
  - Typical tau values are not reported.
  - The pseudocode stores a TTL but compares it as an absolute expiry, which does not match Sec. 5.2.
  - The code (github.com/Hanchenli/vllm-continuum) was not opened.
- **CONCUR:** The control interval, W_0, smoothing, and how U and H are measured are all unstated.
- **WAIT and SIC:**
  - The tail of the WAIT and SIC HTML (about char 200k onward) was unread.
  - The Nested WAIT proofs were not read.
  - A statement that "work-conserving policies are unstable" was not found in either paper.

Sources:
- [Continuum, arXiv 2511.02230](https://arxiv.org/abs/2511.02230)
- [PEEK, arXiv 2607.02525](https://arxiv.org/abs/2607.02525)
- [CONCUR, arXiv 2601.22705](https://arxiv.org/abs/2601.22705)
- [Fluid-Guided Online Scheduling with Memory Constraints (WAIT), arXiv 2504.11320](https://arxiv.org/abs/2504.11320)
- [Service-Induced Congestion in Memory-Constrained LLM Serving, arXiv 2606.15555](https://arxiv.org/abs/2606.15555)