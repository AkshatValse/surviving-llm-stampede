"""Trap criterion (a) on the SIMULATOR's own traps (review of 2026-10-21, findings 1-3): which completion-rate estimator
stays within +-rate_tolerance of its all-miss reference on runs the simulator calls trapped; the transient bias of the
Stage-C closed-curve window; and how often the NO-BURST arm escapes spontaneously. Analysis of recorded simulator output
(see configs/agentload_trap_sim_traces.yaml); writes results/agentload_trap_sim_traces/<ts>/ with per_run.csv,
summary_by_lambda.csv, noburst_escapes.csv, transient_bias.csv, summary.json, config.yaml, meta.json (inputs sha256).
    /opt/anaconda3/bin/python experiments/agentload_trap_sim_traces.py [--config FILE] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta  # noqa: E402
from analysis.params import load_params  # noqa: E402

CFG = REPO / "configs" / "agentload_trap_sim_traces.yaml"
ANALYSIS = REPO / "configs" / "agentload_analysis.yaml"
WIN_COLS = ["policy", "variant", "seed", "run_id", "t_start", "hit_rate", "sessions_per_s", "turns_per_s", "prefill_tok_per_s"]


def effective_mean_turns(mean_turns: float, max_turns: int) -> float:
    p = 1.0 / mean_turns
    return (1.0 - (1.0 - p) ** max_turns) / p


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- references from the simulator's E0 (cache-off closed population)
def e0_references(windows: pd.DataFrame, runs: pd.DataFrame, population: int, warmup_s: float) -> Dict[str, float]:
    """Cache-off closed-population references: completed sessions/s, turns/s and prefill tokens/s after the warmup."""
    ids = set(runs[(runs["exp"] == "e0_miss") & (runs["population"] == population)]["run_id"])
    w = windows[(windows["exp"] == "e0_miss") & (windows["run_id"].isin(ids)) & (windows["t_start"] >= warmup_s)]
    if len(w) == 0:
        raise ValueError(f"no e0_miss windows for population {population} after {warmup_s} s")
    return {"sessions_per_s": float(w["sessions_per_s"].mean()), "turns_per_s": float(w["turns_per_s"].mean()),
            "prefill_tok_per_s": float(w["prefill_tok_per_s"].mean()), "n_windows": int(len(w)), "n_runs": len(ids)}


# ---------------------------------------------------------------- trapped runs of the burst_info experiment
def parse_variant(v: str) -> Tuple[float, int]:
    """'lam=2.0|burst=100' -> (2.0, 100)."""
    parts = dict(kv.split("=") for kv in v.split("|"))
    return float(parts["lam"]), int(parts["burst"])


def window_rates(win: pd.DataFrame, t0: float, t1: float, w: float) -> Optional[Dict[str, float]]:
    """Mean rates over the whole windows with t_start in [t0, t1); None unless every window of the span is present."""
    sel = win[(win["t_start"] >= t0 - 1e-9) & (win["t_start"] < t1 - 1e-9)]
    if len(sel) != int(round((t1 - t0) / w)):
        return None
    return {"sessions_per_s": float(sel["sessions_per_s"].mean()), "turns_per_s": float(sel["turns_per_s"].mean()),
            "prefill_tok_per_s": float(sel["prefill_tok_per_s"].mean()), "hit_rate_max": float(sel["hit_rate"].max())}


def trapped_run_rows(windows: pd.DataFrame, runs: pd.DataFrame, refs: Dict[str, float], lam_miss: float, t_burst: float,
                     eval_spans: Sequence[Sequence[float]], a: Dict[str, Any], tol: float, slope_frac: float) -> pd.DataFrame:
    """One row per (trapped FCFS run, evaluation span): rate / reference ratios and whether (a) fires per estimator."""
    et = effective_mean_turns(float(a["mean_turns"]), int(a["max_turns"]))
    w_s = float(a["window_s"])
    rows: List[Dict[str, Any]] = []
    rr = runs.set_index("run_id")
    pol = windows[windows["policy"] == a["policy"]]
    for run_id, g in pol.groupby("run_id"):
        lam_mult, burst = parse_variant(str(g["variant"].iloc[0]))
        tail_hit = float(rr.loc[run_id, "tail_hit_rate"])
        lam = lam_mult * lam_miss
        for t_from, t_to in eval_spans:
            r = window_rates(g, t_burst + t_from, t_burst + t_to, w_s)
            if r is None:
                continue
            trapped = bool(r["hit_rate_max"] < float(a["trap_hit_below"]) and tail_hit < float(a["trap_hit_below"]))
            ratio_s = r["sessions_per_s"] / refs["sessions_per_s"]
            ratio_t = (r["turns_per_s"] / et) / (refs["turns_per_s"] / et)
            ratio_k = r["prefill_tok_per_s"] / refs["prefill_tok_per_s"]
            rows.append({"run_id": int(run_id), "lam_mult": lam_mult, "burst": burst, "seed": int(g["seed"].iloc[0]),
                         "span": f"[{t_from:g},{t_to:g})", "trapped": trapped, "tail_hit_rate": tail_hit,
                         "ratio_sessions": ratio_s, "ratio_turns": ratio_t, "ratio_tokens": ratio_k,
                         "crit_a_sessions": abs(ratio_s - 1) <= tol, "crit_a_turns": abs(ratio_t - 1) <= tol,
                         "crit_a_tokens": abs(ratio_k - 1) <= tol,
                         # (b) by conservation: backlog slope = lambda - completion rate (sessions/s)
                         "slope_conservation": lam - r["sessions_per_s"],
                         "crit_b_conservation": bool(lam - r["sessions_per_s"] > slope_frac * (lam - refs["sessions_per_s"]))})
    return pd.DataFrame(rows)


def summarize_traps(df: pd.DataFrame) -> pd.DataFrame:
    """Per (span, lam_mult) over the TRAPPED runs: ratios (mean, min, max) and the fraction of runs where (a) fires."""
    out: List[Dict[str, Any]] = []
    t = df[df["trapped"]]
    for (span, lam), g in t.groupby(["span", "lam_mult"]):
        row: Dict[str, Any] = {"span": span, "lam_mult": lam, "n_trapped_runs": int(len(g))}
        for k in ("sessions", "turns", "tokens"):
            col = f"ratio_{k}"
            row.update({f"{col}_mean": float(g[col].mean()), f"{col}_min": float(g[col].min()), f"{col}_max": float(g[col].max()),
                        f"a_fires_{k}": float(g[f"crit_a_{k}"].mean())})
        row["b_fires_conservation"] = float(g["crit_b_conservation"].mean())
        row["a_tokens_and_b"] = float((g["crit_a_tokens"] & g["crit_b_conservation"]).mean())
        row["a_sessions_and_b"] = float((g["crit_a_sessions"] & g["crit_b_conservation"]).mean())
        out.append(row)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- no-burst escapes
def noburst_escapes(windows: pd.DataFrame, runs: pd.DataFrame, a: Dict[str, Any]) -> pd.DataFrame:
    """For the burst=0 runs: start of the first run of >= noburst_trap_min_s consecutive windows with hit < trap_hit_below
    (NaN: never), and whether the run ends trapped."""
    rr = runs.set_index("run_id")
    w_s, need = float(a["window_s"]), int(round(float(a["noburst_trap_min_s"]) / float(a["window_s"])))
    rows: List[Dict[str, Any]] = []
    pol = windows[windows["policy"] == a["policy"]]
    for run_id, g in pol.groupby("run_id"):
        lam_mult, burst = parse_variant(str(g["variant"].iloc[0]))
        if burst != 0:
            continue
        g = g.sort_values("t_start")
        low = (g["hit_rate"].to_numpy() < float(a["trap_hit_below"])).astype(int)
        t = g["t_start"].to_numpy()
        esc = float("nan")
        for i in range(0, len(low) - need + 1):
            if low[i:i + need].all():
                esc = float(t[i])
                break
        rows.append({"run_id": int(run_id), "lam_mult": lam_mult, "seed": int(g["seed"].iloc[0]), "escape_start_s": esc,
                     "escaped": bool(esc == esc), "ends_trapped": bool(rr.loc[run_id, "tail_hit_rate"] < float(a["trap_hit_below"])),
                     "horizon_s": float(rr.loc[run_id, "sim_end_s"])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Stage-C window bias on the closed curve
def transient_bias(curve_windows: pd.DataFrame, a: Dict[str, Any]) -> pd.DataFrame:
    """mu(n) over the Stage-C-like window vs steady state (FCFS-LRU, k=1 curve): sessions/s, turns-based and prefill tokens/s."""
    et = effective_mean_turns(float(a["mean_turns"]), int(a["max_turns"]))
    w = curve_windows[(curve_windows["policy"] == a["policy"]) & (curve_windows["variant"].str.startswith("k=1.0|"))].copy()
    w["n"] = w["variant"].str.split("n=").str[1].astype(int)
    (a0, a1), (b0, b1) = a["curve_window_s"], a["curve_steady_s"]
    rows: List[Dict[str, Any]] = []
    for n, g in w.groupby("n"):
        x = g[(g["t_start"] >= a0) & (g["t_start"] < a1)]
        y = g[(g["t_start"] >= b0) & (g["t_start"] < b1)]
        rows.append({"n": int(n), "mu_sessions_window": float(x["sessions_per_s"].mean()), "mu_sessions_steady": float(y["sessions_per_s"].mean()),
                     "mu_turns_window": float(x["turns_per_s"].mean() / et), "mu_turns_steady": float(y["turns_per_s"].mean() / et),
                     "prefill_tok_window": float(x["prefill_tok_per_s"].mean()), "prefill_tok_steady": float(y["prefill_tok_per_s"].mean())})
    df = pd.DataFrame(rows).sort_values("n").reset_index(drop=True)
    for k in ("sessions", "turns"):
        df[f"rel_bias_{k}"] = df[f"mu_{k}_window"] / df[f"mu_{k}_steady"] - 1.0
    df["rel_bias_prefill_tok"] = df["prefill_tok_window"] / df["prefill_tok_steady"] - 1.0
    return df


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--out-root", default=None)
    args = ap.parse_args(argv)
    git = git_info(REPO)
    t0 = datetime.now()
    cfg = yaml.safe_load(Path(args.config).read_text())
    a, inp = cfg["analysis"], cfg["inputs"]
    tp = load_params(ANALYSIS).trap_v2
    tol, slope_frac = float(tp["rate_tolerance"]), float(tp["slope_frac"])
    bdir, cdir, edir = (p if p.is_absolute() else REPO / p for p in (Path(inp["burst_info_dir"]), Path(inp["curve_dir"]), Path(inp["e0_dir"])))
    files = {"burst_windows": bdir / "windows.csv", "burst_runs": bdir / "runs.csv", "burst_meta": bdir / "meta.json",
             "burst_config": bdir / "config_effective.yaml",
             "curve_windows": cdir / "windows.csv", "e0_windows": edir / "windows.csv", "e0_runs": edir / "runs.csv",
             "e0_summary": edir / "e0_summary.json"}
    meta_b = json.loads(files["burst_meta"].read_text())
    e0 = json.loads(files["e0_summary"].read_text())
    # the burst_info experiment bursts at the end of its warmup (config_effective.yaml: burst_info.warmup_s)
    lam_miss = float(meta_b["lambda_miss"])
    t_burst = float(yaml.safe_load(files["burst_config"].read_text())["burst_info"]["warmup_s"])
    refs = e0_references(pd.read_csv(files["e0_windows"], usecols=["exp", "run_id", "t_start", "sessions_per_s", "turns_per_s",
                                                                    "prefill_tok_per_s"]),
                         pd.read_csv(files["e0_runs"], usecols=["exp", "run_id", "population"]),
                         int(a["e0_population"]), float(a["e0_warmup_s"]))
    refs["lambda_miss_e0_summary"] = float(e0["lambda_miss"])
    runs_b = pd.read_csv(files["burst_runs"], usecols=["run_id", "tail_hit_rate", "sim_end_s"])
    win_b = pd.read_csv(files["burst_windows"], usecols=WIN_COLS)
    spans = a["eval_windows_after_burst_s"]
    rows = trapped_run_rows(win_b, runs_b, refs, lam_miss, t_burst, spans, a, tol, slope_frac)
    summ = summarize_traps(rows)
    esc = noburst_escapes(win_b, runs_b, a)
    bias = transient_bias(pd.read_csv(files["curve_windows"], usecols=["policy", "variant", "t_start", "sessions_per_s",
                                                                       "turns_per_s", "prefill_tok_per_s"]), a)
    out = new_result_dir(REPO / cfg["output"]["root"] if args.out_root is None else args.out_root, cfg["output"]["name"])
    rows.to_csv(out / "per_run.csv", index=False)
    summ.to_csv(out / "summary_by_lambda.csv", index=False)
    esc.to_csv(out / "noburst_escapes.csv", index=False)
    bias.to_csv(out / "transient_bias.csv", index=False)
    horizon = float(a["noburst_horizon_s"])
    esc_sum = [{"lam_mult": float(m), "n_runs": int(len(g)), "n_escaped_any_time": int(g["escaped"].sum()),
                "n_ends_trapped": int(g["ends_trapped"].sum()),
                "n_escaped_before_e2_horizon": int((g["escape_start_s"] + float(a["noburst_trap_min_s"]) <= horizon).sum()),
                "escape_start_s": [None if x != x else float(x) for x in g["escape_start_s"]]}
               for m, g in esc.groupby("lam_mult")]
    summary = {"references": refs, "lambda_miss": lam_miss, "t_burst_s": t_burst, "rate_tolerance": tol, "slope_frac": slope_frac,
               "by_lambda": json.loads(summ.to_json(orient="records")), "noburst_escapes": esc_sum,
               "transient_bias_selected": json.loads(bias[bias["n"].isin([16, 20, 22, 24, 26, 28, 30, 32, 100, 300])]
                                                     .to_json(orient="records"))}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "config.yaml").write_text(Path(args.config).read_text())
    write_meta(out, build_meta(experiment="agentload_trap_sim_traces", argv=[sys.executable, *sys.argv], seeds=[],
                               hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(),
                               extra={"input_sha256": {k: sha256(v) for k, v in files.items()}, "trap_v2_params": tp,
                                      "deterministic": True}, status="finished"))
    with pd.option_context("display.width", 220, "display.max_columns", 40, "display.float_format", "{:.3f}".format):
        print("TRAPPED sim runs, ratio of the window rate to its all-miss reference (mean [min, max]) and fraction where (a) fires")
        keep = ["span", "lam_mult", "n_trapped_runs", "ratio_sessions_mean", "ratio_sessions_min", "ratio_sessions_max", "a_fires_sessions",
                "ratio_turns_mean", "a_fires_turns", "ratio_tokens_mean", "ratio_tokens_min", "ratio_tokens_max", "a_fires_tokens",
                "b_fires_conservation", "a_tokens_and_b", "a_sessions_and_b"]
        print(summ[keep].to_string(index=False))
        print("\nNO-BURST escapes (simulator, from empty)")
        print(json.dumps(esc_sum, indent=1))
        print("\nStage-C window bias on the closed curve")
        print(bias[["n", "mu_sessions_window", "mu_sessions_steady", "rel_bias_sessions", "rel_bias_turns", "rel_bias_prefill_tok"]]
              .to_string(index=False))
    print("result dir:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
