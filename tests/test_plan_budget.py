import json

import pandas as pd
import pytest
import yaml

from analysis.plan_budget import gate_totals, main, stage_rows
from conftest import REPO

CFG = {
    "job": {"gpus": 1, "time_limit_h": 4.0, "startup_h": 0.25, "gap_s": 180, "teardown_h": 0.05},
    "protocol": {"p": {"fields": {"warmup_s": 900, "measure_s": 1800}}, "q": {"fields": {"run_s": 3600}}},
    "stages": [{"name": "a", "protocol": "p", "n_runs": 4, "runs_per_job": 4},
               {"name": "b", "protocol": "q", "n_runs": 3, "runs_per_job": 2},
               {"name": "c", "protocol": "q", "n_runs": 2, "runs_per_job": 2}],
    "gates": {"g1": ["a"], "g2": ["b", "c"]},
}


def test_arithmetic_by_hand():
    df = stage_rows(CFG).set_index("stage")
    # a: one job: 0.25 + 4*(2700/3600) + 3*(180/3600) + 0.05 = 0.25 + 3.0 + 0.15 + 0.05 = 3.45
    assert df.loc["a", "gpu_h"] == pytest.approx(3.45) and df.loc["a", "jobs"] == 1 and df.loc["a", "fits"]
    # b: 3 runs in jobs of 2 -> a full job (0.25 + 2*1 + 0.05 + 0.05 = 2.35) plus a job with 1 run (0.25 + 1 + 0 + 0.05 = 1.3)
    assert df.loc["b", "jobs"] == 2 and df.loc["b", "gpu_h"] == pytest.approx(2.35 + 1.3)
    # c: two 1-hour runs in one job: 2.35 h, fits in 4 h
    assert df.loc["c", "gpu_h"] == pytest.approx(2.35)
    t = gate_totals(CFG, stage_rows(CFG))
    assert t["g1"] == pytest.approx(3.45) and t["g2"] == pytest.approx(2.35 + 1.3 + 2.35)
    assert t["total"] == pytest.approx(3.45 + 3.65 + 2.35)


def test_alternative_protocol_swap():
    from analysis.plan_budget import alternative_rows
    alt = alternative_rows(CFG, {"protocol_map": {"p": "q"}, "time_limit_h": 9.0})
    a = alt.set_index("stage").loc["a"]
    assert a["run_s"] == 3600 and a["fits"]                           # 4 x 1 h runs no longer fit 4 h but fit 9 h
    assert a["gpu_h"] == pytest.approx(0.25 + 4 * 1.0 + 3 * 0.05 + 0.05)


def test_job_that_exceeds_the_limit_is_flagged():
    cfg = {**CFG, "stages": [{"name": "x", "protocol": "q", "n_runs": 4, "runs_per_job": 4}]}
    assert not stage_rows(cfg).iloc[0]["fits"]                       # 0.25 + 4 + 0.15 + 0.05 = 4.45 h > 4 h


def test_shipped_budget_config_is_consistent(tmp_path):
    cfg = yaml.safe_load((REPO / "configs" / "agentload_plan_budget.yaml").read_text())
    assert next(iter(cfg)) == "research_question"
    df = stage_rows(cfg)
    assert df["fits"].all()                                           # every job fits the 4 h limit in the draft scripts
    names = set(df["stage"])
    assert all(set(v) <= names for v in cfg["gates"].values())
    assert set().union(*map(set, cfg["gates"].values())) == names     # every stage belongs to exactly one gate
    assert main(["--config", str(REPO / "configs" / "agentload_plan_budget.yaml"), "--out-root", str(tmp_path)]) == 0
    d = sorted((tmp_path / "agentload_plan_budget").iterdir())[-1]
    tot = json.loads((d / "gpu_hours_totals.json").read_text())
    assert tot["total"] == pytest.approx(pd.read_csv(d / "gpu_hours_by_stage.csv")["gpu_h"].sum())
    alt = pd.read_csv(d / "gpu_hours_by_stage_alt_literal_e2.csv").set_index("stage")
    assert alt["fits"].all() and alt.loc["E2a_kill_sglang_fcfs", "run_s"] == 28000
    assert tot["alt_literal_e2"]["total"] > tot["total"]
    assert tot["total"] == pytest.approx(tot["gate0_smoke"] + tot["gate1_calibration"] + tot["gate2_kill_test"]
                                         + tot["full_grid"])
    assert (d / "meta.json").exists() and (d / "config.yaml").exists()
