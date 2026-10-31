"""B1 basin test (r11): does the good state have a FINITE basin of attraction on the real engine?

One BURST arm per job at 1.65 x lambda_ref (300k pool, SGLang FCFS, refresh on), seeds 0-2, burst sizes n = 100 and n = 25
(60 s wide at t_b = 1200 s, 8700 s runs). Every run pairs by seed (common random numbers: the base sessions are identical,
and the burst start times are the first n of the n = 200 draw) with the committed 300k E2 runs of jobs 17093387-404 at the same
rate: NOBURST (n = 0) and BURST (n = 200).

Two parts:

``fill``      the two registrations (configs/agentload_prereg_2026-10-30_b100.yaml / _b25.yaml). They are filled by
              ``analysis.prereg.fill`` from the SAME inputs as configs/agentload_prereg_2026-10-24.yaml
              (prereg/inputs/2026-10-23/), with the cell's E2 config (protocol.burst_n = n), the single point 1.65 and the
              cap rule smallest_within_margin. The measured values are those of cell ``sglang-fcfs-r1`` (these runs share its
              hardware, pool, policy and refresh flag); ``prereg fill --engine-cell-label sglang-fcfs-r1-b100`` cannot be used
              because ``fill`` looks the label up in mu_curve.json and the E0b bracket, which only hold ``sglang-fcfs-r1``. So the
              fill runs under the measured label and only ``inputs.engine_cell_label`` is then set to the new cell's label,
              which keeps the runs out of the registered sglang-fcfs-r1 verdict. Output is LF, never overwrites.

``classify``  per run STUCK / GOOD from the frozen endpoint definitions (configs/r11_basin_predict.yaml), on top of the
              registered trap_v2 classification (``analysis.trap_v2.trap_v2_run``), joined by seed with the committed n = 0 and
              n = 200 runs; writes a new dir <out-root>/agentload_analysis_basin/<stamp>/ with basin_runs.csv and
              basin_verdict.json (the B1 decision rule).

Frozen primary endpoints (plan B1; the numbers are read from the frozen yaml, these are the definitions):
  STUCK := hit_eval < stuck_hit_below (0.2, the registered constant burst.trap_hit_below) over the evaluation window
           [t_b + eval_from_s, end) = [5700, 8700) s
  GOOD  := trap_v2 RECOVERED, or (hit_eval > good_hit_above (0.8) and backlog slope <= slope_frac * (lambda - lambda_miss),
           the registered trap_v2 slope threshold)
  The trap_v2 TRAPPED label is co-primary for n = 100 only.
Decision (per seed, CRN pairs, no pooled intervals): basin shown (PASS) iff n = 100 is STUCK in >= 2/3 seeds AND n = 25 is
GOOD in >= 2/3 seeds; n = 100 STUCK >= 2/3 but TRAPPED < 2/3 -> 'stuck, slope-indeterminate'; n = 100 GOOD >= 2/3 -> the
simulator's critical size is refuted, the basin edge lies between 100 and 200; n = 25 STUCK >= 2/3 -> 'even 25 traps'.

B2 (r14, remedy N1: the basin dose-response) adds burst sizes n = 40, 50 and 60 with the same design (BURST arm, 1.65 x, seeds
0-2, CRN with the runs above), the same frozen endpoints (configs/r11_basin_predict.yaml, unchanged) and the registrations
configs/agentload_prereg_2026-10-31_b40.yaml / _b50.yaml / _b60.yaml (``fill --n 40|50|60``; n = 100 / 25 fill byte-identically
as before). Frozen B2 rule: the basin boundary is bracketed iff n = 40 is GOOD in >= 2/3 seeds and n = 60 is STUCK in >= 2/3
seeds (:func:`bracket_decision`); n = 50 does not enter the rule. The seven-point curve n = 0, 25, 40, 50, 60, 100, 200
(per seed, :func:`curve_table`) is reported against the frozen committor of the theory predictions.
A B2 run enters the rule and its curve points only if :func:`b2_eligibility` passes: the cell label, the BURST arm at 1.65 x,
not aborted, the frozen window, bound to its registration (``--prereg`` with the B2 files; ``prereg.run_blockers`` empty) and
a config.yaml equal to the tagged cell config (``B2_CONFIG_SHA256``; the B2 registrations predate the e2_config_sha256
binding). Two runs of one seed leave the rule undecided (None) rather than letting the seed vote twice. Runs that fail are
listed in ``b2_not_counted``. (Review fix after r14-basin2-reg, before any B2 job: stricter only; the B1 decision is unchanged.)

CLI:  python -m analysis.basin fill --n 100 --out configs/agentload_prereg_2026-10-30_b100.yaml
      python -m analysis.basin classify --endpoints configs/r11_basin_predict.yaml --run-dirs RUN [RUN ...]
                                        [--baseline-dirs RUN ...] [--prereg FILE ...] [--out-root results]
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

import pandas as pd
import yaml

from . import prereg as prereg_mod
from .load import Run, load_run
from .params import AnalysisParams, load_params
from .trap_v2 import trap_v2_run

REPO = Path(__file__).resolve().parent.parent
MEASURED_CELL = "sglang-fcfs-r1"
CELL_LABEL = "sglang-fcfs-r1-b{n}"
BASIN_NS = (25, 100)
BASIN2_NS = (40, 50, 60)                  # B2 (r14, N1): the dose-response cells
BASIN2_BRACKET = (40, 60)                 # the frozen bracketing rule: n=40 GOOD >= 2/3 and n=60 STUCK >= 2/3
CURVE_NS = (0, 25, 40, 50, 60, 100, 200)  # the seven-point curve reported against the frozen committor
# sha256 of the B2 cell configs as tagged (r14-basin2-reg). The B2 registrations predate the e2_config_sha256 binding, so
# classify binds each B2 run's config.yaml (CRLF read as LF) to these bytes itself before the run enters the B2 rule.
B2_CONFIG_SHA256 = {40: "33257fb768ce8420e78278c9dfd9e0cce0f91e2cdc802e952a0b3d24fcc3036b",
                    50: "7f5710cfeec5bdbe41c4d0b8e711c459d0e05b96b0841a6de8b53a287e5ce909",
                    60: "284cc2d75c6e9cdb686ff73c6363a93168d2aa3cafc9b48651cf43e4d131eb2c"}
BASIN_MULT = 1.65
BASIN_SEEDS = (0, 1, 2)
INPUTS = "prereg/inputs/2026-10-23"
TEMPLATE = "configs/agentload_prereg_template.yaml"
PARENT_PREREG = "configs/agentload_prereg_2026-10-24.yaml"
DEFAULT_E2_CONFIG = "configs/agentload_e2_burst.yaml"
BASELINE_RUN_ROOT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst"
PARAMS = "configs/agentload_analysis.yaml"
REGISTERED_EVAL_FROM_S = 4500.0          # HIT_EVAL_FROM_S of the job glue = pass_rule.eval_from_s of the registrations


def e2_config_path(n: int) -> str:
    return f"configs/agentload_e2_burst_n{n}.yaml"


# ---------------------------------------------------------------- registrations
_HYP = {
    100: ("n=100 (200k first-prompt tokens, below the 300k pool) STUCK in >= 2/3 seeds; trap_v2 TRAPPED is co-primary for "
          "this cell only (in the round-7 simulator sweep, notes/ROBUSTNESS_r7.md item 3, every n=100 run was stuck but the slope "
          "rule called only 8/10 TRAPPED at 1.65 x and 5/10 at 1.35 x), and STUCK with TRAPPED in < 2/3 "
          "is reported as 'stuck, slope-indeterminate'"),
    25: "n=25 GOOD in >= 2/3 seeds",
    40: "n=40 GOOD in >= 2/3 seeds (the lower half of the bracket)",
    50: ("none for n=50 alone: it is a point of the seven-point curve, reported per seed, and does not enter the bracketing "
         "rule"),
    60: "n=60 STUCK in >= 2/3 seeds (the upper half of the bracket)",
}


def rule_text(n: int) -> str:
    """lambda_selection.rule of the n-cell registration: why 1.65, what is paired, and the frozen primary endpoints."""
    if n in BASIN2_NS:
        return _rule_text_b2(n)
    return (
        f"Single point {BASIN_MULT:g} x lambda_ref: the upper registered point (m2) of {PARENT_PREREG}, same inputs "
        f"({INPUTS}: mu_curve, calibration, E0b bracket), same window (1, 2.0) x lambda_ref and the same 1/3-2/3 rule written "
        "on 2026-10-23 before E0b was read; reused unchanged so that each run pairs by seed (common random numbers: identical "
        "base sessions; the burst start times are the first n of the n=200 draw) with the committed 300k E2 NOBURST (n=0) and "
        "BURST (n=200) runs at 1.65 x (jobs 17093387-404). The measured values are those of cell "
        f"{MEASURED_CELL} (same hardware, pool, policy and refresh flag; filled by analysis.basin fill, which runs "
        f"analysis.prereg.fill under {MEASURED_CELL} and then sets only inputs.engine_cell_label), so these runs stay out of "
        f"the {MEASURED_CELL} verdict. Only the burst size differs: protocol.burst_n = {n} from {e2_config_path(n)}, a byte "
        f"copy of {DEFAULT_E2_CONFIG} except arrivals.burst.n (the research_question's '200-session burst' is template text; "
        "this cell's burst is protocol.burst_n). Basin test B1 (r11): BURST arm only, seeds 0, 1, 2. FROZEN PRIMARY "
        "ENDPOINTS (definitions frozen in configs/r11_basin_predict.yaml; per run, over the registered evaluation window "
        "[t_burst_s + eval_from_s, duration_s) = [5700, 8700) s, hit = pass_rule.hit_metric): STUCK := hit_eval < 0.2 (the "
        "registered constant burst.trap_hit_below); GOOD := trap_v2 RECOVERED (pass_rule recovered_*), or (hit_eval > 0.8 and "
        "backlog slope <= slope_frac x (lambda - lambda_miss), the registered trap_v2 slope threshold). "
        f"Hypothesis: {_HYP[n]}. Basin shown on the engine iff n=100 is STUCK in >= 2/3 seeds AND n=25 is GOOD in >= 2/3 "
        "seeds; statistics per seed (CRN pairs), no pooled intervals. The pass_rule and kill_conditions below are the "
        "template's three-arm rule, inherited unchanged so the rule keys match the analysis; this one-arm cell is judged by "
        "the endpoints above (analysis/basin.py), not by the paired PASS rule.")


def _rule_text_b2(n: int) -> str:
    """lambda_selection.rule of a B2 (dose-response) cell: the B1 text's design and endpoints plus the frozen N1 rule."""
    return (
        f"Single point {BASIN_MULT:g} x lambda_ref: the upper registered point (m2) of {PARENT_PREREG}, same inputs "
        f"({INPUTS}: mu_curve, calibration, E0b bracket), same window (1, 2.0) x lambda_ref and the same 1/3-2/3 rule written "
        "on 2026-10-23 before E0b was read; reused unchanged so that each run pairs by seed (common random numbers: identical "
        "base sessions; the burst start times are the first n of the n=200 draw) with the committed 300k E2 NOBURST (n=0) and "
        "BURST (n=200) runs at 1.65 x (jobs 17093387-404) and with the B1 runs n=25 and n=100 (registrations "
        "configs/agentload_prereg_2026-10-30_b25.yaml / _b100.yaml, tag r11-basin-reg). The measured values are those of cell "
        f"{MEASURED_CELL} (same hardware, pool, policy and refresh flag; filled by analysis.basin fill, which runs "
        f"analysis.prereg.fill under {MEASURED_CELL} and then sets only inputs.engine_cell_label), so these runs stay out of "
        f"the {MEASURED_CELL} verdict. Only the burst size differs: protocol.burst_n = {n} from {e2_config_path(n)}, a byte "
        f"copy of {DEFAULT_E2_CONFIG} except arrivals.burst.n (the research_question's '200-session burst' is template text; "
        "this cell's burst is protocol.burst_n). Basin dose-response test B2 (r14, remedy N1): BURST arm only, burst sizes "
        "n = 40, 50, 60, seeds 0, 1, 2. FROZEN PRIMARY ENDPOINTS (the B1 definitions frozen in configs/r11_basin_predict.yaml, "
        "unchanged; per run, over the registered evaluation window [t_burst_s + eval_from_s, duration_s) = [5700, 8700) s, "
        "hit = pass_rule.hit_metric): STUCK := hit_eval < 0.2 (the registered constant burst.trap_hit_below); GOOD := trap_v2 "
        "RECOVERED (pass_rule recovered_*), or (hit_eval > 0.8 and backlog slope <= slope_frac x (lambda - lambda_miss), the "
        f"registered trap_v2 slope threshold). Hypothesis: {_HYP[n]}. FROZEN DECISION RULE (N1): the basin boundary is "
        "bracketed iff b=40 is GOOD in >=2/3 seeds and b=60 STUCK in >=2/3 seeds; the seven-point curve 0,25,40,50,60,100,200 "
        "is reported against the frozen committor (the theory predictions, committed and pushed before the first B2 job is "
        "submitted). b=50 does not enter the bracketing rule. Statistics per seed (CRN pairs), no pooled intervals; a missing "
        "seed counts as not meeting a criterion. The pass_rule and kill_conditions below are the template's three-arm rule, "
        "inherited unchanged so the rule keys match the analysis; this one-arm cell is judged by the endpoints and the rule "
        "above (analysis/basin.py), not by the paired PASS rule.")


