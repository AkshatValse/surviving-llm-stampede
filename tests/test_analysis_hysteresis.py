import numpy as np
import pandas as pd
import pytest

from analysis.hysteresis import (agg_hit, burst_verdict, hysteresis_area, kill_table, kill_verdict, lambda_cap_bracket,
                                 lambda_miss_closed, longest_run_below, ramp_lam_at, ramp_transitions, select_windows, stable_verdict,
                                 trend_rise)
from helpers_analysis import fake_run, mk_win, params, req_df

NAN = float("nan")
TB = 4000.0


def verdict(hits, queues, *, t_end=None, aborted=False, p=None, tb=TB):
    win = mk_win(hits, queues)
    run = fake_run(req_df([dict(sid=1, turn=1, n_turns=1, t_send=1, t_complete=2, prompt_tokens=1)]),
                   t_end if t_end is not None else 1000.0 * len(hits), aborted=aborted, burst_t=tb, rate_mult=1.6)
    return burst_verdict(run, win, p or params())


def test_longest_run_below_matches_simulator_semantics():
    assert longest_run_below([0.9, 0.1, 0.1, 0.5, 0.1], 0.2) == 2
    assert longest_run_below([0.1, NAN, 0.1, 0.1], 0.2) == 2                 # NaN breaks a run
    assert longest_run_below([0.2, 0.2], 0.2) == 0                           # strictly below
    assert longest_run_below([], 0.2) == 0


def test_trapped_after_good_start():
    v = verdict([0.93] * 4 + [0.05] * 20, [2] * 4 + [500] * 20)            # burst at 4000 s; 20 windows low
    assert v["trapped"] and v["trap_run_s"] == 20000 and v["good_before"] and v["hysteresis_run"]
    assert not v["recovered"] and v["verdict"] == "trapped" and v["is_trap"]
    assert v["hit_eval"] == pytest.approx(0.05) and v["n_eval_windows"] == 10         # [14000, 24000]
    assert v["pre_hit"] == pytest.approx(0.93) and v["pre_queue_mean"] == pytest.approx(2.0)


def test_tail_queue_slope_flags_a_draining_queue():
    short = params("burst.trap_min_s=3000")
    drain = verdict([0.93] * 4 + [0.05] * 8, [2] * 4 + [900, 800, 700, 600, 500, 400, 300, 200], p=short)
    grow = verdict([0.93] * 4 + [0.05] * 8, [2] * 4 + [100, 200, 300, 400, 500, 600, 700, 800], p=short)
    assert drain["trapped"] and grow["trapped"]                       # both look trapped to the hit-rate rule
    assert drain["tail_queue_slope_per_window"] == pytest.approx(-100.0)
    assert grow["tail_queue_slope_per_window"] == pytest.approx(100.0)


def test_recovery_after_transient():
    v = verdict([0.93] * 4 + [0.05, 0.1, 0.15] + [0.92] * 17, [2] * 4 + [300, 200, 100] + [3] * 17)
    assert not v["trapped"] and v["trap_run_s"] == 3000
    assert v["recovered"] and v["hit_returned"] and v["queue_returned"] and v["verdict"] == "recovered"
    assert not v["hysteresis_run"] and not v["is_trap"]


def test_slow_partial_state_is_indeterminate_not_trapped():
    v = verdict([0.93] * 4 + [0.5] * 20, [2] * 4 + [60] * 20)
    assert v["verdict"] == "indeterminate" and not v["trapped"] and not v["recovered"]


def test_hit_returns_but_queue_does_not():
    v = verdict([0.93] * 4 + [0.9] * 20, [2] * 4 + [60] * 20)
    assert v["hit_returned"] and not v["queue_returned"] and not v["recovered"]


def test_short_protocol_override_changes_trap_duration_only():
    hits, qs = [0.93] * 4 + [0.05] * 4, [2] * 4 + [400] * 4
    assert not verdict(hits, qs)["trapped"]                                          # 4000 s < simulator's 10000 s
    short = verdict(hits, qs, p=params("burst.trap_min_s=3000", "burst.hit_eval_from_s=2000"))
    assert short["trapped"] and short["verdict"] == "trapped" and short["hit_eval"] == pytest.approx(0.05)


def test_trap_without_good_start_is_not_hysteresis():
    v = verdict([0.1] * 4 + [0.05] * 20, [80] * 4 + [500] * 20)
    assert v["trapped"] and not v["good_before"] and not v["hysteresis_run"] and v["is_trap"]


def test_aborted_run_counts_as_trapped_when_last_windows_low():
    hits = [0.93] * 4 + [0.05] * 5                                    # run aborted after 5 low post-burst windows
    v = verdict(hits, [2] * 4 + [900] * 5, aborted=True)
    assert not v["trapped"] and v["trapped_aborted"] and v["verdict"] == "trapped_aborted" and v["is_trap"]
    assert v["hysteresis_run"]
    ok = verdict([0.93] * 4 + [0.05, 0.05, 0.6, 0.7, 0.8], [2] * 9, aborted=True)   # last windows are not low
    assert not ok["trapped_aborted"]
    na = verdict(hits, [2] * 4 + [900] * 5, aborted=False)
    assert not na["trapped_aborted"] and na["verdict"] == "indeterminate"


