import sys, glob, numpy as np, pandas as pd
root = sys.argv[1]
rows = []
for d in sorted(glob.glob(f"{root}/agentload_e0_miss/*/")):
    rq = pd.read_csv(d + "requests.csv"); ss = pd.read_csv(d + "sessions.csv")
    import yaml; cfg = yaml.safe_load(open(d + "config_effective.yaml"))
    n = cfg["arrivals"]["closed_n"]; seed = cfg.get("run", {}).get("seed", cfg.get("seed"))
    ok = rq[rq.status == "ok"].copy(); ok["unc"] = ok.prompt_tokens - ok.cached_tokens
    comp = ss[ss.status == "completed"]
    edges = np.arange(900, 2701, 300)
    tb = [((ok.t_complete >= a) & (ok.t_complete < b)).sum() / 300 for a, b in zip(edges[:-1], edges[1:])]
    kb = [ok.unc[(ok.t_complete >= a) & (ok.t_complete < b)].sum() / 300 for a, b in zip(edges[:-1], edges[1:])]
    sb = [((comp.t_end >= a) & (comp.t_end < b)).sum() / 300 for a, b in zip(edges[:-1], edges[1:])]
    # slope test on per-bin token rate (6 bins): OLS slope with t-stat
    x = np.arange(6); 
    def slope(y):
        y = np.asarray(y, float); b = np.polyfit(x, y, 1)[0]; r = y - np.polyval(np.polyfit(x, y, 1), x)
        se = np.sqrt((r @ r) / 4 / ((x - x.mean()) ** 2).sum()); return b, b / se if se > 0 else np.nan
    print(f"\n=== POP={n} seed={seed} dir={d}")
    print(" bin start:", list(edges[:-1]))
    print(" turns/s   :", np.round(tb, 3).tolist(), " slope/bin=%.4f t=%.2f" % slope(tb))
    print(" ktok/s    :", np.round(np.array(kb) / 1e3, 2).tolist(), " slope/bin=%.1f t=%.2f" % slope(kb))
    print(" sess/s    :", np.round(sb, 4).tolist(), " slope/bin=%.4f t=%.2f" % slope(sb))
    meas = ok[(ok.t_complete >= 900) & (ok.t_complete < 2700)]
    print(" window: turns=%d uncached_tok/s=%.0f mean_prompt_tokens=%.0f max cached_tokens=%d errors=%d" % (
        len(meas), meas.unc.sum() / 1800, meas.prompt_tokens.mean(), ok.cached_tokens.max(), (rq.status != "ok").sum()))
    # in-flight composition: mean turn index of requests completing in window
    print(" mean turn index in window=%.1f  mean n_turns of in-window requests=%.1f  completed sessions in window=%d" % (
        meas.turn.mean(), meas.n_turns.mean(), ((comp.t_end >= 900) & (comp.t_end < 2700)).sum()))
