"""r16 MIRROR: a blind hardware test of model F's renewal law on a workload for which it predicts the youth premium REVERSED.

Cell sglang-fcfs-r1-mirror-k20: the measured cell sglang-fcfs-r1 (SGLang 0.5.22 FCFS, waiting-prefix refresh on, 300k pool,
Qwen2.5-7B-Instruct, A100 80GB PCIe) with a STEP-CAPPED agent workload: configs/agentload_e2_mirror_k20.yaml is
configs/agentload_e2_burst.yaml with exactly two values changed, workload.mean_turns 15 -> 1000 and max_turns 60 -> 20, so
T = min(Geometric(1/1000), 20) and about 98% of sessions run exactly 20 turns (agents that run to their step budget).

THEORY UNDER TEST (notes/THEORY_ICML_2026-11.md; frozen numbers in results/theory/r16/mirror_predictions.json, written by
analysis/theory/icml/mirror_predict.py in the registration commit).  Theorem 2: a trapped engine completes sessions at
D = lambda_miss H(z) Gamma(z).  For the standard workload (geometric T) H ~ 1 and the cost growth makes D > lambda_miss (the
youth premium, +23% at 1.65x).  For a nearly deterministic T, H(z) << 1 outweighs Gamma(z) > 1: model F predicts the trapped
engine completes sessions BELOW its all-miss capacity (D / lambda_miss = 0.77 at 1.65x, asymptotically).  The exact
plan-driven FIFO adds the transient: the 200-session burst cohort needs 20 FIFO cycles, each longer than the last, before any
of it completes, so completions nearly stop for about 40 min after the burst, then come as a WAVE when the cohort finishes,
then stay below capacity while the backlog grows faster than the excess load.  Every throughput-curve reading (quasi-static:
completions at lambda_miss whenever trapped; Lu et al.'s fluid dN/dt = lambda - X(N)/K; the paper's Eq. (fluid)) predicts
steady completions near the all-miss capacity: no blackout, no wave.

PROTOCOL  the E2 BURST protocol (burst of 200 sessions in [1200, 1260) s, 8700-s runs, one run per job, seeds 0-2) at
          1.65 x lambda_ref (DECISIVE cell) and 1.35 x lambda_ref (SECONDARY cell), lambda_ref = lambda_miss_turns_based of the
          STANDARD workload's registered E0a (prereg/inputs/2026-10-23/calibration.json; it only places the rates).  Paired
          NOBURST controls at 1.65 x (same plans without the burst).  One E0a run of the step-capped workload (MODE=miss with
          GEN_EXTRA setting the same two values) measures its all-miss capacity; no threshold below uses it.
MEASURES  per run, from its own files: completions per second (sessions with status completed and t_end in the window, as
          r15_cut.completion_rate) over BLACKOUT = [2400, 3600) and LATE = [6600, 8700); the WAVE TIME, the median t_end of the
          burst sessions (origin burst) completed by 8700 s (undefined if fewer than 100 completed); the OLS slope S of the
          10-s-bin backlog N(t) over [6000, 8700) (r15_cut.n_grid / grid_slope); STUCK / GOOD exactly as
          configs/r11_basin_predict.yaml defines them (analysis.basin.classify_run, unchanged); 300-s completion bins and the
          mean prompt of the turns completed over [5700, 8700) (analysis.theory.icml.measured.window_stats), reported.
RULES     (per counted BURST run; rates in units of lambda_ref; F = the frozen per-seed model-F value of that cell)
          M1 blackout   completions over BLACKOUT <= 0.30           (model F 0.00-0.09; quasi-static 1.05)
          M2 wave       |wave time - F| <= 0.15 x (F - 1200 s)      (model F's raw prediction; on the committed STANDARD runs
                                                                     model F times burst completions 8% late: factor 0.922)
          M3 below      completions over LATE <= 0.85               (model F 0.49-0.73; quasi-static 1.05)
          M4 growth     |S - S_F| < |S - S_QS|,  S_QS = lambda_plan(6000, 8700) - lambda_miss_model
          seed call     RENEWAL iff the run is STUCK and M1-M4 hold; CURVE iff completions over BLACKOUT and LATE are both
                        >= 0.85 (the throughput-curve signature); NOT-TRAPPED iff the run is not STUCK; else MIXED.
          cell verdict  PASS iff RENEWAL in >= 2 of the 3 registered seeds; FAIL iff CURVE in >= 2 of 3; NO-TRAP iff
                        NOT-TRAPPED in >= 2 of 3 (the trap itself was not reached: model F untested, the paper's basin
                        prediction wrong); else MIXED.  UNDECIDED if a seed has two counted runs; PENDING while a registered
                        seed has no counted run and no verdict is reached.
          The 1.65 x cell is decisive; the 1.35 x cell is decided by the same rules as a SECONDARY cell.
SECONDARY (registered, reported, not in the verdict)  W5 calibrated wave: |wave time - F_cal| <= 0.05 x (F_cal - 1200),
          F_cal = 1200 + 0.922 (F - 1200); W6 order: per seed with both cells counted, wave(1.35x) < wave(1.65x); W7 composition:
          mean prompt over [5700, 8700) within 5% of F; W8 late level: |LATE - F| <= 0.25; W9 controls: every NOBURST run GOOD
          (the paper's basin model: n1 = 14.3, n_u = 41.8 at 1.65x); W10 capacity: the E0a lambda_miss of this workload / lambda_ref,
          against the model's 1.046, and LATE below it.
COUNTED   a run counts iff it is the registered cell's (label, arm, rate_mult 1.65 or 1.35, registered seed), completed (meta status
          finished, run end >= 8700 s, not aborted), bound to its registration (analysis.prereg.run_blockers empty), and its
          plan.csv equals the frozen plan (results/theory/r16/mirror_plans; sid, origin, idx, n_turns exact; arrival_s and
          tool_time_total_s within 1e-9 s).

CLI:  python -m analysis.r16_mirror fill [--out FILE]          (the registration, as r15_cut fills CUT's)
      python -m analysis.r16_mirror diff [--file FILE]         (scripted diff against the 2026-10-24 registration)
      python -m analysis.r16_mirror selfcheck                  (frozen plans vs the config; the rules on synthetic records)
      python -m analysis.r16_mirror sbatch-lines               (prints the submit lines; never submits)
      python -m analysis.r16_mirror classify --run-dirs RUN [RUN ...] --prereg FILE [--pred-git REF:PATH] [--e0a-calib FILE]
                                             [--out-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from . import basin
from . import prereg as prereg_mod
from .load import load_run
from .params import AnalysisParams, load_params
from .r15_cut import (R14_SHED_SUBMIT_LINE, completion_rate, grid_slope, n_grid, parse_submit_line, plan_rate, read_plan,
                      registration_diff)

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = "configs/agentload_prereg_template.yaml"
PARAMS = "configs/agentload_analysis.yaml"
PARENT = "configs/agentload_prereg_2026-10-24.yaml"
INPUTS = "prereg/inputs/2026-10-23"
MEASURED = "sglang-fcfs-r1"
ENDPOINTS = "configs/r11_basin_predict.yaml"
HARDWARE = "NVIDIA A100 80GB PCIe, 81920 MiB"
LABEL = "sglang-fcfs-r1-mirror-k20"
E2 = "configs/agentload_e2_mirror_k20.yaml"
OUT = "configs/agentload_prereg_2026-11-05_mirror_k20.yaml"
MULTS = (1.35, 1.65)
DECISIVE, SECONDARY_MULT = 1.65, 1.35
SEEDS = (0, 1, 2)
NEED = 2
T_BURST_S, DURATION_S = 1200.0, 8700.0
BLACKOUT_S, LATE_S, SLOPE_S, COMP_S = (2400.0, 3600.0), (6600.0, 8700.0), (6000.0, 8700.0), (5700.0, 8700.0)
BLACKOUT_MAX, LATE_MAX, CURVE_MIN = 0.30, 0.85, 0.85
WAVE_TOL_REL, WAVE_TOL_REL_CAL, P_TOL_REL, LATE_TOL_ABS = 0.15, 0.05, 0.05, 0.25
MIN_BURST_DONE = 100
PLAN_ATOL_S = 1e-9
REGISTERED_EVAL_FROM_S = 4500.0          # the E2 protocol's hit-evaluation start (trap_v2.eval_from_s), as in r15_cut
REG_TAG = "r16-mirror-reg"
CLONE_DIR = "/work/classtmp/avalse/swapp/repo_r16_mirror"
PRED_PATH = "results/theory/r16/mirror_predictions.json"
PLAN_DIR = "results/theory/r16/mirror_plans"
JOB_NAMES = {(1.65, "burst"): "pm-mir165b", (1.65, "noburst"): "pm-mir165n", (1.35, "burst"): "pm-mir135b"}
E0A_GEN_EXTRA = "--set workload.mean_turns=1000 --set workload.max_turns=20"

RENEWAL, CURVE, NOT_TRAPPED, MIXED = "RENEWAL", "CURVE", "NOT-TRAPPED", "MIXED"


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


# ================================================================ registration
def rule_text() -> str:
    return ("r16 MIRROR cell " + LABEL + ": the E2 protocol (burst of 200 in [1200, 1260) s, 8700-s runs, one arm per job, seeds "
            "0-2) with the step-capped workload of " + E2 + " (mean_turns 1000, max_turns 20); arms burst at 1.65 x (DECISIVE) and "
            "1.35 x (SECONDARY) lambda_ref, noburst at 1.65 x (controls). Per counted BURST run: M1 completions over [2400, 3600) "
            "<= 0.30 lambda_ref; M2 |median t_end of the burst sessions - model F's frozen per-seed value F| <= 0.15 (F - 1200 s); "
            "M3 completions over [6600, 8700) <= 0.85 lambda_ref; M4 the backlog slope over [6000, 8700) is closer to model F's "
            "than to the quasi-static lambda_plan - lambda_miss_model. RENEWAL iff STUCK and M1-M4; CURVE iff both completion "
            "rates >= 0.85 lambda_ref; NOT-TRAPPED iff not STUCK; else MIXED. A cell PASSES iff RENEWAL in >= 2 of 3 seeds, FAILS "
            "iff CURVE in >= 2 of 3, is NO-TRAP iff NOT-TRAPPED in >= 2 of 3, else MIXED. Frozen predictions: " + PRED_PATH +
            " at tag " + REG_TAG + "; full rules: analysis/r16_mirror.py.")


def fill_registration(*, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                   # noqa: E731
    e2_cfg = yaml.safe_load(rd(E2))
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{INPUTS}/mu_curve.json")), json.loads(rd(f"{INPUTS}/calibration.json")),
        e0b=json.loads(rd(f"{INPUTS}/lambda_cap_bracket.json")), e2_cfg=e2_cfg, lambda_mults=list(MULTS),
        rule=rule_text(), engine_cell_label=MEASURED, mu_curve_path=f"{INPUTS}/mu_curve.json",
        calibration_path=f"{INPUTS}/calibration.json", e0b_path=f"{INPUTS}/lambda_cap_bracket.json", e2_cfg_path=E2,
        n_cap_rule="smallest_within_margin", p=p,
        e2_cfg_sha256=hashlib.sha256((repo / E2).read_bytes()).hexdigest(), arms=["burst", "noburst"])
    if pr["status"] != "FILLED":
        raise ValueError(f"fill did not produce a FILLED registration: {pr['fill_problems']}")
    if pr["measured"].get("hardware") != HARDWARE:
        raise ValueError(f"registered hardware {pr['measured'].get('hardware')!r} != {HARDWARE!r}")
    if pr["protocol"].get("e2_config_sha256") is None or pr["protocol"].get("arms") != ["burst", "noburst"]:
        raise ValueError(f"{E2}: the sha256 / arms binding was not recorded: {pr['protocol']}")
    rp = prereg_mod.ramp_problems(e2_cfg, list(MULTS))
    if rp:
        raise ValueError(f"{E2}: {rp}")
    pr["inputs"]["engine_cell_label"] = LABEL
    return pr


def dump_registration(pr: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(pr, sort_keys=False).encode("utf-8")


# ================================================================ frozen predictions and plans
def load_predictions(path: Optional[str] = None, git_ref: Optional[str] = None) -> Dict[str, Any]:
    if git_ref:
        ref, rel = git_ref.split(":", 1)
        txt = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{rel}"], check=True, capture_output=True, text=True).stdout
        commit = subprocess.run(["git", "-C", str(REPO), "rev-list", "-n", "1", ref], check=True, capture_output=True,
                                text=True).stdout.strip()
        unix = int(subprocess.run(["git", "-C", str(REPO), "show", "-s", "--format=%ct", commit], check=True,
                                  capture_output=True, text=True).stdout.strip())
        obj = json.loads(txt)
        obj["_source"] = dict(git_ref=git_ref, commit=commit, commit_unix=unix)
        return obj
    obj = json.loads(Path(path or REPO / PRED_PATH).read_text())
    obj["_source"] = dict(path=str(path or PRED_PATH))
    return obj


def seed_pred(pred: Mapping[str, Any], mult: float, seed: int) -> Dict[str, float]:
    sd = pred["cells"][f"{mult:g}"]["seeds"][str(int(seed))]
    w = sd["windows"]
    return dict(wave=float(sd["burst_timing"]["median"]), wave_cal=float(sd["burst_timing"]["median_calibrated"]),
                blackout=float(w["blackout"]["completion_over_lam_ref"]), late=float(w["late"]["completion_over_lam_ref"]),
                slope=float(w["slope"]["slope"]), P_served=float(w["w5700"]["P_served_mean"]),
                lam_miss_model=float(pred["lambda_miss_model"]))


def frozen_plan(arm: str, mult: float, seed: int) -> pd.DataFrame:
    return pd.read_csv(REPO / PLAN_DIR / f"{arm}_{mult:g}_seed{int(seed)}.csv")


def plan_matches(plan: pd.DataFrame, ref: pd.DataFrame) -> Tuple[bool, str]:
    if len(plan) != len(ref):
        return False, f"{len(plan)} sessions != frozen {len(ref)}"
    for c in ("sid", "idx", "n_turns"):
        if not (plan[c].to_numpy() == ref[c].to_numpy()).all():
            return False, f"column {c} differs"
    if not (plan["origin"].astype(str).to_numpy() == ref["origin"].astype(str).to_numpy()).all():
        return False, "column origin differs"
    for c in ("arrival_s", "tool_time_total_s"):
        d = float(np.max(np.abs(plan[c].to_numpy(float) - ref[c].to_numpy(float)))) if len(plan) else 0.0
        if d > PLAN_ATOL_S * max(1.0, float(np.max(np.abs(ref[c].to_numpy(float)))) if len(ref) else 1.0):
            return False, f"column {c} differs by {d:.3g}"
    return True, ""


# ================================================================ per-run measures and rules
def wave_time(ses: pd.DataFrame) -> Tuple[float, int]:
    b = ses[(ses["origin"].astype(str) == "burst") & (ses["status"].astype(str) == "completed")]
    t = b["t_end"].to_numpy(float)
    t = t[np.isfinite(t) & (t <= DURATION_S)]
    return (float(np.median(t)) if len(t) >= MIN_BURST_DONE else math.nan), int(len(t))


def completion_bins(ses: pd.DataFrame, lam_ref: float, bin_s: float = 300.0) -> List[float]:
    edges = np.arange(T_BURST_S, DURATION_S + 1e-9, bin_s)
    t = ses[ses["status"].astype(str) == "completed"]["t_end"].to_numpy(float)
    cnt, _ = np.histogram(t[np.isfinite(t)], bins=edges)
    return [float(c / bin_s / lam_ref) for c in cnt]


def measure_run(run, p: AnalysisParams, ep: Dict[str, Any]) -> Dict[str, Any]:
    from .theory.icml import measured as ms
    ses = run.sessions
    run_end = float(run.t_end_s)
    lam_ref = float(run.lambda_ref_value)
    rec: Dict[str, Any] = {"run_end_s": run_end, "lambda_ref": lam_ref}
    for name, (w0, w1) in (("blackout", BLACKOUT_S), ("late", LATE_S)):
        r, n = completion_rate(ses, w0, w1)
        rec[f"{name}_rate"], rec[f"{name}_n"] = r / lam_ref, n
    rec["wave_time"], rec["burst_completed"] = wave_time(ses)
    grid = n_grid(ses, run_end)
    rec["slope"], rec["slope_bins"] = grid_slope(grid, *SLOPE_S)
    lam_plan, _ = plan_rate(read_plan(run.dir), *SLOPE_S)
    rec["lambda_plan_slope_window"] = lam_plan
    rec["completion_bins_300s"] = completion_bins(ses, lam_ref)
    try:
        st = ms.window_stats(str(run.dir), *COMP_S)
        rec["P_served_5700_8700"], rec["fu_hit_5700_8700"] = st.get("P_served_mean"), st.get("fu_hit")
    except Exception as exc:                                     # noqa: BLE001  (secondary measure only)
        rec["P_served_5700_8700"], rec["P_served_problem"] = math.nan, f"{type(exc).__name__}: {exc}"
    b = basin.classify_run(run, p, ep)
    for k in ("basin_state", "stuck", "good", "state", "hit_eval", "backlog_slope", "slope_threshold", "eval_from"):
        rec[k] = b.get(k)
    return rec


def rules(rec: Mapping[str, Any], pr: Mapping[str, float]) -> Dict[str, Any]:
    """The registered per-seed rules (module docstring) on one BURST run's measures and its frozen predictions."""
    qs = rec["lambda_plan_slope_window"] - pr["lam_miss_model"]
    out: Dict[str, Any] = dict(S_F=pr["slope"], S_QS=qs, F_wave=pr["wave"], F_wave_cal=pr["wave_cal"])
    out["M1"] = bool(_finite(rec["blackout_rate"]) and rec["blackout_rate"] <= BLACKOUT_MAX)
    w = rec["wave_time"]
    out["M2"] = bool(_finite(w) and abs(w - pr["wave"]) <= WAVE_TOL_REL * (pr["wave"] - T_BURST_S))
    out["M3"] = bool(_finite(rec["late_rate"]) and rec["late_rate"] <= LATE_MAX)
    s = rec["slope"]
    out["M4"] = bool(_finite(s) and abs(s - pr["slope"]) < abs(s - qs))
    stuck = bool(rec.get("stuck"))
    if not stuck:
        call = NOT_TRAPPED
    elif out["M1"] and out["M2"] and out["M3"] and out["M4"]:
        call = RENEWAL
    elif _finite(rec["blackout_rate"]) and _finite(rec["late_rate"]) and rec["blackout_rate"] >= CURVE_MIN \
            and rec["late_rate"] >= CURVE_MIN:
        call = CURVE
    else:
        call = MIXED
    out["call"] = call
    # secondary (reported)
    out["W5_calibrated_wave"] = bool(_finite(w) and abs(w - pr["wave_cal"]) <= WAVE_TOL_REL_CAL * (pr["wave_cal"] - T_BURST_S))
    ps = rec.get("P_served_5700_8700")
    out["W7_composition"] = bool(_finite(ps) and abs(ps - pr["P_served"]) <= P_TOL_REL * pr["P_served"])
    out["W8_late_level"] = bool(_finite(rec["late_rate"]) and abs(rec["late_rate"] - pr["late"]) <= LATE_TOL_ABS)
    return out


