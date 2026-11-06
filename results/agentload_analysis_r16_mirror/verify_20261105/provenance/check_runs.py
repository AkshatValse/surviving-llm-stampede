"""Read-only provenance checks of the nine r16 MIRROR runs (items 2-4). Writes only to argv[2] (scratch)."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
TAG = "r16-mirror-reg"
PULL = WT / "results/nova/r16_mirror_1726405x_pulled_20261105-1722"
RUNS = ["20261105-145227", "20261105-145240", "20261105-145242", "20261105-145244", "20261105-145244-1",
        "20261105-145244-2", "20261105-145246", "20261105-145247", "20261105-145248"]
LABEL = "sglang-fcfs-r1-mirror-k20"


def git_blob(rel):
    return subprocess.run(["git", "-C", str(WT), "show", f"{TAG}:{rel}"], check=True, capture_output=True,
                          env={"GIT_OPTIONAL_LOCKS": "0", "PATH": __import__("os").environ["PATH"]}).stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()


TAG_PREREG = git_blob("configs/agentload_prereg_2026-11-05_mirror_k20.yaml")
TAG_E2 = git_blob("configs/agentload_e2_mirror_k20.yaml")
PREREG_SHA, E2_SHA = sha(TAG_PREREG), sha(TAG_E2)
print("tag prereg sha256", PREREG_SHA)
print("tag e2 cfg sha256", E2_SHA)
reg = yaml.safe_load(TAG_PREREG)
print("prereg protocol.e2_config_sha256", reg["protocol"]["e2_config_sha256"], "match" if reg["protocol"]["e2_config_sha256"] == E2_SHA else "MISMATCH")

# sacct
sacct = {}
for ln in (WT / "provenance/sacct_cited_jobs_2026-11-05-r16.txt").read_text().splitlines()[1:]:
    f = ln.split("|")
    sacct[f[0]] = dict(zip(["JobID", "JobName", "Account", "Partition", "Submit", "Start", "End", "State", "ExitCode",
                            "NodeList", "SubmitLine"], f))

# job logs: map out_dir -> job
logs = {}
for lp in sorted((PULL / "logs").glob("*.out")):
    txt = lp.read_text(encoding="utf-8", errors="replace")
    m_job = re.search(r"^job:\s+(\d+) name=(\S+) account=(\S+) partition=(\S+) qos=(\S+)", txt, re.M)
    outs = re.findall(r'"out_dir": "results/agentload_e2_burst/([^"]+)"', txt)
    e2 = re.findall(r"E2_CONFIG=(\S+) sha256=([0-9a-f]{64})", txt)
    psha = re.findall(r"^PREREG_SHA256=([0-9a-f]{64})", txt, re.M)
    pok = re.findall(r"^PREREG_OK file=(\S+) commit=([0-9a-f]{40}) committed_clean=(\S+)", txt, re.M)
    gitc = re.findall(r"^commit:\s+([0-9a-f]{40})", txt, re.M)
    gitb = re.findall(r"^branch:\s+(\S+)", txt, re.M)
    gitd = re.findall(r"^dirty:\s+(.*)$", txt, re.M)
    runs = re.findall(r"^\[[0-9:]+\] agentload run: (.*)$", txt, re.M)
    fin = re.findall(r"^\[[0-9:]+\] all runs finished \((\d+) failed\)", txt, re.M)
    allow = re.findall(r"PREREG_ALLOW_UNCOMMITTED=(\S+)", txt)
    banner_date = re.findall(r"^date:\s+(\S+)", txt, re.M)
    for o in outs:
        logs[o] = dict(log=lp.name, job=m_job.groups() if m_job else None, outs=outs, e2=e2, prereg_sha=psha, prereg_ok=pok,
                       git=(gitc, gitb, gitd), runs=runs, finished=fin, allow_uncommitted=allow, date=banner_date)

rows = []
for rn in RUNS:
    d = PULL / "results/agentload_e2_burst" / rn
    meta = json.loads((d / "meta.json").read_text())
    ce = yaml.safe_load((d / "config_effective.yaml").read_text())
    cfg_bytes = (d / "config.yaml").read_bytes()
    lg = logs.get(rn)
    argv = meta["argv"]
    sets = [argv[i + 1] for i, a in enumerate(argv) if a == "--set"]
    seed_argv = argv[argv.index("--seed") + 1] if "--seed" in argv else None
    rm = [s.split("=", 1)[1] for s in sets if s.startswith("arrivals.rate_mult=")]
    burst_null = [s for s in sets if s.startswith("arrivals.burst=")]
    job_meta = meta["slurm_env"]["SLURM_JOB_ID"]
    sa = sacct.get(job_meta, {})
    sl = sa.get("SubmitLine", "")
    ex = dict(kv.split("=", 1) for kv in re.search(r"--export=ALL,(\S+)", sl).group(1).split(",")) if sl else {}
    oc = meta["outcome"]
    row = dict(
        run=rn, job_meta=job_meta, job_log=(lg["job"][0] if lg and lg["job"] else None), log=lg["log"] if lg else None,
        job_name_meta=meta["slurm_env"]["SLURM_JOB_NAME"],
        acct_qos_meta="/".join([meta["slurm_env"]["SLURM_JOB_ACCOUNT"], meta["slurm_env"]["SLURM_JOB_PARTITION"],
                                meta["slurm_env"]["SLURM_JOB_QOS"]]),
        git_commit=meta["git"]["commit"][:12], git_dirty=meta["git"]["dirty"], git_branch=meta["git"]["branch"],
        log_git=(lg["git"][0][0][:12] if lg and lg["git"][0] else None, lg["git"][1][0] if lg and lg["git"][1] else None,
                 lg["git"][2][0] if lg and lg["git"][2] else None),
        prereg_sha_meta_ok=meta.get("prereg_sha256") == PREREG_SHA,
        prereg_sha_cfgeff_ok=(ce.get("meta") or {}).get("prereg_sha256") == PREREG_SHA,
        prereg_sha_log_ok=bool(lg and lg["prereg_sha"] and all(x == PREREG_SHA for x in lg["prereg_sha"])),
        prereg_file=meta.get("prereg_file"),
        prereg_ok_log=(lg["prereg_ok"] if lg else None),
        allow_uncommitted=(lg["allow_uncommitted"] if lg else None),
        e2_sha_log=(sorted(set(x[1] for x in lg["e2"])) == [E2_SHA] if lg else None),
        e2_path_log=(sorted(set(x[0] for x in lg["e2"])) if lg else None),
        config_yaml_sha_ok=sha(cfg_bytes) == E2_SHA, config_yaml_eq_tag=cfg_bytes == TAG_E2,
        argv_config=argv[argv.index("--config") + 1],
        label_meta=meta.get("engine_label"), label_cfgeff=(ce.get("meta") or {}).get("engine_label"),
        arm_meta=meta.get("arm"), arm_cfgeff=(ce.get("meta") or {}).get("arm"), burst_cfgeff=(ce.get("arrivals") or {}).get("burst"),
        burst_set=burst_null,
        rate_cfgeff=(ce.get("arrivals") or {}).get("rate_mult"), rate_argv=rm,
        seed_meta=meta.get("seeds"), seed_argv=seed_argv, seed_cfgeff=(ce.get("run") or {}).get("seed"),
        lam_ref=meta.get("lambda_ref_resolved"), rate_resolved=meta.get("resolved_rate_sessions_per_s"),
        mean_turns=(ce.get("workload") or {}).get("mean_turns"), max_turns=(ce.get("workload") or {}).get("max_turns"),
        duration_cfgeff=(ce.get("run") or {}).get("duration_s"), status=meta.get("status"), t_end_s=oc.get("t_end_s"),
        abort_reason=oc.get("abort_reason"), t_abort_s=oc.get("t_abort_s"), sessions_failed=oc.get("sessions_failed"),
        requests_error=oc.get("requests_error"), start_time=meta.get("start_time"), t0_utc=meta.get("t0_utc"),
        t0_unix=meta.get("t0_unix"), end_time=meta.get("end_time"), wall_s=meta.get("wall_s"),
        hostname=meta.get("hostname"), hardware=meta.get("hardware"),
        sacct_state=sa.get("State"), sacct_exit=sa.get("ExitCode"), sacct_node=sa.get("NodeList"),
        sacct_submit=sa.get("Submit"), sacct_start=sa.get("Start"), sacct_end=sa.get("End"),
        sub_mults=ex.get("MULTS"), sub_seeds=ex.get("SEEDS"), sub_arms=ex.get("ARMS"), sub_label=ex.get("ENGINE_LABEL"),
        sub_prereg=ex.get("PREREG_FILE"), sub_e2=ex.get("E2_CONFIG"), sub_calib=ex.get("CALIB_FILE"),
        log_runs=len(lg["runs"]) if lg else None, log_outs=len(lg["outs"]) if lg else None,
        log_finished=(lg["finished"] if lg else None), log_date=(lg["date"] if lg else None),
    )
    rows.append(row)

df = pd.DataFrame(rows)
pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 200)
pd.set_option("display.max_colwidth", 120)
for r in rows:
    print("=" * 30, r["run"])
    for k, v in r.items():
        print(f"  {k}: {v}")
df.to_csv(OUT / "runs_provenance.csv", index=False)
print("wrote", OUT / "runs_provenance.csv")
