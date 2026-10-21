"""Round-4 tests: the closed-population mode against its definition, the measurement, the registered design (config vs
pre-registration, verbatim predictions), the experiment specs, the evaluator on synthetic data with known answers, and a quick
end-to-end smoke of the CLI in a temporary results root."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r4_eval as E
from prefixmeta.engine import Engine
from prefixmeta.mech_runner import load_mech_config, scaled_engine_overrides
from prefixmeta.r4_runner import (burst_counts, burst_specs, cap_cells, cap_specs, closed_spec, curve_specs, curve_table,
                                  main, point_metrics, round_half_up, scaled_population)
from prefixmeta.sim import RunSpec, build_engine, deep_update, load_config, simulate
from prefixmeta.workload import ArrivalPlan, WorkloadParams, build_specs, length_biased_session_cap

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "configs" / "prefix_meta_r4.yaml"
PREREG = REPO / "configs" / "prefix_meta_r4_prereg.yaml"
LAM_MISS = 0.047418947368421054           # results/prefix_meta_e0/20261021-005706/e0_summary.json


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_mech_config(str(CONFIG), REPO)


@pytest.fixture(scope="module")
def design() -> dict:
    return yaml.safe_load(PREREG.read_text())["preregistration"]["registered_design"]


# =========================================================================== registration vs config
VERBATIM = {
    "R1": "FCFS-LRU closed curve peaks at n* in [20, 32] and mu(n) <= 1.2 lambda_miss for all measured n >= 1.5 n*.",
    "R2": "at n = round(1.5 n*), FCFS-RANDOM mu >= 1.25 x FCFS-LRU mu (graceful degradation).",
    "R3": ("at lambda = 2 lambda_miss, the fluid-predicted critical burst b_c (from the FCFS-LRU curve) is within a factor of 2 of "
           "the empirical critical burst b_emp := smallest burst size in the sweep that leaves FCFS not recovered in >= 3/5 "
           "seeds."),
    "R4": ("for FCFS and LPM, the empirical recovery threshold from 300 cold sessions (from round-3 phase results at the 150k-s "
           "horizon; for LPM between 1.1 and 1.25 x) lies within +-15% of mu_policy(300)/lambda_miss measured here."),
    "R5": ("with a session cap N in {32, 36, 40} (all above N_lb = 28), FCFS-RANDOM or FCFS-MRU_IDLE recovers (>= 2/3 from cold "
           "300 at 2 x lambda_miss, 150k-s horizon) for at least 2 of the 3 caps, while FCFS-LRU recovers 0/3 at each."),
    "R6": ("lambda_cap(k)/mu*(k) increases with k over k in {0.5, 1, 2} (lambda_cap(k) from round-3 escape results; mu*(k) = max "
           "of the closed FCFS-LRU curve at size k measured here with the same k-scaling as round 3)."),
}


def test_prereg_has_the_six_predictions_verbatim_and_research_question_first():
    raw = yaml.safe_load(PREREG.read_text())
    assert list(raw)[0] == "research_question"
    assert list(yaml.safe_load(CONFIG.read_text()))[0] == "research_question"
    preds = raw["preregistration"]["predictions"]
    assert set(preds) == set(VERBATIM)
    for k, v in VERBATIM.items():
        assert preds[k] == v, k


def test_config_equals_the_registered_design(cfg, design):
    cv, bd, cd = cfg["curve"], cfg["burst"], cfg["cap"]
    rc = design["curve"]
    assert cv["n_grid"] == rc["n_grid"] and cv["seeds"] == rc["seeds"]
    assert cv["warmup_s"] == rc["warmup_s"] and cv["horizon_s"] == rc["horizon_s"]
    assert cv["pool_sessions_per_k"] == rc["pool_sessions_per_k"]
    assert cv["k_scaled"]["policy"] == rc["k_scaled"]["policy"] and cv["k_scaled"]["sizes"] == rc["k_scaled"]["sizes"]
    assert cv["k_scaled"]["n_rounding"] == rc["k_scaled"]["n_rounding"] == "half_up"
    assert cfg["metrics"]["window_s"] == design["window_s"] == 1000.0
    # policies: name -> (ordering kind, eviction)
    for name, (kind, ev) in rc["policies"].items():
        assert cfg["policies"][name]["kind"] == kind and cfg["policies"][name]["eviction"] == ev
    assert sorted(cv["policies"]) == sorted(rc["policies"])
    rb = design["burst"]
    for key in ("lam_mult", "sizes", "burst_width_s", "warmup_s", "after_s", "seeds", "recovered_hit_above",
                "recovered_backlog_below"):
        assert bd[key] == rb[key], key
    assert bd["policies"] == rb["policies"]
    rp = design["cap"]
    for key in ("lam_mult", "cold_sessions", "caps", "evictions", "seeds", "horizon_s", "recovered_hit_above",
                "recovered_backlog_below"):
        assert cd[key] == rp[key], key
    assert {e: cd["eviction_policy"][e] for e in rp["evictions"]} == {"lru": "fcfs_lru", "random": "fcfs_random",
                                                                       "mru_idle": "fcfs_mru_idle"}
    # fresh seeds: disjoint from every seed used in rounds 1-3
    old = set(range(0, 5)) | set(range(100, 120)) | set(range(1000, 1020)) | set(range(1100, 1120)) | set(range(9000, 9201))
    for seeds in (cv["seeds"], bd["seeds"], cd["seeds"]):
        assert not (set(seeds) & old)
    # N_lb of the registration is the engine's
    wl = WorkloadParams.from_dict(cfg["workload"])
    assert length_biased_session_cap(cfg["engine"]["kv_memory_tokens"], wl) == design["N_lb"] == 28
    # the E-curve measurement window is >= 30000 s
    assert cv["horizon_s"] - cv["warmup_s"] >= 30000.0
    assert cfg["parallel"]["max_workers"] <= 3


def test_registration_files_it_reads_exist_and_hold_the_registered_numbers(design):
    for ks, rel in design["r6_sources"]["lambda_cap"].items():
        df = pd.read_csv(REPO / rel)
        row = df[np.isclose(df["k"], float(ks))]
        assert len(row) == 1
        assert float(row["lambda_cap"].iloc[0]) == pytest.approx(design["r6_sources"]["lambda_cap_values_at_writing"][ks],
                                                                 abs=1e-6)
    e0 = json.loads((REPO / design["lambda_miss_source"]).read_text())
    assert e0["lambda_miss"] == pytest.approx(LAM_MISS)
    for ks, rel in design["curve"]["k_scaled"]["lambda_miss_k_source"].items():
        df = pd.read_csv(REPO / rel)
        assert len(df[np.isclose(df["k"], float(ks))]) == 1
    phase = pd.read_csv(REPO / design["r4_sources"]["phase_runs"])
    assert {"policy", "lam_mult", "recovered", "horizon_used_s"} <= set(phase.columns)


# =========================================================================== closed-population mode vs its definition
class StrictClosedEngine(Engine):
    """Engine whose per-step invariant check also asserts the closed-population definition: exactly n sessions in the system."""
    n_target = -1

    def check_invariants(self) -> None:
        super().check_invariants()
        assert self.in_system == self.n_target, (self.now, self.in_system, self.n_target)


def run_closed(cfg, policy: str, n: int, horizon: float, seed: int, *, eo=None, pool=3000, debug=True):
    plan = ArrivalPlan(kind="closed", horizon_s=horizon, closed_n=n, pool=pool)
    rs = RunSpec(exp="t", policy=policy, seed=seed, horizon_s=horizon, plan=plan, engine_overrides=eo or {}, debug=debug)
    eng, rec, _ = build_engine(cfg, rs)
    eng.__class__ = StrictClosedEngine
    eng.n_target = n
    eng.trace = []
    eng.run(horizon)
    return eng, rec


@pytest.mark.parametrize("policy,n,M", [("fcfs_lru", 12, None), ("fcfs_random", 30, 60_000), ("fcfs_mru_idle", 30, 60_000),
                                        ("lpm_lru", 30, 60_000)])
def test_closed_mode_keeps_exactly_n_sessions_and_replaces_with_cold_turn1_sessions(cfg, policy, n, M):
    eo = {"kv_memory_tokens": M} if M else {}
    eng, _ = run_closed(cfg, policy, n, 600.0, seed=4, eo=eo)
    assert eng.in_system == n and eng.max_in_system == n
    assert eng.n_sessions_done > 3, "some sessions must complete so replacement is exercised"
    # one replacement per completion, drawn in pool order (session ids n, n+1, ...)
    assert eng._next_idx == n + eng.n_sessions_done
    assert eng.n_arrived == n + eng.n_sessions_done
    first: Dict[int, tuple] = {}
    for x in eng.trace:
        if x[0] == "A":
            first.setdefault(x[1], (x[2], x[3]))
    assert all(turn == 1 and hit is False for turn, hit in first.values())      # first admission of every session: cold turn 1
    assert sorted(first) == list(range(len(first)))                               # replacements enter in pool order
    assert max(first) >= n                                                        # replacements did get admitted


def test_closed_replacement_happens_at_the_completion_instant(cfg):
    """The replacement's arrival time equals the completion time of the session it replaces."""
    eng, _ = run_closed(cfg, "fcfs_lru", 10, 400.0, seed=2)
    done_t = sorted(x[3] for x in eng.trace if x[0] == "D" and x[2] == eng._nt[x[1]])
    arr = sorted(eng._arrived_t[n_] for n_ in range(10, eng._next_idx))
    assert len(done_t) == len(arr) > 0
    assert np.allclose(done_t, arr)
    assert all(eng._arrived_t[i] == 0.0 for i in range(10))


