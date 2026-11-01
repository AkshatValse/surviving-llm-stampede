# Round 9: blind predictions of the calibrated simulator for the real vLLM 0.32.0 experiments (KV pool 300,000 tokens)

Written on branch `r9/vllm-predict` (never pushed, never merged). These are blind predictions of the **calibrated SGLang-like simulator** (`src/prefixmeta/`, cost constants fitted to SGLang 0.5.22 server logs) for the real-engine **vLLM 0.32.0** experiments at the 300,000-token KV cap (18,750 blocks of 16 tokens). **Neither variant models vLLM-specific mechanics** (block-level lazy LRU eviction, no waiting-prefix refresh, vLLM's chunked-prefill budget and scheduler): they are predictions of the SGLang-like model run at vLLM's KV capacity (V0) and additionally at vLLM's measured all-miss token rate (V1), not predictions of a vLLM model.

* **V0**: the SGLang-calibrated engine unchanged (`configs/r7_robustness.yaml` engine block, KV pool 300,000). Every result is in multiples of V0's own turns-based lambda_miss (the "same dimensionless behaviour" hypothesis); the conversion to sessions/s with the real lambda_miss 0.0657 is an explicit multiplication, labelled as such.
* **V1**: the same engine with `per_token_s`, `prefill_attn_s` and `decode_attn_s` (the token-proportional cost terms) multiplied by ONE factor per batching mode, set by a quick B1 check so that the all-miss uncached token rate equals vLLM's measured 10,349 tok/s: **f = 1.0882 (mixed), 1.0806 (separate)**. `iter_fixed_s`, `iter_floor_s` and every other key are unchanged; only existing opt-in config keys (`--set engine.<key>=...`) were used, no `src/` default was changed (the only `src/` change on the branch is the new file `src/prefixmeta/r9_vllm_predict.py`). V1's token rate equals the target **by construction** (fitted, not predicted); V1's lambda_miss is a by-product.
* **Modes**: `mixed` is PRIMARY, `separate_prefill_priority` SECONDARY, for both variants. Each (variant, mode) has its own result tree. All sessions/s values are completed sessions per second; "turns-based" = completed turns/s divided by E[T] = 14.761 (the low-variance estimator used for every multiple, the argmax and the cap).
* **Commits and spec hashes.** Spec declared and committed before any run: `5806460ea76b7ad9a71a0f47509a8934114eb325` (spec sha256 `cd239c19bd5d45bb91846387cf16240d3b42c90c917bbfc9cdf30d1de90b2f65`). V1 factors frozen in the second commit `fd92caf6bd17154f3788b8cd927d64361e89a866` (spec sha256 `98aa0f228e1df1e49d3910035c62ef41b3b457eca875ab148379cbea437d55ca`; the only change to the spec is the two `factor:` values and their comments; the quick B1 check ran on the clean first commit). Driver, B3v stage, report module and tests: `29746a9d4ebd8f0969dfb2512e4ee75c68211308`. **All four simulation trees ran on `29746a9`, clean tree (`dirty = false` in every `meta.json`), with the frozen spec (sha256 `98aa0f22...`, identical to every stage's config copy).** This notes file and the force-added result summaries are in the commit that adds them.
* **Nothing was cut.** Every variant, mode and candidate multiple ran in full: 4 trees x (B1v, B4v, B2v, B3v). B3v ran at the task's seven multiples {1.15, 1.25, 1.35, 1.5, 1.65, 2.0, 2.35} plus one labelled extra, **1.10** (the rule gives 1.10 for a real edge hi = 1.25: 1 + 0.25/3 = 1.083 rounds to 1.10), with the CAPPED arm at the cap the B4v rule picks (20 in all four configurations) and at the sensitivity caps {16, 20, 24, 28, 32} plus one labelled extra, **40**. The compute rule "cut the caps to {20, 28} if over about 3 hours" was not needed: the whole driver took **2 min 41 s** of wall time (12:24:42 to 12:27:23, 6 worker processes; recorded stage wall time 136 s), plus about 8 s per mode for the V1 factor check.
* **Commands and seeds.** Everything ran from the worktree root in Git Bash with the shared venv interpreter, `PYTHONPATH="src;."`: `bash experiments/r9_vllm_predict_run.sh > results/r9_vllm_run_all.log 2>&1` (expands into, per variant and mode, the three round-7 stages `experiments/r7_robustness_run.py {lambda_miss,curves,edge} --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_<variant>_<mode> [--set ...]`, then `python -m prefixmeta.r9_vllm_predict pairs_all ...`, `python -m prefixmeta.r7_report report ...`, and finally `python -m prefixmeta.r9_vllm_predict report`); the exact argv of every stage, with its `--set` overrides, is in the generated provenance section. The tables come from `python -m prefixmeta.r9_vllm_predict report` (report dir `results/r9_vllm_report/20261030-122723/`) and this file from `python -m prefixmeta.r9_vllm_predict assemble`. Seeds: B1v 0 to 2, B4v 0 to 9, B2v 0 to 9, B3v 0 to 9 (all arms of a multiple share the seeds and the arrival streams: common random numbers). Quick V1 factor check (before the main runs, clean commit `5806460`): `calibration/r9_vllm_v1_factor/v1_check.py {mixed,separate}`, logs `factor_check_*.json`. Tests: `tests/test_r9_vllm_predict.py` 17 passed; the unchanged round-7 and round-8 test files that use the same machinery were re-run: `tests/test_r7_robustness.py` 17 passed, `tests/test_r8_native_predict.py` 10 passed.
* **Blindness.** Section "What was and was not used" below lists every file read. Nothing under `results/nova/` and none of the real vLLM files was opened; the two real vLLM numbers come from the task text. The lead knew the outcome of earlier exploratory vLLM BURST runs (see the section below the tables): the BURST-arm predictions at 1.35 x and 1.65 x are blind on my side only.

## 0. Headline predictions

**Summary.** (1) The two variants agree: scaling the token costs by 8 to 9% moves lambda_miss by about 8% and every landmark in multiples (peak n, cap, 0.5-hit crossing, edge) only within seed noise, so in the model the behaviour is dimensionless in lambda_miss; V0 and V1 differ in sessions/s units, and in the B3v verdicts only at 1.10 x and 1.15 x (V0 mixed FAIL at both, V0 separate FAIL at 1.10 x, V1 PASS) and at 2.35 x (V0 FAIL, V1 PASS at exactly 7/10). (2) All four configurations give the same shape: plateau to n = 20 at hit 0.93, peak at n = 24, a cliff between n = 24 and n = 40 with the 0.5-hit crossing at n = 31.4 to 32.6, cap n = 20, from-empty edge hi = 2.0 x lambda_miss (0.131 sessions/s in real units), and the paired kill test PASSES at 1.25 x to 2.0 x at the cap 20 under both PASS rules, including the two points (1.35 x, 1.65 x) a real edge of 2.0 x would register. (3) Weak spots: low multiples (1.10 x, 1.15 x) in V0 and the top point 2.35 x (NOBURST collapses from empty in 3 to 4 of 10 seeds).

All tables in this section are generated from `results/r9_vllm_report/20261030-122723/summary.json` and the per-tree stage dirs (nothing typed by hand but the prose); the full per-seed tables follow in the generated section.

### B1v. All-miss capacity (cache off, closed POP 32, 3 seeds, turns-based)

| variant / mode | lambda_miss turns-based (sessions/s) | sd over 3 seeds | lambda_miss sessions-based | all-miss token rate (tok/s) | x vLLM 10,349 | lambda_miss / real 0.0657 | POP 64 lambda_miss | V1 factor f |
|---|---|---|---|---|---|---|---|---|
| V0 mixed | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1.0841 | 1.0987 | 0.071986 | 1 (unchanged) |
| V0 separate | 0.071359 | 0.0012945 | 0.068889 | 11147 | 1.0771 | 1.0861 | 0.071221 | 1 (unchanged) |
| V1 mixed | 0.066228 | 0.00073592 | 0.065926 | 10358 | 1.0009 | 1.008 | 0.066805 | 1.0882 |
| V1 separate | 0.066328 | 0.00040244 | 0.06537 | 10342 | 0.99931 | 1.0096 | 0.065601 | 1.0806 |

### B4v. Closed curve, mu turns-based sessions/s / hit fraction (10 seeds, mean)

| variant / mode | n=16 | n=20 | n=24 | n=28 | n=32 | n=40 | n=48 | n=96 | n=300 |
|---|---|---|---|---|---|---|---|---|---|
| V0 mixed | 0.177 / 0.93 | 0.216 / 0.93 | 0.222 / 0.89 | 0.167 / 0.74 | 0.112 / 0.46 | 0.073 / 0.03 | 0.071 / 0.00 | 0.079 / 0.00 | 0.112 / 0.00 |
| V0 separate | 0.176 / 0.93 | 0.214 / 0.93 | 0.221 / 0.89 | 0.180 / 0.77 | 0.122 / 0.53 | 0.077 / 0.11 | 0.071 / 0.01 | 0.078 / 0.00 | 0.112 / 0.00 |
| V1 mixed | 0.175 / 0.93 | 0.213 / 0.93 | 0.215 / 0.89 | 0.162 / 0.74 | 0.104 / 0.46 | 0.066 / 0.03 | 0.066 / 0.00 | 0.074 / 0.00 | 0.106 / 0.00 |
| V1 separate | 0.174 / 0.93 | 0.211 / 0.93 | 0.215 / 0.89 | 0.165 / 0.75 | 0.115 / 0.52 | 0.071 / 0.10 | 0.066 / 0.01 | 0.074 / 0.00 | 0.105 / 0.00 |

### B4v landmarks

| variant / mode | peak n | peak mu | peak mu / lambda_miss | hit at peak | n at hit 0.5 | n at hit 0.9 | n at hit 0.2 | cap n (5% rule) | cap margin above 0.95 peak | n=16 margin | mu(300) | mu(300)/peak |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 mixed | 24 | 0.2217 | 3.071 | 0.8898 | 31.46 | 22.99 | 36.9 | 20 | 0.02393 | -0.1607 | 0.1119 | 0.5047 |
| V0 separate | 24 | 0.2208 | 3.095 | 0.8917 | 32.6 | 23.14 | 38.22 | 20 | 0.01842 | -0.1633 | 0.1115 | 0.5051 |
| V1 mixed | 24 | 0.2154 | 3.253 | 0.8883 | 31.42 | 22.87 | 36.79 | 20 | 0.03934 | -0.1433 | 0.1063 | 0.4934 |
| V1 separate | 24 | 0.2151 | 3.243 | 0.8897 | 32.41 | 22.98 | 38.17 | 20 | 0.03423 | -0.1475 | 0.1048 | 0.4869 |

### B2v. From-empty stable runs out of 10 by multiple of the variant's own lambda_miss, and the contiguous edge

| variant / mode | 1.25 x | 1.5 x | 1.75 x | 2 x | 2.5 x | 3 x | edge hi (x lambda_miss) | hi in sessions/s (own units) | hi x real 0.0657 | hi censored | 0.95 / 0.5 crossing (x) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 mixed | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 1/10 | 2 | 0.1444 | 0.1314 | False | 2.06 / 2.60 |
| V0 separate | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 1/10 | 2 | 0.1427 | 0.1314 | False | 2.12 / 2.71 |
| V1 mixed | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 3/10 | 2 | 0.1325 | 0.1314 | False | 2.08 / 2.75 |
| V1 separate | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 3/10 | 2 | 0.1327 | 0.1314 | False | 2.08 / 2.75 |

Plug-in illustration (NOT a prediction of the real design; the number of real seeds is not known to this round): if a real from-empty test used only 3 or 5 seeds per multiple and the per-run stable probability were the 10-seed fraction above, the chance that 2.5 x or 3 x comes out all-stable (which would move the contiguous edge up) would be p^3 or p^5:

| variant / mode | p(2.5 x) = k/10 | P(all 3 stable at 2.5 x) | P(all 5 stable at 2.5 x) | p(3 x) = k/10 | P(all 3 stable at 3 x) | P(all 5 stable at 3 x) |
|---|---|---|---|---|---|---|
| V0 mixed | 0.600 | 0.216 | 0.078 | 0.100 | 0.001 | 0.000 |
| V0 separate | 0.800 | 0.512 | 0.328 | 0.100 | 0.001 | 0.000 |
| V1 mixed | 0.700 | 0.343 | 0.168 | 0.300 | 0.027 | 0.002 |
| V1 separate | 0.700 | 0.343 | 0.168 | 0.300 | 0.027 | 0.002 |

### B3v at the cap 20 that the B4v rule picks in all four configurations

Cell = BURST trapped / NOBURST good / CAPPED(20) recovered (each out of 10), then per-arm verdict / same-seed verdict (P = PASS, F = FAIL; need 7 of 10):

| x lambda_miss | V0 mixed | V0 separate | V1 mixed | V1 separate |
|---|---|---|---|---|
| 1.1 (extra) | 4 / 10 / 10  F / F | 6 / 10 / 10  F / F | 7 / 10 / 10  P / P | 9 / 10 / 10  P / P |
| 1.15 | 6 / 10 / 10  F / F | 8 / 10 / 10  P / P | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P |
| 1.25 | 9 / 10 / 10  P / P | 10 / 10 / 10  P / P | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P |
| 1.35 | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P |
| 1.5 | 7 / 10 / 10  P / P | 8 / 10 / 10  P / P | 9 / 10 / 10  P / P | 10 / 10 / 10  P / P |
| 1.65 | 9 / 10 / 10  P / P | 9 / 10 / 10  P / P | 7 / 10 / 10  P / P | 8 / 10 / 10  P / P |
| 2 | 10 / 9 / 10  P / P | 9 / 9 / 10  P / P | 9 / 9 / 10  P / P | 9 / 9 / 10  P / P |
| 2.35 | 10 / 6 / 10  F / F | 10 / 6 / 10  F / F | 10 / 7 / 10  P / P | 10 / 7 / 10  P / P |

### B3v cap sensitivity: the caps (of 16, 20, 24, 28, 32, 40) at which the PASS holds

| x lambda_miss | V0 mixed | V0 separate | V1 mixed | V1 separate |
|---|---|---|---|---|
| 1.1 (extra) | same-seed: none; per-arm: none | same-seed: none; per-arm: none | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28,32; per-arm: 16,20,24,28,32 |
| 1.15 | same-seed: none; per-arm: none | same-seed: 16,20,24,28; per-arm: 16,20,24,28,32 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28,32; per-arm: 16,20,24,28,32 |
| 1.25 | same-seed: 16,20,24,28; per-arm: 16,20,24,28,32 | same-seed: 16,20,24,28,32; per-arm: 16,20,24,28,32 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 |
| 1.35 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28,32 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 |
| 1.5 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 |
| 1.65 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 | same-seed: 16,20,24; per-arm: 16,20,24,28 | same-seed: 16,20,24,28; per-arm: 16,20,24,28 |
| 2 | same-seed: 20,24; per-arm: 20,24 | same-seed: 20,24,28; per-arm: 20,24,28 | same-seed: 16,20,24; per-arm: 16,20,24 | same-seed: 16,20,24; per-arm: 16,20,24 |
| 2.35 | same-seed: none; per-arm: none | same-seed: none; per-arm: none | same-seed: 20,24; per-arm: 20,24 | same-seed: 20,24; per-arm: 20,24 |

### CAPPED recovered by cap (k/10)

| config | x lambda_miss | cap 16 | cap 20 | cap 24 | cap 28 | cap 32 | cap 40 |
|---|---|---|---|---|---|---|---|
| V0 mixed | 1.1 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V0 mixed | 1.15 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V0 mixed | 1.25 | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 0/10 |
| V0 mixed | 1.35 | 10/10 | 10/10 | 10/10 | 10/10 | 4/10 | 0/10 |
| V0 mixed | 1.5 | 10/10 | 10/10 | 10/10 | 10/10 | 0/10 | 0/10 |
| V0 mixed | 1.65 | 10/10 | 10/10 | 10/10 | 9/10 | 0/10 | 0/10 |
| V0 mixed | 2 | 6/10 | 10/10 | 10/10 | 5/10 | 0/10 | 0/10 |
| V0 mixed | 2.35 | 0/10 | 10/10 | 10/10 | 2/10 | 0/10 | 0/10 |
| V0 separate | 1.1 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 0/10 |
| V0 separate | 1.15 | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 0/10 |
| V0 separate | 1.25 | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 0/10 |
| V0 separate | 1.35 | 10/10 | 10/10 | 10/10 | 10/10 | 7/10 | 0/10 |
| V0 separate | 1.5 | 10/10 | 10/10 | 10/10 | 10/10 | 2/10 | 0/10 |
| V0 separate | 1.65 | 10/10 | 10/10 | 10/10 | 10/10 | 0/10 | 0/10 |
| V0 separate | 2 | 6/10 | 10/10 | 10/10 | 7/10 | 0/10 | 0/10 |
| V0 separate | 2.35 | 0/10 | 10/10 | 10/10 | 3/10 | 0/10 | 0/10 |
| V1 mixed | 1.1 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V1 mixed | 1.15 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V1 mixed | 1.25 | 10/10 | 10/10 | 10/10 | 10/10 | 5/10 | 0/10 |
| V1 mixed | 1.35 | 10/10 | 10/10 | 10/10 | 10/10 | 4/10 | 0/10 |
| V1 mixed | 1.5 | 10/10 | 10/10 | 10/10 | 9/10 | 0/10 | 0/10 |
| V1 mixed | 1.65 | 10/10 | 10/10 | 10/10 | 9/10 | 0/10 | 0/10 |
| V1 mixed | 2 | 10/10 | 10/10 | 10/10 | 4/10 | 0/10 | 0/10 |
| V1 mixed | 2.35 | 1/10 | 10/10 | 10/10 | 3/10 | 0/10 | 0/10 |
| V1 separate | 1.1 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 0/10 |
| V1 separate | 1.15 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 0/10 |
| V1 separate | 1.25 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V1 separate | 1.35 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 |
| V1 separate | 1.5 | 10/10 | 10/10 | 10/10 | 10/10 | 2/10 | 0/10 |
| V1 separate | 1.65 | 10/10 | 10/10 | 10/10 | 9/10 | 0/10 | 0/10 |
| V1 separate | 2 | 10/10 | 10/10 | 10/10 | 6/10 | 0/10 | 0/10 |
| V1 separate | 2.35 | 0/10 | 10/10 | 10/10 | 3/10 | 0/10 | 0/10 |

### The registration map at the picked cap 20 (same-seed rule)

For every possible real edge hi: the two test points, and per configuration BURST trapped / NOBURST good / CAPPED(20) recovered with the same-seed verdict at each point (cap 20 is what all four B4v rules pick; read the cap sensitivity table for other real caps):

| real edge hi | points | V0 mixed | V0 separate | V1 mixed | V1 separate |
|---|---|---|---|---|---|
| 1.25 | 1.1 and 1.15 | 4/10/10 FAIL ; 6/10/10 FAIL  => not both | 6/10/10 FAIL ; 8/10/10 PASS  => not both | 7/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 9/10/10 PASS  => both PASS |
| 1.5 | 1.15 and 1.35 | 6/10/10 FAIL ; 9/10/10 PASS  => not both | 8/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 9/10/10 PASS  => both PASS |
| 1.75 | 1.25 and 1.5 | 9/10/10 PASS ; 7/10/10 PASS  => both PASS | 10/10/10 PASS ; 8/10/10 PASS  => both PASS | 9/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 10/10/10 PASS  => both PASS |
| 2 | 1.35 and 1.65 | 9/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 9/10/10 PASS  => both PASS | 9/10/10 PASS ; 7/10/10 PASS  => both PASS | 9/10/10 PASS ; 8/10/10 PASS  => both PASS |
| 2.5 | 1.5 and 2 | 7/10/10 PASS ; 10/9/10 PASS  => both PASS | 8/10/10 PASS ; 9/9/10 PASS  => both PASS | 9/10/10 PASS ; 9/9/10 PASS  => both PASS | 10/10/10 PASS ; 9/9/10 PASS  => both PASS |
| 3 | 1.65 and 2.35 | 9/10/10 PASS ; 10/6/10 FAIL  => not both | 9/10/10 PASS ; 10/6/10 FAIL  => not both | 7/10/10 PASS ; 10/7/10 PASS  => both PASS | 8/10/10 PASS ; 10/7/10 PASS  => both PASS |
### Readings of the tables above

* **B1v.** V0: lambda_miss 0.0722 (mixed) and 0.0714 (separate) sessions/s, all-miss token rate 11,220 and 11,147 tok/s, i.e. 1.084 x and 1.077 x vLLM's measured 10,349 tok/s and 1.099 x and 1.086 x its measured lambda_miss 0.0657. V1 (fitted): token rate 10,358 (+0.09%) and 10,342 (-0.07%) tok/s; its lambda_miss 0.0662 and 0.0663 sessions/s is a by-product, 1.008 x and 1.010 x the real value (the real value was available to the lead, so this is a consistency check, not a blind output). The V1 main B1v reproduces the factor check **bit for bit** (token rate identical to the accepted check iteration, both modes). A single factor 1.0882 would leave the separate mode at 10,270.8 tok/s (-0.76%), which is why the factor is per mode.
* **B4v.** All four: peak n = 24 (first argmax of the seed-mean turns-based mu), peak mu 0.2217 / 0.2208 / 0.2154 / 0.2151 sessions/s = 3.07 / 3.10 / 3.25 / 3.24 x lambda_miss (V0 in real units: 3.07 x 0.0657 = 0.2018 sessions/s), hit 0.89 at the peak; the hit fraction goes 0.93 (n = 16, 20), 0.89 (24), 0.74 (28), 0.46 (32), 0.03 (40), 0.00 (48 and above) in V0 mixed, so the 0.5 crossing is n = **31.5 / 32.6 / 31.4 / 32.4** (per-seed spread 30.0 to 33.6 in V0 mixed) and 0.9 is crossed at n = 23.0. Past the cliff mu falls to the all-miss floor (0.071 sessions/s at n = 48, about lambda_miss) and rises slowly to 0.105 to 0.112 at n = 300 (0.49 to 0.51 x the peak, hit 0). **The cap is n = 20 in all four** (smallest grid n with seed-mean mu >= 0.95 x the peak): mu(20) lies 2.4 / 1.8 / 3.9 / 3.4% above the 95% line and mu(16) 14 to 16% below it, so the margin is smaller than the seed spread of the argmax cell (n = 24 is bistable: per-seed mu 0.18 to 0.25 in V0 mixed). A real cap of 20 or 24 is the likely outcome; the cap sensitivity below covers 16 to 32 (and 40).
* **B2v.** All four: 10/10 stable at 1.25, 1.5, 1.75 and 2.0 x, hence the contiguous edge **hi = 2.0 x lambda_miss** (not censored). 2.5 x is inside the soft transition: 6/10, 8/10, 7/10, 7/10 stable (stable fraction crosses 0.95 at 2.06 to 2.12 x and 0.5 at 2.60 to 2.75 x), 3.0 x: 1/10, 1/10, 3/10, 3/10. A real test with few seeds can read the edge as 2.5 x (the plug-in illustration above), 3.0 x is unlikely. In real units hi = 2.0 corresponds to 0.131 sessions/s (2.0 x 0.0657) under the dimensionless reading; in the variants' own units 0.144 / 0.143 (V0) and 0.1325 / 0.1327 (V1). The model's mu*/lambda_miss = 3.07 to 3.25 is above every multiple of the edge grid, so the "capped by mu*/lambda_ref" part of the registration rule does not bind in the model (it would bind and give a non-grid hi if the real peak were below 3.0 x the real lambda_ref).
* **B3v (kill test).** Every BURST run in every configuration ends all-miss: hit rate 0.000 and "stuck" (hit < 0.2) in 10/10 seeds at **every** multiple, V0 and V1, both modes; no BURST run recovers. The declared TRAPPED label (token rate within 15% of all-miss AND backlog slope > 0.5 (lambda - lambda_miss)) is met by fewer runs at low multiples because the slope threshold shrinks with lambda - lambda_miss; the remaining runs are INDETERMINATE (stuck, slope too small), not recovered. Trapped runs process 0.99 to 1.07 x the all-miss uncached token rate (V0 mixed: 0.994 at 1.15 x rising to 1.073 at 2.35 x; the other configurations the same range, never above 1.073) with mean backlog in the evaluation window of about 135 to 150 waiting requests at 1.1 x rising to about 480 to 520 at 2.35 x. At the picked cap 20:
  * **At the points a real edge of 2.0 x registers (1.35 x and 1.65 x): PASS in all four configurations under both rules**: BURST trapped 9/10 and 9/10 (V0 mixed), 9 and 9 (V0 separate), 9 and 7 (V1 mixed), 9 and 8 (V1 separate); NOBURST good 10/10 at both; CAPPED(20) recovered 10/10 at both. Same-seed counts equal the BURST counts there (9, 9, 9, 9, 9, 7, 9, 8 of 10).
  * PASS at every multiple from 1.25 x to 2.0 x in all four configurations (and from 1.10 x in V1, from 1.15 x in V0 separate). FAIL in V0 at the low end (BURST trapped 4/10 at 1.10 x and 6/10 at 1.15 x in V0 mixed; 6/10 at 1.10 x in V0 separate) and in V0 at 2.35 x (NOBURST good only 6/10 because the unburst system itself collapses from empty in 4 of 10 seeds). V1 at 2.35 x passes at exactly the threshold (NOBURST good 7/10).
  * The per-arm rule and the registered same-seed rule give the same verdict at every (multiple, cap 20) cell; they differ only away from cap 20: at cap 32 (V0 mixed 1.25 x: per-arm PASS, same-seed FAIL; V0 separate 1.15 x and 1.35 x likewise) and at cap 28 (V1 mixed 1.65 x: BURST trapped 7/10, CAPPED recovered 9/10, same-seed count 6/10).
  * **Cap dependence** (CAPPED recovered k/10 in the table above): caps 16, 20 and 24 recover 10/10 from 1.1 x to 1.65 x everywhere; cap 28 recovers 9 to 10 of 10 up to 1.65 x but only 4 to 7 of 10 at 2.0 x (V0 mixed 5, V0 separate 7, V1 mixed 4, V1 separate 6) and 2 to 3 of 10 at 2.35 x; cap 32 sits on the cliff (0.5-hit crossing n about 31 to 33) and recovers 4 to 9 of 10 at low multiples and 0 to 2 of 10 from 1.5 x; **cap 40 never recovers (0/10 at every multiple)**; cap 16 cannot carry the load at the top (V0 6/10 at 2.0 x, 0/10 at 2.35 x; V1 10/10 at 2.0 x but 0 to 1/10 at 2.35 x) because mu(16) = 0.174 to 0.177 sessions/s is only 4 to 12% above the arrival rate there (utilisation 0.89 to 0.96). So a real cap of 16, 20 or 24 should PASS wherever the BURST and NOBURST arms do; a real cap of 28 passes up to 1.65 x; a real cap at or above 32 is predicted to FAIL (CAPPED trapped or backlogged).
* **Which pairs the real registration would use.** The table "The registration map" above lists, for each possible real edge hi in {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}, the two points and the predicted verdicts at cap 20; the cap-sensitivity table gives the caps that pass at each multiple. In short: hi = 1.75, 2.0 and 2.5 are predicted both-PASS in all four configurations; hi = 1.5 is not both-PASS in V0 mixed (1.15 x fails: 6/10 trapped); hi = 3.0 is not both-PASS in V0 (2.35 x fails on NOBURST), both-PASS in V1 (at the threshold); hi = 1.25 is both-PASS in V1 only.

### How far to trust these (read before comparing with the real runs)

* **The model is not vLLM.** The 300,000-token pool is vLLM's, but the model evicts whole sessions LRU at admission and has SGLang's scheduling; real vLLM evicts 16-token blocks lazily and has different admission. The cliff position (n about 31 to 33 at hit 0.5), the plateau shape and the factor-of-two edge are the pool-geometry predictions the earlier rounds trusted most; levels (sessions/s) depend on the all-miss rate. The 300k validation of the same model against SGLang over-predicted the all-miss floor by up to 42% at FCFS n = 48 (round 6 `VALIDATION.md`, quoted in `notes/PREDICTIONS.md`); V1 removes the token-rate part of that error for vLLM by construction but not any scheduling difference.
* **Fragile cells (stated plainly).** (a) The cap 20 rests on +1.8 to +3.9% above the 95% line, with the peak cell n = 24 bistable across seeds. (b) V0 mixed 1.5 x has BURST trapped exactly 7/10 (the threshold) and V1 mixed 1.65 x also 7/10; V1 2.35 x NOBURST good is exactly 7/10. (c) The low multiples (1.10, 1.15) are decided by the TRAPPED slope threshold, not by recovery: every BURST run is stuck at hit 0 there, so a different trapped rule would flip those verdicts (the "BURST stuck" column of the generated tables is the rate-free reading). (d) The edge is resolved to one grid step and 10 seeds; 2.5 x is a coin flip (6 to 8 of 10 stable). (e) Cap 28 and above are cliff-edge arms: their verdicts are sensitive to the seed.
* **Differences between V0 and V1 are small and mostly noise.** Peak n, cap, edge and the PASS pattern at 1.25 x to 2.0 x are identical; the 0.5-hit crossing differs by 0.04 (mixed) and 0.19 (separate) in n; differences in BURST trapped counts at low multiples (e.g. 4/10 against 7/10 at 1.10 x, mixed) are within what 10 seeds of a slope-threshold label produce (Wilson intervals [0.17, 0.69] and [0.40, 0.89] overlap).

## What did not run

* No 20-seed supplement of the from-empty edge, no burst-size sweep, no 30,000 s horizon, no tool-time workloads other than Exp(5 s), no low-lambda 20-seed BURST fragility run (rounds 6 and 7 had them for SGLang-like settings).
* No vLLM mechanic was modelled: not the engine's existing `ondemand_preempt` (vLLM-like) allocation mode (refused with `separate_prefill_priority`, and not what the task asked), not block-level lazy LRU eviction, not the missing waiting-prefix refresh, not vLLM's chunked-prefill token budget. A variant with `alloc_mode: ondemand_preempt` is the nearest existing opt-in key and would be a natural V2; it was not run.
* The B3v multiples were all run at all caps; nothing was dropped. No multiple off the list (for example the value a mu*/lambda_ref-capped hi would give) was run.

## What was and was not used

**Used (read), inside the worktree `Nova-Research-wt/vllm-predict` (branch `r9/vllm-predict`, cut from `main` at `a4bab1d`):**

* `notes/PREDICTIONS.md`: the heading list (`grep -n "^#"`) and lines 1 to 146 (header, section 0 headline predictions, sections 1 to 3). Its numbers are earlier *simulator* predictions of round 6, not real results.
* `notes/PREDICTIONS_native.md`: lines 1 to 120 (the headline predictions and the sections "What was and was not used" / "What did not run" of round 8; again simulator predictions only).
* The round-7 and round-8 machinery, in full unless noted: `configs/r8_native_predict.yaml`, `experiments/r8_native_predict_run.sh`, `configs/r7_robustness.yaml`, `experiments/r7_robustness_run.py`, `src/prefixmeta/r7_robustness.py`, `src/prefixmeta/r7_report.py`, `src/prefixmeta/r8_native_report.py`, `src/prefixmeta/probe.py`, `tests/test_r8_native_predict.py`.
* Partial reads: `src/prefixmeta/engine.py` (lines 1 to 60 and 130 to 300, and a `grep` of the cost-term names, to find the token-proportional cost terms), `src/prefixmeta/r6_predict.py` lines 1 to 120, `src/prefixmeta/runner.py` lines 68 to 133 (`wilson_ci`, `apply_overrides`, result-dir and git helpers), `src/prefixmeta/mech_runner.py` lines 60 to 125 (`begin`, `finish`), `src/prefixmeta/r6_validate.py` (the `crossing` function via `grep`), `.gitignore` lines 1 to 40, `pytest.ini`.
* Directory listings (names only) of the worktree root, `configs/`, `experiments/`, `src/prefixmeta/`, `notes/`; `git log --oneline` (top entries; the subject of the HEAD commit says "paper draft complete with native and vLLM results; new author decisions", which was visible in the output of `git worktree add` and `git log`; no number came with it).
* Context injected by the harness into the session (not opened by a tool call by me): the user's auto-memory index and the worktree's `CLAUDE.md`. Neither contains a vLLM closed-curve, from-empty or burst number (the index describes the project workflow and unrelated projects; the `CLAUDE.md` is the project overview and environment notes).
* My own outputs: everything under `results/r9_vllm_*`, `calibration/r9_vllm_v1_factor/`, and two scratch files (`v1_check.py` and its JSON logs, copied into `calibration/r9_vllm_v1_factor/`) that I wrote into the session's scratchpad directory; I did not read any other file in the scratchpad (I never listed it).
* **The real numbers used** (all from the task text): the KV cap 18,750 blocks x 16 tokens = 300,000 tokens; vLLM's all-miss capacity lambda_miss (turns-based) 0.0657 sessions/s; vLLM's all-miss uncached prefill rate 10,349 tok/s; the simulator's own all-miss rate "about 11,239 tok/s" (that value belongs to the 955,757-token round-8 setting and is not used by any computation; at the 300,000-token pool the simulator's own B1 rate is the measured one in the tables).

**Not used (not read):** nothing under `results/nova/` (not even the three directories the task allowed: `results/nova/e0a_vllm_17100940_pulled_20261025-180814/`, `results/nova/stageC_1706210x_pulled_20261022-125454/`, `results/nova/s0_smoke_17060165_pulled_20261021-152347/`, nor `prereg/inputs/2026-10-25-vllm/calibration.json`: the two vLLM numbers came from the task text); `notes/LOG.md`; `notes/STATE.md`; anything under `paper/`; `calibration/round6_server_log_fit/` (the cost constants enter only through the engine block copied from `configs/r7_robustness.yaml`); `results/nova/e2_native_vllm_burst_pulled_*` and every native-pool file; the main checkout, any other worktree. No `ssh`, `scp`, `sbatch`, `squeue` or `sacct` was run, the Nova cluster was not contacted, and no real vLLM closed-curve, from-empty or burst number was seen.

## What the lead knew (blindness only on this side)

The lead who commissioned this round knew the outcome of earlier **exploratory vLLM BURST runs** (not shown to me, and not read by me). The BURST-arm predictions at 1.35 x and 1.65 x (the points for a real edge of 2.0 x) are therefore blind on the predictor's side only: whoever compares them with the real BURST outcome has to read them knowing that the lead's own expectation was not blind. The specification of this round (the candidate multiples, the caps, the V1 construction) was written by me from the task text before any run; the spec was committed first, the V1 factors second, and the code third, all before the first simulation of the main round.

## What the two variants are, and are not

Neither variant models vLLM-specific mechanics: not vLLM's block-level (16-token) lazy LRU eviction (the simulator evicts whole sessions LRU-first and decides hit or miss at admission), not the absence of a waiting-prefix refresh, not vLLM's chunked-prefill token budget and scheduler (the simulator keeps its SGLang-calibrated `prefill_chunk_budget` 8192 and its two iteration models). These are predictions of the calibrated SGLang-like model run at vLLM's KV capacity (V0) and additionally at vLLM's measured all-miss token rate (V1), not predictions of a vLLM model. V1's all-miss token rate equals the target by construction (it is fitted, not predicted).

## Provenance: what was run

Generated by `python -m prefixmeta.r9_vllm_predict assemble` from the report `results/r9_vllm_report/20261030-122723` (the tables below are that report's `tables.md`, verbatim; nothing is retyped).

Spec: `configs/r9_vllm_predict.yaml` (sha256 `98aa0f228e1df1e49d3910035c62ef41b3b457eca875ab148379cbea437d55ca`; the first commit of the spec, before any run, had sha256 recorded in the notes); KV pool 300,000 tokens; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes (the stages run one after the other).

**V0 / mixed** (`engine.batching` = `mixed`, out-root `results/r9_vllm_v0_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v0_mixed/r7_lambda_miss/20261030-122443 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:24:43 | 1.2 | True | - |
| curves | results/r9_vllm_v0_mixed/r7_curves/20261030-122445 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:45 | 2.2 | True | - |
| edge | results/r9_vllm_v0_mixed/r7_edge/20261030-122448 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:48 | 1.9 | True | - |
| pairs_all | results/r9_vllm_v0_mixed/r7_pairs_all/20261030-122451 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:24:51 | 29.1 | True | - |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_mixed
```

**V0 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r9_vllm_v0_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v0_separate/r7_lambda_miss/20261030-122524 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:25:23 | 1.3 | True | engine.batching=separate_prefill_priority |
| curves | results/r9_vllm_v0_separate/r7_curves/20261030-122526 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:26 | 2.2 | True | engine.batching=separate_prefill_priority |
| edge | results/r9_vllm_v0_separate/r7_edge/20261030-122529 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:29 | 2 | True | engine.batching=separate_prefill_priority |
| pairs_all | results/r9_vllm_v0_separate/r7_pairs_all/20261030-122532 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:25:32 | 28.8 | True | engine.batching=separate_prefill_priority |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v0_separate --set engine.batching=separate_prefill_priority
```

**V1 / mixed** (`engine.batching` = `mixed`, out-root `results/r9_vllm_v1_mixed`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v1_mixed/r7_lambda_miss/20261030-122604 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:26:04 | 1.2 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| curves | results/r9_vllm_v1_mixed/r7_curves/20261030-122606 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:06 | 2.2 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| edge | results/r9_vllm_v1_mixed/r7_edge/20261030-122609 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:09 | 1.9 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |
| pairs_all | results/r9_vllm_v1_mixed/r7_pairs_all/20261030-122612 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:12 | 28.9 | True | engine.per_token_s=6.8121320000e-05 engine.prefill_attn_s=2.4375680000e-09 engine.decode_attn_s=3.3734200000e-04 |

Recorded stage wall time: 34 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_mixed --set engine.per_token_s=6.8121320000e-05 --set engine.prefill_attn_s=2.4375680000e-09 --set engine.decode_attn_s=3.3734200000e-04
```

**V1 / separate** (`engine.batching` = `separate_prefill_priority`, out-root `results/r9_vllm_v1_separate`):

| stage | result dir | commit | dirty | seeds | start | wall s | spec copy identical to the committed file | overrides |
|---|---|---|---|---|---|---|---|---|
| lambda_miss | results/r9_vllm_v1_separate/r7_lambda_miss/20261030-122644 | 29746a9d4 | False | 0..2 (3) | 2026-10-30T12:26:44 | 1.2 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| curves | results/r9_vllm_v1_separate/r7_curves/20261030-122647 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:47 | 2.1 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| edge | results/r9_vllm_v1_separate/r7_edge/20261030-122650 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:50 | 1.8 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |
| pairs_all | results/r9_vllm_v1_separate/r7_pairs_all/20261030-122653 | 29746a9d4 | False | 0..9 (10) | 2026-10-30T12:26:53 | 28 | True | engine.batching=separate_prefill_priority engine.per_token_s=6.7645560000e-05 engine.prefill_attn_s=2.4205440000e-09 engine.decode_attn_s=3.3498600000e-04 |

Recorded stage wall time: 33 s (0.6 min). Commands (argv as recorded in each `meta.json`; run from the worktree root):

```
experiments/r7_robustness_run.py lambda_miss --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
experiments/r7_robustness_run.py curves --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
experiments/r7_robustness_run.py edge --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\vllm-predict\src\prefixmeta\r9_vllm_predict.py pairs_all --spec configs/r9_vllm_predict.yaml --workers 6 --out-root results/r9_vllm_v1_separate --set engine.batching=separate_prefill_priority --set engine.per_token_s=6.7645560000e-05 --set engine.prefill_attn_s=2.4205440000e-09 --set engine.decode_attn_s=3.3498600000e-04
```

Total recorded stage wall time over the four trees: 136 s (2.3 min).

## Tables (generated)

## Overview

Landmarks per variant and mode:

| variant | mode | lambda_miss turns-based (sessions/s) | all-miss token rate (tok/s) | peak n | peak mu (sessions/s) | peak mu / lambda_miss | cap n (B4v rule) | n at hit 0.5 | edge hi (x lambda_miss) | edge in real units (hi x 0.0657) | edge censored |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 0.07219 | 1.122e+04 | 24 | 0.2217 | 3.071 | 20 | 31.46 | 2 | 0.1314 | False |
| V0 | separate | 0.07136 | 1.115e+04 | 24 | 0.2208 | 3.095 | 20 | 32.6 | 2 | 0.1314 | False |
| V1 | mixed | 0.06623 | 1.036e+04 | 24 | 0.2154 | 3.253 | 20 | 31.42 | 2 | 0.1314 | False |
| V1 | separate | 0.06633 | 1.034e+04 | 24 | 0.2151 | 3.243 | 20 | 32.41 | 2 | 0.1314 | False |

B3v at the cap the B4v rule picks, every candidate multiple (the full tables, with the other caps, are in the blocks below):

| variant | mode | x lambda_miss | picked cap | BURST trapped | NOBURST good | CAPPED recovered | PASS per-arm | same-seed count | PASS same-seed |
|---|---|---|---|---|---|---|---|---|---|
| V0 | mixed | 1.1 | 20 | 4/10 | 10/10 | 10/10 | FAIL | 4/10 | FAIL |
| V0 | mixed | 1.15 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 1.5 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V0 | mixed | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2 | 20 | 10/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | mixed | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.1 | 20 | 6/10 | 10/10 | 10/10 | FAIL | 6/10 | FAIL |
| V0 | separate | 1.15 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.25 | 20 | 10/10 | 10/10 | 10/10 | PASS | 10/10 | PASS |
| V0 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 1.5 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V0 | separate | 1.65 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V0 | separate | 2.35 | 20 | 10/10 | 6/10 | 10/10 | FAIL | 6/10 | FAIL |
| V1 | mixed | 1.1 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | mixed | 1.15 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.5 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 1.65 | 20 | 7/10 | 10/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | mixed | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | mixed | 2.35 | 20 | 10/10 | 7/10 | 10/10 | PASS | 7/10 | PASS |
| V1 | separate | 1.1 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.15 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.25 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.35 | 20 | 9/10 | 10/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 1.5 | 20 | 10/10 | 10/10 | 10/10 | PASS | 10/10 | PASS |
| V1 | separate | 1.65 | 20 | 8/10 | 10/10 | 10/10 | PASS | 8/10 | PASS |
| V1 | separate | 2 | 20 | 9/10 | 9/10 | 10/10 | PASS | 9/10 | PASS |
| V1 | separate | 2.35 | 20 | 10/10 | 7/10 | 10/10 | PASS | 7/10 | PASS |

## V0 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.072187 | 0.0018897 | 0.069444 | 11220 | 1 | 0.071986 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 11,219.7 tok/s = 1.0841 x the vLLM rate; lambda_miss 0.07219 sessions/s = 1.0987 x the vLLM value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1767 / 0.93 |
| 20 | 0.2156 / 0.93 |
| 24 | 0.2217 / 0.89 |
| 28 | 0.1672 / 0.74 |
| 32 | 0.1122 / 0.46 |
| 40 | 0.0727 / 0.03 |
| 48 | 0.0711 / 0.00 |
| 96 | 0.0786 / 0.00 |
| 300 | 0.1119 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2217 | 20 | 0.5047 | 0 | 24 | 0.222 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2217 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.071 |
| hit fraction at the peak n | 0.8898 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.222 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.46 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.99 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 36.9 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.6, s1: 32.8, s2: 30.5, s3: 30.4, s4: 30.4, s5: 32.8, s6: 31.3, s7: 32.1, s8: 33.3, s9: 30.0 |
| mu(300) / peak mu | 0.5047 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0239; -0.1607 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1735 / 0.1774 / 0.1766 / 0.1733 / 0.1790 / 0.1787 / 0.1769 / 0.1776 / 0.1761 / 0.1784 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2130 / 0.2170 / 0.2132 / 0.2137 / 0.2201 / 0.2108 / 0.2156 / 0.2179 / 0.2174 / 0.2176 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2261 / 0.2224 / 0.1904 / 0.2063 / 0.2435 / 0.1813 / 0.2105 / 0.2476 / 0.2473 / 0.2413 | 0.91 / 0.89 / 0.85 / 0.88 / 0.91 / 0.84 / 0.87 / 0.92 / 0.92 / 0.91 |
| 28 | 0.2032 / 0.1871 / 0.1413 / 0.1462 / 0.1729 / 0.1244 / 0.1241 / 0.1979 / 0.2083 / 0.1667 | 0.82 / 0.79 / 0.70 / 0.70 / 0.76 / 0.65 / 0.62 / 0.81 / 0.82 / 0.75 |
| 32 | 0.1458 / 0.1285 / 0.0935 / 0.0959 / 0.0866 / 0.1246 / 0.1081 / 0.1184 / 0.1415 / 0.0786 | 0.62 / 0.55 / 0.38 / 0.37 / 0.33 / 0.55 / 0.48 / 0.51 / 0.60 / 0.25 |
| 40 | 0.0735 / 0.0699 / 0.0765 / 0.0704 / 0.0643 / 0.0830 / 0.0744 / 0.0735 / 0.0738 / 0.0674 | 0.02 / 0.00 / 0.07 / 0.03 / 0.00 / 0.07 / 0.05 / 0.05 / 0.01 / 0.03 |
| 48 | 0.0706 / 0.0702 / 0.0734 / 0.0698 / 0.0637 / 0.0775 / 0.0739 / 0.0749 / 0.0725 / 0.0650 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0750 / 0.0741 / 0.0783 / 0.0788 / 0.0743 / 0.0784 / 0.0785 / 0.0880 / 0.0793 / 0.0817 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1128 / 0.1102 / 0.1105 / 0.1142 / 0.1103 / 0.1098 / 0.1104 / 0.1148 / 0.1145 / 0.1113 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.09023 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0004412 | 0.9311 | 0 |
| Exp(5 s) (record) | 1.5 | 0.1083 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002697 | 0.9296 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1263 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006728 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1444 | 10/10 (1.00) [0.72, 1.00] | True | 1.2 | 12 | 0.4276 | 0.9246 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1805 | 6/10 (0.60) [0.31, 0.83] | False | 37.2 | 119 | 36.4 | 0.627 | 0 |
| Exp(5 s) (record) | 3 | 0.2166 | 1/10 (0.10) [0.02, 0.40] | False | 180.1 | 270 | 123.8 | 0.1992 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.072187 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1444 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07219; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.06 x and through 0.5 at 2.6 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07941 | hi = 1.25 (low) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.996 to 1.010 | 148.8 | 0 | 0.007708 | IITTIITTII | RRRRRRRRRR |
| 1.15 | 0.08301 | hi = 1.25 (high); hi = 1.5 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.994 to 1.015 | 152.3 | 0 | 0.008271 | ITTTIITTTI | RRRRRRRRRR |
| 1.25 | 0.09023 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.999 to 1.020 | 170.5 | 0 | 0.0097 | TTTTITTTTT | RRRRRRRRRR |
| 1.35 | 0.09745 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.006 to 1.026 | 198.4 | 0 | 0.01067 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.1083 | hi = 1.75 (high); hi = 2.5 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.018 to 1.034 | 249.9 | 0 | 0.01289 | TTTTIITTTI | RRRRRRRRRR |
| 1.65 | 0.1191 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.027 to 1.043 | 290.2 | 0 | 0.01506 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1444 | hi = 2.5 (high) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.048 to 1.059 | 399.1 | 0 | 19.56 | TTTTTTTTTT | RRRRRTRRRR |
| 2.35 | 0.1696 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.063 to 1.073 | 522.5 | 0 | 120.4 | TTTTTTTTTT | RRTRRTRTRT |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.01176 | 0.9312 |
| 1.1 (extra) | 20 * | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00771 | 0.9312 |
| 1.1 (extra) | 24 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.00769 | 0.9312 |
| 1.1 (extra) | 28 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 0.007709 | 0.9312 |
| 1.1 (extra) | 32 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 19.21 | 0.7532 |
| 1.1 (extra) | 40 (extra) | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.8 | 0.08885 |
| 1.15 | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01589 | 0.9314 |
| 1.15 | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008452 | 0.9314 |
| 1.15 | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.008271 | 0.9314 |
| 1.15 | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00829 | 0.9314 |
| 1.15 | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 25.26 | 0.7722 |
| 1.15 | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.8 | 0.08945 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.04198 | 0.9308 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01006 | 0.9308 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0097 | 0.9308 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009669 | 0.9308 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 36.17 | 0.7766 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 235.1 | 0.08596 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06429 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0184 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01068 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01074 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 60.62 | 0.6711 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 276.3 | 0.08874 |
| 1.5 | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.09209 | 0.9313 |
| 1.5 | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01914 | 0.9314 |
| 1.5 | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01313 | 0.9314 |
| 1.5 | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.8441 | 0.9234 |
| 1.5 | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 128.3 | 0.4841 |
| 1.5 | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 345.5 | 0.08463 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1464 | 0.9313 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01706 | 0.9313 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01505 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 6.718 | 0.9098 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 193.6 | 0.4838 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 417 | 0.08505 |
| 2 | 16 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 21.95 | 0.9331 |
| 2 | 20 * | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2795 | 0.9332 |
| 2 | 24 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06608 | 0.9319 |
| 2 | 28 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 5/10 (0.50) [0.24, 0.76] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 55.58 | 0.834 |
| 2 | 32 | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 358.9 | 0.4929 |
| 2 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 585.8 | 0.07931 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 174.9 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.569 | 0.9317 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.028 | 0.9242 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 165 | 0.79 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 5 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 528.2 | 0.4758 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 760.2 | 0.07562 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTIITTII | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | ITTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTTTTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RRTRRTRTRT | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V0 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.071359 | 0.0012945 | 0.068889 | 11147 | 0.99999 | 0.071221 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 11,146.8 tok/s = 1.0771 x the vLLM rate; lambda_miss 0.07136 sessions/s = 1.0861 x the vLLM value.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1755 / 0.93 |
| 20 | 0.2137 / 0.93 |
| 24 | 0.2208 / 0.89 |
| 28 | 0.1797 / 0.77 |
| 32 | 0.1222 / 0.53 |
| 40 | 0.0767 / 0.11 |
| 48 | 0.0710 / 0.01 |
| 96 | 0.0781 / 0.00 |
| 300 | 0.1115 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2208 | 20 | 0.5051 | 0 | 24 | 0.2215 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2208 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.095 |
| hit fraction at the peak n | 0.8917 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2215 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 32.6 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 23.14 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 38.22 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 34.6, s1: 33.4, s2: 31.1, s3: 32.4, s4: 31.2, s5: 33.2, s6: 31.8, s7: 32.6, s8: 33.6, s9: 32.1 |
| mu(300) / peak mu | 0.5051 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0184; -0.1633 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1724 / 0.1764 / 0.1754 / 0.1721 / 0.1777 / 0.1773 / 0.1755 / 0.1766 / 0.1750 / 0.1771 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2099 / 0.2152 / 0.2110 / 0.2118 / 0.2177 / 0.2100 / 0.2134 / 0.2161 / 0.2157 / 0.2158 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2248 / 0.2183 / 0.1910 / 0.2204 / 0.2358 / 0.1933 / 0.2144 / 0.2453 / 0.2385 / 0.2267 | 0.91 / 0.89 / 0.85 / 0.89 / 0.91 / 0.86 / 0.88 / 0.91 / 0.91 / 0.90 |
| 28 | 0.2015 / 0.1939 / 0.1445 / 0.1490 / 0.1932 / 0.1313 / 0.1476 / 0.2251 / 0.2204 / 0.1903 | 0.82 / 0.80 / 0.71 / 0.70 / 0.79 / 0.67 / 0.69 / 0.84 / 0.84 / 0.79 |
| 32 | 0.1520 / 0.1417 / 0.0980 / 0.1185 / 0.1017 / 0.1256 / 0.1101 / 0.1218 / 0.1415 / 0.1112 | 0.65 / 0.60 / 0.44 / 0.52 / 0.43 / 0.57 / 0.49 / 0.53 / 0.60 / 0.50 |
| 40 | 0.0871 / 0.0723 / 0.0801 / 0.0753 / 0.0694 / 0.0829 / 0.0771 / 0.0754 / 0.0802 / 0.0670 | 0.20 / 0.06 / 0.13 / 0.12 / 0.09 / 0.09 / 0.10 / 0.11 / 0.11 / 0.05 |
| 48 | 0.0701 / 0.0700 / 0.0763 / 0.0694 / 0.0627 / 0.0774 / 0.0733 / 0.0741 / 0.0718 / 0.0647 | 0.01 / 0.00 / 0.05 / 0.01 / 0.00 / 0.01 / 0.01 / 0.00 / 0.00 / 0.01 |
| 96 | 0.0752 / 0.0737 / 0.0772 / 0.0777 / 0.0743 / 0.0778 / 0.0781 / 0.0871 / 0.0784 / 0.0814 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1125 / 0.1099 / 0.1102 / 0.1137 / 0.1102 / 0.1098 / 0.1100 / 0.1144 / 0.1139 / 0.1109 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.0892 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0001459 | 0.9314 | 0 |
| Exp(5 s) (record) | 1.5 | 0.107 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.0006232 | 0.9297 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1249 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0009475 | 0.9294 | 0 |
| Exp(5 s) (record) | 2 | 0.1427 | 10/10 (1.00) [0.72, 1.00] | True | 0.4 | 4 | 0.4368 | 0.9257 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1784 | 8/10 (0.80) [0.49, 0.94] | False | 18.6 | 115 | 16.01 | 0.801 | 0 |
| Exp(5 s) (record) | 3 | 0.2141 | 1/10 (0.10) [0.02, 0.40] | False | 177 | 283 | 124.2 | 0.2039 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.071359 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1427 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.07136; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.12 x and through 0.5 at 2.71 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07849 | hi = 1.25 (low) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.005 | 149.7 | 0 | 0.007337 | IITTTITTIT | RRRRRRRRRR |
| 1.15 | 0.08206 | hi = 1.25 (high); hi = 1.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.990 to 1.015 | 161.3 | 0 | 0.008262 | TTTTTITTTI | RRRRRRRRRR |
| 1.25 | 0.0892 | hi = 1.75 (low) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.995 to 1.015 | 179.5 | 0 | 0.009333 | TTTTTTTTTT | RRRRRRRRRR |
| 1.35 | 0.09633 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.021 | 206.9 | 0 | 0.01043 | TTTTITTTTT | RRRRRRRRRR |
| 1.5 | 0.107 | hi = 1.75 (high); hi = 2.5 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.014 to 1.027 | 252.4 | 0 | 0.0124 | TTTTIITTTT | RRRRRRRRRR |
| 1.65 | 0.1177 | hi = 2 (high); hi = 3 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.022 to 1.038 | 295.4 | 0 | 0.01452 | TTTTTITTTT | RRRRRRRRRR |
| 2 | 0.1427 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.043 to 1.051 | 409.2 | 0 | 20.24 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1677 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.066 | 521.4 | 0 | 125.5 | TTTTTTTTTT | RTTRRTRTRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.01119 | 0.9313 |
| 1.1 (extra) | 20 * | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007326 | 0.9313 |
| 1.1 (extra) | 24 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.007339 | 0.9313 |
| 1.1 (extra) | 28 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.00732 | 0.9313 |
| 1.1 (extra) | 32 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 6.446 | 0.8805 |
| 1.1 (extra) | 40 (extra) | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 140.2 | 0.1696 |
| 1.15 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02577 | 0.9316 |
| 1.15 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008418 | 0.9316 |
| 1.15 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008245 | 0.9316 |
| 1.15 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.008253 | 0.9316 |
| 1.15 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 5/10 (0.50) [0.24, 0.76] | FAIL | 11.26 | 0.8277 |
| 1.15 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 167.9 | 0.1429 |
| 1.25 | 16 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.04704 | 0.9307 |
| 1.25 | 20 * | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01016 | 0.9307 |
| 1.25 | 24 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009299 | 0.9307 |
| 1.25 | 28 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.009296 | 0.9307 |
| 1.25 | 32 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 1 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 18.64 | 0.8112 |
| 1.25 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 211.2 | 0.1688 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.06025 | 0.9308 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01775 | 0.9308 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.0105 | 0.9308 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01043 | 0.9308 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 29.79 | 0.7971 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 249 | 0.1521 |
| 1.5 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.09019 | 0.9313 |
| 1.5 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.02162 | 0.9313 |
| 1.5 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.014 | 0.9313 |
| 1.5 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01245 | 0.9313 |
| 1.5 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 0 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 79.29 | 0.6274 |
| 1.5 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 313.1 | 0.1551 |
| 1.65 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1452 | 0.9312 |
| 1.65 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01615 | 0.9312 |
| 1.65 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01464 | 0.9312 |
| 1.65 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2905 | 0.9286 |
| 1.65 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 134.6 | 0.5421 |
| 1.65 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 386.9 | 0.1566 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 19.74 | 0.9331 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.2189 | 0.9331 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05659 | 0.9323 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 7/10 (0.70) [0.40, 0.89] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 27.86 | 0.8781 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 306.7 | 0.5455 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 561.4 | 0.1339 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.3 | 0.9328 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 1.461 | 0.9321 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 0.2392 | 0.9277 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 121.2 | 0.8169 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 457.7 | 0.5362 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 724.6 | 0.1379 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | IITTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTITTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRTRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `mixed` (PRIMARY): engine.batching = `mixed`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.066228 | 0.00073592 | 0.065926 | 10358 | 1 | 0.066805 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 10,358.3 tok/s = 1.0009 x the vLLM rate; lambda_miss 0.06623 sessions/s = 1.0080 x the vLLM value. V1 factor f = 1.0882 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 10,358.30 tok/s, +0.09% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1753 / 0.93 |
| 20 | 0.2127 / 0.93 |
| 24 | 0.2154 / 0.89 |
| 28 | 0.1617 / 0.74 |
| 32 | 0.1045 / 0.46 |
| 40 | 0.0663 / 0.03 |
| 48 | 0.0655 / 0.00 |
| 96 | 0.0741 / 0.00 |
| 300 | 0.1063 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2154 | 20 | 0.4934 | 0 | 24 | 0.2153 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2154 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.253 |
| hit fraction at the peak n | 0.8883 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2153 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 31.42 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.87 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 36.79 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 33.3, s1: 31.4, s2: 30.6, s3: 30.8, s4: 30.5, s5: 32.9, s6: 31.6, s7: 31.1, s8: 33.6, s9: 30.1 |
| mu(300) / peak mu | 0.4934 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0393; -0.1433 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1724 / 0.1763 / 0.1752 / 0.1719 / 0.1777 / 0.1770 / 0.1750 / 0.1763 / 0.1747 / 0.1768 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2096 / 0.2152 / 0.2100 / 0.2115 / 0.2175 / 0.2040 / 0.2126 / 0.2158 / 0.2153 / 0.2156 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2275 / 0.2162 / 0.1734 / 0.2155 / 0.2372 / 0.1707 / 0.2084 / 0.2422 / 0.2382 / 0.2251 | 0.91 / 0.89 / 0.83 / 0.89 / 0.91 / 0.83 / 0.88 / 0.91 / 0.91 / 0.90 |
| 28 | 0.2164 / 0.1843 / 0.1301 / 0.1424 / 0.1592 / 0.1234 / 0.1263 / 0.1885 / 0.1918 / 0.1551 | 0.85 / 0.80 / 0.69 / 0.70 / 0.74 / 0.67 / 0.65 / 0.80 / 0.81 / 0.74 |
| 32 | 0.1328 / 0.1006 / 0.0920 / 0.0944 / 0.0847 / 0.1212 / 0.1019 / 0.0981 / 0.1431 / 0.0759 | 0.60 / 0.45 / 0.40 / 0.42 / 0.36 / 0.56 / 0.48 / 0.41 / 0.63 / 0.28 |
| 40 | 0.0662 / 0.0647 / 0.0712 / 0.0642 / 0.0586 / 0.0718 / 0.0707 / 0.0696 / 0.0664 / 0.0598 | 0.00 / 0.00 / 0.07 / 0.01 / 0.00 / 0.02 / 0.06 / 0.08 / 0.00 / 0.02 |
| 48 | 0.0647 / 0.0643 / 0.0670 / 0.0647 / 0.0580 / 0.0714 / 0.0688 / 0.0704 / 0.0668 / 0.0589 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 96 | 0.0709 / 0.0694 / 0.0725 / 0.0747 / 0.0707 / 0.0737 / 0.0741 / 0.0823 / 0.0754 / 0.0770 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1072 / 0.1048 / 0.1049 / 0.1089 / 0.1050 / 0.1041 / 0.1047 / 0.1093 / 0.1083 / 0.1056 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.08278 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002517 | 0.9325 | 0 |
| Exp(5 s) (record) | 1.5 | 0.09934 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0002635 | 0.9309 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1159 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 4.653e-05 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1325 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.002491 | 0.9303 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1656 | 7/10 (0.70) [0.40, 0.89] | False | 14 | 95 | 11.93 | 0.7955 | 0 |
| Exp(5 s) (record) | 3 | 0.1987 | 3/10 (0.30) [0.11, 0.60] | False | 131.8 | 241 | 96.89 | 0.3171 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.066228 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1325 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.06623; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.08 x and through 0.5 at 2.75 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07285 | hi = 1.25 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.991 to 1.004 | 135.5 | 0 | 0.007196 | ITTTTITTIT | RRRRRRRRRR |
| 1.15 | 0.07616 | hi = 1.25 (high); hi = 1.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.992 to 1.012 | 142.9 | 0 | 0.007817 | TTTTTITTTT | RRRRRRRRRR |
| 1.25 | 0.08278 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.001 to 1.019 | 169.2 | 0 | 0.009012 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.08941 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.009 to 1.024 | 193.6 | 0 | 0.01022 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.09934 | hi = 1.75 (high); hi = 2.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.017 to 1.034 | 233.2 | 0 | 0.01195 | TTTTTITTTT | RRRRRRRRRR |
| 1.65 | 0.1093 | hi = 2 (high); hi = 3 (low) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.028 to 1.044 | 277 | 0 | 0.01425 | TTTTIITTTI | RRRRRRRRRR |
| 2 | 0.1325 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.047 to 1.056 | 375.8 | 0 | 15.82 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1556 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 1.058 to 1.068 | 480.7 | 0 | 91.22 | TTTTTTTTTT | RTTRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.009176 | 0.9313 |
| 1.1 (extra) | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007184 | 0.9313 |
| 1.1 (extra) | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007184 | 0.9313 |
| 1.1 (extra) | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.007183 | 0.9313 |
| 1.1 (extra) | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 21.54 | 0.7221 |
| 1.1 (extra) | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 169.9 | 0.08154 |
| 1.15 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007817 | 0.9312 |
| 1.15 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007805 | 0.9312 |
| 1.15 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007806 | 0.9312 |
| 1.15 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007789 | 0.9312 |
| 1.15 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 31.16 | 0.728 |
| 1.15 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 189.2 | 0.08148 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.02014 | 0.9314 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009294 | 0.9314 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009014 | 0.9314 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008967 | 0.9314 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 5/10 (0.50) [0.24, 0.76] | 1 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 46.82 | 0.6594 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 232.2 | 0.08693 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05307 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01129 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01016 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01015 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 4/10 (0.40) [0.17, 0.69] | 1 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 69.13 | 0.6218 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 8 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 271.6 | 0.08946 |
| 1.5 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.07421 | 0.931 |
| 1.5 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01885 | 0.931 |
| 1.5 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01198 | 0.931 |
| 1.5 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.7261 | 0.9134 |
| 1.5 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 1 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 125.7 | 0.504 |
| 1.5 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 329.9 | 0.07164 |
| 1.65 | 16 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.07807 | 0.9312 |
| 1.65 | 20 * | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01426 | 0.9312 |
| 1.65 | 24 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.01406 | 0.9312 |
| 1.65 | 28 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 6/10 (0.60) [0.31, 0.83] | FAIL | 6.811 | 0.9034 |
| 1.65 | 32 | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 4 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 196.7 | 0.4314 |
| 1.65 | 40 (extra) | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 393.1 | 0.07283 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 2.242 | 0.9318 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1283 | 0.9318 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.03132 | 0.9312 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 4/10 (0.40) [0.17, 0.69] | 0 | FAIL | 4/10 (0.40) [0.17, 0.69] | FAIL | 61.65 | 0.8177 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 353 | 0.431 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 548 | 0.08567 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 1/10 (0.10) [0.02, 0.40] | 0 | FAIL | 1/10 (0.10) [0.02, 0.40] | FAIL | 88.6 | 0.9329 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.4853 | 0.9328 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.06998 | 0.9327 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 161.5 | 0.801 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 503.5 | 0.4466 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 702.6 | 0.07068 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | ITTTTITTIT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTIITTTI | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.

## V1 / `separate` (SECONDARY): engine.batching = `separate_prefill_priority`, KV pool 300,000 tokens

### B1v. All-miss capacity lambda_miss (cache off, closed POP 32, window [900, 2700) s, seeds 0,1,2)

| workload | tool-time mean (s) | tool-time CV | lambda_miss (turns-based, sessions/s) | sd over seeds | lambda_miss (sessions/s) | all-miss token rate (tok/s) | GPU busy | POP 64 lambda_miss (turns) | POP 64 busy |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 5 | 1 | 0.066328 | 0.00040244 | 0.06537 | 10342 | 0.9999 | 0.065601 | 1 |

Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate 10,349 tok/s, measured lambda_miss 0.0657 sessions/s. This block: token rate 10,341.9 tok/s = 0.9993 x the vLLM rate; lambda_miss 0.06633 sessions/s = 1.0096 x the vLLM value. V1 factor f = 1.0806 on per_token_s, prefill_attn_s, decode_attn_s (frozen from the quick B1 check, accepted rate 10,341.87 tok/s, -0.07% of the target); the main B1v token rate equals the check's accepted rate exactly: **True**. The token rate is FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.

### B4v. Closed curve mu(n) and hit fraction (cache on, seeds 0-9, window [900, 2700) s)

Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:

| n | Exp(5 s) (record) |
|---|---|
| 16 | 0.1742 / 0.93 |
| 20 | 0.2114 / 0.93 |
| 24 | 0.2151 / 0.89 |
| 28 | 0.1650 / 0.75 |
| 32 | 0.1152 / 0.52 |
| 40 | 0.0709 / 0.10 |
| 48 | 0.0656 / 0.01 |
| 96 | 0.0738 / 0.00 |
| 300 | 0.1048 / 0.00 |

Landmarks (the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):

| workload | peak n | peak mu (turns-based sessions/s) | cap n (smallest within 5%) | mu(300) / peak | hit(300) | [sessions-based] peak n | [sessions-based] peak mu | [sessions-based] cap n |
|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 24 | 0.2151 | 20 | 0.4869 | 0 | 24 | 0.2159 | 20 |

Landmarks of the closed curve:

| landmark | value |
|---|---|
| peak n (first argmax of the seed-mean turns-based mu) | 24 |
| peak mu (turns-based sessions/s) | 0.2151 |
| peak mu / lambda_miss (the registration's mu* / lambda_ref reading) | 3.243 |
| hit fraction at the peak n | 0.8897 |
| cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu) | 20 |
| [sessions-based] peak n / peak mu / cap n | 24 / 0.2159 / 20 |
| n at which the seed-mean hit fraction falls through 0.5 (linear interpolation) | 32.41 |
| n at which the seed-mean hit fraction falls through 0.9 (linear interpolation) | 22.98 |
| n at which the seed-mean hit fraction falls through 0.2 (linear interpolation) | 38.17 |
| largest grid n with seed-mean hit >= 0.9 | 20 |
| per-seed n at which the hit fraction falls through 0.5 | s0: 34.3, s1: 33.7, s2: 31.5, s3: 32.2, s4: 31.1, s5: 33.2, s6: 31.9, s7: 33.0, s8: 33.7, s9: 30.3 |
| mu(300) / peak mu | 0.4869 |
| cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1 | +0.0342; -0.1475 |

Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):

| n | mu turns-based by seed | hit by seed |
|---|---|---|
| 16 | 0.1717 / 0.1750 / 0.1742 / 0.1705 / 0.1766 / 0.1755 / 0.1739 / 0.1753 / 0.1740 / 0.1757 | 0.93 / 0.93 / 0.94 / 0.93 / 0.93 / 0.94 / 0.94 / 0.92 / 0.93 / 0.93 |
| 20 | 0.2087 / 0.2133 / 0.2101 / 0.2096 / 0.2156 / 0.2045 / 0.2110 / 0.2134 / 0.2141 / 0.2135 | 0.93 / 0.93 / 0.93 / 0.93 / 0.93 / 0.92 / 0.94 / 0.93 / 0.93 / 0.93 |
| 24 | 0.2132 / 0.2173 / 0.1764 / 0.2102 / 0.2334 / 0.1795 / 0.2122 / 0.2386 / 0.2394 / 0.2311 | 0.90 / 0.89 / 0.84 / 0.89 / 0.91 / 0.84 / 0.89 / 0.91 / 0.92 / 0.91 |
| 28 | 0.2018 / 0.1880 / 0.1428 / 0.1466 / 0.1540 / 0.1238 / 0.1287 / 0.1997 / 0.2021 / 0.1622 | 0.83 / 0.81 / 0.72 / 0.71 / 0.73 / 0.67 / 0.66 / 0.82 / 0.82 / 0.75 |
| 32 | 0.1413 / 0.1328 / 0.0979 / 0.1120 / 0.0959 / 0.1247 / 0.1044 / 0.1228 / 0.1402 / 0.0796 | 0.63 / 0.60 / 0.47 / 0.51 / 0.44 / 0.58 / 0.49 / 0.55 / 0.62 / 0.31 |
| 40 | 0.0779 / 0.0716 / 0.0743 / 0.0658 / 0.0625 / 0.0718 / 0.0788 / 0.0721 / 0.0683 / 0.0661 | 0.17 / 0.11 / 0.12 / 0.06 / 0.09 / 0.02 / 0.19 / 0.12 / 0.04 / 0.12 |
| 48 | 0.0645 / 0.0642 / 0.0686 / 0.0638 / 0.0586 / 0.0716 / 0.0684 / 0.0710 / 0.0666 / 0.0584 | 0.02 / 0.00 / 0.02 / 0.00 / 0.01 / 0.01 / 0.00 / 0.02 / 0.00 / 0.00 |
| 96 | 0.0710 / 0.0689 / 0.0726 / 0.0748 / 0.0701 / 0.0733 / 0.0739 / 0.0816 / 0.0753 / 0.0769 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |
| 300 | 0.1059 / 0.1033 / 0.1035 / 0.1070 / 0.1037 / 0.1028 / 0.1030 / 0.1080 / 0.1064 / 0.1040 | 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 |

### B2v. From-empty open-loop stability (cache on, B2 rule, 3000 s, 10 seeds)

Stable runs per multiple of the workload's own lambda_miss (from empty, 3000 s, B2 rule), with Wilson 95% intervals:

| workload | multiple of lambda_miss | lambda (sessions/s) | stable runs | all stable | final backlog mean | final backlog max | trend rise mean | tail hit mean | stopped early |
|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 1.25 | 0.08291 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.001759 | 0.9326 | 0 |
| Exp(5 s) (record) | 1.5 | 0.09949 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -1.641e-05 | 0.9308 | 0 |
| Exp(5 s) (record) | 1.75 | 0.1161 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | -0.0008713 | 0.9296 | 0 |
| Exp(5 s) (record) | 2 | 0.1327 | 10/10 (1.00) [0.72, 1.00] | True | 0 | 0 | 0.004477 | 0.9304 | 0 |
| Exp(5 s) (record) | 2.5 | 0.1658 | 7/10 (0.70) [0.40, 0.89] | False | 18.9 | 117 | 14.22 | 0.7959 | 0 |
| Exp(5 s) (record) | 3 | 0.199 | 3/10 (0.30) [0.11, 0.60] | False | 137.5 | 252 | 98.87 | 0.3172 | 0 |

Measured metastability window and the paired-arm test points:

| workload | lambda_miss (sessions/s) | hi (contiguous all-stable) | largest all-stable multiple | same | refinement grid run | window | test points (x lambda_miss) |
|---|---|---|---|---|---|---|---|
| Exp(5 s) (record) | 0.066328 | 2 | 2 | True | False | [1, 2] | 1.35, 1.65 |

**Edge hi = 2 x lambda_miss = 0.1327 sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = 0.06633; largest all-stable multiple irrespective of contiguity: 2). In multiples of the REAL lambda_miss (0.0657 sessions/s) the same multiple is 0.1314 sessions/s (the dimensionless-behaviour reading). Supplementary: the stable fraction falls through 0.95 at 2.08 x and through 0.5 at 2.75 x (linear interpolation between grid multiples; NaN = never).

Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):

