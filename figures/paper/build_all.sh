#!/usr/bin/env bash
# Build every paper figure into paper/figs/ (vector PDFs). Run from anywhere; needs the nova-research venv.
# Usage: PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" bash figures/paper/build_all.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-python}"
export PYTHONPATH="src;."
for f in fig1_e2_timeseries fig2_thrashing_curve fig3_from_empty_stability fig4_mechanisms fig5_robustness fig6_policy_grid fig7_e2_native_timeseries fig8_10_theory; do
  "$PY" "figures/paper/$f.py"
done
