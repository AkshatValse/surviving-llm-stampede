W=/work/classtmp/avalse/swapp; R=$W/repo_h200; J=$W/h200_jobs.env
REV=a09a35458c702b33eeacc393d103063234e8bc28
SLURMOPT="--account=f2026.coms.6250.02 --partition=instruction --qos=instruction --gres=gpu:h200:1"
COMMON="ALL,ENV_GEN=$W/envs/swapp,ENV_SGLANG=$W/envs/sglang,HF_HOME=$W/hf,XDG_CACHE_HOME=$W/cache,CUDA_HOME_SHIM=$W/cuda13-home,HF_REVISION=$REV,OUTPUT_FEEDBACK=server,KV_TOKENS=300000"
PYG=$W/envs/swapp/bin/python; LAB=sglang-fcfs-r1-h200; LAB0=sglang-nocache-h200; D=2026-10-31-h200
sub() {   # sub NAME <sbatch args...>: submit from $R with the billing options, record NAME=jobid in $J and in this shell
  local name=$1 id; shift
  [ "$PWD" = "$R" ] || { echo "cd $R first"; return 1; }
  if env | grep -q '^SBATCH_'; then echo "SBATCH_* is set in this shell; unset it first"; return 1; fi
  id=$(sbatch --parsable $SLURMOPT "$@") || { echo "SUBMIT FAILED: $name"; return 1; }
  echo "$name=$id" | tee -a "$J"; eval "$name=$id"
}
outdir() { grep -m1 '"out_dir"' | sed 's/.*"out_dir": "\([^"]*\)".*/\1/'; }   # the summarize CLI prints {"out_dir": ...}
[ -f "$J" ] && . "$J"
