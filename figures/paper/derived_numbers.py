"""Derived numbers for the paper that no committed analysis reports directly (read-only on committed run data).

Writes three CSVs under paper/derived/ (the paper cites them through paper/NUMBERS.md):

  e2_burst_backlog.csv  per E2 BURST run: the backlog (sessions in the system, the verdict's backlog_trace.csv, 50 s bins)
                        after the burst and over the evaluation window, next to the registered slope test.
  e2_capped_drain.csv   per E2 CAPPED run: when the client-side gate queue first empties after the burst (sessions.csv:
                        arrival_s and t_admit), against the registered fluid drain estimate b / (mu(20) - lambda).
  e0b_hit.csv           per E0b run: the registered hit metric (ok turns with cached_tokens / prompt_tokens > 0.5, first
                        turns included, by completion time) over the whole run and over its two halves.
  e2_counts.csv         Wilson 95% intervals for the real E2 arm counts and the paired sign test on the hit metric.

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


def e2_capped_drain(runs: pd.DataFrame) -> pd.DataFrame:
    import yaml
    reg = yaml.safe_load(S.src(REG).read_text())
    pred = _find_pred(reg)      # the registration's capped_drain.predicted_drain_s_by_mult
    assert pred, "registration has no predicted_drain_s_by_mult"
    rows = []
    for _, r in runs[runs.arm == "capped"].iterrows():
        rel = f"{E2_PULL}/{r.run_dir}"
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


def e0b_hit() -> pd.DataFrame:
    st = pd.read_csv(S.src(E0B_STABLE))
    rows = []
    for _, r in st.sort_values("rate_mult").iterrows():
        rel = f"{E0B_PULL}/{r.run_dir}"
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


def e2_counts(runs: pd.DataFrame) -> pd.DataFrame:
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
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = pd.read_csv(S.src(f"{E2_VERDICT}/trap_v2_runs.csv"))
    assert len(runs) == 18, len(runs)
    trace = pd.read_csv(S.src(f"{E2_VERDICT}/backlog_trace.csv"))
    outs = {"e2_burst_backlog.csv": e2_burst_backlog(runs, trace),
            "e2_capped_drain.csv": e2_capped_drain(runs),
            "e0b_hit.csv": e0b_hit(),
            "e2_counts.csv": e2_counts(runs)}
    for name, df in outs.items():
        p = OUT / name
        df.to_csv(p, index=False, float_format="%.6g", lineterminator="\n")
        print(f"wrote {p}")
        print(df.to_string(index=False))
    print("inputs read: " + ", ".join(S._READ[:3]) + f", ... ({len(S._READ)} files)")


if __name__ == "__main__":
    main()
