# Nova Research

### Metastable failures in prefix-cached LLM agent serving

**Akshat Valse**, Iowa State University (Statistics, Mathematics, Data Science and Computer Science; Honors). Advised by **Dr. Ali Jannesari**, ISU SwaPP Lab (systems, parallel computing, ML efficiency). This is my COMS 6250 (Advanced HPC) research project, working toward an arXiv preprint and a systems/ML workshop submission.

---

## The problem in one paragraph
LLM agents work in loops: model call, tool call, model call. Each turn re-sends the whole growing conversation. Serving engines such as SGLang and vLLM keep that shared prefix in a GPU **KV cache** so they don't recompute it, which makes follow-up turns much cheaper. The cache is small, though. When too many agent sessions compete for it, sessions lose their cached prefix during tool calls. Every turn then becomes a full recompute, and the extra work keeps the cache too full to recover. This project asks two questions. **Can a transient burst of agents push an otherwise healthy server into a persistent low-throughput, all-miss regime, a metastable failure? And which deployed scheduling and admission mechanisms prevent it?**

## What I built and found so far
- **A discrete-event simulator** of a continuous-batching LLM engine with prefix caching (`src/prefixmeta/`). It covers scheduling policies (FCFS, LPM, aging), eviction rules, KV-allocation modes, and re-implementations of recent mechanisms (PEEK, Continuum TTL pins, CONCUR-style adaptive caps). Five rounds of **pre-registered** predictions were each independently re-computed and re-run bit-identically.
- **A queueing-theoretic model.** The closed-population "thrashing curve" μ(n) drives an open-system fluid model. A small checked proposition shows that FCFS-type ordering cannot escape the all-miss regime under any eviction rule. A cap identity says when session caps restore stability.
- **A real-engine harness** (`src/agentload/`, `analysis/`, `slurm/`) that drives SGLang 0.5.22 serving Qwen2.5-7B on NVIDIA A100 80GB GPUs. It runs on ISU's **Nova HPC cluster** through SLURM. It includes an open- and closed-loop agent load generator, cache-flush verification, a billing-safe job layer, a pre-registration tool that refuses to run unregistered experiments, and paired-arm burst experiments with common random numbers.
- **Result so far (real engine).** Throughput rises to a peak at about 20–24 concurrent agent sessions. Then the prefix-cache hit rate collapses from 0.93 to **exactly 0** by 48 sessions, and throughput falls about 3×. Three independent measurement sources confirm the collapse, and its shape matches the simulator. The open-system burst test that decides whether the regime is truly metastable is in progress.

**Methods and tools:** Python (NumPy, SciPy, pandas, asyncio/aiohttp), discrete-event simulation, queueing and fluid models, rare-event and escape-time analysis, SLURM, CUDA toolchains, SGLang, Prometheus metrics, and pytest (about 860 tests). Every reported number traces to a results directory, a commit and a cluster job ID.

---

## Repository guide
| Path | What |
|---|---|
| `src/prefixmeta/` | The simulator |
| `src/agentload/` | Real-engine load generator, mock server, canary flush check, client-side session gate |
| `analysis/` | `python -m analysis.summarize {windows,miss,closed,stable,burst,burst2}` and `python -m analysis.prereg {fill,validate,check-job}` |
| `slurm/` | Nova job scripts (`sglang_job.sbatch` modes smoke / miss / closed / cap / burst; `setup_nova.sbatch`), the CUDA_HOME shim, and a billing guard in every script |
| `configs/` | Experiment configs, each starting with its research question; pre-registrations are `*_prereg*.yaml` |
| `experiments/` | Run scripts |
| `calibration/` | Simulator cost model fitted to real SGLang server-log timing |
| `results/` | Outputs (see the data policy below) |
| `notes/` | `STATE.md` (live status and resume steps), `LOG.md` (research log), runbooks, theory, related work, review and verification reports |
| `tests/` | One pytest suite for both packages |
| `provenance/commit-map.tsv` | Map from old to new commit hashes (see Provenance) |

### Branches and tags
- **`main`** holds everything active. Develop here.
- `wip/r6-separate-batching` is an unreviewed, interrupted simulator change (SGLang-style separate prefill/decode batching). Its tests have not been run.
- The `archive/*` tags are earlier lines of work kept for provenance. They include killed directions (KV rent-or-buy, statistically valid agentic tuning, delayed-gradient edge of stability) that `notes/DIRECTIONS.md` and `notes/LOG.md` explain.

### Setting up a machine
1. `git clone` the repo.
2. Create a Python 3.12 env: `python -m venv .venv && .venv/bin/pip install -r env/requirements-local.txt`.
3. Run `.venv/bin/python -m pytest -q`. On a fresh clone on an M3 Max this gave 860 passed and 1 skipped in 13 min. The skipped test needs gitignored simulator outputs.
4. For Nova, `ssh nova` must work non-interactively (`ssh -o BatchMode=yes nova true`). Nova only resolves on the ISU network or VPN.
5. Machine-specific paths go in `CLAUDE.md` → Environment.

### Data policy
- **Tracked:**
  - `results/nova/`: real-engine data pulled from Nova, including raw requests, metrics, server logs, canary checks and verification. It is irreplaceable, because ISU deletes class storage at semester end. Pull each new Nova result into a new dir there and commit it.
  - `results/vat_*`: timing measurements.
- **Ignored:** all other simulator outputs. They regenerate bit-identically from the commit recorded in each `meta.json`. Their small summaries are force-added.

### Nova workflow
- **Account:** `f2026.coms.6250.02` on partition/QoS `instruction`. The scripts refuse any other account.
- **Code:** `/work/classtmp/avalse/swapp/repo` is synced from a `git bundle`, so no GitHub credentials live on the shared cluster.
- **Envs, model and caches:** `/work/classtmp/avalse/swapp/`.
- **Runbooks:** `notes/STAGE0_RUNBOOK.md`, `notes/E2_RUNBOOK.md`.
- **Approval:** ask before every `sbatch`, and run a short test job first.

### Provenance
This repo's history was rewritten on 2026-10-22, when it moved from the earlier private repo `jannesari-swapp`. Only commit-message trailers changed. Every file tree is identical, so every commit hash changed. Older notes and `meta.json` files cite the original hashes. Look them up in `provenance/commit-map.tsv` (columns: `old`, `new`).
