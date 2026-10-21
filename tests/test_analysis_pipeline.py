"""Generator -> mock server -> analysis CLI, end to end; per-window numbers re-derived independently from the CSV."""
import csv
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from analysis.summarize import main as analysis_main
from conftest import make_raw, run_gen


@pytest.fixture(scope="module")
def open_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("open")
    outs = []
    for seed in (0, 1):
        raw = make_raw(arrivals={"rate": 8.0, "burst": {"n": 15, "t_s": 3.0, "width_s": 0.5}},
                       workload={"tool_time_mean_s": 0.25}, run={"duration_s": 7.0, "seed": seed},
                       meta={"engine_label": "mock-fcfs"})
        raw["arrivals"]["rate"] = None
        raw["arrivals"]["rate_mult"] = 1.6
        raw["arrivals"]["lambda_ref"] = 5.0                          # => 8.0 sessions/s
        outs.append(run_gen(raw, None, root)[0])
    return root, outs


def an(tmp_path, *args):
    out_root = tmp_path / "an"
    rc = analysis_main([*args, "--out-root", str(out_root), "--set", "windows.window_s=2",
                        "--set", "windows.fine_window_s=1", "--set", "burst.tail_window_s=4",
                        "--set", "burst.trap_min_s=4", "--set", "burst.hit_eval_from_s=2"])
    assert rc == 0
    cmd = args[0]
    dirs = sorted((out_root / f"agentload_analysis_{cmd}").iterdir())
    return dirs[-1]


def test_window_hit_rates_match_an_independent_recomputation(open_runs, tmp_path):
    root, outs = open_runs
    d = an(tmp_path, "windows", "--run-dirs", str(outs[0].out_dir))
    w = pd.read_csv(d / "windows.csv")
    rows = [r for r in csv.DictReader(open(outs[0].out_dir / "requests.csv")) if r["status"] == "ok"]
    assert len(w) == 3                                             # 7 s run, 2 s windows: [0,2) [2,4) [4,6)
    for k, wr in w.iterrows():
        sel = [r for r in rows if 2 * k <= float(r["t_complete"]) < 2 * k + 2]
        n = len(sel)
        gt = sum(float(r["cached_tokens"]) / float(r["prompt_tokens"]) > 0.5 for r in sel)
        cached = sum(float(r["cached_tokens"]) for r in sel)
        prompt = sum(float(r["prompt_tokens"]) for r in sel)
        assert wr["n_turns_ok"] == n and n > 5
        assert wr["frac_turns_cached_gt50"] == pytest.approx(gt / n)
        assert wr["token_hit_rate"] == pytest.approx(cached / prompt)
        assert wr["hit_rate"] == pytest.approx(gt / n)
        assert wr["turns_per_s"] == pytest.approx(n / 2)
        lat = [float(r["t_complete"]) - float(r["t_send"]) for r in sel]
        assert wr["lat_p50_s"] == pytest.approx(np.percentile(lat, 50))
        assert wr["lat_p99_s"] == pytest.approx(np.percentile(lat, 99))
    assert set(w["queue_source"]) == {"engine_waiting"} and w["cached_available"].all()
    assert (w["cache_usage_mean"] >= 0).all() and w["engine_counter_hit_rate"].notna().all()
    # whole-run hit rate from windows vs mock's own counters is of course only approximate (partial windows dropped)
    assert 0.3 < w["token_hit_rate"].mean() < 1.0
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "finished" and meta["inputs"][0]["run_dir"] == str(outs[0].out_dir)
    assert meta["git"]["captured_at"] == "run start" and meta["hardware"] == "Apple M3 Max CPU (simulation)"
    assert (d / "config.yaml").exists() and yaml.safe_load((d / "config_effective.yaml").read_text())["windows"]["window_s"] == 2
    assert (d / "queue_trace.csv").exists()


def test_analysis_never_overwrites_a_previous_result_dir(open_runs, tmp_path):
    _, outs = open_runs
    args = ["windows", "--run-dirs", str(outs[0].out_dir), "--out-root", str(tmp_path / "x"), "--set", "windows.window_s=2"]
    analysis_main(args)
    analysis_main(args)
    dirs = list((tmp_path / "x" / "agentload_analysis_windows").iterdir())
    assert len(dirs) == 2


def test_burst_cli_outputs(open_runs, tmp_path):
    _, outs = open_runs
    d = an(tmp_path, "burst", "--run-dirs", *[str(o.out_dir) for o in outs])
    br = pd.read_csv(d / "burst_runs.csv")
    assert len(br) == 2 and set(br["label"]) == {"mock-fcfs"} and set(br["rate_mult"]) == {1.6}
    assert (br["t_burst"] == 3.0).all() and br["verdict"].notna().all()
    assert {"trapped", "recovered", "good_before", "hysteresis_run", "hit_eval", "tail_queue_mean"} <= set(br.columns)
    assert not br["trapped"].any()                                 # an uncongested mock must never look trapped
    assert br["good_before"].all()                                 # hit rate before the burst is high, queue ~0
    cells = pd.read_csv(d / "burst_cells.csv")
    assert cells.iloc[0]["n_runs"] == 2 and not cells.iloc[0]["meets_strict"]      # < min_runs_per_cell
    kv = json.loads((d / "kill_verdict.json").read_text())
    assert kv["interval"] == [1.2, 2.0] and "mock-fcfs" in kv["cells"]
    assert (d / "windows.csv").exists()


def test_stable_cli(open_runs, tmp_path):
    _, outs = open_runs
    d = an(tmp_path, "stable", "--run-dirs", *[str(o.out_dir) for o in outs])
    st = pd.read_csv(d / "stable_runs.csv")
    assert st["stable"].all() and set(st["queue_source"]) == {"engine_waiting"}
    by = pd.read_csv(d / "stable_by_rate.csv")
    assert by.iloc[0]["n_stable"] == 2 and by.iloc[0]["n_runs"] == 2
    br = json.loads((d / "lambda_cap_bracket.json").read_text())
    assert br["largest_all_stable_mult"] == 1.6 and br["first_unstable_mult_above"] is None and br["monotone"]


def test_miss_calibration_from_a_closed_run(tmp_path):
    raw = make_raw(arrivals={"kind": "closed", "rate": None, "closed_n": 4},
                   workload={"mean_turns": 2, "max_turns": 4, "tool_time_mean_s": 0.05}, run={"duration_s": 6.0})
    out, _ = run_gen(raw, None, tmp_path / "closed")
    d = an(tmp_path, "miss", "--run-dirs", str(out.out_dir), "--warmup-s", "2")
    cal = json.loads((d / "calibration.json").read_text())
    rows = [r for r in csv.DictReader(open(out.out_dir / "requests.csv")) if r["status"] == "ok"
            and 2.0 <= float(r["t_complete"]) < out.t_end_s]
    done = sum(r["turn"] == r["n_turns"] for r in rows)
    assert cal["lambda_miss"] == pytest.approx(done / (out.t_end_s - 2.0)) and cal["n_runs"] == 1
    assert cal["lambda_miss_turns_based"] > 0 and cal["lambda_miss_se"] is None
    assert cal["lambda_miss"] > 1.0                                # a toy server: several sessions per second
    # the calibration file is directly usable as arrivals.lambda_ref
    from agentload.config import resolve_lambda_ref
    assert resolve_lambda_ref(f"{d / 'calibration.json'}:lambda_miss_turns_based") == cal["lambda_miss_turns_based"]
