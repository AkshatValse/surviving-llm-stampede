"""r14 extra cells: TOOLSLOW (remedy plan N3) and SHED (remedy plan N4), classified with the frozen B1 endpoints.

Cells (registrations configs/agentload_prereg_2026-10-31_{toolslow_d10,toolslow_d30,shed_t600,shed_t3600}.yaml, made by
``analysis.r14_prereg fill``; SGLang FCFS with waiting-prefix refresh, 300k pool, Qwen2.5-7B, A100 80GB PCIe, 1.35 x lambda_ref):

  sglang-fcfs-r1-toolslow-d10 / -d30   arm noburst, seeds 0-2: tool calls starting in [1200, 2100) s take +10 s / +30 s
  sglang-fcfs-r1-shed-t600 / -t3600    arm burst, seeds 0-1: burst of 200 at 1200 s, arrivals stopped over [1800, 1800 + tau)

Per run STUCK / GOOD exactly as configs/r11_basin_predict.yaml defines them (``analysis.basin.load_endpoints`` and
``analysis.basin.classify_run``, unchanged), over [5700, 8700) s:
  STUCK := hit_eval < 0.2;  GOOD := trap_v2 RECOVERED, or (hit_eval > 0.8 and backlog slope <= 0.5 x (lambda - lambda_miss)).
A SHED run's lambda is its post-stop rate (``analysis.load.Run.lam`` of a ramp run = its last knot), which this module checks is
the ramp's rate over the whole evaluation window.

Pairing (per seed, common random numbers) with the committed 300k E2 runs at 1.35 x (jobs 17093387-404,
results/nova/e2_170933xx_pulled_20261025-144558): TOOLSLOW with the same-seed NOBURST run (plan.csv must be byte-identical)
and, for context, the same-seed BURST run; SHED with the same-seed BURST run (its base arrivals outside the stop, and its burst
sessions, must equal the SHED plan's). Sessions shed := base arrivals of the BURST control in [1800, 1800 + tau + 0.001) that
the SHED plan lacks. R1 (the rescue cap, configs/agentload_prereg_2026-10-31_rescue.yaml) sheds 0 sessions by construction
(it defers sessions at the gate and drops none); optional --r1-dirs adds the R1 runs at 1.35 x, classified with the same
endpoints over the same window, beside the SHED pairs.

Registered decision rules (verbatim from the registrations' lambda_selection.rule):
  TOOLSLOW  'causal test of the gap: d10 GOOD in >=2/3 seeds and d30 STUCK in >=2/3'   (seeds 0, 1, 2: 2 of 3 each)
  SHED      'tau600 STUCK in >=2/3 and tau3600 GOOD in >=2/3; sessions shed reported; compared with R1 (0 shed)'
            (seeds 0, 1: 2 of 2 each)
A seed without a completed run counts against; a run not bound to its registration (``analysis.prereg.run_blockers``; the CLI
defaults --prereg to the four committed registrations, and a run whose binding was not checked is not counted) is reported and
not counted. A run counts only if its manipulation happened (TOOLSLOW: slowed tool calls logged, all started inside the window;
SHED: no base arrival inside the stop). Two counted runs of one seed leave that cell undecided (None), so no seed votes twice.
(Review fixes after r14-extra-reg, before any job of these cells: stricter only.)

CLI:  python -m analysis.r14_cells classify --run-dirs RUN [RUN ...] [--prereg FILE ...] [--control-root DIR]
                                            [--r1-dirs RUN ...] [--endpoints configs/r11_basin_predict.yaml] [--out-root results]
"""
from __future__ import annotations

import argparse
import hashlib
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
from . import r14_prereg
from .load import Run, load_run
from .params import AnalysisParams, load_params

REPO = Path(__file__).resolve().parent.parent
ENDPOINTS = "configs/r11_basin_predict.yaml"
PARAMS = "configs/agentload_analysis.yaml"
CONTROL_ROOT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst"
CONTROL_LABEL = "sglang-fcfs-r1"
MULT = 1.35
REGISTERED_EVAL_FROM_S = 4500.0
T_STOP = 1800.0
STOP_EDGE_S = 0.001                     # the ramp's knot spacing at both ends of the stop

