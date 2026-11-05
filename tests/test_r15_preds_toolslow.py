"""Tests of the r15 TOOLSLOW prediction drivers (analysis/r15_sim_toolslow.py, analysis/r15_pred2_toolslow.py): the
simulator hook is inert without a slowdown and lengthens exactly the tool calls starting in the window, the exact plans are
the committed NOBURST controls', the pred2 driver leaves the frozen module's constants as it found them, and the frozen
output files (when present; they are force-added) carry the headline calls of notes/PREDICTIONS_r15.md."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from analysis import r15_sim_toolslow as S
from prefixmeta import gate_control as gc
from prefixmeta.sim import RunSpec, deep_update
from prefixmeta.workload import ArrivalPlan

REPO = Path(__file__).resolve().parent.parent
SIM_JSON = REPO / "results/theory/r15/toolslow_sim.json"
PRED2_JSON = REPO / "results/theory/r15/toolslow_pred2.json"


def _setup(mode: str = "mixed"):
    cfg0, rcfg = S.load_cfg()
    refs = S.r11.pool_refs(rcfg, S.POOL)
    cfg = deep_update(cfg0, {"engine": {"batching": mode, "kv_memory_tokens": int(refs["kv"])}})
    cp, rate, _ = S.exact_plan(rcfg, 0, 1.35)
    H = float(rcfg["protocol"]["duration_s"])
    rs = RunSpec(exp="test", policy=rcfg["policy"], seed=0, horizon_s=H, variant="t", plan=ArrivalPlan(kind="constant", horizon_s=H, rate=rate))
    ctl = gc.GateControl.from_dict(rcfg["controls"][S.CONTROL])
    return cfg, rs, ctl, cp


def _digest(x) -> str:
    return hashlib.sha256(json.dumps(S.sanitize(x), sort_keys=True, default=str).encode()).hexdigest()


def test_hook_without_slowdown_is_the_frozen_gate_engine():
    cfg, rs, ctl, cp = _setup()
    a = gc.simulate_gate(cfg, rs, ctl, S.r11.specs_from_plan(cp))
    b, hook = S.simulate_toolslow(cfg, rs, ctl, S.r11.specs_from_plan(cp), None)
    assert gc.GateEngine is S._FROZEN_GATE_ENGINE
    assert hook["n_tool_calls_slowed"] == 0 and hook["n_tool_calls"] > 0
    for part in ("trace", "done", "sessions"):
        assert _digest(a["gate"][part]) == _digest(b["gate"][part]), part
    assert _digest(a["windows"]) == _digest(b["windows"])


def test_hook_lengthens_exactly_the_tool_calls_starting_in_the_window():
    cfg, rs, ctl, cp = _setup()
    res, hook = S.simulate_toolslow(cfg, rs, ctl, S.r11.specs_from_plan(cp), (1200.0, 900.0, 30.0))
    d = np.asarray(res["gate"]["done"], dtype=float).reshape(-1, 5)
    nt = np.array([sp.n_turns for sp in cp])
    starts = d[d[:, 2] < nt[d[:, 1].astype(int)]][:, 0]
    assert hook["n_tool_calls_slowed"] == int(((starts >= 1200.0) & (starts < 2100.0)).sum()) > 0
    assert 1200.0 <= hook["slowed_t_start_min"] and hook["slowed_t_start_max"] < 2100.0
    assert gc.GateEngine is S._FROZEN_GATE_ENGINE


def test_exact_plans_are_the_committed_noburst_plans():
    _, rcfg = S.load_cfg()
    rows = S.plan_check(rcfg)
    assert len(rows) == 6 and all(r["matches_control"] for r in rows), rows


def test_tri_state_is_the_registered_rule():
    assert S.tri_state(["stuck", "stuck", "good"]) == "TRAPS"
    assert S.tri_state(["stuck", "good", "good"]) == "NO-TRAP"
    assert S.tri_state(["stuck", "good", "neither"]) == "MIXED"
    assert S.tri_state(["stuck+good", "stuck+good", "neither"]) == "MIXED"


def test_pred2_window_patch_restores_the_frozen_constants():
    from analysis import r15_pred2_toolslow as R
    from analysis.theory.pred2 import toolslow as T
    before = (T.T_ON, T.T_OFF, T.MULT, T.WIN)
    with R.window(1200.0, 3000.0):
        assert (T.T_ON, T.T_OFF) == (1200.0, 3000.0)
    assert (T.T_ON, T.T_OFF, T.MULT, T.WIN) == before == (1200.0, 2100.0, 1.35, (5700.0, 8700.0))
    with pytest.raises(RuntimeError):
        with R.window(0.0, 1.0):
            raise RuntimeError("boom")
    assert (T.T_ON, T.T_OFF) == (1200.0, 2100.0)


@pytest.mark.skipif(not SIM_JSON.exists(), reason="frozen simulator output not present")
def test_frozen_simulator_headline():
    s = json.loads(SIM_JSON.read_text())["summary"]
    for mode in ("mixed", "separate_prefill_priority"):
        assert (s["T1"][mode]["exact_code"], s["T1"][mode]["call"]) == ("SSS", "TRAPS")
        assert (s["T2"][mode]["exact_code"], s["T2"][mode]["call"]) == ("SGG", "NO-TRAP")
        assert s["d10"][mode]["exact_code"] == "GGG" and s["d30"][mode]["exact_code"] == "GGS"   # retrodictions
        assert s["ctl135"][mode]["exact_code"] == "GGG" and s["ctl165"][mode]["exact_code"] == "GGG"


@pytest.mark.skipif(not PRED2_JSON.exists(), reason="frozen pred2 output not present")
def test_frozen_pred2_headline():
    d = json.loads(PRED2_JSON.read_text())
    s = d["summary"]
    assert s["T1"]["fluid_call"] == "STUCK" and s["T1"]["n_at_slowdown_end"] > s["T1"]["n_u"]
    assert s["T2"]["fluid_call"] == "STUCK" and abs(s["T2"]["n_at_slowdown_end"] - 51.1) < 0.05 and abs(s["T2"]["n_u"] - 31.8) < 0.05
    assert s["T2"]["per_seed_calls"] == ["STUCK", "GOOD", "GOOD"]
    assert d["r13_reproduction"]["reproduced"] is True and d["r13_reproduction"]["max_abs_diff_all"] == 0.0