def test_measured_mu_is_the_completion_count_in_the_window_over_its_length(cfg):
    H, warm, W = 6000.0, 2000.0, 1000.0
    plan = ArrivalPlan(kind="closed", horizon_s=H, closed_n=14, pool=3000)
    rs = RunSpec(exp="t", policy="fcfs_lru", seed=6, horizon_s=H, plan=plan)
    eng, rec, _ = build_engine(cfg, rs)
    eng.trace = []
    eng.run(H)
    windows = rec.finalize(eng.end_time)
    m = point_metrics(windows, warm, H, W)
    n_done = sum(1 for x in eng.trace if x[0] == "D" and x[2] == eng._nt[x[1]] and warm <= x[3] < H)
    assert m["n_sessions"] == n_done > 0
    assert m["mu"] == pytest.approx(n_done / (H - warm))
    assert m["n_windows"] == 4
    ev = sum(w["evictions"] for w in windows if w["t_start"] >= warm)
    assert m["evictions_per_s"] == pytest.approx(ev / (H - warm))
    # hit rate = hits / admissions in the window, busy fraction and resident KV are in range
    assert 0.0 <= m["hit_rate"] <= 1.0 and 0.0 < m["gpu_busy"] <= 1.0
    assert m["resident_kv_tokens"] == pytest.approx(m["reserved_tokens"] + m["idle_tokens"])
    assert 0 < m["resident_kv_tokens"] <= cfg["engine"]["kv_memory_tokens"]


