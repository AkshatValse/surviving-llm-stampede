"""Post-hoc probe (after the blind recompute): which backlog definition reproduces the registered slope?
Also checks the alternative hit-metric readings and the S_QS constant against the registered values.
Own code only; does not read any analysis/*.py."""
import json
import os
import sys

import numpy as np
import pandas as pd

mine = json.load(open(sys.argv[1], encoding='utf-8'))
reg = pd.read_csv(sys.argv[2], dtype=str, keep_default_na=False)
reg['run'] = reg['run_dir'].str.replace('/', '\\').str.split('\\').str[-1]
regd = {r['run']: r for _, r in reg.iterrows()}
LAMBDA_MISS_JSON = mine['constants']['lambda_miss_json']


def rel(a, b):
    return 0.0 if a == b else abs(a - b) / max(abs(a), abs(b))


def ols(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    xm, ym = x.mean(), y.mean()
    return float(np.sum((x - xm) * (y - ym)) / np.sum((x - xm) ** 2))


def count_alive(start, end, t):
    return ((start[:, None] <= t[None, :]) & (end[:, None] > t[None, :])).sum(axis=0).astype(float)


def slope_from_samples(t, n, step):
    """bin samples into 10-s bins by floor(t/10); OLS of bin means on bin centres for bins with start in [6000, 8700)."""
    k = np.floor(t / 10.0 + 1e-12).astype(int)
    df = pd.DataFrame({'k': k, 'n': n})
    g = df.groupby('k')['n'].mean()
    starts = g.index.to_numpy() * 10.0
    sel = (starts >= 6000) & (starts < 8700)
    return ols(starts[sel] + 5.0, g.to_numpy()[sel]), int(sel.sum())


def exact_bin_means(start, end, edges):
    """time-average of the step function N(t) over each bin [e_i, e_{i+1})."""
    lo = edges[:-1][None, :]
    hi = edges[1:][None, :]
    ov = np.clip(np.minimum(end[:, None], hi) - np.maximum(start[:, None], lo), 0, None)
    return ov.sum(axis=0) / (edges[1:] - edges[:-1])


results = {}
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    rd = r['run_dir']
    sess = pd.read_csv(os.path.join(rd, 'sessions.csv'))
    req = pd.read_csv(os.path.join(rd, 'requests.csv'), low_memory=False)
    g = regd[r['run']]
    target = float(g['slope'])
    run_end = float(r['run_end_s'])
    arr = sess['arrival_s'].to_numpy(float)
    ended = sess['status'].isin(['completed', 'failed']).to_numpy()
    tend = sess['t_end'].to_numpy(float)
    end_runend = np.where(ended, tend, run_end)
    end_raw = tend  # every session's own t_end (cancelled at ~8700.06)
    variants = {}
    t1 = np.arange(0, 8700, dtype=float)
    variants['V0 mine: int t in [0,8700), arrival, end=t_end|run_end'] = slope_from_samples(t1, count_alive(arr, end_runend, t1), 1)
    t_half = t1 + 0.5
    variants['V2 samples at t+0.5'] = slope_from_samples(t_half, count_alive(arr, end_runend, t_half), 1)
    t_1to = np.arange(1, 8701, dtype=float)
    n_1to = count_alive(arr, end_runend, t_1to)
    # bins (10k, 10k+10]: samples 10k+1..10k+10 -> assign to bin k
    k = ((t_1to - 1) // 10).astype(int)
    gm = pd.Series(n_1to).groupby(k).mean()
    st = gm.index.to_numpy() * 10.0
    sel = (st >= 6000) & (st < 8700)
    variants['V5 samples 10k+1..10k+10'] = (ols(st[sel] + 5, gm.to_numpy()[sel]), int(sel.sum()))
    edges = np.arange(0, 8701, 10, dtype=float)
    em = exact_bin_means(arr, end_runend, edges)
    st = edges[:-1]
    sel = (st >= 6000) & (st < 8700)
    variants['V1 exact time-average per 10-s bin'] = (ols(st[sel] + 5, em[sel]), int(sel.sum()))
    for col in ('t_first_send', 't_admit'):
        s2 = sess[col].to_numpy(float)
        variants[f'V3 start={col}'] = slope_from_samples(t1, count_alive(s2, end_runend, t1), 1)
        em2 = exact_bin_means(s2, end_runend, edges)
        variants[f'V3e start={col}, exact bin mean'] = (ols(st[sel] + 5, em2[sel]), int(sel.sum()))
    # end = last ok request completion for completed sessions
    ok = req[req['status'] == 'ok']
    last_ok = ok.groupby('sid')['t_complete'].max()
    end_lastreq = np.array([last_ok.get(s, np.nan) if e else run_end for s, e in zip(sess['sid'], ended)], float)
    variants['V6 end=last ok t_complete (completed)'] = slope_from_samples(t1, count_alive(arr, end_lastreq, t1), 1)
    # sample grid 0..8700 inclusive with 5-s / 1-s offsets
    for off in (0.25, 0.75, 1.0):
        tt = t1 + off
        variants[f'V2b samples at t+{off}'] = slope_from_samples(tt, count_alive(arr, end_runend, tt), 1)
    # finer sampling 0.1 s
    t01 = np.arange(0, 87000, dtype=float) / 10.0
    variants['V7 samples every 0.1 s'] = slope_from_samples(t01, count_alive(arr, end_runend, t01), 1)
    results[r['run']] = (target, variants)
    print('==', r['run'], r['arm'], r['rate_mult'], r['seed'], 'registered slope %.17g' % target)
    for name, (s, nb) in variants.items():
        print('    %-50s %.17g  nbins %d  rel %.3e' % (name, s, nb, rel(s, target)))

print()
print('hit metric readings vs registered hit_eval ([5700, 8700]):')
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    g = regd[r['run']]
    he = float(g['hit_eval'])
    h = r['hit']['5700_8700']
    h45 = r['hit']['4500_8700']
    print('  %-18s reg %.17g | gt0 %.17g (rel %.2e) | gt50tok %.17g (rel %.2e) | frac>0.5 %.17g (rel %.2e) | gt50tok@4500 %.6g' % (
        r['run'], he, h['frac_turns_cached_gt0'], rel(h['frac_turns_cached_gt0'], he), h['frac_turns_cached_gt50tok'],
        rel(h['frac_turns_cached_gt50tok'], he), h['frac_turns_cachedfrac_gt0p5'], rel(h['frac_turns_cachedfrac_gt0p5'], he),
        h45['frac_turns_cached_gt50tok']))

print()
print('S_QS with the JSON lambda_miss_model (%.17g) vs registered:' % LAMBDA_MISS_JSON)
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    if r['arm'] != 'burst':
        continue
    g = regd[r['run']]
    print('  %-18s mine(json) %.17g reg %.17g rel %.2e | mine(brief) %.17g' % (
        r['run'], r['S_QS_jsonlambda'], float(g['S_QS']), rel(r['S_QS_jsonlambda'], float(g['S_QS'])), r['S_QS']))
