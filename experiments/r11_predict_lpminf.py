"""Round 11, S1 bundle 2: blind simulator predictions for L1 (LPM-INF): FCFS, stock LPM (128-request fallback) and pure LPM at 1.65 x lambda_ref.

    PYTHONPATH="src;." python experiments/r11_predict_lpminf.py run   [--spec configs/r11_predict_lpminf.yaml] [--workers 6] [--quick]
    PYTHONPATH="src;." python experiments/r11_predict_lpminf.py plans [--spec ...]          # only the plan reproduction checks

What it does (no default of src/ is changed; the instrumented runs come from src/prefixmeta/r11_lpm_sim.py):
  * builds every run's sessions from the CLIENT's plan: ``agentload.workload.build_open_plan`` on configs/agentload_e2_burst.yaml (burst 200 at
    1200 s, 60 s wide) with the job's seed, rate 1.65 x lambda_ref and duration 8700 s, converted to the simulator's ``SessionSpecs``; for the
    engine seeds 0-2 the simulator serves the exact arrival times, turn counts and tool times the LPM-INF jobs will send;
  * first reproduces the plan.csv of the six committed stock-LPM 1.65 x BURST runs (seeds 0-2, replicates r0 / r1): arrival times and turn
    counts bit for bit, tool-time totals to < 1e-9 s (libm last-bit differences between Nova and the PC);
  * engine = the round-6 calibrated engine inherited from configs/r6_predict.yaml (asserted), mixed (PRIMARY) and separate_prefill_priority
    (SECONDARY, labelled); arms fcfs (fcfs_lru), lpm128 (lpm128_lru = stock LPM), lpminf (lpm_lru = pure LPM, the predicted cell) and the
    labelled sensitivity lpm128s (stock LPM with SGLang's sticky fallback order);
  * classifies each run with the FROZEN endpoints of configs/r11_lpminf_predict.yaml (primary collapse, simulated trap_v2 state, latency,
    unfinished sessions, miss-turn latency, uncached tokens/s) and writes small CSV / JSON / Markdown summaries to results/r11_predict_lpminf/<ts>/
    (per-window data of every seed to its full/ subdirectory, not meant to be committed).

Simulator analogues of the engine-side quantities (declared here, before any run):
  token hit over W   sum(cached) / sum(prompt tokens) over the turns COMPLETING in W = [5700, 8700) (engine: analysis/windows.py token_hit_rate,
                     attribute_by complete). A simulator hit caches the whole previous context (P_t - 550 tokens); there are no partial hits.
  turn hit           fraction of turns completing in the window that were cache hits (the frac_turns_cached_gt50 analogue: every simulator
                     hit has cached / prompt >= 2100 / 2650 > 0.5, every miss 0)
  token rate         mean prefill tokens / s over the 100 s simulator windows of W (uncached prefill tokens; cache-hit turns count their 550 new)
  crit (a)           |token rate / R_miss - 1| <= 0.15, R_miss = the simulator's own all-miss token rate of the batching mode (r6 B1); the ratio to
                     the registered engine value 11,243.18 is recorded too
  backlog slope      OLS slope over W of the 10 s bin means of sessions in the system (arrived minus completed; there is no gate), the step function
                     sampled at 1 s midpoints; crit (b): slope > 0.5 (lambda - lambda_ref), lambda = the resolved 1.65 x lambda_ref
  RECOVERED          turn hit over the last 300 s > 0.8 AND outstanding requests (waiting queue + admitted-and-unfinished) mean over the last 300 s < 20
  latency            turn latency = completion - turn ready time (turn 1: session arrival; later turns: previous completion + tool time; the engine's
                     send-to-response-end), p50 / p99 over the turns completing in W and in [1200, 8700)
  miss-turn latency  the same over the MISS turns completing in W (p50 / p90 / p99 / max), plus the count of turns with latency > 600 s
  unfinished         sessions arrived by the run end that did not finish all turns
  fallback passes    scheduling passes with more than 128 waiting requests (for every arm; where stock LPM falls back), and the time with the
                     100 s mean waiting queue above 128
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
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

from agentload.config import config_from_dict, resolve_lambda_ref, resolve_rate  # noqa: E402
from agentload.workload import SessionPlan, build_open_plan  # noqa: E402
from prefixmeta.probe import load_probe_config  # noqa: E402
from prefixmeta.r11_lpm_sim import simulate_instrumented  # noqa: E402
from prefixmeta.sim import RunSpec  # noqa: E402
from prefixmeta.workload import ArrivalPlan, SessionSpecs  # noqa: E402

DEFAULT_SPEC = "configs/r11_predict_lpminf.yaml"
MAX_WORKERS = 6
NAN = float("nan")


# ======================================================================= client plans -> simulator sessions
def client_config(agentload_cfg: str, seed: int, mult: float, lambda_ref: float, duration_s: float, burst_n: int, t_burst: float, width_s: float):
    """The agentload Config the LPM-INF job builds (run_gen with --seed, --set arrivals.rate_mult / lambda_ref / run.duration_s / burst.t_s)."""
    raw = yaml.safe_load((REPO / agentload_cfg).read_text())
    raw["arrivals"]["rate_mult"] = float(mult)
    raw["arrivals"]["lambda_ref"] = float(lambda_ref)
    if "uncached_tokens_ref" in raw["arrivals"]:
        raw["arrivals"]["uncached_tokens_ref"] = None          # analysis reference only; unused by the generator
    raw["arrivals"]["burst"] = {"n": int(burst_n), "t_s": float(t_burst), "width_s": float(width_s)} if burst_n > 0 else None
    raw["run"]["seed"] = int(seed)
    raw["run"]["duration_s"] = float(duration_s)
    raw.setdefault("meta", {})["engine_label"] = "sim-r11-predict-lpminf"
    return config_from_dict(raw)


def client_plan(b: dict, seed: int, lambda_ref: float) -> Tuple[List[SessionPlan], float]:
    cfg = client_config(b["agentload_config"], seed, b["lambda_mult"], lambda_ref, b["duration_s"], b["burst_n"], b["t_burst_s"], b["width_s"])
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
    b = job["burst"]
    plan, rate = client_plan(b, job["seed"], job["lambda_ref"])
    specs = plan_to_specs(plan)
    H = float(b["duration_s"])
    rs = RunSpec(exp="r11_lpminf", policy=job["policy"], seed=int(job["seed"]), horizon_s=H, variant=f"{job['arm']}|{job['mode']}",
                 plan=ArrivalPlan(kind="constant", horizon_s=H, rate=rate), engine_overrides={"batching": job["batching"]}, meta={})
    res = simulate_instrumented(cfg, rs, specs=specs, count_threshold=int(job["fallback_threshold"]))
    return {"job": {k: v for k, v in job.items() if k != "cfg"}, "rate": rate,
            "arrival": specs.arrival, "n_turns": specs.n_turns,
            "n_base": int(sum(1 for sp in plan if sp.origin == "base")), "n_burst": int(sum(1 for sp in plan if sp.origin == "burst")),
            "summary": res["summary"], "windows": res["windows"], "turns": res["turns"], "policy_stats": res["policy_stats"]}


def run_jobs(jobs: List[Dict[str, Any]], workers: int) -> List[Dict[str, Any]]:
    if workers <= 1:
        return [_work(j) for j in jobs]
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(_work, jobs, chunksize=1))


# ======================================================================= per-run quantities (frozen endpoints)
def _q(x: np.ndarray, q: float) -> float:
    return float(np.quantile(x, q)) if len(x) else NAN


def _token_hit(t: Dict[str, np.ndarray], m: np.ndarray) -> float:
    s = float(t["prompt"][m].sum())
    return float(t["cached"][m].sum()) / s if s > 0 else NAN


def _turn_hit(t: Dict[str, np.ndarray], m: np.ndarray) -> float:
    return float(t["hit"][m].mean()) if m.any() else NAN


def sessions_in_system_bins(arrival: np.ndarray, n_turns: np.ndarray, t: Dict[str, np.ndarray], H: float, dt: float) -> Tuple[np.ndarray, np.ndarray]:
    """(bin midpoints, bin means) of sessions in the system (arrived minus completed), sampled at 1 s midpoints and averaged in dt bins."""
    last = t["turn"] == n_turns[t["sid"]]
    t_end = np.sort(t["t_done"][last & np.isfinite(t["t_done"])])
    arr = np.sort(arrival[np.isfinite(arrival)])
    grid = np.arange(0.0, H, 1.0) + 0.5
    n = np.searchsorted(arr, grid, side="right") - np.searchsorted(t_end, grid, side="right")
    k = int(round(dt))
    nb = len(grid) // k
    means = n[:nb * k].reshape(nb, k).mean(axis=1)
    mids = dt * np.arange(nb) + dt / 2.0
    return mids, means


def running_mean(t: Dict[str, np.ndarray], t0: float, t1: float) -> float:
    """Time-average over [t0, t1) of the admitted-and-unfinished requests."""
    a = t["t_admit"]
    d = np.where(np.isfinite(t["t_done"]), t["t_done"], np.inf)
    lo = np.maximum(a, t0)
    hi = np.minimum(d, t1)
    return float(np.clip(hi - lo, 0.0, None).sum() / (t1 - t0))


def classify(r: Dict[str, Any], ep: dict, R_miss: float) -> Dict[str, Any]:
    pr, tv, sec = ep["primary"], ep["secondaries"]["trap_v2"], ep["secondaries"]
    cell = ep["cell"]
    lam = float(r["rate"])
    lam_ref = float(cell["lambda_ref"])
    H = float(cell["duration_s"])
    tb = float(cell["burst_t_s"])
    t0, t1 = float(pr["window_s"][0]), float(pr["window_s"][1])
    R_reg = float(tv["uncached_tokens_ref"])
    w = pd.DataFrame(r["windows"]).sort_values("t_start").reset_index(drop=True)
    t = r["turns"]
    done = t["t_done"]
    fin = np.isfinite(done)
    inW = fin & (done >= t0) & (done < t1)
    lat = done - t["ready"]
    wait = t["t_admit"] - t["qtime"]

    token_hit = _token_hit(t, inW)
    collapse = bool(token_hit == token_hit and token_hit < float(pr["collapse_hit_below"]))
    turn_hit_W = _turn_hit(t, inW)
    sW = w[(w["t_start"] >= t0 - 1e-9) & (w["t_end"] <= t1 + 1e-9)]
    tok = float(sW["prefill_tok_per_s"].mean()) if len(sW) else NAN
    crit_a = bool(tok == tok and abs(tok / R_miss - 1.0) <= float(tv["rate_tolerance"]))
    crit_a_reg = bool(tok == tok and abs(tok / R_reg - 1.0) <= float(tv["rate_tolerance"]))
    mids, nsys = sessions_in_system_bins(r["arrival"], r["n_turns"], t, H, float(tv["slope_dt_s"]))
    selW = (mids >= t0) & (mids < t1)
    slope = float(np.polyfit(mids[selW], nsys[selW], 1)[0]) if selW.sum() >= 3 else NAN
    thr = float(tv["slope_frac"]) * (lam - lam_ref)
    crit_b = bool(slope == slope and slope > thr)
    ew = float(tv["end_window_s"])
    end_m = fin & (done >= H - ew) & (done < H)
    hit_end = _turn_hit(t, end_m)
    wend = w[(w["t_start"] >= H - ew - 1e-9) & (w["t_end"] <= H + 1e-9)]
    outst_end = (float(wend["queue_mean"].mean()) if len(wend) else NAN) + running_mean(t, H - ew, H)
    recovered = bool(hit_end == hit_end and hit_end > float(tv["recovered_hit_above"]) and outst_end < float(tv["recovered_backlog_below"]))
    trapped = bool(crit_a and crit_b and lam > lam_ref)
    draining = bool(slope == slope and slope < 0)
    state = "trapped" if trapped else "recovered" if recovered else "draining" if draining else "indeterminate"

    post = fin & (done >= tb) & (done < H)
    miss_W = inW & ~t["hit"]
    lw = float(sec["miss_turn_latency"]["long_wait_s"])
    s = r["summary"]
    # queue above the fallback threshold
    thr_q = int(r["policy_stats"]["count_threshold"])
    over = w[w["queue_mean"] > thr_q]
    first_over = float(over[over["t_start"] >= tb - 1e-9]["t_start"].min()) if len(over) else NAN
    pre = fin & (done < tb)
    return {
        "lam": lam, "token_hit_W": token_hit, "collapse": collapse, "turn_hit_W": turn_hit_W, "token_hit_pre_burst": _token_hit(t, pre),
        "token_rate_W": tok, "token_ratio": tok / R_miss, "token_ratio_registered_ref": tok / R_reg, "crit_a": crit_a,
        "crit_a_registered_ref": crit_a_reg, "backlog_slope": slope, "slope_threshold": thr, "crit_b": crit_b,
        "sessions_in_system_W_mean": float(nsys[selW].mean()) if selW.any() else NAN, "hit_end": hit_end, "outstanding_end": outst_end,
        "trapped": trapped, "recovered": recovered, "draining": draining, "state": state,
        "lat_p50_W": _q(lat[inW], 0.5), "lat_p99_W": _q(lat[inW], 0.99), "lat_p50_post": _q(lat[post], 0.5), "lat_p99_post": _q(lat[post], 0.99),
        "miss_lat_p50_W": _q(lat[miss_W], 0.5), "miss_lat_p90_W": _q(lat[miss_W], 0.9), "miss_lat_p99_W": _q(lat[miss_W], 0.99),
        "miss_lat_max_W": float(lat[miss_W].max()) if miss_W.any() else NAN, "n_miss_turns_W": int(miss_W.sum()), "n_turns_W": int(inW.sum()),
        "miss_wait_p50_W": _q(wait[miss_W], 0.5), "miss_wait_p99_W": _q(wait[miss_W], 0.99),
        "hit_wait_p99_W": _q(wait[inW & t["hit"]], 0.99),
        "n_turns_latency_over_long": int((lat[fin] > lw).sum()),
        "unfinished_sessions": int(s["n_arrived"] - s["n_sessions_done"]), "n_arrived": int(s["n_arrived"]),
        "final_queue": int(s["final_queue"]), "max_queue": int(s["max_queue"]),
        "queue_W_mean": float(sW["queue_mean"].mean()) if len(sW) else NAN,
        "time_queue_over_threshold_s": float((w["queue_mean"] > thr_q).sum() * (w["t_end"] - w["t_start"]).iloc[0]) if len(w) else NAN,
        "first_window_queue_over_threshold_s": first_over,
        "frac_passes_over_threshold": r["policy_stats"]["n_passes_queue_over_threshold"] / max(1, r["policy_stats"]["n_policy_calls"]),
        "n_policy_calls": int(r["policy_stats"]["n_policy_calls"]), "policy_class": r["policy_stats"]["policy_class"],
        "sim_end_s": float(s["sim_end_s"]), "stopped_early": int(s["stopped_early"]),
    }


def window_rows(r: Dict[str, Any], W: float) -> List[Dict[str, Any]]:
    """Per 100 s window: completion-attributed token / turn hit plus the recorder's columns."""
    t = r["turns"]
    done = t["t_done"]
    fin = np.isfinite(done)
    rows = []
    for w in r["windows"]:
        m = fin & (done >= w["t_start"]) & (done < w["t_end"])
        rows.append({"t_start": w["t_start"], "t_end": w["t_end"], "token_hit_c": _token_hit(t, m), "turn_hit_c": _turn_hit(t, m),
                     "hit_rate_adm": w["hit_rate"], "queue_mean": w["queue_mean"], "queue_max": w["queue_max"], "sessions_per_s": w["sessions_per_s"],
                     "turns_per_s": w["turns_per_s"], "prefill_tok_per_s": w["prefill_tok_per_s"], "lat_p50_s": w["lat_p50_s"], "lat_p99_s": w["lat_p99_s"],
                     "evictions_per_s": w["evictions_per_s"], "busy_frac": w["busy_frac"]})
    return rows


