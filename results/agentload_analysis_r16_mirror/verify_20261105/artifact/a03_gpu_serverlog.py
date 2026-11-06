"""GPU utilisation (nvidia-smi gpu_util.csv) and server.log batch lines per run window; gaps in the engine's batch log.

Usage: python -I a03_gpu_serverlog.py WORKTREE OUTDIR
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

WT = sys.argv[1]
OUT = sys.argv[2]
BASE = os.path.join(WT, "results/nova/r16_mirror_1726405x_pulled_20261105-1722/results")
E0A = os.path.join(WT, "results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results")
CST = timezone(timedelta(hours=-6))
WINDOWS = {"pre": (0, 1200), "post": (1200, 2400), "blackout": (2400, 3600), "mid": (3600, 6600), "late": (6600, 8700)}
LAM_REF = 0.07153402100919228

PREFILL = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Prefill batch, #new-seq: (\d+), #new-token: (\d+), #cached-token: (\d+), "
                     r"token usage: ([\d.]+), #running-req: (\d+), #queue-req: (\d+).*input throughput \(token/s\): ([\d.]+)")
DECODE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Decode batch, #running-req: (\d+), #token: (\d+), token usage: ([\d.]+), "
                    r".*gen throughput \(token/s\): ([\d.]+), #queue-req: (\d+)")
STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]")


def parse_server(path, t0_local):
    pre, dec, stamps = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PREFILL.match(line)
            if m:
                t = (datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST) - t0_local).total_seconds()
                pre.append((t, int(m.group(2)), int(m.group(3)), int(m.group(4)), float(m.group(5)), int(m.group(6)),
                            int(m.group(7)), float(m.group(8))))
                stamps.append(t)
                continue
            m = DECODE.match(line)
            if m:
                t = (datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST) - t0_local).total_seconds()
                dec.append((t, int(m.group(2)), int(m.group(3)), float(m.group(4)), float(m.group(5)), int(m.group(6))))
                stamps.append(t)
    P = pd.DataFrame(pre, columns=["t", "new_seq", "new_tok", "cached_tok", "usage", "running", "queue", "in_tps"])
    D = pd.DataFrame(dec, columns=["t", "running", "tokens", "usage", "gen_tps", "queue"])
    return P, D, np.array(sorted(stamps))


def gpu(path, t0_local):
    g = pd.read_csv(path, skipinitialspace=True)
    g.columns = [c.strip() for c in g.columns]
    t = pd.to_datetime(g["timestamp"], format="%Y/%m/%d %H:%M:%S.%f").dt.tz_localize(CST)
    g["t"] = (t - pd.Timestamp(t0_local)).dt.total_seconds()
    g["util"] = g["utilization.gpu [%]"].astype(str).str.replace("%", "").str.strip().astype(float)
    g["mem"] = g["memory.used [MiB]"].astype(str).str.replace("MiB", "").str.strip().astype(float)
    g["power"] = g["power.draw [W]"].astype(str).str.replace("W", "").str.strip().astype(float)
    return g


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for d in sorted(glob.glob(os.path.join(BASE, "agentload_e2_burst", "*"))):
        meta = json.load(open(os.path.join(d, "meta.json")))
        job = meta["slurm_env"]["SLURM_JOB_ID"]
        tag = f"{round(meta['resolved_rate_sessions_per_s'] / LAM_REF, 2)}x-{meta['arm']}-s{meta['seeds'][0]}"
        t0_local = datetime.fromtimestamp(meta["t0_unix"], tz=CST)
        jd = glob.glob(os.path.join(BASE, "nova_job_logs", f"{job}-*"))[0]
        P, D, st = parse_server(os.path.join(jd, "server.log"), t0_local)
        G = gpu(os.path.join(jd, "gpu_util.csv"), t0_local)
        # largest gap between consecutive engine batch log lines inside the run
        inrun = st[(st >= 0) & (st <= 8700)]
        gaps = np.diff(inrun)
        post = st[(st >= 1200) & (st <= 8700)]
        pg = np.diff(post)
        for w, (a, b) in WINDOWS.items():
            p = P[(P.t >= a) & (P.t < b)]
            dd = D[(D.t >= a) & (D.t < b)]
            g = G[(G.t >= a) & (G.t < b)]
            rows.append(dict(run=tag, job=job, node=meta["hostname"], win=w,
                             log_new_tok_per_s=p.new_tok.sum() / (b - a), log_cached_tok_per_s=p.cached_tok.sum() / (b - a),
                             log_cached_frac=p.cached_tok.sum() / max(1, p.cached_tok.sum() + p.new_tok.sum()),
                             log_new_seq_per_s=p.new_seq.sum() / (b - a),
                             log_queue_mean=pd.concat([p.queue, dd.queue]).mean(),
                             log_running_mean=pd.concat([p.running, dd.running]).mean(),
                             in_tps_med_full8192=p[p.new_tok == 8192].in_tps.median(),
                             gpu_util_mean=g.util.mean(), gpu_util_min=g.util.min(), gpu_util_frac_lt50=(g.util < 50).mean(),
                             gpu_power_mean=g.power.mean(), gpu_mem_max=g.mem.max(), n_gpu_samples=len(g),
                             max_log_gap_s=(np.diff(st[(st >= a) & (st < b)]).max() if ((st >= a) & (st < b)).sum() > 1 else np.nan)))
        print(tag, "max gap between engine batch lines in [0,8700]:", gaps.max() if len(gaps) else None,
              "in [1200,8700]:", pg.max() if len(pg) else None, "n lines", len(inrun), flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "gpu_serverlog_windows.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.float_format", lambda x: f"{x:.4g}")
    print(R.to_string(index=False))

    # E0a job (17264093): same summaries on its own clock (run 20261105-145429 POP32 and the POP64 check)
    for rd in ["agentload_e0_miss/20261105-145429", "agentload_e0_miss_popcheck/20261105-154232"]:
        d = os.path.join(E0A, rd)
        meta = json.load(open(os.path.join(d, "meta.json")))
        t0_local = datetime.fromtimestamp(meta["t0_unix"], tz=CST)
        jd = glob.glob(os.path.join(E0A, "nova_job_logs", "17264093-*"))[0]
        P, D, st = parse_server(os.path.join(jd, "server.log"), t0_local)
        G = gpu(os.path.join(jd, "gpu_util.csv"), t0_local)
        a, b = 900, 2700
        p = P[(P.t >= a) & (P.t < b)]
        g = G[(G.t >= a) & (G.t < b)]
        sel = st[(st >= a) & (st < b)]
        print(f"E0a {rd}: node {meta['hostname']} log_new_tok/s {p.new_tok.sum() / (b - a):.1f} cached/s {p.cached_tok.sum() / (b - a):.1f} "
              f"in_tps(8192 chunks) median {p[p.new_tok == 8192].in_tps.median():.1f} queue_mean {p.queue.mean():.2f} "
              f"running_mean {p.running.mean():.2f} gpu_util_mean {g.util.mean():.1f} power {g.power.mean():.1f} "
              f"max_log_gap {np.diff(sel).max():.1f}")


if __name__ == "__main__":
    main()
