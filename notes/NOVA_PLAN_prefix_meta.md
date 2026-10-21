# Real-engine validation plan: prefix-cache metastability (DRAFT, nothing run on Nova)

Status (2026-10-21): **Stage 1 only.** The harness (`src/agentload/`, `analysis/`, `slurm/`, `configs/agentload_*.yaml`) is implemented and tested against a local mock server. **Nothing was submitted to Nova, no Nova host was contacted, no engine or model was installed or run, no network was used.** Every engine flag, env var and metric name below is from memory of SGLang/vLLM and is marked UNVERIFIED until the Stage-0 test job. Needs Akshat's approval before any `sbatch` (project rule: ask first, run a short test job first).

## 1. What this tests, and what the simulator already says

Simulator (branch `pilot/prefix-meta`, commit 8e71275; results summarized in `notes/LOG.md`, 2026-10-21 entry, REFRAME): λ_miss = 0.0474 sessions/s, λ_cap = 0.1156, R = λ_cap/λ_miss = 2.44. A 200-session burst at 2×λ_miss left FCFS, LPM-128 and aging-LPM at hit rate 0.000 over [t_b+10k, t_b+25k] in 5/5 seeds; pure LPM 0.198; a length-biased session cap 0.896. Bursts of 25 recovered, bursts of ≥100 trapped every work-conserving policy. Sim reading: **admission, not ordering, drives the trap**, so "LPM-128 inherits the trap" was vacuous there (LPM was trapped too). Sim limits (LOG.md): whole-session KV, no partial radix prefixes, no waiting-prefix refresh, no lazy block eviction.

The real-engine question: does the sim's mechanism (burst → queue → idle KV evicted before the next turn is admitted → all-miss → no recovery) appear on a shipped engine at all? Cells:

| Cell | Engine / policy | Waiting-prefix refresh | Why |
|---|---|---|---|
| A | SGLang v0.5.22 `--schedule-policy fcfs` | on (shipped default) / off | the kill-criterion cell |
| B | SGLang `lpm` (stock, falls back to FCFS above 128 waiting) | on / off | the fallback claim |
| C | SGLang `lpm` with `WAITING_QUEUE_PREFIX_MATCH_MAX` huge (one-line patch, see §6; **not applied**) | n/a (never falls back) | cache-aware ordering without the fallback |
| D | vLLM v0.32.0 `--enable-prefix-caching` (FCFS only) | n/a | second engine |

Refresh facts are from `notes/lit/engine-sources-prefix-cache.md` (raw-file reads by a small model; no line numbers, no SHAs): `SGLANG_ENABLE_WAITING_PREFIX_REFRESH` (EnvBool, default true) bumps LRU recency of the first 128 waiting requests every 32 passes, only for non-cache-aware active policies (FCFS and the LPM fallback). It is a recency bump, not a pin.

Predictions to compare against (from the sim, **not** pre-registered for the real engine; the lead should decide whether to pre-register): A traps at some λ ∈ (1.2, 2)×λ_miss if the mechanism transfers; B ≈ A; C is the only cell where ordering could matter, and the sim predicts it does not rescue the system either; refresh off ≤ refresh on in hit rate if the bump helps.

## 2. Hardware, model, engines

- One GPU per job: `--account=f2026.coms.6250.02 --partition=instruction --qos=instruction --gres=gpu:a100:1 --cpus-per-task=16 --mem=128G --time=04:00:00`. The default account is the 6720 course, so every script passes the 6250 account explicitly (a test asserts no "6720" in any directive). Per-user QoS cap is 11 GPUs shared with the 6720 project; this plan uses 1 GPU per job, jobs run serially unless Akshat says otherwise.
- The SLURM label `a100` has been seen on nodes whose `nvidia-smi` says "A100 80GB PCIe" (CLAUDE.md). Irrelevant for 1 GPU, but every job prints `nvidia-smi` and `nvidia-smi topo -m` and stores the GPU name in `meta.json`.
- Model: Qwen/Qwen2.5-7B-Instruct (Apache-2.0, ungated), weights to `HF_HOME` on `/work` or `/ptmp` (placeholder until the quota check). `slurm/download_model.sbatch` is a CPU-only draft; it assumes compute nodes can reach huggingface.co (UNVERIFIED).
- Engines: SGLang v0.5.22 (`python -m sglang.launch_server`), vLLM v0.32.0 (`vllm serve`), each in its own env (vLLM pins its torch; `notes/NOVA_ENV_PLAN.md`). **Env plan gap:** the generator env needs `aiohttp` (and `huggingface_hub` for the download job); neither is in the `micromamba create` line of `NOVA_ENV_PLAN.md`.
- Pinned to the sim: `--max-running-requests 256` / `--max-num-seqs 256`; chunk 8192 (`--chunked-prefill-size 8192` / `--max-num-batched-tokens 8192`).

