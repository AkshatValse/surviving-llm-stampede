#!/usr/bin/env bash
# Local stand-in for an engine: the mock server from src/agentload/mock_server.py. Used ONLY by slurm/local_smoke.sh
# to exercise the job-script glue on a laptop. Not a Nova script.

ENGINE=mock
HEALTH_PATH=/health
FLUSH_PATH=/flush_cache
FLUSH_METHOD=POST
RADIX=1

check_engine_flags() { echo "mock engine: no flags to check"; }

launch_engine() {
  log "launching mock server on port $PORT"
  PYTHONPATH="$REPO_DIR/src" "$ENV_GEN/bin/python" -m agentload.mock_server --port "$PORT" \
      --set "kv_capacity_tokens=${MOCK_KV:-20000}" --set "slots=${MOCK_SLOTS:-8}" > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
}
