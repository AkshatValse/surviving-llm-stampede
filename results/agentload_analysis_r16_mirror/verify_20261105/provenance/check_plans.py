"""Items 3-4: each run's plan.csv vs the frozen plan at the tag (bytes and rows), and the effective workload from the data."""
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WT = Path(sys.argv[1])
TAG = "r16-mirror-reg"
PULL = WT / "results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst"
RUNS = ["20261105-145227", "20261105-145240", "20261105-145242", "20261105-145244", "20261105-145244-1",
        "20261105-145244-2", "20261105-145246", "20261105-145247", "20261105-145248"]
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS="0")


def git_blob(rel):
    return subprocess.run(["git", "-C", str(WT), "show", f"{TAG}:{rel}"], check=True, capture_output=True, env=ENV).stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()


COLS = ["sid", "origin", "idx", "arrival_s", "n_turns", "tool_time_total_s"]
summary = []
plans = {}
for rn in RUNS:
    d = PULL / rn
    meta = json.loads((d / "meta.json").read_text())
    arm = meta["arm"]
    argv = meta["argv"]
    mult = float([argv[i + 1] for i, a in enumerate(argv) if a == "--set" and argv[i + 1].startswith("arrivals.rate_mult=")][0].split("=")[1])
    seed = int(meta["seeds"][0])
    rel = f"results/theory/r16/mirror_plans/{arm}_{mult:g}_seed{seed}.csv"
    fb = git_blob(rel)
    wtb = (WT / rel).read_bytes()
    pb = (d / "plan.csv").read_bytes()
    p = pd.read_csv(io.BytesIO(pb))
    f = pd.read_csv(io.BytesIO(fb))
    plans[(arm, mult, seed)] = p
    res = dict(run=rn, cell=f"{arm} {mult:g} seed{seed}", frozen=rel, wt_frozen_eq_tag=(wtb == fb),
               bytes_equal=(pb == fb), sha_run=sha(pb)[:12], sha_frozen=sha(fb)[:12], header_run=list(p.columns),
               header_eq=list(p.columns) == list(f.columns), n_run=len(p), n_frozen=len(f))
    if len(p) == len(f) and list(p.columns) == list(f.columns):
        for c in ("sid", "idx", "n_turns"):
            res[f"{c}_exact"] = bool((p[c].to_numpy() == f[c].to_numpy()).all())
        res["origin_exact"] = bool((p["origin"].astype(str).to_numpy() == f["origin"].astype(str).to_numpy()).all())
        for c in ("arrival_s", "tool_time_total_s"):
            a, b = p[c].to_numpy(float), f[c].to_numpy(float)
            res[f"{c}_exact_float"] = bool((a == b).all())
            res[f"{c}_n_differ"] = int((a != b).sum())
            res[f"{c}_maxabs"] = float(np.max(np.abs(a - b)))
            res[f"{c}_maxrel"] = float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-300)))
        # textual line-by-line equality per column
        pl = pb.decode().splitlines()
        fl = fb.decode().splitlines()
        tdiff = {c: 0 for c in COLS}
        for x, y in zip(pl[1:], fl[1:]):
            xs, ys = x.split(","), y.split(",")
            for c, u, v in zip(COLS, xs, ys):
                if u != v:
                    tdiff[c] += 1
        res["text_cells_differ_by_col"] = tdiff
    # workload as executed (item 4)
    ses = pd.read_csv(d / "sessions.csv")
    nt = p["n_turns"].to_numpy()
    res["plan_turns_min_max"] = (int(nt.min()), int(nt.max()))
    res["plan_share_T20"] = float((nt == 20).mean())
    res["plan_n_T20"] = int((nt == 20).sum())
    res["plan_T_lt20_values"] = sorted(map(int, nt[nt < 20]))[:12]
    res["plan_ET"] = float(nt.mean())
    b = p[p["origin"].astype(str) == "burst"]
    res["plan_origins"] = p["origin"].astype(str).value_counts().to_dict()
    res["burst_n"] = int(len(b))
    if len(b):
        res["burst_arrival_min_max"] = (float(b["arrival_s"].min()), float(b["arrival_s"].max()))
        res["burst_in_[1200,1260)"] = int(((b["arrival_s"] >= 1200) & (b["arrival_s"] < 1260)).sum())
        res["burst_share_T20"] = float((b["n_turns"] == 20).mean())
    nb = p[p["origin"].astype(str) != "burst"]
    res["base_in_[1200,1260)"] = int(((nb["arrival_s"] >= 1200) & (nb["arrival_s"] < 1260)).sum())
    res["base_arrival_max"] = float(nb["arrival_s"].max())
    # sessions.csv agrees with the plan
    m = ses.merge(p, on="sid", suffixes=("", "_plan"))
    res["ses_rows"] = len(ses)
    res["ses_sid_set_eq_plan"] = set(ses["sid"]) == set(p["sid"])
    res["ses_nturns_eq_plan"] = bool((m["n_turns"] == m["n_turns_plan"]).all())
    res["ses_origin_eq_plan"] = bool((m["origin"].astype(str) == m["origin_plan"].astype(str)).all())
    res["ses_arrival_eq_plan"] = bool((m["arrival_s"] == m["arrival_s_plan"]).all())
    res["ses_share_T20"] = float((ses["n_turns"] == 20).mean())
    res["ses_status"] = ses["status"].astype(str).value_counts().to_dict()
    comp = ses[ses["status"].astype(str) == "completed"]
    res["completed_turns_eq_nturns"] = bool((comp["turns_completed"] == comp["n_turns"]).all())
    res["max_turns_completed"] = int(ses["turns_completed"].max())
    req = pd.read_csv(d / "requests.csv", usecols=["sid", "origin", "turn", "n_turns", "status"])
    res["req_turn_max"] = int(req["turn"].max())
    res["req_nturns_max"] = int(req["n_turns"].max())
    res["req_n"] = len(req)
    summary.append(res)

for r in summary:
    print("=" * 20, r["run"], r["cell"])
    for k, v in r.items():
        if k not in ("run", "cell"):
            print(f"  {k}: {v}")

# paired-arm check: NOBURST plan == BURST plan without the burst rows (base sessions identical)
print("\n=== paired arms (1.65 x): noburst plan vs burst plan's base rows")
for s in (0, 1, 2):
    pb_ = plans[("burst", 1.65, s)]
    pn_ = plans[("noburst", 1.65, s)]
    base = pb_[pb_["origin"].astype(str) == "base"].reset_index(drop=True)
    same_len = len(base) == len(pn_)
    eq = same_len and all(
        (base[c].astype(str).to_numpy() == pn_[c].astype(str).to_numpy()).all() if c == "origin"
        else np.array_equal(base[c].to_numpy(), pn_[c].to_numpy()) for c in ["arrival_s", "n_turns", "tool_time_total_s", "origin"])
    print(f"  seed {s}: burst plan {len(pb_)} rows ({len(base)} base), noburst {len(pn_)} rows; base rows identical "
          f"(arrival_s, n_turns, tool_time_total_s): {eq}")
pd.DataFrame(summary).to_csv(Path(sys.argv[2]) / "plans_workload.csv", index=False)