CELLS: Dict[str, Dict[str, Any]] = {
    "sglang-fcfs-r1-toolslow-d10": {"family": "toolslow", "key": "d10", "add_s": 10.0, "arm": "noburst", "seeds": (0, 1, 2),
                                    "e2": "configs/agentload_e2_toolslow_d10.yaml"},
    "sglang-fcfs-r1-toolslow-d30": {"family": "toolslow", "key": "d30", "add_s": 30.0, "arm": "noburst", "seeds": (0, 1, 2),
                                    "e2": "configs/agentload_e2_toolslow_d30.yaml"},
    "sglang-fcfs-r1-shed-t600": {"family": "shed", "key": "t600", "tau_s": 600.0, "arm": "burst", "seeds": (0, 1),
                                 "e2": "configs/agentload_e2_shed_t600.yaml"},
    "sglang-fcfs-r1-shed-t3600": {"family": "shed", "key": "t3600", "tau_s": 3600.0, "arm": "burst", "seeds": (0, 1),
                                  "e2": "configs/agentload_e2_shed_t3600.yaml"},
}
RULES = {"toolslow": "causal test of the gap: d10 GOOD in >=2/3 seeds and d30 STUCK in >=2/3",
         "shed": "tau600 STUCK in >=2/3 and tau3600 GOOD in >=2/3; sessions shed reported; compared with R1 (0 shed)"}
R1_SESSIONS_SHED = 0


def need_of(seeds: Sequence[int]) -> int:
    return math.ceil(2 * len(seeds) / 3)


