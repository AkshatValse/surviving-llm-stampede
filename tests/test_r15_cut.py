"""r15 CUT cell (analysis/r15_cut.py): the two E2 configs, their registrations and check-job binding, the offline plans against
the committed 1.65 x BURST controls (CRN before the cut, thinning after it), the manipulation check, the per-run measurements on a
committed SHED run (results/nova/toolslow_shed_1716990x_pulled_20261101-154800, cell shed-t600 seed 0) as a fixture, the theory
file loader, the registered verdict, classify end to end, and the six submit lines against the r14 SHED submit line."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import REPO

from agentload.config import load_config, resolve_ramp, resolve_rate
from analysis import basin, prereg, r15_cut
from analysis.load import load_run
from analysis.params import load_params
from analysis.throughput import backlog_slope, backlog_trace, completion_rates, hit_stats

CAL = "prereg/inputs/2026-10-23/calibration.json"
LAM_REF = 0.07153402100919228
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
SHED_CFG = REPO / "configs" / "agentload_e2_shed_t600.yaml"
DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
ARMS = sorted(r15_cut.ARMS)
CTRL_ROOT = REPO / r15_cut.CONTROL_ROOT
SHED_PULL = REPO / "results/nova/toolslow_shed_1716990x_pulled_20261101-154800"
SHED_RUN = SHED_PULL / "results/agentload_e2_burst/20261031-224614"              # shed-t600 seed 0, job 17169908
SHED_CONTROL = CTRL_ROOT / "20261024-153951"                                      # its 1.35 x BURST control (job 17093387)
SHED_R14_ROWS = SHED_PULL / "analysis/agentload_analysis_r14/20261101-154909/r14_runs.csv"
SACCT = REPO / "provenance" / "sacct_cited_jobs_2026-11-01.txt"
GIT = shutil.which("git")

# offline kept counts after the cut, (candidates in [2400.001, 8700), kept): uniform draws are platform-exact
KEPT = {("a115", 0): (775, 539), ("a115", 1): (767, 513), ("a115", 2): (788, 540),
        ("b085", 0): (775, 396), ("b085", 1): (767, 366), ("b085", 2): (788, 390)}
PRE_CUT_SESSIONS = {0: 519, 1: 479, 2: 501}


@pytest.fixture(scope="module")
def params():
    return load_params(REPO / r15_cut.PARAMS, [f"trap_v2.eval_from_s={r15_cut.REGISTERED_EVAL_FROM_S}"])


@pytest.fixture(scope="module")
def endpoints():
    return basin.load_endpoints(REPO / r15_cut.ENDPOINTS)


@pytest.fixture(scope="module")
def controls():
    return r15_cut.control_dirs()


@pytest.fixture(scope="module")
def shed_run():
    return load_run(SHED_RUN)


# ============================================================================================ configs
@pytest.mark.parametrize("arm", ARMS)
def test_cut_config_is_the_shed_config_with_the_cut_ramp(arm):
    c = r15_cut.ARMS[arm]
    a, b = SHED_CFG.read_bytes(), (REPO / c["e2"]).read_bytes()
    assert b"\r" not in b and b.isascii()
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    lam = c["lambda_mult"]
    assert yb["arrivals"]["ramp"] == [[0, 1.65], [2400, 1.65], [2400.001, lam], [8700, lam]]
    assert yb["arrivals"]["ramp"] == r15_cut.ramp_knots_mult(arm)
    assert yb["arrivals"]["kind"] == "ramp" and yb["arrivals"]["ramp_is_mult"] is True and yb["arrivals"]["rate_mult"] == 1.65
    assert yb["arrivals"]["burst"] == {"n": 200, "t_s": 1200, "width_s": 60} and yb["arrivals"]["analysis_t_burst_s"] == 1200
    assert yb["run"]["duration_s"] == 8700
    assert yb["meta"]["notes"].startswith(f"E2 BURST 1.65x + {c['name']}")
    for y in (ya, yb):
        for k in ("ramp", "rate_mult"):
            y["arrivals"].pop(k)
        y["meta"].pop("notes")
    assert ya == yb                                      # nothing else differs from the SHED config
    # line level: every line not in the SHED file is a comment of the arrivals block or one of the three changed lines
    la, lb = a.split(b"\n"), b.split(b"\n")
    added = [x for x in lb if x not in la]
    assert all(x.startswith(b"  #") or x.startswith((b"  ramp: ", b"  rate_mult: ", b"  notes: ")) for x in added)
    assert sum(not x.startswith(b"  #") for x in added) == 3
    comments = b"\n".join(x for x in added if x.startswith(b"  #"))
    for phrase in (b"What it tests", b"CRN", b"before 2400 s", b"thinned subset", b"re-drawn",
                   b"pairing after 2400 s is by the", b"arrival process only"):
        assert phrase in comments


@pytest.mark.parametrize("arm", ARMS)
def test_cut_config_differs_from_the_default_e2_config_only_in_the_arrival_rate_lines(arm):
    ya, yb = yaml.safe_load(DEFAULT_CFG.read_bytes()), yaml.safe_load((REPO / r15_cut.ARMS[arm]["e2"]).read_bytes())
    assert ya["arrivals"]["kind"] == "constant"
    for y in (ya, yb):
        for k in ("kind", "ramp", "ramp_is_mult", "rate_mult"):
            y["arrivals"].pop(k, None)
        y["meta"].pop("notes")
    assert ya == yb


@pytest.mark.parametrize("arm", ARMS)
def test_ramp_problems_pass_for_mults_165_only(arm):
    cfg = yaml.safe_load((REPO / r15_cut.ARMS[arm]["e2"]).read_text())
    assert prereg.ramp_problems(cfg, [1.65]) == []
    assert prereg.ramp_problems(cfg, [1.35]) and prereg.ramp_problems(cfg, [r15_cut.ARMS[arm]["lambda_mult"]])


@pytest.mark.parametrize("arm", ARMS)
def test_candidate_stream_rate_is_the_constant_burst_arms(arm):
    sets = ["arrivals.rate_mult=1.65", f"arrivals.lambda_ref=\"{CAL}:lambda_miss_turns_based\"",
            f"arrivals.uncached_tokens_ref=\"{CAL}:all_miss_uncached_tokens_per_s\"", "arrivals.analysis_t_burst_s=1200",
            "meta.arm=\"burst\"", "run.duration_s=8700", "arrivals.burst.t_s=1200", "run.seed=1"]
    cfg, _ = load_config(REPO / r15_cut.ARMS[arm]["e2"], sets)
    const, _ = load_config(DEFAULT_CFG, sets)
    knots = resolve_ramp(cfg.arrivals, REPO)
    assert cfg.arrivals.kind == "ramp" and cfg.arrivals.burst.n == 200
    assert max(r for _, r in knots) == resolve_rate(const.arrivals, REPO) == 1.65 * LAM_REF        # exact: same S_ARRIVALS draw
    assert [t for t, _ in knots] == [0.0, 2400.0, 2400.001, 8700.0]
    assert knots[-1][1] == r15_cut.ARMS[arm]["lambda_mult"] * LAM_REF


# ============================================================================================ plans and CRN
def test_registered_controls_are_the_165_runs_of_jobs_17093390_to_403(controls):
    assert sorted(controls) == sorted(r15_cut.CONTROL_DIRS)
    for (arm, seed), d in controls.items():
        m = json.loads((d / "meta.json").read_text())
        assert m["arm"] == arm and m["seeds"] == [seed] and m["engine_label"] == "sglang-fcfs-r1"
        assert "arrivals.rate_mult=1.65" in m["argv"] and m["hardware"] == HW
        assert int(m["slurm_env"]["SLURM_JOB_ID"]) == r15_cut.CONTROL_JOBS[(arm, seed)]
    # the registered dirs are the only sglang-fcfs-r1 BURST / NOBURST runs at 1.65 x under the control root
    found = {}
    for d in sorted(CTRL_ROOT.iterdir()):
        if not (d / "meta.json").is_file():
            continue
        r = load_run(d)
        arm = r.arm or r.arm_derived
        if r.label == "sglang-fcfs-r1" and r.rate_mult is not None and math.isclose(r.rate_mult, 1.65) \
                and arm in ("burst", "noburst"):
            assert (arm, r.seed) not in found, f"two {arm} controls of seed {r.seed}"
            found[(arm, r.seed)] = d
    assert found == controls


def test_offline_default_plan_is_the_committed_control_plan(controls):
    """The offline plan builder with the job glue's overrides gives the committed controls' plans (sanity of offline_plan)."""
    for (arm, seed), d in controls.items():
        got = r15_cut.offline_plan(None, seed, cfg_path=DEFAULT_CFG, burst_null=(arm == "noburst"))
        ok, d_arr, d_tool = r15_cut._frames_equal(got, r15_cut.read_plan(d), r15_cut.PLAN_ATOL_S)
        assert ok and d_arr == 0.0 and d_tool < 1e-11, (arm, seed, d_arr, d_tool)


def test_run_settings_replay_the_agentload_cli_order():
    argv = ["python", "-m", "agentload", "run", "--config", "c.yaml", "--name", "agentload_e2_burst", "--out-root", "results",
            "--set", "a.b=1", "--seed", "2", "--set=arrivals.burst.t_s=1200", "--seed=3"]
    # agentload.cli._load: every --set in order, then run.seed (the last --seed wins), output.root, output.name
    assert r15_cut.run_settings(argv) == ["a.b=1", "arrivals.burst.t_s=1200", "run.seed=3", "output.root=results",
                                          "output.name=agentload_e2_burst"]


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("arm", ARMS)
def test_pre_cut_plan_equals_the_committed_burst_control_and_the_thinning_is_sane(arm, seed, controls):
    """The CUT plan built offline from the new config under the control's OWN run settings (its meta.json argv)."""
    plan = r15_cut.plan_under_run_settings(REPO / r15_cut.ARMS[arm]["e2"], controls[("burst", seed)])
    assert r15_cut._frames_equal(plan, r15_cut.offline_plan(arm, seed), 0.0)[0]     # = what the job glue's overrides give
    ctl = r15_cut.read_plan(controls[("burst", seed)])
    pre_p, pre_c = plan[plan["arrival_s"] < 2400], ctl[ctl["arrival_s"] < 2400]
    assert len(pre_p) == len(pre_c) == PRE_CUT_SESSIONS[seed]
    for col in ("sid", "origin", "idx", "n_turns", "arrival_s"):          # arrival times exactly equal
        assert (pre_p[col].to_numpy() == pre_c[col].to_numpy()).all(), col
    # tool totals: numpy's exponential differs in the last bit between Windows and Linux libm (~1e-13 s)
    assert np.max(np.abs(pre_p["tool_time_total_s"].to_numpy() - pre_c["tool_time_total_s"].to_numpy())) < 1e-11
    mc = r15_cut.manipulation_check(plan, ctl, keep_probability=r15_cut.keep_prob(arm), thinned=plan)
    assert mc["mc_pass"], mc["mc_problem"]
    assert mc["mc_pre_cut_equal"] and mc["mc_pre_cut_arrivals_exact"] and mc["mc_post_cut_subset_of_control"]
    assert (mc["mc_candidates"], mc["mc_kept"]) == KEPT[(arm, seed)]
    assert mc["mc_kept"] + mc["mc_shed"] == mc["mc_candidates"] and abs(mc["mc_kept_z"]) < 3
    assert mc["mc_ramp_edge_candidates"] == 0 and mc["mc_burst_sessions"] == 200
    assert (plan["origin"] == "burst").sum() == 200 and plan[plan["origin"] == "burst"]["arrival_s"].between(1200, 1260).all()
    # realized post-cut rate within 15% of lambda'; CUT-A above lambda_miss and CUT-B below it in every seed
    lam_plan, _ = r15_cut.plan_rate(plan, 3000.0, 8700.0)
    lam = r15_cut.ARMS[arm]["lambda_mult"]
    assert abs(lam_plan / LAM_REF / lam - 1) < 0.15
    assert (lam_plan > LAM_REF) == (arm == "a115")


