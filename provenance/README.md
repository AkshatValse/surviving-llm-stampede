# provenance/

Records that date the registrations and blind predictions independently of git. Commit and tag times in git are set by the committer; the GitHub and Slurm records below are kept by the servers. Archived 2026-10-30, 18:03 to 18:13 CDT (23:03 to 23:13 UTC). All times below are CDT (UTC-5), the cluster's local time.

| File | What it is |
|---|---|
| `commit-map.tsv` | Old (`jannesari-swapp`) to new (`Nova-Research`) commit hashes. The 2026-10-22 history rewrite removed only AI co-author trailers from commit messages; trees, authors, dates and parents are unchanged (header lines 1-3). |
| `github_activity_2026-10.json` | `gh api 'repos/AkshatValse/Nova-Research/activity?per_page=100' --paginate`. Every ref update GitHub recorded for the repository: 53 entries (pushes and branch creations), from its creation (first push 2026-10-22 17:45:50) to 2026-10-30 17:28:52. Timestamps are UTC, whole seconds. It has no entry for tag pushes. |
| `github_events_2026-10.json` | The same call for `/events`: 44 events, 2026-10-22 17:45:51 to 2026-10-26 11:16:17. The 2026-10-30 pushes had not reached the events feed when it was fetched (twice, 23:03 and 23:09 UTC). GitHub drops events after 30 days. An event's `created_at` is 0 to 1 s after the activity timestamp of the same push. No tag `CreateEvent` appears. |
| `github_tags_2026-10.json` | The same call for `/tags`: the 8 tags on GitHub and the commits they point to. GitHub gives no time for a tag. |
| `github_tag_refs_2026-10.json` | `gh api repos/AkshatValse/Nova-Research/git/matching-refs/tags --paginate`: the annotated tag object behind each tag. All 8 match the local tag objects, so GitHub holds the same tag messages and tagger times as the repository. |
| `sacct_cited_jobs_2026-10-30.txt` | `sacct -j <IDs> -X -P -o JobID,JobName,Account,Partition,Submit,Start,End,State,ExitCode,NodeList,SubmitLine%2000`, run read-only on nova-login-1 at 18:05 (Slurm 26.05.3, time zone America/Chicago). 108 jobs: every job ID cited in `paper/NUMBERS.md` and `paper/sections/*.tex` with ranges expanded, plus vLLM Stage C and E0b 17162959-63 and the registered vLLM paired test 17166121-38. All 108 are billed to account `f2026.coms.6250.02`, partition `instruction`; 89 COMPLETED, 1 FAILED (17060022, the second Stage 0 smoke attempt), and the paired test was still running (3 jobs) or pending (15) at the snapshot. |
| `push_times_2026-10.tsv` | For each registration or prediction commit: committer time, first ref update on GitHub containing it, the matching event, and Slurm submit, start and end of the first job of the batch it concerns. Built by `make_push_times.py` from the files above (run from the repository root). |
| `codex_prediction_verification/` | Byte-identical copy of the first-round independent verifier's evidence, from its workspace `C:\Users\Akshat\Documents\Codex\2026-10-24\cl`: `work/prediction-verification/` (the three seed-0 reruns, `audit.py`, `audit.json`) and `outputs/prediction-verification.txt` (its report). Nothing else from that workspace was copied; the proposed `work/prediction-fixes.patch` is not here. `audit.py` keeps the absolute paths it ran with. The verifier reused the prediction worktree instead of a fresh checkout (`notes/PREDICTIONS_VERIFICATION.md`). |

## First arrival on GitHub and the first job of each batch

"First on GitHub" is the earliest activity entry whose new head contains the commit (`git merge-base --is-ancestor`).

