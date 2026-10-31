"""Round 11: a time-varying client-side session gate for the simulator (rescue cap with pause, attrition cap, AIMD-pause, shedding).

``GateEngine`` subclasses ``engine.Engine`` (engine.py is NOT edited) and overrides five hooks:

* ``_tick``           the controller step, every ``tick_s`` (the engine's AIMD tick clock is used only as a clock: the controller
                      installs ``AimdParams(interval_s=tick_s)`` so that ticks are scheduled; the AIMD rule of mechanisms.py is never
                      called). Setting that tick clock is also what bypasses the engine's static-cap asserts (engine.py
                      ``check_invariants`` / ``_check_invariants_dyn``: ``session_cap is not None and aimd is None``), and it is set
                      ONLY when a controller is given.
* ``_finish_request`` a follow-up hit counter over COMPLETED turns >= 2 (what a client sees in cached_tokens), and per-request
                      completion records for the R1 rule.
* ``_enqueue_turn``   pause: a session whose tool call ends (turn >= 2 becomes ready) while ``in_system > cap`` gives up its slot
                      and joins the resume section at the FRONT of the gate queue (FIFO among paused sessions); new arrivals queue
                      behind it (FIFO). With ``pause: false`` the cap acts by attrition only (session ends), as in the base engine.
* ``_enter``          a paused session leaving the gate resumes at its pending turn (ready time = its tool return, so latency
                      includes the pause; the engine queue time is the resume time, as the client measures sched_delay from resume).
* ``_arrive``         ``shed: true``: while the cap is engaged and binding, an arriving session is dropped (counted in ``n_shed``).

Controller modes (``GateControl.mode``):

``static``  cap = ``cap`` from t = 0, never released (equals ``RunSpec.session_cap_override``; a test checks this).
``rescue``  uncapped until the first tick ``t >= t_on_s``; then cap = ``cap``. Released (cap -> unbounded) at the first tick with
            ``t >= t_engage + min_on_s`` at which the gate queue (new arrivals AND paused sessions) has been empty continuously for
            ``release_hold_s`` (tracked at event time, not only at ticks), or at ``t_off_max_s`` if given (forced; default never).
``aimd``    uncapped until the first decrease. Every tick, H = follow-up hit fraction of the turns completed in the last ``win_s``
            (NaN below ``n_min`` completions). H < ``h_low`` (and at least ``md_holdoff_s`` since the last decrease): cap =
            max(c_min, floor(beta * min(cap, in_system))) if that is lower. H >= ``h_high``: cap += alpha if the cap binds (gate
            non-empty and in_system >= cap), else, with ``aimd_release``, release once the gate has been empty ``release_hold_s``.

Per-tick trace rows (sampled BEFORE the controller acts): t, in_system, gate (incl. paused), paused, n_wait, running, cap
(-1 = unbounded), H, outstanding (= waiting + running requests + gate, the client's "requests in flight + gated / paused
sessions"). ``simulate_gate`` returns the ``sim.simulate`` dict plus a ``gate`` block (trace, completion records, events, counts).
Without a controller ``simulate_gate`` IS ``sim.simulate`` (bit-identical by construction).

Simulator caveats (disclosed with every prediction): the calibrated simulator frees a finished session's KV at once (an oracle),
and a cached prefix is all-or-nothing per session (full_reserve LRU), so a hit at turn t >= 2 has cached / prompt = (P_t - Delta) / P_t > 0.5
and uncached = Delta; a miss is uncached = P_t.
"""
from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import json
import math
import multiprocessing as mp
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .engine import Engine, EngineParams
from .eviction import eviction_rng
from .mechanisms import AimdParams
from .metrics import Recorder, tail_stats, trend_rise
from .sim import RunSpec, build_engine, deep_update, resolve_policy, simulate
from .workload import WorkloadParams, build_specs

BIG = 10 ** 9            # "unbounded" cap (the engine needs an integer cap once the tick clock is installed)
MODES = ("static", "rescue", "aimd")


