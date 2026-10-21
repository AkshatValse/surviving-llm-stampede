"""Pre-registration template (configs/agentload_prereg_template.yaml): formulas, validation against the applied rule, git
provenance, and its use by `summarize burst2 --prereg`."""
import json
import shutil
import subprocess

import pandas as pd
import pytest
import yaml

from analysis import prereg as pr_mod
from analysis.closed import mu_curve
from analysis.summarize import main as analysis_main
from conftest import REPO
from helpers_analysis import params
from helpers_trap import LAM_MISS, MULT, scenario_recovered, scenario_trapped, synth_run, write_run_dir

TEMPLATE = REPO / "configs" / "agentload_prereg_template.yaml"
LABEL = "sglang-fcfs-r1"
CP = dict(n_grid=[16, 24, 32, 48, 96, 300], lpm_n=[48, 300], n_inf=300, mu_estimator="sessions", argmax_margin_warn=0.05)
MUS = (0.05, 0.08, 0.07, 0.05, 0.04, 0.035)                # sessions/s; max at n=24, mu(300)=0.035


def curve(mus=MUS):
    pts = pd.DataFrame([dict(label=LABEL, seed=0, n=n, mu_sessions=m, mu_turns_based=m, turns_per_s=1.0, hit_frac_turns=0.9,
                             hit_frac_followup=0.9, cached_frac_tokens=0.9, queue_mean=0.0, aborted=False)
                        for n, m in zip(CP["n_grid"], mus)])
    return json.loads(json.dumps(mu_curve(pts, CP)))


CAL = {"lambda_miss": 0.0415, "lambda_miss_turns_based": LAM_MISS, "hardware": "synthetic"}


def tmpl():
    return pr_mod.load_prereg(TEMPLATE)


def codes(probs):
    return {x["code"] for x in probs}


def test_template_shape_and_it_is_not_valid_as_is():
    t = tmpl()
    assert next(iter(t)) == "research_question" and t["status"] == "TEMPLATE"
    for sec in ("inputs", "measured", "predicted_boundaries", "lambda_selection", "predictions", "pass_rule", "kill_conditions"):
        assert sec in t, sec
    assert t["inputs"]["engine_cell_label"] == LABEL and t["measured"]["mu_by_n"].keys() == {16, 24, 32, 48, 96, 300}
    probs = pr_mod.validate(t, params())
    assert {"not_filled", "unfilled", "no_lambda_rule", "no_lambda_mults"} <= codes(probs)
    assert all(x["severity"] == "error" for x in probs)


def test_the_registered_rule_equals_the_rule_the_analysis_applies():
    probs = pr_mod.validate(tmpl(), params())
    assert not {"rule_mismatch", "rule_key_missing"} & codes(probs)                 # every pass_rule key equals trap_v2
    bad = tmpl()
    bad["pass_rule"]["rate_tolerance"] = 0.25
    bad["pass_rule"].pop("slope_frac")
    c = pr_mod.validate(bad, params())
    assert {"rule_mismatch", "rule_key_missing"} <= codes(c)
    other = pr_mod.validate(tmpl(), params("trap_v2.rate_estimator=turns_based", "closed.mu_estimator=turns_based"))
    assert sum(x["code"] == "rule_mismatch" for x in other) == 2                    # the estimator keys are also checked


def test_fill_computes_the_boundaries_by_formula():
    f = pr_mod.fill(tmpl(), curve(), CAL, lambda_mults=[1.2, 1.5, 1.9], rule="three points spread across the window",
                    mu_curve_path="mu_curve.json", calibration_path="calibration.json", p=params())
    assert f["status"] == "FILLED" and not [x for x in f["fill_problems"] if x["severity"] == "error"]
    m, b = f["measured"], f["predicted_boundaries"]
    assert m["mu_300"] == 0.035 and m["mu_max"] == 0.08 and m["n_cap"] == 24 and m["lambda_ref"] == LAM_MISS
    assert m["mu_by_n"] == {16: 0.05, 24: 0.08, 32: 0.07, 48: 0.05, 96: 0.04, 300: 0.035} and m["complete_grid"] is True
    assert b["recovery_threshold"]["sessions_per_s"] == 0.035 and b["recovery_threshold"]["mult_of_lambda_ref"] == pytest.approx(0.875)
    w = b["metastable_window"]
    assert (w["lo"], w["hi"]) == (0.035, 0.08) and w["lo_mult"] == pytest.approx(0.875) and w["hi_mult"] == pytest.approx(2.0)
    assert b["trapped_completion_rate"]["value"] == LAM_MISS
    assert b["consistency"]["mu_300_vs_lambda_miss_rel_dev"] == pytest.approx(-0.125) and b["consistency"]["window_nonempty"]
    assert f["lambda_selection"]["lambda_mults"] == [1.2, 1.5, 1.9] and f["lambda_selection"]["rule"].startswith("three points")
    assert f["inputs"]["mu_curve_json"] == "mu_curve.json" and f["inputs"]["calibration_json"] == "calibration.json"
    assert pr_mod.validate(f, params()) == []                                       # a filled file validates clean
    # the template itself is untouched (deep copy)
    assert tmpl()["status"] == "TEMPLATE" and tmpl()["measured"]["mu_300"] is None


