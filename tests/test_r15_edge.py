"""analysis/r15_edge.py and configs/r15_edge_replicate.yaml: the exploratory REPLICATE-EDGE cell (same-plan replicates of the
2.5 x from-empty edge, A100 300k SGLang FCFS).

Fixtures are the two committed original runs (seed 0, job 17084754: UNSTABLE at 1600 s; seed 4, job 17168507: STABLE), the
committed runs of data-B's D3 table (the per-run rule must reproduce its tau exactly), stand-in replicates made from the
originals' small files, and synthetic series and verdict rows for every verdict.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import REPO

from agentload.client import LoadGenerator, write_plan_csv
from agentload.config import load_config
from analysis import r15_edge as E
from analysis.params import load_params

RULE = E.load_rule(REPO / "configs/r15_edge_replicate.yaml")
PR = RULE["per_run_rule"]
ORIG = {s: REPO / RULE["originals"][str(s)]["run_dir"] for s in E.PLANS}
NOVA = REPO / "results/nova"


# ============================================================================================ the frozen rule file
def test_rule_file_is_frozen_exploratory_and_complete():
    assert RULE["status"] == "FROZEN" and RULE["exploratory"] is True
    assert (PR["bin_s"], PR["window_bins"], PR["min_turns_per_window"], PR["warm_s"]) == (100.0, 3, 5, 600.0)
    assert (PR["collapse_hit_at_most"], PR["good_hit_at_least"], PR["recover_hit_at_least"]) == (0.2, 0.6, 0.5)
    assert [j["seeds"] for j in RULE["jobs"]] == [[0, 4, 0], [4, 0, 4]]
    seeds = [s for j in RULE["jobs"] for s in j["seeds"]]
    assert seeds.count(0) == 3 and seeds.count(4) == 3
    v = RULE["verdict"]
    assert (v["min_replicates_per_plan"], v["replicates_for_reproducible"]) == (2, 3)
    assert "exploratory" in RULE["how_this_cell_was_chosen"].lower() or "EXPLORATORY" in RULE["how_this_cell_was_chosen"]
    assert "cannot be decisive" in RULE["how_this_cell_was_chosen"]
    c = RULE["cell"]
    cal = json.loads((REPO / c["calib_file"]).read_text())
    assert cal["lambda_miss_turns_based"] == c["lambda_ref"] and cal["hardware"] == c["hardware"]
    assert c["resolved_rate_sessions_per_s"] == c["rate_mult"] * c["lambda_ref"]
    for s in E.PLANS:
        o = RULE["originals"][str(s)]
        meta = json.loads((ORIG[s] / "meta.json").read_text())
        assert meta["slurm_env"]["SLURM_JOB_ID"] == o["job"] and meta["hostname"] == o["node"]
        assert meta["git"]["commit"] == o["commit"] and meta["engine_label"] == o["engine_label"]
        assert meta["resolved_rate_sessions_per_s"] == c["resolved_rate_sessions_per_s"]
        assert meta["lambda_ref_resolved"] == c["lambda_ref"] and meta["hardware"] == c["hardware"]
        cfg = yaml.safe_load((ORIG[s] / "config_effective.yaml").read_text())
        assert cfg["workload"]["content_salt"] == o["content_salt"] == o["run_position"]
        assert cfg["run"]["seed"] == s and cfg["arrivals"]["rate_mult"] == c["rate_mult"]
        assert cfg["run"]["duration_s"] == c["duration_s"]
        assert (REPO / o["job_log_dir"] / "banner.txt").exists()


def test_a_rule_file_that_is_not_frozen_is_refused(tmp_path):
    raw = yaml.safe_load((REPO / "configs/r15_edge_replicate.yaml").read_text())
    raw["status"] = "DRAFT"
    p = tmp_path / "rule.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="FROZEN"):
        E.load_rule(p)


# ============================================================================================ the two originals
@pytest.fixture(scope="module")
def params():
    return load_params(REPO / "configs/agentload_analysis.yaml", [])


@pytest.fixture(scope="module")
def originals(params):
    return {s: E.classify_run(ORIG[s], RULE, params, role="original") for s in E.PLANS}


def test_seed0_original_is_unstable_at_1600_s(originals):
    r = originals[0]
    assert r["label"] == E.UNSTABLE and r["tau_s"] == 1600.0
    assert r["max_hit_before_tau"] >= 0.6 and r["last_window_hit"] <= 0.2
    assert r["stable_registered"] is False and r["final_queue"] == 127.0          # committed stable_runs.csv: 127.0, rise 146.2
    assert r["node"] == "nova22-gpu-1" and r["gpu_bus_id"] == RULE["originals"]["0"]["gpu_bus_id"]
    assert r["run_position"] == 1 and r["counted"] is False and r["role"] == "original"


def test_seed4_original_is_stable(originals):
    r = originals[4]
    assert r["label"] == E.STABLE and r["tau_s"] is None and r["stable_kind"] == "good"
    assert r["min_hit_after_warm"] > 0.9
    assert r["stable_registered"] is True and r["final_queue"] == 0.0
    assert r["node"] == "nova22-gpu-3" and r["gpu_bus_id"] == RULE["originals"]["4"]["gpu_bus_id"]
    assert r["run_position"] == 2


def test_the_originals_give_the_known_outcomes_and_an_incomplete_verdict(originals):
    v = E.verdict([], originals, RULE)
    assert v["originals_match_known_outcomes"] is True
    assert v["verdict"] == E.INCOMPLETE and v["disagreement_observed"] is False
    assert v["exploratory"] is True


# ============================================================================================ same rule as data-B D3
# (run dir under results/nova, tau of data-B's D3 table, scratch d3_runs.csv of 2026-11-04; None = not collapsed)
D3_CASES = [
    ("e0b_1708475x_pulled_20261024-150639/results/agentload_e0_cap/20261023-151551-1", 1600.0),   # A100 300k 2.5 x s0
    ("e0b_1708475x_pulled_20261024-150639/results/agentload_e0_cap/20261023-151551", 600.0),      # 3.0 x s0
    ("e0b_1708475x_pulled_20261024-150639/results/agentload_e0_cap/20261023-151556", None),       # 2.0 x s0
    ("b1_e0f_1716850x_pulled_20261031-040517/results/agentload_e0_cap/20261031-012149", None),    # 2.5 x s3
    ("b1_e0f_1716850x_pulled_20261031-040517/results/agentload_e0_cap/20261031-021452", None),    # 2.5 x s4
    ("b1_e0f_1716850x_pulled_20261031-040517/results/agentload_e0_cap/20261031-030755", None),    # 2.5 x s5
    ("e0b_native_1710093x_pulled_20261025-173038/results/agentload_e0_cap/20261025-163315", 1300.0),
    ("e0b_vllm_1716296x_pulled_20261030-172810/results/agentload_e0_cap/20261030-153127", 1800.0),
    ("llama31_e0b_registration_pulled_20261031-075313/results/agentload_e0_cap/20261031-065141-1", 2000.0),
    ("h200_wave1_pulled_20261031-023416/results/agentload_e0_cap/20261030-235534", 1600.0),
    ("pool_sweep_1716886x_pulled_20261031-112342/results/agentload_e0_cap/20261031-093158", 2700.0),
    ("pool_sweep_1716886x_pulled_20261031-112342/results/agentload_e0_cap/20261031-094502", 800.0),
    ("h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/results/agentload_e0_cap/20261031-082559", 700.0),
    ("e2_170933xx_pulled_20261025-144558/results/agentload_e2_burst/20261024-160218", None),      # 8700 s NOBURST 1.65 x s0
]


@pytest.mark.parametrize("rel,tau", D3_CASES)
def test_the_rule_reproduces_data_B_D3(rel, tau):
    bins, _ = E.hit_bins(NOVA / rel, PR["bin_s"])
    c = E.classify_bins(bins, PR)
    assert c["tau_s"] == tau and c["label"] == (E.UNSTABLE if tau is not None else E.STABLE)


# ============================================================================================ synthetic series
def _series(points, t_last=2800.0):
    """Window starts 0, 100, ..., t_last with hit fractions from piecewise-constant points [(t_from, hit), ...]."""
    ws = np.arange(0.0, t_last + 1, 100.0)
    hf = np.full(len(ws), np.nan)
    for t, h in points:
        hf[ws >= t] = h
    return ws, hf


@pytest.mark.parametrize("points,label,tau,kind", [
    ([(0, 0.95), (1600, 0.05)], E.UNSTABLE, 1600.0, None),                       # good, then a collapse that lasts
    ([(0, 0.95), (300, 0.1)], E.UNSTABLE, 600.0, None),                          # early collapse: first window >= 600 s
    ([(0, 0.95), (1200, 0.1), (1800, 0.55)], E.STABLE, None, "dipped_and_recovered"),   # a later window reaches 0.5
    ([(0, 0.95), (1200, 0.1), (1800, 0.49)], E.UNSTABLE, 1200.0, None),          # 0.49 is not a recovery
    ([(0, 0.95), (1200, 0.1), (1800, 0.5)], E.STABLE, None, "dipped_and_recovered"),    # exactly 0.5 is (>=)
    ([(0, 0.95), (1200, 0.2)], E.UNSTABLE, 1200.0, None),                        # exactly 0.2 collapses (<=)
    ([(0, 0.95), (1200, 0.21)], E.STABLE, None, "good"),                         # 0.21 does not
    ([(0, 0.6), (1200, 0.1)], E.UNSTABLE, 1200.0, None),                         # exactly 0.6 was a good state (>=)
    ([(0, 0.59), (1200, 0.1)], E.STABLE, None, "never_good"),                    # never good: STABLE by the rule, flagged
    ([(0, 0.1), (900, 0.7), (1500, 0.1)], E.UNSTABLE, 1500.0, None),             # good only after an early low phase
    ([(0, 0.3), (700, 0.1)], E.STABLE, None, "never_good"),
    ([(0, 0.95), (2800, 0.0)], E.UNSTABLE, 2800.0, None),                        # collapse in the last window
    ([(0, 0.95)], E.STABLE, None, "good"),
])
def test_synthetic_series(points, label, tau, kind):
    ws, hf = _series(points)
    c = E.classify_series(ws, hf, PR)
    assert (c["label"], c["tau_s"], c["stable_kind"]) == (label, tau, kind)


def test_invalid_windows_are_skipped_and_the_rolling_window_is_three_bins():
    # 100 s bins: 10 good turns per bin until 1500 s, then all misses; one empty stretch (< 5 turns) in the middle
    t0 = np.arange(0.0, 3100.0, 100.0)
    n = np.full(len(t0), 10)
    hits = np.where(t0 < 1500, 10.0, 0.0)
    n[(t0 >= 800) & (t0 < 1100)] = 0
    hits[(t0 >= 800) & (t0 < 1100)] = 0
    bins = pd.DataFrame({"t0": t0, "n": n, "hits": hits})
    ws, hf, nn = E.rolling_windows(bins, PR)
    assert ws[2] == 0.0 and np.isnan(hf[0]) and np.isnan(hf[1])                  # the first two windows are incomplete
    assert np.isnan(hf[(ws >= 800) & (ws <= 800)]).all()                         # window [800, 1100) has 0 turns
    c = E.classify_bins(bins, PR)
    # windows [1300, 1600): 1 miss bin of 3 -> 0.667; [1400, 1700): 0.333; [1500, 1800): 0.0 -> tau 1500
    assert c["label"] == E.UNSTABLE and c["tau_s"] == 1500.0


# ============================================================================================ manipulation check
def _new_job_plan(seed: int, salt: int, out: Path) -> Path:
    """plan.csv the r15/tonight client writes for the NEW job's run (slurm/common.sh run_gen + mode_cap words)."""
    sets = ['server.base_url="http://127.0.0.1:20000"', 'server.model="Qwen/Qwen2.5-7B-Instruct"', "server.request_token_ids=true",
            "workload.output_feedback=server", f"workload.content_salt={salt}", 'meta.engine_label="sglang-fcfs-r1-edgerep"',
            'meta.hardware="NVIDIA A100 80GB PCIe, 81920 MiB"', "meta.start_state_verified=true", f"run.seed={seed}",
            "arrivals.rate_mult=2.5", 'arrivals.lambda_ref="prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based"',
            "run.duration_s=3000"]
    cfg, raw = load_config(REPO / RULE["cell"]["agentload_config"], sets)
    gen = LoadGenerator(cfg, raw, out, REPO)
    assert gen.rate == RULE["cell"]["resolved_rate_sessions_per_s"]
    out.mkdir(parents=True, exist_ok=True)
    write_plan_csv(out / "plan.csv", gen.build_plan())
    return out


