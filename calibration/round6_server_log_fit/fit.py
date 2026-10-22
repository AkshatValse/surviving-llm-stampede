"""Fit the simulator's iteration-time model to clean SGLang per-iteration times.

Usage: python fit.py <obs_prefix> <out_dir> <seed> <n_boot>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

NORM = 8192.0
SIM = dict(iter_fixed_s=0.002, iter_floor_s=0.0095, per_token_s=0.000084, decode_attn_s=0.00071, prefill_attn_s=3.5e-9)


# ----------------------------------------------------------------------------- data
def load(prefix: str):
    D = pd.read_pickle(prefix + "_decode.pkl")
    D = D[D.growth_ok].copy()
    P = pd.read_pickle(prefix + "_prefill.pkl")
    Pk = P[P.clean & np.isfinite(P.attn_mid)].copy()
    for df in (D, Pk):
        t = pd.to_datetime(df.ts)
        df["block"] = df.job.astype(str) + "_" + df.epoch.astype(str) + "_" + (t.astype("int64") // (120 * 10**9)).astype(str)
    return D, Pk, P


# ----------------------------------------------------------------------------- models
def wls(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Least squares on relative residuals: minimise sum ((X b - y)/y)^2."""
    w = 1.0 / y
    b, *_ = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)
    return b


def dec_lin_design(D):
    return np.column_stack([np.ones(len(D)), D.running.values, D.sumctx.values / NORM])


def pre_design(P, conv="mid"):
    A = P.attn_mid.values if conv == "mid" else P.attn_end.values
    return np.column_stack([np.ones(len(P)), P.X.values, A])


def simform_pred(theta, R_or_X, ctx_term, attn_term, kind):
    a, f, b, c, e = theta
    if kind == "D":
        return a + np.maximum(f, b * R_or_X) + c * ctx_term
    return a + np.maximum(f, b * R_or_X) + e * attn_term


def joint_simform(D, P, conv="mid", x0=None):
    """Joint fit of (iter_fixed, iter_floor, per_token, decode_attn, prefill_attn) in the simulator's exact form,
    applied to separate P and D iterations (SGLang runs them separately). Relative residuals, each set weighted by
    1/sqrt(n_set) so both sets count equally."""
    yD, yP = D.tau.values, P.gap.values
    RD, cD = D.running.values.astype(float), D.sumctx.values / NORM
    XP = P.X.values.astype(float)
    AP = P.attn_mid.values if conv == "mid" else P.attn_end.values
    wD, wP = 1 / np.sqrt(len(yD)), 1 / np.sqrt(len(yP))
    sc = np.array([1e-3, 1e-3, 1e-5, 1e-4, 1e-9])

    def res(z):
        th = z * sc
        rD = (simform_pred(th, RD, cD, None, "D") - yD) / yD * wD
        rP = (simform_pred(th, XP, None, AP, "P") - yP) / yP * wP
        return np.concatenate([rD, rP])

    if x0 is None:
        x0 = np.array([5.0, 5.0, 7.0, 3.0, 2.0])
    r = least_squares(res, x0, bounds=(np.zeros(5), np.full(5, np.inf)), x_scale=1.0)
    return r.x * sc


def dec_simform_free(D, x0=(1.0, 9.0, 7.0, 3.0)):
    """Decode-only sim form with its own per-seq slope: a + max(f, b R) + c ctx/8192."""
    y, R, c = D.tau.values, D.running.values.astype(float), D.sumctx.values / NORM
    sc = np.array([1e-3, 1e-3, 1e-5, 1e-4])

    def res(z):
        a, f, b, cc = z * sc
        return (a + np.maximum(f, b * R) + cc * c - y) / y

    r = least_squares(res, np.array(x0), bounds=(np.zeros(4), np.full(4, np.inf)))
    return r.x * sc


# ----------------------------------------------------------------------------- metrics
def metrics(y, yhat):
    rel = (yhat - y) / y
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return dict(n=int(len(y)), r2=float(1 - ss_res / ss_tot), med_abs_rel=float(np.median(np.abs(rel))),
                p95_abs_rel=float(np.quantile(np.abs(rel), 0.95)), mean_rel=float(np.mean(rel)))


def sim_pred_D(D, p=SIM):
    return p["iter_fixed_s"] + np.maximum(p["iter_floor_s"], p["per_token_s"] * D.running.values) + \
        p["decode_attn_s"] * D.sumctx.values / NORM