def test_burst_never_happened():
    v = verdict([0.9, 0.9], [1, 1], tb=5000.0)
    assert v["verdict"] == "no_burst"


def test_agg_hit_is_turn_weighted_and_token_weighted():
    w = mk_win([0.9, 0.1], [0, 0])
    w.loc[0, "n_turns_ok"], w.loc[0, "n_cached_gt"] = 1000, 900
    assert agg_hit(w) == pytest.approx((900 + 10) / (1000 + 100))
    wt = w.copy()
    wt["hit_source"] = "requests:token_hit_rate"
    wt["prompt_tokens"], wt["cached_tokens"] = [100.0, 300.0], [90.0, 30.0]
    assert agg_hit(wt) == pytest.approx(120 / 400)
    assert np.isnan(agg_hit(w.iloc[0:0]))
    assert len(select_windows(mk_win([0.5] * 5, [0] * 5), 1000, 4000)) == 3          # windows [1,2),[2,3),[3,4) s*1000


def _cell_rows(label, mult, flags):
    return [dict(label=label, seed=i, rate_mult=mult, is_trap=f[0], good_before=f[1], hysteresis_run=f[0] and f[1],
                 recovered=not f[0], aborted=False) for i, f in enumerate(flags)]


def test_kill_criterion_two_of_three_in_open_interval():
    T, F = (True, True), (False, True)
    rows = (_cell_rows("sglang-fcfs-r1", 1.3, [F, F, F]) + _cell_rows("sglang-fcfs-r1", 1.6, [T, T, F])
            + _cell_rows("sglang-lpm-r1", 1.6, [T, T, T]) + _cell_rows("sglang-fcfs-r1", 2.0, [T, T, T]))
    p = params()
    tab = kill_table(pd.DataFrame(rows), p.kill["trapped_fraction_min"], p.kill["min_runs_per_cell"])
    kv = kill_verdict(tab, p)
    assert kv["cells"]["sglang-fcfs-r1"]["strict_meets_at"] == [1.6]              # 2/3 at 1.6; 2.0 is outside (1.2, 2)
    assert 2.0 not in kv["cells"]["sglang-fcfs-r1"]["rate_mults_tested_in_interval"]
    assert "sglang-lpm-r1" not in kv["cells"]                                      # not an FCFS cell
    assert kv["mechanism_transfers_any_fcfs_cell_strict"] and kv["kill_strict"] is False


def test_kill_criterion_fires_when_no_fcfs_cell_traps_enough():
    T, F = (True, True), (False, True)
    rows = (_cell_rows("sglang-fcfs-r1", 1.3, [F, F, T]) + _cell_rows("sglang-fcfs-r1", 1.6, [T, F, F])
            + _cell_rows("vllm-fcfs", 1.6, [F, F, F]))
    p = params()
    kv = kill_verdict(kill_table(pd.DataFrame(rows), p.kill["trapped_fraction_min"], p.kill["min_runs_per_cell"]), p)
    assert kv["kill_strict"] is True and kv["kill_loose"] is True and kv["n_fcfs_cells_with_data"] == 2
    assert kill_verdict(kill_table(pd.DataFrame(_cell_rows("sglang-lpm-r1", 1.6, [T, T, T])),
                                   0.66, 3), p)["kill_strict"] is None            # no FCFS data: undecided, not killed


def test_kill_strict_vs_loose_and_min_runs():
    bad_start = (True, False)                                                       # trapped but pre-burst state was bad
    p = params()
    tab = kill_table(pd.DataFrame(_cell_rows("sglang-fcfs-r1", 1.6, [bad_start] * 3)), 2 / 3, 3)
    kv = kill_verdict(tab, p)
    assert kv["kill_strict"] is True and kv["kill_loose"] is False
    tab2 = kill_table(pd.DataFrame(_cell_rows("sglang-fcfs-r1", 1.6, [(True, True)] * 2)), 2 / 3, 3)
    assert kill_verdict(tab2, p)["kill_strict"] is True                             # only 2 runs < min_runs_per_cell


def trace(vals, B=100.0):
    return pd.DataFrame({"t_start": np.arange(len(vals)) * B, "queue_mean": vals, "queue_max": vals, "source": "x"})


