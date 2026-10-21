# Engine-source and literature check (2026-10-21)

Code facts were read from raw files at each tag via WebFetch. The extraction was done by a small model, so there are no verified line numbers and no commit SHAs. Items I couldn't confirm are listed at the end.

## 1. SGLang, tag v0.5.22
- **Tag:** v0.5.22 is "Latest", dated 19 Oct; the page shows no year ([releases](https://github.com/sgl-project/sglang/releases)).
- **Fallback constant:** In [schedule_policy.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/managers/schedule_policy.py), `WAITING_QUEUE_PREFIX_MATCH_MAX = 128`. The comment says it "bounds per-round prefix work on the waiting queue."
- **What happens above 128:** `_determine_active_policy` checks the configured policy. If it is LPM or HRRN and `len(waiting_queue) > 128`, it returns `CacheAgnosticPolicy.FCFS`. Prefix matching and sorting are skipped, so the queue stays in arrival order.
- **Defaults** from [fields/schedule.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/arg_groups/fields/schedule.py) and [fields/memory.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/arg_groups/fields/memory.py):

| Setting | Default at v0.5.22 |
|---|---|
| `schedule_policy` | `"fcfs"`, so the 128 fallback only applies if LPM or HRRN is selected explicitly |
| `enable_hierarchical_cache` (HiCache) | `False`; `hicache_hook.py` only reads the flag and never sets it |
| `disable_radix_cache` | `False`, so radix cache is on |
| `radix_eviction_policy` | `"lru"` |
| `max_prefill_tokens` | 16384 |

- **`chunked_prefill_size`:** The field default is `None`, and [memory_hook.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/arg_groups/memory_hook.py) resolves it by GPU memory. 60 to under 90 GB (A100-80GB, H100) gives 8192, 90 to under 160 GB (H200) gives 8192, and 160 GB or more gives 16384.
- **Do waiting requests lock their prefix?** No.
  - Matching in `calc_priority` does not lock.
  - `add_one_req` wraps selection in a temporary `_lock_node`, released on exit.
  - The persistent lock `req.lock = self.tree_cache.lock(req.last_node)` is taken in `_commit_prefill_admission`, i.e. at admission.
  - In [radix_cache.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/mem_cache/radix_cache.py), only nodes with `lock_ref > 0` are protected from eviction.
  - So a waiting request's matched prefix can be evicted before admission.
- **Partial mitigation present at this tag:** `_touch_waiting_prefixes` bumps LRU recency for the first 128 waiting requests every 32 scheduling passes.
  - It is gated by `SGLANG_ENABLE_WAITING_PREFIX_REFRESH = EnvBool(True)` ([environ.py](https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/environ.py)).
  - It runs only for non-cache-aware active policies, which includes the FCFS fallback, and only when the tree cache does not report fast match.
  - It is a recency bump, not a pin.
  - `base_prefix_cache.py` returns `False` for `supports_fast_match_prefix` by default. Whether `RadixCache` overrides it is unconfirmed.
  - Which release introduced the refresh is unconfirmed.

## 2. vLLM v0.32.0 (released 18 Oct, per [releases](https://github.com/vllm-project/vllm/releases))
- **Default policy:** `policy: SchedulerPolicy = "fcfs"`, with `Literal["fcfs","priority"]` ([config/scheduler.py](https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/config/scheduler.py)).
- **Queue classes:** [request_queue.py](https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/sched/request_queue.py) has only `FCFSRequestQueue` and `PriorityRequestQueue`. No prefix-cache-aware ordering was found.
- **Waiting-request blocks:**
  - `get_computed_blocks` in [kv_cache_manager.py](https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/kv_cache_manager.py) is lookup-only and takes no reference.
  - Blocks are attached in `allocate_slots`.
  - In [block_pool.py](https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/block_pool.py), a block at `ref_cnt == 0` sits in the free queue, with hashed blocks appended at the tail (LRU-like). It is lazily evicted when `get_new_blocks` reallocates it.
  - So a waiting request's cached blocks can be evicted before admission. The lookup is redone each time the request is reached in the waiting loop (per scheduler.py summary).

## 3. CONCUR ([PMLR](https://proceedings.mlr.press/v306/chen26fs.html), ICML 2026; arXiv [2601.22705](https://arxiv.org/abs/2601.22705))
- **Source of details:** The PMLR PDF was unreadable, so I used the arXiv v1 HTML.
- **Engine:** SGLang. Baselines are SGLang, SGLang with a fixed request-level cap, and SGLang with HiCache (§5.1). Hardware is H100-80GB.
- **Schedule policy:** Not stated in the text I saw. The baseline is described only as "request-level batching with LRU-based KV cache eviction."
- **Agent counts:**
  - Qwen3-32B: batch 256 at TP 8/4/2, plus a batch-16 TP=16 row.
  - DeepSeek-V3: 16, 32 and 40.
  - Static caps: 30, 32, 64 and 128.
- **Threshold:** No explicit threshold, and no ">128" requirement. Hit rate on DeepSeek-V3 (TP=8) falls from 77.72% at batch 32 to 35.41% at 40 (Table 2, per the summary). The paper calls the effect "middle-phase" thrashing, tied to time and accumulated state.

## 4. Prior work on metastability, hysteresis and thrashing
I found no paper using "metastable", "hysteresis" or "bistable" for prefix-cache serving.
- **PEEK** ([2607.02525](https://arxiv.org/abs/2607.02525), 2026), closest. It names "scheduling-induced thrashing" in stock SGLang LPM+LRU and vLLM FCFS+LRU. It notes LPM falls back to FCFS above 128 queued requests, and it protects cache blocks that queued requests will need. The tested engines are SGLang 0.5.9 and vLLM 0.19.1. Its framing is empirical, with hit rates of 30.8 to 65.8% for the SGLang baseline. Oscillation is mentioned only as EMA damping, and feedback loops and hysteresis are not mentioned.
- **XPerf** ([2608.20370](https://arxiv.org/abs/2608.20370)). On vLLM v0.19.0, hit rate drops past a request-rate threshold and plateaus, which it calls "prefix-cache thrashing". There is no hysteresis analysis.
- **CacheWise** ([2606.16824](https://arxiv.org/abs/2606.16824)) combines prefix-aware scheduling and reuse-aware eviction in vLLM for coding agents. **ThunderAgent** ([2602.13692](https://arxiv.org/abs/2602.13692)) is a program-aware scheduler targeting KV hit rate. **When Fancy Eviction Fails** ([2609.28870](https://arxiv.org/abs/2609.28870)) evaluates 14 eviction policies on production traces and finds LRU hard to beat. None frames the problem dynamically.
- **Service-Induced Congestion** ([2606.15555](https://arxiv.org/abs/2606.15555), Ao et al., v3 dated 20 Oct 2026). It gives a formal dynamical-system instability result: an unstable eviction-free equilibrium and limit cycles, with up to 50% throughput loss. It models KV growth during decode and says nothing in the abstract about prefix caching.
- **Queueing and fluid-stability papers:** [2605.04595](https://arxiv.org/abs/2605.04595) (Nie et al.) and [2504.11320](https://arxiv.org/abs/2504.11320) (Ao et al., WAIT policies, Vidur simulator). Neither involves prefix caching. [2604.11001](https://arxiv.org/abs/2604.11001) (flow-controlled scheduling) also does not mention prefix caching.
- **Forward citations via Semantic Scholar:** 2606.15555 has one (2604.26968, unopened), 2605.04595 has four, and 2504.11320 has 25. I scanned titles only. None of the titles indicates prefix-cache metastability.
- **SGLang paper** ([2312.07104](https://arxiv.org/abs/2312.07104), NeurIPS 2024, PDF p. 4-6, §3). LPM is longest-shared-prefix-first, equivalent to DFS order, with an optimality theorem (Theorem 3.1). The paper says "can lead to starvation" and leaves fair scheduling to future work. Footnote 2 says unpredictable output lengths break the proof's assumptions. Running requests refcount their radix nodes, and eviction is LRU on leaves.

## Unconfirmed
- Line numbers, and commit SHAs for both tags.
- Whether `RadixCache` overrides `supports_fast_match_prefix`.
- Which SGLang release added the waiting-prefix refresh.
- CONCUR's schedule policy, its final PMLR text versus arXiv v1, and the ICML "PACE" poster's relation to CONCUR.
- Full forward-citation coverage (Semantic Scholar only), and the 2604.26968 abstract.
- vLLM scheduler lines past character 100000.

## Verdict: NARROW
Empirical thrashing, scheduling-induced thrashing from the LPM-to-FCFS fallback, and eviction of queued prefixes are already covered by PEEK, XPerf, CONCUR and CacheWise. Formal dynamical-instability analysis exists only for KV growth without prefix reuse. The open sliver is a dynamical model of the prefix-cache feedback loop (eviction, then miss, then more prefill, then more eviction), with measured bistability or hysteresis and tested admission thresholds. Any experiment should also run v0.5.22 with the waiting-prefix refresh both on and off.

Queries run: metastable LLM serving prefix cache; KV cache thrashing hysteresis agents; prefix cache aware scheduling stability region bistability; metastable failure admission control hit-rate collapse; hysteresis bistable radix eviction; LPM starvation waiting queue; and a citation search for 2606.15555.