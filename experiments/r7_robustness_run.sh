#!/usr/bin/env bash
# Round-7 robustness driver: every simulation stage in dependency order, then the report.
#
#   bash experiments/r7_robustness_run.sh [lambda_miss curves edge pairs burst_sizes horizon lowlam report]     # default: all, in this order
#
# Run from a CLEAN committed tree (every meta.json records the commit and the dirty flag). At most 6 worker processes. Stages write
# results/r7_<stage>/<timestamp>/ and append to results/r7_robustness/manifest.tsv (later stages read the latest entry of the stages they depend on).
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC=configs/r7_robustness.yaml
PARTS="${*:-lambda_miss curves edge pairs burst_sizes horizon lowlam report}"
for p in $PARTS; do
  echo "[$(date +%H:%M:%S)] START $p"
  if [ "$p" = report ]; then
    PYTHONPATH="src;." "$PY" -m prefixmeta.r7_report report --spec "$SPEC" || { echo "[$(date +%H:%M:%S)] FAILED $p"; exit 1; }
  else
    "$PY" experiments/r7_robustness_run.py "$p" --spec "$SPEC" --workers 6 || { echo "[$(date +%H:%M:%S)] FAILED $p"; exit 1; }
  fi
  echo "[$(date +%H:%M:%S)] DONE  $p"
done
echo "[$(date +%H:%M:%S)] ALL DONE parts=$PARTS"
