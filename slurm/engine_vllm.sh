#!/usr/bin/env bash
# vLLM v0.32.0 launcher. Sourced by slurm/vllm_job.sbatch. Never run on Nova yet.
#
# STATIC CHECK (done 2026-10-25, against the source at tag v0.32.0, commit 5df63a7203cdb9328d824a27b682e77c7b9928be;
# raw files https://raw.githubusercontent.com/vllm-project/vllm/v0.32.0/<path>; table in notes/VLLM_RUNBOOK.md section 3):
#   flags (all in vllm/engine/arg_utils.py unless noted; booleans are argparse.BooleanOptionalAction, so --X and --no-X exist):
#     --enable-prefix-caching / --no-enable-prefix-caching (l.1370, CacheConfig default True), --block-size (l.1355, default 16 =
#     CacheConfig.DEFAULT_BLOCK_SIZE), --num-gpu-blocks-override (l.1367; honoured by the v1 engine in vllm/v1/core/kv_cache_utils.py
#     may_override_num_blocks + get_kv_cache_configs), --gpu-memory-utilization (l.1357), --max-num-seqs (l.1717),
#     --max-num-batched-tokens (l.1703), --enable-chunked-prefill (l.1748, default True), --scheduling-policy (l.1745, choices
#     fcfs|priority, default fcfs, vllm/config/scheduler.py), --max-model-len (l.966), --generation-config (l.1016, "vllm" = no model
#     generation_config.json), --revision (l.961), --hf-overrides (l.1010), --host/--port (frontend), --enable-prompt-tokens-details
#     (vllm/entrypoints/launchers/cli_args.py l.148; without it usage has no prompt_tokens_details.cached_tokens).
#   env vars (vllm/envs.py): VLLM_ALLOW_LONG_MAX_MODEL_LEN (l.1123, "1"/"true"), VLLM_SERVER_DEV_MODE (l.1487, int, gates
#     /reset_prefix_cache: vllm/entrypoints/launchers/api_server/routers.py l.40-43), VLLM_USE_FLASHINFER_SAMPLER (l.878),
#     VLLM_NO_USAGE_STATS (l.833, == "1"), DO_NOT_TRACK / VLLM_DO_NOT_TRACK (l.834), VLLM_USE_RUST_FRONTEND (l.170, default off).
#     check_envvars below greps the INSTALLED package for each name (a misspelt name is silently ignored by the engine).
#   endpoints: GET /health (200, 503 if the engine died; vllm/entrypoints/serve/instrumentator/health.py), GET /metrics,
#     GET /v1/models, POST /v1/completions with a token-id list as prompt, "return_token_ids": true (CompletionRequest.return_token_ids)
#     -> choices[0].token_ids (output ids) and choices[0].prompt_token_ids, POST /reset_prefix_cache (dev mode only;
#     vllm/entrypoints/serve/dev/cache/api_router.py): HTTP 200 with {"success": false} while any block is still held, so a bare
#     HTTP-200 test is NOT enough: flush_cache() below is overridden to require "success": true.
#   metrics (vllm/v1/metrics/loggers.py, Prometheus text names with _total on counters): vllm:num_requests_running,
#     vllm:num_requests_waiting, vllm:kv_cache_usage_perc (in-use blocks only: evictable cached blocks count as free),
#     vllm:prefix_cache_queries_total, vllm:prefix_cache_hits_total (tokens), vllm:num_preemptions_total,
#     vllm:prompt_tokens_total, vllm:prompt_tokens_cached_total.
# STILL UNVERIFIED until the first vLLM smoke job on Nova (runtime behaviour, not names): that vllm serve starts with a CUDA-13 torch
# 2.13.0 on driver 580.178.04, that torch.compile/Triton find a C compiler on the compute node, that the server log prints
# "GPU KV cache size: 299,984 tokens" with the cap (the null block takes one of the 18750 blocks), that the probe's repeated
# 64-token prompt reports 48 cached tokens (block aligned, hit length capped at prompt-1), and that offline HF loading works.
# Optional flags (used only if present in --help): --generation-config, --revision (HF_REVISION pin).

ENGINE=vllm
HEALTH_PATH=/health
FLUSH_PATH=/reset_prefix_cache
FLUSH_METHOD=POST

