# Metastable failures in prefix-cached LLM agent serving

COMS 6250 (Fall 2026) × ISU SwaPP lab. Akshat Valse (lead) with Dr. Ali Jannesari. **Private research repo.**

**Question.** In LLM serving with prefix (KV) caching, multi-turn tool-calling agents reuse their cached context across turns. Does this make the server's good, high-cache-hit state metastable, so that a transient burst tips it into an all-miss regime it cannot leave? And which deployed mechanisms fix that: LPM ordering, queued-prefix protection (PEEK), TTL pins (Continuum), or session caps (CONCUR-style)?

**Status (2026-10-22).**
- Simulation: five verified rounds (`src/prefixmeta/`).
- Real engine, SGLang 0.5.22 + Qwen2.5-7B on one A100: Stage 0 and Stage C are done. The closed-population thrashing curve is verified, and prefix-cache hits collapse to exactly 0 at ≥48 concurrent sessions.
- The open-system kill test (E0a → E0b → pre-registration → E2 paired arms) is in progress.
- Live status and resume steps are in **`notes/STATE.md`**. The full research log is in `notes/LOG.md`.

## Layout
| Path | What |
|---|---|
| `src/prefixmeta/` | Discrete-event simulator of a continuous-batching engine with prefix caching (policies, eviction, allocation modes, fluid predictor) |
| `src/agentload/` | Real-engine load generator: open- and closed-loop multi-turn agent sessions over OpenAI-compatible `/v1/completions`, plus a metrics poller, mock server, canary flush check and client-side session gate |
| `analysis/` | Analysis CLI (`python -m analysis.summarize {windows,miss,closed,stable,burst,burst2}`) and pre-registration tooling (`python -m analysis.prereg {fill,validate,check-job}`) |
| `slurm/` | Nova job scripts: `sglang_job.sbatch` (modes smoke / miss / closed / cap / burst), `setup_nova.sbatch` (env build and model download), the CUDA_HOME shim, and a billing guard in every script |
| `configs/` | Every experiment config. The research question is the first key. Pre-registrations: `*_prereg*.yaml` |
| `experiments/` | Run scripts (simulator rounds, harness utilities) |
| `calibration/` | Simulator cost model fitted to real SGLang server-log timing (round 6) |
| `results/` | Outputs (see Data policy below) |
| `notes/` | `STATE.md`, `LOG.md`, runbooks (`STAGE0_RUNBOOK.md`, `E2_RUNBOOK.md`, `NOVA_PLAN_prefix_meta.md`), theory, related work, referee/verification reports, `lit/` |
| `tests/` | One pytest suite for both packages (`pytest.ini`: `pythonpath = src .`) |
| `.claude/agents/` | Project subagents: `implementer`, `runner`, `scout` |

## Branches
- **`main`**: everything active. On 2026-10-22 `pilot/prefix-meta` and `harness/prefix-meta` were merged in, so a single checkout has the simulator, harness, analysis and notes.
- `pilot/prefix-meta`, `harness/prefix-meta`: historical lines of development, kept for provenance. Recorded results cite their commits. **Develop on `main`.**
- `wip/r6-separate-batching`: an **unreviewed, interrupted** simulator change (SGLang-style separate prefill/decode batching). Its tests have not been run. Do not use it without finishing and reviewing it.
- `pilot/kvrent`, `pilot/vat`, `pilot/delay-eos`: killed or downgraded directions (see `notes/DIRECTIONS.md` and `notes/LOG.md`). Archived.

## Setting up a machine
1. `git clone` this repo.
2. Create a Python 3.12 env: `python -m venv .venv && .venv/bin/pip install -r env/requirements-local.txt`.
3. Run the tests: `.venv/bin/python -m pytest -q`.
   - The full suite takes about 10–20 min and is CPU-only.
   - A few tests skip unless the gitignored simulator outputs exist locally.
4. Nova access: `ssh nova` must work **non-interactively** (`ssh -o BatchMode=yes nova true`, via keys or a ControlMaster session). Nova hostnames only resolve on the ISU network or VPN. Agents never handle passwords or MFA.
5. Claude Code user-level config is **not** in this repo: `~/.claude/CLAUDE.md`, the global agents `referee`, `math-checker`, `experiment-auditor` and `lit-scout`, and the skills `lit-check`, `new-experiment`, `nova-slurm`, `paper-figure` and `results-log`. Copy them to each machine so both behave the same.
6. Update the machine-specific paths in `CLAUDE.md` → Environment (the Python path, for example).

## Data policy
- **Tracked** in git:
  - **`results/nova/`**, real-engine data pulled from Nova. Raw requests, metrics, server logs, canary checks and verification outputs. It is **irreplaceable**: ISU deletes class storage (`/work/classtmp`) at semester end. Pull every new Nova result into a NEW dir under `results/nova/` and commit it.
  - `results/vat_*` timing measurements, which a rerun cannot reproduce bit-for-bit.
- **Ignored:** all other simulator outputs (about 300 MB). Each run's `meta.json` records its commit, and verifiers re-ran them bit-identically from `git archive`. Small summaries (summary/runs CSVs, meta.json, config copies) are force-added (`git add -f`), so the numbers in the notes still trace to tracked files.

## Nova workflow (short; details in `notes/STATE.md`, `notes/STAGE0_RUNBOOK.md`, `notes/E2_RUNBOOK.md`)
- **Account:** `f2026.coms.6250.02` on partition and QoS `instruction`. Every script refuses any other account; the user's default account belongs to a different course.
- **Code on Nova:** `/work/classtmp/avalse/swapp/repo`, a clone synced from a `git bundle`, so no GitHub credentials live on the shared cluster. To sync:
  1. `git bundle create swapp.bundle main`
  2. `scp` it to `/work/classtmp/avalse/swapp/swapp-harness.bundle`
  3. On Nova: `git pull --ff-only ../swapp-harness.bundle main`
- **Envs and caches:** under `/work/classtmp/avalse/swapp/{envs,hf,cache,cuda13-home}`.
- **Approval:** ask before every `sbatch`, and run a short test job first.
