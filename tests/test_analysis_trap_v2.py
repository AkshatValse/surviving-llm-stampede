"""Throughput-based trap criterion and the paired-arm PASS rule, on synthetic traces (trapped / draining / recovered /
noburst-collapse), plus the burst2 CLI end to end (synthetic run dirs, and the three arms on the mock server)."""
import json

import numpy as np
import pandas as pd
import pytest

from analysis.summarize import main as analysis_main
from analysis.throughput import (backlog_at, backlog_mean, backlog_slope, completion_rates, hit_stats)
from analysis.trap_v2 import (cell_verdicts, config_diff, diagnose, legacy_secondary, pairing_problems, seed_verdict,
                              trap_v2_run)
from conftest import make_raw, run_gen
from helpers_analysis import fake_run, params, req_df
from helpers_trap import (LAM_MISS, MULT, T_B, T_END, scenario_collapse, scenario_draining, scenario_recovered,
                          scenario_trapped, synth_run, write_run_dir)

LAM = LAM_MISS * MULT


def rec_of(arm, scen, seed=0, p=None, **kw):
    run = synth_run(arm=arm, seed=seed, **scen, **kw)
    return trap_v2_run(run, p or params()), run


# ------------------------------------------------------------------------------------------------ the four traces
def test_trapped_run():
    r, _ = rec_of("burst", scenario_trapped())
    assert r["trapped"] and r["state"] == "trapped" and not r["draining"] and not r["recovered"]
    assert r["crit_a"] and r["crit_b"] and r["crit_a_sessions"] and r["crit_a_turns"] and r["estimators_agree"]
    assert r["rate_primary"] == pytest.approx(LAM_MISS, rel=0.10) and abs(r["rate_rel_dev"]) < 0.15
    assert r["backlog_slope"] == pytest.approx(LAM - LAM_MISS, rel=0.25)              # grows at ~ lambda - lambda_miss
    assert r["slope_threshold"] == pytest.approx(0.5 * (LAM - LAM_MISS)) and r["backlog_slope"] > r["slope_threshold"]
    assert r["backlog_end"] > 200 and r["hit_end"] < 0.1 and r["lambda_above_miss"]
    assert r["eval_from"] == T_B + 4500.0 and r["eval_len_s"] == T_END - T_B - 4500.0
    assert r["arm"] == "burst" and r["arm_consistent"]


def test_draining_run_is_not_trapped():
    r, _ = rec_of("burst", scenario_draining())
    assert r["draining"] and r["state"] == "draining" and not r["trapped"] and not r["recovered"]
    assert r["backlog_slope"] == pytest.approx(-0.01, abs=0.004)                      # lambda 0.06 vs service 0.07
    assert not r["crit_a"] and r["rate_primary"] == pytest.approx(0.07, rel=0.1)       # well above lambda_miss
    assert r["backlog_end"] > 20 and r["backlog_slope"] < r["slope_threshold"]
    # the OLD hit-rate rule would call this run trapped (hit rate 0.5 is not < 0.2, so use the hit-bad variant of the slow drain)
    bad = dict(scenario_draining(), hit_fn=lambda t: 0.05)
    run = synth_run(arm="burst", seed=0, **bad)
    p = params("burst.trap_min_s=3000", "burst.hit_eval_from_s=4500")
    v2 = trap_v2_run(run, p)
    old = legacy_secondary(run, p)
    assert old["is_trap"] and old["verdict"] == "trapped"              # D1: low hit rate while draining looks like a trap...
    assert not v2["trapped"] and v2["state"] == "draining"             # ...the throughput criterion tells them apart


def test_recovered_run():
    r, _ = rec_of("burst", scenario_recovered())
    assert r["recovered"] and r["good"] and r["state"] == "recovered" and not r["trapped"]
    assert r["hit_end"] > 0.8 and r["backlog_end"] < 20 and r["backlog_end_inst"] < 20
    assert not r["crit_a"] and r["rate_primary"] == pytest.approx(LAM, rel=0.1)       # serves what arrives


def test_noburst_collapse_is_not_good():
    r, _ = rec_of("noburst", scenario_collapse())
    assert not r["good"] and not r["recovered"]
    assert r["trapped"] and r["state"] == "trapped"                    # the dead-framing signature: collapse without a burst
    assert r["arm"] == "noburst" and r["t_burst"] == T_B               # evaluated over the same window via analysis_t_burst_s
    ok, _ = rec_of("noburst", scenario_recovered())
    assert ok["good"] and not ok["trapped"]