: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
SERVED_MODEL="$MODEL"        # the id /v1/models must list (checked after startup)
: "${POLICY:=fcfs}"          # vLLM v0.32.0 --scheduling-policy is fcfs|priority only (no cache-aware ordering); passed explicitly as fcfs
: "${KV_TOKENS:=300000}"     # cap on the KV pool to match the SGLang cell (--max-total-tokens 300000); "native" = no cap
: "${CONTEXT_LEN:=49152}"    # max prompt ~40350 tokens > Qwen2.5's default 32768
: "${BLOCK_SIZE:=16}"        # tokens per KV block; KV_TOKENS / BLOCK_SIZE blocks (the null block takes one: usable = KV_TOKENS - 16)
: "${EXPECTED_VLLM_VERSION:=0.32.0}"   # check_engine_flags refuses another version: every name above was verified for this one
: "${ENV_VLLM:=/work/<group-dir>/avalse/swapp/envs/vllm}"              # PLACEHOLDER (slurm/setup_vllm_env.sbatch builds it)
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER; needs aiohttp numpy pandas pyyaml
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1
# no telemetry from either engine or the HF client (the two engines must not differ in background network/CPU work)
export DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1 HF_HUB_DISABLE_TELEMETRY=1

# RADIX=0 for MODE=miss (prefix caching off in the engine), 1 otherwise
case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

engine_env_dir() { echo "$ENV_VLLM"; }
engine_required_vars() { echo "ENV_VLLM HF_HOME"; }

# The env is never activated: its bin/ goes on PATH (ninja, python), and every cache goes to class storage (home has a 10 GB
# quota): VLLM_CACHE_ROOT holds torch.compile artifacts, TRITON_CACHE_DIR Triton kernels. XDG_CACHE_HOME comes from the submit
# environment (the COMMON exports of the runbook); without it the caches fall back to $HOME/.cache.
setup_vllm_env() {
  export PATH="$ENV_VLLM/bin:$PATH"
  export VLLM_CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/vllm"
  export TRITON_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/triton"
}

# Prints one line per check; returns 1 if STRICT_FLAGS=1 (default) and a required flag / env var / version is missing.
check_engine_flags() {
  local help rc=0 pkgdir f ver
  setup_vllm_env
  help=$("$ENV_VLLM/bin/vllm" serve --help=all 2>&1) || help=$("$ENV_VLLM/bin/vllm" serve --help 2>&1) || help=""
  printf '%s\n' "$help" > "$JOB_DIR/engine_help.txt"
  check_flags "$help" --enable-prefix-caching --no-enable-prefix-caching --block-size --num-gpu-blocks-override \
      --gpu-memory-utilization --max-num-seqs --max-num-batched-tokens --enable-chunked-prefill --scheduling-policy \
      --max-model-len --hf-overrides --enable-prompt-tokens-details --host --port || rc=1
  if [ -n "${HF_REVISION:-}" ]; then check_flags "$help" --revision || rc=1; fi
  for f in --generation-config; do
    if help_has_flag "$help" "$f"; then echo "optional flag ok:      $f"; else echo "optional flag missing: $f (model generation_config defaults may apply; request-level pins in the configs still hold)"; fi
  done
  ver=$("$ENV_VLLM/bin/python" -c "import vllm; print(vllm.__version__)" 2>/dev/null) || ver=""
  if [ "$ver" = "$EXPECTED_VLLM_VERSION" ]; then echo "vllm version ok: $ver"; else echo "vllm version MISMATCH: installed '${ver:-none}', verified for $EXPECTED_VLLM_VERSION (set EXPECTED_VLLM_VERSION only after re-verifying slurm/engine_vllm.sh)"; rc=1; fi
  "$ENV_VLLM/bin/python" -c "import torch; print('torch', torch.__version__, 'cuda build', torch.version.cuda, 'cuda available', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')" 2>&1 || true
  pkgdir=$("$ENV_VLLM/bin/python" -c "import vllm, os; print(os.path.dirname(vllm.__file__))" 2>/dev/null) || pkgdir=""
  check_envvars "$pkgdir" VLLM_ALLOW_LONG_MAX_MODEL_LEN VLLM_SERVER_DEV_MODE VLLM_USE_FLASHINFER_SAMPLER VLLM_NO_USAGE_STATS \
      VLLM_USE_RUST_FRONTEND VLLM_CACHE_ROOT || rc=1
  # torch.compile (Inductor) and Triton build small C stubs at first use: info only, the server aborts loudly if they are missing
  for f in gcc g++ cc; do if command -v "$f" >/dev/null 2>&1; then echo "toolchain ok:  $f $("$f" --version 2>&1 | head -1)"; else echo "toolchain note: $f not on PATH"; fi; done
  if [ "$rc" = "1" ] && [ "${STRICT_FLAGS:-1}" = "1" ]; then echo "STRICT_FLAGS=1: required vLLM flag(s)/env var(s)/version missing; fix slurm/engine_vllm.sh"; return 1; fi
  return 0
}