def test_fill_refuses_lambda_points_outside_the_window_or_inside_the_margin():
    f = pr_mod.fill(tmpl(), curve(), CAL, lambda_mults=[0.8, 1.5], rule="x", p=params())
    assert f["status"] == "INCOMPLETE" and "lambda_outside_window" in codes(f["fill_problems"])
    t = tmpl()
    t["lambda_selection"]["boundary_margin_rel"] = 0.1                            # (0.9625, 1.8)
    ok = pr_mod.fill(t, curve(), CAL, lambda_mults=[1.0, 1.7], rule="x", p=params())
    assert ok["status"] == "FILLED"
    bad = pr_mod.fill(t, curve(), CAL, lambda_mults=[0.95, 1.9], rule="x", p=params())
    assert bad["status"] == "INCOMPLETE" and sum(x["code"] == "lambda_outside_window" for x in bad["fill_problems"]) == 2


def test_fill_needs_a_rule_and_flags_a_closed_curve_that_disagrees_with_lambda_miss():
    f = pr_mod.fill(tmpl(), curve(), CAL, lambda_mults=[1.5], p=params())
    assert f["status"] == "INCOMPLETE" and "no_lambda_rule" in codes(f["fill_problems"])
    far = pr_mod.fill(tmpl(), curve(MUS[:5] + (0.025,)), CAL, lambda_mults=[1.2], rule="x", p=params())      # mu(300)=0.025 vs 0.04
    w = [x for x in far["fill_problems"] if x["code"] == "mu300_far_from_lambda_miss"]
    assert far["status"] == "FILLED" and len(w) == 1 and w[0]["severity"] == "warn"       # a warning, not an error
    # a curve whose maximum is at n=300 has an EMPTY window (mu_max == mu_300): nothing can be tested inside it
    empty = pr_mod.fill(tmpl(), curve((0.05, 0.05, 0.05, 0.04, 0.035, 0.06)), CAL, lambda_mults=[1.5], rule="x", p=params())
    assert empty["predicted_boundaries"]["consistency"]["window_nonempty"] is False
    assert empty["status"] == "INCOMPLETE" and "lambda_outside_window" in codes(empty["fill_problems"])


def test_fill_rejects_mismatched_inputs():
    with pytest.raises(ValueError, match="no cell"):
        t = tmpl()
        t["inputs"]["engine_cell_label"] = "sglang-lpm-r1"
        pr_mod.fill(t, curve(), CAL)
    with pytest.raises(ValueError, match="no key"):
        pr_mod.fill(tmpl(), curve(), {"lambda_miss": 0.04})
    c = curve()
    c["estimator"] = "turns_based"
    with pytest.raises(ValueError, match="estimator"):
        pr_mod.fill(tmpl(), c, CAL)


def test_cli_fill_and_validate(tmp_path, capsys):
    (tmp_path / "mu.json").write_text(json.dumps(curve()))
    (tmp_path / "cal.json").write_text(json.dumps(CAL))
    out = tmp_path / "prereg.yaml"
    args = ["fill", "--template", str(TEMPLATE), "--mu-curve", str(tmp_path / "mu.json"), "--calibration", str(tmp_path / "cal.json"),
            "--out", str(out), "--lambda-mults", "1.3", "1.6", "--rule", "inside the window"]
    assert pr_mod.main(args) == 0 and out.exists()
    assert yaml.safe_load(out.read_text())["status"] == "FILLED"
    assert pr_mod.main(args) == 2                                                    # never overwrites
    assert pr_mod.main(["validate", str(out)]) == 0
    assert pr_mod.main(["validate", str(TEMPLATE)]) == 1
    part = tmp_path / "part.yaml"
    assert pr_mod.main(args[:-4] + ["--out", str(part)]) == 1                        # no lambda points: INCOMPLETE, exit 1
    assert yaml.safe_load(part.read_text())["status"] == "INCOMPLETE"


