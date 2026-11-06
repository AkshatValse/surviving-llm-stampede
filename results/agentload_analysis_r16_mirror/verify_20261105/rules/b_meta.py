import json, hashlib
import pandas as pd, numpy as np
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
runs = ["20261105-145227","20261105-145240","20261105-145242","20261105-145244","20261105-145244-1","20261105-145244-2","20261105-145246","20261105-145247","20261105-145248"]
def sha_lf(path):
    b = open(path,'rb').read().replace(b'\r\n', b'\n')
    return hashlib.sha256(b).hexdigest()
print("prereg file sha256 (raw):", hashlib.sha256(open(W+"/configs/agentload_prereg_2026-11-05_mirror_k20.yaml",'rb').read()).hexdigest())
print("e2 cfg sha256 (raw):", hashlib.sha256(open(W+"/configs/agentload_e2_mirror_k20.yaml",'rb').read()).hexdigest())
for d in runs:
    p = R + d
    meta = json.load(open(p + "/meta.json"))
    print("=====", d)
    print("  git:", meta.get("git"))
    print("  hardware:", meta.get("hardware"), "| hostname:", meta.get("hostname"))
    print("  t0_utc:", meta.get("t0_utc"), "start:", meta.get("start_time"), "end:", meta.get("end_time"), "wall_s:", meta.get("wall_s"))
    print("  prereg_sha256:", meta.get("prereg_sha256"), "prereg_file:", meta.get("prereg_file"))
    print("  lambda_ref_resolved:", meta.get("lambda_ref_resolved"), "rate:", meta.get("resolved_rate_sessions_per_s"), "uncached_ref:", meta.get("uncached_tokens_ref_resolved"))
    print("  start_state_verified:", meta.get("start_state_verified"), meta.get("start_state_detail"))
    print("  config.yaml sha(LF):", sha_lf(p+"/config.yaml"))
    print("  slurm job:", (meta.get("slurm_env") or {}).get("SLURM_JOB_ID"), (meta.get("slurm_env") or {}).get("SLURM_JOB_NAME"))
    print("  versions:", meta.get("versions"))
    print("  argv:", " ".join(meta.get("argv", []))[:600])
    print("  outcome:", {k: v for k, v in (meta.get("outcome") or {}).items() if not isinstance(v, (dict, list))})
