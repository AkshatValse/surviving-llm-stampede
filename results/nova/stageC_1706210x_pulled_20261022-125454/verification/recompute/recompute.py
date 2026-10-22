"""Independent recomputation of Stage C closed-population metrics.

Reads only raw requests.csv / sessions.csv / meta.json (and harness mu_points.csv for
comparison). Does not import the harness packages. Writes outputs next to this script.
"""
from __future__ import annotations

import json
import glob
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = "/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454"
RUNS = os.path.join(ROOT, "agentload_c_closed")
HARNESS = os.path.join(ROOT, "analysis_local/agentload_analysis_closed/20261022-125619/mu_points.csv")
OUT = os.path.dirname(os.path.abspath(__file__))

W0, W1 = 900.0, 2700.0
NBINS = 6
BIN = (W1 - W0) / NBINS


def expected_turns(mean_turns: float, max_turns: int) -> tuple[float, float, np.ndarray]:
    """T = min(G, max_turns), G ~ Geometric(p=1/mean) on {1,2,...}.

    Returns E[T], count-biased mean turn index E[T(T+1)/2]/E[T], and P(T>=k), k=1..max.
    """
    q = 1.0 - 1.0 / mean_turns
    k = np.arange(1, max_turns + 1)
    surv = q ** (k - 1)  # P(T >= k)
    ET = surv.sum()
    mean_k = (k * surv).sum() / ET
    return ET, mean_k, surv


def load(d: str):
    m = json.load(open(os.path.join(d, "meta.json")))
    rq = pd.read_csv(os.path.join(d, "requests.csv"))
    ss = pd.read_csv(os.path.join(d, "sessions.csv"))
    n = int([a for a in m["argv"] if a.startswith("arrivals.closed_n=")][0].split("=")[1])
    return m, rq, ss, n


def window_metrics(rq_ok: pd.DataFrame, ss_done: pd.DataFrame, a: float, b: float, ET: float) -> dict:
    t = rq_ok[(rq_ok.t_complete >= a) & (rq_ok.t_complete < b)]
    s = ss_done[(ss_done.t_end >= a) & (ss_done.t_end < b)]
    dur = b - a
    hit = (t.cached_tokens / t.prompt_tokens) > 0.5
    fu = t.turn >= 2
    return dict(
        sessions=len(s),
        turns=len(t),
        mu_sessions=len(s) / dur,
        turns_per_s=len(t) / dur,
        mu_turns_based=len(t) / dur / ET,
        hit_frac=hit.mean() if len(t) else np.nan,
        hit_frac_followup=hit[fu].mean() if fu.any() else np.nan,
        cached_frac_tok=t.cached_tokens.sum() / t.prompt_tokens.sum() if len(t) else np.nan,
        mean_prompt=t.prompt_tokens.mean(),
        mean_turn=t.turn.mean(),
        mean_T_completed_sessions=s.n_turns.mean() if len(s) else np.nan,
    )


def inflight_snapshot(rq: pd.DataFrame, t: float) -> dict:
    """Requests in flight (sent, not completed) at time t: turn index, prompt length."""
    tc = rq.t_complete.fillna(np.inf)
    f = rq[(rq.t_send <= t) & (tc > t)]
    return dict(n_inflight=len(f), mean_turn=f.turn.mean(), mean_prompt=f.prompt_tokens_client.mean())


