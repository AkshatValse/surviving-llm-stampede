#!/usr/bin/env bash
# Round-8 driver: the blind native-pool predictions, both batching modes, every stage in dependency order, then the report tables.
#
#   bash experiments/r8_native_predict_run.sh [mixed separate]        # default: both, primary first
#
# Spec: configs/r8_native_predict.yaml (KV pool 955,757 tokens). The stages are those of the round-7 driver (experiments/r7_robustness_run.py), used unchanged:
# lambda_miss, curves, edge, pairs, then burst_sizes (the 400-session SENSITIVITY at the pairs' test points, which this script reads off the edge stage with
# `python -m prefixmeta.r8_native_report points` and passes with --set r7.burst_sizes.multiples=[...], recorded in each meta.json). The secondary mode is the same
# spec with --set engine.batching=separate_prefill_priority. Each mode has its own --out-root (own manifest), so the two never mix.
# Run from a CLEAN committed tree (every meta.json records the commit and the dirty flag). At most 6 worker processes: the stages run one after the other.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC=configs/r8_native_predict.yaml
MODES="${*:-mixed separate}"
export PYTHONPATH="src;."
fail() { echo "[$(date +%H:%M:%S)] FAILED $1"; exit 1; }
for mode in $MODES; do
  case "$mode" in
    mixed)    OUT=results/r8_native_mixed;    SETS=() ;;
    separate) OUT=results/r8_native_separate; SETS=(--set engine.batching=separate_prefill_priority) ;;
    *) echo "unknown mode $mode"; exit 2 ;;
  esac
  for stage in lambda_miss curves edge pairs; do
    echo "[$(date +%H:%M:%S)] START $mode $stage"
    "$PY" experiments/r7_robustness_run.py "$stage" --spec "$SPEC" --workers 6 --out-root "$OUT" ${SETS[@]+"${SETS[@]}"} || fail "$mode $stage"
    echo "[$(date +%H:%M:%S)] DONE  $mode $stage"
  done
  PTS=$("$PY" -m prefixmeta.r8_native_report points --out-root "$OUT") || fail "$mode points"
  echo "[$(date +%H:%M:%S)] $mode B3n test points (multiples of lambda_miss): $PTS"
  if [ "$PTS" = "[]" ]; then
    echo "[$(date +%H:%M:%S)] $mode: EMPTY metastability window, the burst-size sensitivity is not run"
  else
    echo "[$(date +%H:%M:%S)] START $mode burst_sizes"
    "$PY" experiments/r7_robustness_run.py burst_sizes --spec "$SPEC" --workers 6 --out-root "$OUT" ${SETS[@]+"${SETS[@]}"} --set "r7.burst_sizes.multiples=$PTS" || fail "$mode burst_sizes"
    echo "[$(date +%H:%M:%S)] DONE  $mode burst_sizes"
  fi
  echo "[$(date +%H:%M:%S)] START $mode r7 report"
  "$PY" -m prefixmeta.r7_report report --spec "$SPEC" --out-root "$OUT" ${SETS[@]+"${SETS[@]}"} > "$OUT/r7_report_stdout.txt" || fail "$mode r7 report"
  echo "[$(date +%H:%M:%S)] DONE  $mode r7 report"
done
echo "[$(date +%H:%M:%S)] START r8 report"
"$PY" -m prefixmeta.r8_native_report report --spec "$SPEC" > results/r8_native_report_stdout.txt || fail "r8 report"
echo "[$(date +%H:%M:%S)] ALL DONE modes=$MODES"