def test_plan_check_table_passes_for_every_arm_and_seed(capsys):
    t = r15_cut.plan_check_table()
    assert len(t) == 6 and t["pass"].all() and t["same_as_job_glue_plan"].all() and t["pre_cut_arrivals_exact"].all()
    assert {(r.arm, r.seed): (r.candidates, r.kept) for r in t.itertuples()} == KEPT
    assert r15_cut.main(["plan-check"]) == 0 and "a115" in capsys.readouterr().out


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cut_b_arrivals_are_a_subset_of_cut_a_arrivals(seed):
    a, b = r15_cut.offline_plan("a115", seed), r15_cut.offline_plan("b085", seed)
    pa, pb = a[a["origin"] == "base"]["arrival_s"], b[b["origin"] == "base"]["arrival_s"]
    assert set(pb) <= set(pa) and len(pb) < len(pa)
    assert (a[a["arrival_s"] < 2400]["arrival_s"].to_numpy() == b[b["arrival_s"] < 2400]["arrival_s"].to_numpy()).all()


def test_manipulation_check_refuses_plans_that_are_not_the_cut(controls):
    ctl = r15_cut.read_plan(controls[("burst", 0)])
    a, b = r15_cut.offline_plan("a115", 0), r15_cut.offline_plan("b085", 0)
    pa = r15_cut.keep_prob("a115")
    assert r15_cut.manipulation_check(a, ctl, keep_probability=pa, thinned=a)["mc_pass"]
    # the CUT-B plan judged as CUT-A: thinned too much, and not CUT-A's thinned plan
    mc = r15_cut.manipulation_check(b, ctl, keep_probability=pa, thinned=a)
    assert not mc["mc_pass"] and not mc["mc_kept_consistent"] and not mc["mc_post_cut_equals_thinned_plan"]
    assert mc["mc_pre_cut_equal"] and mc["mc_post_cut_subset_of_control"]
    # the uncut control as a CUT-A plan: kept fraction 1
    mc = r15_cut.manipulation_check(ctl, ctl, keep_probability=pa)
    assert not mc["mc_pass"] and mc["mc_kept_frac"] == 1.0 and not mc["mc_kept_consistent"]
    # a pre-cut arrival moved by 1 microsecond
    bad = a.copy()
    i = bad.index[(bad["origin"] == "base") & (bad["arrival_s"] < 2400)][10]
    bad.loc[i, "arrival_s"] += 1e-6
    mc = r15_cut.manipulation_check(bad, ctl, keep_probability=pa)
    assert not mc["mc_pass"] and not mc["mc_pre_cut_equal"] and mc["mc_pre_cut_max_abs_d_arrival_s"] > 5e-7
    # no burst
    mc = r15_cut.manipulation_check(a[a["origin"] == "base"], ctl, keep_probability=pa)
    assert not mc["mc_pass"] and not mc["mc_burst_ok"] and not mc["mc_pre_cut_equal"]
    # a post-cut arrival that is not one of the control's candidates
    bad = a.copy()
    j = bad.index[(bad["origin"] == "base") & (bad["arrival_s"] > 5000)][0]
    bad.loc[j, "arrival_s"] += 0.5
    mc = r15_cut.manipulation_check(bad, ctl, keep_probability=pa)
    assert not mc["mc_pass"] and not mc["mc_post_cut_subset_of_control"] and mc["mc_post_cut_not_in_control"] == 1


