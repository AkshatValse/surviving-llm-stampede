"""Recompute claim (4): Lu et al. Eq. 4 drain applied to the registered rescue tests R1/R4,
against the measured releases and our frozen two-phase (and single-phase) drains. Read-only."""
import json, os, csv
import numpy as np
import pandas as pd
REPO = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research\.claude\worktrees\reframe-draft-211a57"
RP = os.path.join(REPO, 'results', 'nova', 'rescue_1716896x_pulled_20261031-070502', 'results')
r1 = pd.read_csv(os.path.join(RP, 'agentload_analysis_rescue_r1', '20261031-071720', 'rescue_runs.csv'))
r4 = pd.read_csv(os.path.join(RP, 'agentload_analysis_rescue_r4', '20261031-071748', 'rescue_runs.csv'))
runs = pd.concat([r1, r4], ignore_index=True)
runs = runs[runs.arm == 'rescue']

th1 = json.load(open(os.path.join(REPO, 'results/theory/merged/r1_rescue_300k.json')))['tests']['R1']['result']
th4 = json.load(open(os.path.join(REPO, 'results/theory/merged/r4_rescue_native.json')))['tests']['R4']['result']
theory = {1.35: th1['1.35'], 1.65: th1['1.65'], 4.0: th4['4.0']}

# measured closed-curve peaks (Stage C 300k; native grid)
sc = pd.read_csv(os.path.join(REPO, 'results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv'))
sc = sc[sc.label == 'sglang-fcfs-r1']
nat = pd.read_csv(os.path.join(REPO, 'results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv'))
peaks = {}
for key, df, cap in [('300k', sc, 20), ('native', nat, 64)]:
    peaks[key] = dict(turns_max=df.mu_turns_based.max(), sess_max=df.mu_sessions.max(),
                      turns_cap=float(df[df.n == cap].mu_turns_based.iloc[0]), sess_cap=float(df[df.n == cap].mu_sessions.iloc[0]),
                      n_argmax=int(df.loc[df.mu_turns_based.idxmax(), 'n']))
print('measured peaks', peaks)

rows = []
for _, r in runs.iterrows():
    m = float(r.rate_mult)
    th = theory[m]
    lam = th['lam']
    cell = '300k' if m < 3 else 'native'
    cap = float(r.n_cap); t_on = float(r.t_engage)
    for nkey in ['sessions_in_system_at_t_on', 'outstanding_at_t_on']:
        for dkey in ['turns_max', 'sess_max', 'turns_cap', 'sess_cap']:
            D = peaks[cell][dkey]
            S = float(r[nkey]) - cap
            t_rel = t_on + S / (D - lam) + 300.0
            rows.append(dict(cell=('R1' if m < 3 else 'R4'), mult=m, seed=int(r.seed), nkey=nkey, dkey=dkey, D=D, lam=lam, S=S,
                             lu_t_rel=t_rel, meas=float(r.t_release),
                             err_pred_vs_meas=(t_rel - float(r.t_release)) / float(r.t_release),
                             late_vs_pred=(float(r.t_release) - t_rel) / t_rel,
                             ours2=th['two_phase']['t_release'], ours1=th['stationary']['t_release']))
df = pd.DataFrame(rows)
pd.set_option('display.width', 250)
main = df[(df.nkey == 'sessions_in_system_at_t_on') & (df.dkey == 'turns_max')]
print('\nLu Eq.4, n_on = sessions in system at t_on, D = measured turns-based mu* (main reading):')
print(main[['cell', 'mult', 'seed', 'S', 'D', 'lam', 'lu_t_rel', 'meas', 'err_pred_vs_meas', 'late_vs_pred']].round(4).to_string())
print('\nRange over variants of n_on and D, per cell (Lu t_rel, error vs measured):')
for (c, m), g in df.groupby(['cell', 'mult']):
    print('  %s %.2f: Lu t_rel %.0f-%.0f s; error pred-vs-meas %+.1f%% to %+.1f%%; measured late vs Lu %+.1f%% to %+.1f%%' % (
        c, m, g.lu_t_rel.min(), g.lu_t_rel.max(), 100 * g.err_pred_vs_meas.max(), 100 * g.err_pred_vs_meas.min(),
        100 * g.late_vs_pred.min(), 100 * g.late_vs_pred.max()))
    for (nk, dk), gg in g.groupby(['nkey', 'dkey']):
        print('      %-28s %-10s mean Lu t_rel %.0f' % (nk, dk, gg.lu_t_rel.mean()))
print('\nOur frozen predictions vs measured:')
for m in [1.35, 1.65, 4.0]:
    g = main[main.mult == m]
    th = theory[m]
    for name, val in [('two-phase (frozen primary)', th['two_phase']['t_release']), ('two-phase F1', th['two_phase_annealed']['t_release']),
                      ('single-phase stationary (frozen, not primary)', th['stationary']['t_release'])]:
        e = (val - g.meas) / g.meas
        late = (g.meas - val) / val
        print('  %.2f %-46s %.0f s: pred-vs-meas %+.1f%% to %+.1f%%; measured late %+.1f%% to %+.1f%%' % (
            m, name, val, 100 * e.max(), 100 * e.min(), 100 * late.min(), 100 * late.max()))
    print('      model n_on %.1f (measured sessions in system %s), model cycle_on %.1f s, backlog_after_pause %.1f, mu_cap %.4f, phase1 %.4f for T1 %.0f s' % (
        th['n_on'], list(g.S + 20 if m < 3 else g.S + 64), th['cycle_on'], th['backlog_after_pause'], th['mu_cap_stationary'],
        th['two_phase']['phase1_rate'], th['two_phase']['T1']))
df.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drain_out.csv'), index=False)
