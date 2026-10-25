# Real agent-trace workload statistics (referee objection 3: our tool times are synthetic)

Branch `r7/traces`, written 2026-10-25. Everything below was computed by the scripts in `scripts/traces/` from public data (commands at the end); every number traces to `results/traces_summary/<source>/` (force-added: `summary.json`, `headline.csv`, `quantiles.csv`, `tokens.csv`, `tables.md`, `meta.json`) and `results/traces_summary/exceedance.{csv,md}`. The simulator was not changed (`src/` untouched); the proposed workloads are `configs/workload_trace_tracelab.yaml` and `configs/workload_trace_mini_swe_v2.yaml`.

## Answer in one table

Workload of record: first prompt 2000 tokens, +550 tool tokens and 100 output tokens per turn, T ~ min(Geometric(1/15), 60) (mean 14.76 calls), tool time Exp(5 s).

| quantity | workload of record | SyFI TraceLab (Claude Code + Codex CLI, 571,612 timed turns) | mini-SWE-agent v2.0.0 on SWE-bench Verified (17,963 timed steps, 500 trajectories) |
|---|---|---|---|
| tool time, mean | 5 s | **13.6 s raw, 8.47 s capped at 600 s** | **1.39 s** |
| tool time, median | 3.47 s | **0.237 s** | **0.104 s** |
| tool time, p90 / p99 | 11.5 s / 23.0 s | 12.4 s / 171 s | 1.82 s / 33.8 s |
| tool time, CV | 1 | 37.4 raw, 4.66 capped | 4.30 |
| P(tool time > 5 s) / > 30 s / > 60 s | 36.8% / 0.25% / 0% | 20.1% / 6.6% / 3.2% | 5.1% / 1.1% / 0.56% |
| share of total tool time in calls > 30 s / > 60 s | 1.7% / 0% | 78% / 64% (capped series) | 41% / 24% |
| KS distance to Exp(5 s) / to Exp with the sample mean | - | 0.480 / 0.558 | 0.692 / 0.496 |
| model calls (turns) per agentic run, mean (median, p90, p99) | 14.8 (11, 34, 60) | 13.0 (5, 28, 116); whole sessions 82.6 | 36.9 (32, 63, 104) |
| tokens appended per call by tool output (delta_ctx), mean (median, p90) | 550 | 1,268 (210, 3,243); winsorised mean 1,251 | 434 (198, 1,066); winsorised mean 429 |
| output tokens per call, mean (median, p90) | 100 | 589 (249, 1,332) | 271 (116, 659) |
| prompt of the first call of a session, mean (median) | 2,000 | 23,308 (17,718); but 206,951 at the first call of an agentic run (the conversation so far) | 1,862 (1,784) |
| prompt at an average call | 2000 + 650 (t-1), about 11k at t = 15 | 171,576 (median 132,092) | 17,939 (median 15,067) |

Reading: our Exp(5 s) has a middle-of-the-road mean (between the two sources) but the wrong shape in both. Real tool calls are two-regime and heavy-tailed: 63-85% finish in under a second (median 0.10-0.24 s, 15-33 times below our 3.5 s) while a few percent last tens of seconds to minutes and carry most of the time (24% of the mini-SWE-agent time and 78% of the raw TraceLab time, 64% after capping at 600 s, is in calls over 60 s, against 0% for Exp(5 s)). Tool time CV is 4-5 (capped) against our 1. Tokens per call are 0.8x (mini-SWE-agent) to 2.3x (TraceLab) our +550 with a heavy tail (CV 1.9 and 2.7; the median is 200), and output tokens per call are 2.7x to 5.9x our 100. Turns per run: TraceLab is 13 but heavily skewed (median 5), mini-SWE-agent 37 (median 32, much less skewed); ours, 15, is geometric. Only the mini-SWE-agent first prompt (1.9k) matches our 2k; the prompt of an average TraceLab call (172k tokens) would by itself fill 57% of the 300k-token KV pool of the workload of record.

