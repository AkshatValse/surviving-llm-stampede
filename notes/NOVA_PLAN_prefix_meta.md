# Real-engine validation plan: prefix-cache metastability (DRAFT, nothing run on Nova)

Status (2026-10-21, revision 2: referee-requested kill-test redesign): the harness (`src/agentload/`, `analysis/`, `slurm/`, `configs/agentload_*.yaml`) is implemented and tested against a local mock server, now including **Stage C (closed-population mu(n)), the three paired E2 arms with a client-side session cap, the throughput-based trap criterion (`kill_verdict_v2.json`) and a pre-registration template**. **Nothing was submitted to Nova, no Nova host was contacted, no engine or model was installed or run, no network was used.** Every engine flag, env var and metric name below is from memory of SGLang/vLLM and is marked UNVERIFIED until the Stage-0 test job. Needs Akshat's approval before any `sbatch` (project rule: ask first, run a short test job first).

**New stage order: S0 smoke → C closed μ(n) → E0a λ_miss → (E0b cross-check) → PRE-REGISTER (commit the filled `configs/agentload_prereg_template.yaml`) → E2 paired arms → native-pool replicate → grid.** Total GPU-hours: **217.10** (§7; was 131.30 before the redesign).

**Required items** (referee, `notes/REFEREE_prefix_meta.md`, "Kill-test design changes"; each is enforced or at least flagged by the scripts as noted):
1. **Server token ids preferred over synthetic feedback: REQUIRED.** Every job except the Stage-0 smoke must pin `OUTPUT_FEEDBACK`; `server` is the required setting. `synthetic` is allowed only if the Stage-0 probe shows the engine cannot return output ids (`PROBE_SUMMARY.output_ids_present=false`); it is a documented deviation (D5), the job log prints a warning, and the analysis guard `output_source_differs` flags (error severity; `--strict-guards` makes it fatal) runs with different sources in one comparison.
2. **At least one λ on the native KV pool: REQUIRED.** `KV_TOKENS=native` drops the 300k-token cap (`--max-total-tokens` / `--num-gpu-blocks-override` omitted), the default engine label gets `-native` (a user-set label must contain `native`; the analysis groups cells by label, so pools are never mixed). The native pool needs its own μ(n) and `n_cap` to pre-register its λ (budgeted as an ASSUMPTION, §7).
3. **Measure the real curve first (Stage C) and pre-register the trap/recovery boundaries from it** (§4).
4. **Paired arms with common random numbers** for every kill-test (λ, seed): BURST, NOBURST, CAPPED (§4).
5. **Throughput-based trap criterion**, fixed before the runs (§5).

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

