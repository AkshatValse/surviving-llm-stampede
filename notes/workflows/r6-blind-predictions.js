export const meta = {
  name: 'r6-blind-predictions',
  description: 'Round 6: finish the SGLang-faithful separate-batching simulator mode, validate the timing-calibrated simulator against Stage C out of sample, then write BLIND predictions for E0b and E2 before those real results are read; independent verification and leak check',
  phases: [
    { title: 'Port', detail: 'finish wip/r6-separate-batching on a new branch from main; full test suite' },
    { title: 'Validate', detail: 'calibrated simulator vs real Stage C mu(n) and hit, both batching modes' },
    { title: 'Predict', detail: 'B1-B4 predictions on a dense absolute-lambda grid; notes/PREDICTIONS.md' },
    { title: 'Verify', detail: 'independent re-run of a subset; leak check' },
  ],
}

const RULES = `
HARD RULES (blindness; violating them invalidates the whole round):
- You work in an isolated git worktree checked out from main at bf20ed4. Stay inside it. Do NOT cd to or read anything under /Users/akshat/research/jannesari-swapp (the main checkout) and do not read any directory named results/nova/e0a_* anywhere.
- NEVER run ssh, scp, rsync, squeue, sacct, or anything that touches the Nova cluster.
- Allowed real data: ONLY results/nova/stageC_1706210x_pulled_20261022-125454/ and results/nova/s0_smoke_17060165_pulled_20261021-152347/ (Stage 0 and Stage C), plus calibration/round6_server_log_fit/ (timing fit from server logs). The E0a, E0b and E2 real results are forbidden; if you ever see numbers for them, stop and report.
- Do not read notes/LOG.md entries dated 2026-10-23 or later.
- Commit on the branch you are told to, with NO AI attribution trailer (no Co-Authored-By, no "Generated with"). Never push. Never touch main.
- Reproducibility: explicit seeds everywhere, configs in YAML, outputs under results/<name>/<timestamp>/ with meta.json recording commit, seed and config. Report what you ran and what you observed; never guess a number.
- Local machine: Apple M3 Max, 48 GB; keep peak memory under 20 GB and total CPU time reasonable (use multiprocessing with at most 8 workers). Python: /opt/anaconda3/bin/python (NumPy 1.26, pandas 2.2, Numba 0.60). No PyTorch.
`

const DESIGN = `
DESIGN (fixed on 2026-10-22, see notes/LOG.md entry "round 6 launched" and calibration/round6_server_log_fit/CALIBRATION_REPORT.md):
The simulator in src/prefixmeta/ models a continuous-batching LLM engine with prefix caching. calibration/round6_server_log_fit/calibration.yaml holds iteration-time constants fitted ONLY from SGLang server-log timing (not from mu(n)). SGLang 0.5.22 runs prefill and decode as separate iterations with prefill priority (enable_mixed_chunk=False); the simulator's default mode mixes them. Round 6 adds a separate-batching mode (branch wip/r6-separate-batching holds an UNREVIEWED, interrupted implementation: src/prefixmeta/engine.py +191, src/prefixmeta/probe.py +444, src/prefixmeta/mech_runner.py +3, tests; that branch was cut before the harness merge, so take only its src/prefixmeta and tests/test_r5_engine.py changes and apply them onto main). The default mixed mode must stay bit-identical (golden fixtures in tests/data/ and the r4/r5 tests enforce this).
Real Stage C protocol (sglang-fcfs-r1 cell, Qwen2.5-7B on A100 80GB, KV cap 300k tokens): closed population, synchronized start at t=0, window [900, 2700) s, workload: first prompt 2000 tokens, +650 tokens per turn (100 output + tool text), T ~ min(Geometric(1/15), 60) turns, tool times Exp(5 s). Real results (allowed): FCFS mu(n) sessions/s: n=16 0.176, 20 0.224, 24 0.233, 32 0.115, 48 0.049, 96 0.061, 300 0.108; hit fraction (>50% tokens cached) 0.93, 0.93, 0.89, 0.51, 0.000, 0.000, 0.000; LPM n=48 0.087 (hit 0.385), n=300 0.105 (hit 0). The tail ordering at n>=48 is a synchronized-start transient; the throughput-implied all-miss floor is about 0.072-0.081 sessions/s.
`

phase('Port')
const port = await agent(`${RULES}
${DESIGN}
TASK (Port): From the worktree, create branch r6/separate-batching from main (bf20ed4). Apply the src/prefixmeta and test changes of wip/r6-separate-batching onto it (git diff main wip/r6-separate-batching -- src/prefixmeta tests/test_r5_engine.py, then git apply; or cherry-pick -n fc870c2 and discard everything outside src/prefixmeta and tests/). Read the result carefully and FINISH the separate-batching mode: prefill and decode as separate iterations, prefill-first ("run prefill first if possible", chunked request's next chunk always scheduled next), iteration cost per calibration.yaml's separate-iteration form (see CALIBRATION_REPORT.md section 2 and "Problems parameters can't fix"). It must be opt-in via config (e.g. engine.batching: mixed|separate) with mixed as the default. Add focused tests for the separate mode (conservation of tokens, prefill priority, a tiny hand-checkable case). Then run the FULL suite: /opt/anaconda3/bin/python -m pytest -q (about 860 tests, ~13 min). Everything must pass except the one pre-existing skip. Commit on r6/separate-batching (no AI attribution). Return: the commit hash, the config key and allowed values, the exact test counts (passed/failed/skipped), the files changed, and any part of the design you could not finish (say so plainly).`,
  { label: 'port:separate-batching', phase: 'Port', model: 'sonnet', isolation: 'worktree', agentType: 'implementer' })

