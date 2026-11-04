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

## For readers of the paper: verifying the pre-registrations

Every registration and blind prediction in the paper was committed and pushed to GitHub before the data it concerns was read. The paper cites the commit hashes of the original development repository. That repository stays private, because four of its notes files hold information about other people and an unrelated project; this repository is the same history with those passages redacted and five local tool-configuration files removed (`provenance/REDACTIONS.md`), so its commit hashes differ. No code, experiment configuration, registration or data file differs in any commit.

| Registration | Original commit (cited in the paper) | Tag | This repository | First GitHub push of the original (Chicago time) | Slurm jobs |
|---|---|---|---|---|---|
| r6 blind predictions B1-B4 | `64bc4e3` | `r6-predictions-frozen` | `4e5e08b` | 2026-10-24 14:53:07 CDT (`r6/validation`) | E0b 17084750-17084755 (results read after the tag); E2 17093387-17093404 |
| E2 registration (configs/agentload_prereg_2026-10-24.yaml) | `d279b7b` | - | `a171d3a` | 2026-10-24 15:09:54 CDT (`main`) | E2 17093387-17093404, submitted 2026-10-24 15:13 CDT |
| exploratory grid registrations (SGLang FCFS r0, LPM r0, LPM r1) | `499c0df` | - | `be32cc8` | 2026-10-24 23:31:32 CDT (`main`) | see notes/STATE.md |
| r8 native-pool predictions B1n-B4n | `e3ea48f` | `r8-native-predictions-frozen` | `0ade9fc` | 2026-10-25 15:08:28 CDT (`r8/native-predict`) | native E0b 17100938-17100939; native kill test 17102173-17102190 |
| native rate rule (notes/STATE.md) | `6cb43e9` | - | `00e0805` | 2026-10-25 15:08:57 CDT (`main`) | - |
| native-pool registration (configs/agentload_prereg_2026-10-25_native.yaml) | `b8c19ec` | - | `1ad5e5e` | 2026-10-25 17:31:56 CDT (`main`) | 17102173-17102190, submitted 2026-10-25 17:42 CDT |
| vLLM exploratory registration (BURST arm) | `a78ce07` | - | `9f3979a` | 2026-10-25 18:06:33 CDT (`main`) | vLLM BURST 17102318 and later |
| r9 vLLM predictions | `cc01dbf` | `r9-vllm-predictions-frozen` | `52fe829` | 2026-10-30 12:32:44 CDT (`r9/vllm-predict`) | vLLM Stage C 17162959-17162961 and E0b 17162962-17162963 (results read after the tag) |
| vLLM registration (configs/agentload_prereg_2026-10-30_vllm.yaml) | `5a6fbcd` | - | `5b1401b` | 2026-10-30 16:26:35 CDT (`r9/vllm-register`) | 17166121-17166138, submitted 2026-10-30 16:30 CDT |
| r11 frozen mechanism, occupancy and detector predictions (vLLM paired test) | `f1338e3` | - | `877581d` | 2026-10-30 18:20:13 CDT (`r11/strengthen`) | 17166121-17166138 |
| r11 basin registrations and S1 bundle-1 predictions | `9b67c26` | `r11-basin-reg` | `0739b63` | 2026-10-30 20:04:30 CDT (`r11/strengthen`) | see notes/STATE.md |
| r11 LPM-INF predictions and exploratory registration | `5064580` | `r11-lpminf-pred` | `f861a36` | 2026-10-30 21:02:46 CDT (`r11/lpminf`) | see notes/STATE.md |
| r11 rescue-cell predictions | `72501f0` | `r11-rescue-pred` | `f997e3e` | 2026-10-30 21:30:40 CDT (`r11/rescue`) | see notes/STATE.md |
| r11 rescue registrations (R1, R4) | `f0bc3ad` | `r11-rescue-reg` | `cedca55` | 2026-10-30 22:39:02 CDT (`r11/rescue`) | see notes/STATE.md |
| r14 BASIN-2 registrations (bursts 40, 50, 60) | `621d88f` | `r14-basin2-reg` | `c9502f3` | 2026-10-31 02:10:48 CDT (`r11/strengthen`) | 17169893-17169901, submitted 2026-10-31 04:21 CDT |
| r13 first-principles theory, frozen predictions | `997d2c4` | `r13-theory-pred` | `6200bea` | 2026-10-31 02:05:30 CDT (`r13/theory`) | H200 n=36/44/52 17169612-17169614; pool sweep 17168864-17168881; rescue R1/R4 17168966-17168974; Llama E0b/E2 (see notes/PREDICTIONS_r13_theory.md) |
| r12 Llama-3.1-8B blind simulator predictions | `a62aea9` | `r12-llama31-predictions-frozen` | `ed52546` | 2026-10-31 02:14:06 CDT (`r12/llama31-predict`) | Llama Stage C 17166814-17166816, E0b 17169565-17169570, E2 17170409-17170426 |
| r14 TOOLSLOW and SHED registrations | `b006291` | `r14-extra-reg` | `eaedd03` | 2026-10-31 02:28:09 CDT (`r14/extra`) | 17169902-17169911, submitted 2026-10-31 04:21 CDT |
| r13 theory, second prediction set (pred2) | `cfa7712` | `r13-theory-pred2` | `f932e86` | 2026-10-31 04:20:20 CDT (`r13/pred2`) | BASIN-2 17169893-17169901; TOOLSLOW 17169902-17169907; SHED 17169908-17169911; H200 600k 17169672-17169687, E2 17171020-17171037 |
| Llama-3.1-8B registration (configs/agentload_prereg_2026-10-30_llama31.yaml) | `1559f8e` | - | `16ff6df` | 2026-10-31 07:49:15 CDT (`r12/llama31`) | 17170409-17170426, submitted 2026-10-31 07:50 CDT |
| Llama-3.1-8B theory conditional | `a36f441` | - | `64bcd2a` | 2026-10-31 07:52:42 CDT (`r12/llama31-theory-cond`) | - |
| Llama-3.1-8B theory conditional, YAML outputs | `d12eef2` | - | `20f765e` | 2026-10-31 07:52:56 CDT (`r12/llama31-theory-cond`) | 17170409-17170426 |
| H200 600k-pool registration (configs/agentload_prereg_2026-10-31_h200_p600k.yaml) | `4d1d431` | - | `56ea644` | 2026-10-31 09:26:41 CDT (`r12/h200-prereg`) | 17171020-17171037, submitted 2026-10-31 09:27 CDT |

