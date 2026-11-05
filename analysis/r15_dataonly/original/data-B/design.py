"""data-B: power/feasibility of a no-trigger survival experiment on A100 300k SGLang FCFS.
Hypotheses for the escape time from t = 0 (exponential, mean T):
  F2   : frozen merged-theory T(m) from results/theory/merged/a100_300k.json (p_escape_fine, H=3000 s)
  EMP  : T(m) = r * T_F2(m), r fitted to the four existing 2.5x runs (seeds 0,3,4,5; realized
         0-3000 s rates 2.726/2.512/2.665/2.470) by exposure MLE with 600 s warm-up
  SLOW : 3 * EMP
Also prints the exponential MLE and exact CI for the existing 2.5x (A100 300k) and 1.4x (H200 300k) data.
"""
import json, math
import numpy as np
from scipy import stats

e = json.load(open(r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\arxiv\results\theory\merged\a100_300k.json"))["from_empty_edge"]
pf = {float(k): v for k, v in e["p_escape_fine"].items()}
def TF2(m):
    ks = sorted(pf); lo = max(k for k in ks if k <= m); hi = min(k for k in ks if k >= m)
    T = lambda k: -3000 / math.log(1 - pf[k])
    if lo == hi: return T(lo)
    w = (m - lo) / (hi - lo); return math.exp((1 - w) * math.log(T(lo)) + w * math.log(T(hi)))

WARM = 600.0
def ci(exposure, events, a=0.05):
    lo = 2 * exposure / stats.chi2.ppf(1 - a / 2, 2 * events + 2) if events >= 0 else None
    hi = 2 * exposure / stats.chi2.ppf(a / 2, 2 * events) if events > 0 else math.inf
    return lo, hi

# existing data, exposure from WARM (tau - 600 or 2500 censored)
for name, exp_s, ev, extra in [("A100 300k 2.5x (4 runs)", 1000 + 3 * 2500, 1, ""),
                              ("H200 300k 1.4x (3 runs)", 1000 + 2500 + 2500, 1, ""),
                              ("H200 300k 1.3x (3 runs)", 3 * 2500, 0, ""),
                              ("A100 300k 2.0x (4 runs)", 4 * 2500, 0, "")]:
    lo, hi = ci(exp_s, ev)
    lb95 = exp_s / -math.log(0.05) if ev == 0 else None
    print(f"{name}: exposure {exp_s} s, events {ev}, T_hat {exp_s/ev if ev else math.inf:.0f}, 95% CI [{lo:.0f}, {hi:.0f}]" + (f", one-sided 95% lower bound {lb95:.0f}" if lb95 else ""))

# fit r on 2.5x runs: each run i has rate m_i, T_i = r*TF2(m_i); exponential from WARM (approx)
runs = [(2.726, 1000.0, 1), (2.512, 2500.0, 0), (2.665, 2500.0, 0), (2.470, 2500.0, 0)]
r_hat = sum(s / TF2(m) for m, s, d in runs) / sum(d for _, _, d in runs)
print("F2 T at realized rates:", [round(TF2(m)) for m, _, _ in runs], " r_hat =", round(r_hat, 2))
# P under F2 of >=3 of 4 surviving 3000 s (from t=0)
ps = [math.exp(-3000 / TF2(m)) for m, _, _ in runs]
print("F2 P(survive 3000) per run:", [round(p, 3) for p in ps], " P(seeds 3,4,5 survive & seed 0 collapses):",
      round((1 - ps[0]) * ps[1] * ps[2] * ps[3], 4), " P(>=3 of 4 survive):",
      round(sum(np.prod([ps[j] if j != i else 1 - ps[j] for j in range(4)]) for i in range(4)) + np.prod(ps), 4))

print()
print("design: mult, N, L(s): for each hypothesis T(m), P(collapse by L-600 censor), E[events], P(events>=6), median tau")
rng = np.random.default_rng(1)
for m in (2.4, 2.5, 2.6, 2.7, 2.8):
    for N, L in ((12, 8700), (18, 8700), (6, 17400), (9, 17400)):
        out = []
        for hyp, T in (("F2", TF2(m)), ("EMP", r_hat * TF2(m)), ("SLOW", 3 * r_hat * TF2(m))):
            C = L - 600.0  # last confirmable collapse time
            # realized-rate heterogeneity: per-seed multiple ~ m*(1+0.025 z) over L
            sims = []
            for _ in range(4000):
                mm = m * (1 + 0.025 * rng.standard_normal(N) * math.sqrt(8700 / L))
                Ti = np.array([(r_hat if hyp != "F2" else 1) * (3 if hyp == "SLOW" else 1) * TF2(max(1.05, min(3.45, x))) for x in mm])
                t = rng.exponential(Ti)
                sims.append(((t >= WARM) & (t <= C)).sum() + (t < WARM).sum())
            sims = np.array(sims)
            p1 = 1 - math.exp(-C / T)
            out.append(f"{hyp}: T={T:6.0f} p={p1:.2f} E={sims.mean():4.1f} P6={np.mean(sims>=6):.2f}")
        print(f"  {m:.2f}x N={N:2d} L={L:5d} | " + " | ".join(out))