@dataclass(frozen=True)
class GateControl:
    mode: str
    cap: Optional[int] = None
    t_on_s: float = 0.0
    pause: bool = True
    release_hold_s: float = 300.0
    min_on_s: float = 600.0
    t_off_max_s: Optional[float] = None
    shed: bool = False
    tick_s: float = 10.0
    # aimd
    win_s: float = 60.0
    n_min: int = 20
    h_low: float = 0.2
    h_high: float = 0.8
    beta: float = 0.7
    alpha: int = 1
    c_min: int = 4
    md_holdoff_s: float = 0.0
    aimd_release: bool = True

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"gate control mode must be one of {MODES}, got {self.mode!r}")
        if self.mode in ("static", "rescue") and (self.cap is None or int(self.cap) < 1):
            raise ValueError(f"mode {self.mode!r} needs an integer cap >= 1")
        if self.tick_s <= 0 or self.win_s <= 0 or self.release_hold_s < 0 or self.min_on_s < 0:
            raise ValueError("tick_s and win_s must be > 0, release_hold_s and min_on_s >= 0")
        if self.mode == "aimd" and not (0.0 < self.beta < 1.0 and self.alpha >= 1 and self.c_min >= 1 and self.h_low <= self.h_high):
            raise ValueError("bad AIMD parameters")

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["GateControl"]:
        if d is None:
            return None
        if isinstance(d, str):
            d = json.loads(d)
        unknown = sorted(set(d) - {f.name for f in dataclasses.fields(cls)})
        if unknown:
            raise ValueError(f"gate control: unknown keys {unknown}")
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


