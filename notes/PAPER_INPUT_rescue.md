# PAPER INPUT: rescue cells R1 and R4 (trap, rescue, release, persist)

Branch `r11/rescue`. Written 2026-10-31 (Sat), after all nine registered runs and the smoke job ended. Every number below has its
source file; `$P` = `results/nova/rescue_1716896x_pulled_20261031-070502`.

## Decisions (registered, decisive)

| Cell | Registration | Verdict | RESCUED | Relapse | Not released by 7,200 s | Failed sessions | Same-seed BURST stuck | Decisive |
|---|---|---|---|---|---|---|---|---|
| R1 `sglang-fcfs-r1-rescue` (300k pool, cap 20 engaged at 1,800 s), 1.35 x | `configs/agentload_prereg_2026-10-31_rescue.yaml` | **PASS** | 3/3 | 0 | 0 | 0 | 3/3 | yes |
| R1, 1.65 x | same | **PASS** | 3/3 | 0 | 0 | 0 | 3/3 | yes |
| R1 family (6 runs) | same | **PASS: no-shed drain at both test points** | 6/6 | 0/6 | 0/6 | 0 | 6/6 | yes |
| R4 `sglang-fcfs-r1-rescue-native` (native pool, cap 64 engaged at 2,100 s), 4.0 x | `configs/agentload_prereg_2026-10-31_rescue_native.yaml` | **PASS: no-shed drain at the native pool** | 3/3 | 0/3 | 0/3 | 0 | 3/3 | yes |

- Verdicts: `$P/results/agentload_analysis_rescue_r1/20261031-071720/rescue_verdict.json` (commit `be50593`) and
  `$P/results/agentload_analysis_rescue_r4/20261031-071748/rescue_verdict.json` (commit `454ff7a`). Both were run on a clean tree
  (`meta.json` git dirty = false) with `python -m analysis.rescue verdict --profile r1|r4 --prereg <registration> --e2-config
  <rescue e2 config> --predictions results/r11_predict_rescue/20261030-195231`, exactly as the registrations' rule text specifies.
- Precedence: REFUTED (>= 2 of 6 RELAPSE or >= 2 of 6 not released by 7,200 s for R1; >= 2 of 3 RELAPSE for R4) takes precedence over
  PASS. Neither refutation condition is met (0 relapses, 0 late releases), so PASS stands. The no-shed part of the claim needs 0 failed
  sessions in the counted runs: 0 failed in all nine, so it is not withheld. No run is INVALID; no pairing, protocol or registration
  problem (`protocol_problems`, `pairing_problems`, `registration_blockers` all empty; `rejected_runs` empty).
- Registration tag `r11-rescue-reg` = `f0bc3ad` (committer 2026-10-30 22:10:47 CDT; GitHub push 22:39:02 CDT, activity API
  `2026-10-31T03:39:02Z`); all ten jobs submitted 23:01:12-13 CDT, after the push.

## Jobs and data

- Jobs (sacct `$P/sacct_1716896x.txt`; all COMPLETED 0:0, account f2026.coms.6250.02, 1 A100 each, from the frozen Nova clone
  `$W/repo_r11_rescue` at `f0bc3ad`): smoke 17168965 (nova22-gpu-2, 23:24-00:08); R1 17168966 (1.35 s0, 02:23-04:53, gpu-3), 17168967
  (1.65 s0, 04:20-06:50, gpu-3), 17168968 (1.35 s1, 03:34-06:03, gpu-2), 17168969 (1.65 s1, 04:20-06:50, gpu-3), 17168970 (1.35 s2,
  04:12-06:41, gpu-1), 17168971 (1.65 s2, 04:20-06:50, gpu-3); R4 17168972-74 (s0-2, 04:21-06:57, gpu-2 / gpu-1 / gpu-2). Hardware in
  every meta.json: "NVIDIA A100 80GB PCIe, 81920 MiB" (the registered string).
