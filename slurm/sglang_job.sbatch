#!/usr/bin/env bash
#SBATCH --job-name=pm-sglang
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
# One A100-80GB: launch SGLang v0.5.22, wait for health, run the generator, collect logs, run the light analysis.
#
# Before sbatch:  env | grep ^SBATCH_   (must print nothing, or only correct values: they override the #SBATCH lines)
#                 mkdir -p logs        (logs/.gitkeep is committed, so a fresh clone has logs/)
# Node class: --exclude=nova22-amp-7 keeps every calibration and burst job on nova22-gpu-[1-3] (A100 80GB PCIe per earlier
# nvidia-smi logs); `gpu:a100` alone also matches nova22-amp-7, whose GPU model is unverified. Drop the exclude only after
# Stage 0 shows both classes report the same `nvidia-smi` name and memory. calibration.json records the hardware string and
# the cap/burst modes refuse to run on a different one (ALLOW_HW_MISMATCH=1 overrides).
# Submit from the repo root, one job per (MODE, POLICY, REFRESH) cell, e.g.
#   sbatch --export=ALL,MODE=smoke slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=miss,OUTPUT_FEEDBACK=server,SEEDS="0 1 2",ENGINE_LABEL=sglang-nocache  slurm/sglang_job.sbatch
#   Stage C (closed-population mu(n), cache ON; the n grid is split over jobs so each fits 4 h; budget: <= 4 runs per job;
#   n = 20 is on the grid because the sharp peak of mu(n) sits near n = 20-24 in the simulator):
#   sbatch --export=ALL,MODE=closed,OUTPUT_FEEDBACK=server,POLICY=fcfs,N_LIST="16 20 24 32" slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=closed,OUTPUT_FEEDBACK=server,POLICY=fcfs,N_LIST="48 96 300" slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=closed,OUTPUT_FEEDBACK=server,POLICY=lpm,N_LIST="48 300" slurm/sglang_job.sbatch
#   E0b (REQUIRED: bounds the pre-registered window from above) must run under the REGISTERED cell, i.e. POLICY=fcfs REFRESH=1
#   (label sglang-fcfs-r1); an LPM bracket says nothing about the FCFS no-burst arm:
#   sbatch --export=ALL,MODE=cap,OUTPUT_FEEDBACK=server,POLICY=fcfs,REFRESH=1,MULTS="1.0 1.5 2.0",CALIB_FILE=results/agentload_analysis_miss/<ts>/calibration.json slurm/sglang_job.sbatch
#   E2, one ARM per job (an arm is one 8700 s run; ARMS defaults to all three, which the wall-time check refuses in a 4 h job):
#   (MODE=burst REFUSES to start unless PREREG_FILE is a valid, COMMITTED, clean pre-registration whose label, MULTS, n_cap,
#   reference rates (CALIB_FILE) and hardware are this job's; its sha256 is written into every run's meta.json)
#   sbatch --export=ALL,MODE=burst,OUTPUT_FEEDBACK=server,POLICY=fcfs,REFRESH=1,MULTS="1.3",SEEDS="0",ARMS=burst,CALIB_FILE=...,PREREG_FILE=configs/agentload_prereg_<date>.yaml,ENGINE_LABEL=sglang-fcfs-r1 slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=burst,...,ARMS=noburst,... slurm/sglang_job.sbatch
#   sbatch --export=ALL,MODE=burst,...,ARMS=capped,CAP_FILE=results/agentload_analysis_closed/<ts>/mu_curve.json,... slurm/sglang_job.sbatch
# (the double-quoted lists above need `--export=ALL,MODE=...` quoting that suits your shell; or `export` the vars first.)
#
# ---------------------------------------------------------------- Parameters (env vars; defaults in the engine file)
#  MODE        smoke | miss | closed | cap | burst         (required; smoke = Stage-0 test job, cache ON, one closed run;
#              closed = Stage C, cache ON, one closed-population run per n in N_LIST)
#  POLICY      fcfs | lpm                                   (default fcfs)
#  REFRESH     1 | 0   SGLANG_ENABLE_WAITING_PREFIX_REFRESH (default 1 = shipped default)
#  LPM_INF     1 -> use ENV_SGLANG_PATCHED (WAITING_QUEUE_PREFIX_MATCH_MAX patched to a huge value; patch NOT applied here)
#  SEEDS       space-separated seeds                        (default "0")
#  MULTS       space-separated multiples of lambda_miss     (cap/burst)
#  N_LIST      space-separated closed populations n         (closed; REQUIRED, no default)
#  ARMS        space-separated subset of "burst noburst capped" (burst; default all three, run in that order for each mult, seed).
#              noburst = same plan without the burst sessions; capped = burst + client-side FIFO session cap.
#  N_CAP / CAP_FILE  (capped arm) the session cap: an integer, or the Stage-C mu_curve.json whose n_cap (argmax mu(n) of the FCFS
#              cell) is used; one of them is REQUIRED when ARMS contains capped, validated before the engine starts. A CAP_FILE is
#              refused unless its primary_label equals ENGINE_LABEL and its hardware is this job's (summarise the 300k and the
#              native pool separately: `summarize closed --primary-label LABEL`); with the PREREG_FILE the cap must equal the registered one
#  CLOSED_RUN_S, CLOSED_WARMUP_S  (closed) run length 2700 s and the 900 s discarded by the post-analysis
#  CALIB_FILE  path to calibration.json from `analysis.summarize miss` (cap/burst)
#  PREREG_FILE (burst; REQUIRED) the filled pre-registration committed BEFORE the first E2 job (analysis.prereg fill; see the plan).
#              PREREG_ALLOW_UNCOMMITTED=1 is for the local smoke test only (the runs' verdict can then never be decisive)
#  ENGINE_LABEL  label stored in every run's meta (cell name), e.g. sglang-fcfs-r1
#  KV_TOKENS   KV pool cap in tokens (default 300000 to match the simulator's M); KV_TOKENS=native drops the cap (the engine's own
#              pool, ~1M tokens: REQUIRED native-pool lambda, see the plan) and appends -native to the default ENGINE_LABEL
#  OUTPUT_FEEDBACK  server | synthetic  (REQUIRED for everything but smoke, which defaults to auto; server is the REQUIRED setting: real output token ids). Pin the SAME value for every cell that
#              will be compared and for both engines (decide from the Stage-0 probe: PROBE_SUMMARY.output_ids_present).
#              synthetic means every hit turn prefills Delta+d = 650 uncached tokens, not the simulator's Delta = 550 (plan D5).
#  REQUEST_TOKEN_IDS  true|false -> server.request_token_ids (default true iff OUTPUT_FEEDBACK=server)
#  HF_REVISION  optional commit sha: passed to the engine as --revision (use the sha printed by download_model.sbatch)
#  ALLOW_HW_MISMATCH=1  let cap/burst run on hardware different from the calibration's (default: refuse)
#  PORT, GAP_S, POP, POP_CHECK, MISS_RUN_S, CAP_RUN_S, BURST_RUN_S, T_BURST, TRAP_MIN_S, HIT_EVAL_FROM_S, STRICT_FLAGS,
#  STRICT_FLUSH (default 1; 0 for smoke), RUN_OVERHEAD_S, TIME_MARGIN_S, STARTUP_ALLOW_S (wall-time budget check)
#  ENV_SGLANG / ENV_SGLANG_PATCHED / ENV_GEN / HF_HOME : env prefixes and cache dir (PLACEHOLDERS from notes/NOVA_ENV_PLAN.md)

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
  if [ "$MODE" = "smoke" ]; then ENGINE_LABEL="sglang-smoke"
  elif [ "$MODE" = "miss" ]; then ENGINE_LABEL="sglang-nocache"
  elif [ "${LPM_INF:-0}" = "1" ]; then ENGINE_LABEL="sglang-lpminf"
  else ENGINE_LABEL="sglang-${POLICY:-fcfs}-r${REFRESH:-1}"; fi
  if [ "${KV_TOKENS:-}" = "native" ]; then ENGINE_LABEL="${ENGINE_LABEL}-native"; fi    # never mix pool sizes under one label
fi
: "${SEEDS:=0}"
export MODE ENGINE_LABEL SEEDS
REPO_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
source "$REPO_DIR/slurm/common.sh"
source "$REPO_DIR/slurm/engine_sglang.sh"
job_main
