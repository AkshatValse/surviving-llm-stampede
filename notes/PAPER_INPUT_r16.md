# PAPER_INPUT r16 (MIRROR), part 0: design, frozen predictions and rules (results pending)

For the paper session (nova-reframe), from the lead, 2026-11-05 about 14:35 CST. Branch `r16/mirror` (worktree
`Nova-Research-wt/mirror`). Results will follow as part 1; until then every outcome below is `\pending`.

## One-paragraph summary for the paper (adapt freely; numbers are frozen)

Theorem 2 factors the trapped completion rate as D = lambda_miss H(z) Gamma(z):
- Gamma(z) >= 1 comes from context growth;
- H(z) comes from the turn-count law, and is about 1 for the geometric turn count of our workload, which is why every
  trapped run at a load above the all-miss capacity completes sessions above it (the youth premium). CUT-B's runs, cut
  to below it, completed 0.92-0.97 lambda_ref, as model F predicts. (Corrected 16:30 after the audit; the earlier text
  said "every trapped run so far".)

The theorem therefore predicts that the premium reverses when agents run to a fixed step budget, since a nearly
deterministic T gives H(z) well below 1. MIRROR tests this blind:
- **Design.** The same engine, pool, burst and run length as the E2 protocol, with one change: the workload's turn count is
  T = min(Geometric(1/1000), 20), so about 98% of the sessions run exactly 20 turns. Its model all-miss capacity is
  1.046 lambda_ref, against 1.004 for the standard workload.
- **Model F's predictions.** At 1.65 lambda_ref, model F predicts three things:
  - completions nearly stop for about 40 minutes after the burst (0.05-0.09 lambda_ref over [2400, 3600) s), because the
    burst cohort must pass through 20 FIFO cycles, each longer than the last, before any of it can finish;
  - the cohort then completes in a wave, with its median completion at 5135-5195 s by seed;
  - completions then stay near half the all-miss capacity (0.49-0.60 lambda_ref over [6600, 8700) s), while the backlog
    grows 1.65-1.95 times as fast as the plan's excess load lambda_plan - lambda_miss over [6000, 8700) s (1.4 times
    asymptotically). (Corrected 16:30 after the audit; the earlier text gave only the asymptotic 1.4, which is not what
    rule M4 scores. See the errata in notes/PREDICTIONS_r16_mirror.md.)
- **The alternatives.** Every throughput-curve reading predicts steady completions near 1.05 lambda_ref and no wave: the
  quasi-static one, Lu et al.'s dN/dt = lambda - X(N)/K, and our Eq. (fluid). The standard workload's measured traps sit
  at 1.05-1.48 lambda_ref in the first window and 1.01-1.35 in the second.

## Design (what changed, exactly)

- Config: `configs/agentload_e2_mirror_k20.yaml` is `configs/agentload_e2_burst.yaml` with `workload.mean_turns` 15 -> 1000
  and `workload.max_turns` 60 -> 20 (plus its description text). Nothing else differs (scripted diff of the parsed YAML).
- Cell label `sglang-fcfs-r1-mirror-k20`: SGLang 0.5.22 FCFS, waiting-prefix refresh on, 300k pool, Qwen2.5-7B-Instruct,
  A100 80GB PCIe.
- Rates are multiples of the standard workload's registered lambda_ref = 0.071534 /s.
- Arms (one per job, seeds 0-2, 8700-s runs, burst of 200 sessions in [1200, 1260) s):
  - BURST at 1.65 x (decisive cell);
  - BURST at 1.35 x (secondary cell);
  - NOBURST at 1.65 x (controls);
  - one E0a of the workload (MODE=miss, closed POP 32, cache off), which measures its all-miss capacity; no rule uses it.
- Why K = 20:
  - the model all-miss capacity of the step-capped workload matches the standard one (1.046 vs 1.004 lambda_ref);
  - its good-state basin at 1.65 x is wide (n1 = 14.3, n_u = 41.8), so the no-burst arm should stay good;
  - chosen by computation only (K = 15, 20 and 25 and mean_turns 30, 40 and 60 were compared in the model). No engine run
    of the workload existed.

