"""End-to-end: the generator against the in-process mock server."""
import json
import re
from collections import defaultdict

import numpy as np
import pandas as pd
import pytest
import yaml

from agentload.mock_server import MockConfig
from conftest import make_raw, run_gen


def load(out, ok_only=True):
    """(requests, sessions, plan, meta). By default only status==ok requests: requests still in flight when the run
    ends are logged as cancelled and carry no usage."""
    d = out.out_dir
    req = pd.read_csv(d / "requests.csv")
    if ok_only:
        req = req[req["status"] == "ok"].reset_index(drop=True)
    return (req, pd.read_csv(d / "sessions.csv"), pd.read_csv(d / "plan.csv"), json.loads((d / "meta.json").read_text()))


@pytest.fixture(scope="module")
def basic(tmp_path_factory):
    root = tmp_path_factory.mktemp("basic")
    raw = make_raw(arrivals={"kind": "constant", "rate": 6.0, "burst": {"n": 12, "t_s": 2.0, "width_s": 0.5}},
                   run={"duration_s": 5.0})
    out, truth = run_gen(raw, None, root)
    return out, truth, raw


def test_outputs_and_meta(basic):
    out, truth, raw = basic
    req, ses, plan, meta = load(out, ok_only=False)
    d = out.out_dir
    for f in ("requests.csv", "sessions.csv", "plan.csv", "metrics.csv", "metrics_first.txt", "metrics_last.txt",
              "meta.json", "config.yaml", "config_effective.yaml", "events.log"):
        assert (d / f).exists(), f
    assert re.fullmatch(r"\d{8}-\d{6}(-\d+)?", d.name)                     # timestamped dir
    assert meta["status"] == "finished" and meta["seeds"] == [0]
    assert meta["hardware"] == "Apple M3 Max CPU (simulation)"
    assert meta["git"]["captured_at"] == "run start" and len(meta["git"]["commit"]) == 40
    assert isinstance(meta["git"]["dirty"], bool)
    assert {"python", "numpy", "aiohttp", "pandas", "yaml"} <= set(meta["versions"])
    assert meta["hostname"] and meta["start_time"] <= meta["end_time"] and meta["wall_s"] > 4.5
    assert meta["outcome"]["abort_reason"] is None
    assert yaml.safe_load((d / "config_effective.yaml").read_text())["run"]["seed"] == 0
    assert meta["outcome"]["requests_total"] == len(req)
    assert meta["outcome"]["requests_ok"] == (req["status"] == "ok").sum()
    assert set(req["status"]) <= {"ok", "cancelled"} and (req[req["status"] == "ok"]["http_status"] == 200).all()


def test_prompts_grow_exactly_and_are_prefix_extensions(basic):
    out, truth, raw = basic
    req, *_ = load(out)
    w = raw["workload"]
    L0, D, d = w["initial_context_tokens"], w["new_prompt_tokens"], w["decode_tokens"]
    assert (req["prompt_tokens_client"] == L0 + (req["turn"] - 1) * (D + d)).all()
    assert (req["prompt_tokens"] == req["prompt_tokens_client"]).all()           # server agrees
    assert (req["completion_tokens"] == d).all()
    # with exact server-returned ids a follow-up turn hits everything but its new Delta tokens
    fu = req[req["turn"] >= 2]
    assert len(fu) > 10
    assert ((fu["prompt_tokens"] - fu["cached_tokens"]) == D).all()
    assert (req[req["turn"] == 1]["cached_tokens"] == 0).all()
    assert set(req["output_ids_source"]) == {"server_ids"}
    # prompts seen by the server: each turn extends the previous turn's prompt (+ its output)
    by_key = defaultdict(list)
    for u in truth["seen"]:
        by_key[tuple(u[:8])].append(u)
    # one unique prefix per session (the mock may have completed <= 2 requests the client cancelled at run end)
    assert 0 <= len(by_key) - len(set(req["sid"])) <= 2
    for seq in by_key.values():
        seq.sort(key=len)
        for a, b in zip(seq, seq[1:]):
            assert len(b) == len(a) + d + D
            assert np.array_equal(b[:len(a)], a)