- Run dirs `$P/results/agentload_e2_burst/`: 1.35 x s0/s1/s2 = `20261031-022506` / `-033519` / `-041322`; 1.65 x s0/s1/s2 =
  `20261031-042156` / `-042159-1` / `-042159`; 4.0 x s0/s1/s2 = `20261031-042315` / `-042504` / `-042858`; smoke `20261030-232541`.
  Job-log dirs `$P/results/nova_job_logs/<job>-<ts>/` (check-run JSON `rescue_check_m<mult>_s<seed>.json`, server log, canaries).
- In-job check-run (`analysis.rescue check-run`, mechanical, outcome-blind): **ok in all 10 jobs** (smoke with `--smoke`: >= 10
  pauses / resumes and 0 request errors; it did not require a release, as bundle 3 predicted 0/10 releases in the smoke protocol; the
  smoke run ended with 142 sessions gated, 20 in the engine, 0 failed).
- Pull: archive sha256 `2ac2309c2d7b98dc9c07cfa7803c61c3ec63d50c28d7d3640c203f47adbe45c5`, equal on both ends, remote copy deleted;
  commit `c6ea41e`.
- Controls (common random numbers, same plan.csv sha256 for BURST, NOBURST plan = rescue plan minus the burst): 300k
  `results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/` BURST 1.35 x s0-2 `20261024-153951`, `-161333`,
  `-211100`; 1.65 x `20261024-155120`, `-184132`, `20261025-000043`; NOBURST 1.35 x `20261024-155125`, `-161834`, `-211253`; 1.65 x
  `20261024-160218`, `-184259`, `20261025-000053`; CAPPED (descriptive only) 1.35 x `20261024-155130`, `-182448`, `-213121`; 1.65 x
  `20261024-161207`, `-184758`, `20261025-000819`. Native `results/nova/e2_native_vllm_burst_pulled_20261026-101256/results/agentload_e2_burst/`
  4.0 x BURST `20261025-174409`, `-201340`, `-205154`; NOBURST `20261025-174445`, `-201333-1`, `-224309`; CAPPED `20261025-175810`,
  `-201337`, `-224304`.

## Per-run rule (from `rescue_runs.csv` of the two verdict dirs)

| Rate | Seed | FU-hit [t_on-300, t_on) | Outstanding at t_on | t_rel (s) | Post windows (min FU-hit) | Post FU-hit | Uncached / all-miss | End hit / outstanding | Relapse | Outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.35 | 0 | 0.000 (612 turns) | 146 | 4,550 | 13 (1.000) | 1.000 | 0.086 | 0.929 / 1.8 | no | RESCUED |
| 1.35 | 1 | 0.000 (621) | 148 | 3,980 | 15 (1.000) | 1.000 | 0.080 | 0.923 / 1.2 | no | RESCUED |
| 1.35 | 2 | 0.000 (609) | 139 | 4,400 | 14 (0.997) | 0.999 | 0.090 | 0.937 / 1.4 | no | RESCUED |
| 1.65 | 0 | 0.000 (619) | 172 | 4,920 | 12 (0.998) | 1.000 | 0.108 | 0.943 / 3.1 | no | RESCUED |
| 1.65 | 1 | 0.000 (614) | 171 | 4,430 | 14 (1.000) | 1.000 | 0.100 | 0.932 / 1.9 | no | RESCUED |
| 1.65 | 2 | 0.000 (594) | 143 | 4,570 | 13 (0.938) | 0.994 | 0.117 | 0.935 / 2.1 | no | RESCUED |
| 4.0 (native) | 0 | 0.000 (588) | 324 | 6,000 | 8 (1.000) | 1.000 | 0.269 | 0.944 / 14.2 | no | RESCUED |
| 4.0 | 1 | 0.000 (581) | 322 | 5,980 | 9 (1.000) | 1.000 | 0.233 | 0.926 / 6.5 | no | RESCUED |
| 4.0 | 2 | 0.002 (570) | 298 | 6,140 | 8 (1.000) | 1.000 | 0.240 | 0.939 / 8.5 | no | RESCUED |

