"""Round 8, blind NATIVE-POOL predictions: tables and the notes file for BOTH batching modes, generated from the round-7 stage result dirs that
``experiments/r8_native_predict_run.sh`` wrote under ``results/r8_native_mixed`` and ``results/r8_native_separate`` (no simulation here).

    python -m prefixmeta.r8_native_report report   --spec configs/r8_native_predict.yaml                  -> results/r8_native_report/<ts>/{tables.md, summary.json, meta.json}
    python -m prefixmeta.r8_native_report points   --out-root results/r8_native_mixed                    -> the B3n test points of the latest edge stage, as a JSON list
    python -m prefixmeta.r8_native_report assemble --spec configs/r8_native_predict.yaml --headline <file.md> --notes notes/PREDICTIONS_native.md

The per-stage tables are the unchanged tables of ``prefixmeta.r7_report`` (the r7 driver and report are used through the spec; nothing in them is re-implemented here).
This module adds only what the r8 task asks for on top of them: the landmarks of the closed curve (peak n and mu, cap n, hit-fraction crossings), the from-empty
edge in multiples and in sessions/s (and whether it is censored at the grid top), the stable fraction at the real E0b grid, and the compact burst-size sensitivity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .mech_runner import begin, finish
from .probe import load_probe_config
from .r6_predict import df_md
from .r6_validate import crossing
from .r7_report import Stages, fs, letters, sha256_of, t_burst_sizes, t_curves, t_edge, t_pairs, t_workloads
from .r7_robustness import stage_summary

TITLE = "Round 8: blind predictions of the calibrated simulator for the native-KV-pool experiments (KV pool 955,757 tokens)"


# ======================================================================= pure helpers (unit-tested)
def curve_landmarks(cs: dict, runs: pd.DataFrame, levels: Sequence[float]) -> Dict[str, Any]:
    """Landmarks of one closed curve from the curves stage summary ``cs`` (``mu_turns_by_n``, ``hit_by_n``, peak / cap) and its per-run table ``runs``
    (columns n, seed, hit_rate): the peak (turns-based), the cap n, the hit-fraction crossings of the seed-mean curve at every level of ``levels`` (n at which the
    hit fraction first falls through the level, linear interpolation between grid points; NaN if it never does), the same 0.5-type crossings per seed for the first
    level, the largest grid n with seed-mean hit >= the highest level, and mu(last n) / peak."""
    ns = sorted(int(n) for n in cs["mu_turns_by_n"])
    hit = [float(cs["hit_by_n"][str(n)]) for n in ns]
    mu = [float(cs["mu_turns_by_n"][str(n)]) for n in ns]
    lv = [float(x) for x in levels]
    out: Dict[str, Any] = {"peak_n": int(cs["peak_n"]), "peak_mu_turns": float(cs["peak_mu_turns"]), "cap_n": int(cs["cap_n"]),
                           "peak_n_sessions_based": int(cs["peak_n_sessions_based"]), "peak_mu_sessions": float(cs["peak_mu_sessions"]),
                           "cap_n_sessions_based": int(cs["cap_n_sessions_based"]),
                           "hit_at_peak": hit[ns.index(int(cs["peak_n"]))], "mu_last_over_peak": mu[-1] / float(cs["peak_mu_turns"]), "last_n": ns[-1],
                           "hit_crossing": {f"{x:g}": float(crossing(ns, hit, x)) for x in lv}}
    hi_lv = max(lv)
    ok = [n for n, h in zip(ns, hit) if h >= hi_lv]
    out["largest_n_with_hit_at_least_top_level"] = max(ok) if ok else None
    per_seed = {}
    for s, g in runs.groupby("seed"):
        t = g.groupby("n")["hit_rate"].mean().reset_index().sort_values("n")
        per_seed[int(s)] = float(crossing(t["n"].tolist(), t["hit_rate"].tolist(), lv[0]))
    out["hit_crossing_first_level_by_seed"] = per_seed
    return out


def edge_landmarks(es: dict, verdicts: pd.DataFrame, lam_miss: float) -> Dict[str, Any]:
    """The from-empty edge of one mode from the edge stage summary ``es`` and its verdict table: hi (contiguous all-stable multiple) in multiples and sessions/s, whether
    it is CENSORED at the top of the grid (every multiple of the grid all-stable, so the true edge may be higher), the largest all-stable multiple, the stable
    fraction by multiple and the multiples at which that fraction falls through 0.95 and 0.5 (linear interpolation, labelled supplementary)."""
    g = verdicts.groupby("lam_mult", sort=True)["stable"].agg(["sum", "size"]).reset_index()
    mults = [float(m) for m in g["lam_mult"]]
    frac = [float(s) / float(n) for s, n in zip(g["sum"], g["size"])]
    top = max(mults)
    hi = float(es["hi"])
    all_stable = [int(s) == int(n) for s, n in zip(g["sum"], g["size"])]
    censored = bool(all(all_stable) and abs(hi - top) < 1e-9)
    return {"hi": hi, "hi_sessions_per_s": hi * lam_miss, "censored_at_grid_top": censored, "grid_top": top, "hi_largest_all_stable": float(es["hi_largest_all_stable"]),
            "contiguous_equals_largest": bool(es["contiguous_equals_largest"]), "lambda_miss": lam_miss, "points": [float(p) for p in es["points"]],
            "window_empty": bool(es["window_empty"]), "n_stable_by_mult": {f"{m:g}": int(s) for m, s in zip(mults, g["sum"])},
            "n_runs_by_mult": {f"{m:g}": int(n) for m, n in zip(mults, g["size"])}, "stable_frac_by_mult": {f"{m:g}": f for m, f in zip(mults, frac)},
            "stable_frac_crossing_0.95": float(crossing(mults, frac, 0.95)), "stable_frac_crossing_0.5": float(crossing(mults, frac, 0.5))}


def e0b_rows(verdicts: pd.DataFrame, grid: Sequence[float], z: float = 1.96) -> pd.DataFrame:
    """Stable runs at exactly the real E0b grid (multiples of lambda_miss; each must be a multiple that the edge stage ran), with Wilson intervals, plus the pooled row."""
    rows, k_all, n_all = [], 0, 0
    for m in grid:
        g = verdicts[np.isclose(verdicts["lam_mult"], float(m))]
        if g.empty:
            raise ValueError(f"E0b multiple {m} was not run by the edge stage")
        k, n = int(g["stable"].sum()), int(len(g))
        k_all += k
        n_all += n
        rows.append({"multiple of lambda_miss": float(m), "lambda (sessions/s)": float(g["lam"].iloc[0]), "stable runs": fs(k, n, z), "stable fraction": k / n,
                     "final backlog mean": float(g["final_backlog"].mean()), "tail hit mean": float(g["tail_hit_rate"].mean())})
    rows.append({"multiple of lambda_miss": "pooled over the grid", "lambda (sessions/s)": float("nan"), "stable runs": fs(k_all, n_all, z), "stable fraction": k_all / n_all,
                 "final backlog mean": float("nan"), "tail hit mean": float("nan")})
    return pd.DataFrame(rows)


def burst_sensitivity(cl: pd.DataFrame, sizes: Sequence[int], hit_below: float, z: float = 1.96) -> pd.DataFrame:
    """Per (multiple, burst size) from the burst_sizes stage's classified runs: TRAPPED / INDETERMINATE / RECOVERED counts and the stuck count (hit < ``hit_below``),
    with Wilson intervals; size 0 is the shared NOBURST arm."""
    rows = []
    for mult in sorted(cl["mult"].unique()):
        for size in [0] + [int(s) for s in sizes]:
            arm = "no_burst" if size == 0 else f"burst_{size}"
            g = cl[np.isclose(cl["mult"], mult) & (cl["arm"] == arm)]
            if g.empty:
                continue
            n = int(len(g))
            rows.append({"x lambda_miss": float(mult), "burst size": size, "trapped": fs(int(g["trapped"].sum()), n, z), "indeterminate": int(g["indeterminate"].sum()),
                         "recovered": fs(int(g["recovered"].sum()), n, z), "stuck (hit < %g)" % hit_below: fs(int((g["hit"] < hit_below).sum()), n, z),
                         "classes by seed": letters(g), "hit (mean)": float(g["hit"].mean()), "backlog (mean)": float(g["backlog"].mean())})
    return pd.DataFrame(rows)


def pairs_vs_sizes(pairs: pd.DataFrame, sizes: pd.DataFrame, burst_n: int) -> Dict[str, Any]:
    """Consistency check between two code paths: the BURST and NOBURST arms of the pairs stage and the ``burst_n``-session and NOBURST arms of the burst-size stage
    (same spec, seeds and test points, so the runs must be identical). Returns the number of (point, arm, seed) runs compared and the largest absolute difference of
    hit, backlog, slope and token rate."""
    cols = ["hit", "backlog", "slope", "token_rate"]
    a = pairs[pairs["arm"].isin(["burst", "no_burst"])][["mult", "arm", "seed"] + cols].copy()
    b = sizes[sizes["arm"].isin([f"burst_{int(burst_n)}", "no_burst"])][["mult", "arm", "seed"] + cols].copy()
    b["arm"] = b["arm"].replace({f"burst_{int(burst_n)}": "burst"})
    for d in (a, b):
        d["mult"] = d["mult"].round(6)
    m = a.merge(b, on=["mult", "arm", "seed"], suffixes=("_pairs", "_sizes"))
    diffs = {c: float((m[c + "_pairs"] - m[c + "_sizes"]).abs().max()) if len(m) else float("nan") for c in cols}
    return {"n_compared": int(len(m)), "n_expected": int(min(len(a), len(b))), "max_abs_diff": diffs, "identical": bool(len(m) == len(a) == len(b) and all(v == 0.0 for v in diffs.values()))}


def test_points(out_root: str) -> List[float]:
    """The B3n test points (multiples of lambda_miss) of the LATEST edge stage under ``out_root``."""
    sm = stage_summary(out_root, "edge")["workloads"]
    (name,) = list(sm)
    return [float(p) for p in sm[name]["points"]]


# ======================================================================= tables
def mode_tables(S: Stages, r7: dict, r8: dict, key: str) -> tuple[str, Dict[str, Any]]:
    """The markdown block and the headline numbers of one batching mode."""
    z = float(r7["wilson_z"])
    levels = [float(r8["hit_crossing_level"])] + [float(x) for x in r8.get("hit_crossing_extra_levels", [])]
    sens_size = int(r8["burst_sensitivity_size"])
    hit_below = float(r7["classify"]["indeterminate_hit_below"])
    name = r7["record_workload"]
    md: List[str] = []
    head: Dict[str, Any] = {}

    md.append("### B1n. All-miss capacity lambda_miss (cache off, closed population, window [%g, %g) s)\n" % (float(r7["lambda_miss"]["warmup_s"]), float(r7["lambda_miss"]["horizon_s"])))
    if S.ok("lambda_miss"):
        md.append(t_workloads(S, r7) + "\n")
        w = S.summary("lambda_miss")["workloads"][name]
        head["B1n"] = {"lambda_miss_turns": w["lambda_miss_turns"], "lambda_miss_turns_sd": w["lambda_miss_turns_sd"], "lambda_miss_sessions": w["lambda_miss_sessions"],
                       "token_rate": w["token_rate"], "busy": w["busy"], **{k: v for k, v in w.items() if k.startswith("check_pop")}}
    else:
        md.append("**stage `lambda_miss` NOT RUN**\n")

    md.append("### B4n. Closed curve mu(n) and hit fraction (cache on, seeds %s, window [%g, %g) s)\n" % (
        ",".join(str(s) for s in r7["curve"]["seeds"]), float(r7["curve"]["warmup_s"]), float(r7["curve"]["horizon_s"])))
    if S.ok("curves"):
        md.append(t_curves(S, r7) + "\n")
        cs = S.summary("curves")["workloads"][name]
        runs = S.csv("curves", "curve_runs.csv")
        lmk = curve_landmarks(cs, runs, levels)
        head["B4n"] = lmk
        rows = [{"landmark": "peak n (first argmax of the turns-based mu)", "value": lmk["peak_n"]},
                {"landmark": "peak mu (turns-based sessions/s)", "value": lmk["peak_mu_turns"]},
                {"landmark": "hit fraction at the peak n", "value": lmk["hit_at_peak"]},
                {"landmark": "cap n (smallest grid n within 5% of the peak)", "value": lmk["cap_n"]},
                {"landmark": "[sessions-based] peak n / peak mu / cap n", "value": f"{lmk['peak_n_sessions_based']} / {lmk['peak_mu_sessions']:.4g} / {lmk['cap_n_sessions_based']}"}]
        for lv, c in lmk["hit_crossing"].items():
            rows.append({"landmark": f"n at which the seed-mean hit fraction falls through {lv} (linear interpolation)", "value": c})
        rows.append({"landmark": "largest grid n with seed-mean hit >= %g" % max(levels), "value": lmk["largest_n_with_hit_at_least_top_level"]})
        rows.append({"landmark": "per-seed n at which the hit fraction falls through %g" % levels[0],
                     "value": ", ".join(f"seed {s}: {c:.1f}" for s, c in lmk["hit_crossing_first_level_by_seed"].items())})
        rows.append({"landmark": f"mu({lmk['last_n']}) / peak mu", "value": lmk["mu_last_over_peak"]})
        md.append("Landmarks of the closed curve (r8 summary of the table above; hit crossing = n at which the hit fraction falls through the level):\n\n" + df_md(pd.DataFrame(rows), "{:.4g}") + "\n")
        per = runs.sort_values(["n", "seed"])
        tab = []
        for n, g in per.groupby("n"):
            tab.append({"n": int(n), "mu turns-based by seed": " / ".join(f"{x:.4f}" for x in g["mu_turns"]), "hit by seed": " / ".join(f"{x:.2f}" for x in g["hit_rate"]),
                        "mu sessions-based by seed": " / ".join(f"{x:.4f}" for x in g["mu"])})
        md.append("Per-seed values (seed order 0, 1, 2; a spread across seeds marks a bistable cliff cell):\n\n" + df_md(pd.DataFrame(tab)) + "\n")
    else:
        md.append("**stage `curves` NOT RUN**\n")

    md.append("### B2n. From-empty open-loop stability (cache on, B2 rule, %g s, %d seeds)\n" % (float(r7["edge"]["horizon_s"]), len(r7["edge"]["seeds"])))
    if S.ok("edge") and S.ok("lambda_miss"):
        md.append(t_edge(S, r7, z) + "\n")
        es = S.summary("edge")["workloads"][name]
        v = S.csv("edge", "edge_verdicts.csv")
        elm = edge_landmarks(es, v, float(es["lambda_miss_turns"]))
        head["B2n"] = elm
        txt = (f"**Edge hi = {elm['hi']:g} x lambda_miss = {elm['hi_sessions_per_s']:.4f} sessions/s** (contiguous all-stable rule; lambda_miss = {elm['lambda_miss']:.5f} sessions/s; "
               f"largest all-stable multiple irrespective of contiguity: {elm['hi_largest_all_stable']:g}). ")
        if elm["censored_at_grid_top"]:
            txt += f"**CENSORED**: every multiple of the grid up to {elm['grid_top']:g} is all-stable, so the true edge is >= {elm['grid_top']:g} x. "
        txt += (f"Supplementary: the stable fraction falls through 0.95 at {elm['stable_frac_crossing_0.95']:.3g} x and through 0.5 at {elm['stable_frac_crossing_0.5']:.3g} x "
                f"(linear interpolation between grid multiples; NaN = never).")
        md.append(txt + "\n")
        e0b = [float(x) for x in r8["e0b_grid"]]
        eb = e0b_rows(v, e0b, z)
        head["B2n_e0b"] = {f"{r['multiple of lambda_miss']:g}" if not isinstance(r["multiple of lambda_miss"], str) else "pooled": r["stable fraction"] for r in eb.to_dict("records")}
        md.append("Stable fraction at exactly the real E0b grid (the same 10-seed runs, read at these multiples):\n\n" + df_md(eb, "{:.4g}") + "\n")
    else:
        md.append("**stage `edge` NOT RUN**\n")

    md.append("### B3n. Paired NOBURST / BURST / CAPPED test at lo + (hi - lo)/3 and lo + 2 (hi - lo)/3 (burst %d sessions in %g s at t = %g s, %d seeds)\n" % (
        int(r7["pairs"]["burst_n"]), float(r7["pairs"]["burst_width_s"]), float(r7["pairs"]["warmup_s"]), len(r7["pairs"]["seeds"])))
    if S.ok("pairs"):
        md.append(t_pairs(S, r7, z) + "\n")
        pw = S.summary("pairs")["workloads"][name]
        head["B3n"] = {"cap_n": pw["cap_n"], "hi": pw["hi"], "window_empty": pw["window_empty"],
                       "points": {m: {k: p[k] for k in ("lam", "n_seeds", "need", "burst_trapped", "burst_indeterminate", "burst_recovered", "noburst_good", "noburst_trapped",
                                                           "cap_recovered", "cap_trapped", "PASS")} for m, p in pw["points"].items()}}
    else:
        md.append("**stage `pairs` NOT RUN**\n")

    md.append("### B3n sensitivity (NOT the registered burst): the same points with a burst of %d sessions (%d seeds)\n" % (sens_size, len(r7["burst_sizes"]["seeds"])))
    if S.ok("burst_sizes"):
        md.append(t_burst_sizes(S, r7, z) + "\n")
        cl = S.csv("burst_sizes", "classified_runs.csv")
        bs = burst_sensitivity(cl, [int(s) for s in r7["burst_sizes"]["sizes"]], hit_below, z)
        md.append("Compact view (declared TRAPPED rule, INDETERMINATE = hit < %g but not TRAPPED, RECOVERED = hit > 0.8 and backlog < 20):\n\n" % hit_below + df_md(bs, "{:.4g}") + "\n")
        if S.ok("pairs"):
            cons = pairs_vs_sizes(S.csv("pairs", "classified_runs.csv"), cl, int(r7["pairs"]["burst_n"]))
            head["consistency_pairs_vs_burst_sizes"] = cons
            md.append("Consistency of two code paths: the BURST (%d sessions) and NOBURST arms of the paired-arm stage against the same arms of this stage: %d of %d runs compared, "
                      "largest absolute difference of hit / backlog / slope / token rate = %s, identical: **%s**.\n" % (
                          int(r7["pairs"]["burst_n"]), cons["n_compared"], cons["n_expected"], " / ".join(f"{v:.3g}" for v in cons["max_abs_diff"].values()), cons["identical"]))
        sm = S.summary("burst_sizes")["by_mult"]
        head["B3n_burst_sensitivity"] = {m: {"lam": v["lam"], "need": v["need"], "per_size": v["per_size"], "noburst_good": v["noburst_good"]} for m, v in sm.items()}
    else:
        md.append("**stage `burst_sizes` NOT RUN** (an empty window has no test points, or the driver was not run)\n")
    return "\n".join(md), head


def prov_rows(S: Stages, spec_path: Path):
    rows, cmds, total = [], [], 0.0
    spec_sha = sha256_of(spec_path)
    for s in S.stages:
        if not S.ok(s):
            rows.append({"stage": s, "result dir": "NOT RUN"})
            continue
        m = S.meta(s)
        seeds = m.get("seeds", [])
        cfg_copy = S.dir[s] / "config.yaml"
        rows.append({"stage": s, "result dir": S.dir[s].as_posix(), "commit": m["git"]["commit"][:9], "dirty": m["git"]["dirty"],
                     "seeds": f"{seeds[0]}..{seeds[-1]} ({len(seeds)})" if seeds else "", "start": m["start_time"], "wall s": round(m["wall_s"], 1),
                     "spec copy identical to the committed file": cfg_copy.exists() and sha256_of(cfg_copy) == spec_sha,
                     "overrides": " ".join(m.get("overrides") or []) or "-"})
        total += float(m["wall_s"])
        cmds.append(" ".join(m["argv"]))
    return pd.DataFrame(rows), cmds, total


def provenance(stages: Dict[str, Stages], spec_path: Path, r8: dict) -> str:
    txt = (f"Spec: `{spec_path.as_posix()}` (sha256 `{sha256_of(spec_path)}`); KV pool {int(r8['kv_pool_tokens']):,} tokens; engine block = `configs/r7_robustness.yaml` engine "
           "block with that one edit; base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter "
           "`C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes (the stages run one after the other).\n\n")
    for key, S in stages.items():
        df, cmds, total = prov_rows(S, spec_path)
        mode = r8["modes"][key]
        txt += (f"**{key}** (`engine.batching` = `{mode['batching']}`, out-root `{mode['out_root']}`):\n\n" + df_md(df) +
                f"\n\nTotal recorded stage wall time: {total:.0f} s ({total / 60:.1f} min). Commands (argv as recorded in each `meta.json`; run from the worktree root):\n\n```\n" +
                "\n".join(cmds) + "\n```\n\n")
    return txt


# ======================================================================= report / assemble
def load_stages(cfg: dict) -> Dict[str, Stages]:
    return {k: Stages(m["out_root"], cfg["r7"].get("stages")) for k, m in cfg["r8"]["modes"].items()}


def build(cfg: dict, stages: Dict[str, Stages]) -> tuple[str, Dict[str, Any]]:
    r7, r8 = cfg["r7"], cfg["r8"]
    parts, head = [], {}
    for i, (key, S) in enumerate(stages.items()):
        m = r8["modes"][key]
        parts.append(f"## Mode `{key}` ({'PRIMARY' if i == 0 else 'SECONDARY'}): engine.batching = `{m['batching']}`, KV pool {int(r8['kv_pool_tokens']):,} tokens\n")
        t, h = mode_tables(S, r7, r8, key)
        parts.append(t)
        head[key] = h
    return "\n".join(parts), head


def cmd_report(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    cfg = load_probe_config(str(spec_path), repo_dir, args.set)
    stages = load_stages(cfg)
    cfg_eff = {k: v for k, v in cfg.items() if k != "preregistration_file"}
    ctx = begin("r8_native_report", "r8_native_report", cfg_eff, cfg_eff, args, repo_dir)
    tables, head = build(cfg, stages)
    (ctx.out / "tables.md").write_text(tables, encoding="utf-8")
    (ctx.out / "summary.json").write_text(json.dumps(head, indent=2, default=float))
    (ctx.out / "provenance.md").write_text(provenance(stages, spec_path, cfg["r8"]), encoding="utf-8")
    for key, S in stages.items():                 # small per-stage CSV summaries, copied so the report dir is self-contained
        for s in S.stages:
            if S.ok(s):
                for name in ("classified_runs.csv", "edge_verdicts.csv", "lambda_miss_runs.csv", "curve_runs.csv", "summary.json"):
                    src = S.dir[s] / name
                    if src.exists():
                        (ctx.out / f"{key}_{s}_{name}").write_bytes(src.read_bytes())
    finish(ctx, [], {"stage": "report", "stage_dirs": {k: {s: (S.dir[s].as_posix() if S.ok(s) else None) for s in S.stages} for k, S in stages.items()}})
    print(tables)
    print("result dir:", ctx.out)
    return ctx.out


def latest_report_dir(out_root: str) -> Path:
    base = Path(out_root) / "r8_native_report"
    ds = sorted(d for d in base.iterdir() if d.is_dir() and (d / "tables.md").exists())
    if not ds:
        raise FileNotFoundError(f"no report under {base}")
    return ds[-1]


def cmd_assemble(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    rd = latest_report_dir(args.out_root)
    tables = (rd / "tables.md").read_text(encoding="utf-8")
    prov = (rd / "provenance.md").read_text(encoding="utf-8")
    head = Path(args.headline).read_text(encoding="utf-8").strip()
    txt = (f"# {TITLE}\n\n{head}\n\n## Provenance: what was run\n\nGenerated by `python -m prefixmeta.r8_native_report assemble` from the report `{rd.as_posix()}` "
           "(the tables below are that report's `tables.md`, verbatim; nothing is retyped).\n\n" + prov + "\n## Tables (generated)\n\n" + tables)
    Path(args.notes).write_text(txt, encoding="utf-8")
    print("wrote", args.notes)
    return Path(args.notes)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round 8 native-pool predictions: report, assemble, points")
    ap.add_argument("cmd", choices=["report", "assemble", "points"])
    ap.add_argument("--spec", "--config", dest="config", default="configs/r8_native_predict.yaml")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--headline", default=None)
    ap.add_argument("--notes", default="notes/PREDICTIONS_native.md")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[])
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None):
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    if args.cmd == "points":
        print(json.dumps(test_points(args.out_root)))
        return 0
    if args.cmd == "report":
        return cmd_report(Path(args.config), args, repo_dir)
    if not args.headline:
        raise SystemExit("assemble needs --headline")
    return cmd_assemble(Path(args.config), args, repo_dir)


if __name__ == "__main__":      # pragma: no cover
    r = main()
    sys.exit(r if isinstance(r, int) else 0)