How to check:

1. **Tags.** `git tag -n99 -l 'r*'` lists the frozen tags with their messages, and `git for-each-ref --format='%(refname:short) %(taggerdate:iso)' refs/tags` their tagger times. Tag names, messages and tagger times are identical to the original tags; only the commit they point to has a new hash.
2. **Registration content.** `sha256sum configs/agentload_prereg_2026-10-25_native.yaml` (and the other registration files) gives the SHA-256 printed in the paper's appendix and in the tag messages.
3. **Push times.** `provenance/github-activity-2026-11-04.json` is an export of GitHub's activity log for the original repository (`gh api --paginate repos/AkshatValse/Nova-Research/activity`), and `provenance/ls-remote-2026-11-04.txt` a `git ls-remote` snapshot of it taken when this repository was built. Reviewers can get read access to the original repository to see the same log on GitHub. GitHub logs branch pushes, not tag pushes, so each tag is dated by the first push whose new tip contains the tagged commit.
4. **Old to new hashes.** `provenance/commit-map-public.tsv` maps every original commit and tag to this repository's. `python provenance/registration-proofs/verify.py` recomputes each original commit hash from its raw object, follows the parent chain to the commit GitHub recorded, and checks that the original `configs/`, `prereg/`, `src/`, `results/`, `analysis/` and `slurm/` trees, the registered files, the commit metadata and the tags are identical to this repository's.
5. **Slurm job IDs.** The job logs under `results/nova/**/` print, for each Slurm job, the job ID and the commit it ran at (an original hash; look it up in the commit map). Submit, start and end times of the jobs are recorded by Iowa State's Slurm accounting, a third party.
6. Commits from before 2026-10-22 22:45 UTC come from an earlier repository (`provenance/commit-map.tsv`) and have no push record. No registration is among them.