phase('Validate')
const validate = await agent(`${RULES}
${DESIGN}
Port stage report: ${port}

TASK (Validate): In your worktree, git checkout r6/separate-batching. Find how round 5 ran closed-population curves (configs/prefix_meta_r5_curve*.yaml, src/prefixmeta/mech_runner.py, notes/LOG.md round-5 entries dated 2026-10-21/22). Build a config that reproduces the REAL Stage C protocol exactly (synchronized start, window [900,2700), the workload above, KV cap 300k, FCFS with waiting-prefix refresh as the registered cell, plus LPM at n=48 and 300 with SGLang's fallback to FCFS when more than 128 requests wait), using calibration/round6_server_log_fit/calibration.yaml constants. Run it for n in {16,20,24,32,48,96,300} FCFS and {48,300} LPM, in BOTH batching modes (mixed, separate), seeds 0,1,2. Compare simulated mu(n) and hit fraction to the real values given above: write calibration/round6_server_log_fit/VALIDATION.md with a table (real, mixed, separate, relative error), the peak location, the 0.5-hit crossing, and the collapse ratio; state which mode is closer and whether the level (not just the shape) now matches within 15%. Record commands, seeds, commit, output dirs. Commit (no AI attribution). Return the table and your pick of mode for the predictions, with its reasons, and anything that did not run.`,
  { label: 'validate:stageC', phase: 'Validate', model: 'sonnet', isolation: 'worktree', agentType: 'implementer' })

phase('Predict')
const predict = await agent(`${RULES}
${DESIGN}
Validation report: ${validate}

TASK (Predict): checkout r6/separate-batching in your worktree. Using the batching mode the validation picked (and also the other mode as a secondary column), produce BLIND predictions and write notes/PREDICTIONS.md:
(B1) all-miss capacity: prefix cache DISABLED, closed POP=32, seeds 0,1,2, 900 s warmup + 1800 s window: completed sessions/s, turns/s / E[T] with E[T]=14.761, and uncached prefill tokens/s. Also POP=64 seed 0.
(B2) from-empty stability (the E0b protocol): open-loop Poisson session arrivals at ABSOLUTE rates lambda on the grid 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18, 0.20, 0.22 sessions/s, cache ON, FCFS refresh=1, start from empty cache and queue, 3000 s, seeds 0,1,2. Stable := final queue < 50 and no upward backlog trend over the last 1500 s. Report the stable fraction per lambda and the predicted largest all-stable lambda (the from-empty edge) in sessions/s and as a multiple of your B1 turns-based value.
(B3) the E2 paired-arm kill test: for lambda in {0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.16} sessions/s and seeds 0,1,2, three arms sharing arrivals and session specs (common random numbers): NOBURST; BURST (200 fresh sessions within 60 s at t_b=1200 s); CAPPED (same burst, client-side session cap n_cap=20 with a FIFO gate). Each run: 1200 s warmup then 7500 s after the burst. Report per (lambda, seed, arm): TRAPPED (post-burst uncached-prefill-token rate within +/-15% of B1's all-miss token rate AND backlog slope > 0.5*(lambda - lambda_miss)), RECOVERED, or neither; and the per-lambda PASS verdict (BURST trapped, NOBURST good, CAPPED recovered in >= 2/3 seeds). If the runs are too slow, reduce to seeds 0,1 and say so; never drop arms.
(B4) native-pool curves: the Stage C closed protocol with KV cap 600k and 900k tokens, FCFS, n in {16,24,32,48,64,96,300}, seed 0: mu(n) and hit.
PREDICTIONS.md must contain: the headline numbers, every table, the exact commands, seeds, config paths, output dirs, the commit hash, and a statement of what was NOT used (no E0a/E0b/E2 data; list the files you read). Keep total runtime reasonable: use multiprocessing (<= 8 workers), and if B3 cannot finish within about 90 minutes of wall time, run lambda in {0.10, 0.12, 0.14} first and report what finished. Commit everything on r6/separate-batching (no AI attribution). Return the headline predictions and what did not run.`,
  { label: 'predict:B1-B4', phase: 'Predict', model: 'sonnet', isolation: 'worktree', agentType: 'implementer' })

phase('Verify')
const verify = await agent(`${RULES}
${DESIGN}
Prediction agent report: ${predict}

TASK (Verify, independent): in a fresh worktree checkout r6/separate-batching. (1) Re-run bit-identically, from the commands in notes/PREDICTIONS.md, one B1 seed, two B2 lambdas (one predicted stable, one unstable) and one B3 (lambda, seed) triple; confirm the numbers match PREDICTIONS.md exactly and say which did not. (2) Leak check: grep the branch's diff vs main and PREDICTIONS.md and VALIDATION.md for any reference to e0a, e0b, e2 real data paths, Nova paths (/work/classtmp), ssh, or the strings 'agentload_e0_miss', 'agentload_e0_cap', 'agentload_e2_burst'; list every hit and judge whether it is a leak (a mention of the protocol name is not a leak; a real number from those runs is). (3) Sanity: is the stable-from-empty edge in B2 consistent with B4/B1 (edge must be <= mu_max and > lambda_miss)? Does the B3 PASS region lie strictly inside the B2 window? (4) Write notes/PREDICTIONS_VERIFICATION.md with the outcome; commit on the branch (no AI attribution). Return: match/mismatch list, leak verdict, sanity verdict.`,
  { label: 'verify:predictions', phase: 'Verify', model: 'sonnet', isolation: 'worktree', agentType: 'implementer' })

return { port, validate, predict, verify }