- VALID window [1,500, 1,800) for R1 and [1,800, 2,100) for R4; engage at t_on + 0.0003-0.0024 s in every run; hardware rule met in all.
- Post-release interval [t_rel + 300, 8,700): 3,480-4,420 s long (R1), 2,260-2,420 s (R4); no window without follow-up turns.
- Gate activity: pauses 124 / 130 / 121 (1.35 x), 141 / 143 / 138 (1.65 x), 251 / 240 / 220 (R4), each with a matching resume (0 paused
  at the end). Max gated + paused 134-148 (1.35 x), 145-159 (1.65 x), 387-397 (R4).
- Recovery happens while the cap is on: t_recovered (first 10-s tick with FU-hit > 0.8 and outstanding < 20 over the next 300 s) =
  3,960 / 3,300 / 3,860 and 4,330 / 3,730 / 3,920 s (R1), 5,670 / 5,680 / 5,790 s (R4); t_rel - t_recovered = 540-700 s (R1), 320-350 s (R4).
  The cap last held a session back 301-310 s before each release (the 300-s hold).
- The hits come back at once; the backlog takes the time. The first 60-s bin after the engage with FU-hit >= 0.8 starts at 1,920 s in
  all six R1 runs and at 2,220 s in all three R4 runs (`hit_onset.csv`): the bin [t_on + 120, t_on + 180). Over 300-s bins during the capped
  phase FU-hit is 0.56-1.00 (R1) and dips to 0.47-0.63 at 2,700-3,300 s in R4 while the native backlog (engine + gate + paused) peaks
  at about 430; it reaches 1.00 once the queue drains (table below).

## Persistence after release (`$P/results/rescue_paper_data/20261031-071938/persistence.csv`, descriptive)

Same interval [t_rel + 300, 8,700) for the rescue run and its same-seed controls, at the same arrival process (same plan):

| Rate | Seed | Rescue FU-hit / mean outstanding | BURST FU-hit / outstanding | NOBURST FU-hit / outstanding | Max in-system after release (cap) | Share of post-release time at >= cap | End outstanding: rescue / BURST / NOBURST | Unfinished at 8,700: rescue / BURST / NOBURST |
|---|---|---|---|---|---|---|---|---|
| 1.35 | 0 | 1.000 / 2.0 | 0.000 / 219 | 1.000 / 2.0 | 16 (20) | 0.0% | 1.8 / 264 / 1.8 | 10 / 270 / 10 |
| 1.35 | 1 | 1.000 / 1.9 | 0.000 / 195 | 1.000 / 1.9 | 17 (20) | 0.0% | 1.2 / 200 / 1.2 | 7 / 206 / 7 |
| 1.35 | 2 | 0.999 / 2.2 | 0.000 / 208 | 0.999 / 2.2 | 20 (20) | 0.2% | 1.4 / 249 / 1.4 | 5 / 256 / 5 |
| 1.65 | 0 | 1.000 / 2.8 | 0.000 / 317 | 1.000 / 2.8 | 23 (20) | 1.4% | 3.1 / 363 / 3.2 | 14 / 370 / 14 |
| 1.65 | 1 | 1.000 / 2.5 | 0.000 / 272 | 1.000 / 2.5 | 21 (20) | 0.7% | 1.9 / 313 / 1.9 | 11 / 320 / 11 |
| 1.65 | 2 | 0.994 / 2.8 | 0.000 / 294 | 0.991 / 3.1 | 27 (20) | 4.5% | 2.1 / 352 / 2.2 | 11 / 361 / 11 |
| 4.0 | 0 | 1.000 / 11.8 | 0.000 / 1,178 | 1.000 / 11.8 | 55 (64) | 0.0% | 14.2 / 1,369 / 14.3 | 36 / 1,404 / 36 |
| 4.0 | 1 | 1.000 / 8.9 | 0.000 / 1,133 | 1.000 / 8.8 | 43 (64) | 0.0% | 6.5 / 1,276 / 6.5 | 27 / 1,307 / 27 |
| 4.0 | 2 | 1.000 / 8.8 | 0.000 / 1,161 | 1.000 / 8.8 | 49 (64) | 0.0% | 8.5 / 1,311 / 8.5 | 23 / 1,331 / 23 |

