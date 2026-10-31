"""Round 11, S1 bundle 1: blind simulator predictions for B1 (burst n = 25 / 100 at 1.65 x lambda_ref) and E0F (from empty at 2.0 / 2.5 x, seeds 3-5).

    PYTHONPATH="src;." python experiments/r11_predict_basin.py run   [--spec configs/r11_predict_basin.yaml] [--workers 6] [--quick]
    PYTHONPATH="src;." python experiments/r11_predict_basin.py plans [--spec ...]          # only the plan reproduction checks

What it does (nothing in src/ is edited; this file only assembles inputs and classifies outputs):
  * builds every run's sessions from the CLIENT's plan: ``agentload.workload.build_open_plan`` on the agentload config the real job uses
    (configs/agentload_e2_burst.yaml with arrivals.burst.n = 25 / 100 / 200 or burst = null; configs/agentload_e0_cap.yaml), with the job's seed,
    rate (mult x lambda_ref), burst and duration; the plan is converted to the simulator's ``SessionSpecs`` and passed to ``prefixmeta.sim.simulate``
    (the ``specs=`` argument), so for the engine seeds the simulator serves the exact arrival times, turn counts and tool times the real jobs send.
    The burst size is set in this plan (the ``arrivals.burst.n`` of the client config), which is how the B1 jobs set it (E2_CONFIG); the probe
    runner is not used, so no probe override is needed.
  * first reproduces the plan.csv of committed real runs (n = 200 / n = 0 at 1.65 x, E0b seed 0 at 2.0 / 2.5 x): arrival times and turn counts
    bit for bit, tool-time totals to < 1e-9 s (libm last-bit differences between Nova and the PC), and checks that the n = 100
    and n = 25 plans have the n = 200 plan's base sessions and a subset of its burst times;
  * engine = the round-6 calibrated engine inherited from configs/r6_predict.yaml (asserted), mixed (PRIMARY) and separate_prefill_priority (SECONDARY);
  * classifies each B1-type run with the FROZEN endpoints of configs/r11_basin_predict.yaml (STUCK, simulated trap_v2 label, GOOD) and each E0b run
    with the registered from-empty stability rule; writes small CSV summaries + meta.json to results/r11_predict_basin/<ts>/ (full per-window data
    to its full/ subdirectory, not meant to be committed).

Simulator analogues of the engine-side quantities (all over the 100 s simulator windows; declared here, before any run):
  hit_eval        hits / admitted turns over the windows of W = [5700, 8700) (simulator hits are attributed by admission time, the engine's by completion)
  token rate      mean prefill tokens / s over W (cache-hit turns count their new tokens: the "uncached prefill tokens" of the engine)
  crit (a)        |token rate / R_miss - 1| <= 0.15, R_miss = the simulator's own all-miss token rate of the same batching mode (r6 B1)
  backlog slope   OLS slope over W of the sessions in the system (arrived minus completed, incl. the gate), evaluated at window midpoints as the
                  mean of the window-end counts; crit (b): slope > 0.5 (lambda - lambda_ref), lambda = mult x lambda_ref (the resolved rate)
  RECOVERED       hit over the last 300 s > 0.8 AND (waiting queue + gate) mean over the last 300 s < 20 (the engine's "outstanding" also counts
                  running requests, which the simulator windows do not record; a few requests in the good state)
  E0b stable      not stopped early AND queue + gate mean of the last 100 s window < 50 AND OLS rise of the 100 s backlog means over the last
                  min(5000, T / 2) = 1500 s <= 10
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import copy
import gzip
import hashlib
import json
import math
import multiprocessing as mp
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
for p in (str(REPO / "src"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agentload.config import config_from_dict, resolve_rate  # noqa: E402
from agentload.workload import SessionPlan, build_open_plan  # noqa: E402
from prefixmeta.metrics import trend_rise  # noqa: E402
from prefixmeta.probe import load_probe_config  # noqa: E402
from prefixmeta.sim import RunSpec, deep_update, simulate  # noqa: E402
from prefixmeta.workload import ArrivalPlan, SessionSpecs  # noqa: E402

DEFAULT_SPEC = "configs/r11_predict_basin.yaml"
MAX_WORKERS = 6
NAN = float("nan")


# ======================================================================= client plans -> simulator sessions
def client_config(agentload_cfg: str, seed: int, mult: float, lambda_ref: float, duration_s: float, burst_n: int,
                  t_burst: float = 1200.0, width_s: float = 60.0):
    """The agentload Config the real job builds (run_gen with --seed, --set arrivals.rate_mult / lambda_ref / run.duration_s, and the burst of the
    cell's E2 config, or arrivals.burst = null for NOBURST / E0b)."""
    raw = yaml.safe_load((REPO / agentload_cfg).read_text())
    raw["arrivals"]["rate_mult"] = float(mult)
    raw["arrivals"]["lambda_ref"] = float(lambda_ref)
    if "uncached_tokens_ref" in raw["arrivals"]:
        raw["arrivals"]["uncached_tokens_ref"] = None          # analysis reference only; unused by the generator
    if burst_n > 0:
        raw["arrivals"]["burst"] = {"n": int(burst_n), "t_s": float(t_burst), "width_s": float(width_s)}
    else:
        raw["arrivals"]["burst"] = None
    raw["run"]["seed"] = int(seed)
    raw["run"]["duration_s"] = float(duration_s)
    raw.setdefault("meta", {})["engine_label"] = "sim-r11-predict"
    return config_from_dict(raw)


def client_plan(agentload_cfg: str, seed: int, mult: float, lambda_ref: float, duration_s: float, burst_n: int,
                t_burst: float = 1200.0, width_s: float = 60.0) -> Tuple[List[SessionPlan], float]:
    cfg = client_config(agentload_cfg, seed, mult, lambda_ref, duration_s, burst_n, t_burst, width_s)
    rate = resolve_rate(cfg.arrivals)
    return build_open_plan(int(seed), cfg.workload, cfg.arrivals, cfg.run.duration_s, rate, []), float(rate)


def plan_to_specs(plan: Sequence[SessionPlan]) -> SessionSpecs:
    """SessionSpecs (sorted by arrival; session id = index) holding exactly the plan's arrival times, turn counts and tool times."""
    arrival = np.array([sp.arrival_s for sp in plan], dtype=float)
    if len(arrival) > 1 and np.any(np.diff(arrival) < 0):
        raise ValueError("client plan is not sorted by arrival")
    nt = np.array([sp.n_turns for sp in plan], dtype=np.int64)
    if np.any(nt < 1):
        raise ValueError("a session with < 1 turn")
    for sp in plan:
        if len(sp.tool_times_s) != sp.n_turns - 1:
            raise ValueError(f"session {sp.sid}: {len(sp.tool_times_s)} tool times for {sp.n_turns} turns")
    flat = np.array([t for sp in plan for t in sp.tool_times_s], dtype=float)
    off = np.concatenate([[0], np.cumsum(nt - 1)[:-1]]).astype(np.int64) if len(nt) else np.zeros(0, np.int64)
    return SessionSpecs(arrival=arrival, n_turns=nt, tool_off=off, tool_flat=flat)


# ======================================================================= one simulation (process-pool worker)
def _work(job: Dict[str, Any]) -> Dict[str, Any]:
    cfg = job["cfg"]
    plan, rate = client_plan(job["agentload_config"], job["seed"], job["mult"], job["lambda_ref"], job["duration_s"], job["burst_n"],
                             job.get("t_burst", 1200.0), job.get("width_s", 60.0))
    specs = plan_to_specs(plan)
    H = float(job["duration_s"])
    rs = RunSpec(exp=f"r11_{job['kind']}", policy=job["policy"], seed=int(job["seed"]), horizon_s=H, variant=job["variant"],
                 plan=ArrivalPlan(kind="constant", horizon_s=H, rate=rate), stop_backlog_above=job.get("stop_backlog_above"),
                 engine_overrides={"batching": job["batching"]}, meta={})
    res = simulate(cfg, rs, specs=specs)
    W = float(cfg["metrics"]["window_s"])
    nwin = int(math.floor(H / W + 1e-9))
    edges = W * np.arange(nwin + 1)
    base = np.array([sp.arrival_s for sp in plan if sp.origin == "base"])
    burst = np.array([sp.arrival_s for sp in plan if sp.origin == "burst"])
    return {"job": {k: v for k, v in job.items() if k != "cfg"}, "rate": rate, "n_base": int(len(base)), "n_burst": int(len(burst)),
            "arr_per_window": np.histogram(np.concatenate([base, burst]), bins=edges)[0].tolist(),
            "summary": res["summary"], "windows": res["windows"], "btrace": res["btrace"]}


def run_jobs(jobs: List[Dict[str, Any]], workers: int) -> List[Dict[str, Any]]:
    if workers <= 1:
        return [_work(j) for j in jobs]
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(_work, jobs, chunksize=1))