class GateEngine(Engine):
    """Engine with a time-varying client-side gate (see the module docstring). ``control=None`` -> the base engine's behaviour
    (no hook does anything beyond calling the base method; ``simulate_gate`` does not even build this class then)."""

    def __init__(self, *a, control: Optional[GateControl] = None, **kw):
        super().__init__(*a, **kw)
        self.ctl = control
        self.trace_rows: List[Tuple[float, ...]] = []
        self.done_rows: List[Tuple[float, int, int, int, int]] = []     # (t_complete, sid, turn, hit, uncached prompt tokens)
        self.events: List[Tuple[float, str, int]] = []                 # (t, kind, value): engage / release / cap / pause / resume / shed
        self._fu_n = self._fu_h = 0
        self._last_n = self._last_h = 0
        self._win: List[Tuple[int, int]] = []
        self._gate_empty_since = 0.0
        self._last_md = -math.inf
        self.t_engage: Optional[float] = None
        self.t_release: Optional[float] = None
        self._released = False
        self._paused: Dict[int, Tuple[float, float]] = {}            # sid -> (ready time, pause time)
        self._npaused_front = 0
        self.n_pauses = 0
        self.n_resumes = 0
        self.pause_s_total = 0.0
        self.n_shed = 0
        self.n_gated_arrivals = 0
        self.gate_wait_s_total = 0.0
        self._gated_at: Dict[int, float] = {}
        self.max_gate_paused = 0
        # per-session user costs (sid -> value): admission wait + pauses, completion time, dropped by shedding
        self.delay_s: Dict[int, float] = {}
        self.t_done: Dict[int, float] = {}
        self.shed_sids: List[int] = []

    # ------------------------------------------------------------------ helpers
    def cap_value(self) -> int:
        c = self.session_cap
        return -1 if c is None or c >= BIG else int(c)

    def _set_cap(self, t: float, c: int) -> None:
        if c != self.session_cap:
            self.session_cap = c
            self.cap_trace.append((t, c))
            if c < BIG:
                self.cap_min = c if self.cap_min is None or self.cap_min >= BIG or c < self.cap_min else self.cap_min
            self.events.append((t, "cap", -1 if c >= BIG else int(c)))

    def _note_gate(self, t: float, before: int) -> None:
        """Track the time the gate (arrivals + paused) last became empty, at event time."""
        g = len(self._gate)
        if before > 0 and g == 0:
            self._gate_empty_since = t
        if g > self.max_gate_paused:
            self.max_gate_paused = g

    def outstanding(self) -> int:
        running = self.n_D + len(self.prefill) if not self._dyn else len(self._run_order)
        return int(self.n_wait + running + len(self._gate))

    # ------------------------------------------------------------------ hooks
    def _arrive(self, i: int, t: float) -> None:
        c = self.ctl
        if c is not None and c.shed and self.t_engage is not None and not self._released and self.in_system >= self.session_cap:
            self.n_arrived += 1
            self._arrived_t[i] = t
            self.n_shed += 1
            self.shed_sids.append(i)
            self.events.append((t, "shed", i))
            return
        g0 = len(self._gate)
        super()._arrive(i, t)
        if c is not None:
            if len(self._gate) > g0:
                self._gated_at[i] = t
                self.n_gated_arrivals += 1
            self._note_gate(t, g0)

    def _enter(self, i: int, t: float) -> None:
        if self.ctl is not None and i in self._paused:
            ready, t_p = self._paused.pop(i)
            self._npaused_front -= 1
            self.in_system += 1
            if self.in_system > self.max_in_system:
                self.max_in_system = self.in_system
            self.n_resumes += 1
            self.pause_s_total += t - t_p
            self.delay_s[i] = self.delay_s.get(i, 0.0) + (t - t_p)
            self.events.append((t, "resume", i))
            super()._enqueue_turn(i, t, ready)
            return
        if self.ctl is not None and i in self._gated_at:
            w = t - self._gated_at.pop(i)
            self.gate_wait_s_total += w
            self.delay_s[i] = self.delay_s.get(i, 0.0) + w
        super()._enter(i, t)

    def _enqueue_turn(self, sid: int, t: float, ready: float) -> None:
        c = self.ctl
        if (c is not None and c.pause and self._turn[sid] > 1 and self.session_cap is not None and self.session_cap < BIG
                and self.in_system > self.session_cap and sid not in self._paused):
            self.in_system -= 1                      # gives up its slot; no hand-off (in_system is still >= cap)
            self._paused[sid] = (ready, t)
            self._gate.insert(self._npaused_front, sid)
            self._npaused_front += 1
            self.n_pauses += 1
            self.events.append((t, "pause", sid))
            if len(self._gate) > self.max_gate:
                self.max_gate = len(self._gate)
            if len(self._gate) > self.max_gate_paused:
                self.max_gate_paused = len(self._gate)
            self.rec.set_gate(t, len(self._gate))
            return
        super()._enqueue_turn(sid, t, ready)

    def _finish_request(self, req, t: float) -> None:
        if self.ctl is None:
            super()._finish_request(req, t)
            return
        hit = bool(req.hit)
        if req.turn > 1:
            self._fu_n += 1
            if hit:
                self._fu_h += 1
        unc = self.wl.new_prompt_tokens if (hit and req.turn > 1) else req.prompt
        self.done_rows.append((t, req.sid, req.turn, int(hit), int(unc)))
        if req.turn >= self._nt[req.sid]:
            self.t_done[req.sid] = t
        g0 = len(self._gate)
        super()._finish_request(req, t)
        self._note_gate(t, g0)

    def _tick(self, tt: float) -> None:
        c = self.ctl
        if c is None:                                 # never reached: the tick clock is installed only with a controller
            super()._tick(tt)
            return
        self.n_ticks += 1
        self._next_tick += self.aimd.interval_s
        dn, dh = self._fu_n - self._last_n, self._fu_h - self._last_h
        self._last_n, self._last_h = self._fu_n, self._fu_h
        self._win.append((dn, dh))
        k = max(1, int(round(c.win_s / c.tick_s)))
        wn = sum(x[0] for x in self._win[-k:])
        wh = sum(x[1] for x in self._win[-k:])
        H = wh / wn if wn >= c.n_min else float("nan")
        gate_len = len(self._gate)
        quiet_s = 0.0 if gate_len > 0 else tt - self._gate_empty_since
        self.trace_rows.append((tt, self.in_system, gate_len, len(self._paused), self.n_wait, self.outstanding() - self.n_wait - gate_len,
                                self.cap_value(), H, self.outstanding()))
        if c.mode == "rescue":
            if self.t_engage is None:
                if tt >= c.t_on_s:
                    self.t_engage = tt
                    self.events.append((tt, "engage", int(c.cap)))
                    self._set_cap(tt, int(c.cap))
            elif not self._released:
                quiet = gate_len == 0 and quiet_s >= c.release_hold_s and tt >= self.t_engage + c.min_on_s
                if quiet or (c.t_off_max_s is not None and tt >= c.t_off_max_s):
                    self._released = True
                    self.t_release = tt
                    self.events.append((tt, "release", int(bool(quiet))))
                    self._set_cap(tt, BIG)
        elif c.mode == "aimd":
            cap = self.session_cap
            if H == H:
                if H < c.h_low and tt - self._last_md >= c.md_holdoff_s:
                    base = min(cap, self.in_system)
                    new = max(int(c.c_min), int(math.floor(c.beta * base)))
                    if new < cap:
                        self._last_md = tt
                        if self.t_engage is None:
                            self.t_engage = tt
                            self.events.append((tt, "engage", new))
                        if self._released:
                            self.events.append((tt, "reengage", new))
                        self._released = False
                        self._set_cap(tt, new)
                elif H >= c.h_high and cap < BIG:
                    if gate_len > 0 and self.in_system >= cap:
                        self._set_cap(tt, cap + int(c.alpha))
                    elif c.aimd_release and gate_len == 0 and quiet_s >= c.release_hold_s:
                        self._released = True
                        self.t_release = tt
                        self.events.append((tt, "release", 1))
                        self._set_cap(tt, BIG)
        g0 = len(self._gate)
        self._release_gate(tt)
        self._note_gate(tt, g0)

    def session_rows(self, t_end: float) -> List[Tuple[int, float, float, float, int]]:
        """(sid, arrival, completion time or NaN, delay = admission wait + pauses incl. the open ones up to t_end, shed) of
        every session that arrived."""
        open_d: Dict[int, float] = {i: t_end - t0 for i, t0 in self._gated_at.items()}
        for i, (_, t_p) in self._paused.items():
            open_d[i] = open_d.get(i, 0.0) + (t_end - t_p)
        shed = set(self.shed_sids)
        out = []
        for i in range(self._next_idx):                   # arrivals are processed in index order
            out.append((i, float(self._arrived_t[i]), float(self.t_done.get(i, float("nan"))),
                        float(self.delay_s.get(i, 0.0) + open_d.get(i, 0.0)), int(i in shed)))
        return out

    def gate_stats(self) -> Dict[str, Any]:
        return {"t_engage": self.t_engage, "t_release": self.t_release, "n_pauses": self.n_pauses, "n_resumes": self.n_resumes,
                "n_paused_end": len(self._paused), "pause_s_total": self.pause_s_total, "n_shed": self.n_shed,
                "n_gated_arrivals": self.n_gated_arrivals, "gate_wait_s_total": self.gate_wait_s_total,
                "n_gated_end": len(self._gated_at), "max_gate_paused": self.max_gate_paused,
                "cap_min": None if self.cap_min is None or self.cap_min >= BIG else int(self.cap_min),
                "conservation_ok": bool(self.n_arrived == self.n_sessions_done + self.in_system + len(self._gate) + self.n_shed)}


