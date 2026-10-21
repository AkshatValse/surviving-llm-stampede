"""Evaluation of the pre-registered predictions P1-P8 (configs/prefix_meta_mech_prereg.yaml) from round-2 result
tables. Pure functions on DataFrames; each returns rows ``{id, claim, verdict, numbers, notes}`` with verdict in
{PASS, FAIL, NOT_EVALUABLE}. The thresholds are copied from the verbatim prediction text and amendment 1; nothing is
tuned here."""
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


def eval_p1(phase_runs: pd.DataFrame) -> Dict[str, Any]:
    claim = "FCFS from cold 300 recovers 3/3 at lambda <= 0.9 lambda_miss and 0/3 at lambda >= 1.1 lambda_miss"
    r = phase_runs[phase_runs["policy"] == "fcfs"]
    nums: Dict[str, Any] = {}
    viol, missing = [], []
    for m in P1_RECOVER_MULTS:
        c = _cell(r, "fcfs", m, "recovered")
        nums[f"recovered@{m}"] = c
        if c is None:
            missing.append(m)
        elif c["k"] != c["n"]:
            viol.append(m)
    for m in P1_FAIL_MULTS:
        c = _cell(r, "fcfs", m, "recovered")
        nums[f"recovered@{m}"] = c
        if c is None:
            missing.append(m)
        elif c["k"] != 0:
            viol.append(m)
    c1 = _cell(r, "fcfs", 1.0, "recovered")
    nums["recovered@1.0 (unspecified)"] = c1
    if len(missing) == len(P1_RECOVER_MULTS) + len(P1_FAIL_MULTS):
        return _row("P1", claim, NA, nums, "no FCFS phase runs")
    if viol:
        return _row("P1", claim, FAIL, {**nums, "violating_mults": viol}, "")
    return _row("P1", claim, NA if missing else PASS, {**nums, "missing_mults": missing},
                "some required cells absent" if missing else "")


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
    sel = burst[burst["policy"] == policy]
    if len(sel) == 0:
        return None
    return {"k": int(_truthy(sel["trapped"]).sum()), "n": int(len(sel))}


def eval_p2(mech_runs: pd.DataFrame) -> Dict[str, Any]:
    claim = "PEEK-like: recovers 0/3 at 1.5x and 2x from cold 300; trapped by burst 200 in >= 4/5 seeds at 2x"
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    cells = _recover_cells(cold, "peek")
    tr = _trapped(burst, "peek")
    nums = {"recovered": {str(k): v for k, v in cells.items()}, "trapped_burst": tr}
    if not _all(list(cells.values())) or tr is None:
        return _row("P2", claim, NA, nums, "peek runs absent")
    ok = all(c["k"] == 0 for c in cells.values()) and tr["k"] >= _ceil(0.8 * tr["n"])
    return _row("P2", claim, PASS if ok else FAIL, nums)


def _p3_family(cold: pd.DataFrame, burst: pd.DataFrame, pols: Sequence[str]) -> Dict[str, Any]:
    nums: Dict[str, Any] = {}
    ok_all, any_missing = True, False
    for p in pols:
        cells = _recover_cells(cold, p)
        tr = _trapped(burst, p)
        nums[p] = {"recovered": {str(k): v for k, v in cells.items()}, "trapped_burst": tr}
        if not _all(list(cells.values())) or tr is None:
            any_missing = True
            continue
        ok = _recovers_at_least(cells, 2.0 / 3.0) and tr["k"] <= _floor(0.2 * tr["n"])
        nums[p]["satisfied"] = bool(ok)
        ok_all = ok_all and bool(ok)
    return {"nums": nums, "ok": ok_all, "missing": any_missing}


def eval_p3(mech_runs: pd.DataFrame) -> List[Dict[str, Any]]:
    claim = ("TTL-pin with tau >= 2x mean tool time (tau in {10, 20} s): recovers >= 2/3 at 1.5x and 2x and trapped in "
             "<= 1/5 burst seeds at 2x")
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    out = []
    for pid, pols, label in (("P3", ["ttl10", "ttl20"], "primary family (Continuum priority + pin)"),
                             ("P3-ablation-FCFS-order", ["ttlf10", "ttlf20"], "pins with plain FCFS order")):
        f = _p3_family(cold, burst, pols)
        verdict = NA if f["missing"] else (PASS if f["ok"] else FAIL)
        out.append(_row(pid, claim + f" [{label}]", verdict, f["nums"]))
    return out


