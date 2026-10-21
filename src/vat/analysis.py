"""Offline analysis of collected timings: pools, truth, protocol sweeps, null test, noise."""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .protocols import draw_streams, pct, run_protocols, naive_fixed, bonf_t, cs_race, race_bounds


def add_log_ratio(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["x_raw"] = np.log(df["baseline_ns"] / df["candidate_ns"])
    return df


def build_arrays(df: pd.DataFrame, b: float, holdout: list) -> dict:
    """x[p,k,blk] clipped log-ratio; train pool per candidate; held-out truth theta."""
    df = add_log_ratio(df).sort_values(["proc", "cand", "block"])
    procs = np.sort(df["proc"].unique())
    cands = np.sort(df["cand"].unique())
    P, K, R = len(procs), len(cands), df["block"].nunique()
    x = np.clip(df["x_raw"].to_numpy(), -b, b).reshape(P, K, R)
    ns = (df["baseline_ns"] + df["candidate_ns"]).to_numpy(float).reshape(P, K, R)
    train = [i for i, p in enumerate(procs) if p not in holdout]
    held = [i for i, p in enumerate(procs) if p in holdout]
    bl = np.stack([g.sort_values("t_ns")["baseline_ns"].to_numpy(float)
                   for _, g in df.groupby("proc")])[train]
    return {
        "cands": cands, "procs": procs, "K": K, "R": R,
        "x_pool": x[train].transpose(1, 0, 2).reshape(K, -1),
        "ns_pool": ns[train].transpose(1, 0, 2).reshape(K, -1),
        "theta": x[held].transpose(1, 0, 2).reshape(K, -1).mean(1),
        "theta_train": x[train].transpose(1, 0, 2).reshape(K, -1).mean(1),
        "baseline_train": bl,
    }


def choose_holdout(procs: np.ndarray, n_hold: int, rng: np.random.Generator) -> list:
    return sorted(int(p) for p in rng.choice(procs, size=n_hold, replace=False))


def run_main(arr: dict, acfg: dict, b: float, c: float, seed_seq: np.random.SeedSequence
             ) -> pd.DataFrame:
    """S resampling replicates over the real candidate set; one row per (rep, protocol, param)."""
    out = []
    for s, ss in enumerate(seed_seq.spawn(acfg["S"])):
        rng = np.random.Generator(np.random.PCG64(ss))
        x, ns = draw_streams(arr["x_pool"], arr["ns_pool"], rng)
        for row in run_protocols(x, ns, arr["theta"], acfg, b, c):
            row["rep"] = s
            out.append(row)
    return pd.DataFrame(out)


def summarize(rep: pd.DataFrame, K: int) -> pd.DataFrame:
    g = rep.groupby(["protocol", "param"], sort=False)
    s = g.agg(
        reported_pct=("reported_pct", "mean"), true_pct=("true_pct", "mean"),
        inflation_pct=("inflation_pct", "mean"), inflation_se=("inflation_pct", "sem"),
        regret_pct=("regret_pct", "mean"), fwer=("any_false_accept", "mean"),
        mean_false_accepts=("n_false_accept", "mean"), mean_accepts=("n_accept", "mean"),
        power=("power", "mean"), winner_is_real=("winner_is_real", "mean"),
        blocks=("blocks", "mean"), seconds=("ns", lambda v: v.mean() / 1e9),
        n_rep=("rep", "count"),
    ).reset_index()
    s["fwer_se"] = np.sqrt(s["fwer"] * (1 - s["fwer"]) / s["n_rep"])
    s["blocks_per_cand"] = s["blocks"] / K
    return s


def null_streams(baseline: np.ndarray, K: int, T: int, b: float, rng: np.random.Generator):
    """Null candidates: x = log(baseline_j / baseline_j') for two distinct blocks j != j' of
    the same (random, train) process. Exchangeable pairs => true mean log-ratio is 0."""
    P, M = baseline.shape
    p = rng.integers(P, size=(K, T))
    j = rng.integers(M, size=(K, T))
    j2 = (j + rng.integers(1, M, size=(K, T))) % M
    t1, t2 = baseline[p, j], baseline[p, j2]
    return np.clip(np.log(t1 / t2), -b, b), t1 + t2


def run_null(arr: dict, acfg: dict, b: float, c: float, seed_seq: np.random.SeedSequence
             ) -> pd.DataFrame:
    """All-null stress test: FWER of each protocol vs K."""
    ncfg = acfg["null_test"]
    cfg = dict(acfg, r_values=ncfg["r_values"])
    out = []
    for K in ncfg["K_values"]:
        T = max(ncfg["r_values"])
        for ss in seed_seq.spawn(ncfg["S"]):
            rng = np.random.Generator(np.random.PCG64(ss))
            x, ns = null_streams(arr["baseline_train"], K, T, b, rng)
            for row in run_protocols(x, ns, np.zeros(K), cfg, b, c):
                row["K"] = K
                out.append(row)
    rep = pd.DataFrame(out)
    g = rep.groupby(["K", "protocol", "param"], sort=False)
    s = g.agg(fwer=("any_false_accept", "mean"), mean_false_accepts=("n_false_accept", "mean"),
              blocks=("blocks", "mean"), seconds=("ns", lambda v: v.mean() / 1e9),
              n_rep=("blocks", "count")).reset_index()
    s["fwer_se"] = np.sqrt(s["fwer"] * (1 - s["fwer"]) / s["n_rep"])
    return s


def _lag1(v: np.ndarray) -> float:
    v = v - v.mean()
    d = (v * v).sum()
    return float((v[1:] * v[:-1]).sum() / d) if d > 0 else np.nan


def noise_summary(df: pd.DataFrame, b: float) -> pd.DataFrame:
    """Per-candidate noise characterisation (log-ratios unclipped except clip fraction)."""
    df = add_log_ratio(df).sort_values(["cand", "proc", "block"])
    rows = []
    for cid, g in df.groupby("cand"):
        procs = [h for _, h in g.groupby("proc")]
        xr = np.stack([h["x_raw"].to_numpy() for h in procs])           # [P, R]
        ct = np.stack([h["candidate_ns"].to_numpy(float) for h in procs])
        P, R = xr.shape
        msb = R * xr.mean(1).var(ddof=1) if P > 1 else np.nan
        msw = xr.var(1, ddof=1).mean()
        sb2 = max(0.0, (msb - msw) / R) if P > 1 else np.nan
        rows.append({
            "cand": cid,
            "mean_log_ratio": xr.mean(), "speedup_pct": float(pct(xr.mean())),
            "cv_cand_time_within_proc": float(np.mean(ct.std(1, ddof=1) / ct.mean(1))),
            "within_proc_var_logratio": float(msw), "between_proc_var_logratio": float(sb2),
            "icc_between": float(sb2 / (sb2 + msw)) if P > 1 else np.nan,
            "lag1_autocorr_logratio": float(np.mean([_lag1(r) for r in xr])),
            "frac_clipped": float((np.abs(xr) > b).mean()),
            "p99_over_p50_time": float(np.mean(np.percentile(ct, 99, axis=1) / np.median(ct, axis=1))),
        })
    # baseline's own time noise (from all blocks, time-ordered per process)
    bl = np.stack([h.sort_values("t_ns")["baseline_ns"].to_numpy(float)
                   for _, h in df.groupby("proc")])
    rows.append({"cand": -1, "cv_cand_time_within_proc": float(np.mean(bl.std(1, ddof=1) / bl.mean(1))),
                 "p99_over_p50_time": float(np.mean(np.percentile(bl, 99, axis=1) / np.median(bl, axis=1))),
                 "lag1_autocorr_logratio": float(np.mean([_lag1(np.log(r)) for r in bl]))})
    return pd.DataFrame(rows)