# ------------------------------------------------------------------------------------------------ git provenance
def git(repo, *a):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo, capture_output=True, text=True, check=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_file_provenance_tracks_commit_state(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    f = repo / "prereg.yaml"
    f.write_text("a: 1\n")
    p0 = pr_mod.file_provenance(f)
    assert len(p0["sha256"]) == 64 and not p0["git_tracked"] and not p0["committed_clean"] and p0["git_last_commit"] is None
    git(repo, "add", "prereg.yaml")
    git(repo, "commit", "-q", "-m", "x")
    p1 = pr_mod.file_provenance(f)
    assert p1["committed_clean"] and p1["git_tracked"] and len(p1["git_last_commit"]) == 40 and p1["sha256"] == p0["sha256"]
    f.write_text("a: 2\n")
    p2 = pr_mod.file_provenance(f)
    assert not p2["committed_clean"] and p2["git_modified_since_commit"] and p2["sha256"] != p1["sha256"]


# ------------------------------------------------------------------------------------------------ burst2 --prereg
def paired_runs():
    """Three seeds of the three arms at lambda = 1.5 x lambda_ref = 0.06 sessions/s (BURST trapped, others good)."""
    runs = []
    for seed in range(3):
        for arm, scen in (("burst", scenario_trapped()), ("noburst", scenario_recovered()), ("capped", scenario_recovered())):
            runs.append(synth_run(arm=arm, seed=seed, label=LABEL, **{**scen, "burst_n": 200}))
    return runs


def burst2(tmp_path, prereg_file):
    dirs = [write_run_dir(r, tmp_path / "runs") for r in paired_runs()]
    out_root = tmp_path / "an"
    args = ["burst2", "--run-dirs", *map(str, dirs), "--out-root", str(out_root), "--set", "burst.trap_min_s=3000",
            "--set", "burst.hit_eval_from_s=4500"]
    if prereg_file is not None:
        args += ["--prereg", str(prereg_file)]
    assert analysis_main(args) == 0
    d = sorted((out_root / "agentload_analysis_burst2").iterdir())[-1]
    return json.loads((d / "kill_verdict_v2.json").read_text())


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_burst2_decisive_only_with_a_committed_valid_prereg_and_lambda_in_window(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    filled = pr_mod.fill(tmpl(), curve(), CAL, lambda_mults=[MULT], rule="mid-window", p=params())
    assert filled["status"] == "FILLED"
    f = repo / "prereg.yaml"
    f.write_text(yaml.safe_dump(filled, sort_keys=False))
    # 1. no prereg: exploratory
    kv = burst2(tmp_path / "a", None)
    assert kv["kill_test_pass_rule_only"] is True and kv["kill_test_pass_decisive"] is None and kv["pre_registered"] is False
    # 2. valid file but NOT committed: still not decisive (the registration must precede the runs)
    kv = burst2(tmp_path / "b", f)
    assert kv["prereg"]["valid"] and not kv["prereg"]["committed_clean"] and kv["pre_registered"] is False
    assert kv["kill_test_pass_decisive"] is None and kv["kill_test_pass_rule_only"] is True
    assert kv["cells"][0]["in_registered_window"] is True and kv["prereg"]["provenance"]["sha256"]
    # 3. committed: decisive PASS (lambda = 0.06 lies inside (0.035, 0.08))
    git(repo, "add", "prereg.yaml")
    git(repo, "commit", "-q", "-m", "register")
    kv = burst2(tmp_path / "c", f)
    assert kv["pre_registered"] is True and kv["kill_test_pass_decisive"] is True
    assert kv["prereg"]["provenance"]["git_last_commit"] and kv["prereg"]["window"]["lo"] == 0.035
    # 4. committed file whose window does NOT contain the tested lambda: the rule passes, the registration does not count
    narrow = pr_mod.fill(tmpl(), curve((0.05, 0.055, 0.05, 0.045, 0.04, 0.035)), CAL, lambda_mults=[1.2], rule="x", p=params())
    assert narrow["predicted_boundaries"]["metastable_window"]["hi"] == 0.055
    g = repo / "narrow.yaml"
    g.write_text(yaml.safe_dump(narrow, sort_keys=False))
    git(repo, "add", "narrow.yaml")
    git(repo, "commit", "-q", "-m", "register narrow")
    kv = burst2(tmp_path / "d", g)
    assert kv["cells"][0]["in_registered_window"] is False and kv["kill_test_pass_rule_only"] is True
    assert kv["pre_registered"] is True and kv["kill_test_pass_decisive"] is False
    # 5. a registered rule that differs from the applied one invalidates the registration
    drift = yaml.safe_load(f.read_text())
    drift["pass_rule"]["recovered_hit_above"] = 0.9
    h = repo / "drift.yaml"
    h.write_text(yaml.safe_dump(drift, sort_keys=False))
    git(repo, "add", "drift.yaml")
    git(repo, "commit", "-q", "-m", "drift")
    kv = burst2(tmp_path / "e", h)
    assert kv["prereg"]["valid"] is False and kv["pre_registered"] is False and kv["kill_test_pass_decisive"] is None
    assert any(x["code"] == "rule_mismatch" for x in kv["prereg"]["problems"])
