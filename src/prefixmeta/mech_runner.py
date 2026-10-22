"""Round-2 experiments for the prefix-cache metastability pilot: phase diagram (``phase``), mechanisms vs the trap
(``mech``), escape-time scaling (``escape``), workload robustness (``robust``) and the pre-registered prediction
evaluation (``evaluate``).

Every command creates a NEW ``results/<name>/<YYYYmmdd-HHMMSS>/`` directory holding ``config.yaml`` (copy of the
round-2 config), ``base_config.yaml``, ``config_effective.yaml``, ``preregistration.yaml`` (copy of the committed
predictions), ``meta.json`` (git commit + dirty flag captured at the START of the run, written first as
``status: running`` and completed at the end), ``runs.csv`` / ``windows.csv`` / ``qtrace.csv`` and the
experiment-specific tables. Nothing existing is ever overwritten.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from . import runner as R1
from .metrics import first_good_window, longest_run_below, tail_stats, trailing_low_hit_onset, trend_rise
from .runner import (HARDWARE, Runner, apply_overrides, collect_frames, env_versions, git_info, new_result_dir,
                     sanitize, save_frames, timing_summary)
from .sim import RunSpec, deep_update, load_config
from .survival import km_median_ci, summarize_escape
from .workload import (ArrivalPlan, WorkloadParams, length_biased_mean_context, length_biased_session_cap)


# ======================================================================= config / provenance
def load_mech_config(path: str, repo_dir: Path) -> dict:
    """Round-2 config merged over its ``base_config`` (the round-2 file wins; dicts merge, lists replace)."""
    top = load_config(path)
    base_rel = top.get("base_config")
    base = load_config(str(repo_dir / base_rel)) if base_rel else {}
    merged = deep_update(base, {k: v for k, v in top.items() if k != "base_config"})
    return merged


def exp_cfg_deep(cfg: dict, name: str, quick: bool) -> dict:
    """Section ``name`` of the config; with ``quick`` the section's ``quick`` block is deep-merged over it."""
    c = dict(cfg[name])
    q = c.pop("quick", {})
    return deep_update(c, q) if quick else c


@dataclass
class Ctx:
    experiment: str
    out: Path
    t_start: float
    git_start: Dict[str, Any]
    argv: List[str]
    args: argparse.Namespace
    extra: Dict[str, Any] = field(default_factory=dict)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(sanitize(obj), indent=2, default=R1._json_default))


def begin(experiment: str, name: str, cfg: dict, cfg_effective: dict, args: argparse.Namespace,
          repo_dir: Path) -> Ctx:
    """Create the result dir, capture git state NOW, copy configs + preregistration, write a provisional meta.json."""
    t0 = time.time()
    git0 = git_info(repo_dir)
    out = new_result_dir(args.out_root, R1.out_name(name, args))
    shutil.copyfile(args.config, out / "config.yaml")
    base_rel = load_config(args.config).get("base_config")
    if base_rel:
        shutil.copyfile(repo_dir / base_rel, out / "base_config.yaml")
    prereg = cfg.get("preregistration_file")
    if prereg and (repo_dir / prereg).exists():
        shutil.copyfile(repo_dir / prereg, out / "preregistration.yaml")
    (out / "config_effective.yaml").write_text(yaml.safe_dump(cfg_effective, sort_keys=False))
    ctx = Ctx(experiment=experiment, out=out, t_start=t0, git_start=git0, argv=list(sys.argv), args=args)
    _write_json(out / "meta.json", {"experiment": experiment, "status": "running", "argv": ctx.argv, "git": git0,
                                    "hardware": HARDWARE, "hostname": socket.gethostname(),
                                    "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0))})
    return ctx


def finish(ctx: Ctx, seeds: Sequence[int], extra: Dict[str, Any]) -> None:
    t1 = time.time()
    meta = {"experiment": ctx.experiment, "status": "done", "argv": ctx.argv,
            "git": ctx.git_start,                                    # captured at the START of the run
            "seeds": sorted(set(int(s) for s in seeds)), "versions": env_versions(),
            "hostname": socket.gethostname(), "hardware": HARDWARE,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ctx.t_start)),
            "end_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t1)), "wall_s": t1 - ctx.t_start,
            "quick": bool(ctx.args.quick), "workers": ctx.args.workers,
            "overrides": list(getattr(ctx.args, "set", None) or []), "tag": getattr(ctx.args, "tag", None)}
    meta.update(extra)
    _write_json(ctx.out / "meta.json", meta)