- With the cap removed the system stays in the good state at the same load for the rest of the run: 3,780-4,720 s (R1) and 2,560-2,720 s
  (R4) of uncapped operation, no relapse. The same-seed BURST control, which got the same burst and was never capped, is at FU-hit 0.000
  over the same interval with 195-317 (R1) and 1,133-1,178 (R4) requests and sessions outstanding and still growing to the end.
- After release the rescue run is indistinguishable from its NOBURST control: same follow-up turn counts in the interval within 0-7,
  same hit, outstanding and engine latency (1.38-1.55 s rescue vs 1.38-1.67 s NOBURST at 300k; 2.13-2.49 vs 2.13-2.51 s native; BURST
  159-231 s and 523-532 s), and the same number of sessions unfinished at 8,700 s. Every burst session completed (rescue completed =
  NOBURST completed + 200 in every pair).
- Caveat (registered rule text): release needs both gate queues empty for 300 s, so rule (c) starts after the cap has stopped binding.
  "Persists" therefore means the drained state sustains itself with control removed; the uncapped run rose above the cap for 0-4.5% of
  the post-release time at 300k (maximum 27 against 20) and never reached 64 at the native pool (maximum 43-55). It does not test a
  release while the cap still binds.

## User-facing costs (`costs.csv`, `costs_summary.csv` of the same dir; `rescue_pairs.csv` of the verdict dirs)

Per seed ranges (s0-s2). Delay = admission wait + pauses per session. Engine latency excludes the gate and pause waits. Cohort = sessions
arriving in [1,200, 3,000).

| Arm | Rate | Completed share | Unfinished at 8,700 | Sessions paused (mean pause per paused session) | Sessions gated (mean / max admission wait) | Delay session-h | Delayed > 60 / 600 s | Cohort completed / median duration | FU-hit after t_on |
|---|---|---|---|---|---|---|---|---|---|
| Rescue | 1.35 | 0.991-0.995 | 5-10 | 121-130 (438-569 s) | 196-244 (415-682 s / 919-1,290 s) | 38-65 | 300-358 / 94-211 | 1.00 / 630-909 s | 0.94-0.95 |
| BURST | 1.35 | 0.755-0.805 | 206-270 | 0 | 0 | 0 | 0 / 0 | 0.96-0.98 / 793-916 s | 0.000 |
| NOBURST | 1.35 | 0.989-0.994 | 5-10 | 0 | 0 | 0 | 0 / 0 | 1.00 / 62-68 s | 1.00 |
| CAPPED (E2, cap 20 from t = 0) | 1.35 | 0.991-0.995 | 5-10 | 0 | 349-404 (410-456 s / 853-965 s) | 40-51 | 307-375 / 88-123 | 1.00 / 478-515 s | 0.99-1.00 |
| Rescue | 1.65 | 0.989-0.991 | 11-14 | 138-143 (420-522 s) | 295-344 (408-600 s / 908-1,087 s) | 50-78 | 410-466 / 109-204 | 1.00 / 684-874 s | 0.95-0.96 |
| BURST | 1.65 | 0.714-0.743 | 320-370 | 0 | 0 | 0 | 0 / 0 | 0.94-0.96 / 886-937 s | 0.000 |
| NOBURST | 1.65 | 0.987-0.990 | 11-14 | 0 | 0 | 0 | 0 / 0 | 1.00 / 63-68 s | 1.00 |
| CAPPED | 1.65 | 0.990-0.991 | 11-13 | 0 | 439-543 (405-471 s / 872-985 s) | 49-65 | 399-500 / 121-187 | 1.00 / 508-633 s | 0.99-1.00 |
| Rescue | 4.0 native | 0.987-0.992 | 23-36 | 220-251 (386-493 s) | 1,050-1,101 (643-683 s / 1,268-1,318 s) | 222-230 | 1,259-1,296 / 629-683 | 1.00 / 1,138-1,146 s | 0.97 |
| BURST | 4.0 | 0.499-0.524 | 1,307-1,404 | 0 | 0 | 0 | 0 / 0 | 0.76-0.80 / 1,004-1,099 s | 0.000 |
| NOBURST | 4.0 | 0.986-0.991 | 23-36 | 0 | 0 | 0 | 0 / 0 | 1.00 / 66-73 s | 1.00 |
| CAPPED (cap 64 from t = 0) | 4.0 | 0.987-0.992 | 23-36 | 0 | 408-448 (141-180 s / 262-361 s) | 18-21 | 354-380 / 0 | 1.00 / 180-200 s | 1.00 |

