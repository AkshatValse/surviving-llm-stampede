# Paper input: the registered vLLM paired test (§5.7, and the `\pending` item at the end of §1)

Written 2026-10-31 for the lead. Every number below comes from committed files on branch `r9/vllm-register`; the pull is `results/nova/e2_vllm_1716612x_pulled_20261031-020956/` (abbreviated **VP**), committed in `cacf833`. Full narrative: `notes/LOG.md`, entry 2026-10-31.

## Sources

| key | path (under VP unless stated) | what |
|---|---|---|
| VREG | `configs/agentload_prereg_2026-10-30_vllm.yaml` (repo root), commit `5a6fbcd` | the registration; PREREG_SHA256 `8f2d5b44d6365795fedde8bf673d51e54bf8a685a14d563c86de44492bb95f84` |
| VV | `results/agentload_analysis_burst2/20261031-020837/` (`kill_verdict_v2.json`, `trap_v2_runs.csv`, `trap_v2_cells.csv`, `backlog_trace.csv`, `guards.json`) | the registered analysis, run on the Nova login node in `repo_next/` at `5a6fbcd`, 2026-10-31 02:08 CDT |
| VR | `results/agentload_e2_burst/<ts>/` (18 run dirs: `requests.csv`, `sessions.csv`, `metrics.csv`, `meta.json`, ...) | raw runs |
| VJ | `results/nova_job_logs/171661xx-*/`, `logs/pm-e2v-171661xx.out` | job logs (hardware, canaries, server log) |
| VS | `sacct_17166121-17166138.txt` | JobID, Start, End, NodeList, State |
| VM | `r11_mechanism/` (`loopvars.csv`, `detector.csv`, `occupancy.csv`, `frozen/`, `COMMANDS.txt`) | outputs of the frozen r11 scripts, run unchanged (hashes `frozen/SHA256SUMS`, identical to `f1338e3`) |
| VD | `derived/` (`r11_mechanism_scored.csv`, `r11_mechanism_decision.json`, `e2_vllm_client_side.csv`, `e2_vllm_client_side_summary.csv`, `e2_vllm_capped_drain.csv`, `r11_detector_false_alarm_context_posthoc.csv`) | written by `analysis/r9_vllm_e2_derived.py` (repo root); the client-side part copies `client_side()` of `figures/paper/derived_numbers.py` (r10/arxiv) |
| B3V | `notes/PREDICTIONS_vllm.md` (tag `r9-vllm-predictions-frozen`, pushed 12:32 CDT 2026-10-30) | blind simulator predictions |
| R11 | `configs/r11_mechanism_predict.yaml`, `notes/PREDICTIONS_r11_mechanism.md` on `origin/r11/strengthen` (`f1338e3`, `4d2bba2`; pushed 18:20:13 CDT 2026-10-30) | frozen mechanism predictions |

Jobs: 17166121–17166138 (seed-major: seed 0 = 17166121–26, 1.35 × BURST / NOBURST / CAPPED then 1.65 ×; seed 1 = 17166127–32; seed 2 = 17166133–38), all COMPLETED 0:0 on nova22-gpu-[1-3] (VS).

## Verdict

**PASS at both registered points (1.35 and 1.65 λ_ref)** by the registered analysis (VV `kill_test_pass_rule_only: true`; `trap_v2_cells.csv`: both cells `meets`, `in_registered_window`, `meets_valid_pairing`; 2 of 3 seeds pass at each, threshold 2/3). As the pending note asks, state it as the registered analysis's pass; do not use the tool's `pre_registered` / `kill_test_pass_decisive` labels (both print `true`; they are assigned by commit order). Timing: `5a6fbcd` committed 16:23:59 CDT; jobs submitted 16:24:36; first job starts 16:25:42 and 16:26:17; registration first on GitHub 16:26:35 (creation of branch `r9/vllm-register`, GitHub activity log); first job end 18:55:07 (VS). This matches NUMBERS.md row "16:23:59; 16:24:36; 37 s; 16:26:35; ...".

## Numbers (with sources)

