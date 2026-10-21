**Provenance.** I read the tagged raw files on raw.githubusercontent.com through WebFetch, which runs pages through a summarizing model. I did not see line-numbered source and have no verbatim blocks. Everything below is extractor-reported unless marked "inferred". Treat it as a spec to spot-check before publishing.

## vLLM v0.32.0 (tag v0.32.0)
Files: `vllm/v1/core/sched/scheduler.py`, `kv_cache_manager.py`, `block_pool.py`, `single_type_kv_cache_manager.py`, `kv_cache_utils.py`, `request_queue.py`, `vllm/config/scheduler.py`.

**Config defaults**
- `max_num_seqs`=128, `max_num_batched_tokens`=2048 (config default), chunked prefill on, policy fcfs.
- `watermark`=0.0, `scheduler_reserve_full_isl`=True, `max_num_active_seqs`=None.

**Per-step order:** the running loop runs first, then the waiting loop.

**Running loop (decode and in-progress prefill chunks)**
- Requests are scheduled in `self.running` list order.
- `n = num_tokens_with_spec + placeholders − num_computed_tokens` (1 for plain decode), capped by the token budget and `max_model_len`.
- `allocate_slots(req, n, num_lookahead_tokens)` allocates blocks up to `cdiv(computed + n + lookahead, block_size)` minus blocks already held. Lookahead is 0 without speculative decoding.
- No watermark and no full-fit check apply here.
- On `None`, a victim is chosen. Default FCFS takes `self.running.pop()`, the last entry in the running list. PRIORITY takes `max(priority, arrival_time)`.
- `_preempt_request` frees the victim's blocks and sets `PREEMPTED` and `num_computed_tokens=0`. It then calls `waiting.prepend_request`, which is `appendleft` for FCFS.
- The scheduler retries `allocate_slots` for the same request. If the victim is the request itself, the loop breaks. Later running requests are then unscheduled this step.
- The waiting loop runs only if `not preempted_reqs`, so any preemption blocks admission for that step.

**Waiting loop**
- Stop at `len(running) >= max_num_active_reqs` or when the token budget is exhausted.
- The FCFS head is considered first. Prefix lookup happens when `num_computed_tokens == 0`, with hit length capped at `num_tokens−1`.
- `num_new_tokens` = tokens past the hit, clamped to the token budget (one chunk).
- `allocate_slots(..., full_sequence_must_fit=True, has_scheduled_reqs=bool(running))`. It returns `None` if `blocks(min(request.num_tokens, max_model_len)) + evictable hit blocks + watermark_blocks > get_num_free_blocks()`.
  - The sequence size is the whole prompt plus any previously generated tokens. `max_tokens` is never reserved.
  - Free blocks include cached blocks with `ref_cnt==0`.
  - `watermark_blocks = int(watermark·num_blocks)`, applied only when status is WAITING or PREEMPTED and `has_scheduled_reqs` is true.
- On `None`, the loop breaks. There is no preemption and no skipping, so the head of line blocks.
- On success, only blocks for the hit plus this chunk are allocated.
- `reserved_blocks` is 0 on the normal path (nonzero only with async KV load). So the full-ISL check does not account for remaining chunks of already-admitted prefills. That implies over-admission is possible (inferred).

**Fate of preempted blocks**
- `free` releases blocks in reverse order, tail first. In `block_pool.free_blocks`, blocks that reach `ref_cnt` 0 with a hash go to the tail of the free queue via `append_n`. Unhashed blocks (partial last block) go to the head via `prepend_n`.
- Hashes persist until `get_new_blocks` pops the block from the head (`popleft_n`), which evicts its hash. Eviction order is LRU by free time.
- Preempted KV therefore stays cached until reused.
- Hashes cover generated tokens too, via `append_output_token_ids` → `update_block_hashes`. A readmitted request re-hits the longest surviving contiguous prefix of prompt plus output.
- `touch` removes a hit block from the free queue. The partial tail block is always recomputed.
- `cache_blocks` runs after each allocation, up to `min(computed + n, num_tokens)`. Blocks are cached as computed, not at finish.

## SGLang v0.5.22 (tag v0.5.22)
Files: `python/sglang/srt/managers/schedule_policy.py`, `scheduler.py`, `schedule_batch.py`, `scheduler_components/new_token_ratio_tracker.py`, `mem_cache/prefill_budget.py`, `mem_cache/common.py`, `radix_cache.py`, `environ.py`.