- Pause time per session (all sessions): 53-63 s (1.35 x), 48-57 s (1.65 x), 30-44 s (R4); the longest single pause total 818-1,240 s.
- Total waiting (pause + admission + engine request latency, session-hours): rescue 73-102 (1.35 x), 87-116 (1.65 x), 336-347 (R4);
  BURST 377-399, 489-535, 1,548-1,588; NOBURST 4.7-5.1, 6.1-6.7, 22-25; CAPPED 46-58, 57-74, 47-53.
- The rescue moves the burst's cost from the engine queue (where it never drains) into an explicit, finite wait: it costs about 4-5 x
  less total waiting than doing nothing at 300k and at the native pool, sheds nothing, and finishes the whole burst cohort. Against the
  E2 CAPPED arm (the same cap applied from t = 0, which prevents the trap rather than curing it) the rescue costs about the same at 300k
  (delay 38-78 vs 40-65 session-h) and about 11 x more at the native pool (222-230 vs 18-21), because there it starts from an established
  trap with about 300 outstanding and a gate queue that peaks near 400. Prevention is cheaper; the rescue is what an operator can do
  after the fact.

## Against the predictions

Both prediction sets were pushed before any rescue run started (so all nine runs are blind in time to both, and ended after both pushes):
bundle 3 (tag `r11-rescue-pred`, `72501f0`, GitHub `2026-10-31T02:30:40Z` = 21:30:40 CDT Fri, branch_creation of `r11/rescue`) and the
theory (tag `r13-theory-pred`, `997d2c4`, GitHub `2026-10-31T07:05:30Z` = 02:05:30 CDT Sat). The earliest registered run started at
02:23:44 CDT (17168966) and the last ended at 06:57:06 CDT. The smoke job (23:24-00:08) ended after bundle 3 and before the theory push;
the theory made no smoke prediction, and its authors report no Nova access and no rescue results opened. Selection disclosure (bundle 3
notes): R4's t_on was moved from 2,400 to 2,100 s after the 2,400-s prediction (13/20) was seen and before any rescue run; the theory
read the registered protocol and the simulator's R1 prediction (20/20).

**Simulator, bundle 3** (`$P/results/agentload_analysis_rescue_r{1,4}/*/rescue_t_rel_scoring.csv`; descriptive):

