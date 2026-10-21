"""Operating characteristic of the throughput-based trap criterion under a counting-process model (see
configs/agentload_trap_power.yaml for the assumptions). Writes results/agentload_trap_power/<ts>/ with the config copy,
meta.json (git state at START), power.csv.
    /opt/anaconda3/bin/python experiments/agentload_trap_power.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta  # noqa: E402
from analysis.params import load_params  # noqa: E402

CFG = REPO / "configs" / "agentload_trap_power.yaml"
ANALYSIS = REPO / "configs" / "agentload_analysis.yaml"


def simulate(rng: np.random.Generator, lam: float, lam_miss: float, window_s: float, dt: float, n: int,
             rel_err: float, tol: float, slope_frac: float) -> dict:
    """P(a), P(b), P(a and b) for n replicates of a truly trapped window (backlog = Poisson arrivals - Poisson departures)."""
    nb = int(window_s / dt)
    arr = rng.poisson(lam * dt, size=(n, nb))
    dep = rng.poisson(lam_miss * dt, size=(n, nb))
    backlog = np.cumsum(arr - dep, axis=1).astype(float)
    t = (np.arange(nb) + 0.5) * dt
    tc = t - t.mean()
    slope = (backlog * tc).sum(axis=1) / (tc ** 2).sum()
    ref = lam_miss * (1.0 + rel_err * rng.standard_normal(n))               # the lambda_miss the criterion compares against
    rate = dep.sum(axis=1) / window_s                                      # sessions estimator: departures per second
    a = np.abs(rate - ref) <= tol * ref
    b = slope > slope_frac * (lam - ref)
    return {"p_a": float(a.mean()), "p_b": float(b.mean()), "p_trapped": float((a & b).mean()),
            "slope_mean": float(slope.mean()), "slope_threshold": slope_frac * (lam - lam_miss)}


def main() -> int:
    git = git_info(REPO)
    t0 = datetime.now()
    cfg = yaml.safe_load(CFG.read_text())
    e = cfg["experiment"]
    tp = load_params(ANALYSIS).trap_v2
    out = new_result_dir(REPO / cfg["output"]["root"], cfg["output"]["name"])
    rng = np.random.default_rng(int(e["seed"]))
    rows = []
    for w in e["window_s"]:
        for err in e["lambda_miss_rel_err"]:
            for m in e["lambda_mults"]:
                lam = m * e["lambda_miss"]
                r = simulate(rng, lam, e["lambda_miss"], float(w), float(tp["slope_dt_s"]), int(e["n_replicates"]), float(err),
                             float(tp["rate_tolerance"]), float(tp["slope_frac"]))
                rows.append({"window_s": w, "lambda_miss_rel_err": err, "lambda_mult": m, "lambda": lam,
                             "lambda_minus_miss": lam - e["lambda_miss"], **r})
    df = pd.DataFrame(rows)
    df.to_csv(out / "power.csv", index=False)
    (out / "config.yaml").write_text(CFG.read_text())
    (out / "trap_v2_params.yaml").write_text(yaml.safe_dump(tp))
    write_meta(out, build_meta(experiment="agentload_trap_power", argv=[sys.executable, *sys.argv], seeds=[int(e["seed"])],
                               hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(),
                               extra={"trap_v2_params": tp}, status="finished"))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(df.round(3).to_string(index=False))
    print("result dir:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
