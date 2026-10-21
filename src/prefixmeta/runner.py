"""Experiment orchestration for the prefix-cache metastability pilot (E0..E4, robustness, ablation,
decision rule). Each experiment writes ``results/<name>/<YYYYmmdd-HHMMSS>/`` containing
``config.yaml`` (copy of the config file), ``config_effective.yaml``, ``meta.json``, ``runs.csv``,
``windows.csv``, ``qtrace.csv`` and experiment-specific summary CSV/JSON. Existing dirs are never reused.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import dataclasses
import json
import math
import multiprocessing as mp
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from .metrics import longest_run_below, tail_stats, trend_rise
from .sim import RunSpec, deep_update, load_config, simulate
from .workload import ArrivalPlan, WorkloadParams, default_session_cap, triangle_rate

HARDWARE = "Apple M3 Max CPU (simulation)"
ID_KEYS = ["exp", "policy", "seed", "variant", "lam", "lam_mult"]


# ======================================================================= infrastructure
def _work(args: Tuple[dict, RunSpec]) -> Dict[str, Any]:
    cfg, rs = args
    return simulate(cfg, rs)


class Runner:
    """Runs RunSpecs, in-process (workers<=1) or in a spawn-context process pool. Output order = input order."""

    def __init__(self, cfg: dict, workers: int):
        self.cfg = cfg
        self.workers = max(1, min(int(workers), int(cfg["parallel"]["max_workers"])))
        self._ex: Optional[cf.ProcessPoolExecutor] = None

    def __enter__(self) -> "Runner":
        if self.workers > 1:
            self._ex = cf.ProcessPoolExecutor(max_workers=self.workers, mp_context=mp.get_context("spawn"))
        return self

    def __exit__(self, *exc) -> None:
        if self._ex is not None:
            self._ex.shutdown()

    def run(self, specs: Sequence[RunSpec]) -> List[Dict[str, Any]]:
        args = [(self.cfg, rs) for rs in specs]
        if self._ex is None:
            return [_work(a) for a in args]
        return list(self._ex.map(_work, args, chunksize=1))


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def new_result_dir(root: str, name: str) -> Path:
    base = Path(root) / name
    base.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    for k in range(100):
        d = base / (stamp if k == 0 else f"{stamp}-{k}")
        try:
            d.mkdir(exist_ok=False)
            return d
        except FileExistsError:
            continue
    raise RuntimeError("could not create a fresh result dir")


def _git(args: List[str], cwd: Path) -> str:
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # pragma: no cover
        return ""


def git_info(repo_dir: Path) -> Dict[str, Any]:
    commit = _git(["rev-parse", "HEAD"], repo_dir)
    dirty = bool(_git(["status", "--porcelain"], repo_dir))     # tracked changes OR untracked non-ignored files
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
    return {"commit": commit, "dirty": dirty, "branch": branch}


def env_versions() -> Dict[str, str]:
    import scipy
    return {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "pyyaml": yaml.__version__, "platform": platform.platform()}


def write_meta(d: Path, *, experiment: str, argv: List[str], seeds: List[int], t_start: float, t_end: float,
               repo_dir: Path, extra: Dict[str, Any]) -> None:
    meta = {
        "experiment": experiment,
        "argv": argv,
        "git": git_info(repo_dir),
        "seeds": seeds,
        "versions": env_versions(),
        "hostname": socket.gethostname(),
        "hardware": HARDWARE,
        "start_time": datetime.fromtimestamp(t_start).isoformat(timespec="seconds"),
        "end_time": datetime.fromtimestamp(t_end).isoformat(timespec="seconds"),
        "wall_s": t_end - t_start,
    }
    meta.update(extra)
    (d / "meta.json").write_text(json.dumps(meta, indent=2, default=_json_default))


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def sanitize(o: Any) -> Any:
    """JSON-safe: NaN/inf -> None recursively."""
    if isinstance(o, dict):
        return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, (float, np.floating)) and not math.isfinite(float(o)):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def collect_frames(results: List[Dict[str, Any]], specs: Sequence[RunSpec]
                   ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    runs, wins, qts = [], [], []
    for i, (res, rs) in enumerate(zip(results, specs)):
        s = dict(res["summary"])
        s["run_id"] = i
        runs.append(s)
        ident = {k: s.get(k) for k in ID_KEYS}
        ident["run_id"] = i
        for w in res["windows"]:
            row = dict(ident)
            row.update(w)
            row.update(res.get("window_extra", {}).get(w["window"], {}))
            wins.append(row)
        for (t, m, x) in res["qtrace"]:
            qts.append({**ident, "t_start": t, "queue_mean": m, "queue_max": x})
    return pd.DataFrame(runs), pd.DataFrame(wins), pd.DataFrame(qts)


def save_frames(d: Path, runs: pd.DataFrame, wins: pd.DataFrame, qts: pd.DataFrame) -> None:
    runs.to_csv(d / "runs.csv", index=False)
    wins.to_csv(d / "windows.csv", index=False)
    qts.to_csv(d / "qtrace.csv", index=False)


def save_configs(d: Path, cfg_path: str, cfg_effective: dict) -> None:
    shutil.copyfile(cfg_path, d / "config.yaml")
    (d / "config_effective.yaml").write_text(yaml.safe_dump(cfg_effective, sort_keys=False))


def exp_cfg(cfg: dict, name: str, quick: bool) -> dict:
    c = dict(cfg[name])
    q = c.pop("quick", {})
    if quick:
        c.update(q)
    return c


def policy_list(cfg: dict, sel: Any) -> List[str]:
    if sel == "all":
        return list(cfg["policy_order"])
    return list(sel)


def timing_summary(runs: pd.DataFrame) -> Dict[str, float]:
    sim = float(runs["sim_end_s"].sum())
    wall = float(runs["wall_s"].sum())
    return {"total_sim_s": sim, "total_run_wall_s": wall,
            "wall_s_per_10k_sim_s": wall / sim * 1e4 if sim > 0 else float("nan"),
            "max_run_wall_s": float(runs["wall_s"].max())}


# ======================================================================= calibration I/O
def load_calibration(calib: Optional[str], results_root: str) -> Dict[str, Any]:
    """Read e0_summary.json from a dir/file, or the newest non-quick prefix_meta_e0 result."""
    if calib:
        p = Path(calib)
        p = p / "e0_summary.json" if p.is_dir() else p
    else:
        cands = sorted(Path(results_root, "prefix_meta_e0").glob("*/e0_summary.json"))
        if not cands:
            raise FileNotFoundError("no prefix_meta_e0 result found; run `e0` first or pass --calib")
        p = cands[-1]
    d = json.loads(p.read_text())
    d["_path"] = str(p)
    return d


# ======================================================================= E0
def miss_run_specs(cfg: dict, e0: dict, population: int, seeds: Sequence[int]) -> List[RunSpec]:
    H = e0["miss_horizon_s"]
    return [RunSpec(exp="e0_miss", policy="fcfs", seed=s, horizon_s=H,
                    plan=ArrivalPlan(kind="closed", horizon_s=H, closed_n=population, pool=e0["miss_pool_sessions"]),
                    engine_overrides={"cache_enabled": False},
                    meta={"lam": float("nan"), "lam_mult": float("nan"), "population": population})
            for s in seeds]


def miss_throughput(res: Dict[str, Any], warmup_s: float, window_s: float) -> Dict[str, float]:
    rows = [w for w in res["windows"] if w["t_start"] >= warmup_s - 1e-9]
    dur = len(rows) * window_s
    sess = sum(w["sessions_per_s"] for w in rows) * window_s
    turns = sum(w["turns_per_s"] for w in rows) * window_s
    return {"sessions_per_s": sess / dur, "turns_per_s": turns / dur,
            "busy_frac": float(np.mean([w["busy_frac"] for w in rows])), "n_sessions": sess}


def stable_verdict(res: Dict[str, Any], e0: dict) -> Dict[str, Any]:
    """Stability of an LPM run from an empty start: final queue < X, no upward trend over the last window,
    and not early-stopped for queue explosion."""
    s = res["summary"]
    end = s["sim_end_s"]
    W = min(e0["stable_trend_window_s"], end / 2.0)
    rise = trend_rise(res["qtrace"], end - W, end)
    fq_ok = s["final_queue"] < e0["stable_final_queue_below"]
    rise_ok = bool(rise == rise and rise <= e0["stable_trend_max_rise"])
    stable = (not s["stopped_early"]) and fq_ok and rise_ok
    return {"stable": bool(stable), "final_queue": s["final_queue"], "trend_rise": rise,
            "tail_queue_mean": s["tail_queue_mean"], "tail_hit_rate": s["tail_hit_rate"],
            "stopped_early": s["stopped_early"], "tail_busy_frac": s["tail_busy_frac"]}


def _frac_stable(rows: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    g = df.groupby("lam_mult")["stable"].agg(["mean", "size"]).reset_index().sort_values("lam_mult")
    return [{"lam_mult": float(r.lam_mult), "frac_stable": float(r["mean"]), "n_seeds": int(r["size"])}
            for _, r in g.iterrows()]


def cap_specs(cfg: dict, e0: dict, lam: float, mult: float) -> List[RunSpec]:
    H = e0["cap_horizon_s"]
    return [RunSpec(exp="e0_cap", policy="lpm", seed=s, horizon_s=H,
                    plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam),
                    stop_queue_above=int(e0["unstable_queue_stop"]),
                    meta={"lam": lam, "lam_mult": mult})
            for s in e0["cap_seeds"]]


def cmd_e0(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    t_start = time.time()
    e0 = exp_cfg(cfg, "e0", args.quick)
    wl = WorkloadParams.from_dict(cfg["workload"])
    W = cfg["metrics"]["window_s"]
    out = new_result_dir(args.out_root, "prefix_meta_e0" + ("_quick" if args.quick else ""))
    all_specs: List[RunSpec] = []
    all_results: List[Dict[str, Any]] = []
    with Runner(cfg, args.workers) as R:
        # ---- lambda_miss: caching disabled, closed population, FCFS
        miss_by_pop: Dict[int, List[Dict[str, float]]] = {}
        pops = [e0["miss_closed_population"]] + [p for p in e0.get("miss_population_check", [])
                                                  if p != e0["miss_closed_population"]]
        for pop in pops:
            specs = miss_run_specs(cfg, e0, pop, e0["miss_seeds"])
            res = R.run(specs)
            all_specs += specs
            all_results += res
            miss_by_pop[pop] = [miss_throughput(r, e0["miss_warmup_s"], W) for r in res]
        primary = miss_by_pop[e0["miss_closed_population"]]
        per_seed = [m["sessions_per_s"] for m in primary]
        lam_miss = float(np.mean(per_seed))
        lam_miss_se = float(np.std(per_seed, ddof=1) / math.sqrt(len(per_seed))) if len(per_seed) > 1 else float("nan")
        turns_based = float(np.mean([m["turns_per_s"] for m in primary]) / wl.effective_mean_turns())

        # ---- lambda_cap: pure LPM, empty start, bracket then bisect
        search_rows: List[Dict[str, Any]] = []

        def test(lam: float, mult: float, phase: str) -> bool:
            nonlocal all_specs, all_results
            specs = cap_specs(cfg, e0, lam, mult)
            res = R.run(specs)
            all_specs += specs
            all_results += res
            verd = [stable_verdict(r, e0) for r in res]
            for sp, v in zip(specs, verd):
                search_rows.append({"phase": phase, "lam": lam, "lam_mult": mult, "seed": sp.seed, **v})
            return all(v["stable"] for v in verd)

        seq = [1.0] + list(e0["cap_bracket_mults"])
        lo_m, hi_m = 0.0, None
        for m in seq:
            if test(m * lam_miss, m, "bracket"):
                lo_m = m
            else:
                hi_m = m
                break
        cap_unbounded = hi_m is None
        if not cap_unbounded:
            lo, hi = lo_m * lam_miss, hi_m * lam_miss
            for _ in range(int(e0["cap_max_bisect_steps"])):
                if lo > 0 and (hi - lo) <= e0["cap_rel_tol"] * lo:
                    break
                mid = 0.5 * (lo + hi)
                if test(mid, mid / lam_miss, "bisect"):
                    lo = mid
                else:
                    hi = mid
            lam_cap = lo
            bracket = [lo, hi]
        else:
            lam_cap = lo_m * lam_miss
            bracket = [lam_cap, float("inf")]

        # ---- diagnostic (does not change lambda_cap): escape-time hazard of the "good" state
        hazard_rows: List[Dict[str, Any]] = []
        hz = e0.get("cap_hazard")
        if hz:
            specs = [RunSpec(exp="e0_hazard", policy=p, seed=sd, horizon_s=hz["horizon_s"],
                             plan=ArrivalPlan(kind="constant", horizon_s=hz["horizon_s"], rate=m * lam_miss),
                             stop_queue_above=int(hz["escape_queue_above"]),
                             meta={"lam": m * lam_miss, "lam_mult": m})
                     for p in hz["policies"] for m in hz["mults"] for sd in hz["seeds"]]
            res = R.run(specs)
            all_specs += specs
            all_results += res
            for p in hz["policies"]:
                for m in hz["mults"]:
                    rr = [r["summary"] for sp, r in zip(specs, res)
                          if sp.policy == p and sp.meta["lam_mult"] == m]
                    esc = [x["stop_time"] for x in rr if x["stopped_early"]]
                    hazard_rows.append({"policy": p, "lam_mult": m, "lam": m * lam_miss, "n_runs": len(rr),
                                        "n_escaped": len(esc), "frac_escaped": len(esc) / len(rr),
                                        "escape_time_median_s": float(np.median(esc)) if esc else float("nan"),
                                        "escape_time_min_s": float(np.min(esc)) if esc else float("nan"),
                                        "horizon_s": hz["horizon_s"], "escape_queue_above": hz["escape_queue_above"]})
    t_end = time.time()

    # ---- outputs
    runs, wins, qts = collect_frames(all_results, all_specs)
    save_frames(out, runs, wins, qts)
    pd.DataFrame(search_rows).to_csv(out / "cap_search.csv", index=False)
    pd.DataFrame(hazard_rows).to_csv(out / "cap_hazard.csv", index=False)
    miss_rows = []
    for pop, ms in miss_by_pop.items():
        for seed, m in zip(e0["miss_seeds"], ms):
            miss_rows.append({"population": pop, "seed": seed, **m})
    pd.DataFrame(miss_rows).to_csv(out / "miss_runs.csv", index=False)
    N_star = default_session_cap(cfg["engine"]["kv_memory_tokens"], wl)
    summary = {
        "quick": bool(args.quick),
        "lambda_miss": lam_miss,
        "lambda_miss_per_seed": per_seed,
        "lambda_miss_se": lam_miss_se,
        "lambda_miss_turns_based": turns_based,
        "lambda_miss_by_population": {str(p): float(np.mean([m["sessions_per_s"] for m in ms]))
                                      for p, ms in miss_by_pop.items()},
        "miss_busy_frac_mean": float(np.mean([m["busy_frac"] for m in primary])),
        "lambda_cap": lam_cap,
        "lambda_cap_bracket": bracket,
        "lambda_cap_unbounded_in_search": bool(cap_unbounded),
        "R": lam_cap / lam_miss,
        "R_bracket": [bracket[0] / lam_miss, bracket[1] / lam_miss],
        "cap_search_frac_stable_by_lambda": _frac_stable(search_rows),
        "cap_hazard": hazard_rows,
        "session_cap_N_star": N_star,
        "mean_turns_effective": wl.effective_mean_turns(),
        "timing": timing_summary(runs),
        "config_e0": e0,
    }
    (out / "e0_summary.json").write_text(json.dumps(sanitize(summary), indent=2))
    save_configs(out, args.config, {**cfg, "e0_effective": e0})
    write_meta(out, experiment="e0", argv=sys.argv, seeds=sorted(set(int(s) for s in runs["seed"])),
               t_start=t_start, t_end=t_end, repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "workers": args.workers, "n_runs": int(len(runs)),
                      "timing": summary["timing"], "lambda_miss": lam_miss, "lambda_cap": lam_cap,
                      "R": summary["R"], "N_star": N_star})
    print(json.dumps(sanitize({k: v for k, v in summary.items() if k != "config_e0"}), indent=2))
    print("result dir:", out)
    return out


# ======================================================================= shared helpers for E1..E4
def tail_len(cfg: dict, horizon: float) -> float:
    return min(cfg["metrics"]["tail_window_s"], horizon / 2.0)


def add_recovery_columns(runs: pd.DataFrame, wins: pd.DataFrame, cfg: dict, horizon: float,
                         q_below: float, hit_above: float) -> pd.DataFrame:
    """recovered: mean waiting queue over the tail < q_below and tail hit rate > hit_above.
    recovered_incl_gate additionally counts the outer-gate backlog (FCFS-CAP) as queue."""
    tail = tail_len(cfg, horizon)
    gate_tail = []
    for rid in runs["run_id"]:
        w = wins[(wins["run_id"] == rid) & (wins["t_start"] >= horizon - tail - 1e-9)]
        gate_tail.append(float(w["gate_mean"].mean()) if len(w) else float("nan"))
    runs = runs.copy()
    runs["tail_gate_mean"] = gate_tail
    runs["recovered"] = (runs["tail_hit_rate"] > hit_above) & (runs["tail_queue_mean"] < q_below)
    runs["recovered_incl_gate"] = runs["recovered"] & ((runs["tail_queue_mean"] + runs["tail_gate_mean"]) < q_below)
    return runs


def recovery_table(runs: pd.DataFrame) -> pd.DataFrame:
    g = runs.groupby(["variant", "policy", "lam_mult"], sort=False)
    t = g.agg(n_runs=("recovered", "size"), n_recovered=("recovered", "sum"),
              n_recovered_incl_gate=("recovered_incl_gate", "sum"),
              tail_hit_mean=("tail_hit_rate", "mean"), tail_queue_mean=("tail_queue_mean", "mean"),
              tail_gate_mean=("tail_gate_mean", "mean"), tail_busy_mean=("tail_busy_frac", "mean"),
              tail_sessions_per_s=("tail_sessions_per_s", "mean")).reset_index()
    return t


def largest_recovered(table: pd.DataFrame, col: str = "n_recovered") -> pd.DataFrame:
    rows = []
    for (variant, policy), g in table.groupby(["variant", "policy"], sort=False):
        ok = g[g[col] == g["n_runs"]]
        rows.append({"variant": variant, "policy": policy,
                     "largest_lam_mult_all_seeds_recovered": float(ok["lam_mult"].max()) if len(ok) else float("nan")})
    return pd.DataFrame(rows)


# ======================================================================= E1 recovery
def cmd_e1(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any],
           ablation: bool = False) -> Path:
    t_start = time.time()
    name = "ablation_skip_ahead" if ablation else "e1"
    e1 = exp_cfg(cfg, name, args.quick)
    lam_miss, lam_cap = calib["lambda_miss"], calib["lambda_cap"]
    H = e1["horizon_s"]
    pols = policy_list(cfg, e1["policies"])
    mults = e1["lam_mults"] if not ablation else [e1["lam_mult"]]
    cold = e1["cold_sessions"]
    specs: List[RunSpec] = []
    skipped = []
    for m in mults:
        lam = m * lam_miss
        if lam >= lam_cap:
            skipped.append(m)
            continue
        plan = ArrivalPlan(kind="constant", horizon_s=H, rate=lam, initial_cold=cold)
        if ablation:
            for skip in (False, True):
                for pol in pols:
                    for sd in e1["seeds"]:
                        specs.append(RunSpec(exp=name, policy=pol, seed=sd, plan=plan, horizon_s=H,
                                             variant=f"skip_ahead={int(skip)}",
                                             engine_overrides={"skip_ahead": skip},
                                             meta={"lam": lam, "lam_mult": m}))
        else:
            for pol in pols:
                for sd in e1["seeds"]:
                    specs.append(RunSpec(exp=name, policy=pol, seed=sd, plan=plan, horizon_s=H, variant="base",
                                         meta={"lam": lam, "lam_mult": m}))
            for pol in policy_list(cfg, e1["robust_policies"]):      # lognormal tool-time robustness
                for sd in e1["robust_seeds"]:
                    specs.append(RunSpec(exp=name, policy=pol, seed=sd, plan=plan, horizon_s=H, variant="lognormal",
                                         workload_overrides={"tool_time_dist": "lognormal",
                                                             "tool_time_cv": e1["robust_cv"]},
                                         meta={"lam": lam, "lam_mult": m}))
    out = new_result_dir(args.out_root, f"prefix_meta_{name}" + ("_quick" if args.quick else ""))
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    t_end = time.time()
    runs, wins, qts = collect_frames(results, specs)
    rq = e1.get("recovered_queue_below", 20.0)
    rh = e1.get("recovered_hit_above", 0.8)
    runs = add_recovery_columns(runs, wins, cfg, H, rq, rh)
    save_frames(out, runs, wins, qts)
    table = recovery_table(runs)
    table.to_csv(out / f"{name}_recovery_table.csv", index=False)
    largest = largest_recovered(table)
    largest.to_csv(out / f"{name}_largest_recovered_lambda.csv", index=False)
    save_configs(out, args.config, {**cfg, f"{name}_effective": e1, "calibration": _calib_public(calib)})
    write_meta(out, experiment=name, argv=sys.argv, seeds=sorted(set(int(s) for s in runs["seed"])),
               t_start=t_start, t_end=t_end, repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "workers": args.workers, "n_runs": int(len(runs)),
                      "timing": timing_summary(runs), "calibration": _calib_public(calib),
                      "lam_mults_skipped_because_ge_lambda_cap": skipped, "N_star": calib.get("session_cap_N_star")})
    print(table.to_string())
    print(largest.to_string())
    print("timing:", timing_summary(runs))
    print("result dir:", out)
    return out


def _calib_public(calib: Dict[str, Any]) -> Dict[str, Any]:
    return {k: calib.get(k) for k in ("lambda_miss", "lambda_cap", "R", "session_cap_N_star", "_path")}


# ======================================================================= E2 burst
def cmd_e2(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any]) -> Path:
    t_start = time.time()
    e2 = exp_cfg(cfg, "e2", args.quick)
    lam_miss, lam_cap = calib["lambda_miss"], calib["lambda_cap"]
    lam = e2["lam_mult"] * lam_miss
    tb = e2["warmup_s"]
    H = tb + e2["after_s"]
    pols = policy_list(cfg, e2["policies"])
    plan = ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=e2["burst_sessions"], burst_t0=tb,
                       burst_width_s=e2["burst_width_s"])
    specs = [RunSpec(exp="e2", policy=p, seed=sd, plan=plan, horizon_s=H,
                     meta={"lam": lam, "lam_mult": e2["lam_mult"], "t_burst": tb})
             for p in pols for sd in e2["seeds"]]
    out = new_result_dir(args.out_root, "prefix_meta_e2" + ("_quick" if args.quick else ""))
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    t_end = time.time()
    runs, wins, qts = collect_frames(results, specs)
    W = cfg["metrics"]["window_s"]
    ev_from, ev_to = tb + e2["hit_eval_from_s"], tb + e2["after_s"]
    extra_cols = []
    for rid in runs["run_id"]:
        w = wins[wins["run_id"] == rid].sort_values("t_start")
        ts = tail_stats(w.to_dict("records"), ev_from, ev_to)
        post = w[w["t_start"] >= tb]
        run_win = longest_run_below(post["hit_rate"].tolist(), e2["trap_hit_below"])
        extra_cols.append({"run_id": rid, "hit_eval": ts["hit_rate"], "queue_eval_mean": ts["queue_mean"],
                           "trap_run_s": run_win * W,
                           "trapped": bool(run_win * W >= e2["trap_min_s"]),
                           "hit_returned": bool(ts["hit_rate"] > e2["recovered_hit_above"])})
    runs = runs.merge(pd.DataFrame(extra_cols), on="run_id")
    runs["queue_returned"] = runs["tail_queue_mean"] < e2["recovered_queue_below"]
    runs["recovered_e2"] = runs["hit_returned"] & runs["queue_returned"]
    save_frames(out, runs, wins, qts)
    tab = runs.groupby("policy", sort=False).agg(
        n_runs=("seed", "size"), n_trapped=("trapped", "sum"), n_hit_returned=("hit_returned", "sum"),
        n_queue_returned=("queue_returned", "sum"), n_recovered=("recovered_e2", "sum"),
        hit_eval_mean=("hit_eval", "mean"), hit_eval_min=("hit_eval", "min"), hit_eval_max=("hit_eval", "max"),
        tail_queue_mean=("tail_queue_mean", "mean")).reset_index()
    tab.to_csv(out / "e2_summary.csv", index=False)
    save_configs(out, args.config, {**cfg, "e2_effective": e2, "calibration": _calib_public(calib)})
    write_meta(out, experiment="e2", argv=sys.argv, seeds=sorted(set(int(s) for s in runs["seed"])),
               t_start=t_start, t_end=t_end, repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "workers": args.workers, "n_runs": int(len(runs)),
                      "timing": timing_summary(runs), "calibration": _calib_public(calib),
                      "lam": lam, "lam_ge_lambda_cap": bool(lam >= lam_cap), "eval_window": [ev_from, ev_to]})
    print(tab.to_string())
    print("timing:", timing_summary(runs))
    print("result dir:", out)
    return out


# ======================================================================= E3 ramp
def hysteresis_area(up: np.ndarray, dn: np.ndarray, lam_up: np.ndarray, lam_dn: np.ndarray,
                    lo: float, hi: float, n_grid: int) -> float:
    """Normalized integral of |f_up(lam) - f_down(lam)| over [lo, hi] (np.interp on a common grid)."""
    grid = np.linspace(lo, hi, n_grid)
    ou, od = np.argsort(lam_up), np.argsort(lam_dn)
    f_up = np.interp(grid, lam_up[ou], up[ou])
    f_dn = np.interp(grid, lam_dn[od], dn[od])
    return float(np.trapz(np.abs(f_up - f_dn), grid) / (hi - lo))


def cmd_e3(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any]) -> Path:
    t_start = time.time()
    e3 = exp_cfg(cfg, "e3", args.quick)
    lam_miss, lam_cap = calib["lambda_miss"], calib["lambda_cap"]
    lo = e3["lo_mult_of_lambda_miss"] * lam_miss
    hi = e3["hi_mult_of_lambda_cap"] * lam_cap
    leg = e3["leg_s"]
    H = 2 * leg
    pols = policy_list(cfg, e3["policies"])
    plan = ArrivalPlan(kind="triangle", horizon_s=H, rate_lo=lo, rate_hi=hi, ramp_s=leg)
    specs = [RunSpec(exp="e3", policy=p, seed=sd, plan=plan, horizon_s=H,
                     meta={"lam": float("nan"), "lam_mult": float("nan")})
             for p in pols for sd in e3["seeds"]]
    out = new_result_dir(args.out_root, "prefix_meta_e3" + ("_quick" if args.quick else ""))
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    t_end = time.time()
    W = cfg["metrics"]["window_s"]
    for res in results:           # annotate windows with the instantaneous lambda at the window midpoint
        extra = {}
        for w in res["windows"]:
            mid = 0.5 * (w["t_start"] + w["t_end"])
            extra[w["window"]] = {"lam_window": float(triangle_rate(np.array([mid]), lo, hi, leg)[0]),
                                  "leg": "up" if mid <= leg else "down"}
        res["window_extra"] = extra
    runs, wins, qts = collect_frames(results, specs)
    save_frames(out, runs, wins, qts)
    rows = []
    for pol in pols:
        per_seed = []
        for sd in e3["seeds"]:
            w = wins[(wins["policy"] == pol) & (wins["seed"] == sd)]
            u, d = w[w["leg"] == "up"].dropna(subset=["hit_rate"]), w[w["leg"] == "down"].dropna(subset=["hit_rate"])
            if len(u) < 2 or len(d) < 2:
                continue
            per_seed.append(hysteresis_area(u["hit_rate"].to_numpy(), d["hit_rate"].to_numpy(),
                                            u["lam_window"].to_numpy(), d["lam_window"].to_numpy(),
                                            lo, hi, int(e3["grid_points"])))
        wp = wins[wins["policy"] == pol]
        rows.append({"policy": pol, "n_seeds": len(per_seed),
                     "hysteresis_area_mean": float(np.mean(per_seed)) if per_seed else float("nan"),
                     "hysteresis_area_per_seed": json.dumps([round(x, 4) for x in per_seed]),
                     "hit_up_mean": float(wp[wp["leg"] == "up"]["hit_rate"].mean()),
                     "hit_down_mean": float(wp[wp["leg"] == "down"]["hit_rate"].mean()),
                     "turns_per_s_up_mean": float(wp[wp["leg"] == "up"]["turns_per_s"].mean()),
                     "turns_per_s_down_mean": float(wp[wp["leg"] == "down"]["turns_per_s"].mean())})
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "e3_hysteresis.csv", index=False)
    save_configs(out, args.config, {**cfg, "e3_effective": e3, "calibration": _calib_public(calib)})
    write_meta(out, experiment="e3", argv=sys.argv, seeds=sorted(set(int(s) for s in runs["seed"])),
               t_start=t_start, t_end=t_end, repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "workers": args.workers, "n_runs": int(len(runs)),
                      "timing": timing_summary(runs), "calibration": _calib_public(calib),
                      "lam_lo": lo, "lam_hi": hi})
    print(tab.to_string())
    print("timing:", timing_summary(runs))
    print("result dir:", out)
    return out


# ======================================================================= E4 escape
def cmd_e4(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any]) -> Path:
    t_start = time.time()
    e4 = exp_cfg(cfg, "e4", args.quick)
    lam_miss, lam_cap = calib["lambda_miss"], calib["lambda_cap"]
    H = e4["horizon_s"]
    pols = policy_list(cfg, e4["policies"])
    specs, above_cap = [], []
    for m in e4["lam_mults"]:          # spec: lambda in {2,3} x lambda_miss; NOT restricted to < lambda_cap (flagged)
        lam = m * lam_miss
        if lam >= lam_cap:
            above_cap.append(m)
        for p in pols:
            for sd in e4["seeds"]:
                specs.append(RunSpec(exp="e4", policy=p, seed=sd, horizon_s=H,
                                     plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam),
                                     stop_queue_above=int(e4["escape_queue_above"]),
                                     meta={"lam": lam, "lam_mult": m}))
    out = new_result_dir(args.out_root, "prefix_meta_e4" + ("_quick" if args.quick else ""))
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    t_end = time.time()
    runs, wins, qts = collect_frames(results, specs)
    runs["escaped"] = runs["stopped_early"].astype(bool)
    runs["escape_time_s"] = np.where(runs["escaped"], runs["stop_time"], np.nan)
    save_frames(out, runs, wins, qts)
    g = runs.groupby(["policy", "lam_mult"], sort=False)
    tab = g.agg(n_runs=("seed", "size"), n_escaped=("escaped", "sum"),
                escape_time_median=("escape_time_s", "median"), escape_time_min=("escape_time_s", "min"),
                max_queue_good_state_max=("max_queue_pre_stop", "max"),
                max_queue_good_state_mean=("max_queue_pre_stop", "mean"),
                hit_rate_all_mean=("hit_rate_all", "mean")).reset_index()
    tab.to_csv(out / "e4_summary.csv", index=False)
    save_configs(out, args.config, {**cfg, "e4_effective": e4, "calibration": _calib_public(calib)})
    write_meta(out, experiment="e4", argv=sys.argv, seeds=sorted(set(int(s) for s in runs["seed"])),
               t_start=t_start, t_end=t_end, repo_dir=repo_dir,
               extra={"quick": bool(args.quick), "workers": args.workers, "n_runs": int(len(runs)),
                      "timing": timing_summary(runs), "calibration": _calib_public(calib),
                      "lam_mults_at_or_above_lambda_cap_but_run_anyway": above_cap})
    print(tab.to_string())
    print("timing:", timing_summary(runs))
    print("result dir:", out)
    return out


# ======================================================================= decision rule
def evaluate_decision(cfg: dict, e0: Dict[str, Any], e1_runs: pd.DataFrame, e2_runs: pd.DataFrame) -> Dict[str, Any]:
    """Apply the spec's GO / REFRAME / KILL rule to E0 + E1 + E2 outputs. Pure function of its inputs."""
    d = cfg["decision"]
    R = float(e0["R"])
    e1b = e1_runs[e1_runs["variant"] == "base"]
    table = recovery_table(e1b)
    largest = largest_recovered(table).set_index("policy")["largest_lam_mult_all_seeds_recovered"].to_dict()

    def n_rec(pol: str, m: float) -> Tuple[int, int]:
        r = table[(table["policy"] == pol) & np.isclose(table["lam_mult"], m)]
        return (int(r["n_recovered"].iloc[0]), int(r["n_runs"].iloc[0])) if len(r) else (-1, 0)

    ok_mults = []
    for m in sorted(table["lam_mult"].unique()):
        if m < d["lam_mult_min"] - 1e-9:
            continue
        lpm, nl = n_rec("lpm", m)
        fc, _ = n_rec("fcfs", m)
        l128, _ = n_rec("lpm128", m)
        if nl > 0 and lpm >= d["lpm_recover_min"] and fc <= d["fcfs_recover_max"] and 0 <= l128 <= d["lpm128_recover_max"]:
            ok_mults.append(float(m))
    e2l128 = e2_runs[e2_runs["policy"] == "lpm128"]
    e2lpm = e2_runs[e2_runs["policy"] == "lpm"]
    n_trapped = int(e2l128["trapped"].sum())
    n_lpm_back = int(e2lpm["hit_returned"].sum())
    lpm_big, ag30 = largest.get("lpm", float("nan")), largest.get("aging30", float("nan"))
    ag_ok = bool(lpm_big == lpm_big and ag30 == ag30 and ag30 >= d["aging30_fraction_of_lpm_lambda"] * lpm_big)
    items = {
        "R_ge_2": {"pass": R >= d["go_R_min"], "R": R},
        "recovery_split_at_lam_ge_1.5": {"pass": len(ok_mults) > 0, "lam_mults_satisfying": ok_mults,
                                         "note": "LPM 3/3, FCFS 0/3, LPM-128 <=1/3 recovered (E1 base variant)"},
        "burst_traps_lpm128": {"pass": n_trapped >= d["burst_lpm128_trapped_min"],
                               "n_trapped": n_trapped, "n_runs": int(len(e2l128))},
        "burst_lpm_returns": {"pass": n_lpm_back >= d["burst_lpm_recover_min"],
                              "n_hit_returned": n_lpm_back, "n_runs": int(len(e2lpm))},
        "aging30_keeps_70pct_of_lpm_lambda": {"pass": ag_ok, "lpm_largest_lam_mult": lpm_big,
                                              "aging30_largest_lam_mult": ag30},
    }
    lpm128_ever_trapped = bool((e1b[e1b["policy"] == "lpm128"]["recovered"] == False).any()) or n_trapped > 0  # noqa: E712
    lpm_recovers_somewhere = bool(any(n_rec("lpm", m)[0] >= d["lpm_recover_min"] for m in table["lam_mult"].unique()
                                      if m >= d["lam_mult_min"] - 1e-9))
    go = all(v["pass"] for v in items.values())
    kill = (R < d["kill_R_below"]) or (not lpm128_ever_trapped)
    reframe = (R >= d["go_R_min"]) and (not lpm_recovers_somewhere)
    verdict = "GO" if go else ("KILL" if kill else ("REFRAME" if reframe else "NEITHER (some GO items fail; not KILL/REFRAME)"))
    return {"verdict": verdict, "items": items, "kill_conditions": {"R_below_1.5": R < d["kill_R_below"],
            "lpm128_never_trapped": not lpm128_ever_trapped},
            "reframe_condition": {"R_ge_2_and_LPM_never_recovers_3of3_at_lam_ge_1.5": reframe}}