| number(s) | what | source |
|---|---|---|
| T D T; G G G; R R R (1.35) / T I T; G G G; R R R (1.65) | states for seeds 0, 1, 2 (T trapped, D draining, I indeterminate, G good, R recovered) | VV `trap_v2_runs.csv` `state` (NOBURST `recovered` = good) |
| 0.000 (all six BURST) | BURST hit fraction over the evaluation window (t_b + 4500 s to 8700 s) | VV `hit_eval` |
| 1.012, 1.007, 0.995; 1.018, 1.014, 0.948 (0.995–1.012; 0.948–1.018) | BURST uncached prefill rate in multiples of vLLM's all-miss rate (10,348.6 tok/s), seeds 0, 1, 2 | VV `1 + rate_rel_dev_tokens` |
| 221.6, 200.5, 220.5; 314.2, 281.3, 330.1 (201–222; 281–330) | BURST mean backlog (sessions in the system) over the evaluation window | VV `backlog_eval_mean` |
| 250.4, 195.8, 244.4; 360.1, 298.9, 382.8 | BURST backlog over the last 300 s | VV `backlog_end` |
| 0.0142, −0.00005, 0.0170 vs 0.0115; 0.0324, 0.0183, 0.0341 vs 0.0213 | BURST backlog slope (sessions/s) vs the registered threshold 0.5 (λ − λ_miss) | VV `backlog_slope`, `slope_threshold` |
| 0.930–0.931 (1.35); 0.932–0.933 (1.65) | NOBURST and CAPPED hit fraction (identical to 3 dp within a seed) | VV `hit_eval` |
| 0.07–0.09; 0.10–0.11 (0.075–0.088; 0.095–0.110) | NOBURST and CAPPED uncached prefill rate in multiples of all-miss | VV `1 + rate_rel_dev_tokens` |
| 7.0–8.4; 9.3–10.9 | NOBURST and CAPPED mean backlog | VV `backlog_eval_mean` |
| < 0.001 | NOBURST and CAPPED |slope| (max 0.00095) | VV `backlog_slope` |
| 0.0793, 0.0843, 0.0777; 0.0857, 0.0930, 0.0873 sps (1.18–1.28; 1.30–1.42 λ_ref) | BURST session completion rate in the evaluation window | VV `rate_sessions`; VD `completed_rate_eval_mult` |
| 285, 245, 278; 347, 307, 342 arrivals; 1.447, 1.244, 1.411; 1.762, 1.558, 1.736 λ_ref | base arrivals realized in [5700, 8700), seeds 0, 1, 2, shared by the three arms of a seed (and identical to the exploratory vLLM BURST runs, NUMBERS row 532) | VD `base_arrivals_eval`, `base_rate_eval_mult` (λ_ref = 0.065663) |
| 322, 334, 404; 499, 402, 462 | CAPPED: sessions that waited at the gate (gate_wait_s > 0) | VD `n_gated` |
| 0.429, 0.431, 0.527; 0.627, 0.532, 0.597 (43–53 %; 53–63 %) | share of base-stream (ordinary) arrivals among the gated sessions | VD `base_share_of_gated` |
| 0.166, 0.183, 0.258; 0.311, 0.223, 0.275 | gated base sessions as a share of all base arrivals (not reported for 300k; optional) | VD `gated_share_of_base_arrivals` |
| 456.0, 435.2, 501.2; 412.9, 417.4, 525.5 s (435–501; 413–526) | mean gate wait | VD `gate_wait_mean_s` |
| 859.3, 895.2, 1052.7; 892.1, 902.4, 1052.1 s (859–1053; 892–1052) | longest gate wait; none censored | VD `gate_wait_max_s`, `n_gate_censored` |
| 0, 0, 0; 2, 1, 3 (≤ 9.2 s); 0, 1, 0; 3, 9, 2 (≤ 9.8 s) | gated sessions that arrived before the burst; after the gate first emptied (and their longest wait) | VD `n_gated_before_burst`, `n_gated_after_gate_emptied`, `..._max_...` |
| 1550, 1521, 2027; 2735, 1848, 2219 s (1521–2027; 1848–2735) | time after the burst at which the CAPPED gate queue first empties | VD `e2_vllm_capped_drain.csv` `gate_empty_after_burst_s` |
| 1529, 1800 s; 0.99–1.33 and 1.03–1.52 | the registration's drain estimate b / (μ(20) − λ) and the ratio to it | VREG `predicted_drain_s_by_mult`; VD `ratio_to_predicted` |
| 1414, 1453, 1460; 1674, 1692, 1692 s; 1.05–1.39 and 1.09–1.63 | fluid estimate (n_1 + b − 20) / (μ(20) − λ), n_1 = 5, 10, 11; 6, 8, 8 sessions at the burst; ratio | VD `fluid_drain_s`, `n_at_burst`, `ratio_to_fluid` |
| 186.4, 179.5, 188.1; 242.2, 226.9, 261.4 s (180–188; 227–261) | BURST mean turn latency (t_complete − t_send) of ok requests completed in [5700, 8700) | VD `latency_mean_eval_s` |
| 1.38–1.42; 1.46–1.53 s | NOBURST mean turn latency in [5700, 8700), 1.35; 1.65 | VD |
| 1.37–1.44; 1.46–1.58 s | CAPPED mean turn latency in [5700, 8700) | VD |
| 1.42–1.67 s | mean turn latency over [300, 1200) in every arm | VD `latency_mean_preburst_s` |
| 24.2, 20.2, 23.6 %; 30.0, 25.8, 31.2 % (20–24 %; 26–31 %) | share of BURST sessions unfinished at 8700 s | VD `unfinished_share_at_end` |
| 0.7–1.1 %; 0.6–0.9 % | NOBURST; CAPPED sessions unfinished at 8700 s | VD |
| 8f2d5b44…5f84 in 18/18 | each run's `meta.json` `prereg_sha256` | VR |

