"""Round-5 experiments of the prefix-cache metastability pilot (allocation-mode robustness of the thrashing curve).

Question (config ``configs/prefix_meta_r5.yaml``, registered in ``configs/prefix_meta_r5_prereg.yaml``): is the metastability an
artifact of reserving each running request's full end-of-turn KV at admission (``full_reserve``), or does it persist under
vLLM-like on-demand allocation with recompute preemption (``ondemand_preempt``) and SGLang-like ``new_token_ratio`` reservation with
retraction (``ratio_reserve``)?

Commands::

    calib   lambda_miss(mode) for the three modes (round-1 E0 closed-population procedure, cache disabled)
    curve   closed-population mu(n) for FCFS-LRU and LPM-LRU in the three modes (3 seeds)
    burst   open system at 2 lambda_miss(mode) from empty, burst 200 and the paired no-burst run, registered modes (5 seeds)
    cap     cold 300 at 2 lambda_miss(mode): static cap at the mode's argmax n* and no cap, registered modes (3 seeds)
    report  prediction_eval.csv (S1-S4 per registered mode, registered readings first), tables and figures from the four result dirs
            (``--calib-dir --curve-dir --burst-dir --cap-dir``; sensitivity variants via ``--sens-dir variant:cmd=DIR``), see report_r5.py

``burst`` and ``cap`` need lambda_miss(mode) (``--calib-dir``, a ``calib`` result dir); ``cap`` also needs n* (``--curve-dir``, a ``curve``
result dir; the quick smoke may use ``cap.nstar_override`` instead).

Every command creates a NEW ``results/<name>/<YYYYmmdd-HHMMSS>/`` directory with ``config.yaml``, ``base_config.yaml``,
``config_effective.yaml``, ``preregistration.yaml``, ``meta.json`` (git commit + dirty flag captured at the START) and CSVs. At most 3 worker
processes.

Provenance guards (amendment 2, review finding F6). A non-quick run refuses ``--set`` overrides and a dirty git tree. ``burst`` and ``cap`` refuse
a ``--calib-dir`` / ``--curve-dir`` that is not a finished, non-quick, clean-tree result of the same variant, at the SAME commit as the current
HEAD, with exactly the registered seeds of its section (a quick run only consumes quick dirs). Sensitivity variants (``--variant NAME``, the
``variants`` block of the config) change engine switches or the grid as stated there; their results go to
``results/prefix_meta_r5_<cmd>_<variant>/`` and are never mixed with the registered ones.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import runner as R1
from .mech_runner import _meta, add_recovery, begin, exp_cfg_deep, finish, load_mech_config
from .r4_runner import closed_spec, point_metrics
from .runner import Runner, apply_overrides, collect_frames, git_info, save_frames, timing_summary
from .sim import RunSpec
from .workload import ArrivalPlan

ALL_MODES_KEY = ("registered", "reference")


def all_modes(cfg: dict) -> List[str]:
    """Registered modes first, then the reference mode (absent in a sensitivity variant that drops it)."""
    m = cfg["modes"]
    return list(m["registered"]) + ([m["reference"]] if m.get("reference") else [])


def mode_overrides(cfg: dict, mode: str) -> Dict[str, Any]:
    return dict(cfg["modes"]["engine_overrides"][mode])


def _tag(rs: RunSpec, mode: str, cfg: dict) -> RunSpec:
    """Attach the allocation mode to a run spec: engine overrides, variant suffix and the output column ``alloc_mode``."""
    rs.engine_overrides = {**rs.engine_overrides, **mode_overrides(cfg, mode)}
    rs.variant = f"mode={mode}|{rs.variant}"
    rs.meta = {**rs.meta, "alloc_mode": mode}
    return rs


# ======================================================================= thrash detector (amendment 2, review finding F3)
def preemption_stats(windows: Sequence[Dict[str, Any]], t_from: float, t_to: Optional[float] = None) -> Dict[str, float]:
    """Preemption / retraction statistics over the complete windows with ``t_start >= t_from`` (and ``t_end <= t_to``): events per admitted
    turn, the most preemptions suffered by one turn in any of these windows, and the work accounting
    (recompute_frac = prefill tokens PROCESSED for re-admitted requests / all processed prefill tokens;
    readmit_demand_frac = tokens demanded by re-admissions / processed prefill tokens, can exceed 1 under thrash;
    lost_prefill_frac = admitted prefill tokens discarded unprocessed / (processed + discarded))."""
    sel = [w for w in windows if w["t_start"] >= t_from - 1e-9 and (t_to is None or w["t_end"] <= t_to + 1e-9)]
    dur = float(sum(w["t_end"] - w["t_start"] for w in sel))
    pre = float(sum(w.get("preemptions", 0) for w in sel))
    adm = float(sum(w["admitted_turns"] for w in sel))
    pf = float(sum(w["prefill_tok_per_s"] * (w["t_end"] - w["t_start"]) for w in sel))
    rp = float(sum(w.get("recompute_processed", 0) for w in sel))
    dem = float(sum(w.get("recompute_tokens", 0) for w in sel))
    lost = float(sum(w.get("lost_prefill", 0) for w in sel))
    return {"preemptions_per_s": pre / dur if dur else float("nan"), "preemptions_per_turn": pre / adm if adm else float("nan"),
            "preempt_max_turn": float(max([w.get("preempt_max_turn", 0) for w in sel], default=0)),
            "recompute_tok_per_s": rp / dur if dur else float("nan"), "recompute_frac": rp / pf if pf else float("nan"),
            "readmit_demand_tok_per_s": dem / dur if dur else float("nan"), "readmit_demand_frac": dem / pf if pf else float("nan"),
            "lost_prefill_frac": lost / (pf + lost) if (pf + lost) else float("nan"),
            "prefill_tok_per_s": pf / dur if dur else float("nan")}


def thrash_flag(preempt_per_turn: float, preempt_max_turn: float, thr: Dict[str, float]) -> bool:
    """Registered label (amendment 2): preemption-thrash iff preemptions per admitted turn > ``preemptions_per_turn_above`` OR the most
    preemptions of one turn in the window set > ``max_per_turn_above``. Reported next to each verdict; it never changes a verdict."""
    ppt_bad = preempt_per_turn == preempt_per_turn and preempt_per_turn > float(thr["preemptions_per_turn_above"])
    return bool(ppt_bad or preempt_max_turn > float(thr["max_per_turn_above"]))


def add_tail_preemption(runs: pd.DataFrame, wins: pd.DataFrame, thr: Dict[str, float]) -> pd.DataFrame:
    """Per run: tail-window preemption statistics (the same last ``tail_s`` seconds as the recovery criterion) and the thrash label."""
    out = runs.copy()
    cols = {"tail_preemptions_per_turn": [], "tail_preempt_max_turn": [], "tail_recompute_frac": [], "tail_lost_prefill_frac": [],
            "tail_thrash": []}
    for _, r in out.iterrows():
        w = wins[wins["run_id"] == r["run_id"]].to_dict("records")
        st = preemption_stats(w, float(r["sim_end_s"]) - float(r["tail_s"]), float(r["sim_end_s"]))
        cols["tail_preemptions_per_turn"].append(st["preemptions_per_turn"])
        cols["tail_preempt_max_turn"].append(st["preempt_max_turn"])
        cols["tail_recompute_frac"].append(st["recompute_frac"])
        cols["tail_lost_prefill_frac"].append(st["lost_prefill_frac"])
        cols["tail_thrash"].append(thrash_flag(st["preemptions_per_turn"], st["preempt_max_turn"], thr))
    for k, v in cols.items():
        out[k] = v
    return out


# ======================================================================= variants and provenance guards (amendment 2, finding F6)
def apply_variant(cfg: dict, name: Optional[str]) -> dict:
    """Config of the sensitivity variant ``name`` (the ``variants`` block): dotted ``set`` overrides, an optional restriction of the modes
    (``modes``; the reference mode is dropped unless ``include_reference``) and of the commands (``commands``). ``None`` = registered."""
    if not name:
        return cfg
    v = (cfg.get("variants") or {}).get(name)
    if v is None:
        raise SystemExit(f"unknown --variant {name!r}; known: {sorted((cfg.get('variants') or {}))}")
    out = apply_overrides(cfg, v.get("set") or [])
    if v.get("modes"):
        out["modes"]["registered"] = list(v["modes"])
    if not v.get("include_reference", False):
        out["modes"]["reference"] = None
    out["_variant"] = {"name": name, **{k: v[k] for k in ("commands", "note") if k in v}}
    return out


def _extra(cfg: dict) -> Dict[str, Any]:
    return {"variant": (cfg.get("_variant") or {}).get("name"), "alloc_mode_overrides": cfg["modes"]["engine_overrides"]}


def _check_command_allowed(cmd: str, cfg: dict) -> None:
    v = cfg.get("_variant")
    if v and v.get("commands") and cmd not in v["commands"]:
        raise SystemExit(f"variant {v['name']!r} supports the commands {v['commands']} only, not {cmd!r}")


def guard_run(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> None:
    """A registered (non-quick) run refuses --set overrides and a dirty git tree."""
    if args.quick:
        return
    if args.set:
        raise SystemExit(f"a registered (non-quick) run accepts no --set overrides, got {args.set}")
    if git_info(repo_dir)["dirty"]:
        raise SystemExit("a registered (non-quick) run needs a clean git tree (commit first); quick runs are exempt")


def check_input_dir(d: str, experiment: str, section: str, cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Dict[str, Any]:
    """Refuse an upstream result dir that cannot decide a registered result: no finished meta.json, wrong experiment, a quick run feeding
    a registered one (or the reverse), a dirty tree, a different commit than the current HEAD, a different variant, or seeds other than
    the registered ones of its section. Returns its meta."""
    mf = Path(d) / "meta.json"
    if not mf.exists():
        raise SystemExit(f"{d}: no meta.json")
    m = json.loads(mf.read_text())
    if m.get("status") != "done" or m.get("experiment") != experiment:
        raise SystemExit(f"{d}: expected a finished {experiment!r} run, got status={m.get('status')!r} experiment={m.get('experiment')!r}")
    if bool(m.get("quick")) != bool(args.quick):
        raise SystemExit(f"{d}: quick={m.get('quick')} but this run has quick={bool(args.quick)} (quick and registered results never mix)")
    want_variant = (cfg.get("_variant") or {}).get("name")
    if m.get("variant") != want_variant:
        raise SystemExit(f"{d}: produced for variant {m.get('variant')!r}, this run is variant {want_variant!r}")
    if not args.quick:
        g = m.get("git") or {}
        if g.get("dirty") is not False:
            raise SystemExit(f"{d}: produced from a dirty (or unknown) git tree")
        head = git_info(repo_dir)["commit"]
        if g.get("commit") != head:
            raise SystemExit(f"{d}: produced at commit {g.get('commit')}, current HEAD is {head}")
        if m.get("overrides"):
            raise SystemExit(f"{d}: produced with --set overrides {m.get('overrides')}")
        seeds = sorted(int(x) for x in exp_cfg_deep(cfg, section, False)["seeds"])
        if sorted(int(x) for x in m.get("seeds", [])) != seeds:
            raise SystemExit(f"{d}: seeds {m.get('seeds')} are not the registered {seeds} of section {section!r}")
    return m


# ======================================================================= calibration: lambda_miss(mode)
def calib_specs(cfg: dict, cb: dict) -> List[RunSpec]:
    H = float(cb["horizon_s"])
    specs: List[RunSpec] = []
    for mode in all_modes(cfg):
        for sd in cb["seeds"]:
            rs = RunSpec(exp="r5_calib", policy=cb["policy"], seed=int(sd), horizon_s=H, variant=f"population={cb['population']}",
                         plan=ArrivalPlan(kind="closed", horizon_s=H, closed_n=int(cb["population"]), pool=int(cb["pool_sessions"])),
                         engine_overrides={"cache_enabled": bool(cb["cache_enabled"])},
                         meta={"lam": float("nan"), "lam_mult": float("nan"), "population": int(cb["population"])})
            specs.append(_tag(rs, mode, cfg))
    return specs


def calib_rows(specs: Sequence[RunSpec], results: Sequence[Dict[str, Any]], warmup_s: float, window_s: float) -> pd.DataFrame:
    rows = []
    for rs, res in zip(specs, results):
        mt = R1.miss_throughput(res, warmup_s, window_s)
        wins = [w for w in res["windows"] if w["t_start"] >= warmup_s - 1e-9]
        st = preemption_stats(res["windows"], warmup_s)
        rows.append({"mode": rs.meta["alloc_mode"], "seed": rs.seed, "sessions_per_s": mt["sessions_per_s"],
                     "turns_per_s": mt["turns_per_s"], "busy_frac": mt["busy_frac"], "n_sessions": mt["n_sessions"],
                     "preemptions_per_s": st["preemptions_per_s"], "preemptions_per_turn": st["preemptions_per_turn"],
                     "recompute_tok_per_s": st["recompute_tok_per_s"], "recompute_frac": st["recompute_frac"],
                     "lost_prefill_frac": st["lost_prefill_frac"],
                     "prefill_tok_per_s": float(np.mean([w["prefill_tok_per_s"] for w in wins])),
                     "n_windows": len(wins), "wall_s": res["summary"]["wall_s"]})
    return pd.DataFrame(rows)


def calib_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Per mode: seed-mean lambda_miss (the registered quantity), sample sd, per-seed values (ordered by seed)."""
    out = []
    for mode, g in rows.groupby("mode", sort=False):
        g = g.sort_values("seed")
        x = g["sessions_per_s"].to_numpy()
        out.append({"mode": mode, "lambda_miss": float(x.mean()), "sd": float(x.std(ddof=1)) if len(x) > 1 else float("nan"),
                    "n_seeds": int(len(x)), "per_seed": json.dumps([float(v) for v in x]),
                    "seeds": json.dumps([int(s) for s in g["seed"]]),
                    "preemptions_per_s": float(g["preemptions_per_s"].mean()),
                    "preemptions_per_turn": float(g["preemptions_per_turn"].mean()) if "preemptions_per_turn" in g else float("nan"),
                    "recompute_tok_per_s": float(g["recompute_tok_per_s"].mean()),
                    "recompute_frac": float(g["recompute_frac"].mean()) if "recompute_frac" in g else float("nan"),
                    "lost_prefill_frac": float(g["lost_prefill_frac"].mean()) if "lost_prefill_frac" in g else float("nan"),
                    "prefill_tok_per_s": float(g["prefill_tok_per_s"].mean())})
    return pd.DataFrame(out)


