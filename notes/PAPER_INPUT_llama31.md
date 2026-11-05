# PAPER_INPUT: Llama-3.1-8B cell (second model family) — FINAL

**Verdict: registered paired kill test, decisive PASS at 1.65 × λ_ref; 1.35 × FAILS the 2/3 rule** (`kill_test_pass_decisive: true`, decisive cells: 1.65 × only). Every BURST run is stuck at zero hits at the all-miss token rate; the registered slope test calls 3 of the 6 trapped (1/3 at 1.35 ×, 2/3 at 1.65 ×). NOBURST good 6/6, CAPPED recovered 6/6. Verdict dir `agentload_analysis_burst2/20261101-154441` in `results/nova/llama31_e2_part5_verdict_pulled_20261101-154525/` (status 2026-11-01 16:00 CST).

Branch `r12/llama31` (from `5a6fbcd`). Live state: `notes/STATE_llama31.md`. Blind simulator predictions: branch `r12/llama31-predict`, tag `r12-llama31-predictions-frozen`. Theory conditional: branch `r12/llama31-theory-cond`.

## Cell
- SGLang 0.5.22, FCFS with waiting-prefix refresh on (label `sglang-fcfs-r1-llama31`), KV pool capped at 300,000 tokens (`--max-total-tokens 300000`; every server log says `max_total_num_tokens=300000`), one NVIDIA A100 80GB PCIe (81,920 MiB), Nova `nova22-gpu-[1-3]`.
- Model: `NousResearch/Meta-Llama-3.1-8B-Instruct` at revision `d10aef7999a2b5ba950ab3974312feeedbfe0b77`, an ungated mirror whose four safetensors shards have the same LFS sha256 as `meta-llama/Llama-3.1-8B-Instruct` at `0e9e39f2` (checked against the HF API and on disk in download job 17166805); config.json, generation_config.json and tokenizer.json are the same blobs. Only the chat template differs, which the harness does not use (token-id prompts). Native context 131,072; the workload's longest prompt plus decode is 40,450 tokens.
- Llama-3.1-8B vs Qwen2.5-7B: KV 131,072 vs 57,344 bytes per token (2.29 ×), 32 vs 28 layers, 32 vs 28 query heads. The pool is in tokens, so its session capacity is the same as the Qwen 300k cell.
- Workload, protocols and analysis code: unchanged from the Qwen 300k and vLLM cells (code at `5a6fbcd`).

## Measurements (all from `results/nova/llama31_*_pulled_*`)
**E0a, all-miss capacity** (prefix cache off, closed POP 32, 3 seeds; jobs 17166823/29/31; combine job 17168803; `results/nova/llama31_wave1_pulled_20261031-033750/results/cal_llama31/calibration.json`, sha256 `7c2cb2de…`, also `prereg/inputs/2026-10-30-llama31/calibration.json`):
- λ_miss (turns-based, the λ_ref) = **0.05964 ± 0.00204 sessions/s**; all-miss uncached prefill rate **9,353 tok/s**. Qwen2.5-7B on the same GPU and engine: 0.07153 and 11,243 (Llama = 0.834 × and 0.832 ×).
- POP-64 check (job 17166833): 9,518 tok/s, 1.018 × the POP-32 rate (the rule allows up to 1.05).

**Stage C, closed thrashing curve** (jobs 17166814–16, one run per n, 900 s warm-up + 1800 s window; combined `agentload_analysis_closed/20261031-074803`, identical to `…-033707`; in `results/nova/llama31_e0b_registration_pulled_20261031-075313/results/agentload_analysis_closed/`):

| n | 16 | 20 | 24 | 28 | 32 | 40 | 48 | 96 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| μ sessions/s | 0.166 | **0.202** | 0.195 | 0.123 | 0.053 | 0.037 | 0.041 | 0.051 | 0.099 |
| μ turns-based | 0.164 | 0.195 | 0.191 | 0.127 | 0.063 | 0.053 | 0.055 | 0.065 | 0.100 |
| hit (cached token fraction) | 0.936 | 0.930 | 0.868 | 0.656 | 0.203 | 0.009 | 0.003 | 0.000 | 0.000 |

