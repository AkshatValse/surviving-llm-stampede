"""Tests of the round-5 evaluator (src/prefixmeta/r5_eval.py) on synthetic inputs with a known right answer: the S1-S4 clauses at their
boundaries, the KILL criterion and the ANSWER template, NOT_EVALUABLE on missing cells, the grid-edge rule for C2, the sensitivity readings,
the thrash label (reported, never decisive), verdict suppression, variant rows, row order, and the verbatim claims."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r5_eval as E
from prefixmeta.mech_runner import load_mech_config

REPO = Path(__file__).resolve().parent.parent
PREREG = REPO / "configs" / "prefix_meta_r5_prereg.yaml"
GRID = [8, 12, 16, 20, 24, 28, 32, 40, 60, 100, 200, 300]
SEEDS = [3000, 3001, 3002]
LAM = 0.05
MODES = ["ondemand_preempt", "ratio_reserve"]


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_mech_config(str(REPO / "configs" / "prefix_meta_r5.yaml"), REPO)


@pytest.fixture(scope="module")
def design() -> dict:
    return yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]


def shape(peak_n: int = 20, peak: float = 0.19, tail: float = 0.05, tail300: Optional[float] = None) -> Dict[int, float]:
    """A unimodal curve: linear rise to ``peak`` at ``peak_n``, linear fall to ``tail`` at n = 40, flat after (300: ``tail300``)."""
    out = {}
    for n in GRID:
        if n <= peak_n:
            out[n] = peak * n / peak_n
        elif n < 40:
            out[n] = peak + (tail - peak) * (n - peak_n) / (40 - peak_n)
        else:
            out[n] = tail
    if tail300 is not None:
        out[300] = tail300
    return out


def curve_frame(curves: Dict[str, Dict[str, Dict[int, float]]], noise: float = 0.0, thrash_cells: Sequence = (), seed_offsets=(-1.0, 0.0, 1.0)) -> pd.DataFrame:
    """curves[mode][policy][n] = seed-mean mu; the three seeds are mean + offset * noise (sample sd = noise)."""
    rows = []
    for mode, pols in curves.items():
        for pol, c in pols.items():
            for n, mu in c.items():
                for sd, off in zip(SEEDS, seed_offsets):
                    flag = (mode, pol, n) in set(thrash_cells)
                    rows.append({"mode": mode, "policy": pol, "n_nominal": n, "n": n, "seed": sd, "mu": mu + off * noise, "hit_rate": 0.5,
                                 "reserved_tokens": 1000.0 + n, "preemptions_per_turn": 0.2 if flag else 0.001, "preempt_max_turn": 12 if flag else 1,
                                 "thrash": flag, "mu_first_half": mu, "mu_second_half": mu})
    return pd.DataFrame(rows)


def calib_frame(lams: Dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([{"mode": m, "seed": s, "sessions_per_s": v, "preemptions_per_s": 0.0, "preemptions_per_turn": 0.0, "recompute_frac": 0.0}
                         for m, v in lams.items() for s in (3300, 3301)])


def burst_frame(rec: Dict[str, Dict[int, Sequence[bool]]], hit: float = 0.5, backlog: float = 100.0, thrash: bool = False) -> pd.DataFrame:
    rows = []
    for mode, by_b in rec.items():
        for b, flags in by_b.items():
            for sd, ok in zip([3100, 3101, 3102, 3103, 3104], flags):
                rows.append({"alloc_mode": mode, "burst_n": b, "seed": sd, "recovered": ok, "tail_hit_rate": 0.95 if ok else hit,
                             "tail_backlog_mean": 1.0 if ok else backlog, "tail_thrash": thrash, "tail_preemptions_per_turn": 0.1 if thrash else 0.0,
                             "tail_preempt_max_turn": 11 if thrash else 0, "max_preempt_per_turn": 11 if thrash else 0})
    return pd.DataFrame(rows)


def cap_frame(rec: Dict[str, Dict[str, Sequence[bool]]], cap: int = 20) -> pd.DataFrame:
    rows = []
    for mode, by_arm in rec.items():
        for arm, flags in by_arm.items():
            for sd, ok in zip([3200, 3201, 3202], flags):
                rows.append({"alloc_mode": mode, "arm": arm, "seed": sd, "cap": cap if arm == "capped_at_nstar" else -1, "recovered": ok,
                             "tail_hit_rate": 0.95 if ok else 0.1, "tail_backlog_mean": 1.0 if ok else 300.0, "tail_gate_mean": 0.0,
                             "tail_thrash": False, "tail_preemptions_per_turn": 0.0, "tail_preempt_max_turn": 0, "max_preempt_per_turn": 0})
    return pd.DataFrame(rows)


def good_inputs(**kw) -> E.R5Inputs:
    curves = {m: {"fcfs_lru": shape(), "lpm_lru": {n: v + 0.012 for n, v in shape().items()}} for m in MODES + ["full_reserve"]}
    return E.R5Inputs(calib=calib_frame({m: LAM for m in MODES + ["full_reserve"]}), curve=curve_frame(curves, noise=0.001),
                      burst=burst_frame({m: {0: [True] * 5, 200: [False] * 5} for m in MODES}),
                      cap=cap_frame({m: {"capped_at_nstar": [True] * 3, "no_cap": [False] * 3} for m in MODES}))


def run(inp, cfg, design, **kw):
    return E.evaluate_all(inp, design, cfg["evaluation"], cfg["thrash"], claims=E.registered_claims(PREREG), modes=MODES, **kw)


def get(rows, pid, mode="ondemand_preempt"):
    r = [x for x in rows if x["id"] == pid and x["mode"] == mode]
    assert len(r) == 1, (pid, mode, len(r))
    return r[0]


# ============================================================================ the headline on a textbook curve
def test_a_collapsing_unimodal_curve_passes_everything_and_the_answer_is_persists(cfg, design):
    rows = run(good_inputs(), cfg, design)
    for m in MODES:
        assert get(rows, "S1", m)["verdict"] == E.PASS and get(rows, "S1-KILL", m)["verdict"] == E.KILL_F
        assert [get(rows, k, m)["verdict"] for k in ("S2", "S3", "S4")] == [E.PASS] * 3
        assert get(rows, "ANSWER", m)["verdict"] == E.PERSISTS
        n = get(rows, "S1", m)["numbers"]
        assert n["n_star"] == 20 and n["mu300"] == pytest.approx(0.05) and n["max_over_mu300"] == pytest.approx(3.8)
        assert get(rows, "S2", m)["numbers"]["n_not_recovered_burst"] == 5 and get(rows, "S3", m)["numbers"]["n_star"] == 20
        assert get(rows, "S4", m)["numbers"]["d_m_over_lambda"] == pytest.approx(0.012 / LAM)
    assert get(rows, "ANSWER")["notes"].count("d = 100") == 1 and "long-decode" in get(rows, "ANSWER")["notes"]


def test_rows_are_ordered_registered_readings_first_and_claims_are_verbatim(cfg, design):
    rows = run(good_inputs(), cfg, design)
    rank = {"headline": 0, "clause": 1, "sensitivity": 2, "information": 3}
    assert [rank[r["reading"]] for r in rows] == sorted(rank[r["reading"]] for r in rows)
    assert {r["id"] for r in rows if r["reading"] == "headline"} == {"S1", "S1-KILL", "S2", "S3", "S4", "ANSWER"}
    claims = yaml.safe_load(PREREG.read_text())["preregistration"]["predictions"]
    for r in rows:
        base = r["id"].split("-")[0].split("@")[0]
        if base in claims:
            assert r["claim"] == claims[base]
    df = E.rows_to_frame(rows)
    assert list(df.columns) == ["id", "mode", "reading", "verdict", "claim", "numbers", "notes"] and len(df) == len(rows)
    json.loads(df["numbers"].iloc[0])


# ============================================================================ S1 boundaries
def _s1(cfg, design, curve, lam=LAM, noise=0.0):
    inp = E.R5Inputs(calib=calib_frame({m: lam for m in MODES}), curve=curve_frame({m: {"fcfs_lru": curve} for m in MODES}, noise=noise))
    ctx = E.Ctx(design, cfg["evaluation"], cfg["thrash"], E.registered_claims(PREREG))
    return {r["id"]: r for r in E.eval_s1(inp, "ondemand_preempt", ctx)}


def test_c1_is_a_less_or_equal_bound_at_1_3_lambda(cfg, design):
    assert _s1(cfg, design, shape(tail=1.3 * LAM - 1e-12))["S1-clause-C1-mu300"]["verdict"] == E.PASS
    assert _s1(cfg, design, shape(tail=1.3 * LAM + 1e-6))["S1-clause-C1-mu300"]["verdict"] == E.FAIL


def test_c2_is_a_greater_or_equal_bound_at_2_mu300_and_kill_at_0_8(cfg, design):
    cv = shape(peak=0.10, tail=0.05)                                    # max = 2 x mu(300) exactly, interior argmax
    r = _s1(cfg, design, cv)
    assert r["S1-clause-C2-peak"]["verdict"] == E.PASS and r["S1-KILL"]["verdict"] == E.KILL_F
    r = _s1(cfg, design, shape(peak=0.0999, tail=0.05))
    assert r["S1-clause-C2-peak"]["verdict"] == E.FAIL
    r = _s1(cfg, design, shape(peak=0.0625, tail=0.05))                 # mu300 = 0.8 max exactly -> KILL (>=)
    assert r["S1-KILL"]["verdict"] == E.KILL_T and r["S1"]["verdict"] == E.FAIL
    assert _s1(cfg, design, shape(peak=0.0626, tail=0.05))["S1-KILL"]["verdict"] == E.KILL_F


def test_a_flat_curve_is_an_artifact_and_the_answer_says_so(cfg, design):
    flat = {n: 0.05 for n in GRID}
    inp = E.R5Inputs(calib=calib_frame({m: LAM for m in MODES}), curve=curve_frame({m: {"fcfs_lru": flat, "lpm_lru": flat} for m in MODES}))
    ctx = E.Ctx(design, cfg["evaluation"], cfg["thrash"], E.registered_claims(PREREG))
    rows = E.evaluate_mode_set(inp, ["ondemand_preempt"], ctx)
    a = [r for r in rows if r["id"] == "ANSWER"][0]
    assert a["verdict"] == E.ARTIFACT and [r for r in rows if r["id"] == "S1-KILL"][0]["verdict"] == E.KILL_T


def test_an_argmax_at_a_grid_edge_cannot_satisfy_c2(cfg, design):
    decreasing = {n: 0.2 * 8 / n for n in GRID}                         # argmax at the first grid point, max/mu300 = 37.5 numerically
    r = _s1(cfg, design, decreasing)
    assert r["S1-clause-C2-peak"]["verdict"] == E.FAIL and r["S1-clause-C2-peak"]["numbers"]["C2_numeric"] is True
    assert r["S1-clause-C2-peak"]["numbers"]["argmax_at_grid_edge"] is True and "grid edge" in r["S1"]["notes"]
    rising = {n: 0.01 * i for i, n in enumerate(GRID)}                  # argmax at n = 300
    assert _s1(cfg, design, rising)["S1-clause-C2-peak"]["verdict"] == E.FAIL


def _with_bump(delta: float) -> Dict[int, float]:
    """The collapsing curve with n = 32 raised ``delta`` ABOVE n = 28 (a rise after the peak). PAV pools the pair: deviation delta / 2 each."""
    cv = shape()
    cv[32] = cv[28] + delta
    return cv


def test_unimodality_tolerance_registered_strict_and_lenient(cfg, design):
    r = _s1(cfg, design, _with_bump(0.010))                             # deviation 0.005 = 0.1 lambda > max(2 SE = 0, 0.02 lambda)
    assert r["S1-clause-C0-unimodal"]["verdict"] == E.FAIL
    assert r["S1-clause-C0-unimodal"]["numbers"]["max_deviation_over_tol"] == pytest.approx(0.005 / (0.02 * LAM))
    # the same curve with seed noise of sd 0.01 (SE = 0.0058, 2 SE = 0.0115 >= 0.005): unimodal within 2 SE
    assert _s1(cfg, design, _with_bump(0.010), noise=0.01)["S1-clause-C0-unimodal"]["verdict"] == E.PASS

    def full(cv):
        inp = E.R5Inputs(calib=calib_frame({m: LAM for m in MODES}), curve=curve_frame({m: {"fcfs_lru": cv, "lpm_lru": cv} for m in MODES}),
                         burst=good_inputs().burst, cap=good_inputs().cap)
        return run(inp, cfg, design)
    rows = full(_with_bump(0.0005))                                     # deviation 0.00025 < 0.001: passes registered, fails strict
    assert get(rows, "S1")["numbers"]["C0_unimodal"] is True and get(rows, "S1-strict-unimodal")["numbers"]["C0_unimodal"] is False
    rows = full(_with_bump(0.008))                                      # deviation 0.004: fails registered (0.001), passes lenient (0.005)
    assert get(rows, "S1")["numbers"]["C0_unimodal"] is False and get(rows, "S1-lenient-unimodal")["numbers"]["C0_unimodal"] is True
    rows = full(_with_bump(0.012))                                      # deviation 0.006 > 0.005: fails lenient too
    assert get(rows, "S1-lenient-unimodal")["numbers"]["C0_unimodal"] is False


def test_s1_per_seed_counts_the_seeds_that_pass_on_their_own_curve(cfg, design):
    rows = run(good_inputs(), cfg, design)
    ps = get(rows, "S1-per-seed")
    assert ps["numbers"]["n_pass"] == 3 and ps["verdict"] == E.PASS
    # one seed with a flat curve -> KILL on that seed and a MIXED row
    inp = good_inputs()
    cur = inp.curve
    flat = (cur["mode"] == "ondemand_preempt") & (cur["policy"] == "fcfs_lru") & (cur["seed"] == 3002)
    cur.loc[flat, "mu"] = 0.05
    ps = get(run(inp, cfg, design), "S1-per-seed")
    assert ps["numbers"]["n_pass"] == 2 and ps["verdict"] == E.MIXED and ps["numbers"]["n_kill"] == 1


def test_missing_cells_are_not_evaluable_never_judged_on_a_partial_design(cfg, design):
    inp = good_inputs()
    inp.curve = inp.curve[~((inp.curve["mode"] == "ondemand_preempt") & (inp.curve["policy"] == "fcfs_lru") & (inp.curve["n_nominal"] == 60)
                           & (inp.curve["seed"] == 3001))]
    inp.burst = inp.burst[~((inp.burst["alloc_mode"] == "ratio_reserve") & (inp.burst["burst_n"] == 0) & (inp.burst["seed"] == 3104))]
    inp.cap = inp.cap[~((inp.cap["alloc_mode"] == "ondemand_preempt") & (inp.cap["arm"] == "no_cap") & (inp.cap["seed"] == 3200))]
    rows = run(inp, cfg, design)
    assert get(rows, "S1")["verdict"] == E.NA and get(rows, "S1-KILL")["verdict"] == E.NA and get(rows, "ANSWER")["verdict"] == E.NA
    assert get(rows, "S3")["verdict"] == E.NA and get(rows, "S4")["verdict"] == E.PASS
    assert get(rows, "S2", "ratio_reserve")["verdict"] == E.NA and get(rows, "S2")["verdict"] == E.PASS
    assert get(rows, "S1", "ratio_reserve")["verdict"] == E.PASS
    assert E.evaluate_all(E.R5Inputs(), design, cfg["evaluation"], cfg["thrash"], modes=MODES)[0]["verdict"] == E.NA


# ============================================================================ S2 / S3 / S4
@pytest.mark.parametrize("burst_flags,nob_flags,expect,unstable", [
    ([False] * 3 + [True] * 2, [True] * 5, E.PASS, False),                 # 3/5 not recovered, no-burst 5/5 good
    ([False] * 2 + [True] * 3, [True] * 5, E.FAIL, False),                 # only 2/5 not recovered
    ([False] * 5, [True] * 4 + [False], E.PASS, False),                    # no-burst 4/5 good is allowed
    ([False] * 5, [True] * 3 + [False] * 2, E.FAIL, True),                 # open system unstable without a burst
])
def test_s2_thresholds_and_the_paired_no_burst_clause(cfg, design, burst_flags, nob_flags, expect, unstable):
    inp = good_inputs()
    inp.burst = burst_frame({m: {0: nob_flags, 200: burst_flags} for m in MODES})
    r = get(run(inp, cfg, design), "S2")
    assert r["verdict"] == expect
    assert ("unstable at 2 lambda_m" in r["notes"]) == unstable
    clauses = {x["id"]: x["verdict"] for x in run(inp, cfg, design) if x["mode"] == "ondemand_preempt" and x["id"].startswith("S2-clause")}
    assert clauses["S2-clause-burst"] == (E.PASS if sum(not f for f in burst_flags) >= 3 else E.FAIL)
    assert clauses["S2-clause-noburst"] == (E.PASS if sum(not f for f in nob_flags) <= 1 else E.FAIL)


def test_s2_hit_only_sensitivity_ignores_the_backlog(cfg, design):
    inp = good_inputs()
    b = burst_frame({m: {0: [True] * 5, 200: [False] * 5} for m in MODES})
    b.loc[b["burst_n"] == 200, "tail_hit_rate"] = 0.9                    # hit rate fine, backlog high (e.g. thrash backlog): not recovered by backlog
    inp.burst = b
    rows = run(inp, cfg, design)
    assert get(rows, "S2")["verdict"] == E.PASS and get(rows, "S2-hit-only")["verdict"] == E.FAIL


@pytest.mark.parametrize("capped,nocap,expect", [([True] * 3, [False] * 3, E.PASS), ([True, True, False], [False] * 3, E.PASS),
                                                 ([True, False, False], [False] * 3, E.FAIL), ([True] * 3, [True, False, False], E.FAIL)])
def test_s3_thresholds(cfg, design, capped, nocap, expect):
    inp = good_inputs()
    inp.cap = cap_frame({m: {"capped_at_nstar": capped, "no_cap": nocap} for m in MODES})
    assert get(run(inp, cfg, design), "S3")["verdict"] == expect


def test_s3_is_not_evaluable_without_a_collapse_or_with_a_wrong_cap(cfg, design):
    inp = good_inputs()
    rising = {n: 0.005 * i for i, n in enumerate(GRID)}                  # argmax at n = 300 >= 100
    inp.curve = curve_frame({m: {"fcfs_lru": rising, "lpm_lru": rising} for m in MODES})
    inp.cap = cap_frame({m: {"capped_at_nstar": [True] * 3, "no_cap": [False] * 3} for m in MODES}, cap=300)
    r = get(run(inp, cfg, design), "S3")
    assert r["verdict"] == E.NA and "no collapse to cap" in r["notes"]
    inp = good_inputs()
    inp.cap = cap_frame({m: {"capped_at_nstar": [True] * 3, "no_cap": [False] * 3} for m in MODES}, cap=24)          # runs used 24, the curve says n* = 20
    r = get(run(inp, cfg, design), "S3")
    assert r["verdict"] == E.NA and "cap used" in r["notes"]


def test_nstar_is_the_first_argmax(cfg, design):
    cv = shape()
    cv[24] = cv[20]
    inp = E.R5Inputs(calib=calib_frame({m: LAM for m in MODES}), curve=curve_frame({m: {"fcfs_lru": cv} for m in MODES}))
    assert E.nstar_of(inp, "ondemand_preempt", E.Ctx(design, cfg["evaluation"], cfg["thrash"])) == 20


def test_s4_threshold_is_0_05_lambda_and_all_seeds_is_a_sensitivity(cfg, design):
    def inputs(gap, offsets):
        f = shape()
        l = dict(f)
        l[300] = f[300] + gap
        curves = {m: {"fcfs_lru": f, "lpm_lru": l} for m in MODES}
        cf = curve_frame(curves, seed_offsets=offsets, noise=0.0)
        return E.R5Inputs(calib=calib_frame({m: LAM for m in MODES}), curve=cf, burst=good_inputs().burst, cap=good_inputs().cap)
    rows = run(inputs(0.05 * LAM, (0, 0, 0)), cfg, design)
    assert get(rows, "S4")["verdict"] == E.PASS and get(rows, "S4-all-seeds")["verdict"] == E.PASS
    assert get(rows, "S4")["numbers"]["d_m_over_mu300_fcfs"] == pytest.approx(0.05 * LAM / 0.05)
    assert get(run(inputs(0.05 * LAM - 1e-6, (0, 0, 0)), cfg, design), "S4")["verdict"] == E.FAIL
    # the mean gap clears the bar but one paired seed does not: headline PASS, all-seeds FAIL
    f = shape()
    l = dict(f)
    l[300] = f[300] + 0.004
    cf = curve_frame({m: {"fcfs_lru": f, "lpm_lru": l} for m in MODES})
    cf.loc[(cf["policy"] == "lpm_lru") & (cf["n_nominal"] == 300) & (cf["seed"] == 3000), "mu"] = f[300] - 0.001
    cf.loc[(cf["policy"] == "lpm_lru") & (cf["n_nominal"] == 300) & (cf["seed"] == 3001), "mu"] = f[300] + 0.004
    cf.loc[(cf["policy"] == "lpm_lru") & (cf["n_nominal"] == 300) & (cf["seed"] == 3002), "mu"] = f[300] + 0.009
    rows = run(E.R5Inputs(calib=calib_frame({m: LAM for m in MODES}), curve=cf, burst=good_inputs().burst, cap=good_inputs().cap), cfg, design)
    assert get(rows, "S4")["verdict"] == E.PASS and get(rows, "S4-all-seeds")["verdict"] == E.FAIL
    assert "IDEALISED LPM" in get(rows, "S4")["notes"]


# ============================================================================ thrash label, suppression, variants, information rows
def test_the_thrash_label_is_reported_next_to_the_verdict_and_never_changes_it(cfg, design):
    plain = run(good_inputs(), cfg, design)
    inp = good_inputs()
    curves = {m: {"fcfs_lru": shape(), "lpm_lru": {n: v + 0.012 for n, v in shape().items()}} for m in MODES + ["full_reserve"]}
    inp.curve = curve_frame(curves, noise=0.001, thrash_cells=[("ondemand_preempt", "fcfs_lru", 300), ("ondemand_preempt", "lpm_lru", 300)])
    inp.burst = burst_frame({m: {0: [True] * 5, 200: [False] * 5} for m in MODES}, thrash=True)
    flagged = run(inp, cfg, design)
    for pid in ("S1", "S1-KILL", "S2", "S4", "ANSWER"):
        assert get(flagged, pid)["verdict"] == get(plain, pid)["verdict"]
    assert "THRASH-FLAG at fcfs_lru n=300" in get(flagged, "S1")["notes"] and get(flagged, "S1")["numbers"]["thrash"]["fcfs_lru n=300"]["n_flagged"] == 3
    assert "THRASH-FLAG" in get(flagged, "S2")["notes"] and get(flagged, "S2")["numbers"]["thrash"]["burst=200"]["n_flagged"] == 5
    assert "THRASH-FLAG" in get(flagged, "S4")["notes"]
    assert "no thrash flag" in get(plain, "S1")["notes"] and "THRASH-FLAG" not in get(flagged, "S1", "ratio_reserve")["notes"]
    info = get(flagged, "INFO-thrash")
    assert len(info["numbers"]["curve_flagged"]) == 6 and info["numbers"]["burst_tail_flagged"] == 10


def test_verdicts_are_suppressed_for_unsafe_inputs_and_numbers_are_kept(cfg, design):
    rows = E.suppress_verdicts(run(good_inputs(), cfg, design), "q: quick run")
    assert all(r["verdict"] in (E.NA, E.INFO) for r in rows)
    r = get(rows, "S1")
    assert "VERDICT SUPPRESSED: q: quick run" in r["notes"] and r["numbers"]["mu300"] == pytest.approx(0.05)


def test_information_rows(cfg, design):
    rows = run(good_inputs(), cfg, design)
    lam = get(rows, "INFO-lambda_miss", "full_reserve")
    assert lam["numbers"]["lambda_miss"] == pytest.approx(LAM) and lam["numbers"]["ratio_to_round1_full_reserve"] == pytest.approx(LAM / 0.047418947)
    ex = get(rows, "INFO-reservation-excess")
    assert ex["numbers"]["by_n"]["300"]["excess"] == pytest.approx(0.0) and "0.9 % of M" in ex["notes"]
    assert get(rows, "INFO-stationarity")["numbers"]["by_n"]["20"]["first_half"] == pytest.approx(0.19)
    assert get(rows, "S1-vs-reference")["verdict"] == E.INFO and "full_reserve" in get(rows, "S1-vs-reference")["numbers"]


def test_variant_rows_carry_the_suffix_and_are_sensitivities(cfg, design):
    main = good_inputs()
    var = good_inputs()
    var.burst = burst_frame({"ondemand_preempt": {0: [True] * 5, 200: [True] * 5}})                  # the variant does not trap
    rows = E.evaluate_all(main, design, cfg["evaluation"], cfg["thrash"], claims=E.registered_claims(PREREG), modes=MODES,
                          variants={"stage1_whole_victim": var})
    v = get(rows, "S2@stage1_whole_victim")
    assert v["reading"] == "sensitivity" and v["verdict"] == E.FAIL
    assert get(rows, "S2")["verdict"] == E.PASS                                                      # the headline is untouched
    assert get(rows, "ANSWER@stage1_whole_victim")["reading"] == "sensitivity"
    assert get(rows, "S2@stage1_whole_victim", "ratio_reserve")["verdict"] == E.NA                   # the variant has no ratio_reserve burst cells


def test_lpm128_information_row(cfg, design):
    main = good_inputs()
    l128 = shape()
    l128[300] = shape()[300] + 0.001
    var = E.R5Inputs(curve=pd.concat([curve_frame({m: {"lpm128_lru": {300: l128[300]}}}) for m in MODES]))
    rows = E.evaluate_all(main, design, cfg["evaluation"], cfg["thrash"], claims=E.registered_claims(PREREG), modes=MODES, variants={"lpm128": var})
    r = get(rows, "S4-lpm128")
    assert r["reading"] == "information" and r["verdict"] == E.INFO and r["numbers"]["d_m"] == pytest.approx(0.001)
    assert get(rows, "S4")["verdict"] == E.PASS                                                      # registered S4 unaffected