| Quantity | Predicted | GPU |
|---|---|---|
| R1 RESCUED | 20/20 per rate (20 seeds), exact plans 6/6, verdict PASS at both rates | 6/6, PASS at both rates |
| R4 RESCUED (cell `R4s_t2100`) | 16/20 (mixed), exact plans 3/3, verdict PASS | 3/3, PASS |
| Relapses | 0 | 0 |
| R1 t_rel 1.35 x, seeds 0/1/2 | 3,960 / 3,470 / 3,940 (band [3,470, 5,830]) | 4,550 / 3,980 / 4,400 (+590 / +510 / +460) |
| R1 t_rel 1.65 x | 4,900 / 4,440 / 4,280 (band [4,050, 6,050]) | 4,920 / 4,430 / 4,570 (+20 / -10 / +290) |
| R4 t_rel 4.0 x | 4,250 / 5,180 / 4,410 (band [3,720, 7,920]) | 6,000 / 5,980 / 6,140 (+1,750 / +800 / +1,730) |
| Inside the band | expected 0.905 per run | 9/9 (R1 6/6, R4 3/3) |
| Within +-600 s of the seed's exact prediction | | R1 6/6, R4 0/3 |
| t_rec (exact plans) | 3,390 / 2,830 / 3,420; 4,310 / 3,770 / 3,390; R4 3,880 / 4,810 / 4,070 | 3,960 / 3,300 / 3,860; 4,330 / 3,730 / 3,920; 5,670 / 5,680 / 5,790 |
| Pauses (exact) | 122 / 127 / 119; 141 / 142 / 137; R4 238 / 231 / 220 | 124 / 130 / 121; 141 / 143 / 138; 251 / 240 / 220 |
| Max gated + paused (exact) | 131 / 141 / 128; 156 / 159 / 141; R4 264 / 342 / 258 | 134 / 146 / 148; 158 / 159 / 145; 397 / 397 / 387 |
| Post-release max in-system (exact) | 16 / 20 / 19; 21 / 20 / 26; R4 50 / 39 / 49 | 16 / 17 / 20; 23 / 21 / 27; 55 / 43 / 49 |
| Delay session-h (exact) | 32 / 26 / 45; 77 / 55 / 49; R4 74 / 155 / 90 | 53 / 38 / 65; 78 / 50 / 61; 222 / 230 / 225 |
| Completed share (exact) | 0.9909 / 0.9934 / 0.9954; 0.9900 / 0.9912 / 0.9930; R4 0.9882 / 0.9901 / 0.9918 | 0.9909 / 0.9934 / 0.9954; 0.9892 / 0.9912 / 0.9915; 0.9872 / 0.9901 / 0.9918 |

Reading: every pass/fail prediction held, and at 300k the per-seed release times are within 600 s (late by a median 375 s, most at
1.35 x). At the native pool the GPU drains the gate slower than the simulator, as the non-blind CAPPED-drain check in the bundle-3
notes warned: release 800-1,750 s later than each seed's exact prediction (still inside the 20-seed band and before the 7,200 s deadline),
a larger gate queue (387-397 vs 258-342) and about 1.5-3 x the delay session-hours.

**Theory, `r13-theory-pred`** (scoring rule `notes/THEORY_r13_scoring.md` at the tag: NOT RESCUED refutes; release outside +-15% is a
miss):

| Cell | Predicted (F1 phase 1) | GPU t_rel per seed | Within +-15% | GPU mean |
|---|---|---|---|---|
| R1 1.35 x | RESCUED, release 3,830 s (3,920) | 4,550 (+18.8%), 3,980 (+3.9%), 4,400 (+14.9%) | 2/3 | 4,310 (+12.5%) |
| R1 1.65 x | RESCUED, release 4,360 s (4,480) | 4,920 (+12.8%), 4,430 (+1.6%), 4,570 (+4.8%) | 3/3 | 4,640 (+6.4%) |
| R4 4.0 x | RESCUED, release 5,040 s (5,250) | 6,000 (+19.0%), 5,980 (+18.7%), 6,140 (+21.8%) | 0/3 (F1: +14.3 / +13.9 / +17.0%) | 6,040 (+19.8%) |
| Relapse | P = 0.002 / 0.025 (R1), about 0 (R4) | 0/6, 0/3 | consistent (P(0 of 6) about 0.92 under the prediction) | |

Reading: not refuted (RESCUED 9/9). Release times: R1 5/6 within +-15% (all late), R4 a miss in 3/3, late by about 19-22%. Like the
simulator, the theory's drain is too fast at the native pool. Its stated weakest point was R4's phase-1 rate (needs >= 51% of its fluid
value); the GPU phase 1 was slower than fluid but far from collapsed.

