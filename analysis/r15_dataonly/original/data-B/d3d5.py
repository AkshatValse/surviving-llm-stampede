"""data-B D3 (noise-induced escape) and D5 (trap lifetime) tables from runs.csv / bins.csv.

Rolling window: 300 s (3 x 100 s bins) of frac_turns_cached_gt50 over turns > 1 by completion.
COLLAPSE (G->B) at tau: first bin start t >= WARM with rolling hf <= 0.2, provided the run had
  rolling hf >= 0.6 somewhere in [WARM, t) and no later 300 s window has hf >= 0.5.
  (tau reported as the START of the 100 s bin that closes the first <=0.2 window, minus 200 s,
   i.e. the start of that 300 s window.)
EXCURSION: a rolling-hf minimum < 0.5 between two >= 0.8 windows (a dip that came back).
TRAP (D5): after the trigger time, first window with rolling hf <= 0.2; trapped time counts up to
  run end or the intervention time (rescue gate t_on, SHED ramp to 0); ESCAPE = any later 300 s
  window with hf >= 0.5 before that cut-off.
"""
import os, json, math
import numpy as np, pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
WARM = 600.0
runs = pd.read_csv(os.path.join(OUT, "runs.csv"))
bins = pd.read_csv(os.path.join(OUT, "bins.csv"))
TH = {}
for name, f in [("a100_300k", "a100_300k.json"), ("a100_150k", "a100_pool150k.json"),
                ("a100_600k", "a100_pool600k.json"), ("a100_native", "a100_native.json"),
                ("h200_300k", "h200_300k.json"), ("llama_300k", "llama31_8b_300k.json"),
                ("vllm_300k", "vllm_300k.json")]:
    e = json.load(open(os.path.join(r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\arxiv\results\theory\merged", f)))["from_empty_edge"]
    TH[name] = e


def cellkey(r):
    m = str(r.model); hw = str(r.hardware); lab = str(r.engine_label); pool = r.pool
    if "llama" in m.lower():
        return "llama_300k"
    if "vllm" in lab:
        return "vllm_300k"
    if "H200" in hw:
        return "h200_300k" if pool and pool < 4e5 else "h200_600k"
    if pool and pool > 9e5:
        return "a100_native"
    if pool and pool < 2e5:
        return "a100_150k"
    if pool and 5e5 < pool < 7e5:
        return "a100_600k"
    return "a100_300k"


def f2_T(cell, mult):
    e = TH.get(cell)
    if not e:
        return None, None
    pf = {float(k): v for k, v in e["p_escape_fine"].items()}
    ks = sorted(pf)
    k = min(ks, key=lambda z: abs(z - mult))
    p = pf[k]
    T = (-e["horizon_s"] / math.log(1 - p)) if 0 < p < 1 else (math.inf if p <= 0 else 0.0)
    return T, e.get("fluid_upper_edge_mult")


def rolling(b):
    n = b.n.rolling(3, min_periods=3).sum().values
    h = b.hits.rolling(3, min_periods=3).sum().values
    hf = np.where(n >= 5, h / np.clip(n, 1, None), np.nan)
    return hf, b.t0.values - 200.0  # window start


def realized_mult(d, r, t_lo, t_hi):
    p = pd.read_csv(os.path.join(r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\arxiv\results\nova", d, "plan.csv"),
                    usecols=["origin", "arrival_s"])
    p = p[p.origin == "base"] if "base" in set(p.origin) else p
    k = ((p.arrival_s >= t_lo) & (p.arrival_s < t_hi)).sum()
    return k / (t_hi - t_lo) / r.lambda_ref


rows3, rows5 = [], []
for _, r in runs.iterrows():
    b = bins[bins.run == r.run].sort_values("t0").reset_index(drop=True)
    hf, ws = rolling(b)
    t_end = float(b.t0.max() + 100)
    open_const = r.arr_kind == "constant" and r.stage in ("agentload_e0_cap", "agentload_e2_burst")
    burst = isinstance(r.burst, str) and len(r.burst) > 2
    wl = json.loads(r.workload_extra) if isinstance(r.workload_extra, str) else {}
    ax = json.loads(r.arrivals_extra) if isinstance(r.arrivals_extra, str) else {}
    gate = json.loads(r.gate) if isinstance(r.gate, str) and r.gate else {}
    trigger = None
    if burst:
        trigger = float(r.t_burst if not pd.isna(r.t_burst) else json.loads(r.burst)["t_s"])
    elif "tool_slowdown" in wl:
        trigger = float(wl["tool_slowdown"]["t_s"])
    cell = cellkey(r)
    valid = ~np.isnan(hf)
    # ---------- D3: no trigger, open constant arrivals, no cap
    if open_const and trigger is None and not gate.get("n_cap"):
        good_seen = False; tau = None
        for i in range(len(hf)):
            if not valid[i] or ws[i] < WARM:
                if valid[i] and hf[i] >= 0.6:
                    good_seen = True
                continue
            if hf[i] >= 0.6:
                good_seen = True
            if good_seen and hf[i] <= 0.2:
                later = hf[i + 1:]
                if not np.any(later[~np.isnan(later)] >= 0.5):
                    tau = float(ws[i]); break
        # excursions: dips below 0.5 that return to >= 0.8
        exc = []
        i = 0
        while i < len(hf):
            if valid[i] and hf[i] < 0.5 and ws[i] >= 0:
                j = i
                while j < len(hf) and (not valid[j] or hf[j] < 0.8):
                    j += 1
                seg = hf[i:j]
                if j < len(hf) and (tau is None or ws[i] < tau):
                    exc.append((float(ws[i]), float(np.nanmin(seg)), float(ws[j] - ws[i])))
                i = j + 1
            else:
                i += 1
        T_f2, upper = f2_T(cell, float(r.rate_mult))
        rm = realized_mult(r.run, r, 0, min(t_end, 3000.0))
        rm_full = realized_mult(r.run, r, 0, t_end)
        rows3.append(dict(run=r.run, cell=cell, stage=r.stage, arm=r.arm, job=r.job, seed=r.seed,
                          mult=r.rate_mult, realized_0_3000=round(rm, 3), realized_full=round(rm_full, 3),
                          t_end=t_end, collapsed=tau is not None, tau=tau,
                          exposure=(tau if tau is not None else t_end) - WARM,
                          n_exc=len(exc), exc=";".join(f"{a:.0f}(min{m:.2f},{d:.0f}s)" for a, m, d in exc),
                          F2_T=None if T_f2 is None else (T_f2 if math.isinf(T_f2) else round(T_f2)), fluid_upper=upper))
    # ---------- D5: trapped runs
    t_trig = trigger
    if t_trig is None and open_const and not gate.get("n_cap"):
        t_trig = WARM  # from-empty collapses: trap after spontaneous collapse
    if t_trig is not None and r.arr_kind in ("constant", "ramp"):
        cut = t_end; cut_reason = "end"
        if gate.get("mode") == "rescue":
            cut = float(gate["t_on_s"]); cut_reason = "rescue_on"
        elif gate.get("n_cap"):
            continue
        if "ramp" in ax:
            # first knot where multiplier drops to 0
            for (t, m) in ax["ramp"]:
                if m == 0:
                    cut = float(t); cut_reason = "shed_stop"; break
        tt = None
        for i in range(len(hf)):
            if valid[i] and ws[i] >= t_trig and hf[i] <= 0.2 and b.t0.values[i] + 100 <= cut:
                tt = float(ws[i]); break
        if tt is None:
            continue
        esc = None
        for i in range(len(hf)):
            if valid[i] and ws[i] > tt and b.t0.values[i] + 100 <= cut and hf[i] >= 0.5:
                esc = float(ws[i]); break
        # backlog: sessions in system at trap entry and at cut
        def act_at(t):
            k = b.index[b.t0 <= t - 100]
            return int(b.active.iloc[k[-1]]) if len(k) else None
        rows5.append(dict(run=r.run, cell=cell, label=r.engine_label, arm=r.arm, seed=r.seed,
                          mult=r.rate_mult, trigger=("burst" if burst else ("toolslow" if "tool_slowdown" in wl else "spontaneous")),
                          burst_n=(json.loads(r.burst)["n"] if burst else None),
                          t_trap=tt, cut=cut, cut_reason=cut_reason, trapped_s=(esc if esc else cut) - tt,
                          escaped=esc is not None, t_escape=esc,
                          active_at_trap=act_at(tt + 300), active_at_cut=act_at(cut - 100), hf_last1000=float(np.nansum(b.hits[(b.t0>=cut-1000)&(b.t0<cut)])/max(1,b.n[(b.t0>=cut-1000)&(b.t0<cut)].sum())),
                          coarse_after=None))

D3 = pd.DataFrame(rows3); D5 = pd.DataFrame(rows5)
D3.to_csv(os.path.join(OUT, "d3_runs.csv"), index=False)
D5.to_csv(os.path.join(OUT, "d5_trapped.csv"), index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 90)
print(D3.sort_values(["cell", "mult", "seed"]).drop(columns=["run"]).to_string())
print()
g = D3.groupby(["cell", "mult"]).agg(runs=("tau", "size"), events=("collapsed", "sum"), exposure=("exposure", "sum"),
                                       taus=("tau", lambda s: ",".join(str(int(x)) for x in s.dropna())),
                                       F2_T=("F2_T", "first"), upper=("fluid_upper", "first"),
                                       n_exc=("n_exc", "sum"), realized=("realized_full", lambda s: ",".join(f"{x:.2f}" for x in s)))
print(g.to_string())
print()
D5["sched"] = np.where(D5.label.str.contains("lpm"), "LPM", "FCFS")
print(D5.sort_values(["sched", "cell", "mult", "trigger"]).drop(columns=["run", "coarse_after"]).to_string())
print()
print(D5.groupby(["sched", "trigger", "cut_reason"]).agg(runs=("trapped_s", "size"), escaped=("escaped", "sum"),
                                                          trapped_s=("trapped_s", "sum")).to_string())
