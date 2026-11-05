"""D1: does the trap outlive every trigger session?  Read-only over results/nova (run from the worktree root).

For every stuck run (registered trap_v2 hit_eval < 0.2 on [5700, 8700) s) of the BURST type, plus SHED t600 and TOOLSLOW d30 s2:
  * trigger sessions: origin == 'burst' (sessions.csv); for TOOLSLOW, the sessions with a slowed tool call (tool_calls.csv add_s > 0)
  * t_last_trig_end: latest t_end of a COMPLETED trigger session; n_trig_left_end: trigger sessions cancelled at run end
  * n_trig_active(t): trigger sessions with arrival_s <= t < t_end (cancelled ones end at the run end), t = 4500, 5700, 7200
  * pop_eval: time-average over [5700, 8700) of sessions in the system (arrived, not ended; includes gate waiters);
    trig_share_eval: the trigger sessions' share of that average; inflight_eval: time-average of requests in flight
  * hit_eval: fraction of ok turns completing in [5700, 8700) with cached/prompt > 0.5 (same as trap_v2 frac_turns_cached_gt50)
  * trig_req_share_eval: share of ok requests completed in [5700, 8700) that belong to trigger sessions
  * hit_after_trig: hit fraction of ok turns completing after the LAST trigger session left (completed or cancelled at end);
    t_free: the time after which no trigger session is in the system (NaN if one is still there at the run end)
  * hit_base_after_lastend: hit fraction of base turns completing after t_last_trig_end (completed trigger sessions only)
"""
import os, sys
import numpy as np
import pandas as pd

S = os.path.dirname(os.path.abspath(__file__))
E0, E1 = 5700.0, 8700.0


def hitfrac(req, lo, hi, mask=None):
    r = req[(req.status == "ok") & (req.t_complete >= lo) & (req.t_complete < hi)]
    if mask is not None:
        r = r[mask.reindex(r.index, fill_value=False)]
    if len(r) == 0:
        return np.nan, 0
    return float(((r.cached_tokens.fillna(0) / r.prompt_tokens) > 0.5).mean()), len(r)


def step_mean(starts, ends, lo, hi):
    """time-average over [lo, hi) of #intervals [s, e) covering t"""
    s = np.clip(starts, lo, hi)
    e = np.clip(ends, lo, hi)
    return float(np.sum(np.maximum(e - s, 0)) / (hi - lo))


