r"""Every summary number quoted in notes/THEORY_ICML_2026-11.md sections 6.1-6.7, computed from results/theory/icml/trap_check.json
(run_check) and the frozen cell models.

    PYTHONPATH="src;." python -m analysis.theory.icml.support          # writes results/theory/icml/support.json (~3 min)
"""
from __future__ import annotations

import json
import os

import numpy as np

from ..merged.spec import ROOT
from .run_check import cell_model
from .trap_renewal import fifo_fluid, trap_asymptotics, trap_costs, window_stats

CELLS = ["a100_300k", "a100_native", "vllm_300k", "llama31_fit", "h200_300k", "h200_600k", "a100_pool150k", "a100_pool600k"]
# registered E2 cells (registered slope rule 0.5 (lambda - lambda_ref)); vLLM includes the exploratory runs on the same plans
REGISTERED = {"sglang-fcfs-r1", "sglang-fcfs-r1-native", "vllm-fcfs", "sglang-fcfs-r1-h200-p600k", "sglang-fcfs-r1-llama31"}


def premium_scan() -> dict:
    out = {}
    for c in CELLS:
        m, _ = cell_model(c)
        tc = trap_costs(m)
        rhos = np.concatenate([1 + np.logspace(-4, 0, 40), np.linspace(2.05, 10, 80)])
        A = [trap_asymptotics(r * tc.lam_miss, tc) for r in rhos]
        pr = np.array([a["premium"] for a in A])
        Dl = np.array([a["D_over_lam_miss"] for a in A])
        out[c] = dict(lam_miss=tc.lam_miss, c_nondecreasing=bool(np.all(np.diff(tc.c) >= 0)), min_premium=float(pr.min()),
                      argmin_rho=float(rhos[pr.argmin()]), premium_slope_at_1=float(pr[0] / (rhos[0] - 1)),
                      predicted_slope_at_1=float(1 - A[0]["near_threshold_coef"]),
                      min_H=float(min(a["H_T"] for a in A)), one_minus_qK=float(1 - (1 - 1 / 15.0) ** 60),
                      near_coef=float(A[0]["near_threshold_coef"]), kbar_c=float(A[0]["kbar_c"]), ET=float(tc.ET),
                      c60_over_c1=float(tc.c[-1] / tc.c[0]), D_increasing=bool(np.all(np.diff(Dl) > 0)))
    return out


def premium_certificate(n_ratio: float = 1.5, eps: float = 1e-12) -> dict:
    """Theorem 2(vi) plus a monotone bracket (suggested by the Theorem 2 referee). For T = min(Geometric(1 - q), K),
    H(z) is non-increasing and Gamma(z) non-decreasing in z (c non-decreasing), so on [z_i, z_{i+1}] the premium is at least
    H(z_{i+1}) Gamma(z_i) - 1. Check that lower bound on a geometric grid of z - 1 from eps to z_1 (where Gamma(z_1) =
    1/(1 - q^K)); above z_1 Theorem 2(vi) applies. Floating point, not interval arithmetic."""
    from scipy.optimize import brentq
    q, K = 1 - 1 / 15.0, 60
    out = {}
    for c in CELLS:
        m, _ = cell_model(c)
        tc = trap_costs(m)

        def H(z):
            zk = z ** (-tc.k)
            S = float((tc.G * zk).sum())
            return 1 - q ** K * (1 - tc.ET * z ** (-K) / S)

        def Gam(z):
            zk = z ** (-tc.k)
            S = float((tc.G * zk).sum())
            return (float((tc.c * tc.G).sum()) / tc.ET) / (float((tc.c * tc.G * zk).sum()) / S)

        sup_gamma = (float((tc.c * tc.G).sum()) / tc.ET) / float(tc.c[0])
        thr = 1 / (1 - q ** K)
        z1 = brentq(lambda z: Gam(z) - thr, 1 + 1e-15, 50.0, xtol=1e-15) if sup_gamma > thr else None
        grid = [1 + eps]
        while grid[-1] < z1:
            grid.append(1 + (grid[-1] - 1) * n_ratio)
        grid[-1] = z1
        lows = [H(grid[i + 1]) * Gam(grid[i]) - 1 for i in range(len(grid) - 1)]
        # normalised margin: bracket lower bound over (z_{i+1} - 1)
        norm = [lows[i] / (grid[i + 1] - 1) for i in range(len(lows))]
        out[c] = dict(sup_Gamma=sup_gamma, needed=thr, z1=z1, n_brackets=len(lows), min_bracket_lower_bound=float(min(lows)),
                      min_normalised_margin=float(min(norm)), all_positive=bool(min(lows) > 0), eps=eps)
    return out


