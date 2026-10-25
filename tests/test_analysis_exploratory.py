"""Derived grid registrations report run states without becoming decisive kill tests."""
import json
import shutil

import pandas as pd
import pytest
import yaml

from analysis import prereg as pr_mod
from helpers_trap import MULT, scenario_draining, scenario_recovered, scenario_trapped, synth_run
from test_prereg import CAL, LABEL, burst2, filled, git, paired_runs


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
GRID_LABEL = "sglang-fcfs-r0"


@pytest.fixture()
def grid_registration(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    cal = repo / "calibration.json"
    cal.write_text(json.dumps(CAL))
    parent = repo / "parent.yaml"
    parent.write_text(yaml.safe_dump(filled(calibration_path="calibration.json"), sort_keys=False))
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "register parent")
    child = repo / "grid.yaml"
    assert pr_mod.main(["derive-exploratory", "--from", str(parent), "--engine-cell-label", GRID_LABEL,
                        "--out", str(child)]) == 0
    git(repo, "add", "grid.yaml")
    git(repo, "commit", "-q", "-m", "register exploratory grid")
    return repo, parent, child


def test_burst2_exploratory_reports_trapped_recovered_and_neither(tmp_path, grid_registration):
    _, _, child = grid_registration
    prov = pr_mod.file_provenance(child)
    runs = []
    for seed, scenario in enumerate((scenario_trapped(), scenario_recovered(), scenario_draining())):
        run = synth_run(arm="burst", label=GRID_LABEL, seed=seed, **{**scenario, "burst_n": 200})
        run.meta["prereg_sha256"] = prov["sha256"]
        runs.append(run)
    kv = burst2(tmp_path / "analysis", child, runs)
    assert kv["prereg"]["status"] == "EXPLORATORY" and kv["prereg"]["valid"]
    assert kv["prereg"]["committed_clean"] and not kv["pre_registered"]
    assert kv["prereg"]["exploratory"]["allowed_arms"] == ["burst"]
    assert kv["prereg"]["window_scope"] == "inherited_parent_not_measured_for_cell"
    assert kv["kill_test_pass_decisive"] is None and kv["decisive_cells"] == []
    cell, = kv["cells"]
    assert cell["exploratory"] and not cell["decisive_eligible"]
    assert cell["diagnosis"].startswith("EXPLORATORY:") and cell["in_registered_window"] is None
    assert cell["registration_blockers"] == {}
    assert [(r["seed"], r["classification"]) for r in kv["runs"]] == [(0, "TRAPPED"), (1, "RECOVERED"), (2, "neither")]
    out, = (tmp_path / "analysis" / "an" / "agentload_analysis_burst2").iterdir()
    table = pd.read_csv(out / "trap_v2_runs.csv")
    assert table["classification"].tolist() == ["TRAPPED", "RECOVERED", "neither"]
    assert table["state"].tolist() == ["trapped", "recovered", "draining"]


def test_complete_exploratory_pairs_are_never_decisive(tmp_path, grid_registration):
    _, _, child = grid_registration
    sha = pr_mod.file_provenance(child)["sha256"]
    kv = burst2(tmp_path / "analysis", child, paired_runs(sha=sha, label=GRID_LABEL))
    assert kv["kill_test_pass_rule_only"] is True
    assert kv["kill_test_pass_decisive"] is None and not kv["pre_registered"] and kv["decisive_cells"] == []
    cell, = kv["cells"]
    assert cell["meets_valid_pairing"] and not cell["decisive_eligible"] and cell["exploratory"]
    assert cell["diagnosis"].startswith("EXPLORATORY:")
    assert any("arm" in reason for reasons in cell["registration_blockers"].values() for reason in reasons)


def test_derived_runs_cannot_enter_the_parent_decisive_verdict(tmp_path, grid_registration):
    _, parent, child = grid_registration
    parent_sha = pr_mod.file_provenance(parent)["sha256"]
    child_sha = pr_mod.file_provenance(child)["sha256"]
    runs = paired_runs(sha=parent_sha) + paired_runs(sha=child_sha, label=GRID_LABEL)
    kv = burst2(tmp_path / "combined", parent, runs)
    assert kv["pre_registered"] and kv["kill_test_pass_decisive"] is True
    assert kv["decisive_cells"] == [{"label": LABEL, "rate_mult": MULT}]
    grid, = [c for c in kv["cells"] if c["label"] == GRID_LABEL]
    assert grid["exploratory"] and not grid["decisive_eligible"]
    assert all(any("not bound to this file" in reason for reason in reasons)
               for reasons in grid["registration_blockers"].values())
    # Even a run falsely claiming the parent's label remains bound to the derived file's distinct SHA.
    spoofed = burst2(tmp_path / "spoofed", parent, paired_runs(sha=child_sha, label=LABEL))
    assert spoofed["kill_test_pass_rule_only"] is True and spoofed["kill_test_pass_decisive"] is False
    assert spoofed["decisive_cells"] == []
    assert all(any("not bound to this file" in reason for reason in reasons)
               for reasons in spoofed["cells"][0]["registration_blockers"].values())


def test_exploratory_marker_cannot_be_promoted_by_editing_status(tmp_path, grid_registration):
    repo, _, child = grid_registration
    changed = pr_mod.load_prereg(child)
    changed["status"] = "FILLED"
    child.write_text(yaml.safe_dump(changed, sort_keys=False))
    git(repo, "commit", "-q", "-am", "change status")
    sha = pr_mod.file_provenance(child)["sha256"]
    kv = burst2(tmp_path / "analysis", child, paired_runs(sha=sha, label=GRID_LABEL))
    assert not kv["pre_registered"] and kv["kill_test_pass_decisive"] is None
    assert kv["decisive_cells"] == [] and not kv["cells"][0]["decisive_eligible"]
    assert kv["cells"][0]["exploratory"]
