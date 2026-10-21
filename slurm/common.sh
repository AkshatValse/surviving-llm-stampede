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

# help_has_flag HELP_TEXT FLAG: exact-token match (so --port does not match --port-base, or a flag named inside prose)
help_has_flag() { printf '%s\n' "$1" | grep -qE -- "(^|[^[:alnum:]-])$2([^[:alnum:]-]|\$)"; }

# check_flags HELP_TEXT FLAG...: prints one line per flag; returns 1 if any is missing
check_flags() {
  local help="$1" f rc=0; shift
  for f in "$@"; do
    if help_has_flag "$help" "$f"; then echo "flag ok:      $f"; else echo "flag MISSING: $f"; rc=1; fi
  done
  return "$rc"
}

# check_envvars PKG_DIR NAME...: an env var the launcher sets must occur in the installed package source (a wrong
# name is silently ignored by the engine, which then runs without the override).
check_envvars() {
  local dir="$1" n rc=0; shift
  if [ ! -d "$dir" ]; then echo "env var check: package dir '$dir' not found"; return 1; fi
  for n in "$@"; do
    if grep -rqF --include='*.py' -- "$n" "$dir"; then echo "env var ok:      $n"; else echo "env var MISSING: $n (not found under $dir)"; rc=1; fi
  done
  return "$rc"
}

# Hooks the engine files override. Defaults: nothing to require, no engine env to record.
engine_required_vars() { :; }
engine_env_dir() { :; }

# ------------------------------------------------------------------ banner (spec: hostname, nvidia-smi, topo, git hash, seed, config)
banner() {
  echo "================ JOB BANNER ================"
  echo "date:      $(date -Is 2>/dev/null || date)"
  echo "hostname:  $(hostname)"
  echo "job:       ${SLURM_JOB_ID:-none} name=${SLURM_JOB_NAME:-none} account=${SLURM_JOB_ACCOUNT:-none} partition=${SLURM_JOB_PARTITION:-none} qos=${SLURM_JOB_QOS:-none}"
  echo "SBATCH_* input env (must be empty or correct; it overrides the #SBATCH lines): $(env | grep '^SBATCH_' | tr '\n' ' ' || true)"
  echo "node list: ${SLURM_JOB_NODELIST:-none}   gpus: ${SLURM_GPUS_ON_NODE:-none}   CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
  echo "ulimit -n: soft $(ulimit -n) hard $(ulimit -Hn)"
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
  echo "OUTPUT_FEEDBACK=$OUTPUT_FEEDBACK REQUEST_TOKEN_IDS=$REQUEST_TOKEN_IDS STRICT_FLUSH=$STRICT_FLUSH STRICT_FLAGS=${STRICT_FLAGS:-1}"
  echo "ENGINE_LABEL=$ENGINE_LABEL  CALIB_FILE=${CALIB_FILE:-}"
  echo "MODEL=${MODEL:-} SERVED_MODEL=$SERVED_MODEL HF_REVISION=${HF_REVISION:-unpinned} HF_HOME=${HF_HOME:-}"
  echo "HW=$HW"
  echo "--- configs (verbatim)"
  for f in "$REPO_DIR"/configs/agentload_e0_miss.yaml "$REPO_DIR"/configs/agentload_e0_cap.yaml \
           "$REPO_DIR"/configs/agentload_e2_burst.yaml "$REPO_DIR"/configs/agentload_analysis.yaml; do
    [ -f "$f" ] && { echo "##### $f"; cat "$f"; }
  done
  echo "============================================"
}

# Provenance of the software the numbers came from: pip freeze of the generator and engine envs, HF snapshot dir.
record_environment() {
  local e name
  for e in "$ENV_GEN" "$(engine_env_dir)"; do
    [ -n "$e" ] && [ -x "$e/bin/python" ] || continue
    name=$(basename "$e")
    "$e/bin/python" -m pip freeze > "$JOB_DIR/pip_freeze_${name}.txt" 2>&1 || echo "pip freeze failed for $e" >> "$JOB_DIR/pip_freeze_${name}.txt"
  done
  if [ -n "${HF_HOME:-}" ] && [ -n "${MODEL:-}" ]; then
    ls -1 "$HF_HOME/hub/models--$(echo "$MODEL" | sed 's#/#--#g')/snapshots" > "$JOB_DIR/hf_snapshot.txt" 2>&1 || true
  fi
}

# ------------------------------------------------------------------ ports
port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# ------------------------------------------------------------------ server lifecycle
SERVER_PID=""
GPU_MON_PID=""

