#!/usr/bin/env bash
#SBATCH --job-name=pm-vllm-setup
#SBATCH --account=f2026.coms.6250.02
#SBATCH --partition=instruction
#SBATCH --qos=instruction
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#
# Builds the vLLM engine env  $SWAPP_ROOT/envs/vllm  (micromamba python + pip, class storage only). DRAFT -- NEVER SUBMITTED.
# Two phases of one script, because installing needs no GPU but the import / CUDA check does:
#   PHASE=install (default)  CPU-only job exactly like slurm/setup_nova.sbatch (the header above asks for no GPU, so no GPU-hours are
#                            spent on the 20-40 minute pip install): internet check, micromamba env, pip install of the pinned vllm
#                            (its exact torch==2.13.0 pin pulls the CUDA 13.0 torch wheels from PyPI), pip check, version asserts,
#                            envs/vllm.lock.txt and envs/vllm.micromamba.yml. Idempotent: an env that already holds the pinned vllm is
#                            only re-verified.
#   PHASE=check              needs a GPU: nvidia-smi, torch.cuda, a bf16 matmul, import of vLLM's compiled kernels, the flash-attn
#                            module, and the same flag / env-var / version check that every job runs (slurm/engine_vllm.sh
#                            check_engine_flags, i.e. `vllm serve --help=all`). Override the resources on the command line:
#                              --gres=gpu:a100:1 --exclude=nova22-amp-7 --time=00:20:00
# Submit from the repo root (see notes/VLLM_RUNBOOK.md section 4, steps 1 and 2, for the exact lines):
#   sbatch --export=ALL,SWAPP_ROOT=/work/classtmp/avalse/swapp slurm/setup_vllm_env.sbatch
#   sbatch --gres=gpu:a100:1 --exclude=nova22-amp-7 --time=00:20:00 --export=ALL,SWAPP_ROOT=/work/classtmp/avalse/swapp,PHASE=check slurm/setup_vllm_env.sbatch
# Parameters: SWAPP_ROOT (required), PHASE, VLLM_SPEC (default vllm==0.32.0), VLLM_PYTHON (default 3.12), EXPECT_TORCH (2.13.0),
# EXPECT_CUDA_MAJOR (13), MICROMAMBA_MODULE. Every cache goes to class storage (home has a 10 GB quota).
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
: "${PHASE:=install}"
: "${VLLM_SPEC:=vllm==0.32.0}"
: "${VLLM_PYTHON:=3.12}"
: "${EXPECT_TORCH:=2.13.0}"
: "${EXPECT_CUDA_MAJOR:=13}"
: "${MICROMAMBA_MODULE:=micromamba/1.4.2-7jjmfkf}"
case "$VLLM_SPEC" in vllm==[0-9]*) VLLM_WANT="${VLLM_SPEC#vllm==}" ;; *) echo "FATAL: VLLM_SPEC must pin an exact version (vllm==X.Y.Z), got '$VLLM_SPEC'"; exit 2 ;; esac
ENV_VLLM="$SWAPP_ROOT/envs/vllm"
export PIP_CACHE_DIR="$SWAPP_ROOT/cache/pip" XDG_CACHE_HOME="$SWAPP_ROOT/cache" CONDA_PKGS_DIRS="$SWAPP_ROOT/mamba-pkgs"
export MAMBA_ROOT_PREFIX="$SWAPP_ROOT/mamba-root" HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1
export DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1
mkdir -p "$SWAPP_ROOT/envs" "$PIP_CACHE_DIR" "$CONDA_PKGS_DIRS" "$MAMBA_ROOT_PREFIX"
echo "hostname: $(hostname)  date: $(date -Is)  job: ${SLURM_JOB_ID:-none}  git: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "SWAPP_ROOT=$SWAPP_ROOT PHASE=$PHASE VLLM_SPEC=$VLLM_SPEC VLLM_PYTHON=$VLLM_PYTHON ENV_VLLM=$ENV_VLLM EXPECT_TORCH=$EXPECT_TORCH EXPECT_CUDA_MAJOR=$EXPECT_CUDA_MAJOR"
echo "caches: PIP_CACHE_DIR=$PIP_CACHE_DIR XDG_CACHE_HOME=$XDG_CACHE_HOME CONDA_PKGS_DIRS=$CONDA_PKGS_DIRS"

