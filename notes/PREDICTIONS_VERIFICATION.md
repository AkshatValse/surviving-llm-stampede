# Round 6 prediction verification

This is an append-only verification record for frozen prediction commit 64bc4e3cab4887ecc219e160ff2a84106bd74277. It does not amend PREDICTIONS.md, simulation outputs, thresholds, or scientific conclusions.

Procedural deviations: the current prediction worktree is on r6/validation, not the older r6/separate-batching name in the frozen workflow. Verification reused that clean checkout instead of creating a fresh worktree; all rerun outputs and caches were isolated externally. The scientific reproduction checks pass, but strict B3-within-B2 containment fails and the existing full suite has 32 failures. This commit is an honest verification record, not authorization to merge, push, or certify that all checks passed.

External evidence root: the verifier's workspace C:\Users\Akshat\Documents\Codex\2026-10-24\cl on the PC. Archive note (2026-10-30): its work/prediction-verification/ folder and outputs/prediction-verification.txt are copied byte for byte, with the same layout, to provenance/codex_prediction_verification/ in this repository, so references below beginning work/prediction-verification/ or outputs/ resolve there. Nothing else from that workspace was copied; the proposed work/prediction-fixes.patch (section 5) stays in the external workspace only and remains unapplied. No E0b/E2 real data or remote cluster commands were used in this verification.

---
Round 6 independent prediction verification — 2026-10-24

Checkpoint: 64bc4e3cab4887ecc219e160ff2a84106bd74277, branch r6/validation, C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\predict.
Scope: original workflow's Verify stage, read-only review plus six short local simulation reruns. Original checkout remains clean and unchanged. No E0b/E2 real data or cluster commands were used. No new long test suite was run.

VERDICT
- Reproduction of required subset: PASS for deterministic scientific fields.
- Report/manifest consistency and independent classification arithmetic: PASS.
- Textual leak check: no affirmative forbidden-data evidence found; this is not proof of historical blindness.
- B2 edge above B1 floor and below B4 peak: PASS.
- B3 PASS region strictly inside B2 all-stable window: FAIL.
- Full-suite status: 1017 passed, 32 failed, 2 skipped in the existing log. The suite did NOT fully pass; documented platform failures remain.
- No numerical implementation defect requiring a code fix was established. The failed containment criterion is a scientific/definition mismatch to disclose, not grounds to retune frozen predictions. A proposed documentation-only patch is saved separately and has NOT been applied.

1. Independent reruns
Used the project's pinned Python 3.12.10 interpreter and checkpoint 64bc4e3. Changes since simulation commit 630ab9e affect report code, tests and driver line endings, not simulator/config code. Python bytecode writes were disabled; Numba cache and all rerun outputs were redirected under Codex work. All six simulations finished in 7.5 seconds total.

Ran the commands documented in PREDICTIONS.md, with workers=1, new tags, absolute --out-root, and these subset overrides:
- B1 curve: engine.batching=mixed; probe.curve.seeds=[0]; POP32 unchanged.
- B2 open: engine.batching=mixed; probe.open.seeds=[0]; probe.open.lambdas=[0.10,0.22].
- B3 burst: engine.batching=mixed; probe.burst.lambda=0.12; probe.burst.seeds=[0]; all three arms unchanged.

Compared rows by seed/variant/policy (and window bounds). Exact serialized values matched in every compared scientific column:
- B1: 1 run row x 61 columns; 27 window rows x 32 columns. Sessions/s = 0.08, matching the committed seed-0 prediction.
- B2: 2 run rows x 58 columns; 60 window rows x 32 columns. Lambda 0.10 stable, final backlog 0; lambda 0.22 unstable, final backlog 275.
- B3: 3 run rows x 77 columns; 261 window rows x 32 columns. NOBURST and CAPPED recovered, BURST trapped.
There were zero mismatches. Excluded run_id because subset enumeration changes it, and wall_s / wall_s_per_10k_sim_s because runtime measurements are not deterministic. This is scientific-field reproduction, not a byte-identical whole-file claim.

Evidence is under provenance/codex_prediction_verification/work/prediction-verification/reruns/ (copied from work/prediction-verification/reruns/ in the Codex workspace). The three result timestamps are 20261024-035525, 20261024-035527, and 20261024-035530. The audit script and machine-readable evidence are provenance/codex_prediction_verification/work/prediction-verification/audit.py and audit.json; audit.py keeps the absolute paths it ran with.

2. Arithmetic, completeness, and existing tests
All 48 manifest entries are unique; every referenced meta.json is status=done, git.dirty=false, simulation commit 630ab9edc7f40b33718771b4efb6a52da66b8eb6. Generated table rows match section 4 of PREDICTIONS.md exactly (heading levels differ intentionally).

