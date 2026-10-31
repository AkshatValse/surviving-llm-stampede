# Round 11, bundle 3: blind simulator predictions for the rescue cells (R1, R4) and the remedy comparison (plan S1)

Written 2026-10-30, about 19:00 CDT; revised about 20:00 CDT after two adversarial reviews, for tag `r11-rescue-pred`. Result dir
`results/r11_predict_rescue/20261030-195231/` (force-added summaries). Driver `experiments/r11_predict_rescue.py`, spec
`configs/r11_predict_rescue.yaml`, controller `src/prefixmeta/gate_control.py`.

## R4 engage time: lead decision (2026-10-30, about 21:30 CDT, before the tag; no rescue run existed)

- **R4 engages at t_on = 2,100 s, not 2,400 s.** The lead chose this **after the 2,400-s R4 prediction (13/20 RESCUED, mixed) had been
  seen and before any real rescue run** (no GPU rescue job had been submitted or run). It is a selection step under the plan R1 rule
  "if a frozen prediction for a cell is below 7/10 RESCUED, rethink that cell before submission, never after", and it is disclosed here.
- **The R4 prediction of record is the `R4s_t2100` cell of this result dir: 16/20 RESCUED (mixed, primary) and 18/20 (separate).**
  Exact plans: seeds 0, 1, 2 RESCUED in both modes (t_rel 4,250 / 5,180 / 4,410 mixed; 4,680 / 4,480 / 4,820 separate). The `R4_rescue`
  cell (t_on 2,400) is kept unchanged in the dir as the superseded prediction; every number of it below is labelled as such.
- The driver was **not** rerun for this: the `R4s_t2100` cell is exactly the R4 protocol with t_on 2,100 (cap 64, pause, hold 300,
  min_on 600, 4.0 x, 20 seeds plus the exact plans of seeds 0-2, both modes), so every file of the result dir stays bit-identical.
- The three coordinated edits are in the registration commit (tag `r11-rescue-reg`): `configs/agentload_e2_rescue_native.yaml`
  `gate.t_on_s: 2100`; `analysis/rescue.py` `PROFILES["r4"]`: `t_on_s` 2100 (so VALID is FU-hit < 0.2 over [1,800, 2,100) and more than
  50 outstanding at 2,100 s) and `prediction_cell` `R4s_t2100` (the t_rel scoring band); and the native rescue registration
  `configs/agentload_prereg_2026-10-31_rescue_native.yaml`, filled from that e2 config.

## What changed after the review (no rescue run existed before or after)

- The driver was rerun (2,090 runs, about 105 s on 6 workers). The superseded pre-review dir `20261030-185637` is no longer in the repo.
- **Every registered prediction quantity is bit-identical to the pre-review run.** On all 913 runs both dirs contain (each mode), these
  fields are equal: VALID, RELEASED, POST_GOOD, RESCUED, RELAPSE, t_rel, t_engage, pauses, STUCK, RECOVERED at the end, sessions shed.
- **t_rec was redefined** to the `analysis/rescue.py` `t_recovered` definition, so that the per-seed rows can be scored against the GPU
  runs: the first 10-s tick t >= t_on whose window [t, t + 300) has FU-hit > 0.8 and mean outstanding < 20. The old definition (every
  tick for 300 s with 60-s H > 0.8 and outstanding < 20) was stricter: the new t_rec is earlier by a median of 120-130 s (at most
  about 1,500 s). t_rec is descriptive; it is not part of the rule.
- **New descriptive columns:** per-session delays (admission wait + pauses), delay session-hours, sessions still gated or paused at the end,
  completed share, the [1200, 3000) arrival cohort's completed share and median duration, the FU-hit before the release / lull end, and
  how close the uncapped run came to the cap after release.
- **New comparator cells (selection disclosure: added after the review, before any rescue run):**
  - `R1_shed_pause`: the pause cap's cap, engage and release rule, but an arrival that finds the cap binding is DROPPED, not queued;
  - `R1_shed_attrition`: the same without pausing;
  - `lull_stop_trel`: a full stop from 1,800 s that ends at the same seed's pause-cap release time.
- `src/agentload/config.py` is now in the hashed files of `meta.json` (the exact client plans depend on it).
- The lull rows' "relapse" is relabelled. No lull run relapsed after a good release: every lull "relapse" is a run still trapped at the
  lull end (FU-hit < 0.2 over the 300 s before it).

## Headline

