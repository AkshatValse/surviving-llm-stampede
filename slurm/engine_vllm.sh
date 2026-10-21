#!/usr/bin/env bash
# vLLM v0.32.0 launcher (DRAFT, never run). Sourced by slurm/vllm_job.sbatch.
#
# Flags are from memory of the vLLM CLI and UNVERIFIED for v0.32.0; check_engine_flags greps `vllm serve --help`
# (or `--help=all`) for each. Names to verify: --enable-prefix-caching/--no-enable-prefix-caching --max-num-seqs
# --max-num-batched-tokens --max-model-len --num-gpu-blocks-override --enable-prompt-tokens-details
# --gpu-memory-utilization. Env (from memory): VLLM_ALLOW_LONG_MAX_MODEL_LEN (exceed model default 32768);
# VLLM_SERVER_DEV_MODE (exposes /reset_prefix_cache in recent versions).
# vLLM's block size is assumed 16 tokens (KV_TOKENS / 16 blocks); verify in the server log.

ENGINE=vllm
HEALTH_PATH=/health
FLUSH_PATH=/reset_prefix_cache
FLUSH_METHOD=POST

: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
: "${POLICY:=fcfs}"          # vLLM v0.32.0 scheduler policy is fcfs|priority only (engine-sources note); kept for the banner
: "${KV_TOKENS:=300000}"
: "${CONTEXT_LEN:=49152}"
: "${ENV_VLLM:=/work/<group-dir>/avalse/swapp/envs/vllm}"              # PLACEHOLDER
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1

case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

check_engine_flags() {
  require_set ENV_VLLM; require_set HF_HOME
  local help miss=0 f
  help=$("$ENV_VLLM/bin/vllm" serve --help=all 2>&1 || "$ENV_VLLM/bin/vllm" serve --help 2>&1) || help=""
  for f in --enable-prefix-caching --max-num-seqs --max-num-batched-tokens --max-model-len \
           --num-gpu-blocks-override --enable-prompt-tokens-details --gpu-memory-utilization --port; do
    if echo "$help" | grep -q -- "$f"; then echo "flag ok:      $f"; else echo "flag MISSING: $f"; miss=1; fi
  done
  "$ENV_VLLM/bin/python" -c "import vllm; print('vllm version:', vllm.__version__)" 2>&1 || true
  if [ "$miss" = "1" ] && [ "${STRICT_FLAGS:-1}" = "1" ]; then die "required vLLM flag(s) missing; fix slurm/engine_vllm.sh"; fi
}

launch_engine() {
  local cache_flag="--enable-prefix-caching"
  [ "$RADIX" = "0" ] && cache_flag="--no-enable-prefix-caching"
  log "launching vLLM: prefix_caching=$([ "$RADIX" = "1" ] && echo on || echo off) kv_tokens=$KV_TOKENS"
  VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 VLLM_SERVER_DEV_MODE=1 \
  "$ENV_VLLM/bin/vllm" serve "$MODEL" --host 127.0.0.1 --port "$PORT" \
      $cache_flag --max-num-seqs 256 --max-num-batched-tokens 8192 --max-model-len "$CONTEXT_LEN" \
      --num-gpu-blocks-override "$((KV_TOKENS / 16))" --enable-prompt-tokens-details \
      --gpu-memory-utilization 0.90 \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
