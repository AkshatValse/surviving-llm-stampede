"""GPU-hour arithmetic for the real-engine plan (configs/agentload_plan_budget.yaml).

Per stage:  jobs = ceil(n_runs / runs_per_job);
            job_wall_h = startup_h + runs_per_job * run_s / 3600 + (runs_per_job - 1) * gap_s / 3600 + teardown_h;
            GPU-h = jobs * job_wall_h * gpus.
The last job of a stage may hold fewer runs; it is charged for the runs it actually holds.
A job must fit in ``time_limit_h`` (``fits`` column). The ``arithmetic`` column spells out every sum, e.g.
``1 x (0.25 + 3 x 0.7500 + 2 x 0.0500 + 0.05) = 2.650 h  +  ...  => 5.300 GPU-h``, and the CLI prints it, so the table can be
checked by hand.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
import yaml

from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta


def job_wall_h(job: Dict[str, Any], run_s: float, k: int) -> float:
    """Wall hours of a job holding k runs of run_s seconds."""
    return job["startup_h"] + k * run_s / 3600.0 + (k - 1) * job["gap_s"] / 3600.0 + job["teardown_h"]


def arithmetic(job: Dict[str, Any], run_s: float, n_runs: int, runs_per_job: int) -> str:
    """The stage's GPU-hour sum written out term by term (see module docstring)."""
    full, rem = divmod(n_runs, runs_per_job)
    run_h, gap_h = run_s / 3600.0, job["gap_s"] / 3600.0
    parts: List[str] = []
    total = 0.0
    for count, k in ((full, runs_per_job), (1 if rem else 0, rem)):
        if count:
            w = job_wall_h(job, run_s, k)
            total += count * w
            parts.append(f"{count} x ({job['startup_h']:g} + {k} x {run_h:.4f} + {k - 1} x {gap_h:.4f} + {job['teardown_h']:g}) = {w:.3f} h")
    return "  +  ".join(parts) + f"  =>  {total * job['gpus']:.2f} GPU-h" + ("" if job["gpus"] == 1 else f" ({job['gpus']} GPUs)")


def stage_rows(cfg: Dict[str, Any]) -> pd.DataFrame:
    job = cfg["job"]
    rows: List[Dict[str, Any]] = []
    for st in cfg["stages"]:
        run_s = float(sum(cfg["protocol"][st["protocol"]]["fields"].values()))
        n, rpj = int(st["n_runs"]), int(st["runs_per_job"])
        jobs = math.ceil(n / rpj)
        full, rem = divmod(n, rpj)

        def wall(k: int) -> float:
            return job_wall_h(job, run_s, k)

        total_wall = full * wall(rpj) + (wall(rem) if rem else 0.0)
        rows.append({"stage": st["name"], "protocol": st["protocol"], "run_s": run_s, "n_runs": n,
                     "runs_per_job": rpj, "jobs": jobs, "job_wall_h_full": wall(rpj),
                     "fits": wall(rpj) <= job["time_limit_h"], "gpu_h": total_wall * job["gpus"],
                     "arithmetic": arithmetic(job, run_s, n, rpj), "note": st.get("note", "")})
    return pd.DataFrame(rows)


def alternative_rows(cfg: Dict[str, Any], alt: Dict[str, Any]) -> pd.DataFrame:
    """Same stages with protocols swapped (``protocol_map``) and a different job time limit."""
    c = {**cfg, "job": {**cfg["job"], "time_limit_h": alt.get("time_limit_h", cfg["job"]["time_limit_h"])},
         "stages": [{**st, "protocol": alt.get("protocol_map", {}).get(st["protocol"], st["protocol"])}
                    for st in cfg["stages"]]}
    return stage_rows(c)


def gate_totals(cfg: Dict[str, Any], df: pd.DataFrame) -> Dict[str, float]:
    out = {g: float(df[df["stage"].isin(names)]["gpu_h"].sum()) for g, names in cfg["gates"].items()}
    out["total"] = float(df["gpu_h"].sum())
    for name, gates in (cfg.get("sums") or {}).items():          # named sums of gates (e.g. the cheap stages before pre-registration)
        out[name] = float(sum(out[g] for g in gates))
    return out


def gate_arithmetic(cfg: Dict[str, Any], df: pd.DataFrame) -> List[str]:
    """One line per gate and per named sum: the stage (gate) values added up."""
    gpu = df.set_index("stage")["gpu_h"]
    lines: List[str] = []
    gate_val: Dict[str, float] = {}
    for g, names in cfg["gates"].items():
        vals = [float(gpu[n]) for n in names]
        gate_val[g] = sum(vals)
        lines.append(f"{g} = " + " + ".join(f"{v:.2f}" for v in vals) + f" = {gate_val[g]:.2f} GPU-h  [{', '.join(names)}]")
    for name, gates in (cfg.get("sums") or {}).items():
        vals = [gate_val[g] for g in gates]
        lines.append(f"{name} = " + " + ".join(f"{v:.2f}" for v in vals) + f" = {sum(vals):.2f} GPU-h  [{', '.join(gates)}]")
    lines.append("total = " + " + ".join(f"{gate_val[g]:.2f}" for g in cfg["gates"]) + f" = {sum(gate_val.values()):.2f} GPU-h")
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.plan_budget")
    ap.add_argument("--config", default="configs/agentload_plan_budget.yaml")
    ap.add_argument("--out-root", default=None)
    args = ap.parse_args(argv)
    git = git_info(Path(args.config).resolve().parent.parent)
    t0 = datetime.now()
    cfg = yaml.safe_load(Path(args.config).read_text())
    out = new_result_dir(args.out_root or cfg["output"]["root"], cfg["output"]["name"])
    df = stage_rows(cfg)
    df.to_csv(out / "gpu_hours_by_stage.csv", index=False)
    totals = gate_totals(cfg, df)
    for name, alt in (cfg.get("alternatives") or {}).items():
        adf = alternative_rows(cfg, alt)
        adf.to_csv(out / f"gpu_hours_by_stage_alt_{name}.csv", index=False)
        totals[f"alt_{name}"] = gate_totals(cfg, adf)
    (out / "gpu_hours_totals.json").write_text(json.dumps(totals, indent=2))
    (out / "config.yaml").write_text(Path(args.config).read_text())
    write_meta(out, build_meta(experiment="agentload_plan_budget", argv=[sys.executable, "-m", "analysis.plan_budget",
               *(argv if argv is not None else sys.argv[1:])], seeds=[], hardware=default_hardware(),
               git=git, t_start=t0, t_end=datetime.now(), extra={"totals": totals}, status="finished"))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(df.drop(columns=["note", "arithmetic"]).round(3).to_string(index=False))
    print("\nArithmetic (jobs x (startup + runs x run_h + (runs-1) x gap_h + teardown) per stage):")
    for _, r in df.iterrows():
        print(f"  {r['stage']}: {r['n_runs']} runs x {r['run_s']:.0f} s, {r['runs_per_job']} per job: {r['arithmetic']}")
    glines = gate_arithmetic(cfg, df)
    print("\nGates and sums:")
    for ln in glines:
        print("  " + ln)
    (out / "gpu_hours_arithmetic.txt").write_text("\n".join(f"{r['stage']}: {r['arithmetic']}" for _, r in df.iterrows())
                                                  + "\n\n" + "\n".join(glines) + "\n")
    print(json.dumps(totals, indent=2))
    print("result dir:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