### Frozen mechanism predictions (R11; all 18 runs blind: earliest End 18:55:07 > push 18:20:13)

| number(s) | what | source |
|---|---|---|
| 0.000; 6.44–8.78 (1.35: 6.44–6.79; 1.65: 8.16–8.78); R 28.1–30.2 s; gap 183–261 s | BURST follow-up hit, median gap / R, R = M / churn, median gap (band: hit < 0.05, gap/R > 2) | VM `loopvars.csv` |
| 1.000 (3 dp); 0.014–0.022; R 229–337 s; gap 4.9–5.1 s | NOBURST/CAPPED (band: hit > 0.95, gap/R < 0.05) | VM `loopvars.csv` |
| 0.920–0.937 | BURST mean `vllm:kv_cache_usage_perc` over [5700, 8700) (band ≥ 0.90) | VM `occupancy.csv` |
| 0.871–0.955 (1.35: 0.937–0.955; 1.65: 0.871–0.947) | BURST uncached-token rate of requests sent in [5700, 8700) / 10,348.6 (band [0.85, 1.15]) | VM `occupancy.csv` |
| 0.061–0.098 | NOBURST/CAPPED mean KV usage (descriptive) | VM |
| 100–120 s | detector first alarm after the burst, BURST (band ≤ 300 s) | VM `detector.csv` |
| 2080 s (2 ticks), 2020 s (4 ticks); 880, 820 s after the burst; hits back from 2190, 2180 s | the two good-arm false alarms: CAPPED seed 2 at 1.35 and at 1.65 (band: none in [600, 8700)) | VM `detector.csv`; VD `r11_mechanism_scored.csv` |
| 170–210 s; none | engine-TTFT rule first alarm after the burst, BURST; good arms | VM `occupancy.csv` |
| 6/6, 6/6, 6/6, 6/6; 12/12, 10/12, 12/12 | BURST meeting (a), (b), (c), (d); good arms meeting (a), (c), (d) | VD `r11_mechanism_decision.json` |
| not met | frozen decision rule (every blind BURST meets (b) and (c): yes; every good arm except at most one meets (a) and (c): two fail (c)) | VD `r11_mechanism_decision.json` |
| 20 admitted, 123–143 waiting; H 0.06–0.17 for 20–40 s | post hoc: state of the CAPPED runs at the two false alarms | VD `r11_detector_false_alarm_context_posthoc.csv` |

## Against B3v

PASS predicted at both points in all four configurations: held. BURST trapped 7–9/10 predicted, 2/3 real at each point (no contradiction at three seeds); the rest predicted INDETERMINATE (stuck at zero hits): real one INDETERMINATE (1.65, seed 1) and one DRAINING (1.35, seed 1) whose slope is −0.00005 sessions/s, a flat backlog at zero hits, a label B3v never produced; no BURST run recovered. NOBURST good and CAPPED recovered 10/10 predicted, 6/6 and 6/6 real. Trapped token rate 0.99–1.07 predicted; real 0.995–1.018 in three trapped runs and 0.948 in the fourth (1.65, seed 2), below the predicted range and inside the registered ±15 %. Blindness: B3v blind in time; its BURST predictions at these points blind on the predicting worker's side only (the lead knew the exploratory BURST outcome).

## Caveats

