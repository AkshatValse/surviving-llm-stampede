"""B2 basin dose-response (r14, remedy N1): the n=40 / 50 / 60 E2 configs, their registrations, check-job, and the frozen
bracketing rule of analysis/basin.py.

No engine anywhere: plans come from the generator's own plan code and check-job is the real CLI. The B1 cells (n=100 / 25)
keep their own tests in tests/test_r11_basin.py; here they are only checked to fill byte-identically after the B2 change."""
import hashlib

import yaml
import pytest

from conftest import REPO

from analysis import basin, prereg
from analysis.params import load_params

NS = (40, 50, 60)
DEFAULT_CFG = REPO / "configs" / "agentload_e2_burst.yaml"
PARENT = REPO / "configs" / "agentload_prereg_2026-10-24.yaml"
CAL = "prereg/inputs/2026-10-23/calibration.json"
HW = "NVIDIA A100 80GB PCIe, 81920 MiB"
ENDPOINTS = REPO / "configs" / "r11_basin_predict.yaml"
N1_RULE = ("the basin boundary is bracketed iff b=40 is GOOD in >=2/3 seeds and b=60 STUCK in >=2/3 seeds; the seven-point "
           "curve 0,25,40,50,60,100,200 is reported against the frozen committor")


def cfg_path(n):
    return REPO / "configs" / f"agentload_e2_burst_n{n}.yaml"


def reg_path(n):
    return REPO / "configs" / (f"agentload_prereg_2026-10-31_b{n}.yaml" if n in NS else f"agentload_prereg_2026-10-30_b{n}.yaml")


# ---------------------------------------------------------------- configs
@pytest.mark.parametrize("n", NS)
def test_cell_config_is_a_byte_copy_except_burst_n(n):
    a, b = DEFAULT_CFG.read_bytes(), cfg_path(n).read_bytes()
    assert b"\r" not in b
    la, lb = a.split(b"\n"), b.split(b"\n")
    assert len(la) == len(lb)
    diff = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    assert len(diff) == 1
    old, new = la[diff[0]], lb[diff[0]]
    assert old.startswith(b"  burst: {n: 200, t_s: 1200, width_s: 60}")
    assert new.startswith(b"  burst: {n: %d, t_s: 1200, width_s: 60}" % n)
    assert old.split(b"#", 1)[1] == new.split(b"#", 1)[1]                  # comment unchanged
    ya, yb = yaml.safe_load(a), yaml.safe_load(b)
    assert yb["arrivals"]["burst"] == {"n": n, "t_s": 1200, "width_s": 60}
    yb["arrivals"]["burst"]["n"] = 200
    assert ya == yb


@pytest.mark.parametrize("n", NS)
def test_cell_config_has_the_same_shape_as_the_b1_configs(n):
    # n=25 and n=100 were made the same way; the n-cell file equals each of them up to the digits of burst.n
    for m in (25, 100):
        other = cfg_path(m).read_bytes().replace(b"  burst: {n: %d," % m, b"  burst: {n: %d," % n, 1)
        assert other == cfg_path(n).read_bytes()


# ---------------------------------------------------------------- plans: common random numbers with E2 and B1
def _base(plan):
    return [(s.idx, repr(s.arrival_s), s.n_turns, tuple(repr(t) for t in s.tool_times_s)) for s in plan if s.origin == "base"]


def _burst_times(plan):
    return sorted(s.arrival_s for s in plan if s.origin == "burst")


def _burst_specs(plan):
    return sorted((s.idx, s.n_turns, tuple(repr(t) for t in s.tool_times_s)) for s in plan if s.origin == "burst")


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cell_plans_share_base_sessions_and_draw_burst_times_as_a_subset(seed):
    import numpy as np
    from agentload.workload import S_BURST, make_rng

    p200 = basin.basin_plan(DEFAULT_CFG, seed)
    p0 = basin.basin_plan(DEFAULT_CFG, seed, burst_null=True)
    assert sum(s.origin == "burst" for s in p200) == 200 and not any(s.origin == "burst" for s in p0)
    b200 = _burst_times(p200)
    raw200 = make_rng(seed, S_BURST).uniform(1200.0, 1260.0, size=200)          # the n=200 draw in draw order
    prev = None
    for n in (25,) + NS + (100,):
        pn = basin.basin_plan(cfg_path(n), seed)
        assert _base(pn) == _base(p200) == _base(p0)                       # byte-identical base sessions
        bn = _burst_times(pn)
        assert len(bn) == n and set(bn) <= set(b200)                       # burst starts: a subset of the 200
        assert bn == sorted(float(t) for t in raw200[:n])                  # ... namely the FIRST n draws of the 200
        assert all(1200.0 <= t < 1260.0 for t in bn)
        assert _burst_specs(pn) == _burst_specs(p200)[:n]                  # burst session specs: the first n of the 200
        if prev is not None:
            assert set(prev) < set(bn)                                     # nested: 25 < 40 < 50 < 60 < 100 < 200
        prev = bn
    assert np.all(np.diff(b200) >= 0)


