#!/usr/bin/env bash
# vLLM v0.32.0 launcher (DRAFT, never run). Sourced by slurm/vllm_job.sbatch.
#
# Flags are from memory of the vLLM CLI and UNVERIFIED for v0.32.0; check_engine_flags greps `vllm serve --help`
# (or `--help=all`) for each (exact token match). Names to verify: --enable-prefix-caching/--no-enable-prefix-caching
# --max-num-seqs --max-num-batched-tokens --max-model-len --num-gpu-blocks-override --enable-prompt-tokens-details
# --gpu-memory-utilization. Env (from memory): VLLM_ALLOW_LONG_MAX_MODEL_LEN (exceed model default 32768);
# VLLM_SERVER_DEV_MODE (exposes /reset_prefix_cache in recent versions). Env var NAMES are checked against the installed
# package source (a misspelt name is silently ignored).
# Optional flags (used only if present in --help): --generation-config (we want 'vllm' so the model's
# generation_config.json does not inject a repetition penalty), --revision (HF_REVISION pin).
# vLLM's block size is assumed 16 tokens (KV_TOKENS / 16 blocks); verify in the server log.

ENGINE=vllm
HEALTH_PATH=/health
FLUSH_PATH=/reset_prefix_cache
FLUSH_METHOD=POST

: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
SERVED_MODEL="$MODEL"        # the id /v1/models must list (checked after startup)
: "${POLICY:=fcfs}"          # vLLM v0.32.0 scheduler policy is fcfs|priority only (engine-sources note); kept for the banner
: "${KV_TOKENS:=300000}"    # "native" = no cap on the KV pool
: "${CONTEXT_LEN:=49152}"
: "${ENV_VLLM:=/work/<group-dir>/avalse/swapp/envs/vllm}"              # PLACEHOLDER
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1
# no telemetry from either engine or the HF client (the two engines must not differ in background network/CPU work)
export DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1 HF_HUB_DISABLE_TELEMETRY=1

case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

engine_env_dir() { echo "$ENV_VLLM"; }
engine_required_vars() { echo "ENV_VLLM HF_HOME"; }

# Prints one line per check; returns 1 if STRICT_FLAGS=1 (default) and a required flag / env var is missing.
check_engine_flags() {
  local help rc=0 pkgdir f
  help=$("$ENV_VLLM/bin/vllm" serve --help=all 2>&1) || help=$("$ENV_VLLM/bin/vllm" serve --help 2>&1) || help=""
  printf '%s\n' "$help" > "$JOB_DIR/engine_help.txt"
  check_flags "$help" --enable-prefix-caching --max-num-seqs --max-num-batched-tokens --max-model-len \
      --num-gpu-blocks-override --enable-prompt-tokens-details --gpu-memory-utilization --port || rc=1
  if [ -n "${HF_REVISION:-}" ]; then check_flags "$help" --revision || rc=1; fi
  for f in --generation-config; do
    if help_has_flag "$help" "$f"; then echo "optional flag ok:      $f"; else echo "optional flag missing: $f (model generation_config defaults may apply; request-level pins in the configs still hold)"; fi
  done
  "$ENV_VLLM/bin/python" -c "import vllm; print('vllm version:', vllm.__version__)" 2>&1 || true
  pkgdir=$("$ENV_VLLM/bin/python" -c "import vllm, os; print(os.path.dirname(vllm.__file__))" 2>/dev/null) || pkgdir=""
  check_envvars "$pkgdir" VLLM_ALLOW_LONG_MAX_MODEL_LEN VLLM_SERVER_DEV_MODE || rc=1
  if [ "$rc" = "1" ] && [ "${STRICT_FLAGS:-1}" = "1" ]; then echo "STRICT_FLAGS=1: required vLLM flag(s)/env var(s) missing; fix slurm/engine_vllm.sh"; return 1; fi
  return 0
}

launch_engine() {
  local cache_flag="--enable-prefix-caching" extra="" help kv_flag=""
  help=$(cat "$JOB_DIR/engine_help.txt" 2>/dev/null || true)
  [ "$KV_TOKENS" != "native" ] && kv_flag="--num-gpu-blocks-override $((KV_TOKENS / 16))"   # KV_TOKENS=native: the engine sizes its own pool
  [ "$RADIX" = "0" ] && cache_flag="--no-enable-prefix-caching"
  if help_has_flag "$help" --generation-config; then extra="$extra --generation-config vllm"; fi
  if [ -n "${HF_REVISION:-}" ]; then extra="$extra --revision $HF_REVISION"; fi
  log "launching vLLM: prefix_caching=$([ "$RADIX" = "1" ] && echo on || echo off) kv_tokens=$KV_TOKENS extra='$extra'"
  VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 VLLM_SERVER_DEV_MODE=1 \
  "$ENV_VLLM/bin/vllm" serve "$MODEL" --host 127.0.0.1 --port "$PORT" \
      $cache_flag --max-num-seqs 256 --max-num-batched-tokens 8192 --max-model-len "$CONTEXT_LEN" \
      $kv_flag --enable-prompt-tokens-details \
      --gpu-memory-utilization 0.90 $extra \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