1. **R1 (300k pool, pause cap 20 engaged at 1800 s): RESCUED in 20/20 seeds at 1.35 x and 20/20 at 1.65 x, in both batching modes.**
   - The 6 exact client plans (seeds 0-2 at both rates) are all RESCUED as well.
   - No run relapses.
   - The cap is released at 3,490-5,830 s (1.35 x) and 4,050-6,050 s (1.65 x) in the primary mode.
   - After release, every post-release 300-s window has FU-hit >= 0.98 (whole interval >= 0.997), and the uncached-token rate is 0.08-0.11 x the all-miss reference.
   - No session is shed. The same-seed BURST controls are STUCK in 40/40 runs.
   - **What "persists after release" shows.** Release needs both gate queues empty for 300 s, so the cap has already stopped binding when
     rule (c) starts. After release the run stays far from the cap: in-system is >= 20 in a median 0% of the post-release ticks (at most
     1.2% at 1.35 x, 3.8% at 1.65 x), with a post-release maximum of 16-26 sessions. On the 6 exact plans: 0% in 2 runs and 0.2-3.8% in
     the other 4. Rule (c) therefore shows that **the drained state sustains itself with control removed**. It does not test whether
     removing a binding cap is safe; that needs a perturbation after release (not in this protocol).
   - Recovery comes while the cap is on: t_rec is about 500-900 s before t_rel on the exact plans.
2. **R4 prediction of record (native pool, 4.0 x, cap 64, engaged at 2,100 s, cell `R4s_t2100`): RESCUED in 16/20 (primary, mixed)
   and 18/20 (separate); exact seeds 0-2 all RESCUED in both modes; 0 relapses.** The 4 mixed failures are not released by 7,200 s
   (two release at 7,540 and 7,920 s, two are never released by 8,700 s); 18/20 are RECOVERED at 8,700 s.
   Superseded (t_on 2,400, as first specified): **RESCUED in only 13/20 (primary, mixed) and 16/20 (separate).**
   - **That was below the plan's 7/10 threshold in the primary mode, so the plan R1 rule "rethink that cell before submission" applied.
     The lead moved engage to 2,100 s (see "R4 engage time: lead decision" above). The 2,400-s bullets below describe the superseded cell.**
   - None of the failures is a relapse. Every failure is a release after 7,200 s; 19/20 runs are RECOVERED at 8,700 s.
   - Exact plans: seeds 0 and 2 are RESCUED and seed 1 fails (b), with release at 8,640 s (mixed). In the separate mode all three are RESCUED.
   - Engaging at 2,100 s gives 16/20 and 18/20; a cap of 80 gives 0/20.
3. **Smoke (2,400-s run, burst at 300 s, engage at 900 s): release is predicted in 0/10 seeds before 2,400 s, so release is NOT a smoke pass requirement.**
   - The plan requires release only if at least 8/10 seeds release.
   - The other smoke checks are predicted to pass in 10/10 seeds:
     - engage exactly at t_on;
     - 128-164 pauses, each with a matching resume except those still paused at the end;
     - session conservation.
   - About 120 sessions (median) are still gated at 2,400 s; they go unserved in the smoke run.
4. **Remedy comparison: the pause cap trades load for delay. Shedding drains faster only by dropping sessions.** See the table under
   "Remedy comparison". At 300k, the pause cap RESCUES 40/40 with 0 sessions shed, but it delays 346-478 sessions by more than 60 s and
   183-256 by more than 600 s (medians, 1.35 / 1.65 x), for 64-86 delay session-hours. Dropping the over-cap arrivals instead (same cap,
   engage and release rule) also RESCUES 40/40 and releases earlier (2,920-4,160 s), but drops 91-231 sessions. A full stop that ends at
   the pause cap's own release time RESCUES only 11/20 and 16/20 and drops 158-509 sessions. Matching the pause cap with a fixed full
   stop from 1,800 s takes a stop that ends between 4,800 s (13/20) and 5,400 s (20/20), i.e. lasts between 3,000 and 3,600 s, and drops
   328-451 sessions.