Peak 0.2017 sessions/s at n = 20 (n = 24 within 3.3%); μ_max / λ_ref = 3.38 (turns-based 3.28); 0.5-hit crossing ≈ 29.4 (linear between 28 and 32); μ falls 73% from n = 24 to 32; at n = 32–48 the turns-based μ (0.053–0.063) is 0.89–1.06 × λ_miss. No guard warnings.

**E0b, from-empty edge** (jobs 17169565–70, one 3000 s run per multiple of λ_ref; six-run bracket `agentload_analysis_stable/20261031-074804`): stable at 1.25, 1.5, 1.75, 2.0 ×; **unstable at 2.5 and 3.0 ×**; monotone, no guard warnings. Window (1, 2.0) × λ_ref; μ_max / λ_ref = 3.38 does not bind.

**Registration** `configs/agentload_prereg_2026-10-30_llama31.yaml`, commit `1559f8e`, GitHub push **2026-10-31 07:49:15 CDT** (before the first E2 submission at 07:50:02); FILLED, `validate` exit 0, PREREG_SHA256 `e584ed87…`. λ points **1.35 and 1.65 × λ_ref** (0.0805 and 0.0984 sessions/s) by the ⅓/⅔ rule of `836063a`; cap **n_cap = 20** (`smallest_within_margin`); capped-drain limit 2.80 ×; the Qwen 300k registration's trap rules unchanged. Warnings only: `n_cap_ambiguous`, `mu300_far_from_lambda_miss`. `check-job` passed for all six (λ, arm) pairs.

## Blind predictions against the measurements
**Simulator (round 12, `notes/PREDICTIONS_llama31.md` on `r12/llama31-predict`, tag `r12-llama31-predictions-frozen`, GitHub 2026-10-31 02:14:06 CDT, while Stage C was running and before E0b started).** V1 = the Qwen-calibrated simulator with its token costs scaled by one factor (1.2121 mixed, 1.2040 separate) to Llama's measured 9,353 tok/s (fitted, not predicted); V0 = unscaled (reproduces round 9's V0 exactly).

| landmark | V1 mixed | V1 separate | V0 mixed | real |
|---|---|---|---|---|
| peak n | 20 | 20 | 24 | **20** |
| peak μ turns-based (sessions/s) | 0.210 | 0.208 | 0.222 (own units) | 0.195 |
| peak μ / λ_miss (turns) | 3.52 | 3.48 | 3.07 | 3.28 |
| cap n | 20 | 20 | 20 | **20** |
| 0.5-hit crossing n | 30.6 | 31.6 | 31.5 | 29.4 |
| hit at n = 32 | 0.38 | 0.47 | 0.46 | 0.20 |
| from-empty edge (× λ_miss) | 2.5 (2.5 × 10/10, 3.0 × 5/10) | 2.0 (2.5 × 8/10) | 2.0 (2.5 × 6/10) | **2.0** (2.5 × unstable) |
| registered points | 1.5, 2.0 | 1.35, 1.65 | 1.35, 1.65 | **1.35, 1.65** |

Readings: peak location and cap right in every V1 configuration; the peak is 7% lower than V1 and the cliff is earlier and steeper (as for vLLM); the edge matches V1-separate and V0, while V1-mixed put it one grid step high (its 2.5 × run is a 10/10 prediction against one real unstable run). B3v at the registered points with cap 20 (both V1 modes, both rules): **PASS** (BURST trapped 9/10 and 8/10 in mixed, 9/10 and 9/10 in separate; NOBURST good 10/10; CAPPED recovered 10/10).