def fill_registration(n: int, *, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    """The filled registration of the n-cell (a dict; :func:`write_registration` writes it)."""
    if n not in _HYP:
        raise ValueError(f"no B1 cell for burst size {n} (cells: {sorted(_HYP)})")
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                  # noqa: E731
    e2_rel = e2_config_path(n)
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{INPUTS}/mu_curve.json")), json.loads(rd(f"{INPUTS}/calibration.json")),
        e0b=json.loads(rd(f"{INPUTS}/lambda_cap_bracket.json")), e2_cfg=yaml.safe_load(rd(e2_rel)),
        lambda_mults=[BASIN_MULT], rule=rule_text(n), engine_cell_label=MEASURED_CELL,
        mu_curve_path=f"{INPUTS}/mu_curve.json", calibration_path=f"{INPUTS}/calibration.json",
        e0b_path=f"{INPUTS}/lambda_cap_bracket.json", e2_cfg_path=e2_rel, n_cap_rule="smallest_within_margin", p=p)
    if pr["status"] != "FILLED":
        raise ValueError(f"fill did not produce a FILLED registration: {pr['fill_problems']}")
    if int(pr["protocol"]["burst_n"]) != n:
        raise ValueError(f"{e2_rel} registers burst_n={pr['protocol']['burst_n']}, not {n}")
    pr["inputs"]["engine_cell_label"] = CELL_LABEL.format(n=n)
    return pr