report_versions() {   # versions from package metadata (no GPU needed) and torch's CUDA build
  "$ENV_VLLM/bin/python" - <<'PY'
import importlib.metadata as m
for n in ("vllm", "torch", "torchvision", "torchaudio", "triton", "flashinfer-python", "transformers", "huggingface-hub",
          "tokenizers", "numpy", "numba", "xgrammar", "cuda-toolkit", "nvidia-cudnn-cu13", "nvidia-nccl-cu13", "nvidia-cutlass-dsl"):
    try:
        print(f"  {n}=={m.version(n)}")
    except m.PackageNotFoundError:
        print(f"  {n}: NOT INSTALLED")
import torch
print("  torch.version.cuda =", torch.version.cuda, "| torch.cuda.is_available() =", torch.cuda.is_available())
PY
}

assert_versions() {   # exit 6 unless vllm and torch are the pinned versions and torch is a CUDA-13 build
  VLLM_WANT="$VLLM_WANT" EXPECT_TORCH="$EXPECT_TORCH" EXPECT_CUDA_MAJOR="$EXPECT_CUDA_MAJOR" "$ENV_VLLM/bin/python" - <<'PY'
import importlib.metadata as m, os, sys
import torch
ok = True
v = m.version("vllm")
if v != os.environ["VLLM_WANT"]:
    print(f"FATAL: vllm {v} != {os.environ['VLLM_WANT']}"); ok = False
if not torch.__version__.startswith(os.environ["EXPECT_TORCH"]):
    print(f"FATAL: torch {torch.__version__} does not start with {os.environ['EXPECT_TORCH']}"); ok = False
if not (torch.version.cuda or "").startswith(os.environ["EXPECT_CUDA_MAJOR"] + "."):
    print(f"FATAL: torch.version.cuda={torch.version.cuda!r}, expected a CUDA {os.environ['EXPECT_CUDA_MAJOR']}.x build (the driver on Nova is 580.x)"); ok = False
print("VERSIONS_OK" if ok else "VERSIONS_BAD")
sys.exit(0 if ok else 1)
PY
}

phase_install() {
  echo "=== 1. outbound internet from the compute node (pip needs PyPI)"
  local pypi
  pypi=$(curl -sI -m 15 https://pypi.org/simple/vllm/ | head -1 | tr -d '\r')
  echo "pypi: ${pypi:-none}"
  case "$pypi" in *200*) ;; *) echo "FATAL: no outbound internet from $(hostname); build on the login node (nice) instead"; exit 3 ;; esac

  echo "=== 2. micromamba env $ENV_VLLM (python $VLLM_PYTHON)"
  if ! type module >/dev/null 2>&1; then
    local f
    for f in /etc/profile.d/lmod.sh /etc/profile.d/z00_lmod.sh /usr/share/lmod/lmod/init/bash /etc/profile.d/modules.sh; do [ -f "$f" ] && . "$f" && break; done
  fi
  module load "$MICROMAMBA_MODULE" || { echo "FATAL: module load $MICROMAMBA_MODULE failed"; exit 4; }
  command -v micromamba >/dev/null || { echo "FATAL: micromamba not on PATH after module load"; exit 4; }
  micromamba --version
  if [ ! -x "$ENV_VLLM/bin/python" ]; then
    micromamba create -y -p "$ENV_VLLM" -c conda-forge --override-channels "python=$VLLM_PYTHON" pip || { echo "FATAL: ENV_VLLM create failed"; exit 5; }
  fi
  "$ENV_VLLM/bin/python" --version

  echo "=== 3. pip install $VLLM_SPEC"
  if [ "$("$ENV_VLLM/bin/python" -c "import importlib.metadata as m; print(m.version('vllm'))" 2>/dev/null)" != "$VLLM_WANT" ]; then
    "$ENV_VLLM/bin/python" -m pip install --upgrade pip
    if ! "$ENV_VLLM/bin/python" -m pip install "$VLLM_SPEC"; then
      echo "FATAL: pip install '$VLLM_SPEC' failed; available versions:"; "$ENV_VLLM/bin/python" -m pip index versions vllm 2>&1 | head -3; exit 6
    fi
  else
    echo "vllm $VLLM_WANT already installed; re-verifying only"
  fi
  "$ENV_VLLM/bin/python" -m pip check || { echo "FATAL: pip check failed"; exit 6; }

  echo "=== 4. versions (no GPU on this node unless the job asked for one)"
  report_versions || exit 6
  assert_versions || exit 6
  "$ENV_VLLM/bin/python" -m pip freeze > "$SWAPP_ROOT/envs/vllm.lock.txt"
  micromamba env export -p "$ENV_VLLM" > "$SWAPP_ROOT/envs/vllm.micromamba.yml" 2>/dev/null || true
  echo "lock file: $SWAPP_ROOT/envs/vllm.lock.txt ($(wc -l < "$SWAPP_ROOT/envs/vllm.lock.txt") lines)"
  du -sh "$ENV_VLLM" "$SWAPP_ROOT/cache" 2>/dev/null
}