**Theory (lead's round 13, tag `r13-theory-pred`, pushed 02:05:30 CDT; second set `r13-theory-pred2`, 04:20:20 CDT).** A-priori Llama row: λ_miss 0.0619, μ_max 0.208 (F1) at n ≈ 23, 0.5-hit crossing 30.9, n_b 32.0, window 3.37 (F1), edge 2.46 ×; conditional rule s = T_meas / 9,559 = 9,353 / 9,559 = 0.978 through `results/theory/merged/llama31_8b_300k_speed_table.json`. The lead scores it with `notes/THEORY_r13_scoring.md`; the measured landmarks it needs are above (peak n 20, μ_max 0.2017 sessions / 0.195 turns, 0.5-hit crossing 29.4, edge 2.0 × with 2.5 × unstable, window 3.38 sessions / 3.28 turns).
- Registration-conditional theory prediction for E2 (`analysis.theory.pred2.conditional --cell llama31_8b_300k --registration configs/agentload_prereg_2026-10-30_llama31.yaml`, run on `r13-theory-pred2` at 07:51; commits `a36f441` and `d12eef2` on `r12/llama31-theory-cond`, GitHub 12:52:42Z and 12:52:56Z = 07:52:42 / 07:52:56 CDT, with no E2 job started): at 1.35 / 1.65 × and cap 20, trapped token ratio 1.004 / 1.013, BURST backlog 191 / 266, NOBURST hit 0.932, capped drain 1,574 / 1,869 s (fit variant: 1.006 / 1.015, 197 / 272, 0.932, 1,601 / 1,908 s). Files: `results/theory/pred2/conditional/llama31_8b_300k_conditional{,_fit}.{json,yaml}`.

## E2, the registered paired kill test
Jobs 17170409–17170426, all COMPLETED 0:0 (Sat 12:41 – 23:31 CDT; seed-major: seeds 0, 1, 2 → 1.35, 1.65 × → BURST, NOBURST, CAPPED with N_CAP = 20), one 8700 s arm per job (burst of 200 sessions in 60 s at t = 1200 s), from `$W/repo_llama31` at `1559f8e`, `CALIB_FILE=prereg/inputs/2026-10-30-llama31/calibration.json`, `PREREG_FILE=configs/agentload_prereg_2026-10-30_llama31.yaml`. Every job passed the in-job registration check (PREREG_OK, sha256 `e584ed87…`, committed clean) and the pool check. Verdict on Nova's login node with the frozen code: `analysis.summarize burst2 --prereg configs/agentload_prereg_2026-10-30_llama31.yaml --set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500` over all 18 runs → `agentload_analysis_burst2/20261101-154441` (`kill_verdict_v2.json`, `trap_v2_runs.csv`). `pre_registered: true`; registration first and last commit `1559f8e` (07:49:13 CDT Sat), before every run; no pairing problems, no guard problems; decisive cells: **1.65 ×**.

| λ (× λ_ref) | arm | seed 0 | seed 1 | seed 2 | count | cell |
|---|---|---|---|---|---|---|
| 1.35 (0.0805 /s) | BURST | indeterminate | draining | trapped | trapped 1/3 | **FAIL** |
| 1.35 | NOBURST | good | good | good | 3/3 | |
| 1.35 | CAPPED | recovered | recovered | recovered | 3/3 | |
| 1.65 (0.0984 /s) | BURST | trapped | indeterminate | trapped | trapped 2/3 | **PASS** |
| 1.65 | NOBURST | good | good | good | 3/3 | |
| 1.65 | CAPPED | recovered | recovered | recovered | 3/3 | |

Per BURST run (evaluation window t_b + 4500 s to the end): uncached-token rate / all-miss rate, backlog slope vs threshold 0.5 (λ − λ_miss), mean backlog:
- 1.35 ×: seed 0 1.050, 0.0052 vs 0.0104, 210 (indeterminate: stuck at zero hits, slope below threshold); seed 1 1.034, −0.000003, 196 (draining: backlog 196 → 181 at hit 0.000; the registered label for a negative slope); seed 2 1.012, 0.0157, 208 (trapped).
- 1.65 ×: seed 0 1.044, 0.0243 vs 0.0194, 288 (trapped); seed 1 1.030, 0.0114, 267 (indeterminate); seed 2 1.054, 0.0245, 277 (trapped).
- All six at hit 0.000. NOBURST hit 0.925–0.935, backlog 7–10; CAPPED equal to NOBURST in the evaluation window (the gate drained the burst first).

Against the predictions for E2: simulator V1 predicted PASS at both points (BURST trapped 9/10 and 8/10, mixed; 9/10 and 9/10, separate), trapped token ratio 0.985–1.068, BURST backlog 181 / 252 (mixed); real trapped 1/3 and 2/3, ratio 1.012–1.054, backlog 196–210 / 267–288. Every BURST run is stuck as predicted; the slope test, flagged by the simulator as the fragile part at low λ, fails in 3 of 6 real runs. Theory conditional (committed before any E2 job started): token ratio 1.004 / 1.013, backlog 191 / 266, NOBURST hit 0.932 at 1.35 / 1.65 ×.

## Caveats
- The decisive PASS rests on one of the two registered points (1.65 ×); the 1.35 × point FAILS by the registered rule. Report it as such; "stuck 6/6" is a descriptive reading, not the registered criterion.
- Three seeds per point. The slope criterion is the fragile part at the lower point (the Qwen 300k cell had 1 of 3 stuck-but-indeterminate at 1.35 ×; here 2 of 3).
- One run per n (Stage C) and one run per multiple (E0b), as in the other cells; n = 24 is within 3.3% of the peak (cap choice noisy, warning recorded).
- The weights come from a third-party mirror proven byte-identical to Meta's shards; the paper should name the mirror and revision (Llama 3.1 Community License).
- Llama runs within its trained context (131k); the Qwen2.5 cells ran past their trained 32k with no YaRN.
- Procedural: the cell's jobs were reordered by `nice` (62–64, then 54, then 44 for E2) to keep the coordination order under Slurm's age factor; the E0b jobs were submitted without `afterok` because Slurm had purged the finished calibration job; the registration was filled on the PC, so the file has CRLF line endings as written by `prereg fill` (as the vLLM registration). None of these touches a registered quantity.

## Suggested text
*Two sentences.* With a second model family, Llama-3.1-8B-Instruct (Meta's weights; 17% lower all-miss capacity than Qwen2.5-7B), the measured curve, window and registered points are the same (peak n = 20, edge 2.0 × λ_miss, points 1.35 and 1.65 ×, cap 20), and the pre-registered paired test passes decisively at 1.65 × (BURST trapped 2/3, NOBURST good 3/3, CAPPED recovered 3/3). At 1.35 × it fails the registered 2/3 rule: all three BURST runs sit at zero hits at the all-miss token rate, but only one clears the backlog-slope threshold (one is indeterminate, one draining).

*Paragraph (longer form).* To test whether the effect depends on the model, we repeated the whole protocol with a second model family, Llama-3.1-8B-Instruct (Meta's weights via an ungated mirror), on the same GPU, engine and 300k-token pool. Its all-miss capacity is 17% lower than Qwen2.5-7B's (λ_miss = 0.0596 sessions/s, 9,353 prefill tokens/s), but the closed curve has the same shape: a plateau to n = 20 at hit 0.93, a peak of 0.202 sessions/s (3.4 × λ_miss), and a cliff to hit 0.20 by n = 32 and to the all-miss floor by n = 40. The from-empty edge is again 2.0 × λ_miss, so the same rule registers the same points and cap. After the burst, all six BURST runs are stuck at zero hits at 1.01–1.05 × the all-miss token rate while every paired NOBURST run stays good and every CAPPED run recovers; by the registered rule this is a decisive PASS at 1.65 × (2/3 trapped) and a FAIL at 1.35 ×, where the backlog grows too slowly in two of three seeds to clear the slope threshold.

*Table row (cells table).* Llama-3.1-8B, SGLang 0.5.22, A100, 300k | λ_miss 0.0596 | μ_max/λ_miss 3.38 | peak n 20 | edge 2.0 × | points 1.35, 1.65 × | cap 20 | E2: PASS at 1.65 × (2/3 / 3/3 / 3/3), FAIL at 1.35 × (1/3 / 3/3 / 3/3); stuck 6/6 | decisive PASS.
