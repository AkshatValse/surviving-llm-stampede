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
# a gated repo and needs no token. HF_REVISION=<sha> pins the snapshot; the resolved sha is printed and appended to
# $HF_HOME/MODEL_REVISION.txt (pass the same HF_REVISION to the engine jobs so they load exactly this snapshot).
# Before sbatch:  env | grep ^SBATCH_   (must print nothing, or only correct values)
# ---- BILLING GUARD (identical in all .sbatch files; keep it before anything else) ----------------------------
# SBATCH_* variables in the submitting shell override the #SBATCH lines above, and the user's default account is a
# different allocation. Refuse to run unless the allocation really is the COMS 6250 one. Values come from
# the job environment, falling back to `scontrol show job`. Before submitting, also run:  env | grep ^SBATCH_
_ctx() {   # _ctx ENV_VAR_NAME SCONTROL_KEY
  local v; eval "v=\${$1:-}"
  if [ -z "$v" ] && [ -n "${SLURM_JOB_ID:-}" ] && command -v scontrol >/dev/null 2>&1; then
    v=$(scontrol show job "$SLURM_JOB_ID" -o 2>/dev/null | tr ' ' '\n' | sed -n "s/^$2=//p" | head -1)
  fi
  echo "$v"
}
_acct=$(_ctx SLURM_JOB_ACCOUNT Account); _part=$(_ctx SLURM_JOB_PARTITION Partition); _qos=$(_ctx SLURM_JOB_QOS QOS)
if [ "$_acct" != "f2026.coms.6250.02" ] || [ "$_part" != "instruction" ] || [ "$_qos" != "instruction" ]; then
  echo "FATAL: wrong or unknown SLURM context: account='$_acct' partition='$_part' qos='$_qos' (want f2026.coms.6250.02 / instruction / instruction). SBATCH_* in env: $(env | grep '^SBATCH_' | tr '\n' ' ')" >&2
  exit 2
fi
unset -f _ctx; unset _acct _part _qos
# ---- end billing guard ---------------------------------------------------------------------------------------

set -u -o pipefail
echo "hostname: $(hostname)  date: $(date -Is)"
: "${HF_HOME:=/work/<group-dir>/avalse/hf}"           # PLACEHOLDER
: "${ENV_GEN:=/work/<group-dir>/avalse/swapp/envs/swapp}"   # PLACEHOLDER; needs huggingface_hub (add to the env plan)
case "$HF_HOME$ENV_GEN" in *"<"*) echo "FATAL: placeholder paths not filled in"; exit 1;; esac
export HF_HOME
mkdir -p "$HF_HOME"
"$ENV_GEN/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
import os
rev = os.environ.get("HF_REVISION") or None          # pin a commit sha for the paper; unset = whatever main is today
p = snapshot_download("Qwen/Qwen2.5-7B-Instruct", revision=rev,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "merges.txt", "tokenizer*"])
print("downloaded to", p)
sha = os.path.basename(p.rstrip("/"))                  # the snapshot dir name is the commit sha
print("RESOLVED_REVISION", sha)
open(os.path.join(os.environ["HF_HOME"], "MODEL_REVISION.txt"), "a").write(f"{sha} Qwen/Qwen2.5-7B-Instruct\n")
PY
du -sh "$HF_HOME"
