"""Statistics, fits and empirical quantile tables from the normalised trace CSVs (output of parse_tracelab.py / parse_mini_swe.py).

  python -I scripts/traces/analyze.py KIND NORMDIR OUTDIR --config configs/traces_analysis.yaml
      KIND: tracelab | mini

Writes OUTDIR/summary.json (everything), OUTDIR/quantiles.csv (1st..99th percentile of every tool-time series),
OUTDIR/headline.csv (one row per series x group: n, mean, median, p90, p99, CV, lognormal and mixture fits, KS distances),
OUTDIR/tokens.csv (tokens and turn statistics) and OUTDIR/tables.md (the same, readable).

Nothing here depends on the simulator. The only simulator-facing outputs are the parameters used by make_configs.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # our own scripts/traces, not the data directory
from common import (dist_summary, fit_lognormal, fit_lognormal_mixture, geometric_mean_param, ks_vs_exponential,  # noqa: E402
                    lognormal_bic, quantile_table)

# set from configs/traces_analysis.yaml in main(): cap for the 'capped' statistics, floor for the log-scale fits (durations below it are
# raised to it), and the reference exponential mean (the simulator's current Exp(5 s))
CAP_S = 600.0
EXP_REF_MEAN_S = 5.0
FLOOR_S = 0.01


def series_stats(x: np.ndarray, floor: float, seed: int, fit: bool = True) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x) & (x >= 0)]
    out = {"raw": dist_summary(x)}
    xc = np.minimum(x, CAP_S)
    out["capped600"] = dist_summary(xc)
    out["frac_gt_cap"] = float(np.mean(x > CAP_S))
    out["frac_lt_1s"] = float(np.mean(x < 1.0))
    out["frac_gt_60s"] = float(np.mean(x > 60.0))
    out["time_share_gt_60s"] = float(x[x > 60.0].sum() / x.sum()) if x.sum() > 0 else float("nan")
    out["quantiles_1_99"] = quantile_table(x)
    out["ks_exp5"] = ks_vs_exponential(x, EXP_REF_MEAN_S)
    out["ks_exp_meanmatched"] = ks_vs_exponential(x, float(x.mean()))
    out["ks_exp_meanmatched_capped"] = ks_vs_exponential(xc, float(xc.mean()))
    out["atom_frac_lt_floor"] = float(np.mean(x < floor))
    if fit and x.size >= 200:
        # (a) the whole sample, durations below the floor raised to the floor (an atom at the floor remains: ~20% of tool calls
        #     finish in under 1 ms, so a continuous model cannot get KS below about half of that atom's mass)
        out["lognormal"] = fit_lognormal(x, floor)
        out["lognormal_capped600"] = fit_lognormal(xc, floor)
        out["mixture2"] = fit_lognormal_mixture(x, floor, seed=seed, max_n=100_000, iters=300)
        out["mixture2_capped600"] = fit_lognormal_mixture(xc, floor, seed=seed, max_n=100_000, iters=300)
        out["bic_lognormal_sub"] = lognormal_bic(x, floor, max_n=100_000, seed=seed)
        # (b) the positive part (durations >= floor), i.e. conditional on not being an instantaneous call; atom mass reported above
        xp, xpc = x[x >= floor], xc[xc >= floor]
        out["lognormal_pos"] = fit_lognormal(xp, floor)
        out["lognormal_pos_capped600"] = fit_lognormal(xpc, floor)
        out["mixture2_pos"] = fit_lognormal_mixture(xp, floor, seed=seed, max_n=100_000, iters=300)
        out["mixture2_pos_capped600"] = fit_lognormal_mixture(xpc, floor, seed=seed, max_n=100_000, iters=300)
        out["bic_lognormal_pos_sub"] = lognormal_bic(xp, floor, max_n=100_000, seed=seed)
        out["n_pos"] = int(xp.size)
    return out


def token_stats(rounds: pd.DataFrame, eps: pd.DataFrame, sess: pd.DataFrame | None) -> dict:
    out = {}
    out["input_total_all_rounds"] = dist_summary(rounds["input_total"])
    out["output_tokens_per_round"] = dist_summary(rounds["output_tokens"])
    d = rounds["delta_ctx"].dropna()
    out["delta_ctx_negative_frac"] = float((d < 0).mean()) if len(d) else float("nan")
    out["delta_ctx_nonneg"] = dist_summary(d[d >= 0])
    if "d_in" in rounds:
        out["d_in_all"] = dist_summary(rounds["d_in"].dropna())
    first = rounds[rounds["pos_in_episode"] == 0]["input_total"]
    out["first_round_input_total_per_episode"] = dist_summary(first)
    out["first_input_total_per_session"] = dist_summary((sess if sess is not None else eps)["first_input_total"])
    return out


def turns_stats(eps: pd.DataFrame, sess: pd.DataFrame | None, tag: str, max_turns: int = 60) -> dict:
    out = {}
    T = eps["n_rounds"].astype(float)
    out["episode_rounds_all"] = dist_summary(T)
    ag = eps[eps["n_tool_rounds"] > 0]
    Ta = ag["n_rounds"].astype(float)
    out["episode_rounds_agentic"] = dist_summary(Ta)
    out["n_episodes"] = int(len(eps))
    out["n_agentic_episodes"] = int(len(ag))
    if sess is not None:
        out["session_rounds"] = dist_summary(sess["n_rounds"].astype(float))
        out["session_episodes"] = dist_summary(sess["n_episodes"].astype(float))
        out["n_sessions"] = int(len(sess))
    # geometric parameter matching the mean of the capped number of turns (WorkloadParams convention) for two caps
    fits = {}
    for M in (max_turns, int(np.ceil(np.percentile(Ta, 99)))):
        capped = np.minimum(Ta.to_numpy(), M)
        fits[str(M)] = {"max_turns": M, "target_mean_capped": float(capped.mean()), "mean_turns_geometric": geometric_mean_param(float(capped.mean()), M)}
    out["geometric_match_agentic"] = fits
    return out


def run_tracelab(norm: str, seed: int, max_turns: int) -> dict:
    calls = pd.read_csv(os.path.join(norm, "calls.csv"))
    rounds = pd.read_csv(os.path.join(norm, "rounds.csv"))
    eps = pd.read_csv(os.path.join(norm, "episodes.csv"))
    sess = pd.read_csv(os.path.join(norm, "sessions.csv"))
    floor = FLOOR_S
    res = {"kind": "tracelab", "n_calls": int(len(calls)), "n_rounds": int(len(rounds)), "floor_s": floor}
    nohuman = calls[calls.cls != "human"]
    execonly = calls[~calls.cls.isin(["human", "deleg", "poll"])]
    res["class_counts"] = {f"{p}:{c}": int(n) for (p, c), n in calls.groupby(["provider", "cls"]).size().items()}
    series = {}
    for prov in ("all", "claude", "codex"):
        sel = (lambda df: df) if prov == "all" else (lambda df, p=prov: df[df.provider == p])
        series[f"call_best_nohuman|{prov}"] = sel(nohuman)["best_s"].dropna().to_numpy()
        series[f"call_wall_nohuman|{prov}"] = sel(nohuman)["wall_s"].dropna().to_numpy()
        series[f"call_internal_nohuman|{prov}"] = sel(nohuman)["internal_s"].dropna().to_numpy()
        series[f"call_best_exec_only|{prov}"] = sel(execonly)["best_s"].dropna().to_numpy()
        series[f"call_best_shell|{prov}"] = sel(calls[calls.cls == "shell"])["best_s"].dropna().to_numpy()
        series[f"call_best_all_logged|{prov}"] = sel(calls)["best_s"].dropna().to_numpy()
        rt = rounds[(rounds.n_tools > 0) & (~rounds.classes.fillna("").str.contains("human"))]
        series[f"round_z_nohuman|{prov}"] = sel(rt)["z_round_s"].dropna().to_numpy()
        series[f"round_gap_next_nohuman|{prov}"] = sel(rt)["gap_next_s"].dropna().to_numpy()
    # per tool class (all providers), best_s
    for cls in ("shell", "file", "web", "poll", "deleg", "book", "other", "human"):
        series[f"class_{cls}|all"] = calls[calls.cls == cls]["best_s"].dropna().to_numpy()
    headline = {"call_best_nohuman|all", "call_best_nohuman|claude", "call_best_nohuman|codex", "call_best_exec_only|all", "call_best_shell|all",
                "round_z_nohuman|all", "call_best_all_logged|all", "call_wall_nohuman|all", "call_internal_nohuman|codex"}
    res["series"] = {}
    for name, x in series.items():
        res["series"][name] = series_stats(x, floor, seed, fit=name in headline)
    # per-tool breakdown for the dominant tools
    top = calls.groupby(["provider", "tool"]).size().sort_values(ascending=False).head(14).index
    res["per_tool"] = {f"{p}:{t}": dist_summary(calls[(calls.provider == p) & (calls.tool == t)]["best_s"]) for p, t in top}
    # wall vs internal on the rows where both exist
    both = calls.dropna(subset=["wall_s", "internal_s"])
    res["wall_minus_internal"] = {p: dist_summary((g.wall_s - g.internal_s)) for p, g in both.groupby("provider")}
    res["tokens"] = {}
    res["turns"] = {}
    for prov in ("all", "claude", "codex"):
        r = rounds if prov == "all" else rounds[rounds.provider == prov]
        e = eps if prov == "all" else eps[eps.provider == prov]
        s = sess if prov == "all" else sess[sess.provider == prov]
        res["tokens"][prov] = token_stats(r, e, s)
        res["turns"][prov] = turns_stats(e, s, prov, max_turns)
    # human response time between episodes (context only)
    res["human_gap_before_episode_s"] = dist_summary(eps["human_gap_before_s"].dropna())
    # tool-appended tokens vs result chars, to translate chars to tokens
    cc = calls.dropna(subset=["result_chars"])
    res["result_chars_per_call"] = dist_summary(cc["result_chars"])
    return res


def run_mini(norm: str, seed: int, max_turns: int) -> dict:
    calls = pd.read_csv(os.path.join(norm, "calls.csv"))
    rounds = pd.read_csv(os.path.join(norm, "rounds.csv"))
    eps = pd.read_csv(os.path.join(norm, "episodes.csv"))
    floor = FLOOR_S
    res = {"kind": "mini", "n_calls": int(len(calls)), "n_rounds": int(len(rounds)), "floor_s": floor}
    models = sorted(calls.model.unique())
    res["models"] = models
    series = {}
    for m in ["all"] + models:
        c = calls if m == "all" else calls[calls.model == m]
        series[f"phase_wall|{m}"] = c["wall_s"].dropna().to_numpy()
        series[f"phase_wall_uncensored|{m}"] = c[c.censored == 0]["wall_s"].dropna().to_numpy()
        series[f"phase_wall_single_cmd|{m}"] = c[c.n_parallel == 1]["wall_s"].dropna().to_numpy()
        r = rounds if m == "all" else rounds[rounds.model == m]
        series[f"llm_latency|{m}"] = r["llm_s"].dropna().to_numpy()
    headline = {"phase_wall|all", "phase_wall_uncensored|all", "phase_wall_single_cmd|all"}
    res["series"] = {}
    for name, x in series.items():
        res["series"][name] = series_stats(x, floor, seed, fit=name in headline)
        res["series"][name]["censored_60s_frac"] = float(np.mean(x >= 59.9)) if name.startswith("phase_wall|") else None
    res["tokens"] = {}
    res["turns"] = {}
    for m in ["all"] + models:
        r = rounds if m == "all" else rounds[rounds.model == m]
        e = eps if m == "all" else eps[eps.model == m] if "model" in eps else eps
        if m != "all":
            e = eps[eps.session.str.startswith(m + ":")]
        res["tokens"][m] = token_stats(r, e, None)
        res["turns"][m] = turns_stats(e, None, m, max_turns)
    res["exit_status"] = {k: int(v) for k, v in eps["exit_status"].value_counts().items()}
    res["noop_steps_total"] = int(eps["n_noop"].sum())
    res["timeouts_total"] = int(eps["n_timeouts"].sum())
    res["trajectory_wall_s"] = dist_summary(eps["wall_s"].dropna())
    res["total_tool_s_per_trajectory"] = dist_summary(eps["total_tool_s"].dropna())
    return res


def write_outputs(res: dict, out: str) -> None:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=False)
    qrows = {name: s["quantiles_1_99"] for name, s in res["series"].items() if "quantiles_1_99" in s}
    qdf = pd.DataFrame(qrows, index=np.arange(1, 100))
    qdf.index.name = "percentile"
    qdf.round(5).to_csv(os.path.join(out, "quantiles.csv"))
    rows = []
    for name, s in res["series"].items():
        r = s["raw"]
        if r.get("n", 0) == 0:
            continue
        c = s["capped600"]
        row = {"series": name, "n": r["n"], "mean": r["mean"], "median": r["median"], "p90": r["p90"], "p99": r["p99"], "cv": r["cv"],
               "mean_cap600": c["mean"], "cv_cap600": c["cv"], "frac_gt_cap": s["frac_gt_cap"], "frac_lt_1s": s["frac_lt_1s"],
               "frac_gt_60s": s["frac_gt_60s"], "time_share_gt_60s": s["time_share_gt_60s"],
               "ks_exp5": s["ks_exp5"], "ks_exp_meanmatched_cap600": s["ks_exp_meanmatched_capped"]}
        if "lognormal" in s:
            row["atom_frac_lt_floor"] = s["atom_frac_lt_floor"]
            for tag in ("", "_pos"):
                ln, lnc = s["lognormal" + tag], s["lognormal" + tag + "_capped600"]
                mx, mxc = s["mixture2" + tag], s["mixture2" + tag + "_capped600"]
                row.update({f"ln{tag}_mu": ln["mu"], f"ln{tag}_sigma": ln["sigma"], f"ln{tag}_ks": ln["ks"],
                            f"ln{tag}_cap_mu": lnc["mu"], f"ln{tag}_cap_sigma": lnc["sigma"], f"ln{tag}_cap_ks": lnc["ks"],
                            f"mix{tag}_ks": mx["ks"], f"mix{tag}_cap_ks": mxc["ks"],
                            f"mix{tag}_cap_w1": mxc["components"][0]["weight"], f"mix{tag}_cap_med1": mxc["components"][0]["median_s"],
                            f"mix{tag}_cap_sig1": mxc["components"][0]["sigma"],
                            f"mix{tag}_cap_w2": mxc["components"][1]["weight"], f"mix{tag}_cap_med2": mxc["components"][1]["median_s"],
                            f"mix{tag}_cap_sig2": mxc["components"][1]["sigma"],
                            f"mix{tag}_cap_mean": mxc["mean_implied"], f"mix{tag}_cap_cv": mxc["cv_implied"]})
        rows.append(row)
    pd.DataFrame(rows).to_csv(os.path.join(out, "headline.csv"), index=False, float_format="%.6g")
    trows = []
    for grp, tk in res["tokens"].items():
        tn = res["turns"][grp]
        for k, v in tk.items():
            if isinstance(v, dict) and v.get("n"):
                trows.append({"group": grp, "quantity": k, **{kk: v[kk] for kk in ("n", "mean", "mean_w999", "median", "p90", "p99", "cv") if kk in v}})
        for k, v in tn.items():
            if isinstance(v, dict) and v.get("n"):
                trows.append({"group": grp, "quantity": k, **{kk: v[kk] for kk in ("n", "mean", "mean_w999", "median", "p90", "p99", "cv") if kk in v}})
    pd.DataFrame(trows).to_csv(os.path.join(out, "tokens.csv"), index=False, float_format="%.6g")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["tracelab", "mini"])
    ap.add_argument("norm")
    ap.add_argument("out")
    ap.add_argument("--config", default="configs/traces_analysis.yaml")
    a = ap.parse_args()
    global CAP_S, EXP_REF_MEAN_S, FLOOR_S
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["analysis"]
    CAP_S, EXP_REF_MEAN_S, FLOOR_S = float(cfg["cap_s"]), float(cfg["exp_ref_mean_s"]), float(cfg["floor_s"])
    a.seed = int(cfg["seed"])
    a.max_turns = int(cfg["max_turns_workload_of_record"])
    res = run_tracelab(a.norm, a.seed, a.max_turns) if a.kind == "tracelab" else run_mini(a.norm, a.seed, a.max_turns)
    res["analysis"] = {"seed": a.seed, "cap_s": CAP_S, "floor_s": FLOOR_S, "exp_ref_mean_s": EXP_REF_MEAN_S, "config": a.config}
    write_outputs(res, a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
