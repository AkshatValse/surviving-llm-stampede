"""data-B: classify each run's hit-fraction trajectory into good (G) / bad (B) segments and
find collapses (G->B) and escapes (B->G).  Reads runs.csv / bins.csv written by extract.py.

States use a 300 s rolling hit fraction (turns>1 whose cached/prompt > 0.5, attributed by
completion time, 100 s bins, as analysis/summarize.py's frac_turns_cached_gt50):
  G: rolling hf >= 0.6 ; B: rolling hf <= 0.2 ; else M.  A segment counts if it lasts
  >= MIN_SEG s.  Collapse time = first 100 s bin of the B segment whose rolling hf <= 0.2
  (also reported: last bin with rolling hf >= 0.5 before it).
"""
import os, json, sys
import numpy as np, pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
MIN_SEG = float(os.environ.get("MIN_SEG", 500))
runs = pd.read_csv(os.path.join(OUT, "runs.csv"))
bins = pd.read_csv(os.path.join(OUT, "bins.csv"))


def roll(b, k=3):
    n = b.n.rolling(k, min_periods=1, center=False).sum()
    h = b.hits.rolling(k, min_periods=1, center=False).sum()
    return np.where(n >= 5, h / n.clip(lower=1), np.nan)


def segments(state, t0, binw=100.0):
    segs = []
    cur, start = None, None
    for i, s in enumerate(state):
        if s != cur:
            if cur is not None:
                segs.append((cur, t0[start], t0[i - 1] + binw))
            cur, start = s, i
    if cur is not None:
        segs.append((cur, t0[start], t0[len(state) - 1] + binw))
    return segs


recs = []
coarse = {}
for run, b in bins.groupby("run", sort=False):
    b = b.sort_values("t0").reset_index(drop=True)
    hr = roll(b)
    st = np.where(np.isnan(hr), "N", np.where(hr >= 0.6, "G", np.where(hr <= 0.2, "B", "M")))
    # carry N forward (sparse bins) so they do not split segments
    st2 = st.copy()
    for i in range(1, len(st2)):
        if st2[i] == "N":
            st2[i] = st2[i - 1]
    segs = segments(st2, b.t0.values)
    long = [(s, a, e) for (s, a, e) in segs if s in "GB" and e - a >= MIN_SEG]
    trans = []
    for (s1, a1, e1), (s2, a2, e2) in zip(long, long[1:]):
        if s1 != s2:
            # last time rolling hf >= 0.5 before a2
            pre = b.t0.values[(b.t0.values < a2) & (np.nan_to_num(hr, nan=-1) >= 0.5)]
            t_last_good = float(pre.max() + 100) if len(pre) else np.nan
            trans.append(dict(kind="collapse" if s1 == "G" else "escape", t=a2,
                              t_last_hf50=t_last_good, dur_before=e1 - a1, dur_after=e2 - a2))
    # coarse 300 s string of hf (one digit = floor(10*hf), '.' if empty)
    n3 = b.n.groupby(b.t0 // 300).sum(); h3 = b.hits.groupby(b.t0 // 300).sum()
    coarse[run] = "".join("." if n < 5 else ("X" if h / n >= 0.95 else str(int(10 * h / n)))
                          for n, h in zip(n3, h3))
    t_end = b.t0.max() + 100
    last = b[b.t0 >= t_end - 1000]
    recs.append(dict(run=run, segs=";".join(f"{s}{int(a)}-{int(e)}" for s, a, e in long),
                     n_trans=len(trans), trans=json.dumps(trans),
                     hf_last1000=last.hits.sum() / max(last.n.sum(), 1),
                     infl_end=int(b.inflight.iloc[-1]), active_end=b.active.iloc[-1],
                     active_max=b.active.max(), coarse=coarse[run]))

S = pd.DataFrame(recs).merge(runs, on="run")
S.to_csv(os.path.join(OUT, "states.csv"), index=False)
print("wrote states.csv", len(S))
