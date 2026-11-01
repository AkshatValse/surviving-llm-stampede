"""POST-HOC, read-only: an online trap detector a client could run, applied to committed runs. Every TICK s, over completions
in the last WIN s: H = fraction of follow-up turns (turn >= 2, ok) with cached/prompt > 0.5; alarm if n >= NMIN and H < HLOW.
Reports first alarm time, alarm time relative to the burst, number of alarm ticks, and whether hits ever returned (H > 0.8 for
300 s) after the first alarm."""
import sys, glob, json
import numpy as np, pandas as pd
from analysis.load import load_run
TICK, WIN, NMIN, HLOW = 10.0, 60.0, 20, 0.2
rows = []
for d in sys.argv[1:]:
    try:
        r = load_run(d)
    except Exception as e:
        print("skip", d, e); continue
    q = r.requests
    ok = q[(q["status"] == "ok") & (q["turn"] >= 2)].copy()
    if ok["cached_tokens"].isna().all():
        continue
    ok = ok.sort_values("t_complete")
    tc = ok["t_complete"].to_numpy(float)
    hit = (ok["cached_tokens"].fillna(0) / ok["prompt_tokens"].where(ok["prompt_tokens"] > 0) > 0.5).to_numpy()
    cs = np.concatenate([[0], np.cumsum(hit)])
    ts = np.arange(WIN, r.t_end_s, TICK)
    lo = np.searchsorted(tc, ts - WIN); hi = np.searchsorted(tc, ts)
    n = hi - lo; H = np.where(n > 0, (cs[hi] - cs[lo]) / np.maximum(n, 1), np.nan)
    alarm = (n >= NMIN) & (H < HLOW)
    first = float(ts[alarm][0]) if alarm.any() else None
    tb = r.t_burst_ref
    ret = None
    if first is not None:
        good = (n >= NMIN) & (H > 0.8)
        k = int(round(300 / TICK))
        idx = np.where(ts > first)[0]
        for i in idx:
            if i + k <= len(good) and good[i:i + k].all():
                ret = float(ts[i]); break
    rows.append({"dir": d.split("results/nova/")[-1][:90], "label": r.label, "arm": r.arm or r.arm_derived if r.t_burst_ref is not None else "e0b",
                 "mult": r.rate_mult, "seed": r.seed, "t_burst": tb, "first_alarm": first,
                 "delay_after_burst": (first - tb) if (first is not None and tb is not None) else None,
                 "alarm_ticks": int(alarm.sum()), "ticks": int(len(ts)), "hits_returned_at": ret})
df = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 60)
print(df.drop(columns=["dir"]).to_string())
import os
if os.environ.get("DETECTOR_OUT"):
    df.to_csv(os.environ["DETECTOR_OUT"], index=False)
