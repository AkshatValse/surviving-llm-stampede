"""r15 CUT cell: a blind hardware test of the trapped-engine cut theorem on the measured cell sglang-fcfs-r1 (SGLang 0.5.22 FCFS,
waiting-prefix refresh on, 300k pool, Qwen2.5-7B-Instruct, A100 80GB PCIe).

THEOREM UNDER TEST (the theory session's statement): in the trapped engine, an arrival cut to lambda' between the all-miss
capacity lambda_miss and the throughput D measured in the trap does NOT clear the trap: the backlog dips a few percent and grows
again. A cut below lambda_miss drains, slowly, over a busy period V_tot / (1 - rho').

PROTOCOL  the E2 BURST protocol at 1.65 x lambda_ref (lambda_ref = lambda_miss_turns_based of prereg/inputs/2026-10-23/
          calibration.json), the E2 burst of 200 sessions in [1200, 1260) s, 8700-s runs, one run (arm burst) per job, seeds 0-2;
          at t_cut = 2400 s the arrival rate drops to lambda' until the run end (arrivals.kind ramp, ramp_is_mult true, knots
          [[0, 1.65], [2400, 1.65], [2400.001, L], [8700, L]]):
            CUT-A  sglang-fcfs-r1-cut-a115  configs/agentload_e2_cut_a115.yaml  L = 1.15   (lambda_miss < lambda' < D)
            CUT-B  sglang-fcfs-r1-cut-b085  configs/agentload_e2_cut_b085.yaml  L = 0.85   (lambda' < lambda_miss)
CRN       the candidate arrivals come from the S_ARRIVALS stream at rate_max = 1.65 x lambda_ref (the constant 1.65 x BURST arm's)
          and all are kept before 2400 s, so the sessions arriving before 2400 s and the 200 burst sessions are those of the
          committed 1.65 x BURST control of the same seed (jobs 17093390 / 17093396 / 17093402; the NOBURST arms 17093391 /
          17093397 / 17093403 are reported beside; results/nova/e2_170933xx_pulled_20261025-144558). After the cut a candidate is
          kept with probability L / 1.65 (stream S_THIN; the same uniforms for both arms, so CUT-B's arrivals are a subset of
          CUT-A's); kept sessions get re-drawn specs (their index within origin shifts): pairing after 2400 s is by the arrival
          process only.

fill      the registrations configs/agentload_prereg_2026-11-05_cut_a115.yaml / _cut_b085.yaml, made as analysis.r14_prereg makes
          the SHED ones: analysis.prereg.fill under the MEASURED label sglang-fcfs-r1 from the inputs of the 2026-10-24
          registration (prereg/inputs/2026-10-23), its registered point m2 = 1.65, the cap rule smallest_within_margin, the cell's
          E2 config (sha256 -> protocol.e2_config_sha256) and arm (protocol.arms = [burst]); then only inputs.engine_cell_label is
          set to the cell's label. registration_diff against the 2026-10-24 file must find no forbidden leaf. Output is
          yaml.safe_dump(sort_keys=False), LF, never overwrites.
measure   per run, from its own files (measure_run): N(t) = sessions in the system (sessions.csv: arrived at arrival_s and not
          ended; a session ends at t_end if its status is completed or failed; any other session, e.g. one cancelled at the end,
          ends at the run end) as 10-s bin means on [0, 8700); OLS slopes of the bin means against the bin centres over
          [3000, 8700) (the primary S) and [5700, 8700); the post-cut minimum of N and its time; the session completion rate
          (sessions with status completed and t_end in the window, per second) over [1800, 2400) (D_pre) and [5700, 8700); the
          follow-up hit fraction (turns >= 2) over the frozen B1 window, and STUCK / GOOD exactly as
          configs/r11_basin_predict.yaml defines them (analysis.basin.classify_run, unchanged; reported, not part of the rule).
          NAIVE comparator (frozen): S_naive = lambda'_plan - D_trap(seed), lambda'_plan = base arrivals per second in the run's
          own plan.csv over [3000, 8700), D_trap(seed) = NAIVE_D_TRAP (the trapped throughput of the uncut 1.65 x BURST control of
          the same seed over [3000, 8700), fixed before any CUT run): the backlog would change at lambda' - D if the engine kept
          completing sessions at the rate it showed in the trap. QUASI-STATIC comparator (CUT-A only): S_qs = lambda'_plan -
          lambda_ref (completion at the all-miss capacity). S_naive_pre = lambda'_plan - D_pre is reported, not used.
manipulation check (manipulation_check, against the same-seed BURST control's plan.csv): the sessions arriving before 2400 s
          equal the control's (sid, origin, idx, n_turns exact; arrival_s and tool_time_total_s within 1e-9 s: numpy's exponential
          differs in the last bit between Windows and Linux libm); every base arrival at or after 2400 s is one of the control's
          and the post-cut sessions are exactly those the run's own config and seed give under the registered ramp; the kept count
          over [2400.001, 8700) is within 4 binomial standard deviations of (control candidates there) x L / 1.65; 200 burst
          sessions, all in [1200, 1260). classify adds: the run's ramp knots are the registered ones and the ramp is flat at
          lambda' over the slope window.
verdict   (arm_verdict; the text is decision_rule(arm), as registered) per counted seed: UNSTUCK if the run is not STUCK on the
          frozen evaluation window (counts against the theory); else THEORY-FAVOURED iff |S - S_theory| is smaller than the
          distance to every comparator of the arm (CUT-A: naive and quasi-static; CUT-B: naive), NAIVE- / QS-FAVOURED iff that
          comparator is strictly the closest, TIE otherwise. The arm PASSES iff THEORY-FAVOURED in >= 2 of the 3 registered seeds
          and its sign clause holds in >= 2 of 3 (CUT-A: the slope over [5700, 8700) > 0; CUT-B: S < 0); FAILS iff NAIVE-,
          QS-FAVOURED or UNSTUCK in >= 2 of 3 together; else MIXED. A run counts only if it is
          the registered cell's (label, arm burst, rate_mult 1.65, registered seed), completed (meta status finished, run end
          >= 8700 s) and not aborted, bound to its registration
          (analysis.prereg.run_blockers empty) and its manipulation check passes. Reporting states: UNDECIDED (two counted runs of
          one seed), PENDING (a registered seed has no run yet and neither PASS nor FAIL is reached), NO-THEORY (no theory slope
          for the arm).

THEORY PREDICTIONS FILE (written by the theory session, frozen at git tag icml-cut-pred; format not fixed when this was
written). load_theory_slopes accepts a YAML or JSON mapping, slopes in sessions/s over [3000, 8700):
    {arm: {seed: slope_3000_8700}}          e.g.  {cut-a115: {0: 0.004, 1: 0.003, 2: 0.004}, cut-b085: {0: -0.01, ...}}
  arm keys: a115 | cut-a115 | cut-a | cuta | sglang-fcfs-r1-cut-a115 (and the b085 forms), case-insensitive, '_' read as '-';
  seed keys: ints or digit strings; a value is a number, or a mapping with key slope_3000_8700; a number in place of the seed
  mapping applies to every registered seed. The mapping may sit under one wrapper key (theory_slopes, slopes, slope_3000_8700,
  predictions, cut). Other top-level keys are ignored and listed (ignored_keys). Pass it by path (--theory FILE) or straight
  from git (--theory-git REF:PATH), which records the commit and whether it predates every run.
  The file frozen at icml-cut-pred is results/theory/icml/cut_predictions.json, whose per-seed slope over [3000, 8700) is
  arms.<CUT-A|CUT-B>.seeds.<seed>.w3000.theory_slope (sessions/s; its w3000.lam_plan equals this module's lambda'_plan): that
  layout is read as such (_icml_layout_slopes), e.g.
      --theory-git icml-cut-pred:results/theory/icml/cut_predictions.json

CLI:  python -m analysis.r15_cut fill --arm a115|b085 [--out FILE]
      python -m analysis.r15_cut diff --arm a115|b085 [--file FILE]       (scripted diff against the 2026-10-24 registration)
      python -m analysis.r15_cut plan-check                                (offline plans vs the committed controls, no runs)
      python -m analysis.r15_cut sbatch-lines                              (prints the six submit lines; never submits)
      python -m analysis.r15_cut classify --run-dirs RUN [RUN ...] [--prereg FILE ...] [--theory FILE | --theory-git REF:PATH]
                                          [--control-root DIR] [--endpoints configs/r11_basin_predict.yaml] [--out-root results]
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
from .load import Run, load_run
from .params import AnalysisParams, load_params
from .throughput import completion_rates, hit_stats
from .windows import step_bins

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = "configs/agentload_prereg_template.yaml"
PARAMS = "configs/agentload_analysis.yaml"
PARENT = "configs/agentload_prereg_2026-10-24.yaml"
INPUTS = "prereg/inputs/2026-10-23"
MEASURED = "sglang-fcfs-r1"
ENDPOINTS = "configs/r11_basin_predict.yaml"
HARDWARE = "NVIDIA A100 80GB PCIe, 81920 MiB"
MULT = 1.65
SEEDS = (0, 1, 2)
NEED = 2                                    # ">= 2 of 3"
T_BURST_S, BURST_N, BURST_WIDTH_S = 1200.0, 200, 60.0
T_CUT_S = 2400.0
RAMP_EDGE_S = 0.001                         # the ramp's knot spacing at the cut
DURATION_S = 8700.0
GRID_DT_S = 10.0
SLOPE_WINDOW_S = (3000.0, 8700.0)           # primary slope S (and lambda'_plan)
LATE_WINDOW_S = (5700.0, 8700.0)            # reported slope and completion rate (= the frozen B1 evaluation window)
PRE_CUT_RATE_WINDOW_S = (1800.0, 2400.0)    # D_pre (reported; not in the rule)
# The naive comparator's trapped throughput D_trap(seed), FROZEN before any CUT run (2026-11-05, about 03:55 CST): the trapped
# throughput of the uncut 1.65 x BURST control of the same seed over SLOPE_WINDOW_S, D = lambda_plan - S (base arrivals per second
# in the control's plan.csv minus the OLS slope of its N(t)), computed with plan_rate / n_grid / grid_slope below;
# tests/test_r15_cut.py recomputes it from the committed controls. D_pre over PRE_CUT_RATE_WINDOW_S still holds the burst's own
# completions (1.75 / 1.65 / 1.23 x lambda_ref in the controls), so it is reported, not used by the rule.
NAIVE_D_TRAP: Dict[int, float] = {0: 0.09557230209941714, 1: 0.10053911353659345, 2: 0.09460296282643499}
REGISTERED_EVAL_FROM_S = 4500.0
PLAN_ATOL_S = 1e-9
KEPT_Z_MAX = 4.0
THEORY_TAG = "icml-cut-pred"
# The CUT registration commit gets its own tag and fresh clone: r15-reg (e05a262, pushed 2026-11-05 03:17) holds the TOOLSLOW-W /
# EDGE registrations without the CUT files, and its clone /work/classtmp/avalse/swapp/repo_r15_tonight runs those cells' jobs.
REG_TAG = "r15-cut-reg"
CLONE_DIR = "/work/classtmp/avalse/swapp/repo_r15_cut"
CONTROL_ROOT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst"
CONTROL_DIRS: Dict[Tuple[str, int], str] = {("burst", 0): "20261024-155120", ("burst", 1): "20261024-184132",
                                            ("burst", 2): "20261025-000043", ("noburst", 0): "20261024-160218",
                                            ("noburst", 1): "20261024-184259", ("noburst", 2): "20261025-000053"}
CONTROL_JOBS: Dict[Tuple[str, int], int] = {("burst", 0): 17093390, ("burst", 1): 17093396, ("burst", 2): 17093402,
                                            ("noburst", 0): 17093391, ("noburst", 1): 17093397, ("noburst", 2): 17093403}
CONTROL_LABEL = MEASURED

ARMS: Dict[str, Dict[str, Any]] = {
    # sign: the sign clause (+1: the slope over sign_window is > 0; -1: < 0); qs_comparator: the quasi-static comparator is in
    # the rule (for CUT-B the frozen predictions put it within 0.002 /s of the theory, so it could not discriminate there).
    "a115": {"name": "CUT-A", "label": "sglang-fcfs-r1-cut-a115", "lambda_mult": 1.15, "sign": +1, "sign_window": LATE_WINDOW_S,
             "qs_comparator": True,
             "e2": "configs/agentload_e2_cut_a115.yaml", "out": "configs/agentload_prereg_2026-11-05_cut_a115.yaml",
             "job_name": "pm-cut115"},
    "b085": {"name": "CUT-B", "label": "sglang-fcfs-r1-cut-b085", "lambda_mult": 0.85, "sign": -1, "sign_window": SLOPE_WINDOW_S,
             "qs_comparator": False,
             "e2": "configs/agentload_e2_cut_b085.yaml", "out": "configs/agentload_prereg_2026-11-05_cut_b085.yaml",
             "job_name": "pm-cut085"},
}
LABEL_TO_ARM = {c["label"]: k for k, c in ARMS.items()}

THEORY, NAIVE, TIE, NO_THEORY, UNDEFINED = "THEORY-FAVOURED", "NAIVE-FAVOURED", "TIE", "NO-THEORY", "UNDEFINED"
QS, UNSTUCK = "QS-FAVOURED", "UNSTUCK"
AGAINST = (NAIVE, QS, UNSTUCK)
NOT_COUNTED = "NOT-COUNTED"


def ramp_knots_mult(arm: str) -> List[List[float]]:
    """The registered ramp, in multiples of lambda_ref."""
    lam = float(ARMS[arm]["lambda_mult"])
    return [[0.0, MULT], [T_CUT_S, MULT], [T_CUT_S + RAMP_EDGE_S, lam], [DURATION_S, lam]]


def keep_prob(arm: str) -> float:
    return float(ARMS[arm]["lambda_mult"]) / MULT


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool) and math.isfinite(float(x))


# ================================================================ registration text and fill
def _sign_text(arm: str) -> str:
    c = ARMS[arm]
    w0, w1 = c["sign_window"]
    rel = ">" if c["sign"] > 0 else "<"
    return f"the slope of N over [{w0:.0f}, {w1:.0f}) s is {rel} 0"


def decision_rule(arm: str) -> str:
    c = ARMS[arm]
    comps = "|S - S_naive| and |S - S_qs|" if c["qs_comparator"] else "|S - S_naive|"
    alt = "NAIVE-FAVOURED (QS-FAVOURED) iff S_naive (S_qs) is strictly the closest" if c["qs_comparator"] else \
        "NAIVE-FAVOURED iff |S - S_naive| < |S - S_theory|"
    against = "NAIVE-FAVOURED, QS-FAVOURED or UNSTUCK" if c["qs_comparator"] else "NAIVE-FAVOURED or UNSTUCK"
    return (f"per counted seed: UNSTUCK if the run is not STUCK on the frozen evaluation window (it counts against the theory); "
            f"otherwise THEORY-FAVOURED iff |S - S_theory| < {comps} (S the measured slope of N over [3000, 8700) s), {alt}, "
            f"TIE otherwise; {c['name']} PASS iff THEORY-FAVOURED in >= 2 of the 3 registered seeds and {_sign_text(arm)} in >= 2 "
            f"of the 3; FAIL iff {against} in >= 2 of the 3 together; else MIXED; a run counts only if it is the registered "
            f"cell's (label {c['label']}, arm burst, rate_mult {MULT:g}, a registered seed), completed (not aborted), bound to "
            "this registration (analysis.prereg.run_blockers empty) and its manipulation check passes")


def _controls_text() -> str:
    b = ", ".join(f"seed {s}: job {CONTROL_JOBS[('burst', s)]}, {CONTROL_DIRS[('burst', s)]}" for s in SEEDS)
    n = ", ".join(f"{CONTROL_JOBS[('noburst', s)]} {CONTROL_DIRS[('noburst', s)]}" for s in SEEDS)
    return f"{CONTROL_ROOT}/<dir>, {b}; their NOBURST arms {n} are reported beside"


_COMMON = (
    f"Single point {MULT:g} x lambda_ref: the upper registered point (m2) of {PARENT}, same inputs ({INPUTS}: mu_curve, "
    "calibration, E0b bracket), same window (1, 2.0) x lambda_ref and the same 1/3-2/3 rule written on 2026-10-23 before E0b "
    "was read; reused unchanged so that each run pairs by seed (common random numbers) with the committed 300k E2 runs at "
    f"{MULT:g} x (jobs 17093387-17093404 (results/nova/e2_170933xx_pulled_20261025-144558)). The measured values are those of "
    f"cell {MEASURED} (same hardware, pool, policy and refresh flag; filled by analysis.r15_cut fill, which runs "
    f"analysis.prereg.fill under {MEASURED} with this cell's E2 config and arm and then sets only inputs.engine_cell_label), so "
    f"these runs stay out of the {MEASURED} verdict. The cell's E2 config is registered by its sha256 (protocol.e2_config_sha256; "
    "check-job refuses a job whose --e2-config bytes differ, and a run whose config.yaml differs is not bound) and the only "
    f"authorised arm is protocol.arms. Hardware: a run on hardware other than '{HARDWARE}' is not bound (measured.hardware). "
    "The pass_rule and kill_conditions below are the template's three-arm rule, inherited unchanged so the rule keys match the "
    "analysis; this one-arm cell is judged by the decision rule above (analysis/r15_cut.py), not by the paired PASS rule.")


def rule_text(arm: str) -> str:
    c = ARMS[arm]
    lam = float(c["lambda_mult"])
    if c["sign"] > 0:
        claim = (f"lambda' = {lam:g} x lambda_ref lies between lambda_miss (= lambda_ref) and the throughput D measured in the "
                 "trap: the theorem says the cut does NOT clear the trap (N dips a few percent and grows again); the naive "
                 "comparator says N drains at lambda' - D; the quasi-static comparator says N grows at lambda' - lambda_ref")
    else:
        claim = (f"lambda' = {lam:g} x lambda_ref lies below lambda_miss (= lambda_ref): the theorem says N drains, slowly, over "
                 "a busy period V_tot / (1 - rho'); the naive comparator says N drains fast, at lambda' - D")
    knots = f"[[0,{MULT:g}],[{T_CUT_S:g},{MULT:g}],[{T_CUT_S + RAMP_EDGE_S:.3f},{lam:g}],[{DURATION_S:g},{lam:g}]]"
    return (
        f"CUT cell (r15), arm {c['name']}, label {c['label']}: a blind hardware test of the trapped-engine cut theorem; {claim}. "
        f"Protocol: the E2 BURST protocol at {MULT:g} x lambda_ref (arm burst only), seeds 0, 1, 2, one run per job, 300k pool, "
        "OUTPUT_FEEDBACK=server, the E2 burst of 200 at [1200, 1260), 8700-s runs, with the arrival rate cut at t_cut = 2400 s "
        f"to {lam:g} x lambda_ref until the run end. Protocol from {c['e2']} (a copy of configs/agentload_e2_shed_t600.yaml "
        "except the arrivals comment, ramp and rate_mult lines and meta.notes): arrivals.kind ramp, ramp_is_mult true, knots "
        f"{knots}. CRN: the candidate arrivals come from the same S_ARRIVALS stream at rate_max = {MULT:g} x lambda_ref as the "
        f"constant {MULT:g} x BURST arm and are all kept before 2400 s (thinning probability 1), so the sessions arriving before "
        f"2400 s and the 200 burst sessions are those of the committed {MULT:g} x BURST control of the same seed "
        f"({_controls_text()}); after the cut each candidate is kept with probability {lam:g}/{MULT:g} (stream S_THIN), a "
        "thinned subset whose session specs are re-drawn (their index within origin shifts), so pairing after 2400 s is by the "
        f"arrival process only. The job's MULTS must equal the ramp's {MULT:g} (check-job). MEASUREMENTS per run (python -m "
        "analysis.r15_cut classify, from the run's own files): N(t) = sessions in the system (sessions.csv: arrived at "
        "arrival_s and not ended; a session ends at t_end if its status is completed or failed, any other session, e.g. one "
        "cancelled at the end, at the run end) as 10-s bin means on [0, 8700); S = the OLS slope of the bin means against the "
        "bin centres over [3000, 8700) (primary), and over [5700, 8700) (reported); the post-cut minimum of N and its time "
        "(reported); D_pre = the session completion rate (sessions with status completed and t_end in the window, per second) "
        "over [1800, 2400), and the same over [5700, 8700) (reported); the follow-up hit fraction (turns >= 2) over the frozen "
        f"evaluation window and STUCK / GOOD exactly as {ENDPOINTS} defines them (STUCK enters the rule as below). NAIVE "
        "comparator per run (frozen): S_naive = lambda'_plan - D_trap(seed), lambda'_plan = base arrivals per second in the "
        "run's own plan.csv over [3000, 8700), D_trap(seed) = the trapped throughput of the uncut 1.65 x BURST control of the "
        "same seed over [3000, 8700) (its plan's base arrival rate there minus the OLS slope of its N), fixed before any CUT run: "
        + ", ".join(f"seed {s} {NAIVE_D_TRAP[s]:.6f}" for s in SEEDS) + " sessions/s"
        + ("; QUASI-STATIC comparator: S_qs = lambda'_plan - lambda_ref (completions at the all-miss capacity)"
           if c["qs_comparator"] else "")
        + "; reported only: S_naive_pre = lambda'_plan - D_pre (D_pre over [1800, 2400) still holds the burst's own "
        "completions). THEORY slope per run: S_theory = the theory session's frozen slope over [3000, 8700) for this arm and "
        f"seed (git tag {THEORY_TAG}; a YAML/JSON mapping {{arm: {{seed: slope_3000_8700}}}} in sessions/s, read by "
        "analysis.r15_cut.load_theory_slopes). MANIPULATION CHECK per run, against the same-seed control's plan.csv: the "
        "sessions arriving before 2400 s equal the control's (sid, origin, idx, n_turns exact; arrival_s and tool_time_total_s "
        "within 1e-9 s); every base arrival at or after 2400 s is one of the control's, and the sessions arriving at or after "
        "2400 s are exactly those of the plan the run's own config and seed give under the registered ramp (sid, origin, idx, "
        f"n_turns exact; arrival_s and tool_time_total_s within 1e-9 s); the kept count over [2400.001, 8700) is within "
        f"{KEPT_Z_MAX:g} binomial standard deviations of (the control's candidates there) x {lam:g}/{MULT:g}; the plan has the "
        "200 burst sessions, all in [1200, 1260); the run's ramp knots are the registered ones and the ramp is flat at lambda' "
        f"over [3000, 8700]. DECISION RULE ({c['name']}): {decision_rule(arm)}. A registered seed without a counted run is "
        "neither THEORY- nor NAIVE-FAVOURED; two counted runs of one seed leave the arm UNDECIDED (no seed votes twice); while a "
        "registered seed has no run and neither PASS nor FAIL is reached the arm is PENDING; without a theory slope for the arm "
        "it is NO-THEORY. Statistics per seed (CRN pairs), no pooled intervals. BLINDNESS: the theory session's predictions are "
        f"committed and pushed separately (git tag {THEORY_TAG}, pushed 2026-11-05 02:25:43 CST) before the first job of this "
        "cell is submitted; this registration does not contain them. RULE HISTORY: this rule was fixed at about 03:55 CST on "
        "2026-11-05, after those predictions were pushed and before any CUT job; it is stricter than the draft the theory session "
        "simulated: the naive comparator uses each seed's frozen trapped throughput instead of the burst-inflated D_pre, CUT-A adds "
        "the quasi-static comparator and takes its sign clause over [5700, 8700) (the theory session's recommendation: its "
        "per-seed dips bottom out near 6750 s), CUT-B adds S < 0, and a run that leaves the trap counts against the theory. "
        + _COMMON)


def fill_registration(arm: str, *, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    c = ARMS[arm]
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                   # noqa: E731
    e2_cfg = yaml.safe_load(rd(c["e2"]))
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{INPUTS}/mu_curve.json")), json.loads(rd(f"{INPUTS}/calibration.json")),
        e0b=json.loads(rd(f"{INPUTS}/lambda_cap_bracket.json")), e2_cfg=e2_cfg, lambda_mults=[MULT],
        rule=rule_text(arm), engine_cell_label=MEASURED, mu_curve_path=f"{INPUTS}/mu_curve.json",
        calibration_path=f"{INPUTS}/calibration.json", e0b_path=f"{INPUTS}/lambda_cap_bracket.json", e2_cfg_path=c["e2"],
        n_cap_rule="smallest_within_margin", p=p,
        e2_cfg_sha256=hashlib.sha256((repo / c["e2"]).read_bytes()).hexdigest(), arms=["burst"])
    if pr["status"] != "FILLED":
        raise ValueError(f"fill did not produce a FILLED registration: {pr['fill_problems']}")
    if pr["measured"].get("hardware") != HARDWARE:
        raise ValueError(f"registered hardware {pr['measured'].get('hardware')!r} != {HARDWARE!r}")
    if pr["protocol"].get("e2_config_sha256") is None or pr["protocol"].get("arms") != ["burst"]:
        raise ValueError(f"{c['e2']}: the sha256 / arms binding was not recorded: {pr['protocol']}")
    rp = prereg_mod.ramp_problems(e2_cfg, [MULT])
    if rp:
        raise ValueError(f"{c['e2']}: {rp}")
    pr["inputs"]["engine_cell_label"] = c["label"]
    return pr


def dump_registration(pr: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(pr, sort_keys=False).encode("utf-8")


def _flatten(d: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(d, list):
        out[prefix] = json.dumps(d, sort_keys=True)
    else:
        out[prefix] = d
    return out


ALLOWED = ("inputs.engine_cell_label", "inputs.e2_config", "protocol.e2_config_sha256", "protocol.arms",
           "lambda_selection.lambda_mults", "lambda_selection.rule")
DERIVED_PREFIX = ("predicted_boundaries.capped_drain.",)


def registration_diff(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, List[str]]:
    """Leaves that differ between the 2026-10-24 registration and a CUT one: allowed (label, e2 config and its sha256, arms,
    lambda list, rule), derived (the CAPPED-drain numbers fill derives from the lambda list) and forbidden (anything else)."""
    a, b = _flatten(parent), _flatten(child)
    diff = [k for k in sorted(set(a) | set(b)) if a.get(k, "<missing>") != b.get(k, "<missing>")]
    allowed = [k for k in diff if k in ALLOWED]
    derived = [k for k in diff if k not in allowed and k.startswith(DERIVED_PREFIX)]
    return {"allowed": allowed, "derived": derived, "forbidden": [k for k in diff if k not in allowed and k not in derived]}


# ================================================================ plans and the manipulation check
PLAN_COLS = ("sid", "origin", "idx", "arrival_s", "n_turns", "tool_time_total_s")


def read_plan(run_dir: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(run_dir) / "plan.csv", float_precision="round_trip")


def plan_frame(plan: Sequence[Any]) -> pd.DataFrame:
    """A list of agentload.workload.SessionPlan as the plan.csv columns."""
    return pd.DataFrame([{"sid": s.sid, "origin": s.origin, "idx": s.idx, "arrival_s": s.arrival_s, "n_turns": s.n_turns,
                          "tool_time_total_s": float(sum(s.tool_times_s))} for s in plan], columns=list(PLAN_COLS))


def _plan_from(cfg_path: str | Path, sets: Sequence[str], repo: Path = REPO) -> pd.DataFrame:
    from agentload.config import load_config, resolve_ramp, resolve_rate
    from agentload.workload import build_open_plan

    cfg, _ = load_config(Path(cfg_path), list(sets))
    rate = resolve_rate(cfg.arrivals, repo) if cfg.arrivals.kind == "constant" else None
    knots = resolve_ramp(cfg.arrivals, repo) if cfg.arrivals.kind == "ramp" else []
    return plan_frame(build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, knots))


def offline_plan(arm: Optional[str], seed: int, *, cfg_path: Optional[str | Path] = None, repo: Path = REPO,
                 calibration: str = f"{INPUTS}/calibration.json", rate_mult: float = MULT,
                 burst_null: bool = False) -> pd.DataFrame:
    """The plan an E2 job of ``arm`` (or of ``cfg_path``, e.g. configs/agentload_e2_burst.yaml) would execute: the generator's own
    plan code with the job glue's overrides (slurm/common.sh e2_run; no server)."""
    path = Path(cfg_path) if cfg_path is not None else repo / ARMS[str(arm)]["e2"]
    sets = [f"run.seed={int(seed)}", f"arrivals.rate_mult={rate_mult}",
            f"arrivals.lambda_ref=\"{calibration}:lambda_miss_turns_based\"", f"arrivals.analysis_t_burst_s={T_BURST_S:g}",
            f"run.duration_s={DURATION_S:g}"]
    sets.append("arrivals.burst=null" if burst_null else f"arrivals.burst.t_s={T_BURST_S:g}")
    return _plan_from(path, sets, repo)