def cmd_decision(cfg: dict, args: argparse.Namespace, repo_dir: Path, calib: Dict[str, Any]) -> Path:
    t_start = time.time()
    root = Path(args.out_root)

    def latest(name: str) -> Path:
        c = sorted((root / name).glob("*/runs.csv"))
        if not c:
            raise FileNotFoundError(f"no result for {name}")
        return c[-1].parent

    d1 = Path(args.e1_dir) if args.e1_dir else latest("prefix_meta_e1")
    d2 = Path(args.e2_dir) if args.e2_dir else latest("prefix_meta_e2")
    e1 = pd.read_csv(d1 / "runs.csv")
    e2 = pd.read_csv(d2 / "runs.csv")
    dec = evaluate_decision(cfg, calib, e1, e2)
    out = new_result_dir(args.out_root, "prefix_meta_decision")
    dec["inputs"] = {"e0": calib.get("_path"), "e1": str(d1), "e2": str(d2)}
    (out / "decision.json").write_text(json.dumps(sanitize(dec), indent=2))
    save_configs(out, args.config, cfg)
    write_meta(out, experiment="decision", argv=sys.argv, seeds=[], t_start=t_start, t_end=time.time(),
               repo_dir=repo_dir, extra={"inputs": dec["inputs"]})
    print(json.dumps(sanitize(dec), indent=2))
    return out


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Prefix-cache metastability pilot (simulation)")
    ap.add_argument("cmd", choices=["e0", "e1", "e2", "e3", "e4", "ablation", "decision"])
    ap.add_argument("--config", default="configs/prefix_meta.yaml")
    ap.add_argument("--quick", action="store_true", help="smoke-test sizes (shorter horizons, fewer seeds)")
    ap.add_argument("--workers", type=int, default=3, help="processes (hard-capped by config parallel.max_workers)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--calib", default=None, help="E0 result dir or e0_summary.json (default: newest non-quick E0)")
    ap.add_argument("--e1-dir", default=None)
    ap.add_argument("--e2-dir", default=None)
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    repo_dir = repo_dir or Path(args.config).resolve().parent.parent
    if args.cmd == "e0":
        cmd_e0(cfg, args, repo_dir)
        return 0
    calib = load_calibration(args.calib, args.out_root)
    if args.cmd == "e1":
        cmd_e1(cfg, args, repo_dir, calib)
    elif args.cmd == "ablation":
        cmd_e1(cfg, args, repo_dir, calib, ablation=True)
    elif args.cmd == "e2":
        cmd_e2(cfg, args, repo_dir, calib)
    elif args.cmd == "e3":
        cmd_e3(cfg, args, repo_dir, calib)
    elif args.cmd == "e4":
        cmd_e4(cfg, args, repo_dir, calib)
    elif args.cmd == "decision":
        cmd_decision(cfg, args, repo_dir, calib)
    return 0