5. **AIMD-pause (no mu(n) curve; the gate scope's design with a 60-s decrease holdoff) cures 20/20 and 17/20 at 300k (1.35 / 1.65 x), and 20/20 and 15/20 native (2.5 / 4.0 x), in the primary mode.**
   - It engages 90-110 s after the burst at 300k and 180-560 s after it at the native pool.
   - False alarms without a burst: 0/60 at 1.35-1.65 x, 0/20 at 1.8 x, 2/20 at 2.0 x (the from-empty edge), and 0/40 native.
   - The secondary mode is weaker at the native pool: 5/20 at 4.0 x.
   - Simulation only.

## Blindness scope

- No rescue run existed when these predictions were made, nor when they were revised: no GPU job, no mock run with the rescue gate, and no
  rescue requests.csv. (The client tests run the rescue gate against the in-process mock server; those mock runs have nothing to do with
  the engine and were not read by this driver.)
- Nothing under `results/nova/` was read by the driver except the committed E2 `plan.csv` files. They are inputs, read only to check that the client plans rebuilt here are the ones the GPU runs will replay.
- The same-seed BURST / NOBURST controls of R1 and R4 are committed. Their outcomes were known before this work (6/6 stuck at 300k), so the control rows below are consistency checks, not blind predictions.
- The registered rescue jobs are not yet submitted. Jobs 17166121-17166138 and the frozen Nova clones were not touched.
- Selection disclosure:
  - three of the cells were added after the R4 prediction came out below 7/10, as rethink aids: `R4s_cap80`, `R4s_t2100`, `R4s_rates`. Of these, `R4s_t2100` was then made the R4 prediction of record by the lead's t_on = 2,100 s decision (after the 2,400-s prediction was seen, before any real rescue run); the other two remain sensitivities and change no registration;
  - three comparator cells were added after the review (above): `R1_shed_pause`, `R1_shed_attrition`, `lull_stop_trel`. They are simulation-only and have no GPU cell.
- AIMD disclosure: the primary AIMD was switched from no holdoff to the 60-s holdoff after the first run.
  - Reason: the 60-s holdoff is the controller the gate scope designed and ran ("at most once per 60 s"). With it, this port reproduces the scope's design-time AIMD runs, seeds 0-9, to one 10-s tick.
  - The literal plan S1 (6) parameter list names no holdoff. That variant is reported as a sensitivity. The switch made the reported AIMD result worse (no holdoff: 20/20 and 20/20).
  - AIMD has no GPU cell, so nothing registered depends on this choice.

## What was run

- **Engine:** the calibrated round-6 engine block (`configs/r6_predict.yaml` `engine:`, unchanged: full_reserve, finished-session KV freed at once).
  - The native pool changes only `kv_memory_tokens` to 955,757.
  - PRIMARY `batching: mixed`, SECONDARY `separate_prefill_priority`.
- **Workload:** the record (Stage C) workload.
- **Rates:** each pool in its own engine lambda units. lambda = mult x the registered `lambda_miss_turns_based`:
  - 0.0715340 (300k, `prereg/inputs/2026-10-23`);
  - 0.0717974 (native, `prereg/inputs/2026-10-25-native`).
  - The rule (c) uncached reference is that calibration's `all_miss_uncached_tokens_per_s`: 11,243.2 and 11,282.0 tok/s.
- **Protocol:** burst of 200 sessions over [1200, 1260) s, 8,700-s run. Smoke: burst at 300 s, 2,400-s run.
- **Seeds:**
  - 20 simulator seeds per cell (10 for the smoke and the fixed-lull cells; 20 for `lull_stop_trel`, one per R1 seed).
  - In addition, the exact client plans of seeds 0-2: `agentload.workload.build_open_plan` of `configs/agentload_e2_burst.yaml` with the job's overrides.
  - The rebuilt plans equal the committed E2 BURST / CAPPED / NOBURST `plan.csv` of the same seed and rate. Session ids, origins, arrival times and turn counts are exact; tool-time totals agree within 6e-16 relative. The file sha256 differs only because numpy 1.26 here and numpy 2.x on Nova differ in the last bit of the exponential draws.
  - See `plan_check.csv` for the matched run dirs. The smoke plan has no committed counterpart.
- **Controller** (`GateEngine`, a subclass; engine.py not edited):

  | Item | Value |
  |---|---|
  | Tick | 10 s |
  | Rescue: engage | at the first tick >= t_on |
  | Rescue: release | at the first tick >= t_engage + min_on (600 s; smoke 300 s) at which the gate and resume queues have been empty continuously for release_hold (300 s; smoke 120 s), tracked at event time; no forced release |
  | Pause | a session whose tool call ends while in_system > cap gives up its slot and waits at the front of the gate (FIFO among paused sessions) |
  | Shed (comparators only) | while the cap is engaged and binding, an arriving session is dropped |
  | AIMD | 60-s follow-up hit window, n_min 20, h_low 0.2 / h_high 0.8, beta 0.7, alpha 1, c_min 4, release after 300 s empty |

- **Commit and file hashes:** `meta.json` records git 4d2bba2 with dirty=True, because these files were uncommitted when the run started, plus the sha256 of every file used (now including `src/agentload/config.py`). The committed files must match those hashes. Rerunning on the tagged commit reproduces every number bit for bit on this PC.
- **Reproduce:** `PYTHONPATH="src;." python experiments/r11_predict_rescue.py --workers 6`. The run makes 2,090 runs in about 105 s on 6 workers. The `lull_stop_trel` cell runs in a second phase, after the R1 rescue runs whose release times it uses.

### The registered per-run rule (plan R1), as computed on a simulated run (`gate_control.rescue_measures`)

- **FU-hit:** the share of turns >= 2 completed in a window that hit.
  - In this simulator a hit has cached / prompt = (P_t - 550) / P_t > 0.5, and a miss has 0, so FU-hit is the client's cached/prompt > 0.5 share.
- **(a) VALID:** FU-hit < 0.2 over [t_on - 300, t_on) AND outstanding > 50 at t_on.
  - Outstanding = waiting + running requests + gated + paused sessions, the tick sample at t_on.
- **(b) RELEASED:** t_rel <= 7,200 s.
- **(c) POST-GOOD over [t_rel + 300, 8,700):**
  - every 300-s window has FU-hit >= 0.5. Windows are tiled from t_rel + 300, a short remainder is covered by [8400, 8700) as in `analysis/rescue.py`, and an empty window fails;
  - the whole interval has FU-hit > 0.8;
  - the uncached-token rate is < 0.5 x the reference;
  - trap_v2 RECOVERED holds over the last 300 s: all-turn hit > 0.8 AND mean outstanding < 20.
- **RESCUED** = a and b and c. **RELAPSE** = some post-release window with FU-hit < 0.2.
- **STUCK** (controls; the `analysis/rescue.py` definition) = FU-hit over [t_on, 8,700) < 0.2 AND NOT RECOVERED at the end.
- **cured** (the lull and AIMD rows, which have no fixed t_on) = b and c.
  - For lulls, t_rel = the lull end.
- **t_rec** (descriptive; the same definition as `analysis/rescue.py` `t_recovered`) = the first 10-s tick t >= t_on whose window [t, t + 300) has FU-hit > 0.8 and mean outstanding < 20. The simulator averages the tick samples; `rescue.py` integrates the outstanding count exactly.
- **trapped at release** (descriptive) = FU-hit < 0.2 over the 300 s before t_rel (or the lull end).

### How the GPU release times will be scored against these predictions (`analysis/rescue.py` `score_t_rel`, `T_REL_SCORING`)

- This scores the simulator, not the rescue (descriptive; it is not part of PASS).
- **Band** per rate: the union of the 20-seed [min, max] (primary mode, `cells_mixed.csv`) and the exact-plan values (`runs_mixed.csv`,
  kind = exact). This fixes the pre-review problem that the exact seed-1 value at 1.35 x (3,470 s) lay 20 s below the 20-seed minimum
  (3,490 s):

  | Cell | Rate | 20-seed band | Exact plans (seeds 0, 1, 2) | Scoring band (union) |
  |---|---|---|---|---|
  | R1 | 1.35 x | [3,490, 5,830] | 3,960, 3,470, 3,940 | [3,470, 5,830] |
  | R1 | 1.65 x | [4,050, 6,050] | 4,900, 4,440, 4,280 | [4,050, 6,050] |
  | R4 (t_on 2,100, `R4s_t2100`, of record) | 4.0 x | [3,720, 7,920] | 4,250, 5,180, 4,410 | [3,720, 7,920] |
  | R4 (t_on 2,400, `R4_rescue`, superseded) | 4.0 x | [4,330, 8,160] | 5,860, 8,640, 5,890 | [4,330, 8,640] |

- **Per seed:** each GPU run's t_rel against its own seed's exact-plan prediction, within +-600 s.
- **Expectation:** even a perfect simulator puts one new run inside a 20-run [min, max] only with probability 19/21 (about 0.905), and all 6 R1 runs inside about 55% of the time (0.905^6). The count inside the band is reported against 0.905 x n, not as a pass/fail.
- `python -m analysis.rescue verdict ... --predictions results/r11_predict_rescue/20261030-195231` writes `rescue_t_rel_scoring.csv` and records the two files' sha256.

## R1: rescue-pause, 300k pool, cap 20, t_on 1800 (20 seeds; scoring bands for the GPU runs)

| Mode | Rate | VALID | Released by 7,200 | RESCUED | Relapse | t_rel [min, median, max] | t_rec - t_on, median [min, max] | Max gate + paused | Pauses |
|---|---|---|---|---|---|---|---|---|---|
| mixed | 1.35 x | 20 | 20 | **20** | 0 | [3,490, 4,550, 5,830] | 2,145 [1,180, 3,460] | 114-227 | 110-156 |
| mixed | 1.65 x | 20 | 20 | **20** | 0 | [4,050, 5,085, 6,050] | 2,660 [1,450, 3,570] | 131-231 | 124-165 |
| separate | 1.35 x | 20 | 20 | **20** | 0 | [3,380, 4,465, 5,870] | 2,055 [1,100, 3,500] | 119-232 | 113-157 |
| separate | 1.65 x | 20 | 20 | **20** | 0 | [3,990, 5,195, 6,070] | 2,735 [1,540, 3,460] | 138-216 | 124-168 |

Per-seed predictions on the exact client plans:

| Rate | Seed | Label | t_rel (mixed / separate) | t_rec (mixed / separate) | Pauses (mixed) | End hit (all turns) |
|---|---|---|---|---|---|---|
| 1.35 x | 0 | RESCUED | 3,960 / 4,440 | 3,390 / 3,870 | 122 | 0.93 |
| 1.35 x | 1 | RESCUED | 3,470 / 3,950 | 2,830 / 3,070 | 127 | 0.92 |
| 1.35 x | 2 | RESCUED | 3,940 / 4,190 | 3,420 / 3,630 | 119 | 0.94 |
| 1.65 x | 0 | RESCUED | 4,900 / 4,680 | 4,310 / 4,160 | 141 | 0.94 |
| 1.65 x | 1 | RESCUED | 4,440 / 4,430 | 3,770 / 3,730 | 142 | 0.93 |
| 1.65 x | 2 | RESCUED | 4,280 / 3,860 | 3,390 / 3,300 | 137 | 0.94 |

- At t_on, FU-hit over [1500, 1800) is 0.00 in every R1 run, with 139-168 outstanding (exact plans). So VALID is predicted for every seed.
- Predicted R1 verdict: PASS at both rates (6/6 RESCUED), so the no-shed drain is claimed "at both test points".
- Costs (medians, mixed), against the same-seed controls. Delay = admission wait + pauses per session. Engine latency excludes the gate and pause waits, so it is not the user's wait; the cohort is the sessions arriving in [1200, 3000):

  | Arm | Rate | Pause session-h | Gate wait session-h | Sessions delayed > 60 / 300 / 600 s | Engine-queue session-h after the burst | Median per-window engine p50 latency | Cohort completed | Cohort median duration |
  |---|---|---|---|---|---|---|---|---|
  | Rescue | 1.35 x | 18.9 | 43.5 | 347 / 259 / 183 | 17.2 | 1.4 s | 1.00 | 881 s |
  | BURST control | 1.35 x | 0 | 0 | 0 | 317 | 148 s | 0.96 | 789 s |
  | NOBURST control | 1.35 x | 0 | 0 | 0 | 0.02 | 1.3 s | 1.00 | 61 s |
  | Rescue | 1.65 x | 24.3 | 62.8 | 478 / 385 / 256 | 18.8 | 1.5 s | 1.00 | 966 s |
  | BURST control | 1.65 x | 0 | 0 | 0 | 428 | 172 s | 0.94 | 855 s |
  | NOBURST control | 1.65 x | 0 | 0 | 0 | 0.03 | 1.3 s | 1.00 | 62 s |

  The rescue's cohort sessions take longer than in the BURST control (the wait moved from the engine queue to the gate), but all of them finish, and the sessions arriving after the release see the NOBURST service level.

## R4 of record: rescue-pause, native pool, 4.0 x, cap 64, t_on 2100 (cell `R4s_t2100`)

| Mode | VALID | Released by 7,200 | RESCUED | Relapse | RECOVERED at the end | t_rel [min, median, max] | Max gate + paused |
|---|---|---|---|---|---|---|---|
| mixed | 20 | 16 | **16** | 0 | 18 | [3,720, 4,830, 7,920] | 221-965 |
| separate | 20 | 18 | **18** | 0 | 20 | [3,810, 4,695, 8,590] | 221-728 |

Exact plans (all VALID: FU-hit 0.0 over [1,800, 2,100), 293-327 outstanding at 2,100 s):

| Seed | Mixed | Separate |
|---|---|---|
| 0 | RESCUED, t_rel 4,250 | RESCUED, t_rel 4,680 |
| 1 | RESCUED, t_rel 5,180 | RESCUED, t_rel 4,480 |
| 2 | RESCUED, t_rel 4,410 | RESCUED, t_rel 4,820 |

- Predicted R4 verdict (>= 2/3 RESCUED with stuck controls): PASS in both modes. Per-run rate 0.8 (mixed): P(>= 2 of 3) about 0.90.
- Failures (mixed, seeds 2, 6, 12, 16 of the 20): released late (7,540 and 7,920 s) or never released by 8,700 s (2 runs); in a GPU run
  that is not released, the sessions still gated at 8,700 s go unserved. No relapse.
- After release in-system never reaches 64 (0% of post-release ticks; post-release maximum 38-52 mixed, 29-51 separate).
- Costs (medians, mixed): 153 delay session-hours; 989 / 728 / 404 sessions delayed by more than 60 / 300 / 600 s.
- The non-blind CAPPED-drain check below (GPU drains slower than the simulator at the native pool) still points to later GPU releases
  than predicted; the review's 1.2 x slow-drain sensitivity gave 14/20 at t_on 2,100 (review-reported, not reproduced).

## R4 superseded: rescue-pause, native pool, 4.0 x, cap 64, t_on 2400 (cell `R4_rescue`; not the prediction of record)

| Mode | VALID | Released by 7,200 | RESCUED | Relapse | RECOVERED at the end | t_rel [min, median, max] | Max gate + paused |
|---|---|---|---|---|---|---|---|
| mixed | 20 | 13 | **13** | 0 | 19 | [4,330, 6,410, 8,160] | 275-789 |
| separate | 20 | 16 | **16** | 0 | 19 | [4,830, 5,770, 8,400] | 306-741 |

Exact plans:

| Seed | Mixed | Separate |
|---|---|---|
| 0 | RESCUED, t_rel 5,860 | RESCUED, t_rel 6,460 |
| 1 | **not released by 7,200** (t_rel 8,640; not RESCUED) | RESCUED, t_rel 6,940 |
| 2 | RESCUED, t_rel 5,890 | RESCUED, t_rel 5,540 |

- Predicted R4 verdict (>= 2/3 RESCUED with stuck controls): PASS in both modes, but with seed 1 at risk.
- Over 20 seeds the primary prediction is 0.65, below the 7/10 rethink threshold.
- The failure mode is a slow drain, not a relapse:
  - the gate queue holds up to 789 sessions;
  - with the cap at 64 it drains at most at mu(64) - lambda, about 0.48 - 0.29 = 0.19 sessions/s (registered mu(64) = 0.479), which is about 4,000 s for the largest queues.
  - Every simulated R4 run is released by 8,640 s, so no session is still gated at 8,700 s; in a GPU run that is not released, the sessions still gated at 8,700 s go unserved.
- After release the native run never comes near the cap: in-system >= 64 in 0% of the post-release ticks in every run, post-release maximum 37-46 (mixed) and 31-49 (separate).
- Costs (medians, mixed): 274 delay session-hours, 1,331 / 1,065 / 766 sessions delayed by more than 60 / 300 / 600 s.

**Rethink aids (sensitivities, not registered; 20 seeds, RESCUED counts mixed / separate):**

| Variant | RESCUED (mixed / separate) | Notes |
|---|---|---|
| R4 as registered (4.0 x, cap 64, t_on 2,400) | 13 / 16 | |
| Engage at 2,100 s (VALID window [1,800, 2,100)) | 16 / 18 | Exact seeds 0-2 all RESCUED in both modes, t_rel 4,250-5,180; median t_rel 4,830 (mixed) instead of 6,410; 153 delay session-hours instead of 274 |
| Cap 80 (the runner-up n of the native curve) | 0 / 0 | The cap holds hits (end hit 0.90-0.93) but the gate queue never drains (outstanding 840-1,260 at the end) |
| 2.5 x | 20 / 20 | |
| 3.0 x | 18 / 19 | 1 INVALID seed |
| 3.5 x | 17 / 17 | |

### R4: decision input (decided by the lead: Option A, t_on 2,100; kept as the record of what the decision saw)

- **A non-blind check against committed GPU data points to later GPU releases than predicted, most of all at the native pool.** The
  committed CAPPED runs (a static cap from t = 0, same plans) were replayed in the simulator with the same cap
  (`scratchpad/r11rescue/fixup/capped_check.py`, read-only). Sessions held at the gate at 1,300 / 1,500 / 1,800 / 2,400 s:

  | Pool | Rate | Seed | GPU | Simulator |
  |---|---|---|---|---|
  | 300k | 1.35 x | 0 / 1 / 2 | 180/152/116/57, 179/149/118/39, 179/156/120/80 | 180/151/115/50, 178/148/118/35, 179/155/120/81 |
  | 300k | 1.65 x | 0 / 1 / 2 | 184/160/128/88, 184/159/131/59, 180/165/136/109 | 182/158/124/83, 184/154/129/51, 180/165/133/103 |
  | native | 4.0 x | 0 / 1 / 2 | 146/118/62/0, 160/120/47/0, 136/98/60/0 | 140/100/41/0, 152/106/29/0, 126/84/33/0 |

  At 300k the GPU drains slightly slower than the simulator; at the native pool clearly slower (gated at 1,800 s: 47-62 on GPU, 29-41
  in the simulator; the last gated session is admitted 115-165 s later). A review sensitivity (not in this result dir, not reproduced
  here) that slows the simulator's drain by 1.1 / 1.2 / 1.3 x reported 12 / 9 / 8 of 20 R4 runs RESCUED at t_on 2,400 and 14/20 at
  t_on 2,100 with 1.2 x; R1 kept 20/20 releases by 7,200 s at 1.2 x (19/20 at 1.3 x, 1.65 x).
- **Option A (move engage to 2,100 s):** 16 / 18 of 20 RESCUED. With p = 0.8 per run, P(>= 2 of 3 RESCUED) is about 0.90, against
  about 0.72 at p = 0.65 for t_on 2,400. The review gives 2,100 s as the earliest engage whose VALID window [1,800, 2,100) starts at least
  250 s after the latest GPU trap onset (its estimate: about 1,550 s). Checked here on the committed data: all three native 4.0 x BURST
  controls have FU-hit 0.0 over [1,800, 2,100) and 283-335 outstanding at 2,100 s, so the VALID filter is not expected to bind. Changing it needs three edits together, all owned elsewhere: `configs/agentload_e2_rescue_native.yaml` (`t_on_s`),
  `analysis/rescue.py` `PROFILES["r4"]["t_on_s"]` (which also moves the VALID window), and the native rescue registration. This result
  dir already holds the t_on 2,100 prediction (`R4s_t2100`), which would become the scored R4 prediction.
- **Option B (keep 2,400 s):** keep R4 as an upside cell and state in advance that it is predicted at 0.65 per run, with the slower GPU
  drain pointing lower.

## Smoke (R1 gating job): 300k, 1.65 x, cap 20, 2,400-s run, burst at 300 s, t_on 900, hold 120, min_on 300; 10 seeds plus the exact seed-0 plan

- Engage at 900 s in 10/10 runs (the check needs "within 10 s of t_on").
- 128-164 pauses per run (exact seed 0: 148 pauses and 148 resumes). The check needs at least 10 pauses and 10 resumes.
- Session conservation holds in every run.
- **Release before 2,400 s: 0/10, in both modes.**
  - The gate still holds 46-221 sessions over the last 300 s.
  - So the smoke check must not require a release (the plan threshold is 8/10).
- VALID: FU-hit over [600, 900) = 0.00, with 145-186 outstanding at 900 s. The trap has formed by t_on.

## Remedy comparison (simulation only)

300k pool, both rates, primary mode (secondary in parentheses where it differs). 20 seeds for the cap cells and `lull_stop_trel`, 10 for
the fixed lulls. Delay = admission wait + pauses per session (open ones counted to 8,700 s). "Trapped at the end" = still all-miss over the
300 s before the release / lull end (the pre-review "relapse" of the lull rows: no lull run relapsed after a good release).

| Remedy | Cured / RESCUED (1.35 x, 1.65 x) | Release (or lull end) | Sessions dropped | Sessions delayed > 60 / 600 s (median) | Delay session-h (median) | Cohort completed (median) | Notes |
|---|---|---|---|---|---|---|---|
| Pause cap 20 at 1,800 | 20/20, 20/20 | 3,490-6,050 | 0 | 347 / 183, 478 / 256 | 64, 86 | 1.00, 1.00 | |
| Drop over-cap arrivals, pause (cap 20 at 1,800, same release rule) | 20/20, 20/20 | 2,920-4,160 | 91-231 | 126 / 57, 140 / 64 | 19, 24 | 0.70, 0.67 | Every delay is a pause; t_rec - t_on about 1,100 s |
| Drop over-cap arrivals, no pause | 0/20, 0/20 | 2,400 (the gate is always empty) | 49-87 | 0 | 0 | 0.83, 0.80 | Released at t_engage + min_on while still trapped; never recovers |
| Attrition-only cap 20 at 1,800 (pause false) | 8/20 (7/20), 0/20 | 6,110-8,630 | 0 | 514 / 425, 810 / 669 | 224, 363 | 1.00, 1.00 | Recovers by 8,700 in 20/20 (19) and 10/20 (8); gate up to 204-476 |
| Full stop [1,800, the same seed's pause-cap t_rel) | 11/20, 16/20 | 3,490-6,050 | 158-509 | 0 | 0 | 0.68, 0.65 | Trapped at the end in 14/20 and 8/20 runs |
| Full stop [1,800, 4,200) | 2/10 (1/10), 1/10 | 4,200 | 213-305 | 0 | 0 | 0.69, 0.65 | Trapped at the end in 9/10 and 9/10 |
| Full stop [1,800, 4,800) | 8/10 (7/10), 5/10 | 4,800 | 272-386 | 0 | 0 | 0.69, 0.65 | Trapped at the end in 3/10 (4/10) and 6/10 |
| Full stop [1,800, 5,400) | 10/10, 10/10 | 5,400 | 328-451 | 0 | 0 | 0.69, 0.65 | Trapped at the end in 1/10 at each rate; both recover after it |
| Half rate [1,800, 6,000) | 0/10, 0/10 | 6,000 | 194-258 | 0 | 0 | 0.84, 0.82 | Trapped at the end in 10/10; never recovers |
| AIMD-pause (60-s holdoff) | 20/20, 17/20 (20/20, 12/20) | 3,550-7,650 | 0 | 383 / 189, 637 / 315 | 68, 104 | 1.00, 1.00 | Engages 90-110 s after the burst; min cap 10-16 (8-20) |
| AIMD-pause, no holdoff (sensitivity) | 20/20, 20/20 (20/20, 18/20) | 3,310-6,550 | 0 | | | | Min cap reaches c_min = 4 |

- Same-seed BURST control (no remedy): cohort completed 0.96 / 0.94, engine p50 latency 148 / 172 s; NOBURST: cohort completed 1.00.
- The median engine latency of the remedies (`lat_p50`) excludes the gate and pause waits; it is in `summary.md`, but it is not a
  user-facing cost of the pause cap.
- The completed shares count dropped sessions as not completed.

At the native pool:

| Remedy | Result |
|---|---|
| Attrition-only cap 64 at 2,400 | 0/20 cured in both modes; the gate queue grows to about 1,600 |
| AIMD-pause | 20/20 at 2.5 x and 15/20 at 4.0 x (19/20 and 5/20); engages 180-560 s after the burst; min cap 39-81 against the registered 64 |
| AIMD-pause, no holdoff | 20/20 at both rates (both modes) |

AIMD false alarms (NOBURST, primary / secondary):

| Pool | Rate | Engagements |
|---|---|---|
| 300k | 1.35, 1.5, 1.65 x | 0/60 in both modes |
| 300k | 1.8 x | 0/20 (1/20, at 8,610 s) |
| 300k | 2.0 x | 2/20 (1/20). Mixed: seed 5 engages at 2,880 s and is released, recovered, at 3,750 s; seed 12 engages at 8,630 s and is not RECOVERED at 8,700 s. The secondary 1.8 x engagement (8,610 s) is also in a run not RECOVERED at the end; 2.0 x is at the from-empty edge |
| native | 2.5, 4.0 x | 0/40 |

What this comparison says:
- Deferral versus dropping is the real trade. The pause cap drops nothing and finishes every cohort session, but its cost is waiting:
  64-86 delay session-hours and about 180-260 sessions delayed by more than 10 minutes. Dropping the over-cap arrivals under the same cap
  halves the time to release and cuts the delay to 19-24 session-hours, at the price of 91-231 dropped sessions (about 30% of the cohort).
- Pausing at tool boundaries is the active ingredient: without it, neither the attrition cap (0-8/20) nor dropping arrivals (0/20)
  rescues reliably.
- A full stop is a worse form of dropping: ending it when the pause cap would release rescues only 11/20 and 16/20; a fixed stop needs
  between 3,000 and 3,600 s (13/20 at 3,000, 20/20 at 3,600) and drops 328-451 sessions. A 4,200-s half-rate cut never rescues.
- So the existing "cut the rate below lambda_miss" advice is expensive and slow in this simulator.

## Controls (consistency checks against committed outcomes, not blind)

- BURST (no controller): STUCK in 20/20 runs at 1.35 and 1.65 x (300k), 2.5 and 4.0 x (native), and in the smoke protocol (10/10). This includes the exact plans of seeds 0-2.
- NOBURST: RECOVERED in 20/20 runs at every rate.
- CAPPED drain against the committed GPU CAPPED runs: see "R4: decision input".

## Caveats (simulator)

- The simulator frees a finished session's KV at once (an oracle), and a session's cached prefix is all-or-nothing (full_reserve LRU).
- Real recovery may be slower if resumed sessions miss more than here. A paused session's KV stays as evictable idle KV, as on the engine.
- The GPU drains a capped queue slower than the simulator (see above), so GPU release times are expected at the late edge of the bands.
- Outstanding (rule a, RECOVERED, t_rec) is sampled at the 10-s ticks, not integrated exactly.
- The controller's tick clock splits batched decode runs. All event counts are identical to the uncontrolled engine (tested); time averages differ by about 1e-15 relative.
- The engine's trap-onset times, latencies and the native-pool behaviour are calibrated, not measured, quantities. A miss of these predictions is reported as a miss.
