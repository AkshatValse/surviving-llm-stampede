"""Tests for the prediction-evaluation logic (src/delayeos/analysis.py) on synthetic summaries."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from delayeos.analysis import band_check, eval_a, eval_b, eval_c, eval_d, go_decision, main_table

ROOT = Path(__file__).resolve().parents[1]
P = yaml.safe_load(open(ROOT / "configs" / "delay_eos.yaml"))["predictions"]
ETAS = [0.003, 0.01, 0.03]


def make_df(sp_fn, loss_fn) -> pd.DataFrame:
    rows = []
    for opt, b1s, modes in (("adam", [0.9, 0.99], ["sync", "delay", "ef"]), ("muon", [np.nan], ["sync", "delay"])):
        for batch in (1000, 64):
            for b1 in b1s:
                for mode in modes:
                    for eta in ETAS:
                        for seed in range(3):
                            sp = sp_fn(opt, b1, mode, batch, eta, seed)
                            rows.append({"optimizer": opt, "beta1": b1, "mode": mode, "batch": batch, "eta": eta,
                                         "seed": seed, "diverged": 0, "final_loss": loss_fn(opt, b1, mode, batch, eta),
                                         "med_eta_SP_last": sp, "max_eta_SP_all": sp * 1.2 if mode == "sync" else sp,
                                         "med_eta_S_last": 0.1})
    return pd.DataFrame(rows)


def ideal_sp(opt, b1, mode, batch, eta, seed):
    if opt == "muon":
        return np.nan
    return {"sync": 38.0, "delay": 1.0, "ef": 2.7}[mode] if batch == 1000 else {"sync": 3.0, "delay": 1.0, "ef": 2.7}[mode]


def loss(opt, b1, mode, batch, eta):
    base = 0.01 * (1 + abs(np.log10(eta / 0.01)))  # best eta = 0.01
    pen = {"sync": 1.0, "delay": 1.5 if b1 != 0.99 else 1.2, "ef": 1.2}[mode]
    if opt == "muon":
        pen = {"sync": 1.0, "delay": 1.1}[mode]
    return base * pen


def test_eval_a_pass_fail_inconclusive():
    df = make_df(ideal_sp, loss)
    a = eval_a(df, P)
    assert a["verdict"] == "PASS" and a["sync_beta0.9"]["reached_gate"]
    # delay at 0.99 off-band at all etas -> FAIL
    bad = make_df(lambda o, b1, m, bt, e, s: 2.0 if (m == "delay" and b1 == 0.99 and bt == 1000) else ideal_sp(o, b1, m, bt, e, s), loss)
    assert eval_a(bad, P)["verdict"] == "FAIL"
    # sync never exceeds 10 -> inconclusive regardless of bands
    low = make_df(lambda o, b1, m, bt, e, s: 5.0 if m == "sync" else ideal_sp(o, b1, m, bt, e, s), loss)
    assert eval_a(low, P)["verdict"].startswith("INCONCLUSIVE")


def test_band_check_needs_two_of_three_seeds_at_two_etas():
    rows = []
    for eta, vals in zip(ETAS, ([1.0, 1.1, 5.0], [1.0, 5.0, 5.0], [0.8, 0.9, 1.0])):
        for seed, v in enumerate(vals):
            rows.append({"eta": eta, "seed": seed, "diverged": 0, "med_eta_SP_last": v})
    r = band_check(pd.DataFrame(rows), [0.75, 1.25], P["a"]["min_seed_frac"], P["a"]["min_etas"])
    assert [v["ok"] for v in r["per_eta"].values()] == [True, False, True] and r["passed"]
    rows[0]["diverged"] = rows[1]["diverged"] = 1  # diverged runs never count as in-band
    r = band_check(pd.DataFrame(rows), [0.75, 1.25], P["a"]["min_seed_frac"], P["a"]["min_etas"])
    assert [v["ok"] for v in r["per_eta"].values()] == [False, False, True] and not r["passed"]


def test_eval_b_downgrade_when_sync_not_at_cap():
    df = make_df(lambda o, b1, m, bt, e, s: 1.0 if (bt == 64 and m == "sync") else ideal_sp(o, b1, m, bt, e, s), loss)
    b = eval_b(df, P)["beta0.9"]
    assert b["downgrade_not_stability_effect"] and not b["go_clause"]
    assert b["penalty_at_sync_best_eta"] == pytest.approx(0.5) and b["best_eta_sync"] == 0.01
    # sync at cap (3.0 >= 2) and delay at ~1 with a 50% penalty -> GO clause, no downgrade
    b2 = eval_b(make_df(ideal_sp, loss), P)["beta0.9"]
    assert b2["go_clause"] and not b2["downgrade_not_stability_effect"]
    assert go_decision(eval_a(make_df(ideal_sp, loss), P), eval_b(make_df(ideal_sp, loss), P))["GO"]


def test_eval_c_and_d():
    df = make_df(ideal_sp, loss)
    c = eval_c(df, P)["batch64"]
    assert c["supported_tuned"] and c["n_eta_with_smaller_penalty_at_0.99"] == 3
    d = eval_d(df, P)["batch1000"]
    assert d["muon_penalty_tuned"] == pytest.approx(0.1) and d["adam0.9_penalty_tuned"] == pytest.approx(0.5)
    assert not d["negative_muon_ge_adam0.9"]
    worse = make_df(ideal_sp, lambda o, b1, m, bt, e: loss(o, b1, m, bt, e) * (3.0 if (o == "muon" and m == "delay") else 1.0))
    assert eval_d(worse, P)["batch1000"]["negative_muon_ge_adam0.9"]


def test_main_table_shape_and_divergence_is_inf():
    df = make_df(ideal_sp, loss)
    df.loc[(df.optimizer == "adam") & (df["mode"] == "delay") & (df.batch == 64) & (df.eta == 0.03) & (df.seed == 0),
           "diverged"] = 1
    t = main_table(df)
    assert len(t) == 48
    row = t[(t.optimizer == "adam") & (t["mode"] == "delay") & (t.batch == 64) & (t.eta == 0.03) & (t.beta1 == 0.9)].iloc[0]
    assert row.n_diverged == 1 and np.isinf(row.final_loss_mean)
