# Round 7: real-trace tool times in the calibrated simulator (referee objection 3)

Branch `r7/robustness` (never pushed), written 2026-10-25. Referee objection 3: "your agent tool times are synthetic". This note re-runs the round-7 stages (`notes/ROBUSTNESS_r7.md`, step 2) on the calibrated simulator with the tool-time law replaced by the EMPIRICAL quantile tables measured on real agent traces by branch `r7/traces` (`notes/lit/AGENT_TRACES.md` there: SyFI TraceLab, Claude Code and Codex CLI sessions of 52 developers; mini-SWE-agent v2.0.0 on SWE-bench Verified). The spec `configs/r7_traces_sim.yaml` was committed (7918292) before any run. Everything declared ran in full (no seeds, workloads or arms dropped); the four stages took 44 s of recorded wall time. Three labelled post-hoc additions follow the declared results: a 20-seed fresh-seed replication of the paired stage, diagnostics of the paired arms, and a protocol-adjusted rerun of the secondary workload.

**Design.** Primary: the record workload exactly as in round 7 (first prompt 2000 tokens, +550 tool tokens and 100 output tokens per turn, T ~ min(Geometric(1/15), 60), KV pool 300000 tokens, `mixed` batching, round-6 engine block) with ONLY the tool-time law replaced by (a) the TraceLab per-turn table (mean 8.51 s, CV 4.65, median 0.237 s), (b) the TraceLab inter-request idle-gap table (mean 14.52 s, CV 3.53, an upper bound that includes model-output-to-request overhead and human waits), (c) the mini-SWE-agent table (mean 1.40 s, CV 4.29, median 0.104 s). The Exp(5 s) record workload was re-run as a control through the same code path. Same stages, seeds and rules as round 7: lambda_miss (3 seeds), closed curve on the same n grid (3 seeds), from-empty edge on the same multiple grid (10 seeds, B2 contiguous rule), paired NOBURST / BURST / CAPPED at lo + (hi - lo)/3 and lo + 2(hi - lo)/3 of the measured window (rounded to 0.05), 10 seeds, CAPPED cap = smallest n within 5% of the turns-based argmax, PASS by the >= 7/10 rule on all three arms, Wilson 95% intervals. Secondary (declared in the spec): the mini-SWE-agent FULL workload (its own turns, E[T] 34.79; +429 appended and 269 decoded tokens per turn; 1862-token first prompt; longest session 43313 tokens = 14% of the pool), same stages. The TraceLab FULL workload was NOT run: its prompts at an average call are 172k tokens (207k at the first call of an agentic run), so the 300k-token pool could not hold two such sessions and the mapped first prompt of its config (23308 tokens, the first call of a session) would not describe the traced workload; only its tool-time law is used (a, b).

**Control.** The Exp(5 s) rows are bit-identical to the round-7 record workload: lambda_miss 0.072187 sessions/s, the whole closed curve (peak n = 20, 0.2144 sessions/s), window [1, 2.0], and all 60 classified runs of the paired stage (hit, backlog, slope and token rate differ by 0.0); in the fresh-seed replication the 20 BURST runs at 1.35 x equal round 7's low-lambda stage (same seeds 100-119, same labels, differences 0.0). So every difference below is due to the tool-time law.

## Headline: per tool-time law (10 seeds per point unless stated)

| tool-time law | mean (s) / CV | lambda_miss (sessions/s) | vs Exp(5 s) | peak n | peak mu (sessions/s), x lambda_miss | cap n | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (control = round-7 record) | 5 / 1 | 0.07219 | - | 20 | 0.2144, 2.97 | 20 | [1, 2.0] | 1.35, 1.65 |
| TraceLab per-turn | 8.51 / 4.65 | 0.07315 | +1.3% | 32 | 0.2178, 2.98 | 32 | [1, 2.25] | 1.40, 1.85 |
| TraceLab idle gap (upper bound) | 14.52 / 3.53 | 0.07158 | -0.8% | 40 | 0.1694, 2.37 | 40 | [1, 2.0] | 1.35, 1.65 |
| mini-SWE-agent v2 tool time | 1.40 / 4.29 | 0.07294 | +1.0% | 24 | 0.3913, 5.37 | 20 | [1, 3.0] | 1.65, 2.35 |
| [secondary] mini-SWE-agent v2 full workload | 1.40 / 4.29 | 0.011962 (0.416 turns/s, E[T] 34.79); not converged, see 4 | n/a | 12 | 0.0503, 4.21 | 12 | [1, 3.0] | 1.65, 2.35 |

| tool-time law | x lambda_miss | BURST trapped | NOBURST good | CAPPED recovered (cap n) | PASS |
|---|---|---|---|---|---|
| Exp(5 s) (control) | 1.35 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (20) | PASS |
| Exp(5 s) (control) | 1.65 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (20) | PASS |
| TraceLab per-turn | 1.40 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (32) | **FAIL** |
| TraceLab per-turn | 1.85 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (32) | PASS |
| TraceLab idle gap | 1.35 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (40) | PASS |
| TraceLab idle gap | 1.65 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (40) | PASS |
| mini-SWE-agent v2 tool time | 1.65 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (20) | PASS |
| mini-SWE-agent v2 tool time | 2.35 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] (20) | PASS |
| [secondary] mini-SWE-agent v2 full workload | 1.65 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] (12) | PASS |
| [secondary] mini-SWE-agent v2 full workload | 2.35 | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0/10 (0.00) [0.00, 0.28] (12) | **FAIL** |

Declared rule: 8 of the 10 points PASS. The control: 2 of 2 PASS. The six points of the three primary laws: 5 PASS, 1 FAIL (TraceLab per-turn at 1.40 x). The secondary workload: 1 PASS, 1 FAIL. NOBURST was good in 10/10 seeds and CAPPED recovered in 10/10 at every point except the two points of the secondary workload (NOBURST 8/10 at 2.35 x; CAPPED 8/10 and 0/10), and 100 of 100 BURST runs were stuck (hit rate < 0.2 over the last 2500 s). Pooled over the 10 points the declared TRAPPED rule labels 87 of 100 BURST runs TRAPPED and the other 13 INDETERMINATE (stuck at hit 0 but the backlog slope falls under 0.5 (lambda - lambda_miss)); none is RECOVERED.