def run_settings(argv: Sequence[str]) -> List[str]:
    """The config overrides of an ``agentload run`` argv (meta.json argv), in the order agentload.cli applies them: every
    --set, then --seed as run.seed (and --out-root / --name, which do not touch the plan)."""
    sets: List[str] = []
    last: Dict[str, str] = {}                            # argparse: the last --seed / --out-root / --name wins
    toks = [str(a) for a in argv]
    i = 0
    while i < len(toks):
        a = toks[i]
        name, eq, val = a.partition("=")
        if name in ("--set", "--seed", "--out-root", "--name"):
            if not eq:
                if i + 1 >= len(toks):
                    break
                val, i = toks[i + 1], i + 1
            if name == "--set":
                sets.append(val)
            else:
                last[name] = val
        i += 1
    if "--seed" in last:
        sets.append(f"run.seed={int(last['--seed'])}")
    if "--out-root" in last:
        sets.append(f"output.root={last['--out-root']}")
    if "--name" in last:
        sets.append(f"output.name={last['--name']}")
    return sets


def plan_under_run_settings(cfg_path: str | Path, run_dir: str | Path, repo: Path = REPO) -> pd.DataFrame:
    """The plan ``cfg_path`` gives under the run settings (--set / --seed of meta.json argv) of the committed run ``run_dir``:
    a CUT config under a control's own settings."""
    return _plan_from(cfg_path, run_settings(json.loads((Path(run_dir) / "meta.json").read_text())["argv"]), repo)


