# Independent check of D1, D5, P (own code from raw CSVs)

Universe: all 152 `agentload_e2_*` run dirs under results/nova (sessions.csv, requests.csv, config_effective.yaml, metrics.csv, tool_calls.csv). Hit = cached/prompt > 0.5 over status=ok turns. STUCK = hit fraction over turns completing in [5700,8700) < 0.2. Run end taken as 8700 s. Scripts: build.py, d1.py, d5.py, e0b.py, pool.py, final.py (same folder).
Per-run CSVs: D1_stuck_runs.csv, D5_trapped_runs.csv, D5_e0b_from_empty_runs.csv, P_pool_share_stuck_runs.csv (all stuck runs; engine-specific).

Stuck counts I get: 57 (SGLang FCFS 39 = r0 6, r1 6, b100 3, b60 3, b50 1, H200-600k 6, Llama 6, native 6, shed-t600 2; vLLM 12; stock LPM 5; toolslow-d30 1).

## D1 - CORRECTED (15 of 16, not 16; one number off)
The 16 runs: H200 600k burst 6, b50 1, b60 3, b100 3, shed-t600 2, toolslow-d30 seed2 1. All 16 have every trigger session completed (0 present at end). Ranges reproduce: time between last trigger session leaving and run end 558-6246 s (shed-t600 558 and 708; b60 seed2 6246), post-leave turns 727-15,453.
- Exactly 15 satisfy "no trigger session left AND zero hits afterwards" (all but toolslow-d30 seed 2, run 20261031-224211).
- toolslow-d30 seed 2: 87 trigger sessions (slowed tool call), last left at 4069 s (4631 s before end); 5937 later turns, 4 hits (completion t = 4547, 4696, 4702, 4784 s, cached ratios 0.79-0.97), hit fraction 0.00067, not 0.000. Brief transient, then zero hits.
- A100 registered 200-session BURST, 24 runs (SGLang r1 300k 6, native 6, vLLM 300k (e2_vllm_1716612x) 6, Llama 6): burst sessions still present at end 3-30 (r1 3-9, native 8-30, vLLM 4-13, Llama 4-10): CONFIRMED. The "at most 5.8% of the population" I cannot reproduce: max is 15.0% of burst sessions (30/200, native), 4.07% of sessions present at end (Llama seed2 9/221), 1.08% of all sessions in the run, and burst share of turns in [5700,8700) at most 6.07%. 5.8% matches none; denominator unknown. Note a second vLLM set (e2_native_vllm_burst, 6 more runs, 5-10 present) also exists; the 24 as described are not ambiguous on the 3-30 range either way.
- Not in the list but stuck: r0 grid runs and stock-LPM/vLLM runs all have 3-30 trigger sessions still present, so "trigger left" holds only for the 15/16 above plus none of the A100 200-bursts.

## D5 - CONFIRMED in substance, hours slightly CORRECTED
Window rule implemented as stated (100 s bins by t_complete, turn>1, pooled 3-bin rolling windows, step 100 s; onset = first window with start >= 1200 and hit <= 0.2; escape = later window fully before cut-off with hit >= 0.5).
- FCFS trapped cohort: 50 runs = 49 burst (r0 6, r1 6, native 6, vLLM 12, Llama 6, H200-600k 6, b100 3, b60 3, b50 1) + 1 toolslow-d30 seed 2. That equals the stuck FCFS burst runs minus the 2 shed-t600 runs (SHED truncates at stop start 1800 s, trapped span only 600 s; rescue runs span 600-700 s; neither is in the 50). 0 escapes; highest post-onset window hit anywhere = 0.164 (the toolslow run).
- Trapped time: onset = window START: 371,300 s = 103.1 h; onset = window END: 356,300 s = 99.0 h. Claim's 376,300 s (104.5 h) not reproduced under either (about 1.4% above my start-based figure). Shortest span: 6400 s (toolslow, onset window starting 2300) under start convention, 6100 under end; claim ~6500. Burst runs span 7200-7500 s (start).
- Bound 1 - 0.05^(1/50) = 5.82% is arithmetically right for 50 runs / 0 escapes; the window is ~6400 s (not 6500) under the start convention. Definitional: this is a bound per run on the run's observed length with window-level detection.
- From-empty E0b-type (agentload_e0_cap, 58 runs, 3000 s): 16 collapse (onset window start >= 0/300/600/900 all give 16), 1 escaped: sglang-fcfs-r1-p150k (150k pool), rate_mult 1.30, seed 0, run 20261031-093158 (onset 1200 s, window start 2200 s hit 0.52 at its maximum 0.66; last-1000 s hit 0.37). CONFIRMED 16 / 1.
- Stock-LPM: 9 trapped runs (lpm-r0 + lpm-r1, of 12), 4 escaped (lpm-r1 seed0 20261025-051901, lpm-r1 seed1 20261025-081311, lpm-r0 seed1 20261025-081740, lpm-r1 seed2 20261025-101756). The claim's "10 trapped, 5 escaped" holds only if the lpminf (LPM without the 128 fallback) run is added: sglang-lpminf seed1 20261031-014355 (escape window start 7200 s, hit 0.508; 1 of 3 lpminf runs). CORRECTED: stock LPM 9 / 4; LPM-family incl. lpminf 10 / 5.
- Caveat: several of the LPM escapes are barely above 0.5 (0.504-0.512).

## P - CORRECTED
Measurable directly: metrics.csv scrapes every 5 s. SGLang: `sglang:kv_used_tokens` (= `full_token_usage` x pool; pool = `max_total_num_tokens`) is the KV not available and not evictable, i.e. held by running/locked requests; `kv_evictable_tokens` is the idle cache; `num_running_reqs`. vLLM: `vllm:kv_cache_usage_perc`, `num_requests_running`. I averaged snapshots in [5700,8700) per run (n=600 per run).
Running-KV share of pool, stuck runs (hit fraction 0.000):
- SGLang A100 r1 300k (e2_170933xx), 6 runs: 62.8-78.8%. This is exactly the quoted 63-79%.
- BASIN b60 3 runs: 55.7-75.0% (claim 56-75% OK). b100: 55.9-77.2%, b50: 77.4%.
- Other registered sets do not fit 63-79%: Llama-3.1 300k 76.6-82.4%; H200 600k 55.2-83.4%; SGLang native pool (955,757 tokens) 84.8-94.2%; vLLM 91.9-93.6% (vLLM usage_perc may count differently); shed-t600 79.4-82.6%; toolslow-d30 75.4%.
- Across all 34 non-native SGLang FCFS stuck runs: 55.2-83.4%. So the claim is correct for the A100 SGLang 300k set (and b60), but not as a statement about all registered traps. Pool share varies a lot run to run (55%-83%) with queue lengths 70-850.
- Caveat: gauge snapshots; kv_used also includes locked prefix nodes and in-flight prefill allocation, not only decode KV. Median differs from mean by up to ~5 points (see run_share_med).
