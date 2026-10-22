"""Sim vs real Stage C closed-population curve comparison (read-only on all inputs)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
RES = Path("/Users/akshat/research/jannesari-swapp/results")
R4 = RES / "prefix_meta_r4_curve/20261021-050856"
R5 = RES / "prefix_meta_r5_curve/20261021-070313"
R5L = RES / "prefix_meta_r5_curve_lpm128/20261021-070537"
REAL = RES / "nova/stageC_1706210x_pulled_20261022-125454"
NGRID = [16, 20, 24, 32, 48, 96, 300]
W0, W1 = 900.0, 2700.0

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 50)

# ---------------- sim
lam_r4 = json.loads((R4 / "meta.json").read_text())["lambda_miss"]
lam_r5 = json.loads((RES / "prefix_meta_r5_calib/20261021-070308/calib_summary.json").read_text())["lambda_miss"]
t4 = pd.read_csv(R4 / "curve_table.csv")
t4 = t4[t4.k == 1.0]
t5 = pd.read_csv(R5 / "curve_table.csv")
t5l = pd.read_csv(R5L / "curve_table.csv")


def sim_curve(src: str, mode: str | None, policy: str) -> pd.DataFrame:
    if src == "r4":
        d = t4[t4.policy == policy][["n", "mu_mean", "mu_se", "hit_rate_mean"]]
    else:
        d = t5[(t5["mode"] == mode) & (t5.policy == policy)].rename(columns={"n_nominal": "n"})
        d = d[["n", "mu_mean", "mu_se", "hit_rate_mean"]]
    return d.sort_values("n").reset_index(drop=True)


def interp_logn(d: pd.DataFrame, n: float, col: str) -> float:
    x = np.log(d["n"].to_numpy(float))
    return float(np.interp(np.log(n), x, d[col].to_numpy(float)))


curves = {
    "r4 FULL_RESERVE FCFS": sim_curve("r4", None, "fcfs_lru"),
    "r4 FULL_RESERVE LPM": sim_curve("r4", None, "lpm_lru"),
    "r5 RATIO FCFS": sim_curve("r5", "ratio_reserve", "fcfs_lru"),
    "r5 RATIO LPM": sim_curve("r5", "ratio_reserve", "lpm_lru"),
    "r5 ONDEMAND FCFS": sim_curve("r5", "ondemand_preempt", "fcfs_lru"),
    "r5 ONDEMAND LPM": sim_curve("r5", "ondemand_preempt", "lpm_lru"),
}
lam_of = {"r4": lam_r4, "r5 RATIO": lam_r5["ratio_reserve"], "r5 ONDEMAND": lam_r5["ondemand_preempt"]}
print("lambda_miss r4:", lam_r4, " r5:", lam_r5)

# ---------------- real
mc = pd.read_csv(REAL / "analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv")
mp = pd.read_csv(REAL / "analysis_local/agentload_analysis_closed/20261022-125619/mu_points.csv")


def eff_mean_turns(mean: float = 15, cap: int = 60) -> tuple[float, float]:
    p = 1.0 / mean
    k = np.arange(1, cap + 1)
    pk = p * (1 - p) ** (k - 1)
    pk[-1] += (1 - p) ** cap  # mass beyond cap lumps at cap
    ET = float((k * pk).sum())
    # all-miss prefill tokens per session: turn j prompt = 2000 + 650 (j-1)
    tok = 2000 * k + 650 * k * (k - 1) / 2
    Etok = float((tok * pk).sum())
    return ET, Etok


ET, ETOK = eff_mean_turns()
print(f"E[T]={ET:.4f}  E[all-miss prefill tokens/session]={ETOK:.0f}")

rows = []
win_rows = []
for _, pt in mp.iterrows():
    rd = REAL / "agentload_c_closed" / Path(pt.run_dir).name
    rq = pd.read_csv(rd / "requests.csv")
    ok = rq[rq.status == "ok"].copy()
    ok["prompt"] = ok.prompt_tokens.fillna(ok.prompt_tokens_client).astype(float)
    ok["cached"] = ok.cached_tokens.fillna(0).astype(float)
    ok["cf"] = ok.cached / ok.prompt
    sel = ok[(ok.t_complete >= W0) & (ok.t_complete < W1)]
    dur = W1 - W0
    # turn-2 prompt check
    t2 = ok[ok.turn == 2].prompt.median()
    rows.append(dict(
        label=pt.label, n=int(pt.n), turns=len(sel), sess=int((sel.turn == sel.n_turns).sum()),
        mu_sess=(sel.turn == sel.n_turns).sum() / dur, mu_turns=len(sel) / dur / ET,
        hit=(sel.cf > 0.5).mean(), partial=((sel.cf > 0) & (sel.cf <= 0.5)).mean(),
        hit_full=(sel.cf > 0.95).mean(),
        mean_prompt=sel.prompt.mean(), mean_turn=sel.turn.mean(),
        unc_tok_s=(sel.prompt - sel.cached).sum() / dur,
        mu_tok=(sel.prompt - sel.cached).sum() / dur / ETOK,
        mean_n_turns_done_sessions=sel[sel.turn == sel.n_turns].n_turns.mean(),
        t2_prompt=t2, max_t=ok.t_complete.max()))
    # 300-s windows over the whole run
    for a in np.arange(0, 2700, 300):
        s = ok[(ok.t_complete >= a) & (ok.t_complete < a + 300)]
        win_rows.append(dict(label=pt.label, n=int(pt.n), t0=a, turns_per_s=len(s) / 300,
                             hit=(s.cf > 0.5).mean() if len(s) else np.nan,
                             mean_prompt=s.prompt.mean() if len(s) else np.nan,
                             unc_tok_s=(s.prompt - s.cached).sum() / 300))
real = pd.DataFrame(rows).sort_values(["label", "n"]).reset_index(drop=True)
wins = pd.DataFrame(win_rows)
print("\nREAL recomputed [900,2700):")
print(real.to_string())
print("\nREAL vs harness mu_sessions max abs diff:",
      float(np.abs(real.set_index(["label", "n"]).mu_sess -
                   mc.set_index(["label", "n"]).mu_sessions).max()))
print("\nREAL 300-s windows (turns/s, hit, mean prompt, uncached tok/s):")
piv = wins.pivot_table(index=["label", "n"], columns="t0", values=["hit"]).round(2)
print(piv.to_string())
piv = wins.pivot_table(index=["label", "n"], columns="t0", values=["turns_per_s"]).round(2)
print(piv.to_string())
piv = wins.pivot_table(index=["label", "n"], columns="t0", values=["unc_tok_s"]).round(0)
print(piv.to_string())
piv = wins.pivot_table(index=["label", "n"], columns="t0", values=["mean_prompt"]).round(0)
print(piv.to_string())
real.to_csv(OUT / "real_recomputed.csv", index=False)
wins.to_csv(OUT / "real_windows300.csv", index=False)

# ---------------- sim synchronized-start window [1000,3000) (like-for-like with real [900,2700))
def sim_sync(path: Path, mode: str | None, policy: str) -> pd.DataFrame:
    w = pd.read_csv(path / "windows.csv")
    w = w[w.policy == policy]
    if mode is not None:
        w = w[w.variant.str.contains(f"mode={mode}|", regex=False)]
    else:
        w = w[w.variant.str.contains("k=1.0|", regex=False)]
    w = w.assign(n=w.variant.str.extract(r"n=(\d+)")[0].astype(int))
    early = w[(w.t_start >= 1000) & (w.t_end <= 3000)]
    late = w[w.t_start >= 5000]
    g1 = early.groupby(["n", "seed"]).agg(mu_e=("sessions_per_s", "mean"), hit_e=("hit_rate", "mean"),
                                          pf_e=("prefill_tok_per_s", "mean")).groupby("n").mean()
    g2 = late.groupby(["n", "seed"]).agg(mu_l=("sessions_per_s", "mean"), hit_l=("hit_rate", "mean"),
                                         pf_l=("prefill_tok_per_s", "mean")).groupby("n").mean()
    out = g1.join(g2)
    out["sync_bias"] = out.mu_e / out.mu_l - 1
    return out.reset_index()


sync = {
    "r4 FCFS": sim_sync(R4, None, "fcfs_lru"),
    "r4 LPM": sim_sync(R4, None, "lpm_lru"),
    "r5 RATIO FCFS": sim_sync(R5, "ratio_reserve", "fcfs_lru"),
    "r5 RATIO LPM": sim_sync(R5, "ratio_reserve", "lpm_lru"),
    "r5 RATIO LPM128": sim_sync(R5L, "ratio_reserve", "lpm128_lru"),
}
for k, v in sync.items():
    print(f"\nSIM sync-start window [1000,3000) vs steady [5000,35000): {k}")
    print(v.round(4).to_string())
    v.to_csv(OUT / f"sim_sync_{k.replace(' ', '_')}.csv", index=False)

# ---------------- main table at the real grid
fc = real[real.label == "sglang-fcfs-r1"].set_index("n")
lp = real[real.label == "sglang-lpm-r1"].set_index("n")
mu_max_real = fc.mu_sess.max()
tab = []
for n in NGRID:
    r = dict(n=n, real_mu=fc.mu_sess[n], real_norm=fc.mu_sess[n] / mu_max_real, real_hit=fc.hit[n],
             real_mu_tok=fc.mu_tok[n])
    for key, lab in [("r4 FULL_RESERVE FCFS", "r4"), ("r5 RATIO FCFS", "r5")]:
        d = curves[key]
        mx = d.mu_mean.max()
        mu = interp_logn(d, n, "mu_mean")
        r[f"{lab}_mu"] = mu
        r[f"{lab}_norm"] = mu / mx
        r[f"{lab}_hit"] = interp_logn(d, n, "hit_rate_mean")
        r[f"{lab}_exact"] = n in set(d.n)
        r[f"ratio_real/{lab}"] = fc.mu_sess[n] / mu
    for skey, slab in [("r4 FCFS", "r4s"), ("r5 RATIO FCFS", "r5s")]:
        sd = sync[skey].rename(columns={"mu_e": "mu_mean", "hit_e": "hit_rate_mean"})
        r[f"{slab}_mu"] = interp_logn(sd, n, "mu_mean")
        r[f"{slab}_norm"] = r[f"{slab}_mu"] / sd.mu_mean.max()
        r[f"{slab}_hit"] = interp_logn(sd, n, "hit_rate_mean")
        r[f"ratio_real/{slab}"] = fc.mu_sess[n] / r[f"{slab}_mu"]
    tab.append(r)
tab = pd.DataFrame(tab)
print("\nMAIN TABLE (FCFS):")
print(tab.round(4).to_string())
tab.to_csv(OUT / "main_table_fcfs.csv", index=False)

# summary stats
for key in ["r4 FULL_RESERVE FCFS", "r5 RATIO FCFS", "r5 ONDEMAND FCFS"]:
    d = curves[key]
    i = d.mu_mean.idxmax()
    on_grid = d[d.n.isin([16, 20, 24, 32])]
    j = on_grid.mu_mean.idxmax()
    # hit crossing 0.5 on fine grid
    h = d.hit_rate_mean.to_numpy(); nn = d.n.to_numpy(float)
    k = np.where((h[:-1] >= 0.5) & (h[1:] < 0.5))[0][0]
    nc = nn[k] + (h[k] - 0.5) / (h[k] - h[k + 1]) * (nn[k + 1] - nn[k])
    # on the real coarse grid
    hc = np.array([interp_logn(d, x, "hit_rate_mean") for x in NGRID]); ng = np.array(NGRID, float)
    kc = np.where((hc[:-1] >= 0.5) & (hc[1:] < 0.5))[0][0]
    ncc = ng[kc] + (hc[kc] - 0.5) / (hc[kc] - hc[kc + 1]) * (ng[kc + 1] - ng[kc])
    lam = lam_r4 if key.startswith("r4") else lam_r5["ratio_reserve" if "RATIO" in key else "ondemand_preempt"]
    n40 = d[d.n >= 40]
    print(f"\n{key}: n*={d.n[i]} mu_max={d.mu_mean[i]:.4f} (={d.mu_mean[i]/lam:.2f} lam) "
          f"n*_on_real_grid={on_grid.n[j]}  n_hit0.5 fine={nc:.1f} coarse={ncc:.1f}  "
          f"mu(n>=40)/lam range {n40.mu_mean.min()/lam:.3f}-{n40.mu_mean.max()/lam:.3f} "
          f"hit(n>=40) max {n40.hit_rate_mean.max():.3f}; mu(300)/mu_max={d.mu_mean.iloc[-1]/d.mu_mean[i]:.3f}")
hr = fc.hit.to_numpy(); ng = np.array(NGRID, float)
kc = np.where((hr[:-1] >= 0.5) & (hr[1:] < 0.5))[0][0]
print(f"\nREAL: n*={fc.mu_sess.idxmax()} mu_max={mu_max_real:.4f} runner-up margin "
      f"{(mu_max_real - fc.mu_sess.drop(fc.mu_sess.idxmax()).max())/mu_max_real:.3f}; n_hit0.5 coarse="
      f"{ng[kc] + (hr[kc]-0.5)/(hr[kc]-hr[kc+1])*(ng[kc+1]-ng[kc]):.1f}")
print("REAL mu_max / lam_r4 =", mu_max_real / lam_r4, "; real mu(48) / lam_r4 =", fc.mu_sess[48] / lam_r4)

# LPM vs FCFS
print("\nLPM vs FCFS:")
for n in [48, 300]:
    print(f" real n={n}: LPM/FCFS mu={lp.mu_sess[n]/fc.mu_sess[n]:.3f} (sess) "
          f"{lp.mu_turns[n]/fc.mu_turns[n]:.3f} (turns) {lp.mu_tok[n]/fc.mu_tok[n]:.3f} (uncached tok); "
          f"hit LPM={lp.hit[n]:.3f} FCFS={fc.hit[n]:.3f}; LPM partial={lp.partial[n]:.3f}")
    for a, b, lam in [("r4 FULL_RESERVE LPM", "r4 FULL_RESERVE FCFS", lam_r4),
                      ("r5 RATIO LPM", "r5 RATIO FCFS", lam_r5["ratio_reserve"])]:
        mL, mF = interp_logn(curves[a], n, "mu_mean"), interp_logn(curves[b], n, "mu_mean")
        print(f"  sim {a}: LPM/FCFS={mL/mF:.3f}, LPM/lam={mL/lam:.3f}, hit LPM={interp_logn(curves[a], n, 'hit_rate_mean'):.3f}")
l128 = t5l[t5l["mode"] == "ratio_reserve"].iloc[0]
f300 = curves["r5 RATIO FCFS"].set_index("n").loc[300]
print(f"  sim r5 RATIO LPM128 n=300: mu={l128.mu_mean:.4f} LPM128/FCFS={l128.mu_mean/f300.mu_mean:.3f} "
      f"/lam={l128.mu_mean/lam_r5['ratio_reserve']:.3f} hit={l128.hit_rate_mean:.3f}")
l128o = t5l[t5l["mode"] == "ondemand_preempt"].iloc[0]
print(f"  sim r5 ONDEMAND LPM128 n=300: mu={l128o.mu_mean:.4f} hit={l128o.hit_rate_mean:.3f}")

# real all-miss token-normalised vs sim prefill
print("\nAll-miss prefill throughput (uncached tok/s): real", fc.unc_tok_s.round(0).to_dict(),
      " sim r5 RATIO FCFS steady:", sync["r5 RATIO FCFS"].set_index("n").pf_l.round(0).to_dict())

# ---------------- figure
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 2, figsize=(10.5, 5.6))
sty = {"r4 FULL_RESERVE FCFS": ("C0", "-"), "r5 RATIO FCFS": ("C1", "-"),
       "r4 FULL_RESERVE LPM": ("C0", ":"), "r5 RATIO LPM": ("C1", ":")}
lab = {"r4 FULL_RESERVE FCFS": "sim r4 FCFS (full reserve)", "r5 RATIO FCFS": "sim r5 FCFS (SGLang-like ratio)",
       "r4 FULL_RESERVE LPM": "sim r4 ideal LPM", "r5 RATIO LPM": "sim r5 ideal LPM"}
for key, (c, ls) in sty.items():
    d = curves[key]
    base = curves[key.replace("LPM", "FCFS")].mu_mean.max()
    ax[0].plot(d.n, d.mu_mean / base, color=c, ls=ls, lw=1.4, label=lab[key])
    ax[1].plot(d.n, d.hit_rate_mean, color=c, ls=ls, lw=1.4, label=lab[key])
s4 = sync["r4 FCFS"]
ax[0].plot(s4.n, s4.mu_e / s4.mu_e.max(), color="C0", ls="--", lw=1.0,
           label="sim r4 FCFS, same protocol: sync start, window [1000,3000) s")
ax[1].plot(s4.n, s4.hit_e, color="C0", ls="--", lw=1.0, label="sim r4 FCFS, sync window [1000,3000) s")
s5 = sync["r5 RATIO FCFS"]
ax[0].plot(s5.n, s5.mu_e / s5.mu_e.max(), "^", mfc="none", color="C1", ms=5,
           label="sim r5 FCFS, sync window [1000,3000) s")
ax[0].plot([300], [l128.mu_mean / curves["r5 RATIO FCFS"].mu_mean.max()], "x", color="C1", ms=8, mew=1.5,
           label="sim r5 LPM-128 (n=300)")
ax[1].plot([300], [l128.hit_rate_mean], "x", color="C1", ms=8, mew=1.5)
ax[0].plot(fc.index, fc.mu_sess / mu_max_real, "ks-", ms=5, lw=1.2, label="real SGLang FCFS (sessions/s)")
fa = fc[fc.hit < 0.01]
ax[0].plot(fa.index, fa.mu_tok / mu_max_real, "ko", ms=5, mfc="none", ls="none",
           label="real FCFS all-miss proxy: uncached tok/s / E[tok/session]")
ax[0].plot(lp.index, lp.mu_sess / mu_max_real, "D", color="C3", ms=6, ls="none", label="real SGLang LPM")
ax[1].plot(fc.index, fc.hit, "ks-", ms=5, lw=1.2, label="real FCFS")
ax[1].plot(lp.index, lp.hit, "D", color="C3", ms=6, ls="none", label="real LPM")
for a in ax:
    a.set_xscale("log")
    a.set_xlabel("closed population n (concurrent sessions)")
    a.set_xlim(7, 340)
    a.set_xticks([8, 16, 24, 32, 48, 96, 300]); a.set_xticklabels(["8", "16", "24", "32", "48", "96", "300"])
    a.minorticks_off()
    a.grid(alpha=0.3)
ax[0].set_ylabel(r"$\mu(n)/\mu_{\max}^{\mathrm{FCFS}}$ (dimensionless)")
ax[1].set_ylabel("hit fraction of turns (dimensionless)")
ax[0].set_title("Normalized session throughput")
ax[1].set_title("Prefix-cache hit fraction")
ax[0].legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
ax[1].legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
ax[0].set_ylim(0, 1.1); ax[1].set_ylim(-0.03, 1.0)
fig.suptitle("Stage C: real SGLang (1 seed, 900+1800 s, sync start) vs simulator (3 seeds, 35k s), M=300k tokens",
             fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "simcmp_stageC.pdf")
print("\nwrote", OUT / "simcmp_stageC.pdf")
