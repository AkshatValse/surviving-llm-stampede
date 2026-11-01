#!/usr/bin/env bash
# Llama E2: pack finished jobs read-only into $W/pull_tmp/<name>.tar.xz (job .out logs, job log dirs, run dirs, per-job analysis dirs).
# usage on Nova: bash e2_pack.sh <name> <jobid> [<jobid> ...]  -> prints sha256 and path
set -eu
NAME=$1; shift
W=/work/classtmp/avalse/swapp; M2=$W/repo_llama31; cd "$M2"
mkdir -p $W/pull_tmp; L=$W/pull_tmp/$NAME.list; : > $L
for j in "$@"; do
  st=$(sacct -n -X -j $j -o State%14 | tr -d ' ')
  [ "$st" = COMPLETED ] || { echo "SKIP $j state=$st"; continue; }
  ls logs/pm-l31-e2-$j.out >> $L
  ls -d results/nova_job_logs/$j-* >> $L
  cat results/nova_job_logs/$j-*/run_dirs_burst.txt >> $L
  grep -h "\"out_dir\": \"results/agentload_analysis_burst" logs/pm-l31-e2-$j.out | sed -E 's/.*"(results[^"]+)".*/\1/' >> $L
done
sort -u -o $L $L
for p in $(cat $L); do [ -e "$p" ] || { echo "MISSING $p"; exit 1; }; done
echo "entries: $(wc -l < $L)"
nice -n 19 tar -cf $W/pull_tmp/$NAME.tar -T $L
nice -n 19 xz -T2 -6 -f $W/pull_tmp/$NAME.tar
ls -la $W/pull_tmp/$NAME.tar.xz; sha256sum $W/pull_tmp/$NAME.tar.xz