def test_littles_law_holds_for_the_closed_population(cfg):
    """n = mu x (mean time in system of completed sessions): a stationarity / bookkeeping check of the closed mode."""
    H, warm, n = 40000.0, 10000.0, 16
    plan = ArrivalPlan(kind="closed", horizon_s=H, closed_n=n, pool=6000)
    rs = RunSpec(exp="t", policy="fcfs_lru", seed=1, horizon_s=H, plan=plan)
    eng, rec, _ = build_engine(cfg, rs)
    eng.trace = []
    eng.run(H)
    life = [x[3] - eng._arrived_t[x[1]] for x in eng.trace if x[0] == "D" and x[2] == eng._nt[x[1]] and warm <= x[3] < H]
    mu = len(life) / (H - warm)
    assert len(life) > 300
    assert mu * float(np.mean(life)) == pytest.approx(n, rel=0.12)


def test_closed_pool_exhaustion_is_an_error_not_a_silent_open_system(cfg):
    plan = ArrivalPlan(kind="closed", horizon_s=2000.0, closed_n=10, pool=12)
    with pytest.raises(RuntimeError):
        simulate(cfg, RunSpec(exp="t", policy="fcfs_lru", seed=0, horizon_s=2000.0, plan=plan))


def test_point_metrics_rejects_an_incomplete_measurement_window():
    w = [{"t_start": 1000.0 * i, "sessions_per_s": 0.05, "turns_per_s": 0.5, "admitted_turns": 10, "hits": 5,
          "busy_frac": 1.0, "reserved_mean": 1.0, "idle_mean": 2.0, "evictions": 3} for i in range(5)]
    assert point_metrics(w, 2000.0, 5000.0, 1000.0)["mu"] == pytest.approx(0.05)
    with pytest.raises(ValueError):
        point_metrics(w, 2000.0, 6000.0, 1000.0)
    m = point_metrics(w, 1000.0, 5000.0, 1000.0)
    assert m["mu_first_half"] == m["mu_second_half"] == pytest.approx(0.05) and m["evictions_per_s"] == pytest.approx(0.003)


# =========================================================================== experiment specs
def test_scaled_population_is_round_half_up_not_bankers():
    assert round_half_up(22.5) == 23 and round(22.5) == 22
    assert scaled_population(45, 0.5) == 23 and scaled_population(22, 0.5) == 11 and scaled_population(4, 0.5) == 2
    assert scaled_population(300, 2.0) == 600 and scaled_population(1, 0.5) == 1
    ns = [scaled_population(n, 0.5) for n in [4, 8, 12, 16, 20, 22, 24, 26, 28, 30, 32, 34, 36, 40, 45, 50, 60, 80, 100, 150, 200, 300]]
    assert len(set(ns)) == len(ns)                                    # the half-scaled grid has no duplicates


def test_curve_specs_cover_the_registered_grid_with_shared_seeds(cfg, design):
    cv = cfg["curve"]
    specs = curve_specs(cfg, cv)
    n_main = len(cv["policies"]) * len(cv["n_grid"]) * len(cv["seeds"])
    n_k = len(cv["k_scaled"]["sizes"]) * len(cv["n_grid"]) * len(cv["seeds"])
    assert len(specs) == n_main + n_k == 4 * 22 * 3 + 2 * 22 * 3
    assert {s.seed for s in specs} == set(design["curve"]["seeds"])
    for s in specs:
        assert s.plan.kind == "closed" and s.horizon_s == 35000.0 and s.exp == "r4_curve"
    ks = [s for s in specs if s.meta["k"] != 1.0]
    assert {s.policy for s in ks} == {"fcfs_lru"}
    s2 = next(s for s in ks if s.meta["k"] == 2.0 and s.meta["n_nominal"] == 30)
    assert s2.plan.closed_n == 60 and s2.plan.pool == 60000
    assert s2.engine_overrides == scaled_engine_overrides(cfg["engine"], 2.0)
    assert s2.engine_overrides["kv_memory_tokens"] == 600_000 and s2.engine_overrides["max_running_seqs"] == 512
    s05 = next(s for s in ks if s.meta["k"] == 0.5 and s.meta["n_nominal"] == 45)
    assert s05.plan.closed_n == 23 and s05.plan.pool == 15000
    # same seed and same n: the workload is identical for every policy (CRN)
    wl = WorkloadParams.from_dict(cfg["workload"])
    a = [s for s in specs if s.meta["k"] == 1.0 and s.meta["n_nominal"] == 24 and s.seed == 2000]
    assert {s.policy for s in a} == set(cv["policies"])
    base = build_specs(wl, a[0].plan, 2000)
    for s in a[1:]:
        o = build_specs(wl, s.plan, s.seed)
        assert np.array_equal(base.n_turns, o.n_turns) and np.array_equal(base.tool_flat, o.tool_flat)


def test_without_memory_pressure_all_policies_see_the_same_workload_and_agree(cfg):
    """n = 8 never exceeds memory: no eviction and no queue, so every policy is identical (checks the CRN plumbing)."""
    res = {}
    for pol in cfg["curve"]["policies"]:
        r = simulate(cfg, closed_spec(pol, 8, 1.0, 5, {**cfg["curve"], "horizon_s": 4000.0}, cfg["engine"]))
        res[pol] = (r["summary"]["n_sessions_done"], r["summary"]["n_hits"], r["summary"]["n_admitted"],
                    r["summary"]["n_evictions"])
    assert len(set(res.values())) == 1 and next(iter(res.values()))[3] == 0


