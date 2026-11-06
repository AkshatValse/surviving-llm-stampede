import json, math, subprocess
import numpy as np, pandas as pd
W = r"C:/Users/Akshat/Desktop/Claude Code/Nova-Research-wt/mirror"
R = W + "/results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst/"
pred = json.loads(subprocess.run(["git","-C",W,"show","r16-mirror-reg:results/theory/r16/mirror_predictions.json"],capture_output=True,text=True,check=True).stdout)
LR = float(pred["lambda_ref"]); LM = float(pred["lambda_miss_model"])
runs = {"20261105-145227":("burst",1.65,0),"20261105-145244-2":("burst",1.65,1),"20261105-145240":("burst",1.65,2),
        "20261105-145244-1":("burst",1.35,0),"20261105-145246":("burst",1.35,1),"20261105-145244":("burst",1.35,2),
        "20261105-145242":("noburst",1.65,0),"20261105-145247":("noburst",1.65,1),"20261105-145248":("noburst",1.65,2)}
E0A_TURNS, E0A_TOK = 1.504982870256933, 12120.33426835178
for k, (arm, mult, seed) in runs.items():
    p = R + k
    meta = json.load(open(p+"/meta.json")); run_end = float(meta["outcome"]["t_end_s"])
    ses = pd.read_csv(p+"/sessions.csv"); req = pd.read_csv(p+"/requests.csv")
    plan = pd.read_csv(p+"/plan.csv", float_precision="round_trip")
    fro = pd.read_csv(W + f"/results/theory/r16/mirror_plans/{arm}_{mult:g}_seed{seed}.csv", float_precision="round_trip")
    da = float(np.max(np.abs(plan["arrival_s"].to_numpy(float) - fro["arrival_s"].to_numpy(float))))
    dt = float(np.max(np.abs(plan["tool_time_total_s"].to_numpy(float) - fro["tool_time_total_s"].to_numpy(float))))
    exact = all((plan[c].astype(str).to_numpy() == fro[c].astype(str).to_numpy()).all() for c in ("sid","origin","idx","n_turns"))
    # sessions.csv arrival vs plan
    m = ses.merge(plan, on="sid", suffixes=("", "_plan"))
    d_arr = float(np.max(np.abs(m["arrival_s"] - m["arrival_s_plan"])))
    d_nt = int((m["n_turns"] != m["n_turns_plan"]).sum())
    lag = (ses["t_first_send"] - ses["arrival_s"]).dropna()
    ok = req[req["status"]=="ok"]
    sd_ = ok["sched_delay_s"].dropna()
    print(f"== {arm} {mult} s{seed} ({k}): plan vs frozen: ids exact {exact}, max|d arrival| {da:.3g} s, max|d tool_total| {dt:.3g} s; "
          f"sessions.csv vs plan: max|d arrival| {d_arr:.3g}, n_turns mismatches {d_nt}")
    print(f"   first-send lag: median {lag.median():.4f} s, max {lag.max():.3f} s; request sched_delay_s: median {sd_.median():.4f}, p99 {sd_.quantile(0.99):.3f}, max {sd_.max():.3f}")
    for (a, b) in [(5700., 8700.), (6600., 8700.)]:
        w = ok[(ok["t_complete"]>=a)&(ok["t_complete"]<b)]
        unc = (w["prompt_tokens"] - w["cached_tokens"].fillna(0)).sum()/(b-a)
        print(f"   [{a:.0f},{b:.0f}): ok turns/s {len(w)/(b-a):.4f} (E0a {E0A_TURNS:.4f}, ratio {len(w)/(b-a)/E0A_TURNS:.3f}); uncached tok/s {unc:.0f} "
              f"(E0a {E0A_TOK:.0f}, ratio {unc/E0A_TOK:.3f}; std E0a 11243 ratio {unc/11243.18:.3f}); mean prompt {w['prompt_tokens'].mean():.0f}; mean turn {w['turn'].mean():.2f}")
    # hit over exact [5700, 8700)
    okh = ok.copy(); okh["fr"] = okh["cached_tokens"].fillna(0)/okh["prompt_tokens"]
    h1 = okh[(okh["t_complete"]>=5700)&(okh["t_complete"]<8700)]["fr"].gt(0.5).mean()
    h2 = okh[(okh["t_complete"]>=5700)&(okh["t_complete"]<run_end+1e-9)]["fr"].gt(0.5).mean()
    print(f"   hit frac_turns>0.5 over [5700,8700): {h1:.6f}; over [5700,t_end_s]: {h2:.6f}; n turns in (8700, t_end]: {int(((ok['t_complete']>=8700)&(ok['t_complete']<=run_end)).sum())}")
    if arm == "burst":
        b = ses[ses["origin"]=="burst"]
        print(f"   burst sessions: n {len(b)}, completed {int((b['status']=='completed').sum())}, t_end range [{b['t_end'].min():.1f}, {b['t_end'].max():.1f}], arrival range [{b['arrival_s'].min():.2f}, {b['arrival_s'].max():.2f}]")
        c = ses[ses["status"]=="completed"]
        for (a, bb) in [(2400., 3600.), (6600., 8700.)]:
            cc = c[(c["t_end"]>=a)&(c["t_end"]<bb)]
            print(f"   completions in [{a:.0f},{bb:.0f}) by origin: {cc['origin'].value_counts().to_dict()}; by n_turns: {cc['n_turns'].value_counts().sort_index().to_dict()}")
        # conservation: arrivals - completions vs slope
        arr = ((ses["arrival_s"]>=6000)&(ses["arrival_s"]<8700)).sum(); cmp_ = ((c["t_end"]>=6000)&(c["t_end"]<8700)).sum()
        print(f"   [6000,8700): arrivals {arr}, completions {cmp_} ({cmp_/2700/LR:.3f} lam_ref); (arr-comp)/2700 = {(arr-cmp_)/2700:.5f} /s")
