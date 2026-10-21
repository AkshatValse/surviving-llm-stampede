"""Pre-registration template (configs/agentload_prereg_template.yaml): formulas, validation against the applied rule, git
provenance, job-start authorisation (check-job) and its use by `summarize burst2 --prereg` (what makes a verdict DECISIVE)."""
import copy
import itertools
import json
import shutil
import subprocess
import time
from functools import lru_cache

import pandas as pd
import pytest
import yaml

from analysis import prereg as pr_mod
from analysis.closed import mu_curve
from analysis.summarize import main as analysis_main
from conftest import REPO
from helpers_analysis import params
from helpers_trap import K, LAM_MISS, MULT, PROMPT, scenario_recovered, scenario_trapped, synth_run, write_run_dir

TEMPLATE = REPO / "configs" / "agentload_prereg_template.yaml"
LABEL = "sglang-fcfs-r1"
N_CAP = 24
CP = dict(n_grid=[16, 20, 24, 32, 48, 96, 300], lpm_n=[48, 300], n_inf=300, mu_estimator="sessions", argmax_margin_warn=0.05)
MUS = (0.12, 0.16, 0.20, 0.17, 0.10, 0.06, 0.04)           # sessions/s; max at n=24 (n_cap), mu(300)=0.04 = lambda_miss
MULTS_OK = [1.3, MULT, 2.0]                                   # window is (1.0, 2.5) from E0b's edge; margin 0.1 => (1.1, 2.25)
TOK_REF = LAM_MISS * K * PROMPT                               # the synthetic runs' all-miss uncached prefill tokens/s


def curve(mus=MUS, label=LABEL, hardware="synthetic"):
    pts = pd.DataFrame([dict(label=label, seed=0, n=n, mu_sessions=m, mu_turns_based=m, turns_per_s=1.0, hit_frac_turns=0.9,
                             hit_frac_followup=0.9, cached_frac_tokens=0.9, queue_mean=0.0, aborted=False, hardware=hardware)
                        for n, m in zip(CP["n_grid"], mus)])
    return json.loads(json.dumps(mu_curve(pts, CP)))


CAL = {"lambda_miss": 0.0415, "lambda_miss_turns_based": LAM_MISS, "all_miss_uncached_tokens_per_s": TOK_REF,
       "hardware": "synthetic"}
E0B = {"by_label": {LABEL: {"largest_all_stable_mult": 2.5, "first_unstable_mult_above": 3.0, "monotone": True,
                            "hardware": ["synthetic"]}}}
E2CFG = {"run": {"duration_s": 8700}, "arrivals": {"analysis_t_burst_s": 1200, "burst": {"n": 200, "t_s": 1200, "width_s": 60}}}


def tmpl():
    return pr_mod.load_prereg(TEMPLATE)


def codes(probs):
    return {x["code"] for x in probs}


def filled(mults=MULTS_OK, rule="spread over the window", mus=MUS, e0b=E0B, cal=CAL, label=None, p=None, **kw):
    return pr_mod.fill(tmpl(), curve(mus), cal, e0b=e0b, e2_cfg=E2CFG, lambda_mults=mults, rule=rule, engine_cell_label=label,
                       p=p or params(), **kw)


def test_template_shape_and_it_is_not_valid_as_is():
    t = tmpl()
    assert next(iter(t)) == "research_question" and t["status"] == "TEMPLATE"
    for sec in ("inputs", "protocol", "measured", "predicted_boundaries", "lambda_selection", "predictions", "pass_rule",
                "kill_conditions"):
        assert sec in t, sec
    assert t["inputs"]["engine_cell_label"] == LABEL and t["measured"]["mu_by_n"].keys() == {16, 20, 24, 32, 48, 96, 300}
    probs = pr_mod.validate(t, params())
    assert {"not_filled", "unfilled", "no_lambda_rule", "no_lambda_mults"} <= codes(probs)
    assert all(x["severity"] == "error" for x in probs)


