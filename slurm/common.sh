#!/usr/bin/env bash
# Shared helpers for the DRAFT Nova job scripts (slurm/sglang_job.sbatch, slurm/vllm_job.sbatch).
# DRAFT: never submitted. Sourced, not executed. Keep bash-3.2 compatible so slurm/local_smoke.sh can exercise
# the same code path on a laptop against the mock server (ENGINE=mock).
#
# Everything is driven by environment variables (see the "Parameters" block in each .sbatch).

set -u -o pipefail

# ------------------------------------------------------------------ small utilities
log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "FATAL: $*" >&2; exit 1; }

# Fail loudly if a variable still holds a "<placeholder>" (paths we cannot know until the Nova quota check).
require_set() {
  local name="$1" val
  eval "val=\${$name:-}"
  [ -n "$val" ] || die "$name is empty"
  case "$val" in *"<"*) die "$name still contains a placeholder: $val (edit the job script or export it)";; esac
}

# ------------------------------------------------------------------ banner (spec: hostname, nvidia-smi, topo, git hash, seed, config)
banner() {
  echo "================ JOB BANNER ================"
  echo "date:      $(date -Is 2>/dev/null || date)"
  echo "hostname:  $(hostname)"
  echo "job:       ${SLURM_JOB_ID:-none} name=${SLURM_JOB_NAME:-none} account=${SLURM_JOB_ACCOUNT:-none} partition=${SLURM_JOB_PARTITION:-none} qos=${SLURM_JOB_QOS:-none}"
  echo "node list: ${SLURM_JOB_NODELIST:-none}   gpus: ${SLURM_GPUS_ON_NODE:-none}   CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
  echo "--- nvidia-smi"
  if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi; else echo "nvidia-smi: not found (local smoke test?)"; fi
  echo "--- nvidia-smi topo -m"
  if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi topo -m; else echo "n/a"; fi
  echo "--- git"
  echo "commit:    $(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "branch:    $(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo "dirty:     $(git -C "$REPO_DIR" status --porcelain 2>/dev/null | wc -l | tr -d ' ') changed/untracked paths"
  echo "--- run parameters"
  echo "ENGINE=$ENGINE MODE=$MODE POLICY=${POLICY:-} REFRESH=${REFRESH:-} LPM_INF=${LPM_INF:-} RADIX=${RADIX:-}"
  echo "SEEDS=\"$SEEDS\" MULTS=\"${MULTS:-}\" KV_TOKENS=${KV_TOKENS:-} CONTEXT_LEN=${CONTEXT_LEN:-} PORT=$PORT"
  echo "ENGINE_LABEL=$ENGINE_LABEL  CALIB_FILE=${CALIB_FILE:-}"
  echo "MODEL=${MODEL:-} HF_HOME=${HF_HOME:-}"
  echo "--- configs (verbatim)"
  for f in "$REPO_DIR"/configs/agentload_e0_miss.yaml "$REPO_DIR"/configs/agentload_e0_cap.yaml \
           "$REPO_DIR"/configs/agentload_e2_burst.yaml "$REPO_DIR"/configs/agentload_analysis.yaml; do
    [ -f "$f" ] && { echo "##### $f"; cat "$f"; }
  done
  echo "============================================"
}

# ------------------------------------------------------------------ server lifecycle
SERVER_PID=""
GPU_MON_PID=""

wait_health() {   # wait_health URL TIMEOUT_S
  local url="$1" timeout="$2" t=0
  while [ "$t" -lt "$timeout" ]; do
    if curl -sf -o /dev/null "$url"; then log "healthy: $url after ${t}s"; return 0; fi
    if [ -n "$SERVER_PID" ] && ! kill -0 "$SERVER_PID" 2>/dev/null; then die "server process died during startup (see $SERVER_LOG)"; fi
    sleep 5; t=$((t + 5))
  done
  die "server not healthy after ${timeout}s: $url (see $SERVER_LOG)"
}

stop_server() {
  if [ -n "$GPU_MON_PID" ]; then kill "$GPU_MON_PID" 2>/dev/null || true; GPU_MON_PID=""; fi
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    log "stopping server pid $SERVER_PID"
    kill "$SERVER_PID" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 5; done
    kill -9 "$SERVER_PID" 2>/dev/null || true
  fi
  SERVER_PID=""
}

start_gpu_monitor() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv -l 5 > "$JOB_DIR/gpu_util.csv" 2>&1 &
    GPU_MON_PID=$!
  fi
}

