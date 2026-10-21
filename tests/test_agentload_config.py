import json

import pytest
import yaml

from agentload.config import (apply_overrides, config_from_dict, load_config, resolve_lambda_ref, resolve_rate,
                              resolve_ramp)
from conftest import REPO, make_raw

GEN_CONFIGS = ["agentload_mock", "agentload_e0_miss", "agentload_e0_cap", "agentload_e2_burst", "agentload_c_closed"]


@pytest.mark.parametrize("name", GEN_CONFIGS)
def test_generator_configs_load(name):
    cfg, raw = load_config(REPO / "configs" / f"{name}.yaml")
    assert cfg.workload.max_turns >= 1 and cfg.run.duration_s > 0


def test_all_agentload_configs_have_research_question_first():
    paths = sorted((REPO / "configs").glob("agentload_*.yaml"))
    assert len(paths) >= 9 and "agentload_prereg_template.yaml" in {p.name for p in paths}
    for p in paths:
        first_key = next(iter(yaml.safe_load(p.read_text())))
        assert first_key == "research_question", p.name


def test_real_engine_configs_match_simulator_workload():
    # the simulator's constants (configs/prefix_meta.yaml on pilot/prefix-meta)
    for name in ("agentload_e0_miss", "agentload_e0_cap", "agentload_e2_burst", "agentload_c_closed"):
        cfg, _ = load_config(REPO / "configs" / f"{name}.yaml")
        w = cfg.workload
        assert (w.initial_context_tokens, w.new_prompt_tokens, w.decode_tokens) == (2000, 550, 100)
        assert (w.mean_turns, w.max_turns, w.tool_time_mean_s, w.tool_time_dist) == (15, 60, 5.0, "exp")
        assert cfg.server.extra_body["ignore_eos"] is True
    b = load_config(REPO / "configs" / "agentload_e2_burst.yaml")[0].arrivals.burst
    assert (b.n, b.width_s) == (200, 60.0)


def test_unknown_keys_rejected():
    raw = make_raw()
    raw["workload"]["bogus"] = 1
    with pytest.raises(KeyError):
        config_from_dict(raw)
    raw = make_raw()
    raw["bogus"] = 1
    with pytest.raises(KeyError):
        config_from_dict(raw)


def test_validation():
    with pytest.raises(ValueError):
        config_from_dict(make_raw(workload={"prompt_mode": "audio"}))
    with pytest.raises(ValueError):
        config_from_dict(make_raw(arrivals={"kind": "closed", "closed_n": 0}))
    with pytest.raises(ValueError):
        config_from_dict(make_raw(arrivals={"kind": "ramp", "ramp": [[0, 1]]}))


def test_overrides_nested_and_yaml_typed():
    raw = apply_overrides(make_raw(), ["run.seed=7", "arrivals.burst.n=5", "meta.engine_label=\"a b\"",
                                       "server.extra_body={ignore_eos: false}"])
    cfg = config_from_dict(raw)
    assert cfg.run.seed == 7 and cfg.arrivals.burst.n == 5 and cfg.meta.engine_label == "a b"
    assert cfg.server.extra_body == {"ignore_eos": False}
    with pytest.raises(ValueError):
        apply_overrides(make_raw(), ["no_equals_sign"])


def test_resolve_rate_and_lambda_ref(tmp_path):
    f = tmp_path / "calibration.json"
    f.write_text(json.dumps({"lambda_miss": 0.05, "lambda_miss_turns_based": 0.04}))
    cfg = config_from_dict(make_raw(arrivals={"rate": None, "rate_mult": 1.5,
                                              "lambda_ref": f"{f}:lambda_miss_turns_based"}))
    assert resolve_rate(cfg.arrivals) == pytest.approx(0.06)
    assert resolve_lambda_ref(0.1) == 0.1
    with pytest.raises(ValueError):                      # rate and rate_mult together
        resolve_rate(config_from_dict(make_raw(arrivals={"rate": 1.0, "rate_mult": 2.0, "lambda_ref": 1.0})).arrivals)
    with pytest.raises(FileNotFoundError, match="placeholder"):
        resolve_rate(config_from_dict(make_raw(arrivals={"rate": None, "rate_mult": 1.0,
                                                         "lambda_ref": "<RESULTS_DIR>/calibration.json:x"})).arrivals)


