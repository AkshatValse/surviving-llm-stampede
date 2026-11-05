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
: "${LPM_INF:=0}"            # 1: the STOCK env (ENV_SGLANG) plus the job-local hook slurm/hooks/lpm_inf/sitecustomize.py on the
                             #    server command line only: WAITING_QUEUE_PREFIX_MATCH_MAX 128 -> LPM_INF_MAX, so LPM never
                             #    falls back to FCFS. 0 (default): every command is byte-identical to the stock cells.
LPM_INF_MAX=1000000000                                # not overridable: the registered sglang-lpminf cell uses exactly 1e9
LPM_INF_STOCK_MD5=b8ec334ac1ed028e3c176022ea1f9143   # md5 of sglang 0.5.22 srt/managers/schedule_policy.py in envs/sglang
LPM_INF_HOOK_MD5=be788ae7495e6445788bad8bd370349a   # md5 of slurm/hooks/lpm_inf/sitecustomize.py (tests/test_lpm_inf_hook.py keeps it current)
: "${KV_TOKENS:=300000}"     # cap on the KV pool to match the simulator's M (native pool ~0.9M tokens, see the plan); "native" = no cap
: "${CONTEXT_LEN:=49152}"    # max prompt ~40350 tokens > Qwen2.5's default 32768
: "${ENV_SGLANG:=/work/<group-dir>/avalse/swapp/envs/sglang}"          # PLACEHOLDER (notes/NOVA_ENV_PLAN.md)
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"              # PLACEHOLDER; needs aiohttp numpy pandas pyyaml
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"                            # PLACEHOLDER
export HF_HOME HF_HUB_OFFLINE=1
# no telemetry from either engine or the HF client (the two engines must not differ in background network/CPU work)
export DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1 HF_HUB_DISABLE_TELEMETRY=1

# RADIX=0 for MODE=miss (prefix caching off in the engine), 1 otherwise
case "${MODE:-}" in miss) RADIX=0 ;; *) RADIX=1 ;; esac

engine_env_prefix() { echo "$ENV_SGLANG"; }     # LPM_INF=1 uses the same stock env (ENV_SGLANG_PATCHED is gone)
engine_env_dir() { engine_env_prefix; }
engine_required_vars() { echo "ENV_SGLANG HF_HOME"; }