## Figure data: trap, rescue, release, persist

Files (all in `$P/results/rescue_paper_data/20261031-071938/`, commit `51c803d`, script `figures/rescue_paper_data.py`):
`trace_aligned.csv` (60-s bins, every arm and seed: fu_hit, fu_n, outstanding, in-flight, gated, paused, cap, latency, with t_engage,
t_release, t - t_engage, t - t_rel), `trace_300s.csv` (300-s bins), `trace_median.csv` (median over seeds per 60-s bin),
`trace_median_rel_release.csv` (rescue arm aligned on t - t_rel), `hit_onset.csv`. Suggested figure: one panel per rate (1.35 x, 1.65 x,
native 4.0 x), FU-hit (top) and outstanding (bottom, log scale) against time, rescue (3 seeds) against BURST and NOBURST, with vertical
lines at the burst (1,200 s), the engage (1,800 / 2,100 s) and each seed's release.

FU-hit in 300-s bins starting at t (rescue arm, seeds 0 / 1 / 2; BURST is 0.00 in every bin from 1,500 s on, NOBURST 0.92-1.00 throughout):

| t (s) | 1.35 x | out (1.35 x) | 1.65 x | out (1.65 x) | 4.0 x native | out (4.0 x) |
|---|---|---|---|---|---|---|
| 900 | 1.00 / 1.00 / 1.00 | 2 / 3 / 3 | 1.00 / 1.00 / 1.00 | 3 / 3 / 3 | 1.00 / 1.00 / 1.00 | 11 / 11 / 9 |
| 1,200 (burst) | 0.17 / 0.11 / 0.11 | 143 / 155 / 153 | 0.18 / 0.12 / 0.15 | 149 / 157 / 152 | 0.63 / 0.62 / 0.78 | 197 / 195 / 172 |
| 1,500 | 0.00 / 0.00 / 0.00 | 151 / 158 / 159 | 0.00 / 0.00 / 0.00 | 165 / 167 / 159 | 0.00 / 0.00 / 0.08 | 256 / 257 / 227 |
| 1,800 (R1 engage) | 0.73 / 0.72 / 0.73 | 133 / 137 / 125 | 0.69 / 0.70 / 0.70 | 163 / 153 / 144 | 0.00 / 0.00 / 0.00 | 307 / 302 / 277 |
| 2,100 (R4 engage) | 0.72 / 0.77 / 0.62 | 121 / 124 / 126 | 0.74 / 0.82 / 0.74 | 154 / 131 / 137 | 0.76 / 0.75 / 0.78 | 299 / 289 / 275 |
| 2,400 | 0.56 / 0.70 / 0.63 | 112 / 114 / 147 | 0.75 / 0.74 / 0.84 | 140 / 124 / 141 | 0.84 / 0.84 / 0.87 | 285 / 280 / 271 |
| 2,700 | 0.77 / 0.98 / 0.60 | 112 / 82 / 158 | 0.86 / 0.99 / 0.79 | 125 / 99 / 146 | 0.63 / 0.78 / 0.56 | 333 / 315 / 333 |
| 3,000 | 1.00 / 1.00 / 0.88 | 78 / 49 / 144 | 0.92 / 1.00 / 1.00 | 118 / 80 / 115 | 0.57 / 0.47 / 0.48 | 392 / 394 / 393 |
| 3,300 | 0.87 / 1.00 / 1.00 | 81 / 19 / 97 | 0.98 / 1.00 / 1.00 | 115 / 53 / 72 | 0.91 / 0.89 / 0.88 | 423 / 431 / 423 |
| 3,600 | 1.00 / 1.00 / 1.00 | 60 / 4 / 63 | 1.00 / 0.96 / 1.00 | 96 / 30 / 33 | 1.00 / 1.00 / 1.00 | 363 / 382 / 368 |
| 3,900 | 1.00 | 26 / 2 / 15 | 0.99 / 1.00 / 0.99 | 76 / 9 / 21 | 1.00 | 310 / 333 / 322 |
| 4,200 | 1.00 | 5 / 1 / 2 | 0.99 / 1.00 / 1.00 | 37 / 3 / 4 | 1.00 | 250 / 269 / 261 |
| 4,500 | 1.00 | 2 / 2 / 3 | 1.00 | 6 / 3 / 2 | 1.00 | 200 / 226 / 207 |
| 4,800-5,700 | 1.00 | 1-3 | 1.00 | 2-3 | 1.00 | 156 / 183 / 163 at 4,800 down to 18 / 19 / 32 at 5,700 |
| 6,000-8,700 | 1.00 | 1-4 | 0.95-1.00 | 1-6 | 1.00 | 6-16 |

