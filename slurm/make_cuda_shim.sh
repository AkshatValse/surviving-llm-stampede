#!/usr/bin/env bash
# Build a CUDA_HOME shim (symlinks only) over the pip CUDA toolkit inside an engine env, in the layout FlashInfer's JIT
# expects: $CUDA_HOME/{bin,include,nvvm,...} and $CUDA_HOME/lib64/{libcudart.so, stubs/libcuda.so}. FlashInfer links with
# "-L$cuda_home/lib64 -L$cuda_home/lib64/stubs -lcudart -lcuda"; the pip toolkit ships lib/ (not lib64/), only versioned
# .so names and no libcuda stub (found on Nova job 17060022). libcuda.so points at the node's driver library, so the link
# step can only succeed on a GPU node (the job script checks that before launching). Cheap, idempotent, no compilation.
# Usage:  slurm/make_cuda_shim.sh ENGINE_ENV_PREFIX SHIM_DIR
set -eu
env_prefix="${1:?engine env prefix}"; shim="${2:?shim dir}"
py="$env_prefix/bin/python"
toolkit=$("$py" - <<'PY'
import glob, os, site
for sp in site.getsitepackages():
    for cand in sorted(glob.glob(os.path.join(sp, "nvidia", "cu*"))):
        if os.path.isfile(os.path.join(cand, "bin", "nvcc")):
            print(cand); raise SystemExit
raise SystemExit("no pip CUDA toolkit with bin/nvcc found under site-packages/nvidia/cu*")
PY
)
echo "pip CUDA toolkit: $toolkit"
mkdir -p "$shim/lib64/stubs"
for entry in "$toolkit"/*; do
  name=$(basename "$entry")
  [ "$name" = "lib" ] && continue
  ln -sfn "$entry" "$shim/$name"
done
for f in "$toolkit"/lib/*; do ln -sfn "$f" "$shim/lib64/$(basename "$f")"; done
cudart=$(ls "$toolkit"/lib/libcudart.so.* | head -1)
ln -sfn "$cudart" "$shim/lib64/libcudart.so"
# driver library: present on GPU nodes (driver 580.x), usually absent on login nodes (then the symlink dangles, by design)
ln -sfn /usr/lib64/libcuda.so.1 "$shim/lib64/stubs/libcuda.so"
echo "shim: $shim"; ls -l "$shim" "$shim/lib64/libcudart.so" "$shim/lib64/stubs/libcuda.so"
"$shim/bin/nvcc" --version | tail -1