wait_health() {   # wait_health URL TIMEOUT_S   (wall-clock timeout; curl is bounded; our own server pid must be alive)
  local url="$1" timeout="$2" t0 now
  t0=$(date +%s)
  while :; do
    if [ -n "$SERVER_PID" ] && ! kill -0 "$SERVER_PID" 2>/dev/null; then die "server process died during startup (see $SERVER_LOG)"; fi
    if curl -sf -m "${HEALTH_CURL_MAX_S:-10}" -o /dev/null "$url"; then
      # a foreign server on the same port could answer while ours failed to bind
      if [ -n "$SERVER_PID" ] && ! kill -0 "$SERVER_PID" 2>/dev/null; then die "health answered but our server pid $SERVER_PID is dead: a foreign process owns the port"; fi
      log "healthy: $url after $(( $(date +%s) - t0 ))s"; return 0
    fi
    now=$(date +%s)
    [ $((now - t0)) -lt "$timeout" ] || die "server not healthy after ${timeout}s: $url (see $SERVER_LOG)"
    sleep 5
  done
}

verify_served_model() {   # the server on $BASE_URL must list the model we think we are driving
  local body
  body=$(curl -sf -m "${HEALTH_CURL_MAX_S:-10}" "$BASE_URL/v1/models") || die "cannot read $BASE_URL/v1/models"
  case "$body" in
    *"\"$SERVED_MODEL\""*) log "server lists model $SERVED_MODEL" ;;
    *) die "server at $BASE_URL does not list model '$SERVED_MODEL': ${body:0:300}" ;;
  esac
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
# NOTE: an HTTP 200 is NOT proof that the cache was emptied; reset_and_verify() below checks the outcome.
flush_cache() {
  local tries=0 code
  [ -n "${FLUSH_PATH:-}" ] || { echo "$(date +%T) flush: no endpoint configured" >> "$JOB_DIR/job_events.log"; return 1; }
  while [ "$tries" -lt "${FLUSH_TRIES:-24}" ]; do
    code=$(curl -s -m "${FLUSH_CURL_MAX_S:-30}" -o /dev/null -w '%{http_code}' -X "${FLUSH_METHOD:-POST}" "$BASE_URL$FLUSH_PATH") || code=000
    if [ "$code" = "200" ]; then
      echo "$(date +%T) flush HTTP 200 ($FLUSH_PATH) after $tries retries" >> "$JOB_DIR/job_events.log"; return 0
    fi
    tries=$((tries + 1)); sleep "${FLUSH_RETRY_S:-5}"
  done
  echo "$(date +%T) flush FAILED ($FLUSH_PATH, last http $code): cache NOT emptied before next run" >> "$JOB_DIR/job_events.log"
  log "WARNING: cache flush failed; the next run does not start from an empty cache"
  [ "${STRICT_FLUSH:-1}" = "1" ] && die "STRICT_FLUSH=1 and flush failed"
  return 1
}

# ------------------------------------------------------------------ start-state verification (canary)
CANARY_N=0
START_VERIFIED=false
START_DETAIL="no reset performed yet"

canary_cli() {   # canary_cli PHASE [extra args]   (needs CANARY_SALT, CACHE_EXPECTED)
  local phase="$1"; shift
  gen_python -m agentload canary --config configs/agentload_e2_burst.yaml --phase "$phase" --salt "$CANARY_SALT" \
      --cache-expected "$CACHE_EXPECTED" --set "server.base_url=\"$BASE_URL\"" --set "server.model=\"$SERVED_MODEL\"" \
      --out "$JOB_DIR/canary_${CANARY_N}_${phase}.json" "$@"
}

