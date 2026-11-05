# r15 REPLICATE-EDGE (exploratory): frozen predictions for same-plan replicates of the 2.5 x from-empty edge

Written 2026-11-05, about 02:05 CST, on branch `r15/tonight` (HEAD `8aaabdb`; the files below were not yet committed). Revised about 03:00 CST by the independent review, still before any run existed: the verdict order now follows the design (a disagreement is a PLAN-CONDITIONAL ESCAPE whatever the replicate counts), a descriptive among-new-runs location was added, the sbatch lines carry `LPM_INF=0` and `--cpus-per-task=16` as the E0F submit line did, and the JSON was regenerated (no prediction changed; see the end of this file). Frozen JSON: **`results/theory/r15/edge_preds.json`** (generator `experiments/r15_edge_preds.py`, 7 s on the PC). Frozen rule: **`configs/r15_edge_replicate.yaml`**. Classifier: `analysis/r15_edge.py`. Tests: `tests/test_r15_edge.py`.

`results/*` is git-ignored, so the JSON must be force-added (`git add -f results/theory/r15/edge_preds.json`).

## What the cell asks, and why it is exploratory

The question is whether the 2.5 x from-empty edge of the A100 300k SGLang FCFS cell is fixed by the workload path, or whether the same plan escapes on some runs and not others. The second case would be noise-induced escape at a fixed workload.

Two runs define that edge at 2.5 x:
* seed 0 collapsed at about 1600 s (job 17084754, nova22-gpu-1, GPU Bus-Id 00000000:86:00.0, commit `bf20ed4`);
* seed 4 stayed stable for 3000 s (job 17168507, nova22-gpu-3, Bus-Id 00000000:06:00.0, commit `9b67c26`).

Both plans are re-run unchanged, with the same arrival times, turn counts and tool times. Each runs 3 times, in two MODE=cap jobs of 3 runs each (CAP_RUN_S 3000, MULTS 2.5):

| job | run 1 (salt 1, fresh engine) | run 2 (salt 2) | run 3 (salt 3) |
|---|---|---|---|
| A, SEEDS "0 4 0" | seed 0 (as its original: position 1, salt 1) | seed 4 (as its original: position 2, salt 2) | seed 0 |
| B, SEEDS "4 0 4" | seed 4 | seed 0 | seed 4 |

Between runs the job glue sleeps 180 s, flushes the cache and verifies it empty with the canary (`between_runs` → `reset_and_verify`, STRICT_FLUSH=1). The content salt changes only the token ids of the prompts, not their lengths or timing.

**This cell is exploratory, and it cannot be decisive.**
* It was chosen tonight, after the existing E0b and E0F data had been read: data-B's D3 table, and the N3 review, which showed that the count, turn and token brackets of the four 2.5 x runs are equally deterministic.
* The two plans were picked because their outcomes are known.
* MODE=cap has no registration branch in the job glue.
* The sample is 3 + 3 new runs.

The result is stated as "k of n same-plan replicates (dis)agreed", never as a test of metastability or of the F2 law.

## The frozen rule (configs/r15_edge_replicate.yaml), in short

* **Per run.** This is data-B's D3 definition, applied unchanged.
  * Hit metric: the follow-up hit fraction over ok turns > 1 (cached / prompt tokens > 0.5), in 100 s bins by completion time, over rolling 300 s windows that hold at least 5 turns.
  * **UNSTABLE** iff a window starting at or after 600 s has hit ≤ 0.2, an earlier window had hit ≥ 0.6, and no later window reaches ≥ 0.5. Otherwise STABLE.
  * The registered E0b stability verdict (`analysis.summarize stable`) is recorded next to it for comparison.
  * The rule reproduces data-B's collapse flags and taus on all 88 committed runs of the D3 table, with no mismatch. It gives seed 0's original tau = 1600 s and calls seed 4's original STABLE.
