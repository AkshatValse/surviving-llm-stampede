"""Pre-registration of the E2 kill-test predictions (configs/agentload_prereg_template.yaml).

Workflow: Stage C writes ``mu_curve.json``, E0a writes ``calibration.json``. ``fill`` turns the template into a filled
file by FORMULA (no hand-typed numbers); the lead writes the lambda points and the rule that chose them; the filled file
is committed BEFORE the first E2 run is submitted; ``summarize burst2 --prereg FILE`` records the file's sha256 and git
state in kill_verdict_v2.json, refuses a registered rule that differs from the applied one, and checks that each tested
lambda lies inside the registered window.

Predictions (sessions/s; lambda = rate_mult * lambda_ref):
  recovery threshold      mu(n_inf)          (n_inf = 300): for lambda < mu(300) the closed curve never drops below the
                                              arrival rate, so a burst drains;
  metastable window       (mu(300), max_n mu(n)): the good state exists (lambda < max mu) but the all-miss tail cannot carry
                                              lambda (lambda > mu(300)), so a large enough burst traps;
  trapped completion rate lambda_miss        (the throughput-based criterion (a) compares against it; if mu(300) is more than
                                              rate_tolerance away from lambda_miss the criterion can reject a real trap:
                                              reported as ``mu_300_vs_lambda_miss_rel_dev``).
CLI:  python -m analysis.prereg fill --template T --mu-curve M --calibration C --out NEWFILE [--lambda-mults ...] [--rule TEXT]
      python -m analysis.prereg validate FILE
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from .params import AnalysisParams, load_params

# trap_v2 parameters that the registered pass_rule must equal (name in the prereg file -> key in trap_v2)
RULE_KEYS = {"rate_tolerance": "rate_tolerance", "slope_frac": "slope_frac", "recovered_hit_above": "recovered_hit_above",
             "recovered_backlog_below": "recovered_backlog_below", "pass_fraction_min": "pass_fraction_min",
             "min_seeds": "min_seeds", "rate_estimator": "rate_estimator", "eval_from_s": "eval_from_s",
             "end_window_s": "end_window_s", "min_eval_s": "min_eval_s", "slope_dt_s": "slope_dt_s"}


def load_prereg(path: str | Path) -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text()) or {}


def window_of(pr: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Registered window in sessions/s and in multiples of lambda_ref (None where unfilled)."""
    w = ((pr.get("predicted_boundaries") or {}).get("metastable_window") or {})
    return {"lo": w.get("lo"), "hi": w.get("hi"), "lo_mult": w.get("lo_mult"), "hi_mult": w.get("hi_mult"),
            "lambda_ref": (pr.get("measured") or {}).get("lambda_ref")}


def lambda_in_window(pr: Dict[str, Any], lam: float) -> Optional[bool]:
    """Is the arrival rate ``lam`` (sessions/s) strictly inside the registered window? None if the window is unfilled."""
    w = window_of(pr)
    if w["lo"] is None or w["hi"] is None:
        return None
    return bool(w["lo"] < lam < w["hi"])


def file_provenance(path: str | Path) -> Dict[str, Any]:
    """sha256 of the file and its git state: last commit touching it, whether it is committed and unmodified."""
    p = Path(path).resolve()
    out: Dict[str, Any] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=p.parent, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return ""

    out["git_last_commit"] = git("log", "-1", "--format=%H", "--", p.name) or None
    out["git_last_commit_time"] = git("log", "-1", "--format=%cI", "--", p.name) or None
    out["git_tracked"] = bool(git("ls-files", "--error-unmatch", p.name))
    out["git_modified_since_commit"] = bool(git("status", "--porcelain", "--", p.name))
    out["committed_clean"] = bool(out["git_last_commit"] and out["git_tracked"] and not out["git_modified_since_commit"])
    return out


def _unfilled(d: Any, prefix: str = "") -> List[str]:
    """Paths of null leaves under the sections that must be filled."""
    out: List[str] = []
    if isinstance(d, dict):
        for k, v in d.items():
            out += _unfilled(v, f"{prefix}.{k}" if prefix else str(k))
    elif d is None:
        out.append(prefix)
    return out


