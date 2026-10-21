"""Command line analysis of agentload runs. Every invocation writes a NEW dir ``<root>/<name>/<timestamp>/`` with
the analysis params (config.yaml), meta.json (git state at start, inputs, versions) and the CSV/JSON outputs.

  python -m analysis.summarize windows   --run-dirs RUN [RUN ...]
  python -m analysis.summarize burst     --run-dirs RUN [RUN ...]          # trap / recovery / hysteresis + kill rule
  python -m analysis.summarize miss      --run-dirs RUN [...] --warmup-s N  # lambda_miss from closed-population runs
  python -m analysis.summarize stable    --run-dirs RUN [...]               # stable-from-empty verdict per run
  python -m analysis.summarize closed    --run-dirs RUN [...] [--warmup-s N] [--primary-label L]   # Stage C: mu(n) curve, n_cap = argmax of L (mu_curve.json)
  python -m analysis.summarize burst2    --run-dirs RUN [...] [--prereg FILE] # paired-arm kill test, throughput criterion
                                                                              # (kill_verdict_v2.json); `burst` stays the
                                                                              # old hit-rate criterion (secondary)

Every invocation also runs the consistency guards of ``analysis.guards`` (unverified from-empty start, mixed hardware or
output-id source, prompt-token mismatches, transport errors): problems go to ``guards.json``, meta.json and stderr;
``--strict-guards`` makes any error-severity problem a non-zero exit (after the outputs are written).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import yaml

from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta

from . import prereg as prereg_mod
from .closed import closed_point, mu_curve
from .guards import check_runs, summarize_problems
from .hysteresis import (burst_verdict, kill_table, kill_verdict, lambda_cap_bracket, lambda_miss_closed,
                         stable_verdict)
from .load import Run, load_run
from .params import AnalysisParams, load_params
from .throughput import backlog_trace
from .trap_v2 import (cell_verdicts, diagnose, legacy_secondary, pairing_problems, trap_v2_run)
from .windows import queue_trace, window_table

DEFAULT_PARAMS = "configs/agentload_analysis.yaml"


def _sanitize(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, (float, np.floating)) and not np.isfinite(float(o)):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def _finish(out: Path, params_path: str, p: AnalysisParams, argv: List[str], git: Dict[str, Any], t0: datetime,
            inputs: List[Run], extra: Dict[str, Any]) -> None:
    (out / "config.yaml").write_text(Path(params_path).read_text())
    (out / "config_effective.yaml").write_text(yaml.safe_dump(p.raw, sort_keys=False))
    ins = [{"run_dir": str(r.dir), "label": r.label, "seed": r.seed, "run_git": r.meta.get("git"),
            "run_start": r.meta.get("start_time"), "hardware": r.meta.get("hardware"),
            "slurm_env": r.meta.get("slurm_env")} for r in inputs]
    meta = build_meta(experiment="agentload_analysis", argv=argv, seeds=[r.seed for r in inputs],
                      hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(),
                      extra={"inputs": ins, **extra}, status="finished")
    write_meta(out, meta)


def _runs(dirs: Sequence[str]) -> List[Run]:
    return [load_run(d) for d in dirs]


def cmd_windows(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    frames, traces = [], []
    for r in runs:
        w = window_table(r, p)
        w.insert(0, "run_dir", str(r.dir))
        w.insert(1, "label", r.label)
        w.insert(2, "seed", r.seed)
        frames.append(w)
        tr = queue_trace(r, p)
        tr.insert(0, "run_dir", str(r.dir))
        traces.append(tr)
    pd.concat(frames, ignore_index=True).to_csv(out / "windows.csv", index=False)
    pd.concat(traces, ignore_index=True).to_csv(out / "queue_trace.csv", index=False)
    return {"n_runs": len(runs)}


def cmd_burst(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    """Legacy (hit-rate) criterion. Runs without a burst (the NOBURST arm) cannot be classified and are listed under
    ``skipped_no_burst``; the kill table counts only BURST-arm (or unlabelled) runs, so the CAPPED and NOBURST arms of a
    paired set cannot dilute it. The paired-arm verdict is ``burst2``."""
    rows, frames, skipped = [], [], []
    for r in runs:
        if r.t_burst is None:
            skipped.append(str(r.dir))
            continue
        w = window_table(r, p)
        v = burst_verdict(r, w, p)
        v["run_dir"] = str(r.dir)
        v["arm"] = r.arm or r.arm_derived
        rows.append(v)
        w.insert(0, "run_dir", str(r.dir))
        frames.append(w)
    df = pd.DataFrame(rows)
    df.to_csv(out / "burst_runs.csv", index=False)
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(out / "windows.csv", index=False)
    kdf = df[df["arm"].isin(["burst"])] if len(df) else df
    tab = kill_table(kdf, p.kill["trapped_fraction_min"], p.kill["min_runs_per_cell"]) if len(kdf) else pd.DataFrame(
        columns=["label", "rate_mult", "n_runs", "n_trap", "n_good_before", "n_hysteresis", "n_recovered", "n_aborted",
                 "frac_hysteresis", "frac_trap_any", "meets_strict", "meets_loose"])
    tab.to_csv(out / "burst_cells.csv", index=False)
    kv = kill_verdict(tab, p, args.fcfs_substr)
    kv["guards"] = summarize_problems(args.guard_problems)       # a verdict next to unresolved guard errors is suspect
    kv["skipped_no_burst"] = skipped
    kv["arms_in_kill_table"] = ["burst"]
    kv["role"] = ("SECONDARY: hit-rate criterion of the first draft. The pre-registered kill-test verdict is "
                  "kill_verdict_v2.json (`summarize burst2`: throughput criterion, paired arms)")
    (out / "kill_verdict.json").write_text(json.dumps(_sanitize(kv), indent=2, default=json_default))
    return {"n_runs": len(runs), "kill_verdict": _sanitize(kv)}


def cmd_burst2(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    """Paired-arm kill test with the throughput-based trap criterion -> kill_verdict_v2.json (see analysis.trap_v2)."""
    recs, by_run, skipped, trace_frames = [], {}, [], []
    for r in runs:
        try:
            rec = trap_v2_run(r, p)
        except ValueError as e:
            skipped.append({"run_dir": str(r.dir), "reason": str(e)})
            continue
        rec["legacy"] = legacy_secondary(r, p)
        recs.append(rec)
        by_run[rec["run_dir"]] = r
        tr = backlog_trace(r.sessions, 0.0, r.t_end_s, float(p.trap_v2["trace_bin_s"]))
        tr.insert(0, "run_dir", rec["run_dir"])
        tr.insert(1, "arm", rec["arm"])
        if len(tr):
            trace_frames.append(tr)
    flat = []
    for rec in recs:
        row = {k: v for k, v in rec.items() if k != "legacy"}
        for k, v in (rec["legacy"] or {}).items():
            row[f"legacy_{k}"] = v
        flat.append(row)
    pd.DataFrame(flat).to_csv(out / "trap_v2_runs.csv", index=False)
    if trace_frames:
        pd.concat(trace_frames, ignore_index=True).to_csv(out / "backlog_trace.csv", index=False)

    # pairing validity per (label, rate_mult, seed)
    groups: Dict[tuple, list] = {}
    for rec in recs:
        groups.setdefault((rec["label"], rec["rate_mult"], rec["seed"]), []).append((rec, by_run[rec["run_dir"]]))
    pair_probs = {f"{k[0]}|{k[1]}|{k[2]}": pairing_problems(g) for k, g in groups.items()}
    pair_probs = {k: v for k, v in pair_probs.items() if v}

    cells = cell_verdicts(recs, p.trap_v2)
    pr, pr_info = None, {"provided": False}
    if args.prereg:
        pr = prereg_mod.load_prereg(args.prereg)
        probs = prereg_mod.validate(pr, p, args.fcfs_substr)
        prov = prereg_mod.file_provenance(args.prereg)
        pr_info = {"provided": True, "provenance": prov, "problems": probs, "status": pr.get("status"),
                   "window": prereg_mod.window_of(pr), "engine_cell_label": (pr.get("inputs") or {}).get("engine_cell_label"),
                   "registered_lambda_mults": prereg_mod.registered_mults(pr),
                   "valid": not any(x["severity"] == "error" for x in probs),
                   "committed_clean": prov["committed_clean"]}
    run_by_dir = {rec["run_dir"]: by_run[rec["run_dir"]] for rec in recs}
    for c in cells:
        c["diagnosis"] = diagnose(c)
        c["in_registered_window"] = prereg_mod.lambda_in_window(pr, c["lambda"]) if pr is not None else None
        c["pairing_problems"] = {k: v for k, v in pair_probs.items() if k.startswith(f"{c['label']}|{c['rate_mult']}|")}
        c["meets_valid_pairing"] = bool(c["meets"] and not c["pairing_problems"])
        if pr is not None:
            # a cell is the REGISTERED one only if its label is exactly the registered cell and its multiple is a registered
            # lambda; each of its runs must also be bound to this file (sha256 in meta), launched with the registered
            # protocol / references / cap / hardware, and started after the file's last commit (review finding 4)
            c["registered_label"] = bool(c["label"] == pr_info["engine_cell_label"])
            c["registered_lambda"] = prereg_mod.mult_is_registered(pr, c["rate_mult"])
            blockers = {}
            for rec in recs:
                if rec["label"] == c["label"] and rec["rate_mult"] == c["rate_mult"]:
                    bl = prereg_mod.run_blockers(pr, pr_info["provenance"], run_by_dir[rec["run_dir"]])
                    if bl:
                        blockers[rec["run_dir"]] = bl
            c["registration_blockers"] = blockers
            c["decisive_eligible"] = bool(c["registered_label"] and c["registered_lambda"] and c["in_registered_window"] is True
                                          and not blockers)
    fc = [c for c in cells if args.fcfs_substr in str(c["label"])]
    pre_registered = bool(pr_info.get("valid") and pr_info.get("committed_clean"))
    rule_only = [c for c in fc if c["meets_valid_pairing"]]
    decisive = ([c for c in cells if c["meets_valid_pairing"] and c.get("decisive_eligible")] if pre_registered else [])
    legacy_tab = pd.DataFrame([{"label": r["label"], "rate_mult": r["rate_mult"], "seed": r["seed"],
                                "is_trap": (r["legacy"] or {}).get("is_trap")} for r in recs
                               if r["arm"] == "burst" and r["legacy"] is not None])
    legacy = {}
    if len(legacy_tab):
        for (lab, m), g in legacy_tab.groupby(["label", "rate_mult"], dropna=False):
            legacy[f"{lab}|{m}"] = {"n_burst_runs": int(len(g)), "n_legacy_trap": int(g["is_trap"].sum())}
    doc = {
        "schema": "kill_verdict_v2",
        "criterion": "TRAPPED iff the completion rate (trap_v2.rate_estimator; default: uncached prefill tokens/s over the "
                     "post-burst window vs E0a's all-miss rate) is within +-rate_tolerance of its all-miss reference AND the "
                     "session backlog slope > slope_frac*(lambda-lambda_miss) [and lambda > lambda_miss]; DRAINING iff slope<0; "
                     "RECOVERED iff hit > recovered_hit_above and the backlog (trap_v2.recovered_backlog_metric; default "
                     "outstanding = requests in flight + gate queue) < recovered_backlog_below at the end. PASS per lambda: "
                     "BURST trapped AND NOBURST good AND CAPPED recovered in >= pass_fraction_min of the seeds.",
        "rule": dict(p.trap_v2), "hit_metric": p.w["hit_metric"],
        "prereg": pr_info, "pre_registered": pre_registered,
        "fcfs_substr": args.fcfs_substr, "cells": cells,
        "fcfs_cells_meeting_rule": [{"label": c["label"], "rate_mult": c["rate_mult"]} for c in rule_only],
        "kill_test_pass_rule_only": bool(rule_only) if fc else None,
        "kill_test_pass_decisive": (bool(decisive) if pre_registered else None),
        "decisive_cells": [{"label": c["label"], "rate_mult": c["rate_mult"]} for c in decisive],
        "decisive_note": ("a decisive PASS needs a valid, committed, clean pre-registration file whose last commit predates every "
                          "run of the cell, the registered cell (label == inputs.engine_cell_label; 'fcfs'-substring matches "
                          "such as vllm-fcfs or -native do NOT count), a registered lambda multiple inside its window, and "
                          "every run bound to the file (meta.prereg_sha256) and to its protocol; without --prereg the verdict "
                          "is exploratory"),
        "pairing_problems": pair_probs, "skipped_runs": skipped,
        "legacy_secondary_burst_arm": legacy,
        "guards": summarize_problems(args.guard_problems)}
    (out / "kill_verdict_v2.json").write_text(json.dumps(_sanitize(doc), indent=2, default=json_default))
    pd.DataFrame([{k: v for k, v in c.items() if k not in ("seeds", "pairing_problems", "incomplete", "registration_blockers")}
                  for c in cells]
                 ).to_csv(out / "trap_v2_cells.csv", index=False)
    return {"n_runs": len(runs), "kill_verdict_v2": _sanitize({k: doc[k] for k in (
        "pre_registered", "kill_test_pass_rule_only", "kill_test_pass_decisive", "fcfs_cells_meeting_rule", "decisive_cells",
        "pairing_problems")})}


def cmd_closed(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    """Stage C: mu(n) from closed-population runs (cache on). Writes mu_points.csv, mu_curve.csv and mu_curve.json."""
    warm = args.warmup_s if args.warmup_s is not None else float(p.closed["warmup_s"])
    df = pd.DataFrame([closed_point(r, warm, p) for r in runs])
    df.to_csv(out / "mu_points.csv", index=False)
    curve = mu_curve(df, p.closed, args.fcfs_substr, primary_label=args.primary_label)
    curve["warmup_s"] = warm
    curve["inputs_unverified_start"] = sorted(df.loc[df["start_state_verified"] != True, "run_dir"].tolist())
    (out / "mu_curve.json").write_text(json.dumps(_sanitize(curve), indent=2, default=json_default))
    rows = []
    for lab, c in curve["cells"].items():
        for i, n in enumerate(c["n"]):
            rows.append({"label": lab, "n": n, "n_runs": c["n_runs"][i], "mu_sessions": c["mu_sessions"][i],
                         "mu_turns_based": c["mu_turns_based"][i], "turns_per_s": c["turns_per_s"][i],
                         "hit_frac_turns": c["hit_frac_turns"][i], "cached_frac_tokens": c["cached_frac_tokens"][i],
                         "queue_mean": c["queue_mean"][i]})
    pd.DataFrame(rows).to_csv(out / "mu_curve.csv", index=False)
    return {"n_runs": len(runs), "mu_curve": _sanitize({k: curve[k] for k in ("estimator", "primary_label", "n_cap", "mu_300",
                                                                              "mu_max", "notes")})}


def cmd_miss(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    warm = args.warmup_s if args.warmup_s is not None else 0.0
    rows = [lambda_miss_closed(r, warm) for r in runs]
    df = pd.DataFrame(rows)
    df.to_csv(out / "lambda_miss_runs.csv", index=False)
    n = len(df)
    hw = sorted({str(r.hardware) for r in runs})
    calib = {
        "hardware": hw[0] if len(hw) == 1 else None, "hardware_all": hw,
        "hostnames": sorted({str(r.meta.get("hostname")) for r in runs}),
        "output_ids_sources": sorted({k for r in runs for k in r.output_ids_sources}),
        "lambda_miss": float(df["lambda_miss_sessions"].mean()),
        "lambda_miss_turns_based": float(df["lambda_miss_turns_based"].mean()),
        "lambda_miss_se": float(df["lambda_miss_sessions"].std(ddof=1) / np.sqrt(n)) if n > 1 else None,
        "lambda_miss_turns_based_se": float(df["lambda_miss_turns_based"].std(ddof=1) / np.sqrt(n)) if n > 1 else None,
        # the reference of trap criterion (a): uncached prefill tokens/s of the all-miss closed population. With the engine's
        # cache disabled every prompt token is uncached; cached_frac_tokens_max must then be ~0 (else the cache was not off)
        "all_miss_uncached_tokens_per_s": float(df["uncached_tokens_per_s"].mean()),
        "all_miss_uncached_tokens_per_s_se": float(df["uncached_tokens_per_s"].std(ddof=1) / np.sqrt(n)) if n > 1 else None,
        "all_miss_cached_frac_tokens_max": float(df["cached_frac_tokens"].max()),
        "n_runs": n, "warmup_s": warm, "labels": sorted(set(df["label"])),
        "note": "lambda_miss = completed sessions/s (simulator headline); turns-based = turns/s / E[T]; "
                "use the key you want in arrivals.lambda_ref ('<path>/calibration.json:<key>'). "
                "all_miss_uncached_tokens_per_s = arrivals.uncached_tokens_ref of the E2 runs (trap criterion (a))."}
    (out / "calibration.json").write_text(json.dumps(_sanitize(calib), indent=2))
    return {"calibration": _sanitize(calib)}


def cmd_stable(args: argparse.Namespace, p: AnalysisParams, out: Path, runs: List[Run]) -> Dict[str, Any]:
    rows = []
    for r in runs:
        row = stable_verdict(r, queue_trace(r, p), p)
        row["run_dir"] = str(r.dir)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(out / "stable_runs.csv", index=False)
    g = df.groupby(["label", "rate_mult"], dropna=False)["stable"].agg(["sum", "size"]).reset_index()
    g.columns = ["label", "rate_mult", "n_stable", "n_runs"]
    g.to_csv(out / "stable_by_rate.csv", index=False)
    # pooled over labels: for a single-label analysis this is the bracket; with several labels use by_label
    g_pool = g.groupby("rate_mult", dropna=False)[["n_stable", "n_runs"]].sum().reset_index()
    br = lambda_cap_bracket(g_pool[g_pool["rate_mult"].notna()])
    hw_by_label = {lab: sorted({str(r.hardware) for r in runs if r.label == lab}) for lab in sorted(set(df["label"]))}
    by_label = {lab: {**_sanitize(lambda_cap_bracket(gl[gl["rate_mult"].notna()])), "hardware": hw_by_label[lab]}
                for lab, gl in g.groupby("label")} if "label" in g.columns else {}
    # `by_label` is what the pre-registration reads (the bracket must come from the registered cell's own policy: an LPM
    # bracket says nothing about FCFS); the top-level keys pool all labels and are kept for older readers
    br = {**_sanitize(br), "by_label": by_label, "guards": summarize_problems(args.guard_problems)} if isinstance(br, dict) else br
    (out / "lambda_cap_bracket.json").write_text(json.dumps(_sanitize(br), indent=2))
    return {"n_runs": len(runs), "lambda_cap_bracket_in_lambda_miss_units": _sanitize(br)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.summarize")
    ap.add_argument("cmd", choices=["windows", "burst", "burst2", "miss", "stable", "closed"])
    ap.add_argument("--run-dirs", nargs="+", required=True)
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--set", action="append", default=[], help="override an analysis param, e.g. burst.trap_min_s=6000")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--warmup-s", type=float, default=None,
                    help="(miss, closed) discard this many seconds at the start (miss: 0 if omitted; closed: closed.warmup_s)")
    ap.add_argument("--fcfs-substr", default="fcfs", help="(burst, burst2, closed) labels containing this are the FCFS cells")
    ap.add_argument("--prereg", default=None, help="(burst2) filled pre-registration YAML; recorded and checked")
    ap.add_argument("--primary-label", default=None,
                    help="(closed) the engine label whose n_cap / mu_300 / mu_max become the top-level values of mu_curve.json "
                         "(default: the FCFS cell with the most distinct n; summarise the 300k and the native pool separately)")
    ap.add_argument("--strict-guards", action="store_true",
                    help="exit 3 if any guard problem has severity 'error' (outputs are still written)")
    args = ap.parse_args(argv)
    p = load_params(args.params, args.set)
    repo = Path(args.params).resolve().parent.parent
    git = git_info(repo)                              # at START
    t0 = datetime.now()
    root = args.out_root or p.raw["output"]["root"]
    name = args.name or f'{p.raw["output"]["name"]}_{args.cmd}'
    out = new_result_dir(root, name)
    runs = _runs(args.run_dirs)
    problems = check_runs(runs, require_verified_start=args.cmd in ("burst", "burst2", "stable"))
    args.guard_problems = problems
    (out / "guards.json").write_text(json.dumps({"summary": summarize_problems(problems), "problems": problems}, indent=2))
    for pr in problems:
        print(f"GUARD [{pr['severity']}] {pr['code']}: {pr['message']} ({pr['run_dir']})", file=sys.stderr)
    fn = {"windows": cmd_windows, "burst": cmd_burst, "burst2": cmd_burst2, "miss": cmd_miss, "stable": cmd_stable,
          "closed": cmd_closed}[args.cmd]
    extra = fn(args, p, out, runs)
    extra["guard_problems"] = problems
    _finish(out, args.params, p, [sys.executable, "-m", "analysis.summarize", *(argv if argv is not None else sys.argv[1:])],
            git, t0, runs, extra)
    print(json.dumps({"out_dir": str(out), **{k: v for k, v in extra.items() if k not in ("kill_verdict", "kill_verdict_v2", "guard_problems")},
                      "guards": summarize_problems(problems)}, indent=2, default=json_default))
    if "kill_verdict" in extra:
        print(json.dumps(extra["kill_verdict"], indent=2))
    if "kill_verdict_v2" in extra:
        print(json.dumps(extra["kill_verdict_v2"], indent=2))
    if args.strict_guards and any(pr["severity"] == "error" for pr in problems):
        print("strict guards: error-severity problems present", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