def rebuild_plan(run: Run, knots: Sequence[Sequence[float]]) -> pd.DataFrame:
    """The plan the run's own effective config (workload, burst, seed, duration; arrivals.kind ramp) gives with the ramp
    ``knots`` in sessions/s (the generator's own plan code, no server)."""
    from agentload.config import config_from_dict
    from agentload.workload import build_open_plan

    cfg = config_from_dict(run.cfg)
    if cfg.arrivals.kind != "ramp":
        raise ValueError(f"{run.dir}: arrivals.kind {cfg.arrivals.kind!r} is not ramp")
    kn = [(float(t), float(r)) for t, r in knots]
    return plan_frame(build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, None, kn))


def thinned_plan_of_run(run: Run, arm: str) -> pd.DataFrame:
    """The plan the run must have executed: its own config under the REGISTERED ramp of ``arm`` (knots x the run's resolved
    lambda_ref)."""
    lam_ref = run.lambda_ref_value
    if lam_ref is None:
        raise ValueError(f"{run.dir}: no resolved lambda_ref")
    return rebuild_plan(run, [(t, m * float(lam_ref)) for t, m in ramp_knots_mult(arm)])


def _match_within(x: np.ndarray, ref: np.ndarray, atol: float) -> np.ndarray:
    """For each x, whether some element of ``ref`` lies within ``atol`` of it."""
    if len(x) == 0:
        return np.zeros(0, dtype=bool)
    if len(ref) == 0:
        return np.zeros(len(x), dtype=bool)
    r = np.sort(np.asarray(ref, dtype=float))
    i = np.clip(np.searchsorted(r, x), 1, len(r) - 1) if len(r) > 1 else np.zeros(len(x), dtype=int)
    best = np.abs(r[i] - x)
    if len(r) > 1:
        best = np.minimum(best, np.abs(r[i - 1] - x))
    return best <= atol


