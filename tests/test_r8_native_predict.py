"""configs/r8_native_predict.yaml (blind native-pool predictions with the round-7 stages) and src/prefixmeta/r8_native_report.py.

* the spec is the declared pre-registration: it differs from configs/r7_robustness.yaml in exactly the declared ways (KV pool, one workload, the grids, the stages);
* the pure helpers of the report (landmarks, edge censoring, E0b rows, burst sensitivity) on small synthetic frames;
* every stage of the spec, both batching modes, the burst-size sensitivity at the edge stage's points, the r7 and r8 reports and the assembly run end to end on a
  tiny scaled-down copy of the REAL spec.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r7_report as RP
from prefixmeta import r7_robustness as R7
from prefixmeta import r8_native_report as R8
from prefixmeta.probe import load_probe_config
from prefixmeta.workload import WorkloadParams

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "configs" / "r8_native_predict.yaml"
OLD = REPO / "configs" / "r7_robustness.yaml"


def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- the spec is pinned to its declaration
def test_the_only_engine_change_is_the_kv_pool_and_it_is_the_one_real_fact():
    a, b = load(SPEC), load(OLD)
    assert a["engine"]["kv_memory_tokens"] == 955757 and a["r8"]["kv_pool_tokens"] == 955757
    assert {k: v for k, v in a["engine"].items() if k != "kv_memory_tokens"} == {k: v for k, v in b["engine"].items() if k != "kv_memory_tokens"}
    assert a["engine"]["batching"] == "mixed" and a["engine"]["cache_enabled"] is True
    for k in ("base_config", "workload", "metrics", "parallel"):
        assert a[k] == b[k], k
    cfg = load_probe_config(str(SPEC), REPO)
    assert cfg["engine"]["kv_memory_tokens"] == 955757
    wl = WorkloadParams.from_dict(cfg["workload"])
    assert (wl.initial_context_tokens, wl.new_prompt_tokens, wl.decode_tokens, wl.mean_turns, wl.max_turns) == (2000, 550, 100, 15, 60)
    assert R7.expected_turns(cfg, cfg["r7"], "exp5") == pytest.approx(14.761, abs=5e-4)


def test_everything_else_of_the_r7_block_is_the_round7_declaration_except_the_declared_differences():
    a, b = load(SPEC)["r7"], load(OLD)["r7"]
    for k in ("policy", "expected_turns", "wilson_z", "window", "classify", "lambda_miss", "record_workload"):
        assert a[k] == b[k], k
    assert list(a["workloads"]) == ["exp5"] and a["workloads"]["exp5"]["workload"] == b["workloads"]["exp5"]["workload"]
    assert a["stages"] == ["lambda_miss", "curves", "edge", "pairs", "burst_sizes"]
    assert a["curve"]["n_grid"] == [16, 24, 32, 48, 64, 72, 80, 88, 96, 112, 128, 160, 300]
    assert {k: v for k, v in a["curve"].items() if k != "n_grid"} == {k: v for k, v in b["curve"].items() if k != "n_grid"}
    assert a["edge"]["multiples"] == [1.5 + 0.5 * i for i in range(13)] and a["edge"]["multiples"][-1] == 7.5
    assert {k: v for k, v in a["edge"].items() if k != "multiples"} == {k: v for k, v in b["edge"].items() if k != "multiples"}
    assert a["edge"]["seeds"] == list(range(10)) and a["edge"]["horizon_s"] == 3000.0 and a["lambda_miss"]["population"] == 32 and a["lambda_miss"]["check_populations"] == [64]
    assert a["lambda_miss"]["seeds"] == a["curve"]["seeds"] == [0, 1, 2]
    assert a["pairs"] == b["pairs"] and a["pairs"]["burst_n"] == 200 and a["pairs"]["seeds"] == list(range(10))
    assert a["burst_sizes"]["multiples"] is None and a["burst_sizes"]["sizes"] == [200, 400]       # the driver sets the multiples from the edge stage's points


def test_the_e0b_grid_is_a_subset_of_the_edge_multiples_and_the_modes_are_declared_primary_first():
    s = load(SPEC)
    assert s["r8"]["e0b_grid"] == [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    assert set(s["r8"]["e0b_grid"]) <= set(s["r7"]["edge"]["multiples"])
    modes = s["r8"]["modes"]
    assert list(modes) == ["mixed", "separate"]
    assert modes["mixed"]["batching"] == "mixed" and modes["separate"]["batching"] == "separate_prefill_priority"
    assert modes["mixed"]["out_root"] != modes["separate"]["out_root"]
    cfg = load_probe_config(str(SPEC), REPO, ["engine.batching=separate_prefill_priority"])           # the override the driver uses is valid
    assert cfg["engine"]["batching"] == "separate_prefill_priority"


# ----------------------------------------------------------------------------- pure helpers
def curve_summary():
    ns = [16, 24, 32, 48, 64, 96, 300]
    mu = {16: 0.18, 24: 0.25, 32: 0.33, 48: 0.43, 64: 0.40, 96: 0.08, 300: 0.11}
    hit = {16: 0.93, 24: 0.93, 32: 0.93, 48: 0.92, 64: 0.6, 96: 0.0, 300: 0.0}
    return {"peak_n": 48, "peak_mu_turns": 0.43, "cap_n": 48, "peak_n_sessions_based": 48, "peak_mu_sessions": 0.42, "cap_n_sessions_based": 48,
            "mu_turns_by_n": {str(n): mu[n] for n in ns}, "hit_by_n": {str(n): hit[n] for n in ns}}


def test_curve_landmarks_are_the_peak_the_cap_and_the_interpolated_crossings():
    cs = curve_summary()
    runs = pd.DataFrame([{"n": n, "seed": s, "hit_rate": cs["hit_by_n"][str(n)] + d} for n in map(int, cs["hit_by_n"]) for s, d in ((0, 0.0), (1, -0.02))])
    lm = R8.curve_landmarks(cs, runs, [0.5, 0.9, 0.2])
    assert (lm["peak_n"], lm["cap_n"], lm["peak_mu_turns"], lm["hit_at_peak"], lm["last_n"]) == (48, 48, 0.43, 0.92, 300)
    # hit 0.92 at n = 48 and 0.6 at n = 64: the 0.9 level is crossed at 48 + 16 * (0.92 - 0.9) / 0.32 = 49; 0.5 between 64 (0.6) and 96 (0.0): 64 + 32 * 0.1 / 0.6
    assert lm["hit_crossing"]["0.9"] == pytest.approx(48 + 16 * 0.02 / 0.32) and lm["hit_crossing"]["0.5"] == pytest.approx(64 + 32 * 0.1 / 0.6)
    assert lm["hit_crossing"]["0.2"] == pytest.approx(64 + 32 * 0.4 / 0.6)
    assert lm["largest_n_with_hit_at_least_top_level"] == 48 and lm["mu_last_over_peak"] == pytest.approx(0.11 / 0.43)
    assert set(lm["hit_crossing_first_level_by_seed"]) == {0, 1} and lm["hit_crossing_first_level_by_seed"][0] == pytest.approx(64 + 32 * 0.1 / 0.6)
    assert lm["hit_crossing_first_level_by_seed"][1] < lm["hit_crossing_first_level_by_seed"][0]          # the lower seed falls through 0.5 earlier


def verdicts(stable_by_mult: dict, n: int = 10) -> pd.DataFrame:
    rows = []
    for m, k in stable_by_mult.items():
        for i in range(n):
            rows.append({"lam_mult": m, "lam": 0.0722 * m, "stable": i < k, "final_backlog": 0.0 if i < k else 100.0, "tail_hit_rate": 0.93 if i < k else 0.2,
                         "trend_rise": 0.0, "stopped_early": False})
    return pd.DataFrame(rows)


def test_the_edge_is_reported_in_multiples_and_sessions_per_second_and_flagged_when_censored():
    v = verdicts({1.5: 10, 2.0: 10, 2.5: 10, 3.0: 9, 3.5: 10, 4.0: 4})
    es = {"hi": 2.5, "hi_largest_all_stable": 3.5, "contiguous_equals_largest": False, "points": [1.5, 2.0], "window_empty": False}
    e = R8.edge_landmarks(es, v, 0.0722)
    assert e["hi"] == 2.5 and e["hi_sessions_per_s"] == pytest.approx(2.5 * 0.0722) and not e["censored_at_grid_top"] and e["hi_largest_all_stable"] == 3.5
    assert e["n_stable_by_mult"]["3"] == 9 and e["stable_frac_by_mult"]["4"] == pytest.approx(0.4) and e["points"] == [1.5, 2.0]
    assert e["stable_frac_crossing_0.5"] == pytest.approx(3.5 + 0.5 * (1.0 - 0.5) / (1.0 - 0.4))          # 1.0 at 3.5 x falls to 0.4 at 4.0 x
    allst = verdicts({1.5: 10, 2.0: 10, 2.5: 10})
    c = R8.edge_landmarks({"hi": 2.5, "hi_largest_all_stable": 2.5, "contiguous_equals_largest": True, "points": [1.5, 2.0], "window_empty": False}, allst, 0.0722)
    assert c["censored_at_grid_top"] and c["grid_top"] == 2.5 and np.isnan(c["stable_frac_crossing_0.5"])


def test_the_e0b_rows_read_the_stable_fraction_at_exactly_the_grid_and_refuse_a_multiple_that_was_not_run():
    v = verdicts({1.5: 10, 2.0: 10, 2.5: 9, 3.0: 5, 3.5: 2})
    t = R8.e0b_rows(v, [1.5, 2.5, 3.5])
    assert list(t["stable fraction"]) == [1.0, 0.9, 0.2, pytest.approx(21 / 30)]
    assert t["stable runs"].iloc[1].startswith("9/10 (0.90) [0.60, 0.98]") and t["stable runs"].iloc[-1].startswith("21/30")
    with pytest.raises(ValueError, match="was not run"):
        R8.e0b_rows(v, [1.5, 4.5])


def test_the_burst_sensitivity_counts_the_arms_per_multiple_and_size():
    rows = []
    for arm, labels in (("no_burst", "R" * 10), ("burst_200", "T" * 9 + "I"), ("burst_400", "T" * 5 + "I" * 5)):
        for seed, lab in enumerate(labels):
            rows.append({"mult": 2.0, "arm": arm, "seed": seed, "label": lab and {"T": "TRAPPED", "I": "INDETERMINATE", "R": "RECOVERED"}[lab], "trapped": lab == "T",
                         "recovered": lab == "R", "indeterminate": lab == "I", "hit": 0.93 if lab == "R" else 0.0, "backlog": 0.01 if lab == "R" else 300.0})
    t = R8.burst_sensitivity(pd.DataFrame(rows), [200, 400], 0.2)
    assert list(t["burst size"]) == [0, 200, 400] and list(t["indeterminate"]) == [0, 1, 5]
    assert t["trapped"].iloc[1].startswith("9/10 (0.90)") and t["trapped"].iloc[2].startswith("5/10 (0.50)") and t["recovered"].iloc[0].startswith("10/10")
    assert t["stuck (hit < 0.2)"].iloc[2].startswith("10/10") and t["classes by seed"].iloc[2] == "TTTTTIIIII"


# ----------------------------------------------------------------------------- end to end on a tiny scaled-down copy of the REAL spec
def tiny_spec(tmp_path: Path) -> Path:
    raw = load(SPEC)
    r7 = raw["r7"]
    r7["lambda_miss"].update(seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["curve"].update(n_grid=[8, 16, 32, 64], seeds=[0, 1], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["edge"].update(multiples=[1.5, 2.5, 3.5], seeds=[0, 1], horizon_s=1500.0, stable_trend_window_s=500.0)
    r7["pairs"].update(seeds=[0, 1], burst_n=60, warmup_s=300.0, after_s=1200.0)
    r7["classify"]["eval_window_rel_to_burst_s"] = [700.0, 1200.0]
    r7["burst_sizes"].update(seeds=[0, 1], warmup_s=300.0, after_s=1200.0, sizes=[60, 120])
    raw["r8"]["e0b_grid"] = [1.5, 2.5, 3.5]
    raw["r8"]["modes"]["mixed"]["out_root"] = str(tmp_path / "res_mixed")
    raw["r8"]["modes"]["separate"]["out_root"] = str(tmp_path / "res_sep")
    p = tmp_path / "tiny_r8.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return p


def run_mode(spec: Path, out: str, sets: list):
    def run(stage, extra=()):
        argv = [stage, "--spec", str(spec), "--workers", "1", "--out-root", out]
        for s in sets:
            argv += ["--set", s]
        assert R7.main(argv + list(extra), repo_dir=REPO) == 0

    for st in ("lambda_miss", "curves", "edge"):
        run(st)
    ed_dir = R7.stage_dir(out, "edge")
    ed = json.loads((ed_dir / "summary.json").read_text())
    ed["workloads"]["exp5"].update(hi=2.5, points=[1.5, 2.0], window_empty=False)          # a fixed, non-empty window for the tiny run
    (ed_dir / "summary.json").write_text(json.dumps(ed))
    run("pairs")
    pts = R8.test_points(out)
    assert pts == [1.5, 2.0]
    run("burst_sizes", ["--set", "r7.burst_sizes.multiples=" + json.dumps(pts)])


def test_both_modes_all_stages_the_sensitivity_the_reports_and_the_assembly_run_end_to_end_on_a_tiny_copy(tmp_path, capsys):
    spec = tiny_spec(tmp_path)
    cfg = load_probe_config(str(spec), REPO)
    run_mode(spec, cfg["r8"]["modes"]["mixed"]["out_root"], [])
    run_mode(spec, cfg["r8"]["modes"]["separate"]["out_root"], ["engine.batching=separate_prefill_priority"])
    mx = json.loads((R7.stage_dir(cfg["r8"]["modes"]["mixed"]["out_root"], "lambda_miss") / "meta.json").read_text())
    sp = json.loads((R7.stage_dir(cfg["r8"]["modes"]["separate"]["out_root"], "lambda_miss") / "meta.json").read_text())
    assert mx["overrides"] == [] and sp["overrides"] == ["engine.batching=separate_prefill_priority"]
    eff = yaml.safe_load((R7.stage_dir(cfg["r8"]["modes"]["separate"]["out_root"], "curves") / "config_effective.yaml").read_text())
    assert eff["engine"]["batching"] == "separate_prefill_priority" and eff["engine"]["kv_memory_tokens"] == 955757
    # the 200-session arm of the sensitivity stage is bit-identical to the BURST arm of the pairs stage (same seeds, same point): the consistency check of the report
    pr = pd.read_csv(R7.stage_dir(cfg["r8"]["modes"]["mixed"]["out_root"], "pairs") / "classified_runs.csv")
    assert set(R7.stage_summary(cfg["r8"]["modes"]["mixed"]["out_root"], "burst_sizes")["by_mult"]) == {"1.5", "2"} and set(pr["arm"]) == {"burst", "no_burst", "burst_cap"}

    out = str(tmp_path / "res_report")
    d = Path(R8.main(["report", "--spec", str(spec), "--out-root", out], repo_dir=REPO))
    text = (d / "tables.md").read_text(encoding="utf-8")
    assert text.index("## Mode `mixed` (PRIMARY)") < text.index("## Mode `separate` (SECONDARY)")
    for h in ("### B1n.", "### B4n.", "### B2n.", "### B3n. Paired", "### B3n sensitivity (NOT the registered burst)"):
        assert text.count(h) == 2, h
    assert "NOT RUN" not in text and "Stable fraction at exactly the real E0b grid" in text and "pooled over the grid" in text
    assert "Landmarks of the closed curve" in text and "falls through 0.5" in text and "Per-seed values" in text
    head = json.loads((d / "summary.json").read_text())
    for mode in ("mixed", "separate"):
        h = head[mode]
        assert set(h) >= {"B1n", "B4n", "B2n", "B2n_e0b", "B3n", "B3n_burst_sensitivity"}
        assert h["B1n"]["lambda_miss_turns"] > 0.05 and h["B1n"]["busy"] > 0.9 and h["B4n"]["peak_n"] in (8, 16, 32, 64) and h["B4n"]["cap_n"] <= h["B4n"]["peak_n"]
        assert set(h["B2n_e0b"]) == {"1.5", "2.5", "3.5", "pooled"} and h["B3n"]["points"].keys() == {"1.5", "2"}
        assert set(h["B3n_burst_sensitivity"]) == {"1.5", "2"} and set(h["B3n_burst_sensitivity"]["1.5"]["per_size"]) == {"60", "120"}
    prov = (d / "provenance.md").read_text(encoding="utf-8")
    assert "**mixed** (`engine.batching` = `mixed`" in prov and "**separate** (`engine.batching` = `separate_prefill_priority`" in prov
    # (in-process runs record pytest's argv, so the overrides column is what carries the --set values here)
    assert "955,757" in prov and "engine.batching=separate_prefill_priority" in prov and "r7.burst_sizes.multiples=[1.5, 2.0]" in prov
    notes, hl = tmp_path / "notes.md", tmp_path / "head.md"
    hl.write_text("HEADLINE", encoding="utf-8")
    R8.main(["assemble", "--spec", str(spec), "--out-root", out, "--headline", str(hl), "--notes", str(notes)], repo_dir=REPO)
    t = notes.read_text(encoding="utf-8")
    assert t.startswith("# Round 8: blind predictions of the calibrated simulator for the native-KV-pool experiments (KV pool 955,757 tokens)\n\nHEADLINE") and "## Tables (generated)" in t


def test_the_report_marks_a_mode_that_was_not_run_instead_of_dropping_it(tmp_path):
    spec = tiny_spec(tmp_path)
    cfg = load_probe_config(str(spec), REPO)
    out_root = cfg["r8"]["modes"]["mixed"]["out_root"]
    assert R7.main(["lambda_miss", "--spec", str(spec), "--workers", "1", "--out-root", out_root], repo_dir=REPO) == 0
    with pytest.raises(TypeError):                           # a burst-size run without the driver's --set r7.burst_sizes.multiples=[...] fails loudly (multiples: null)
        R7.main(["burst_sizes", "--spec", str(spec), "--workers", "1", "--out-root", out_root], repo_dir=REPO)
    d = Path(R8.main(["report", "--spec", str(spec), "--out-root", str(tmp_path / "rep")], repo_dir=REPO))
    text = (d / "tables.md").read_text(encoding="utf-8")
    assert "**stage `curves` NOT RUN**" in text and "**stage `edge` NOT RUN**" in text and "**stage `pairs` NOT RUN**" in text and "**stage `burst_sizes` NOT RUN**" in text
    assert text.count("**stage `lambda_miss` NOT RUN**") == 1                  # only the separate mode has no lambda_miss stage