def validate(pr: Dict[str, Any], p: Optional[AnalysisParams] = None) -> List[Dict[str, str]]:
    """Problems with a pre-registration file: {severity, code, message}. 'error' means it must not be used as filled."""
    probs: List[Dict[str, str]] = []

    def add(sev: str, code: str, msg: str) -> None:
        probs.append({"severity": sev, "code": code, "message": msg})

    if pr.get("status") != "FILLED":
        add("error", "not_filled", f"status is {pr.get('status')!r}, not FILLED")
    for sec in ("measured", "predicted_boundaries"):
        miss = _unfilled(pr.get(sec) or {})
        if miss:
            add("error", "unfilled", f"{sec}: null fields {miss}")
    ls = pr.get("lambda_selection") or {}
    if not ls.get("rule"):
        add("error", "no_lambda_rule", "lambda_selection.rule is empty: say how the lambda points were chosen")
    mults = ls.get("lambda_mults") or []
    if not mults:
        add("error", "no_lambda_mults", "lambda_selection.lambda_mults is empty")
    w = window_of(pr)
    if None not in (w["lo_mult"], w["hi_mult"]):
        margin = ls.get("boundary_margin_rel") or 0.0
        for m in mults:
            lo, hi = w["lo_mult"] * (1 + margin), w["hi_mult"] * (1 - margin)
            if not lo < m < hi:
                add("error", "lambda_outside_window", f"lambda mult {m} is not inside ({lo:.4g}, {hi:.4g}) "
                    f"(window ({w['lo_mult']:.4g}, {w['hi_mult']:.4g}) x lambda_ref, margin {margin})")
    rd = ((pr.get("predicted_boundaries") or {}).get("consistency") or {}).get("mu_300_vs_lambda_miss_rel_dev")
    tol = (pr.get("pass_rule") or {}).get("rate_tolerance")
    if rd is not None and tol is not None and abs(rd) > tol:
        add("warn", "mu300_far_from_lambda_miss", f"|mu(300)/lambda_miss - 1| = {abs(rd):.3f} > rate_tolerance {tol}: "
            "criterion (a) compares the trapped completion rate with lambda_miss; if the trap runs at ~mu(300) it can be rejected")
    if p is not None:
        tp = p.trap_v2
        rule = pr.get("pass_rule") or {}
        for k, tk in RULE_KEYS.items():
            if k not in rule:
                add("error", "rule_key_missing", f"pass_rule.{k} missing")
            elif rule[k] != tp[tk] and not (isinstance(rule[k], float) and abs(rule[k] - float(tp[tk])) < 1e-12):
                add("error", "rule_mismatch", f"pass_rule.{k}={rule[k]!r} but the analysis applies trap_v2.{tk}={tp[tk]!r}")
        cp = p.closed
        inputs = pr.get("inputs") or {}
        if inputs.get("mu_estimator") not in (None, cp["mu_estimator"]):
            add("error", "rule_mismatch", f"inputs.mu_estimator={inputs.get('mu_estimator')!r} but closed.mu_estimator={cp['mu_estimator']!r}")
    return probs


