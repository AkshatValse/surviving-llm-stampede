"""Round-5 runner tests: the config equals the registered design, the verbatim predictions, the seed discipline, the append-only
amendment, the experiment specs (paired no-burst runs, cap = n*, mode overrides), n* selection, and a quick end-to-end smoke of the CLI
in a temporary results root (never overwrites, copies configs, records git state at the start)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta.engine import EngineParams
from prefixmeta.mech_runner import load_mech_config
from prefixmeta.r5_runner import (all_modes, burst_specs, calib_specs, calib_summary, cap_specs, curve_specs, curve_table, main,
                                  mode_overrides, nstar_from_curve_table, point_metrics_r5)
from prefixmeta.sim import build_engine, simulate
from prefixmeta.workload import ArrivalPlan, WorkloadParams, build_specs

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "configs" / "prefix_meta_r5.yaml"
PREREG = REPO / "configs" / "prefix_meta_r5_prereg.yaml"
REGISTERED_BYTES = 29121
REGISTERED_SHA256 = "10f50df6c83f1d0235c2c3e0ba7ed9b6cc0f9e97be591d35671ba2451b738b16"      # prereg text of commit e24e3cd
QUESTION = ("Is prefix-cache metastability in agent serving an artifact of reserving each running request's full end-of-turn KV at "
            "admission, or does it persist under vLLM-like on-demand allocation with recompute preemption and SGLang-like "
            "new_token_ratio reservation with retraction?")


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_mech_config(str(CONFIG), REPO)


@pytest.fixture(scope="module")
def design() -> dict:
    return yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]


# =========================================================================== registration vs config
VERBATIM = {
    "S1": ("the closed FCFS-LRU curve mu(n) is unimodal with mu(300) <= 1.3 lambda_miss(mode) and max mu >= 2 x mu(300) (collapse "
           "persists). KILL-criterion for the mechanism: mu(300) >= 0.8 max mu in a mode => metastability is a full-reservation "
           "artifact in that mode."),
    "S2": ("burst 200 at 2 x lambda_miss(mode) from empty (5k s warmup) leaves FCFS not recovered (last 5 windows: backlog >= 20 or "
           "hit < 0.8, 60k s after burst) in >= 3/5 seeds, while the paired no-burst run (b=0, same seeds) is good in >= 4/5."),
    "S3": ("a static session cap at the mode's measured argmax n* recovers from cold 300 at 2 x lambda_miss(mode) in >= 2/3 seeds "
           "(150k s), and FCFS without cap recovers 0/3."),
    "S4": "LPM mu(300) - FCFS mu(300) >= 0.05 lambda_miss in each mode (LPM's short-tool benefit persists).",
}


def test_prereg_and_config_start_with_the_research_question_and_have_the_verbatim_predictions():
    raw = yaml.safe_load(PREREG.read_text())
    assert list(raw)[0] == "research_question" and raw["research_question"] == QUESTION
    assert list(yaml.safe_load(CONFIG.read_text()))[0] == "research_question"
    assert yaml.safe_load(CONFIG.read_text())["research_question"] == QUESTION
    preds = raw["preregistration"]["predictions"]
    assert set(preds) == set(VERBATIM)
    for k, v in VERBATIM.items():
        assert preds[k] == v, k


def test_amendment_is_append_only():
    raw = PREREG.read_bytes()
    assert len(raw) > REGISTERED_BYTES
    assert hashlib.sha256(raw[:REGISTERED_BYTES]).hexdigest() == REGISTERED_SHA256
    assert "amendment_1" in yaml.safe_load(raw)["preregistration"]


def test_config_equals_the_registered_design(cfg, design):
    cb, cv, bd, cd = cfg["calibration"], cfg["curve"], cfg["burst"], cfg["cap"]
    rc = design["calibration"]
    for key in ("population", "cache_enabled", "policy", "seeds", "pool_sessions", "horizon_s", "warmup_s"):
        assert cb[key] == rc[key], key
    rv = design["curve"]
    for key in ("n_grid", "policies", "seeds", "warmup_s", "horizon_s", "pool_sessions_per_k"):
        assert cv[key] == rv[key], key
    rb = design["burst"]
    for key in ("policy", "lam_mult", "sizes", "burst_width_s", "warmup_s", "after_s", "seeds", "recovered_hit_above",
                "recovered_backlog_below"):
        assert bd[key] == rb[key], key
    rp = design["cap"]
    for key in ("policy", "lam_mult", "cold_sessions", "arms", "seeds", "horizon_s", "recovered_hit_above", "recovered_backlog_below"):
        assert cd[key] == rp[key], key
    assert cfg["modes"]["registered"] == design["modes"]["registered"] and cfg["modes"]["reference"] == design["modes"]["reference"]
    assert cfg["modes"]["engine_overrides"] == design["modes"]["engine_overrides"]
    assert cfg["metrics"]["window_s"] == design["window_s"] == 1000.0
    for name, (kind, ev) in design["policies"].items():
        assert cfg["policies"][name]["kind"] == kind and cfg["policies"][name]["eviction"] == ev
    assert cfg["parallel"]["max_workers"] <= 3
    assert cv["horizon_s"] - cv["warmup_s"] >= 30000.0
    wl = WorkloadParams.from_dict(cfg["workload"])
    from prefixmeta.workload import length_biased_session_cap
    assert length_biased_session_cap(cfg["engine"]["kv_memory_tokens"], wl) == design["N_lb"] == 28


def test_seeds_are_fresh_and_quick_seeds_are_unregistered(cfg, design):
    old = (set(range(0, 5)) | set(range(100, 120)) | set(range(1000, 1020)) | set(range(1100, 1120)) | set(range(2000, 2003))
           | set(range(2100, 2105)) | set(range(2200, 2203)) | set(range(7000, 7201)) | set(range(8000, 8230)) | set(range(9000, 9201)))
    registered = set()
    for sec in ("calibration", "curve", "burst", "cap"):
        seeds = set(cfg[sec]["seeds"])
        assert not (seeds & old), sec
        registered |= seeds
    quick = set()
    for sec in ("calibration", "curve", "burst", "cap"):
        quick |= set(cfg[sec]["quick"]["seeds"])
    assert not (quick & old) and not (quick & registered)
    assert quick <= set(design["quick_seeds_not_registered"])


def test_engine_constants_in_the_config_are_the_engine_defaults_and_scout_values(cfg):
    ep = EngineParams.from_dict(cfg["engine"])
    ro = cfg["modes"]["engine_overrides"]["ratio_reserve"]
    d = EngineParams.from_dict({**cfg["engine"], **ro})
    assert (d.sched_conservativeness, d.init_new_token_ratio, d.min_new_token_ratio_factor, d.new_token_ratio_decay_steps,
            d.retract_decode_steps, d.clip_max_new_tokens_estimation) == (1.0, 0.7, 0.14, 600, 20, 4096)
    assert (ep.sched_conservativeness, ep.init_new_token_ratio, ep.min_new_token_ratio_factor, ep.new_token_ratio_decay_steps,
            ep.retract_decode_steps, ep.clip_max_new_tokens_estimation, ep.watermark_frac) == (1.0, 0.7, 0.14, 600, 20, 4096, 0.0)
    assert ep.alloc_mode == "full_reserve"


# =========================================================================== experiment specs
def test_calib_specs_per_mode(cfg):
    cb = cfg["calibration"]
    specs = calib_specs(cfg, cb)
    assert len(specs) == 3 * len(cb["seeds"])
    assert [rs.meta["alloc_mode"] for rs in specs[::len(cb["seeds"])]] == all_modes(cfg) == ["ondemand_preempt", "ratio_reserve", "full_reserve"]
    for rs in specs:
        assert rs.plan.kind == "closed" and rs.plan.closed_n == 60 and rs.plan.pool == 60000 and rs.policy == "fcfs_lru"
        assert rs.engine_overrides["cache_enabled"] is False and rs.engine_overrides["alloc_mode"] == rs.meta["alloc_mode"]
        assert rs.horizon_s == 100000.0 and rs.variant.startswith("mode=")


def test_curve_specs_cover_modes_policies_grid_seeds_with_crn(cfg):
    cv = cfg["curve"]
    specs = curve_specs(cfg, cv)
    assert len(specs) == 3 * 2 * 12 * 3 == 216
    assert {(rs.meta["alloc_mode"], rs.policy, rs.meta["n_nominal"], rs.seed) for rs in specs} == {
        (m, p, n, s) for m in all_modes(cfg) for p in cv["policies"] for n in cv["n_grid"] for s in cv["seeds"]}
    for rs in specs:
        assert rs.plan.kind == "closed" and rs.plan.closed_n == rs.meta["n_nominal"] and rs.horizon_s == 35000.0
        assert rs.engine_overrides == mode_overrides(cfg, rs.meta["alloc_mode"])
    # same seed -> the same workload stream for every mode and policy (common random numbers)
    wl = WorkloadParams.from_dict(cfg["workload"])
    a = build_specs(wl, [s for s in specs if s.meta["alloc_mode"] == "ratio_reserve"][0].plan, 3000)
    b = build_specs(wl, [s for s in specs if s.meta["alloc_mode"] == "full_reserve"][0].plan, 3000)
    assert np.array_equal(a.n_turns, b.n_turns) and np.array_equal(a.tool_flat, b.tool_flat)


def test_burst_specs_use_each_modes_own_lambda_and_pair_the_no_burst_run(cfg):
    lam = {"ondemand_preempt": 0.040, "ratio_reserve": 0.050}
    specs = burst_specs(cfg, cfg["burst"], lam)
    assert len(specs) == 2 * 2 * 5
    for rs in specs:
        assert rs.plan.rate == pytest.approx(2.0 * lam[rs.meta["alloc_mode"]]) and rs.meta["lam_mult"] == 2.0
        assert rs.plan.burst_n == rs.meta["burst_n"] in (0, 200) and rs.plan.burst_t0 == 5000.0 and rs.plan.burst_width_s == 60.0
        assert rs.horizon_s == 65000.0 and rs.policy == "fcfs_lru"
    wl = WorkloadParams.from_dict(cfg["workload"])
    for mode in lam:
        for sd in cfg["burst"]["seeds"]:
            p0 = [s for s in specs if s.meta["alloc_mode"] == mode and s.seed == sd and s.plan.burst_n == 0][0].plan
            p200 = [s for s in specs if s.meta["alloc_mode"] == mode and s.seed == sd and s.plan.burst_n == 200][0].plan
            a0, a200 = build_specs(wl, p0, sd), build_specs(wl, p200, sd)
            base0 = a0.arrival
            # the Poisson stream is shared: every no-burst arrival is also an arrival of the burst run (same seed, same lambda)
            assert len(a200) == len(a0) + 200
            assert set(np.round(base0, 9)) <= set(np.round(a200.arrival, 9))


def test_cap_specs_cap_at_the_modes_nstar_and_a_no_cap_arm(cfg):
    lam = {"ondemand_preempt": 0.040, "ratio_reserve": 0.050}
    nstar = {"ondemand_preempt": 20, "ratio_reserve": 24}
    specs = cap_specs(cfg, cfg["cap"], lam, nstar)
    assert len(specs) == 2 * 2 * 3
    for rs in specs:
        mode, arm = rs.meta["alloc_mode"], rs.meta["arm"]
        assert rs.plan.initial_cold == 300 and rs.plan.rate == pytest.approx(2.0 * lam[mode]) and rs.horizon_s == 150000.0
        assert rs.session_cap_override == (nstar[mode] if arm == "capped_at_nstar" else None)
        assert rs.meta["cap"] == (nstar[mode] if arm == "capped_at_nstar" else -1)


def _table(mode_curves):
    rows = []
    for mode, vals in mode_curves.items():
        for n, mu in vals.items():
            rows.append({"mode": mode, "policy": "fcfs_lru", "n_nominal": n, "mu_mean": mu})
            rows.append({"mode": mode, "policy": "lpm_lru", "n_nominal": n, "mu_mean": 10.0 * mu})
    return pd.DataFrame(rows)


def test_nstar_is_the_first_argmax_of_the_fcfs_lru_curve():
    ct = _table({"a": {8: 0.08, 16: 0.16, 20: 0.17, 24: 0.17, 300: 0.05}, "b": {8: 0.2, 300: 0.05}})
    assert nstar_from_curve_table(ct, "a") == 20                 # ties: smallest n
    assert nstar_from_curve_table(ct, "b") == 8
    assert nstar_from_curve_table(ct, "a", policy="lpm_lru") == 20
    with pytest.raises(ValueError):
        nstar_from_curve_table(ct, "missing")


def test_curve_table_and_calib_summary_aggregate_by_seed(cfg):
    rows = []
    for sd, mu in ((1, 0.10), (2, 0.12), (3, 0.14)):
        rows.append({"mode": "m", "policy": "fcfs_lru", "n_nominal": 8, "seed": sd, "mu": mu, **{c: 1.0 for c in (
            "hit_rate", "gpu_busy", "resident_kv_tokens", "reserved_tokens", "idle_tokens", "evictions_per_s", "turns_per_s",
            "mu_first_half", "mu_second_half", "preemptions_per_s", "preemptions_per_turn", "recompute_tok_per_s", "recompute_frac")}})
    ct = curve_table(pd.DataFrame(rows))
    assert ct["mu_mean"].iloc[0] == pytest.approx(0.12) and ct["mu_sd"].iloc[0] == pytest.approx(0.02)
    assert ct["mu_se"].iloc[0] == pytest.approx(0.02 / math.sqrt(3)) and json.loads(ct["seeds"].iloc[0]) == [1, 2, 3]
    cs = calib_summary(pd.DataFrame([{"mode": "m", "seed": s, "sessions_per_s": v, "preemptions_per_s": 0.0, "recompute_tok_per_s": 0.0,
                                      "prefill_tok_per_s": 1.0} for s, v in ((2, 0.04), (1, 0.05))]))
    assert cs["lambda_miss"].iloc[0] == pytest.approx(0.045) and json.loads(cs["per_seed"].iloc[0]) == [0.05, 0.04]


def test_point_metrics_r5_reports_preemption_columns(cfg):
    from prefixmeta.r4_runner import closed_spec
    cv = dict(cfg["curve"])
    cv["horizon_s"] = 4000.0
    cv["warmup_s"] = 1000.0
    out = {}
    for mode in ("full_reserve", "ondemand_preempt"):
        rs = closed_spec("fcfs_lru", 200, 1.0, 7300, cv, cfg["engine"])
        rs.engine_overrides = mode_overrides(cfg, mode)
        res = simulate(cfg, rs)
        out[mode] = point_metrics_r5(res["windows"], 1000.0, 4000.0, 1000.0)
    assert out["full_reserve"]["preemptions_per_s"] == 0.0 and out["full_reserve"]["recompute_frac"] == 0.0
    assert out["ondemand_preempt"]["preemptions_per_s"] > 0.0 and 0.0 < out["ondemand_preempt"]["recompute_frac"] < 1.0
    assert out["ondemand_preempt"]["preemptions_per_turn"] > 0.0


# =========================================================================== CLI smoke (quick sizes, temporary results root)
def test_quick_cli_end_to_end_in_a_temporary_results_root(tmp_path):
    root = tmp_path / "results"
    base = ["--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(root)]
    main(["calib"] + base, repo_dir=REPO)
    cal_dirs = sorted((root / "prefix_meta_r5_calib_quick").glob("*"))
    assert len(cal_dirs) == 1
    cal = cal_dirs[0]
    for f in ("config.yaml", "base_config.yaml", "config_effective.yaml", "preregistration.yaml", "meta.json", "calib_runs.csv",
              "calib_summary.csv", "calib_summary.json", "runs.csv", "windows.csv"):
        assert (cal / f).exists() and (cal / f).stat().st_size > 0, f
    meta = json.loads((cal / "meta.json").read_text())
    assert meta["status"] == "done" and meta["quick"] is True and set(meta["git"]) >= {"commit", "dirty", "branch"}
    lam = json.loads((cal / "calib_summary.json").read_text())["lambda_miss"]
    assert set(lam) == {"ondemand_preempt", "ratio_reserve", "full_reserve"} and all(0.01 < v < 0.2 for v in lam.values())
    assert yaml.safe_load((cal / "config.yaml").read_text())["research_question"] == QUESTION

    main(["curve"] + base, repo_dir=REPO)
    cur = sorted((root / "prefix_meta_r5_curve_quick").glob("*"))[0]
    ct = pd.read_csv(cur / "curve_table.csv")
    assert set(ct["mode"]) == set(lam) and set(ct["policy"]) == {"fcfs_lru", "lpm_lru"} and set(ct["n_nominal"]) == {8, 24, 100}
    assert (ct["mu_mean"] > 0).all()
    assert json.loads((cur / "meta.json").read_text())["nstar_by_mode"].keys() == lam.keys()

    main(["burst"] + base + ["--calib-dir", str(cal)], repo_dir=REPO)
    bur = sorted((root / "prefix_meta_r5_burst_quick").glob("*"))[0]
    bc = pd.read_csv(bur / "burst_counts.csv")
    assert set(bc["alloc_mode"]) == {"ondemand_preempt", "ratio_reserve"} and set(bc["burst_n"]) == {0, 100}

    main(["cap"] + base + ["--calib-dir", str(cal), "--curve-dir", str(cur)], repo_dir=REPO)
    cap = sorted((root / "prefix_meta_r5_cap_quick").glob("*"))[0]
    cc = pd.read_csv(cap / "cap_cells.csv")
    assert set(cc["arm"]) == {"capped_at_nstar", "no_cap"} and set(cc["alloc_mode"]) == {"ondemand_preempt", "ratio_reserve"}
    capmeta = json.loads((cap / "meta.json").read_text())
    assert capmeta["nstar_source"] == str(cur) and set(capmeta["nstar_by_mode"]) == {"ondemand_preempt", "ratio_reserve"}
    assert set(cc[cc["arm"] == "capped_at_nstar"]["cap"]) <= {8, 24, 100}

    # a second invocation creates a NEW directory (nothing is overwritten)
    import time
    time.sleep(1.1)
    main(["calib"] + base, repo_dir=REPO)
    assert len(sorted((root / "prefix_meta_r5_calib_quick").glob("*"))) == 2
    assert (cal / "calib_summary.json").exists()


def test_burst_and_cap_refuse_to_run_without_a_calibration(tmp_path):
    base = ["--config", str(CONFIG), "--quick", "--workers", "1", "--out-root", str(tmp_path / "r")]
    with pytest.raises(SystemExit):
        main(["burst"] + base, repo_dir=REPO)
    with pytest.raises(SystemExit):
        main(["cap"] + base, repo_dir=REPO)
