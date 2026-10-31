# LPM-128 crossing analysis (r11, plan item L1 step 1)

**POST HOC AND CORRELATIONAL.** The 128-request hypothesis was formed after these runs had been read (the r10 review and
the r11 lpm scope), so nothing below was registered and none of it is causal evidence. The causal test is L1 step 2
(cell `sglang-lpminf`: the same stock engine with the constant raised to 1e9 by a job-local hook). It has its own
registration and frozen predictions, and this note does not anticipate its result. Zero GPU.

- Code: `analysis/lpm_crossing.py` (`python -m analysis.lpm_crossing [--out DIR]`)
- Test: `tests/test_lpm_crossing.py`. It reproduces the scout's scratch `queue_vs_128.csv` byte for byte (sha256 `69a64820…`, embedded in the test) and pins every number quoted here.
- Figure: `figures/paper/fig_lpm_crossing.py` → `paper/figs/fig_lpm_crossing.pdf` (7.0 x 4.5 in, double column).
- Inputs: git-tracked pulls only.
  - `results/nova/r7_native_grid_vllm_pulled_20261025-145126`: the exploratory grid, BURST arm only. Cells `sglang-fcfs-r0`, `sglang-lpm-r0` and `sglang-lpm-r1`; jobs 17097086-17097103; code 6d0dad7.
  - `results/nova/e2_170933xx_pulled_20261025-144558`: the registered E2 cell `sglang-fcfs-r1`, BURST arm. Jobs 17093387, -90, -93, -96, -99 and 17093402; code d279b7b.
  - States are the committed trap_v2 verdicts: `agentload_analysis_burst2/20261025-1442{30,33,36}` and `20261025-144012`, the same files F6 reads.
- Setup: SGLang 0.5.22, Qwen2.5-7B-Instruct, one A100 80GB PCIe, 300k-token KV pool. A 200-session burst arrives at 1200 s. λ = 1.35 and 1.65 × λ_ref (0.07153 sessions/s), seeds 0-2, 8700-s runs. Each run is one Nova job, and each job log's `launching SGLang: policy=… refresh=… lpm_inf=0` line matches the run's cell label (the test checks this).

## 1. The engine mechanism

The file is `sglang/srt/managers/schedule_policy.py`, SGLang 0.5.22. The installed copy is in `/work/classtmp/avalse/swapp/envs/sglang/lib/python3.11/site-packages/`. Its md5 is `b8ec334ac1ed028e3c176022ea1f9143`, the same as the v0.5.22 tag copy. I re-read it on Nova on 2026-10-30 with `md5sum` and `sed -n`.

- **:132-133** sets the constant: `# Arbitrary; bounds per-round prefix work on the waiting queue.` / `WAITING_QUEUE_PREFIX_MATCH_MAX = 128`.
- **:300-311** is `_determine_active_policy`. It returns `CacheAgnosticPolicy.FCFS` when `self.policy` is LPM or HRRN and `len(waiting_queue) > WAITING_QUEUE_PREFIX_MATCH_MAX`, strictly more than 128. The comment at :309 reads "Turn off the expensive prefix matching and sorting when the #queue is large."
- **:215, :227, :260**: `calc_priority` takes the *active* policy (215) but branches on the *configured* one (227). In fallback, control therefore reaches the cache-agnostic branch, where FCFS is `pass` (260). There is no prefix match and no re-sort, so the queue keeps its last LPM order and new arrivals go to the end.
- **:276-297**: `_touch_waiting_prefixes(active policy)` returns at once while the active policy is cache-aware. The waiting-prefix refresh of the `-r1` cells therefore acts on an LPM run only during fallback, over the window `waiting_queue[:128]` (297).
- No env var or server flag sets the constant.
- The gauge `sglang:num_queue_reqs` is `len(scheduler.waiting_queue)` at the scheduler's last stats tick (`scheduler_components/metrics_reporter.py`, read on Nova the same day). The client scrapes it every 5 s, and the test checks that every gap is within 10% of 5 s. The engine tests the condition on every scheduling pass, so a 5-s sample can miss short excursions above 128.

## 2. Definitions