def _frames_equal(a: pd.DataFrame, b: pd.DataFrame, atol: float) -> Tuple[bool, float, float]:
    """Same sessions (sid, origin, idx, n_turns exact) in the same order; (equal, max |d arrival|, max |d tool total|)."""
    a, b = a.reset_index(drop=True), b.reset_index(drop=True)
    if len(a) != len(b):
        return False, math.inf, math.inf
    if len(a) == 0:
        return True, 0.0, 0.0
    keys = all((a[c].to_numpy() == b[c].to_numpy()).all() for c in ("sid", "origin", "idx", "n_turns"))
    da = float(np.max(np.abs(a["arrival_s"].to_numpy(float) - b["arrival_s"].to_numpy(float))))
    dt = float(np.max(np.abs(a["tool_time_total_s"].to_numpy(float) - b["tool_time_total_s"].to_numpy(float))))
    return bool(keys and da <= atol and dt <= atol), da, dt


def manipulation_check(plan: pd.DataFrame, control: pd.DataFrame, *, keep_probability: float,
                       thinned: Optional[pd.DataFrame] = None, t_cut: float = T_CUT_S, edge_s: float = RAMP_EDGE_S,
                       t_end: float = DURATION_S, burst_n: int = BURST_N,
                       burst_window: Tuple[float, float] = (T_BURST_S, T_BURST_S + BURST_WIDTH_S), atol: float = PLAN_ATOL_S,
                       z_max: float = KEPT_Z_MAX) -> Dict[str, Any]:
    """Did the run execute the CUT manipulation? ``plan`` is the run's plan.csv, ``control`` the same-seed constant-rate BURST
    control's (its base arrivals after the cut are the candidate stream), ``thinned`` the plan the registered ramp gives for the
    run's seed (``thinned_plan_of_run``; None skips that comparison). Keys prefixed ``mc_``; ``mc_pass`` is the conjunction."""
    plan = plan.sort_values("sid", kind="stable")
    control = control.sort_values("sid", kind="stable")
    pre_r, pre_c = plan[plan["arrival_s"] < t_cut], control[control["arrival_s"] < t_cut]
    pre_ok, d_arr, d_tool = _frames_equal(pre_r, pre_c, atol)
    rb, cb = plan[plan["origin"] == "base"], control[control["origin"] == "base"]
    post_r = rb[rb["arrival_s"] >= t_cut]["arrival_s"].to_numpy(float)
    post_c = cb[cb["arrival_s"] >= t_cut]["arrival_s"].to_numpy(float)
    in_ctl = _match_within(post_r, post_c, atol)
    subset = bool(in_ctl.all())
    lo, hi = t_cut + edge_s, t_end
    n = int(((post_c >= lo) & (post_c < hi)).sum())
    k = int(((post_r >= lo) & (post_r < hi)).sum())
    n_edge, k_edge = int(((post_c >= t_cut) & (post_c < lo)).sum()), int(((post_r >= t_cut) & (post_r < lo)).sum())
    p = float(keep_probability)
    sd = math.sqrt(n * p * (1.0 - p))
    if sd > 0:
        z = (k - n * p) / sd
    else:
        z = 0.0 if math.isclose(k, n * p) else math.inf
    kept_ok = bool(abs(z) <= z_max and k <= n)
    br = plan[plan["origin"] == "burst"]
    burst_ok = bool(len(br) == burst_n and (br["arrival_s"] >= burst_window[0]).all()
                    and (br["arrival_s"] < burst_window[1]).all())
    rec: Dict[str, Any] = {
        "mc_pre_cut_sessions": int(len(pre_r)), "mc_pre_cut_sessions_control": int(len(pre_c)), "mc_pre_cut_equal": pre_ok,
        "mc_pre_cut_max_abs_d_arrival_s": d_arr, "mc_pre_cut_max_abs_d_tool_s": d_tool,
        "mc_pre_cut_arrivals_exact": bool(len(pre_r) == len(pre_c) and d_arr == 0.0),
        "mc_post_cut_base_arrivals": int(len(post_r)), "mc_post_cut_candidates": int(len(post_c)),
        "mc_post_cut_subset_of_control": subset, "mc_post_cut_not_in_control": int((~in_ctl).sum()),
        "mc_kept": k, "mc_candidates": n, "mc_shed": n - k, "mc_kept_frac": (k / n) if n else math.nan,
        "mc_keep_prob": p, "mc_kept_z": z, "mc_kept_consistent": kept_ok, "mc_ramp_edge_candidates": n_edge,
        "mc_ramp_edge_kept": k_edge, "mc_burst_sessions": int(len(br)), "mc_burst_ok": burst_ok}
    ok = pre_ok and subset and kept_ok and burst_ok
    if thinned is not None:            # post-cut sessions (sid, origin, idx, n_turns, arrival, tool total) = the registered plan's
        thinned = thinned.sort_values("sid", kind="stable")
        same, _, _ = _frames_equal(plan[plan["arrival_s"] >= t_cut], thinned[thinned["arrival_s"] >= t_cut], atol)
        rec["mc_post_cut_equals_thinned_plan"] = bool(same)
        ok = ok and same
    rec["mc_pass"] = bool(ok)
    probs = [m for flag, m in ((pre_ok, "sessions before the cut differ from the control's"),
                               (subset, "post-cut base arrivals not in the control's candidate stream"),
                               (kept_ok, f"kept fraction {rec['mc_kept_frac']:.4f} inconsistent with {p:.4f} (z = {z:+.2f})"),
                               (burst_ok, f"burst: {len(br)} sessions (expected {burst_n} in [{burst_window[0]:g}, "
                                          f"{burst_window[1]:g}))"),
                               (rec.get("mc_post_cut_equals_thinned_plan", True),
                                "post-cut sessions are not those of the registered ramp's plan")) if not flag]
    rec["mc_problem"] = "; ".join(probs)
    return rec


def ramp_is_registered(run: Run, arm: str) -> bool:
    knots = run.meta.get("ramp_knots") or []
    lam_ref = run.lambda_ref_value
    want = ramp_knots_mult(arm)
    if lam_ref is None or len(knots) != len(want):
        return False
    return all(math.isclose(float(t), w_t, rel_tol=0, abs_tol=1e-9) and math.isclose(float(r), w_m * lam_ref, rel_tol=1e-12)
               for (t, r), (w_t, w_m) in zip(knots, want))


