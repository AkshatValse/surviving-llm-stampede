"""Derived numbers for the paper that no committed analysis reports directly (read-only on committed run data).

Writes these CSVs under paper/derived/ (the paper cites them through paper/NUMBERS.md):

  e2_burst_backlog.csv  per E2 BURST run: the backlog (sessions in the system, the verdict's backlog_trace.csv, 50 s bins)
                        after the burst and over the evaluation window, next to the registered slope test.
  e2_capped_drain.csv   per E2 CAPPED run: when the client-side gate queue first empties after the burst (sessions.csv:
                        arrival_s and t_admit), against the registered estimate b / (mu(20) - lambda) and against
                        the fluid estimate (n_1 + b - 20) / (mu(20) - lambda), n_1 the sessions present at the burst
                        (columns n_at_burst, fluid_drain_s, ratio_to_fluid; added 2026-10-31).
  e0b_hit.csv           per E0b run: the registered hit metric (ok turns with cached_tokens / prompt_tokens > 0.5, first
                        turns included, by completion time) over the whole run and over its two halves, and the sessions
                        that arrived over the run (arrival seed 0) as a realized rate in multiples of lambda_ref.
  e2_counts.csv         the real E2 arm counts and a post-hoc sign test on the hit metric that counts each seed once
                        (both rates share the three seeds, so the six seed-and-rate pairs are not independent).

and the same quantities for the native-pool runs and the exploratory vLLM BURST runs (added 2026-10-26):

  e0b_native_hit.csv          e0b_hit.csv for native E0b (jobs 17100938-39).
  e2_native_burst_backlog.csv e2_burst_backlog.csv for the native E2 BURST runs (jobs 17102173-90).
  e2_native_capped_drain.csv  e2_capped_drain.csv for the native E2 CAPPED runs, against the native registration's estimate.
  e2_native_counts.csv        e2_counts.csv for native E2 (no counts pooled over the two tests: they share the seeds).
  vllm_burst_backlog.csv      e2_burst_backlog.csv for the six exploratory vLLM BURST runs (jobs 17102318-23).
  burst_hit_onset.csv         per BURST run of all three tests: the hit metric from 300 s to the burst; in 100 s windows (by
                              completion time) the first window from which every later window has no hit; the hit in the
                              window containing the burst; and the eval-window hit recomputed from requests.csv next to the
                              verdict's hit_eval (a check).

added 2026-10-30:

  e0b_vllm_hit.csv            e0b_hit.csv for vLLM E0b (jobs 17162962-63; six-run bracket 20261030-172042).
  e2_client_side.csv          per run of all three tests (300k E2, native E2, exploratory vLLM BURST), every arm: the
                              client-side cost. Gate waits (sessions.csv gate_wait_s > 0: count, mean, max, the share of
                              ordinary base-stream arrivals among them, and the waits of sessions that arrived after the
                              gate first emptied and of those that arrived in the evaluation window); turn latency
                              (t_complete - t_send; the client does not stream) over ok requests completed in
                              [5700, t_end) and in [300, 1200); the share of sessions unfinished at
                              t_end (8700 s); base-stream arrivals and completed sessions in [5700, t_end), as rates in
                              multiples of lambda_ref.
  e2_client_side_summary.csv  e2_client_side.csv as min-max ranges per test, rate and arm.

Every CSV that names a run gives run_dir, the run's path as the analyses and the cluster record it
(results/agentload_*/<timestamp>), and run_path, the same run's path from the repository root
(results/nova/<pull>/results/agentload_*/<timestamp>).

Every input is read through _style.src, which refuses files that git does not track unmodified.
Run:  PYTHONPATH="src;." python figures/paper/derived_numbers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style as S  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

E2_PULL = "results/nova/e2_170933xx_pulled_20261025-144558"
E2_VERDICT = f"{E2_PULL}/results/agentload_analysis_burst2/20261025-144012"
E0B_PULL = "results/nova/e0b_1708475x_pulled_20261024-150639"
E0B_STABLE = f"{E0B_PULL}/results/agentload_analysis_stable/20261024-150720/stable_runs.csv"
REG = "configs/agentload_prereg_2026-10-24.yaml"
NAT_PULL = "results/nova/e2_native_vllm_burst_pulled_20261026-101256"
NAT_VERDICT = f"{NAT_PULL}/results/agentload_analysis_burst2/20261026-100653"     # native E2, registered
VLLM_VERDICT = f"{NAT_PULL}/results/agentload_analysis_burst2/20261026-100701"    # vLLM BURST, exploratory
NAT_REG = "configs/agentload_prereg_2026-10-25_native.yaml"
E0B_NAT_PULL = "results/nova/e0b_native_1710093x_pulled_20261025-173038"
E0B_NAT_STABLE = f"{E0B_NAT_PULL}/results/agentload_analysis_stable/20261025-172934/stable_runs.csv"
E0B_VLLM_PULL = "results/nova/e0b_vllm_1716296x_pulled_20261030-172810"
E0B_VLLM_STABLE = f"{E0B_VLLM_PULL}/results/agentload_analysis_stable/20261030-172042/stable_runs.csv"   # six-run bracket
OUT = S.ROOT / "paper" / "derived"
T_BURST = 1200.0
BURST_N = 200
EVAL_FROM = 5700.0
E0B_DURATION = 3000.0   # every E0b run: 3000 s from an empty cache and queue
PRE_FROM = 300.0        # start of the pre-burst latency window (the warm-up before it is excluded)


def _mean_backlog(tr: pd.DataFrame, a: float, b: float) -> float:
    g = tr[(tr.t_start >= a) & (tr.t_start < b)]
    return float(g.backlog_mean.mean())


def _run_path(pull: str, run_dir: str) -> str:
    """The run's path from the repository root: the pull directory, then the path the cluster recorded."""
    p = f"{pull}/{run_dir}"
    assert (S.ROOT / p).is_dir(), p
    return p