### KV pool: the sim's M is 300k tokens; the real pool is ~3× larger
Qwen2.5-7B KV per token = 2 (K,V) × 28 layers × 4 KV heads × 128 dim × 2 B = 57,344 B (architecture numbers from memory of the HF config; verify in Stage 0). On an 80 GB card at 0.9 utilisation, minus ~15.2 GB weights and a few GB of activations/graphs, that is roughly 1.0M tokens (my arithmetic, not a measurement). The sim used M = 300k. To make the real runs comparable and to keep the metastability reachable with a 200-session burst, the scripts cap the pool at `KV_TOKENS=300000` (`--max-total-tokens` for SGLang; `--num-gpu-blocks-override KV_TOKENS/16` for vLLM, assuming 16-token blocks). Stage 0 must confirm the cap is honored (server log). A native-pool replication is a possible follow-up, not budgeted.

### Context length
Max prompt = L0 + 59(Δ+d) = 2000 + 59·650 = 40,350 tokens (the plan-stats output records `max_prompt_tokens`), above Qwen2.5-7B-Instruct's default 32,768. The scripts launch with `CONTEXT_LEN=49152` plus the engines' long-context override env vars (`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN`, `VLLM_ALLOW_LONG_MAX_MODEL_LEN`; names UNVERIFIED). Past 32k the model runs without YaRN; outputs are garbage but ignored (`ignore_eos`, fixed length), and we measure systems behavior only. Alternative if the override fails: `max_turns` 45 (context ≤ 32k), which changes E[T] from 14.76 to ≈14.3 (formula in `effective_mean_turns`) and departs from the sim.

## 3. Harness (what exists)

| Path | Role |
|---|---|
| `src/agentload/workload.py` | Seeded plan: Poisson arrivals, optional ramp (thinning), burst (N within W at t_b), T ~ min(Geom(1/15), 60), Z ~ Exp(5 s), synthetic content. Session specs and text depend only on `(seed, origin, idx)` (common random numbers). |
| `src/agentload/client.py` | Open-loop aiohttp generator, `/v1/completions`, non-streaming, `max_tokens=d`, `ignore_eos`. Per-request log, `sessions.csv`, `plan.csv`, `meta.json` (git commit + dirty captured at start, seeds, versions, hostname, hardware, start/end, outcome). Safety aborts at `max_inflight` / `max_errors`. Closed-population mode for λ_miss. |
| `src/agentload/poller.py` | `/metrics` scrape every 5 s (prefix filter `vllm:`/`sglang:`, `_bucket` dropped), plus client in-flight and active sessions. Saves the first and last raw scrape. |
| `src/agentload/mock_server.py` | aiohttp mock with per-session LRU prefix cache, FIFO slots, `cached_tokens` in vLLM-usage or SGLang-meta_info form, vLLM- or SGLang-style metrics. Binds 127.0.0.1. Tests only. |
| `python -m agentload {run,plan,probe}` | `probe` sends two identical requests and prints the raw JSON plus the metric names: the first Stage-0 action. |
| `analysis/` | `windows.py` (per-1000 s windows), `hysteresis.py` (trap / recovery / stability / escape / kill rule, §5), `summarize.py` (CLI `windows|burst|miss|stable`; every call writes a new timestamped dir; `stable` also writes `lambda_cap_bracket.json`), `plan_budget.py` (§7). |
| `slurm/` | `sglang_job.sbatch`, `vllm_job.sbatch`, `download_model.sbatch` (drafts), `common.sh` (modes `smoke|miss|cap|burst`, banner, health wait, flush, post-analysis), `engine_*.sh`, `local_smoke.sh` (runs the same job code against the mock on a laptop). |
| `configs/agentload_*.yaml` | `mock`, `mock_server`, `e0_miss`, `e0_cap`, `e2_burst`, `analysis`, `plan_budget`. Research question is the first key of each. |

Workload fidelity to the sim: L0 = 2000, Δ = 550, d = 100, geometric mean 15 (cap 60), Exp(5 s) tool time, burst 200 in 60 s. A test checks the prompt at turn t is exactly L0 + (t−1)(Δ+d) tokens and that each prompt extends the previous prompt plus its output.

