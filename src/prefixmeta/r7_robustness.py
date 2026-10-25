"""Round 7, simulator ROBUSTNESS: tool-time sweep, burst-size sweep, horizon and low-lambda fragility of the calibrated simulator.

Spec and declared definitions: ``configs/r7_robustness.yaml`` (``r7:`` block; committed before the runs). Nothing here re-implements simulation, metrics or
classification: every stage calls the probe runner (``probe.run_curve`` / ``run_open`` / ``run_burst``, which call ``Runner``) and the round-6 B3 window
statistics (``r6_predict.eval_stats`` / ``classify``). Every stage writes a NEW ``results/r7_<stage>/<timestamp>/`` (config copies, ``meta.json`` with the
git commit and dirty flag captured at the start, seeds, CSVs, ``summary.json``) and appends ``stage<TAB>dir`` to ``results/r7_robustness/manifest.tsv``;
later stages read the latest manifest entry of the stages they depend on.

    python experiments/r7_robustness_run.py <stage> --spec configs/r7_robustness.yaml [--workers 6] [--only exp1 exp5 ...] [--set key=val]

    lambda_miss   B1 per workload: cache off, closed POP 32 (and the labelled POP 64 check), seeds 0-2
    curves        closed curve mu(n) per workload (cache on), peak n and the cap n (smallest n within 5% of the peak)
    edge          from-empty stability on multiples of the workload's lambda_miss (10 seeds), the measured window [1, hi] and the two test points
    pairs         paired NOBURST / BURST / CAPPED arms at the two points of every workload with a non-empty window (10 seeds)
    burst_sizes   record workload, 2 lambdas x 5 burst sizes (+ shared NOBURST), 10 seeds
    horizon       record workload, 2 lambdas, BURST and NOBURST with 30000 s after the burst, 10 seeds
    lowlam        record workload, 1.35 x lambda_miss, BURST, 20 seeds: slope distribution and TRAPPED / INDETERMINATE counts

The report (tables, notes file) is ``prefixmeta.r7_report``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .mech_runner import begin, finish
from .probe import load_probe_config, probe_section, run_burst, run_curve, run_open
from .r6_predict import classify, eval_stats
from .sim import deep_update
from .workload import WorkloadParams, tool_time_moments

MAX_WORKERS = 6
STAGES = ("lambda_miss", "curves", "edge", "pairs", "burst_sizes", "horizon", "lowlam")


# ======================================================================= provenance: manifest of stage result dirs
def manifest_path(out_root: str) -> Path:
    return Path(out_root) / "r7_robustness" / "manifest.tsv"


def register(out_root: str, stage: str, d: Path) -> None:
    mp = manifest_path(out_root)
    mp.parent.mkdir(parents=True, exist_ok=True)
    if not mp.exists():
        mp.write_text("stage\tdir\n")
    with open(mp, "a", newline="") as f:
        f.write(f"{stage}\t{d.as_posix()}\n")


def stage_dir(out_root: str, stage: str) -> Path:
    """Latest registered result dir of ``stage``."""
    mp = manifest_path(out_root)
    if not mp.exists():
        raise FileNotFoundError(f"no manifest {mp}: run the stage {stage!r} first")
    m = pd.read_csv(mp, sep="\t")
    m = m[m["stage"] == stage]
    if m.empty:
        raise FileNotFoundError(f"stage {stage!r} is not in {mp}")
    return Path(m["dir"].iloc[-1])


def stage_summary(out_root: str, stage: str) -> dict:
    return json.loads((stage_dir(out_root, stage) / "summary.json").read_text())


# ======================================================================= declarations
def r7_block(cfg: dict) -> dict:
    return cfg["r7"]


def workload_names(r7: dict, only: Optional[Sequence[str]]) -> List[str]:
    names = list(r7["workloads"])
    if only:
        bad = [o for o in only if o not in names]
        if bad:
            raise ValueError(f"unknown workload(s) {bad}; known: {names}")
        names = [n for n in names if n in only]
    return names


def wl_over(r7: dict, name: str) -> dict:
    return dict(r7["workloads"][name]["workload"])


def merged_workload(cfg: dict, r7: dict, name: str) -> WorkloadParams:
    return WorkloadParams.from_dict(deep_update(cfg["workload"], wl_over(r7, name)))


def expected_turns(cfg: dict, r7: dict, name: str) -> float:
    """E[T] of a workload; asserted to equal the declared value (it does not depend on the tool-time distribution)."""
    et = merged_workload(cfg, r7, name).effective_mean_turns()
    if abs(et - float(r7["expected_turns"])) > 5e-4:
        raise ValueError(f"E[T]={et} of workload {name} differs from the declared {r7['expected_turns']}")
    return et


def round_to(x: float, step: float) -> float:
    return round(float(np.round(x / step) * step), 6)


def window_points(hi: float, w: dict) -> List[float]:
    """The paired-arm test points lo + (hi - lo) * f, rounded to ``round_to``; [] if the window is empty (hi <= empty_if_hi_at_most)."""
    lo = float(w["lo"])
    if hi <= float(w["empty_if_hi_at_most"]) + 1e-12:
        return []
    return [round_to(lo + (hi - lo) * float(f), float(w["round_to"])) for f in w["point_fractions"]]


def need_count(n: int, min_frac: float) -> int:
    """ceil(min_frac * n) with the round-6 epsilon (7 of 10 for 2/3)."""
    return int(math.ceil(min_frac * n - 1e-9))


# ======================================================================= pure helpers (unit-tested)
def contiguous_edge(mults: Sequence[float], all_stable: Sequence[bool], lo: float = 1.0) -> float:
    """Largest multiple m such that EVERY grid multiple <= m is all-stable; ``lo`` if even the smallest is not (empty window)."""
    order = np.argsort(np.asarray(mults, dtype=float), kind="stable")
    edge = lo
    for i in order:
        if bool(all_stable[i]):
            edge = float(mults[i])
        else:
            break
    return edge


def largest_all_stable(mults: Sequence[float], all_stable: Sequence[bool], lo: float = 1.0) -> float:
    ok = [float(m) for m, s in zip(mults, all_stable) if bool(s)]
    return max(ok) if ok else lo


def smallest_within(ns: Sequence[int], mu: Sequence[float], tol: float = 0.05) -> Tuple[int, float, int]:
    """(peak n, peak mu, cap n): peak = first argmax of ``mu`` over the (ascending) grid, cap = smallest n with mu >= (1 - tol) * peak mu."""
    order = np.argsort(np.asarray(ns))
    n_s = [int(ns[i]) for i in order]
    m_s = [float(mu[i]) for i in order]
    k = int(np.argmax(m_s))                                   # first maximum
    peak_mu = m_s[k]
    cap = next(n for n, m in zip(n_s, m_s) if m >= (1.0 - tol) * peak_mu - 1e-15)
    return n_s[k], peak_mu, cap


def classify_label(trapped: bool, recovered: bool, indeterminate: bool) -> str:
    if trapped and recovered:
        return "BOTH"
    if trapped:
        return "TRAPPED"
    if recovered:
        return "RECOVERED"
    if indeterminate:
        return "INDETERMINATE"
    return "OTHER"


def classify_burst_frames(runs: pd.DataFrame, wins: pd.DataFrame, lam_miss: float, token_rate_miss: float, p: dict,
                          eval_rel: Sequence[float], extra: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """One row per (arm, seed) of a ``run_burst`` result with the B3 window statistics over [t_burst + eval_rel[0], t_burst + eval_rel[1]] and the
    declared TRAPPED / RECOVERED / INDETERMINATE classification (``classify`` of round 6 plus the ``indeterminate`` class)."""
    by_run = {rid: g for rid, g in wins.groupby("run_id")}
    rows = []
    for _, r in runs.iterrows():
        tb = float(r["t_burst"])
        st = eval_stats(by_run[r["run_id"]], tb + float(eval_rel[0]), tb + float(eval_rel[1]))
        lam = float(r["lam"])
        c = classify(st, lam, lam_miss, token_rate_miss, p)
        ind = bool(st["hit"] < float(p["indeterminate_hit_below"])) and not c["trapped"] if st["hit"] == st["hit"] else False
        rows.append({**(extra or {}), "run_id": int(r["run_id"]), "lam": lam, "arm": r["arm"], "seed": int(r["seed"]), "cap": int(r["cap"]),
                     "burst_n": int(r["burst_n"]), "n_windows": st["n_windows"], "hit": st["hit"], "backlog": st["backlog"], "slope": st["slope"],
                     "token_rate": st["token_rate"], "token_ratio": c["token_ratio"], "slope_threshold": c["slope_threshold"],
                     "rise_over_window": st["slope"] * (float(eval_rel[1]) - float(eval_rel[0])), "rate_ok": c["rate_ok"], "slope_ok": c["slope_ok"],
                     "trapped": c["trapped"], "recovered": c["recovered"], "indeterminate": ind,
                     "label": classify_label(c["trapped"], c["recovered"], ind)})
    return pd.DataFrame(rows)


def run_events(w: pd.DataFrame, t_burst: float, p: dict) -> Dict[str, float]:
    """Per-run event times from the 100 s windows ``w`` of one run (declared in the config, ``horizon:``): collapse_s (first window, any time, with
    backlog = queue_mean + gate_mean above ``collapse_backlog_above``), trap_onset_s (end of the first window starting at or after t_burst with hit rate below
    ``trap_hit_below``), release_s (end of the first window after the onset with hit rate above ``release_hit_above``), all NaN if the event never happens,
    plus the extremes needed to read them."""
    s = w.sort_values("t_start")
    backlog = (s["queue_mean"] + s["gate_mean"]).to_numpy(dtype=float)
    hit = s["hit_rate"].to_numpy(dtype=float)
    t_start = s["t_start"].to_numpy(dtype=float)
    t_end = s["t_end"].to_numpy(dtype=float)
    nan = float("nan")
    over = np.nonzero(backlog > float(p["collapse_backlog_above"]))[0]
    collapse = float(t_end[over[0]]) if len(over) else nan
    post = np.nonzero((t_start >= t_burst - 1e-9) & (hit < float(p["trap_hit_below"])))[0]
    onset_i = int(post[0]) if len(post) else None
    onset = float(t_end[onset_i]) if onset_i is not None else nan
    release = nan
    if onset_i is not None:
        rel = np.nonzero((np.arange(len(hit)) > onset_i) & (hit > float(p["release_hit_above"])))[0]
        release = float(t_end[rel[0]]) if len(rel) else nan
    after = (t_start >= t_burst - 1e-9)
    return {"collapse_s": collapse, "trap_onset_s": onset, "release_s": release, "max_backlog": float(np.nanmax(backlog)),
            "final_backlog": float(backlog[-1]), "final_hit": float(hit[-1]) if np.isfinite(hit[-1]) else nan,
            "min_hit_after_burst": float(np.nanmin(hit[after])) if after.any() else nan}


def quantiles(x: Sequence[float], qs: Sequence[float] = (0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0)) -> Dict[str, float]:
    a = np.asarray(list(x), dtype=float)
    return {f"q{int(round(q * 100)):03d}": float(np.quantile(a, q)) for q in qs}


# ======================================================================= stage plumbing
def start(stage: str, cfg: dict, args: argparse.Namespace, repo_dir: Path):
    cfg_eff = {k: v for k, v in cfg.items() if k not in ("preregistration_file",)}
    return begin(f"r7_{stage}", f"r7_{stage}", cfg_eff, cfg_eff, args, repo_dir)


def end(ctx, args: argparse.Namespace, seeds: Sequence[int], extra: Dict[str, Any], summary: Dict[str, Any]) -> Path:
    (ctx.out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    finish(ctx, seeds, extra)
    register(args.out_root, ctx.experiment.replace("r7_", "", 1), ctx.out)
    return ctx.out


def concat(frames: List[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def curve_section(cfg: dict, r7: dict, block: dict, cache_enabled: bool, n_grid: Sequence[int], name: str) -> dict:
    sec = probe_section(cfg, "curve", False)
    return deep_update(sec, {"policies": [r7["policy"]], "n_grid": [int(n) for n in n_grid], "seeds": [int(s) for s in block["seeds"]],
                             "warmup_s": float(block["warmup_s"]), "horizon_s": float(block["horizon_s"]), "pool_sessions": int(block["pool_sessions"]),
                             "cache_enabled": bool(cache_enabled), "workload": wl_over(r7, name)})


def closed_rows(result, workload: str, E_T: float, warm: float, hor: float, W: float) -> pd.DataFrame:
    """One row per (n, seed) of a ``run_curve`` result: mu, mu_turns (turns / s / E[T]), token rate (mean per-window prefill_tok_per_s over the measured
    windows), busy fraction (mean per-window busy_frac), hit rate."""
    _, wins, _ = result.frames
    rows = []
    for i, r in result.runs.reset_index(drop=True).iterrows():
        sel = wins[(wins["run_id"] == i) & (wins["t_start"] >= warm - 1e-9) & (wins["t_end"] <= hor + 1e-9)]
        if len(sel) != round((hor - warm) / W):
            raise ValueError(f"{workload}: run {i} has {len(sel)} measurement windows")
        rows.append({"workload": workload, "n": int(r["n_nominal"]), "seed": int(r["seed"]), "mu": float(r["mu"]), "turns_per_s": float(r["turns_per_s"]),
                     "mu_turns": float(r["turns_per_s"]) / E_T, "token_rate": float(sel["prefill_tok_per_s"].mean()),
                     "busy": float(sel["busy_frac"].mean()), "hit_rate": float(r["hit_rate"]), "evictions_per_s": float(r.get("evictions_per_s", float("nan")))})
    return pd.DataFrame(rows)


# ======================================================================= stage: lambda_miss (B1)
def stage_lambda_miss(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    b = r7["lambda_miss"]
    W = float(cfg["metrics"]["window_s"])
    ctx = start("lambda_miss", cfg, args, repo_dir)
    rows: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workloads": {}}
    pops = [int(b["population"])] + [int(x) for x in b.get("check_populations") or []]
    for name in workload_names(r7, args.only):
        E_T = expected_turns(cfg, r7, name)
        sec = curve_section(cfg, r7, b, False, pops, name)
        res = run_curve(cfg, sec, workers=args.workers)
        df = closed_rows(res, name, E_T, float(b["warmup_s"]), float(b["horizon_s"]), W)
        rows.append(df)
        ref = df[df["n"] == int(b["population"])]
        w = {"label": r7["workloads"][name]["label"], "population": int(b["population"]), "n_seeds": int(ref["seed"].nunique()),
             "lambda_miss_turns": float(ref["mu_turns"].mean()), "lambda_miss_turns_sd": float(ref["mu_turns"].std(ddof=1)) if len(ref) > 1 else float("nan"),
             "lambda_miss_sessions": float(ref["mu"].mean()), "lambda_miss_sessions_sd": float(ref["mu"].std(ddof=1)) if len(ref) > 1 else float("nan"),
             "token_rate": float(ref["token_rate"].mean()), "busy": float(ref["busy"].mean()), "E_T": E_T,
             "tool_time_mean_s": tool_time_moments(merged_workload(cfg, r7, name))[0], "tool_time_cv": tool_time_moments(merged_workload(cfg, r7, name))[1]}
        for pop in pops[1:]:
            c = df[df["n"] == pop]
            w[f"check_pop{pop}"] = {"lambda_miss_turns": float(c["mu_turns"].mean()), "token_rate": float(c["token_rate"].mean()), "busy": float(c["busy"].mean()),
                                    "n_seeds": int(c["seed"].nunique())}
        summ["workloads"][name] = w
        print(f"[lambda_miss] {name}: {w['lambda_miss_turns']:.5f} sessions/s (turns-based), token rate {w['token_rate']:.0f}, busy {w['busy']:.3f}", flush=True)
    concat(rows).to_csv(ctx.out / "lambda_miss_runs.csv", index=False)
    return end(ctx, args, b["seeds"], {"stage": "lambda_miss", "only": args.only}, summ)


# ======================================================================= stage: curves
def stage_curves(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    b = r7["curve"]
    W = float(cfg["metrics"]["window_s"])
    ctx = start("curves", cfg, args, repo_dir)
    rows: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workloads": {}}
    for name in workload_names(r7, args.only):
        E_T = expected_turns(cfg, r7, name)
        sec = curve_section(cfg, r7, b, True, b["n_grid"], name)
        res = run_curve(cfg, sec, workers=args.workers)
        df = closed_rows(res, name, E_T, float(b["warmup_s"]), float(b["horizon_s"]), W)
        rows.append(df)
        t = df.groupby("n").agg(mu_turns=("mu_turns", "mean"), mu=("mu", "mean"), hit=("hit_rate", "mean")).reset_index().sort_values("n")
        n_pk, mu_pk, cap = smallest_within(t["n"].tolist(), t["mu_turns"].tolist(), 0.05)
        n_pk_s, mu_pk_s, cap_s = smallest_within(t["n"].tolist(), t["mu"].tolist(), 0.05)
        summ["workloads"][name] = {"label": r7["workloads"][name]["label"], "peak_n": n_pk, "peak_mu_turns": mu_pk, "cap_n": cap,
                                   "peak_n_sessions_based": n_pk_s, "peak_mu_sessions": mu_pk_s, "cap_n_sessions_based": cap_s,
                                   "mu_turns_by_n": {int(r.n): float(r.mu_turns) for r in t.itertuples()},
                                   "mu_sessions_by_n": {int(r.n): float(r.mu) for r in t.itertuples()},
                                   "hit_by_n": {int(r.n): float(r.hit) for r in t.itertuples()}}
        print(f"[curves] {name}: peak n={n_pk} mu_turns={mu_pk:.5f}, cap n={cap} (sessions-based: peak {n_pk_s}, cap {cap_s})", flush=True)
    concat(rows).to_csv(ctx.out / "curve_runs.csv", index=False)
    return end(ctx, args, b["seeds"], {"stage": "curves", "only": args.only}, summ)


# ======================================================================= stage: edge (B2 rule on multiples of lambda_miss)
def open_section(cfg: dict, r7: dict, e: dict, name: str, lam_miss: float, mults: Sequence[float]) -> dict:
    sec = probe_section(cfg, "open", False)
    return deep_update(sec, {"policy": r7["policy"], "lambdas": None, "lambda_miss": float(lam_miss), "lam_mults": [float(m) for m in mults],
                             "seeds": [int(s) for s in e["seeds"]], "horizon_s": float(e["horizon_s"]),
                             "unstable_backlog_stop": int(e["unstable_backlog_stop"]), "stable_final_backlog_below": float(e["stable_final_backlog_below"]),
                             "stable_trend_window_s": float(e["stable_trend_window_s"]), "stable_trend_max_rise": float(e["stable_trend_max_rise"]),
                             "workload": wl_over(r7, name)})


def edge_table(v: pd.DataFrame) -> pd.DataFrame:
    """Per multiple: n_runs, n_stable, mean / max final backlog, mean trend rise, mean tail hit, all_stable."""
    g = v.groupby("lam_mult", sort=True)
    t = g.agg(n_runs=("stable", "size"), n_stable=("stable", "sum"), final_backlog_mean=("final_backlog", "mean"), final_backlog_max=("final_backlog", "max"),
              trend_rise_mean=("trend_rise", "mean"), tail_hit_mean=("tail_hit_rate", "mean"), n_stopped_early=("stopped_early", "sum")).reset_index()
    t["n_stable"] = t["n_stable"].astype(int)
    t["all_stable"] = t["n_stable"] == t["n_runs"]
    return t


def stage_edge(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    e = r7["edge"]
    lm = stage_summary(args.out_root, "lambda_miss")["workloads"]
    ctx = start("edge", cfg, args, repo_dir)
    verd: List[pd.DataFrame] = []
    wins_all: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workloads": {}, "lambda_miss_dir": str(stage_dir(args.out_root, "lambda_miss"))}
    for name in workload_names(r7, args.only):
        lam_miss = float(lm[name]["lambda_miss_turns"])
        parts = []
        mult_sets = [[float(m) for m in e["multiples"]]]
        refined = False
        k = 0
        while k < len(mult_sets):
            sec = open_section(cfg, r7, e, name, lam_miss, mult_sets[k])
            res = run_open(cfg, sec, workers=args.workers)
            vd = res.verdicts.copy()
            vd.insert(0, "workload", name)
            vd["refinement"] = k > 0
            parts.append(vd)
            w = res.frames[1].copy()
            w.insert(0, "workload", name)
            wins_all.append(w)
            tab = edge_table(concat(parts))
            lowest = float(tab["lam_mult"].min())
            if k == 0 and not bool(tab[tab["lam_mult"] == lowest]["all_stable"].iloc[0]) and e.get("refine_if_lowest_unstable"):
                mult_sets.append([float(m) for m in e["refine_if_lowest_unstable"]])
                refined = True
            k += 1
        v = concat(parts)
        verd.append(v)
        tab = edge_table(v)
        hi = contiguous_edge(tab["lam_mult"].tolist(), tab["all_stable"].tolist(), float(r7["window"]["lo"]))
        hi_any = largest_all_stable(tab["lam_mult"].tolist(), tab["all_stable"].tolist(), float(r7["window"]["lo"]))
        pts = window_points(hi, r7["window"])
        summ["workloads"][name] = {"label": r7["workloads"][name]["label"], "lambda_miss_turns": lam_miss, "hi": hi, "hi_largest_all_stable": hi_any,
                                   "contiguous_equals_largest": bool(abs(hi - hi_any) < 1e-12), "refined": refined, "window_empty": len(pts) == 0,
                                   "points": pts, "n_seeds": int(len(e["seeds"])),
                                   "n_stable_by_mult": {f"{r.lam_mult:g}": int(r.n_stable) for r in tab.itertuples()}}
        print(f"[edge] {name}: hi={hi:g} (largest all-stable {hi_any:g}), refined={refined}, points={pts}", flush=True)
    concat(verd).to_csv(ctx.out / "edge_verdicts.csv", index=False)
    concat(wins_all).to_csv(ctx.out / "windows.csv", index=False)
    return end(ctx, args, e["seeds"], {"stage": "edge", "only": args.only}, summ)


# ======================================================================= bursts (pairs, burst sizes, horizon, low lambda)
def burst_section(cfg: dict, r7: dict, name: str, lam_miss: float, mult: float, *, burst_n: int, width: float, warmup: float, after: float,
                  seeds: Sequence[int], arms: Optional[dict] = None, cap: Optional[int] = None, eval_len: float = 2500.0) -> dict:
    sec = probe_section(cfg, "burst", False)
    c = r7["classify"]
    upd = {"policy": r7["policy"], "lambda": None, "lambda_miss": float(lam_miss), "lam_mult": float(mult), "burst_n": int(burst_n),
           "burst_width_s": float(width), "warmup_s": float(warmup), "after_s": float(after), "cap": cap, "arms": arms, "seeds": [int(s) for s in seeds],
           "recovered_hit_above": float(c["recovered_hit_above"]), "recovered_backlog_below": float(c["recovered_backlog_below"]),
           "hit_eval_from_s": float(after) - eval_len, "trap_hit_below": float(c["indeterminate_hit_below"]), "trap_min_s": eval_len,
           "workload": wl_over(r7, name)}
    return deep_update(sec, upd)


def verdict_counts(cl: pd.DataFrame, min_frac: float) -> Dict[str, Any]:
    """Counts of the paired-arm classification at ONE (workload, lambda): out of the seeds, BURST trapped / recovered / indeterminate, NOBURST good (RECOVERED) /
    trapped, CAPPED recovered / trapped, and PASS (each of the first three >= ceil(min_frac * n))."""
    def cnt(arm: str, col: str) -> int:
        return int(cl[cl["arm"] == arm][col].sum())

    n = int(cl[cl["arm"] == "burst"]["seed"].nunique())
    need = need_count(n, min_frac)
    out = {"n_seeds": n, "need": need, "burst_trapped": cnt("burst", "trapped"), "burst_recovered": cnt("burst", "recovered"),
           "burst_indeterminate": cnt("burst", "indeterminate"), "noburst_good": cnt("no_burst", "recovered"), "noburst_trapped": cnt("no_burst", "trapped"),
           "cap_recovered": cnt("burst_cap", "recovered") if (cl["arm"] == "burst_cap").any() else None,
           "cap_trapped": cnt("burst_cap", "trapped") if (cl["arm"] == "burst_cap").any() else None}
    out["PASS"] = bool(out["burst_trapped"] >= need and out["noburst_good"] >= need and out["cap_recovered"] is not None and out["cap_recovered"] >= need)
    return out


def stage_pairs(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    pr = r7["pairs"]
    c = r7["classify"]
    lm = stage_summary(args.out_root, "lambda_miss")["workloads"]
    cv = stage_summary(args.out_root, "curves")["workloads"]
    ed = stage_summary(args.out_root, "edge")["workloads"]
    ctx = start("pairs", cfg, args, repo_dir)
    ev = [float(x) for x in c["eval_window_rel_to_burst_s"]]
    runs_all: List[pd.DataFrame] = []
    wins_all: List[pd.DataFrame] = []
    cls_all: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workloads": {}, "dirs": {s: str(stage_dir(args.out_root, s)) for s in ("lambda_miss", "curves", "edge")}}
    for name in workload_names(r7, args.only):
        lam_miss, tok = float(lm[name]["lambda_miss_turns"]), float(lm[name]["token_rate"])
        cap = int(cv[name]["cap_n"])
        pts = [float(x) for x in ed[name]["points"]]
        w = {"label": r7["workloads"][name]["label"], "lambda_miss_turns": lam_miss, "token_rate_miss": tok, "cap_n": cap, "hi": ed[name]["hi"], "window_empty": not pts,
             "points": {}}
        if not pts:
            print(f"[pairs] {name}: EMPTY window (hi={ed[name]['hi']:g}); no paired test", flush=True)
        for mult in pts:
            sec = burst_section(cfg, r7, name, lam_miss, mult, burst_n=pr["burst_n"], width=pr["burst_width_s"], warmup=pr["warmup_s"], after=pr["after_s"],
                                seeds=pr["seeds"], cap=cap)
            res = run_burst(cfg, sec, workers=args.workers)
            runs, wins, _ = res.frames
            key = f"{name}|{mult:g}"
            cl = classify_burst_frames(runs, wins, lam_miss, tok, c, ev, {"workload": name, "mult": mult, "call": key})
            v = verdict_counts(cl, float(c["pass_min_frac"]))
            w["points"][f"{mult:g}"] = {"lam": mult * lam_miss, **v}
            r2 = runs.copy()
            r2.insert(0, "call", key)
            runs_all.append(r2)
            w2 = wins.copy()
            w2.insert(0, "call", key)
            wins_all.append(w2)
            cls_all.append(cl)
            print(f"[pairs] {name} x{mult:g}: trapped {v['burst_trapped']}/{v['n_seeds']} noburst good {v['noburst_good']} cap recovered {v['cap_recovered']} -> "
                  f"{'PASS' if v['PASS'] else 'FAIL'}", flush=True)
        summ["workloads"][name] = w
    concat(runs_all).to_csv(ctx.out / "runs.csv", index=False)
    concat(wins_all).to_csv(ctx.out / "windows.csv", index=False)
    concat(cls_all).to_csv(ctx.out / "classified_runs.csv", index=False)
    return end(ctx, args, pr["seeds"], {"stage": "pairs", "only": args.only}, summ)


def record_lambda(cfg: dict, args: argparse.Namespace) -> Tuple[str, float, float]:
    r7 = r7_block(cfg)
    name = r7["record_workload"]
    lm = stage_summary(args.out_root, "lambda_miss")["workloads"][name]
    return name, float(lm["lambda_miss_turns"]), float(lm["token_rate"])


def stage_burst_sizes(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    bs = r7["burst_sizes"]
    c = r7["classify"]
    name, lam_miss, tok = record_lambda(cfg, args)
    ctx = start("burst_sizes", cfg, args, repo_dir)
    ev = [float(x) for x in c["eval_window_rel_to_burst_s"]]
    arms = {"no_burst": {"burst_n": 0, "cap": None}, **{f"burst_{int(b)}": {"burst_n": int(b), "cap": None} for b in bs["sizes"]}}
    cls_all: List[pd.DataFrame] = []
    wins_all: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workload": name, "lambda_miss_turns": lam_miss, "token_rate_miss": tok, "by_mult": {},
                            "lambda_miss_dir": str(stage_dir(args.out_root, "lambda_miss"))}
    for mult in bs["multiples"]:
        sec = burst_section(cfg, r7, name, lam_miss, float(mult), burst_n=max(bs["sizes"]), width=bs["burst_width_s"], warmup=bs["warmup_s"], after=bs["after_s"],
                            seeds=bs["seeds"], arms=arms)
        res = run_burst(cfg, sec, workers=args.workers)
        runs, wins, _ = res.frames
        key = f"{name}|{float(mult):g}"
        cl = classify_burst_frames(runs, wins, lam_miss, tok, c, ev, {"workload": name, "mult": float(mult), "call": key})
        cls_all.append(cl)
        w2 = wins.copy()
        w2.insert(0, "call", key)
        wins_all.append(w2)
        n = int(cl[cl["arm"] == "no_burst"]["seed"].nunique())
        need = need_count(n, float(c["pass_min_frac"]))
        per = {}
        for b in bs["sizes"]:
            g = cl[cl["arm"] == f"burst_{int(b)}"]
            per[str(int(b))] = {"trapped": int(g["trapped"].sum()), "recovered": int(g["recovered"].sum()), "indeterminate": int(g["indeterminate"].sum()), "n": int(len(g))}
        sizes = [int(b) for b in bs["sizes"]]
        ok = [per[str(b)]["trapped"] >= need for b in sizes]
        smallest = next((b for b, o in zip(sizes, ok) if o), None)
        from_here = next((sizes[i] for i in range(len(sizes)) if all(ok[i:])), None)
        g0 = cl[cl["arm"] == "no_burst"]
        summ["by_mult"][f"{float(mult):g}"] = {"lam": float(mult) * lam_miss, "need": need, "n_seeds": n, "per_size": per,
                                               "noburst_good": int(g0["recovered"].sum()), "noburst_trapped": int(g0["trapped"].sum()),
                                               "smallest_size_trapping_in_need": smallest, "smallest_size_from_which_all_larger_trap": from_here}
        print(f"[burst_sizes] x{mult:g}: " + ", ".join(f"{b}:{per[str(b)]['trapped']}/{n}" for b in sizes) + f" -> smallest {smallest}", flush=True)
    concat(cls_all).to_csv(ctx.out / "classified_runs.csv", index=False)
    concat(wins_all).to_csv(ctx.out / "windows.csv", index=False)
    return end(ctx, args, bs["seeds"], {"stage": "burst_sizes", "only": args.only}, summ)


def stage_horizon(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    hz = r7["horizon"]
    c = r7["classify"]
    name, lam_miss, tok = record_lambda(cfg, args)
    ctx = start("horizon", cfg, args, repo_dir)
    arms = {"no_burst": {"burst_n": 0, "cap": None}, "burst": {"burst_n": int(hz["burst_n"]), "cap": None}}
    cls_all: List[pd.DataFrame] = []
    ev_all: List[pd.DataFrame] = []
    wins_all: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workload": name, "lambda_miss_turns": lam_miss, "token_rate_miss": tok, "by_mult": {},
                            "lambda_miss_dir": str(stage_dir(args.out_root, "lambda_miss"))}
    for mult in hz["multiples"]:
        sec = burst_section(cfg, r7, name, lam_miss, float(mult), burst_n=hz["burst_n"], width=hz["burst_width_s"], warmup=hz["warmup_s"], after=hz["after_s"],
                            seeds=hz["seeds"], arms=arms)
        res = run_burst(cfg, sec, workers=args.workers)
        runs, wins, _ = res.frames
        key = f"{name}|{float(mult):g}"
        per_win = {}
        for k, evw in enumerate(hz["eval_windows_rel_to_burst_s"]):
            cl = classify_burst_frames(runs, wins, lam_miss, tok, c, [float(x) for x in evw], {"workload": name, "mult": float(mult), "call": key})
            cl.insert(0, "eval_window", f"[{evw[0]:g}, {evw[1]:g}]")
            cls_all.append(cl)
            per_win[f"[{evw[0]:g}, {evw[1]:g}]"] = cl
        tb = float(hz["warmup_s"])
        by_run = {rid: g for rid, g in wins.groupby("run_id")}
        rows = []
        for _, r in runs.iterrows():
            rows.append({"workload": name, "mult": float(mult), "arm": r["arm"], "seed": int(r["seed"]), "run_id": int(r["run_id"]),
                         **run_events(by_run[r["run_id"]], tb, hz)})
        evd = pd.DataFrame(rows)
        ev_all.append(evd)
        w2 = wins.copy()
        w2.insert(0, "call", key)
        wins_all.append(w2)
        info: Dict[str, Any] = {"lam": float(mult) * lam_miss}
        for arm in ("no_burst", "burst"):
            e = evd[evd["arm"] == arm]
            info[arm] = {"n": int(len(e)), "n_collapsed": int(e["collapse_s"].notna().sum()), "collapse_s": [None if not np.isfinite(x) else float(x) for x in e["collapse_s"]],
                         "n_trap_onset": int(e["trap_onset_s"].notna().sum()), "n_released": int(e["release_s"].notna().sum()),
                         "release_s": [None if not np.isfinite(x) else float(x) for x in e["release_s"]]}
            for wk, cl in per_win.items():
                g = cl[cl["arm"] == arm]
                info[arm][f"trapped_in_{wk}"] = int(g["trapped"].sum())
                info[arm][f"recovered_in_{wk}"] = int(g["recovered"].sum())
        summ["by_mult"][f"{float(mult):g}"] = info
        print(f"[horizon] x{mult:g}: NOBURST collapsed {info['no_burst']['n_collapsed']}/{info['no_burst']['n']}, BURST onset {info['burst']['n_trap_onset']} "
              f"released {info['burst']['n_released']}", flush=True)
    concat(cls_all).to_csv(ctx.out / "classified_runs.csv", index=False)
    concat(ev_all).to_csv(ctx.out / "events.csv", index=False)
    concat(wins_all).to_csv(ctx.out / "windows.csv", index=False)
    return end(ctx, args, hz["seeds"], {"stage": "horizon", "only": args.only}, summ)


def stage_lowlam(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    lw = r7["lowlam"]
    c = r7["classify"]
    name, lam_miss, tok = record_lambda(cfg, args)
    ctx = start("lowlam", cfg, args, repo_dir)
    ev = [float(x) for x in c["eval_window_rel_to_burst_s"]]
    arms = {"burst": {"burst_n": int(lw["burst_n"]), "cap": None}}
    mult = float(lw["multiple"])
    sec = burst_section(cfg, r7, name, lam_miss, mult, burst_n=lw["burst_n"], width=lw["burst_width_s"], warmup=lw["warmup_s"], after=lw["after_s"],
                        seeds=lw["seeds"], arms=arms)
    res = run_burst(cfg, sec, workers=args.workers)
    runs, wins, _ = res.frames
    cl = classify_burst_frames(runs, wins, lam_miss, tok, c, ev, {"workload": name, "mult": mult, "call": f"{name}|{mult:g}"})
    n = len(cl)
    thr = float(cl["slope_threshold"].iloc[0])
    summ = {"workload": name, "mult": mult, "lam": mult * lam_miss, "lambda_miss_turns": lam_miss, "token_rate_miss": tok, "n": n, "slope_threshold": thr,
            "slope_quantiles": quantiles(cl["slope"]), "slope_over_threshold_quantiles": quantiles(cl["slope"] / thr),
            "token_ratio_quantiles": quantiles(cl["token_ratio"]), "hit_quantiles": quantiles(cl["hit"]),
            "classes": {k: int((cl["label"] == k).sum()) for k in ("TRAPPED", "RECOVERED", "INDETERMINATE", "OTHER", "BOTH")},
            "n_slope_above_threshold": int(cl["slope_ok"].sum()), "n_rate_ok": int(cl["rate_ok"].sum()),
            "n_hit_below_0.05": int((cl["hit"] < 0.05).sum()), "lambda_miss_dir": str(stage_dir(args.out_root, "lambda_miss"))}
    cl.to_csv(ctx.out / "classified_runs.csv", index=False)
    runs.to_csv(ctx.out / "runs.csv", index=False)
    wins.to_csv(ctx.out / "windows.csv", index=False)
    print(f"[lowlam] x{mult:g}: classes {summ['classes']}, slope/threshold median {summ['slope_over_threshold_quantiles']['q050']:.2f}", flush=True)
    return end(ctx, args, lw["seeds"], {"stage": "lowlam", "only": args.only}, summ)


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round 7 simulator robustness: one stage per call (see the module docstring)")
    ap.add_argument("stage", choices=list(STAGES))
    ap.add_argument("--spec", "--config", dest="config", required=True)
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"processes (1..{MAX_WORKERS}; also capped by the spec's parallel.max_workers)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--only", nargs="*", default=None, help="restrict the per-workload stages to these workload names (smoke tests)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override (recorded in meta.json)")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true", help="unused (kept for the begin()/finish() provenance helpers)")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    if not (1 <= args.workers <= MAX_WORKERS):
        raise SystemExit(f"--workers must be in 1..{MAX_WORKERS}, got {args.workers}")
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    cfg = load_probe_config(args.config, repo_dir, args.set)
    {"lambda_miss": stage_lambda_miss, "curves": stage_curves, "edge": stage_edge, "pairs": stage_pairs, "burst_sizes": stage_burst_sizes,
     "horizon": stage_horizon, "lowlam": stage_lowlam}[args.stage](cfg, args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