def sim_pred_P(P, p=SIM, conv="end"):
    A = P.attn_end.values if conv == "end" else P.attn_mid.values
    return p["iter_fixed_s"] + np.maximum(p["iter_floor_s"], p["per_token_s"] * P.X.values) + p["prefill_attn_s"] * A


# ----------------------------------------------------------------------------- bootstrap
def cluster_boot(df_list, fn, B, rng):
    """Resample clusters (column 'block') with replacement, independently per dataset."""
    groups = [{k: v.index.values for k, v in df.groupby("block")} for df in df_list]
    keys = [np.array(list(g.keys())) for g in groups]
    out = []
    for _ in range(B):
        samp = []
        for df, g, k in zip(df_list, groups, keys):
            pick = rng.choice(k, size=len(k), replace=True)
            idx = np.concatenate([g[x] for x in pick])
            samp.append(df.loc[idx])
        out.append(fn(*samp))
    return np.array(out)


def ci(a):
    return [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]


def main(prefix: str, out_dir: str, seed: int, B: int) -> None:
    out = Path(out_dir)
    rng = np.random.default_rng(seed)
    D, P, Pall = load(prefix)
    res = dict(seed=seed, n_boot=B, n_decode=len(D), n_prefill=len(P),
               decode_blocks=int(D.block.nunique()), prefill_blocks=int(P.block.nunique()))

    # --- decode, free linear
    bD = wls(dec_lin_design(D), D.tau.values)
    bootD = cluster_boot([D], lambda d: wls(dec_lin_design(d), d.tau.values), B, rng)
    res["decode_linear"] = dict(names=["a_s", "per_seq_s", "per_ctx8192_s"], est=bD.tolist(),
                                ci=[ci(bootD[:, i]) for i in range(3)],
                                metrics=metrics(D.tau.values, dec_lin_design(D) @ bD))
    # --- decode, sim form with free slope (identifiability check of floor vs fixed)
    th = dec_simform_free(D)
    predS = th[0] + np.maximum(th[1], th[2] * D.running.values) + th[3] * D.sumctx.values / NORM
    res["decode_simform_free"] = dict(names=["iter_fixed_s", "iter_floor_s", "per_seq_s", "decode_attn_s"],
                                      est=th.tolist(), metrics=metrics(D.tau.values, predS),
                                      knee_R=float(th[1] / th[2]) if th[2] > 0 else None)

    # --- prefill, linear, both attention conventions
    for conv in ("mid", "end"):
        bP = wls(pre_design(P, conv), P.gap.values)
        bootP = cluster_boot([P], lambda d, c=conv: wls(pre_design(d, c), d.gap.values), B, rng)
        res[f"prefill_linear_{conv}"] = dict(names=["a_s", "per_token_s", "prefill_attn_s"], est=bP.tolist(),
                                             ci=[ci(bootP[:, i]) for i in range(3)],
                                             metrics=metrics(P.gap.values, pre_design(P, conv) @ bP))
    # --- joint simulator-form fit (the calibration), both conventions
    for conv in ("mid", "end"):
        th = joint_simform(D, P, conv)
        bootJ = cluster_boot([D, P], lambda d, p, c=conv, t0=th: joint_simform(d, p, c, x0=t0 / np.array([1e-3, 1e-3, 1e-5, 1e-4, 1e-9])), B, rng)
        pD = simform_pred(th, D.running.values, D.sumctx.values / NORM, None, "D")
        AP = P.attn_mid.values if conv == "mid" else P.attn_end.values
        pP = simform_pred(th, P.X.values, None, AP, "P")
        res[f"joint_simform_{conv}"] = dict(
            names=["iter_fixed_s", "iter_floor_s", "per_token_s", "decode_attn_s", "prefill_attn_s"],
            est=th.tolist(), ci=[ci(bootJ[:, i]) for i in range(5)],
            ci_fixed_plus_floor=ci(bootJ[:, 0] + bootJ[:, 1]),
            metrics_decode=metrics(D.tau.values, pD), metrics_prefill=metrics(P.gap.values, pP))
    # --- simulator's assumed values on the same observations
    res["sim_assumed"] = dict(params=SIM, metrics_decode=metrics(D.tau.values, sim_pred_D(D)),
                              metrics_prefill_end=metrics(P.gap.values, sim_pred_P(P, conv="end")),
                              metrics_prefill_mid=metrics(P.gap.values, sim_pred_P(P, conv="mid")))
    (out / "fit_results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "names"}) for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
