"""D2: Lu et al. (arXiv:2611.02543, Sec. 7.1) SLO goodput on our paired arms.  Read-only over results/nova.

goodput = completed sessions per hour with slowdown <= 4 (their ITL condition is OMITTED: we have no per-token ITL).
slowdown(session) = (t_end - arrival_s) / ref, arrival_s is the planned arrival (so the client-gate wait and the wait before
the first call are included), ref = planned tool time (plan.csv tool_time_total_s, the n_turns-1 tool sleeps) +
sum_{k=1..n_turns} L0(k), L0(k) = unloaded per-call latency of turn k (prompt 2000 + 650(k-1) tokens, 100 decode tokens).

L0 per cell, estimated from that cell's NOBURST runs (all seeds and rates pooled; at 1.35-4 x lambda_ref with a warm cache
these runs have ~2-6 requests in flight, the lightest real-engine load we have that matches the workload exactly):
  turn 1: minimum observed latency of turn-1 calls (a cold 2000-token prefill + 100 decode);
  turn k >= 2: a least-squares line in k through the per-turn MINIMUM latency of cache-hit calls (cached/prompt > 0.5) over turns
  with >= 20 calls, evaluated at every k (smooths the sparse long-session tail).
Sensitivity variant 'q05': the same with the per-turn 5th percentile instead of the minimum (larger ref, laxer SLO).

Windows (sessions of BASE origin only, so arms are comparable; burst sessions all arrive in [1200, 1260) s):
  H1  = arrival cohort [1260, 4860) s: sessions arriving in the hour after the burst ends (Lu's "following hour" metric)
  J   = arrival cohort [5700, 8400) s: arrivals in the judged window, 300 s censoring margin before the 8700 s end
  JC  = completion window [5700, 8700) s: base sessions COMPLETING in the judged window with slowdown <= 4, per hour
  ALL = arrival cohort [0, 8400) s (whole run)
Loss = 1 - G(arm) / G(NOBURST, same cell, rate, seed) (common random numbers: same base arrivals and specs).
"""
import os, sys
import numpy as np
import pandas as pd

S = os.path.dirname(os.path.abspath(__file__))
WINDOWS = {"H1": ("arr", 1260.0, 4860.0), "J": ("arr", 5700.0, 8400.0), "JC": ("end", 5700.0, 8700.0),
           "ALL": ("arr", 0.0, 8400.0)}
KMAX = 60


def base_cell(label):
    lab = label
    for suf in ("-rescue-native", "-rescue-smoke", "-rescue"):
        if lab.endswith(suf):
            return lab[: -len(suf)] + ("-native" if suf == "-rescue-native" else "")
    for b in ("-b25", "-b40", "-b50", "-b60", "-b100", "-shed-t600", "-shed-t3600"):
        if lab.endswith(b):
            return lab[: -len(b)]
    return lab


def cell_key(r):
    # the pre-registration vLLM grid shares the 'vllm-fcfs' label with the registered vLLM cell
    if r.label == "vllm-fcfs" and r.pulled.startswith("e2_native_vllm"):
        return "vllm-fcfs-grid"
    return base_cell(r.label)


def unloaded_ref(nb_dirs, stat):
    reqs = []
    for d in nb_dirs:
        r = pd.read_csv(f"{d}/requests.csv", usecols=["turn", "status", "latency_s", "prompt_tokens", "cached_tokens"],
                        low_memory=False)
        reqs.append(r[r.status == "ok"])
    r = pd.concat(reqs)
    f = (lambda x: x.min()) if stat == "min" else (lambda x: np.percentile(x, 5))
    t1 = f(r[r.turn == 1].latency_s.values)
    h = r[(r.turn >= 2) & ((r.cached_tokens.fillna(0) / r.prompt_tokens) > 0.5)]
    g = h.groupby("turn").latency_s.agg(["size", lambda x: f(x.values)])
    g.columns = ["n", "v"]
    g = g[g.n >= 20]
    a, b = np.polyfit(g.index.values.astype(float), g.v.values, 1)
    L = np.zeros(KMAX + 1)
    L[1] = t1
    k = np.arange(2, KMAX + 1)
    L[2:] = b + a * k
    return L, dict(L1=t1, slope_per_turn=a, intercept=b, L2=L[2], L15=L[15], L40=L[40], n_turns_fit=len(g),
                   n_req=len(r), hit_followup_frac=float(len(h) / max(1, (r.turn >= 2).sum())))


