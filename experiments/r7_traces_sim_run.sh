#!/usr/bin/env bash
# Round-7 REAL-TRACE tool times: the stages of configs/r7_traces_sim.yaml in dependency order, then the report.
#
#   bash experiments/r7_traces_sim_run.sh [lambda_miss curves edge pairs report]     # default: all, in this order
#
# Run from a CLEAN committed tree (every meta.json records the commit and the dirty flag). At most 6 worker processes. The stages write
# results/r7_traces_sim/r7_<stage>/<timestamp>/ and append to results/r7_traces_sim/r7_robustness/manifest.tsv, a manifest of its own, so that the manifest of the
# synthetic round-7 runs (results/r7_robustness/manifest.tsv) is untouched. The driver is the one of the round-7 spec (experiments/r7_robustness_run.py).
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC=configs/r7_traces_sim.yaml
OUT=results/r7_traces_sim
PARTS="${*:-lambda_miss curves edge pairs report}"
for p in $PARTS; do
  echo "[$(date +%H:%M:%S)] START $p"
  if [ "$p" = report ]; then
    PYTHONPATH="src;." "$PY" -m prefixmeta.r7_report report --spec "$SPEC" --out-root "$OUT" || { echo "[$(date +%H:%M:%S)] FAILED $p"; exit 1; }
  else
    "$PY" experiments/r7_robustness_run.py "$p" --spec "$SPEC" --out-root "$OUT" --workers 6 || { echo "[$(date +%H:%M:%S)] FAILED $p"; exit 1; }
  fi
  echo "[$(date +%H:%M:%S)] DONE  $p"
done
echo "[$(date +%H:%M:%S)] ALL DONE parts=$PARTS"
