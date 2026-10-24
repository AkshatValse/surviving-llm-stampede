"""Round-6 validation: simulator vs the REAL Stage C closed-population curve (SGLang 0.5.22, Qwen2.5-7B, A100 80GB, KV cap 300k).

Config: ``configs/r6_validate_stagec.yaml``. CLI: ``experiments/prefix_meta_r6_validate_stagec.py``. Nothing here re-implements simulation:
the runs are ``probe.run_curve`` calls (closed population, synchronized start at t = 0, measured window [warmup_s, horizon_s)) with the
calibrated cost constants of ``calibration/round6_server_log_fit/calibration.yaml`` merged over the base engine and, per arm, engine overrides
(``batching`` mixed | separate_prefill_priority, plus the sensitivities declared in the config).

This module adds only (a) loading of the real Stage C numbers from the pulled analysis CSVs, (b) pure comparison functions
(relative error, argmax with runner-up flag, hit crossing by linear interpolation, collapse ratio) and (c) tables.

Definitions (declared in the config before any run)
---------------------------------------------------
* ``mu_sessions`` : sessions completed in the window / window length (real: ``analysis.throughput.completion_rates``; sim: ``point_metrics``).
* ``mu_turns``    : completed turns / window length / E[T], E[T] = E[min(Geom(1/15), 60)] (the lower-variance estimator of the real analysis).
* ``hit``         : real = fraction of ok turns completing in the window with cached/prompt > 0.5, first turns included; sim = hits / admitted
                    turns in the window (a hit is a resident session KV, i.e. cached/prompt >= 0.79, so the two agree up to the time stamp).
* relative error  : (sim - real) / real, of the seed-mean sim value against the single real value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import probe
from .engine import EngineParams
from .mech_runner import begin, finish
from .runner import git_info
from .sim import deep_update, load_config
from .workload import WorkloadParams

MIXED = "mixed"
SEP = "separate_prefill_priority"
MAX_WORKERS = 8
KEY = ["arm", "batching", "policy", "n"]


# ======================================================================= configuration
def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_dotted(d: dict, dotted: str) -> Any:
    cur: Any = d
    for k in dotted.split("."):
        cur = cur[k]
    return cur


def load_validation_config(spec_path: str, repo_dir: Path, sets: Optional[Sequence[str]] = None) -> dict:
    """Probe-style merged config of the validation spec with the calibration's ``engine`` block merged over the base engine.
    Validates engine / workload parameters and that the 100 s metric windows tile [warmup_s, horizon_s)."""
    cfg = probe.load_probe_config(spec_path, repo_dir, sets)
    cal_path = repo_dir / cfg["calibration_file"]
    cfg["engine"] = deep_update(cfg["engine"], load_config(str(cal_path))["engine"])
    cfg["_calibration_sha256"] = sha256_file(cal_path)
    EngineParams.from_dict(cfg["engine"])
    WorkloadParams.from_dict(cfg["workload"])
    pr = cfg["validate"]["protocol"]
    W = float(cfg["metrics"]["window_s"])
    for name in ("warmup_s", "horizon_s"):
        if abs(pr[name] / W - round(pr[name] / W)) > 1e-9:
            raise ValueError(f"protocol.{name}={pr[name]} is not a multiple of metrics.window_s={W}")
    if float(cfg["engine"]["kv_memory_tokens"]) != float(pr["kv_cap_tokens"]):
        raise ValueError("engine.kv_memory_tokens differs from protocol.kv_cap_tokens")
    for arm_name, arm in cfg["validate"]["arms"].items():
        for b in arm["batching_modes"]:
            EngineParams.from_dict(deep_update(cfg["engine"], arm_engine(cfg, arm, b)))
    return cfg


def arm_engine(cfg: dict, arm: dict, batching: str) -> Dict[str, Any]:
    """Engine overrides of one (arm, batching) cell: ``engine_from`` (dotted path into the config) < ``engine`` < ``batching``."""
    eo: Dict[str, Any] = {}
    if arm.get("engine_from"):
        eo.update(get_dotted(cfg, arm["engine_from"]))
    eo.update(arm.get("engine") or {})
    eo["batching"] = batching
    return eo


# ======================================================================= real Stage C data
def load_real(cfg: dict, repo_dir: Path) -> pd.DataFrame:
    """The real Stage C table: columns policy, n, real_mu, real_mu_turns, real_hit, real_cached_tokens (one row per cell)."""
    rc = cfg["validate"]["real"]
    parts = []
    for f in rc["files"]:
        d = pd.read_csv(repo_dir / f["path"])
        d["policy"] = d["label"].map(rc["label_to_policy"])
        if d["policy"].isna().any():
            raise ValueError(f"unmapped label in {f['path']}: {sorted(d['label'].unique())}")
        parts.append(d)
    r = pd.concat(parts, ignore_index=True)
    out = pd.DataFrame({"policy": r["policy"], "n": r["n"].astype(int), "real_mu": r["mu_sessions"], "real_mu_turns": r["mu_turns_based"],
                        "real_hit": r["hit_frac_turns"], "real_cached_tokens": r["cached_frac_tokens"]})
    if out.duplicated(["policy", "n"]).any():
        raise ValueError("duplicate (policy, n) in the real tables")
    return out.sort_values(["policy", "n"]).reset_index(drop=True)


# ======================================================================= pure comparison functions
def rel_err(sim: float, real: float) -> float:
    """(sim - real) / real; NaN if real is 0 or either is NaN."""
    if not (math.isfinite(sim) and math.isfinite(real)) or real == 0.0:
        return float("nan")
    return (sim - real) / real


def first_argmax(ns: Sequence[float], vals: Sequence[float]) -> Tuple[int, float]:
    """(n, value) of the first maximum over the grid sorted by n (ties: smallest n)."""
    order = np.argsort(np.asarray(ns, dtype=float), kind="stable")
    n = np.asarray(ns)[order]
    v = np.asarray(vals, dtype=float)[order]
    i = int(np.argmax(v))
    return int(n[i]), float(v[i])


def runner_up(ns: Sequence[float], vals: Sequence[float]) -> Tuple[int, float]:
    """(n, value) of the second-largest grid value (n of the argmax excluded)."""
    n_star, _ = first_argmax(ns, vals)
    cand = [(int(n), float(v)) for n, v in zip(ns, vals) if int(n) != n_star]
    return max(cand, key=lambda t: t[1])


def crossing(ns: Sequence[float], vals: Sequence[float], level: float = 0.5) -> float:
    """n at which ``vals`` (sorted by n) first falls from >= level to < level, by linear interpolation between the adjacent grid points.
    NaN if vals[0] < level (already below at the smallest n) or it never falls below."""
    order = np.argsort(np.asarray(ns, dtype=float), kind="stable")
    n = np.asarray(ns, dtype=float)[order]
    v = np.asarray(vals, dtype=float)[order]
    if v[0] < level:
        return float("nan")
    for i in range(len(n) - 1):
        if v[i] >= level > v[i + 1]:
            return float(n[i] + (n[i + 1] - n[i]) * (v[i] - level) / (v[i] - v[i + 1]))
    return float("nan")


def collapse_ratio(ns: Sequence[float], mu: Sequence[float], n_tail: int = 300) -> Dict[str, float]:
    """mu(n_tail) / mu*, mu* = max of mu over the grid (the Stage C analysis-plan definition), and mu(48)/mu* when 48 is on the grid."""
    d = {int(n): float(m) for n, m in zip(ns, mu)}
    _, star = first_argmax(list(d), list(d.values()))
    out = {"mu_star": star, f"mu_{n_tail}_over_star": d[n_tail] / star if n_tail in d else float("nan")}
    out["mu_48_over_star"] = d[48] / star if 48 in d else float("nan")
    return out


def summarize_curve(tab: pd.DataFrame, mu_col: str, hit_col: str, *, runner_up_frac: float, level: float) -> Dict[str, Any]:
    """Peak location (+ runner-up flag), hit crossing and collapse ratio of one FCFS curve (``tab`` has n, ``mu_col``, ``hit_col``)."""
    ns = tab["n"].tolist()
    mu = tab[mu_col].tolist()
    n_star, mu_star = first_argmax(ns, mu)
    n2, mu2 = runner_up(ns, mu)
    out = {"peak_n": n_star, "peak_mu": mu_star, "runner_up_n": n2, "runner_up_mu": mu2,
           "runner_up_gap": (mu_star - mu2) / mu_star if mu_star else float("nan"),
           "peak_ambiguous": bool(mu_star and (mu_star - mu2) / mu_star < runner_up_frac),
           "hit_crossing_n": crossing(ns, tab[hit_col].tolist(), level)}
    out.update(collapse_ratio(ns, mu))
    return out


# ======================================================================= running
def curve_section(cfg: dict, policy: str, ns: Sequence[int], seeds: Sequence[int], engine_overrides: Dict[str, Any]) -> dict:
    pr = cfg["validate"]["protocol"]
    return {"policies": [policy], "n_grid": [int(n) for n in ns], "seeds": [int(s) for s in seeds], "warmup_s": float(pr["warmup_s"]),
            "horizon_s": float(pr["horizon_s"]), "pool_sessions": int(pr["pool_sessions"]), "cache_enabled": True,
            "engine": dict(engine_overrides), "workload": {}}


def run_cells(cfg: dict, arm_name: str, batching: str, cells: Sequence[Tuple[str, Sequence[int]]], seeds: Sequence[int], workers: int
              ) -> pd.DataFrame:
    """Per-run rows (one per policy, n, seed) of one (arm, batching): ``probe.run_curve`` per policy plus the extra columns."""
    arm = cfg["validate"]["arms"][arm_name]
    eo = arm_engine(cfg, arm, batching)
    ET = WorkloadParams.from_dict(cfg["workload"]).effective_mean_turns()
    parts = []
    for policy, ns in cells:
        sec = curve_section(cfg, policy, ns, seeds, eo)
        res = probe.run_curve(cfg, sec, workers=workers)
        df = res.runs.copy()
        df.insert(0, "arm", arm_name)
        df.insert(1, "batching", batching)
        df["mu_turns"] = df["turns_per_s"] / ET
        parts.append(df)
    out = pd.concat(parts, ignore_index=True)
    out["n"] = out["n_nominal"].astype(int)
    return out


def run_all(cfg: dict, workers: int, quick: bool = False, log=print) -> Dict[str, pd.DataFrame]:
    """All registered arms x batching modes x cells x seeds (+ the supplementary runs unless ``quick``). Returns {'runs', 'supp_fine', 'supp_seeds'}."""
    v = cfg["validate"]
    seeds = [v["seeds"][0]] if quick else list(v["seeds"])
    cells = [(c["policy"], list(c["n"])) for c in v["cells"]]
    if quick:
        cells = [("fcfs_lru", [16, 48]), ("lpm128_lru", [48])]
    arms = {"primary": v["arms"]["primary"]} if quick else v["arms"]
    parts = []
    for arm_name, arm in arms.items():
        for b in arm["batching_modes"]:
            log(f"[run] arm={arm_name} batching={b} seeds={seeds}")
            parts.append(run_cells(cfg, arm_name, b, cells, seeds, workers))
    out = {"runs": pd.concat(parts, ignore_index=True)}
    if not quick:
        sf = v["supplementary"]["fine_grid"]
        parts = []
        for b in v["arms"]["primary"]["batching_modes"]:
            log(f"[supp fine grid] batching={b}")
            parts.append(run_cells(cfg, "primary", b, [(sf["policy"], sf["n"])], sf["seeds"], workers))
        out["supp_fine"] = pd.concat(parts, ignore_index=True)
        parts = []
        for b in v["arms"]["primary"]["batching_modes"]:
            log(f"[supp many seeds] batching={b}")
            parts.append(run_cells(cfg, "primary", b, cells, v["supplementary"]["many_seeds"]["seeds"], workers))
        out["supp_seeds"] = pd.concat(parts, ignore_index=True)
    return out


# ======================================================================= tables
def seed_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (arm, batching, policy, n): seed-mean, sd (ddof 1), se, min, max of mu; means of the other metrics; per-seed mu as JSON."""
    rows = []
    for key, g in runs.groupby(KEY, sort=False):
        g = g.sort_values("seed")
        k = len(g)
        sd = float(g["mu"].std(ddof=1)) if k > 1 else float("nan")
        row = dict(zip(KEY, key))
        row.update({"n_seeds": k, "mu_mean": float(g["mu"].mean()), "mu_sd": sd, "mu_se": sd / math.sqrt(k) if k > 1 else float("nan"),
                    "mu_min": float(g["mu"].min()), "mu_max": float(g["mu"].max()), "mu_turns_mean": float(g["mu_turns"].mean()),
                    "hit_mean": float(g["hit_rate"].mean()), "hit_sd": float(g["hit_rate"].std(ddof=1)) if k > 1 else float("nan"),
                    "mu_per_seed": json.dumps([float(x) for x in g["mu"]])})
        for c in ("gpu_busy", "reserved_tokens", "idle_tokens", "evictions_per_s", "prefill_tok_per_s", "preemptions_per_s",
                  "mu_first_half", "mu_second_half", "run_prefill_busy_frac", "run_decode_busy_frac", "run_prefill_iter_frac"):
            if c in g and g[c].notna().any():
                row[c + "_mean"] = float(g[c].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def attach_real(tab: pd.DataFrame, real: pd.DataFrame) -> pd.DataFrame:
    """Left-join the real values on (policy, n) and add the relative errors (mu, mu_turns) and the absolute hit difference."""
    t = tab.merge(real, on=["policy", "n"], how="left")
    t["rel_err_mu"] = [rel_err(a, b) for a, b in zip(t["mu_mean"], t["real_mu"])]
    t["rel_err_mu_turns"] = [rel_err(a, b) for a, b in zip(t["mu_turns_mean"], t["real_mu_turns"])]
    t["abs_err_hit"] = t["hit_mean"] - t["real_hit"]
    t["real_in_seed_range"] = (t["real_mu"] >= t["mu_min"] - 1e-12) & (t["real_mu"] <= t["mu_max"] + 1e-12)
    return t


def judged(t: pd.DataFrame, excluded: Iterable[Sequence[Any]]) -> pd.DataFrame:
    ex = {(str(p), int(n)) for p, n in excluded}
    keep = [(p, int(n)) not in ex for p, n in zip(t["policy"], t["n"])]
    return t[np.asarray(keep, dtype=bool) & t["real_mu"].notna().to_numpy()]


def arm_summary(t: pd.DataFrame, crit: dict) -> Dict[str, Any]:
    """Summary of one (arm, batching) table (its rows = the registered cells): errors over the judged cells, peak, crossing, collapse."""
    j = judged(t, crit["level_excluded_cells"])
    err = j["rel_err_mu"].abs()
    err_t = j["rel_err_mu_turns"].abs()
    fc = t[t["policy"] == "fcfs_lru"].sort_values("n")
    s: Dict[str, Any] = {
        "n_cells": int(len(t)), "n_judged": int(len(j)),
        "mean_abs_rel_err_mu": float(err.mean()), "max_abs_rel_err_mu": float(err.max()),
        "rms_log_ratio_mu": float(np.sqrt(np.mean(np.log(j["mu_mean"] / j["real_mu"]) ** 2))),
        "n_within_tol": int((err <= crit["level_rel_tol"]).sum()), "level_ok": bool((err <= crit["level_rel_tol"]).all()),
        "mean_abs_rel_err_mu_turns": float(err_t.mean()), "n_within_tol_turns": int((err_t <= crit["level_rel_tol"]).sum()),
        "mean_abs_err_hit": float(t["abs_err_hit"].abs().mean()),
        "cells_over_tol": [f"{p}@{int(n)}:{e:+.3f}" for p, n, e in zip(j["policy"], j["n"], j["rel_err_mu"]) if abs(e) > crit["level_rel_tol"]],
        "plateau_max_abs_rel_err": float(fc[fc["n"] <= 24]["rel_err_mu"].abs().max()),
        "tail_max_abs_rel_err": float(fc[fc["n"] >= 48]["rel_err_mu"].abs().max()),
    }
    s["sim_curve"] = summarize_curve(fc.rename(columns={"mu_mean": "mu", "hit_mean": "hit"}), "mu", "hit",
                                     runner_up_frac=crit["peak_runner_up_flag_frac"], level=crit["hit_crossing_level"])
    return s


def real_summary(real: pd.DataFrame, crit: dict) -> Dict[str, Any]:
    fc = real[real["policy"] == "fcfs_lru"].sort_values("n")
    return summarize_curve(fc.rename(columns={"real_mu": "mu", "real_hit": "hit"}), "mu", "hit",
                           runner_up_frac=crit["peak_runner_up_flag_frac"], level=crit["hit_crossing_level"])


def summarize_all(table: pd.DataFrame, real: pd.DataFrame, crit: dict) -> Dict[str, Any]:
    out: Dict[str, Any] = {"real": real_summary(real, crit), "arms": {}}
    for (arm, b), g in table.groupby(["arm", "batching"], sort=False):
        out["arms"].setdefault(arm, {})[b] = arm_summary(g, crit)
    return out


def pick_mode(arm_summaries: Dict[str, Dict[str, Any]], metric: str = "mean_abs_rel_err_mu") -> Dict[str, Any]:
    """The closer batching mode of one arm by ``metric`` (lower wins); None if the arm lacks one of the two modes."""
    if MIXED not in arm_summaries or SEP not in arm_summaries:
        return {"closer": None}
    a, b = arm_summaries[MIXED][metric], arm_summaries[SEP][metric]
    return {"closer": MIXED if a < b else SEP, "mixed": a, "separate": b}


def _f(x: float, nd: int = 3) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x:.{nd}f}"


