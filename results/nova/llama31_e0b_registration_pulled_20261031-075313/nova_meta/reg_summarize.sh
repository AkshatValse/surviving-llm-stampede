#!/usr/bin/env bash
# Llama cell, step 7 of COORD/model2/commands_corrected.sh (login node, nice): model guard, combined closed curve, E0b bracket.
# Run on Nova from anywhere: bash reg_summarize.sh   (writes only git-ignored results/agentload_analysis_{closed,stable}/<ts>/ in repo_llama31)
set -u
W=/work/classtmp/avalse/swapp; M2=$W/repo_llama31; TAG=llama31; MODEL=NousResearch/Meta-Llama-3.1-8B-Instruct; LBL=sglang-fcfs-r1-$TAG
cd "$M2" || exit 1
PY="nice -n 19 $W/envs/swapp/bin/python"
CDIRS=$(cat results/nova_job_logs/{17166814,17166815,17166816}-*/run_dirs_closed.txt | tr '\n' ' ')
B_JOBS=$(sed -n 's/^E0B //p' "$W/submit_${TAG}.log" | tr '\n' ' ')
BDIRS=$(for j in $B_JOBS; do cat results/nova_job_logs/$j-*/run_dirs_cap.txt; done | tr '\n' ' ')
echo "B_JOBS=$B_JOBS"; echo "CDIRS=$CDIRS"; echo "BDIRS=$BDIRS"
echo "model guard (expect 9 ok, then 6 ok):"
for d in $CDIRS; do grep -q "^  model: $MODEL\$" $d/config_effective.yaml && echo ok || echo "BAD $d"; done | sort | uniq -c
for d in $BDIRS; do grep -q "^  model: $MODEL\$" $d/config_effective.yaml && echo ok || echo "BAD $d"; done | sort | uniq -c
PYTHONPATH=src:. $PY -m analysis.summarize closed --run-dirs $CDIRS --warmup-s 900 --primary-label $LBL --out-root results 2>&1 | tail -4
CTS=$(ls -t results/agentload_analysis_closed | head -1); echo "CTS=$CTS"
PYTHONPATH=src:. $PY -m analysis.summarize stable --run-dirs $BDIRS --out-root results 2>&1 | tail -4
STS=$(ls -t results/agentload_analysis_stable | head -1); echo "STS=$STS"
sha256sum results/agentload_analysis_closed/$CTS/mu_curve.json results/agentload_analysis_stable/$STS/lambda_cap_bracket.json results/cal_llama31/calibration.json
cat results/agentload_analysis_closed/$CTS/guards.json | head -c 400; echo; cat results/agentload_analysis_stable/$STS/guards.json | head -c 400; echo