Known fidelity gaps (all flagged, none hidden):
1. **Output feedback.** In token mode the next prompt appends the model's actual output only if the server returns token ids (`choices.0.token_ids`, or the paths in `server.output_ids_paths`; vLLM may need `request_token_ids: true`, UNVERIFIED). Otherwise it appends synthetic ids (`output_ids_source=synthetic` in every row), so a "hit" covers the previous prompt but not its d output tokens: the follow-up miss tail is Δ+d = 650, not Δ = 550 (tested on the mock). The probe shows which case applies. Text mode (`workload.prompt_mode: text`) is the alternative; it appends the returned text but cannot control token counts exactly (no offline tokenizer).
2. **Hit definition.** The sim's hit = whole session KV resident. Here a turn counts as a hit if `cached_tokens / prompt_tokens > 0.5` (reported next to the token-weighted rate). A missing `cached_tokens` is treated as 0 only if some other request in the run reports it (vLLM may omit the field when 0; UNVERIFIED).
3. **Window attribution.** The sim attributes hits to admission time; the client sees completion time (default) or send time. They differ by the service time (seconds vs 1000 s windows).
4. **Queue.** Engine waiting-count metric if present (names UNVERIFIED, candidates in `configs/agentload_analysis.yaml`), else client in-flight count (includes running requests, so it is an upper bound on the waiting queue; `queue_source` column says which).
5. **First byte.** Streaming is off, so `t_headers` ≈ completion, not TTFT.

## 4. Experiments

### Stage 0: test job (≈ 0.8 GPU-h per engine, §7; needs approval)
`MODE=smoke` in `slurm/sglang_job.sbatch` / `slurm/vllm_job.sbatch`. Per engine: `check_engine_flags` (greps `--help` for every flag the scripts use; aborts before launch on a miss), launch, health, `probe`, a ~30 min closed-population run with the cache on. Decide from the logs: (a) flags/env vars exist; (b) `cached_tokens` is reported and where; (c) token ids returned? (d) metric names (`metrics_first.txt`); (e) 40k context accepted; (f) KV cap honored; (g) client `prompt_tokens` equals server `prompt_tokens` in token mode; (h) cache-flush endpoint works with no requests running; (i) real startup time and inter-run gap (replace `startup_h`, `gap_s` in the budget config); (j) GPU name and topology. Edit `slurm/engine_*.sh` and `configs/agentload_analysis.yaml` accordingly.

