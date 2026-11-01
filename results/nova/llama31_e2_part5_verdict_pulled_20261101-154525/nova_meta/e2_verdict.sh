#!/usr/bin/env bash
# Llama E2 verdict (COORD/model2/commands_corrected.sh section 9): burst2 --prereg over all 18 runs with the E2 overrides (login node, nice).
set -u
W=/work/classtmp/avalse/swapp; M2=$W/repo_llama31; cd "$M2" || exit 1
PRE=configs/agentload_prereg_2026-10-30_llama31.yaml
echo "HEAD $(git rev-parse HEAD) porcelain $(git status --porcelain | wc -l)"
JOBS=$(cat $W/submit_llama31_e2.log | tr '\n' ' '); echo "JOBS=$JOBS"
sacct -n -X -j $(echo $JOBS | tr ' ' ',') -o JobID,State%12,ExitCode,Elapsed | awk '{print $2}' | sort | uniq -c
E2DIRS=$(for j in $JOBS; do cat results/nova_job_logs/$j-*/run_dirs_burst.txt 2>/dev/null; done | tr '\n' ' ')
echo "n_dirs=$(echo $E2DIRS | wc -w)"
PYTHONPATH=src:. nice -n 19 $W/envs/swapp/bin/python -m analysis.summarize burst2 --run-dirs $E2DIRS --out-root results \
  --set burst.trap_min_s=3000 --set burst.hit_eval_from_s=4500 --set trap_v2.eval_from_s=4500 --prereg $PRE > /tmp/l31_burst2.txt 2>&1
echo "burst2 exit $?"
grep -E "out_dir|GUARD" /tmp/l31_burst2.txt | head -5
OUT=$(grep -o '"out_dir": "[^"]*agentload_analysis_burst2[^"]*"' /tmp/l31_burst2.txt | head -1 | sed -E 's/.*"(results[^"]+)"/\1/')
echo "OUT=$OUT"; ls $OUT
cat $OUT/kill_verdict_v2.json | head -120