**Defaults:** `schedule_conservativeness`=1.0, `SGLANG_INIT_NEW_TOKEN_RATIO`=0.7, `MIN_NEW_TOKEN_RATIO_FACTOR`=0.14, `NEW_TOKEN_RATIO_DECAY_STEPS`=600, `RETRACT_DECODE_STEPS`=20, `CLIP_MAX_NEW_TOKENS_ESTIMATION`=4096, `retraction_policy`="length", `max_prefill_tokens`=16384.

**Ratio tracker**
- `init = min(0.7·cons, 1)`, `min = init·0.14` (0.098 at defaults), `decay = (init−min)/600`.
- `decay_step()` is called on decode steps without retraction: `current = max(current − decay, min)`.
- `reset()` sets `current = init` when fully idle.
- After a retraction, `current = min(1, (Σ len(output_ids) + 20·n) / (Σ max_new_tokens + 1))`. The sums run over the kept requests only, because the estimate is computed after `filter_batch`.

**Admission (`PrefillAdder`)**
- `pool = allocator.available_size() + tree.evictable_size()`.
- `total_offset` starts at `num_mixed_decode_tokens` plus Σ over running requests of `min(max_new − len(out), 4096) × ratio`. The ratio is 1.0 for `ignore_eos`.
- Candidate cost: `total_tokens = (len(fill_ids) − prefix_len) + min(max(max_new − len(out), 0), 4096) + per_req_overhead`.
- Admit iff `total_tokens < pool − total_offset` (strict).
- On commit, `total_offset += ceil_page(extend) + page_size + extra + max_new`. The new request's `max_new` is not scaled by the ratio.
- `NO_TOKEN` breaks the loop. The matched prefix node is locked, which excludes it from evictable.

**Decode OOM**
- `check_decode_mem` fails when one new page per request at a page boundary cannot be allocated (allocator capacity check includes eviction). `update_running_batch` then calls `retract_decode`.
- Victim order: sort key `(len(output_ids), −len(origin_input_ids))` descending, then `pop()` from the end. Victims are fewest-output first, ties broken by longest prompt. The "priority" policy prepends priority to the key.
- Loop: `first_iter or not check_decode_mem`. It keeps at least one request ("Always keep at least one request"). If the last request still doesn't fit, it is aborted with status 500.
- Per victim: `release_kv_cache(req, tree, checkpoint=False)`.
  - This frees KV beyond `cache_protected_len`, unlocks the node, and frees the pool slot.
  - Then `evict_from_tree_cache(remaining·20 tokens)` runs.
  - Then `reset_for_retract` sets `prefix_len=0`, `last_node=None`, `already_computed=0`. `output_ids` are kept.
- The victim is re-queued at the tail of `waiting_queue` via `_add_request_to_queue(is_retracted=True)`. The next policy sort may reorder it.

**Radix fate**
- The prompt is checkpointed into the tree after prefill (`checkpoint_kv_cache`, non-chunked unfinished requests). Decode does not insert unfinished requests.
- On retraction the prompt prefix stays in the tree, unlocked and evictable. The generated-token KV is freed and not inserted. The code comment says "don't insert into the tree because we need the space instantly".
- Re-hit is on the prompt only, and outputs are recomputed (inferred). The 20·n eviction can evict the victim's own prompt nodes.

## Unconfirmed
- No verbatim source or line numbers; every item above is extractor-mediated.
- vLLM:
  - Hybrid, SWA and mamba groups were not traced.
  - Async-scheduling `deferred_frees` timing was not traced.
  - The over-admission claim is inferred.
  - The default `block_size` is unchecked.
- SGLang:
  - The `check_decode_capacity` body and the allocator's eviction arithmetic were not seen.
  - The `checkpoint_kv_cache` body was not seen, so whether chunked-prefill requests insert their prompt is unconfirmed.
  - The default radix eviction policy is unseen (LRU assumed).
  - `beam_retraction_order` and the `add_one_req` chunk-splitting details were not read.
  - The `page_size` default is unseen.

Sources:
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/sched/scheduler.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/kv_cache_manager.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/block_pool.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/single_type_kv_cache_manager.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/kv_cache_utils.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/v1/core/sched/request_queue.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/vllm/config/scheduler.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/managers/schedule_policy.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/managers/scheduler.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/managers/schedule_batch.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/managers/scheduler_components/new_token_ratio_tracker.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/mem_cache/prefill_budget.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/mem_cache/common.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/mem_cache/radix_cache.py
- https://raw.githubusercontent.com/sgl-project/sglang/v0.5.22/python/sglang/srt/environ.py