def test_the_registered_rule_equals_the_rule_the_analysis_applies():
    probs = pr_mod.validate(tmpl(), params())
    assert not {"rule_mismatch", "rule_key_missing", "rule_key_unregistered"} & codes(probs)       # every pass_rule key is applied
    bad = tmpl()
    bad["pass_rule"]["rate_tolerance"] = 0.25
    bad["pass_rule"].pop("slope_frac")
    c = pr_mod.validate(bad, params())
    assert {"rule_mismatch", "rule_key_missing"} <= codes(c)
    other = pr_mod.validate(tmpl(), params("trap_v2.rate_estimator=turns_based", "closed.mu_estimator=turns_based"))
    assert sum(x["code"] == "rule_mismatch" for x in other) == 2                    # the estimator keys are also checked


@pytest.mark.parametrize("override", ["windows.hit_metric=token_hit_rate", "windows.cached_frac_threshold=0.3",
                                      "windows.attribute_by=send", "trap_v2.recovered_backlog_metric=sessions",
                                      "trap_v2.rate_estimator=sessions"])
def test_every_analysis_setting_that_changes_a_verdict_is_registered(override):
    """Review finding 8: `--set windows.hit_metric=...` used to change what 'hit > 0.8' means without touching the prereg."""
    f = filled()
    assert pr_mod.validate(f, params()) == []
    probs = pr_mod.validate(f, params(override))
    assert any(x["code"] == "rule_mismatch" and x["severity"] == "error" for x in probs), override


def test_fcfs_substr_is_registered_and_every_trap_v2_key_is_registered_or_exempt():
    f = filled()
    assert pr_mod.validate(f, params(), fcfs_substr="fcfs") == []
    assert "rule_mismatch" in codes(pr_mod.validate(f, params(), fcfs_substr="sglang"))
    registered = {v.split(".", 1)[1] for v in pr_mod.RULE_KEYS.values() if v.startswith("trap_v2.")}
    assert set(params().trap_v2) == registered | set(pr_mod.UNREGISTERED_TRAP_V2_KEYS)
    extra = params("trap_v2.brand_new_knob=1")                                       # a knob nobody registered is an error
    assert "rule_key_unregistered" in codes(pr_mod.validate(f, extra))


def test_fill_computes_the_boundaries_by_formula():
    f = filled(mults=[1.3, 1.6, 2.0], rule="three points spread across the window", mu_curve_path="mu_curve.json",
               calibration_path="calibration.json", e0b_path="b.json", e2_cfg_path="e2.yaml")
    assert f["status"] == "FILLED" and not [x for x in f["fill_problems"] if x["severity"] == "error"]
    m, b = f["measured"], f["predicted_boundaries"]
    assert m["mu_300"] == 0.04 and m["mu_max"] == 0.20 and m["n_cap"] == N_CAP and m["mu_n_cap"] == 0.20 and m["lambda_ref"] == LAM_MISS
    assert m["all_miss_uncached_tokens_per_s"] == TOK_REF and m["hardware"] == "synthetic"
    assert m["mu_by_n"] == dict(zip(CP["n_grid"], MUS)) and m["complete_grid"] is True
    assert m["lambda_cap_e0b"] == {"largest_all_stable_mult": 2.5, "first_unstable_mult_above": 3.0, "monotone": True}
    # recovery threshold = lambda_miss (NOT mu(300)); the window ends at min(mu_max, E0b's largest all-stable multiple)
    assert b["recovery_threshold"]["sessions_per_s"] == LAM_MISS and b["recovery_threshold"]["mult_of_lambda_ref"] == 1.0
    w = b["metastable_window"]
    assert (w["lo"], w["lo_mult"]) == (LAM_MISS, 1.0) and w["hi"] == pytest.approx(0.10) and w["hi_mult"] == pytest.approx(2.5)
    assert w["hi_source"] == "lambda_cap_e0b"
    assert b["trapped_uncached_token_rate"]["value"] == TOK_REF and b["trapped_completion_rate"]["value"] == LAM_MISS
    assert b["consistency"]["mu_300_vs_lambda_miss_rel_dev"] == pytest.approx(0.0) and b["consistency"]["window_nonempty"]
    assert f["checks"]["mu_300_is_a_check_only"]["value"] == 0.04
    assert f["protocol"] == {"duration_s": 8700, "t_burst_s": 1200, "burst_n": 200, "burst_width_s": 60}
    assert f["lambda_selection"]["lambda_mults"] == [1.3, 1.6, 2.0] and f["lambda_selection"]["rule"].startswith("three points")
    assert f["inputs"]["mu_curve_json"] == "mu_curve.json" and f["inputs"]["e0b_bracket_json"] == "b.json"
    assert pr_mod.validate(f, params()) == []                                       # a filled file validates clean
    assert tmpl()["status"] == "TEMPLATE" and tmpl()["measured"]["mu_300"] is None   # the template is untouched (deep copy)


