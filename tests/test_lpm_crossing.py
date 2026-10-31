"""analysis/lpm_crossing.py: the post hoc LPM-128 crossing analysis (r11, plan item L1 step 1).

The data tests read the two committed pulls (24 BURST runs, about 1.1 GB of metrics.csv; about 5 s on the PC) and check:
- that the ported queue table reproduces the r11 lpm scout's scratch output queue_vs_128.csv byte for byte (embedded below
  as SCOUT_CSV, sha256 69a64820..., written by scratchpad design/scope_lpm/queue_vs_128.py on 2026-10-30);
- the crossing facts the notes and the plan quote (five sustained crossings, all collapsed; seven runs under 128, none
  collapsed; Fisher p = 1/792; the 1.35 x seed 0 pair; the scheduler-cost drop at the crossing).
"""
from __future__ import annotations

import csv
import hashlib
import io
import math

import pytest

from analysis import lpm_crossing as L

# The scout's queue_vs_128.csv (CRLF in the original; LF here, restored before hashing).
SCOUT_CSV = """\
src,run,label,seed,mult,state,q_max,t_peak,t_first_gt128,frac_post_gt128,t_below128_60s,q_eval_mean,tok_hit_eval,gnb_s_per_s_q_le128,gnb_s_per_s_q_gt128,tok_hit_every600s_from900
grid,20261025-034335,sglang-fcfs-r0,0,1.35,trapped,259.0,8555,3075,0.714,,202.8,0.0,0.0032,0.0028,0.15 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-074824,sglang-fcfs-r0,1,1.35,indeterminate,205.0,8150,2640,0.725,,175.1,0.0,0.0032,0.0027,0.12 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-101012,sglang-fcfs-r0,2,1.35,trapped,246.0,8395,2455,0.813,,196.2,0.0,0.0033,0.0028,0.14 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-054815,sglang-fcfs-r0,0,1.65,trapped,342.0,8675,1665,0.91,,294.1,0.0,0.0036,0.0029,0.15 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-082227,sglang-fcfs-r0,1,1.65,trapped,298.0,8660,1660,0.885,,249.0,0.0,0.0036,0.0029,0.12 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-104710,sglang-fcfs-r0,2,1.65,trapped,336.0,8560,1415,0.871,,275.2,0.0,0.0034,0.0031,0.14 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261024-153951,sglang-fcfs-r1,0,1.35,trapped,250.0,8570,3035,0.715,,200.9,0.0,0.0031,0.0027,0.14 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261024-161333,sglang-fcfs-r1,1,1.35,indeterminate,193.0,8170,3000,0.719,,169.3,0.0,0.0031,0.0028,0.13 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261024-211100,sglang-fcfs-r1,2,1.35,trapped,240.0,8450,2510,0.805,,194.8,0.0,0.0032,0.0028,0.13 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261024-155120,sglang-fcfs-r1,0,1.65,trapped,356.0,8600,1670,0.909,,302.3,0.0,0.0038,0.0031,0.16 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261024-184132,sglang-fcfs-r1,1,1.65,trapped,299.0,8540,1650,0.884,,249.4,0.0,0.0035,0.0029,0.11 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
e2,20261025-000043,sglang-fcfs-r1,2,1.65,trapped,338.0,8625,1415,0.885,,276.8,0.0,0.0032,0.0027,0.14 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-054345,sglang-lpm-r0,0,1.35,trapped,244.0,8515,3410,0.679,,193.3,0.0,0.0125,0.003,0.24 0.11 0.16 0.21 0.04 0.01 0.01 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-081740,sglang-lpm-r0,1,1.35,recovered,118.0,1740,,0.0,1740,11.7,0.799,0.01,nan,0.28 0.20 0.25 0.33 0.30 0.47 0.49 0.58 0.60 0.61 0.95 0.95 0.93
grid,20261025-104238,sglang-lpm-r0,2,1.35,recovered,116.0,1460,,0.0,1460,0.0,0.936,0.0093,nan,0.37 0.36 0.53 0.59 0.61 0.82 0.95 0.92 0.95 0.93 0.94 0.92 0.95
grid,20261025-074047,sglang-lpm-r0,0,1.65,trapped,345.0,8540,2360,0.769,,285.7,0.0,0.0123,0.0028,0.33 0.30 0.33 0.02 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-090204,sglang-lpm-r0,1,1.65,trapped,287.0,8650,2350,0.787,,237.9,0.0,0.0125,0.0029,0.23 0.18 0.13 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-112253,sglang-lpm-r0,2,1.65,recovered,121.0,1395,,0.0,1395,1.8,0.826,0.0084,nan,0.43 0.49 0.61 0.60 0.57 0.60 0.60 0.47 0.60 0.93 0.94 0.94 0.94
grid,20261025-051901,sglang-lpm-r1,0,1.35,recovered,126.0,3865,,0.0,3865,26.0,0.712,0.0094,nan,0.26 0.18 0.22 0.28 0.38 0.48 0.58 0.61 0.60 0.58 0.57 0.95 0.94
grid,20261025-081311,sglang-lpm-r1,1,1.35,recovered,117.0,1760,,0.0,1760,9.1,0.814,0.0096,nan,0.25 0.20 0.26 0.39 0.42 0.45 0.49 0.61 0.57 0.73 0.95 0.95 0.93
grid,20261025-101756,sglang-lpm-r1,2,1.35,draining,133.0,2820,2815,0.005,2840,66.1,0.5,0.0102,0.0077,0.28 0.20 0.20 0.26 0.26 0.34 0.37 0.37 0.43 0.46 0.49 0.59 0.60
grid,20261025-061332,sglang-lpm-r1,0,1.65,trapped,334.0,8605,2525,0.787,,278.5,0.0,0.0129,0.003,0.30 0.26 0.33 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-084258,sglang-lpm-r1,1,1.65,trapped,290.0,8570,1865,0.825,,240.7,0.0,0.0129,0.0031,0.20 0.10 0.13 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
grid,20261025-105152,sglang-lpm-r1,2,1.65,indeterminate,122.0,1465,,0.0,1465,73.5,0.442,0.0097,nan,0.36 0.47 0.49 0.47 0.44 0.43 0.43 0.53 0.42 0.48 0.44 0.44 0.44
"""
SCOUT_SHA256 = "69a64820fef9d06abb884710dc043e1b887c2cd2e557ed3458cad054cf1d1c04"

