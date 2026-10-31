"""Round 11, S1 bundle 2: the instrumented LPM runs (src/prefixmeta/r11_lpm_sim.py) and the LPM-INF prediction driver.

* simulate_instrumented with a stock policy reproduces prefixmeta.sim.simulate exactly (windows, queue and backlog traces, summary counters);
* the sticky fallback variant equals pure LPM when the threshold is never exceeded, keeps the last LPM order during a fallback pass, and is active
  (differs from nothing it should equal) only through the policy object;
* the per-turn records agree with the engine's own counters;
* the frozen endpoints carry the registered constants; the driver's plan reproduction and input checks pass on the committed tree.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from prefixmeta.policies import LpmFallback
from prefixmeta.probe import load_probe_config
from prefixmeta.r11_lpm_sim import LpmFallbackSticky, simulate_instrumented
from prefixmeta.sim import RunSpec, simulate
from prefixmeta.workload import ArrivalPlan

REPO = Path(__file__).resolve().parent.parent
SPEC = "configs/r11_predict_lpminf.yaml"


def _driver():
    spec = importlib.util.spec_from_file_location("r11_predict_lpminf", REPO / "experiments" / "r11_predict_lpminf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def drv():
    return _driver()


@pytest.fixture(scope="module")
def cfg():
    return load_probe_config(str(REPO / SPEC), REPO, None)


def _short_burst(drv, cfg, seed=0, duration=3000.0):
    """The engine-seed client plan (1.65 x, burst 200 at 1200 s) cut to ``duration`` s: the queue crosses 128 after the burst."""
    rl = cfg["r11_lpminf"]
    b = dict(rl["burst"], duration_s=duration)
    plan, rate = drv.client_plan(b, seed, float(rl["lambda_ref"]))
    return drv.plan_to_specs(plan), rate


def _same_rows(a, b) -> bool:
    """Bit-for-bit equality of two lists of window dicts (NaN equals NaN)."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.keys() != y.keys():
            return False
        for k in x:
            u, v = x[k], y[k]
            if isinstance(u, float) and isinstance(v, float) and u != u and v != v:
                continue
            if u != v:
                return False
    return True


def _rs(policy, rate, H, batching="mixed", seed=0):
    return RunSpec(exp="t", policy=policy, seed=seed, horizon_s=H, plan=ArrivalPlan(kind="constant", horizon_s=H, rate=rate),
                   engine_overrides={"batching": batching})


# ------------------------------------------------------------------ equality with the stock simulate()
@pytest.mark.parametrize("policy", ["fcfs_lru", "lpm128_lru", "lpm_lru"])
@pytest.mark.parametrize("batching", ["mixed", "separate_prefill_priority"])
def test_instrumented_run_equals_stock_simulate(drv, cfg, policy, batching):
    specs, rate = _short_burst(drv, cfg)
    a = simulate(cfg, _rs(policy, rate, 3000.0, batching), specs=specs)
    specs, rate = _short_burst(drv, cfg)
    b = simulate_instrumented(cfg, _rs(policy, rate, 3000.0, batching), specs=specs)
    assert _same_rows(a["windows"], b["windows"])
    assert a["qtrace"] == b["qtrace"]
    assert a["btrace"] == b["btrace"]
    for k in ("n_arrived", "n_sessions_done", "n_turns_done", "n_admitted", "n_hits", "max_queue", "n_passes", "n_iterations", "final_queue"):
        assert a["summary"][k] == b["summary"][k], k
    assert b["policy_stats"]["policy_class"] == {"fcfs_lru": "Fcfs", "lpm128_lru": "LpmFallback", "lpm_lru": "Lpm"}[policy]


