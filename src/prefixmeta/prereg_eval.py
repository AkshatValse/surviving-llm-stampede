"""Evaluation of the pre-registered predictions P1-P8 (configs/prefix_meta_mech_prereg.yaml) from round-2 result
tables. Pure functions on DataFrames; each returns rows ``{id, claim, verdict, numbers, notes}`` with verdict in
{PASS, FAIL, NOT_EVALUABLE}. The thresholds are copied from the verbatim prediction text, amendment 1 and amendment 2
(written after the round-2 review); nothing is tuned here. Where amendment 2 changed a reading, BOTH readings are
returned as separate rows: the amended one under the plain id (P3, P4, P6, ...) and the registered one under an id
that says so."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

PASS, FAIL, NA = "PASS", "FAIL", "NOT_EVALUABLE"
#: amendment 1 (p6_policy_set)
NWC_POLICIES = ["peek", "ttl5", "ttl10", "ttl20", "ttlf5", "ttlf10", "ttlf20", "lb_cap", "cap_1p3", "aimd_cap",
                "concur_cap"]
#: amendment 2 adds the Continuum-like eager-unpin variants to the non-work-conserving set of P6
NWC_POLICIES_A2 = NWC_POLICIES + ["ttl10e", "ttl20e", "ttl10ef", "ttl20ef"]
#: P3 families (amendment 2): A = blocking pin + program priority (amendment-1 primary), B = blocking pin + FCFS,
#: C = Continuum-like eager unpin (scout spec, unverified against the paper)
P3_FAMILIES = {"A": ["ttl10", "ttl20"], "B": ["ttlf10", "ttlf20"], "C": ["ttl10e", "ttl20e"]}
P1_RECOVER_MULTS = [0.6, 0.8, 0.9]
P1_FAIL_MULTS = [1.1, 1.25, 1.5, 2.0]


def _row(pid: str, claim: str, verdict: str, numbers: Dict[str, Any], notes: str = "") -> Dict[str, Any]:
    return {"id": pid, "claim": claim, "verdict": verdict, "numbers": numbers, "notes": notes}


def _truthy(series: pd.Series) -> pd.Series:
    """Bool view of a column that may hold NaN (-> False) and True/False objects or 'True'/'False' strings."""
    return series.map(lambda v: (v is True) or (v == "True") or (isinstance(v, (bool, np.bool_)) and bool(v))
                      or (isinstance(v, (int, float, np.number)) and v == v and bool(v)))


def _ceil(x: float) -> int:
    return int(math.ceil(x - 1e-9))


def _floor(x: float) -> int:
    return int(math.floor(x + 1e-9))


def _cell(df: pd.DataFrame, policy: str, mult: float, col: str) -> Optional[Dict[str, int]]:
    """(count of True in ``col``, n runs) for a policy at a multiple; None if the cell is absent."""
    sel = df[(df["policy"] == policy) & np.isclose(df["lam_mult"].astype(float), mult)]
    if len(sel) == 0:
        return None
    return {"k": int(_truthy(sel[col]).sum()), "n": int(len(sel))}


def _all(cells: Sequence[Optional[Dict[str, int]]]) -> bool:
    return all(c is not None for c in cells)


def eval_p1(phase_runs: pd.DataFrame, col: str = "recovered", pid: str = "P1") -> Dict[str, Any]:
    claim = "FCFS from cold 300 recovers 3/3 at lambda <= 0.9 lambda_miss and 0/3 at lambda >= 1.1 lambda_miss"
    r = phase_runs[phase_runs["policy"] == "fcfs"]
    nums: Dict[str, Any] = {}
    viol, missing = [], []
    for m in P1_RECOVER_MULTS:
        c = _cell(r, "fcfs", m, col)
        nums[f"recovered@{m}"] = c
        if c is None:
            missing.append(m)
        elif c["k"] != c["n"]:
            viol.append(m)
    for m in P1_FAIL_MULTS:
        c = _cell(r, "fcfs", m, col)
        nums[f"recovered@{m}"] = c
        if c is None:
            missing.append(m)
        elif c["k"] != 0:
            viol.append(m)
    c1 = _cell(r, "fcfs", 1.0, col)
    nums["recovered@1.0 (unspecified)"] = c1
    if len(missing) == len(P1_RECOVER_MULTS) + len(P1_FAIL_MULTS):
        return _row(pid, claim, NA, nums, "no FCFS phase runs")
    if viol:
        return _row(pid, claim, FAIL, {**nums, "violating_mults": viol}, "")
    return _row(pid, claim, NA if missing else PASS, {**nums, "missing_mults": missing},
                "some required cells absent" if missing else "")


def eval_p1_rows(phase_runs: pd.DataFrame) -> List[Dict[str, Any]]:
    """P1 judged at the horizon the runs used (long, amendment 2) and, from the same runs' windows, at the registered
    30 000 s horizon (``recovered_registered_horizon``, present when the phase runs carry it)."""
    rows = [eval_p1(phase_runs)]
    if "recovered_registered_horizon" in phase_runs.columns:
        r = eval_p1(phase_runs, col="recovered_registered_horizon", pid="P1-registered-horizon")
        r["notes"] = ("the same runs re-judged on [25000, 30000] s, i.e. at the registered horizon (review finding 7)"
                      + (("; " + r["notes"]) if r["notes"] else ""))
        rows.append(r)
    return rows


def _cold(mech_runs: pd.DataFrame) -> pd.DataFrame:
    return mech_runs[mech_runs["part"] == "cold"]


def _burst(mech_runs: pd.DataFrame, lam_mult: float = 2.0) -> pd.DataFrame:
    b = mech_runs[(mech_runs["part"] == "burst") & np.isclose(mech_runs["lam_mult"].astype(float), lam_mult)]
    return b


def _recover_cells(cold: pd.DataFrame, policy: str) -> Dict[float, Optional[Dict[str, int]]]:
    return {m: _cell(cold, policy, m, "recovered") for m in (1.5, 2.0)}


def _recovers_at_least(cells: Dict[float, Optional[Dict[str, int]]], frac: float) -> Optional[bool]:
    if not _all(list(cells.values())):
        return None
    return all(c["k"] >= _ceil(frac * c["n"]) for c in cells.values())


def _trapped(burst: pd.DataFrame, policy: str) -> Optional[Dict[str, int]]:
    """Registered burst reading: runs the E2 criterion calls TRAPPED (hit rate < 0.2 for >= 10 consecutive windows)."""
    sel = burst[burst["policy"] == policy]
    if len(sel) == 0:
        return None
    return {"k": int(_truthy(sel["trapped"]).sum()), "n": int(len(sel))}


def _congested(burst: pd.DataFrame, policy: str) -> Optional[Dict[str, int]]:
    """Strict burst reading (amendment 2): a run counts as congested unless it is ``burst_recovered`` (hit rate > 0.8 AND
    tail backlog < 20), so a policy that keeps the hit rate high while its queue / gate grows is NOT counted as fine."""
    sel = burst[burst["policy"] == policy]
    if len(sel) == 0 or "burst_recovered" not in sel.columns:
        return None
    return {"k": int((~_truthy(sel["burst_recovered"])).sum()), "n": int(len(sel))}


def eval_p2(mech_runs: pd.DataFrame, policy: str = "peek_rank", pid: str = "P2") -> Dict[str, Any]:
    claim = (f"PEEK-like queued-prefix protection [{policy}]: recovers 0/3 at 1.5x and 2x from cold 300; trapped by burst "
             "200 in >= 4/5 seeds at 2x")
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    cells = _recover_cells(cold, policy)
    tr = _trapped(burst, policy)
    nums = {"policy": policy, "recovered": {str(k): v for k, v in cells.items()}, "trapped_burst": tr,
            "not_burst_recovered": _congested(burst, policy)}
    if not _all(list(cells.values())) or tr is None:
        return _row(pid, claim, NA, nums, f"{policy} runs absent")
    ok = all(c["k"] == 0 for c in cells.values()) and tr["k"] >= _ceil(0.8 * tr["n"])
    return _row(pid, claim, PASS if ok else FAIL, nums)


def eval_p2_rows(mech_runs: pd.DataFrame) -> List[Dict[str, Any]]:
    """Amendment 2: the PEEK clause of H1 (work-conserving admission) is judged on ``peek_rank`` (ranking only, never a
    pin); hard ``peek`` is non-work-conserving and is reported as its own row, ``peek_lpm`` (= LPM in this workload)
    as information."""
    rows = [eval_p2(mech_runs, "peek_rank", "P2")]
    rows[0]["notes"] = "headline: peek_rank (work-conserving)"
    hard = eval_p2(mech_runs, "peek", "P2-hard-pin")
    hard["notes"] = "amendment-1 primary; hard pin is non-work-conserving (admission waits behind protected KV)"
    lpm = eval_p2(mech_runs, "peek_lpm", "P2-peek_lpm")
    lpm["notes"] = "information: hard protection under LPM order never binds in this workload (equivalent to LPM)"
    return rows + [hard, lpm]


def _p3_family(cold: pd.DataFrame, burst: pd.DataFrame, pols: Sequence[str], reading: str = "registered"
               ) -> Dict[str, Any]:
    nums: Dict[str, Any] = {}
    ok_all, any_missing = True, False
    for p in pols:
        cells = _recover_cells(cold, p)
        tr = _trapped(burst, p) if reading == "registered" else _congested(burst, p)
        nums[p] = {"recovered": {str(k): v for k, v in cells.items()}, "burst_count": tr, "burst_reading": reading,
                   "trapped_burst": _trapped(burst, p), "not_burst_recovered": _congested(burst, p)}
        if not _all(list(cells.values())) or tr is None:
            any_missing = True
            continue
        ok = _recovers_at_least(cells, 2.0 / 3.0) and tr["k"] <= _floor(0.2 * tr["n"])
        nums[p]["satisfied"] = bool(ok)
        ok_all = ok_all and bool(ok)
    return {"nums": nums, "ok": ok_all, "missing": any_missing}


def eval_p3(mech_runs: pd.DataFrame) -> List[Dict[str, Any]]:
    """P3 under every family x burst reading (amendment 2). Headline ``P3`` = all three families (A: blocking pin +
    program priority, B: blocking pin + FCFS, C: Continuum-like eager unpin) satisfy the STRICT burst reading;
    ``P3-registered-burst-reading`` = all three satisfy the registered (trapped-only) reading."""
    claim = ("TTL-pin with tau >= 2x mean tool time (tau in {10, 20} s): recovers >= 2/3 at 1.5x and 2x and trapped in "
             "<= 1/5 burst seeds at 2x")
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    out: List[Dict[str, Any]] = []
    verdicts: Dict[str, Dict[str, str]] = {"strict": {}, "registered": {}}
    for reading in ("strict", "registered"):
        for fam, pols in P3_FAMILIES.items():
            f = _p3_family(cold, burst, pols, reading)
            v = NA if f["missing"] else (PASS if f["ok"] else FAIL)
            verdicts[reading][fam] = v
            out.append(_row(f"P3-{fam}-{reading}", claim + f" [family {fam}: {pols}; burst reading: {reading}]", v,
                            f["nums"]))

    def conj(vs: Dict[str, str]) -> str:
        if any(v == FAIL for v in vs.values()):
            return FAIL
        return NA if any(v == NA for v in vs.values()) else PASS
    head = _row("P3", claim + " [all three families A, B, C; strict burst reading]", conj(verdicts["strict"]),
                {"family_verdicts": verdicts["strict"]},
                "A = blocking pin + program priority, B = blocking pin + FCFS, C = eager unpin (Continuum-like)")
    reg = _row("P3-registered-burst-reading", claim + " [all three families; trapped-only burst reading]",
               conj(verdicts["registered"]), {"family_verdicts": verdicts["registered"]})
    return [head, reg] + out


def eval_p4(mech_runs: pd.DataFrame, reading: str = "strict", pid: str = "P4") -> Dict[str, Any]:
    claim = ("LB-CAP (N_lb from the workload): recovers >= 2/3 at 1.5x and 2x, trapped <= 1/5 at 2x; CAP at 1.3 N_lb "
             f"recovers 0/3 at 2x [burst reading: {reading}]")
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    cells = _recover_cells(cold, "lb_cap")
    tr = _trapped(burst, "lb_cap") if reading == "registered" else _congested(burst, "lb_cap")
    c13 = _cell(cold, "cap_1p3", 2.0, "recovered")
    nums = {"lb_cap_recovered": {str(k): v for k, v in cells.items()}, "lb_cap_burst_count": tr, "burst_reading": reading,
            "lb_cap_trapped_burst": _trapped(burst, "lb_cap"), "lb_cap_not_burst_recovered": _congested(burst, "lb_cap"),
            "cap_1p3_recovered@2.0": c13}
    if not _all(list(cells.values())) or tr is None or c13 is None:
        return _row(pid, claim, NA, nums, "lb_cap / cap_1p3 runs absent")
    ok = _recovers_at_least(cells, 2.0 / 3.0) and tr["k"] <= _floor(0.2 * tr["n"]) and c13["k"] == 0
    return _row(pid, claim, PASS if ok else FAIL, nums)


def eval_p4_rows(mech_runs: pd.DataFrame) -> List[Dict[str, Any]]:
    a = eval_p4(mech_runs, "strict", "P4")
    a["notes"] = ("LB-CAP N_lb and the CAP(1.3 N_lb) failure were observed in round 1 before the prediction was "
                  "written (a confirmation, not a blind prediction; amendment 2)")
    return [a, eval_p4(mech_runs, "registered", "P4-registered-burst-reading")]


def eval_p5(mech_runs: pd.DataFrame) -> Dict[str, Any]:
    claim = "AIMD-CAP recovers >= 2/3 at 1.5x and 2x"
    cells = _recover_cells(_cold(mech_runs), "aimd_cap")
    nums = {"aimd_cap_recovered": {str(k): v for k, v in cells.items()}}
    ok = _recovers_at_least(cells, 2.0 / 3.0)
    if ok is None:
        return _row("P5", claim, NA, nums, "aimd_cap runs absent")
    return _row("P5", claim, PASS if ok else FAIL, nums)


def eval_p6(mech_runs: pd.DataFrame, limits: Optional[pd.DataFrame],
            policies: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """REGISTERED reading: ratio of from-empty stable limits (escape-limited; review finding 5 shows it is close to
    tautological because a policy that recovers at 2x has a limit of about 2x or more)."""
    claim = ("every non-work-conserving policy that recovers has a from-empty stable limit >= 0.8 x LPM's limit")
    if limits is None or "lpm" not in set(limits["policy"]):
        return _row("P6", claim, NA, {}, "limits table or LPM limit absent")
    cold = _cold(mech_runs)
    lim = limits.set_index("policy")["lambda_cap"].to_dict()
    lpm = float(lim["lpm"])
    rows, viol, missing_limit = {}, [], []
    for p in (policies if policies is not None else NWC_POLICIES):
        cells = _recover_cells(cold, p)
        rec = _recovers_at_least(cells, 2.0 / 3.0)
        if rec is None or not rec:
            rows[p] = {"recovers": bool(rec) if rec is not None else None}
            continue
        if p not in lim:
            missing_limit.append(p)
            rows[p] = {"recovers": True, "limit": None}
            continue
        ratio = float(lim[p]) / lpm
        rows[p] = {"recovers": True, "limit": float(lim[p]), "ratio_to_lpm": ratio}
        if ratio < 0.8:
            viol.append(p)
    recovering = [p for p, v in rows.items() if v.get("recovers")]
    nums = {"lpm_limit": lpm, "policies": rows, "violating": viol, "recovering": recovering,
            "recovering_without_limit": missing_limit}
    if missing_limit:
        return _row("P6", claim, NA, nums, "a recovering policy has no measured limit")
    if not recovering:
        return _row("P6", claim, NA, nums, "vacuous: no non-work-conserving policy recovered")
    return _row("P6", claim, FAIL if viol else PASS, nums)


def eval_p6_capacity(mech_runs: pd.DataFrame, capacity: Optional[pd.DataFrame],
                     policies: Optional[Sequence[str]] = None, ref: str = "lpm") -> Dict[str, Any]:
    """AMENDED reading (amendment 2): the price of stability is the ratio of GOOD-STATE CAPACITIES (max over closed
    populations of the cached steady-state throughput) of each recovering non-work-conserving policy to LPM's, which
    must be >= 0.8. Unlike the stable limit this is not depressed by the metastable escapes under study."""
    claim = ("every non-work-conserving policy that recovers has a good-state throughput ceiling >= 0.8 x LPM's "
             "ceiling [closed-population capacity]")
    if capacity is None or ref not in set(capacity["policy"]):
        return _row("P6", claim, NA, {}, "capacity table or LPM ceiling absent")
    cold = _cold(mech_runs)
    ceil = capacity.set_index("policy")["ceiling_sessions_per_s"].to_dict()
    ref_c = float(ceil[ref])
    rows, viol, missing = {}, [], []
    for p in (policies if policies is not None else NWC_POLICIES_A2):
        cells = _recover_cells(cold, p)
        rec = _recovers_at_least(cells, 2.0 / 3.0)
        if rec is None or not rec:
            rows[p] = {"recovers": bool(rec) if rec is not None else None}
            continue
        if p not in ceil:
            missing.append(p)
            rows[p] = {"recovers": True, "ceiling": None}
            continue
        ratio = float(ceil[p]) / ref_c
        rows[p] = {"recovers": True, "ceiling": float(ceil[p]), "ratio_to_lpm": ratio}
        if ratio < 0.8:
            viol.append(p)
    recovering = [p for p, v in rows.items() if v.get("recovers")]
    nums = {"lpm_ceiling_sessions_per_s": ref_c, "policies": rows, "violating": viol, "recovering": recovering,
            "recovering_without_ceiling": missing}
    if missing:
        return _row("P6", claim, NA, nums, "a recovering policy has no measured ceiling")
    if not recovering:
        return _row("P6", claim, NA, nums, "vacuous: no non-work-conserving policy recovered")
    return _row("P6", claim, FAIL if viol else PASS, nums)


def _p7_one(summary: pd.DataFrame, col: str, ks: Sequence[float], min_events: int = 3) -> Dict[str, Any]:
    means, events = [], []
    for k in ks:
        r = summary[np.isclose(summary["k"].astype(float), k)]
        means.append(float(r[col].iloc[0]) if len(r) else float("nan"))
        events.append(int(r["n_events"].iloc[0]) if len(r) else 0)
    # An order violation can only be asserted between sizes whose means are both ESTIMATED (>= min_events collapses). A
    # censored size contributes a lower bound (Kaplan-Meier restricted mean: the horizon; exponential MLE with few
    # events: very noisy), and two bounds that tie at the horizon are not a violation (evaluator fix made after the full
    # runs; it changes no PASS / FAIL of a primary exponential-MLE row, see the report notes).
    est = [(m, e) for m, e in zip(means, events)]
    order_viol = any((a[0] == a[0] and b[0] == b[0] and a[1] >= min_events and b[1] >= min_events and b[0] <= a[0])
                     for a, b in zip(est, est[1:]))
    out: Dict[str, Any] = {"estimator": col, "ks": list(ks), "means": means, "n_events": events}
    if order_viol:
        return {**out, "verdict": FAIL, "reason": "means are not strictly increasing in k"}
    if any(e < min_events for e in events) or any(m != m for m in means):
        return {**out, "verdict": NA, "reason": f"fewer than {min_events} collapses at some size (mean censored)"}
    s1 = (math.log(means[1]) - math.log(means[0])) / (ks[1] - ks[0])
    s2 = (math.log(means[2]) - math.log(means[1])) / (ks[2] - ks[1])
    ratio = s1 / s2 if s2 != 0 else float("inf")
    lin = s1 > 0 and s2 > 0 and 0.5 <= ratio <= 2.0
    return {**out, "slopes": [s1, s2], "slope_ratio": ratio, "verdict": PASS if lin else FAIL,
            "reason": "" if lin else "log-mean not roughly linear in k (slopes not positive and within a factor 2)"}


def _window_info(s: pd.DataFrame, ks: Sequence[float]) -> Dict[str, Any]:
    """lambda_cap(k) and lambda / lambda_cap(k) per size (when the escape run measured the per-size limit)."""
    info: Dict[str, Any] = {}
    if "lam_over_cap" not in s.columns:
        return info
    ratios = []
    for k in ks:
        r = s[np.isclose(s["k"].astype(float), k)]
        v = float(r["lam_over_cap"].iloc[0]) if len(r) and r["lam_over_cap"].notna().any() else float("nan")
        ratios.append(v)
    info["lam_over_cap"] = ratios
    if "lambda_cap_k" in s.columns:
        info["lambda_cap_k"] = [float(s[np.isclose(s["k"].astype(float), k)]["lambda_cap_k"].iloc[0])
                                if len(s[np.isclose(s["k"].astype(float), k)]) else float("nan") for k in ks]
    info["in_window_all_sizes"] = bool(all(v == v and v < 1.0 for v in ratios))
    return info


def eval_p7(escape_summary: pd.DataFrame, lam_mult: float = 2.25, ks: Sequence[float] = (0.25, 0.5, 1.0),
            scaling: str = "calibrated", pid: str = "P7", label: str = "") -> List[Dict[str, Any]]:
    sizes = "{" + ", ".join(f"{k:g}" for k in ks) + "}"
    claim = (f"at lambda = {lam_mult:g} lambda_miss the mean time to collapse increases strictly with k in {sizes} with "
             f"log(mean) roughly linear in k [{scaling} lambda scaling{(', ' + label) if label else ''}]")
    es = escape_summary
    if "scaling" in es.columns:
        es = es[es["scaling"] == scaling]
    s = es[np.isclose(es["lam_mult"].astype(float), lam_mult)]
    if len(s) == 0 or not all((np.isclose(s["k"].astype(float), k)).any() for k in ks):
        return [_row(pid, claim, NA, {}, "escape summary for the required sizes absent")]
    prim = _p7_one(s, "exp_mean", ks)
    sec = _p7_one(s, "km_rmst", ks)
    info = _window_info(s, ks)
    prim.update(info)
    sec.update(info)
    note = prim.get("reason", "")
    if info and not info.get("in_window_all_sizes", True):
        note += ("; NOT all sizes are inside their own stability window at this lambda (lambda / lambda_cap(k) = "
                 f"{[round(v, 3) for v in info['lam_over_cap']]}), so a verdict here is not evidence for H3")
    return [_row(pid, claim + " [primary: exponential-MLE mean]", prim["verdict"], prim, note.strip("; ")),
            _row(pid + "-secondary-KM-RMST", claim + " [Kaplan-Meier restricted mean, a lower bound]", sec["verdict"],
                 sec, sec.get("reason", ""))]


def eval_p7_rows(esc_registered: Optional[pd.DataFrame], esc_inwindow: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """Amendment 2: headline ``P7`` = the in-window design (k in {1, 2, 4}) at 2.25x, calibrated scaling, exponential-MLE
    mean; secondary rows for the other multiples and the fluid scaling; the registered design (k in {0.25, 0.5, 1}) is
    reported as ``P7-registered-sizes`` with the in-window flag."""
    rows: List[Dict[str, Any]] = []
    if esc_inwindow is not None:
        ks = (1.0, 2.0, 4.0)
        rows += eval_p7(esc_inwindow, 2.25, ks, "calibrated", "P7", "in-window sizes")
        mults = sorted(set(esc_inwindow["lam_mult"].astype(float)) - {2.25})
        for m in mults:
            rows += eval_p7(esc_inwindow, m, ks, "calibrated", f"P7-inwindow-m{m:g}", "in-window sizes")
        if "scaling" in esc_inwindow.columns and (esc_inwindow["scaling"] == "fluid").any():
            for m in sorted(set(esc_inwindow["lam_mult"].astype(float))):
                rows += eval_p7(esc_inwindow, m, ks, "fluid", f"P7-inwindow-fluid-m{m:g}", "sensitivity")
    else:
        rows.append(_row("P7", "", NA, {}, "in-window escape result absent"))
    if esc_registered is not None:
        ks = (0.25, 0.5, 1.0)
        rows += eval_p7(esc_registered, 2.25, ks, "calibrated", "P7-registered-sizes", "registered sizes")
        rows += eval_p7(esc_registered, 2.0, ks, "calibrated", "P7-registered-sizes-m2", "registered sizes")
        if "scaling" in esc_registered.columns and (esc_registered["scaling"] == "fluid").any():
            rows += eval_p7(esc_registered, 2.25, ks, "fluid", "P7-registered-sizes-fluid", "sensitivity")
    return rows


def eval_p8(robust_summary: pd.DataFrame, needed: int = 5) -> Dict[str, Any]:
    claim = ("R > 1.5 and FCFS burst trap in >= 4/5 seeds hold for >= 5 of the workload variants")
    if robust_summary is None or len(robust_summary) == 0:
        return _row("P8", claim, NA, {}, "robust summary absent")
    n_hold = int(_truthy(robust_summary["holds"]).sum())
    per = {r["variant"]: {"R_lpm": float(r["R_lpm"]), "burst_n_trapped": int(r["burst_n_trapped"]),
                          "burst_n_runs": int(r["burst_n_runs"]), "holds": bool(_truthy(pd.Series([r["holds"]])).iloc[0])}
           for _, r in robust_summary.iterrows()}
    nums = {"n_variants": int(len(robust_summary)), "n_holding": n_hold, "needed": needed, "variants": per}
    return _row("P8", claim, PASS if n_hold >= needed else FAIL, nums)


def evaluate_all(*, phase_runs: Optional[pd.DataFrame], mech_runs: Optional[pd.DataFrame],
                 mech_limits: Optional[pd.DataFrame], escape_summary: Optional[pd.DataFrame],
                 robust_summary: Optional[pd.DataFrame], p8_needed: int = 5,
                 mech_capacity: Optional[pd.DataFrame] = None,
                 escape_inwindow_summary: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows += eval_p1_rows(phase_runs) if phase_runs is not None else [_row("P1", "", NA, {}, "phase result absent")]
    if mech_runs is None:
        for pid in ("P2", "P3", "P4", "P5", "P6"):
            rows.append(_row(pid, "", NA, {}, "mech result absent"))
    else:
        rows += eval_p2_rows(mech_runs)
        rows += eval_p3(mech_runs)
        rows += eval_p4_rows(mech_runs)
        rows.append(eval_p5(mech_runs))
        rows.append(eval_p6_capacity(mech_runs, mech_capacity))
        reg = eval_p6(mech_runs, mech_limits, NWC_POLICIES_A2)
        reg["id"] = "P6-registered-limit-based"
        reg["notes"] = (reg["notes"] + "; " if reg["notes"] else "") + \
            "from-empty stable limit is escape-limited, near-tautological for any policy that recovers at 2x (finding 5)"
        rows.append(reg)
    if escape_summary is None and escape_inwindow_summary is None:
        rows.append(_row("P7", "", NA, {}, "escape result absent"))
    else:
        rows += eval_p7_rows(escape_summary, escape_inwindow_summary)
    rows.append(eval_p8(robust_summary, p8_needed) if robust_summary is not None
                else _row("P8", "", NA, {}, "robust result absent"))
    return rows


def rows_to_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{"id": r["id"], "verdict": r["verdict"], "claim": r["claim"], "notes": r["notes"],
                          "numbers": json.dumps(r["numbers"], default=float)} for r in rows])
