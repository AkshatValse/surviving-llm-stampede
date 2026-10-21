# STATE

_Last updated: 2026-10-21 ~07:20 (end of overnight session)_

## Phase
Phase 0 is complete. **Direction approved 2026-10-21: metastable failures in prefix-cached agent serving.** Phase 1/2 prep (Nova Stage 0) is in progress. It rests on simulation evidence across 5 verified rounds. The real-engine test is designed but not run.

## Branches (local only; nothing pushed)
- `main`: notes, CLAUDE.md, lit checks, theory, LOG, MORNING.
- `pilot/prefix-meta` (worktree `.claude/worktrees/prefix-meta`): simulator `src/prefixmeta/`, rounds 1–5. HEAD is around 44dd21f+. Pre-registrations are in `configs/prefix_meta_*prereg*.yaml`.
- `harness/prefix-meta` (worktree `.claude/worktrees/pm-harness`): real-engine load generator `src/agentload/`, analysis, DRAFT SLURM scripts, `notes/NOVA_PLAN_prefix_meta.md`. HEAD is around 2f22e08.
- Killed or downgraded pilots: `pilot/kvrent`, `pilot/vat`, `pilot/delay-eos`.
- Result dirs were copied into `results/` on main (gitignored). Summaries are committed on each branch.

## Running
None. No Nova jobs (`squeue` was empty at 22:30). No background agents.

## Open decisions (Akshat)
See `notes/MORNING.md` → "Decisions needed". In short:
1. ~~Approve the direction~~ (approved 2026-10-21).
2. Approve about 27 GPU-h for Nova cheap stages (S0, C, E0a, E0b).
3. KV pool cap (300k vs native).
4. Output-feedback mode.
5. Codex-folder allow-rule in settings.local.json.

## Next steps (in order)
1. Akshat runs the "Needs Akshat" commands (account, quotas, modules, HF reachability). Fill in CLAUDE.md "Nova storage".
2. Build the Nova envs per `notes/NOVA_ENV_PLAN.md`, adding aiohttp and huggingface_hub, in an salloc session. Needs approval.
3. Stage 0 smoke on SGLang v0.5.22 (1×A100, ~0.8 GPU-h). Resolve the unverified flags, metrics and token-id feedback.
4. Stage C: real closed μ(n). Then E0a/E0b. Then fill and commit the pre-registration (`configs/agentload_prereg_template.yaml`). Then the paired-arm kill test.
5. Optional simulation round 6: block-wise partial-prefix eviction plus a d-sweep.
6. Re-verify every citation in `notes/RELATED_WORK_prefix_meta.md` before any paper text.