# POST the engine's cache-flush endpoint (retry: engines refuse while requests are still draining).
# FLUSH_PATH / FLUSH_METHOD come from the engine file. Result is appended to $JOB_DIR/job_events.log.
flush_cache() {
  local tries=0 code
  [ -n "${FLUSH_PATH:-}" ] || { echo "$(date +%T) flush: no endpoint configured" >> "$JOB_DIR/job_events.log"; return 1; }
  while [ "$tries" -lt 24 ]; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -X "${FLUSH_METHOD:-POST}" "$BASE_URL$FLUSH_PATH" || echo 000)
    if [ "$code" = "200" ]; then
      echo "$(date +%T) flush OK ($FLUSH_PATH) after $tries retries" >> "$JOB_DIR/job_events.log"; return 0
    fi
    tries=$((tries + 1)); sleep 5
  done
  echo "$(date +%T) flush FAILED ($FLUSH_PATH, last http $code): cache NOT emptied before next run" >> "$JOB_DIR/job_events.log"
  log "WARNING: cache flush failed; the next run does not start from an empty cache"
  [ "${STRICT_FLUSH:-1}" = "1" ] && die "STRICT_FLUSH=1 and flush failed"
  return 1
}

# ------------------------------------------------------------------ generator wrappers
gen_python() { PYTHONPATH="$REPO_DIR/src:$REPO_DIR" "$ENV_GEN/bin/python" "$@"; }

hardware_string() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1 | tr -d '"'
  else
    echo "Apple M3 Max CPU (simulation)"
  fi
}

FAILED_RUNS=0

# run_gen CONFIG NAME [extra agentload args...]   (GEN_EXTRA: optional extra '--set k=v' words; used by the local smoke test)
run_gen() {
  local cfg="$1" name="$2"; shift 2
  log "agentload run: $cfg name=$name $*"
  local out
  out=$(mktemp)
  gen_python -m agentload run --config "$cfg" --name "$name" --out-root "$RESULTS_ROOT" \
      --set "server.base_url=\"$BASE_URL\"" \
      --set "meta.engine_label=\"$ENGINE_LABEL\"" \
      --set "meta.hardware=\"$HW\"" ${GEN_EXTRA:-} "$@" 2>&1 | tee "$out"
  local rc=${PIPESTATUS[0]}
  grep '"out_dir"' "$out" | sed 's/.*"out_dir": "\(.*\)".*/\1/' >> "$JOB_DIR/run_dirs_${RUN_TAG:-$MODE}.txt"
  rm -f "$out"
  return "$rc"
}

# Quick post-hoc summaries of this job's runs (analysis is light CPU work; results go to new dirs under $RESULTS_ROOT).
post_analysis() {
  local f="$JOB_DIR/run_dirs_${MODE}.txt" dirs
  [ -s "$f" ] || { log "no run dirs recorded; skipping analysis"; return 0; }
  dirs=$(tr '\n' ' ' < "$f")
  case "$MODE" in
    miss)  gen_python -m analysis.summarize miss --run-dirs $dirs --warmup-s "$MISS_WARMUP_S" \
               --out-root "$RESULTS_ROOT" ${ANALYSIS_EXTRA:-}
           if [ -s "$JOB_DIR/run_dirs_miss_popcheck.txt" ]; then
             gen_python -m analysis.summarize miss --run-dirs $(tr '\n' ' ' < "$JOB_DIR/run_dirs_miss_popcheck.txt") \
                 --warmup-s "$MISS_WARMUP_S" --out-root "$RESULTS_ROOT" --name agentload_analysis_miss_popcheck ${ANALYSIS_EXTRA:-}
           fi ;;
    cap)   gen_python -m analysis.summarize stable --run-dirs $dirs --out-root "$RESULTS_ROOT" ${ANALYSIS_EXTRA:-} ;;
    burst) gen_python -m analysis.summarize burst --run-dirs $dirs --out-root "$RESULTS_ROOT" \
               --set "burst.trap_min_s=$TRAP_MIN_S" --set "burst.hit_eval_from_s=$HIT_EVAL_FROM_S" ${ANALYSIS_EXTRA:-} ;;
  esac || log "post-analysis failed (raw results are intact)"
}

between_runs() {   # let the server drain cancelled requests, then flush the prefix cache
  log "between runs: sleeping ${GAP_S}s then flushing cache"
  sleep "$GAP_S"
  flush_cache || true
}

# ------------------------------------------------------------------ the three modes
mode_miss() {   # E0a: caching disabled server-side, closed population
  local seed
  for seed in $SEEDS; do
    run_gen configs/agentload_e0_miss.yaml "agentload_e0_miss" --seed "$seed" --set "arrivals.closed_n=$POP" \
        --set "run.duration_s=$MISS_RUN_S" || { log "run failed (seed $seed)"; FAILED_RUNS=$((FAILED_RUNS + 1)); }
    between_runs
  done
  if [ -n "${POP_CHECK:-}" ]; then   # population-sensitivity check; kept out of the calibration average (separate list)
    RUN_TAG=miss_popcheck run_gen configs/agentload_e0_miss.yaml "agentload_e0_miss_popcheck" --seed 0 \
        --set "arrivals.closed_n=$POP_CHECK" --set "run.duration_s=$MISS_RUN_S" \
        || { log "pop-check run failed"; FAILED_RUNS=$((FAILED_RUNS + 1)); }
  fi
}

