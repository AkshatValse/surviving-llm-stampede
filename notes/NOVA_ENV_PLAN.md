# Nova environment plan (DRAFT — not executed)

Status: drafted 2026-10-20 overnight. Nothing below has been run. Requires Akshat's approval, and the storage paths depend on the quota checks in `notes/MORNING.md`.

## Decisions
- **Where:** env and code under `/work/<group-dir>/avalse/` (fill in after `ls /work` / quota check). Not `$HOME` (small quota, conda pkgs cache bloats it). Checkpoints and large intermediates in `/ptmp`. Final results copied to `/lss` (backed up).
- **Package manager:** `micromamba` module (fast, single binary) with `pkgs_dirs` pointed at `/work` so the cache doesn't land in `$HOME`. Fallback: `miniforge3/24.3.0-0-il3e4xj`.
- **PyTorch:** pip wheels from the PyTorch index built against CUDA 12.4 (`cu124`). The wheels bundle the CUDA runtime, cuDNN, and NCCL, so no `cuda` module is needed at runtime; the node driver (reported 580.x on the A100 nodes, re-verify) supports CUDA 12.x. Load `cuda/12.4.1-cz3ljd3` only if we compile custom kernels (Triton ships its own). Not using the Spack `py-torch/2.6.0` module: we want pinned versions we control and identical package sets across nodes.
- **Python:** 3.11 (best wheel coverage on EL9 for torch 2.5–2.6).
- **Build on a compute node**, not the login node (the solve and pip install are CPU/IO heavy): a 1-CPU-GPU-free `instruction` job or `salloc` for 30 min.

## Commands (for approval; run in order)
```bash
# 0. interactive allocation on the 6250 account (no GPU needed to build)
salloc --account=f2026.coms.6250.02 --partition=instruction --qos=instruction --cpus-per-task=8 --mem=32G --time=00:45:00

# 1. on the compute node
export PROJ=/work/<group-dir>/avalse/swapp        # fill in after quota check
mkdir -p $PROJ/envs $PROJ/mamba-pkgs
module load micromamba/1.4.2-<hash>               # exact name from `module avail micromamba`
export MAMBA_ROOT_PREFIX=$PROJ/mamba-root
micromamba create -y -p $PROJ/envs/swapp -c conda-forge python=3.11 numpy scipy numba pandas pyyaml matplotlib pytest
micromamba run -p $PROJ/envs/swapp pip install --index-url https://download.pytorch.org/whl/cu124 torch==2.6.0
micromamba run -p $PROJ/envs/swapp pip freeze > $PROJ/envs/swapp.lock.txt

# 2. GPU smoke test (separate short job, see /nova-slurm skill): print torch.__version__, torch.version.cuda,
#    torch.cuda.get_device_name(), nvidia-smi, nvidia-smi topo -m, and a 4096x4096 bf16 matmul timing.
```

## Open questions
- Exact `/work` group directory and quotas (pending `df`/quota output).
- Whether `micromamba` module version works with current conda-forge repodata; if not, use miniforge3.
- Whether an inference engine (vLLM/SGLang) is needed — only if the chosen direction involves LLM serving. vLLM pins its own torch version, so it would get a separate env.
