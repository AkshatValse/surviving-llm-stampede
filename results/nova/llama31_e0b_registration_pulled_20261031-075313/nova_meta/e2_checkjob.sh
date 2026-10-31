#!/usr/bin/env bash
# Llama cell: check-job for every (lambda, arm) of the registration (COORD/model2/commands_corrected.sh section 7, last loop). Read-only.
# usage on Nova: bash e2_checkjob.sh LM1 LM2 NCAP
set -u
LM1=$1; LM2=$2; NCAP=$3
W=/work/classtmp/avalse/swapp; M2=$W/repo_llama31; TAG=llama31; LBL=sglang-fcfs-r1-$TAG; HW="NVIDIA A100 80GB PCIe, 81920 MiB"
PD=2026-10-30-$TAG; CAL=prereg/inputs/$PD/calibration.json; PRE=configs/agentload_prereg_2026-10-30_$TAG.yaml
cd "$M2" || exit 1
PY="nice -n 19 $W/envs/swapp/bin/python"
echo "HEAD $(git rev-parse HEAD) porcelain $(git status --porcelain | wc -l)"; git log -1 --format="%H %cd" --date=iso -- "$PRE"
rc=0
for m in $LM1 $LM2; do for arm in burst noburst capped; do
  X=""; [ $arm = capped ] && X="--n-cap $NCAP"
  echo "== $m $arm"
  PYTHONPATH=src:. $PY -m analysis.prereg check-job $PRE --label $LBL --mults "$m" --arms "$arm" $X \
    --calib $CAL --hardware "$HW" --duration-s 8700 --t-burst-s 1200 --set trap_v2.eval_from_s=4500 | tail -2
  r=${PIPESTATUS[0]}; [ $r -ne 0 ] && { echo "CHECK_FAIL $m $arm rc=$r"; rc=1; }
done; done
echo "CHECKJOB_RC=$rc"