# ============================================================================================ measurements on the SHED fixture
def test_shed_fixture_plan_is_rebuilt_from_its_own_ramp(shed_run):
    """rebuild_plan (used by the manipulation check) reproduces a committed ramp run's plan.csv from its own effective config
    and recorded ramp knots."""
    got = r15_cut.rebuild_plan(shed_run, shed_run.meta["ramp_knots"])
    ok, d_arr, d_tool = r15_cut._frames_equal(got, r15_cut.read_plan(SHED_RUN), r15_cut.PLAN_ATOL_S)
    assert ok and d_arr == 0.0 and d_tool < 1e-11
    with pytest.raises(ValueError, match="not ramp"):
        r15_cut.rebuild_plan(load_run(SHED_CONTROL), shed_run.meta["ramp_knots"])
    # under a CUT ramp the same run gives another plan (the registered thinned plan is not the SHED plan)
    cut = r15_cut.thinned_plan_of_run(shed_run, "a115")
    assert not r15_cut._frames_equal(cut, got, r15_cut.PLAN_ATOL_S)[0]


def test_manipulation_check_on_the_shed_fixture_against_its_control(shed_run):
    plan, ctl = r15_cut.read_plan(SHED_RUN), r15_cut.read_plan(SHED_CONTROL)
    # with the SHED stop start as "t_cut" the CRN part holds (sessions before 1800 s equal, later arrivals are candidates) ...
    mc = r15_cut.manipulation_check(plan, ctl, keep_probability=r15_cut.keep_prob("a115"), t_cut=1800.0)
    assert mc["mc_pre_cut_equal"] and mc["mc_post_cut_subset_of_control"] and mc["mc_burst_ok"]
    assert not mc["mc_kept_consistent"] and not mc["mc_pass"]            # ... but it is not a 1.15/1.65 thinning
    # the stop removed the arrivals of [1800, 2400): before 2400 s the plans differ
    assert not r15_cut.manipulation_check(plan, ctl, keep_probability=1.0)["mc_pre_cut_equal"]


def test_n_events_end_cancelled_and_unfinished_sessions_at_the_run_end():
    # completed [0, 20), failed [5, 8), cancelled at the end (t_end 8000 > run end), still running (no t_end), completed [30, 35)
    ses = pd.DataFrame({"arrival_s": [0.0, 5.0, 12.0, 15.0, 30.0],
                        "t_end": [20.0, 8.0, 8000.0, np.nan, 35.0],
                        "status": ["completed", "failed", "cancelled", "running", "completed"]})
    t, v = r15_cut.n_events(ses, run_end=40.0)
    at = lambda x: float(v[np.searchsorted(t, x, side="right") - 1]) if np.searchsorted(t, x, side="right") else 0.0  # noqa: E731
    assert [at(x) for x in (0.0, 6.0, 9.0, 13.0, 16.0, 21.0, 26.0, 31.0, 39.9, 40.0)] == [1, 2, 1, 2, 3, 2, 2, 3, 2, 0]
    g = r15_cut.n_grid(ses, run_end=40.0, t_max=40.0, dt=10.0)
    assert list(g["t_start"]) == [0.0, 10.0, 20.0, 30.0]
    # [0,10): 1 on [0,5), 2 on [5,8), 1 on [8,10) -> 1.3;  [10,20): 1 on [10,12), 2 on [12,15), 3 on [15,20) -> 2.3
    # [20,30): 2 -> 2.0;  [30,40): 3 on [30,35), 2 on [35,40) -> 2.5 (the cancelled and the running session stay to 40)
    assert np.allclose(g["n_mean"], [1.3, 2.3, 2.0, 2.5], rtol=0, atol=1e-12)


def test_n_grid_is_the_registered_backlog_on_the_shed_fixture(shed_run):
    g = r15_cut.n_grid(shed_run.sessions, shed_run.t_end_s)
    assert len(g) == 870 and g["t_start"].iloc[-1] == 8690.0
    ref = backlog_trace(shed_run.sessions, 0.0, 8700.0, 10.0)
    assert np.array_equal(g["t_start"].to_numpy(), ref["t_start"].to_numpy())
    assert np.allclose(g["n_mean"].to_numpy(), ref["backlog_mean"].to_numpy(), rtol=0, atol=1e-9)
    s, nb = r15_cut.grid_slope(g, 5700.0, 8700.0)
    bs, nbs = backlog_slope(shed_run.sessions, 5700.0, shed_run.t_end_s, 10.0)       # what trap_v2 registers
    assert nb == nbs == 300 and abs(s - bs) <= 1e-12 * abs(bs)
    r14 = pd.read_csv(SHED_R14_ROWS)
    committed = float(r14[r14["run_dir"].str.endswith("20261031-224614")]["backlog_slope"].iloc[0])
    assert abs(s - committed) < 1e-6                                                  # r14 classified this run with it
    s3, nb3 = r15_cut.grid_slope(g, 3000.0, 8700.0)
    assert nb3 == 570 and math.isfinite(s3)
    assert math.isnan(r15_cut.grid_slope(g[g["t_start"] < 8000], 3000.0, 8700.0)[0])  # a grid that does not cover: NaN