def cell_verdict(calls: Mapping[int, List[str]]) -> str:
    if any(len(v) > 1 for v in calls.values()):
        return "UNDECIDED"
    flat = [v[0] for v in calls.values() if v]
    if flat.count(RENEWAL) >= NEED:
        return "PASS"
    if flat.count(CURVE) >= NEED:
        return "FAIL"
    if flat.count(NOT_TRAPPED) >= NEED:
        return "NO-TRAP"
    if any(not calls.get(s) for s in SEEDS):
        return "PENDING"
    return "MIXED"


# ================================================================ classify
def classify(run_dirs: Iterable[str], ep: Dict[str, Any], p: AnalysisParams, *, preregs: Sequence[str],
             pred: Dict[str, Any], e0a_calib: Optional[str] = None) -> Dict[str, Any]:
    regs = {}
    for f in preregs:
        pr = prereg_mod.load_prereg(f)
        regs[(pr.get("inputs") or {}).get("engine_cell_label")] = (pr, prereg_mod.file_provenance(f), str(f))
    rows: List[Dict[str, Any]] = []
    for d in run_dirs:
        r = load_run(d)
        arm = r.arm or r.arm_derived
        mult = float(r.rate_mult) if r.rate_mult is not None else math.nan
        rec: Dict[str, Any] = dict(run_dir=str(r.dir), label=r.label, seed=r.seed, arm=arm, rate_mult=mult,
                                   t0_unix=r.t0_unix, run_status=r.meta.get("status"), aborted=r.aborted)
        probs: List[str] = []
        if r.label != LABEL:
            probs.append(f"label {r.label!r} != {LABEL!r}")
        if arm not in ("burst", "noburst"):
            probs.append(f"arm {arm!r} is not registered")
        mk = next((m for m in MULTS if math.isclose(mult, m)), None) if _finite(mult) else None
        if mk is None:
            probs.append(f"rate_mult {mult} not in {list(MULTS)}")
        if arm == "noburst" and mk is not None and not math.isclose(mk, DECISIVE):
            probs.append("noburst runs are registered at 1.65 x only")
        if r.seed not in SEEDS:
            probs.append(f"seed {r.seed} is not registered")
        if r.aborted:
            probs.append(f"aborted ({r.abort_reason})")
        if rec["run_status"] != "finished":
            probs.append(f"not completed: meta status {rec['run_status']!r}")
        if not r.t_end_s >= DURATION_S - 1e-6:
            probs.append(f"not completed: ended at {r.t_end_s:.1f} s")
        reg = regs.get(r.label)
        if reg is None:
            probs.append("no --prereg for this label")
        else:
            bl = prereg_mod.run_blockers(reg[0], reg[1], r)
            rec.update(prereg_file=reg[2], prereg_bound=not bl, prereg_blockers="; ".join(bl))
            if bl:
                probs.append("not bound to its registration: " + "; ".join(bl))
        if mk is not None and arm in ("burst", "noburst") and r.seed in SEEDS:
            ok, why = plan_matches(read_plan(r.dir), frozen_plan(arm, mk, r.seed))
            rec["plan_matches_frozen"] = ok
            if not ok:
                probs.append("plan differs from the frozen plan: " + why)
        try:
            rec.update(measure_run(r, p, ep))
        except Exception as exc:                                 # noqa: BLE001  (reported; the run does not count)
            probs.append(f"measurement failed: {type(exc).__name__}: {exc}")
        if not probs and arm == "burst":
            rec.update(rules(rec, seed_pred(pred, mk, r.seed)))
        rec["mult_key"] = mk
        rec["problem"] = "; ".join(probs)
        rec["counted"] = not probs
        rows.append(rec)
    out: Dict[str, Any] = dict(rows=rows, cells={})
    for mk, role in ((DECISIVE, "decisive"), (SECONDARY_MULT, "secondary")):
        calls = {s: [x["call"] for x in rows if x["counted"] and x["arm"] == "burst" and x["mult_key"] == mk and x["seed"] == s]
                 for s in SEEDS}
        out["cells"][f"{mk:g}"] = dict(role=role, calls={str(s): v for s, v in calls.items()}, verdict=cell_verdict(calls))
    # W6: the wave comes earlier at 1.35 x than at 1.65 x, per seed
    w6 = {}
    for s in SEEDS:
        a = [x["wave_time"] for x in rows if x["counted"] and x["arm"] == "burst" and x["mult_key"] == SECONDARY_MULT and x["seed"] == s]
        b = [x["wave_time"] for x in rows if x["counted"] and x["arm"] == "burst" and x["mult_key"] == DECISIVE and x["seed"] == s]
        w6[str(s)] = (bool(a[0] < b[0]) if len(a) == 1 and len(b) == 1 and _finite(a[0]) and _finite(b[0]) else None)
    out["W6_order"] = w6
    out["W9_controls_good"] = {str(x["seed"]): x.get("good") for x in rows if x["counted"] and x["arm"] == "noburst"}
    if e0a_calib:
        c = json.loads(Path(e0a_calib).read_text())
        lr = float(pred["lambda_ref"])
        lm = float(c["lambda_miss_turns_based"])
        late = [x["late_rate"] for x in rows if x["counted"] and x["arm"] == "burst" and _finite(x.get("late_rate"))]
        out["W10_capacity"] = dict(e0a_calibration=e0a_calib, lambda_miss_measured=lm, over_lambda_ref=lm / lr,
                                   model_over_lambda_ref=float(pred["lambda_miss_model_over_ref"]),
                                   late_below_measured_capacity=[bool(v < lm / lr) for v in late])
    src = pred.get("_source", {})
    t0s = [x["t0_unix"] for x in rows if x["counted"] and _finite(x.get("t0_unix"))]
    out["predictions"] = dict(source=src, predates_all_counted_runs=(bool(src["commit_unix"] < min(t0s))
                                                                     if "commit_unix" in src and t0s else None))
    return out