HAVE_DATA = all((L.ROOT / pull).is_dir() for _, pull in L.SOURCES)


# --------------------------------------------------------------------------- primitives (no data)
def _q(vals, t0=1200.0, dt=5.0):
    return [(t0 + i * dt, float(v)) for i, v in enumerate(vals)]


def test_sustained_crossing_needs_sixty_consecutive_samples_strictly_above_128():
    assert L.sustained_crossing(_q([129] * 59 + [128] + [129] * 59)) is None
    assert L.sustained_crossing(_q([100] * 10 + [129] * 60)) == 1200.0 + 50.0
    assert L.sustained_crossing(_q([128] * 100)) is None          # the engine's test is strictly > 128
    # samples before the burst do not count
    pre = [(float(t), 200.0) for t in range(0, 1200, 5)]
    assert L.sustained_crossing(pre + _q([0] * 10)) is None


def test_longest_above_counts_only_post_burst_runs():
    q = [(1000.0, 500.0)] + _q([129] * 5 + [100] + [130] * 3)
    assert L.longest_above_s(q) == 25.0


def test_fisher_and_stratified_exact_values():
    assert L.fisher_one_sided(5, 0, 0, 7) == pytest.approx(1 / 792, rel=1e-12)
    assert L.fisher_one_sided(3, 0, 0, 3) == pytest.approx(1 / 20, rel=1e-12)
    assert L.stratified_exact_one_sided([(1, 0, 0, 5), (4, 0, 0, 2)]) == pytest.approx(1 / 90, rel=1e-12)
    stats = pytest.importorskip("scipy.stats")
    for t in [(5, 0, 0, 7), (3, 1, 1, 4), (2, 3, 4, 1), (0, 2, 3, 3)]:
        a, b, c, d = t
        assert L.fisher_one_sided(*t) == pytest.approx(stats.fisher_exact([[a, b], [c, d]], alternative="greater")[1], rel=1e-9)