def session_table(d, L):
    s = pd.read_csv(f"{d}/sessions.csv")
    p = pd.read_csv(f"{d}/plan.csv")[["sid", "tool_time_total_s"]]
    s = s.merge(p, on="sid", how="left")
    cumL = np.cumsum(L)
    s["ref"] = s.tool_time_total_s + cumL[s.n_turns.clip(upper=KMAX).values]
    s["elapsed"] = s.t_end - s.arrival_s
    s["slowdown"] = s.elapsed / s.ref
    s["ok"] = (s.status == "completed") & (s.slowdown <= 4.0)
    return s


def goodput(s):
    out = {}
    b = s[s.origin == "base"]
    for w, (kind, lo, hi) in WINDOWS.items():
        if kind == "arr":
            c = b[(b.arrival_s >= lo) & (b.arrival_s < hi)]
            out[f"G_{w}"] = c.ok.sum() / ((hi - lo) / 3600.0)
            out[f"n_{w}"] = len(c)
            out[f"compl_{w}"] = float((c.status == "completed").mean()) if len(c) else np.nan
            cc = c[c.status == "completed"]
            out[f"medslow_{w}"] = float(cc.slowdown.median()) if len(cc) else np.nan
        else:
            c = b[(b.status == "completed") & (b.t_end >= lo) & (b.t_end < hi)]
            out[f"G_{w}"] = c.ok.sum() / ((hi - lo) / 3600.0)
            out[f"n_{w}"] = len(c)
    return out


if __name__ == "__main__":
    inv = pd.read_csv(f"{S}/inventory.csv")
    inv = inv[~inv.label.str.contains("smoke|toolslow|lpminf|-r0$|lpm-r1", regex=True)]
    inv = inv[~inv.pulled.str.startswith("r7_native_grid")]
    inv["cell"] = inv.apply(cell_key, axis=1)
    refs = {}
    rows = []
    for stat in ("min", "q05"):
        for cell, g in inv.groupby("cell"):
            nb = g[g.arm == "noburst"]
            if len(nb) == 0:
                # BASIN / rescue / shed cells: use the base cell's NOBURST runs
                nb = inv[(inv.cell == cell) & (inv.arm == "noburst")]
            if len(nb) == 0:
                print("no NOBURST for", cell, file=sys.stderr)
                continue
            L, info = unloaded_ref(nb.run_dir.tolist(), stat)
            refs[(stat, cell)] = L
            info.update(stat=stat, cell=cell, n_noburst_runs=len(nb))
            rows.append(info)
    pd.DataFrame(rows).to_csv(f"{S}/d2_unloaded_ref.csv", index=False)
    out = []
    for _, r in inv.iterrows():
        for stat in ("min", "q05"):
            L = refs.get((stat, r.cell))
            if L is None:
                continue
            s = session_table(r.run_dir, L)
            gp = goodput(s)
            gp.update(stat=stat, cell=r.cell, label=r.label, arm=r.arm, rate_mult=r.rate_mult, seed=r.seed,
                      burst_n=r.burst_n, run_dir=r.run_dir, job=r.job, trap_v2_state=r.trap_v2_state, pulled=r.pulled)
            out.append(gp)
    out = pd.DataFrame(out)
    out.to_csv(f"{S}/d2_runs.csv", index=False)
    print(out.groupby(["stat", "cell", "label", "arm", "rate_mult"]).size())