* **Manipulation check.** The run's plan.csv must equal the original's: sid, origin, idx and n_turns identical; arrival and tool-time totals within 1e-9 s.
* **Validity.** A run counts only if all of these hold:
  * it is a finished, full 3000 s run;
  * its start state is verified;
  * its effective config equals the original's except the job-specific keys;
  * the label, hardware and rate are the cell's, and the clone is clean;
  * the engine is not shown to differ: SGLang `server_args` other than port and random_seed, the job banner's run parameters (including REFRESH, which is an engine environment variable and not a server arg), the pip freezes and the HF snapshot are compared against the original job.
* **Verdict.** The rules are applied in this order:
  1. **PLAN-CONDITIONAL ESCAPE** if a plan's runs disagree, counting the original as a 4th replicate, whatever the replicate counts.
  2. Otherwise **REPRODUCIBLE** if seed 0 is UNSTABLE in 3/3 and seed 4 is STABLE in 3/3.
  3. Otherwise **INCOMPLETE** if either plan has fewer than 2 valid replicates.
  4. Otherwise **CONSISTENT-PARTIAL**.
* **Locating a disagreement.** It is labelled as one of:
  * **WITHIN-GPU**: two runs on the same node and Bus-Id disagree;
  * **WITHIN-NODE**: two runs on the same node disagree;
  * **ACROSS-NODES-ONLY**: the outcome is constant within each node.

  Only a within-node disagreement is read as noise-induced escape at a fixed workload. Reported next to it, descriptive only: whether a plan's new runs disagree among themselves, and where. A disagreement between the original and the new runs only is also confounded with the date and the job.

## Predictions (frozen)

| predictor (source) | seed 0 plan | seed 4 plan | predicted verdict |
|---|---|---|---|
| realized arrival count (bracket: stable ≤ 2.665, unstable ≥ 2.726 × λ_ref) | 585 sessions, 2.726 → UNSTABLE | 572, 2.665 → STABLE | REPRODUCIBLE |
| turn load, turns / (3000 λ_ref × 15) (bracket 2.515 / 2.708) | 8718 turns, 2.708 → UNSTABLE | 8019 turns, 2.491 → STABLE | REPRODUCIBLE |
| token work, Σ T·L0 + 650·T(T−1)/2 (bracket 84.3 / 92.0 Mtok) | 92.01 → UNSTABLE | 84.32 → STABLE | REPRODUCIBLE |
| level crossing on the exact plan (`results/theory/pred2/e0f.json`, frozen `r13-theory-pred2` `cfa7712`) | UNSTABLE (first crossing at 1464 s) | STABLE (peak live KV 304,750 < V2 321,981) | REPRODUCIBLE |
| calibrated simulator, exact plan, mixed (PRIMARY) | UNSTABLE, tau 1600 s; registered rule unstable (final queue 121, rise 134) | STABLE; registered stable (final queue 0.05) | REPRODUCIBLE |
| calibrated simulator, separate_prefill_priority (SECONDARY) | UNSTABLE, tau 1600 s (final queue 114) | STABLE | REPRODUCIBLE |
| F2 escape law, p_escape_fine['2.5'] = 0.6907 at 3000 s (`results/theory/merged/a100_300k.json`, frozen `r13-theory-pred` `997d2c4`), replicates read as independent draws | P(3/3 UNSTABLE) = 0.330 | P(3/3 STABLE) = 0.030 | PLAN-CONDITIONAL ESCAPE, P = 0.990 (REPRODUCIBLE 0.0097) |
| F2 at each plan's realized rate (pred2 band: p = 0.878 for seed 0 and 0.839 for seed 4) | 0.677 | 0.0042 | PLAN-CONDITIONAL ESCAPE, P = 0.997 |