# Flush the prefix cache AND check that it worked: (1) wait until the engine is idle, send a fixed canary prompt twice
# (the 2nd must hit: the cache works and holds it); (2) flush; (3) idle again, the canary must now miss. Sets
# START_VERIFIED / START_DETAIL, which the next run_gen records in its meta.json. Under STRICT_FLUSH=1 a failed check
# aborts the job: "from empty" would be unproven. With the engine's prefix caching disabled (RADIX=0) only the idle
# wait is checked.
reset_and_verify() {
  local out rc_prime=0 rc_check=0
  CANARY_N=$((CANARY_N + 1)); CANARY_SALT=$((900000 + CANARY_N)); CACHE_EXPECTED="$RADIX"
  out=$(canary_cli prime 2>&1) || rc_prime=$?
  echo "$out" >> "$JOB_DIR/canary.log"; echo "$out" | grep CANARY_RESULT | cut -c1-400
  flush_cache || true
  out=$(canary_cli check --prime-json "$JOB_DIR/canary_${CANARY_N}_prime.json" 2>&1) || rc_check=$?
  echo "$out" >> "$JOB_DIR/canary.log"; echo "$out" | grep CANARY_RESULT | cut -c1-400
  if [ "$CACHE_EXPECTED" = "1" ]; then flush_cache || true; fi      # drop the canary entry the check itself created
  START_DETAIL="canary $CANARY_N: prime rc=$rc_prime check rc=$rc_check (0 ok, 1 failed, 3 unverifiable); see canary_${CANARY_N}_*.json"
  if [ "$rc_prime" -eq 0 ] && [ "$rc_check" -eq 0 ]; then
    START_VERIFIED=true
  else
    START_VERIFIED=false
    log "WARNING: start state NOT verified: $START_DETAIL"
    [ "${STRICT_FLUSH:-1}" = "1" ] && { echo "$(date +%T) start state NOT verified: $START_DETAIL" >> "$JOB_DIR/job_events.log"; die "STRICT_FLUSH=1 and the post-flush start-state check did not pass"; }
  fi
  echo "$(date +%T) reset_and_verify: verified=$START_VERIFIED $START_DETAIL" >> "$JOB_DIR/job_events.log"
  return 0
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
RUN_IDX=0

# run_gen CONFIG NAME [extra agentload args...]   (GEN_EXTRA: optional extra '--set k=v' words; used by the local smoke test)
# Every run gets its own content salt (RUN_IDX), so a flush that silently failed cannot make its prompts hit the
# previous run's cache; arrival and spec streams (seed) are unchanged. The start-state verdict of the last
# reset_and_verify is recorded in the run's meta.json and then reset: a run is only "verified" right after a reset.
run_gen() {
  local cfg="$1" name="$2"; shift 2
  RUN_IDX=$((RUN_IDX + 1))
  log "agentload run: $cfg name=$name salt=$RUN_IDX start_verified=$START_VERIFIED $*"
  local out
  out=$(mktemp)
  gen_python -m agentload run --config "$cfg" --name "$name" --out-root "$RESULTS_ROOT" \
      --set "server.base_url=\"$BASE_URL\"" \
      --set "server.model=\"$SERVED_MODEL\"" \
      --set "server.request_token_ids=$REQUEST_TOKEN_IDS" \
      --set "workload.output_feedback=$OUTPUT_FEEDBACK" \
      --set "workload.content_salt=$RUN_IDX" \
      --set "meta.engine_label=\"$ENGINE_LABEL\"" \
      --set "meta.hardware=\"$HW\"" \
      --set "meta.start_state_verified=$START_VERIFIED" \
      --set "meta.start_state_detail=\"$START_DETAIL\"" ${GEN_EXTRA:-} "$@" 2>&1 | tee "$out"
  local rc=${PIPESTATUS[0]}
  grep '"out_dir"' "$out" | sed 's/.*"out_dir": "\(.*\)".*/\1/' >> "$JOB_DIR/run_dirs_${RUN_TAG:-$MODE}.txt"
  rm -f "$out"
  START_VERIFIED=false; START_DETAIL="no verified reset since the previous run"
  return "$rc"
}

# Quick post-hoc summaries of this job's runs (analysis is light CPU work; results go to new dirs under $RESULTS_ROOT).
post_analysis() {
  local f="$JOB_DIR/run_dirs_${MODE}.txt" dirs
  [ -s "$f" ] || { log "no run dirs recorded; skipping analysis"; return 0; }
  dirs=$(tr '\n' ' ' < "$f")
  case "$MODE" in
    smoke) gen_python -m analysis.summarize windows --run-dirs $dirs --out-root "$RESULTS_ROOT" ${ANALYSIS_EXTRA:-} ;;
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

between_runs() {   # let the server drain cancelled requests, then flush the prefix cache and verify it
  log "between runs: sleeping ${GAP_S}s then flushing cache (+ canary check)"
  sleep "$GAP_S"
  reset_and_verify
}

# ------------------------------------------------------------------ wall-time budget
# parse_slurm_time [D-]HH:MM:SS | HH:MM:SS | MM:SS -> seconds (empty for UNLIMITED / unparsable)
parse_slurm_time() {
  local t="$1" d=0 h=0 m=0 s=0 a b c
  case "$t" in ""|UNLIMITED|INVALID|NOT_SET) echo ""; return 0;; esac
  case "$t" in *-*) d=${t%%-*}; t=${t#*-};; esac
  IFS=: read -r a b c <<< "$t"
  if [ -n "${c:-}" ]; then h=$a; m=$b; s=$c; elif [ -n "${b:-}" ]; then m=$a; s=$b; else s=$a; fi
  echo $((10#$d * 86400 + 10#$h * 3600 + 10#$m * 60 + 10#$s))
}

remaining_seconds() {   # seconds left on this allocation; empty if unknown (REMAINING_S_OVERRIDE is for tests)
  if [ -n "${REMAINING_S_OVERRIDE:-}" ]; then echo "$REMAINING_S_OVERRIDE"; return 0; fi
  if [ -n "${SLURM_JOB_ID:-}" ] && command -v squeue >/dev/null 2>&1; then
    parse_slurm_time "$(squeue -h -j "$SLURM_JOB_ID" -o %L 2>/dev/null | tr -d ' ')"
  fi
}

planned_seconds() {   # runs + gaps + per-run overhead of the selected MODE (startup and margin are added by the caller)
  local ns nm total
  ns=$(echo "$SEEDS" | wc -w | tr -d ' '); nm=$(echo "${MULTS:-}" | wc -w | tr -d ' ')
  case "$MODE" in
    smoke) total=$((SMOKE_RUN_S + RUN_OVERHEAD_S)) ;;
    miss)  total=$((ns * (MISS_RUN_S + GAP_S + RUN_OVERHEAD_S)))
           if [ -n "${POP_CHECK:-}" ]; then total=$((total + MISS_RUN_S + RUN_OVERHEAD_S)); fi ;;   # popcheck: no gap after it
    cap)   total=$((ns * nm * (CAP_RUN_S + GAP_S + RUN_OVERHEAD_S))) ;;
    burst) total=$((ns * nm * (BURST_RUN_S + GAP_S + RUN_OVERHEAD_S))) ;;
    *)     total=0 ;;
  esac
  echo "$total"
}

