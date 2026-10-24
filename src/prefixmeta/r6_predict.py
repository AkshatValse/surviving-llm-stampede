"""Round-6 PREDICT stage: analysis of the blind-prediction runs B1-B4 (no simulation happens here).

The runs themselves are ordinary ``probe`` calls (``experiments/prefix_meta_probe_run.py {curve,open,burst} --spec configs/r6_predict.yaml ...``, driver
``experiments/r6_predict_run.sh``); each call writes its own ``results/prefix_meta_probe_<cmd>_<tag>/<timestamp>/`` and the driver appends one line
``part<TAB>cmd<TAB>tag<TAB>dir`` per call to ``results/r6_predict/manifest.tsv``. ``report`` reads that manifest and writes a NEW
``results/r6_predict_report/<timestamp>/`` (tables.md, summary.json, CSVs, meta.json).

Declared definitions (configs/r6_predict.yaml ``predict:``; fixed before any prediction run)
-------------------------------------------------------------------------------------------
B1  all-miss capacity: cache disabled, closed population POP, measured window [900, 2700) s. ``mu`` = sessions completed / s; ``mu_turns`` = completed turns / s
    divided by E[T] = 14.761; ``token_rate`` = mean of the 100 s windows' ``prefill_tok_per_s`` (prefill tokens PROCESSED per second; with the cache off every
    token of every prompt is uncached). The reference used by B3 is POP = 32, seeds 0-2, 3-seed mean, of the same batching mode.
B2  stable := not early-stopped, final backlog < 50, OLS rise of the backlog over the last 1500 s <= 10 requests (``mech_runner.backlog_verdict``).
    Predicted from-empty edge := the largest grid lambda such that every grid lambda <= it is all-stable (all seeds).
B3  per run, over the evaluation window E = [t_burst + 5000, t_burst + 7500) (the last 2500 s of the run; the same absolute window for the no-burst arm):
      hit_E = hits / admitted turns; backlog_E = mean of (queue_mean + gate_mean) over the 100 s windows; slope_E = OLS slope (requests / s) of
      (queue_mean + gate_mean) against the window centre; token_rate_E = mean ``prefill_tok_per_s``.
      TRAPPED   := |token_rate_E / B1_token_rate - 1| <= 0.15  AND  slope_E > 0.5 * (lambda - lambda_miss),   lambda_miss = B1 turns-based POP = 32 value
      RECOVERED := hit_E > 0.8 AND backlog_E < 20 (the probe's ``recovered``); NOBURST "good" := the same test on the no_burst arm.
    Per lambda: a condition holds if it holds in at least ceil(2/3 * n_seeds) seeds (2 of 3); PASS := BURST trapped AND NOBURST good AND CAPPED recovered.
B4  closed Stage C protocol with a larger KV pool: ``mu``, ``mu_turns`` and ``hit_rate`` of ``probe curve`` (cache on, FCFS).
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
from .r6_validate import MIXED, SEP, crossing, first_argmax
from .runner import git_info
from .sim import load_config
from .workload import WorkloadParams

MODES = (MIXED, SEP)
MODE_TAG = {MIXED: "mixed", SEP: "sep"}


# ======================================================================= generic helpers
def df_md(df: pd.DataFrame, floatfmt: str = "{:.4g}") -> str:
    """Plain markdown table of a DataFrame ('n/a' for NaN)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = []
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append("n/a" if not math.isfinite(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_dir(d: Path) -> Tuple[dict, pd.DataFrame, pd.DataFrame]:
    """(meta, runs, windows) of a finished probe result dir; refuses an unfinished one."""
    meta = json.loads((d / "meta.json").read_text())
    if meta.get("status") != "done":
        raise ValueError(f"{d} is not a finished run (status={meta.get('status')!r})")
    runs = pd.read_csv(d / "runs.csv")
    wins = pd.read_csv(d / "windows.csv") if (d / "windows.csv").exists() else pd.DataFrame()
    return meta, runs, wins


def read_manifest(path: Path) -> pd.DataFrame:
    m = pd.read_csv(path, sep="\t")
    need = {"part", "cmd", "tag", "dir"}
    if not need <= set(m.columns):
        raise ValueError(f"manifest {path} needs columns {sorted(need)}")
    if m["tag"].duplicated().any():
        raise ValueError(f"duplicate tags in the manifest: {m['tag'][m['tag'].duplicated()].tolist()}")
    return m


def expected_turns(workload: dict) -> float:
    return WorkloadParams.from_dict(workload).effective_mean_turns()


# ======================================================================= B1: all-miss capacity
def window_mean(wins: pd.DataFrame, run_id: int, col: str, t_from: float, t_to: Optional[float] = None) -> float:
    w = wins[(wins["run_id"] == run_id) & (wins["t_start"] >= t_from - 1e-9)]
    if t_to is not None:
        w = w[w["t_end"] <= t_to + 1e-9]
    return float(w[col].mean()) if len(w) else float("nan")


def b1_runs(d: Path, E_T: float, warmup_s: float, horizon_s: float, window_s: float) -> pd.DataFrame:
    """One row per (population, seed) of a ``probe curve`` dir: mu, mu_turns, token_rate (all over [warmup_s, horizon_s)), busy, hit."""
    meta, runs, wins = load_dir(d)
    cr = pd.read_csv(d / "curve_runs.csv")
    if len(cr) != len(runs):
        raise ValueError(f"{d}: curve_runs.csv and runs.csv differ in length")
    rows = []
    for i, r in cr.reset_index(drop=True).iterrows():
        rid = int(runs.loc[i, "run_id"])
        if int(runs.loc[i, "seed"]) != int(r["seed"]):
            raise ValueError("row order mismatch between curve_runs.csv and runs.csv")
        sel = wins[(wins["run_id"] == rid) & (wins["t_start"] >= warmup_s - 1e-9) & (wins["t_end"] <= horizon_s + 1e-9)]
        if len(sel) != round((horizon_s - warmup_s) / window_s):
            raise ValueError(f"{d}: run {rid} has {len(sel)} measurement windows")
        rows.append({"n": int(r["n_nominal"]), "seed": int(r["seed"]), "mu": float(r["mu"]), "mu_turns": float(r["turns_per_s"]) / E_T,
                     "turns_per_s": float(r["turns_per_s"]), "token_rate": float(sel["prefill_tok_per_s"].mean()),
                     "busy": float(sel["busy_frac"].mean()), "hit_rate": float(r["hit_rate"]), "n_windows": int(len(sel))})
    return pd.DataFrame(rows)


def summarize_seeds(df: pd.DataFrame, cols: Sequence[str], by: Sequence[str]) -> pd.DataFrame:
    """Per ``by`` group: n_seeds and mean / sd (ddof 1) of each column in ``cols``."""
    rows = []
    for key, g in df.groupby(list(by), sort=True):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(by, key))
        row["n_seeds"] = int(len(g))
        for c in cols:
            row[c + "_mean"] = float(g[c].mean())
            row[c + "_sd"] = float(g[c].std(ddof=1)) if len(g) > 1 else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


# ======================================================================= B2: from-empty stability
def contiguous_edge(lams: Sequence[float], all_stable: Sequence[bool]) -> Optional[float]:
    """Largest grid lambda such that every grid lambda <= it is all-stable; None if even the smallest is not."""
    order = np.argsort(np.asarray(lams, dtype=float), kind="stable")
    edge = None
    for i in order:
        if bool(all_stable[i]):
            edge = float(lams[i])
        else:
            break
    return edge


def largest_all_stable(lams: Sequence[float], all_stable: Sequence[bool]) -> Optional[float]:
    ok = [float(l) for l, s in zip(lams, all_stable) if bool(s)]
    return max(ok) if ok else None


def b2_table(d: Path) -> pd.DataFrame:
    """Per lambda: n_runs, n_stable, stable fraction, mean final backlog, mean trend rise, mean tail hit, all_stable."""
    v = pd.read_csv(d / "open_verdicts.csv")
    g = v.groupby("lam", sort=True)
    t = g.agg(n_runs=("stable", "size"), n_stable=("stable", "sum"), final_backlog_mean=("final_backlog", "mean"),
              final_backlog_max=("final_backlog", "max"), trend_rise_mean=("trend_rise", "mean"), tail_hit_mean=("tail_hit_rate", "mean"),
              tail_busy_mean=("tail_busy_frac", "mean")).reset_index()
    t["n_stable"] = t["n_stable"].astype(int)
    t["stable_frac"] = t["n_stable"] / t["n_runs"]
    t["all_stable"] = t["n_stable"] == t["n_runs"]
    return t


# ======================================================================= B3: E2 paired arms
def eval_stats(w: pd.DataFrame, t_from: float, t_to: float) -> Dict[str, float]:
    """hit rate, mean backlog (queue + gate), OLS backlog slope (requests / s), mean prefill token rate over the complete windows in [t_from, t_to]."""
    s = w[(w["t_start"] >= t_from - 1e-9) & (w["t_end"] <= t_to + 1e-9)].sort_values("t_start")
    if s.empty:
        return {"n_windows": 0, "hit": float("nan"), "backlog": float("nan"), "slope": float("nan"), "token_rate": float("nan")}
    adm = float(s["admitted_turns"].sum())
    backlog = (s["queue_mean"] + s["gate_mean"]).to_numpy(dtype=float)
    x = ((s["t_start"] + s["t_end"]) / 2.0).to_numpy(dtype=float)
    slope = float(np.polyfit(x, backlog, 1)[0]) if len(s) >= 3 else float("nan")
    return {"n_windows": int(len(s)), "hit": float(s["hits"].sum()) / adm if adm else float("nan"), "backlog": float(backlog.mean()), "slope": slope,
            "token_rate": float(s["prefill_tok_per_s"].mean())}


def classify(stats: Dict[str, float], lam: float, lam_miss: float, token_rate_miss: float, p: dict) -> Dict[str, Any]:
    """TRAPPED / RECOVERED flags and the label of one run from its evaluation-window statistics (definitions in the module docstring)."""
    ratio = stats["token_rate"] / token_rate_miss if token_rate_miss else float("nan")
    thr = p["trapped_slope_frac"] * (lam - lam_miss)
    rate_ok = bool(abs(ratio - 1.0) <= p["trapped_token_rate_rel_tol"]) if ratio == ratio else False
    slope_ok = bool(stats["slope"] > thr) if stats["slope"] == stats["slope"] else False
    trapped = rate_ok and slope_ok
    recovered = bool(stats["hit"] > p["recovered_hit_above"] and stats["backlog"] < p["recovered_backlog_below"])
    label = "BOTH" if (trapped and recovered) else "TRAPPED" if trapped else "RECOVERED" if recovered else "neither"
    return {"token_ratio": ratio, "slope_threshold": thr, "rate_ok": rate_ok, "slope_ok": slope_ok, "trapped": trapped, "recovered": recovered,
            "label": label}


def b3_runs(d: Path, lam_miss: float, token_rate_miss: float, p: dict, eval_rel: Sequence[float] = (5000.0, 7500.0), check: bool = True) -> pd.DataFrame:
    """One row per (arm, seed) of a ``probe burst`` dir, with the declared TRAPPED / RECOVERED classification over [t_burst + eval_rel[0], t_burst + eval_rel[1]]."""
    meta, runs, wins = load_dir(d)
    rows = []
    for _, r in runs.iterrows():
        tb = float(r["t_burst"])
        w = wins[wins["run_id"] == r["run_id"]]
        st = eval_stats(w, tb + eval_rel[0], tb + eval_rel[1])
        lam = float(r["lam"])
        row = {"lam": lam, "arm": r["arm"], "seed": int(r["seed"]), "cap": int(r["cap"]), "burst_n": int(r["burst_n"]), "n_windows": st["n_windows"],
               "token_rate": st["token_rate"], "hit": st["hit"], "backlog": st["backlog"], "slope": st["slope"],
               "rise_over_window": st["slope"] * (eval_rel[1] - eval_rel[0]), **classify(st, lam, lam_miss, token_rate_miss, p)}
        if check:          # cross-checks against the probe's own columns (same window by construction of the spec: hit_eval_from_s, metrics.tail_window_s)
            row["check_hit_diff"] = abs(st["hit"] - float(r["hit_eval"])) if st["hit"] == st["hit"] else float("nan")
            row["check_backlog_diff"] = abs(st["backlog"] - float(r["tail_backlog_mean"]))
        rows.append(row)
    return pd.DataFrame(rows)


def b3_verdicts(runs: pd.DataFrame, min_frac: float) -> pd.DataFrame:
    """Per lambda: counts out of n_seeds of BURST trapped, NOBURST good, CAPPED recovered, and PASS (each count >= ceil(min_frac * n_seeds))."""
    rows = []
    for lam, g in runs.groupby("lam", sort=True):
        ns = int(g[g["arm"] == "burst"]["seed"].nunique())
        need = int(math.ceil(min_frac * ns - 1e-9))
        cnt = lambda arm, col: int(g[(g["arm"] == arm)][col].sum())      # noqa: E731
        row = {"lam": float(lam), "n_seeds": ns, "need": need,
               "burst_trapped": cnt("burst", "trapped"), "noburst_good": cnt("no_burst", "recovered"), "cap_recovered": cnt("burst_cap", "recovered"),
               "burst_recovered": cnt("burst", "recovered"), "noburst_trapped": cnt("no_burst", "trapped"), "cap_trapped": cnt("burst_cap", "trapped")}
        row["PASS"] = bool(row["burst_trapped"] >= need and row["noburst_good"] >= need and row["cap_recovered"] >= need)
        row["PASS_all_seeds"] = bool(row["burst_trapped"] == ns and row["noburst_good"] == ns and row["cap_recovered"] == ns)
        rows.append(row)
    return pd.DataFrame(rows)


# ======================================================================= B4: closed curves with a larger pool
def b4_table(d: Path, E_T: float) -> pd.DataFrame:
    cr = pd.read_csv(d / "curve_runs.csv")
    out = cr[["n_nominal", "seed", "mu", "turns_per_s", "hit_rate", "gpu_busy"]].copy()
    out["mu_turns"] = out["turns_per_s"] / E_T
    return out.rename(columns={"n_nominal": "n"})


def b4_landmarks(b4: pd.DataFrame) -> pd.DataFrame:
    """Per (mode, KV pool) and per seed set (seed 0 only / all seeds present): peak n and mu*, the 0.5-hit crossing n, mu(300) and the n=48/64/96 values."""
    rows = []
    for (mode, kv), g in b4.groupby(["mode", "kv_k"], sort=True):
        for label, sel in (("seed 0", g[g["seed"] == 0]), (f"seeds {int(g['seed'].min())}-{int(g['seed'].max())} mean", g)):
            t = sel.groupby("n").agg(mu=("mu", "mean"), hit=("hit_rate", "mean")).reset_index().sort_values("n")
            n_star, mu_star = first_argmax(t["n"].tolist(), t["mu"].tolist())
            row = {"mode": mode, "kv_k": int(kv), "seeds": label, "n_seeds": int(sel["seed"].nunique()), "peak_n": n_star, "peak_mu": mu_star,
                   "hit_crossing_n": crossing(t["n"].tolist(), t["hit"].tolist(), 0.5)}
            for n in (48, 64, 96, 300):
                row[f"mu_{n}"] = float(t.loc[t["n"] == n, "mu"].iloc[0]) if (t["n"] == n).any() else float("nan")
            rows.append(row)
    return pd.DataFrame(rows)


# ======================================================================= report
def _dirs(man: pd.DataFrame, repo: Path) -> Dict[str, Path]:
    return {r.tag: (repo / r.dir) for r in man.itertuples()}


def cmd_report(spec_path: Path, manifest: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    spec = load_config(str(spec_path))
    pred = spec["predict"]
    E_T = expected_turns(spec["workload"])
    if abs(E_T - pred["b1"]["expected_turns"]) > 5e-4:
        raise ValueError(f"E[T]={E_T} differs from the declared {pred['b1']['expected_turns']}")
    man = read_manifest(manifest)
    D = _dirs(man, repo_dir)
    W = float(spec["metrics"]["window_s"])
    cv = spec["probe"]["curve"]
    warm, hor = float(cv["warmup_s"]), float(cv["horizon_s"])
    p3 = dict(pred["b3"])
    summ: Dict[str, Any] = {"git": git_info(repo_dir), "E_T": E_T, "modes": {}}
    md: List[str] = []
    ctx = begin("r6_predict_report", "r6_predict_report", spec, spec, args, repo_dir)
    all_b1, all_b2, all_b2s, all_b3, all_b3v, all_b3sens, all_b3s, all_b4 = [], [], [], [], [], [], [], []
    for mode in MODES:
        mt = MODE_TAG[mode]
        S: Dict[str, Any] = {}
        # ---------------- B1
        b1 = pd.concat([b1_runs(D[f"r6pred_b1pop32_{mt}"], E_T, warm, hor, W), b1_runs(D[f"r6pred_b1pop64_{mt}"], E_T, warm, hor, W)], ignore_index=True)
        b1.insert(0, "mode", mode)
        all_b1.append(b1)
        b1s = summarize_seeds(b1, ["mu", "mu_turns", "token_rate", "busy"], ["n"])
        ref = b1[b1["n"] == pred["b1"]["reference_population"]]
        lam_miss_turns, lam_miss_sess, tok_miss = float(ref["mu_turns"].mean()), float(ref["mu"].mean()), float(ref["token_rate"].mean())
        S["b1"] = {"lambda_miss_turns": lam_miss_turns, "lambda_miss_sessions": lam_miss_sess, "token_rate": tok_miss,
                   "table": b1s.to_dict(orient="records")}
        # ---------------- B2
        b2 = b2_table(D[f"r6pred_b2_{mt}"])
        b2.insert(0, "mode", mode)
        all_b2.append(b2)
        edge = contiguous_edge(b2["lam"].tolist(), b2["all_stable"].tolist())
        las = largest_all_stable(b2["lam"].tolist(), b2["all_stable"].tolist())
        S["b2"] = {"edge_contiguous": edge, "edge_over_lambda_miss_turns": (edge / lam_miss_turns if edge else None),
                   "largest_all_stable": las, "largest_all_stable_over_lambda_miss_turns": (las / lam_miss_turns if las else None),
                   "stable_fraction": {f"{r.lam:g}": r.stable_frac for r in b2.itertuples()}}
        s20 = D.get(f"r6pred_b2s20_{mt}")
        if s20 is not None:
            b2s = b2_table(s20)
            b2s.insert(0, "mode", mode)
            all_b2s.append(b2s)
            c50 = crossing(b2s["lam"].tolist(), b2s["stable_frac"].tolist(), 0.5)
            c95 = crossing(b2s["lam"].tolist(), b2s["stable_frac"].tolist(), 0.95)
            S["b2_supp_20seeds"] = {"stable_fraction": {f"{r.lam:g}": r.stable_frac for r in b2s.itertuples()},
                                    "lambda_stable_frac_crosses_0.5": c50, "lambda_stable_frac_crosses_0.95": c95,
                                    "edge_all_stable_contiguous": contiguous_edge(b2s["lam"].tolist(), b2s["all_stable"].tolist())}
        # ---------------- B3
        b3_lams = sorted({float(t.split("lam")[1].split("_")[0]) for t in D if t.startswith("r6pred_b3_lam") and t.endswith("_" + mt)})
        ev0 = tuple(float(x) for x in p3["eval_window_s"])
        runs3 = pd.concat([b3_runs(D[f"r6pred_b3_lam{l:.2f}_{mt}"], lam_miss_turns, tok_miss, p3, eval_rel=ev0) for l in b3_lams], ignore_index=True)
        runs3.insert(0, "mode", mode)
        all_b3.append(runs3)
        v3 = b3_verdicts(runs3, float(p3["pass_min_frac"]))
        v3.insert(0, "mode", mode)
        all_b3v.append(v3)
        S["b3"] = {"lambdas": b3_lams, "PASS": {f"{r.lam:g}": bool(r.PASS) for r in v3.itertuples()},
                   "PASS_all_seeds": {f"{r.lam:g}": bool(r.PASS_all_seeds) for r in v3.itertuples()},
                   "check_hit_diff_max": float(np.nanmax(runs3["check_hit_diff"])), "check_backlog_diff_max": float(np.nanmax(runs3["check_backlog_diff"]))}
        s_lams = sorted({float(t.split("lam")[1].split("_")[0]) for t in D if t.startswith("r6pred_b3s20_lam") and t.endswith("_" + mt)})
        if s_lams:
            runs3s = pd.concat([b3_runs(D[f"r6pred_b3s20_lam{l:.2f}_{mt}"], lam_miss_turns, tok_miss, p3, eval_rel=ev0) for l in s_lams], ignore_index=True)
            v3s = b3_verdicts(runs3s, float(p3["pass_min_frac"]))
            v3s.insert(0, "mode", mode)
            all_b3s.append(v3s)
            S["b3_supp_20seeds"] = {"PASS": {f"{r.lam:g}": bool(r.PASS) for r in v3s.itertuples()},
                                    "burst_trapped": {f"{r.lam:g}": int(r.burst_trapped) for r in v3s.itertuples()},
                                    "noburst_good": {f"{r.lam:g}": int(r.noburst_good) for r in v3s.itertuples()},
                                    "cap_recovered": {f"{r.lam:g}": int(r.cap_recovered) for r in v3s.itertuples()}}
        for ev in p3["sensitivity_eval_windows_s"]:
            rs = pd.concat([b3_runs(D[f"r6pred_b3_lam{l:.2f}_{mt}"], lam_miss_turns, tok_miss, p3, eval_rel=ev, check=False) for l in b3_lams],
                           ignore_index=True)
            vs = b3_verdicts(rs, float(p3["pass_min_frac"]))
            vs.insert(0, "eval_window_rel_to_burst", f"[{ev[0]:g}, {ev[1]:g}]")
            vs.insert(0, "mode", mode)
            all_b3sens.append(vs)
        # ---------------- B4
        for kv in (300, 600, 900):
            t = D.get(f"r6pred_b4_kv{kv}k_{mt}")
            if t is None:
                continue
            b4 = b4_table(t, E_T)
            b4.insert(0, "kv_k", kv)
            b4.insert(0, "mode", mode)
            b4["set"] = "registered(seed 0)"
            all_b4.append(b4)
            ts = D.get(f"r6pred_b4s_kv{kv}k_{mt}")
            if ts is not None:
                bs = b4_table(ts, E_T)
                bs.insert(0, "kv_k", kv)
                bs.insert(0, "mode", mode)
                bs["set"] = "supplementary(seeds 1-4)"
                all_b4.append(bs)
        summ["modes"][mode] = S
    cat = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()      # noqa: E731
    b1_all, b2_all, b2s_all, b3_all, b3v_all, b3sens_all, b3s_all, b4_all = (cat(x) for x in (all_b1, all_b2, all_b2s, all_b3, all_b3v, all_b3sens, all_b3s,
                                                                                               all_b4))
    for name, df in (("b1_seed", b1_all), ("b2_table", b2_all), ("b2_supp20_table", b2s_all), ("b3_runs", b3_all), ("b3_verdicts", b3v_all),
                     ("b3_sensitivity_verdicts", b3sens_all), ("b3_supp20_verdicts", b3s_all), ("b4_runs", b4_all)):
        if len(df):
            df.to_csv(ctx.out / f"{name}.csv", index=False)
    # ---------------- markdown
    md.append(f"# Round-6 Predict: tables (report {ctx.out.name}, code commit {summ['git']['commit']}, dirty={summ['git']['dirty']})\n")
    md.append("## B1. All-miss capacity (cache disabled, closed population, FCFS, window [900, 2700) s)\n")
    t = summarize_seeds(b1_all, ["mu", "mu_turns", "token_rate", "busy"], ["mode", "n"])
    md.append(df_md(t, "{:.5g}") + "\n")
    md.append("Per seed:\n")
    md.append(df_md(b1_all[["mode", "n", "seed", "mu", "mu_turns", "token_rate", "busy", "hit_rate"]], "{:.5g}") + "\n")
    md.append("B3 reference values used below (POP = 32, seeds 0-2, 3-seed means):\n")
    md.append(df_md(pd.DataFrame([{"mode": m, "lambda_miss_turns": summ["modes"][m]["b1"]["lambda_miss_turns"],
                                   "lambda_miss_sessions": summ["modes"][m]["b1"]["lambda_miss_sessions"],
                                   "token_rate_tok_per_s": summ["modes"][m]["b1"]["token_rate"]} for m in MODES]), "{:.5g}") + "\n")
    md.append("## B2. From-empty open-loop stability (cache on, FCFS, horizon 3000 s, seeds 0-2)\n")
    show = b2_all.copy()
    show["stable"] = [f"{r.n_stable}/{r.n_runs}" for r in show.itertuples()]
    md.append(df_md(show[["mode", "lam", "stable", "final_backlog_mean", "final_backlog_max", "trend_rise_mean", "tail_hit_mean", "tail_busy_mean"]], "{:.4g}") + "\n")
    md.append(df_md(pd.DataFrame([{"mode": m, "edge (largest lambda with every smaller grid lambda all-stable), sessions/s": summ["modes"][m]["b2"]["edge_contiguous"],
                                   "x B1 turns-based lambda_miss": summ["modes"][m]["b2"]["edge_over_lambda_miss_turns"],
                                   "largest all-stable grid lambda": summ["modes"][m]["b2"]["largest_all_stable"],
                                   "x B1 turns-based (largest)": summ["modes"][m]["b2"]["largest_all_stable_over_lambda_miss_turns"]} for m in MODES]), "{:.4g}") + "\n")
    if len(b2s_all):
        md.append("Supplementary (labelled, not part of the prediction): stable fraction with 20 fresh seeds (100-119):\n")
        sp = b2s_all.copy()
        sp["stable"] = [f"{r.n_stable}/{r.n_runs}" for r in sp.itertuples()]
        md.append(df_md(sp[["mode", "lam", "stable", "stable_frac", "final_backlog_mean", "trend_rise_mean"]], "{:.4g}") + "\n")
        md.append(df_md(pd.DataFrame([{"mode": m, **{k: v for k, v in summ["modes"][m]["b2_supp_20seeds"].items() if k != "stable_fraction"}} for m in MODES
                                      if "b2_supp_20seeds" in summ["modes"][m]]), "{:.4g}") + "\n")
    md.append("## B3. E2 paired arms (lambda grid, seeds 0-2; eval window = last 2500 s)\n")
    md.append("Per-lambda verdict (counts out of the seeds; PASS needs each of the first three counts >= `need`):\n")
    md.append(df_md(b3v_all, "{:.4g}") + "\n")
    md.append("Per run:\n")
    cols = ["mode", "lam", "seed", "arm", "label", "token_ratio", "slope", "slope_threshold", "rise_over_window", "hit", "backlog", "token_rate"]
    md.append(df_md(b3_all.sort_values(["mode", "lam", "arm", "seed"])[cols], "{:.4g}") + "\n")
    md.append("Sensitivity of the verdicts to the evaluation window (labelled; never used for the verdict):\n")
    md.append(df_md(b3sens_all[["mode", "eval_window_rel_to_burst", "lam", "burst_trapped", "noburst_good", "cap_recovered", "PASS"]], "{:.4g}") + "\n")
    if len(b3s_all):
        md.append("Supplementary (labelled, not part of the prediction): the same per-lambda verdict with 20 fresh seeds (100-119), counts out of 20 (need = 14):\n")
        md.append(df_md(b3s_all, "{:.4g}") + "\n")
    md.append("## B4. Closed-population curves with a larger KV pool (cache on, FCFS)\n")
    if len(b4_all):
        reg = b4_all[b4_all["set"].str.startswith("registered")]
        md.append("Registered (seed 0; each cell is `mu sessions/s / mu turns-based sessions/s / hit fraction`; the 300k column is the validation's own cell rerun in the same code):\n")
        for mode in MODES:
            rm = reg[reg["mode"] == mode]
            tab = pd.DataFrame({"n": sorted(rm["n"].unique())})
            for kv in sorted(rm["kv_k"].unique()):
                g = rm[rm["kv_k"] == kv].set_index("n")
                tab[f"{kv}k pool"] = [f"{g.loc[n, 'mu']:.4f} / {g.loc[n, 'mu_turns']:.4f} / {g.loc[n, 'hit_rate']:.3f}" for n in tab["n"]]
            md.append(f"{mode}:\n")
            md.append(df_md(tab) + "\n")
        lm = b4_landmarks(b4_all)
        lm.to_csv(ctx.out / "b4_landmarks.csv", index=False)
        md.append("Landmarks of the B4 curves (peak = first argmax of mu over the grid; hit crossing = n at which the hit fraction falls through 0.5, linear interpolation "
                  "between adjacent grid points; coarse grid: 16, 24, 32, 48, 64, 96, 300):\n")
        md.append(df_md(lm, "{:.4g}") + "\n")
        summ["b4_landmarks"] = lm.to_dict(orient="records")
        sup = b4_all[b4_all["set"].str.startswith("supp")]
        if len(sup):
            allv = b4_all.copy()
            sm = allv.groupby(["mode", "kv_k", "n"]).agg(n_seeds=("seed", "nunique"), mu_mean=("mu", "mean"), mu_sd=("mu", "std"), mu_turns_mean=("mu_turns", "mean"),
                                                         hit_mean=("hit_rate", "mean")).reset_index()
            sm.to_csv(ctx.out / "b4_seed_means.csv", index=False)
            md.append("Supplementary: mean over seeds 0-4 (registered seed 0 plus supplementary seeds 1-4):\n")
            md.append(df_md(sm, "{:.4g}") + "\n")
    (ctx.out / "tables.md").write_text("\n".join(md))
    (ctx.out / "summary.json").write_text(json.dumps(summ, indent=2, default=float))
    finish(ctx, sorted(set(int(s) for s in b1_all["seed"]) | set(int(s) for s in b3_all["seed"])),
           {"manifest": str(manifest), "n_manifest_dirs": int(len(man)), "predict_definitions": pred, "E_T": E_T})
    print("\n".join(md))
    print("result dir:", ctx.out)
    return ctx.out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round-6 Predict: tables from the probe result dirs listed in a manifest (no simulation)")
    ap.add_argument("cmd", choices=["report"])
    ap.add_argument("--spec", "--config", dest="config", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[])
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    cmd_report(Path(args.config), Path(args.manifest), args, repo_dir)
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