def fill(template: Dict[str, Any], mu_curve: Dict[str, Any], calibration: Dict[str, Any], *,
         lambda_mults: Optional[Sequence[float]] = None, rule: Optional[str] = None,
         mu_curve_path: str = "", calibration_path: str = "", p: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    """Fill the measured values and the formula-derived boundaries of ``template`` (a deep copy is returned). The
    lambda points and their rule come from the arguments (or stay as in the template). ``status`` becomes FILLED only
    if :func:`validate` finds no error."""
    pr = copy.deepcopy(template)
    inp = pr["inputs"]
    cell = (mu_curve.get("cells") or {}).get(inp["engine_cell_label"])
    if cell is None:
        raise ValueError(f"mu_curve.json has no cell {inp['engine_cell_label']!r} (cells: {sorted(mu_curve.get('cells') or {})})")
    key = inp["lambda_ref_key"]
    if key not in calibration:
        raise ValueError(f"calibration.json has no key {key!r}")
    if mu_curve.get("estimator") != inp["mu_estimator"]:
        raise ValueError(f"mu_curve.json estimator {mu_curve.get('estimator')!r} != inputs.mu_estimator {inp['mu_estimator']!r}")
    inp["mu_curve_json"], inp["calibration_json"] = mu_curve_path or inp.get("mu_curve_json"), calibration_path or inp.get("calibration_json")
    lam_ref = float(calibration[key])
    mu_300 = cell.get("mu_n_inf")
    mu_max = cell.get("mu_max")
    pr["measured"] = {
        "mu_by_n": {int(k): v for k, v in cell["mu_by_n"].items()}, "mu_300": mu_300, "mu_max": mu_max,
        "n_cap": cell["argmax_n"], "n_cap_ambiguous": cell["argmax_ambiguous"], "complete_grid": cell["complete_grid"],
        "lambda_miss": calibration.get("lambda_miss"), "lambda_miss_turns_based": calibration.get("lambda_miss_turns_based"),
        "lambda_ref": lam_ref}
    pb = pr["predicted_boundaries"]
    pb["recovery_threshold"].update(sessions_per_s=mu_300, mult_of_lambda_ref=None if mu_300 is None else mu_300 / lam_ref)
    pb["metastable_window"].update(lo=mu_300, hi=mu_max, lo_mult=None if mu_300 is None else mu_300 / lam_ref,
                                   hi_mult=None if mu_max is None else mu_max / lam_ref)
    pb["trapped_completion_rate"]["value"] = lam_ref
    pb["consistency"] = {"mu_300_vs_lambda_miss_rel_dev": None if mu_300 is None else mu_300 / lam_ref - 1.0,
                         "window_nonempty": None if None in (mu_300, mu_max) else bool(mu_max > mu_300)}
    ls = pr["lambda_selection"]
    if lambda_mults is not None:
        ls["lambda_mults"] = [float(m) for m in lambda_mults]
    if rule is not None:
        ls["rule"] = rule
    probs = validate({**pr, "status": "FILLED"}, p)
    pr["status"] = "FILLED" if not any(x["severity"] == "error" for x in probs) else "INCOMPLETE"
    pr["fill_problems"] = probs
    return pr


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.prereg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill", help="fill the template from mu_curve.json and calibration.json; writes a NEW file")
    f.add_argument("--template", required=True)
    f.add_argument("--mu-curve", required=True)
    f.add_argument("--calibration", required=True)
    f.add_argument("--out", required=True, help="new file (refuses to overwrite)")
    f.add_argument("--lambda-mults", nargs="*", type=float, default=None)
    f.add_argument("--rule", default=None, help="text: how the lambda points were chosen inside the window")
    f.add_argument("--params", default="configs/agentload_analysis.yaml")
    v = sub.add_parser("validate", help="exit 1 if the file has error-severity problems")
    v.add_argument("file")
    v.add_argument("--params", default="configs/agentload_analysis.yaml")
    args = ap.parse_args(argv)
    p = load_params(args.params)
    if args.cmd == "fill":
        out = Path(args.out)
        if out.exists():
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        pr = fill(load_prereg(args.template), json.loads(Path(args.mu_curve).read_text()),
                  json.loads(Path(args.calibration).read_text()), lambda_mults=args.lambda_mults, rule=args.rule,
                  mu_curve_path=args.mu_curve, calibration_path=args.calibration, p=p)
        out.write_text(yaml.safe_dump(pr, sort_keys=False))
        print(f"wrote {out} status={pr['status']}")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0 if pr["status"] == "FILLED" else 1
    probs = validate(load_prereg(args.file), p)
    for x in probs:
        print(f"[{x['severity']}] {x['code']}: {x['message']}")
    return 1 if any(x["severity"] == "error" for x in probs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