def test_cached_tokens_match_mock_ground_truth(basic):
    out, truth, _ = basic
    req, *_ = load(out)
    # exact up to <= 2 requests that the mock completed but the client had already cancelled at run end
    slack = 2 * req["prompt_tokens"].max()
    assert 0 <= truth["stats"]["prompt_tokens"] - req["prompt_tokens"].sum() <= slack
    assert 0 <= truth["stats"]["cached_tokens"] - req["cached_tokens"].sum() <= slack
    assert 0 <= truth["stats"]["completed"] - len(req) <= 2
    assert abs(req["cached_tokens"].sum() / req["prompt_tokens"].sum()
               - truth["stats"]["cached_tokens"] / truth["stats"]["prompt_tokens"]) < 0.01


def test_burst_timing_in_the_log(basic):
    out, truth, raw = basic
    req, ses, plan, meta = load(out)
    b = plan[plan["origin"] == "burst"]
    assert len(b) == 12 and b["arrival_s"].between(2.0, 2.5, inclusive="left").all()
    first = req[(req["turn"] == 1)].merge(plan[["sid", "arrival_s"]], on="sid")
    bf = first[first["origin"] == "burst"]
    assert len(bf) == 12
    assert ((bf["t_send"] - bf["arrival_s"]) >= -1e-3).all() and ((bf["t_send"] - bf["arrival_s"]) < 0.25).all()
    assert (first["sched_delay_s"] < 0.25).all()


def test_sessions_and_planned_turns(basic):
    out, *_ = basic
    req, ses, plan, meta = load(out)
    done = ses[ses["status"] == "completed"]
    assert len(done) > 10
    # completed sessions sent exactly their planned number of turns, with increasing send times
    per = req.groupby("sid").agg(n=("turn", "size"), mx=("turn", "max"))
    m = done.merge(per, left_on="sid", right_index=True)
    assert (m["n"] == m["n_turns"]).all() and (m["mx"] == m["n_turns"]).all()
    for sid, g in req.groupby("sid"):
        g = g.sort_values("turn")
        assert (np.diff(g["t_send"]) > 0).all()
        assert (g["t_send"].iloc[1:].to_numpy() >= g["t_complete"].iloc[:-1].to_numpy()).all()   # tool time after reply


def test_metrics_log(basic):
    out, *_ = basic
    m = pd.read_csv(out.out_dir / "metrics.csv")
    names = set(m["name"])
    assert {"vllm:num_requests_waiting", "vllm:num_requests_running", "vllm:prefix_cache_hits_total",
            "agentload:inflight_requests", "agentload:scrape_ok"} <= names
    assert not any(n.endswith("_bucket") for n in names) and "python_gc_objects_collected_total" not in names
    t = np.sort(m[m["name"] == "agentload:scrape_ok"]["t_s"].to_numpy())
    assert 8 <= len(t) <= 11 and np.all(np.abs(np.diff(t) - 0.5) < 0.15)          # 0.5 s interval, no drift
    assert (m[m["name"] == "agentload:scrape_ok"]["value"] == 1.0).all()
    assert "vllm:num_requests_waiting" in (out.out_dir / "metrics_first.txt").read_text()


def test_reproducible_per_seed(tmp_path):
    raw = make_raw(run={"duration_s": 2.5})
    o1, _ = run_gen(raw, None, tmp_path / "a")
    o2, _ = run_gen(raw, None, tmp_path / "b")
    r3 = make_raw(run={"duration_s": 2.5, "seed": 1})
    o3, _ = run_gen(r3, None, tmp_path / "c")
    p1, p2, p3 = (pd.read_csv(o.out_dir / "plan.csv") for o in (o1, o2, o3))
    pd.testing.assert_frame_equal(p1, p2)
    assert not p1.equals(p3)
    q1, q2 = (pd.read_csv(o.out_dir / "requests.csv") for o in (o1, o2))
    key = lambda q: sorted(zip(q["sid"], q["turn"], q["prompt_hash"]))
    common = set(key(q1)) & set(key(q2))
    assert len(common) >= 0.9 * min(len(q1), len(q2)) > 5          # same prompts (tail may differ at the cutoff)