def test_measure_run_on_the_shed_fixture(shed_run, params, endpoints):
    m = r15_cut.measure_run(shed_run, params, endpoints)
    ses = shed_run.sessions
    n = int(((ses["status"] == "completed") & (ses["t_end"] >= 1800) & (ses["t_end"] < 2400)).sum())
    assert m["n_completed_1800_2400"] == n and m["completion_rate_1800_2400"] == n / 600.0
    assert m["completion_rate_1800_2400"] == completion_rates(shed_run, 1800.0, 2400.0)["sessions_per_s"]
    assert m["completion_rate_5700_8700"] == completion_rates(shed_run, 5700.0, 8700.0)["sessions_per_s"]
    plan = r15_cut.read_plan(SHED_RUN)
    k = int(((plan["origin"] == "base") & (plan["arrival_s"] >= 3000) & (plan["arrival_s"] < 8700)).sum())
    assert m["lambda_plan_3000_8700"] == k / 5700.0
    assert m["naive_slope_3000_8700"] == m["lambda_plan_3000_8700"] - m["completion_rate_1800_2400"]
    assert m["lambda_ref"] == LAM_REF and m["lambda_plan_mult"] == pytest.approx(k / 5700.0 / LAM_REF)
    # B1 endpoints exactly as basin.classify_run gives them; the SHED t600 seed 0 run is STUCK (r14 classification)
    b = basin.classify_run(shed_run, params, endpoints)
    for key in ("basin_state", "stuck", "good", "hit_eval", "backlog_slope", "slope_threshold", "state"):
        assert m[key] == b[key], key
    r14 = pd.read_csv(SHED_R14_ROWS)
    row = r14[r14["run_dir"].str.endswith("20261031-224614")].iloc[0]
    assert m["basin_state"] == row["basin_state"] == "stuck" and m["hit_eval"] == pytest.approx(row["hit_eval"], abs=1e-6)
    h = hit_stats(shed_run, params, 5700.0, shed_run.t_end_s + 1e-9)
    assert m["hit_followup_eval"] == h["hit_frac_followup"] and m["hit_turns_eval"] == m["hit_eval"]
    assert m["window_matches_endpoints"] and m["slope_5700_8700"] == pytest.approx(m["backlog_slope"], rel=1e-12)
    # post-cut minimum over the bins at or after 2400 s
    g = m["_grid"]
    post = g[g["t_start"] >= 2400]
    assert m["n_post_cut_min"] == post["n_mean"].min() and m["t_post_cut_min_s"] >= 2400
    assert m["n_pre_cut"] == float(g[g["t_start"] == 2390.0]["n_mean"].iloc[0])
    assert m["post_cut_dip_rel"] == pytest.approx(1 - m["n_post_cut_min"] / m["n_pre_cut"])


def test_ramp_checks_on_the_shed_fixture(shed_run):
    assert not r15_cut.ramp_is_registered(shed_run, "a115")
    assert r15_cut.ramp_flat_over_window(shed_run, 2400.001, 8700.0)
    assert not r15_cut.ramp_flat_over_window(shed_run, 1000.0, 8700.0)


# ============================================================================================ registrations
@pytest.mark.parametrize("arm", ARMS)
def test_registration_is_reproduced_by_fill_and_differs_from_the_parent_only_where_allowed(arm, params):
    c = r15_cut.ARMS[arm]
    path = REPO / c["out"]
    pr = r15_cut.fill_registration(arm)
    assert r15_cut.dump_registration(pr) == path.read_bytes()
    reg = yaml.safe_load(path.read_text())
    res = r15_cut.registration_diff(yaml.safe_load(PARENT.read_text()), reg)
    assert res["forbidden"] == []
    assert sorted(res["allowed"]) == sorted(r15_cut.ALLOWED)
    assert res["derived"] == ["predicted_boundaries.capped_drain.predicted_drain_s_by_mult.1.35"]
    assert reg["status"] == "FILLED" and reg["inputs"]["engine_cell_label"] == c["label"]
    assert reg["inputs"]["e2_config"] == c["e2"] and reg["protocol"]["arms"] == ["burst"]
    sha = hashlib.sha256((REPO / c["e2"]).read_bytes()).hexdigest()
    assert reg["protocol"]["e2_config_sha256"] == sha == prereg.config_text_sha256(REPO / c["e2"])
    assert reg["lambda_selection"]["lambda_mults"] == [1.65] and reg["lambda_selection"]["seeds"] == [0, 1, 2]
    assert reg["measured"]["hardware"] == HW and reg["measured"]["lambda_ref"] == LAM_REF
    assert [x for x in prereg.validate(reg, params) if x["severity"] == "error"] == []
    rule = reg["lambda_selection"]["rule"]
    assert rule == r15_cut.rule_text(arm) and r15_cut.decision_rule(arm) in rule
    for phrase in ("BLINDNESS", r15_cut.THEORY_TAG, "MANIPULATION CHECK", "NAIVE comparator", "[2400.001,", "1800, 2400",
                   "3000, 8700", c["label"], "jobs 17093387-17093404", "17093390", "17093396", "17093402"):
        assert phrase in rule, phrase
    for phrase in ("RULE HISTORY", "UNSTUCK", "D_trap(seed)", f"seed 0 {r15_cut.NAIVE_D_TRAP[0]:.6f}"):
        assert phrase in rule, phrase
    assert ("the slope of N over [5700, 8700) s is > 0 in >= 2 of the 3" in rule) == (arm == "a115")
    assert ("the slope of N over [3000, 8700) s is < 0 in >= 2 of the 3" in rule) == (arm == "b085")
    assert ("QUASI-STATIC comparator" in rule) == (arm == "a115")
    assert b"\r" not in path.read_bytes()


def _check_job(arm, params, *, label=None, mults=(1.65,), arms=("burst",), e2=None, hw=HW):
    c = r15_cut.ARMS[arm]
    reg = REPO / c["out"]
    e2 = REPO / (e2 or c["e2"])
    cfg = yaml.safe_load(e2.read_text())
    cfg["run"]["duration_s"], cfg["arrivals"]["analysis_t_burst_s"] = 8700, 1200
    return prereg.check_job(prereg.load_prereg(reg), prereg.file_provenance(reg), params, label=label or c["label"],
                            mults=list(mults), calibration=json.loads((REPO / CAL).read_text()), hardware=hw, e2_cfg=cfg,
                            fcfs_substr="fcfs", arms=list(arms), calibration_path=REPO / CAL, allow_uncommitted=True,
                            e2_cfg_sha256=hashlib.sha256(e2.read_bytes()).hexdigest())


