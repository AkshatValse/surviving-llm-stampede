#!/bin/bash
# H200 600k-pool registered paired test: pre-flight check-job for every (mult, arm), then 18 one-arm jobs, seed-major.
# Usage (Nova login node): bash submit_h200p600k_e2.sh M1 M2 NCAP [--dry]
set -euo pipefail
M1=$1; M2=$2; NCAP=$3; DRY=${4:-}
W=/work/classtmp/avalse/swapp; R=$W/repo_h200; J=$W/h200_jobs.env
cd $R
if env | grep -q '^SBATCH_'; then echo "SBATCH_* variables are set; refusing"; exit 1; fi
if [ -n "$(GIT_OPTIONAL_LOCKS=0 git status --porcelain --untracked-files=no)" ]; then echo "repo_h200 has tracked changes; refusing"; exit 1; fi
mkdir -p logs
REV=a09a35458c702b33eeacc393d103063234e8bc28
SLURMOPT="--account=f2026.coms.6250.02 --partition=instruction --qos=instruction --gres=gpu:h200:1"
COMMON="ALL,ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,HF_REVISION=$REV,OUTPUT_FEEDBACK=server,KV_TOKENS=600000"
LAB=sglang-fcfs-r1-h200-p600k
PRE=configs/agentload_prereg_2026-10-31_h200_p600k.yaml
CALR=prereg/inputs/2026-10-31-h200-p600k/calibration.json
PYG=$W/envs/swapp/bin/python
HW=$($PYG -c "import json,sys;print(json.load(open(sys.argv[1]))['hardware'])" "$CALR")
echo "repo_h200 HEAD $(git rev-parse HEAD) HW='$HW' PRE sha256 $(sha256sum $PRE | cut -d' ' -f1)"
for m in $M1 $M2; do for arm in burst noburst capped; do
  extra=(); [ "$arm" = capped ] && extra=(--n-cap "$NCAP")
  out=$(PYTHONPATH=src:. nice -n 19 $PYG -m analysis.prereg check-job "$PRE" --label $LAB --arms "$arm" \
        --mults "$m" --calib "$CALR" --hardware "$HW" --duration-s 8700 --t-burst-s 1200 "${extra[@]}" \
        --set "trap_v2.eval_from_s=4500" 2>&1) || { echo "$out"; echo "CHECK FAILED m=$m arm=$arm"; exit 2; }
  echo "check ok m=$m arm=$arm $(echo "$out" | grep PREREG_SHA256)"
done; done
[ "$DRY" = "--dry" ] && { echo "DRY RUN: nothing submitted"; exit 0; }
for s in 0 1 2; do for m in $M1 $M2; do for arm in burst noburst capped; do
  EXTRA=""; [ "$arm" = capped ] && EXTRA=",N_CAP=$NCAP"
  id=$(sbatch --parsable $SLURMOPT --time=03:10:00 --deadline=2026-11-01T11:40:00 --job-name=pm-e2h6 \
       --export="$COMMON,MODE=burst,POLICY=fcfs,REFRESH=1,MULTS=$m,SEEDS=$s,ARMS=$arm,CALIB_FILE=$CALR,PREREG_FILE=$PRE,ENGINE_LABEL=$LAB$EXTRA" \
       slurm/sglang_job.sbatch)
  echo "E2P6_s${s}_${m/./p}_$arm=$id" >> $J
  echo "SUBMITTED $id m=$m seed=$s arm=$arm"
done; done; done
