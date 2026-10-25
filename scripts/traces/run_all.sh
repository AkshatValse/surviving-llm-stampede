#!/usr/bin/env bash
# Parse -> analyse -> meta.json -> proposed workload configs, for both sources. Run from the repo root after download.sh.
#   bash scripts/traces/run_all.sh [tracelab|mini]      (default: both)
# Writes results/traces_norm/<source>/ (flat CSVs, large, ignored), results/traces_summary/<source>/ (small; force-added),
# configs/workload_trace_<source>.yaml.
set -euo pipefail
PY="${PY:-C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe}"
CFG=configs/traces_analysis.yaml
what="${1:-both}"

if [ "$what" = both ] || [ "$what" = tracelab ]; then
  "$PY" -I scripts/traces/parse_tracelab.py results/traces_raw/tracelab_v0.0.2/syfi_coding_trace.jsonl.gz results/traces_norm/tracelab
  "$PY" -I scripts/traces/analyze.py tracelab results/traces_norm/tracelab results/traces_summary/tracelab --config "$CFG"
  "$PY" -I scripts/traces/write_meta.py tracelab --config "$CFG"
  "$PY" -I scripts/traces/make_configs.py tracelab --config "$CFG"
fi

if [ "$what" = both ] || [ "$what" = mini ]; then
  "$PY" -I scripts/traces/parse_mini_swe.py results/traces_raw/mini_swe_v2 results/traces_norm/mini_swe_v2
  "$PY" -I scripts/traces/analyze.py mini results/traces_norm/mini_swe_v2 results/traces_summary/mini_swe_v2 --config "$CFG"
  "$PY" -I scripts/traces/write_meta.py mini_swe_v2 --config "$CFG"
  "$PY" -I scripts/traces/make_configs.py mini_swe_v2 --config "$CFG"
fi