## License

- Code (everything outside `results/` and `paper/`): MIT License, see `LICENSE`.
- Data in `results/`: Creative Commons Attribution 4.0 International (CC BY 4.0), see `LICENSE-DATA`.
- The manuscript source in `paper/`: the license of the paper's arXiv version.
- Third-party material (TraceLab and mini-SWE-agent trace statistics; Qwen2.5, SGLang and vLLM as measured systems): see `NOTICE`.

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
| `provenance/` | `commit-map.tsv` (2026-10-22 rewrite), `commit-map-public.tsv`, the GitHub activity log export, `registration-proofs/` and `REDACTIONS.md` (public release; see Provenance) |

### Branches and tags
- **`r10/arxiv`** (the default branch) is the version of the paper: the manuscript, all code and data, and the public-release commit (licenses, `provenance/`, these README sections) on top. Tag `arxiv-v1` marks the commit the arXiv version describes.
- `main` is the earlier development line; the result branches below were merged into `r10/arxiv`.
- Other published branches, kept because frozen tags or cited commits are on them: `r11/lpminf`, `r11/rescue`, `r11/strengthen`, `r12/h200`, `r12/h200-prereg`, `r12/llama31`, `r12/llama31-predict`, `r12/llama31-theory-cond`, `r13/pool-sweep`, `r13/pred2`, `r13/theory`, `r14/extra`, `r6/validation`, `r8/native-predict`, `r9/vllm-predict`, `r9/vllm-register`, `wip/r6-separate-batching`.
- Frozen registration and prediction tags: `r11-basin-reg`, `r11-lpminf-pred`, `r11-rescue-pred`, `r11-rescue-reg`, `r12-llama31-predictions-frozen`, `r13-theory-pred`, `r13-theory-pred2`, `r14-basin2-reg`, `r14-extra-reg`, `r6-predictions-frozen`, `r8-native-predictions-frozen`, `r9-vllm-predictions-frozen`.
- The `archive/*` tags (`archive/harness-prefix-meta`, `archive/pilot-delay-eos`, `archive/pilot-kvrent`, `archive/pilot-prefix-meta`, `archive/pilot-vat`) are earlier lines of work kept for provenance. They include killed directions (KV rent-or-buy, statistically valid agentic tuning, delayed-gradient edge of stability) that `notes/DIRECTIONS.md` and `notes/LOG.md` explain.
- Work-in-progress and side branches of the original repository that hold nothing cited are not published. Some notes mention them by name.

### Setting up a machine
1. `git clone` the repo.
2. Create a Python 3.12 env: `python -m venv .venv && .venv/bin/pip install -r env/requirements-local.txt`.
3. Run `.venv/bin/python -m pytest -q`. On a fresh clone on an M3 Max this gave 860 passed and 1 skipped in 13 min. The skipped test needs gitignored simulator outputs.
4. For Nova, `ssh nova` must work non-interactively (`ssh -o BatchMode=yes nova true`). Nova only resolves on the ISU network or VPN.
5. Keep machine-specific paths and credentials out of the repository.

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
This history has been rewritten twice. Both rewrites kept every commit, author, committer, date, tag and parent relation.
1. **2026-10-22**, when the work moved from the earlier private repository `jannesari-swapp`: only commit-message trailers changed (co-author trailers were removed). Every file tree is identical. Notes and `meta.json` files from before then cite the original hashes; look them up in `provenance/commit-map.tsv` (columns: `old`, `new`).
2. **Public release**: this repository was built from a mirror of the private development repository `AkshatValse/Nova-Research` by redacting passages of four files in `notes/` and removing five local tool-configuration files from every commit (`provenance/REDACTIONS.md`). Commit and tag messages are unchanged, except 2 commit messages in which a clause about the same redacted topics was replaced by a marker (listed in `provenance/REDACTIONS.md`). Every other file, and so every code, configuration, registration and data blob, keeps its hash. The paper, the notes and the job logs cite the development repository's hashes; `provenance/commit-map-public.tsv` maps them to this repository's, and `provenance/registration-proofs/verify.py` checks the correspondence for every registration.
