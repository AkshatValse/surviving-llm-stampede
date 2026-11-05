"""Recompute claim (2): measured 0.5-hit crossings, Lu et al. readings, our frozen n_half, M/E_S, MAEs.
Reads only committed files in the repository (read-only)."""
import json, os, csv
import numpy as np
REPO = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research\.claude\worktrees\reframe-draft-211a57"
N = os.path.join(REPO, 'results', 'nova')
HERE = os.path.dirname(os.path.abspath(__file__))
cells = {
 # name: (pool M, mu_curve path, label, frozen json)
 'A100 150k': (150000, 'pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112201/mu_curve.csv', 'sglang-fcfs-r1-p150k', 'results/theory/merged/a100_pool150k.json'),
 'A100 300k': (300000, 'stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv', 'sglang-fcfs-r1', 'results/theory/merged/a100_300k.json'),
 'A100 600k': (600000, 'pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112200/mu_curve.csv', 'sglang-fcfs-r1-p600k', 'results/theory/merged/a100_pool600k.json'),
 'A100 native': (955757, 'r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv', 'sglang-fcfs-r1-native', 'results/theory/merged/a100_native.json'),
 'H200 300k': (300000, 'h200_stageC_extra_1716961x_pulled_20261031-040933/results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.csv', 'sglang-fcfs-r1-h200', 'results/theory/merged/h200_300k.json'),
 'H200 600k': (600000, 'h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/results/agentload_analysis_closed/20261031-092435/mu_curve.csv', 'sglang-fcfs-r1-h200-p600k', 'results/theory/pred2/h200_600k.json'),
 'vLLM 300k': (300000, 'stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv', 'vllm-fcfs', 'results/theory/merged/vllm_300k.json'),
 'Llama 300k': (300000, 'llama31_e0b_registration_pulled_20261031-075313/results/agentload_analysis_closed/20261031-074803/mu_curve.csv', 'sglang-fcfs-r1-llama31', 'results/theory/merged/llama31_8b_300k.json'),
}


def crossing(path, label, col='hit_frac_turns', level=0.5):
    rows = [r for r in csv.DictReader(open(os.path.join(N, path))) if r['label'] == label]
    pts = sorted((float(r['n']), float(r[col])) for r in rows)
    for (n0, h0), (n1, h1) in zip(pts, pts[1:]):
        if h0 >= level > h1:
            return n0 + (n1 - n0) * (h0 - level) / (h0 - h1), (n0, round(h0, 4), n1, round(h1, 4))
    return None, None


out = {}
for k, (M, p, lab, js) in cells.items():
    d = json.load(open(os.path.join(REPO, js)))
    th = d['all_miss']['threshold']
    meas, br = crossing(p, lab)
    meas_tok, _ = crossing(p, lab, col='cached_frac_tokens')
    out[k] = dict(M=M, Ebar=th['E_bar'], meas=meas, bracket=br, meas_tok=meas_tok,
                  ours=d['closed_curve']['fluid']['n_half'], ours_f1=d['closed_curve']['annealed']['n_half'],
                  nb=d['all_miss']['n_b'], pool=th['pool_part'], tool=th['tool_call_part'], E_S=th['E_S'])

Ebar = out['A100 300k']['Ebar']
kappa = out['A100 300k']['meas'] * Ebar / 300000.0   # W/C at the A100 300k crossing
print('Ebar = %.3f; kappa (W/C at A100 300k crossing) = %.5f' % (Ebar, kappa))
print('%-12s %8s %8s %8s %8s %8s %8s %8s %8s %8s' % ('cell', 'meas', 'Lu1.9', 'Lufit', 'ours', 'oursF1', 'M/E_S', 'n_b', 'W/C@meas', 'meas_tok'))
for k, v in out.items():
    v['lu19'] = 1.9 * v['M'] / Ebar
    v['lufit'] = kappa * v['M'] / Ebar
    print('%-12s %8.3f %8.2f %8.3f %8.3f %8.3f %8.3f %8.3f %8.4f %8.3f  bracket=%s' % (
        k, v['meas'], v['lu19'], v['lufit'], v['ours'], v['ours_f1'], v['pool'], v['nb'], v['meas'] * Ebar / v['M'], v['meas_tok'], v['bracket']))


def mae(keys, f):
    e = [abs(out[k][f] - out[k]['meas']) for k in keys]
    return float(np.mean(e)), e


