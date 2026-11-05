"""Claim (3) peak-ratio ratios; extra robustness for claim (2): token-based crossings, intercept CI. Read-only."""
import json, os
import numpy as np
import pandas as pd
from scipy import stats
REPO = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research\.claude\worktrees\reframe-draft-211a57"
N = os.path.join(REPO, 'results', 'nova')
HERE = os.path.dirname(os.path.abspath(__file__))
curves = {
 'A100 150k': ('pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112201/mu_curve.csv', 'sglang-fcfs-r1-p150k', 'results/theory/merged/a100_pool150k.json', 0.071534021),
 'A100 300k': ('stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv', 'sglang-fcfs-r1', 'results/theory/merged/a100_300k.json', 0.071534021),
 'A100 600k': ('pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112200/mu_curve.csv', 'sglang-fcfs-r1-p600k', 'results/theory/merged/a100_pool600k.json', 0.071534021),
 'A100 native': ('r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv', 'sglang-fcfs-r1-native', 'results/theory/merged/a100_native.json', None),
 'H200 300k': ('h200_stageC_extra_1716961x_pulled_20261031-040933/results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.csv', 'sglang-fcfs-r1-h200', 'results/theory/merged/h200_300k.json', 0.19388),
 'H200 600k': ('h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/results/agentload_analysis_closed/20261031-092435/mu_curve.csv', 'sglang-fcfs-r1-h200-p600k', 'results/theory/pred2/h200_600k.json', 0.19388),
}
# native lambda_ref: registered R4 rate 4.0 x lambda_ref = 0.2871896 (r4 json e2/tests lam); take from the JSON
r4 = json.load(open(os.path.join(REPO, 'results/theory/merged/r4_rescue_native.json')))
lam_nat = r4['tests']['R4']['result']['4.0']['lam'] / 4.0
r1 = json.load(open(os.path.join(REPO, 'results/theory/merged/r1_rescue_300k.json')))
lam_300 = r1['tests']['R1']['result']['1.35']['lam'] / 1.35
print('lambda_ref 300k = %.7f (from R1 lam/1.35), native = %.7f (from R4 lam/4.0)' % (lam_300, lam_nat))
res = {}
for k, (p, lab, js, lref) in curves.items():
    if lref is None:
        lref = lam_nat
    if k.startswith('A100') and k != 'A100 native':
        lref = lam_300
    m = pd.read_csv(os.path.join(N, p)); m = m[m.label == lab]
    d = json.load(open(os.path.join(REPO, js)))
    res[k] = dict(meas_turns=m.mu_turns_based.max() / lref, meas_sess=m.mu_sessions.max() / lref,
                  f1=d['window']['annealed_vs_lambda_ref'], fluid=d['window']['vs_lambda_ref'])
    print('%-12s peak ratio measured %.4f (sessions %.4f); frozen F1 %.4f, fluid %.4f' % (k, res[k]['meas_turns'], res[k]['meas_sess'], res[k]['f1'], res[k]['fluid']))
M = {'A100 150k': 150000, 'A100 300k': 300000, 'A100 600k': 600000, 'A100 native': 955757, 'H200 300k': 300000, 'H200 600k': 600000}
for a, b in [('A100 native', 'A100 300k'), ('A100 600k', 'A100 300k'), ('A100 150k', 'A100 300k'), ('H200 600k', 'H200 300k')]:
    print('%-12s / %-10s measured %.3f (sessions %.3f); ours F1 %.3f, fluid %.3f; proportional (pool ratio) %.3f' % (
        a, b, res[a]['meas_turns'] / res[b]['meas_turns'], res[a]['meas_sess'] / res[b]['meas_sess'],
        res[a]['f1'] / res[b]['f1'], res[a]['fluid'] / res[b]['fluid'], M[a] / M[b]))

# claim (2) robustness: intercept CI of the affine fit on the four A100 pools
o = json.load(open(os.path.join(HERE, 'onset_out.json')))
keys = ['A100 150k', 'A100 300k', 'A100 600k', 'A100 native']
Ebar = o['A100 300k']['Ebar']
x = np.array([o[k]['M'] / Ebar for k in keys]); y = np.array([o[k]['meas'] for k in keys])
lr = stats.linregress(x, y)
t = stats.t.ppf(0.975, len(x) - 2)
print('affine, 4 A100 pools: intercept %.3f +- %.3f (SE), 95%% CI [%.2f, %.2f]; slope %.4f +- %.4f' % (
    lr.intercept, lr.intercept_stderr, lr.intercept - t * lr.intercept_stderr, lr.intercept + t * lr.intercept_stderr, lr.slope, lr.stderr))
# proportional fit through origin vs affine: residuals
kap = (x * y).sum() / (x * x).sum()
print('through-origin kappa %.4f, residuals %s; affine residuals %s' % (kap, np.round(y - kap * x, 2), np.round(y - (lr.intercept + lr.slope * x), 2)))
# token-based crossings (cached_frac_tokens) as Lu's h is a token hit rate
kap_tok = o['A100 300k']['meas_tok'] * Ebar / 300000.0
seven = [k for k in o if k != 'A100 300k']
blind5 = ['A100 150k', 'A100 600k', 'H200 300k', 'H200 600k', 'Llama 300k']
for name, ks in [('7', seven), ('5 blind', blind5)]:
    e_lu = [abs(kap_tok * o[k]['M'] / Ebar - o[k]['meas_tok']) for k in ks]
    e_ours = [abs(o[k]['ours'] - o[k]['meas_tok']) for k in ks]
    print('token-hit crossing, %-8s: Lu-fit (kappa %.4f) MAE %.2f; ours MAE %.2f' % (name, kap_tok, np.mean(e_lu), np.mean(e_ours)))