def e2_burst_backlog(runs: pd.DataFrame, trace: pd.DataFrame, pull: str) -> pd.DataFrame:
    rows = []
    for _, r in runs[runs.arm == "burst"].iterrows():
        tr = trace[trace.run_dir == r.run_dir]
        post = tr[(tr.t_start >= T_BURST + 100) & (tr.t_start < 4000)]   # after the burst window, before the evaluation window
        imin = post.backlog_mean.idxmin()
        rows.append({
            "rate_mult": r.rate_mult, "seed": int(r.seed), "state": r.state, "run_dir": r.run_dir,
            "run_path": _run_path(pull, r.run_dir),
            "backlog_1300_1500": _mean_backlog(tr, 1300, 1500),
            "backlog_min_after_burst": float(post.backlog_mean.min()),
            "t_min_after_burst_s": float(tr.loc[imin, "t_start"] - T_BURST),
            "backlog_eval_first300": _mean_backlog(tr, EVAL_FROM, EVAL_FROM + 300),
            "backlog_eval_last300": _mean_backlog(tr, 8400, 8700),
            "backlog_eval_start_registered": float(r.backlog_eval_start),
            "backlog_end_registered": float(r.backlog_end),
            "backlog_slope": float(r.backlog_slope), "slope_threshold": float(r.slope_threshold),
            "rate_sessions": float(r.rate_sessions), "lambda": float(r["lambda"]),
            "lambda_miss": float(r.lambda_miss)})
    return pd.DataFrame(rows).sort_values(["rate_mult", "seed"])


def _first_gate_empty(ses: pd.DataFrame, after: float) -> float:
    """First time > `after` at which the gate queue (arrived, not yet admitted) is empty again, having been non-empty."""
    ev = [(float(a), +1) for a in ses.arrival_s] + [(float(t), -1) for t in ses.t_admit if np.isfinite(t)]
    ev.sort(key=lambda x: (x[0], x[1]))       # an admission at the same instant as an arrival is processed first
    q, was_busy = 0, False
    for t, d in ev:
        q += d
        if t >= after and q > 10:
            was_busy = True
        if was_busy and q == 0:
            return t
    return float("nan")


