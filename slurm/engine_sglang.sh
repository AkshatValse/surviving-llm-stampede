#!/usr/bin/env bash
# SGLang v0.5.22 launcher (DRAFT, never run). Sourced by slurm/sglang_job.sbatch.
#
# EVERY engine flag below is from memory of the SGLang CLI and is UNVERIFIED for v0.5.22; check_engine_flags greps
# `--help` for each and the job aborts (STRICT_FLAGS=1, default) if one is missing, before any GPU time is spent
# on a wrong command line. Names to verify: --schedule-policy --max-running-requests --chunked-prefill-size
# --max-total-tokens --context-length --enable-metrics --enable-cache-report --disable-radix-cache.
# Env vars (from notes/lit/engine-sources-prefix-cache.md): SGLANG_ENABLE_WAITING_PREFIX_REFRESH (EnvBool, default true).
# SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN is from memory (needed to exceed the model's 32768 default); verify.

ENGINE=sglang
HEALTH_PATH=/health
FLUSH_PATH=/flush_cache      # POST; SGLang refuses while requests are running, flush_cache() retries
FLUSH_METHOD=POST

: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
: "${POLICY:=fcfs}"          # fcfs | lpm
: "${REFRESH:=1}"            # SGLANG_ENABLE_WAITING_PREFIX_REFRESH: 1 (shipped default) | 0
: "${LPM_INF:=0}"            # 1: use the PATCHED sglang env (WAITING_QUEUE_PREFIX_MATCH_MAX effectively infinite)
: "${KV_TOKENS:=300000}"     # cap on the KV pool to match the simulator's M (native pool ~0.9M tokens, see the plan)
: "${CONTEXT_LEN:=49152}"    # max prompt ~40350 tokens > Qwen2.5's default 32768
: "${ENV_SGLANG:=/work/<group-dir>/avalse/swapp/envs/sglang}"          # PLACEHOLDER (notes/NOVA_ENV_PLAN.md)
: "${ENV_SGLANG_PATCHED:=/work/<group-dir>/avalse/swapp/envs/sglang-lpm-inf}"   # PLACEHOLDER; only for LPM_INF=1
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER; needs aiohttp numpy pandas pyyaml
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1

# RADIX=0 for MODE=miss (prefix caching off in the engine), 1 otherwise
case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

engine_env_prefix() { if [ "$LPM_INF" = "1" ]; then echo "$ENV_SGLANG_PATCHED"; else echo "$ENV_SGLANG"; fi; }

check_engine_flags() {
  require_set ENV_SGLANG; require_set HF_HOME
  [ "$LPM_INF" = "1" ] && require_set ENV_SGLANG_PATCHED
  local help miss=0 f
  help=$("$(engine_env_prefix)/bin/python" -m sglang.launch_server --help 2>&1) || { echo "could not run sglang --help"; help=""; }
  for f in --schedule-policy --max-running-requests --chunked-prefill-size --max-total-tokens --context-length \
           --enable-metrics --enable-cache-report --disable-radix-cache --model-path --port; do
    if echo "$help" | grep -q -- "$f"; then echo "flag ok:      $f"; else echo "flag MISSING: $f"; miss=1; fi
  done
  "$(engine_env_prefix)/bin/python" -c "import sglang; print('sglang version:', sglang.__version__)" 2>&1 || true
  if [ "$miss" = "1" ] && [ "${STRICT_FLAGS:-1}" = "1" ]; then die "required SGLang flag(s) missing; fix slurm/engine_sglang.sh"; fi
}

launch_engine() {
  local extra=""
  [ "$RADIX" = "0" ] && extra="--disable-radix-cache"
  log "launching SGLang: policy=$POLICY refresh=$REFRESH radix=$RADIX lpm_inf=$LPM_INF kv_tokens=$KV_TOKENS"
  SGLANG_ENABLE_WAITING_PREFIX_REFRESH="$REFRESH" SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 \
  "$(engine_env_prefix)/bin/python" -m sglang.launch_server \
      --model-path "$MODEL" --host 127.0.0.1 --port "$PORT" \
      --schedule-policy "$POLICY" \
      --max-running-requests 256 --chunked-prefill-size 8192 --max-total-tokens "$KV_TOKENS" \
      --context-length "$CONTEXT_LEN" \
      --enable-metrics --enable-cache-report $extra \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