def test_upper_edge_is_mu_max_when_that_is_below_the_e0b_edge_and_e0b_is_required():
    low = {"by_label": {LABEL: {**E0B["by_label"][LABEL], "largest_all_stable_mult": 9.0}}}         # E0b edge far above mu_max=5x
    f = filled(mults=[1.5], e0b=low)
    w = f["predicted_boundaries"]["metastable_window"]
    assert w["hi"] == pytest.approx(0.20) and w["hi_source"] == "mu_max" and f["status"] == "FILLED"
    # no E0b at all: the window's upper edge is UNKNOWN, not mu_max alone -> not fillable
    no = pr_mod.fill(tmpl(), curve(), CAL, e0b=None, e2_cfg=E2CFG, lambda_mults=[1.5], rule="x", p=params())
    assert no["status"] == "INCOMPLETE" and {"e0b_missing", "unfilled"} <= codes(no["fill_problems"])
    assert no["predicted_boundaries"]["metastable_window"]["hi"] is None
    # E0b found no stable rate at all: nothing to test
    none_stable = {"by_label": {LABEL: {**E0B["by_label"][LABEL], "largest_all_stable_mult": None}}}
    ns = filled(mults=[1.5], e0b=none_stable)
    assert ns["status"] == "INCOMPLETE" and "e0b_no_stable_rate" in codes(ns["fill_problems"])
    # E0b must come from the registered cell: an LPM bracket does not bound the FCFS no-burst arm
    with pytest.raises(ValueError, match="E0b bracket has no entry"):
        filled(e0b={"by_label": {"sglang-lpm-r1": E0B["by_label"][LABEL]}})
    # a non-monotone bracket is a warning
    nm = {"by_label": {LABEL: {**E0B["by_label"][LABEL], "monotone": False}}}
    assert "e0b_not_monotone" in codes(filled(mults=[1.5], e0b=nm)["fill_problems"])


def test_fill_refuses_lambda_points_outside_the_window_or_inside_the_margin():
    f = filled(mults=[0.8, 1.5])
    assert f["status"] == "INCOMPLETE" and "lambda_outside_window" in codes(f["fill_problems"])
    ok = filled(mults=[1.15, 2.2])                                                  # margin 0.1: (1.1, 2.25)
    assert ok["status"] == "FILLED"
    bad = filled(mults=[1.05, 2.4])
    assert bad["status"] == "INCOMPLETE" and sum(x["code"] == "lambda_outside_window" for x in bad["fill_problems"]) == 2
    t = tmpl()
    t["lambda_selection"]["boundary_margin_rel"] = None
    assert "no_margin" in codes(pr_mod.fill(t, curve(), CAL, e0b=E0B, e2_cfg=E2CFG, lambda_mults=[1.5], rule="x",
                                            p=params())["fill_problems"])


