#!/usr/bin/env bash
# Round-6 Predict driver: every simulation call of B1-B4 (probe runner, configs/r6_predict.yaml), primary column (mixed) then secondary (separate_prefill_priority).
#
#   bash experiments/r6_predict_run.sh [b1 b2 b2s b3 b3s b4 b4s]      # default: all parts; run from the repository root (any cwd works, it cd's to the root)
#
# Each call writes a NEW results/prefix_meta_probe_<cmd>_<tag>/<timestamp>/ (meta.json: commit, dirty flag, seeds, argv, effective config) and appends
# one line  part<TAB>cmd<TAB>tag<TAB>dir  to results/r6_predict/manifest.tsv (read by `python -m prefixmeta.r6_predict report`).
# Run it from a CLEAN committed tree (meta.json records the commit and the dirty flag). Up to 6 worker processes per call.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC=configs/r6_predict.yaml
MAN=results/r6_predict/manifest.tsv
mkdir -p results/r6_predict
[ -f "$MAN" ] || printf 'part\tcmd\ttag\tdir\n' > "$MAN"

PARTS="${*:-b1 b2 b2s b3 b3s b4 b4s}"
SEEDS20='[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]'
B3_LAMBDAS="0.09 0.10 0.11 0.12 0.13 0.14 0.16"
B4_GRID='[16,24,32,48,64,96,300]'

run() {   # part cmd tag [probe args...]
  local part=$1 cmd=$2 tag=$3
  shift 3
  echo "[$(date +%H:%M:%S)] START part=$part cmd=$cmd tag=$tag args: $*"
  if ! "$PY" experiments/prefix_meta_probe_run.py "$cmd" --spec "$SPEC" --workers 6 --tag "$tag" "$@"; then
    echo "[$(date +%H:%M:%S)] FAILED tag=$tag"
    return 1
  fi
  local d
  d=$(ls -1d "results/prefix_meta_probe_${cmd}_${tag}"/*/ | sort | tail -1)
  d=${d%/}
  printf '%s\t%s\t%s\t%s\n' "$part" "$cmd" "$tag" "$d" >> "$MAN"
  echo "[$(date +%H:%M:%S)] DONE  tag=$tag dir=$d"
}

has() { case " $PARTS " in *" $1 "*) return 0;; esac; return 1; }

for entry in "mixed:mixed" "sep:separate_prefill_priority"; do
  m=${entry%%:*}
  B=${entry##*:}
  BSET="engine.batching=$B"
  if has b1; then
    run b1 curve "r6pred_b1pop32_$m" --set "$BSET"
    run b1 curve "r6pred_b1pop64_$m" --set "$BSET" --set 'probe.curve.n_grid=[64]' --set 'probe.curve.seeds=[0]'
  fi
  if has b4; then
    for kv in 300 600 900; do
      run b4 curve "r6pred_b4_kv${kv}k_$m" --set "$BSET" --set "engine.kv_memory_tokens=${kv}000" --set probe.curve.cache_enabled=true \
        --set "probe.curve.n_grid=$B4_GRID" --set 'probe.curve.seeds=[0]'
    done
  fi
  if has b4s; then
    for kv in 300 600 900; do
      run b4s curve "r6pred_b4s_kv${kv}k_$m" --set "$BSET" --set "engine.kv_memory_tokens=${kv}000" --set probe.curve.cache_enabled=true \
        --set "probe.curve.n_grid=$B4_GRID" --set 'probe.curve.seeds=[1,2,3,4]'
    done
  fi
  if has b2; then
    run b2 open "r6pred_b2_$m" --set "$BSET"
  fi
  if has b2s; then
    run b2s open "r6pred_b2s20_$m" --set "$BSET" --set "probe.open.seeds=$SEEDS20"
  fi
  if has b3; then
    for lam in $B3_LAMBDAS; do
      run b3 burst "r6pred_b3_lam${lam}_$m" --set "$BSET" --set "probe.burst.lambda=$lam"
    done
  fi
  if has b3s; then
    for lam in $B3_LAMBDAS; do
      run b3s burst "r6pred_b3s20_lam${lam}_$m" --set "$BSET" --set "probe.burst.lambda=$lam" --set "probe.burst.seeds=$SEEDS20"
    done
  fi
done
echo "[$(date +%H:%M:%S)] ALL DONE parts=$PARTS"