@pytest.mark.parametrize("arm", ARMS)
def test_check_job_authorises_exactly_the_registered_job(arm, params):
    other = "b085" if arm == "a115" else "a115"
    assert _check_job(arm, params) == []
    assert any("MULTS entry 1.35" in x for x in _check_job(arm, params, mults=(1.35,)))
    assert any("not in the registered protocol.arms" in x for x in _check_job(arm, params, arms=("noburst",)))
    assert any("ENGINE_LABEL" in x for x in _check_job(arm, params, label=r15_cut.ARMS[other]["label"]))
    assert any("sha256" in x for x in _check_job(arm, params, e2=r15_cut.ARMS[other]["e2"]))
    assert any("hardware" in x for x in _check_job(arm, params, hw="NVIDIA H200, 143771 MiB"))


def test_a_committed_shed_run_is_not_bound_to_a_cut_registration(shed_run):
    reg = REPO / r15_cut.ARMS["a115"]["out"]
    bl = prereg.run_blockers(prereg.load_prereg(reg), prereg.file_provenance(reg), shed_run)
    assert any("label" in x for x in bl) and any("rate_mult" in x for x in bl) and any("config.yaml sha256" in x for x in bl)


# ============================================================================================ theory predictions file
def test_theory_loader_formats(tmp_path):
    p = r15_cut.parse_theory_slopes
    assert p({"cut-a115": {0: 0.004, 1: 0.003, 2: 0.005}, "cut-b085": {"0": -0.01, "1": -0.011, "2": -0.009}})["slopes"] == \
        {"a115": {0: 0.004, 1: 0.003, 2: 0.005}, "b085": {0: -0.01, 1: -0.011, 2: -0.009}}
    got = p({"CUT-A": 0.002, "sglang-fcfs-r1-cut-b085": {0: {"slope_3000_8700": -0.02}}, "source": "x", "units": "sessions/s"})
    assert got["slopes"] == {"a115": {0: 0.002, 1: 0.002, 2: 0.002}, "b085": {0: -0.02}}
    assert sorted(got["ignored_keys"]) == ["source", "units"]
    w = p({"meta": {"tag": "icml-cut-pred"}, "slope_3000_8700": {"a115": {1: 0.1}, "cut_b085": {1: -0.1}, "note": "x"}})
    assert w["slopes"] == {"a115": {1: 0.1}, "b085": {1: -0.1}} and w["wrapper_key"] == "slope_3000_8700"
    assert w["ignored_keys"] == ["meta", "slope_3000_8700.note"]
    for bad, msg in (({"x": 1}, "name no CUT arm"), ({"a115": {0: "fast"}}, "finite number"), ({"a115": {"s0": 1.0}}, "seed key"),
                     ({"a115": 1.0, "cut-a115": 2.0}, "twice"), ({"a115": {0: float("nan")}}, "finite number"),
                     ({"a115": {0: {"slope": 1.0}}}, "slope_3000_8700"), ([1, 2], "mapping")):
        with pytest.raises(ValueError, match=msg):
            p(bad)
    f = tmp_path / "pred.json"
    f.write_text(json.dumps({"cut-a115": {"0": 0.001}, "cut-b085": {"0": -0.002}}))
    t = r15_cut.load_theory_slopes(f)
    assert t["slopes"] == {"a115": {0: 0.001}, "b085": {0: -0.002}}
    assert t["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    y = tmp_path / "pred.yaml"
    y.write_text("cut-a115:\n  0: 0.001\ncut-b085:\n  0: -0.002\n")
    assert r15_cut.load_theory_slopes(y)["slopes"] == t["slopes"]
    with pytest.raises(ValueError, match="exactly one"):
        r15_cut.load_theory_slopes(f, git_ref="x:y")


@pytest.mark.skipif(GIT is None, reason="git not available")
def test_theory_loader_reads_a_tagged_file_from_git(tmp_path):
    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    g("init", "-q")
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    g("config", "commit.gpgsign", "false")
    (tmp_path / "pred").mkdir()
    (tmp_path / "pred" / "cut.yaml").write_text("cut-a115: {0: 0.003}\ncut-b085: {0: -0.004}\n")
    g("add", "pred/cut.yaml")
    g("commit", "-q", "-m", "pred")
    g("tag", "icml-cut-pred")
    (tmp_path / "pred" / "cut.yaml").write_text("cut-a115: {0: 9.0}\ncut-b085: {0: 9.0}\n")      # an edit after the tag
    t = r15_cut.load_theory_slopes(git_ref="icml-cut-pred:pred/cut.yaml", repo=tmp_path)
    assert t["slopes"] == {"a115": {0: 0.003}, "b085": {0: -0.004}}
    assert len(t["git_commit"]) == 40 and t["git_commit_unix"] > 1.7e9 and t["git_ref"] == "icml-cut-pred"
    with pytest.raises(ValueError, match="git show"):
        r15_cut.load_theory_slopes(git_ref="icml-cut-pred:pred/missing.yaml", repo=tmp_path)


def test_theory_loader_reads_the_icml_cut_pred_layout():
    """The layout analysis/theory/icml/cut_predict.py froze at icml-cut-pred: arms.<CUT-A|CUT-B>.seeds.<seed>.w3000.theory_slope
    (w3000 = [3000, 8700) s); the arm-level fluid slope and the w5700 window are not S_theory (made-up numbers here)."""
    seed = lambda x: {"w3000": {"lam_plan": 0.08, "theory_slope": x, "naive_expected": -9.0}, "w5700": {"theory_slope": 99.0}}  # noqa: E731
    obj = {"tag": "icml-cut-pred", "lambda_ref": 0.07, "noise": {"w3000": {"sd": 1.0}},
           "arms": {"CUT-A": {"mult_after": 1.15, "fluid": {"slope": {"w3000": 42.0}}, "seeds": {"0": seed(0.1), "1": seed(0.2),
                                                                                                  "2": seed(0.3)}},
                    "CUT-B": {"mult_after": 0.85, "seeds": {"0": seed(-0.1), "2": seed(-0.3)}}}}
    got = r15_cut.parse_theory_slopes(obj)
    assert got["slopes"] == {"a115": {0: 0.1, 1: 0.2, 2: 0.3}, "b085": {0: -0.1, 2: -0.3}}
    assert got["wrapper_key"] == r15_cut.ICML_SLOPE_PATH and sorted(got["ignored_keys"]) == ["lambda_ref", "noise", "tag"]
    bad = json.loads(json.dumps(obj))
    del bad["arms"]["CUT-B"]["seeds"]["2"]["w3000"]["theory_slope"]
    with pytest.raises(ValueError, match="no w3000.theory_slope"):
        r15_cut.parse_theory_slopes(bad)
    bad = json.loads(json.dumps(obj))
    bad["arms"]["CUT-A"]["seeds"]["1"]["w3000"]["theory_slope"] = float("nan")
    with pytest.raises(ValueError, match="finite number"):
        r15_cut.parse_theory_slopes(bad)


THEORY_FILE = "results/theory/icml/cut_predictions.json"


@pytest.mark.skipif(GIT is None or subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/tags/icml-cut-pred"], cwd=REPO,
                                                 capture_output=True).returncode != 0, reason="tag icml-cut-pred not available")