def test_capped_drain_time_limits_the_lambda_points():
    """Review finding 6: the gate queue drains at mu(n_cap) - lambda; 200 / (mu(n_cap) - lambda) must fit in the run."""
    d = pr_mod.capped_drain(0.20, LAM_MISS, 200, 8700.0, 1200.0, 300.0, 0.8, [1.3, 2.0])
    assert d["post_burst_available_s"] == 7200.0 and d["max_drain_s"] == pytest.approx(5760.0)
    assert d["max_lambda"] == pytest.approx(0.20 - 200 / 5760.0) and d["max_lambda_mult"] == pytest.approx(d["max_lambda"] / LAM_MISS)
    assert d["predicted_drain_s_by_mult"]["1.3"] == pytest.approx(200 / (0.20 - 1.3 * LAM_MISS))
    assert d["predicted_drain_s_by_mult"]["2"] == pytest.approx(200 / (0.20 - 2.0 * LAM_MISS))
    assert pr_mod.capped_drain(0.05, LAM_MISS, 200, 8700.0, 1200.0, 300.0, 0.8, [2.0])["predicted_drain_s_by_mult"]["2"] == float("inf")
    f = filled(mults=MULTS_OK)
    dr = f["predicted_boundaries"]["capped_drain"]
    assert dr["mu_n_cap"] == 0.20 and dr["burst_n"] == 200 and set(dr["predicted_drain_s_by_mult"]) == {"1.3", "1.5", "2"}
    # a slow closed system under the cap: mu(n_cap) = 0.08 => max lambda = 0.08 - 0.0347 = 0.0453 = 1.13 x lambda_miss: the registered
    # points (1.3 x and up) are refused for a reason that has nothing to do with the mechanism
    slow = filled(mults=MULTS_OK, mus=(0.05, 0.06, 0.08, 0.07, 0.05, 0.04, 0.04))
    assert slow["status"] == "INCOMPLETE" and "capped_drain_does_not_fit" in codes(slow["fill_problems"])
    assert slow["predicted_boundaries"]["capped_drain"]["max_lambda_mult"] == pytest.approx(1.132, abs=0.01)


def test_ambiguous_n_cap_and_incomplete_grid_are_warned_about():
    f = filled(mults=[1.5], mus=(0.12, 0.16, 0.199, 0.20, 0.10, 0.06, 0.04))                  # n=24 and n=32 within 5%
    w = {x["code"]: x for x in f["fill_problems"]}
    assert f["status"] == "FILLED" and w["n_cap_ambiguous"]["severity"] == "warn" and f["measured"]["n_cap_ambiguous"] is True
    assert "grid_incomplete" not in w and "n_cap_ambiguous" not in {x["code"] for x in filled(mults=[1.5])["fill_problems"]}


def test_fill_needs_a_rule_and_flags_a_closed_curve_that_disagrees_with_lambda_miss():
    f = filled(mults=[1.5], rule=None)
    assert f["status"] == "INCOMPLETE" and "no_lambda_rule" in codes(f["fill_problems"])
    # mu(300) is only a CHECK now: a 70% transient-inflated value is a warning at most, and does not move the window
    far = filled(mults=[1.5], mus=MUS[:6] + (0.068,))
    w = [x for x in far["fill_problems"] if x["code"] == "mu300_far_from_lambda_miss"]
    assert far["status"] == "FILLED" and len(w) == 1 and w[0]["severity"] == "warn"
    assert far["predicted_boundaries"]["metastable_window"]["lo"] == LAM_MISS
    # a curve whose maximum sits below lambda_miss has an EMPTY window
    empty = filled(mults=[1.5], mus=(0.03, 0.035, 0.036, 0.034, 0.03, 0.03, 0.03))
    assert empty["predicted_boundaries"]["consistency"]["window_nonempty"] is False
    assert empty["status"] == "INCOMPLETE" and "lambda_outside_window" in codes(empty["fill_problems"])


def test_fill_rejects_mismatched_inputs():
    with pytest.raises(ValueError, match="no cell"):
        filled(label="sglang-lpm-r1")
    with pytest.raises(ValueError, match="no key"):
        filled(cal={"lambda_miss": 0.04, "lambda_miss_turns_based": 0.04})                 # no token reference
    c = curve()
    c["estimator"] = "turns_based"
    with pytest.raises(ValueError, match="estimator"):
        pr_mod.fill(tmpl(), c, CAL, e0b=E0B, e2_cfg=E2CFG)


