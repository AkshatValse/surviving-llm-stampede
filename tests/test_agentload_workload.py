import numpy as np
import pytest

from agentload.config import WorkloadCfg, config_from_dict
from agentload.workload import (WORDS, ContentGen, SessionPlan, build_open_plan, burst_times, context_len,
                                effective_mean_turns, extend_context, make_closed_session, poisson_times, prompt_len,
                                ramp_rate, ramp_times, make_rng, session_spec)
from conftest import make_raw


def wl(**kw):
    base = dict(initial_context_tokens=100, new_prompt_tokens=30, decode_tokens=6, mean_turns=15.0, max_turns=60,
                tool_time_mean_s=5.0)
    base.update(kw)
    return WorkloadCfg(**base)


def plan_for(seed, rate=0.5, dur=2000.0, burst=None, kind="constant", ramp=()):
    raw = make_raw(arrivals={"kind": kind, "rate": rate if kind == "constant" else None, "burst": burst,
                             "ramp": [list(k) for k in ramp]})
    cfg = config_from_dict(raw)
    return build_open_plan(seed, wl(), cfg.arrivals, dur, rate if kind == "constant" else None, list(ramp))


def test_plan_reproducible_per_seed_and_differs_across_seeds():
    a, b, c = plan_for(3), plan_for(3), plan_for(4)
    assert a == b
    assert [p.arrival_s for p in a] != [p.arrival_s for p in c]
    assert [p.n_turns for p in a[:30]] != [p.n_turns for p in c[:30]]


def test_arrival_count_matches_poisson_rate():
    n = [len(plan_for(s, rate=0.5, dur=2000.0)) for s in range(40)]
    mean, sd = np.mean(n), np.std(n, ddof=1) / np.sqrt(len(n))
    assert abs(mean - 1000) < 4 * max(sd, 1.0)            # E = rate * duration = 1000
    p = plan_for(0)
    t = np.array([x.arrival_s for x in p])
    assert np.all(np.diff(t) >= 0) and t.min() >= 0 and t.max() < 2000
    assert [x.sid for x in p] == list(range(len(p)))


def test_turns_geometric_capped_and_tool_times():
    w = wl()
    specs = [session_spec(1, "base", i, w) for i in range(20000)]
    t = np.array([s[0] for s in specs])
    assert t.min() == 1 and t.max() <= 60
    assert abs(t.mean() - effective_mean_turns(w)) < 4 * t.std() / np.sqrt(len(t))
    assert 14.0 < effective_mean_turns(w) < 15.0           # cap 60 shaves ~0.24 off the mean of 15
    assert all(len(s[1]) == s[0] - 1 for s in specs[:200])
    z = np.concatenate([np.array(s[1]) for s in specs[:5000] if s[1]])
    assert abs(z.mean() - 5.0) < 4 * z.std() / np.sqrt(len(z))
    assert z.min() > 0
    # per-session spec depends only on (seed, origin, idx)
    assert session_spec(1, "base", 7, w) == session_spec(1, "base", 7, w)
    assert session_spec(1, "base", 7, w) != session_spec(2, "base", 7, w)
    assert session_spec(1, "base", 7, w) != session_spec(1, "burst", 7, w)


def test_lognormal_and_const_tool_times():
    r = make_rng(0, 99)
    from agentload.workload import draw_tool_times
    z = draw_tool_times(r, 50000, "lognormal", 5.0, 1.5)
    assert abs(z.mean() - 5.0) < 0.2
    assert np.all(draw_tool_times(r, 3, "const", 2.5, 0) == 2.5)
    with pytest.raises(ValueError):
        draw_tool_times(r, 3, "weird", 1, 1)


def test_burst_timing_and_common_random_numbers():
    burst = {"n": 50, "t_s": 700.0, "width_s": 60.0}
    with_b, without = plan_for(5, burst=burst), plan_for(5)
    bs = [p for p in with_b if p.origin == "burst"]
    assert len(bs) == 50
    assert all(700.0 <= p.arrival_s < 760.0 for p in bs)
    base_with = [p for p in with_b if p.origin == "base"]
    assert [p.arrival_s for p in base_with] == [p.arrival_s for p in without]
    # base sessions keep their (origin, idx)-keyed spec even though ids are re-ranked
    by_idx = {p.idx: p for p in base_with}
    assert all((by_idx[p.idx].n_turns, by_idx[p.idx].tool_times_s) == (p.n_turns, p.tool_times_s) for p in without)
    assert [p.arrival_s for p in with_b] == sorted(p.arrival_s for p in with_b)
    assert [p.sid for p in with_b] == list(range(len(with_b)))
    # bursts are reproducible and honour zero width
    assert np.array_equal(burst_times(1, 10, 5.0, 2.0), burst_times(1, 10, 5.0, 2.0))
    assert np.all(burst_times(1, 4, 5.0, 0.0) == 5.0)