def test_degenerate_lambda_below_lambda_miss_is_never_trapped():
    # lambda = 0.9 * lambda_miss served exactly: the bare formula (a)&(b) would accept it (rate within 15% of lambda_miss,
    # slope ~ 0 > 0.5*(lambda-lambda_miss) < 0); the explicit lambda > lambda_miss condition rejects it
    run = synth_run(arm="noburst", mu_fn=lambda t: 0.5, hit_fn=lambda t: 0.97, lam_override=0.9 * LAM_MISS)
    r = trap_v2_run(run, params())
    assert r["crit_a"] and r["crit_b"] and not r["lambda_above_miss"] and not r["trapped"]
    assert r["recovered"]


def test_window_too_short_is_indeterminate_but_end_state_is_still_reported():
    r, _ = rec_of("burst", scenario_recovered(), t_end=T_B + 4500 + 300)
    assert r["window_too_short"] and r["state"] == "recovered" and r["state_reason"] == "window_too_short"
    r2, _ = rec_of("burst", scenario_trapped(), t_end=T_B + 4500 + 300)
    assert r2["window_too_short"] and r2["state"] == "indeterminate" and not r2["trapped"]


def test_aborted_run_with_a_long_enough_window_is_evaluated_and_flagged():
    run = synth_run(arm="burst", **scenario_trapped())
    run.aborted, run.abort_reason = True, "max_inflight>4000"
    r = trap_v2_run(run, params())
    assert r["trapped"] and r["aborted"] and r["abort_reason"] == "max_inflight>4000"


def test_estimator_choice_decides_criterion_a_and_both_are_reported():
    run = synth_run(arm="burst", **scenario_trapped())
    # remove every last-turn completion in the window: sessions-based rate = 0, turns-based unchanged
    r = run.requests
    in_win = (r["t_complete"] >= T_B + 4500) & (r["turn"] == r["n_turns"])
    run.requests = r[~in_win].copy()
    a = trap_v2_run(run, params())
    b = trap_v2_run(run, params("trap_v2.rate_estimator=turns_based"))
    assert a["rate_sessions"] == 0.0 and a["rate_turns_based"] > 0.03
    assert not a["crit_a_sessions"] and b["crit_a_turns"] and not a["estimators_agree"]
    assert not a["trapped"] and b["trapped"]                          # the key decides the verdict
    assert a["rate_primary"] == a["rate_sessions"] and b["rate_primary"] == b["rate_turns_based"]
    with pytest.raises(ValueError):
        trap_v2_run(run, params("trap_v2.rate_estimator=bogus"))


# ------------------------------------------------------------------------------------------------ primitives
def test_backlog_primitives_by_hand():
    ses = pd.DataFrame({"arrival_s": [0.0, 1.0, 2.0, 3.0], "t_end": [4.0, 5.0, 6.0, 10.0],
                        "status": ["completed", "completed", "failed", "cancelled"]})
    # in system: 1 on [0,1), 2 on [1,2), 3 on [2,3), 4 on [3,4), 3 on [4,5), 2 on [5,6), 1 on [6,inf) (cancelled is never "ended")
    assert [backlog_at(ses, t) for t in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 100)] == [1, 2, 3, 4, 3, 2, 1, 1]
    assert backlog_mean(ses, 0.0, 4.0) == pytest.approx(2.5)
    slope, nb = backlog_slope(ses, 0.0, 4.0, 1.0)
    assert nb == 4 and slope == pytest.approx(1.0)                      # means 1,2,3,4
    assert np.isnan(backlog_slope(ses, 0.0, 2.0, 1.0)[0])               # < 3 bins
    assert backlog_mean(pd.DataFrame(), 0, 1) != backlog_mean(pd.DataFrame(), 0, 1)       # NaN


def test_completion_rates_and_hits_by_hand():
    rows = []
    for s in range(20):                                   # 20 sessions of 15 turns, one turn per 10 s => 300 turns in [0,200)
        for t in range(1, 16):
            rows.append(dict(sid=s, turn=t, n_turns=15, t_send=(s * 15 + t) * 0.6, t_complete=(s * 15 + t) * 0.6 + 0.1,
                             prompt_tokens=1000, cached_tokens=(900 if t >= 2 else 0)))
    run = fake_run(req_df(rows), 200.0, cfg_extra={"workload": {**make_raw()["workload"], "mean_turns": 15, "max_turns": 60}})
    r = completion_rates(run, 0.0, 200.0)
    assert r["n_turns_completed"] == 300 and r["n_sessions_completed"] == 20
    assert r["sessions_per_s"] == pytest.approx(0.1) and r["turns_per_s"] == pytest.approx(1.5)
    assert r["turns_based_per_s"] == pytest.approx(1.5 / r["effective_mean_turns"]) and 14.7 < r["effective_mean_turns"] < 14.8
    h = hit_stats(run, params(), 0.0, 200.0)
    assert h["hit_frac_turns"] == pytest.approx(280 / 300) and h["hit_frac_followup"] == 1.0
    assert h["cached_frac_tokens"] == pytest.approx(280 * 900 / 300000)
    assert hit_stats(run, params(), 500.0, 600.0)["n_turns"] == 0