def ramp_flat_over_window(run: Run, w0: float, w1: float) -> bool:
    """True if the run's ramp rate equals run.lam everywhere on [w0, w1] (copied from analysis.r14_cells)."""
    if (run.cfg.get("arrivals") or {}).get("kind") != "ramp":
        return True
    knots = run.meta.get("ramp_knots") or []
    if not knots or run.lam is None:
        return False
    from agentload.workload import ramp_rate
    ts = [w0, w1] + [float(t) for t, _ in knots if w0 <= float(t) <= w1]
    return bool(np.allclose(ramp_rate(np.array(ts), [(float(t), float(r)) for t, r in knots]), run.lam, rtol=1e-12, atol=0))


# ================================================================ per-run measurements
def n_events(ses: pd.DataFrame, run_end: float) -> Tuple[np.ndarray, np.ndarray]:
    """Event times and N after each event: +1 at arrival_s; -1 at t_end for a completed or failed session, at ``run_end`` for
    every other one (cancelled at the end of the run, or unfinished). Arrivals before departures at equal times."""
    if len(ses) == 0:
        return np.zeros(0), np.zeros(0)
    arr = ses["arrival_s"].to_numpy(dtype=float)
    te = ses["t_end"].to_numpy(dtype=float) if "t_end" in ses.columns else np.full(len(ses), np.nan)
    ended = ses["status"].isin(["completed", "failed"]).to_numpy() & np.isfinite(te)
    dep = np.where(ended, te, float(run_end))
    t = np.concatenate([arr, dep])
    d = np.concatenate([np.ones(len(arr)), -np.ones(len(dep))])
    order = np.lexsort((-d, t))
    return t[order], np.cumsum(d[order])


def n_grid(ses: pd.DataFrame, run_end: float, *, t_max: float = DURATION_S, dt: float = GRID_DT_S) -> pd.DataFrame:
    """N(t) as bin means on the grid [k dt, (k+1) dt), k = 0 .. up to min(t_max, run_end)."""
    t_top = min(float(t_max), float(run_end))
    nb = int(math.floor(t_top / dt + 1e-9))
    edges = dt * np.arange(nb + 1)
    if nb < 1:
        return pd.DataFrame({"t_start": [], "t_center": [], "n_mean": []})
    t, v = n_events(ses, run_end)
    mean, _ = step_bins(t, v, edges)
    return pd.DataFrame({"t_start": edges[:-1], "t_center": 0.5 * (edges[:-1] + edges[1:]), "n_mean": mean})


def grid_slope(grid: pd.DataFrame, w0: float, w1: float, dt: float = GRID_DT_S) -> Tuple[float, int]:
    """OLS slope (sessions/s) of the bin means against the bin centres over the bins inside [w0, w1); NaN unless the grid covers
    the whole window (and >= 3 bins). Same estimator as analysis.throughput.backlog_slope (np.polyfit on bin means)."""
    sel = grid[(grid["t_start"] >= w0 - 1e-9) & (grid["t_start"] + dt <= w1 + 1e-9)]
    want = int(math.floor((w1 - w0) / dt + 1e-9))
    if len(sel) != want or want < 3:
        return math.nan, int(len(sel))
    return float(np.polyfit(sel["t_center"].to_numpy(float), sel["n_mean"].to_numpy(float), 1)[0]), int(len(sel))


def completion_rate(ses: pd.DataFrame, w0: float, w1: float) -> Tuple[float, int]:
    """(sessions with status completed and t_end in [w0, w1), per second; their count)."""
    te = pd.to_numeric(ses["t_end"], errors="coerce")
    n = int(((ses["status"] == "completed") & (te >= w0) & (te < w1)).sum())
    return n / (w1 - w0), n


def plan_rate(plan: pd.DataFrame, w0: float, w1: float) -> Tuple[float, int]:
    """(base arrivals of the plan in [w0, w1), per second; their count)."""
    b = plan[(plan["origin"] == "base") & (plan["arrival_s"] >= w0) & (plan["arrival_s"] < w1)]
    return len(b) / (w1 - w0), int(len(b))


def measure_run(run: Run, p: AnalysisParams, ep: Dict[str, Any]) -> Dict[str, Any]:
    """The registered per-run measurements (module docstring), keyed for cut_runs.csv; also returns the N grid under '_grid'."""
    ses, plan = run.sessions, read_plan(run.dir)
    run_end = float(run.t_end_s)
    grid = n_grid(ses, run_end)
    rec: Dict[str, Any] = {"run_end_s": run_end, "grid_bins": int(len(grid))}
    for (w0, w1) in (SLOPE_WINDOW_S, LATE_WINDOW_S):
        s, nb = grid_slope(grid, w0, w1)
        rec[f"slope_{w0:.0f}_{w1:.0f}"], rec[f"slope_bins_{w0:.0f}_{w1:.0f}"] = s, nb
    pre = grid[(grid["t_start"] >= T_CUT_S - GRID_DT_S - 1e-9) & (grid["t_start"] < T_CUT_S - 1e-9)]
    post = grid[grid["t_start"] >= T_CUT_S - 1e-9]
    rec["n_pre_cut"] = float(pre["n_mean"].iloc[0]) if len(pre) else math.nan          # mean over [2390, 2400)
    if len(post):
        i = int(post["n_mean"].to_numpy().argmin())
        rec["n_post_cut_min"] = float(post["n_mean"].iloc[i])
        rec["t_post_cut_min_s"] = float(post["t_start"].iloc[i])
        rec["n_end"] = float(post["n_mean"].iloc[-1])
    else:
        rec["n_post_cut_min"] = rec["t_post_cut_min_s"] = rec["n_end"] = math.nan
    rec["post_cut_dip_rel"] = (1.0 - rec["n_post_cut_min"] / rec["n_pre_cut"]) if rec["n_pre_cut"] else math.nan
    for (w0, w1) in (PRE_CUT_RATE_WINDOW_S, LATE_WINDOW_S):
        r, n = completion_rate(ses, w0, w1)
        tag = f"{w0:.0f}_{w1:.0f}"
        rec[f"completion_rate_{tag}"], rec[f"n_completed_{tag}"] = r, n
        rec[f"completion_rate_req_{tag}"] = completion_rates(run, w0, w1)["sessions_per_s"]   # requests-based cross-check
    lam_plan, n_plan = plan_rate(plan, *SLOPE_WINDOW_S)
    rec["lambda_plan_3000_8700"], rec["n_plan_arrivals_3000_8700"] = lam_plan, n_plan
    lam_ref = run.lambda_ref_value
    rec["lambda_ref"] = lam_ref
    rec["lambda_plan_mult"] = (lam_plan / lam_ref) if lam_ref else math.nan
    d_pre = rec[f"completion_rate_{PRE_CUT_RATE_WINDOW_S[0]:.0f}_{PRE_CUT_RATE_WINDOW_S[1]:.0f}"]
    rec["naive_slope_3000_8700"] = lam_plan - d_pre
    b = basin.classify_run(run, p, ep)
    for k in ("basin_state", "stuck", "good", "good_by_recovered", "good_by_hit_slope", "state", "hit_eval", "backlog_slope",
              "slope_threshold", "lambda", "hit_end", "outstanding_end", "eval_from", "t_end_s", "window_matches_endpoints"):
        rec[k] = b.get(k)
    h = hit_stats(run, p, float(b["eval_from"]), run_end + 1e-9)                   # the same turns as hit_eval
    rec["hit_followup_eval"], rec["hit_turns_eval"] = h["hit_frac_followup"], h["hit_frac_turns"]
    rec["_grid"] = grid
    return rec


# ================================================================ controls
def control_dirs(root: str | Path = REPO / CONTROL_ROOT) -> Dict[Tuple[str, int], Path]:
    """The registered CRN controls {(arm, seed): run dir}, each checked (label, arm, seed, rate_mult 1.65)."""
    out: Dict[Tuple[str, int], Path] = {}
    for (arm, seed), name in CONTROL_DIRS.items():
        d = Path(root) / name
        if not (d / "meta.json").is_file():
            continue
        r = load_run(d)
        if r.label != CONTROL_LABEL or (r.arm or r.arm_derived) != arm or r.seed != seed or r.rate_mult is None \
                or not math.isclose(r.rate_mult, MULT):
            raise ValueError(f"{d}: not the registered {arm} control of seed {seed} at {MULT:g} x ({r.label}, {r.arm}, {r.seed}, "
                             f"{r.rate_mult})")
        out[(arm, seed)] = d
    return out


# ================================================================ theory predictions
WRAPPER_KEYS = ("theory_slopes", "slopes", "slope_3000_8700", "predictions", "cut")


def arm_key(name: Any) -> Optional[str]:
    """The CUT arm a theory-file key names (None if it names none)."""
    s = str(name).strip().lower().replace("_", "-")
    for k, c in ARMS.items():
        if s in {k, f"cut-{k}", c["name"].lower(), c["name"].lower().replace("-", ""), c["label"]}:
            return k
    return None


def _slope_value(v: Any, where: str) -> float:
    if isinstance(v, Mapping):
        if "slope_3000_8700" not in v:
            raise ValueError(f"{where}: a mapping value needs key slope_3000_8700, got {sorted(v)}")
        v = v["slope_3000_8700"]
    if not _finite(v):
        raise ValueError(f"{where}: slope must be a finite number, got {v!r}")
    return float(v)


ICML_SLOPE_PATH = "arms.<arm>.seeds.<seed>.w3000.theory_slope"


