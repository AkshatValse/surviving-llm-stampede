"""experiments/agentload_trap_sim_traces.py: criterion (a) on the simulator's own traps. Synthetic window tables with known answers,
plus (skipped if the main checkout's recorded simulator outputs are absent) the recorded numbers."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import REPO

spec = importlib.util.spec_from_file_location("trap_sim_traces", REPO / "experiments" / "agentload_trap_sim_traces.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

A = yaml.safe_load((REPO / "configs" / "agentload_trap_sim_traces.yaml").read_text())["analysis"]
LAM_MISS, ET = 0.05, ts.effective_mean_turns(15, 60)
REFS = {"sessions_per_s": LAM_MISS, "turns_per_s": LAM_MISS * ET, "prefill_tok_per_s": 7000.0}
TB = 5000.0


def windows(run_id, variant, hit, sessions, tok, n=14, policy="fcfs_lru", seed=1):
    """n whole 1000 s windows with constant rates after t = 0; turns/s consistent with `sessions` (x E[T])."""
    return pd.DataFrame({"policy": policy, "variant": variant, "seed": seed, "run_id": run_id, "t_start": 1000.0 * np.arange(n),
                         "hit_rate": hit, "sessions_per_s": sessions, "turns_per_s": sessions * ET, "prefill_tok_per_s": tok})


def test_young_sessions_are_rejected_in_session_units_but_accepted_in_token_units():
    # a trapped run at lambda = 2 x lambda_miss: sessions complete 1.34 x lambda_miss, prefill tokens at 1.05 x the all-miss rate
    win = pd.concat([windows(0, "lam=2.0|burst=100", 0.0, 1.34 * LAM_MISS, 1.05 * 7000.0),
                     windows(1, "lam=2.0|burst=10", 0.9, 2.0 * LAM_MISS, 900.0)])       # a recovered run: serves lambda, few uncached tokens
    runs = pd.DataFrame({"run_id": [0, 1], "tail_hit_rate": [0.0, 0.9], "sim_end_s": [14000.0, 14000.0]})
    df = ts.trapped_run_rows(win, runs, REFS, LAM_MISS, TB, [[5000, 8000]], A, 0.15, 0.5)
    t = df[df["trapped"]]
    assert list(t["run_id"]) == [0] and not df[df["run_id"] == 1]["trapped"].any()
    r = t.iloc[0]
    assert r["ratio_sessions"] == pytest.approx(1.34) and r["ratio_turns"] == pytest.approx(1.34) and r["ratio_tokens"] == pytest.approx(1.05)
    assert not r["crit_a_sessions"] and not r["crit_a_turns"] and r["crit_a_tokens"]
    # (b) by conservation: slope = lambda - completion rate = 0.66 x lambda_miss > 0.5 x (lambda - lambda_miss) = 0.5 x lambda_miss
    assert r["slope_conservation"] == pytest.approx(0.66 * LAM_MISS) and r["crit_b_conservation"]
    s = ts.summarize_traps(df)
    assert len(s) == 1 and s.iloc[0]["n_trapped_runs"] == 1 and s.iloc[0]["a_fires_tokens"] == 1.0 and s.iloc[0]["a_fires_sessions"] == 0.0


def test_a_run_that_recovers_later_or_has_a_hit_in_the_window_is_not_counted_as_trapped():
    win = pd.concat([windows(0, "lam=1.5|burst=100", 0.0, 1.3 * LAM_MISS, 7100.0),
                     windows(1, "lam=1.5|burst=100", 0.0, 1.3 * LAM_MISS, 7100.0, seed=2)])
    win.loc[(win["run_id"] == 1) & (win["t_start"] == 10000.0), "hit_rate"] = 0.5        # one good window inside the span
    runs = pd.DataFrame({"run_id": [0, 1], "tail_hit_rate": [0.95, 0.0], "sim_end_s": [14000.0, 14000.0]})    # run 0 recovers by the end
    df = ts.trapped_run_rows(win, runs, REFS, LAM_MISS, TB, [[4000, 7000]], A, 0.15, 0.5)
    assert not df["trapped"].any()
    # incomplete spans produce no row
    short = ts.trapped_run_rows(windows(0, "lam=1.5|burst=1", 0.0, 0.05, 7000.0, n=8), runs.iloc[:1], REFS, LAM_MISS, TB, [[5000, 8000]], A, 0.15, 0.5)
    assert len(short) == 0


def test_noburst_escape_time_and_final_state():
    hit = np.ones(20)
    hit[11:] = 0.0                                                       # collapses at t = 11000 s and stays down
    ok = windows(0, "lam=2.0|burst=0", 0.9, 0.1, 100.0, n=20)
    esc = windows(1, "lam=2.0|burst=0", hit, 0.1, 100.0, n=20, seed=2)
    runs = pd.DataFrame({"run_id": [0, 1], "tail_hit_rate": [0.9, 0.0], "sim_end_s": [20000.0, 20000.0]})
    df = ts.noburst_escapes(pd.concat([ok, esc]), runs, A)
    assert list(df["escaped"]) == [False, True] and list(df["ends_trapped"]) == [False, True]
    assert df.iloc[1]["escape_start_s"] == 11000.0 and np.isnan(df.iloc[0]["escape_start_s"])
    burst = windows(2, "lam=2.0|burst=50", 0.0, 0.1, 100.0, n=20)       # runs with a burst are not no-burst runs
    assert len(ts.noburst_escapes(burst, runs.assign(run_id=[2, 3]), A)) == 0


def test_transient_bias_by_hand():
    rows = []
    for n, early, late in ((20, 0.18, 0.20), (300, 0.08, 0.05)):
        for t in range(0, 36):
            rows.append({"policy": "fcfs_lru", "variant": f"k=1.0|n={n}", "t_start": 1000.0 * t,
                         "sessions_per_s": early if 1 <= t < 3 else late, "turns_per_s": (early if 1 <= t < 3 else late) * ET,
                         "prefill_tok_per_s": 100.0})
    b = ts.transient_bias(pd.DataFrame(rows), A).set_index("n")
    assert b.loc[20, "rel_bias_sessions"] == pytest.approx(0.18 / 0.20 - 1) and b.loc[300, "rel_bias_sessions"] == pytest.approx(0.08 / 0.05 - 1)
    assert b.loc[300, "rel_bias_turns"] == pytest.approx(0.6) and b.loc[300, "rel_bias_prefill_tok"] == pytest.approx(0.0)


def test_parse_variant_and_references():
    assert ts.parse_variant("lam=2.0|burst=100") == (2.0, 100) and ts.parse_variant("lam=1.5|burst=0") == (1.5, 0)
    w = pd.DataFrame({"exp": "e0_miss", "run_id": [0] * 4 + [1] * 4, "t_start": [0, 5000, 6000, 7000] * 2,
                      "sessions_per_s": [9.0, 0.04, 0.06, 0.05, 9.0, 1, 1, 1], "turns_per_s": 1.0,
                      "prefill_tok_per_s": [9.0, 100.0, 300.0, 200.0, 9.0, 1, 1, 1]})
    runs = pd.DataFrame({"exp": "e0_miss", "run_id": [0, 1], "population": [60, 30]})
    ref = ts.e0_references(w, runs, 60, 5000.0)
    assert ref["sessions_per_s"] == pytest.approx(0.05) and ref["prefill_tok_per_s"] == pytest.approx(200.0) and ref["n_windows"] == 3
    with pytest.raises(ValueError):
        ts.e0_references(w, runs, 999, 5000.0)


MAIN = Path(__file__).resolve().parent.parent / "results"      # recorded simulator outputs (gitignored; regenerate to run)
RECORDED = (MAIN / "prefix_meta_r4_burst_info/20261021-051020/windows.csv").exists() and (MAIN / "prefix_meta_e0/20261021-005706/windows.csv").exists()


@pytest.mark.skipif(not RECORDED, reason="the main checkout's recorded simulator outputs are not available")
def test_recorded_simulator_traps(tmp_path):
    """What the recorded simulator output says (deterministic analysis of files written by the simulator, not a new run)."""
    rc = ts.main(["--out-root", str(tmp_path)])
    assert rc == 0
    d = sorted((tmp_path / "agentload_trap_sim_traces").iterdir())[-1]
    s = json.loads((d / "summary.json").read_text())
    assert s["lambda_miss"] == pytest.approx(0.0474189, rel=1e-5) and s["t_burst_s"] == 5000.0
    by = {(r["span"], r["lam_mult"]): r for r in s["by_lambda"]}
    for span in ("[5000,8000)", "[4000,7000)", "[10000,13000)"):
        for lam in (1.5, 2.0, 2.5):
            r = by[(span, lam)]
            assert r["a_fires_tokens"] == 1.0 and 1.0 <= r["ratio_tokens_min"] and r["ratio_tokens_max"] <= 1.10, (span, lam)
    for span in ("[5000,8000)", "[4000,7000)"):                          # sessions/s: outside the +-15% band at 2 x and 2.5 x
        assert by[(span, 2.0)]["a_fires_sessions"] == 0.0 and by[(span, 2.5)]["a_fires_sessions"] == 0.0
        assert by[(span, 1.5)]["a_fires_sessions"] < 0.6
    esc = {e["lam_mult"]: e for e in s["noburst_escapes"]}
    assert all(e["n_escaped_before_e2_horizon"] == 0 for e in esc.values())     # no no-burst escape inside the 8700 s E2 horizon
    assert esc[2.0]["n_ends_trapped"] == 1 and esc[2.5]["n_ends_trapped"] == 2
    for key in ("per_run.csv", "summary_by_lambda.csv", "noburst_escapes.csv", "transient_bias.csv", "config.yaml", "meta.json"):
        assert (d / key).exists(), key
    meta = json.loads((d / "meta.json").read_text())
    assert len(meta["input_sha256"]["burst_windows"]) == 64 and meta["deterministic"] is True and meta["git"]["captured_at"] == "run start"
    bias = pd.read_csv(d / "transient_bias.csv").set_index("n")
    assert bias.loc[300, "rel_bias_sessions"] > 0.5 and bias.loc[100, "rel_bias_sessions"] > 0.1 and bias.loc[28, "rel_bias_sessions"] < -0.1
