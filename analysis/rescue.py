"""RESCUE arm (plan items R1 and R4): the automatic per-run check and the registered verdict.

A rescue run is the BURST protocol (burst of 200 at t_b, 8700-s run) with a client gate that is uncapped until
``gate.t_on_s`` and then engages the registered cap ``n_cap``; over-cap sessions pause at their next tool-call boundary
and resume before new arrivals; the cap is released once both gate queues have been empty for ``release_hold_s``
(see :class:`agentload.config.GateCfg`, :mod:`agentload.gate`). Two subcommands::

  python -m analysis.rescue check-run RUN_DIR --e2-config FILE [--burst-plan PLAN_CSV] [--smoke] [--json-out FILE]
  python -m analysis.rescue verdict --rescue-runs RUN [...] --control-runs RUN [...] [--profile auto|r1|r4]
                                    [--e2-config FILE] [--prereg FILE] [--predictions DIR] [--params FILE]
                                    [--out-root DIR] [--name NAME]

INPUT FORMATS (the client-gate builder's design, plan R1 code_changes)
  requests.csv   + ``t_ready`` (the turn was ready to send: end of its tool time) and ``pause_s`` (pause before it, 0 if
                 none); a paused turn's request is outstanding at the client over [t_ready, t_send).
  sessions.csv   + ``n_pauses``, ``pause_s_total`` (an open pause counted up to t_end), ``pause_censored``.
  gate_events.csv  ``t_s, event, sid, cap, active, waiting, paused, pause_s``; events ``engage`` (cap set at t_on),
                 ``pause``, ``resume``, ``release`` (cap removed), ``cap`` (any other cap change) and ``pause_censored``
                 (the session ended while paused). Aliases of the column names are accepted (``_ALIASES``).
  meta.json      ``arm`` = rescue, ``gate_mode`` / ``gate.mode`` / ``outcome.gate.mode`` = rescue,
                 ``outcome.gate.t_engage`` / ``t_release``.
  The committed BURST / NOBURST controls (results/nova/e2_170933xx_*, e2_native_*) predate these columns; missing
  columns read as "no pause".

CHECK-RUN (run by the job glue after every rescue run; exit 0 = pass, 1 = fail)
  meta.arm == rescue; the config's and the meta's gate.mode == rescue; the run's gate block equals the --e2-config gate
  block (n_cap compared as the resolved cap); run length and burst equal the e2 config's; gate_events.csv has exactly one
  engage, within ``engage_within_s`` of t_on and at the cap; no pause before the engage or after a release; resumes never
  outnumber pauses per session; if more sessions were active at the engage than the cap, at least one pause; session
  conservation (every planned session that arrived was started, every started session completed, failed, or was still
  outstanding (in the engine, gated or paused) when the run ended, up to 3 sessions spawned in the last instant and never
  started (status pending, no t_end, no request); counts agree with meta.outcome and with requests.csv; the pause logs
  agree with each other: censored pauses in gate_events / sessions.csv / meta, per session n_pauses - pause_censored ==
  resume events, requests with a pause == resume events with a pause); the gate-log invariants
  (``gate_invariant_checks``: pause rows over the cap, no session waiting while a slot is free, the cap held once
  reached, at most one cap removal on the check grid after t_on + min_on and after an empty hold, meta pause / resume
  counts, no slot held or session queued after the end-of-run cancel, no controller error); with --burst-plan the
  plan.csv sha256 equals that committed BURST plan.csv. ``--smoke`` adds the
  smoke-job criteria of plan R1 (>= 10 pauses, >= 10 resumes, 0 request errors); ``--require-release`` asks for a
  release. BLINDING: the report is mechanical only (no hit fractions, latencies, completion counts or release outcome
  unless --smoke / --require-release), because the operator monitors only the check result until all cells of a rate
  have ended (plan R1 protocol).

THE REGISTERED PER-RUN RULE (plan R1 'Registered per-run rule'; R4 uses it with t_on 2100, so its VALID window is
[1800, 2100) and more than 50 outstanding at 2100 s). FROZEN in ``RULE``.
  FU-hit = share of completed (status ok) turns >= 2, attributed by completion time, with cached/prompt > 0.5.
  (a) VALID: FU-hit < 0.2 over [t_on - 300, t_on) AND more than 50 outstanding at t_on (outstanding = requests in flight
      + sessions waiting at the gate + paused sessions, the trap_v2 'outstanding' backlog with the pause intervals plan R1
      adds; computed here, see ``outstanding_step``). Otherwise INVALID, which counts against PASS.
  (b) RELEASED with t_rel <= 7200 (the first ``release`` gate event).
  (c) POST-GOOD over [t_rel + 300, 8700): every 300-s window has FU-hit >= 0.5 (windows tile the interval from its start;
      a remainder shorter than 300 s is covered by the window ending at 8700, so every instant lies in a full window);
      the whole interval has FU-hit > 0.8; its uncached-token rate is < 0.5 x the all-miss reference
      (meta.uncached_tokens_ref_resolved); the registered trap_v2 RECOVERED predicate holds over the last 300 s.
  RESCUED = a and b and c.  RELAPSE = any of those 300-s windows has FU-hit < 0.2 (defined whenever released).
  A window in which no follow-up turn completes has an undefined FU-hit: it fails (c) (counted in post_n_windows_nan)
  but is not a RELAPSE (no evidence of the all-miss state); an undefined VALID window makes the run INVALID.

THE REGISTERED DECISION RULE (plan R1 / R4 decision_rule; ``PROFILES``)
  R1 (sglang-fcfs-r1-rescue, 1.35 and 1.65 x, seeds 0-2): per rate cell PASS iff >= 2 of the 3 registered seeds are
  RESCUED and every same-seed committed BURST control is stuck. The no-shed drain claim is made if 1.35 x passes, 'at
  both test points' if 1.65 x passes too. REFUTED (a negative result) if >= 2 of the 6 runs RELAPSE or >= 2 of the 6 are
  not released by 7200 s. R4 (sglang-fcfs-r1-rescue-native, 4.0 x, seeds 0-2): PASS iff >= 2 of 3 RESCUED and every
  same-seed committed BURST control is stuck; >= 2 of 3 RELAPSE refutes persistence at the native pool. A missing seed
  counts against PASS (never for REFUTED); a cell with pairing / protocol problems does not count
  (``meets_valid_pairing``). REFUTED takes precedence over PASS (a cell that also meets PASS is listed). The NO-SHED part
  of a PASS claim needs 0 failed sessions in the counted runs (a failed session leaves the gate too, which is shedding);
  otherwise the verdict says the no-shed claim is withheld. 'Persists after release' is tested after the cap stopped
  binding (release needs both queues empty for the hold), so the claim is that the drained state sustains itself with
  control removed; each run records when the cap last held a session back (t_cap_last_binding) and the share of the
  post-release time with active >= n_cap (post_release_frac_active_ge_cap) and its maximum, descriptively.
  'Stuck' is not given a formula in the plan ('the same-seed committed BURST controls stay at hit 0'; 'stuck (already
  6/6)'). Operationalised here (``STUCK``, frozen): FU-hit over [t_on, 8700) < 0.2 AND the trap_v2 RECOVERED predicate
  false over the last 300 s. All six committed SGLang-300k BURST runs meet it.

PAIRING (common random numbers with the committed controls of the same seed and rate, cross-commit allow-list)
  BURST: plan.csv sha256 must be equal; NOBURST: its plan must equal the rescue plan without the burst sessions. The
  effective configs may differ only in the trap_v2 pairing allow-list plus meta.prereg_sha256, meta.prereg_file,
  meta.engine_label (checked through the label map) and meta.notes; the git commit may differ (not in the config).
  Resolved rate, lambda_miss, all-miss reference, hardware and burst time must be equal; BURST's burst spec too.

OUTPUTS of ``verdict`` (a new dir <out-root>/<name>/<timestamp>/): rescue_runs.csv (rule fields per rescue run),
rescue_windows.csv (the post-release 300-s windows), rescue_pairs.csv (rescue vs BURST vs NOBURST of the same seed: hit
over the same windows and user-facing costs: pause and admission waits, request waits, completed sessions),
rescue_costs.csv (one row per run and arm), rescue_trace.csv (60-s bins for the time-series figure), rescue_verdict.json,
rescue_t_rel_scoring.csv (with --predictions: each release time against the frozen simulator band of its rate, the union
of the 20-seed [min, max] and the exact-plan values, and against its seed's exact-plan prediction +- 600 s; ``T_REL_SCORING``,
descriptive), config.yaml / config_effective.yaml (analysis params) and meta.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from agentload.runmeta import build_meta, default_hardware, git_info, json_default, new_result_dir, write_meta

from . import prereg as prereg_mod
from .load import Run, load_run
from .params import AnalysisParams, load_params
from .throughput import backlog_at, backlog_mean, hit_stats, hit_value
from .trap_v2 import _ALLOWED_DIFF_EXACT, _ALLOWED_DIFF_PREFIXES, _flatten

NAN = float("nan")
ARM = "rescue"
MODE = "rescue"
GATE_EVENTS_FILE = "gate_events.csv"
DEFAULT_PARAMS = "configs/agentload_analysis.yaml"

# --------------------------------------------------------------------------------------------- frozen constants
RULE: Dict[str, Any] = {
    "fu_cached_frac_threshold": 0.5,       # a follow-up turn is a hit when cached / prompt > this
    "valid_window_s": 300.0,               # (a) FU-hit over [t_on - this, t_on) ...
    "valid_fu_hit_below": 0.2,             # ... < this
    "valid_outstanding_above": 50.0,       # (a) outstanding at t_on > this
    "release_by_s": 7200.0,                # (b) t_rel <= this
    "post_start_after_release_s": 300.0,   # (c) interval [t_rel + this, horizon)
    "post_window_s": 300.0,                # (c) window length
    "post_window_fu_hit_min": 0.5,         # (c) every window FU-hit >= this
    "post_interval_fu_hit_above": 0.8,     # (c) whole-interval FU-hit > this
    "post_uncached_rate_frac_below": 0.5,  # (c) uncached-token rate < this x all-miss reference
    "relapse_fu_hit_below": 0.2,           # RELAPSE: some window FU-hit < this
}
STUCK: Dict[str, Any] = {"fu_hit_below": 0.2, "from": "t_on", "and_not_recovered_end": True}

PROFILES: Dict[str, Dict[str, Any]] = {
    "r1": {"plan_item": "R1", "label": "sglang-fcfs-r1-rescue", "control_label": "sglang-fcfs-r1",
           "rate_mults": [1.35, 1.65], "seeds": [0, 1, 2], "t_on_s": 1800.0, "n_cap": 20, "horizon_s": 8700.0,
           "t_burst_s": 1200.0, "pass_min_rescued": 2, "require_controls_stuck": True, "primary_rate": 1.35,
           "refute_relapse_min": 2, "refute_unreleased_min": 2, "prediction_cell": "R1_rescue",
           "claims": {"primary": "no-shed drain of an established trap (1.35 x passes)",
                      "all": "no-shed drain at both test points (1.35 x and 1.65 x pass)",
                      "refuted": ">= 2 of 6 RELAPSE or >= 2 of 6 not released by 7200 s (negative result)"}},
    # R4 decision_rule: 'PASS if at least 2/3 runs are RESCUED. If at least 2/3 RELAPSE, persistence at the native pool
    # is refuted.' It names no release-count refutation, so none is applied. The same-seed BURST controls must be stuck,
    # as in R1 (fixed before the registration tag, review of bundle 3): a rescue of a run that would have recovered
    # anyway is no rescue. All three committed native 4.0 x BURST controls are stuck.
    # t_on 2100 (plan R4 said 2400): the lead's decision after the 2400-s bundle-3 prediction (13/20 RESCUED, below the plan's
    # 7/10 rethink threshold) was seen and before any rescue run; VALID moves to [1800, 2100) with > 50 outstanding at 2100 s.
    # The scored prediction is cell R4s_t2100 of results/r11_predict_rescue/20261030-195231 (tag r11-rescue-pred).
    "r4": {"plan_item": "R4", "label": "sglang-fcfs-r1-rescue-native", "control_label": "sglang-fcfs-r1-native",
           "rate_mults": [4.0], "seeds": [0, 1, 2], "t_on_s": 2100.0, "n_cap": 64, "horizon_s": 8700.0,
           "t_burst_s": 1200.0, "pass_min_rescued": 2, "require_controls_stuck": True, "primary_rate": 4.0,
           "refute_relapse_min": 2, "refute_unreleased_min": None, "prediction_cell": "R4s_t2100",
           "claims": {"primary": "no-shed drain at the native pool (4.0 x passes)",
                      "all": "no-shed drain at the native pool (4.0 x passes)",
                      "refuted": ">= 2 of 3 RELAPSE: persistence at the native pool refuted"}},
}
CHECK: Dict[str, Any] = {"engage_within_s": 10.0, "cancel_end_tolerance_s": 5.0, "arrival_end_tolerance_s": 1.0,
                         "max_not_started_at_end": 3, "release_grid_tol_s": 2.0, "release_hold_tol_s": 2.0,
                         "clock_early_tol_s": 0.05,     # asyncio may fire a timer up to one clock tick early (15.6 ms on Windows)
                         "smoke_min_pauses": 10, "smoke_min_resumes": 10, "smoke_max_request_errors": 0}
# Scoring of the GPU release times against the frozen simulator prediction (descriptive: it judges the simulator, not
# the rescue; plan S1). The band per rate is the UNION of the 20-seed [min, max] and the exact-plan values; each seed is
# also compared with its own exact-plan prediction within per_seed_tol_s. A perfect simulator puts one new run inside a
# 20-run [min, max] with probability 19/21 (about 0.905), so n_inside is reported against that expectation, not as a
# pass/fail.
T_REL_SCORING: Dict[str, Any] = {"mode": "mixed", "per_seed_tol_s": 600.0, "expected_inside_frac_per_run": 19.0 / 21.0}
DELAY_THRESHOLDS_S = (60.0, 300.0, 600.0)
COST_COHORT_S = 1800.0          # cost cohort: sessions arriving in [t_burst, t_burst + this)  (gate scope item 6)
TRACE_BIN_S = 60.0
RATE_TOL = 1e-9

_PAIR_ALLOWED_EXACT = tuple(_ALLOWED_DIFF_EXACT) + ("meta.prereg_sha256", "meta.prereg_file", "meta.engine_label",
                                                    "meta.notes")
_ALIASES = {"t_s": ("t_s", "t", "time_s"), "event": ("event", "kind", "type"), "sid": ("sid", "session"),
            "cap": ("cap", "n_cap", "gate_cap")}
_TERMINAL = ("completed", "failed", "cancelled")


# --------------------------------------------------------------------------------------------- small helpers
def _isnan(x: Any) -> bool:
    return not (isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) and x == x)


def _close(a: Any, b: Any, rel: float = 1e-9) -> bool:
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _sanitize(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, (float, np.floating)) and not np.isfinite(float(o)):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _numeric(df: pd.DataFrame, cols: Sequence[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


# --------------------------------------------------------------------------------------------- loading
def read_gate_events(run_dir: str | Path) -> Optional[pd.DataFrame]:
    """gate_events.csv normalised to columns ``t_s, event, sid, cap`` (+ the others as written), sorted by time; None if
    the file does not exist. A file without a time or an event column is an error."""
    path = Path(run_dir) / GATE_EVENTS_FILE
    if not path.exists():
        return None
    df = pd.read_csv(path) if path.stat().st_size > 0 else pd.DataFrame()
    ren = {}
    for canon, names in _ALIASES.items():
        if canon in df.columns:
            continue
        hit = next((n for n in names if n in df.columns), None)
        if hit is not None:
            ren[hit] = canon
    df = df.rename(columns=ren)
    if len(df.columns) == 0:
        df = pd.DataFrame(columns=["t_s", "event"])
    missing = [c for c in ("t_s", "event") if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: no {missing} column (columns: {list(df.columns)})")
    for c in ("sid", "cap"):
        if c not in df.columns:
            df[c] = np.nan
    _numeric(df, ("t_s", "sid", "cap", "active", "waiting", "paused", "pause_s"))
    df["event"] = df["event"].astype(str).str.strip().str.lower()
    return df.sort_values("t_s", kind="stable").reset_index(drop=True)


def load_rescue_run(run_dir: str | Path) -> Tuple[Run, Optional[pd.DataFrame]]:
    """The run (analysis.load) with the rescue columns numeric, and its gate events (None: no gate_events.csv)."""
    run = load_run(run_dir)
    _numeric(run.requests, ("t_ready", "pause_s"))
    if len(run.sessions):
        _numeric(run.sessions, ("n_pauses", "pause_s_total", "pause_censored", "gate_censored"))
    return run, read_gate_events(run_dir)


def gate_block(run: Run) -> Dict[str, Any]:
    return dict(run.cfg.get("gate") or {})


def gate_mode_records(run: Run) -> Dict[str, Any]:
    """Where the run's meta.json recorded the gate mode (the runtime record), source -> value."""
    m = run.meta
    out: Dict[str, Any] = {}
    og = (m.get("outcome") or {}).get("gate")
    if isinstance(og, dict) and "mode" in og:
        out["meta.outcome.gate.mode"] = og["mode"]
    if "gate_mode" in m:
        out["meta.gate_mode"] = m["gate_mode"]
    if isinstance(m.get("gate"), dict) and "mode" in m["gate"]:
        out["meta.gate.mode"] = m["gate"]["mode"]
    return out