def cmd_calib(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    _check_command_allowed("calib", cfg)
    guard_run(cfg, args, repo_dir)
    cb = exp_cfg_deep(cfg, "calibration", args.quick)
    ctx = begin("r5_calib", "prefix_meta_r5_calib", cfg, {**cfg, "calibration_effective": cb}, args, repo_dir)
    specs = calib_specs(cfg, cb)
    W = float(cfg["metrics"]["window_s"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    rows = calib_rows(specs, results, float(cb["warmup_s"]), W)
    runs, wins, qts = collect_frames(results, specs)
    save_frames(ctx.out, runs, wins, qts)
    rows.to_csv(ctx.out / "calib_runs.csv", index=False)
    cs = calib_summary(rows)
    cs.to_csv(ctx.out / "calib_summary.csv", index=False)
    lam = {r["mode"]: r["lambda_miss"] for _, r in cs.iterrows()}
    (ctx.out / "calib_summary.json").write_text(json.dumps({"lambda_miss": lam, "warmup_s": cb["warmup_s"],
                                                           "horizon_s": cb["horizon_s"], "population": cb["population"]}, indent=2))
    finish(ctx, rows["seed"], {"n_runs": int(len(rows)), "timing": timing_summary(runs), "lambda_miss": lam,
                               "common_random_numbers": "same seed -> same workload for every mode", **_extra(cfg)})
    with pd.option_context("display.width", 250):
        print(cs.to_string())
    print("result dir:", ctx.out)
    return ctx.out


def load_lambda_miss(calib_dir: str) -> Dict[str, float]:
    """lambda_miss(mode) from a ``calib`` result dir (or its calib_summary.json)."""
    p = Path(calib_dir)
    p = p / "calib_summary.json" if p.is_dir() else p
    return {k: float(v) for k, v in json.loads(p.read_text())["lambda_miss"].items()}


# ======================================================================= curve: mu(n) per mode
def curve_specs(cfg: dict, cv: dict) -> List[RunSpec]:
    specs: List[RunSpec] = []
    for mode in all_modes(cfg):
        for pol in cv["policies"]:
            for n in cv["n_grid"]:
                for sd in cv["seeds"]:
                    rs = closed_spec(pol, int(n), 1.0, int(sd), cv, cfg["engine"])
                    rs.exp = "r5_curve"
                    specs.append(_tag(rs, mode, cfg))
    return specs


def point_metrics_r5(windows: Sequence[Dict[str, Any]], warmup_s: float, horizon_s: float, window_s: float,
                     thrash: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Round-4 steady-state metrics plus the allocation-mode columns of ``preemption_stats`` over the measurement window (all 0 / NaN-free in
    full_reserve) and, if ``thrash`` is given, the registered thrash label of the measurement window."""
    pm = point_metrics(windows, warmup_s, horizon_s, window_s)
    st = preemption_stats(windows, warmup_s)
    pm.update(st)
    if thrash is not None:
        pm["thrash"] = thrash_flag(st["preemptions_per_turn"], st["preempt_max_turn"], thrash)
    return pm


def curve_table(cr: pd.DataFrame) -> pd.DataFrame:
    """Per (mode, policy, n): seed-mean, sample sd (ddof 1), standard error of mu and the means of the other metrics."""
    rows = []
    for (mode, pol, nn), g in cr.groupby(["mode", "policy", "n_nominal"], sort=False):
        g = g.sort_values("seed")
        row = {"mode": mode, "policy": pol, "n_nominal": int(nn), "n_seeds": int(len(g)),
               "mu_mean": float(g["mu"].mean()), "mu_sd": float(g["mu"].std(ddof=1)) if len(g) > 1 else float("nan"),
               "mu_se": float(g["mu"].std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else float("nan"),
               "mu_per_seed": json.dumps([float(x) for x in g["mu"]]), "seeds": json.dumps([int(s) for s in g["seed"]])}
        for c in ("hit_rate", "gpu_busy", "resident_kv_tokens", "reserved_tokens", "idle_tokens", "evictions_per_s", "turns_per_s",
                  "mu_first_half", "mu_second_half", "preemptions_per_s", "preemptions_per_turn", "recompute_tok_per_s",
                  "recompute_frac", "readmit_demand_frac", "lost_prefill_frac"):
            if c in g:
                row[c + "_mean"] = float(g[c].mean())
        if "preempt_max_turn" in g:
            row["preempt_max_turn_max"] = float(g["preempt_max_turn"].max())
        if "thrash" in g:
            row["n_thrash"] = int(g["thrash"].astype(bool).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def nstar_from_curve_table(ct: pd.DataFrame, mode: str, policy: str = "fcfs_lru") -> int:
    """n* = first argmax over the grid of the seed-mean FCFS-LRU mu(n) of ``mode`` (ties: smallest n) -- the registered S3 rule."""
    g = ct[(ct["mode"] == mode) & (ct["policy"] == policy)].sort_values("n_nominal")
    if g.empty:
        raise ValueError(f"no {policy} curve rows for mode {mode!r}")
    return int(g["n_nominal"].iloc[int(np.argmax(g["mu_mean"].to_numpy()))])


def cmd_curve(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    _check_command_allowed("curve", cfg)
    guard_run(cfg, args, repo_dir)
    cv = exp_cfg_deep(cfg, "curve", args.quick)
    thr = cfg["thrash"]
    ctx = begin("r5_curve", "prefix_meta_r5_curve", cfg, {**cfg, "curve_effective": cv}, args, repo_dir)
    specs = curve_specs(cfg, cv)
    W = float(cfg["metrics"]["window_s"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    cr = pd.DataFrame([{"mode": rs.meta["alloc_mode"], "policy": rs.policy, "n_nominal": rs.meta["n_nominal"], "n": rs.meta["population"],
                        "seed": rs.seed, **point_metrics_r5(res["windows"], cv["warmup_s"], cv["horizon_s"], W, thr),
                        "max_preempt_per_turn_run": res["summary"].get("max_preempt_per_turn", 0),
                        "wall_s": res["summary"]["wall_s"]} for rs, res in zip(specs, results)])
    runs, wins, _ = collect_frames(results, specs)
    runs.to_csv(ctx.out / "runs.csv", index=False)
    wins.to_csv(ctx.out / "windows.csv", index=False)
    cr.to_csv(ctx.out / "curve_runs.csv", index=False)
    ct = curve_table(cr)
    ct.to_csv(ctx.out / "curve_table.csv", index=False)
    nstar = {m: nstar_from_curve_table(ct, m) for m in all_modes(cfg)} if set(cv["policies"]) >= {"fcfs_lru"} else {}
    finish(ctx, cr["seed"], {"n_runs": int(len(cr)), "timing": timing_summary(runs), "n_grid": list(cv["n_grid"]),
                             "warmup_s": cv["warmup_s"], "horizon_s": cv["horizon_s"], "nstar_by_mode": nstar,
                             "common_random_numbers": "same seed -> same workload stream for every mode, policy and n", **_extra(cfg)})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(ct[["mode", "policy", "n_nominal", "n_seeds", "mu_mean", "mu_sd", "hit_rate_mean", "gpu_busy_mean",
                  "preemptions_per_s_mean", "recompute_frac_mean"]].to_string())
    print("n* by mode:", nstar)
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= burst
def burst_specs(cfg: dict, bd: dict, lam_miss: Dict[str, float]) -> List[RunSpec]:
    tb = float(bd["warmup_s"])
    H = tb + float(bd["after_s"])
    specs: List[RunSpec] = []
    for mode in cfg["modes"]["registered"]:
        lam = float(bd["lam_mult"]) * lam_miss[mode]
        for b in bd["sizes"]:
            for sd in bd["seeds"]:
                rs = RunSpec(exp="r5_burst", policy=bd["policy"], seed=int(sd), horizon_s=H, variant=f"burst={b}",
                             plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=int(b), burst_t0=tb,
                                              burst_width_s=float(bd["burst_width_s"])),
                             meta=_meta(lam, float(bd["lam_mult"]), burst_n=int(b), t_burst=tb))
                specs.append(_tag(rs, mode, cfg))
    return specs


def burst_counts(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (mode, burst size): runs, not-recovered count, tail hit / backlog means, preemption statistics (run totals, tail-window rate per
    admitted turn, most preemptions of one turn in the tail, number of tail-thrash runs)."""
    out = runs.groupby(["alloc_mode", "burst_n"], sort=False).agg(
        n_runs=("seed", "size"), n_recovered=("recovered", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
        tail_backlog_mean=("tail_backlog_mean", "mean"), tail_sessions_per_s=("tail_sessions_per_s", "mean"),
        n_preempt_mean=("n_preempt", "mean"), tail_preemptions_per_turn_mean=("tail_preemptions_per_turn", "mean"),
        tail_preempt_max_turn_max=("tail_preempt_max_turn", "max"), n_tail_thrash=("tail_thrash", "sum"),
        max_preempt_per_turn_run_max=("max_preempt_per_turn", "max")).reset_index()
    out["n_not_recovered"] = out["n_runs"] - out["n_recovered"]
    return out


def cmd_burst(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    _check_command_allowed("burst", cfg)
    bd = exp_cfg_deep(cfg, "burst", args.quick)
    if not args.calib_dir:
        raise SystemExit("burst needs --calib-dir (a `calib` result dir)")
    guard_run(cfg, args, repo_dir)
    check_input_dir(args.calib_dir, "r5_calib", "calibration", cfg, args, repo_dir)
    lam = load_lambda_miss(args.calib_dir)
    ctx = begin("r5_burst", "prefix_meta_r5_burst", cfg, {**cfg, "burst_effective": bd, "lambda_miss_by_mode": lam,
                                                          "calib_dir": str(args.calib_dir)}, args, repo_dir)
    specs = burst_specs(cfg, bd, lam)
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, bd["recovered_hit_above"], bd["recovered_backlog_below"])
    runs = add_tail_preemption(runs, wins, cfg["thrash"])
    save_frames(ctx.out, runs, wins, qts)
    bc = burst_counts(runs)
    bc.to_csv(ctx.out / "burst_counts.csv", index=False)
    finish(ctx, runs["seed"], {"n_runs": int(len(runs)), "timing": timing_summary(runs), "lambda_miss_by_mode": lam,
                               "calib_dir": str(args.calib_dir), "t_burst": bd["warmup_s"],
                               "horizon_s": bd["warmup_s"] + bd["after_s"],
                               "common_random_numbers": "same seed -> same workload for both burst sizes (the Poisson stream is "
                                                        "shared; the burst sessions are an extra stream); modes differ in lambda",
                               **_extra(cfg)})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(bc.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= cap
def cap_specs(cfg: dict, cd: dict, lam_miss: Dict[str, float], nstar: Dict[str, int]) -> List[RunSpec]:
    H = float(cd["horizon_s"])
    specs: List[RunSpec] = []
    for mode in cfg["modes"]["registered"]:
        lam = float(cd["lam_mult"]) * lam_miss[mode]
        for arm in cd["arms"]:
            cap: Optional[int] = int(nstar[mode]) if arm == "capped_at_nstar" else None
            for sd in cd["seeds"]:
                rs = RunSpec(exp="r5_cap", policy=cd["policy"], seed=int(sd), horizon_s=H, variant=f"arm={arm}",
                             session_cap_override=cap,
                             plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, initial_cold=int(cd["cold_sessions"])),
                             meta=_meta(lam, float(cd["lam_mult"]), arm=arm, cap=-1 if cap is None else cap,
                                        cold_sessions=int(cd["cold_sessions"])))
                specs.append(_tag(rs, mode, cfg))
    return specs


def cap_cells(runs: pd.DataFrame) -> pd.DataFrame:
    out = runs.groupby(["alloc_mode", "arm"], sort=False).agg(
        cap=("cap", "first"), n_runs=("seed", "size"), n_recovered=("recovered", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
        tail_backlog_mean=("tail_backlog_mean", "mean"), tail_gate_mean=("tail_gate_mean", "mean"),
        tail_sessions_per_s=("tail_sessions_per_s", "mean"), n_preempt_mean=("n_preempt", "mean"),
        tail_preemptions_per_turn_mean=("tail_preemptions_per_turn", "mean"), tail_preempt_max_turn_max=("tail_preempt_max_turn", "max"),
        n_tail_thrash=("tail_thrash", "sum"), max_preempt_per_turn_run_max=("max_preempt_per_turn", "max")).reset_index()
    return out


def cmd_cap(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    _check_command_allowed("cap", cfg)
    cd = exp_cfg_deep(cfg, "cap", args.quick)
    if not args.calib_dir:
        raise SystemExit("cap needs --calib-dir (a `calib` result dir)")
    guard_run(cfg, args, repo_dir)
    check_input_dir(args.calib_dir, "r5_calib", "calibration", cfg, args, repo_dir)
    lam = load_lambda_miss(args.calib_dir)
    if args.curve_dir:
        check_input_dir(args.curve_dir, "r5_curve", "curve", cfg, args, repo_dir)
        ct = pd.read_csv(Path(args.curve_dir) / "curve_table.csv")
        nstar = {m: nstar_from_curve_table(ct, m) for m in cfg["modes"]["registered"]}
        nstar_source = str(args.curve_dir)
    else:
        if not args.quick:
            raise SystemExit("a registered (non-quick) cap run needs --curve-dir; cap.nstar_override is for quick smoke tests only")
        nstar = {m: int(v) for m, v in (cd.get("nstar_override") or {}).items()}
        missing = [m for m in cfg["modes"]["registered"] if m not in nstar]
        if missing:
            raise SystemExit(f"cap needs --curve-dir (or cap.nstar_override for modes {missing})")
        nstar_source = "cap.nstar_override (NOT the registered rule)"
    ctx = begin("r5_cap", "prefix_meta_r5_cap", cfg, {**cfg, "cap_effective": cd, "lambda_miss_by_mode": lam, "nstar_by_mode": nstar,
                                                       "nstar_source": nstar_source, "calib_dir": str(args.calib_dir)}, args, repo_dir)
    specs = cap_specs(cfg, cd, lam, nstar)
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, cd["recovered_hit_above"], cd["recovered_backlog_below"])
    runs = add_tail_preemption(runs, wins, cfg["thrash"])
    save_frames(ctx.out, runs, wins, qts)
    cc = cap_cells(runs)
    cc.to_csv(ctx.out / "cap_cells.csv", index=False)
    finish(ctx, runs["seed"], {"n_runs": int(len(runs)), "timing": timing_summary(runs), "lambda_miss_by_mode": lam,
                               "nstar_by_mode": nstar, "nstar_source": nstar_source, "calib_dir": str(args.calib_dir),
                               "common_random_numbers": "same seed -> same workload for the capped and the uncapped arm", **_extra(cfg)})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(cc.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Prefix-cache metastability pilot, round 5 (allocation modes; simulation)")
    ap.add_argument("cmd", choices=["calib", "curve", "burst", "cap", "report"])
    ap.add_argument("--config", default="configs/prefix_meta_r5.yaml")
    ap.add_argument("--quick", action="store_true", help="smoke-test sizes (short horizons, one seed, unregistered seeds)")
    ap.add_argument("--workers", type=int, default=3, help="processes (hard-capped by config parallel.max_workers = 3)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--calib-dir", default=None, help="burst / cap: `calib` result dir (lambda_miss per mode)")
    ap.add_argument("--curve-dir", default=None, help="cap, report: `curve` result dir (n* per mode)")
    ap.add_argument("--burst-dir", default=None, help="report: `burst` result dir")
    ap.add_argument("--cap-dir", default=None, help="report: `cap` result dir")
    ap.add_argument("--sens-dir", action="append", default=[], metavar="VARIANT:CMD=DIR",
                    help="report: result dir of a sensitivity variant, e.g. stage1_whole_victim:curve=results/.../ (repeatable)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override")
    ap.add_argument("--tag", default=None, help="suffix for the result dir name")
    ap.add_argument("--variant", default=None, help="sensitivity variant (a key of the config `variants` block); results go to "
                                                    "results/prefix_meta_r5_<cmd>_<variant>/")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(args.config).resolve().parent.parent
    cfg = apply_overrides(load_mech_config(args.config, repo_dir), args.set)
    if args.variant:
        cfg = apply_variant(cfg, args.variant)
        args.tag = args.variant if not args.tag else f"{args.variant}_{args.tag}"
    if args.cmd == "report":
        from .report_r5 import cmd_report
        cmd_report(cfg, args, repo_dir)
        return 0
    {"calib": cmd_calib, "curve": cmd_curve, "burst": cmd_burst, "cap": cmd_cap}[args.cmd](cfg, args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