def test_the_frozen_theory_file_at_icml_cut_pred_is_readable():
    """classify --theory-git icml-cut-pred:results/theory/icml/cut_predictions.json works: every registered arm and seed has a
    finite slope (structure only; no predicted value is asserted or printed here)."""
    t = r15_cut.load_theory_slopes(git_ref=f"{r15_cut.THEORY_TAG}:{THEORY_FILE}")
    assert {a: sorted(v) for a, v in t["slopes"].items()} == {"a115": [0, 1, 2], "b085": [0, 1, 2]}
    assert all(math.isfinite(x) for v in t["slopes"].values() for x in v.values())
    assert t["wrapper_key"] == r15_cut.ICML_SLOPE_PATH and len(t["git_commit"]) == 40


# ============================================================================================ verdict
def test_seed_call():
    c, N, Q = r15_cut.seed_call, r15_cut.NAIVE, r15_cut.QS
    assert c(0.010, 0.008, {N: -0.03}) == r15_cut.THEORY
    assert c(-0.020, 0.008, {N: -0.03}) == r15_cut.NAIVE
    assert c(0.0, 0.01, {N: -0.01}) == r15_cut.TIE
    assert c(0.012, 0.004, {N: -0.03, Q: 0.014}) == r15_cut.QS                   # the quasi-static comparator is closer
    assert c(0.006, 0.004, {N: -0.03, Q: 0.014}) == r15_cut.THEORY
    assert c(0.006, 0.004, {N: -0.03}, stuck=False) == r15_cut.UNSTUCK           # a run that left the trap: against the theory
    assert c(float("nan"), 0.01, {N: -0.01}) == r15_cut.UNDEFINED and c(0.01, 0.01, {N: None}) == r15_cut.UNDEFINED
    assert c(0.01, 0.01, {}) == r15_cut.UNDEFINED and c(0.01, 0.01, {N: -0.01}, stuck=None) == r15_cut.UNDEFINED
    assert c(0.01, None, {N: -0.01}) == r15_cut.NO_THEORY and c(0.01, float("nan"), {N: -0.01}) == r15_cut.NO_THEORY


def test_naive_d_trap_is_each_controls_trapped_throughput(controls):
    """The frozen D_trap(seed) of the naive comparator is the uncut 1.65 x BURST control's lambda_plan - S over [3000, 8700)."""
    for s in r15_cut.SEEDS:
        r = load_run(controls[("burst", s)])
        grid = r15_cut.n_grid(r.sessions, float(r.t_end_s))
        slope, _ = r15_cut.grid_slope(grid, *r15_cut.SLOPE_WINDOW_S)
        lam, _ = r15_cut.plan_rate(r15_cut.read_plan(r.dir), *r15_cut.SLOPE_WINDOW_S)
        assert lam - slope == pytest.approx(r15_cut.NAIVE_D_TRAP[s], rel=1e-12, abs=1e-15)
        assert 1.3 < r15_cut.NAIVE_D_TRAP[s] / LAM_REF < 1.45                   # above lambda_ref: the youth premium


def test_comparators():
    row = {"seed": 1, "lambda_plan_3000_8700": 0.08, "lambda_ref": LAM_REF}
    a = r15_cut.comparators("a115", row)
    assert a[r15_cut.NAIVE] == pytest.approx(0.08 - r15_cut.NAIVE_D_TRAP[1]) and a[r15_cut.QS] == pytest.approx(0.08 - LAM_REF)
    b = r15_cut.comparators("b085", row)
    assert set(b) == {r15_cut.NAIVE}                                              # CUT-B: naive only


def _row(arm, seed, slope, naive=-0.03, qs=0.05, late=None, stuck=True, counted=True):
    lam = naive + r15_cut.NAIVE_D_TRAP[seed]                                      # so that S_naive = naive, S_qs = qs
    return {"role": "new", "arm": arm, "seed": seed, "counted": counted, "slope_3000_8700": slope,
            "slope_5700_8700": slope if late is None else late, "lambda_plan_3000_8700": lam, "lambda_ref": lam - qs,
            "stuck": stuck, "naive_slope_3000_8700": -0.1, "run_dir": f"r/{arm}/{seed}"}


TH_A = {0: 0.008, 1: 0.008, 2: 0.008}
TH_B = {0: -0.010, 1: -0.010, 2: -0.010}