def test_resolve_ramp_mult():
    cfg = config_from_dict(make_raw(arrivals={"kind": "ramp", "rate": None, "ramp": [[0, 1.0], [100, 2.0]],
                                              "ramp_is_mult": True, "lambda_ref": 0.05}))
    assert resolve_ramp(cfg.arrivals) == [(0.0, 0.05), (100.0, 0.1)]
    with pytest.raises(ValueError):
        resolve_ramp(config_from_dict(make_raw(arrivals={"kind": "ramp", "rate": None,
                                                         "ramp": [[10, 1.0], [5, 2.0]]})).arrivals)


def test_plan_cli_writes_recorded_stats(tmp_path, capsys):
    from agentload.cli import main
    from agentload.workload import build_open_plan, prompt_len
    cfgp = REPO / "configs" / "agentload_e2_burst.yaml"
    rc = main(["plan", "--config", str(cfgp), "--set", "arrivals.lambda_ref=0.05", "--set", "arrivals.rate_mult=1.6",
               "--seed", "3", "--out-root", str(tmp_path), "--write"])
    assert rc == 0
    d = next((tmp_path / "agentload_e2_burst_planstats").iterdir())
    st = json.loads((d / "plan_stats.json").read_text())
    cfg, _ = load_config(cfgp, ["arrivals.lambda_ref=0.05", "arrivals.rate_mult=1.6", "run.seed=3"])
    plan = build_open_plan(3, cfg.workload, cfg.arrivals, cfg.run.duration_s, 0.08, [])
    assert st["resolved_rate"] == pytest.approx(0.08) and st["n_sessions"] == len(plan)
    assert st["n_burst_sessions"] == 200 and st["n_turns_total"] == sum(p.n_turns for p in plan)
    assert st["all_miss_prompt_tokens_total"] == sum(prompt_len(cfg.workload, t) for p in plan
                                                     for t in range(1, p.n_turns + 1))
    assert st["max_prompt_tokens"] == 2000 + 59 * 650
    meta = json.loads((d / "meta.json").read_text())
    assert meta["seeds"] == [3] and meta["git"]["captured_at"] == "run start" and (d / "config.yaml").exists()


def test_stage_c_and_e2_configs_encode_the_referee_design():
    c, _ = load_config(REPO / "configs" / "agentload_c_closed.yaml")
    assert c.arrivals.kind == "closed" and c.run.duration_s == 2700 and c.gate.n_cap is None      # warmup 900 + measure 1800
    e, _ = load_config(REPO / "configs" / "agentload_e2_burst.yaml", ["arrivals.lambda_ref=0.05"])
    assert e.gate.n_cap is None and e.meta.arm == "" and e.arrivals.analysis_t_burst_s == e.arrivals.burst.t_s == 1200
    # the three arms are overrides of ONE config: NOBURST drops the burst, CAPPED adds the gate
    nb, _ = load_config(REPO / "configs" / "agentload_e2_burst.yaml", ["arrivals.lambda_ref=0.05", "arrivals.burst=null", "meta.arm=\"noburst\""])
    assert nb.arrivals.burst is None and nb.arrivals.analysis_t_burst_s == 1200 and nb.meta.arm == "noburst"
    cp, _ = load_config(REPO / "configs" / "agentload_e2_burst.yaml", ["arrivals.lambda_ref=0.05", "gate.n_cap=22", "meta.arm=capped"])
    assert cp.gate.n_cap == 22 and cp.arrivals.burst.n == 200