# ---------------------------------------------------------------- registrations
@pytest.mark.parametrize("n", (100, 25))
def test_b1_registrations_still_fill_byte_identically(n):
    assert basin.dump_registration(basin.fill_registration(n)) == reg_path(n).read_bytes()


@pytest.mark.parametrize("n", NS)
def test_registration_is_reproduced_by_fill_and_is_valid(n):
    data = reg_path(n).read_bytes()
    assert b"\r" not in data
    assert basin.dump_registration(basin.fill_registration(n)) == data
    pr = prereg.load_prereg(reg_path(n))
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", [])
    errs = [x for x in prereg.validate(pr, p, "fcfs", prereg_path=reg_path(n)) if x["severity"] == "error"]
    assert errs == []
    assert pr["status"] == "FILLED"
    assert pr["inputs"]["engine_cell_label"] == f"sglang-fcfs-r1-b{n}"
    assert pr["inputs"]["e2_config"] == f"configs/agentload_e2_burst_n{n}.yaml"
    assert pr["protocol"] == {"duration_s": 8700, "t_burst_s": 1200, "burst_n": n, "burst_width_s": 60}
    assert pr["lambda_selection"]["lambda_mults"] == [1.65]
    assert pr["measured"]["n_cap"] == 20
    rule = pr["lambda_selection"]["rule"]
    for needle in ("STUCK := hit_eval < 0.2", "GOOD := trap_v2 RECOVERED", "[5700, 8700)", "configs/r11_basin_predict.yaml",
                   "17093387-404", "1/3-2/3", N1_RULE, "r11-basin-reg"):
        assert needle in rule
    assert pr["measured"]["n_cap_rule"].startswith("smallest n with mu(n) >= (1 - 0.05) * mu_max")       # smallest_within_margin


@pytest.mark.parametrize("n", NS)
def test_registration_differs_from_the_2026_10_24_file_only_where_allowed(n):
    a, b = prereg.load_prereg(PARENT), prereg.load_prereg(reg_path(n))
    d = basin.registration_diff(a, b)
    assert d["forbidden"] == []
    assert sorted(d["allowed"]) == sorted(basin.REGISTRATION_DIFF_ALLOWED)
    assert all(k.startswith("predicted_boundaries.capped_drain.") for k in d["derived"])
    for sec in ("measured", "pass_rule", "kill_conditions", "predictions", "checks", "fill_problems"):
        assert a[sec] == b[sec], sec
    for k in ("mu_curve_json", "calibration_json", "e0b_bracket_json"):
        assert a["inputs"][k] == b["inputs"][k]


@pytest.mark.parametrize("n", NS)
def test_registration_differs_from_the_b100_registration_only_in_label_config_burst_and_rule(n):
    d = basin.registration_diff(prereg.load_prereg(reg_path(100)), prereg.load_prereg(reg_path(n)))
    assert d["forbidden"] == []
    assert sorted(d["allowed"]) == ["inputs.e2_config", "inputs.engine_cell_label", "lambda_selection.rule", "protocol.burst_n"]


def test_frozen_endpoints_are_the_b1_ones_and_agree_with_the_registered_constants():
    ep = basin.load_endpoints(ENDPOINTS)
    assert ep["stuck_hit_below"] == 0.2 and ep["good_hit_above"] == 0.8 and ep["eval_window_s"] == [5700.0, 8700.0]
    assert ep["trapped_co_primary_n"] == [100]
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", ["trap_v2.eval_from_s=4500.0"])
    assert basin.endpoint_problems(ep, p) == []


# ---------------------------------------------------------------- check-job
def _check_job(capsys, reg, cfg, label, mults="1.65", arms="burst"):
    rc = prereg.main(["check-job", str(reg), "--label", label, "--mults", mults, "--arms", arms, "--calib", str(REPO / CAL),
                      "--hardware", HW, "--e2-config", str(cfg), "--duration-s", "8700", "--t-burst-s", "1200",
                      "--params", str(REPO / "configs" / "agentload_analysis.yaml"), "--set", "trap_v2.eval_from_s=4500.0",
                      "--allow-uncommitted"])
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("n", NS)
def test_check_job_accepts_the_cell_config_with_its_registration(capsys, n):
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), f"sglang-fcfs-r1-b{n}")
    assert rc == 0, out
    assert "PREREG_SHA256=" in out and "PREREG_OK " in out


