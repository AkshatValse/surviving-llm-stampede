import csv, json, math, statistics, pathlib, re, difflib

repo = pathlib.Path(r'C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\predict')
out = pathlib.Path(r'C:\Users\Akshat\Documents\Codex\2026-10-24\cl\work\prediction-verification')
report = repo / 'results/r6_predict_report/20261024-034707'

def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f, delimiter='\t' if path.suffix == '.tsv' else ','))

def key(r, extra=()):
    return tuple(r.get(c, '') for c in ('seed', 'variant', 'policy') + tuple(extra))

checks = {}
manifest = rows(repo / 'results/r6_predict/manifest.tsv')
dirs = {r['tag']: repo / r['dir'] for r in manifest}
checks['manifest'] = {'entries': len(manifest), 'unique_tags': len(dirs), 'bad_meta': []}
for tag,d in dirs.items():
    m=json.loads((d/'meta.json').read_text())
    if m.get('status')!='done' or m['git']['commit']!='630ab9edc7f40b33718771b4efb6a52da66b8eb6' or m['git']['dirty']:
        checks['manifest']['bad_meta'].append(tag)

pairs = [
 ('b1', dirs['r6pred_b1pop32_mixed'], out/'reruns/prefix_meta_probe_curve_codex_verify_b1_mixed_seed0/20261024-035525'),
 ('b2', dirs['r6pred_b2_mixed'], out/'reruns/prefix_meta_probe_open_codex_verify_b2_mixed_seed0/20261024-035527'),
 ('b3', dirs['r6pred_b3_lam0.12_mixed'], out/'reruns/prefix_meta_probe_burst_codex_verify_b3_mixed_seed0/20261024-035530')]
checks['reruns'] = {}
for name, original, rerun in pairs:
    result={}
    for fn,extra in [('runs.csv',()),('windows.csv',('t_start','t_end'))]:
        a=rows(original/fn); b=rows(rerun/fn)
        index={key(r,extra):r for r in a}
        mismatches=[]; cols=set(b[0]) - {'run_id','wall_s','wall_s_per_10k_sim_s'}
        for r in b:
            k=key(r,extra); orig=index[k]
            for c in sorted(cols):
                if orig[c]!=r[c]: mismatches.append({'key':k,'column':c,'original':orig[c],'rerun':r[c]})
        result[fn]={'compared_rows':len(b),'columns_per_row':len(cols),'exact_string_mismatches':mismatches}
    checks['reruns'][name]=result

E=15*(1-(14/15)**60)
checks['expected_turns']=E
b1=rows(report/'b1_seed.csv')
refs={}
for mode in ('mixed','separate_prefill_priority'):
    selected=[r for r in b1 if r['mode']==mode and r['n']=='32']
    refs[mode]=(statistics.mean(float(r['mu_turns']) for r in selected),statistics.mean(float(r['token_rate']) for r in selected))

def slope(xs,ys):
    xm=statistics.mean(xs);ym=statistics.mean(ys)
    return sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)

expected_b3={(r['mode'],float(r['lam']),int(r['seed']),r['arm']):r for r in rows(report/'b3_runs.csv')}
checks['b3_independent']={'runs_checked':0,'mismatches':[], 'max_absolute_numeric_delta':0.0}
for tag,d in dirs.items():
    if not tag.startswith('r6pred_b3_lam'): continue
    mode='mixed' if tag.endswith('_mixed') else 'separate_prefill_priority'
    rs=rows(d/'runs.csv');wins=rows(d/'windows.csv');lm,tm=refs[mode]
    for r in rs:
        w=[x for x in wins if x['run_id']==r['run_id'] and float(x['t_start'])>=6200 and float(x['t_end'])<=8700]
        assert len(w)==25
        q=[float(x['queue_mean'])+float(x['gate_mean']) for x in w]
        st={'hit':sum(float(x['hits']) for x in w)/sum(float(x['admitted_turns']) for x in w),
            'backlog':statistics.mean(q),'slope':slope([(float(x['t_start'])+float(x['t_end']))/2 for x in w],q),
            'token_rate':statistics.mean(float(x['prefill_tok_per_s']) for x in w)}
        ratio=st['token_rate']/tm; threshold=.5*(float(r['lam'])-lm)
        trapped=abs(ratio-1)<=.15 and st['slope']>threshold
        recovered=st['hit']>.8 and st['backlog']<20
        label='BOTH' if trapped and recovered else 'TRAPPED' if trapped else 'RECOVERED' if recovered else 'neither'
        k=(mode,float(r['lam']),int(r['seed']),r['arm']); exp=expected_b3[k]
        for field,val in st.items():
            delta=abs(val-float(exp[field])); checks['b3_independent']['max_absolute_numeric_delta']=max(checks['b3_independent']['max_absolute_numeric_delta'],delta)
            if not math.isclose(val,float(exp[field]),rel_tol=1e-12,abs_tol=1e-12): checks['b3_independent']['mismatches'].append([k,field,val,exp[field]])
        if label!=exp['label']:checks['b3_independent']['mismatches'].append([k,'label',label,exp['label']])
        checks['b3_independent']['runs_checked']+=1

