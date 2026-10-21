#!/usr/bin/env bash
# SGLang v0.5.22 launcher (DRAFT, never run). Sourced by slurm/sglang_job.sbatch.
#
# EVERY engine flag below is from memory of the SGLang CLI and is UNVERIFIED for v0.5.22; check_engine_flags greps
# `--help` for each (exact token match) and the job aborts (STRICT_FLAGS=1, default) if one is missing, before any GPU
# time is spent on a wrong command line. Names to verify: --schedule-policy --max-running-requests
# --chunked-prefill-size --max-total-tokens --context-length --enable-metrics --enable-cache-report --disable-radix-cache.
# Env vars (from notes/lit/engine-sources-prefix-cache.md): SGLANG_ENABLE_WAITING_PREFIX_REFRESH (EnvBool, default true).
# SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN is from memory (needed to exceed the model's 32768 default). Env var NAMES
# are checked against the installed package source (a misspelt name is silently ignored by the engine).
# Optional flags (used only if present in --help): --sampling-defaults (from memory: model|openai; we want 'openai' so
# the model's generation_config.json does not inject a repetition penalty), --revision (HF_REVISION pin).

ENGINE=sglang
HEALTH_PATH=/health
FLUSH_PATH=/flush_cache      # POST; SGLang refuses while requests are running, flush_cache() retries
FLUSH_METHOD=POST

: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
SERVED_MODEL="$MODEL"        # the id /v1/models must list (checked after startup)
: "${POLICY:=fcfs}"          # fcfs | lpm
: "${REFRESH:=1}"            # SGLANG_ENABLE_WAITING_PREFIX_REFRESH: 1 (shipped default) | 0
: "${LPM_INF:=0}"            # 1: use the PATCHED sglang env (WAITING_QUEUE_PREFIX_MATCH_MAX effectively infinite)
: "${KV_TOKENS:=300000}"     # cap on the KV pool to match the simulator's M (native pool ~0.9M tokens, see the plan); "native" = no cap
: "${CONTEXT_LEN:=49152}"    # max prompt ~40350 tokens > Qwen2.5's default 32768
: "${ENV_SGLANG:=/work/<group-dir>/avalse/swapp/envs/sglang}"          # PLACEHOLDER (notes/NOVA_ENV_PLAN.md)
: "${ENV_SGLANG_PATCHED:=/work/<group-dir>/avalse/swapp/envs/sglang-lpm-inf}"   # PLACEHOLDER; only for LPM_INF=1
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER; needs aiohttp numpy pandas pyyaml
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1
# no telemetry from either engine or the HF client (the two engines must not differ in background network/CPU work)
export DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1 HF_HUB_DISABLE_TELEMETRY=1

# RADIX=0 for MODE=miss (prefix caching off in the engine), 1 otherwise
case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

engine_env_prefix() { if [ "$LPM_INF" = "1" ]; then echo "$ENV_SGLANG_PATCHED"; else echo "$ENV_SGLANG"; fi; }
engine_env_dir() { engine_env_prefix; }
engine_required_vars() { echo "ENV_SGLANG HF_HOME"; if [ "$LPM_INF" = "1" ]; then echo "ENV_SGLANG_PATCHED"; fi; }

# Prints one line per check; returns 1 if STRICT_FLAGS=1 (default) and a required flag / env var is missing.
check_engine_flags() {
  local help pkgdir rc=0 py f
  py="$(engine_env_prefix)/bin/python"
  help=$("$py" -m sglang.launch_server --help 2>&1) || { echo "could not run sglang --help"; help=""; }
  printf '%s\n' "$help" > "$JOB_DIR/engine_help.txt"
  check_flags "$help" --schedule-policy --max-running-requests --chunked-prefill-size --max-total-tokens \
      --context-length --enable-metrics --enable-cache-report --disable-radix-cache --model-path --port || rc=1
  if [ -n "${HF_REVISION:-}" ]; then check_flags "$help" --revision || rc=1; fi
  for f in --sampling-defaults; do
    if help_has_flag "$help" "$f"; then echo "optional flag ok:      $f"; else echo "optional flag missing: $f (model generation_config defaults may apply; request-level pins in the configs still hold)"; fi
  done
  "$py" -c "import sglang; print('sglang version:', sglang.__version__)" 2>&1 || true
  pkgdir=$("$py" -c "import sglang, os; print(os.path.dirname(sglang.__file__))" 2>/dev/null) || pkgdir=""
  check_envvars "$pkgdir" SGLANG_ENABLE_WAITING_PREFIX_REFRESH SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN || rc=1
  check_jit_toolchain || rc=1
  if [ "$rc" = "1" ] && [ "${STRICT_FLAGS:-1}" = "1" ]; then echo "STRICT_FLAGS=1: required SGLang flag(s)/env var(s)/JIT toolchain missing; fix slurm/engine_sglang.sh"; return 1; fi
  return 0
}