**1. The finding survives the real tool-time laws.** lambda_miss is a property of the server and moves by -0.8% to +1.3% against Exp(5 s) (3-seed sd 0.0015 to 0.0036; the POP 64 check is within 0.2% to 3.0% for the four primary workloads, all with GPU busy 1.00). Each primary law has a non-empty window of metastability and a closed curve that collapses to lambda_miss at large n (mu(64) = 0.0715 to 0.0726 sessions/s). At every tested point of the three primary laws the paired result has the round-7 shape: NOBURST stays in the good state (10/10), BURST is stuck at hit 0 with an all-miss token rate, CAPPED escapes (10/10 recovered). Real heavy-tailed laws with a 0.1 to 0.24 s median and a few percent of minute-long calls do not remove the trap.

**2. What does change, and how it compares with Exp(5 s).** The tool-time law moves the n at which the GPU saturates and the cache falls off its cliff, not lambda_miss: the closed-curve peak is at n = 32 (TraceLab per-turn, mean 8.5 s) and n = 40 (idle gap, mean 14.5 s) against 20 for Exp(5 s) and 20 to 24 for all five synthetic laws of round 7; the peak height is the same as Exp(5 s) for the per-turn law (2.98 vs 2.97 x lambda_miss) and lower for the idle gap (2.37 x). The CAPPED arm therefore needs cap 32 and 40, not 20, and it recovers at those caps (10/10). The window: TraceLab per-turn [1, 2.25] is one grid step wider than Exp(5 s) [1, 2.0] (10/10 stable at 2.25 x against 7/10, a difference at the level of the seed noise of a 10-seed count); the idle gap has the same edge as Exp(5 s) (2.0, and the same 7/10 at 2.25 x); the mini-SWE-agent law (mean 1.4 s) gives [1, 3.0] and a peak of 5.37 x lambda_miss, close to round 7's Exp(1 s) (3.0 and 5.25 x). Across the eight laws of the two rounds the peak height falls as the mean tool time grows (5.4 x at 1.4 s, 4.6 x at 2 s, about 3.0 x at 4.8 to 8.5 s, 2.4 x at 14.5 s); the shape (CV 3.5 to 4.7 against 1 to 2) shows no separate effect that these runs can resolve. This is an observation across eight laws, not a test.

**3. The one primary FAIL is the slope test, not the trap.** TraceLab per-turn at 1.40 x: BURST TRAPPED in 6/10 (Wilson [0.31, 0.83], below the bound 7) but all 10 runs are stuck at hit < 0.2 with an all-miss token rate; the 4 non-TRAPPED runs are INDETERMINATE (backlog slope under the 0.5 (lambda - lambda_miss) threshold), the fragility documented in round 7 section 2. Post-hoc, on 20 fresh seeds (100-119, same stage and rules, need 14 of 20; section "Fresh-seed replication" below) the same point is 17/20 TRAPPED (0.85, [0.64, 0.95]), PASS, equal to the control at 1.35 x (17/20); all 8 points of the control and the three primary laws PASS on the fresh seeds (over all 10 points, 181 of 200 BURST runs are TRAPPED and 200 of 200 stuck). The two lowest-lambda points of the longest-mean laws (per-turn 1.40 x, idle gap 1.35 x) are the two that touch the 7-of-10 bound, as expected from a slope threshold that shrinks with lambda - lambda_miss. With 10 seeds a single such point is a noisy statement; the stuck state itself is 100% in every run.

**4. Secondary: the full mini-SWE-agent workload.** Declared protocol (tables above): the window, the trap and the cap all appear (peak n = 12, BURST trapped 10/10 at both points, 1 PASS and 1 FAIL). Three properties of the declared protocol make it unsuitable for sessions this long; they are read off the finished runs and the post-hoc tables below, and none changes a declared verdict.
* (i) lambda_miss is not converged. B1's measured window (900 to 2700 s) is shorter than one session lifetime at POP 32 (32 / 0.011962 = 2675 s; the record workload's is 443 s), and the POP 64 check reads 0.016588 (+39%). With a 20 x longer window (post-hoc, same stage with `--set`: warm-up 18000 s, window [18000, 54000) s, 3 seeds) POP 32 gives 0.014093 and POP 64 0.014060 sessions/s (they agree within 0.3%), 17.8% above the declared value; the same long window gives 0.072682 for the control (+0.7%). In units of the converged lambda_miss the declared test points 1.65 x and 2.35 x are 1.40 x and 1.99 x, the peak is 3.57 x (4.21 x declared) and the declared hi = 3.0 is 2.55 x.
* (ii) The edge stage's 3000 s horizon is too short for this workload. At 2.35 x (1.99 x converged) two of the ten NOBURST runs of the 8700 s paired stage collapse by themselves, with the first window of hit < 0.2 ending at 2600 s and 4400 s (no NOBURST run of the record workload, the other primary laws or the 1.65 x point does), although the edge stage, which stops at 3000 s, calls every multiple up to 3.0 x all-stable.
* (iii) CAPPED escapes the trap (hit rate 0.96 to 0.97 and a falling backlog in 10/10 runs at both points) but has not drained the 200-session burst by the evaluation window: with a standing backlog the capped system serves mu(12) = 0.0503 sessions/s, so the burst drains in about 200 / (0.0503 - lambda) = 6.5e3 s at 1.65 x and 9.0e3 s at 2.35 x (an estimate: arithmetic on two measured numbers), against an evaluation window that starts 5000 s after the burst; the mean backlog over the window is 13.8 and 58.0 requests, the RECOVERED limit is 20.

