"""Round-4 experiments of the prefix-cache metastability pilot (thrashing-curve / fluid-picture tests).

Commands (config ``configs/prefix_meta_r4.yaml``, registered in ``configs/prefix_meta_r4_prereg.yaml``)::

    curve   E-curve : closed-population mu(n) for FCFS-LRU / LPM-LRU / FCFS-RANDOM / FCFS-MRU_IDLE (+ FCFS-LRU at k = 0.5, 2)
    burst   E-burst : open system at 2 lambda_miss from empty, bursts of b sessions in 60 s, recovery after 60k s
    burst_info      : INFORMATIONAL burst cells (amendment 1): b = 0 controls and lambda in {1.5, 2, 2.5} lambda_miss on a finer grid
    cap     E-cap   : cold 300 at 2 lambda_miss, static session cap x eviction rule
    report          : reads the three result dirs and writes results/prefix_meta_r4/<ts>/ (figures, tables, prediction_eval.csv)

Every command creates a NEW ``results/<name>/<YYYYmmdd-HHMMSS>/`` directory holding ``config.yaml``, ``base_config.yaml``,
``config_effective.yaml``, ``preregistration.yaml``, ``meta.json`` (git commit + dirty flag captured at the START, seeds,
versions, hostname, hardware, start / end) and CSVs. Nothing existing is overwritten. At most 3 worker processes.

Closed-population mode (the thrashing curve). ``ArrivalPlan(kind="closed")``: ``n`` sessions at t = 0; the engine injects a
fresh turn-1 session (the next one of a pre-generated pool) at the instant a session finishes its last turn, so exactly ``n``
sessions are in the system at all times (tests: tests/test_r4.py). ``mu(n)`` = sessions completed in the complete windows with
t_start >= warmup divided by their total length.
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
from .mech_runner import (_meta, add_recovery, base_calibration, begin, exp_cfg_deep, finish, load_mech_config,
                          scaled_engine_overrides)
from .runner import Runner, apply_overrides, collect_frames, save_frames, timing_summary
from .sim import RunSpec
from .workload import ArrivalPlan


# ======================================================================= closed-population curve
def round_half_up(x: float) -> int:
    """floor(x + 1/2): the registered rounding of k-scaled populations (Python's round() is banker's rounding)."""
    return int(math.floor(x + 0.5))


def scaled_population(n: int, k: float) -> int:
    """n_k = floor(k n + 0.5), at least 1."""
    return max(1, round_half_up(k * n))


def point_metrics(windows: Sequence[Dict[str, Any]], warmup_s: float, horizon_s: float, window_s: float
                  ) -> Dict[str, float]:
    """Steady-state metrics of one closed-population run over the complete windows with t_start >= ``warmup_s``.

    mu = completed sessions / s; hit_rate = hits / admissions; gpu_busy = mean busy fraction; reserved / idle / resident KV =
    mean over windows of the reserved (running requests' full end-of-turn contexts) / idle (tool-call + waiting sessions) /
    total KV tokens; evictions_per_s = evicted whole sessions / s. mu_first_half / mu_second_half are the same completion
    rate over the first / second half of the measurement windows (stationarity diagnostic only)."""
    rows = sorted((w for w in windows if w["t_start"] >= warmup_s - 1e-9), key=lambda w: w["t_start"])
    dur = len(rows) * window_s
    if not rows or abs(dur - (horizon_s - warmup_s)) > 1e-6:
        raise ValueError(f"measurement window incomplete: {len(rows)} windows of {window_s} s for "
                         f"[{warmup_s}, {horizon_s})")

    def count(key: str, rr: Sequence[Dict[str, Any]]) -> int:
        return int(sum(round(w[key] * window_s) for w in rr))

    half = len(rows) // 2
    sessions = count("sessions_per_s", rows)
    adm = int(sum(w["admitted_turns"] for w in rows))
    hits = int(sum(w["hits"] for w in rows))
    res = float(np.mean([w["reserved_mean"] for w in rows]))
    idl = float(np.mean([w["idle_mean"] for w in rows]))
    return {
        "mu": sessions / dur, "n_sessions": sessions, "turns_per_s": count("turns_per_s", rows) / dur,
        "hit_rate": hits / adm if adm else float("nan"),
        "gpu_busy": float(np.mean([w["busy_frac"] for w in rows])),
        "reserved_tokens": res, "idle_tokens": idl, "resident_kv_tokens": res + idl,
        "evictions_per_s": int(sum(w["evictions"] for w in rows)) / dur,
        "mu_first_half": count("sessions_per_s", rows[:half]) / (half * window_s) if half else float("nan"),
        "mu_second_half": count("sessions_per_s", rows[half:]) / ((len(rows) - half) * window_s) if half else float("nan"),
        "n_windows": len(rows),
    }


def closed_spec(policy: str, n_nominal: int, k: float, seed: int, cv: Dict[str, Any], engine_cfg: Dict[str, Any]
                ) -> RunSpec:
    """One closed-population run: ``n_k = floor(k n + 0.5)`` sessions, engine scaled by ``k`` (round-3 scaling)."""
    n = scaled_population(n_nominal, k) if k != 1.0 else int(n_nominal)
    pool = max(100, int(round(cv["pool_sessions_per_k"] * k)))
    eo = scaled_engine_overrides(engine_cfg, k) if k != 1.0 else {}
    H = float(cv["horizon_s"])
    return RunSpec(exp="r4_curve", policy=policy, seed=int(seed), horizon_s=H, variant=f"k={k}|n={n}",
                   plan=ArrivalPlan(kind="closed", horizon_s=H, closed_n=n, pool=pool), engine_overrides=eo,
                   meta={"lam": float("nan"), "lam_mult": float("nan"), "population": n, "n_nominal": int(n_nominal),
                         "k": float(k)})


def curve_specs(cfg: dict, cv: dict) -> List[RunSpec]:
    specs: List[RunSpec] = []
    for pol in cv["policies"]:
        for n in cv["n_grid"]:
            for sd in cv["seeds"]:
                specs.append(closed_spec(pol, n, 1.0, sd, cv, cfg["engine"]))
    ks = cv.get("k_scaled")
    if ks:
        if ks.get("n_rounding", "half_up") != "half_up":
            raise ValueError("only half_up rounding is registered")
        for k in ks["sizes"]:
            for n in cv["n_grid"]:
                for sd in cv["seeds"]:
                    specs.append(closed_spec(ks["policy"], n, float(k), sd, cv, cfg["engine"]))
    return specs


def curve_table(cr: pd.DataFrame) -> pd.DataFrame:
    """Per (policy, k, n_nominal): seed-mean, sample sd (ddof = 1) and standard error (sd / sqrt(n_seeds)) of mu and the mean
    of the other metrics, plus the per-seed mu as JSON (ordered by seed). The unit of replication is the seed. mu near the cliff
    is a time average over a process that switches between regimes, not the mean of a stationary law."""
    rows = []
    for (pol, k, nn), g in cr.groupby(["policy", "k", "n_nominal"], sort=True):
        g = g.sort_values("seed")
        row = {"policy": pol, "k": float(k), "n_nominal": int(nn), "n": int(g["n"].iloc[0]), "n_seeds": int(len(g)),
               "mu_mean": float(g["mu"].mean()), "mu_sd": float(g["mu"].std(ddof=1)) if len(g) > 1 else float("nan"),
               "mu_se": float(g["mu"].std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else float("nan"),
               "mu_per_seed": json.dumps([float(x) for x in g["mu"]]), "seeds": json.dumps([int(s) for s in g["seed"]])}
        for c in ("hit_rate", "gpu_busy", "resident_kv_tokens", "reserved_tokens", "idle_tokens", "evictions_per_s",
                  "turns_per_s", "mu_first_half", "mu_second_half"):
            row[c + "_mean"] = float(g[c].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def cmd_curve(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    cv = exp_cfg_deep(cfg, "curve", args.quick)
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("r4_curve", "prefix_meta_r4_curve", cfg, {**cfg, "curve_effective": cv, "calibration": cal}, args, repo_dir)
    specs = curve_specs(cfg, cv)
    W = float(cfg["metrics"]["window_s"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    cr = pd.DataFrame([{"policy": rs.policy, "k": rs.meta["k"], "n_nominal": rs.meta["n_nominal"],
                        "n": rs.meta["population"], "seed": rs.seed,
                        **point_metrics(res["windows"], cv["warmup_s"], cv["horizon_s"], W),
                        "wall_s": res["summary"]["wall_s"]} for rs, res in zip(specs, results)])
    runs, wins, _ = collect_frames(results, specs)
    runs.to_csv(ctx.out / "runs.csv", index=False)
    wins.to_csv(ctx.out / "windows.csv", index=False)
    cr.to_csv(ctx.out / "curve_runs.csv", index=False)
    ct = curve_table(cr)
    ct.to_csv(ctx.out / "curve_table.csv", index=False)
    finish(ctx, cr["seed"], {"calibration": cal, "n_runs": int(len(cr)), "timing": timing_summary(runs),
                             "lambda_miss": cal["lambda_miss"], "n_grid": list(cv["n_grid"]),
                             "warmup_s": cv["warmup_s"], "horizon_s": cv["horizon_s"],
                             "common_random_numbers": "same seed -> same workload stream for every policy and every n"})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(ct[["policy", "k", "n_nominal", "n", "n_seeds", "mu_mean", "mu_sd", "hit_rate_mean", "gpu_busy_mean",
                  "resident_kv_tokens_mean", "evictions_per_s_mean"]].to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= burst
def burst_specs(cfg: dict, bd: dict, lam_miss: float) -> List[RunSpec]:
    tb = float(bd["warmup_s"])
    H = tb + float(bd["after_s"])
    lam = float(bd["lam_mult"]) * lam_miss
    pols = [bd["policies"]["primary"], bd["policies"]["informational"]]
    specs: List[RunSpec] = []
    for pol in pols:
        for b in bd["sizes"]:
            for sd in bd["seeds"]:
                specs.append(RunSpec(
                    exp="r4_burst", policy=pol, seed=int(sd), horizon_s=H, variant=f"burst={b}",
                    plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=int(b), burst_t0=tb,
                                     burst_width_s=float(bd["burst_width_s"])),
                    meta=_meta(lam, float(bd["lam_mult"]), burst_n=int(b), t_burst=tb)))
    return specs


def burst_info_specs(cfg: dict, bi: dict, lam_miss: float) -> List[RunSpec]:
    """INFORMATIONAL cells (amendment 1): FCFS-LRU burst sweeps (incl. the no-burst control b = 0) at several lambda, and the
    FCFS-RANDOM no-burst control. Same seeds as the registered E-burst (CRN-coupled with it)."""
    tb = float(bi["warmup_s"])
    H = tb + float(bi["after_s"])
    ld, cr = bi["lambda_dependence"], bi["control_random"]
    cells = [(ld["policy"], float(m), int(b)) for m in ld["lam_mults"] for b in ld["sizes"]]
    cells += [(cr["policy"], float(cr["lam_mult"]), int(b)) for b in cr["sizes"]]
    specs: List[RunSpec] = []
    for pol, mult, b in cells:
        for sd in bi["seeds"]:
            specs.append(RunSpec(
                exp="r4_burst_info", policy=pol, seed=int(sd), horizon_s=H, variant=f"lam={mult}|burst={b}",
                plan=ArrivalPlan(kind="constant", horizon_s=H, rate=mult * lam_miss, burst_n=b, burst_t0=tb,
                                 burst_width_s=float(bi["burst_width_s"])),
                meta=_meta(mult * lam_miss, mult, burst_n=b, t_burst=tb)))
    return specs


def cmd_burst_info(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    bi = exp_cfg_deep(cfg, "burst_info", args.quick)
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("r4_burst_info", "prefix_meta_r4_burst_info", cfg, {**cfg, "burst_info_effective": bi, "calibration": cal},
                args, repo_dir)
    specs = burst_info_specs(cfg, bi, cal["lambda_miss"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, bi["recovered_hit_above"], bi["recovered_backlog_below"])
    save_frames(ctx.out, runs, wins, qts)
    bc = runs.groupby(["policy", "lam_mult", "burst_n"], sort=True).agg(
        n_runs=("seed", "size"), n_recovered=("recovered", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
        tail_backlog_mean=("tail_backlog_mean", "mean")).reset_index()
    bc["n_not_recovered"] = bc["n_runs"] - bc["n_recovered"]
    bc.to_csv(ctx.out / "burst_info_counts.csv", index=False)
    finish(ctx, runs["seed"], {"calibration": cal, "n_runs": int(len(runs)), "timing": timing_summary(runs),
                               "lambda_miss": cal["lambda_miss"], "informational": True,
                               "common_random_numbers": "same seed -> same random streams; at equal lambda the workload equals that of "
                                                        "the registered E-burst run of the same seed, across lambda the "
                                                        "coupling is partial (arrival counts differ). Cells are not independent"})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(bc.to_string())
    print("result dir:", ctx.out)
    return ctx.out


def burst_counts(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (policy, burst size): runs, not-recovered count, tail hit rate / backlog means. Recovery = round-3 reading."""
    g = runs.groupby(["policy", "burst_n"], sort=True)
    out = g.agg(n_runs=("seed", "size"), n_recovered=("recovered", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
                tail_backlog_mean=("tail_backlog_mean", "mean"), tail_sessions_per_s=("tail_sessions_per_s", "mean")
                ).reset_index()
    out["n_not_recovered"] = out["n_runs"] - out["n_recovered"]
    return out


def cmd_burst(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    bd = exp_cfg_deep(cfg, "burst", args.quick)
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("r4_burst", "prefix_meta_r4_burst", cfg, {**cfg, "burst_effective": bd, "calibration": cal}, args, repo_dir)
    specs = burst_specs(cfg, bd, cal["lambda_miss"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, bd["recovered_hit_above"], bd["recovered_backlog_below"])
    save_frames(ctx.out, runs, wins, qts)
    bc = burst_counts(runs)
    bc.to_csv(ctx.out / "burst_counts.csv", index=False)
    finish(ctx, runs["seed"], {"calibration": cal, "n_runs": int(len(runs)), "timing": timing_summary(runs),
                               "lambda_miss": cal["lambda_miss"], "lam": bd["lam_mult"] * cal["lambda_miss"],
                               "t_burst": bd["warmup_s"], "horizon_s": bd["warmup_s"] + bd["after_s"],
                               "common_random_numbers": "same seed -> same workload for both policies and all burst sizes"})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(bc.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= cap
def cap_specs(cfg: dict, cd: dict, lam_miss: float) -> List[RunSpec]:
    H = float(cd["horizon_s"])
    lam = float(cd["lam_mult"]) * lam_miss
    specs: List[RunSpec] = []
    for ev in cd["evictions"]:
        pol = cd["eviction_policy"][ev]
        for cap in cd["caps"]:
            for sd in cd["seeds"]:
                specs.append(RunSpec(
                    exp="r4_cap", policy=pol, seed=int(sd), horizon_s=H, variant=f"cap={cap}",
                    session_cap_override=int(cap),
                    plan=ArrivalPlan(kind="constant", horizon_s=H, rate=lam, initial_cold=int(cd["cold_sessions"])),
                    meta=_meta(lam, float(cd["lam_mult"]), cap=int(cap), cold_sessions=int(cd["cold_sessions"]))))
    return specs


def cap_cells(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (eviction, cap): number of seeds recovered (round-3 reading: last 5000 s hit > 0.8 and backlog < 20)."""
    g = runs.groupby(["eviction", "cap"], sort=True)
    out = g.agg(n_runs=("seed", "size"), n_recovered=("recovered", "sum"), tail_hit_mean=("tail_hit_rate", "mean"),
                tail_backlog_mean=("tail_backlog_mean", "mean"), tail_gate_mean=("tail_gate_mean", "mean"),
                tail_sessions_per_s=("tail_sessions_per_s", "mean")).reset_index()
    return out


def cmd_cap(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    cd = exp_cfg_deep(cfg, "cap", args.quick)
    cal = base_calibration(cfg, args, repo_dir)
    ctx = begin("r4_cap", "prefix_meta_r4_cap", cfg, {**cfg, "cap_effective": cd, "calibration": cal}, args, repo_dir)
    specs = cap_specs(cfg, cd, cal["lambda_miss"])
    with Runner(cfg, args.workers) as R:
        results = R.run(specs)
    runs, wins, qts = collect_frames(results, specs)
    runs = add_recovery(runs, cd["recovered_hit_above"], cd["recovered_backlog_below"])
    save_frames(ctx.out, runs, wins, qts)
    cc = cap_cells(runs)
    cc.to_csv(ctx.out / "cap_cells.csv", index=False)
    finish(ctx, runs["seed"], {"calibration": cal, "n_runs": int(len(runs)), "timing": timing_summary(runs),
                               "lambda_miss": cal["lambda_miss"], "lam": cd["lam_mult"] * cal["lambda_miss"],
                               "common_random_numbers": "same seed -> same workload for every cap and eviction rule"})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(cc.to_string())
    print("result dir:", ctx.out)
    return ctx.out


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Prefix-cache metastability pilot, round 4 (thrashing curve; simulation)")
    ap.add_argument("cmd", choices=["curve", "burst", "burst_info", "cap", "report"])
    ap.add_argument("--config", default="configs/prefix_meta_r4.yaml")
    ap.add_argument("--quick", action="store_true", help="smoke-test sizes (short horizons, one seed)")
    ap.add_argument("--workers", type=int, default=3, help="processes (hard-capped by config parallel.max_workers = 3)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--calib", default=None, help="round-1 E0 result dir or e0_summary.json (base workload)")
    ap.add_argument("--curve-dir", default=None, help="report: E-curve result dir")
    ap.add_argument("--burst-dir", default=None, help="report: E-burst result dir")
    ap.add_argument("--burst-info-dir", default=None, help="report: burst_info (informational) result dir")
    ap.add_argument("--cap-dir", default=None, help="report: E-cap result dir")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override")
    ap.add_argument("--tag", default=None, help="suffix for the result dir name")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(args.config).resolve().parent.parent
    cfg = apply_overrides(load_mech_config(args.config, repo_dir), args.set)
    if args.cmd == "report":
        from .report_r4 import cmd_report
        cmd_report(cfg, args, repo_dir)
    else:
        {"curve": cmd_curve, "burst": cmd_burst, "burst_info": cmd_burst_info, "cap": cmd_cap}[args.cmd](cfg, args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
