"""Write configs/workload_trace_<source>.yaml (proposed simulator workloads) from results/traces_summary/<source>/summary.json and the
normalised trace CSVs of the same source.

  python -I scripts/traces/make_configs.py SOURCE --config configs/traces_analysis.yaml

Field names are exactly those of prefixmeta.workload.WorkloadParams on branch r7/robustness (commit 8c08883, opt-in tool-time laws):
  tool_time_dist: lognormal   tool_time_mean_s, tool_time_cv                         (runs with the round-6 code too)
  tool_time_dist: bimodal     tool_time_lo_s, tool_time_hi_s, tool_time_p_hi         (explicit P(hi); needs 8c08883)
  tool_time_dist: empirical   tool_time_quantiles + tool_time_quantile_levels        (levels strictly increasing from 0.0 to 1.0; needs 8c08883)
For the empirical law tool_time_mean_s / tool_time_cv are not used by the sampler; they are set to the EXACT moments of the table
(prefixmeta.workload.empirical_moments), which the simulator's reports print as the tool-time mean and CV.

Token and turn mapping (see notes/lit/AGENT_TRACES.md):
  initial_context_tokens = mean prompt size of the first model call of a session (conversation / trajectory)
  new_prompt_tokens      = mean tokens appended between two consecutive calls beyond the previous input + output (delta_ctx),
                           context-compaction events (negative delta) excluded, winsorised at the 99.9th percentile
  decode_tokens          = mean output tokens per model call (winsorised at the 99.9th percentile)
  mean_turns, max_turns  = geometric parameter such that E[min(Geometric(1/mean_turns), max_turns)] equals the observed mean number of
                           model calls per agentic episode capped at max_turns (the workload of record's cap, 60)
Tool-time series: TraceLab per-round value (last tool result minus last tool request); mini-SWE-agent per-step command time. All laws
are fitted to the series capped at analysis.cap_s (600 s). The two-component lognormal mixture has no simulator counterpart; its fit is
quoted in a comment and in summary.json only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # our own scripts/traces, not the data directory
from common import empirical_moments, quantile_levels, two_point_match  # noqa: E402


def fmt_list(xs, nd=5) -> str:
    return "[" + ", ".join(f"{x:.{nd}g}" for x in xs) + "]"


def tracelab_series(norm: str, col: str) -> np.ndarray:
    r = pd.read_csv(os.path.join(norm, "rounds.csv"), usecols=["n_tools", "classes", col])
    r = r[(r.n_tools > 0) & (~r.classes.fillna("").str.contains("human"))]
    return r[col].dropna().to_numpy()


def mini_series(norm: str, col: str) -> np.ndarray:
    return pd.read_csv(os.path.join(norm, "calls.csv"), usecols=[col])[col].dropna().to_numpy()


# which summary series / token group is the headline of each source; `load(norm)` re-reads the raw series (checked against the summary)
HEAD = {
    "tracelab": {"series": "round_z_nohuman|all", "group": "all", "label": "SyFI TraceLab (Claude Code + Codex CLI sessions)",
                 "series_desc": "per-turn idle interval (last tool result - last tool request of the model call), tool calls of all kinds except "
                                "human-interaction tools (AskUserQuestion, ExitPlanMode, ...), wall clock as logged",
                 "load": lambda norm: tracelab_series(norm, "z_round_s"),
                 "alt": {"series": "round_gap_next_nohuman|all",
                         "name": "workload_empirical_idle_gap",
                         "desc": "inter-request idle time = next request ready minus the end of this call's model output (tool time plus output-to-tool-call "
                                 "and result-to-request overhead and any human wait for permission prompts); an upper-bound sensitivity, not the tool time",
                         "load": lambda norm: tracelab_series(norm, "gap_next_s")}},
    "mini_swe_v2": {"series": "phase_wall|all", "group": "all", "label": "mini-SWE-agent v2.0.0 on SWE-bench Verified (5 models, 100 paired instances each)",
                    "series_desc": "per-step shell command wall time in the SWE-bench docker container (60 s harness timeout, censored)",
                    "load": lambda norm: mini_series(norm, "wall_s"), "alt": None},
}


def empirical_block(x: np.ndarray, cap: float, summary_q: list[float] | None) -> dict:
    """Quantile table of the series capped at `cap` on the grid of common.quantile_levels, with the exact moments of the table."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x) & (x >= 0)]
    if summary_q is not None:       # the re-read series must be the one the summary was computed from
        got = np.percentile(x, np.arange(1, 100))
        if not np.allclose(got, summary_q, rtol=1e-5, atol=1e-9):
            raise SystemExit("series re-read from the normalised CSV does not reproduce summary.json quantiles_1_99")
    xc = np.minimum(x, cap)
    lv = quantile_levels()
    vals = np.quantile(xc, lv)
    vals = [float(f"{v:.5g}") for v in vals]
    lv_r = [float(f"{u:.7g}") for u in lv]
    assert all(b >= a for a, b in zip(vals[:-1], vals[1:])) and all(b > a for a, b in zip(lv_r[:-1], lv_r[1:]))
    m, cv = empirical_moments(lv_r, vals)
    return {"levels": lv_r, "values": vals, "mean": m, "cv": cv, "sample_mean_capped": float(xc.mean()),
            "sample_cv_capped": float(xc.std(ddof=1) / xc.mean()), "sample_mean_raw": float(x.mean()), "median": float(np.median(x)),
            "n": int(x.size), "frac_ge_cap": float(np.mean(x >= cap)), "max_raw": float(x.max())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--config", default="configs/traces_analysis.yaml")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    src = cfg["sources"][a.source]
    M = int(cfg["analysis"]["max_turns_workload_of_record"])
    cap = float(cfg["analysis"]["cap_s"])
    with open(os.path.join(src["summary_dir"], "summary.json"), encoding="utf-8") as f:
        S = json.load(f)
    h = HEAD[a.source]
    ser = S["series"][h["series"]]
    tok = S["tokens"][h["group"]]
    trn = S["turns"][h["group"]]
    L0 = tok["first_input_total_per_session"]["mean"]
    delta = tok["delta_ctx_nonneg"]["mean_w999"]
    dec = tok["output_tokens_per_round"]["mean_w999"]
    geo = trn["geometric_match_agentic"][str(M)]
    mean_turns = geo["mean_turns_geometric"]
    cap_stats = ser["capped600"]
    ln = ser["lognormal_capped600"]
    mixp = ser["mixture2_pos_capped600"]
    atom = ser["atom_frac_lt_floor"]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "scripts/traces"], capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("scripts/traces has uncommitted changes; commit them first so the config header names the script version that wrote it")

    x_head = h["load"](src["norm_dir"])
    E = empirical_block(x_head, cap, ser["quantiles_1_99"])
    if abs(E["sample_mean_capped"] - cap_stats["mean"]) > 1e-9 * max(1.0, cap_stats["mean"]):
        raise SystemExit("re-read series mean does not match summary.json capped600 mean")
    sample_mean, sample_cv = cap_stats["mean"], cap_stats["cv"]
    two = two_point_match(sample_mean, sample_cv, lo=ser["raw"]["median"])
    mp = ln["mean_preserving"]

    lines: list[str] = []
    w = lines.append
    w(f"# PROPOSED simulator workload from real agent traces: {h['label']}.")
    w(f"# Generated by scripts/traces/make_configs.py (repo commit {commit}) from {src['summary_dir']}/summary.json and {src['norm_dir']}/*.csv. Not used by any run yet.")
    w("# Method, definitions and caveats: notes/lit/AGENT_TRACES.md.")
    w(f"# Tool-time series: {h['series_desc']}. Every law below is fitted to this series capped at {cap:.0f} s.")
    w("#")
    w("# Field names are those of prefixmeta.workload.WorkloadParams on branch r7/robustness (commit 8c08883).")
    w("# `workload`                 tool_time_dist: lognormal    loads with the round-6 code and with 8c08883.")
    w("# `workload_bimodal`         tool_time_dist: bimodal      with the explicit tool_time_p_hi; needs 8c08883.")
    w("# `workload_empirical`       tool_time_dist: empirical    quantile table with explicit levels; needs 8c08883.")
    if h["alt"]:
        w(f"# `{h['alt']['name']}`  empirical table of the {h['alt']['series']} series (see below); needs 8c08883.")
    w("# Each section is a complete `workload:` mapping; use one of them as the `workload` of a probe config or as workload_overrides.")
    w("#")
    w("# Token mapping: initial_context_tokens = mean first-call prompt of a session; new_prompt_tokens = mean tokens appended between two calls beyond the")
    w("# previous input+output (context compactions excluded, winsorised at p99.9); decode_tokens = mean output tokens per call (winsorised at p99.9).")
    w(f"# mean_turns = geometric parameter reproducing the observed mean calls per agentic episode (capped at max_turns = {M}):")
    w(f"# observed mean {geo['target_mean_capped']:.2f} capped, median {trn['episode_rounds_agentic']['median']:.0f}, p90 {trn['episode_rounds_agentic']['p90']:.0f}, p99 {trn['episode_rounds_agentic']['p99']:.0f}.")
    w("# NOTE the trace turn counts are not geometric (see AGENT_TRACES.md); this only matches the mean.")
    w("#")
    c1, c2 = mixp["components"]
    w(f"# Two-component lognormal mixture (no simulator counterpart, not a section): EM fit on the positive part (>= {cfg['analysis']['floor_s']:.2g} s) of the capped series, KS {mixp['ks']:.3f};")
    w(f"# P(tool time < {cfg['analysis']['floor_s']:.2g} s) = {atom:.4g}; weights [{c1['weight']:.4g}, {c2['weight']:.4g}], medians [{c1['median_s']:.4g}, {c2['median_s']:.4g}] s,")
    w(f"# sigma of log(seconds) [{c1['sigma']:.4g}, {c2['sigma']:.4g}].")
    w("")
    base = [
        ("initial_context_tokens", f"{int(round(L0))}"),
        ("new_prompt_tokens", f"{int(round(delta))}"),
        ("decode_tokens", f"{int(round(dec))}"),
        ("mean_turns", f"{mean_turns:.4g}"),
        ("max_turns", f"{M}"),
    ]

    def section(name: str, comment: str = "") -> None:
        w(f"{name}:" + (f"          # {comment}" if comment else ""))
        for k, v in base:
            w(f"  {k}: {v}")

    section("workload", "lognormal: mean fixed to the sample mean, CV chosen to minimise the KS distance")
    w(f"  tool_time_mean_s: {mp['mean']:.4g}          # sample mean of the series capped at {cap:.0f} s (uncapped mean {ser['raw']['mean']:.4g} s)")
    w("  tool_time_dist: lognormal")
    w(f"  tool_time_cv: {mp['cv']:.4g}               # KS {mp['ks']:.3f} at this mean")
    w(f"  # alternatives: MLE lognormal mean {ln['mean_implied']:.4g} s, CV {ln['cv_implied']:.4g} (KS {ln['ks']:.3f}); moment-matched CV {ln['moment_matched']['cv']:.4g} (KS {ln['moment_matched']['ks']:.3f})")
    w("")
    section("workload_bimodal", "two-point law with exactly the sample mean and CV; lo = sample median, hi and P(hi) solve mean and variance")
    w(f"  tool_time_mean_s: {two['mean']:.4g}          # = {sample_mean:.4g}, the sample mean (unused by the sampler when tool_time_p_hi is given)")
    w("  tool_time_dist: bimodal")
    w(f"  tool_time_cv: {two['cv']:.4g}              # = {sample_cv:.4g}, the sample CV (unused by the sampler)")
    w(f"  tool_time_lo_s: {two['lo']:.6g}")
    w(f"  tool_time_hi_s: {two['hi']:.6g}")
    w(f"  tool_time_p_hi: {two['p_hi']:.6g}")
    w("  # crude: two atoms. It carries the mean and the CV of the capped series (the quantities that set the idle-session count and the tail), not its shape.")
    w("")

    def emp_section(name: str, comment: str, EE: dict, extra_comments: list[str]) -> None:
        section(name, comment)
        w(f"  tool_time_mean_s: {EE['mean']:.5g}          # exact mean of the table (sample mean of the capped series {EE['sample_mean_capped']:.5g}; uncapped {EE['sample_mean_raw']:.5g})")
        w("  tool_time_dist: empirical")
        w(f"  tool_time_cv: {EE['cv']:.4g}              # exact CV of the table (sample CV of the capped series {EE['sample_cv_capped']:.4g})")
        for c in extra_comments:
            w("  # " + c)
        w(f"  # {len(EE['values'])} knots; level 0 = minimum, level 1 = {EE['values'][-1]:.5g} s = the {'cap' if EE['frac_ge_cap'] > 0 else 'maximum of the series'}; inverse CDF linear between knots")
        w("  tool_time_quantile_levels: " + fmt_list(EE["levels"], 8))
        w("  tool_time_quantiles: " + fmt_list(EE["values"], 5))

    emp_section("workload_empirical", "empirical quantile table of the tool-time series", E,
                [(f"{E['frac_ge_cap'] * 100:.2f}% of the raw series is at or above the {cap:.0f} s cap" if E['frac_ge_cap'] > 0 else f"no value of the series reaches the {cap:.0f} s cap (maximum {E['max_raw']:.5g} s)")
                 + f"; values above 60 s hold {ser['time_share_gt_60s'] * 100:.0f}% of the raw time;",
                 f"table mean vs sample mean of the capped series: {100 * (E['mean'] / E['sample_mean_capped'] - 1):+.2f}%, CV {100 * (E['cv'] / E['sample_cv_capped'] - 1):+.2f}%."])
    if h["alt"]:
        alt = h["alt"]
        sa = S["series"][alt["series"]]
        Ea = empirical_block(alt["load"](src["norm_dir"]), cap, sa["quantiles_1_99"])
        w("")
        emp_section(alt["name"], "empirical table of the inter-request idle time (sensitivity)", Ea,
                    [alt["desc"] + ".", f"{Ea['frac_ge_cap'] * 100:.2f}% of the raw series is at or above the {cap:.0f} s cap; median {Ea['median']:.3g} s.",
                     f"table mean vs sample mean of the capped series: {100 * (Ea['mean'] / Ea['sample_mean_capped'] - 1):+.2f}%, CV {100 * (Ea['cv'] / Ea['sample_cv_capped'] - 1):+.2f}%."])

    out = os.path.join("configs", f"workload_trace_{a.source}.yaml")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    with open(out, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    want = {"workload", "workload_bimodal", "workload_empirical"} | ({h["alt"]["name"]} if h["alt"] else set())
    assert set(d) == want, d.keys()
    for k, sec in d.items():
        if sec["tool_time_dist"] == "empirical":
            lv, q = sec["tool_time_quantile_levels"], sec["tool_time_quantiles"]
            assert len(lv) == len(q) and lv[0] == 0.0 and lv[-1] == 1.0 and all(b > a for a, b in zip(lv[:-1], lv[1:]))
            assert all(b >= a for a, b in zip(q[:-1], q[1:])) and q[0] >= 0
            m, cv = empirical_moments(lv, q)
            assert abs(m - sec["tool_time_mean_s"]) < 1e-4 * m and abs(cv - sec["tool_time_cv"]) < 1e-3 * cv
    print("wrote", out)


if __name__ == "__main__":
    main()