# ---------------------------------------------------------------- plan pairing
def _plan(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(Path(run_dir) / "plan.csv", float_precision="round_trip")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plans_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Same sessions (sid, origin, idx, n_turns), same arrival times exactly, tool-time totals within 1e-9 s (numpy's
    exponential can differ in the last bit between platforms: Windows vs Linux libm)."""
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return False
    for c in ("sid", "origin", "idx", "n_turns", "arrival_s"):
        if not (a[c].to_numpy() == b[c].to_numpy()).all():
            return False
    return bool(np.allclose(a["tool_time_total_s"].to_numpy(), b["tool_time_total_s"].to_numpy(), rtol=0, atol=1e-9))


def toolslow_pairing(run: Run, control: Optional[Path]) -> Dict[str, Any]:
    """plan.csv of a TOOLSLOW run must equal the same-seed NOBURST control's (on Nova: byte for byte, also reported)."""
    if control is None:
        return {"paired": False, "pairing_problem": "no committed NOBURST control for this seed"}
    a, b = _sha(run.dir / "plan.csv"), _sha(Path(control) / "plan.csv")
    same = a == b or plans_equal(_plan(run.dir), _plan(control))
    return {"paired": same, "plan_sha256": a, "control_plan_sha256": b, "plan_bytes_identical": a == b,
            "pairing_problem": "" if same else "plan.csv differs from the NOBURST control's"}


def shed_pairing(run: Run, control: Optional[Path], tau: float) -> Dict[str, Any]:
    """Base arrivals outside the stop and the burst sessions equal the same-seed BURST control's; sessions shed counted."""
    if control is None:
        return {"paired": False, "pairing_problem": "no committed BURST control for this seed", "sessions_shed": None}
    p, c = _plan(run.dir), _plan(control)
    lo, hi = T_STOP, T_STOP + tau + STOP_EDGE_S
    out_c = lambda df: df[(df["arrival_s"] < lo) | (df["arrival_s"] >= hi)]          # noqa: E731
    pb, cb = p[p["origin"] == "base"], c[c["origin"] == "base"]
    same_outside = np.array_equal(np.sort(out_c(pb)["arrival_s"].to_numpy()), np.sort(out_c(cb)["arrival_s"].to_numpy()))
    same_burst = np.array_equal(np.sort(p[p["origin"] == "burst"]["arrival_s"].to_numpy()),
                                np.sort(c[c["origin"] == "burst"]["arrival_s"].to_numpy()))
    in_c = cb[(cb["arrival_s"] >= lo) & (cb["arrival_s"] < hi)]["arrival_s"]
    in_p = pb[(pb["arrival_s"] >= lo) & (pb["arrival_s"] < hi)]["arrival_s"]
    shed = int(len(set(in_c) - set(in_p)))
    probs = [m for ok, m in ((same_outside, "base arrivals outside the stop differ from the BURST control's"),
                             (same_burst, "burst sessions differ from the BURST control's")) if not ok]
    return {"paired": not probs, "pairing_problem": "; ".join(probs), "sessions_shed": shed,
            "control_base_arrivals_in_stop": int(len(in_c)), "run_base_arrivals_in_stop": int(len(in_p)),
            "run_base_sessions": int(len(pb)), "control_base_sessions": int(len(cb))}


def ramp_flat_over_window(run: Run, w0: float, w1: float) -> bool:
    """True if the run's ramp rate equals run.lam everywhere on [w0, w1] (constant runs: True)."""
    if (run.cfg.get("arrivals") or {}).get("kind") != "ramp":
        return True
    knots = run.meta.get("ramp_knots") or []
    if not knots or run.lam is None:
        return False
    from agentload.workload import ramp_rate
    ts = [w0, w1] + [float(t) for t, _ in knots if w0 <= float(t) <= w1]
    return bool(np.allclose(ramp_rate(np.array(ts), [(float(t), float(r)) for t, r in knots]), run.lam, rtol=1e-12, atol=0))


def tool_call_summary(run: Run) -> Dict[str, Any]:
    f = run.dir / "tool_calls.csv"
    if not f.is_file():
        return {"tool_calls_logged": False}
    tc = pd.read_csv(f, float_precision="round_trip")
    sl = tc[tc["add_s"] > 0]
    return {"tool_calls_logged": True, "n_tool_calls": int(len(tc)), "n_tool_calls_slowed": int(len(sl)),
            "slowed_t_start_min": float(sl["t_start"].min()) if len(sl) else None,
            "slowed_t_start_max": float(sl["t_start"].max()) if len(sl) else None,
            "add_s_values": sorted({float(x) for x in sl["add_s"]})}


# ---------------------------------------------------------------- controls
def find_controls(root: str | Path, label: str = CONTROL_LABEL, rate_mult: float = MULT) -> Dict[tuple, Path]:
    """{(arm, seed): run dir} of the committed E2 NOBURST / BURST runs at ``rate_mult``."""
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
def decision(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The two registered rules over the counted (cell, completed, bound when checked, paired) runs."""
    cells: Dict[str, Dict[str, Any]] = {}
    for label, c in CELLS.items():
        recs = [r for r in rows if r.get("role") == "new" and r["label"] == label and r.get("counted")]
        got = sorted({int(r["seed"]) for r in recs})
        dup = sorted({int(r["seed"]) for r in recs if sum(int(x["seed"]) == int(r["seed"]) for x in recs) > 1})
        cells[c["key"]] = {"label": label, "family": c["family"], "seeds": list(c["seeds"]), "need": need_of(c["seeds"]),
                           "seeds_present": got, "missing_seeds": [s for s in c["seeds"] if s not in got],
                           "duplicate_seeds": dup,
                           "stuck": sum(bool(r["stuck"]) for r in recs if int(r["seed"]) in c["seeds"]),
                           "good": sum(bool(r["good"]) for r in recs if int(r["seed"]) in c["seeds"])}
        if c["family"] == "shed":
            cells[c["key"]]["sessions_shed_by_seed"] = {str(r["seed"]): r.get("sessions_shed") for r in recs}

    def tri(cell: Dict[str, Any], key: str) -> Optional[bool]:
        if cell["duplicate_seeds"]:              # a resubmitted seed must not vote twice: undecided until a human resolves it
            return None
        if cell[key] >= cell["need"]:
            return True
        if cell[key] + len(cell["missing_seeds"]) < cell["need"]:
            return False
        return None

    def both(a: Optional[bool], b: Optional[bool]) -> Optional[bool]:
        if a is False or b is False:
            return False
        return True if (a and b) else None

    ts = {"rule": RULES["toolslow"], "d10_good_majority": tri(cells["d10"], "good"),
          "d30_stuck_majority": tri(cells["d30"], "stuck")}
    ts["pass"] = both(ts["d10_good_majority"], ts["d30_stuck_majority"])
    sh = {"rule": RULES["shed"], "t600_stuck_majority": tri(cells["t600"], "stuck"),
          "t3600_good_majority": tri(cells["t3600"], "good"), "r1_sessions_shed": R1_SESSIONS_SHED}
    sh["pass"] = both(sh["t600_stuck_majority"], sh["t3600_good_majority"])
    return {"cells": cells, "toolslow": ts, "shed": sh,
            "note": "pass is True / False once the present seeds decide it, None while missing seeds could still change it"}


# ---------------------------------------------------------------- classification
def classify(run_dirs: Iterable[str | Path], ep: Dict[str, Any], p: AnalysisParams, *, preregs: Sequence[str | Path] = (),
             control_root: str | Path = REPO / CONTROL_ROOT, r1_dirs: Iterable[str | Path] = ()) -> Dict[str, Any]:
    pr_by_label = {}
    for f in preregs:
        pr = prereg_mod.load_prereg(f)
        pr_by_label[(pr.get("inputs") or {}).get("engine_cell_label")] = (pr, prereg_mod.file_provenance(f), str(f))
    controls = find_controls(control_root)
    w0, w1 = ep["eval_window_s"]
    rows: List[Dict[str, Any]] = []
    for d in run_dirs:
        r = load_run(d)
        c = CELLS.get(r.label)
        rec: Dict[str, Any] = {"role": "new", "run_dir": str(r.dir), "label": r.label, "seed": r.seed}
        if c is None:
            rec.update(counted=False, problem=f"label {r.label!r} is not an r14 cell")
            rows.append(rec)
            continue
        rec.update(basin.classify_run(r, p, ep))
        rec.update(role="new", family=c["family"], cell=c["key"], aborted=r.aborted, abort_reason=r.abort_reason)
        probs = []
        arm = r.arm or r.arm_derived
        if arm != c["arm"]:
            probs.append(f"arm {arm!r} != the cell's {c['arm']!r}")
        if r.rate_mult is None or not math.isclose(r.rate_mult, MULT):
            probs.append(f"rate_mult {r.rate_mult} != {MULT}")
        if not rec["window_matches_endpoints"]:
            probs.append("evaluation window does not match the frozen endpoints")
        if c["family"] == "toolslow":
            rec.update(toolslow_pairing(r, controls.get(("noburst", r.seed))))
            rec.update(tool_call_summary(r))
            ts = r.meta.get("tool_slowdown") or {}
            if not (ts and math.isclose(float(ts.get("add_s", -1)), c["add_s"])):
                probs.append(f"meta.tool_slowdown {ts} does not apply add_s = {c['add_s']}")
            # the manipulation must have happened: slowed calls logged, all of them started inside [t_s, t_s + width_s)
            if not rec.get("n_tool_calls_slowed"):
                probs.append("no tool call was slowed (tool_calls.csv missing or empty): the manipulation did not happen")
            elif ts:
                t_s, t_e = float(ts.get("t_s", 0.0)), float(ts.get("t_s", 0.0)) + float(ts.get("width_s", 0.0))
                if not (t_s <= rec["slowed_t_start_min"] and rec["slowed_t_start_max"] < t_e):
                    probs.append(f"slowed tool calls started outside [{t_s}, {t_e})")
        else:
            rec.update(shed_pairing(r, controls.get(("burst", r.seed)), c["tau_s"]))
            rec["ramp_flat_over_window"] = ramp_flat_over_window(r, w0, w1)
            if not rec["ramp_flat_over_window"]:
                probs.append("the ramp is not at the post-stop rate over the whole evaluation window")
            if rec.get("run_base_arrivals_in_stop") not in (0, None):   # the manipulation must have happened
                probs.append(f"{rec['run_base_arrivals_in_stop']} base arrivals inside the stop: arrivals did not stop")
        if not rec.get("paired"):
            probs.append(rec.get("pairing_problem") or "not paired")
        reg = pr_by_label.get(r.label)
        if reg is not None:
            bl = prereg_mod.run_blockers(reg[0], reg[1], r)
            rec.update(prereg_file=reg[2], prereg_bound=not bl, prereg_blockers="; ".join(bl))
            if bl:
                probs.append("not bound to its registration: " + "; ".join(bl))
        else:   # a run is counted only when its binding was checked (the CLI defaults --prereg to the four registrations)
            rec.update(prereg_file=None, prereg_bound=None, prereg_blockers="no --prereg for this label")
            probs.append("binding not checked: no --prereg for this label")
        rec["problem"] = "; ".join(probs)
        rec["counted"] = not probs and not r.aborted
        rows.append(rec)
    for (arm, seed), d in sorted(controls.items()):
        r = load_run(d)
        rec = basin.classify_run(r, p, ep)
        rec.update(role=f"control_{arm}", counted=False)
        rows.append(rec)
    for d in r1_dirs:
        r = load_run(d)
        rec = basin.classify_run(r, p, ep)
        rec.update(role="r1_rescue", counted=False, sessions_shed=R1_SESSIONS_SHED)
        rows.append(rec)
    by_seed: Dict[str, Dict[str, Any]] = {}
    for rec in rows:
        if rec.get("basin_state") is None:
            continue
        key = rec.get("cell") or rec["role"]
        by_seed.setdefault(str(rec["seed"]), {})[key] = rec["basin_state"]
    return {"rows": rows, "by_seed": by_seed, "decision": decision(rows),
            "endpoint_problems": basin.endpoint_problems(ep, p)}


_COLS = ("role", "cell", "family", "seed", "label", "rate_mult", "arm", "basin_state", "stuck", "good", "good_by_recovered",
         "good_by_hit_slope", "state", "trapped", "hit_eval", "backlog_slope", "slope_threshold", "lambda", "hit_end",
         "outstanding_end", "eval_from", "t_end_s", "window_matches_endpoints", "paired", "pairing_problem", "sessions_shed",
         "control_base_arrivals_in_stop", "run_base_arrivals_in_stop", "ramp_flat_over_window", "n_tool_calls",
         "n_tool_calls_slowed", "slowed_t_start_min", "slowed_t_start_max", "prereg_bound", "prereg_blockers", "counted",
         "problem", "run_dir")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r14_cells")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="per-run STUCK / GOOD of the TOOLSLOW and SHED runs, CRN pairs, the registered rules")
    c.add_argument("--run-dirs", nargs="+", required=True)
    c.add_argument("--prereg", nargs="*", default=[str(REPO / c_["out"]) for c_ in r14_prereg.CELLS.values()],
                   help="the r14 registrations (binding of each run, by label; default: the four committed files)")
    c.add_argument("--control-root", default=str(REPO / CONTROL_ROOT))
    c.add_argument("--r1-dirs", nargs="*", default=[], help="optional: R1 rescue runs at 1.35 x, reported beside SHED")
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
    res = classify(args.run_dirs, ep, p, preregs=args.prereg, control_root=args.control_root, r1_dirs=args.r1_dirs)
    d = new_result_dir(args.out_root, "agentload_analysis_r14")
    df = pd.DataFrame(res["rows"])
    df[[k for k in _COLS if k in df.columns]].to_csv(d / "r14_runs.csv", index=False)
    verdict = {k: res[k] for k in ("by_seed", "decision", "endpoint_problems")}
    verdict["endpoints"] = ep
    (d / "r14_verdict.json").write_text(json.dumps(verdict, indent=2, default=json_default))
    write_meta(d, build_meta(experiment="agentload_analysis_r14", argv=[sys.executable, "-m", "analysis.r14_cells",
                                                                        *(argv or sys.argv[1:])],
                             seeds=sorted({int(r["seed"]) for r in res["rows"] if r.get("seed") is not None}),
                             hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(), status="finished",
                             extra={"run_dirs": [str(x) for x in args.run_dirs], "prereg": list(args.prereg),
                                    "control_root": str(args.control_root), "r1_dirs": list(args.r1_dirs)}))
    print(json.dumps(verdict["decision"], indent=2, default=json_default))
    for msg in res["endpoint_problems"]:
        print(f"ENDPOINT PROBLEM: {msg}", file=sys.stderr)
    print(f"r14 outputs: {d}")
    return 1 if res["endpoint_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