Release times (vertical lines): 1.35 x 4,550 / 3,980 / 4,400; 1.65 x 4,920 / 4,430 / 4,570; 4.0 x 6,000 / 5,980 / 6,140 s.
"out" = mean outstanding (engine requests + gated + paused sessions) in the bin.

## Suggested text

**Paragraph.** *Rescuing an established trap.* A trap is not permanent if the operator acts on session count. In two pre-registered
cells we let the burst trap the engine (follow-up hit 0.00 and 139-172 outstanding at 1,800 s on the 300k pool; 298-324 at 2,100 s on
the native pool), then switched on a client-side cap at the knee of the measured curve (20 and 64 sessions): sessions over the cap
pause at their next tool call and resume before new arrivals, and the cap is removed once the gate has been empty for 300 s. All nine
runs were rescued under the registered rule (both cells PASS, decisive): the hit fraction returned above 0.8 within three minutes of the
engage, the backlog drained by 3,980-4,920 s (300k) and 5,980-6,140 s (native), and after the cap was removed the engine stayed in the
good state at the same load for the remaining 2,560-4,720 s with no relapse, while the same-seed uncapped controls stayed at hit 0.00
with 195-1,178 sessions outstanding. After release each rescued run is indistinguishable from its no-burst control (same hit, backlog,
latency and unfinished count). Nothing was shed and every burst session finished; the price is explicit waiting: 121-251 sessions
paused (about 7-8 min on average per paused session) and 196-1,101 held at admission (7-11 min on average), 38-78 delay session-hours
on the 300k pool and about 225 on the native pool, against 377-1,588 session-hours of engine queueing if nothing is done. Both the blind
simulator and the first-principles theory predicted the rescue; both put the native-pool release too early (by 800-1,750 s and about
20%).

**Table row (rescue).**

| Cell | Pool, rate, cap, engage | Runs | RESCUED | Relapse | Release (s) | Post-release FU-hit | BURST control | Shed | Delay session-h |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 300k, 1.35 x, 20, 1,800 s | 3 | 3/3 | 0 | 3,980-4,550 | 0.999-1.000 | stuck 3/3 (hit 0.00) | 0 | 38-65 |
| R1 | 300k, 1.65 x, 20, 1,800 s | 3 | 3/3 | 0 | 4,430-4,920 | 0.994-1.000 | stuck 3/3 | 0 | 50-78 |
| R4 | native, 4.0 x, 64, 2,100 s | 3 | 3/3 | 0 | 5,980-6,140 | 1.000 | stuck 3/3 | 0 | 222-230 |

## Caveats

- Three seeds per cell; the claim is the registered >= 2/3 rule, met 3/3 everywhere.
- "Persists" is tested after the cap stopped binding (see above); there is no perturbation after release.
- The rescue uses the registered knee cap from the measured μ(n) curve and a known t_on; it is not an online detector (AIMD-pause was
  simulated only, bundle 3).
- Costs, persistence tables, the CAPPED comparison and the figure data are post hoc and descriptive (`figures/rescue_paper_data.py`,
  using the verdict's own `user_costs`); only the verdict JSONs are registered.
- R4's t_on (2,100 s) was chosen after the 2,400-s simulator prediction was seen, before any rescue run (disclosed in the registration).