def _icml_layout_slopes(obj: Mapping) -> Optional[Dict[str, Dict[int, float]]]:
    """The layout frozen at git tag icml-cut-pred (results/theory/icml/cut_predictions.json, written by
    analysis/theory/icml/cut_predict.py): {arms: {CUT-A: {seeds: {"0": {w3000: {theory_slope: x, ...}, ...}, ...}, ...}, CUT-B: ...},
    ...}, where w3000 is the window [3000, 8700) s and slopes are in sessions/s. Returns {arm: {seed: slope}}, or None when ``obj``
    is not in that layout (then the generic {arm: {seed: slope}} reading applies)."""
    arms = obj.get("arms")
    if not isinstance(arms, Mapping) or not arms or not all(arm_key(k) for k in arms) \
            or not all(isinstance(v, Mapping) and isinstance(v.get("seeds"), Mapping) for v in arms.values()):
        return None
    out: Dict[str, Dict[int, float]] = {}
    for k, v in arms.items():
        a = arm_key(k)
        if a in out:
            raise ValueError(f"theory predictions name arm {a} twice")
        per: Dict[int, float] = {}
        for sk, sv in v["seeds"].items():
            try:
                seed = int(str(sk).strip())
            except ValueError as exc:
                raise ValueError(f"theory predictions arms.{k}.seeds: seed key {sk!r} is not an integer") from exc
            w = sv.get("w3000") if isinstance(sv, Mapping) else None
            if not isinstance(w, Mapping) or "theory_slope" not in w:
                raise ValueError(f"theory predictions arms.{k}.seeds.{sk}: no w3000.theory_slope")
            per[seed] = _slope_value(w["theory_slope"], f"arms.{k}.seeds.{sk}.w3000.theory_slope")
        out[a] = per
    return out


def parse_theory_slopes(obj: Any) -> Dict[str, Any]:
    """{'slopes': {arm: {seed: slope}}, 'ignored_keys': [...]} from the loaded YAML/JSON object (see the module docstring)."""
    if not isinstance(obj, Mapping):
        raise ValueError(f"theory predictions must be a mapping, got {type(obj).__name__}")
    icml = _icml_layout_slopes(obj)
    if icml is not None:
        return {"slopes": icml, "ignored_keys": [str(k) for k in obj if k != "arms"], "wrapper_key": ICML_SLOPE_PATH}
    level, wrapper = obj, None
    if not any(arm_key(k) for k in obj):
        inner = [k for k in WRAPPER_KEYS if isinstance(obj.get(k), Mapping) and any(arm_key(x) for x in obj[k])]
        if not inner:
            raise ValueError(f"theory predictions name no CUT arm (keys {sorted(map(str, obj))}; expected e.g. cut-a115, "
                             "cut-b085)")
        wrapper = inner[0]
        level = obj[wrapper]
    ignored = [str(k) for k in obj if k != wrapper and (wrapper is not None or arm_key(k) is None)]
    if wrapper is not None:
        ignored += [f"{wrapper}.{k}" for k in level if arm_key(k) is None]
    slopes: Dict[str, Dict[int, float]] = {}
    for k, v in level.items():
        a = arm_key(k)
        if a is None:
            continue
        if a in slopes:
            raise ValueError(f"theory predictions name arm {a} twice")
        if isinstance(v, Mapping) and "slope_3000_8700" not in v:
            per: Dict[int, float] = {}
            for sk, sv in v.items():
                try:
                    seed = int(str(sk).strip())
                except ValueError as exc:
                    raise ValueError(f"theory predictions {k}: seed key {sk!r} is not an integer") from exc
                per[seed] = _slope_value(sv, f"{k}[{sk}]")
            slopes[a] = per
        else:
            val = _slope_value(v, str(k))
            slopes[a] = {s: val for s in SEEDS}
    return {"slopes": slopes, "ignored_keys": ignored, "wrapper_key": wrapper}


def load_theory_slopes(path: Optional[str | Path] = None, *, git_ref: Optional[str] = None,
                       repo: Path = REPO) -> Dict[str, Any]:
    """Read the frozen theory predictions by path, or (``git_ref`` = 'REF:PATH') from git, and parse them; records sha256 and,
    for git, the commit and its time."""
    if (path is None) == (git_ref is None):
        raise ValueError("give exactly one of path / git_ref")
    meta: Dict[str, Any] = {}
    if path is not None:
        raw = Path(path).read_bytes()
        meta["path"] = str(path)
    else:
        ref, _, rel = str(git_ref).partition(":")
        if not ref or not rel:
            raise ValueError(f"git_ref must be REF:PATH, got {git_ref!r}")
        res = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=repo, capture_output=True, timeout=60)
        if res.returncode:
            raise ValueError(f"git show {ref}:{rel} failed: {res.stderr.decode(errors='replace').strip()}")
        raw = res.stdout
        log = subprocess.run(["git", "log", "-1", "--format=%H %ct", ref, "--"], cwd=repo, capture_output=True, text=True,
                             timeout=60).stdout.split()
        meta.update(git_ref=ref, git_path=rel, git_commit=log[0] if log else None,
                    git_commit_unix=float(log[1]) if len(log) > 1 else None)
    meta["sha256"] = hashlib.sha256(raw).hexdigest()
    out = parse_theory_slopes(yaml.safe_load(raw.decode("utf-8")))
    out.update(meta)
    return out


# ================================================================ verdict
def seed_call(measured: Any, theory: Any, alternatives: Mapping[str, Any], stuck: Any = True) -> str:
    """The registered per-seed call. ``alternatives`` maps a call label (NAIVE, QS) to that comparator's slope; ``stuck`` is the
    run's STUCK flag on the frozen evaluation window (a run that is not STUCK is UNSTUCK, which counts against the theory)."""
    if not _finite(measured) or not alternatives or not all(_finite(v) for v in alternatives.values()):
        return UNDEFINED
    if not _finite(theory):
        return NO_THEORY
    if stuck is None:
        return UNDEFINED
    if not bool(stuck):
        return UNSTUCK
    m = float(measured)
    dt = abs(m - float(theory))
    d_alt = {k: abs(m - float(v)) for k, v in alternatives.items()}
    best = min(d_alt.values())
    if dt < best:
        return THEORY
    if best < dt:
        return min(d_alt, key=lambda k: (d_alt[k], k))
    return TIE


def comparators(arm: str, row: Mapping[str, Any]) -> Dict[str, float]:
    """{NAIVE: S_naive[, QS: S_qs]} for one row (lambda'_plan and lambda_ref from the row; D_trap frozen per seed)."""
    lam, lam_ref, seed = row.get("lambda_plan_3000_8700"), row.get("lambda_ref"), row.get("seed")
    out: Dict[str, float] = {}
    d = NAIVE_D_TRAP.get(int(seed)) if seed is not None else None
    out[NAIVE] = float(lam) - float(d) if _finite(lam) and _finite(d) else math.nan
    if ARMS[arm]["qs_comparator"]:
        out[QS] = float(lam) - float(lam_ref) if _finite(lam) and _finite(lam_ref) else math.nan
    return out


def arm_verdict(arm: str, rows: Sequence[Dict[str, Any]], theory: Optional[Mapping[int, float]],
                seeds: Sequence[int] = SEEDS, need: int = NEED) -> Dict[str, Any]:
    """The registered rule for one arm over the rows of classify (role 'new', this arm; only counted rows vote)."""
    c = ARMS[arm]
    recs = [r for r in rows if r.get("role") == "new" and r.get("arm") == arm and r.get("seed") is not None]
    counted = [r for r in recs if r.get("counted")]
    present = sorted({int(r["seed"]) for r in recs})
    dup = sorted({s for s in seeds if sum(int(r["seed"]) == s for r in counted) > 1})
    per_seed: Dict[str, Dict[str, Any]] = {}
    for s in seeds:
        rs = [r for r in counted if int(r["seed"]) == s]
        if len(rs) != 1:
            per_seed[str(s)] = {"counted": False, "call": NOT_COUNTED, "n_counted_runs": len(rs),
                                "run_present": s in present}
            continue
        r = rs[0]
        th = None if theory is None else theory.get(s)
        m = r.get("slope_3000_8700")
        w0, w1 = c["sign_window"]
        m_sign = r.get(f"slope_{w0:.0f}_{w1:.0f}")
        alts = comparators(arm, r)
        call = seed_call(m, th, alts, r.get("stuck"))
        sign_ok = bool(_finite(m_sign) and (m_sign > 0 if c["sign"] > 0 else m_sign < 0))
        per_seed[str(s)] = {"counted": True, "run_dir": r.get("run_dir"), "measured_slope": m, "theory_slope": th,
                            "naive_slope": alts.get(NAIVE), "qs_slope": alts.get(QS),
                            "naive_pre_slope_reported": r.get("naive_slope_3000_8700"), "stuck": r.get("stuck"),
                            "abs_err_theory": abs(m - th) if _finite(m) and _finite(th) else None,
                            "abs_err_naive": abs(m - alts[NAIVE]) if _finite(m) and _finite(alts.get(NAIVE)) else None,
                            "abs_err_qs": abs(m - alts[QS]) if QS in alts and _finite(m) and _finite(alts[QS]) else None,
                            "call": call, "sign_slope": m_sign, "sign_ok": sign_ok}
    n_th = sum(v["call"] == THEORY for v in per_seed.values())
    n_nv = sum(v["call"] in AGAINST for v in per_seed.values())
    n_pos = sum(bool(v.get("sign_ok")) for v in per_seed.values() if v["counted"])
    missing = [s for s in seeds if s not in present]
    passes = n_th >= need and n_pos >= need
    fails = n_nv >= need
    if theory is None or not theory:
        verdict = NO_THEORY
    elif dup:
        verdict = "UNDECIDED"
    elif passes:
        verdict = "PASS"
    elif fails:
        verdict = "FAIL"
    elif missing:
        verdict = "PENDING"
    else:
        verdict = "MIXED"
    return {"arm": arm, "name": c["name"], "label": c["label"], "lambda_mult": c["lambda_mult"], "rule": decision_rule(arm),
            "verdict": verdict, "n_theory_favoured": n_th, "n_against_theory": n_nv, "n_sign_ok": n_pos,
            "naive_d_trap": {str(k): v for k, v in NAIVE_D_TRAP.items()},
            "need": need, "seeds": list(seeds), "missing_seeds": missing, "duplicate_seeds": dup, "per_seed": per_seed}