@pytest.mark.parametrize("rows, theory, arm, want", [
    # CUT-A: theory-favoured and the late slope positive in 3 / 3
    ([_row("a115", s, 0.007) for s in (0, 1, 2)], TH_A, "a115", "PASS"),
    # CUT-A: theory-favoured in 3 / 3 but the late slope > 0 in 1 / 3 -> not PASS, not FAIL
    ([_row("a115", 0, 0.007), _row("a115", 1, 0.007, late=-0.002), _row("a115", 2, 0.007, late=-0.001)], TH_A, "a115",
     "MIXED"),
    # CUT-A: the sign clause uses [5700, 8700), not S: S < 0 but the late slope > 0 in 2 / 3 still passes
    ([_row("a115", 0, -0.001, late=0.004), _row("a115", 1, 0.002, late=0.003), _row("a115", 2, 0.007, late=-0.001)], TH_A,
     "a115", "PASS"),
    # CUT-A: naive-favoured in 2 / 3
    ([_row("a115", 0, -0.028), _row("a115", 1, -0.025), _row("a115", 2, 0.007)], TH_A, "a115", "FAIL"),
    # CUT-A: quasi-static-favoured in 2 / 3
    ([_row("a115", 0, 0.045), _row("a115", 1, 0.047), _row("a115", 2, 0.007)], TH_A, "a115", "FAIL"),
    # CUT-A: two runs left the trap
    ([_row("a115", 0, 0.007, stuck=False), _row("a115", 1, 0.007, stuck=False), _row("a115", 2, 0.007)], TH_A, "a115",
     "FAIL"),
    # CUT-A: one naive, one quasi-static, one theory: against the theory 2 / 3 together
    ([_row("a115", 0, -0.028), _row("a115", 1, 0.047), _row("a115", 2, 0.007)], TH_A, "a115", "FAIL"),
    # CUT-B: theory-favoured in 2 / 3 and S < 0 in 3 / 3
    ([_row("b085", 0, -0.011), _row("b085", 1, -0.012), _row("b085", 2, -0.029)], TH_B, "b085", "PASS"),
    # CUT-B: closer to the theory than to the naive comparator, but the backlog grows: the sign clause blocks PASS
    ([_row("b085", s, 0.001, naive=-0.06) for s in (0, 1, 2)], TH_B, "b085", "MIXED"),
    # CUT-B: no quasi-static comparator (a slope at S_qs is still theory-favoured when nearer the theory than the naive)
    ([_row("b085", s, -0.011, qs=-0.011) for s in (0, 1, 2)], TH_B, "b085", "PASS"),
    # one each: theory, naive, an exact tie (|0 - 0.008| == |0 + 0.008|)
    ([_row("a115", 0, 0.007), _row("a115", 1, -0.028), _row("a115", 2, 0.0, naive=-0.008)], TH_A, "a115", "MIXED"),
    # seeds missing, nothing decided yet
    ([_row("a115", 0, 0.007)], TH_A, "a115", "PENDING"),
    # PASS (and FAIL) are reached early: the missing seed cannot undo them
    ([_row("a115", 0, 0.007), _row("a115", 1, 0.009)], TH_A, "a115", "PASS"),
    ([_row("b085", 0, -0.031), _row("b085", 2, -0.028)], TH_B, "b085", "FAIL"),
    # a resubmitted seed must not vote twice
    ([_row("a115", 0, 0.007), _row("a115", 0, 0.006), _row("a115", 1, 0.007)], TH_A, "a115", "UNDECIDED"),
    # a run that does not count does not vote (2 counted theory-favoured, 1 uncounted naive-favoured)
    ([_row("a115", 0, 0.007), _row("a115", 1, 0.007), _row("a115", 2, -0.03, counted=False)], TH_A, "a115", "PASS"),
    # all seeds present, only one counted: neither PASS nor FAIL, final
    ([_row("a115", 0, 0.007), _row("a115", 1, -0.03, counted=False), _row("a115", 2, -0.03, counted=False)], TH_A, "a115",
     "MIXED"),
    # no theory slopes for the arm
    ([_row("a115", s, 0.007) for s in (0, 1, 2)], None, "a115", "NO-THEORY"),
    # theory for one seed only: the other seeds are NO-THEORY calls, so 1 / 3 theory-favoured
    ([_row("a115", s, 0.007) for s in (0, 1, 2)], {0: 0.008}, "a115", "MIXED"),
])
def test_arm_verdict(rows, theory, arm, want):
    v = r15_cut.arm_verdict(arm, rows, theory)
    assert v["verdict"] == want, v
    assert v["rule"] == r15_cut.decision_rule(arm)


def test_arm_verdict_per_seed_detail():
    v = r15_cut.arm_verdict("a115", [_row("a115", 0, 0.007), _row("a115", 1, -0.028), _row("b085", 2, 0.5)], TH_A)
    s0, s1, s2 = (v["per_seed"][str(s)] for s in (0, 1, 2))
    assert s0["call"] == r15_cut.THEORY and s0["abs_err_theory"] == pytest.approx(0.001) and s0["sign_ok"]
    assert s0["naive_slope"] == pytest.approx(-0.03) and s0["qs_slope"] == pytest.approx(0.05)
    assert s1["call"] == r15_cut.NAIVE and not s1["sign_ok"]
    assert s2["call"] == r15_cut.NOT_COUNTED and not s2["run_present"]           # the b085 row belongs to the other arm
    assert v["missing_seeds"] == [2] and v["verdict"] == "PENDING"
    both = r15_cut.verdict([_row("a115", s, 0.007) for s in (0, 1, 2)], {"a115": TH_A})
    assert both["a115"]["verdict"] == "PASS" and both["b085"]["verdict"] == "NO-THEORY"