def t_on_of(run: Run) -> Optional[float]:
    return _f(gate_block(run).get("t_on_s"))


def engage_release(events: Optional[pd.DataFrame]) -> Tuple[Optional[float], Optional[float]]:
    """(t of the first engage, t of the first release after it); None where absent."""
    if events is None or len(events) == 0:
        return None, None
    eng = events.loc[events["event"] == "engage", "t_s"]
    if not len(eng):
        return None, None
    t_eng = float(eng.iloc[0])
    rel = events.loc[(events["event"] == "release") & (events["t_s"] >= t_eng), "t_s"]
    return t_eng, (float(rel.iloc[0]) if len(rel) else None)


# --------------------------------------------------------------------------------------------- step functions
class Step:
    """Right-continuous step function f(t) = v[i] on [t[i], t[i+1]), 0 before the first event (the convention of
    analysis.windows.step_bins), with exact interval means through the cumulative area."""

    def __init__(self, t: np.ndarray, v: np.ndarray):
        self.t = np.asarray(t, dtype=float)
        self.v = np.asarray(v, dtype=float)
        self.A = np.concatenate([[0.0], np.cumsum(self.v[:-1] * np.diff(self.t))]) if len(self.t) else np.zeros(0)

    def area(self, x: Any) -> np.ndarray:
        x = np.atleast_1d(np.asarray(x, dtype=float))
        if len(self.t) == 0:
            return np.zeros(len(x))
        i = np.searchsorted(self.t, x, side="right") - 1
        j = np.maximum(i, 0)
        return np.where(i >= 0, self.A[j] + self.v[j] * (x - self.t[j]), 0.0)

    def mean(self, a: float, b: float) -> float:
        if not b > a:
            return NAN
        return float((self.area(b) - self.area(a))[0] / (b - a))

    def means(self, edges: np.ndarray) -> np.ndarray:
        ar = self.area(edges)
        return np.diff(ar) / np.diff(edges)

    def at(self, x: float) -> float:
        if len(self.t) == 0:
            return 0.0
        i = int(np.searchsorted(self.t, x, side="right")) - 1
        return float(self.v[i]) if i >= 0 else 0.0

    def max_on(self, a: float, b: float) -> float:
        """Max of f on [a, b)."""
        if len(self.t) == 0:
            return 0.0
        i0 = int(np.searchsorted(self.t, a, side="right"))
        i1 = int(np.searchsorted(self.t, b, side="left"))
        vals = [self.at(a)] + list(self.v[i0:i1])
        return float(max(vals))


def frac_at_or_above(st: "Step", a: float, b: float, thr: float) -> float:
    """Share of [a, b) during which the step function is >= thr."""
    if not b > a:
        return NAN
    inner = [float(x) for x in st.t if a < x < b]
    pts = [a] + inner + [b]
    tot = sum(x1 - x0 for x0, x1 in zip(pts[:-1], pts[1:]) if st.at(x0) >= thr)
    return float(tot / (b - a))


def active_step(run: Run, horizon: float) -> "Step":
    """Sessions holding a gate slot over [t_admit, t_end) (t_end missing: the horizon). Exact after a release (no
    session is paused then); during the capped period a paused session is still counted, so use it after release."""
    ses = run.sessions
    if len(ses) == 0 or "t_admit" not in ses.columns:
        return Step(np.zeros(0), np.zeros(0))
    a = pd.to_numeric(ses["t_admit"], errors="coerce")
    e = pd.to_numeric(ses["t_end"], errors="coerce").fillna(horizon)
    m = a.notna()
    return step_from_intervals([a[m].to_numpy(dtype=float)], [e[m].to_numpy(dtype=float)])


def step_from_intervals(starts: Sequence[np.ndarray], ends: Sequence[np.ndarray]) -> Step:
    """Count of open intervals [s, e) (+1 at s, -1 at e; +1 first at equal times; non-finite events dropped one by one,
    exactly as analysis.throughput.outstanding_events does)."""
    ts: List[np.ndarray] = []
    ds: List[np.ndarray] = []
    for s, e in zip(starts, ends):
        s, e = np.asarray(s, dtype=float), np.asarray(e, dtype=float)
        ts += [s, e]
        ds += [np.ones(len(s)), -np.ones(len(e))]
    if not ts:
        return Step(np.zeros(0), np.zeros(0))
    t, d = np.concatenate(ts), np.concatenate(ds)
    keep = np.isfinite(t)
    t, d = t[keep], d[keep]
    order = np.lexsort((-d, t))
    return Step(t[order], np.cumsum(d[order]))


def gate_wait_intervals(run: Run) -> Tuple[np.ndarray, np.ndarray]:
    """[arrival, admission) of sessions that waited at the gate (t_end if never admitted) -- throughput's rule."""
    ses = run.sessions
    if len(ses) == 0 or "gate_wait_s" not in ses.columns or "t_admit" not in ses.columns:
        return np.zeros(0), np.zeros(0)
    w = ses[ses["gate_wait_s"].fillna(0.0) > 0.0]
    t_out = w["t_admit"].where(w["t_admit"].notna(), w["t_end"])
    return w["arrival_s"].to_numpy(dtype=float), t_out.to_numpy(dtype=float)


