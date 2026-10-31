"""Round 11, bundle 3 (plan S1, tag r11-rescue-pred): blind simulator predictions for the rescue cells R1 / R4 and the remedy comparison.

    PYTHONPATH="src;." python experiments/r11_predict_rescue.py --config configs/r11_predict_rescue.yaml [--workers 6] [--quick]
                                                               [--modes mixed separate] [--cells R1_rescue smoke ...]

Reads ONLY the config (and, through it, the calibrated round-6 engine block of configs/r6_predict.yaml, the two registered calibration.json
files and the client config configs/agentload_e2_burst.yaml). For every cell x batching mode x rate it runs ``seeds`` simulator seeds
(``prefixmeta.workload.build_specs``) and, for ``exact_seeds``, the EXACT client plan of that seed (``agentload.workload.build_open_plan``, the
plan the GPU run will replay: same arrivals, turn counts and tool times). Every run is scored by the registered per-run rule of plan R1
(``gate_control.rescue_measures``). Writes results/r11_predict_rescue/<ts>/: runs_<mode>.csv (one row per run), cells_<mode>.csv (per cell x
rate), exact_traces_<mode>.csv (per-tick traces of the exact-plan rows), plan_check.csv (sha256 of every rebuilt client plan.csv and the
committed BURST plan.csv files it matches), meta.json (git state at start, file sha256s, versions), summary.md.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import dataclasses
import hashlib
import io
import json
import math
import multiprocessing as mp
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "src", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from prefixmeta import probe                                                    # noqa: E402
from prefixmeta.gate_control import BIG, GateControl, rescue_measures, simulate_gate   # noqa: E402
from prefixmeta.runner import env_versions, git_info, new_result_dir, sanitize  # noqa: E402
from prefixmeta.sim import RunSpec, deep_update                                 # noqa: E402
from prefixmeta.workload import ArrivalPlan, SessionSpecs, WorkloadParams, build_specs   # noqa: E402

EXPERIMENT = "r11_predict_rescue"
TRACKED_FILES = ("src/prefixmeta/gate_control.py", "src/prefixmeta/probe.py", "src/prefixmeta/workload.py", "src/prefixmeta/engine.py",
                 "experiments/r11_predict_rescue.py", "configs/r11_predict_rescue.yaml", "configs/r6_predict.yaml",
                 "configs/agentload_e2_burst.yaml", "src/agentload/workload.py", "src/agentload/config.py")
DELAY_THRESHOLDS_S = (60.0, 300.0, 600.0)
COHORT_S = 1800.0          # cost cohort: sessions arriving in [t_burst, t_burst + this) (analysis/rescue.py COST_COHORT_S)


# ======================================================================= exact client plans
def client_plan(rcfg: dict, *, seed: int, mult: float, lambda_ref_spec: str, protocol: dict, burst: bool):
    """The client's plan (list of SessionPlan) for one GPU run: the e2 config with the job's overrides (rate_mult, lambda_ref = the
    registered calibration path:key, run seed and duration, burst time; NOBURST: arrivals.burst = null)."""
    from agentload.config import load_config, resolve_rate
    from agentload.workload import build_open_plan
    b = protocol["burst"]
    sets = [f"arrivals.rate_mult={mult!r}", f"arrivals.lambda_ref={lambda_ref_spec}", f"run.seed={int(seed)}",
            f"run.duration_s={float(protocol['duration_s'])!r}", f"arrivals.analysis_t_burst_s={float(b['t_s'])!r}",
            "arrivals.uncached_tokens_ref=1.0"]
    sets += ([f"arrivals.burst.n={int(b['n'])}", f"arrivals.burst.t_s={float(b['t_s'])!r}", f"arrivals.burst.width_s={float(b['width_s'])!r}"]
             if burst else ["arrivals.burst=null"])
    cfg, _ = load_config(REPO / rcfg["client_config"], sets)
    rate = resolve_rate(cfg.arrivals, REPO)
    return build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, []), rate


def plan_csv_sha256(plan) -> str:
    """sha256 of the plan.csv bytes the client writes (agentload.client.write_plan_csv: csv.DictWriter, default \\r\\n terminator)."""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=["sid", "origin", "idx", "arrival_s", "n_turns", "tool_time_total_s"])
    w.writeheader()
    for sp in plan:
        w.writerow({"sid": sp.sid, "origin": sp.origin, "idx": sp.idx, "arrival_s": sp.arrival_s, "n_turns": sp.n_turns,
                    "tool_time_total_s": float(sum(sp.tool_times_s))})
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def specs_from_plan(plan) -> SessionSpecs:
    arr = np.array([sp.arrival_s for sp in plan], dtype=float)
    nt = np.array([sp.n_turns for sp in plan], dtype=np.int64)
    flat = np.array([x for sp in plan for x in sp.tool_times_s], dtype=float)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if len(plan) else np.zeros(0, np.int64)
    assert np.all(np.diff(arr) >= 0), "client plan not sorted by arrival"
    return SessionSpecs(arrival=arr, n_turns=nt, tool_off=off, tool_flat=flat)


# ======================================================================= run list
def pool_refs(rcfg: dict, pool: str) -> Dict[str, Any]:
    p = rcfg["pools"][pool]
    cal = json.loads((REPO / p["calibration"]).read_text())
    return {"lambda_ref": float(cal[p["lambda_ref_key"]]), "uncached_ref": float(cal[p["uncached_ref_key"]]),
            "lambda_ref_spec": f"{p['calibration']}:{p['lambda_ref_key']}", "kv": int(p["kv_memory_tokens"])}


def build_jobs(cfg: dict, rcfg: dict, modes: List[str], cells: List[str], quick: bool) -> List[Dict[str, Any]]:
    jobs = []
    for mode in modes:
        batching = rcfg["batching_modes"][mode]
        for cname in cells:
            c = rcfg["cells"][cname]
            refs = pool_refs(rcfg, c["pool"])
            prot = rcfg[c.get("protocol", "protocol")]
            ctl = dict(rcfg["controls"][c["control"]])
            burst = bool(c.get("burst", True))
            seeds = list(range(2 if quick else int(c["seeds"])))
            exact = list(c.get("exact_seeds") or [])[: (1 if quick else None)]
            for mult in c["mults"]:
                lam = float(mult) * refs["lambda_ref"]
                for kind, sd in [("sim", s) for s in seeds] + [("exact", s) for s in exact]:
                    jobs.append({"mode": mode, "batching": batching, "cell": cname, "group": str(c["group"]), "pool": c["pool"],
                                 "kv": refs["kv"], "mult": float(mult), "lam": lam, "uncached_ref": refs["uncached_ref"],
                                 "lambda_ref_spec": refs["lambda_ref_spec"], "control": ctl, "control_name": c["control"], "burst": burst,
                                 "protocol": prot, "t_on": c.get("t_on"), "lull": dict(c["lull"]) if c.get("lull") else None,
                                 "kind": kind, "seed": int(sd)})
    return jobs


def resolve_lull_ends(jobs: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> None:
    """Phase 2: a lull with ``t1_from: <cell>`` ends at the release time of that cell's run with the same mode, rate, kind and seed (the
    run's ``t_rel``; the run length if it never released)."""
    by = {(r["mode"], r["cell"], r["mult"], r["kind"], r["seed"]): r for r in rows}
    for j in jobs:
        src = j["lull"].get("t1_from")
        r = by.get((j["mode"], src, j["mult"], j["kind"], j["seed"]))
        if r is None:
            raise ValueError(f"{j['cell']}: no {src} run for mode {j['mode']} x {j['mult']} {j['kind']} seed {j['seed']}")
        t = r.get("t_rel")
        j["lull"]["t1"] = float(t) if t is not None and t == t else float(j["protocol"]["duration_s"])


