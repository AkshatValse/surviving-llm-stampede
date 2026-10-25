# vLLM runbook for Nova (second engine, grid cell D)

- Written 2026-10-25 on branch `r7/vllm-prep` (worktree `Nova-Research-wt/vllm-prep`). **Nothing here has been submitted or run on Nova.** No Nova host was contacted; every fact below comes from PyPI, the vLLM GitHub release and the raw source at tag `v0.32.0`.
- Scope: prepare the vLLM `vllm-fcfs` cell. The cell is **exploratory**: it inherits the SGLang registration's window and lambda multiples (1.35 and 1.65 x lambda_ref), uses vLLM's own E0a reference rates, runs the BURST arm only, and never enters the registered cell's decisive verdict (`notes/E2_RUNBOOK.md` Stage 5).
- Each stage needs the owner's go-ahead before its `sbatch` (project rule). The lead submits; this file only gives the lines.

## 1. Release choice: vllm 0.32.0

| Item | Value | Source |
|---|---|---|
| Version | **vllm 0.32.0**, the plan's choice and the newest release on PyPI (previous: 0.31.0, 2026-10-05) | https://pypi.org/project/vllm/0.32.0/ , `https://pypi.org/pypi/vllm/json` |
| PyPI upload | 2026-10-18T10:03:29Z (aarch64 wheel), 10:03:52Z (x86_64 wheel) | PyPI JSON `urls[].upload_time_iso_8601` |
| GitHub release | `v0.32.0`, published 2026-10-18T06:50:48Z, tag -> commit `5df63a7203cdb9328d824a27b682e77c7b9928be` | `gh api repos/vllm-project/vllm/releases/tags/v0.32.0`, `.../git/ref/tags/v0.32.0` |
| Wheel | `vllm-0.32.0-cp38-abi3-manylinux_2_28_x86_64.whl`, 311 MiB, sha256 `5e2ecdc5b0baf729...` | PyPI JSON |
| Python | `>=3.11,<3.15` (3.10 dropped in 0.32.0); the env uses 3.12 | PyPI `requires_python`; release notes "Breaking Changes" |
| torch pin | `torch==2.13.0` (exact), `torchvision==0.28.0`, `torchaudio==2.11.0`, `flashinfer-python==0.7.0.post1`, `numba==0.65.0`, `transformers>=5.16.1,<5.20.0` | PyPI `requires_dist` of 0.32.0 |
| CUDA | Release notes: "PyPI (CUDA 13.0): `pip install vllm`". torch 2.13.0's default Linux wheel depends on `cuda-toolkit[...]==13.0.3`, `nvidia-cudnn-cu13==9.20.0.48`, `nvidia-nccl-cu13==2.29.7`, `triton==3.7.1` | release notes; `https://pypi.org/pypi/torch/2.13.0/json` |
| Binary check | The compiled modules in the x86_64 wheel link CUDA 13: `DT_NEEDED` of `_deepselect_C`, `_flashkda_C`, `_flashmla_C`, `_flashmla_extension_C`, `_qutlass_C` = `libcudart.so.13`; `cumem_allocator`, `fs_io_C`, `spinloop` = `libnvrtc.so.13`; none needs `libcudart.so.12`. (Read by HTTP range requests; nothing saved. The three largest modules, `_C_stable_libtorch`, `_moe_C_stable_libtorch` and the two flash-attn modules, have their dynamic section beyond the 24 MB prefix I read and were not inspected.) | the wheel URL on files.pythonhosted.org |
| Driver fit | Nova's driver 580.178.04 is an R580 driver (CUDA 13.0 branch). The SGLang env already runs torch 2.14.1+cu130 on it (job 17060165), so both engines sit on the same CUDA 13.0 runtime | `notes/NOVA_PLAN_prefix_meta.md` Stage 0 result |
| Resolution | `uv pip compile` for `x86_64-manylinux_2_28`, Python 3.12 resolves cleanly: 198 packages, `torch==2.13.0`, `torchaudio==2.11.0`, `triton==3.7.1`, `transformers==5.19.0`, `huggingface-hub==2.3.0`, `numpy==2.3.5`. Resolver only, nothing installed | run locally 2026-10-25 |

Why this version and not another: it is the release the plan named, it exists, it is the latest, and its PyPI wheel is the CUDA 13.0 build that the Nova driver and the SGLang env already use. An older release would not add information (the lit notes, `notes/lit/engine-sources-prefix-cache.md`, were read at this tag). One conflict is recorded: `docs/getting_started/installation/gpu.cuda.inc.md` at the same tag still says "compiled with CUDA 12.9" and recommends `uv pip install vllm --torch-backend=auto`; the release notes and the binary check say the PyPI wheel is CUDA 13.0, so the docs line is stale. `setup_vllm_env.sbatch` asserts `torch.version.cuda` starts with `13.` and fails loudly otherwise.