@pytest.mark.parametrize("n", NS)
def test_check_job_refuses_the_default_config_under_the_cell_registration(capsys, n):
    rc, out = _check_job(capsys, reg_path(n), DEFAULT_CFG, f"sglang-fcfs-r1-b{n}")
    assert rc == 1
    assert f"E2 config burst.n=200 != registered protocol {n}" in out
    assert out.count("PREREG PROBLEM") == 1


@pytest.mark.parametrize("n", NS)
def test_check_job_refuses_the_cell_config_under_the_2026_10_24_registration(capsys, n):
    rc, out = _check_job(capsys, PARENT, cfg_path(n), f"sglang-fcfs-r1-b{n}")
    assert rc == 1
    assert "!= registered cell 'sglang-fcfs-r1'" in out and f"E2 config burst.n={n} != registered protocol 200" in out


@pytest.mark.parametrize("n,other", [(40, 60), (60, 40), (50, 40), (40, 50)])
def test_check_job_refuses_a_crossed_cell(capsys, n, other):
    rc, out = _check_job(capsys, reg_path(n), cfg_path(other), f"sglang-fcfs-r1-b{n}")      # wrong config
    assert rc == 1 and f"E2 config burst.n={other} != registered protocol {n}" in out and out.count("PREREG PROBLEM") == 1
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), f"sglang-fcfs-r1-b{other}")      # wrong label
    assert rc == 1 and f"!= registered cell 'sglang-fcfs-r1-b{n}'" in out


@pytest.mark.parametrize("n", NS)
def test_check_job_refuses_the_measured_label_and_unregistered_rates_or_arms(capsys, n):
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), "sglang-fcfs-r1")
    assert rc == 1 and f"!= registered cell 'sglang-fcfs-r1-b{n}'" in out
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), f"sglang-fcfs-r1-b{n}", mults="1.35")
    assert rc == 1 and "PREREG PROBLEM" in out
    rc, out = _check_job(capsys, reg_path(n), cfg_path(n), f"sglang-fcfs-r1-b{n}", arms="burst capped")
    assert rc == 0 or "PREREG PROBLEM" in out      # the three-arm template registers capped too; only checked not to crash


# ---------------------------------------------------------------- the frozen bracketing rule
def _rec(seed, stuck=False, good=False):
    return {"seed": seed, "stuck": stuck, "good": good, "basin_state": "stuck" if stuck else "good" if good else "neither",
            "hit_eval": 0.0 if stuck else 0.9 if good else 0.5}


def test_bracket_decision():
    G, S, X = (lambda s: _rec(s, good=True)), (lambda s: _rec(s, stuck=True)), (lambda s: _rec(s))
    d = basin.bracket_decision({40: [G(0), G(1), S(2)], 60: [S(0), S(1), G(2)]})
    assert d["bracketed"] is True and d["notes"] == [] and d["need_of_seeds"] == 2
    d = basin.bracket_decision({40: [G(0), S(1), S(2)], 60: [S(0), S(1), S(2)]})
    assert d["bracketed"] is False and any("below 40" in x for x in d["notes"])
    d = basin.bracket_decision({40: [G(0), G(1), G(2)], 60: [G(0), G(1), X(2)]})
    assert d["bracketed"] is False and any("above 60" in x for x in d["notes"])
    d = basin.bracket_decision({40: [G(0), G(1)], 60: [S(0)]})
    assert d["bracketed"] is None and d["incomplete"] == ["40", "60"]    # 60 can still reach 2/3
    d = basin.bracket_decision({40: [G(0), X(1)], 60: [S(0), S(1), S(2)]})
    assert d["bracketed"] is None                                        # 40 seed 2 still open
    d = basin.bracket_decision({40: [X(0), X(1)], 60: [S(0), S(1), S(2)]})
    assert d["bracketed"] is False                                       # 40 can no longer reach 2/3 GOOD
    d = basin.bracket_decision({40: [G(0), G(1), G(2)], 50: [S(0), S(1), S(2)], 60: [S(0), S(1), S(2)]})
    assert d["bracketed"] is True and set(d["cells"]) == {"40", "60"}    # 50 does not enter the rule
    d = basin.bracket_decision({40: [G(0), G(1), G(2), G(5)], 60: [S(0), S(1), S(2)]})
    assert d["cells"]["40"]["n_runs"] == 3                               # seeds outside 0-2 are ignored


