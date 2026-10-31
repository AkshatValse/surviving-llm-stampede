# Round 11: frozen mechanism predictions for the registered vLLM paired test

Written 2026-10-30 ~18:25 CDT, while the 18 registered vLLM jobs (17166121–17166138, registration `configs/agentload_prereg_2026-10-30_vllm.yaml`, commit `5a6fbcd`) were running or pending and none had ended. No output of these jobs (run dirs, per-job analyses, `logs/pm-e2v-*.out`, which print an in-job burst2 summary) has been opened; only `squeue`/`sacct` states were read. **Blind rule:** a run is blind iff its sacct End is later than the push time of the commit that adds this note (recorded below after the push).

**What is predicted** (`configs/r11_mechanism_predict.yaml`; code `analysis/r11/{loopvars,detector,occupancy}_frozen.py`, committed unchanged with this note):
- (a) In NOBURST and CAPPED: median follow-up gap / R < 0.05 and follow-up hit > 0.95; in BURST: gap / R > 2 and hit < 0.05, where R = M / churn (M = 300,000 tokens; churn = new KV tokens written per second). Descriptive: gap / R and hit are not independent.
- (b) In BURST over [5700, 8700) s: mean `vllm:kv_cache_usage_perc` ≥ 0.90 and uncached-prompt-token rate within [0.85, 1.15] × the all-miss reference 10,348.6 tok/s. This is the outcome-independent check that the trapped pool is full and rewritten at the all-miss rate (refill-then-evict), not empty (failure to fill).
- (c) The online hit detector alarms within 300 s after the burst in every BURST run and never in [600, 8700) s in NOBURST/CAPPED.
- (d) The engine-TTFT rule (100 s mean TTFT > 30 s) has the same timing pattern.

**Decision rule:** consistent with refill-then-evict if every blind BURST run meets (b) and (c) and every blind good-arm run except at most one meets (a) and (c). A BURST run failing (b) drops the description for vLLM. Intermediate states are not tested.

**Scope of blindness:** the bands were chosen on committed SGLang E2 runs and the six exploratory vLLM BURST runs (17102318–23). The registered BURST arms reuse those runs' arrival plans (common random numbers), so the BURST checks are a replication on new executions; only NOBURST and CAPPED are out of sample. Sanity runs of the frozen code on the six exploratory vLLM BURST runs (before freezing): hit 0.000, gap/R 6.5–8.6, detector delay 100–120 s, KV usage 0.919–0.931, uncached ratio 0.937–0.962.

**Afterwards:** first the registered verdict (`summarize burst2 --prereg configs/agentload_prereg_2026-10-30_vllm.yaml`), then these frozen scripts unchanged, with a blind/non-blind flag per run from sacct End vs the push time.

## Time record
- Freeze commit `f1338e3` (committer time 2026-10-30 18:20:11 CDT), pushed to GitHub as the creation of branch `r11/strengthen`: GitHub activity log timestamp **2026-10-30T23:20:13Z = 18:20:13 CDT** (`gh api repos/AkshatValse/Nova-Research/activity`).
- At 18:20:13 CDT `sacct` showed 17166121 and 17166122 RUNNING since 16:25–16:26, 17166123 RUNNING since 17:17, and 17166124–17166138 PENDING: no run of the test had ended, so all 18 are blind under the rule if none ended before the push (to be confirmed from sacct End at evaluation).