def pause_intervals(run: Run, events: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Pause intervals (columns sid, t0, t1, source): [t_ready, t_send) of every request with pause_s > 0 ('request'),
    plus the pause still open when a session ended ('open': a sid with more pause than resume events, from its last
    pause to its pause_censored event or its t_end). Runs without the columns / events have none."""
    rows: List[pd.DataFrame] = []
    rq = run.requests
    if "pause_s" in rq.columns and "t_ready" in rq.columns:
        pr = rq[(rq["pause_s"].fillna(0.0) > 0.0) & rq["t_ready"].notna() & rq["t_send"].notna()]
        if len(pr):
            rows.append(pd.DataFrame({"sid": pr["sid"].to_numpy(dtype=float), "t0": pr["t_ready"].to_numpy(dtype=float),
                                      "t1": pr["t_send"].to_numpy(dtype=float), "source": "request"}))
    if events is not None and len(events) and events["sid"].notna().any():
        ev = events[events["sid"].notna()]
        t_end_by_sid = (run.sessions.set_index("sid")["t_end"].to_dict()
                        if len(run.sessions) and "sid" in run.sessions.columns else {})
        open_rows = []
        for sid, g in ev.groupby("sid"):
            n_p = int((g["event"] == "pause").sum())
            n_r = int((g["event"] == "resume").sum())
            if n_p > n_r:
                t_p = float(g.loc[g["event"] == "pause", "t_s"].iloc[-1])
                cens = g.loc[g["event"] == "pause_censored", "t_s"]
                t1 = float(cens.iloc[-1]) if len(cens) else _f(t_end_by_sid.get(sid))
                if t1 is None:
                    t1 = run.t_end_s
                open_rows.append({"sid": float(sid), "t0": t_p, "t1": max(t1, t_p), "source": "open"})
        if open_rows:
            rows.append(pd.DataFrame(open_rows))
    if not rows:
        return pd.DataFrame({"sid": [], "t0": [], "t1": [], "source": []})
    return pd.concat(rows, ignore_index=True)


def outstanding_step(run: Run, pauses: pd.DataFrame) -> Step:
    """Outstanding units: requests in flight [t_send, t_complete) (any status) + sessions waiting at the gate + paused
    sessions. Without pauses this is exactly analysis.throughput.outstanding_events (tested)."""
    rq = run.requests
    g0, g1 = gate_wait_intervals(run)
    starts = [rq["t_send"].to_numpy(dtype=float) if len(rq) else np.zeros(0), g0, pauses["t0"].to_numpy(dtype=float)]
    ends = [rq["t_complete"].to_numpy(dtype=float) if len(rq) else np.zeros(0), g1, pauses["t1"].to_numpy(dtype=float)]
    return step_from_intervals(starts, ends)


# --------------------------------------------------------------------------------------------- hit and rates
class FollowUps:
    """Sorted completion times of the ok follow-up turns (turn >= 2) and their hit flags, for fast window queries."""

    def __init__(self, run: Run, thr: float):
        r = run.requests
        ok = r[(r["status"] == "ok") & (r["turn"] >= 2)]
        prompt = ok["prompt_tokens"].where(ok["prompt_tokens"].notna(), ok["prompt_tokens_client"]).astype(float)
        cached = ok["cached_tokens"].fillna(0.0).astype(float)
        frac = np.where(prompt.to_numpy() > 0, cached.to_numpy() / np.where(prompt.to_numpy() > 0, prompt.to_numpy(), 1.0),
                        np.nan)
        self.available = bool(r["cached_tokens"].notna().any()) if "cached_tokens" in r.columns else False
        t = ok["t_complete"].to_numpy(dtype=float)
        order = np.argsort(t, kind="stable")
        self.t = t[order]
        hit = (frac > thr)[order]
        self.cs = np.concatenate([[0], np.cumsum(hit)])

    def hit(self, t0: float, t1: float) -> Tuple[float, int]:
        """(FU-hit over [t0, t1), number of follow-up turns); NaN if none or the server reports no cached counts."""
        lo = int(np.searchsorted(self.t, t0, side="left"))
        hi = int(np.searchsorted(self.t, t1, side="left"))
        n = hi - lo
        if n <= 0 or not self.available:
            return NAN, max(n, 0)
        return float((self.cs[hi] - self.cs[lo]) / n), n


def uncached_rate(run: Run, t0: float, t1: float) -> float:
    """Uncached prompt tokens/s of the ok turns completing in [t0, t1) (throughput.completion_rates' token estimator; a
    missing cached count is 0 once the run reports any; NaN if it reports none)."""
    r = run.requests
    if not t1 > t0 or "cached_tokens" not in r.columns or not r["cached_tokens"].notna().any():
        return NAN
    ok = r[(r["status"] == "ok") & (r["t_complete"] >= t0) & (r["t_complete"] < t1)]
    prompt = ok["prompt_tokens"].where(ok["prompt_tokens"].notna(), ok["prompt_tokens_client"]).astype(float)
    return float((prompt - ok["cached_tokens"].fillna(0.0).astype(float)).sum() / (t1 - t0))


def post_windows(t0: float, t1: float, w: float) -> List[Tuple[float, float]]:
    """300-s windows over [t0, t1): tiled from t0; a remainder shorter than w is covered by the window [t1 - w, t1).
    Empty if the interval is shorter than w."""
    if not (t1 - t0) >= w - 1e-9:
        return []
    n = int(math.floor((t1 - t0) / w + 1e-9))
    wins = [(t0 + k * w, t0 + (k + 1) * w) for k in range(n)]
    if t0 + n * w < t1 - 1e-6:
        wins.append((t1 - w, t1))
    return wins


def recovered_end(run: Run, p: AnalysisParams, out: Step) -> Dict[str, Any]:
    """The registered trap_v2 RECOVERED predicate over the last end_window_s of the run (hit by windows.hit_metric >
    recovered_hit_above AND backlog < recovered_backlog_below), with the outstanding backlog including pauses."""
    tp = p.trap_v2
    end = run.t_end_s
    ew = min(float(tp["end_window_s"]), max(end, 0.0))
    res: Dict[str, Any] = {"hit_end": NAN, "outstanding_end": NAN, "backlog_end": NAN, "recovered": False}
    if ew <= 0:
        return res
    res["hit_end"] = hit_value(hit_stats(run, p, end - ew, end + 1e-9), p)
    res["outstanding_end"] = out.mean(end - ew, end)
    res["backlog_end"] = backlog_mean(run.sessions, end - ew, end) if len(run.sessions) else NAN
    metric = str(tp.get("recovered_backlog_metric", "outstanding"))
    b = res["outstanding_end"] if metric == "outstanding" else res["backlog_end"]
    res["recovered"] = bool(not _isnan(res["hit_end"]) and res["hit_end"] > float(tp["recovered_hit_above"])
                            and not _isnan(b) and b < float(tp["recovered_backlog_below"]))
    return res


# --------------------------------------------------------------------------------------------- per-run rule
def evaluate_rescue_run(run: Run, events: Optional[pd.DataFrame], prof: Dict[str, Any], p: AnalysisParams,
                        rule: Dict[str, Any] = RULE) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Rule (a)-(c) for one rescue run. Returns the record and its post-release windows."""
    t_on = float(prof["t_on_s"])
    H = float(prof["horizon_s"])
    fu = FollowUps(run, float(rule["fu_cached_frac_threshold"]))
    pauses = pause_intervals(run, events)
    out = outstanding_step(run, pauses)
    t_eng, t_rel = engage_release(events)
    rec: Dict[str, Any] = {
        "run_dir": str(run.dir), "label": run.label, "seed": run.seed, "rate_mult": run.rate_mult, "arm": run.arm,
        "gate_mode_config": gate_block(run).get("mode"), "gate_mode_meta": gate_mode_records(run),
        "n_cap": run.gate_n_cap, "t_on_registered": t_on, "t_on_config": t_on_of(run), "t_engage": t_eng,
        "t_release": t_rel, "horizon_s": H, "t_end_s": run.t_end_s, "aborted": run.aborted,
        "has_gate_events": events is not None, "prereg_sha256": run.prereg_sha256, "hardware": run.hardware,
        "t0_unix": run.t0_unix}
    # (a) VALID at engage
    v0 = t_on - float(rule["valid_window_s"])
    rec["valid_fu_hit"], rec["valid_fu_n"] = fu.hit(v0, t_on)
    rec["outstanding_at_t_on"] = out.at(t_on)
    rec["outstanding_mean_valid_window"] = out.mean(v0, t_on)
    rec["sessions_in_system_at_t_on"] = backlog_at(run.sessions, t_on) if len(run.sessions) else NAN
    rec["valid_hit_ok"] = bool(not _isnan(rec["valid_fu_hit"]) and rec["valid_fu_hit"] < float(rule["valid_fu_hit_below"]))
    rec["valid_outstanding_ok"] = bool(rec["outstanding_at_t_on"] > float(rule["valid_outstanding_above"]))
    rec["valid"] = bool(rec["valid_hit_ok"] and rec["valid_outstanding_ok"])
    # (b) released by the deadline
    rec["released"] = t_rel is not None
    rec["released_by_deadline"] = bool(t_rel is not None and t_rel <= float(rule["release_by_s"]) + 1e-9)
    # (c) good after release
    ended_early = run.t_end_s < H - 1.0
    rec["run_ended_early"] = bool(ended_early)
    wins: List[Dict[str, Any]] = []
    for k in ("post_t0", "post_t1", "post_fu_hit", "post_fu_n", "post_uncached_rate", "post_uncached_ref",
              "post_uncached_rel", "post_min_window_fu_hit", "hit_end", "outstanding_end", "backlog_end"):
        rec[k] = NAN
    rec.update(post_n_windows=0, post_n_windows_nan=0, post_windows_ok=False, post_interval_ok=False,
               post_uncached_ok=False, recovered_end=False, post_good=False, relapse=None)
    rend = recovered_end(run, p, out)
    rec["hit_end"], rec["outstanding_end"], rec["backlog_end"] = rend["hit_end"], rend["outstanding_end"], rend["backlog_end"]
    rec["recovered_end"] = rend["recovered"]
    if t_rel is not None:
        a = t_rel + float(rule["post_start_after_release_s"])
        rec["post_t0"], rec["post_t1"] = a, H
        ws = post_windows(a, H, float(rule["post_window_s"]))
        for (w0, w1) in ws:
            h, n = fu.hit(w0, w1)
            wins.append({"run_dir": str(run.dir), "seed": run.seed, "rate_mult": run.rate_mult, "t0": w0, "t1": w1,
                         "fu_hit": h, "fu_n": n, "outstanding_mean": out.mean(w0, w1)})
        hs = [w["fu_hit"] for w in wins]
        rec["post_n_windows"] = len(wins)
        rec["post_n_windows_nan"] = int(sum(_isnan(h) for h in hs))
        finite = [h for h in hs if not _isnan(h)]
        rec["post_min_window_fu_hit"] = min(finite) if finite else NAN
        rec["post_windows_ok"] = bool(wins and all(not _isnan(h) and h >= float(rule["post_window_fu_hit_min"]) for h in hs))
        rec["relapse"] = bool(any(not _isnan(h) and h < float(rule["relapse_fu_hit_below"]) for h in hs))
        if H > a:
            rec["post_fu_hit"], rec["post_fu_n"] = fu.hit(a, H)
            rec["post_uncached_rate"] = uncached_rate(run, a, H)
        rec["post_interval_ok"] = bool(not _isnan(rec["post_fu_hit"])
                                       and rec["post_fu_hit"] > float(rule["post_interval_fu_hit_above"]))
        ref = run.uncached_tokens_ref_value
        rec["post_uncached_ref"] = NAN if ref is None else float(ref)
        if ref is not None and ref > 0 and not _isnan(rec["post_uncached_rate"]):
            rec["post_uncached_rel"] = rec["post_uncached_rate"] / float(ref)
            rec["post_uncached_ok"] = bool(rec["post_uncached_rel"] < float(rule["post_uncached_rate_frac_below"]))
        rec["post_good"] = bool(rec["post_windows_ok"] and rec["post_interval_ok"] and rec["post_uncached_ok"]
                                and rec["recovered_end"] and not ended_early)
    rec["rescued"] = bool(rec["valid"] and rec["released_by_deadline"] and rec["post_good"])
    if not rec["valid"]:
        rec["outcome"] = "INVALID"
    elif rec["rescued"]:
        rec["outcome"] = "RESCUED"
    elif rec["relapse"]:
        rec["outcome"] = "RELAPSE"
    elif not rec["released"]:
        rec["outcome"] = "NOT_RELEASED"
    elif not rec["released_by_deadline"]:
        rec["outcome"] = "RELEASED_LATE"
    else:
        rec["outcome"] = "NOT_GOOD_AFTER_RELEASE"
    # descriptive: recovery time t_recovered, THE definition shared with gate_control.rescue_measures (t_rec): the first
    # t = t_engage + k * 10 s whose window [t, t + 300) has FU-hit > 0.8 and mean outstanding < 20; pauses, gate
    tp = p.trap_v2
    rec["t_recovered"] = NAN
    if t_eng is not None:
        for t in np.arange(t_eng, H - 300.0 + 1e-9, 10.0):
            h, n = fu.hit(t, t + 300.0)
            if not _isnan(h) and h > float(tp["recovered_hit_above"]) and out.mean(t, t + 300.0) < float(tp["recovered_backlog_below"]):
                rec["t_recovered"] = float(t)
                break
    rec["t_recovered_after_engage"] = (rec["t_recovered"] - t_eng) if (t_eng is not None and not _isnan(rec["t_recovered"])) else NAN
    ps = step_from_intervals([pauses["t0"].to_numpy(dtype=float)], [pauses["t1"].to_numpy(dtype=float)])
    g0, g1 = gate_wait_intervals(run)
    gs = step_from_intervals([g0], [g1])
    rec["max_paused"] = ps.max_on(0.0, H)
    rec["max_gated"] = gs.max_on(0.0, H)
    rec["max_gated_plus_paused"] = step_from_intervals([pauses["t0"].to_numpy(dtype=float), g0],
                                                       [pauses["t1"].to_numpy(dtype=float), g1]).max_on(0.0, H)
    # descriptive: rule (c) is evaluated after the cap stopped binding (release needs both queues empty for the hold),
    # so 'persists after release' means 'the drained state sustains itself with control removed'. Recorded: when the
    # cap last held a session back before the release, and how close the uncapped run came to the cap afterwards.
    lim = t_rel if t_rel is not None else H
    st0 = np.concatenate([pauses["t0"].to_numpy(dtype=float), g0])
    st1 = np.concatenate([pauses["t1"].to_numpy(dtype=float), g1])
    mk = np.isfinite(st0) & (st0 < lim)
    rec["t_cap_last_binding"] = float(min(np.nanmax(st1[mk]), lim)) if mk.any() else NAN
    rec["release_after_last_binding_s"] = (float(t_rel) - rec["t_cap_last_binding"]
                                           if t_rel is not None and not _isnan(rec["t_cap_last_binding"]) else NAN)
    act = active_step(run, H)
    rec["post_release_max_active"] = act.max_on(t_rel, H) if t_rel is not None and H > t_rel else NAN
    rec["post_release_frac_active_ge_cap"] = (frac_at_or_above(act, t_rel, H, float(run.gate_n_cap))
                                              if t_rel is not None and H > t_rel and run.gate_n_cap is not None else NAN)
    st_s = run.sessions["status"].astype(str) if len(run.sessions) else pd.Series(dtype=str)
    rec["sessions_failed"] = int((st_s == "failed").sum())
    rec["requests_error"] = int((run.requests["status"] == "error").sum()) if len(run.requests) else 0
    if events is not None:
        rec["n_pause_events"] = int((events["event"] == "pause").sum())
        rec["n_resume_events"] = int((events["event"] == "resume").sum())
    return rec, wins


def burst_stuck(run: Run, prof: Dict[str, Any], p: AnalysisParams, rule: Dict[str, Any] = RULE) -> Dict[str, Any]:
    """STUCK of a BURST control: FU-hit over [t_on, horizon) < STUCK.fu_hit_below and RECOVERED false at the end."""
    fu = FollowUps(run, float(rule["fu_cached_frac_threshold"]))
    out = outstanding_step(run, pause_intervals(run, None))
    h, n = fu.hit(float(prof["t_on_s"]), float(prof["horizon_s"]))
    rend = recovered_end(run, p, out)
    return {"fu_hit_after_t_on": h, "fu_n_after_t_on": n, "recovered_end": rend["recovered"], "hit_end": rend["hit_end"],
            "outstanding_end": rend["outstanding_end"],
            "stuck": bool(not _isnan(h) and h < float(STUCK["fu_hit_below"]) and not rend["recovered"])}


# --------------------------------------------------------------------------------------------- costs and traces
def user_costs(run: Run, *, t_on: float, t_burst: Optional[float], horizon: float) -> Dict[str, Any]:
    """User-facing costs, computed the same way for every arm (columns a control lacks count as zero)."""
    ses, rq = run.sessions, run.requests
    st = ses["status"] if len(ses) else pd.Series(dtype=str)
    npz = ses["n_pauses"].fillna(0.0) if "n_pauses" in ses.columns else pd.Series(0.0, index=ses.index)
    pst = ses["pause_s_total"].fillna(0.0) if "pause_s_total" in ses.columns else pd.Series(0.0, index=ses.index)
    gw = ses["gate_wait_s"].fillna(0.0) if "gate_wait_s" in ses.columns else pd.Series(0.0, index=ses.index)
    n = int(len(ses))
    lat_all = rq["latency_s"].fillna(0.0) if "latency_s" in rq.columns else pd.Series(0.0, index=rq.index)
    ok = rq[rq["status"] == "ok"]
    ok_after = ok[(ok["t_complete"] >= t_on) & (ok["t_complete"] < horizon)]
    delay = gw + pst                                        # per session: admission wait + pauses (censored ones to t_end)
    done = ses[st == "completed"] if n else ses
    c: Dict[str, Any] = {
        "sessions_planned": run.meta.get("n_sessions_planned"), "sessions_started": n,
        "sessions_completed": int((st == "completed").sum()), "sessions_failed": int((st == "failed").sum()),
        "sessions_unfinished": int((st == "cancelled").sum()),
        "completed_frac": float((st == "completed").mean()) if n else NAN,
        "sessions_paused": int((npz > 0).sum()), "pauses_total": int(npz.sum()),
        "pause_hours": float(pst.sum() / 3600.0), "pause_s_per_session": float(pst.sum() / n) if n else NAN,
        "pause_s_per_paused_session": float(pst[npz > 0].mean()) if (npz > 0).any() else 0.0,
        "pause_s_max": float(pst.max()) if n else 0.0,
        "sessions_gated": int((gw > 0).sum()), "gate_wait_hours": float(gw.sum() / 3600.0),
        "gate_wait_s_per_session": float(gw.sum() / n) if n else NAN,
        "gate_wait_s_per_gated_session": float(gw[gw > 0].mean()) if (gw > 0).any() else 0.0,
        "gate_wait_s_max": float(gw.max()) if n else 0.0,
        "request_wait_hours": float(lat_all.sum() / 3600.0),
        # engine latency = t_send -> t_complete: it EXCLUDES the gate wait and the pauses (reported separately above)
        "engine_latency_mean_s_after_t_on": float(ok_after["latency_s"].mean()) if len(ok_after) else NAN,
        "session_duration_median_s": (float((done["t_end"] - done["arrival_s"]).median()) if len(done) else NAN),
        "delay_session_hours": float(delay.sum() / 3600.0),
        "sessions_gated_or_paused_at_end": int(((st == "cancelled") & (
            (ses["t_admit"].isna() if "t_admit" in ses.columns else False)
            | ((ses["pause_censored"].fillna(0) > 0) if "pause_censored" in ses.columns else False))).sum()) if n else 0,
        "requests_error": int((rq["status"] == "error").sum())}
    for thr in DELAY_THRESHOLDS_S:
        c[f"sessions_delayed_gt_{int(thr)}s"] = int((delay > thr).sum())
    c["wait_hours_total"] = c["pause_hours"] + c["gate_wait_hours"] + c["request_wait_hours"]
    if t_burst is not None and n:
        co = ses[(ses["arrival_s"] >= t_burst) & (ses["arrival_s"] < t_burst + COST_COHORT_S)]
        done = co[co["status"] == "completed"]
        c.update(cohort_t0=t_burst, cohort_t1=t_burst + COST_COHORT_S, cohort_sessions=int(len(co)),
                 cohort_completed_frac=float((co["status"] == "completed").mean()) if len(co) else NAN,
                 cohort_duration_median_s=float((done["t_end"] - done["arrival_s"]).median()) if len(done) else NAN)
    return c


def trace(run: Run, events: Optional[pd.DataFrame], arm: str, horizon: float, bin_s: float = TRACE_BIN_S) -> pd.DataFrame:
    """Per-bin FU-hit, latency, outstanding, in-flight, gated and paused sessions, and the cap in force (figure data)."""
    edges = np.arange(0.0, horizon + 1e-9, bin_s)
    if len(edges) < 2:
        return pd.DataFrame()
    fu = FollowUps(run, float(RULE["fu_cached_frac_threshold"]))
    pauses = pause_intervals(run, events)
    rq = run.requests
    infl = step_from_intervals([rq["t_send"].to_numpy(dtype=float)], [rq["t_complete"].to_numpy(dtype=float)])
    g0, g1 = gate_wait_intervals(run)
    gated = step_from_intervals([g0], [g1])
    paused = step_from_intervals([pauses["t0"].to_numpy(dtype=float)], [pauses["t1"].to_numpy(dtype=float)])
    out = outstanding_step(run, pauses)
    ok = rq[rq["status"] == "ok"]
    idx = np.searchsorted(edges, ok["t_complete"].to_numpy(dtype=float), side="right") - 1
    lat = ok["latency_s"].to_numpy(dtype=float)
    rows = []
    cap_ev = events[events["event"].isin(["engage", "release", "cap"])] if events is not None else None
    for j in range(len(edges) - 1):
        a, b = edges[j], edges[j + 1]
        h, n = fu.hit(a, b)
        sel = lat[idx == j]
        cap = NAN
        if cap_ev is not None and len(cap_ev):
            prev = cap_ev[cap_ev["t_s"] <= a]
            if len(prev):
                cap = _f(prev["cap"].iloc[-1]) or NAN
        rows.append({"t_start": a, "fu_hit": h, "fu_n": n, "latency_mean_s": float(sel.mean()) if len(sel) else NAN})
        rows[-1]["cap"] = cap
    df = pd.DataFrame(rows)
    df["outstanding_mean"] = out.means(edges)
    df["inflight_mean"] = infl.means(edges)
    df["gated_mean"] = gated.means(edges)
    df["paused_mean"] = paused.means(edges)
    df.insert(0, "arm", arm)
    df.insert(0, "seed", run.seed)
    df.insert(0, "rate_mult", run.rate_mult)
    df.insert(0, "run_dir", str(run.dir))
    return df


# --------------------------------------------------------------------------------------------- pairing
def cross_commit_config_diff(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    """Config keys that differ beyond the cross-commit allow-list (see the module docstring)."""
    fa, fb = _flatten(a), _flatten(b)
    return [k for k in sorted(set(fa) | set(fb)) if fa.get(k, "<absent>") != fb.get(k, "<absent>")
            and k not in _PAIR_ALLOWED_EXACT
            and not any(k == pre.rstrip(".") or k.startswith(pre) for pre in _ALLOWED_DIFF_PREFIXES)]


def _plan_rows(path: Path, drop_burst: bool) -> Optional[List[Tuple[str, ...]]]:
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if drop_burst and "origin" in df.columns:
        df = df[df["origin"] != "burst"]
    cols = [c for c in ("origin", "idx", "arrival_s", "n_turns", "tool_time_total_s") if c in df.columns]
    return [tuple(r) for r in df[cols].itertuples(index=False)]


def pairing_problems(rescue: Run, control: Run, arm: str, expected_label: str) -> List[str]:
    """Why ``control`` (arm burst | noburst) is not a valid common-random-number partner of ``rescue``."""
    probs: List[str] = []
    if control.arm != arm:
        probs.append(f"{arm}: meta.arm is {control.arm!r}")
    if control.label != expected_label:
        probs.append(f"{arm}: label {control.label!r} != expected control label {expected_label!r}")
    if control.seed != rescue.seed:
        probs.append(f"{arm}: seed {control.seed} != {rescue.seed}")
    if not _close(control.rate_mult, rescue.rate_mult):
        probs.append(f"{arm}: rate_mult {control.rate_mult} != {rescue.rate_mult}")
    diff = cross_commit_config_diff(rescue.cfg, control.cfg)
    if diff:
        probs.append(f"{arm}: configs differ in {diff}")
    for name, x, y in (("resolved rate", rescue.lam, control.lam), ("lambda_miss", rescue.lambda_ref_value, control.lambda_ref_value),
                       ("all-miss uncached reference", rescue.uncached_tokens_ref_value, control.uncached_tokens_ref_value)):
        if (x is None) != (y is None) or (x is not None and not _close(x, y, 1e-12)):
            probs.append(f"{arm}: different {name} ({x} vs {y})")
    if str(rescue.hardware) != str(control.hardware):
        probs.append(f"{arm}: different hardware ({rescue.hardware!r} vs {control.hardware!r})")
    if rescue.t_burst_ref != control.t_burst_ref:
        probs.append(f"{arm}: different burst reference time ({rescue.t_burst_ref} vs {control.t_burst_ref})")
    rp, cp = Path(rescue.dir) / "plan.csv", Path(control.dir) / "plan.csv"
    if arm == "burst":
        if (rescue.cfg.get("arrivals") or {}).get("burst") != (control.cfg.get("arrivals") or {}).get("burst"):
            probs.append("burst: different burst specification")
        if not rp.exists() or not cp.exists():
            probs.append(f"burst: plan.csv missing ({'rescue' if not rp.exists() else 'control'})")
        elif file_sha256(rp) != file_sha256(cp):
            probs.append(f"burst: plan.csv sha256 differs ({file_sha256(rp)[:12]} vs {file_sha256(cp)[:12]})")
        if control.gate_n_cap is not None:
            probs.append(f"burst: control ran with a gate cap {control.gate_n_cap}")
    else:
        if (control.cfg.get("arrivals") or {}).get("burst"):
            probs.append("noburst: control has a burst configured")
        a, b = _plan_rows(rp, drop_burst=True), _plan_rows(cp, drop_burst=False)
        if a is None or b is None:
            probs.append(f"noburst: plan.csv missing ({'rescue' if a is None else 'control'})")
        elif a != b:
            probs.append("noburst: control plan != rescue plan without its burst sessions")
    return probs


def control_label_for(prof: Optional[Dict[str, Any]], rescue_label: str, override: Optional[str] = None) -> str:
    if override:
        return override
    if prof is not None:
        return str(prof["control_label"])
    return rescue_label.replace("-rescue", "", 1)


# --------------------------------------------------------------------------------------------- protocol / registration
def e2_gate_problems(run: Run, e2: Dict[str, Any]) -> List[str]:
    """The run's gate block against the e2 config's (every key but n_cap equal; n_cap as the resolved cap)."""
    probs: List[str] = []
    ref = dict(e2.get("gate") or {})
    got = gate_block(run)
    if ref.get("mode") != MODE:
        probs.append(f"--e2-config gate.mode is {ref.get('mode')!r}, not {MODE!r}")
    for k in sorted((set(ref) | set(got)) - {"n_cap"}):
        if ref.get(k, "<absent>") != got.get(k, "<absent>"):
            probs.append(f"gate.{k}: run {got.get(k, '<absent>')!r} != e2 config {ref.get(k, '<absent>')!r}")
    ncap = ref.get("n_cap")
    if isinstance(ncap, int) and not isinstance(ncap, bool):
        if run.gate_n_cap != ncap:
            probs.append(f"resolved cap {run.gate_n_cap} != e2 config gate.n_cap {ncap}")
    elif ncap is not None and str(got.get("n_cap")) != str(ncap):
        probs.append(f"gate.n_cap: run {got.get('n_cap')!r} != e2 config {ncap!r}")
    rd, ed = (run.cfg.get("run") or {}).get("duration_s"), (e2.get("run") or {}).get("duration_s")
    if ed is not None and not _close(rd, ed):
        probs.append(f"run.duration_s {rd} != e2 config {ed}")
    rb, eb = (run.cfg.get("arrivals") or {}).get("burst"), (e2.get("arrivals") or {}).get("burst")
    if eb is not None:
        if not rb or any(not _close(rb.get(k), eb.get(k)) for k in ("n", "t_s", "width_s") if k in eb):
            probs.append(f"arrivals.burst {rb} != e2 config {eb}")
    return probs


def registration_blockers(pr: Dict[str, Any], prov: Dict[str, Any], run: Run) -> List[str]:
    """Why a rescue run cannot count towards a DECISIVE verdict under the rescue registration ``pr`` (empty = bound).
    The rescue analogue of analysis.prereg.run_blockers (which judges the arm by its cap and so refuses a rescue run)."""
    inp, m, proto = pr.get("inputs") or {}, pr.get("measured") or {}, pr.get("protocol") or {}
    out: List[str] = []
    if run.label != inp.get("engine_cell_label"):
        out.append(f"label {run.label!r} != registered cell {inp.get('engine_cell_label')!r}")
    if not prereg_mod.mult_is_registered(pr, run.rate_mult):
        out.append(f"rate_mult {run.rate_mult} not in the registered lambda_mults {prereg_mod.registered_mults(pr)}")
    if run.lambda_ref_value is None or not _close(run.lambda_ref_value, m.get("lambda_ref"), 1e-6):
        out.append(f"lambda_ref {run.lambda_ref_value} != registered {m.get('lambda_ref')}")
    if run.uncached_tokens_ref_value is None or not _close(run.uncached_tokens_ref_value, m.get("all_miss_uncached_tokens_per_s"), 1e-6):
        out.append(f"uncached_tokens_ref {run.uncached_tokens_ref_value} != registered {m.get('all_miss_uncached_tokens_per_s')}")
    if m.get("hardware") is not None and str(run.hardware) != str(m["hardware"]):
        out.append(f"hardware {run.hardware!r} != registered {m['hardware']!r}")
    if m.get("n_cap") is not None and run.gate_n_cap != m.get("n_cap"):
        out.append(f"gate cap {run.gate_n_cap} != registered n_cap {m.get('n_cap')}")
    if proto.get("duration_s") is not None and not _close((run.cfg.get("run") or {}).get("duration_s"), proto["duration_s"]):
        out.append(f"run.duration_s {(run.cfg.get('run') or {}).get('duration_s')} != registered {proto['duration_s']}")
    if proto.get("t_burst_s") is not None and (run.t_burst_ref is None or not _close(run.t_burst_ref, proto["t_burst_s"])):
        out.append(f"burst time {run.t_burst_ref} != registered {proto['t_burst_s']}")
    bcfg = (run.cfg.get("arrivals") or {}).get("burst")
    if not bcfg or not _close(bcfg.get("n"), proto.get("burst_n")) or not _close(bcfg.get("width_s"), proto.get("burst_width_s")):
        out.append(f"burst spec {bcfg} != registered n={proto.get('burst_n')} width={proto.get('burst_width_s')}")
    pg = proto.get("gate")
    if isinstance(pg, dict):
        if pg.get("mode") != MODE:
            out.append(f"registration protocol.gate.mode is {pg.get('mode')!r}, not {MODE!r}")
        got = gate_block(run)
        for k in sorted((set(pg) | set(got)) - {"n_cap"}):
            if pg.get(k, "<absent>") != got.get(k, "<absent>"):
                out.append(f"gate.{k}: run {got.get(k, '<absent>')!r} != registered {pg.get(k, '<absent>')!r}")
    else:
        out.append("registration has no protocol.gate block (not a rescue registration)")
    if run.prereg_sha256 != prov.get("sha256"):
        out.append(f"run not bound to this file (meta.prereg_sha256={run.prereg_sha256!r}, file sha256={prov.get('sha256')!r})")
    t0, last = run.t0_unix, prov.get("git_last_commit_unix")
    if t0 is None or last is None:
        out.append("run start time or registration commit time unknown")
    elif not last < t0:
        out.append(f"registration committed at {last} but the run started at {t0}: the file does not predate the run")
    return out


def resolve_profile(name: str, labels: Sequence[str]) -> Tuple[str, Dict[str, Any]]:
    if name != "auto":
        if name not in PROFILES:
            raise ValueError(f"--profile must be auto|{'|'.join(PROFILES)}, got {name!r}")
        return name, PROFILES[name]
    hits = {k for lab in set(labels) for k, v in PROFILES.items() if v["label"] == lab}
    if len(hits) != 1:
        raise ValueError(f"--profile auto: rescue labels {sorted(set(labels))} do not map to exactly one registered "
                         f"profile ({ {k: v['label'] for k, v in PROFILES.items()} }); pass --profile")
    k = hits.pop()
    return k, PROFILES[k]


# --------------------------------------------------------------------------------------------- verdict
def verdict(rescue_dirs: Sequence[str], control_dirs: Sequence[str], p: AnalysisParams, *, profile: str = "auto",
            e2_cfg: Optional[Dict[str, Any]] = None, prereg_path: Optional[str] = None,
            control_label: Optional[str] = None, predictions: Optional[str] = None
            ) -> Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]:
    loaded = [load_rescue_run(d) for d in rescue_dirs]
    pname, prof = resolve_profile(profile, [r.label for r, _ in loaded])
    ctl_label = control_label_for(prof, prof["label"], control_label)
    controls: Dict[Tuple[str, float, int, str], List[Run]] = {}
    for d in control_dirs:
        c = load_run(d)
        controls.setdefault((c.label, round(float(c.rate_mult or 0), 9), c.seed, c.arm), []).append(c)
    H, t_on, tb = float(prof["horizon_s"]), float(prof["t_on_s"]), float(prof["t_burst_s"])
    pr = prov = None
    if prereg_path:
        pr = prereg_mod.load_prereg(prereg_path)
        prov = prereg_mod.file_provenance(prereg_path)

    recs, wins, pairs, costs, traces = [], [], [], [], []
    rejected: List[Dict[str, Any]] = []
    for run, ev in loaded:
        why = []
        if run.arm != ARM:
            why.append(f"meta.arm is {run.arm!r}, not {ARM!r} (a run is never relabelled)")
        modes = gate_mode_records(run)
        if gate_block(run).get("mode") != MODE or not modes or any(v != MODE for v in modes.values()):
            why.append(f"gate mode not rescue (config {gate_block(run).get('mode')!r}, meta {modes})")
        if run.label != prof["label"]:
            why.append(f"label {run.label!r} is not the registered cell {prof['label']!r}")
        if not any(_close(run.rate_mult, m) for m in prof["rate_mults"]):
            why.append(f"rate_mult {run.rate_mult} not registered {prof['rate_mults']}")
        if run.seed not in prof["seeds"]:
            why.append(f"seed {run.seed} not registered {prof['seeds']}")
        if why:
            rejected.append({"run_dir": str(run.dir), "reasons": why})
            continue
        rec, w = evaluate_rescue_run(run, ev, prof, p)
        proto: List[str] = []
        if rec["t_on_config"] is None or not _close(rec["t_on_config"], t_on):
            proto.append(f"gate.t_on_s {rec['t_on_config']} != registered {t_on}")
        if rec["n_cap"] != prof["n_cap"]:
            proto.append(f"resolved cap {rec['n_cap']} != registered {prof['n_cap']}")
        if ev is None:
            proto.append("gate_events.csv missing")
        elif rec["t_engage"] is None or abs(rec["t_engage"] - t_on) > float(CHECK["engage_within_s"]):
            proto.append(f"engage at {rec['t_engage']} not within {CHECK['engage_within_s']} s of t_on {t_on}")
        if e2_cfg is not None:
            proto += e2_gate_problems(run, e2_cfg)
        rec["protocol_problems"] = proto
        rec["registration_blockers"] = registration_blockers(pr, prov, run) if pr is not None else None
        # paired controls
        key = (ctl_label, round(float(run.rate_mult), 9), run.seed)
        pair_probs: List[str] = []
        ctl: Dict[str, Optional[Run]] = {}
        for arm in ("burst", "noburst"):
            got = controls.get(key + (arm,), [])
            if len(got) > 1:
                pair_probs.append(f"{arm}: {len(got)} control runs for seed {run.seed} at {run.rate_mult} x")
            ctl[arm] = got[0] if got else None
            if ctl[arm] is None:
                pair_probs.append(f"{arm}: no committed control {ctl_label} {run.rate_mult} x seed {run.seed}")
            else:
                pair_probs += pairing_problems(run, ctl[arm], arm, ctl_label)
        rec["pairing_problems"] = pair_probs
        b = ctl["burst"]
        st = burst_stuck(b, prof, p) if b is not None else None
        rec["burst_control_dir"] = str(b.dir) if b is not None else None
        rec["noburst_control_dir"] = str(ctl["noburst"].dir) if ctl["noburst"] is not None else None
        rec["burst_stuck"] = None if st is None else st["stuck"]
        rec["burst_fu_hit_after_t_on"] = NAN if st is None else st["fu_hit_after_t_on"]
        recs.append(rec)
        wins += w
        # pairs and costs over the same windows
        cmp0, cmp1 = (rec["post_t0"], H) if rec["released"] and not _isnan(rec["post_t0"]) else (t_on, H)
        prow: Dict[str, Any] = {"rate_mult": run.rate_mult, "seed": run.seed, "rescue_outcome": rec["outcome"],
                                "t_engage": rec["t_engage"], "t_release": rec["t_release"], "cmp_t0": cmp0, "cmp_t1": cmp1}
        for arm, r_, e_ in (("rescue", run, ev), ("burst", ctl["burst"], None), ("noburst", ctl["noburst"], None)):
            if r_ is None:
                continue
            fu = FollowUps(r_, float(RULE["fu_cached_frac_threshold"]))
            o = outstanding_step(r_, pause_intervals(r_, e_))
            prow[f"{arm}_fu_hit_valid_window"] = fu.hit(t_on - float(RULE["valid_window_s"]), t_on)[0]
            prow[f"{arm}_fu_hit_cmp"] = fu.hit(cmp0, cmp1)[0]
            prow[f"{arm}_outstanding_mean_cmp"] = o.mean(cmp0, cmp1)
            okr = r_.requests[(r_.requests["status"] == "ok") & (r_.requests["t_complete"] >= cmp0) & (r_.requests["t_complete"] < cmp1)]
            prow[f"{arm}_engine_latency_mean_s_cmp"] = float(okr["latency_s"].mean()) if len(okr) else NAN
            cst = user_costs(r_, t_on=t_on, t_burst=tb, horizon=H)
            for k in ("sessions_completed", "completed_frac", "sessions_unfinished", "sessions_failed", "pause_hours",
                      "pause_s_per_session", "gate_wait_hours", "gate_wait_s_per_session", "request_wait_hours",
                      "wait_hours_total", "delay_session_hours", "sessions_delayed_gt_60s", "sessions_delayed_gt_300s",
                      "sessions_delayed_gt_600s", "sessions_gated_or_paused_at_end", "session_duration_median_s",
                      "cohort_completed_frac", "cohort_duration_median_s"):
                prow[f"{arm}_{k}"] = cst.get(k)
            costs.append({"run_dir": str(r_.dir), "label": r_.label, "rate_mult": r_.rate_mult, "seed": r_.seed, "arm": arm,
                          **cst})
            traces.append(trace(r_, e_, arm, H))
        pairs.append(prow)

    cells, fam = _cells(recs, prof)
    t_rel_df, t_rel_doc = score_t_rel(recs, predictions, prof) if predictions else (pd.DataFrame(), None)
    decisive = bool(pr is not None and prov is not None and prov.get("committed_clean")
                    and all(not r["registration_blockers"] for r in recs) and recs)
    doc = {
        "schema": "rescue_verdict_v1", "profile": pname, "plan_item": prof["plan_item"],
        "registered": {k: v for k, v in prof.items() if k != "claims"}, "claims_text": prof["claims"],
        "rule": RULE, "stuck_definition": STUCK, "check": CHECK,
        "trap_v2_recovered": {k: p.trap_v2[k] for k in ("recovered_hit_above", "recovered_backlog_below",
                                                         "recovered_backlog_metric", "end_window_s")},
        "hit_metric": p.w["hit_metric"], "control_label": ctl_label,
        "cells": cells, "family": fam, "t_rel_scoring": t_rel_doc,
        "runs": [{k: r[k] for k in ("run_dir", "rate_mult", "seed", "outcome", "valid", "released", "released_by_deadline",
                                    "post_good", "relapse", "rescued", "t_engage", "t_release", "burst_stuck",
                                    "protocol_problems", "pairing_problems", "registration_blockers")} for r in recs],
        "rejected_runs": rejected,
        "prereg": None if pr is None else {"provenance": prov, "status": pr.get("status"),
                                           "engine_cell_label": (pr.get("inputs") or {}).get("engine_cell_label")},
        "decisive": decisive,
        "decisive_note": ("decisive needs --prereg with a committed, clean rescue registration and every counted run bound "
                          "to it (sha256, started after its last commit, registered label / rate / references / cap / gate "
                          "block); otherwise the verdict is exploratory"),
    }
    frames = {"rescue_runs": pd.DataFrame([{k: (json.dumps(_sanitize(v)) if isinstance(v, (list, dict)) else v)
                                            for k, v in r.items()} for r in recs]),
              "rescue_windows": pd.DataFrame(wins), "rescue_pairs": pd.DataFrame(pairs),
              "rescue_costs": pd.DataFrame(costs), "rescue_t_rel_scoring": t_rel_df,
              "rescue_trace": pd.concat([t for t in traces if len(t)], ignore_index=True) if any(len(t) for t in traces)
              else pd.DataFrame()}
    return doc, frames


def score_t_rel(recs: List[Dict[str, Any]], pred_dir: str | Path, prof: Dict[str, Any],
                scoring: Dict[str, Any] = T_REL_SCORING) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Each rescue run's release time against the frozen simulator prediction (``T_REL_SCORING``): the union band
    [min(20-seed min, exact-plan values), max(20-seed max, exact-plan values)] of its rate, and its own seed's
    exact-plan prediction within per_seed_tol_s. A run that was not released is outside both. Descriptive only."""
    d = Path(pred_dir)
    mode, cell = str(scoring["mode"]), str(prof["prediction_cell"])
    fc, fr = d / f"cells_{mode}.csv", d / f"runs_{mode}.csv"
    cells, runs = pd.read_csv(fc), pd.read_csv(fr)
    cells, runs = cells[cells["cell"] == cell], runs[(runs["cell"] == cell) & (runs["kind"] == "exact")]
    tol = float(scoring["per_seed_tol_s"])
    rows = []
    for r in recs:
        m = float(r["rate_mult"])
        c = cells[np.isclose(cells["mult"].astype(float), m)]
        ex = runs[np.isclose(runs["mult"].astype(float), m)]
        exv = pd.to_numeric(ex["t_rel"], errors="coerce").dropna()
        lo = float(c["t_rel_min"].iloc[0]) if len(c) else NAN
        hi = float(c["t_rel_max"].iloc[0]) if len(c) else NAN
        ulo = float(np.nanmin([lo, *exv.tolist()])) if (len(exv) or not _isnan(lo)) else NAN
        uhi = float(np.nanmax([hi, *exv.tolist()])) if (len(exv) or not _isnan(hi)) else NAN
        sp = pd.to_numeric(ex.loc[ex["seed"].astype(int) == int(r["seed"]), "t_rel"], errors="coerce").dropna()
        pred = float(sp.iloc[0]) if len(sp) else NAN
        g = r.get("t_release")
        g = None if g is None or _isnan(g) else float(g)
        rows.append({"rate_mult": m, "seed": r["seed"], "run_dir": r["run_dir"], "gpu_t_rel": g, "band_min": lo,
                     "band_max": hi, "union_min": ulo, "union_max": uhi, "exact_pred_t_rel": pred,
                     "delta_vs_exact_s": (g - pred) if g is not None and not _isnan(pred) else NAN,
                     "inside_band": bool(g is not None and lo <= g <= hi),
                     "inside_union": bool(g is not None and ulo <= g <= uhi),
                     "within_tol_of_exact": bool(g is not None and not _isnan(pred) and abs(g - pred) <= tol)})
    df = pd.DataFrame(rows)
    n = len(df)
    summ = {"scoring": dict(scoring), "prediction_cell": cell, "files": {str(fc): file_sha256(fc), str(fr): file_sha256(fr)},
            "n_scored": n, "n_inside_union": int(df["inside_union"].sum()) if n else 0,
            "n_inside_band": int(df["inside_band"].sum()) if n else 0,
            "expected_inside_if_simulator_exact": n * float(scoring["expected_inside_frac_per_run"]),
            "n_within_tol_of_exact": int(df["within_tol_of_exact"].sum()) if n else 0,
            "median_delta_vs_exact_s": float(df["delta_vs_exact_s"].median()) if n else NAN}
    return df, summ


def _cells(recs: List[Dict[str, Any]], prof: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []
    seeds = list(prof["seeds"])
    for m in prof["rate_mults"]:
        rs = [r for r in recs if _close(r["rate_mult"], m)]
        by_seed: Dict[int, List[Dict[str, Any]]] = {}
        for r in rs:
            by_seed.setdefault(int(r["seed"]), []).append(r)
        dup = sorted(s for s, v in by_seed.items() if len(v) > 1)
        per: Dict[str, Any] = {}
        for s in seeds:
            v = by_seed.get(s)
            if not v:
                per[str(s)] = {"present": False}
                continue
            r = v[0]
            per[str(s)] = {"present": True, "outcome": r["outcome"], "rescued": r["rescued"], "valid": r["valid"],
                           "released_by_deadline": r["released_by_deadline"], "relapse": r["relapse"],
                           "sessions_failed": r.get("sessions_failed", 0),
                           "t_release": r["t_release"], "burst_stuck": r["burst_stuck"],
                           "problems": r["protocol_problems"] + r["pairing_problems"] + (["duplicate run"] if s in dup else [])}
        present = [per[str(s)] for s in seeds if per[str(s)]["present"]]
        n_resc = sum(bool(x["rescued"]) for x in present)
        # the same-seed BURST control of every rescue run present must be stuck (a missing rescue run has no pair)
        not_stuck = [s for s in seeds if per[str(s)]["present"] and per[str(s)]["burst_stuck"] is not True]
        stuck_all = bool(present and not not_stuck)
        rule_met = bool(n_resc >= int(prof["pass_min_rescued"]) and (stuck_all or not prof["require_controls_stuck"]))
        probs = {s: v["problems"] for s, v in per.items() if v.get("present") and v["problems"]}
        n_miss = len(seeds) - len(present)
        if rule_met:
            diag = "PASS" if not probs else "PASS by the rule but pairing / protocol problems"
            diag += f" ({n_miss} registered seed(s) missing)" if n_miss else ""
        else:
            diag = f"FAIL: {n_resc} of {len(seeds)} registered seeds RESCUED (need {prof['pass_min_rescued']})"
            diag += f"; {n_miss} seed(s) missing" if n_miss else ""
            if prof["require_controls_stuck"] and not_stuck:
                diag += f"; BURST control not stuck or missing for seed(s) {not_stuck}"
        cells.append({
            "rate_mult": m, "seeds": per, "n_registered_seeds": len(seeds), "n_present": len(present),
            "n_missing": len(seeds) - len(present), "complete": len(present) == len(seeds),
            "n_rescued": n_resc, "n_valid": sum(bool(x["valid"]) for x in present),
            "n_invalid": sum(not x["valid"] for x in present),
            "n_relapse": sum(x["relapse"] is True for x in present),
            "n_sessions_failed": int(sum(int(x.get("sessions_failed") or 0) for x in present)),
            "n_not_released_by_deadline": sum(not x["released_by_deadline"] for x in present),
            "burst_controls_stuck_all": stuck_all, "burst_controls_not_stuck": not_stuck,
            "require_controls_stuck": prof["require_controls_stuck"],
            "meets": rule_met, "problems": probs, "meets_valid_pairing": bool(rule_met and not probs), "diagnosis": diag})
    n_rel = sum(c["n_relapse"] for c in cells)
    n_unrel = sum(c["n_not_released_by_deadline"] for c in cells)
    ref_rel = n_rel >= int(prof["refute_relapse_min"])
    ref_unrel = prof["refute_unreleased_min"] is not None and n_unrel >= int(prof["refute_unreleased_min"])
    by_rate = {c["rate_mult"]: c for c in cells}
    prim = by_rate.get(prof["primary_rate"])
    primary_pass = bool(prim and prim["meets_valid_pairing"])
    all_pass = bool(cells and all(c["meets_valid_pairing"] for c in cells))
    refuted = bool(ref_rel or ref_unrel)
    n_failed = int(sum(c["n_sessions_failed"] for c in cells))
    no_shed = n_failed == 0
    passing = [c["rate_mult"] for c in cells if c["meets_valid_pairing"]]
    if refuted:                                   # REFUTED takes precedence over PASS (registered precedence)
        v = "REFUTED" + (f" (takes precedence over PASS; cell(s) {passing} also meet the PASS rule, reported)"
                         if passing else "")
    elif all_pass or primary_pass:
        v = "PASS: " + prof["claims"]["all" if all_pass else "primary"]
        if not no_shed:                           # sessions that fail drain the gate too: that is shedding, not a drain
            v += f" -- the no-shed part of the claim is WITHHELD: {n_failed} sessions failed in the counted runs"
    else:
        v = "NOT SHOWN"
    fam = {"n_runs": sum(c["n_present"] for c in cells), "n_relapse": n_rel, "n_not_released_by_deadline": n_unrel,
           "refuted_by_relapse": bool(ref_rel), "refuted_by_unreleased": bool(ref_unrel), "refuted": refuted,
           "refuted_takes_precedence": True, "cells_meeting_pass": passing,
           "primary_rate_pass": primary_pass, "all_rates_pass": all_pass, "n_sessions_failed": n_failed,
           "no_shed": no_shed, "complete": all(c["complete"] for c in cells), "verdict": v}
    return cells, fam


# --------------------------------------------------------------------------------------------- check-run
def _active_at(ses: pd.DataFrame, t: float) -> int:
    if len(ses) == 0 or "t_admit" not in ses.columns:
        return 0
    adm = ses["t_admit"].to_numpy(dtype=float)
    te = ses["t_end"].to_numpy(dtype=float)
    return int(np.sum((adm <= t) & ~(te <= t)))


def conservation(run: Run, events: Optional[pd.DataFrame], tol_end: float, tol_arr: float
                 ) -> Tuple[List[str], Dict[str, int]]:
    """Session conservation problems (empty = conserved) and the end-of-run breakdown (descriptive).

    A session left at status ``pending`` is one the scheduler spawned in the last instant whose task was cancelled by the
    end of the run before it first ran (client behaviour since the CAPPED arm): it is accepted as NOT STARTED when it has
    no t_end, arrived within ``arrival_end_tolerance_s`` of the stop and has no request row, up to
    ``CHECK['max_not_started_at_end']`` of them; any other non-terminal status is a failure.
    The pause records are compared with each other (not with a breakdown derived from them): the pause_censored events,
    sessions.csv pause_censored and meta.outcome.gate.n_sessions_paused_at_end agree; per session, n_pauses -
    pause_censored == its resume events, and its requests with pause_s > 0 == its resume events with pause_s > 0."""
    probs: List[str] = []
    ses, rq = run.sessions, run.requests
    plan_path = Path(run.dir) / "plan.csv"
    if not plan_path.exists():
        return ["plan.csv missing"], {}
    plan = pd.read_csv(plan_path)
    if len(ses) == 0 or "sid" not in ses.columns:
        return ["sessions.csv missing or empty"], {}
    t_stop = run.t_abort_s if (run.aborted and run.t_abort_s is not None) else run.t_end_s
    sids = ses["sid"].to_numpy()
    if len(set(sids)) != len(sids):
        probs.append(f"{len(sids) - len(set(sids))} duplicate session ids in sessions.csv")
    planned = set(plan["sid"].to_numpy())
    extra = sorted(set(sids) - planned)
    if extra:
        probs.append(f"{len(extra)} sessions not in plan.csv (e.g. {extra[:5]})")
    arrived = plan[plan["arrival_s"] < t_stop - tol_arr]
    lost = sorted(set(arrived["sid"].to_numpy()) - set(sids))
    if lost:
        probs.append(f"{len(lost)} planned sessions arrived before the end but never started (e.g. {lost[:5]})")
    st = ses["status"].astype(str)
    rq_sids = set(rq["sid"].dropna().astype(int)) if len(rq) else set()
    t_end_col = (pd.to_numeric(ses["t_end"], errors="coerce") if "t_end" in ses.columns
                 else pd.Series(np.nan, index=ses.index))
    not_started = ((st == "pending") & t_end_col.isna() & (ses["arrival_s"] >= t_stop - tol_arr)
                   & ~ses["sid"].astype(int).isin(rq_sids))
    n_ns = int(not_started.sum())
    if n_ns > int(CHECK["max_not_started_at_end"]):
        probs.append(f"{n_ns} sessions spawned at the end of the run never started (allowed "
                     f"{CHECK['max_not_started_at_end']})")
    bad = ses[~st.isin(_TERMINAL) & ~not_started]
    if len(bad):
        probs.append(f"{len(bad)} sessions with a non-terminal status at the end ({sorted(set(bad['status'].astype(str)))})")
    comp = ses[st == "completed"]
    if "turns_completed" in ses.columns and len(comp):
        short = comp[comp["turns_completed"] != comp["n_turns"]]
        if len(short):
            probs.append(f"{len(short)} completed sessions with turns_completed != n_turns")
    canc = ses[st == "cancelled"]
    early = canc[~(canc["t_end"] >= t_stop - tol_end)]
    if len(early):
        probs.append(f"{len(early)} cancelled sessions ended before the end of the run (lost, not outstanding)")
    if len(rq):
        unknown = sorted(set(rq["sid"].dropna().astype(int)) - set(int(s) for s in sids))
        if unknown:
            probs.append(f"{len(unknown)} request session ids not in sessions.csv (e.g. {unknown[:5]})")
        if "turns_completed" in ses.columns:
            n_ok = rq[rq["status"] == "ok"].groupby("sid").size()
            tc = ses.set_index("sid")["turns_completed"]
            mism = [s for s in tc.index if int(n_ok.get(s, 0)) != int(tc[s])]
            if mism:
                probs.append(f"{len(mism)} sessions whose ok requests != turns_completed (e.g. {mism[:5]})")
    o = run.meta.get("outcome") or {}
    for k, v in (("sessions_started", len(ses)), ("sessions_completed", int((st == "completed").sum())),
                 ("sessions_failed", int((st == "failed").sum())), ("sessions_cancelled", int((st == "cancelled").sum()))):
        if o.get(k) is not None and int(o[k]) != v:
            probs.append(f"meta.outcome.{k} = {o[k]} but sessions.csv has {v}")
    og = o.get("gate") if isinstance(o.get("gate"), dict) else {}
    if events is not None and "n_pauses" in ses.columns and events["sid"].notna().any():
        ev_n = events[events["event"] == "pause"].groupby("sid").size()
        npz = ses.set_index("sid")["n_pauses"].fillna(0)
        mism = [s for s in npz.index if int(ev_n.get(s, 0)) != int(npz[s])]
        if mism:
            probs.append(f"{len(mism)} sessions whose n_pauses != their pause events (e.g. {mism[:5]})")
    # the pause records against each other (independent logs: gate events, sessions.csv, requests.csv, meta.json)
    if events is not None:
        n_cens_ev = int((events["event"] == "pause_censored").sum())
        n_cens_ses = int(ses["pause_censored"].fillna(0).sum()) if "pause_censored" in ses.columns else None
        n_cens_meta = og.get("n_sessions_paused_at_end")
        vals = {"pause_censored events": n_cens_ev, "sessions.csv pause_censored": n_cens_ses,
                "meta.outcome.gate.n_sessions_paused_at_end": None if n_cens_meta is None else int(n_cens_meta)}
        if n_cens_ses is None or n_cens_meta is None or len(set(vals.values())) > 1:
            probs.append(f"sessions paused at the end disagree or are missing: {vals}")
        if "n_pauses" in ses.columns and "pause_censored" in ses.columns:
            ev_s = events[events["sid"].notna()]
            res = ev_s[ev_s["event"] == "resume"]
            res_n = res.groupby("sid").size()
            ps = pd.to_numeric(res["pause_s"], errors="coerce") if "pause_s" in res.columns else pd.Series(np.nan, index=res.index)
            res_pos = res[ps > 0].groupby("sid").size()
            by = ses.set_index("sid")
            closed = by["n_pauses"].fillna(0) - by["pause_censored"].fillna(0)
            mism = [s for s in closed.index if int(closed[s]) != int(res_n.get(s, 0))]
            if mism:
                probs.append(f"{len(mism)} sessions whose n_pauses - pause_censored != their resume events (e.g. {mism[:5]})")
            if "pause_s" in rq.columns and len(rq):
                rq_pos = rq[pd.to_numeric(rq["pause_s"], errors="coerce").fillna(0.0) > 0].groupby("sid").size()
                keys = set(int(k) for k in rq_pos.index) | set(int(k) for k in res_pos.index)
                mism = sorted(s for s in keys if int(rq_pos.get(s, 0)) != int(res_pos.get(s, 0)))
                if mism:
                    probs.append(f"{len(mism)} sessions whose requests with a pause != their resume events with a pause "
                                 f"(e.g. {mism[:5]})")
    # end-of-run breakdown (descriptive only; reported with --smoke / --require-release)
    if "pause_censored" in ses.columns:
        paused_end = set(ses.loc[(st == "cancelled") & (ses["pause_censored"].fillna(0) > 0), "sid"])
    else:
        op = pause_intervals(run, events)
        paused_end = set(op.loc[op["source"] == "open", "sid"].astype(int)) if len(op) else set()
    gated_end = set(ses.loc[(st == "cancelled") & ses["t_admit"].isna(), "sid"]) if "t_admit" in ses.columns else set()
    br = {"planned": int(len(plan)), "arrived": int(len(arrived)), "started": int(len(ses)),
          "completed": int((st == "completed").sum()), "failed": int((st == "failed").sum()),
          "paused_at_end": int(len(paused_end)), "gated_at_end": int(len(gated_end - paused_end)),
          "in_system_at_end": int(len(canc) - len(paused_end | gated_end)), "not_started_at_end": n_ns}
    return probs, br


def _gate_params(run: Run) -> Dict[str, float]:
    """The run's effective rescue timing (meta.gate as the client recorded it; else the config block with the client's
    defaults)."""
    mg = run.meta.get("gate") if isinstance(run.meta.get("gate"), dict) else {}
    g = gate_block(run)
    out: Dict[str, float] = {}
    for k, d in (("release_hold_s", 300.0), ("min_on_s", 600.0), ("release_check_s", 10.0)):
        v = mg.get(k, g.get(k))
        out[k] = float(d if v is None else v)
    return out


def gate_invariant_checks(run: Run, ev: pd.DataFrame, t_on: Optional[float]) -> List[Tuple[str, bool, str]]:
    """Mechanical checks of the gate log (each row records the counts AFTER its event); returns (name, ok, detail).
    BLIND: the detail of a passing check is the same whether or not the cap was ever removed.

    gate_counts          every engage / pause / resume / cap-change row carries active, waiting and paused.
    gate_pause_rows      every pause row has a cap and active >= cap (a session pauses only over the cap).
    gate_no_lost_wakeup  every row with a cap and waiting + paused > 0 has active >= cap (nobody waits while a slot is
                         free).
    gate_cap_held        under one cap, once active <= cap no later row has active > cap (attrition never reverses).
    gate_uncap_rule      at most one cap removal; after the engage, at a row with waiting == paused == 0, at
                         t >= t_on + min_on_s and on the check grid t_on + k * release_check_s (at most
                         min(release_grid_tol_s, check / 2) late from scheduling lag, at most clock_early_tol_s early:
                         asyncio runs a timer up to one clock resolution before its time).
    gate_uncap_hold      no pause or resume event, and no gated or paused session, during the hold before the removal
                         (the hold shortened by min(release_hold_tol_s, hold / 4) at its start for the hand-off lag).
    gate_outcome_counts  meta.outcome.gate n_pauses / n_resumes equal the pause / resume events.
    gate_end_state       after the end-of-run cancel no slot is held and no session is queued, and the controller
                         raised no error (meta.outcome.gate active_after_end, queued_after_end, gate_control_error)."""
    out: List[Tuple[str, bool, str]] = []
    gp = _gate_params(run)
    cnt_cols = ["active", "waiting", "paused"]
    missing = [c for c in cnt_cols if c not in ev.columns]
    if missing:
        return [("gate_counts", False, f"{GATE_EVENTS_FILE} lacks the columns {missing}")]
    sel = ev[ev["event"].isin(["engage", "pause", "resume", "release", "cap"])]
    no_cnt = sel[sel[cnt_cols].isna().any(axis=1)]
    out.append(("gate_counts", len(no_cnt) == 0,
                f"{len(no_cnt)} engage / pause / resume / cap rows without active, waiting and paused counts"))
    capped = ev["cap"].notna()
    act, wai, pau = ev["active"], ev["waiting"].fillna(0.0), ev["paused"].fillna(0.0)
    pz = ev["event"] == "pause"
    bad_p = ev[pz & (~capped | ~(act >= ev["cap"]))]
    out.append(("gate_pause_rows", len(bad_p) == 0,
                f"{len(bad_p)} pause rows without a cap or with active < cap" if len(bad_p) else
                "every pause row has a cap and active >= cap"))
    lw = ev[capped & ((wai + pau) > 0) & ~(act >= ev["cap"])]
    out.append(("gate_no_lost_wakeup", len(lw) == 0,
                f"{len(lw)} rows with sessions waiting while active < cap (first at t={float(lw['t_s'].iloc[0]):.1f})"
                if len(lw) else "no session waited while a slot was free"))
    above: List[float] = []
    cur_cap: Optional[float] = None
    reached = False
    for r in ev.itertuples(index=False):
        if r.event in ("engage", "cap", "release"):
            cur_cap, reached = (None if _isnan(r.cap) else float(r.cap)), False
        if cur_cap is None or _isnan(r.active):
            continue
        if r.active <= cur_cap:
            reached = True
        elif reached:
            above.append(float(r.t_s))
    out.append(("gate_cap_held", not above,
                f"active above the cap again after reaching it, {len(above)} rows (first at t={above[0]:.1f})"
                if above else "once at the cap, active never exceeded it"))
    rel = ev[ev["event"] == "release"]
    eng = ev[ev["event"] == "engage"]
    pr: List[str] = []
    hold_pr: List[str] = []
    if len(rel):
        t_rel = float(rel["t_s"].iloc[0])
        row = rel.iloc[0]
        dt, hold, min_on = gp["release_check_s"], gp["release_hold_s"], gp["min_on_s"]
        if len(rel) > 1:
            pr.append(f"{len(rel)} cap removals")
        if not len(eng) or t_rel < float(eng["t_s"].iloc[0]):
            pr.append("cap removed before any engage")
        if not (_f(row.get("waiting")) == 0 and _f(row.get("paused")) == 0):
            pr.append("sessions still queued at the cap removal")
        if t_on is not None:
            early = float(CHECK["clock_early_tol_s"])
            if t_rel < t_on + min_on - early:
                pr.append("cap removed before t_on + min_on_s")
            k = round((t_rel - t_on) / dt)
            lag = t_rel - (t_on + k * dt)
            if not (-early <= lag <= min(float(CHECK["release_grid_tol_s"]), 0.5 * dt)):
                pr.append("cap removed off the check grid t_on + k * release_check_s")
        tol = min(float(CHECK["release_hold_tol_s"]), 0.25 * hold)
        a, b = t_rel - hold + tol, t_rel
        n_ev = int((ev["event"].isin(["pause", "resume"]) & (ev["t_s"] > a) & (ev["t_s"] < b)).sum())
        if n_ev:
            hold_pr.append(f"{n_ev} pause / resume events inside the hold")
        g0, g1 = gate_wait_intervals(run)
        pi = pause_intervals(run, ev)
        q = step_from_intervals([g0, pi["t0"].to_numpy(dtype=float)], [g1, pi["t1"].to_numpy(dtype=float)])
        if b - tol > a and q.max_on(a, b - tol) > 0:
            hold_pr.append("a gated or paused session inside the hold")
    out.append(("gate_uncap_rule", not pr, "; ".join(pr) if pr else "cap-removal rule respected"))
    out.append(("gate_uncap_hold", not hold_pr, "; ".join(hold_pr) if hold_pr else "hold rule respected"))
    og = (run.meta.get("outcome") or {}).get("gate") or {}
    n_p, n_r = int(pz.sum()), int((ev["event"] == "resume").sum())
    cp: List[str] = []
    for k, v in (("n_pauses", n_p), ("n_resumes", n_r)):
        if og.get(k) is None or int(og[k]) != v:
            cp.append(f"meta.outcome.gate.{k} = {og.get(k)!r} but {v} events")
    out.append(("gate_outcome_counts", not cp, "; ".join(cp) if cp else "meta pause / resume counts equal the events"))
    es: List[str] = []
    for k in ("active_after_end", "queued_after_end"):
        if og.get(k) is None or int(og[k]) != 0:
            es.append(f"meta.outcome.gate.{k} = {og.get(k)!r} (want 0)")
    if og.get("gate_control_error"):
        es.append(f"gate controller error: {og['gate_control_error']}")
    out.append(("gate_end_state", not es, "; ".join(es) if es else
                "no slot held and no session queued after the end-of-run cancel; no controller error"))
    return out


def check_run(run_dir: str | Path, e2_cfg_path: str | Path, *, burst_plan: Optional[str | Path] = None,
              min_pauses: int = 0, min_resumes: int = 0, max_request_errors: Optional[int] = None,
              require_release: bool = False, smoke: bool = False) -> Dict[str, Any]:
    """The automatic post-run check of a rescue run (see the module docstring). ``ok`` False = the job must fail."""
    checks: List[Dict[str, Any]] = []
    rep: Dict[str, Any] = {"run_dir": str(run_dir), "e2_config": str(e2_cfg_path), "checks": checks}

    def add(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    def finish() -> Dict[str, Any]:
        rep["failures"] = [f"{c['name']}: {c['detail']}" for c in checks if not c["ok"]]
        rep["ok"] = not rep["failures"]
        return rep

    try:
        e2 = yaml.safe_load(Path(e2_cfg_path).read_text()) or {}
    except Exception as e:
        add("e2_config", False, f"cannot read {e2_cfg_path}: {type(e).__name__}: {e}")
        return finish()
    try:
        run, ev = load_rescue_run(run_dir)
    except Exception as e:
        add("load", False, f"{type(e).__name__}: {e}")
        return finish()
    add("arm", run.arm == ARM, f"meta.arm = {run.arm!r}")
    modes = gate_mode_records(run)
    add("gate_mode_config", gate_block(run).get("mode") == MODE, f"config gate.mode = {gate_block(run).get('mode')!r}")
    add("gate_mode_meta", bool(modes) and all(v == MODE for v in modes.values()),
        f"meta records {modes}" if modes else "meta.json records no gate mode")
    gp = e2_gate_problems(run, e2)
    add("e2_config_gate", not gp, "; ".join(gp) if gp else "gate block, cap, run length and burst match")
    n_cap = run.gate_n_cap
    t_on = _f((e2.get("gate") or {}).get("t_on_s"))
    if t_on is None:
        t_on = t_on_of(run)
    if ev is None:
        add("gate_events", False, f"{GATE_EVENTS_FILE} missing")
    else:
        n_eng = int((ev["event"] == "engage").sum())
        t_eng, t_rel = engage_release(ev)
        ok = n_eng == 1 and t_eng is not None and t_on is not None and abs(t_eng - t_on) <= float(CHECK["engage_within_s"])
        add("engage", ok, f"{n_eng} engage event(s); t_engage={t_eng}, t_on={t_on}")
        if t_eng is not None:
            cap_e = _f(ev.loc[ev["event"] == "engage", "cap"].iloc[0])
            add("engage_cap", cap_e is not None and n_cap is not None and int(cap_e) == n_cap,
                f"engage cap {cap_e}, resolved cap {n_cap}")
        npz = int((ev["event"] == "pause").sum())
        nres = int((ev["event"] == "resume").sum())
        bad_t = []
        if t_eng is not None:
            if ((ev["event"] == "pause") & (ev["t_s"] < t_eng)).any():
                bad_t.append("pause before the engage")
        elif npz:
            bad_t.append("pause events without an engage")
        if t_rel is not None and ((ev["event"] == "pause") & (ev["t_s"] > t_rel)).any():
            bad_t.append("pause after the release")
        if ev["sid"].notna().any():
            for sid, g in ev[ev["sid"].notna() & ev["event"].isin(["pause", "resume"])].groupby("sid"):
                bal = np.cumsum(np.where(g["event"].to_numpy() == "pause", 1, -1))
                if (bal < 0).any() or (bal > 1).any():
                    bad_t.append(f"pause/resume out of order for session {int(sid)}")
                    break
        add("pause_order", not bad_t, "; ".join(bad_t) if bad_t else "pauses only while engaged, resumes follow pauses")
        if t_eng is not None and n_cap is not None:
            eng_row = ev[ev["event"] == "engage"].iloc[0]
            act = _f(eng_row.get("active")) if "active" in ev.columns else None
            if act is None:
                act = float(_active_at(run.sessions, t_eng))
            over = act > n_cap
            add("pause_when_over_cap", (npz > 0) or not over,
                f"{int(act)} active at the engage vs cap {n_cap}; {npz} pause / {nres} resume events")
        if min_pauses or min_resumes:
            add("pause_counts", npz >= min_pauses and nres >= min_resumes,
                f"{npz} pauses (need >= {min_pauses}), {nres} resumes (need >= {min_resumes})")
        for name, ok_, detail in gate_invariant_checks(run, ev, t_on):
            add(name, ok_, detail)
        if require_release:
            add("release", t_rel is not None and t_rel <= run.t_end_s, f"t_release={t_rel}")
            rep["t_release"] = t_rel
    probs, br = conservation(run, ev, float(CHECK["cancel_end_tolerance_s"]), float(CHECK["arrival_end_tolerance_s"]))
    add("conservation", not probs, "; ".join(probs) if probs else
        f"planned {br.get('planned')}, arrived {br.get('arrived')}, started {br.get('started')}: every session ended or "
        "was still outstanding at the end")
    if smoke or require_release:
        rep["breakdown_at_end"] = br
    if burst_plan is not None:
        rp = Path(run_dir) / "plan.csv"
        if not Path(burst_plan).exists() or not rp.exists():
            add("plan_sha256", False, f"missing {'--burst-plan file' if not Path(burst_plan).exists() else 'plan.csv'}")
        else:
            a, b = file_sha256(rp), file_sha256(burst_plan)
            add("plan_sha256", a == b, f"run {a} vs BURST {b}")
    if max_request_errors is not None:
        n_err = int((run.requests["status"] == "error").sum()) if len(run.requests) else 0
        add("request_errors", n_err <= max_request_errors, f"{n_err} request errors (allowed {max_request_errors})")
    add("not_aborted", not run.aborted, f"abort_reason={run.abort_reason!r}" if run.aborted else "")
    return finish()


# --------------------------------------------------------------------------------------------- CLI
def _write_outputs(out: Path, doc: Dict[str, Any], frames: Dict[str, pd.DataFrame], params_path: str, p: AnalysisParams,
                   argv: List[str], git: Dict[str, Any], t0: datetime, inputs: List[str]) -> None:
    for name, df in frames.items():
        df.to_csv(out / f"{name}.csv", index=False)
    (out / "rescue_verdict.json").write_text(json.dumps(_sanitize(doc), indent=2, default=json_default))
    (out / "config.yaml").write_text(Path(params_path).read_text())
    (out / "config_effective.yaml").write_text(yaml.safe_dump(p.raw, sort_keys=False))
    meta = build_meta(experiment="agentload_analysis_rescue", argv=argv, seeds=[], hardware=default_hardware(), git=git,
                      t_start=t0, t_end=datetime.now(), extra={"inputs": inputs, "verdict": doc["family"]["verdict"],
                                                                 "decisive": doc["decisive"]}, status="finished")
    write_meta(out, meta)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.rescue", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check-run", help="automatic post-run check of one rescue run (exit 1 on failure)")
    c.add_argument("run_dir")
    c.add_argument("--e2-config", required=True, help="the rescue e2 config the run was launched with")
    c.add_argument("--burst-plan", default=None, help="committed BURST plan.csv of the same seed and rate")
    c.add_argument("--smoke", action="store_true",
                   help=f"smoke-job criteria: >= {CHECK['smoke_min_pauses']} pauses and >= {CHECK['smoke_min_resumes']} "
                        f"resumes, {CHECK['smoke_max_request_errors']} request errors")
    c.add_argument("--min-pauses", type=int, default=None)
    c.add_argument("--min-resumes", type=int, default=None)
    c.add_argument("--max-request-errors", type=int, default=None)
    c.add_argument("--require-release", action="store_true", help="also require a release event (smoke, if predicted)")
    c.add_argument("--json-out", default=None, help="also write the report to this file")
    v = sub.add_parser("verdict", help="registered rule (a)-(c) and the PASS rule over rescue runs and their controls")
    v.add_argument("--rescue-runs", nargs="+", required=True)
    v.add_argument("--control-runs", nargs="+", required=True, help="committed BURST and NOBURST runs of the same seeds")
    v.add_argument("--profile", default="auto", help=f"auto|{'|'.join(PROFILES)} (auto: from the rescue runs' label)")
    v.add_argument("--control-label", default=None, help="override the profile's control engine label")
    v.add_argument("--e2-config", default=None, help="check every run's gate block against this e2 config")
    v.add_argument("--prereg", default=None, help="the committed rescue registration (decisive verdict)")
    v.add_argument("--predictions", default=None,
                   help="frozen prediction result dir (cells_mixed.csv, runs_mixed.csv) to score the release times")
    v.add_argument("--params", default=DEFAULT_PARAMS)
    v.add_argument("--set", action="append", default=[], help="override an analysis param (recorded)")
    v.add_argument("--out-root", default=None)
    v.add_argument("--name", default="agentload_analysis_rescue")
    args = ap.parse_args(argv)
    if args.cmd == "check-run":
        mp = args.min_pauses if args.min_pauses is not None else (CHECK["smoke_min_pauses"] if args.smoke else 0)
        mr = args.min_resumes if args.min_resumes is not None else (CHECK["smoke_min_resumes"] if args.smoke else 0)
        me = args.max_request_errors if args.max_request_errors is not None else (
            CHECK["smoke_max_request_errors"] if args.smoke else None)
        rep = check_run(args.run_dir, args.e2_config, burst_plan=args.burst_plan, min_pauses=mp, min_resumes=mr,
                        max_request_errors=me, require_release=args.require_release, smoke=args.smoke)
        txt = json.dumps(_sanitize(rep), indent=2, default=json_default)
        print(txt)
        if args.json_out:
            Path(args.json_out).write_text(txt)
        if not rep["ok"]:
            print("rescue check-run FAILED: " + " | ".join(rep["failures"]), file=sys.stderr)
            return 1
        return 0
    p = load_params(args.params, args.set)
    repo = Path(args.params).resolve().parent.parent
    git = git_info(repo)
    t0 = datetime.now()
    e2 = yaml.safe_load(Path(args.e2_config).read_text()) if args.e2_config else None
    doc, frames = verdict(args.rescue_runs, args.control_runs, p, profile=args.profile, e2_cfg=e2,
                          prereg_path=args.prereg, control_label=args.control_label, predictions=args.predictions)
    out = new_result_dir(args.out_root or p.raw["output"]["root"], args.name)
    _write_outputs(out, doc, frames, args.params, p,
                   [sys.executable, "-m", "analysis.rescue", *(argv if argv is not None else sys.argv[1:])], git, t0,
                   [*args.rescue_runs, *args.control_runs])
    print(json.dumps(_sanitize({"out_dir": str(out), "profile": doc["profile"], "family": doc["family"],
                                "cells": [{k: c[k] for k in ("rate_mult", "n_rescued", "n_present", "meets",
                                                             "meets_valid_pairing", "diagnosis")} for c in doc["cells"]],
                                "rejected_runs": doc["rejected_runs"], "decisive": doc["decisive"]}),
                     indent=2, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
