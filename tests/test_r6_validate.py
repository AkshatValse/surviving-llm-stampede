"""Tests of the round-6 validation harness (src/prefixmeta/r6_validate.py, configs/r6_validate_stagec.yaml).

Pure comparison functions are checked by hand-computed cases; the config is checked against the Stage C harness config and the calibration file;
the plumbing is checked by equality with a direct ``simulate`` call on the same spec (not by approximation); one quick CLI run writes a result dir."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r6_validate as rv
from prefixmeta.r4_runner import closed_spec
from prefixmeta.r5_runner import point_metrics_r5
from prefixmeta.sim import deep_update, simulate

REPO = Path(__file__).resolve().parent.parent
SPEC = "configs/r6_validate_stagec.yaml"
SEP = rv.SEP


@pytest.fixture(scope="module")
def cfg() -> dict:
    return rv.load_validation_config(str(REPO / SPEC), REPO)


# ============================================================================ pure functions
def test_rel_err_and_nan_handling():
    assert rv.rel_err(0.12, 0.10) == pytest.approx(0.2)
    assert rv.rel_err(0.05, 0.10) == pytest.approx(-0.5)
    assert math.isnan(rv.rel_err(0.1, 0.0)) and math.isnan(rv.rel_err(float("nan"), 0.1))


def test_first_argmax_ties_runner_up_and_unsorted_input():
    assert rv.first_argmax([32, 16, 24], [0.1, 0.2, 0.2]) == (16, 0.2)          # tie -> smallest n; input order is irrelevant
    assert rv.runner_up([16, 20, 24], [0.176, 0.224, 0.233]) == (20, 0.224)
    assert rv.runner_up([16, 20, 24], [0.3, 0.224, 0.233]) == (24, 0.233)


def test_crossing_linear_interpolation_matches_the_stage_c_value():
    # real FCFS hit (Stage C): 0.93, 0.93, 0.89, 0.505 at 16..32 then 0 at 48: the crossing is in (32, 48), the logged value 32.2
    ns = [16, 20, 24, 32, 48, 96, 300]
    hit = [0.9321, 0.9268, 0.8877, 0.5052, 0.0, 0.0, 0.0]
    assert rv.crossing(ns, hit, 0.5) == pytest.approx(32 + 16 * (0.5052 - 0.5) / 0.5052)
    assert 32.1 < rv.crossing(ns, hit, 0.5) < 32.3
    assert rv.crossing([8, 16, 24], [0.9, 0.7, 0.3], 0.5) == pytest.approx(20.0)  # hand: 16 + 8 * (0.7 - 0.5) / (0.7 - 0.3)
    assert math.isnan(rv.crossing([8, 16], [0.4, 0.2], 0.5))                      # already below at the smallest n
    assert math.isnan(rv.crossing([8, 16], [0.9, 0.8], 0.5))                      # never crosses
    assert rv.crossing([16, 8], [0.2, 0.9], 0.5) == pytest.approx(8 + 8 * 0.4 / 0.7)   # sorted internally


def test_collapse_ratio_uses_the_grid_maximum():
    d = rv.collapse_ratio([16, 24, 48, 300], [0.17, 0.25, 0.05, 0.10])
    assert d["mu_star"] == 0.25 and d["mu_300_over_star"] == pytest.approx(0.4) and d["mu_48_over_star"] == pytest.approx(0.2)
    assert math.isnan(rv.collapse_ratio([16, 24], [0.1, 0.2])["mu_300_over_star"])


def test_summarize_curve_flags_an_ambiguous_peak():
    tab = pd.DataFrame({"n": [16, 20, 24, 32, 48, 300], "mu": [0.176, 0.224, 0.233, 0.115, 0.049, 0.108],
                        "hit": [0.93, 0.93, 0.89, 0.51, 0.0, 0.0]})
    s = rv.summarize_curve(tab, "mu", "hit", runner_up_frac=0.05, level=0.5)
    assert s["peak_n"] == 24 and s["runner_up_n"] == 20 and s["peak_ambiguous"]            # (0.233 - 0.224) / 0.233 = 3.9% < 5%
    assert s["mu_300_over_star"] == pytest.approx(0.108 / 0.233)
    s2 = rv.summarize_curve(tab.assign(mu=[0.1, 0.3, 0.2, 0.1, 0.05, 0.1]), "mu", "hit", runner_up_frac=0.05, level=0.5)
    assert s2["peak_n"] == 20 and not s2["peak_ambiguous"]


def test_pick_mode_lower_error_wins():
    summ = {rv.MIXED: {"mean_abs_rel_err_mu": 0.4}, SEP: {"mean_abs_rel_err_mu": 0.2}}
    assert rv.pick_mode(summ)["closer"] == SEP
    assert rv.pick_mode({rv.MIXED: summ[rv.MIXED]})["closer"] is None


# ============================================================================ configuration
def test_workload_and_protocol_equal_the_stage_c_harness_config(cfg):
    sc = yaml.safe_load((REPO / "configs/agentload_c_closed.yaml").read_text())
    for k, v in sc["workload"].items():
        if k in cfg["workload"]:
            assert cfg["workload"][k] == v, k
    assert cfg["workload"]["initial_context_tokens"] == 2000 and cfg["workload"]["new_prompt_tokens"] + cfg["workload"]["decode_tokens"] == 650
    pr = cfg["validate"]["protocol"]
    assert pr["warmup_s"] == 900 and pr["horizon_s"] == 2700 and sc["run"]["duration_s"] == 2700 and pr["synchronized_start"] is True
    assert sc["arrivals"]["kind"] == "closed"
    grid = {c["policy"]: c["n"] for c in cfg["validate"]["cells"]}
    assert grid == {"fcfs_lru": [16, 20, 24, 32, 48, 96, 300], "lpm128_lru": [48, 300]}
    assert cfg["validate"]["seeds"] == [0, 1, 2]
    assert cfg["policies"]["lpm128_lru"] == {"kind": "lpm_fallback", "threshold": 128, "eviction": "lru"}


def test_calibration_constants_are_merged_over_the_base_engine(cfg):
    cal = yaml.safe_load((REPO / cfg["calibration_file"]).read_text())["engine"]
    for k, v in cal.items():
        assert cfg["engine"][k] == v, k
    e = cfg["engine"]
    assert e["iter_fixed_s"] == 0.00924 and e["prefill_attn_ctx"] == "mid" and e["kv_memory_tokens"] == 300000
    assert e.get("batching", "mixed") == "mixed" and e.get("alloc_mode", "full_reserve") == "full_reserve"   # the arms set `batching`
    assert len(cfg["_calibration_sha256"]) == 64


def test_arms_are_valid_and_the_primary_arm_changes_nothing_but_batching(cfg):
    arms = cfg["validate"]["arms"]
    assert rv.arm_engine(cfg, arms["primary"], rv.MIXED) == {"batching": "mixed"}
    assert rv.arm_engine(cfg, arms["primary"], SEP) == {"batching": SEP}
    s1 = rv.arm_engine(cfg, arms["S1_ratio_reserve"], SEP)
    assert s1["alloc_mode"] == "ratio_reserve" and s1["init_new_token_ratio"] == 0.7 and s1["batching"] == SEP
    s4 = rv.arm_engine(cfg, arms["S4_sglang_like"], rv.MIXED)
    assert s4["alloc_mode"] == "ratio_reserve" and s4["free_kv_on_session_end"] is False
    assert arms["S3_decode_per_seq"]["batching_modes"] == [SEP]                      # the key is ignored in mixed mode
    assert rv.arm_engine(cfg, arms["S3_decode_per_seq"], SEP)["decode_per_seq_s"] == 4.351e-05


def test_window_tiling_is_enforced(tmp_path):
    spec = yaml.safe_load((REPO / SPEC).read_text())
    spec["metrics"]["window_s"] = 700.0
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(spec, sort_keys=False))
    with pytest.raises(ValueError, match="multiple"):
        rv.load_validation_config(str(p), REPO)


# ============================================================================ real data
@pytest.mark.skipif(not (REPO / "results/nova/stageC_1706210x_pulled_20261022-125454").exists(), reason="Stage C pulled data not available")
def test_real_values_equal_the_stage_c_table(cfg):
    real = rv.load_real(cfg, REPO).set_index(["policy", "n"])
    mu = {16: 0.176, 20: 0.224, 24: 0.233, 32: 0.115, 48: 0.049, 96: 0.061, 300: 0.108}
    hit = {16: 0.93, 20: 0.93, 24: 0.89, 32: 0.51, 48: 0.0, 96: 0.0, 300: 0.0}
    for n in mu:
        assert real.loc[("fcfs_lru", n), "real_mu"] == pytest.approx(mu[n], abs=6e-4)
        assert real.loc[("fcfs_lru", n), "real_hit"] == pytest.approx(hit[n], abs=6e-3)
    assert real.loc[("lpm128_lru", 48), "real_mu"] == pytest.approx(0.087, abs=6e-4)
    assert real.loc[("lpm128_lru", 48), "real_hit"] == pytest.approx(0.385, abs=6e-4)
    assert real.loc[("lpm128_lru", 300), "real_mu"] == pytest.approx(0.105, abs=6e-4)
    assert len(real) == 9


# ============================================================================ plumbing
def test_run_cells_equals_a_direct_simulate_call(cfg):
    """probe.run_curve + the arm overrides must give exactly the numbers of simulate() on the same closed spec (both batching modes)."""
    for b in (rv.MIXED, SEP):
        got = rv.run_cells(cfg, "primary", b, [("fcfs_lru", [16])], [0], workers=1).iloc[0]
        eng = deep_update(cfg["engine"], {"batching": b})
        cfg2 = {**cfg, "engine": eng}
        pr = cfg["validate"]["protocol"]
        rs = closed_spec("fcfs_lru", 16, 1.0, 0, {"horizon_s": pr["horizon_s"], "pool_sessions_per_k": pr["pool_sessions"]}, eng)
        res = simulate(cfg2, rs)
        pm = point_metrics_r5(res["windows"], pr["warmup_s"], pr["horizon_s"], cfg["metrics"]["window_s"])
        assert got["mu"] == pm["mu"] and got["hit_rate"] == pm["hit_rate"] and got["batching"] == b
        assert got["n_windows"] == 18                                                  # [900, 2700) in 100 s windows
        assert got["mu_turns"] == pytest.approx(pm["turns_per_s"] / 14.7, rel=0.01)    # E[min(Geom(1/15), 60)] = 14.7


def test_separate_mode_differs_from_mixed_in_the_loaded_regime(cfg):
    a = rv.run_cells(cfg, "primary", rv.MIXED, [("fcfs_lru", [24])], [0], 1).iloc[0]
    b = rv.run_cells(cfg, "primary", SEP, [("fcfs_lru", [24])], [0], 1).iloc[0]
    assert a["mu"] != b["mu"] or a["gpu_busy"] != b["gpu_busy"]


def test_quick_cli_run_writes_a_complete_result_dir(tmp_path):
    rc = rv.main(["run", "--spec", str(REPO / SPEC), "--quick", "--workers", "1", "--out-root", str(tmp_path)], repo_dir=REPO)
    assert rc == 0
    d = next((tmp_path / "r6_validate_stagec_quick").iterdir())
    for f in ("meta.json", "config.yaml", "config_effective.yaml", "runs.csv", "cell_table.csv", "summary.json", "tables.md", "real_stagec.csv"):
        assert (d / f).exists(), f
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "done" and meta["seeds"] == [0] and len(meta["git"]["commit"]) == 40 and meta["refresh_modelled"] is False
    tab = pd.read_csv(d / "cell_table.csv")
    assert set(tab["batching"]) == {rv.MIXED, SEP} and set(tab["arm"]) == {"primary"} and len(tab) == 6   # 3 cells x 2 batching modes
    assert tab["rel_err_mu"].notna().all()


# ============================================================================ report helpers
def test_md_tables_show_na_for_a_batching_mode_an_arm_does_not_have():
    row = {"arm": "S3", "batching": SEP, "policy": "fcfs_lru", "n": 16, "mu_mean": 0.17, "mu_se": 0.01, "real_mu": 0.176, "rel_err_mu": -0.034,
           "real_mu_turns": 0.176, "rel_err_mu_turns": -0.03, "hit_mean": 0.93, "real_hit": 0.932, "abs_err_hit": -0.002}
    md = rv.md_main_table(pd.DataFrame([row]), "S3")
    line = md.splitlines()[-1]
    assert "n/a (n/a)" in line and "0.170 (0.010)" in line and "-3.4%" in line            # mixed columns n/a, separate columns filled
    hit = rv.md_hit_table(pd.DataFrame([row]), "S3").splitlines()[-1]
    assert "| n/a | n/a | 0.930 | -0.002 |" in hit


def test_zscore_table_hand_values():
    runs = pd.DataFrame({"arm": "primary", "batching": rv.MIXED, "policy": "fcfs_lru", "n": 24, "seed": [0, 1, 2, 3],
                         "mu": [0.20, 0.22, 0.24, 0.26], "mu_turns": [0.2, 0.2, 0.2, 0.2], "hit_rate": [0.8, 0.9, 0.9, 0.8]})
    real = pd.DataFrame({"policy": ["fcfs_lru"], "n": [24], "real_mu": [0.233], "real_mu_turns": [0.21], "real_hit": [0.89]})
    z = rv.zscore_table(runs, real).iloc[0]
    sd = float(np.std([0.20, 0.22, 0.24, 0.26], ddof=1))                                  # 0.0258199
    assert z["mu_sim_mean"] == pytest.approx(0.23) and z["mu_sim_sd"] == pytest.approx(sd)
    assert z["mu_z"] == pytest.approx((0.233 - 0.23) / sd) and z["mu_frac_sim_le_real"] == 0.5     # 0.20 and 0.22 are <= 0.233
    assert math.isnan(z["mu_turns_z"])                                                     # zero spread -> NaN, not inf
    assert z["hit_sim_mean"] == pytest.approx(0.85)


def test_report_writes_new_files_and_never_overwrites(tmp_path):
    rv.main(["run", "--spec", str(REPO / SPEC), "--quick", "--workers", "1", "--out-root", str(tmp_path)], repo_dir=REPO)
    d = next((tmp_path / "r6_validate_stagec_quick").iterdir())
    before = {f.name: f.read_bytes() for f in d.iterdir()}
    rv.main(["report", "--run-dir", str(d)], repo_dir=REPO)
    assert (d / "report.md").exists() and (d / "zscores_registered_seeds.csv").exists() and (d / "report_meta.json").exists()
    for name, content in before.items():                                                   # nothing that existed was touched
        assert (d / name).read_bytes() == content, name
    with pytest.raises(FileExistsError):
        rv.main(["report", "--run-dir", str(d)], repo_dir=REPO)


def test_zscore_markdown_shows_na_for_an_undefined_z_not_nan():
    runs = pd.DataFrame({"arm": "primary", "batching": [rv.MIXED, SEP, SEP, SEP], "policy": "fcfs_lru", "n": 24, "seed": [0, 0, 1, 2],
                         "mu": [0.2, 0.21, 0.23, 0.25], "mu_turns": [0.2] * 4, "hit_rate": [0.9] * 4})   # mixed: ONE seed; separate: three seeds
    real = pd.DataFrame({"policy": ["fcfs_lru"], "n": [24], "real_mu": [0.233], "real_mu_turns": [0.21], "real_hit": [0.89]})
    md = rv.md_zscore_table(rv.zscore_table(runs, real), "primary")
    mixed_line, sep_line = md.splitlines()[-2:]
    assert "nan" not in md.lower()
    assert mixed_line.split("|")[3].strip() == "24" and mixed_line.split("|")[6].strip() == "n/a"      # one seed: sd undefined -> z shown as n/a
    assert sep_line.split("|")[6].strip() == "+0.15"                                                  # (0.233 - 0.23) / 0.02
    assert sep_line.split("|")[10].strip() == "n/a"                                                   # turns column has zero spread across seeds


def test_report_refuses_an_unfinished_run_dir(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"status": "running"}))
    with pytest.raises(ValueError, match="not a finished run"):
        rv.cmd_report(tmp_path, REPO)