def _pct(x: float) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{100 * x:+.1f}%"


def _rows_by_batching(table: pd.DataFrame, arm: str):
    """(index, mixed rows, separate rows) of one arm; the index is the union of the (policy, n) cells present, FCFS first, ascending n."""
    t = table[table["arm"] == arm]
    m, s = t[t["batching"] == MIXED].set_index(["policy", "n"]), t[t["batching"] == SEP].set_index(["policy", "n"])
    idx = sorted(set(m.index) | set(s.index), key=lambda pn: (pn[0] != "fcfs_lru", pn[0], pn[1]))
    return idx, m, s


def _cell(row: Optional[pd.Series], col: str, fmt: str) -> str:
    if row is None:
        return "n/a"
    v = row[col]
    if fmt == "pct":
        return _pct(v)
    if fmt == "diff":
        return f"{v:+.3f}" if math.isfinite(v) else "n/a"
    return _f(v)


def md_main_table(table: pd.DataFrame, arm: str = "primary") -> str:
    """Markdown mu table of one arm: real | mixed (seed-mean +- se) | rel. err. | separate | rel. err. (also vs the turns-based real).
    A batching mode the arm does not have shows n/a."""
    idx, m, s = _rows_by_batching(table, arm)
    lines = ["| policy | n | real mu | mixed mu (se) | rel.err | separate mu (se) | rel.err | real mu (turns) | mixed rel.err (turns) | separate rel.err (turns) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i in idx:
        a = m.loc[i] if i in m.index else None
        b = s.loc[i] if i in s.index else None
        ref = a if a is not None else b
        pol, n = i
        lines.append(f"| {'FCFS' if pol == 'fcfs_lru' else 'LPM(128)'} | {n} | {_f(ref['real_mu'])} | {_cell(a, 'mu_mean', 'f')} ({_cell(a, 'mu_se', 'f')}) | "
                     f"{_cell(a, 'rel_err_mu', 'pct')} | {_cell(b, 'mu_mean', 'f')} ({_cell(b, 'mu_se', 'f')}) | {_cell(b, 'rel_err_mu', 'pct')} | "
                     f"{_f(ref['real_mu_turns'])} | {_cell(a, 'rel_err_mu_turns', 'pct')} | {_cell(b, 'rel_err_mu_turns', 'pct')} |")
    return "\n".join(lines)


def md_hit_table(table: pd.DataFrame, arm: str = "primary") -> str:
    """Markdown hit-fraction table of one arm: real | mixed | difference | separate | difference (absolute differences; real hit is 0 at n >= 48)."""
    idx, m, s = _rows_by_batching(table, arm)
    lines = ["| policy | n | real hit | mixed hit | diff | separate hit | diff |", "|---|---|---|---|---|---|---|"]
    for i in idx:
        a = m.loc[i] if i in m.index else None
        b = s.loc[i] if i in s.index else None
        ref = a if a is not None else b
        pol, n = i
        lines.append(f"| {'FCFS' if pol == 'fcfs_lru' else 'LPM(128)'} | {n} | {_f(ref['real_hit'])} | {_cell(a, 'hit_mean', 'f')} | "
                     f"{_cell(a, 'abs_err_hit', 'diff')} | {_cell(b, 'hit_mean', 'f')} | {_cell(b, 'abs_err_hit', 'diff')} |")
    return "\n".join(lines)


def _df_md(df: pd.DataFrame) -> str:
    """Plain markdown table of a DataFrame (no optional tabulate dependency)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("n/a" if (isinstance(v, float) and not math.isfinite(v)) else str(v) for v in row) + " |")
    return "\n".join(lines)


def zscore_table(runs: pd.DataFrame, real: pd.DataFrame) -> pd.DataFrame:
    """Where the single real value falls in the simulator's seed distribution, per (arm, batching, policy, n): sim mean / sd over seeds,
    z = (real - mean) / sd and the fraction of seeds with sim <= real, for mu_sessions and the turns-based estimator."""
    rows = []
    for key, g in runs.groupby(KEY, sort=False):
        r = real[(real["policy"] == key[2]) & (real["n"] == key[3])]
        if r.empty:
            continue
        r = r.iloc[0]
        row = dict(zip(KEY, key))
        row["n_seeds"] = len(g)
        for tag, col, rcol in (("mu", "mu", "real_mu"), ("mu_turns", "mu_turns", "real_mu_turns")):
            x = g[col].to_numpy(dtype=float)
            sd = float(x.std(ddof=1)) if len(x) > 1 else float("nan")
            row[f"{tag}_sim_mean"] = float(x.mean())
            row[f"{tag}_sim_sd"] = sd
            row[f"{tag}_real"] = float(r[rcol])
            # z is undefined for one seed and for (numerically) zero spread: identical values give a float sd ~1e-17, not exactly 0
            spread_ok = math.isfinite(sd) and sd > 1e-9 * max(abs(float(x.mean())), 1e-12)
            row[f"{tag}_z"] = (float(r[rcol]) - float(x.mean())) / sd if spread_ok else float("nan")
            row[f"{tag}_frac_sim_le_real"] = float((x <= float(r[rcol])).mean())
        row["hit_sim_mean"] = float(g["hit_rate"].mean())
        row["hit_real"] = float(r["real_hit"])
        rows.append(row)
    return pd.DataFrame(rows)


def _z(x: float) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x:+.2f}"


def md_zscore_table(z: pd.DataFrame, arm: str = "primary") -> str:
    """z-score table of one arm; an undefined z (one seed, or zero spread across seeds) shows n/a, never 'nan'."""
    t = z[z["arm"] == arm]
    lines = ["| batching | policy | n | real mu | sim mean (sd) | z | frac sims <= real | real mu (turns) | sim mean (sd) | z |", "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in t.iterrows():
        lines.append(f"| {r['batching']} | {'FCFS' if r['policy'] == 'fcfs_lru' else 'LPM(128)'} | {int(r['n'])} | {_f(r['mu_real'])} | "
                     f"{_f(r['mu_sim_mean'])} ({_f(r['mu_sim_sd'])}) | {_z(r['mu_z'])} | {_f(r['mu_frac_sim_le_real'], 2)} | {_f(r['mu_turns_real'])} | "
                     f"{_f(r['mu_turns_sim_mean'])} ({_f(r['mu_turns_sim_sd'])}) | {_z(r['mu_turns_z'])} |")
    return "\n".join(lines)


def md_summary_table(summ: Dict[str, Any]) -> str:
    """One row per (arm, batching): error summary, peak, crossing, collapse ratio, next to the real values."""
    r = summ["real"]
    lines = ["| arm | batching | mean abs rel.err (mu) | max abs | cells within 15% | level_ok | plateau max | tail max | peak n (runner-up gap) | 0.5-hit crossing n | mu(300)/mu* | mu(48)/mu* |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|",
             f"| REAL | Stage C | - | - | - | - | - | - | {r['peak_n']} ({_f(r['runner_up_gap'])}, n={r['runner_up_n']}) | {_f(r['hit_crossing_n'], 1)} | "
             f"{_f(r['mu_300_over_star'])} | {_f(r['mu_48_over_star'])} |"]
    for arm, d in summ["arms"].items():
        for b, s in d.items():
            c = s["sim_curve"]
            lines.append(f"| {arm} | {b} | {_f(s['mean_abs_rel_err_mu'])} | {_f(s['max_abs_rel_err_mu'])} | {s['n_within_tol']}/{s['n_judged']} | "
                         f"{s['level_ok']} | {_f(s['plateau_max_abs_rel_err'])} | {_f(s['tail_max_abs_rel_err'])} | {c['peak_n']} ({_f(c['runner_up_gap'])}, n={c['runner_up_n']}) | "
                         f"{_f(c['hit_crossing_n'], 1)} | {_f(c['mu_300_over_star'])} | {_f(c['mu_48_over_star'])} |")
    return "\n".join(lines)


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round-6 validation of the simulator against the real Stage C curve")
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--spec", "--config", dest="config", default=None, help="validation spec (run)")
    ap.add_argument("--run-dir", default=None, help="result dir of a finished `run` (report)")
    ap.add_argument("--quick", action="store_true", help="smoke test: primary arm only, 1 seed, 3 cells, no supplementary runs")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL")
    ap.add_argument("--tag", default=None)
    return ap


def cmd_run(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    crit = cfg["validate"]["criteria"]
    ctx = begin("r6_validate_stagec", "r6_validate_stagec", cfg, cfg, args, repo_dir)
    real = load_real(cfg, repo_dir)
    real.to_csv(ctx.out / "real_stagec.csv", index=False)
    res = run_all(cfg, args.workers, args.quick)
    runs = res["runs"]
    runs.to_csv(ctx.out / "runs.csv", index=False)
    table = attach_real(seed_table(runs), real)
    table.to_csv(ctx.out / "cell_table.csv", index=False)
    summ = summarize_all(table, real, crit)
    md = ["## Summary per arm and batching mode", md_summary_table(summ), "", "## mu table (primary arm)", md_main_table(table, "primary"),
          "", "## hit table (primary arm)", md_hit_table(table, "primary")]
    for arm in table["arm"].unique():
        if arm != "primary":
            md += ["", f"## mu table ({arm})", md_main_table(table, arm)]
    seeds_used = set(runs["seed"].astype(int))
    if "supp_fine" in res:
        res["supp_fine"].to_csv(ctx.out / "supp_fine_runs.csv", index=False)
        ft = attach_real(seed_table(res["supp_fine"]), real)
        ft.to_csv(ctx.out / "supp_fine_cell_table.csv", index=False)
        seeds_used |= set(res["supp_fine"]["seed"].astype(int))
        # fine-grid curve = registered FCFS grid + fine points, per batching mode
        fine_summ = {}
        for b in cfg["validate"]["arms"]["primary"]["batching_modes"]:
            base = table[(table["arm"] == "primary") & (table["batching"] == b) & (table["policy"] == "fcfs_lru")]
            comb = pd.concat([base, ft[(ft["batching"] == b)]], ignore_index=True).sort_values("n")
            fine_summ[b] = summarize_curve(comb.rename(columns={"mu_mean": "mu", "hit_mean": "hit"}), "mu", "hit",
                                           runner_up_frac=crit["peak_runner_up_flag_frac"], level=crit["hit_crossing_level"])
            comb[["n", "mu_mean", "mu_se", "hit_mean", "mu_turns_mean"]].to_csv(ctx.out / f"supp_fine_curve_{b}.csv", index=False)
        summ["supp_fine_grid"] = fine_summ
    if "supp_seeds" in res:
        res["supp_seeds"].to_csv(ctx.out / "supp_seeds_runs.csv", index=False)
        st = attach_real(seed_table(res["supp_seeds"]), real)
        st.to_csv(ctx.out / "supp_seeds_cell_table.csv", index=False)
        seeds_used |= set(res["supp_seeds"]["seed"].astype(int))
        summ["supp_many_seeds"] = {arm_b: arm_summary(g, crit) for arm_b, g in
                                   ((b, st[st["batching"] == b]) for b in st["batching"].unique())}
        md += ["", "## supplementary: 20-seed means (primary arm), mu", md_main_table(st, "primary")]
    (ctx.out / "summary.json").write_text(json.dumps(summ, indent=2, default=float))
    (ctx.out / "tables.md").write_text("\n".join(md) + "\n")
    finish(ctx, sorted(seeds_used), {"n_runs": int(len(runs)), "calibration_file": cfg["calibration_file"],
                                     "calibration_sha256": cfg["_calibration_sha256"], "engine_effective": cfg["engine"],
                                     "workload_effective": cfg["workload"], "protocol": cfg["validate"]["protocol"],
                                     "criteria": crit, "registered_seeds": cfg["validate"]["seeds"],
                                     "refresh_modelled": False,
                                     "real_files": [f["path"] for f in cfg["validate"]["real"]["files"]]})
    print("\n".join(md))
    print("result dir:", ctx.out)
    return ctx.out


def cmd_report(run_dir: Path, repo_dir: Path) -> Path:
    """Post-processing of a finished ``run`` result dir (no simulation): corrected per-arm tables and the position of the real values inside the
    simulator's seed distribution. Writes NEW files (report.md, zscores_*.csv, report_meta.json); refuses to overwrite an existing report."""
    if (run_dir / "report.md").exists():
        raise FileExistsError(f"{run_dir / 'report.md'} exists; reports are never overwritten")
    meta = json.loads((run_dir / "meta.json").read_text())
    if meta.get("status") != "done":
        raise ValueError(f"{run_dir} is not a finished run (meta.json status={meta.get('status')!r}); nothing to report")
    real = pd.read_csv(run_dir / "real_stagec.csv")
    table = pd.read_csv(run_dir / "cell_table.csv")
    runs = pd.read_csv(run_dir / "runs.csv")
    z3 = zscore_table(runs, real)
    z3.to_csv(run_dir / "zscores_registered_seeds.csv", index=False)
    md = [f"# Report of {run_dir.name} (run commit {meta['git']['commit']}, dirty={meta['git']['dirty']})", ""]
    for arm in table["arm"].unique():
        md += [f"## mu table, arm {arm} (registered seeds {meta['registered_seeds']})", md_main_table(table, arm), ""]
        if arm == "primary":
            md += ["## hit table, arm primary", md_hit_table(table, arm), ""]
    md += ["## position of the real value in the simulator's seed distribution, primary arm, registered seeds (3)", md_zscore_table(z3, "primary"), ""]
    if (run_dir / "supp_seeds_runs.csv").exists():
        r20 = pd.read_csv(run_dir / "supp_seeds_runs.csv")
        z20 = zscore_table(r20, real)
        z20.to_csv(run_dir / "zscores_20seeds.csv", index=False)
        t20 = pd.read_csv(run_dir / "supp_seeds_cell_table.csv")
        md += ["## supplementary 20-seed (100-119) mu table, primary arm", md_main_table(t20, "primary"), "",
               "## supplementary 20-seed hit table, primary arm", md_hit_table(t20, "primary"), "",
               "## position of the real value in the simulator's 20-seed distribution, primary arm", md_zscore_table(z20, "primary"), ""]
    diag = table[table["arm"] == "primary"][["batching", "policy", "n", "gpu_busy_mean", "prefill_tok_per_s_mean", "evictions_per_s_mean",
                                               "reserved_tokens_mean", "idle_tokens_mean"]]
    md += ["## simulator diagnostics, primary arm (means over the measured window and seeds)", _df_md(diag.round(3)), ""]
    (run_dir / "report.md").write_text("\n".join(md))
    (run_dir / "report_meta.json").write_text(json.dumps({"report_git": git_info(repo_dir), "run_commit": meta["git"]["commit"]}, indent=2))
    print("\n".join(md))
    return run_dir / "report.md"


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    if not (1 <= args.workers <= MAX_WORKERS):
        raise SystemExit(f"--workers must be in 1..{MAX_WORKERS}")
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    if args.cmd == "report":
        if not args.run_dir:
            raise SystemExit("report needs --run-dir")
        cmd_report(Path(args.run_dir), repo_dir)
        return 0
    if not args.config:
        raise SystemExit("run needs --spec")
    cfg = load_validation_config(args.config, repo_dir, args.set)
    cmd_run(cfg, args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