def test_curve_table_lists_the_seven_points_per_seed():
    by_n = {0: [_rec(0, good=True)], 200: [_rec(0, stuck=True), _rec(1, stuck=True)], 40: [_rec(2, good=True)]}
    c = basin.curve_table(by_n)
    assert list(c) == ["0", "25", "40", "50", "60", "100", "200"]
    assert c["200"]["stuck"] == 2 and c["200"]["per_seed"]["2"] is None and c["40"]["per_seed"]["2"]["basin_state"] == "good"
    assert c["25"]["n_seeds"] == 0


def test_classify_reports_the_bracket_and_curve_without_b2_runs():
    p = load_params(REPO / "configs" / "agentload_analysis.yaml", ["trap_v2.eval_from_s=4500.0"])
    ep = basin.load_endpoints(ENDPOINTS)
    res = basin.classify([], [], ep, p, [])
    assert res["b2_bracket"]["bracketed"] is None and res["b2_bracket"]["incomplete"] == ["40", "60"]
    assert list(res["curve"]) == ["0", "25", "40", "50", "60", "100", "200"]
    assert res["decision"]["basin_pass"] is None


def test_fill_cli_offers_the_b2_cells_and_refuses_others(tmp_path):
    out = tmp_path / "x.yaml"
    assert basin.main(["fill", "--n", "40", "--out", str(out)]) == 0
    assert out.read_bytes() == reg_path(40).read_bytes()
    assert basin.main(["fill", "--n", "40", "--out", str(out)]) == 2      # refuses to overwrite
    with pytest.raises(SystemExit):
        basin.main(["fill", "--n", "45", "--out", str(tmp_path / "y.yaml")])


# ---------------------------------------------------------------- review fixes: one vote per seed, only bound runs count
def test_bracket_decision_refuses_to_count_a_seed_twice():
    G, S = (lambda s: _rec(s, good=True)), (lambda s: _rec(s, stuck=True))
    d = basin.bracket_decision({40: [G(0), G(0), S(1), S(2)], 60: [S(0), S(1), S(2)]})   # a resubmitted seed 0
    assert d["bracketed"] is None and d["cells"]["40"]["duplicate_seeds"] == [0]
    assert any("duplicate seed" in x for x in d["notes"])
    d = basin.bracket_decision({40: [G(0), G(1), S(2)], 60: [S(0), S(1), S(2)]})
    assert d["bracketed"] is True and d["cells"]["40"]["duplicate_seeds"] == []


def _b2rec(tmp_path, n=40, cfg_bytes=None, **kw):
    d = tmp_path / f"run{n}_{len(list(tmp_path.iterdir()))}"
    d.mkdir()
    (d / "config.yaml").write_bytes(cfg_path(n).read_bytes() if cfg_bytes is None else cfg_bytes)
    rec = {"run_dir": str(d), "burst_n": n, "role": "new", "label": f"sglang-fcfs-r1-b{n}", "arm": "burst",
           "rate_mult": 1.65, "aborted": False, "window_matches_endpoints": True, "prereg_bound": True, "prereg_blockers": ""}
    rec.update(kw)
    return rec


def test_b2_eligibility(tmp_path):
    for n in (40, 50, 60):
        assert basin.B2_CONFIG_SHA256[n] == hashlib.sha256(cfg_path(n).read_bytes()).hexdigest()
        assert basin.b2_eligibility(_b2rec(tmp_path, n)) == (True, "")
    crlf = cfg_path(40).read_bytes().replace(b"\n", b"\r\n")
    assert basin.b2_eligibility(_b2rec(tmp_path, cfg_bytes=crlf))[0] is True          # CRLF read as LF
    for kw, msg in (({"prereg_bound": None, "prereg_blockers": None}, "no --prereg"),
                    ({"prereg_bound": False, "prereg_blockers": "run not bound"}, "run not bound"),
                    ({"label": "sglang-fcfs-r1"}, "label"), ({"arm": "noburst"}, "arm"), ({"rate_mult": 1.35}, "rate_mult"),
                    ({"aborted": True, "abort_reason": "x"}, "aborted"), ({"window_matches_endpoints": False}, "window"),
                    ({"role": "baseline"}, "role")):
        ok, why = basin.b2_eligibility(_b2rec(tmp_path, **kw))
        assert ok is False and msg in why, (kw, why)
    ok, why = basin.b2_eligibility(_b2rec(tmp_path, cfg_bytes=cfg_path(60).read_bytes()))   # n60 bytes under n=40
    assert ok is False and "config.yaml sha256" in why
    assert basin.b2_eligibility({"burst_n": 100}) == (False, "")                              # B1 / baselines untouched
