# Redactions in the public history

This repository is the public copy of the authors' private development repository. Its history was produced from a fresh mirror of that repository by `git filter-repo` with a content callback restricted to the 4 notes files below, and 5 local tool-configuration files (*Removed files*) were dropped from every commit. **No other file was changed in any commit.** Every commit, author, committer, author date, committer date, tag, tagger date and parent relation is kept (author and committer e-mail addresses were normalised with a mailmap), and so is every commit and tag message except the 2 commit messages listed under *Commit and tag messages* below, in which a clause was replaced by a redaction marker. Commit hashes differ only because of these changes. The original repository is kept unchanged and private; reviewers can get read access to it on request.

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
| `notes/STAGE0_RUNBOOK.md` | 1 | 273 | 1 (0 whole sections) | 1 | third-party cluster usernames and storage: 1 |
| `notes/LOG.md` | 36 | 243 | 36 (36 whole sections) | 396 | unrelated unpublished project: 36; cluster-wide accounting data: 36 |
| `notes/STATE.md` | 33 | 272 | 109 (25 whole sections) | 159 | third-party cluster usernames and storage: 33; unrelated unpublished project: 74; cluster-wide accounting data: 50; other course: 2 |
| `notes/STATE_h200.md` | 5 | 25 | 5 (0 whole sections) | 5 | third-party cluster usernames and storage: 5 |

A passage that touches several categories is counted once under each. Counts are over distinct file versions (the same version shared by several commits is counted once).

## Removed files

Five local tool-configuration files (`CLAUDE.md`, `.claude/agents/implementer.md`, `.claude/agents/runner.md`, `.claude/agents/scout.md`, `.claude/settings.json`) are removed from every commit; their blobs are not in this repository. No other path is removed, and no code, experiment configuration, registration or data file is affected. The registration proofs keep the original root tree objects, whose entry lists still name these files, because the original commit hashes are recomputed from them.

## Commit and tag messages

Messages are kept byte for byte except in the objects below, where each clause that falls under a category above (and only that clause) was replaced by the marker. The rest of the message, the separator before the clause, and every header are unchanged; the build checks that each public message is its original with only marker substitutions. The commit map lists both hashes.

| Object | Original | This repository | Category | Clauses replaced |
|---|---|---|---|---|
| commit | `2d4274666dd6` | `d146f7ebc385` | unrelated unpublished project | 1 |
| commit | `ff749c9ebbbd` | `7a906cbab361` | unrelated unpublished project | 1 |

## What was not changed

- No code, configuration, registration (`configs/*prereg*.yaml`), registration input (`prereg/`), result (`results/`), analysis, Slurm script, test, figure or paper blob changed, in any commit. Checked by comparing the blob sets of the original and the public history (`git rev-list --objects`): 8007 blobs in the original and 7995 here. The 87 original blobs that are not here are 75 versions of the redacted notes files and 12 versions of the removed files; the 75 blobs that are only here are the redacted versions of the notes files.
- For every one of the 360 commits, the original and the public tree differ only at the redacted notes files and the removed files (checked recursively, tree by tree). Every subtree that does not contain one of them, such as `configs/`, `prereg/`, `src/`, `results/`, `analysis/`, `slurm/` and `tests/`, has the same git hash in both histories.
- `registration-proofs/verify.py` re-checks this for every registration and blind-prediction commit from the original raw objects, and binds each one to the GitHub activity log of the original repository (`github-activity-2026-11-04.json`).
- The edits in the last commit of `r10/arxiv` (licenses, this provenance directory, README sections, and small wording fixes in the current notes, Slurm comments and tests) are ordinary new changes on top of the history; they rewrite nothing.
