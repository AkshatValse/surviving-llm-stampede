"""r15 TOOLSLOW cells T1 and T2, classified with the frozen B1 endpoints; one tri-state decision rule per cell.

Cells (registrations configs/agentload_prereg_2026-11-05_toolslow_d30w1800.yaml / _toolslow_d15_165.yaml, made by
``analysis.r15_prereg fill``; SGLang FCFS with waiting-prefix refresh, 300k pool, Qwen2.5-7B, A100 80GB PCIe; arm noburst,
seeds 0-2, one seed per job, 8700-s runs; the client option workload.tool_slowdown {t_s, width_s, add_s}):

  T1  sglang-fcfs-r1-toolslow-d30w1800   1.35 x lambda_ref   tool calls starting in [1200, 3000) s take +30 s
  T2  sglang-fcfs-r1-toolslow-d15-165    1.65 x lambda_ref   tool calls starting in [1200, 2100) s take +15 s

A copy of analysis/r14_cells.py (frozen, unchanged; its TOOLSLOW part) with a per-cell rate multiplier: the cell's ``mult`` is
used in the rate check, in ``find_controls(rate_mult=...)`` and in the cell's own decision rule; r14's MULT = 1.35 is gone.

Per run STUCK / GOOD exactly as configs/r11_basin_predict.yaml defines them (``analysis.basin.load_endpoints`` and
``analysis.basin.classify_run``, unchanged), over [5700, 8700) s:
  STUCK := hit_eval < 0.2;  GOOD := trap_v2 RECOVERED, or (hit_eval > 0.8 and backlog slope <= 0.5 x (lambda - lambda_miss)),
  lambda = the run's resolved rate (the cell's mult x lambda_ref).

A run counts only if all of these hold (``classify``):
  - its label is a cell's, it ran arm noburst at the cell's rate_mult on a registered seed, it did not abort, and its
    evaluation window matches the frozen endpoints;
  - pairing (common random numbers): its plan.csv equals the same-seed committed NOBURST control's at the cell's rate
    (jobs 17093387-404, results/nova/e2_170933xx_pulled_20261025-144558): same columns and rows, sid / origin / idx / n_turns
    exactly, arrival_s and tool_time_total_s within 1e-9 s (numpy's exponential can differ in the last bit between
    platforms); byte identity is reported;
  - the manipulation happened (``manipulation_check``, stricter than r14, which only required some slowed call and all
    slowed calls inside the window): meta.tool_slowdown is the cell's {t_s, width_s, add_s}; tool_calls.csv exists with the
    client's columns and is complete (row count and slowed count equal meta.outcome.tool_slowdown); at least one call starts
    in [t_s, t_s + width_s); every call starting there has add_s == the cell's delta; no call starting outside has add_s != 0;
    every call has t_ready == t_start + tool_s + add_s (1e-6 s);
  - it is bound to its registration (``analysis.prereg.run_blockers``; the CLI defaults --prereg to the two r15
    registrations, and a run whose binding was not checked is not counted).

Registered decision rule, per cell, no conjunction across cells (``RULE``, verbatim in each registration's
lambda_selection.rule): TRAPS iff STUCK in >= 2 of the 3 registered seeds; NO-TRAP iff GOOD in >= 2 of 3; else MIXED (MIXED
also when both counts reach 2, possible only through runs that are both STUCK and GOOD). A seed without a counted run counts
against both. ``outcome`` is the call once no result of the missing seeds could change it (None before), and
``outcome_if_missing_count_against`` the call if the missing seeds never come. Two counted runs of one seed leave the cell
undecided (both None), so no seed votes twice.

CLI:  python -m analysis.r15_cells classify --run-dirs RUN [RUN ...] [--prereg FILE ...] [--control-root DIR]
                                            [--endpoints configs/r11_basin_predict.yaml] [--out-root results]
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import basin
from . import prereg as prereg_mod
from . import r15_prereg
from .load import Run, load_run
from .params import AnalysisParams, load_params

REPO = Path(__file__).resolve().parent.parent
ENDPOINTS = "configs/r11_basin_predict.yaml"
PARAMS = "configs/agentload_analysis.yaml"
CONTROL_ROOT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst"
CONTROL_LABEL = "sglang-fcfs-r1"
REGISTERED_EVAL_FROM_S = 4500.0
PLAN_ATOL_S = 1e-9                      # plan.csv float columns (arrival_s, tool_time_total_s)
ADD_ATOL_S = 1e-9                       # tool_calls.csv add_s against the cell's delta / zero
READY_ATOL_S = 1e-6                     # t_ready against t_start + tool_s + add_s
PLAN_FLOAT_COLUMNS = ("arrival_s", "tool_time_total_s")
TOOL_CALL_COLUMNS = ["sid", "origin", "idx", "turn", "t_start", "tool_s", "add_s", "t_ready"]   # agentload.client.TOOL_CALL_FIELDS

RULE = ("TRAPS iff STUCK in >= 2 of the 3 registered seeds; NO-TRAP iff GOOD in >= 2 of 3; else MIXED (a cell that meets "
        "both counts, possible only through runs that are both STUCK and GOOD, is MIXED)")

CELLS: Dict[str, Dict[str, Any]] = {
    "sglang-fcfs-r1-toolslow-d30w1800": {
        "key": "T1", "mult": 1.35, "t_s": 1200.0, "width_s": 1800.0, "add_s": 30.0, "arm": "noburst", "seeds": (0, 1, 2),
        "e2": "configs/agentload_e2_toolslow_d30w1800.yaml",
        "rule": f"T1 (sglang-fcfs-r1-toolslow-d30w1800) is decided alone, with no conjunction with any other cell: {RULE}"},
    "sglang-fcfs-r1-toolslow-d15-165": {
        "key": "T2", "mult": 1.65, "t_s": 1200.0, "width_s": 900.0, "add_s": 15.0, "arm": "noburst", "seeds": (0, 1, 2),
        "e2": "configs/agentload_e2_toolslow_d15.yaml",
        "rule": f"T2 (sglang-fcfs-r1-toolslow-d15-165) is decided alone, with no conjunction with any other cell: {RULE}"},
}
OUTCOMES = ("TRAPS", "NO-TRAP", "MIXED")
_SEED_STATES = ((False, False), (True, False), (False, True), (True, True))     # (stuck, good) a missing seed could still get


def need_of(seeds: Sequence[int]) -> int:
    return math.ceil(2 * len(seeds) / 3)


# ---------------------------------------------------------------- plan pairing
def _plan(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(Path(run_dir) / "plan.csv", float_precision="round_trip")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_diff(a: pd.DataFrame, b: pd.DataFrame) -> Dict[str, Any]:
    """Compare two plan.csv tables: same columns and rows; float columns (arrival_s, tool_time_total_s) within PLAN_ATOL_S,
    every other column (sid, origin, idx, n_turns) exactly. Returns equal and the largest absolute float difference."""
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return {"equal": False, "max_abs_diff_s": None, "plan_problem": f"shape/columns differ: {len(a)} x {list(a.columns)} "
                                                                         f"vs {len(b)} x {list(b.columns)}"}
    probs, mx = [], 0.0
    for c in a.columns:
        if c in PLAN_FLOAT_COLUMNS:
            x = pd.to_numeric(a[c], errors="coerce").to_numpy(float)
            y = pd.to_numeric(b[c], errors="coerce").to_numpy(float)
            d = np.abs(x - y)
            if len(d) and not np.isfinite(d).all():
                probs.append(f"{c}: non-numeric values")
                continue
            m = float(d.max()) if len(d) else 0.0
            mx = max(mx, m)
            if m > PLAN_ATOL_S:
                probs.append(f"{c}: max |diff| {m:.3g} s > {PLAN_ATOL_S:g}")
        elif not (a[c].to_numpy() == b[c].to_numpy()).all():
            probs.append(f"{c} differs")
    return {"equal": not probs, "max_abs_diff_s": mx, "plan_problem": "; ".join(probs)}


def plans_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    return bool(plan_diff(a, b)["equal"])


def toolslow_pairing(run: Run, control: Optional[Path]) -> Dict[str, Any]:
    """plan.csv of a TOOLSLOW run must equal the same-seed NOBURST control's at the cell's rate (byte identity reported)."""
    if control is None:
        return {"paired": False, "control_dir": None,
                "pairing_problem": "no committed NOBURST control for this seed at the cell's rate"}
    if not (Path(run.dir) / "plan.csv").is_file():
        return {"paired": False, "control_dir": str(control), "pairing_problem": "the run has no plan.csv"}
    a, b = _sha(Path(run.dir) / "plan.csv"), _sha(Path(control) / "plan.csv")
    pdiff = plan_diff(_plan(run.dir), _plan(control))
    same = pdiff["equal"]
    return {"paired": same, "control_dir": str(control), "plan_sha256": a, "control_plan_sha256": b,
            "plan_bytes_identical": a == b, "plan_max_abs_diff_s": pdiff["max_abs_diff_s"],
            "pairing_problem": "" if same else f"plan.csv differs from the same-seed NOBURST control's ({pdiff['plan_problem']})"}


# ---------------------------------------------------------------- manipulation check
def _close(x: Any, y: float, tol: float = ADD_ATOL_S) -> bool:
    try:
        return isinstance(x, (int, float)) and not isinstance(x, bool) and abs(float(x) - y) <= tol
    except (TypeError, ValueError):
        return False


def manipulation_check(run: Run, cell: Dict[str, Any]) -> Dict[str, Any]:
    """Did the registered slowdown happen, call by call (see the module docstring)? ``manipulation_ok`` and the counts."""
    t_s, w, delta = float(cell["t_s"]), float(cell["width_s"]), float(cell["add_s"])
    t_e = t_s + w
    out: Dict[str, Any] = {"tool_calls_logged": False, "manipulation_ok": False}
    probs: List[str] = []
    ts = run.meta.get("tool_slowdown") or {}
    if not (isinstance(ts, dict) and all(_close(ts.get(k), v) for k, v in (("t_s", t_s), ("width_s", w), ("add_s", delta)))):
        probs.append(f"meta.tool_slowdown {ts} is not the cell's {{t_s: {t_s:g}, width_s: {w:g}, add_s: {delta:g}}}")
    f = Path(run.dir) / "tool_calls.csv"
    if not f.is_file():
        probs.append("tool_calls.csv missing: the manipulation is not logged")
        out["manipulation_problem"] = "; ".join(probs)
        return out
    tc = pd.read_csv(f, float_precision="round_trip")
    if list(tc.columns) != TOOL_CALL_COLUMNS:
        probs.append(f"tool_calls.csv columns {list(tc.columns)} != {TOOL_CALL_COLUMNS}")
        out["manipulation_problem"] = "; ".join(probs)
        return out
    num = {c: pd.to_numeric(tc[c], errors="coerce").to_numpy(float) for c in ("t_start", "tool_s", "add_s", "t_ready")}
    t0, add = num["t_start"], num["add_s"]
    finite = np.isfinite(t0) & np.isfinite(add) & np.isfinite(num["tool_s"]) & np.isfinite(num["t_ready"])
    inwin = finite & (t0 >= t_s) & (t0 < t_e)
    outwin = finite & ~inwin
    slowed = finite & (add > ADD_ATOL_S)
    n_in_bad = int((inwin & ~(np.abs(add - delta) <= ADD_ATOL_S)).sum())
    n_out_bad = int((outwin & ~(np.abs(add) <= ADD_ATOL_S)).sum())
    ready_dev = np.abs(num["t_ready"] - (t0 + num["tool_s"] + add))
    ready_ok = bool(finite.all() and (ready_dev[finite] <= READY_ATOL_S).all()) if len(tc) else True
    oc = (run.meta.get("outcome") or {}).get("tool_slowdown") or {}
    counts_ok = (oc.get("n_tool_calls") == len(tc) and oc.get("n_tool_calls_slowed") == int(slowed.sum()))
    if not finite.all():
        probs.append(f"{int((~finite).sum())} tool calls with non-numeric times or add_s")
    if not counts_ok:
        probs.append(f"tool_calls.csv is not the complete log: {len(tc)} rows, {int(slowed.sum())} slowed, but "
                     f"meta.outcome.tool_slowdown = {oc}")
    if not inwin.sum():
        probs.append(f"no tool call started inside [{t_s:g}, {t_e:g}): the manipulation did not happen")
    if n_in_bad:
        probs.append(f"{n_in_bad} tool calls starting inside [{t_s:g}, {t_e:g}) have add_s != {delta:g}")
    if n_out_bad:
        probs.append(f"{n_out_bad} tool calls starting outside [{t_s:g}, {t_e:g}) have add_s != 0")
    if not ready_ok:
        probs.append(f"t_ready != t_start + tool_s + add_s (max deviation {float(np.nanmax(ready_dev)):.3g} s)")
    sl_t = t0[slowed]
    in_t = t0[inwin]
    out.update(tool_calls_logged=True, n_tool_calls=int(len(tc)), n_tool_calls_in_window=int(inwin.sum()),
               n_tool_calls_slowed=int(slowed.sum()), n_in_window_add_not_delta=n_in_bad, n_outside_add_nonzero=n_out_bad,
               in_window_t_start_min=float(in_t.min()) if len(in_t) else None,
               in_window_t_start_max=float(in_t.max()) if len(in_t) else None,
               slowed_t_start_min=float(sl_t.min()) if len(sl_t) else None,
               slowed_t_start_max=float(sl_t.max()) if len(sl_t) else None,
               add_s_values=sorted({float(x) for x in add[finite]}), tool_log_complete=bool(counts_ok),
               t_ready_consistent=ready_ok, manipulation_ok=not probs, manipulation_problem="; ".join(probs))
    return out


# ---------------------------------------------------------------- controls
def find_controls(root: str | Path, *, rate_mult: float, label: str = CONTROL_LABEL) -> Dict[tuple, Path]:
    """{(arm, seed): run dir} of the committed E2 NOBURST / BURST runs at ``rate_mult`` (no default: a cell passes its own)."""
    out: Dict[tuple, Path] = {}
    root = Path(root)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if not (d / "meta.json").is_file():
            continue
        r = load_run(d)
        arm = r.arm or r.arm_derived
        if r.label == label and r.rate_mult is not None and math.isclose(r.rate_mult, rate_mult) and arm in ("burst", "noburst"):
            out[(arm, r.seed)] = d
    return out


# ---------------------------------------------------------------- decision
def outcome_of(stuck: int, good: int, need: int) -> str:
    traps, notrap = stuck >= need, good >= need
    if traps and not notrap:
        return "TRAPS"
    if notrap and not traps:
        return "NO-TRAP"
    return "MIXED"


def decision(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Each cell's own registered rule over its counted (completed, bound, paired, manipulated) runs; no conjunction."""
    cells: Dict[str, Dict[str, Any]] = {}
    for label, c in CELLS.items():
        recs = [r for r in rows if r.get("role") == "new" and r.get("label") == label and r.get("counted")
                and int(r["seed"]) in c["seeds"]]
        seeds = [int(r["seed"]) for r in recs]
        got = sorted(set(seeds))
        dup = sorted({s for s in seeds if seeds.count(s) > 1})
        missing = [s for s in c["seeds"] if s not in got]
        need = need_of(c["seeds"])
        stuck = sum(bool(r["stuck"]) for r in recs)
        good = sum(bool(r["good"]) for r in recs)
        if dup:                     # a resubmitted seed must not vote twice: undecided until a human resolves it
            possible: List[str] = []
            outcome = final = None
        else:
            possible = sorted({outcome_of(stuck + sum(s for s, _ in combo), good + sum(g for _, g in combo), need)
                               for combo in itertools.product(_SEED_STATES, repeat=len(missing))}, key=OUTCOMES.index)
            outcome = possible[0] if len(possible) == 1 else None
            final = outcome_of(stuck, good, need)
        cells[c["key"]] = {"label": label, "mult": c["mult"], "rule": c["rule"], "seeds": list(c["seeds"]), "need": need,
                           "seeds_present": got, "missing_seeds": missing, "duplicate_seeds": dup, "stuck": stuck,
                           "good": good, "stuck_seeds": sorted(int(r["seed"]) for r in recs if r["stuck"]),
                           "good_seeds": sorted(int(r["seed"]) for r in recs if r["good"]),
                           "possible_outcomes": possible, "outcome": outcome, "outcome_if_missing_count_against": final}
    return {"cells": cells,
            "note": "per cell, no conjunction: outcome is TRAPS / NO-TRAP / MIXED once no result of the missing seeds could "
                    "change it, None before (and None, with outcome_if_missing_count_against None, while a seed has two "
                    "counted runs); outcome_if_missing_count_against is the call if the missing seeds never come"}


