# D2 independent check: Lu et al. SLO goodput on committed E2 runs

Own code: gp.py, run.py, run2.py (this folder). Per-run output: per_run_primary.csv (primary reference, all burst/capped/rescue runs); all_runs_sensitivity.csv (every reference variant).

## Definitions
- Sessions: origin==base only. Burst and NOBURST pair by `idx` (sids differ; base arrivals and n_turns identical, asserted for all 30 pairs).
- Good session: status completed, all n_turns requests ok, slowdown = (t_end - arrival_s)/ref <= 4. ITL condition OMITTED (no per-token ITL), so goodput is an upper bound and loss a lower bound.
- Goodput of a window = good sessions arriving in the window (per hour scaling cancels in the ratio). Loss = 1 - good(arm)/good(same-seed NOBURST).
- Windows: W1 = arrivals in [1260,4860) (hour after burst ends; alt [1200,4800) reported); WJ = [5700,8400).
- Reference (per session) = plan tool_time_total_s + sum over turns of L0(turn). L0(turn) = a + b*new_suffix_tokens + c*completion_tokens, least squares fitted per engine/hardware family on requests of that family's NOBURST runs (all seeds, both rates) sent at t<600 s with sched_delay<0.05 s (lightest load, warm cache; 4.0k-16k requests per family). new_suffix = prompt_k - (prompt_{k-1}+completion_{k-1}) (turn 1: full prompt), so the reference does not use observed cached_tokens (no load leakage). Fitted per-token prefill ~1.4e-4 s, decode ~1.4e-2 s/token (H200 6.7e-3 s). The OLS line is a mean, so NOBURST median slowdown = 1.00 (p5 0.95, p95 1.10) by construction.
- Sensitivity: p10 (line shifted to 10th percentile residual), and reference scaled x0.5, x2, x3.
- Run set: 30 BURST runs = sglang300k (e2_170933xx, 1.35/1.65), native pool (2.5/4.0), vLLM (e2_vllm_1716612x, 1.35/1.65; the 2026-10-25 vllm-fcfs burst runs in e2_native_vllm have no NOBURST pair and were excluded), H200 600k (1.5/2.0), Llama-3.1-8B (1.35/1.65), 3 seeds each. CAPPED: 30 runs (same cells). Rescue: 15 runs (sglang300k 1.35/1.65 cap engaged 1800 s; native 4.0 engaged 2100 s). No rescue runs for the other families.

## Verdicts (primary reference, OLS x1)
1. BURST, base arrivals in hour after burst lose 99.4-100%: **CORRECTED to 99.2-100%** (min 99.18%: H200 1.5x seed 2, 9 good of 1092; next lowest 99.70%). 26 of 30 runs have exactly 0 good sessions, i.e. 100%. With p10 reference 99.3-100%; with the shifted window [1200,4800) 98.2-100%; with a x0.5 stricter reference 100% (W1 window) / 99.5-100%. Substance holds; the stated lower bound of 99.4 is slightly too high under the median-based reference.
2. BURST, WJ [5700,8400): 100% in all 30 runs: **CONFIRMED** (0 good sessions in every burst run; holds for all references up to x2; at x3 99.8-100%). Caveat: the nonzero NOBURST denominator is 202-1109 sessions.
3. CAPPED WJ loss within 0-2%: **CONFIRMED** (0.00-1.74%; max sglang300k 1.65 seed 2). With p10 0-1.7%.
4. Rescue WJ loss within 0-2%: **CONFIRMED** (-0.3% to +0.9%; one run is 0.3% better than NOBURST).
5. CAPPED first-hour cost 5-57%: **CORRECTED to 4.2-55.7%** (native 2.5 seed 1 = 4.2% low end; llama 1.65 seed 2 = 55.7% high end). With p10 4.5-57.0% (matches claim); depends on reference tightness. Range by family: native 4-14%, H200 6-15%, sglang300k/vLLM/Llama 26-56%.
6. Rescue first-hour cost 46-97%: **CORRECTED to 45.4-94.8%** (primary), 45.7-96.8% (p10). Native rescue 92-95% (primary); sglang300k 45-76%. Claim is within reference-choice noise, but "97" needs the tighter reference.
7. Lu et al. about 88% from one run: they report ~88% over the following hour; not verifiable here beyond their text (different model/stack, ITL included). Our comparable figure is 99.2-100% under their slowdown<=4; only a very lenient reference (x3 of unloaded) gives 70-99.9%, so our loss exceeds theirs under any reasonable reference. Direction agrees with their claim.

## Sensitivity (W1 loss, WJ loss; min-max over runs)
| ref | BURST W1 | BURST WJ | CAPPED W1 | CAPPED WJ | RESCUE W1 | RESCUE WJ |
|---|---|---|---|---|---|---|
| x0.5 | 100% | 100% | 8.5-69.4% | -0.1-3.2% | 57.5-100% | -0.9-2.0% |
| OLS x1 (primary) | 99.2-100% | 100% | 4.2-55.7% | 0-1.7% | 45.4-94.8% | -0.3-0.9% |
| p10 | 99.3-100% | 100% | 4.5-57.0% | 0-1.7% | 45.7-96.8% | -0.3-1.1% |
| x2 | 90.5-100% | 100% | 2.3-41.0% | 0-1.5% | 31.2-70.3% | 0-0.6% |
| x3 | 70.2-99.9% | 99.8-100% | 1.4-29.6% | 0-1.2% | 23.1-54.9% | 0-0.5% |
Claim ranges for burst WJ and for CAPPED/rescue WJ are robust to the reference; first-hour CAPPED/rescue percentages move materially (reference x2 cuts them by about a quarter to a third), so quote them as reference-dependent.

## Explanation of discrepancy (read after own numbers)
Other agent's d2_goodput.py (data-A) uses a tighter reference: per-turn minimum latency of NOBURST cache-hit calls (plus a q05 variant) with a fixed 100-token decode and 2000+650(k-1) prompt shape; ours is a token-based mean. Min-based references are smaller, so slowdown is larger, which pushes loss up slightly at the margins (e.g. rescue up to 97%, burst bound 99.4). Windows, base-only pairing, and slowdown<=4 match. All qualitative conclusions agree.