def test_burst_and_cap_specs_follow_the_registration(cfg, design):
    bd, cd = cfg["burst"], cfg["cap"]
    bs = burst_specs(cfg, bd, LAM_MISS)
    assert len(bs) == 2 * 9 * 5
    assert {s.policy for s in bs} == {"fcfs_lru", "fcfs_random"}
    for s in bs:
        assert s.horizon_s == 65000.0 and s.plan.kind == "constant" and s.plan.rate == pytest.approx(2 * LAM_MISS)
        assert s.plan.burst_t0 == 5000.0 and s.plan.burst_width_s == 60.0 and s.plan.initial_cold == 0
        assert s.stop_queue_above is None and s.stop_backlog_above is None          # no early stop
    assert sorted({s.plan.burst_n for s in bs}) == design["burst"]["sizes"]
    cs = cap_specs(cfg, cd, LAM_MISS)
    assert len(cs) == 5 * 3 * 3
    for s in cs:
        assert s.horizon_s == 150000.0 and s.plan.initial_cold == 300 and s.plan.rate == pytest.approx(2 * LAM_MISS)
        assert s.session_cap_override == s.meta["cap"]
    assert {(s.policy, s.meta["cap"]) for s in cs} == {(p, c) for p in ("fcfs_lru", "fcfs_random", "fcfs_mru_idle")
                                                       for c in (24, 28, 32, 36, 40)}


# =========================================================================== evaluator on synthetic data with known answers
GRID = [4, 8, 12, 16, 20, 22, 24, 26, 28, 30, 32, 34, 36, 40, 45, 50, 60, 80, 100, 150, 200, 300]
LRU = [0.045, 0.0863, 0.125, 0.1627, 0.168, 0.170, 0.1694, 0.145, 0.1048, 0.082, 0.0656, 0.0560, 0.0520, 0.0487, 0.0478,
       0.0474, 0.0473, 0.0474, 0.0474, 0.0476, 0.0478, 0.0481]
RND = [0.045, 0.0863, 0.125, 0.1627, 0.168, 0.170, 0.1694, 0.160, 0.150, 0.138, 0.125, 0.110, 0.100, 0.085, 0.075, 0.070,
       0.062, 0.055, 0.052, 0.050, 0.049, 0.049]
SEEDS = [2000, 2001, 2002]


def synth_curve_runs(curves: Dict[tuple, List[float]], scale_seed: float = 0.01) -> pd.DataFrame:
    rows = []
    for (pol, k), mu in curves.items():
        for n, m in zip(GRID, mu):
            for j, sd in enumerate(SEEDS):
                rows.append({"policy": pol, "k": k, "n_nominal": n, "n": n, "seed": sd,
                             "mu": m * (1 + scale_seed * (j - 1))})
    return pd.DataFrame(rows)


def base_curves(mru_like_random: bool = True) -> Dict[tuple, List[float]]:
    return {("fcfs_lru", 1.0): LRU, ("lpm_lru", 1.0): [m * 1.1 for m in LRU], ("fcfs_random", 1.0): RND,
            ("fcfs_mru_idle", 1.0): RND if mru_like_random else LRU,
            ("fcfs_lru", 0.5): [m * 0.5 for m in LRU], ("fcfs_lru", 2.0): [m * 2.05 for m in LRU]}


def burst_df(counts_lru: List[int], counts_rnd: List[int], sizes=(10, 20, 30, 40, 50, 60, 80, 100, 150)) -> pd.DataFrame:
    rows = []
    for pol, counts in (("fcfs_lru", counts_lru), ("fcfs_random", counts_rnd)):
        for b, c in zip(sizes, counts):
            for j, sd in enumerate([2100, 2101, 2102, 2103, 2104]):
                rows.append({"policy": pol, "burst_n": b, "seed": sd, "recovered": j >= c})      # first c seeds not recovered
    return pd.DataFrame(rows)


def cap_df(table: Dict[tuple, int]) -> pd.DataFrame:
    """table[(eviction, cap)] = number of recovered seeds of 3."""
    rows = []
    for ev in ("lru", "random", "mru_idle"):
        for cap in (24, 28, 32, 36, 40):
            for j, sd in enumerate([2200, 2201, 2202]):
                rows.append({"eviction": ev, "cap": cap, "seed": sd, "recovered": j < table.get((ev, cap), 0)})
    return pd.DataFrame(rows)


def phase_df(counts: Dict[str, Dict[float, int]], horizon: float = 150000.0) -> pd.DataFrame:
    rows = []
    for pol, d in counts.items():
        for m, c in d.items():
            for j in range(3):
                rows.append({"policy": pol, "lam_mult": m, "recovered": j < c, "horizon_used_s": horizon})
    return pd.DataFrame(rows)


PHASE = phase_df({"fcfs": {0.6: 3, 0.8: 3, 0.9: 3, 1.0: 0, 1.1: 0, 1.25: 0},
                  "lpm": {0.6: 3, 0.8: 3, 0.9: 3, 1.0: 3, 1.1: 3, 1.25: 0}})
LAMCAP = {0.5: 0.033386, 1.0: 0.114102, 2.0: 0.295825}