| real edge hi (x lambda_ref) | test point low | test point high |
|---|---|---|
| 1.25 | 1.1 | 1.15 |
| 1.5 | 1.15 | 1.35 |
| 1.75 | 1.25 | 1.5 |
| 2 | 1.35 | 1.65 |
| 2.5 | 1.5 | 2 |
| 3 | 1.65 | 2.35 |

### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst 200 sessions in 60 s at t = 1200 s, 10 seeds, evaluation window = last 2500 s)

Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and mode, and the mean backlog (waiting requests) over the evaluation window.

| x lambda_miss | lambda (sessions/s) | real registration uses it if | BURST trapped | NOBURST good | BURST stuck (hit < 0.2) | trapped runs: token rate / all-miss rate | trapped runs: mean backlog | BURST hit (mean of runs) | NOBURST backlog (mean) | BURST classes by seed | NOBURST classes by seed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 0.07296 | hi = 1.25 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.988 to 1.008 | 139 | 0 | 0.007273 | TTTTTITTTT | RRRRRRRRRR |
| 1.15 | 0.07628 | hi = 1.25 (high); hi = 1.5 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.991 to 1.008 | 151.6 | 0 | 0.007641 | TTTTTITTTT | RRRRRRRRRR |
| 1.25 | 0.08291 | hi = 1.75 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.999 to 1.017 | 178.4 | 0 | 0.00875 | TTTTTITTTT | RRRRRRRRRR |
| 1.35 | 0.08954 | hi = 1.5 (high); hi = 2 (low) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.008 to 1.023 | 203.2 | 0 | 0.009878 | TTTTTITTTT | RRRRRRRRRR |
| 1.5 | 0.09949 | hi = 1.75 (high); hi = 2.5 (low) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.015 to 1.035 | 238.3 | 0 | 0.01166 | TTTTTTTTTT | RRRRRRRRRR |
| 1.65 | 0.1094 | hi = 2 (high); hi = 3 (low) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 1.026 to 1.042 | 280.9 | 0 | 0.01389 | TTTTIITTTT | RRRRRRRRRR |
| 2 | 0.1327 | hi = 2.5 (high) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 1.044 to 1.054 | 386.4 | 0 | 17.07 | TTTTTITTTT | RRRRRTRRRR |
| 2.35 | 0.1559 | hi = 3 (high) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 1.054 to 1.065 | 492.5 | 0 | 100.4 | TTTTTTTTTT | RTTRRTRRRR |