# ============================================================================================ classify end to end
def _fake_cut_run(tmp_path, arm, seed, controls):
    """A CUT-labelled run dir assembled from the seed's 1.65 x BURST control (its sessions and requests) with the offline CUT
    plan and a CUT config / meta: exercises classify's plumbing (the measurements are the control's, not a CUT run's)."""
    src = controls[("burst", seed)]
    d = tmp_path / f"cut_{arm}_{seed}"
    d.mkdir()
    for f in ("sessions.csv", "requests.csv", "config.yaml"):
        shutil.copyfile(src / f, d / f)
    c = r15_cut.ARMS[arm]
    meta = json.loads((src / "meta.json").read_text())
    meta.update(engine_label=c["label"], resolved_rate_sessions_per_s=None,
                ramp_knots=[[t, m * LAM_REF] for t, m in r15_cut.ramp_knots_mult(arm)])
    (d / "meta.json").write_text(json.dumps(meta))
    cfg = yaml.safe_load((src / "config_effective.yaml").read_text())
    cfg["arrivals"].update(kind="ramp", ramp_is_mult=True, ramp=r15_cut.ramp_knots_mult(arm))
    cfg["meta"]["engine_label"] = c["label"]
    (d / "config_effective.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    r15_cut.offline_plan(arm, seed).to_csv(d / "plan.csv", index=False)
    return d


def test_classify_end_to_end(tmp_path, controls, params, endpoints):
    d = _fake_cut_run(tmp_path, "a115", 0, controls)
    theory = r15_cut.parse_theory_slopes({"cut-a115": {0: 0.02, 1: 0.02, 2: 0.02}, "cut-b085": {0: -0.01}})
    res = r15_cut.classify([d], endpoints, params, theory=theory)
    new = [r for r in res["rows"] if r["role"] == "new"]
    assert len(new) == 1 and len([r for r in res["rows"] if r["role"].startswith("control_")]) == 6
    r = new[0]
    assert r["arm"] == "a115" and r["mc_pass"] and r["ramp_registered"] and r["ramp_flat_over_slope_window"]
    assert r["mc_post_cut_equals_thinned_plan"] and r["counted"] is False
    assert r["problem"] == "binding not checked: no --prereg for this label"
    ctl = [x for x in res["rows"] if x["role"] == "control_burst" and x["seed"] == 0][0]
    assert r["slope_3000_8700"] == ctl["slope_3000_8700"]                        # the fake run carries the control's sessions
    assert r["naive_slope_3000_8700"] != ctl["naive_slope_3000_8700"]            # but its own (thinned) plan rate
    assert res["verdict"]["a115"]["verdict"] == "PENDING" and res["verdict"]["a115"]["per_seed"]["0"]["run_present"]
    assert set(res["grid"]["role"]) == {"new", "control_burst", "control_noburst"} and len(res["grid"]) == 7 * 870
    assert res["endpoint_problems"] == [] and res["theory"]["slopes"]["a115"] == {"0": 0.02, "1": 0.02, "2": 0.02}
    # with the registration: not bound (the fake run was not made under it), so still not counted
    res2 = r15_cut.classify([d], endpoints, params, preregs=[REPO / r15_cut.ARMS["a115"]["out"]], include_controls=False)
    r2 = res2["rows"][0]
    assert r2["prereg_bound"] is False and "not bound to its registration" in r2["problem"] and not r2["counted"]
    # a run whose plan is the uncut control's fails the manipulation check
    shutil.copyfile(controls[("burst", 0)] / "plan.csv", d / "plan.csv")
    r3 = r15_cut.classify([d], endpoints, params, include_controls=False)["rows"][0]
    assert not r3["mc_pass"] and "manipulation check failed" in r3["problem"]


def test_classify_does_not_count_a_run_that_did_not_complete(tmp_path, controls, params, endpoints):
    """'completed (not aborted)': a client that raised or was killed leaves meta status 'failed' / 'running' and no outcome
    (so no abort_reason); such a run must not take its seed's vote (review fix)."""
    d = _fake_cut_run(tmp_path, "b085", 1, controls)
    ok = r15_cut.classify([d], endpoints, params, include_controls=False)["rows"][0]
    assert ok["run_status"] == "finished" and ok["run_end_s"] > 8700 and "not completed" not in ok["problem"]
    meta = json.loads((d / "meta.json").read_text())
    meta["status"] = "failed"
    meta.pop("outcome")
    (d / "meta.json").write_text(json.dumps(meta))
    req = pd.read_csv(d / "requests.csv")
    req[req["t_complete"] < 5000].to_csv(d / "requests.csv", index=False)
    ses = pd.read_csv(d / "sessions.csv")
    ses.loc[ses["t_end"] > 5000, ["t_end", "status"]] = [5000.0, "cancelled"]
    ses[ses["arrival_s"] < 5000].to_csv(d / "sessions.csv", index=False)
    r = r15_cut.classify([d], endpoints, params, include_controls=False)["rows"][0]
    assert "measurement failed" not in r["problem"] and r["aborted"] is False and r["counted"] is False
    assert "not completed: meta status 'failed'" in r["problem"] and "before 8700 s" in r["problem"]
    assert math.isnan(r["slope_3000_8700"])


def test_classify_cli_writes_its_outputs(tmp_path, controls):
    d = _fake_cut_run(tmp_path, "b085", 1, controls)
    th = tmp_path / "pred.yaml"
    th.write_text("cut-a115: {0: 0.01, 1: 0.01, 2: 0.01}\ncut-b085: {0: -0.01, 1: -0.01, 2: -0.01}\n")
    out = tmp_path / "out"
    assert r15_cut.main(["classify", "--run-dirs", str(d), "--prereg", "--theory", str(th), "--out-root", str(out)]) == 0
    od = next((out / "agentload_analysis_r15_cut").iterdir())
    runs = pd.read_csv(od / "cut_runs.csv")
    assert len(runs) == 7 and runs[runs["role"] == "new"]["arm"].tolist() == ["b085"]
    v = json.loads((od / "cut_verdict.json").read_text())
    assert v["verdict"]["b085"]["verdict"] == "PENDING" and v["theory"]["sha256"] == hashlib.sha256(th.read_bytes()).hexdigest()
    assert v["rules"]["a115"] == r15_cut.decision_rule("a115")
    assert len(pd.read_csv(od / "cut_n_grid.csv")) == 7 * 870 and (od / "meta.json").is_file()


# ============================================================================================ submit lines
def test_the_r14_shed_submit_line_is_the_committed_provenance_one():
    rows = [ln.split("|") for ln in SACCT.read_text().splitlines()]
    hit = [r for r in rows if r[0] == "17169908"]
    assert len(hit) == 1 and hit[0][-1] == r15_cut.R14_SHED_SUBMIT_LINE


def test_sbatch_lines_change_only_the_allowed_fields():
    lines = r15_cut.sbatch_lines()
    assert len(lines) == 7 and lines[0].startswith(f"cd {r15_cut.CLONE_DIR} ") and r15_cut.REG_TAG in lines[0]
    o14, e14, s14 = r15_cut.parse_submit_line(r15_cut.R14_SHED_SUBMIT_LINE)
    seen = []
    for ln in lines[1:]:
        o, e, s = r15_cut.parse_submit_line(ln)
        assert s == s14 == "slurm/sglang_job.sbatch" and [k for k, _ in o] == [k for k, _ in o14]
        od, ed = dict(o), dict(e)
        assert [k for k, _ in e] == [k for k, _ in e14]
        assert {k for k in od if od[k] != dict(o14)[k]} == {"--mem", "--job-name"}
        assert od["--mem"] == "20G" and od["--time"] == "03:10:00" and od["--account"] == "f2026.coms.6250.02"
        assert od["--partition"] == "instruction" and od["--qos"] == "instruction"
        changed = {k for k in ed if ed[k] != dict(e14)[k]}
        assert changed <= {"MULTS", "SEEDS", "E2_CONFIG", "PREREG_FILE", "ENGINE_LABEL"}
        assert changed >= {"MULTS", "E2_CONFIG", "PREREG_FILE", "ENGINE_LABEL"}
        arm = r15_cut.LABEL_TO_ARM[ed["ENGINE_LABEL"]]
        c = r15_cut.ARMS[arm]
        assert ed["MULTS"] == "1.65" and ed["E2_CONFIG"] == c["e2"] and ed["PREREG_FILE"] == c["out"]
        assert od["--job-name"] == c["job_name"] and ed["ARMS"] == "burst" and ed["MODE"] == "burst"
        for k in ("E2_CONFIG", "PREREG_FILE", "CALIB_FILE"):
            assert (REPO / ed[k]).is_file(), ed[k]
        reg = yaml.safe_load((REPO / ed["PREREG_FILE"]).read_text())
        assert reg["inputs"]["engine_cell_label"] == ed["ENGINE_LABEL"] and reg["inputs"]["e2_config"] == ed["E2_CONFIG"]
        assert prereg.ramp_problems(yaml.safe_load((REPO / ed["E2_CONFIG"]).read_text()), [float(ed["MULTS"])]) == []
        seen.append((arm, int(ed["SEEDS"])))
    assert seen == [(a, s) for a in r15_cut.ARMS for s in (0, 1, 2)]