# ================================================================ submit lines (printed only; never submitted from here)
SUBMIT_MEM = "20G"


def sbatch_line(mult: float, arm: str, seed: int) -> str:
    opts, exports, script = parse_submit_line(R14_SHED_SUBMIT_LINE)
    new_opt = {"--mem": SUBMIT_MEM, "--time": "03:10:00", "--job-name": JOB_NAMES[(mult, arm)],
               "--account": "f2026.coms.6250.02", "--partition": "instruction", "--qos": "instruction"}
    new_exp = {"MULTS": f"{mult:g}", "SEEDS": str(int(seed)), "ARMS": arm, "E2_CONFIG": E2, "PREREG_FILE": OUT,
               "ENGINE_LABEL": LABEL}
    o = " ".join(f"{k}={new_opt.get(k, v)}" if v != "" else k for k, v in opts)
    e = ",".join(f"{k}={new_exp.get(k, v)}" for k, v in exports)
    return f"sbatch {o} --export=ALL,{e} {script}"


def e0a_line(smoke: bool = False) -> str:
    """MODE=miss (E0a: cache off server-side, closed POP 32) with the step-capped workload through GEN_EXTRA, which the job
    glue appends to every run_gen; MISS_RUN_S 300 for the smoke test (default 2700: warmup 900 + measure 1800)."""
    opts, exports, script = parse_submit_line(R14_SHED_SUBMIT_LINE)
    keep = ("ENV_GEN", "ENV_SGLANG", "HF_HOME", "XDG_CACHE_HOME", "CUDA_HOME_SHIM", "HF_REVISION", "OUTPUT_FEEDBACK", "KV_TOKENS")
    new_opt = {"--mem": SUBMIT_MEM, "--time": "00:40:00" if smoke else "01:30:00",
               "--job-name": "pm-mire0s" if smoke else "pm-mire0a", "--account": "f2026.coms.6250.02",
               "--partition": "instruction", "--qos": "instruction"}
    o = " ".join(f"{k}={new_opt.get(k, v)}" if v != "" else k for k, v in opts)
    ex = [f"{k}={v}" for k, v in exports if k in keep] + ["MODE=miss", "SEEDS=0",
                                                          f"ENGINE_LABEL=sglang-nocache-mirror-k20{'-smoke' if smoke else ''}"]
    if smoke:
        ex.append("MISS_RUN_S=300")
    return f"GEN_EXTRA='{E0A_GEN_EXTRA}' sbatch {o} --export=ALL,{','.join(ex)} {script}"