checks['b2_independent']={'runs_checked':0,'classification_mismatches':[], 'positive_trend_stable_runs':0}
for mt in ('mixed','sep'):
    d=dirs['r6pred_b2_'+mt]
    rs=rows(d/'runs.csv');wins=rows(d/'windows.csv');v={(int(x['seed']),float(x['lam'])):x for x in rows(d/'open_verdicts.csv')}
    for r in rs:
        w=[x for x in wins if x['run_id']==r['run_id'] and float(x['t_start'])>=1500]
        assert len(w)==15
        q=[float(x['queue_mean'])+float(x['gate_mean']) for x in w]
        rise=slope([(float(x['t_start'])+float(x['t_end']))/2 for x in w],q)*1500
        stable=float(r['stopped_early'])==0 and float(r['final_backlog'])<50 and rise<=10
        expected=v[(int(r['seed']),float(r['lam']))]['stable']=='True'
        if stable!=expected:checks['b2_independent']['classification_mismatches'].append([mt,r['seed'],r['lam'],stable,expected])
        if stable and rise>0:checks['b2_independent']['positive_trend_stable_runs']+=1
        checks['b2_independent']['runs_checked']+=1

notes=(repo/'notes/PREDICTIONS.md').read_text()
section=notes.split('## 4. Tables',1)[1].split('## 5. How to read',1)[0]
checks['generated_table_rows_match_notes_exactly']=[x for x in (report/'tables.md').read_text().splitlines() if x.startswith('|')]==[x for x in section.splitlines() if x.startswith('|')]
log=(repo/'results/r6_predict/full_suite_pytest.log').read_text()
progress=re.findall(r'^([.FsxXE]+)\s+\[\s*\d+%\]',log,re.M)
checks['logged_pytest_progress_counts']={c:''.join(progress).count(c) for c in '.FsxXE'}
checks['logged_pytest_failed_lines']=len(re.findall(r'^FAILED ',log,re.M))
(out/'audit.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))

# Proposed prose corrections only; preserve preregistered thresholds and numerical tables.
path=repo/'notes/PREDICTIONS.md'
old=path.read_text();new=old.replace('Stable runs out of 3 (stable := final backlog < 50 and no upward backlog trend over the last 1500 s):',
 'Stable runs out of 3 (stable := no early stop, final backlog < 50, and an OLS backlog rise of at most 10 requests over the last 1500 s, as fixed in section 3):')
anchor='### How far to trust the levels (from the Validate stage, `calibration/round6_server_log_fit/VALIDATION.md`)'
paragraph=('### Cross-prediction sanity check\n\n'
 'The B2 all-stable edges (0.14 mixed, 0.15 separate) are above the B1 all-miss floors and below the B4 300k throughput peaks. '
 'The requested strict containment check does **not** pass: B3 predicts PASS at 0.16, beyond both B2 edges, and mixed also predicts PASS at its 0.14 boundary. '
 'B2 requires all three seeds to remain stable over 3000 s, whereas B3 requires two of three NOBURST arms to be good over a different evaluation window in an 8700 s run. '
 'These differing criteria can explain the disagreement, but the results do not establish a common strict stability boundary. The frozen predictions and thresholds are retained.\n\n')
new=new.replace(anchor,paragraph+anchor)
new=new.replace('while the plateau (n = 16 to 24, within 9%)', 'while the mixed-mode plateau (n = 16 to 24, within 9.2%)')
patch=''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/notes/PREDICTIONS.md',tofile='b/notes/PREDICTIONS.md'))
(out.parent/'prediction-fixes.patch').write_text(patch,encoding='utf-8',newline='\n')