def main() -> None:
    harness = pd.read_csv(HARNESS)
    harness["ts"] = harness.run_dir.str.rsplit("/", n=1).str[-1]
    rows, bins_rows, stat_rows, misc_rows, snap_rows = [], [], [], [], []
    for d in sorted(glob.glob(RUNS + "/*/")):
        ts = os.path.basename(d.rstrip("/"))
        m, rq, ss, n = load(d)
        wl = m.get("expected_turns_per_session")
        ET, mean_k, surv = expected_turns(15.0, 60)
        assert abs(ET - wl) < 1e-9, (ET, wl)
        pol = "LPM" if "lpm" in m["engine_label"] else "FCFS"
        t_end = m["outcome"]["t_end_s"]
        rq_ok = rq[rq.status == "ok"]
        ss_done = ss[ss.status == "completed"]
        # sanity: prompt length formula and session end == last-turn completion
        k = rq_ok.turn
        formula_bad = int((rq_ok.prompt_tokens != 2000 + 650 * (k - 1)).sum())
        last = rq_ok.sort_values("turn").groupby("sid").tail(1).set_index("sid")
        sd = ss_done.set_index("sid")
        common = sd.index.intersection(last.index)
        end_mismatch = float(np.nanmax(np.abs(sd.loc[common, "t_end"] - last.loc[common, "t_complete"]))) if len(common) else np.nan
        pt_client_mismatch = int((rq_ok.prompt_tokens != rq_ok.prompt_tokens_client).sum())

        main_w = window_metrics(rq_ok, ss_done, W0, W1, ET)
        alt_w = window_metrics(rq_ok, ss_done, W0, t_end + 1e-9, ET)  # harness-like [900, t_end]
        h = harness[harness.ts == ts].iloc[0]
        meas = h.measure_s
        row = dict(ts=ts, job=m["slurm_env"]["SLURM_JOB_ID"], pol=pol, n=n, **main_w)
        row["alt_sessions"] = alt_w["sessions"]
        row["alt_turns"] = alt_w["turns"]
        row["mu_sessions_harnessdiv"] = alt_w["sessions"] / meas
        row["mu_turns_harnessdiv"] = alt_w["turns"] / meas / ET
        for c in ["mu_sessions", "mu_turns_based", "turns_per_s", "hit_frac_turns", "hit_frac_followup", "cached_frac_tokens", "sessions_completed", "turns_completed"]:
            row["H_" + c] = h[c]
        row["formula_bad"] = formula_bad
        row["end_mismatch_s"] = end_mismatch
        row["pt_client_mismatch"] = pt_client_mismatch
        rows.append(row)

        # bins
        b_vals = []
        for i in range(NBINS):
            a = W0 + i * BIN
            bm = window_metrics(rq_ok, ss_done, a, a + BIN, ET)
            snap = inflight_snapshot(rq, a + BIN / 2)
            bm.update(ts=ts, pol=pol, n=n, bin=i, inflight_mean_turn_mid=snap["mean_turn"], inflight_mean_prompt_mid=snap["mean_prompt"], n_inflight_mid=snap["n_inflight"])
            bins_rows.append(bm)
            b_vals.append(bm)
        bdf = pd.DataFrame(b_vals)
        st = dict(ts=ts, pol=pol, n=n)
        idx = np.arange(NBINS)
        for c in ["mu_sessions", "turns_per_s", "hit_frac", "mean_prompt", "mean_turn"]:
            v = bdf[c].to_numpy(float)
            if np.all(np.isfinite(v)) and np.nanstd(v) > 0:
                rho = stats.spearmanr(idx, v).statistic
            else:
                rho = np.nan
            fl = (v[-1] - v[0]) / v[0] if np.isfinite(v[0]) and v[0] != 0 else np.nan
            st[c + "_rho"] = rho
            st[c + "_firstlast"] = fl
        for c in ["mu_turns_based", "hit_frac", "mu_sessions"]:
            v = bdf[c].to_numpy(float)
            st[c + "_bm_mean"] = v.mean()
            st[c + "_bm_se"] = v.std(ddof=1) / np.sqrt(NBINS)
            st[c + "_lag1"] = np.corrcoef(v[:-1], v[1:])[0, 1] if np.std(v) > 0 else np.nan
        stat_rows.append(st)

        # misc: statuses, latency
        win = rq_ok[(rq_ok.t_complete >= W0) & (rq_ok.t_complete < W1)]
        lat = win.latency_s
        canc = rq[rq.status == "cancelled"]
        misc_rows.append(dict(
            ts=ts, pol=pol, n=n,
            req_total=len(rq), ok=int((rq.status == "ok").sum()), cancelled=len(canc),
            other_status=int((~rq.status.isin(["ok", "cancelled"])).sum()),
            error_nonnull=int(rq.error.notna().sum()), error_kind_nonnull=int(rq.error_kind.notna().sum()),
            http_non200_ok=int((rq_ok.http_status != 200).sum()),
            cancelled_min_send=float(canc.t_send.min()) if len(canc) else np.nan,
            ois=json.dumps(rq.output_ids_source.value_counts(dropna=False).rename(index=str).to_dict()),
            completion_not100=int((rq_ok.completion_tokens != 100).sum()),
            sess_completed=int((ss.status == "completed").sum()), sess_cancelled=int((ss.status == "cancelled").sum()),
            sess_other=int((~ss.status.isin(["completed", "cancelled"])).sum()),
            meta_err=m["outcome"]["requests_error"], meta_abort=m["outcome"]["abort_reason"],
            meta_ptmismatch=m["outcome"]["prompt_tokens_mismatch"],
            lat_p50=lat.quantile(0.5), lat_p90=lat.quantile(0.9), lat_p99=lat.quantile(0.99), lat_max=lat.max(),
            sched_p99=win.sched_delay_s.quantile(0.99),
        ))

        # n-sample of in-flight snapshots + session ages for the transient analysis
        for tt in [900, 1200, 1500, 1800, 2100, 2400, 2699]:
            s = inflight_snapshot(rq, tt)
            alive = ss[(ss.t_first_send <= tt) & (ss.t_end.fillna(np.inf) > tt)]
            gen0 = (alive.idx < n).mean()  # sessions from the synchronized initial cohort
            snap_rows.append(dict(ts=ts, pol=pol, n=n, t=tt, **s, alive=len(alive), frac_initial_cohort=gen0,
                                  mean_age=(tt - alive.t_first_send).mean()))

    df = pd.DataFrame(rows).sort_values(["pol", "n"])
    bins = pd.DataFrame(bins_rows)
    st = pd.DataFrame(stat_rows).sort_values(["pol", "n"])
    misc = pd.DataFrame(misc_rows).sort_values(["pol", "n"])
    snaps = pd.DataFrame(snap_rows).sort_values(["pol", "n", "t"])
    df.to_csv(os.path.join(OUT, "recompute_points.csv"), index=False)
    bins.to_csv(os.path.join(OUT, "bins.csv"), index=False)
    st.to_csv(os.path.join(OUT, "stationarity.csv"), index=False)
    misc.to_csv(os.path.join(OUT, "misc.csv"), index=False)
    snaps.to_csv(os.path.join(OUT, "snapshots.csv"), index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    ET, mean_k, surv = expected_turns(15.0, 60)
    print(f"E[T]={ET:.6f}  count-biased mean turn index={mean_k:.4f}  -> mean prompt={2000+650*(mean_k-1):.1f}")
    print(df[["pol", "n", "job", "sessions", "alt_sessions", "turns", "alt_turns", "mu_sessions", "mu_turns_based", "turns_per_s", "hit_frac", "hit_frac_followup", "cached_frac_tok", "mean_T_completed_sessions", "formula_bad", "end_mismatch_s", "pt_client_mismatch"]].to_string(index=False))
    diffs = {
        "mu_sessions(own [900,2700)/1800)": (df.mu_sessions - df.H_mu_sessions).abs().max(),
        "mu_sessions(harness window/div)": (df.mu_sessions_harnessdiv - df.H_mu_sessions).abs().max(),
        "mu_turns_based(own)": (df.mu_turns_based - df.H_mu_turns_based).abs().max(),
        "mu_turns_based(harness div)": (df.mu_turns_harnessdiv - df.H_mu_turns_based).abs().max(),
        "hit_frac": (df.hit_frac - df.H_hit_frac_turns).abs().max(),
        "hit_frac_followup": (df.hit_frac_followup - df.H_hit_frac_followup).abs().max(),
        "cached_frac_tokens": (df.cached_frac_tok - df.H_cached_frac_tokens).abs().max(),
        "sessions count": (df.alt_sessions - df.H_sessions_completed).abs().max(),
        "turns count": (df.alt_turns - df.H_turns_completed).abs().max(),
    }
    print("\nmax abs diff vs harness:")
    for k_, v in diffs.items():
        print(f"  {k_}: {v:.3e}")
    print("\nbins:")
    print(bins[["pol", "n", "bin", "sessions", "mu_sessions", "turns_per_s", "hit_frac", "mean_prompt", "mean_turn", "mean_T_completed_sessions", "inflight_mean_turn_mid", "inflight_mean_prompt_mid", "n_inflight_mid"]].round(4).to_string(index=False))
    print("\nstationarity:")
    print(st.round(3).to_string(index=False))
    print("\nmisc:")
    print(misc.round(2).to_string(index=False))
    print("\nsnapshots:")
    print(snaps.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