def test_mixed_hardware_or_another_pools_curve_cannot_be_registered():
    """Review finding 5: a curve whose top-level n_cap belongs to another cell, or measured on other hardware, is refused."""
    f = filled(cal={**CAL, "hardware": "other GPU"})
    assert f["status"] == "INCOMPLETE" and "hardware_mismatch" in codes(f["fill_problems"])
    f2 = pr_mod.fill(tmpl(), curve(hardware="other GPU"), CAL, e0b=E0B, e2_cfg=E2CFG, lambda_mults=[1.5], rule="x", p=params())
    assert f2["status"] == "INCOMPLETE" and "hardware_mismatch" in codes(f2["fill_problems"])
    # both pools in one curve: mu_curve takes the alphabetically-first label of a tie as primary (the 300k pool), and fill refuses
    pts = pd.concat([pd.DataFrame([dict(label=lab, seed=0, n=n, mu_sessions=m, mu_turns_based=m, turns_per_s=1.0, hit_frac_turns=0.9,
                                        hit_frac_followup=0.9, cached_frac_tokens=0.9, queue_mean=0.0, aborted=False, hardware="synthetic")
                                   for n, m in zip(CP["n_grid"], mus)]) for lab, mus in ((LABEL, MUS), (LABEL + "-native", MUS[::-1]))])
    both = json.loads(json.dumps(mu_curve(pts, CP)))
    assert both["primary_label"] == LABEL and any("FCFS cells" in x for x in both["notes"])
    ok = json.loads(json.dumps(mu_curve(pts, CP, primary_label=LABEL + "-native")))
    assert ok["primary_label"] == LABEL + "-native" and ok["primary_label_explicit"] is True
    assert ok["n_cap"] == ok["cells"][LABEL + "-native"]["argmax_n"] != both["n_cap"]
    with pytest.raises(ValueError, match="primary_label"):
        mu_curve(pts, CP, primary_label="nope")
    nat_e0b = {"by_label": {LABEL + "-native": E0B["by_label"][LABEL]}}
    native = pr_mod.fill(tmpl(), both, CAL, e0b=nat_e0b, e2_cfg=E2CFG, lambda_mults=[1.5], rule="x", engine_cell_label=LABEL + "-native",
                         p=params())
    assert native["status"] == "INCOMPLETE" and "primary_label_mismatch" in codes(native["fill_problems"])
    native_ok = pr_mod.fill(tmpl(), ok, CAL, e0b=nat_e0b, e2_cfg=E2CFG, lambda_mults=[1.5], rule="x", engine_cell_label=LABEL + "-native",
                            p=params())
    assert native_ok["status"] == "FILLED" and native_ok["inputs"]["engine_cell_label"] == LABEL + "-native"


def test_cli_fill_and_validate(tmp_path, capsys):
    (tmp_path / "mu.json").write_text(json.dumps(curve()))
    (tmp_path / "cal.json").write_text(json.dumps(CAL))
    (tmp_path / "e0b.json").write_text(json.dumps(E0B))
    out = tmp_path / "prereg.yaml"
    args = ["fill", "--template", str(TEMPLATE), "--mu-curve", str(tmp_path / "mu.json"), "--calibration", str(tmp_path / "cal.json"),
            "--e0b-bracket", str(tmp_path / "e0b.json"), "--e2-config", str(REPO / "configs" / "agentload_e2_burst.yaml"),
            "--out", str(out), "--lambda-mults", "1.3", "1.6", "--rule", "inside the window"]
    assert pr_mod.main(args) == 0 and out.exists()
    assert yaml.safe_load(out.read_text())["status"] == "FILLED"
    assert yaml.safe_load(out.read_text())["protocol"]["duration_s"] == 8700            # read from the real E2 config
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
def test_file_provenance_tracks_commit_state_and_first_and_last_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    f = repo / "prereg.yaml"
    f.write_text("a: 1\n")
    p0 = pr_mod.file_provenance(f)
    assert len(p0["sha256"]) == 64 and not p0["git_tracked"] and not p0["committed_clean"] and p0["git_last_commit"] is None
    assert p0["git_first_commit_unix"] is None and p0["git_last_commit_unix"] is None
    git(repo, "add", "prereg.yaml")
    git(repo, "commit", "-q", "-m", "x")
    p1 = pr_mod.file_provenance(f)
    assert p1["committed_clean"] and p1["git_tracked"] and len(p1["git_last_commit"]) == 40 and p1["sha256"] == p0["sha256"]
    assert p1["git_first_commit"] == p1["git_last_commit"] and abs(p1["git_last_commit_unix"] - time.time()) < 120
    f.write_text("a: 2\n")
    p2 = pr_mod.file_provenance(f)
    assert not p2["committed_clean"] and p2["git_modified_since_commit"] and p2["sha256"] != p1["sha256"]
    git(repo, "commit", "-q", "-am", "edit after the fact")
    p3 = pr_mod.file_provenance(f)
    assert p3["committed_clean"] and p3["git_first_commit"] == p1["git_first_commit"] and p3["git_last_commit"] != p1["git_last_commit"]