# ====================================================================== building and running
def control_mechanisms(mech, control: GateControl):
    """The engine's mechanisms with the AIMD tick clock set to the controller's tick (the AIMD rule itself is never called)."""
    return dataclasses.replace(mech, aimd=AimdParams(interval_s=float(control.tick_s)))


def build_gate_engine(cfg: dict, rs: RunSpec, control: GateControl, specs=None):
    """Like ``sim.build_engine`` but a ``GateEngine`` with ``control``. The initial cap is ``control.cap`` for ``static`` and
    unbounded (BIG) otherwise; ``rs.session_cap_override`` must be None (the controller owns the cap)."""
    if rs.session_cap_override is not None:
        raise ValueError("a run with a gate controller must not also set session_cap_override")
    ep = EngineParams.from_dict(deep_update(cfg["engine"], rs.engine_overrides))
    wl = WorkloadParams.from_dict(deep_update(cfg["workload"], rs.workload_overrides))
    policy, cap0, mech = resolve_policy(cfg, rs.policy, ep, wl, None)
    if cap0 is not None or mech.aimd is not None:
        raise ValueError(f"policy {rs.policy!r} has its own session cap; a gate controller needs an uncapped policy")
    if specs is None:
        specs = build_specs(wl, rs.plan, rs.seed)
    rec = Recorder(cfg["metrics"]["window_s"], cfg["metrics"]["fine_window_s"])
    rec.mem_on = bool(cfg["metrics"].get("track_memory", False))
    rec.dyn_on = ep.alloc_mode != "full_reserve"
    cap = int(control.cap) if control.mode == "static" else BIG
    eng = GateEngine(ep, wl, specs, policy, rec, session_cap=cap, closed=(rs.plan.kind == "closed"),
                     stop_queue_above=rs.stop_queue_above, debug=rs.debug, mech=control_mechanisms(mech, control),
                     stop_backlog_above=rs.stop_backlog_above, stop_low_hit=rs.stop_low_hit,
                     evict_rng=eviction_rng(rs.seed) if mech.eviction == "random" else None, control=control)
    return eng, rec, cap


