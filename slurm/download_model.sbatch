#!/usr/bin/env bash
#SBATCH --job-name=pm-download
#SBATCH --account=f2026.coms.6250.02
#SBATCH --partition=instruction
#SBATCH --qos=instruction
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%j.out
#
# DRAFT -- NEVER SUBMITTED. CPU-only job (no GPU). Downloads Qwen2.5-7B-Instruct (Apache-2.0, ungated; ~15 GB of
# bf16 safetensors) into HF_HOME on /work or /ptmp. Assumes compute nodes can reach huggingface.co (UNVERIFIED on Nova;
# if not, download on a login node with a rate limit, or on a machine with network and rsync). The job never touches
# a gated repo and needs no token.
set -u -o pipefail
echo "hostname: $(hostname)  date: $(date -Is)"
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"           # PLACEHOLDER
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"   # PLACEHOLDER; needs huggingface_hub (add to the env plan)
case "$HF_HOME$ENV_GEN" in *"<"*) echo "FATAL: placeholder paths not filled in"; exit 1;; esac
export HF_HOME
mkdir -p "$HF_HOME"
"$ENV_GEN/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen2.5-7B-Instruct", allow_patterns=["*.json", "*.safetensors", "*.txt", "merges.txt", "tokenizer*"])
print("downloaded to", p)
PY
du -sh "$HF_HOME"
