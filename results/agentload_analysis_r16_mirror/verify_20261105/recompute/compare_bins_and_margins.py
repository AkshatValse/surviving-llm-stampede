"""Extra post-hoc checks: (1) my 300-s completion bins vs the registered mirror_bins.json (rates over lambda_ref);
(2) max relative difference of every agreeing numeric field; (3) rule margins with my slope and with the registered slope."""
import json
import sys

import numpy as np
import pandas as pd

LREF = 0.07153402100919228
mine = json.load(open(sys.argv[1], encoding='utf-8'))
bins = json.load(open(sys.argv[2], encoding='utf-8'))
reg = pd.read_csv(sys.argv[3], dtype=str, keep_default_na=False)
reg['run'] = reg['run_dir'].str.replace('/', '\\').str.split('\\').str[-1]
regd = {r['run']: r for _, r in reg.iterrows()}
bins_by_run = {k.replace('/', '\\').split('\\')[-1]: v for k, v in bins.items()}

print('(1) 300-s bins over [1200, 8700): mine (count/300/lambda_ref) vs registered mirror_bins.json')
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    rb = np.asarray(bins_by_run[r['run']], float)
    mb = np.asarray(r['bins300_count'], float) / 300.0 / LREF
    same_len = len(rb) == len(mb)
    md = float(np.max(np.abs(rb - mb) / np.maximum(np.abs(rb), 1e-300))) if same_len else None
    cnt_reg = np.rint(rb * 300.0 * LREF).astype(int)
    print('  %-18s n_bins mine %d reg %d | max rel diff %s | counts equal %s' % (
        r['run'], len(mb), len(rb), f'{md:.2e}' if md is not None else 'n/a',
        bool(same_len and np.array_equal(cnt_reg, np.asarray(r['bins300_count'])))))

print()
print('(2) max relative difference over runs, agreeing numeric fields')
pairs = [('blackout', 'blackout_rate'), ('late', 'late_rate'), ('wave', 'wave_time'), ('lambda_plan', 'lambda_plan_slope_window'),
         ('S_F', 'S_F'), ('F_wave', 'F_wave'), ('run_end_s', 'run_end_s')]
for mk, rk in pairs:
    ds = []
    for r in mine['runs']:
        a = r.get(mk)
        b = regd[r['run']][rk]
        if a is None or b == '':
            continue
        a, b = float(a), float(b)
        ds.append(0.0 if a == b else abs(a - b) / max(abs(a), abs(b)))
    print('  %-12s vs %-26s n=%d max rel diff %.3e' % (mk, rk, len(ds), max(ds)))

print()
print('(3) rule margins (burst runs): positive = rule holds with that much room')
for r in sorted([r for r in mine['runs'] if r['arm'] == 'burst'], key=lambda r: (-r['rate_mult'], r['seed'])):
    g = regd[r['run']]
    S_reg = float(g['slope'])
    sf, sqs = r['S_F'], r['S_QS_jsonlambda']
    m4_mine = abs(r['slope'] - r['S_QS']) - abs(r['slope'] - sf)
    m4_reg = abs(S_reg - sqs) - abs(S_reg - sf)
    print('  %-18s %.2fx s%d | M1 0.30-blackout %.4f (%d of max 25 completions) | M2 tol-|dw| %.1f s (|dw| %.1f, tol %.1f) | '
          'M3 0.85-late %.4f (%d vs 127.69) | M4 |S-SQS|-|S-SF| mine %.5f, reg-slope+json %.5f | CURVE needs blackout>=0.85: %.3f' % (
              r['run'], r['rate_mult'], r['seed'], 0.30 - r['blackout'], r['n_completed_blackout'],
              r['M2_tol_s'] - abs(r['wave_minus_F']), abs(r['wave_minus_F']), r['M2_tol_s'],
              0.85 - r['late'], r['n_completed_late'], m4_mine, m4_reg, r['blackout']))