def verdict(rows: Sequence[Dict[str, Any]], theory_slopes: Optional[Mapping[str, Mapping[int, float]]]) -> Dict[str, Any]:
    ts = theory_slopes or {}
    return {a: arm_verdict(a, rows, ts.get(a) if theory_slopes is not None else None) for a in ARMS}


# ================================================================ classification of runs
def classify(run_dirs: Iterable[str | Path], ep: Dict[str, Any], p: AnalysisParams, *, preregs: Sequence[str | Path] = (),
             control_root: str | Path = REPO / CONTROL_ROOT, theory: Optional[Dict[str, Any]] = None,
             include_controls: bool = True) -> Dict[str, Any]:
    pr_by_label = {}
    for f in preregs:
        pr = prereg_mod.load_prereg(f)
        pr_by_label[(pr.get("inputs") or {}).get("engine_cell_label")] = (pr, prereg_mod.file_provenance(f), str(f))
    controls = control_dirs(control_root)
    ctl_plans: Dict[Tuple[str, int], pd.DataFrame] = {}
    rows: List[Dict[str, Any]] = []
    grids: List[pd.DataFrame] = []

    def keep_grid(rec: Dict[str, Any]) -> None:
        g = rec.pop("_grid", None)
        if g is not None and len(g):
            g = g.copy()
            g.insert(0, "run_dir", rec["run_dir"])
            g.insert(0, "seed", rec["seed"])
            g.insert(0, "label", rec["label"])
            g.insert(0, "role", rec["role"])
            grids.append(g)

    for d in run_dirs:
        r = load_run(d)
        arm = LABEL_TO_ARM.get(r.label)
        rec: Dict[str, Any] = {"role": "new", "run_dir": str(r.dir), "label": r.label, "seed": r.seed, "arm": arm}
        if arm is None:
            rec.update(counted=False, problem=f"label {r.label!r} is not a CUT cell")
            rows.append(rec)
            continue
        try:
            rec.update(measure_run(r, p, ep))
        except Exception as exc:                         # noqa: BLE001  (reported; the run does not count)
            rec.update(counted=False, problem=f"measurement failed: {type(exc).__name__}: {exc}")
            rows.append(rec)
            continue
        rec.update(rate_mult=r.rate_mult, run_arm=r.arm or r.arm_derived, aborted=r.aborted, abort_reason=r.abort_reason,
                   t0_unix=r.t0_unix, run_status=r.meta.get("status"))
        probs: List[str] = []
        if rec["run_arm"] != "burst":
            probs.append(f"arm {rec['run_arm']!r} != 'burst'")
        if r.rate_mult is None or not math.isclose(r.rate_mult, MULT):
            probs.append(f"rate_mult {r.rate_mult} != {MULT}")
        if r.seed not in SEEDS:
            probs.append(f"seed {r.seed} is not a registered seed {list(SEEDS)}")
        if r.aborted:
            probs.append(f"aborted ({r.abort_reason})")
        # "completed": the client wrote its final meta (status 'finished'; an aborted run also ends 'finished' but carries the
        # abort_reason checked above) and ran the full duration. A client that raised or was killed leaves status 'failed' /
        # 'running' and no outcome, hence no abort_reason: without this check such a run would be counted (with a NaN slope) and
        # would block a resubmitted run of its seed (two counted runs -> UNDECIDED).
        if rec["run_status"] != "finished":
            probs.append(f"not completed: meta status {rec['run_status']!r} (the client did not finish the run)")
        if not r.t_end_s >= DURATION_S - 1e-6:
            probs.append(f"not completed: the run ended at {r.t_end_s:.1f} s, before {DURATION_S:g} s")
        rec["ramp_registered"] = ramp_is_registered(r, arm)
        if not rec["ramp_registered"]:
            probs.append(f"ramp knots {r.meta.get('ramp_knots')} are not the registered {ramp_knots_mult(arm)} x lambda_ref")
        rec["ramp_flat_over_slope_window"] = ramp_flat_over_window(r, *SLOPE_WINDOW_S)
        if not rec["ramp_flat_over_slope_window"]:
            probs.append("the ramp is not at lambda' over the whole slope window")
        ctl = controls.get(("burst", r.seed))
        rec["control_dir"] = str(ctl) if ctl is not None else None
        if ctl is None:
            probs.append("no registered BURST control for this seed")
        else:
            if ("burst", r.seed) not in ctl_plans:
                ctl_plans[("burst", r.seed)] = read_plan(ctl)
            try:
                th = thinned_plan_of_run(r, arm)
            except Exception as exc:                     # noqa: BLE001  (reported; the run does not count)
                th = None
                probs.append(f"cannot rebuild the registered thinned plan: {exc}")
            rec.update(manipulation_check(read_plan(r.dir), ctl_plans[("burst", r.seed)], keep_probability=keep_prob(arm),
                                          thinned=th))
            if not rec["mc_pass"]:
                probs.append("manipulation check failed: " + rec["mc_problem"])
        reg = pr_by_label.get(r.label)
        if reg is not None:
            bl = prereg_mod.run_blockers(reg[0], reg[1], r)
            rec.update(prereg_file=reg[2], prereg_bound=not bl, prereg_blockers="; ".join(bl))
            if bl:
                probs.append("not bound to its registration: " + "; ".join(bl))
        else:
            rec.update(prereg_file=None, prereg_bound=None, prereg_blockers="no --prereg for this label")
            probs.append("binding not checked: no --prereg for this label")
        rec["problem"] = "; ".join(probs)
        rec["counted"] = not probs
        keep_grid(rec)
        rows.append(rec)
    if include_controls:
        for (carm, seed), d in sorted(controls.items()):
            r = load_run(d)
            rec = {"role": f"control_{carm}", "run_dir": str(d), "label": r.label, "seed": seed, "arm": None,
                   "job_id": CONTROL_JOBS[(carm, seed)], "counted": False, "rate_mult": r.rate_mult}
            rec.update(measure_run(r, p, ep))
            keep_grid(rec)
            rows.append(rec)
    slopes = None if theory is None else theory["slopes"]
    out = {"rows": rows, "grid": pd.concat(grids, ignore_index=True) if grids else pd.DataFrame(),
           "verdict": verdict(rows, slopes), "endpoint_problems": basin.endpoint_problems(ep, p)}
    if theory is not None:
        t0s = [r["t0_unix"] for r in rows if r.get("role") == "new" and r.get("counted") and _finite(r.get("t0_unix"))]
        tc = theory.get("git_commit_unix")
        out["theory"] = {k: v for k, v in theory.items() if k != "slopes"}
        out["theory"]["slopes"] = {a: {str(s): v for s, v in per.items()} for a, per in theory["slopes"].items()}
        out["theory"]["predates_all_counted_runs"] = (bool(tc < min(t0s)) if (tc is not None and t0s) else None)
    return out


# ================================================================ submit lines (printed only; never submitted from here)
# The r14 SHED t600 seed 0 submit line, verbatim from provenance/sacct_cited_jobs_2026-11-01.txt (job 17169908, SubmitLine).
R14_SHED_SUBMIT_LINE = (
    "sbatch --parsable --account=f2026.coms.6250.02 --partition=instruction --qos=instruction --time=03:10:00 --mem=48G "
    "--cpus-per-task=16 --job-name=pm-sh600 --nice=57 --export=ALL,ENV_GEN=/work/classtmp/avalse/swapp/envs/swapp,"
    "ENV_SGLANG=/work/classtmp/avalse/swapp/envs/sglang,HF_HOME=/work/classtmp/avalse/swapp/hf,"
    "XDG_CACHE_HOME=/work/classtmp/avalse/swapp/cache,CUDA_HOME_SHIM=/work/classtmp/avalse/swapp/cuda13-home,"
    "HF_REVISION=a09a35458c702b33eeacc393d103063234e8bc28,OUTPUT_FEEDBACK=server,KV_TOKENS=300000,MODE=burst,POLICY=fcfs,"
    "REFRESH=1,LPM_INF=0,MULTS=1.35,SEEDS=0,ARMS=burst,E2_CONFIG=configs/agentload_e2_shed_t600.yaml,"
    "CALIB_FILE=prereg/inputs/2026-10-23/calibration.json,PREREG_FILE=configs/agentload_prereg_2026-10-31_shed_t600.yaml,"
    "ENGINE_LABEL=sglang-fcfs-r1-shed-t600 slurm/sglang_job.sbatch")
SUBMIT_MEM = "20G"


def parse_submit_line(line: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], str]:
    """(sbatch options [(name, value)], export entries [(key, value)], script) of a one-line ``sbatch ... script``."""
    tok = line.split(" ")
    if tok[0] != "sbatch":
        raise ValueError(f"not an sbatch line: {line[:40]!r}")
    opts: List[Tuple[str, str]] = []
    exports: List[Tuple[str, str]] = []
    for t in tok[1:-1]:
        name, _, val = t.partition("=")
        if name == "--export":
            parts = val.split(",")
            if parts[0] != "ALL":
                raise ValueError("--export must start with ALL")
            exports = [tuple(x.split("=", 1)) for x in parts[1:]]           # type: ignore[misc]
        else:
            opts.append((name, val))
    return opts, exports, tok[-1]


def sbatch_line(arm: str, seed: int) -> str:
    c = ARMS[arm]
    opts, exports, script = parse_submit_line(R14_SHED_SUBMIT_LINE)
    new_opt = {"--mem": SUBMIT_MEM, "--time": "03:10:00", "--job-name": c["job_name"], "--account": "f2026.coms.6250.02",
               "--partition": "instruction", "--qos": "instruction"}
    new_exp = {"MULTS": f"{MULT:g}", "SEEDS": str(int(seed)), "E2_CONFIG": c["e2"], "PREREG_FILE": c["out"],
               "ENGINE_LABEL": c["label"]}
    o = " ".join(f"{k}={new_opt.get(k, v)}" if v != "" else k for k, v in opts)
    e = ",".join(f"{k}={new_exp.get(k, v)}" for k, v in exports)
    return f"sbatch {o} --export=ALL,{e} {script}"