def by_id(rows) -> Dict[str, dict]:
    return {r["id"]: r for r in rows}


def test_headline_rows_come_first_and_all_six_are_present(design):
    cr = synth_curve_runs(base_curves())
    rows = E.evaluate_all(cr, burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), cap_df({}), PHASE, LAMCAP, LAM_MISS, design)
    assert [r["id"] for r in rows[:6]] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert all(r["reading"] == "headline" for r in rows[:6]) and all(r["reading"] != "headline" for r in rows[6:])
    assert len({r["id"] for r in rows}) == len(rows)


def test_r1_pass_and_fail_clauses(design):
    r, n_star = E.eval_r1(synth_curve_runs(base_curves()), LAM_MISS, design)
    assert r["verdict"] == E.PASS and n_star == 22
    assert r["numbers"]["clause_peak_in_[20,32]"] and r["numbers"]["clause_tail_le_1.2_lambda_miss"]
    # a peak outside [20, 32]
    shifted = LRU.copy()
    shifted[GRID.index(12)] = 0.2
    r, n_star = E.eval_r1(synth_curve_runs({("fcfs_lru", 1.0): shifted}), LAM_MISS, design)
    assert n_star == 12 and r["verdict"] == E.FAIL and not r["numbers"]["clause_peak_in_[20,32]"]
    # tail above 1.2 lambda_miss at n >= 1.5 n* = 33  (n = 34 is the first)
    fat = LRU.copy()
    fat[GRID.index(34)] = 1.21 * LAM_MISS
    r, _ = E.eval_r1(synth_curve_runs({("fcfs_lru", 1.0): fat}), LAM_MISS, design)
    assert r["verdict"] == E.FAIL and r["numbers"]["tail_violators"] == [34]
    # exactly 1.2 lambda_miss is allowed (<=); n = 32 < 33 is outside the tail set
    ok = LRU.copy()
    ok[GRID.index(34)] = 1.2 * LAM_MISS
    ok[GRID.index(32)] = 5 * LAM_MISS
    assert E.eval_r1(synth_curve_runs({("fcfs_lru", 1.0): ok}, scale_seed=0.0), LAM_MISS, design)[0]["verdict"] == E.PASS
    # a missing registered cell -> NOT_EVALUABLE, never a partial verdict
    cr = synth_curve_runs(base_curves())
    cr = cr[~((cr["policy"] == "fcfs_lru") & (cr["n_nominal"] == 26) & (cr["seed"] == 2001))]
    assert E.eval_r1(cr, LAM_MISS, design)[0]["verdict"] == E.NA


def test_r2_uses_interpolation_at_round_half_up_1p5_n_star(design):
    cr = synth_curve_runs(base_curves(), scale_seed=0.0)
    r1, n_star = E.eval_r1(cr, LAM_MISS, design)
    assert n_star == 22
    r2 = E.eval_r2(cr, n_star, design)
    n_r2 = 33
    mu_l = np.interp(n_r2, GRID, LRU)
    mu_r = np.interp(n_r2, GRID, RND)
    assert r2["numbers"]["n_R2"] == n_r2 and not r2["numbers"]["on_grid"]
    assert r2["numbers"]["mu_lru"] == pytest.approx(mu_l) and r2["numbers"]["mu_fcfs_random"] == pytest.approx(mu_r)
    assert r2["numbers"]["ratio"] == pytest.approx(mu_r / mu_l)
    assert r2["verdict"] == (E.PASS if mu_r >= 1.25 * mu_l else E.FAIL) == E.PASS
    near = E.eval_r2(cr, n_star, design, pid="R2-nearest-grid", reading="sensitivity", nearest=True)
    assert near["numbers"]["evaluated_at_n"] == 34                      # |33-32| = |33-34|: ties go to the larger n
    info = E.eval_r2(cr, n_star, design, other="fcfs_mru_idle", pid="R2-MRU", reading="information", informational=True)
    assert info["verdict"] == E.INFO
    # RANDOM only 1.2x LRU at n_R2 -> FAIL
    weak = [m * 1.2 if n >= 28 else m for n, m in zip(GRID, LRU)]
    cr2 = synth_curve_runs({("fcfs_lru", 1.0): LRU, ("fcfs_random", 1.0): weak}, scale_seed=0.0)
    assert E.eval_r2(cr2, 22, design)["verdict"] == E.FAIL
    # exactly 1.25x passes (>=): tail of RND = 1.25 x LRU on [28, 36]
    edge = [m * 1.25 if 28 <= n <= 36 else m for n, m in zip(GRID, LRU)]
    cr3 = synth_curve_runs({("fcfs_lru", 1.0): LRU, ("fcfs_random", 1.0): edge}, scale_seed=0.0)
    assert E.eval_r2(cr3, 22, design)["verdict"] == E.PASS
    assert E.eval_r2(cr, None, design)["verdict"] == E.NA


def test_empirical_critical_burst_and_censoring():
    sizes = [10, 20, 30, 40, 50, 60, 80, 100, 150]
    n5 = [5] * 9
    assert E.empirical_critical_burst(sizes, [0, 1, 2, 3, 4, 5, 5, 5, 5], n5) == (40, "found")
    assert E.empirical_critical_burst(sizes, [0, 0, 3, 0, 0, 0, 0, 0, 0], n5) == (30, "found")      # not required monotone
    assert E.empirical_critical_burst(sizes, [3, 4, 5, 5, 5, 5, 5, 5, 5], n5) == (10, "left_censored")
    assert E.empirical_critical_burst(sizes, [0, 0, 0, 0, 0, 0, 2, 2, 2], n5) == (None, "right_censored")