Per multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the real cap.

| x lambda_miss | cap | BURST trapped | NOBURST good | CAPPED recovered | CAPPED trapped | PASS per-arm (each >= 7) | same-seed count (all three in one seed) | PASS same-seed (>= 7) | CAPPED backlog (mean) | CAPPED hit (mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 (extra) | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01047 | 0.9313 |
| 1.1 (extra) | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007273 | 0.9313 |
| 1.1 (extra) | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007274 | 0.9313 |
| 1.1 (extra) | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007273 | 0.9313 |
| 1.1 (extra) | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 7.845 | 0.8713 |
| 1.1 (extra) | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 143.5 | 0.1914 |
| 1.15 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.00765 | 0.9311 |
| 1.15 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007641 | 0.9311 |
| 1.15 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007641 | 0.9311 |
| 1.15 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.007658 | 0.9311 |
| 1.15 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 9.852 | 0.8371 |
| 1.15 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 167.7 | 0.1674 |
| 1.25 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01882 | 0.9314 |
| 1.25 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008982 | 0.9315 |
| 1.25 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008757 | 0.9315 |
| 1.25 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.008637 | 0.9315 |
| 1.25 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 27.68 | 0.7915 |
| 1.25 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 2 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 206.1 | 0.1703 |
| 1.35 | 16 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.05013 | 0.9307 |
| 1.35 | 20 * | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.01112 | 0.9307 |
| 1.35 | 24 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009751 | 0.9307 |
| 1.35 | 28 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.009981 | 0.9307 |
| 1.35 | 32 | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 6/10 (0.60) [0.31, 0.83] | 1 | FAIL | 5/10 (0.50) [0.24, 0.76] | FAIL | 42.74 | 0.7564 |
| 1.35 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 6 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 250.9 | 0.1641 |
| 1.5 | 16 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.08075 | 0.931 |
| 1.5 | 20 * | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.02031 | 0.931 |
| 1.5 | 24 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01168 | 0.931 |
| 1.5 | 28 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 10/10 (1.00) [0.72, 1.00] | PASS | 0.01161 | 0.931 |
| 1.5 | 32 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 2/10 (0.20) [0.06, 0.51] | 1 | FAIL | 2/10 (0.20) [0.06, 0.51] | FAIL | 83.09 | 0.5837 |
| 1.5 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 7 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 305.1 | 0.1671 |
| 1.65 | 16 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.08731 | 0.9311 |
| 1.65 | 20 * | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01422 | 0.9312 |
| 1.65 | 24 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 8/10 (0.80) [0.49, 0.94] | PASS | 0.01391 | 0.9312 |
| 1.65 | 28 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 9/10 (0.90) [0.60, 0.98] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 1.55 | 0.9149 |
| 1.65 | 32 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 153.9 | 0.5167 |
| 1.65 | 40 (extra) | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 370.7 | 0.1359 |
| 2 | 16 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 2.864 | 0.9319 |
| 2 | 20 * | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.1254 | 0.9319 |
| 2 | 24 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 9/10 (0.90) [0.60, 0.98] | PASS | 0.04568 | 0.9311 |
| 2 | 28 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 6/10 (0.60) [0.31, 0.83] | 0 | FAIL | 6/10 (0.60) [0.31, 0.83] | FAIL | 31.1 | 0.8733 |
| 2 | 32 | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 308.1 | 0.5091 |
| 2 | 40 (extra) | 9/10 (0.90) [0.60, 0.98] | 9/10 (0.90) [0.60, 0.98] | 0/10 (0.00) [0.00, 0.28] | 9 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 518.1 | 0.1532 |
| 2.35 | 16 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 0 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 97.11 | 0.9329 |
| 2.35 | 20 * | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.4858 | 0.9329 |
| 2.35 | 24 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 10/10 (1.00) [0.72, 1.00] | 0 | PASS | 7/10 (0.70) [0.40, 0.89] | PASS | 0.06635 | 0.9326 |
| 2.35 | 28 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 3/10 (0.30) [0.11, 0.60] | 0 | FAIL | 3/10 (0.30) [0.11, 0.60] | FAIL | 117.3 | 0.8218 |
| 2.35 | 32 | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 3 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 435.5 | 0.534 |
| 2.35 | 40 (extra) | 10/10 (1.00) [0.72, 1.00] | 7/10 (0.70) [0.40, 0.89] | 0/10 (0.00) [0.00, 0.28] | 10 | FAIL | 0/10 (0.00) [0.00, 0.28] | FAIL | 672.9 | 0.1563 |

Per-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):

| x lambda_miss | cap | BURST | NOBURST | CAPPED |
|---|---|---|---|---|
| 1.1 (extra) | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.15 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.25 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.35 | 20 | TTTTTITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.5 | 20 | TTTTTTTTTT | RRRRRRRRRR | RRRRRRRRRR |
| 1.65 | 20 | TTTTIITTTT | RRRRRRRRRR | RRRRRRRRRR |
| 2 | 20 | TTTTTITTTT | RRRRRTRRRR | RRRRRRRRRR |
| 2.35 | 20 | TTTTTTTTTT | RTTRRTRRRR | RRRRRRRRRR |

The simulator's own registration (hi = 2): test points 1.35, 1.65; verdicts at the picked cap 20 are the rows of those multiples above.