# ---------------------------------------------------------------- classification
def classify(run_dirs: Iterable[str | Path], ep: Dict[str, Any], p: AnalysisParams, *, preregs: Sequence[str | Path] = (),
             control_root: str | Path = REPO / CONTROL_ROOT) -> Dict[str, Any]:
    pr_by_label = {}
    for f in preregs:
        pr = prereg_mod.load_prereg(f)
        pr_by_label[(pr.get("inputs") or {}).get("engine_cell_label")] = (pr, prereg_mod.file_provenance(f), str(f))
    mults = sorted({float(c["mult"]) for c in CELLS.values()})
    controls = {m: find_controls(control_root, rate_mult=m) for m in mults}
    rows: List[Dict[str, Any]] = []
    for d in run_dirs:
        r = load_run(d)
        c = CELLS.get(r.label)
        rec: Dict[str, Any] = {"role": "new", "run_dir": str(r.dir), "label": r.label, "seed": r.seed}
        if c is None:
            rec.update(counted=False, problem=f"label {r.label!r} is not an r15 cell")
            rows.append(rec)
            continue
        rec.update(basin.classify_run(r, p, ep))
        rec.update(role="new", cell=c["key"], cell_mult=c["mult"], aborted=r.aborted, abort_reason=r.abort_reason)
        probs = []
        arm = r.arm or r.arm_derived
        if arm != c["arm"]:
            probs.append(f"arm {arm!r} != the cell's {c['arm']!r}")
        if r.rate_mult is None or not math.isclose(r.rate_mult, c["mult"]):
            probs.append(f"rate_mult {r.rate_mult} != the cell's {c['mult']}")
        if r.seed not in c["seeds"]:
            probs.append(f"seed {r.seed} is not a registered seed {list(c['seeds'])}")
        if not rec["window_matches_endpoints"]:
            probs.append("evaluation window does not match the frozen endpoints")
        if r.aborted:
            probs.append(f"run aborted ({r.abort_reason})")
        rec.update(toolslow_pairing(r, controls[float(c["mult"])].get(("noburst", r.seed))))
        if not rec.get("paired"):
            probs.append(rec.get("pairing_problem") or "not paired")
        rec.update(manipulation_check(r, c))
        if not rec["manipulation_ok"]:
            probs.append("manipulation check failed: " + rec["manipulation_problem"])
        reg = pr_by_label.get(r.label)
        if reg is not None:
            bl = prereg_mod.run_blockers(reg[0], reg[1], r)
            rec.update(prereg_file=reg[2], prereg_bound=not bl, prereg_blockers="; ".join(bl))
            if bl:
                probs.append("not bound to its registration: " + "; ".join(bl))
        else:   # a run is counted only when its binding was checked (the CLI defaults --prereg to the two registrations)
            rec.update(prereg_file=None, prereg_bound=None, prereg_blockers="no --prereg for this label")
            probs.append("binding not checked: no --prereg for this label")
        rec["problem"] = "; ".join(probs)
        rec["counted"] = not probs
        rows.append(rec)
    for m in mults:
        for (arm, seed), d in sorted(controls[m].items()):
            r = load_run(d)
            rec = basin.classify_run(r, p, ep)
            rec.update(role=f"control_{arm}", control_mult=m, counted=False)
            rows.append(rec)
    by_seed: Dict[str, Dict[str, Any]] = {}
    for rec in rows:
        if rec.get("basin_state") is None:
            continue
        key = rec.get("cell") or f"{rec['role']}@{rec['control_mult']:g}"
        by_seed.setdefault(str(rec["seed"]), {})[key] = rec["basin_state"]
    return {"rows": rows, "by_seed": by_seed, "decision": decision(rows),
            "endpoint_problems": basin.endpoint_problems(ep, p)}


