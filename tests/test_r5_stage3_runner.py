"""Stage-3 runner tests (amendment 2): the thrash statistics and label, the tail-window columns, the provenance guards (finding F6), the
sensitivity variants, and the report command end to end in a temporary results root."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r5_runner as R
from prefixmeta import report_r5 as RP
from prefixmeta.mech_runner import load_mech_config
from prefixmeta.r5_runner import (add_tail_preemption, apply_variant, check_input_dir, guard_run, main, preemption_stats, thrash_flag)

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "configs" / "prefix_meta_r5.yaml"
THR = {"preemptions_per_turn_above": 0.05, "max_per_turn_above": 10}


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_mech_config(str(CONFIG), REPO)


def win(k, adm=100, pre=0, maxp=0, pf=1000.0, rp=0, dem=0, lost=0):
    return {"window": k, "t_start": 1000.0 * k, "t_end": 1000.0 * (k + 1), "admitted_turns": adm, "preemptions": pre, "preempt_max_turn": maxp,
            "prefill_tok_per_s": pf, "recompute_processed": rp, "recompute_tokens": dem, "lost_prefill": lost}


# ============================================================================ thrash statistics
def test_preemption_stats_and_work_fractions():
    w = [win(0, pre=50, maxp=2), win(1, pre=10, maxp=4, rp=20_000, dem=30_000, lost=5_000), win(2, pre=0, maxp=0, rp=10_000, dem=10_000)]
    st = preemption_stats(w, 1000.0)                                      # windows 1 and 2 only
    assert st["preemptions_per_s"] == pytest.approx(10 / 2000.0) and st["preemptions_per_turn"] == pytest.approx(10 / 200)
    assert st["preempt_max_turn"] == 4
    assert st["recompute_frac"] == pytest.approx(30_000 / 2_000_000)                       # processed recompute / processed prefill
    assert st["readmit_demand_frac"] == pytest.approx(40_000 / 2_000_000)                  # the stage-1 quantity, kept under its own name
    assert st["lost_prefill_frac"] == pytest.approx(5_000 / (2_000_000 + 5_000))
    both = preemption_stats(w, 0.0, 2000.0)                                                # a window set with t_end <= t_to
    assert both["preemptions_per_turn"] == pytest.approx(60 / 200)
    empty = preemption_stats([], 0.0)
    assert np.isnan(empty["preemptions_per_turn"]) and empty["preempt_max_turn"] == 0.0
    # full_reserve windows have none of the columns: everything is zero, never a KeyError
    fr = [{"window": 0, "t_start": 0.0, "t_end": 1000.0, "admitted_turns": 10, "prefill_tok_per_s": 100.0}]
    assert preemption_stats(fr, 0.0)["preemptions_per_turn"] == 0.0 and preemption_stats(fr, 0.0)["recompute_frac"] == 0.0


def test_thrash_flag_boundaries_are_strict_inequalities():
    assert not thrash_flag(0.05, 10, THR) and thrash_flag(0.0501, 0, THR) and thrash_flag(0.0, 11, THR)
    assert not thrash_flag(float("nan"), 10, THR) and thrash_flag(float("nan"), 11, THR)


def test_add_tail_preemption_uses_the_recovery_tail_window():
    runs = pd.DataFrame([{"run_id": 0, "sim_end_s": 10000.0, "tail_s": 5000.0}, {"run_id": 1, "sim_end_s": 10000.0, "tail_s": 5000.0}])
    rows = []
    for rid, per_window in ((0, [(5, 1)] * 5 + [(0, 0)] * 5), (1, [(0, 0)] * 5 + [(30, 12)] * 5)):     # run 0 churned early only, run 1 in the tail
        for k, (pre, mx) in enumerate(per_window):
            rows.append({"run_id": rid, **win(k, pre=pre, maxp=mx)})
    out = add_tail_preemption(runs, pd.DataFrame(rows), THR)
    assert out["tail_preemptions_per_turn"].tolist() == [0.0, pytest.approx(150 / 500)] and out["tail_preempt_max_turn"].tolist() == [0.0, 12.0]
    assert out["tail_thrash"].tolist() == [False, True]


def test_point_metrics_r5_carries_the_thrash_label_and_processed_recompute(cfg):
    from prefixmeta.r4_runner import closed_spec
    from prefixmeta.sim import simulate
    cv = dict(cfg["curve"])
    cv["horizon_s"], cv["warmup_s"] = 4000.0, 1000.0
    rs = closed_spec("fcfs_lru", 200, 1.0, 7300, cv, cfg["engine"])
    rs.engine_overrides = R.mode_overrides(cfg, "ondemand_preempt")
    res = simulate(cfg, rs)
    pm = R.point_metrics_r5(res["windows"], 1000.0, 4000.0, 1000.0, cfg["thrash"])
    assert pm["thrash"] is False and pm["preempt_max_turn"] >= 1 and 0 < pm["recompute_frac"] <= pm["readmit_demand_frac"] + 1e-12
    assert 0 <= pm["lost_prefill_frac"] < 1
    s = res["summary"]
    assert s["max_preempt_per_turn"] >= pm["preempt_max_turn"] and s["recompute_processed_tokens"] <= s["recompute_tokens"]
    strict = R.point_metrics_r5(res["windows"], 1000.0, 4000.0, 1000.0, {"preemptions_per_turn_above": 0.0, "max_per_turn_above": 10})
    assert strict["thrash"] is True                                       # the label responds to the thresholds


# ============================================================================ variants
def test_apply_variant(cfg):
    assert apply_variant(cfg, None) is cfg
    w = apply_variant(cfg, "stage1_whole_victim")
    assert [w["modes"]["engine_overrides"][m]["victim_kv_eviction"] for m in ("ondemand_preempt", "ratio_reserve")] == ["whole", "whole"]
    assert w["modes"]["registered"] == cfg["modes"]["registered"] and w["modes"]["reference"] is None and w["_variant"]["name"] == "stage1_whole_victim"
    assert cfg["modes"]["engine_overrides"]["ondemand_preempt"]["victim_kv_eviction"] == "tail"       # the registered config is untouched
    f = apply_variant(cfg, "ondemand_first_chunk")
    assert f["modes"]["registered"] == ["ondemand_preempt"] and f["modes"]["engine_overrides"]["ondemand_preempt"]["ondemand_admission"] == "first_chunk"
    assert f["modes"]["engine_overrides"]["ratio_reserve"] == cfg["modes"]["engine_overrides"]["ratio_reserve"]
    assert R.all_modes(f) == ["ondemand_preempt"]
    l = apply_variant(cfg, "lpm128")
    assert l["curve"]["policies"] == ["lpm128_lru"] and l["curve"]["n_grid"] == [300] and l["_variant"]["commands"] == ["curve"]
    with pytest.raises(SystemExit):
        apply_variant(cfg, "nope")


def test_variant_cli_writes_to_its_own_directory_and_records_the_variant(tmp_path):
    base = ["--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(tmp_path / "r"), "--variant", "stage1_whole_victim"]
    main(["curve"] + base, repo_dir=REPO)
    d = sorted((tmp_path / "r" / "prefix_meta_r5_curve_stage1_whole_victim_quick").glob("*"))[0]
    meta = json.loads((d / "meta.json").read_text())
    assert meta["variant"] == "stage1_whole_victim" and meta["alloc_mode_overrides"]["ondemand_preempt"]["victim_kv_eviction"] == "whole"
    eff = yaml.safe_load((d / "config_effective.yaml").read_text())
    assert eff["modes"]["reference"] is None and set(pd.read_csv(d / "curve_runs.csv")["mode"]) == {"ondemand_preempt", "ratio_reserve"}
    # lpm128 runs the curve only
    with pytest.raises(SystemExit):
        main(["calib", "--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(tmp_path / "r"), "--variant", "lpm128"], repo_dir=REPO)
    main(["curve", "--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(tmp_path / "r"), "--variant", "lpm128"], repo_dir=REPO)
    d2 = sorted((tmp_path / "r" / "prefix_meta_r5_curve_lpm128_quick").glob("*"))[0]
    cr = pd.read_csv(d2 / "curve_runs.csv")
    assert set(cr["policy"]) == {"lpm128_lru"} and set(cr["mode"]) == {"ondemand_preempt", "ratio_reserve"}


# ============================================================================ provenance guards (finding F6)
def _fake_git(monkeypatch, commit="abc", dirty=False):
    monkeypatch.setattr(R, "git_info", lambda repo_dir: {"commit": commit, "dirty": dirty, "branch": "b"})


def _args(quick=False, sets=()):
    return type("A", (), {"quick": quick, "set": list(sets)})()


def test_registered_runs_refuse_overrides_and_a_dirty_tree(cfg, monkeypatch):
    _fake_git(monkeypatch, dirty=False)
    guard_run(cfg, _args(), REPO)                                                              # clean, no overrides: allowed
    with pytest.raises(SystemExit, match="--set"):
        guard_run(cfg, _args(sets=["engine.kv_memory_tokens=1e6"]), REPO)
    _fake_git(monkeypatch, dirty=True)
    with pytest.raises(SystemExit, match="clean git tree"):
        guard_run(cfg, _args(), REPO)
    guard_run(cfg, _args(quick=True, sets=["x=1"]), REPO)                                      # quick runs are exempt


def _meta_dir(tmp_path, name, **kw):
    d = tmp_path / name
    d.mkdir()
    m = {"experiment": "r5_calib", "status": "done", "quick": False, "git": {"commit": "abc", "dirty": False}, "variant": None, "overrides": [],
         "seeds": [3300, 3301, 3302, 3303, 3304]}
    m.update(kw)
    (d / "meta.json").write_text(json.dumps(m))
    return str(d)


@pytest.mark.parametrize("kw,msg", [
    ({"status": "running"}, "finished"), ({"experiment": "r5_curve"}, "finished"), ({"quick": True}, "quick"),
    ({"git": {"commit": "abc", "dirty": True}}, "dirty"), ({"git": {"commit": "zzz", "dirty": False}}, "current HEAD"),
    ({"variant": "stage1_whole_victim"}, "variant"), ({"overrides": ["engine.x=1"]}, "overrides"), ({"seeds": [7303]}, "registered"),
])
def test_input_dirs_that_cannot_decide_a_registered_result_are_refused(cfg, tmp_path, monkeypatch, kw, msg):
    _fake_git(monkeypatch, commit="abc")
    good = _meta_dir(tmp_path, "good")
    assert check_input_dir(good, "r5_calib", "calibration", cfg, _args(), REPO)["experiment"] == "r5_calib"
    bad = _meta_dir(tmp_path, "bad", **kw)
    with pytest.raises(SystemExit, match=msg):
        check_input_dir(bad, "r5_calib", "calibration", cfg, _args(), REPO)
    with pytest.raises(SystemExit, match="no meta.json"):
        check_input_dir(str(tmp_path / "missing"), "r5_calib", "calibration", cfg, _args(), REPO)


def test_a_quick_run_only_consumes_quick_inputs_and_the_reverse(cfg, tmp_path, monkeypatch):
    _fake_git(monkeypatch, commit="abc")
    quick_dir = _meta_dir(tmp_path, "q", quick=True, seeds=[7303], git={"commit": "old", "dirty": True})
    assert check_input_dir(quick_dir, "r5_calib", "calibration", cfg, _args(quick=True), REPO)["quick"] is True      # quick: no commit / seed checks
    with pytest.raises(SystemExit, match="quick"):
        check_input_dir(quick_dir, "r5_calib", "calibration", cfg, _args(quick=False), REPO)
    reg = _meta_dir(tmp_path, "r")
    with pytest.raises(SystemExit, match="quick"):
        check_input_dir(reg, "r5_calib", "calibration", cfg, _args(quick=True), REPO)


def test_a_variant_run_needs_a_variant_input(cfg, tmp_path, monkeypatch):
    _fake_git(monkeypatch, commit="abc")
    v = apply_variant(cfg, "stage1_whole_victim")
    d = _meta_dir(tmp_path, "v", variant="stage1_whole_victim")
    assert check_input_dir(d, "r5_calib", "calibration", v, _args(), REPO)["variant"] == "stage1_whole_victim"
    with pytest.raises(SystemExit, match="variant"):
        check_input_dir(_meta_dir(tmp_path, "plain"), "r5_calib", "calibration", v, _args(), REPO)


def test_the_registered_cli_refuses_a_dirty_tree_before_running_anything(tmp_path, monkeypatch):
    _fake_git(monkeypatch, dirty=True)
    with pytest.raises(SystemExit, match="clean git tree"):
        main(["calib", "--config", str(CONFIG), "--workers", "1", "--out-root", str(tmp_path / "r")], repo_dir=REPO)
    assert not (tmp_path / "r").exists()
    _fake_git(monkeypatch, dirty=False)
    with pytest.raises(SystemExit, match="--set"):
        main(["curve", "--config", str(CONFIG), "--workers", "1", "--out-root", str(tmp_path / "r"), "--set", "curve.horizon_s=100.0"], repo_dir=REPO)
    assert not (tmp_path / "r").exists()
    good = _meta_dir(tmp_path, "good")                                                           # a valid calib dir, but no --curve-dir
    (Path(good) / "calib_summary.json").write_text(json.dumps({"lambda_miss": {"ondemand_preempt": 0.04, "ratio_reserve": 0.04}}))
    _fake_git(monkeypatch, commit="abc", dirty=False)
    with pytest.raises(SystemExit, match="curve-dir"):
        main(["cap", "--config", str(CONFIG), "--workers", "1", "--out-root", str(tmp_path / "r"), "--calib-dir", good], repo_dir=REPO)


# ============================================================================ report end to end (quick sizes, monkeypatched small design)
def test_report_end_to_end_in_a_temporary_results_root(tmp_path, monkeypatch):
    root = tmp_path / "results"
    sets = ["--set", "curve.quick.n_grid=[8,24,300]", "--set", "curve.quick.seeds=[7300,7301,7302]", "--set", "curve.quick.warmup_s=1000.0",
            "--set", "curve.quick.horizon_s=4000.0", "--set", "curve.quick.pool_sessions_per_k=3000",
            "--set", "calibration.quick.seeds=[7303,7304]", "--set", "calibration.quick.horizon_s=4000.0", "--set", "calibration.quick.pool_sessions=3000",
            "--set", "burst.quick.sizes=[0,50]", "--set", "burst.quick.seeds=[7301,7302]", "--set", "burst.quick.warmup_s=1000.0",
            "--set", "burst.quick.after_s=3000.0", "--set", "cap.quick.seeds=[7302]", "--set", "cap.quick.horizon_s=4000.0"]
    base = ["--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(root)] + sets
    main(["calib"] + base, repo_dir=REPO)
    cal = sorted((root / "prefix_meta_r5_calib_quick").glob("*"))[0]
    main(["curve"] + base, repo_dir=REPO)
    cur = sorted((root / "prefix_meta_r5_curve_quick").glob("*"))[0]
    main(["burst"] + base + ["--calib-dir", str(cal)], repo_dir=REPO)
    bur = sorted((root / "prefix_meta_r5_burst_quick").glob("*"))[0]
    main(["cap"] + base + ["--calib-dir", str(cal), "--curve-dir", str(cur)], repo_dir=REPO)
    cap = sorted((root / "prefix_meta_r5_cap_quick").glob("*"))[0]
    runs_b = pd.read_csv(bur / "runs.csv")
    for c in ("tail_preemptions_per_turn", "tail_preempt_max_turn", "tail_recompute_frac", "tail_lost_prefill_frac", "tail_thrash", "max_preempt_per_turn"):
        assert c in runs_b.columns, c
    assert {"preempt_max_turn", "thrash", "recompute_frac", "readmit_demand_frac", "lost_prefill_frac"} <= set(pd.read_csv(cur / "curve_runs.csv").columns)

    orig = RP.load_design

    def small_design(cfg, repo_dir):
        d = copy.deepcopy(orig(cfg, repo_dir))
        d["curve"]["n_grid"], d["curve"]["seeds"] = [8, 24, 300], [7300, 7301, 7302]
        d["burst"]["sizes"], d["burst"]["seeds"] = [0, 50], [7301, 7302]
        d["cap"]["seeds"] = [7302]
        return d
    monkeypatch.setattr(RP, "load_design", small_design)
    rep_args = ["report", "--config", str(CONFIG), "--quick", "--out-root", str(root), "--calib-dir", str(cal), "--curve-dir", str(cur),
                "--burst-dir", str(bur), "--cap-dir", str(cap)]
    main(rep_args, repo_dir=REPO)
    out = sorted((root / "prefix_meta_r5_quick").glob("*"))[0]
    for f in ("prediction_eval.csv", "prediction_eval.json", "meta.json", "config.yaml", "preregistration.yaml", "table_curve.csv", "table_calib_runs.csv",
              "table_burst_counts.csv", "table_cap_cells.csv", "table_input_provenance.csv", "fig1_mu_curves_three_modes.pdf", "fig2_burst_outcomes.pdf",
              "fig3_preemption_rate_vs_n.pdf"):
        assert (out / f).exists() and (out / f).stat().st_size > 0, f
    pe = pd.read_csv(out / "prediction_eval.csv")
    head = pe[pe["reading"] == "headline"]
    assert set(head["id"]) == {"S1", "S1-KILL", "S2", "S3", "S4", "ANSWER"} and set(head["mode"]) == {"ondemand_preempt", "ratio_reserve"}
    assert (head["verdict"] == "NOT_EVALUABLE").all()                                 # every input is a quick run: all verdicts suppressed
    assert head["notes"].str.contains("VERDICT SUPPRESSED").all() and head["notes"].str.contains("quick run").all()
    assert list(pe["reading"].map({"headline": 0, "clause": 1, "sensitivity": 2, "information": 3})) == sorted(pe["reading"].map(
        {"headline": 0, "clause": 1, "sensitivity": 2, "information": 3}))
    s1 = json.loads(head[(head["id"] == "S1") & (head["mode"] == "ondemand_preempt")]["numbers"].iloc[0])
    assert s1["grid"] == [8, 24, 300] and s1["lambda_m"] > 0
    meta = json.loads((out / "meta.json").read_text())
    assert meta["quick"] is True and set(meta["git"]) >= {"commit", "dirty"} and any("quick run" in f for f in meta["flags"])
    # a missing input is NOT_EVALUABLE, not a crash
    main(["report", "--config", str(CONFIG), "--quick", "--out-root", str(root), "--calib-dir", str(cal), "--curve-dir", str(cur)], repo_dir=REPO)


def test_parse_sens():
    assert RP.parse_sens(["stage1_whole_victim:curve=/a/b", "stage1_whole_victim:calib=/a/c", "lpm128:curve=/d"]) == {
        "stage1_whole_victim": {"curve": "/a/b", "calib": "/a/c"}, "lpm128": {"curve": "/d"}}
    for bad in ("curve=/a", "v:nope=/a", "v:curve"):
        with pytest.raises(SystemExit):
            RP.parse_sens([bad])