def run_metrics(d, trig_kind):
    ses = pd.read_csv(f"{d}/sessions.csv")
    req = pd.read_csv(f"{d}/requests.csv")
    t_run_end = float(max(ses.t_end.max(), req.t_complete.max()))
    ses["t_end_eff"] = ses.t_end.fillna(t_run_end)
    if trig_kind == "toolslow":
        tc = pd.read_csv(f"{d}/tool_calls.csv")
        trig_sids = set(tc.loc[tc.add_s > 0, "sid"])
        ses["trig"] = ses.sid.isin(trig_sids)
    else:
        ses["trig"] = ses.origin == "burst"
    T = ses[ses.trig]
    comp = T[T.status == "completed"]
    out = dict(n_trig=len(T), n_trig_completed=len(comp), n_trig_left_end=int((T.status != "completed").sum()),
               t_last_trig_end=float(comp.t_end.max()) if len(comp) else np.nan)
    for t in (4500, 5700, 7200):
        out[f"n_trig_active_{t}"] = int(((T.arrival_s <= t) & (T.t_end_eff > t)).sum())
        out[f"n_all_active_{t}"] = int(((ses.arrival_s <= t) & (ses.t_end_eff > t)).sum())
    out["pop_eval"] = step_mean(ses.arrival_s.values, ses.t_end_eff.values, E0, E1)
    out["pop_trig_eval"] = step_mean(T.arrival_s.values, T.t_end_eff.values, E0, E1)
    out["trig_share_eval"] = out["pop_trig_eval"] / out["pop_eval"] if out["pop_eval"] else np.nan
    out["pop_start_eval"] = int(((ses.arrival_s <= E0) & (ses.t_end_eff > E0)).sum())
    out["pop_end"] = int(((ses.arrival_s <= E1 - 1) & (ses.t_end_eff > E1 - 1)).sum())
    out["inflight_eval"] = step_mean(req.t_send.values, req.t_complete.fillna(t_run_end).values, E0, E1)
    out["hit_eval"], out["n_turns_eval"] = hitfrac(req, E0, E1)
    trig_sid = set(T.sid)
    ok_eval = req[(req.status == "ok") & (req.t_complete >= E0) & (req.t_complete < E1)]
    out["trig_req_share_eval"] = float(ok_eval.sid.isin(trig_sid).mean()) if len(ok_eval) else np.nan
    # time after which no trigger session is present
    t_free = float(T.t_end_eff.max()) if len(T) else np.nan
    if out["n_trig_left_end"] > 0:
        t_free = np.nan
    out["t_free"] = t_free
    if np.isfinite(t_free):
        out["hit_after_trig"], out["n_turns_after_trig"] = hitfrac(req, t_free, E1 + 1)
        out["s_trap_after_trig"] = t_run_end - t_free
    else:
        out["hit_after_trig"], out["n_turns_after_trig"], out["s_trap_after_trig"] = np.nan, 0, np.nan
    if np.isfinite(out["t_last_trig_end"]):
        base_mask = ~req.sid.isin(trig_sid)
        out["hit_base_after_lastend"], out["n_base_turns_after_lastend"] = hitfrac(req, out["t_last_trig_end"], E1 + 1, base_mask)
    # hits of base turns in eval window (base only), and the 10 min before the run end
    out["hit_base_eval"], _ = hitfrac(req, E0, E1, ~req.sid.isin(trig_sid))
    out["hit_last600"], _ = hitfrac(req, E1 - 600, E1 + 1)
    out["t_run_end"] = t_run_end
    return out


def group_of(r):
    p, lab = r.pulled, r.label
    if p.startswith("e2_170933xx"):
        return "REG sglang-300k A100"
    if p.startswith("e2_native_vllm") and lab == "sglang-fcfs-r1-native":
        return "REG sglang-native-956k A100"
    if p.startswith("e2_native_vllm") and lab == "vllm-fcfs":
        return "GRID vllm (pre-registration, e2_native_vllm_burst)"
    if p.startswith("e2_vllm_1716612x"):
        return "REG vllm-0.32 A100"
    if p.startswith("h200p600k"):
        return "REG sglang-600k H200"
    if p.startswith("llama31"):
        return "REG llama31-8B A100"
    if p.startswith("b1_") or p.startswith("b2_"):
        return f"REG BASIN burst_n={int(r.burst_n)}"
    if "shed" in lab:
        return "REG SHED " + lab.split("-")[-1]
    if "toolslow" in lab:
        return "REG TOOLSLOW " + lab.split("-")[-1]
    if p.startswith("r7_native_grid"):
        return f"GRID r7 {lab}"
    return f"OTHER {p} {lab}"


if __name__ == "__main__":
    inv = pd.read_csv(f"{S}/inventory.csv")
    sel = inv[(inv.v_hit_eval < 0.2) & ((inv.arm == "burst") | inv.label.str.contains("toolslow"))].copy()
    rows = []
    for _, r in sel.iterrows():
        kind = "toolslow" if "toolslow" in r.label else "burst"
        m = run_metrics(r.run_dir, kind)
        m.update(group=group_of(r), run_dir=r.run_dir, label=r.label, seed=r.seed, rate_mult=r.rate_mult, burst_n=r.burst_n,
                 job=r.job, trap_v2_state=r.trap_v2_state, v_hit_eval=r.v_hit_eval)
        rows.append(m)
        print(r.run_dir, kind, m["hit_eval"], m["t_last_trig_end"], m["n_trig_left_end"], file=sys.stderr)
    out = pd.DataFrame(rows)
    out.to_csv(f"{S}/d1_runs.csv", index=False)
