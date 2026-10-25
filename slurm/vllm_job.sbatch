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
# DRAFT -- NEVER SUBMITTED. Needs Akshat's approval; run a short test job first (MODE=smoke; see notes/VLLM_RUNBOOK.md).
# One A100-80GB: launch vLLM v0.32.0 (`vllm serve ... --enable-prefix-caching`), wait for health, run the generator,
# collect logs, run the light analysis. Same parameters as slurm/sglang_job.sbatch (POLICY/REFRESH/LPM_INF do not apply;
# vLLM v0.32.0 has FCFS only, per notes/lit/engine-sources-prefix-cache.md). Every flag, env var, endpoint and metric name
# the launcher relies on was checked against the v0.32.0 source: see the header of slurm/engine_vllm.sh and section 3 of
# notes/VLLM_RUNBOOK.md. The environment is built by slurm/setup_vllm_env.sbatch (torch 2.13.0, CUDA 13.0 wheel).
#
# Before sbatch:  env | grep ^SBATCH_   (must print nothing, or only correct values: they override the #SBATCH lines)
#                 mkdir -p logs        (logs/.gitkeep is committed, so a fresh clone has logs/)
# MODE = smoke | miss | closed | cap | burst, as in slurm/sglang_job.sbatch (N_LIST, ARMS, N_CAP/CAP_FILE, KV_TOKENS=native
# work the same way); node-class pin (--exclude) explained there.
#   sbatch --export=ALL,MODE=smoke slurm/vllm_job.sbatch
#   sbatch --export=ALL,MODE=miss,OUTPUT_FEEDBACK=server,SEEDS="0 1 2" slurm/vllm_job.sbatch             # E0a: label vllm-nocache
#   sbatch --export=ALL,MODE=closed,OUTPUT_FEEDBACK=server,N_LIST="16 20 24 32" slurm/vllm_job.sbatch      # Stage C (optional for vLLM)
#   sbatch --export=ALL,MODE=burst,OUTPUT_FEEDBACK=server,MULTS="1.35",SEEDS="0",ARMS=burst,CALIB_FILE=...,PREREG_FILE=...,ENGINE_LABEL=vllm-fcfs slurm/vllm_job.sbatch
#   (MODE=burst needs a committed PREREG_FILE whose registered cell is this ENGINE_LABEL: the registered kill-test cell is
#    SGLang FCFS; the vLLM cell uses a derived EXPLORATORY registration (python -m analysis.prereg derive-exploratory ... --arms burst)
#    built from vLLM's own E0a calibration.json; see notes/VLLM_RUNBOOK.md)
# OUTPUT_FEEDBACK (server|synthetic) is required for everything but smoke and must equal the SGLang cells' value; server is the
# REQUIRED setting (see sglang_job.sbatch). vLLM returns output ids with "return_token_ids": true (choices[0].token_ids), which the
# job sets when OUTPUT_FEEDBACK=server.
#
#  vLLM-only parameters (defaults in slurm/engine_vllm.sh):
#   ENV_VLLM      env prefix built by slurm/setup_vllm_env.sbatch (/work/classtmp/avalse/swapp/envs/vllm); ENV_GEN / HF_HOME as in the SGLang job
#   XDG_CACHE_HOME  class-storage cache root: vLLM's torch.compile cache (VLLM_CACHE_ROOT) and Triton's cache live under it
#   BLOCK_SIZE    KV block size in tokens (default 16); the pool cap is --num-gpu-blocks-override KV_TOKENS/BLOCK_SIZE
#   EXPECTED_VLLM_VERSION  default 0.32.0; the flag check refuses any other installed version
#   ENFORCE_EAGER=1  smoke-only diagnostic (no torch.compile / CUDA graphs); refused for every other MODE
#   POLICY / REFRESH / LPM_INF do not alter vLLM (FCFS only); SGLang's CUDA_HOME_SHIM / ATTN_BACKEND are not used.

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
: "${MODE:?MODE must be smoke|miss|closed|cap|burst}"
if [ -z "${ENGINE_LABEL:-}" ]; then
  if [ "$MODE" = "smoke" ]; then ENGINE_LABEL="vllm-smoke"
  elif [ "$MODE" = "miss" ]; then ENGINE_LABEL="vllm-nocache"; else ENGINE_LABEL="vllm-fcfs"; fi
  if [ "${KV_TOKENS:-}" = "native" ]; then ENGINE_LABEL="${ENGINE_LABEL}-native"; fi    # never mix pool sizes under one label
fi
: "${SEEDS:=0}"
export MODE ENGINE_LABEL SEEDS
REPO_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_vllm.sh"
job_main
