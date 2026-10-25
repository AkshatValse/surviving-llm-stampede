"""Render results/traces_summary/<source>/tables.md and results/traces_summary/tables.md from the summary.json files.

  python -I scripts/traces/make_tables.py [--root results/traces_summary]
"""
from __future__ import annotations

import argparse
import json
import math
import os

PCTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]


def f(x, nd=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 100:
        return f"{x:.0f}"
    if abs(x) >= 10:
        return f"{x:.1f}"
    return f"{x:.{nd}g}" if abs(x) < 1 else f"{x:.2f}"


def md(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


def exp_q(mean):
    return [-mean * math.log(1 - p / 100) for p in PCTS]


def time_table(S, names, labels=None):
    rows = []
    for n in names:
        s = S["series"].get(n)
        if not s or s["raw"].get("n", 0) == 0:
            continue
        r, c = s["raw"], s["capped600"]
        rows.append([labels.get(n, n) if labels else n, f"{r['n']:,}", f(r["mean"]), f(r["median"]), f(r["p90"]), f(r["p99"]), f(r["cv"]),
                     f(c["mean"]), f(c["cv"]), f"{100 * s['frac_lt_1s']:.0f}%", f"{100 * s['frac_gt_60s']:.1f}%", f"{100 * s['time_share_gt_60s']:.0f}%"])
    return md(rows, ["series", "n", "mean (s)", "median", "p90", "p99", "CV", "mean cap600", "CV cap600", "<1 s", ">60 s", "share of time >60 s"])


def fit_table(S, names, labels=None):
    rows = []
    for n in names:
        s = S["series"].get(n)
        if not s or "lognormal" not in s:
            continue
        ln, lp, mp = s["lognormal_capped600"], s["lognormal_pos_capped600"], s["mixture2_pos_capped600"]
        c1, c2 = mp["components"]
        mpr = ln["mean_preserving"]
        rows.append([labels.get(n, n) if labels else n, f"{100 * s['atom_frac_lt_floor']:.1f}%",
                     f"{ln['mu']:.2f} / {ln['sigma']:.2f}", f"{ln['ks']:.3f}", f"{mpr['mean']:.3g} s, {mpr['cv']:.3g}, {mpr['ks']:.3f}",
                     f"{lp['mu']:.2f} / {lp['sigma']:.2f}", f"{lp['ks']:.3f}",
                     f"{c1['weight']:.2f}: {c1['median_s']:.3g} s, {c1['sigma']:.2f}", f"{c2['weight']:.2f}: {c2['median_s']:.3g} s, {c2['sigma']:.2f}",
                     f"{mp['ks']:.3f}", f"{s['ks_exp5']:.3f}", f"{s['ks_exp_meanmatched_capped']:.3f}"])
    return md(rows, ["series (capped 600 s)", "atom <10 ms", "LN MLE mu / sigma (all)", "KS", "mean-preserving LN: mean, CV, KS", "LN mu / sigma (positive part)", "KS",
                     "mix comp 1: weight: median, sigma", "mix comp 2", "KS mix", "KS Exp(5 s)", "KS Exp(mean-matched)"])


def quant_table(S, names, labels=None, with_exp=True):
    rows = []
    for n in names:
        s = S["series"].get(n)
        if not s or "quantiles_1_99" not in s:
            continue
        q = s["quantiles_1_99"]
        rows.append([labels.get(n, n) if labels else n] + [f(q[p - 1]) for p in PCTS])
    if with_exp:
        rows.append(["Exp(5 s) (current simulator)"] + [f(v) for v in exp_q(5.0)])
    return md(rows, ["series"] + [f"p{p}" for p in PCTS])


def tok_table(S, groups):
    rows = []
    for g in groups:
        tk, tn = S["tokens"][g], S["turns"][g]
        def row(label, d):
            return [g, label, f"{d['n']:,}", f(d["mean"]), f(d.get("mean_w999")), f(d["median"]), f(d["p90"]), f(d["p99"]), f(d["cv"])]
        rows.append(row("first call prompt of a session (tokens)", tk["first_input_total_per_session"]))
        rows.append(row("prompt at every call (tokens)", tk["input_total_all_rounds"]))
        rows.append(row("output tokens per call", tk["output_tokens_per_round"]))
        rows.append(row("tokens appended between calls (delta_ctx >= 0)", tk["delta_ctx_nonneg"]))
        rows.append(row("model calls per agentic episode", tn["episode_rounds_agentic"]))
        if "session_rounds" in tn:
            rows.append(row("model calls per whole session", tn["session_rounds"]))
    return md(rows, ["group", "quantity", "n", "mean", "mean (winsorised p99.9)", "median", "p90", "p99", "CV"])


def render(S, kind):
    out = []
    if kind == "tracelab":
        names = ["call_wall_nohuman|all", "call_wall_nohuman|claude", "call_wall_nohuman|codex", "round_z_nohuman|all", "round_z_nohuman|claude",
                 "round_z_nohuman|codex", "call_wall_exec_only|all", "call_wall_shell|all", "call_wall_all_logged|all", "call_internal_nohuman|all",
                 "call_internal_nohuman|codex", "call_internal_nohuman|claude", "call_best_nohuman|all", "round_gap_next_nohuman|all"]
        fit_names = ["call_wall_nohuman|all", "call_wall_nohuman|claude", "call_wall_nohuman|codex", "round_z_nohuman|all", "round_z_nohuman|claude",
                     "round_z_nohuman|codex", "call_wall_exec_only|all", "call_wall_shell|all", "call_internal_nohuman|all"]
        q_names = ["round_z_nohuman|all", "call_wall_nohuman|all", "call_wall_shell|all", "call_wall_exec_only|all", "call_internal_nohuman|all",
                   "round_z_nohuman|claude", "round_z_nohuman|codex"]
        out.append("### Tool time (seconds; wall clock between request and result unless 'internal')\n")
        out.append(time_table(S, names))
        out.append("\n### Fits\n")
        out.append(fit_table(S, fit_names))
        out.append("\n### Percentiles (seconds)\n")
        out.append(quant_table(S, q_names))
        out.append("\n### By tool class (wall clock)\n")
        out.append(time_table(S, [f"class_{c}|all" for c in ("shell", "file", "web", "poll", "deleg", "book", "other", "human")]))
        out.append("\n### By tool (wall clock, 14 most frequent)\n")
        rows = [[k, f"{v['n']:,}", f(v["mean"]), f(v["median"]), f(v["p90"]), f(v["p99"]), f(v["cv"])] for k, v in S["per_tool"].items()]
        out.append(md(rows, ["provider:tool", "n", "mean", "median", "p90", "p99", "CV"]))
        out.append("\n### Wall minus runner-reported duration, rows where both are logged (seconds)\n")
        rows = [[k, f"{v['n']:,}", f(v["mean"]), f(v["median"]), f(v["p90"]), f(v["p99"])] for k, v in S["wall_minus_internal"].items()]
        out.append(md(rows, ["provider", "n", "mean", "median", "p90", "p99"]))
        out.append("\n### Tokens and turns\n")
        out.append(tok_table(S, ["all", "claude", "codex"]))
        out.append(f"\nHuman response time between agent runs (context only): {json.dumps({k: round(v, 2) for k, v in S['human_gap_before_episode_s'].items() if k in ('n', 'mean', 'median', 'p90', 'p99')})}\n")
    else:
        models = S["models"]
        names = ["phase_wall|all"] + [f"phase_wall|{m}" for m in models] + ["phase_wall_uncensored|all", "phase_wall_single_cmd|all", "llm_latency|all"]
        out.append("### Tool time (seconds; wall time of the shell command(s) of one step in the SWE-bench container; 60 s timeout)\n")
        out.append(time_table(S, names))
        out.append("\n### Fits\n")
        out.append(fit_table(S, ["phase_wall|all"] + [f"phase_wall|{m}" for m in models] + ["phase_wall_uncensored|all"]))
        out.append("\n### Percentiles (seconds)\n")
        out.append(quant_table(S, ["phase_wall|all"] + [f"phase_wall|{m}" for m in models] + ["llm_latency|all"]))
        out.append("\n### Tokens and turns (per trajectory = session)\n")
        out.append(tok_table(S, ["all"] + models))
        out.append(f"\nExit status: {S['exit_status']}; format-error retries: {S['noop_steps_total']}; commands hitting the 60 s limit: {S['timeouts_total']}\n")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/traces_summary")
    a = ap.parse_args()
    combined = []
    for src, kind in (("tracelab", "tracelab"), ("mini_swe_v2", "mini")):
        p = os.path.join(a.root, src, "summary.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            S = json.load(fh)
        text = render(S, kind)
        with open(os.path.join(a.root, src, "tables.md"), "w", encoding="utf-8", newline="\n") as g:
            g.write(f"## {src}\n\n{text}\n")
        combined.append(f"## {src}\n\n{text}\n")
    with open(os.path.join(a.root, "tables.md"), "w", encoding="utf-8", newline="\n") as g:
        g.write("\n".join(combined))
    print("wrote tables")


if __name__ == "__main__":
    main()
