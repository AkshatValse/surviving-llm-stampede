# Paper input: the H200 cells (SGLang): 300k window compression, no registered test there; 600k pool registered, paired test running

Written 2026-10-31 for the lead. Every number below comes from committed files on branch `r12/h200`. The pull is `results/nova/h200_wave1_pulled_20261031-023416/` (abbreviated **HP**), committed in `d108056`. Full narrative: `notes/LOG.md`, entry 2026-10-31 "H200 cell".

## Verdict

**At the 300k pool: no kill test on the H200.** The registered rule (`836063a`: window (1, hi), points at ⅓ and ⅔ rounded to 0.05, `boundary_margin_rel` 0.1) cannot be applied:
- hi = min(μ_max/λ_ref, largest all-stable E0b multiple) = min(1.99, 1.3) = 1.3;
- the rule's points 1.10 and 1.20 × both fall outside the band (1.1, 1.17);
- `analysis.prereg fill` returns INCOMPLETE.

So there is no registration and no E2, and no decisive claim for this cell. No exploratory pair was run either: `derive-exploratory` needs a FILLED parent, the only one at this pool is the A100 registration, and its hardware check refuses the H200 calibration. Making that work would need a code change.

**At a 600k pool on the same H200, the window reopens to (1, 2.5) and the cell registers** (1.5 and 2.0 ×, cap 48). Its paired test, jobs 17171020–37, is running; see the section "600k-pool H200 cell" below. The verdict will be added after the Sunday pull.

**What the cell delivers is a measurement: window compression on a faster GPU.** The pool (300k tokens) and the workload (Exp(5 s) tool time) are the same as on the A100. Against the A100:
- the H200 raises λ_miss 2.71 ×;
- the peak of μ(n) rises only 1.66 ×;
- the from-empty edge rises 1.76 ×;
- so the window in units of λ_miss narrows from (1, 2.0) to (1, 1.3).

There is **no blind simulator prediction** for this cell. The round-13 first-principles theory (tag `r13-theory-pred`, pushed before the combine) predicted the curve and the edge. Its predictions are compared below.

## Sources

| key | path (under HP unless stated) | what |
|---|---|---|
| CAL | `results/agentload_analysis_miss/20261030-204701/calibration.json` (= `prereg/inputs/2026-10-31-h200/calibration.json`) | E0a combined, 3 runs (jobs 17166810–12) |
| POP | `results/agentload_analysis_miss_popcheck/20261030-204702/calibration.json` | POP-64 check (job 17166813) |
| MU | `results/agentload_analysis_closed/20261031-023040/mu_curve.json` (= `prereg/inputs/2026-10-31-h200/mu_curve.json`) | Stage C nine-run curve (jobs 17166818–22, 17166828, 830, 832, 834), `--primary-label sglang-fcfs-r1-h200` |
| BR | `results/agentload_analysis_stable/20261031-023042/` (`lambda_cap_bracket.json`, `stable_runs.csv`) | E0b bracket, six runs (jobs 17168377–82) |
| RC | `prereg/inputs/2026-10-31-h200/fill_rulecheck_INCOMPLETE.yaml` (repo root) | the fill with the rule's points, status INCOMPLETE |
| HJ | `results/nova_job_logs/<job>-*/` (banner, server.log), `logs/pm-h200-*.out`, `swapp/h200_jobs.env`, `swapp/h200_wave1_submit.log` | job logs, IDs and exact sbatch lines |
| A100 | `prereg/inputs/2026-10-23/` (repo root) | the A100 300k cell (`sglang-fcfs-r1`) for comparison |
| TH | `notes/PREDICTIONS_r13_theory.md`, `results/theory/merged/h200_300k.json` at tag `r13-theory-pred` (`997d2c4`, pushed 02:05:30 CDT 2026-10-31) | frozen theory predictions |

Setup facts:
- **Software:** SGLang 0.5.22, Qwen2.5-7B-Instruct `a09a3545`.
- **Hardware:** nova25-gpu-3, "NVIDIA H200 NVL, 143771 MiB", driver 580.178.04.
- **Server log (HJ, all 20 jobs):** `max_total_num_tokens=300000` and `attention_backend: 'fa3'` (the Hopper default; the A100 cells ran FlashInfer).
- **Provenance:** all jobs ran from clone `repo_h200` at `5a6fbcd` and finished COMPLETED 0:0; 16.3 GPU-h in total.

## Numbers (with sources)

