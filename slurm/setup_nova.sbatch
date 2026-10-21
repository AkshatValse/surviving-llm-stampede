#!/usr/bin/env bash
#SBATCH --job-name=pm-setup
#SBATCH --account=f2026.coms.6250.02
#SBATCH --partition=instruction
#SBATCH --qos=instruction
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#
# CPU-only setup job (no GPU): steps B and C of notes/STAGE0_RUNBOOK.md in one non-interactive job.
#   1. check outbound internet from the compute node (pip and the HF hub need it); exit 3 if absent
#   2. build the generator env (ENV_GEN) and the SGLang env (ENV_SGLANG) with micromamba + pip, into class storage
#   3. download Qwen/Qwen2.5-7B-Instruct into HF_HOME and print RESOLVED_REVISION <sha>
# Every cache goes to class storage (home has a 10 GB quota).
# Submit from the repo root:
#   sbatch --export=ALL,SWAPP_ROOT=/work/classtmp/avalse/swapp slurm/setup_nova.sbatch
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
: "${SWAPP_ROOT:?set SWAPP_ROOT, e.g. /work/classtmp/avalse/swapp}"
: "${SGLANG_SPEC:=sglang[all]==0.5.22}"
: "${MICROMAMBA_MODULE:=micromamba/1.4.2-7jjmfkf}"
: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
ENV_GEN="$SWAPP_ROOT/envs/swapp"; ENV_SGLANG="$SWAPP_ROOT/envs/sglang"; HF_HOME="$SWAPP_ROOT/hf"
export PIP_CACHE_DIR="$SWAPP_ROOT/cache/pip" XDG_CACHE_HOME="$SWAPP_ROOT/cache" CONDA_PKGS_DIRS="$SWAPP_ROOT/mamba-pkgs"
export MAMBA_ROOT_PREFIX="$SWAPP_ROOT/mamba-root" HF_HOME HF_HUB_DISABLE_TELEMETRY=1
mkdir -p "$SWAPP_ROOT/envs" "$PIP_CACHE_DIR" "$CONDA_PKGS_DIRS" "$MAMBA_ROOT_PREFIX" "$HF_HOME"
echo "hostname: $(hostname)  date: $(date -Is)  job: ${SLURM_JOB_ID:-none}  git: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "SWAPP_ROOT=$SWAPP_ROOT SGLANG_SPEC=$SGLANG_SPEC MODEL=$MODEL HF_REVISION=${HF_REVISION:-unpinned}"

echo "=== 1. outbound internet from the compute node"
pypi=$(curl -sI -m 15 https://pypi.org/simple/sglang/ | head -1 | tr -d '\r'); hf=$(curl -sI -m 15 https://huggingface.co | head -1 | tr -d '\r')
echo "pypi: ${pypi:-none}   huggingface: ${hf:-none}"
case "$pypi$hf" in *200*200*) ;; *) echo "FATAL: no outbound internet from $(hostname); build on the login node instead"; exit 3;; esac

echo "=== 2. envs"
if ! type module >/dev/null 2>&1; then
  for f in /etc/profile.d/lmod.sh /etc/profile.d/z00_lmod.sh /usr/share/lmod/lmod/init/bash /etc/profile.d/modules.sh; do [ -f "$f" ] && . "$f" && break; done
fi
module load "$MICROMAMBA_MODULE" || { echo "FATAL: module load $MICROMAMBA_MODULE failed"; exit 4; }
command -v micromamba >/dev/null || { echo "FATAL: micromamba not on PATH after module load"; exit 4; }
micromamba --version
if [ ! -x "$ENV_GEN/bin/python" ]; then
  micromamba create -y -p "$ENV_GEN" -c conda-forge --override-channels python=3.11 numpy pandas pyyaml aiohttp huggingface_hub pytest || { echo "FATAL: ENV_GEN create failed"; exit 5; }
fi
"$ENV_GEN/bin/python" -c "import aiohttp, numpy, pandas, yaml, huggingface_hub; print('ENV_GEN ok', aiohttp.__version__, numpy.__version__, pandas.__version__, huggingface_hub.__version__)" || exit 5
if [ ! -x "$ENV_SGLANG/bin/python" ]; then
  micromamba create -y -p "$ENV_SGLANG" -c conda-forge --override-channels python=3.11 pip || { echo "FATAL: ENV_SGLANG create failed"; exit 6; }
fi
if ! "$ENV_SGLANG/bin/python" -c "import sglang" 2>/dev/null; then
  "$ENV_SGLANG/bin/python" -m pip install --upgrade pip
  if ! "$ENV_SGLANG/bin/python" -m pip install "$SGLANG_SPEC"; then
    echo "FATAL: pip install '$SGLANG_SPEC' failed; available versions:"; "$ENV_SGLANG/bin/python" -m pip index versions sglang 2>&1 | head -3; exit 6
  fi
fi
"$ENV_SGLANG/bin/python" -c "import sglang, torch; print('sglang', sglang.__version__, 'torch', torch.__version__, 'cuda build', torch.version.cuda)" || exit 6
# FlashInfer JIT needs every compiler-side CUDA wheel at torch's runtime major.minor. The [all] extra resolved nvcc, nvvm and
# crt to 13.4 and cccl to 13.3 against runtime 13.0.96, which fails with "CUDA compiler and CUDA toolkit headers are
# incompatible" and then "ptxas: Unsupported .version 9.4" (Nova job 17060085). Pin them to the runtime's major.minor.
cuda_mm=$("$ENV_SGLANG/bin/python" -c "import importlib.metadata as m; v=m.version('nvidia-cuda-runtime').split('.'); print(v[0]+'.'+v[1])")
"$ENV_SGLANG/bin/python" -m pip install "nvidia-cuda-nvcc==${cuda_mm}.*" "nvidia-nvvm==${cuda_mm}.*" "nvidia-cuda-crt==${cuda_mm}.*" "nvidia-cuda-cccl==${cuda_mm}.*" || exit 6
"$ENV_SGLANG/bin/python" -m pip check || exit 6
bash "$(dirname "$0")/make_cuda_shim.sh" "$ENV_SGLANG" "$SWAPP_ROOT/cuda13-home" || exit 6
"$ENV_SGLANG/bin/python" -m pip freeze > "$SWAPP_ROOT/envs/sglang.lock.txt"
"$ENV_GEN/bin/python" -m pip freeze > "$SWAPP_ROOT/envs/swapp.lock.txt"
micromamba env export -p "$ENV_GEN" > "$SWAPP_ROOT/envs/swapp.micromamba.yml" 2>/dev/null || true

echo "=== 3. model download -> $HF_HOME"
MODEL="$MODEL" "$ENV_GEN/bin/python" - <<'PY' || { echo "FATAL: model download failed"; exit 7; }
from huggingface_hub import snapshot_download
import os
rev = os.environ.get("HF_REVISION") or None
p = snapshot_download(os.environ["MODEL"], revision=rev,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "merges.txt", "tokenizer*"])
print("downloaded to", p)
sha = os.path.basename(p.rstrip("/"))
print("RESOLVED_REVISION", sha)
open(os.path.join(os.environ["HF_HOME"], "MODEL_REVISION.txt"), "a").write(f"{sha} {os.environ['MODEL']}\n")
PY
du -sh "$HF_HOME" "$ENV_GEN" "$ENV_SGLANG" "$SWAPP_ROOT/cache" 2>/dev/null
echo "SETUP_DONE $(date -Is)"