def r3_with(design, counts, curves=None):
    cr = synth_curve_runs(curves or base_curves(), scale_seed=0.0)
    return E.eval_r3(cr, burst_df(counts, [0] * 9), LAM_MISS, design)


def test_r3_within_factor_two_and_censoring_rules(design):
    # fluid b_c for the synthetic LRU curve at 2 lambda_miss: n1 and n2 by hand
    lam = 2 * LAM_MISS
    n1 = 8 + (lam - 0.0863) / (0.125 - 0.0863) * 4
    n2 = 28 + (0.1048 - lam) / (0.1048 - 0.082) * 2
    r = r3_with(design, [0, 1, 3, 3, 4, 5, 5, 5, 5])                    # b_emp = 30
    assert r["numbers"]["fluid"]["kind"] == "bistable"
    assert r["numbers"]["fluid"]["b_c"] == pytest.approx(n2 - n1)
    assert r["numbers"]["b_emp"] == 30 and r["numbers"]["b_emp_status"] == "found"
    assert 0.5 <= (n2 - n1) / 30 <= 2 and r["verdict"] == E.PASS
    assert r3_with(design, [0, 0, 0, 0, 0, 3, 5, 5, 5])["verdict"] == E.FAIL       # b_emp = 60: b_c/b_emp = 0.33
    assert r3_with(design, [0, 0, 0, 0, 0, 0, 0, 0, 0])["verdict"] == E.FAIL       # right-censored, b_c ~ 20 < 75
    # left-censored (the smallest size already has >= 3/5 not recovered): FAIL iff b_c > 2 x 10, else NOT_EVALUABLE
    rr = r3_with(design, [4, 5, 5, 5, 5, 5, 5, 5, 5])
    assert rr["numbers"]["b_emp_status"] == "left_censored" and rr["numbers"]["b_emp"] == 10
    assert rr["numbers"]["fluid"]["b_c"] == pytest.approx(n2 - n1) and n2 - n1 < 20
    assert rr["verdict"] == E.NA
    wide = r3_with(design, [4, 5, 5, 5, 5, 5, 5, 5, 5], {("fcfs_lru", 1.0): RND})          # b_c ~ 28.5 > 20
    assert wide["numbers"]["fluid"]["b_c"] > 20 and wide["verdict"] == E.FAIL
    # right-censored with a large b_c: cannot be established -> NOT_EVALUABLE (FAIL only if b_c < 75)
    graceful = [m if n < 34 else (0.12 if n <= 60 else 0.11 if n == 80 else 0.09 if n == 100 else 0.06)
                for n, m in zip(GRID, RND)]
    far = r3_with(design, [0] * 9, {("fcfs_lru", 1.0): graceful})
    assert far["numbers"]["b_emp_status"] == "right_censored" and far["numbers"]["fluid"]["b_c"] > 75
    assert far["verdict"] == E.NA
    assert r3_with(design, [0] * 9, {("fcfs_lru", 1.0): RND})["verdict"] == E.FAIL         # b_c ~ 28.5 < 75
    # monostable (lambda <= mu_inf) -> FAIL when b_emp is finite
    high_tail = [m if n <= 28 else 0.1 for n, m in zip(GRID, LRU)]                  # unimodal, tail 0.1 > lambda = 0.0948
    r = r3_with(design, [0, 1, 3, 3, 4, 5, 5, 5, 5], {("fcfs_lru", 1.0): high_tail})
    assert r["numbers"]["fluid"]["kind"] == "monostable" and r["verdict"] == E.FAIL
    # overload (lambda > mu*) -> FAIL
    low = [0.5 * m for m in LRU]
    r = r3_with(design, [0, 1, 3, 3, 4, 5, 5, 5, 5], {("fcfs_lru", 1.0): low})
    assert r["numbers"]["fluid"]["kind"] == "overload" and r["verdict"] == E.FAIL
    # the raw-PL sensitivity is a separate row id
    raw = E.eval_r3(synth_curve_runs(base_curves(), scale_seed=0.0), burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9),
                    LAM_MISS, design, unimodal=False, pid="R3-raw", reading="sensitivity")
    assert raw["id"] == "R3-raw" and raw["reading"] == "sensitivity"
    # missing burst runs / seeds -> NOT_EVALUABLE
    assert E.eval_r3(synth_curve_runs(base_curves()), None, LAM_MISS, design)["verdict"] == E.NA
    bd = burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9)
    bd = bd[~((bd["policy"] == "fcfs_lru") & (bd["burst_n"] == 50) & (bd["seed"] == 2103))]
    assert E.eval_r3(synth_curve_runs(base_curves()), bd, LAM_MISS, design)["verdict"] == E.NA


def test_phase_threshold_matches_the_round3_file_and_the_registered_brackets(design):
    real = pd.read_csv(REPO / design["r4_sources"]["phase_runs"])
    mh = design["r4_sources"]["min_horizon_s"]
    f = E.phase_threshold(real, "fcfs", mh)
    l = E.phase_threshold(real, "lpm", mh)
    assert (f["lo"], f["hi"]) == (0.9, 1.0) and (l["lo"], l["hi"]) == (1.1, 1.25)
    assert E.phase_threshold(PHASE, "fcfs", mh)["ok"]
    # short-horizon rows are ignored; a policy that never fails within the 150k multiples has no bracket
    assert not E.phase_threshold(phase_df({"fcfs": {0.9: 3, 1.0: 3}}), "fcfs", mh)["ok"]
    assert not E.phase_threshold(phase_df({"fcfs": {0.9: 0, 1.0: 0}}), "fcfs", mh)["ok"]
    assert not E.phase_threshold(phase_df({"fcfs": {0.9: 3, 1.0: 0}}, horizon=30000.0), "fcfs", mh)["ok"]