# ------------------------------------------------------------------------------------------------ burst2 --prereg
@lru_cache(maxsize=None)
def _base_runs(label, mult, n_cap):
    runs = []
    for seed in range(3):
        for arm, scen in (("burst", scenario_trapped()), ("noburst", scenario_recovered()), ("capped", scenario_recovered())):
            runs.append(synth_run(arm=arm, seed=seed, label=label, mult=mult, n_cap=n_cap, **{**scen, "burst_n": 200}))
    return tuple(runs)


def paired_runs(sha=None, label=LABEL, mult=MULT, n_cap=N_CAP, t0=None, edit=None):
    """Three seeds of the three arms at lambda = mult x lambda_ref (BURST trapped, others good), bound to ``sha``."""
    runs = [copy.deepcopy(r) for r in _base_runs(label, mult, n_cap)]
    for r in runs:
        r.meta["prereg_sha256"] = sha
        if t0 is not None:
            r.meta["t0_unix"] = t0
        if edit:
            edit(r)
    return runs


def burst2(tmp_path, prereg_file, runs, *extra):
    dirs = [write_run_dir(r, tmp_path / "runs") for r in runs]
    out_root = tmp_path / "an"
    args = ["burst2", "--run-dirs", *map(str, dirs), "--out-root", str(out_root), "--set", "burst.trap_min_s=3000",
            "--set", "burst.hit_eval_from_s=4500", *extra]
    if prereg_file is not None:
        args += ["--prereg", str(prereg_file)]
    assert analysis_main(args) == 0
    d = sorted((out_root / "agentload_analysis_burst2").iterdir())[-1]
    return json.loads((d / "kill_verdict_v2.json").read_text())


@pytest.fixture()
def registered(tmp_path):
    """A temp git repo holding a filled, COMMITTED pre-registration of the cell (LABEL, MULTS_OK)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    f = filled()
    assert f["status"] == "FILLED"
    path = repo / "prereg.yaml"
    path.write_text(yaml.safe_dump(f, sort_keys=False))
    git(repo, "add", "prereg.yaml")
    git(repo, "commit", "-q", "-m", "register")
    return repo, path, pr_mod.file_provenance(path)


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


@needs_git
def test_burst2_decisive_only_with_a_committed_valid_prereg_bound_runs_and_registered_cell(tmp_path, registered):
    repo, path, prov = registered
    sha = prov["sha256"]
    # 1. no prereg: exploratory
    kv = burst2(tmp_path / "a", None, paired_runs())
    assert kv["kill_test_pass_rule_only"] is True and kv["kill_test_pass_decisive"] is None and kv["pre_registered"] is False
    # 2. valid, committed, runs bound to the file, registered cell and lambda inside the window: decisive PASS
    kv = burst2(tmp_path / "b", path, paired_runs(sha=sha))
    assert kv["pre_registered"] is True and kv["kill_test_pass_decisive"] is True and kv["prereg"]["valid"]
    (cell,) = kv["cells"]
    assert cell["registered_label"] and cell["registered_lambda"] and cell["in_registered_window"] is True
    assert cell["registration_blockers"] == {} and cell["decisive_eligible"] and kv["decisive_cells"] == [{"label": LABEL, "rate_mult": MULT}]
    assert kv["prereg"]["provenance"]["git_first_commit_unix"] and kv["prereg"]["window"]["lo"] == LAM_MISS
    # 3. the runs were NOT launched under this file (no sha in meta, or another file's): never decisive
    for bad in (None, "0" * 64):
        kv = burst2(tmp_path / f"c{bad}", path, paired_runs(sha=bad))
        assert kv["kill_test_pass_rule_only"] is True and kv["kill_test_pass_decisive"] is False
        assert any("not bound to this file" in x for bl in kv["cells"][0]["registration_blockers"].values() for x in bl)


@needs_git
def test_the_loophole_of_the_review_vllm_fcfs_at_an_unregistered_lambda_is_not_decisive(tmp_path):
    """Review finding 4 (probe): a prereg registering ONLY 1.2 x, committed, then `burst2 --prereg` on runs labelled vllm-fcfs at
    1.5 x used to print pre_registered True / kill_test_pass_decisive True. Three gaps: any 'fcfs' substring counted, rate_mult
    was never compared with lambda_mults, and the commit time was never compared with the runs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    f = filled(mults=[1.2])
    path = repo / "prereg.yaml"
    path.write_text(yaml.safe_dump(f, sort_keys=False))
    git(repo, "add", "prereg.yaml")
    git(repo, "commit", "-q", "-m", "register 1.2x only")
    sha = pr_mod.file_provenance(path)["sha256"]
    for i, label in enumerate(("vllm-fcfs", "sglang-fcfs-r0", LABEL + "-native", LABEL)):
        kv = burst2(tmp_path / f"x{i}", path, paired_runs(sha=sha, label=label))            # all at 1.5 x, which is NOT registered
        assert kv["pre_registered"] is True                                                  # the FILE is fine ...
        assert kv["kill_test_pass_rule_only"] is True                                        # ... the rule is met ...
        assert kv["kill_test_pass_decisive"] is False and kv["decisive_cells"] == [], label  # ... but this is not the registered cell
        cell = kv["cells"][0]
        assert cell["registered_lambda"] is False and cell["registered_label"] is (label == LABEL)