| number(s) | what | source |
|---|---|---|
| 0.19388 ± 0.0062 sessions/s (turns-based); 0.1933 sessions-based | λ_miss = λ_ref | CAL |
| 29,866 ± 23 tok/s | all-miss uncached prefill rate | CAL |
| 2.71 ×, 2.66 × | H200 / A100 λ_ref and tokens (A100: 0.07153, 11,243) | CAL, A100 |
| 1.046 (tokens), 1.100 (turns-based) | POP-64 / POP-32 | POP vs CAL |
| 0.219, 0.279, 0.327, 0.369, **0.386**, 0.329, 0.274, 0.218, 0.225 | μ sessions/s at n = 16, 20, 24, 28, 32, 40, 48, 96, 300 | MU `mu_sessions` |
| 0.211, 0.262, 0.311, 0.350, **0.367**, 0.312, 0.259, 0.211, 0.226 | μ turns-based, same n | MU `mu_turns_based` |
| 0.929, 0.925, 0.901, 0.839, 0.744, 0.456, 0.215, 0.000, 0.000 | hit fraction (turns), same n | MU `hit_frac_turns` |
| n = 32; μ_max 0.3861; runner-up n = 28 within 4.3 % | peak (`n_cap_ambiguous`) | MU |
| 1.99 (turns-based 1.89) | μ_max / λ_ref (A100: 3.26) | MU, CAL |
| ≈ 38.8 (A100 ≈ 32.1) | 0.5-hit crossing, linear interpolation | MU |
| 1.13 × λ_miss (A100: 0.68 ×) | minimum μ over the grid (sessions-based) | MU |
| stable 1.1, 1.2, 1.3 × (final queue 0); unstable 1.4 × (50.4, rise +48.6), 1.55 × (177.7, +115.6), 1.75 × (272.6, +170.7) (seed 0); reseeds 1.3 × seeds 1, 2 stable; 1.4 × seeds 1, 2 stable (final queue 0) | E0b outcomes (1.3 × stable 3/3, 1.4 × 2/3) | BR `stable_runs.csv`; reseeds `agentload_analysis_stable_supp10/20261031-050254` |
| largest all-stable 1.3 × (0.252 sessions/s), first unstable 1.4 × (0.271), monotone | E0b bracket (A100: 2.0 ×, 2.5 ×) | BR |
| (1, 1.3) × λ_ref = (0.194, 0.252) sessions/s; 0.3 λ_miss wide (A100: (0.0715, 0.143), 1.0 λ_miss wide) | metastable window, `hi_source: lambda_cap_e0b` | RC |
| 1.10, 1.20 vs band (1.1, 1.17) | rule's points vs `boundary_margin_rel` band | RC `fill_problems` |
| n_cap 28; capped-drain limit 1.73 × | what the cap rule would have given (not binding) | RC |
| 1.66 ×, 1.76 × | H200 / A100 μ_max and edge rate (0.3861/0.2333; 0.252/0.143) | MU, BR, A100 |
| 0.65 (A100 0.61) | edge / (μ_max/λ_ref) | MU, BR, A100 |

## Against the frozen theory (TH; turns-based estimator, read after the combine)

| quantity | predicted | measured | tolerance (THEORY_r13_scoring.md) |
|---|---|---|---|
| μ_max | 0.372 (F1) | 0.367 | ±10 %: hit (+1.3 %) |
| window μ_max/λ_ref | 1.92 (band 1.65–1.96) | 1.89 | ±10 %: hit |
| peak n | 32.5 | 32 (flat top: n = 32 only) | hit |
| n_half (0.5-hit) | 37.3 (annealed 36.5) | ≈ 38.8 | ±3: hit |
| hit at peak | 0.69 | 0.744 | (not scored) |
| E0b edge | 1.39 × (F2) | bracket [1.3, 1.4) | inside the bracket |
| μ(40), μ(48) | 0.257 / 0.278; 0.197 / 0.201 (fluid / annealed) | 0.312; 0.259 | softer cliff than predicted |
| hit(48) | 0.000 / 0.013 | 0.215 | refutation needs ≥ 0.5: not refuted |

F2 P(unstable) at the six E0b multiples is 0.04, 0.12, 0.28, 0.52, 0.84 and 0.98, which gives a log-likelihood of −1.36 for the observed S S S U U U. None of the three refutation rules fires. These are this session's readings of the frozen JSON; the theory session does the official scoring.