def test_turn_records_agree_with_engine_counters(drv, cfg):
    specs, rate = _short_burst(drv, cfg)
    r = simulate_instrumented(cfg, _rs("lpm_lru", rate, 3000.0), specs=specs)
    t, s = r["turns"], r["summary"]
    assert len(t["sid"]) == s["n_admitted"]
    assert int(t["hit"].sum()) == s["n_hits"]
    assert int(np.isfinite(t["t_done"]).sum()) == s["n_turns_done"]
    wl = cfg["workload"]
    P = wl["initial_context_tokens"] + (t["turn"] - 1) * (wl["new_prompt_tokens"] + wl["decode_tokens"])
    assert (t["prompt"] == P).all()
    assert (t["cached"][t["hit"]] == P[t["hit"]] - wl["new_prompt_tokens"]).all()
    assert (t["cached"][~t["hit"]] == 0).all()
    assert (t["t_admit"] >= t["qtime"]).all() and (t["qtime"] >= t["ready"] - 1e-9).all()
    fin = np.isfinite(t["t_done"])
    assert (t["t_done"][fin] > t["t_admit"][fin]).all()
    assert len({(a, b) for a, b in zip(t["sid"], t["turn"])}) == len(t["sid"])     # each turn admitted once (full_reserve)
    # per-window admission hits from the records equal the recorder's
    for w in r["windows"]:
        m = (t["t_admit"] >= w["t_start"]) & (t["t_admit"] < w["t_end"])
        assert int(m.sum()) == w["admitted_turns"] and int(t["hit"][m].sum()) == w["hits"]


def test_pass_counter_counts_passes_over_the_threshold(drv, cfg):
    specs, rate = _short_burst(drv, cfg)
    r = simulate_instrumented(cfg, _rs("lpm_lru", rate, 3000.0), specs=specs, count_threshold=10 ** 9)
    assert r["policy_stats"]["n_passes_queue_over_threshold"] == 0
    specs, rate = _short_burst(drv, cfg)
    r = simulate_instrumented(cfg, _rs("lpm_lru", rate, 3000.0), specs=specs, count_threshold=128)
    assert r["summary"]["max_queue"] > 128 and r["policy_stats"]["n_passes_queue_over_threshold"] > 0
    assert r["policy_stats"]["n_policy_calls"] == r["summary"]["n_passes"]


# ------------------------------------------------------------------ the sticky fallback variant
def test_sticky_with_a_threshold_never_reached_equals_pure_lpm(drv, cfg):
    c2 = dict(cfg, policies=dict(cfg["policies"], big_s={"kind": "lpm_fallback", "threshold": 10 ** 9, "eviction": "lru", "sticky": True}))
    specs, rate = _short_burst(drv, cfg)
    a = simulate_instrumented(c2, _rs("big_s", rate, 3000.0), specs=specs)
    specs, rate = _short_burst(drv, cfg)
    b = simulate(cfg, _rs("lpm_lru", rate, 3000.0), specs=specs)
    assert a["policy_stats"]["policy_class"] == "LpmFallbackSticky" and a["policy_stats"]["sticky_fallback_passes"] == 0
    assert _same_rows(a["windows"], b["windows"]) and a["qtrace"] == b["qtrace"]


def test_sticky_variant_is_built_only_by_the_instrumented_run(drv, cfg):
    specs, rate = _short_burst(drv, cfg)
    r = simulate_instrumented(cfg, _rs("lpm128s_lru", rate, 3000.0), specs=specs)
    assert r["policy_stats"]["policy_class"] == "LpmFallbackSticky"
    assert r["policy_stats"]["sticky_fallback_passes"] > 0 and r["policy_stats"]["sticky_lpm_passes"] > 0
    # the stock simulate() ignores `sticky` and builds the stock fallback (documented; the driver never calls it for lpm128s)
    from prefixmeta.policies import make_policy
    assert isinstance(make_policy(cfg["policies"]["lpm128s_lru"]), LpmFallback)


class _Req:
    def __init__(self, rid, sid, qtime):
        self.rid, self.sid, self.qtime, self.alive, self.mark = rid, sid, qtime, True, -1


class _View:
    """Minimal policy view: FIFO by qtime; resident = dict sid -> cached prefix."""

    def __init__(self, reqs, resident):
        self.reqs, self.resident, self.pass_id = reqs, resident, 0

    @property
    def n_waiting(self):
        return sum(r.alive for r in self.reqs)

    def fifo_iter(self):
        return (r for r in sorted(self.reqs, key=lambda r: r.qtime) if r.alive)

    def resident_waiting(self, skip_marked=False):
        out = sorted((r for r in self.reqs if r.alive and r.sid in self.resident), key=lambda r: (-self.resident[r.sid], r.qtime, r.rid))
        for r in out:
            r.mark = self.pass_id
        return out