def _run_all(payload, workers: int) -> List[Dict[str, Any]]:
    if workers <= 1:
        return [run_job(x) for x in payload]
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(run_job, payload, chunksize=4))


def _cap_traj(cap_trace: List[Tuple[float, int]], limit: int = 40) -> str:
    s = ";".join(f"{t:g}:{c}" for t, c in cap_trace)
    parts = s.split(";")
    return s if len(parts) <= limit else ";".join(parts[:limit]) + f";...(+{len(parts) - limit})"


def run_job(args: Tuple[dict, dict, dict]) -> Dict[str, Any]:
    cfg0, rcfg, job = args
    cfg = deep_update(cfg0, {"engine": {"batching": job["batching"], "kv_memory_tokens": job["kv"]}})
    prot = job["protocol"]
    H = float(prot["duration_s"])
    b = prot["burst"]
    burst_n = int(b["n"]) if job["burst"] else 0
    lull = job.get("lull")
    if lull and job["kind"] == "exact":
        raise ValueError(f"{job['cell']}: a lull cell cannot use exact client plans (the client plan has no lull thinning)")
    if lull and lull.get("t1") is None:
        raise ValueError(f"lull of {job['cell']} has no end time (t1_from not resolved)")
    plan = ArrivalPlan(kind="constant", horizon_s=H, rate=job["lam"], burst_n=burst_n, burst_t0=float(b["t_s"]), burst_width_s=float(b["width_s"]),
                       **({} if not lull else {"lull_t0": float(lull["t0"]), "lull_t1": float(lull["t1"]), "lull_keep": float(lull["keep"])}))
    rs = RunSpec(exp=EXPERIMENT, policy=rcfg["policy"], seed=job["seed"], horizon_s=H, variant=job["cell"], plan=plan)
    row: Dict[str, Any] = {k: job[k] for k in ("mode", "cell", "group", "pool", "mult", "lam", "kind", "seed", "control_name", "burst")}
    specs = None
    n_shed_lull = 0
    arrivals_planned = None              # arrival times of every planned session (incl. sessions a lull removes)
    if job["kind"] == "exact":
        cp, rate = client_plan(rcfg, seed=job["seed"], mult=job["mult"], lambda_ref_spec=job["lambda_ref_spec"], protocol=prot, burst=job["burst"])
        assert abs(rate - job["lam"]) <= 1e-15 * job["lam"], (rate, job["lam"])
        specs = specs_from_plan(cp)
        arrivals_planned = specs.arrival
        row["plan_sha256"] = plan_csv_sha256(cp)
        row["n_sessions_planned"] = len(cp)
        row["_plan"] = plan_frame(cp)
    else:
        wl = WorkloadParams.from_dict(cfg["workload"])
        specs = build_specs(wl, plan, job["seed"])
        arrivals_planned = specs.arrival
        if lull:
            full = build_specs(wl, dataclasses.replace(plan, lull_t0=None, lull_t1=None, lull_keep=1.0), job["seed"])
            n_shed_lull = len(full) - len(specs)
            arrivals_planned = full.arrival
        row["n_sessions_planned"] = len(specs)
    if lull:
        row["lull_t1"] = float(lull["t1"])
    control = GateControl.from_dict(job["control"])
    t0 = time.perf_counter()
    res = simulate_gate(cfg, rs, control, specs)
    row["wall_s"] = time.perf_counter() - t0
    g = res["gate"]["stats"]
    t_on = job["t_on"] if job["t_on"] is not None else g["t_engage"]
    if lull:
        t_rel = float(lull["t1"])
    else:
        t_rel = g["t_release"]
    rule = dict(rcfg["rule"])
    m = rescue_measures(res, t_on=float(t_on) if t_on is not None else float(b["t_s"]) + 600.0, t_end=H, t_rel=t_rel,
                        uncached_ref=job["uncached_ref"], valid_window_s=rule["valid_window_s"],
                        valid_outstanding_above=rule["valid_outstanding_above"], release_by=rule["release_by_s"],
                        post_delay_s=rule["post_delay_s"], win_s=rule["win_s"], post_win_min=rule["post_win_min"],
                        post_all_min=rule["post_all_min"], uncached_frac_max=rule["uncached_frac_max"], relapse_below=rule["relapse_below"],
                        rec_hit_above=rule["rec_hit_above"], rec_outstanding_below=rule["rec_outstanding_below"],
                        end_window_s=rule["end_window_s"],
                        cap=int(control.cap) if (control.mode == "rescue" and control.cap is not None and not lull) else None)
    row.update({"t_engage": g["t_engage"], "t_release_ctl": g["t_release"], "n_pauses": g["n_pauses"], "n_resumes": g["n_resumes"],
                "n_paused_end": g["n_paused_end"], "pause_session_h": g["pause_s_total"] / 3600.0, "n_gated_arrivals": g["n_gated_arrivals"],
                "gate_session_h": g["gate_wait_s_total"] / 3600.0, "n_gated_end": g["n_gated_end"], "cap_min": g["cap_min"],
                "n_cap_changes": max(0, len(res["cap_trace"]) - 1), "cap_traj": _cap_traj(res["cap_trace"]),
                "conservation_ok": g["conservation_ok"], "n_shed": g["n_shed"] + n_shed_lull, "n_arrived": res["gate"]["n_arrived"],
                "n_sessions_done": res["gate"]["n_sessions_done"], "t_on_rule": t_on})
    row.update(m)
    row["t_rec_after_on"] = (m["t_rec"] - t_on) if (m["t_rec"] is not None and t_on is not None) else None
    win = res["windows"]
    W = float(cfg["metrics"]["window_s"])
    tb = float(b["t_s"])
    row["queue_session_h_after_burst"] = float(sum(w["queue_mean"] * W for w in win if w["t_start"] >= tb)) / 3600.0
    lat = [w["lat_p50_s"] for w in win if w["t_start"] >= tb and w["lat_p50_s"] == w["lat_p50_s"]]
    row["lat_p50_median_after_burst_s"] = float(np.median(lat)) if lat else float("nan")   # ENGINE latency: no gate / pause wait
    row.update(session_costs(res["gate"]["sessions"], arrivals_planned, tb, H))
    if job["kind"] == "exact":
        row["_trace"] = res["gate"]["trace"]
    return row


