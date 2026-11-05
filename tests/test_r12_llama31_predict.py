"""configs/r12_llama31_predict.yaml (blind Llama-3.1-8B predictions with the round-7 stages plus the B3v stage) and src/prefixmeta/r12_llama31_predict.py.

A renamed copy of tests/test_r9_vllm_predict.py; the differences are the spec block name (r12), the Llama real inputs (filled from this cell's E0a in the
second commit) and the range allowed for the V1 factor.

* the spec is the declared pre-registration: it differs from configs/r7_robustness.yaml in exactly the declared ways; the V1 factors are frozen and agree with the
  logs of the quick B1 check that set them;
* the V1 override strings (scaled keys only, nothing else changes), the registration map, the cap / multiple lists and the two PASS rules (per-arm and same-seed) on small
  synthetic frames;
* every stage, both variants, both modes, the B3v stage, the report and the assembly run end to end on a tiny scaled-down copy of the REAL spec; the multi-arm B3v runs are
  bit-identical to the single-cap runs of the round-7 helper.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from prefixmeta import r7_robustness as R7
from prefixmeta import r12_llama31_predict as R9
from prefixmeta.engine import EngineParams
from prefixmeta.probe import load_probe_config, run_burst
from prefixmeta.workload import WorkloadParams

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "configs" / "r12_llama31_predict.yaml"
OLD = REPO / "configs" / "r7_robustness.yaml"
DRIVER = REPO / "experiments" / "r12_llama31_predict_run.sh"


def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- the spec is pinned to its declaration
def test_the_engine_workload_and_metrics_are_the_round7_ones_at_the_300k_kv_cap():
    a, b = load(SPEC), load(OLD)
    assert a["engine"] == b["engine"] and a["engine"]["kv_memory_tokens"] == 300000 == a["r12"]["kv_pool_tokens"]
    assert a["engine"]["batching"] == "mixed" and a["engine"]["cache_enabled"] is True
    for k in ("base_config", "workload", "metrics", "parallel"):
        assert a[k] == b[k], k
    cfg = load_probe_config(str(SPEC), REPO)
    wl = WorkloadParams.from_dict(cfg["workload"])
    assert (wl.initial_context_tokens, wl.new_prompt_tokens, wl.decode_tokens, wl.mean_turns, wl.max_turns) == (2000, 550, 100, 15, 60)
    assert R7.expected_turns(cfg, cfg["r7"], "exp5") == pytest.approx(14.761, abs=5e-4)


def test_the_r7_block_is_the_round7_declaration_except_the_declared_differences():
    a, b = load(SPEC)["r7"], load(OLD)["r7"]
    for k in ("policy", "expected_turns", "wilson_z", "window", "classify", "lambda_miss", "record_workload", "pairs"):
        assert a[k] == b[k], k
    assert list(a["workloads"]) == ["exp5"] and a["workloads"]["exp5"]["workload"] == b["workloads"]["exp5"]["workload"]
    assert a["stages"] == ["lambda_miss", "curves", "edge"]
    assert a["curve"]["n_grid"] == [16, 20, 24, 28, 32, 40, 48, 96, 300] and a["curve"]["seeds"] == list(range(10))
    assert {k: v for k, v in a["curve"].items() if k not in ("n_grid", "seeds")} == {k: v for k, v in b["curve"].items() if k not in ("n_grid", "seeds")}
    assert a["edge"]["multiples"] == [1.25, 1.5, 1.75, 2.0, 2.5, 3.0] and a["edge"]["refine_if_lowest_unstable"] == []
    assert {k: v for k, v in a["edge"].items() if k not in ("multiples", "refine_if_lowest_unstable")} == {k: v for k, v in b["edge"].items() if k not in ("multiples", "refine_if_lowest_unstable")}
    assert a["lambda_miss"]["population"] == 32 and a["lambda_miss"]["seeds"] == [0, 1, 2] and (a["lambda_miss"]["warmup_s"], a["lambda_miss"]["horizon_s"]) == (900.0, 2700.0)
    assert a["pairs"]["burst_n"] == 200 and a["pairs"]["burst_width_s"] == 60.0 and a["pairs"]["warmup_s"] == 1200.0 and a["pairs"]["after_s"] == 7500.0
    assert a["pairs"]["seeds"] == list(range(10))


def test_the_registration_rule_and_the_b3v_candidates_cover_every_point_the_rule_can_produce():
    s = load(SPEC)
    reg, b3 = s["r12"]["registration"], s["r12"]["b3v"]
    m = R9.registration_map(reg)
    assert {h: pts for h, pts in m.items()} == {1.25: [1.10, 1.15], 1.5: [1.15, 1.35], 1.75: [1.25, 1.5], 2.0: [1.35, 1.65], 2.5: [1.5, 2.0], 3.0: [1.65, 2.35]}
    produced = {p for pts in m.values() for p in pts}
    cands = {mm for mm, _ in R9.candidate_multiples(b3)}
    assert cands == produced                                                        # nothing the rule can produce is missing, nothing else is run
    assert [mm for mm, e in R9.candidate_multiples(b3) if not e] == [1.15, 1.25, 1.35, 1.5, 1.65, 2.0, 2.35]       # the task's list
    assert [mm for mm, e in R9.candidate_multiples(b3) if e] == [1.10]
    assert reg["edge_grid"] == s["r7"]["edge"]["multiples"]
    assert b3["caps_sensitivity"] == [16, 20, 24, 28, 32] and b3["cut_caps_if_over_budget"] == [20, 28]
    assert R9.used_by(reg, 1.35) == "hi = 1.5 (high); hi = 2 (low)" and R9.used_by(reg, 1.65) == "hi = 2 (high); hi = 3 (low)" and R9.used_by(reg, 1.7) == "none"


def test_the_two_real_inputs_and_the_v1_declaration_are_pinned():
    r9 = load(SPEC)["r12"]
    lm, tok = r9["real_inputs"]["lambda_miss_turns_sessions_per_s"], r9["real_inputs"]["all_miss_token_rate_tok_per_s"]
    assert lm is not None and tok is not None and r9["real_inputs"]["source"], "the real inputs are filled in the second commit"
    assert 0.01 < lm < 0.2 and 2000 < tok < 30000
    assert r9["v1"]["target_token_rate_tok_per_s"] == tok and r9["v1"]["scaled_engine_keys"] == ["per_token_s", "prefill_attn_s", "decode_attn_s"]
    assert list(r9["modes"]) == ["mixed", "separate"] and r9["variants"] == ["v0", "v1"]
    assert r9["modes"]["separate"]["batching"] == "separate_prefill_priority"
    assert len({R9.out_root_for(r9, v, m) for v in r9["variants"] for m in r9["modes"]}) == 4


# ----------------------------------------------------------------------------- the V1 overrides
def test_v0_has_no_cost_override_and_only_the_secondary_mode_changes_the_batching():
    s = load(SPEC)
    assert R9.variant_sets(s, "v0", "mixed") == []
    assert R9.variant_sets(s, "v0", "separate") == ["engine.batching=separate_prefill_priority"]
    with pytest.raises(ValueError, match="unknown variant"):
        R9.variant_sets(s, "v2", "mixed")


@pytest.mark.parametrize("mode", ["mixed", "separate"])
def test_v1_scales_exactly_the_three_declared_keys_by_the_frozen_factor_and_nothing_else(mode):
    s = load(SPEC)
    f = s["r12"]["v1"]["factor"][mode]
    assert f is not None and 0.8 < f < 2.0
    sets = R9.variant_sets(s, "v1", mode)
    cfg = load_probe_config(str(SPEC), REPO, sets)
    base = load_probe_config(str(SPEC), REPO)
    keys = s["r12"]["v1"]["scaled_engine_keys"]
    for k in keys:
        assert cfg["engine"][k] == pytest.approx(base["engine"][k] * f, rel=1e-9) and isinstance(cfg["engine"][k], float)
    assert {k: v for k, v in cfg["engine"].items() if k not in keys and k != "batching"} == {k: v for k, v in base["engine"].items() if k not in keys and k != "batching"}
    assert cfg["engine"]["batching"] == s["r12"]["modes"][mode]["batching"]
    EngineParams.from_dict(cfg["engine"])
    assert len([x for x in sets if not x.startswith("engine.batching")]) == 3


def test_an_unfrozen_factor_is_refused():
    s = load(SPEC)
    s["r12"]["v1"]["factor"]["mixed"] = None
    with pytest.raises(ValueError, match="not frozen"):
        R9.variant_sets(s, "v1", "mixed")
    assert R9.variant_sets(s, "v0", "mixed") == []


@pytest.mark.parametrize("mode", ["mixed", "separate"])
def test_the_frozen_factor_is_the_accepted_iteration_of_the_logged_check(mode):
    s = load(SPEC)
    chk = json.loads((REPO / R9.CAL_DIR / f"factor_check_{mode}.json").read_text())
    tol, target = s["r12"]["v1"]["tolerance_rel"], s["r12"]["v1"]["target_token_rate_tok_per_s"]
    assert chk["converged"] and chk["target"] == target and abs(chk["residual_rel"]) <= tol
    assert chk["accepted_factor"] == s["r12"]["v1"]["factor"][mode]
    acc = [it for it in chk["iterations"] if it["factor"] == chk["accepted_factor"]][-1]
    assert acc["token_rate"] == chk["accepted_rate"] and acc["sets"] == R9.variant_sets(s, "v1", mode)              # the main run uses the strings of the check
    assert all(it["git"]["dirty"] is False for it in chk["iterations"]) and len({it["git"]["commit"] for it in chk["iterations"]}) == 1
    assert chk["iterations"][0]["factor"] == 1.0 and chk["iterations"][0]["sets"] == R9.variant_sets(s, "v0", mode)
    f1 = round(chk["iterations"][0]["token_rate"] / target, s["r12"]["v1"]["factor_decimals"])
    assert chk["iterations"][1]["factor"] == f1                                                                     # the declared first step


# ----------------------------------------------------------------------------- pure helpers
def test_the_cap_list_has_the_picked_cap_the_sensitivity_caps_and_the_labelled_extra_once_each():
    b3 = load(SPEC)["r12"]["b3v"]
    c = R9.caps_for(24, b3)
    assert [k["cap"] for k in c] == [16, 20, 24, 28, 32, 40] and [k["cap"] for k in c if k["picked"]] == [24]
    assert [k["cap"] for k in c if k["extra_labelled"]] == [40] and all(k["sensitivity"] for k in c if k["cap"] in (16, 20, 24, 28, 32))
    c2 = R9.caps_for(48, b3)                                     # a picked cap outside the sensitivity list is added, not dropped
    assert [k["cap"] for k in c2] == [16, 20, 24, 28, 32, 40, 48] and [k["cap"] for k in c2 if k["picked"]] == [48] and not c2[-1]["sensitivity"]


def classified(spec: dict, burst: str, noburst: str, cap: str, capn: int = 24) -> pd.DataFrame:
    """Synthetic classified runs of one multiple: one letter per seed (T trapped, R recovered, I indeterminate)."""
    rows = []
    for arm, lab in (("burst", burst), ("no_burst", noburst), (f"cap_{capn}", cap)):
        for seed, ch in enumerate(lab):
            rows.append({"mult": 1.5, "arm": arm, "seed": seed, "trapped": ch == "T", "recovered": ch == "R", "indeterminate": ch == "I",
                         "label": {"T": "TRAPPED", "R": "RECOVERED", "I": "INDETERMINATE"}[ch], "hit": 0.93 if ch == "R" else 0.0,
                         "backlog": 0.05 if ch == "R" else 400.0, "token_ratio": 1.05 if ch == "T" else 0.0, "slope": 0.0})
    return pd.DataFrame(rows)


def test_the_per_arm_rule_can_pass_where_the_same_seed_rule_fails_and_both_count_correctly():
    # 10 seeds, need 7. Each arm holds in exactly 7 seeds, but the failures of the three arms fall in different seeds: per-arm PASS, same-seed count 4.
    burst = "TTTTTTTRRR"                 # trapped in seeds 0-6 (7)
    nob = "RRRIRRRRRR"                   # good in 9 seeds, not in seed 3
    cap = "IIIRRRRRRR"                   # recovered in seeds 3-9 (7)
    v = R9.pair_verdict(classified({}, burst, nob, cap), 24, 7)
    assert (v["burst_trapped"], v["noburst_good"], v["cap_recovered"]) == (7, 9, 7) and v["per_arm_pass"]
    assert v["same_seed_count"] == 3 and not v["same_seed_pass"]            # seed 3 fails NOBURST, seeds 0-2 fail CAPPED, seeds 7-9 fail BURST: only seeds 4, 5, 6 pass all three
    ok = R9.pair_verdict(classified({}, "T" * 10, "R" * 10, "R" * 9 + "T"), 24, 7)
    assert ok["per_arm_pass"] and ok["same_seed_pass"] and ok["same_seed_count"] == 9 and ok["cap_trapped"] == 1
    bad = R9.pair_verdict(classified({}, "T" * 6 + "R" * 4, "R" * 10, "R" * 10), 24, 7)
    assert not bad["per_arm_pass"] and not bad["same_seed_pass"] and bad["burst_trapped"] == 6
    assert R7.need_count(10, 2 / 3) == 7                                  # the declared 7-of-10


def test_the_b3_tables_carry_both_verdicts_the_marked_cap_and_the_registration_use():
    s = load(SPEC)
    r9 = s["r12"]
    cl = classified({}, "T" * 10, "R" * 10, "R" * 10)
    rows = []
    for arm, lab in (("cap_16", "T" * 10),):
        for seed, ch in enumerate(lab):
            rows.append({"mult": 1.5, "arm": arm, "seed": seed, "trapped": True, "recovered": False, "indeterminate": False, "label": "TRAPPED", "hit": 0.0, "backlog": 300.0,
                         "token_ratio": 1.0, "slope": 0.0})
    cl = pd.concat([cl, pd.DataFrame(rows)], ignore_index=True)
    caps = R9.caps_for(24, {"caps_sensitivity": [16, 24], "caps_extra_labelled": []})
    per_cap = {str(k["cap"]): R9.pair_verdict(cl, k["cap"], 7) for k in caps}
    p0 = per_cap["24"]
    summ = {"cap_picked": 24, "caps": caps, "points": {"1.5": {"lam": 0.1, "extra_labelled": False, "n_seeds": 10, "need": 7, "burst_trapped": p0["burst_trapped"],
                                                              "noburst_good": p0["noburst_good"], "per_cap": per_cap}}}
    txt, head = R9.b3_tables(cl, summ, r9, s["r7"]["window"], 1.96, 0.2)
    assert "hi = 1.75 (high); hi = 2.5 (low)" in txt and "| 24 * |" in txt and "| 16 |" in txt
    assert "PASS same-seed (>= 7)" in txt and "PASS per-arm (each >= 7)" in txt
    assert head["points"]["1.5"]["caps"]["24"]["same_seed_pass"] and not head["points"]["1.5"]["caps"]["16"]["per_arm_pass"]
    assert head["points"]["1.5"]["trapped_token_ratio_max"] == pytest.approx(1.05)


def test_the_driver_script_is_valid_bash_with_unix_line_endings_and_runs_all_stages_for_both_variants():
    raw = DRIVER.read_bytes()
    assert b"\r" not in raw
    txt = raw.decode("utf-8")
    for needle in ("v1sets", "experiments/r7_robustness_run.py", "pairs_all", "prefixmeta.r7_report report", "prefixmeta.r12_llama31_predict report", "lambda_miss curves edge",
                   "--workers 6", "VARIANTS=\"${*:-v0 v1}\"", 'MODES="mixed separate"', "set -u"):
        assert needle in txt, needle
    assert "--workers 7" not in txt and not re.search(r"(ssh|scp|sbatch|squeue|sacct)", txt)
    bash = shutil.which("bash")
    if bash:
        r = subprocess.run([bash, "-n", str(DRIVER)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_the_module_adds_only_new_code_and_reads_no_forbidden_path():
    src = (REPO / "src" / "prefixmeta" / "r12_llama31_predict.py").read_text(encoding="utf-8")
    for bad in ("results/nova", "notes/LOG", "notes/STATE", "paper/", "ssh ", "sbatch", "squeue", "sacct"):
        assert bad not in src, bad


# ----------------------------------------------------------------------------- end to end on a tiny scaled-down copy of the REAL spec
def tiny_spec(tmp_path: Path) -> Path:
    raw = load(SPEC)
    r7 = raw["r7"]
    r7["lambda_miss"].update(seeds=[0], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["curve"].update(n_grid=[8, 16, 32, 64], seeds=[0, 1], warmup_s=300.0, horizon_s=900.0, pool_sessions=2000)
    r7["edge"].update(multiples=[1.25, 1.5, 2.0], seeds=[0, 1], horizon_s=1500.0, stable_trend_window_s=500.0)
    r7["pairs"].update(seeds=[0, 1], burst_n=60, warmup_s=300.0, after_s=1200.0)
    r7["classify"]["eval_window_rel_to_burst_s"] = [700.0, 1200.0]
    raw["r12"]["b3v"].update(multiples=[1.15, 1.5], multiples_extra_labelled=[1.10], caps_sensitivity=[16, 20], caps_extra_labelled=[])
    for m in ("mixed", "separate"):                     # before the factor freeze the real spec holds null; the machinery test then uses placeholders
        raw["r12"]["v1"]["factor"][m] = raw["r12"]["v1"]["factor"][m] or 1.25
    ri = raw["r12"]["real_inputs"]
    ri["lambda_miss_turns_sessions_per_s"] = ri["lambda_miss_turns_sessions_per_s"] or 0.06
    ri["all_miss_token_rate_tok_per_s"] = ri["all_miss_token_rate_tok_per_s"] or 9000
    raw["r12"]["out_root_template"] = str(tmp_path / "res_{variant}_{mode}")
    p = tmp_path / "tiny_r12.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return p


def run_tree(spec: Path, variant: str, mode: str) -> str:
    s = load(spec)
    out = R9.out_root_for(s["r12"], variant, mode)
    sets = R9.variant_sets(s, variant, mode)
    for st in ("lambda_miss", "curves", "edge"):
        argv = [st, "--spec", str(spec), "--workers", "1", "--out-root", out]
        for x in sets:
            argv += ["--set", x]
        assert R7.main(argv, repo_dir=REPO) == 0
    argv = ["pairs_all", "--spec", str(spec), "--workers", "1", "--out-root", out]
    for x in sets:
        argv += ["--set", x]
    assert R9.main(argv, repo_dir=REPO) == 0
    return out


def test_the_stages_the_b3v_stage_the_report_and_the_assembly_run_end_to_end_on_a_tiny_copy(tmp_path):
    spec = tiny_spec(tmp_path)
    s = load(spec)
    o0 = run_tree(spec, "v0", "mixed")
    o1 = run_tree(spec, "v1", "separate")
    # V1 / separate ran with the frozen scaled cost keys and the separate mode, V0 / mixed with none
    eff1 = yaml.safe_load((R7.stage_dir(o1, "curves") / "config_effective.yaml").read_text())
    eff0 = yaml.safe_load((R7.stage_dir(o0, "curves") / "config_effective.yaml").read_text())
    f = s["r12"]["v1"]["factor"]["separate"]
    assert eff1["engine"]["batching"] == "separate_prefill_priority" and eff1["engine"]["per_token_s"] == pytest.approx(6.26e-05 * f, rel=1e-9)
    assert eff0["engine"]["per_token_s"] == 6.26e-05 and eff0["engine"]["batching"] == "mixed"
    m1 = json.loads((R7.stage_dir(o1, "pairs_all") / "meta.json").read_text())
    assert m1["overrides"] == R9.variant_sets(s, "v1", "separate") and json.loads((R7.stage_dir(o0, "pairs_all") / "meta.json").read_text())["overrides"] == []
    # B3v: every candidate multiple, every arm, the verdict fields
    summ = R7.stage_summary(o0, "pairs_all")
    assert list(summ["points"]) == ["1.1", "1.15", "1.5"] and summ["points"]["1.1"]["extra_labelled"] and not summ["points"]["1.15"]["extra_labelled"]
    picked = summ["cap_picked"]
    assert sorted(int(c) for c in summ["points"]["1.5"]["per_cap"]) == sorted({16, 20, picked}) and set(summ["arms"]) == {"no_burst", "burst"} | {f"cap_{c}" for c in (16, 20, picked)}
    cl = pd.read_csv(R7.stage_dir(o0, "pairs_all") / "classified_runs.csv", float_precision="round_trip")
    assert len(cl) == 3 * len(summ["arms"]) * 2 and set(cl["seed"]) == {0, 1}
    for mk, p in summ["points"].items():
        for c, v in p["per_cap"].items():
            assert v["same_seed_count"] <= min(v["burst_trapped"], v["noburst_good"], v["cap_recovered"])
            assert v["burst_trapped"] == p["burst_trapped"] and v["noburst_good"] == p["noburst_good"]
    # the multi-arm run is bit-identical to a single-cap run of the round-7 helper at one multiple (arms are independent runs on the same seeds)
    cfg = load_probe_config(str(spec), REPO)
    lm = R7.stage_summary(o0, "lambda_miss")["workloads"]["exp5"]
    sec = R7.burst_section(cfg, cfg["r7"], "exp5", float(lm["lambda_miss_turns"]), 1.5, burst_n=60, width=60.0, warmup=300.0, after=1200.0, seeds=[0, 1], cap=int(picked))
    res = run_burst(cfg, sec, workers=1)
    runs, wins, _ = res.frames
    ev = [700.0, 1200.0]
    one = R7.classify_burst_frames(runs, wins, float(lm["lambda_miss_turns"]), float(lm["token_rate"]), cfg["r7"]["classify"], ev, {"mult": 1.5})
    a = one[one["arm"] == "burst_cap"].sort_values("seed")[["hit", "backlog", "slope", "token_rate"]].reset_index(drop=True)
    b = cl[(np.isclose(cl["mult"], 1.5)) & (cl["arm"] == f"cap_{picked}")].sort_values("seed")[["hit", "backlog", "slope", "token_rate"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_exact=True)

    d = Path(R9.main(["report", "--spec", str(spec), "--out-root", str(tmp_path / "rep")], repo_dir=REPO))
    text = (d / "tables.md").read_text(encoding="utf-8")
    assert text.index("## V0 / `mixed` (PRIMARY)") < text.index("## V0 / `separate` (SECONDARY)") < text.index("## V1 / `mixed` (PRIMARY)") < text.index("## V1 / `separate` (SECONDARY)")
    assert text.count("**stage `lambda_miss` NOT RUN**") == 2 and text.count("**stage `pairs_all` NOT RUN**") == 2          # the two trees that were not run are marked, not dropped
    for h in ("### B1v.", "### B4v.", "### B2v.", "### B3v."):
        assert text.count(h) == 4, h
    assert "PASS same-seed" in text and "PASS per-arm" in text and "Landmarks of the closed curve" in text and "real registration uses it if" in text
    assert "(extra)" in text and "the main B1v token rate equals the check's accepted rate exactly" in text
    head = json.loads((d / "summary.json").read_text())
    assert set(head) == {"v0_mixed", "v0_separate", "v1_mixed", "v1_separate"}
    h0, h1 = head["v0_mixed"], head["v1_separate"]
    assert set(h0) >= {"B1v", "B4v", "B2v", "B3v"} and h1["B1v"]["v1_factor"] == f and h1["B1v"]["bit_identical_to_the_frozen_check"] is False      # tiny run != the frozen check
    assert h0["B3v"]["cap_picked"] == picked and set(h0["B3v"]["points"]) == {"1.1", "1.15", "1.5"} and h0["B4v"]["cap_n"] == picked
    prov = (d / "provenance.md").read_text(encoding="utf-8")
    assert "**V0 / mixed**" in prov and "**V1 / separate** (`engine.batching` = `separate_prefill_priority`" in prov and "engine.per_token_s=" in prov and "NOT RUN" in prov
    notes, hl = tmp_path / "notes.md", tmp_path / "head.md"
    hl.write_text("HEADLINE", encoding="utf-8")
    R9.main(["assemble", "--spec", str(spec), "--out-root", str(tmp_path / "rep"), "--headline", str(hl), "--notes", str(notes)], repo_dir=REPO)
    t = notes.read_text(encoding="utf-8")
    assert t.startswith(f"# {R9.TITLE}\n\nHEADLINE") and "## Tables (generated)" in t and "## Provenance: what was run" in t


def test_v1sets_prints_one_override_per_line(tmp_path, capsys):
    assert R9.main(["v1sets", "--spec", str(SPEC), "--variant", "v1", "--mode", "mixed"], repo_dir=REPO) == 0
    lines = capsys.readouterr().out.splitlines()
    s = load(SPEC)
    assert lines == R9.variant_sets(s, "v1", "mixed") and len(lines) == 3 and all(x.startswith("engine.") for x in lines)
    assert R9.main(["v1sets", "--spec", str(SPEC), "--variant", "v0", "--mode", "mixed"], repo_dir=REPO) == 0 and capsys.readouterr().out == ""
