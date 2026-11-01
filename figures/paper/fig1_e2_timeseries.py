"""F1 (double column): real E2, the pre-registered paired kill test, at 1.35 and 1.65 x lambda_ref.

Per arm (BURST, NOBURST, CAPPED) and seed (thin lines): prefix-cache hit fraction and backlog against time, from the
18 run directories of the E2 pull. Marks the burst (t_b = 1200 s) and shades the registered evaluation window
(t_b + 4500 s to the end of the run).

Hit fraction: the registered metric (fraction of ok turns whose cached_tokens / prompt_tokens > 0.5, first turns included,
by completion time) in 100 s windows, computed with the repo's own analysis.windows.window_table.
Backlog: the verdict's backlog_trace.csv (sessions in the system = arrived minus ended, 50 s bins; analysis.throughput.backlog_trace).
Run -> (seed, lambda multiple, arm) comes from the verdict's trap_v2_runs.csv.
Run:  python figures/paper/fig1_e2_timeseries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

S.add_repo_paths()

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from analysis.load import Run  # noqa: E402
from analysis.params import load_params  # noqa: E402
from analysis.windows import window_table  # noqa: E402

PULL = "results/nova/e2_170933xx_pulled_20261025-144558"
VERDICT = f"{PULL}/results/agentload_analysis_burst2/20261025-144012"
HIT_WINDOW_S = 100.0
ARMS = ("noburst", "capped", "burst")          # draw order: BURST on top
TRAP_OVERRIDES = ["burst.trap_min_s=3000", "burst.hit_eval_from_s=4500", "trap_v2.eval_from_s=4500"]  # as the verdict was run


def load_run_without_metrics(rel_dir: str) -> Run:
    """analysis.load.load_run minus the 46 MB engine-metrics file (not needed for the hit fraction)."""
    meta = json.loads(S.src(f"{rel_dir}/meta.json").read_text())
    cfg = yaml.safe_load(S.src(f"{rel_dir}/config_effective.yaml").read_text())
    req = pd.read_csv(S.src(f"{rel_dir}/requests.csv"))
    for c in ("t_send", "t_headers", "t_complete", "latency_s", "prompt_tokens", "prompt_tokens_client",
              "completion_tokens", "cached_tokens", "turn", "n_turns", "sid"):
        if c in req.columns:
            req[c] = pd.to_numeric(req[c], errors="coerce")
    ses = pd.read_csv(S.src(f"{rel_dir}/sessions.csv"))
    out = meta.get("outcome") or {}
    t_end = out.get("t_end_s")
    if t_end is None:
        t_end = float(np.nanmax(req["t_complete"]))
    empty_metrics = pd.DataFrame(columns=["t_s", "name", "labels", "value"])
    return Run(dir=Path(rel_dir), meta=meta, cfg=cfg, requests=req, sessions=ses, metrics=empty_metrics, t_end_s=float(t_end))


def draw(pull: str, verdict: str, mults: tuple, n_cap: int, name: str, bl_ylim: tuple = (1, 700),
         bl_ticks: tuple = (1, 10, 100), height: float = 3.9, top: float = 0.93, bottom: float = 0.17,
         label_dx: float = 90.0) -> None:
    """One E2-style figure: hit fraction (top) and backlog (bottom) per arm and seed, one column per registered rate.

    Used by this script (E2, 300k pool) and by fig7_e2_native_timeseries.py (native pool)."""
    runs = pd.read_csv(S.src(f"{verdict}/trap_v2_runs.csv"))
    assert len(runs) == 18, len(runs)
    trace = pd.read_csv(S.src(f"{verdict}/backlog_trace.csv"))
    p = load_params(S.src("configs/agentload_analysis.yaml"), TRAP_OVERRIDES)

    series = {}      # (mult, arm, seed) -> dict(t_hit, hit, t_bl, bl)
    t_burst = set()
    eval_from = set()
    t_end = set()
    for _, r in runs.iterrows():
        rel = f"{pull}/{r['run_dir']}"
        run = load_run_without_metrics(rel)
        wt = window_table(run, p, window_s=HIT_WINDOW_S)
        tb = trace[trace["run_dir"] == r["run_dir"]].sort_values("t_start")
        assert len(tb) > 100, r["run_dir"]
        key = (float(r["rate_mult"]), str(r["arm"]), int(r["seed"]))
        assert key not in series
        series[key] = dict(
            t_hit=0.5 * (wt["t_start"].to_numpy() + wt["t_end"].to_numpy()), hit=wt["hit_rate"].to_numpy(),
            t_bl=tb["t_start"].to_numpy() + 0.5 * 50.0, bl=tb["backlog_mean"].to_numpy(), state=str(r["state"]))
        t_burst.add(float(r["t_burst"]))
        eval_from.add(float(r["eval_from"]))
        t_end.add(round(float(r["t_end_s"])))
    assert len(t_burst) == 1 and len(eval_from) == 1, (t_burst, eval_from)
    tb_, ef_, te_ = t_burst.pop(), eval_from.pop(), max(t_end)
    lam = {float(m): float(g["lambda"].iloc[0]) for m, g in runs.groupby("rate_mult")}

    assert set(lam) == set(mults), (sorted(lam), mults)
    fig, axes = plt.subplots(2, 2, figsize=(S.COL2, height), sharex=True)
    for j, m in enumerate(mults):
        for i, ax in enumerate(axes[:, j]):
            ax.axvspan(ef_, te_, color=S.LGRAY, alpha=0.28, lw=0, zorder=0)
            ax.axvline(tb_, color=S.DARK, lw=0.7, ls=(0, (3, 2)), zorder=1)
            for arm in ARMS:
                for seed in (0, 1, 2):
                    d = series[(m, arm, seed)]
                    if i == 0:
                        ax.plot(d["t_hit"], d["hit"], color=S.ARM_COLOR[arm], lw=0.7, alpha=0.9,
                                ls="-" if arm != "capped" else (0, (3, 1.2)), zorder=3 if arm == "burst" else 2)
                    else:
                        ax.plot(d["t_bl"], d["bl"], color=S.ARM_COLOR[arm], lw=0.7, alpha=0.9,
                                ls="-" if arm != "capped" else (0, (3, 1.2)), zorder=3 if arm == "burst" else 2)
            ax.set_xlim(0, te_)
            ax.set_xticks([0, 2000, 4000, 6000, 8000])
        axes[0, j].set_ylim(-0.03, 1.03)
        axes[0, j].set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        axes[1, j].set_yscale("log")
        axes[1, j].set_ylim(*bl_ylim)
        axes[1, j].set_xlabel("time since start of run (s)")
        axes[0, j].set_title(rf"{m:.2f} $\times\ \lambda_{{\mathrm{{ref}}}}$  ($\lambda$ = {lam[m]:.4f} sessions/s)", pad=4)
        # burst and window labels
        axes[0, j].text(tb_ + label_dx, 0.25, "burst at 1200 s:\n200 sessions in 60 s", fontsize=7.5, va="center", ha="left", color=S.DARK)
        axes[0, j].text((ef_ + te_) / 2, 0.25, "registered\nevaluation window", fontsize=7.5, va="center", ha="center", color=S.DARK)
    axes[0, 0].set_ylabel("prefix-cache hit fraction")
    axes[1, 0].set_ylabel("backlog (sessions in system)")
    for ax in axes[1, :]:
        ax.set_yticks(list(bl_ticks))
        ax.set_yticklabels([f"{t:d}" for t in bl_ticks])

    from matplotlib.lines import Line2D
    labels = {"burst": "BURST", "noburst": "NOBURST", "capped": rf"CAPPED (gate $n_{{\mathrm{{cap}}}}$ = {n_cap})"}
    handles = [Line2D([0], [0], color=S.ARM_COLOR[a], lw=1.4, ls="-" if a != "capped" else (0, (3, 1.2)), label=labels[a])
               for a in ("burst", "noburst", "capped")]
    handles.append(Line2D([0], [0], color=S.GRAY, lw=0.7, label="one line per seed (0, 1, 2)"))
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.005), columnspacing=1.8, handlelength=2.0)
    fig.subplots_adjust(left=0.075, right=0.99, top=top, bottom=bottom, hspace=0.12, wspace=0.14)
    S.save(fig, name)
    S.finish(name)


def main() -> None:
    draw(PULL, VERDICT, (1.35, 1.65), 20, "fig1_e2_timeseries")


if __name__ == "__main__":
    main()
