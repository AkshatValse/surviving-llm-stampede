"""Exploratory cells inherit the kill-test protocol without becoming registered kill tests."""
import copy
import hashlib
import json
import shutil

import pytest
import yaml

from analysis import prereg as pr_mod
from helpers_analysis import params
from test_prereg import CAL, E2CFG, LABEL, MULTS_OK, N_CAP, TOK_REF, filled, git


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
GRID_LABEL = "sglang-lpm-r1"


def _write_yaml(path, value):
    path.write_text(yaml.safe_dump(value, sort_keys=False))


def _commit(repo, *paths):
    git(repo, "add", *[str(p.relative_to(repo)) for p in paths])
    git(repo, "commit", "-q", "-m", "record synthetic registration")


@pytest.fixture()
def parent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "configs").mkdir()
    (repo / "inputs").mkdir()
    calibration = repo / "inputs" / "calibration.json"
    calibration.write_text(json.dumps(CAL))
    path = repo / "configs" / "parent.yaml"
    _write_yaml(path, filled(calibration_path="inputs/calibration.json"))
    _commit(repo, path, calibration)
    return repo, path, calibration


def _derive(parent, **kwargs):
    return pr_mod.derive_exploratory(parent[1], engine_cell_label=kwargs.pop("engine_cell_label", GRID_LABEL),
                                     p=params(), **kwargs)


def _save_derived(parent, pr=None, commit=True):
    repo, _, _ = parent
    path = repo / "configs" / "grid.yaml"
    _write_yaml(path, _derive(parent) if pr is None else pr)
    if commit:
        _commit(repo, path)
    return path


def _check(parent, path, **kwargs):
    args = dict(label=GRID_LABEL, arms=["burst"], mults=MULTS_OK, calibration=CAL, calibration_path=parent[2],
                hardware="synthetic", e2_cfg=E2CFG, fcfs_substr="fcfs")
    args.update(kwargs)
    return pr_mod.check_job(pr_mod.load_prereg(path), pr_mod.file_provenance(path), params(), **args)


def test_derive_records_parent_hash_and_preserves_registered_protocol(parent):
    _, path, _ = parent
    before = path.read_bytes()
    source = pr_mod.load_prereg(path)
    derived = _derive(parent)
    assert derived["status"] == "EXPLORATORY"
    assert derived["inputs"]["engine_cell_label"] == GRID_LABEL
    assert derived["exploratory"]["parent"] == {
        "path": "configs/parent.yaml", "sha256": hashlib.sha256(before).hexdigest()}
    assert derived["exploratory"]["allowed_arms"] == ["burst"]
    assert derived["exploratory"]["inherited_from_engine_cell_label"] == LABEL
    assert derived["exploratory"]["inherited_window_lambda_ref"] == source["measured"]["lambda_ref"]
    assert "inherited" in derived["exploratory"]["boundary_note"].lower()
    for key in ("protocol", "lambda_selection", "pass_rule", "predicted_boundaries", "measured"):
        assert derived[key] == source[key], key
    assert derived["inputs"]["calibration_json"] == source["inputs"]["calibration_json"]
    assert "calibration_override" not in derived["exploratory"]
    derived["protocol"]["duration_s"] = 1
    assert path.read_bytes() == before and source["protocol"]["duration_s"] == 8700


def test_derive_cli_writes_new_file_and_never_overwrites(parent, capsys):
    repo, path, _ = parent
    out = repo / "configs" / "cli-grid.yaml"
    args = ["derive-exploratory", "--from", str(path), "--engine-cell-label", GRID_LABEL, "--out", str(out)]
    assert pr_mod.main(args) == 0
    saved = out.read_bytes()
    assert pr_mod.load_prereg(out)["status"] == "EXPLORATORY"
    assert pr_mod.main(["validate", str(out)]) == 0
    assert pr_mod.main(args) == 2
    assert "overwrite" in capsys.readouterr().err.lower()
    assert out.read_bytes() == saved


@pytest.mark.parametrize("label", [LABEL, ""])
def test_derive_refuses_registered_or_empty_label(parent, label):
    with pytest.raises(ValueError):
        _derive(parent, engine_cell_label=label)


@pytest.mark.parametrize("arms", [(), ("unknown",), ("burst", "unknown"), ("burst", "burst")])
def test_derive_refuses_empty_or_unknown_allowed_arms(parent, arms):
    with pytest.raises(ValueError):
        _derive(parent, arms=arms)


def test_explicit_allowed_arms_are_enforced(parent):
    derived = _derive(parent, arms=("burst", "noburst"))
    assert derived["exploratory"]["allowed_arms"] == ["burst", "noburst"]
    path = _save_derived(parent, derived)
    assert _check(parent, path, arms=["burst", "noburst"]) == []
    assert _check(parent, path, arms=["capped"])


