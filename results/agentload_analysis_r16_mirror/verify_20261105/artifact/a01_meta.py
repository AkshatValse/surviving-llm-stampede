import json, glob, os, sys
root = sys.argv[1]
rows = []
for d in sorted(glob.glob(os.path.join(root, '*'))):
    m = json.load(open(os.path.join(d, 'meta.json')))
    argv = m.get('argv', [])
    sets = {}
    for i, a in enumerate(argv):
        if a == '--set':
            k, v = argv[i+1].split('=', 1)
            sets[k] = v
        if a == '--seed':
            sets['seed'] = argv[i+1]
    o = m['outcome']
    print(os.path.basename(d), m['slurm_env']['SLURM_JOB_ID'], m['slurm_env']['SLURM_JOB_NAME'], m['hostname'],
          'arm=', m.get('arm'), 'rate=', sets.get('arrivals.rate_mult'), 'seed=', sets.get('seed'),
          'status=', m['status'], 'git=', m['git']['commit'][:7], m['git']['dirty'], m['git']['branch'])
    print('   start', m['start_time'], 'end', m['end_time'], 'wall', round(m['wall_s'], 1), 'planned', m['n_sessions_planned'],
          'rate', round(m['resolved_rate_sessions_per_s'], 6), 'label', m['engine_label'])
    print('   outcome:', {k: v for k, v in o.items() if k not in ('gate',)})
    print('   gate:', o.get('gate'))
    print('   start_state:', m.get('start_state_verified'), m.get('start_state_detail'))
    print('   salt', m.get('content_salt'), 'feedback', m.get('output_feedback_configured'), 'prereg', m.get('prereg_sha256')[:12], 'burst set', sets.get('arrivals.burst'), sets.get('arrivals.burst.t_s'))