@needs_git
def test_runs_that_started_before_the_last_commit_are_not_decisive(tmp_path, registered):
    repo, path, prov = registered
    early = prov["git_last_commit_unix"] - 3600.0                                            # an hour before the registration
    kv = burst2(tmp_path / "a", path, paired_runs(sha=prov["sha256"], t0=early))
    assert kv["pre_registered"] is True and kv["kill_test_pass_rule_only"] is True and kv["kill_test_pass_decisive"] is False
    assert any("does not predate the run" in x for bl in kv["cells"][0]["registration_blockers"].values() for x in bl)
    # an edit committed AFTER the runs started moves the last commit past them, even though the file is clean again
    f2 = yaml.safe_load(path.read_text())
    f2["lambda_selection"]["rule"] = "rewritten after seeing the runs"
    path.write_text(yaml.safe_dump(f2, sort_keys=False))
    git(repo, "commit", "-q", "-am", "late edit")
    prov2 = pr_mod.file_provenance(path)
    assert prov2["committed_clean"] and prov2["git_first_commit"] == prov["git_first_commit"]
    t0 = prov2["git_last_commit_unix"] - 1.0
    kv = burst2(tmp_path / "b", path, paired_runs(sha=prov2["sha256"], t0=t0))
    assert kv["kill_test_pass_decisive"] is False


@needs_git
def test_run_blockers_name_each_registered_quantity(tmp_path, registered):
    repo, path, prov = registered
    pr = pr_mod.load_prereg(path)
    ok = paired_runs(sha=prov["sha256"])
    assert all(pr_mod.run_blockers(pr, prov, _load(tmp_path, r)) == [] for r in ok)
    cases = {
        "hardware": lambda r: r.meta.update(hardware="other GPU"),
        "lambda_ref": lambda r: r.meta.update(lambda_ref_resolved=0.05),
        "uncached_tokens_ref": lambda r: r.meta.update(uncached_tokens_ref_resolved=TOK_REF * 2),
        "run.duration_s": lambda r: r.cfg["run"].update(duration_s=7000),
        "burst spec": lambda r: r.cfg["arrivals"].update(burst=None if r.cfg["arrivals"]["burst"] is None else {"n": 100, "t_s": 1200, "width_s": 60.0}),
    }
    for name, edit in cases.items():
        bad = paired_runs(sha=prov["sha256"], edit=lambda r, e=edit: e(r))
        found = [pr_mod.run_blockers(pr, prov, _load(tmp_path, r)) for r in bad]
        assert any(found), name
    capped = [r for r in paired_runs(sha=prov["sha256"], n_cap=22) if r.cfg["gate"]["n_cap"] is not None]
    assert any("gate cap 22 != registered n_cap 24" in x for r in capped for x in pr_mod.run_blockers(pr, prov, _load(tmp_path, r)))