| Event | Commit | Committed | First on GitHub | First job | Submitted | Started |
|---|---|---|---|---|---|---|
| B1-B4 predictions (tag `r6-predictions-frozen`) | `64bc4e3` | 10-24 03:49:32 | 10-24 14:53:07 (`r6/validation` to `877b936`) | E0b 17084750; E2 17093387; native Stage C/E0a 17096856 | 10-23 14:42:06; 10-24 15:13:39; 10-24 23:10:13 | 10-23 14:42:09; 10-24 15:38:33; 10-25 02:28:53 |
| E2 registration | `d279b7b` | 10-24 15:09:12 | 10-24 15:09:54 (`main`) | E2 17093387 | 10-24 15:13:39 | 10-24 15:38:33 |
| B1n-B4n predictions (tag `r8-native-predictions-frozen`) | `e3ea48f` | 10-25 15:06:41 | 10-25 15:08:28 (branch `r8/native-predict` created) | native E0b 17100938; native E2 17102173 | 10-25 14:45:17; 10-25 17:42:29 | 10-25 14:45:22; 10-25 17:42:32 |
| native registration | `b8c19ec` | 10-25 17:31:16 | 10-25 17:31:56 (`main`) | native E2 17102173 | 10-25 17:42:29 | 10-25 17:42:32 |
| vLLM exploratory registration | `a78ce07` | 10-25 18:06:18 | 10-25 18:06:33 (`main`) | vLLM BURST 17102318 | 10-25 18:07:19 | 10-25 22:41:51 |
| round-9 vLLM predictions (tag `r9-vllm-predictions-frozen`) | `cc01dbf` | 10-30 12:31:58 | 10-30 12:32:44 (branch `r9/vllm-predict` created) | vLLM Stage C 17162959; vLLM E0b 17162962 | 10-30 12:10:56 | 10-30 12:11:01; 10-30 13:17:27 |
| vLLM registration | `5a6fbcd` | 10-30 16:23:59 | 10-30 16:26:35 (branch `r9/vllm-register` created at `9b31c09`) | vLLM paired test 17166121 | 10-30 16:24:36 | 10-30 16:25:42 |

Points the table does not show on its own:

- E0b (17084750-55) had finished by 10-23 16:09:04, before the B1-B4 predictions were committed. Only their pull (10-24 15:06, local record) came after the push.
- Native E0b (17100938-39) was running when B1n-B4n were pushed; it ended at 17:26:11 and 17:26:24.
- The round-9 predictions reached GitHub 21 min 48 s after the five vLLM Stage C and E0b jobs were submitted. Jobs 17162959-60 had been running since 12:11:01 and 12:11:04; none of the five ended before 14:36:50.
- The vLLM registration `5a6fbcd` reached GitHub 1 min 59 s after the paired-test jobs were submitted and 53 s after the first one started (17166122 started at 16:26:17). The Slurm submit line names the registration file (`PREREG_FILE=configs/agentload_prereg_2026-10-30_vllm.yaml`) but not its hash. `notes/LOG.md` and `notes/STATE.md` give the submission time as 16:30; Slurm records 16:24:36.
- Tags: GitHub records no push time for tags. The tagger times, set by the committer, are 10-24 14:52:56 (`r6`), 10-25 15:08:26 (`r8`) and 10-30 12:32:41 (`r9`).
- The 103 commits in `commit-map.tsv` (all made before the rewrite) have no server record earlier than the repository's first push. 97 of them, including `288b801`, `4435c51` and `d0235a7`, arrived with `main` at 2026-10-22 17:45:50; `fc870c2` with `wip/r6-separate-batching` at 17:45:52. The other 5 are reachable only from the `archive/*` tags, which have no push record.

## Refresh of 2026-11-01 (after the last registered jobs)

Exported 2026-11-01, 15:55 to 16:05 CST (21:55 to 22:05 UTC). Daylight saving time ended at 02:00 CDT on 2026-11-01, so Slurm local times from 01:00 on that day are CST (UTC-6); the `_utc` copy below is unambiguous. The 2026-10 files above are unchanged.