def test_counter_rate_and_regime_split_boundaries():
    gnb = [(1200.0 + 5 * i, 0.01 * i) for i in range(5)]
    assert L.counter_rate(gnb, 1200.0, 1220.0) == pytest.approx(0.002)
    assert math.isnan(L.counter_rate(gnb, 1300.0, 1400.0))
    q = [(1200.0, 128.0), (1205.0, 129.0), (1210.0, 19.0), (1215.0, 20.0), (1220.0, 0.0)]
    g = [(1200.0, 0.0), (1205.0, 0.05), (1210.0, 0.06), (1215.0, 0.08), (1220.0, 0.10)]
    le, gt = L.gnb_by_regime(q, g)
    assert le == pytest.approx((0.05 + 0.02) / 10.0)          # queue 128 and 20 count as LPM-active
    assert gt == pytest.approx(0.01 / 5.0)                    # queue 129 is fallback; queue 19 is skipped


def test_hit_bins_and_hitfrac_are_token_weighted():
    reqs = [(10.0, 100.0, 50.0), (20.0, 300.0, 0.0), (310.0, 100.0, 100.0)]
    hb = L.hit_bins(reqs)
    assert hb[0.0] == pytest.approx(50 / 400) and hb[300.0] == pytest.approx(1.0)
    tok, turn, n = L.hitfrac(reqs, 0.0, 300.0)
    assert (tok, turn, n) == (pytest.approx(0.125), 0.0, 2)  # 50 cached of 100 is not > half


# --------------------------------------------------------------------------- committed data
@pytest.fixture(scope="module")
def runs():
    if not HAVE_DATA:
        pytest.skip("pulled E2 / grid data not in this checkout")
    return L.load_runs()


def test_embedded_scout_csv_is_the_scout_file():
    raw = SCOUT_CSV.replace("\n", "\r\n").encode("ascii")
    assert hashlib.sha256(raw).hexdigest() == SCOUT_SHA256


@pytest.mark.skipif(not HAVE_DATA, reason="pulled data not available")
def test_queue_table_reproduces_the_scout_queue_vs_128_csv(runs):
    buf = io.StringIO(newline="")
    L.write_csv(L.queue_table(runs), buf, L.QUEUE_COLUMNS)
    got = buf.getvalue()
    exp_rows = list(csv.DictReader(io.StringIO(SCOUT_CSV)))
    got_rows = list(csv.DictReader(io.StringIO(got)))
    assert len(got_rows) == len(exp_rows) == 24
    for g, e in zip(got_rows, exp_rows):
        assert g == e, {k: (g[k], e[k]) for k in e if g.get(k) != e[k]}
    assert hashlib.sha256(got.encode("ascii")).hexdigest() == SCOUT_SHA256


@pytest.mark.skipif(not HAVE_DATA, reason="pulled data not available")
def test_inputs_are_what_the_analysis_assumes(runs):
    assert sorted({r.label for r in runs}) == ["sglang-fcfs-r0", "sglang-fcfs-r1", "sglang-lpm-r0", "sglang-lpm-r1"]
    assert all(r.launch.get("policy") == r.policy and r.launch.get("refresh") == str(r.refresh)
               and r.launch.get("lpm_inf") == "0" and r.launch.get("kv_tokens") == "300000" for r in runs)
    for r in runs:
        ts = [t for t, _ in r.queue]
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        assert max(gaps) < 1.1 * L.SAMPLE_DT and min(gaps) > 0.9 * L.SAMPLE_DT, r.run   # 60 samples = 300 s
        assert {t for t, _ in r.gnb} == set(ts), r.run
    # one arrival plan per (rate, seed) across all four cells (common random numbers)
    plans = {}
    for r in runs:
        plans.setdefault((r.mult, r.seed), set()).add(r.plan_sha256)
    assert len(plans) == 6 and all(len(v) == 1 for v in plans.values())