# ======================================================================= plan checks
def _blob_matches_head(f: Path, rel: str) -> Optional[bool]:
    """True iff the git blob of file ``f`` equals HEAD:<rel> of this repo (the committed input, read from another checkout)."""
    head = _git(["rev-parse", f"HEAD:{rel}"])
    try:
        mine = subprocess.run(["git", "hash-object", str(f)], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:       # pragma: no cover
        return None
    return bool(head) and head == mine


def plan_checks(rl: dict, repo: Path) -> pd.DataFrame:
    """``repo`` is where the committed plan.csv / meta.json are read; when it is not this repo (a Windows path-length workaround for a scratch
    clone), every file read must be blob-identical to this repo's HEAD."""
    lam_ref = float(rl["lambda_ref"])
    rows = []
    for c in rl["plan_checks"]:
        d = repo / c["dir"]
        if Path(repo).resolve() != REPO:
            for name in ("plan.csv", "meta.json"):
                if not _blob_matches_head(d / name, f"{c['dir']}/{name}"):
                    raise SystemExit(f"{d / name} is not blob-identical to HEAD:{c['dir']}/{name}")
        ref = pd.read_csv(d / "plan.csv", float_precision="round_trip")
        plan, rate = client_plan(rl["burst"], int(c["seed"]), lam_ref)
        mine = pd.DataFrame([{"sid": sp.sid, "origin": sp.origin, "idx": sp.idx, "arrival_s": sp.arrival_s, "n_turns": sp.n_turns,
                              "tool_time_total_s": float(sum(sp.tool_times_s))} for sp in plan])
        meta = json.loads((d / "meta.json").read_text())
        argv = meta.get("argv", [])
        seed_argv = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else None
        same_len = len(mine) == len(ref)
        exact = bool(same_len and all((mine[k].to_numpy() == ref[k].to_numpy()).all() for k in ("sid", "origin", "idx", "n_turns"))
                     and np.array_equal(mine["arrival_s"].to_numpy(), ref["arrival_s"].to_numpy()))
        tool_diff = float(np.max(np.abs(mine["tool_time_total_s"].to_numpy() - ref["tool_time_total_s"].to_numpy()))) if same_len else NAN
        tool_bits = int((mine["tool_time_total_s"].to_numpy() != ref["tool_time_total_s"].to_numpy()).sum()) if same_len else -1
        rows.append({"dir": c["dir"], "label": c["label"], "label_meta": meta.get("engine_label"), "seed": c["seed"], "seed_argv": seed_argv,
                     "e2_config_argv": argv[argv.index("--config") + 1] if "--config" in argv else None,
                     "n_sessions": len(mine), "n_sessions_committed": len(ref), "n_burst": int((mine["origin"] == "burst").sum()),
                     "rate": rate, "rate_committed": meta.get("resolved_rate_sessions_per_s"),
                     "rate_equal": rate == meta.get("resolved_rate_sessions_per_s"), "arrivals_turns_exact": exact,
                     "tool_total_max_abs_diff_s": tool_diff, "tool_total_n_last_bit_diff": tool_bits,
                     "exact": bool(exact and tool_diff == tool_diff and tool_diff < 1e-9 and seed_argv == int(c["seed"])
                                   and meta.get("engine_label") == c["label"])})
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
              "configs/prefix_meta.yaml", "configs/agentload_e2_burst.yaml", "configs/r11_predict_lpminf.yaml", "configs/r11_lpminf_predict.yaml",
              "experiments/r11_predict_lpminf.py"]


