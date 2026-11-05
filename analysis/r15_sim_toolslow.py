"""r15 TOOLSLOW cells T1 and T2: blind predictions of the calibrated simulator, with the r14 d10 / d30 retrodictions.

    PYTHONPATH="src;." python -m analysis.r15_sim_toolslow run [--workers 6] [--out results/theory/r15/toolslow_sim.json]
    PYTHONPATH="src;." python -m analysis.r15_sim_toolslow selfcheck     # the hook is inert without a slowdown (bit-identical)
    PYTHONPATH="src;." python -m analysis.r15_sim_toolslow plans         # rebuilt client plans vs the committed NOBURST plan.csv
    PYTHONPATH="src;." python -m analysis.r15_sim_toolslow measure --run-dirs RUN [RUN ...] [--out FILE]
                                                   # the same secondary / exploratory measures on GPU run dirs (for scoring)

Cells (300k pool, FCFS + LRU, NOBURST arrivals, 8700-s runs, evaluation window W = [5700, 8700) s). The slowdown is the
client option workload.tool_slowdown {t_s, width_s, add_s}: a tool call whose sleep STARTS at t in [t_s, t_s + width_s)
(the instant the previous turn's response completes) lasts its drawn tool time plus add_s; later tool calls are normal.

    role          cell    rate            slowdown {t_s, width_s, add_s}   GPU outcome known when this file was written
    PREDICTION    T1      1.35 x lambda   {1200, 1800, 30}                 no run exists
    PREDICTION    T2      1.65 x lambda   {1200,  900, 15}                 no run exists
    RETRODICTION  d10     1.35 x lambda   {1200,  900, 10}                 GOOD / GOOD / GOOD   (jobs 17169902-04)
    RETRODICTION  d30     1.35 x lambda   {1200,  900, 30}                 GOOD / GOOD / STUCK  (jobs 17169905-07)
    RETRODICTION  ctl135  1.35 x lambda   none                             GOOD x 3 (NOBURST controls, jobs 17093387-404)
    RETRODICTION  ctl165  1.65 x lambda   none                             GOOD x 3 (same jobs)

lambda = mult x lambda_ref, lambda_ref = 0.07153402100919228 sessions/s (prereg/inputs/2026-10-23/calibration.json,
lambda_miss_turns_based, the registered value). The tool-slowdown hook was written on 2026-11-04 AFTER the d10 / d30 GPU
results were known, so every d10 / d30 / control row is a RETRODICTION, never a prediction.

Exact client plans (seeds 0, 1, 2 = the plans the GPU jobs replay): experiments/r11_predict_rescue.client_plan on
configs/agentload_e2_burst.yaml with arrivals.burst = null, the job's rate_mult and seed, lambda_ref = the registered
calibration path:key and run.duration_s 8700 (agentload.workload.build_open_plan, the generator the jobs run). The slowdown
changes no random draw, so these are the committed NOBURST plans of results/nova/e2_170933xx_pulled_20261025-144558
(1.35 x: 20261024-155125 / -161834 / -211253; 1.65 x: 20261024-160218 / -184259 / 20261025-000053); ``plans`` checks
it (byte-identical plan.csv, or equal with the tool-time totals within 1e-12 relative: libm last bits, Nova vs this PC).
Simulator seeds: 20 per cell and mode, seeds 0-19 of prefixmeta.workload.build_specs (the r11 ``seeds: 20`` convention;
independent draws of the same workload, a plan-sensitivity band, not the GPU plans).

Engine: exactly configs/r11_predict_rescue.yaml (base_config configs/r6_predict.yaml: the round-6 calibrated engine block,
unchanged; checked at start), kv_memory_tokens 300000 (pool p300k), policy fcfs_lru; PRIMARY batching ``mixed``, SECONDARY
``separate_prefill_priority``. The registered ``observe`` controller of that config (rescue mode, t_on 1e18: never
engages) runs the frozen prefixmeta.gate_control.GateEngine so that the per-turn completion records and the 10-s tick
trace exist; with the cap never engaged the gate stays empty.

Slowdown hook (nothing under src/ is edited): ``ToolSlowEngine`` subclasses the frozen gate_control.GateEngine and extends
only ``_finish_request``: when turn k < T of a session completes at t inside the window, its tool time k is increased by
add_s before the frozen method schedules the tool return at t + Z. The frozen gate_control.simulate_gate builds its engine
through the module-level name ``GateEngine``; ``_engine_bound`` binds that name to the subclass for one call and restores
it. Without a slowdown the subclass is bit-identical to the frozen engine (``selfcheck``). Ported from the scratch driver
theory-pred/simdrv.py of 2026-11-04 (its toolslow hook only; the scratch stall / wipe / pollution hooks are not ported).

Per-run endpoints: the frozen B1 endpoints of configs/r11_basin_predict.yaml (read from it) on the simulator's records:
    hit_eval       all-turn hit over W: share of the turns COMPLETED in W that hit (cached / prompt > 0.5), first turns
                   included (frac_turns_cached_gt50, attributed by completion; gate_control.all_hit)
    RECOVERED      all-turn hit over the last 300 s > 0.8 AND mean outstanding < 20 over the last 300 s (outstanding =
                   waiting + running requests + gate, the 10-s tick samples; the client's requests in flight + gated)
    backlog slope  OLS slope of the sessions in the system (arrived, not finished, incl. the gate) over the 10-s tick
                   samples in W; threshold slope_frac x (lambda - lambda_ref) = 0.5 x (mult - 1) x lambda_ref
    STUCK := hit_eval < 0.2;  GOOD := RECOVERED, or (hit_eval > 0.8 and slope <= threshold);  state stuck | good | neither
Secondary and exploratory measures (per run; the same definitions are applied to the GPU runs' requests.csv / sessions.csv):
    out_2100_2400  mean outstanding requests over the tick samples in [2100, 2400)
    out_3300       outstanding requests at the 3300-s tick
    alive_2100, alive_3000   sessions in the system at the 2100-s and 3000-s ticks
    t_fu150        start a of the first 150-s window [a, a + 150), a = 1200 + 150 k, whose follow-up hit (turns >= 2
                   completed in the window) is < 0.5; None if no such window before 8700 s
Cell call per mode (exact seeds 0-2), the registered r15 rule: TRAPS (STUCK in >= 2 of 3) | NO-TRAP (GOOD in >= 2 of 3) |
MIXED (otherwise, or both). The ``mixed`` column is the frozen call; ``separate_prefill_priority`` is the secondary column.
Sensitivities (``sensitivity`` block; NOT predictions, the calibrated engine and the registered slowdown stay the
prediction): the exact-plan calls of T1 and T2 on an add_s grid at the cell's own window and rate, and with every
iteration cost of the engine block scaled by f in {0.85, 0.9, 1.1, 1.15} (f < 1 = a faster engine).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import contextlib
import hashlib
import json
import math
import multiprocessing as mp
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "src", REPO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiments.r11_predict_rescue as r11                                     # noqa: E402
from prefixmeta import gate_control as gc                                          # noqa: E402
from prefixmeta import probe                                                       # noqa: E402
from prefixmeta.runner import env_versions, git_info, sanitize                     # noqa: E402
from prefixmeta.sim import RunSpec, deep_update                                    # noqa: E402
from prefixmeta.workload import ArrivalPlan, SessionSpecs, WorkloadParams, build_specs   # noqa: E402

EXPERIMENT = "r15_sim_toolslow"
SIM_CONFIG = "configs/r11_predict_rescue.yaml"        # r6 calibration (base_config configs/r6_predict.yaml), unchanged
R6_CONFIG = "configs/r6_predict.yaml"
ENDPOINTS = "configs/r11_basin_predict.yaml"
POOL = "p300k"
CONTROL = "observe"                                   # configs/r11_predict_rescue.yaml r11_rescue.controls.observe
MODES = ("mixed", "separate_prefill_priority")        # PRIMARY first
EXACT_SEEDS = (0, 1, 2)
SIM_SEEDS = tuple(range(20))
DEFAULT_OUT = "results/theory/r15/toolslow_sim.json"
QUICK_OUT = "results/theory/r15/toolslow_sim_quick.json"
CONTROL_ROOT = "results/nova/e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst"
CONTROL_DIRS = {1.35: ("20261024-155125", "20261024-161834", "20261024-211253"),
                1.65: ("20261024-160218", "20261024-184259", "20261025-000053")}

# cell -> rate multiple, slowdown (t_s, width_s, add_s) or None, role, and the GPU outcome when it was known before this file
CELLS: Dict[str, Dict[str, Any]] = {
    "T1": {"mult": 1.35, "slowdown": (1200.0, 1800.0, 30.0), "role": "prediction", "gpu_known": None},
    "T2": {"mult": 1.65, "slowdown": (1200.0, 900.0, 15.0), "role": "prediction", "gpu_known": None},
    "d10": {"mult": 1.35, "slowdown": (1200.0, 900.0, 10.0), "role": "retrodiction",
            "gpu_known": {"states": ["good", "good", "good"], "source": "jobs 17169902-04, results/nova/"
                          "toolslow_shed_1716990x_pulled_20261101-154800 (analysis.r14_cells classify, r14_runs.csv)"}},
    "d30": {"mult": 1.35, "slowdown": (1200.0, 900.0, 30.0), "role": "retrodiction",
            "gpu_known": {"states": ["good", "good", "stuck"], "source": "jobs 17169905-07, results/nova/"
                          "toolslow_shed_1716990x_pulled_20261101-154800 (analysis.r14_cells classify, r14_runs.csv)"}},
    "ctl135": {"mult": 1.35, "slowdown": None, "role": "retrodiction",
               "gpu_known": {"states": ["good", "good", "good"], "source": "NOBURST controls 1.35 x, jobs 17093387-404 "
                             "(r14_runs.csv control rows)"}},
    "ctl165": {"mult": 1.65, "slowdown": None, "role": "retrodiction",
               "gpu_known": {"states": ["good", "good", "good"], "source": "NOBURST controls 1.65 x, jobs 17093387-404"}},
}
TRACKED_FILES = ("analysis/r15_sim_toolslow.py", SIM_CONFIG, R6_CONFIG, ENDPOINTS, "configs/agentload_e2_burst.yaml",
                 "experiments/r11_predict_rescue.py", "src/prefixmeta/gate_control.py", "src/prefixmeta/engine.py",
                 "src/prefixmeta/sim.py", "src/prefixmeta/workload.py", "src/prefixmeta/probe.py", "src/prefixmeta/metrics.py",
                 "src/agentload/workload.py", "src/agentload/config.py", "prereg/inputs/2026-10-23/calibration.json")
NAN = float("nan")

# exploratory constants (declared here, before any run of this module)
FU150_W = 150.0
FU150_BELOW = 0.5
FU150_FROM = 1200.0
T1_ONSET_BAND = (1800.0, 3300.0)          # T1 exploratory prediction: t_fu150 of every STUCK run inside [1800, 3300)
OUT_WIN = (2100.0, 2400.0)
OUT_AT = 3300.0
ALIVE_AT = (2100.0, 2400.0, 3000.0)
# SENSITIVITIES of the exact-plan calls of the two prediction cells (NOT predictions): the slowdown's add_s at the cell's window
# and rate, and the engine speed (every iteration cost of the calibrated engine block scaled by f; f < 1 = faster engine)
SENS_ADD_S = {"T1": (15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 60.0), "T2": (10.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0, 25.0)}
SENS_ENGINE_SCALE = (0.85, 0.9, 1.1, 1.15)
ENGINE_COST_KEYS = ("iter_fixed_s", "iter_floor_s", "per_token_s", "decode_attn_s", "prefill_attn_s")


# ======================================================================= the hook
_FROZEN_GATE_ENGINE = gc.GateEngine       # captured at import, before any binding


class ToolSlowEngine(_FROZEN_GATE_ENGINE):
    """The frozen GateEngine plus the TOOLSLOW client option. ``SLOWDOWN`` (t_s, width_s, add_s) or None and ``INSTANCES``
    (every engine built from the class) are class attributes of the per-run subclass made by :func:`engine_class`;
    ``slow_log`` records every lengthened tool call."""

    SLOWDOWN: Optional[Tuple[float, float, float]] = None
    INSTANCES: List["ToolSlowEngine"] = []

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.slow_log: List[Tuple[float, int, int]] = []          # (tool-call start t, sid, turn whose response started it)
        self.n_tool_calls = 0
        type(self).INSTANCES.append(self)

    def _finish_request(self, req, t: float) -> None:
        sid = req.sid
        if req.turn < self._nt[sid]:                                # a tool call starts now (the session has a next turn)
            self.n_tool_calls += 1
            ts = self.SLOWDOWN
            if ts is not None and ts[0] <= t < ts[0] + ts[1]:
                k = self._toff[sid] + req.turn - 1
                self._tool[k] = self._tool[k] + ts[2]               # read by the frozen Engine._finish_request below
                self.slow_log.append((float(t), int(sid), int(req.turn)))
        super()._finish_request(req, t)


def engine_class(slowdown: Optional[Sequence[float]]) -> type:
    sd = None if slowdown is None else (float(slowdown[0]), float(slowdown[1]), float(slowdown[2]))
    return type("ToolSlowEngineRun", (ToolSlowEngine,), {"SLOWDOWN": sd, "INSTANCES": []})


@contextlib.contextmanager
def _engine_bound(cls: type) -> Iterator[None]:
    """Bind gate_control's module-level name GateEngine (looked up by the frozen build_gate_engine at call time) to ``cls``
    for one simulate_gate call; always restored."""
    old = gc.GateEngine
    gc.GateEngine = cls
    try:
        yield
    finally:
        gc.GateEngine = old


def simulate_toolslow(cfg: dict, rs: RunSpec, control: gc.GateControl, specs: SessionSpecs,
                      slowdown: Optional[Sequence[float]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """frozen gate_control.simulate_gate with the engine class bound to the slowdown subclass; (result, hook log)."""
    cls = engine_class(slowdown)
    with _engine_bound(cls):
        res = gc.simulate_gate(cfg, rs, control, specs)
    if len(cls.INSTANCES) != 1:
        raise AssertionError(f"expected one engine built by simulate_gate, got {len(cls.INSTANCES)}")
    eng = cls.INSTANCES[0]
    log = np.asarray(eng.slow_log, dtype=float).reshape(-1, 3)
    hook = {"n_tool_calls": int(eng.n_tool_calls), "n_tool_calls_slowed": int(len(log)),
            "slowed_t_start_min": float(log[:, 0].min()) if len(log) else None,
            "slowed_t_start_max": float(log[:, 0].max()) if len(log) else None}
    return res, hook


# ======================================================================= config, plans, jobs
def load_cfg() -> Tuple[dict, dict]:
    cfg = probe.load_probe_config(str(REPO / SIM_CONFIG), REPO)
    r6 = probe.load_probe_config(str(REPO / R6_CONFIG), REPO)
    if cfg["engine"] != r6["engine"] or cfg["workload"] != r6["workload"]:
        raise SystemExit(f"{SIM_CONFIG}: engine / workload differ from the r6 calibration {R6_CONFIG}")
    return cfg, cfg["r11_rescue"]


def load_endpoints() -> Dict[str, Any]:
    ep = yaml.safe_load((REPO / ENDPOINTS).read_text())
    b1, tv = ep["b1"], ep["b1"]["trap_v2"]
    return {"stuck_hit_below": float(b1["stuck"]["trap_hit_below"]), "good_hit_above": float(tv["recovered_hit_above"]),
            "window_s": [float(b1["window_s"][0]), float(b1["window_s"][1])], "slope_frac": float(tv["slope_frac"]),
            "recovered_hit_above": float(tv["recovered_hit_above"]),
            "recovered_backlog_below": float(tv["recovered_backlog_below"]), "end_window_s": float(tv["end_window_s"]),
            "lambda_ref": float(b1["lambda_ref"]), "duration_s": float(b1["duration_s"])}


def build_jobs(cells: Sequence[str], modes: Sequence[str], quick: bool) -> List[Dict[str, Any]]:
    jobs = []
    for mode in modes:
        for c in cells:
            spec = CELLS[c]
            sim = SIM_SEEDS[:2] if quick else SIM_SEEDS
            exact = EXACT_SEEDS[:1] if quick else EXACT_SEEDS
            for kind, sd in [("exact", s) for s in exact] + [("sim", s) for s in sim]:
                jobs.append({"cell": c, "mode": mode, "mult": float(spec["mult"]), "slowdown": spec["slowdown"], "kind": kind,
                             "seed": int(sd)})
    return jobs


def build_sens_jobs(cells: Sequence[str], modes: Sequence[str], quick: bool) -> List[Dict[str, Any]]:
    """Exact-plan sensitivity runs of the prediction cells (add_s grid at the cell's window and rate; engine speed)."""
    jobs = []
    for mode in modes:
        for c in cells:
            if c not in SENS_ADD_S:
                continue
            t_s, w, add0 = CELLS[c]["slowdown"]
            for sd in (EXACT_SEEDS[:1] if quick else EXACT_SEEDS):
                for a in SENS_ADD_S[c]:
                    if a != add0:
                        jobs.append({"cell": c, "mode": mode, "mult": float(CELLS[c]["mult"]), "slowdown": (t_s, w, float(a)),
                                     "kind": "exact", "seed": int(sd), "sens": f"add_s={a:g}"})
                for f in SENS_ENGINE_SCALE:
                    jobs.append({"cell": c, "mode": mode, "mult": float(CELLS[c]["mult"]), "slowdown": CELLS[c]["slowdown"],
                                 "kind": "exact", "seed": int(sd), "sens": f"engine_scale={f:g}", "engine_scale": float(f)})
    return jobs


def exact_plan(rcfg: dict, seed: int, mult: float):
    refs = r11.pool_refs(rcfg, POOL)
    cp, rate = r11.client_plan(rcfg, seed=int(seed), mult=float(mult), lambda_ref_spec=refs["lambda_ref_spec"],
                               protocol=rcfg["protocol"], burst=False)
    return cp, float(rate), refs


# ======================================================================= measures
def _fu_windows(done: np.ndarray, t0: float, t1: float, w: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(window starts, follow-up hit per window or NaN, follow-up completions per window) over [t0, t1) tiled by w."""
    edges = np.arange(t0, t1 + 1e-9, w)
    fu = done[done[:, 2] >= 2]
    n = np.histogram(fu[:, 0], bins=edges)[0]
    h = np.histogram(fu[:, 0], bins=edges, weights=fu[:, 3])[0]
    with np.errstate(invalid="ignore", divide="ignore"):
        hit = np.where(n > 0, h / np.maximum(n, 1), np.nan)
    return edges[:-1], hit, n


def _tick(tr: pd.DataFrame, t: float, col: str) -> float:
    m = np.isclose(tr["t"].to_numpy(dtype=float), t, rtol=0.0, atol=1e-6)
    return float(tr.loc[m, col].iloc[0]) if m.any() else NAN


def measures(res: Dict[str, Any], mult: float, ep: Dict[str, Any], H: float) -> Dict[str, Any]:
    done = gc._done_array(res)
    tr = gc.trace_frame(res)
    tr["alive"] = tr["in_system"] + tr["gate"]
    w0, w1 = ep["window_s"]
    lam_ref = ep["lambda_ref"]
    lam = float(mult) * lam_ref
    thr = ep["slope_frac"] * (lam - lam_ref)
    hit_eval = gc.all_hit(done, w0, w1)
    sel = tr[(tr["t"] >= w0 - 1e-9) & (tr["t"] < w1 - 1e-9)]
    slope = float(np.polyfit(sel["t"].to_numpy(dtype=float), sel["alive"].to_numpy(dtype=float), 1)[0]) if len(sel) >= 3 else NAN
    ew = ep["end_window_s"]
    hit_end = gc.all_hit(done, H - ew, H)
    tail = tr[(tr["t"] >= H - ew - 1e-9) & (tr["t"] < H - 1e-9)]
    out_end = float(tail["outstanding"].mean()) if len(tail) else NAN
    recovered = bool(hit_end == hit_end and hit_end > ep["recovered_hit_above"] and out_end == out_end
                     and out_end < ep["recovered_backlog_below"])
    stuck = bool(hit_eval == hit_eval and hit_eval < ep["stuck_hit_below"])
    good_hs = bool(hit_eval == hit_eval and slope == slope and hit_eval > ep["good_hit_above"] and slope <= thr)
    good = bool(recovered or good_hs)
    state = "stuck+good" if (stuck and good) else "stuck" if stuck else "good" if good else "neither"
    starts, fuh, fun = _fu_windows(done, FU150_FROM, H, FU150_W)
    below = np.nonzero((fun > 0) & (fuh < FU150_BELOW))[0]
    ow = tr[(tr["t"] >= OUT_WIN[0] - 1e-9) & (tr["t"] < OUT_WIN[1] - 1e-9)]
    m = {"state": state, "stuck": stuck, "good": good, "good_by_recovered": recovered, "good_by_hit_slope": good_hs,
         "hit_eval": hit_eval, "backlog_slope": slope, "slope_threshold": thr, "hit_end": hit_end, "outstanding_end": out_end,
         "fu_eval": gc.fu_hit(done, w0, w1)[0],
         "out_2100_2400": float(ow["outstanding"].mean()) if len(ow) else NAN, "out_3300": _tick(tr, OUT_AT, "outstanding"),
         "t_fu150": float(starts[below[0]]) if len(below) else None,
         "uncached_rate_1800_2100": gc.uncached_rate(done, 1800.0, 2100.0)}
    for a in ALIVE_AT:
        m[f"alive_{int(a)}"] = _tick(tr, a, "alive")
    m["max_alive"] = float(tr["alive"].max()) if len(tr) else NAN
    m["t_max_alive"] = float(tr["t"].iloc[int(tr["alive"].to_numpy().argmax())]) if len(tr) else NAN
    return m


def series(res: Dict[str, Any], H: float) -> Dict[str, Any]:
    """Compact time courses of an exact-plan run: follow-up hit and mean outstanding / alive per 150 s over [1200, 3600),
    all-turn hit per 300 s over the whole run."""
    done = gc._done_array(res)
    tr = gc.trace_frame(res)
    tr["alive"] = tr["in_system"] + tr["gate"]
    starts, fuh, fun = _fu_windows(done, 1200.0, 3600.0, 150.0)
    out_m, alive_m = [], []
    for a in starts:
        s = tr[(tr["t"] >= a - 1e-9) & (tr["t"] < a + 150.0 - 1e-9)]
        out_m.append(round(float(s["outstanding"].mean()), 1) if len(s) else None)
        alive_m.append(round(float(s["alive"].mean()), 1) if len(s) else None)
    e300 = np.arange(0.0, H + 1e-9, 300.0)
    hit300 = [gc.all_hit(done, a, b) for a, b in zip(e300[:-1], e300[1:])]
    return {"w150_start": [float(a) for a in starts], "fu150": [None if x != x else round(float(x), 3) for x in fuh],
            "n_fu150": [int(x) for x in fun], "outstanding150": out_m, "alive150": alive_m,
            "w300_start": [float(a) for a in e300[:-1]], "hit300": [None if x != x else round(float(x), 3) for x in hit300]}


# ======================================================================= one run (process-pool worker)
def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    cfg0, rcfg = load_cfg()
    ep = load_endpoints()
    refs = r11.pool_refs(rcfg, POOL)
    cfg = deep_update(cfg0, {"engine": {"batching": job["mode"], "kv_memory_tokens": int(refs["kv"])}})
    if job.get("engine_scale") is not None:                         # SENSITIVITY only: every iteration cost scaled by f
        f = float(job["engine_scale"])
        cfg = deep_update(cfg, {"engine": {k: float(cfg0["engine"][k]) * f for k in ENGINE_COST_KEYS}})
    prot = rcfg["protocol"]
    H = float(prot["duration_s"])
    lam = float(job["mult"]) * refs["lambda_ref"]
    plan = ArrivalPlan(kind="constant", horizon_s=H, rate=lam, burst_n=0, burst_t0=float(prot["burst"]["t_s"]),
                       burst_width_s=float(prot["burst"]["width_s"]))
    rs = RunSpec(exp=EXPERIMENT, policy=rcfg["policy"], seed=int(job["seed"]), horizon_s=H, variant=job["cell"], plan=plan)
    row: Dict[str, Any] = {k: job[k] for k in ("cell", "mode", "kind", "seed", "mult")}
    row["lam"] = lam
    if job.get("sens"):
        row["sens"] = job["sens"]
        row["slowdown"] = list(job["slowdown"]) if job["slowdown"] is not None else None
        row["engine_scale"] = job.get("engine_scale", 1.0)
    if job["kind"] == "exact":
        cp, rate, _ = exact_plan(rcfg, job["seed"], job["mult"])
        if abs(rate - lam) > 1e-15 * lam:
            raise AssertionError(f"client rate {rate} != {lam}")
        specs = r11.specs_from_plan(cp)
        row["plan_sha256"] = r11.plan_csv_sha256(cp)
        row["n_sessions_planned"] = len(cp)
    else:
        specs = build_specs(WorkloadParams.from_dict(cfg["workload"]), plan, int(job["seed"]))
        row["n_sessions_planned"] = len(specs)
    control = gc.GateControl.from_dict(rcfg["controls"][CONTROL])
    t0 = time.perf_counter()
    res, hook = simulate_toolslow(cfg, rs, control, specs, job["slowdown"])
    row["wall_s"] = time.perf_counter() - t0
    if res["gate"]["stats"]["t_engage"] is not None:
        raise AssertionError("the observe controller engaged")
    row.update(hook)
    row.update(measures(res, job["mult"], ep, H))
    row["n_sessions_done"] = int(res["gate"]["n_sessions_done"])
    row["n_arrived"] = int(res["gate"]["n_arrived"])
    if job["kind"] == "exact" and not job.get("sens"):
        row["series"] = series(res, H)
    return row


def _run_all(jobs: List[Dict[str, Any]], workers: int) -> List[Dict[str, Any]]:
    if workers <= 1:
        return [run_job(j) for j in jobs]
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(run_job, jobs, chunksize=1))


# ======================================================================= summaries
def _code(states: Sequence[str]) -> str:
    return "".join({"stuck": "S", "good": "G", "neither": "N", "stuck+good": "X"}[s] for s in states)


def tri_state(states: Sequence[str], need: int = 2) -> str:
    """The registered r15 rule (analysis/r15_cells.py RULE): TRAPS iff STUCK in >= 2 of 3; NO-TRAP iff GOOD in >= 2 of 3;
    else MIXED (also MIXED when both counts reach 2, possible only through runs that are both STUCK and GOOD)."""
    n_s = sum(s in ("stuck", "stuck+good") for s in states)
    n_g = sum(s in ("good", "stuck+good") for s in states)
    if n_s >= need and n_g >= need:
        return "MIXED"
    return "TRAPS" if n_s >= need else "NO-TRAP" if n_g >= need else "MIXED"


def at_least(p: float, k: int = 2, n: int = 3) -> float:
    return float(sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1)))


def _band(v: Sequence[Optional[float]]) -> Optional[List[float]]:
    x = [float(a) for a in v if a is not None and a == a]
    return [min(x), float(np.median(x)), max(x)] if x else None


def sens_summary(rows: List[Dict[str, Any]], modes: Sequence[str], cells: Sequence[str]) -> Dict[str, Any]:
    """Exact-plan codes per sensitivity setting (the cell's own setting included, from the main rows)."""
    out: Dict[str, Any] = {}
    for c in cells:
        if c not in SENS_ADD_S:
            continue
        out[c] = {}
        for mode in modes:
            rr = [r for r in rows if r["cell"] == c and r["mode"] == mode and r["kind"] == "exact"]
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for r in rr:
                tag = r.get("sens") or f"add_s={CELLS[c]['slowdown'][2]:g} (the cell)"
                groups.setdefault(tag, []).append(r)
            d = {}
            for tag, g in groups.items():
                g = sorted(g, key=lambda r: r["seed"])
                d[tag] = {"seeds": [r["seed"] for r in g], "code": _code([r["state"] for r in g]),
                          "call": tri_state([r["state"] for r in g]), "hit_eval": [r["hit_eval"] for r in g],
                          "alive_2100": [r["alive_2100"] for r in g], "alive_3000": [r["alive_3000"] for r in g]}
            key = lambda t: (0 if t.startswith("add_s") else 1, float(t.split("=")[1].split(" ")[0]))   # noqa: E731
            out[c][mode] = {t: d[t] for t in sorted(d, key=key)}
    return out


def summarize(rows: List[Dict[str, Any]], modes: Sequence[str], cells: Sequence[str]) -> Dict[str, Any]:
    rows = [r for r in rows if not r.get("sens")]
    out: Dict[str, Any] = {}
    for c in cells:
        out[c] = {}
        for mode in modes:
            ex = sorted([r for r in rows if r["cell"] == c and r["mode"] == mode and r["kind"] == "exact"], key=lambda r: r["seed"])
            sm = [r for r in rows if r["cell"] == c and r["mode"] == mode and r["kind"] == "sim"]
            st = [r["state"] for r in ex]
            n = len(sm)
            ns = sum(r["state"] == "stuck" for r in sm)
            ng = sum(r["state"] == "good" for r in sm)
            d: Dict[str, Any] = {
                "exact_seeds": [r["seed"] for r in ex], "exact_states": st, "exact_code": _code(st), "call": tri_state(st),
                "exact_hit_eval": [r["hit_eval"] for r in ex],
                "exact_out_2100_2400": [r["out_2100_2400"] for r in ex], "exact_out_3300": [r["out_3300"] for r in ex],
                "exact_alive_2100": [r["alive_2100"] for r in ex], "exact_alive_3000": [r["alive_3000"] for r in ex],
                "exact_t_fu150": [r["t_fu150"] for r in ex],
                "sim_seeds": [r["seed"] for r in sorted(sm, key=lambda r: r["seed"])],
                "sim_n": n, "sim_stuck": ns, "sim_good": ng, "sim_neither": n - ns - ng,
                "sim_p_traps_exchangeable": at_least(ns / n) if n else None,
                "sim_p_notrap_exchangeable": at_least(ng / n) if n else None,
                "sim_out_2100_2400_band": _band([r["out_2100_2400"] for r in sm]),
                "sim_alive_2100_band": _band([r["alive_2100"] for r in sm]),
                "sim_alive_3000_band": _band([r["alive_3000"] for r in sm]),
                "sim_t_fu150_stuck_band": _band([r["t_fu150"] for r in sm if r["state"] == "stuck"]),
                "n_stuck_runs_t_fu150_in_T1_band": None}
            if c == "T1":
                stuck_runs = [r for r in ex + sm if r["state"] == "stuck"]
                d["n_stuck_runs_t_fu150_in_T1_band"] = {
                    "band": list(T1_ONSET_BAND), "n_stuck_runs": len(stuck_runs),
                    "n_inside": sum(1 for r in stuck_runs if r["t_fu150"] is not None
                                    and T1_ONSET_BAND[0] <= r["t_fu150"] < T1_ONSET_BAND[1])}
            gk = CELLS[c]["gpu_known"]
            if gk is not None:
                d["gpu_known_states"] = gk["states"]
                d["gpu_known_code"] = _code(gk["states"])
                d["retrodiction_seed_agreement"] = sum(a == b for a, b in zip(st, gk["states"]))
            out[c][mode] = d
    return out


def committed_control_plans() -> List[Tuple[str, str, pd.DataFrame]]:
    out = []
    for mult, dirs in CONTROL_DIRS.items():
        for d in dirs:
            p = REPO / CONTROL_ROOT / d / "plan.csv"
            out.append((p.parent.relative_to(REPO).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest(),
                        pd.read_csv(p, float_precision="round_trip")))
    return out


def plan_check(rcfg: dict) -> List[Dict[str, Any]]:
    committed = committed_control_plans()
    rows = []
    for mult, dirs in CONTROL_DIRS.items():
        for sd, d in zip(EXACT_SEEDS, dirs):
            cp, rate, _ = exact_plan(rcfg, sd, mult)
            sha = r11.plan_csv_sha256(cp)
            m = r11.match_committed(r11.plan_frame(cp), sha, committed)
            want = f"{CONTROL_ROOT}/{d}"
            ok = want in m["committed_byte_identical"].split() or want in m["committed_equal_up_to_tool_ulp"].split()
            rows.append({"mult": mult, "seed": sd, "rate": rate, "n_sessions": len(cp), "plan_sha256": sha, "control_dir": want,
                         "matches_control": bool(ok), **m})
    return rows


def file_sha(rel: str) -> Optional[str]:
    p = REPO / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


# ======================================================================= CLI
def cmd_run(args) -> int:
    t_start = time.time()
    git0 = git_info(REPO)
    cfg, rcfg = load_cfg()
    ep = load_endpoints()
    modes = list(args.modes or MODES)
    cells = list(args.cells or CELLS)
    pc = plan_check(rcfg)
    bad = [r for r in pc if not r["matches_control"]]
    if bad:
        raise SystemExit(f"rebuilt client plans differ from the committed NOBURST controls: {bad}")
    jobs = build_jobs(cells, modes, args.quick)
    sjobs = [] if args.no_sens else build_sens_jobs(cells, modes, args.quick)
    print(f"{len(jobs)} runs + {len(sjobs)} sensitivity runs, {args.workers} workers", flush=True)
    allrows = _run_all(jobs + sjobs, args.workers)
    rows = [r for r in allrows if not r.get("sens")]
    srows = [r for r in allrows if r.get("sens")]
    summ = summarize(rows, modes, cells)
    ssum = sens_summary(allrows, modes, cells)
    for c, v in ssum.items():
        for mode, d in v.items():
            print(f"SENS {c} {mode[:3]} " + "  ".join(f"{t}:{x['code']}" for t, x in d.items()), flush=True)
    for c in cells:
        for mode in modes:
            d = summ[c][mode]
            print(f"{c:7s} {mode[:3]} exact {d['exact_code']} ({d['call']}) sim {d['sim_stuck']}S/{d['sim_good']}G/"
                  f"{d['sim_neither']}N of {d['sim_n']}  out[2100,2400) {[round(x, 1) for x in d['exact_out_2100_2400']]}  "
                  f"alive2100 {d['exact_alive_2100']} alive3000 {d['exact_alive_3000']}  t_fu150 {d['exact_t_fu150']}", flush=True)
    t1 = time.time()
    obj = {
        "experiment": EXPERIMENT,
        "status": ("FROZEN blind simulator predictions for T1 and T2 (no GPU run of these cells existed); d10, d30, ctl135 and "
                   "ctl165 are RETRODICTIONS (their GPU outcomes were known and the hook was written after them)"),
        "quick": bool(args.quick),
        "cells": {c: {"mult": CELLS[c]["mult"], "lambda": CELLS[c]["mult"] * ep["lambda_ref"],
                      "slowdown": None if CELLS[c]["slowdown"] is None else dict(zip(("t_s", "width_s", "add_s"), CELLS[c]["slowdown"])),
                      "role": CELLS[c]["role"], "gpu_known": CELLS[c]["gpu_known"]} for c in cells},
        "engine": {"config": SIM_CONFIG, "base_config": cfg.get("_base_config"), "pool": POOL, "kv_memory_tokens": int(r11.pool_refs(rcfg, POOL)["kv"]),
                   "policy": rcfg["policy"], "modes": modes, "primary_mode": modes[0], "control": rcfg["controls"][CONTROL],
                   "engine_block": {k: v for k, v in cfg["engine"].items()}, "workload_block": cfg["workload"]},
        "endpoints": {**ep, "source": ENDPOINTS, "state_rule": "STUCK := hit_eval < 0.2; GOOD := RECOVERED or (hit_eval > 0.8 "
                      "and backlog slope <= 0.5 (lambda - lambda_ref)); state stuck | good | neither",
                      "cell_call": "per mode over exact seeds 0-2: TRAPS (STUCK >= 2 of 3) | NO-TRAP (GOOD >= 2 of 3) | MIXED"},
        "exploratory_definitions": {"out_2100_2400": "mean outstanding requests (waiting + running + gate) over the 10-s tick samples in [2100, 2400)",
                                    "out_3300": "outstanding requests at the 3300-s tick",
                                    "alive_T": "sessions in the system (arrived, not finished, incl. gate) at the T-s tick",
                                    "t_fu150": "start of the first 150-s window [1200 + 150k, +150) with follow-up hit < 0.5",
                                    "T1_onset_band": list(T1_ONSET_BAND)},
        "seeds": {"exact": list(EXACT_SEEDS[:1] if args.quick else EXACT_SEEDS),
                  "sim": list(SIM_SEEDS[:2] if args.quick else SIM_SEEDS)},
        "plan_check": pc,
        "summary": summ,
        "sensitivity": {"note": "NOT predictions: exact-plan calls of the prediction cells when one input is changed, (a) the "
                                "slowdown's add_s at the cell's window and rate, (b) the engine speed (every iteration cost of the "
                                "calibrated engine block scaled by f; f < 1 = faster engine)",
                        "add_s_grid": {c: list(v) for c, v in SENS_ADD_S.items() if c in cells},
                        "engine_scale_grid": list(SENS_ENGINE_SCALE), "engine_cost_keys": list(ENGINE_COST_KEYS),
                        "codes": ssum},
        "runs": rows,
        "sensitivity_runs": srows,
        "provenance": {"git_at_start": git0, "file_sha256": {f: file_sha(f) for f in TRACKED_FILES}, "versions": env_versions(),
                       "hostname": socket.gethostname(), "argv": sys.argv,
                       "start_time": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t_start)),
                       "end_time": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t1)), "wall_s": t1 - t_start,
                       "workers": args.workers, "ported_from": "scratch theory-pred/simdrv.py (2026-11-04), toolslow hook only",
                       "blindness": "no GPU run of T1 or T2 existed; nothing under results/nova is read except the six committed "
                                    "NOBURST plan.csv files (to check the rebuilt client plans)"},
    }
    out_rel = args.out or (QUICK_OUT if args.quick else DEFAULT_OUT)      # a --quick run never overwrites the frozen file
    out = (REPO / out_rel).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sanitize(obj), indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.as_posix(), f"({t1 - t_start:.0f} s)")
    return 0


