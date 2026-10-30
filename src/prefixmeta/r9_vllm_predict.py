"""Round 9, blind vLLM predictions of the calibrated simulator: the B3v stage ``pairs_all``, the V1 override strings, the tables and the notes file.

Spec (committed before any run; the V1 cost factors frozen in a second commit): ``configs/r9_vllm_predict.yaml`` (``r9:`` block). The stages B1v (``lambda_miss``), B4v
(``curves``) and B2v (``edge``) are the round-7 stages of ``experiments/r7_robustness_run.py``, used UNCHANGED through the spec (as in round 8). This module adds only

* ``pairs_all`` (B3v): the paired NOBURST / BURST / CAPPED test at EVERY candidate multiple of the registration rule and, for the CAPPED arm, at the cap the closed-curve rule
  picks and at the sensitivity caps; the verdicts under the per-arm rule (each arm in >= 7 of 10 seeds) and under the registered same-seed rule (all three conditions in the
  same seed, in >= 7 of 10 seeds);
* ``v1sets``: the ``--set`` strings of a (variant, mode): V0 = the engine unchanged (only the batching mode for the secondary), V1 = the three token-proportional cost keys
  multiplied by the frozen factor of the mode;
* ``report`` / ``assemble``: the generated tables for the four (variant, mode) result trees and the notes file.

    python -m prefixmeta.r9_vllm_predict pairs_all --spec configs/r9_vllm_predict.yaml --out-root results/r9_vllm_v0_mixed [--set engine.batching=...] [--workers 6]
    python -m prefixmeta.r9_vllm_predict v1sets    --spec configs/r9_vllm_predict.yaml --variant v1 --mode separate     -> one key=value per line
    python -m prefixmeta.r9_vllm_predict report    --spec configs/r9_vllm_predict.yaml                                  -> results/r9_vllm_report/<ts>/
    python -m prefixmeta.r9_vllm_predict assemble  --spec configs/r9_vllm_predict.yaml --headline <file.md> --notes notes/PREDICTIONS_vllm.md

No simulation or classification is re-implemented: the stage calls ``probe.run_burst`` and ``r7_robustness.classify_burst_frames`` (the round-6 window statistics and rules).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from .mech_runner import begin, finish
from .probe import load_probe_config, run_burst
from .r6_predict import df_md
from .r7_report import Stages, fs, letters, sha256_of, t_curves, t_edge, t_workloads
from .r7_robustness import (burst_section, classify_burst_frames, concat, end, need_count, r7_block, stage_dir, stage_summary, start,
                            window_points)
from .r8_native_report import curve_landmarks, edge_landmarks

TITLE = "Round 9: blind predictions of the calibrated simulator for the real vLLM 0.32.0 experiments (KV pool 300,000 tokens)"
CAL_DIR = "calibration/r9_vllm_v1_factor"
STAGES_ALL = ("lambda_miss", "curves", "edge", "pairs_all")


# ======================================================================= pure helpers (unit-tested)
def scaled_value(base: float, factor: float, fmt: str) -> str:
    """The string passed to --set for a scaled engine key: ``base * factor`` in the declared format (always contains a '.', so YAML reads a float)."""
    return format(float(base) * float(factor), fmt)


def v1_factor(r9: dict, mode: str) -> float:
    f = r9["v1"]["factor"][mode]
    if f is None:
        raise ValueError(f"r9.v1.factor.{mode} is not frozen (null): run the quick B1 check and commit the factor first")
    return float(f)


def variant_sets(spec: dict, variant: str, mode: str) -> List[str]:
    """The dotted ``--set`` overrides (``key=value``) of a (variant, mode) on top of the spec: ``engine.batching`` for a non-mixed mode (the spec's engine is mixed) and,
    for V1, the declared scaled engine keys at base x the frozen factor of the mode. V0 mixed has none."""
    r9 = spec["r9"]
    if variant not in r9["variants"]:
        raise ValueError(f"unknown variant {variant!r}; known: {r9['variants']}")
    if mode not in r9["modes"]:
        raise ValueError(f"unknown mode {mode!r}; known: {list(r9['modes'])}")
    sets: List[str] = []
    batching = r9["modes"][mode]["batching"]
    if batching != spec["engine"]["batching"]:
        sets.append(f"engine.batching={batching}")
    if variant == "v1":
        f = v1_factor(r9, mode)
        for k in r9["v1"]["scaled_engine_keys"]:
            sets.append(f"engine.{k}={scaled_value(spec['engine'][k], f, r9['v1']['value_format'])}")
    return sets


def out_root_for(r9: dict, variant: str, mode: str) -> str:
    return r9["out_root_template"].format(variant=variant, mode=mode)


def candidate_multiples(b3: dict) -> List[Tuple[float, bool]]:
    """[(multiple, is_extra_labelled)] sorted ascending: the declared multiples and the labelled extras (no duplicates)."""
    core = [float(m) for m in b3["multiples"]]
    extra = [float(m) for m in b3.get("multiples_extra_labelled") or [] if float(m) not in core]
    return sorted([(m, False) for m in core] + [(m, True) for m in extra])


def caps_for(picked: int, b3: dict) -> List[Dict[str, Any]]:
    """The CAPPED arms: the cap the closed-curve rule picked, the sensitivity caps and the labelled extras, ascending, no duplicates."""
    sens = [int(c) for c in b3["caps_sensitivity"]]
    extra = [int(c) for c in b3.get("caps_extra_labelled") or []]
    allc = sorted(set(sens) | set(extra) | {int(picked)})
    return [{"cap": c, "picked": c == int(picked), "sensitivity": c in sens, "extra_labelled": c in extra and c not in sens} for c in allc]


def registration_map(reg: dict, window: Optional[dict] = None) -> Dict[float, List[float]]:
    """hi (largest all-stable multiple of the edge grid) -> the two test points the registration rule gives (empty window not possible on this grid)."""
    w = {"lo": float(reg["window_lo"]), "point_fractions": reg["point_fractions"], "round_to": reg["round_to"], "empty_if_hi_at_most": 1.1}
    if window:
        w["empty_if_hi_at_most"] = window["empty_if_hi_at_most"]
    return {float(h): window_points(float(h), w) for h in reg["edge_grid"]}


def used_by(reg: dict, mult: float, window: Optional[dict] = None) -> str:
    """Which possible real edges hi make the registration use ``mult``, and as which of the two points (low / high)."""
    out = []
    for h, pts in registration_map(reg, window).items():
        for i, p in enumerate(pts):
            if abs(p - float(mult)) < 1e-9:
                out.append(f"hi = {h:g} ({'low' if i == 0 else 'high'})")
    return "; ".join(out) if out else "none"


def pair_verdict(cl: pd.DataFrame, cap: int, need: int) -> Dict[str, Any]:
    """The verdicts of one (multiple, cap) from the classified runs ``cl`` of ONE multiple (arms ``burst``, ``no_burst``, ``cap_<cap>``; columns seed, trapped, recovered):
    the per-arm counts and PASS (each of BURST trapped, NOBURST good = recovered, CAPPED recovered in >= ``need`` seeds) and the same-seed count and PASS (the number of
    seeds in which all three hold at once, >= ``need``)."""
    b = cl[cl["arm"] == "burst"].set_index("seed")
    n = cl[cl["arm"] == "no_burst"].set_index("seed")
    c = cl[cl["arm"] == f"cap_{int(cap)}"].set_index("seed")
    seeds = sorted(set(b.index) & set(n.index) & set(c.index))
    bt = b.loc[seeds, "trapped"].astype(bool)
    ng = n.loc[seeds, "recovered"].astype(bool)
    cr = c.loc[seeds, "recovered"].astype(bool)
    ss = int((bt & ng & cr).sum())
    return {"n_seeds": len(seeds), "need": int(need), "burst_trapped": int(bt.sum()), "noburst_good": int(ng.sum()), "cap_recovered": int(cr.sum()),
            "cap_trapped": int(c.loc[seeds, "trapped"].astype(bool).sum()),
            "per_arm_pass": bool(bt.sum() >= need and ng.sum() >= need and cr.sum() >= need), "same_seed_count": ss, "same_seed_pass": bool(ss >= need)}


# ======================================================================= stage: pairs_all (B3v)
def stage_pairs_all(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    r7 = r7_block(cfg)
    b3 = cfg["r9"]["b3v"]
    pr = r7["pairs"]
    c = r7["classify"]
    name = r7["record_workload"]
    lm = stage_summary(args.out_root, "lambda_miss")["workloads"][name]
    lam_miss, tok = float(lm["lambda_miss_turns"]), float(lm["token_rate"])
    picked = int(stage_summary(args.out_root, "curves")["workloads"][name]["cap_n"])
    caps = caps_for(picked, b3)
    mults = candidate_multiples(b3)
    ctx = start("pairs_all", cfg, args, repo_dir)
    ev = [float(x) for x in c["eval_window_rel_to_burst_s"]]
    burst_n = int(pr["burst_n"])
    arms: Dict[str, dict] = {"no_burst": {"burst_n": 0, "cap": None}, "burst": {"burst_n": burst_n, "cap": None}}
    for k in caps:
        arms[f"cap_{k['cap']}"] = {"burst_n": burst_n, "cap": int(k["cap"])}
    cls_all: List[pd.DataFrame] = []
    wins_all: List[pd.DataFrame] = []
    summ: Dict[str, Any] = {"workload": name, "lambda_miss_turns": lam_miss, "token_rate_miss": tok, "cap_picked": picked, "caps": caps,
                            "multiples": [{"mult": m, "extra_labelled": e} for m, e in mults], "arms": list(arms), "points": {},
                            "dirs": {s: str(stage_dir(args.out_root, s)) for s in ("lambda_miss", "curves", "edge")}}
    for mult, extra in mults:
        sec = burst_section(cfg, r7, name, lam_miss, mult, burst_n=burst_n, width=pr["burst_width_s"], warmup=pr["warmup_s"], after=pr["after_s"],
                            seeds=pr["seeds"], arms=arms)
        res = run_burst(cfg, sec, workers=args.workers)
        runs, wins, _ = res.frames
        key = f"{name}|{mult:g}"
        cl = classify_burst_frames(runs, wins, lam_miss, tok, c, ev, {"workload": name, "mult": mult, "call": key})
        cls_all.append(cl)
        w2 = wins.copy()
        w2.insert(0, "call", key)
        wins_all.append(w2)
        n = int(cl[cl["arm"] == "burst"]["seed"].nunique())
        need = need_count(n, float(c["pass_min_frac"]))
        per_cap = {str(k["cap"]): pair_verdict(cl, int(k["cap"]), need) for k in caps}
        p0 = per_cap[str(picked)]
        summ["points"][f"{mult:g}"] = {"lam": mult * lam_miss, "extra_labelled": extra, "n_seeds": n, "need": need,
                                       "burst_trapped": p0["burst_trapped"], "noburst_good": p0["noburst_good"],
                                       "burst_indeterminate": int(cl[cl["arm"] == "burst"]["indeterminate"].sum()),
                                       "noburst_trapped": int(cl[cl["arm"] == "no_burst"]["trapped"].sum()), "per_cap": per_cap}
        print(f"[pairs_all] x{mult:g}: BURST trapped {p0['burst_trapped']}/{n}, NOBURST good {p0['noburst_good']}/{n}; CAPPED recovered by cap: "
              + ", ".join(f"{k['cap']}:{per_cap[str(k['cap'])]['cap_recovered']}" for k in caps)
              + f"; PASS(picked cap {picked}) per-arm {p0['per_arm_pass']} same-seed {p0['same_seed_pass']}", flush=True)
    concat(cls_all).to_csv(ctx.out / "classified_runs.csv", index=False)
    concat(wins_all).to_csv(ctx.out / "windows.csv", index=False)
    return end(ctx, args, pr["seeds"], {"stage": "pairs_all", "only": None, "arms": list(arms)}, summ)


# ======================================================================= tables
def fmt_range(x: pd.Series, f: str = "{:.3f}") -> str:
    return "n/a" if len(x) == 0 else (f.format(float(x.min())) if float(x.min()) == float(x.max()) else f"{f.format(float(x.min()))} to {f.format(float(x.max()))}")


def b3_tables(cl: pd.DataFrame, summ: dict, r9: dict, window: dict, z: float, hit_lo: float) -> Tuple[str, Dict[str, Any]]:
    """The B3v tables of one (variant, mode) from its classified runs ``cl`` and stage summary ``summ``: per multiple (BURST / NOBURST arms and the trapped runs'
    diagnostics), per (multiple, cap) (CAPPED recovered, both PASS verdicts) and the per-seed classes at the picked cap."""
    reg = r9["registration"]
    picked = int(summ["cap_picked"])
    caps = summ["caps"]
    rows_a, rows_b, rows_c = [], [], []
    head: Dict[str, Any] = {"cap_picked": picked, "points": {}}
    for mkey, p in summ["points"].items():
        mult = float(mkey)
        n = int(p["n_seeds"])
        g = cl[np.isclose(cl["mult"], mult)]
        gb, gn = g[g["arm"] == "burst"], g[g["arm"] == "no_burst"]
        tr = gb[gb["trapped"].astype(bool)]
        tag = " (extra)" if p["extra_labelled"] else ""
        rows_a.append({"x lambda_miss": f"{mult:g}{tag}", "lambda (sessions/s)": p["lam"], "real registration uses it if": used_by(reg, mult, window),
                       "BURST trapped": fs(p["burst_trapped"], n, z), "NOBURST good": fs(p["noburst_good"], n, z),
                       "BURST stuck (hit < %g)" % hit_lo: fs(int((gb["hit"] < hit_lo).sum()), n, z),
                       "trapped runs: token rate / all-miss rate": fmt_range(tr["token_ratio"]) if len(tr) else "none trapped",
                       "trapped runs: mean backlog": float(tr["backlog"].mean()) if len(tr) else float("nan"),
                       "BURST hit (mean of runs)": float(gb["hit"].mean()), "NOBURST backlog (mean)": float(gn["backlog"].mean()),
                       "BURST classes by seed": letters(gb), "NOBURST classes by seed": letters(gn)})
        hp: Dict[str, Any] = {"lam": p["lam"], "burst_trapped": p["burst_trapped"], "noburst_good": p["noburst_good"], "n_seeds": n,
                              "trapped_token_ratio_min": float(tr["token_ratio"].min()) if len(tr) else None,
                              "trapped_token_ratio_max": float(tr["token_ratio"].max()) if len(tr) else None,
                              "trapped_backlog_mean": float(tr["backlog"].mean()) if len(tr) else None, "caps": {}}
        for k in caps:
            c = int(k["cap"])
            v = p["per_cap"][str(c)]
            gc = g[g["arm"] == f"cap_{c}"]
            lab = f"{c}" + (" *" if k["picked"] else "") + (" (extra)" if k["extra_labelled"] else "")
            rows_b.append({"x lambda_miss": f"{mult:g}{tag}", "cap": lab, "BURST trapped": fs(v["burst_trapped"], n, z), "NOBURST good": fs(v["noburst_good"], n, z),
                           "CAPPED recovered": fs(v["cap_recovered"], n, z), "CAPPED trapped": v["cap_trapped"],
                           "PASS per-arm (each >= %d)" % v["need"]: "PASS" if v["per_arm_pass"] else "FAIL",
                           "same-seed count (all three in one seed)": fs(v["same_seed_count"], n, z),
                           "PASS same-seed (>= %d)" % v["need"]: "PASS" if v["same_seed_pass"] else "FAIL",
                           "CAPPED backlog (mean)": float(gc["backlog"].mean()), "CAPPED hit (mean)": float(gc["hit"].mean())})
            hp["caps"][str(c)] = v
            if k["picked"]:
                rows_c.append({"x lambda_miss": f"{mult:g}{tag}", "cap": c, "BURST": letters(gb), "NOBURST": letters(gn), "CAPPED": letters(gc)})
        head["points"][mkey] = hp
    txt = ("Per multiple of the variant's own lambda_miss (10 seeds, Wilson 95% intervals). `real registration uses it if` lists the possible real edges hi (largest all-stable "
           "multiple of {1.25, 1.5, 1.75, 2.0, 2.5, 3.0}) for which the registration rule gives this multiple, as the low or the high of its two points (a hi capped by mu*/lambda_ref "
           "can give points off this list; not predicted here). Trapped runs: the uncached-token rate over the evaluation window divided by the all-miss rate of the same variant and "
           "mode, and the mean backlog (waiting requests) over the evaluation window.\n\n" + df_md(pd.DataFrame(rows_a), "{:.4g}") +
           "\n\nPer multiple and cap (`*` = the cap the B4v rule picks; `(extra)` = labelled extra, not in the task list). CAPPED recovered is out of the same 10 seeds; "
           "BURST and NOBURST columns repeat the per-multiple arms. Both verdicts: per-arm = each of the three conditions in >= need seeds; same-seed = the number of seeds in "
           "which all three conditions hold at once is >= need. The real registration uses the cap the REAL closed-curve rule picks, which is unknown here: read the row of the "
           "real cap.\n\n" + df_md(pd.DataFrame(rows_b), "{:.4g}") +
           "\n\nPer-seed classes at the picked cap (T trapped, R recovered, I indeterminate = hit < 0.2 but not trapped, O other; seed order 0-9):\n\n" +
           df_md(pd.DataFrame(rows_c)))
    return txt, head


def reg_table(reg: dict, window: dict) -> str:
    rows = [{"real edge hi (x lambda_ref)": h, "test point low": pts[0], "test point high": pts[1]} for h, pts in registration_map(reg, window).items()]
    return df_md(pd.DataFrame(rows), "{:.4g}")


def block_tables(cfg: dict, variant: str, mode: str, repo_dir: Path) -> Tuple[str, Dict[str, Any]]:
    """The markdown block and the headline numbers of one (variant, mode) from its result tree."""
    r7, r9 = cfg["r7"], cfg["r9"]
    z = float(r7["wilson_z"])
    name = r7["record_workload"]
    out_root = out_root_for(r9, variant, mode)
    S = Stages(out_root, r7.get("stages"))
    levels = [0.5, 0.9, 0.2]
    md: List[str] = []
    head: Dict[str, Any] = {"out_root": out_root}
    real_lm = float(r9["real_inputs"]["lambda_miss_turns_sessions_per_s"])
    target = float(r9["real_inputs"]["all_miss_token_rate_tok_per_s"])

    md.append("### B1v. All-miss capacity lambda_miss (cache off, closed POP %d, window [%g, %g) s, seeds %s)\n" % (
        int(r7["lambda_miss"]["population"]), float(r7["lambda_miss"]["warmup_s"]), float(r7["lambda_miss"]["horizon_s"]), ",".join(str(s) for s in r7["lambda_miss"]["seeds"])))
    if S.ok("lambda_miss"):
        md.append(t_workloads(S, r7) + "\n")
        w = S.summary("lambda_miss")["workloads"][name]
        head["B1v"] = {"lambda_miss_turns": w["lambda_miss_turns"], "lambda_miss_turns_sd": w["lambda_miss_turns_sd"], "lambda_miss_sessions": w["lambda_miss_sessions"],
                       "token_rate": w["token_rate"], "busy": w["busy"], "token_rate_over_vllm_target": w["token_rate"] / target,
                       "lambda_miss_over_vllm_real": w["lambda_miss_turns"] / real_lm, **{k: v for k, v in w.items() if k.startswith("check_pop")}}
        txt = (f"Reference values (the two real vLLM numbers of the task, not outputs of the simulator): measured all-miss uncached rate {target:,.0f} tok/s, measured "
               f"lambda_miss {real_lm:g} sessions/s. This block: token rate {w['token_rate']:,.1f} tok/s = {w['token_rate'] / target:.4f} x the vLLM rate; lambda_miss "
               f"{w['lambda_miss_turns']:.5f} sessions/s = {w['lambda_miss_turns'] / real_lm:.4f} x the vLLM value.")
        if variant == "v1":
            f = v1_factor(r9, mode)
            chk = json.loads((repo_dir / CAL_DIR / f"factor_check_{mode}.json").read_text())
            same = abs(float(chk["accepted_rate"]) - float(w["token_rate"])) == 0.0
            head["B1v"]["v1_factor"] = f
            head["B1v"]["bit_identical_to_the_frozen_check"] = bool(same)
            head["B1v"]["check_accepted_rate"] = float(chk["accepted_rate"])
            txt += (f" V1 factor f = {f:g} on {', '.join(r9['v1']['scaled_engine_keys'])} (frozen from the quick B1 check, accepted rate {chk['accepted_rate']:,.2f} tok/s, "
                    f"{(chk['accepted_rate'] / target - 1) * 100:+.2f}% of the target); the main B1v token rate equals the check's accepted rate exactly: **{same}**. The token rate is "
                    "FITTED to the target (by construction, not a prediction); lambda_miss is a by-product.")
        md.append(txt + "\n")
    else:
        md.append("**stage `lambda_miss` NOT RUN**\n")

    md.append("### B4v. Closed curve mu(n) and hit fraction (cache on, seeds %s, window [%g, %g) s)\n" % (
        seed_span(r7["curve"]["seeds"]), float(r7["curve"]["warmup_s"]), float(r7["curve"]["horizon_s"])))
    if S.ok("curves"):
        md.append(t_curves(S, r7) + "\n")
        cs = S.summary("curves")["workloads"][name]
        runs = S.csv("curves", "curve_runs.csv")
        lmk = curve_landmarks(cs, runs, levels)
        head["B4v"] = lmk
        lam_ref = head.get("B1v", {}).get("lambda_miss_turns")
        rows = [{"landmark": "peak n (first argmax of the seed-mean turns-based mu)", "value": lmk["peak_n"]},
                {"landmark": "peak mu (turns-based sessions/s)", "value": lmk["peak_mu_turns"]},
                {"landmark": "peak mu / lambda_miss (the registration's mu* / lambda_ref reading)", "value": (lmk["peak_mu_turns"] / lam_ref) if lam_ref else float("nan")},
                {"landmark": "hit fraction at the peak n", "value": lmk["hit_at_peak"]},
                {"landmark": "cap n (smallest grid n with seed-mean mu >= 0.95 x peak mu)", "value": lmk["cap_n"]},
                {"landmark": "[sessions-based] peak n / peak mu / cap n", "value": f"{lmk['peak_n_sessions_based']} / {lmk['peak_mu_sessions']:.4g} / {lmk['cap_n_sessions_based']}"}]
        for lv, c in lmk["hit_crossing"].items():
            rows.append({"landmark": f"n at which the seed-mean hit fraction falls through {lv} (linear interpolation)", "value": c})
        rows.append({"landmark": "largest grid n with seed-mean hit >= 0.9", "value": lmk["largest_n_with_hit_at_least_top_level"]})
        rows.append({"landmark": "per-seed n at which the hit fraction falls through 0.5", "value": ", ".join(f"s{s}: {c:.1f}" for s, c in lmk["hit_crossing_first_level_by_seed"].items())})
        rows.append({"landmark": f"mu({lmk['last_n']}) / peak mu", "value": lmk["mu_last_over_peak"]})
        # the cap margin: how far the first grid n below the cap is from the 95% threshold, and the cap's own margin (the cap is knife-edge when either is within ~1%)
        ns = sorted(int(n) for n in cs["mu_turns_by_n"])
        thr = 0.95 * float(cs["peak_mu_turns"])
        below = [n for n in ns if n < int(cs["cap_n"])]
        marg = {"cap_margin_rel": float(cs["mu_turns_by_n"][str(cs["cap_n"])]) / thr - 1.0}
        if below:
            marg["next_below_margin_rel"] = float(cs["mu_turns_by_n"][str(below[-1])]) / thr - 1.0
        head["B4v"]["cap_margins"] = marg
        rows.append({"landmark": "cap margins: mu(cap) / (0.95 peak) - 1; mu(next grid n below the cap) / (0.95 peak) - 1",
                     "value": f"{marg['cap_margin_rel']:+.4f}; " + (f"{marg['next_below_margin_rel']:+.4f}" if below else "n/a")})
        md.append("Landmarks of the closed curve:\n\n" + df_md(pd.DataFrame(rows), "{:.4g}") + "\n")
        per = runs.sort_values(["n", "seed"])
        tab = []
        for n, g in per.groupby("n"):
            tab.append({"n": int(n), "mu turns-based by seed": " / ".join(f"{x:.4f}" for x in g["mu_turns"]), "hit by seed": " / ".join(f"{x:.2f}" for x in g["hit_rate"])})
        md.append("Per-seed values (seed order 0-9; a spread across seeds marks a bistable cliff cell):\n\n" + df_md(pd.DataFrame(tab)) + "\n")
    else:
        md.append("**stage `curves` NOT RUN**\n")

    md.append("### B2v. From-empty open-loop stability (cache on, B2 rule, %g s, %d seeds)\n" % (float(r7["edge"]["horizon_s"]), len(r7["edge"]["seeds"])))
    if S.ok("edge") and S.ok("lambda_miss"):
        md.append(t_edge(S, r7, z) + "\n")
        es = S.summary("edge")["workloads"][name]
        v = S.csv("edge", "edge_verdicts.csv")
        elm = edge_landmarks(es, v, float(es["lambda_miss_turns"]))
        elm["hi_in_real_units_sessions_per_s"] = elm["hi"] * real_lm
        head["B2v"] = elm
        txt = (f"**Edge hi = {elm['hi']:g} x lambda_miss = {elm['hi_sessions_per_s']:.4f} sessions/s in this block's own units** (contiguous all-stable rule; lambda_miss = "
               f"{elm['lambda_miss']:.5f}; largest all-stable multiple irrespective of contiguity: {elm['hi_largest_all_stable']:g}). In multiples of the REAL lambda_miss "
               f"({real_lm:g} sessions/s) the same multiple is {elm['hi'] * real_lm:.4f} sessions/s (the dimensionless-behaviour reading). ")
        if elm["window_empty"]:
            txt += "The window is EMPTY (hi <= 1.1). "
        if elm["censored_at_grid_top"]:
            txt += f"**CENSORED**: every multiple up to {elm['grid_top']:g} is all-stable, the edge is >= {elm['grid_top']:g} x. "
        txt += (f"Supplementary: the stable fraction falls through 0.95 at {elm['stable_frac_crossing_0.95']:.3g} x and through 0.5 at {elm['stable_frac_crossing_0.5']:.3g} x "
                "(linear interpolation between grid multiples; NaN = never).")
        md.append(txt + "\n")
        md.append("Test points of the registration rule for every possible real edge hi (points 1 + (hi - 1)/3 and 1 + 2 (hi - 1)/3 rounded to 0.05):\n\n" + reg_table(r9["registration"], r7["window"]) + "\n")
    else:
        md.append("**stage `edge` NOT RUN**\n")

    md.append("### B3v. Paired NOBURST / BURST / CAPPED test at every candidate multiple (burst %d sessions in %g s at t = %g s, %d seeds, evaluation window = last 2500 s)\n" % (
        int(r7["pairs"]["burst_n"]), float(r7["pairs"]["burst_width_s"]), float(r7["pairs"]["warmup_s"]), len(r7["pairs"]["seeds"])))
    try:
        d_pa = stage_dir(out_root, "pairs_all")
    except FileNotFoundError:
        d_pa = None
    if d_pa is not None:
        summ = json.loads((d_pa / "summary.json").read_text())
        cl = pd.read_csv(d_pa / "classified_runs.csv")
        t, h = b3_tables(cl, summ, r9, r7["window"], z, float(r7["classify"]["indeterminate_hit_below"]))
        md.append(t + "\n")
        head["B3v"] = h
        if "B2v" in head:
            pts = head["B2v"]["points"]
            head["B3v"]["sim_registration_points"] = pts
            md.append("The simulator's own registration (hi = %g): test points %s; verdicts at the picked cap %d are the rows of those multiples above.\n" % (
                head["B2v"]["hi"], ", ".join(f"{p:g}" for p in pts) or "none (empty window)", h["cap_picked"]))
    else:
        md.append("**stage `pairs_all` NOT RUN**\n")
    return "\n".join(md), head


def seed_span(seeds: Sequence[int]) -> str:
    s = [int(x) for x in seeds]
    return f"{s[0]}-{s[-1]}" if s == list(range(s[0], s[-1] + 1)) else ",".join(str(x) for x in s)


# ======================================================================= summary across the four blocks
def overview(cfg: dict, heads: Dict[Tuple[str, str], Dict[str, Any]]) -> str:
    r9 = cfg["r9"]
    real_lm = float(r9["real_inputs"]["lambda_miss_turns_sessions_per_s"])
    rows1, rows2 = [], []
    for (variant, mode), h in heads.items():
        b1, b4, b2, b3 = h.get("B1v"), h.get("B4v"), h.get("B2v"), h.get("B3v")
        rows1.append({"variant": variant.upper(), "mode": mode, "lambda_miss turns-based (sessions/s)": b1["lambda_miss_turns"] if b1 else float("nan"),
                      "all-miss token rate (tok/s)": b1["token_rate"] if b1 else float("nan"),
                      "peak n": b4["peak_n"] if b4 else None, "peak mu (sessions/s)": b4["peak_mu_turns"] if b4 else float("nan"),
                      "peak mu / lambda_miss": (b4["peak_mu_turns"] / b1["lambda_miss_turns"]) if (b4 and b1) else float("nan"),
                      "cap n (B4v rule)": b4["cap_n"] if b4 else None,
                      "n at hit 0.5": b4["hit_crossing"]["0.5"] if b4 else float("nan"),
                      "edge hi (x lambda_miss)": b2["hi"] if b2 else float("nan"),
                      "edge in real units (hi x %g)" % real_lm: b2["hi"] * real_lm if b2 else float("nan"),
                      "edge censored": b2["censored_at_grid_top"] if b2 else None})
        if b3:
            for mkey, p in b3["points"].items():
                cap_p = str(b3["cap_picked"])
                v = p["caps"][cap_p]
                rows2.append({"variant": variant.upper(), "mode": mode, "x lambda_miss": float(mkey), "picked cap": b3["cap_picked"], "BURST trapped": f"{v['burst_trapped']}/{v['n_seeds']}",
                              "NOBURST good": f"{v['noburst_good']}/{v['n_seeds']}", "CAPPED recovered": f"{v['cap_recovered']}/{v['n_seeds']}",
                              "PASS per-arm": "PASS" if v["per_arm_pass"] else "FAIL", "same-seed count": f"{v['same_seed_count']}/{v['n_seeds']}",
                              "PASS same-seed": "PASS" if v["same_seed_pass"] else "FAIL"})
    return ("Landmarks per variant and mode:\n\n" + df_md(pd.DataFrame(rows1), "{:.4g}") +
            "\n\nB3v at the cap the B4v rule picks, every candidate multiple (the full tables, with the other caps, are in the blocks below):\n\n" + df_md(pd.DataFrame(rows2), "{:.4g}"))


# ======================================================================= provenance
def provenance(cfg: dict, spec_path: Path, repo_dir: Path) -> str:
    r9 = cfg["r9"]
    sha = sha256_of(spec_path)
    txt = (f"Spec: `{spec_path.as_posix()}` (sha256 `{sha}`; the first commit of the spec, before any run, had sha256 recorded in the notes); KV pool {int(r9['kv_pool_tokens']):,} tokens; "
           "base chain `configs/prefix_meta_r5.yaml` -> `configs/prefix_meta.yaml`; interpreter `C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe`; "
           "at most 6 worker processes (the stages run one after the other).\n\n")
    grand = 0.0
    for variant in r9["variants"]:
        for mode, m in r9["modes"].items():
            out_root = out_root_for(r9, variant, mode)
            S = Stages(out_root, list(STAGES_ALL))
            rows, cmds, total = [], [], 0.0
            for s in S.stages:
                if not S.ok(s):
                    rows.append({"stage": s, "result dir": "NOT RUN"})
                    continue
                mt = S.meta(s)
                seeds = mt.get("seeds", [])
                cfg_copy = S.dir[s] / "config.yaml"
                rows.append({"stage": s, "result dir": S.dir[s].as_posix(), "commit": mt["git"]["commit"][:9], "dirty": mt["git"]["dirty"],
                             "seeds": f"{seeds[0]}..{seeds[-1]} ({len(seeds)})" if seeds else "", "start": mt["start_time"], "wall s": round(mt["wall_s"], 1),
                             "spec copy identical to the committed file": cfg_copy.exists() and sha256_of(cfg_copy) == sha,
                             "overrides": " ".join(mt.get("overrides") or []) or "-"})
                total += float(mt["wall_s"])
                cmds.append(" ".join(mt["argv"]))
            grand += total
            txt += (f"**{variant.upper()} / {mode}** (`engine.batching` = `{m['batching']}`, out-root `{out_root}`):\n\n" + df_md(pd.DataFrame(rows)) +
                    f"\n\nRecorded stage wall time: {total:.0f} s ({total / 60:.1f} min). Commands (argv as recorded in each `meta.json`; run from the worktree root):\n\n```\n" +
                    "\n".join(cmds) + "\n```\n\n")
    return txt + f"Total recorded stage wall time over the four trees: {grand:.0f} s ({grand / 60:.1f} min).\n"


# ======================================================================= report / assemble
def cmd_report(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    cfg = load_probe_config(str(spec_path), repo_dir, args.set)
    r9 = cfg["r9"]
    cfg_eff = {k: v for k, v in cfg.items() if k != "preregistration_file"}
    ctx = begin("r9_vllm_report", "r9_vllm_report", cfg_eff, cfg_eff, args, repo_dir)
    parts: List[str] = []
    heads: Dict[Tuple[str, str], Dict[str, Any]] = {}
    blocks: List[str] = []
    for variant in r9["variants"]:
        for i, (mode, m) in enumerate(r9["modes"].items()):
            t, h = block_tables(cfg, variant, mode, repo_dir)
            heads[(variant, mode)] = h
            blocks.append(f"## {variant.upper()} / `{mode}` ({'PRIMARY' if i == 0 else 'SECONDARY'}): engine.batching = `{m['batching']}`, KV pool {int(r9['kv_pool_tokens']):,} tokens\n\n" + t)
    parts.append("## Overview\n\n" + overview(cfg, heads) + "\n")
    parts.extend(blocks)
    tables = "\n".join(parts)
    (ctx.out / "tables.md").write_text(tables, encoding="utf-8")
    (ctx.out / "summary.json").write_text(json.dumps({f"{v}_{m}": h for (v, m), h in heads.items()}, indent=2, default=float))
    (ctx.out / "provenance.md").write_text(provenance(cfg, spec_path, repo_dir), encoding="utf-8")
    for variant in r9["variants"]:                  # small per-stage CSV summaries, copied so the report dir is self-contained
        for mode in r9["modes"]:
            S = Stages(out_root_for(r9, variant, mode), list(STAGES_ALL))
            for s in S.stages:
                if S.ok(s):
                    for name in ("classified_runs.csv", "edge_verdicts.csv", "lambda_miss_runs.csv", "curve_runs.csv", "summary.json"):
                        src = S.dir[s] / name
                        if src.exists():
                            (ctx.out / f"{variant}_{mode}_{s}_{name}").write_bytes(src.read_bytes())
    finish(ctx, [], {"stage": "report"})
    print(tables)
    print("result dir:", ctx.out)
    return ctx.out


def latest_report_dir(out_root: str) -> Path:
    base = Path(out_root) / "r9_vllm_report"
    ds = sorted(d for d in base.iterdir() if d.is_dir() and (d / "tables.md").exists())
    if not ds:
        raise FileNotFoundError(f"no report under {base}")
    return ds[-1]


def cmd_assemble(spec_path: Path, args: argparse.Namespace, repo_dir: Path) -> Path:
    rd = latest_report_dir(args.out_root)
    tables = (rd / "tables.md").read_text(encoding="utf-8")
    prov = (rd / "provenance.md").read_text(encoding="utf-8")
    head = Path(args.headline).read_text(encoding="utf-8").strip()
    txt = (f"# {TITLE}\n\n{head}\n\n## Provenance: what was run\n\nGenerated by `python -m prefixmeta.r9_vllm_predict assemble` from the report `{rd.as_posix()}` "
           "(the tables below are that report's `tables.md`, verbatim; nothing is retyped).\n\n" + prov + "\n## Tables (generated)\n\n" + tables)
    Path(args.notes).write_text(txt, encoding="utf-8")
    print("wrote", args.notes)
    return Path(args.notes)


# ======================================================================= CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Round 9 vLLM predictions: pairs_all (B3v stage), v1sets, report, assemble")
    ap.add_argument("cmd", choices=["pairs_all", "v1sets", "report", "assemble"])
    ap.add_argument("--spec", "--config", dest="config", default="configs/r9_vllm_predict.yaml")
    ap.add_argument("--workers", type=int, default=6, help="processes (1..6; also capped by the spec's parallel.max_workers)")
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL", help="dotted config override (recorded in meta.json)")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--quick", action="store_true", help="unused (kept for the begin()/finish() provenance helpers)")
    ap.add_argument("--variant", default=None, help="v1sets: v0 | v1")
    ap.add_argument("--mode", default=None, help="v1sets: mixed | separate")
    ap.add_argument("--headline", default=None)
    ap.add_argument("--notes", default="notes/PREDICTIONS_vllm.md")
    return ap


def main(argv: Optional[List[str]] = None, repo_dir: Optional[Path] = None):
    args = build_parser().parse_args(argv)
    repo_dir = repo_dir or Path(__file__).resolve().parent.parent.parent
    if args.cmd == "v1sets":
        if not (args.variant and args.mode):
            raise SystemExit("v1sets needs --variant and --mode")
        spec = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
        sys.stdout.write("".join(s + "\n" for s in variant_sets(spec, args.variant, args.mode)))
        return 0
    if args.cmd == "pairs_all":
        if not (1 <= args.workers <= 6):
            raise SystemExit(f"--workers must be in 1..6, got {args.workers}")
        cfg = load_probe_config(args.config, repo_dir, args.set)
        stage_pairs_all(cfg, args, repo_dir)
        return 0
    if args.cmd == "report":
        return cmd_report(Path(args.config), args, repo_dir)
    if not args.headline:
        raise SystemExit("assemble needs --headline")
    return cmd_assemble(Path(args.config), args, repo_dir)


if __name__ == "__main__":      # pragma: no cover
    r = main()
    sys.exit(r if isinstance(r, int) else 0)