@pytest.mark.parametrize("change", ["uncommitted", "dirty", "invalid", "exploratory"])
def test_derive_requires_a_committed_clean_valid_filled_parent(parent, change):
    repo, path, _ = parent
    if change == "uncommitted":
        loose = repo / "configs" / "loose.yaml"
        loose.write_bytes(path.read_bytes())
        parent = (repo, loose, parent[2])
    elif change == "dirty":
        path.write_text(path.read_text() + "\n# changed after commit\n")
    else:
        source = pr_mod.load_prereg(path)
        if change == "invalid":
            source["lambda_selection"]["lambda_mults"] = [99.0]
        else:
            source["status"] = "EXPLORATORY"
        _write_yaml(path, source)
        _commit(repo, path)
    with pytest.raises(ValueError):
        _derive(parent)


def _other_calibration(parent, values=None):
    repo, _, _ = parent
    path = repo / "inputs" / "vllm-calibration.json"
    values = values if values is not None else {
        **CAL, "lambda_miss": 0.082, "lambda_miss_turns_based": 0.08,
        "all_miss_uncached_tokens_per_s": TOK_REF * 2}
    path.write_text(json.dumps(values))
    _commit(repo, path)
    return path, values


def test_other_engine_uses_own_calibration_but_inherits_window_and_lambda_multiples(parent):
    cal_path, cal = _other_calibration(parent)
    derived = _derive(parent, engine_cell_label="vllm-fcfs", calibration_path=cal_path)
    source = pr_mod.load_prereg(parent[1])
    assert derived["status"] == "EXPLORATORY"
    assert derived["inputs"]["calibration_json"] == "inputs/vllm-calibration.json"
    assert derived["measured"]["lambda_ref"] == cal["lambda_miss_turns_based"]
    assert derived["measured"]["all_miss_uncached_tokens_per_s"] == cal["all_miss_uncached_tokens_per_s"]
    assert derived["exploratory"]["calibration_override"] == {
        "path": "inputs/vllm-calibration.json", "sha256": hashlib.sha256(cal_path.read_bytes()).hexdigest()}
    for key in ("protocol", "lambda_selection", "pass_rule", "predicted_boundaries"):
        assert derived[key] == source[key], key
    assert pr_mod.window_of(derived) == pr_mod.window_of(source)
    assert derived["exploratory"]["inherited_window_lambda_ref"] == source["measured"]["lambda_ref"]
    assert pr_mod.window_of(derived)["lambda_ref"] != derived["measured"]["lambda_ref"]
    note = derived["exploratory"]["boundary_note"].lower()
    assert "inherited" in note and "not measured" in note and "sglang" in note
    path = _save_derived(parent, derived)
    assert _check(parent, path, label="vllm-fcfs", calibration=cal, calibration_path=cal_path) == []
    assert _check(parent, path, label="vllm-fcfs")


def test_vllm_requires_its_own_calibration(parent):
    with pytest.raises(ValueError):
        _derive(parent, engine_cell_label="vllm-fcfs")


def test_other_engine_refuses_a_calibration_labelled_as_sglang(parent):
    path, _ = _other_calibration(parent, {**CAL, "labels": ["sglang-nocache"]})
    with pytest.raises(ValueError, match="labels"):
        _derive(parent, engine_cell_label="vllm-fcfs", calibration_path=path)


@pytest.mark.parametrize("field,value", [
    ("lambda_miss_turns_based", 0), ("lambda_miss_turns_based", -0.1),
    ("lambda_miss_turns_based", float("nan")), ("lambda_miss_turns_based", float("inf")),
    ("all_miss_uncached_tokens_per_s", 0), ("all_miss_uncached_tokens_per_s", float("inf")),
    ("hardware", "another GPU")])
def test_calibration_override_requires_positive_finite_rates_and_matching_hardware(parent, field, value):
    path, _ = _other_calibration(parent, {**CAL, field: value})
    with pytest.raises(ValueError):
        _derive(parent, engine_cell_label="vllm-fcfs", calibration_path=path)


def test_check_job_authorises_committed_exploratory_cell_and_prints_binding(parent, capsys):
    _, _, calibration = parent
    path = _save_derived(parent)
    assert _check(parent, path) == []
    args = ["check-job", str(path), "--label", GRID_LABEL, "--arms", "burst", "--mults", "1.3 1.5",
            "--calib", str(calibration), "--hardware", "synthetic", "--duration-s", "8700", "--t-burst-s", "1200"]
    assert pr_mod.main(args) == 0
    output = capsys.readouterr().out
    assert f"PREREG_SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}" in output
    assert "PREREG_OK" in output
    assert pr_mod.main([*args, "--arms", "noburst"]) == 1
    assert "PREREG_SHA256" not in capsys.readouterr().out


@pytest.mark.parametrize("override", [
    {"label": LABEL}, {"label": "sglang-fcfs-r0"},
    {"arms": ["noburst"]}, {"arms": ["capped"]}, {"arms": ["burst", "capped"]}, {"arms": []}, {"arms": None},
    {"mults": [1.7]}, {"n_cap": N_CAP - 1}, {"hardware": "other GPU"},
    {"hardware": "other GPU", "allow_hw_mismatch": True}, {"calibration": None},
    {"calibration": {**CAL, "lambda_miss_turns_based": 0.08}},
    {"calibration": {**CAL, "all_miss_uncached_tokens_per_s": TOK_REF * 2}}])
