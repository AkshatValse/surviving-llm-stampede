"""Tests for scripts/traces (agent-trace parsers and statistics) on small synthetic fixtures with known answers.

The parsers are run as the real thing is (python -I SCRIPT DATA OUT) so the isolated-mode import path is exercised too.
"""
from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "traces"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "src"))

from common import (fit_lognormal, fit_lognormal_mixture, geometric_mean_param, ks_distance, quantile_table,  # noqa: E402
                    tool_class)


def run_script(name: str, *args) -> None:
    r = subprocess.run([sys.executable, "-I", str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr


def read_csv(p: Path) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------------------------------------ common.py
def test_geometric_match_inverts_effective_mean_turns():
    from prefixmeta.workload import WorkloadParams
    for m, M in [(15.0, 60), (10.0, 60), (30.0, 100)]:
        wl = WorkloadParams(2000, 550, 100, m, M, 5.0, "exp", 1.0)
        got = geometric_mean_param(wl.effective_mean_turns(), M)
        assert got == pytest.approx(m, rel=1e-6)


def test_ks_distance_known_values():
    # a single atom at 1 against a uniform(0,2) CDF: F_n jumps 0 -> 1 at x=1 where F = 0.5, so D = 0.5
    assert ks_distance([1.0, 1.0, 1.0], lambda v: np.clip(v / 2.0, 0, 1)) == pytest.approx(0.5)
    # a sample that is exactly the quantile grid of the CDF has D = 1/(2n)
    n = 100
    x = (np.arange(n) + 0.5) / n
    assert ks_distance(x, lambda v: np.clip(v, 0, 1)) == pytest.approx(0.5 / n)


def test_lognormal_fit_recovers_parameters():
    x = np.random.default_rng(1).lognormal(mean=0.7, sigma=1.3, size=200_000)
    f = fit_lognormal(x, floor=1e-6)
    assert f["mu"] == pytest.approx(0.7, abs=0.02)
    assert f["sigma"] == pytest.approx(1.3, abs=0.02)
    assert f["ks"] < 0.01
    assert f["mean_implied"] == pytest.approx(np.exp(0.7 + 1.3 ** 2 / 2), rel=0.02)
    mp = f["mean_preserving"]                                  # keeps the sample mean; for lognormal data the KS-optimal CV is the true one
    assert mp["mean"] == pytest.approx(x.mean(), rel=1e-9)
    assert mp["cv"] == pytest.approx(np.sqrt(np.expm1(1.3 ** 2)), rel=0.2) and mp["ks"] < 0.02


def test_mixture_fit_recovers_two_components_and_beats_single_lognormal():
    rng = np.random.default_rng(2)
    n = 200_000
    comp = rng.random(n) < 0.4
    x = np.where(comp, rng.lognormal(np.log(0.1), 0.5, n), rng.lognormal(np.log(8.0), 1.0, n))
    m = fit_lognormal_mixture(x, floor=1e-6, seed=0)
    c1, c2 = m["components"]
    assert c1["weight"] == pytest.approx(0.4, abs=0.02)
    assert c1["median_s"] == pytest.approx(0.1, rel=0.05)
    assert c2["median_s"] == pytest.approx(8.0, rel=0.05)
    assert c2["sigma"] == pytest.approx(1.0, abs=0.05)
    assert m["ks"] < 0.01 < fit_lognormal(x, floor=1e-6)["ks"]


def test_quantile_table_and_tool_class():
    assert quantile_table(np.arange(1, 101, dtype=float))[:3] == pytest.approx([1.99, 2.98, 3.97])
    assert len(quantile_table(np.arange(1000.0))) == 99
    assert tool_class("Bash") == "shell" and tool_class("exec_command") == "shell"
    assert tool_class("AskUserQuestion") == "human" and tool_class("Agent") == "deleg"
    assert tool_class("write_stdin") == "poll" and tool_class("custom_tool_7") == "other"


# ------------------------------------------------------------------------------------------------ parse_tracelab.py
def _rec(session, ri, inp, out, events, tools, first_in, prefix=0):
    return {"provider": "claude", "project": "p", "session_id": session, "round_index": ri, "round_id": f"r{ri}", "model": "m",
            "input_tokens_total": inp, "prefix_tokens": prefix, "newly_append_tokens": inp - prefix, "output_tokens": out,
            "timing_events": events, "tools": tools, "first_input_event_type": first_in, "user": "u", "store": ".claude"}


def _tool(name, emit, res, wall, internal=None):
    return {"tool_name": name, "tool_call_id": name + emit, "emitted_at": emit, "result_at": res, "tool_wall_latency_ms": wall,
            "tool_internal_latency_ms": internal, "is_error": False, "input_chars": 10, "result_chars": 100}


def test_parse_tracelab_synthetic(tmp_path):
    ev = lambda t, ts: {"event_type": t, "timestamp": ts, "source": "x"}   # noqa: E731
    recs = [
        _rec("S", 0, 1000, 50, [ev("user_message", "2026-01-01T00:00:00.000Z"), ev("text", "2026-01-01T00:00:01.000Z"),
                                 ev("tool_call", "2026-01-01T00:00:02.000Z"), ev("tool_call", "2026-01-01T00:00:02.200Z")],
             [_tool("Read", "2026-01-01T00:00:02.000Z", "2026-01-01T00:00:02.500Z", 500),
              _tool("Bash", "2026-01-01T00:00:02.200Z", "2026-01-01T00:00:05.200Z", 3000, internal=2900)], "user_message"),
        _rec("S", 1, 1350, 80, [ev("tool_result", "2026-01-01T00:00:02.500Z"), ev("tool_result", "2026-01-01T00:00:05.200Z"),
                                 ev("tool_call", "2026-01-01T00:00:08.000Z")],
             [_tool("Bash", "2026-01-01T00:00:08.000Z", "2026-01-01T00:00:09.000Z", 1000)], "tool_result"),
        _rec("S", 2, 1630, 20, [ev("tool_result", "2026-01-01T00:00:09.000Z"), ev("text", "2026-01-01T00:00:10.000Z")], [], "tool_result"),
        _rec("S", 3, 1700, 30, [ev("user_message", "2026-01-01T00:01:50.000Z"), ev("text", "2026-01-01T00:01:51.000Z")], [], "user_message"),
    ]
    p = tmp_path / "t.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    out = tmp_path / "norm"
    run_script("parse_tracelab.py", p, out)
    calls, rounds, eps, sess = (read_csv(out / f"{n}.csv") for n in ("calls", "rounds", "episodes", "sessions"))
    assert [c["tool"] for c in calls] == ["Read", "Bash", "Bash"]
    assert [float(c["wall_s"]) for c in calls] == [0.5, 3.0, 1.0]
    assert [c["internal_s"] for c in calls] == ["", "2.9", ""] and [float(c["best_s"]) for c in calls] == [0.5, 2.9, 1.0]
    r0, r1 = rounds[0], rounds[1]
    assert float(r0["z_round_s"]) == pytest.approx(3.0)          # last result (5.2) - last request (2.2), parallel calls
    assert int(r0["delta_ctx"]) == 300                           # 1350 - 1000 - 50
    assert int(r1["delta_ctx"]) == 1630 - 1350 - 80
    assert rounds[2]["delta_ctx"] == "" and rounds[2]["n_tools"] == "0"      # last round of the episode has no successor
    assert [(e["episode"], e["n_rounds"], e["n_tool_rounds"]) for e in eps] == [("0", "3", "2"), ("1", "1", "0")]
    assert float(eps[1]["human_gap_before_s"]) == pytest.approx(110.0 - 10.0)   # 00:01:50 minus the end of episode 0 (00:00:10)
    assert sess[0]["n_rounds"] == "4" and sess[0]["n_episodes"] == "2" and sess[0]["first_input_total"] == "1000"


# ------------------------------------------------------------------------------------------------ parse_mini_swe.py
def _chat_assistant(ts, inp, out, ncmd):
    return {"role": "assistant", "content": "x", "extra": {"actions": [{"command": "c"}] * ncmd, "timestamp": ts,
                                                           "response": {"usage": {"prompt_tokens": inp, "completion_tokens": out,
                                                                                  "prompt_tokens_details": {"cached_tokens": 0}}}}}


def _tool_msg(ts, rc=0, exc=None):
    ex = {"raw_output": "abc", "returncode": rc, "timestamp": ts, "exception_info": ""}
    if exc:
        ex["exception_type"] = exc
    return {"role": "tool", "content": "o", "extra": ex, "tool_call_id": "t"}


def test_parse_mini_swe_synthetic_chat_and_responses_formats(tmp_path):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
            _chat_assistant(100.0, 1000, 50, 1), _tool_msg(100.4),
            _chat_assistant(103.0, 1500, 60, 1), _tool_msg(163.0, rc=-1, exc="TimeoutExpired"),
            _chat_assistant(165.0, 1700, 70, 2), _tool_msg(166.5), _tool_msg(166.5),
            _chat_assistant(170.0, 1900, 40, 1), {"role": "exit", "content": "", "extra": {"exit_status": "Submitted"}}]
    # the same trajectory in OpenAI Responses-API layout (no role keys)
    resp = []
    for m in msgs:
        if m["role"] == "assistant":
            u = m["extra"]["response"]["usage"]
            resp.append({"object": "response", "usage": {"input_tokens": u["prompt_tokens"], "output_tokens": u["completion_tokens"],
                                                         "input_tokens_details": {"cached_tokens": 0}},
                         "extra": {"actions": m["extra"]["actions"], "timestamp": m["extra"]["timestamp"]}})
        elif m["role"] == "tool":
            resp.append({"type": "function_call_output", "call_id": "c", "output": "o", "extra": m["extra"]})
        else:
            resp.append(m)
    for run, mm in (("20260217_mini-v2.0.0_chatmodel", msgs), ("20260217_mini-v2.0.0_respmodel", resp)):
        d = tmp_path / "raw" / run
        d.mkdir(parents=True)
        (d / "inst__1.traj.json").write_text(json.dumps({"info": {"exit_status": "Submitted"}, "messages": mm,
                                                          "trajectory_format": "mini-swe-agent-1.1", "instance_id": "inst__1"}), encoding="utf-8")
    out = tmp_path / "norm"
    run_script("parse_mini_swe.py", tmp_path / "raw", out)
    calls, rounds, eps = (read_csv(out / f"{n}.csv") for n in ("calls", "rounds", "episodes"))
    assert len(calls) == 6 and len(eps) == 2
    for model in ("chatmodel", "respmodel"):
        cs = [c for c in calls if c["model"] == model]
        assert [float(c["wall_s"]) for c in cs] == pytest.approx([0.4, 60.0, 1.5])
        assert [c["censored"] for c in cs] == ["0", "1", "0"] and [c["n_parallel"] for c in cs] == ["1", "1", "2"]
        rs = [r for r in rounds if r["model"] == model]
        assert [int(r["input_total"]) for r in rs] == [1000, 1500, 1700, 1900]
        assert [r["delta_ctx"] for r in rs] == ["450", "140", "130", ""]            # 1500-1000-50, 1700-1500-60, 1900-1700-70
        assert [float(r["llm_s"]) for r in rs[1:]] == pytest.approx([2.6, 2.0, 3.5])  # 103.0-100.4, 165.0-163.0, 170.0-166.5
        e = [x for x in eps if x["session"].startswith(model)][0]
        assert (e["n_rounds"], e["n_tool_rounds"], e["n_timeouts"], e["exit_status"]) == ("4", "3", "1", "Submitted")
