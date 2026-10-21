#!/usr/bin/env bash
#SBATCH --job-name=pm-vllm
#SBATCH --account=f2026.coms.6250.02
#SBATCH --partition=instruction
#SBATCH --qos=instruction
#SBATCH --gres=gpu:a100:1
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
# Before sbatch:  mkdir -p logs
#   sbatch --export=ALL,MODE=miss,SEEDS="0 1 2",ENGINE_LABEL=vllm-nocache slurm/vllm_job.sbatch
#   sbatch --export=ALL,MODE=burst,MULTS="1.6",SEEDS="0",CALIB_FILE=...,ENGINE_LABEL=vllm-fcfs slurm/vllm_job.sbatch
#
#  ENV_VLLM / ENV_GEN / HF_HOME: PLACEHOLDERS (notes/NOVA_ENV_PLAN.md says vLLM needs its own env: it pins its own torch).

set -u -o pipefail
: "${MODE:?MODE must be miss|cap|burst}"
if [ -z "${ENGINE_LABEL:-}" ]; then
  if [ "$MODE" = "miss" ]; then ENGINE_LABEL="vllm-nocache"; else ENGINE_LABEL="vllm-fcfs"; fi
fi
: "${SEEDS:=0}"
export MODE ENGINE_LABEL SEEDS
REPO_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_vllm.sh"
job_main