# FlashInfer (SGLang's default attention backend on A100) JIT-compiles its kernels at startup: it needs ninja, nvcc under
# $CUDA_HOME/bin and links -L$CUDA_HOME/lib64{,/stubs} -lcudart -lcuda (Nova job 17060022 died with "No such file: ninja").
# The env is never activated, so its bin/ and the CUDA_HOME shim (slurm/make_cuda_shim.sh) are exported here. JIT and Triton
# caches go to XDG_CACHE_HOME (class storage; home has a 10 GB quota). ATTN_BACKEND=triton needs none of this.
setup_jit_env() {
  export PATH="$(engine_env_prefix)/bin:$PATH"
  if [ -n "${CUDA_HOME_SHIM:-}" ]; then export CUDA_HOME="$CUDA_HOME_SHIM"; export PATH="$CUDA_HOME/bin:$PATH"; fi
  export FLASHINFER_WORKSPACE_BASE="${XDG_CACHE_HOME:-$HOME/.cache}"
  export TRITON_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/triton"
}
check_jit_toolchain() {
  [ "${ATTN_BACKEND:-flashinfer}" = "triton" ] && { echo "jit toolchain: skipped (ATTN_BACKEND=triton)"; return 0; }
  local rc=0
  setup_jit_env
  if command -v ninja >/dev/null 2>&1; then echo "jit ok:      ninja $(ninja --version)"; else echo "jit MISSING: ninja on PATH"; rc=1; fi
  if [ -z "${CUDA_HOME:-}" ]; then echo "jit MISSING: CUDA_HOME (set CUDA_HOME_SHIM, see slurm/make_cuda_shim.sh)"; return 1; fi
  if [ -x "$CUDA_HOME/bin/nvcc" ]; then echo "jit ok:      $("$CUDA_HOME/bin/nvcc" --version | tail -1)"; else echo "jit MISSING: $CUDA_HOME/bin/nvcc"; rc=1; fi
  local f; for f in "$CUDA_HOME/lib64/libcudart.so" "$CUDA_HOME/lib64/stubs/libcuda.so"; do
    if [ -e "$f" ]; then echo "jit ok:      $f -> $(readlink "$f")"; else echo "jit MISSING: $f (or its target)"; rc=1; fi
  done
  return "$rc"
}

launch_engine() {
  local extra="" help kv_flag=""
  help=$(cat "$JOB_DIR/engine_help.txt" 2>/dev/null || true)
  [ "$RADIX" = "0" ] && extra="--disable-radix-cache"
  [ "$KV_TOKENS" != "native" ] && kv_flag="--max-total-tokens $KV_TOKENS"     # KV_TOKENS=native: the engine sizes its own pool
  if help_has_flag "$help" --sampling-defaults; then extra="$extra --sampling-defaults openai"; fi
  if [ -n "${HF_REVISION:-}" ]; then extra="$extra --revision $HF_REVISION"; fi
  if [ "${ATTN_BACKEND:-flashinfer}" = "triton" ]; then extra="$extra --attention-backend triton --sampling-backend pytorch"; fi
  setup_jit_env
  log "launching SGLang: policy=$POLICY refresh=$REFRESH radix=$RADIX lpm_inf=$LPM_INF kv_tokens=$KV_TOKENS attn=${ATTN_BACKEND:-flashinfer} CUDA_HOME=${CUDA_HOME:-unset} extra='$extra'"
  SGLANG_ENABLE_WAITING_PREFIX_REFRESH="$REFRESH" SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 \
  "$(engine_env_prefix)/bin/python" -m sglang.launch_server \
      --model-path "$MODEL" --host 127.0.0.1 --port "$PORT" \
      --schedule-policy "$POLICY" \
      --max-running-requests 256 --chunked-prefill-size 8192 $kv_flag \
      --context-length "$CONTEXT_LEN" \
      --enable-metrics --enable-cache-report $extra \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
