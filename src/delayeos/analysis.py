"""Evaluation of the pre-registered predictions (a)-(d) and the GO rule from a runs_summary table.

Input: DataFrame with one row per run (columns of train.summarize): optimizer, beta1, mode, batch, eta, seed,
diverged, final_loss, med_eta_SP_last, max_eta_SP_all, ...  Diverged runs count as infinite loss and as
"not in band".  All thresholds come from the config's `predictions` section.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def sel(df: pd.DataFrame, optimizer: str, mode: str, batch: int, beta1: Optional[float] = None) -> pd.DataFrame:
    m = (df.optimizer == optimizer) & (df["mode"] == mode) & (df.batch == batch)
    if beta1 is not None and optimizer == "adam":
        m &= np.isclose(df.beta1, beta1)
    return df[m]


def loss_by_eta(d: pd.DataFrame) -> pd.Series:
    """Mean final loss over seeds per eta; a diverged seed makes the entry inf."""
    v = d.assign(L=np.where(d.diverged == 1, np.inf, d.final_loss))
    return v.groupby("eta").L.mean()


def sp_by_eta(d: pd.DataFrame, col: str = "med_eta_SP_last") -> pd.Series:
    """Median over seeds of the per-seed median eta*S_P (last-1000-step window) per eta."""
    return d.groupby("eta")[col].median()


def band_check(d: pd.DataFrame, band: list[float], min_frac: float, min_etas: int) -> dict:
    """Per eta: seeds whose per-seed median eta*S_P lies in `band`; pass if >= min_frac of seeds at >= min_etas etas."""
    per_eta = {}
    for eta, g in d.groupby("eta"):
        vals = np.where(g.diverged == 1, np.nan, g.med_eta_SP_last)
        n_in = int(np.sum((vals >= band[0]) & (vals <= band[1])))
        need = math.ceil(min_frac * len(g) - 1e-6)
        per_eta[float(eta)] = {"per_seed": [None if np.isnan(v) else round(float(v), 4) for v in vals],
                               "n_in_band": n_in, "n_seeds": int(len(g)), "ok": n_in >= need}
    n_ok = sum(v["ok"] for v in per_eta.values())
    return {"band": band, "per_eta": per_eta, "n_eta_ok": n_ok, "passed": n_ok >= min_etas}


def eval_a(df: pd.DataFrame, p: dict) -> dict:
    pa = p["a"]
    B, b1, b1x = pa["batch"], pa["beta1_main"], pa["beta1_extra"]
    delay = band_check(sel(df, "adam", "delay", B, b1), pa["delay_band"], pa["min_seed_frac"], pa["min_etas"])
    ef = band_check(sel(df, "adam", "ef", B, b1), pa["ef_band"], pa["min_seed_frac"], pa["min_etas"])
    delay99 = band_check(sel(df, "adam", "delay", B, b1x), pa["delay_band"], pa["min_seed_frac"], pa["min_etas"])
    s = sel(df, "adam", "sync", B, b1)
    sync = {"max_over_all_runs_and_times": float(np.nanmax(s.max_eta_SP_all)),
            "per_run_max": {f"eta={r.eta:g},seed={r.seed}": round(float(r.max_eta_SP_all), 3) for r in s.itertuples()},
            "median_last1000_by_eta": {f"{k:g}": round(float(v), 3) for k, v in sp_by_eta(s).items()},
            "reached_gate": bool(np.nanmax(s.max_eta_SP_all) > pa["sync_reach"]), "gate": pa["sync_reach"]}
    all_pass = delay["passed"] and ef["passed"] and delay99["passed"]
    verdict = "INCONCLUSIVE (sync never exceeded gate)" if not sync["reached_gate"] else ("PASS" if all_pass else "FAIL")
    return {"delay_beta0.9": delay, "ef_beta0.9": ef, "delay_beta0.99": delay99, "sync_beta0.9": sync,
            "all_three_bands_pass": all_pass, "verdict": verdict}


def penalty_table(df: pd.DataFrame, optimizer: str, batch: int, beta1: Optional[float]) -> dict:
    """Mean final losses, matched-eta and tuned delay penalties (L_delay / L_sync - 1) and preconditioned sharpness.

    penalty_at_sync_best_eta: both modes at the sync-best eta.  penalty_tuned: each mode at its own best eta."""
    sync, delay = sel(df, optimizer, "sync", batch, beta1), sel(df, optimizer, "delay", batch, beta1)
    ls, ld = loss_by_eta(sync), loss_by_eta(delay)
    etas = sorted(ls.index)
    best_s, best_d = ls.idxmin(), ld.idxmin()
    sp_s = sp_by_eta(sync) if optimizer == "adam" else pd.Series(np.nan, index=ls.index)
    sp_d = sp_by_eta(delay) if optimizer == "adam" else pd.Series(np.nan, index=ls.index)
    out = {
        "etas": [float(e) for e in etas],
        "loss_sync": {f"{e:g}": float(ls[e]) for e in etas}, "loss_delay": {f"{e:g}": float(ld[e]) for e in etas},
        "penalty_matched": {f"{e:g}": float(ld[e] / ls[e] - 1.0) for e in etas},
        "best_eta_sync": float(best_s), "best_eta_delay": float(best_d),
        "penalty_at_sync_best_eta": float(ld[best_s] / ls[best_s] - 1.0),
        "penalty_tuned": float(ld.min() / ls.min() - 1.0),
        "etaSP_sync_at_best_eta": float(sp_s[best_s]), "etaSP_delay_at_sync_best_eta": float(sp_d[best_s]),
        "etaSP_delay_at_delay_best_eta": float(sp_d[best_d]),
        "n_diverged_sync": int(sync.diverged.sum()), "n_diverged_delay": int(delay.diverged.sum()),
    }
    return out


def eval_b(df: pd.DataFrame, p: dict) -> dict:
    pb, pa = p["b"], p["a"]
    out: dict = {}
    for b1 in (pa["beta1_main"], pa["beta1_extra"]):
        t = penalty_table(df, "adam", pb["batch"], b1)
        sp, pen = t["etaSP_sync_at_best_eta"], t["penalty_at_sync_best_eta"]
        d_sp = t["etaSP_delay_at_sync_best_eta"]
        t["downgrade_not_stability_effect"] = bool(sp <= pb["sync_sp_max"] and pen >= pb["penalty_min"])
        t["downgrade_using_tuned_penalty"] = bool(sp <= pb["sync_sp_max"] and t["penalty_tuned"] >= pb["penalty_min"])
        t["go_clause"] = bool(sp >= pb["go_sync_sp_min"] and pa["delay_band"][0] <= d_sp <= pa["delay_band"][1]
                              and pen >= pb["penalty_min"])
        out[f"beta{b1}"] = t
    return out


def eval_c(df: pd.DataFrame, p: dict) -> dict:
    pa = p["a"]
    out: dict = {}
    for B in sorted(df.batch.unique(), reverse=True):
        t9 = penalty_table(df, "adam", int(B), pa["beta1_main"])
        t99 = penalty_table(df, "adam", int(B), pa["beta1_extra"])
        etas = t9["etas"]
        smaller = [bool(t99["penalty_matched"][f"{e:g}"] < t9["penalty_matched"][f"{e:g}"]) for e in etas]
        out[f"batch{int(B)}"] = {
            "penalty_matched_beta0.9": t9["penalty_matched"], "penalty_matched_beta0.99": t99["penalty_matched"],
            "penalty_tuned_beta0.9": t9["penalty_tuned"], "penalty_tuned_beta0.99": t99["penalty_tuned"],
            "n_eta_with_smaller_penalty_at_0.99": int(sum(smaller)), "n_eta": len(etas),
            "supported_tuned": bool(t99["penalty_tuned"] < t9["penalty_tuned"]),
            "supported_matched_majority": bool(sum(smaller) > len(etas) / 2)}
    return out


def eval_d(df: pd.DataFrame, p: dict) -> dict:
    pa = p["a"]
    out: dict = {}
    for B in sorted(df.batch.unique(), reverse=True):
        a9 = penalty_table(df, "adam", int(B), pa["beta1_main"])
        a99 = penalty_table(df, "adam", int(B), pa["beta1_extra"])
        mu = penalty_table(df, "muon", int(B), None)
        out[f"batch{int(B)}"] = {
            "adam0.9_penalty_tuned": a9["penalty_tuned"], "adam0.99_penalty_tuned": a99["penalty_tuned"],
            "muon_penalty_tuned": mu["penalty_tuned"], "muon_penalty_matched": mu["penalty_matched"],
            "muon_best_eta_sync": mu["best_eta_sync"], "muon_best_eta_delay": mu["best_eta_delay"],
            "muon_loss_sync": mu["loss_sync"], "muon_loss_delay": mu["loss_delay"],
            "negative_muon_ge_adam0.9": bool(mu["penalty_tuned"] >= a9["penalty_tuned"]),
            "negative_muon_ge_adam0.99": bool(mu["penalty_tuned"] >= a99["penalty_tuned"])}
    return out


def main_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    d = df.assign(beta1=df.beta1.fillna(-1.0))
    for (opt, b1, mode, batch, eta), g in d.groupby(["optimizer", "beta1", "mode", "batch", "eta"], sort=False):
        g = g.sort_values("seed")
        L = np.where(g.diverged == 1, np.inf, g.final_loss)
        rows.append({"optimizer": opt, "beta1": b1 if b1 >= 0 else np.nan, "mode": mode, "batch": batch, "eta": eta,
                     "etaSP_per_seed": "/".join("nan" if np.isnan(v) else f"{v:.3g}" for v in g.med_eta_SP_last),
                     "etaS_per_seed": "/".join("nan" if np.isnan(v) else f"{v:.3g}" for v in g.med_eta_S_last),
                     "etaSP_median_over_seeds": float(np.nanmedian(g.med_eta_SP_last)) if g.med_eta_SP_last.notna().any() else np.nan,
                     "final_loss_per_seed": "/".join(f"{v:.3g}" for v in L), "final_loss_mean": float(np.mean(L)),
                     "n_diverged": int(g.diverged.sum())})
    return pd.DataFrame(rows)


def go_decision(a: dict, b: dict) -> dict:
    b_main = b["beta0.9"]
    a_ok = a["delay_beta0.9"]["passed"] and a["ef_beta0.9"]["passed"] and a["sync_beta0.9"]["reached_gate"]
    go = bool(a_ok and b_main["go_clause"])
    return {"a_delayed_and_ef_pass_and_sync_reaches_gate": bool(a_ok), "b_go_clause_beta0.9": b_main["go_clause"],
            "GO": go}