def session_costs(sessions, arrivals_planned, t_burst: float, horizon: float) -> Dict[str, Any]:
    """User-facing costs from the simulator's per-session rows (sid, arrival, completion or NaN, delay, shed): sessions delayed
    (admission wait + pauses, open ones counted to the end) by more than 60 / 300 / 600 s, delay session-hours, sessions still gated or
    paused at the end, the completed share of all planned sessions, and the [t_b, t_b + 1800) arrival cohort's completed share and
    median duration (arrival -> last turn done, waits included). Sessions removed by a lull or shed at the gate count as planned and not
    completed."""
    a = np.asarray(sessions, dtype=float).reshape(-1, 5)
    arr, tdone, delay, shed = a[:, 1], a[:, 2], a[:, 3], a[:, 4] > 0
    out: Dict[str, Any] = {f"sessions_delayed_gt_{int(x)}s": int((delay > x).sum()) for x in DELAY_THRESHOLDS_S}
    out["delay_session_h"] = float(delay.sum() / 3600.0)
    planned = np.asarray(arrivals_planned, dtype=float)
    planned = planned[planned < horizon]
    done = np.isfinite(tdone)
    out["completed_frac"] = float(done.sum() / len(planned)) if len(planned) else float("nan")
    co = (arr >= t_burst) & (arr < t_burst + COHORT_S) & ~shed
    n_co = int(((planned >= t_burst) & (planned < t_burst + COHORT_S)).sum())
    dur = tdone[co & done] - arr[co & done]
    out["cohort_sessions_planned"] = n_co
    out["cohort_completed_frac"] = float((co & done).sum() / n_co) if n_co else float("nan")
    out["cohort_duration_median_s"] = float(np.median(dur)) if len(dur) else float("nan")
    return out


