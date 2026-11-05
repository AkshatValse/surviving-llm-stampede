"""Inventory of every E2-style run dir under results/nova with its registered verdict (read-only).

Run from the worktree root:  python <this> > inventory.csv
Verdicts: the LAST trap_v2_runs.csv row (agentload_analysis_burst2) seen for (run_ts, engine label); stuck := hit_eval < 0.2
(analysis/basin.py STUCK rule, registered constant burst.trap_hit_below), r14/basin rows attached when present.
"""
import glob, json, os, sys
import pandas as pd
import yaml

ROOT = "results/nova"


def rate_from_argv(argv):
    for i, a in enumerate(argv):
        if a.startswith("arrivals.rate_mult="):
            return float(a.split("=", 1)[1])
    return None


def inventory():
    rows = []
    for req in glob.glob(f"{ROOT}/*/**/agentload_e2_burst/*/requests.csv", recursive=True):
        d = os.path.dirname(req).replace("\\", "/")
        parts = d.split("/")
        pulled = parts[2]
        ts = parts[-1]
        m = json.load(open(f"{d}/meta.json"))
        c = yaml.safe_load(open(f"{d}/config_effective.yaml"))
        arr = c.get("arrivals", {}) or {}
        b = arr.get("burst") or {}
        g = c.get("gate", {}) or {}
        rows.append(dict(
            pulled=pulled, run_ts=ts, run_dir=d, label=m.get("engine_label"), arm=m.get("arm"),
            seed=(m.get("seeds") or [None])[0], rate_mult=arr.get("rate_mult", rate_from_argv(m.get("argv", []))),
            burst_n=b.get("n"), gate_mode=g.get("mode"), n_cap=g.get("n_cap"), t_on=g.get("t_on_s"),
            job=(m.get("slurm_env") or {}).get("SLURM_JOB_ID"), hardware=m.get("hardware"),
            prereg_file=m.get("prereg_file"), status=m.get("status"), t_end_s=(m.get("outcome") or {}).get("t_end_s"),
            notes=m.get("notes"), lambda_ref=m.get("lambda_ref_resolved")))
    inv = pd.DataFrame(rows)
    # verdicts
    v = []
    for f in sorted(glob.glob(f"{ROOT}/**/trap_v2_runs.csv", recursive=True)):
        t = pd.read_csv(f)
        t["v_src"] = f.replace("\\", "/")
        v.append(t)
    v = pd.concat(v)
    v["run_ts"] = v.run_dir.str.replace("\\", "/").str.split("/").str[-1]
    v = v.sort_values("v_src").drop_duplicates(["run_ts", "label"], keep="last")
    v = v[["run_ts", "label", "state", "hit_eval", "trapped", "good", "eval_from", "v_src"]].rename(
        columns={"state": "trap_v2_state", "hit_eval": "v_hit_eval", "eval_from": "v_eval_from"})
    inv = inv.merge(v, on=["run_ts", "label"], how="left")
    o = []
    for f in glob.glob(f"{ROOT}/**/r14_runs.csv", recursive=True) + glob.glob(f"{ROOT}/**/basin_runs.csv", recursive=True):
        t = pd.read_csv(f)
        t = t[t.run_dir.astype(str).str.contains("results")]
        t["run_ts"] = t.run_dir.str.replace("\\", "/").str.split("/").str[-1]
        t["o_src"] = f.replace("\\", "/")
        o.append(t[["run_ts", "label", "basin_state", "stuck", "o_src"]])
    o = pd.concat(o).drop_duplicates(["run_ts", "label"], keep="last")
    inv = inv.merge(o, on=["run_ts", "label"], how="left")
    return inv


if __name__ == "__main__":
    inv = inventory()
    inv.to_csv(sys.argv[1] if len(sys.argv) > 1 else sys.stdout, index=False)