An independent standard-library calculation, without importing the project's analysis functions, recomputed all 78 registered B2 stability classifications and all 126 registered B3 classifications from their window CSVs. All labels matched. B3 statistics agreed within relative/absolute tolerance 1e-12; maximum absolute numerical difference was 3.64e-12 in a token-rate value around 11000, from summation order. E[T] independently evaluates to 14.761055049953429.

The existing full_suite_pytest.log progress characters independently count 1017 successes, 32 failures, 2 skips and zero error markers; there are exactly 32 FAILED summary lines. They are the same recorded Windows/platform failure families as the validation checkpoint. This review reused that log and did not claim those failures were resolved or waive the project's merge criterion.

3. Required sanity checks
Using the comparable B4 300k pool and registered seed-0 peak:
- Mixed: B1 floor 0.072187 < B2 edge 0.14 < B4 peak 0.226111 sessions/s: PASS.
- Separate: B1 floor 0.071359 < B2 edge 0.15 < B4 peak 0.225556: PASS.
- Both modes predict B3 PASS at 0.16, beyond their B2 all-stable edges. Mixed also PASSes at 0.14, exactly on its boundary. Therefore the workflow's requested STRICT containment criterion FAILS. Strictly interior tested PASS points are 0.09–0.13 mixed and 0.09–0.14 separate.

B2 requires all three seeds stable after a 3000-second run; B3 requires each condition in at least two of three seeds, evaluated over the last 2500 seconds of an 8700-second run. The weaker seed requirement and different horizons can explain the discrepancy, but do not make the strict containment check pass. Preserve the frozen numerical predictions and document this limitation.

4. Leak review and provenance limits
A separate reviewer scanned all 407 changed files in main...64bc4e3 (merge-base bf20ed4, current main 8b0a120) and classified all 427 matching added lines. No E0a/E0b/E2 real-result files were opened. Hit inventory, grouped by repeated exact source locations:
- 200 protocol-label hits: configs/r6_predict.yaml lines 1,16,66,78; the same four lines in all 48 simulation config.yaml copies and the prediction report config.yaml.
- 49 research-question hits: line 3 in all 48 simulation config_effective.yaml copies and report config_effective.yaml.
- 147 inherited simulator preregistration hits: lines 36,41,304 in all 48 simulation config_effective.yaml files; lines 36,41,303 in validation config_effective.yaml. Corresponding settings already exist at bf20ed4:configs/prefix_meta.yaml (current lines 29,31,199).
- Seven protocol/denial hits: notes/PREDICTIONS.md lines 4,46,250,558,560; calibration/round6_server_log_fit/VALIDATION.md lines 26,243.
- Four report-label hits: src/prefixmeta/r6_predict.py lines 158,378; results/r6_predict/report_stdout.txt line 104; prediction report tables.md line 104.
- Six mock-fixture hits: both prediction and validation full_suite_pytest.log files, lines 590,803,1106. These explicitly refer to fake E0a calibration data, with adjacent fixture assertions.
- Thirteen permitted Stage C input hits: configs/r6_validate_stagec.yaml lines 63–65; validation config.yaml lines 63–65, config_effective.yaml lines 665,667,669, meta.json lines 121–123; tests/test_r6_validate.py line 126.
- One SHA false positive: tests/data/mixed_golden.json line 197 contains e0b within a hash.
There are zero scoped diff hits for /work/classtmp, agentload_e0_miss, agentload_e0_cap, or agentload_e2_burst. The only ssh hit is PREDICTIONS.md:560's denial of cluster access. Broader _e2 matches are end-to-end test filenames (PREDICTIONS:582, VALIDATION:396,398, both pytest logs:34,57,1426,1427).

The reviewing agent had previously read main's STATE.md during the validation review; that exposes earlier E0a context. Accordingly this is an independent verifier, not a blind predictor. The original prediction-stage blindness statement is a source assertion. A text scan cannot establish that nobody previously read withheld data. E0b's gate is not certified solely by this review.

5. Minimal proposed clarification
work/prediction-fixes.patch changes only notes/PREDICTIONS.md and passes git apply --check against the unchanged checkpoint. It:
- Makes the B2 headline match the frozen operational rule: no early stop, backlog <50, and OLS backlog rise <=10 requests over 1500 seconds. The existing headline says "no upward trend," although 42 of 78 runs are classified stable with a positive (tolerated) trend. The threshold was fixed before runs and remains unchanged; it is a documented relaxation of a literal zero-rise reading.
- Adds the explicit failed containment sanity check and explains the different definitions without changing outcomes.
- Corrects the inherited mixed plateau phrase from "within 9%" to "within 9.2%" (actual 9.1266%).

The original frozen checkpoint is intact. Prefer keeping this independent report alongside it; apply any prose amendment explicitly as an amendment rather than replacing the registered predictions silently. The initial review produced external artifacts and a proposed patch. This append-only documentation commit records that completed review in the repository; the proposed patch remains unapplied.


