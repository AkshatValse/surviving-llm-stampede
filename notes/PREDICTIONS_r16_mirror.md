# r16 MIRROR: frozen blind predictions (model F, the renewal law of the trap)

Written 2026-11-05, about 16:00 CST, by the lead session, before any MIRROR job was submitted. Branch `r16/mirror`, registration
tag `r16-mirror-reg`. Code: `analysis/theory/icml/mirror_predict.py` (predictions), `analysis/r16_mirror.py` (registration,
rules, scoring). Frozen numbers: `results/theory/r16/mirror_predictions.json`; frozen client plans:
`results/theory/r16/mirror_plans/`. Registration: `configs/agentload_prereg_2026-11-05_mirror_k20.yaml`.

## What is tested, and why it is decisive

Theorem 2 says a trapped engine completes sessions at D = lambda_miss H(z) Gamma(z). Gamma >= 1 comes from the cost growth; H
comes from the turn-count law and equals 1 for a geometric T. For the standard workload (T = min(Geometric(1/15), 60)) the
product is above 1: the youth premium, which every one of our 57 stuck runs shows. For a nearly deterministic T, H(z) is far
below 1, and model F predicts the opposite: a trapped engine that completes sessions BELOW its all-miss capacity.

MIRROR changes only the turn-count law, to agents that run to a step budget:
- the workload is `configs/agentload_e2_burst.yaml` with `mean_turns 15 -> 1000` and `max_turns 60 -> 20`;
- so T = min(Geometric(1/1000), 20): 97.7-98.2% of the sessions in the plans run exactly 20 turns;
- the engine, the pool, the burst (200 sessions in [1200, 1260) s), the run length (8700 s) and the rates are unchanged;
- the rates are multiples of the standard workload's registered lambda_ref.

The model puts this workload's all-miss capacity at 1.046 lambda_ref, against 1.004 for the standard one.

The exact plan-driven FIFO of model F (`plan_fifo`, unchanged) gives the transient as well as the asymptote:
- **Blackout.** The burst cohort needs 20 FIFO cycles, each longer than the last, before any of it can complete. Completions
  nearly stop for about 40 minutes after the burst.
- **Wave.** The cohort then completes together.
- **Lull.** Completions stay well below capacity afterwards, while the backlog grows 1.4x faster than the excess load.

Every throughput-curve reading predicts steady completions at about the all-miss capacity whenever the engine is trapped:
- the quasi-static one (completions at lambda_miss);
- Lu et al.'s fluid dN/dt = lambda - X(N)/K;
- our own Eq. (fluid).

None of them gives a blackout or a wave. The standard workload's committed traps sit at 1.05-1.48 lambda_ref in the blackout
window and 1.01-1.35 in the late window, which these rules would score as CURVE.

## Headline (frozen)

lambda_ref = 0.071534 /s. lambda_miss (model, this workload) = 0.074831 /s = 1.046 lambda_ref. n_b = 43.2.

**1.65 x (DECISIVE).**
- rho = 1.577.
- Asymptotic D / lambda_miss = 0.771 = H 0.699 x Gamma 1.103. The standard workload is at 1.223 = 0.989 x 1.236.
- alpha / (lambda - lambda_miss) = 1.398.
- Good state: n1 = 14.3, n_u = 41.8.

| seed | sessions | T=20 | blackout [2400,3600) | wave time F (cal.) s | burst IQR s | late [6600,8700) | slope [6000,8700) F / QS | P_served [5700,8700) |
|---|---|---|---|---|---|---|---|---|
| 0 | 1294 | 0.981 | 0.047 | 5195 (4884) | 4803-5392 | 0.546 | +0.0789 / +0.0478 | 6920 |
| 1 | 1246 | 0.982 | 0.070 | 5135 (4830) | 4876-5299 | 0.599 | +0.0857 / +0.0441 | 7074 |
| 2 | 1289 | 0.978 | 0.093 | 5157 (4850) | 4788-5376 | 0.486 | +0.0930 / +0.0518 | 6976 |

**1.35 x (SECONDARY).**
- rho = 1.291.
- Asymptotic D / lambda_miss = 0.870 = H 0.825 x Gamma 1.055. The standard workload is at 1.126.
- alpha / (lambda - lambda_miss) = 1.447.
- Good state: n1 = 11.6, n_u = 42.5.

| seed | sessions | T=20 | blackout [2400,3600) | wave time F (cal.) s | burst IQR s | late [6600,8700) | slope [6000,8700) F / QS | P_served [5700,8700) |
|---|---|---|---|---|---|---|---|---|
| 0 | 1101 | 0.981 | 0.000 | 4883 (4597) | 4497-5022 | 0.599 | +0.0565 / +0.0274 | 7451 |
| 1 | 1057 | 0.981 | 0.058 | 4802 (4522) | 4500-4973 | 0.686 | +0.0534 / +0.0192 | 7732 |
| 2 | 1097 | 0.977 | 0.070 | 4870 (4585) | 4546-5068 | 0.726 | +0.0603 / +0.0278 | 7548 |

How to read the tables:
- Rates are completions per second over lambda_ref.
- The wave time is the median completion time of the 200 burst sessions.
- QS is the quasi-static slope lambda_plan - lambda_miss_model.
- At the quasi-static reading both completion windows are 1.046.