### E0a: λ_miss (cache disabled in the engine)
`MODE=miss`, SGLang `--disable-radix-cache`, vLLM `--no-enable-prefix-caching`. Closed population 32 (sim: 60, insensitive across 30/60/120), 900 s warmup + 1800 s measured, 3 seeds, plus one population-64 check (analysed separately, not averaged in). Output `calibration.json` with `lambda_miss` (sessions/s, the sim's headline) and `lambda_miss_turns_based` (turns/s ÷ E[T]); rates in later configs use `lambda_miss_turns_based` (lower variance for short runs). Deviation D2: sim used 5 seeds × 100,000 s.

### E0b: λ_cap from empty (SGLang `lpm`, cache on)
`MODE=cap`: open loop at multiples of λ_miss, e.g. 1.0, 1.4, 1.8, 2.2, 2.6, 3.0 then a refinement round, one seed per point, 3000 s each, cache flushed and queue drained between runs (`flush_cache` logs success or failure to `job_events.log`; STRICT_FLUSH aborts the job if it fails, because a non-empty cache voids "from empty"). Stability rule = sim's: final queue < 50, fitted queue rise over the last min(5000, run/2) s ≤ 10, not aborted. Like the sim's, this is a finite-horizon lifetime criterion; 3000 s cannot see slow escapes.

**Gate 1.** R = λ_cap/λ_miss. Sim kill rule: R < 1.5 ⇒ no metastable window ⇒ stop. The E2 rate multiples must lie inside (1.2, min(2, 0.9·R)) so the good state is stable before the burst: if 0.9·R < 1.9 (R < 2.11) the planned {1.3, 1.6, 1.9} must shrink accordingly.

### E2: burst test
`MODE=burst`. Warm-up to t_b = 1200 s, 200 sessions within 60 s, run to 8700 s. Rate multiples: **kill test** (cell A, refresh on) λ ∈ {1.3, 1.6, 1.9}×λ_miss × seeds {0,1,2}; **grid** (spec range) λ ∈ {1.6, 2.0}× for cells A(refresh off), B(on/off), C, D, plus A(on) at 2.0. Between runs: cancel, drain, flush. Each run: classify with `analysis.summarize burst`.

### Kill criterion (spec) and how it is computed
"No hysteresis: the burst does not trap FCFS in ≥ 2/3 of runs at any λ ∈ (1.2, 2)×λ_miss ⇒ the sim's mechanism does not transfer." Computed per (cell, λ) as: runs with `is_trap` (sim criterion, or `trapped_aborted`) **and** `good_before` over runs; ≥ 2/3 with ≥ 3 runs. `kill_verdict.json` reports a strict version (needs `good_before`, i.e. a true good→bad switch) and a loose one (any trap), per FCFS cell, and `kill_strict = not any FCFS cell meets`. Open interpretation (O1): "FCFS" = every FCFS cell (A-on, A-off, D); the alternative is A-on alone.

Interpretation table for the report (no result exists yet):

| Outcome | Reading |
|---|---|
| A-on traps ≥ 2/3 at some λ | mechanism transfers to SGLang FCFS; proceed to the grid |
| A-on never traps, A-off does | the shipped refresh is protective; transfer holds only without it |
| No FCFS cell traps | kill: the sim's mechanism does not transfer (or the short protocol is too short, see D1) |
| B, C recover while A traps | ordering matters on the real engine, contradicting the sim |
| B, C trap like A | consistent with the sim's admission-not-ordering reading |

## 5. Analysis definitions (match the sim; deviations marked)

Windows of 1000 s, complete windows only. Ported from `prefixmeta`: `trapped` = longest run of consecutive post-burst windows with hit rate < 0.2 lasts ≥ `trap_min_s`; `hit_eval` over [t_b + `hit_eval_from_s`, end]; `recovered` = `hit_eval` > 0.8 and tail-queue mean < 20 (tail = last min(5000, run/2) s); stable-from-empty; ramp escape (queue > 128) and re-entry (5 bins < 20). Additions: `good_before` (pre-burst hit > 0.5 and queue < 20); `trapped_aborted` (client aborted for overload and the last 3 post-burst windows all < 0.2); verdicts `recovered | trapped | trapped_aborted | indeterminate | no_burst`. The analysis defaults are the sim's (`trap_min_s` = `hit_eval_from_s` = 10000); the job scripts pass the short-protocol values (3000 / 4500).

## 6. Deviations and open issues (for the lead)

- **D1: E2 timing.** Sim: 5000 s warm-up + 25,000 s after the burst (30,000 s = 8.3 h; trap needs 10,000 s of hit < 0.2). The 4 h job limit in the spec cannot hold that. The draft uses t_b = 1200 s, 7500 s after (8700 s per run, one run per job), `trap_min_s` = 3000, `hit_eval_from_s` = 4500. **Risk:** draining a 200-session burst from the good state takes thousands of seconds even when the system does recover, so 3 consecutive low windows can be a slow drain rather than a trap, and the short protocol cannot tell them apart by hit rate alone. `burst_runs.csv` therefore carries `tail_queue_slope_per_window` (fitted queue change per window over the tail; clearly negative = still draining). Every `trapped` run under the short protocol must be checked against it and its queue trace before it counts toward the 2/3 rule (not automated). A literal-protocol alternative needs `--time` ≈ 8.5-9 h (allowed by the partition's 2-day max, but not what the spec says); its cost is in §7. Decision needed.
- **D2: λ_miss** from short runs and the turns-based estimator (sim: 100,000 s, 5 seeds).
- **D3: KV pool** capped at 300k tokens to match the sim (native ≈ 1M).
- **D4: context** > 32,768 needs the long-context override (UNVERIFIED), or `max_turns` 45.
- **O1:** which cells count as "FCFS" for the kill rule (above).
- **O2:** λ points: spec says "1.6–2×" for E2 and "(1.2, 2)" for the kill rule; the draft uses {1.3, 1.6, 1.9} for the kill test and {1.6, 2.0} for the grid. 2.0 itself is outside the open interval.
- **O3:** LPM patch (cell C). Not applied. In `python/sglang/srt/managers/schedule_policy.py` (path from the engine-sources note, no line number), change `WAITING_QUEUE_PREFIX_MATCH_MAX = 128` to a huge value (e.g. `10**9`). To be done in a separate editable install (`ENV_SGLANG_PATCHED`) so the stock cells stay stock. Whether prefix matching over thousands of waiting requests is too slow to serve is itself a finding.
- **O4:** the `a100` GRES may land on different A100 variants; record per run (done in `meta.json`).
- **O5:** engine defaults I did not pin: HiCache off by default (per the engine-sources note), `radix_eviction_policy` lru. Confirm in the server log.
- **O6:** the vLLM FCFS cell cannot be varied (no ordering knob), only compared.
- **O7:** `/flush_cache` (SGLang) and `/reset_prefix_cache` (vLLM, may need `VLLM_SERVER_DEV_MODE`) are from memory; no flush = no "from empty".
- **O8:** the per-request client abort at 4000 in-flight requests. In the trapped regime the queue can reach thousands; a run that hits the cap is recorded as aborted, not as a failed experiment.

## 7. GPU-hour estimate (plan arithmetic, not a measurement)

Source: `analysis/plan_budget.py` on `configs/agentload_plan_budget.yaml`; recorded in `results/agentload_plan_budget/20261021-021036` (`gpu_hours_by_stage.csv`, `gpu_hours_totals.json`, `gpu_hours_by_stage_alt_literal_e2.csv`).

Per stage: jobs = ⌈n_runs / runs_per_job⌉; job wall = startup + runs_per_job·run_s/3600 + (runs_per_job−1)·gap/3600 + teardown, with startup = 0.25 h, gap = 180 s, teardown = 0.05 h (**guesses**, replaced by Stage-0 timings). Worked example, E0a (1 job, 4 runs of 2700 s): 0.25 + 4·0.75 + 3·0.05 + 0.05 = 3.45 h. E2 (1 run of 8700 s = 2.417 h per job): 0.25 + 2.417 + 0 + 0.05 = 2.717 h.

| Stage | Runs | Jobs | GPU-h |
|---|---|---|---|
| S0_smoke_sglang | 1 × 1800 s | 1 | 0.80 |
| S0_smoke_vllm | 1 × 1800 s | 1 | 0.80 |
| E0a_miss_sglang | 4 × 2700 s | 1 | 3.45 |
| E0a_miss_vllm | 4 × 2700 s | 1 | 3.45 |
| E0b_cap_sglang_lpm | 9 × 3000 s | 3 | 8.70 |
| E2a_kill_sglang_fcfs | 9 × 8700 s | 9 | 24.45 |
| E2b_sglang_fcfs_r0 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_fcfs_r1_2x | 3 × 8700 s | 3 | 8.15 |
| E2b_sglang_lpm_r1 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_lpm_r0 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_lpm_inf | 6 × 8700 s | 6 | 16.30 |
| E2b_vllm_fcfs | 6 × 8700 s | 6 | 16.30 |
| **Total** | | 49 | **131.30** |

Gates: gate 0 smoke 1.60; gate 1 calibration 15.60; gate 2 kill test 24.45; full grid 89.65; total 131.30 GPU-h. The E2 stages are 87% of the total, which is why the kill test (gate 2) runs before the grid. Not included: CPU-only env build, model download, re-runs after failures, and the native-pool replication. For the literal timing (28,000 s per run: 3000 s warm-up + 25,000 s after the burst, job limit 9 h) the E2 stages cost 339.3 (total 356.5) GPU-h in total.

Load per E2 run, sized with the **simulator's** λ_miss = 0.0474 sessions/s (`results/prefix_meta_e0/20261021-005706/e0_summary.json` in the main checkout; the real λ_miss is unknown until E0a): at 1.6× and seed 0 the plan has 914 sessions (200 burst), 13,533 turns and 141,076,650 prompt tokens if every turn missed; max prompt 40,350 tokens (`results/agentload_e2_burst_planstats/20261021-021037/plan_stats.json`). About 1.6 requests/s average, so the client side is light; the in-flight cap (4000) matters only in the trapped regime.

## 8. Run locally (laptop, mock server; this is what was tested)

```
/opt/anaconda3/bin/python -m pytest                       # full suite
/opt/anaconda3/bin/python experiments/agentload_record_tests.py   # same, recorded under results/agentload_tests/<ts>
PYTHONPATH=src python -m agentload.mock_server --config configs/agentload_mock_server.yaml --port 18080 &
PYTHONPATH=src python -m agentload run --config configs/agentload_mock.yaml
PYTHONPATH=src:. python -m analysis.summarize windows --run-dirs results/agentload_mock/<ts> --set windows.window_s=4
ENV_GEN=/opt/anaconda3 slurm/local_smoke.sh burst         # job-script glue against the mock
```

Recorded at commit c37374d on a clean tree: tests in `results/agentload_tests/20261021-021100` (116 passed, 0 failed, 0 skipped; `junit.xml`, `pytest_stdout.txt`, `meta.json`); a mock-server demo run in `results/agentload_mock_demo/20261021-021039` with its analyses in `results/agentload_mock_demo_analysis/20261021-021058`, `..._burst/20261021-021059`, `..._stable/20261021-021059`. These show the file layout only; mock numbers say nothing about SGLang or vLLM.