def eval_p4(mech_runs: pd.DataFrame) -> Dict[str, Any]:
    claim = ("LB-CAP (N_lb from the workload): recovers >= 2/3 at 1.5x and 2x, trapped <= 1/5 at 2x; CAP at 1.3 N_lb "
             "recovers 0/3 at 2x")
    cold, burst = _cold(mech_runs), _burst(mech_runs)
    cells = _recover_cells(cold, "lb_cap")
    tr = _trapped(burst, "lb_cap")
    c13 = _cell(cold, "cap_1p3", 2.0, "recovered")
    nums = {"lb_cap_recovered": {str(k): v for k, v in cells.items()}, "lb_cap_trapped_burst": tr,
            "cap_1p3_recovered@2.0": c13}
    if not _all(list(cells.values())) or tr is None or c13 is None:
        return _row("P4", claim, NA, nums, "lb_cap / cap_1p3 runs absent")
    ok = _recovers_at_least(cells, 2.0 / 3.0) and tr["k"] <= _floor(0.2 * tr["n"]) and c13["k"] == 0
    return _row("P4", claim, PASS if ok else FAIL, nums)


def eval_p5(mech_runs: pd.DataFrame) -> Dict[str, Any]:
    claim = "AIMD-CAP recovers >= 2/3 at 1.5x and 2x"
    cells = _recover_cells(_cold(mech_runs), "aimd_cap")
    nums = {"aimd_cap_recovered": {str(k): v for k, v in cells.items()}}
    ok = _recovers_at_least(cells, 2.0 / 3.0)
    if ok is None:
        return _row("P5", claim, NA, nums, "aimd_cap runs absent")
    return _row("P5", claim, PASS if ok else FAIL, nums)


def eval_p6(mech_runs: pd.DataFrame, limits: Optional[pd.DataFrame]) -> Dict[str, Any]:
    claim = ("every non-work-conserving policy that recovers has a from-empty stable limit >= 0.8 x LPM's limit")
    if limits is None or "lpm" not in set(limits["policy"]):
        return _row("P6", claim, NA, {}, "limits table or LPM limit absent")
    cold = _cold(mech_runs)
    lim = limits.set_index("policy")["lambda_cap"].to_dict()
    lpm = float(lim["lpm"])
    rows, viol, missing_limit = {}, [], []
    for p in NWC_POLICIES:
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


def _p7_one(summary: pd.DataFrame, col: str, ks: Sequence[float], min_events: int = 3) -> Dict[str, Any]:
    means, events = [], []
    for k in ks:
        r = summary[np.isclose(summary["k"].astype(float), k)]
        means.append(float(r[col].iloc[0]) if len(r) else float("nan"))
        events.append(int(r["n_events"].iloc[0]) if len(r) else 0)
    fin = [m for m in means if m == m]
    order_viol = any(b <= a for a, b in zip(fin, fin[1:]))
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


def eval_p7(escape_summary: pd.DataFrame, lam_mult: float = 2.25, ks: Sequence[float] = (0.25, 0.5, 1.0)
            ) -> List[Dict[str, Any]]:
    claim = ("at lambda = 2.25 lambda_miss the mean time to collapse increases strictly with k in {0.25, 0.5, 1} with "
             "log(mean) roughly linear in k")
    s = escape_summary[np.isclose(escape_summary["lam_mult"].astype(float), lam_mult)]
    if len(s) == 0 or not all((np.isclose(s["k"].astype(float), k)).any() for k in ks):
        return [_row("P7", claim, NA, {}, "escape summary for the required sizes absent")]
    prim = _p7_one(s, "exp_mean", ks)
    sec = _p7_one(s, "km_rmst", ks)
    return [_row("P7", claim + " [primary: exponential-MLE mean]", prim["verdict"], prim, prim.get("reason", "")),
            _row("P7-secondary-KM-RMST", claim + " [Kaplan-Meier restricted mean, a lower bound]", sec["verdict"],
                 sec, sec.get("reason", ""))]


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
                 robust_summary: Optional[pd.DataFrame], p8_needed: int = 5) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.append(eval_p1(phase_runs) if phase_runs is not None else _row("P1", "", NA, {}, "phase result absent"))
    if mech_runs is None:
        for pid in ("P2", "P3", "P4", "P5", "P6"):
            rows.append(_row(pid, "", NA, {}, "mech result absent"))
    else:
        rows.append(eval_p2(mech_runs))
        rows += eval_p3(mech_runs)
        rows.append(eval_p4(mech_runs))
        rows.append(eval_p5(mech_runs))
        rows.append(eval_p6(mech_runs, mech_limits))
    rows += eval_p7(escape_summary) if escape_summary is not None else [_row("P7", "", NA, {}, "escape result absent")]
    rows.append(eval_p8(robust_summary, p8_needed) if robust_summary is not None
                else _row("P8", "", NA, {}, "robust result absent"))
    return rows


def rows_to_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{"id": r["id"], "verdict": r["verdict"], "claim": r["claim"], "notes": r["notes"],
                          "numbers": json.dumps(r["numbers"], default=float)} for r in rows])
