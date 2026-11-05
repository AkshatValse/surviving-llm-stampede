#!/usr/bin/env bash
# Round-12 driver: the blind Llama-3.1-8B predictions, both variants (V0 unchanged engine, V1 token-cost scaling) in both batching modes, every stage in dependency order,
# then the report tables.
#
#   bash experiments/r12_llama31_predict_run.sh [v0 v1]        # default: both variants, each in mixed (primary) then separate (secondary)
#
# Spec: configs/r12_llama31_predict.yaml (KV pool 300,000 tokens; real inputs and V1 factors filled in the second commit). A renamed copy of round 9's driver. B1v / B4v / B2v are the stages lambda_miss / curves / edge of the
# round-7 driver (experiments/r7_robustness_run.py), used unchanged; B3v is the stage `pairs_all` of src/prefixmeta/r12_llama31_predict.py. The --set overrides of a (variant, mode)
# are printed by `python -m prefixmeta.r12_llama31_predict v1sets` (V0 mixed: none; separate: engine.batching; V1: the three scaled cost keys at the frozen factor) and are
# recorded in every meta.json. Each (variant, mode) has its own --out-root (own manifest), so the four never mix.
# Run from a CLEAN committed tree (every meta.json records the commit and the dirty flag). At most 6 worker processes: the stages run one after the other.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC=configs/r12_llama31_predict.yaml
VARIANTS="${*:-v0 v1}"
MODES="mixed separate"
export PYTHONPATH="src;."
fail() { echo "[$(date +%H:%M:%S)] FAILED $1"; exit 1; }
for variant in $VARIANTS; do
  case "$variant" in v0|v1) ;; *) echo "unknown variant $variant"; exit 2 ;; esac
  for mode in $MODES; do
    OUT="results/r12_llama31_${variant}_${mode}"
    SETARGS=()
    SETLINES=$("$PY" -m prefixmeta.r12_llama31_predict v1sets --spec "$SPEC" --variant "$variant" --mode "$mode") || fail "$variant $mode v1sets"
    while IFS= read -r line; do
      line="${line%$'\r'}"
      if [ -n "$line" ]; then SETARGS+=(--set "$line"); fi
    done <<< "$SETLINES"
    echo "[$(date +%H:%M:%S)] $variant $mode overrides: ${SETARGS[*]-none}"
    for stage in lambda_miss curves edge; do
      echo "[$(date +%H:%M:%S)] START $variant $mode $stage"
      "$PY" experiments/r7_robustness_run.py "$stage" --spec "$SPEC" --workers 6 --out-root "$OUT" ${SETARGS[@]+"${SETARGS[@]}"} || fail "$variant $mode $stage"
      echo "[$(date +%H:%M:%S)] DONE  $variant $mode $stage"
    done
    echo "[$(date +%H:%M:%S)] START $variant $mode pairs_all"
    "$PY" -m prefixmeta.r12_llama31_predict pairs_all --spec "$SPEC" --workers 6 --out-root "$OUT" ${SETARGS[@]+"${SETARGS[@]}"} || fail "$variant $mode pairs_all"
    echo "[$(date +%H:%M:%S)] DONE  $variant $mode pairs_all"
    echo "[$(date +%H:%M:%S)] START $variant $mode r7 report"
    "$PY" -m prefixmeta.r7_report report --spec "$SPEC" --out-root "$OUT" ${SETARGS[@]+"${SETARGS[@]}"} > "$OUT/r7_report_stdout.txt" || fail "$variant $mode r7 report"
    echo "[$(date +%H:%M:%S)] DONE  $variant $mode r7 report"
  done
done
echo "[$(date +%H:%M:%S)] START r12 report"
"$PY" -m prefixmeta.r12_llama31_predict report --spec "$SPEC" > results/r12_llama31_report_stdout.txt || fail "r12 report"
echo "[$(date +%H:%M:%S)] ALL DONE variants=$VARIANTS"