def cmd_selfcheck(args) -> int:
    """Without a slowdown the hook engine reproduces the frozen GateEngine bit for bit (summary, trace, completion records);
    with a slowdown it lengthens exactly the tool calls starting inside the window."""
    cfg0, rcfg = load_cfg()
    refs = r11.pool_refs(rcfg, POOL)
    ok = True
    for mode in (args.modes or ["mixed"]):
        cfg = deep_update(cfg0, {"engine": {"batching": mode, "kv_memory_tokens": int(refs["kv"])}})
        prot = rcfg["protocol"]
        H = float(prot["duration_s"])
        cp, rate, _ = exact_plan(rcfg, 0, 1.35)
        plan = ArrivalPlan(kind="constant", horizon_s=H, rate=rate, burst_n=0)
        rs = RunSpec(exp=EXPERIMENT, policy=rcfg["policy"], seed=0, horizon_s=H, variant="selfcheck", plan=plan)
        ctl = gc.GateControl.from_dict(rcfg["controls"][CONTROL])
        a = gc.simulate_gate(cfg, rs, ctl, r11.specs_from_plan(cp))
        b, hook = simulate_toolslow(cfg, rs, ctl, r11.specs_from_plan(cp), None)
        if gc.GateEngine is not _FROZEN_GATE_ENGINE:
            raise AssertionError("gate_control.GateEngine not restored")
        drop = {"wall_s", "wall_s_per_10k_sim_s"}

        def digest(x: Any) -> str:                                  # NaN-aware (NaN -> null), order-preserving
            return hashlib.sha256(json.dumps(sanitize(x), sort_keys=True, default=str).encode()).hexdigest()

        parts = {"summary": ({k: v for k, v in a["summary"].items() if k not in drop},
                             {k: v for k, v in b["summary"].items() if k not in drop}),
                 "windows": (a["windows"], b["windows"]), "qtrace": (a["qtrace"], b["qtrace"]),
                 "btrace": (a["btrace"], b["btrace"]), "trace": (a["gate"]["trace"], b["gate"]["trace"]),
                 "done": (a["gate"]["done"], b["gate"]["done"]), "sessions": (a["gate"]["sessions"], b["gate"]["sessions"])}
        diff = [k for k, (x, y) in parts.items() if digest(x) != digest(y)]
        same = not diff
        print(f"{mode}: no slowdown, hook engine == frozen GateEngine: {same} (differing parts: {diff or 'none'}; "
              f"done-record digest {digest(a['gate']['done'])[:16]}); tool calls {hook['n_tool_calls']}, slowed "
              f"{hook['n_tool_calls_slowed']}")
        ok &= same and hook["n_tool_calls_slowed"] == 0
        # with the d30 slowdown: every tool call starting in [1200, 2100) lengthened, none outside
        c, hook2 = simulate_toolslow(cfg, rs, ctl, r11.specs_from_plan(cp), (1200.0, 900.0, 30.0))
        d = np.asarray(c["gate"]["done"], dtype=float).reshape(-1, 5)
        nt = np.array([sp.n_turns for sp in cp])
        starts = d[(d[:, 2] < nt[d[:, 1].astype(int)])][:, 0]           # completions with a next turn = tool-call starts
        n_in = int(((starts >= 1200.0) & (starts < 2100.0)).sum())
        good = (hook2["n_tool_calls_slowed"] == n_in and hook2["slowed_t_start_min"] >= 1200.0 and hook2["slowed_t_start_max"] < 2100.0)
        print(f"{mode}: d30 slowdown: slowed {hook2['n_tool_calls_slowed']} = tool calls starting in [1200, 2100) {n_in}: {good}; "
              f"first {hook2['slowed_t_start_min']:.1f} s, last {hook2['slowed_t_start_max']:.1f} s")
        ok &= good
    print("SELFCHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def measure_run(run_dir: str | Path, p) -> Dict[str, Any]:
    """The secondary / exploratory measures on a GPU run dir, with the frozen analysis helpers (analysis.throughput):
    out_2100_2400 = outstanding_mean over [2100, 2400) (requests in flight + gated sessions, time-average); out_3300 =
    outstanding_at(3300); alive_T = backlog_at(sessions, T) (sessions in the system, right-continuous); t_fu150 = start of
    the first 150-s window [1200 + 150 k, + 150) whose hit_frac_followup (ok turns >= 2 completing in it, cached / prompt >
    windows.cached_frac_threshold) is < 0.5; hit_eval = hit_frac_turns over [5700, 8700) (the frozen endpoint's hit)."""
    from analysis import throughput as TP
    from analysis.load import load_run
    run = load_run(run_dir)
    out: Dict[str, Any] = {"run_dir": Path(run_dir).as_posix(), "label": run.label, "seed": run.seed,
                           "rate_mult": (run.cfg.get("arrivals") or {}).get("rate_mult"),
                           "tool_slowdown": (run.cfg.get("workload") or {}).get("tool_slowdown"), "t_end_s": run.t_end_s}
    out["hit_eval"] = TP.hit_stats(run, p, 5700.0, 8700.0)["hit_frac_turns"]
    out["out_2100_2400"] = TP.outstanding_mean(run, OUT_WIN[0], OUT_WIN[1])
    out["out_3300"] = TP.outstanding_at(run, OUT_AT)
    for a in ALIVE_AT:
        out[f"alive_{int(a)}"] = TP.backlog_at(run.sessions, a)
    first = None
    a = FU150_FROM
    while a + FU150_W <= float(run.t_end_s) + 1e-9:
        h = TP.hit_stats(run, p, a, a + FU150_W)["hit_frac_followup"]
        if h == h and h < FU150_BELOW:
            first = a
            break
        a += FU150_W
    out["t_fu150"] = first
    return out


def cmd_measure(args) -> int:
    from analysis.params import load_params
    p = load_params(REPO / "configs/agentload_analysis.yaml")
    rows = [measure_run(d, p) for d in args.run_dirs]
    for r in rows:
        print(f"{r['label']} seed {r['seed']} x{r['rate_mult']}: hit_eval {r['hit_eval']:.4f}  out[2100,2400) "
              f"{r['out_2100_2400']:.1f}  out@3300 {r['out_3300']:.0f}  alive@2100/2400/3000 {r['alive_2100']:.0f}/"
              f"{r['alive_2400']:.0f}/{r['alive_3000']:.0f}  t_fu150 {r['t_fu150']}")
    if args.out:
        o = (REPO / args.out).resolve()
        o.parent.mkdir(parents=True, exist_ok=True)
        prov = {"git": git_info(REPO), "argv": sys.argv, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "file_sha256": {f: file_sha(f) for f in ("analysis/r15_sim_toolslow.py", "analysis/throughput.py",
                                                         "analysis/load.py", "configs/agentload_analysis.yaml")}}
        o.write_text(json.dumps(sanitize({"definitions": measure_run.__doc__, "runs": rows, "provenance": prov}), indent=1) + "\n",
                     encoding="utf-8", newline="\n")
        print("wrote", o.as_posix())
    return 0


def cmd_plans(args) -> int:
    _, rcfg = load_cfg()
    rows = plan_check(rcfg)
    for r in rows:
        print(f"{r['mult']} seed {r['seed']}: {r['n_sessions']} sessions, sha256 {r['plan_sha256'][:16]}, control {r['control_dir']}: "
              f"byte-identical={bool(r['committed_byte_identical'])} equal-up-to-tool-ulp={bool(r['committed_equal_up_to_tool_ulp'])} "
              f"max rel tool diff {r['max_rel_tool_total_diff']:.2e} -> {'OK' if r['matches_control'] else 'MISMATCH'}")
    return 0 if all(r["matches_control"] for r in rows) else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--quick", action="store_true", help="1 exact and 2 simulator seeds per cell (plumbing check)")
    r.add_argument("--modes", nargs="*", default=None)
    r.add_argument("--cells", nargs="*", default=None, choices=list(CELLS))
    r.add_argument("--out", default=None, help=f"default {DEFAULT_OUT} ({QUICK_OUT} with --quick)")
    r.add_argument("--no-sens", action="store_true", help="skip the sensitivity runs")
    s = sub.add_parser("selfcheck")
    s.add_argument("--modes", nargs="*", default=None)
    sub.add_parser("plans")
    m = sub.add_parser("measure", help="the secondary / exploratory measures on GPU run dirs (frozen analysis helpers)")
    m.add_argument("--run-dirs", nargs="+", required=True)
    m.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        if not (1 <= args.workers <= 6):
            raise SystemExit("--workers must be in 1..6")
        return cmd_run(args)
    if args.cmd == "selfcheck":
        return cmd_selfcheck(args)
    if args.cmd == "measure":
        return cmd_measure(args)
    return cmd_plans(args)


if __name__ == "__main__":
    sys.exit(main())