# ======================================================================= aggregation
def _band(x: pd.Series) -> Tuple[float, float, float]:
    v = pd.to_numeric(x, errors="coerce").dropna()
    return (float(v.min()), float(v.median()), float(v.max())) if len(v) else (math.nan, math.nan, math.nan)


def cell_table(runs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cell, mult), d in runs[runs["kind"] == "sim"].groupby(["cell", "mult"], sort=False):
        n = len(d)
        r = {"cell": cell, "group": d["group"].iloc[0], "pool": d["pool"].iloc[0], "mult": mult, "lam": d["lam"].iloc[0], "n_seeds": n,
             "n_valid": int(d["VALID"].sum()), "n_engaged": int(d["t_engage"].notna().sum()), "n_released": int(d["RELEASED"].sum()),
             "n_post_good": int(d["POST_GOOD"].sum()), "n_cured": int((d["RELEASED"] & d["POST_GOOD"]).sum()),
             "n_rescued": int(d["RESCUED"].sum()), "n_relapse": int(d["RELAPSE"].sum()),
             "n_end_recovered": int(d["end_recovered"].sum()), "n_stuck": int(d["STUCK"].sum()), "n_conservation_ok": int(d["conservation_ok"].sum()),
             "n_trapped_at_rel": int((d["trapped_at_rel"] & d["t_rel"].notna()).sum()),
             "n_relapse_after_good": int((d["RELAPSE"] & ~d["trapped_at_rel"]).sum())}
        for col in ("t_engage", "t_rel", "t_rec", "t_rec_after_on", "max_gate_paused", "n_pauses", "n_shed", "pause_session_h", "gate_session_h",
                    "queue_session_h_after_burst", "cap_min", "end_hit_all", "end_outstanding", "post_fu", "post_uncached_rel", "fu_valid",
                    "outstanding_at_on", "lat_p50_median_after_burst_s", "sessions_delayed_gt_60s", "sessions_delayed_gt_300s",
                    "sessions_delayed_gt_600s", "delay_session_h", "n_gated_end", "n_paused_end", "completed_frac", "cohort_completed_frac",
                    "cohort_duration_median_s", "fu_pre_rel", "rel_after_last_bound_s", "post_rel_frac_in_system_ge_cap",
                    "post_rel_max_in_system"):
            lo, med, hi = _band(d[col])
            r[f"{col}_min"], r[f"{col}_med"], r[f"{col}_max"] = lo, med, hi
        rows.append(r)
    return pd.DataFrame(rows)


