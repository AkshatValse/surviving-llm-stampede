"""Derived numbers for the registered vLLM paired test (jobs 17166121-17166138), read-only on the pulled run data.

Two parts, both written into <pull>/derived/:

1. Scoring of the frozen r11 mechanism predictions (configs/r11_mechanism_predict.yaml at f1338e3, pushed 18:20:13 CDT
   2026-10-30). The three frozen scripts (analysis/r11/{loopvars,detector,occupancy}_frozen.py, checked out unchanged
   from origin/r11/strengthen) are run separately; their CSV outputs are in <pull>/r11_mechanism/. This script only
   applies the frozen bands and the frozen decision rule per arm, and flags each run blind iff its sacct End is later
   than the freeze push time (sacct times are CDT).
   -> r11_mechanism_scored.csv, r11_mechanism_decision.json

2. Client-side numbers, computed as the paper's 300k E2 numbers are (figures/paper/derived_numbers.py client_side on
   r10/arxiv; the function body is copied here unchanged in substance): gate waits (sessions.csv gate_wait_s > 0: count,
   mean, max, share of ordinary base-stream arrivals), the time after the burst at which the CAPPED gate queue first
   empties, mean turn latency of ok requests completed in [5700, 8700), the share of sessions unfinished at 8700 s,
   base-stream arrivals and completed sessions in [5700, 8700) as rates in multiples of lambda_ref.
   -> e2_vllm_client_side.csv, e2_vllm_client_side_summary.csv

Post hoc and descriptive except for part 1, which applies rules frozen before any run ended.
Run:  PYTHONPATH="src;." python analysis/r9_vllm_e2_derived.py results/nova/<pull>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

T_BURST = 1200.0
PRE_FROM = 300.0
FREEZE_PUSH_CDT = datetime(2026, 10, 30, 18, 20, 13)
VERDICT = "results/agentload_analysis_burst2/20261031-020837"


def _first_gate_empty(ses: pd.DataFrame, after: float) -> float:
    """First time > `after` at which the gate queue (arrived, not yet admitted) is empty again, having been non-empty
    (more than 10 waiting). Same definition as derived_numbers.py."""
    ev = [(float(a), +1) for a in ses.arrival_s] + [(float(t), -1) for t in ses.t_admit if np.isfinite(t)]
    ev.sort(key=lambda x: (x[0], x[1]))
    q, was_busy = 0, False
    for t, d in ev:
        q += d
        if t >= after and q > 10:
            was_busy = True
        if was_busy and q == 0:
            return t
    return float("nan")


def job_map(pull: Path) -> pd.DataFrame:
    rows = []
    for d in sorted((pull / "results" / "nova_job_logs").iterdir()):
        job = int(d.name.split("-")[0])
        run = (d / "run_dirs_burst.txt").read_text().strip()
        rows.append({"job_id": job, "run_dir": run, "run": run.rsplit("/", 1)[-1]})
    jm = pd.DataFrame(rows)
    sa = pd.read_csv(pull / "sacct_17166121-17166138.txt", sep="|")
    sa = sa.rename(columns={"JobID": "job_id"})
    jm = jm.merge(sa, on="job_id", how="left")
    jm["end_dt"] = pd.to_datetime(jm.End)
    jm["blind"] = jm.end_dt > FREEZE_PUSH_CDT
    return jm


def score(pull: Path, cfg: dict, jm: pd.DataFrame, runs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    mech = pull / "r11_mechanism"
    lv = pd.read_csv(mech / "loopvars.csv", dtype={"run": str})
    de = pd.read_csv(mech / "detector.csv")
    oc = pd.read_csv(mech / "occupancy.csv", dtype={"run": str})
    de["run"] = de["dir"].astype(str).str.rsplit("/", n=1).str[-1]
    b = cfg["bands"]
    ga, ba, bb = b["a_good_arms"]["noburst_and_capped"], b["a_burst_arm"], b["b_burst_arm"]
    c, dd = b["c_detector"], b["d_ttft_rule"]
    lo_c, hi_c = c["good_arms_no_alarm_in_s"]
    lo_d, hi_d = dd["good_arms_no_alarm_in_s"]
    rows = []
    for _, j in jm.iterrows():
        L = lv[lv.run == j.run].iloc[0]
        D = de[de.run == j.run].iloc[0]
        O = oc[oc.run == j.run].iloc[0]
        V = runs[runs.run_dir == j.run_dir].iloc[0]
        arm = V.arm
        assert arm == L.arm == D.arm == O.arm, (j.run, arm, L.arm, D.arm, O.arm)
        fa = D.first_alarm if pd.notna(D.first_alarm) else None
        ft = O.ttft_first_alarm if pd.notna(O.ttft_first_alarm) else None
        if arm == "burst":
            a_ok = bool(L.gap_over_R > ba["gap_over_R_min"] and L.hit < ba["hit_max"])
            b_ok = bool(O.occ_mean >= bb["occ_mean_min"] and bb["uncached_ratio"][0] <= O.uncached_ratio <= bb["uncached_ratio"][1])
            c_ok = bool(fa is not None and (fa - T_BURST) <= c["burst_first_alarm_delay_max_s"])
            d_ok = bool(ft is not None and (ft - T_BURST) <= dd["burst_first_alarm_delay_max_s"])
            c_note = d_note = ""
        else:
            a_ok = bool(L.gap_over_R < ga["gap_over_R_max"] and L.hit > ga["hit_min"])
            b_ok = None
            # the frozen detector reports the first alarm only; an alarm before 600 s would leave later ticks unknown
            if fa is None:
                c_ok, c_note = True, ""
            elif lo_c <= fa < hi_c:
                c_ok, c_note = False, f"false alarm at {fa:.0f} s ({int(D.alarm_ticks)} ticks)"
            else:
                c_ok, c_note = None, "first alarm before 600 s: later ticks not reported by the frozen script"
            if ft is None:
                d_ok, d_note = True, ""
            elif lo_d <= ft < hi_d:
                d_ok, d_note = False, f"TTFT alarm at {ft:.0f} s"
            else:
                d_ok, d_note = None, "first TTFT alarm before 600 s"
        rows.append({"job_id": int(j.job_id), "run": j.run, "rate_mult": float(V.rate_mult), "seed": int(V.seed), "arm": arm,
                     "state": V.state, "end_cdt": j.End, "blind": bool(j.blind),
                     "hit_fu": L.hit, "gap_med_s": L.gap_med, "R_s": L.R_s, "gap_over_R": L.gap_over_R, "a_ok": a_ok,
                     "occ_mean": O.occ_mean, "uncached_ratio": O.uncached_ratio, "b_ok": b_ok,
                     "det_first_alarm_s": fa, "det_delay_s": (fa - T_BURST) if fa is not None else None,
                     "det_alarm_ticks": int(D.alarm_ticks), "det_hits_returned_at_s": D.hits_returned_at, "c_ok": c_ok, "c_note": c_note,
                     "ttft_first_alarm_s": ft, "ttft_delay_s": (ft - T_BURST) if ft is not None else None, "d_ok": d_ok, "d_note": d_note})
    sc = pd.DataFrame(rows).sort_values(["rate_mult", "arm", "seed"])
    bl = sc[sc.blind]
    bu, gd = bl[bl.arm == "burst"], bl[bl.arm != "burst"]
    burst_ok = bool((bu.b_ok == True).all() and (bu.c_ok == True).all())  # noqa: E712
    good_fail = gd[~((gd.a_ok == True) & (gd.c_ok == True))]  # noqa: E712
    dec = {
        "freeze_push_cdt": FREEZE_PUSH_CDT.isoformat(sep=" "),
        "n_runs": int(len(sc)), "n_blind": int(sc.blind.sum()),
        "burst_blind": int(len(bu)), "burst_meet_b": int((bu.b_ok == True).sum()), "burst_meet_c": int((bu.c_ok == True).sum()),  # noqa: E712
        "burst_meet_a": int((bu.a_ok == True).sum()), "burst_meet_d": int((bu.d_ok == True).sum()),  # noqa: E712
        "good_blind": int(len(gd)), "good_meet_a": int((gd.a_ok == True).sum()), "good_meet_c": int((gd.c_ok == True).sum()),  # noqa: E712
        "good_meet_d": int((gd.d_ok == True).sum()),  # noqa: E712
        "good_failing_a_or_c": good_fail[["job_id", "run", "rate_mult", "seed", "arm", "a_ok", "c_ok", "c_note"]].to_dict("records"),
        "every_blind_burst_meets_b_and_c": burst_ok,
        "good_arm_failures_allowed": 1,
        "consistent_with_refill_then_evict": bool(burst_ok and len(good_fail) <= 1),
        "b_failure_any": bool((bu.b_ok == False).any()),  # noqa: E712
        "detector_false_alarms_good_arms": int((gd.c_ok == False).sum()),  # noqa: E712
    }
    return sc, dec


def client_side(runs: pd.DataFrame, pull: Path) -> pd.DataFrame:
    rows = []
    for _, r in runs.sort_values(["rate_mult", "arm", "seed"]).iterrows():
        rd = pull / r.run_dir
        ses = pd.read_csv(rd / "sessions.csv")
        req = pd.read_csv(rd / "requests.csv", usecols=["turn", "t_send", "t_complete", "latency_s", "status"])
        for c in ("arrival_s", "t_end", "gate_wait_s", "t_admit", "gate_censored"):
            ses[c] = pd.to_numeric(ses[c], errors="coerce")
        for c in ("t_send", "t_complete", "latency_s", "turn"):
            req[c] = pd.to_numeric(req[c], errors="coerce")
        ok = req[req.status == "ok"]
        assert np.allclose(ok.latency_s, ok.t_complete - ok.t_send, atol=1e-6), rd
        t_end, e0 = float(r.t_end_s), float(r.eval_from)
        e_len = t_end - e0
        assert abs(e_len - float(r.eval_len_s)) < 1e-6 and float(r.t_burst) == T_BURST
        lam_ref = float(r["lambda"]) / float(r.rate_mult)
        assert abs(lam_ref - float(r.lambda_miss)) < 1e-9, (rd, lam_ref, r.lambda_miss)
        ev = ok[(ok.t_complete >= e0) & (ok.t_complete < t_end)]
        pre = ok[(ok.t_complete >= PRE_FROM) & (ok.t_complete < T_BURST)]
        base = ses[ses.origin == "base"]
        base_eval = base[(base.arrival_s >= e0) & (base.arrival_s < t_end)]
        done_eval = ses[(ses.status == "completed") & (ses.t_end >= e0) & (ses.t_end <= t_end)]
        gated = ses[ses.gate_wait_s > 0]
        t_empty = _first_gate_empty(ses, T_BURST) if r.arm == "capped" else float("nan")
        late = gated[gated.arrival_s > t_empty] if np.isfinite(t_empty) else gated.iloc[0:0]
        gated_eval = gated[(gated.arrival_s >= e0) & (gated.arrival_s < t_end)]
        early = gated[gated.arrival_s < T_BURST]
        n_base_total = int((ses.origin == "base").sum())
        rows.append({
            "label": r.label, "rate_mult": r.rate_mult, "seed": int(r.seed), "arm": r.arm, "state": r.state,
            "gate_n_cap": float(r.gate_n_cap), "lambda_ref": lam_ref,
            "n_gated": int(len(gated)), "n_gated_base": int((gated.origin == "base").sum()),
            "n_gated_burst": int((gated.origin == "burst").sum()),
            "base_share_of_gated": float((gated.origin == "base").mean()) if len(gated) else float("nan"),
            "gated_share_of_base_arrivals": float((gated.origin == "base").sum() / n_base_total) if n_base_total else float("nan"),
            "gate_wait_mean_s": float(gated.gate_wait_s.mean()) if len(gated) else float("nan"),
            "gate_wait_max_s": float(gated.gate_wait_s.max()) if len(gated) else float("nan"),
            "n_gate_censored": int((ses.gate_censored == 1).sum()),
            "gate_empty_after_burst_s": t_empty - T_BURST,
            "n_gated_before_burst": int(len(early)),
            "gate_wait_max_before_burst_s": float(early.gate_wait_s.max()) if len(early) else float("nan"),
            "n_gated_after_gate_emptied": int(len(late)),
            "gate_wait_max_after_gate_emptied_s": float(late.gate_wait_s.max()) if len(late) else float("nan"),
            "n_gated_arrived_eval": int(len(gated_eval)),
            "gate_wait_max_arrived_eval_s": float(gated_eval.gate_wait_s.max()) if len(gated_eval) else float("nan"),
            "n_turns_eval_ok": int(len(ev)),
            "latency_mean_eval_s": float(ev.latency_s.mean()), "latency_median_eval_s": float(ev.latency_s.median()),
            "latency_mean_followup_eval_s": float(ev[ev.turn > 1].latency_s.mean()),
            "n_turns_preburst_ok": int(len(pre)), "latency_mean_preburst_s": float(pre.latency_s.mean()),
            "n_sessions": int(len(ses)), "n_base_sessions": n_base_total, "n_unfinished_at_end": int((ses.status != "completed").sum()),
            "unfinished_share_at_end": float((ses.status != "completed").mean()),
            "eval_len_s": e_len, "base_arrivals_eval": int(len(base_eval)),
            "base_rate_eval_sps": len(base_eval) / e_len, "base_rate_eval_mult": len(base_eval) / e_len / lam_ref,
            "sessions_completed_eval": int(len(done_eval)),
            "sessions_completed_eval_registered": int(r.n_sessions_completed_eval),
            "completed_rate_eval_mult": len(done_eval) / e_len / lam_ref,
            "run_dir": r.run_dir})
    return pd.DataFrame(rows)


def capped_drain(runs: pd.DataFrame, pull: Path, reg: dict) -> pd.DataFrame:
    """As derived_numbers.e2_capped_drain: gate-empty time after the burst against the registration's estimate
    b / (mu(n_cap) - lambda) and the fluid estimate (n_1 + b - n_cap) / (mu(n_cap) - lambda)."""
    pred = {float(a): float(b) for a, b in reg["capped_drain"]["predicted_drain_s_by_mult"].items()} \
        if "capped_drain" in reg else None
    if pred is None:
        def find(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "predicted_drain_s_by_mult":
                        return {float(a): float(b) for a, b in v.items()}
                    g = find(v)
                    if g:
                        return g
            return None
        pred = find(reg)
    n_cap = 20
    rows = []
    for _, r in runs[runs.arm == "capped"].sort_values(["rate_mult", "seed"]).iterrows():
        ses = pd.read_csv(pull / r.run_dir / "sessions.csv")
        ses["t_admit"] = pd.to_numeric(ses["t_admit"], errors="coerce")
        t_empty = _first_gate_empty(ses, T_BURST)
        p = pred[float(r.rate_mult)]
        tend = pd.to_numeric(ses.t_end, errors="coerce")
        n1 = int(((ses.arrival_s < T_BURST) & ~(tend <= T_BURST)).sum())
        fluid = (n1 + 200 - n_cap) * p / 200
        rows.append({"rate_mult": r.rate_mult, "seed": int(r.seed), "run_dir": r.run_dir,
                     "gate_empty_after_burst_s": t_empty - T_BURST, "predicted_drain_s": p,
                     "ratio_to_predicted": (t_empty - T_BURST) / p, "n_at_burst": n1, "fluid_drain_s": fluid,
                     "ratio_to_fluid": (t_empty - T_BURST) / fluid,
                     "max_gate_wait_s": float(pd.to_numeric(ses.gate_wait_s, errors="coerce").max())})
    return pd.DataFrame(rows)


def alarm_context(pull: Path, sc: pd.DataFrame) -> pd.DataFrame:
    """POST HOC: for each good-arm run with a frozen-detector alarm, the detector's own 10 s / 60 s series (follow-up
    turns, ok, by completion time) from 120 s before the first alarm to 120 s after, with the number of sessions
    admitted and the gate queue at each tick. Same arithmetic as detector_frozen.py."""
    rows = []
    for _, s in sc[(sc.arm != "burst") & (sc.c_ok == False)].iterrows():  # noqa: E712
        rd = next((pull / "results" / "agentload_e2_burst").glob(s.run))
        q = pd.read_csv(rd / "requests.csv", usecols=["turn", "t_complete", "status", "cached_tokens", "prompt_tokens"])
        ses = pd.read_csv(rd / "sessions.csv")
        ok = q[(q.status == "ok") & (q.turn >= 2)].sort_values("t_complete")
        tc = ok.t_complete.to_numpy(float)
        hit = (ok.cached_tokens.fillna(0) / ok.prompt_tokens.where(ok.prompt_tokens > 0) > 0.5).to_numpy()
        cs = np.concatenate([[0], np.cumsum(hit)])
        t_adm = pd.to_numeric(ses.t_admit, errors="coerce")
        t_end = pd.to_numeric(ses.t_end, errors="coerce")
        for t in np.arange(s.det_first_alarm_s - 120, s.det_first_alarm_s + 130, 10.0):
            lo, hi = np.searchsorted(tc, t - 60), np.searchsorted(tc, t)
            n = hi - lo
            rows.append({"run": s.run, "rate_mult": s.rate_mult, "seed": s.seed, "arm": s.arm, "t_s": t, "n_fu_60s": int(n),
                         "H": (cs[hi] - cs[lo]) / n if n else float("nan"), "alarm": bool(n >= 20 and (cs[hi] - cs[lo]) / max(n, 1) < 0.2),
                         "admitted_active": int(((t_adm <= t) & ~(t_end <= t)).sum()),
                         "gate_queue": int(((ses.arrival_s <= t) & ~(t_adm <= t)).sum())})
    return pd.DataFrame(rows)


def summary(cs: pd.DataFrame) -> pd.DataFrame:
    cols = ["n_gated", "base_share_of_gated", "gated_share_of_base_arrivals", "gate_wait_mean_s", "gate_wait_max_s",
            "gate_empty_after_burst_s", "n_gated_after_gate_emptied", "n_gated_arrived_eval", "latency_mean_eval_s",
            "latency_median_eval_s", "latency_mean_followup_eval_s", "latency_mean_preburst_s", "unfinished_share_at_end",
            "base_rate_eval_mult", "completed_rate_eval_mult"]
    rows = []
    for (rate, arm), g in cs.groupby(["rate_mult", "arm"], sort=False):
        row = {"rate_mult": rate, "arm": arm, "n_runs": int(len(g))}
        for c in cols:
            row[f"{c}_min"] = float(g[c].min())
            row[f"{c}_max"] = float(g[c].max())
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    pull = Path(sys.argv[1])
    cfg_path = pull / "r11_mechanism" / "frozen" / "configs" / "r11_mechanism_predict.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["status"] == "FROZEN"
    runs = pd.read_csv(pull / VERDICT / "trap_v2_runs.csv")
    assert len(runs) == 18 and (runs.label == "vllm-fcfs").all()
    jm = job_map(pull)
    assert len(jm) == 18 and set(jm.run_dir) == set(runs.run_dir)
    out = pull / "derived"
    out.mkdir(exist_ok=True)
    sc, dec = score(pull, cfg, jm, runs)
    sc.to_csv(out / "r11_mechanism_scored.csv", index=False, float_format="%.6g", lineterminator="\n")
    (out / "r11_mechanism_decision.json").write_text(json.dumps(dec, indent=2, default=str) + "\n")
    cs = client_side(runs, pull)
    cs = cs.merge(jm[["run_dir", "job_id"]], on="run_dir")
    cs.to_csv(out / "e2_vllm_client_side.csv", index=False, float_format="%.6g", lineterminator="\n")
    sm = summary(cs)
    sm.to_csv(out / "e2_vllm_client_side_summary.csv", index=False, float_format="%.6g", lineterminator="\n")
    reg = yaml.safe_load((pull.parents[2] / "configs" / "agentload_prereg_2026-10-30_vllm.yaml").read_text())
    dr = capped_drain(runs, pull, reg)
    dr.to_csv(out / "e2_vllm_capped_drain.csv", index=False, float_format="%.6g", lineterminator="\n")
    ac = alarm_context(pull, sc)
    ac.to_csv(out / "r11_detector_false_alarm_context_posthoc.csv", index=False, float_format="%.6g", lineterminator="\n")
    print(dr.drop(columns=["run_dir"]).to_string(index=False))
    print(ac.to_string(index=False))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
    print(sc.to_string(index=False))
    print(json.dumps(dec, indent=2, default=str))
    print(cs.drop(columns=["run_dir", "label"]).to_string(index=False))


if __name__ == "__main__":
    main()