def dump_registration(pr: Dict[str, Any]) -> bytes:
    """Exactly what ``analysis.prereg fill`` writes (yaml.safe_dump, sort_keys=False), with LF line ends on every OS."""
    return yaml.safe_dump(pr, sort_keys=False).encode("utf-8")


def write_registration(n: int, out: Path, *, repo: Path = REPO) -> Dict[str, Any]:
    pr = fill_registration(n, repo=repo)
    with Path(out).open("xb") as f:                                             # refuses to overwrite
        f.write(dump_registration(pr))
    return pr


def _flatten(d: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(d, list):
        out[prefix] = tuple(d)
    else:
        out[prefix] = d
    return out


# fields of a B1 registration that may differ from the 2026-10-24 parent: the cell label, the cell's E2 config path, the burst
# size, the lambda list and its rule text, and the CAPPED-arm drain numbers that fill derives from burst_n and the lambda list
REGISTRATION_DIFF_ALLOWED = ("inputs.engine_cell_label", "inputs.e2_config", "protocol.burst_n",
                             "lambda_selection.lambda_mults", "lambda_selection.rule")
REGISTRATION_DIFF_DERIVED_PREFIX = "predicted_boundaries.capped_drain."


def registration_diff(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, List[str]]:
    """Leaves that differ between two registrations, split into allowed / derived (capped_drain) / forbidden."""
    a, b = _flatten(parent), _flatten(child)
    keys = sorted(set(a) | set(b))
    diff = [k for k in keys if a.get(k, "<missing>") != b.get(k, "<missing>")]
    return {"allowed": [k for k in diff if k in REGISTRATION_DIFF_ALLOWED],
            "derived": [k for k in diff if k.startswith(REGISTRATION_DIFF_DERIVED_PREFIX)],
            "forbidden": [k for k in diff if k not in REGISTRATION_DIFF_ALLOWED
                          and not k.startswith(REGISTRATION_DIFF_DERIVED_PREFIX)]}


# ---------------------------------------------------------------- plans (no engine)
def basin_plan(cfg_path: str | Path, seed: int, *, rate_mult: float = BASIN_MULT,
               calibration: str = f"{INPUTS}/calibration.json", repo: Path = REPO, burst_null: bool = False):
    """The open-loop session plan an E2 run of ``cfg_path`` would execute (the generator's own plan code, no server)."""
    from agentload.config import load_config, resolve_rate
    from agentload.workload import build_open_plan

    sets = [f"run.seed={int(seed)}", f"arrivals.rate_mult={rate_mult}",
            f"arrivals.lambda_ref=\"{calibration}:lambda_miss_turns_based\""]          # repo-relative, as the job passes it
    if burst_null:
        sets.append("arrivals.burst=null")
    cfg, _ = load_config(Path(cfg_path), sets)
    rate = resolve_rate(cfg.arrivals, repo)
    return build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, [])


