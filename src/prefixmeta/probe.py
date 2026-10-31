"""Probe runner: three small, config-driven experiments on one engine configuration, with arbitrary engine / workload overrides from a YAML file.

    curve   closed-population service-rate curve mu(n): ``n`` sessions always in the system (a finished session is replaced at once)
    open    open-loop stability from an EMPTY start at one or more arrival rates lambda (optionally the bisection for the stable limit)
    burst   open system at lambda from empty with a burst of ``burst_n`` sessions at ``t_burst``; PAIRED arms on the same seeds: ``no_burst``
            (same Poisson stream, no burst), ``burst`` and ``burst_cap`` (burst + a client-side cap on sessions in the system)

Nothing here re-implements simulation, metrics or classification logic; it only assembles ``RunSpec`` lists and calls the existing pieces:
``r4_runner.closed_spec`` / ``r5_runner.point_metrics_r5`` / ``r5_runner.curve_table`` / ``r5_runner.nstar_from_curve_table`` (curve),
``mech_runner.backlog_verdict`` / ``mech_runner.find_stable_limit`` (open), ``mech_runner.add_recovery`` / ``burst_columns`` / ``burst_counts`` /
``recovery_counts`` and ``r5_runner.add_tail_preemption`` (burst), ``runner.Runner`` / ``collect_frames`` (process pool, at most
``parallel.max_workers`` processes), ``mech_runner.begin`` / ``finish`` (fresh timestamped result directory, config copies, git commit and dirty
flag at the start, versions, seeds).

Spec file (YAML)::

    base_config: configs/prefix_meta_r5.yaml       # optional (default); bases chain (r5 -> prefix_meta.yaml)
    engine:   {batching: separate_prefill_priority, alloc_mode: ratio_reserve, prefill_per_token_s: 8.4e-5, ...}   # merged over the base engine
    workload: {decode_tokens: 100, ...}                                                                              # merged over the base workload
    parallel: {max_workers: 3}                      # hard cap on processes (this CLI refuses more than 6)
    probe:
      curve: {policies: [fcfs_lru], n_grid: [8, 16, 32], seeds: [0, 1], warmup_s: 5000, horizon_s: 35000, cache_enabled: true,
              engine: {}, workload: {}}              # section-level engine / workload entries are per-RUN overrides on top of the global ones
      open:  {policy: fcfs_lru, lambdas: [0.05, 0.1], seeds: [0, 1, 2], horizon_s: 20000,
              lambda_miss: 0.047, lam_mults: [1.5, 2.0],     # alternative to ``lambdas`` (absolute sessions / s)
              search: {bracket_mults: [1.5, 2, 3], rel_tol: 0.05, max_bisect_steps: 6}}   # optional: bracket + bisection of the stable limit
      burst: {policy: fcfs_lru, lambda: 0.1, burst_n: 200, burst_width_s: 60, warmup_s: 5000, after_s: 60000, cap: 28, seeds: [0, 1, 2]}

``--quick`` merges ``probe.<section>.quick`` over the section (smoke-test sizes). Every key has a default (``DEFAULTS``); unknown section keys are an
error. ``--set dotted.key=value`` overrides any entry of the merged config. See configs/prefix_meta_probe.yaml for a commented example.

Definitions (all inherited from the existing code, not redefined here): ``stable`` (open) = not early-stopped, final backlog (queue + gate) below
``stable_final_backlog_below`` and fitted backlog rise over the last ``stable_trend_window_s`` at most ``stable_trend_max_rise``
(``mech_runner.backlog_verdict``); ``recovered`` (burst) = tail hit rate > ``recovered_hit_above`` and tail backlog < ``recovered_backlog_below``;
``trapped`` = hit rate < ``trap_hit_below`` for at least ``trap_min_s`` of consecutive windows from the burst on (``mech_runner.burst_columns``).
The client-side cap is the engine's session cap (a gate in front of the engine: a session enters only while fewer than ``cap`` sessions are in the
system; the others wait outside, counted in the backlog).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .engine import EngineParams
from .mech_runner import (add_recovery, backlog_verdict, begin, burst_columns, burst_counts, find_stable_limit, finish,
                          recovery_counts)
from .r4_runner import closed_spec
from .r5_runner import add_tail_preemption, curve_table, nstar_from_curve_table, point_metrics_r5
from .runner import Runner, apply_overrides, collect_frames, save_frames, timing_summary
from .sim import RunSpec, deep_update, load_config
from .workload import ArrivalPlan, WorkloadParams

MAX_WORKERS = 6
DEFAULT_BASE = "configs/prefix_meta_r5.yaml"
SECTIONS = ("curve", "open", "burst")
THRASH_DEFAULT = {"preemptions_per_turn_above": 0.05, "max_per_turn_above": 10}

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "curve": {"policies": ["fcfs_lru"], "n_grid": [8, 16, 24, 32, 40, 60], "seeds": [0, 1, 2], "warmup_s": 5000.0, "horizon_s": 35000.0,
              "pool_sessions": 20000, "cache_enabled": True, "engine": {}, "workload": {},
              "quick": {"n_grid": [8, 32], "seeds": [0], "warmup_s": 1000.0, "horizon_s": 4000.0, "pool_sessions": 3000}},
    "open": {"policy": "fcfs_lru", "lambdas": None, "lambda_miss": None, "lam_mults": None, "seeds": [0, 1, 2], "horizon_s": 20000.0,
             "unstable_backlog_stop": 3000, "stable_final_backlog_below": 50.0, "stable_trend_window_s": 5000.0, "stable_trend_max_rise": 10.0,
             "search": None, "engine": {}, "workload": {},
             "quick": {"seeds": [0], "horizon_s": 3000.0, "stable_trend_window_s": 1000.0}},
    "burst": {"policy": "fcfs_lru", "lambda": None, "lambda_miss": None, "lam_mult": None, "burst_n": 200, "burst_width_s": 60.0,
              "warmup_s": 5000.0, "after_s": 60000.0, "cap": None, "arms": None, "seeds": [0, 1, 2], "recovered_hit_above": 0.8,
              "recovered_backlog_below": 20.0, "hit_eval_from_s": 10000.0, "trap_hit_below": 0.2, "trap_min_s": 10000.0, "engine": {},
              "workload": {}, "quick": {"seeds": [0], "burst_n": 50, "warmup_s": 1000.0, "after_s": 4000.0, "hit_eval_from_s": 1000.0,
                                         "trap_min_s": 2000.0}},
}


# ======================================================================= configuration
def _load_chain(path: Path, repo_dir: Path, _depth: int = 0) -> dict:
    """Config at ``path`` merged over its ``base_config`` chain (dicts merge, lists replace, the file wins)."""
    if _depth > 5:
        raise ValueError("base_config chain too deep (cycle?)")
    top = load_config(str(path))
    base_rel = top.get("base_config")
    base = _load_chain(repo_dir / base_rel, repo_dir, _depth + 1) if base_rel else {}
    return deep_update(base, {k: v for k, v in top.items() if k != "base_config"})


def probe_section(cfg: dict, name: str, quick: bool) -> dict:
    """Section ``name`` of ``cfg['probe']`` over ``DEFAULTS``; with ``quick`` the section's ``quick`` block (default merged with the user's) on top.
    Unknown keys are an error (a misspelt key must not be silently ignored)."""
    if name not in SECTIONS:
        raise ValueError(f"unknown probe section {name!r}; known: {SECTIONS}")
    user = dict((cfg.get("probe") or {}).get(name) or {})
    default = DEFAULTS[name]
    unknown = sorted(set(user) - set(default))
    if unknown:
        raise ValueError(f"probe.{name}: unknown keys {unknown}; known: {sorted(default)}")
    sec = deep_update({k: v for k, v in default.items() if k != "quick"}, {k: v for k, v in user.items() if k != "quick"})
    if quick:
        sec = deep_update(sec, deep_update(default.get("quick", {}), user.get("quick") or {}))
    sec.pop("quick", None)
    return sec


def load_probe_config(spec_path: str, repo_dir: Path, sets: Optional[Sequence[str]] = None) -> dict:
    """Merged config of a probe spec: base chain (default ``DEFAULT_BASE``) <- spec <- ``sets`` (dotted ``key=value`` overrides). Forces the memory
    traces the metrics need (``metrics.track_memory``) and validates the engine / workload entries before any run is launched."""
    top = load_config(spec_path)
    base_rel = top.get("base_config", DEFAULT_BASE)
    base = _load_chain(repo_dir / base_rel, repo_dir)
    cfg = deep_update(base, {k: v for k, v in top.items() if k != "base_config"})
    cfg = apply_overrides(cfg, sets)
    cfg["metrics"] = {**cfg.get("metrics", {}), "track_memory": True}
    cfg["_base_config"] = base_rel
    EngineParams.from_dict(cfg["engine"])
    WorkloadParams.from_dict(cfg["workload"])
    return cfg


def check_overrides(cfg: dict, engine_overrides: Optional[dict], workload_overrides: Optional[dict]) -> None:
    """Fail fast (before the process pool starts): the engine / workload override set must produce valid parameters."""
    EngineParams.from_dict(deep_update(cfg["engine"], engine_overrides or {}))
    WorkloadParams.from_dict(deep_update(cfg["workload"], workload_overrides or {}))


def check_run_specs(cfg: dict, specs: Sequence[RunSpec]) -> None:
    """``check_overrides`` for every distinct override set of ``specs``."""
    seen = set()
    for rs in specs:
        key = (json.dumps(rs.engine_overrides, sort_keys=True, default=str), json.dumps(rs.workload_overrides, sort_keys=True, default=str))
        if key not in seen:
            seen.add(key)
            check_overrides(cfg, rs.engine_overrides, rs.workload_overrides)


def mode_label(cfg: dict, sec: dict) -> str:
    """``alloc_mode|batching`` of the (section-overridden) engine; the ``mode`` column of the curve table."""
    e = deep_update(cfg["engine"], sec.get("engine") or {})
    return f"{e.get('alloc_mode', 'full_reserve')}|{e.get('batching', 'mixed')}"


def _run(cfg: dict, specs: Sequence[RunSpec], workers: int) -> List[Dict[str, Any]]:
    check_run_specs(cfg, specs)
    if any(rs.meta.get("control") is not None for rs in specs):       # round 11: gate controllers run through gate_control
        from .gate_control import run_specs
        return run_specs(cfg, specs, workers)
    with Runner(cfg, workers) as R:
        return R.run(specs)


def _lam_list(sec: dict) -> List[Tuple[float, float]]:
    """[(lambda, lambda / lambda_miss or NaN)] from ``lambdas`` (absolute) or ``lambda_miss`` x ``lam_mults``."""
    lm = sec.get("lambda_miss")
    if sec.get("lambdas"):
        return [(float(x), float(x) / float(lm) if lm else float("nan")) for x in sec["lambdas"]]
    if lm and sec.get("lam_mults"):
        return [(float(m) * float(lm), float(m)) for m in sec["lam_mults"]]
    raise ValueError("give either `lambdas` (sessions / s) or `lambda_miss` together with `lam_mults`")


# ======================================================================= (i) closed-population curve mu(n)
def curve_specs(cfg: dict, sec: dict) -> List[RunSpec]:
    H, W0 = float(sec["horizon_s"]), float(sec["warmup_s"])
    Wd = float(cfg["metrics"]["window_s"])
    if not (0.0 <= W0 < H) or abs(((H - W0) / Wd) - round((H - W0) / Wd)) > 1e-9:
        raise ValueError(f"curve: horizon_s - warmup_s = {H - W0} must be a positive multiple of the metric window ({Wd} s)")
    cv = {"horizon_s": H, "pool_sessions_per_k": int(sec["pool_sessions"])}
    eo = {**dict(sec.get("engine") or {}), "cache_enabled": bool(sec["cache_enabled"])}
    specs: List[RunSpec] = []
    for pol in sec["policies"]:
        for n in sec["n_grid"]:
            for sd in sec["seeds"]:
                rs = closed_spec(pol, int(n), 1.0, int(sd), cv, cfg["engine"])
                rs.exp = "probe_curve"
                rs.engine_overrides = {**rs.engine_overrides, **eo}
                rs.workload_overrides = dict(sec.get("workload") or {})
                specs.append(rs)
    return specs


@dataclass
class CurveResult:
    runs: pd.DataFrame            # one row per (policy, n, seed): mu, hit rate, busy, KV occupancy, preemption statistics, run-level timing split
    table: pd.DataFrame           # r5_runner.curve_table: seed-mean / sd / se of mu per (mode, policy, n)
    nstar: Dict[str, int]         # first argmax over the grid of the seed-mean mu per policy (r5_runner.nstar_from_curve_table; ties: smallest n)
    frames: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]   # collect_frames: per-run summaries, windows, queue traces
    specs: List[RunSpec]


def run_curve(cfg: dict, sec: Optional[dict] = None, *, workers: int = 1, quick: bool = False) -> CurveResult:
    """mu(n) for every (policy, n, seed): sessions completed per second over the complete windows after ``warmup_s`` (``point_metrics``)."""
    sec = sec if sec is not None else probe_section(cfg, "curve", quick)
    specs = curve_specs(cfg, sec)
    results = _run(cfg, specs, workers)
    W = float(cfg["metrics"]["window_s"])
    label = mode_label(cfg, sec)
    rows = []
    for rs, res in zip(specs, results):
        s = res["summary"]
        row = {"mode": label, "policy": rs.policy, "n_nominal": rs.meta["n_nominal"], "n": rs.meta["population"], "k": 1.0, "seed": rs.seed,
               **point_metrics_r5(res["windows"], sec["warmup_s"], sec["horizon_s"], W), "wall_s": s["wall_s"]}
        if "n_prefill_iters" in s:                       # separate_prefill_priority: whole-run (incl. warm-up) split of the engine's time
            row.update({"run_prefill_busy_frac": s["prefill_busy_s"] / s["sim_end_s"], "run_decode_busy_frac": s["decode_busy_s"] / s["sim_end_s"],
                        "run_prefill_iter_frac": s["n_prefill_iters"] / s["n_iterations"]})
        rows.append(row)
    cr = pd.DataFrame(rows)
    ct = curve_table(cr)
    nstar = {pol: nstar_from_curve_table(ct, label, pol) for pol in sec["policies"]}
    return CurveResult(runs=cr, table=ct, nstar=nstar, frames=collect_frames(results, specs), specs=specs)


# ======================================================================= (ii) open-loop stability from an empty start
def open_specs(cfg: dict, sec: dict) -> List[RunSpec]:
    H = float(sec["horizon_s"])
    specs: List[RunSpec] = []
    for lam, mult in _lam_list(sec):
        for sd in sec["seeds"]:
            specs.append(RunSpec(exp="probe_open", policy=sec["policy"], seed=int(sd), horizon_s=H, variant=f"lam={lam:.6g}",
                                 plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam), stop_backlog_above=int(sec["unstable_backlog_stop"]),
                                 engine_overrides=dict(sec.get("engine") or {}), workload_overrides=dict(sec.get("workload") or {}),
                                 meta={"lam": lam, "lam_mult": mult}))
    return specs


def _limit_cfg(sec: dict) -> dict:
    """The ``lim`` dict of ``mech_runner.backlog_verdict`` / ``find_stable_limit`` from the section."""
    lim = {"stable_final_backlog_below": float(sec["stable_final_backlog_below"]), "stable_trend_window_s": float(sec["stable_trend_window_s"]),
           "stable_trend_max_rise": float(sec["stable_trend_max_rise"]), "unstable_backlog_stop": int(sec["unstable_backlog_stop"]),
           "horizon_s": float(sec["horizon_s"]), "seeds": [int(s) for s in sec["seeds"]]}
    return lim


@dataclass
class OpenResult:
    verdicts: pd.DataFrame        # one row per (lambda, seed): backlog_verdict fields
    table: pd.DataFrame           # per lambda: n_stable / n_runs, stable_all
    search: Optional[Dict[str, Any]]    # find_stable_limit summary (bracket + bisection) or None
    frames: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    specs: List[RunSpec]


def run_open(cfg: dict, sec: Optional[dict] = None, *, workers: int = 1, quick: bool = False) -> OpenResult:
    """Run the open system from empty at each lambda; verdicts by ``mech_runner.backlog_verdict`` (early-stopped runs count as unstable)."""
    sec = sec if sec is not None else probe_section(cfg, "open", quick)
    lim = _limit_cfg(sec)
    check_overrides(cfg, sec.get("engine"), sec.get("workload"))
    have_lams = bool(sec.get("lambdas") or (sec.get("lambda_miss") and sec.get("lam_mults")))
    if not have_lams and not sec.get("search"):
        raise ValueError("open: give `lambdas` (or `lambda_miss` + `lam_mults`) and / or `search`")
    specs = open_specs(cfg, sec) if have_lams else []
    results = _run(cfg, specs, workers) if specs else []
    rows = []
    for rs, res in zip(specs, results):
        rows.append({"lam": rs.meta["lam"], "lam_mult": rs.meta["lam_mult"], "seed": rs.seed, **backlog_verdict(res, lim),
                     "sim_end_s": res["summary"]["sim_end_s"], "wall_s": res["summary"]["wall_s"]})
    vd = pd.DataFrame(rows)
    tab = (vd.groupby("lam", sort=True).agg(lam_mult=("lam_mult", "first"), n_runs=("stable", "size"), n_stable=("stable", "sum"),
                                            final_backlog_mean=("final_backlog", "mean"), trend_rise_mean=("trend_rise", "mean"),
                                            tail_hit_mean=("tail_hit_rate", "mean"), tail_busy_mean=("tail_busy_frac", "mean"),
                                            tail_sessions_per_s=("tail_sessions_per_s", "mean")).reset_index() if len(vd) else pd.DataFrame())
    if len(tab):
        tab["stable_all"] = tab["n_stable"] == tab["n_runs"]
    search = None
    all_specs, all_res = list(specs), list(results)
    if sec.get("search"):
        sr = dict(sec["search"])
        lm = float(sr.get("lambda_miss") or sec.get("lambda_miss") or 0.0)
        if lm <= 0.0:
            raise ValueError("open.search needs lambda_miss (open.lambda_miss or open.search.lambda_miss)")
        slim = {**lim, "bracket_mults": [float(m) for m in sr.get("bracket_mults", [1.5, 2.0, 3.0, 4.0, 6.0])],
                "rel_tol": float(sr.get("rel_tol", 0.05)), "max_bisect_steps": int(sr.get("max_bisect_steps", 6))}
        if sr.get("lower_mults"):
            slim["lower_mults"] = [float(m) for m in sr["lower_mults"]]
        with Runner(cfg, workers) as R:
            search, s_specs, s_res = find_stable_limit(R, cfg, sec["policy"], lm, slim, workload_overrides=dict(sec.get("workload") or {}),
                                                       engine_overrides=dict(sec.get("engine") or {}), variant="search", exp="probe_open_search")
        all_specs += s_specs
        all_res += s_res
    return OpenResult(verdicts=vd, table=tab, search=search, frames=collect_frames(all_res, all_specs) if all_specs else
                      (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()), specs=all_specs)


# ======================================================================= (iii) burst with paired no-burst and client-side-cap arms
def burst_lambda(sec: dict) -> Tuple[float, float]:
    """(lambda, lambda / lambda_miss or NaN) of the burst section: ``lambda`` (absolute) or ``lambda_miss`` x ``lam_mult``."""
    if sec.get("lambda"):
        lam = float(sec["lambda"])
        return lam, lam / float(sec["lambda_miss"]) if sec.get("lambda_miss") else float("nan")
    if sec.get("lambda_miss") and sec.get("lam_mult"):
        return float(sec["lam_mult"]) * float(sec["lambda_miss"]), float(sec["lam_mult"])
    raise ValueError("burst: give `lambda` (sessions / s) or `lambda_miss` together with `lam_mult`")


ARM_KEYS = ("burst_n", "cap", "control", "lull")


def _arm(v: dict) -> Dict[str, Any]:
    """One explicit arm: {burst_n, cap} plus, only when given, ``control`` (a ``gate_control.GateControl`` dict, validated here) and
    ``lull`` ({t0, t1, keep}: ``ArrivalPlan`` lull fields). An arm without them has exactly the keys of the earlier rounds."""
    unknown = sorted(set(v) - set(ARM_KEYS))
    if unknown:
        raise ValueError(f"probe.burst.arms: unknown keys {unknown}; known: {list(ARM_KEYS)}")
    a: Dict[str, Any] = {"burst_n": int(v.get("burst_n", 0)), "cap": (None if v.get("cap") is None else int(v["cap"]))}
    if v.get("control") is not None:
        from .gate_control import GateControl
        if a["cap"] is not None:
            raise ValueError("probe.burst.arms: an arm with `control` must not also set `cap` (the controller owns the cap)")
        a["control"] = dict(GateControl.from_dict(dict(v["control"])).__dict__)
    if v.get("lull") is not None:
        lu = dict(v["lull"])
        if sorted(lu) != ["keep", "t0", "t1"]:
            raise ValueError("probe.burst.arms: `lull` needs exactly t0, t1 and keep")
        a["lull"] = {"t0": float(lu["t0"]), "t1": float(lu["t1"]), "keep": float(lu["keep"])}
    return a


def burst_arms(sec: dict) -> Dict[str, Dict[str, Any]]:
    """arm -> {burst_n, cap[, control][, lull]}. Default: no_burst (b = 0), burst (b = burst_n), burst_cap (b = burst_n, cap = ``cap``; only if
    ``cap`` is given). Explicit ``arms`` may carry a gate controller (``control``) and / or an arrival lull (``lull``), see ``_arm``."""
    if sec.get("arms"):
        return {str(k): _arm(dict(v)) for k, v in sec["arms"].items()}
    arms = {"no_burst": {"burst_n": 0, "cap": None}, "burst": {"burst_n": int(sec["burst_n"]), "cap": None}}
    if sec.get("cap") is not None:
        arms["burst_cap"] = {"burst_n": int(sec["burst_n"]), "cap": int(sec["cap"])}
    return arms


def burst_specs(cfg: dict, sec: dict) -> List[RunSpec]:
    tb = float(sec["warmup_s"])
    H = tb + float(sec["after_s"])
    lam, mult = burst_lambda(sec)
    specs: List[RunSpec] = []
    for arm, a in burst_arms(sec).items():
        lull = {} if "lull" not in a else {"lull_t0": a["lull"]["t0"], "lull_t1": a["lull"]["t1"], "lull_keep": a["lull"]["keep"]}
        for sd in sec["seeds"]:
            meta = {"lam": lam, "lam_mult": mult, "arm": arm, "burst_n": a["burst_n"], "cap": -1 if a["cap"] is None else a["cap"], "t_burst": tb}
            if "control" in a:
                meta["control"] = json.dumps(a["control"], sort_keys=True)
            if lull:
                meta.update(lull)
            specs.append(RunSpec(
                exp="probe_burst", policy=sec["policy"], seed=int(sd), horizon_s=H, variant=f"arm={arm}", session_cap_override=a["cap"],
                plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=a["burst_n"], burst_t0=tb, burst_width_s=float(sec["burst_width_s"]),
                                 **lull),
                engine_overrides=dict(sec.get("engine") or {}), workload_overrides=dict(sec.get("workload") or {}), meta=meta))
    return specs


@dataclass
class BurstResult:
    runs: pd.DataFrame            # one row per (arm, seed) with recovery / trap classification
    arms: pd.DataFrame            # per arm: counts of trapped / recovered runs and tail statistics
    frames: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    specs: List[RunSpec]


def run_burst(cfg: dict, sec: Optional[dict] = None, *, workers: int = 1, quick: bool = False) -> BurstResult:
    """All arms on the same seeds. Common random numbers: for a seed the Poisson stream and the sessions' turn counts / tool times are shared by
    every arm; the burst sessions are an extra stream, so ``no_burst`` and ``burst`` differ by exactly the burst."""
    sec = sec if sec is not None else probe_section(cfg, "burst", quick)
    specs = burst_specs(cfg, sec)
    results = _run(cfg, specs, workers)
    runs, wins, qts = collect_frames(results, specs)
    W = float(cfg["metrics"]["window_s"])
    tb = float(sec["warmup_s"])
    runs = add_recovery(runs, sec["recovered_hit_above"], sec["recovered_backlog_below"])
    runs = burst_columns(runs, wins, {k: sec[k] for k in ("hit_eval_from_s", "after_s", "trap_hit_below", "trap_min_s", "recovered_hit_above",
                                                          "recovered_backlog_below")}, W, tb)
    runs = add_tail_preemption(runs, wins, cfg.get("thrash") or THRASH_DEFAULT)
    arms = burst_counts(runs, ["arm"]).merge(recovery_counts(runs, ["arm"])[["arm", "n_recovered", "n_recovered_queue_only", "tail_hit_mean",
                                                                             "tail_queue_mean", "tail_gate_mean", "tail_sessions_per_s",
                                                                             "n_stopped_early"]], on="arm")
    arms.insert(1, "burst_n", [int(runs[runs["arm"] == a]["burst_n"].iloc[0]) for a in arms["arm"]])
    arms.insert(2, "cap", [int(runs[runs["arm"] == a]["cap"].iloc[0]) for a in arms["arm"]])
    return BurstResult(runs=runs, arms=arms, frames=(runs, wins, qts), specs=specs)


# ======================================================================= commands (fresh result dir per call)
def _meta_extra(cfg: dict, sec: dict, specs: Sequence[RunSpec], runs: pd.DataFrame) -> Dict[str, Any]:
    return {"n_runs": int(len(runs)), "timing": timing_summary(runs), "engine_effective": cfg["engine"], "workload_effective": cfg["workload"],
            "section_effective": sec, "base_config": cfg.get("_base_config")}


def _begin(experiment: str, name: str, cfg: dict, sec: dict, args: argparse.Namespace, repo_dir: Path):
    cfg_eff = {**{k: v for k, v in cfg.items() if k not in ("preregistration_file",)}, "section_effective": sec}
    cfg_begin = {k: v for k, v in cfg.items() if k != "preregistration_file"}      # not a registered run: do not copy a pre-registration
    return begin(experiment, name, cfg_begin, cfg_eff, args, repo_dir)


def _print(df: pd.DataFrame) -> None:
    with pd.option_context("display.width", 250, "display.max_rows", 500, "display.max_columns", 50):
        print(df.to_string())


def cmd_curve(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    sec = probe_section(cfg, "curve", args.quick)
    ctx = _begin("probe_curve", "prefix_meta_probe_curve", cfg, sec, args, repo_dir)
    r = run_curve(cfg, sec, workers=args.workers)
    runs, wins, _ = r.frames
    runs.to_csv(ctx.out / "runs.csv", index=False)
    wins.to_csv(ctx.out / "windows.csv", index=False)
    r.runs.to_csv(ctx.out / "curve_runs.csv", index=False)
    r.table.to_csv(ctx.out / "curve_table.csv", index=False)
    finish(ctx, r.runs["seed"], {**_meta_extra(cfg, sec, r.specs, runs), "nstar": r.nstar, "n_grid": list(sec["n_grid"]),
                                 "warmup_s": sec["warmup_s"], "horizon_s": sec["horizon_s"],
                                 "common_random_numbers": "same seed -> same workload stream for every policy and every n"})
    _print(r.table[["mode", "policy", "n_nominal", "n_seeds", "mu_mean", "mu_sd", "hit_rate_mean", "gpu_busy_mean", "preemptions_per_s_mean"]])
    print("n* by policy:", r.nstar)
    print("result dir:", ctx.out)
    return ctx.out


def cmd_open(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    sec = probe_section(cfg, "open", args.quick)
    ctx = _begin("probe_open", "prefix_meta_probe_open", cfg, sec, args, repo_dir)
    r = run_open(cfg, sec, workers=args.workers)
    runs, wins, qts = r.frames
    save_frames(ctx.out, runs, wins, qts)
    r.verdicts.to_csv(ctx.out / "open_verdicts.csv", index=False)
    r.table.to_csv(ctx.out / "open_table.csv", index=False)
    if r.search is not None:
        (ctx.out / "open_search.json").write_text(json.dumps(r.search, indent=2, default=float))
    finish(ctx, runs["seed"], {**_meta_extra(cfg, sec, r.specs, runs), "search": None if r.search is None else
                               {k: v for k, v in r.search.items() if k != "search_rows"}})
    _print(r.table)
    if r.search is not None:
        print("stable limit:", {k: v for k, v in r.search.items() if k != "search_rows"})
    print("result dir:", ctx.out)
    return ctx.out


def cmd_burst(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    sec = probe_section(cfg, "burst", args.quick)
    ctx = _begin("probe_burst", "prefix_meta_probe_burst", cfg, sec, args, repo_dir)
    r = run_burst(cfg, sec, workers=args.workers)
    runs, wins, qts = r.frames
    save_frames(ctx.out, r.runs, wins, qts)
    r.arms.to_csv(ctx.out / "burst_arms.csv", index=False)
    finish(ctx, r.runs["seed"], {**_meta_extra(cfg, sec, r.specs, r.runs), "arms": burst_arms(sec), "lambda": burst_lambda(sec)[0],
                                 "t_burst": sec["warmup_s"], "horizon_s": sec["warmup_s"] + sec["after_s"],
                                 "common_random_numbers": "same seed -> same Poisson stream and sessions for every arm; the burst is an extra stream"})
    _print(r.arms)
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Prefix-cache pilot probe: mu(n) curve / open-loop stability / burst with paired arms, "
                                             "arbitrary engine and workload overrides from a YAML spec")
    ap.add_argument("cmd", choices=list(SECTIONS))
    ap.add_argument("--spec", "--config", dest="config", required=True, help="YAML spec (see the module docstring / configs/prefix_meta_probe.yaml)")
    ap.add_argument("--quick", action="store_true", help="smoke-test sizes: merge probe.<section>.quick over the section")
    ap.add_argument("--workers", type=int, default=3, help=f"processes (at most {MAX_WORKERS}; also capped by the spec's parallel.max_workers)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override, e.g. engine.batching=mixed")
    ap.add_argument("--tag", default=None, help="suffix for the result dir name")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    if not (1 <= args.workers <= MAX_WORKERS):
        raise SystemExit(f"--workers must be in 1..{MAX_WORKERS}, got {args.workers}")
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    cfg = load_probe_config(args.config, repo_dir, args.set)
    {"curve": cmd_curve, "open": cmd_open, "burst": cmd_burst}[args.cmd](cfg, args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
