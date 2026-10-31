"""F-LPM (double column): stock SGLang LPM against its hard-coded 128-request FCFS fallback. POST HOC, CORRELATIONAL.

SGLang 0.5.22 schedule_policy.py:132-133 sets WAITING_QUEUE_PREFIX_MATCH_MAX = 128 and :300-311 switches LPM to FCFS
order whenever the waiting queue is longer than that (md5 b8ec334ac1ed028e3c176022ea1f9143). Data: the 12 stock-LPM BURST
runs of the exploratory policy grid (cells sglang-lpm-r0 / -r1, 1.35 and 1.65 x lambda_ref, seeds 0-2, jobs
17097087-17097103) and, in panel (d), the 12 FCFS BURST runs (grid cell sglang-fcfs-r0 and the registered E2 cell
sglang-fcfs-r1, jobs 17093387-17093402). Qwen2.5-7B-Instruct, one A100 80GB PCIe, 300k-token KV pool, 200-session burst at
1200 s. All numbers from analysis/lpm_crossing.py (notes/LPM_CROSSING_r11.md).
  (a) waiting queue (sglang:num_queue_reqs, 60-s means) per run, coloured by the committed trap_v2 state; the bold pair is
      the same arrival stream (1.35 x, seed 0) run twice; dots mark the sustained crossing (300 s above 128).
  (b) token hit (cached / prompt tokens, 300-s bins by completion time), same runs and colours.
  (c) the five sustained crossings in event time (60-s bins): share of 5-s queue samples above 128 (gray bars, mean over
      the five) and token hit (one line per run). Hit is binned by completion, which lags the engine by up to one latency
      (about 2 min here), so the panel cannot order the two events.
  (d) scheduler cost get_next_batch_to_run (s per wall s) against queue length, pooled over runs: LPM drops to the FCFS
      level once the queue passes 128 (the manipulation check that the fallback engaged).
Run:  python figures/paper/fig_lpm_crossing.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

S.add_repo_paths()

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from analysis import lpm_crossing as L  # noqa: E402

NAME = "fig_lpm_crossing"
PAIR = ("1.35", "0")
STATE_ORDER = ("trapped", "draining", "indeterminate", "recovered")


def main() -> None:
    runs = L.load_runs(path_fn=lambda rel: S.src(rel))
    lpm = [r for r in runs if r.policy == "lpm"]
    fcfs = [r for r in runs if r.policy == "fcfs"]
    assert len(lpm) == 12 and len(fcfs) == 12, (len(lpm), len(fcfs))
    rows = {x["run"]: x for x in L.crossing_table(runs)}

    fig, axs = plt.subplots(2, 2, figsize=(S.COL2, 4.5))
    (ax_q, ax_h), (ax_e, ax_c) = axs

    # draw the pair last so it sits on top
    order = sorted(lpm, key=lambda r: ((r.mult, r.seed) == PAIR, r.state == "trapped"))
    for r in order:
        pair = (r.mult, r.seed) == PAIR
        col = S.STATE_COLOR[r.state]
        lw, al, z = (1.5, 1.0, 4) if pair else (0.7, 0.75, 2)
        qb = L.queue_binned(r.queue, 60.0)
        ax_q.plot([t for t, _ in qb], [v for _, v in qb], color=col, lw=lw, alpha=al, zorder=z)
        tx = rows[r.run]["t_cross"]
        if tx is not None:
            qd = dict(qb)
            near = min(qd, key=lambda c: abs(c - tx))
            ax_q.plot([near], [qd[near]], "o", ms=3.2 if pair else 2.6, mfc=col, mec="white", mew=0.4, zorder=z + 1)
        hb = L.hit_bins(r.reqs)
        ts = [t for t in sorted(hb) if t < L.EVAL_T1]
        ax_h.plot([t + L.HIT_BIN_S / 2 for t in ts], [hb[t] for t in ts], color=col, lw=lw, alpha=al, zorder=z)
    for ax in (ax_q, ax_h):
        ax.axvline(L.T_BURST, color=S.GRAY, lw=0.6, ls=":", zorder=1)
        ax.axvspan(L.EVAL_T0, L.EVAL_T1, color=S.LGRAY, alpha=0.25, lw=0, zorder=0)
        ax.set_xlim(0, L.EVAL_T1)
        ax.set_xticks(range(0, 8701, 1500))
        ax.set_xlabel("time since run start (s)")
    ax_q.axhline(L.THRESHOLD, color=S.DARK, lw=0.7, ls="--", zorder=1)
    ax_q.text(80, L.THRESHOLD + 8, "fallback\nthreshold\n128", fontsize=6.8, color=S.DARK, va="bottom", linespacing=1.05)
    ax_q.text(L.T_BURST - 60, 30, "burst", fontsize=6.8, color=S.GRAY, va="bottom", ha="right")
    ax_q.set_ylim(0, 360)
    ax_q.set_ylabel("waiting queue (requests)")
    ax_q.set_title("stock LPM, BURST arm: waiting queue", loc="left")
    # annotate the pair
    pr = {r.label: r for r in lpm if (r.mult, r.seed) == PAIR}
    x0 = rows[pr["sglang-lpm-r0"].run]
    x1 = rows[pr["sglang-lpm-r1"].run]
    ax_q.text(1400, 350, "bold: one arrival stream (1.35x, seed 0), run twice", fontsize=6.5, color=S.DARK, va="top")
    ax_q.text(1400, 328, f"refresh off: above 128 from {x0['t_first_gt128']} s, {x0['state']}", fontsize=6.5,
              color=S.STATE_COLOR[x0["state"]], va="top")
    ax_q.text(1400, 306, f"refresh on: peak {x1['q_max_post']:.0f}, {x1['state']}", fontsize=6.5,
              color=S.STATE_COLOR[x1["state"]], va="top")
    handles = [Line2D([], [], color=S.STATE_COLOR[s], lw=1.2, label=S.STATE_LABEL[s]) for s in STATE_ORDER
               if any(r.state == s for r in lpm)]
    ax_h.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 0.05), ncol=2, fontsize=7, columnspacing=0.8)
    ax_h.set_ylim(0, 1.0)
    ax_h.set_ylabel("token hit")
    ax_h.set_title("token hit (300-s bins); shaded: L1 endpoint window", loc="left")

    # (c) event time around the sustained crossings
    ev = {r.run: L.event_time(r) for r in lpm if rows[r.run]["crossed"]}
    assert len(ev) == 5, len(ev)
    ks = [e["t0_rel"] for e in next(iter(ev.values()))]
    share = [sum(v[i]["share_gt128"] for v in ev.values()) / len(ev) for i in range(len(ks))]
    w = L.EVENT_BIN_S
    ax_e.bar([k + w / 2 for k in ks], share, width=w * 0.92, color=S.LGRAY, edgecolor="none", zorder=1,
             label="share of time queue > 128 (mean)")
    for run, e in ev.items():
        ax_e.plot([x["t0_rel"] + w / 2 for x in e], [x["hit"] for x in e], color=S.STATE_COLOR["trapped"], lw=0.8,
                  marker="o", ms=1.8, alpha=0.9, zorder=3)
    ax_e.plot([], [], color=S.STATE_COLOR["trapped"], lw=0.8, marker="o", ms=1.8, label="token hit, each of the 5 runs")
    ax_e.axvline(0, color=S.DARK, lw=0.6, ls="--", zorder=2)
    ax_e.set_xlim(ks[0], ks[-1] + w)
    ax_e.set_ylim(0, 1.05)
    ax_e.set_xlabel(r"time relative to sustained crossing $t_\times$ (s)")
    ax_e.set_ylabel("fraction")
    ax_e.set_title("the five sustained crossings, 60-s bins", loc="left")
    ax_e.legend(loc="upper left", fontsize=7)

    # (d) scheduler cost vs queue length
    edges = L.COST_EDGES
    for pol, rr in (("fcfs", fcfs), ("lpm", lpm)):
        b = [x for x in L.gnb_by_queue_bin(rr, edges) if x["n"] >= 20]
        ax_c.plot([(x["q_lo"] + x["q_hi"] - 1) / 2 for x in b], [x["s_per_s"] for x in b], color=S.POLICY_COLOR[pol],
                  marker="o", ms=2.6, lw=0.9, label={"fcfs": "FCFS (12 runs)", "lpm": "stock LPM (12 runs)"}[pol])
    ax_c.axvline(L.THRESHOLD + 0.5, color=S.DARK, lw=0.6, ls="--")
    ax_c.set_xlim(0, 370)
    ax_c.set_ylim(0, None)
    ax_c.set_xlabel("waiting queue at scrape (requests, 16-wide bins)")
    ax_c.set_ylabel("get_next_batch_to_run (s/s)")
    ax_c.set_title("scheduler cost: prefix matching stops above 128", loc="left")
    ax_c.legend(loc="upper right", fontsize=7)

    for ax, lab in zip((ax_q, ax_h, ax_e, ax_c), "abcd"):
        S.panel_label(ax, lab, dx=-0.10, dy=1.02)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.93, bottom=0.10, wspace=0.24, hspace=0.55)
    S.save(fig, NAME)
    S.finish(NAME)


if __name__ == "__main__":
    main()