# ---- LPM_INF=1 (cell sglang-lpminf). Every function below is a no-op (no output, status 0) when LPM_INF != 1.
lpm_inf_hook_dir() { echo "${REPO_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}/slurm/hooks/lpm_inf"; }
# CPU-only self-test, run by check_engine_flags before any GPU work: a fresh interpreter of the engine env with exactly
# the server's hook environment must import the INSTALLED schedule_policy.py (stock md5), see the constant at LPM_INF_MAX,
# load our sitecustomize (pinned md5), print the hook marker, and pick LPM at a queue of 300 (the real
# _determine_active_policy body). The same import without PM_WAITING_QUEUE_PREFIX_MATCH_MAX must give 128 and FCFS.
check_lpm_inf_hook() {
  [ "$LPM_INF" = "1" ] || return 0
  local py="$1" dir out ctl rc=0
  dir="$(lpm_inf_hook_dir)"
  echo "lpm_inf: hook dir $dir"
  [ "$POLICY" = "lpm" ] || { echo "lpm_inf FAILED: LPM_INF=1 requires POLICY=lpm (got $POLICY)"; return 1; }
  [ "$RADIX" = "1" ] || { echo "lpm_inf FAILED: LPM_INF=1 requires the radix cache (MODE=${MODE:-} disables it)"; return 1; }
  [ -z "${PYTHONPATH:-}" ] || { echo "lpm_inf FAILED: PYTHONPATH is set in the job env ('$PYTHONPATH'); the stock cells would inherit it and the hook cell would not"; return 1; }
  [ -f "$dir/sitecustomize.py" ] || { echo "lpm_inf FAILED: hook missing: $dir/sitecustomize.py"; return 1; }
  local code='
import hashlib, os, sys, types
import sitecustomize as h
import sglang.srt.managers.schedule_policy as sp
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
act = lambda n: sp.SchedulePolicy._determine_active_policy(types.SimpleNamespace(policy=sp.CacheAwarePolicy.LPM), [None] * n).value
sys.stderr.flush()
fwd = lambda p: p.replace(os.sep, "/")
print("lpm_inf_selftest value=%s md5=%s hook_md5=%s active100=%s active300=%s file=%s hook=%s" % (
    sp.WAITING_QUEUE_PREFIX_MATCH_MAX, md5(sp.__file__), md5(h.__file__), act(100), act(300), fwd(sp.__file__), fwd(h.__file__)))'
  out=$(env "PYTHONPATH=$dir" "PM_WAITING_QUEUE_PREFIX_MATCH_MAX=$LPM_INF_MAX" "$py" -c "$code" 2>&1 | grep -a -e '^\[pm-lpminf-hook\]' -e '^lpm_inf_selftest' -e 'Error')
  ctl=$(env "PYTHONPATH=$dir" "$py" -c "$code" 2>&1 | grep -a -e '^\[pm-lpminf-hook\]' -e '^lpm_inf_selftest' -e 'Error')
  echo "lpm_inf self-test (hooked):  $out"
  echo "lpm_inf self-test (control): $ctl"
  case "$out" in
    *"lpm_inf_selftest value=$LPM_INF_MAX md5=$LPM_INF_STOCK_MD5 hook_md5=$LPM_INF_HOOK_MD5 active100=lpm active300=lpm "*) ;;
    *) echo "lpm_inf FAILED: hooked import must give value=$LPM_INF_MAX md5=$LPM_INF_STOCK_MD5 hook_md5=$LPM_INF_HOOK_MD5 active300=lpm"; rc=1 ;;
  esac
  case "$out" in
    *"[pm-lpminf-hook] pid="*" 128 -> $LPM_INF_MAX file="*) ;;
    *) echo "lpm_inf FAILED: no hook marker from the hooked import"; rc=1 ;;
  esac
  case "$out" in *"file=$(engine_env_prefix)/"*) ;; *) echo "lpm_inf FAILED: schedule_policy was not imported from $(engine_env_prefix)"; rc=1 ;; esac
  case "$ctl" in
    *"pm-lpminf-hook"*) echo "lpm_inf FAILED: the hook acted without PM_WAITING_QUEUE_PREFIX_MATCH_MAX"; rc=1 ;;
    *"lpm_inf_selftest value=128 md5=$LPM_INF_STOCK_MD5 hook_md5=$LPM_INF_HOOK_MD5 active100=lpm active300=fcfs "*) ;;
    *) echo "lpm_inf FAILED: control import must give value=128 active300=fcfs"; rc=1 ;;
  esac
  [ "$rc" = "0" ] && echo "lpm_inf hook ok: $LPM_INF_MAX (stock 128), schedule_policy md5 $LPM_INF_STOCK_MD5, hook md5 $LPM_INF_HOOK_MD5"
  return "$rc"
}
# After /health: the scheduler, a spawn child of the launch_server process (pid != SERVER_PID), must have logged the
# patch. Writes every marker line to $JOB_DIR/lpm_inf_markers.txt (the manipulation check reads it). grep -o, not ^: a
# marker can follow a partial line (progress bars) written by another process to the same server.log.
engine_post_health_check() {
  [ "$LPM_INF" = "1" ] || return 0
  local markers n_child n_bad
  markers=$(grep -ao '\[pm-lpminf-hook\] pid=[0-9][0-9]* ppid=[0-9][0-9]* [^ ]* 128 -> [0-9][0-9]*' "$SERVER_LOG" || true)
  [ -n "${JOB_DIR:-}" ] && printf '%s\n' "$markers" > "$JOB_DIR/lpm_inf_markers.txt"
  n_child=$(printf '%s\n' "$markers" | awk -v sp="$SERVER_PID" -v want="$LPM_INF_MAX" \
      '$2 ~ /^pid=/ { p = substr($2, 5); if (p != sp && $NF == want) c++ } END { print c + 0 }')
  n_bad=$(printf '%s\n' "$markers" | awk -v want="$LPM_INF_MAX" '$2 ~ /^pid=/ && $NF != want { c++ } END { print c + 0 }')
  log "lpm_inf: $n_child hook marker line(s) from processes other than the server pid $SERVER_PID, $n_bad with a wrong value"
  printf '%s\n' "$markers" | head -8
  if grep -aq 'pm-lpminf-hook.*refusing' "$SERVER_LOG"; then log "lpm_inf: the hook refused to patch"; return 1; fi
  [ "$n_bad" = "0" ] && [ "$n_child" -ge 1 ]
}

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
  check_lpm_inf_hook "$py" || { echo "lpm_inf self-test FAILED: aborting (independent of STRICT_FLAGS)"; return 1; }
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
  local extra="" help kv_flag="" lpm_env=()
  help=$(cat "$JOB_DIR/engine_help.txt" 2>/dev/null || true)
  [ "$RADIX" = "0" ] && extra="--disable-radix-cache"
  [ "$KV_TOKENS" != "native" ] && kv_flag="--max-total-tokens $KV_TOKENS"     # KV_TOKENS=native: the engine sizes its own pool
  if help_has_flag "$help" --sampling-defaults; then extra="$extra --sampling-defaults openai"; fi
  if [ -n "${HF_REVISION:-}" ]; then extra="$extra --revision $HF_REVISION"; fi
  if [ "${ATTN_BACKEND:-flashinfer}" = "triton" ]; then extra="$extra --attention-backend triton --sampling-backend pytorch"; fi
  setup_jit_env
  log "launching SGLang: policy=$POLICY refresh=$REFRESH radix=$RADIX lpm_inf=$LPM_INF kv_tokens=$KV_TOKENS attn=${ATTN_BACKEND:-flashinfer} CUDA_HOME=${CUDA_HOME:-unset} extra='$extra'"
  # LPM_INF=1 only: `env PYTHONPATH=<hook dir> PM_WAITING_QUEUE_PREFIX_MATCH_MAX=1000000000` in front of python (env execs
  # python in the same pid). LPM_INF=0: the array is empty and expands to no words, so the command is the stock one.
  if [ "$LPM_INF" = "1" ]; then
    lpm_env=(env "PYTHONPATH=$(lpm_inf_hook_dir)" "PM_WAITING_QUEUE_PREFIX_MATCH_MAX=$LPM_INF_MAX")
    log "lpm_inf: server command prefixed with: ${lpm_env[*]}"
  fi
  SGLANG_ENABLE_WAITING_PREFIX_REFRESH="$REFRESH" SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 \
  ${lpm_env[@]+"${lpm_env[@]}"} "$(engine_env_prefix)/bin/python" -m sglang.launch_server \
      --model-path "$MODEL" --host 127.0.0.1 --port "$PORT" \
      --schedule-policy "$POLICY" \
      --max-running-requests 256 --chunked-prefill-size 8192 $kv_flag \
      --context-length "$CONTEXT_LEN" \
      --enable-metrics --enable-cache-report $extra \
      > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "server pid $SERVER_PID, log $SERVER_LOG"
}