# ======================================================================= classification (frozen endpoints)
def _sel(w: pd.DataFrame, t0: float, t1: float) -> pd.DataFrame:
    return w[(w["t_start"] >= t0 - 1e-9) & (w["t_end"] <= t1 + 1e-9)].sort_values("t_start")


def _hit(s: pd.DataFrame) -> float:
    a = float(s["admitted_turns"].sum())
    return float(s["hits"].sum()) / a if a else NAN


def basin_classify(r: Dict[str, Any], ep: dict, R_miss: float, R_reg: float) -> Dict[str, Any]:
    b1, tv = ep["b1"], ep["b1"]["trap_v2"]
    w = pd.DataFrame(r["windows"]).sort_values("t_start").reset_index(drop=True)
    W = float(w["t_end"].iloc[0] - w["t_start"].iloc[0])
    lam = float(r["rate"])
    lam_ref = float(b1["lambda_ref"])
    t0, t1 = float(b1["window_s"][0]), float(b1["window_s"][1])
    end = float(r["summary"]["sim_end_s"])
    # sessions in the system: arrived minus completed at window ends; window "bin mean" = mean of its two end counts
    arr = np.asarray(r["arr_per_window"][:len(w)], dtype=float)
    done = np.rint(w["sessions_per_s"].to_numpy(dtype=float) * W)
    n_end = np.cumsum(arr) - np.cumsum(done)
    n_start = np.concatenate([[0.0], n_end[:-1]])
    w["n_sys_mid"] = 0.5 * (n_start + n_end)
    w["backlog_qg"] = w["queue_mean"] + w["gate_mean"]
    s = _sel(w, t0, t1)
    x = ((s["t_start"] + s["t_end"]) / 2.0).to_numpy(dtype=float)
    slope = float(np.polyfit(x, s["n_sys_mid"].to_numpy(dtype=float), 1)[0]) if len(s) >= 3 else NAN
    slope_qg = float(np.polyfit(x, s["backlog_qg"].to_numpy(dtype=float), 1)[0]) if len(s) >= 3 else NAN
    hit_eval = _hit(s)
    tok = float(s["prefill_tok_per_s"].mean()) if len(s) else NAN
    thr = float(tv["slope_frac"]) * (lam - lam_ref)
    crit_a = bool(tok == tok and abs(tok / R_miss - 1.0) <= float(tv["rate_tolerance"]))
    crit_a_reg = bool(tok == tok and abs(tok / R_reg - 1.0) <= float(tv["rate_tolerance"]))
    crit_b = bool(slope == slope and slope > thr)
    ew = float(tv["end_window_s"])
    se = _sel(w, end - ew, end)
    hit_end = _hit(se)
    outst_end = float(se["backlog_qg"].mean()) if len(se) else NAN
    recovered = bool(hit_end == hit_end and hit_end > float(tv["recovered_hit_above"]) and outst_end == outst_end
                     and outst_end < float(tv["recovered_backlog_below"]))
    trapped = bool(crit_a and crit_b and lam > lam_ref)
    draining = bool(slope == slope and slope < 0)
    state = "trapped" if trapped else "recovered" if recovered else "draining" if draining else "indeterminate"
    stuck = bool(hit_eval == hit_eval and hit_eval < float(b1["stuck"]["trap_hit_below"]))
    good = bool(recovered or (hit_eval == hit_eval and hit_eval > float(tv["recovered_hit_above"]) and slope == slope and slope <= thr))
    # descriptive event times
    tb = float(r["job"].get("t_burst", 1200.0))
    post = w[(w["t_start"] >= tb - 1e-9) & (w["hit_rate"] < float(b1["stuck"]["trap_hit_below"]))]
    onset = float(post["t_end"].iloc[0]) if len(post) else NAN
    release = NAN
    if onset == onset:
        rel = w[(w["t_start"] >= onset - 1e-9) & (w["hit_rate"] > float(tv["recovered_hit_above"]))]
        release = float(rel["t_end"].iloc[0]) if len(rel) else NAN
    pre = _sel(w, 0.0, tb)
    return {"lam": lam, "hit_eval": hit_eval, "token_rate": tok, "token_ratio": tok / R_miss, "token_ratio_registered_ref": tok / R_reg,
            "crit_a": crit_a, "crit_a_registered_ref": crit_a_reg, "backlog_slope": slope, "slope_threshold": thr, "crit_b": crit_b,
            "backlog_slope_queue_gate": slope_qg, "sessions_in_system_eval_mean": float(s["n_sys_mid"].mean()) if len(s) else NAN,
            "queue_gate_eval_mean": float(s["backlog_qg"].mean()) if len(s) else NAN, "hit_end": hit_end, "outstanding_end_qg": outst_end,
            "trapped": trapped, "recovered": recovered, "draining": draining, "state": state, "stuck": stuck, "good": good,
            "trap_onset_s": onset, "release_s": release, "max_queue_gate": float(w["backlog_qg"].max()), "hit_pre_burst": _hit(pre),
            "sim_end_s": end, "stopped_early": int(r["summary"]["stopped_early"])}


