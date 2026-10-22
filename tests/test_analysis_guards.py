"""Consistency guards in the analysis: unverified start state, mixed hardware, calibration hardware, output-id source."""
import json
from pathlib import Path

import pandas as pd
import pytest

from analysis import guards
from analysis.guards import check_runs
from analysis.summarize import main as analysis_main
from conftest import make_raw, run_gen
from agentload.mock_server import MockConfig

FAST = dict(kv_capacity_tokens=10**7, slots=64, fixed_s=0.001, per_uncached_token_s=0, per_completion_token_s=0)


def codes(problems):
    return sorted(p["code"] for p in problems)


def open_run(tmp_path, name, **meta_sections):
    raw = make_raw(arrivals={"rate": 4.0}, run={"duration_s": 2.5}, metrics={"enabled": True}, meta={"engine_label": "mock-fcfs", **meta_sections})
    out, _ = run_gen(raw, MockConfig(**FAST), tmp_path / name)
    from analysis.load import load_run
    return load_run(out.out_dir)


def test_unverified_start_state_is_an_error_for_open_loop_runs_only(tmp_path):
    unk = open_run(tmp_path, "a")                                          # start_state_verified not recorded
    bad = open_run(tmp_path, "b", start_state_verified=False, start_state_detail="canary 1: check rc=1")
    ok = open_run(tmp_path, "c", start_state_verified=True)
    assert codes(check_runs([ok], True)) == []
    p = check_runs([unk, bad, ok], True)
    assert codes(p) == ["start_state_unverified"] * 2
    assert "not recorded" in p[0]["message"] and "check rc=1" in p[1]["message"]
    assert all(x["severity"] == "error" for x in p)
    assert codes(check_runs([unk], False)) == []                           # windows / miss do not need it


def test_closed_population_runs_are_exempt_from_the_start_state_guard(tmp_path):
    raw = make_raw(arrivals={"kind": "closed", "rate": None, "closed_n": 3}, workload={"mean_turns": 2, "max_turns": 3},
                   run={"duration_s": 2.0}, metrics={"enabled": False})
    out, _ = run_gen(raw, MockConfig(**FAST), tmp_path)
    from analysis.load import load_run
    assert codes(check_runs([load_run(out.out_dir)], True)) == []


def test_mixed_hardware_and_calibration_mismatch(tmp_path):
    a = open_run(tmp_path, "a", hardware="NVIDIA A100 80GB PCIe, 81920 MiB", start_state_verified=True)
    b = open_run(tmp_path, "b", hardware="NVIDIA A100-SXM4-80GB, 81920 MiB", start_state_verified=True)
    assert codes(check_runs([a], True)) == [] and codes(check_runs([a, b], True)) == ["hardware_mixed"]
    cal = tmp_path / "calibration.json"
    cal.write_text(json.dumps({"lambda_miss_turns_based": 1.0, "hardware": "NVIDIA A100-SXM4-80GB, 81920 MiB"}))
    a.cfg["arrivals"]["lambda_ref"] = f"{cal}:lambda_miss_turns_based"
    b.cfg["arrivals"]["lambda_ref"] = f"{cal}:lambda_miss_turns_based"
    p = check_runs([a, b], True)
    assert codes(p) == ["hardware_mixed", "hardware_vs_calibration"] and p[1]["run_dir"] == str(a.dir)
    cal.write_text(json.dumps({"lambda_miss_turns_based": 1.0, "hardware": None}))
    assert "calibration_hardware" in codes(check_runs([a], True))


def test_output_source_must_be_uniform_within_and_across_runs(tmp_path):
    srv = open_run(tmp_path, "a", start_state_verified=True)
    syn = open_run(tmp_path, "b", start_state_verified=True)
    syn.meta["outcome"]["output_ids_source_counts"] = {"synthetic": 40}
    mixed = open_run(tmp_path, "c", start_state_verified=True)
    mixed.meta["outcome"]["output_ids_source_counts"] = {"synthetic": 10, "server_ids": 30}
    assert srv.output_ids_sources and set(srv.output_ids_sources) == {"server_ids"}
    assert codes(check_runs([srv, syn], True)) == ["output_source_differs"]
    assert codes(check_runs([mixed], True)) == ["output_source_mixed"]
    assert codes(check_runs([srv, srv], True)) == []


def test_old_runs_without_counts_fall_back_to_the_request_log(tmp_path):
    r = open_run(tmp_path, "a")
    del r.meta["outcome"]["output_ids_source_counts"]
    assert set(r.output_ids_sources) == {"server_ids"}


def test_prompt_mismatch_and_transport_errors_are_flagged(tmp_path):
    r = open_run(tmp_path, "a", start_state_verified=True)
    r.meta["outcome"]["prompt_tokens_mismatch"] = 3
    r.meta["outcome"]["errors_by_kind"] = {"transport": 2, "http": 1}
    p = check_runs([r], True)
    assert codes(p) == ["prompt_tokens_mismatch", "transport_errors"]
    assert {x["code"]: x["severity"] for x in p} == {"prompt_tokens_mismatch": "error", "transport_errors": "warn"}


def test_calib_hw_cli(tmp_path, capsys):
    cal = tmp_path / "c.json"
    cal.write_text(json.dumps({"hardware": "H1"}))
    assert guards.main(["calib-hw", "--calib", str(cal), "--hardware", "H1"]) == 0
    assert guards.main(["calib-hw", "--calib", str(cal), "--hardware", "H2"]) == 1
    cal.write_text(json.dumps({"hardware": None, "hardware_all": ["H1", "H2"]}))
    assert guards.main(["calib-hw", "--calib", str(cal), "--hardware", "H1"]) == 1
    cal.write_text(json.dumps({"lambda_miss": 1.0}))                          # an old calibration without the field
    assert guards.main(["calib-hw", "--calib", str(cal), "--hardware", "H1"]) == 1