def simulate_gate(cfg: dict, rs: RunSpec, control: Optional[GateControl] = None, specs=None) -> Dict[str, Any]:
    """``sim.simulate`` with a gate controller. ``control`` defaults to ``GateControl.from_dict(rs.meta['control'])`` (a JSON
    string); without a controller this is exactly ``sim.simulate``. The summary is built as in ``sim.simulate`` (same keys) plus
    ``gate_*`` columns; the result has an extra ``gate`` block."""
    if control is None:
        control = GateControl.from_dict(rs.meta.get("control"))
    if control is None:
        return simulate(cfg, rs, specs)
    eng, rec, cap = build_gate_engine(cfg, rs, control, specs)
    specs = None
    t0 = time.perf_counter()
    eng.run(rs.horizon_s)
    wall = time.perf_counter() - t0
    windows = rec.finalize(eng.end_time)
    qtrace = rec.queue_trace()
    btrace = rec.backlog_trace()
    tail_s = min(cfg["metrics"]["tail_window_s"], eng.end_time / 2.0)
    tl = tail_stats(windows, eng.end_time - tail_s, eng.end_time)
    summary: Dict[str, Any] = {
        "exp": rs.exp, "policy": rs.policy, "seed": rs.seed, "variant": rs.variant, "horizon_s": rs.horizon_s, "sim_end_s": eng.end_time,
        "session_cap": -1 if cap >= BIG else cap, "eviction": eng.mech.eviction, "wall_s": wall,
        "wall_s_per_10k_sim_s": wall / eng.end_time * 1e4 if eng.end_time > 0 else float("nan"), "tail_s": tail_s,
        "tail_hit_rate": tl["hit_rate"], "tail_queue_mean": tl["queue_mean"], "tail_queue_max": tl["queue_max"],
        "tail_turns_per_s": tl["turns_per_s"], "tail_sessions_per_s": tl["sessions_per_s"], "tail_busy_frac": tl["busy_frac"],
        "tail_queue_trend_rise": trend_rise(qtrace, eng.end_time - tail_s, eng.end_time), "tail_gate_mean": tl["gate_mean"],
        "tail_backlog_mean": tl["queue_mean"] + tl["gate_mean"],
        "tail_backlog_trend_rise": trend_rise(btrace, eng.end_time - tail_s, eng.end_time),
        "final_backlog": eng.n_wait + len(eng._gate),
    }
    summary.update(eng.stats())
    gs = eng.gate_stats()
    summary.update({f"gate_{k}": (float("nan") if v is None else v) for k, v in gs.items()})
    summary["cap_final"] = eng.cap_value()
    summary["cap_max"] = -1
    summary["cap_min"] = -1 if gs["cap_min"] is None else gs["cap_min"]
    summary.update(rs.meta)
    return {"summary": summary, "windows": windows, "qtrace": qtrace, "btrace": btrace,
            "cap_trace": [(t, -1 if c >= BIG else int(c)) for t, c in eng.cap_trace],
            "gate": {"control": dataclasses.asdict(control), "trace": eng.trace_rows, "done": eng.done_rows, "events": eng.events,
                     "stats": gs, "n_sessions_done": eng.n_sessions_done, "n_arrived": eng.n_arrived,
                     "sessions": eng.session_rows(eng.end_time)}}