* **What the brackets are.** They are the definitions of the N3 review (scratch `verify-N3/rates.py`), recomputed here from the exact client plans of seeds 0, 3, 4 and 5: stable maxima 2.665 (count, seed 4), 2.515 (turns, seed 3) and 84.32 Mtok (tokens, seed 4); unstable minima from seed 0. Seed 0 and seed 4 define these brackets themselves, so their calls are retrodictions of the originals. For the replicates they say only this: a deterministic function of the plan cannot differ between replicates of one plan.
* **Simulator.** This is the round-6 calibrated engine (`configs/r6_predict.yaml`, asserted) run through the r11 E0F driver unchanged (`experiments/r11_predict_basin.py`, `_work` + `e0b_classify`). It is built at duration 3000 s with `configs/agentload_e0_cap.yaml`, on exactly the plans the jobs will send.
  * It reproduces the committed r11 E0F rows for seeds 0 and 4 at 2.5 x in both modes (`results/r11_predict_basin/20261030-194539/e0b_runs.csv`).
  * The r15 rule is applied to its 100 s follow-up hit windows. These are attributed by admission time; the engine attributes by completion time.
  * The simulator has no service noise. It is deterministic given the plan, so it predicts that every replicate repeats its call.
* **Speed sensitivity (descriptive, frozen with the rest).** Every engine time constant was scaled by f, with f from 0.70 to 1.30.
  * In the PRIMARY mode, seed 0 first survives at f = 0.70 (30% faster service). Seed 4 first collapses at f = 1.30 (30% slower). The SECONDARY mode gives 0.75 and 1.30.
  * Both calls hold for every f between 0.80 and 1.25. The node-to-node spread of the all-miss token rate is about 2% (11,347–11,573 tok/s across nova22-gpu-1/2/3).
  * So the simulator predicts no ACROSS-NODES-ONLY disagreement either.
  * Seed 0's simulated collapse time stays at 1500–1800 s over f = 0.85–1.15. The original collapsed at 1600 s.
* **F2.** F2 is a law for a cell, not for a fixed plan. Read as independent draws, it predicts disagreement inside both plans. Same-plan replicates hold the arrival path fixed and leave only service noise. Under F2's own noise model the disagreement probabilities above are therefore upper bounds, by Jensen's inequality (E[q⁴]/E[q] ≥ E[q]³ for the plan-conditional collapse probability q).
  * Other F2 quantities: P(disagreement in plan 0) = 0.670; P(disagreement in plan 4) = 0.970; P(a same-GPU pair differs) = 0.427 per job; P(at least one of the two same-GPU pairs differs) = 0.672.
  * The rule's last collapse window starts at 2800 s, so its effective horizon is shorter than 3000 s. With the constant hazard implied by p(3000), p = 0.652 at 2700 s and 0.624 at 2500 s. This adjustment is derived, not frozen.

**Headline.** Every deterministic predictor predicts REPRODUCIBLE: the plan statistics, the level crossing, and the simulator (including across ±20% service speed). F2 read as independent draws predicts PLAN-CONDITIONAL ESCAPE with P ≈ 0.99.
* A within-node disagreement would contradict every deterministic predictor.
* REPRODUCIBLE would contradict F2 read as independent draws. It would not contradict F2 as a cell law whose hazard depends on the plan; report it as "F2 does not describe same-plan replicates", not as a refutation of F2's cell-level escape probability.

## How the runs will be scored

* **Command.** On the PC, after the pull:

  ```
  PYTHONPATH="src;." python -m analysis.r15_edge classify --run-dirs <the 6 run dirs> --out-root <pull dir>/analysis
  ```

  It writes `r15_edge_runs.csv` (every run: node, GPU, position, salt, label, tau, the registered verdict, checks), `r15_edge_verdict.json` (the frozen verdict, its location label, and the same verdict under the registered stable rule, descriptive) and `meta.json`.
* **Scoring.** Each predictor's verdict above is compared with the frozen verdict. The per-plan calls are compared with the per-run labels. Every run's node and GPU is quoted. A miss is reported, not explained away.
* **INCOMPLETE.** A disagreement among the valid runs is a PLAN-CONDITIONAL ESCAPE whatever the counts, and it is scored. Without one, if fewer than 2 valid replicates of a plan exist, no predictor is scored.

