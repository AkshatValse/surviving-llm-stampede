"""Recompute claim (1): f = fraction of active sessions in service = 1 - nu*zbar'/n on the queue-free branch,
from the frozen model outputs (and from the measured curves), and Lu et al.'s Eq. 2 read with C = D_KV = M."""
import json, os
import numpy as np
import pandas as pd
REPO = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research\.claude\worktrees\reframe-draft-211a57"
cells = {
 'A100 150k': ('results/theory/merged/a100_pool150k.json', 'pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112201/mu_curve.csv', 'sglang-fcfs-r1-p150k'),
 'A100 300k': ('results/theory/merged/a100_300k.json', 'stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv', 'sglang-fcfs-r1'),
 'A100 600k': ('results/theory/merged/a100_pool600k.json', 'pool_sweep_1716886x_pulled_20261031-112342/results/agentload_analysis_closed/20261031-112200/mu_curve.csv', 'sglang-fcfs-r1-p600k'),
 'A100 native': ('results/theory/merged/a100_native.json', 'r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv', 'sglang-fcfs-r1-native'),
 'H200 300k': ('results/theory/merged/h200_300k.json', 'h200_stageC_extra_1716961x_pulled_20261031-040933/results/agentload_analysis_closed_supp12/20261031-040909/mu_curve.csv', 'sglang-fcfs-r1-h200'),
 'H200 600k': ('results/theory/pred2/h200_600k.json', 'h200p600k_stageC_e0b_171696xx_pulled_20261031-092822/results/agentload_analysis_closed/20261031-092435/mu_curve.csv', 'sglang-fcfs-r1-h200-p600k'),
 'vLLM 300k': ('results/theory/merged/vllm_300k.json', 'stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv', 'vllm-fcfs'),
 'Llama 300k': ('results/theory/merged/llama31_8b_300k.json', 'llama31_e0b_registration_pulled_20261031-075313/results/agentload_analysis_closed/20261031-074803/mu_curve.csv', 'sglang-fcfs-r1-llama31'),
}
print('%-12s %6s %7s %7s | %6s %6s %6s | %6s %6s | %6s %6s %6s | %s' % ('cell', 'E[T]', "zbar'", 'n*', 'f_fl', 'f_F1', 'f_nh', 'f_nb', 'Kr/M*', 'f_meas', 'n_meas', 'hit*', 'Eq2 flags (f<0.5 / f<1/1.9)'))
for k, (js, mc, lab) in cells.items():
    d = json.load(open(os.path.join(REPO, js)))
    am = d['all_miss']; th = am['threshold']
    ET = am['nu_b'] / th['mu_b']
    zp = th['tool_call_part'] / am['nu_b']
    fl = d['closed_curve']['fluid']; an = d['closed_curve']['annealed']
    f_fl = 1 - fl['mu_max'] * ET * zp / fl['peak_n']
    f_an = 1 - an['mu_max'] * ET * zp / an['peak_n']
    # f at the fluid 0.5-hit crossing (interpolate on the model's curve)
    c = d['closed_curve']['curve']
    n = np.array(c['n']); mu = np.array(c['mu_fluid'])
    nh = fl['n_half']
    mu_nh = float(np.interp(nh, n, mu))
    f_nh = 1 - mu_nh * ET * zp / nh
    f_nb = th['pool_part'] / am['n_b']   # at n_b: running sessions M/E_S over n_b (K_run = M)
    # running KV share at the peak: f * n * E_S / M approx (diagnostic only)
    M = d['all_miss']['threshold']['pool_part'] * th['E_S']
    kr = f_fl * fl['peak_n'] * th['E_S'] / M
    # measured f at the measured peak (turns-based mu, the estimator of nu/E[T])
    m = pd.read_csv(os.path.join(REPO, 'results', 'nova', mc)); m = m[m.label == lab]
    i = m.mu_turns_based.idxmax()
    f_meas = 1 - m.loc[i, 'mu_turns_based'] * ET * zp / m.loc[i, 'n']
    flags = ('Y' if f_fl < 0.5 else 'n', 'Y' if f_fl < 1 / 1.9 else 'n')
    print('%-12s %6.2f %7.3f %7.2f | %6.3f %6.3f %6.3f | %6.3f %6.3f | %6.3f %6.0f %6.3f | %s' % (
        k, ET, zp, fl['peak_n'], f_fl, f_an, f_nh, f_nb, kr, f_meas, m.loc[i, 'n'], fl['hit_at_peak'], flags))
print('1/1.9 = %.4f' % (1 / 1.9))
