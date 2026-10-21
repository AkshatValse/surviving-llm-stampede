"""Tests of the round-4 amendment 1 (configs/prefix_meta_r4_prereg.yaml, ``amendment_1``): append-only registration, stricter R4
headline in the verbatim orientation, R1/R2 sensitivity rows, the R3 bootstrap robustness label / envelope / informational cells,
R6 null-implied reporting, the seed bootstrap, claim strings from the prereg, and verdict suppression for unsafe inputs."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r4_boot as B
from prefixmeta import r4_eval as E
from prefixmeta.mech_runner import load_mech_config
from prefixmeta.r4_runner import burst_info_specs, curve_table
from prefixmeta.report_r4 import unsafe_inputs

from test_r4 import (CONFIG, GRID, LAM_MISS, LAMCAP, LRU, PHASE, PREREG, REPO, RND, SEEDS, VERBATIM, base_curves, burst_df, by_id,
                     cap_df, run_cli, synth_curve_runs)

# sha256 of the first 23003 bytes of the pre-registration = the text registered in commit db30e76 (before any amendment)
REGISTERED_BYTES = 23003
REGISTERED_SHA256 = "658f846acadc43a8dd7b73052b88499eb8274c515a1e76af2551edc5210b18f6"


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_mech_config(str(CONFIG), REPO)


@pytest.fixture(scope="module")
def design() -> dict:
    return yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]


# =========================================================================== the amendment is append-only and matches the config
def test_registered_text_is_untouched_and_amendment_is_appended():
    raw = PREREG.read_bytes()
    assert hashlib.sha256(raw[:REGISTERED_BYTES]).hexdigest() == REGISTERED_SHA256
    doc = yaml.safe_load(raw)
    pre = doc["preregistration"]
    assert list(doc)[0] == "research_question"
    assert list(pre)[-2:] == ["amendment_1", "amendment_2"] and pre["amendment_1"]["date"].isoformat() == "2026-10-21"
    assert pre["amendment_2"]["posthoc_information_row"]["id"] == "R3-posthoc-b0-excluded"
    for k in ("disclosure_of_looks", "reclassification_of_predictions", "R4_amended_reading", "R1_R2_sensitivity",
              "R3_amended_reporting", "burst_info_cells", "R6_amended_reporting", "fluid_predictor_fix", "evaluator_hygiene",
              "findings_dispositions"):
        assert k in pre["amendment_1"], k
    assert pre["predictions"] == VERBATIM                                  # R1-R6 verbatim, unchanged
    assert "round1_burst_sweep" not in pre["known_at_writing"]               # the original text is not rewritten
    assert "No burst-size sweep" in pre["known_at_writing"]["never_observed"]


def test_burst_info_config_equals_the_amendment_and_bootstrap_constants(cfg):
    am = yaml.safe_load(PREREG.read_text())["preregistration"]["amendment_1"]["burst_info_cells"]
    bi = cfg["burst_info"]
    assert bi["seeds"] == am["seeds"] == cfg["burst"]["seeds"]
    for key in ("warmup_s", "burst_width_s", "after_s", "recovered_hit_above", "recovered_backlog_below"):
        assert bi[key] == am["common"][key] == cfg["burst"][key]
    assert bi["lambda_dependence"] == am["lambda_dependence"] and bi["control_random"] == am["control_random"]
    assert cfg["report"]["bootstrap"] == {"n_boot": B.BOOT_N, "entropy": B.BOOT_ENTROPY, "level": B.BOOT_LEVEL}
    assert (B.BOOT_N, B.BOOT_ENTROPY, B.BOOT_LEVEL) == (2000, 20261021, 0.95)
    assert E.R6_MARGIN == 1.10


def test_burst_info_specs_cover_the_informational_cells(cfg):
    bi = cfg["burst_info"]
    specs = burst_info_specs(cfg, bi, LAM_MISS)
    assert len(specs) == (3 * 15 + 1) * 5
    assert {s.seed for s in specs} == set(bi["seeds"])
    lru = [s for s in specs if s.policy == "fcfs_lru"]
    assert {round(s.plan.rate / LAM_MISS, 6) for s in lru} == {1.5, 2.0, 2.5}
    assert sorted({s.plan.burst_n for s in lru}) == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 80, 100, 150]
    rnd = [s for s in specs if s.policy == "fcfs_random"]
    assert len(rnd) == 5 and all(s.plan.burst_n == 0 and s.plan.rate == pytest.approx(2 * LAM_MISS) for s in rnd)
    assert all(s.horizon_s == 65000.0 and s.plan.burst_t0 == 5000.0 and s.exp == "r4_burst_info" for s in specs)
    assert all(s.stop_queue_above is None and s.stop_backlog_above is None for s in specs)      # no early stop


# =========================================================================== claims come from the prereg; verdicts are suppressed on unsafe inputs
def test_claim_strings_are_the_verbatim_registered_predictions_with_parentheticals(design):
    assert E.registered_claims() == VERBATIM
    rows = E.evaluate_all(synth_curve_runs(base_curves()), burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), cap_df({}), PHASE, LAMCAP,
                          LAM_MISS, design)
    for r in rows:
        base = r["id"].split("-")[0]
        assert r["claim"] == VERBATIM[base], r["id"]
    assert "(all above N_lb = 28)" in by_id(rows)["R5"]["claim"] and "(graceful degradation)" in by_id(rows)["R2"]["claim"]
    # an explicit claims argument is used and then restored
    rows = E.evaluate_all(synth_curve_runs(base_curves()), None, None, None, None, LAM_MISS, design, claims={"R1": "X"})
    assert by_id(rows)["R1"]["claim"] == "X"
    assert E._row("R1", E.PASS, {})["claim"] == VERBATIM["R1"]


def test_unsafe_inputs_and_verdict_suppression(design):
    clean = {"experiment": "x", "quick": False, "git_dirty": False, "status": "done"}
    assert unsafe_inputs({"curve": clean, "burst": None}) == []
    assert any("quick" in x for x in unsafe_inputs({"curve": {**clean, "quick": True}}))
    assert any("dirty" in x for x in unsafe_inputs({"curve": {**clean, "git_dirty": True}}))
    assert any("dirty" in x for x in unsafe_inputs({"curve": {**clean, "git_dirty": None}}))
    assert any("not 'done'" in x for x in unsafe_inputs({"curve": {**clean, "status": "running"}}))
    assert any("meta.json missing" in x for x in unsafe_inputs({"curve": {"dir": "d", "meta": None}}))
    rows = E.evaluate_all(synth_curve_runs(base_curves()), burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), cap_df({}), PHASE, LAMCAP,
                          LAM_MISS, design, lambda_miss_k={0.5: 0.5 * LAM_MISS, 2.0: 2.05 * LAM_MISS})
    assert any(r["verdict"] in (E.PASS, E.FAIL) for r in rows)
    sup = E.suppress_verdicts(rows, "curve: produced from a dirty git tree")
    assert all(r["verdict"] not in E.TEST_VERDICTS for r in sup)
    assert all("VERDICT SUPPRESSED" in r["notes"] for r, o in zip(sup, rows) if o["verdict"] in E.TEST_VERDICTS)
    assert [r["numbers"] for r in sup] == [r["numbers"] for r in rows]             # numbers are kept
    assert [r["verdict"] for r, o in zip(sup, rows) if o["verdict"] == E.INFO] == [E.INFO] * sum(o["verdict"] == E.INFO for o in rows)


# =========================================================================== seed bootstrap
def test_bootstrap_streams_are_reproducible_per_tag_and_order_independent():
    a = B.resample_indices("R3", 3, 500)
    b = B.resample_indices("R3", 3, 500)
    c = B.resample_indices("R6", 3, 500)
    _ = B.resample_indices("other", 3, 10)                                   # evaluating another tag does not change "R3"
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert a.shape == (500, 3) and a.min() == 0 and a.max() == 2
    assert not np.array_equal(a, B.resample_indices("R3", 3, 500, entropy=1))
    M = np.arange(12, dtype=float).reshape(4, 3)
    idx = np.array([[0, 0, 0], [0, 1, 2]])
    bm = B.boot_means(M, idx)
    assert bm.shape == (2, 4) and np.allclose(bm[0], M[:, 0]) and np.allclose(bm[1], M.mean(axis=1))


def test_interval_handles_nan_and_inf_and_se_rows():
    iv = B.interval([1.0, 2.0, 3.0, 4.0, 5.0], 0.95)
    assert iv["lo"] == pytest.approx(1.1) and iv["hi"] == pytest.approx(4.9) and iv["median"] == 3.0 and iv["n"] == 5
    iv = B.interval([1.0, np.nan, np.inf, np.inf, 2.0, 3.0], 0.95)
    assert iv["n_nan"] == 1 and iv["n_inf"] == 2 and iv["n"] == 5 and iv["hi"] == math.inf and iv["lo"] >= 1.0
    assert B.interval([np.nan, np.nan])["n"] == 0 and math.isnan(B.interval([np.nan])["lo"])
    assert B.interval([np.inf, np.inf, np.inf])["lo"] == math.inf
    M = np.array([[1.0, 2.0, 3.0], [5.0, 5.0, 5.0]])
    assert np.allclose(B.se_rows(M), [1.0 / math.sqrt(3), 0.0])
    assert np.isnan(B.se_rows(M[:, :1])).all()


def test_curve_table_has_the_seed_standard_error():
    cr = synth_curve_runs({("fcfs_lru", 1.0): LRU})
    for c in ("hit_rate", "gpu_busy", "resident_kv_tokens", "reserved_tokens", "idle_tokens", "evictions_per_s", "turns_per_s",
              "mu_first_half", "mu_second_half"):
        cr[c] = 0.5
    ct = curve_table(cr)
    row = ct[ct["n_nominal"] == 22].iloc[0]
    assert row["mu_se"] == pytest.approx(row["mu_sd"] / math.sqrt(3)) and row["mu_se"] > 0


# =========================================================================== R4: stricter headline, verbatim orientation, new rows
def r4_rows(r_fcfs: float, r_lpm: float, phase=PHASE, r_tail_lpm=None) -> Dict[str, dict]:
    f = [m if n != 300 else r_fcfs * LAM_MISS for n, m in zip(GRID, LRU)]
    l = [m if n != 300 else r_lpm * LAM_MISS for n, m in zip(GRID, LRU)]
    cr = synth_curve_runs({("fcfs_lru", 1.0): f, ("lpm_lru", 1.0): l}, scale_seed=0.0)
    return by_id(E.eval_r4(cr, phase, LAM_MISS, yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]))


def test_r4_tests_orientation_and_bounds_by_hand():
    # LPM bracket (1.1, 1.25]: t = 1.175. Registered |r - t| <= 0.15 t -> r in [0.99875, 1.35125]; verbatim |t - r| <= 0.15 r ->
    # r in [1.175/1.15, 1.175/0.85] = [1.02174, 1.38235]
    lo, hi = 1.1, 1.25
    t = E.r4_tests(0.999, lo, hi)
    assert t["registered"] and not t["verbatim"] and not t["headline"]
    t = E.r4_tests(1.0, lo, hi)                                              # the trivial predictor 'r = 1': passes only the transposed test
    assert t["registered"] and not t["verbatim"] and not t["headline"]
    t = E.r4_tests(1.03, lo, hi)
    assert t["registered"] and t["verbatim"] and t["headline"]
    t = E.r4_tests(1.36, lo, hi)                                             # verbatim-only
    assert not t["registered"] and t["verbatim"] and not t["headline"]
    # strict (every t in [lo, hi]): hi/1.15 <= r <= lo/0.85 -> [1.08696, 1.29412]; lenient (some t): [lo/1.15, hi/0.85] = [0.95652, 1.47059]
    for r, s, l in ((1.08, False, True), (1.09, True, True), (1.29, True, True), (1.30, False, True), (0.95, False, False),
                    (0.96, False, True), (1.47, False, True), (1.48, False, False)):
        t = E.r4_tests(r, lo, hi)
        assert (t["strict"], t["lenient"]) == (s, l), r
    # the original (transposed) formulas: strict 0.85 hi <= r <= 1.15 lo = [1.0625, 1.265], lenient [0.935, 1.4375]
    for r, s, l in ((1.06, False, True), (1.07, True, True), (1.27, False, True), (0.93, False, False), (1.44, False, False)):
        t = E.r4_tests(r, lo, hi)
        assert (t["strict_as_registered"], t["lenient_as_registered"]) == (s, l), r
    assert E.r4_tests(1.1, lo, hi)["bracket"] is False and E.r4_tests(1.25, lo, hi)["bracket"] is True      # lo < r <= hi
    assert E.r4_tests(1.1000001, lo, hi)["bracket"] is True


def test_r4_headline_is_the_conjunction_of_both_orientations_and_never_more_lenient():
    rows = r4_rows(1.014, 1.16)
    assert rows["R4"]["verdict"] == E.PASS and rows["R4-as-registered"]["verdict"] == E.PASS
    assert all(rows[i]["verdict"] == E.PASS for i in ("R4-strict", "R4-lenient"))
    # the LPM test curve here is the LRU shape with only n = 300 raised, so its tail minimum is 0.9975 lambda_miss, which fails
    # |r - 1.175| <= 0.15 x 1.175: R4-mintail FAILS although the n = 300 value passes (the tail minimum matters)
    assert rows["R4-mintail"]["numbers"]["LPM"]["r_pred_min_over_n>=n_star"] == pytest.approx(0.0473 / LAM_MISS)
    assert rows["R4-mintail"]["verdict"] == E.FAIL
    assert rows["R4-bracket"]["verdict"] == E.FAIL                           # r_FCFS = 1.014 lies above the FCFS bracket (0.9, 1.0]
    assert rows["R4"]["numbers"]["FCFS"]["tests"]["bracket"] is False and rows["R4"]["numbers"]["LPM"]["tests"]["bracket"] is True
    # 'r = 1 for every policy': passes the registered transposed reading, FAILS the amended headline (LPM)
    rows = r4_rows(1.0, 1.0)
    assert rows["R4-as-registered"]["verdict"] == E.PASS and rows["R4"]["verdict"] == E.FAIL
    assert rows["R4"]["numbers"]["LPM"]["within_15pct_verbatim_orientation"] is False
    assert rows["R4"]["numbers"]["FCFS"]["within_15pct_verbatim_orientation"] is True
    # over a grid of r_LPM the amended headline passes only where BOTH hold, and only a subset of the registered passes
    for r in np.linspace(0.9, 1.5, 61):
        rr = r4_rows(1.0, float(r))
        if rr["R4"]["verdict"] == E.PASS:
            assert rr["R4-as-registered"]["verdict"] == E.PASS
    # FCFS r = 1.06 is inside the mid band but outside strict (verbatim: <= lo/0.85 = 1.0588): (PASS, FAIL, PASS) as before
    rows = r4_rows(1.06, 1.16)
    assert (rows["R4"]["verdict"], rows["R4-strict"]["verdict"], rows["R4-lenient"]["verdict"]) == (E.PASS, E.FAIL, E.PASS)
    assert rows["R4-strict-as-registered"]["verdict"] == E.FAIL
    rows = r4_rows(1.014, 1.40)
    assert (rows["R4"]["verdict"], rows["R4-strict"]["verdict"], rows["R4-lenient"]["verdict"]) == (E.FAIL, E.FAIL, E.PASS)
    # a missing phase table -> every R4 row NOT_EVALUABLE, including the bootstrap row
    cr = synth_curve_runs(base_curves(), scale_seed=0.0)
    d = yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]
    assert all(r["verdict"] == E.NA for r in E.eval_r4(cr, None, LAM_MISS, d))
    assert len(E.eval_r4(cr, None, LAM_MISS, d)) == 9


def test_r4_mintail_and_bootstrap_rows(design):
    # LRU tail has a dip below mu(300): min over n >= n* is below the n = 300 value
    f = [m if n != 100 else 0.80 * LAM_MISS for n, m in zip(GRID, LRU)]
    f[-1] = 1.014 * LAM_MISS
    cr = synth_curve_runs({("fcfs_lru", 1.0): f, ("lpm_lru", 1.0): [m * 1.1 for m in LRU]}, scale_seed=0.0)
    rows = by_id(E.eval_r4(cr, PHASE, LAM_MISS, design))
    nums = rows["R4"]["numbers"]["FCFS"]
    assert nums["r_pred"] == pytest.approx(1.014) and nums["r_pred_min_over_n>=n_star"] == pytest.approx(0.80)
    assert rows["R4"]["verdict"] in (E.PASS, E.FAIL) and rows["R4-mintail"]["verdict"] == E.FAIL     # 0.80 < 0.826 (verbatim lower bound)
    boot = rows["R4-bootstrap"]["numbers"]
    assert rows["R4-bootstrap"]["verdict"] == E.INFO and 0.0 <= boot["P_headline_pass_both"] <= 1.0 and boot["n_boot"] == B.BOOT_N
    assert boot["FCFS"]["r_interval"]["lo"] <= nums["r_pred"] <= boot["FCFS"]["r_interval"]["hi"]


# =========================================================================== R1 / R2 sensitivity rows
def bumped_runs(bumps=(0.01, 0.01, 0.01)) -> pd.DataFrame:
    """LRU / RANDOM curves where seed j has an extra bump of ``bumps[j]`` at n = 20, 22, 24 respectively (so the per-seed argmax
    differs from seed to seed while the seed-mean argmax is n = 22)."""
    pos = {0: GRID.index(20), 1: GRID.index(22), 2: GRID.index(24)}
    rows = []
    for pol, base in (("fcfs_lru", LRU), ("fcfs_random", RND)):
        for j, sd in enumerate(SEEDS):
            mu = list(base)
            if pol == "fcfs_lru":
                mu[pos[j]] += bumps[j]
            for n, m in zip(GRID, mu):
                rows.append({"policy": pol, "k": 1.0, "n_nominal": n, "n": n, "seed": sd, "mu": m})
    return pd.DataFrame(rows)


def test_near_max_set_per_seed_and_bootstrap_rows(design):
    cr = synth_curve_runs(base_curves())
    rows = by_id(E.eval_r1r2_nearmax(cr, LAM_MISS, design))
    cands = [c["n_star_candidate"] for c in rows["R1-nearmax"]["numbers"]["candidates"]]
    assert cands == [20, 22, 24]                                             # 0.168, 0.170, 0.1694 within 2 SE of 0.170
    assert [c["pass"] for c in rows["R1-nearmax"]["numbers"]["candidates"]] == [False, True, True]       # n* = 20: mu(30) = 1.73
    assert rows["R1-nearmax"]["verdict"] == E.MIXED and rows["R2-nearmax"]["verdict"] == E.PASS
    assert rows["R1-nearmax"]["reading"] == "sensitivity"
    # a single clear maximum: the set is just the argmax
    sharp = [m if n != 22 else 0.30 for n, m in zip(GRID, LRU)]
    cr2 = synth_curve_runs({("fcfs_lru", 1.0): sharp, ("fcfs_random", 1.0): RND})
    assert [c["n_star_candidate"] for c in by_id(E.eval_r1r2_nearmax(cr2, LAM_MISS, design))["R1-nearmax"]["numbers"]["candidates"]] == [22]
    # per-seed argmax: identical shapes -> every seed picks n = 22 and passes
    rows = by_id(E.eval_r1r2_per_seed(cr, LAM_MISS, design))
    assert rows["R1-per-seed"]["verdict"] == E.PASS and rows["R2-per-seed"]["verdict"] == E.PASS
    assert [s["n_star"] for s in rows["R1-per-seed"]["numbers"]["seeds"]] == [22, 22, 22]
    # bumped seeds: the seed-mean argmax is 22 (headline), per-seed argmax = 20 / 22 / 24, R1 is MIXED across seeds
    cr = bumped_runs()
    r1, n_star = E.eval_r1(cr, LAM_MISS, design)
    assert n_star == 22 and r1["verdict"] == E.PASS
    rows = by_id(E.eval_r1r2_per_seed(cr, LAM_MISS, design))
    assert [s["n_star"] for s in rows["R1-per-seed"]["numbers"]["seeds"]] == [20, 22, 24]
    assert rows["R1-per-seed"]["verdict"] == E.MIXED
    rows = by_id(E.eval_r1r2_bootstrap(cr, LAM_MISS, design))
    dist = {int(k): v for k, v in rows["R1-bootstrap"]["numbers"]["n_star_distribution"].items()}      # JSON-safe keys are strings
    assert set(dist) == {20, 22, 24} and sum(dist.values()) == B.BOOT_N
    # R1 fails in exactly the resamples whose argmax is 20: P(R1 pass) = 1 - P(n* = 20)
    assert rows["R1-bootstrap"]["numbers"]["P_R1_pass"] == pytest.approx(1 - dist[20] / B.BOOT_N)
    assert 0.0 < rows["R1-bootstrap"]["numbers"]["P_R1_pass"] < 1.0
    assert rows["R2-bootstrap"]["numbers"]["P_ratio_ge_1.25"] == pytest.approx(1.0)
    assert rows["R1-bootstrap"]["verdict"] == rows["R2-bootstrap"]["verdict"] == E.INFO
    # reproducible
    again = by_id(E.eval_r1r2_bootstrap(cr, LAM_MISS, design))
    assert again["R1-bootstrap"]["numbers"] == rows["R1-bootstrap"]["numbers"]
    # missing cells -> NOT_EVALUABLE
    cr3 = cr[~((cr["policy"] == "fcfs_random") & (cr["n_nominal"] == 26) & (cr["seed"] == 2001))]
    assert all(r["verdict"] == E.NA for r in E.eval_r1r2_nearmax(cr3, LAM_MISS, design) + E.eval_r1r2_bootstrap(cr3, LAM_MISS, design))


# =========================================================================== R3: verdict function, robustness label, envelope, informational cells
SIZES = [10, 20, 30, 40, 50, 60, 80, 100, 150]


def test_r3_verdict_function_and_change_points():
    assert E.r3_verdict(20.0, 40, "found", SIZES)[0] == E.PASS and E.r3_verdict(19.99, 40, "found", SIZES)[0] == E.FAIL
    assert E.r3_verdict(80.0, 40, "found", SIZES)[0] == E.PASS and E.r3_verdict(80.01, 40, "found", SIZES)[0] == E.FAIL
    assert E.r3_verdict(math.inf, 40, "found", SIZES)[0] == E.FAIL and E.r3_verdict(math.nan, 40, "found", SIZES)[0] == E.FAIL
    assert E.r3_verdict(19.0, 10, "left_censored", SIZES)[0] == E.NA and E.r3_verdict(21.0, 10, "left_censored", SIZES)[0] == E.FAIL
    assert E.r3_verdict(74.0, None, "right_censored", SIZES)[0] == E.FAIL and E.r3_verdict(76.0, None, "right_censored", SIZES)[0] == E.NA
    assert E.r3_change_points(40, "found", SIZES) == [20.0, 80.0]
    assert E.r3_change_points(10, "left_censored", SIZES) == [20.0] and E.r3_change_points(None, "right_censored", SIZES) == [75.0]


def test_robustness_label_robust_vs_fragile():
    rng = np.random.default_rng(0)
    knife = rng.uniform(19.0, 21.0, 400)                                     # straddles b_c = 20
    far = rng.uniform(25.0, 28.0, 400)
    # b_emp = 40: PASS iff b_c >= 20 -> the interval [19, 21] holds the change point -> FRAGILE; [25, 28] -> ROBUST (PASS)
    r = E.robustness_label(knife, 40, "found", SIZES, 0.95)
    assert r["label"] == E.FRAGILE and r["verdicts_in_interval"] == [E.FAIL, E.PASS] and 0.0 < r["P_pass"] < 1.0
    r = E.robustness_label(far, 40, "found", SIZES, 0.95)
    assert r["label"] == E.ROBUST and r["verdicts_in_interval"] == [E.PASS] and r["P_pass"] == 1.0
    assert E.robustness_label(knife, 30, "found", SIZES, 0.95)["label"] == E.ROBUST      # band [15, 60] contains [19, 21]
    assert E.robustness_label(knife, 60, "found", SIZES, 0.95)["label"] == E.ROBUST      # band [30, 120]: always FAIL
    assert E.robustness_label(knife, 10, "left_censored", SIZES, 0.95)["label"] == E.FRAGILE    # change point 2 x 10 = 20
    assert E.robustness_label(far, 10, "left_censored", SIZES, 0.95)["label"] == E.ROBUST
    assert E.robustness_label(np.array([70.0, 80.0] * 50), None, "right_censored", SIZES, 0.95)["label"] == E.FRAGILE   # change at 75
    # +inf replicates (monostable resamples) count as FAIL for a found b_emp
    mix = np.concatenate([np.full(30, 20.5), np.full(10, np.inf)])
    r = E.robustness_label(mix, 40, "found", SIZES, 0.95)
    assert r["label"] == E.FRAGILE and r["interval"]["hi"] == math.inf and r["P_pass"] == pytest.approx(0.75)
    assert E.robustness_label(np.full(5, np.nan), 40, "found", SIZES, 0.95)["label"] == E.NA


def test_r3_robustness_row_on_the_synthetic_knife_edge(design):
    # the synthetic LRU curve has b_c = 19.9914 at 2 lambda_miss (n1 = 8.8825, n2 = 28.8739)
    cr = synth_curve_runs(base_curves(), scale_seed=0.01)
    r3 = E.eval_r3(cr, burst_df([0, 0, 0, 3, 4, 5, 5, 5, 5], [0] * 9), LAM_MISS, design)
    assert r3["numbers"]["b_emp"] == 40 and r3["verdict"] == E.FAIL                       # 19.9914 / 40 = 0.49979 < 0.5
    rob = E.eval_r3_robustness(cr, burst_df([0, 0, 0, 3, 4, 5, 5, 5, 5], [0] * 9), LAM_MISS, design)
    assert rob["verdict"] == E.FRAGILE and rob["reading"] == "sensitivity"
    assert rob["numbers"]["headline_verdict"] == E.FAIL and rob["numbers"]["bootstrap"]["interval"]["lo"] < 20.0 < \
        rob["numbers"]["bootstrap"]["interval"]["hi"]
    safe = E.eval_r3_robustness(cr, burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), LAM_MISS, design)       # b_emp = 30: band [15, 60]
    assert safe["verdict"] == E.ROBUST and safe["numbers"]["bootstrap"]["P_pass"] == 1.0
    # the robustness row never touches the headline verdict
    assert E.eval_r3(cr, burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), LAM_MISS, design)["verdict"] == E.PASS
    # NOT_EVALUABLE when the headline is (right-censored with b_c = 20 -> FAIL; left-censored with b_c <= 20 -> NA)
    left = E.eval_r3_robustness(cr, burst_df([4, 5, 5, 5, 5, 5, 5, 5, 5], [0] * 9), LAM_MISS, design)
    assert left["numbers"]["headline_verdict"] == E.NA and left["verdict"] == E.NA
    assert E.eval_r3_robustness(cr, None, LAM_MISS, design)["verdict"] == E.NA


def test_monotone_envelope_function_and_row(design):
    n5 = [5] * 9
    assert E.monotone_envelope_burst(SIZES, [0, 3, 0, 3, 3, 3, 3, 3, 3]) == (40, "found")
    assert E.empirical_critical_burst(SIZES, [0, 3, 0, 3, 3, 3, 3, 3, 3], n5) == (20, "found")        # b_emp ignores the dip at 30
    assert E.monotone_envelope_burst(SIZES, [3] * 9) == (10, "left_censored")
    assert E.monotone_envelope_burst(SIZES, [3, 3, 3, 3, 3, 3, 3, 3, 0]) == (None, "right_censored")
    assert E.monotone_envelope_burst(SIZES, [0] * 9) == (None, "right_censored")
    assert E.monotone_envelope_burst(SIZES, [0, 0, 0, 0, 3, 3, 3, 3, 3]) == (50, "found")
    cr = synth_curve_runs(base_curves(), scale_seed=0.0)
    row = E.eval_r3_envelope(cr, burst_df([0, 3, 0, 3, 3, 3, 3, 3, 3], [0] * 9), LAM_MISS, design)
    assert row["id"] == "R3-envelope" and row["reading"] == "sensitivity"
    assert row["numbers"]["b_env"] == 40 and row["numbers"]["b_emp"] == 20
    assert row["verdict"] == E.FAIL                                           # b_c = 19.9914; 19.9914 / 40 < 0.5
    ok = E.eval_r3_envelope(cr, burst_df([0, 0, 3, 3, 3, 3, 3, 3, 3], [0] * 9), LAM_MISS, design)
    assert ok["numbers"]["b_env"] == 30 and ok["verdict"] == E.PASS            # 19.9914 / 30 = 0.67
    assert E.eval_r3_envelope(cr, None, LAM_MISS, design)["verdict"] == E.NA


def info_runs(cfg_bi: dict, not_recovered: Dict[float, Dict[int, int]], rnd_b0: int = 0, flip=None) -> pd.DataFrame:
    rows = []
    for mult in cfg_bi["lambda_dependence"]["lam_mults"]:
        for b in cfg_bi["lambda_dependence"]["sizes"]:
            for j, sd in enumerate(cfg_bi["seeds"]):
                k = not_recovered.get(mult, {}).get(b, 0)
                rows.append({"policy": "fcfs_lru", "lam_mult": mult, "burst_n": b, "seed": sd, "recovered": j >= k})
    for j, sd in enumerate(cfg_bi["seeds"]):
        rows.append({"policy": "fcfs_random", "lam_mult": 2.0, "burst_n": 0, "seed": sd, "recovered": j >= rnd_b0})
    df = pd.DataFrame(rows)
    if flip:
        m = (df["policy"] == "fcfs_lru") & (df["lam_mult"] == flip[0]) & (df["burst_n"] == flip[1]) & (df["seed"] == flip[2])
        df.loc[m, "recovered"] = ~df.loc[m, "recovered"]
    return df


def test_burst_info_rows_b0_controls_lambda_dependence_and_registered_consistency(cfg, design):
    bi = cfg["burst_info"]
    cr = synth_curve_runs(base_curves(), scale_seed=0.01)
    reg = burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9)
    nr = {1.5: {b: 5 for b in (45, 50, 60, 80, 100, 150)} | {40: 3}, 2.0: {b: 5 for b in (30, 35, 40, 45, 50, 60, 80, 100, 150)},
          2.5: {0: 4, 5: 5} | {b: 5 for b in bi["lambda_dependence"]["sizes"] if b >= 10}}
    # make the lam 2.0 cells consistent with the registered E-burst counts at the shared sizes
    nr[2.0] = {10: 0, 20: 1, 30: 3, 40: 3, 50: 4, 60: 5, 80: 5, 100: 5, 150: 5} | {5: 0, 15: 0, 25: 2, 35: 3, 45: 4}
    runs = info_runs(bi, nr, rnd_b0=1)
    rows = by_id(E.eval_burst_info(cr, runs, reg, LAM_MISS, design, bi))
    b0 = {(c["policy"], c["lam_mult"]): c for c in rows["R3-info-b0"]["numbers"]["no_burst_controls"]}
    assert b0[("fcfs_lru", 2.5)]["n_not_recovered"] == 4 and b0[("fcfs_lru", 2.0)]["n_not_recovered"] == 0
    assert b0[("fcfs_random", 2.0)]["n_not_recovered"] == 1 and all(c["n_runs"] == 5 for c in b0.values())
    per = {p["lam_mult"]: p for p in rows["R3-info-lambda"]["numbers"]["per_lambda"]}
    assert per[1.5]["b_emp"] == 40 and per[2.0]["b_emp"] == 30 and per[2.0]["b_emp_status"] == "found"
    assert per[2.5]["b_emp"] == 0 and per[2.5]["b_emp_status"] == "left_censored" and math.isnan(per[2.5]["b_c_over_b_emp"])
    assert per[1.5]["b_env"] == 40 and per[2.0]["b_env"] == 30 and per[1.5]["fluid"]["kind"] == "bistable"
    assert per[1.5]["fluid"]["b_c"] > per[2.0]["fluid"]["b_c"] > per[2.5]["fluid"]["b_c"]          # b_c decreases with lambda
    assert per[2.0]["b_c_interval"]["lo"] <= per[2.0]["fluid"]["b_c"] <= per[2.0]["b_c_interval"]["hi"]
    assert per[2.0]["within_factor_2"] is True and per[2.5]["within_factor_2"] is None
    chk = rows["R3-info-lambda"]["numbers"]["registered_consistency_check"]
    assert chk["n_compared"] == 9 * 5 and chk["n_mismatch"] == 0                  # lam 2.0, the 9 registered sizes x 5 seeds
    assert rows["R3-info-lambda"]["verdict"] == rows["R3-info-b0"]["verdict"] == E.INFO
    # a flipped run is detected by the determinism check
    bad = E.eval_burst_info(cr, info_runs(bi, nr, flip=(2.0, 30, 2104)), reg, LAM_MISS, design, bi)
    assert by_id(bad)["R3-info-lambda"]["numbers"]["registered_consistency_check"]["n_mismatch"] == 1
    # missing inputs
    assert all(r["verdict"] == E.NA for r in E.eval_burst_info(cr, None, reg, LAM_MISS, design, bi))
    gap = runs[~((runs["policy"] == "fcfs_lru") & (runs["lam_mult"] == 1.5) & (runs["burst_n"] == 40) & (runs["seed"] == 2100))]
    assert E.eval_burst_info(cr, gap, reg, LAM_MISS, design, bi)[1]["verdict"] == E.NA


def posthoc_inputs(cfg_bi: dict, per_seed_fail_from: Dict[int, int], baseline_trapped=(2103,)) -> tuple:
    """(registered E-burst runs, burst_info runs) where seed s is not recovered at every size >= per_seed_fail_from[s] (None = never),
    and the seeds in ``baseline_trapped`` also fail at b = 0 at lam_mult 2.0."""
    rows = []
    for b in SIZES:
        for sd in cfg_bi["seeds"]:
            f = per_seed_fail_from.get(sd)
            rows.append({"policy": "fcfs_lru", "burst_n": b, "seed": sd, "recovered": not (f is not None and b >= f)})
            rows.append({"policy": "fcfs_random", "burst_n": b, "seed": sd, "recovered": True})
    info = []
    for sd in cfg_bi["seeds"]:
        info.append({"policy": "fcfs_lru", "lam_mult": 2.0, "burst_n": 0, "seed": sd, "recovered": sd not in baseline_trapped})
    return pd.DataFrame(rows), pd.DataFrame(info)


def test_posthoc_row_excludes_seeds_trapped_without_a_burst(cfg, design):
    """Amendment 2: the observed pattern of the full runs, rebuilt by hand. Seed 2103 fails at every size (and at b = 0); 2100 fails from
    20, 2102 from 40, 2101 and 2104 from 80. All seeds: counts [1, 2, 2, 3, 3, 3, 5, 5, 5] -> b_emp = 40; without 2103: [0, 1, 1, 2, 2, 2,
    4, 4, 4] -> >= ceil(0.6 x 4) = 3 of 4 first at 80."""
    bi = cfg["burst_info"]
    reg, info = posthoc_inputs(bi, {2100: 20, 2101: 80, 2102: 40, 2103: 10, 2104: 80})
    cr = synth_curve_runs(base_curves(), scale_seed=0.0)
    assert E.eval_r3(cr, reg, LAM_MISS, design)["numbers"]["b_emp"] == 40                      # the headline is untouched by the row
    row = E.eval_r3_posthoc_b0_excluded(cr, reg, info, LAM_MISS, design, bi)
    n = row["numbers"]
    assert row["id"] == "R3-posthoc-b0-excluded" and row["reading"] == "information" and row["verdict"] == E.INFO
    assert n["baseline_trapped_seeds"] == [2103] and n["remaining_seeds"] == [2100, 2101, 2102, 2104]
    assert list(n["not_recovered_by_size_all_seeds"].values()) == [1, 2, 2, 3, 3, 3, 5, 5, 5]
    assert list(n["not_recovered_by_size_excluding_baseline_trapped"].values()) == [0, 1, 1, 2, 2, 2, 4, 4, 4]
    assert n["b_emp_excl"] == 80 and n["b_emp_excl_status"] == "found" and n["min_count_rule"].endswith("3 of 4")
    assert n["b_c_over_b_emp_excl"] == pytest.approx(n["b_c"] / 80) and n["b_c_over_b_emp_excl"] < 0.5
    assert n["first_size_from_which_every_larger_size_is_not_recovered_by_seed"] == {"2100": 20, "2101": 80, "2102": 40, "2103": 10,
                                                                                    "2104": 80}
    assert "POST-HOC" in row["notes"]
    # no baseline-trapped seed: the row reduces to the registered counts
    reg2, info2 = posthoc_inputs(bi, {2100: 20, 2101: 80, 2102: 40, 2103: 10, 2104: 80}, baseline_trapped=())
    n2 = E.eval_r3_posthoc_b0_excluded(cr, reg2, info2, LAM_MISS, design, bi)["numbers"]
    assert n2["baseline_trapped_seeds"] == [] and n2["b_emp_excl"] == 40
    # every seed trapped, or inputs missing -> NOT_EVALUABLE
    _, allinfo = posthoc_inputs(bi, {}, baseline_trapped=tuple(bi["seeds"]))
    assert E.eval_r3_posthoc_b0_excluded(cr, reg, allinfo, LAM_MISS, design, bi)["verdict"] == E.NA
    assert E.eval_r3_posthoc_b0_excluded(cr, reg, None, LAM_MISS, design, bi)["verdict"] == E.NA
    assert E.eval_r3_posthoc_b0_excluded(cr, None, info, LAM_MISS, design, bi)["verdict"] == E.NA


# =========================================================================== R6: null-implied reporting
LMK = {0.5: 0.5 * LAM_MISS, 1.0: LAM_MISS, 2.0: 2.05 * LAM_MISS}


def r6_curves(f05: float, f2: float) -> pd.DataFrame:
    return synth_curve_runs({("fcfs_lru", 1.0): LRU, ("fcfs_lru", 0.5): [m * f05 for m in LRU], ("fcfs_lru", 2.0): [m * f2 for m in LRU]},
                            scale_seed=0.0)


def test_r6_passes_under_the_k_independent_shape_null_and_beyond_null_does_not(design):
    cr = r6_curves(0.5, 2.05)                                                # c(k) = mu*/lambda_miss(k) identical for all k
    head = E.eval_r6(cr, LAMCAP, design, LMK)
    assert head["verdict"] == E.PASS                                         # the registered headline passes under the null
    n = head["numbers"]
    assert n["k=0.5"]["c_mu_star_over_lambda_miss"] == pytest.approx(n["k=1.0"]["c_mu_star_over_lambda_miss"]) == \
        pytest.approx(n["k=2.0"]["c_mu_star_over_lambda_miss"])
    for k in (0.5, 1.0, 2.0):
        assert n[f"k={k}"]["E_excess_ratio"] == pytest.approx(1.0)
        assert n[f"k={k}"]["rho"] == pytest.approx(n[f"k={k}"]["rho_null"])
        assert n[f"k={k}"]["lambda_cap_over_lambda_miss"] == pytest.approx(LAMCAP[k] / LMK[k])
    assert n["k=0.5"]["rho_null"] < n["k=1.0"]["rho_null"] < n["k=2.0"]["rho_null"]       # the null itself is increasing
    rows = by_id(E.eval_r6_extras(cr, LAMCAP, LMK, design))
    assert rows["R6-beyond-null"]["verdict"] == E.FAIL
    assert rows["R6-beyond-null"]["reading"] == "sensitivity" and rows["R6-bootstrap"]["verdict"] == E.INFO
    # headline numbers without lambda_miss(k) are the old ones
    assert "rho_null" not in E.eval_r6(cr, LAMCAP, design)["numbers"]["k=1.0"]


def test_r6_beyond_null_margins(design):
    # c(0.5) = 1.1 c(1), c(2) = 1.8/2.05 c(1) = 0.878 c(1) -> E(0.5) = 0.909 < 1, E(2) = 1.139 >= 1.10
    rows = by_id(E.eval_r6_extras(r6_curves(0.55, 1.8), LAMCAP, LMK, design))
    assert rows["R6-beyond-null"]["verdict"] == E.PASS
    assert rows["R6-beyond-null"]["numbers"]["k=2.0"]["E"] == pytest.approx(2.05 / 1.8) and 1.10 < 2.05 / 1.8
    # c(2) only 5% lower -> E(2) = 1.05 < 1.10
    assert by_id(E.eval_r6_extras(r6_curves(0.55, 1.95), LAMCAP, LMK, design))["R6-beyond-null"]["verdict"] == E.FAIL
    # c(0.5) not higher than c(1) -> FAIL even with a big drop at k = 2
    assert by_id(E.eval_r6_extras(r6_curves(0.5, 1.7), LAMCAP, LMK, design))["R6-beyond-null"]["verdict"] == E.FAIL
    assert E.beyond_null({0.5: 0.99, 1.0: 1.0, 2.0: 1.10}) and not E.beyond_null({0.5: 1.0, 1.0: 1.0, 2.0: 1.2})
    assert not E.beyond_null({0.5: 0.9, 1.0: 1.0, 2.0: 1.0999})
    # missing inputs
    assert all(r["verdict"] == E.NA for r in E.eval_r6_extras(r6_curves(0.5, 2.05), LAMCAP, None, design))
    assert all(r["verdict"] == E.NA for r in E.eval_r6_extras(r6_curves(0.5, 2.05), None, LMK, design))
    assert all(r["verdict"] == E.NA for r in E.eval_r6_extras(r6_curves(0.5, 2.05)[lambda x: x["k"] != 2.0], LAMCAP, LMK, design))


def test_loo_mu_star_removes_the_selection_bias_by_hand():
    M = np.array([[1.0, 1.0, 1.0], [1.3, 0.9, 0.8], [0.9, 1.2, 1.0]])
    assert M.mean(axis=1).max() == pytest.approx(1.0333333)
    assert E.loo_mu_star(M) == pytest.approx((0.9 + 0.9 + 0.8) / 3)           # folds pick g2, g1, g1 and score 0.9, 0.9, 0.8
    flat = np.tile(np.array([[1.0], [2.0], [1.5]]), (1, 3))
    assert E.loo_mu_star(flat) == pytest.approx(2.0)


def test_r6_bootstrap_and_loo_rows_are_consistent(design):
    cr = r6_curves(0.5, 2.05)
    rows = by_id(E.eval_r6_extras(cr, LAMCAP, LMK, design))
    b = rows["R6-bootstrap"]["numbers"]
    for k in (0.5, 1.0, 2.0):
        iv = b[f"k={k}"]["rho"]
        assert iv["lo"] <= LAMCAP[k] / (max(LRU) * {0.5: 0.5, 1.0: 1.0, 2.0: 2.05}[k]) <= iv["hi"] + 1e-12
    # identical seeds' shapes (scale 0): bootstrap has no spread
    assert b["P_rho_strictly_increasing"] in (0.0, 1.0)
    assert rows["R6-loo"]["verdict"] in (E.PASS, E.FAIL) and rows["R6-loo-beyond-null"]["verdict"] == E.FAIL


# =========================================================================== bootstrap table and the complete evaluation
def test_bootstrap_table_covers_the_derived_quantities(design):
    cr = synth_curve_runs(base_curves())
    t = E.bootstrap_table(cr, LAM_MISS, design, LAMCAP, LMK)
    q = set(t["quantity"])
    assert {"n_star", "mu_star_over_lambda_miss", "mu300_over_lambda_miss", "b_c@1.5x", "b_c@2.0x", "b_c@2.5x", "n1@2.0x", "n2@2.0x",
            "R2_ratio_random_over_lru", "rho", "c_mu_star_over_lambda_miss_k", "E_excess_ratio"} <= q
    r = t[(t["quantity"] == "n_star") & (t["policy"] == "fcfs_lru")].iloc[0]
    assert r["estimate"] == 22 and r["lo"] <= 22 <= r["hi"] and r["n_boot"] == B.BOOT_N
    bc = t[(t["quantity"] == "b_c@2.0x")].iloc[0]
    assert bc["estimate"] == pytest.approx(19.9914, abs=0.001) and bc["lo"] <= bc["estimate"] <= bc["hi"]
    # the table is reproducible
    t2 = E.bootstrap_table(cr, LAM_MISS, design, LAMCAP, LMK)
    pd.testing.assert_frame_equal(t, t2)
    # an empty design (no curve cells) gives an empty table, not an error
    assert E.bootstrap_table(cr[cr["policy"] == "none"], LAM_MISS, design).empty


def test_evaluate_all_with_every_input_orders_headlines_first_and_has_unique_ids(cfg, design):
    cr = synth_curve_runs(base_curves())
    reg = burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9)
    runs = info_runs(cfg["burst_info"], {})
    rows = E.evaluate_all(cr, reg, cap_df({}), PHASE, LAMCAP, LAM_MISS, design, lambda_miss_k=LMK, burst_info_runs=runs,
                          burst_info=cfg["burst_info"])
    ids = [r["id"] for r in rows]
    assert ids[:6] == ["R1", "R2", "R3", "R4", "R5", "R6"] and len(set(ids)) == len(ids)
    assert all(r["reading"] == "headline" for r in rows[:6]) and all(r["reading"] != "headline" for r in rows[6:])
    for need in ("R3-posthoc-b0-excluded", "R1-nearmax", "R2-nearmax", "R1-per-seed", "R2-per-seed", "R1-bootstrap", "R2-bootstrap", "R3-robustness",
                 "R3-envelope", "R3-info-b0", "R3-info-lambda", "R4-as-registered", "R4-bracket", "R4-mintail", "R4-bootstrap",
                 "R6-beyond-null", "R6-loo", "R6-bootstrap"):
        assert need in ids, need
    df = E.rows_to_frame(rows)
    for s in df["numbers"]:
        json.loads(s)


# =========================================================================== CLI: burst_info and the report on top of it (quick sizes)
def test_quick_burst_info_and_report_flags(tmp_path):
    cdir = run_cli(tmp_path, "curve", "--quick")
    bdir = run_cli(tmp_path, "burst", "--quick")
    idir = run_cli(tmp_path, "burst_info", "--quick")
    ir = pd.read_csv(idir / "runs.csv")
    assert set(ir["burst_n"]) == {0, 20} and set(ir["policy"]) == {"fcfs_lru", "fcfs_random"} and set(ir["lam_mult"]) == {2.0}
    assert (idir / "burst_info_counts.csv").exists()
    meta = json.loads((idir / "meta.json").read_text())
    assert meta["status"] == "done" and meta["quick"] is True and meta["informational"] is True
    kdir = run_cli(tmp_path, "cap", "--quick")
    rdir = run_cli(tmp_path, "report", "--quick", "--curve-dir", str(cdir), "--burst-dir", str(bdir), "--burst-info-dir", str(idir),
                   "--cap-dir", str(kdir))
    pe = pd.read_csv(rdir / "prediction_eval.csv")
    assert list(pe["id"][:6]) == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert not pe["verdict"].isin(["PASS", "FAIL", "MIXED", "ROBUST", "FRAGILE"]).any()      # quick inputs: every verdict suppressed
    assert pe["claim"][0] == VERBATIM["R1"]
    rmeta = json.loads((rdir / "meta.json").read_text())
    assert any("quick" in f for f in rmeta["flags"]) and "burst_info" in rmeta["inputs"] and rmeta["bootstrap"]["n_boot"] == 2000
    for f in ("table_bootstrap.csv", "table_burst_info_counts.csv", "table_curve.csv"):
        assert (rdir / f).exists(), f
    assert "mu_se_over_lambda_miss" in pd.read_csv(rdir / "table_curve.csv").columns


def test_dirty_inputs_suppress_verdicts_in_the_report(tmp_path):
    cdir = run_cli(tmp_path, "curve", "--quick")
    meta = json.loads((cdir / "meta.json").read_text())
    meta["git"]["dirty"] = True
    meta["quick"] = False
    (cdir / "meta.json").write_text(json.dumps(meta))
    rdir = run_cli(tmp_path, "report", "--quick", "--curve-dir", str(cdir))
    rmeta = json.loads((rdir / "meta.json").read_text())
    assert any("dirty" in f for f in rmeta["flags"])
    pe = pd.read_csv(rdir / "prediction_eval.csv")
    assert not pe["verdict"].isin(["PASS", "FAIL"]).any()


# =========================================================================== the full report on a synthetic COMPLETE design (clean, finished inputs)
def _write_dir(root: Path, name: str, df: Dict[str, pd.DataFrame], meta: dict) -> Path:
    d = root / name
    d.mkdir(parents=True)
    for fname, frame in df.items():
        frame.to_csv(d / fname, index=False)
    (d / "meta.json").write_text(json.dumps(meta))
    return d


def test_report_on_a_synthetic_complete_design_writes_verdicts_figures_and_tables(tmp_path, cfg):
    clean = {"status": "done", "quick": False, "git": {"commit": "abc", "dirty": False}, "n_runs": 1, "start_time": "t"}
    cr = synth_curve_runs({**base_curves(), ("fcfs_lru", 1.0): LRU})
    cr = cr.assign(**{c: 0.5 for c in ("hit_rate", "gpu_busy", "resident_kv_tokens", "reserved_tokens", "idle_tokens",
                                       "evictions_per_s", "turns_per_s", "mu_first_half", "mu_second_half")})
    cr["n"] = (cr["n_nominal"] * cr["k"]).round().astype(int)
    extra = {"tail_hit_rate": 0.5, "tail_backlog_mean": 1.0, "tail_sessions_per_s": 0.1, "tail_gate_mean": 0.0}
    reg = burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9).assign(**extra)
    runs = info_runs(cfg["burst_info"], {2.0: {10: 0, 20: 1, 30: 3, 40: 3, 50: 4, 60: 5, 80: 5, 100: 5, 150: 5}}).assign(**extra)
    cap = cap_df({("random", 32): 3, ("random", 36): 3, ("mru_idle", 40): 2}).assign(**extra)
    cdir = _write_dir(tmp_path / "in", "curve", {"curve_runs.csv": cr, "curve_table.csv": curve_table(cr)}, {**clean, "experiment": "c"})
    bdir = _write_dir(tmp_path / "in", "burst", {"runs.csv": reg}, {**clean, "experiment": "b"})
    idir = _write_dir(tmp_path / "in", "info", {"runs.csv": runs}, {**clean, "experiment": "i"})
    kdir = _write_dir(tmp_path / "in", "cap", {"runs.csv": cap}, {**clean, "experiment": "k"})
    rdir = run_cli(tmp_path, "report", "--curve-dir", str(cdir), "--burst-dir", str(bdir), "--burst-info-dir", str(idir),
                   "--cap-dir", str(kdir))
    pe = pd.read_csv(rdir / "prediction_eval.csv")
    head = dict(zip(pe["id"][:6], pe["verdict"][:6]))
    assert head["R1"] == "PASS" and head["R3"] == "PASS" and head["R5"] == "PASS" and head["R4"] in ("PASS", "FAIL")
    assert head["R6"] in ("PASS", "FAIL")
    sens = dict(zip(pe["id"], pe["verdict"]))
    assert sens["R3-robustness"] in ("ROBUST", "FRAGILE") and sens["R1-nearmax"] == "MIXED" and sens["R3-info-lambda"] == "INFO"
    assert pe["claim"][0] == VERBATIM["R1"]
    rmeta = json.loads((rdir / "meta.json").read_text())
    assert rmeta["flags"] == [] or all("dirty" not in f and "quick" not in f for f in rmeta["flags"])
    for f in ("fig1_mu_curves.pdf", "fig2_fluid_burst.pdf", "fig3_cap_heatmap.pdf", "fig4_k_scaling.pdf", "table_bootstrap.csv",
              "table_burst_info_counts.csv", "table_fluid_bc.csv", "table_cap_cells.csv", "table_burst_counts.csv"):
        assert (rdir / f).exists() and (rdir / f).stat().st_size > 0, f
        if f.endswith(".pdf"):
            assert (rdir / f).read_bytes()[:4] == b"%PDF"
    bt = pd.read_csv(rdir / "table_bootstrap.csv")
    assert {"n_star", "b_c@2.0x", "rho"} <= set(bt["quantity"])
    # amendment 2: table_curve normalises each row by lambda_miss(k) of its own k (the first report used lambda_miss(1) for all k)
    tc = pd.read_csv(rdir / "table_curve.csv")
    lmk_ = {0.5: 0.02456, 1.0: LAM_MISS, 2.0: 0.0910231578947368}
    for k, lam_k in lmk_.items():
        sub = tc[np.isclose(tc["k"], k)]
        assert np.allclose(sub["lambda_miss_k"], lam_k, rtol=1e-6)
        assert np.allclose(sub["mu_over_lambda_miss"], sub["mu_mean"] / lam_k, rtol=1e-6)
    # the same inputs from a dirty tree: every test verdict is suppressed
    meta = json.loads((cdir / "meta.json").read_text())
    meta["git"]["dirty"] = True
    (cdir / "meta.json").write_text(json.dumps(meta))
    rdir2 = run_cli(tmp_path, "report", "--curve-dir", str(cdir), "--burst-dir", str(bdir), "--burst-info-dir", str(idir),
                    "--cap-dir", str(kdir))
    pe2 = pd.read_csv(rdir2 / "prediction_eval.csv")
    assert not pe2["verdict"].isin(["PASS", "FAIL", "MIXED", "ROBUST", "FRAGILE"]).any()
    assert pe2["notes"].str.contains("VERDICT SUPPRESSED").any()