def _fmt(x: Any, nd: int = 0) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "-"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else "no"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{x:.{nd}f}"


def summary_md(out: Path, runs_by_mode: Dict[str, pd.DataFrame], cells_by_mode: Dict[str, pd.DataFrame], meta: Dict[str, Any]) -> str:
    L = [f"# r11 bundle 3 (rescue) simulator predictions: {out.name}", "",
         f"git at start: {meta['git'].get('commit')} dirty={meta['git'].get('dirty')}; file sha256s in meta.json.", ""]
    for mode, ct in cells_by_mode.items():
        L += [f"## {mode}", "", "cured = released by 7200 AND post-good (rule b and c without the VALID gate a; the AIMD and lull rows)", "",
              "| cell | x | seeds | VALID | engaged | released | cured | RESCUED | relapse | end recovered | STUCK | t_rel min/med/max | t_rec-t_on med [min,max] | "
              "max gate+paused med | shed med | pauses med | cap_min min |", "|" + "---|" * 17]
        for _, r in ct.iterrows():
            L.append(f"| {r['cell']} | {r['mult']:g} | {r['n_seeds']} | {r['n_valid']} | {r['n_engaged']} | {r['n_released']} | {r['n_cured']} | "
                     f"{r['n_rescued']} | {r['n_relapse']} | "
                     f"{r['n_end_recovered']} | {r['n_stuck']} | {_fmt(r['t_rel_min'])}/{_fmt(r['t_rel_med'])}/{_fmt(r['t_rel_max'])} | "
                     f"{_fmt(r['t_rec_after_on_med'])} [{_fmt(r['t_rec_after_on_min'])}, {_fmt(r['t_rec_after_on_max'])}] | "
                     f"{_fmt(r['max_gate_paused_med'])} | {_fmt(r['n_shed_med'])} | {_fmt(r['n_pauses_med'])} | {_fmt(r['cap_min_min'])} |")
        L += ["", "User-facing costs (medians over the simulator seeds; delay = admission wait + pauses per session, open ones counted to "
              "8,700 s; latency = ENGINE latency, which excludes the gate and pause waits; cohort = sessions arriving in [t_b, t_b + 1800), "
              "shed sessions counted as not completed; trapped at release = FU-hit < 0.2 over the 300 s before the release / lull end):", "",
              "| cell | x | shed | delayed > 60 / 300 / 600 s | delay session-h | gated + paused at end | completed share | cohort completed | "
              "cohort median duration s | engine p50 latency s | trapped at release | relapse after a good release |", "|" + "---|" * 12]
        for _, r in ct.iterrows():
            L.append(f"| {r['cell']} | {r['mult']:g} | {_fmt(r['n_shed_med'])} | {_fmt(r['sessions_delayed_gt_60s_med'])} / "
                     f"{_fmt(r['sessions_delayed_gt_300s_med'])} / {_fmt(r['sessions_delayed_gt_600s_med'])} | {_fmt(r['delay_session_h_med'], 1)} | "
                     f"{_fmt(r['n_gated_end_med'] + r['n_paused_end_med'])} | {_fmt(r['completed_frac_med'], 3)} | {_fmt(r['cohort_completed_frac_med'], 3)} | "
                     f"{_fmt(r['cohort_duration_median_s_med'])} | {_fmt(r['lat_p50_median_after_burst_s_med'], 1)} | {r['n_trapped_at_rel']} | "
                     f"{r['n_relapse_after_good']} |")
        ex = runs_by_mode[mode]
        ex = ex[ex["kind"] == "exact"]
        if len(ex):
            L += ["", "Exact client plans:", "", "| cell | x | seed | plan sha256 (12) | VALID | t_engage | t_rel | RESCUED | relapse | t_rec | pauses | "
                  "max gate+paused | end hit | end outstanding |", "|" + "---|" * 14]
            for _, r in ex.iterrows():
                L.append(f"| {r['cell']} | {r['mult']:g} | {r['seed']} | {str(r.get('plan_sha256', ''))[:12]} | {_fmt(r['VALID'])} | {_fmt(r['t_engage'])} | "
                         f"{_fmt(r['t_rel'])} | {_fmt(r['RESCUED'])} | {_fmt(r['RELAPSE'])} | {_fmt(r['t_rec'])} | {_fmt(r['n_pauses'])} | "
                         f"{_fmt(r['max_gate_paused'])} | {_fmt(r['end_hit_all'], 3)} | {_fmt(r['end_outstanding'], 1)} |")
        L.append("")
    return "\n".join(L)


