"""Harness robustness found in review round 3: keep-alive races, error classification, SIGTERM finalization,
wall-clock anchor, foreign-server refusal, text-mode gating, content salt, fd limits, scrape overrun, probe."""
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import numpy as np
import pandas as pd
import pytest
import yaml

from agentload import client as client_mod
from agentload.client import classify_error
from agentload.config import MetricsCfg, config_from_dict
from agentload.mock_server import MockConfig
from agentload.poller import MetricsPoller
from agentload.workload import ContentGen, SessionPlan, build_open_plan
from conftest import REPO, make_raw, run_gen

FAST = dict(kv_capacity_tokens=10**7, slots=64, fixed_s=0.001, per_uncached_token_s=0, per_completion_token_s=0)


def load(out):
    d = out.out_dir
    return pd.read_csv(d / "requests.csv"), json.loads((d / "meta.json").read_text())


# ------------------------------------------------------------------ finding 1: keep-alive race
def keepalive_raw(force_close=True):
    return make_raw(server={"force_close_connections": force_close},
                    workload={"tool_time_dist": "const", "tool_time_mean_s": 0.25, "mean_turns": 6, "max_turns": 10},
                    arrivals={"rate": 25.0}, run={"duration_s": 6.0}, metrics={"enabled": False})


def test_short_server_keepalive_causes_no_transport_errors(tmp_path):
    # server closes idle connections after 0.25 s == the tool time: reused connections would race the close
    out, _ = run_gen(keepalive_raw(), MockConfig(keepalive_timeout_s=0.25, **FAST), tmp_path)
    req, meta = load(out)
    assert len(req) > 300
    assert (req["status"] == "ok").sum() + (req["status"] == "cancelled").sum() == len(req)
    o = meta["outcome"]
    assert o["errors_by_kind"].get("transport", 0) == 0 and o["requests_error"] == 0 and o["sessions_failed"] == 0
    assert meta["force_close_connections"] is True


def test_the_session_uses_a_force_close_connector(tmp_path, monkeypatch):
    seen = []
    orig = aiohttp.TCPConnector.__init__

    def spy(self, *a, **kw):
        seen.append(kw.get("force_close"))
        orig(self, *a, **kw)
    monkeypatch.setattr(aiohttp.TCPConnector, "__init__", spy)
    run_gen(make_raw(run={"duration_s": 1.0}, metrics={"enabled": False}), MockConfig(**FAST), tmp_path)
    assert seen and seen[0] is True                       # the generator's own connector (limit=0, force_close=True)
    assert config_from_dict(make_raw()).server.force_close_connections is True


def test_error_kinds_are_classified(tmp_path):
    assert classify_error(aiohttp.ServerDisconnectedError()) == "transport"
    assert classify_error(aiohttp.ClientOSError(104, "Connection reset by peer")) == "transport"
    assert classify_error(aiohttp.ClientPayloadError("x")) == "transport"
    assert classify_error(asyncio.TimeoutError()) == "timeout"
    assert classify_error(aiohttp.ServerTimeoutError()) == "timeout"
    assert classify_error(json.JSONDecodeError("m", "d", 0)) == "parse"
    assert classify_error(KeyError("x")) == "other"
    out, _ = run_gen(make_raw(arrivals={"rate": 10.0}, run={"duration_s": 3.0, "max_errors": 1000},
                              metrics={"enabled": False}), MockConfig(fail_every_n=3, **FAST), tmp_path)
    req, meta = load(out)
    err = req[req["status"] == "error"]
    assert len(err) > 5 and (err["error_kind"] == "http").all()
    assert req[req["status"] == "ok"]["error_kind"].isna().all()
    assert meta["outcome"]["errors_by_kind"] == {"http": len(err)}


