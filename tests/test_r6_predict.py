"""Tests of the round-6 Predict stage (configs/r6_predict.yaml, src/prefixmeta/r6_predict.py, experiments/r6_predict_run.sh).

The spec is checked against the Validate stage's primary arm (same engine, workload, window); the analysis functions are checked by hand-computed cases;
one tiny end-to-end run (probe calls for every tag of the report, then ``report``) checks the plumbing and the cross-checks against the probe's own columns."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import probe
from prefixmeta import r6_predict as rp
from prefixmeta import r6_validate as rv
from prefixmeta.sim import deep_update

REPO = Path(__file__).resolve().parent.parent
SPEC = "configs/r6_predict.yaml"
VSPEC = "configs/r6_validate_stagec.yaml"
DRIVER = REPO / "experiments/r6_predict_run.sh"
SEP = rv.SEP


@pytest.fixture(scope="module")
def cfg() -> dict:
    return probe.load_probe_config(str(REPO / SPEC), REPO)


@pytest.fixture(scope="module")
def vcfg() -> dict:
    return rv.load_validation_config(str(REPO / VSPEC), REPO)


# ============================================================================ the spec equals the Validate stage's primary arm
def test_engine_is_the_validation_primary_arm_engine_in_both_batching_modes(cfg, vcfg):
    prim = vcfg["validate"]["arms"]["primary"]
    assert cfg["engine"] == deep_update(vcfg["engine"], rv.arm_engine(vcfg, prim, rv.MIXED))
    assert deep_update(cfg["engine"], {"batching": SEP}) == deep_update(vcfg["engine"], rv.arm_engine(vcfg, prim, SEP))
    cal = yaml.safe_load((REPO / vcfg["calibration_file"]).read_text())["engine"]
    for k, v in cal.items():
        assert cfg["engine"][k] == v, k
    assert cfg["engine"]["batching"] == "mixed" and cfg["engine"].get("alloc_mode", "full_reserve") == "full_reserve"


def test_workload_window_and_policy_equal_the_validation_spec(cfg, vcfg):
    assert cfg["workload"] == vcfg["workload"]
    assert cfg["metrics"]["window_s"] == vcfg["metrics"]["window_s"] == 100.0 and cfg["metrics"]["fine_window_s"] == vcfg["metrics"]["fine_window_s"]
    assert cfg["policies"]["fcfs_lru"] == vcfg["policies"]["fcfs_lru"]
    assert rp.expected_turns(cfg["workload"]) == pytest.approx(14.761, abs=5e-4)
    assert cfg["parallel"]["max_workers"] == 6
    only_here = {k for k in cfg["metrics"] if cfg["metrics"][k] != vcfg["metrics"].get(k)}
    assert only_here == {"tail_window_s"}            # the single declared difference of the metrics block


def test_probe_sections_and_the_driver_overrides_resolve(cfg):
    for sec in ("curve", "open", "burst"):
        probe.probe_section(cfg, sec, False)
    b1 = probe.probe_section(cfg, "curve", False)
    assert b1["n_grid"] == [32] and b1["seeds"] == [0, 1, 2] and b1["warmup_s"] == 900 and b1["horizon_s"] == 2700 and b1["cache_enabled"] is False
    c4 = probe.load_probe_config(str(REPO / SPEC), REPO, ["engine.batching=separate_prefill_priority", "engine.kv_memory_tokens=600000",
                                                          "probe.curve.cache_enabled=true", "probe.curve.n_grid=[16,24,32,48,64,96,300]", "probe.curve.seeds=[0]"])
    s4 = probe.probe_section(c4, "curve", False)
    assert c4["engine"]["batching"] == SEP and c4["engine"]["kv_memory_tokens"] == 600000 and s4["cache_enabled"] is True
    assert s4["n_grid"] == [16, 24, 32, 48, 64, 96, 300] and s4["seeds"] == [0]
    specs = probe.curve_specs(c4, s4)
    assert len(specs) == 7 and all(rs.plan.kind == "closed" and rs.engine_overrides["cache_enabled"] is True for rs in specs)
    o = probe.probe_section(cfg, "open", False)
    assert o["lambdas"] == [0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18, 0.20, 0.22] and o["horizon_s"] == 3000 and o["seeds"] == [0, 1, 2]
    os_ = probe.open_specs(cfg, o)
    assert len(os_) == 39 and all(rs.plan.kind == "constant" and rs.horizon_s == 3000 and rs.policy == "fcfs_lru" for rs in os_)
    assert probe._limit_cfg(o)["stable_trend_window_s"] == 1500 and probe._limit_cfg(o)["stable_final_backlog_below"] == 50


def test_burst_arms_match_the_b3_design(cfg):
    c = probe.load_probe_config(str(REPO / SPEC), REPO, ["probe.burst.lambda=0.12"])
    b = probe.probe_section(c, "burst", False)
    assert probe.burst_lambda(b)[0] == 0.12
    specs = probe.burst_specs(c, b)
    assert len(specs) == 9 and {rs.meta["arm"] for rs in specs} == {"no_burst", "burst", "burst_cap"}
    for rs in specs:
        assert rs.horizon_s == 8700 and rs.plan.rate == 0.12 and rs.plan.burst_t0 == 1200 and rs.plan.burst_width_s == 60
        assert rs.plan.burst_n == (0 if rs.meta["arm"] == "no_burst" else 200)
        assert rs.session_cap_override == (20 if rs.meta["arm"] == "burst_cap" else None)
    assert sorted({rs.seed for rs in specs}) == [0, 1, 2]
    # eval window = the last 2500 s = the probe's tail window and its hit_eval window
    assert 1200 + cfg["predict"]["b3"]["eval_window_s"][0] == 8700 - cfg["metrics"]["tail_window_s"] == 1200 + b["hit_eval_from_s"]
    assert 1200 + cfg["predict"]["b3"]["eval_window_s"][1] == 8700


def test_driver_script_lists_the_declared_grids():
    t = DRIVER.read_text()
    assert 'B3_LAMBDAS="0.09 0.10 0.11 0.12 0.13 0.14 0.16"' in t and "--workers 6" in t and "B4_GRID='[16,24,32,48,64,96,300]'" in t
    assert "[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119]" in t
    for kv in ("300 600 900",):
        assert kv in t


# ============================================================================ pure functions
def test_contiguous_edge_and_largest_all_stable():
    lams = [0.07, 0.08, 0.09, 0.10, 0.11]
    assert rp.contiguous_edge(lams, [True, True, True, False, True]) == 0.09              # the later all-stable 0.11 does not count
    assert rp.largest_all_stable(lams, [True, True, True, False, True]) == 0.11
    assert rp.contiguous_edge(lams, [False, True, True, True, True]) is None
    assert rp.contiguous_edge(lams, [True] * 5) == 0.11
    assert rp.contiguous_edge([0.09, 0.07, 0.08], [False, True, True]) == 0.08            # unsorted input


def _windows(n, *, t0=0.0, w=100.0, hit_n=10, adm=10, q=0.0, g=0.0, qslope=0.0, tok=1000.0):
    rows = []
    for i in range(n):
        rows.append({"t_start": t0 + i * w, "t_end": t0 + (i + 1) * w, "admitted_turns": adm, "hits": hit_n, "queue_mean": q + qslope * (i * w + w / 2),
                     "gate_mean": g, "prefill_tok_per_s": tok})
    return pd.DataFrame(rows)


def test_eval_stats_hand_values():
    w = _windows(30, q=5.0, g=2.0, qslope=0.01, tok=11500.0, hit_n=8, adm=10)            # backlog 7 + 0.01 t at the window centres
    s = rp.eval_stats(w, 500.0, 3000.0)
    assert s["n_windows"] == 25 and s["slope"] == pytest.approx(0.01) and s["token_rate"] == pytest.approx(11500.0) and s["hit"] == pytest.approx(0.8)
    centres = np.arange(25) * 100.0 + 550.0
    assert s["backlog"] == pytest.approx(float(np.mean(7.0 + 0.01 * centres)))
    only = rp.eval_stats(w, 600.0, 650.0)                                                # no complete window in [600, 650]
    assert only["n_windows"] == 0 and math.isnan(only["hit"])
    assert rp.eval_stats(_windows(2), 0.0, 200.0)["slope"] != rp.eval_stats(_windows(2), 0.0, 200.0)["slope"]    # < 3 windows -> NaN slope


P3 = {"trapped_token_rate_rel_tol": 0.15, "trapped_slope_frac": 0.5, "recovered_hit_above": 0.8, "recovered_backlog_below": 20.0}


def test_classify_cases():
    base = {"token_rate": 11000.0, "slope": 0.03, "hit": 0.0, "backlog": 300.0}
    # lambda 0.12, lambda_miss 0.08: threshold 0.5 * 0.04 = 0.02 requests / s
    c = rp.classify(base, 0.12, 0.08, 11500.0, P3)
    assert c["label"] == "TRAPPED" and c["slope_threshold"] == pytest.approx(0.02) and c["token_ratio"] == pytest.approx(11000 / 11500)
    assert rp.classify({**base, "slope": c["slope_threshold"]}, 0.12, 0.08, 11500.0, P3)["label"] == "neither"   # slope must EXCEED the threshold
    assert rp.classify({**base, "token_rate": 9000.0}, 0.12, 0.08, 11500.0, P3)["label"] == "neither"    # 9000 / 11500 = 0.783 < 0.85
    assert rp.classify({**base, "token_rate": 13200.0}, 0.12, 0.08, 11500.0, P3)["label"] == "TRAPPED"   # 1.148 <= 1.15
    assert rp.classify({**base, "token_rate": 13300.0}, 0.12, 0.08, 11500.0, P3)["label"] == "neither"   # 1.157 > 1.15
    good = {"token_rate": 4000.0, "slope": 0.0, "hit": 0.9, "backlog": 5.0}
    assert rp.classify(good, 0.12, 0.08, 11500.0, P3)["label"] == "RECOVERED"
    assert rp.classify({**good, "backlog": 20.0}, 0.12, 0.08, 11500.0, P3)["label"] == "neither"         # backlog must be < 20
    assert rp.classify({**good, "hit": 0.8}, 0.12, 0.08, 11500.0, P3)["label"] == "neither"              # hit must be > 0.8
    nan = {"token_rate": float("nan"), "slope": float("nan"), "hit": float("nan"), "backlog": 1.0}
    assert rp.classify(nan, 0.12, 0.08, 11500.0, P3)["label"] == "neither"                               # NaN never counts as trapped / recovered


def test_b3_verdicts_pass_rule():
    rows = []
    for lam, spec in ((0.10, dict(burst=[1, 1, 0], no_burst=[1, 1, 1], burst_cap=[1, 0, 1])), (0.12, dict(burst=[1, 0, 0], no_burst=[1, 1, 1], burst_cap=[1, 1, 1])),
                      (0.14, dict(burst=[1, 1, 1], no_burst=[0, 0, 1], burst_cap=[1, 1, 1]))):
        for arm, flags in spec.items():
            for sd, f in enumerate(flags):
                rows.append({"lam": lam, "arm": arm, "seed": sd, "trapped": bool(f) if arm == "burst" else False, "recovered": bool(f) if arm != "burst" else False})
    v = rp.b3_verdicts(pd.DataFrame(rows), 2.0 / 3.0).set_index("lam")
    assert v.loc[0.10, "need"] == 2 and bool(v.loc[0.10, "PASS"]) and not bool(v.loc[0.10, "PASS_all_seeds"])
    assert not bool(v.loc[0.12, "PASS"]) and v.loc[0.12, "burst_trapped"] == 1
    assert not bool(v.loc[0.14, "PASS"]) and v.loc[0.14, "noburst_good"] == 1
    assert v.loc[0.10, "cap_recovered"] == 2 and v.loc[0.14, "burst_trapped"] == 3
    assert rp.b3_verdicts(pd.DataFrame(rows[:0] + [{"lam": 0.1, "arm": a, "seed": s, "trapped": True, "recovered": True} for a in ("burst", "no_burst", "burst_cap") for s in (0, 1)]),
                          2.0 / 3.0).iloc[0]["need"] == 2                                  # 2 seeds -> both needed


def test_read_manifest_rejects_duplicates(tmp_path):
    p = tmp_path / "m.tsv"
    p.write_text("part\tcmd\ttag\tdir\nb1\tcurve\tt1\tx\nb1\tcurve\tt1\ty\n")
    with pytest.raises(ValueError, match="duplicate"):
        rp.read_manifest(p)


# ============================================================================ tiny end-to-end: probe calls for every tag, then `report`
def _tiny_spec(tmp_path: Path) -> Path:
    s = yaml.safe_load((REPO / SPEC).read_text())
    s["probe"]["curve"].update({"warmup_s": 100.0, "horizon_s": 300.0, "n_grid": [4], "seeds": [0, 1], "pool_sessions": 3000})
    s["probe"]["open"].update({"lambdas": [0.05, 0.10], "seeds": [0, 1], "horizon_s": 400.0, "stable_trend_window_s": 200.0})
    s["probe"]["burst"].update({"lambda": 0.10, "warmup_s": 200.0, "after_s": 600.0, "burst_n": 20, "cap": 5, "seeds": [0, 1], "hit_eval_from_s": 400.0,
                                "trap_min_s": 200.0})
    s["metrics"]["tail_window_s"] = 200.0
    s["predict"]["b1"]["reference_population"] = 4
    s["predict"]["b3"]["eval_window_s"] = [400.0, 600.0]
    s["predict"]["b3"]["sensitivity_eval_windows_s"] = [[500.0, 600.0], [200.0, 600.0]]
    p = tmp_path / "tiny.yaml"
    p.write_text(yaml.safe_dump(s, sort_keys=False))
    return p


def test_tiny_end_to_end_report(tmp_path):
    spec = _tiny_spec(tmp_path)
    root = tmp_path / "res"
    rows = []

    def call(part, cmd, tag, *extra, batching):
        before = set((root).glob("*")) if root.exists() else set()
        rc = probe.main([cmd, "--spec", str(spec), "--workers", "1", "--out-root", str(root), "--tag", tag, "--set", f"engine.batching={batching}", *extra],
                        repo_dir=REPO)
        assert rc == 0
        d = sorted((root / f"prefix_meta_probe_{cmd}_{tag}").iterdir())[-1]
        rows.append((part, cmd, tag, str(d)))

    for mt, b in (("mixed", "mixed"), ("sep", SEP)):
        call("b1", "curve", f"r6pred_b1pop32_{mt}", batching=b)
        call("b1", "curve", f"r6pred_b1pop64_{mt}", "--set", "probe.curve.n_grid=[8]", "--set", "probe.curve.seeds=[0]", batching=b)
        call("b2", "open", f"r6pred_b2_{mt}", batching=b)
        call("b2s", "open", f"r6pred_b2s20_{mt}", "--set", "probe.open.seeds=[5,6,7]", batching=b)
        call("b3", "burst", f"r6pred_b3_lam0.10_{mt}", batching=b)
        call("b3s", "burst", f"r6pred_b3s20_lam0.10_{mt}", "--set", "probe.burst.seeds=[5,6,7]", batching=b)
        call("b4", "curve", f"r6pred_b4_kv600k_{mt}", "--set", "engine.kv_memory_tokens=600000", "--set", "probe.curve.cache_enabled=true",
             "--set", "probe.curve.n_grid=[4,8]", "--set", "probe.curve.seeds=[0]", batching=b)
    man = tmp_path / "manifest.tsv"
    man.write_text("part\tcmd\ttag\tdir\n" + "".join("\t".join(r) + "\n" for r in rows))
    rc = rp.main(["report", "--spec", str(spec), "--manifest", str(man), "--out-root", str(root)], repo_dir=REPO)
    assert rc == 0
    d = sorted((root / "r6_predict_report").iterdir())[-1]
    for f in ("meta.json", "tables.md", "summary.json", "b1_seed.csv", "b2_table.csv", "b3_runs.csv", "b3_verdicts.csv", "b4_runs.csv"):
        assert (d / f).exists(), f
    summ = json.loads((d / "summary.json").read_text())
    b1 = pd.read_csv(d / "b1_seed.csv")
    for mode in (rv.MIXED, SEP):
        S = summ["modes"][mode]
        ref = b1[(b1["mode"] == mode) & (b1["n"] == 4)]
        assert S["b1"]["lambda_miss_turns"] == pytest.approx(ref["mu_turns"].mean()) and S["b1"]["token_rate"] == pytest.approx(ref["token_rate"].mean())
        assert S["b1"]["token_rate"] > 0 and S["b1"]["lambda_miss_turns"] > 0
        assert S["b3"]["check_hit_diff_max"] < 1e-9 and S["b3"]["check_backlog_diff_max"] < 1e-9        # same window as the probe's own columns
        assert set(S["b2"]["stable_fraction"]) == {"0.05", "0.1"}
    runs3 = pd.read_csv(d / "b3_runs.csv")
    assert set(runs3["arm"]) == {"no_burst", "burst", "burst_cap"} and len(runs3) == 2 * 3 * 2 and (runs3["n_windows"] == 2).all()
    sv = pd.read_csv(d / "b3_supp20_verdicts.csv")
    assert (sv["n_seeds"] == 3).all() and (sv["need"] == 2).all() and len(sv) == 2
    # the same E[T] estimator as the declared 14.761 (turns-based mu = turns_per_s / E[T])
    assert summ["E_T"] == pytest.approx(14.761, abs=5e-4)
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "done" and len(meta["git"]["commit"]) == 40


def test_b4_landmarks_hand_case():
    rows = [dict(mode="mixed", kv_k=600, seed=s, n=n, mu=mu + 0.01 * s, hit_rate=hit)
            for s in (0, 1) for n, mu, hit in ((16, 0.17, 0.93), (24, 0.25, 0.93), (48, 0.40, 0.92), (64, 0.10, 0.30), (300, 0.10, 0.0))]
    lm = rp.b4_landmarks(pd.DataFrame(rows)).set_index("seeds")
    s0 = lm.loc["seed 0"]
    assert s0["peak_n"] == 48 and s0["peak_mu"] == pytest.approx(0.40) and s0["mu_300"] == pytest.approx(0.10) and s0["n_seeds"] == 1
    assert s0["hit_crossing_n"] == pytest.approx(48 + 16 * (0.92 - 0.5) / (0.92 - 0.30))
    both = lm.loc["seeds 0-1 mean"]
    assert both["n_seeds"] == 2 and both["peak_mu"] == pytest.approx(0.405) and math.isnan(lm.loc["seed 0", "mu_96"])