def committed_plans() -> List[Tuple[str, str, pd.DataFrame]]:
    """(run dir, sha256, plan frame) of every committed E2 plan.csv under results/nova/e2_* (inputs only; nothing else in those dirs is read)."""
    out = []
    for p in sorted((REPO / "results" / "nova").glob("e2_*/**/plan.csv")):
        out.append((p.parent.relative_to(REPO).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest(), pd.read_csv(p, float_precision="round_trip")))
    return out


def plan_frame(plan) -> pd.DataFrame:
    return pd.DataFrame({"sid": [sp.sid for sp in plan], "origin": [sp.origin for sp in plan], "idx": [sp.idx for sp in plan],
                         "arrival_s": [sp.arrival_s for sp in plan], "n_turns": [sp.n_turns for sp in plan],
                         "tool_time_total_s": [float(sum(sp.tool_times_s)) for sp in plan]})


def match_committed(pf: pd.DataFrame, sha: str, committed) -> Dict[str, Any]:
    """Committed plans equal to ``pf``: byte-identical (sha256), or equal in sid / origin / idx / arrival_s / n_turns exactly with the tool-time
    totals within 1e-12 relative (numpy 1.26 here vs numpy 2.x on Nova differ in the last bits of the exponential draws)."""
    exact, close, rel = [], [], []
    for d, h, cf_ in committed:
        if h == sha:
            exact.append(d)
            continue
        if len(cf_) != len(pf) or not (cf_["origin"].astype(str).to_numpy() == pf["origin"].to_numpy()).all():
            continue
        same = all((cf_[c].to_numpy() == pf[c].to_numpy()).all() for c in ("sid", "idx", "arrival_s", "n_turns"))
        if same:
            a, b = cf_["tool_time_total_s"].to_numpy(dtype=float), pf["tool_time_total_s"].to_numpy(dtype=float)
            r = float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-9))) if len(pf) else 0.0
            if r <= 1e-12:
                close.append(d)
                rel.append(r)
    return {"committed_byte_identical": " ".join(exact), "committed_equal_up_to_tool_ulp": " ".join(close),
            "max_rel_tool_total_diff": max(rel) if rel else (0.0 if exact else float("nan"))}