def kendall_numbers() -> list:
    """Remark 5 (classical; Kendall 1951): with realized remaining work w, the all-miss queue ever empties with probability
    exp(-lambda (1 - q) w), q the least root of q = E[exp(-lambda W(T) (1 - q))]. w is taken from the exact FIFO fluid
    (sum over pending mass of the class's remaining work) 3000 s after the registered burst on the 300k cell; a fluid
    stand-in for a realized value, so the numbers are orders of magnitude."""
    m, _ = cell_model("a100_300k")
    tc = trap_costs(m)
    W = np.cumsum(tc.c)
    rows = []
    for rho in (1.01, 1.02, 1.05, 1.10, 1.35, 1.65):
        lam = rho * tc.lam_miss
        qq = 0.0
        for _ in range(200000):
            qn = float((tc.p * np.exp(-lam * W * (1 - qq))).sum())
            if abs(qn - qq) < 1e-16:
                break
            qq = qn
        tr = fifo_fluid(lam, tc, 0.0, t_end=4200.0, grid=600.0)
        w = float(tr["Vtot"][-1])
        rows.append(dict(rho=rho, q=qq, one_minus_q=1 - qq, N_4200=float(tr["N"][-1]), Vtot_4200=w,
                         p_empty=float(np.exp(-lam * (1 - qq) * w))))
    return rows


def data_summaries(path: str) -> dict:
    J = json.load(open(path))
    rows = []
    for g in J["groups"]:
        a, me = g["asym"], g["measured"]
        fw = g.get("fluid_window") or {}
        for i, seed in enumerate(g["seeds"]):
            lw = me["arrival_rate_window"][i]
            thr = 0.5 * (g["lam"] - g["lam_ref"])
            rows.append(dict(kind=g["kind"], label=g["label"], mult=g["rate_mult"], seed=seed, run=g["runs"][i],
                             P_err=me["P_served_mean"][i] / a["P_served_mean"] - 1.0,
                             P_err_fluid=(me["P_served_mean"][i] / fw["P_served_mean"] - 1.0) if fw else None,
                             gap_ratio=me["gap_med_slope"][i] / a["gamma"],
                             compl_over_D=me["completion_rate"][i] / a["D"],
                             compl_over_lref=me["completion_rate"][i] / g["lam_ref"],
                             slope=me["backlog_slope"][i], slope_frac=me["backlog_slope"][i] / (g["lam"] - g["lam_ref"]),
                             plugin=lw - a["D"], plugin_resid=me["backlog_slope"][i] - (lw - a["D"]), threshold=thr,
                             meas_above=bool(me["backlog_slope"][i] > thr), plugin_above=bool(lw - a["D"] > thr),
                             lam_window_over_nominal=lw / g["lam"]))
    e2 = [r for r in rows if r["kind"] == "e2"]
    e0b = [r for r in rows if r["kind"] == "e0b"]
    reg = [r for r in e2 if r["label"] in REGISTERED]
    agree = sum(1 for r in reg if r["meas_above"] == r["plugin_above"])
    s = dict(
        n_e2_runs=len(e2), n_e0b_runs=len(e0b), n_e2_groups=len({(r["label"], r["mult"]) for r in e2}),
        P_err_e2=[min(r["P_err"] for r in e2), max(r["P_err"] for r in e2)],
        P_err_e2_within3=sum(1 for r in e2 if abs(r["P_err"]) <= 0.03), P_err_e2_within5=sum(1 for r in e2 if abs(r["P_err"]) <= 0.05),
        P_err_e0b=[min(r["P_err"] for r in e0b), max(r["P_err"] for r in e0b)],
        gap_ratio_mean_e2=float(np.mean([r["gap_ratio"] for r in e2])), gap_ratio_median_e2=float(np.median([r["gap_ratio"] for r in e2])),
        gap_ratio_mean_e0b=float(np.mean([r["gap_ratio"] for r in e0b])),
        compl_over_D_e2=[min(r["compl_over_D"] for r in e2), max(r["compl_over_D"] for r in e2)],
        compl_over_D_e2_mean=float(np.mean([r["compl_over_D"] for r in e2])),
        compl_over_lref_all=[min(r["compl_over_lref"] for r in rows), max(r["compl_over_lref"] for r in rows)],
        all_above_lref=all(r["compl_over_lref"] > 1 for r in rows),
        slope_frac_e2=[min(r["slope_frac"] for r in e2), max(r["slope_frac"] for r in e2)],
        slope_frac_e2_mean=float(np.mean([r["slope_frac"] for r in e2])),
        plugin_resid_e2_median=float(np.median([r["plugin_resid"] for r in e2])),
        plugin_resid_abs_le_0p002=sum(1 for r in e2 if abs(r["plugin_resid"]) <= 0.002),
        plugin_resid_abs_le_0p01=sum(1 for r in e2 if abs(r["plugin_resid"]) <= 0.01),
        registered_runs=len(reg), registered_threshold_side_agreement=agree,
        registered_disagreements=[dict(label=r["label"], mult=r["mult"], seed=r["seed"], slope=round(r["slope"], 4),
                                       plugin=round(r["plugin"], 4), threshold=round(r["threshold"], 4)) for r in reg
                                  if r["meas_above"] != r["plugin_above"]],
        registered_below_threshold=[dict(label=r["label"], mult=r["mult"], seed=r["seed"], slope=round(r["slope"], 4),
                                         plugin=round(r["plugin"], 4), threshold=round(r["threshold"], 4)) for r in reg
                                    if not r["meas_above"]],
        seed1_window_dip=sorted({round(1 - r["lam_window_over_nominal"], 3) for r in e2 if r["seed"] == 1}),
    )
    return dict(summary=s, rows=rows)


