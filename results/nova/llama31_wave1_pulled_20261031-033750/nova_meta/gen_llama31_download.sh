#!/usr/bin/env bash
set -euo pipefail
echo "hostname: $(hostname)  date: $(date -Is)  job: ${SLURM_JOB_ID:-none} account=${SLURM_JOB_ACCOUNT:-?} partition=${SLURM_JOB_PARTITION:-?} qos=${SLURM_JOB_QOS:-?}"
[ "${SLURM_JOB_ACCOUNT:-}" = "f2026.coms.6250.02" ] && [ "${SLURM_JOB_PARTITION:-}" = "instruction" ] || { echo "FATAL: wrong account/partition"; exit 2; }
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=0
"$ENV_GEN/bin/python" - <<'PY'
import os
from huggingface_hub import snapshot_download
m, rev = os.environ["DL_MODEL"], os.environ["DL_REV"]
kw = dict(allow_patterns=["*.json", "*.safetensors", "*.txt", "tokenizer*"], ignore_patterns=["original/*"])   # FIX 1b
p = snapshot_download(m, revision=rev, **kw)
assert os.path.basename(p.rstrip("/")) == rev, (p, rev)
# FIX 1: a download by commit sha writes NO refs/main. The Qwen cache the engines have only ever run against has refs/main ->
# a09a3545 (setup_nova downloaded main). Resolve main once more (online; nothing new is fetched) so the Llama cache has the same
# layout and any engine lookup made without --revision still resolves offline. Fails loudly if main ever moved off d10aef7.
p2 = snapshot_download(m, revision="main", **kw)
assert p2 == p, ("main is not the pinned revision", p2, p)
print("downloaded to", p); print("RESOLVED_REVISION", rev)
open(os.path.join(os.environ["HF_HOME"], "MODEL_REVISION.txt"), "a").write(f"{rev} {m}\n")
PY
R="$HF_HOME/hub/models--$(echo "$DL_MODEL" | sed 's#/#--#g')"
echo "refs/main: $(cat "$R/refs/main")"; [ "$(cat "$R/refs/main")" = "$DL_REV" ]
S="$R/snapshots/$DL_REV"; ls -la "$S"; du -shL "$S"; [ ! -e "$S/original" ]
cd "$S" && sha256sum -c - <<'EOF'
2b1879f356aed350030bb40eb45ad362c89d9891096f79a3ab323d3ba5607668  model-00001-of-00004.safetensors
09d433f650646834a83c580877bd60c6d1f88f7755305c12576b5c7058f9af15  model-00002-of-00004.safetensors
fc1cdddd6bfa91128d6e94ee73d0ce62bfcdb7af29e978ddcab30c66ae9ea7fa  model-00003-of-00004.safetensors
92ecfe1a2414458b4821ac8c13cf8cb70aed66b5eea8dc5ad9eeb4ff309d6d7b  model-00004-of-00004.safetensors
EOF
echo "DOWNLOAD_DONE $(date -Is)"
