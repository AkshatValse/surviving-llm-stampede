"""Open-loop multi-turn agent session load generator.

Open loop: sessions start at their planned arrival times regardless of how the server is doing (or, in
``closed`` mode, a fixed population is maintained for throughput calibration). Within a session the agent is a
closed loop: turn ``t+1`` is sent after the response to turn ``t`` plus a tool time ``Z_t``. Each request is
``POST /v1/completions`` with a prompt (token-id list or text), ``max_tokens=d`` and ``ignore_eos=true`` (via
``server.extra_body``), non-streaming.

Time convention. All logged times are seconds since run start on the event loop's monotonic clock.
``t_headers`` is when the response headers arrived; since streaming is off, servers typically send headers
together with the body, so ``t_headers`` is close to ``t_complete`` and is NOT a time-to-first-token.

Safety (a real engine under overload queues without bound): the run aborts, cancelling all in-flight
requests (which are logged with ``status=cancelled``), when more than ``run.max_inflight`` requests are
outstanding or ``run.max_errors`` requests failed. The abort reason and time are written to ``meta.json``.
SIGTERM / SIGINT abort the same way (reason ``signal_SIGTERM`` ...), so a job killed at its wall limit still
writes ``sessions.csv`` and a finished ``meta.json``.

Failed requests keep ``status=error`` and carry ``error_kind``: ``http`` (non-200), ``transport`` (connection
reset / server disconnected / payload error), ``timeout``, ``parse``, ``no_output`` or ``other``; counts per kind
are in ``meta.json`` (``outcome.errors_by_kind``). Connections are not reused by default
(``server.force_close_connections``): reuse races the server's keep-alive timeout.

Client-side session gate (``gate.n_cap``, the CAPPED arm). Sessions still arrive on the open-loop schedule, but at
most ``n_cap`` of them are admitted (= active: admitted and not yet ended); the rest wait in a FIFO queue between
arrival and their first request (:mod:`agentload.gate`). ``sessions.csv`` carries ``t_admit`` and ``gate_wait_s`` for
every session (0.0 without a gate); a session cancelled while still queued has an empty ``t_admit`` and
``gate_censored=1`` (its ``gate_wait_s`` is the wait up to the cancel). The first request's ``sched_delay_s`` is
measured from the admission time when the session waited (the wait is reported separately).

Time zero. ``meta.json`` records ``t0_unix`` (wall clock, ``time.time()``) taken at the instant the monotonic run
clock starts, so ``wall time = t0_unix + t_s`` aligns these logs with server.log, gpu_util.csv and SLURM logs.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import signal
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Tuple, Union

import aiohttp
import numpy as np
import yaml

from .config import Config, resolve_lambda_ref, resolve_n_cap, resolve_rate, resolve_ramp
from .gate import SessionGate
from .parse import extract_output_ids, extract_output_text, extract_usage
from .poller import MetricsPoller
from .runmeta import build_meta, git_info, new_result_dir, write_meta
from .workload import (ContentGen, Context, SessionPlan, build_open_plan, context_len, effective_mean_turns,
                       extend_context, make_closed_session)

REQ_FIELDS = ["req_id", "sid", "origin", "turn", "n_turns", "t_planned", "t_send", "t_headers", "t_complete",
              "latency_s", "sched_delay_s", "status", "http_status", "error", "prompt_tokens_client",
              "prompt_tokens", "completion_tokens", "cached_tokens", "cached_source", "output_ids_source",
              "prompt_hash", "raw_usage_json", "error_kind"]
SESSION_FIELDS = ["sid", "origin", "idx", "arrival_s", "n_turns", "t_first_send", "t_end", "turns_completed",
                  "status", "t_admit", "gate_wait_s", "gate_censored"]
PLAN_FIELDS = ["sid", "origin", "idx", "arrival_s", "n_turns", "tool_time_total_s"]


def prompt_hash(ctx: Context) -> str:
    b = ctx.encode() if isinstance(ctx, str) else np.ascontiguousarray(ctx, dtype=np.int32).tobytes()
    return hashlib.blake2b(b, digest_size=6).hexdigest()


def _raise_nofile() -> Dict[str, Any]:
    """Raise the soft RLIMIT_NOFILE towards min(hard, 65536) and return what happened (recorded in meta.json;
    -1 means unlimited). Never raises: the caller decides whether the resulting soft limit is enough."""
    info: Dict[str, Any] = {"soft_before": None, "soft_after": None, "hard": None, "error": None}
    try:
        import resource

        def enc(v: int) -> int:
            return -1 if v == resource.RLIM_INFINITY else int(v)

        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        info.update(soft_before=enc(soft), hard=enc(hard))
        want = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft != resource.RLIM_INFINITY and soft < want:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
            except (ValueError, OSError) as e:
                info["error"] = f"{type(e).__name__}: {e}"
        info["soft_after"] = enc(resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    except Exception as e:  # pragma: no cover  (non-Unix or restricted)
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def classify_error(e: BaseException) -> str:
    """Error kind of a failed request's exception (see module docstring)."""
    if isinstance(e, asyncio.TimeoutError):
        return "timeout"
    if isinstance(e, (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError)):
        return "transport"
    if isinstance(e, ValueError):               # json.JSONDecodeError
        return "parse"
    return "other"