## Theory numbers (asymptotic; `results/theory/r16/mirror_predictions.json`)

| rate | rho | D / lambda_miss | H | Gamma | standard workload D / lambda_miss | alpha / (lambda - lambda_miss) |
|---|---|---|---|---|---|---|
| 1.65 x | 1.577 | 0.771 | 0.699 | 1.103 | 1.223 (H 0.989, Gamma 1.236) | 1.398 (standard: 0.65) |
| 1.35 x | 1.291 | 0.870 | 0.825 | 1.055 | 1.126 | 1.447 |

## Frozen per-seed predictions (model F, plan-driven FIFO; rates in lambda_ref)

1.65 x (decisive):

| seed | blackout [2400,3600) | wave time (median t_end of burst sessions) | burst IQR | late [6600,8700) | backlog slope [6000,8700) F / QS |
|---|---|---|---|---|---|
| 0 | 0.047 | 5195 s | 4803-5392 | 0.546 | +0.0789 / +0.0478 |
| 1 | 0.070 | 5135 s | 4876-5299 | 0.599 | +0.0857 / +0.0441 |
| 2 | 0.093 | 5157 s | 4788-5376 | 0.486 | +0.0930 / +0.0518 |

1.35 x (secondary): the wave times are 4883 / 4802 / 4870 s. Each is earlier than at 1.65 x, by 287-334 s per seed (corrected after the audit from "270-330 s"); this is
registered secondary W6.

## Registered rules (`analysis/r16_mirror.py`; registration commit bc81ee7, tag `r16-mirror-reg`, pushed 14:07:35 CST per GitHub's activity log)

Per BURST run, the rules are:
- M1: blackout completions <= 0.30.
- M2: |wave time - F| <= 0.15 (F - 1200 s).
- M3: late completions <= 0.85.
- M4: the backlog slope is closer to model F's than to the quasi-static slope.

Seed calls:
- RENEWAL iff the run is STUCK and M1-M4 hold;
- CURVE iff both completion windows are >= 0.85 (the throughput-curve signature);
- NOT-TRAPPED iff the run is not STUCK;
- otherwise MIXED.

The cell PASSES with 2 of 3 RENEWAL, FAILS with 2 of 3 CURVE, and is NO-TRAP with 2 of 3 NOT-TRAPPED. Secondary rules:
- W5: the wave against the calibrated value, +-5% of the elapsed time;
- W6: the rate ordering;
- W7: composition within 5%;
- W8: the late level within 0.25;
- W9: NOBURST controls GOOD;
- W10: the measured all-miss capacity.

**Tolerance provenance (committed data only).** On the six committed standard-workload BURST runs, model F's plan-driven
FIFO times burst-session completions about 8% late: measured/model elapsed time is 0.9125-0.9327 per run, mean 0.9223. M2's
+-15% covers that bias. W5 applies the factor 0.9223 with +-5%.

**Not blind, to state:**
- The lead chose the workload after computing the model's predictions for it and for a few alternatives.
- The tolerance factor comes from the standard workload's committed runs.
- No simulator prediction was made for MIRROR.
- The test came after Lu et al. (5 Nov).

## Figure

`figures/r16/fig_mirror.py` (in `r16/mirror`) draws:
- panel (a): completions per 300-s bin after the burst;
- panel (b): the backlog.

Each panel shows the standard workload's three committed 1.65 x traps (grey), model F's frozen step-capped predictions
(blue dashed) and, once pulled, the step-capped runs (orange). A preview without MIRROR data is
`results/theory/r16/fig_mirror.pdf` once rendered there. The final version comes with part 1.

## Suggested paper text placement

- One subsection in the evidence section, "A reversed youth premium (MIRROR)", with the figure.
- One ledger row: claim "the premium's sign is set by the turn-count law (Theorem 2's H)"; test MIRROR; blind;
  result \pending.
- In the intro's contributions, one clause, once the result is in.