def test_open_loop_arrivals_do_not_wait_for_the_server(tmp_path):
    slow = MockConfig(kv_capacity_tokens=10**7, slots=1, fixed_s=0.4, per_uncached_token_s=0, per_completion_token_s=0)
    raw = make_raw(arrivals={"rate": 8.0}, run={"duration_s": 3.0}, metrics={"enabled": False})
    out, _ = run_gen(raw, slow, tmp_path)
    req, ses, plan, meta = load(out, ok_only=False)
    first = req[req["turn"] == 1]
    assert len(first) >= 15
    assert first["sched_delay_s"].max() < 0.2            # sessions start on schedule although the server is 8x overloaded
    assert req["latency_s"].max() > 1.5                  # ...and requests queue
    assert meta["outcome"]["max_inflight_seen"] > 8


def test_overload_abort_cancels_inflight_and_is_recorded(tmp_path):
    slow = MockConfig(kv_capacity_tokens=10**7, slots=1, fixed_s=0.5, per_uncached_token_s=0, per_completion_token_s=0)
    raw = make_raw(arrivals={"rate": 40.0}, run={"duration_s": 10.0, "max_inflight": 6}, metrics={"enabled": False})
    out, _ = run_gen(raw, slow, tmp_path)
    req, ses, plan, meta = load(out, ok_only=False)
    assert out.abort_reason.startswith("max_inflight") and meta["outcome"]["abort_reason"] == out.abort_reason
    assert out.t_end_s < 5.0 and meta["outcome"]["t_abort_s"] == pytest.approx(out.t_end_s, abs=0.5)
    assert (req["status"] == "cancelled").sum() >= 6
    assert (ses["status"].isin(["cancelled", "completed", "failed"])).all()
    assert req["t_complete"].notna().all()


def test_errors_are_logged_and_abort_after_max_errors(tmp_path):
    flaky = MockConfig(kv_capacity_tokens=10**7, fail_every_n=2, fixed_s=0, per_uncached_token_s=0,
                       per_completion_token_s=0)
    raw = make_raw(arrivals={"rate": 10.0}, run={"duration_s": 6.0, "max_errors": 3}, metrics={"enabled": False})
    out, _ = run_gen(raw, flaky, tmp_path)
    req, ses, _, meta = load(out, ok_only=False)
    assert out.abort_reason.startswith("max_errors")
    err = req[req["status"] == "error"]
    assert len(err) >= 3 and (err["http_status"] == 500).all() and err["error"].str.contains("injected").all()
    assert (ses[ses["status"] == "failed"].shape[0]) >= 3


def test_closed_population_is_replaced_and_bounded(tmp_path):
    raw = make_raw(arrivals={"kind": "closed", "rate": None, "closed_n": 3},
                   workload={"mean_turns": 2, "max_turns": 3, "tool_time_mean_s": 0.05}, run={"duration_s": 3.0},
                   metrics={"enabled": False})
    out, _ = run_gen(raw, None, tmp_path)
    req, ses, plan, meta = load(out)
    assert len(plan) == 0 and meta["outcome"]["sessions_started"] > 10
    assert set(ses["origin"]) == {"closed"}
    started = ses["arrival_s"].to_numpy()
    assert (started[:3] == 0.0).all() or (started[:3] < 0.1).all()
    ends = ses["t_end"].to_numpy()
    for t in np.linspace(0.1, 2.8, 25):                    # never more than closed_n live sessions
        alive = ((ses["arrival_s"] <= t) & (ends > t)).sum()
        assert alive <= 3
    for t in np.linspace(0.2, 2.8, 10):
        assert ((ses["arrival_s"] <= t) & (ends > t)).sum() >= 2      # ...and the population is kept up