## Supplementary 12-point curve (blind test of the theory's cliff; not used for registration)

- **Jobs:** 17169612–14 (n = 36, 44, 52), submitted 02:33 CDT, after the theory's push at 02:05:30.
- **Combine:** `results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.json`, under HP2 = `results/nova/h200_stageC_extra_1716961x_pulled_20261031-040933/` (archive sha256 `c069b0b8…`).

| n | 36 | 44 | 52 |
|---|---|---|---|
| μ sessions/s | 0.374 | 0.299 | 0.269 |
| μ turns-based | 0.354 | 0.280 | 0.250 |
| hit (turns) | 0.613 | 0.318 | 0.156 |
| r13 μ turns-based (fluid / annealed) | 0.359 / 0.348 | 0.197 / 0.221 | 0.197 / 0.198 |
| r13 hit (fluid / annealed) | 0.56 / 0.53 | 0.00 / 0.08 | 0.00 / 0.00 |

- The peak stays at n = 32; n = 36 is within 3.2 %.
- The 0.5-hit crossing is ≈ 38.9.
- The theory matches to n = 36. Past the midpoint the real tail is gradual: hit 0.32 and 0.16 at n = 44 and 52, where the theory is all-miss, and μ 1.27–1.29 × the annealed prediction.
- No refutation rule is affected.
- **Suggested sentence:** "On the H200 the collapse is a slide rather than a cliff: hit falls from 0.74 at n = 32 to 0.16 at n = 52, whereas the fluid model, which matches the rising branch and the peak blind, goes all-miss by n ≈ 42."

## 600k-pool H200 cell (`sglang-fcfs-r1-h200-p600k`): registered; E2 running (verdict pending)

Sources:
- pull HP6 = `results/nova/h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/` (archive sha256 `10682cc6…`), with the curve `results/agentload_analysis_closed/20261031-092435/mu_curve.json` and the bracket `results/agentload_analysis_stable/20261031-092436/`;
- registration `configs/agentload_prereg_2026-10-31_h200_p600k.yaml` (repo root; commit `4d1d431`, pushed 09:26:41 CDT; PREREG_SHA256 `6be6e232280a8b5d2454e08356e8a169a67fb908eb4afdf7a02f444aa504578e`);
- inputs `prereg/inputs/2026-10-31-h200-p600k/`.

Jobs: Stage C 17169672–80, E0b 17169682–87 (all COMPLETED 0:0; all started after the pred2 push at 04:20:20); E2 **17171020–17171037** (submitted 09:27:44 CDT).

| number(s) | what | source |
|---|---|---|
| 0.427, 0.522, **0.592**, 0.581, 0.477, 0.403, 0.298, 0.269, 0.232 | μ sessions/s at n = 32, 40, 48, 56, 64, 72, 80, 96, 300 | HP6 curve `mu_sessions` |
| 0.412, 0.505, **0.577**, 0.569, 0.466, 0.379, 0.281, 0.254, 0.231 | μ turns-based | `mu_turns_based` |
| 0.930, 0.927, 0.897, 0.804, 0.654, 0.478, 0.227, 0.140, 0.000 | hit fraction (turns) | `hit_frac_turns` |
| 3.05 (turns-based 2.98) | μ_max/λ_ref (λ_ref 0.19388, the H200 E0a) | curve, calibration |
| ≈ 71.0 | 0.5-hit crossing | curve |
| stable 1.25–2.5 × (final queue 0); unstable 3.0 × (620.2, +433) | E0b | HP6 bracket `stable_runs.csv` |
| (1, 2.5) × λ_ref = (0.194, 0.485) sessions/s; points 1.5, 2.0 × (0.291, 0.388); n_cap 48 | registration | prereg file |

Against pred2 (`results/theory/pred2/h200_600k.json` at tag `r13-theory-pred2`, read after the combine):

| quantity | predicted | measured | result |
|---|---|---|---|
| μ_max (F1) | 0.620 | 0.577 | +7.3 % |
| window | 3.20 | 2.98 | hit |
| peak n | ≈ 53 | flat top 48–56 | hit |
| n_half | 66.6 / 64.8 | ≈ 71.0 | miss (+4.4 / +6.2) |
| E0b bracket | [2.5, 3.0) | [2.5, 3.0) | equal |
| registration | 1.5 / 2.0 ×, cap 48 | 1.5 / 2.0 ×, cap 48 | identical |

