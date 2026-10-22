#!/usr/bin/env bash
# LOCAL smoke test of the job-script glue (banner, server launch, health wait, probe, run loop, flush, post-analysis)
# against the mock server. Runs on a laptop; never touches SLURM or Nova. Usage:
#   ENV_GEN=/opt/anaconda3 slurm/local_smoke.sh MODE        (MODE = smoke | miss | closed | cap | burst; default burst)
# MODE=burst runs the three paired arms (ARMS="burst noburst capped") against a tiny fake Stage-C mu_curve.json (n_cap=3) and a fake,
# uncommitted pre-registration (slurm/local_smoke_prereg.py) that the job script validates exactly as it would on Nova.
# Writes under $RESULTS_ROOT (default: a fresh temp dir, printed at the end).
set -u -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HERE/.." && pwd)"
: "${ENV_GEN:?set ENV_GEN to a python prefix with aiohttp/numpy/pandas/pyyaml, e.g. /opt/anaconda3}"
export MODE="${1:-burst}" ENGINE_LABEL="mock-fcfs" SEEDS="${SEEDS:-0}"
export RESULTS_ROOT="${RESULTS_ROOT:-$(mktemp -d)}"
export PORT="${PORT:-18091}" GAP_S=1 HEALTH_TIMEOUT_S=30
export OUTPUT_FEEDBACK="${OUTPUT_FEEDBACK:-server}"      # the mock returns token ids when asked
export POP=4 POP_CHECK="${POP_CHECK-}" SMOKE_RUN_S=8 MISS_RUN_S=12 MISS_WARMUP_S=3 CAP_RUN_S=12 BURST_RUN_S=14 T_BURST=6 TRAP_MIN_S=3 HIT_EVAL_FROM_S=4
export N_LIST="${N_LIST:-2 4}" CLOSED_RUN_S=12 CLOSED_WARMUP_S=3 ARMS="${ARMS:-burst noburst capped}"
export REPO_DIR
# scale the workload down so a 12 s run exercises sessions, turns, cache hits and a burst
export GEN_EXTRA="--set workload.initial_context_tokens=200 --set workload.new_prompt_tokens=55 --set workload.decode_tokens=10 --set workload.mean_turns=4 --set workload.max_turns=12 --set workload.tool_time_mean_s=0.3 --set arrivals.burst.n=10 --set arrivals.burst.width_s=1 --set run.preflight_wait_s=10 --set metrics.interval_s=1"
export ANALYSIS_EXTRA="--set windows.window_s=3 --set windows.fine_window_s=1 --set burst.tail_window_s=6 --set trap_v2.min_eval_s=2 --set trap_v2.slope_dt_s=1 --set trap_v2.end_window_s=3 --set trap_v2.trace_bin_s=1"
# fake inputs standing in for the E0a calibration, the Stage-C curve (n_cap = 3), E0b and, for MODE=burst, a pre-registration filled from them
# by the real analysis.prereg code (NOT committed: PREREG_ALLOW_UNCOMMITTED=1, so no verdict of these runs can be decisive)
mkdir -p "$RESULTS_ROOT/fake_calib"
FAKE_HW="${FAKE_CALIB_HW:-Apple M3 Max CPU (simulation)}"
export MULTS="${MULTS:-1.5}"
[ "$MODE" = burst ] && [ "$MULTS" = "1.0" ] && export MULTS=1.5     # lambda must lie strictly inside the fake window (1.1, 2.7)
"$ENV_GEN/bin/python" "$HERE/local_smoke_prereg.py" --dir "$RESULTS_ROOT/fake_calib" --label "$ENGINE_LABEL" --hardware "$FAKE_HW" \
    --mult "${MULTS%% *}" --duration-s "$BURST_RUN_S" --t-burst-s "$T_BURST" $([ "$MODE" = burst ] && echo --prereg) \
    --set "trap_v2.eval_from_s=$HIT_EVAL_FROM_S" $ANALYSIS_EXTRA || { echo "fake inputs failed"; exit 1; }
export CALIB_FILE="${CALIB_FILE:-$RESULTS_ROOT/fake_calib/calibration.json}"      # pass CALIB_FILE to use a real calibration.json
export PREREG_FILE="${PREREG_FILE:-$RESULTS_ROOT/fake_calib/prereg.yaml}" PREREG_ALLOW_UNCOMMITTED=1
[ -n "${N_CAP:-}" ] || export CAP_FILE="${CAP_FILE:-$RESULTS_ROOT/fake_calib/mu_curve.json}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_mock.sh"
job_main
echo "SMOKE RESULTS: $RESULTS_ROOT"