def e0b_classify(r: Dict[str, Any], ep: dict) -> Dict[str, Any]:
    st = ep["e0f"]["stable"]
    w = pd.DataFrame(r["windows"]).sort_values("t_start")
    s = r["summary"]
    end = float(s["sim_end_s"])
    Wt = min(float(st["stable_trend_window_s"]), end / 2.0)
    rise = trend_rise(r["btrace"], end - Wt, end)
    last = w.iloc[-1] if len(w) else None
    fq = float(last["queue_mean"] + last["gate_mean"]) if last is not None else NAN
    stopped = bool(s["stopped_early"])
    stable = bool((not stopped) and fq == fq and fq < float(st["stable_final_queue_below"]) and rise == rise
                  and rise <= float(st["stable_trend_max_rise"]))
    # cross-check: the round-6 B2 / probe rule (instantaneous final backlog)
    stable_r6 = bool((not stopped) and float(s["final_backlog"]) < float(st["stable_final_queue_below"]) and rise == rise
                     and rise <= float(st["stable_trend_max_rise"]))
    tail = _sel(w, end - Wt, end)
    return {"lam": float(r["rate"]), "stable": stable, "stable_r6_rule": stable_r6, "final_queue_lastwin": fq,
            "final_backlog_inst": float(s["final_backlog"]), "trend_rise": rise, "stopped_early": int(stopped),
            "stop_time": float(s["stop_time"]), "tail_hit": _hit(tail), "max_queue": float(s["max_queue"]), "sim_end_s": end}