## Blindness and what was read

* **Blind in time.** No run of this cell existed when this was written: nothing had been submitted.
* **Not blind on the originals.** Their outcomes, their run directories (requests.csv, metrics.csv, plan.csv, meta.json, job logs), data-B's tables and the N3 review were all read. The cell was designed from them.
* **Frozen inputs, unchanged.**
  * F2: frozen at `997d2c4`.
  * pred2 band and level crossing: frozen at `cfa7712`.
  * The simulator engine is the round-6 calibration. Nothing was fitted to these runs.
* **Tonight's jobs.** No result or output of any of tonight's jobs was read.

## Verification done before freezing (on the PC; scratch scripts in `scratchpad/tonight/build-edge/`)

* **Plans.**
  * The r15/tonight client regenerates both originals' plan.csv through `LoadGenerator.build_plan` and `write_plan_csv`. This was done twice: from the new job's own `--set` words, and from each original's `config_effective.yaml`.
  * Session counts (585 and 572), order, origin, idx, arrival times and turn counts match bit for bit. Tool-time totals agree to 1.7e-13 s, a libm last-bit difference between Linux and Windows. The resolved rate equals `meta.json`'s exactly.
  * The new job's effective config differs from the originals' only in base_url, content_salt, engine_label, start_state_detail, and (seed 0 only) the lambda_ref path.
  * The lambda_ref path points at the committed `prereg/inputs/2026-10-23/calibration.json`, the E0F job's CALIB_FILE. Its lambda_miss_turns_based is identical to the Nova file the seed-0 job used. The two copies differ only in the last digit of `all_miss_uncached_tokens_per_s_se`.
* **Code path.**
  * These bash functions are byte-identical at `bf20ed4`, `9b67c26` and HEAD: `mode_cap`, `reset_and_verify`, `run_gen`, `between_runs`, `flush_cache`, `canary_cli`, `check_calib_hardware`, the time-budget functions, `setup_jit_env` and `check_jit_toolchain`.
  * These files are blob-identical at all three commits: `src/agentload/{workload,canary,cli,poller,parse,runmeta,__main__}.py` and `configs/agentload_{e0_cap,e2_burst,analysis}.yaml`.
  * The functions that changed (`job_main`, `validate_mode_inputs`, `post_analysis`, `banner`, `launch_engine`, `check_engine_flags`, `engine_env_prefix`, `engine_required_vars`, `engine_post_health_check`) change only in branches that are inactive or log-only for these jobs: the LPM_INF=1, MODE=burst, ARMS=rescue and E2_CONFIG paths.
  * The `client.py`, `config.py` and `gate.py` changes are guarded by `gate.mode: rescue` and `workload.tool_slowdown`. The repo's identity tests against the older clients pass on the PC (4 passed): `tests/test_agentload_rescue_e2e.py::test_uncapped_and_static_capped_runs_match_the_base_commit` (base `4d2bba2`, whose `src/agentload` equals `bf20ed4`'s and `9b67c26`'s) and `tests/test_r14_extra.py::test_without_the_option_the_client_matches_the_base_commit` (base `f0bc3ad`).