**NOBURST controls (1.65 x):** predicted GOOD 3/3 by the paper's basin model (n1 = 14.3 is far below n_u = 41.8). No
simulator prediction was made for MIRROR.

**E0a of this workload:** predicted lambda_miss = 1.046 lambda_ref (model). This is a measurement only; no rule uses it.

## Registered rules (verbatim in `analysis/r16_mirror.py`)

Per counted BURST run (F = the frozen per-seed value of that run's cell):

| rule | condition | model F | throughput-curve readings |
|---|---|---|---|
| M1 blackout | completions over [2400, 3600) <= 0.30 lambda_ref | 0.00-0.09 | 1.05 |
| M2 wave | \|median t_end of burst sessions - F\| <= 0.15 (F - 1200 s); undefined below 100 completed | as tabled | no wave |
| M3 below capacity | completions over [6600, 8700) <= 0.85 lambda_ref | 0.49-0.73 | 1.05 |
| M4 growth | \|S - S_F\| < \|S - S_QS\|, S = OLS slope of the 10-s backlog over [6000, 8700) | +0.053 to +0.093 | +0.019 to +0.052 |

Seed calls:
- RENEWAL iff the run is STUCK (frozen B1 endpoints, `analysis.basin.classify_run`) and M1-M4 all hold.
- CURVE iff both completion rates are >= 0.85 lambda_ref (the throughput-curve signature).
- NOT-TRAPPED iff the run is not STUCK.
- Otherwise MIXED.

Cell verdicts:
- PASS iff RENEWAL in >= 2 of the 3 seeds.
- FAIL iff CURVE in >= 2 of 3.
- NO-TRAP iff NOT-TRAPPED in >= 2 of 3: the trap was not reached, so model F is untested and the basin prediction is wrong.
- Otherwise MIXED.

1.65 x is the decisive cell; 1.35 x is a secondary cell under the same rules.

A run counts only if all of these hold:
- it is the registered cell's: label `sglang-fcfs-r1-mirror-k20`, a registered arm, rate and seed;
- it completed: status finished, run end >= 8700 s, not aborted;
- it is bound to the registration (`analysis.prereg.run_blockers` is empty);
- its plan.csv equals the frozen plan.

**Secondary (registered, reported, not in the verdict):**
- W5: the calibrated wave, |wave - F_cal| <= 0.05 (F_cal - 1200), with F_cal = 1200 + 0.9223 (F - 1200);
- W6: per seed, the wave comes earlier at 1.35 x than at 1.65 x (model F: by 270-330 s);
- W7: the mean prompt of turns completed over [5700, 8700) is within 5% of F;
- W8: |late - F| <= 0.25 lambda_ref;
- W9: every NOBURST control is GOOD;
- W10: the E0a lambda_miss of this workload, and whether the late completions are below it.

## Where the tolerances come from (committed data only; no MIRROR result exists)

**M2 tolerance.** Model F's plan-driven FIFO was compared with the six committed standard-workload BURST runs at 1.35 x and
1.65 x (jobs 17093388-402, `results/nova/e2_170933xx_pulled_20261025-144558`).
- The statistic: per run, the median over burst sessions that completed and that model F predicts to finish after 3000 s,
  of (t_end measured - 1200) / (t_end model - 1200).
- Result: 0.9125-0.9327, mean 0.9223, sd 0.0073. Model F's timing runs about 8% slow on this engine; the engine finishes
  sooner than the cost model says.
- So the primary M2 uses model F as it stands, with +-15% of the elapsed time. That covers the known bias with about 7
  points to spare.
- W5 applies the declared factor 0.9223 with +-5%.

**Thresholds M1, M3 and CURVE.** These sit between model F and the quasi-static values. They were fixed from those values
and the standard workload's measured traps, never from MIRROR data.

## Not blind, stated

- The lead chose the workload (mean_turns 1000, max_turns 20) after computing model F's and the paper's fluid-model
  predictions for it and for a few alternatives:
  - K = 15, 20 and 25;
  - mean_turns 30, 40 and 60.
- K = 20 was chosen because:
  - its model all-miss capacity matches the standard workload's (1.046 against 1.004 lambda_ref);
  - its predicted good-state basin at 1.65 x is wide (n_u 41.8).
- No engine run of this workload existed or was read.
- The tolerance calibration reads committed runs of the standard workload only.

## Reproduce

    PYTHONPATH="src;." python -m analysis.theory.icml.mirror_predict      # predictions and plans (deterministic)
    PYTHONPATH="src;." python -m analysis.r16_mirror fill                  # the registration (refuses to overwrite)
    PYTHONPATH="src;." python -m analysis.r16_mirror selfcheck             # frozen plans == config plans; rules on synthetic records
    PYTHONPATH="src;." python -m analysis.r16_mirror sbatch-lines          # the submit lines (never submits)
    PYTHONPATH="src;." python -m analysis.r16_mirror classify --run-dirs RUN ... [--e0a-calib calibration.json]

## Freeze record

The registration commit is tagged `r16-mirror-reg` and pushed to GitHub (private `origin`) before any MIRROR job is submitted.
The push time comes from GitHub's activity log (provenance), as for r15.
