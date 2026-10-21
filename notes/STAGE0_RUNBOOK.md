# Stage 0 runbook: SGLang smoke test on one A100 (nothing below has been run)

Every Nova step below needs Akshat's explicit OK before it runs. The project rule is to ask before any `sbatch`. Steps A–C are prerequisites: the smoke job runs with `HF_HUB_OFFLINE=1` and from a git checkout on Nova, so the code, the envs and the model weights must already be there.

**Placeholder.** `<WORK>` stands for the project directory on `/work`. Fill it in from the storage check ("Needs Akshat" #2), for example `/work/<group>/avalse`. Nothing below is valid until it is filled in.

**Local verification (done).** I ran the exact `MODE=smoke` code path (`slurm/local_smoke.sh smoke`, `OUTPUT_FEEDBACK=auto`) against the mock engine at harness commit 2f22e08: exit 0, 138/138 requests ok, 0 guard errors. This tests only the glue code, not SGLang.

## A. Put the code on Nova with its git history (so the job banner records a real commit hash)
On the Mac:
```bash
git -C /Users/akshat/research/jannesari-swapp bundle create /tmp/swapp-harness.bundle harness/prefix-meta
scp /tmp/swapp-harness.bundle nova:<WORK>/swapp-harness.bundle
```
On Nova:
```bash
git clone -b harness/prefix-meta <WORK>/swapp-harness.bundle <WORK>/swapp/repo
git -C <WORK>/swapp/repo log --oneline -1
```
The last command should print `2f22e08` or a later commit.

## B. Build the two envs on a compute node, not the login node
`pip` needs outbound internet from the compute node; "Needs Akshat" #4 checks that. If compute nodes have no internet, stop and decide. The fallback is the login node with `nice`, since the install is IO-bound.
```bash
salloc --account=f2026.coms.6250.02 --partition=instruction --qos=instruction --cpus-per-task=8 --mem=32G --time=01:00:00
# on the compute node:
module load micromamba/<exact name from `module -t avail micromamba`>
export MAMBA_ROOT_PREFIX=<WORK>/swapp/mamba-root
micromamba create -y -p <WORK>/swapp/envs/swapp  -c conda-forge python=3.11 numpy pandas pyyaml aiohttp huggingface_hub pytest
micromamba create -y -p <WORK>/swapp/envs/sglang -c conda-forge python=3.11
<WORK>/swapp/envs/sglang/bin/pip install "sglang[all]==0.5.22"
<WORK>/swapp/envs/sglang/bin/python -c "import sglang; print(sglang.__version__)"
<WORK>/swapp/envs/sglang/bin/pip freeze > <WORK>/swapp/envs/sglang.lock.txt
<WORK>/swapp/envs/swapp/bin/pip freeze  > <WORK>/swapp/envs/swapp.lock.txt
exit
```
**Unverified:**
- The PyPI version string `0.5.22` and the `[all]` extra. Check them on the SGLang install page right before running.
- Whether the SGLang wheel pulls its own torch and flashinfer. It should, since the node driver supports CUDA 12.x.

## C. Download the model weights (CPU-only job, about 15 GB)
On Nova, from `<WORK>/swapp/repo`:
```bash
env | grep ^SBATCH_
mkdir -p logs
sbatch --export=ALL,HF_HOME=<WORK>/hf,ENV_GEN=<WORK>/swapp/envs/swapp slurm/download_model.sbatch
```
- The `env` check must print nothing.
- The job asks for 2 CPUs, 8 GB and 1 h on `instruction` under account `f2026.coms.6250.02`, with no GPU.
- After it finishes, copy the `RESOLVED_REVISION <sha>` line from `logs/pm-download-<jobid>.out`. That sha is `HF_REVISION` below.

## D. Stage 0 smoke: the job to approve
On Nova, from `<WORK>/swapp/repo`:
```bash
env | grep ^SBATCH_
mkdir -p logs
sbatch --time=01:30:00 \
  --export=ALL,MODE=smoke,ENV_GEN=<WORK>/swapp/envs/swapp,ENV_SGLANG=<WORK>/swapp/envs/sglang,HF_HOME=<WORK>/hf,HF_REVISION=<sha from step C> \
  slurm/sglang_job.sbatch
```
The `env` check must print nothing.

**Resources.** These come from the `#SBATCH` lines; `--time` on the command line overrides the script's 4 h.

| Setting | Value |
|---|---|
| Account | `f2026.coms.6250.02` (billing guard: the job exits with code 2 under any other account, partition or QoS) |
| Partition / QoS | `instruction` / `instruction` |
| GPU | `gpu:a100:1`, excluding `nova22-amp-7`, so it lands on `nova22-gpu-[1-3]` |
| CPU / memory | 16 CPUs, 128 GB |
| Wall time | **1 h 30 min** |
| Expected use | about 0.8 GPU-h |

**What it does:**
1. Prints the banner: hostname, `nvidia-smi`, `nvidia-smi topo -m`, git commit/branch/dirty, every parameter, and the configs verbatim.
2. Records `pip freeze` and the HF snapshot.
3. Greps `sglang.launch_server --help` for every flag the scripts use, and the package source for the env-var names. It aborts before launch if any is missing.
4. Launches SGLang 0.5.22 with Qwen2.5-7B-Instruct, `--schedule-policy fcfs`, `--max-running-requests 256`, `--chunked-prefill-size 8192`, `--max-total-tokens 300000`, `--context-length 49152`, metrics and cache report.
5. Waits for health (15 min timeout) and checks that `/v1/models` lists the model.
6. Runs the **probe**, which captures the raw response, `cached_tokens`, whether `return_token_ids` works, and the metric names.
7. Runs the flush/canary check.
8. Runs one closed-population run: 32 sessions for 30 min, cache on.
9. Runs the window analysis. Everything goes to `results/nova_job_logs/<jobid>-<ts>/` and `results/agentload_s0_smoke/<ts>/`.

**What we learn** (plan §4 items a–m):
- whether the flags and env vars exist;
- where `cached_tokens` appears;
- whether output token ids come back, which decides `OUTPUT_FEEDBACK=server|synthetic`;
- the metric names;
- whether a 40k-token context is accepted;
- whether the 300k KV cap is honored (server log);
- whether the flush works;
- real startup time;
- the GPU name.

**Kill or abort conditions:**
- A required flag is missing: the job aborts before launch, and I fix `slurm/engine_sglang.sh`.
- The server is not healthy within 15 min: the job aborts.
- Either case costs at most about 20 min of one GPU.

**After it finishes:**
1. I pull `results/nova_job_logs/<jobid>-*` back to a new timestamped local dir with read-only `rsync`.
2. I fill in the unverified items in the plan.
3. I propose the vLLM smoke job (same shape, `slurm/vllm_job.sbatch`, needs its own env) and then Stage C. Each needs a separate OK.