def base_calibration(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Dict[str, Any]:
    """lambda_miss (and the round-1 LPM lambda_cap, reference only) of the BASE workload from the round-1 E0 result."""
    path = Path(args.calib) if getattr(args, "calib", None) else repo_dir / cfg["calibration"]["e0_summary"]
    if path.is_dir():
        path = path / "e0_summary.json"
    d = json.loads(path.read_text())
    wl = WorkloadParams.from_dict(cfg["workload"])
    M = float(cfg["engine"]["kv_memory_tokens"])
    return {"lambda_miss": float(d["lambda_miss"]), "lambda_cap_lpm_round1": float(d["lambda_cap"]),
            "R_round1": float(d["R"]), "N_lb": length_biased_session_cap(M, wl),
            "E_lb": length_biased_mean_context(wl), "_path": str(path)}


def _meta(lam: float, mult: float, **kw: Any) -> Dict[str, Any]:
    return {"lam": lam, "lam_mult": mult, **kw}


# ======================================================================= recovery / burst classification
def add_recovery(runs: pd.DataFrame, hit_above: float, backlog_below: float) -> pd.DataFrame:
    """``recovered`` = tail hit rate > hit_above AND tail backlog (waiting queue + gate queue) < backlog_below.
    ``recovered_queue_only`` ignores the gate (the round-1 ``recovered``)."""
    r = runs.copy()
    r["recovered"] = (r["tail_hit_rate"] > hit_above) & (r["tail_backlog_mean"] < backlog_below)
    r["recovered_queue_only"] = (r["tail_hit_rate"] > hit_above) & (r["tail_queue_mean"] < backlog_below)
    return r


def recovery_counts(runs: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    g = runs.groupby(list(keys), sort=False)
    return g.agg(n_runs=("recovered", "size"), n_recovered=("recovered", "sum"),
                 n_recovered_queue_only=("recovered_queue_only", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
                 tail_queue_mean=("tail_queue_mean", "mean"), tail_gate_mean=("tail_gate_mean", "mean"),
                 tail_sessions_per_s=("tail_sessions_per_s", "mean"),
                 n_stopped_early=("stopped_early", "sum")).reset_index()


def burst_columns(runs: pd.DataFrame, wins: pd.DataFrame, b: dict, W: float, tb: float) -> pd.DataFrame:
    """Per-run burst metrics (the round-1 E2 trap criterion, with backlog = queue + gate for the recovery test):
    trapped = hit rate < trap_hit_below in >= trap_min_s of CONSECUTIVE windows from the burst on;
    burst_recovered = hit rate over [tb + hit_eval_from_s, tb + after_s] > recovered_hit_above and tail backlog <
    recovered_backlog_below; otherwise 'partial'."""
    ev_from, ev_to = tb + b["hit_eval_from_s"], tb + b["after_s"]
    by_run = {rid: g.sort_values("t_start") for rid, g in wins.groupby("run_id")}
    cols = []
    for rid in runs["run_id"]:
        w = by_run[rid]
        ts = tail_stats(w.to_dict("records"), ev_from, ev_to)
        post = w[w["t_start"] >= tb]
        run_win = longest_run_below(post["hit_rate"].tolist(), b["trap_hit_below"])
        cols.append({"run_id": rid, "hit_eval": ts["hit_rate"], "queue_eval_mean": ts["queue_mean"],
                     "trap_run_s": run_win * W, "trapped": bool(run_win * W >= b["trap_min_s"]),
                     "hit_returned": bool(ts["hit_rate"] > b["recovered_hit_above"])})
    out = runs.merge(pd.DataFrame(cols), on="run_id")
    out["backlog_returned"] = out["tail_backlog_mean"] < b["recovered_backlog_below"]
    out["burst_recovered"] = out["hit_returned"] & out["backlog_returned"]
    out["burst_outcome"] = np.where(out["trapped"], "trapped", np.where(out["burst_recovered"], "recovered", "partial"))
    return out


def burst_counts(runs: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    g = runs.groupby(list(keys), sort=False)
    out = g.agg(n_runs=("seed", "size"), n_trapped=("trapped", "sum"), n_burst_recovered=("burst_recovered", "sum"),
                hit_eval_mean=("hit_eval", "mean"), hit_eval_min=("hit_eval", "min"),
                hit_eval_max=("hit_eval", "max"), tail_backlog_mean=("tail_backlog_mean", "mean")).reset_index()
    # strict reading (amendment 2): a burst run that did not return to hit > 0.8 AND backlog < 20 counts as congested
    out["n_not_burst_recovered"] = out["n_runs"] - out["n_burst_recovered"]
    return out


# ======================================================================= lambda_miss and stable limits
def miss_specs(population: int, seeds: Sequence[int], horizon: float, pool: int,
               workload_overrides: Optional[dict] = None, engine_overrides: Optional[dict] = None,
               exp: str = "calib_miss", variant: str = "base") -> List[RunSpec]:
    """Closed-population, caching disabled, FCFS: the all-miss capacity (round-1 E0 procedure)."""
    eo = {"cache_enabled": False, **(engine_overrides or {})}
    return [RunSpec(exp=exp, policy="fcfs", seed=s, horizon_s=horizon,
                    plan=ArrivalPlan(kind="closed", horizon_s=horizon, closed_n=population, pool=pool),
                    engine_overrides=eo, workload_overrides=dict(workload_overrides or {}), variant=variant,
                    meta={"lam": float("nan"), "lam_mult": float("nan"), "population": population})
            for s in seeds]


def measure_lambda_miss(R: Runner, cfg: dict, population: int, seeds: Sequence[int], horizon: float, warmup: float,
                        pool: int, workload_overrides: Optional[dict] = None,
                        engine_overrides: Optional[dict] = None, variant: str = "base"
                        ) -> Tuple[float, List[float], List[RunSpec], List[Dict[str, Any]]]:
    specs = miss_specs(population, seeds, horizon, pool, workload_overrides, engine_overrides, variant=variant)
    res = R.run(specs)
    W = cfg["metrics"]["window_s"]
    per_seed = [R1.miss_throughput(r, warmup, W)["sessions_per_s"] for r in res]
    return float(np.mean(per_seed)), per_seed, specs, res


def backlog_verdict(res: Dict[str, Any], lim: dict) -> Dict[str, Any]:
    """Stability of a run from an empty start: not early-stopped, final backlog (queue + gate) below a bound and no
    upward trend of the backlog over the last window (the E0 criterion generalised to gated policies)."""
    s = res["summary"]
    end = s["sim_end_s"]
    Wt = min(lim["stable_trend_window_s"], end / 2.0)
    rise = trend_rise(res["btrace"], end - Wt, end)
    fb_ok = s["final_backlog"] < lim["stable_final_backlog_below"]
    rise_ok = bool(rise == rise and rise <= lim["stable_trend_max_rise"])
    stable = (not s["stopped_early"]) and fb_ok and rise_ok
    return {"stable": bool(stable), "final_backlog": s["final_backlog"], "trend_rise": rise,
            "tail_backlog_mean": s["tail_backlog_mean"], "tail_hit_rate": s["tail_hit_rate"],
            "stopped_early": s["stopped_early"], "stop_reason": s["stop_reason"],
            "tail_busy_frac": s["tail_busy_frac"], "tail_sessions_per_s": s["tail_sessions_per_s"]}


def find_stable_limit(R: Runner, cfg: dict, policy: str, lam_miss: float, lim: dict, *,
                      workload_overrides: Optional[dict] = None, engine_overrides: Optional[dict] = None,
                      variant: str = "base", exp: str = "limit"
                      ) -> Tuple[Dict[str, Any], List[RunSpec], List[Dict[str, Any]]]:
    """From-empty stable limit of ``policy`` (E0 procedure): bracket over {1} + bracket_mults times lambda_miss, then
    bisect to rel_tol. A lambda is stable iff ALL seeds are stable. Returns (summary, specs run, results)."""
    rows: List[Dict[str, Any]] = []
    all_specs: List[RunSpec] = []
    all_res: List[Dict[str, Any]] = []

    def test(lam: float, mult: float, phase: str) -> bool:
        specs = [RunSpec(exp=exp, policy=policy, seed=sd, horizon_s=lim["horizon_s"], variant=variant,
                         plan=ArrivalPlan(kind="constant", horizon_s=lim["horizon_s"], rate=lam),
                         stop_backlog_above=int(lim["unstable_backlog_stop"]),
                         workload_overrides=dict(workload_overrides or {}),
                         engine_overrides=dict(engine_overrides or {}),
                         meta={"lam": lam, "lam_mult": mult, "search_phase": phase}) for sd in lim["seeds"]]
        res = R.run(specs)
        all_specs.extend(specs)
        all_res.extend(res)
        verd = [backlog_verdict(r, lim) for r in res]
        for sp, v in zip(specs, verd):
            rows.append({"variant": variant, "policy": policy, "phase": phase, "lam": lam, "lam_mult": mult,
                         "seed": sp.seed, **v})
        return all(v["stable"] for v in verd)

    lo_m, hi_m = 0.0, None
    for m in [1.0] + list(lim["bracket_mults"]):
        if test(m * lam_miss, m, "bracket"):
            lo_m = m
        else:
            hi_m = m
            break
    if lo_m == 0.0 and lim.get("lower_mults"):
        # unstable already at lambda_miss (small systems): search downwards for a stable multiple
        for m in sorted(lim["lower_mults"], reverse=True):
            if test(m * lam_miss, m, "bracket_down"):
                lo_m = m
                break
            hi_m = m
    unbounded = hi_m is None
    if not unbounded:
        lo, hi = lo_m * lam_miss, hi_m * lam_miss
        for _ in range(int(lim["max_bisect_steps"])):
            if lo > 0 and (hi - lo) <= lim["rel_tol"] * lo:
                break
            mid = 0.5 * (lo + hi)
            if test(mid, mid / lam_miss, "bisect"):
                lo = mid
            else:
                hi = mid
        lam_cap, bracket = lo, [lo, hi]
    else:
        lam_cap = lo_m * lam_miss
        bracket = [lam_cap, float("inf")]
    summary = {"variant": variant, "policy": policy, "lambda_miss": lam_miss, "lambda_cap": lam_cap,
               "lam_cap_mult": lam_cap / lam_miss, "bracket_lo": bracket[0], "bracket_hi": bracket[1],
               "unbounded_in_search": bool(unbounded), "n_search_runs": len(all_res), "search_rows": rows}
    return summary, all_specs, all_res


def strip_for_storage(res: Dict[str, Any]) -> Dict[str, Any]:
    """Search runs keep only the summary (windows / traces would dominate the output size)."""
    return {"summary": res["summary"], "windows": [], "qtrace": []}


# ======================================================================= good-state capacity (P6, amendment 2)
def capacity_by_population(rows: pd.DataFrame) -> pd.DataFrame:
    """Mean / sd over seeds of the post-warmup closed-population throughput, per (policy, population)."""
    g = rows.groupby(["policy", "population"], sort=False)
    return g.agg(n_seeds=("seed", "size"), sessions_per_s=("sessions_per_s", "mean"),
                 sessions_per_s_sd=("sessions_per_s", "std"), turns_per_s=("turns_per_s", "mean"),
                 hit_rate=("hit_rate", "mean"), busy_frac=("busy_frac", "mean")).reset_index()


def capacity_ceilings(by_pop: pd.DataFrame, ref: str = "lpm") -> pd.DataFrame:
    """Good-state throughput ceiling of each policy = max over the population grid of the seed-mean closed-population
    throughput (sessions/s), the population attaining it, and the ratio to the ``ref`` policy's ceiling. The max over
    populations is deliberately generous to work-conserving policies (it picks their best-case population) and so
    biases the ratio of a cap / pin policy DOWN, i.e. against the hypothesis."""
    rows = []
    for pol, g in by_pop.groupby("policy", sort=False):
        i = g["sessions_per_s"].idxmax()
        rows.append({"policy": pol, "ceiling_sessions_per_s": float(g.loc[i, "sessions_per_s"]),
                     "population_at_ceiling": int(g.loc[i, "population"]),
                     "hit_rate_at_ceiling": float(g.loc[i, "hit_rate"]),
                     "throughput_at_largest_population": float(g.sort_values("population")["sessions_per_s"].iloc[-1])})
    out = pd.DataFrame(rows)
    r = out.loc[out["policy"] == ref, "ceiling_sessions_per_s"]
    out["ratio_to_" + ref] = out["ceiling_sessions_per_s"] / float(r.iloc[0]) if len(r) else float("nan")
    return out


# ======================================================================= phase
def phase_horizon(ph: dict, mult: float) -> float:
    """Horizon of a phase run at ``mult`` x lambda_miss: ``long_horizon_s`` for mult <= ``long_horizon_up_to_mult``
    (recovery just below lambda_miss takes 12k-73k s, round-2 review finding 7), else ``horizon_s``."""
    lh, up = ph.get("long_horizon_s"), ph.get("long_horizon_up_to_mult")
    if lh is not None and up is not None and mult <= float(up) + 1e-9:
        return float(lh)
    return float(ph["horizon_s"])


def phase_derived(runs: pd.DataFrame, wins: pd.DataFrame, ph: dict) -> pd.DataFrame:
    """Per-run derived columns, all computed from the recorded windows: ``recovered_registered_horizon`` (the same
    criterion applied to the last ``tail`` seconds of the REGISTERED horizon ``horizon_s``, which is how the prediction
    would have been judged without the long-horizon fix) and ``t_first_good_s`` (start of the first window with hit
    rate > recovered_hit_above and backlog < recovered_backlog_below)."""
    H0 = float(ph["horizon_s"])
    tail = float(ph.get("registered_tail_s", 5000.0))
    by_run = {rid: g.sort_values("t_start").to_dict("records") for rid, g in wins.groupby("run_id")}
    ha, bb = ph["recovered_hit_above"], ph["recovered_backlog_below"]
    reg, tfg = [], []
    for rid in runs["run_id"]:
        w = by_run[rid]
        ts = tail_stats(w, H0 - tail, H0)
        reg.append(bool(ts["n_windows"] > 0 and ts["hit_rate"] > ha and ts["queue_mean"] + ts["gate_mean"] < bb))
        tfg.append(first_good_window(w, ha, bb))
    out = runs.copy()
    out["recovered_registered_horizon"] = reg
    out["t_first_good_s"] = tfg
    return out


def cmd_phase(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    ph = exp_cfg_deep(cfg, "phase", args.quick)
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("phase", "prefix_meta_phase", cfg, {**cfg, "phase_effective": ph, "calibration": cal}, args, repo_dir)
    lam_miss, cold = cal["lambda_miss"], ph["cold_sessions"]
    specs = [RunSpec(exp="phase", policy=p, seed=sd, horizon_s=phase_horizon(ph, m), variant="cold",
                     plan=ArrivalPlan(kind="constant", horizon_s=phase_horizon(ph, m), rate=m * lam_miss,
                                      initial_cold=cold),
                     meta=_meta(m * lam_miss, m, cold_sessions=cold, horizon_used_s=phase_horizon(ph, m)))
             for m in ph["lam_mults"] for p in ph["policies"] for sd in ph["seeds"]]
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, ph["recovered_hit_above"], ph["recovered_backlog_below"])
    runs = phase_derived(runs, wins, ph)
    save_frames(ctx.out, runs, wins, qts)
    tab = recovery_counts(runs, ["policy", "lam_mult"])
    tab.insert(2, "lam", [m * lam_miss for m in tab["lam_mult"]])
    extra = runs.groupby(["policy", "lam_mult"], sort=False).agg(
        n_recovered_registered_horizon=("recovered_registered_horizon", "sum"),
        t_first_good_median_s=("t_first_good_s", "median"), n_first_good=("t_first_good_s", lambda x: int(x.notna().sum())),
        horizon_used_s=("horizon_used_s", "max")).reset_index()
    tab = tab.merge(extra, on=["policy", "lam_mult"])
    tab.to_csv(ctx.out / "phase_table.csv", index=False)
    finish(ctx, runs["seed"], {"calibration": cal, "n_runs": int(len(runs)), "timing": timing_summary(runs),
                               "lam_mults_ge_round1_lambda_cap": [m for m in ph["lam_mults"]
                                                                 if m * lam_miss >= cal["lambda_cap_lpm_round1"]]})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(tab.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= mech
def cmd_mech(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    mc = exp_cfg_deep(cfg, "mech", args.quick)
    if getattr(args, "only", None):
        mc["policies"] = [p for p in mc["policies"] if p in args.only]
        mc["limit"] = {**mc["limit"], "policies": [p for p in mc["limit"]["policies"] if p in args.only]}
        if mc.get("capacity"):
            mc["capacity"] = {**mc["capacity"], "policies": [p for p in mc["capacity"]["policies"] if p in args.only]}
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("mech", "prefix_meta_mech", cfg, {**cfg, "mech_effective": mc, "calibration": cal}, args, repo_dir)
    lam_miss = cal["lambda_miss"]
    W = cfg["metrics"]["window_s"]
    pols = mc["policies"]
    cd, bd, cs, lim, cp = mc["cold"], mc["burst"], mc.get("cap_sweep"), mc["limit"], mc.get("capacity")

    specs: List[RunSpec] = []
    parts: List[str] = []
    # (A) recovery from a cold start
    for m in cd["lam_mults"]:
        for p in pols:
            for sd in cd["seeds"]:
                specs.append(RunSpec(exp="mech", policy=p, seed=sd, horizon_s=cd["horizon_s"], variant="cold",
                                     plan=ArrivalPlan(kind="constant", horizon_s=cd["horizon_s"], rate=m * lam_miss,
                                                      initial_cold=cd["cold_sessions"]),
                                     meta=_meta(m * lam_miss, m, cold_sessions=cd["cold_sessions"])))
                parts.append("cold")
    # (B) burst on top of a good state
    tb = bd["warmup_s"]
    Hb = tb + bd["after_s"]
    lam_b = bd["lam_mult"] * lam_miss
    for p in pols:
        for sd in bd["seeds"]:
            specs.append(RunSpec(exp="mech", policy=p, seed=sd, horizon_s=Hb, variant="burst",
                                 plan=ArrivalPlan(kind="constant", horizon_s=Hb, rate=lam_b,
                                                  burst_n=bd["burst_sessions"], burst_t0=tb,
                                                  burst_width_s=bd["burst_width_s"]),
                                 meta=_meta(lam_b, bd["lam_mult"], t_burst=tb, burst_sessions=bd["burst_sessions"])))
            parts.append("burst")
    # (C) supplementary static-cap sweep (cliff)
    N_lb = cal["N_lb"]
    sweep_caps: List[int] = []
    if cs:
        sweep_caps = sorted({int(math.floor(x * N_lb)) for x in cs["mults_of_N_lb"]})
        for c in sweep_caps:
            for sd in cs["seeds"]:
                specs.append(RunSpec(exp="mech", policy="fcfs", seed=sd, horizon_s=cs["horizon_s"],
                                     variant=f"cap={c}", session_cap_override=c,
                                     plan=ArrivalPlan(kind="constant", horizon_s=cs["horizon_s"],
                                                      rate=cs["lam_mult"] * lam_miss, initial_cold=cs["cold_sessions"]),
                                     meta=_meta(cs["lam_mult"] * lam_miss, cs["lam_mult"],
                                                cold_sessions=cs["cold_sessions"], cap=c)))
                parts.append("capsweep")
    # (E) good-state capacity: closed population WITH the cache, throughput ceiling over the population grid
    cap_pols: List[str] = []
    if cp:
        cap_pols = list(cp["policies"])
        for p in cap_pols:
            for n_pop in cp["populations"]:
                for sd in cp["seeds"]:
                    specs.append(RunSpec(exp="mech", policy=p, seed=sd, horizon_s=cp["horizon_s"],
                                         variant=f"closedN={n_pop}",
                                         plan=ArrivalPlan(kind="closed", horizon_s=cp["horizon_s"], closed_n=int(n_pop),
                                                          pool=int(cp["pool_sessions"])),
                                         meta={"lam": float("nan"), "lam_mult": float("nan"),
                                               "population": int(n_pop)}))
                    parts.append("capacity")
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
        # (D) from-empty stable limits
        limit_summaries: List[Dict[str, Any]] = []
        limit_specs: List[RunSpec] = []
        limit_results: List[Dict[str, Any]] = []
        for p in lim["policies"]:
            summ, sp, rs = find_stable_limit(R, cfg, p, lam_miss, lim, exp="limit")
            limit_summaries.append(summ)
            limit_specs += sp
            limit_results += [strip_for_storage(r) for r in rs]

    # ---- assemble
    runs, wins, qts = collect_frames(results, specs)
    runs["part"] = parts
    # capacity rows: post-warmup closed-population throughput (before the windows of those runs are dropped)
    cap_rows: List[Dict[str, Any]] = []
    if cp:
        for res, rs, part in zip(results, specs, parts):
            if part != "capacity":
                continue
            thr = R1.miss_throughput(res, cp["warmup_s"], W)
            tl = tail_stats(res["windows"], cp["warmup_s"], rs.horizon_s)
            cap_rows.append({"policy": rs.policy, "population": rs.meta["population"], "seed": rs.seed,
                             "sessions_per_s": thr["sessions_per_s"], "turns_per_s": thr["turns_per_s"],
                             "hit_rate": tl["hit_rate"], "busy_frac": thr["busy_frac"]})
    runs = add_recovery(runs, cd["recovered_hit_above"], cd["recovered_backlog_below"])
    is_b = (runs["part"] == "burst").to_numpy()
    bruns = burst_columns(runs[is_b].reset_index(drop=True), wins, bd, W, tb)
    runs = runs.merge(bruns[["run_id", "hit_eval", "queue_eval_mean", "trap_run_s", "trapped", "hit_returned",
                             "backlog_returned", "burst_recovered", "burst_outcome"]], on="run_id", how="left")
    save_frames(ctx.out, runs, wins, qts)
    cold = runs[runs["part"] == "cold"]
    recovery_counts(cold, ["policy", "lam_mult"]).to_csv(ctx.out / "mech_cold_table.csv", index=False)
    bsub = runs[runs["part"] == "burst"].copy()
    bsub["trapped"] = bsub["trapped"].astype(bool)
    bsub["burst_recovered"] = bsub["burst_recovered"].astype(bool)
    burst_counts(bsub, ["policy", "lam_mult"]).to_csv(ctx.out / "mech_burst_table.csv", index=False)
    cap = runs[runs["part"] == "capsweep"]
    if len(cap):
        t = recovery_counts(cap, ["variant", "lam_mult"])
        t["cap"] = [int(v.split("=")[1]) for v in t["variant"]]
        t.to_csv(ctx.out / "mech_capsweep_table.csv", index=False)
    cap_ceil = None
    if cap_rows:
        cr = pd.DataFrame(cap_rows)
        cr.to_csv(ctx.out / "mech_capacity_runs.csv", index=False)
        bp = capacity_by_population(cr)
        bp.to_csv(ctx.out / "mech_capacity_by_population.csv", index=False)
        cap_ceil = capacity_ceilings(bp, "lpm")
        cap_ceil.to_csv(ctx.out / "mech_capacity.csv", index=False)
    lrows = [r for s_ in limit_summaries for r in s_["search_rows"]]
    pd.DataFrame(lrows).to_csv(ctx.out / "limit_search.csv", index=False)
    lt = pd.DataFrame([{k: v for k, v in s_.items() if k != "search_rows"} for s_ in limit_summaries])
    ref = lt[lt["policy"] == "lpm"]["lambda_cap"]
    lt["ratio_to_lpm"] = lt["lambda_cap"] / float(ref.iloc[0]) if len(ref) else float("nan")
    lt.to_csv(ctx.out / "mech_limits.csv", index=False)
    allspecs = specs + limit_specs
    finish(ctx, [rs.seed for rs in allspecs],
           {"calibration": cal, "n_runs": int(len(specs)), "n_limit_search_runs": len(limit_specs),
            "timing": timing_summary(runs), "N_lb": N_lb, "E_lb": cal["E_lb"], "cap_sweep_caps": sweep_caps,
            "cap_1p3": int(math.floor(1.3 * N_lb)), "lam_burst": lam_b, "capacity_policies": cap_pols})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(recovery_counts(cold, ["policy", "lam_mult"]).to_string())
        print(burst_counts(bsub, ["policy", "lam_mult"]).to_string())
        print(lt.drop(columns=[]).to_string())
        if cap_ceil is not None:
            print(cap_ceil.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= escape
def scaled_engine_overrides(engine_cfg: dict, k: float) -> Dict[str, Any]:
    """Engine overrides for a size-k system: M, chunk budget and max-running scaled by k, per-token costs divided
    by k (so the iteration time of a k-scaled population equals the base one), per-iteration constants unchanged."""
    if k <= 0:
        raise ValueError("k must be > 0")
    if engine_cfg.get("batching", "mixed") != "mixed":
        raise ValueError("k-scaling is defined for the shared (mixed) iteration-cost keys only; batching="
                         f"{engine_cfg['batching']!r} has per-iteration-type cost keys that this scaling does not touch")
    return {"kv_memory_tokens": float(engine_cfg["kv_memory_tokens"]) * k,
            "prefill_chunk_budget": max(1, int(round(engine_cfg["prefill_chunk_budget"] * k))),
            "max_running_seqs": max(1, int(round(engine_cfg["max_running_seqs"] * k))),
            "per_token_s": float(engine_cfg["per_token_s"]) / k,
            "decode_attn_s": float(engine_cfg["decode_attn_s"]) / k,
            "prefill_attn_s": float(engine_cfg["prefill_attn_s"]) / k}


def collapse_queue_threshold(engine_cfg: dict, wl: WorkloadParams, k: float, factor: float) -> int:
    """Collapse if the waiting queue exceeds ``factor * M_k / E_lb`` sessions (floor; the queue is an integer)."""
    return int(math.floor(factor * float(engine_cfg["kv_memory_tokens"]) * k / length_biased_mean_context(wl)))


def scale_limit_cfg(lim: dict, k: float) -> dict:
    """Stability thresholds of the from-empty limit search for a size-k system: the absolute backlog thresholds are
    multiplied by max(1, k) (identical to the unscaled E0 procedure for k <= 1; a size-4 system has 4x the sessions,
    so its steady-state backlog noise is larger)."""
    f = max(1.0, float(k))
    out = dict(lim)
    out["unstable_backlog_stop"] = int(round(lim["unstable_backlog_stop"] * f))
    out["stable_final_backlog_below"] = lim["stable_final_backlog_below"] * f
    out["stable_trend_max_rise"] = lim["stable_trend_max_rise"] * f
    return out


def escape_event_times(runs: pd.DataFrame, wins: pd.DataFrame, hit_below: float, window_s: float) -> pd.DataFrame:
    """Single, pre-specified event time of the escape experiments (round-2 review finding 9): the ONSET of the
    hit-rate collapse = start of the maximal trailing run of complete windows with hit rate < ``hit_below`` at the
    moment the run stopped. A hit-rule stop already is such an onset (``stop_time``); a queue-rule stop is
    later than the onset (the queue needs ~2000 s to cross its threshold), so the onset is recovered from the windows;
    if the last complete window before a queue stop is not below the threshold the crossing time is used (flagged).
    Adds ``stop_time_s``, ``onset_source``, ``escape_time_s``, ``obs_time_s``."""
    by_run = {rid: g.sort_values("t_start") for rid, g in wins.groupby("run_id")} if len(wins) else {}
    out = runs.copy()
    esc = out["stopped_early"].astype(bool).to_numpy()
    stop = out["stop_time"].to_numpy(dtype=float)
    reason = out["stop_reason"].astype(str).to_numpy()
    onset, source = [], []
    for i, rid in enumerate(out["run_id"]):
        if not esc[i]:
            onset.append(float("nan"))
            source.append("")
            continue
        w = by_run.get(rid)
        o = float("nan")
        if w is not None and len(w):
            o = trailing_low_hit_onset(w["t_start"].to_numpy(), w["hit_rate"].to_numpy(), hit_below, window_s)
        if reason[i] == "hit":
            onset.append(stop[i])             # the engine's own streak onset
            source.append("hit")
        elif o == o:
            onset.append(o)
            source.append("queue_trailing_low_hit")
        else:
            onset.append(stop[i])
            source.append("queue_crossing_fallback")
    out["stop_time_s"] = np.where(esc, stop, np.nan)
    out["onset_source"] = source
    out["escape_time_s"] = onset
    return out


def calib_row(k: float, pop: int, lm: float, per_seed: List[float], busy: float, lm1: Optional[float]) -> Dict[str, Any]:
    """One row of escape_calib.csv: lambda_miss(k) with a 95 % t-interval over the calibration seeds and its deviation
    from the exact fluid scaling k * lambda_miss(1)."""
    from scipy import stats as _st
    x = np.asarray(per_seed, dtype=float)
    n = len(x)
    sd = float(np.std(x, ddof=1)) if n > 1 else float("nan")
    half = float(_st.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else float("nan")
    row = {"k": k, "population": pop, "lambda_miss": lm, "lambda_miss_over_k": lm / k, "lambda_miss_sd": sd,
           "lambda_miss_ci95_lo": lm - half, "lambda_miss_ci95_hi": lm + half, "n_seeds": n,
           "tail_busy_frac": busy, "per_seed": json.dumps(per_seed)}
    if lm1 is not None:
        row["fluid_lambda_miss"] = k * lm1
        row["rel_dev_from_fluid"] = lm / (k * lm1) - 1.0
    return row


def cmd_escape(cfg: dict, args: argparse.Namespace, repo_dir: Path, section: str = "escape",
               name: str = "prefix_meta_escape") -> Path:
    ec = exp_cfg_deep(cfg, section, args.quick)
    ctx = begin("escape", name, cfg, {**cfg, f"{section}_effective": ec}, args, repo_dir)
    wl = WorkloadParams.from_dict(cfg["workload"])
    cc = ec["calib"]
    scalings = list(ec.get("scalings", ["calibrated"]))
    # ---- lambda_miss(k)
    calib_rows, lam_miss_k, per_seed_k = [], {}, {}
    calib_specs: List[RunSpec] = []
    calib_res: List[Dict[str, Any]] = []
    limit_summaries: List[Dict[str, Any]] = []
    limit_specs: List[RunSpec] = []
    with Runner(cfg, args.workers) as R:
        for k in ec["sizes"]:
            eo = scaled_engine_overrides(cfg["engine"], k)
            pop = max(1, int(round(cc["population_per_k"] * k)))
            lm, per_seed, sp, rs = measure_lambda_miss(R, cfg, pop, cc["seeds"], cc["horizon_s"], cc["warmup_s"],
                                                       cc["pool_sessions"], engine_overrides=eo, variant=f"k={k}")
            lam_miss_k[k] = lm
            per_seed_k[k] = per_seed
            calib_specs += sp
            calib_res += [strip_for_storage(r) for r in rs]
            busy = float(np.mean([r["summary"]["tail_busy_frac"] for r in rs]))
            calib_rows.append((k, pop, lm, per_seed, busy))
        lm1 = lam_miss_k.get(1.0)
        if "fluid" in scalings and lm1 is None:
            raise ValueError("scaling 'fluid' needs k = 1.0 in sizes (lambda = m * k * lambda_miss(1))")
        calib_df = pd.DataFrame([calib_row(k, pop, lm, ps, busy, lm1) for (k, pop, lm, ps, busy) in calib_rows])
        calib_df.to_csv(ctx.out / "escape_calib.csv", index=False)
        # ---- from-empty stable limit of the escape policy at each size (context for lambda / lambda_cap(k))
        lim_cfg = ec.get("limit")
        if lim_cfg:
            for k in ec["sizes"]:
                eo = scaled_engine_overrides(cfg["engine"], k)
                summ, sp, _ = find_stable_limit(R, cfg, ec["policy"], lam_miss_k[k], scale_limit_cfg(lim_cfg, k),
                                                engine_overrides=eo, variant=f"k={k}", exp="escape_limit")
                summ["k"] = k
                limit_summaries.append(summ)
                limit_specs += sp
            pd.DataFrame([r for sm in limit_summaries for r in sm["search_rows"]]).to_csv(
                ctx.out / "escape_limit_search.csv", index=False)
            lt = pd.DataFrame([{kk: v for kk, v in sm.items() if kk != "search_rows"} for sm in limit_summaries])
            lt["lambda_cap_over_lambda_miss"] = lt["lambda_cap"] / lt["lambda_miss"]
            lt.to_csv(ctx.out / "escape_limits.csv", index=False)
        # ---- escape runs
        specs: List[RunSpec] = []
        for scaling in scalings:
            for k in ec["sizes"]:
                if scaling == "fluid" and k == 1.0:
                    continue                      # identical to the calibrated k = 1 runs (same lambda, same seeds)
                eo = scaled_engine_overrides(cfg["engine"], k)
                thr = collapse_queue_threshold(cfg["engine"], wl, k, ec["queue_factor"])
                base_rate = lam_miss_k[k] if scaling == "calibrated" else k * lam_miss_k[1.0]
                for m in ec["lam_mults"]:
                    lam = m * base_rate
                    for sd in ec["seeds"]:
                        specs.append(RunSpec(exp="escape", policy=ec["policy"], seed=sd, horizon_s=ec["horizon_s"],
                                             variant=f"k={k}", engine_overrides=eo, stop_queue_above=thr,
                                             stop_low_hit=(ec["hit_below"], int(ec["hit_windows"])),
                                             plan=ArrivalPlan(kind="constant", horizon_s=ec["horizon_s"], rate=lam),
                                             meta=_meta(lam, m, k=k, queue_threshold=thr, scaling=scaling)))
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs["escaped"] = runs["stopped_early"].astype(bool)
    runs = escape_event_times(runs, wins, ec["hit_below"], cfg["metrics"]["window_s"])
    runs["obs_time_s"] = np.where(runs["escaped"], runs["escape_time_s"], ec["horizon_s"])
    save_frames(ctx.out, runs, wins, qts)
    lim_by_k = {sm["k"]: sm for sm in limit_summaries}
    tab = escape_table(runs, ec["horizon_s"], lim_by_k, lam_miss_k)
    tab.to_csv(ctx.out / "escape_summary.csv", index=False)
    runs[["policy", "seed", "k", "scaling", "lam_mult", "lam", "queue_threshold", "escaped", "stop_reason",
          "stop_time_s", "escape_time_s", "onset_source", "obs_time_s", "sim_end_s", "max_queue",
          "hit_rate_all"]].to_csv(ctx.out / "escape_runs.csv", index=False)
    finish(ctx, [rs.seed for rs in specs + limit_specs + calib_specs],
           {"n_runs": int(len(runs)), "n_limit_search_runs": len(limit_specs), "timing": timing_summary(runs),
            "lambda_miss_by_k": {str(k): v for k, v in lam_miss_k.items()}, "scalings": scalings,
            "queue_thresholds": {str(k): collapse_queue_threshold(cfg["engine"], wl, k, ec["queue_factor"])
                                 for k in ec["sizes"]},
            "lambda_cap_by_k": {str(k): sm["lambda_cap"] for k, sm in lim_by_k.items()}})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(calib_df.drop(columns=["per_seed"]).to_string())
        if limit_summaries:
            print(lt.to_string())
        print(tab.to_string())
    print("result dir:", ctx.out)
    return ctx.out


def escape_table(runs: pd.DataFrame, horizon: float, lim_by_k: Optional[Dict[float, Dict[str, Any]]] = None,
                 lam_miss_k: Optional[Dict[float, float]] = None) -> pd.DataFrame:
    """Per (scaling, k, lam_mult): Kaplan-Meier / exponential-MLE summaries of the time to collapse (right-censored at
    the horizon; event time = hit-collapse onset), stop reasons, the KM median with a Greenwood log-log interval, and
    lambda / lambda_cap(k) when the per-size limit was measured. The fluid k = 1 rows are copies of the calibrated
    k = 1 rows (identical runs) and are flagged."""
    if "scaling" not in runs.columns:
        runs = runs.assign(scaling="calibrated")
    rows = []
    for (sc, k, m), g in runs.groupby(["scaling", "k", "lam_mult"], sort=True):
        rows.append(_escape_row(g, sc, k, m, horizon, lim_by_k, lam_miss_k, False))
    have_fluid = (runs["scaling"] == "fluid").any()
    if have_fluid and (runs["k"] == 1.0).any():
        for (k, m), g in runs[(runs["scaling"] == "calibrated") & (runs["k"] == 1.0)].groupby(["k", "lam_mult"]):
            rows.append(_escape_row(g, "fluid", k, m, horizon, lim_by_k, lam_miss_k, True))
    return pd.DataFrame(rows).sort_values(["scaling", "k", "lam_mult"]).reset_index(drop=True)


def _escape_row(g: pd.DataFrame, scaling: str, k: float, m: float, horizon: float,
                lim_by_k: Optional[Dict[float, Dict[str, Any]]], lam_miss_k: Optional[Dict[float, float]],
                copied: bool) -> Dict[str, Any]:
    sm = summarize_escape(g["obs_time_s"].to_numpy(), g["escaped"].to_numpy(), horizon)
    med, lo, hi = km_median_ci(g["obs_time_s"].to_numpy(), g["escaped"].to_numpy())
    reasons = g.loc[g["escaped"], "stop_reason"].value_counts().to_dict()
    row = {"scaling": scaling, "k": k, "lam_mult": m, **sm, "km_median_ci_lo": lo, "km_median_ci_hi": hi,
           "n_by_queue": int(reasons.get("queue", 0)), "n_by_hit": int(reasons.get("hit", 0)),
           "lam": float(g["lam"].mean()), "copied_from_calibrated_k1": bool(copied)}
    if "onset_source" in g.columns:
        row["n_onset_fallback"] = int((g["onset_source"] == "queue_crossing_fallback").sum())
    if lim_by_k and k in lim_by_k:
        cap = float(lim_by_k[k]["lambda_cap"])
        row["lambda_cap_k"] = cap
        row["lam_over_cap"] = row["lam"] / cap if cap > 0 else float("nan")
    return row


# ======================================================================= robust
def cmd_robust(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    rc = exp_cfg_deep(cfg, "robust", args.quick)
    ctx = begin("robust", "prefix_meta_robust", cfg, {**cfg, "robust_effective": rc}, args, repo_dir)
    W = cfg["metrics"]["window_s"]
    cc, lim = rc["calib"], rc["limit"]
    tb = rc["warmup_s"]
    Hb = tb + rc["after_s"]
    M = float(cfg["engine"]["kv_memory_tokens"])
    var_rows: List[Dict[str, Any]] = []
    limit_rows: List[Dict[str, Any]] = []
    burst_specs: List[RunSpec] = []
    stored_specs: List[RunSpec] = []
    stored_res: List[Dict[str, Any]] = []
    with Runner(cfg, args.workers) as R:
        for v in rc["variants"]:
            name, wo = v["name"], dict(v.get("workload", {}))
            wl = WorkloadParams.from_dict(deep_update(cfg["workload"], wo))
            lm, per_seed, sp, rs = measure_lambda_miss(R, cfg, cc["population"], cc["seeds"], cc["horizon_s"],
                                                       cc["warmup_s"], cc["pool_sessions"], workload_overrides=wo,
                                                       variant=name)
            stored_specs += sp
            stored_res += [strip_for_storage(r) for r in rs]
            row = {"variant": name, "lambda_miss": lm, "lambda_miss_per_seed": json.dumps(per_seed),
                   "E_lb": length_biased_mean_context(wl), "N_lb": length_biased_session_cap(M, wl)}
            for p in rc["limit_policies"]:
                summ, sp, rs = find_stable_limit(R, cfg, p, lm, lim, workload_overrides=wo, variant=name,
                                                 exp="robust_limit")
                stored_specs += sp
                stored_res += [strip_for_storage(r) for r in rs]
                row[f"lambda_cap_{p}"] = summ["lambda_cap"]
                row[f"R_{p}"] = summ["lambda_cap"] / lm
                row[f"bracket_hi_{p}"] = summ["bracket_hi"]
                limit_rows += summ["search_rows"]
            var_rows.append(row)
            lam_b = rc["burst_lam_mult"] * lm
            for sd in rc["burst_seeds"]:
                burst_specs.append(RunSpec(exp="robust", policy=rc["burst_policy"], seed=sd, horizon_s=Hb, variant=name,
                                           workload_overrides=wo,
                                           plan=ArrivalPlan(kind="constant", horizon_s=Hb, rate=lam_b,
                                                            burst_n=rc["burst_sessions"], burst_t0=tb,
                                                            burst_width_s=rc["burst_width_s"]),
                                           meta=_meta(lam_b, rc["burst_lam_mult"], t_burst=tb,
                                                      burst_sessions=rc["burst_sessions"])))
        bres = R.run(burst_specs)
    runs, wins, qts = collect_frames(bres, burst_specs)
    runs = burst_columns(runs, wins, rc, W, tb)
    save_frames(ctx.out, runs, wins, qts)
    pd.DataFrame(limit_rows).to_csv(ctx.out / "limit_search.csv", index=False)
    vt = pd.DataFrame(var_rows)
    bc = burst_counts(runs, ["variant"]).rename(columns={"n_runs": "burst_n_runs", "n_trapped": "burst_n_trapped",
                                                         "n_burst_recovered": "burst_n_recovered"})
    vt = vt.merge(bc[["variant", "burst_n_runs", "burst_n_trapped", "burst_n_recovered", "hit_eval_mean"]],
                  on="variant")
    vt["burst_lam_mult"] = rc["burst_lam_mult"]
    vt["burst_below_lpm_limit"] = rc["burst_lam_mult"] * vt["lambda_miss"] < vt["lambda_cap_lpm"]
    vt["holds"] = ((vt["R_lpm"] > rc["holds_R_above"]) & (vt["burst_n_trapped"] >= rc["holds_trap_min_seeds"])
                   & vt["burst_below_lpm_limit"])
    vt.to_csv(ctx.out / "robust_summary.csv", index=False)
    n_hold = int(vt["holds"].sum())
    finish(ctx, [s.seed for s in burst_specs + stored_specs],
           {"n_variants": int(len(vt)), "n_variants_holding": n_hold, "variants_needed": rc["holds_variants_needed"],
            "n_burst_runs": int(len(runs)), "n_search_and_calib_runs": len(stored_specs),
            "timing": timing_summary(runs)})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(vt.drop(columns=["lambda_miss_per_seed"]).to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= evaluate (pre-registered predictions)
def _read_input(d: Optional[str], fname: str) -> Optional[pd.DataFrame]:
    if not d:
        return None
    f = Path(d) / fname
    return pd.read_csv(f) if f.exists() else None


def _input_provenance(d: Optional[str]) -> Optional[Dict[str, Any]]:
    if not d:
        return None
    mf = Path(d) / "meta.json"
    if not mf.exists():
        return {"dir": str(d), "meta": None}
    m = json.loads(mf.read_text())
    return {"dir": str(d), "experiment": m.get("experiment"), "git_commit": m.get("git", {}).get("commit"),
            "git_dirty": m.get("git", {}).get("dirty"), "quick": m.get("quick"), "n_runs": m.get("n_runs"),
            "start_time": m.get("start_time")}


def cmd_evaluate(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    from .prereg_eval import evaluate_all, rows_to_frame
    ctx = begin("evaluate", "prefix_meta_eval", cfg, cfg, args, repo_dir)
    phase = _read_input(args.phase_dir, "runs.csv")
    mech = _read_input(args.mech_dir, "runs.csv")
    limits = _read_input(args.mech_dir, "mech_limits.csv")
    capacity = _read_input(args.mech_dir, "mech_capacity.csv")
    esc = _read_input(args.escape_dir, "escape_summary.csv")
    esc_iw = _read_input(getattr(args, "escape_inwindow_dir", None), "escape_summary.csv")
    rob = _read_input(args.robust_dir, "robust_summary.csv")
    needed = int(exp_cfg_deep(cfg, "robust", False).get("holds_variants_needed", 5))
    rows = evaluate_all(phase_runs=phase, mech_runs=mech, mech_limits=limits, escape_summary=esc,
                        robust_summary=rob, p8_needed=needed, mech_capacity=capacity, escape_inwindow_summary=esc_iw)
    prov = {k: _input_provenance(v) for k, v in (("phase", args.phase_dir), ("mech", args.mech_dir),
                                                 ("escape", args.escape_dir),
                                                 ("escape_inwindow", getattr(args, "escape_inwindow_dir", None)),
                                                 ("robust", args.robust_dir))}
    flags = [f"{k}: quick run" for k, v in prov.items() if v and v.get("quick")]
    flags += [f"{k}: produced from a dirty git tree" for k, v in prov.items() if v and v.get("git_dirty")]
    _write_json(ctx.out / "prediction_eval.json", {"rows": rows, "inputs": prov, "flags": flags})
    rows_to_frame(rows).to_csv(ctx.out / "prediction_eval.csv", index=False)
    finish(ctx, [], {"inputs": prov, "flags": flags, "verdicts": {r["id"]: r["verdict"] for r in rows}})
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        print(rows_to_frame(rows)[["id", "verdict", "notes"]].to_string())
    for f in flags:
        print("FLAG:", f)
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Prefix-cache metastability pilot, round 2 (simulation)")
    ap.add_argument("cmd", choices=["phase", "mech", "escape", "escape_inwindow", "robust", "evaluate", "report"])
    ap.add_argument("--config", default="configs/prefix_meta_mech.yaml")
    ap.add_argument("--quick", action="store_true", help="smoke-test sizes (short horizons, few seeds)")
    ap.add_argument("--workers", type=int, default=3, help="processes (hard-capped by config parallel.max_workers)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--calib", default=None, help="round-1 E0 result dir or e0_summary.json (base workload)")
    ap.add_argument("--only", nargs="*", default=None, help="restrict mech to these policy names")
    ap.add_argument("--phase-dir", default=None, help="evaluate: phase result dir")
    ap.add_argument("--mech-dir", default=None, help="evaluate: mech result dir")
    ap.add_argument("--escape-dir", default=None, help="evaluate: escape result dir (registered sizes)")
    ap.add_argument("--escape-inwindow-dir", default=None, help="evaluate: escape_inwindow result dir (k = 1, 2, 4)")
    ap.add_argument("--robust-dir", default=None, help="evaluate: robust result dir")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override")
    ap.add_argument("--tag", default=None, help="suffix for the result dir name")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(args.config).resolve().parent.parent
    cfg = apply_overrides(load_mech_config(args.config, repo_dir), args.set)
    if args.cmd == "escape_inwindow":
        cmd_escape(cfg, args, repo_dir, section="escape_inwindow", name="prefix_meta_escape_inwindow")
    elif args.cmd == "report":
        from .report_r3 import cmd_report
        cmd_report(cfg, args, repo_dir)
    else:
        {"phase": cmd_phase, "mech": cmd_mech, "escape": cmd_escape, "robust": cmd_robust,
         "evaluate": cmd_evaluate}[args.cmd](cfg, args, repo_dir)
    return 0
