#!/usr/bin/env bash
set -euo pipefail
[ "${SLURM_JOB_ACCOUNT:-}" = "f2026.coms.6250.02" ] || { echo "FATAL: wrong account"; exit 2; }
cd "$M2"; echo "hostname $(hostname) $(date -Is) commit $(git rev-parse HEAD)"
dirs=""; for j in $E0A_JOBS; do f=$(ls results/nova_job_logs/${j}-*/run_dirs_miss.txt); dirs="$dirs $(tr '\n' ' ' < "$f")"; done
echo "E0a run dirs:$dirs"
"$ENV_GEN/bin/python" - "$DL_MODEL" $dirs <<'PY'
import sys, yaml                                  # FIX 10: model guard (the analysis guards check label + hardware only)
m = sys.argv[1]
for d in sys.argv[2:]:
    got = yaml.safe_load(open(f"{d}/config_effective.yaml"))["server"]["model"]
    assert got == m, (d, got)
print("MODEL_OK", m, len(sys.argv) - 2, "runs")
PY
PYTHONPATH=src:. "$ENV_GEN/bin/python" -m analysis.summarize miss --run-dirs $dirs --warmup-s 900 --out-root "results/cal_$TAG"
c=$(ls -d results/cal_$TAG/agentload_analysis_miss/*/calibration.json | tail -1)
"$ENV_GEN/bin/python" - "$c" "$TAG" <<'PY'
import json, sys
c = json.load(open(sys.argv[1])); tag = sys.argv[2]
assert c["n_runs"] == 3, c["n_runs"]
assert c["hardware"] == "NVIDIA A100 80GB PCIe, 81920 MiB", c["hardware"]
assert c["labels"] == [f"sglang-nocache-{tag}"], c["labels"]
assert c["all_miss_cached_frac_tokens_max"] == 0.0, c["all_miss_cached_frac_tokens_max"]
assert 0.01 < c["lambda_miss_turns_based"] < 0.2, c["lambda_miss_turns_based"]
print("CALIB_OK", {k: c[k] for k in ("lambda_miss_turns_based", "lambda_miss_turns_based_se", "all_miss_uncached_tokens_per_s")})
PY
cp "$c" "results/cal_$TAG/calibration.json"       # FIX 4: git-ignored (results/*); copied into prereg/inputs only at registration
echo "CALIB_FILE=results/cal_$TAG/calibration.json  (source $c)"
