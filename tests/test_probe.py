"""Tests of the probe runner (src/prefixmeta/probe.py): mu(n) curve, open-loop stability from empty, burst with paired no-burst / client-cap arms.

The probe must only ASSEMBLE runs and call the existing machinery, so the central tests compare its output with direct calls of
``simulate`` / ``point_metrics_r5`` / ``backlog_verdict`` on the same specs (equality, not approximation)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import probe
from prefixmeta.mech_runner import backlog_verdict
from prefixmeta.r4_runner import closed_spec
from prefixmeta.r5_runner import point_metrics_r5
from prefixmeta.sim import simulate

REPO = Path(__file__).resolve().parent.parent
SEP = "separate_prefill_priority"


def write_spec(tmp_path: Path, spec: dict, name: str = "spec.yaml") -> str:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(spec, sort_keys=False))
    return str(p)


def load(tmp_path: Path, spec: dict, sets=None) -> dict:
    return probe.load_probe_config(write_spec(tmp_path, spec), REPO, sets)


SMALL_CURVE = {"policies": ["fcfs_lru"], "n_grid": [6, 12], "seeds": [1], "warmup_s": 1000.0, "horizon_s": 4000.0, "pool_sessions": 3000}


# ============================================================================ configuration
def test_config_chain_defaults_and_early_validation(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP, "alloc_mode": "ratio_reserve", "decode_per_seq_s": 1e-4}})
    assert cfg["engine"]["batching"] == SEP and cfg["engine"]["decode_per_seq_s"] == 1e-4
    assert cfg["engine"]["iter_fixed_s"] == 0.002                                   # from configs/prefix_meta.yaml via the r5 -> base chain
    assert "fcfs_lru" in cfg["policies"] and cfg["metrics"]["track_memory"] is True and cfg["_base_config"] == probe.DEFAULT_BASE
    with pytest.raises(ValueError):                                                   # invalid combination: refused when the spec is loaded
        load(tmp_path, {"engine": {"batching": SEP, "alloc_mode": "ondemand_preempt"}})
    with pytest.raises(TypeError):                                                    # misspelt engine key
        load(tmp_path, {"engine": {"batchin": SEP}})
    cfg2 = load(tmp_path, {"base_config": "configs/prefix_meta.yaml"}, sets=["engine.batching=separate_prefill_priority", "workload.decode_tokens=50"])
    assert cfg2["engine"]["batching"] == SEP and cfg2["workload"]["decode_tokens"] == 50 and "fcfs_lru" not in cfg2["policies"]


def test_sections_merge_defaults_quick_and_reject_unknown_keys(tmp_path):
    cfg = load(tmp_path, {"probe": {"curve": {"n_grid": [3], "quick": {"seeds": [9]}}}})
    full = probe.probe_section(cfg, "curve", quick=False)
    assert full["n_grid"] == [3] and full["seeds"] == [0, 1, 2] and full["horizon_s"] == 35000.0 and "quick" not in full
    q = probe.probe_section(cfg, "curve", quick=True)
    assert q["seeds"] == [9] and q["n_grid"] == [8, 32] and q["horizon_s"] == 4000.0      # user quick > default quick > the section (quick = smoke sizes)
    with pytest.raises(ValueError):
        probe.probe_section(load(tmp_path, {"probe": {"burst": {"burst_size": 3}}}), "burst", False)
    with pytest.raises(ValueError):
        probe.probe_section(cfg, "nope", False)


# ============================================================================ (i) curve
def test_curve_equals_direct_simulation_for_every_cell(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP, "alloc_mode": "ratio_reserve", "prefill_per_token_s": 1e-4}, "probe": {"curve": SMALL_CURVE}})
    sec = probe.probe_section(cfg, "curve", False)
    r = probe.run_curve(cfg, sec)
    assert list(r.runs["n_nominal"]) == [6, 12] and (r.runs["mode"] == f"ratio_reserve|{SEP}").all()
    for _, row in r.runs.iterrows():
        cv = {"horizon_s": 4000.0, "pool_sessions_per_k": 3000}
        rs = closed_spec("fcfs_lru", int(row["n_nominal"]), 1.0, 1, cv, cfg["engine"])
        rs.engine_overrides = {"cache_enabled": True}
        res = simulate(cfg, rs)
        pm = point_metrics_r5(res["windows"], 1000.0, 4000.0, 1000.0)
        for k in ("mu", "hit_rate", "gpu_busy", "reserved_tokens", "idle_tokens", "turns_per_s", "preemptions_per_s", "n_sessions"):
            assert row[k] == pm[k] or (row[k] != row[k] and pm[k] != pm[k]), k
        assert row["run_prefill_busy_frac"] == res["summary"]["prefill_busy_s"] / res["summary"]["sim_end_s"]
    t = r.table.sort_values("n_nominal")
    assert r.nstar == {"fcfs_lru": int(t["n_nominal"].iloc[int(np.argmax(t["mu_mean"].to_numpy()))])}       # first argmax over the grid
    assert set(r.table.columns) >= {"mode", "policy", "n_nominal", "n_seeds", "mu_mean", "mu_sd", "mu_se", "mu_per_seed", "hit_rate_mean"}


def test_curve_cache_disabled_overrides_and_batching_modes(tmp_path):
    base = {"engine": {"alloc_mode": "full_reserve"}, "probe": {"curve": {**SMALL_CURVE, "n_grid": [12]}}}
    cfg = load(tmp_path, base)
    sec = probe.probe_section(cfg, "curve", False)
    mixed = probe.run_curve(cfg, sec).runs.iloc[0]
    assert "run_prefill_busy_frac" not in mixed.index or pd.isna(mixed["run_prefill_busy_frac"])      # no split in mixed mode
    nocache = probe.run_curve(cfg, {**sec, "cache_enabled": False}).runs.iloc[0]
    assert nocache["hit_rate"] == 0.0 and mixed["hit_rate"] > 0.0
    sep = probe.run_curve(cfg, {**sec, "engine": {"batching": SEP}}).runs.iloc[0]                    # section-level engine override
    assert sep["mode"] == f"full_reserve|{SEP}" and mixed["mode"] == "full_reserve|mixed"
    assert 0.0 < sep["run_prefill_busy_frac"] < 1.0 and sep["mu"] != mixed["mu"]
    with pytest.raises(ValueError):                                                                   # section override is validated too
        probe.run_curve(cfg, {**sec, "engine": {"batching": SEP, "alloc_mode": "ondemand_preempt"}})
    with pytest.raises(ValueError):                                                                   # measurement window must be complete windows
        probe.run_curve(cfg, {**sec, "horizon_s": 4500.0})


def test_curve_is_deterministic_and_the_process_pool_gives_the_same_numbers(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP}, "probe": {"curve": {**SMALL_CURVE, "seeds": [1, 2]}}})
    sec = probe.probe_section(cfg, "curve", False)
    a = probe.run_curve(cfg, sec, workers=1).runs.drop(columns=["wall_s"])
    b = probe.run_curve(cfg, sec, workers=1).runs.drop(columns=["wall_s"])
    c = probe.run_curve(cfg, sec, workers=2).runs.drop(columns=["wall_s"])
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(a, c)
    assert len(set(a["mu"])) > 1


# ============================================================================ (ii) open loop
OPEN = {"policy": "fcfs_lru", "lambdas": [0.02, 0.6], "seeds": [0], "horizon_s": 3000.0, "unstable_backlog_stop": 300, "stable_trend_window_s": 1000.0}


def test_open_loop_verdicts_equal_backlog_verdict_and_separate_stable_from_unstable(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP}, "probe": {"open": OPEN}})
    sec = probe.probe_section(cfg, "open", False)
    r = probe.run_open(cfg, sec)
    assert list(r.table["lam"]) == [0.02, 0.6] and list(r.table["stable_all"]) == [True, False]
    lim = probe._limit_cfg(sec)
    for rs, (_, row) in zip(r.specs, r.verdicts.iterrows()):
        direct = backlog_verdict(simulate(cfg, rs), lim)
        for k, v in direct.items():
            assert row[k] == v or (v != v and row[k] != row[k]), k
    hi = r.verdicts.iloc[1]
    assert hi["stopped_early"] == 1 and hi["stop_reason"] == "backlog"                    # overload from empty: early-stopped at the backlog bound
    # lambda given as lambda_miss x multiples
    sec2 = {**sec, "lambdas": None, "lambda_miss": 0.01, "lam_mults": [2.0]}
    r2 = probe.run_open(cfg, sec2)
    assert list(r2.table["lam"]) == [0.02] and list(r2.table["lam_mult"]) == [2.0]
    assert r2.verdicts.iloc[0]["final_backlog"] == r.verdicts.iloc[0]["final_backlog"]    # same lambda, same seed -> same run
    with pytest.raises(ValueError):
        probe.run_open(cfg, {**sec, "lambdas": None})


def test_open_loop_stable_limit_search_brackets_the_edge(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP}})
    sec = {**probe.probe_section(cfg, "open", False), **OPEN, "lambdas": None, "lambda_miss": 0.05,
           "search": {"bracket_mults": [2.0, 4.0, 16.0], "rel_tol": 0.3, "max_bisect_steps": 3}}
    r = probe.run_open(cfg, sec)
    s = r.search
    assert s is not None and r.table.empty and not s["unbounded_in_search"]
    assert 0.05 <= s["lambda_cap"] <= s["bracket_hi"] <= 16 * 0.05 and s["bracket_lo"] == s["lambda_cap"]
    assert s["n_search_runs"] == len(r.specs) >= 3
    rows = pd.DataFrame(s["search_rows"])
    assert rows.loc[rows["lam"] <= s["bracket_lo"], "stable"].all() and not rows.loc[rows["lam"] >= s["bracket_hi"], "stable"].any()


# ============================================================================ (iii) burst with paired arms
BURST = {"policy": "fcfs_lru", "lambda": 0.1, "burst_n": 40, "burst_width_s": 30.0, "warmup_s": 1000.0, "after_s": 3000.0, "cap": 10,
         "seeds": [0, 1], "hit_eval_from_s": 1000.0, "trap_min_s": 2000.0}


def test_burst_arms_are_paired_and_the_client_side_cap_gates(tmp_path):
    cfg = load(tmp_path, {"engine": {"batching": SEP, "alloc_mode": "ratio_reserve"}, "probe": {"burst": BURST}})
    r = probe.run_burst(cfg, probe.probe_section(cfg, "burst", False))
    assert list(r.arms["arm"]) == ["no_burst", "burst", "burst_cap"] and list(r.arms["burst_n"]) == [0, 40, 40] and list(r.arms["cap"]) == [-1, -1, 10]
    assert (r.arms["n_runs"] == 2).all()
    runs = r.runs.set_index(["arm", "seed"])
    for sd in (0, 1):
        # paired: identical Poisson stream; the burst arm has exactly the burst's sessions on top
        assert runs.loc[("burst", sd), "n_arrived"] - runs.loc[("no_burst", sd), "n_arrived"] == 40
        assert runs.loc[("burst_cap", sd), "n_arrived"] == runs.loc[("burst", sd), "n_arrived"]
        capped = runs.loc[("burst_cap", sd)]
        assert capped["max_in_system"] <= 10 and capped["entries_over_cap"] == 0 and capped["max_gate"] > 0
        assert runs.loc[("burst", sd), "max_in_system"] > 10 and runs.loc[("burst", sd), "max_gate"] == 0
    for col in ("recovered", "trapped", "burst_recovered", "burst_outcome", "tail_thrash", "hit_eval", "tail_backlog_mean", "tail_gate_mean"):
        assert col in r.runs.columns, col
    assert r.arms["n_trapped"].between(0, 2).all() and r.arms["n_burst_recovered"].between(0, 2).all()


def test_burst_lambda_forms_and_custom_arms(tmp_path):
    cfg = load(tmp_path, {})
    sec = {**probe.probe_section(cfg, "burst", False), **BURST}
    assert probe.burst_lambda({**sec, "lambda": None, "lambda_miss": 0.05, "lam_mult": 2.0}) == (0.1, 2.0)
    assert probe.burst_lambda(sec)[0] == 0.1
    with pytest.raises(ValueError):
        probe.burst_lambda({**sec, "lambda": None})
    assert list(probe.burst_arms({**sec, "cap": None})) == ["no_burst", "burst"]
    arms = probe.burst_arms({**sec, "arms": {"a": {"burst_n": 5}, "b": {"burst_n": 5, "cap": 7}}})
    assert arms == {"a": {"burst_n": 5, "cap": None}, "b": {"burst_n": 5, "cap": 7}}
    specs = probe.burst_specs(cfg, {**sec, "arms": {"a": {"burst_n": 5}, "b": {"burst_n": 5, "cap": 7}}})
    assert [(s.meta["arm"], s.seed, s.session_cap_override, s.plan.burst_n) for s in specs] == [
        ("a", 0, None, 5), ("a", 1, None, 5), ("b", 0, 7, 5), ("b", 1, 7, 5)]


# ============================================================================ CLI
def test_cli_writes_a_fresh_result_dir_per_call_with_provenance(tmp_path):
    spec = write_spec(tmp_path, {"engine": {"batching": SEP}, "probe": {"curve": {**SMALL_CURVE, "quick": SMALL_CURVE}}})
    out = tmp_path / "res"
    argv = ["curve", "--spec", spec, "--out-root", str(out), "--quick", "--workers", "1", "--tag", "t"]
    assert probe.main(argv, repo_dir=REPO) == 0
    assert probe.main(argv + ["--set", "engine.batching=mixed"], repo_dir=REPO) == 0
    dirs = sorted((out / "prefix_meta_probe_curve_t_quick").iterdir())
    assert len(dirs) == 2                                                              # a new timestamped dir each time, nothing overwritten
    for d in dirs:
        for f in ("config.yaml", "config_effective.yaml", "meta.json", "runs.csv", "windows.csv", "curve_runs.csv", "curve_table.csv"):
            assert (d / f).exists() and (d / f).stat().st_size > 0, f
    metas = [json.loads((d / "meta.json").read_text()) for d in dirs]
    assert [m["status"] for m in metas] == ["done", "done"] and all(m["quick"] and m["seeds"] == [1] for m in metas)
    assert all(len(m["git"]["commit"]) == 40 and "dirty" in m["git"] for m in metas)
    assert {m["engine_effective"]["batching"] for m in metas} == {SEP, "mixed"}       # --set took effect and is recorded
    assert "preregistration.yaml" not in {p.name for d in dirs for p in d.iterdir()}  # a probe is not a registered run
    with pytest.raises(SystemExit):
        probe.main(["curve", "--spec", spec, "--out-root", str(out), "--workers", "7"], repo_dir=REPO)
    with pytest.raises(SystemExit):
        probe.main(["curve", "--spec", spec, "--out-root", str(out), "--workers", "0"], repo_dir=REPO)


def test_cli_open_and_burst_commands_write_their_tables(tmp_path):
    spec = write_spec(tmp_path, {"engine": {"batching": SEP}, "probe": {"open": {**OPEN, "quick": OPEN}, "burst": {**BURST, "quick": BURST}}})
    out = tmp_path / "res"
    assert probe.main(["open", "--spec", spec, "--out-root", str(out), "--workers", "1", "--quick"], repo_dir=REPO) == 0
    assert probe.main(["burst", "--spec", spec, "--out-root", str(out), "--workers", "1", "--quick"], repo_dir=REPO) == 0
    d_open = next((out / "prefix_meta_probe_open_quick").iterdir())
    d_burst = next((out / "prefix_meta_probe_burst_quick").iterdir())
    ot = pd.read_csv(d_open / "open_table.csv")
    assert list(ot["stable_all"]) == [True, False] and (d_open / "open_verdicts.csv").exists()
    ba = pd.read_csv(d_burst / "burst_arms.csv")
    assert list(ba["arm"]) == ["no_burst", "burst", "burst_cap"]
    assert json.loads((d_burst / "meta.json").read_text())["arms"]["burst_cap"] == {"burst_n": 40, "cap": 10}