def test_r4_headline_midpoint_and_strict_lenient_sensitivities(design):
    # FCFS bracket (0.9, 1.0], mid 0.95: allowed r in [0.8075, 1.0925]; LPM (1.1, 1.25], mid 1.175: [0.99875, 1.35125]
    def runs(r_fcfs, r_lpm):
        mu300_f, mu300_l = r_fcfs * LAM_MISS, r_lpm * LAM_MISS
        f = [m if n != 300 else mu300_f for n, m in zip(GRID, LRU)]
        l = [m if n != 300 else mu300_l for n, m in zip(GRID, LRU)]
        return synth_curve_runs({("fcfs_lru", 1.0): f, ("lpm_lru", 1.0): l}, scale_seed=0.0)
    rows = by_id(E.eval_r4(runs(1.014, 1.16), PHASE, LAM_MISS, design))
    assert rows["R4"]["verdict"] == rows["R4-strict"]["verdict"] == rows["R4-lenient"]["verdict"] == E.PASS
    nums = rows["R4"]["numbers"]
    assert nums["FCFS"]["t_mid"] == pytest.approx(0.95) and nums["LPM"]["t_mid"] == pytest.approx(1.175)
    assert nums["LPM"]["r_pred"] == pytest.approx(1.16)
    # r_LPM = 1.40: outside mid +-15% and outside strict, inside lenient [0.935, 1.4375]
    rows = by_id(E.eval_r4(runs(1.014, 1.40), PHASE, LAM_MISS, design))
    assert (rows["R4"]["verdict"], rows["R4-strict"]["verdict"], rows["R4-lenient"]["verdict"]) == (E.FAIL, E.FAIL, E.PASS)
    # r_FCFS = 1.06: inside mid band (<= 1.0925) but outside strict (<= 1.035)
    rows = by_id(E.eval_r4(runs(1.06, 1.16), PHASE, LAM_MISS, design))
    assert (rows["R4"]["verdict"], rows["R4-strict"]["verdict"], rows["R4-lenient"]["verdict"]) == (E.PASS, E.FAIL, E.PASS)
    assert all(r["verdict"] == E.NA for r in E.eval_r4(runs(1.0, 1.0), None, LAM_MISS, design))


def test_r5_best_single_rule_vs_union_and_lru_clause(design):
    base = {("random", 32): 3, ("random", 36): 2, ("random", 40): 0, ("mru_idle", 32): 0, ("mru_idle", 36): 3,
            ("mru_idle", 40): 3}
    rows = by_id(E.eval_r5(cap_df(base), design))
    assert rows["R5"]["numbers"]["caps_recovered_per_rule"] == {"random": 2, "mru_idle": 2}
    assert rows["R5"]["verdict"] == E.PASS and rows["R5-union"]["verdict"] == E.PASS
    assert rows["R5"]["numbers"]["caps_recovered_union"] == 3
    # each rule recovers at one cap only: headline FAILS, union (2 caps) passes
    split = {("random", 32): 3, ("mru_idle", 36): 3}
    rows = by_id(E.eval_r5(cap_df(split), design))
    assert rows["R5"]["verdict"] == E.FAIL and rows["R5-union"]["verdict"] == E.PASS
    # "recovers" needs >= 2 of 3 seeds
    rows = by_id(E.eval_r5(cap_df({("random", 32): 1, ("random", 36): 1, ("random", 40): 1}), design))
    assert rows["R5"]["verdict"] == E.FAIL
    # LRU must be 0/3 at each of 32, 36, 40 (a single recovered seed breaks it); caps 24 / 28 do not count
    rows = by_id(E.eval_r5(cap_df({**base, ("lru", 40): 1}), design))
    assert rows["R5"]["verdict"] == E.FAIL
    rows = by_id(E.eval_r5(cap_df({**base, ("lru", 24): 3, ("lru", 28): 2}), design))
    assert rows["R5"]["verdict"] == E.PASS
    # a missing seed -> NOT_EVALUABLE
    d = cap_df(base)
    d = d[~((d["eviction"] == "random") & (d["cap"] == 36) & (d["seed"] == 2202))]
    assert by_id(E.eval_r5(d, design))["R5"]["verdict"] == E.NA
    assert by_id(E.eval_r5(None, design))["R5"]["verdict"] == E.NA


