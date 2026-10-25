"""Round 7 robustness: tables and the notes file, generated from the stage result dirs listed in ``results/r7_robustness/manifest.tsv`` (no simulation here).

    python -m prefixmeta.r7_report report   --spec configs/r7_robustness.yaml [--out-root results]      -> results/r7_report/<ts>/{tables.md, summary.json, meta.json}
    python -m prefixmeta.r7_report assemble --spec configs/r7_robustness.yaml --headline <file.md> --notes notes/ROBUSTNESS_r7.md

``report`` reads the LATEST manifest entry of every stage; a stage that was never run is listed as "not run" (never dropped silently). ``assemble`` builds the
notes file from the headline text (written by hand from the generated tables), a generated provenance section (commands, seeds, commits, result dirs, wall time) and
the generated tables, verbatim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .mech_runner import begin, finish
from .probe import load_probe_config
from .r6_predict import df_md
from .r7_robustness import STAGES, stage_dir
from .runner import wilson_ci

LETTER = {"TRAPPED": "T", "RECOVERED": "R", "INDETERMINATE": "I", "OTHER": "O", "BOTH": "B"}


def fs(k: int, n: int, z: float = 1.96) -> str:
    """'k/n (fraction) [Wilson low, high]'."""
    if n <= 0:
        return "n/a"
    lo, hi = wilson_ci(int(k), int(n), z)
    return f"{int(k)}/{int(n)} ({k / n:.2f}) [{lo:.2f}, {hi:.2f}]"


def seed_range(seeds: List[int]) -> str:
    """'0-2' for a contiguous list of seeds, else the comma-separated list."""
    s = [int(x) for x in seeds]
    if len(s) == 1:
        return str(s[0])
    return f"{s[0]}-{s[-1]}" if s == list(range(s[0], s[-1] + 1)) else ",".join(str(x) for x in s)


def fnum(x: Any, fmt: str = "{:.4g}") -> str:
    return "never" if x is None or (isinstance(x, float) and not np.isfinite(x)) else fmt.format(x)


def letters(g: pd.DataFrame) -> str:
    """Per-seed class letters of one arm, in seed order (T trapped, R recovered, I indeterminate, O other, B both)."""
    return "".join(LETTER[x] for x in g.sort_values("seed")["label"])


class Stages:
    """Latest result dir, summary.json and meta.json of every stage (None for a stage that was never run)."""

    def __init__(self, out_root: str, stages: Optional[List[str]] = None):
        self.out_root = out_root
        self.stages = tuple(stages) if stages else tuple(STAGES)           # r7.stages of the spec (default: all); the report lists only these
        self.dir: Dict[str, Optional[Path]] = {}
        for s in self.stages:
            try:
                self.dir[s] = stage_dir(out_root, s)
            except FileNotFoundError:
                self.dir[s] = None

    def ok(self, s: str) -> bool:
        return self.dir.get(s) is not None

    def summary(self, s: str) -> dict:
        return json.loads((self.dir[s] / "summary.json").read_text())

    def meta(self, s: str) -> dict:
        return json.loads((self.dir[s] / "meta.json").read_text())

    def csv(self, s: str, name: str) -> pd.DataFrame:
        return pd.read_csv(self.dir[s] / name)


# ======================================================================= tables
def t_workloads(S: Stages, r7: dict) -> str:
    sm = S.summary("lambda_miss")["workloads"]
    rows = []
    for name, w in sm.items():
        row = {"workload": w["label"], "tool-time mean (s)": w["tool_time_mean_s"], "tool-time CV": w["tool_time_cv"],
               "lambda_miss (turns-based, sessions/s)": w["lambda_miss_turns"], "sd over seeds": w["lambda_miss_turns_sd"],
               "lambda_miss (sessions/s)": w["lambda_miss_sessions"], "all-miss token rate (tok/s)": w["token_rate"], "GPU busy": w["busy"]}
        if len({round(float(x["E_T"]), 6) for x in sm.values()}) > 1:         # different turn laws: sessions/s are not comparable, turns/s are
            row["E[T] (turns per session)"] = w["E_T"]
            row["lambda_miss x E[T] (turns/s)"] = w["lambda_miss_turns"] * w["E_T"]
        for k, v in w.items():
            if k.startswith("check_pop"):
                row[f"{k.replace('check_pop', 'POP ')} lambda_miss (turns)"] = v["lambda_miss_turns"]
                row[f"{k.replace('check_pop', 'POP ')} busy"] = v["busy"]
        rows.append(row)
    return df_md(pd.DataFrame(rows), "{:.5g}")


def t_curves(S: Stages, r7: dict) -> str:
    sm = S.summary("curves")["workloads"]
    names = list(sm)
    ns = sorted(next(iter(sm.values()))["mu_turns_by_n"], key=int)
    tab = pd.DataFrame({"n": [int(n) for n in ns]})
    for name in names:
        w = sm[name]
        tab[w["label"]] = [f"{w['mu_turns_by_n'][n]:.4f} / {w['hit_by_n'][n]:.2f}" for n in ns]
    lm = []
    for name in names:
        w = sm[name]
        last = max(int(n) for n in w["mu_turns_by_n"])
        lm.append({"workload": w["label"], "peak n": w["peak_n"], "peak mu (turns-based sessions/s)": w["peak_mu_turns"], "cap n (smallest within 5%)": w["cap_n"],
                   f"mu({last}) / peak": w["mu_turns_by_n"][str(last)] / w["peak_mu_turns"], f"hit({last})": w["hit_by_n"][str(last)],
                   "[sessions-based] peak n": w["peak_n_sessions_based"], "[sessions-based] peak mu": w["peak_mu_sessions"],
                   "[sessions-based] cap n": w["cap_n_sessions_based"]})
    return ("Cell = `mu turns-based (sessions/s) / hit fraction`, mean over the seeds, closed population, cache on:\n\n" + df_md(tab) + "\n\nLandmarks "
            "(the cap n of the CAPPED arm is the turns-based one; the sessions-based columns are a labelled sensitivity):\n\n" + df_md(pd.DataFrame(lm), "{:.4g}"))


def t_edge(S: Stages, r7: dict, z: float) -> str:
    sm = S.summary("edge")["workloads"]
    v = S.csv("edge", "edge_verdicts.csv")
    rows = []
    for name, w in sm.items():
        g = v[v["workload"] == name]
        for m, gg in g.groupby("lam_mult", sort=True):
            k, n = int(gg["stable"].sum()), int(len(gg))
            rows.append({"workload": w["label"], "multiple of lambda_miss": m, "lambda (sessions/s)": float(gg["lam"].iloc[0]), "stable runs": fs(k, n, z),
                         "all stable": k == n, "final backlog mean": gg["final_backlog"].mean(), "final backlog max": gg["final_backlog"].max(),
                         "trend rise mean": gg["trend_rise"].mean(), "tail hit mean": gg["tail_hit_rate"].mean(), "stopped early": int(gg["stopped_early"].sum())})
    win = []
    for name, w in sm.items():
        win.append({"workload": w["label"], "lambda_miss (sessions/s)": w["lambda_miss_turns"], "hi (contiguous all-stable)": w["hi"],
                    "largest all-stable multiple": w["hi_largest_all_stable"], "same": w["contiguous_equals_largest"], "refinement grid run": w["refined"],
                    "window": "EMPTY (hi <= 1.1)" if w["window_empty"] else f"[1, {w['hi']:g}]", "test points (x lambda_miss)": ", ".join(f"{p:g}" for p in w["points"]) or "none"})
    return ("Stable runs per multiple of the workload's own lambda_miss (from empty, %g s, B2 rule), with Wilson 95%% intervals:\n\n" % float(r7["edge"]["horizon_s"]) +
            df_md(pd.DataFrame(rows), "{:.4g}") +
            "\n\nMeasured metastability window and the paired-arm test points:\n\n" + df_md(pd.DataFrame(win), "{:.5g}"))


def t_pairs(S: Stages, r7: dict, z: float) -> str:
    hit_lo = float(r7["classify"]["indeterminate_hit_below"])
    sm = S.summary("pairs")["workloads"]
    cl = S.csv("pairs", "classified_runs.csv")
    rows, strs, empty = [], [], []
    for name, w in sm.items():
        if w["window_empty"]:
            empty.append(f"* **{w['label']}**: EMPTY window (hi = {w['hi']:g} <= 1.1): no paired test was run.")
            continue
        for mult, p in w["points"].items():
            n = p["n_seeds"]
            g = cl[(cl["workload"] == name) & (np.isclose(cl["mult"], float(mult)))]
            gb = g[g["arm"] == "burst"]
            rows.append({"workload": w["label"], "x lambda_miss": float(mult), "lambda (sessions/s)": p["lam"], "cap n": w["cap_n"],
                         "BURST trapped": fs(p["burst_trapped"], n, z), "NOBURST good": fs(p["noburst_good"], n, z), "CAPPED recovered": fs(p["cap_recovered"], n, z),
                         "PASS (need %d)" % p["need"]: "PASS" if p["PASS"] else "FAIL",
                         "[sensitivity] BURST stuck (hit < %g)" % hit_lo: fs(int((gb["hit"] < hit_lo).sum()), n, z)})
            row = {"workload": w["label"], "x lambda_miss": float(mult)}
            for arm, lab in (("burst", "BURST"), ("no_burst", "NOBURST"), ("burst_cap", "CAPPED")):
                row[lab] = letters(g[g["arm"] == arm])
            row["BURST indeterminate"] = p["burst_indeterminate"]
            row["BURST recovered"] = p["burst_recovered"]
            row["NOBURST trapped"] = p["noburst_trapped"]
            row["CAPPED trapped"] = p["cap_trapped"]
            row["NOBURST hit (mean)"] = g[g["arm"] == "no_burst"]["hit"].mean()
            row["NOBURST backlog (mean)"] = g[g["arm"] == "no_burst"]["backlog"].mean()
            strs.append(row)
    out = ("Counts out of the seeds, with Wilson 95% intervals; PASS needs BURST trapped, NOBURST good and CAPPED recovered each in at least `need` seeds "
           "(the declared rules). The last column is a labelled post-hoc sensitivity, not part of the verdict: BURST runs whose hit rate over the evaluation window "
           "is below the indeterminate threshold, whatever their backlog slope (TRAPPED plus INDETERMINATE):\n\n")
    out += (df_md(pd.DataFrame(rows)) if rows else "(no point was tested)") + "\n\n"
    if empty:
        out += "\n".join(empty) + "\n\n"
    if strs:
        out += ("Per-seed classes in seed order (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other) and diagnostics:\n\n" +
                df_md(pd.DataFrame(strs), "{:.4g}"))
    return out


def t_burst_sizes(S: Stages, r7: dict, z: float) -> str:
    hit_lo = float(r7["classify"]["indeterminate_hit_below"])
    sm = S.summary("burst_sizes")
    cl = S.csv("burst_sizes", "classified_runs.csv")
    out = []
    for mult, m in sm["by_mult"].items():
        rows = []
        n = m["n_seeds"]
        g0 = cl[(np.isclose(cl["mult"], float(mult))) & (cl["arm"] == "no_burst")]
        stuck_ok = []
        rows.append({"burst size": "0 (NOBURST)", "trapped": fs(m["noburst_trapped"], n, z), "recovered (good)": fs(m["noburst_good"], n, z), "indeterminate": 0,
                     "[sensitivity] stuck (hit < %g)" % hit_lo: fs(int((g0["hit"] < hit_lo).sum()), n, z), "classes by seed": letters(g0), "hit (mean)": g0["hit"].mean()})
        for b, p in m["per_size"].items():
            g = cl[(np.isclose(cl["mult"], float(mult))) & (cl["arm"] == f"burst_{b}")]
            k_stuck = int((g["hit"] < hit_lo).sum())
            stuck_ok.append((int(b), k_stuck >= m["need"]))
            rows.append({"burst size": int(b), "trapped": fs(p["trapped"], n, z), "recovered (good)": fs(p["recovered"], n, z), "indeterminate": p["indeterminate"],
                         "[sensitivity] stuck (hit < %g)" % hit_lo: fs(k_stuck, n, z), "classes by seed": letters(g), "hit (mean)": g["hit"].mean()})
        smallest_stuck = next((b for b, ok in stuck_ok if ok), None)
        out.append(f"**lambda = {mult} x lambda_miss = {m['lam']:.5f} sessions/s** (need {m['need']} of {n} seeds): smallest burst trapping in >= {m['need']}/{n} seeds "
                   f"(declared TRAPPED rule): **{fnum(m['smallest_size_trapping_in_need'], '{}')}**; smallest burst from which every larger burst also does: "
                   f"{fnum(m['smallest_size_from_which_all_larger_trap'], '{}')}; [sensitivity] smallest burst with hit < {hit_lo:g} in >= {m['need']}/{n} seeds "
                   f"(stuck, slope test ignored): {fnum(smallest_stuck, '{}')}\n\n" + df_md(pd.DataFrame(rows), "{:.3g}"))
    return "\n\n".join(out)


def t_horizon(S: Stages, r7: dict, z: float) -> str:
    sm = S.summary("horizon")
    cl = S.csv("horizon", "classified_runs.csv")
    ev = S.csv("horizon", "events.csv")
    out = []
    for mult, info in sm["by_mult"].items():
        rows = []
        for arm in ("no_burst", "burst"):
            a = info[arm]
            ea = ev[(np.isclose(ev["mult"], float(mult))) & (ev["arm"] == arm)]
            row = {"arm": arm.upper().replace("_", ""), "runs": a["n"], "backlog > 50 at some window (collapse)": fs(a["n_collapsed"], a["n"], z),
                   "hit < 0.2 after the burst (trap onset)": fs(a["n_trap_onset"], a["n"], z), "released (hit > 0.5 after onset)": fs(a["n_released"], a["n"], z),
                   "last window: backlog > 50": fs(int((ea["final_backlog"] > 50).sum()), a["n"], z), "last window: hit < 0.2": fs(int((ea["final_hit"] < 0.2).sum()), a["n"], z)}
            for k, v in a.items():
                if k.startswith("trapped_in_"):
                    row["TRAPPED in " + k.replace("trapped_in_", "")] = fs(v, a["n"], z)
            for k, v in a.items():
                if k.startswith("recovered_in_"):
                    row["RECOVERED in " + k.replace("recovered_in_", "")] = fs(v, a["n"], z)
            rows.append(row)
        out.append(f"**lambda = {mult} x lambda_miss = {info['lam']:.5f} sessions/s**, 30000 s after the burst (run length 31200 s):\n\n" + df_md(pd.DataFrame(rows)))
        e = ev[np.isclose(ev["mult"], float(mult))]
        wins = sorted(cl["eval_window"].unique())
        for arm in ("no_burst", "burst"):
            ea = e[e["arm"] == arm].sort_values("seed")
            rr = []
            for _, r in ea.iterrows():
                row = {"seed": int(r["seed"]), "collapse_s (backlog > 50)": r["collapse_s"], "trap_onset_s": r["trap_onset_s"], "release_s": r["release_s"],
                       "min hit after burst": r["min_hit_after_burst"], "final hit": r["final_hit"], "max backlog": r["max_backlog"], "final backlog": r["final_backlog"]}
                for wk in wins:
                    c = cl[(np.isclose(cl["mult"], float(mult))) & (cl["arm"] == arm) & (cl["seed"] == r["seed"]) & (cl["eval_window"] == wk)]
                    row["class " + wk] = c["label"].iloc[0] if len(c) else "n/a"
                rr.append(row)
            out.append(f"Per run, {arm.upper().replace('_', '')} (times are window END times in absolute seconds; `n/a` = the event did not happen):\n\n" + df_md(pd.DataFrame(rr), "{:.4g}"))
    return "\n\n".join(out)


def t_lowlam(S: Stages, r7: dict, z: float) -> str:
    sm = S.summary("lowlam")
    cl = S.csv("lowlam", "classified_runs.csv").sort_values("slope")
    n = sm["n"]
    thr = sm["slope_threshold"]
    q = pd.DataFrame([{"quantity": "backlog slope over the last 2500 s (requests/s)", **{k: v for k, v in sm["slope_quantiles"].items()}},
                      {"quantity": "slope / threshold", **{k: v for k, v in sm["slope_over_threshold_quantiles"].items()}},
                      {"quantity": "slope / (lambda - lambda_miss)", **{k: 0.5 * v for k, v in sm["slope_over_threshold_quantiles"].items()}},
                      {"quantity": "uncached-token rate / all-miss rate", **{k: v for k, v in sm["token_ratio_quantiles"].items()}},
                      {"quantity": "hit rate over the last 2500 s", **{k: v for k, v in sm["hit_quantiles"].items()}}])
    cls = pd.DataFrame([{"class": k, "runs": fs(v, n, z)} for k, v in sm["classes"].items() if v or k in ("TRAPPED", "INDETERMINATE")])
    detail = cl[["seed", "hit", "backlog", "token_ratio", "slope", "slope_threshold", "rate_ok", "slope_ok", "label"]].copy()
    detail.insert(5, "slope / threshold", detail["slope"] / detail["slope_threshold"])
    head = (f"lambda = {sm['mult']} x lambda_miss = {sm['lam']:.5f} sessions/s; threshold 0.5 (lambda - lambda_miss) = {thr:.5f} requests/s; {n} BURST runs.\n\n"
            f"Slope exceeds the threshold in {fs(sm['n_slope_above_threshold'], n, z)}; token rate within 15% of all-miss in {fs(sm['n_rate_ok'], n, z)}; hit < 0.05 in "
            f"{fs(sm['n_hit_below_0.05'], n, z)}.\n\n")
    return head + "Quantiles over the runs:\n\n" + df_md(q, "{:.4g}") + "\n\nClasses:\n\n" + df_md(cls) + "\n\nPer run, sorted by slope:\n\n" + df_md(detail, "{:.4g}")


def t_detection(S: Stages, r7: dict, z: float) -> str:
    """Post-hoc pooling of every BURST run (200 sessions) of this round: how often the declared slope rule labels a run that is stuck at (near) zero hits TRAPPED."""
    hit_lo = float(r7["classify"]["indeterminate_hit_below"])
    srcs = []
    if S.ok("pairs"):
        c = S.csv("pairs", "classified_runs.csv")
        b = c[c["arm"] == "burst"]
        srcs.append((f"pairs, all test points ({b['workload'].nunique()} workloads, {b['call'].nunique()} points, seeds {int(b['seed'].min())}-{int(b['seed'].max())})", b))
        rec = b[b["workload"] == r7["record_workload"]]
        if len(rec):
            srcs.append((f"pairs, record workload only ({' and '.join(f'{m:g}' for m in sorted(rec['mult'].unique()))} x, seeds {int(rec['seed'].min())}-{int(rec['seed'].max())})", rec))
    if S.ok("burst_sizes"):
        c = S.csv("burst_sizes", "classified_runs.csv")
        srcs.append(("burst_sizes, 200 sessions (bit-identical to the record-workload rows of pairs)", c[c["arm"] == "burst_200"]))
    if S.ok("horizon"):
        c = S.csv("horizon", "classified_runs.csv")
        for wk in sorted(c["eval_window"].unique()):
            srcs.append((f"horizon, window {wk} of the 31200 s runs (new realisations, seeds 0-9)", c[(c["arm"] == "burst") & (c["eval_window"] == wk)]))
    if S.ok("lowlam"):
        srcs.append(("lowlam, 1.35 x, seeds 100-119", S.csv("lowlam", "classified_runs.csv")))
    rows = []
    for name, g in srcs:
        n = len(g)
        row = {"source": name, "BURST runs": n}
        for lab in ("TRAPPED", "INDETERMINATE", "RECOVERED", "OTHER"):
            row[lab] = fs(int((g["label"] == lab).sum()), n, z)
        row[f"hit < {hit_lo:g}"] = fs(int((g["hit"] < hit_lo).sum()), n, z)
        rows.append(row)
    from math import comb
    need = 7
    pt = pd.DataFrame([{"true per-run probability that the declared rule labels a stuck run TRAPPED": q,
                        "P(at least 7 of 10 seeds TRAPPED)": sum(comb(10, i) * q ** i * (1 - q) ** (10 - i) for i in range(need, 11))} for q in (0.6, 0.7, 0.8, 0.9, 0.95, 1.0)])
    return ("Every BURST run (200 sessions) of the round, by source and evaluation window. TRAPPED = the declared rule (token rate within 15% of all-miss AND backlog slope "
            "above 0.5 (lambda - lambda_miss)); INDETERMINATE = hit < 0.2 but not TRAPPED:\n\n" + df_md(pd.DataFrame(rows)) +
            "\n\nBinomial: the chance that a 10-seed point reaches the 7-of-10 requirement for BURST trapped, if each run is independently labelled TRAPPED with the probability in the "
            "first column (exact arithmetic, not a simulation):\n\n" + df_md(pt, "{:.3f}"))


# ======================================================================= provenance
def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def provenance(S: Stages, spec_path: Path) -> str:
    rows, cmds = [], []
    total = 0.0
    spec_sha = sha256_of(spec_path)
    for s in S.stages:
        if not S.ok(s):
            rows.append({"stage": s, "result dir": "NOT RUN", "commit": "", "dirty": "", "seeds": "", "start": "", "wall s": ""})
            continue
        m = S.meta(s)
        seeds = m.get("seeds", [])
        cfg_copy = S.dir[s] / "config.yaml"
        same = cfg_copy.exists() and sha256_of(cfg_copy) == spec_sha
        rows.append({"stage": s, "result dir": S.dir[s].as_posix(), "commit": m["git"]["commit"][:9], "dirty": m["git"]["dirty"],
                     "seeds": f"{seeds[0]}..{seeds[-1]} ({len(seeds)})" if seeds else "", "start": m["start_time"], "wall s": round(m["wall_s"], 1),
                     "spec identical to the committed file": same})
        total += float(m["wall_s"])
        cmds.append(" ".join(m["argv"]))
    txt = ("Spec: `%s` (sha256 `%s`); engine = `configs/r6_predict.yaml` engine block, batching `mixed`; base chain `configs/prefix_meta_r5.yaml` -> "
           "`configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; at most 6 worker processes.\n\n"
           % (spec_path.as_posix(), spec_sha))
    txt += df_md(pd.DataFrame(rows)) + f"\n\nTotal recorded stage wall time: {total:.0f} s ({total / 60:.1f} min).\n\nCommands (argv as recorded in each `meta.json`; run from the worktree root):\n\n```\n"
    txt += "\n".join(cmds) + "\n```\n"
    return txt


# ======================================================================= report / assemble
def build_tables(S: Stages, r7: dict) -> str:
    z = float(r7["wilson_z"])
    parts = []
    lmb, cvb = r7["lambda_miss"], r7["curve"]
    sections = (("lambda_miss", "Workloads and lambda_miss (B1: cache off, closed POP %d, window [%g, %g) s)" % (int(lmb["population"]), float(lmb["warmup_s"]), float(lmb["horizon_s"])),
                 lambda: t_workloads(S, r7)),
                ("curves", "Closed curve mu(n) (cache on, seeds %s) and the cap" % seed_range(cvb["seeds"]), lambda: t_curves(S, r7)),
                ("edge", "From-empty stability edge and the measured window", lambda: t_edge(S, r7, z)),
                ("pairs", "Paired-arm test at the two window points (%d seeds)" % len(r7["pairs"]["seeds"]), lambda: t_pairs(S, r7, z)),
                ("burst_sizes", "Burst-size sweep (record workload, 10 seeds)", lambda: t_burst_sizes(S, r7, z)),
                ("horizon", "Horizon: 30000 s after the burst (record workload, 10 seeds)", lambda: t_horizon(S, r7, z)),
                ("lowlam", "Low-lambda fragility (record workload, 1.35 x lambda_miss, 20 seeds, BURST)", lambda: t_lowlam(S, r7, z)),
                ("pairs", "Post-hoc: how often the declared slope rule labels a stuck BURST run TRAPPED", lambda: t_detection(S, r7, z)))
    k = 0
    for stage, title, fn in sections:
        if stage not in S.stages:                 # a spec that does not declare the stage (r7.stages) has no section for it; a declared stage that was not run says so
            continue
        k += 1
        parts.append(f"### {k}. {title}\n")
        parts.append(fn() + "\n" if S.ok(stage) else f"**stage `{stage}` NOT RUN**\n")
    return "\n".join(parts)


def headline_numbers(S: Stages) -> Dict[str, Any]:
    h: Dict[str, Any] = {}
    if S.ok("lambda_miss"):
        h["lambda_miss"] = {k: v["lambda_miss_turns"] for k, v in S.summary("lambda_miss")["workloads"].items()}
    if S.ok("curves"):
        h["peak_cap"] = {k: {"peak_n": v["peak_n"], "peak_mu_turns": v["peak_mu_turns"], "cap_n": v["cap_n"]} for k, v in S.summary("curves")["workloads"].items()}
    if S.ok("edge"):
        h["window"] = {k: {"hi": v["hi"], "points": v["points"], "empty": v["window_empty"]} for k, v in S.summary("edge")["workloads"].items()}
    if S.ok("pairs"):
        h["pairs"] = {k: {m: {x: p[x] for x in ("burst_trapped", "noburst_good", "cap_recovered", "PASS")} for m, p in v["points"].items()}
                      for k, v in S.summary("pairs")["workloads"].items()}
    if S.ok("burst_sizes"):
        h["burst_sizes"] = {m: {"smallest": v["smallest_size_trapping_in_need"], "trapped_by_size": {b: p["trapped"] for b, p in v["per_size"].items()}}
                            for m, v in S.summary("burst_sizes")["by_mult"].items()}
    if S.ok("horizon"):
        h["horizon"] = {m: {arm: {k: v for k, v in info[arm].items() if not isinstance(v, list)} for arm in ("no_burst", "burst")} for m, info in S.summary("horizon")["by_mult"].items()}
    if S.ok("lowlam"):
        sm = S.summary("lowlam")
        h["lowlam"] = {"classes": sm["classes"], "slope_threshold": sm["slope_threshold"], "slope_quantiles": sm["slope_quantiles"]}
    return h


def cmd_report(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    cfg = load_probe_config(str(spec_path), repo_dir, args.set)               # the same dotted overrides as the stage runs (e.g. r7.pairs.seeds)
    r7 = cfg["r7"]
    S = Stages(args.out_root, r7.get("stages"))
    cfg_eff = {k: v for k, v in cfg.items() if k != "preregistration_file"}      # not a registered run: do not copy a pre-registration into the report dir
    ctx = begin("r7_report", "r7_report", cfg_eff, cfg_eff, args, repo_dir)
    tables = build_tables(S, r7)
    (ctx.out / "tables.md").write_text(tables, encoding="utf-8")
    head = headline_numbers(S)
    (ctx.out / "summary.json").write_text(json.dumps(head, indent=2, default=float))
    (ctx.out / "provenance.md").write_text(provenance(S, spec_path), encoding="utf-8")
    for s in S.stages:                     # small per-stage CSV summaries, copied so the report dir is self-contained
        if S.ok(s):
            for name in ("classified_runs.csv", "events.csv", "edge_verdicts.csv", "lambda_miss_runs.csv", "curve_runs.csv", "summary.json"):
                src = S.dir[s] / name
                if src.exists():
                    (ctx.out / f"{s}_{name}").write_bytes(src.read_bytes())
    finish(ctx, [], {"stage": "report", "stage_dirs": {s: (S.dir[s].as_posix() if S.ok(s) else None) for s in S.stages}})
    print(tables)
    print("result dir:", ctx.out)
    return ctx.out


def latest_report_dir(out_root: str) -> Path:
    base = Path(out_root) / "r7_report"
    ds = sorted(d for d in base.iterdir() if d.is_dir() and (d / "tables.md").exists())
    if not ds:
        raise FileNotFoundError(f"no report under {base}")
    return ds[-1]


DEFAULT_TITLE = "Round 7: simulator robustness (tool-time distributions, burst size, horizon, low-lambda fragility)"


def cmd_assemble(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    title = load_probe_config(str(spec_path), repo_dir)["r7"].get("title", DEFAULT_TITLE)       # optional r7.title
    rd = latest_report_dir(args.out_root)
    tables = (rd / "tables.md").read_text(encoding="utf-8")
    prov = (rd / "provenance.md").read_text(encoding="utf-8")
    head = Path(args.headline).read_text(encoding="utf-8").strip()
    txt = (f"# {title}\n\n"
           f"{head}\n\n## Provenance: what was run\n\nGenerated by `python -m prefixmeta.r7_report assemble` from the report `{rd.as_posix()}` (the tables below are that report's "
           "`tables.md`, verbatim; nothing is retyped).\n\n" + prov + "\n## Tables (generated)\n\n" + tables)
    Path(args.notes).write_text(txt, encoding="utf-8")
    print("wrote", args.notes)
    return Path(args.notes)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round 7 robustness: report (tables) and assemble (notes file)")
    ap.add_argument("cmd", choices=["report", "assemble"])
    ap.add_argument("--spec", "--config", dest="config", required=True)
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--headline", default=None)
    ap.add_argument("--notes", default="notes/ROBUSTNESS_r7.md")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[])
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None) -> Path:
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    if args.cmd == "report":
        return cmd_report(Path(args.config), args, repo_dir)
    if not args.headline:
        raise SystemExit("assemble needs --headline")
    return cmd_assemble(Path(args.config), args, repo_dir)


if __name__ == "__main__":      # pragma: no cover
    main()
    sys.exit(0)