check_time_budget() {   # check_time_budget pre|post   ("pre": before the engine starts, reserves STARTUP_ALLOW_S)
  local need rem
  need=$(( $(planned_seconds) + TIME_MARGIN_S ))
  [ "$1" = "pre" ] && need=$((need + STARTUP_ALLOW_S))
  rem=$(remaining_seconds)
  if [ -z "$rem" ]; then log "time budget ($1): remaining wall time unknown (not under SLURM); check skipped"; return 0; fi
  log "time budget ($1): need ${need}s (runs+gaps+overhead $(planned_seconds)s, margin ${TIME_MARGIN_S}s$([ "$1" = pre ] && echo ", startup ${STARTUP_ALLOW_S}s")), remaining ${rem}s"
  [ "$need" -le "$rem" ] || die "planned runs do not fit the remaining wall time ($need s > $rem s); reduce SEEDS/MULTS/run lengths or request a longer --time"
}

# ------------------------------------------------------------------ the modes (smoke, miss, cap, burst)
check_calib_hardware() {   # cap/burst must run on the hardware the calibration was measured on
  gen_python -m analysis.guards calib-hw --calib "$CALIB_FILE" --hardware "$HW" && return 0
  if [ "${ALLOW_HW_MISMATCH:-0}" = "1" ]; then log "WARNING: hardware differs from the calibration (ALLOW_HW_MISMATCH=1)"; return 0; fi
  die "this job's hardware differs from the calibration's; lambda_miss does not transfer across GPU variants"
}

