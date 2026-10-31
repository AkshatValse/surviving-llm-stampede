#!/usr/bin/env bash
# Llama cell E2: 18 one-arm jobs, seed-major (COORD/model2/commands_corrected.sh section 8), with --mem=48G, --nice=54 and the lead's --deadline.
# usage on Nova: bash e2_submit.sh LM1 LM2 NCAP
set -u
LM1=$1; LM2=$2; NCAP=$3
W=/work/classtmp/avalse/swapp; M2=$W/repo_llama31; TAG=llama31; MODEL=NousResearch/Meta-Llama-3.1-8B-Instruct; REV=d10aef7999a2b5ba950ab3974312feeedbfe0b77
LBL=sglang-fcfs-r1-$TAG; PD=2026-10-30-$TAG; CAL=prereg/inputs/$PD/calibration.json; PRE=configs/agentload_prereg_2026-10-30_$TAG.yaml
cd "$M2" || exit 1
[ "$(pwd -P)" = "$(cd "$M2" && pwd -P)" ] || { echo "STOP cwd"; exit 1; }
[ -z "$(env | grep ^SBATCH_)" ] || { echo "STOP SBATCH_ set"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "STOP dirty tree"; exit 1; }
[ -f "$PRE" ] && [ -f "$CAL" ] || { echo "STOP missing $PRE or $CAL"; exit 1; }
[ ! -e "$W/submit_${TAG}_e2.log" ] || { echo "STOP $W/submit_${TAG}_e2.log exists"; exit 1; }
SB="sbatch --parsable --account=f2026.coms.6250.02 --partition=instruction --qos=instruction"
COMMON="ALL,ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,MODEL=$MODEL,HF_REVISION=$REV,OUTPUT_FEEDBACK=server,KV_TOKENS=300000"
for s in 0 1 2; do for m in $LM1 $LM2; do for arm in burst noburst capped; do
  X=""; [ $arm = capped ] && X=",N_CAP=$NCAP"
  $SB --mem=48G --nice=54 --time=03:10:00 --deadline=2026-11-01T11:40:00 --job-name=pm-l31-e2 \
      --export="$COMMON,MODE=burst,POLICY=fcfs,REFRESH=1,MULTS=$m,SEEDS=$s,ARMS=$arm,CALIB_FILE=$CAL,PREREG_FILE=$PRE,ENGINE_LABEL=$LBL$X" \
      slurm/sglang_job.sbatch
done; done; done | tee -a "$W/submit_${TAG}_e2.log"
echo "submitted $(wc -l < $W/submit_${TAG}_e2.log) jobs"