def test_a_dead_server_is_a_transport_error_with_its_own_kind(tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    sock.close()                                            # nothing listens here any more
    from agentload.client import LoadGenerator
    raw = make_raw(run={"duration_s": 1.0}, metrics={"enabled": False})
    raw["server"]["base_url"] = f"http://127.0.0.1:{port}"
    cfg = config_from_dict(raw)

    async def go():
        gen = LoadGenerator(cfg, raw, tmp_path, REPO)
        gen._loop = asyncio.get_running_loop()
        gen._t0 = gen._loop.time()
        gen.req_log = client_mod.CsvLog(tmp_path / "r.csv", client_mod.REQ_FIELDS)
        gen.http = aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True))
        gen._stop = asyncio.Event()
        sp = SessionPlan(sid=0, origin="base", idx=0, arrival_s=0.0, n_turns=2, tool_times_s=(0.0,))
        out = await gen._send(sp, 1, gen.content.initial(sp), 0.0)
        await gen.http.close()
        gen.req_log.close()
        return out, gen
    out, gen = asyncio.run(go())
    assert out is None and gen.err_kinds == {"transport": 1}
    row = pd.read_csv(tmp_path / "r.csv").iloc[0]
    assert row["status"] == "error" and row["error_kind"] == "transport"


# ------------------------------------------------------------------ finding: SIGTERM finalizes the run
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_sigterm_finalizes_meta_and_sessions(tmp_path):
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    srv = subprocess.Popen([sys.executable, "-m", "agentload.mock_server", "--port", str(port)], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        gen = subprocess.Popen([sys.executable, "-m", "agentload", "run", "--config", str(REPO / "configs/agentload_mock.yaml"),
                                "--set", f"server.base_url=\"http://127.0.0.1:{port}\"", "--set", "run.duration_s=120",
                                "--out-root", str(tmp_path), "--name", "sigterm"],
                               env=env, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(4.0)
        gen.send_signal(signal.SIGTERM)
        out, err = gen.communicate(timeout=30)
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    assert gen.returncode == 143, (out, err)
    d = next((tmp_path / "sigterm").iterdir())
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "finished" and meta["outcome"]["abort_reason"] == "signal_SIGTERM"
    assert 2.0 < meta["outcome"]["t_end_s"] < 15.0
    ses = pd.read_csv(d / "sessions.csv")
    req = pd.read_csv(d / "requests.csv")
    assert len(ses) > 3 and len(req) > 5 and req["t_complete"].notna().all()           # nothing left half-written
    assert set(req["status"]) <= {"ok", "cancelled"}


# ------------------------------------------------------------------ wall-clock anchor, model check, rlimit
def test_meta_has_a_wall_clock_anchor_for_t_zero(tmp_path):
    t_before = time.time()
    out, _ = run_gen(make_raw(run={"duration_s": 2.0}), MockConfig(**FAST), tmp_path)
    t_after = time.time()
    req, meta = load(out)
    assert t_before <= meta["t0_unix"] <= t_after
    assert abs(datetime.fromisoformat(meta["t0_utc"]).timestamp() - meta["t0_unix"]) < 0.01
    # first metrics scrape is at ~0 s on the run clock and has its own wall timestamp
    assert abs(meta["first_metrics_scrape_unix"] - (meta["t0_unix"] + meta["first_metrics_scrape_t_s"])) < 0.05
    assert meta["first_metrics_scrape_t_s"] < 0.2
    assert meta["time_convention"].endswith("wall time = t0_unix + t_s")
    # a request's wall time via the anchor lies inside the run's wall interval
    first = req.sort_values("t_send").iloc[0]
    assert t_before <= meta["t0_unix"] + first["t_send"] <= t_after


def test_a_server_that_does_not_serve_the_configured_model_is_refused(tmp_path):
    raw = make_raw(server={"model": "Qwen/Qwen2.5-7B-Instruct"}, run={"duration_s": 1.0})
    with pytest.raises(RuntimeError, match="serves \\['mock'\\], not the configured model"):
        run_gen(raw, MockConfig(**FAST), tmp_path)
    d = next((tmp_path / "agentload_test").iterdir())
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "failed" and "configured model" in meta["error"]
    assert not (d / "sessions.csv").read_text().strip().splitlines()[1:]              # no request was sent


def test_nofile_limit_is_recorded_and_too_low_a_limit_fails_fast(tmp_path, monkeypatch):
    out, _ = run_gen(make_raw(run={"duration_s": 1.0}), MockConfig(**FAST), tmp_path / "a")
    _, meta = load(out)
    assert {"soft_before", "soft_after", "hard", "error"} <= set(meta["rlimit_nofile"])
    monkeypatch.setattr(client_mod, "_raise_nofile", lambda: {"soft_before": 256, "soft_after": 256, "hard": 256, "error": None})
    with pytest.raises(RuntimeError, match="RLIMIT_NOFILE soft limit 256"):
        run_gen(make_raw(run={"duration_s": 1.0, "max_inflight": 500}), MockConfig(**FAST), tmp_path / "b")
    d = next((tmp_path / "b" / "agentload_test").iterdir())
    assert json.loads((d / "meta.json").read_text())["status"] == "failed"


def test_raise_nofile_reports_what_happened():
    info = client_mod._raise_nofile()
    assert info["soft_after"] is not None and (info["soft_after"] == -1 or info["soft_after"] >= info["soft_before"] or info["error"])


# ------------------------------------------------------------------ text mode, content salt, token accounting
def test_text_mode_is_rejected_for_real_engines_unless_explicitly_allowed():
    with pytest.raises(ValueError, match="only allowed for mock engines"):
        config_from_dict(make_raw(workload={"prompt_mode": "text"}, meta={"engine_label": "sglang-fcfs-r1"}))
    config_from_dict(make_raw(workload={"prompt_mode": "text", "allow_text_mode": True},
                              meta={"engine_label": "sglang-fcfs-r1"}))
    config_from_dict(make_raw(workload={"prompt_mode": "text"}, meta={"engine_label": "mock-x"}))


def test_content_salt_changes_content_but_not_arrivals_or_specs():
    base = config_from_dict(make_raw())
    salted = config_from_dict(make_raw(workload={"content_salt": 3}))
    other = config_from_dict(make_raw(workload={"content_salt": 4}))
    sp = SessionPlan(sid=0, origin="base", idx=7, arrival_s=0.0, n_turns=3, tool_times_s=(1.0, 1.0))
    a, b, c = (ContentGen(0, w.workload).initial(sp) for w in (base, salted, other))
    assert not np.array_equal(a, b) and not np.array_equal(b, c)
    assert np.array_equal(b, ContentGen(0, salted.workload).initial(sp))              # deterministic per salt
    for cfg in (base, salted):
        assert not np.array_equal(ContentGen(0, cfg.workload).delta(sp, 2), ContentGen(0, cfg.workload).initial(sp)[:30])
    p0 = build_open_plan(0, base.workload, base.arrivals, 30.0, 2.0, [])
    p1 = build_open_plan(0, salted.workload, salted.arrivals, 30.0, 2.0, [])
    assert p0 == p1                                                                   # arrivals / specs untouched
    with pytest.raises(ValueError):
        config_from_dict(make_raw(workload={"content_salt": -1}))


def test_salt_keeps_a_missed_flush_from_inflating_the_next_runs_hits(tmp_path):
    mc = MockConfig(**FAST, log_requests=True)
    r0 = make_raw(run={"duration_s": 2.0}, arrivals={"rate": 5.0}, metrics={"enabled": False})
    _, t0 = run_gen(r0, mc, tmp_path / "a")
    r1 = make_raw(run={"duration_s": 2.0}, arrivals={"rate": 5.0}, workload={"content_salt": 1}, metrics={"enabled": False})
    _, t1 = run_gen(r1, mc, tmp_path / "b")
    first0 = {tuple(u[:8]) for u in t0["seen"]}
    first1 = {tuple(u[:8]) for u in t1["seen"]}
    assert len(first0) > 3 and len(first1) > 3 and not (first0 & first1)             # no shared session prefix across runs
    q0, q1 = (pd.read_csv(o) for o in sorted((tmp_path).glob("*/agentload_test/*/requests.csv")))
    assert set(q0["prompt_hash"]).isdisjoint(set(q1["prompt_hash"]))


def test_token_accounting_and_source_counts_in_meta(tmp_path):
    out, _ = run_gen(make_raw(run={"duration_s": 2.0}, metrics={"enabled": False}), MockConfig(**FAST), tmp_path)
    req, meta = load(out)
    o = meta["outcome"]
    assert o["prompt_tokens_mismatch"] == 0 and o["prompt_tokens_missing_in_response"] == 0
    assert o["output_ids_source_counts"] == {"server_ids": int((req["status"] == "ok").sum())}
    assert meta["start_state_verified"] is None and meta["content_salt"] == 0


def test_a_prompt_token_mismatch_is_counted(tmp_path, monkeypatch):
    from agentload import parse
    real = parse.extract_usage

    def lying(data):
        u = real(data)
        u["prompt_tokens"] = (u["prompt_tokens"] or 0) + 1
        return u
    monkeypatch.setattr(client_mod, "extract_usage", lying)
    out, _ = run_gen(make_raw(run={"duration_s": 1.5}, metrics={"enabled": False}), MockConfig(**FAST), tmp_path)
    req, meta = load(out)
    assert meta["outcome"]["prompt_tokens_mismatch"] == int((req["status"] == "ok").sum()) > 3


# ------------------------------------------------------------------ poller: overrun, no catch-up burst
def test_scrape_overrun_skips_ticks_instead_of_bursting(tmp_path):
    async def go():
        p = MetricsPoller(None, "http://x", MetricsCfg(interval_s=0.1), tmp_path, lambda: 0.0)
        p.open()
        stamps = []

        async def slow():                      # a scrape that takes 0.35 s with a 0.1 s interval
            stamps.append(time.monotonic())
            await asyncio.sleep(0.35)
            p.n_scrapes += 1
        p.scrape_once = slow                   # type: ignore[assignment]
        t = asyncio.get_running_loop().create_task(p.run())
        await asyncio.sleep(1.5)
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)
        p.close()
        return p, stamps
    p, stamps = asyncio.run(go())
    gaps = np.diff(stamps)
    assert p.n_skipped_ticks >= 3 and len(stamps) <= 5
    assert (gaps >= 0.4).all()                 # never back-to-back (a catch-up burst would give ~0.35 s gaps)


def test_first_scrape_wall_time_is_recorded(tmp_path):
    out, _ = run_gen(make_raw(run={"duration_s": 1.5}), MockConfig(**FAST), tmp_path)
    _, meta = load(out)
    assert meta["outcome"]["metrics_skipped_ticks"] == 0 and meta["outcome"]["metrics_scrapes"] >= 2


# ------------------------------------------------------------------ probe: does the engine return output ids?
def _probe_summary(tmp_path, mock_cfg, capsys, **sections):
    from agentload.cli import _probe
    from agentload.mock_server import MockServer

    async def go():
        async with MockServer(mock_cfg) as srv:
            raw = make_raw(**sections)
            raw["server"]["base_url"] = srv.url
            await _probe(config_from_dict(raw))
    asyncio.run(go())
    out = capsys.readouterr().out
    line = [l for l in out.splitlines() if l.startswith("PROBE_SUMMARY ")][0]
    return out, json.loads(line[len("PROBE_SUMMARY "):])


def test_probe_asks_for_token_ids_even_when_the_config_does_not(tmp_path, capsys):
    out, s = _probe_summary(tmp_path, MockConfig(**FAST), capsys, server={"request_token_ids": False})
    assert "request 3 (return_token_ids=true): HTTP 200" in out
    assert s["return_token_ids_http"] == 200 and s["output_ids_present"] is True and s["output_ids_path"] == "choices.0.token_ids"
    assert s["request1_cached_tokens"] == 0 and s["request2_cached_tokens"] == 63 and s["request2_prompt_tokens"] == 64
    assert s["prompt_tokens_sent"] == 64 and s["metrics_http"] == 200


def test_probe_reports_engines_that_ignore_or_reject_return_token_ids(tmp_path, capsys):
    _, s = _probe_summary(tmp_path, MockConfig(token_ids_mode="ignore", **FAST), capsys)
    assert s["return_token_ids_http"] == 200 and s["output_ids_present"] is False and s["output_ids_path"] is None
    _, s = _probe_summary(tmp_path, MockConfig(token_ids_mode="reject", **FAST), capsys)
    assert s["return_token_ids_http"] == 400 and s["output_ids_present"] is False