def e2_capped_drain(runs: pd.DataFrame, reg_path: str = REG, pull: str = E2_PULL) -> pd.DataFrame:
    import yaml
    reg = yaml.safe_load(S.src(reg_path).read_text())
    pred = _find_pred(reg)      # the registration's capped_drain.predicted_drain_s_by_mult
    assert pred, "registration has no predicted_drain_s_by_mult"
    n_cap = int(_find_key(reg, "n_cap"))
    rows = []
    for _, r in runs[runs.arm == "capped"].iterrows():
        rel = f"{pull}/{r.run_dir}"
        ses = pd.read_csv(S.src(f"{rel}/sessions.csv"))
        ses["t_admit"] = pd.to_numeric(ses["t_admit"], errors="coerce")
        t_empty = _first_gate_empty(ses, T_BURST)
        p = pred[float(r.rate_mult)]
        # The fluid estimate (Sec. 3.4): the burst fills the n_cap - n_1 free slots at once, so the gate holds
        # n_1 + b - n_cap sessions and empties after (n_1 + b - n_cap) / (mu(n_cap) - lambda); mu(n_cap) - lambda is
        # taken from the registered estimate b / (mu(n_cap) - lambda), and n_1 is the number of sessions in the system
        # at the burst (arrived before T_BURST, not ended by then).
        tend = pd.to_numeric(ses.t_end, errors="coerce")
        n1 = int(((ses.arrival_s < T_BURST) & ~(tend <= T_BURST)).sum())
        fluid = (n1 + BURST_N - n_cap) * p / BURST_N
        rows.append({"rate_mult": r.rate_mult, "seed": int(r.seed), "run_dir": r.run_dir,
                     "run_path": _run_path(pull, r.run_dir),
                     "gate_empty_after_burst_s": t_empty - T_BURST, "predicted_drain_s": p,
                     "ratio_to_predicted": (t_empty - T_BURST) / p,
                     "n_at_burst": n1, "fluid_drain_s": fluid, "ratio_to_fluid": (t_empty - T_BURST) / fluid,
                     "max_gate_wait_s": float(pd.to_numeric(ses.gate_wait_s, errors="coerce").max())})
    return pd.DataFrame(rows).sort_values(["rate_mult", "seed"])


def _find_key(obj, key):
    """First scalar value of `key` anywhere in the registration."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and not isinstance(v, (dict, list)):
                return v
            got = _find_key(v, key)
            if got is not None:
                return got
    if isinstance(obj, list):
        for v in obj:
            got = _find_key(v, key)
            if got is not None:
                return got
    return None


def _find_pred(obj):
    """Locate predicted_drain_s_by_mult anywhere in the registration."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "predicted_drain_s_by_mult":
                return {float(a): float(b) for a, b in v.items()}
            got = _find_pred(v)
            if got:
                return got
    if isinstance(obj, list):
        for v in obj:
            got = _find_pred(v)
            if got:
                return got
    return None


def e0b_hit(stable: str = E0B_STABLE, pull: str = E0B_PULL) -> pd.DataFrame:
    st = pd.read_csv(S.src(stable))
    rows = []
    for _, r in st.sort_values("rate_mult").iterrows():
        rel = f"{pull}/{r.run_dir}"
        req = pd.read_csv(S.src(f"{rel}/requests.csv"))
        meta = json.loads(S.src(f"{rel}/meta.json").read_text())
        req = req[req.status == "ok"].copy()
        for c in ("t_complete", "prompt_tokens", "cached_tokens"):
            req[c] = pd.to_numeric(req[c], errors="coerce")
        req["hit"] = (req.cached_tokens / req.prompt_tokens) > 0.5

        def frac(a: float, b: float) -> float:
            g = req[(req.t_complete >= a) & (req.t_complete < b)]
            return float(g.hit.mean()) if len(g) else float("nan")

        ses = pd.read_csv(S.src(f"{rel}/sessions.csv"))
        rate = float(meta.get("resolved_rate_sessions_per_s", float("nan")))
        lam_ref = float(meta.get("lambda_ref_resolved") or rate / float(r.rate_mult))
        assert abs(rate / lam_ref - float(r.rate_mult)) < 1e-6, (rel, rate, lam_ref)
        dur = E0B_DURATION
        n_arr = int((pd.to_numeric(ses.arrival_s, errors="coerce") < dur).sum())
        rows.append({"rate_mult": r.rate_mult, "stable": bool(r.stable),
                     "rate_sessions_per_s": rate,
                     "hit_whole_run": float(req.hit.mean()), "hit_300_1500": frac(300, 1500),
                     "hit_1500_3000": frac(1500, 3000), "n_turns": int(len(req)),
                     "final_queue": float(r.final_queue), "trend_rise": float(r.trend_rise),
                     "lambda_ref": lam_ref, "n_sessions_arrived": n_arr,
                     "realized_rate_sessions_per_s": n_arr / dur, "realized_mult": n_arr / dur / lam_ref,
                     "realized_over_nominal": n_arr / dur / rate - 1.0,
                     "run_dir": r.run_dir, "run_path": _run_path(pull, r.run_dir)})
    return pd.DataFrame(rows)