## 2. Files in this branch

| File | What |
|---|---|
| `slurm/setup_vllm_env.sbatch` | NEW. Builds `/work/classtmp/avalse/swapp/envs/vllm`. `PHASE=install` (default) is CPU-only, `PHASE=check` needs one GPU. Details in section 4, steps 1 and 2 |
| `slurm/engine_vllm.sh` | Rewritten against the v0.32.0 source: flags, env vars, version guard, `flush_cache` override, rotary-cache sizing, block size |
| `slurm/vllm_job.sbatch` | Header only (parameters, sbatch examples); directives, billing guard and body unchanged |
| `tests/test_vllm_scripts.py`, `tests/helpers_vllm_server.py` | NEW. 61 tests: syntax, directives, billing guard, setup failure paths, the launch command line and environment, flag/env/version check, flush semantics, harness metric names, three end-to-end `job_main` runs through the real launcher against a vLLM-like fake server, and checks that this runbook agrees with the scripts and the registration |
| `notes/VLLM_RUNBOOK.md` | This file |

`slurm/common.sh`, `src/agentload/`, `analysis/prereg.py`, `tests/test_slurm_scripts.py` and everything under `results/nova/`, `prereg/inputs/` and `configs/agentload_prereg_2026-10-24.yaml` are untouched. The existing `tests/test_slurm_scripts.py` expects `UNVERIFIED` in `engine_vllm.sh`, `<group-dir>` placeholders, `--num-gpu-blocks-override 18750` and the default labels; all still hold (the header keeps an honest list of what stays unverified until the first Nova job).

## 3. What was checked against the v0.32.0 source

URL pattern: `https://github.com/vllm-project/vllm/blob/v0.32.0/<path>#L<line>` (raw: `https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/<path>`). "unchanged" = the draft already had it; "changed" = the launcher differs from the draft because of what the source says; "new" = not in the draft.

### Flags (`vllm serve`)