# ------------------------------------------------------------------------------------------------ pairs and the PASS rule
def triple(seed, burst=None, noburst=None, capped=None, label="sglang-fcfs-r1", **kw):
    """The three arms of one seed; each argument is a scenario dict (None = default) or False (arm missing)."""
    spec = {"burst": burst if burst is not None else scenario_trapped(),
            "noburst": noburst if noburst is not None else scenario_recovered(),
            "capped": capped if capped is not None else scenario_recovered()}
    # all arms of a pair share the burst specification (200 sessions); only the service dynamics differ between scenarios
    return [synth_run(arm=a, seed=seed, label=label, **{**s, "burst_n": 200}, **kw) for a, s in spec.items() if s is not False]


def records(runs, p=None):
    p = p or params()
    return [trap_v2_run(r, p) for r in runs]


def test_seed_verdict_and_pass_rule_two_of_three_seeds():
    p = params()
    runs = triple(0) + triple(1) + triple(2, noburst=scenario_collapse())          # seed 2: no-burst collapses
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert cell["rate_mult"] == MULT and cell["n_seeds_seen"] == 3 and cell["n_pass"] == 2 and cell["meets"]
    assert cell["seeds"]["2"]["noburst_good"] is False and cell["seeds"]["0"]["pass"] and cell["seeds"]["1"]["pass"]
    assert cell["frac_pass"] == pytest.approx(2 / 3) and cell["burst_trapped_frac"] == 1.0
    assert cell["noburst_good_frac"] == pytest.approx(2 / 3) and cell["capped_recovered_frac"] == 1.0
    assert cell["lambda"] == pytest.approx(LAM) and cell["lambda_miss"] == LAM_MISS


def test_pass_rule_fails_with_only_one_seed_passing_and_names_the_reason():
    p = params()
    runs = triple(0) + triple(1, burst=scenario_recovered()) + triple(2, burst=scenario_draining())
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert cell["n_pass"] == 1 and not cell["meets"]
    assert cell["burst_trapped_frac"] == pytest.approx(1 / 3)
    assert diagnose(cell).startswith("FAIL: the burst arm is not trapped")


def test_diagnosis_when_the_noburst_arm_collapses_everywhere():
    p = params()
    runs = sum((triple(s, noburst=scenario_collapse()) for s in range(3)), [])
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert not cell["meets"] and cell["noburst_good_frac"] == 0.0
    assert diagnose(cell).startswith("FAIL: the no-burst arm does not stay good")


def test_diagnosis_when_the_cap_does_not_rescue():
    p = params()
    runs = sum((triple(s, capped=scenario_collapse()) for s in range(3)), [])
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert not cell["meets"] and diagnose(cell).startswith("FAIL: the capped arm does not recover")


def test_missing_arm_counts_as_a_failed_seed_and_is_listed():
    p = params()
    runs = triple(0) + triple(1) + triple(2, capped=False)
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert cell["n_pass"] == 2 and cell["meets"] and cell["incomplete"] == ["2"] and cell["n_seeds_complete"] == 2
    assert cell["seeds"]["2"]["missing_arms"] == ["capped"] and not cell["seeds"]["2"]["pass"]
    runs = triple(0) + triple(1, capped=False) + triple(2, capped=False)
    (cell,) = cell_verdicts(records(runs, p), p.trap_v2)
    assert cell["n_pass"] == 1 and not cell["meets"]


def test_fewer_than_min_seeds_never_passes():
    p = params()
    (cell,) = cell_verdicts(records(triple(0) + triple(1), p), p.trap_v2)
    assert cell["n_pass"] == 2 and not cell["enough_seeds"] and not cell["meets"]
    assert diagnose(cell).startswith("INSUFFICIENT")


