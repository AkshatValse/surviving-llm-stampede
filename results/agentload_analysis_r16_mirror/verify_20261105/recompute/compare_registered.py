"""Compare recompute_out.json (independent) with the registered scorer's mirror_runs.csv and mirror_verdict.json.
Run only after recompute_mirror.py has written its outputs."""
import json
import math
import sys

import pandas as pd

mine = json.load(open(sys.argv[1], encoding='utf-8'))
reg = pd.read_csv(sys.argv[2], dtype=str, keep_default_na=False)
verdict = json.load(open(sys.argv[3], encoding='utf-8'))
REL = 1e-9

reg['run'] = reg['run_dir'].str.replace('/', '\\').str.split('\\').str[-1]
regd = {r['run']: r for _, r in reg.iterrows()}


def as_float(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return None if (isinstance(s, float) and math.isnan(s)) else float(s)
    s = str(s).strip()
    if s == '':
        return None
    return float(s)


def as_bool(s):
    if s is None:
        return None
    if isinstance(s, bool):
        return s
    s = str(s).strip()
    if s == '':
        return None
    return {'True': True, 'False': False}[s]


def rel(a, b):
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b))


# (my key or callable, registered column, kind)
FIELDS = [
    ('engine_label', 'label', 'str'),
    ('arm', 'arm', 'str'),
    ('rate_mult', 'rate_mult', 'num'),
    ('seed', 'seed', 'num'),
    ('status', 'run_status', 'str'),
    ('run_end_s', 'run_end_s', 'num'),
    (lambda r: r['abort_reason'] is not None, 'aborted', 'bool'),
    (lambda r: r['plan_check'].get('equal_within_1e-12_rel'), 'plan_matches_frozen', 'bool'),
    (lambda r: 0.07153402100919228, 'lambda_ref', 'num'),
    ('blackout', 'blackout_rate', 'num'),
    ('n_completed_blackout', 'blackout_n', 'num'),
    ('late', 'late_rate', 'num'),
    ('n_completed_late', 'late_n', 'num'),
    ('wave', 'wave_time', 'num'),
    ('n_burst_completed', 'burst_completed', 'num'),
    ('slope', 'slope', 'num'),
    ('backlog_n_bins', 'slope_bins', 'num'),
    ('lambda_plan', 'lambda_plan_slope_window', 'num'),
    (lambda r: r['hit']['5700_8700']['frac_turns_cached_gt0'], 'hit_eval', 'num'),
    ('STUCK', 'stuck', 'bool'),
    ('S_F', 'S_F', 'num'),
    ('S_QS', 'S_QS', 'num'),
    ('F_wave', 'F_wave', 'num'),
    ('M1', 'M1', 'bool'),
    ('M2', 'M2', 'bool'),
    ('M3', 'M3', 'bool'),
    ('M4', 'M4', 'bool'),
    ('call', 'call', 'str'),
]

disag = []
n_checked = 0
for r in sorted(mine['runs'], key=lambda r: (r['arm'], -r['rate_mult'], r['seed'])):
    g = regd.get(r['run'])
    if g is None:
        disag.append((r['run'], 'MISSING in registered', '', '', ''))
        continue
    for key, col, kind in FIELDS:
        m = key(r) if callable(key) else r.get(key)
        gv = g[col]
        n_checked += 1
        if kind == 'num':
            a, b = as_float(m), as_float(gv)
            if a is None and b is None:
                continue
            if a is None or b is None:
                disag.append((r['run'], col, m, gv, 'one side empty'))
                continue
            d = rel(a, b)
            if d > REL:
                disag.append((r['run'], col, repr(a), repr(b), f'rel {d:.3e} abs {a - b:+.3e}'))
        elif kind == 'bool':
            a, b = (None if m is None else bool(m)), as_bool(gv)
            if a != b:
                disag.append((r['run'], col, a, b, 'boolean differs'))
        else:
            a, b = ('' if m is None else str(m)), str(gv)
            if a != b:
                disag.append((r['run'], col, a, b, 'string differs'))

extra_reg = sorted(set(regd) - {r['run'] for r in mine['runs']})
print(f'checked {n_checked} field values over {len(mine["runs"])} runs; registered-only runs: {extra_reg}')
print(f'{len(disag)} disagreements (rel > {REL:g}, boolean, string):')
for d in disag:
    print('  ', ' | '.join(str(x) for x in d))

print()
print('cell verdicts: mine vs registered')
for mk, c in mine['cells'].items():
    rv = verdict['cells'].get(mk, {})
    rcalls = [rv.get('calls', {}).get(str(s), [None])[0] for s in c['seeds']]
    print('  ', mk, 'mine', c['verdict'], c['calls'], '| registered', rv.get('verdict'), rcalls,
          '| AGREE' if (c['verdict'] == rv.get('verdict') and c['calls'] == rcalls) else '| DISAGREE')
