import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_NUM_THREADS", "4")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from vat import analysis as an
from vat.cs import prpl_eb_cs
from vat.kernels import build_candidates, make_grid
from vat.measure import collect_process, process_seeds

KCFG = {"orders": ["row", "col"], "tiles": [0, 16, 64], "parallel": [False, True],
        "fastmath": [False, True]}
ACFG = {"alpha": 0.05, "delta": 0.03, "holdout": 1, "S": 6, "r_values": [3, 5],
        "race_budget_per_candidate": [3, 8],
        "null_test": {"K_values": [2, 4], "r_values": [5], "S": 5}}
B = float(np.log(4))


def test_candidates_numerically_equal():
    cands = build_candidates(KCFG)
    assert len(cands) == 1 + 2 * 3 * 2 * 2
    n = 70   # not a multiple of any tile: exercises edge tiles
    ref = make_grid(n, 3)
    a0, b0 = ref.copy(), ref.copy()
    cands[0].make(2)(a0, b0)
    for c in cands[1:]:
        a, b = ref.copy(), ref.copy()
        c.make(2)(a, b)
        assert np.allclose(a, a0, rtol=1e-12, atol=1e-12), c.name


def test_collect_process_shape_and_determinism_of_schedule():
    cands = build_candidates({**KCFG, "tiles": [0, 16]})
    ss = process_seeds(1, 2)[0]
    d1 = collect_process(cands, 48, 1, 3, 0, ss)
    d2 = collect_process(cands, 48, 1, 3, 0, ss)
    K = len(cands) - 1
    assert len(d1) == 3 * K and (d1.baseline_ns > 0).all() and (d1.candidate_ns > 0).all()
    # schedule (candidate order / pair order) is seed-determined; times are not
    assert (d1[["block", "cand", "cand_first"]].values == d2[["block", "cand", "cand_first"]].values).all()
    assert d1.groupby("cand").size().eq(3).all()


def test_cs_coverage_time_uniform():
    rng = np.random.default_rng(0)
    a, b_ = 2.0, 5.0
    mu = a / (a + b_)
    x = rng.beta(a, b_, size=(2000, 500))
    lo, hi = prpl_eb_cs(x, 0.05)
    miss = ((lo > mu) | (hi < mu)).any(axis=1).mean()
    slack = 3 * np.sqrt(0.05 * 0.95 / 2000)
    assert miss <= 0.05 + slack, miss
    assert (hi - lo)[:, -1].mean() < 0.2          # and it actually shrinks
    assert (np.diff(lo, axis=-1) >= 0).all() and (np.diff(hi, axis=-1) <= 0).all()


def synth_df(seed=0, P=4, K=6, R=20) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    gain = np.linspace(-0.05, 0.12, K)
    for p in range(P):
        pe = rng.normal(0, 0.01)
        t = 0
        for blk in range(R):
            for k in rng.permutation(K):
                tb = 1e6 * np.exp(rng.normal(0, 0.03))
                tc = tb * np.exp(-gain[k] - pe + rng.normal(0, 0.03))
                t += 1
                rows.append((p, blk, k + 1, int(rng.integers(2)), int(tb), int(tc), t))
    return pd.DataFrame(rows, columns=["proc", "block", "cand", "cand_first",
                                       "baseline_ns", "candidate_ns", "t_ns"])


def run_analysis(seed):
    df = synth_df()
    ss_h, ss_m, ss_n = np.random.SeedSequence(seed).spawn(3)
    hold = an.choose_holdout(np.sort(df.proc.unique()), 1, np.random.default_rng(ss_h))
    arr = an.build_arrays(df, B, hold)
    rep = an.run_main(arr, ACFG, B, 0.5, ss_m)
    null = an.run_null(arr, ACFG, B, 0.5, ss_n)
    return an.summarize(rep, arr["K"]), null, an.noise_summary(df, B)


def test_analysis_deterministic_and_sane():
    s1, n1, z1 = run_analysis(5)
    s2, n2, z2 = run_analysis(5)
    pd.testing.assert_frame_equal(s1, s2)
    pd.testing.assert_frame_equal(n1, n2)
    pd.testing.assert_frame_equal(z1, z2)
    s3, _, _ = run_analysis(6)
    assert not s1.equals(s3)
    assert set(s1.protocol) == {"NAIVE", "BONF-T", "CS-RACE", "CS-RACE-BEST"}
    assert (s1.regret_pct >= -1e-9).all()
    assert (s1.fwer.between(0, 1)).all() and (s1.power.dropna().between(0, 1)).all()
    naive = s1[s1.protocol == "NAIVE"].set_index("param")
    assert (naive.blocks == 6 * naive.index).all()
    assert len(z1) == 7 and z1.frac_clipped.dropna().eq(0).all()


def test_race_stops_early_on_big_effect():
    from vat.protocols import cs_race, race_bounds
    rng = np.random.default_rng(0)
    K, T = 4, 200
    x = np.stack([rng.normal(m, 0.02, T) for m in (0.3, 0.3, -0.3, 0.0)])
    ns = np.full((K, T), 2.0)
    theta = np.array([0.3, 0.3, -0.3, 0.0])
    lo, hi = race_bounds(x, 0.05, B, 0.5)
    r = cs_race(x, ns, lo, hi, 4 * T, 0.03, B, theta, True)
    assert r["blocks"] < 4 * T and r["n_accept"] == 2 and r["n_false_accept"] == 0
