# vLLM runbook for Nova (second engine, cell D)

Status: DRAFT in progress (branch r7/vllm-prep). Nothing here has been run on Nova. This file is written first and
filled in as each item is verified; sections marked TODO are not done yet.

## 1. Release choice (verified 2026-10-25 against PyPI and GitHub)

| Item | Value | Source |
|---|---|---|
| Version | vllm 0.32.0 (latest on PyPI; the plan's choice) | https://pypi.org/project/vllm/0.32.0/ , `https://pypi.org/pypi/vllm/json` |
| PyPI upload | 2026-10-18T10:03:29Z (aarch64 wheel), x86_64 wheel 10:03:52Z | PyPI JSON `urls[].upload_time_iso_8601` |
| GitHub release | v0.32.0, published 2026-10-18T06:50:48Z, tag -> commit 5df63a7203cdb9328d824a27b682e77c7b9928be | `gh api repos/vllm-project/vllm/releases/tags/v0.32.0`, `git/ref/tags/v0.32.0` |
| Wheel | `vllm-0.32.0-cp38-abi3-manylinux_2_28_x86_64.whl`, 311 MiB, sha256 5e2ecdc5b0baf729... | PyPI JSON |
| Python | `>=3.11,<3.15` (3.10 dropped in 0.32.0) | PyPI `requires_python`, release notes |
| torch pin | `torch==2.13.0` (exact), `torchvision==0.28.0`, `torchaudio==2.11.0`, `flashinfer-python==0.7.0.post1`, `numba==0.65.0` | PyPI `requires_dist` of 0.32.0 |
| CUDA | release notes: "PyPI (CUDA 13.0): `pip install vllm`"; torch 2.13.0's default Linux wheel depends on `cuda-toolkit[...]==13.0.3`, `nvidia-cudnn-cu13==9.20.0.48`, `nvidia-nccl-cu13==2.29.7` | release notes; `https://pypi.org/pypi/torch/2.13.0/json` |
| Driver fit | NVIDIA 580.178.04 (Nova A100 nodes) is an R580 driver, i.e. the CUDA 13.0 branch; the SGLang env already runs torch 2.14.1+cu130 on it (Stage 0, job 17060165) | notes/NOVA_PLAN_prefix_meta.md, Stage 0 result |
| Binary check | The x86_64 wheel's compiled modules link CUDA 13: `DT_NEEDED` of `_deepselect_C`, `_flashkda_C`, `_flashmla_C`, `_flashmla_extension_C`, `_qutlass_C` = `libcudart.so.13`; `cumem_allocator`, `fs_io_C`, `spinloop` = `libnvrtc.so.13`. None needs `libcudart.so.12`. Read by HTTP range requests on the PyPI wheel (nothing saved). | `https://files.pythonhosted.org/packages/a5/0d/0b15fda9a56ac485ebb607e466f0e3386c8c115bafeced6514298bd325b5/vllm-0.32.0-cp38-abi3-manylinux_2_28_x86_64.whl` |
| Doc conflict | `docs/getting_started/installation/gpu.cuda.inc.md` at the tag still says "compiled with CUDA 12.9"; the release notes and the binary check say CUDA 13.0 for the PyPI wheel. The docs line is stale. | `https://github.com/vllm-project/vllm/blob/v0.32.0/docs/getting_started/installation/gpu.cuda.inc.md` |

Finding that changes the launcher (source, not memory): Qwen2 builds its rotary cos/sin cache from
`config.max_position_embeddings` (32768), not from `--max-model-len`
(`vllm/model_executor/models/qwen2.py` line 268 at the tag). `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` alone lets the server accept
49152-token contexts, but positions above 32767 then index past the end of that cache. The launcher therefore also passes
`--hf-overrides '{"max_position_embeddings": CONTEXT_LEN}'` (flag at `vllm/engine/arg_utils.py` line 1010), which sizes the cache to 49152.
