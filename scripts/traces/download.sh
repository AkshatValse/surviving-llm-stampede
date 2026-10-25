#!/usr/bin/env bash
# Download the two trace sources into their own directories under results/traces_raw/ (gitignored). Run from the repo root.
# The data is untrusted: it is only ever read by the parse scripts (python -I, path as argument).
#   bash scripts/traces/download.sh [tracelab|mini]      (default: both)
set -euo pipefail
PY="${PY:-C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe}"
CFG=configs/traces_analysis.yaml
what="${1:-both}"

if [ "$what" = both ] || [ "$what" = tracelab ]; then
  D=results/traces_raw/tracelab_v0.0.2
  mkdir -p "$D"
  "$PY" -I scripts/traces/fetch.py ranges \
    "https://github.com/uw-syfi/TraceLab/releases/download/v0.0.2/syfi_coding_trace.jsonl.gz" "$D/syfi_coding_trace.jsonl.gz" \
    --size 100939722 --sha256 11ce51ec0a25e3d1d95b025bca2f7d1647e47571eb7cc968acd5fc64d4b4fb65 --threads 32 --chunk-mb 1
fi

if [ "$what" = both ] || [ "$what" = mini ]; then
  L=results/traces_raw/_lists
  mkdir -p "$L" results/traces_raw/mini_swe_v2
  "$PY" -I scripts/traces/list_s3.py "$L" --config "$CFG"
  runs=$("$PY" -I -c "import yaml,sys; c=yaml.safe_load(open(sys.argv[1]))['sources']['mini_swe_v2']; print(' '.join(c['runs'])); " "$CFG")
  n=$("$PY" -I -c "import yaml,sys; c=yaml.safe_load(open(sys.argv[1]))['sources']['mini_swe_v2']; print(c['n_instances_per_run'])" "$CFG")
  seed=$("$PY" -I -c "import yaml,sys; c=yaml.safe_load(open(sys.argv[1]))['sources']['mini_swe_v2']; print(c['sample_seed'])" "$CFG")
  # shellcheck disable=SC2086
  "$PY" -I scripts/traces/make_sample_list.py "$L" "$L/mini_v2_sample.tsv" --runs $runs --n "$n" --seed "$seed"
  "$PY" -I scripts/traces/fetch.py files "$L/mini_v2_sample.tsv" results/traces_raw/mini_swe_v2 --threads 24
fi