def test_cells_are_separated_by_label_and_lambda():
    p = params()
    runs = (triple(0) + triple(1) + triple(2) + triple(0, label="sglang-lpm-r1") + triple(1, label="sglang-lpm-r1")
            + triple(0, mult=1.2) + triple(1, mult=1.2) + triple(2, mult=1.2))
    cells = cell_verdicts(records(runs, p), p.trap_v2)
    keyed = {(c["label"], c["rate_mult"]): c for c in cells}
    assert set(keyed) == {("sglang-fcfs-r1", MULT), ("sglang-lpm-r1", MULT), ("sglang-fcfs-r1", 1.2)}
    assert keyed[("sglang-lpm-r1", MULT)]["n_seeds_seen"] == 2


def test_seed_verdict_handles_each_missing_arm():
    r = lambda **k: {"trapped": False, "good": False, "recovered": False, "state": "x", **k}
    assert seed_verdict({"burst": r(trapped=True), "noburst": r(good=True), "capped": r(recovered=True)})["pass"]
    for drop in ("burst", "noburst", "capped"):
        arms = {"burst": r(trapped=True), "noburst": r(good=True), "capped": r(recovered=True)}
        arms.pop(drop)
        v = seed_verdict(arms)
        assert not v["pass"] and v["missing_arms"] == [drop]


# ------------------------------------------------------------------------------------------------ common random numbers
def test_pairing_checks_catch_non_paired_configs():
    p = params()
    good = triple(0)
    pairs = lambda runs: [(r, run) for r, run in zip(records(runs, p), runs)]
    assert pairing_problems(pairs(good)) == []
    # different workload in one arm
    def edit(raw):
        raw["workload"]["new_prompt_tokens"] = 999
    bad = [good[0], synth_run(arm="noburst", seed=0, cfg_edit=edit, **scenario_recovered()), good[2]]
    probs = pairing_problems(pairs(bad))
    assert any("workload.new_prompt_tokens" in x for x in probs)
    # different seed in the config of one arm
    def edit2(raw):
        raw["run"]["seed"] = 5
    probs = pairing_problems(pairs([good[0], synth_run(arm="noburst", seed=0, cfg_edit=edit2, **scenario_recovered()), good[2]]))
    assert any("run.seed" in x for x in probs)
    # mislabelled arm: meta says capped but there is no gate
    mis = synth_run(arm="burst", seed=0, explicit_arm="capped", **scenario_trapped())
    probs = pairing_problems(pairs([mis, good[1]]))
    assert any("config implies 'burst'" in x for x in probs)
    # capped arm that ran without a gate
    nogate = synth_run(arm="capped", seed=0, n_cap=22, **scenario_recovered())
    nogate.meta["gate_n_cap_resolved"] = None
    nogate_rec = trap_v2_run(nogate, p)
    probs = pairing_problems([(trap_v2_run(good[0], p), good[0]), (nogate_rec, nogate)])
    assert any("without a resolved gate cap" in x for x in probs)
    # duplicate arm
    dup = synth_run(arm="burst", seed=0, tag="-again", **scenario_trapped())
    probs = pairing_problems(pairs(good + [dup]))
    assert any("duplicate burst runs" in x for x in probs)


def test_config_diff_ignores_only_the_keys_that_may_differ_between_arms():
    a, b = {"a": {"x": 1}, "arrivals": {"burst": {"n": 1}}, "gate": {"n_cap": 3}, "meta": {"arm": "burst"}, "output": {"name": "q"}},\
        {"a": {"x": 2}, "arrivals": {"burst": None}, "gate": {"n_cap": None}, "meta": {"arm": "noburst"}, "output": {"name": "r"}}
    assert config_diff(a, b) == ["a.x"]
    assert config_diff({"workload": {"content_salt": 1}}, {"workload": {"content_salt": 2}}) == []
    assert config_diff({"arrivals": {"analysis_t_burst_s": 1.0}}, {"arrivals": {"analysis_t_burst_s": 2.0}}) == ["arrivals.analysis_t_burst_s"]


# ------------------------------------------------------------------------------------------------ CLI on synthetic run dirs
def cli(tmp_path, runs, *extra):
    dirs = [write_run_dir(r, tmp_path / "runs") for r in runs]
    out_root = tmp_path / "an"
    rc = analysis_main(["burst2", "--run-dirs", *map(str, dirs), "--out-root", str(out_root),
                        "--set", "burst.trap_min_s=3000", "--set", "burst.hit_eval_from_s=4500", *extra])   # short protocol
    assert rc == 0
    d = sorted((out_root / "agentload_analysis_burst2").iterdir())[-1]
    return d, json.loads((d / "kill_verdict_v2.json").read_text())


