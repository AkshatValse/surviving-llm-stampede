"""Stage C: closed-population mu(n) analysis (analysis.closed, `summarize closed`) on the mock server and on synthetic points,
and the hand-off of its n_cap to the CAPPED arm's gate."""
import json

import pandas as pd
import pytest

from agentload.config import config_from_dict, resolve_n_cap
from agentload.mock_server import MockConfig
from analysis.closed import closed_point, mu_curve
from analysis.summarize import main as analysis_main
from conftest import make_raw, run_gen
from helpers_analysis import fake_run, params, req_df

# A mock with a thrashing curve: 3000 tokens of KV ~ 6-8 sessions' worth, one slot, a miss costs ~10x a hit.
THRASH = dict(kv_capacity_tokens=3000, slots=1, fixed_s=0.002, per_uncached_token_s=1e-4, per_completion_token_s=2e-4)
NS = (2, 6, 12, 40)
SMALL = ["--set", "closed.n_grid=[2, 6, 12, 40]", "--set", "closed.n_inf=40", "--set", "closed.warmup_s=2",
         "--set", "windows.fine_window_s=0.5"]


def closed_raw(n, seed=0, label="mock-fcfs"):
    return make_raw(arrivals={"kind": "closed", "rate": None, "closed_n": n},
                    workload={"initial_context_tokens": 200, "new_prompt_tokens": 55, "decode_tokens": 10, "mean_turns": 4,
                              "max_turns": 12, "tool_time_mean_s": 0.1},
                    run={"duration_s": 6.0, "seed": seed}, metrics={"enabled": True, "interval_s": 0.5},
                    meta={"engine_label": label})


@pytest.fixture(scope="module")
def stage_c(tmp_path_factory):
    root = tmp_path_factory.mktemp("stage_c")
    outs = {n: run_gen(closed_raw(n), MockConfig(**THRASH), root / "runs")[0] for n in NS}
    out_root = root / "an"
    rc = analysis_main(["closed", "--run-dirs", *[str(o.out_dir) for o in outs.values()], "--out-root", str(out_root), *SMALL])
    assert rc == 0
    d = sorted((out_root / "agentload_analysis_closed").iterdir())[-1]
    return root, outs, d, json.loads((d / "mu_curve.json").read_text())


def test_mu_curve_has_the_thrashing_shape_and_picks_the_argmax(stage_c):
    _, outs, d, curve = stage_c
    c = curve["cells"]["mock-fcfs"]
    assert c["n"] == [2, 6, 12, 40] and c["n_runs"] == [1, 1, 1, 1] and c["complete_grid"] and c["missing_n"] == []
    mu = dict(zip(c["n"], c["mu_sessions"]))
    assert mu[6] > mu[2] and mu[6] > 1.3 * mu[12] and mu[6] > 1.3 * mu[40]            # rises, peaks at 6, then thrashes
    assert c["argmax_n"] == 6 == curve["n_cap"] and c["mu_max"] == mu[6] == curve["mu_max"]
    assert curve["mu_300"] == mu[40] == c["mu_n_inf"] and curve["mu_300"] < 0.7 * curve["mu_max"]   # n_inf=40 stands for "300"
    assert c["argmax_n_by_estimator"] == {"sessions": 6, "turns_based": 6} and c["argmax_estimators_agree"]
    assert not c["argmax_ambiguous"] and c["argmax_margin_rel"] > 0.3 and c["runner_up_n"] in (2, 12, 40)
    assert curve["primary_label"] == "mock-fcfs" and curve["estimator"] == "sessions" and curve["warmup_s"] == 2.0
    assert curve["notes"] == [] and curve["inputs_unverified_start"] == [str(o.out_dir) for o in outs.values()]
    hit = dict(zip(c["n"], c["hit_frac_turns"]))
    assert hit[2] > hit[12] and hit[12] < 0.2                                          # the cache stops working past the knee


