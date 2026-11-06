"""E0a (all-miss, cache off) of the MIRROR workload: sanity of the POP-32 run and the POP-64 check, own recomputation of
lambda_miss over several windows, and the robustness of 'LATE below the all-miss capacity'.

Usage: python -I a05_e0a.py WORKTREE OUTDIR
"""
import json
import os
import sys

import numpy as np
import pandas as pd

WT = sys.argv[1]
OUT = sys.argv[2]
E = os.path.join(WT, "results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results")
RUNS = {"POP32 (17264093)": "agentload_e0_miss/20261105-145429", "POP64 check (17264093)": "agentload_e0_miss_popcheck/20261105-154232",
        "smoke POP32 300s (17264039)": "agentload_e0_miss/20261105-145027", "smoke POP64 300s (17264039)": "agentload_e0_miss_popcheck/20261105-145831"}
LAM_REF = 0.07153402100919228
ET = 19.811135170465317
LATE = {"1.65x-s0": 0.5924586900477234, "1.65x-s1": 0.6057723684757622, "1.65x-s2": 0.4992629410514523,
        "1.35x-s0": 0.6190860469038009, "1.35x-s1": 0.7389091527561494, "1.35x-s2": 0.8454185801804592}
LATE_N = {"1.65x-s0": 89, "1.65x-s1": 91, "1.65x-s2": 75, "1.35x-s0": 93, "1.35x-s1": 111, "1.35x-s2": 127}


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", lambda x: f"{x:.5g}")
    caps = {}
    for name, rd in RUNS.items():
        d = os.path.join(E, rd)
        meta = json.load(open(os.path.join(d, "meta.json")))
        cfg = open(os.path.join(d, "config_effective.yaml")).read()
        req = pd.read_csv(os.path.join(d, "requests.csv"))
        ses = pd.read_csv(os.path.join(d, "sessions.csv"))
        o = meta["outcome"]
        ok = req[req.status == "ok"].copy()
        ok["unc"] = ok.prompt_tokens - ok.cached_tokens
        dur = meta["duration_s_configured"]
        print(f"\n##### {name}  {rd}  node {meta['hostname']} job {meta['slurm_env']['SLURM_JOB_ID']} label {meta['engine_label']} "
              f"status {meta['status']} duration {dur} wall {meta['wall_s']:.0f}")
        print(f"   outcome: sessions started {o['sessions_started']} completed {o['sessions_completed']} failed {o['sessions_failed']} "
              f"cancelled {o['sessions_cancelled']}; requests ok {o['requests_ok']} error {o['requests_error']} cancelled "
              f"{o['requests_cancelled']}; errors_by_kind {o.get('errors_by_kind')}; abort {o['abort_reason']}; max_inflight "
              f"{o['max_inflight_seen']}; scrape failures {o['metrics_scrape_failures']} skipped {o['metrics_skipped_ticks']}")
        print(f"   req status {req.status.value_counts().to_dict()}, http {req.http_status.value_counts(dropna=False).to_dict()}, "
              f"cached tokens total {int(ok.cached_tokens.sum())}, completion_tokens!=100: {int((ok.completion_tokens != 100).sum())}, "
              f"prompt mismatch {int((ok.prompt_tokens != ok.prompt_tokens_client).sum())}, n_turns values "
              f"{ses.n_turns.value_counts().sort_index().to_dict()}")
        canc = req[req.status == "cancelled"]
        print(f"   cancelled requests: t_complete set {sorted(set(np.round(canc.t_complete.dropna(), 0)))[:4]}; "
              f"max gap between ok completions {np.diff(np.sort(ok.t_complete)).max():.2f} s; max latency {ok.latency_s.max():.1f} s; "
              f"sched_delay max {req.sched_delay_s.max():.4f}")
        if dur < 1000:
            continue
        comp = ses[ses.status == "completed"]
        rows = []
        for a, b in [(900, 2700), (600, 2700), (1200, 2700), (900, 1800), (1800, 2700), (300, 2700)]:
            w = ok[(ok.t_complete >= a) & (ok.t_complete < b)]
            c = comp[(comp.t_end >= a) & (comp.t_end < b)]
            L = b - a
            rows.append(dict(window=f"[{a},{b})", sessions=len(c), sess_per_s=len(c) / L, sess_over_ref=len(c) / L / LAM_REF,
                             turns=len(w), turns_per_s=len(w) / L, turns_based_over_ref=len(w) / L / ET / LAM_REF,
                             unc_tok_per_s=w.unc.sum() / L, mean_prompt=w.prompt_tokens.mean(),
                             lat_med=w.latency_s.median()))
        R = pd.DataFrame(rows)
        print(R.to_string(index=False))
        caps[name] = R.iloc[0].to_dict()
        # synchronisation of the closed cohort (deterministic T = 20, all sessions start at t = 0)
        cb = comp.copy()
        cb["b120"] = (cb.t_end // 120 * 120).astype(int)
        print("   session completions per 120-s bin: " + " ".join(f"{k}:{v}" for k, v in cb.groupby("b120").size().items()))
        # bootstrap-free spread: completions in 300-s blocks over [900,2700)
        blocks = [len(comp[(comp.t_end >= a) & (comp.t_end < a + 300)]) for a in range(900, 2700, 300)]
        print(f"   completions in six 300-s blocks of [900,2700): {blocks}; mean {np.mean(blocks):.1f} sd {np.std(blocks, ddof=1):.1f} "
              f"-> SE of the 1800-s rate {np.std(blocks, ddof=1) / np.sqrt(6) / 300 / LAM_REF:.3f} lambda_ref")
        tblocks = [len(ok[(ok.t_complete >= a) & (ok.t_complete < a + 300)]) for a in range(900, 2700, 300)]
        print(f"   turns in six 300-s blocks: {tblocks}; turns-based SE {np.std(tblocks, ddof=1) / np.sqrt(6) / 300 / ET / LAM_REF:.4f} lambda_ref")

    print("\n=== W10 robustness: LATE (registered scorer values, lambda_ref units) against each all-miss capacity estimate")
    est = {"E0a POP32 sessions [900,2700)": caps["POP32 (17264093)"]["sess_over_ref"],
           "E0a POP32 turns-based": caps["POP32 (17264093)"]["turns_based_over_ref"],
           "POP64 sessions [900,2700)": caps["POP64 check (17264093)"]["sess_over_ref"],
           "POP64 turns-based": caps["POP64 check (17264093)"]["turns_based_over_ref"],
           "model (frozen)": 1.0460918059169675}
    for k, v in LATE.items():
        n = LATE_N[k]
        se = v / np.sqrt(n)
        print(f"   {k}: LATE {v:.3f} (n {n}, Poisson SE {se:.3f}); ratio to each estimate: "
              + ", ".join(f"{e}: {v / c:.3f}" for e, c in est.items()))
    print("   estimates: " + ", ".join(f"{e} = {c:.4f}" for e, c in est.items()))


if __name__ == "__main__":
    main()
