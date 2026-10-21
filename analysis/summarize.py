"""Command line analysis of agentload runs. Every invocation writes a NEW dir ``<root>/<name>/<timestamp>/`` with
the analysis params (config.yaml), meta.json (git state at start, inputs, versions) and the CSV/JSON outputs.

  python -m analysis.summarize windows   --run-dirs RUN [RUN ...]
  python -m analysis.summarize burst     --run-dirs RUN [RUN ...]          # trap / recovery / hysteresis + kill rule
  python -m analysis.summarize miss      --run-dirs RUN [...] --warmup-s N  # lambda_miss from closed-population runs
  python -m analysis.summarize stable    --run-dirs RUN [...]               # stable-from-empty verdict per run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import yaml

from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta

from .hysteresis import (burst_verdict, kill_table, kill_verdict, lambda_miss_closed, stable_verdict)
from .load import Run, load_run
from .params import AnalysisParams, load_params
from .windows import queue_trace, window_table

DEFAULT_PARAMS = "configs/agentload_analysis.yaml"


def _sanitize(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, (float, np.floating)) and not np.isfinite(float(o)):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def _finish(out: Path, params_path: str, p: AnalysisParams, argv: List[str], git: Dict[str, Any], t0: datetime,
            inputs: List[Run], extra: Dict[str, Any]) -> None:
    (out / "config.yaml").write_text(Path(params_path).read_text())
    (out / "config_effective.yaml").write_text(yaml.safe_dump(p.raw, sort_keys=False))
    ins = [{"run_dir": str(r.dir), "label": r.label, "seed": r.seed, "run_git": r.meta.get("git"),
            "run_start": r.meta.get("start_time"), "hardware": r.meta.get("hardware"),
            "slurm_env": r.meta.get("slurm_env")} for r in inputs]
    meta = build_meta(experiment="agentload_analysis", argv=argv, seeds=[r.seed for r in inputs],
                      hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(),
                      extra={"inputs": ins, **extra}, status="finished")
    write_meta(out, meta)


def _runs(dirs: Sequence[str]) -> List[Run]:
    return [load_run(d) for d in dirs]


def cmd_windows(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    frames, traces = [], []
    for r in runs:
        w = window_table(r, p)
        w.insert(0, "run_dir", str(r.dir))
        w.insert(1, "label", r.label)
        w.insert(2, "seed", r.seed)
        frames.append(w)
        tr = queue_trace(r, p)
        tr.insert(0, "run_dir", str(r.dir))
        traces.append(tr)
    pd.concat(frames, ignore_index=True).to_csv(out / "windows.csv", index=False)
    pd.concat(traces, ignore_index=True).to_csv(out / "queue_trace.csv", index=False)
    return {"n_runs": len(runs)}


def cmd_burst(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    rows, frames = [], []
    for r in runs:
        w = window_table(r, p)
        v = burst_verdict(r, w, p)
        v["run_dir"] = str(r.dir)
        rows.append(v)
        w.insert(0, "run_dir", str(r.dir))
        frames.append(w)
    df = pd.DataFrame(rows)
    df.to_csv(out / "burst_runs.csv", index=False)
    pd.concat(frames, ignore_index=True).to_csv(out / "windows.csv", index=False)
    tab = kill_table(df, p.kill["trapped_fraction_min"], p.kill["min_runs_per_cell"])
    tab.to_csv(out / "burst_cells.csv", index=False)
    kv = kill_verdict(tab, p, args.fcfs_substr)
    (out / "kill_verdict.json").write_text(json.dumps(_sanitize(kv), indent=2, default=json_default))
    return {"n_runs": len(runs), "kill_verdict": _sanitize(kv)}


def cmd_miss(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    rows = [lambda_miss_closed(r, args.warmup_s) for r in runs]
    df = pd.DataFrame(rows)
    df.to_csv(out / "lambda_miss_runs.csv", index=False)
    n = len(df)
    calib = {
        "lambda_miss": float(df["lambda_miss_sessions"].mean()),
        "lambda_miss_turns_based": float(df["lambda_miss_turns_based"].mean()),
        "lambda_miss_se": float(df["lambda_miss_sessions"].std(ddof=1) / np.sqrt(n)) if n > 1 else None,
        "lambda_miss_turns_based_se": float(df["lambda_miss_turns_based"].std(ddof=1) / np.sqrt(n)) if n > 1 else None,
        "n_runs": n, "warmup_s": args.warmup_s, "labels": sorted(set(df["label"])),
        "note": "lambda_miss = completed sessions/s (simulator headline); turns-based = turns/s / E[T]; "
                "use the key you want in arrivals.lambda_ref ('<path>/calibration.json:<key>')."}
    (out / "calibration.json").write_text(json.dumps(_sanitize(calib), indent=2))
    return {"calibration": _sanitize(calib)}


def cmd_stable(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    rows = []
    for r in runs:
        row = stable_verdict(r, queue_trace(r, p), p)
        row["run_dir"] = str(r.dir)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(out / "stable_runs.csv", index=False)
    g = df.groupby(["label", "rate_mult"], dropna=False)["stable"].agg(["sum", "size"]).reset_index()
    g.columns = ["label", "rate_mult", "n_stable", "n_runs"]
    g.to_csv(out / "stable_by_rate.csv", index=False)
    return {"n_runs": len(runs)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.summarize")
    ap.add_argument("cmd", choices=["windows", "burst", "miss", "stable"])
    ap.add_argument("--run-dirs", nargs="+", required=True)
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--set", action="append", default=[], help="override an analysis param, e.g. burst.trap_min_s=6000")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--warmup-s", type=float, default=0.0, help="(miss) discard this many seconds at the start")
    ap.add_argument("--fcfs-substr", default="fcfs", help="(burst) labels containing this are the FCFS cells")
    args = ap.parse_args(argv)
    p = load_params(args.params, args.set)
    repo = Path(args.params).resolve().parent.parent
    git = git_info(repo)                              # at START
    t0 = datetime.now()
    root = args.out_root or p.raw["output"]["root"]
    name = args.name or f'{p.raw["output"]["name"]}_{args.cmd}'
    out = new_result_dir(root, name)
    runs = _runs(args.run_dirs)
    fn = {"windows": cmd_windows, "burst": cmd_burst, "miss": cmd_miss, "stable": cmd_stable}[args.cmd]
    extra = fn(args, p, out, runs)
    _finish(out, args.params, p, [sys.executable, "-m", "analysis.summarize", *(argv if argv is not None else sys.argv[1:])],
            git, t0, runs, extra)
    print(json.dumps({"out_dir": str(out), **{k: v for k, v in extra.items() if k != "kill_verdict"}}, indent=2,
                     default=json_default))
    if "kill_verdict" in extra:
        print(json.dumps(extra["kill_verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
