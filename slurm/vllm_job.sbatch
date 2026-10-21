#!/usr/bin/env bash
#SBATCH --job-name=pm-vllm
#SBATCH --account=f2026.coms.6250.02
#SBATCH --partition=instruction
#SBATCH --qos=instruction
#SBATCH --gres=gpu:a100:1
#SBATCH --exclude=nova22-amp-7
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out
#
# DRAFT -- NEVER SUBMITTED. Needs Akshat's approval; run a short test job first (see notes/NOVA_PLAN_prefix_meta.md).
# One A100-80GB: launch vLLM v0.32.0 (`vllm serve ... --enable-prefix-caching`), wait for health, run the generator,
# collect logs, run the light analysis. Same parameters as slurm/sglang_job.sbatch (POLICY/REFRESH/LPM_INF do not apply;
# vLLM v0.32.0 has FCFS only, per notes/lit/engine-sources-prefix-cache.md).
#
# Before sbatch:  env | grep ^SBATCH_   (must print nothing, or only correct values: they override the #SBATCH lines)
#                 mkdir -p logs        (logs/.gitkeep is committed, so a fresh clone has logs/)
# MODE = smoke | miss | cap | burst, as in slurm/sglang_job.sbatch; node-class pin (--exclude) explained there.
#   sbatch --export=ALL,MODE=smoke slurm/vllm_job.sbatch
#   sbatch --export=ALL,MODE=miss,OUTPUT_FEEDBACK=server,SEEDS="0 1 2",ENGINE_LABEL=vllm-nocache slurm/vllm_job.sbatch
#   sbatch --export=ALL,MODE=burst,OUTPUT_FEEDBACK=server,MULTS="1.6",SEEDS="0",CALIB_FILE=...,ENGINE_LABEL=vllm-fcfs slurm/vllm_job.sbatch
# OUTPUT_FEEDBACK (server|synthetic) is required for miss/cap/burst and must equal the SGLang cells' value; see sglang_job.sbatch.
#
#  ENV_VLLM / ENV_GEN / HF_HOME: PLACEHOLDERS (notes/NOVA_ENV_PLAN.md says vLLM needs its own env: it pins its own torch).

# ---- BILLING GUARD (identical in all .sbatch files; keep it before anything else) ----------------------------
# SBATCH_* variables in the submitting shell override the #SBATCH lines above, and the user's default account is the
# OTHER course (f2026.coms.6720.01). Refuse to run unless the allocation really is the COMS 6250 one. Values come from
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
: "${MODE:?MODE must be smoke|miss|cap|burst}"
if [ -z "${ENGINE_LABEL:-}" ]; then
  if [ "$MODE" = "smoke" ]; then ENGINE_LABEL="vllm-smoke"
  elif [ "$MODE" = "miss" ]; then ENGINE_LABEL="vllm-nocache"; else ENGINE_LABEL="vllm-fcfs"; fi
fi
: "${SEEDS:=0}"
export MODE ENGINE_LABEL SEEDS
REPO_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_vllm.sh"
job_main
