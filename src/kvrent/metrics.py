"""Per-run metrics and cross-seed aggregation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .sim import SimParams, SimResult


def run_metrics(res: SimResult, prm: SimParams) -> dict:
    """Latency over programs arriving in [warmup, horizon - margin].

    Primary latency stats use completed programs only. `*_cens` columns
    additionally include unfinished programs at their lower-bound latency
    (horizon - arrival), to expose censoring bias.
    """
    a, f = res.arrival, res.finish
    win = (a >= prm.warmup) & (a < prm.horizon - prm.margin)
    done = win & ~np.isnan(f)
    lat = (f - a)[done]
    inflight = int((win & np.isnan(f)).sum())
    lat_c = np.concatenate([lat, (prm.horizon - a)[win & np.isnan(f)]])

    def q(x: np.ndarray, p: float) -> float:
        return float(np.percentile(x, p)) if len(x) else float("nan")

    ncalls = res.n_held + res.n_swap + res.n_discard
    span = prm.horizon - prm.warmup - prm.margin
    return dict(
        n_window=int(win.sum()), n_done=int(done.sum()), n_inflight=inflight,
        mean_lat=float(lat.mean()) if len(lat) else float("nan"),
        p50=q(lat, 50), p95=q(lat, 95), p99=q(lat, 99),
        mean_lat_cens=float(lat_c.mean()) if len(lat_c) else float("nan"),
        p95_cens=q(lat_c, 95),
        throughput=float(done.sum() / span),
        util_mean=res.util_mean, max_used=res.max_used,
        frac_held=res.n_held / ncalls if ncalls else float("nan"),
        frac_swap=res.n_swap / ncalls if ncalls else float("nan"),
        frac_discard=res.n_discard / ncalls if ncalls else float("nan"),
        n_forced=res.n_forced, recompute_s=res.recompute_s, swap_s=res.swap_s,
        n_events=res.n_events,
    )


def ci95(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float("nan")
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def summarize(raw: pd.DataFrame, etas: list[float]) -> pd.DataFrame:
    """Aggregate raw per-run rows over seeds. Eta-free policies are replicated per eta.

    Ratios to ORACLE_STATIC are computed per seed (paired; same workload, same eta),
    then mean +/- 95% t-CI across seeds.
    """
    raw = raw.copy()
    free = raw["eta"].isna()
    rep = [raw[~free]]
    for e in etas:
        r = raw[free].copy()
        r["eta"] = e
        rep.append(r)
    df = pd.concat(rep, ignore_index=True)
    keys = ["mix", "lam", "eta", "seed"]
    orc = df[df.policy == "ORACLE_STATIC"].set_index(keys)[["mean_lat", "p95", "mean_lat_cens", "p95_cens"]]
    df = df.join(orc, on=keys, rsuffix="_orc")
    df["ratio_mean"] = df.mean_lat / df.mean_lat_orc
    df["ratio_p95"] = df.p95 / df.p95_orc
    df["ratio_mean_cens"] = df.mean_lat_cens / df.mean_lat_cens_orc
    df["ratio_p95_cens"] = df.p95_cens / df.p95_cens_orc
    cols = ["mean_lat", "p50", "p95", "p99", "throughput", "util_mean", "frac_held", "frac_swap",
            "frac_discard", "n_forced", "n_inflight", "recompute_s", "swap_s",
            "mean_lat_cens", "p95_cens", "ratio_mean", "ratio_p95", "ratio_mean_cens", "ratio_p95_cens"]
    out = []
    for k, g in df.groupby(["mix", "lam", "eta", "policy"], sort=True):
        row = dict(zip(["mix", "lam", "eta", "policy"], k))
        row["n_seeds"] = len(g)
        for c in cols:
            row[c] = float(g[c].mean())
            if c in ("mean_lat", "p95", "p99", "util_mean", "ratio_mean", "ratio_p95",
                     "ratio_mean_cens", "ratio_p95_cens"):
                row[c + "_ci95"] = ci95(g[c].to_numpy())
        out.append(row)
    return pd.DataFrame(out)
