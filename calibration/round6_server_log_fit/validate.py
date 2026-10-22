"""Out-of-sample checks, per-job robustness, residual plots and derived quantities.

Usage: python validate.py <work_dir>
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
from fit import NORM, SIM, dec_lin_design, metrics, pre_design, simform_pred, wls, load  # noqa: E402

CHUNK = 8192
M_TOK = 300000


def pre_mid(theta_lin, X, prefix):
    a, b, e = theta_lin
    return a + b * X + e * (X * prefix + X * (X + 1) / 2.0)


def chain_bounds(batches: pd.DataFrame) -> pd.DataFrame:
    """For every Prefill line that directly follows a truncated (8192-token) Prefill line and has one sequence,
    bound the continuation's prefix [lo, hi] using the chain of chunk sizes (first chunk inside a multi-seq batch
    has an unknown size)."""
    rows = []
    for job, g in batches.groupby("job", sort=False):
        g = g.sort_values("line")
        lo = hi = np.nan
        prev_trunc = False
        prev_epoch = None
        for r in g.itertuples(index=False):
            if r.kind != "P":
                prev_trunc, lo, hi, prev_epoch = False, np.nan, np.nan, r.epoch
                continue
            cont = prev_trunc and prev_epoch == r.epoch
            X = r.new_tok
            trunc = X == CHUNK
            nlo = nhi = np.nan
            if r.new_seq == 1:
                if cont:
                    plo, phi = lo, hi
                    rows.append(dict(job=job, line=r.line, X=X, plo=plo, phi=phi, gap=X / r.thr, usage=r.usage))
                else:
                    plo = phi = float(r.cached)
                if trunc:
                    nlo, nhi = plo + X, phi + X
            else:
                if trunc:
                    # last request truncated: own first chunk j in [1, X - (n-1) - (1 if cont)], own prefix in [0, cached]
                    jmax = X - (r.new_seq - 1) - (1 if cont else 0)
                    nlo, nhi = 1.0, float(jmax + r.cached)
            lo, hi, prev_trunc, prev_epoch = nlo, nhi, trunc, r.epoch
    return pd.DataFrame(rows)


def main(work: str) -> None:
    W = Path(work)
    res = json.loads((W / "fit_results.json").read_text())
    D, P, Pall = load(str(W / "obs"))
    batches = pd.read_pickle(W / "batches.pkl")
    th = np.array(res["joint_simform_mid"]["est"])            # calibration (simulator form, mid convention)
    lin_d = np.array(res["decode_linear"]["est"])
    lin_p = np.array(res["prefill_linear_mid"]["est"])
    out = {}

    # ------------------------------------------------------------------ per-job robustness (linear fits)
    pj = {}
    for job in sorted(set(D.job) | set(P.job)):
        d, p = D[D.job == job], P[P.job == job]
        e = {}
        if len(d) >= 30:
            e["decode_linear"] = dict(n=len(d), est=wls(dec_lin_design(d), d.tau.values).tolist())
        if len(p) >= 30:
            e["prefill_linear_mid"] = dict(n=len(p), est=wls(pre_design(p, "mid"), p.gap.values).tolist())
        pj[job] = e
    out["per_job"] = pj

    # ------------------------------------------------------------------ validation 1: continuation chunks, prefix bounded
    cb = chain_bounds(batches)
    cb = cb[np.isfinite(cb.plo)].copy()
    cb["unknown"] = cb.plo != cb.phi
    v = cb[cb.unknown].copy()
    th_s = th
    def calib_P(X, prefix):
        A = X * prefix + X * (X + 1) / 2.0
        return th_s[0] + np.maximum(th_s[1], th_s[2] * X) + th_s[4] * A
    v["pred_lo"] = calib_P(v.X.values, v.plo.values)
    v["pred_hi"] = calib_P(v.X.values, v.phi.values)
    tol = 0.02
    inside = (v.gap >= v.pred_lo * (1 - tol)) & (v.gap <= v.pred_hi * (1 + tol))
    width = (v.phi - v.plo)
    out["val_unknown_prefix_chunks"] = dict(
        n=int(len(v)), frac_inside_pm2pct=float(inside.mean()),
        frac_below=float((v.gap < v.pred_lo * (1 - tol)).mean()), frac_above=float((v.gap > v.pred_hi * (1 + tol)).mean()),
        median_bound_width_tokens=float(width.median()))
    # implied prefix point estimate from observed time (inverse of the model) and whether it lies in the bound
    X = v.X.values.astype(float)
    pref_hat = (v.gap.values - th_s[0] - np.maximum(th_s[1], th_s[2] * X) - th_s[4] * X * (X + 1) / 2) / (th_s[4] * X)
    out["val_unknown_prefix_chunks"]["frac_implied_prefix_in_bound_pm2048"] = float(
        np.mean((pref_hat >= v.plo.values - 2048) & (pref_hat <= v.phi.values + 2048)))

    # ------------------------------------------------------------------ validation 2: hit prefills, integer number of decodes
    b = batches.sort_values(["job", "line"]).copy()
    b["prev_kind"] = b.groupby("job").kind.shift(1)
    b["prev_new_tok"] = b.groupby("job").new_tok.shift(1)
    h = b[(b.kind == "P") & (b.new_seq == 1) & (b.new_tok < CHUNK) & (b.running > 0) & (b.cached > 0)
          & ~((b.prev_kind == "P") & (b.prev_new_tok == CHUNK))].copy()
    h["gap"] = h.new_tok / h.thr
    h["tauP"] = calib_P(h.new_tok.values.astype(float), h.cached.values.astype(float))
    sumctx = np.clip(h.usage.values * M_TOK - (h.cached.values + h.new_tok.values), h.running.values * 1.0, None)
    h["tauD"] = simform_pred(th, h.running.values.astype(float), sumctx / NORM, None, "D")
    h["k_hat"] = (h.gap - h.tauP) / h.tauD
    hk = h[(h.k_hat > -0.5) & (h.k_hat < 3.5)]
    frac = hk.k_hat - np.round(hk.k_hat)
    out["val_hit_prefill_integer_k"] = dict(
        n_hits=int(len(h)), n_k_below_3p5=int(len(hk)),
        frac_k_hat_below_minus0p5=float((h.k_hat < -0.5).mean()),
        frac_within_0p2_of_integer=float((np.abs(frac) < 0.2).mean()),
        expected_if_uniform=0.4,
        median_X=float(h.new_tok.median()), median_cached=float(h.cached.median()))
    # k == 0 cluster (prefill directly after a prefill): implied tauP
    k0 = hk[np.abs(hk.k_hat) < 0.5]
    out["val_hit_prefill_integer_k"]["k0_n"] = int(len(k0))
    out["val_hit_prefill_integer_k"]["k0_median_rel_err"] = float(np.median((k0.tauP - k0.gap) / k0.gap)) if len(k0) else None

    # ------------------------------------------------------------------ derived quantities
    der = {}
    for name, f in (("calib", lambda X, p: calib_P(X, p)), ("prefill_linear_mid", lambda X, p: pre_mid(lin_p, X, p)),
                    ("sim_assumed_end", lambda X, p: SIM["iter_fixed_s"] + np.maximum(SIM["iter_floor_s"], SIM["per_token_s"] * X) + SIM["prefill_attn_s"] * X * (p + X))):
        d = {}
        for pre in (0, 8192, 16384, 24576, 32768):
            t = float(f(8192.0, float(pre)))
            d[f"chunk8192_prefix{pre}"] = dict(t_s=t, tok_per_s=8192 / t)
        for Ptot in (2000, 2650, 8000, 16000, 32000):
            t = 0.0
            done = 0
            while done < Ptot:
                x = min(CHUNK, Ptot - done)
                t += float(f(float(x), float(done)))
                done += x
            d[f"full_miss_P{Ptot}"] = dict(t_s=t, tok_per_s=Ptot / t)
        h551 = {}
        for c in (2000, 10000, 20000, 30000):
            h551[f"cached{c}"] = float(f(551.0, float(c)))
        d["hit_551_new_t_s"] = h551
        der[name] = d
    # decode step times
    dd = {}
    for R in (16, 32, 64):
        e = {}
        for per in (2650, 8192, 16384):
            S = min(R * per, 295000)
            e[f"ctx_per_seq{per}" + ("_capped295k" if R * per > 295000 else "")] = dict(
                sumctx=S, calib_s=float(simform_pred(th, np.array([float(R)]), np.array([S / NORM]), None, "D")[0]),
                decode_linear_s=float(lin_d[0] + lin_d[1] * R + lin_d[2] * S / NORM),
                sim_assumed_s=float(SIM["iter_fixed_s"] + max(SIM["iter_floor_s"], SIM["per_token_s"] * R) + SIM["decode_attn_s"] * S / NORM))
        sel = D[(D.running >= R * 0.8) & (D.running <= R * 1.25)]
        e["empirical_near_R"] = dict(n=int(len(sel)), R_range=[int(sel.running.min()), int(sel.running.max())] if len(sel) else None,
                                      median_tau_s=float(sel.tau.median()) if len(sel) else None,
                                      median_sumctx=float(sel.sumctx.median()) if len(sel) else None)
        dd[f"R{R}"] = e
    der["decode"] = dd
    # model-free prefill throughput over clean batches, all-miss work only (no cached tokens in the batch)
    Pc = Pall[Pall.clean]
    mm = Pc[(Pc.cached == 0)]
    der["empirical_clean_prefill_cached0"] = dict(n=int(len(mm)), tokens=int(mm.X.sum()), seconds=float(mm.gap.sum()),
                                                  tok_per_s=float(mm.X.sum() / mm.gap.sum()),
                                                  by_job={j: float(x.X.sum() / x.gap.sum()) for j, x in mm.groupby("job")})
    out["derived"] = der
    (W / "validation.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

    # ------------------------------------------------------------------ plots
    jobs = sorted(set(D.job) | set(P.job))
    colors = dict(zip(jobs, ["#1b6ca8", "#d1495b", "#2e933c", "#edae49"]))
    pD = simform_pred(th, D.running.values.astype(float), D.sumctx.values / NORM, None, "D")
    pP = simform_pred(th, P.X.values.astype(float), None, P.attn_mid.values, "P")
    rD = (pD - D.tau.values) / D.tau.values
    rP = (pP - P.gap.values) / P.gap.values
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.5))
    for j in jobs:
        m = (D.job == j).values
        ax[0, 0].scatter(D.running.values[m], 100 * rD[m], s=6, alpha=0.6, color=colors[j], label=j)
        ax[0, 1].scatter(D.sumctx.values[m] / NORM, 100 * rD[m], s=6, alpha=0.6, color=colors[j])
        ax[0, 2].scatter(1e3 * D.tau.values[m], 1e3 * pD[m], s=6, alpha=0.6, color=colors[j])
        m = (P.job == j).values
        ax[1, 0].scatter(P.X.values[m], 100 * rP[m], s=6, alpha=0.6, color=colors[j])
        ax[1, 1].scatter(P.prefix.values[m] / 1000, 100 * rP[m], s=6, alpha=0.6, color=colors[j])
        ax[1, 2].scatter(1e3 * P.gap.values[m], 1e3 * pP[m], s=6, alpha=0.6, color=colors[j])
    for a in (ax[0, 0], ax[0, 1], ax[1, 0], ax[1, 1]):
        a.axhline(0, color="k", lw=0.8)
        a.set_ylabel("relative residual (pred - obs)/obs [%]")
    ax[0, 0].set_xlabel("decode batch size R [sequences]")
    ax[0, 1].set_xlabel("sum of contexts / 8192 [-]")
    ax[0, 0].legend(title="job", fontsize=7, markerscale=2)
    ax[1, 0].set_xlabel("prefill new tokens X [tokens]")
    ax[1, 1].set_xlabel("prefix (KV before chunk) [k tokens]")
    for a, lab in ((ax[0, 2], "decode"), (ax[1, 2], "prefill")):
        lim = [0, max(a.get_xlim()[1], a.get_ylim()[1])]
        a.plot(lim, lim, "k-", lw=0.8)
        a.set_xlabel(f"observed {lab} iteration time [ms]")
        a.set_ylabel(f"calibrated-model {lab} time [ms]")
    ax[0, 0].set_title("Decode (40-iteration clean windows)")
    ax[1, 0].set_title("Prefill (clean continuation chunks, known prefix)")
    fig.tight_layout()
    fig.savefig(W / "residuals_calibrated.pdf")
    plt.close(fig)

    # assumed vs calibrated vs observed
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    sD = (D.sumctx / NORM).values
    sc = ax[0].scatter(sD, 1e3 * D.tau.values, c=D.running.values, s=6, cmap="viridis", label="observed")
    g = np.linspace(0, 37, 50)
    for R, ls in ((1, "-"), (32, "--"), (128, ":")):
        ax[0].plot(g, 1e3 * simform_pred(th, np.full_like(g, R), g, None, "D"), "k" + ls, lw=1, label=f"calibrated, R={R}")
        ax[0].plot(g, 1e3 * (SIM["iter_fixed_s"] + max(SIM["iter_floor_s"], SIM["per_token_s"] * R) + SIM["decode_attn_s"] * g),
                   color="#d1495b", ls=ls, lw=1, label=f"assumed, R={R}")
    plt.colorbar(sc, ax=ax[0], label="R [sequences]")
    ax[0].set_xlabel("sum of contexts / 8192 [-]")
    ax[0].set_ylabel("decode iteration time [ms]")
    ax[0].legend(fontsize=7)
    m8 = P.X.values == CHUNK
    ax[1].scatter(P.prefix.values[m8] / 1000, 1e3 * P.gap.values[m8], s=6, color="#1b6ca8", label="observed, X=8192")
    gp = np.linspace(0, 36000, 50)
    ax[1].plot(gp / 1000, 1e3 * calib_P(8192.0, gp), "k-", lw=1, label="calibrated (mid)")
    ax[1].plot(gp / 1000, 1e3 * (SIM["iter_fixed_s"] + SIM["per_token_s"] * 8192 + SIM["prefill_attn_s"] * 8192 * (gp + 8192)),
               color="#d1495b", lw=1, label="assumed (end)")
    ax[1].set_xlabel("prefix before the chunk [k tokens]")
    ax[1].set_ylabel("prefill iteration time, 8192-token chunk [ms]")
    ax[1].set_xlim(left=0)
    ax[1].set_ylim(bottom=0)
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(W / "assumed_vs_calibrated.pdf")
    plt.close(fig)

    # hit-prefill integer-k histogram
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(h.k_hat[(h.k_hat > -1) & (h.k_hat < 8)], bins=180, color="#1b6ca8")
    ax.set_xlabel("(gap - predicted prefill time) / predicted decode step [-]")
    ax.set_ylabel("count [prefill lines]")
    ax.set_title("Hit prefills: implied number of decode steps in the gap", fontsize=9)
    fig.tight_layout()
    fig.savefig(W / "hit_prefill_integer_k.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1])