def sbatch_lines() -> List[str]:
    return [f"cd {CLONE_DIR}   # a fresh clone at tag {REG_TAG}, git status clean"] + \
        [sbatch_line(a, s) for a in ARMS for s in SEEDS]


# ================================================================ offline plan check (no runs needed)
def plan_check_table(control_root: str | Path = REPO / CONTROL_ROOT, repo: Path = REPO) -> pd.DataFrame:
    """Per arm and seed: the CUT plan built offline from the new config under the same-seed BURST control's own run settings,
    checked against the control's plan.csv (manipulation_check), and compared with the plan the job glue's overrides give."""
    controls = control_dirs(control_root)
    rows = []
    for a in ARMS:
        for s in SEEDS:
            ctl_dir = controls[("burst", s)]
            plan, ctl = plan_under_run_settings(repo / ARMS[a]["e2"], ctl_dir, repo), read_plan(ctl_dir)
            glue_same, _, _ = _frames_equal(plan, offline_plan(a, s, repo=repo), 0.0)
            mc = manipulation_check(plan, ctl, keep_probability=keep_prob(a), thinned=plan)
            lam_plan, _ = plan_rate(plan, *SLOPE_WINDOW_S)
            rows.append({"arm": a, "seed": s, "control": ctl_dir.name, "plan_sessions": len(plan),
                         "control_sessions": len(ctl), "lambda_plan_mult_3000_8700": lam_plan / _lambda_ref(repo),
                         "same_as_job_glue_plan": bool(glue_same), **{k[3:]: v for k, v in mc.items()}})
    return pd.DataFrame(rows)


def _lambda_ref(repo: Path = REPO) -> float:
    return float(json.loads((repo / INPUTS / "calibration.json").read_text())["lambda_miss_turns_based"])


# ================================================================ CLI
_COLS = ("role", "arm", "label", "seed", "job_id", "counted", "problem", "slope_3000_8700", "naive_slope_3000_8700",
         "slope_5700_8700", "lambda_plan_3000_8700", "lambda_plan_mult", "completion_rate_1800_2400",
         "completion_rate_req_1800_2400", "n_completed_1800_2400", "completion_rate_5700_8700", "completion_rate_req_5700_8700",
         "n_completed_5700_8700", "n_pre_cut", "n_post_cut_min", "t_post_cut_min_s", "post_cut_dip_rel", "n_end",
         "hit_followup_eval", "hit_eval", "basin_state", "stuck", "good", "state", "backlog_slope", "slope_threshold", "lambda",
         "window_matches_endpoints", "mc_pass", "mc_problem", "mc_pre_cut_equal", "mc_pre_cut_arrivals_exact",
         "mc_pre_cut_max_abs_d_tool_s", "mc_post_cut_subset_of_control", "mc_post_cut_equals_thinned_plan", "mc_candidates",
         "mc_kept", "mc_shed", "mc_kept_frac", "mc_keep_prob", "mc_kept_z", "mc_burst_ok", "ramp_registered",
         "ramp_flat_over_slope_window", "rate_mult", "aborted", "run_status", "run_end_s", "prereg_bound", "prereg_blockers",
         "control_dir", "run_dir")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r15_cut")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill", help="write the FILLED registration of one CUT arm (never overwrites)")
    f.add_argument("--arm", required=True, choices=sorted(ARMS))
    f.add_argument("--out", default=None)
    d = sub.add_parser("diff", help="scripted diff of a CUT registration against the 2026-10-24 registration")
    d.add_argument("--arm", required=True, choices=sorted(ARMS))
    d.add_argument("--file", default=None)
    sub.add_parser("plan-check", help="offline CUT plans vs the committed 1.65 x BURST control plans")
    sub.add_parser("sbatch-lines", help="print the six submit lines (never submits)")
    c = sub.add_parser("classify", help="per-run measurements, manipulation check, binding and the registered verdict")
    c.add_argument("--run-dirs", nargs="+", required=True)
    c.add_argument("--prereg", nargs="*", default=[str(REPO / a["out"]) for a in ARMS.values()],
                   help="the CUT registrations (binding of each run, by label; default: the two files)")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--theory", default=None, help="the theory session's frozen slopes file (YAML/JSON, see the docstring)")
    g.add_argument("--theory-git", default=None,
                   help=f"REF:PATH, e.g. {THEORY_TAG}:results/theory/icml/cut_predictions.json (read with git show)")
    c.add_argument("--control-root", default=str(REPO / CONTROL_ROOT))
    c.add_argument("--endpoints", default=str(REPO / ENDPOINTS))
    c.add_argument("--params", default=str(REPO / PARAMS))
    c.add_argument("--set", action="append", default=[])
    c.add_argument("--out-root", default="results")
    args = ap.parse_args(argv)
    if args.cmd == "fill":
        a = ARMS[args.arm]
        out = Path(args.out or REPO / a["out"])
        pr = fill_registration(args.arm)
        res = registration_diff(yaml.safe_load((REPO / PARENT).read_text()), pr)
        if res["forbidden"]:
            print(f"refusing: forbidden differences from {PARENT}: {res['forbidden']}", file=sys.stderr)
            return 1
        try:
            with out.open("xb") as fh:                                         # refuses to overwrite
                fh.write(dump_registration(pr))
        except FileExistsError:
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        print(f"wrote {out} status={pr['status']} label={pr['inputs']['engine_cell_label']} arms={pr['protocol']['arms']} "
              f"lambda_mults={pr['lambda_selection']['lambda_mults']} e2_config_sha256={pr['protocol']['e2_config_sha256']}")
        print(f"registration_diff vs {PARENT}: allowed={res['allowed']} derived={len(res['derived'])} forbidden=[]")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0
    if args.cmd == "diff":
        a = ARMS[args.arm]
        parent = yaml.safe_load((REPO / PARENT).read_text())
        child = yaml.safe_load(Path(args.file or REPO / a["out"]).read_text())
        res = registration_diff(parent, child)
        fa, fb = _flatten(parent), _flatten(child)
        print(f"parent {PARENT}  vs  {args.file or a['out']}")
        for kind in ("allowed", "derived", "forbidden"):
            print(f"{kind}: {len(res[kind])}")
            for k in res[kind]:
                va, vb = str(fa.get(k, "<missing>")), str(fb.get(k, "<missing>"))
                print(f"  {k}: {va if len(va) < 90 else va[:87] + '...'}  ->  {vb if len(vb) < 90 else vb[:87] + '...'}")
        return 1 if res["forbidden"] else 0
    if args.cmd == "plan-check":
        t = plan_check_table()
        cols = ["arm", "seed", "control", "pre_cut_sessions", "pre_cut_equal", "pre_cut_arrivals_exact",
                "pre_cut_max_abs_d_tool_s", "candidates", "kept", "shed", "kept_frac", "keep_prob", "kept_z",
                "post_cut_subset_of_control", "burst_sessions", "lambda_plan_mult_3000_8700", "same_as_job_glue_plan", "pass"]
        with pd.option_context("display.width", 250, "display.max_columns", 40):
            print(t[cols].to_string(index=False))
        return 0 if bool(t["pass"].all() and t["same_as_job_glue_plan"].all()) else 1
    if args.cmd == "sbatch-lines":
        print("\n".join(sbatch_lines()))
        return 0
    from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta
    t0 = datetime.now()
    git = git_info(REPO)
    p = load_params(args.params, [f"trap_v2.eval_from_s={REGISTERED_EVAL_FROM_S}", *args.set])
    ep = basin.load_endpoints(args.endpoints)
    theory = None
    if args.theory or args.theory_git:
        theory = load_theory_slopes(args.theory, git_ref=args.theory_git)
    res = classify(args.run_dirs, ep, p, preregs=args.prereg, control_root=args.control_root, theory=theory)
    od = new_result_dir(args.out_root, "agentload_analysis_r15_cut")
    df = pd.DataFrame(res["rows"])
    df[[k for k in _COLS if k in df.columns]].to_csv(od / "cut_runs.csv", index=False)
    res["grid"].to_csv(od / "cut_n_grid.csv", index=False)
    out = {"verdict": res["verdict"], "theory": res.get("theory"), "endpoint_problems": res["endpoint_problems"],
           "endpoints": ep, "rules": {a: decision_rule(a) for a in ARMS}}
    (od / "cut_verdict.json").write_text(json.dumps(out, indent=2, default=json_default))
    write_meta(od, build_meta(experiment="agentload_analysis_r15_cut",
                              argv=[sys.executable, "-m", "analysis.r15_cut", *(argv or sys.argv[1:])],
                              seeds=sorted({int(r["seed"]) for r in res["rows"] if r.get("seed") is not None}),
                              hardware=default_hardware(), git=git, t_start=t0, t_end=datetime.now(), status="finished",
                              extra={"run_dirs": [str(x) for x in args.run_dirs], "prereg": list(args.prereg),
                                     "control_root": str(args.control_root), "theory": args.theory or args.theory_git}))
    for a, v in res["verdict"].items():
        print(f"{v['name']} ({v['label']}): {v['verdict']}  theory-favoured {v['n_theory_favoured']}, against the theory "
              f"(naive / quasi-static / unstuck) {v['n_against_theory']}, sign clause {v['n_sign_ok']} of the counted seeds; "
              f"missing {v['missing_seeds']}")
    for msg in res["endpoint_problems"]:
        print(f"ENDPOINT PROBLEM: {msg}", file=sys.stderr)
    print(f"r15 CUT outputs: {od}")
    return 1 if res["endpoint_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