def e2_counts(runs: pd.DataFrame, test: str | None = None) -> pd.DataFrame:
    """Arm counts, and a post-hoc one-sided sign test on the hit metric (BURST hit below NOBURST hit) that counts each seed
    once. The two rates of a test reuse the same three seeds (same burst, nested arrivals), so the six seed-and-rate pairs
    are not independent; a seed counts as a success only if BURST is below NOBURST at every rate. No intervals are given:
    the runs of an arm come from three workload realizations, and no registration declares an interval."""
    rows = []
    for label, arm, k in (("NOBURST good", "noburst", int(runs[runs.arm == "noburst"].good.sum())),
                          ("CAPPED recovered", "capped", int(runs[runs.arm == "capped"].recovered.sum())),
                          ("BURST trapped (registered rule)", "burst", int(runs[runs.arm == "burst"].trapped.sum())),
                          ("BURST hit 0 over the window", "burst", int((runs[runs.arm == "burst"].hit_eval == 0).sum()))):
        rows.append({"quantity": label, "k": k, "n": int((runs.arm == arm).sum())})
    piv = runs.pivot_table(index=["rate_mult", "seed"], columns="arm", values="hit_eval")
    below = piv["burst"] < piv["noburst"]
    rows.append({"quantity": "BURST hit < NOBURST hit, seed-and-rate pairs (descriptive; the pairs share seeds)",
                 "k": int(below.sum()), "n": int(len(below))})
    by_seed = below.groupby(level="seed").all()
    from scipy import stats
    k, n = int(by_seed.sum()), int(len(by_seed))
    p = float(stats.binomtest(k, n, 0.5, alternative="greater").pvalue)
    rows.append({"quantity": "seeds with BURST hit < NOBURST hit at every rate (post-hoc sign test, each seed once)",
                 "k": k, "n": n, "p_one_sided": p})
    out = pd.DataFrame(rows)
    if test is not None:
        out.insert(0, "test", test)
    return out


def burst_hit_onset(runs: pd.DataFrame, pull: str, test: str, window_s: float = 100.0) -> pd.DataFrame:
    """Per BURST run: the registered hit metric in 100 s windows (ok turns, cached/prompt > 0.5, by completion time)."""
    rows = []
    for _, r in runs[runs.arm == "burst"].sort_values(["rate_mult", "seed"]).iterrows():
        req = pd.read_csv(S.src(f"{pull}/{r.run_dir}/requests.csv"))
        req = req[req.status == "ok"].copy()
        for c in ("t_complete", "prompt_tokens", "cached_tokens"):
            req[c] = pd.to_numeric(req[c], errors="coerce")
        req["hit"] = (req.cached_tokens / req.prompt_tokens) > 0.5
        t_end = float(r.t_end_s)
        req["w"] = np.floor(req.t_complete / window_s) * window_s
        by = req.groupby("w").hit.agg(["sum", "count"])
        hits = {float(w): (int(a), int(b)) for w, (a, b) in by.iterrows()}
        # first window start t0 >= t_burst such that every window from t0 to the end of the run has no hit
        starts = [float(w) for w in np.arange(0.0, t_end, window_s) if w >= float(r.t_burst)]
        onset = float("nan")
        for t0 in starts:
            if all(hits.get(w, (0, 0))[0] == 0 for w in starts if w >= t0):
                onset = t0
                break
        burst_w = float(np.floor(float(r.t_burst) / window_s) * window_s)
        hb = hits.get(burst_w, (0, 0))
        ev = req[(req.t_complete >= float(r.eval_from)) & (req.t_complete <= t_end)]
        pre = req[(req.t_complete >= 300.0) & (req.t_complete < float(r.t_burst))]     # before the burst (post hoc, descriptive)
        rows.append({"test": test, "label": r.label, "rate_mult": r.rate_mult, "seed": int(r.seed), "state": r.state,
                     "run_dir": r.run_dir, "run_path": _run_path(pull, r.run_dir),
                     "hit_300_to_burst": float(pre.hit.mean()),
                     "zero_hit_from_s": onset, "zero_hit_from_after_burst_s": onset - float(r.t_burst),
                     "hit_burst_window": hb[0] / hb[1] if hb[1] else float("nan"),
                     "hit_eval_recomputed": float(ev.hit.mean()), "hit_eval_registered": float(r.hit_eval)})
    return pd.DataFrame(rows)


