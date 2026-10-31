"""Quick B1 check that sets the V1 cost factor, exactly as declared in configs/r9_vllm_predict.yaml (r9.v1). Run from the worktree root on a clean tree."""
import json, subprocess, sys, time
from pathlib import Path
import yaml
sys.path.insert(0, "src")
from prefixmeta.r7_robustness import stage_summary, stage_dir

REPO = Path(".").resolve()
PY = "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe"
SPEC = "configs/r9_vllm_predict.yaml"
spec = yaml.safe_load(Path(SPEC).read_text(encoding="utf-8"))
v1 = spec["r9"]["v1"]
target = float(v1["target_token_rate_tok_per_s"]); tol = float(v1["tolerance_rel"]); dec = int(v1["factor_decimals"]); maxit = int(v1["max_iterations"])
fmt = v1["value_format"]
keys = v1["scaled_engine_keys"]
mode = sys.argv[1]
batching = spec["r9"]["modes"][mode]["batching"]
out_root = spec["r9"]["check_out_root_template"].format(mode=mode)
logfile = Path(sys.argv[2])

def sets_for(f):
    s = []
    if batching != "mixed":
        s.append(f"engine.batching={batching}")
    if f is not None:
        for k in keys:
            s.append(f"engine.{k}={format(float(spec['engine'][k]) * f, fmt)}")
    return s

def run(f):
    argv = [PY, "experiments/r7_robustness_run.py", "lambda_miss", "--spec", SPEC, "--workers", "6", "--out-root", out_root]
    for s in sets_for(f):
        argv += ["--set", s]
    t0 = time.time()
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit("run failed")
    w = stage_summary(out_root, "lambda_miss")["workloads"]["exp5"]
    d = stage_dir(out_root, "lambda_miss")
    return {"factor": f, "sets": sets_for(f), "token_rate": w["token_rate"], "lambda_miss_turns": w["lambda_miss_turns"], "busy": w["busy"],
            "dir": str(d).replace("\\", "/"), "wall_s": time.time() - t0,
            "git": json.loads((d / "meta.json").read_text())["git"]}

hist = []
def log(rec):
    hist.append(rec)
    logfile.write_text(json.dumps({"mode": mode, "target": target, "tolerance_rel": tol, "iterations": hist}, indent=2))
    print(f"[{mode}] f={rec['factor']} R={rec['token_rate']:.2f} ratio={rec['token_rate']/target:.5f} lambda_miss={rec['lambda_miss_turns']:.5f} dirty={rec['git']['dirty']}", flush=True)

r0 = run(None); r0["factor"] = 1.0; log(r0)
f = round(r0["token_rate"] / target, dec)
accepted = None
for k in range(1, maxit + 1):
    rk = run(f); log(rk)
    if abs(rk["token_rate"] / target - 1) <= tol:
        accepted = rk; break
    prev = hist[-2]
    inv_k, inv_p = 1 / rk["token_rate"], 1 / prev["token_rate"]
    f = round(rk["factor"] + (1 / target - inv_k) * (rk["factor"] - prev["factor"]) / (inv_k - inv_p), dec)
if accepted is None:
    accepted = min(hist[1:], key=lambda r: abs(r["token_rate"] / target - 1))
print(f"[{mode}] FROZEN f={accepted['factor']} rate={accepted['token_rate']:.2f} residual={accepted['token_rate']/target-1:+.5f} converged={abs(accepted['token_rate']/target-1)<=tol}")
logfile.write_text(json.dumps({"mode": mode, "target": target, "tolerance_rel": tol, "iterations": hist, "accepted_factor": accepted["factor"],
                               "accepted_rate": accepted["token_rate"], "residual_rel": accepted["token_rate"] / target - 1,
                               "converged": abs(accepted["token_rate"] / target - 1) <= tol}, indent=2))