def test_synthetic_output_feedback_when_server_returns_no_ids(tmp_path):
    raw = make_raw(server={"request_token_ids": False}, run={"duration_s": 2.5}, metrics={"enabled": False})
    out, _ = run_gen(raw, None, tmp_path)
    req, *_ = load(out)
    w = raw["workload"]
    fu = req[req["turn"] >= 2]
    assert set(req["output_ids_source"].dropna()) == {"synthetic"}
    # the output text differs from the synthetic ids, so a hit covers the previous PROMPT only
    assert (fu["prompt_tokens"] - fu["cached_tokens"] == w["new_prompt_tokens"] + w["decode_tokens"]).all()


def test_server_only_feedback_fails_session_without_ids(tmp_path):
    raw = make_raw(server={"request_token_ids": False}, workload={"output_feedback": "server"},
                   run={"duration_s": 2.0}, metrics={"enabled": False})
    out, _ = run_gen(raw, None, tmp_path)
    req, ses, _, _ = load(out, ok_only=False)
    assert (req["status"].isin(["error", "cancelled"])).all() and (req["status"] == "error").sum() > 3
    req = req[req["status"] == "error"]
    assert (req["status"] == "error").all() and req["error"].str.contains("no usable model output").all()


def test_text_mode_end_to_end(tmp_path):
    raw = make_raw(workload={"prompt_mode": "text"}, run={"duration_s": 2.5}, metrics={"enabled": False},
                   server={"request_token_ids": False})
    out, truth = run_gen(raw, None, tmp_path)
    req, *_ = load(out)
    w = raw["workload"]
    assert (req["prompt_tokens_client"] == w["initial_context_tokens"] + (req["turn"] - 1)
            * (w["new_prompt_tokens"] + w["decode_tokens"])).all()                  # words == tokens in the mock
    fu = req[req["turn"] >= 2]
    assert len(fu) > 5 and ((fu["prompt_tokens"] - fu["cached_tokens"]) == w["new_prompt_tokens"]).all()
    assert set(req["output_ids_source"]) == {"server_text"}


def test_cached_report_variants(tmp_path):
    for style, src in (("choice_meta", "choices.0.meta_info"), ("none", "none")):
        raw = make_raw(run={"duration_s": 1.5}, metrics={"enabled": False})
        out, _ = run_gen(raw, MockConfig(kv_capacity_tokens=10**7, cached_style=style, fixed_s=0.001,
                                         per_uncached_token_s=0, per_completion_token_s=0), tmp_path / style)
        req, *_ = load(out)
        req = req[req["status"] == "ok"]               # requests cancelled at the end carry no usage
        assert set(req["cached_source"]) == {src}
        assert req["cached_tokens"].isna().all() == (style == "none")


def test_eviction_lowers_hit_rate(tmp_path):
    raw = make_raw(arrivals={"rate": 8.0}, run={"duration_s": 5.0}, workload={"tool_time_mean_s": 0.8},
                   metrics={"enabled": False})
    big, small = MockConfig(kv_capacity_tokens=10**7), MockConfig(kv_capacity_tokens=1000)
    rates = []
    for i, mc in enumerate((big, small)):
        out, _ = run_gen(raw, mc, tmp_path / str(i))
        req, *_ = load(out)
        rates.append(req["cached_tokens"].sum() / req["prompt_tokens"].sum())
    assert rates[0] > 0.5 and rates[1] < rates[0] - 0.2


def test_preflight_failure_is_recorded(tmp_path):
    import asyncio
    from datetime import datetime
    from agentload.client import LoadGenerator
    from agentload.config import config_from_dict
    from agentload.runmeta import new_result_dir
    from conftest import REPO
    raw = make_raw(run={"duration_s": 1.0, "preflight_wait_s": 1})
    raw["server"]["base_url"] = "http://127.0.0.1:9"           # nothing listens on the discard port
    raw["output"]["root"] = str(tmp_path)
    cfg = config_from_dict(raw)
    d = new_result_dir(tmp_path, "pf")
    (d / "config.yaml").write_text("x: 1")
    (d / "config_effective.yaml").write_text(yaml.safe_dump(raw))
    gen = LoadGenerator(cfg, raw, d, REPO)
    with pytest.raises(RuntimeError, match="not healthy"):
        asyncio.run(gen.run(["pytest"], {"commit": "x", "dirty": False}, datetime.now(), []))
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "failed" and "not healthy" in meta["error"]
