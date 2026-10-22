import numpy as np
import pandas as pd
import pytest

from analysis.windows import inflight_events, n_complete_windows, pick_series, queue_trace, step_bins, window_table
from helpers_analysis import fake_run, params, req_df


def test_step_bins_exact():
    t = np.array([10.0, 20.0, 30.0, 60.0])
    v = np.array([1.0, 2.0, 1.0, 0.0])
    mean, mx = step_bins(t, v, np.array([0.0, 50.0, 100.0]))
    assert mean.tolist() == pytest.approx([50 / 50, 10 / 50])                       # 0*10 + 1*10 + 2*10 + 1*20 = 50
    assert mx.tolist() == [2.0, 1.0]                                                # 2nd bin starts at value 1
    m2, x2 = step_bins(np.zeros(0), np.zeros(0), np.array([0.0, 10.0]))
    assert m2.tolist() == [0.0] and x2.tolist() == [0.0]


def test_inflight_counts_all_statuses():
    r = req_df([dict(t_send=1, t_complete=5, status="ok"), dict(t_send=2, t_complete=3, status="error"),
                dict(t_send=2.5, t_complete=9, status="cancelled")])
    t, v = inflight_events(r)
    assert v.max() == 3 and v[-1] == 0 and np.all(np.diff(t) >= 0)


def test_n_complete_windows():
    assert n_complete_windows(250.0, 100.0) == 2 and n_complete_windows(300.0, 100.0) == 3
    assert n_complete_windows(299.9999999999, 100.0) == 3                      # float fuzz
    assert n_complete_windows(99.0, 100.0) == 0


@pytest.fixture
def known():
    # window 0: [0,100)  turns: (prompt, cached) = (1000,0) (1100,1000) (1200,1100) (1300,100)   -> 2 of 4 above 50%
    # window 1: [100,200) turns: (1000,0) x2 + (2000,2000-1) -> 1 of 3 ... (cached 1999/2000 above 50%)
    rows = [
        dict(sid=1, turn=1, n_turns=1, t_send=1, t_complete=10, prompt_tokens=1000, cached_tokens=0),
        dict(sid=2, turn=2, n_turns=3, t_send=20, t_complete=30, prompt_tokens=1100, cached_tokens=1000),
        dict(sid=3, turn=3, n_turns=3, t_send=40, t_complete=50, prompt_tokens=1200, cached_tokens=1100),
        dict(sid=4, turn=2, n_turns=5, t_send=60, t_complete=95, prompt_tokens=1300, cached_tokens=100),
        dict(sid=5, turn=1, n_turns=2, t_send=95, t_complete=105, prompt_tokens=1000, cached_tokens=0),
        dict(sid=6, turn=1, n_turns=1, t_send=110, t_complete=150, prompt_tokens=1000, cached_tokens=0),
        dict(sid=7, turn=2, n_turns=2, t_send=120, t_complete=130, prompt_tokens=2000, cached_tokens=1999),
        dict(sid=8, turn=1, n_turns=1, t_send=205, t_complete=230, prompt_tokens=1000, cached_tokens=0),   # incomplete window 2
    ]
    return fake_run(req_df(rows), t_end=250.0)


def test_window_table_known_values(known):
    p = params("windows.window_s=100", "windows.fine_window_s=50")
    w = window_table(known, p)
    assert len(w) == 2                                        # [200,250) is incomplete and excluded
    w0, w1 = w.iloc[0], w.iloc[1]
    assert w0["n_turns_ok"] == 4 and w0["turns_per_s"] == pytest.approx(0.04)
    assert w0["token_hit_rate"] == pytest.approx((0 + 1000 + 1100 + 100) / (1000 + 1100 + 1200 + 1300))
    assert w0["frac_turns_cached_gt50"] == pytest.approx(2 / 4)                   # 1000/1100 and 1100/1200 above 0.5
    assert w0["frac_turns_cached_gt50_followup"] == pytest.approx(2 / 3)          # turns >= 2 only
    assert w0["sessions_per_s"] == pytest.approx(2 / 100)                         # sids 1 and 3 finished their last turn
    assert w0["lat_p50_s"] == pytest.approx(np.percentile([9, 10, 10, 35], 50))
    assert w0["lat_p99_s"] == pytest.approx(np.percentile([9, 10, 10, 35], 99))
    assert w0["first_turn_lat_mean_s"] == pytest.approx(9.0)
    assert w1["n_turns_ok"] == 3 and w1["frac_turns_cached_gt50"] == pytest.approx(1 / 3)
    assert w1["token_hit_rate"] == pytest.approx(1999 / 4000)
    assert w1["sessions_per_s"] == pytest.approx(2 / 100)                         # sids 6 and 7
    assert (w["hit_rate"] == w["frac_turns_cached_gt50"]).all() and set(w["hit_source"]) == {"requests:frac_turns_cached_gt50"}
    pt = window_table(known, params("windows.window_s=100", "windows.hit_metric=token_hit_rate"))
    assert pt["hit_rate"].tolist() == pytest.approx(pt["token_hit_rate"].tolist())