@pytest.mark.skipif(not HAVE_DATA, reason="pulled data not available")
def test_crossing_table_fisher_and_pairs(runs):
    rows = L.crossing_table(runs)
    lpm = [x for x in rows if x["policy"] == "lpm"]
    crossed = {(x["label"], x["mult"], x["seed"]): x["t_cross"] for x in lpm if x["crossed"]}
    assert crossed == {("sglang-lpm-r0", "1.35", "0"): 3755, ("sglang-lpm-r0", "1.65", "0"): 3050,
                       ("sglang-lpm-r1", "1.65", "0"): 2880, ("sglang-lpm-r0", "1.65", "1"): 2900,
                       ("sglang-lpm-r1", "1.65", "1"): 2695}
    for x in lpm:
        if x["crossed"]:
            assert x["collapsed"] and x["state"] == "trapped" and x["tok_hit_eval"] < 0.01
            assert x["hit_pre"] > 0.13 and x["hit_post"] < 0.011
        else:
            assert not x["collapsed"] and x["state"] != "trapped" and x["q_max_post"] <= 133
            assert x["longest_gt128_s"] <= 25.0
    s = L.summary(runs)
    f = s["fisher"]
    assert f["table"] == [[5, 0], [0, 7]] and f["p_exact_fraction"] == "1/792"
    assert f["p_one_sided"] == pytest.approx(1 / 792)
    assert f["p_stratified_by_rate"] == pytest.approx(1 / 90)
    assert f["stream_table"] == [[3, 0], [0, 3]] and f["p_streams"] == pytest.approx(1 / 20)
    # FCFS (where 128 means nothing): every run reaches the all-miss floor within a minute of the burst and its queue
    # passes 128 only 2.5-31 min later, so collapse alone drives a queue above 128 (the reverse-causation route)
    for x in rows:
        if x["policy"] == "fcfs":
            assert x["collapsed"] and x["t_hit_floor60"] == 1260 and x["t_first_gt128"] >= 1415


@pytest.mark.skipif(not HAVE_DATA, reason="pulled data not available")
def test_same_seed_natural_experiment(runs):
    ne = L.natural_experiment(runs)
    assert ne["same_plan"] and ne["jobs"] == ("17097088", "17097087")
    r0, r1 = ne["r0"], ne["r1"]
    assert r0["crossed"] and r0["t_first_gt128"] == 3410 and r0["state"] == "trapped" and r0["collapsed"]
    assert not r1["crossed"] and r1["q_max_post"] == 126 and r1["state"] == "recovered" and not r1["collapsed"]
    # the two runs had already separated before r0 first passed 128: r0's hit was lower in every 300-s bin from 1500 s
    pre = [b for b in ne["trace"] if 1500 <= b["t"] < 3300]
    assert pre and all(b["hit_r0"] < b["hit_r1"] for b in pre)
    pairs = L.summary(runs)["pairs"]
    assert [(p["mult"], p["seed"]) for p in pairs if p["discordant"]] == [("1.35", "0")]


@pytest.mark.skipif(not HAVE_DATA, reason="pulled data not available")
def test_scheduler_cost_drops_to_the_fcfs_level_at_the_crossing(runs):
    sc = L.summary(runs)["sched_cost"]
    assert sc["lpm_q_le128"] == (0.0084, 0.0129)
    assert sc["lpm_q_gt128_crossed"] == (0.0028, 0.0031)
    assert sc["fcfs_all"] == (0.0027, 0.0038)
    assert round(sc["lpm_q_le128_mean"], 3) == 0.011 and round(sc["lpm_q_gt128_crossed_mean"], 3) == 0.003
    lo_pre, _ = sc["at_crossing_pre"]
    _, hi_post = sc["at_crossing_post"]
    assert lo_pre > 0.009 and hi_post < 0.0034
    # pooled by queue length: LPM cost rises with the queue up to 128 and is at the FCFS level from 129 on
    lpm = {b["q_lo"]: b for b in L.gnb_by_queue_bin([r for r in runs if r.policy == "lpm"], L.COST_EDGES)}
    assert lpm[113]["s_per_s"] > 0.012 and lpm[129]["s_per_s"] < 0.0035
    assert all(b["s_per_s"] < 0.0035 for q, b in lpm.items() if q >= 129 and b["n"] >= 20)
    assert 0.007 < sc["lpm_fit_per_100_waiting"] < 0.009