def test_r6_strictly_increasing_ratio(design):
    r = E.eval_r6(synth_curve_runs(base_curves(), scale_seed=0.0), LAMCAP, design)
    mu = {k: max(LRU) * f for k, f in ((0.5, 0.5), (1.0, 1.0), (2.0, 2.05))}
    assert r["numbers"]["k=1.0"]["mu_star"] == pytest.approx(mu[1.0])
    assert r["numbers"]["k=0.5"]["rho"] == pytest.approx(LAMCAP[0.5] / mu[0.5])
    assert r["numbers"]["k=2.0"]["argmax_n_actual"] == 44
    assert r["verdict"] == E.PASS
    flat = dict(LAMCAP)
    flat[2.0] = 0.3 * 2.05 * max(LRU) * 0.5                 # rho(2) below rho(1) -> FAIL
    assert E.eval_r6(synth_curve_runs(base_curves(), scale_seed=0.0), flat, design)["verdict"] == E.FAIL
    eq = {0.5: 0.5 * max(LRU) * 0.5, 1.0: 1.0 * max(LRU) * 0.5, 2.0: 2.05 * max(LRU) * 0.5}          # equal ratios: not strictly increasing
    assert E.eval_r6(synth_curve_runs(base_curves(), scale_seed=0.0), eq, design)["verdict"] == E.FAIL
    cr = synth_curve_runs(base_curves())
    assert E.eval_r6(cr[cr["k"] != 2.0], LAMCAP, design)["verdict"] == E.NA
    assert E.eval_r6(cr, None, design)["verdict"] == E.NA


def test_rows_to_frame_is_json_clean(design):
    cr = synth_curve_runs(base_curves())
    rows = E.evaluate_all(cr, burst_df([0, 1, 3, 3, 4, 5, 5, 5, 5], [0] * 9), cap_df({}), PHASE, LAMCAP, LAM_MISS, design)
    df = E.rows_to_frame(rows)
    assert list(df.columns) == ["id", "reading", "verdict", "claim", "numbers", "notes"]
    for s in df["numbers"]:
        json.loads(s)


# =========================================================================== CLI smoke (quick sizes, temporary results root)
def run_cli(tmp_path, *argv) -> Path:
    before = {p for p in tmp_path.rglob("*") if p.is_dir()}
    main(list(argv) + ["--config", str(CONFIG), "--out-root", str(tmp_path), "--workers", "1"], repo_dir=REPO)
    new = [p for p in tmp_path.rglob("*") if p.is_dir() and p not in before and (p / "meta.json").exists()]
    assert len(new) == 1
    return new[0]


def test_quick_pipeline_end_to_end_writes_provenance_and_never_overwrites(tmp_path):
    cdir = run_cli(tmp_path, "curve", "--quick")
    meta = json.loads((cdir / "meta.json").read_text())
    assert meta["status"] == "done" and meta["quick"] is True
    assert meta["git"]["commit"] and isinstance(meta["git"]["dirty"], bool)
    assert meta["hardware"] == "Apple M3 Max CPU (simulation)" and meta["hostname"]
    assert meta["seeds"] == [7000] and meta["start_time"] <= meta["end_time"]
    assert {"python", "numpy", "pandas"} <= set(meta["versions"])
    for f in ("config.yaml", "base_config.yaml", "config_effective.yaml", "preregistration.yaml", "runs.csv", "windows.csv",
              "curve_runs.csv", "curve_table.csv"):
        assert (cdir / f).exists(), f
    assert (cdir / "config.yaml").read_text() == CONFIG.read_text()
    assert (cdir / "preregistration.yaml").read_text() == PREREG.read_text()
    ct = pd.read_csv(cdir / "curve_table.csv")
    assert set(ct["policy"]) == {"fcfs_lru", "lpm_lru", "fcfs_random", "fcfs_mru_idle"}
    assert set(ct["k"]) == {0.5, 1.0}
    cr = pd.read_csv(cdir / "curve_runs.csv")
    assert (cr["mu"] > 0).all() and (cr["n_windows"] == 3).all()
    runs = pd.read_csv(cdir / "runs.csv")
    assert set(runs["eviction"]) == {"lru", "random", "mru_idle"}
    first_files = {p.name: p.stat().st_mtime_ns for p in cdir.iterdir()}

    bdir = run_cli(tmp_path, "burst", "--quick")
    br = pd.read_csv(bdir / "runs.csv")
    assert {"recovered", "burst_n", "tail_hit_rate", "tail_backlog_mean"} <= set(br.columns)
    assert set(br["burst_n"]) == {20, 100} and set(br["policy"]) == {"fcfs_lru", "fcfs_random"}
    assert (bdir / "burst_counts.csv").exists()

    kdir = run_cli(tmp_path, "cap", "--quick")
    kr = pd.read_csv(kdir / "runs.csv")
    assert {"eviction", "cap", "recovered"} <= set(kr.columns) and set(kr["eviction"]) == {"lru", "random", "mru_idle"}
    assert set(kr["cap"]) == {28, 36}

    rdir = run_cli(tmp_path, "report", "--quick", "--curve-dir", str(cdir), "--burst-dir", str(bdir), "--cap-dir", str(kdir))
    pe = pd.read_csv(rdir / "prediction_eval.csv")
    assert list(pe["id"][:6]) == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert (pe["verdict"][:6] == "NOT_EVALUABLE").all()          # a quick design is not the registered design
    for f in ("fig1_mu_curves.pdf", "fig2_fluid_burst.pdf", "fig3_cap_heatmap.pdf", "fig4_k_scaling.pdf", "meta.json",
              "table_curve.csv", "table_input_provenance.csv", "preregistration.yaml"):
        assert (rdir / f).exists(), f
        if f.endswith(".pdf"):
            assert (rdir / f).read_bytes()[:4] == b"%PDF"
    rmeta = json.loads((rdir / "meta.json").read_text())
    assert rmeta["flags"] and any("quick" in x for x in rmeta["flags"])
    # a second invocation creates a NEW directory and leaves the first untouched
    cdir2 = run_cli(tmp_path, "curve", "--quick")
    assert cdir2 != cdir
    assert {p.name: p.stat().st_mtime_ns for p in cdir.iterdir()} == first_files
