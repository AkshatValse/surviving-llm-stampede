"""Extra post-hoc checks outside the brief (secondary W items from the tagged note's prose; basin backlog_slope column)."""
import json
import os
import sys

import numpy as np
import pandas as pd

mine = json.load(open(sys.argv[1], encoding='utf-8'))
reg = pd.read_csv(sys.argv[2], dtype=str, keep_default_na=False)
pred = json.load(open(sys.argv[3], encoding='utf-8'))
calib = json.load(open(sys.argv[4], encoding='utf-8'))
verdict = json.load(open(sys.argv[5], encoding='utf-8'))
LREF = 0.07153402100919228
reg['run'] = reg['run_dir'].str.replace('/', '\\').str.split('\\').str[-1]
regd = {r['run']: r for _, r in reg.iterrows()}


def ols(x, y):
    xm, ym = x.mean(), y.mean()
    return float(np.sum((x - xm) * (y - ym)) / np.sum((x - xm) ** 2))


def exact_bin_slope(sess, run_end, lo, hi):
    arr = sess['arrival_s'].to_numpy(float)
    ended = sess['status'].isin(['completed', 'failed']).to_numpy()
    end = np.where(ended, sess['t_end'].to_numpy(float), run_end)
    edges = np.arange(0, 8701, 10, dtype=float)
    ov = np.clip(np.minimum(end[:, None], edges[1:][None, :]) - np.maximum(arr[:, None], edges[:-1][None, :]), 0, None)
    means = ov.sum(axis=0) / 10.0
    st = edges[:-1]
    sel = (st >= lo) & (st < hi)
    return ols(st[sel] + 5.0, means[sel]), int(sel.sum())


print('basin backlog_slope column vs exact-bin-average slope over [5700, 8700) (and [4500, 8700)):')
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    sess = pd.read_csv(os.path.join(r['run_dir'], 'sessions.csv'))
    s57, n57 = exact_bin_slope(sess, float(r['run_end_s']), 5700, 8700)
    s45, n45 = exact_bin_slope(sess, float(r['run_end_s']), 4500, 8700)
    b = float(regd[r['run']]['backlog_slope'])
    thr = float(regd[r['run']]['slope_threshold'])
    print('  %-18s reg %.17g | exact[5700,8700) %.17g rel %.2e | exact[4500,8700) %.6g | thr reg %.12g, 0.5*(mult-1)*lref %.12g' % (
        r['run'], b, s57, abs(s57 - b) / abs(b), s45, thr, 0.5 * (r['rate_mult'] - 1) * LREF))

print()
print('W5 (calibrated wave, +-5%), W8 (|late - F_late| <= 0.25), W6 (wave earlier at 1.35x than 1.65x), W10 (late < E0a capacity):')
lam_e0a = None
for k in ('lambda_miss_turns_based', 'lambda_miss'):
    if k in calib:
        lam_e0a = float(calib[k])
        print('  E0a calibration %s = %.17g (= %.6f lambda_ref); registered W10 lambda_miss_measured = %.17g' % (
            k, lam_e0a, lam_e0a / LREF, verdict['W10_capacity']['lambda_miss_measured']))
        break
waves = {}
for r in sorted([r for r in mine['runs'] if r['arm'] == 'burst'], key=lambda r: (-r['rate_mult'], r['seed'])):
    fs = pred['cells'][f"{r['rate_mult']:.2f}"]['seeds'][str(r['seed'])]
    fcal = float(fs['burst_timing']['median_calibrated'])
    flate = float(fs['windows']['late']['completion_over_lam_ref'])
    w5 = abs(r['wave'] - fcal) <= 0.05 * (fcal - 1200.0)
    w8 = abs(r['late'] - flate) <= 0.25
    w10 = (lam_e0a is not None) and (r['late'] < lam_e0a / LREF)
    g = regd[r['run']]
    waves[(r['rate_mult'], r['seed'])] = r['wave']
    print('  %-18s %.2fx s%d | F_cal %.3f |w-Fcal| %.1f tol %.1f W5 %s (reg %s) | F_late %.4f late %.4f W8 %s (reg %s) | W10 late<E0a %s' % (
        r['run'], r['rate_mult'], r['seed'], fcal, abs(r['wave'] - fcal), 0.05 * (fcal - 1200), w5, g['W5_calibrated_wave'],
        flate, r['late'], w8, g['W8_late_level'], w10))
for s in (0, 1, 2):
    print('  W6 seed %d: wave 1.35x %.1f < 1.65x %.1f: %s (reg %s)' % (
        s, waves[(1.35, s)], waves[(1.65, s)], waves[(1.35, s)] < waves[(1.65, s)], verdict['W6_order'][str(s)]))
