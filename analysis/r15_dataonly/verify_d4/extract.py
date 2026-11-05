import json, sys, os
REPO = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research\.claude\worktrees\reframe-draft-211a57"
files = {
 'a100_150k': 'results/theory/merged/a100_pool150k.json',
 'a100_300k': 'results/theory/merged/a100_300k.json',
 'a100_600k': 'results/theory/merged/a100_pool600k.json',
 'a100_native': 'results/theory/merged/a100_native.json',
 'h200_300k': 'results/theory/merged/h200_300k.json',
 'h200_600k': 'results/theory/pred2/h200_600k.json',
 'vllm_300k': 'results/theory/merged/vllm_300k.json',
 'llama_300k': 'results/theory/merged/llama31_8b_300k.json',
}
for k, f in files.items():
    p = os.path.join(REPO, f)
    d = json.load(open(p))
    am = d.get('all_miss', {})
    th = am.get('threshold', {})
    cf = d.get('closed_curve', {}).get('fluid', {})
    ca = d.get('closed_curve', {}).get('annealed', {})
    w = d.get('window', {})
    print(k, f)
    print('  top keys:', list(d.keys()))
    print('  spec:', d.get('spec_name'), '| desc:', d.get('description'))
    print('  info:', d.get('info'))
    print('  nu_b=%s n_b=%s tool=%s pool=%s E_S=%s E_bar=%s mu_b=%s' % (am.get('nu_b'), am.get('n_b'), th.get('tool_call_part'), th.get('pool_part'), th.get('E_S'), th.get('E_bar'), th.get('mu_b')))
    print('  fluid: peak_n=%s mu_max=%s hit_at_peak=%s n_half=%s' % (cf.get('peak_n'), cf.get('mu_max'), cf.get('hit_at_peak'), cf.get('n_half')))
    print('  annealed: peak_n=%s mu_max=%s hit_at_peak=%s n_half=%s' % (ca.get('peak_n'), ca.get('mu_max'), ca.get('hit_at_peak'), ca.get('n_half')))
    print('  window:', {kk: vv for kk, vv in w.items() if not isinstance(vv, dict)})