def test_burst2_cli_writes_kill_verdict_v2(tmp_path):
    runs = triple(0) + triple(1) + triple(2, noburst=scenario_collapse())
    d, kv = cli(tmp_path, runs)
    for f in ("kill_verdict_v2.json", "trap_v2_runs.csv", "trap_v2_cells.csv", "backlog_trace.csv", "meta.json", "config.yaml",
              "guards.json", "config_effective.yaml"):
        assert (d / f).exists(), f
    assert kv["schema"] == "kill_verdict_v2" and kv["rule"]["pass_fraction_min"] == pytest.approx(2 / 3)
    (cell,) = kv["cells"]
    assert cell["meets"] and cell["n_pass"] == 2 and cell["diagnosis"].startswith("PASS") and cell["pairing_problems"] == {}
    assert kv["kill_test_pass_rule_only"] is True and kv["kill_test_pass_decisive"] is None      # no pre-registration
    assert kv["pre_registered"] is False and kv["prereg"] == {"provided": False}
    assert kv["pairing_problems"] == {} and kv["skipped_runs"] == [] and kv["guards"]["codes"] == []
    runs_csv = pd.read_csv(d / "trap_v2_runs.csv")
    assert len(runs_csv) == 9 and set(runs_csv["arm"]) == {"burst", "noburst", "capped"}
    assert runs_csv[runs_csv["arm"] == "burst"]["trapped"].all() and runs_csv[runs_csv["arm"] == "capped"]["recovered"].all()
    assert {"legacy_verdict", "legacy_is_trap", "backlog_slope", "rate_sessions", "rate_turns_based"} <= set(runs_csv.columns)
    # the old hit-rate criterion is carried as a secondary column: the BURST arm is a legacy trap too
    assert runs_csv[runs_csv["arm"] == "burst"]["legacy_is_trap"].all()
    assert kv["legacy_secondary_burst_arm"][f"sglang-fcfs-r1|{MULT}"] == {"n_burst_runs": 3, "n_legacy_trap": 3}
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "finished" and meta["git"]["captured_at"] == "run start" and len(meta["inputs"]) == 9
    tr = pd.read_csv(d / "backlog_trace.csv")
    assert {"run_dir", "arm", "t_start", "backlog_mean"} <= set(tr.columns)


def test_burst2_cli_flags_a_broken_pairing_and_does_not_count_it_as_decisive(tmp_path):
    def edit(raw):
        raw["workload"]["decode_tokens"] = 7
    runs = triple(0) + triple(1) + [synth_run(arm="burst", seed=2, **scenario_trapped()),
                                    synth_run(arm="noburst", seed=2, cfg_edit=edit, **scenario_recovered()),
                                    synth_run(arm="capped", seed=2, **{**scenario_recovered(), "burst_n": 200})]
    d, kv = cli(tmp_path, runs)
    assert len(kv["pairing_problems"]) == 1 and "seed" not in str(kv["pairing_problems"]).split("|")[0]
    (cell,) = kv["cells"]
    assert cell["meets"] and not cell["meets_valid_pairing"] and kv["fcfs_cells_meeting_rule"] == []
    assert kv["kill_test_pass_rule_only"] is False


def test_burst2_cli_skips_runs_that_are_not_e2_runs(tmp_path):
    runs = triple(0)
    bad = synth_run(arm="burst", seed=9, **scenario_trapped(), tag="-x")
    bad.meta.pop("resolved_rate_sessions_per_s")
    bad.meta.pop("lambda_ref_resolved")
    bad.cfg["arrivals"]["rate_mult"] = None
    d, kv = cli(tmp_path, runs + [bad])
    assert len(kv["skipped_runs"]) == 1 and "lacks the resolved arrival rate" in kv["skipped_runs"][0]["reason"]