def file_sha(rel: str) -> Optional[str]:
    p = REPO / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="configs/r11_predict_rescue.yaml")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quick", action="store_true", help="2 simulator seeds and 1 exact seed per cell (plumbing check)")
    ap.add_argument("--modes", nargs="*", default=None)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--out-root", default="results")
    args = ap.parse_args(argv)
    if not (1 <= args.workers <= 6):
        raise SystemExit("--workers must be in 1..6")
    t_start = time.time()
    git0 = git_info(REPO)
    cfg = probe.load_probe_config(str(REPO / args.config), REPO)
    rcfg = cfg["r11_rescue"]
    modes = args.modes or list(rcfg["batching_modes"])
    cells = args.cells or list(rcfg["cells"])
    jobs = build_jobs(cfg, rcfg, modes, cells, args.quick)
    out = new_result_dir(args.out_root, EXPERIMENT + ("_quick" if args.quick else ""))
    (out / "config.yaml").write_text((REPO / args.config).read_text())
    (out / "config_effective.yaml").write_text(yaml.safe_dump(sanitize({k: v for k, v in cfg.items() if not k.startswith("_")}), sort_keys=False))
    print(f"{len(jobs)} runs -> {out}", flush=True)
    dep = [j for j in jobs if j["lull"] and j["lull"].get("t1_from")]
    first = [j for j in jobs if not (j["lull"] and j["lull"].get("t1_from"))]
    rows = _run_all([(cfg, rcfg, j) for j in first], args.workers)
    if dep:
        resolve_lull_ends(dep, rows)
        rows += _run_all([(cfg, rcfg, j) for j in dep], args.workers)
    committed = committed_plans()
    plan_rows = []
    runs_by_mode, cells_by_mode = {}, {}
    for mode in modes:
        rr = [r for r in rows if r["mode"] == mode]
        traces = []
        for r in rr:
            pf = r.pop("_plan", None)
            tr = r.pop("_trace", None)
            if tr is not None:
                for row in tr:
                    traces.append({"cell": r["cell"], "mult": r["mult"], "seed": r["seed"], **dict(zip(
                        ["t", "in_system", "gate", "paused", "n_wait", "running", "cap", "H", "outstanding"], row))})
                if mode == modes[0]:
                    plan_rows.append({"cell": r["cell"], "pool": r["pool"], "mult": r["mult"], "seed": r["seed"], "burst": r["burst"],
                                      "plan_sha256": r["plan_sha256"], "n_sessions": r["n_sessions_planned"],
                                      **match_committed(pf, r["plan_sha256"], committed)})
        df = pd.DataFrame(rr)
        df.to_csv(out / f"runs_{mode}.csv", index=False)
        if traces:
            pd.DataFrame(traces).to_csv(out / f"exact_traces_{mode}.csv", index=False)
        ct = cell_table(df)
        ct.to_csv(out / f"cells_{mode}.csv", index=False)
        runs_by_mode[mode], cells_by_mode[mode] = df, ct
    if plan_rows:
        pd.DataFrame(plan_rows).drop_duplicates(["pool", "mult", "seed", "burst", "plan_sha256"]).to_csv(out / "plan_check.csv", index=False)
    t1 = time.time()
    meta = {"experiment": EXPERIMENT, "status": "done", "argv": sys.argv if argv is None else argv, "git": git0,
            "file_sha256": {f: file_sha(f) for f in TRACKED_FILES}, "versions": env_versions(), "hostname": socket.gethostname(),
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t_start)),
            "end_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t1)), "wall_s": t1 - t_start, "n_runs": len(rows),
            "quick": bool(args.quick), "workers": args.workers, "modes": modes, "cells": cells,
            "blindness": "no rescue run (GPU or mock with the rescue gate) existed when this ran; only committed BURST plan.csv files were read "
                         "from results/nova (to check the rebuilt client plans)"}
    (out / "meta.json").write_text(json.dumps(sanitize(meta), indent=2, default=str))
    (out / "summary.md").write_text(summary_md(out, runs_by_mode, cells_by_mode, meta))
    print((out / "summary.md").read_text())
    print("result dir:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