@pytest.fixture(scope="module")
def three_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("g")
    outs = []
    for i, (hw, ver) in enumerate((("HW-A", True), ("HW-B", False), ("HW-A", True))):
        raw = make_raw(arrivals={"rate": 4.0, "burst": {"n": 5, "t_s": 1.0, "width_s": 0.5}}, run={"duration_s": 3.0, "seed": i},
                       meta={"engine_label": "mock-fcfs", "hardware": hw, "start_state_verified": ver})
        outs.append(run_gen(raw, MockConfig(**FAST), root / str(i))[0])
    return root, outs


def test_summarize_writes_guards_and_strict_mode_fails(three_runs, tmp_path, capsys):
    _, outs = three_runs
    args = ["burst", "--run-dirs", *[str(o.out_dir) for o in outs], "--out-root", str(tmp_path / "an"), "--set", "windows.window_s=1",
            "--set", "windows.fine_window_s=1", "--set", "burst.tail_window_s=1"]
    assert analysis_main(args) == 0                                           # default: loud, not fatal
    err = capsys.readouterr().err
    assert "GUARD [error] hardware_mixed" in err and "GUARD [error] start_state_unverified" in err
    d = sorted((tmp_path / "an" / "agentload_analysis_burst").iterdir())[-1]
    g = json.loads((d / "guards.json").read_text())
    assert g["summary"]["codes"] == ["hardware_mixed", "start_state_unverified"] and g["summary"]["n_errors"] == 2
    kv = json.loads((d / "kill_verdict.json").read_text())
    assert kv["guards"]["n_errors"] == 2                                      # the verdict itself carries the warning
    meta = json.loads((d / "meta.json").read_text())
    assert len(meta["guard_problems"]) == 2
    assert analysis_main(args + ["--strict-guards"]) == 3
    # the clean subset (the two HW-A, verified runs) passes even in strict mode
    clean = ["burst", "--run-dirs", str(outs[0].out_dir), str(outs[2].out_dir), "--out-root", str(tmp_path / "an2"),
             "--set", "windows.window_s=1", "--set", "windows.fine_window_s=1", "--set", "burst.tail_window_s=1", "--strict-guards"]
    assert analysis_main(clean) == 0


def test_calibration_json_records_hardware_and_sources(three_runs, tmp_path):
    _, outs = three_runs
    base = ["miss", "--warmup-s", "0.5", "--out-root", str(tmp_path / "m")]
    analysis_main([*base, "--run-dirs", str(outs[0].out_dir), str(outs[2].out_dir)])
    d = sorted((tmp_path / "m" / "agentload_analysis_miss").iterdir())[-1]
    cal = json.loads((d / "calibration.json").read_text())
    assert cal["hardware"] == "HW-A" and cal["hardware_all"] == ["HW-A"] and cal["output_ids_sources"] == ["server_ids"]
    assert cal["hostnames"] and cal["n_runs"] == 2
    analysis_main([*base, "--run-dirs", str(outs[0].out_dir), str(outs[1].out_dir)])
    d = sorted((tmp_path / "m" / "agentload_analysis_miss").iterdir())[-1]
    cal = json.loads((d / "calibration.json").read_text())
    assert cal["hardware"] is None and cal["hardware_all"] == ["HW-A", "HW-B"]          # no single value: calib-hw refuses it


def test_windows_table_counts_transport_errors(three_runs, tmp_path):
    _, outs = three_runs
    analysis_main(["windows", "--run-dirs", str(outs[0].out_dir), "--out-root", str(tmp_path / "w"), "--set", "windows.window_s=1"])
    d = sorted((tmp_path / "w" / "agentload_analysis_windows").iterdir())[-1]
    w = pd.read_csv(d / "windows.csv")
    assert "n_errors_transport" in w.columns and (w["n_errors_transport"] == 0).all()


def test_cap_file_must_be_this_jobs_cell_and_hardware(tmp_path, capsys):
    """Review finding 5: a native-pool capped job must not silently take the 300k pool's cap."""
    from analysis.guards import check_cap_file, main as guards_main
    curve = {"n_cap": 24, "primary_label": "sglang-fcfs-r1", "primary_hardware": ["A100 80GB"]}
    assert check_cap_file(curve, "sglang-fcfs-r1", "A100 80GB") == (24, [])
    n, probs = check_cap_file(curve, "sglang-fcfs-r1-native", "A100 80GB")
    assert n == 24 and len(probs) == 1 and "primary_label" in probs[0] and "sglang-fcfs-r1-native" in probs[0]
    n, probs = check_cap_file(curve, "sglang-fcfs-r1", "H200")
    assert any("measured on" in x for x in probs) and check_cap_file(curve, "sglang-fcfs-r1", "H200", allow_hw_mismatch=True)[1] == []
    assert any("no hardware" in x for x in check_cap_file({**curve, "primary_hardware": None}, "sglang-fcfs-r1", "A100 80GB")[1])
    for bad in (None, 0, 2.5, True, "3"):
        assert check_cap_file({**curve, "n_cap": bad}, "sglang-fcfs-r1", "A100 80GB")[0] is None
    f = tmp_path / "mu_curve.json"
    f.write_text(json.dumps(curve))
    assert guards_main(["cap-file", "--file", str(f), "--label", "sglang-fcfs-r1", "--hardware", "A100 80GB"]) == 0
    assert "N_CAP=24" in capsys.readouterr().out
    assert guards_main(["cap-file", "--file", str(f), "--label", "sglang-fcfs-r1-native", "--hardware", "A100 80GB"]) == 1
    assert "CAP_FILE PROBLEM" in capsys.readouterr().out
