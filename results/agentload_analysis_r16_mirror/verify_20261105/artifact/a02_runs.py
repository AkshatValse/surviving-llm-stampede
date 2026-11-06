"""Artifact check of the r16 MIRROR runs, from the raw run files only (requests.csv, sessions.csv, metrics.csv, meta.json).

Usage: python -I a02_runs.py WORKTREE OUTDIR
Prints per-run window tables and writes per-run bins to OUTDIR.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

WT = sys.argv[1]
OUT = sys.argv[2]
PULL = os.path.join(WT, "results/nova/r16_mirror_1726405x_pulled_20261105-1722/results/agentload_e2_burst")
RUNS = ["20261105-145227", "20261105-145244-2", "20261105-145240",      # 1.65 burst s0 s1 s2
        "20261105-145244-1", "20261105-145246", "20261105-145244",      # 1.35 burst s0 s1 s2
        "20261105-145242", "20261105-145247", "20261105-145248"]        # 1.65 noburst s0 s1 s2
LAM_REF = 0.07153402100919228
E0A_UNC = 12120.33426835178
WINDOWS = {"pre[0,1200)": (0, 1200), "post[1200,2400)": (1200, 2400), "blackout[2400,3600)": (2400, 3600),
           "mid[3600,6600)": (3600, 6600), "late[6600,8700)": (6600, 8700), "w[5700,8700)": (5700, 8700)}


def load(d):
    meta = json.load(open(os.path.join(d, "meta.json")))
    req = pd.read_csv(os.path.join(d, "requests.csv"),
                      usecols=["req_id", "sid", "origin", "turn", "n_turns", "t_planned", "t_send", "t_headers", "t_complete",
                               "latency_s", "sched_delay_s", "status", "http_status", "error", "prompt_tokens_client",
                               "prompt_tokens", "completion_tokens", "cached_tokens", "t_ready", "pause_s"])
    ses = pd.read_csv(os.path.join(d, "sessions.csv"))
    return meta, req, ses


def window_table(req, ses, meta):
    ok = req[req.status == "ok"].copy()
    ok["unc"] = ok.prompt_tokens - ok.cached_tokens
    ok["hit"] = (ok.cached_tokens / ok.prompt_tokens) > 0.5
    comp = ses[ses.status == "completed"]
    rows = []
    for name, (a, b) in WINDOWS.items():
        L = b - a
        w = ok[(ok.t_complete >= a) & (ok.t_complete < b)]
        ws = req[(req.t_send >= a) & (req.t_send < b)]
        c = comp[(comp.t_end >= a) & (comp.t_end < b)]
        rows.append(dict(
            window=name,
            turns_per_s=len(w) / L,
            unc_tok_per_s=w.unc.sum() / L,
            unc_over_e0a=w.unc.sum() / L / E0A_UNC,
            prompt_tok_per_s=w.prompt_tokens.sum() / L,
            mean_prompt=w.prompt_tokens.mean() if len(w) else np.nan,
            hit_frac=w.hit.mean() if len(w) else np.nan,
            tok_hit=(w.cached_tokens.sum() / w.prompt_tokens.sum()) if len(w) else np.nan,
            sess_per_s_over_ref=len(c) / L / LAM_REF,
            n_sess=len(c),
            lat_med=w.latency_s.median() if len(w) else np.nan,
            lat_p90=w.latency_s.quantile(0.9) if len(w) else np.nan,
            lat_max=w.latency_s.max() if len(w) else np.nan,
            sched_delay_max=ws.sched_delay_s.max() if len(ws) else np.nan,
            sched_delay_p99=ws.sched_delay_s.quantile(0.99) if len(ws) else np.nan,
        ))
    return pd.DataFrame(rows)


def gaps(req, a=0.0, b=8700.0):
    ok = req[(req.status == "ok") & (req.t_complete >= a) & (req.t_complete < b)].t_complete.sort_values().to_numpy()
    if len(ok) < 2:
        return np.nan, []
    g = np.diff(ok)
    big = [(float(ok[i]), float(g[i])) for i in np.where(g > 30)[0]]
    return float(g.max()), big


def inflight_grid(req, step=1.0, T=8700.0):
    t = np.arange(0, T, step)
    s = req.t_send.to_numpy()
    e = req.t_complete.to_numpy().copy()
    e[np.isnan(e)] = T + 1
    starts = np.searchsorted(np.sort(s), t, side="right")
    ends = np.searchsorted(np.sort(e), t, side="right")
    return t, starts - ends


def metrics(d):
    m = pd.read_csv(os.path.join(d, "metrics.csv"), keep_default_na=False)
    want = {"sglang:num_running_reqs", "sglang:num_queue_reqs", "sglang:token_usage", "sglang:num_retracted_reqs",
            "sglang:num_paused_reqs", "sglang:scheduler_idle_seconds_total", "sglang:utilization", "sglang:gen_throughput",
            "sglang:prefill_effective_tokens_total", "sglang:realtime_tokens_total", "sglang:num_requests_total",
            "sglang:http_requests_active", "agentload:inflight_requests", "agentload:sessions_in_system",
            "sglang:scheduler_process_cpu_seconds_total", "sglang:cache_hit_rate", "agentload:scrape_latency_s",
            "sglang:queue_time_seconds_sum", "sglang:queue_time_seconds_count", "sglang:kv_evictable_tokens",
            "sglang:kv_used_tokens", "sglang:fwd_occupancy"}
    m = m[m.name.isin(want)].copy()
    m["value"] = pd.to_numeric(m.value, errors="coerce")
    key = m.name.copy()
    sel = m.name.isin(["sglang:prefill_effective_tokens_total", "sglang:realtime_tokens_total"])
    key[sel] = m.name[sel] + "|" + m["labels"][sel].str.extract(r'mode="([^"]+)"')[0]
    sel = m.name == "sglang:http_requests_active"
    key[sel] = m.name[sel] + "|" + m["labels"][sel].str.extract(r'endpoint="([^"]+)"')[0]
    m["key"] = key
    wide = m.pivot_table(index="t_s", columns="key", values="value", aggfunc="sum")
    return wide


def metric_windows(wide):
    rows = []
    t = wide.index.to_numpy()
    for name, (a, b) in WINDOWS.items():
        sel = (t >= a) & (t < b)
        w = wide[sel]
        r = dict(window=name)
        for col in ["sglang:num_running_reqs", "sglang:num_queue_reqs", "sglang:token_usage", "sglang:num_retracted_reqs",
                    "sglang:num_paused_reqs", "sglang:utilization", "agentload:inflight_requests", "sglang:fwd_occupancy"]:
            if col in w:
                r[col.split(":")[1] + "_mean"] = w[col].mean()
                r[col.split(":")[1] + "_min"] = w[col].min()
                r[col.split(":")[1] + "_max"] = w[col].max()
        # counters -> rates over the window (last - first) / dt
        tw = w.index.to_numpy()
        if len(tw) >= 2:
            dt = tw[-1] - tw[0]
            for col in ["sglang:scheduler_idle_seconds_total", "sglang:prefill_effective_tokens_total|input",
                        "sglang:prefill_effective_tokens_total|device_hit", "sglang:realtime_tokens_total|prefill_compute",
                        "sglang:realtime_tokens_total|prefill_cache", "sglang:realtime_tokens_total|decode",
                        "sglang:num_requests_total", "sglang:scheduler_process_cpu_seconds_total"]:
                if col in w:
                    r["rate:" + col.split(":")[1]] = (w[col].iloc[-1] - w[col].iloc[0]) / dt
            if "sglang:queue_time_seconds_sum" in w:
                dq = w["sglang:queue_time_seconds_sum"].iloc[-1] - w["sglang:queue_time_seconds_sum"].iloc[0]
                dn = w["sglang:queue_time_seconds_count"].iloc[-1] - w["sglang:queue_time_seconds_count"].iloc[0]
                r["queue_time_mean_s"] = dq / dn if dn > 0 else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.float_format", lambda x: f"{x:.4g}")
    allwin, allmet, summ = [], [], []
    for r in RUNS:
        d = os.path.join(PULL, r)
        meta, req, ses = load(d)
        arm = meta["arm"]
        rate = round(meta["resolved_rate_sessions_per_s"] / LAM_REF, 2)
        seed = meta["seeds"][0]
        tag = f"{rate}x-{arm}-s{seed}"
        wt = window_table(req, ses, meta)
        wt.insert(0, "run", tag)
        allwin.append(wt)
        gmax_all, big_all = gaps(req)
        gmax_post, big_post = gaps(req, 1200, 8700)
        t, inf = inflight_grid(req)
        canc = req[req.status == "cancelled"]
        okr = req[req.status == "ok"]
        # requests completing after cancellation time / sanity
        s = dict(run=tag, dir=r, job=meta["slurm_env"]["SLURM_JOB_ID"], node=meta["hostname"],
                 n_req=len(req), n_ok=len(okr), n_cancel=len(canc),
                 cancel_tsend_min=canc.t_send.min() if len(canc) else np.nan,
                 cancel_tcomplete_set=sorted(set(np.round(canc.t_complete.dropna(), 0)))[:5] if len(canc) else [],
                 http_non200=int(((okr.http_status != 200)).sum()),
                 prompt_mismatch=int((okr.prompt_tokens != okr.prompt_tokens_client).sum()),
                 completion_not_100=int((okr.completion_tokens != 100).sum()),
                 max_gap_all_s=gmax_all, max_gap_post_s=gmax_post, n_gaps_gt30_post=len(big_post),
                 gaps_gt30_post=big_post[:10],
                 inflight_max=int(inf.max()), inflight_mean_blackout=float(inf[(t >= 2400) & (t < 3600)].mean()),
                 inflight_min_blackout=int(inf[(t >= 2400) & (t < 3600)].min()),
                 latency_max_all=float(okr.latency_s.max()),
                 sched_delay_max=float(req.sched_delay_s.max()), sched_delay_p999=float(req.sched_delay_s.quantile(0.999)),
                 sessions_failed=int((ses.status == "failed").sum()))
        summ.append(s)
        wide = metrics(d)
        mw = metric_windows(wide)
        mw.insert(0, "run", tag)
        allmet.append(mw)
        # 60-s bins for later plotting/inspection
        okc = okr.copy()
        okc["unc"] = okc.prompt_tokens - okc.cached_tokens
        okc["hit"] = (okc.cached_tokens / okc.prompt_tokens) > 0.5
        okc["bin60"] = (okc.t_complete // 60 * 60).astype(int)
        b = okc.groupby("bin60").agg(turns=("req_id", "size"), unc=("unc", "sum"), hit=("hit", "mean"),
                                     lat_med=("latency_s", "median"))
        comp = ses[ses.status == "completed"].copy()
        comp["bin60"] = (comp.t_end // 60 * 60).astype(int)
        b["sess"] = comp.groupby("bin60").size()
        b = b.reindex(range(0, 8700, 60)).fillna({"turns": 0, "unc": 0, "sess": 0})
        b["turns_per_s"] = b.turns / 60
        b["unc_per_s"] = b.unc / 60
        b.to_csv(os.path.join(OUT, f"bins60_{tag}.csv"))
        wide.to_csv(os.path.join(OUT, f"metrics_wide_{tag}.csv"))
        print(f"done {tag}", flush=True)
    W = pd.concat(allwin)
    M = pd.concat(allmet)
    S = pd.DataFrame(summ)
    W.to_csv(os.path.join(OUT, "windows_requests.csv"), index=False)
    M.to_csv(os.path.join(OUT, "windows_metrics.csv"), index=False)
    S.to_csv(os.path.join(OUT, "run_summary.csv"), index=False)
    print("\n=== per-run sanity")
    print(S.drop(columns=["dir"]).to_string(index=False))
    print("\n=== request/session windows (by t_complete / t_end)")
    print(W.to_string(index=False))
    print("\n=== engine metrics windows")
    print(M.to_string(index=False))


if __name__ == "__main__":
    main()
