"""Pins the engine-side LPM-INF evaluation (analysis/r11_lpminf_eval.py) on the committed pulls."""
import pytest

from analysis import r11_lpminf_eval as ev


@pytest.fixture(scope="module")
def rows():
    return ev.evaluate(ev.load_endpoints())


def _row(rows, label, seed):
    (r,) = [x for x in rows if x["label"] == label and x["seed"] == seed]
    return r


def test_frozen_constants_are_read_from_the_endpoint_file():
    ep = ev.load_endpoints()
    assert ep["primary"]["window_s"] == [5700, 8700]
    assert ep["primary"]["collapse_hit_below"] == 0.05
    assert ep["manipulation_check"]["scheduler_cost_min_s_per_s"] == 0.008


def test_all_cells_share_the_client_plan_per_seed(rows):
    for s in (0, 1, 2):
        assert len({r["plan_sha256"] for r in rows if r["seed"] == s}) == 1
    assert len(rows) == 15


def test_lpminf_rows(rows):
    exp = {0: (0.5948, "draining", "PASS"), 1: (0.4193, "indeterminate", "PASS"), 2: (0.5566, "draining", "UNINFORMATIVE")}
    for s, (hit, state, sc) in exp.items():
        r = _row(rows, "sglang-lpminf", s)
        assert r["tok_hit_W"] == pytest.approx(hit, abs=1e-4)
        assert r["collapse"] is False
        assert r["trap_v2_state"] == state
        assert r["sc_state"] == sc
        assert r["hook_ok"] and r["manipulation_verified"]
        assert r["n_lat_gt600"] == 0


def test_stock_lpm_falls_to_fcfs_scheduler_cost_above_128(rows):
    for lab in ("sglang-lpm-r1", "sglang-lpm-r0"):
        for s in (0, 1):
            r = _row(rows, lab, s)
            assert r["collapse"] is True and r["trap_v2_state"] == "trapped"
            assert r["sc_median_q_gt128"] < 0.0035


def test_decision_is_consistent(rows):
    d = ev.decision(rows, ev.load_endpoints())
    assert d["outcome"] == "consistent"
    assert d["collapse_informative_seeds"] == {0: False, 1: False}