*Protocol-adjusted rerun of the secondary (post-hoc, section below).* Same code, spec and seeds, three horizon changes via `--set`: the converged lambda_miss (long window above), the edge horizon equal to the paired-run horizon (8700 s), and paired runs of 20000 s after the burst with the last 2500 s as the evaluation window. The window becomes [1, 1.5] (10/10 stable at 1.25 x and 1.5 x; 9/10, 8/10 and 9/10 at 1.75, 2.0 and 2.25 x; 4/10 at 2.5 x), the test points 1.15 x and 1.35 x. At 1.35 x: BURST trapped 7/10, NOBURST good 10/10, CAPPED (cap 12) recovered 10/10, PASS. At 1.15 x: BURST trapped 3/10 (declared FAIL) with 10/10 stuck at hit < 0.2 (7 INDETERMINATE: the slope rule again), NOBURST 10/10, CAPPED 10/10. So for the real mini-SWE-agent workload the trap exists, the cap releases it, and the window is narrower than the declared protocol suggested ([1, 1.5] against the record workload's [1, 2.0]).

**5. Caveats (what the numbers do not say).**
* The primary design pairs real tool-time laws with the record workload's synthetic tokens and turns (550 appended, 100 decoded, geometric T with mean 14.76). It isolates the tool-time law as asked; it does not simulate TraceLab (whose contexts, 172k tokens on average, exceed the testbed pool; not run) or any other real session. The secondary uses mini-SWE-agent's own turns and tokens but a geometric turn count (the trace's is a unimodal bump around 32 turns).
* TraceLab "tool time" is the client-observed interval from tool request to result: it contains human waits at permission prompts, whole sub-agent runs of delegation tools and the 5, 10 and 30 s yield timers of the runners; values above 600 s are capped at 600 s (0.18% of the turns, 38% of the raw mean). The idle-gap table is an upper bound (mean 14.5 s). mini-SWE-agent commands are censored by the harness's 60 s limit (0.56% of the steps, 24% of the time), so its mean is a lower bound. See `notes/lit/AGENT_TRACES.md` on `r7/traces`.
* The tables are 250-knot quantile tables with linear interpolation (table mean +0.42%, +0.47% and +0.31% against the sample means; the simulator uses the exact table moments printed below).
* Ten seeds per point: fractions near 0.6 to 0.8 have Wilson intervals of width 0.3 to 0.5. The closed-curve peak and cap come from 3 seeds on the declared grid (steps of 4 from 8 to 32, then 40, 48, 64, 96 and 300), so a peak of n = 32 or 40 is known to about one grid step.
* Only the stages of step 2 were run on the traces; the burst-size, horizon and low-lambda stages (steps 3 to 5) were not, `separate_prefill_priority` was not used, and no per-provider TraceLab subset (Claude Code only, Codex CLI only) was run.

**Interpretation choices (the lead's to overrule; all declared in `configs/r7_traces_sim.yaml`).** The Exp(5 s) control was added to the spec so that the comparison runs through one code path. The TraceLab per-turn series is the headline TraceLab law (the unit the simulator uses: one tool time per turn); the idle gap is reported next to it as the upper bound, as the trace study recommends. The window rule, test points, seeds and caps are those of round 7 and were not changed after the first run for any workload, including the secondary one; the protocol-adjusted rerun of the secondary is a separate, labelled run.

**Files.** Spec `configs/r7_traces_sim.yaml`; trace configs `configs/workload_trace_tracelab.yaml`, `configs/workload_trace_mini_swe_v2.yaml` (byte copies from `r7/traces`, tip 1556630e864a7f54f6e20e3b00d17283f570dd0f; sha256 c59c7fda33d146b9f1f9dbc8017f9c885b0a89d7fbe28661f7f60df4c2d476e0 and cf0f43f6a7754ae55a8a12e089392bb4e7b86131164003a481ac1c8febfba459); runner `experiments/r7_traces_sim_run.sh`; code `src/prefixmeta/r7_posthoc.py` and the opt-in keys (per-workload `expected_turns`, `r7.stages`, `r7.title`, effective-value captions) in `src/prefixmeta/r7_robustness.py` and `src/prefixmeta/r7_report.py`, which behave as before for `configs/r7_robustness.yaml`; tests `tests/test_r7_traces_sim.py`; results `results/r7_traces_sim/` (declared run, report, post-hoc), `results/r7_traces_sim_ext/` (fresh seeds), `results/r7_traces_sim_lmcheck/` and `results/r7_traces_sim_adj/` (secondary, adjusted); summaries force-added, the large `windows.csv` files are not.

## Provenance: what was run

Generated by `python -m prefixmeta.r7_report assemble` from the report `results/r7_traces_sim/r7_report/20261025-012451` (the tables below are that report's `tables.md`, verbatim; nothing is retyped).

Spec: `configs/r7_traces_sim.yaml` (sha256 `b1619c0618b6331fa94bc23708d4be8b2279f8c073400430488e0f92d92b0c4b`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim/r7_lambda_miss/20261025-011208 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:07 | 5.7 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim/r7_edge/20261025-011223 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:23 | 10.1 | True |
| pairs | results/r7_traces_sim/r7_pairs/20261025-011234 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:34 | 21.1 | True |

Total recorded stage wall time: 44 s (0.7 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
```

## Tables (generated)

### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [900, 2700) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | E[T] (turns per session) | lambda_miss x E[T] (turns/s) | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 14.761 | 1.0656 | 0.071986 | 1 |
| TraceLab per-turn (empirical) | 8.5099 | 4.6533 | 0.073153 | 0.0036179 | 0.07037 | 11248 | 1 | 14.761 | 1.0798 | 0.073266 | 1 |
| TraceLab idle gap (empirical, upper bound) | 14.523 | 3.5296 | 0.071585 | 0.0020638 | 0.068333 | 11018 | 0.99997 | 14.761 | 1.0567 | 0.07373 | 1 |
| mini-SWE-agent v2 tool time (empirical) | 1.3982 | 4.2923 | 0.07294 | 0.0014784 | 0.070556 | 11292 | 1 | 14.761 | 1.0767 | 0.072262 | 1 |
| mini-SWE-agent v2 full workload (empirical) | 1.3982 | 4.2923 | 0.011962 | 0.00022187 | 0.0088889 | 8894.1 | 1 | 34.787 | 0.41611 | 0.016588 | 1 |

### 2. Closed curve mu(n) (cache on, seeds 0-2) and the cap

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record, control) | TraceLab per-turn (empirical) | TraceLab idle gap (empirical, upper bound) | mini-SWE-agent v2 tool time (empirical) | mini-SWE-agent v2 full workload (empirical) |
|---|---|---|---|---|---|
| 8 | 0.0905 / 0.93 | 0.0581 / 0.93 | 0.0340 / 0.93 | 0.1928 / 0.93 | 0.0406 / 0.97 |
| 12 | 0.1341 / 0.93 | 0.0880 / 0.93 | 0.0534 / 0.93 | 0.2638 / 0.93 | 0.0503 / 0.96 |
| 16 | 0.1759 / 0.93 | 0.1148 / 0.93 | 0.0701 / 0.93 | 0.3285 / 0.93 | 0.0274 / 0.70 |
| 20 | 0.2144 / 0.93 | 0.1387 / 0.93 | 0.0903 / 0.93 | 0.3802 / 0.93 | 0.0173 / 0.35 |
| 24 | 0.2130 / 0.88 | 0.1672 / 0.93 | 0.1079 / 0.93 | 0.3913 / 0.92 | 0.0134 / 0.15 |
| 28 | 0.1772 / 0.77 | 0.1944 / 0.93 | 0.1252 / 0.92 | 0.2206 / 0.77 | 0.0107 / 0.00 |
| 32 | 0.1226 / 0.52 | 0.2178 / 0.92 | 0.1404 / 0.92 | 0.1179 / 0.40 | 0.0113 / 0.00 |
| 40 | 0.0733 / 0.03 | 0.1982 / 0.73 | 0.1694 / 0.88 | 0.0720 / 0.00 | 0.0127 / 0.00 |
| 48 | 0.0714 / 0.00 | 0.1002 / 0.23 | 0.1259 / 0.55 | 0.0721 / 0.00 | 0.0140 / 0.00 |
| 64 | 0.0715 / 0.00 | 0.0726 / 0.00 | 0.0715 / 0.00 | 0.0720 / 0.00 | 0.0163 / 0.00 |
| 96 | 0.0758 / 0.00 | 0.0763 / 0.00 | 0.0765 / 0.00 | 0.0758 / 0.00 | 0.0203 / 0.00 |
| 300 | 0.1112 / 0.00 | 0.1116 / 0.00 | 0.1120 / 0.00 | 0.1114 / 0.00 | 0.0354 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 20 | 0.2144 | 20 | 0.5186 | 0 | 20 | 0.2126 | 20 |
| TraceLab per-turn (empirical) | 32 | 0.2178 | 32 | 0.5125 | 0 | 32 | 0.2183 | 32 |
| TraceLab idle gap (empirical, upper bound) | 40 | 0.1694 | 40 | 0.6612 | 0 | 40 | 0.1693 | 40 |
| mini-SWE-agent v2 tool time (empirical) | 24 | 0.3913 | 20 | 0.2846 | 0 | 24 | 0.3883 | 20 |
| mini-SWE-agent v2 full workload (empirical) | 12 | 0.05035 | 12 | 0.704 | 0 | 12 | 0.0513 | 12 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record, control) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record, control) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record, control) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record, control) | 2.25 | 0.1624 | 7/10 (0.70) [0.40, 0.89] | False | 10.5 | 78 | 9.203 | 0.7995 | 0 |
| Exp(5 s) (record, control) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record, control) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |
| Exp(5 s) (record, control) | 3.5 | 0.2527 | 0/10 (0.00) [0.00, 0.28] | False | 292.4 | 361 | 188.3 | 0.06604 | 0 |
| TraceLab per-turn (empirical) | 1.25 | 0.09144 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002288 | 0.9308 | 0 |
| TraceLab per-turn (empirical) | 1.5 | 0.1097 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.002298 | 0.93 | 0 |
| TraceLab per-turn (empirical) | 1.75 | 0.128 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0141 | 0.9282 | 0 |
| TraceLab per-turn (empirical) | 2 | 0.1463 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00265 | 0.9276 | 0 |
| TraceLab per-turn (empirical) | 2.25 | 0.1646 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.003882 | 0.9244 | 0 |
| TraceLab per-turn (empirical) | 2.5 | 0.1829 | 8/10 (0.80) [0.49, 0.94] | False | 20.5 | 144 | 18.7 | 0.7942 | 0 |
| TraceLab per-turn (empirical) | 3 | 0.2195 | 5/10 (0.50) [0.24, 0.76] | False | 83.1 | 246 | 70.53 | 0.5282 | 0 |
| TraceLab per-turn (empirical) | 3.5 | 0.256 | 2/10 (0.20) [0.06, 0.51] | False | 173 | 314 | 133.8 | 0.3331 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.25 | 0.08948 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.003263 | 0.9289 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.5 | 0.1074 | 10/10 (1.00) [0.72, 1.00] | True | 0.1 | 1 | 0.002057 | 0.9216 | 0 |
| TraceLab idle gap (empirical, upper bound) | 1.75 | 0.1253 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.02342 | 0.9146 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2 | 0.1432 | 10/10 (1.00) [0.72, 1.00] | True | 0.5 | 5 | 0.3725 | 0.8963 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2.25 | 0.1611 | 7/10 (0.70) [0.40, 0.89] | False | 27.8 | 114 | 23.12 | 0.6725 | 0 |
| TraceLab idle gap (empirical, upper bound) | 2.5 | 0.179 | 4/10 (0.40) [0.17, 0.69] | False | 63.5 | 156 | 51.08 | 0.5005 | 0 |
| TraceLab idle gap (empirical, upper bound) | 3 | 0.2148 | 1/10 (0.10) [0.02, 0.40] | False | 176.2 | 251 | 133.5 | 0.09072 | 0 |
| TraceLab idle gap (empirical, upper bound) | 3.5 | 0.2505 | 0/10 (0.00) [0.00, 0.28] | False | 290.7 | 345 | 197.2 | 0 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.25 | 0.09117 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.001808 | 0.9306 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.5 | 0.1094 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001299 | 0.9297 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 1.75 | 0.1276 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002736 | 0.9295 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2 | 0.1459 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006165 | 0.931 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2.25 | 0.1641 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.006351 | 0.9319 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 2.5 | 0.1823 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.001891 | 0.9327 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 3 | 0.2188 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00479 | 0.9324 | 0 |
| mini-SWE-agent v2 tool time (empirical) | 3.5 | 0.2553 | 9/10 (0.90) [0.60, 0.98] | False | 27.1 | 271 | 15.36 | 0.8385 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.25 | 0.01495 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001371 | 0.9701 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.5 | 0.01794 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002028 | 0.9704 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.75 | 0.02093 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0008958 | 0.9702 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2 | 0.02392 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006773 | 0.9705 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.25 | 0.02691 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.01228 | 0.9702 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.5 | 0.0299 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002682 | 0.9714 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3 | 0.03589 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.004188 | 0.9707 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3.5 | 0.04187 | 7/10 (0.70) [0.40, 0.89] | False | 8.3 | 36 | 8.979 | 0.7607 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| TraceLab per-turn (empirical) | 0.073153 | 2.25 | 2.25 | True | False | [1, 2.25] | 1.4, 1.85 |
| TraceLab idle gap (empirical, upper bound) | 0.071585 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |
| mini-SWE-agent v2 tool time (empirical) | 0.07294 | 3 | 3 | True | False | [1, 3] | 1.65, 2.35 |
| mini-SWE-agent v2 full workload (empirical) | 0.011962 | 3 | 3 | True | False | [1, 3] | 1.65, 2.35 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | 0.09745 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| Exp(5 s) (record, control) | 1.65 | 0.1191 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| TraceLab per-turn (empirical) | 1.4 | 0.1024 | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | FAIL | 10/10 (1.00) [0.72, 1.00] |
| TraceLab per-turn (empirical) | 1.85 | 0.1353 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.35 | 0.09664 | 40 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.65 | 0.1181 | 40 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | 0.1204 | 20 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | 0.1714 | 20 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | 0.01974 | 12 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | PASS | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 0.02811 | 12 | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0/10 (0.00) [0.00, 0.28] | FAIL | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9307 | 0.01067 |
| Exp(5 s) (record, control) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9313 | 0.01506 |
| TraceLab per-turn (empirical) | 1.4 | ITTTIITTTI | RRRRRRRRRR | RRRRRRRRRR | 4 | 0 | 0 | 0 | 0.9311 | 0.01183 |
| TraceLab per-turn (empirical) | 1.85 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9304 | 0.02158 |
| TraceLab idle gap (empirical, upper bound) | 1.35 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9271 | 0.01673 |
| TraceLab idle gap (empirical, upper bound) | 1.65 | TTTTTITTTI | RRRRRRRRRR | RRRRRRRRRR | 2 | 0 | 0 | 0 | 0.9225 | 0.02856 |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR | 1 | 0 | 0 | 0 | 0.931 | 0.01629 |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9327 | 0.02991 |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | TTTTTTTTTT | RRRRRRRRRR | RRRRROORRR | 0 | 0 | 0 | 0 | 0.9718 | 0.005414 |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | TTTTTTTTTT | RRTRRTRRRR | OOOOOOOOOO | 0 | 0 | 2 | 0 | 0.7761 | 10.52 |

### 5. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (5 workloads, 10 points, seeds 0-9) | 100 | 87/100 (0.87) [0.79, 0.92] | 13/100 (0.13) [0.08, 0.21] | 0/100 (0.00) [0.00, 0.04] | 0/100 (0.00) [0.00, 0.04] | 100/100 (1.00) [0.96, 1.00] |
| pairs, record workload only (1.35 and 1.65 x, seeds 0-9) | 20 | 18/20 (0.90) [0.70, 0.97] | 2/20 (0.10) [0.03, 0.30] | 0/20 (0.00) [0.00, 0.16] | 0/20 (0.00) [0.00, 0.16] | 20/20 (1.00) [0.84, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |

## Post-hoc diagnostics of the paired arms (generated by `python -m prefixmeta.r7_posthoc`; not part of the declared verdicts)

Result dir `results/r7_traces_sim/r7_posthoc/20261025-012454` (commit `2a25e69f9`, dirty False); reads the stage dirs of the declared run. The drain-time column is arithmetic on two measured numbers (burst size / (mu(cap) - lambda)), not a simulation.

### P1. CAPPED and NOBURST arms beyond the declared test (POST-HOC, not part of the verdicts)

The estimate column is arithmetic on two measured numbers (see the module docstring), not a simulation. `CAPPED hit > 0.8` ignores the backlog condition of RECOVERED; the declared verdict is the `recovered (declared)` columns.

| workload | x lambda_miss | lambda (sessions/s) | cap n | mu(cap) (sessions/s) | [estimate] drain time of the burst (s) | [estimate] / eval window start (5000 s) | CAPPED recovered (declared) | CAPPED hit > 0.8 (hit only) | CAPPED hit (mean) | CAPPED backlog (mean over seeds) | CAPPED backlog slope < 0 | NOBURST recovered (declared) | NOBURST trapped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | 0.09745 | 20 | 0.2144 | 1710 | 0.3421 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9307 | 0.0184 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| Exp(5 s) (record, control) | 1.65 | 0.1191 | 20 | 0.2144 | 2099 | 0.4198 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9313 | 0.01706 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab per-turn (empirical) | 1.4 | 0.1024 | 32 | 0.2178 | 1733 | 0.3466 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9311 | 0.01183 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab per-turn (empirical) | 1.85 | 0.1353 | 32 | 0.2178 | 2424 | 0.4849 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9304 | 0.05485 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab idle gap (empirical, upper bound) | 1.35 | 0.09664 | 40 | 0.1694 | 2751 | 0.5501 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9271 | 0.01639 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab idle gap (empirical, upper bound) | 1.65 | 0.1181 | 40 | 0.1694 | 3903 | 0.7807 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9223 | 0.03218 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | 0.1204 | 20 | 0.3802 | 769.6 | 0.1539 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.931 | 0.01629 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | 0.1714 | 20 | 0.3802 | 957.8 | 0.1916 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9327 | 0.02991 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | 0.01974 | 12 | 0.05035 | 6533 | 1.307 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0.9692 | 13.81 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 0.02811 | 12 | 0.05035 | 8993 | 1.799 | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0.963 | 58.03 | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 2/10 (0.20) [0.06, 0.51] |

### P2. NOBURST runs that are not RECOVERED (POST-HOC): when did they collapse? (edge stage horizon 3000 s, paired runs 8700 s)

| workload | x lambda_miss | seed | label | first window with backlog > 50 ends (s) | first window after t_burst with hit < 0.2 ends (s) | final backlog | final hit |
|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 2 | TRAPPED | 6200 | 2600 | 96.98 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 5 | TRAPPED | n/a | 4400 | 40.13 | 0 |


## Fresh-seed replication of the paired stage (post-hoc: seeds 100-119, 20 per arm, the same spec, caps and rules; PASS needs 14 of 20)

Same stage, same lambda_miss, curve and edge results as the declared run (their result dirs are in the manifest of `results/r7_traces_sim_ext/`), only `r7.pairs.seeds` overridden with `--set`. Table 4 below is that report's table; table 5 pools all 200 BURST runs.

### 4. Paired-arm test at the two window points (20 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 14) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | 0.09745 | 20 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| Exp(5 s) (record, control) | 1.65 | 0.1191 | 20 | 18/20 (0.90) [0.70, 0.97] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab per-turn (empirical) | 1.4 | 0.1024 | 32 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab per-turn (empirical) | 1.85 | 0.1353 | 32 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.35 | 0.09664 | 40 | 17/20 (0.85) [0.64, 0.95] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| TraceLab idle gap (empirical, upper bound) | 1.65 | 0.1181 | 40 | 16/20 (0.80) [0.58, 0.92] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | 0.1204 | 20 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | 0.1714 | 20 | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | 20/20 (1.00) [0.84, 1.00] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | 0.01974 | 12 | 19/20 (0.95) [0.76, 0.99] | 20/20 (1.00) [0.84, 1.00] | 14/20 (0.70) [0.48, 0.85] | PASS | 20/20 (1.00) [0.84, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 0.02811 | 12 | 19/20 (0.95) [0.76, 0.99] | 18/20 (0.90) [0.70, 0.97] | 2/20 (0.10) [0.03, 0.30] | FAIL | 20/20 (1.00) [0.84, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | TTTTTTTTTITTTTTTTITI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9324 | 0.01083 |
| Exp(5 s) (record, control) | 1.65 | TTTTTTTITITTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 2 | 0 | 0 | 0 | 0.9319 | 0.01488 |
| TraceLab per-turn (empirical) | 1.4 | TITTTTTTTITTTTTTTTTI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9316 | 0.0119 |
| TraceLab per-turn (empirical) | 1.85 | TTTTTTTTTTTTTTTTTITT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9308 | 0.02268 |
| TraceLab idle gap (empirical, upper bound) | 1.35 | TTTTTTTTIITTTTTTTITT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9279 | 0.01557 |
| TraceLab idle gap (empirical, upper bound) | 1.65 | ITTTTTTTTITTTTTTTITI | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 4 | 0 | 0 | 0 | 0.9216 | 0.03035 |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | TTTTTTTTTITTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 1 | 0 | 0 | 0 | 0.9321 | 0.01616 |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | TTTTTTTTTTTTTTTTTTTT | RRRRRRRRRRRRRRRRRRRR | RRRRRRRRRRRRRRRRRRRR | 0 | 0 | 0 | 0 | 0.9326 | 0.02973 |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | TTTTTTTTTTTTTTTITTTT | RRRRRRRRRRRRRRRRRRRR | ORRRRRRRORORRRRROORO | 1 | 0 | 0 | 0 | 0.9711 | 0.004959 |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | TTTTTTTTTTTTTTTITTTT | RRRRRRRRRRRRRRRRRTOR | OOROOOOOOOOOROOOOOOO | 1 | 0 | 1 | 0 | 0.8944 | 4.197 |

### 5. Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED

Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:

| source | BURST runs | TRAPPED | INDETERMINATE | RECOVERED | OTHER | hit < 0.2 |
|---|---|---|---|---|---|---|
| pairs, all test points (5 workloads, 10 points, seeds 100-119) | 200 | 181/200 (0.91) [0.86, 0.94] | 19/200 (0.10) [0.06, 0.14] | 0/200 (0.00) [0.00, 0.02] | 0/200 (0.00) [0.00, 0.02] | 200/200 (1.00) [0.98, 1.00] |
| pairs, record workload only (1.35 and 1.65 x, seeds 100-119) | 40 | 35/40 (0.88) [0.74, 0.95] | 5/40 (0.12) [0.05, 0.26] | 0/40 (0.00) [0.00, 0.09] | 0/40 (0.00) [0.00, 0.09] | 40/40 (1.00) [0.91, 1.00] |

Binomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the first column (exact arithmetic, not a simulation):

| true per-run probability that the declared rule labels a stuck run TRAPPED | P(at least 7 of 10 seeds TRAPPED) |
|---|---|
| 0.600 | 0.382 |
| 0.700 | 0.650 |
| 0.800 | 0.879 |
| 0.900 | 0.987 |
| 0.950 | 0.999 |
| 1.000 | 1.000 |

Provenance of that report:

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim/r7_lambda_miss/20261025-011208 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:07 | 5.7 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim/r7_edge/20261025-011223 | c515f0c1e | False | 0..9 (10) | 2026-10-25T01:12:23 | 10.1 | True |
| pairs | results/r7_traces_sim_ext/r7_pairs/20261025-011657 | a83bdde4f | False | 100..119 (20) | 2026-10-25T01:16:57 | 28.8 | True |

Total recorded stage wall time: 52 s (0.9 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_ext --workers 6 --set r7.pairs.seeds=[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]
```


## Protocol-adjusted rerun of the secondary workload (post-hoc: converged lambda_miss, edge horizon = paired-run horizon, paired runs of 20000 s after the burst)

Only `mini_full` (and the Exp(5 s) control in the lambda_miss table) was run. Changes against the declared protocol, all through `--set` (recorded in each `meta.json`): `r7.lambda_miss.warmup_s=18000`, `r7.lambda_miss.horizon_s=54000` (window [18000, 54000) s, 20 x the declared one, 3 seeds, POP 32 and POP 64); `r7.edge.horizon_s=8700` (= the paired-run horizon of the declared run); `r7.pairs.after_s=20000` with `r7.classify.eval_window_rel_to_burst_s=[17500, 20000]` (the last 2500 s after the burst, as before). Seeds, grids, cap (12, from the declared curve stage), burst size, thresholds and the PASS rule are unchanged. The curve section of this report is the declared one.

### 1. Workloads and lambda_miss (B1: cache off, closed POP 32, window [18000, 54000) s)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | E[T] (turns per session) | lambda_miss x E[T] (turns/s) | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 5 | 1 | 0.072682 | 0.0010673 | 0.072722 | 11208 | 0.99998 | 14.761 | 1.0729 | 0.073106 | 1 |
| mini-SWE-agent v2 full workload (empirical) | 1.3982 | 4.2923 | 0.014093 | 0.00020632 | 0.013991 | 8958.8 | 1 | 34.787 | 0.49026 | 0.01406 | 1 |

### 3. From-empty stability edge and the measured window

Stable runs per multiple of the workload's own lambda_miss (from empty, 8700 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.25 | 0.01762 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.00172 | 0.972 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.5 | 0.02114 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0008639 | 0.9709 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 1.75 | 0.02466 | 9/10 (0.90) [0.60, 0.98] | False | 7 | 70 | 2.709 | 0.8737 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2 | 0.02819 | 8/10 (0.80) [0.49, 0.94] | False | 13.8 | 96 | 4.408 | 0.7761 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.25 | 0.03171 | 9/10 (0.90) [0.60, 0.98] | False | 11.6 | 116 | 2.693 | 0.8719 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.5 | 0.03523 | 4/10 (0.40) [0.17, 0.69] | False | 55.2 | 141 | 18.11 | 0.3877 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3 | 0.04228 | 3/10 (0.30) [0.11, 0.60] | False | 109.1 | 202 | 26.88 | 0.3309 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 3.5 | 0.04933 | 0/10 (0.00) [0.00, 0.28] | False | 218.3 | 276 | 51.67 | 0 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 0.014093 | 1.5 | 1.5 | True | False | [1, 1.5] | 1.15, 1.35 |

### 4. Paired-arm test at the two window points (10 seeds)

Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds (the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):

| workload | x lambda_miss | lambda (sessions/s) | cap n | BURST trapped | NOBURST good | CAPPED recovered | PASS (need 7) | [sensitivity] BURST stuck (hit < 0.2) |
|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.15 | 0.01621 | 12 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | FAIL | 10/10 (1.00) [0.72, 1.00] |
| mini-SWE-agent v2 full workload (empirical) | 1.35 | 0.01903 | 12 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | PASS | 10/10 (1.00) [0.72, 1.00] |

Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:

| workload | x lambda_miss | BURST | NOBURST | CAPPED | BURST indeterminate | BURST recovered | NOBURST trapped | CAPPED trapped | NOBURST hit (mean) | NOBURST backlog (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 1.15 | TITIIITIII | RRRRRRRRRR | RRRRRRRRRR | 7 | 0 | 0 | 0 | 0.9709 | 0.003858 |
| mini-SWE-agent v2 full workload (empirical) | 1.35 | TITTITTTTI | RRRRRRRRRR | RRRRRRRRRR | 3 | 0 | 0 | 0 | 0.9724 | 0.00527 |

Provenance of that report:

| stage | result dir | commit | dirty | seeds | start | wall s | spec identical to the committed file |
|---|---|---|---|---|---|---|---|
| lambda_miss | results/r7_traces_sim_lmcheck/r7_lambda_miss/20261025-012241 | 85f739837 | False | 0..2 (3) | 2026-10-25T01:22:41 | 3.3 | True |
| curves | results/r7_traces_sim/r7_curves/20261025-011214 | c515f0c1e | False | 0..2 (3) | 2026-10-25T01:12:14 | 7.5 | True |
| edge | results/r7_traces_sim_adj/r7_edge/20261025-012331 | 85f739837 | False | 0..9 (10) | 2026-10-25T01:23:31 | 2.6 | True |
| pairs | results/r7_traces_sim_adj/r7_pairs/20261025-012341 | 85f739837 | False | 0..9 (10) | 2026-10-25T01:23:41 | 4.7 | True |

Total recorded stage wall time: 18 s (0.3 min).

Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_lmcheck --workers 6 --only exp5 mini_full --set r7.lambda_miss.warmup_s=18000.0 --set r7.lambda_miss.horizon_s=54000.0
experiments/r7_robustness_run.py curves --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --workers 6
experiments/r7_robustness_run.py edge --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full --set r7.edge.horizon_s=8700.0
experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full --set r7.pairs.after_s=20000.0 --set r7.classify.eval_window_rel_to_burst_s=[17500.0, 20000.0]
```


## Reproduce

All commands from the worktree root, run from a clean committed tree (every `meta.json` records commit and dirty flag). At most 6 worker processes. `PY` = `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`.

```
# declared run: lambda_miss, curves, edge, pairs, report (log logs/r7_traces_sim_run.log, 49 s)
bash experiments/r7_traces_sim_run.sh
# the report and the post-hoc tables are pure functions of the stage dirs; regenerated at the final commit
PYTHONPATH="src;." "$PY" -m prefixmeta.r7_report report --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim
PYTHONPATH="src;." "$PY" -m prefixmeta.r7_posthoc --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim
# the notes file
PYTHONPATH="src;." "$PY" -m prefixmeta.r7_report assemble --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim --headline <headline.md> --notes notes/ROBUSTNESS_r7_traces.md

# fresh seeds (results/r7_traces_sim_ext/r7_robustness/manifest.tsv = the first three rows of the declared manifest)
"$PY" experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_ext --workers 6 \
    --set "r7.pairs.seeds=[100,101,...,119]"
PYTHONPATH="src;." "$PY" -m prefixmeta.r7_report report --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_ext --set "r7.pairs.seeds=[100,...,119]"

# secondary, adjusted protocol (results/r7_traces_sim_adj/r7_robustness/manifest.tsv = lambda_miss from the long-window run + the declared curves row)
"$PY" experiments/r7_robustness_run.py lambda_miss --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_lmcheck --workers 6 --only exp5 mini_full \
    --set r7.lambda_miss.warmup_s=18000.0 --set r7.lambda_miss.horizon_s=54000.0
"$PY" experiments/r7_robustness_run.py edge  --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full --set r7.edge.horizon_s=8700.0
"$PY" experiments/r7_robustness_run.py pairs --spec configs/r7_traces_sim.yaml --out-root results/r7_traces_sim_adj --workers 6 --only mini_full \
    --set r7.pairs.after_s=20000.0 --set "r7.classify.eval_window_rel_to_burst_s=[17500.0, 20000.0]"
```

Seeds: lambda_miss and curves 0-2; edge and pairs 0-9 (declared); 100-119 (fresh seeds). Spec sha256 `b1619c0618b6331fa94bc23708d4be8b2279f8c073400430488e0f92d92b0c4b` (the file the declared run used, committed in 7918292 before any run; unchanged since). Trace configs: `configs/workload_trace_tracelab.yaml` sha256 `c59c7fda33d146b9f1f9dbc8017f9c885b0a89d7fbe28661f7f60df4c2d476e0`, `configs/workload_trace_mini_swe_v2.yaml` sha256 `cf0f43f6a7754ae55a8a12e089392bb4e7b86131164003a481ac1c8febfba459` (byte copies of the files on `r7/traces`, tip `1556630e864a7f54f6e20e3b00d17283f570dd0f`; branch not merged).

Commits on `r7/robustness` (never pushed): `ca165a0` trace configs copied from `r7/traces`; `beb2717` optional `expected_turns`, `r7.stages`, `r7.title` in the driver and report; `7918292` the declared spec and its test (before any run); `c515f0c` the runner script (the commit of the declared stage runs); `a83bdde` post-hoc module (the commit of the fresh-seed replication); `85f7398` report title from the effective seed count (the commit of the long-window lambda_miss check and of the adjusted edge and pairs runs); `2a25e69` effective-value captions (the commit of the final reports, the post-hoc tables and this file's tables); the commit of this file and of the force-added summaries follows.

Wall time (recorded in the `meta.json` files): declared run 44 s (lambda_miss 5.7, curves 7.5, edge 10.1, pairs 21.1); fresh-seed pairs 28.8 s; long-window lambda_miss 3.3 s; adjusted edge 2.6 s and pairs 4.7 s.

Tests (Windows PC, `PYTHONPATH="src;." "$PY" -m pytest -p no:cacheprovider -rA <files>`): `tests/test_r7_robustness.py` 17 passed, `tests/test_r7_traces_sim.py` 12 passed (new), `tests/test_r7_workload.py` 20 passed: 49 passed, 0 failed. They pin the inlined tables to the two trace configs value for value, everything else of the spec to `configs/r7_robustness.yaml`, the per-workload E[T] assertion, the refusal of undeclared stages, and run every stage, the report, the post-hoc tables and `assemble` end to end on a tiny scaled-down copy of the real spec (with an empty window and a workload of different E[T]); the original spec's report keeps its eight sections and its provenance text. Full suite at code commit `2a25e69`: 1100 collected, 1066 passed, 32 failed, 2 skipped. The same suite before any code change of this work (run at `ca165a0`, 1088 tests): 1053 passed, 33 failed, 2 skipped. All 32 failures are in the platform families that `CLAUDE.md` lists for this machine, none in an r7 test: 12 `tests/test_batching.py` and 6 `tests/test_r5_engine.py` bit-identity tests (the last-bit OLS slope; `CLAUDE.md` lists 13 for batching, 12 failed here), 5 agentload tests, 1 `tests/test_mech_runner.py`, and 8 `tests/test_slurm_scripts.py` (the 5 mock-server cases plus `test_cap_and_burst_refuse_hardware_that_differs_from_the_calibration`, `test_burst_refuses_to_start_without_a_valid_prereg` and `test_a_flush_that_answers_200_but_does_not_empty_the_cache_is_caught`, which fail in both runs with the hardware-string and path messages of the job glue (calibration `Apple M3 Max` against this machine's GPU); these three are not in that list of 31 and were not investigated). The one baseline failure that is absent from the final run is `tests/test_analysis_pipeline.py::test_stable_cli` (a real-time mock fixture, in the same list), which passed this time. No file under `src/` other than `r7_robustness.py`, `r7_report.py` and the new `r7_posthoc.py` changed; `tests/test_r7_workload.py::test_earlier_workloads_are_bit_identical_to_round6` (5 cases) passes, and the Exp(5 s) control reproduces round 7 bit for bit, so the simulator's golden digests are untouched.
