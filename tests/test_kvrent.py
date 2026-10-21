import copy
import math
from pathlib import Path

import numpy as np
import pytest

from experiments.kvrent_run import main as run_main
from kvrent.policies import POLICY_NAMES, ETA_FREE, Costs, ContinuumTTL, SkiRand
from kvrent.runner import run_one
from kvrent.sim import SimParams
from kvrent.workload import generate_workload, load_config

CFG_PATH = Path(__file__).resolve().parents[1] / "configs/kvrent_pilot.yaml"


def small_cfg(horizon=900.0, warmup=60.0, margin=120.0, **server):
    cfg = copy.deepcopy(load_config(CFG_PATH))
    cfg["sim"].update(horizon_s=horizon, warmup_s=warmup, margin_s=margin)
    cfg["server"].update(server)
    return cfg


def test_smoke():
    cfg = small_cfg()
    res, row = run_one(cfg, 0.2, "default", "CONTINUUM_TTL", 4.0, seed=0)
    assert row["n_done"] > 0 and 0 < row["util_mean"] <= 1.0
    assert math.isclose(row["frac_held"] + row["frac_swap"] + row["frac_discard"], 1.0)


def test_determinism(tmp_path):
    cfg = small_cfg(horizon=300, warmup=30, margin=60)
    import yaml
    p = tmp_path / "c.yaml"
    cfg["experiment"].update(arrival_rates=[0.2, 0.4], seeds=[0, 1], mixes=["default", "shift"])
    p.write_text(yaml.safe_dump(cfg))
    a = run_main(["--config", str(p), "--outdir", str(tmp_path / "a"), "--no-plots"])
    b = run_main(["--config", str(p), "--outdir", str(tmp_path / "b"), "--no-plots"])
    for f in ("results.csv", "summary.csv"):
        assert (a / f).read_bytes() == (b / f).read_bytes()
    assert (a / "meta.json").exists()


def test_different_seed_differs():
    cfg = small_cfg()
    _, r0 = run_one(cfg, 0.2, "default", "SKI_RAND", 4.0, seed=0)
    _, r1 = run_one(cfg, 0.2, "default", "SKI_RAND", 4.0, seed=1)
    assert r0["mean_lat"] != r1["mean_lat"]


@pytest.mark.parametrize("pol", POLICY_NAMES)
def test_memory_never_exceeds_M_under_pressure(pol):
    cfg = small_cfg(M_tokens=60000)   # small M, heavy contention, exercises forced eviction
    res, row = run_one(cfg, 0.3, "heavy", pol, 4.0, seed=3)
    assert res.max_used <= 60000 + 1e-6
    assert row["util_mean"] <= 1.0 + 1e-9


@pytest.mark.parametrize("pol", POLICY_NAMES)
def test_every_program_completes_or_inflight(pol):
    cfg = small_cfg(M_tokens=100000)
    prm = SimParams.from_cfg(cfg)
    res, row = run_one(cfg, 0.3, "default", pol, 4.0, seed=2)
    arrived = res.arrival < prm.horizon
    done = ~np.isnan(res.finish)
    assert (res.finish[done] >= res.arrival[done]).all()
    win = (res.arrival >= prm.warmup) & (res.arrival < prm.horizon - prm.margin)
    assert row["n_window"] == int(win.sum()) == row["n_done"] + row["n_inflight"]
    assert arrived.all()


def test_zero_tool_latency_policies_identical():
    # Uncontended memory: under contention the policies' eviction *action* can differ
    # via the deadlock breaker (forced eviction), which is outside this invariant.
    cfg = small_cfg(M_tokens=1e9)
    cfg["sim"]["tool_time_scale"] = 0.0
    fins = []
    for pol in POLICY_NAMES:
        res, _ = run_one(cfg, 0.3, "default", pol, 4.0, seed=5)
        fins.append(res.finish.copy())
    for f in fins[1:]:
        assert np.allclose(f, fins[0], equal_nan=True, rtol=0, atol=1e-9)


@pytest.mark.parametrize("mix", ["default", "heavy"])
def test_hold_huge_M_exact_latency(mix):
    cfg = small_cfg(M_tokens=1e12, max_context=100000)
    prm = SimParams.from_cfg(cfg)
    progs = generate_workload(cfg, 0.3, mix, seed=7)
    res, _ = run_one(cfg, 0.3, mix, "ALWAYS_HOLD", None, seed=7, progs=progs)
    for g in progs:
        expect = sum(prm.p * g.new[k] + prm.d * g.dec[k] for k in range(g.K)) + sum(g.dur)
        if not np.isnan(res.finish[g.pid]):
            assert res.finish[g.pid] - g.arrival == pytest.approx(expect, abs=1e-6)
        else:
            assert g.arrival + expect > prm.horizon - 1e-6


def test_ski_rand_inverse_cdf_in_range():
    costs = Costs(1e-4, 2e-5, 4e5)
    pol = SkiRand(costs, 4.0, np.random.default_rng(0))
    taus = np.array([pol.decide(0, 10000, 1.0)[0] for _ in range(5000)])
    B = pol.B(10000)
    assert taus.min() >= 0 and taus.max() <= B
    # CDF (e^{x/B}-1)/(e-1): median at B ln((1+e)/2)
    assert np.median(taus) == pytest.approx(B * math.log((1 + math.e) / 2), rel=0.05)


def test_continuum_holds_until_warmup_then_decides():
    costs = Costs(1e-4, 2e-5, 4e5)
    pol = ContinuumTTL(costs, 4.0, 1, warmup_obs=50, refresh_every=10, grid=64)
    assert pol.decide(0, 10000, 1.0)[0] == math.inf
    rng = np.random.default_rng(0)
    for x in rng.lognormal(0, 1, 100):
        pol.observe(0, float(x))
    tau, _ = pol.decide(0, 10000, 1.0)
    assert 0.0 <= tau < math.inf
