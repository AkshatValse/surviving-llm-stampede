"""Round-5 report of the prefix-cache metastability pilot: ``results/prefix_meta_r5/<ts>/``.

Reads the calib / curve / burst / cap result dirs (never modifies them), the registered design of the pre-registration and the evaluation
parameters of the config, and writes

* ``prediction_eval.{csv,json}``   S1-S4 per registered mode under the REGISTERED readings first (headline rows), then clauses, the registered
                                   sensitivities, the sensitivity VARIANTS of amendment 2 (suffix ``@variant``) and the information rows
                                   (lambda_miss per mode, thrash label, reservation excess, stationarity). Every test verdict becomes
                                   NOT_EVALUABLE ("VERDICT SUPPRESSED") if an input is a quick run, was produced from a dirty git tree, has no
                                   finished meta.json or belongs to a different variant,
* ``table_*.csv``                  the tables behind the figures,
* ``fig1_mu_curves_three_modes.pdf``   mu(n) for the three modes overlaid (FCFS-LRU solid, LPM-LRU dashed; the round-4 FULL_RESERVE curve of
                                   seeds 2000-2002 as an unpaired grey reference),
* ``fig2_burst_outcomes.pdf``      tail hit rate and tail backlog of the burst and paired no-burst runs, per seed,
* ``fig3_preemption_rate_vs_n.pdf``    preemptions per admitted turn, discarded and recomputed prefill work, and the most preemptions of one turn vs n,
* ``config.yaml`` / ``preregistration.yaml`` / ``meta.json`` (git commit + dirty flag at the START).

Every number in a figure or table is read from a file in the input result dirs. Seeds are the unit of replication; cells that share a seed are
CRN-coupled, not independent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from . import r5_eval as E  # noqa: E402
from .mech_runner import _write_json, begin, finish  # noqa: E402
from .r5_runner import all_modes, burst_counts, cap_cells, guard_run, curve_table  # noqa: E402
from .runner import git_info  # noqa: E402

MODE_STYLE = {"full_reserve": ("#7f7f7f", "FULL_RESERVE (rounds 1-4)"), "ondemand_preempt": ("#d62728", "ONDEMAND_PREEMPT (vLLM-like model)"),
              "ratio_reserve": ("#1f77b4", "RATIO_RESERVE (SGLang-like model)")}
R4_CURVE = "results/prefix_meta_r4_curve/20261021-050856/curve_table.csv"        # round-4 FULL_RESERVE curve, seeds 2000-2002 (unpaired reference)


def load_design(cfg: dict, repo_dir: Path) -> Dict[str, Any]:
    return yaml.safe_load((repo_dir / cfg["preregistration_file"]).read_text())["preregistration"]["registered_design"]


def _read(d: Optional[str], name: str) -> Optional[pd.DataFrame]:
    if not d:
        return None
    f = Path(d) / name
    return pd.read_csv(f) if f.exists() else None


def provenance(d: Optional[str]) -> Optional[Dict[str, Any]]:
    if not d:
        return None
    mf = Path(d) / "meta.json"
    if not mf.exists():
        return {"dir": str(d), "meta": None}
    m = json.loads(mf.read_text())
    return {"dir": str(d), "experiment": m.get("experiment"), "git_commit": m.get("git", {}).get("commit"), "git_dirty": m.get("git", {}).get("dirty"),
            "quick": m.get("quick"), "n_runs": m.get("n_runs"), "start_time": m.get("start_time"), "status": m.get("status"), "seeds": m.get("seeds"),
            "variant": m.get("variant"), "overrides": m.get("overrides")}


def unsafe_inputs(prov: Dict[str, Optional[Dict[str, Any]]], expect_variant: Dict[str, Optional[str]]) -> List[str]:
    """Reasons an input must not decide a verdict: quick run, dirty / unknown git tree, unfinished or missing meta.json, --set overrides, wrong variant."""
    out = []
    for k, v in prov.items():
        if not v:
            continue
        if v.get("meta") is None and "experiment" not in v:
            out.append(f"{k}: meta.json missing")
            continue
        if v.get("quick"):
            out.append(f"{k}: quick run")
        if v.get("git_dirty") is not False:
            out.append(f"{k}: produced from a dirty (or unknown) git tree")
        if v.get("status") != "done":
            out.append(f"{k}: status {v.get('status')!r} is not 'done'")
        if v.get("overrides"):
            out.append(f"{k}: produced with --set overrides {v.get('overrides')}")
        if v.get("variant") != expect_variant.get(k):
            out.append(f"{k}: variant {v.get('variant')!r}, expected {expect_variant.get(k)!r}")
    return out


def parse_sens(items: List[str]) -> Dict[str, Dict[str, str]]:
    """``--sens-dir variant:cmd=path`` (repeatable) -> {variant: {cmd: path}}."""
    out: Dict[str, Dict[str, str]] = {}
    for it in items or []:
        left, _, path = it.partition("=")
        var, _, cmd = left.partition(":")
        if not (var and cmd and path) or cmd not in ("calib", "curve", "burst", "cap"):
            raise SystemExit(f"bad --sens-dir {it!r}; expected variant:calib|curve|burst|cap=DIR")
        out.setdefault(var, {})[cmd] = path
    return out


def load_inputs(dirs: Dict[str, Optional[str]]) -> E.R5Inputs:
    cal = _read(dirs.get("calib"), "calib_runs.csv")
    cur = _read(dirs.get("curve"), "curve_runs.csv")
    bur = _read(dirs.get("burst"), "runs.csv")
    cap = _read(dirs.get("cap"), "runs.csv")
    for df in (bur, cap):
        if df is not None:
            df["recovered"] = df["recovered"].astype(bool)
    if cur is not None and "thrash" in cur:
        cur["thrash"] = cur["thrash"].astype(bool)
    return E.R5Inputs(calib=cal, curve=cur, burst=bur, cap=cap)


# ------------------------------------------------------------------------------------------------ figures
def fig_curves(ct: pd.DataFrame, lam: Dict[str, float], nstar: Dict[str, int], r4: Optional[pd.DataFrame], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    for mode, (c, lab) in MODE_STYLE.items():
        for pol, ls, mk in (("fcfs_lru", "-", "o"), ("lpm_lru", "--", "s")):
            d = ct[(ct["mode"] == mode) & (ct["policy"] == pol)].sort_values("n_nominal")
            if d.empty:
                continue
            se = d["mu_se"].fillna(0)
            axes[0].errorbar(d["n_nominal"], d["mu_mean"], yerr=se, color=c, ls=ls, marker=mk, ms=3.5, lw=1.1, capsize=2,
                             label=f"{lab} {'FCFS' if pol == 'fcfs_lru' else 'LPM'}")
            axes[1].errorbar(d["n_nominal"], d["mu_mean"] / lam[mode], yerr=se / lam[mode], color=c, ls=ls, marker=mk, ms=3.5, lw=1.1, capsize=2)
        if mode in lam:
            axes[0].axhline(lam[mode], color=c, lw=0.6, ls=":")
        if mode in nstar:
            axes[0].axvline(nstar[mode], color=c, lw=0.6, ls="-.")
    if r4 is not None:
        for pol, ls in (("fcfs_lru", "-"), ("lpm_lru", "--")):
            d = r4[(r4["policy"] == pol) & np.isclose(r4["k"], 1.0)].sort_values("n_nominal")
            axes[0].plot(d["n_nominal"], d["mu_mean"], color="0.55", ls=ls, lw=0.8, alpha=0.8,
                         label="round-4 FULL_RESERVE, seeds 2000-2002 (unpaired)" if pol == "fcfs_lru" else None)
    axes[0].set_ylabel(r"$\mu(n)$  (completed sessions / s)")
    axes[1].set_ylabel(r"$\mu(n)/\lambda_{\rm miss}(\mathrm{mode})$")
    axes[1].axhline(1.0, color="k", lw=0.7, ls=":")
    axes[1].axhline(1.3, color="k", lw=0.6, ls="--")
    for a in axes:
        a.set_xscale("log")
        a.set_xlabel("closed population $n$ (sessions)")
        a.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=5.8, frameon=False, loc="upper right")
    axes[0].set_title(r"seed mean $\pm$ 1 SE (3 seeds, CRN-coupled); dotted: $\lambda_{\rm miss}$ per mode; dash-dot: $n^*$", fontsize=7.5)
    axes[1].set_title(r"normalised by each mode's own $\lambda_{\rm miss}$ (dashed: $1.3\lambda$, the S1 C1 bound)", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_burst(runs: pd.DataFrame, modes: List[str], design: Dict[str, Any], out: Path) -> None:
    b = design["burst"]
    fig, axes = plt.subplots(2, len(modes), figsize=(5.2 * len(modes), 5.4), squeeze=False)
    for j, m in enumerate(modes):
        c, lab = MODE_STYLE[m]
        d = runs[runs["alloc_mode"] == m]
        for i, (col, ylab) in enumerate((("tail_hit_rate", "hit rate, last 5000 s"), ("tail_backlog_mean", "backlog (queue + gate), last 5000 s"))):
            ax = axes[i][j]
            for k, size in enumerate(b["sizes"]):
                g = d[d["burst_n"] == size].sort_values("seed")
                x = np.full(len(g), float(k)) + np.linspace(-0.12, 0.12, len(g)) if len(g) else []
                ok = g["recovered"].astype(bool).to_numpy()
                th = g["tail_thrash"].astype(bool).to_numpy() if "tail_thrash" in g else np.zeros(len(g), bool)
                ax.scatter(np.asarray(x)[ok], g[col].to_numpy()[ok], marker="o", facecolors="none", edgecolors=c, s=30, label="recovered" if k == 0 else None)
                ax.scatter(np.asarray(x)[~ok], g[col].to_numpy()[~ok], marker="o", color=c, s=30, label="not recovered" if k == 0 else None)
                if th.any():
                    ax.scatter(np.asarray(x)[th], g[col].to_numpy()[th], marker="*", color="k", s=70, label="thrash flag" if k == 0 else None)
            ax.set_xticks(range(len(b["sizes"])))
            ax.set_xticklabels([f"burst {s}" if s else "no burst (b=0)" for s in b["sizes"]])
            ax.set_ylabel(ylab)
            ax.grid(alpha=0.25)
            if col == "tail_hit_rate":
                ax.axhline(b["recovered_hit_above"], color="k", lw=0.7, ls="--")
                ax.set_ylim(-0.03, 1.03)
            else:
                ax.axhline(b["recovered_backlog_below"], color="k", lw=0.7, ls="--")
                ax.set_yscale("symlog", linthresh=1.0)
                ax.set_ylim(bottom=0.0)
            if i == 0:
                n1 = int((~d[d["burst_n"] == max(b["sizes"])]["recovered"].astype(bool)).sum())
                n0 = int((~d[d["burst_n"] == 0]["recovered"].astype(bool)).sum())
                ax.set_title(f"{lab}\nnot recovered: burst {n1}/5, no-burst {n0}/5", fontsize=8)
                ax.legend(fontsize=6, frameon=False, loc="lower left")
    fig.suptitle("S2: burst 200 at $2\\lambda_{\\rm miss}$(mode) from empty vs the paired no-burst run (same seeds; dashed: recovery thresholds)", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out)
    plt.close(fig)


def fig_preempt(ct: pd.DataFrame, thr: Dict[str, float], out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
    for mode in ("ondemand_preempt", "ratio_reserve"):
        c, lab = MODE_STYLE[mode]
        for pol, ls, mk in (("fcfs_lru", "-", "o"), ("lpm_lru", "--", "s")):
            d = ct[(ct["mode"] == mode) & (ct["policy"] == pol)].sort_values("n_nominal")
            if d.empty:
                continue
            nm = f"{lab} {'FCFS' if pol == 'fcfs_lru' else 'LPM'}"
            axes[0].plot(d["n_nominal"], d["preemptions_per_turn_mean"], color=c, ls=ls, marker=mk, ms=3.5, lw=1.1, label=nm)
            axes[1].plot(d["n_nominal"], d["lost_prefill_frac_mean"], color=c, ls=ls, marker=mk, ms=3.5, lw=1.1)
            axes[2].plot(d["n_nominal"], d["preempt_max_turn_max"], color=c, ls=ls, marker=mk, ms=3.5, lw=1.1)
    axes[0].axhline(thr["preemptions_per_turn_above"], color="k", lw=0.7, ls="--")
    axes[2].axhline(thr["max_per_turn_above"], color="k", lw=0.7, ls="--")
    axes[0].set_ylabel("preemptions / retractions per admitted turn")
    axes[1].set_ylabel("admitted prefill discarded unprocessed (fraction)")
    axes[2].set_ylabel("most preemptions of one turn (max over seeds)")
    for a in axes:
        a.set_xscale("log")
        a.set_xlabel("closed population $n$ (sessions)")
        a.grid(alpha=0.25, which="both")
    axes[0].set_yscale("symlog", linthresh=1e-3)
    axes[1].set_yscale("symlog", linthresh=1e-4)
    axes[2].set_yscale("symlog", linthresh=1.0)
    top0 = max(2.0 * thr["preemptions_per_turn_above"], 1.5 * float(ct["preemptions_per_turn_mean"].max()))
    top2 = max(2.0 * thr["max_per_turn_above"], 1.5 * float(ct["preempt_max_turn_max"].max()))
    axes[0].set_ylim(0.0, top0)
    axes[1].set_ylim(bottom=0.0)
    axes[2].set_ylim(0.0, top2)
    axes[0].legend(fontsize=6, frameon=False)
    axes[0].set_title("rates in the measurement window (dashed: thrash threshold)", fontsize=8)
    axes[1].set_title("work discarded by preemption", fontsize=8)
    axes[2].set_title("per-turn churn (dashed: thrash threshold)", fontsize=8)
    fig.text(0.5, 0.005, "simulator models of the scout-reported rules; the vLLM-like preemption rate rests on the scout's unverified full-ISL admission claim "
                         "(see sensitivity variant ondemand_first_chunk)", ha="center", fontsize=6.3, color="0.3")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ command
def cmd_report(cfg: dict, args: argparse.Namespace, repo_dir: Path) -> Path:
    guard_run(cfg, args, repo_dir)
    design = load_design(cfg, repo_dir)
    ev, thr = cfg["evaluation"], cfg["thrash"]
    sens = parse_sens(getattr(args, "sens_dir", None) or [])
    main_dirs = {"calib": args.calib_dir, "curve": args.curve_dir, "burst": args.burst_dir, "cap": args.cap_dir}
    ctx = begin("r5_report", "prefix_meta_r5", cfg, {**cfg, "registered_design": design, "inputs": main_dirs, "sens_inputs": sens}, args, repo_dir)
    inp = load_inputs(main_dirs)
    variants = {v: load_inputs(d) for v, d in sens.items()}
    prov = {k: provenance(d) for k, d in main_dirs.items()}
    expect = {k: None for k in main_dirs}
    for v, d in sens.items():
        for k, path in d.items():
            prov[f"{v}:{k}"] = provenance(path)
            expect[f"{v}:{k}"] = v
    unsafe = unsafe_inputs(prov, expect)
    modes = list(cfg["modes"]["registered"])
    M_tokens = float(cfg["engine"]["kv_memory_tokens"])
    rows = E.evaluate_all(inp, design, ev, thr, claims=E.registered_claims(repo_dir / cfg["preregistration_file"]), variants=variants,
                          ref_mode=cfg["modes"]["reference"], M_tokens=M_tokens, modes=modes, decode_tokens=int(cfg["workload"]["decode_tokens"]))
    if unsafe:
        rows = E.suppress_verdicts(rows, "; ".join(unsafe))
    flags = list(unsafe)
    flags += [f"{k}: result dir missing" for k, v in prov.items() if v is None and ":" not in k]
    commits = {v.get("git_commit") for v in prov.values() if v}
    if len(commits) > 1:
        flags.append(f"inputs were produced at different commits: {sorted(str(c) for c in commits)}")
    head = git_info(repo_dir)
    if commits and not args.quick and commits != {head["commit"]}:
        flags.append(f"inputs' commit(s) {sorted(str(c) for c in commits)} differ from the report's HEAD {head['commit']}")
    out = ctx.out
    lam = E.lambda_miss_by_mode(inp.calib) if inp.calib is not None else {}
    _write_json(out / "prediction_eval.json", {"rows": rows, "inputs": prov, "flags": flags, "lambda_miss": lam, "evaluation": ev, "thrash": thr})
    E.rows_to_frame(rows).to_csv(out / "prediction_eval.csv", index=False)
    pd.DataFrame([{"input": k, **(v or {})} for k, v in prov.items()]).to_csv(out / "table_input_provenance.csv", index=False)
    if inp.calib is not None:
        inp.calib.to_csv(out / "table_calib_runs.csv", index=False)
    if inp.curve is not None:
        ct = curve_table(inp.curve)
        ct["lambda_miss"] = ct["mode"].map(lam)
        ct["mu_over_lambda_miss"] = ct["mu_mean"] / ct["lambda_miss"]
        ct.to_csv(out / "table_curve.csv", index=False)
        nstar = {m: E.nstar_of(inp, m, E.Ctx(design, ev, thr)) for m in all_modes(cfg)}
        r4p = repo_dir / R4_CURVE
        r4 = pd.read_csv(r4p) if r4p.exists() else None
        fig_curves(ct, lam, {k: v for k, v in nstar.items() if v is not None}, r4, out / "fig1_mu_curves_three_modes.pdf")
        fig_preempt(ct, thr, out / "fig3_preemption_rate_vs_n.pdf")
    if inp.burst is not None:
        burst_counts(inp.burst).to_csv(out / "table_burst_counts.csv", index=False)
        fig_burst(inp.burst, modes, design, out / "fig2_burst_outcomes.pdf")
    if inp.cap is not None:
        cap_cells(inp.cap).to_csv(out / "table_cap_cells.csv", index=False)
    finish(ctx, [], {"inputs": prov, "flags": flags, "lambda_miss": lam,
                     "verdicts": {f"{r['id']}|{r['mode']}": r["verdict"] for r in rows if r["reading"] in ("headline", "clause")},
                     "note": "headline rows are the registered readings; clause / sensitivity / information rows never decide a verdict; cells sharing "
                             "a seed are CRN-coupled, not independent; scope: d = 100 decode tokens per turn"})
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        pe = E.rows_to_frame(rows)
        pe = pe[pe["reading"].isin(["headline"])][["id", "mode", "verdict", "notes"]].copy()
        pe["notes"] = pe["notes"].str.slice(0, 150)
        print(pe.to_string())
    for f in flags:
        print("FLAG:", f)
    print("result dir:", out)
    return out