def _work(args: Tuple[dict, RunSpec]) -> Dict[str, Any]:
    cfg, rs = args
    return simulate_gate(cfg, rs)


def run_specs(cfg: dict, specs: Sequence[RunSpec], workers: int) -> List[Dict[str, Any]]:
    """``runner.Runner.run`` for specs that may carry ``meta['control']`` (in-process for workers <= 1, else a spawn pool capped
    by ``cfg['parallel']['max_workers']``). Output order = input order."""
    w = max(1, min(int(workers), int(cfg.get("parallel", {}).get("max_workers", 1))))
    args = [(cfg, rs) for rs in specs]
    if w <= 1:
        return [_work(a) for a in args]
    with cf.ProcessPoolExecutor(max_workers=w, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(_work, args, chunksize=1))


# ====================================================================== per-run measures (client-side definitions of plan R1)
def _done_array(res: Dict[str, Any]) -> np.ndarray:
    d = res["gate"]["done"]
    return np.asarray(d, dtype=float).reshape(-1, 5)


def fu_hit(done: np.ndarray, t0: float, t1: float) -> Tuple[float, int]:
    """FU-hit = share of turns >= 2 completed in [t0, t1) that hit (cached / prompt > 0.5); (NaN, 0) if there are none."""
    sel = (done[:, 0] >= t0) & (done[:, 0] < t1) & (done[:, 2] >= 2)
    n = int(sel.sum())
    return (float(done[sel, 3].mean()) if n else float("nan")), n


def all_hit(done: np.ndarray, t0: float, t1: float) -> float:
    """trap_v2 hit metric frac_turns_cached_gt50: share of ALL ok turns completed in [t0, t1) with cached / prompt > 0.5."""
    sel = (done[:, 0] >= t0) & (done[:, 0] < t1)
    return float(done[sel, 3].mean()) if sel.any() else float("nan")


def uncached_rate(done: np.ndarray, t0: float, t1: float) -> float:
    sel = (done[:, 0] >= t0) & (done[:, 0] < t1)
    return float(done[sel, 4].sum() / (t1 - t0)) if t1 > t0 else float("nan")


def trace_frame(res: Dict[str, Any]):
    import pandas as pd
    return pd.DataFrame(res["gate"]["trace"], columns=["t", "in_system", "gate", "paused", "n_wait", "running", "cap", "H", "outstanding"])