mode_smoke() {  # Stage 0: engine with caching ON, closed population, one run; checks flags/probe/metrics/timing
  run_gen configs/agentload_e0_miss.yaml "agentload_s0_smoke" --seed 0 --set "arrivals.closed_n=$POP" \
      --set "run.duration_s=$SMOKE_RUN_S" || { log "smoke run failed"; FAILED_RUNS=$((FAILED_RUNS + 1)); }
}

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
  require_set CALIB_FILE; require_set MULTS
  check_calib_hardware
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
  require_set CALIB_FILE; require_set MULTS
  check_calib_hardware
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
# check_engine_flags (prints which required flags/env vars the installed engine knows; returns non-zero if STRICT_FLAGS=1
# and one is missing), engine_required_vars, engine_env_dir, HEALTH_PATH, FLUSH_PATH.
job_main() {
  REPO_DIR="${REPO_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}"
  cd "$REPO_DIR" || die "cannot cd to $REPO_DIR"
  if [ -z "${PORT:-}" ]; then          # derive a port from the job id; skip ports that are already bound (shared node)
    PORT=$((20000 + ${SLURM_JOB_ID:-$$} % 20000)); local tries=0
    while port_in_use "$PORT" && [ "$tries" -lt 50 ]; do PORT=$((PORT + 1)); tries=$((tries + 1)); done
  fi
  port_in_use "$PORT" && die "port $PORT is already in use by another process; pick another PORT"
  : "${RESULTS_ROOT:=results}"
  : "${SEEDS:=0}"
  : "${GAP_S:=180}"
  : "${POP:=32}"; : "${POP_CHECK=64}"      # POP_CHECK="" disables the population-sensitivity run
  : "${SMOKE_RUN_S:=1800}"; : "${MISS_RUN_S:=2700}"; : "${MISS_WARMUP_S:=900}"; : "${CAP_RUN_S:=3000}"; : "${BURST_RUN_S:=8700}"; : "${T_BURST:=1200}"
  : "${TRAP_MIN_S:=3000}"; : "${HIT_EVAL_FROM_S:=4500}"      # short protocol (deviation D1); simulator: 10000 / 10000
  : "${RUN_OVERHEAD_S:=150}"; : "${TIME_MARGIN_S:=600}"; : "${STARTUP_ALLOW_S:=600}"
  : "${SERVED_MODEL:=${MODEL:-Qwen/Qwen2.5-7B-Instruct}}"
  case "$MODE" in
    smoke) : "${STRICT_FLUSH:=0}" ;;       # Stage 0 exists to find out whether the check can work: report, do not abort
    *)     : "${STRICT_FLUSH:=1}" ;;
  esac
  export STRICT_FLUSH
  # Output feedback is a design choice that must be identical across compared cells (see notes/NOVA_PLAN D5): pin it.
  if [ "$MODE" = "smoke" ]; then : "${OUTPUT_FEEDBACK:=auto}"; fi
  case "${OUTPUT_FEEDBACK:-}" in
    server|synthetic) ;;
    auto) [ "$MODE" = "smoke" ] || die "OUTPUT_FEEDBACK=auto is only allowed for MODE=smoke; pin server or synthetic from the Stage-0 probe" ;;
    *) die "OUTPUT_FEEDBACK must be server|synthetic (auto only for MODE=smoke), got '${OUTPUT_FEEDBACK:-}'" ;;
  esac
  : "${REQUEST_TOKEN_IDS:=$([ "$OUTPUT_FEEDBACK" = "server" ] && echo true || echo false)}"
  BASE_URL="http://127.0.0.1:$PORT"
  TS=$(date +%Y%m%d-%H%M%S)
  JOB_DIR="$RESULTS_ROOT/nova_job_logs/${SLURM_JOB_ID:-local}-$TS"
  mkdir -p "$JOB_DIR" "$REPO_DIR/logs"
  SERVER_LOG="$JOB_DIR/server.log"
  HW="$(hardware_string)"
  export AGENTLOAD_HARDWARE="$HW"      # meta.json of analysis outputs
  require_set ENV_GEN
  local v; for v in $(engine_required_vars); do require_set "$v"; done
  trap 'stop_server' EXIT
  trap 'exit 143' TERM INT
  banner 2>&1 | tee "$JOB_DIR/banner.txt"
  record_environment
  # the check runs in this shell (not in a pipeline), so a failure really aborts the job before any GPU time is spent
  local rc=0
  check_engine_flags > "$JOB_DIR/flag_check.txt" 2>&1 || rc=$?
  cat "$JOB_DIR/flag_check.txt"
  [ "$rc" -eq 0 ] || die "engine flag/env-var check failed (STRICT_FLAGS=${STRICT_FLAGS:-1}); see $JOB_DIR/flag_check.txt"
  check_time_budget pre
  launch_engine
  wait_health "$BASE_URL$HEALTH_PATH" "${HEALTH_TIMEOUT_S:-900}"
  verify_served_model
  check_time_budget post
  start_gpu_monitor
  log "probe (raw engine response, return_token_ids test, metric names)"
  gen_python -m agentload probe --config configs/agentload_e2_burst.yaml \
      --set "server.base_url=\"$BASE_URL\"" --set "server.model=\"$SERVED_MODEL\"" 2>&1 | tee "$JOB_DIR/probe.txt" || log "probe failed (continuing)"
  reset_and_verify
  case "$MODE" in
    smoke) mode_smoke ;;
    miss)  mode_miss ;;
    cap)   mode_cap ;;
    burst) mode_burst ;;
    *) die "MODE must be smoke|miss|cap|burst, got '$MODE'" ;;
  esac
  post_analysis
  log "all runs finished ($FAILED_RUNS failed); results under $RESULTS_ROOT (job log dir $JOB_DIR)"
  [ "$FAILED_RUNS" -eq 0 ] || exit 1
}