@pytest.mark.parametrize("seed,salt", [(0, 1), (0, 3), (4, 1), (4, 2)])
def test_the_new_jobs_plans_pass_the_manipulation_check(tmp_path, seed, salt):
    d = _new_job_plan(seed, salt, tmp_path / "run")
    pc = E.plan_check(d, ORIG[seed])
    assert pc["equal"] is True and pc["ids_and_turns_identical"] and pc["max_abs_arrival_diff_s"] == 0.0
    assert pc["max_abs_tool_total_diff_s"] < 1e-12                               # libm last bits only (Linux vs Windows)
    assert pc["rows"] == {0: 585, 4: 572}[seed]


def test_a_different_plan_fails_the_manipulation_check(tmp_path):
    d = _new_job_plan(4, 2, tmp_path / "run")
    assert E.plan_check(d, ORIG[0])["equal"] is False                             # seed 4's plan is not seed 0's
    p = pd.read_csv(d / "plan.csv", float_precision="round_trip")
    p.loc[10, "tool_time_total_s"] += 1e-6
    p.to_csv(d / "plan.csv", index=False)
    pc = E.plan_check(d, ORIG[4])
    assert pc["equal"] is False and pc["ids_and_turns_identical"] is True


# ============================================================================================ stand-in replicates
SMALL = ("meta.json", "config_effective.yaml", "plan.csv", "requests.csv", "sessions.csv")