def sbatch_lines() -> List[str]:
    lines = [f"cd {CLONE_DIR}   # a fresh clone at tag {REG_TAG}, git status clean", "# smoke test first:", e0a_line(True),
             "# then, in this order:"]
    lines += [sbatch_line(1.65, "burst", s) for s in SEEDS] + [sbatch_line(1.65, "noburst", s) for s in SEEDS]
    lines += [e0a_line(False)] + [sbatch_line(1.35, "burst", s) for s in SEEDS]
    return lines


# ================================================================ self-check (no runs needed)
def selfcheck() -> List[str]:
    from analysis.theory.icml.mirror_predict import build_plan
    from analysis.theory.icml.cut_predict import plan_csv
    import io
    probs: List[str] = []
    for mult in MULTS:
        for arm in ("burst", "noburst"):
            for s in SEEDS:
                plan, _, _ = build_plan(s, mult, burst=(arm == "burst"))
                mine = pd.read_csv(io.StringIO(plan_csv(plan)))
                ok, why = plan_matches(mine, frozen_plan(arm, mult, s))
                if not ok:
                    probs.append(f"{arm} {mult} seed {s}: {why}")
    pr = dict(wave=5000.0, wave_cal=4700.0, blackout=0.05, late=0.55, slope=0.085, P_served=7000.0, lam_miss_model=1.046 * 0.0715)
    base = dict(blackout_rate=0.05, late_rate=0.55, wave_time=4900.0, slope=0.08, lambda_plan_slope_window=0.118, stuck=True,
                P_served_5700_8700=7100.0)
    cases = [(base, RENEWAL), (dict(base, stuck=False), NOT_TRAPPED), (dict(base, blackout_rate=1.0, late_rate=1.0), CURVE),
             (dict(base, wave_time=6000.0), MIXED), (dict(base, slope=0.045), MIXED), (dict(base, late_rate=0.9), MIXED)]
    for rec, want in cases:
        got = rules(rec, pr)["call"]
        if got != want:
            probs.append(f"rules: {rec} -> {got}, want {want}")
    if cell_verdict({0: [RENEWAL], 1: [RENEWAL], 2: []}) != "PASS" or cell_verdict({0: [CURVE], 1: [CURVE], 2: [RENEWAL]}) != "FAIL" \
            or cell_verdict({0: [RENEWAL], 1: [], 2: []}) != "PENDING" or cell_verdict({0: [RENEWAL], 1: [CURVE], 2: [MIXED]}) != "MIXED":
        probs.append("cell_verdict")
    return probs


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r16_mirror")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill")
    f.add_argument("--out", default=OUT)
    d = sub.add_parser("diff")
    d.add_argument("--file", default=OUT)
    sub.add_parser("selfcheck")
    sub.add_parser("sbatch-lines")
    c = sub.add_parser("classify")
    c.add_argument("--run-dirs", nargs="+", required=True)
    c.add_argument("--prereg", nargs="+", default=[OUT])
    c.add_argument("--pred-git", default=f"{REG_TAG}:{PRED_PATH}")
    c.add_argument("--pred", default=None)
    c.add_argument("--e0a-calib", default=None)
    c.add_argument("--endpoints", default=ENDPOINTS)
    c.add_argument("--out-root", default="results")
    args = ap.parse_args(argv)
    if args.cmd == "fill":
        out = REPO / args.out
        if out.exists():
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 1
        out.write_bytes(dump_registration(fill_registration()))
        print(out)
        return 0
    if args.cmd == "diff":
        parent = yaml.safe_load((REPO / PARENT).read_text())
        child = yaml.safe_load((REPO / args.file).read_text())
        print(json.dumps(registration_diff(parent, child), indent=1))
        return 0
    if args.cmd == "selfcheck":
        probs = selfcheck()
        print("selfcheck OK" if not probs else "\n".join(probs))
        return 0 if not probs else 1
    if args.cmd == "sbatch-lines":
        print("\n".join(sbatch_lines()))
        return 0
    p = load_params(REPO / PARAMS, [f"trap_v2.eval_from_s={REGISTERED_EVAL_FROM_S}"])     # as r15_cut classify
    ep_path = args.endpoints if Path(args.endpoints).is_absolute() else str(REPO / args.endpoints)
    ep = basin.load_endpoints(ep_path)
    pred = load_predictions(args.pred, None if args.pred else args.pred_git)
    res = classify(args.run_dirs, ep, p, preregs=args.prereg, pred=pred, e0a_calib=args.e0a_calib)
    res["endpoint_problems"] = basin.endpoint_problems(ep, p)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    od = Path(args.out_root) / "agentload_analysis_r16_mirror" / stamp
    od.mkdir(parents=True, exist_ok=True)
    rows = res.pop("rows")
    pd.DataFrame([{k: v for k, v in r.items() if k != "completion_bins_300s"} for r in rows]).to_csv(od / "mirror_runs.csv",
                                                                                                    index=False)
    (od / "mirror_bins.json").write_text(json.dumps({r["run_dir"]: r.get("completion_bins_300s") for r in rows}, indent=1))
    (od / "mirror_verdict.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["cells"], indent=1))
    print(od)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
