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