| File | What it is |
|---|---|
| `github_activity_2026-11-01.json` | The same `gh api .../activity --paginate` call: 122 entries, 2026-10-22 22:45:50Z to 2026-11-01 21:56:08Z. No tag pushes, as before. |
| `github_tag_refs_2026-11-01.json` | `gh api repos/AkshatValse/Nova-Research/git/matching-refs/tags --paginate`: the 17 tags on GitHub with their tag objects. |
| `sacct_cited_jobs_2026-11-01.txt` | `sacct -j <IDs> -X -P -o JobID,JobName,Account,Partition,Submit,Start,End,State,ExitCode,NodeList,SubmitLine%2000` on nova-login-1: 258 jobs, every job ID cited in `paper/NUMBERS.md`, `paper/main.tex` and `paper/sections/*.tex` with ranges expanded. All are billed to `f2026.coms.6250.02`, partition `instruction`; 257 COMPLETED and 1 FAILED (17060022, the second Stage 0 smoke attempt). Rows of five unrelated job IDs, which the range expansion picked up from list notation and which belong to other users, were removed before saving. |
| `sacct_cited_jobs_2026-11-01_utc.txt` | The same jobs with `TZ=UTC` and without the submit line. |
| `push_times_2026-11-01.tsv` | `python provenance/make_push_times.py --activity github_activity_2026-11-01.json --sacct sacct_cited_jobs_2026-11-01.txt --extra`: the 14 rows of `push_times_2026-10.tsv` (identical except that the vLLM paired test now has its end time) plus 21 rows for rounds 11 to 14 (BASIN-1, LPM-INF, rescue, the two theory freezes, the Llama-3.1-8B predictions, registration and theory conditional, BASIN-2, TOOLSLOW, SHED and the 600k H200 registration). The event column reads "not in event log" for the new rows: the events export was not refreshed. |

## Refresh of 2026-11-05 (round 15, CST)

Exported 2026-11-05 at about 06:50 CST (12:50 UTC). Every time of this round is after the end of daylight saving time, so local times are CST (UTC-6). The earlier files above are unchanged; `make_push_times.py` still regenerates `push_times_2026-10.tsv` and `push_times_2026-11-01.tsv` byte for byte.

| File | What it is |
|---|---|
| `github_activity_2026-11-05.json` | The same `gh api 'repos/AkshatValse/Nova-Research/activity?per_page=100' --paginate` call (pages merged): 149 entries, 2026-10-22 22:45:50Z to 2026-11-05 12:43:38Z. No tag pushes, as before. |
| `github_tag_refs_2026-11-05.json` | `gh api repos/AkshatValse/Nova-Research/git/matching-refs/tags --paginate`: 21 tags, including `icml-trap-pred`, `icml-cut-pred`, `r15-reg` and `r15-cut-reg`. |
| `sacct_cited_jobs_2026-11-05.txt` | `sacct -j <IDs> -X -P -o JobID,JobName,Account,Partition,Submit,Start,End,State,ExitCode,NodeList,SubmitLine%2000` on nova-login-1 for the 14 jobs of round 15 (17256674-78, 17256867-75), all billed to `f2026.coms.6250.02`, partition `instruction`. Jobs still running at export time show End `Unknown`; the file is refreshed when they end. |
| `sacct_cited_jobs_2026-11-05_utc.txt` | The same jobs with `TZ=UTC` and without the submit line. |
| `push_times_2026-11-05.tsv` | `python provenance/make_push_times.py --activity github_activity_2026-11-05.json --sacct sacct_cited_jobs_2026-11-05.txt --r15`: one row per (commit, batch) of round 15, times in CST. Every registration and prediction commit was on GitHub before the first job of its batch was submitted (margins 145 s to 3 h 32 min). The one later row is `fdb80c9`, which added the scorer's unregistered gamma/z column 777 s after the TOOLSLOW-W jobs were submitted and before any of their output existed. |

Tag objects carry no push time. Each tag's commit is the "first on GitHub" commit of its branch push: `icml-trap-pred` = `6b47a6c` (branch `claude/theory-icml-2164a9` created 06:24:47Z), `icml-cut-pred` = `2f90267` (pushed 08:25:43Z), `r15-reg` = `e05a262` (in `185dac9`, branch `r15/tonight` created 09:18:36Z), `r15-cut-reg` = `11b0e4e` (in `063024e`, pushed 09:54:49Z).
