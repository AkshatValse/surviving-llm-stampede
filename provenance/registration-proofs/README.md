# Registration proofs

The paper cites commit hashes of the authors' original development repository, which stays private.
This repository's history is the same history with four notes files redacted, five local
tool-configuration files removed and an older name and e-mail address of the first author replaced
by a mailmap (`../REDACTIONS.md`), so its commit hashes differ. This directory binds the two
together.

- `objects/` holds raw git objects of the **original** repository, named by their hash: each
  registration or blind-prediction commit, its root tree, its `notes/` tree, the trees on the path to
  each registered file, its annotated tag (if any), and the commits between it and the tip that GitHub
  recorded.
- `proofs.json` lists, for each registration, the original and the public commit, the GitHub
  activity-log event that first carried it (from `../github-activity-2026-11-06.json`, an export of the original
  repository's activity log), and the registered files with their blob hashes.
- `verify.py` recomputes every hash from the stored bytes and compares the trees, the commit dates and
  messages, the mapped parents, the tags (apart from the commit each points to) and the registered files
  with this repository; because of the mailmap it does not compare author, committer and tagger names and
  e-mail addresses (`mailmap_applied` in `proofs.json`):

      python provenance/registration-proofs/verify.py

GitHub's activity log records branch pushes, not tag pushes: a tag is dated by the first branch push
whose new tip contains the tagged commit. The tag objects themselves are also listed in
`../ls-remote-2026-11-06.txt`, a `git ls-remote` snapshot of the original repository taken when this repository
was built. Tree objects reveal only file names and blob hashes; the hashes of the redacted file
versions cannot be inverted.