def test_points_match_an_independent_recomputation_from_the_request_log(stage_c):
    _, outs, d, _ = stage_c
    pts = pd.read_csv(d / "mu_points.csv").set_index("n")
    for n, o in outs.items():
        req = pd.read_csv(o.out_dir / "requests.csv")
        ok = req[(req["status"] == "ok") & (req["t_complete"] >= 2.0) & (req["t_complete"] < o.t_end_s)]
        dur = o.t_end_s - 2.0
        row = pts.loc[n]
        assert row["measure_s"] == pytest.approx(dur)
        assert row["mu_sessions"] == pytest.approx((ok["turn"] == ok["n_turns"]).sum() / dur)
        assert row["turns_per_s"] == pytest.approx(len(ok) / dur)
        assert row["hit_frac_turns"] == pytest.approx(((ok["cached_tokens"] / ok["prompt_tokens"]) > 0.5).mean())
        assert row["cached_frac_tokens"] == pytest.approx(ok["cached_tokens"].sum() / ok["prompt_tokens"].sum())
        assert row["queue_source"] == "engine_waiting" and row["queue_mean"] >= 0 and row["client_inflight_mean"] >= 0
        assert row["warmup_s"] == 2.0 and not row["aborted"]
    # the population is the independent variable: more sessions queue more at the engine once the cache stops working
    assert pts.loc[40, "queue_mean"] > pts.loc[2, "queue_mean"]


def test_all_stage_c_outputs_are_written_to_a_new_dir(stage_c):
    _, outs, d, _ = stage_c
    for f in ("mu_curve.json", "mu_curve.csv", "mu_points.csv", "meta.json", "config.yaml", "config_effective.yaml", "guards.json"):
        assert (d / f).exists(), f
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "finished" and len(meta["inputs"]) == 4 and meta["git"]["captured_at"] == "run start"
    mc = pd.read_csv(d / "mu_curve.csv")
    assert list(mc["n"]) == [2, 6, 12, 40] and {"mu_sessions", "mu_turns_based", "hit_frac_turns", "queue_mean"} <= set(mc.columns)


def test_stage_c_n_cap_feeds_the_capped_arm_gate(stage_c, tmp_path):
    """The hand-off: gate.n_cap = '<dir>/mu_curve.json:n_cap' resolves to the argmax and the generator enforces it."""
    _, _, d, curve = stage_c
    ref = f"{d / 'mu_curve.json'}:n_cap"
    assert resolve_n_cap(config_from_dict(make_raw(gate={"n_cap": ref})).gate) == curve["n_cap"] == 6
    raw = make_raw(arrivals={"rate": 6.0, "burst": {"n": 20, "t_s": 1.0, "width_s": 0.1}, "analysis_t_burst_s": 1.0},
                   gate={"n_cap": ref}, meta={"arm": "capped"}, run={"duration_s": 3.0}, metrics={"enabled": False})
    out, _ = run_gen(raw, MockConfig(kv_capacity_tokens=10**7, slots=64, fixed_s=0.05, per_uncached_token_s=0,
                                     per_completion_token_s=0), tmp_path)
    meta = json.loads((out.out_dir / "meta.json").read_text())
    assert meta["gate_n_cap_resolved"] == 6 and meta["gate_n_cap_configured"] == ref
    assert meta["outcome"]["gate"]["max_active_seen"] <= 6 and meta["outcome"]["gate"]["n_waited"] > 0


def test_closed_point_rejects_a_run_that_is_not_closed_population():
    run = fake_run(req_df([dict(sid=1, turn=1, n_turns=1, t_send=1, t_complete=2, prompt_tokens=1)]), 100.0)
    with pytest.raises(ValueError, match="not a closed-population run"):
        closed_point(run, 10.0, params())


# ------------------------------------------------------------------------------------------------ synthetic points
def pts(rows):
    base = dict(seed=0, mu_turns_based=None, turns_per_s=1.0, hit_frac_turns=0.9, hit_frac_followup=0.95,
                cached_frac_tokens=0.9, queue_mean=0.0, aborted=False)
    out = []
    for label, n, mu in rows:
        out.append({**base, "label": label, "n": n, "mu_sessions": mu, "mu_turns_based": mu})
    return pd.DataFrame(out)


CP = dict(n_grid=[16, 24, 32, 48, 96, 300], lpm_n=[48, 300], n_inf=300, mu_estimator="sessions", argmax_margin_warn=0.05)


