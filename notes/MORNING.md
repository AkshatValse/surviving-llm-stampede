# Morning report: 2026-10-21

_DRAFT, being filled during the night._

## Needs Akshat (run in this order)
1. **Re-verify the account and QoS.** I did not run this tonight because it wasn't on the allowed list. CLAUDE.md's account info comes from an earlier session.
   ```bash
   ssh nova groups
   ssh nova 'sacctmgr -n show assoc user=$USER format=account%30,partition,qos%40'
   ```
   Why: the account must be `f2026.coms.6250.02`, and your default account is the 6720 one.
2. **Check storage and quotas.** These decide the env location in `notes/NOVA_ENV_PLAN.md`.
   ```bash
   ssh nova 'df -h $HOME /work /ptmp /lss 2>&1; ls -ld /work/* /lss/* 2>/dev/null | grep -i -E "6250|jannesari|avalse|coms" ; quota -s 2>&1 | head'
   ```
3. **List the module names.** CLAUDE.md has a list from earlier; this refreshes the exact hashes.
   ```bash
   ssh nova 'module -t avail 2>&1 | grep -Ei "^(python|cuda|cudnn|nccl|miniforge|micromamba|mamba|conda|gcc)/" | sort -u'
   ```
4. **Local PyTorch (optional).** Only needed for MPS pilots (direction #3). It goes in a new conda env, so it doesn't touch base.
   ```bash
   /opt/anaconda3/bin/conda create -y -n swapp python=3.12 numpy scipy numba pandas pyyaml matplotlib pytest && /opt/anaconda3/envs/swapp/bin/pip install torch
   ```
5. **Approve the Nova env plan** (`notes/NOVA_ENV_PLAN.md`) after items 1–3, then let me run it in an `salloc` session.
