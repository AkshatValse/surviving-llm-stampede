"""Hit prefills (X = 551 new tokens, radix prefix c > 0) are never 'clean' by the chunk rule: their gap is
    gap = tau_P(c) + k * tau_D + (idle = 0 when R > 0),   k = number of decode iterations since the previous prefill.
With no Decode line in between (previous batch line is a Prefill) k is a small integer and the gaps form a comb
spaced by tau_D. We recover the k = 0 tooth by iterating: fit tau_P(c) = alpha + beta*c on the members with
|k_hat| < 0.5, where k_hat = (gap - tau_P(c)) / tau_D(R, sumctx) and tau_D comes from the calibrated decode model.

Usage: python hits.py <work_dir> <seed> <n_boot>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fit import NORM, simform_pred  # noqa: E402

M_TOK = 300000
XH = 551


def prep(W: Path, th: np.ndarray) -> pd.DataFrame:
    b = pd.read_pickle(W / "batches.pkl").sort_values(["job", "line"])
    for c in ["kind", "new_tok", "epoch"]:
        b["prev_" + c] = b.groupby("job")[c].shift(1)
    h = b[(b.kind == "P") & (b.new_seq == 1) & (b.new_tok == XH) & (b.running > 0) & (b.cached > 0)
          & (b.prev_kind == "P") & (b.prev_new_tok < 8192) & (b.prev_epoch == b.epoch)].copy()
    h["gap"] = h.new_tok / h.thr
    sumctx = np.clip(h.usage.values * M_TOK - (h.cached.values + h.new_tok.values), h.running.values * 1.0, None)
    h["tauD"] = simform_pred(th, h.running.values.astype(float), sumctx / NORM, None, "D")
    t = pd.to_datetime(h.ts)
    h["block"] = h.job.astype(str) + "_" + h.epoch.astype(str) + "_" + (t.astype("int64") // (120 * 10**9)).astype(str)
    return h


def comb_fit(h: pd.DataFrame, n_iter: int = 30):
    c, g, tD = h.cached.values.astype(float), h.gap.values, h.tauD.values
    # init: line through per-bin 3rd percentiles (lower envelope)
    bins = np.arange(0, 26000, 1000)
    idx = np.digitize(c, bins)
    xs, ys = [], []
    for i in np.unique(idx):
        m = idx == i
        if m.sum() >= 20:
            xs.append(np.median(c[m]))
            ys.append(np.quantile(g[m], 0.03))
    beta, alpha = np.polyfit(xs, ys, 1)
    for _ in range(n_iter):
        k = (g - (alpha + beta * c)) / tD
        mem = np.abs(k) < 0.5
        beta_n, alpha_n = np.polyfit(c[mem], g[mem], 1)
        if abs(beta_n - beta) < 1e-12 and abs(alpha_n - alpha) < 1e-9:
            break
        alpha, beta = alpha_n, beta_n
    k = (g - (alpha + beta * c)) / tD
    return alpha, beta, k


def main(work: str, seed: int, B: int) -> None:
    W = Path(work)
    res = json.loads((W / "fit_results.json").read_text())
    th = np.array(res["joint_simform_mid"]["est"])
    h = prep(W, th)
    alpha, beta, k = comb_fit(h)
    mem0 = np.abs(k) < 0.5
    mem1 = np.abs(k - 1) < 0.5
    mem2 = np.abs(k - 2) < 0.5
    rng = np.random.default_rng(seed)
    groups = {kk: v.index.values for kk, v in h.groupby("block")}
    keys = np.array(list(groups.keys()))
    boot = []
    for _ in range(B):
        pick = rng.choice(keys, size=len(keys), replace=True)
        hb = h.loc[np.concatenate([groups[x] for x in pick])]
        a_b, b_b, _ = comb_fit(hb)
        boot.append((a_b, b_b))
    boot = np.array(boot)
    e_hit = beta / XH                                   # s per (query, key) pair from the prefix
    # calibrated (chunk-fitted) model prediction for the same hits
    A = XH * h.cached.values + XH * (XH + 1) / 2.0
    tP_cal = th[0] + max(th[1], th[2] * XH) + th[4] * A
    rel_cal = (tP_cal[mem0] - h.gap.values[mem0]) / h.gap.values[mem0]
    out = dict(
        n_candidates=int(len(h)), n_k0=int(mem0.sum()), n_k1=int(mem1.sum()), n_k2=int(mem2.sum()),
        alpha_s=float(alpha), beta_s_per_cached_token=float(beta),
        alpha_ci=[float(np.quantile(boot[:, 0], q)) for q in (0.025, 0.975)],
        beta_ci=[float(np.quantile(boot[:, 1], q)) for q in (0.025, 0.975)],
        e_hit_s_per_pair=float(e_hit), e_hit_ci=[float(np.quantile(boot[:, 1], q) / XH) for q in (0.025, 0.975)],
        k0_resid_iqr_ms=[float(1e3 * q) for q in np.quantile(h.gap.values[mem0] - (alpha + beta * h.cached.values[mem0]), [0.25, 0.75])],
        # tooth spacing check: (gap - tau_P) on the k=1 / k=2 teeth divided by the decode model's tau_D
        k1_spacing_over_tauD_median=float(np.median((h.gap.values[mem1] - (alpha + beta * h.cached.values[mem1])) / h.tauD.values[mem1])),
        k2_spacing_over_tauD_median=float(np.median((h.gap.values[mem2] - (alpha + beta * h.cached.values[mem2])) / h.tauD.values[mem2])),
        calibrated_model_on_k0_median_rel=float(np.median(rel_cal)),
        calibrated_model_on_k0_by_cached={f"{lo}-{hi}": float(np.median(rel_cal[(h.cached.values[mem0] >= lo) & (h.cached.values[mem0] < hi)]))
                                          for lo, hi in ((0, 4000), (4000, 8000), (8000, 16000), (16000, 26000))
                                          if np.any((h.cached.values[mem0] >= lo) & (h.cached.values[mem0] < hi))},
        hit_time_s={f"cached{c}": float(alpha + beta * c) for c in (2000, 10000, 20000, 30000)},
        # tooth positions: median k_hat in [t-0.75, t+0.25) for t = 1..6 (teeth sit slightly below the integers)
        tooth_median_k_hat={str(t): float(np.median(k[(k >= t - 0.75) & (k < t + 0.25)])) for t in range(1, 7)},
        tooth_counts={str(t): int(np.sum((k >= t - 0.75) & (k < t + 0.25))) for t in range(0, 7)},
        seed=seed, n_boot=B)
    (W / "hits.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    c = h.cached.values / 1000
    ax[0].scatter(c[~mem0], 1e3 * h.gap.values[~mem0], s=3, color="0.75", label="k >= 1 or unassigned")
    ax[0].scatter(c[mem0], 1e3 * h.gap.values[mem0], s=4, color="#1b6ca8", label="k = 0 tooth (assigned)")
    gc = np.linspace(0, 26000, 50)
    ax[0].plot(gc / 1000, 1e3 * (alpha + beta * gc), "k-", lw=1, label="hit fit (k = 0 tooth)")
    ax[0].plot(gc / 1000, 1e3 * (th[0] + th[2] * XH + th[4] * (XH * gc + XH * (XH + 1) / 2)), color="#2e933c", lw=1,
               label="calibrated (chunk-fitted)")
    ax[0].plot(gc / 1000, 1e3 * (0.002 + 0.000084 * XH + 3.5e-9 * XH * (gc + XH)), color="#d1495b", lw=1, label="assumed")
    ax[0].set_ylim(0, 160)
    ax[0].set_xlabel("cached prefix c [k tokens]")
    ax[0].set_ylabel("gap since previous prefill [ms]")
    ax[0].set_title("Hit prefills (551 new tokens), previous batch line = Prefill", fontsize=9)
    ax[0].legend(fontsize=7)
    ax[1].hist(k[(k > -1) & (k < 6)], bins=140, color="#1b6ca8")
    ax[1].set_xlabel("k_hat = (gap - hit fit) / decode-model step [-]")
    ax[1].set_ylabel("count [prefill lines]")
    ax[1].set_title("Comb of decode steps: teeth at integers validate tau_D", fontsize=9)
    fig.tight_layout()
    fig.savefig(W / "hit_prefill_comb.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