def provenance() -> Dict[str, Any]:
    files = {}
    for rel in SIM_INPUTS:
        p = REPO / rel
        for f in (sorted(p.glob("*.py")) if p.is_dir() else [p]):
            files[str(f.relative_to(REPO)).replace("\\", "/")] = sha256(f)
    sim_dirty = _git(["status", "--porcelain", "--", *SIM_INPUTS])
    return {"git_head": _git(["rev-parse", "HEAD"]), "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "git_status_porcelain": _git(["status", "--porcelain"]).splitlines(),
            "simulation_inputs_clean_vs_head": sim_dirty == "", "simulation_inputs_status": sim_dirty.splitlines(),
            "sha256": files, "hostname": socket.gethostname(), "platform": platform.platform(), "python": sys.version,
            "numpy": np.__version__, "pandas": pd.__version__}


# ======================================================================= tables
def _rel(p: Path) -> str:
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


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


def summarize(runs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (mode, arm), g in runs.groupby(["mode", "arm"], sort=False):
        row = {"mode": mode, "arm": arm, "policy": g["policy"].iloc[0]}
        e = g[g["seed_kind"] == "engine"].sort_values("seed")
        x = g[g["seed_kind"] == "extra"]
        row["engine_by_seed"] = " ".join(f"s{int(s)}:{'COLLAPSE' if c else 'no'}/{st}/{h:.3f}" for s, c, st, h in
                                         zip(e["seed"], e["collapse"], e["state"], e["token_hit_W"]))
        for kind, sub in (("engine", e), ("extra", x), ("all", g)):
            row[f"{kind}_n"] = len(sub)
            row[f"{kind}_collapse"] = int(sub["collapse"].sum())
            for st in ("trapped", "recovered", "draining", "indeterminate"):
                row[f"{kind}_{st}"] = int((sub["state"] == st).sum())
            row[f"{kind}_token_hit_W_mean"] = float(sub["token_hit_W"].mean())
        row["extra_token_hit_W_min"] = float(x["token_hit_W"].min()) if len(x) else NAN
        row["extra_token_hit_W_max"] = float(x["token_hit_W"].max()) if len(x) else NAN
        for c in ("lat_p99_W", "miss_lat_p99_W", "unfinished_sessions", "token_ratio", "queue_W_mean", "time_queue_over_threshold_s"):
            row[f"all_{c}_mean"] = float(g[c].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def decision(e: pd.DataFrame, informative: Sequence[int]) -> str:
    d = {int(s): bool(c) for s, c in zip(e["seed"], e["collapse"])}
    if any(s not in d for s in informative):
        return "inconclusive"
    v = [d[s] for s in informative]
    if not any(v):
        return "consistent"
    if all(v):
        return "against"
    return "inconclusive"


# ======================================================================= main command
def build_jobs(cfg: dict, rl: dict, quick: bool) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    b = rl["burst"]
    extra = b["extra_seeds"][:2] if quick else b["extra_seeds"]
    for mode, batching in rl["modes"].items():
        for arm, a in rl["arms"].items():
            for kind, seeds in (("engine", b["engine_seeds"]), ("extra", extra)):
                for sd in seeds:
                    jobs.append({"cfg": cfg, "mode": mode, "batching": batching, "arm": arm, "policy": a["policy"], "seed": int(sd),
                                 "seed_kind": kind, "lambda_ref": float(rl["lambda_ref"]), "burst": b,
                                 "fallback_threshold": int(rl["fallback_threshold"])})
    return jobs


def check_inputs(cfg: dict, rl: dict, ep: dict) -> None:
    if ep.get("status") != "FROZEN":
        raise SystemExit("endpoints file: status is not FROZEN")
    r6 = load_probe_config(str(REPO / "configs/r6_predict.yaml"), REPO, None)
    if cfg["engine"] != r6["engine"] or cfg["workload"] != r6["workload"] or cfg["metrics"] != r6["metrics"]:
        raise SystemExit("effective engine / workload / metrics differ from configs/r6_predict.yaml")
    lam_file = resolve_lambda_ref(rl["lambda_ref_source"], REPO)
    if not (float(rl["lambda_ref"]) == float(ep["cell"]["lambda_ref"]) == float(lam_file)):
        raise SystemExit(f"lambda_ref of the spec / endpoints / calibration file differ ({rl['lambda_ref']}, {ep['cell']['lambda_ref']}, {lam_file})")
    b, c = rl["burst"], ep["cell"]
    for k_spec, k_ep in (("engine_seeds", "seeds"),):
        if [int(x) for x in b[k_spec]] != [int(x) for x in c[k_ep]]:
            raise SystemExit("engine seeds of the spec and of the frozen endpoints differ")
    for k_spec, k_ep in (("lambda_mult", "lambda_mult"), ("burst_n", "burst_n"), ("t_burst_s", "burst_t_s"), ("width_s", "burst_width_s"),
                         ("duration_s", "duration_s")):
        if float(b[k_spec]) != float(c[k_ep]):
            raise SystemExit(f"{k_spec} of the spec and {k_ep} of the frozen endpoints differ")
    if b["agentload_config"] != c["e2_config"]:
        raise SystemExit("agentload config of the spec and e2_config of the endpoints differ")
    summ = json.loads((REPO / rl["references"]["source"]).read_text())
    for mode, batching in rl["modes"].items():
        if float(summ["modes"][batching]["b1"]["token_rate"]) != float(rl["references"]["all_miss_tok_per_s"][mode]):
            raise SystemExit(f"all-miss token rate of mode {mode} differs from {rl['references']['source']}")
    for name in {a["policy"] for a in rl["arms"].values()}:
        if name not in cfg["policies"]:
            raise SystemExit(f"policy {name} not in the effective config")


def cmd_run(args: argparse.Namespace) -> Path:
    t_start = time.time()
    spec = (REPO / args.spec).resolve()
    cfg = load_probe_config(str(spec), REPO, args.set)
    rl = cfg["r11_lpminf"]
    ep_path = (REPO / rl["endpoints"]).resolve()
    ep = yaml.safe_load(ep_path.read_text())
    check_inputs(cfg, rl, ep)
    prov = provenance()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = REPO / args.out_root / ("r11_predict_lpminf" + ("_quick" if args.quick else "")) / stamp
    (out / "full").mkdir(parents=True, exist_ok=False)
    print(f"[r11-lpm] out {out}", flush=True)

    plan_root = Path(args.plan_root).resolve() if args.plan_root else REPO
    pc = plan_checks(rl, plan_root)
    pc.to_csv(out / "plan_checks.csv", index=False, lineterminator="\n")
    print(pc[["label", "seed", "n_sessions", "n_burst", "rate_equal", "arrivals_turns_exact", "tool_total_max_abs_diff_s", "exact"]].to_string(), flush=True)
    if not (pc["exact"].all() and pc["rate_equal"].all()):
        raise SystemExit("plan reproduction check FAILED: the simulated streams would not be the engine's; nothing simulated")

    jobs = build_jobs(cfg, rl, args.quick)
    print(f"[r11-lpm] {len(jobs)} simulations on {args.workers} workers", flush=True)
    t_sim = time.time()
    results = run_jobs(jobs, args.workers)
    sim_wall = time.time() - t_sim
    print(f"[r11-lpm] simulations done in {sim_wall:.1f} s", flush=True)

    refs = rl["references"]["all_miss_tok_per_s"]
    rows, wrows = [], []
    for r in results:
        j = r["job"]
        ident = {"mode": j["mode"], "batching": j["batching"], "arm": j["arm"], "policy": j["policy"], "seed": j["seed"], "seed_kind": j["seed_kind"],
                 "n_base": r["n_base"], "n_burst": r["n_burst"], "lambda": r["rate"], "realized_base_mult": r["n_base"] / float(j["burst"]["duration_s"]) / j["lambda_ref"],
                 "wall_s": float(r["summary"]["wall_s"])}
        rows.append({**ident, **classify(r, ep, float(refs[j["mode"]]))})
        for w in window_rows(r, 100.0):
            wrows.append({**{k: ident[k] for k in ("mode", "arm", "seed", "seed_kind")}, **w})
    runs, wa = pd.DataFrame(rows), pd.DataFrame(wrows)
    runs.to_csv(out / "runs.csv", index=False, lineterminator="\n")
    summ = summarize(runs)
    summ.to_csv(out / "summary.csv", index=False, lineterminator="\n")
    with gzip.open(out / "full" / "windows_all.csv.gz", "wt", newline="") as fh:
        wa.to_csv(fh, index=False, lineterminator="\n")
    wa[wa["seed_kind"] == "engine"].drop(columns=["seed_kind"]).to_csv(out / "engine_seed_windows.csv", index=False, lineterminator="\n", float_format="%.6g")

    informative = [int(s) for s in ep["cell"]["informative_seeds"]]
    head: Dict[str, Any] = {"primary_mode": rl["primary_mode"], "predicted_arm": rl["predicted_arm"], "informative_seeds": informative, "modes": {}}
    for mode in rl["modes"]:
        hm = {}
        for arm in rl["arms"]:
            g = runs[(runs["mode"] == mode) & (runs["arm"] == arm)]
            e = g[g["seed_kind"] == "engine"].sort_values("seed")
            x = g[g["seed_kind"] == "extra"]
            hm[arm] = {"engine_seeds": {int(s): {"collapse": bool(c), "state": st, "token_hit_W": float(h), "turn_hit_W": float(th),
                                                 "lat_p99_W_s": float(l99), "miss_lat_p99_W_s": float(m99), "unfinished_sessions": int(u),
                                                 "token_ratio": float(tr), "backlog_slope": float(sl), "time_queue_over_128_s": float(tq)}
                                          for s, c, st, h, th, l99, m99, u, tr, sl, tq in
                                          zip(e["seed"], e["collapse"], e["state"], e["token_hit_W"], e["turn_hit_W"], e["lat_p99_W"],
                                              e["miss_lat_p99_W"], e["unfinished_sessions"], e["token_ratio"], e["backlog_slope"],
                                              e["time_queue_over_threshold_s"])},
                       "engine_collapse": int(e["collapse"].sum()), "engine_states": {st: int((e["state"] == st).sum()) for st in
                                                                                      ("trapped", "recovered", "draining", "indeterminate")},
                       "decision_rule_on_simulated_seeds": decision(e, informative),
                       "extra_n": int(len(x)), "extra_collapse": int(x["collapse"].sum()),
                       "extra_states": {st: int((x["state"] == st).sum()) for st in ("trapped", "recovered", "draining", "indeterminate")},
                       "extra_token_hit_W": [float(x["token_hit_W"].min()), float(x["token_hit_W"].mean()), float(x["token_hit_W"].max())]
                       if len(x) else None}
        hm["lpminf_minus_lpm128_unfinished_by_seed"] = {
            int(s): int(runs[(runs["mode"] == mode) & (runs["arm"] == "lpminf") & (runs["seed"] == s)]["unfinished_sessions"].iloc[0]
                        - runs[(runs["mode"] == mode) & (runs["arm"] == "lpm128") & (runs["seed"] == s)]["unfinished_sessions"].iloc[0])
            for s in rl["burst"]["engine_seeds"]}
        head["modes"][mode] = hm
    (out / "headline.json").write_bytes(json.dumps(head, indent=2).encode())

    ecols = ["mode", "arm", "seed", "n_base", "realized_base_mult", "token_hit_pre_burst", "token_hit_W", "collapse", "turn_hit_W", "token_ratio",
             "token_ratio_registered_ref", "backlog_slope", "slope_threshold", "crit_a", "crit_b", "hit_end", "outstanding_end", "state",
             "lat_p50_W", "lat_p99_W", "miss_lat_p50_W", "miss_lat_p99_W", "miss_lat_max_W", "n_turns_latency_over_long", "unfinished_sessions",
             "queue_W_mean", "max_queue", "time_queue_over_threshold_s", "first_window_queue_over_threshold_s", "frac_passes_over_threshold"]
    md = ["# r11 predict LPM-INF (S1 bundle 2): generated tables", "", f"result dir `{_rel(out)}`", "",
          "## Plan reproduction (committed stock-LPM 1.65 x BURST runs)", "",
          md_table(pc, ["label", "seed", "n_sessions", "n_sessions_committed", "n_burst", "rate_equal", "arrivals_turns_exact",
                        "tool_total_max_abs_diff_s", "tool_total_n_last_bit_diff", "exact"]), "",
          "## Summary (engine = seeds 0-2 on the exact client plans; extra = 10 seeds)", "",
          md_table(summ, ["mode", "arm", "engine_by_seed", "engine_collapse", "engine_trapped", "extra_n", "extra_collapse", "extra_trapped",
                          "extra_recovered", "extra_draining", "extra_indeterminate", "extra_token_hit_W_mean", "extra_token_hit_W_min",
                          "extra_token_hit_W_max", "all_lat_p99_W_mean", "all_miss_lat_p99_W_mean", "all_unfinished_sessions_mean"]), "",
          "## Engine-seed runs", "", md_table(runs[runs["seed_kind"] == "engine"].sort_values(["mode", "arm", "seed"]), ecols), "",
          "## Extra-seed runs", "", md_table(runs[runs["seed_kind"] == "extra"].sort_values(["mode", "arm", "seed"]), ecols), ""]
    (out / "tables.md").write_bytes("\n".join(md).encode("utf-8"))

    (out / "config.yaml").write_bytes(spec.read_bytes())
    (out / "endpoints.yaml").write_bytes(ep_path.read_bytes())
    meta = {"experiment": "r11_predict_lpminf", "argv": sys.argv, "started": datetime.fromtimestamp(t_start).isoformat(timespec="seconds"),
            "ended": datetime.now().isoformat(timespec="seconds"), "wall_s": time.time() - t_start, "sim_wall_s": sim_wall, "n_simulations": len(jobs),
            "workers": args.workers, "quick": bool(args.quick), "sets": args.set, "plan_root": str(plan_root), "engine_effective": cfg["engine"],
            "workload_effective": cfg["workload"], "metrics_effective": cfg["metrics"],
            "policies_effective": {a["policy"]: cfg["policies"][a["policy"]] for a in rl["arms"].values()}, "r11_lpminf": rl, **prov,
            "blindness": ("no LPM-INF (sglang-lpminf) engine run exists when this runs; the fcfs and lpm128 rows are retrodictions of committed "
                          "engine cells whose outcomes are known to the lead (stock LPM at 1.65 x trapped or stuck in 4 of 6 runs)")}
    (out / "meta.json").write_bytes(json.dumps(meta, indent=2, default=str).encode())
    print((out / "tables.md").read_text(encoding="utf-8"))
    print(json.dumps(head, indent=1)[:4000])
    print(f"[r11-lpm] done: {out}", flush=True)
    return out


def cmd_plans(args: argparse.Namespace) -> None:
    cfg = load_probe_config(str((REPO / args.spec).resolve()), REPO, args.set)
    print(plan_checks(cfg["r11_lpminf"], Path(args.plan_root).resolve() if args.plan_root else REPO).to_string())


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "plans"])
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quick", action="store_true", help="2 extra seeds per cell (smoke test; written to results/r11_predict_lpminf_quick/)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL")
    ap.add_argument("--plan-root", default=None, help="read the committed plan.csv / meta.json of the plan checks from this checkout (each file must "
                    "be blob-identical to this repo's HEAD); default: this repo")
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