def client_side(runs: pd.DataFrame, pull: str, test: str) -> pd.DataFrame:
    """Per run, every arm: gate waits, turn latency, unfinished sessions and realized rates (the cost of the cap at the client,
    and the trapped latency). All post hoc and descriptive."""
    rows = []
    for _, r in runs.sort_values(["rate_mult", "arm", "seed"]).iterrows():
        rel = f"{pull}/{r.run_dir}"
        ses = pd.read_csv(S.src(f"{rel}/sessions.csv"))
        req = pd.read_csv(S.src(f"{rel}/requests.csv"))
        for c in ("arrival_s", "t_end", "gate_wait_s", "t_admit", "gate_censored"):
            ses[c] = pd.to_numeric(ses[c], errors="coerce")
        for c in ("t_send", "t_complete", "latency_s", "turn"):
            req[c] = pd.to_numeric(req[c], errors="coerce")
        ok = req[req.status == "ok"]
        assert np.allclose(ok.latency_s, ok.t_complete - ok.t_send, atol=1e-6), rel
        t_end, e0 = float(r.t_end_s), float(r.eval_from)
        e_len = t_end - e0
        assert abs(e_len - float(r.eval_len_s)) < 1e-6 and float(r.t_burst) == T_BURST
        lam_ref = float(r["lambda"]) / float(r.rate_mult)
        assert abs(lam_ref - float(r.lambda_miss)) < 1e-9, (rel, lam_ref, r.lambda_miss)
        ev = ok[(ok.t_complete >= e0) & (ok.t_complete < t_end)]
        pre = ok[(ok.t_complete >= PRE_FROM) & (ok.t_complete < T_BURST)]
        base = ses[ses.origin == "base"]
        base_eval = base[(base.arrival_s >= e0) & (base.arrival_s < t_end)]
        done_eval = ses[(ses.status == "completed") & (ses.t_end >= e0) & (ses.t_end <= t_end)]
        gated = ses[ses.gate_wait_s > 0]
        t_empty = _first_gate_empty(ses, T_BURST) if r.arm == "capped" else float("nan")
        late = gated[gated.arrival_s > t_empty] if np.isfinite(t_empty) else gated.iloc[0:0]
        gated_eval = gated[(gated.arrival_s >= e0) & (gated.arrival_s < t_end)]
        rows.append({
            "test": test, "label": r.label, "rate_mult": r.rate_mult, "seed": int(r.seed), "arm": r.arm, "state": r.state,
            "gate_n_cap": float(r.gate_n_cap), "lambda_ref": lam_ref,
            "n_gated": int(len(gated)), "n_gated_base": int((gated.origin == "base").sum()),
            "n_gated_burst": int((gated.origin == "burst").sum()),
            "base_share_of_gated": float((gated.origin == "base").mean()) if len(gated) else float("nan"),
            "gate_wait_mean_s": float(gated.gate_wait_s.mean()) if len(gated) else float("nan"),
            "gate_wait_max_s": float(gated.gate_wait_s.max()) if len(gated) else float("nan"),
            "n_gate_censored": int((ses.gate_censored == 1).sum()),
            "gate_empty_after_burst_s": t_empty - T_BURST,
            "n_gated_after_gate_emptied": int(len(late)),
            "gate_wait_max_after_gate_emptied_s": float(late.gate_wait_s.max()) if len(late) else float("nan"),
            "n_gated_arrived_eval": int(len(gated_eval)),
            "gate_wait_max_arrived_eval_s": float(gated_eval.gate_wait_s.max()) if len(gated_eval) else float("nan"),
            "n_turns_eval_ok": int(len(ev)),
            "latency_mean_eval_s": float(ev.latency_s.mean()), "latency_median_eval_s": float(ev.latency_s.median()),
            "latency_mean_followup_eval_s": float(ev[ev.turn > 1].latency_s.mean()),
            "latency_median_followup_eval_s": float(ev[ev.turn > 1].latency_s.median()),
            "n_turns_preburst_ok": int(len(pre)), "latency_mean_preburst_s": float(pre.latency_s.mean()),
            "n_sessions": int(len(ses)), "n_unfinished_at_end": int((ses.status != "completed").sum()),
            "unfinished_share_at_end": float((ses.status != "completed").mean()),
            "eval_len_s": e_len, "base_arrivals_eval": int(len(base_eval)),
            "base_rate_eval_sps": len(base_eval) / e_len, "base_rate_eval_mult": len(base_eval) / e_len / lam_ref,
            "sessions_completed_eval": int(len(done_eval)),
            "sessions_completed_eval_registered": int(r.n_sessions_completed_eval),
            "completed_rate_eval_mult": len(done_eval) / e_len / lam_ref,
            "run_dir": r.run_dir, "run_path": _run_path(pull, r.run_dir)})
    return pd.DataFrame(rows)