class CsvLog:
    """Append-only CSV with periodic flush (partial results survive a killed job)."""

    def __init__(self, path: Path, fields: List[str]):
        self.fh: TextIO = open(path, "w", newline="")
        self.w = csv.DictWriter(self.fh, fieldnames=fields)
        self.w.writeheader()
        self.fields = fields
        self.n = 0

    def write(self, row: Dict[str, Any]) -> None:
        self.w.writerow({k: row.get(k, "") for k in self.fields})
        self.n += 1

    def flush(self) -> None:
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


@dataclass
class SessionState:
    plan: SessionPlan
    t_first_send: Optional[float] = None
    t_end: Optional[float] = None
    turns_completed: int = 0
    status: str = "pending"          # pending | gated | running | completed | failed | cancelled
    t_admit: Optional[float] = None  # when the session passed the gate (None: never admitted)
    gate_wait_s: float = 0.0


@dataclass
class Outcome:
    out_dir: Path
    abort_reason: Optional[str]
    t_end_s: float
    counts: Dict[str, int] = field(default_factory=dict)


class LoadGenerator:
    def __init__(self, cfg: Config, raw_cfg: Dict[str, Any], out_dir: Path, base_dir: Path):
        self.cfg, self.raw_cfg, self.out_dir, self.base_dir = cfg, raw_cfg, out_dir, base_dir
        self.seed = cfg.run.seed
        self.content = ContentGen(self.seed, cfg.workload)
        self.rate = resolve_rate(cfg.arrivals, base_dir) if cfg.arrivals.kind == "constant" else None
        self.ramp = resolve_ramp(cfg.arrivals, base_dir) if cfg.arrivals.kind == "ramp" else []
        self.n_cap = resolve_n_cap(cfg.gate, base_dir)
        self.url = cfg.server.base_url.rstrip("/") + cfg.server.completions_path
        self.states: Dict[int, SessionState] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self.inflight = 0
        self.n_req = 0
        self.n_ok = self.n_err = self.n_cancel = 0
        self.err_kinds: Counter = Counter()
        self.src_counts: Counter = Counter()          # output_ids_source of ok requests
        self.n_prompt_mismatch = 0                    # tokens mode: server prompt_tokens != tokens sent
        self.n_prompt_missing = 0                     # tokens mode: response had no prompt_tokens
        self.max_inflight_seen = 0
        self.abort_reason: Optional[str] = None
        self.t_abort: Optional[float] = None
        self._signals: List[signal.Signals] = []
        self._stop: asyncio.Event = None  # type: ignore[assignment]   # created in run() inside the loop
        self._closing = False
        self._next_closed_idx = 0
        self._next_sid = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._t0 = 0.0
        self.http: Optional[aiohttp.ClientSession] = None
        self.gate = SessionGate(self.n_cap, self.now)

    # ------------------------------------------------------------ time
    def now(self) -> float:
        assert self._loop is not None
        return self._loop.time() - self._t0

    async def _sleep_until(self, t: float) -> None:
        d = t - self.now()
        if d > 0:
            await asyncio.sleep(d)

    # ------------------------------------------------------------ plan
    def build_plan(self) -> List[SessionPlan]:
        a = self.cfg.arrivals
        if a.kind == "closed":
            return []
        return build_open_plan(self.seed, self.cfg.workload, a, self.cfg.run.duration_s, self.rate, self.ramp)

    # ------------------------------------------------------------ abort
    def _abort(self, reason: str) -> None:
        if self.abort_reason is None:
            self.abort_reason = reason
            self.t_abort = self.now() if self._t0 else None      # None: aborted before the run clock started
        self._stop.set()

    def _install_signals(self) -> None:
        assert self._loop is not None
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                self._loop.add_signal_handler(sig, self._abort, f"signal_{sig.name}")
                self._signals.append(sig)
            except (NotImplementedError, RuntimeError, ValueError):   # non-main thread / non-Unix
                pass

    def _remove_signals(self) -> None:
        for sig in self._signals:
            try:
                assert self._loop is not None
                self._loop.remove_signal_handler(sig)
            except Exception:  # pragma: no cover
                pass
        self._signals = []

    # ------------------------------------------------------------ one request
    async def _send(self, sp: SessionPlan, turn: int, ctx: Context, t_planned: float
                    ) -> Optional[Union[np.ndarray, str]]:
        """Send one turn. Returns the model output to append to the context, or None if the request failed (or
        returned nothing usable). The request row is always logged, including on cancellation."""
        wl, srv = self.cfg.workload, self.cfg.server
        prompt: Any = ctx.tolist() if isinstance(ctx, np.ndarray) else ctx
        body: Dict[str, Any] = {"model": srv.model, "prompt": prompt, "max_tokens": wl.decode_tokens,
                                "temperature": wl.temperature, "stream": False}
        body.update(srv.extra_body)
        if srv.request_token_ids:
            body["return_token_ids"] = True
        self.n_req += 1
        row: Dict[str, Any] = {"req_id": self.n_req, "sid": sp.sid, "origin": sp.origin, "turn": turn,
                               "n_turns": sp.n_turns, "t_planned": t_planned,
                               "prompt_tokens_client": context_len(ctx), "prompt_hash": prompt_hash(ctx)}
        t_send = self.now()
        row["t_send"] = t_send
        row["sched_delay_s"] = t_send - t_planned
        self.inflight += 1
        self.max_inflight_seen = max(self.max_inflight_seen, self.inflight)
        if self.inflight > self.cfg.run.max_inflight:
            self._abort(f"max_inflight>{self.cfg.run.max_inflight}")
        out: Optional[Union[np.ndarray, str]] = None
        try:
            assert self.http is not None
            to = aiohttp.ClientTimeout(total=srv.request_timeout_s)
            async with self.http.post(self.url, json=body, timeout=to) as resp:
                row["t_headers"] = self.now()
                row["http_status"] = resp.status
                raw = await resp.read()
                if resp.status == 200:
                    data = json.loads(raw)
                    row["status"] = "ok"
                    row.update(extract_usage(data))
                    nxt = self._next_output(sp, turn, data)
                    if nxt is None:
                        row["status"] = "error"
                        row["error_kind"] = "no_output"
                        row["error"] = "no usable model output (missing text / token ids)"
                    else:
                        out, row["output_ids_source"] = nxt
                else:
                    row["status"] = "error"
                    row["error_kind"] = "http"
                    row["error"] = raw[:300].decode("utf-8", "replace")
        except asyncio.CancelledError:
            row["status"] = "cancelled"
            row["error"] = "cancelled"
            raise
        except Exception as e:
            row["status"] = "error"
            row["error_kind"] = classify_error(e)
            row["error"] = f"{type(e).__name__}: {e}"[:300]
        finally:
            self.inflight -= 1
            t_c = self.now()
            row["t_complete"] = t_c
            row["latency_s"] = t_c - t_send
            st = row.get("status", "error")
            row["status"] = st
            if st == "ok":
                self.n_ok += 1
                self.src_counts[str(row.get("output_ids_source", ""))] += 1
                if wl.prompt_mode == "tokens":          # plan check (g): the server counted what we sent
                    if row.get("prompt_tokens") is None:
                        self.n_prompt_missing += 1
                    elif row["prompt_tokens"] != row["prompt_tokens_client"]:
                        self.n_prompt_mismatch += 1
            elif st == "cancelled":
                self.n_cancel += 1
            else:
                self.n_err += 1
                self.err_kinds[str(row.get("error_kind", "other"))] += 1
                if self.n_err >= self.cfg.run.max_errors:
                    self._abort(f"max_errors>={self.cfg.run.max_errors}")
            self.req_log.write(row)
        return out if row["status"] == "ok" else None

    def _next_output(self, sp: SessionPlan, turn: int, data: Dict[str, Any]
                     ) -> Optional[Tuple[Union[np.ndarray, str], str]]:
        """(context fragment for the model's output, source tag), or None if no usable output."""
        wl = self.cfg.workload
        if wl.prompt_mode == "text":
            txt = extract_output_text(data)
            return (txt, "server_text") if txt else None
        ids = None
        if wl.output_feedback != "synthetic":
            ids = extract_output_ids(data, self.cfg.server.output_ids_paths)
        if ids is not None:
            return np.asarray(ids, dtype=np.int32), "server_ids"
        if wl.output_feedback == "server":
            return None
        return self.content.synthetic_output(sp, turn), "synthetic"

    # ------------------------------------------------------------ one session
    async def _session(self, sp: SessionPlan) -> None:
        st = self.states[sp.sid]
        admitted = False
        try:
            if self.n_cap is not None:
                st.status = "gated"
            st.gate_wait_s = await self.gate.acquire()           # FIFO; returns at once when there is no cap / room
            admitted = True
            st.t_admit = self.now()
            st.status = "running"
            ctx = self.content.initial(sp)
            t_planned = sp.arrival_s if st.gate_wait_s <= 0.0 else st.t_admit
            for turn in range(1, sp.n_turns + 1):
                if turn > 1:
                    ctx = extend_context(ctx, self.content.delta(sp, turn))
                    await self._sleep_until(t_planned)
                if st.t_first_send is None:
                    st.t_first_send = self.now()
                out = await self._send(sp, turn, ctx, t_planned)
                if out is None:
                    st.status = "failed"
                    return
                st.turns_completed = turn
                ctx = extend_context(ctx, out)
                if turn < sp.n_turns:
                    t_planned = self.now() + sp.tool_times_s[turn - 1]
            st.status = "completed"
        except asyncio.CancelledError:
            st.status = "cancelled"
            raise
        finally:
            st.t_end = self.now()
            if not admitted:                                     # cancelled while queued: censored wait
                st.gate_wait_s = st.t_end - sp.arrival_s
            if admitted:
                self.gate.release()
            if st.status == "running":
                st.status = "failed"
            if self.cfg.arrivals.kind == "closed" and not self._closing and st.status in ("completed", "failed"):
                self._spawn_closed()

    def _lambda_ref_value(self) -> Optional[float]:
        """Resolved ``arrivals.lambda_ref`` (sessions/s; the lambda_miss the arrival rate is a multiple of), if set and
        resolvable. The analysis needs it to judge the trap criterion; a placeholder here already failed in resolve_rate."""
        ref = self.cfg.arrivals.lambda_ref
        if ref is None:
            return None
        try:
            return float(resolve_lambda_ref(ref, self.base_dir))
        except (FileNotFoundError, ValueError):
            return None

    # ------------------------------------------------------------ spawning
    def _spawn(self, sp: SessionPlan) -> None:
        self.states[sp.sid] = SessionState(plan=sp)
        self.tasks[sp.sid] = asyncio.get_running_loop().create_task(self._session(sp))

    def _spawn_closed(self) -> None:
        idx = self._next_closed_idx
        self._next_closed_idx += 1
        sp = make_closed_session(self.seed, self.cfg.workload, self._next_sid, idx, self.now())
        self._next_sid += 1
        self._spawn(sp)

    async def _scheduler(self, plan: List[SessionPlan]) -> None:
        for sp in plan:
            await self._sleep_until(sp.arrival_s)
            self._spawn(sp)

    # ------------------------------------------------------------ run
    def _client_gauges(self) -> Dict[str, float]:
        active = sum(1 for s in self.states.values() if s.status == "running")
        gated = sum(1 for s in self.states.values() if s.status == "gated")
        return {"agentload:inflight_requests": float(self.inflight), "agentload:active_sessions": float(active),
                "agentload:gated_sessions": float(gated), "agentload:sessions_in_system": float(active + gated)}

    async def _preflight(self) -> Dict[str, Any]:
        """Wait (up to run.preflight_wait_s) for the health endpoint; record /v1/models for meta.json."""
        srv = self.cfg.server
        deadline = time.monotonic() + self.cfg.run.preflight_wait_s
        last = ""
        while True:
            if self._stop.is_set():
                raise RuntimeError(f"aborted during preflight ({self.abort_reason})")
            try:
                assert self.http is not None
                async with self.http.get(srv.base_url.rstrip("/") + srv.health_path,
                                         timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        break
                    last = f"health status {r.status}"
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            if time.monotonic() > deadline:
                raise RuntimeError(f"server not healthy at {srv.base_url}{srv.health_path}: {last}")
            await asyncio.sleep(1.0)
        info: Dict[str, Any] = {}
        try:
            async with self.http.get(srv.base_url.rstrip("/") + srv.models_path,
                                     timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    info = await r.json()
        except Exception as e:
            info = {"error": f"{type(e).__name__}: {e}"}
        ids = [m.get("id") for m in (info.get("data") or []) if isinstance(m, dict)]
        if ids and srv.model not in ids:       # e.g. a foreign server on the derived port: refuse to drive it
            raise RuntimeError(f"server at {srv.base_url} serves {ids}, not the configured model {srv.model!r}")
        info["model_check"] = ("ok" if ids else "unverified (no model list returned)")
        return info

    async def run(self, argv: List[str], git: Dict[str, Any], t_start: datetime, plan: List[SessionPlan]
                  ) -> Outcome:
        cfg = self.cfg
        nofile = _raise_nofile()
        self._loop = asyncio.get_running_loop()
        self.req_log = CsvLog(self.out_dir / "requests.csv", REQ_FIELDS)
        self.events: List[str] = []
        self._stop = asyncio.Event()
        self._install_signals()
        connector = aiohttp.TCPConnector(limit=0, force_close=cfg.server.force_close_connections)
        self.http = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=None))
        poller: Optional[MetricsPoller] = None
        poll_task: Optional[asyncio.Task] = None
        sched_task: Optional[asyncio.Task] = None
        flush_task: Optional[asyncio.Task] = None
        t_end = t_end_all = 0.0
        meta_extra: Dict[str, Any] = {
            "config_effective_file": "config_effective.yaml", "n_sessions_planned": len(plan),
            "resolved_rate_sessions_per_s": self.rate, "ramp_knots": self.ramp,
            "engine_label": cfg.meta.engine_label, "notes": cfg.meta.notes,
            "expected_turns_per_session": effective_mean_turns(cfg.workload),
            "duration_s_configured": cfg.run.duration_s,
            "time_convention": "seconds since run start (event-loop monotonic clock); wall time = t0_unix + t_s",
            "rlimit_nofile": nofile, "force_close_connections": cfg.server.force_close_connections,
            "output_feedback_configured": cfg.workload.output_feedback, "prompt_mode": cfg.workload.prompt_mode,
            "request_token_ids": cfg.server.request_token_ids, "content_salt": cfg.workload.content_salt,
            "start_state_verified": cfg.meta.start_state_verified, "start_state_detail": cfg.meta.start_state_detail,
            "arm": cfg.meta.arm, "analysis_t_burst_s": cfg.arrivals.analysis_t_burst_s,
            "gate_n_cap_configured": cfg.gate.n_cap, "gate_n_cap_resolved": self.n_cap,
            "lambda_ref_resolved": self._lambda_ref_value()}

        def meta(status: str, ended: bool = False) -> None:
            write_meta(self.out_dir, build_meta(experiment=cfg.output.name, argv=argv, seeds=[self.seed],
                                                hardware=cfg.meta.hardware, git=git, t_start=t_start,
                                                t_end=datetime.now() if ended else None, extra=meta_extra,
                                                status=status))

        meta("starting")                      # a record exists even if the preflight fails
        try:
            need_fds = cfg.run.max_inflight + 256
            soft = nofile.get("soft_after")
            if soft is not None and soft != -1 and soft < need_fds:
                raise RuntimeError(f"RLIMIT_NOFILE soft limit {soft} < run.max_inflight + 256 = {need_fds} "
                                   f"(hard {nofile.get('hard')}): in-flight sockets would fail as connector errors")
            meta_extra["server_models"] = await self._preflight()
            self._t0 = self._loop.time()
            meta_extra["t0_unix"] = time.time()             # wall-clock anchor of t_s = 0 (see module docstring)
            meta_extra["t0_utc"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            meta_extra["t0_monotonic_s"] = self._t0
            meta("running")
            if cfg.metrics.enabled:
                poller = MetricsPoller(self.http, cfg.server.base_url.rstrip("/") + cfg.server.metrics_path,
                                       cfg.metrics, self.out_dir, self.now, self._client_gauges)
                poller.open()
                poll_task = self._loop.create_task(poller.run())
            flush_task = self._loop.create_task(self._flusher())
            if cfg.arrivals.kind == "closed":
                for _ in range(cfg.arrivals.closed_n):
                    self._spawn_closed()
            else:
                sched_task = self._loop.create_task(self._scheduler(plan))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=cfg.run.duration_s)
            except asyncio.TimeoutError:
                pass
            t_end = self.now()
            self._closing = True
            if sched_task:
                sched_task.cancel()
            for t in list(self.tasks.values()):
                t.cancel()
            await asyncio.gather(*([sched_task] if sched_task else []), *self.tasks.values(),
                                 return_exceptions=True)
            t_end_all = self.now()
        except BaseException as e:
            meta_extra["error"] = f"{type(e).__name__}: {e}"
            meta("failed", ended=True)
            raise
        finally:
            for t in (poll_task, flush_task):
                if t:
                    t.cancel()
            await asyncio.gather(*[t for t in (poll_task, flush_task) if t], return_exceptions=True)
            if poller:
                poller.close()
            self._remove_signals()
            await self.http.close()
            self._finalize_files()
        counts = {"sessions_planned": len(plan), "sessions_started": len(self.states),
                  "sessions_completed": sum(s.status == "completed" for s in self.states.values()),
                  "sessions_failed": sum(s.status == "failed" for s in self.states.values()),
                  "sessions_cancelled": sum(s.status == "cancelled" for s in self.states.values()),
                  "sessions_never_admitted": sum(s.t_admit is None for s in self.states.values()),
                  "requests_total": self.n_req, "requests_ok": self.n_ok, "requests_error": self.n_err,
                  "requests_cancelled": self.n_cancel, "max_inflight_seen": self.max_inflight_seen,
                  "metrics_scrapes": poller.n_scrapes if poller else 0,
                  "metrics_scrape_failures": poller.n_failures if poller else 0,
                  "metrics_skipped_ticks": poller.n_skipped_ticks if poller else 0}
        if poller and poller.first_scrape_unix is not None:
            meta_extra["first_metrics_scrape_unix"] = poller.first_scrape_unix
            meta_extra["first_metrics_scrape_t_s"] = poller.first_scrape_t_s
        meta_extra["outcome"] = {"abort_reason": self.abort_reason, "t_abort_s": self.t_abort, "t_end_s": t_end,
                                 "t_end_incl_cancel_s": t_end_all, **counts,
                                 "errors_by_kind": dict(self.err_kinds), "gate": self.gate.summary(),
                                 "output_ids_source_counts": dict(self.src_counts),
                                 "prompt_tokens_mismatch": self.n_prompt_mismatch,
                                 "prompt_tokens_missing_in_response": self.n_prompt_missing}
        meta("finished", ended=True)
        return Outcome(out_dir=self.out_dir, abort_reason=self.abort_reason, t_end_s=t_end, counts=counts)

    async def _flusher(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.cfg.run.flush_every_s)
                self.req_log.flush()
        except asyncio.CancelledError:
            pass

    def _finalize_files(self) -> None:
        """Close request log; write sessions.csv and events.log."""
        self.req_log.close()
        with open(self.out_dir / "sessions.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=SESSION_FIELDS)
            w.writeheader()
            for sid in sorted(self.states):
                s = self.states[sid]
                w.writerow({"sid": sid, "origin": s.plan.origin, "idx": s.plan.idx, "arrival_s": s.plan.arrival_s,
                            "n_turns": s.plan.n_turns, "t_first_send": s.t_first_send, "t_end": s.t_end,
                            "turns_completed": s.turns_completed, "status": s.status,
                            "t_admit": "" if s.t_admit is None else s.t_admit, "gate_wait_s": s.gate_wait_s,
                            "gate_censored": int(s.t_admit is None)})
        (self.out_dir / "events.log").write_text("\n".join(self.events) + ("\n" if self.events else ""))


def write_plan_csv(path: Path, plan: List[SessionPlan]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_FIELDS)
        w.writeheader()
        for sp in plan:
            w.writerow({"sid": sp.sid, "origin": sp.origin, "idx": sp.idx, "arrival_s": sp.arrival_s,
                        "n_turns": sp.n_turns, "tool_time_total_s": float(sum(sp.tool_times_s))})


def run_experiment(cfg: Config, raw_cfg: Dict[str, Any], cfg_path: str | Path, argv: List[str],
                   repo_dir: Path) -> Outcome:
    """Create the result dir, capture git state first, run the generator, write all outputs. Blocking."""
    git = git_info(repo_dir)                       # captured at START, before anything else
    t_start = datetime.now()
    out_dir = new_result_dir(cfg.output.root, cfg.output.name)
    Path(out_dir / "config.yaml").write_text(Path(cfg_path).read_text())
    (out_dir / "config_effective.yaml").write_text(yaml.safe_dump(raw_cfg, sort_keys=False))
    gen = LoadGenerator(cfg, raw_cfg, out_dir, repo_dir)
    plan = gen.build_plan()
    write_plan_csv(out_dir / "plan.csv", plan)
    return asyncio.run(gen.run(argv, git, t_start, plan))