def test_ramp_rate_and_thinning_follow_the_schedule():
    knots = [(0.0, 0.0), (1000.0, 1.0), (2000.0, 0.0)]
    assert ramp_rate(np.array([-5, 0, 500, 1000, 1500, 3000]), knots).tolist() == [0, 0, 0.5, 1.0, 0.5, 0.0]
    counts = np.zeros(4)
    n_rep = 30
    for s in range(n_rep):
        t = ramp_times(make_rng(s, 0), make_rng(s, 1), knots, 2000.0)
        counts += np.histogram(t, bins=[0, 500, 1000, 1500, 2000])[0]
    expected = np.array([125, 375, 375, 125]) * n_rep       # integral of the triangle over each 500 s bin
    assert np.all(np.abs(counts - expected) < 5 * np.sqrt(expected))
    assert plan_for(0, kind="ramp", ramp=knots, dur=2000.0) == plan_for(0, kind="ramp", ramp=knots, dur=2000.0)


def test_poisson_times_edge_cases():
    r = make_rng(0, 0)
    assert len(poisson_times(r, 0.0, 0, 10)) == 0 and len(poisson_times(r, 1.0, 5, 5)) == 0


def test_closed_session_keys():
    a = make_closed_session(2, wl(), sid=0, idx=3, arrival_s=1.0)
    b = make_closed_session(2, wl(), sid=9, idx=3, arrival_s=50.0)
    assert (a.n_turns, a.tool_times_s) == (b.n_turns, b.tool_times_s) and a.origin == "closed"


def test_prompt_len_formula():
    w = wl(initial_context_tokens=2000, new_prompt_tokens=550, decode_tokens=100)
    assert [prompt_len(w, t) for t in (1, 2, 3, 60)] == [2000, 2650, 3300, 2000 + 59 * 650]


def test_content_unique_reproducible_and_independent():
    w = wl(initial_context_tokens=200)
    cg = ContentGen(7, w)
    sp = lambda i, o="base": SessionPlan(i, o, i, 0.0, 3, (1.0, 1.0))
    heads = {tuple(cg.initial(sp(i))[:16]) for i in range(300)}
    assert len(heads) == 300                              # session-specific prefixes
    a = cg.initial(sp(5))
    assert a.dtype == np.int32 and len(a) == 200
    assert a.min() >= w.token_id_low and a.max() < w.token_id_high
    assert np.array_equal(a, ContentGen(7, w).initial(sp(5)))
    assert not np.array_equal(a, ContentGen(8, w).initial(sp(5)))
    assert not np.array_equal(a, cg.initial(sp(5, "burst")))
    d2, d3 = cg.delta(sp(5), 2), cg.delta(sp(5), 3)
    assert len(d2) == 30 and not np.array_equal(d2, d3)
    assert len(cg.synthetic_output(sp(5), 2)) == 6
    assert not np.array_equal(cg.synthetic_output(sp(5), 2)[:6], d2[:6])


def test_text_mode_content():
    w = wl(prompt_mode="tokens")
    wt = WorkloadCfg(**{**w.__dict__, "prompt_mode": "text", "text_words_per_token": 1.0})
    cg = ContentGen(1, wt)
    s = SessionPlan(0, "base", 0, 0.0, 2, (1.0,))
    t0 = cg.initial(s)
    assert isinstance(t0, str) and context_len(t0) == 100 and t0.startswith(" ")
    assert context_len(extend_context(t0, cg.delta(s, 2))) == 130
    assert t0 != ContentGen(1, wt).initial(SessionPlan(1, "base", 1, 0.0, 2, (1.0,)))
    assert len(set(WORDS)) == len(WORDS) >= 200 and all(w == w.strip() and " " not in w for w in WORDS)
    wt2 = WorkloadCfg(**{**wt.__dict__, "text_words_per_token": 0.5})
    assert context_len(ContentGen(1, wt2).initial(s)) == 50