def test_sticky_fallback_keeps_the_last_lpm_order_then_appends_arrivals():
    reqs = [_Req(i, i, float(i)) for i in range(5)]
    view = _View(reqs, resident={3: 500, 1: 900})
    pol = LpmFallbackSticky(threshold=5)
    view.pass_id = 1
    assert [r.rid for r in pol.candidates(view, 0.0)] == [1, 3, 0, 2, 4]          # LPM pass (5 waiting, not > 5)
    reqs[1].alive = False                                                          # admitted
    reqs += [_Req(5, 5, 5.0), _Req(6, 6, 6.0)]
    view.resident = {6: 10_000, 3: 500}                                            # a new hit arrives: LPM would put it first
    view.pass_id = 2
    got = [r.rid for r in pol.candidates(view, 0.0)]                               # 6 waiting > 5: fallback keeps the old order
    assert got == [3, 0, 2, 4, 5, 6]
    stock = LpmFallback(threshold=5)
    for r in reqs:
        r.mark = -1
    view.pass_id = 3
    assert [r.rid for r in stock.candidates(view, 0.0)] == [0, 2, 3, 4, 5, 6]      # the stock variant: plain FIFO
    assert pol.n_fallback_passes == 1 and pol.n_lpm_passes == 1


# ------------------------------------------------------------------ frozen endpoints and driver checks
def test_frozen_endpoints_carry_the_registered_constants():
    ep = yaml.safe_load((REPO / "configs/r11_lpminf_predict.yaml").read_text())
    pre = yaml.safe_load((REPO / "configs/agentload_prereg_2026-10-24.yaml").read_text())
    pr, tv = pre["pass_rule"], ep["secondaries"]["trap_v2"]
    assert ep["status"] == "FROZEN"
    for k in ("rate_estimator", "rate_tolerance", "slope_frac", "recovered_hit_above", "recovered_backlog_below", "recovered_backlog_metric",
              "end_window_s", "eval_from_s", "min_eval_s", "slope_dt_s", "hit_metric", "cached_frac_threshold"):
        assert tv[k] == pr[k], k
    assert tv["uncached_tokens_ref"] == pre["measured"]["all_miss_uncached_tokens_per_s"]
    assert ep["cell"]["lambda_ref"] == pre["measured"]["lambda_ref"]
    assert ep["primary"]["window_s"] == [ep["cell"]["burst_t_s"] + pr["eval_from_s"], ep["cell"]["duration_s"]]
    assert ep["primary"]["collapse_hit_below"] == 0.05 and ep["primary"]["hit_metric"] == "token_hit_rate"
    assert ep["cell"]["seeds"] == [0, 1, 2] and ep["cell"]["lambda_mult"] == 1.65 and ep["cell"]["kv_tokens"] == 300000


def test_driver_input_checks_and_plan_reproduction(drv, cfg):
    rl = cfg["r11_lpminf"]
    ep = yaml.safe_load((REPO / rl["endpoints"]).read_text())
    drv.check_inputs(cfg, rl, ep)                       # raises SystemExit on any mismatch
    if not all((REPO / c["dir"] / "plan.csv").exists() for c in rl["plan_checks"]):
        pytest.skip("committed plan.csv not readable here (Windows MAX_PATH in a deep scratch clone; the driver has --plan-root)")
    pc = drv.plan_checks(rl, REPO)
    assert len(pc) == 6 and pc["exact"].all() and pc["rate_equal"].all() and (pc["n_burst"] == 200).all()


def test_decision_rule_on_seeds_0_and_1(drv):
    import pandas as pd
    mk = lambda c: pd.DataFrame({"seed": [0, 1, 2], "collapse": c})
    assert drv.decision(mk([False, False, True]), [0, 1]) == "consistent"
    assert drv.decision(mk([True, True, False]), [0, 1]) == "against"
    assert drv.decision(mk([True, False, False]), [0, 1]) == "inconclusive"
    assert drv.decision(pd.DataFrame({"seed": [0, 2], "collapse": [False, False]}), [0, 1]) == "inconclusive"


def test_sessions_in_system_bins_step_function(drv):
    arrival = np.array([0.0, 5.0, 25.0])
    n_turns = np.array([1, 1, 1])
    t = {"sid": np.array([0, 1, 2]), "turn": np.array([1, 1, 1]), "t_done": np.array([15.0, np.nan, 28.0])}
    mids, means = drv.sessions_in_system_bins(arrival, n_turns, t, 30.0, 10.0)
    assert list(mids) == [5.0, 15.0, 25.0]
    assert list(means) == pytest.approx([1.5, 1.5, 1.3])   # [0,10): 1 then 2 from 5 s; [10,20): 2 until 15, then 1; [20,30): 1, 2 on [25,28)