_COLS = ("role", "cell", "seed", "label", "rate_mult", "cell_mult", "control_mult", "arm", "basin_state", "stuck", "good",
         "good_by_recovered", "good_by_hit_slope", "state", "trapped", "hit_eval", "backlog_slope", "slope_threshold", "lambda",
         "hit_end", "outstanding_end", "eval_from", "t_end_s", "window_matches_endpoints", "paired", "plan_bytes_identical",
         "plan_max_abs_diff_s", "pairing_problem", "control_dir", "tool_calls_logged", "tool_log_complete", "n_tool_calls",
         "n_tool_calls_in_window", "n_tool_calls_slowed", "n_in_window_add_not_delta", "n_outside_add_nonzero",
         "in_window_t_start_min", "in_window_t_start_max", "slowed_t_start_min", "slowed_t_start_max", "t_ready_consistent",
         "manipulation_ok", "manipulation_problem", "prereg_bound", "prereg_blockers", "counted", "problem", "run_dir")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r15_cells")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="per-run STUCK / GOOD of the r15 TOOLSLOW runs, CRN pairs, each cell's own rule")
    c.add_argument("--run-dirs", nargs="+", required=True)
    c.add_argument("--prereg", nargs="*", default=[str(REPO / c_["out"]) for c_ in r15_prereg.CELLS.values()],
                   help="the r15 registrations (binding of each run, by label; default: the two r15 files)")
    c.add_argument("--control-root", default=str(REPO / CONTROL_ROOT))
    c.add_argument("--endpoints", default=str(REPO / ENDPOINTS))
    c.add_argument("--params", default=str(REPO / PARAMS))
    c.add_argument("--set", action="append", default=[])
    c.add_argument("--out-root", default="results")
    args = ap.parse_args(argv)
    from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta
    t0 = datetime.now()
    git = git_info(REPO)
    p = load_params(args.params, [f"trap_v2.eval_from_s={REGISTERED_EVAL_FROM_S}", *args.set])
    ep = basin.load_endpoints(args.endpoints)
    res = classify(args.run_dirs, ep, p, preregs=args.prereg, control_root=args.control_root)
    d = new_result_dir(args.out_root, "agentload_analysis_r15")
    df = pd.DataFrame(res["rows"])
    df[[k for k in _COLS if k in df.columns]].to_csv(d / "r15_runs.csv", index=False)
    verdict = {k: res[k] for k in ("by_seed", "decision", "endpoint_problems")}
    verdict["endpoints"] = ep
    (d / "r15_verdict.json").write_text(json.dumps(verdict, indent=2, default=json_default))
    write_meta(d, build_meta(experiment="agentload_analysis_r15", argv=[sys.executable, "-m", "analysis.r15_cells",
                                                                        *(argv or sys.argv[1:])],
                             seeds=sorted({int(r["seed"]) for r in res["rows"] if r.get("seed") is not None}),
                             hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(), status="finished",
                             extra={"run_dirs": [str(x) for x in args.run_dirs], "prereg": list(args.prereg),
                                    "control_root": str(args.control_root)}))
    print(json.dumps(verdict["decision"], indent=2, default=json_default))
    for msg in res["endpoint_problems"]:
        print(f"ENDPOINT PROBLEM: {msg}", file=sys.stderr)
    print(f"r15 outputs: {d}")
    return 1 if res["endpoint_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