def full_curve(label="sglang-fcfs-r1", mus=(0.05, 0.08, 0.07, 0.05, 0.04, 0.035)):
    return [(label, n, m) for n, m in zip(CP["n_grid"], mus)]


def test_mu_curve_argmax_mu_max_and_mu_300_by_hand():
    c = mu_curve(pts(full_curve()), CP)
    assert c["n_cap"] == 24 and c["mu_max"] == 0.08 and c["mu_300"] == 0.035 and c["primary_label"] == "sglang-fcfs-r1"
    cell = c["cells"]["sglang-fcfs-r1"]
    assert cell["complete_grid"] and not cell["argmax_ambiguous"] and cell["argmax_margin_rel"] == pytest.approx(0.125)
    assert cell["mu_by_n"] == {"16": 0.05, "24": 0.08, "32": 0.07, "48": 0.05, "96": 0.04, "300": 0.035}
    assert c["notes"] == []


def test_near_tie_is_flagged_ambiguous_and_estimator_disagreement_is_reported():
    df = pts(full_curve(mus=(0.05, 0.080, 0.079, 0.05, 0.04, 0.035)))
    df["mu_turns_based"] = df["mu_sessions"].where(df["n"] != 32, 0.090)          # the other estimator prefers n=32
    c = mu_curve(df, CP)
    cell = c["cells"]["sglang-fcfs-r1"]
    assert cell["argmax_ambiguous"] and cell["argmax_n_by_estimator"] == {"sessions": 24, "turns_based": 32}
    assert not cell["argmax_estimators_agree"] and c["n_cap"] == 24                # the configured estimator decides
    assert any("ambiguous" in n for n in c["notes"]) and any("differs by estimator" in n for n in c["notes"])
    c2 = mu_curve(df, {**CP, "mu_estimator": "turns_based"})
    assert c2["n_cap"] == 32 and c2["mu_max"] == 0.090


def test_incomplete_grid_and_missing_mu_300_are_reported():
    c = mu_curve(pts(full_curve()[:4]), CP)
    cell = c["cells"]["sglang-fcfs-r1"]
    assert not cell["complete_grid"] and cell["missing_n"] == [96, 300] and c["mu_300"] is None and c["n_cap"] == 24
    assert any("grid incomplete" in n for n in c["notes"]) and any("mu(n=300) missing" in n for n in c["notes"])


def test_the_lpm_cell_is_a_separate_cell_and_never_the_primary_one():
    df = pts(full_curve() + [("sglang-lpm-r1", 48, 0.06), ("sglang-lpm-r1", 300, 0.05)])
    c = mu_curve(df, CP)
    assert set(c["cells"]) == {"sglang-fcfs-r1", "sglang-lpm-r1"} and c["primary_label"] == "sglang-fcfs-r1"
    lpm = c["cells"]["sglang-lpm-r1"]
    assert lpm["complete_grid"] and lpm["missing_n"] == [] and lpm["mu_n_inf"] == 0.05 and lpm["argmax_n"] == 48
    only_lpm = mu_curve(pts([("sglang-lpm-r1", 48, 0.06), ("sglang-lpm-r1", 300, 0.05)]), CP)
    assert only_lpm["n_cap"] is None and only_lpm["primary_label"] is None and "no cell label contains" in only_lpm["notes"][0]


def test_replicates_at_one_n_are_averaged_and_ties_go_to_the_smaller_n():
    df = pd.concat([pts(full_curve()), pts([("sglang-fcfs-r1", 24, 0.060)]).assign(seed=1)], ignore_index=True)
    c = mu_curve(df, CP)
    cell = c["cells"]["sglang-fcfs-r1"]
    assert cell["n_runs"][cell["n"].index(24)] == 2 and cell["mu_by_n"]["24"] == pytest.approx(0.07)
    assert cell["mu_by_n"]["32"] == pytest.approx(0.07)                             # exact tie with n=32 ...
    assert c["n_cap"] == 24 and cell["argmax_margin_rel"] == pytest.approx(0.0, abs=1e-9) and cell["argmax_ambiguous"]    # ... smaller n, flagged


def test_unknown_estimator_is_rejected():
    with pytest.raises(ValueError, match="mu_estimator"):
        mu_curve(pts(full_curve()), {**CP, "mu_estimator": "bogus"})