# ======================================================================= plan checks
def plan_checks(rb: dict, repo: Path) -> pd.DataFrame:
    lam_ref = float(rb["lambda_ref"])
    rows = []
    for c in rb["plan_checks"]:
        d = repo / c["dir"]
        ref = pd.read_csv(d / "plan.csv", float_precision="round_trip")   # exact float round trip
        kind = c["kind"]
        acfg = rb["basin"]["agentload_config"] if kind == "basin" else rb["e0b"]["agentload_config"]
        dur = rb["basin"]["duration_s"] if kind == "basin" else rb["e0b"]["duration_s"]
        plan, rate = client_plan(acfg, int(c["seed"]), float(c["mult"]), lam_ref, float(dur), int(c["burst_n"]),
                                 rb["basin"]["t_burst_s"], rb["basin"]["width_s"])
        mine = pd.DataFrame([{"sid": sp.sid, "origin": sp.origin, "idx": sp.idx, "arrival_s": sp.arrival_s, "n_turns": sp.n_turns,
                              "tool_time_total_s": float(sum(sp.tool_times_s))} for sp in plan])
        meta = json.loads((d / "meta.json").read_text())
        same_len = len(mine) == len(ref)
        exact = bool(same_len and (mine["sid"].to_numpy() == ref["sid"].to_numpy()).all()
                     and (mine["origin"].to_numpy() == ref["origin"].to_numpy()).all()
                     and (mine["idx"].to_numpy() == ref["idx"].to_numpy()).all()
                     and (mine["n_turns"].to_numpy() == ref["n_turns"].to_numpy()).all()
                     and np.array_equal(mine["arrival_s"].to_numpy(), ref["arrival_s"].to_numpy()))
        # Tool times are Exp draws (a log in NumPy's sampler): the Linux (Nova) and Windows (PC) libm differ in the last bit of some draws, so the
        # per-session tool-time totals agree to ~1e-13 s, not bit for bit. Arrival times (uniforms) and turn counts are bit-identical.
        tool_diff = float(np.max(np.abs(mine["tool_time_total_s"].to_numpy() - ref["tool_time_total_s"].to_numpy()))) if same_len else NAN
        tool_bits = int((mine["tool_time_total_s"].to_numpy() != ref["tool_time_total_s"].to_numpy()).sum()) if same_len else -1
        max_dt = float(np.max(np.abs(mine["arrival_s"].to_numpy() - ref["arrival_s"].to_numpy()))) if same_len else NAN
        rows.append({"dir": c["dir"], "kind": kind, "seed": c["seed"], "mult": c["mult"], "burst_n": c["burst_n"], "n_sessions": len(mine),
                     "n_sessions_committed": len(ref), "rate": rate, "rate_committed": meta.get("resolved_rate_sessions_per_s"),
                     "rate_equal": rate == meta.get("resolved_rate_sessions_per_s"), "max_abs_arrival_diff_s": max_dt,
                     "arrivals_turns_exact": exact, "tool_total_max_abs_diff_s": tool_diff, "tool_total_n_last_bit_diff": tool_bits,
                     "exact": bool(exact and tool_diff == tool_diff and tool_diff < 1e-9)})
    return pd.DataFrame(rows)


def basin_subset_checks(rb: dict) -> pd.DataFrame:
    """B1 plan test: the n = 100 / 25 plans carry the n = 200 plan's base sessions unchanged and a subset of its burst times."""
    b = rb["basin"]
    rows = []
    for sd in b["engine_seeds"]:
        p200, _ = client_plan(b["agentload_config"], sd, b["lambda_mult"], rb["lambda_ref"], b["duration_s"], 200, b["t_burst_s"], b["width_s"])
        base200 = [(sp.arrival_s, sp.n_turns, sp.tool_times_s) for sp in p200 if sp.origin == "base"]
        bt200 = set(sp.arrival_s for sp in p200 if sp.origin == "burst")
        for n in b["burst_ns"]:
            pn, _ = client_plan(b["agentload_config"], sd, b["lambda_mult"], rb["lambda_ref"], b["duration_s"], n, b["t_burst_s"], b["width_s"])
            basen = [(sp.arrival_s, sp.n_turns, sp.tool_times_s) for sp in pn if sp.origin == "base"]
            btn = [sp.arrival_s for sp in pn if sp.origin == "burst"]
            cell_cfg = f"configs/agentload_e2_burst_n{n}.yaml"          # the B1 job's E2_CONFIG (plan item B1), if it exists in the tree
            if (REPO / cell_cfg).exists():
                cc = yaml.safe_load((REPO / cell_cfg).read_text())
                pc_, _ = client_plan(cell_cfg, sd, b["lambda_mult"], rb["lambda_ref"], b["duration_s"], int(cc["arrivals"]["burst"]["n"]),
                                     float(cc["arrivals"]["burst"]["t_s"]), float(cc["arrivals"]["burst"]["width_s"]))
                same_cell = bool(int(cc["arrivals"]["burst"]["n"]) == n and pc_ == pn)
            else:
                same_cell = None
            rows.append({"seed": sd, "burst_n": n, "plan_equals_cell_config_plan": same_cell, "cell_config": cell_cfg,
                         "base_identical_to_n200": basen == base200, "n_burst": len(btn),
                         "burst_times_subset_of_n200": set(btn) <= bt200,
                         "burst_window": [min(btn), max(btn)] if btn else None, "first_prompt_tokens_of_burst": 2000 * len(btn)})
    return pd.DataFrame(rows)


