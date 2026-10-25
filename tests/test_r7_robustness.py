"""Round 7 robustness driver (src/prefixmeta/r7_robustness.py, r7_report.py): the pure helpers by hand, and every stage + the report end to end on a tiny
config (so the code paths that the real runs use are exercised before the real runs)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r7_report as RP
from prefixmeta import r7_robustness as R7

REPO = Path(__file__).resolve().parent.parent
WINDOW = {"lo": 1.0, "point_fractions": [1 / 3, 2 / 3], "round_to": 0.05, "empty_if_hi_at_most": 1.1}


# ----------------------------------------------------------------------------- pure helpers
def test_contiguous_edge_and_largest_all_stable():
    m = [1.25, 1.5, 1.75, 2.0, 2.25]
    assert R7.contiguous_edge(m, [True, True, False, True, False]) == 1.5
    assert R7.largest_all_stable(m, [True, True, False, True, False]) == 2.0
    assert R7.contiguous_edge(m, [False, True, True, True, True]) == 1.0        # even the smallest is unstable: empty window
    assert R7.largest_all_stable(m, [False] * 5) == 1.0
    assert R7.contiguous_edge(m, [True] * 5) == 2.25
    assert R7.contiguous_edge(list(reversed(m)), list(reversed([True, True, False, True, False]))) == 1.5      # order of the input does not matter


@pytest.mark.parametrize("hi,expected", [(2.0, [1.35, 1.65]), (2.5, [1.5, 2.0]), (3.0, [1.65, 2.35]), (1.25, [1.1, 1.15]), (1.75, [1.25, 1.5]),
                                         (2.25, [1.4, 1.85]), (1.1, []), (1.0, []), (1.05, [])])
def test_window_points_rounded_to_0p05(hi, expected):
    assert R7.window_points(hi, WINDOW) == pytest.approx(expected)


def test_smallest_within_5_percent_of_the_argmax():
    ns = [8, 12, 16, 20, 24]
    assert R7.smallest_within(ns, [0.04, 0.06, 0.069, 0.07, 0.05]) == (20, 0.07, 16)
    assert R7.smallest_within(ns, [0.04, 0.06, 0.0664, 0.07, 0.05])[2] == 20                   # 0.95 * 0.07 = 0.0665 > 0.0664
    assert R7.smallest_within(ns, [0.07, 0.07, 0.07, 0.07, 0.07]) == (8, 0.07, 8)               # ties: first argmax
    assert R7.smallest_within([24, 8, 20, 16, 12], [0.05, 0.04, 0.07, 0.069, 0.06]) == (20, 0.07, 16)       # unsorted grid


def test_need_count_is_the_two_thirds_rule():
    assert (R7.need_count(3, 2 / 3), R7.need_count(10, 2 / 3), R7.need_count(20, 2 / 3)) == (2, 7, 14)
    assert R7.need_count(10, 0.6666666666666666) == 7


def test_classify_label():
    assert R7.classify_label(True, False, False) == "TRAPPED"
    assert R7.classify_label(False, True, False) == "RECOVERED"
    assert R7.classify_label(False, False, True) == "INDETERMINATE"
    assert R7.classify_label(False, False, False) == "OTHER"
    assert R7.classify_label(True, True, False) == "BOTH"


def _windows(hit, backlog, t0=0.0, w=100.0):
    n = len(hit)
    return pd.DataFrame({"t_start": [t0 + w * i for i in range(n)], "t_end": [t0 + w * (i + 1) for i in range(n)], "hit_rate": hit,
                         "queue_mean": backlog, "gate_mean": [0.0] * n})


P_EVENTS = {"collapse_backlog_above": 50.0, "trap_hit_below": 0.2, "release_hit_above": 0.5}


def test_run_events_by_hand():
    # burst at t = 300; hit stays high until the window [400, 500), is below 0.2 for [400, 700), is back above 0.5 from [700, 800)
    hit = [0.9, 0.9, 0.9, 0.8, 0.1, 0.0, 0.0, 0.6, 0.9, 0.9]
    backlog = [0, 0, 1, 5, 60, 80, 70, 40, 10, 2]
    ev = R7.run_events(_windows(hit, backlog), 300.0, P_EVENTS)
    assert ev["collapse_s"] == 500.0                    # first window with backlog > 50 is [400, 500)
    assert ev["trap_onset_s"] == 500.0                  # first window at/after t_burst with hit < 0.2 is [400, 500)
    assert ev["release_s"] == 800.0                     # first window after the onset with hit > 0.5 is [700, 800)
    assert ev["max_backlog"] == 80 and ev["final_hit"] == 0.9 and ev["min_hit_after_burst"] == 0.0
    # never traps, never collapses
    ev2 = R7.run_events(_windows([0.9] * 6, [1.0] * 6), 200.0, P_EVENTS)
    assert np.isnan(ev2["collapse_s"]) and np.isnan(ev2["trap_onset_s"]) and np.isnan(ev2["release_s"])
    # trapped to the end
    ev3 = R7.run_events(_windows([0.9, 0.9, 0.0, 0.0, 0.0], [0, 0, 60, 90, 120]), 100.0, P_EVENTS)
    assert ev3["trap_onset_s"] == 300.0 and np.isnan(ev3["release_s"]) and ev3["collapse_s"] == 300.0
    # a low-hit window BEFORE the burst is not an onset (NOBURST-like start-up transient)
    ev4 = R7.run_events(_windows([0.0, 0.9, 0.9, 0.9], [0, 0, 0, 0]), 200.0, P_EVENTS)
    assert np.isnan(ev4["trap_onset_s"])


def test_verdict_counts_and_pass_rule():
    rows = []
    for arm, rec, trp in (("no_burst", [1] * 10, [0] * 10), ("burst", [0] * 10, [1] * 7 + [0] * 3), ("burst_cap", [1] * 9 + [0], [0] * 10)):
        for s in range(10):
            rows.append({"arm": arm, "seed": s, "recovered": bool(rec[s]), "trapped": bool(trp[s]), "indeterminate": arm == "burst" and s >= 7})
    v = R7.verdict_counts(pd.DataFrame(rows), 0.6666666666666666)
    assert (v["n_seeds"], v["need"]) == (10, 7)
    assert (v["burst_trapped"], v["burst_indeterminate"], v["noburst_good"], v["cap_recovered"]) == (7, 3, 10, 9) and v["PASS"] is True
    rows2 = [dict(r, trapped=(r["trapped"] and not (r["arm"] == "burst" and r["seed"] == 0))) for r in rows]
    assert R7.verdict_counts(pd.DataFrame(rows2), 0.6666666666666666)["PASS"] is False          # 6 of 10 trapped is below the 7 needed


# ----------------------------------------------------------------------------- end to end on a tiny config
def tiny_spec(tmp_path: Path) -> Path:
    raw = yaml.safe_load((REPO / "configs" / "r7_robustness.yaml").read_text())
    r7 = raw["r7"]
    r7["workloads"] = {k: r7["workloads"][k] for k in ("exp1", "exp5", "bimodal")}
    r7["record_workload"] = "exp5"
    r7["lambda_miss"].update(seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["curve"].update(n_grid=[8, 16, 32], seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["edge"].update(multiples=[1.25, 2.0, 3.5], seeds=[0, 1], horizon_s=1500.0, stable_trend_window_s=500.0)
    r7["pairs"].update(seeds=[0, 1], burst_n=60, warmup_s=300.0, after_s=1200.0)
    r7["classify"]["eval_window_rel_to_burst_s"] = [700.0, 1200.0]
    r7["burst_sizes"].update(multiples=[1.35], sizes=[20, 60], seeds=[0, 1], warmup_s=300.0, after_s=1200.0)
    r7["horizon"].update(multiples=[1.35], seeds=[0, 1], burst_n=60, warmup_s=300.0, after_s=1500.0,
                         eval_windows_rel_to_burst_s=[[700.0, 1200.0], [1000.0, 1500.0]])
    r7["lowlam"].update(seeds=[100, 101], burst_n=60, warmup_s=300.0, after_s=1200.0)
    p = tmp_path / "tiny.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    return p


def test_every_stage_and_the_report_run_end_to_end_on_a_tiny_config(tmp_path):
    spec = tiny_spec(tmp_path)
    out = str(tmp_path / "res")

    def run(stage, *extra):
        assert R7.main([stage, "--spec", str(spec), "--workers", "1", "--out-root", out, *extra], repo_dir=REPO) == 0

    run("lambda_miss")
    lm = R7.stage_summary(out, "lambda_miss")["workloads"]
    assert set(lm) == {"exp1", "exp5", "bimodal"} and all(w["busy"] > 0.9 and w["lambda_miss_turns"] > 0.03 for w in lm.values())
    assert lm["bimodal"]["tool_time_mean_s"] == pytest.approx(4.8) and "check_pop64" in lm["exp5"]
    run("curves")
    cv = R7.stage_summary(out, "curves")["workloads"]
    assert all(c["cap_n"] <= c["peak_n"] and c["cap_n"] in (8, 16, 32) for c in cv.values())
    run("edge")
    ed_dir = R7.stage_dir(out, "edge")
    ed = json.loads((ed_dir / "summary.json").read_text())
    assert set(ed["workloads"]) == {"exp1", "exp5", "bimodal"}
    # force the three branches of the pairs stage: an empty window, two points, one point
    ed["workloads"]["exp1"].update(hi=1.0, points=[], window_empty=True)
    ed["workloads"]["exp5"].update(hi=2.0, points=[1.35, 1.65], window_empty=False)
    ed["workloads"]["bimodal"].update(hi=1.5, points=[1.2], window_empty=False)
    (ed_dir / "summary.json").write_text(json.dumps(ed))
    run("pairs")
    pr = R7.stage_summary(out, "pairs")["workloads"]
    assert pr["exp1"]["window_empty"] and pr["exp1"]["points"] == {} and set(pr["exp5"]["points"]) == {"1.35", "1.65"} and set(pr["bimodal"]["points"]) == {"1.2"}
    pt = pr["exp5"]["points"]["1.35"]
    assert pt["n_seeds"] == 2 and pt["need"] == 2 and pt["cap_recovered"] is not None
    cl = pd.read_csv(R7.stage_dir(out, "pairs") / "classified_runs.csv")
    assert set(cl["arm"]) == {"no_burst", "burst", "burst_cap"} and set(cl["label"]) <= {"TRAPPED", "RECOVERED", "INDETERMINATE", "OTHER"}
    assert (cl[cl["arm"] == "burst_cap"]["cap"] == cv["exp5"]["cap_n"]).sum() >= 2
    run("burst_sizes")
    bs = R7.stage_summary(out, "burst_sizes")["by_mult"]["1.35"]
    assert set(bs["per_size"]) == {"20", "60"} and bs["n_seeds"] == 2
    run("horizon")
    hz = R7.stage_summary(out, "horizon")["by_mult"]["1.35"]
    assert hz["no_burst"]["n"] == 2 and hz["burst"]["n"] == 2 and "trapped_in_[1000, 1500]" in hz["burst"]
    run("lowlam")
    lw = R7.stage_summary(out, "lowlam")
    assert lw["n"] == 2 and sum(lw["classes"].values()) == 2 and lw["slope_threshold"] > 0
    # the report reads only the manifest
    d = RP.main(["report", "--spec", str(spec), "--out-root", out], repo_dir=REPO)
    assert (Path(d) / "tables.md").exists() and (Path(d) / "summary.json").exists()
    text = (Path(d) / "tables.md").read_text()
    for needle in ("lambda_miss", "Wilson", "burst size", "Horizon", "Low-lambda", "Binomial"):
        assert needle.lower() in text.lower(), needle
    # a spec without the optional r7.stages / r7.title keys keeps all eight numbered sections and the original provenance text
    assert [ln.split(".")[0] for ln in text.splitlines() if ln.startswith("### ")] == [f"### {i}" for i in range(1, 9)]
    assert "pairs, all test points (2 workloads, 3 points, seeds 0-1)" in text and "E[T] (turns per session)" not in text
    assert (Path(d) / "provenance.md").read_text(encoding="utf-8").startswith("Spec: `" + str(spec).replace("\\", "/") + "` (sha256 `")


def test_edge_refinement_grid_runs_when_the_lowest_multiple_is_unstable(tmp_path):
    raw = yaml.safe_load(tiny_spec(tmp_path).read_text())
    raw["r7"]["edge"].update(multiples=[3.5, 5.0], refine_if_lowest_unstable=[1.05, 1.1], seeds=[0, 1], horizon_s=1500.0, stable_trend_window_s=500.0)
    spec = tmp_path / "refine.yaml"
    spec.write_text(yaml.safe_dump(raw, sort_keys=False))
    out = str(tmp_path / "res")
    for stage in ("lambda_miss", "edge"):
        assert R7.main([stage, "--spec", str(spec), "--workers", "1", "--out-root", out, "--only", "exp5"], repo_dir=REPO) == 0
    w = R7.stage_summary(out, "edge")["workloads"]["exp5"]
    v = pd.read_csv(R7.stage_dir(out, "edge") / "edge_verdicts.csv")
    assert w["refined"] is True and set(v["lam_mult"]) == {1.05, 1.1, 3.5, 5.0} and set(v[v["refinement"]]["lam_mult"]) == {1.05, 1.1}
    assert w["hi"] == 1.1 and w["window_empty"] is True and w["points"] == []            # 1.05 and 1.1 stable, 3.5 not: hi = 1.1 <= 1.1 -> empty