def make_standin(root: Path, seed: int, ts: str, *, job: str, salt: int, meta_over=None, cfg_over=None,
                 requests_fn=None, node=None) -> Path:
    """A replicate-shaped run dir from the original's small files, as the new job would label it."""
    d = root / "agentload_e0_cap" / ts
    d.mkdir(parents=True)
    for f in SMALL:
        shutil.copyfile(ORIG[seed] / f, d / f)
    meta = json.loads((d / "meta.json").read_text())
    meta["engine_label"] = RULE["cell"]["engine_label"]
    meta["slurm_env"]["SLURM_JOB_ID"] = job
    meta["start_state_verified"] = True
    if node:
        meta["hostname"] = node
    for k, v in (meta_over or {}).items():
        meta[k] = v
    (d / "meta.json").write_text(json.dumps(meta))
    cfg = yaml.safe_load((d / "config_effective.yaml").read_text())
    cfg["meta"]["engine_label"] = RULE["cell"]["engine_label"]
    cfg["workload"]["content_salt"] = salt
    cfg["server"]["base_url"] = "http://127.0.0.1:21234"
    cfg["arrivals"]["lambda_ref"] = "prereg/inputs/2026-10-23/calibration.json:lambda_miss_turns_based"
    for k, v in (cfg_over or {}).items():
        sec, key = k.split(".")
        cfg[sec][key] = v
    (d / "config_effective.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    if requests_fn is not None:
        r = pd.read_csv(d / "requests.csv")
        requests_fn(r).to_csv(d / "requests.csv", index=False)
    return d


def _all_miss_after(t):
    def f(r):
        r.loc[r["t_complete"] >= t, "cached_tokens"] = 0
        return r
    return f


def test_a_clean_standin_counts_and_job_specific_keys_are_allowed(tmp_path):
    d = make_standin(tmp_path / "results", 4, "20261105-030000", job="99000001", salt=1)
    r = E.classify_run(d, RULE, registered=False)
    assert r["role"] == "replicate" and r["counted"] is True, r["problems"]
    assert r["label"] == E.STABLE and r["plan_equal"] is True and r["plan_bytes_equal"] is True
    assert r["engine_verified"] is None                                           # no job log dir next to the stand-in
    assert r["content_salt_equals_original"] is False and r["run_position"] == 1


@pytest.mark.parametrize("meta_over,cfg_over,needle", [
    ({"start_state_verified": False}, None, "start state not verified"),
    ({"status": "failed"}, None, "not finished"),
    ({"hardware": "NVIDIA H200, 143771 MiB"}, None, "hardware"),
    ({"engine_label": "sglang-fcfs-r1"}, None, "engine_label"),
    ({"git": {"commit": "x", "dirty": True}}, None, "git state"),
    ({"resolved_rate_sessions_per_s": 0.18}, None, "resolved rate"),
    (None, {"workload.decode_tokens": 101}, "config workload.decode_tokens"),
    (None, {"run.duration_s": 2900}, "config run.duration_s"),
])
def test_an_invalid_standin_does_not_count(tmp_path, meta_over, cfg_over, needle):
    d = make_standin(tmp_path / "results", 0, "20261105-030000", job="99000001", salt=1, meta_over=meta_over, cfg_over=cfg_over)
    r = E.classify_run(d, RULE, registered=False)
    assert r["counted"] is False and needle in r["problems"], r["problems"]


def test_a_standin_with_a_short_run_does_not_count(tmp_path):
    meta = json.loads((ORIG[0] / "meta.json").read_text())
    out = dict(meta["outcome"], t_end_s=1800.0, abort_reason="max_errors")
    d = make_standin(tmp_path / "results", 0, "20261105-030000", job="99000001", salt=1, meta_over={"outcome": out})
    r = E.classify_run(d, RULE, registered=False)
    assert r["counted"] is False and "shorter than" in r["problems"] and "not finished cleanly" in r["problems"]


# ============================================================================================ engine identity
def test_the_two_original_jobs_ran_the_same_engine():
    a, b = (REPO / RULE["originals"][s]["job_log_dir"] for s in ("0", "4"))
    e = E.engine_identity(a, b)
    assert e["verified"] is True and e["differing_server_args"] == [] and e["differing_banner_params"] == []
    assert all(e["files_equal"].values())
    assert E.gpu_of_job(a) == {"gpu_name": "NVIDIA A100 80GB PCIe", "gpu_bus_id": "00000000:86:00.0"}
    pa, pb = E.banner_params(a), E.banner_params(b)
    assert (pa["POLICY"], pa["REFRESH"], pa["LPM_INF"], pa["KV_TOKENS"], pa["MODE"]) == ("fcfs", "1", "0", "300000", "cap")
    assert (pa["SEEDS"], pb["SEEDS"]) == ("0", "3 4 5") and pa["ENGINE_LABEL"] != pb["ENGINE_LABEL"]   # job-specific, not compared


def test_a_changed_refresh_in_the_banner_is_caught(tmp_path):
    src = REPO / RULE["originals"]["4"]["job_log_dir"]
    jd = tmp_path / "nova_job_logs" / "99000004-20261105-030000"
    jd.mkdir(parents=True)
    for f in E.ENGINE_FILES:
        shutil.copyfile(src / f, jd / f)
    (jd / "banner.txt").write_text((src / "banner.txt").read_text(encoding="utf-8", errors="replace").replace(
        "POLICY=fcfs REFRESH=1", "POLICY=fcfs REFRESH=0"), encoding="utf-8")
    line = next(l for l in (src / "server.log").read_text(encoding="utf-8", errors="replace").splitlines() if "server_args=" in l)
    (jd / "server.log").write_text(line + "\n")
    e = E.engine_identity(jd, REPO / RULE["originals"]["0"]["job_log_dir"])
    assert e["verified"] is False and e["differing_banner_params"] == ["REFRESH"] and e["differing_server_args"] == []


def test_a_changed_engine_is_caught(tmp_path):
    src = REPO / RULE["originals"]["4"]["job_log_dir"]
    jd = tmp_path / "nova_job_logs" / "99000002-20261105-030000"
    jd.mkdir(parents=True)
    for f in E.ENGINE_FILES + ("banner.txt",):
        shutil.copyfile(src / f, jd / f)
    line = next(l for l in (src / "server.log").read_text(encoding="utf-8", errors="replace").splitlines() if "server_args=" in l)
    (jd / "server.log").write_text(line.replace("'schedule_policy': 'fcfs'", "'schedule_policy': 'lpm'") + "\n")
    e = E.engine_identity(jd, REPO / RULE["originals"]["0"]["job_log_dir"])
    assert e["verified"] is False and e["differing_server_args"] == ["schedule_policy"]
    assert E.engine_identity(None, src)["verified"] is None


# ============================================================================================ verdicts (synthetic rows)
def _row(seed, label, node, gpu, *, counted=True, role="replicate", job="1", pos=1):
    return {"seed": seed, "label": label, "node": node, "gpu_bus_id": gpu, "counted": counted, "role": role, "job": job,
            "run_position": pos, "content_salt": pos, "tau_s": 1600.0 if label == E.UNSTABLE else None, "run_dir": f"{seed}-{job}-{pos}"}


O = {0: _row(0, E.UNSTABLE, "nova22-gpu-1", "00000000:86:00.0", counted=False, role="original", job="17084754"),
     4: _row(4, E.STABLE, "nova22-gpu-3", "00000000:06:00.0", counted=False, role="original", job="17168507", pos=2)}
A = ("nova22-gpu-2", "00000000:C6:00.0")         # job A's GPU in these cases
B = ("nova22-gpu-1", "00000000:46:00.0")         # job B's GPU


def _jobs(a_out, b_out):
    """Rows of job A (seeds 0 4 0) and job B (seeds 4 0 4) with the given labels per position."""
    rows = [_row(s, l, *A, job="A", pos=i + 1) for i, (s, l) in enumerate(zip((0, 4, 0), a_out))]
    rows += [_row(s, l, *B, job="B", pos=i + 1) for i, (s, l) in enumerate(zip((4, 0, 4), b_out))]
    return rows


U, S = E.UNSTABLE, E.STABLE


def test_verdict_reproducible():
    v = E.verdict(_jobs((U, S, U), (S, U, S)), O, RULE)
    assert v["verdict"] == E.REPRODUCIBLE and not v["disagreement_observed"] and v["disagreement_level"] is None
    assert v["plans"]["0"]["replicates_unstable"] == 3 and v["plans"]["4"]["replicates_stable"] == 3


def test_verdict_escape_within_gpu():
    v = E.verdict(_jobs((U, S, S), (S, U, S)), O, RULE)          # seed 0 in job A: UNSTABLE at position 1, STABLE at 3
    assert v["verdict"] == E.ESCAPE and v["disagreement_level"] == "WITHIN-GPU"
    assert v["noise_induced_escape_at_fixed_workload"] is True
    assert v["plans"]["0"]["disagree"] and not v["plans"]["4"]["disagree"]
    assert v["plans"]["0"]["location"]["gpus_with_disagreement"] == [f"{A[0]}/{A[1]}"]
    assert v["plans"]["0"]["disagree_among_new_runs"] is True and v["disagreement_among_new_runs_observed"] is True
    assert v["plans"]["0"]["location_among_new_runs"]["level"] == "WITHIN-GPU"


def test_verdict_escape_within_node_on_different_gpus():
    rows = _jobs((U, S, U), (S, U, S))
    rows[3] = _row(4, U, "nova22-gpu-3", "00000000:45:00.0", job="B", pos=1)   # seed 4 UNSTABLE on the original's node, other GPU
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.ESCAPE and v["disagreement_level"] == "WITHIN-NODE"
    assert v["plans"]["4"]["location"]["nodes_with_disagreement"] == ["nova22-gpu-3"]
    assert v["noise_induced_escape_at_fixed_workload"] is True


def test_verdict_escape_across_nodes_only_when_only_the_original_disagrees():
    v = E.verdict(_jobs((U, U, U), (U, U, U)), O, RULE)          # seed 4: all 3 new runs UNSTABLE, the original STABLE
    assert v["verdict"] == E.ESCAPE and v["disagreement_level"] == "ACROSS-NODES-ONLY"
    assert v["noise_induced_escape_at_fixed_workload"] is False
    loc = v["plans"]["4"]["location"]
    assert loc["outcomes_by_node"] == {"nova22-gpu-3": [S], A[0]: [U], B[0]: [U]}
    assert v["plans"]["4"]["disagree_among_new_runs"] is False


def test_a_disagreement_is_an_escape_whatever_the_replicate_counts():
    # the design: PLAN-CONDITIONAL ESCAPE iff some plan's runs disagree (the original counted); no count gate before it
    rows = _jobs((U, S, U), (S, U, S))
    for r in rows:
        if r["seed"] == 4 and r["job"] == "B":
            r["counted"] = False                                  # job B's seed-4 runs failed a check
    rows[1]["label"] = U                                          # the one counted seed-4 replicate disagrees
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.ESCAPE and v["disagreement_observed"] is True
    assert v["plans"]["4"]["n_valid_replicates"] == 1 and v["plans"]["4"]["disagree"] is True
    assert v["plans"]["4"]["disagree_among_new_runs"] is False    # only the original disagrees with its one replicate
    # a same-GPU disagreement of plan 0 while plan 4 has no valid replicate at all is still an ESCAPE, read as noise
    rows = _jobs((U, S, S), (S, U, S))
    for r in rows:
        if r["seed"] == 4:
            r["counted"] = False
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.ESCAPE and v["plans"]["4"]["n_valid_replicates"] == 0
    assert v["disagreement_level"] == "WITHIN-GPU" and v["noise_induced_escape_at_fixed_workload"] is True


def test_verdict_incomplete_only_without_a_disagreement():
    rows = _jobs((U, S, U), (S, U, S))
    for r in rows:
        if r["seed"] == 4 and r["job"] == "B":
            r["counted"] = False                                  # 1 valid seed-4 replicate, everything agrees
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.INCOMPLETE and v["disagreement_observed"] is False
    assert v["plans"]["4"]["n_valid_replicates"] == 1


def test_an_original_only_disagreement_on_its_node_is_flagged_as_not_among_the_new_runs():
    # job A on the seed-0 original's GPU: all three new seed-0 runs STABLE, the original UNSTABLE -> WITHIN-GPU by the rule,
    # but the new runs agree among themselves (the disagreement is also confounded with the date and the job)
    rows = [_row(s, l, "nova22-gpu-1", "00000000:86:00.0", job="A", pos=i + 1) for i, (s, l) in enumerate(zip((0, 4, 0), (S, S, S)))]
    rows += [_row(s, l, *B, job="B", pos=i + 1) for i, (s, l) in enumerate(zip((4, 0, 4), (S, S, S)))]
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.ESCAPE and v["disagreement_level"] == "WITHIN-GPU"
    p0 = v["plans"]["0"]
    assert p0["disagree"] is True and p0["disagree_among_new_runs"] is False and p0["location_among_new_runs"] is None
    assert v["disagreement_among_new_runs_observed"] is False


def test_verdict_consistent_partial_with_two_replicates_of_a_plan():
    rows = _jobs((U, S, U), (S, U, S))
    rows[2]["counted"] = False                                    # seed 0: 2 valid replicates, both UNSTABLE
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.PARTIAL and v["plans"]["0"]["n_valid_replicates"] == 2


def test_runs_that_do_not_count_cannot_create_a_disagreement():
    rows = _jobs((U, S, U), (S, U, S))
    rows.append(_row(4, U, *A, counted=False, job="A", pos=4))
    v = E.verdict(rows, O, RULE)
    assert v["verdict"] == E.REPRODUCIBLE


def test_an_original_that_the_rule_reclassifies_is_a_rule_error():
    o = dict(O)
    o[4] = dict(O[4], label=U)
    assert E.verdict(_jobs((U, S, U), (S, U, S)), o, RULE)["verdict"] == E.RULE_ERROR


# ============================================================================================ end to end
def test_classify_end_to_end_with_standins(tmp_path):
    root = tmp_path / "results"
    dirs = []
    for job, seeds in (("99000001", (0, 4, 0)), ("99000002", (4, 0, 4))):
        for i, s in enumerate(seeds):
            dirs.append(make_standin(root, s, f"2026110{job[-1]}-0{i}0000", job=job, salt=i + 1))
    res = E.classify(dirs + [ORIG[0]], RULE, registered=False)      # an original passed in is recognised, not counted twice
    assert len(res["rows"]) == 6 and all(r["counted"] for r in res["rows"])
    assert res["verdict"]["verdict"] == E.REPRODUCIBLE
    assert {j["planned_job"] for j in res["jobs"].values()} == {"A", "B"}
    # one seed-4 stand-in turns all-miss after 1500 s on the original's node: same plan, different outcome, same node
    bad = make_standin(root, 4, "20261103-000000", job="99000003", salt=1, requests_fn=_all_miss_after(1500.0))
    res2 = E.classify(dirs + [bad], RULE, registered=False)
    v = res2["verdict"]
    assert v["verdict"] == E.ESCAPE and v["plans"]["4"]["disagree"] and v["disagreement_level"] == "WITHIN-NODE"
    assert v["plans"]["4"]["replicates_unstable"] == 1 and v["plans"]["4"]["location"]["gpu_ids_complete"] is False


PREDS = REPO / "results/theory/r15/edge_preds.json"


@pytest.mark.skipif(not PREDS.exists(), reason="frozen predictions not in this checkout (results/* is ignored; force-added)")
def test_the_frozen_predictions_match_their_sources_and_this_rule_file():
    d = json.loads(PREDS.read_text())
    assert d["status"] == "FROZEN" and d["exploratory"] is True and d["rule_file"] == "configs/r15_edge_replicate.yaml"
    import hashlib
    assert d["provenance"]["sha256"]["configs/r15_edge_replicate.yaml"] == \
        hashlib.sha256((REPO / "configs/r15_edge_replicate.yaml").read_bytes()).hexdigest()
    f2 = json.loads((REPO / "results/theory/merged/a100_300k.json").read_text())["from_empty_edge"]["p_escape_fine"]["2.5"]
    assert d["F2"]["exchangeable_independent_replicates"]["p_unstable_per_run"] == f2
    h = d["headline"]
    assert h["deterministic_comparators"] == {"count": "REPRODUCIBLE", "turns": "REPRODUCIBLE", "token_work": "REPRODUCIBLE"}
    assert h["pred2_level_crossing"] == "REPRODUCIBLE" and h["F2_exchangeable"]["verdict"] == E.ESCAPE
    assert h["simulator_calls"] == {"0": {"mixed": U, "separate": U}, "4": {"mixed": S, "separate": S}}
    b = d["deterministic_comparators"]["brackets"]
    assert (round(b["turns"]["stable_max"], 3), round(b["turns"]["unstable_min"], 3)) == (2.515, 2.708)
    assert (round(b["token_work"]["stable_max"], 1), round(b["token_work"]["unstable_min"], 1)) == (84.3, 92.0)
    assert all(d["simulator"]["reproduces_committed_r11_e0b_rows"].values())


def test_cli_writes_its_outputs_for_the_originals(tmp_path):
    rc = E.main(["classify", "--run-dirs", str(ORIG[0]), str(ORIG[4]), "--out-root", str(tmp_path)])
    assert rc == 0
    (d,) = list((tmp_path / "agentload_analysis_r15_edge").iterdir())
    df = pd.read_csv(d / "r15_edge_runs.csv")
    assert list(df["role"]) == ["original", "original"] and list(df["label"]) == [E.UNSTABLE, E.STABLE]
    out = json.loads((d / "r15_edge_verdict.json").read_text())
    assert out["verdict"]["verdict"] == E.INCOMPLETE
    assert out["verdict_with_registered_stable_rule_descriptive"]["verdict"] == E.INCOMPLETE
    meta = json.loads((d / "meta.json").read_text())
    assert meta["exploratory"] is True and meta["status"] == "finished"