_COUNTER = itertools.count()


def _load(tmp_path, run):
    from analysis.load import load_run
    return load_run(write_run_dir(run, tmp_path / "blk" / str(next(_COUNTER))))


@needs_git
def test_uncommitted_modified_or_drifted_prereg_is_not_decisive(tmp_path, registered):
    repo, path, prov = registered
    # committed but then modified in the working tree
    path.write_text(path.read_text() + "\n# touched\n")
    kv = burst2(tmp_path / "a", path, paired_runs(sha=prov["sha256"]))
    assert kv["prereg"]["valid"] and not kv["prereg"]["committed_clean"] and kv["pre_registered"] is False
    assert kv["kill_test_pass_decisive"] is None and kv["kill_test_pass_rule_only"] is True
    git(repo, "checkout", "--", "prereg.yaml")
    # a registered rule that differs from the applied one invalidates the registration
    drift = yaml.safe_load(path.read_text())
    drift["pass_rule"]["recovered_hit_above"] = 0.9
    h = repo / "drift.yaml"
    h.write_text(yaml.safe_dump(drift, sort_keys=False))
    git(repo, "add", "drift.yaml")
    git(repo, "commit", "-q", "-m", "drift")
    kv = burst2(tmp_path / "b", h, paired_runs(sha=pr_mod.file_provenance(h)["sha256"]))
    assert kv["prereg"]["valid"] is False and kv["pre_registered"] is False and kv["kill_test_pass_decisive"] is None
    assert any(x["code"] == "rule_mismatch" for x in kv["prereg"]["problems"])
    # an analysis-side --set that changes what 'hit' means is caught the same way (finding 8)
    kv = burst2(tmp_path / "c", path, paired_runs(sha=prov["sha256"]), "--set", "windows.hit_metric=token_hit_rate")
    assert kv["prereg"]["valid"] is False and kv["kill_test_pass_decisive"] is None


# ------------------------------------------------------------------------------------------------ job-start authorisation
@needs_git
def test_check_job_authorises_only_the_registered_job(tmp_path, registered, capsys):
    repo, path, prov = registered
    cal = tmp_path / "calibration.json"
    cal.write_text(json.dumps(CAL))
    base = [str(path), "--label", LABEL, "--mults", "1.3 1.5", "--n-cap", str(N_CAP), "--calib", str(cal), "--hardware", "synthetic",
            "--duration-s", "8700", "--t-burst-s", "1200"]
    assert pr_mod.main(["check-job", *base]) == 0
    out = capsys.readouterr().out
    assert f"PREREG_SHA256={prov['sha256']}" in out and "PREREG_OK" in out
    wrong = {"label": ["--label", "vllm-fcfs"], "mults": ["--mults", "1.3 1.7"], "n_cap": ["--n-cap", "22"],
             "hardware": ["--hardware", "other GPU"], "duration": ["--duration-s", "7000"], "t_burst": ["--t-burst-s", "900"]}
    for name, override in wrong.items():
        rc = pr_mod.main(["check-job", *base, *override])               # later duplicates of an option win in argparse
        out = capsys.readouterr().out
        assert rc == 1 and "PREREG PROBLEM" in out and "PREREG_SHA256" not in out, name
    cal2 = tmp_path / "calibration2.json"
    cal2.write_text(json.dumps({**CAL, "all_miss_uncached_tokens_per_s": TOK_REF * 1.2}))
    assert pr_mod.main(["check-job", *base, "--calib", str(cal2)]) == 1
    assert "CALIB_FILE" in capsys.readouterr().out
    # not committed: refused (and the test-only escape hatch lets the smoke test through)
    loose = tmp_path / "loose.yaml"
    loose.write_text(path.read_text())
    assert pr_mod.main(["check-job", str(loose), *base[1:]]) == 1
    assert "not committed" in capsys.readouterr().out
    assert pr_mod.main(["check-job", str(loose), *base[1:], "--allow-uncommitted"]) == 0
    # an unfilled template never authorises anything
    assert pr_mod.main(["check-job", str(TEMPLATE), *base[1:], "--allow-uncommitted"]) == 1
