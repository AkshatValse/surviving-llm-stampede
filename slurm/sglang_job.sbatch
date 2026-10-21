#!/usr/bin/env bash
#SBATCH --job-name=pm-sglang
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
# One A100-80GB: launch SGLang v0.5.22, wait for health, run the generator, collect logs, run the light analysis.
#
# Before sbatch:  mkdir -p logs   (SLURM does not create the --output directory)
# Submit from the repo root, one job per (MODE, POLICY, REFRESH) cell, e.g.
#   sbatch --export=ALL,MODE=miss,SEEDS="0 1 2",ENGINE_LABEL=sglang-nocache  slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=cap,POLICY=lpm,MULTS="1.0 1.5 2.0",CALIB_FILE=results/agentload_e0_miss_summary/<ts>/calibration.json,ENGINE_LABEL=sglang-lpm slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=burst,POLICY=fcfs,REFRESH=1,MULTS="1.3",SEEDS="0",CALIB_FILE=...,ENGINE_LABEL=sglang-fcfs-r1 slurm/sglang_job.sbatch
# (the double-quoted lists above need `--export=ALL,MODE=...` quoting that suits your shell; or `export` the vars first.)
#
# ---------------------------------------------------------------- Parameters (env vars; defaults in the engine file)
#  MODE        miss | cap | burst                          (required)
#  POLICY      fcfs | lpm                                   (default fcfs)
#  REFRESH     1 | 0   SGLANG_ENABLE_WAITING_PREFIX_REFRESH (default 1 = shipped default)
#  LPM_INF     1 -> use ENV_SGLANG_PATCHED (WAITING_QUEUE_PREFIX_MATCH_MAX patched to a huge value; patch NOT applied here)
#  SEEDS       space-separated seeds                        (default "0")
#  MULTS       space-separated multiples of lambda_miss     (cap/burst)
#  CALIB_FILE  path to calibration.json from `analysis.summarize miss` (cap/burst)
#  ENGINE_LABEL  label stored in every run's meta (cell name), e.g. sglang-fcfs-r1
#  KV_TOKENS   KV pool cap in tokens (default 300000 to match the simulator's M)
#  PORT, GAP_S, POP, POP_CHECK, MISS_RUN_S, CAP_RUN_S, BURST_RUN_S, T_BURST, TRAP_MIN_S, HIT_EVAL_FROM_S, STRICT_FLAGS, STRICT_FLUSH
#  ENV_SGLANG / ENV_SGLANG_PATCHED / ENV_GEN / HF_HOME : env prefixes and cache dir (PLACEHOLDERS from notes/NOVA_ENV_PLAN.md)

set -u -o pipefail
: "${MODE:?MODE must be miss|cap|burst}"
: "${ENGINE_LABEL:=sglang-${POLICY:-fcfs}-r${REFRESH:-1}}"
: "${SEEDS:=0}"
export MODE ENGINE_LABEL SEEDS
REPO_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_sglang.sh"
job_main
