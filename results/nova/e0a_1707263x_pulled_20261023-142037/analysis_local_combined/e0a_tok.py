import sys, glob, numpy as np, pandas as pd
root = sys.argv[1]
allrq = []
for d in sorted(glob.glob(f"{root}/agentload_e0_miss/*/")):
    rq = pd.read_csv(d + "requests.csv"); rq["run"] = d; allrq.append(rq)
rq = pd.concat(allrq); ok = rq[rq.status == "ok"]
g = ok.groupby("turn").prompt_tokens.agg(["mean", "std", "count"])
print("prompt_tokens by turn (first 8, last 3):"); print(g.head(8)); print(g.tail(3))
b = np.polyfit(ok.turn, ok.prompt_tokens, 1); print("linear fit prompt = %.1f + %.1f*(turn)  resid sd=%.1f" % (b[1], b[0], (ok.prompt_tokens - np.polyval(b, ok.turn)).std()))
# per-session total prefill tokens if all-miss: W(T) = sum_k prompt(k), prompt(k)= a + c*(k-1) empirically
a = g["mean"].iloc[0]; c = b[0]
ss = pd.concat([pd.read_csv(d + "sessions.csv") for d in sorted(glob.glob(f"{root}/agentload_e0_miss/*/"))])
T = ss.n_turns.values
print("n_turns sample: n=%d mean=%.2f max=%d" % (len(T), T.mean(), T.max()))
W_emp = (a * T + c * T * (T - 1) / 2)
print("E[W] empirical-T = %.0f tokens/session (SE %.0f)" % (W_emp.mean(), W_emp.std(ddof=1) / np.sqrt(len(T))))
# analytic: geometric on {1,2,...} with mean 15, capped at 60
p = 1 / 15.0; k = np.arange(1, 2001); pk = p * (1 - p) ** (k - 1); Tc = np.minimum(k, 60)
ET = (pk * Tc).sum(); EW = (pk * (a * Tc + c * Tc * (Tc - 1) / 2)).sum()
print("analytic geometric(mean 15) cap 60: E[T]=%.3f  E[W]=%.0f" % (ET, EW))
for C in (11243.18, 11075.7, 11342.0, 11311.8):
    print("  C_tok=%.0f -> lambda_tok = %.4f sessions/s (analytic E[W]), %.4f (empirical E[W])" % (C, C / EW, C / W_emp.mean()))