mode_cap() {   # E0b: caching on, open loop from empty at several multiples of lambda_miss
  require_set CALIB_FILE
  local m seed
  for m in $MULTS; do
    for seed in $SEEDS; do
      run_gen configs/agentload_e0_cap.yaml "agentload_e0_cap" --seed "$seed" \
          --set "arrivals.rate_mult=$m" --set "arrivals.lambda_ref=\"$CALIB_FILE:lambda_miss_turns_based\"" \
          --set "run.duration_s=$CAP_RUN_S" || { log "run failed (mult $m seed $seed)"; FAILED_RUNS=$((FAILED_RUNS + 1)); }
      between_runs
    done
  done
}

mode_burst() {  # E2: caching on, burst at t_burst, several rate multiples and seeds
  require_set CALIB_FILE
  local m seed
  for m in $MULTS; do
    for seed in $SEEDS; do
      run_gen configs/agentload_e2_burst.yaml "agentload_e2_burst" --seed "$seed" \
          --set "arrivals.rate_mult=$m" --set "arrivals.lambda_ref=\"$CALIB_FILE:lambda_miss_turns_based\"" \
          --set "arrivals.burst.t_s=$T_BURST" --set "run.duration_s=$BURST_RUN_S" || { log "run failed (mult $m seed $seed)"; FAILED_RUNS=$((FAILED_RUNS + 1)); }
      between_runs
    done
  done
}

# ------------------------------------------------------------------ driver
# Expects the engine file to have defined: launch_engine (starts the server in the background, sets SERVER_PID),
# check_engine_flags (prints which required flags the installed engine knows), HEALTH_PATH, FLUSH_PATH.
job_main() {
  REPO_DIR="${REPO_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}"
  cd "$REPO_DIR" || die "cannot cd to $REPO_DIR"
  : "${PORT:=$((20000 + ${SLURM_JOB_ID:-$$} % 20000))}"
  : "${RESULTS_ROOT:=results}"
  : "${SEEDS:=0}"
  : "${GAP_S:=180}"
  : "${POP:=32}"; : "${POP_CHECK=64}"      # POP_CHECK="" disables the population-sensitivity run
  : "${MISS_RUN_S:=2700}"; : "${MISS_WARMUP_S:=900}"; : "${CAP_RUN_S:=3000}"; : "${BURST_RUN_S:=8700}"; : "${T_BURST:=1200}"
  : "${TRAP_MIN_S:=3000}"; : "${HIT_EVAL_FROM_S:=4500}"      # short protocol (deviation D1); simulator: 10000 / 10000
  BASE_URL="http://127.0.0.1:$PORT"
  TS=$(date +%Y%m%d-%H%M%S)
  JOB_DIR="$RESULTS_ROOT/nova_job_logs/${SLURM_JOB_ID:-local}-$TS"
  mkdir -p "$JOB_DIR" "$REPO_DIR/logs"
  SERVER_LOG="$JOB_DIR/server.log"
  HW="$(hardware_string)"
  export AGENTLOAD_HARDWARE="$HW"      # meta.json of analysis outputs
  require_set ENV_GEN
  trap 'stop_server' EXIT
  trap 'exit 143' TERM INT
  banner 2>&1 | tee "$JOB_DIR/banner.txt"
  check_engine_flags 2>&1 | tee "$JOB_DIR/flag_check.txt"
  launch_engine
  wait_health "$BASE_URL$HEALTH_PATH" "${HEALTH_TIMEOUT_S:-900}"
  start_gpu_monitor
  log "probe (raw engine response + metric names)"
  gen_python -m agentload probe --config configs/agentload_e2_burst.yaml \
      --set "server.base_url=\"$BASE_URL\"" 2>&1 | tee "$JOB_DIR/probe.txt" || log "probe failed (continuing)"
  flush_cache || true
  case "$MODE" in
    miss)  mode_miss ;;
    cap)   mode_cap ;;
    burst) mode_burst ;;
    *) die "MODE must be miss|cap|burst, got '$MODE'" ;;
  esac
  post_analysis
  log "all runs finished ($FAILED_RUNS failed); results under $RESULTS_ROOT (job log dir $JOB_DIR)"
  [ "$FAILED_RUNS" -eq 0 ] || exit 1
}