* **Engines.** The two original jobs ran identical engines. Their SGLang `server_args` (536 keys) differ only in port and random_seed. Their pip freezes, HF snapshot (`a09a3545…`) and flag checks are identical. Both logged the same launch line: `policy=fcfs refresh=1 radix=1 lpm_inf=0 kv_tokens=300000 attn=flashinfer CUDA_HOME=/work/classtmp/avalse/swapp/cuda13-home extra=' --sampling-defaults openai --revision a09a3545…'`.
* **Nova, read-only, 01:42 CST.**
  * `envs/swapp` has numpy 2.4.6 (the originals' version) and `envs/sglang` has sglang 0.5.22.
  * `cuda13-home`, `cache` and the HF snapshot `a09a3545…` exist.
  * `repo_r15_tonight` does not exist yet.

## Jobs

They are submitted from a fresh clone at the tag `r15-reg`. The command block:

```
cd /work/classtmp/avalse/swapp/repo_r15_tonight      # fresh clone at tag r15-reg; git status --porcelain must be empty
env | grep -E '^(SBATCH_|PYTHONPATH=|MODEL=|CONTEXT_LEN=|LPM_INF=|GAP_S=|STRICT_FLUSH=|STRICT_FLAGS=|PORT=|SEEDS=|MULTS=|ARMS=|N_CAP=|CAP_FILE=|PREREG_FILE=|E2_CONFIG=|ALLOW_HW_MISMATCH=|ATTN_BACKEND=|REQUEST_TOKEN_IDS=|RESULTS_ROOT=|CAP_RUN_S=|GEN_EXTRA=|ANALYSIS_EXTRA=)'   # must print nothing (--export=ALL passes them on)
sbatch --account=f2026.coms.6250.02 --partition=instruction --qos=instruction --cpus-per-task=16 --mem=20G --time=03:20:00 --job-name=pm-edgeA --export="ALL,ENV_GEN=/work/classtmp/avalse/swapp/envs/swapp,ENV_SGLANG=/work/classtmp/avalse/swapp/envs/sglang,HF_HOME=/work/classtmp/avalse/swapp/hf,XDG_CACHE_HOME=/work/classtmp/avalse/swapp/cache,CUDA_HOME_SHIM=/work/classtmp/avalse/swapp/cuda13-home,HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28,OUTPUT_FEEDBACK=server,KV_TOKENS=300000,MODE=cap,POLICY=fcfs,REFRESH=1,LPM_INF=0,MULTS=2.5,SEEDS=0 4 0,CAP_RUN_S=3000,CALIB_FILE=prereg/inputs/2026-10-23/calibration.json,ENGINE_LABEL=sglang-fcfs-r1-edgerep" slurm/sglang_job.sbatch
sbatch --account=f2026.coms.6250.02 --partition=instruction --qos=instruction --cpus-per-task=16 --mem=20G --time=03:20:00 --job-name=pm-edgeB --export="ALL,ENV_GEN=/work/classtmp/avalse/swapp/envs/swapp,ENV_SGLANG=/work/classtmp/avalse/swapp/envs/sglang,HF_HOME=/work/classtmp/avalse/swapp/hf,XDG_CACHE_HOME=/work/classtmp/avalse/swapp/cache,CUDA_HOME_SHIM=/work/classtmp/avalse/swapp/cuda13-home,HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28,OUTPUT_FEEDBACK=server,KV_TOKENS=300000,MODE=cap,POLICY=fcfs,REFRESH=1,LPM_INF=0,MULTS=2.5,SEEDS=4 0 4,CAP_RUN_S=3000,CALIB_FILE=prereg/inputs/2026-10-23/calibration.json,ENGINE_LABEL=sglang-fcfs-r1-edgerep" slurm/sglang_job.sbatch
```

**Where each setting comes from.** Both originals' exact submit lines are in `provenance/sacct_cited_jobs_2026-11-01.txt` (SubmitLine of jobs 17084754 and 17168507).
* ENV_GEN, ENV_SGLANG, HF_HOME, XDG_CACHE_HOME, CUDA_HOME_SHIM, HF_REVISION, OUTPUT_FEEDBACK, KV_TOKENS, MODE=cap, POLICY=fcfs, REFRESH=1 and MULTS=2.5: both submit lines, unchanged. The job banners and logs agree (run parameters; jit-check and launch lines).
* LPM_INF=0 and `--cpus-per-task=16`: the E0F submit line (17168507). The E0b line (17084754) left both at their defaults, which are the same values.
* CALIB_FILE: the E0F job's committed copy. The E0b job read the Nova copy `results/agentload_analysis_miss/20261023-142433/calibration.json`, whose lambda_miss_turns_based is identical.
* CAP_RUN_S=3000: the default, made explicit.

**What differs from the originals.**
* Memory: `--mem=20G`. The originals used 128G (E0b, the script default) and 48G (E0F). MaxRSS of the batch step was 4.42 GB (17084754), 4.59 GB (17168506) and 4.42 GB (17168507) (sacct, read 2026-11-05). No SGLang job in the pulled sacct records or in the cited-jobs provenance ran at 20G (all used 48G or 128G).
* Time limit: `--time=03:20:00`. The E0b job had 01:30:00 and the E0F job 03:30:00. The glue's budget needs 11,190 s; the E0F 3-run jobs took 2:40:30.
* The E0F submit line had `--nice=58`. It is not carried over; whether to use it is the lead's call.
* The label `sglang-fcfs-r1-edgerep`.
* The job names.
* The seed lists.

**Cheap login-node check before submitting.** This writes nothing. It should print n_sessions 585 / n_turns_total 8718 for seed 0, and 572 / 8019 for seed 4:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. /work/classtmp/avalse/swapp/envs/swapp/bin/python -m agentload plan --config configs/agentload_e0_cap.yaml --seed 0 --set arrivals.rate_mult=2.5 --set arrivals.lambda_ref="prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based" --set run.duration_s=3000
```

Run it again with `--seed 4`. (The same command on the PC prints 585 / 8718 and 572 / 8019, with all_miss_prompt_tokens_total 92,008,550 and 84,323,750.)

**Optional placement.** To cross the originals' nodes, add `--nodelist=nova22-gpu-1` to job A and `--nodelist=nova22-gpu-3` to job B. Each plan then has two runs on its original's node and one on the other node. This can delay the start.

## Independent review (about 03:00 CST, before any run existed)

Checked by re-running, not by reading the build notes:
* **Plans.** Both originals' plan.csv were regenerated through the `agentload run` argument parser with each original's own argv (from meta.json) and with the new jobs' words for all six (seed, salt) positions. Counts, ids, origins, idx, arrival times and turn counts are identical. Tool-time totals differ by at most 1.7e-13 s on the PC (217 and 205 rows, last bits). Effective configs differ only in the allowed keys.
* **Code path.** The diffs `bf20ed4..HEAD` and `9b67c26..HEAD` of `slurm/` and `src/agentload/` were read in full. Every change is in a MODE=burst, ARMS=rescue, E2_CONFIG, LPM_INF=1, `gate.mode: rescue` or `workload.tool_slowdown` branch, or is log-only. The four client identity tests pass.
* **Nova, read-only.** The `envs/swapp` and `envs/sglang` site-packages directories and `envs/swapp/conda-meta` have mtimes of 2026-10-21, and nothing in them is newer than 2026-10-31 22:00. The pip freezes of the 2026-10-31 r14 jobs (17169908-11) equal the originals'. So the new jobs' freezes should equal them too. The only HF snapshot is `a09a3545…`. The Nova calibration copy's sha256 is `420b7111…`. `repo_r15_tonight` is absent.
* **Rule.** It agrees with data-B's D3 table on all 88 runs. The originals come out as seed 0 UNSTABLE (tau 1600 s) and seed 4 STABLE.
* **Predictions, re-derived independently.**
  * The comparators came from plan.csv files on disk. The token work matches the client's own all-miss prompt-token total.
  * The F2 verdict probabilities came from enumerating the 6 new runs.
  * The simulator was re-run for both plans and both modes. Its per-100 s hit rates match the committed r11 run, and a separate implementation of the rule gives the same calls and taus.
  * Every number in the JSON matched.
* **Changed by the review.**
  * Verdict order: ESCAPE now comes before INCOMPLETE, as the design specified.
  * New descriptive among-new-runs fields.
  * In the sbatch lines, `LPM_INF=0` and `--cpus-per-task=16`.
  * The provenance of each setting, now from the submit lines.
  * The generator docstring's speed range.
  * The JSON was regenerated. Only `written` and the provenance block changed.