def test_legacy_burst_cli_counts_only_the_burst_arm(tmp_path):
    """`summarize burst` (hit-rate criterion) on a paired set: NOBURST runs are skipped, CAPPED runs do not dilute the table."""
    runs = triple(0) + triple(1) + triple(2)
    dirs = [write_run_dir(r, tmp_path / "runs") for r in runs]
    rc = analysis_main(["burst", "--run-dirs", *map(str, dirs), "--out-root", str(tmp_path / "an"),
                        "--set", "burst.trap_min_s=3000", "--set", "burst.hit_eval_from_s=4500"])
    assert rc == 0
    d = sorted((tmp_path / "an" / "agentload_analysis_burst").iterdir())[-1]
    kv = json.loads((d / "kill_verdict.json").read_text())
    assert len(kv["skipped_no_burst"]) == 3 and kv["arms_in_kill_table"] == ["burst"]
    cells = pd.read_csv(d / "burst_cells.csv")
    assert len(cells) == 1 and cells.iloc[0]["n_runs"] == 3 and cells.iloc[0]["n_trap"] == 3
    br = pd.read_csv(d / "burst_runs.csv")
    assert set(br["arm"]) == {"burst", "capped"} and len(br) == 6


# ------------------------------------------------------------------------------------------------ mock server, three arms
def mock_arm_raw(arm, seed):
    arrivals = {"rate": None, "rate_mult": 1.25, "lambda_ref": 4.0, "analysis_t_burst_s": 1.5,
                "burst": None if arm == "noburst" else {"n": 25, "t_s": 1.5, "width_s": 0.2}}
    return make_raw(arrivals=arrivals, workload={"tool_time_mean_s": 0.15, "mean_turns": 3, "max_turns": 5},
                    run={"duration_s": 5.0, "seed": seed}, meta={"arm": arm, "engine_label": "mock-fcfs"},
                    gate={"n_cap": 4 if arm == "capped" else None})


def test_burst2_end_to_end_on_the_mock_server(tmp_path):
    from agentload.mock_server import MockConfig
    mc = dict(kv_capacity_tokens=10**7, slots=64, fixed_s=0.05, per_uncached_token_s=0, per_completion_token_s=0)
    outs = []
    for seed in (0, 1, 2):
        for i, arm in enumerate(("burst", "noburst", "capped")):
            raw = mock_arm_raw(arm, seed)
            raw["workload"]["content_salt"] = 10 * seed + i + 1
            outs.append(run_gen(raw, MockConfig(**mc), tmp_path / "runs")[0])
    out_root = tmp_path / "an"
    rc = analysis_main(["burst2", "--run-dirs", *[str(o.out_dir) for o in outs], "--out-root", str(out_root),
                        "--set", "trap_v2.eval_from_s=1.5", "--set", "trap_v2.min_eval_s=1", "--set", "trap_v2.slope_dt_s=0.25",
                        "--set", "trap_v2.end_window_s=1.0", "--set", "trap_v2.trace_bin_s=0.5",
                        "--set", "trap_v2.recovered_hit_above=0.5",             # toy workload: E[T]~3, so first turns cap the hit fraction near 0.67
                        "--set", "windows.window_s=1", "--set", "windows.fine_window_s=0.5", "--set", "burst.tail_window_s=2",
                        "--set", "burst.trap_min_s=2", "--set", "burst.hit_eval_from_s=1"])
    assert rc == 0
    d = sorted((out_root / "agentload_analysis_burst2").iterdir())[-1]
    kv = json.loads((d / "kill_verdict_v2.json").read_text())
    assert kv["skipped_runs"] == [] and kv["pairing_problems"] == {}               # real arms are valid CRN pairs
    (cell,) = kv["cells"]
    assert cell["n_seeds_seen"] == 3 and cell["n_seeds_complete"] == 3 and cell["incomplete"] == []
    assert cell["lambda"] == pytest.approx(5.0) and cell["lambda_miss"] == 4.0
    runs = pd.read_csv(d / "trap_v2_runs.csv")
    assert sorted(runs["arm"]) == ["burst"] * 3 + ["capped"] * 3 + ["noburst"] * 3 and runs["arm_consistent"].all()
    assert (runs[runs["arm"] == "capped"]["gate_n_cap"] == 4).all()
    # an uncongested mock never traps; BURST and NOBURST end in the good state. The CAPPED arm may still be draining its gate
    # queue when this 5 s toy run ends (25 burst sessions behind 4 slots): a legitimate "not yet recovered", so not asserted
    assert not runs["trapped"].any()
    assert runs[runs["arm"] != "capped"]["recovered"].all()
    assert (runs[runs["arm"] == "capped"]["backlog_end"] >= runs[runs["arm"] == "burst"]["backlog_end"].min()).all()
    assert not cell["meets"] and diagnose(cell).startswith("FAIL: the burst arm is not trapped")
    guards = json.loads((d / "guards.json").read_text())
    assert "start_state_unverified" in guards["summary"]["codes"]                   # mock runs were not canary-verified
    assert "gate_cap_exceeded" not in guards["summary"]["codes"]
