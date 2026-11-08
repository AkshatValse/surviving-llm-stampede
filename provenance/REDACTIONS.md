# Redactions in the public history

This repository is the public copy of the authors' private development repository. Its history was produced from a fresh mirror of that repository by `git filter-repo` with a content callback restricted to the 4 notes files below, and 5 local tool-configuration files (*Removed files*) were dropped from every commit. **No other file was changed in any commit of that history**; the public-release commits on top of it are new commits, described at the end of this file. Every commit of the published branches and tags is kept, with its author date, committer date and parent relations, and so is every tag with its tagger date; the original's other branches, named in `ls-remote-2026-11-06.txt`, are not published; every commit on them is on a published branch or tag, except five commits of 2026-11-03 on the side branch `claude/inspiring-mendel-iofn3w`, which hold nothing cited (README, *Branches and tags*). Every author, committer and tagger is kept too, except that the 111 commits of 2026-10-20 to 2026-10-23 and the five `archive/*` tags, which in the original record the first author under another name and e-mail address, now carry the name and GitHub noreply address that every later commit and tag uses (a mailmap). Every commit and tag message is kept except the 2 commit messages listed under *Commit and tag messages* below, in which a clause was replaced by a redaction marker. Commit hashes differ only because of these changes. The original repository is kept unchanged and private; reviewers can get read access to it on request.

Each removed passage (a line, a list item, or a whole section) was replaced by one line of the form

    [redacted: <category>; see provenance/REDACTIONS.md]

## Categories

| Category | What was removed |
|---|---|
| third-party cluster usernames and storage | the cluster usernames of other people, their Unix group name, and notes about a storage volume that belongs to them |
| unrelated unpublished project | notes about a separate, unpublished research project (its scope, chosen direction, repository and the work of other students); unrelated to this paper |
| cluster-wide accounting data | notes about the cluster's accounting records of other users' jobs; no such records were ever committed, only remarks about them |
| other course | the name of another course's instructor, the local path of that course's project, and remarks about that course's allocation |

## Files

| File | Redacted versions (blobs) | Commits whose tree holds a redacted version | Passages | Lines removed | Passages by category |
|---|---|---|---|---|---|
| `notes/STAGE0_RUNBOOK.md` | 1 | 319 | 1 (0 whole sections) | 1 | third-party cluster usernames and storage: 1 |
| `notes/LOG.md` | 42 | 289 | 42 (42 whole sections) | 462 | unrelated unpublished project: 42; cluster-wide accounting data: 42 |
| `notes/STATE.md` | 33 | 318 | 109 (25 whole sections) | 159 | third-party cluster usernames and storage: 33; unrelated unpublished project: 74; cluster-wide accounting data: 50; other course: 2 |
| `notes/STATE_h200.md` | 5 | 71 | 5 (0 whole sections) | 5 | third-party cluster usernames and storage: 5 |

A passage that touches several categories is counted once under each. Counts are over distinct file versions (the same version shared by several commits is counted once).

## Removed files

Five local tool-configuration files (`CLAUDE.md`, `.claude/agents/implementer.md`, `.claude/agents/runner.md`, `.claude/agents/scout.md`, `.claude/settings.json`) are removed from every commit; their blobs are not in this repository. No other path is removed, and no code, experiment configuration, registration or data file is affected. The registration proofs keep the original root tree objects, whose entry lists still name these files, because the original commit hashes are recomputed from them.

## Commit and tag messages

Messages are kept byte for byte except in the objects below, where each clause that falls under a category above (and only that clause) was replaced by the marker. The rest of the message and the separator before the clause are unchanged, and so are the author and committer dates; the tree and parent hashes differ, as in every rewritten commit, and the author and committer carry the name and e-mail address that the mailmap set (see above). The build checks that each public message is its original with only marker substitutions. The commit map lists both hashes.

| Object | Original | This repository | Category | Clauses replaced |
|---|---|---|---|---|
| commit | `2d4274666dd6` | `d146f7ebc385` | unrelated unpublished project | 1 |
| commit | `ff749c9ebbbd` | `7a906cbab361` | unrelated unpublished project | 1 |

## What was not changed

- No code, configuration, registration (`configs/*prereg*.yaml`), registration input (`prereg/`), result (`results/`), analysis, Slurm script, test, figure or paper blob changed in any commit of the rewritten history (every commit except the public-release commits described below). Checked by comparing the blob sets of the original and the rewritten history over the branches and tags published here (`git rev-list --objects`): 9214 blobs in the original and 9202 in the rewritten history. The 93 original blobs that are not in it are 81 versions of the redacted notes files and 12 versions of the removed files; the 81 blobs that are only in it are the redacted versions of the notes files.
- For every one of the 406 rewritten commits, the original and the public tree differ only at the redacted notes files and the removed files (checked recursively, tree by tree). Every subtree that does not contain one of them, such as `configs/`, `prereg/`, `src/`, `results/`, `analysis/`, `slurm/` and `tests/`, has the same git hash in both histories.
- `registration-proofs/verify.py` re-checks this for every registration and blind-prediction commit from the original raw objects, and binds each one to the GitHub activity log of the original repository (`github-activity-2026-11-06.json`).
- The last commit of `trap/arxiv` (tag `trap-arxiv-v1`) is the public-release commit, an ordinary new commit on top of the history that rewrites nothing. It adds the licenses and `NOTICE`, and adds to this directory this file, `.gitattributes`, `commit-map-public.tsv`, `github-activity-2026-11-06.json`, `ls-remote-2026-11-06.txt` and `registration-proofs/`; the other files here, including the activity-log, push-time and Slurm accounting exports that the paper cites, were committed earlier in the history, and the release commit does not change them. It adds the README's banner and its sections for readers of the paper and on the license, and updates its repository guide and its notes on branches, provenance and machine setup; rewords or removes a few lines of the current notes and Slurm comments that named the first author's other allocation, other directories on the cluster or local tool files, and rewords two notes on commit trailers; in the tests, replaces that allocation's account name with the placeholder `f2026.other.0000.01`, so the three checks that no Slurm directive or runbook names it now always pass; drops the lines naming local tool files from `.gitignore`; and makes the freeze check in `analysis/theory/pred2/common.py` fall back to tag `r13-theory-pred` when the original commit hash it compares against is absent, as it is in this repository. `git show --name-status trap-arxiv-v1` lists every file it adds (A) or edits (M). The published `r10/arxiv` (tag `arxiv-v1`) ends in its own public-release commit of 2026-11-04, which made the same edits to those notes, Slurm comments, tests, `.gitignore` and `common.py`.
- Paths of the agents' local scratch directories, which files under `analysis/`, `calibration/`, `notes/`, `paper/`, `results/` and `tests/` record, and of an independent verifier's workspace, which files under `notes/` and `provenance/` record, are left as they are; the public-release commit only rewords the one line of `notes/STATE.md` that pointed to a file in that workspace. These paths name folders on the first author's machines, which are not part of this repository.
