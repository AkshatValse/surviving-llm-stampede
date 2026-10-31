# Round 11, S1 bundle 1: blind simulator predictions for B1 (basin) and E0F (fresh E0b seeds)

Written 2026-10-30, about 18:40 CDT, on branch `r11/strengthen` (HEAD `4d2bba2`; the files of this bundle were not yet committed). Result dir: **`results/r11_predict_basin/20261030-194539/`**. (A first run at 18:38, `20261030-183847`, gave identical outputs except wall times; it was re-run at 19:45 after a comment in `configs/r11_basin_predict.yaml` was corrected, so that `meta.json` records the final endpoint file's sha256. The first run is not committed.) Frozen endpoints: **`configs/r11_basin_predict.yaml`**. Driver: `experiments/r11_predict_basin.py`. Spec: `configs/r11_predict_basin.yaml`.

## Headline predictions

All of these are for the calibrated round-6 simulator. The PRIMARY column uses mixed batching. The SECONDARY column (separate_prefill_priority) gives the same verdict in every cell. Rates are in engine units, lambda = mult x 0.0715340 sessions/s. Seeds 0-2 (B1) and 3-5 (E0F) are simulated on the **exact client plans** the jobs will send: the same arrival times, turn counts and tool times.

**B1, burst at t = 1200 s, 60 s wide, 1.65 x (lambda = 0.118031), seeds 0-2**

| cell | seed 0 | seed 1 | seed 2 | per-seed numbers (mixed) | 30 extra seeds (mixed / separate) |
|---|---|---|---|---|---|
| **n = 100** | STUCK, trap_v2 TRAPPED | STUCK, TRAPPED | STUCK, TRAPPED | hit_eval 0.000; token ratio 1.03-1.05; sessions-in-system slope 0.031-0.036 /s (threshold 0.0232) | STUCK 30/30 / 30/30; TRAPPED 24/30 / 25/30 (the others: indeterminate, slope below threshold); GOOD 0/30 |
| **n = 25** | GOOD (RECOVERED) | GOOD (RECOVERED) | GOOD (RECOVERED) | hit_eval 0.934 / 0.934 / 0.928; slope -0.0007 to 0.0009 /s; end backlog < 0.02 | GOOD 28/30 / 28/30; STUCK 2/30 (seeds 108 and 109, both modes) |

* **Predicted B1 verdict: PASS (basin shown).** n100 is STUCK in 3/3 seeds and n25 is GOOD in 3/3, in both modes. The co-primary trap_v2 label for n100 is TRAPPED in 3/3, so the pre-stated outcome "stuck, slope-indeterminate" is **not** predicted for seeds 0-2. Over 30 seeds, though, 5-6 of 30 n100 runs fail the slope test while staying at hit 0. The slope label is therefore the fragile part, as round 7 found (8/10 TRAPPED at n = 100 and 1.65 x, all 10 stuck).
* The n = 100 burst's first prompts total 200,000 tokens, less than the 300,000-token pool, yet every simulated n = 100 run is stuck at hit 0 from the 1300-1400 s window on. None releases before 8700 s.
* Size of the basin in the simulator at 1.65 x, on these plans: 25 sessions do not trap (28 of 30 extra seeds), and 100 sessions always do (33 of 33 seeds).

**E0F, from empty, 3000 s, registered E0b stability rule, seeds 3-5**

| mult | seed 3 | seed 4 | seed 5 | 20 extra seeds stable (mixed / separate) |
|---|---|---|---|---|
| **2.0 x** (lambda 0.143068) | stable (realized 2.01 x) | stable (2.15 x) | stable (1.97 x) | 18/20 / 19/20 |
| **2.5 x** (lambda 0.178835) | stable (2.51 x) | stable (2.67 x) | stable (2.47 x) | 11/20 / 12/20 |

* **Predicted E0F verdict: NOT replicated.** 2.0 x is stable in 3/3 as the plan hypothesises. But 2.5 x is predicted **stable** in 3/3 seeds, not unstable in at least 2/3. Seeds 3-5 draw realized rates close to or below nominal (2.47-2.67 x). The committed seed 0 drew 2.73 x (+2.1 SD), and the same simulator, on the same rule and plan, calls that run unstable. So the simulator predicts the engine's 2.0/2.5 x bracket edge is partly a seed-0 arrival effect. The plan's decision rule then applies: restate the bracket in realized rates.
* The per-seed 2.5 x calls are fragile. In the extra seeds, stability at 2.5 x nominal is close to a coin flip (11-12 of 20). Every extra seed with a realized rate of at least 2.58 x is unstable except one (separate mode, 2.69 x). Seed 4 (2.665 x) is therefore the least secure "stable" call. Seeds 3 and 5 (2.51 x and 2.47 x) sit where extra seeds go either way.

**Retrodictions (outcomes known; listed so the reader can calibrate the predictions above):** on the same exact plans, NOBURST (n = 0) is predicted RECOVERED in 3/3 seeds and BURST-200 TRAPPED in 3/3. E0b seed 0 is predicted stable at 2.0 x and unstable at 2.5 x. All of these match the committed engine runs.

## Scope of blindness

* **No B1 run (burst n = 100 or 25) and no E0F run (seeds 3-5) exists** anywhere when these predictions are made: none has been submitted. The registrations `configs/agentload_prereg_2026-10-30_b100.yaml` and `_b25.yaml` and the cell configs `configs/agentload_e2_burst_n100.yaml` and `_n25.yaml` exist in the worktree, uncommitted. This bundle, the endpoints and those files are meant to be committed and tagged together as `r11-basin-reg` before the first submission.
* **The lead knows the committed outcomes of the n = 200 BURST and n = 0 NOBURST runs** on the same seeds (jobs 17093387-17093404, `results/nova/e2_170933xx_pulled_20261025-144558`: BURST trapped and NOBURST good). The lead also knows E0b seed 0 (2.0 x stable, 2.5 x unstable). These shaped the plan's hypothesis, so the n = 25/100 predictions are blind only about the new burst sizes and seeds. The base sessions of the n = 100 and n = 25 plans are identical to those of the known n = 200 and n = 0 runs (checked below), so only the burst sessions are new inputs.
* The simulator, engine block, workload and analysis constants are unchanged since round 6. No parameter was fitted to any r11 data. The plan read of committed real runs uses `plan.csv`, `meta.json` and `config_effective.yaml` (inputs only). No outcome file of any run was read for this bundle.
* The round-7 simulator burst-size sweep (`notes/ROBUSTNESS_r7.md` item 3, simulator lambda units, the simulator's own streams) is the earlier blind record. It is consistent with this bundle: n = 25 trapped 0/10, n = 100 stuck 10/10 and TRAPPED 8/10 at 1.65 x.

## What was simulated

* **Engine:** the round-6 calibrated engine, inherited from `configs/r6_predict.yaml` through `base_config`. The driver refuses to run if the effective engine, workload or metrics differ from that file's. PRIMARY is `batching: mixed`; SECONDARY is `separate_prefill_priority`. FCFS with LRU eviction, 300k KV tokens, finished-session KV freed at once, 100 s windows.
* **Streams (the change from round 6):** the round-6 predictions used the simulator's own Poisson streams (`prefixmeta.workload.build_specs`) with the seed numbers 0-2, and those are not the client's streams. Here every run is driven by the client generator. The driver calls `agentload.workload.build_open_plan` on `configs/agentload_e2_burst.yaml` (B1; burst.n set to 25, 100 or 200, or `arrivals.burst = null` for NOBURST) or on `configs/agentload_e0_cap.yaml` (E0b), with the job's seed, `rate_mult` x lambda_ref, burst and duration. It converts the result to `SessionSpecs` and passes them to `prefixmeta.sim.simulate(..., specs=...)`. No file in `src/` was edited. The burst size is set in the client config, exactly as the B1 jobs set it through `E2_CONFIG`, so no probe override was needed.
* **Plan checks (`plan_checks.csv`, `plan_subset_checks.csv`), all passed before anything was simulated:**
  * The driver reproduces the committed `plan.csv` of the six 1.65 x n = 200 and n = 0 runs (seeds 0-2) and of E0b seed 0 at 2.0 x and 2.5 x. Session count, order, origin, index, arrival times and turn counts match bit for bit, and the resolved rate equals `meta.json`'s.
  * Per-session tool-time totals agree to 1.7e-13 s, not bit for bit (35% of sessions differ in the last bits). The tool times are exponential draws, which use a log, and Nova's Linux libm and the PC's differ in the last bit. Arrival times are uniforms and match exactly. The difference has no effect at the simulator's resolution.
  * For seeds 0-2, the n = 100 and n = 25 plans have exactly the n = 200 plan's base sessions, and their burst times are a subset of its burst times. The burst sessions' turn counts and tool times are re-indexed by rank, so only base sessions pair exactly.
  * The plans built from the cell configs `configs/agentload_e2_burst_n100.yaml` and `_n25.yaml` (as they stand in the worktree) are identical to the driver's.
* **Seeds:** B1 engine seeds 0-2, plus 30 extra seeds (100-129) for each of n = 25, 100 (predicted) and 0, 200 (reference). E0b engine seeds 3-5, reference seed 0, plus 20 extra seeds (100-119) at each of 2.0 x and 2.5 x. No engine run uses seeds 100-129. In total, 360 simulations (both modes) ran in 11 s on 6 worker processes on the PC.

## Endpoints and their simulator analogues

The frozen definitions are in `configs/r11_basin_predict.yaml`. That file is read by this driver and by `analysis/basin.py`, and every constant in it is a registered one (`configs/agentload_prereg_2026-10-24.yaml` pass_rule, which equals the pass_rule of the two 2026-10-30 registrations). In short, over W = [5700, 8700) s:

* **STUCK** := hit_eval < 0.2.
* **trap_v2 label** := the registered label, with crit (a) |uncached prefill tok/s / reference - 1| <= 0.15 AND crit (b) sessions-in-system slope > 0.5 (lambda - lambda_ref).
  * Precedence: trapped > recovered (hit > 0.8 and outstanding backlog < 20 over the last 300 s) > draining > indeterminate.
* **GOOD** := RECOVERED OR (hit_eval > 0.8 AND slope <= threshold).
* **Decision rule:** PASS iff n100 is STUCK in >= 2/3 seeds AND n25 is GOOD in >= 2/3.
  * Pre-stated outcomes: "stuck, slope-indeterminate"; critical size refuted (n100 GOOD); "even 25 traps".
* **E0F:** stable := not aborted AND final queue < 50 AND fitted rise of the 100 s queue means over the last 1500 s <= 10.
  * Replicated iff 2.0 x is stable in 3/3 AND 2.5 x is unstable in >= 2/3. Realized rates are always quoted.

The simulator does not produce request logs, so the engine-side quantities are computed from its 100 s windows. Each analogue below was declared in the driver's docstring before the run:

* **hit:** hits / admitted turns. The simulator attributes a turn by its admission time; the engine attributes it by completion time.
* **crit (a):** compared with the simulator's own all-miss token rate of the same mode (r6 B1: 11,219.7 mixed, 11,146.8 separate), as r6 B3 and r7 did. The registered engine value, 11,243.2, is 0.2% higher, so either choice gives the same crit (a) in every run here (both columns are in `basin_runs.csv`).
* **slope:** the sessions in the system are arrivals minus completed sessions at window ends, averaged per window. The OLS slope over W uses 100 s windows instead of 10 s bins. The registered waiting-queue + gate slope is in `backlog_slope_queue_gate` for comparison.
* **outstanding:** waiting queue + gate. The engine also counts running requests, a handful in the good state, which cannot move a run across the 20 threshold.
* **E0b final queue:** the last 100 s window's mean (the engine uses its last fine bin). The round-6 rule, with the instantaneous final backlog, gives the same counts (`stable_r6_rule`).

## How the engine runs will be scored against this bundle

This follows S1's decision_rule.
* **Per-seed state match:** n100 STUCK and TRAPPED; n25 GOOD; E0F 2.0 x stable 3/3 and 2.5 x stable 3/3.
* **Numeric bands:** hit_eval within ±0.1 of the prediction (n25: 0.93; n100: 0.00).
* **Descriptive only:** n100 token ratio 1.03-1.05 against the engine's own E0a reference, and n100 sessions-in-system slope 0.031-0.036 /s.
* A miss is reported, not explained away. The validation already showed that the simulator's all-miss level can sit above the real engine's. Seed-level from-empty calls near 2.5 x are the weakest predictions here, as noted above.

## Commands and provenance

```
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" experiments/r11_predict_basin.py run
```

`meta.json` records the following:
* git HEAD `4d2bba245537a1b42801291217cb3e56d8d59513` (`r11/strengthen`) and the full `git status`. The bundle's own files and other agents' r11 files were untracked, and `slurm/common.sh` was modified.
* `simulation_inputs_clean_vs_head: true`: `src/prefixmeta`, `src/agentload/{workload,config}.py`, the r6/r5/base configs and the two agentload configs equal HEAD.
* The sha256 of every simulation input, including:
  * driver `5d5e0864...` (`experiments/r11_predict_basin.py`)
  * spec `48228d93...` (`configs/r11_predict_basin.yaml`)
  * endpoints `2f340909...` (`configs/r11_basin_predict.yaml`)
  * `configs/agentload_e2_burst_n100.yaml` `3fd25217...`
  * `configs/agentload_e2_burst_n25.yaml` `967d9bbf...`

If any of these files changes before the commit, the bundle must be re-run (11 s).
* Machine: Akshat-PC, Windows 11, Python 3.12.10, NumPy 1.26.4, pandas 2.2.2.

Files to force-add (all small): everything in `results/r11_predict_basin/20261030-194539/` except `full/` (`full/windows_all.csv.gz`, 1.6 MB, all 100 s windows of all runs, stays local).
* `plan_checks.csv`, `plan_subset_checks.csv`
* `basin_runs.csv` (one row per B1-type run, both modes, every endpoint quantity), `basin_summary.csv`
* `e0b_runs.csv`, `e0b_summary.csv`
* `engine_seed_windows.csv` (per-window hit / queue / rates of the engine-seed and reference runs, for the basin figure)
* `headline.json`, `tables.md` (generated tables), `config.yaml`, `endpoints.yaml`, `meta.json`