def test_trend_rise_and_stable_verdict():
    p = params()
    n = 100                                                                         # 10000 s run, 100 s bins
    flat = trace(np.full(n, 3.0))
    ramp = trace(np.arange(n) * 0.02 * 100)                                         # +2 queue per 100 s -> rise 100 over 5000 s
    assert trend_rise(ramp, 5000, 10000) == pytest.approx(100.0, rel=1e-6)
    assert trend_rise(flat, 5000, 10000) == pytest.approx(0.0, abs=1e-9)
    assert np.isnan(trend_rise(flat, 9900, 10000))
    base = fake_run(req_df([dict(sid=1, turn=1, n_turns=1, t_send=1, t_complete=2, prompt_tokens=1)]), 10000.0)
    assert stable_verdict(base, flat, p)["stable"]
    assert not stable_verdict(base, ramp, p)["stable"]
    high = trace(np.full(n, 80.0))
    assert not stable_verdict(base, high, p)["stable"]                             # final queue >= 50
    ab = fake_run(base.requests, 10000.0, aborted=True)
    assert not stable_verdict(ab, flat, p)["stable"]


def test_ramp_transitions_and_hysteresis_area():
    q = np.concatenate([np.full(10, 2.0), np.full(5, 300.0), np.full(3, 15.0), np.full(10, 2.0)])
    lam_at = lambda t: t / 1000.0
    r = ramp_transitions(trace(q), lam_at, 128, 20, 5, 100.0, 1000.0)
    assert r["escaped"] and r["escape_time_s"] == 1050.0 and r["escape_leg"] == "down"       # 1000.0 is the leg boundary
    assert r["escape_lambda"] == pytest.approx(1.05)
    assert r["reentered"] and r["reentry_time_s"] == 1500.0                      # 3 bins at 15 then 2s: 5 consecutive below 20
    assert not ramp_transitions(trace(np.full(20, 3.0)), lam_at, 128, 20, 5, 100.0, 1000.0)["escaped"]
    never = ramp_transitions(trace(np.concatenate([np.full(5, 200.0), np.full(3, 2.0)])), lam_at, 128, 20, 5, 100.0, 1000.0)
    assert never["escaped"] and not never["reentered"]
    lam = np.linspace(0, 1, 11)
    assert hysteresis_area(np.zeros(11), np.full(11, 0.5), lam, lam, 0.0, 1.0) == pytest.approx(0.5)
    assert hysteresis_area(lam, lam[::-1][::-1], lam, lam, 0.0, 1.0) == pytest.approx(0.0)


def test_ramp_lam_at_from_config():
    run = fake_run(req_df([dict(sid=1, turn=1, n_turns=1, t_send=1, t_complete=2, prompt_tokens=1)]), 10.0,
                   cfg_extra={"arrivals": {"kind": "ramp", "ramp": [[0, 1.0], [100, 3.0]], "ramp_is_mult": True,
                                           "lambda_ref": 0.05, "rate": None}})
    f = ramp_lam_at(run)
    assert f(0) == pytest.approx(0.05) and f(50) == pytest.approx(0.1) and f(500) == pytest.approx(0.15)


def test_lambda_miss_closed_counts_post_warmup_completions():
    rows = []
    # 4 sessions, a turn completes every 5 s from t=5.. (160 turns in [200, 1000)), every 8th turn ends a session
    for i, tc in enumerate(np.arange(5.0, 1000.0, 5.0)):
        last = (i % 8 == 7)
        rows.append(dict(sid=i, turn=3 if last else 2, n_turns=3, t_send=tc - 2, t_complete=tc, prompt_tokens=10))
    run = fake_run(req_df(rows), 1000.0, cfg_extra={"arrivals": {"kind": "closed", "rate": None, "closed_n": 4,
                                                                  "burst": None}})
    r = lambda_miss_closed(run, 200.0)
    assert r["measure_s"] == 800.0 and r["turns_completed"] == 160
    assert r["turns_per_s"] == pytest.approx(0.2)
    assert r["sessions_completed"] == 20 and r["lambda_miss_sessions"] == pytest.approx(20 / 800)
    from agentload.workload import effective_mean_turns
    from agentload.config import config_from_dict
    et = effective_mean_turns(config_from_dict(run.cfg).workload)
    assert r["lambda_miss_turns_based"] == pytest.approx(0.2 / et) and r["closed_n"] == 4
    with pytest.raises(ValueError):
        lambda_miss_closed(run, 1000.0)


def test_lambda_cap_bracket():
    t = lambda rows: pd.DataFrame(rows, columns=["rate_mult", "n_stable", "n_runs"])
    b = lambda_cap_bracket(t([(1.0, 3, 3), (1.5, 3, 3), (2.0, 2, 3), (2.5, 0, 3)]))
    assert b == {"largest_all_stable_mult": 1.5, "first_unstable_mult_above": 2.0, "monotone": True, "n_rates": 4}
    assert lambda_cap_bracket(t([(1.0, 3, 3), (2.0, 3, 3)]))["first_unstable_mult_above"] is None
    none_stable = lambda_cap_bracket(t([(1.0, 0, 1), (2.0, 0, 1)]))
    assert none_stable["largest_all_stable_mult"] is None and none_stable["first_unstable_mult_above"] == 1.0
    nm = lambda_cap_bracket(t([(1.0, 3, 3), (1.5, 0, 3), (2.0, 3, 3)]))          # stable above an unstable rate
    assert nm["monotone"] is False and nm["largest_all_stable_mult"] == 2.0