The tail past the midpoint is softer than predicted, as at 300k: hit 0.48 / 0.23 / 0.14 at n = 72 / 80 / 96, against 0.15 / 0.02 / 0.00.

The 2×2 (μ_max/λ_ref; edge):

| | A100 | H200 |
|---|---|---|
| 300k | 3.26; 2.0 × | 1.99; 1.3 × |
| 600k | from the pool-sweep cell | 3.05; 2.5 × |

**Suggested sentence:** "Doubling the pool on the H200 reopens the window: the peak rises 1.53 × and moves from n = 32 to 48, the from-empty edge moves from 1.3 to 2.5 λ_miss, and the cell registers at 1.5 and 2.0 λ_miss, exactly the registration our frozen model predicted."

The verdict follows when the 18 E2 jobs have finished (pull Sunday 08:00–11:30).

## Caveats

- **The edge is stochastic.** The 1.4 × seed-0 run ended at queue 50.4, just above the threshold of 50 (its trend +48.6 is clearly rising). The reseeds 17169668–71 (pull `results/nova/h200_e0b_reseeds_1716966x_pulled_20261031-050308/`; ten-run bracket `agentload_analysis_stable_supp10/20261031-050254`) give 1.3 × stable in 3/3 seeds and 1.4 × stable in 2/3. So hi stays 1.3 under the all-stable rule, and the registration conclusion is unchanged. Quote the edge as "stable at 1.3 × in 3/3 seeds, at 1.4 × in 2/3". The frozen r13 F2 gives P(stable) 0.72 and 0.48 there. Even if 1.4 × had been all-stable, the rule would give 1.15 and 1.25 against a band of (1.1, 1.26), and that registers only because 1.25 < 1.26.
- **One run per n** on the Stage C curve.
- **Saturation.** POP 32 may not quite saturate the H200 in turns (POP-64 turns ratio 1.10; tokens 1.046 is within the runbook's 5 %). If λ_ref is low, the window in λ_miss units is narrower still.
- **Backend.** fa3 on the H200 vs FlashInfer on the A100, the deployed default per GPU. The comparison is GPU-plus-default-backend, not GPU alone.
- **Blindness.** The per-job n = 16–32 μ values (Stage C 17166818–22) were seen by the cell operator and Akshat at about 22:28 CDT, and not by the lead or the theory agents. n ≥ 40 and the E0b edge are fully blind.
- **The checker's a-priori estimate** (μ_max/λ_ref 1.2–1.7, hi 1.1–1.5; written in COORD 2026-10-30 ~18:20 before any H200 job, not committed) is not a blind prediction by the project's standard. Its premise was a cliff at n ≈ 24–28 on either GPU, and the cliff moved out to about 39.
- **Extra Stage C.** Jobs 17169612–14 (n = 36, 44, 52) were submitted at the lead's request after the combine. They are not part of the registration numbers; see the supplementary section above.

## Suggested text (one paragraph, e.g. for the generality / limits section)

> **A faster GPU at the same pool narrows the window.** We repeated the 300k-token SGLang cell on one H200 NVL (same model, revision, engine version, pool and workload; SGLang's Hopper-default fa3 attention). The all-miss rate rises 2.71 × (λ_miss = 0.194 sessions/s), but the peak of the closed-loop curve rises only 1.66 × (μ_max = 0.386 at n = 32), and the from-empty edge 1.76 × (stable at 1.3 λ_miss in 3/3 seeds; at 1.4 λ_miss in 2/3; unstable at 1.55 and above). The metastable window therefore shrinks from (1, 2.0) λ_miss on the A100 to (1, 1.3) λ_miss on the H200. That is too narrow for our pre-registered rule to place two test points at least 10 % from its edges, so we ran no kill test on this GPU. The compression follows from the window being the gap between a pool-limited peak and a compute-limited all-miss rate: faster compute raises the floor more than the peak. Our first-principles model, frozen before the H200 curve was read, predicted μ_max = 0.372 (turns-based; measured 0.367), a peak at n ≈ 32.5 and an edge at 1.39 λ_miss.

## Suggested table row (cells table: GPU, pool, λ_miss, μ_max/λ_miss, peak n, edge, window, test)

| H200 NVL | 300k | 0.194 | 1.99 | 32 | 1.3 × (3/3 stable; 1.4 × 2/3) | (1, 1.3) | not registrable (rule's points 1.10/1.20 outside (1.1, 1.17)); no E2 |