def test_check_job_refuses_mismatching_cell_arm_lambda_cap_hardware_and_rates(parent, override):
    path = _save_derived(parent)
    assert _check(parent, path, **override)


@pytest.mark.parametrize("field", ["duration_s", "analysis_t_burst_s", "n", "width_s"])
def test_check_job_keeps_the_registered_protocol_checks(parent, field):
    path = _save_derived(parent)
    cfg = copy.deepcopy(E2CFG)
    target = cfg["run"] if field == "duration_s" else (
        cfg["arrivals"] if field == "analysis_t_burst_s" else cfg["arrivals"]["burst"])
    target[field] += 1
    assert _check(parent, path, e2_cfg=cfg)


@pytest.mark.parametrize("state", ["untracked", "staged", "dirty"])
def test_exploratory_file_must_be_committed_and_clean_even_with_smoke_test_escape(parent, state):
    repo, _, _ = parent
    path = _save_derived(parent, commit=state == "dirty")
    if state == "staged":
        git(repo, "add", "configs/grid.yaml")
    elif state == "dirty":
        path.write_text(path.read_text() + "\n# changed after commit\n")
    for allow in (False, True):
        assert _check(parent, path, allow_uncommitted=allow)


@pytest.mark.parametrize("state", ["wrong_hash", "parent_recommitted", "parent_dirty"])
def test_check_job_requires_the_original_committed_parent_bytes(parent, state):
    repo, source, _ = parent
    derived = _derive(parent)
    if state == "wrong_hash":
        derived["exploratory"]["parent"]["sha256"] = "0" * 64
    path = _save_derived(parent, derived)
    if state != "wrong_hash":
        source.write_text(source.read_text() + "\n# changed parent bytes\n")
        if state == "parent_recommitted":
            _commit(repo, source)
    assert _check(parent, path)


def test_parent_binding_uses_committed_bytes_when_git_assumes_parent_unchanged(parent):
    repo, source, _ = parent
    derived = _derive(parent)
    committed_sha = derived["exploratory"]["parent"]["sha256"]
    git(repo, "update-index", "--assume-unchanged", "configs/parent.yaml")
    source.write_text(source.read_text() + "\n# modification hidden from git status\n")
    prov = pr_mod.file_provenance(source)
    assert prov["committed_clean"] and prov["sha256"] != committed_sha
    with pytest.raises(ValueError, match="committed parent"):
        _derive(parent)
    # A crafted derivation bound to the altered working bytes still cannot claim those bytes were committed.
    derived["exploratory"]["parent"]["sha256"] = prov["sha256"]
    path = _save_derived(parent, derived)
    problems = pr_mod.validate(pr_mod.load_prereg(path), params(), prereg_path=path)
    assert any(p["code"] == "parent_sha_mismatch" and p["severity"] == "error" for p in problems)
    assert any("parent_sha_mismatch" in problem for problem in _check(parent, path))


@pytest.mark.parametrize("field", ["protocol", "lambda_selection", "pass_rule", "predicted_boundaries", "measured"])
def test_inherited_values_cannot_be_changed_in_a_committed_derived_file(parent, field):
    derived = _derive(parent)
    if field == "protocol":
        derived[field]["duration_s"] += 1
    elif field == "lambda_selection":
        derived[field]["lambda_mults"] = [1.3]
    elif field == "pass_rule":
        derived[field]["rate_tolerance"] += 0.01
    elif field == "predicted_boundaries":
        derived[field]["metastable_window"]["hi"] += 0.01
    else:
        derived[field]["lambda_ref"] *= 2
    path = _save_derived(parent, derived)
    assert _check(parent, path)


@pytest.mark.parametrize("tamper", ["status", "registered_label"])
def test_derived_file_cannot_masquerade_as_the_registered_kill_test(parent, tamper):
    derived = _derive(parent)
    if tamper == "status":
        derived["status"] = "FILLED"
    else:
        derived["inputs"]["engine_cell_label"] = LABEL
    path = _save_derived(parent, derived)
    assert _check(parent, path, label=derived["inputs"]["engine_cell_label"])


def test_override_calibration_hash_is_bound_even_when_reference_rates_are_unchanged(parent):
    repo, _, _ = parent
    cal_path, cal = _other_calibration(parent)
    derived = _derive(parent, engine_cell_label="vllm-fcfs", calibration_path=cal_path)
    path = _save_derived(parent, derived)
    cal_path.write_text(json.dumps({**cal, "comment": "changed bytes, same rates"}))
    _commit(repo, cal_path)
    assert _check(parent, path, label="vllm-fcfs", calibration=cal, calibration_path=cal_path)
