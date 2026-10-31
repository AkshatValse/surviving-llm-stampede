"""Pre-registration of the E2 kill-test predictions (configs/agentload_prereg_template.yaml).

Workflow: Stage C writes ``mu_curve.json``, E0a writes ``calibration.json``, E0b writes ``lambda_cap_bracket.json`` (E0b is
REQUIRED: it bounds the window from above). ``fill`` turns the template into a filled file by FORMULA (no hand-typed
numbers); the lead writes the lambda points and the rule that chose them; the filled file is committed BEFORE the first E2
job is submitted. The E2 job script validates it again (``check-job``), refuses to start unless it is committed and clean and
the job's label / lambdas / cap / hardware / reference rates are the registered ones, and writes its sha256 into every run's
meta.json. ``summarize burst2 --prereg FILE`` then calls a verdict DECISIVE only if the file is valid, committed, clean and
first committed before the earliest run started, and the cell is the registered one (label == inputs.engine_cell_label,
rate_mult in lambda_selection.lambda_mults, lambda inside the window) and every run of it is bound to this file.

Predictions (sessions/s unless noted; lambda = rate_mult * lambda_ref, lambda_ref = E0a's all-miss session capacity):
  recovery threshold      lambda_ref          (FCFS mu(infinity) = lambda_miss; the simulator's R4 gives 0.989 x). The Stage-C
                                              value mu(300) is only a CHECK: all n sessions start together at t=0, so in the
                                              measured window [900 s, 2700 s) mu(300) is transient-inflated (simulator:
                                              +65% at n=300, +17-20% at n=100) and n=22-30 are 9-25% low (review finding 2).
  metastable window       (lambda_ref, min(mu_max, lambda_cap_E0b))
                                              the good state exists below mu_max AND below the from-empty stability edge of
                                              E0b (above it the NOBURST arm itself escapes spontaneously: the simulator has
                                              1/5 and 2/5 no-burst runs trapped at 2x and 2.5x with its from-empty edge at
                                              2.41x and its curve peak at 4.07x; review finding 3);
  trapped prefill rate    E0a's all-miss uncached prefill tokens/s (criterion (a) compares against it, +-rate_tolerance);
  CAPPED drain            burst_n / (mu(n_cap) - lambda) must fit in the post-burst run time minus the end window, times
                          ``drain_fit_frac``; lambdas above the resulting limit are refused (review finding 6).
CLI:  python -m analysis.prereg fill --template T --mu-curve M --calibration C --e0b-bracket B --out NEWFILE
                                     [--lambda-mults ...] [--rule TEXT] [--engine-cell-label L] [--e2-config F]
      python -m analysis.prereg derive-exploratory --from FILLED --engine-cell-label L [--calibration C] --out NEWFILE
      python -m analysis.prereg validate FILE
      python -m analysis.prereg check-job FILE --label L --mults "..." --arms "..." [--n-cap N] [--calib F] [--hardware HW] ...

RESCUE registrations (plan R1 / R4): when the E2 config given to ``fill`` has ``gate.mode: rescue``, fill copies that gate block
verbatim into ``protocol.gate`` and the config file's sha256 into ``protocol.e2_config_sha256`` (other configs: nothing is
added, so the default fill output is unchanged). Such a registration authorises ONLY the rescue arm, and the rescue arm is
authorised ONLY by such a registration (check-job and run_blockers). check-job then refuses a job whose --e2-config gate block
differs in any key (t_on_s, n_cap, hold, min_on, ...) or whose e2-config bytes differ from the registered sha256, and a job
that runs any other arm with a rescue config. The CAPPED-drain limit is informational for a rescue registration (no CAPPED
arm runs under it).

NON-DEFAULT E2 CONFIGS (r14: TOOLSLOW, SHED): when ``fill`` is given an E2 config other than ``configs/agentload_e2_burst.yaml``
together with its sha256 (the CLI always hashes it), it records ``protocol.e2_config_sha256`` (the default fill output is
unchanged: the default config records nothing, and callers that pass no sha256, such as ``analysis.basin fill``, record
nothing). Whenever a registration records ``protocol.e2_config_sha256``, check-job refuses a job whose --e2-config bytes differ
(or that passes none), and run_blockers refuses a run whose config.yaml (the byte copy of the run config the client writes;
CRLF read as LF) hashes differently. ``fill(..., arms=[...])`` records ``protocol.arms``: the only arms the registration
authorises (check-job: ARMS; run_blockers: the run's arm); absent = unrestricted, as before. A ramp E2 config
(``arrivals.kind: ramp``) needs ``ramp_is_mult: true`` and every job MULTS entry equal to the ramp's largest knot (the rate
outside the stop), since the job glue's ``arrivals.rate_mult`` is then only recorded. Older registrations with a non-default
E2 config and no recorded sha256 (B1: b100, b25, made before this binding) keep their old checks (burst / duration fields).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from .params import AnalysisParams, load_params

# pass_rule key in the prereg file -> dotted path into the analysis params (configs/agentload_analysis.yaml). Everything that
# changes what a verdict means must be here (review finding 8): the trap_v2 rule, and the windows.* settings that define
# "hit". ``--fcfs-substr`` is registered as inputs.fcfs_substr. Only plotting resolution is exempt.
RULE_KEYS: Dict[str, str] = {
    "rate_tolerance": "trap_v2.rate_tolerance", "slope_frac": "trap_v2.slope_frac",
    "recovered_hit_above": "trap_v2.recovered_hit_above", "recovered_backlog_below": "trap_v2.recovered_backlog_below",
    "recovered_backlog_metric": "trap_v2.recovered_backlog_metric", "pass_fraction_min": "trap_v2.pass_fraction_min",
    "min_seeds": "trap_v2.min_seeds", "rate_estimator": "trap_v2.rate_estimator", "eval_from_s": "trap_v2.eval_from_s",
    "end_window_s": "trap_v2.end_window_s", "min_eval_s": "trap_v2.min_eval_s", "slope_dt_s": "trap_v2.slope_dt_s",
    "hit_metric": "windows.hit_metric", "cached_frac_threshold": "windows.cached_frac_threshold",
    "attribute_by": "windows.attribute_by"}
UNREGISTERED_TRAP_V2_KEYS = ("trace_bin_s",)            # plots only; changes no verdict
# leaves of the filled sections that may legitimately be null
_OPTIONAL_NULL = ("measured.lambda_cap_e0b.first_unstable_mult_above",)
REL_TOL = 1e-9
RESCUE_MODE = "rescue"
DEFAULT_E2_CONFIG = "configs/agentload_e2_burst.yaml"
KNOWN_ARMS = ("burst", "noburst", "capped", "rescue")


def registered_arms(pr: Dict[str, Any]) -> Optional[List[str]]:
    """``protocol.arms`` (the only arms this registration authorises), or None (unrestricted)."""
    a = (pr.get("protocol") or {}).get("arms")
    return [str(x) for x in a] if isinstance(a, list) else None


def _sha_ok(sha: Any) -> bool:
    return isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)


def config_text_sha256(path: str | Path) -> str:
    """sha256 of a config file with CRLF read as LF (the client writes config.yaml with the platform's newline)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def ramp_problems(e2_cfg: Dict[str, Any], mults: Sequence[float]) -> List[str]:
    """A ramp E2 config: ramp_is_mult true and each MULTS entry equal to the ramp's largest knot rate."""
    arr = e2_cfg.get("arrivals") or {}
    if arr.get("kind") != "ramp":
        return []
    out = []
    knots = arr.get("ramp") or []
    if not arr.get("ramp_is_mult"):
        out.append("E2 config arrivals.kind ramp needs ramp_is_mult true (rates as multiples of the registered lambda_ref)")
    try:
        top = max(float(k[1]) for k in knots)
    except (TypeError, ValueError, IndexError):
        return out + [f"E2 config arrivals.ramp knots unreadable: {knots!r}"]
    for m in mults:
        if not _close(float(m), top):
            out.append(f"MULTS entry {m} != the ramp's rate outside the stop ({top}): with kind ramp the job's rate_mult is "
                       "only recorded, so it must name the ramp's rate")
    return out


def protocol_gate(pr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The registered gate block (``protocol.gate``), or None: only rescue registrations carry one."""
    g = (pr.get("protocol") or {}).get("gate")
    return g if isinstance(g, dict) else None


def is_rescue_registration(pr: Dict[str, Any]) -> bool:
    g = protocol_gate(pr)
    return g is not None and g.get("mode") == RESCUE_MODE


def _same(a: Any, b: Any) -> bool:
    def num(x: Any) -> bool:
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    return _close(a, b) if num(a) and num(b) else a == b


def gate_block_diff(registered: Dict[str, Any], got: Dict[str, Any], skip: Sequence[str] = ()) -> List[str]:
    """Keys whose value differs between the registered gate block and ``got`` ("<absent>" for a missing key)."""
    return [f"gate.{k}: {got.get(k, '<absent>')!r} != registered {registered.get(k, '<absent>')!r}"
            for k in sorted((set(registered) | set(got)) - set(skip))
            if not _same(registered.get(k, "<absent>"), got.get(k, "<absent>"))]


def load_prereg(path: str | Path) -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text()) or {}


def _param(p: AnalysisParams, dotted: str) -> Any:
    node: Any = p.raw
    for part in dotted.split("."):
        node = node[part]
    return node


def _close(a: Any, b: Any, rel: float = REL_TOL) -> bool:
    try:
        return abs(float(a) - float(b)) <= rel * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


def window_of(pr: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Registered window in sessions/s and in multiples of lambda_ref (None where unfilled)."""
    w = ((pr.get("predicted_boundaries") or {}).get("metastable_window") or {})
    # An exploratory engine may have its own reference rate; these boundaries still describe the parent's measurement.
    lam_ref = ((pr.get("exploratory") or {}).get("inherited_window_lambda_ref")
               if pr.get("status") == "EXPLORATORY" else (pr.get("measured") or {}).get("lambda_ref"))
    return {"lo": w.get("lo"), "hi": w.get("hi"), "lo_mult": w.get("lo_mult"), "hi_mult": w.get("hi_mult"),
            "lambda_ref": lam_ref}


def lambda_in_window(pr: Dict[str, Any], lam: float) -> Optional[bool]:
    """Is the arrival rate ``lam`` (sessions/s) strictly inside the registered window? None if the window is unfilled."""
    w = window_of(pr)
    if w["lo"] is None or w["hi"] is None:
        return None
    return bool(w["lo"] < lam < w["hi"])


def registered_mults(pr: Dict[str, Any]) -> List[float]:
    return [float(m) for m in ((pr.get("lambda_selection") or {}).get("lambda_mults") or [])]


def mult_is_registered(pr: Dict[str, Any], mult: Optional[float]) -> bool:
    return mult is not None and any(_close(mult, m) for m in registered_mults(pr))


def file_provenance(path: str | Path) -> Dict[str, Any]:
    """sha256 of the file and its git state: first and last commit touching it (hash, ISO time, unix time), whether it is
    committed and unmodified."""
    p = Path(path).resolve()
    out: Dict[str, Any] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=p.parent, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return ""

    log = [ln.split(" ") for ln in git("log", "--format=%H %ct %cI", "--", p.name).splitlines() if ln.strip()]
    last, first = (log[0], log[-1]) if log else (None, None)           # newest first
    out["git_last_commit"] = last[0] if last else None
    out["git_last_commit_unix"] = float(last[1]) if last else None
    out["git_last_commit_time"] = last[2] if last else None
    out["git_first_commit"] = first[0] if first else None
    out["git_first_commit_unix"] = float(first[1]) if first else None
    out["git_first_commit_time"] = first[2] if first else None
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
    elif d is None and prefix not in _OPTIONAL_NULL:
        out.append(prefix)
    return out


def validate(pr: Dict[str, Any], p: Optional[AnalysisParams] = None, fcfs_substr: Optional[str] = None, *,
             prereg_path: Optional[str | Path] = None) -> List[Dict[str, str]]:
    """Problems with a pre-registration file: {severity, code, message}. 'error' means it must not be used as filled."""
    if pr.get("status") == "EXPLORATORY" or "exploratory" in pr:
        # Reuse every existing rule check, but separately enforce derivation and the EXPLORATORY status.
        base = {k: v for k, v in pr.items() if k != "exploratory"}
        base["status"] = "FILLED"
        return (_validate_exploratory(pr, p, fcfs_substr, prereg_path)
                + validate(base, p, fcfs_substr))
    probs: List[Dict[str, str]] = []

    def add(sev: str, code: str, msg: str) -> None:
        probs.append({"severity": sev, "code": code, "message": msg})

    if pr.get("status") != "FILLED":
        add("error", "not_filled", f"status is {pr.get('status')!r}, not FILLED")
    for sec in ("measured", "predicted_boundaries", "protocol"):
        miss = [m for m in _unfilled({sec: pr.get(sec) or {}}, "")]
        if miss:
            add("error", "unfilled", f"{sec}: null fields {miss}")
    ls = pr.get("lambda_selection") or {}
    if not ls.get("rule"):
        add("error", "no_lambda_rule", "lambda_selection.rule is empty: say how the lambda points were chosen")
    mults = ls.get("lambda_mults") or []
    if not mults:
        add("error", "no_lambda_mults", "lambda_selection.lambda_mults is empty")
    margin = ls.get("boundary_margin_rel")
    if not isinstance(margin, (int, float)) or isinstance(margin, bool) or margin < 0:
        add("error", "no_margin", f"lambda_selection.boundary_margin_rel must be a number >= 0 (got {margin!r})")
        margin = 0.0
    w = window_of(pr)
    if None not in (w["lo_mult"], w["hi_mult"]):
        for m in mults:
            lo, hi = w["lo_mult"] * (1 + margin), w["hi_mult"] * (1 - margin)
            if not lo < m < hi:
                add("error", "lambda_outside_window", f"lambda mult {m} is not inside ({lo:.4g}, {hi:.4g}) "
                    f"(window ({w['lo_mult']:.4g}, {w['hi_mult']:.4g}) x lambda_ref, margin {margin})")
    drain = (pr.get("predicted_boundaries") or {}).get("capped_drain") or {}
    pg = protocol_gate(pr)
    if drain.get("max_lambda_mult") is not None:
        for m in mults:
            if m > drain["max_lambda_mult"]:
                add("warn" if pg is not None else "error", "capped_drain_does_not_fit",
                    f"lambda mult {m} > {drain['max_lambda_mult']:.4g}: the CAPPED arm's gate queue "
                    f"({drain.get('burst_n')} sessions at mu(n_cap)-lambda) would not drain inside the run, so kill condition 3 "
                    "(cap does not rescue) would fire for a reason unrelated to the mechanism"
                    + (" (rescue registration: no CAPPED arm runs under it, informational)" if pg is not None else ""))
    if pg is not None:
        if pg.get("mode") != RESCUE_MODE:
            add("error", "gate_block_not_rescue", f"protocol.gate.mode is {pg.get('mode')!r}: only a rescue gate block is registered")
        n_cap_reg = (pr.get("measured") or {}).get("n_cap")
        if pg.get("n_cap") != n_cap_reg:
            add("error", "gate_cap_mismatch", f"protocol.gate.n_cap {pg.get('n_cap')!r} != measured.n_cap {n_cap_reg!r} (the cap "
                "rule's value): the rescue cap must be the registered cap")
        for k in ("t_on_s", "pause_at_turns", "release_hold_s", "min_on_s"):
            if k not in pg:
                add("error", "gate_block_incomplete", f"protocol.gate.{k} missing")
        sha = (pr.get("protocol") or {}).get("e2_config_sha256")
        if not _sha_ok(sha):
            add("error", "e2_config_sha256_missing", f"protocol.e2_config_sha256 must be the e2 config's sha256 (got {sha!r})")
    proto_v = pr.get("protocol") or {}
    if pg is None and "e2_config_sha256" in proto_v and not _sha_ok(proto_v.get("e2_config_sha256")):
        add("error", "e2_config_sha256_invalid", f"protocol.e2_config_sha256 must be a sha256 hex digest (got "
            f"{proto_v.get('e2_config_sha256')!r})")
    ra = registered_arms(pr)
    if "arms" in proto_v and (ra is None or not ra or any(a not in KNOWN_ARMS for a in ra)):
        add("error", "protocol_arms_invalid", f"protocol.arms must be a non-empty list of {list(KNOWN_ARMS)}, got "
            f"{proto_v.get('arms')!r}")
    rd = ((pr.get("predicted_boundaries") or {}).get("consistency") or {}).get("mu_300_vs_lambda_miss_rel_dev")
    if rd is not None and abs(rd) > 0.25:
        add("warn", "mu300_far_from_lambda_miss", f"|mu(300)/lambda_miss - 1| = {abs(rd):.3f}: only a check (all n sessions "
            "start together, so mu(300) in the 1800 s window is transient-biased: simulator +65%); the registered recovery "
            "threshold is lambda_miss")
    if p is not None:
        rule = pr.get("pass_rule") or {}
        for k, path in RULE_KEYS.items():
            applied = _param(p, path)
            if k not in rule:
                add("error", "rule_key_missing", f"pass_rule.{k} missing")
            elif rule[k] != applied and not (isinstance(rule[k], float) and abs(rule[k] - float(applied)) < 1e-12):
                add("error", "rule_mismatch", f"pass_rule.{k}={rule[k]!r} but the analysis applies {path}={applied!r}")
        for k in p.trap_v2:
            if k not in {v.split(".", 1)[1] for v in RULE_KEYS.values() if v.startswith("trap_v2.")} \
                    and k not in UNREGISTERED_TRAP_V2_KEYS:
                add("error", "rule_key_unregistered", f"trap_v2.{k} exists in the analysis config but is neither registered "
                    "in analysis.prereg.RULE_KEYS nor exempt")
        cp = p.closed
        inputs = pr.get("inputs") or {}
        if inputs.get("mu_estimator") not in (None, cp["mu_estimator"]):
            add("error", "rule_mismatch", f"inputs.mu_estimator={inputs.get('mu_estimator')!r} but closed.mu_estimator={cp['mu_estimator']!r}")
        if fcfs_substr is not None and inputs.get("fcfs_substr") != fcfs_substr:
            add("error", "rule_mismatch", f"inputs.fcfs_substr={inputs.get('fcfs_substr')!r} but the analysis was called with "
                f"--fcfs-substr {fcfs_substr!r}")
    return probs


# ---------------------------------------------------------------- fill
def capped_drain(mu_n_cap: float, lam_ref: float, burst_n: float, duration_s: float, t_burst_s: float, end_window_s: float,
                 fit_frac: float, mults: Sequence[float]) -> Dict[str, Any]:
    """Predicted drain time of the CAPPED arm's gate queue: the burst (``burst_n`` sessions) queues behind ``n_cap`` active
    sessions, which the closed system serves at mu(n_cap) sessions/s while sessions keep arriving at lambda, so the queue
    drains at mu(n_cap) - lambda. It must fit in the post-burst run time minus the window that judges RECOVERED, times
    ``fit_frac`` (a margin for the noise of the one-run mu(n_cap))."""
    avail = duration_s - t_burst_s - end_window_s
    budget = fit_frac * avail
    max_lam = mu_n_cap - burst_n / budget if budget > 0 else float("-inf")
    by_mult: Dict[str, Any] = {}
    for m in mults:
        lam = m * lam_ref
        by_mult[f"{m:g}"] = (burst_n / (mu_n_cap - lam)) if mu_n_cap > lam else float("inf")      # inf: never drains
    return {"burst_n": burst_n, "mu_n_cap": mu_n_cap, "post_burst_available_s": avail, "drain_fit_frac": fit_frac,
            "max_drain_s": budget, "max_lambda": max_lam, "max_lambda_mult": max_lam / lam_ref,
            "predicted_drain_s_by_mult": by_mult,
            "rule": "burst_n / (mu_n_cap - lambda) <= drain_fit_frac * (duration_s - t_burst_s - end_window_s)"}


def fill(template: Dict[str, Any], mu_curve: Dict[str, Any], calibration: Dict[str, Any], *,
         e0b: Optional[Dict[str, Any]] = None, e2_cfg: Optional[Dict[str, Any]] = None,
         lambda_mults: Optional[Sequence[float]] = None, rule: Optional[str] = None,
         engine_cell_label: Optional[str] = None,
         mu_curve_path: str = "", calibration_path: str = "", e0b_path: str = "", e2_cfg_path: str = "",
         n_cap_rule: str = "argmax", p: Optional[AnalysisParams] = None,
         e2_cfg_sha256: Optional[str] = None, arms: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Fill the measured values and the formula-derived boundaries of ``template`` (a deep copy is returned). The
    lambda points and their rule come from the arguments (or stay as in the template). ``status`` becomes FILLED only
    if :func:`validate` finds no error. ``e0b`` (the ``lambda_cap_bracket.json`` of E0b) and ``e2_cfg`` (the raw E2 config:
    run length, burst) are required: a missing E0b leaves the window's upper edge unfilled."""
    pr = copy.deepcopy(template)
    inp = pr["inputs"]
    if engine_cell_label:
        inp["engine_cell_label"] = engine_cell_label
    label = inp["engine_cell_label"]
    cell = (mu_curve.get("cells") or {}).get(label)
    if cell is None:
        raise ValueError(f"mu_curve.json has no cell {label!r} (cells: {sorted(mu_curve.get('cells') or {})})")
    key, tok_key = inp["lambda_ref_key"], inp["uncached_tokens_ref_key"]
    for k in (key, tok_key):
        if k not in calibration:
            raise ValueError(f"calibration.json has no key {k!r} (E0a: `analysis.summarize miss` writes it)")
    if mu_curve.get("estimator") != inp["mu_estimator"]:
        raise ValueError(f"mu_curve.json estimator {mu_curve.get('estimator')!r} != inputs.mu_estimator {inp['mu_estimator']!r}")
    inp["mu_curve_json"], inp["calibration_json"] = mu_curve_path or inp.get("mu_curve_json"), calibration_path or inp.get("calibration_json")
    inp["e0b_bracket_json"], inp["e2_config"] = e0b_path or inp.get("e0b_bracket_json"), e2_cfg_path or inp.get("e2_config")
    lam_ref, tok_ref = float(calibration[key]), float(calibration[tok_key])
    mu_300, mu_max, n_cap = cell.get("mu_n_inf"), cell.get("mu_max"), cell["argmax_n"]
    mu_by_n = {int(k): v for k, v in cell["mu_by_n"].items()}
    n_cap_argmax = n_cap
    n_cap_rule_text = "argmax_n mu(n)"
    if n_cap_rule == "smallest_within_margin":
        # the CAPPED arm's cap: the SMALLEST n whose mu(n) is within the argmax noise margin of mu_max (one run per n: the
        # argmax among near-ties is noise, and a smaller cap keeps the closed system further from the cliff)
        if p is None:
            raise ValueError("n_cap_rule='smallest_within_margin' needs the analysis params (closed.argmax_margin_warn)")
        margin = float(p.raw["closed"]["argmax_margin_warn"])
        ok = sorted(n for n, v in mu_by_n.items() if v is not None and mu_max is not None and float(v) >= (1.0 - margin) * float(mu_max))
        n_cap = ok[0] if ok else n_cap
        n_cap_rule_text = f"smallest n with mu(n) >= (1 - {margin:g}) * mu_max (closed.argmax_margin_warn)"
    elif n_cap_rule != "argmax":
        raise ValueError(f"unknown n_cap_rule {n_cap_rule!r} (argmax | smallest_within_margin)")
    mu_n_cap = mu_by_n.get(int(n_cap)) if n_cap is not None else None
    b = None
    if e0b is not None:
        b = (e0b.get("by_label") or {}).get(label)
        if b is None:
            raise ValueError(f"E0b bracket has no entry for label {label!r} (labels: {sorted(e0b.get('by_label') or {})}): "
                             "E0b must be run under the registered cell (POLICY=fcfs REFRESH=1 for sglang-fcfs-r1)")
    hw_problems: List[str] = []
    hw_vals = set()
    for src, v in (("calibration", calibration.get("hardware")), ("mu_curve", cell.get("hardware")),
                   ("e0b", None if b is None else b.get("hardware"))):
        if src == "e0b" and b is None:
            continue                                             # reported once, as e0b_missing
        vs = [str(x) for x in (v if isinstance(v, list) else [v])] if v not in (None, []) else []
        if len(vs) != 1:
            hw_problems.append(f"{src}: expected exactly one hardware string, found {vs}")
        hw_vals.update(vs)
    hardware = next(iter(hw_vals)) if len(hw_vals) == 1 and not hw_problems else None
    if len(hw_vals) > 1:
        hw_problems.append(f"calibration, Stage C and E0b ran on different hardware: {sorted(hw_vals)}")
    pr["measured"] = {
        "mu_by_n": mu_by_n, "mu_300": mu_300, "mu_max": mu_max, "n_cap": n_cap, "mu_n_cap": mu_n_cap,
        "n_cap_rule": n_cap_rule_text, "n_cap_argmax": n_cap_argmax,
        "n_cap_ambiguous": cell["argmax_ambiguous"], "complete_grid": cell["complete_grid"],
        "lambda_miss": calibration.get("lambda_miss"), "lambda_miss_turns_based": calibration.get("lambda_miss_turns_based"),
        "lambda_ref": lam_ref, "all_miss_uncached_tokens_per_s": tok_ref,
        "lambda_cap_e0b": {"largest_all_stable_mult": None if b is None else b.get("largest_all_stable_mult"),
                           "first_unstable_mult_above": None if b is None else b.get("first_unstable_mult_above"),
                           "monotone": None if b is None else b.get("monotone")},
        "hardware": hardware}
    cp = e2_cfg or {}
    arr, run_c = cp.get("arrivals") or {}, cp.get("run") or {}
    burst = arr.get("burst") or {}
    pr["protocol"] = {"duration_s": run_c.get("duration_s"),
                      "t_burst_s": arr.get("analysis_t_burst_s", burst.get("t_s")),
                      "burst_n": burst.get("n"), "burst_width_s": burst.get("width_s")}
    if isinstance(cp.get("gate"), dict) and cp["gate"].get("mode") == RESCUE_MODE:
        # a rescue registration: the gate block is registered verbatim, and the config file by its sha256 (plan R1)
        pr["protocol"]["gate"] = copy.deepcopy(cp["gate"])
        pr["protocol"]["e2_config_sha256"] = e2_cfg_sha256
    elif e2_cfg_sha256 is not None and inp.get("e2_config") and inp["e2_config"] != DEFAULT_E2_CONFIG:
        # a non-default E2 config (r14 TOOLSLOW / SHED): registered by its sha256; the default config records nothing
        pr["protocol"]["e2_config_sha256"] = e2_cfg_sha256
    if arms is not None:
        pr["protocol"]["arms"] = [str(a) for a in arms]
    pb = pr["predicted_boundaries"]
    pb["recovery_threshold"].update(sessions_per_s=lam_ref, mult_of_lambda_ref=1.0)
    lcap = None if b is None or b.get("largest_all_stable_mult") is None else float(b["largest_all_stable_mult"]) * lam_ref
    if lcap is None or mu_max is None:
        hi, hi_src = None, None            # no E0b stable rate (or no curve): the upper edge is unknown, NOT mu_max alone
    else:
        hi, hi_src = (mu_max, "mu_max") if mu_max <= lcap else (lcap, "lambda_cap_e0b")
    pb["metastable_window"].update(lo=lam_ref, lo_mult=1.0, hi=hi, hi_mult=None if hi is None else hi / lam_ref, hi_source=hi_src)
    pb["trapped_completion_rate"]["value"] = lam_ref
    pb["trapped_uncached_token_rate"]["value"] = tok_ref
    pb["consistency"] = {"mu_300_vs_lambda_miss_rel_dev": None if mu_300 is None else mu_300 / lam_ref - 1.0,
                         "window_nonempty": None if hi is None else bool(hi > lam_ref)}
    ls = pr["lambda_selection"]
    if lambda_mults is not None:
        ls["lambda_mults"] = [float(m) for m in lambda_mults]
    if rule is not None:
        ls["rule"] = rule
    fit = float(ls.get("drain_fit_frac") or 0.8)
    ls["drain_fit_frac"] = fit
    ewin = float((p.trap_v2["end_window_s"]) if p is not None else (pr.get("pass_rule") or {}).get("end_window_s", 300.0))
    if None in (mu_n_cap, pr["protocol"]["duration_s"], pr["protocol"]["t_burst_s"], pr["protocol"]["burst_n"]):
        pb["capped_drain"].update(burst_n=pr["protocol"]["burst_n"], mu_n_cap=mu_n_cap, max_lambda=None, max_lambda_mult=None)
    else:
        pb["capped_drain"] = capped_drain(float(mu_n_cap), lam_ref, float(pr["protocol"]["burst_n"]), float(pr["protocol"]["duration_s"]),
                                          float(pr["protocol"]["t_burst_s"]), ewin, fit, ls.get("lambda_mults") or [])
    pr["checks"] = {"mu_300_is_a_check_only": {
        "value": mu_300, "rel_dev_vs_lambda_miss": pb["consistency"]["mu_300_vs_lambda_miss_rel_dev"],
        "note": "all n sessions start at t=0; mu(300) over the measured window is transient-biased, so it does not set the window"}}
    probs = validate({**pr, "status": "FILLED"}, p)
    for msg in hw_problems:
        probs.append({"severity": "error", "code": "hardware_mismatch", "message": msg})
    if mu_curve.get("primary_label") != label:
        probs.append({"severity": "error", "code": "primary_label_mismatch",
                      "message": f"mu_curve.json primary_label is {mu_curve.get('primary_label')!r} but the registered cell is "
                                 f"{label!r}: the CAPPED arm reads the file's top-level n_cap, which would be another pool's"})
    if cell.get("argmax_ambiguous"):
        probs.append({"severity": "warn", "code": "n_cap_ambiguous", "message": f"n_cap={n_cap}: the runner-up n={cell.get('runner_up_n')} is within "
                      f"{cell.get('argmax_margin_rel')} (one run per n; mu(n) near its peak is bistable and transient-biased in the "
                      "Stage-C window): the CAPPED arm's cap is a noisy choice"})
    if not cell.get("complete_grid"):
        probs.append({"severity": "warn", "code": "grid_incomplete", "message": f"Stage C n grid incomplete, missing {cell.get('missing_n')}"})
    if e0b is None:
        probs.append({"severity": "error", "code": "e0b_missing", "message": "E0b (lambda_cap_bracket.json) is required: it "
                      "bounds the window from above (the NOBURST arm must be able to stay good from empty)"})
    elif b is not None and b.get("largest_all_stable_mult") is None:
        probs.append({"severity": "error", "code": "e0b_no_stable_rate", "message": "E0b found no rate at which all seeds are "
                      "stable from empty: there is no good state to test"})
    elif b is not None and b.get("monotone") is False:
        probs.append({"severity": "warn", "code": "e0b_not_monotone", "message": "E0b stability is not monotone in the rate "
                      "(noise or a non-monotone region): the upper edge is the largest all-stable rate, which one more seed could move"})
    pr["status"] = "FILLED" if not any(x["severity"] == "error" for x in probs) else "INCOMPLETE"
    pr["fill_problems"] = probs
    return pr


# ---------------------------------------------------------------- exploratory derivation (never a new kill test)
def _repo_root(path: Path) -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path if path.is_dir() else path.parent,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(f"not inside a git repository: {path}")
    return Path(result.stdout.strip()).resolve()


def _reference_path(path: str, prereg_path: Optional[str | Path]) -> Path:
    """Stored relative references are repository-relative, independent of the caller's working directory."""
    ref = Path(path)
    if ref.is_absolute():
        return ref.resolve()
    return _repo_root(Path(prereg_path).resolve() if prereg_path else Path.cwd()) / ref


def _record_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _committed_sha256(path: Path) -> str:
    """Hash the HEAD blob itself: a clean status alone can conceal filters or assume-unchanged files."""
    root = _repo_root(path)
    relative = path.resolve().relative_to(root).as_posix()
    blob = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True, timeout=30)
    if blob.returncode:
        raise ValueError(f"no committed file at {relative}")
    return hashlib.sha256(blob.stdout).hexdigest()


def _exploratory_payload(parent: Dict[str, Any], label: str, metadata: Dict[str, Any],
                         calibration: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    parent_label = parent["inputs"]["engine_cell_label"]
    if not isinstance(label, str) or not label or label in (parent_label, "sglang-fcfs-r1"):
        raise ValueError("an exploratory registration must not use the registered label")
    arms = metadata.get("allowed_arms")
    if not isinstance(arms, list) or not arms or any(a not in ("burst", "noburst", "capped") for a in arms):
        raise ValueError("allowed_arms must be a nonempty list of burst, noburst or capped")
    if len(set(arms)) != len(arms):
        raise ValueError("allowed_arms must not contain duplicates")
    if label.split("-", 1)[0] != parent_label.split("-", 1)[0] and calibration is None:
        raise ValueError("a different engine requires its own --calibration")
    pr = copy.deepcopy(parent)
    pr["status"] = "EXPLORATORY"
    pr["inputs"]["engine_cell_label"] = label
    pr["exploratory"] = copy.deepcopy(metadata)
    pr["assumptions_note"] = ("EXPLORATORY only; never a decisive kill test. The parent's measurements, predictions, "
                              "window and lambda multiples are inherited, not measured for this engine cell. "
                              "Only the allowed arms may run; any calibration override supplies this cell's reference "
                              "rates, without rescaling or re-measuring the inherited window.")
    pr["frozen"]["rule"] = "Commit this EXPLORATORY file before submitting grid jobs; changes require a new file."
    if calibration is not None:
        labels = calibration.get("labels")
        if labels is not None and (not isinstance(labels, list) or not labels or any(
                not isinstance(lab, str) or lab.split("-", 1)[0] != label.split("-", 1)[0] for lab in labels)):
            raise ValueError("calibration labels must belong to this engine's own E0a")
        if calibration.get("hardware") != parent["measured"]["hardware"]:
            raise ValueError("calibration hardware must equal the registered hardware")
        for key, target in ((parent["inputs"]["lambda_ref_key"], "lambda_ref"),
                            (parent["inputs"]["uncached_tokens_ref_key"], "all_miss_uncached_tokens_per_s")):
            value = calibration.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"calibration reference {key} must be finite and positive")
            pr["measured"][target] = float(value)
        pr["inputs"]["calibration_json"] = metadata["calibration_override"]["path"]
    return pr


def derive_exploratory(parent_path: str | Path, *, engine_cell_label: str,
                       calibration_path: Optional[str | Path] = None, arms: Sequence[str] = ("burst",),
                       p: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    """Copy a valid committed FILLED registration with an immutable parent binding and exploratory scope."""
    path = Path(parent_path).resolve()
    parent, prov = load_prereg(path), file_provenance(path)
    if parent.get("status") != "FILLED" or "exploratory" in parent:
        raise ValueError("parent must be a FILLED registration, not an exploratory derivation")
    problems = validate(parent, p)
    if any(x["severity"] == "error" for x in problems):
        raise ValueError(f"parent is not valid: {problems}")
    if not prov["committed_clean"]:
        raise ValueError("parent must be committed and unmodified")
    if prov["sha256"] != _committed_sha256(path):
        raise ValueError("parent bytes must match the committed parent sha256")
    root = _repo_root(path)
    metadata = {"parent": {"path": _record_path(path, root), "sha256": prov["sha256"]},
                "allowed_arms": list(arms), "inherited_from_engine_cell_label": parent["inputs"]["engine_cell_label"],
                "inherited_window_lambda_ref": parent["measured"]["lambda_ref"],
                "boundary_note": "Window, lambda multiples, protocol and trap rule are inherited from "
                                 f"{parent['inputs']['engine_cell_label']}; the window and lambda multiples are not "
                                 "measured for this engine cell. Parent predictions are context only, never decisive."}
    calibration = None
    if calibration_path is not None:
        cal_path = Path(calibration_path).resolve()
        metadata["calibration_override"] = {"path": _record_path(cal_path, root),
                                            "sha256": hashlib.sha256(cal_path.read_bytes()).hexdigest()}
        calibration = json.loads(cal_path.read_text())
    return _exploratory_payload(parent, engine_cell_label, metadata, calibration)


def _validate_exploratory(pr: Dict[str, Any], p: Optional[AnalysisParams], fcfs_substr: Optional[str],
                          prereg_path: Optional[str | Path]) -> List[Dict[str, str]]:
    probs: List[Dict[str, str]] = []

    def error(code: str, message: str) -> None:
        probs.append({"severity": "error", "code": code, "message": message})

    if pr.get("status") != "EXPLORATORY":
        error("exploratory_status", "a derived registration must have status EXPLORATORY, never FILLED")
    try:
        meta = pr["exploratory"]
        if not isinstance(meta, dict):
            raise ValueError("exploratory metadata must be a mapping")
        parent_path = _reference_path(meta["parent"]["path"], prereg_path)
        parent = load_prereg(parent_path)
        prov = file_provenance(parent_path)
        if not prov["committed_clean"]:
            error("parent_uncommitted", "parent must be committed and unmodified")
        if prov["sha256"] != meta["parent"]["sha256"] or _committed_sha256(parent_path) != meta["parent"]["sha256"]:
            error("parent_sha_mismatch", "parent sha256 does not match the committed parent")
        if parent.get("status") != "FILLED" or "exploratory" in parent:
            raise ValueError("parent must be FILLED and must not itself be derived")
        probs.extend(x for x in validate(parent, p, fcfs_substr) if x["severity"] == "error")
        if meta.get("inherited_from_engine_cell_label") != parent["inputs"]["engine_cell_label"] or not meta.get("boundary_note"):
            error("inheritance_metadata", "the inherited cell label and boundary note must identify the parent")
        if meta.get("inherited_window_lambda_ref") != parent["measured"]["lambda_ref"]:
            error("inheritance_metadata", "the inherited window reference rate must equal the parent's lambda_ref")
        calibration = None
        if "calibration_override" in meta:
            cal_ref = meta["calibration_override"]
            cal_path = _reference_path(cal_ref["path"], prereg_path)
            if hashlib.sha256(cal_path.read_bytes()).hexdigest() != cal_ref["sha256"]:
                error("calibration_sha_mismatch", "calibration sha256 does not match the recorded file")
            calibration = json.loads(cal_path.read_text())
        expected = _exploratory_payload(parent, pr["inputs"]["engine_cell_label"], meta, calibration)
        for section in expected:
            if section not in ("status", "exploratory") and pr.get(section) != expected[section]:
                error("inheritance_mismatch", f"{section} differs from the parent-derived values")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error("invalid_derivation", str(exc))
    return probs


# ---------------------------------------------------------------- binding of runs / jobs to the registration
def run_blockers(pr: Dict[str, Any], prov: Dict[str, Any], run: Any) -> List[str]:
    """Reasons why ``run`` cannot count towards a DECISIVE verdict under registration ``pr`` (empty = bound). ``run`` is an
    :class:`analysis.load.Run`."""
    inp, m, proto = pr.get("inputs") or {}, pr.get("measured") or {}, pr.get("protocol") or {}
    out: List[str] = []
    if run.label != inp.get("engine_cell_label"):
        out.append(f"label {run.label!r} != registered cell {inp.get('engine_cell_label')!r}")
    if not mult_is_registered(pr, run.rate_mult):
        out.append(f"rate_mult {run.rate_mult} not in the registered lambda_mults {registered_mults(pr)}")
    if run.lambda_ref_value is None or not _close(run.lambda_ref_value, m.get("lambda_ref")):
        out.append(f"lambda_ref {run.lambda_ref_value} != registered {m.get('lambda_ref')}")
    if run.uncached_tokens_ref_value is None or not _close(run.uncached_tokens_ref_value, m.get("all_miss_uncached_tokens_per_s")):
        out.append(f"uncached_tokens_ref {run.uncached_tokens_ref_value} != registered {m.get('all_miss_uncached_tokens_per_s')}")
    if m.get("hardware") is not None and str(run.hardware) != str(m["hardware"]):
        out.append(f"hardware {run.hardware!r} != registered {m['hardware']!r}")
    if proto.get("duration_s") is not None and not _close((run.cfg.get("run") or {}).get("duration_s"), proto["duration_s"]):
        out.append(f"run.duration_s {(run.cfg.get('run') or {}).get('duration_s')} != registered {proto['duration_s']}")
    if proto.get("t_burst_s") is not None and (run.t_burst_ref is None or not _close(run.t_burst_ref, proto["t_burst_s"])):
        out.append(f"burst time {run.t_burst_ref} != registered {proto['t_burst_s']}")
    arm = run.arm or run.arm_derived
    if pr.get("status") == "EXPLORATORY" and arm not in (pr.get("exploratory") or {}).get("allowed_arms", []):
        out.append(f"arm {arm!r} is not allowed by this exploratory registration")
    reg_rescue = is_rescue_registration(pr)
    if arm == RESCUE_MODE and not reg_rescue:
        out.append("rescue arm: the registration has no rescue gate block (protocol.gate.mode rescue)")
    if reg_rescue and arm != RESCUE_MODE:
        out.append(f"arm {arm!r} under a rescue registration (it registers only the rescue arm)")
    bcfg = (run.cfg.get("arrivals") or {}).get("burst")
    if arm in ("burst", "capped", RESCUE_MODE):
        if not bcfg or not _close(bcfg.get("n"), proto.get("burst_n")) or not _close(bcfg.get("width_s"), proto.get("burst_width_s")):
            out.append(f"burst spec {bcfg} != registered n={proto.get('burst_n')} width={proto.get('burst_width_s')}")
    if arm in ("capped", RESCUE_MODE):
        if run.gate_n_cap != m.get("n_cap"):
            out.append(f"gate cap {run.gate_n_cap} != registered n_cap {m.get('n_cap')}")
    elif run.gate_n_cap is not None:
        out.append(f"{arm} arm ran with a gate cap {run.gate_n_cap}")
    if arm == RESCUE_MODE and reg_rescue:                   # n_cap is compared above as the resolved cap
        out.extend(gate_block_diff(protocol_gate(pr) or {}, dict(run.cfg.get("gate") or {}), skip=("n_cap",)))
    ra = registered_arms(pr)
    if ra is not None and arm not in ra:
        out.append(f"arm {arm!r} not in the registered protocol.arms {ra}")
    want_sha = proto.get("e2_config_sha256")
    if want_sha is not None and not reg_rescue:             # r14: the run's config file is the registered E2 config
        cfile = Path(run.dir) / "config.yaml"
        if not cfile.is_file():
            out.append("run dir has no config.yaml to compare with the registered protocol.e2_config_sha256")
        elif config_text_sha256(cfile) != want_sha:
            out.append(f"run config.yaml sha256 {config_text_sha256(cfile)} != registered protocol.e2_config_sha256 {want_sha}")
    if run.prereg_sha256 != prov.get("sha256"):
        out.append(f"run not bound to this file (meta.prereg_sha256={run.prereg_sha256!r}, file sha256={prov.get('sha256')!r})")
    t0 = run.t0_unix
    last = prov.get("git_last_commit_unix")
    if t0 is None or last is None:
        out.append("run start time or registration commit time unknown")
    elif not last < t0:
        out.append(f"registration committed at {last} but the run started at {t0}: the file does not predate the run")
    return out


def check_job(pr: Dict[str, Any], prov: Dict[str, Any], p: AnalysisParams, *, label: str, mults: Sequence[float],
              n_cap: Optional[int] = None, calibration: Optional[Dict[str, Any]] = None, hardware: Optional[str] = None,
              e2_cfg: Optional[Dict[str, Any]] = None, fcfs_substr: Optional[str] = None,
              arms: Optional[Sequence[str]] = None, calibration_path: Optional[str | Path] = None,
              allow_uncommitted: bool = False, allow_hw_mismatch: bool = False,
              e2_cfg_sha256: Optional[str] = None) -> List[str]:
    """Problems with launching an E2 job under registration ``pr`` (what the job script will pass); empty = go."""
    out = [f"[{x['code']}] {x['message']}" for x in validate(pr, p, fcfs_substr, prereg_path=prov.get("path"))
           if x["severity"] == "error"]
    inp, m, proto = pr.get("inputs") or {}, pr.get("measured") or {}, pr.get("protocol") or {}
    exploratory = pr.get("status") == "EXPLORATORY" or "exploratory" in pr
    if not allow_uncommitted or exploratory:
        if not prov["committed_clean"]:
            out.append("pre-registration file is not committed and unmodified (commit the filled file BEFORE submitting E2 jobs)")
    if exploratory:
        meta = pr.get("exploratory") if isinstance(pr.get("exploratory"), dict) else {}
        allowed = meta.get("allowed_arms", [])
        try:
            if _committed_sha256(Path(prov["path"])) != prov["sha256"]:
                out.append("exploratory file bytes do not match the committed sha256")
        except (OSError, ValueError, KeyError) as exc:
            out.append(f"exploratory file must be committed: {exc}")
        if not arms:
            out.append("exploratory jobs require explicit ARMS")
        for arm in arms or []:
            if arm not in allowed:
                out.append(f"job arm {arm!r} not in allowed_arms {allowed}")
        if calibration is None:
            out.append("exploratory jobs require CALIB_FILE reference rates")
        override = meta.get("calibration_override")
        if override and calibration_path is not None:
            if hashlib.sha256(Path(calibration_path).read_bytes()).hexdigest() != override.get("sha256"):
                out.append("CALIB_FILE sha256 does not match the exploratory calibration")
    if label != inp.get("engine_cell_label"):
        out.append(f"job ENGINE_LABEL {label!r} != registered cell {inp.get('engine_cell_label')!r}")
    for mu in mults:
        if not mult_is_registered(pr, mu):
            out.append(f"MULTS entry {mu} not in the registered lambda_mults {registered_mults(pr)}")
    if n_cap is not None and n_cap != m.get("n_cap"):
        out.append(f"capped arm n_cap {n_cap} != registered n_cap {m.get('n_cap')}")
    if calibration is not None:
        for k, reg in ((inp.get("lambda_ref_key"), m.get("lambda_ref")), (inp.get("uncached_tokens_ref_key"), m.get("all_miss_uncached_tokens_per_s"))):
            if k not in calibration or not _close(calibration[k], reg):
                out.append(f"CALIB_FILE {k}={calibration.get(k)} != registered {reg}")
    if hardware is not None and (not allow_hw_mismatch or exploratory) and m.get("hardware") is not None and str(hardware) != str(m["hardware"]):
        out.append(f"job hardware {hardware!r} != registered {m['hardware']!r}")
    if e2_cfg is not None:
        arr, run_c = e2_cfg.get("arrivals") or {}, e2_cfg.get("run") or {}
        b = arr.get("burst") or {}
        for name, got, want in (("run.duration_s", run_c.get("duration_s"), proto.get("duration_s")),
                                ("burst.n", b.get("n"), proto.get("burst_n")),
                                ("burst.width_s", b.get("width_s"), proto.get("burst_width_s")),
                                ("analysis_t_burst_s", arr.get("analysis_t_burst_s"), proto.get("t_burst_s"))):
            if want is not None and not _close(got, want):
                out.append(f"E2 config {name}={got} != registered protocol {want}")
    # rescue arm (plan R1): authorised only by a rescue registration, which authorises nothing else, with the registered gate
    # block and e2-config bytes; a rescue e2 config runs only the rescue arm
    pg, reg_rescue = protocol_gate(pr), is_rescue_registration(pr)
    job_arms = list(arms) if arms is not None else None
    if job_arms is None:
        if reg_rescue:
            out.append("a rescue registration requires explicit ARMS (rescue)")
    else:
        if RESCUE_MODE in job_arms and not reg_rescue:
            out.append("job arm 'rescue' needs a rescue registration (protocol.gate.mode rescue); this one registers none")
        if reg_rescue and any(a != RESCUE_MODE for a in job_arms):
            out.append(f"job arms {job_arms}: this rescue registration authorises only the rescue arm")
    if reg_rescue and n_cap is None:
        out.append("rescue arm: the job passes no resolved cap (--n-cap / N_CAP)")
    if e2_cfg is not None:
        eg = e2_cfg.get("gate") if isinstance(e2_cfg.get("gate"), dict) else {}
        other = [a for a in (job_arms or []) if a != RESCUE_MODE]
        if eg.get("mode") == RESCUE_MODE and other:
            out.append(f"E2 config gate.mode is rescue: only the rescue arm may run it, not {other}")
        if pg is not None:
            if eg.get("mode") != RESCUE_MODE:
                out.append(f"E2 config has no rescue gate block (gate.mode {eg.get('mode')!r}) but the registration registers one")
            out.extend(f"E2 config {d}" for d in gate_block_diff(pg, eg))
    if pg is not None or proto.get("e2_config_sha256") is not None:
        want = proto.get("e2_config_sha256")
        if e2_cfg_sha256 is None:
            out.append(f"{'rescue registration' if pg is not None else 'registered e2 config sha256'}: check-job needs the "
                       "--e2-config file to compare its sha256")
        elif want != e2_cfg_sha256:
            out.append(f"E2 config sha256 {e2_cfg_sha256} != registered protocol.e2_config_sha256 {want}")
    ra = registered_arms(pr)
    if ra is not None:
        if job_arms is None:
            out.append(f"this registration authorises only the arms {ra}: the job must pass explicit ARMS")
        else:
            bad = [a for a in job_arms if a not in ra]
            if bad:
                out.append(f"job arms {bad} not in the registered protocol.arms {ra}")
    if e2_cfg is not None:
        out.extend(ramp_problems(e2_cfg, mults))
    return out


# ---------------------------------------------------------------- CLI
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.prereg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill", help="fill the template from mu_curve.json, calibration.json, E0b's bracket; writes a NEW file")
    f.add_argument("--template", required=True)
    f.add_argument("--mu-curve", required=True)
    f.add_argument("--calibration", required=True)
    f.add_argument("--e0b-bracket", required=True, help="lambda_cap_bracket.json of E0b (REQUIRED, under the registered cell)")
    f.add_argument("--e2-config", default="configs/agentload_e2_burst.yaml", help="source of the registered run protocol")
    f.add_argument("--engine-cell-label", default=None, help="override the template's cell (e.g. sglang-fcfs-r1-native)")
    f.add_argument("--out", required=True, help="new file (refuses to overwrite)")
    f.add_argument("--lambda-mults", nargs="*", type=float, default=None)
    f.add_argument("--rule", default=None, help="text: how the lambda points were chosen inside the window")
    f.add_argument("--n-cap-rule", default="argmax", choices=["argmax", "smallest_within_margin"],
                   help="how the CAPPED arm's cap is chosen from mu(n) (recorded in measured.n_cap_rule)")
    f.add_argument("--params", default="configs/agentload_analysis.yaml")
    f.add_argument("--set", action="append", default=[], help="override an analysis param (as summarize --set)")
    f.add_argument("--arms", nargs="*", default=None, help="register protocol.arms: the only arms the registration authorises")
    d = sub.add_parser("derive-exploratory", help="derive a NEW exploratory cell file from a committed FILLED parent")
    d.add_argument("--from", dest="parent", required=True)
    d.add_argument("--engine-cell-label", required=True)
    d.add_argument("--calibration", default=None, help="this engine's E0a calibration (required for a different engine)")
    d.add_argument("--arms", nargs="+", default=["burst"], choices=["burst", "noburst", "capped"])
    d.add_argument("--out", required=True, help="new file in the parent's repository (refuses to overwrite)")
    d.add_argument("--params", default="configs/agentload_analysis.yaml")
    d.add_argument("--set", action="append", default=[])
    v = sub.add_parser("validate", help="exit 1 if the file has error-severity problems")
    v.add_argument("file")
    v.add_argument("--params", default="configs/agentload_analysis.yaml")
    v.add_argument("--set", action="append", default=[], help="override an analysis param (as summarize --set)")
    v.add_argument("--fcfs-substr", default="fcfs")
    c = sub.add_parser("check-job", help="exit 1 unless an E2 job with these inputs may run under this registration; prints PREREG_SHA256")
    c.add_argument("file")
    c.add_argument("--label", required=True)
    c.add_argument("--mults", required=True, help="space-separated list")
    c.add_argument("--arms", default=None, help="space-separated job arms; required for exploratory registrations")
    c.add_argument("--n-cap", type=int, default=None)
    c.add_argument("--calib", default=None)
    c.add_argument("--hardware", default=None)
    c.add_argument("--e2-config", default="configs/agentload_e2_burst.yaml")
    c.add_argument("--duration-s", type=float, default=None, help="the job's effective run.duration_s (overrides the config file)")
    c.add_argument("--t-burst-s", type=float, default=None, help="the job's effective burst time (overrides the config file)")
    c.add_argument("--params", default="configs/agentload_analysis.yaml")
    c.add_argument("--set", action="append", default=[], help="override an analysis param (the SAME overrides the analysis will use)")
    c.add_argument("--fcfs-substr", default="fcfs")
    c.add_argument("--allow-uncommitted", action="store_true", help="TEST ONLY (local smoke test)")
    c.add_argument("--allow-hw-mismatch", action="store_true")
    args = ap.parse_args(argv)
    p = load_params(args.params, args.set)
    if args.cmd == "derive-exploratory":
        out = Path(args.out)
        if out.exists():
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        try:
            if _repo_root(out.resolve()) != _repo_root(Path(args.parent).resolve()):
                raise ValueError("output must be in the parent's repository")
            pr = derive_exploratory(args.parent, engine_cell_label=args.engine_cell_label,
                                    calibration_path=args.calibration, arms=args.arms, p=p)
            with out.open("x", encoding="utf-8", newline="\n") as stream:
                yaml.safe_dump(pr, stream, sort_keys=False)
        except (OSError, ValueError) as exc:
            print(f"cannot derive exploratory registration: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {out} status=EXPLORATORY")
        return 0
    if args.cmd == "fill":
        out = Path(args.out)
        if out.exists():
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        pr = fill(load_prereg(args.template), json.loads(Path(args.mu_curve).read_text()),
                  json.loads(Path(args.calibration).read_text()), e0b=json.loads(Path(args.e0b_bracket).read_text()),
                  e2_cfg=yaml.safe_load(Path(args.e2_config).read_text()), lambda_mults=args.lambda_mults, rule=args.rule,
                  engine_cell_label=args.engine_cell_label, mu_curve_path=args.mu_curve, calibration_path=args.calibration,
                  e0b_path=args.e0b_bracket, e2_cfg_path=args.e2_config, n_cap_rule=args.n_cap_rule, p=p,
                  e2_cfg_sha256=hashlib.sha256(Path(args.e2_config).read_bytes()).hexdigest(), arms=args.arms)
        out.write_text(yaml.safe_dump(pr, sort_keys=False))
        print(f"wrote {out} status={pr['status']}")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0 if pr["status"] == "FILLED" else 1
    if args.cmd == "validate":
        probs = validate(load_prereg(args.file), p, args.fcfs_substr, prereg_path=args.file)
        for x in probs:
            print(f"[{x['severity']}] {x['code']}: {x['message']}")
        return 1 if any(x["severity"] == "error" for x in probs) else 0
    pr = load_prereg(args.file)
    prov = file_provenance(args.file)
    calib = json.loads(Path(args.calib).read_text()) if args.calib else None
    e2 = yaml.safe_load(Path(args.e2_config).read_text()) if args.e2_config else None
    e2_sha = hashlib.sha256(Path(args.e2_config).read_bytes()).hexdigest() if args.e2_config else None
    if e2 is not None:
        if args.duration_s is not None:
            e2.setdefault("run", {})["duration_s"] = args.duration_s
        if args.t_burst_s is not None:
            e2.setdefault("arrivals", {})["analysis_t_burst_s"] = args.t_burst_s
    probs = check_job(pr, prov, p, label=args.label, mults=[float(x) for x in args.mults.split()], n_cap=args.n_cap,
                      calibration=calib, hardware=args.hardware, e2_cfg=e2, fcfs_substr=args.fcfs_substr,
                      arms=args.arms.split() if args.arms is not None else None, calibration_path=args.calib,
                      allow_uncommitted=args.allow_uncommitted, allow_hw_mismatch=args.allow_hw_mismatch,
                      e2_cfg_sha256=e2_sha)
    for x in probs:
        print(f"PREREG PROBLEM: {x}")
    if probs:
        return 1
    print(f"PREREG_SHA256={prov['sha256']}")
    print(f"PREREG_OK file={prov['path']} commit={prov['git_last_commit']} committed_clean={prov['committed_clean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
