"""Tests for the round-2 experiment layer: workload variants, survival statistics, system-size scaling, config
resolution, result-directory provenance, classification helpers and the prediction evaluator."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from scipy import stats

from prefixmeta import mech_runner as MR
from prefixmeta import prereg_eval as PE
from prefixmeta.engine import EngineParams
from prefixmeta.sim import RunSpec, build_engine, deep_update, simulate
from prefixmeta import report_r3 as RP
from prefixmeta.metrics import first_good_window, trailing_low_hit_onset
from prefixmeta.survival import (exponential_mle, kaplan_meier, km_median, km_median_ci, km_restricted_mean,
                                 km_survival_at, slopes_log_mean_vs_k, summarize_escape)
from prefixmeta.workload import (ArrivalPlan, WorkloadParams, bimodal_p_hi, build_specs, length_biased_mean_context,
                                 length_biased_session_cap, tool_times)

REPO = Path(__file__).resolve().parent.parent
CFG_PATH = REPO / "configs" / "prefix_meta_mech.yaml"
PREREG_PATH = REPO / "configs" / "prefix_meta_mech_prereg.yaml"


@pytest.fixture(scope="module")
def cfg() -> dict:
    return MR.load_mech_config(str(CFG_PATH), REPO)


# ----------------------------------------------------------------------------- configs
def test_research_question_is_the_first_key_of_the_new_configs():
    for p in (CFG_PATH, PREREG_PATH):
        d = yaml.safe_load(p.read_text())
        assert list(d)[0] == "research_question" and len(d["research_question"]) > 40


def test_prereg_contains_verbatim_predictions_and_hypotheses():
    d = yaml.safe_load(PREREG_PATH.read_text())["preregistration"]
    assert list(d["predictions"]) == [f"P{i}" for i in range(1, 9)] and list(d["hypotheses"]) == ["H1", "H2", "H3", "H4"]
    assert "recovers (3/3) at lambda <= 0.9 lambda_miss and fails (0/3) at lambda >= 1.1 lambda_miss" in d["predictions"]["P1"]
    assert "trapped by burst 200 in >= 4/5 seeds at 2x" in d["predictions"]["P2"]
    assert "CAP at 1.3 x N_lb fails (0/3 at 2x)" in d["predictions"]["P4"]
    assert "burst trap of FCFS in >= 4/5 seeds hold for >= 5 of the workload variants" in d["predictions"]["P8"]
    assert "amendment_1" in d and "amendment_2" in d


def test_mech_config_merges_over_base_and_every_policy_resolves(cfg):
    assert cfg["engine"]["kv_memory_tokens"] == 300000 and "fcfs_cap_lb" in cfg["policies"]   # inherited
    assert cfg["metrics"]["track_memory"] is True and cfg["metrics"]["window_s"] == 1000.0     # merged, not replaced
    exp_cap = {"lb_cap": 28, "cap_1p3": 36, "aimd_cap": 28, "concur_cap": 28}
    for name in cfg["policies"]:
        eng, rec, cap = build_engine(cfg, RunSpec(exp="t", policy=name, seed=0, horizon_s=10.0,
                                                  plan=ArrivalPlan(kind="constant", horizon_s=10.0, rate=0.05)))
        if name in exp_cap:
            assert cap == exp_cap[name], name
        spec = cfg["policies"][name]
        assert eng.mech.ttl_s == spec.get("ttl_pin_s") and eng.mech.protect_queued == spec.get("protect_queued")
    assert set(cfg["mech"]["policies"]) <= set(cfg["policies"])
    assert set(cfg["mech"]["limit"]["policies"]) <= set(cfg["policies"])


def test_quick_blocks_deep_merge_and_keep_required_keys(cfg):
    for name in ("phase", "mech", "escape", "escape_inwindow", "robust"):
        full, quick = MR.exp_cfg_deep(cfg, name, False), MR.exp_cfg_deep(cfg, name, True)
        assert "quick" not in full and "quick" not in quick
        assert set(full) == set(quick), name
    q = MR.exp_cfg_deep(cfg, "mech", True)
    assert q["cold"]["cold_sessions"] == 300 and q["cold"]["seeds"] == [0]            # nested merge, not replace
    assert MR.exp_cfg_deep(cfg, "mech", False)["burst"]["burst_sessions"] == 200


# ----------------------------------------------------------------------------- workload variants
def test_bimodal_tool_times_support_mean_and_probability():
    assert bimodal_p_hi(5.0, 0.3, 20.0) == pytest.approx(4.7 / 19.7)
    x = tool_times(np.random.default_rng(3), 400_000, "bimodal", 5.0, 1.5, 0.3, 20.0)
    assert set(np.unique(x)) == {0.3, 20.0}
    assert x.mean() == pytest.approx(5.0, rel=0.01) and (x == 20.0).mean() == pytest.approx(0.2386, abs=0.004)
    with pytest.raises(ValueError):
        bimodal_p_hi(25.0, 0.3, 20.0)


def test_workload_params_backward_compatible_and_variants_change_n_lb(cfg):
    old = {k: v for k, v in cfg["workload"].items() if k not in ("tool_time_lo_s", "tool_time_hi_s")}
    wl = WorkloadParams.from_dict(old)
    assert wl.tool_time_lo_s == 0.3 and wl.tool_time_hi_s == 20.0
    M = 300_000.0
    n = {v["name"]: length_biased_session_cap(M, WorkloadParams.from_dict(deep_update(cfg["workload"], v["workload"])))
         for v in cfg["robust"]["variants"]}
    assert n["base"] == 28
    assert n["ctx8k"] < n["base"] and n["ctx16k"] < n["ctx8k"]
    assert n["tool_lognormal"] == n["tool_bimodal"] == n["base"]          # N_lb ignores tool time by construction
    assert n["turns30"] < n["base"] < n["turns5"]
    assert n["decode400"] < n["base"]


def test_every_robust_variant_builds_a_valid_workload_and_engine(cfg):
    for v in cfg["robust"]["variants"]:
        rs = RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=50.0, workload_overrides=v["workload"],
                     plan=ArrivalPlan(kind="constant", horizon_s=50.0, rate=0.05))
        res = simulate(cfg, rs)
        assert res["summary"]["n_arrived"] > 0, v["name"]


def test_bimodal_variant_workload_is_reproducible_and_changes_tools_only(cfg):
    wo = {"tool_time_dist": "bimodal"}
    a = build_specs(WorkloadParams.from_dict(deep_update(cfg["workload"], wo)),
                    ArrivalPlan(kind="constant", horizon_s=2000.0, rate=0.1), 5)
    b = build_specs(WorkloadParams.from_dict(cfg["workload"]), ArrivalPlan(kind="constant", horizon_s=2000.0, rate=0.1), 5)
    assert np.array_equal(a.arrival, b.arrival) and np.array_equal(a.n_turns, b.n_turns)   # same sessions
    assert set(np.unique(a.tool_flat)) == {0.3, 20.0} and not np.array_equal(a.tool_flat, b.tool_flat)


# ----------------------------------------------------------------------------- survival
def test_kaplan_meier_hand_example():
    t = [1, 2, 2, 3, 4, 5]
    e = [1, 1, 0, 1, 0, 1]
    km = kaplan_meier(t, e)
    assert list(km["time"]) == [1, 2, 3, 5] and list(km["at_risk"]) == [6, 5, 3, 1] and list(km["deaths"]) == [1, 1, 1, 1]
    assert km["surv"] == pytest.approx([5 / 6, 2 / 3, 4 / 9, 0.0])
    assert km_survival_at(km, 0.5) == 1.0 and km_survival_at(km, 2.5) == pytest.approx(2 / 3)
    assert km_restricted_mean(km, 6.0) == pytest.approx(1 + 5 / 6 + 2 / 3 + 8 / 9)
    assert km_restricted_mean(km, 2.5) == pytest.approx(1 + 5 / 6 + 0.5 * 2 / 3)
    assert km_median(km) == 3.0


def test_kaplan_meier_all_censored_and_ties():
    km = kaplan_meier([5.0, 5.0, 5.0], [False, False, False])
    assert len(km["time"]) == 0 and km_survival_at(km, 5.0) == 1.0 and km_restricted_mean(km, 5.0) == 5.0
    assert math.isnan(km_median(km))
    km2 = kaplan_meier([2.0, 2.0, 2.0, 4.0], [True, True, False, False])           # tied event times, censoring at a tie
    assert list(km2["at_risk"]) == [4.0] and list(km2["deaths"]) == [2.0] and km2["surv"] == pytest.approx([0.5])


def test_km_restricted_mean_estimates_exponential_mean_without_censoring_bias():
    rng = np.random.default_rng(11)
    true_mean, H = 100.0, 500.0
    x = rng.exponential(true_mean, 20_000)
    t, e = np.minimum(x, H), x <= H
    km = kaplan_meier(t, e)
    expected_rmst = true_mean * (1 - math.exp(-H / true_mean))             # integral of exp survival on [0, H]
    assert km_restricted_mean(km, H) == pytest.approx(expected_rmst, rel=0.02)
    assert exponential_mle(t, e)["mean"] == pytest.approx(true_mean, rel=0.03)   # naive mean of events would be biased
    assert km_median(km) == pytest.approx(true_mean * math.log(2), rel=0.05)


def test_exponential_mle_interval_has_nominal_coverage():
    rng = np.random.default_rng(5)
    true_mean, H, n, reps = 300.0, 400.0, 20, 600
    hit = 0
    for _ in range(reps):
        x = rng.exponential(true_mean, n)
        r = exponential_mle(np.minimum(x, H), x <= H)
        hit += r["mean_ci_lo"] <= true_mean <= r["mean_ci_hi"]
    assert 0.92 <= hit / reps <= 0.985
    r0 = exponential_mle([10.0, 10.0], [False, False])                      # no events: mean undefined, lower bound only
    assert math.isnan(r0["mean"]) and r0["mean_ci_hi"] == math.inf
    assert r0["mean_ci_lo"] == pytest.approx(2 * 20.0 / stats.chi2.ppf(0.975, 2))


def test_summarize_escape_and_slopes():
    s = summarize_escape([10.0, 20.0, 30.0, 30.0], [True, True, False, False], 30.0)
    assert s["n"] == 4 and s["n_events"] == 2 and s["horizon"] == 30.0
    assert s["surv_at_horizon"] == pytest.approx(0.5) and s["exp_mean"] == pytest.approx(90.0 / 2)
    assert s["km_rmst"] == pytest.approx(10 * 1.0 + 10 * 0.75 + 10 * 0.5)
    sl = slopes_log_mean_vs_k([0.25, 0.5, 1.0], [10.0, 20.0, 80.0])
    assert sl == pytest.approx((math.log(2) / 0.25, math.log(4) / 0.5))


# ----------------------------------------------------------------------------- system-size scaling
def test_scaled_engine_overrides_and_iteration_time_invariance(cfg):
    base = cfg["engine"]
    assert MR.scaled_engine_overrides(base, 1.0) == {"kv_memory_tokens": 300000.0, "prefill_chunk_budget": 8192,
                                                      "max_running_seqs": 256, "per_token_s": base["per_token_s"],
                                                      "decode_attn_s": base["decode_attn_s"],
                                                      "prefill_attn_s": base["prefill_attn_s"]}
    o = MR.scaled_engine_overrides(base, 0.25)
    assert o["kv_memory_tokens"] == 75000.0 and o["prefill_chunk_budget"] == 2048 and o["max_running_seqs"] == 64
    assert o["per_token_s"] == pytest.approx(4 * base["per_token_s"])
    assert o["decode_attn_s"] == pytest.approx(4 * base["decode_attn_s"])
    assert o["prefill_attn_s"] == pytest.approx(4 * base["prefill_attn_s"])
    assert "iter_fixed_s" not in o and "iter_floor_s" not in o                    # per-iteration constants unchanged

    def tau(p: EngineParams, tok: float, n_dec: float, sumctx: float, attn: float) -> float:
        return (p.iter_fixed_s + max(p.iter_floor_s, p.per_token_s * (tok + n_dec))
                + p.decode_attn_s * sumctx / p.attn_ctx_norm + p.prefill_attn_s * attn)
    p1 = EngineParams.from_dict(base)
    for k in (0.25, 0.5):
        pk = EngineParams.from_dict(deep_update(base, MR.scaled_engine_overrides(base, k)))
        for state in [(6000.0, 120.0, 900_000.0, 4e10), (0.0, 200.0, 1_500_000.0, 0.0), (500.0, 10.0, 50_000.0, 1e9)]:
            tok, nd, sc, at = state
            assert tau(pk, k * tok, k * nd, k * sc, k * at) == pytest.approx(tau(p1, tok, nd, sc, at), rel=1e-9)
    with pytest.raises(ValueError):
        MR.scaled_engine_overrides(base, 0.0)


def test_collapse_queue_threshold_scales_with_k(cfg):
    wl = WorkloadParams.from_dict(cfg["workload"])
    E = length_biased_mean_context(wl)
    for k in (0.25, 0.5, 1.0):
        thr = MR.collapse_queue_threshold(cfg["engine"], wl, k, 4.0)
        assert thr == math.floor(4.0 * 300_000 * k / E)
    assert MR.collapse_queue_threshold(cfg["engine"], wl, 1.0, 4.0) == 113


def test_scaled_system_runs_and_keeps_the_memory_invariant(cfg):
    k = 0.25
    eo = MR.scaled_engine_overrides(cfg["engine"], k)
    rs = RunSpec(exp="t", policy="fcfs", seed=1, horizon_s=1500.0, engine_overrides=eo, debug=True,
                 plan=ArrivalPlan(kind="constant", horizon_s=1500.0, rate=0.5 * 0.0474 * k * 4))
    s = simulate(cfg, rs)["summary"]
    assert s["max_resident_tokens"] <= 75000.0 and s["max_running"] <= 64 and s["n_turns_done"] > 20


# ----------------------------------------------------------------------------- classification helpers
def _synth_burst(hit_series_by_run, tb=5000.0, W=1000.0):
    rows, wins = [], []
    for rid, hits in enumerate(hit_series_by_run):
        rows.append({"run_id": rid, "seed": rid, "policy": "p", "tail_backlog_mean": 5.0})
        for j, h in enumerate(hits):
            wins.append({"run_id": rid, "t_start": j * W, "t_end": (j + 1) * W, "hit_rate": h, "queue_mean": 5.0,
                         "queue_max": 6.0, "gate_mean": 0.0, "turns_per_s": 1.0, "sessions_per_s": 0.05,
                         "busy_frac": 0.5, "admitted_turns": 100, "hits": int(round(100 * h)) if h == h else 0})
    return pd.DataFrame(rows), pd.DataFrame(wins)


def test_burst_columns_trapped_recovered_partial():
    b = {"hit_eval_from_s": 10000.0, "after_s": 25000.0, "trap_hit_below": 0.2, "trap_min_s": 10000.0,
         "recovered_hit_above": 0.8, "recovered_backlog_below": 20.0}
    good = [0.93] * 5
    trapped = good + [0.0] * 25
    recovered = good + [0.0] * 3 + [0.93] * 22
    partial = good + [0.0] * 9 + [0.5] * 16                  # hit < 0.2 for only 9 windows, never back above 0.8
    runs, wins = _synth_burst([trapped, recovered, partial])
    out = MR.burst_columns(runs, wins, b, 1000.0, 5000.0)
    assert list(out["burst_outcome"]) == ["trapped", "recovered", "partial"]
    assert list(out["trapped"]) == [True, False, False]
    assert out["trap_run_s"].tolist() == [25000.0, 3000.0, 9000.0]
    cnt = MR.burst_counts(out, ["policy"])
    assert int(cnt["n_trapped"].iloc[0]) == 1 and int(cnt["n_burst_recovered"].iloc[0]) == 1


def test_add_recovery_uses_backlog_including_the_gate():
    r = pd.DataFrame({"tail_hit_rate": [0.9, 0.9, 0.5], "tail_backlog_mean": [3.0, 150.0, 3.0],
                      "tail_queue_mean": [3.0, 1.0, 3.0]})
    out = MR.add_recovery(r, 0.8, 20.0)
    assert list(out["recovered"]) == [True, False, False]
    assert list(out["recovered_queue_only"]) == [True, True, False]       # the gate backlog fails run 2 only in `recovered`


def test_backlog_verdict_separates_light_and_heavy_load(cfg):
    lim = {"stable_trend_window_s": 1500.0, "stable_trend_max_rise": 10.0, "stable_final_backlog_below": 50}
    lm = 0.0474
    ok = simulate(cfg, RunSpec(exp="t", policy="lpm", seed=0, horizon_s=3000.0,
                               plan=ArrivalPlan(kind="constant", horizon_s=3000.0, rate=0.8 * lm),
                               stop_backlog_above=3000))
    bad = simulate(cfg, RunSpec(exp="t", policy="fcfs", seed=0, horizon_s=3000.0,
                                plan=ArrivalPlan(kind="constant", horizon_s=3000.0, rate=6 * lm),
                                stop_backlog_above=3000))
    assert MR.backlog_verdict(ok, lim)["stable"] is True
    assert MR.backlog_verdict(bad, lim)["stable"] is False
    # a gated policy: the backlog sits in the gate, so a queue-only test would call it stable
    gated = simulate(cfg, RunSpec(exp="t", policy="lb_cap", seed=0, horizon_s=3000.0,
                                  plan=ArrivalPlan(kind="constant", horizon_s=3000.0, rate=6 * lm),
                                  stop_backlog_above=3000))
    v = MR.backlog_verdict(gated, lim)
    assert v["stable"] is False and gated["summary"]["final_gate"] > 50


def test_find_stable_limit_brackets_and_is_deterministic(cfg):
    lim = {"seeds": [0], "horizon_s": 3000.0, "bracket_mults": [2.0, 4.0, 8.0], "rel_tol": 0.05,
           "max_bisect_steps": 3, "unstable_backlog_stop": 3000, "stable_final_backlog_below": 50,
           "stable_trend_window_s": 1500.0, "stable_trend_max_rise": 10.0}
    with MR.Runner(cfg, 1) as R:
        a, specs, res = MR.find_stable_limit(R, cfg, "lpm", 0.0474, lim)
        b, _, _ = MR.find_stable_limit(R, cfg, "lpm", 0.0474, lim)
    assert a["lambda_cap"] == b["lambda_cap"] and a["search_rows"] == b["search_rows"]
    assert 0.0474 <= a["lambda_cap"] < a["bracket_hi"] <= 8.0 * 0.0474
    assert a["bracket_hi"] / a["bracket_lo"] <= 2.0 + 1e-9 and len(specs) == len(res) == a["n_search_runs"]
    stable = {(r["lam"], r["stable"]) for r in a["search_rows"]}
    assert any(s for _, s in stable) and any(not s for _, s in stable)


# ----------------------------------------------------------------------------- experiment smoke + provenance
def _run(cmd: str, tmp: Path, extra=()):
    argv = [cmd, "--quick", "--workers", "1", "--out-root", str(tmp), "--config", str(CFG_PATH), *extra]
    assert MR.main(argv, repo_dir=REPO) == 0


def _only_dir(tmp: Path, name: str) -> Path:
    ds = sorted((tmp / name).glob("*"))
    assert ds, f"no result dir for {name}"
    return ds[-1]


def test_quick_phase_mech_escape_robust_write_provenance_and_never_overwrite(tmp_path, monkeypatch):
    calls = []

    def fake_git(repo_dir):
        calls.append(1)
        return {"commit": "START" if len(calls) == 1 else f"LATER{len(calls)}", "dirty": False, "branch": "b"}
    monkeypatch.setattr(MR, "git_info", fake_git)
    _run("phase", tmp_path)
    d = _only_dir(tmp_path, "prefix_meta_phase_quick")
    meta = json.loads((d / "meta.json").read_text())
    assert meta["git"]["commit"] == "START" and len(calls) == 1               # captured once, at the start
    assert meta["status"] == "done" and meta["hardware"] == "Apple M3 Max CPU (simulation)"
    assert meta["start_time"] <= meta["end_time"] and meta["seeds"] == [0] and meta["quick"] is True
    for f in ("config.yaml", "base_config.yaml", "config_effective.yaml", "preregistration.yaml", "runs.csv",
              "windows.csv", "qtrace.csv", "phase_table.csv"):
        assert (d / f).exists() and (d / f).stat().st_size > 0, f
    assert (d / "preregistration.yaml").read_text() == PREREG_PATH.read_text()
    assert (d / "config.yaml").read_text() == CFG_PATH.read_text()
    tab = pd.read_csv(d / "phase_table.csv")
    assert {"policy", "lam_mult", "lam", "n_runs", "n_recovered"} <= set(tab.columns)
    runs = pd.read_csv(d / "runs.csv")
    assert {"recovered", "recovered_queue_only", "tail_backlog_mean", "stop_reason"} <= set(runs.columns)
    # a second identical invocation creates a NEW directory
    first = {p.name for p in (tmp_path / "prefix_meta_phase_quick").iterdir()}
    _run("phase", tmp_path)
    second = {p.name for p in (tmp_path / "prefix_meta_phase_quick").iterdir()}
    assert first < second and len(second) == 2
    assert json.loads((d / "meta.json").read_text())["git"]["commit"] == "START"          # the old dir is untouched

    monkeypatch.undo()
    _run("mech", tmp_path)
    m = _only_dir(tmp_path, "prefix_meta_mech_quick")
    for f in ("mech_cold_table.csv", "mech_burst_table.csv", "mech_capsweep_table.csv", "mech_limits.csv",
              "limit_search.csv", "runs.csv"):
        assert (m / f).stat().st_size > 0, f
    mruns = pd.read_csv(m / "runs.csv")
    assert set(mruns["part"]) == {"cold", "burst", "capsweep", "capacity"}
    for f in ("mech_capacity.csv", "mech_capacity_by_population.csv", "mech_capacity_runs.csv"):
        assert (m / f).stat().st_size > 0, f
    capc = pd.read_csv(m / "mech_capacity.csv")
    assert {"policy", "ceiling_sessions_per_s", "population_at_ceiling", "ratio_to_lpm"} <= set(capc.columns)
    assert "n_not_burst_recovered" in pd.read_csv(m / "mech_burst_table.csv").columns
    assert (mruns[mruns["part"] == "burst"]["trapped"].notna()).all()
    lim = pd.read_csv(m / "mech_limits.csv")
    assert {"policy", "lambda_cap", "bracket_lo", "bracket_hi", "ratio_to_lpm"} <= set(lim.columns)
    mm = json.loads((m / "meta.json").read_text())
    assert mm["N_lb"] == 28 and mm["cap_1p3"] == 36 and mm["calibration"]["lambda_miss"] > 0

    _run("escape", tmp_path)
    e = _only_dir(tmp_path, "prefix_meta_escape_quick")
    es = pd.read_csv(e / "escape_summary.csv")
    assert {"k", "lam_mult", "n", "n_events", "km_rmst", "exp_mean", "surv_at_horizon"} <= set(es.columns)
    cal = pd.read_csv(e / "escape_calib.csv")
    assert list(cal["k"]) == [0.25, 0.5] and (cal["tail_busy_frac"] > 0.9).all()
    er = pd.read_csv(e / "escape_runs.csv")
    assert (er["obs_time_s"] <= 4000.0 + 1e-6).all()
    assert {"scaling", "stop_time_s", "escape_time_s", "onset_source"} <= set(er.columns)
    assert {"lambda_miss_ci95_lo", "lambda_miss_ci95_hi"} <= set(cal.columns)
    el = pd.read_csv(e / "escape_limits.csv")
    assert list(el["k"]) == [0.25, 0.5] and (el["lambda_cap"] > 0).all()
    assert {"lam_over_cap", "lambda_cap_k", "km_median_ci_lo"} <= set(es.columns)
    _run("escape_inwindow", tmp_path)
    ei = _only_dir(tmp_path, "prefix_meta_escape_inwindow_quick")
    eis = pd.read_csv(ei / "escape_summary.csv")
    assert set(eis["scaling"]) == {"calibrated", "fluid"} and set(eis["k"]) == {1.0, 2.0}
    assert eis[(eis["scaling"] == "fluid") & (eis["k"] == 1.0)]["copied_from_calibrated_k1"].all()
    assert not (pd.read_csv(ei / "escape_runs.csv").query("scaling == 'fluid' and k == 1.0")).shape[0]
    cali = pd.read_csv(ei / "escape_calib.csv")
    assert {"fluid_lambda_miss", "rel_dev_from_fluid"} <= set(cali.columns)

    _run("robust", tmp_path)
    r = _only_dir(tmp_path, "prefix_meta_robust_quick")
    rb = pd.read_csv(r / "robust_summary.csv")
    assert list(rb["variant"]) == ["base", "tool_bimodal"]
    assert {"lambda_miss", "lambda_cap_lpm", "R_lpm", "lambda_cap_fcfs", "burst_n_trapped", "holds"} <= set(rb.columns)

    # the evaluator reads the four directories and writes its own new dir
    _run("evaluate", tmp_path, ["--phase-dir", str(d), "--mech-dir", str(m), "--escape-dir", str(e),
                                "--escape-inwindow-dir", str(ei), "--robust-dir", str(r)])
    ev = _only_dir(tmp_path, "prefix_meta_eval_quick")
    pj = json.loads((ev / "prediction_eval.json").read_text())
    assert {row["id"] for row in pj["rows"]} >= {f"P{i}" for i in range(1, 9)}
    assert any("quick run" in f for f in pj["flags"])
    # the round-3 report writes tables + four PDFs into a new dir and never touches its inputs
    before = (m / "runs.csv").read_bytes()
    _run("report", tmp_path, ["--phase-dir", str(d), "--mech-dir", str(m), "--escape-dir", str(e),
                              "--escape-inwindow-dir", str(ei), "--robust-dir", str(r)])
    rp = _only_dir(tmp_path, "prefix_meta_r3_quick")
    for f in ("fig1_phase_diagram.pdf", "fig2_mechanisms.pdf", "fig3_escape_vs_k.pdf", "fig4_robustness.pdf",
              "prediction_eval.csv", "table_pre_full_runs.csv", "table_input_provenance.csv", "meta.json",
              "table_mechanisms.csv", "table_robustness.csv"):
        assert (rp / f).exists() and (rp / f).stat().st_size > 0, f
    assert (m / "runs.csv").read_bytes() == before
    pre = pd.read_csv(rp / "table_pre_full_runs.csv")
    assert len(pre) >= 5 and {"relation_to_amendment_1", "what_it_showed", "git_dirty"} <= set(pre.columns)


def test_only_flag_restricts_mech_policies(tmp_path):
    _run("mech", tmp_path, ["--only", "fcfs", "lb_cap"])
    m = _only_dir(tmp_path, "prefix_meta_mech_quick")
    runs = pd.read_csv(m / "runs.csv")
    assert set(runs[runs["part"] != "capsweep"]["policy"]) == {"fcfs", "lb_cap"}


# ----------------------------------------------------------------------------- prediction evaluator
def _cold_rows(policy, mult, k, n=3):
    return [{"part": "cold", "policy": policy, "lam_mult": mult, "recovered": i < k, "trapped": float("nan"),
             "burst_recovered": float("nan")} for i in range(n)]


def _burst_rows(policy, trapped, n=5, mult=2.0, recovered=None):
    """``trapped`` runs are trapped; ``recovered`` (default: all the others) are burst_recovered; the rest 'partial'."""
    rec = (n - trapped) if recovered is None else recovered
    return [{"part": "burst", "policy": policy, "lam_mult": mult, "recovered": False, "trapped": i < trapped,
             "burst_recovered": (i >= trapped) and (i - trapped) < rec} for i in range(n)]


def test_eval_p1_and_registered_horizon_rows():
    rows = []
    for m, k in [(0.6, 3), (0.8, 3), (0.9, 3), (1.0, 3), (1.1, 0), (1.25, 0), (1.5, 0), (2.0, 0)]:
        rows += [{"policy": "fcfs", "lam_mult": m, "recovered": i < k, "recovered_registered_horizon": i < k}
                 for i in range(3)]
    df = pd.DataFrame(rows)
    assert PE.eval_p1(df)["verdict"] == PE.PASS
    bad = df.copy()
    bad.loc[(bad["lam_mult"] == 1.1) & (bad.index % 3 == 0), "recovered"] = True
    r = PE.eval_p1(bad)
    assert r["verdict"] == PE.FAIL and r["numbers"]["violating_mults"] == [1.1]
    assert PE.eval_p1(df[df["lam_mult"] != 0.9])["verdict"] == PE.NA
    assert PE.eval_p1(df.iloc[0:0])["verdict"] == PE.NA
    # horizon artefact: at 0.9x the long run recovers 3/3 but at the registered 30k horizon only 0/3 had
    art = df.copy()
    art["recovered_registered_horizon"] = art["recovered"] & (art["lam_mult"] != 0.9)
    r_long, r_reg = PE.eval_p1_rows(art)
    assert r_long["id"] == "P1" and r_long["verdict"] == PE.PASS
    assert r_reg["id"] == "P1-registered-horizon" and r_reg["verdict"] == PE.FAIL
    assert r_reg["numbers"]["violating_mults"] == [0.9]
    assert len(PE.eval_p1_rows(df.drop(columns=["recovered_registered_horizon"]))) == 1


def _mech_frame():
    rows = []
    cells = {"peek": (0, 0), "peek_rank": (0, 0), "peek_lpm": (0, 0), "ttl10": (3, 2), "ttl20": (2, 3),
             "ttlf10": (0, 0), "ttlf20": (0, 0), "ttl10e": (0, 0), "ttl20e": (0, 0), "lb_cap": (3, 3),
             "cap_1p3": (1, 0), "aimd_cap": (2, 3)}
    for pol, (k15, k20) in cells.items():
        rows += _cold_rows(pol, 1.5, k15) + _cold_rows(pol, 2.0, k20)
    rows += _burst_rows("peek", 5) + _burst_rows("peek_rank", 5) + _burst_rows("peek_lpm", 5)
    rows += _burst_rows("ttl10", 1) + _burst_rows("ttl20", 0) + _burst_rows("ttlf10", 5) + _burst_rows("ttlf20", 5)
    rows += _burst_rows("ttl10e", 5) + _burst_rows("ttl20e", 5)
    rows += _burst_rows("lb_cap", 0) + _burst_rows("cap_1p3", 5) + _burst_rows("aimd_cap", 1)
    return pd.DataFrame(rows)


def test_eval_p2_to_p5():
    m = _mech_frame()
    p2, p2_hard, p2_lpm = PE.eval_p2_rows(m)
    assert p2["id"] == "P2" and p2["numbers"]["policy"] == "peek_rank" and p2["verdict"] == PE.PASS      # headline: rank
    assert p2_hard["id"] == "P2-hard-pin" and p2_hard["verdict"] == PE.PASS and p2_lpm["id"] == "P2-peek_lpm"
    fams = {r["id"]: r for r in PE.eval_p3(m)}
    assert fams["P3-A-strict"]["verdict"] == PE.PASS and fams["P3-B-strict"]["verdict"] == PE.FAIL
    assert fams["P3-C-strict"]["verdict"] == PE.FAIL and fams["P3"]["verdict"] == PE.FAIL        # conjunction of A, B, C
    assert fams["P3"]["numbers"]["family_verdicts"] == {"A": PE.PASS, "B": PE.FAIL, "C": PE.FAIL}
    assert PE.eval_p4(m)["verdict"] == PE.PASS and PE.eval_p5(m)["verdict"] == PE.PASS
    # every family satisfied -> P3 passes under both readings
    good = m.copy()
    for pol in ("ttlf10", "ttlf20", "ttl10e", "ttl20e"):
        good = good[~((good["policy"] == pol))]
        good = pd.concat([good, pd.DataFrame(_cold_rows(pol, 1.5, 3) + _cold_rows(pol, 2.0, 3) + _burst_rows(pol, 0))])
    fam_ok = {r["id"]: r for r in PE.eval_p3(good)}
    assert fam_ok["P3"]["verdict"] == PE.PASS and fam_ok["P3-registered-burst-reading"]["verdict"] == PE.PASS
    # break each condition in turn
    bad = m.copy()
    bad.loc[(bad["policy"] == "peek_rank") & (bad["part"] == "cold") & (bad["lam_mult"] == 2.0), "recovered"] = True
    assert PE.eval_p2(bad, "peek_rank")["verdict"] == PE.FAIL
    bad = m[~((m["policy"] == "peek_rank") & (m["part"] == "burst"))]
    assert PE.eval_p2(bad, "peek_rank")["verdict"] == PE.NA
    bad = m.copy()
    bad.loc[(bad["policy"] == "ttl10") & (bad["part"] == "burst"), ["trapped", "burst_recovered"]] = [True, False]
    assert {r["id"]: r for r in PE.eval_p3(bad)}["P3-A-strict"]["verdict"] == PE.FAIL
    bad = m.copy()
    bad.loc[(bad["policy"] == "cap_1p3") & (bad["part"] == "cold") & (bad["lam_mult"] == 2.0), "recovered"] = True
    assert PE.eval_p4(bad)["verdict"] == PE.FAIL
    bad = m.copy()
    bad.loc[(bad["policy"] == "aimd_cap") & (bad["lam_mult"] == 1.5), "recovered"] = False       # 0/3
    assert PE.eval_p5(bad)["verdict"] == PE.FAIL


def test_p3_p4_strict_burst_reading_does_not_count_a_congested_pinning_policy_as_fine():
    """Round-2 review finding 3: ttl20-like runs keep the hit rate high (so they are never 'trapped') but the backlog is
    large and rising, so none is burst_recovered. Registered reading: 0 trapped -> satisfied. Strict reading: 5 congested
    -> not satisfied. Same for a capping policy."""
    rows = []
    for pol in ("ttl10", "ttl20", "lb_cap"):
        rows += _cold_rows(pol, 1.5, 3) + _cold_rows(pol, 2.0, 3) + _burst_rows(pol, 0, recovered=0)   # 5 'partial'
    rows += _cold_rows("cap_1p3", 2.0, 0) + _cold_rows("cap_1p3", 1.5, 0)
    m = pd.DataFrame(rows)
    out = {r["id"]: r for r in PE.eval_p3(m) if r["id"].startswith("P3-A")}
    assert out["P3-A-registered"]["verdict"] == PE.PASS and out["P3-A-strict"]["verdict"] == PE.FAIL
    assert PE.eval_p4(m, "registered")["verdict"] == PE.PASS and PE.eval_p4(m, "strict")["verdict"] == PE.FAIL
    # one non-recovered seed out of five is allowed by '<= 1/5'
    m2 = m[~((m["policy"] == "lb_cap") & (m["part"] == "burst"))]
    m2 = pd.concat([m2, pd.DataFrame(_burst_rows("lb_cap", 0, recovered=4))])
    assert PE.eval_p4(m2, "strict")["verdict"] == PE.PASS


def test_eval_p6_registered_and_capacity_readings():
    cold = pd.DataFrame(_cold_rows("lb_cap", 1.5, 3) + _cold_rows("lb_cap", 2.0, 3) + _cold_rows("ttl10", 1.5, 3)
                        + _cold_rows("ttl10", 2.0, 3) + _cold_rows("peek", 1.5, 0) + _cold_rows("peek", 2.0, 0))
    lim = pd.DataFrame({"policy": ["lpm", "lb_cap", "ttl10", "peek"], "lambda_cap": [0.1, 0.09, 0.085, 0.01]})
    r = PE.eval_p6(cold, lim)
    assert r["verdict"] == PE.PASS and sorted(r["numbers"]["recovering"]) == ["lb_cap", "ttl10"]   # peek does not recover
    lim2 = lim.copy()
    lim2.loc[lim2["policy"] == "ttl10", "lambda_cap"] = 0.05
    r2 = PE.eval_p6(cold, lim2)
    assert r2["verdict"] == PE.FAIL and r2["numbers"]["violating"] == ["ttl10"]
    assert PE.eval_p6(cold, lim[lim["policy"] != "ttl10"])["verdict"] == PE.NA                     # recovering, no limit
    assert PE.eval_p6(cold, lim[lim["policy"] != "lpm"])["verdict"] == PE.NA
    none = pd.DataFrame(_cold_rows("lb_cap", 1.5, 0) + _cold_rows("lb_cap", 2.0, 0))
    assert PE.eval_p6(none, lim)["verdict"] == PE.NA                                               # vacuous
    # capacity reading: LPM's escape-limited limit would pass lb_cap (ratio 0.9) but its good-state ceiling is much higher
    cap = pd.DataFrame({"policy": ["lpm", "lb_cap", "ttl10"], "ceiling_sessions_per_s": [0.20, 0.17, 0.10]})
    c = PE.eval_p6_capacity(cold, cap)
    assert c["id"] == "P6" and c["verdict"] == PE.FAIL and c["numbers"]["violating"] == ["ttl10"]
    assert c["numbers"]["policies"]["lb_cap"]["ratio_to_lpm"] == pytest.approx(0.85)
    cap_ok = cap.assign(ceiling_sessions_per_s=[0.20, 0.17, 0.18])
    assert PE.eval_p6_capacity(cold, cap_ok)["verdict"] == PE.PASS
    assert PE.eval_p6_capacity(cold, cap[cap["policy"] != "lpm"])["verdict"] == PE.NA
    assert PE.eval_p6_capacity(cold, cap[cap["policy"] != "ttl10"])["verdict"] == PE.NA


def _esc(means, events, rmst=None, ks=(0.25, 0.5, 1.0), lam_mult=2.25, scaling="calibrated", lam_over_cap=None):
    rows = []
    for i, (k, m, ev) in enumerate(zip(ks, means, events)):
        row = {"scaling": scaling, "k": k, "lam_mult": lam_mult, "exp_mean": m, "n_events": ev,
               "km_rmst": (rmst or means)[i]}
        if lam_over_cap is not None:
            row["lam_over_cap"] = lam_over_cap[i]
            row["lambda_cap_k"] = 0.1
        rows.append(row)
    return pd.DataFrame(rows)


def test_eval_p7():
    good = _esc([1000.0, 5000.0, 60000.0], [20, 15, 8])           # slopes ln5/.25=6.4, ln12/.5=4.97 -> ratio 1.29
    prim, sec = PE.eval_p7(good)
    assert prim["verdict"] == PE.PASS and sec["verdict"] == PE.PASS
    unordered = _esc([1000.0, 800.0, 60000.0], [20, 15, 8])
    assert PE.eval_p7(unordered)[0]["verdict"] == PE.FAIL
    nonlinear = _esc([1000.0, 1100.0, 90000.0], [20, 15, 8])      # slopes 0.38 vs 8.8
    assert PE.eval_p7(nonlinear)[0]["verdict"] == PE.FAIL
    censored = _esc([1000.0, 5000.0, float("nan")], [20, 15, 0])
    assert PE.eval_p7(censored)[0]["verdict"] == PE.NA
    few = _esc([1000.0, 5000.0, 60000.0], [20, 15, 2])
    assert PE.eval_p7(few)[0]["verdict"] == PE.NA
    assert PE.eval_p7(good.iloc[:2])[0]["verdict"] == PE.NA
    mixed = _esc([1000.0, 5000.0, 60000.0], [20, 15, 8], rmst=[900.0, 800.0, 5000.0])
    p, s = PE.eval_p7(mixed)
    assert p["verdict"] == PE.PASS and s["verdict"] == PE.FAIL


def test_eval_p7_flags_sizes_outside_their_stability_window_and_selects_the_scaling():
    reg = _esc([1000.0, 5000.0, 60000.0], [20, 15, 8], lam_over_cap=[2.3, 1.4, 0.97])
    prim, _ = PE.eval_p7(reg, pid="P7-registered-sizes")
    assert prim["verdict"] == PE.PASS and prim["numbers"]["in_window_all_sizes"] is False
    assert "not evidence for H3" in prim["notes"]
    inw = _esc([2000.0, 9000.0, 80000.0], [18, 12, 6], ks=(1.0, 2.0, 4.0), lam_over_cap=[0.9, 0.8, 0.7])
    prim_iw, _ = PE.eval_p7(inw, ks=(1.0, 2.0, 4.0))
    assert prim_iw["numbers"]["in_window_all_sizes"] is True and "not evidence" not in prim_iw["notes"]
    both = pd.concat([_esc([1000.0, 5000.0, 60000.0], [20, 15, 8]),
                      _esc([1000.0, 800.0, 60000.0], [20, 15, 8], scaling="fluid")])
    assert PE.eval_p7(both, scaling="calibrated")[0]["verdict"] == PE.PASS
    assert PE.eval_p7(both, scaling="fluid")[0]["verdict"] == PE.FAIL
    rows = PE.eval_p7_rows(reg, inw)
    ids = [r["id"] for r in rows]
    assert ids[0] == "P7" and "P7-registered-sizes" in ids and "P7-secondary-KM-RMST" in ids
    assert PE.eval_p7_rows(None, None) == [PE._row("P7", "", PE.NA, {}, "in-window escape result absent")]


def test_eval_p8_and_evaluate_all():
    rb = pd.DataFrame({"variant": list("abcdefgh"), "R_lpm": [2.4] * 8, "burst_n_trapped": [5] * 8,
                       "burst_n_runs": [5] * 8, "holds": [True] * 5 + [False] * 3})
    assert PE.eval_p8(rb)["verdict"] == PE.PASS
    rb.loc[0, "holds"] = False
    r = PE.eval_p8(rb)
    assert r["verdict"] == PE.FAIL and r["numbers"]["n_holding"] == 4
    rows = PE.evaluate_all(phase_runs=None, mech_runs=None, mech_limits=None, escape_summary=None, robust_summary=rb)
    ids = [x["id"] for x in rows]
    assert ids[0] == "P1" and "P8" in ids and sum(1 for x in rows if x["verdict"] == PE.NA) >= 6
    df = PE.rows_to_frame(rows)
    assert list(df.columns) == ["id", "verdict", "claim", "notes", "numbers"]
    json.loads(df["numbers"].iloc[-1])
    full = PE.evaluate_all(phase_runs=None, mech_runs=_mech_frame(), mech_limits=None, escape_summary=None,
                           robust_summary=rb, mech_capacity=pd.DataFrame(
                               {"policy": ["lpm", "lb_cap", "ttl10", "aimd_cap", "ttl20"],
                                "ceiling_sessions_per_s": [0.2, 0.19, 0.19, 0.18, 0.2]}))
    got = {x["id"]: x["verdict"] for x in full}
    assert got["P6"] == PE.PASS and got["P2"] == PE.PASS and got["P3"] == PE.FAIL and got["P4"] == PE.PASS
    assert "P6-registered-limit-based" in got and "P3-registered-burst-reading" in got and "P2-hard-pin" in got


def test_nwc_set_of_amendment_2_contains_the_eager_variants():
    assert set(PE.NWC_POLICIES) < set(PE.NWC_POLICIES_A2)
    assert {"ttl10e", "ttl20e", "ttl10ef", "ttl20ef"} <= set(PE.NWC_POLICIES_A2)
    assert set(PE.P3_FAMILIES) == {"A", "B", "C"}


# ----------------------------------------------------------------------------- amendment 2: event time, horizons, capacity
def test_trailing_low_hit_onset_edge_cases():
    t = [0.0, 1000.0, 2000.0, 3000.0, 4000.0]
    assert trailing_low_hit_onset(t, [0.9, 0.1, 0.15, 0.05, 0.1], 0.2, 1000.0) == 1000.0
    assert trailing_low_hit_onset(t, [0.1, 0.1, 0.9, 0.1, 0.1], 0.2, 1000.0) == 3000.0       # only the TRAILING run
    assert math.isnan(trailing_low_hit_onset(t, [0.1, 0.1, 0.1, 0.1, 0.5], 0.2, 1000.0))        # last window is fine
    assert trailing_low_hit_onset(t, [0.1] * 5, 0.2, 1000.0) == 0.0
    assert trailing_low_hit_onset(t, [0.1, 0.1, float("nan"), 0.1, 0.1], 0.2, 1000.0) == 3000.0  # NaN breaks the run
    assert trailing_low_hit_onset([0.0, 1000.0, 3000.0], [0.1, 0.1, 0.1], 0.2, 1000.0) == 3000.0   # gap breaks the run
    assert math.isnan(trailing_low_hit_onset([], [], 0.2, 1000.0))
    assert trailing_low_hit_onset(t, [0.2, 0.2, 0.2, 0.2, 0.19], 0.2, 1000.0) == 4000.0         # strict inequality


def test_first_good_window():
    rows = [{"t_start": 0.0, "hit_rate": 0.1, "queue_mean": 50.0, "gate_mean": 0.0},
            {"t_start": 1000.0, "hit_rate": 0.9, "queue_mean": 30.0, "gate_mean": 0.0},       # hit ok, backlog not
            {"t_start": 2000.0, "hit_rate": 0.85, "queue_mean": 3.0, "gate_mean": 5.0},
            {"t_start": 3000.0, "hit_rate": 0.9, "queue_mean": 1.0, "gate_mean": 0.0}]
    assert first_good_window(rows[::-1], 0.8, 20.0) == 2000.0
    assert math.isnan(first_good_window(rows[:2], 0.8, 20.0))
    rows[2]["gate_mean"] = 40.0                                           # a gate backlog counts
    assert first_good_window(rows, 0.8, 20.0) == 3000.0


def test_escape_event_time_is_the_hit_collapse_onset_for_both_stop_rules(cfg):
    """Run the registered stop rules on a saturated k=0.25 system: whichever fires, escape_time_s is the start of the
    trailing run of windows with hit rate < 0.2, which equals the engine's own streak onset for hit-stopped runs and is
    EARLIER than the stop time for queue-stopped runs."""
    eo = MR.scaled_engine_overrides(cfg["engine"], 0.25)
    wl = WorkloadParams.from_dict(cfg["workload"])
    thr = MR.collapse_queue_threshold(cfg["engine"], wl, 0.25, 4.0)
    specs, res = [], []
    for seed in (1000, 1001, 1002, 1003):
        for stop_hit in ((0.2, 3), None):                                 # hit rule on / off (then only the queue rule)
            rs = RunSpec(exp="escape", policy="fcfs", seed=seed, horizon_s=30000.0, variant="k=0.25",
                         engine_overrides=eo, stop_queue_above=thr, stop_low_hit=stop_hit,
                         plan=ArrivalPlan(kind="constant", horizon_s=30000.0, rate=3.0 * 0.0097),
                         meta={"lam": 3.0 * 0.0097, "lam_mult": 3.0, "k": 0.25, "scaling": "calibrated"})
            specs.append(rs)
            res.append(simulate(cfg, rs))
    from prefixmeta.runner import collect_frames
    runs, wins, _ = collect_frames(res, specs)
    out = MR.escape_event_times(runs, wins, 0.2, cfg["metrics"]["window_s"])
    esc = out[out["stopped_early"].astype(bool)]
    assert len(esc) >= 4
    hit_stopped = esc[esc["stop_reason"] == "hit"]
    queue_stopped = esc[esc["stop_reason"] == "queue"]
    assert len(hit_stopped) and len(queue_stopped)
    assert (hit_stopped["escape_time_s"] == hit_stopped["stop_time"]).all() and (hit_stopped["onset_source"] == "hit").all()
    assert (queue_stopped["escape_time_s"] <= queue_stopped["stop_time"] + 1e-9).all()
    assert (queue_stopped["onset_source"] != "hit").all()
    # the same seed collapses at the same onset whichever rule fires first (the windows are identical up to the stop)
    for seed in (1000, 1001, 1002, 1003):
        a = out[(out["seed"] == seed)]
        ts = a["escape_time_s"].dropna()
        if len(ts) == 2:
            assert abs(ts.iloc[0] - ts.iloc[1]) <= 1000.0 + 1e-9
    unesc = out[~out["stopped_early"].astype(bool)]
    assert unesc["escape_time_s"].isna().all()


def test_km_median_ci_basic_properties():
    t = np.arange(1.0, 11.0)
    med, lo, hi = km_median_ci(t, np.ones(10, dtype=bool))
    assert med == 5.0 and lo <= med and (hi != hi or hi >= med)           # S(5) = 0.5 exactly
    assert lo == lo and lo >= 1.0
    med2, lo2, hi2 = km_median_ci(np.full(5, 100.0), np.zeros(5, dtype=bool))         # all censored
    assert all(x != x for x in (med2, lo2, hi2))
    # censoring keeps the median undefined if S never reaches 0.5
    d = np.array([10.0, 20.0, 30.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    e = np.array([1, 1, 0, 0, 0, 0, 0, 0], dtype=bool)
    assert math.isnan(km_median_ci(d, e)[0])
    # wider interval with fewer observations; the interval contains the sample median
    rng = np.random.default_rng(0)
    big = rng.exponential(100.0, 400)
    mb, lb, hb = km_median_ci(big, np.ones(400, dtype=bool))
    ms, ls, hs = km_median_ci(big[:20], np.ones(20, dtype=bool))
    assert (hb - lb) < (hs - ls) and lb <= mb <= hb and ls <= ms <= hs


def test_km_median_ci_coverage_with_right_censoring():
    """Nominal 95 % interval for the median of an Exp(100) sample with administrative censoring at 400 s (S(400) = 0.018)."""
    rng = np.random.default_rng(7)
    true_med = 100.0 * math.log(2)
    hits, n_rep = 0, 400
    for _ in range(n_rep):
        x = rng.exponential(100.0, 60)
        ev = x < 400.0
        obs = np.minimum(x, 400.0)
        med, lo, hi = km_median_ci(obs, ev)
        hi = float("inf") if hi != hi else hi
        hits += int(lo <= true_med <= hi)
    assert 0.90 <= hits / n_rep <= 0.99, hits / n_rep


def test_scale_limit_cfg_and_calib_row():
    lim = {"unstable_backlog_stop": 3000, "stable_final_backlog_below": 50, "stable_trend_max_rise": 10.0, "seeds": [0]}
    assert MR.scale_limit_cfg(lim, 0.25) == lim and MR.scale_limit_cfg(lim, 1.0) == lim              # k <= 1: unscaled
    s4 = MR.scale_limit_cfg(lim, 4.0)
    assert s4["unstable_backlog_stop"] == 12000 and s4["stable_final_backlog_below"] == 200 and s4["stable_trend_max_rise"] == 40.0
    assert lim["unstable_backlog_stop"] == 3000                                                    # input not mutated
    row = MR.calib_row(2.0, 120, 0.09, [0.08, 0.09, 0.10], 1.0, 0.05)
    assert row["fluid_lambda_miss"] == pytest.approx(0.10) and row["rel_dev_from_fluid"] == pytest.approx(-0.1)
    assert row["lambda_miss_ci95_lo"] < 0.09 < row["lambda_miss_ci95_hi"] and row["lambda_miss_sd"] == pytest.approx(0.01)
    assert "fluid_lambda_miss" not in MR.calib_row(1.0, 60, 0.05, [0.05], 1.0, None)


def test_find_stable_limit_searches_downwards_when_unstable_at_lambda_miss(cfg):
    lim = {"seeds": [0], "horizon_s": 3000.0, "bracket_mults": [2.0], "lower_mults": [0.5, 0.25, 0.1],
           "rel_tol": 0.2, "max_bisect_steps": 2, "unstable_backlog_stop": 3000, "stable_final_backlog_below": 50,
           "stable_trend_window_s": 1500.0, "stable_trend_max_rise": 10.0}
    with MR.Runner(cfg, 1) as R:
        # pretend lambda_miss is 6x the real one: 1.0x is hopelessly overloaded, 0.1x (= 0.6 real) still is not safe
        summ, _, _ = MR.find_stable_limit(R, cfg, "fcfs", 0.047419 * 3.0, lim)
    phases = [r["phase"] for r in summ["search_rows"]]
    assert "bracket_down" in phases and summ["lambda_cap"] > 0
    assert summ["bracket_hi"] <= 0.047419 * 3.0 and summ["unbounded_in_search"] is False
    first = summ["search_rows"][0]
    assert first["phase"] == "bracket" and first["lam_mult"] == 1.0 and not first["stable"]


def test_phase_horizon_and_derived_columns():
    ph = {"horizon_s": 30000.0, "long_horizon_s": 150000.0, "long_horizon_up_to_mult": 1.25,
          "recovered_hit_above": 0.8, "recovered_backlog_below": 20.0, "registered_tail_s": 5000.0}
    assert MR.phase_horizon(ph, 0.6) == 150000.0 and MR.phase_horizon(ph, 1.25) == 150000.0
    assert MR.phase_horizon(ph, 1.5) == 30000.0 and MR.phase_horizon({"horizon_s": 30000.0}, 0.6) == 30000.0
    W = 1000.0

    def windows(rid, good_from):
        return [{"run_id": rid, "t_start": i * W, "t_end": (i + 1) * W, "admitted_turns": 100,
                 "hits": 90 if i >= good_from else 0, "hit_rate": 0.9 if i >= good_from else 0.0,
                 "queue_mean": 2.0 if i >= good_from else 300.0, "queue_max": 5.0, "gate_mean": 0.0,
                 "turns_per_s": 1.0, "sessions_per_s": 0.1, "busy_frac": 0.5} for i in range(60)]
    wins = pd.DataFrame(windows(0, 20) + windows(1, 40))                 # recovers at 20k s / at 40k s (after the 30k horizon)
    runs = pd.DataFrame({"run_id": [0, 1], "tail_hit_rate": [0.9, 0.9], "tail_backlog_mean": [2.0, 2.0],
                         "tail_queue_mean": [2.0, 2.0]})
    out = MR.phase_derived(MR.add_recovery(runs, 0.8, 20.0), wins, ph)
    assert list(out["recovered"]) == [True, True]
    assert list(out["recovered_registered_horizon"]) == [True, False]    # the second run is horizon-limited at 30k
    assert list(out["t_first_good_s"]) == [20000.0, 40000.0]


def test_capacity_summary_and_ceilings():
    rows = []
    for pol, curve in {"lpm": {8: 0.10, 28: 0.20, 64: 0.05, 300: 0.047}, "cap": {8: 0.10, 28: 0.19, 64: 0.19, 300: 0.19}}.items():
        for n, v in curve.items():
            for sd, jitter in ((0, -0.002), (1, 0.002)):
                rows.append({"policy": pol, "population": n, "seed": sd, "sessions_per_s": v + jitter, "turns_per_s": 1.0,
                             "hit_rate": 0.9, "busy_frac": 0.9})
    by = MR.capacity_by_population(pd.DataFrame(rows))
    assert len(by) == 8 and by.loc[(by["policy"] == "lpm") & (by["population"] == 28), "sessions_per_s"].iloc[0] == pytest.approx(0.20)
    ce = MR.capacity_ceilings(by, "lpm").set_index("policy")
    assert ce.loc["lpm", "ceiling_sessions_per_s"] == pytest.approx(0.20) and ce.loc["lpm", "population_at_ceiling"] == 28
    assert ce.loc["cap", "ceiling_sessions_per_s"] == pytest.approx(0.19)
    assert ce.loc["cap", "ratio_to_lpm"] == pytest.approx(0.95) and ce.loc["lpm", "ratio_to_lpm"] == pytest.approx(1.0)
    assert ce.loc["lpm", "throughput_at_largest_population"] == pytest.approx(0.047)


def test_closed_population_capacity_run_with_cache_and_cap(cfg):
    """A closed population of 64 with the cache: LPM thrashes (throughput near lambda_miss), the LB cap holds ~N_lb
    sessions in the system and keeps the hit rate high; both keep the population constant."""
    out = {}
    for pol in ("lpm", "lb_cap"):
        rs = RunSpec(exp="t", policy=pol, seed=0, horizon_s=6000.0, variant="closedN=64",
                     plan=ArrivalPlan(kind="closed", horizon_s=6000.0, closed_n=64, pool=4000),
                     meta={"lam": float("nan"), "lam_mult": float("nan"), "population": 64})
        out[pol] = simulate(cfg, rs)
    th = {k: MR.R1.miss_throughput(v, 1000.0, 1000.0)["sessions_per_s"] for k, v in out.items()}
    assert th["lb_cap"] > th["lpm"] > 0
    assert out["lb_cap"]["summary"]["max_in_system"] <= 28 and out["lb_cap"]["summary"]["n_in_flight"] == 64


# ----------------------------------------------------------------------------- report: figures and provenance table
def test_report_figures_run_on_synthetic_tables(tmp_path):
    phase = pd.DataFrame([{"policy": p, "lam_mult": m, "seed": s, "recovered": (m < 1.0) and p != "peek",
                           "tail_hit_rate": 0.9 if m < 1.0 else 0.05}
                          for p in ("fcfs", "lpm", "peek_rank", "peek") for m in (0.6, 1.0, 2.0) for s in range(3)])
    t = RP.fig_phase(phase, 0.0474, 0.1156, tmp_path / "f1.pdf")
    assert (tmp_path / "f1.pdf").stat().st_size > 1000 and set(t["policy"]) == {"fcfs", "lpm", "peek_rank", "peek"}
    cold = pd.DataFrame([{"policy": p, "lam_mult": m, "seed": s, "recovered": p == "lb_cap"}
                         for p in ("fcfs", "lb_cap", "ttl10e") for m in (1.5, 2.0) for s in range(3)])
    burst = pd.DataFrame([{"policy": p, "lam_mult": 2.0, "seed": s, "trapped": p == "fcfs", "burst_recovered": p == "lb_cap"}
                          for p in ("fcfs", "lb_cap", "ttl10e") for s in range(5)])
    lim = pd.DataFrame({"policy": ["fcfs", "lb_cap"], "lambda_cap": [0.11, 0.16]})
    cap = pd.DataFrame({"policy": ["fcfs", "lb_cap"], "ceiling_sessions_per_s": [0.2, 0.19], "ratio_to_lpm": [1.0, 0.95]})
    wide = RP.fig_mechanisms(cold, burst, lim, cap, 0.0474, ["fcfs", "lb_cap", "ttl10e", "lpm"], tmp_path / "f2.pdf")
    assert (tmp_path / "f2.pdf").stat().st_size > 1000 and list(wide["policy"]) == ["fcfs", "lb_cap", "ttl10e"]
    assert wide.set_index("policy").loc["lb_cap", "recovered_2x"] == "3/3" and wide["burst_trapped"].tolist() == [5, 0, 0]
    es = pd.DataFrame([{"scaling": sc, "k": k, "lam_mult": 2.25, "n": 20, "n_events": 20 if k < 4 else 0, "horizon": 4e5,
                        "km_median": 1e4 * k if k < 4 else float("nan"), "km_median_ci_lo": 5e3 * k,
                        "km_median_ci_hi": 2e4 * k if k < 4 else float("nan"), "exp_mean": 1e4 * k if k < 4 else float("nan"),
                        "exp_mean_ci_lo": 5e3 * k, "exp_mean_ci_hi": 2e4 * k, "lam_over_cap": 0.9}
                       for sc in ("calibrated", "fluid") for k in (1.0, 2.0, 4.0)])
    pl = RP.fig_escape(es, es, tmp_path / "f3.pdf")
    assert (tmp_path / "f3.pdf").stat().st_size > 1000 and len(pl) == 2 * 2 * 6
    rob = pd.DataFrame({"variant": ["base", "ctx8k"], "R_lpm": [2.4, 1.2], "R_fcfs": [2.3, 1.1], "burst_n_runs": [5, 5],
                        "burst_n_trapped": [5, 2], "burst_n_recovered": [0, 3], "holds": [True, False]})
    RP.fig_robust(rob, tmp_path / "f4.pdf")
    assert (tmp_path / "f4.pdf").stat().st_size > 1000


def test_pre_full_run_table_marks_runs_before_and_after_the_amendment_commit(tmp_path, monkeypatch):
    def mk_dir(name, stamp, commit, dirty, quick=True):
        d = tmp_path / "results" / name / stamp
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"experiment": name, "start_time": "2026-10-21T" + stamp,
                                                 "git": {"commit": commit, "dirty": dirty}, "quick": quick, "n_runs": 3}))
        return d
    a = mk_dir("prefix_meta_mech_quick", "01:35:12", "a8b2da7aaa", True)
    pd.DataFrame({"policy": ["ttl10"], "lam_mult": [2.0], "n_runs": [1], "n_trapped": [0]}).to_csv(a / "mech_burst_table.csv", index=False)
    mk_dir("prefix_meta_mech_quick", "01:46:26", "cb9d0ceaaa", True)
    mk_dir("prefix_meta_phase", "03:00:00", "zzz", False, quick=False)             # a full run is not listed
    t_am = time.mktime(time.strptime("2026-10-21T01:41:01", "%Y-%m-%dT%H:%M:%S"))
    monkeypatch.setattr(RP, "_git_epoch", lambda repo, rev: t_am)
    tab = RP.pre_full_run_table(tmp_path / "results", tmp_path)
    assert list(tab["relation_to_amendment_1"]) == ["before amendment 1", "after amendment 1"]
    assert list(tab["git_dirty"]) == [True, True] and "ttl10 0/1" in tab["what_it_showed"].iloc[0]
