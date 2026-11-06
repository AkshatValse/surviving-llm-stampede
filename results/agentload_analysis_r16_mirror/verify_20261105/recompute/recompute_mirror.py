#!/usr/bin/env python
"""Independent recompute of the r16 MIRROR measures, written from recompute_brief.md only.

Does NOT import or read analysis/r16_mirror.py, analysis/r15_cut.py, analysis/basin.py, analysis/trap_v2.py,
analysis/throughput.py or analysis/theory/icml/measured.py, and does not read the registered scorer's output.
Inputs: the run directories (sessions.csv, requests.csv, plan.csv, meta.json, config_effective.yaml), the frozen
predictions JSON (extracted from tag r16-mirror-reg) and the frozen plans directory (for an extra plan-equality check).

Usage:
  python -I recompute_mirror.py --pred mirror_predictions_tag.json --plans-dir <worktree>/results/theory/r16/mirror_plans \
      --out-dir <scratch> RUN_DIR [RUN_DIR ...]
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
import yaml

LAMBDA_REF = 0.07153402100919228          # sessions/s (brief)
LAMBDA_MISS_BRIEF = 0.07483084            # /s, "the model all-miss capacity" as written in the brief
BLACKOUT = (2400.0, 3600.0)               # [a, b)
LATE = (6600.0, 8700.0)                   # [a, b)
SLOPE_WIN = (6000.0, 8700.0)              # bins over [6000, 8700)
T_RUN = 8700                              # backlog sampled at integer t in [0, 8700)
HIT_WINDOWS = ((4500.0, 8700.0), (5700.0, 8700.0))   # closed windows on t_complete, per the brief
STUCK_THR = 0.2
BIN300_LO, BIN300_HI, BIN300_W = 1200.0, 8700.0, 300.0
WAVE_MIN_N = 100
T_BURST = 1200.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def completion_count(sess, a, b):
    m = (sess['status'] == 'completed') & (sess['t_end'] >= a) & (sess['t_end'] < b)
    return int(m.sum())


def completion_rate(sess, a, b):
    n = completion_count(sess, a, b)
    return n, n / (b - a) / LAMBDA_REF


def wave_time(sess):
    m = (sess['origin'] == 'burst') & (sess['status'] == 'completed') & (sess['t_end'] <= 8700.0)
    x = np.sort(sess.loc[m, 't_end'].to_numpy(dtype=float))
    n = int(len(x))
    if n < WAVE_MIN_N:
        return None, n, None, None
    med = float(np.median(x))
    lo = float(x[(n - 1) // 2])      # lower median (alternative reading)
    hi = float(x[n // 2])            # upper median (alternative reading)
    return med, n, lo, hi


def backlog_series(sess, run_end):
    """N(t) at integer t in [0, T_RUN): arrived (arrival_s <= t) and not ended (end > t).
    end = t_end for completed/failed, otherwise the run end."""
    arr = sess['arrival_s'].to_numpy(dtype=float)
    ended = sess['status'].isin(['completed', 'failed']).to_numpy()
    end = np.where(ended, sess['t_end'].to_numpy(dtype=float), float(run_end))
    t = np.arange(0, T_RUN, dtype=float)
    # direct broadcast count (sessions x times)
    alive = (arr[:, None] <= t[None, :]) & (end[:, None] > t[None, :])
    n_direct = alive.sum(axis=0).astype(float)
    # cross-check via sorted counts (valid because end >= arr for every session)
    assert np.all(end >= arr), 'a session ends before it arrives'
    n_sorted = (np.searchsorted(np.sort(arr), t, side='right') - np.searchsorted(np.sort(end), t, side='right')).astype(float)
    assert np.array_equal(n_direct, n_sorted), 'backlog cross-check failed'
    return t, n_direct


def ols_slope(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xm, ym = x.mean(), y.mean()
    s = float(np.sum((x - xm) * (y - ym)) / np.sum((x - xm) ** 2))
    s_pf = float(np.polyfit(x, y, 1)[0])
    assert abs(s - s_pf) <= 1e-9 * max(1.0, abs(s)), (s, s_pf)
    return s


def backlog_slope(sess, run_end):
    t, n = backlog_series(sess, run_end)
    nb = T_RUN // 10
    means = n.reshape(nb, 10).mean(axis=1)
    starts = np.arange(nb) * 10.0
    centres = starts + 5.0
    sel = (starts >= SLOPE_WIN[0]) & (starts < SLOPE_WIN[1])
    slope = ols_slope(centres[sel], means[sel])
    # alternative x = mean of the integer sample times (start + 4.5): identical slope in exact arithmetic
    slope_alt = ols_slope(starts[sel] + 4.5, means[sel])
    return {
        'slope': slope,
        'slope_alt_centre_4p5': slope_alt,
        'n_bins': int(sel.sum()),
        'N_bin_first': float(means[sel][0]),
        'N_bin_last': float(means[sel][-1]),
        'N_at_6000': float(n[6000]),
        'N_at_8699': float(n[8699]),
        'N_max': float(n.max()),
    }


def lambda_plan(plan):
    m = (plan['origin'] == 'base') & (plan['arrival_s'] >= SLOPE_WIN[0]) & (plan['arrival_s'] < SLOPE_WIN[1])
    return int(m.sum()), int(m.sum()) / (SLOPE_WIN[1] - SLOPE_WIN[0])


def hit_fractions(req):
    ok = req[req['status'] == 'ok'].copy()
    ok['cached_tokens'] = pd.to_numeric(ok['cached_tokens'], errors='raise').astype(float)
    ok['prompt_tokens'] = pd.to_numeric(ok['prompt_tokens'], errors='raise').astype(float)
    out = {}
    for a, b in HIT_WINDOWS:
        w = ok[(ok['t_complete'] >= a) & (ok['t_complete'] <= b)]
        key = f'{int(a)}_{int(b)}'
        c = w['cached_tokens'].to_numpy()
        p = w['prompt_tokens'].to_numpy()
        pc = pd.to_numeric(w['prompt_tokens_client'], errors='coerce').to_numpy(dtype=float)
        out[key] = {
            'n_turns': int(len(w)),
            'frac_turns_cached_gt0': float(np.mean(c > 0)) if len(w) else None,
            'token_hit_rate': float(c.sum() / p.sum()) if len(w) else None,
            # alternative readings of the config name `frac_turns_cached_gt50`
            'frac_turns_cached_gt50tok': float(np.mean(c > 50)) if len(w) else None,
            'frac_turns_cachedfrac_gt0p5': float(np.mean(c / p > 0.5)) if len(w) else None,
            'token_hit_rate_client_prompt': float(c.sum() / pc.sum()) if len(w) else None,
            'n_prompt_server_ne_client': int(np.sum(p != pc)),
            'n_cached_in_1_to_50': int(np.sum((c > 0) & (c <= 50))),
            'n_cached_gt0_but_frac_le_0p5': int(np.sum((c > 0) & (c / p <= 0.5))),
        }
    return out


def identify(run_dir):
    meta = json.load(open(os.path.join(run_dir, 'meta.json'), encoding='utf-8'))
    cfg = yaml.safe_load(open(os.path.join(run_dir, 'config_effective.yaml'), encoding='utf-8'))
    plan = pd.read_csv(os.path.join(run_dir, 'plan.csv'))
    argv = meta.get('argv', [])
    sets = {}
    for i in range(len(argv) - 1):
        if argv[i] == '--set':
            k, _, v = argv[i + 1].partition('=')
            sets[k] = v.strip('"')
    argv_seed = [argv[i + 1] for i in range(len(argv) - 1) if argv[i] == '--seed']
    arm_meta = meta.get('arm')
    arm_cfg = cfg.get('meta', {}).get('arm')
    has_burst_cfg = cfg.get('arrivals', {}).get('burst') is not None
    n_burst_plan = int((plan['origin'] == 'burst').sum())
    arm_from_plan = 'burst' if n_burst_plan > 0 else 'noburst'
    arm_from_cfg_burst = 'burst' if has_burst_cfg else 'noburst'
    arms = {arm_meta, arm_cfg, arm_from_plan, arm_from_cfg_burst}
    rate_cfg = float(cfg['arrivals']['rate_mult'])
    rate_argv = float(sets['arrivals.rate_mult']) if 'arrivals.rate_mult' in sets else None
    rate_resolved = meta.get('resolved_rate_sessions_per_s')
    seed_cfg = int(cfg['run']['seed'])
    seeds_meta = meta.get('seeds')
    ident = {
        'arm': arm_cfg,
        'arm_sources': {'meta.arm': arm_meta, 'config.meta.arm': arm_cfg, 'plan.csv has burst': arm_from_plan,
                        'config.arrivals.burst': arm_from_cfg_burst},
        'arm_consistent': len(arms) == 1,
        'rate_mult': rate_cfg,
        'rate_sources': {'config.arrivals.rate_mult': rate_cfg, 'argv --set': rate_argv,
                         'meta.resolved_rate/lambda_ref': (rate_resolved / LAMBDA_REF) if rate_resolved else None},
        'rate_consistent': (rate_argv is None or abs(rate_argv - rate_cfg) < 1e-12)
                           and (rate_resolved is None or abs(rate_resolved / LAMBDA_REF - rate_cfg) < 1e-9),
        'seed': seed_cfg,
        'seed_sources': {'config.run.seed': seed_cfg, 'meta.seeds': seeds_meta, 'argv --seed': argv_seed},
        'seed_consistent': (seeds_meta == [seed_cfg]) and (argv_seed == [str(seed_cfg)]),
        'engine_label': meta.get('engine_label'),
        'job_id': meta.get('slurm_env', {}).get('SLURM_JOB_ID'),
        'job_name': meta.get('slurm_env', {}).get('SLURM_JOB_NAME'),
        'status': meta.get('status'),
        'run_end_s': meta.get('outcome', {}).get('t_end_s'),
        'abort_reason': meta.get('outcome', {}).get('abort_reason'),
        'git_commit': meta.get('git', {}).get('commit'),
        'git_dirty': meta.get('git', {}).get('dirty'),
        'prereg_sha256': meta.get('prereg_sha256'),
        'lambda_ref_resolved': meta.get('lambda_ref_resolved'),
        'workload_turns': (cfg['workload'].get('mean_turns'), cfg['workload'].get('max_turns')),
        'duration_s': cfg['run'].get('duration_s'),
    }
    return ident, meta, plan


def plan_vs_frozen(plan, plans_dir, arm, mult, seed):
    path = os.path.join(plans_dir, f'{arm}_{mult:.2f}_seed{seed}.csv')
    if not os.path.exists(path):
        return {'frozen_plan': path, 'exists': False}
    fz = pd.read_csv(path)
    res = {'frozen_plan': os.path.basename(path), 'exists': True, 'n_run': len(plan), 'n_frozen': len(fz)}
    if len(fz) != len(plan) or list(fz.columns) != list(plan.columns):
        res['equal'] = False
        return res
    exact_cols = ['sid', 'origin', 'idx', 'n_turns']
    res['exact_cols_equal'] = bool(all((fz[c].astype(str).values == plan[c].astype(str).values).all() for c in exact_cols))
    dev = {}
    for c in ['arrival_s', 'tool_time_total_s']:
        a = fz[c].to_numpy(dtype=float)
        b = plan[c].to_numpy(dtype=float)
        dev[c] = {'max_abs_diff': float(np.max(np.abs(a - b))),
                  'max_rel_diff': float(np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-300))),
                  'n_bitwise_diff': int(np.sum(a != b))}
    res['float_cols'] = dev
    res['equal_within_1e-12_rel'] = bool(res['exact_cols_equal'] and all(v['max_rel_diff'] <= 1e-12 for v in dev.values()))
    return res


def seed_call(stuck, m1, m2, m3, m4, blackout, late):
    if stuck and m1 and m2 and m3 and m4:
        return 'RENEWAL'
    if blackout >= 0.85 and late >= 0.85:
        return 'CURVE'
    if not stuck:
        return 'NOT-TRAPPED'
    return 'MIXED'


def cell_verdict(calls):
    n = len(calls)
    if sum(c == 'RENEWAL' for c in calls) >= 2:
        return 'PASS'
    if sum(c == 'CURVE' for c in calls) >= 2:
        return 'FAIL'
    if sum(c == 'NOT-TRAPPED' for c in calls) >= 2:
        return 'NO-TRAP'
    return 'MIXED'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', required=True)
    ap.add_argument('--plans-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('run_dirs', nargs='+')
    args = ap.parse_args()
    pred = json.load(open(args.pred, encoding='utf-8'))
    lambda_miss_json = float(pred['lambda_miss_model'])

    runs = []
    for rd in args.run_dirs:
        ident, meta, plan = identify(rd)
        sess = pd.read_csv(os.path.join(rd, 'sessions.csv'))
        req = pd.read_csv(os.path.join(rd, 'requests.csv'), low_memory=False)
        arm, mult, seed = ident['arm'], ident['rate_mult'], ident['seed']
        mkey = f'{mult:.2f}'
        rec = {'run': os.path.basename(os.path.normpath(rd)), 'run_dir': rd, **ident}
        rec['inputs_sha256'] = {f: sha256(os.path.join(rd, f)) for f in
                                ('sessions.csv', 'requests.csv', 'plan.csv', 'meta.json', 'config_effective.yaml')}
        rec['n_sessions'] = int(len(sess))
        rec['session_status_counts'] = {f'{o}/{s}': int(v) for (o, s), v in sess.groupby(['origin', 'status']).size().items()}
        rec['sessions_arrival_equals_plan'] = bool(len(sess) == len(plan) and
                                                   np.array_equal(sess['sid'].to_numpy(), plan['sid'].to_numpy()) and
                                                   np.array_equal(sess['arrival_s'].to_numpy(dtype=float), plan['arrival_s'].to_numpy(dtype=float)))
        rec['plan_check'] = plan_vs_frozen(plan, args.plans_dir, arm, mult, seed)

        nb, blackout = completion_rate(sess, *BLACKOUT)
        nl, late = completion_rate(sess, *LATE)
        rec['n_completed_blackout'] = nb
        rec['blackout'] = blackout
        rec['n_completed_late'] = nl
        rec['late'] = late
        edges = np.arange(BIN300_LO, BIN300_HI + 1e-9, BIN300_W)
        rec['bins300_start'] = [float(e) for e in edges[:-1]]
        rec['bins300_count'] = [completion_count(sess, a, b) for a, b in zip(edges[:-1], edges[1:])]
        rec['bins300_count_burst'] = [completion_count(sess[sess['origin'] == 'burst'], a, b) for a, b in zip(edges[:-1], edges[1:])]
        run_end = ident['run_end_s'] if ident['run_end_s'] is not None else float(T_RUN)
        bl = backlog_slope(sess, run_end)
        rec.update({f'backlog_{k}': v for k, v in bl.items()})
        rec['slope'] = bl['slope']
        n_lp, lp = lambda_plan(plan)
        rec['n_base_plan_6000_8700'] = n_lp
        rec['lambda_plan'] = lp
        rec['hit'] = hit_fractions(req)

        # STUCK under every metric/window reading
        stuck = {}
        for wk, h in rec['hit'].items():
            for mk in ('frac_turns_cached_gt0', 'token_hit_rate', 'frac_turns_cached_gt50tok', 'frac_turns_cachedfrac_gt0p5'):
                stuck[f'{mk}@{wk}'] = (h[mk] is not None) and (h[mk] < STUCK_THR)
        rec['stuck_by_reading'] = stuck
        rec['stuck_readings_agree'] = len(set(stuck.values())) == 1
        # primary per the brief: the turn-share metric (config selects frac_turns_cached_gt50), brief text: cached tokens > 0
        rec['STUCK'] = stuck['frac_turns_cached_gt0@4500_8700']

        if arm == 'burst':
            cell = pred['cells'][mkey]
            fs = cell['seeds'][str(seed)]
            S_F = float(fs['windows']['slope']['slope'])
            F_wave = float(fs['burst_timing']['median'])
            S_QS = lp - LAMBDA_MISS_BRIEF
            S_QS_json = lp - lambda_miss_json
            wv, nwave, wlo, whi = wave_time(sess)
            tol = 0.15 * (F_wave - T_BURST)
            rec.update({
                'S_F': S_F, 'F_wave': F_wave, 'S_QS': S_QS, 'S_QS_jsonlambda': S_QS_json,
                'F_lam_plan_slope_window': float(fs['windows']['slope']['lam_plan']),
                'wave': wv, 'n_burst_completed': nwave, 'wave_lower_median': wlo, 'wave_upper_median': whi,
                'M2_tol_s': tol,
                'wave_minus_F': (wv - F_wave) if wv is not None else None,
                'dist_S_SF': abs(bl['slope'] - S_F), 'dist_S_SQS': abs(bl['slope'] - S_QS),
                'dist_S_SQS_jsonlambda': abs(bl['slope'] - S_QS_json),
            })
            rec['M1'] = bool(blackout <= 0.30)
            rec['M2'] = bool(wv is not None and abs(wv - F_wave) <= tol)
            rec['M3'] = bool(late <= 0.85)
            rec['M4'] = bool(abs(bl['slope'] - S_F) < abs(bl['slope'] - S_QS))
            # alternative readings
            rec['M2_lower_median'] = bool(wlo is not None and abs(wlo - F_wave) <= tol)
            rec['M2_upper_median'] = bool(whi is not None and abs(whi - F_wave) <= tol)
            rec['M4_jsonlambda'] = bool(abs(bl['slope'] - S_F) < abs(bl['slope'] - S_QS_json))
            rec['call'] = seed_call(rec['STUCK'], rec['M1'], rec['M2'], rec['M3'], rec['M4'], blackout, late)
            # call under every STUCK reading
            rec['call_by_stuck_reading'] = {k: seed_call(v, rec['M1'], rec['M2'], rec['M3'], rec['M4'], blackout, late)
                                            for k, v in stuck.items()}
            # CURVE-before-RENEWAL / NOT-TRAPPED-before-CURVE precedence alternatives
            curve = blackout >= 0.85 and late >= 0.85
            rec['curve_condition'] = bool(curve)
        else:
            for k in ('S_F', 'F_wave', 'S_QS', 'wave', 'n_burst_completed', 'M1', 'M2', 'M3', 'M4', 'call'):
                rec[k] = None
        runs.append(rec)

    # cell verdicts (BURST runs only)
    cells = {}
    for mult in sorted({r['rate_mult'] for r in runs if r['arm'] == 'burst'}):
        rs = sorted([r for r in runs if r['arm'] == 'burst' and r['rate_mult'] == mult], key=lambda r: r['seed'])
        calls = [r['call'] for r in rs]
        cells[f'{mult:.2f}'] = {
            'seeds': [r['seed'] for r in rs], 'calls': calls, 'verdict': cell_verdict(calls),
            'n_renewal': sum(c == 'RENEWAL' for c in calls),
            'verdict_by_stuck_reading': {k: cell_verdict([r['call_by_stuck_reading'][k] for r in rs])
                                         for k in rs[0]['call_by_stuck_reading']},
        }

    os.makedirs(args.out_dir, exist_ok=True)
    out = {'constants': {'lambda_ref': LAMBDA_REF, 'lambda_miss_brief': LAMBDA_MISS_BRIEF,
                         'lambda_miss_json': lambda_miss_json, 'blackout': BLACKOUT, 'late': LATE,
                         'slope_window': SLOPE_WIN, 'hit_windows': HIT_WINDOWS, 'stuck_thr': STUCK_THR},
           'pred_sha256': sha256(args.pred), 'runs': runs, 'cells': cells}
    with open(os.path.join(args.out_dir, 'recompute_out.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, default=float)

    cols = ['run', 'job_id', 'engine_label', 'arm', 'rate_mult', 'seed', 'blackout', 'late', 'wave', 'n_burst_completed',
            'slope', 'lambda_plan', 'S_F', 'S_QS', 'F_wave', 'M1', 'M2', 'M3', 'M4', 'STUCK', 'call']
    rows = []
    for r in runs:
        row = {c: r.get(c) for c in cols}
        for wk, h in r['hit'].items():
            row[f'turn_gt0_{wk}'] = h['frac_turns_cached_gt0']
            row[f'tok_{wk}'] = h['token_hit_rate']
            row[f'turn_gt50tok_{wk}'] = h['frac_turns_cached_gt50tok']
            row[f'turn_frac_gt0p5_{wk}'] = h['frac_turns_cachedfrac_gt0p5']
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(['arm', 'rate_mult', 'seed'], ascending=[True, False, True])
    df.to_csv(os.path.join(args.out_dir, 'recompute_runs.csv'), index=False, float_format='%.17g')
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 60)
    print(df[cols].to_string(index=False))
    print()
    print(df[['run', 'arm', 'rate_mult', 'seed'] + [c for c in df.columns if c.startswith(('turn_', 'tok_'))]].to_string(index=False))
    print()
    for r in sorted(runs, key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
        print(r['run'], r['arm'], r['rate_mult'], r['seed'], 'bins300:', ' '.join(str(c) for c in r['bins300_count']))
    print()
    print(json.dumps(cells, indent=1))


if __name__ == '__main__':
    main()