phase_check() {
  [ -x "$ENV_VLLM/bin/python" ] || { echo "FATAL: $ENV_VLLM not built; run PHASE=install first"; exit 5; }
  echo "=== nvidia-smi"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    nvidia-smi topo -m
  else
    echo "FATAL: nvidia-smi not found: PHASE=check needs a GPU (submit with --gres=gpu:a100:1, see the header)"; exit 7
  fi
  echo "=== versions"
  report_versions || exit 6
  assert_versions || exit 6
  echo "=== torch CUDA, bf16 matmul, vLLM compiled kernels and flash-attn module"
  "$ENV_VLLM/bin/python" - <<'PY' || { echo "FATAL: GPU import check failed"; exit 8; }
import importlib, time, torch
assert torch.cuda.is_available(), "torch.cuda.is_available() is False"
print("device:", torch.cuda.get_device_name(0), "capability", torch.cuda.get_device_capability(0))
x = torch.randn(4096, 4096, device="cuda", dtype=torch.bfloat16)
torch.cuda.synchronize(); t0 = time.time()
y = x @ x; torch.cuda.synchronize()
print("bf16 4096x4096 matmul ok, mean|y| =", float(y.float().abs().mean()), "in", round(time.time() - t0, 3), "s")
import vllm
print("import vllm ok:", vllm.__version__)
from vllm.platforms import current_platform
print("vllm platform:", type(current_platform).__name__, getattr(current_platform, "device_name", "?"))
for mod in ("vllm._custom_ops", "vllm.vllm_flash_attn"):
    importlib.import_module(mod); print("import ok:", mod)
PY
  echo "=== the job-time flag / env-var / version check (slurm/engine_vllm.sh check_engine_flags = vllm serve --help=all)"
  local repo="${SLURM_SUBMIT_DIR:-$PWD}"
  [ -f "$repo/slurm/common.sh" ] && [ -f "$repo/slurm/engine_vllm.sh" ] || { echo "FATAL: run from the repo root (slurm/common.sh not found in $repo)"; exit 9; }
  # shellcheck disable=SC1090
  source "$repo/slurm/common.sh"
  export ENV_VLLM STRICT_FLAGS=1 MODE=smoke
  JOB_DIR=$(mktemp -d)
  source "$repo/slurm/engine_vllm.sh"
  check_engine_flags || { echo "FATAL: check_engine_flags failed (see lines above); fix slurm/engine_vllm.sh before any vLLM job"; exit 9; }
  cp "$JOB_DIR/engine_help.txt" "$SWAPP_ROOT/envs/vllm_serve_help_${VLLM_WANT}.txt" && echo "saved: $SWAPP_ROOT/envs/vllm_serve_help_${VLLM_WANT}.txt ($(wc -l < "$JOB_DIR/engine_help.txt") lines)"
  echo "CHECK_DONE"
}

case "$PHASE" in
  install) phase_install ;;
  check)   phase_check ;;
  *) echo "FATAL: PHASE must be install|check, got '$PHASE'"; exit 2 ;;
esac
echo "SETUP_DONE $PHASE $(date -Is)"