seven = [k for k in out if k != 'A100 300k']
blind5 = ['A100 150k', 'A100 600k', 'H200 300k', 'H200 600k', 'Llama 300k']
for name, keys in [('7 cells (all but A100 300k)', seven), ('5 blind cells', blind5), ('all 8', list(out))]:
    for f in ['lufit', 'ours', 'ours_f1', 'pool', 'lu19']:
        m, e = mae(keys, f)
        print('MAE %-28s %-8s %.3f   %s' % (name, f, m, ' '.join('%.2f' % x for x in e)))
print('signed errors (pred - meas):')
for k, v in out.items():
    print('  %-12s Lufit %+6.2f  ours %+6.2f  oursF1 %+6.2f  M/E_S %+6.2f  Lu1.9 %+6.2f' % (
        k, v['lufit'] - v['meas'], v['ours'] - v['meas'], v['ours_f1'] - v['meas'], v['pool'] - v['meas'], v['lu19'] - v['meas']))

# more charitable proportional readings of h(W/C): kappa fitted by least squares
for name, keys in [('LS kappa on all 8', list(out)), ('LS kappa on 7 (excl 300k)', seven),
                   ('LS kappa on A100 Qwen SGLang 4', ['A100 150k', 'A100 300k', 'A100 600k', 'A100 native'])]:
    x = np.array([out[k]['M'] / Ebar for k in keys]); y = np.array([out[k]['meas'] for k in keys])
    kap = float((x * y).sum() / (x * x).sum())
    e7 = [abs(kap * out[k]['M'] / Ebar - out[k]['meas']) for k in seven]
    e5 = [abs(kap * out[k]['M'] / Ebar - out[k]['meas']) for k in blind5]
    e8 = [abs(kap * out[k]['M'] / Ebar - out[k]['meas']) for k in out]
    print('%-32s kappa=%.4f  MAE7=%.2f MAE5=%.2f MAE8=%.2f' % (name, kap, np.mean(e7), np.mean(e5), np.mean(e8)))
loo = []
for k in out:
    keys = [j for j in out if j != k]
    x = np.array([out[j]['M'] / Ebar for j in keys]); y = np.array([out[j]['meas'] for j in keys])
    kap = float((x * y).sum() / (x * x).sum())
    loo.append(abs(kap * out[k]['M'] / Ebar - out[k]['meas']))
print('LOO proportional model MAE over 8 = %.2f' % np.mean(loo), ' '.join('%.2f' % v for v in loo))
print('ours MAE over 8 = %.2f' % mae(list(out), 'ours')[0])
print('H200 shifts: meas 300k %+.3f 600k %+.3f ; ours %+.3f %+.3f ; n_b %+.3f %+.3f' % (
    out['H200 300k']['meas'] - out['A100 300k']['meas'], out['H200 600k']['meas'] - out['A100 600k']['meas'],
    out['H200 300k']['ours'] - out['A100 300k']['ours'], out['H200 600k']['ours'] - out['A100 600k']['ours'],
    out['H200 300k']['nb'] - out['A100 300k']['nb'], out['H200 600k']['nb'] - out['A100 600k']['nb']))
for name, keys in [('A100 4 pools', ['A100 150k', 'A100 300k', 'A100 600k', 'A100 native']),
                   ('A100 3 pools (no native)', ['A100 150k', 'A100 300k', 'A100 600k']),
                   ('H200 2 pools', ['H200 300k', 'H200 600k'])]:
    x = np.array([out[k]['M'] / Ebar for k in keys]); y = np.array([out[k]['meas'] for k in keys])
    b, a = np.polyfit(x, y, 1)
    yo = np.array([out[k]['ours'] for k in keys]); bo, ao = np.polyfit(x, yo, 1)
    print('affine %-26s measured: crossing = %.3f + %.4f * M/Ebar ; ours (frozen n_half): %.3f + %.4f * M/Ebar ; resid %s' % (
        name, a, b, ao, bo, np.round(y - (a + b * x), 2)))
for k, v in out.items():
    print('  %-12s tool-call part %.3f  pool part %.3f  n_b %.3f  n_b - n_half %.3f  E_S %.1f' % (k, v['tool'], v['pool'], v['nb'], v['nb'] - v['ours'], v['E_S']))
json.dump(out, open(os.path.join(HERE, 'onset_out.json'), 'w'), indent=1, default=str)
