"""configs/r7_traces_sim.yaml (real-trace tool-time laws in the round-7 stages): the spec is the declared pre-registration, so these tests pin it to its sources.

* the inlined empirical tables equal the `workload_empirical*` blocks of the two trace configs value for value, and the trace configs are the files whose
  sha256 the spec header records;
* everything that is not the tool-time law (engine, record geometry, seeds, grids, rules) is identical to configs/r7_robustness.yaml;
* the opt-in driver keys (per-workload `expected_turns`, `r7.stages`, `r7.title`) work, and the original spec's report is unchanged by them;
* every stage of the new spec and its report run end to end on a tiny scaled-down copy.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r7_posthoc as PH
from prefixmeta import r7_report as RP
from prefixmeta import r7_robustness as R7
from prefixmeta.probe import load_probe_config
from prefixmeta.sim import deep_update
from prefixmeta.workload import WorkloadParams, empirical_moments, tool_time_moments

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "configs" / "r7_traces_sim.yaml"
OLD = REPO / "configs" / "r7_robustness.yaml"
TL = REPO / "configs" / "workload_trace_tracelab.yaml"
MI = REPO / "configs" / "workload_trace_mini_swe_v2.yaml"
TT = ("tool_time_dist", "tool_time_mean_s", "tool_time_cv", "tool_time_quantile_levels", "tool_time_quantiles")
GEOM = ("initial_context_tokens", "new_prompt_tokens", "decode_tokens", "mean_turns", "max_turns")


def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- the spec is pinned to its sources
def test_the_trace_configs_are_the_files_the_spec_header_records():
    head = SPEC.read_text(encoding="utf-8")
    for p in (TL, MI):
        m = re.search(rf"configs/{re.escape(p.name)}\s+sha256 ([0-9a-f]{{64}})", head)
        assert m is not None and m.group(1) == sha(p), p.name


@pytest.mark.parametrize("name,src,block", [("tl_turn", TL, "workload_empirical"), ("tl_idle", TL, "workload_empirical_idle_gap"),
                                            ("mini_tool", MI, "workload_empirical"), ("mini_full", MI, "workload_empirical")])
def test_inlined_tables_equal_the_trace_config_blocks_value_for_value(name, src, block):
    spec = load(SPEC)["r7"]["workloads"][name]["workload"]
    ref = load(src)[block]
    for k in TT:
        assert spec[k] == ref[k], (name, k)                      # lists of floats compared exactly, element by element
    assert len(spec["tool_time_quantiles"]) == len(spec["tool_time_quantile_levels"]) == 250
    wl = WorkloadParams.from_dict(deep_update(load(SPEC)["workload"], spec))
    m, cv = tool_time_moments(wl)
    assert (m, cv) == empirical_moments(ref["tool_time_quantiles"], ref["tool_time_quantile_levels"])
    assert m == pytest.approx(ref["tool_time_mean_s"], rel=1e-4) and cv == pytest.approx(ref["tool_time_cv"], rel=1e-3)      # the config's own rounded moments


def test_mini_full_carries_exactly_the_geometry_of_the_trace_config():
    spec = load(SPEC)["r7"]["workloads"]["mini_full"]["workload"]
    ref = load(MI)["workload_empirical"]
    assert {k: spec[k] for k in GEOM} == {k: ref[k] for k in GEOM}
    assert (spec["initial_context_tokens"], spec["new_prompt_tokens"], spec["decode_tokens"], spec["mean_turns"], spec["max_turns"]) == (1862, 429, 269, 49.02, 60)


def test_primary_workloads_change_only_the_tool_time_law():
    cfg = load_probe_config(str(SPEC), REPO)
    rec = WorkloadParams.from_dict(cfg["workload"])
    assert (rec.initial_context_tokens, rec.new_prompt_tokens, rec.decode_tokens, rec.mean_turns, rec.max_turns) == (2000, 550, 100, 15, 60)
    for name in ("exp5", "tl_turn", "tl_idle", "mini_tool"):
        wl = R7.merged_workload(cfg, cfg["r7"], name)
        assert all(getattr(wl, k) == getattr(rec, k) for k in GEOM), name
    assert R7.merged_workload(cfg, cfg["r7"], "exp5") == rec
    assert {n: R7.merged_workload(cfg, cfg["r7"], n).tool_time_dist for n in cfg["r7"]["workloads"]} == {
        "exp5": "exp", "tl_turn": "empirical", "tl_idle": "empirical", "mini_tool": "empirical", "mini_full": "empirical"}


def test_everything_else_is_identical_to_the_round7_spec():
    a, b = load(SPEC), load(OLD)
    for k in ("base_config", "engine", "workload", "metrics", "parallel"):
        assert a[k] == b[k], k
    for k in ("policy", "expected_turns", "wilson_z", "lambda_miss", "curve", "edge", "window", "pairs", "classify"):
        assert a["r7"][k] == b["r7"][k], k
    assert a["r7"]["stages"] == ["lambda_miss", "curves", "edge", "pairs"]
    assert not {"burst_sizes", "horizon", "lowlam"} & set(a["r7"])                  # steps 3-5 are not part of this spec


def test_expected_turns_of_every_workload_is_asserted_per_workload():
    cfg = load_probe_config(str(SPEC), REPO)
    r7 = cfg["r7"]
    et = {n: R7.expected_turns(cfg, r7, n) for n in r7["workloads"]}
    assert et["exp5"] == et["tl_turn"] == et["tl_idle"] == et["mini_tool"] == pytest.approx(14.761, abs=5e-4)
    assert et["mini_full"] == pytest.approx(34.786744834183175, abs=1e-12)
    bad = dict(r7, workloads=dict(r7["workloads"], mini_full=dict(r7["workloads"]["mini_full"], expected_turns=34.0)))
    with pytest.raises(ValueError, match="differs from the declared"):
        R7.expected_turns(cfg, bad, "mini_full")
    wrong = dict(r7, workloads=dict(r7["workloads"], tl_turn=dict(r7["workloads"]["tl_turn"], workload=dict(r7["workloads"]["tl_turn"]["workload"], mean_turns=10.74))))
    with pytest.raises(ValueError, match="differs from the declared"):              # a workload that changes the turn law must declare its own E[T]
        R7.expected_turns(cfg, wrong, "tl_turn")


def test_a_stage_that_the_spec_does_not_declare_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="not a stage of this spec"):
        R7.main(["burst_sizes", "--spec", str(SPEC), "--workers", "1", "--out-root", str(tmp_path / "res")], repo_dir=REPO)
    assert not (tmp_path / "res").exists()


# ----------------------------------------------------------------------------- end to end on a tiny scaled-down copy of the REAL spec
def tiny_traces_spec(tmp_path: Path) -> Path:
    raw = load(SPEC)
    r7 = raw["r7"]
    r7["workloads"] = {k: r7["workloads"][k] for k in ("exp5", "tl_turn", "mini_full")}
    r7["lambda_miss"].update(seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["curve"].update(n_grid=[8, 16, 32], seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["edge"].update(multiples=[1.25, 2.0, 3.5], seeds=[0, 1], horizon_s=1500.0, stable_trend_window_s=500.0)
    r7["pairs"].update(seeds=[0, 1], burst_n=60, warmup_s=300.0, after_s=1200.0)
    r7["classify"]["eval_window_rel_to_burst_s"] = [700.0, 1200.0]
    p = tmp_path / "tiny_traces.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return p


def test_every_stage_and_the_report_of_the_traces_spec_run_end_to_end_on_a_tiny_copy(tmp_path):
    spec = tiny_traces_spec(tmp_path)
    out = str(tmp_path / "res")

    def run(stage):
        assert R7.main([stage, "--spec", str(spec), "--workers", "1", "--out-root", out], repo_dir=REPO) == 0

    run("lambda_miss")
    lm = R7.stage_summary(out, "lambda_miss")["workloads"]
    assert set(lm) == {"exp5", "tl_turn", "mini_full"} and all(w["busy"] > 0.9 for w in lm.values())
    ref = load(TL)["workload_empirical"]
    assert (lm["tl_turn"]["tool_time_mean_s"], lm["tl_turn"]["tool_time_cv"]) == empirical_moments(ref["tool_time_quantiles"], ref["tool_time_quantile_levels"])
    assert lm["exp5"]["E_T"] == pytest.approx(14.761, abs=5e-4) and lm["tl_turn"]["E_T"] == lm["exp5"]["E_T"] and lm["mini_full"]["E_T"] == pytest.approx(34.7867, abs=1e-4)
    run("curves")
    cv = R7.stage_summary(out, "curves")["workloads"]
    assert all(c["cap_n"] <= c["peak_n"] for c in cv.values())
    run("edge")
    ed_dir = R7.stage_dir(out, "edge")
    ed = json.loads((ed_dir / "summary.json").read_text())
    ed["workloads"]["exp5"].update(hi=2.0, points=[1.35, 1.65], window_empty=False)
    ed["workloads"]["tl_turn"].update(hi=1.0, points=[], window_empty=True)                  # an EMPTY window is a result, not an error
    ed["workloads"]["mini_full"].update(hi=1.5, points=[1.2], window_empty=False)
    (ed_dir / "summary.json").write_text(json.dumps(ed))
    run("pairs")
    pr = R7.stage_summary(out, "pairs")["workloads"]
    assert pr["tl_turn"]["window_empty"] and pr["tl_turn"]["points"] == {} and set(pr["exp5"]["points"]) == {"1.35", "1.65"} and set(pr["mini_full"]["points"]) == {"1.2"}
    # the manifest of the traces runs lives under its own out-root: the stages that the spec does not declare are not in it
    assert set(pd.read_csv(Path(out) / "r7_robustness" / "manifest.tsv", sep="\t")["stage"]) == {"lambda_miss", "curves", "edge", "pairs"}
    d = Path(RP.main(["report", "--spec", str(spec), "--out-root", out], repo_dir=REPO))
    text = (d / "tables.md").read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("### ")]
    assert [h.split(".")[0] for h in heads] == ["### 1", "### 2", "### 3", "### 4", "### 5"]            # consecutive; the stages that are not declared are absent
    assert not any(w in text for w in ("Horizon", "Low-lambda", "Burst-size", "NOT RUN"))
    assert "EMPTY window" in text and "TraceLab per-turn (empirical)" in text and "E[T]" in text           # E[T] differs across the workloads, so it is shown
    prov = (d / "provenance.md").read_text(encoding="utf-8")
    assert "`" + str(spec).replace("\\", "/") in prov.replace("\\", "/") or "tiny_traces.yaml" in prov
    assert "burst_sizes" not in prov and "horizon" not in prov
    ph = Path(PH.main(["--spec", str(spec), "--out-root", out], repo_dir=REPO))                # post-hoc diagnostics read the same manifest
    ptxt = (ph / "posthoc.md").read_text(encoding="utf-8")
    assert "P1. CAPPED and NOBURST arms" in ptxt and "P2. NOBURST runs that are not RECOVERED" in ptxt and "drain time of the burst" in ptxt
    assert "TraceLab per-turn" not in ptxt.split("### P2.")[0]                                         # the empty-window workload has no tested point, hence no row
    ps = json.loads((ph / "summary.json").read_text())
    assert {r["workload"] for r in ps["capped"]} == {"Exp(5 s) (record, control)", "mini-SWE-agent v2 full workload (empirical)"} and len(ps["capped"]) == 3
    notes = tmp_path / "notes.md"
    head = tmp_path / "head.md"
    head.write_text("HEADLINE", encoding="utf-8")
    RP.main(["assemble", "--spec", str(spec), "--out-root", out, "--headline", str(head), "--notes", str(notes)], repo_dir=REPO)
    assert notes.read_text(encoding="utf-8").startswith("# Round 7: real-trace tool times in the calibrated simulator (referee objection 3)\n")


def test_drain_time_is_burst_over_spare_capacity():
    assert PH.drain_time_s(200, 0.05035, 0.02811) == pytest.approx(200 / 0.02224)
    assert PH.drain_time_s(200, 0.2144, 0.09745) == pytest.approx(200 / (0.2144 - 0.09745))
    assert PH.drain_time_s(200, 0.05, 0.05) == float("inf") and PH.drain_time_s(200, 0.04, 0.05) == float("inf")