def fluid_checks() -> dict:
    m, _ = cell_model("a100_300k")
    tc = trap_costs(m)
    out = {}
    think = {}
    for mult, n1 in ((1.35, 8.47), (1.65, 10.4)):
        lam = mult * 0.071534
        r = {}
        for th in (0.0, 5.0):
            r[str(th)] = window_stats(fifo_fluid(lam, tc, n1, think=th), 5700.0, 8700.0, tc)
        think[str(mult)] = r
    out["think_time"] = think
    lam = 1.65 * 0.071534
    tr = fifo_fluid(lam, tc, 10.4, t_end=30000.0, grid=100.0, dt_arr=1.0, orbit_from=1300.0)
    orb = tr["orbit"]
    D = orb[:, 1]
    a = lam * tc.c * tc.G
    K = len(a)
    res = [(D[n] - sum(a[k - 1] * D[n - k] for k in range(1, K + 1))) / D[n] for n in range(K, len(D))]
    out["orbit"] = dict(steps=int(len(D)), max_abs_rel_residual=float(np.max(np.abs(res))), last_V_over_u=float(D[-1] / orb[-1, 0]),
                        gamma=trap_asymptotics(lam, tc)["gamma"])
    cuts = []
    Dp = trap_asymptotics(lam, tc)["D"]
    for f in (0.90, 1.05, 1.10, 1.18):
        tr = fifo_fluid(lam, tc, 10.4, t_end=30000.0, grid=50.0, dt_arr=5.0, lam_after=[(5000.0, f * tc.lam_miss)])
        N, tt = tr["N"], tr["t"]
        i5 = int(np.searchsorted(tt, 5000.0))
        im = i5 + int(np.argmin(N[i5:]))
        cuts.append(dict(cut_over_lam_miss=f, D_over_lam_miss=Dp / tc.lam_miss, N_at_cut=float(N[i5]), N_min=float(N[im]),
                         t_min=float(tt[im]), N_30000=float(N[-1])))
    out["cuts"] = cuts
    lam = 1.35 * 0.071534
    tr = fifo_fluid(lam, tc, 8.47, t_end=9000.0, grid=5.0, lam_after=[(1800.0, 0.0)])
    N, t = tr["N"], tr["t"]
    nb = float(m.bad()["n_b"])
    i = int(np.argmax((t > 1800) & (N < nb)))
    j = int(np.argmax((t > 1800) & (N < 0.5)))
    out["shed"] = dict(N_1800=float(N[t >= 1800][0]), N_2400=float(N[t >= 2400][0]), n_b=nb, t_to_n_b=float(t[i] - 1800),
                       t_to_empty=float(t[j] - 1800), N_5400=float(N[t >= 5400][0]))
    return out


def self_similarity(path: str) -> list:
    """Theorem 1(d): a session joining at u finishes near u z^T, so among stuck runs the sojourn of base sessions with
    similar T grows linearly in the arrival time with slope about E[z^T - 1]. Completed base sessions arriving in
    [2500, 7000) s; right-censoring at 8700 s biases long-T, high-z bins down (late long sessions have not finished)."""
    import csv
    J = json.load(open(path))
    out = []
    for g in J["groups"]:
        if g["kind"] != "e2" or g["label"] not in REGISTERED:
            continue
        z = g["asym"]["z"]
        for rd, seed in zip(g["runs"], g["seeds"]):
            S = []
            with open(os.path.join(ROOT, rd, "sessions.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    if r["status"] != "completed" or r["origin"] != "base":
                        continue
                    a = float(r["arrival_s"])
                    if 2500.0 <= a < 7000.0:
                        S.append((a, float(r["t_end"]) - a, int(r["n_turns"])))
            S = np.array(S)
            for lo, hi in ((3, 6), (8, 12), (13, 18)):
                sel = (S[:, 2] >= lo) & (S[:, 2] <= hi)
                if sel.sum() < 15:
                    continue
                out.append(dict(label=g["label"], mult=g["rate_mult"], seed=seed, run=rd, T_lo=lo, T_hi=hi, n=int(sel.sum()),
                                slope=float(np.polyfit(S[sel, 0], S[sel, 1], 1)[0]),
                                predicted=float(np.mean(z ** S[sel, 2] - 1.0))))
    return out


def main() -> int:
    out = dict(premium=premium_scan(), premium_certificate=premium_certificate(), kendall=kendall_numbers(),
               data=data_summaries(os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")),
               fluid=fluid_checks(), self_similarity=self_similarity(os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")))
    path = os.path.join(ROOT, "results", "theory", "icml", "support.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps(out["data"]["summary"], indent=1, default=float))
    print(json.dumps(out["fluid"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
