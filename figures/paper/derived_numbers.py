"""Derived numbers for the paper that no committed analysis reports directly (read-only on committed run data).

Writes three CSVs under paper/derived/ (the paper cites them through paper/NUMBERS.md):

  e2_burst_backlog.csv  per E2 BURST run: the backlog (sessions in the system, the verdict's backlog_trace.csv, 50 s bins)
                        after the burst and over the evaluation window, next to the registered slope test.
  e2_capped_drain.csv   per E2 CAPPED run: when the client-side gate queue first empties after the burst (sessions.csv:
                        arrival_s and t_admit), against the registered fluid drain estimate b / (mu(20) - lambda).
  e0b_hit.csv           per E0b run: the registered hit metric (ok turns with cached_tokens / prompt_tokens > 0.5, first
                        turns included, by completion time) over the whole run and over its two halves.
  e2_counts.csv         Wilson 95% intervals for the real E2 arm counts and the paired sign test on the hit metric.

and the same quantities for the native-pool runs and the exploratory vLLM BURST runs (added 2026-10-26):

  e0b_native_hit.csv          e0b_hit.csv for native E0b (jobs 17100938-39).
  e2_native_burst_backlog.csv e2_burst_backlog.csv for the native E2 BURST runs (jobs 17102173-90).
  e2_native_capped_drain.csv  e2_capped_drain.csv for the native E2 CAPPED runs, against the native registration's estimate.
  e2_native_counts.csv        Wilson intervals and the sign test for native E2, and the counts pooled over both registered tests.
  vllm_burst_backlog.csv      e2_burst_backlog.csv for the six exploratory vLLM BURST runs (jobs 17102318-23).
  burst_hit_onset.csv         per BURST run of all three tests: the hit metric from 300 s to the burst; in 100 s windows (by
                              completion time) the first window from which every later window has no hit; the hit in the
                              window containing the burst; and the eval-window hit recomputed from requests.csv next to the
                              verdict's hit_eval (a check).

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
OUT = S.ROOT / "paper" / "derived"
T_BURST = 1200.0
BURST_N = 200
EVAL_FROM = 5700.0


def _mean_backlog(tr: pd.DataFrame, a: float, b: float) -> float:
    g = tr[(tr.t_start >= a) & (tr.t_start < b)]
    return float(g.backlog_mean.mean())


def e2_burst_backlog(runs: pd.DataFrame, trace: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in runs[runs.arm == "burst"].iterrows():
        tr = trace[trace.run_dir == r.run_dir]
        post = tr[(tr.t_start >= T_BURST + 100) & (tr.t_start < 4000)]   # after the burst window, before the evaluation window
        imin = post.backlog_mean.idxmin()
        rows.append({
            "rate_mult": r.rate_mult, "seed": int(r.seed), "state": r.state, "run_dir": r.run_dir,
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
    rows = []
    for _, r in runs[runs.arm == "capped"].iterrows():
        rel = f"{pull}/{r.run_dir}"
        ses = pd.read_csv(S.src(f"{rel}/sessions.csv"))
        ses["t_admit"] = pd.to_numeric(ses["t_admit"], errors="coerce")
        t_empty = _first_gate_empty(ses, T_BURST)
        p = pred[float(r.rate_mult)]
        rows.append({"rate_mult": r.rate_mult, "seed": int(r.seed), "run_dir": r.run_dir,
                     "gate_empty_after_burst_s": t_empty - T_BURST, "predicted_drain_s": p,
                     "ratio_to_predicted": (t_empty - T_BURST) / p,
                     "max_gate_wait_s": float(pd.to_numeric(ses.gate_wait_s, errors="coerce").max())})
    return pd.DataFrame(rows).sort_values(["rate_mult", "seed"])


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

        rows.append({"rate_mult": r.rate_mult, "stable": bool(r.stable),
                     "rate_sessions_per_s": float(meta.get("resolved_rate_sessions_per_s", float("nan"))),
                     "hit_whole_run": float(req.hit.mean()), "hit_300_1500": frac(300, 1500),
                     "hit_1500_3000": frac(1500, 3000), "n_turns": int(len(req)), "run_dir": r.run_dir})
    return pd.DataFrame(rows)


def e2_counts(runs: pd.DataFrame, test: str | None = None) -> pd.DataFrame:
    rows = []
    for label, k, n in (("NOBURST good", int(runs[runs.arm == "noburst"].good.sum()), 6),
                        ("CAPPED recovered", int(runs[runs.arm == "capped"].recovered.sum()), 6),
                        ("BURST trapped (registered rule)", int(runs[runs.arm == "burst"].trapped.sum()), 6),
                        ("BURST hit 0 over the window", int((runs[runs.arm == "burst"].hit_eval == 0).sum()), 6)):
        lo, hi = S.wilson(k, n)
        rows.append({"quantity": label, "k": k, "n": n, "wilson95_lo": lo, "wilson95_hi": hi})
    # paired sign test over the 6 CRN pairs (rate, seed): BURST hit below NOBURST hit
    piv = runs.pivot_table(index=["rate_mult", "seed"], columns="arm", values="hit_eval")
    n_pairs = int(len(piv))
    n_pred = int((piv["burst"] < piv["noburst"]).sum())
    from scipy import stats
    p = float(stats.binomtest(n_pred, n_pairs, 0.5, alternative="greater").pvalue)
    rows.append({"quantity": "sign test BURST hit < NOBURST hit (pairs)", "k": n_pred, "n": n_pairs,
                 "wilson95_lo": float("nan"), "wilson95_hi": float("nan"), "p_one_sided": p})
    out = pd.DataFrame(rows)
    if test is not None:
        out.insert(0, "test", test)
    return out


def pooled_counts(r300: pd.DataFrame, rnat: pd.DataFrame) -> pd.DataFrame:
    """Arm counts pooled over the two registered tests (300k E2 and native E2), with Wilson 95% intervals."""
    both = pd.concat([r300, rnat], ignore_index=True)
    rows = []
    for label, arm, col in (("NOBURST good", "noburst", "good"), ("CAPPED recovered", "capped", "recovered"),
                            ("BURST trapped (registered rule)", "burst", "trapped")):
        g = both[both.arm == arm]
        k, n = int(g[col].sum()), int(len(g))
        lo, hi = S.wilson(k, n)
        rows.append({"test": "pooled 300k + native", "quantity": label, "k": k, "n": n, "wilson95_lo": lo, "wilson95_hi": hi})
    g = both[both.arm == "burst"]
    k, n = int((g.hit_eval == 0).sum()), int(len(g))
    lo, hi = S.wilson(k, n)
    rows.append({"test": "pooled 300k + native", "quantity": "BURST hit 0 over the window", "k": k, "n": n,
                 "wilson95_lo": lo, "wilson95_hi": hi})
    return pd.DataFrame(rows)


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
                     "run_dir": r.run_dir, "hit_300_to_burst": float(pre.hit.mean()),
                     "zero_hit_from_s": onset, "zero_hit_from_after_burst_s": onset - float(r.t_burst),
                     "hit_burst_window": hb[0] / hb[1] if hb[1] else float("nan"),
                     "hit_eval_recomputed": float(ev.hit.mean()), "hit_eval_registered": float(r.hit_eval)})
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
    outs = {"e2_burst_backlog.csv": e2_burst_backlog(runs, trace),
            "e2_capped_drain.csv": e2_capped_drain(runs),
            "e0b_hit.csv": e0b_hit(),
            "e2_counts.csv": e2_counts(runs),
            "e0b_native_hit.csv": e0b_hit(E0B_NAT_STABLE, E0B_NAT_PULL),
            "e2_native_burst_backlog.csv": e2_burst_backlog(nat, nat_trace),
            "e2_native_capped_drain.csv": e2_capped_drain(nat, NAT_REG, NAT_PULL),
            "e2_native_counts.csv": pd.concat([e2_counts(nat, "native"), pooled_counts(runs, nat)], ignore_index=True),
            "vllm_burst_backlog.csv": e2_burst_backlog(vl, vl_trace),
            "burst_hit_onset.csv": pd.concat([burst_hit_onset(runs, E2_PULL, "300k"), burst_hit_onset(nat, NAT_PULL, "native"),
                                              burst_hit_onset(vl, NAT_PULL, "vllm")], ignore_index=True)}
    for name, df in outs.items():
        p = OUT / name
        df.to_csv(p, index=False, float_format="%.6g", lineterminator="\n")
        print(f"wrote {p}")
        print(df.to_string(index=False))
    print("inputs read: " + ", ".join(S._READ[:3]) + f", ... ({len(S._READ)} files)")


if __name__ == "__main__":
    main()