def client_side_summary(cs: pd.DataFrame) -> pd.DataFrame:
    """e2_client_side.csv as min-max ranges per test, rate and arm."""
    cols = ["n_gated", "base_share_of_gated", "gate_wait_mean_s", "gate_wait_max_s", "n_gated_after_gate_emptied",
            "gate_wait_max_after_gate_emptied_s", "n_gated_arrived_eval", "gate_wait_max_arrived_eval_s", "latency_mean_eval_s", "latency_median_eval_s",
            "latency_mean_followup_eval_s", "latency_median_followup_eval_s", "latency_mean_preburst_s",
            "unfinished_share_at_end", "base_rate_eval_mult", "completed_rate_eval_mult"]
    rows = []
    for (test, rate, arm), g in cs.groupby(["test", "rate_mult", "arm"], sort=False):
        row = {"test": test, "rate_mult": rate, "arm": arm, "n_runs": int(len(g))}
        for c in cols:
            row[f"{c}_min"] = float(g[c].min())
            row[f"{c}_max"] = float(g[c].max())
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = pd.read_csv(S.src(f"{E2_VERDICT}/trap_v2_runs.csv"))
    assert len(runs) == 18, len(runs)
    trace = pd.read_csv(S.src(f"{E2_VERDICT}/backlog_trace.csv"))
    nat = pd.read_csv(S.src(f"{NAT_VERDICT}/trap_v2_runs.csv"))
    assert len(nat) == 18 and (nat.label == "sglang-fcfs-r1-native").all(), len(nat)
    nat_trace = pd.read_csv(S.src(f"{NAT_VERDICT}/backlog_trace.csv"))
    vl = pd.read_csv(S.src(f"{VLLM_VERDICT}/trap_v2_runs.csv"))
    assert len(vl) == 6 and (vl.label == "vllm-fcfs").all() and (vl.arm == "burst").all(), len(vl)
    vl_trace = pd.read_csv(S.src(f"{VLLM_VERDICT}/backlog_trace.csv"))
    for d in (nat, vl):
        assert set(d.t_burst) == {T_BURST} and set(d.eval_from) == {EVAL_FROM}
    cs = pd.concat([client_side(runs, E2_PULL, "300k"), client_side(nat, NAT_PULL, "native"),
                    client_side(vl, NAT_PULL, "vllm")], ignore_index=True)
    outs = {"e2_burst_backlog.csv": e2_burst_backlog(runs, trace, E2_PULL),
            "e2_capped_drain.csv": e2_capped_drain(runs),
            "e0b_hit.csv": e0b_hit(),
            "e2_counts.csv": e2_counts(runs),
            "e0b_native_hit.csv": e0b_hit(E0B_NAT_STABLE, E0B_NAT_PULL),
            "e2_native_burst_backlog.csv": e2_burst_backlog(nat, nat_trace, NAT_PULL),
            "e2_native_capped_drain.csv": e2_capped_drain(nat, NAT_REG, NAT_PULL),
            "e2_native_counts.csv": e2_counts(nat, "native"),
            "vllm_burst_backlog.csv": e2_burst_backlog(vl, vl_trace, NAT_PULL),
            "burst_hit_onset.csv": pd.concat([burst_hit_onset(runs, E2_PULL, "300k"), burst_hit_onset(nat, NAT_PULL, "native"),
                                              burst_hit_onset(vl, NAT_PULL, "vllm")], ignore_index=True),
            "e0b_vllm_hit.csv": e0b_hit(E0B_VLLM_STABLE, E0B_VLLM_PULL),
            "e2_client_side.csv": cs,
            "e2_client_side_summary.csv": client_side_summary(cs)}
    for name, df in outs.items():
        p = OUT / name
        df.to_csv(p, index=False, float_format="%.6g", lineterminator="\n")
        print(f"wrote {p}")
        print(df.to_string(index=False))
    print("inputs read: " + ", ".join(S._READ[:3]) + f", ... ({len(S._READ)} files)")


if __name__ == "__main__":
    main()
