"""Read-only analysis: the two self-consistent states of the eviction loop, measured from committed E2 request logs.

For each run (arm, rate, seed) over a window, report:
  hit      fraction of follow-up turns with cached_tokens > prompt/2
  Z        mean client tool time between turns (t_send[k+1] - t_complete[k])
  lat      mean follow-up latency (send -> complete; non-streaming, so ~ queue wait + service)
  gap      mean (Z + lat) = time from the end of turn k to the end of turn k+1 (upper bound of KV age at reuse)
  churn    new KV tokens written per second = uncached prompt tokens + completion tokens of requests completed in window
  R        Che-type characteristic time of the pool = M / churn (how long LRU idle KV survives)
Usage: python loopvars.py <results_dir_with_run_subdirs> <pool_tokens> [t0 t1]
"""
import csv, json, sys, os, statistics as st
from collections import defaultdict

root = sys.argv[1]; M = float(sys.argv[2])
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 5700.0
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else 8700.0

def argval(argv, key):
    for i, a in enumerate(argv):
        if a == "--set" and argv[i + 1].startswith(key + "="):
            return argv[i + 1].split("=", 1)[1].strip('"')
        if a == key:
            return argv[i + 1]
    return None

rows_out = []
for d in sorted(os.listdir(root)):
    p = os.path.join(root, d)
    if not os.path.isfile(os.path.join(p, "requests.csv")):
        continue
    meta = json.load(open(os.path.join(p, "meta.json")))
    argv = meta.get("argv", [])
    arm = argval(argv, "meta.arm"); rate = argval(argv, "arrivals.rate_mult") or ("n=" + str(argval(argv, "arrivals.closed_n"))); seed = argval(argv, "--seed")
    eng = argval(argv, "meta.engine_label")
    by_sid = defaultdict(dict)
    reqs = []
    with open(os.path.join(p, "requests.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["status"] != "ok":
                continue
            t_send = float(r["t_send"]); t_c = float(r["t_complete"])
            k = int(r["turn"]); pt = int(r["prompt_tokens"] or 0); ct = int(r["cached_tokens"] or 0)
            comp = int(r["completion_tokens"] or 0)
            rec = dict(t_send=t_send, t_c=t_c, k=k, pt=pt, ct=ct, comp=comp, lat=float(r["latency_s"]))
            by_sid[r["sid"]][k] = rec
            reqs.append(rec)
    win = [q for q in reqs if t0 <= q["t_c"] < t1]
    fu = [q for q in win if q["k"] > 1]
    if not fu:
        continue
    hit = sum(1 for q in fu if q["ct"] > q["pt"] / 2) / len(fu)
    Zs, gaps, ages_hit = [], [], []
    for sid, turns in by_sid.items():
        for k, q in turns.items():
            if k > 1 and (k - 1) in turns and t0 <= q["t_c"] < t1:
                z = q["t_send"] - turns[k - 1]["t_c"]
                Zs.append(z); gaps.append(z + q["lat"]); ages_hit.append((z + q["lat"], q["ct"] > q["pt"] / 2))
    churn = sum((q["pt"] - q["ct"]) + q["comp"] for q in win) / (t1 - t0)
    R = M / churn if churn > 0 else float("inf")
    pred = sum(1 for a, h in ages_hit if a < R) / max(1, len(ages_hit))
    rows_out.append(dict(run=d, eng=eng, arm=arm, rate=rate, seed=seed, n_fu=len(fu), hit=round(hit, 3),
                         Z=round(st.mean(Zs), 2), lat=round(st.mean(q["lat"] for q in fu), 1),
                         gap_med=round(st.median(gaps), 1), churn_tok_s=round(churn), R_s=round(R, 1), gap_over_R=round(st.median(gaps) / R, 3), pred_hit=round(pred, 3)))

w = csv.DictWriter(sys.stdout, fieldnames=list(rows_out[0].keys()))
w.writeheader()
for r in sorted(rows_out, key=lambda r: (r["eng"] or "", r["rate"] or "", r["arm"] or "", r["seed"] or "")):
    w.writerow(r)
