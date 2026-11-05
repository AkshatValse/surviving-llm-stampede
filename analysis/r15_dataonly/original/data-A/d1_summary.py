"""Summarize d1_runs.csv per group (min-max across runs)."""
import os
import pandas as pd
S = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(f"{S}/d1_runs.csv")
def mm(x, f="{:.0f}"):
    x = x.dropna()
    return "-" if not len(x) else (f.format(x.min()) if x.min() == x.max() else f"{f.format(x.min())}-{f.format(x.max())}")
rows = []
for (g, rate), x in d.groupby(["group", "rate_mult"]):
    rows.append(dict(group=g, rate=rate, n=len(x), all_trig_gone=int(x.t_free.notna().sum()),
        t_last_trig_end=mm(x.t_last_trig_end), trig_left_at_end=mm(x.n_trig_left_end),
        trig_active_4500=mm(x.n_trig_active_4500), trig_active_5700=mm(x.n_trig_active_5700),
        pop_eval=mm(x.pop_eval), pop_end=mm(x.pop_end), trig_share_eval=mm(100*x.trig_share_eval, "{:.1f}%"),
        inflight_eval=mm(x.inflight_eval), hit_eval=mm(x.hit_eval, "{:.3f}"), hit_base_eval=mm(x.hit_base_eval, "{:.3f}"),
        trapped_s_after_last_trig=mm(x.s_trap_after_trig), hit_after_trig=mm(x.hit_after_trig, "{:.3f}"),
        turns_after_trig=mm(x.n_turns_after_trig)))
t = pd.DataFrame(rows)
cols = list(t.columns)
print("| " + " | ".join(cols) + " |"); print("|" + "---|" * len(cols))
for _, r in t.iterrows(): print("| " + " | ".join(str(r[c]) for c in cols) + " |")