def test_attribute_by_send_vs_complete(known):
    wc = window_table(known, params("windows.window_s=100"))
    ws = window_table(known, params("windows.window_s=100", "windows.attribute_by=send"))
    assert wc["n_turns_ok"].tolist() == [4, 3] and ws["n_turns_ok"].tolist() == [5, 2]   # sid 5 was sent at t=95


def test_threshold_is_strict_and_configurable(known):
    w = window_table(known, params("windows.window_s=100", "windows.cached_frac_threshold=0.95"))
    assert w.iloc[0]["n_cached_gt"] == 0 and w.iloc[1]["n_cached_gt"] == 1


def test_missing_cached_counts_zero_when_some_reported():
    rows = [dict(sid=1, turn=2, n_turns=3, t_send=1, t_complete=2, prompt_tokens=100, cached_tokens=90),
            dict(sid=2, turn=2, n_turns=3, t_send=1, t_complete=3, prompt_tokens=100, cached_tokens=np.nan)]
    w = window_table(fake_run(req_df(rows), 100.0), params("windows.window_s=100")).iloc[0]
    assert w["n_cached_missing_as_zero"] == 1 and w["frac_turns_cached_gt50"] == 0.5 and w["cached_available"]


def test_no_cached_reports_gives_nan_and_counter_fallback():
    rows = [dict(sid=i, turn=2, n_turns=3, t_send=1, t_complete=10 + i, prompt_tokens=100, cached_tokens=np.nan)
            for i in range(5)]
    met = pd.DataFrame([(t, n, "", v) for t, h, q in ((0, 0, 0), (50, 20, 40), (100, 60, 100), (150, 90, 150),
                                                       (200, 90, 150))
                        for n, v in (("vllm:prefix_cache_hits_total", h), ("vllm:prefix_cache_queries_total", q))],
                       columns=["t_s", "name", "labels", "value"])
    w = window_table(fake_run(req_df(rows), 200.0, metrics=met), params("windows.window_s=100"))
    assert not w["cached_available"].any() and w["token_hit_rate"].isna().all() and w["frac_turns_cached_gt50"].isna().all()
    assert set(w["hit_source"]) == {"engine_counters"}
    assert w["engine_counter_hit_rate"].tolist() == pytest.approx([60 / 100, 30 / 50])   # deltas over [0,100], [100,200]
    assert w["hit_rate"].tolist() == pytest.approx(w["engine_counter_hit_rate"].tolist())


def test_queue_from_engine_metrics_sums_label_sets_and_falls_back_to_client():
    reqs = req_df([dict(sid=1, turn=1, n_turns=1, t_send=10, t_complete=60, prompt_tokens=10, cached_tokens=0)])
    rows = []
    for t in range(0, 200, 5):
        w = 4.0 if t < 100 else 40.0
        rows += [(t, "vllm:num_requests_waiting", '{engine="0"}', w), (t, "vllm:num_requests_waiting", '{engine="1"}', 1.0)]
    run = fake_run(reqs, 200.0, metrics=pd.DataFrame(rows, columns=["t_s", "name", "labels", "value"]))
    p = params("windows.window_s=100", "windows.fine_window_s=50")
    w = window_table(run, p)
    assert w["queue_source"].tolist() == ["engine_waiting"] * 2
    assert w["queue_mean"].tolist() == pytest.approx([5.0, 41.0]) and w["queue_max"].tolist() == [5.0, 41.0]
    assert w["inflight_mean"].iloc[0] == pytest.approx(50 / 100)             # one request in flight for 50 s
    tr = queue_trace(run, p)
    assert tr["source"].iloc[0] == "engine_waiting" and tr["queue_mean"].tolist() == pytest.approx([5, 5, 41, 41])
    nometrics = fake_run(reqs, 200.0)
    assert set(window_table(nometrics, p)["queue_source"]) == {"client_inflight"}
    assert queue_trace(nometrics, p)["queue_mean"].iloc[0] == pytest.approx(40 / 50)


def test_pick_series_priority_and_agg():
    m = pd.DataFrame([(0, "sglang:num_queue_reqs", "", 7.0), (0, "vllm:num_requests_waiting", "", 3.0)],
                     columns=["t_s", "name", "labels", "value"])
    name, s = pick_series(m, params().role("waiting"))
    assert name == "vllm:num_requests_waiting" and s["value"].tolist() == [3.0]            # first candidate present wins
    name, s = pick_series(pd.DataFrame(columns=["t_s", "name", "labels", "value"]), params().role("waiting"))
    assert name is None and len(s) == 0