def rescue_measures(res: Dict[str, Any], *, t_on: float, t_end: float, t_rel: Optional[float], uncached_ref: float,
                    valid_window_s: float = 300.0, valid_outstanding_above: float = 50.0, release_by: float = 7200.0,
                    post_delay_s: float = 300.0, win_s: float = 300.0, post_win_min: float = 0.5, post_all_min: float = 0.8,
                    uncached_frac_max: float = 0.5, relapse_below: float = 0.2, rec_hit_above: float = 0.8,
                    rec_outstanding_below: float = 20.0, end_window_s: float = 300.0, cap: Optional[int] = None,
                    rec_window_s: float = 300.0) -> Dict[str, Any]:
    """The registered per-run rule of plan R1 on a simulated run (any arm with a gate block):

    (a) VALID: FU-hit < 0.2 over [t_on - 300, t_on) AND outstanding (> 50) at t_on (the tick sample at t_on, before the controller acts).
    (b) RELEASED: t_rel <= 7200 (``t_rel`` = the controller's release tick; for a lull arm the lull end; None = never).
    (c) POST-GOOD over [t_rel + 300, t_end): every 300-s window has FU-hit >= 0.5 (windows tiled from t_rel + 300; a remainder shorter
        than 300 s is covered by the window [t_end - 300, t_end), as analysis/rescue.py ``post_windows``; a window with no follow-up
        completion fails (c) but is not a relapse); the whole interval FU-hit > 0.8; uncached-token rate < 0.5 x ``uncached_ref``;
        trap_v2 RECOVERED over the last 300 s (all-turn hit > 0.8 AND mean outstanding < 20, the mean of the 10-s tick samples).
    RESCUED = a and b and c.  RELAPSE = some 300-s window after t_rel + 300 with FU-hit < 0.2.
    STUCK (the control-arm predicate of analysis/rescue.py): FU-hit over [t_on, t_end) < 0.2 AND NOT RECOVERED over the last 300 s.
    Also (descriptive):
    t_rec = analysis/rescue.py ``t_recovered``: the first tick t >= t_on (10-s grid) whose window [t, t + 300) ends by t_end and has
        FU-hit > 0.8 and mean outstanding < 20 (the mean of the tick samples in the window; rescue.py integrates exactly).
    fu_pre_rel = FU-hit over [t_rel - 300, t_rel); trapped_at_rel = fu_pre_rel < 0.2 (a lull that ends with the engine still trapped).
    With ``cap`` (the rescue cap): t_cap_last_bound = the last tick before t_rel with a non-empty gate (arrivals or paused), and
        post_rel_frac_in_system_ge_cap / post_rel_max_in_system over the ticks t >= t_rel (how close the uncapped run came to the cap)."""
    done = _done_array(res)
    tr = trace_frame(res)
    out: Dict[str, Any] = {}
    fu_v, n_v = fu_hit(done, t_on - valid_window_s, t_on)
    at_on = tr[tr["t"] >= t_on - 1e-9]
    out_on = float(at_on["outstanding"].iloc[0]) if len(at_on) else float("nan")
    out.update(fu_valid=fu_v, n_fu_valid=n_v, outstanding_at_on=out_on,
               in_system_at_on=float(at_on["in_system"].iloc[0]) if len(at_on) else float("nan"))
    out["VALID"] = bool(fu_v == fu_v and fu_v < 0.2 and out_on > valid_outstanding_above)
    out["t_rel"] = t_rel
    out["RELEASED"] = bool(t_rel is not None and t_rel <= release_by)
    post_good = False
    relapse = False
    if t_rel is not None and t_rel + post_delay_s < t_end:
        a = t_rel + post_delay_s
        wins = [fu_hit(done, w0, w1) for w0, w1 in post_windows(a, t_end, win_s)]
        vals = [h for h, n in wins if n > 0]
        out["post_min_win_fu"] = float(min(vals)) if vals else float("nan")
        out["post_n_windows"] = len(wins)
        out["post_n_windows_nan"] = sum(1 for _, n in wins if n == 0)
        fu_all, _ = fu_hit(done, a, t_end)
        out["post_fu"] = fu_all
        unc = uncached_rate(done, a, t_end)
        out["post_uncached_rate"] = unc
        out["post_uncached_rel"] = unc / uncached_ref
        relapse = any(n > 0 and h < relapse_below for h, n in wins)
        end_hit = all_hit(done, t_end - end_window_s, t_end)
        tail = tr[(tr["t"] >= t_end - end_window_s) & (tr["t"] < t_end)]
        end_out = float(tail["outstanding"].mean()) if len(tail) else float("nan")
        recovered_end = bool(end_hit == end_hit and end_hit > rec_hit_above and end_out < rec_outstanding_below)
        post_good = bool(wins and len(vals) == len(wins) and min(vals) >= post_win_min and fu_all == fu_all and fu_all > post_all_min and unc < uncached_frac_max * uncached_ref
                         and recovered_end)
        out["post_recovered_end"] = recovered_end
    out["POST_GOOD"] = post_good
    out["RELAPSE"] = relapse
    out["RESCUED"] = bool(out["VALID"] and out["RELEASED"] and post_good)
    # recovery time (the analysis/rescue.py t_recovered definition, vectorised over the ticks)
    t = tr["t"].to_numpy(dtype=float)
    o = tr["outstanding"].to_numpy(dtype=float)
    fu_sel = done[:, 2] >= 2
    ft = done[fu_sel, 0]
    order = np.argsort(ft, kind="stable")
    ft, fh = ft[order], done[fu_sel, 3][order]
    ch = np.concatenate([[0.0], np.cumsum(fh)])
    co = np.concatenate([[0.0], np.cumsum(o)])
    cand = np.nonzero((t >= t_on - 1e-9) & (t + rec_window_s <= t_end + 1e-9))[0]
    t_rec = None
    if len(cand):
        t0s = t[cand]
        lo, hi = np.searchsorted(ft, t0s, side="left"), np.searchsorted(ft, t0s + rec_window_s, side="left")
        n = hi - lo
        h = np.where(n > 0, (ch[hi] - ch[lo]) / np.maximum(n, 1), np.nan)
        a, b = np.searchsorted(t, t0s - 1e-9, side="left"), np.searchsorted(t, t0s + rec_window_s - 1e-9, side="left")
        m = np.where(b > a, (co[b] - co[a]) / np.maximum(b - a, 1), np.nan)
        ok = (n > 0) & (h > rec_hit_above) & (m < rec_outstanding_below)
        if ok.any():
            t_rec = float(t0s[int(np.argmax(ok))])
    out["t_rec"] = t_rec
    # descriptive: the state when control was removed and after it
    out["fu_pre_rel"] = fu_hit(done, t_rel - 300.0, t_rel)[0] if t_rel is not None else float("nan")
    out["trapped_at_rel"] = bool(out["fu_pre_rel"] == out["fu_pre_rel"] and out["fu_pre_rel"] < relapse_below)
    out["t_cap_last_bound"] = out["rel_after_last_bound_s"] = float("nan")
    out["post_rel_frac_in_system_ge_cap"] = out["post_rel_max_in_system"] = float("nan")
    if cap is not None and t_rel is not None:
        before = tr[(tr["t"] < t_rel) & (tr["gate"] > 0)]
        if len(before):
            out["t_cap_last_bound"] = float(before["t"].iloc[-1])
            out["rel_after_last_bound_s"] = float(t_rel) - out["t_cap_last_bound"]
        after = tr[tr["t"] >= t_rel]
        if len(after):
            out["post_rel_frac_in_system_ge_cap"] = float((after["in_system"] >= cap).mean())
            out["post_rel_max_in_system"] = float(after["in_system"].max())
    # end-of-run state
    out["end_hit_all"] = all_hit(done, t_end - end_window_s, t_end)
    out["end_fu"] = fu_hit(done, t_end - end_window_s, t_end)[0]
    tail = tr[(tr["t"] >= t_end - end_window_s) & (tr["t"] < t_end)]
    out["end_outstanding"] = float(tail["outstanding"].mean()) if len(tail) else float("nan")
    out["end_gate"] = float(tail["gate"].mean()) if len(tail) else float("nan")
    out["end_in_system"] = float(tail["in_system"].mean()) if len(tail) else float("nan")
    out["end_recovered"] = bool(out["end_hit_all"] == out["end_hit_all"] and out["end_hit_all"] > rec_hit_above
                                and out["end_outstanding"] < rec_outstanding_below)
    out["max_gate_paused"] = int(tr["gate"].max()) if len(tr) else 0
    fu_after_on, _ = fu_hit(done, t_on, t_end)
    out["fu_after_on"] = fu_after_on
    out["STUCK"] = bool(fu_after_on == fu_after_on and fu_after_on < 0.2 and not out["end_recovered"])
    return out


def post_windows(t0: float, t1: float, w: float) -> List[Tuple[float, float]]:
    """Windows of length ``w`` over [t0, t1), tiled from t0; a remainder shorter than w is covered by [t1 - w, t1); empty if t1 - t0 < w
    (the tiling of analysis/rescue.py ``post_windows``)."""
    if not (t1 - t0) >= w - 1e-9:
        return []
    n = int(math.floor((t1 - t0) / w + 1e-9))
    wins = [(t0 + k * w, t0 + (k + 1) * w) for k in range(n)]
    if t0 + n * w < t1 - 1e-6:
        wins.append((t1 - w, t1))
    return wins