## Sources

### Used

| | SyFI TraceLab | mini-SWE-agent v2.0.0 trajectories |
|---|---|---|
| what | Real Claude Code and Codex CLI sessions of 52 pseudonymous developers, Sep 23 2025 - Jul 24 2026 (release v0.0.2, "SyFI Coding Trace v2"): 8,058 sessions, 665,453 LLM rounds, 743,819 tool calls, 114.2B input tokens | Published SWE-bench Verified "bash-only" runs of mini-SWE-agent 2.0.0 (directories dated 2026-02-17), one shell command per step in the SWE-bench docker image, 60 s command timeout |
| URL | https://github.com/uw-syfi/TraceLab/releases/tag/v0.0.2, asset `syfi_coding_trace.jsonl.gz` (100,939,722 bytes, SHA-256 `11ce51ec...4fb65` = the digest GitHub publishes; verified) | public S3 bucket `swe-bench-submissions`, key `bash-only/<run>/trajs/<instance>/<instance>.traj.json` (listable without credentials); https://github.com/SWE-bench/experiments indexes these submissions |
| paper / citation | Zhu, Jacob, Ma, Pan, Wang, Krishnamurthy, Kasikci, "TraceLab: Characterizing Coding Agent Workloads for LLM Serving", arXiv:2606.30560 (Jun 2026) | mini-SWE-agent, https://github.com/SWE-agent/mini-swe-agent |
| licence | data CC BY 4.0, code Apache-2.0 (README of the repository, read 2026-10-25). The project site https://tracelab.cs.washington.edu/ states no licence. Attribution required: cite the paper and the dataset | mini-SWE-agent software: MIT. The SWE-bench/experiments repository, which indexes the submissions, shows no LICENSE file and no licence in its About box (read 2026-10-25), so I found no stated licence for the trajectories: used for aggregate statistics only, raw files are not redistributed (gitignored under `results/traces_raw/`), nothing but derived numbers is committed |
| sample | the whole release | 5 of the 13 listed v2.0.0 runs (claude-4-5-sonnet-high, claude-4-5-opus-high, gpt-5-2-high, gpt-5-mini, kimi-k2-5-high), the SAME 100 SWE-bench Verified instances in each (seeded draw, seed 20261024 from the 500 ids): 500 trajectories, 188 MB |
| download | 100.9 MB, 32 parallel HTTP range requests, checksum verified | 500 files, 188 MB, size of every file checked against the bucket listing |
| timing semantics | `emitted_at` (the model's tool_call event) and `result_at` (the tool_result event), both from the agent's own session log; `tool_wall_latency_ms = result_at - emitted_at`; `tool_internal_latency_ms` = the duration the tool or runner reports (Codex wrapper "Wall time", Claude durationMs), when present | `extra.timestamp` is set on an assistant message when the model response has come back and on every tool message when the shell command has returned; command time = timestamp(last tool message) - timestamp(assistant message). LLM latency = timestamp(assistant k) - timestamp(last tool message of step k-1) |
| what the "tool time" is | client-observed wall time from the model asking for the tool to the result being appended: command execution plus permission prompts (a human waiting is in the data), tool start-up, and for delegation tools the whole sub-agent run | wall time of the `docker exec` command(s) of the step, with the harness's 60 s limit (censoring) |

Cross-check of the TraceLab parse against the dataset authors' own description (project site, release v0.0.2): 52 users, 8,058 sessions (5,319 Claude, 2,739 Codex), 665,453 agent steps (305,445 / 360,008), 743,819 tool calls and the window Sep 23 2025 - Jul 24 2026 all match my row counts exactly; the site's Claude tool-latency p50 115 ms and p90 10.1 s compare with my Claude wall-clock median 113 ms and p90 9.0 s (tool calls without human tools); the site's Codex wall-minus-internal residual median 0.16 s with my 0.154 s. The GitHub front page still describes an earlier snapshot ("357K rounds from 43 developers"); the 43 in `configs/traces_analysis.yaml` before this commit came from there. The site counts 84,538 "requests" (one user input through the final response); my 92,024 "episodes" use a different cut (below), so those two numbers differ by definition.

### Looked at and not used

* One OpenHands SWE-bench trajectory per model (two models, instance astropy-12907, `results/traces_raw/probe_openhands/`; the origin URLs were not recorded before the interruption of this task): a bare list of `{role, content}` messages, no timestamps or durations. Unusable for timing.
* One mini-SWE-agent v1.16 trajectory (`probe_mini_v1.16/`): messages carry no `extra.timestamp`; the v2 format (`mini-swe-agent-1.1`) does. Not used.
* Continuum (arXiv 2511.02230): a web search found no released tool-call duration trace.
* Seen in the search results, not downloaded and not examined: the WEKA `kv-cache-tester` repository (739 Claude Code session traces with API time and think time per request, https://github.com/callanjfox/kv-cache-tester), MORI (arXiv 2606.00866), CacheWise (arXiv 2606.16824), "Ask the Tool, Don't Guess" (arXiv 2609.18849). Terminal-Bench, tau-bench and SWE-agent logs were not checked. They are leads for a referee who wants a third source.

## Method

Scripts (all run with `python -I`, data path as argument; nothing from the data is executed, `json` and `gzip` only):

* `fetch.py`, `list_s3.py`, `make_sample_list.py`, `download.sh`: allow-listed hosts (github.com, the S3 bucket), size and SHA-256 checks.
* `parse_tracelab.py`, `parse_mini_swe.py`: flat CSVs (`calls`, `rounds`, `episodes`, `sessions`) under `results/traces_norm/<source>/` (large, ignored).
* `analyze.py`: statistics, fits, quantile tables. `common.py`: lognormal MLE, KS-optimal mean-preserving lognormal, EM two-component lognormal mixture, KS distance, exact table moments. `write_meta.py`: `meta.json` (commit, seed, config, input checksums). `make_configs.py`, `compare.py`, `make_tables.py`. Driver `run_all.sh`; spec `configs/traces_analysis.yaml` (seed 0, cap 600 s, floor 10 ms).
* Tests: `tests/test_traces_scripts.py` (synthetic fixtures with known answers for the parsers, the fits, the KS distance, the table moments, the two-point match, the proposed configs; 14 pass against the round-7 workload module (`r7/robustness` 8c08883), 11 pass and 3 skip against the round-6 one in this worktree).

Definitions.

* **Turn** = one model call. A run with T calls has T-1 tool intervals (the simulator's convention; the last call ends the run).
* **Episode** (TraceLab) = maximal run of consecutive rounds of a session that ends with the first round that issues no tool call (an autonomous run for one user prompt); **agentic episode** = at least one tool call. 92,024 episodes, 47,887 agentic. For mini-SWE-agent one trajectory = one episode (500, all `Submitted`, 0 format-error retries).
* **Tool time** per turn. TraceLab headline `round_z`: last `result_at` minus last `emitted_at` of the round's tool calls, for rounds with at least one tool call and no human-interaction tool (AskUserQuestion, ExitPlanMode, ...); 571,612 turns. Per-call wall time and the runner-reported internal time are in `summary.json` (`call_wall_*`, `call_internal_*`). mini-SWE-agent: command time of the step (`phase_wall`); when a step issues several commands (6.1% of steps) only their total is observable.
* **Tokens.** First prompt = `input_tokens_total` of the first call of a session (conversation / trajectory). Appended tokens per turn = `delta_ctx` = input(k+1) - input(k) - output(k): what the client added between two consecutive calls (tool output plus any user text); negative values (context compaction: 1.3% in TraceLab, 1.0% in mini) are excluded and the mean is winsorised at p99.9 for the configs. Output tokens = completion tokens of the call. Prompt token counts include cached tokens.
* **Capped statistics.** Durations above 600 s (Claude Code's maximum Bash timeout) are set to 600 s: 0.18% of the TraceLab turns, which carry 5.1 s of the 13.6 s raw mean. This is the series every fitted law below describes. For mini-SWE-agent the cap never binds (the maximum is 60.08 s).
* **Fits.** Lognormal by MLE on max(x, 10 ms); the mean-preserving lognormal (the sample mean, with the CV that minimises KS: what `tool_time_dist: lognormal` takes); a two-component lognormal mixture by EM on log x (4 initialisations, <= 100,000 points, seed 0). KS = sup |F_n - F|, ties handled on both sides.

## Tool-time results

Seconds. "cap600" = after capping at 600 s. Full set (per provider, per model, per tool class, per tool): `results/traces_summary/*/tables.md`, `headline.csv`.

| series | n | mean | median | p90 | p99 | CV | mean / CV cap600 | < 1 s | > 60 s | time share of > 60 s |
|---|---|---|---|---|---|---|---|---|---|---|
| TraceLab, per turn (`round_z`, headline) | 571,612 | 13.6 | 0.237 | 12.4 | 171 | 37.4 | 8.47 / 4.66 | 63% | 3.2% | 78% |
| TraceLab, per turn, Claude Code | 259,736 | 19.9 | 0.118 | 10.0 | 216 | 36.6 | 10.1 / 4.94 | 71% | 4.1% | 89% |
| TraceLab, per turn, Codex CLI | 311,876 | 8.34 | 0.588 | 14.9 | 120 | 21.7 | 7.15 / 3.93 | 55% | 2.3% | 56% |
| TraceLab, per call (all except human tools) | 740,637 | 11.3 | 0.216 | 10.0 | 131 | 39.9 | 7.13 / 5.03 | 66% | 2.7% | 77% |
| TraceLab, shell calls only | 469,947 | 11.6 | 0.332 | 7.45 | 121 | 46.9 | 6.08 / 5.89 | 65% | 2.1% | 81% |
| TraceLab, runner-reported internal time (Codex-dominated) | 345,523 | 5.07 | 0.078 | 6.41 | 110 | 4.58 | 5.07 / 4.52 | 70% | 1.9% | 51% |
| TraceLab, inter-request idle (`gap_next`) | 561,940 | 42.9 | 1.16 | 30.1 | 241 | 88.6 | 14.5 / 3.53 | 48% | 5.2% | 87% |
| mini-SWE-agent, all 5 models (headline) | 17,963 | 1.39 | 0.104 | 1.82 | 33.8 | 4.30 | 1.39 / 4.30 | 85% | 0.6% | 24% |
| mini-SWE-agent, steps with one command | 16,861 | 1.43 | 0.091 | 1.82 | 36.1 | 4.31 | | 86% | 0.6% | 25% |
| mini-SWE-agent, excluding the 101 timed-out steps | 17,862 | 1.06 | 0.103 | 1.69 | 20.8 | 3.84 | | 86% | 0% | 0% |
| mini-SWE-agent by model: opus-4.5 / sonnet-4.5 / gpt-5.2 / gpt-5-mini / kimi-k2.5 (mean) | 3,167 / 4,882 / 3,468 / 1,875 / 4,571 | 1.77 / 0.90 / 0.82 / 1.69 / 1.97 | 0.156 / 0.100 / 0.084 / 0.069 / 0.128 | 2.13 / 1.26 / 1.42 / 3.11 / 2.72 | 48.6 / 13.8 / 12.8 / 36.3 / 59.9 | 4.08 / 4.69 / 4.19 / 3.80 / 3.90 | | | | |
| mini-SWE-agent LLM latency (not a tool time) | 17,963 | 5.90 | 3.37 | 11.7 | 40.1 | 1.60 | | 0% | 0.4% | 8% |

Empirical quantile table (percentiles of the uncapped series, seconds; all 99 percentiles are in `quantiles.csv` of each source):

| series | p1 | p5 | p10 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| TraceLab per turn (`round_z`) | 0 | 0.008 | 0.021 | 0.062 | 0.237 | 2.61 | 12.4 | 30.0 | 171 |
| TraceLab per call | 0 | 0.009 | 0.023 | 0.066 | 0.216 | 1.57 | 10.0 | 30.0 | 131 |
| TraceLab, Claude Code per turn | 0.003 | 0.009 | 0.018 | 0.044 | 0.118 | 1.60 | 10.0 | 41.9 | 216 |
| TraceLab, Codex per turn | 0 | 0.007 | 0.028 | 0.083 | 0.588 | 5.00 | 14.9 | 30.0 | 120 |
| mini-SWE-agent steps | 0.0411 | 0.0477 | 0.0504 | 0.0572 | 0.104 | 0.427 | 1.82 | 5.14 | 33.8 |
| Exp(5 s), current simulator | 0.0503 | 0.256 | 0.527 | 1.44 | 3.47 | 6.93 | 11.5 | 15.0 | 23.0 |

Exceedance (`exceedance.md`):

| series | P(>0.5 s) | P(>1 s) | P(>5 s) | P(>10 s) | P(>30 s) | P(>60 s) | P(>300 s) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) | 90.5% | 81.9% | 36.8% | 13.5% | 0.25% | 0 | 0 |
| TraceLab per turn | 42.6% | 37.5% | 20.1% | 13.2% | 6.6% | 3.2% | 0.54% |
| TraceLab inter-request idle | 54.6% | 51.7% | 36.7% | 25.3% | 11.1% | 5.2% | 0.85% |
| mini-SWE-agent | 22.1% | 14.6% | 5.1% | 2.9% | 1.1% | 0.56% | 0 |

Fits to the capped series (KS = Kolmogorov-Smirnov distance):

| series | lognormal MLE: mu, sigma (log s) | KS | mean-preserving lognormal: mean, CV | KS | two-component mixture | KS | Exp(5 s) KS | Exp(sample mean) KS |
|---|---|---|---|---|---|---|---|---|
| TraceLab per turn | -0.89, 2.46 | 0.090 | 8.47 s, 22.9 | 0.075 | 5.8% of turns < 10 ms; of the rest 0.42 at median 0.069 s (sigma 0.85) + 0.58 at median 2.26 s (sigma 1.99) | 0.032 | 0.480 | 0.558 |
| TraceLab, Claude per turn | -1.34, 2.49 | 0.144 | 10.1 s, 42.6 | 0.125 | 0.59 at 0.065 s (0.85) + 0.41 at 3.16 s (2.10) | 0.020 | 0.596 | 0.636 |
| TraceLab, Codex per turn | -0.52, 2.38 | 0.065 | 7.15 s, 11.3 | 0.078 | 0.29 at 0.077 s (0.84) + 0.71 at 1.97 s (1.90) | 0.066 | 0.444 | 0.505 |
| mini-SWE-agent | -1.65, 1.56 | 0.155 | 1.39 s, 5.83 | 0.173 | 0.43 at 0.058 s (sigma 0.20) + 0.57 at 0.475 s (1.52) | 0.058 | 0.692 | 0.496 |

A single lognormal is a poor description of both (KS 0.08-0.23): the real laws are two-regime. The two-component mixture reduces KS to 0.02-0.07 (BIC on the positive part of the uncapped TraceLab per-turn series, 100,000-point subsample: 455,937 for one lognormal against 435,439 for two, lower is better). The first mini-SWE-agent component sits at the sigma floor of the EM (0.2): a point mass at 58 ms, consistent with the fixed cost of a `docker exec` rather than a spread.

What the TraceLab quantiles show: three plateaus at 5, 10 and 30 s (percentiles 80-82 of the per-turn series sit at 5.00-5.02 s, 87-89 at 10.0-10.07 s, 94-95 at 30.0 s). They look like runner yield timers rather than command durations: Codex `write_stdin` calls have median 5.01 s, `exec` calls have p90 = p99 = 10.1 s, `wait` median 11.9 s. A long command therefore shows up as a chain of 5-30 s calls, each followed by a new model request. For the question the simulator asks (how long is a session idle between two requests to the server) this is the right unit, not the length of the command.

## Tokens and turns

| group | quantity | n | mean | winsorised mean (p99.9) | median | p90 | p99 | CV |
|---|---|---|---|---|---|---|---|---|
| TraceLab | first call prompt of a session (tokens) | 8,058 | 23,308 | 23,273 | 17,718 | 36,044 | 169,133 | 1.07 |
| TraceLab | first call prompt of an agentic episode | 92,024 | 206,951 | | 148,491 | 499,711 | 933,522 | 0.99 |
| TraceLab | prompt at every call | 665,453 | 171,576 | 171,566 | 132,092 | 338,662 | 856,464 | 0.93 |
| TraceLab | output tokens per call | 665,453 | 589 | 583 | 249 | 1,332 | 5,542 | 1.99 |
| TraceLab | tokens appended between calls (delta_ctx >= 0) | 565,771 | 1,268 | 1,251 | 210 | 3,243 | 15,323 | 2.65 |
| TraceLab | calls per agentic episode | 47,887 | 12.97 | | 5 | 28 | 116 | 2.53 |
| TraceLab | calls per whole session | 8,058 | 82.6 | | 16 | 145 | 1,130 | 4.95 |
| TraceLab, Claude / Codex | calls per agentic episode (mean, median) | 31,590 / 16,297 | 9.3 / 20.1 | | 3 / 9 | 20 / 41 | 91 / 183 | |
| TraceLab, Claude / Codex | tokens appended (mean, median) | | 1,124 / 1,389 | | 274 / 158 | | | |
| mini-SWE-agent | first call prompt | 500 | 1,862 | 1,862 | 1,784 | 2,604 | 3,920 | 0.35 |
| mini-SWE-agent | prompt at every call | 18,463 | 17,939 | 17,933 | 15,067 | 35,576 | 57,878 | 0.71 |
| mini-SWE-agent | output tokens per call | 18,463 | 271 | 269 | 116 | 659 | 2,110 | 1.67 |
| mini-SWE-agent | tokens appended between calls (delta_ctx >= 0) | 17,782 | 434 | 429 | 198 | 1,066 | 2,912 | 1.85 |
| mini-SWE-agent | calls per trajectory | 500 | 36.9 | 36.9 | 32 | 63 | 104 | 0.56 |
| mini-SWE-agent, per model | calls per trajectory (mean) | 100 each | opus 32.7, sonnet 49.8, gpt-5.2 35.7, gpt-5-mini 19.8, kimi 46.7 | | | | | |

Trajectory totals in mini-SWE-agent: wall time of a trajectory mean 262 s (median 222 s), of which tool time mean 50 s (median 28 s). Command time is 19% of the wall clock; most of the rest is model latency (mean 5.9 s, median 3.4 s per call).

Geometric fit: `mean_turns` such that E[min(Geometric(1/m), 60)] equals the observed mean calls per agentic episode capped at 60 (TraceLab 10.71, m = 10.74; mini-SWE-agent 34.79, m = 49.02). It matches only the mean: the real counts are far from geometric (TraceLab CV 2.5 with median 5 against mean 13; mini-SWE-agent CV 0.56, a unimodal bump around 32, against 1 for a geometric). If the shape of T matters for the thrashing curve, `turn_counts` would need a table-driven law like the one added for tool times.

## Proposed workloads

`configs/workload_trace_<source>.yaml`, each file holds complete `workload:` mappings with the field names of `prefixmeta.workload.WorkloadParams` on branch `r7/robustness` (commit 8c08883), checked by loading them through that module and sampling (`tool_time_moments` equals the written mean and CV; sampled moments agree within sampling error).

| section | tool-time law | what it carries | needs |
|---|---|---|---|
| `workload` | `lognormal`, mean = sample mean of the capped series, CV chosen to minimise KS (TraceLab 8.47 s, CV 22.9; mini 1.39 s, CV 5.83) | the mean (idle-session count by Little's law) and a heavy tail; median too high by 1.5-2.3x | round-6 code and later |
| `workload_bimodal` | `bimodal`, `tool_time_lo_s` = sample median, `tool_time_hi_s` and `tool_time_p_hi` solve the sample mean and CV exactly (TraceLab 0.237 s / 197.6 s / P(hi) 4.17%; mini 0.104 s / 29.3 s / 4.42%) | exact mean and CV, two atoms; crude | 8c08883 (`tool_time_p_hi`) |
| `workload_empirical` | `empirical`, 250-knot table, `tool_time_quantile_levels` strictly increasing 0..1 (0.5% steps, then 1-u shrinking by 2^(1/4) per knot to 1-2e-6), `tool_time_quantiles` = quantiles of the capped series; `tool_time_mean_s` / `tool_time_cv` set to the table's exact moments | the whole distribution; table mean +0.42% (TraceLab) and +0.31% (mini) against the sample mean, CV -0.10% and -0.24% | 8c08883 |
| `workload_empirical_idle_gap` (TraceLab only) | `empirical` table of the inter-request idle time, exact mean 14.5 s | upper-bound sensitivity: includes output-to-call and result-to-request overhead and human waits for permission prompts | 8c08883 |

Why the table has a dense tail: the 1st..99th percentile table alone, interpolated linearly with a point at level 0 and at level 1, overstates the mean of the TraceLab series by 8% (the slowest 1% of the capped series holds 39% of its time) and understates the mini-SWE-agent mean by 2.8%; the 250-knot grid brings both within 0.5%. The 99 percentiles themselves are in `quantiles.csv`.

The two-component mixture has no counterpart in the simulator; its fit is in the config comments and `summary.json`. The `initial_context_tokens`, `new_prompt_tokens`, `decode_tokens`, `mean_turns` fields are the means above (TraceLab 23,308 / 1,251 / 583 / 10.74; mini 1,862 / 429 / 269 / 49.02). The TraceLab section is indicative for tool times, appended tokens and turns, not for context size (see caveat 6); the mini-SWE-agent section is the one whose token profile is closest to the workload of record.

None of the sections has been run. A robustness run that keeps the workload of record's tokens and turns and swaps only the tool-time law (`workload_overrides` with `tool_time_dist: empirical` and a table) isolates the effect of objection 3.

## Caveats

1. **What the number measures.** TraceLab: client-side wall time between the tool request and the result. It contains human waits at permission prompts, background-task effects, the full run of a sub-agent for delegation tools (class `deleg`: mean 57 s, 19% above 60 s), web tools (mean 33 s), and poll/yield timers (the 5, 10, 30 s plateaus). Only the human-interaction tools (AskUserQuestion, ExitPlanMode, EnterPlanMode, request_user_input; 2,413 calls, mean 1,350 s) are removed; nothing else is filtered. Without the `deleg` and `poll` classes (`call_wall_exec_only`) the per-call mean falls from 11.3 s to 9.6 s and the capped mean from 7.1 s to 5.0 s. mini-SWE-agent: `docker exec` time in the leaderboard environment, with startup overhead of the exec (median 58 ms), on hardware that is not documented, possibly under load from parallel runs.
2. **Censoring and caps.** mini-SWE-agent: 101 steps (0.56%) hit the 60 s limit (`TimeoutExpired`) and carry 24% of the total command time; their true duration is longer, so the mean 1.39 s is a lower bound (1.06 s without them, with the tail removed). TraceLab: values above 600 s are set to 600 s in every capped statistic and fit; the raw mean is 13.6 s, so the capped table drops 38% of the raw mean (0.18% of turns). Whether those hour-long calls are tool executions or an abandoned session is not knowable from the log; for the simulator a 600 s cap means a session is gone after ten minutes.
3. **Not replays.** Both sources are first-run logs with real timing (the mini-SWE-agent runs are the published leaderboard runs, the TraceLab sessions are developers' own sessions); neither is a cached or simulated replay. There are no format-error retries in the sample (0 of 500 trajectories) and the tool-call retries inside TraceLab are indistinguishable from ordinary calls.
4. **Representativeness.** TraceLab is human-in-the-loop interactive coding (52 pseudonymous users, a selection process I did not find described; mixed 2025-2026 Claude and GPT models, mostly gpt-5.5, claude-opus-4-8 and claude-opus-4-7 by rounds); mini-SWE-agent is one fully autonomous bash-only scaffold on one benchmark (SWE-bench Verified, 100 of 500 instances, paired across 5 models). Neither is a general agent population; the tool-time law of a customer-support or browsing agent could differ. The five mini-SWE-agent models give means of 0.8-2.0 s with similar medians (0.07-0.16 s) and CV 3.8-4.7, so the shape is stable across models, the scale less so.
5. **Sampling noise of heavy tails.** With CV 22.9 the mean of a sample of 390k lognormal draws came out 4.6% above the target in a check (8.87 s against 8.47 s). Long simulations that use the `workload` lognormal section converge slowly; the empirical table is capped at 600 s and does not have this problem.
6. **Context size.** TraceLab prompts at an average call hold 172k tokens (median 132k, p99 856k) and an agentic run starts, on average, at 207k: far outside a 300k-token KV pool shared by tens of sessions, and outside Qwen2.5-7B's context. `initial_context_tokens: 23308` is the first call of a session, not the typical start of a run. The tool-time, appended-token and turn statistics of TraceLab can be used with a smaller context; its context statistics cannot be matched on the testbed.
7. **Turn counts** are not geometric (see above) and the mapping to `mean_turns` preserves only the mean.
8. **delta_ctx** includes any user text the client appends; for TraceLab this contributes where a human types between two calls of the same run (rare inside an episode, by the episode definition) and compaction events are excluded as negative deltas (1.3%).

## Open issues and ambiguities in the task

* "Tool execution time per call" is not one quantity in these sources. I used the per-turn interval (TraceLab `round_z`) as the headline because the simulator has one tool time per turn; the per-call wall time, the runner-reported internal time and the inter-request idle time are reported next to it, and they differ by up to 2x in the mean (internal 5.07 s, per call 7.13 s, per turn 8.47 s, inter-request 14.5 s, all capped). Which one the paper should call "real tool time" is a judgement; the inter-request idle time is what the KV cache sees, the per-turn value is what the task text defines.
* The task's `tool_time_dist: empirical` / `lognormal` spelling was superseded by the round-7 field names (`tool_time_quantile_levels` and explicit `tool_time_p_hi`), which I used as instructed. The empirical sampler needs strictly increasing levels from exactly 0.0 to 1.0, so a plain 1st..99th percentile list cannot be passed on its own (it would be read as 99 equally spaced levels from 0 to 1).
* No third source was added: the two used cover interactive and autonomous agents with timestamps for both model and tool events, which was the stated preference; SWE-agent, Terminal-Bench and tau-bench logs are unchecked.

## Reproduce

```
bash scripts/traces/download.sh            # results/traces_raw/tracelab_v0.0.2, results/traces_raw/mini_swe_v2, checksum-verified
bash scripts/traces/run_all.sh             # parse -> analyze -> meta -> configs -> exceedance -> tables
```

Commits (branch `r7/traces`): download/parse/analysis scripts and tests 7c793f7, 0634824; series and per-provider fits 6ea62b8; tables 236e7b9, a2138a7; KS-optimal lognormal e1a4e3e; summaries c93304f; round-7 field names 8a1e24c, 98594c2; configs d1bb4ce, 4d0d64b, a1b35c7; exceedance e6226b6. The analysis outputs in `results/traces_summary/` were produced at e1a4e3e (`meta.json` records it and the SHA-256 of the inputs); later commits changed only the config writer and the comparison script. The only randomness is the seeded subsampling of the EM fits (seed 0) and the seeded instance draw (20261024).