# vLLM answers POST /reset_prefix_cache with HTTP 200 and {"success": false} while any KV block is still held (a request that is
# still draining after the client cancelled it), so the common.sh version, which accepts any 200, would report success for a cache
# that was NOT emptied (the canary check would then catch it and, under STRICT_FLUSH=1, abort the whole job). This override, defined
# after common.sh is sourced, retries until the body says "success": true. Same tries/timeouts/log lines as common.sh.
flush_cache() {
  local tries=0 resp code body last="none"
  [ -n "${FLUSH_PATH:-}" ] || { echo "$(date +%T) flush: no endpoint configured" >> "$JOB_DIR/job_events.log"; return 1; }
  while [ "$tries" -lt "${FLUSH_TRIES:-24}" ]; do
    resp=$(curl -s -m "${FLUSH_CURL_MAX_S:-30}" -w $'\n%{http_code}' -X "${FLUSH_METHOD:-POST}" "$BASE_URL$FLUSH_PATH") || resp=$'\n000'
    code=${resp##*$'\n'}; body=${resp%$'\n'*}; last="http $code body '${body:0:80}'"
    if [ "$code" = "200" ] && grep -qE '"success"[[:space:]]*:[[:space:]]*true' <<< "$body"; then
      echo "$(date +%T) flush HTTP 200 success=true ($FLUSH_PATH) after $tries retries" >> "$JOB_DIR/job_events.log"; return 0
    fi
    tries=$((tries + 1)); sleep "${FLUSH_RETRY_S:-5}"
  done
  echo "$(date +%T) flush FAILED ($FLUSH_PATH, last $last): cache NOT emptied before next run" >> "$JOB_DIR/job_events.log"
  log "WARNING: cache flush failed; the next run does not start from an empty cache"
  [ "${STRICT_FLUSH:-1}" = "1" ] && die "STRICT_FLUSH=1 and flush failed"
  return 1
}

launch_engine() {
  local cache_flag="--enable-prefix-caching" extra="" help kv_flag=""
  help=$(cat "$JOB_DIR/engine_help.txt" 2>/dev/null || true)
  # ENFORCE_EAGER=1 (no torch.compile, no CUDA graphs) is a smoke-job diagnostic only: it changes the speed of every request
  if [ "${ENFORCE_EAGER:-0}" = "1" ]; then
    [ "${MODE:-}" = "smoke" ] || die "ENFORCE_EAGER=1 is a diagnostic for MODE=smoke only; calibration and E2 data must use the default (compiled) engine"
    extra="$extra --enforce-eager"
  fi
  # KV_TOKENS=native: the engine sizes its own pool. Otherwise the pool is KV_TOKENS / BLOCK_SIZE blocks (the null block is one of them)
  [ "$KV_TOKENS" != "native" ] && kv_flag="--num-gpu-blocks-override $((KV_TOKENS / BLOCK_SIZE))"
  [ "$RADIX" = "0" ] && cache_flag="--no-enable-prefix-caching"
  if help_has_flag "$help" --generation-config; then extra="$extra --generation-config vllm"; fi
  if [ -n "${HF_REVISION:-}" ]; then extra="$extra --revision $HF_REVISION"; fi
  setup_vllm_env
  log "launching vLLM: prefix_caching=$([ "$RADIX" = "1" ] && echo on || echo off) policy=fcfs kv_tokens=$KV_TOKENS block_size=$BLOCK_SIZE context_len=$CONTEXT_LEN VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT extra='$extra'"
  # VLLM_ALLOW_LONG_MAX_MODEL_LEN + --hf-overrides: the first lets the server accept CONTEXT_LEN > the model's 32768, the second sizes
  # Qwen2's rotary cos/sin cache (built from config.max_position_embeddings, not from --max-model-len) to CONTEXT_LEN so positions
  # above 32767 do not read past it. Past 32k the model has no YaRN: outputs are garbage but finite and ignored (ignore_eos).
  # VLLM_USE_FLASHINFER_SAMPLER=0: no FlashInfer JIT (needs nvcc) for sampling; greedy requests do not use it anyway.
  # VLLM_SERVER_DEV_MODE=1 exposes /reset_prefix_cache (and other dev routes) on 127.0.0.1:$PORT without authentication.
  VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 VLLM_SERVER_DEV_MODE=1 VLLM_USE_FLASHINFER_SAMPLER=0 VLLM_USE_RUST_FRONTEND=0 \
  "$ENV_VLLM/bin/vllm" serve "$MODEL" --host 127.0.0.1 --port "$PORT" \
      $cache_flag --block-size "$BLOCK_SIZE" $kv_flag \
      --scheduling-policy fcfs --enable-chunked-prefill \
      --max-num-seqs 256 --max-num-batched-tokens 8192 --max-model-len "$CONTEXT_LEN" \
      --hf-overrides "{\"max_position_embeddings\": $CONTEXT_LEN}" \
      --enable-prompt-tokens-details \
      --gpu-memory-utilization 0.90 $extra \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