- **Crossed** means a sustained crossing: 60 consecutive 5-s samples above 128 after the burst, about 300 s (the scout's `crossing.py`). `t_cross` is the first sample of that stretch, and `t_first_gt128` is the first single sample above 128.
- **Collapsed** is the L1 endpoint: token hit below 0.05 over [5700, 8700) s. Token hit is cached / prompt tokens of ok requests, pooled by completion time. The scout's mean of 300-s bins gives the same classification for every run.
- **hit_pre / hit_post** is token hit over [t_cross − 600, t_cross), then [t_cross + 300, t_cross + 900).
- **gnb** is the scheduler cost: increments of `sglang:scheduler_stage_seconds_total{category="get_next_batch_to_run"}` per wall second. LPM's prefix matching is the expensive part of that stage. The regime split uses scrape intervals whose starting queue is in [20, 128] or above 128.
- **t_hit_floor60** is the onset of the all-miss floor: the start of the first 60-s bin after the burst from which every later 60-s bin up to 8700 s has token hit below 0.05.
- **s_q80_128** is the time after the burst with 80 ≤ queue ≤ 128, i.e. congested but still LPM-ordered.

## 3. Crossing table: the 12 stock-LPM BURST runs

Times are in s since run start. `r0` means waiting-prefix refresh off and `r1` means on.

| cell | λ mult | seed | job | queue max | first > 128 | longest > 128 (s) | s at q 80-128 | t_cross | hit_pre | hit_post | floor onset (60 s) | gnb pre | gnb post | hit [5700, 8700) | collapsed | trap_v2 state |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lpm-r0 | 1.35 | 0 | 17097088 | 244 | 3410 | 3620 | 2310 | **3755** | 0.175 | 0.010 | 4560 | 0.0095 | 0.0033 | 0.000 | yes | trapped |
| lpm-r0 | 1.35 | 1 | 17097094 | 118 | - | 0 | 3855 | - | - | - | - | - | - | 0.783 | no | recovered |
| lpm-r0 | 1.35 | 2 | 17097100 | 116 | - | 0 | 1335 | - | - | - | - | - | - | 0.939 | no | recovered |
| lpm-r0 | 1.65 | 0 | 17097091 | 345 | 2360 | 5650 | 1655 | **3050** | 0.299 | 0.000 | 3000 | 0.0105 | 0.0028 | 0.000 | yes | trapped |
| lpm-r0 | 1.65 | 1 | 17097097 | 287 | 2350 | 5800 | 1535 | **2900** | 0.137 | 0.000 | 2940 | 0.0108 | 0.0029 | 0.000 | yes | trapped |
| lpm-r0 | 1.65 | 2 | 17097103 | 121 | - | 0 | 1685 | - | - | - | - | - | - | 0.816 | no | recovered |
| lpm-r1 | 1.35 | 0 | 17097087 | 126 | - | 0 | 3835 | - | - | - | - | - | - | 0.707 | no | recovered |
| lpm-r1 | 1.35 | 1 | 17097093 | 117 | - | 0 | 3330 | - | - | - | - | - | - | 0.795 | no | recovered |
| lpm-r1 | 1.35 | 2 | 17097099 | 133 | 2815 | 25 | 4745 | - | - | - | - | - | - | 0.508 | no | draining |
| lpm-r1 | 1.65 | 0 | 17097090 | 334 | 2525 | 5820 | 1520 | **2880** | 0.310 | 0.000 | 2880 | 0.0117 | 0.0030 | 0.000 | yes | trapped |
| lpm-r1 | 1.65 | 1 | 17097096 | 290 | 1865 | 6005 | 1245 | **2695** | 0.132 | 0.000 | 2640 | 0.0111 | 0.0030 | 0.000 | yes | trapped |
| lpm-r1 | 1.65 | 2 | 17097102 | 122 | - | 0 | 3785 | - | - | - | - | - | - | 0.442 | no | indeterminate |

**Runs that crossed (5 of 5 collapsed).** In all five, token hit fell from 0.13-0.31 in the 600 s before `t_cross` to 0.000-0.010 in [+300, +900) s. It stayed at 0.000-0.003 over [+900, +1800) s, and every one of the five ends `trapped` with hit 0.000.

**Runs that did not (none of 7 collapsed).** None of the seven held above 128: their queue maximum was 116-126, apart from lpm-r1 1.35 × s2, which touched 133 for 25 s. The outcomes were 5 recovered, 1 draining and 1 indeterminate, with hit over [5700, 8700) of 0.44-0.94. These runs were not idle. They spent 1335-4745 s congested at a queue of 80-128, with token hit of 0.25-0.56 over [1500, 4500) s, and LPM ordering held them in a partial-hit state without collapsing.

**FCFS reference (12 runs, cells fcfs-r0 and fcfs-r1).** Every run collapsed (hit_eval 0.000; 10 trapped, 2 indeterminate). These runs show what an all-miss engine's queue does on its own:
- the all-miss floor begins in the first minute after the burst (onset 1260 s in 12 of 12);
- the queue first passes 128 only at 1415-3075 s, 2.6 to 30 min later;
- the queue maximum reaches 193-356, and scheduler cost is 0.0027-0.0038 s/s throughout.

## 4. Fisher test, and why it is weak evidence

Over the 12 stock-LPM runs, sustained crossing against collapse gives:

| | collapsed | not collapsed |
|---|---|---|
| crossed (≥ 300 s above 128) | 5 | 0 |
| did not cross | 0 | 7 |

The one-sided Fisher exact p is 1/C(12,5) = **1/792 = 0.0013**. This is an association. Three caveats limit it, and any text that quotes the p must carry all three.

1. **Dependence.** The 12 runs are not 12 independent units.
   - lpm-r0 and lpm-r1 replicate each other on the same arrival stream: `plan.csv` is byte-identical for each (rate, seed) across all four cells.
   - They differ only by the refresh flag, which is inert until the queue passes 128 (§1).
   - Rate is a confounder: at 1.65 × the queue crossed in 4 of 6 runs, and at 1.35 × in 1 of 6.
   - Stratified by rate (an exact conditional test, strata 1.35: [[1,0],[0,5]] and 1.65: [[4,0],[0,2]]), p = 1/90 = **0.011**.
   - With one unit per arrival stream (crossed or collapsed in either replicate: [[3,0],[0,3]]), p = 1/20 = **0.05**.
   - The honest effective sample is six arrival streams and one discordant pair (§6).
2. **Reverse causation.** A collapsed engine's queue grows past 128 by itself. The FCFS runs show it directly: there the threshold means nothing, every run reached the all-miss floor within a minute of the burst, and every queue passed 128 2.6-30 min later.
   - So "collapsed ⇒ eventually crossed" holds whatever causes the collapse, and the 5/0 row would look the same if the collapse came first.
   - The informative half of the table is the 0/7 row: no stock-LPM run collapsed while its queue stayed at or below 128, although seven of them spent 22-79 min congested between 80 and 128.
3. **A common cause.** A longer queue means longer waits, and longer waits push a session's gap past the pool's residence time under any ordering.
   - A queue that grows past 128 for any reason could therefore tip LPM over without the fallback playing a part.
   - These data cannot separate "the fallback switched off LPM" from "the queue reached a length at which LPM would fail anyway".
   - Step 2 separates them: with the constant at 1e9, LPM keeps ordering at any queue length.

## 5. Timing around the crossing (60-s bins)

From `event_time` and panel (c) of the figure:

| run | first > 128 | t_cross | share of samples > 128 in between | hit in the 600 s before | floor onset | median latency before t_cross (s) |
|---|---|---|---|---|---|---|
| lpm-r0 1.35 s0 | 3410 | 3755 | 0.54 | 0.175 | 4560* | 132 |
| lpm-r0 1.65 s0 | 2360 | 3050 | 0.17 | 0.299 | 3000 | 127 |
| lpm-r0 1.65 s1 | 2350 | 2900 | 0.18 | 0.137 | 2940 | 119 |
| lpm-r1 1.65 s0 | 2525 | 2880 | 0.23 | 0.310 | 2880 | 114 |
| lpm-r1 1.65 s1 | 1865 | 2695 | 0.22 | 0.132 | 2640 | 114 |

\* In lpm-r0 1.35 s0, hit was 0.00-0.02 in each minute from t_cross − 60 s to t_cross + 240 s. One later minute reached 0.05 or more, so the strict onset rule places it at 4560 s.

- In all five, the queue made excursions above 128 for 345-830 s before the sustained crossing. During them the hit stayed at its congested level: brief excursions did not collapse it.
- The hit fell in the last minutes before `t_cross`, as the queue spent more of each minute above 128: 42-92% of samples in the last minute. Hit was 0.00-0.05 in the minute starting at `t_cross` in all five runs, and already 0.00-0.02 in the minute before in three. In four runs the floor began between 55 s before and 40 s after `t_cross`.
- This order (excursions first, collapse after) is the reverse of FCFS, where the collapse comes first. It fits the fallback mattering.
- It does not establish an order at the scale that matters. Hit is binned by completion, and a request's cache outcome is fixed at admission, somewhere between send and completion. The median send-to-complete latency just before `t_cross` was 114-132 s, about the size of the gap being measured.
- The common-cause reading of §4 predicts the same picture.

## 6. The same-seed natural experiment (1.35 ×, seed 0)

The arrival plans are byte-identical (`plan.csv` sha256 `c9195aad…`). Job 17097088 is lpm-r0 (refresh off) and job 17097087 is lpm-r1 (refresh on).

- **lpm-r1** peaked at **126** (5-s samples) and never exceeded 128. It recovered: hit_eval 0.707, with 300-s hit above 0.9 from the 7800-s bin on.
- **lpm-r0** first exceeded 128 at 3410 s, held above it from 3755 s and was trapped (hit_eval 0.000).
- Until r0 first passed 128, the two runs had the same effective scheduler: refresh is inert while LPM is active (§1). The burst-time queue samples (1240-1295 s) are nearly identical.
- So the same arrivals landed on either side of the threshold, by a margin of a few requests, and the outcome followed the side.

| 300-s bin from | queue r0 | queue r1 | hit r0 | hit r1 |
|---|---|---|---|---|
| 1200 | 71.6 | 72.0 | 0.239 | 0.257 |
| 1500 | 100.2 | 99.2 | 0.104 | 0.159 |
| 1800 | 106.1 | 103.8 | 0.106 | 0.181 |
| 2100 | 103.5 | 101.9 | 0.120 | 0.177 |
| 2400 | 108.1 | 103.6 | 0.161 | 0.220 |
| 2700 | 108.7 | 98.6 | 0.208 | 0.291 |
| 3000 | 110.0 | 96.3 | 0.214 | 0.281 |
| 3300 | 123.0 | 112.5 | 0.207 | 0.312 |
| 3600 | 133.6 | 112.8 | 0.043 | 0.384 |
| 3900 | 141.6 | 110.8 | 0.000 | 0.418 |

**This pair is not a clean natural experiment.**
- The runs had separated long before r0 first passed 128. r0's token hit was 0.05-0.10 lower than r1's in every 300-s bin from 1500 s (the test checks this), and its queue was 1-14 requests higher in each of those bins.
- The cause of that early divergence is not in the data. Run-to-run timing nondeterminism is one candidate. Another is sub-5-s excursions above 128 that the gauge cannot see, during which the refresh flag would act.
- r0 may therefore already have been on the losing path when it crossed. The pair shows that one arrival stream can end on either side of 128 and that the outcome followed the side. It does not show that crossing caused the outcome.
- It is the only discordant pair: the other five streams agree in both replicates (crossed and collapsed at 1.65 × seeds 0-1; neither at 1.35 × seeds 1-2 and 1.65 × seed 2).

## 7. Scheduler cost drops at the crossing (the fallback engaged)

These figures come from `get_next_batch_to_run` in seconds per wall second.

| | range over runs | mean |
|---|---|---|
| stock LPM, queue in [20, 128] (12 runs) | 0.0084-0.0129 | **0.011** |
| stock LPM, queue > 128 (the 5 crossing runs) | 0.0028-0.0031 | **0.003** |
| FCFS, any queue ≥ 20 (12 runs) | 0.0027-0.0038 | |
| at the crossing: [t_cross − 600, t_cross) | 0.0095-0.0117 | 0.0107 |
| at the crossing: [t_cross + 300, t_cross + 900) | 0.0028-0.0033 | 0.0030 |

- Pooled by queue length (figure, panel d), LPM's cost rises roughly linearly with the queue up to 128, to about 0.0125 s/s in the 113-128 bin. In the next bin, 129-144, it drops to the FCFS level and stays there.
- This is the manipulation check: in every crossing run, prefix matching stopped when the queue passed 128, exactly as the source says.
- It shows that the fallback engaged. It says nothing about whether the fallback caused the collapse.
- It also sizes the cost of removing the fallback, as plan O3 asks. A least-squares fit over the LPM-active bins (`lpm_cost_fit`) gives 0.0029 s/s + 0.0082 s/s per 100 waiting requests. If that stays linear, it is about 0.03 s/s (3% of wall time) at a queue of 350, the largest seen here.

## 8. What this supports, and the wording it allows

Supported (post hoc, correlational):
- Stock SGLang LPM silently becomes FCFS-ordered whenever more than 128 requests wait (source lines above). The fallback engaged in every run whose queue held above 128 (§7).
- In these 12 runs, stock LPM never collapsed while its queue stayed at or below 128 (0/7). It always collapsed once the queue held above 128 for 300 s (5/5). Collapse came at the time of the sustained crossing, never before the first excursion.

Not supported:
- "The fallback causes the collapse."
- "Pure LPM would not collapse."
- Any p-value without the dependence and reverse-causation caveats.

Suggested paper wording (5.6): "Stock LPM recovered or drained in every run whose waiting queue stayed at or below SGLang's hard-coded 128-request prefix-matching limit (7/7), and fell into the all-miss state in every run whose queue held above it (5/5). Above 128 the scheduler silently reverts to FCFS order, and its scheduling cost drops to the FCFS level at the crossing. This association is post hoc; collapse also inflates the queue, so it does not by itself show that the fallback causes the collapse (§L1 step 2)." The plan's sentence "stock LPM escapes only while its queue stays under 128" is acceptable as a description of these 12 runs. It should not be read as a mechanism claim until step 2 reports.

## 9. Reproduce

```
cd <worktree>
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" -m analysis.lpm_crossing --out <scratch dir>
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" -m pytest -q tests/test_lpm_crossing.py
PYTHONPATH="src;." "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" figures/paper/fig_lpm_crossing.py
```

Each step takes about 5-7 s on the PC: the 24 `metrics.csv` files, about 1.1 GB, are pre-filtered by line. The figure reads only git-tracked, unmodified files through `_style.src` and rebuilds byte-identically. It is not yet listed in `figures/paper/build_all.sh` or `paper/figs/README.md`, which belong to other agents.