| Flag | Status | Source at v0.32.0 |
|---|---|---|
| `--enable-prefix-caching` / `--no-enable-prefix-caching` | verified, unchanged (the check list now also requires the `--no-` form) | `vllm/engine/arg_utils.py#L1370`; bool fields become `argparse.BooleanOptionalAction` (`#L378-L380`); default True `vllm/config/cache.py#L141` |
| `--block-size` | **changed**: passed explicitly (`16`); the draft assumed it | `arg_utils.py#L1355`; `CacheConfig.DEFAULT_BLOCK_SIZE = 16` `cache.py#L72` |
| `--num-gpu-blocks-override` | verified and honoured by the v1 engine; pool = `KV_TOKENS / 16` = 18750 blocks | `arg_utils.py#L1367`; `vllm/v1/core/kv_cache_utils.py#L1230` (`may_override_num_blocks`), `#L2605-L2625` (logs "Overriding num_gpu_blocks=%d with num_gpu_blocks_override=%d"). The help text says "used for testing preemption"; the code path is live. `--kv-cache-memory-bytes` (`#L1363`) is the byte-denominated alternative, not used |
| `--gpu-memory-utilization 0.90` | verified (default 0.92, alias `--device-memory-utilization`) | `arg_utils.py#L1357`, `cache.py` |
| `--max-num-seqs 256`, `--max-num-batched-tokens 8192` | verified; vLLM's defaults are 128 and 2048, so the explicit values matter | `arg_utils.py#L1717`, `#L1703`; `vllm/config/scheduler.py#L41-L43` |
| `--enable-chunked-prefill` | **new**, explicit (default is already True) | `arg_utils.py#L1748`; `scheduler.py#L134` |
| `--scheduling-policy fcfs` | **new**, explicit; choices are `fcfs`/`priority` only, default fcfs, no cache-aware ordering | `arg_utils.py#L1745`; `scheduler.py#L21`, `#L159` |
| `--max-model-len 49152` | verified; needs the env override below | `arg_utils.py#L966`; `vllm/config/model.py#L2644-L2665` |
| `--hf-overrides '{"max_position_embeddings": 49152}'` | **new, changes behaviour** (see "Rotary cache" below) | flag `arg_utils.py#L1010`; `vllm/model_executor/models/qwen2.py#L268`; `vllm/model_executor/layers/rotary_embedding/base.py#L97` |
| `--enable-prompt-tokens-details` | verified; without it `usage` has no `prompt_tokens_details.cached_tokens` | `vllm/entrypoints/launchers/cli_args.py#L148`; `vllm/entrypoints/openai/completion/serving.py#L453-L456`, `#L609-L615` |
| `--generation-config vllm` | verified (optional flag; "vllm" = do not load the model's `generation_config.json`) | `arg_utils.py#L1016`; `model.py#L354-L360` |
| `--revision` | verified; the tokenizer follows it; resolution is best-effort and offline-safe | `arg_utils.py#L961`; `model.py#L598-L599`; `vllm/transformers_utils/repo_utils.py#L52-L93` |
| `--host`, `--port` | verified | `cli_args.py#L283`, `#L285` |
| `--help=all` | verified: plain `--help` prints only the group list; `--help=all` prints every flag, which is what the check greps | `vllm/utils/argparse_utils.py#L196-L244`, `#L347-L349` |
| `--enforce-eager` | **new**, smoke-only diagnostic (`ENFORCE_EAGER=1`); refused for every other MODE | `arg_utils.py#L975` |

### Environment variables (`vllm/envs.py`)

| Name | Status | Source |
|---|---|---|
| `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` | verified. Needed: Qwen2.5's `config.json` has no `model_max_length`, so 49152 > 32768 raises without it | `envs.py#L1123`; `model.py#L2643-L2665` |
| `VLLM_SERVER_DEV_MODE=1` | verified. Gates `/reset_prefix_cache` (and the other dev routes) | `envs.py#L1487`; `vllm/entrypoints/launchers/api_server/routers.py#L40-L43`; `vllm/entrypoints/serve/__init__.py#L43-L65` |
| `VLLM_USE_FLASHINFER_SAMPLER=0` | **new**. Default is True; the FlashInfer top-p/top-k sampler JIT-compiles (needs nvcc). Our requests are greedy with `top_p=1.0`, so it would not run, but warm-up might touch it | `envs.py#L878`; `vllm/v1/sample/ops/topk_topp_sampler.py#L77-L135` |
| `VLLM_USE_RUST_FRONTEND=0` | **new**, explicit (default off). 0.32.0 ships an optional Rust frontend; the dev routes below are the Python frontend's | `envs.py#L170`, `#L582-L600` |
| `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1` | verified (`== "1"` / `VLLM_DO_NOT_TRACK or DO_NOT_TRACK`) | `envs.py#L833-L840` |
| `VLLM_CACHE_ROOT`, `TRITON_CACHE_DIR` | **new**: set under `$XDG_CACHE_HOME` (class storage). vLLM's default is `$XDG_CACHE_HOME/vllm` anyway; the launcher makes it explicit and overridable | `envs.py#L338-L342`, `#L712` |

`check_engine_flags` greps the installed package for each of these names, so a rename in another release fails before launch.

### HTTP endpoints and response fields

| Item | Status | Source |
|---|---|---|
| `GET /health` -> 200 (503 if the engine died); the API server listens only after the engine is up | verified, unchanged | `vllm/entrypoints/serve/instrumentator/health.py#L22-L33` |
| `GET /v1/models` lists the model id (`Qwen/Qwen2.5-7B-Instruct`) | verified | `vllm/entrypoints/openai/models/api_router.py#L20` |
| `GET /metrics` always on (Prometheus text) | verified; the access-log filter keeps `/metrics` and `/health` out of the log | `vllm/entrypoints/serve/instrumentator/metrics.py` |
| `POST /v1/completions`, `prompt` = list of token ids; `ignore_eos`, `repetition_penalty`, `top_p` are request fields | verified | `vllm/entrypoints/openai/completion/protocol.py#L51-L56`, `#L72`, `#L79`, `#L84` |
| `"return_token_ids": true` -> `choices[0].token_ids` (output ids) and `choices[0].prompt_token_ids` | verified; matches the harness path `choices.0.token_ids` | `protocol.py#L171`, `#L667-L669` |
| `usage.prompt_tokens_details.cached_tokens` | verified, present as 0 when nothing is cached (`num_cached_tokens` starts at 0), counted at first scheduling, local + external | `serving.py#L609-L615`; `vllm/v1/engine/output_processor.py#L182`, `#L734-L737`; `vllm/v1/metrics/stats.py#L308-L346` |
| `POST /reset_prefix_cache` | verified, **dev mode only**. Returns HTTP 200 and `{"success": false}` while any KV block is still held | `vllm/entrypoints/serve/dev/cache/api_router.py#L20-L45`; `vllm/v1/core/block_pool.py#L827-L866` ("Failed to reset prefix cache because some blocks (%d) are not freed yet") |
| Client disconnect cancels the request in the engine (`@with_cancellation`) | verified | `vllm/entrypoints/openai/completion/api_router.py#L45` |

**Flush fix.** `slurm/common.sh` `flush_cache` accepts any HTTP 200. I ran its function against a server that answers `200 {"success": false}` and it returns 0 (cache not emptied). `engine_vllm.sh` therefore redefines `flush_cache` (it is sourced after `common.sh`): same tries, timeouts, log lines and `STRICT_FLUSH` behaviour, but success needs `"success": true` in the body. `reset_and_verify` still proves the outcome with the canary, as before.

### Metrics (Prometheus text names; counters get `_total`)

| Metric | Use | Source (`vllm/v1/metrics/loggers.py`) |
|---|---|---|
| `vllm:num_requests_running` | running gauge | `#L528` |
| `vllm:num_requests_waiting` | waiting gauge (waiting + skipped-waiting) | `#L538`, `#L1150-L1154` |
| `vllm:kv_cache_usage_perc` | KV in use, 0 to 1. **Evictable cached blocks count as free**, so it is "in use by running requests", not "resident"; denominator is `num_gpu_blocks - 1` (`block_pool.py#L877-L886`) | `#L620` |
| `vllm:prefix_cache_queries_total`, `vllm:prefix_cache_hits_total` | tokens queried / hit | `#L662`, `#L673` |
| `vllm:num_preemptions_total` | preemptions by recompute (the SGLang retraction analogue) | `#L739` |
| `vllm:prompt_tokens_total`, `vllm:prompt_tokens_cached_total` | prompt and cached prompt tokens | `#L748`, `#L773` |
| `vllm:cache_config_info{...}` | one series whose labels hold `block_size`, `num_gpu_blocks`, `kv_cache_size_tokens`, `cache_hit_alignment_tokens`: the proof of the KV cap in `metrics_first.txt` | `#L1114-L1131`; `vllm/config/cache.py#L219-L240`, `#L322` |

The names in `configs/agentload_analysis.yaml` (`engine_metrics`) and `CanaryCfg` already list the first six, so no harness change is needed (`vllm:gpu_prefix_cache_hit_rate` in `hit_gauge` no longer exists; the analysis falls back to the counters). A test pins this (`test_harness_metric_candidates_list_the_names_verified_in_v0_32_0`).

### Behaviour that differs from SGLang and matters for the comparison

- **Block granularity.** A prefix hit is a whole 16-token block and is capped at `prompt - 1` tokens (`vllm/v1/core/kv_cache_manager.py#L290-L298`). The probe's repeated 64-token prompt should report **48** cached tokens (SGLang reported 63); the canary (1024 tokens) should report 1008 on the second request and 0 after a flush (`max_cached_after_flush: 15` is one block). A follow-up turn recomputes about 550 + up to 15 tokens, about 1% more than SGLang's 550 + 1.
- **Null block.** The pool is 18750 blocks including the null block: the log line reports 300,000 tokens, the usable pool is 18749 blocks = 299,984 tokens (16 tokens below SGLang's `--max-total-tokens 300000`).
- **Admission.** `scheduler_reserve_full_isl` is True: a waiting request is admitted only if its whole uncached prompt fits (`vllm/config/scheduler.py#L190`; `scheduler.py#L1270`), and blocks of a waiting request's cached prefix can be evicted before it is admitted (`notes/lit/engine-alloc-semantics-vllm-sglang.md`). `max_tokens` is not reserved (release note #57035).
- **Chunk size.** `--max-num-batched-tokens 8192` is a per-step budget shared by prefill chunks and decodes, not a per-request chunk like SGLang's `--chunked-prefill-size 8192`.
- **Async scheduling** is on by default when supported (`vllm/config/vllm.py#L1585-L1644`); the launcher does not touch it. Read the server log to record it.
- **Attention backend** on an A100 (compute capability 8.x) is FLASH_ATTN first, FlashInfer second (`vllm/platforms/cuda.py#L158-L181`): no FlashInfer JIT on the default path, so none of the `CUDA_HOME` shim work of the SGLang env is needed.
- **Hashing** is sha256 over pickled blocks by default (`--prefix-caching-hash-algo`, `docs/design/prefix_caching.md`); about 2500 block hashes per 40k-token prompt, small at 1 to 2 requests/s.
- **Dev-mode exposure.** `VLLM_SERVER_DEV_MODE=1` also exposes `/collective_rpc`, `/sleep`, `/server_info` on `127.0.0.1:$PORT` without authentication (`--api-key` only guards `/v1`, `/v2`, `/inference`, `/cohere`: `vllm/entrypoints/serve/middleware/authenticate.py#L12`). Same exposure class as SGLang's `/flush_cache` on a shared node (the port is derived from the job id); nothing else is reachable from outside the node.

### Rotary cache (the finding that changed the launcher)

The plan sets `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` and `--max-model-len 49152`. In v0.32.0 that lets the server accept 49152-token contexts, but Qwen2 builds its rotary cos/sin cache from `config.max_position_embeddings` (32768), not from `--max-model-len` (`qwen2.py#L268`; the cache is `torch.arange(max_position_embeddings)`, `rotary_embedding/base.py#L97`). Positions 32768 and above would index past the end of that cache; the fused CUDA op does no bounds check. The prompts reach 40,350 tokens (36 requests above 32,768 in the SGLang smoke). SGLang does not have the problem (its cache follows `--context-length`). The launcher passes `--hf-overrides '{"max_position_embeddings": 49152}'`, which sizes the cache to the served context. Past 32k the model has no YaRN, so the outputs are garbage but finite and are ignored (`ignore_eos`, fixed length), the same position as the SGLang cells. The smoke job must show no CUDA error or NaN in the log.

## 4. Order of work and what each step needs

```
setup install (CPU) -> setup check (GPU, 20 min) -> smoke -> E0a (vLLM own lambda_miss) -> derive + commit the EXPLORATORY registration (local) -> 6 BURST jobs
```

Every sbatch below is run on Nova from `/work/classtmp/avalse/swapp/repo` after syncing it to a commit that contains this branch. First `env | grep ^SBATCH_` must print nothing and `mkdir -p logs`. Account, partition and QoS are passed on the command line as well as in the header: command-line options win over any `SBATCH_*` variable in the shell. Shared exports:

```bash
W=/work/classtmp/avalse/swapp
REV=a09a35458c702b33eeacc393d103063234e8bc28
SLURMOPT="--account=f2026.coms.6250.02 --partition=instruction --qos=instruction"
SMOKE="ALL,ENV_GEN=$W/envs/swapp,ENV_VLLM=$W/envs/vllm,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,HF_REVISION=$REV"
COMMON="$SMOKE,OUTPUT_FEEDBACK=server,KV_TOKENS=300000"
```

(No `CUDA_HOME_SHIM`: vLLM's default path needs no JIT toolchain.)

### Step 1: environment, install phase (CPU only, no GPU-hours)

```bash
sbatch $SLURMOPT --export=ALL,SWAPP_ROOT=$W slurm/setup_vllm_env.sbatch
```

The job header asks for 8 CPUs, 32 GB, 2 h and no GPU, like `setup_nova.sbatch` (which took 18:54 for the SGLang env plus the model). It checks PyPI reachability (exit 3 if not), creates `$W/envs/vllm` with micromamba (`python=3.12`), `pip install vllm==0.32.0`, runs `pip check`, prints the versions, asserts `vllm==0.32.0`, `torch` starts with `2.13.0` and `torch.version.cuda` starts with `13.`, and writes `$W/envs/vllm.lock.txt` and `vllm.micromamba.yml`. All caches (`PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `CONDA_PKGS_DIRS`, `MAMBA_ROOT_PREFIX`) are on class storage. Compute nodes reach PyPI (`notes/LOG.md`, 2026-10-21: HTTP 200 from nova22-25); the script still checks. No GPU is needed because the wheels are prebuilt and `import torch` works on a CPU node; the import of vLLM's compiled kernels needs the driver, hence Step 2. Expect several GB of downloads (torch 502 MiB, the CUDA 13 libraries, flashinfer, triton).

Success: last line `SETUP_DONE install ...`, `VERSIONS_OK`, `pip check` clean. Pull `envs/vllm.lock.txt` next to `swapp.lock.txt` and `sglang.lock.txt` for the record.

### Step 2: environment, GPU check (about 10 to 20 min, <= 0.33 GPU-h)

```bash
sbatch $SLURMOPT --gres=gpu:a100:1 --exclude=nova22-amp-7 --time=00:20:00 --export=ALL,SWAPP_ROOT=$W,PHASE=check slurm/setup_vllm_env.sbatch
```

Prints `nvidia-smi` and `nvidia-smi topo -m`, the versions, a bf16 4096x4096 matmul on the GPU, `import vllm`, the platform, `import vllm._custom_ops` (loads the compiled kernels) and `vllm.vllm_flash_attn`, then runs exactly the check every job runs (`check_engine_flags`: `vllm serve --help=all`, all flags, env var names, version) and saves the help text to `$W/envs/vllm_serve_help_0.32.0.txt`. Success: `CHECK_DONE`. Failure exit codes: 6 version, 7 no GPU, 8 GPU import, 9 flag check. This catches every static mistake before a 0.84 GPU-h smoke job.

### Step 3: smoke (about 35 to 45 min, 0.84 GPU-h)

```bash
sbatch $SLURMOPT --time=01:30:00 --export="$SMOKE,MODE=smoke" slurm/vllm_job.sbatch
```

Closed population 32 for 1800 s, prefix caching on, `OUTPUT_FEEDBACK=auto` (default for smoke), label `vllm-smoke`, `STRICT_FLUSH=0`. Decide from the logs (the Stage 0 list, a to m, for vLLM):

| # | Look at | Expect |
|---|---|---|
| a | `flag_check.txt` | no MISSING or MISMATCH; `vllm version ok: 0.32.0` |
| b | `probe.txt` | request 1 `cached_tokens` 0, request 2 **48**, `prompt_tokens` 64 |
| c | `probe.txt` request 3, `PROBE_SUMMARY` | `return_token_ids_http` 200, `output_ids_present` true. **Decision: if true, pin `OUTPUT_FEEDBACK=server` for every vLLM job (the SGLang cells use server).** If false, stop: both engines must use the same source (D5) and the lead decides |
| d | `metrics_first.txt` | the six names of section 3, plus `vllm:cache_config_info` with `block_size="16"`, `num_gpu_blocks="18750"` |
| e | `server.log`, `meta.json` | requests above 32,768 tokens served (36 in the SGLang smoke), no `illegal memory access`, no NaN or CUDA error, (the exact log wording for `hf_overrides` is not verified; look for the override in the startup config echo) |
| f | `server.log` | "GPU KV cache size: 300,000 tokens" and "Overriding num_gpu_blocks=N with num_gpu_blocks_override=18750": **N x 16 is the native pool**, needed only if the native-pool replicate is ever run |
| g | run `meta.json` | `prompt_tokens_mismatch` 0 |
| h | `job_events.log`, `canary_1_*.json` | `flush HTTP 200 success=true`; canary prime cached about 1008, check cached 0; `reset_and_verify: verified=true` |
| i | `server.log` timestamps | real startup time to healthy (cold torch.compile and CUDA-graph capture are in it); the SGLang value was 101 s. If above 900 s, raise `HEALTH_TIMEOUT_S` |
| j | `banner.txt` | `NVIDIA A100 80GB PCIe, 81920 MiB`, driver 580.178.04, a `nova22-gpu-*` node |
| k | `server.log` | attention backend (expected FLASH_ATTN), "Asynchronous scheduling" line, `torch.compile` cache path under `$W/cache/vllm`, no FlashInfer compile |
| l | `requests.csv` | 0 request errors with `repetition_penalty` and `top_p` in the body |
| m | `agentload_analysis_windows` | follow-up hit fraction and `vllm:kv_cache_usage_perc` for the record; not a pass/fail (SGLang: 0.689 follow-up, KV mean 0.61) |

If the server dies at startup the job exits within minutes and costs about 0.1 GPU-h. Read `server.log`. If the error is in torch.compile, Triton or a missing C compiler, rerun the smoke once with `ENFORCE_EAGER=1` in the export (smoke only, the script refuses it elsewhere) to separate engine start-up from compiler problems; calibration and E2 data must not use it. If parallel cold starts ever race on the shared compile cache, preset `VLLM_CACHE_ROOT` to a job-local directory in the export.

### Step 4: E0a, vLLM's own all-miss capacity (1 job, 3.62 GPU-h, about 3.7 h wall)

```bash
sbatch $SLURMOPT --export="$COMMON,MODE=miss,SEEDS=0 1 2" slurm/vllm_job.sbatch
```

Prefix caching **off** (`--no-enable-prefix-caching`), label `vllm-nocache`, closed population 32, seeds 0, 1, 2 at 2700 s each (900 s warm-up, 1800 s measured), plus one population-64 check (seed 0, analysed separately). The job's own wall check needs 3.65 h of the 4 h limit. Post-analysis writes `results/agentload_analysis_miss/<ts>/calibration.json` with `lambda_miss`, `lambda_miss_turns_based`, `all_miss_uncached_tokens_per_s`, `all_miss_cached_frac_tokens_max`, `labels`, `hardware`.

Checks before moving on, as for SGLang: seeds agree within about 5%; population 64 within about 5% of 32; `all_miss_cached_frac_tokens_max` is 0 (a non-zero value means the cache was not off); no trend over six 300 s bins; `labels == ["vllm-nocache"]` and `hardware == "NVIDIA A100 80GB PCIe, 81920 MiB"` (both are required by the derivation below). SGLang's references for scale: `lambda_miss_turns_based` 0.0715 sessions/s, `all_miss_uncached_tokens_per_s` 11,243.

### Step 5: derived EXPLORATORY registration (local, no GPU)

The tool is on `main` (`analysis/prereg.py`, `derive-exploratory`; `notes/E2_RUNBOOK.md` Stage 5). From a checkout that contains the committed parent `configs/agentload_prereg_2026-10-24.yaml`:

```bash
D=2026-10-NN                                     # date of the vLLM E0a pull
VCAL=prereg/inputs/$D/calibration_vllm-nocache.json
PRE=configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml
mkdir -p prereg/inputs/$D
cp <pulled>/agentload_analysis_miss/<ts>/calibration.json "$VCAL"
PYTHONPATH=src:. python -m analysis.prereg derive-exploratory --from configs/agentload_prereg_2026-10-24.yaml \
    --engine-cell-label vllm-fcfs --calibration "$VCAL" --arms burst --out "$PRE"
PYTHONPATH=src:. python -m analysis.prereg validate "$PRE"
git add "$VCAL" "$PRE" && git commit -m "vLLM exploratory registration vllm-fcfs (BURST arm) and its E0a calibration"
PYTHONPATH=src:. python -m analysis.prereg check-job "$PRE" --label vllm-fcfs --arms burst --mults "1.35 1.65" \
    --calib "$VCAL" --hardware "NVIDIA A100 80GB PCIe, 81920 MiB"
```

What the tool enforces (read from `analysis/prereg.py` on `main`): the parent must be `FILLED`, valid, committed and byte-identical to its HEAD blob; the label must not be the registered one (`vllm-fcfs` is fine); a different engine needs its own `--calibration`, whose `labels` must start with `vllm` and whose `hardware` must equal the registered hardware; the derived file takes vLLM's `lambda_ref` and `all_miss_uncached_tokens_per_s` and **keeps the parent's window, multiples, protocol and trap rule** (so the window is not a measured vLLM boundary); it refuses to overwrite; `check-job` later requires the calibration bytes to match the sha256 recorded in the file, `ARMS` given and in `allowed_arms`, and the file committed and clean on Nova. The calibration file must therefore be committed in the repo (not only in `results/`) before the first burst job, together with the derived file; sync both to Nova, then submit.

### Step 6: BURST arm, 2 multiples x 3 seeds (6 jobs, 16.85 GPU-h, 2.81 h each)

```bash
VCAL=prereg/inputs/$D/calibration_vllm-nocache.json
PRE=configs/agentload_prereg_2026-10-24_grid_vllm-fcfs.yaml
for m in 1.35 1.65; do for s in 0 1 2; do
  sbatch $SLURMOPT --time=03:10:00 --export="$COMMON,MODE=burst,MULTS=$m,SEEDS=$s,ARMS=burst,CALIB_FILE=$VCAL,PREREG_FILE=$PRE,ENGINE_LABEL=vllm-fcfs" slurm/vllm_job.sbatch
done; done
```

Same line as `notes/E2_RUNBOOK.md` Stage 5 for the vLLM cell, with `slurm/vllm_job.sbatch` and the vLLM calibration. One 8700 s BURST run per job (burst of 200 sessions in 60 s at t_b = 1200 s); `POLICY`, `REFRESH` and `LPM_INF` are not read by the vLLM scripts. The six jobs are independent and can run in one wave (the per-user cap of 11 GPUs is shared with the COMS 6720 project and with the SGLang grid jobs 17097086 to 17097103). Summarise with:

```bash
python -m analysis.summarize burst2 --run-dirs <the six run dirs> --prereg "$PRE"
```

The verdict reports TRAPPED / RECOVERED / neither per run; it is exploratory and never decisive.

## 5. GPU-hour estimate (the plan's formula)

Per job: 0.25 h startup + k runs x (run_s + 150 s overhead)/3600 + g gaps x 180 s/3600 + 0.05 h teardown (`notes/NOVA_PLAN_prefix_meta.md` section 7; the figures match its `S0_smoke_vllm`, `E0a_miss_vllm` and `E2b_vllm_fcfs` rows).

| Step | Jobs | Arithmetic | GPU-h |
|---|---|---|---|
| 1 setup install | 1 (CPU) | no GPU | 0 |
| 2 setup check | 1 | limit 20 min, expected 10 | <= 0.33 |
| 3 smoke | 1 | 0.25 + (1800+150)/3600 + 0 + 0.05 = 0.842 | 0.84 |
| 4 E0a | 1 | 0.25 + 4 x (2700+150)/3600 + 3 x 0.05 + 0.05 = 3.617 | 3.62 |
| 5 registration | local | no GPU | 0 |
| 6 BURST x 6 | 6 | 6 x [0.25 + (8700+150)/3600 + 0.05 + 0.05] = 6 x 2.808 | 16.85 |
| **Total** | 10 | 0.84 + 3.62 + 16.85 = 21.31, plus the check | **21.31, at most 21.64** |

A failed start-up attempt costs about 0.1 GPU-h each (the three failed SGLang smoke attempts ran 28 s, 1:49 and 1:04). Wall time: install about 0.5 h, check 0.3 h, smoke 0.9 h, E0a 3.7 h, registration 0.2 h, burst wave 3 h: about 8.6 h plus queueing. Not included: vLLM Stage C (optional, about 6.49 GPU-h for the SGLang grid; the plan gives vLLM no Stage-C curve, so its window is inherited), a native-pool replicate, re-runs.

## 6. Open risks for the first smoke job

1. **torch.compile / Triton / C compiler on the compute node.** vLLM compiles with Inductor and Triton at first start; Triton builds a small C stub against the driver's `libcuda`. Not exercised for vLLM yet. The SGLang run used Triton kernels on the same nodes (job 17060165), and the flag check prints whether `gcc`, `g++` and `cc` exist. Fallback: the smoke-only `ENFORCE_EAGER=1`.
2. **Cold start time.** First start includes weight load from NFS, compile and CUDA-graph capture; `HEALTH_TIMEOUT_S` defaults to 900 s, `STARTUP_ALLOW_S` to 600 s. The shared compile cache under `$XDG_CACHE_HOME` is warm after the smoke; six simultaneous cold starts could race on it (preset `VLLM_CACHE_ROOT` to a job-local directory if so).
3. **Positions above 32k.** The `--hf-overrides` fix rests on reading `qwen2.py` and `rotary_embedding/base.py`; the smoke is where it is confirmed (item e of the table). If a CUDA error appears at the first prompt above 32,768 tokens, the alternative is the plan's `max_turns` 45 (context <= 32k), which departs from the simulator.
4. **Statically verified, never run.** All flag, env, endpoint and metric names are checked against source, and the tests prove the launcher builds the command I think it builds, but only a job proves vLLM starts with this command on EL9 and driver 580.
5. **Hit semantics.** Block-aligned hits (48 not 63 in the probe) and `kv_cache_usage_perc` excluding evictable blocks mean cross-engine plots of hit rate and KV usage need the definitions in section 3, not a raw overlay.
6. **Doc conflict on CUDA 12.9 versus 13.0.** Resolved by the release notes and the binaries; the install asserts it.
7. **FlashInfer/Humming compiler wheels.** vLLM's resolve pulls `nvidia-cuda-nvcc==13.4.92`, `nvidia-nvvm==13.4.92`, `nvidia-cuda-crt==13.4.92` (via `humming-kernels`) next to a 13.0.96 runtime, the mix that broke SGLang's FlashInfer JIT (job 17060085). The default A100 path for a bf16 dense model uses none of them, so they are left as vLLM publishes them; pin them to 13.0 as `setup_nova.sbatch` does only if a JIT path ever fires.
8. **Dev-mode endpoints** are unauthenticated on localhost of a shared node (section 3).
9. **`/reset_prefix_cache` while draining.** `success=false` is retried for up to 24 x 5 s; after a trapped run the engine may need longer than the 180 s gap to abort thousands of cancelled requests. The job then aborts under `STRICT_FLUSH=1` rather than start from a non-empty cache (`FLUSH_TRIES`, `GAP_S` are tunable).
10. **Compute-node internet.** The task brief calls it untested; `notes/LOG.md` (2026-10-21) records HTTP 200 for PyPI and Hugging Face from nova22-25. The setup script checks again.