# ---------------------------------------------------------------- endpoints
_ENDPOINT_ALIASES = {
    "stuck_hit_below": ("stuck_hit_below", "trap_hit_below", "stuck_hit_eval_below"),
    "good_hit_above": ("good_hit_above", "good_hit_eval_above", "hit_above"),
    "eval_window_s": ("eval_window_s", "window_s", "eval_window"),
    "trapped_co_primary_n": ("trapped_co_primary_n", "trap_v2_co_primary_n", "co_primary_n"),
}


def load_endpoints(path: str | Path) -> Dict[str, Any]:
    """The frozen endpoint constants. Read from the ``endpoints`` (or ``basin_endpoints`` / ``primary_endpoints``) mapping of
    the frozen yaml, keys (aliases in _ENDPOINT_ALIASES): stuck_hit_below, good_hit_above, eval_window_s [start, end] in run
    seconds, trapped_co_primary_n (list of burst sizes). Missing keys are an error: the endpoints must come from the frozen
    file, never from defaults here."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    sec = None
    for name in ("endpoints", "basin_endpoints", "primary_endpoints"):
        if isinstance(raw.get(name), dict):
            sec = raw[name]
            break
    if sec is None:
        raise ValueError(f"{path}: no 'endpoints' mapping (expected keys {sorted(_ENDPOINT_ALIASES)})")
    out: Dict[str, Any] = {}
    for key, names in _ENDPOINT_ALIASES.items():
        hit = [n for n in names if n in sec]
        if not hit:
            raise ValueError(f"{path}: endpoints lacks {key!r} (any of {list(names)})")
        out[key] = sec[hit[0]]
    w = out["eval_window_s"]
    if not (isinstance(w, (list, tuple)) and len(w) == 2 and float(w[0]) < float(w[1])):
        raise ValueError(f"{path}: eval_window_s must be [start, end] in run seconds, got {w!r}")
    out["eval_window_s"] = [float(w[0]), float(w[1])]
    out["stuck_hit_below"], out["good_hit_above"] = float(out["stuck_hit_below"]), float(out["good_hit_above"])
    co = out["trapped_co_primary_n"]
    out["trapped_co_primary_n"] = [int(x) for x in (co if isinstance(co, (list, tuple)) else [co])]
    out["source"] = str(path)
    return out


def endpoint_problems(ep: Dict[str, Any], p: AnalysisParams, t_burst: float = 1200.0) -> List[str]:
    """Frozen endpoints that disagree with the registered analysis constants (they must not)."""
    out = []
    if not math.isclose(ep["stuck_hit_below"], float(p.burst["trap_hit_below"])):
        out.append(f"stuck_hit_below {ep['stuck_hit_below']} != registered burst.trap_hit_below {p.burst['trap_hit_below']}")
    if not math.isclose(ep["eval_window_s"][0] - t_burst, float(p.trap_v2["eval_from_s"])):
        out.append(f"eval window start {ep['eval_window_s'][0]} != t_b + trap_v2.eval_from_s = {t_burst + float(p.trap_v2['eval_from_s'])}")
    return out


# ---------------------------------------------------------------- per-run classification
def burst_n_of(run: Run) -> int:
    b = (run.cfg.get("arrivals") or {}).get("burst")
    return int(b.get("n") or 0) if b else 0


def classify_run(run: Run, p: AnalysisParams, ep: Dict[str, Any]) -> Dict[str, Any]:
    """trap_v2 record of the run plus burst_n, STUCK, GOOD (see module docstring)."""
    rec = trap_v2_run(run, p)
    rec["burst_n"] = burst_n_of(run)
    w0, w1 = ep["eval_window_s"]
    rec["window_matches_endpoints"] = bool(math.isclose(rec["eval_from"], w0, abs_tol=1e-6)
                                           and abs(rec["t_end_s"] - w1) <= 1.0)
    h, slope, thr = rec["hit_eval"], rec["backlog_slope"], rec["slope_threshold"]
    ok = lambda x: x is not None and not (isinstance(x, float) and math.isnan(x))           # noqa: E731
    rec["stuck"] = bool(ok(h) and h < ep["stuck_hit_below"])
    rec["good_by_recovered"] = bool(rec["state"] == "recovered")
    rec["good_by_hit_slope"] = bool(ok(h) and ok(slope) and ok(thr) and h > ep["good_hit_above"] and slope <= thr)
    rec["good"] = bool(rec["good_by_recovered"] or rec["good_by_hit_slope"])
    rec["basin_state"] = ("stuck+good" if rec["stuck"] and rec["good"] else "stuck" if rec["stuck"]
                          else "good" if rec["good"] else "neither")
    return rec


def _count(recs: Sequence[Dict[str, Any]], key: str) -> int:
    return sum(bool(r.get(key)) for r in recs)


def decision(by_n: Dict[int, List[Dict[str, Any]]], seeds: Sequence[int] = BASIN_SEEDS,
             co_primary_n: Sequence[int] = (100,)) -> Dict[str, Any]:
    """The B1 decision rule over the per-seed records of each burst size (a missing seed counts as not meeting a criterion)."""
    need = math.ceil(2 * len(seeds) / 3)
    out: Dict[str, Any] = {"seeds": list(seeds), "need_of_seeds": need, "cells": {}}
    for n, recs in sorted(by_n.items()):
        got = sorted(r["seed"] for r in recs)
        c = {"n_runs": len(recs), "seeds_present": got, "missing_seeds": [s for s in seeds if s not in got],
             "stuck": _count(recs, "stuck"), "good": _count(recs, "good"), "trapped": _count(recs, "trapped")}
        c["stuck_majority"], c["good_majority"] = c["stuck"] >= need, c["good"] >= need
        if n in co_primary_n:
            c["trapped_majority"] = c["trapped"] >= need
        out["cells"][str(n)] = c
    c100, c25 = out["cells"].get("100"), out["cells"].get("25")
    notes = []
    if c100 is not None:
        if c100["stuck_majority"] and not c100.get("trapped_majority", True):
            notes.append("n=100: stuck, slope-indeterminate (STUCK >= 2/3 but trap_v2 TRAPPED < 2/3)")
        if c100["good_majority"]:
            notes.append("n=100: GOOD >= 2/3: the simulator's critical size is refuted on the engine; the basin edge lies "
                         "between 100 and 200")
    if c25 is not None and c25["stuck_majority"]:
        notes.append("n=25: STUCK >= 2/3: the basin is smaller than predicted ('even 25 traps')")
    # tri-state: True / False once the present seeds decide it, None while missing seeds could still change it
    if c100 is None or c25 is None:
        out["basin_pass"] = None
    elif c100["stuck_majority"] and c25["good_majority"]:
        out["basin_pass"] = True
    elif (c100["stuck"] + len(c100["missing_seeds"]) < need) or (c25["good"] + len(c25["missing_seeds"]) < need):
        out["basin_pass"] = False
    else:
        out["basin_pass"] = None
    out["incomplete"] = [n for n, c in out["cells"].items() if c["missing_seeds"] and n in ("25", "100")]
    out["notes"] = notes
    return out


def bracket_decision(by_n: Dict[int, List[Dict[str, Any]]], seeds: Sequence[int] = BASIN_SEEDS,
                     bracket: Sequence[int] = BASIN2_BRACKET) -> Dict[str, Any]:
    """The frozen B2 (N1) rule: the basin boundary is bracketed iff n=bracket[0] (40) is GOOD in >= 2/3 seeds AND
    n=bracket[1] (60) is STUCK in >= 2/3 seeds. Tri-state like :func:`decision`: True / False once the present seeds decide
    it, None while missing seeds could still change it. A missing seed counts as not meeting a criterion."""
    need = math.ceil(2 * len(seeds) / 3)
    lo, hi = int(bracket[0]), int(bracket[1])
    cells: Dict[str, Any] = {}
    for n in (lo, hi):
        recs = [r for r in by_n.get(n, []) if r["seed"] in seeds]
        got = sorted(r["seed"] for r in recs)
        cells[str(n)] = {"n_runs": len(recs), "seeds_present": got, "missing_seeds": [s for s in seeds if s not in got],
                         "duplicate_seeds": sorted({s for s in got if got.count(s) > 1}),
                         "stuck": _count(recs, "stuck"), "good": _count(recs, "good")}
    clo, chi = cells[str(lo)], cells[str(hi)]
    lo_ok, hi_ok = clo["good"] >= need, chi["stuck"] >= need
    if clo["duplicate_seeds"] or chi["duplicate_seeds"]:
        # two runs of one seed (a resubmission): one seed must not vote twice; left undecided for a human to resolve
        lo_ok = hi_ok = False
        bracketed: Optional[bool] = None
    elif lo_ok and hi_ok:
        bracketed = True
    elif clo["good"] + len(clo["missing_seeds"]) < need or chi["stuck"] + len(chi["missing_seeds"]) < need:
        bracketed = False
    else:
        bracketed = None
    notes = []
    for c in (clo, chi):
        if c["duplicate_seeds"]:
            notes.append(f"duplicate seed runs {c['duplicate_seeds']}: undecided until resolved (first registered run per seed)")
    if clo["stuck"] >= need:
        notes.append(f"n={lo}: STUCK >= 2/3: the boundary lies below {lo}")
    if chi["good"] >= need:
        notes.append(f"n={hi}: GOOD >= 2/3: the boundary lies above {hi}")
    return {"rule": f"bracketed iff n={lo} GOOD >= {need}/{len(seeds)} seeds and n={hi} STUCK >= {need}/{len(seeds)} seeds",
            "seeds": list(seeds), "need_of_seeds": need, "cells": cells, f"good_majority_{lo}": lo_ok,
            f"stuck_majority_{hi}": hi_ok, "bracketed": bracketed, "notes": notes,
            "incomplete": [n for n, c in cells.items() if c["missing_seeds"]]}


def curve_table(by_n: Dict[int, List[Dict[str, Any]]], seeds: Sequence[int] = BASIN_SEEDS,
                ns: Sequence[int] = CURVE_NS) -> Dict[str, Any]:
    """The seven-point dose-response curve: per burst size, the per-seed basin_state / hit_eval and the STUCK / GOOD counts."""
    out: Dict[str, Any] = {}
    for n in ns:
        recs = {r["seed"]: r for r in by_n.get(n, []) if r["seed"] in seeds}
        out[str(n)] = {"per_seed": {str(s): (None if s not in recs else
                                             {"basin_state": recs[s].get("basin_state"), "hit_eval": recs[s].get("hit_eval"),
                                              "stuck": recs[s].get("stuck"), "good": recs[s].get("good")}) for s in seeds},
                       "stuck": _count(list(recs.values()), "stuck"), "good": _count(list(recs.values()), "good"),
                       "n_seeds": len(recs)}
    return out


def find_baselines(root: str | Path, rate_mult: float = BASIN_MULT, label: str = MEASURED_CELL,
                   seeds: Sequence[int] = BASIN_SEEDS) -> List[Path]:
    """Run dirs of the committed 300k E2 NOBURST (n=0) and BURST (n=200) arms at ``rate_mult`` for ``seeds``."""
    out = []
    for d in sorted(Path(root).iterdir()):
        if not (d / "meta.json").is_file():
            continue
        r = load_run(d)
        if r.label == label and r.seed in seeds and r.rate_mult is not None and math.isclose(r.rate_mult, rate_mult) \
                and (r.arm or r.arm_derived) in ("burst", "noburst"):
            out.append(d)
    return out


def _config_text_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def b2_eligibility(rec: Dict[str, Any]) -> tuple:
    """(counted, problem) of a run for the B2 rule: a NEW run of burst size 40 / 50 / 60 counts only if it carries the
    cell label, ran the BURST arm at 1.65 x, completed over the frozen window, is bound to its registration
    (prereg.run_blockers empty; --prereg is required) and its config.yaml is the tagged cell config byte for byte."""
    n = int(rec.get("burst_n") or 0)
    if n not in BASIN2_NS:
        return False, ""
    probs = []
    if rec.get("role") != "new":
        probs.append(f"role {rec.get('role')!r} is not a new run")
    if rec.get("label") != CELL_LABEL.format(n=n):
        probs.append(f"label {rec.get('label')!r} != {CELL_LABEL.format(n=n)!r}")
    if rec.get("arm") != "burst":
        probs.append(f"arm {rec.get('arm')!r} != 'burst'")
    rm = rec.get("rate_mult")
    if rm is None or not math.isclose(float(rm), BASIN_MULT):
        probs.append(f"rate_mult {rm} != {BASIN_MULT}")
    if rec.get("aborted"):
        probs.append(f"aborted ({rec.get('abort_reason')})")
    if not rec.get("window_matches_endpoints"):
        probs.append("evaluation window does not match the frozen endpoints")
    if rec.get("prereg_bound") is not True:
        probs.append("not bound to its registration: " + (rec.get("prereg_blockers") or "no --prereg for this label"))
    cfile = Path(rec["run_dir"]) / "config.yaml"
    if not cfile.is_file():
        probs.append("run dir has no config.yaml")
    elif _config_text_sha256(cfile) != B2_CONFIG_SHA256[n]:
        probs.append(f"config.yaml sha256 {_config_text_sha256(cfile)} != the tagged cell config {B2_CONFIG_SHA256[n]}")
    return (not probs), "; ".join(probs)


def classify(run_dirs: Iterable[str | Path], baseline_dirs: Iterable[str | Path], ep: Dict[str, Any], p: AnalysisParams,
             preregs: Sequence[str | Path] = ()) -> Dict[str, Any]:
    pr_by_label = {}
    for f in preregs:
        pr = prereg_mod.load_prereg(f)
        pr_by_label[(pr.get("inputs") or {}).get("engine_cell_label")] = (pr, prereg_mod.file_provenance(f), str(f))
    rows = []
    for role, dirs in (("new", run_dirs), ("baseline", baseline_dirs)):
        for d in dirs:
            r = load_run(d)
            rec = classify_run(r, p, ep)
            rec["role"] = role
            reg = pr_by_label.get(r.label)
            if reg is not None:
                bl = prereg_mod.run_blockers(reg[0], reg[1], r)
                rec["prereg_file"], rec["prereg_bound"], rec["prereg_blockers"] = reg[2], not bl, "; ".join(bl)
            rows.append(rec)
    by_n: Dict[int, List[Dict[str, Any]]] = {}
    for rec in rows:
        if rec["arm"] in ("burst", "noburst"):
            by_n.setdefault(int(rec["burst_n"]), []).append(rec)
    for rec in rows:
        rec["b2_counted"], rec["b2_problem"] = b2_eligibility(rec)
    by_n_b2 = {n: ([r for r in rs if r["b2_counted"]] if n in BASIN2_NS else rs) for n, rs in by_n.items()}
    dup = {n: [s for s in {r["seed"] for r in rs} if sum(r["seed"] == s for r in rs) > 1] for n, rs in by_n.items()}
    dup = {n: s for n, s in dup.items() if s}
    pairs = {}
    for s in sorted({r["seed"] for r in rows}):
        pairs[str(s)] = {str(n): next((r["basin_state"] for r in rs if r["seed"] == s), None) for n, rs in sorted(by_n.items())}
    return {"rows": rows, "by_n": by_n, "duplicate_seed_runs": dup, "by_seed": pairs,
            "decision": decision({n: by_n.get(n, []) for n in BASIN_NS}, co_primary_n=ep["trapped_co_primary_n"]),
            "b2_bracket": bracket_decision(by_n_b2), "curve": curve_table(by_n_b2),
            "b2_not_counted": [{"run_dir": r["run_dir"], "problem": r["b2_problem"]} for r in rows
                               if int(r.get("burst_n") or 0) in BASIN2_NS and not r["b2_counted"]],
            "endpoint_problems": endpoint_problems(ep, p),
            "window_mismatch_runs": [r["run_dir"] for r in rows if not r["window_matches_endpoints"]]}


_COLS = ("role", "burst_n", "seed", "label", "rate_mult", "arm", "basin_state", "stuck", "good", "good_by_recovered",
         "good_by_hit_slope", "state", "trapped", "recovered", "hit_eval", "backlog_slope", "slope_threshold", "hit_end",
         "outstanding_end", "rate_rel_dev", "eval_from", "t_end_s", "window_matches_endpoints", "prereg_bound",
         "prereg_blockers", "b2_counted", "b2_problem", "run_dir")


# ---------------------------------------------------------------- CLI
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.basin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill", help="write the B1 / B2 registration of burst size n (refuses to overwrite)")
    f.add_argument("--n", type=int, required=True, choices=sorted(_HYP))
    f.add_argument("--out", required=True)
    c = sub.add_parser("classify", help="per-run STUCK / GOOD, the B1 decision and the B2 bracket")
    c.add_argument("--endpoints", required=True, help="the frozen yaml (configs/r11_basin_predict.yaml)")
    c.add_argument("--run-dirs", nargs="+", required=True, help="the B1 (n=100, 25) and / or B2 (n=40, 50, 60) runs")
    c.add_argument("--baseline-dirs", nargs="*", default=None,
                   help=f"the n=0 / n=200 runs to join (default: the 1.65 x seeds 0-2 runs under {BASELINE_RUN_ROOT})")
    c.add_argument("--prereg", nargs="*", default=[], help="registrations to check the binding of each run against (by label)")
    c.add_argument("--params", default=PARAMS)
    c.add_argument("--set", action="append", default=[])
    c.add_argument("--out-root", default="results")
    args = ap.parse_args(argv)
    if args.cmd == "fill":
        out = Path(args.out)
        if out.exists():
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        pr = write_registration(args.n, out)
        print(f"wrote {out} status={pr['status']} label={pr['inputs']['engine_cell_label']} burst_n={pr['protocol']['burst_n']}")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0
    from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta
    t0 = datetime.now()
    git = git_info(REPO)
    p = load_params(args.params, [f"trap_v2.eval_from_s={REGISTERED_EVAL_FROM_S}", *args.set])
    ep = load_endpoints(args.endpoints)
    base = args.baseline_dirs if args.baseline_dirs is not None else find_baselines(REPO / BASELINE_RUN_ROOT)
    res = classify(args.run_dirs, base, ep, p, args.prereg)
    d = new_result_dir(args.out_root, "agentload_analysis_basin")
    df = pd.DataFrame(res["rows"])
    df[[k for k in _COLS if k in df.columns]].sort_values(["burst_n", "seed", "role"]).to_csv(d / "basin_runs.csv", index=False)
    verdict = {k: res[k] for k in ("by_seed", "decision", "b2_bracket", "curve", "b2_not_counted", "duplicate_seed_runs",
                                   "endpoint_problems",
                                   "window_mismatch_runs")}
    verdict["endpoints"] = ep
    (d / "basin_verdict.json").write_text(json.dumps(verdict, indent=2, default=json_default))
    (d / "endpoints.yaml").write_text(Path(args.endpoints).read_text())
    write_meta(d, build_meta(experiment="agentload_analysis_basin", argv=[sys.executable, "-m", "analysis.basin", *(argv or sys.argv[1:])],
                             seeds=sorted({int(r["seed"]) for r in res["rows"]}), hardware=default_hardware(), git=git,
                             t_start=t0, t_end=datetime.now(), status="finished",
                             extra={"run_dirs": [str(x) for x in args.run_dirs], "baseline_dirs": [str(x) for x in base],
                                    "prereg": list(args.prereg)}))
    print(json.dumps({"decision": verdict["decision"], "b2_bracket": verdict["b2_bracket"]}, indent=2, default=json_default))
    for msg in res["endpoint_problems"]:
        print(f"ENDPOINT PROBLEM: {msg}", file=sys.stderr)
    print(f"basin outputs: {d}")
    return 1 if res["endpoint_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