# ======================================================================= provenance
def _git(args: List[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:      # pragma: no cover
        return f"<git failed: {e}>"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


SIM_INPUTS = ["src/prefixmeta", "src/agentload/workload.py", "src/agentload/config.py", "configs/r6_predict.yaml", "configs/prefix_meta_r5.yaml",
              "configs/prefix_meta.yaml", "configs/agentload_e2_burst.yaml", "configs/agentload_e0_cap.yaml"]


def provenance(spec: Path, ep_path: Path) -> Dict[str, Any]:
    files = {}
    for rel in SIM_INPUTS:
        p = REPO / rel
        for f in (sorted(p.glob("*.py")) if p.is_dir() else [p]):
            files[str(f.relative_to(REPO)).replace("\\", "/")] = sha256(f)
    extra = [REPO / f"configs/agentload_e2_burst_n{n}.yaml" for n in (25, 100)]
    for f in (Path(__file__).resolve(), spec, ep_path, *[e for e in extra if e.exists()]):
        files[str(f.relative_to(REPO)).replace("\\", "/")] = sha256(f)
    sim_dirty = _git(["status", "--porcelain", "--", *SIM_INPUTS])
    return {"git_head": _git(["rev-parse", "HEAD"]), "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "git_status_porcelain": _git(["status", "--porcelain"]).splitlines(),
            "simulation_inputs_clean_vs_head": sim_dirty == "", "simulation_inputs_status": sim_dirty.splitlines(),
            "sha256": files, "hostname": socket.gethostname(), "platform": platform.platform(), "python": sys.version,
            "numpy": np.__version__, "pandas": pd.__version__}


# ======================================================================= tables
def counts_str(sub: pd.DataFrame, col: str) -> str:
    return f"{int(sub[col].sum())}/{len(sub)}"


def basin_summary(br: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (mode, n), g in br.groupby(["mode", "burst_n"], sort=True):
        row = {"mode": mode, "burst_n": int(n)}
        for kind, sub in (("engine", g[g["seed_kind"] == "engine"].sort_values("seed")), ("extra", g[g["seed_kind"] == "extra"]),
                          ("all", g)):
            row[f"{kind}_n"] = len(sub)
            for col in ("stuck", "good", "trapped", "recovered"):
                row[f"{kind}_{col}"] = int(sub[col].sum())
            row[f"{kind}_hit_eval_mean"] = float(sub["hit_eval"].mean())
        e = g[g["seed_kind"] == "engine"].sort_values("seed")
        row["engine_states"] = " ".join(f"s{int(s)}:{st}" for s, st in zip(e["seed"], e["state"]))
        row["engine_stuck_by_seed"] = "".join("S" if x else "." for x in e["stuck"])
        row["engine_good_by_seed"] = "".join("G" if x else "." for x in e["good"])
        rows.append(row)
    return pd.DataFrame(rows)


def e0b_summary(er: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (mode, m), g in er.groupby(["mode", "mult"], sort=True):
        row = {"mode": mode, "mult": float(m)}
        for kind in ("engine", "reference", "extra"):
            sub = g[g["seed_kind"] == kind].sort_values("seed")
            row[f"{kind}_n"] = len(sub)
            row[f"{kind}_stable"] = int(sub["stable"].sum())
            if kind != "extra":
                row[f"{kind}_by_seed"] = " ".join(f"s{int(s)}:{'stable' if x else 'UNSTABLE'}" for s, x in zip(sub["seed"], sub["stable"]))
        ex = g[g["seed_kind"] == "extra"]
        row["extra_stable_frac"] = float(ex["stable"].mean()) if len(ex) else NAN
        row["extra_stable_r6_rule"] = int(ex["stable_r6_rule"].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: Sequence[str], fmt: str = "{:.4g}") -> str:
    def f(v: Any) -> str:
        if isinstance(v, (bool, np.bool_)):
            return "yes" if v else "no"
        if isinstance(v, (float, np.floating)):
            return fmt.format(v) if v == v else "nan"
        return str(v)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(f(r[c]) for c in cols) + " |")
    return "\n".join(lines)


# ======================================================================= main command
def build_jobs(cfg: dict, rb: dict, quick: bool) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    b, e = rb["basin"], rb["e0b"]
    extra_b = b["extra_seeds"][:2] if quick else b["extra_seeds"]
    extra_e = e["extra_seeds"][:2] if quick else e["extra_seeds"]
    for mode, batching in rb["modes"].items():
        for n in list(b["burst_ns"]) + list(b["reference_burst_ns"]):
            for kind, seeds in (("engine", b["engine_seeds"]), ("extra", extra_b)):
                for sd in seeds:
                    jobs.append({"cfg": cfg, "kind": "basin", "mode": mode, "batching": batching, "policy": rb["policy"], "seed": int(sd),
                                 "seed_kind": kind, "mult": float(b["lambda_mult"]), "lambda_ref": float(rb["lambda_ref"]), "burst_n": int(n),
                                 "predicted_cell": int(n) in [int(x) for x in b["burst_ns"]], "t_burst": float(b["t_burst_s"]),
                                 "width_s": float(b["width_s"]), "duration_s": float(b["duration_s"]),
                                 "agentload_config": b["agentload_config"], "variant": f"basin|n={n}|{mode}", "stop_backlog_above": None})
        for m in e["lambda_mults"]:
            for kind, seeds in (("engine", e["engine_seeds"]), ("reference", e["reference_seeds"]), ("extra", extra_e)):
                for sd in seeds:
                    jobs.append({"cfg": cfg, "kind": "e0b", "mode": mode, "batching": batching, "policy": rb["policy"], "seed": int(sd),
                                 "seed_kind": kind, "mult": float(m), "lambda_ref": float(rb["lambda_ref"]), "burst_n": 0,
                                 "duration_s": float(e["duration_s"]), "agentload_config": e["agentload_config"],
                                 "variant": f"e0b|m={m}|{mode}", "stop_backlog_above": int(e["unstable_backlog_stop"])})
    return jobs


def cmd_run(args: argparse.Namespace) -> Path:
    t_start = time.time()
    spec = (REPO / args.spec).resolve()
    cfg = load_probe_config(str(spec), REPO, args.set)
    rb = cfg["r11_basin"]
    ep_path = (REPO / rb["endpoints"]).resolve()
    ep = yaml.safe_load(ep_path.read_text())
    if ep.get("status") != "FROZEN":
        raise SystemExit(f"{ep_path}: status is not FROZEN")
    # the engine must be the round-6 calibrated engine of configs/r6_predict.yaml, unchanged
    r6 = load_probe_config(str(REPO / "configs/r6_predict.yaml"), REPO, None)
    if cfg["engine"] != r6["engine"] or cfg["workload"] != r6["workload"] or cfg["metrics"] != r6["metrics"]:
        raise SystemExit("effective engine / workload / metrics differ from configs/r6_predict.yaml")
    if float(rb["lambda_ref"]) != float(ep["b1"]["lambda_ref"]) or float(rb["lambda_ref"]) != float(ep["e0f"]["lambda_ref"]):
        raise SystemExit("lambda_ref of the spec and of the frozen endpoints differ")
    if [int(x) for x in rb["e0b"]["engine_seeds"]] != [int(x) for x in ep["e0f"]["seeds"]] or \
            [int(x) for x in rb["basin"]["engine_seeds"]] != [int(x) for x in ep["b1"]["seeds"]]:
        raise SystemExit("engine seeds of the spec and of the frozen endpoints differ")
    prov = provenance(spec, ep_path)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = REPO / args.out_root / ("r11_predict_basin" + ("_quick" if args.quick else "")) / stamp
    (out / "full").mkdir(parents=True, exist_ok=False)
    print(f"[r11] out {out}", flush=True)

    pc = plan_checks(rb, REPO)
    pc.to_csv(out / "plan_checks.csv", index=False, lineterminator="\n")
    sc = basin_subset_checks(rb)
    sc.to_csv(out / "plan_subset_checks.csv", index=False, lineterminator="\n")
    print(pc[["kind", "seed", "mult", "burst_n", "n_sessions", "rate_equal", "exact"]].to_string(), flush=True)
    print(sc.to_string(), flush=True)
    if not (pc["exact"].all() and pc["rate_equal"].all() and sc["base_identical_to_n200"].all() and sc["burst_times_subset_of_n200"].all()
            and not (sc["plan_equals_cell_config_plan"] == False).any()):      # noqa: E712  (None = cell config not in the tree)
        raise SystemExit("plan reproduction / subset check FAILED: the simulated streams would not be the engine's; nothing simulated")

    jobs = build_jobs(cfg, rb, args.quick)
    print(f"[r11] {len(jobs)} simulations on {args.workers} workers", flush=True)
    t_sim = time.time()
    results = run_jobs(jobs, args.workers)
    sim_wall = time.time() - t_sim
    print(f"[r11] simulations done in {sim_wall:.1f} s", flush=True)

    refs = rb["references"]["all_miss_tok_per_s"]
    R_reg = float(ep["b1"]["trap_v2"]["uncached_tokens_ref"])
    brow, erow, wrows = [], [], []
    for r in results:
        j = r["job"]
        ident = {"mode": j["mode"], "batching": j["batching"], "kind": j["kind"], "seed": j["seed"], "seed_kind": j["seed_kind"], "mult": j["mult"],
                 "burst_n": j["burst_n"], "n_base": r["n_base"], "n_burst": r["n_burst"], "lambda": r["rate"],
                 "realized_base_rate": r["n_base"] / j["duration_s"], "realized_base_mult": r["n_base"] / j["duration_s"] / j["lambda_ref"],
                 "base_count_z": (r["n_base"] - r["rate"] * j["duration_s"]) / math.sqrt(r["rate"] * j["duration_s"]),
                 "wall_s": float(r["summary"]["wall_s"])}
        if j["kind"] == "basin":
            brow.append({**ident, "predicted_cell": j["predicted_cell"], **basin_classify(r, ep, float(refs[j["mode"]]), R_reg)})
        else:
            erow.append({**ident, **e0b_classify(r, ep)})
        for w in r["windows"]:
            wrows.append({**{k: ident[k] for k in ("mode", "kind", "seed", "seed_kind", "mult", "burst_n")},
                          **{k: w[k] for k in ("t_start", "t_end", "admitted_turns", "hits", "hit_rate", "queue_mean", "gate_mean", "sessions_per_s",
                                               "turns_per_s", "prefill_tok_per_s", "busy_frac", "evictions_per_s", "lat_p50_s", "lat_p99_s",
                                               "reserved_mean")}})
    br, er, wa = pd.DataFrame(brow), pd.DataFrame(erow), pd.DataFrame(wrows)
    br.to_csv(out / "basin_runs.csv", index=False, lineterminator="\n")
    er.to_csv(out / "e0b_runs.csv", index=False, lineterminator="\n")
    bs, es = basin_summary(br), e0b_summary(er)
    bs.to_csv(out / "basin_summary.csv", index=False, lineterminator="\n")
    es.to_csv(out / "e0b_summary.csv", index=False, lineterminator="\n")
    with gzip.open(out / "full" / "windows_all.csv.gz", "wt", newline="") as fh:
        wa.to_csv(fh, index=False, lineterminator="\n")
    wa[wa["seed_kind"].isin(["engine", "reference"])][["mode", "kind", "seed", "mult", "burst_n", "t_start", "hit_rate", "queue_mean",
                                                      "sessions_per_s", "prefill_tok_per_s"]].to_csv(out / "engine_seed_windows.csv", index=False, lineterminator="\n",
                                                                                                      float_format="%.6g")

    # headline: the predicted cells, both modes
    head: Dict[str, Any] = {"primary_mode": rb["primary_mode"], "b1": {}, "e0f": {}}
    need = int(ep["b1"]["decision_rule"]["need"])
    for mode in rb["modes"]:
        hb = {}
        for n in rb["basin"]["burst_ns"] + rb["basin"]["reference_burst_ns"]:
            g = br[(br["mode"] == mode) & (br["burst_n"] == n)]
            e = g[g["seed_kind"] == "engine"].sort_values("seed")
            x = g[g["seed_kind"] == "extra"]
            hb[str(n)] = {"engine_seeds": {int(s): {"state": st, "stuck": bool(a), "good": bool(b_), "hit_eval": float(h)}
                                           for s, st, a, b_, h in zip(e["seed"], e["state"], e["stuck"], e["good"], e["hit_eval"])},
                          "engine_stuck": int(e["stuck"].sum()), "engine_good": int(e["good"].sum()), "engine_trapped": int(e["trapped"].sum()),
                          "extra_n": int(len(x)), "extra_stuck": int(x["stuck"].sum()), "extra_good": int(x["good"].sum()),
                          "extra_trapped": int(x["trapped"].sum()), "extra_recovered": int(x["recovered"].sum())}
        e100 = br[(br["mode"] == mode) & (br["burst_n"] == 100) & (br["seed_kind"] == "engine")]
        e25 = br[(br["mode"] == mode) & (br["burst_n"] == 25) & (br["seed_kind"] == "engine")]
        hb["predicted_basin_pass"] = bool(e100["stuck"].sum() >= need and e25["good"].sum() >= need)
        hb["predicted_n100_trap_v2_trapped_ge_2of3"] = bool(e100["trapped"].sum() >= need)
        head["b1"][mode] = hb
        he = {}
        for m in rb["e0b"]["lambda_mults"]:
            g = er[(er["mode"] == mode) & (er["mult"] == m)]
            e = g[g["seed_kind"] == "engine"].sort_values("seed")
            x = g[g["seed_kind"] == "extra"]
            he[str(m)] = {"engine_seeds": {int(s): bool(v) for s, v in zip(e["seed"], e["stable"])}, "engine_stable": int(e["stable"].sum()),
                          "extra_n": int(len(x)), "extra_stable": int(x["stable"].sum()),
                          "engine_realized_mult": {int(s): float(v) for s, v in zip(e["seed"], e["realized_base_mult"])}}
        e2 = er[(er["mode"] == mode) & (er["mult"] == 2.0) & (er["seed_kind"] == "engine")]
        e25_ = er[(er["mode"] == mode) & (er["mult"] == 2.5) & (er["seed_kind"] == "engine")]
        he["predicted_replicated"] = bool(e2["stable"].sum() == len(e2) and (~e25_["stable"]).sum() >= need)
        head["e0f"][mode] = he
    (out / "headline.json").write_bytes(json.dumps(head, indent=2).encode())

    # markdown tables for the notes
    md = ["# r11 predict basin: generated tables", "", f"result dir `{out.relative_to(REPO).as_posix()}`", "",
          "## Plan reproduction", "", md_table(pc, ["kind", "seed", "mult", "burst_n", "n_sessions", "n_sessions_committed", "rate_equal", "arrivals_turns_exact", "tool_total_max_abs_diff_s", "tool_total_n_last_bit_diff", "exact"]),
          "", md_table(sc, ["seed", "burst_n", "base_identical_to_n200", "n_burst", "burst_times_subset_of_n200", "plan_equals_cell_config_plan"]), "",
          "## B1 summary (counts; engine = seeds 0-2 on the exact client plans, extra = 30 seeds)", "",
          md_table(bs, ["mode", "burst_n", "engine_states", "engine_stuck", "engine_good", "engine_trapped", "engine_hit_eval_mean", "extra_n",
                        "extra_stuck", "extra_good", "extra_trapped", "extra_recovered", "extra_hit_eval_mean"]), "",
          "## B1 engine-seed runs", "",
          md_table(br[br["seed_kind"] == "engine"].sort_values(["mode", "burst_n", "seed"]),
                   ["mode", "burst_n", "seed", "n_base", "realized_base_mult", "hit_pre_burst", "hit_eval", "token_ratio", "backlog_slope",
                    "slope_threshold", "crit_a", "crit_b", "hit_end", "outstanding_end_qg", "state", "stuck", "good", "trap_onset_s", "release_s",
                    "max_queue_gate"]), "",
          "## E0b summary (engine = seeds 3-5 exact plans; reference = committed seed 0; extra = 20 seeds)", "",
          md_table(es, ["mode", "mult", "engine_by_seed", "engine_stable", "reference_by_seed", "extra_n", "extra_stable", "extra_stable_r6_rule"]), "",
          "## E0b engine-seed and reference runs", "",
          md_table(er[er["seed_kind"] != "extra"].sort_values(["mode", "mult", "seed"]),
                   ["mode", "mult", "seed", "seed_kind", "n_base", "realized_base_mult", "base_count_z", "stable", "final_queue_lastwin", "trend_rise",
                    "stopped_early", "stop_time", "tail_hit", "max_queue"]), ""]
    (out / "tables.md").write_bytes("\n".join(md).encode("utf-8"))

    shutil_copy(spec, out / "config.yaml")
    shutil_copy(ep_path, out / "endpoints.yaml")
    meta = {"experiment": "r11_predict_basin", "argv": sys.argv, "started": datetime.fromtimestamp(t_start).isoformat(timespec="seconds"),
            "ended": datetime.now().isoformat(timespec="seconds"), "wall_s": time.time() - t_start, "sim_wall_s": sim_wall, "n_simulations": len(jobs),
            "workers": args.workers, "quick": bool(args.quick), "sets": args.set, "engine_effective": cfg["engine"],
            "workload_effective": cfg["workload"], "metrics_effective": cfg["metrics"], "r11_basin": rb, **prov,
            "blindness": "no B1 (burst n = 100 / 25) or E0F (seeds 3-5) engine run exists when this runs; the n = 200 / n = 0 / E0b seed 0 rows are "
                         "retrodictions of committed runs whose outcomes are known"}
    (out / "meta.json").write_bytes(json.dumps(meta, indent=2, default=str).encode())
    print((out / "tables.md").read_text(encoding="utf-8"))
    print(f"[r11] done: {out}", flush=True)
    return out


def shutil_copy(src: Path, dst: Path) -> None:
    dst.write_bytes(src.read_bytes())


def cmd_plans(args: argparse.Namespace) -> None:
    cfg = load_probe_config(str((REPO / args.spec).resolve()), REPO, args.set)
    rb = cfg["r11_basin"]
    print(plan_checks(rb, REPO).to_string())
    print(basin_subset_checks(rb).to_string())


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "plans"])
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quick", action="store_true", help="2 extra seeds per cell (smoke test; written to results/r11_predict_basin_quick/)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL")
    args = ap.parse_args(argv)
    if not (1 <= args.workers <= MAX_WORKERS):
        raise SystemExit(f"--workers must be in 1..{MAX_WORKERS}")
    if args.cmd == "plans":
        cmd_plans(args)
    else:
        cmd_run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
