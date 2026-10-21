import json

import pandas as pd
import pytest
import yaml

from analysis.plan_budget import arithmetic, gate_arithmetic, gate_totals, main, stage_rows
from conftest import REPO

CFG = {
    "job": {"gpus": 1, "time_limit_h": 4.0, "startup_h": 0.25, "gap_s": 180, "teardown_h": 0.05},     # overhead_s absent: 0
    "protocol": {"p": {"fields": {"warmup_s": 900, "measure_s": 1800}, "gap_after_last_run": False},
                 "q": {"fields": {"run_s": 3600}, "gap_after_last_run": False}},
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


def test_arithmetic_strings_spell_out_every_term():
    job = CFG["job"]
    assert arithmetic(job, 2700, 4, 4, False) == "1 x (0.25 + 4 x 0.7500 + 3 x 0.0500 + 0.05) = 3.450 h  =>  3.45 GPU-h"
    # 6 runs in jobs of 4: a full job and a job with the 2 remaining runs
    assert arithmetic(job, 2700, 6, 4, False) == ("1 x (0.25 + 4 x 0.7500 + 3 x 0.0500 + 0.05) = 3.450 h  +  "
                                                  "1 x (0.25 + 2 x 0.7500 + 1 x 0.0500 + 0.05) = 1.850 h  =>  5.30 GPU-h")
    assert arithmetic(job, 8700, 27, 1, False).startswith("27 x (0.25 + 1 x 2.4167 + 0 x 0.0500 + 0.05) = 2.717 h  =>  73.35 GPU-h")
    df = stage_rows(CFG)
    assert df.set_index("stage").loc["b", "arithmetic"].endswith("=>  3.65 GPU-h")
    lines = gate_arithmetic(CFG, df)
    assert lines[0].startswith("g1 = 3.45 = 3.45 GPU-h") and lines[1].startswith("g2 = 3.65 + 2.35 = 6.00 GPU-h")
    assert lines[-1] == "total = 3.45 + 6.00 = 9.45 GPU-h"
    two_gpu = {**job, "gpus": 2}
    assert arithmetic(two_gpu, 3600, 1, 1, False).endswith("=>  2.60 GPU-h (2 GPUs)")    # (0.25 + 1 + 0.05) h x 2


def test_trailing_gap_and_per_run_overhead_are_budgeted_like_the_job_script_does():
    """Review finding 10: slurm/common.sh runs a gap + flush + canary after the LAST run of a job too, and budgets RUN_OVERHEAD_S per
    run; the first budget left both out (~0.09 h per one-run job, ~3% overall)."""
    from analysis.plan_budget import job_wall_h
    job = {**CFG["job"], "overhead_s": 150}
    one = 0.25 + (8700 + 150) / 3600 + 180 / 3600 + 0.05
    assert job_wall_h(job, 8700, 1, True) == pytest.approx(one) and one == pytest.approx(2.8083, abs=1e-4)
    assert job_wall_h(job, 8700, 1, False) == pytest.approx(one - 180 / 3600)
    assert job_wall_h(job, 8700, 1, True) - (0.25 + 8700 / 3600 + 0.05) == pytest.approx(0.0917, abs=1e-4)      # the "about 0.09 h"
    assert job_wall_h(job, 2700, 4, True) == pytest.approx(0.25 + 4 * (2850 / 3600) + 4 * 0.05 + 0.05)
    assert "4 x 0.0500" in arithmetic(job, 2700, 4, 4, True) and "x 0.7917" in arithmetic(job, 2700, 4, 4, True)
    cfg = {**CFG, "job": job, "stages": [{"name": "x", "protocol": "q", "n_runs": 2, "runs_per_job": 2, "gap_after_last_run": True}]}
    assert stage_rows(cfg).iloc[0]["gpu_h"] == pytest.approx(0.25 + 2 * 3750 / 3600 + 2 * 0.05 + 0.05)


def test_shipped_budget_config_is_consistent(tmp_path):
    cfg = yaml.safe_load((REPO / "configs" / "agentload_plan_budget.yaml").read_text())
    assert next(iter(cfg)) == "research_question"
    df = stage_rows(cfg)
    assert df["fits"].all()                                           # every job fits the 4 h limit in the draft scripts
    names = list(df["stage"])
    assert len(names) == len(set(names))
    in_gates = [n for v in cfg["gates"].values() for n in v]
    assert sorted(in_gates) == sorted(names)                          # every stage belongs to exactly ONE gate
    assert main(["--config", str(REPO / "configs" / "agentload_plan_budget.yaml"), "--out-root", str(tmp_path)]) == 0
    d = sorted((tmp_path / "agentload_plan_budget").iterdir())[-1]
    tot = json.loads((d / "gpu_hours_totals.json").read_text())
    assert tot["total"] == pytest.approx(pd.read_csv(d / "gpu_hours_by_stage.csv")["gpu_h"].sum())
    assert tot["total"] == pytest.approx(sum(tot[g] for g in cfg["gates"]))
    alt = pd.read_csv(d / "gpu_hours_by_stage_alt_literal_e2.csv").set_index("stage")
    assert alt["fits"].all() and alt.loc["E2a_kill_sglang_fcfs_paired", "run_s"] == 28000
    assert tot["alt_literal_e2"]["total"] > tot["total"]
    assert (d / "meta.json").exists() and (d / "config.yaml").exists()
    arith = (d / "gpu_hours_arithmetic.txt").read_text()
    assert ("C_closed_sglang_fcfs: 1 x (0.25 + 4 x 0.7917 + 4 x 0.0500 + 0.05) = 3.667 h  +  "
            "1 x (0.25 + 3 x 0.7917 + 3 x 0.0500 + 0.05) = 2.825 h  =>  6.49 GPU-h") in arith
    assert "total = " in arith and "cheap_before_prereg = " in arith
    assert "arithmetic" in pd.read_csv(d / "gpu_hours_by_stage.csv").columns


def test_shipped_budget_has_the_new_stage_order_and_the_hand_checked_numbers():
    cfg = yaml.safe_load((REPO / "configs" / "agentload_plan_budget.yaml").read_text())
    df = stage_rows(cfg).set_index("stage")
    order = list(df.index)
    pos = lambda n: order.index(n)
    # S0 smoke -> C closed mu(n) -> E0a lambda_miss -> E0b (REQUIRED, FCFS) -> E2 paired arms (-> native pool -> grid)
    assert (pos("S0_smoke_sglang") < pos("C_closed_sglang_fcfs") < pos("E0a_miss_sglang") < pos("E0b_cap_sglang_fcfs")
            < pos("E2a_kill_sglang_fcfs_paired") < pos("E2c_native_sglang_fcfs_paired") < pos("E2b_sglang_fcfs_r0"))
    assert "E0b_cap_sglang_lpm" not in order and "E0b_cap_sglang_fcfs_native" in order       # E0b under the registered cell, also on the native pool
    assert cfg["gates"]["gate1_calibration"].count("E0b_cap_sglang_fcfs") == 1                # not droppable: it is in a gate, not in a "can be dropped" list
    assert "can be dropped" not in yaml.safe_dump(cfg["stages"])
    # Stage C: n in {16,20,24,32,48,96,300} FCFS (7 runs) and {48,300} LPM (2 runs), warmup 900 + measured 1800
    assert df.loc["C_closed_sglang_fcfs", "n_runs"] == 7 and df.loc["C_closed_sglang_fcfs", "run_s"] == 2700
    assert df.loc["C_closed_sglang_lpm", "n_runs"] == 2 and df.loc["C_closed_sglang_fcfs_native", "n_runs"] == 7
    assert cfg["protocol"]["c_closed"]["fields"] == {"warmup_s": 900, "measure_s": 1800}
    # by hand (overhead 150 s per run, gap 180 s after EVERY run incl. the last):
    #   FCFS Stage C: job of 4 runs 0.25 + 4 x 0.79167 + 4 x 0.05 + 0.05 = 3.6667 h, job of 3 runs 0.25 + 3 x 0.79167 + 3 x 0.05 + 0.05 = 2.825 h
    assert df.loc["C_closed_sglang_fcfs", "gpu_h"] == pytest.approx(3.6667 + 2.825, abs=1e-3)
    assert df.loc["C_closed_sglang_lpm", "gpu_h"] == pytest.approx(0.25 + 2 * 0.79167 + 2 * 0.05 + 0.05, abs=1e-3)       # 1.9833
    assert df.loc["C_closed_sglang_fcfs", "fits"] and df.loc["C_closed_sglang_fcfs", "job_wall_h_full"] < 4.0
    # paired arms: 3 lambda x 3 seeds x 3 arms = 27 one-run jobs of 0.25 + (8700 + 150)/3600 + 0.05 + 0.05 h
    assert df.loc["E2a_kill_sglang_fcfs_paired", "n_runs"] == 27
    assert df.loc["E2a_kill_sglang_fcfs_paired", "gpu_h"] == pytest.approx(27 * (0.25 + 8850 / 3600 + 0.05 + 0.05))
    # smoke has no gap after its only run; the E0a job ends with the population check (no gap after it): 3 gaps for 4 runs
    assert df.loc["S0_smoke_sglang", "gpu_h"] == pytest.approx(0.25 + 1950 / 3600 + 0.05)
    assert df.loc["E0a_miss_sglang", "gpu_h"] == pytest.approx(0.25 + 4 * 2850 / 3600 + 3 * 0.05 + 0.05)
    t = gate_totals(cfg, stage_rows(cfg))
    assert t["gateC_closed_mu"] == pytest.approx(6.4917 + 1.9833, abs=1e-3)
    assert t["cheap_before_prereg"] == pytest.approx(t["gate0_smoke"] + t["gateC_closed_mu"] + t["gate1_calibration"])
    assert t["total"] == pytest.approx(sum(t[g] for g in cfg["gates"]))
