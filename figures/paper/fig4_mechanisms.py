"""F4 (double column): mechanism comparison in the simulator, closed-population service rate mu(300) / lambda_miss.

Round-3 simulator (private-prefix workload, FCFS unless stated, lambda_miss = 0.047419 sessions/s), baselines audit of
2026-10-24/25 (notes/BASELINES_AUDIT.md). Dots: mean over seeds 0-9 with the 95% Student-t interval (bars). Hollow dots are the
historical rows (PEEK as an FCFS queued-session-protection ablation; Continuum pins under the old idle-only release
rule); filled dots are the audited rows (PEEK released-scheduler ordering + eviction score projected onto private
prefixes; Continuum pins under the released preview's waiting-allocation rule). CONCUR is the CONCUR-equation session-gate
SURROGATE (the paper's control equation and constants; its lifecycle, usage signal and scheduler are not specified);
the lower CONCUR row shows all 18 cells (6 variants x seeds 0-2) when finished sessions' KV counts as usage.
Static session caps c = 20, 28, 36: the closed FCFS curve mu(c) of round 4 (seeds 2000-2002, 3 seeds, 95% t-interval),
since a cap c on a large population holds the engine at c sessions.
Run:  python figures/paper/fig4_mechanisms.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

AUDIT = "results/prefix_meta_baselines_audit_summary/20261025-001850"
CURVE10 = f"{AUDIT}/curve_baselines_audit_s10.csv"
CURVE_DEADKV = f"{AUDIT}/curve_baselines_audit_deadkv.csv"
AUDIT_META = f"{AUDIT}/meta.json"
R4_CURVE = "results/prefix_meta_r4_curve/20261021-050856/curve_runs.csv"
CONCUR_VARIANTS = ["concur_cap", "concur_lpm", "concur_i5", "concur_i20", "concur_s8", "concur_s56"]


def main() -> None:
    meta = json.loads(S.src(AUDIT_META).read_text())
    lam = float(meta["lambda_miss"])
    c10 = pd.read_csv(S.src(CURVE10)).set_index("policy")
    ckv = pd.read_csv(S.src(CURVE_DEADKV)).set_index("policy")
    r4 = pd.read_csv(S.src(R4_CURVE))
    r4 = r4[(r4["policy"] == "fcfs_lru") & (r4["k"] == 1.0)]

    def audit(pol):
        r = c10.loc[pol]
        assert int(r["n_seeds"]) == 10
        return float(r["mean_x"]), float(r["ci95_half"])

    def cap_row(c):
        v = r4[r4["n"] == c].sort_values("seed")
        assert len(v) == 3 and list(v["seed"]) == [2000, 2001, 2002], (c, len(v))
        x = v["mu"].to_numpy() / lam
        return float(x.mean()), S.t_half_width(float(x.std(ddof=1)), 3), x

    # rows: (group, label, color, [markers]); marker = dict(x, ci, filled, dots)
    rows = []

    def add(group, label, color, markers):
        rows.append(dict(group=group, label=label, color=color, markers=markers))

    m, h = audit("fcfs"); add("Ordering", "FCFS", S.POLICY_COLOR["fcfs"], [dict(x=m, ci=h, filled=True)])
    m, h = audit("lpm"); add("Ordering", "LPM (resident-first)", S.POLICY_COLOR["lpm"], [dict(x=m, ci=h, filled=True)])
    m, h = audit("peek_rank"); add("PEEK", "ablation, soft rank (historical)", S.POLICY_COLOR["peek"], [dict(x=m, ci=h, filled=False)])
    m, h = audit("peek"); add("PEEK", "ablation, hard pin (historical)", S.POLICY_COLOR["peek"], [dict(x=m, ci=h, filled=False)])
    m, h = audit("peek_singleton_audit"); add("PEEK", "audited ordering + score projection", S.POLICY_COLOR["peek"], [dict(x=m, ci=h, filled=True)])
    for tau, old, new in ((5, "ttl5", "ttl5cw"), (10, "ttl10", "ttl10cw"), (20, "ttl20", "ttl20cw")):
        mo, ho = audit(old)
        mn, hn = audit(new)
        add("Continuum-style\nTTL pins", rf"$\tau$ = {tau} s", S.POLICY_COLOR["continuum"],
            [dict(x=mo, ci=ho, filled=False, dy=0.16), dict(x=mn, ci=hn, filled=True, dy=-0.16)])
    m, h = audit("concur_cap"); add("CONCUR", "equation surrogate", S.POLICY_COLOR["concur"], [dict(x=m, ci=h, filled=True)])
    dots = np.concatenate([np.array(json.loads(ckv.loc[p, "per_seed_x"])) for p in CONCUR_VARIANTS])
    assert len(dots) == 18
    add("CONCUR", "surrogate, usage counts cached KV", S.POLICY_COLOR["concur"], [dict(x=None, ci=None, filled=False, dots=dots)])
    for c, tag in ((20, "c = 20 ($= n^*$, as in E2)"), (28, r"c = 28 (= $N_{\mathrm{lb}}$)"), (36, r"c = 36 (= 1.3 $N_{\mathrm{lb}}$)")):
        m, h, x = cap_row(c)
        add("Static session\ncap", tag, S.POLICY_COLOR["cap"], [dict(x=m, ci=h, filled=True, dots=x)])

    n = len(rows)
    row_h = 0.205
    fig_h = n * row_h + 0.80
    fig, ax = plt.subplots(figsize=(S.COL2, fig_h))
    ys = np.arange(n)[::-1].astype(float)
    ax.axvline(1.0, color=S.GRAY, lw=0.6, ls=(0, (2, 2)), zorder=0)
    prev_group = None
    group_rows = {}
    for y, r in zip(ys, rows):
        group_rows.setdefault(r["group"], []).append(y)
        for mk in r["markers"]:
            yy = y + mk.get("dy", 0.0)
            if mk.get("dots") is not None:
                ax.plot(mk["dots"], np.full(len(mk["dots"]), yy), lw=0, marker="o", ms=2.8, color=r["color"], alpha=0.55,
                        mew=0, zorder=2)
            if mk["x"] is None:
                continue
            ax.errorbar(mk["x"], yy, xerr=mk["ci"], fmt="none", ecolor=r["color"], elinewidth=1.0, capsize=2.0, capthick=0.8, zorder=3)
            ax.plot(mk["x"], yy, lw=0, marker="o", ms=4.4, mfc=r["color"] if mk["filled"] else "white", mec=r["color"], mew=1.0, zorder=4)
    # separators between groups
    order = list(group_rows)
    for g in order[:-1]:
        ax.axhline(min(group_rows[g]) - 0.5, color=S.LGRAY, lw=0.5, zorder=0)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows])
    ax.tick_params(axis="y", length=0, pad=3)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 5.0)
    ax.set_xlabel(r"closed-population service rate $\mu(300)\,/\,\lambda_{\mathrm{miss}}$")
    for g, yv in group_rows.items():
        ax.text(-0.545, float(np.mean(yv)), g, transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=8.5,
                fontweight="bold")
    # value column
    for y, r in zip(ys, rows):
        mk = r["markers"]
        if len(mk) == 1 and mk[0]["x"] is not None:
            txt = rf"{mk[0]['x']:.2f} $\pm$ {mk[0]['ci']:.2f}"
        elif len(mk) == 2:
            txt = f"old {mk[0]['x']:.2f}, new {mk[1]['x']:.2f}"
        else:
            d = mk[0]["dots"]
            txt = f"{int((d < 2).sum())} of {len(d)} cells at {d[d < 2].mean():.2f}"
        ax.text(1.01, y, txt, transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=7.5, color=S.DARK)
    ax.text(1.01, 1.0, "mean $\\pm$ 95% interval", transform=ax.transAxes, ha="left", va="bottom", fontsize=7.5, color=S.GRAY)
    h = [Line2D([0], [0], marker="o", mfc="white", mec=S.DARK, lw=0, ms=4.4, label="historical rule"),
         Line2D([0], [0], marker="o", mfc=S.DARK, mec=S.DARK, lw=0, ms=4.4, label="audited / released-preview rule"),
         Line2D([0], [0], marker="o", color=S.GRAY, alpha=0.5, lw=0, ms=2.4, label="single seed")]
    ax.legend(handles=h, loc="upper right", bbox_to_anchor=(0.995, 1.0), fontsize=7.5, ncol=1)
    ax.text(1.06, -0.45, "", transform=ax.transData)
    fig.subplots_adjust(left=0.335, right=0.80, top=1 - 0.30 / fig_h, bottom=0.55 / fig_h)
    S.save(fig, "fig4_mechanisms")
    S.finish("fig4_mechanisms")


if __name__ == "__main__":
    main()