- The BURST arm reuses the exploratory runs' seeds and arrivals (the paper already says so). The state pattern repeats: seed 1 is the non-trapped run at both rates in both sets.
- 1.35 × seed 1's DRAINING label means slope < 0 by 5 × 10⁻⁵ sessions/s; hit 0.000, token rate 1.007, backlog 200.5 (last 300 s: 195.8), completions 1.28 λ_ref against base arrivals 1.24 λ_ref. It is stuck, not draining in any practical sense; the paper should say so, not hide the label.
- Two frozen-detector false alarms during the CAPPED drain at cap 20 (one seed per rate), so the frozen r11 decision rule fails on detector specificity; the refill-then-evict checks (a, b) and the TTFT rule (d) hold in every run.
- Memory request: the then-pending jobs 17166124–38 had MinMemoryNode lowered from 128G to 48G at 18:21 CDT 10-30 (sacct ReqMem). Scheduling only: no code, argument or registration change; the first three jobs had started, none had ended.
- One model, one GPU type, one pool size (300k), three seeds.

## Suggested text (§5.7, replacing the `\pending{}`)

The paired test passed at both registered points by the registered analysis (Table X). At 1.35 $\lref$ the burst trapped vLLM in two of three seeds; in the third (seed 1, the seed that delivered the fewest arrivals, 1.24 $\lref$ in the evaluation window) the engine was stuck at zero hits with a flat backlog of 200 sessions and an uncached prefill rate of 1.007 times the all-miss rate, which the rule labels draining because the fitted slope was $-5\times10^{-5}$\sps. At 1.65 $\lref$ it trapped two of three, the third (again seed 1) indeterminate by the slope test (0.018 against 0.021). Every BURST run had zero hits over the evaluation window and prefilled 0.948--1.018 times vLLM's all-miss token rate; its backlog over the last 300\,s was 196--250 sessions at 1.35 and 299--383 at 1.65 $\lref$, and its turns took 180--261\,s on average against 1.4--1.6\,s in the other two arms, with 20--31\% of its sessions unfinished at the end. NOBURST stayed good and CAPPED recovered in all six runs each (hit 0.930--0.933; in the evaluation window the two arms are indistinguishable). The gate held 322--499 sessions per run, 43--63\% of them ordinary arrivals rather than burst sessions, for 413--526\,s on average and at most 1053\,s, and its queue first emptied 1521--2735\,s after the burst, 1.05--1.63 times the fluid estimate. The realized base arrival rates in the window were 1.24--1.45 and 1.56--1.76 $\lref$. B3v predicted a pass at both points; the trapped runs' token rates sat at or just below its range (0.948--1.018 against 0.99--1.07). The frozen mechanism checks, committed and pushed before any of these runs ended, held in every run: the trapped pool was full (KV usage 0.92--0.94) and rewritten at 0.87--0.96 times the all-miss rate, the median gap between a session's turns exceeded the pool's eviction horizon $M/\text{churn}$ by 6--9 times in BURST and was below 3\% of it in the other arms. The online hit detector alarmed 100--120\,s after the burst in every BURST run but also, briefly, during the CAPPED drain in one seed at each rate, so its frozen decision rule, which allowed one false alarm, was not met.

## Suggested table rows (in the format of the E2 table; legend gains "D draining")

```
\multicolumn{7}{@{}l}{\emph{vLLM 0.32.0, 300k-token pool (cap 20, $\lref=0.0657$\sps)}}\\
1.35 & BURST   & T D T & 0.000 & 0.995--1.012 & 201--222 & $-0.0001$--0.0170\\
     & NOBURST & G G G & 0.930--0.931 & 0.07--0.09 & 7.0--8.4 & ${<}0.001$\\
     & CAPPED  & R R R & 0.930--0.931 & 0.07--0.09 & 7.0--8.4 & ${<}0.001$\\
\addlinespace
1.65 & BURST   & T I T & 0.000 & 0.948--1.018 & 281--330 & 0.0183--0.0341\\
     & NOBURST & G G G & 0.932--0.933 & 0.10--0.11 & 9.3--10.8 & ${<}0.001$\\
     & CAPPED  & R R R & 0.932--0.933 & 0.10--0.11 & 9.3--10.9 & ${<}0.001$\\
```
Caption additions: slope thresholds 0.0115 and 0.0213 at 1.35 and 1.65 $\lref$; realized base arrivals 1.45, 1.24, 1.41 and 1.76, 1.56, 1.74 $\lref$.