Predictions to compare against (from the sim; the kill-test boundaries are now pre-registered from the MEASURED real curve, §4, instead of the simulator's λ multiples): A traps at some λ inside the measured window (μ(300), max μ(n)) if the mechanism transfers; B ≈ A; C is the only cell where ordering could matter, and the sim predicts it does not rescue the system either; refresh off ≤ refresh on in hit rate if the bump helps.

## 2. Hardware, model, engines

- One GPU per job: `--account=f2026.coms.6250.02 --partition=instruction --qos=instruction --gres=gpu:a100:1 --cpus-per-task=16 --mem=128G --time=04:00:00`. The default account is the 6720 course, so every script passes the 6250 account explicitly (a test asserts no "6720" in any directive). Per-user QoS cap is 11 GPUs shared with the 6720 project; this plan uses 1 GPU per job, jobs run serially unless Akshat says otherwise.
- The SLURM label `a100` has been seen on nodes whose `nvidia-smi` says "A100 80GB PCIe" (CLAUDE.md). Irrelevant for 1 GPU, but every job prints `nvidia-smi` and `nvidia-smi topo -m` and stores the GPU name in `meta.json`.
- Model: Qwen/Qwen2.5-7B-Instruct (Apache-2.0, ungated), weights to `HF_HOME` on `/work` or `/ptmp` (placeholder until the quota check). `slurm/download_model.sbatch` is a CPU-only draft; it assumes compute nodes can reach huggingface.co (UNVERIFIED).
- Engines: SGLang v0.5.22 (`python -m sglang.launch_server`), vLLM v0.32.0 (`vllm serve`), each in its own env (vLLM pins its torch; `notes/NOVA_ENV_PLAN.md`). **Env plan gap:** the generator env needs `aiohttp` (and `huggingface_hub` for the download job); neither is in the `micromamba create` line of `NOVA_ENV_PLAN.md`.
- Pinned to the sim: `--max-running-requests 256` / `--max-num-seqs 256`; chunk 8192 (`--chunked-prefill-size 8192` / `--max-num-batched-tokens 8192`).

### KV pool: the sim's M is 300k tokens; the real pool is ~3× larger
Qwen2.5-7B KV per token = 2 (K,V) × 28 layers × 4 KV heads × 128 dim × 2 B = 57,344 B (architecture numbers from memory of the HF config; verify in Stage 0). On an 80 GB card at 0.9 utilisation, minus ~15.2 GB weights and a few GB of activations/graphs, that is roughly 1.0M tokens (my arithmetic, not a measurement). The sim used M = 300k. To make the real runs comparable and to keep the metastability reachable with a 200-session burst, the scripts cap the pool at `KV_TOKENS=300000` (`--max-total-tokens` for SGLang; `--num-gpu-blocks-override KV_TOKENS/16` for vLLM, assuming 16-token blocks). Stage 0 must confirm the cap is honored (server log). **A native-pool replicate (`KV_TOKENS=native`, one λ, paired arms) is a REQUIRED item** and is budgeted in §7: a ~3× larger pool shifts the knee n* and the window, so the 300k-token window and `n_cap` do not transfer, and the native pool gets its own Stage-C curve.

### Context length
Max prompt = L0 + 59(Δ+d) = 2000 + 59·650 = 40,350 tokens (the plan-stats output records `max_prompt_tokens`), above Qwen2.5-7B-Instruct's default 32,768. The scripts launch with `CONTEXT_LEN=49152` plus the engines' long-context override env vars (`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN`, `VLLM_ALLOW_LONG_MAX_MODEL_LEN`; names UNVERIFIED). Past 32k the model runs without YaRN; outputs are garbage but ignored (`ignore_eos`, fixed length), and we measure systems behavior only. Alternative if the override fails: `max_turns` 45 (context ≤ 32k), which changes E[T] from 14.76 to ≈14.3 (formula in `effective_mean_turns`) and departs from the sim.

## 3. Harness (what exists)

| Path | Role |
|---|---|
| `src/agentload/workload.py` | Seeded plan: Poisson arrivals, optional ramp (thinning), burst (N within W at t_b), T ~ min(Geom(1/15), 60), Z ~ Exp(5 s), synthetic content. Session specs and text depend only on `(seed, origin, idx)` (common random numbers). |
| `src/agentload/client.py` | Open-loop aiohttp generator, `/v1/completions`, non-streaming, `max_tokens=d`, `ignore_eos`. Per-request log, `sessions.csv`, `plan.csv`, `meta.json` (git commit + dirty captured at start, seeds, versions, hostname, hardware, start/end, outcome). Safety aborts at `max_inflight` / `max_errors`. Closed-population mode for λ_miss. |
| `src/agentload/gate.py` | Client-side FIFO session gate (`gate.n_cap`): at most N sessions admitted (= active until the session ends, tool sleeps included); later arrivals queue between arrival and first request, freed slots are handed to the queue head, cancellation-safe. `sessions.csv` logs `t_admit`, `gate_wait_s`, `gate_censored`; `meta.json` `outcome.gate` summarises (max active/waiting, waits); the metrics log has `agentload:gated_sessions` and `agentload:sessions_in_system`. |
| `src/agentload/poller.py` | `/metrics` scrape every 5 s (prefix filter `vllm:`/`sglang:`, `_bucket` dropped), plus client in-flight and active sessions. Saves the first and last raw scrape. |
| `src/agentload/mock_server.py` | aiohttp mock with per-session LRU prefix cache, FIFO slots, `cached_tokens` in vLLM-usage or SGLang-meta_info form, vLLM- or SGLang-style metrics. Binds 127.0.0.1. Tests only. |
| `python -m agentload {run,plan,probe}` | `probe` sends two identical requests and prints the raw JSON plus the metric names: the first Stage-0 action. |
| `analysis/` | `windows.py` (per-1000 s windows), `hysteresis.py` (the old HIT-RATE trap / recovery / stability / escape / kill rule, now SECONDARY, §5), `throughput.py` (completion rates, backlog, hit fractions over an interval), `closed.py` (Stage C: μ(n), argmax = `n_cap`), `trap_v2.py` (throughput criterion, pairing check, PASS rule), `prereg.py` (fill / validate / provenance of the pre-registration file), `summarize.py` (CLI `windows|burst|burst2|closed|miss|stable`; every call writes a new timestamped dir; `closed` writes `mu_curve.json`, `burst2` writes `kill_verdict_v2.json`, `stable` also writes `lambda_cap_bracket.json`), `plan_budget.py` (§7, now with the arithmetic spelled out). |
| `slurm/` | `sglang_job.sbatch`, `vllm_job.sbatch`, `download_model.sbatch` (drafts), `common.sh` (modes `smoke|miss|closed|cap|burst`; `burst` runs the paired arms `ARMS`, banner, health wait, flush, post-analysis), `engine_*.sh`, `local_smoke.sh` (runs the same job code against the mock on a laptop). |
| `configs/agentload_*.yaml` | `mock`, `mock_server`, `c_closed` (Stage C), `e0_miss`, `e0_cap`, `e2_burst` (all three arms are overrides of this one file), `analysis` (incl. the `trap_v2` and `closed` blocks), `plan_budget`, `prereg_template`, `trap_power`. Research question is the first key of each. |

Workload fidelity to the sim: L0 = 2000, Δ = 550, d = 100, geometric mean 15 (cap 60), Exp(5 s) tool time, burst 200 in 60 s. A test checks the prompt at turn t is exactly L0 + (t−1)(Δ+d) tokens and that each prompt extends the previous prompt plus its output.

Known fidelity gaps (all flagged, none hidden):
1. **Output feedback.** In token mode the next prompt appends the model's actual output only if the server returns token ids (`choices.0.token_ids`, or the paths in `server.output_ids_paths`; vLLM may need `request_token_ids: true`, UNVERIFIED). Otherwise it appends synthetic ids (`output_ids_source=synthetic` in every row), so a "hit" covers the previous prompt but not its d output tokens: the follow-up miss tail is Δ+d = 650, not Δ = 550 (tested on the mock). The probe's third request (`return_token_ids=true`, sent regardless of config) shows which case applies (`PROBE_SUMMARY.output_ids_present`). **`output_feedback` is pinned per job** (`OUTPUT_FEEDBACK=server|synthetic`, required for miss/cap/burst; `auto` is for MODE=smoke only) and the analysis guard `output_source_differs` flags compared runs with different sources; see D5. Text mode (`workload.prompt_mode: text`) is the alternative; it appends the returned text but cannot control token counts exactly (no offline tokenizer).
2. **Hit definition.** The sim's hit = whole session KV resident. Here a turn counts as a hit if `cached_tokens / prompt_tokens > 0.5` (reported next to the token-weighted rate). A missing `cached_tokens` is treated as 0 only if some other request in the run reports it (vLLM may omit the field when 0; UNVERIFIED).
3. **Window attribution.** The sim attributes hits to admission time; the client sees completion time (default) or send time. They differ by the service time (seconds vs 1000 s windows).
4. **Queue.** Engine waiting-count metric if present (names UNVERIFIED, candidates in `configs/agentload_analysis.yaml`), else client in-flight count (includes running requests, so it is an upper bound on the waiting queue; `queue_source` column says which).
5. **First byte.** Streaming is off, so `t_headers` ≈ completion, not TTFT.

## 4. Experiments (stage order: S0 → C → E0a → [E0b] → pre-register → E2 paired arms → native pool → grid)

### Stage 0: test job (≈ 0.8 GPU-h per engine, §7; needs approval)
`MODE=smoke` in `slurm/sglang_job.sbatch` / `slurm/vllm_job.sbatch`. Per engine: `check_engine_flags` (greps `--help` for every flag the scripts use; aborts before launch on a miss), launch, health, `probe`, a ~30 min closed-population run with the cache on. Decide from the logs: (a) flags/env vars exist; (b) `cached_tokens` is reported and where; (c) token ids returned? (**required item 1: if yes, `OUTPUT_FEEDBACK=server` for everything that follows**); (d) metric names (`metrics_first.txt`); (e) 40k context accepted; (f) KV cap honored, and what the native pool is (needed for the required native-pool λ); (g) client `prompt_tokens` equals server `prompt_tokens` in token mode; (h) cache-flush endpoint works with no requests running, **judged by the canary (`canary_*_check.json`: the primed canary must miss after the flush) not by the HTTP status**, and the idle gauges named in `canary:` exist; (k) `PROBE_SUMMARY`: `return_token_ids_http`, `output_ids_present`, `request2_cached_tokens`, server `prompt_tokens` = 64; (l) `extra_body` fields `repetition_penalty`/`top_p` accepted (HTTP 200) by both engines; (m) `--exclude=nova22-amp-7` still wanted: both node classes report the same `nvidia-smi` name/memory?; (i) real startup time and inter-run gap (replace `startup_h`, `gap_s` in the budget config); (j) GPU name and topology. Edit `slurm/engine_*.sh` and `configs/agentload_analysis.yaml` accordingly.

### Stage C: closed-population μ(n) on the real engine, cache ON (new; before E0a/E2)
`MODE=closed`, `configs/agentload_c_closed.yaml`. n ∈ {16, 24, 32, 48, 96, 300} under SGLang `--schedule-policy fcfs`, and n ∈ {48, 300} under `lpm`; one seed per n; **warmup 900 s, measured 1800 s** (2700 s per run); the cache is flushed and verified empty between runs. `N_LIST` has no default (the grid is split over jobs so each fits 4 h: `N_LIST="16 24 32"`, `"48 96 300"`, and `POLICY=lpm N_LIST="48 300"`; 3 runs per job in the budget). Per run, over the measured window, the analysis (`python -m analysis.summarize closed --run-dirs … --warmup-s 900`) records: **completions/s** (completed sessions/s and the lower-variance turns/s ÷ E[T], both), **hit fraction** (turns with cached share > 0.5; first turns count as misses, so the ceiling is ≈ 1 − 1/E[T] ≈ 0.93), the follow-up-only hit fraction, the **token-weighted cached fraction** (Σcached/Σprompt), and the **queue** (engine waiting gauge if the metric exists, else client in-flight requests; `queue_source` says which). `mu_curve.json` holds per-cell curves, `argmax_n` and the top-level **`n_cap` = argmax μ(n) of the FCFS cell** (`mu_max`, `mu_300`), a near-tie flag (`argmax_ambiguous`: runner-up within 5%, one run per n!), whether both estimators agree, and whether the n grid is complete. Ties go to the smaller n. The CAPPED arm reads `n_cap` from this file (`CAP_FILE=…/mu_curve.json` or `N_CAP=<int>`).

### E0a: λ_miss (cache disabled in the engine)
`MODE=miss`, SGLang `--disable-radix-cache`, vLLM `--no-enable-prefix-caching`. Closed population 32 (sim: 60, insensitive across 30/60/120), 900 s warmup + 1800 s measured, 3 seeds, plus one population-64 check (analysed separately, not averaged in). Output `calibration.json` with `lambda_miss` (sessions/s, the sim's headline) and `lambda_miss_turns_based` (turns/s ÷ E[T]); rates in later configs use `lambda_miss_turns_based` (lower variance for short runs). Deviation D2: sim used 5 seeds × 100,000 s.

### E0b: λ_cap from empty (SGLang `lpm`, cache on) — cross-check, not an input of the pre-registration
`MODE=cap`: open loop at multiples of λ_miss, e.g. 1.0, 1.4, 1.8, 2.2, 2.6, 3.0 then a refinement round, one seed per point, 3000 s each, cache flushed and queue drained between runs (`flush_cache` logs success or failure to `job_events.log`; STRICT_FLUSH aborts the job if it fails, because a non-empty cache voids "from empty"). Stability rule = sim's: final queue < 50, fitted queue rise over the last min(5000, run/2) s ≤ 10, not aborted. Like the sim's, this is a finite-horizon lifetime criterion; 3000 s cannot see slow escapes. E0b's λ_cap/λ_miss (R) is now a cross-check of Stage C's window rather than the source of the E2 λ points (the old Gate 1: R < 1.5 ⇒ no window). It is kept in the budget because the referee's "cheap stages" (≈ 20–25 GPU-h) include it; it can be dropped if GPU-hours are short (−8.70).

### Pre-registration (new; between E0a and E2, committed before any E2 job)
`configs/agentload_prereg_template.yaml` holds the predictions to be filled **by formula** from `mu_curve.json` and `calibration.json` (`python -m analysis.prereg fill --template … --mu-curve … --calibration … --out NEWFILE --lambda-mults … --rule "…"`; refuses to overwrite; `validate FILE` exits 1 on errors):
- **recovery threshold ≈ μ(300)** (sessions/s; also in multiples of λ_ref): below it the closed curve never falls under the arrival rate, so any burst drains;
- **metastable window (μ(300), max_n μ(n))**: the good state exists, the all-miss tail cannot carry λ, a large enough burst traps; above max μ there is no good state (NOBURST must collapse too);
- trapped completion rate = λ_miss (criterion (a) compares against it) with a consistency check |μ(300)/λ_ref − 1| vs the ±15% tolerance;
- per-regime predictions for the three arms, the **PASS rule** (parameters copied from `trap_v2` and checked key by key against the applied analysis config), the **kill conditions** (no-burst arm collapses, nothing traps, cap does not rescue, empty window), the λ points (`lambda_mults`, must lie strictly inside the window; **the lead writes the rule that chooses them**) and the single native-pool λ.
`summarize burst2 --prereg FILE` records the file's sha256 and git state; a verdict counts as **decisive** only if the file is valid, committed and unmodified, and the tested λ lies in its registered window; otherwise `kill_verdict_v2.json` says it is exploratory.

### E2: paired-arm burst test (the kill test)
`MODE=burst`, per (λ, seed) three arms with **common random numbers**: same seed ⇒ same Poisson arrivals and per-session specs (turn counts, tool times); the content salt differs per run by design (it keeps a missed flush from producing cross-run prefix hits), so token content differs but not lengths or timing.
- **BURST**: as before (200 sessions in 60 s at t_b = 1200 s; 8700 s run).
- **NOBURST**: the same plan with the burst sessions removed (`arrivals.burst=null`; the post-burst window is still anchored at `arrivals.analysis_t_burst_s`, recorded in every arm).
- **CAPPED**: BURST plus a **client-side session cap** N_cap = argmax μ(n) from Stage C: the generator never has more than N_cap sessions active; excess new sessions wait in a FIFO gate between arrival and first request and their wait is logged.
One arm per job (`ARMS=burst|noburst|capped`; the default is all three, which the wall-time check refuses in a 4 h job). λ points: those of the filled pre-registration, inside the measured window, × seeds {0,1,2} (budget: 3 λ). The engine is SGLang FCFS, refresh on (cell A). Between runs: cancel, drain, flush, canary-verify. **Native pool**: the same with `KV_TOKENS=native` for one λ (required item 2), after its own Stage C. **Grid** (cells A refresh off, B on/off, C, D): BURST arm only, λ points re-set from the pre-registration.

### Kill criterion v2 (pre-registrable) and PASS rule
Definitions are in §5. Per λ: **PASS** iff BURST **trapped** AND NOBURST **good** (hit > 0.8, backlog < 20) AND CAPPED **recovered**, in ≥ 2/3 of the seeds (≥ 3 seeds; a seed missing an arm counts as a failure). `kill_verdict_v2.json` lists per-seed arm states, pass counts, a plain-language diagnosis per λ (e.g. "the no-burst arm does not stay good (no good state at this λ)"), the pairing check (arm configs must differ only in burst/gate/label keys), the legacy hit-rate verdict as secondary, the guard summary and the pre-registration provenance. Referee decision rule: if the NOBURST arm also collapses, or nothing traps, drop this framing.

The old rule ("the burst does not trap FCFS in ≥ 2/3 of runs at any λ ∈ (1.2, 2)×λ_miss ⇒ kill") survives as the SECONDARY hit-rate criterion in `kill_verdict.json` (`summarize burst`), computed over BURST-arm runs only.

Interpretation table for the report (no result exists yet):

| Outcome | Reading |
|---|---|
| BURST traps, NOBURST good, CAPPED recovers (≥ 2/3 seeds) at a λ in the registered window | mechanism transfers to SGLang FCFS at the 300k pool; proceed to native pool and grid |
| NOBURST also collapses | no good state at that λ (λ above max μ or the engine is already thrashing): the framing is dead there |
| nothing traps at any in-window λ | the sim's mechanism does not transfer (or the window is empty/too narrow for the noise) |
| BURST traps, CAPPED does not recover | the session count is not the mechanism, or λ > μ(n_cap) |
| BURST draining (slope < 0) | slow recovery, not a trap; distinguishes what the hit-rate rule could not (D1) |
| A traps, B/C recover (grid) | ordering matters on the real engine, contradicting the sim |
| A, B, C trap alike | consistent with the sim's admission-not-ordering reading |

## 5. Analysis definitions (hit-rate rule = the sim's, now SECONDARY; throughput rule = primary)

Windows of 1000 s, complete windows only. Ported from `prefixmeta`: `trapped` = longest run of consecutive post-burst windows with hit rate < 0.2 lasts ≥ `trap_min_s`; `hit_eval` over [t_b + `hit_eval_from_s`, end]; `recovered` = `hit_eval` > 0.8 and tail-queue mean < 20 (tail = last min(5000, run/2) s); stable-from-empty; ramp escape (queue > 128) and re-entry (5 bins < 20). Additions: `good_before` (pre-burst hit > 0.5 and queue < 20); `trapped_aborted` (client aborted for overload and the last 3 post-burst windows all < 0.2); verdicts `recovered | trapped | trapped_aborted | indeterminate | no_burst`. The analysis defaults are the sim's (`trap_min_s` = `hit_eval_from_s` = 10000); the job scripts pass the short-protocol values (3000 / 4500).

**Throughput-based criterion (primary; `analysis/trap_v2.py`, parameters `trap_v2` in `configs/agentload_analysis.yaml`, copied into the pre-registration).** Per run, over the post-burst evaluation window W = [t_b + `eval_from_s`, end] (`eval_from_s` = 4500 s in the short protocol ⇒ W = 3000 s; shorter than 600 s ⇒ indeterminate), with λ the run's arrival rate and λ_miss the `arrivals.lambda_ref` it was set from (both recorded in `meta.json`):
- **backlog** = client sessions in the system (planned arrival minus completed/failed; **includes the gate queue**); **slope** = OLS slope (sessions/s) of its 10 s bin means over W.
- **TRAPPED** iff (a) the session completion rate over W is within ±15% of λ_miss AND (b) slope > 0.5 × (λ − λ_miss); plus the explicit condition λ > λ_miss (without it the bare formula would call a healthy system at 0.9 λ_miss "trapped").
- **DRAINING** iff slope < 0. **RECOVERED** (= "good") iff hit fraction > 0.8 and backlog < 20, both averaged over the last 300 s. `state` ∈ trapped > recovered > draining > indeterminate. The old hit-rate verdict, hit_eval and the tail queue slope are carried next to it as secondary columns.
- **Rate estimator** (`trap_v2.rate_estimator`, decided before pre-registering): `sessions` = completed sessions/s (the literal "session completion rate", default) or `turns_based` = turns/s ÷ E[T] (same estimand, lower variance). Both are always written; `estimators_agree` flags runs where they would give different answers for (a).

**Operating characteristic (a MODEL, not an engine result; `experiments/agentload_trap_power.py`, `results/agentload_trap_power/20261021-053658/power.csv`):** with Poisson arrivals and Poisson departures at λ_miss = 0.0474 (the simulator's value), a TRULY trapped window of 3000 s and the sessions estimator, 20,000 seeded replicates give P(a) = 0.93 (0.87 if the λ_miss it is compared against is off by 5%), P(b) = 0.77 / 0.86 / 0.98 / 1.00 at λ = 1.2 / 1.3 / 1.6 / 1.9 × λ_miss, and P(a and b) = 0.73 / 0.82 / 0.91 / 0.93. A 6000 s window raises P(a) to 0.99 and P(a and b) at 1.2× to 0.84. At λ = 1.1× the criterion fires in 60% of truly trapped 3000 s windows. Poisson departures are probably pessimistic; the turns-based estimator is not modelled.

## 6. Deviations and open issues (for the lead)

- **D1: E2 timing (revised).** Sim: 5000 s warm-up + 25,000 s after the burst (30,000 s = 8.3 h; trap needs 10,000 s of hit < 0.2). The 4 h job limit cannot hold that, so the draft keeps t_b = 1200 s, 7500 s after (8700 s per run, one run per job), with the evaluation window starting at t_b + 4500 s (W = 3000 s). The first draft could not tell a trap from a slow drain by hit rate alone (draining a 200-session burst takes thousands of seconds); the **throughput criterion** (§5) is the answer to that: a drain shows a negative backlog slope and a completion rate above λ_miss, a trap a positive slope at ≈ λ_miss (tested on synthetic traces, including a slow drain that the old hit-rate rule calls "trapped"). What it cannot do is see an escape that happens after 8700 s (finite horizon, like the sim's λ_cap). A literal-protocol alternative needs `--time` ≈ 8.5-9 h; its cost is in §7.
- **D2: λ_miss** from short runs and the turns-based estimator (sim: 100,000 s, 5 seeds).
- **D3: KV pool** capped at 300k tokens to match the sim (native ≈ 1M).
- **D4: context** > 32,768 needs the long-context override (UNVERIFIED), or `max_turns` 45.
- **D5: output feedback (pending Stage 0).** If an engine does not return output token ids, `synthetic` feedback makes every hit turn prefill Δ+d = 650 uncached tokens (about 18% more than the simulator's Δ = 550) and leaves a dead d-token branch in the KV pool per turn. Then BOTH engines must run `synthetic` (not one of each), and the simulator's λ_cap/λ_miss comparison is like-for-like only if the simulator is re-run with an effective Δ of 650 (not done here; it is the lead's call) or the deviation is reported next to D1-D4. `meta.json` records `output_feedback_configured` and `outcome.output_ids_source_counts`; calibration.json records `output_ids_sources`.
- **D6: from-empty premise.** `reset_and_verify` (canary prime, flush, canary check) runs before every run; the run's `meta.json` carries `start_state_verified` and the analysis marks unverified open-loop runs as an error-severity guard (`guards.json`, also copied into `kill_verdict.json`). Each run in a job also has its own `workload.content_salt`, so a missed flush cannot produce prefix hits across runs; arrival and session-spec streams stay common across runs and engines. The canary needs the engine to report `cached_tokens` (else the check is `unverifiable` and `STRICT_FLUSH=1` aborts; MODE=smoke defaults to `STRICT_FLUSH=0` so Stage 0 can find out).
- **O1:** which cells count as "FCFS" for the kill rule. In the v2 design the pre-registered cell is SGLang FCFS with refresh on (label `sglang-fcfs-r1`, `--fcfs-substr fcfs` selects the FCFS cells; any other FCFS label in the same analysis would be a second cell and is reported separately).
- **O2 (superseded):** the E2 λ points are no longer fixed multiples (1.3/1.6/1.9×λ_miss): they come from the pre-registered window (μ(300), max μ(n)) measured in Stage C, expressed as multiples of λ_ref. 3 points are budgeted.
- **O3:** LPM patch (cell C). Not applied. In `python/sglang/srt/managers/schedule_policy.py` (path from the engine-sources note, no line number), change `WAITING_QUEUE_PREFIX_MATCH_MAX = 128` to a huge value (e.g. `10**9`). To be done in a separate editable install (`ENV_SGLANG_PATCHED`) so the stock cells stay stock. Whether prefix matching over thousands of waiting requests is too slow to serve is itself a finding.
- **O4:** the `a100` GRES may land on different A100 variants; the job scripts now `--exclude=nova22-amp-7` (unverified class), `calibration.json` records `hardware`, and cap/burst jobs refuse a different hardware string (`ALLOW_HW_MISMATCH=1` overrides; the analysis flags `hardware_mixed` / `hardware_vs_calibration`).
- **O5:** engine defaults I did not pin: HiCache off by default (per the engine-sources note), `radix_eviction_policy` lru. Confirm in the server log.
- **O6:** the vLLM FCFS cell cannot be varied (no ordering knob), only compared.
- **O7:** `/flush_cache` (SGLang) and `/reset_prefix_cache` (vLLM, may need `VLLM_SERVER_DEV_MODE`) are from memory; no flush = no "from empty".
- **O8:** the per-request client abort at 4000 in-flight requests. In the trapped regime the queue can reach thousands; a run that hits the cap is recorded as aborted, not as a failed experiment.
- **O9 (rate estimator).** The spec says "session completion rate" and "completions/s"; the default is the literal sessions/s. In the model above it makes criterion (a) fail in ≈ 7% of truly trapped 3000 s windows by Poisson noise alone, and the Stage-C `n_cap` argmax is noisier with it (one run per n, flagged when the runner-up is within 5%). `turns_based` has the same estimand and far lower variance and is consistent with the `lambda_miss_turns_based` that sets λ. One key (`trap_v2.rate_estimator`, `closed.mu_estimator`) flips both; decide before pre-registering. Not changed because it would depart from the spec text.
- **O10 (backlog < 20 is in sessions).** In-flight sessions include tool-time sleeps: by Little's law the healthy level is ≈ λ × (session duration ≈ 14 turns × (5 s + service)), i.e. on the order of 5-10 at λ ≈ 0.06-0.1 sessions/s. The threshold 20 (spec) is therefore only ~2× the healthy level at the simulator's λ and would be violated by a healthy system at λ ≳ 0.2 sessions/s. The real λ_miss is unknown until E0a; re-check before pre-registering.
- **O11 (hit > 0.8 has little headroom).** The turn-level hit fraction counts first turns as misses: ceiling ≈ 0.93 with E[T] = 14.76; with partial misses a healthy state can sit near 0.85. Both the follow-up-only and the token-weighted fractions are logged. The threshold is the spec's.
- **O12 (explicit λ > λ_miss in TRAPPED).** An addition to the spec's two conditions, see §5; it only matters for λ ≤ λ_miss.
- **O13 (CRN scope).** Arrivals and session specs are common across the three arms; token content is not (per-run salt, deliberate). Pairing validity is checked from the effective configs (`pairing_problems` in the verdict).
- **O14 (Stage C has one run per n).** μ(n) noise is 5-10% (≈ 100-200 session completions in 1800 s); the argmax is flagged when ambiguous, but a wrong `n_cap` weakens the CAPPED arm, and the window edges inherit the noise (`boundary_margin_rel` in the template). Replicates at the knee (n = 24, 32) are the obvious extra spend (≈ 0.75 GPU-h per run plus startup).
- **O15 (ASSUMPTIONS in the budget, not in the spec).** (i) Stage C is repeated on the native pool (5.30 GPU-h) because the 300k-pool window does not transfer; (ii) the native-pool replicate is 1 λ × 3 seeds × 3 arms (24.45); (iii) E0b stays in the calibration gate as a cross-check; (iv) grid cells D (vLLM) and C (patched LPM) have no Stage-C curve of their own, so their boundaries are not pre-registered; (v) grid λ points are two of the pre-registered ones; if only one is in E2a, `E2b_sglang_fcfs_r1_2x` covers the other.
- **O16 (cost).** The paired kill test is 27 one-run jobs (73.35 GPU-h at 3 λ). Dropping to 2 λ saves 24.45; shortening the NOBURST arm would break the CRN pairing window and is not done.

## 7. GPU-hour estimate (plan arithmetic, not a measurement)

Source: `analysis/plan_budget.py` on `configs/agentload_plan_budget.yaml`; recorded in `results/agentload_plan_budget/20261021-053658` (`gpu_hours_by_stage.csv` with an `arithmetic` column, `gpu_hours_arithmetic.txt`, `gpu_hours_totals.json`, `gpu_hours_by_stage_alt_literal_e2.csv`).

Per stage: jobs = ⌈n_runs / runs_per_job⌉; job wall = startup + runs_per_job·run_s/3600 + (runs_per_job−1)·gap/3600 + teardown, with startup = 0.25 h, gap = 180 s, teardown = 0.05 h (**guesses**, replaced by Stage-0 timings); a last, smaller job is charged for the runs it holds. Worked example, Stage C FCFS (6 runs of 2700 s, 3 per job): each job is 0.25 + 3·0.75 + 2·0.05 + 0.05 = 2.65 h, two jobs ⇒ 5.30 GPU-h; Stage C LPM (2 runs, one job): 0.25 + 2·0.75 + 0.05 + 0.05 = 1.85 h. E2 (one 8700 s arm per job): 0.25 + 2.4167 + 0 + 0.05 = 2.7167 h, 27 jobs ⇒ 73.35.

| Stage | Runs | Jobs | GPU-h |
|---|---|---|---|
| S0_smoke_sglang | 1 × 1800 s | 1 | 0.80 |
| S0_smoke_vllm | 1 × 1800 s | 1 | 0.80 |
| C_closed_sglang_fcfs | 6 × 2700 s | 2 | 5.30 |
| C_closed_sglang_lpm | 2 × 2700 s | 1 | 1.85 |
| E0a_miss_sglang | 4 × 2700 s | 1 | 3.45 |
| E0a_miss_vllm | 4 × 2700 s | 1 | 3.45 |
| E0b_cap_sglang_lpm | 9 × 3000 s | 3 | 8.70 |
| E2a_kill_sglang_fcfs_paired | 27 × 8700 s | 27 | 73.35 |
| C_closed_sglang_fcfs_native | 6 × 2700 s | 2 | 5.30 |
| E2c_native_sglang_fcfs_paired | 9 × 8700 s | 9 | 24.45 |
| E2b_sglang_fcfs_r0 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_fcfs_r1_2x | 3 × 8700 s | 3 | 8.15 |
| E2b_sglang_lpm_r1 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_lpm_r0 | 6 × 8700 s | 6 | 16.30 |
| E2b_sglang_lpm_inf | 6 × 8700 s | 6 | 16.30 |
| E2b_vllm_fcfs | 6 × 8700 s | 6 | 16.30 |
| **Total** | | 81 | **217.10** |

Stage arithmetic, as printed by `plan_budget.py`:
```
S0_smoke_sglang: 1 x (0.25 + 1 x 0.5000 + 0 x 0.0500 + 0.05) = 0.800 h  =>  0.80 GPU-h
S0_smoke_vllm: 1 x (0.25 + 1 x 0.5000 + 0 x 0.0500 + 0.05) = 0.800 h  =>  0.80 GPU-h
C_closed_sglang_fcfs: 2 x (0.25 + 3 x 0.7500 + 2 x 0.0500 + 0.05) = 2.650 h  =>  5.30 GPU-h
C_closed_sglang_lpm: 1 x (0.25 + 2 x 0.7500 + 1 x 0.0500 + 0.05) = 1.850 h  =>  1.85 GPU-h
E0a_miss_sglang: 1 x (0.25 + 4 x 0.7500 + 3 x 0.0500 + 0.05) = 3.450 h  =>  3.45 GPU-h
E0a_miss_vllm: 1 x (0.25 + 4 x 0.7500 + 3 x 0.0500 + 0.05) = 3.450 h  =>  3.45 GPU-h
E0b_cap_sglang_lpm: 3 x (0.25 + 3 x 0.8333 + 2 x 0.0500 + 0.05) = 2.900 h  =>  8.70 GPU-h
E2a_kill_sglang_fcfs_paired: 27 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  73.35 GPU-h
C_closed_sglang_fcfs_native: 2 x (0.25 + 3 x 0.7500 + 2 x 0.0500 + 0.05) = 2.650 h  =>  5.30 GPU-h
E2c_native_sglang_fcfs_paired: 9 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  24.45 GPU-h
E2b_sglang_fcfs_r0: 6 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  16.30 GPU-h
E2b_sglang_fcfs_r1_2x: 3 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  8.15 GPU-h
E2b_sglang_lpm_r1: 6 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  16.30 GPU-h
E2b_sglang_lpm_r0: 6 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  16.30 GPU-h
E2b_sglang_lpm_inf: 6 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  16.30 GPU-h
E2b_vllm_fcfs: 6 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  16.30 GPU-h
```
Gates and sums:
```
gate0_smoke = 0.80 + 0.80 = 1.60 GPU-h  [S0_smoke_sglang, S0_smoke_vllm]
gateC_closed_mu = 5.30 + 1.85 = 7.15 GPU-h  [C_closed_sglang_fcfs, C_closed_sglang_lpm]
gate1_calibration = 3.45 + 3.45 + 8.70 = 15.60 GPU-h  [E0a_miss_sglang, E0a_miss_vllm, E0b_cap_sglang_lpm]
gate2_kill_test = 73.35 = 73.35 GPU-h  [E2a_kill_sglang_fcfs_paired]
gate_native_pool = 5.30 + 24.45 = 29.75 GPU-h  [C_closed_sglang_fcfs_native, E2c_native_sglang_fcfs_paired]
full_grid = 16.30 + 8.15 + 16.30 + 16.30 + 16.30 + 16.30 = 89.65 GPU-h  [E2b_sglang_fcfs_r0, E2b_sglang_fcfs_r1_2x, E2b_sglang_lpm_r1, E2b_sglang_lpm_r0, E2b_sglang_lpm_inf, E2b_vllm_fcfs]
cheap_before_prereg = 1.60 + 7.15 + 15.60 = 24.35 GPU-h  [gate0_smoke, gateC_closed_mu, gate1_calibration]
through_kill_test = 1.60 + 7.15 + 15.60 + 73.35 = 97.70 GPU-h  [gate0_smoke, gateC_closed_mu, gate1_calibration, gate2_kill_test]
through_native_pool = 1.60 + 7.15 + 15.60 + 73.35 + 29.75 = 127.45 GPU-h  [gate0_smoke, gateC_closed_mu, gate1_calibration, gate2_kill_test, gate_native_pool]
total = 1.60 + 7.15 + 15.60 + 73.35 + 29.75 + 89.65 = 217.10 GPU-h
```
Reading: the referee's "cheap stages" (Stage 0, calibration, closed μ(n); ≈ 20–25 GPU-h) come to **24.35** here, of which Stage C is 7.15. Through the kill test: 97.70; with the native-pool gate: 127.45; everything: **217.10** (49 jobs and 131.30 GPU-h before the redesign). The paired E2 stages (27 + 9 runs) are 97.80 of the total. Not included: CPU-only env build, model download, re-runs after failures, vLLM Stage C. For the literal timing (28,000 s per run: 3000 s warm-up + 25,000 s after the burst, job limit 9 h) the totals are gate-2 218.10, native pool 78.00, grid 266.57, total **587.02** GPU-h.

Load per E2 run, sized with the **simulator's** λ_miss = 0.0474 sessions/s (`results/prefix_meta_e0/20261021-005706/e0_summary.json` in the main checkout; the real λ_miss is unknown until E0a): at 1.6× and seed 0 the BURST/CAPPED plan has 914 sessions (200 burst), 13,533 turns and 141,076,650 prompt tokens if every turn missed; max prompt 40,350 tokens (`results/agentload_e2_burst_planstats/20261021-021037/plan_stats.json`). About 1.6 requests/s average, so the client side is light; the in-flight cap (4000 requests) matters only in a runaway regime (outstanding requests ≤ sessions in the system).

## 8. Run locally (laptop, mock server; this is what was tested)

```
/opt/anaconda3/bin/python -m pytest                       # full suite
/opt/anaconda3/bin/python experiments/agentload_record_tests.py   # same, recorded under results/agentload_tests/<ts>
PYTHONPATH=src python -m agentload.mock_server --config configs/agentload_mock_server.yaml --port 18080 &
PYTHONPATH=src python -m agentload run --config configs/agentload_mock.yaml
PYTHONPATH=src:. python -m analysis.summarize windows --run-dirs results/agentload_mock/<ts> --set windows.window_s=4
ENV_GEN=/opt/anaconda3 slurm/local_smoke.sh closed        # Stage C job glue against the mock (N_LIST="2 4")
ENV_GEN=/opt/anaconda3 slurm/local_smoke.sh burst         # the three paired arms against the mock, then burst + burst2 analysis
PYTHONPATH=src:. python -m analysis.summarize closed --run-dirs <Stage C run dirs> --warmup-s 900      # -> mu_curve.json
PYTHONPATH=src:. python -m analysis.prereg fill --template configs/agentload_prereg_template.yaml --mu-curve <mu_curve.json> --calibration <calibration.json> --out configs/agentload_prereg_<date>.yaml --lambda-mults … --rule "…"
PYTHONPATH=src:. python -m analysis.summarize burst2 --run-dirs <all E2 run dirs> --prereg configs/agentload_prereg_<date>.yaml   # -> kill_verdict_v2.json
PYTHONPATH=src:. python experiments/agentload_trap_power.py   # operating characteristic of the trap criterion (model)
```

Recorded at commit 367f8ac on a clean tree: tests in `results/agentload_tests/20261021-052646` (**274 passed, 0 failed, 0 skipped**, 560 s; `junit.xml`, `pytest_stdout.txt`, `meta.json`). The previous revision had 189. New in this revision: `test_agentload_gate.py` (15: gate unit tests incl. FIFO and both cancellation races, the three arms end to end on the mock server with identical session specs except the burst, cap never exceeded recomputed from the log, gate waits logged, censored waits), `test_analysis_trap_v2.py` (25: trapped / draining / recovered / noburst-collapse on synthetic traces, PASS rule, pairing checks, `burst2` CLI on synthetic run dirs and on mock-server arms), `test_analysis_closed.py` (11: Stage C on the mock server with a thrashing curve, synthetic μ(n) cases, hand-off of `n_cap` to the gate), `test_prereg.py` (9), `test_trap_power.py` (3), plus additions to `test_slurm_scripts.py` (MODE=closed and the three-arm job glue, input validation, KV_TOKENS=native, time budget; 82 tests in that file) and `test_plan_budget.py`. The mock numbers say nothing about SGLang or vLLM: the mock's thrashing curve is built to have a knee, so the Stage-C tests check the code path (argmax, flags, hand-off), not a result. Earlier recorded mock-server demos (`results/agentload_mock_demo/…`) show the file layout only.
