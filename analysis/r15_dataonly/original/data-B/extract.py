"""data-B: extract per-run hit-fraction time series and state transitions from all
pulled real-engine runs (read-only over results/nova). Writes runs.csv and bins.parquet-like
CSV under this scratch dir.

Usage (Git Bash, from the arxiv worktree root):
  "C:/Users/Akshat/Desktop/Claude Code/.venvs/nova-research/Scripts/python.exe" \
     <scratch>/data-B/extract.py
"""
import json, os, re, sys, glob
import numpy as np, pandas as pd, yaml

ROOT = r"C:\Users\Akshat\Desktop\Claude Code\Nova-Research-wt\arxiv\results\nova"
OUT = os.path.dirname(os.path.abspath(__file__))
BIN = 100.0


def pool_tokens(d):
    p = os.path.join(d, "metrics_first.txt")
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"^sglang:max_total_num_tokens\{[^}]*\}\s+([0-9.eE+]+)", txt, re.M)
    if m:
        return float(m.group(1))
    m = re.search(r"^vllm:cache_config_info\{([^}]*)\}", txt, re.M)
    if m:
        lab = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        try:
            return float(lab.get("num_gpu_blocks")) * float(lab.get("block_size"))
        except Exception:
            return None
    return None


rows = []
bins_all = []
for req in sorted(glob.glob(os.path.join(ROOT, "**", "requests.csv"), recursive=True)):
    d = os.path.dirname(req)
    rel = os.path.relpath(d, ROOT).replace("\\", "/")
    parts = rel.split("/")
    cell = parts[0]
    stage = parts[-2]
    try:
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    except Exception:
        meta = {}
    try:
        cfg = yaml.safe_load(open(os.path.join(d, "config_effective.yaml"), encoding="utf-8")) or {}
    except Exception:
        cfg = {}
    arr = cfg.get("arrivals", {}) or {}
    gate = cfg.get("gate", {}) or {}
    wl = cfg.get("workload", {}) or {}
    run = cfg.get("run", {}) or {}
    mt = cfg.get("meta", {}) or {}
    burst = arr.get("burst")
    try:
        r = pd.read_csv(req, usecols=["sid", "turn", "t_send", "t_complete", "status",
                                       "prompt_tokens", "cached_tokens", "origin"])
    except Exception as e:
        print("skip", rel, e, file=sys.stderr)
        continue
    ok = r[r.status == "ok"].copy()
    dur = float(run.get("duration_s") or meta.get("duration_s_configured") or
                (ok.t_complete.max() if len(ok) else 0))
    t_end = (meta.get("outcome") or {}).get("t_end_s") or dur
    ok["hit"] = (ok.cached_tokens / ok.prompt_tokens.clip(lower=1)) > 0.5
    w = ok[ok.turn > 1]
    nb = int(np.ceil(t_end / BIN))
    edges = np.arange(nb + 1) * BIN
    idx = np.clip((w.t_complete.values // BIN).astype(int), 0, nb - 1)
    n = np.bincount(idx, minlength=nb)
    h = np.bincount(idx, weights=w.hit.values.astype(float), minlength=nb)
    # uncached tokens completed per bin (all turns)
    idx2 = np.clip((ok.t_complete.values // BIN).astype(int), 0, nb - 1)
    unc = np.bincount(idx2, weights=(ok.prompt_tokens - ok.cached_tokens.fillna(0)).values, minlength=nb)
    # in-flight requests at bin ends (client side), incl. never-completed
    ts = r.t_send.values
    tc = r.t_complete.fillna(np.inf).values
    tse = np.sort(ts[~np.isnan(ts)]); tce = np.sort(tc[~np.isnan(ts)])
    ends = edges[1:]
    infl = np.searchsorted(tse, ends, side="right") - np.searchsorted(tce, ends, side="right")
    # active sessions at bin ends
    try:
        s = pd.read_csv(os.path.join(d, "sessions.csv"), usecols=["arrival_s", "t_end"])
        sa = np.sort(s.arrival_s.values); se = np.sort(s.t_end.fillna(np.inf).values)
        act = np.searchsorted(sa, ends, side="right") - np.searchsorted(se, ends, side="right")
    except Exception:
        act = np.full(nb, np.nan)
    b = pd.DataFrame({"t0": edges[:-1], "n": n, "hits": h, "unc_tok": unc,
                      "inflight": infl, "active": act})
    b["hf"] = np.where(b.n > 0, b.hits / b.n.clip(lower=1), np.nan)
    b["run"] = rel
    bins_all.append(b)
    out = meta.get("outcome") or {}
    rows.append(dict(
        run=rel, cell=cell, stage=stage,
        job=(meta.get("slurm_env") or {}).get("SLURM_JOB_ID"),
        host=meta.get("hostname"), hardware=meta.get("hardware") or mt.get("hardware"),
        model=(cfg.get("server") or {}).get("model"),
        engine_label=meta.get("engine_label") or mt.get("engine_label"),
        arm=meta.get("arm") or mt.get("arm") or "",
        pool=pool_tokens(d), rate_mult=arr.get("rate_mult"), arr_kind=arr.get("kind"),
        lambda_ref=meta.get("lambda_ref_resolved"),
        rate_sps=meta.get("resolved_rate_sessions_per_s"),
        burst=json.dumps(burst) if burst else "",
        t_burst=meta.get("analysis_t_burst_s"),
        arrivals_extra=json.dumps({k: v for k, v in arr.items() if k not in (
            "kind", "rate_mult", "lambda_ref", "uncached_tokens_ref", "burst", "analysis_t_burst_s")}),
        gate=json.dumps(gate) if gate else "",
        workload_extra=json.dumps({k: v for k, v in wl.items() if k not in (
            "prompt_mode", "initial_context_tokens", "new_prompt_tokens", "decode_tokens",
            "mean_turns", "max_turns", "tool_time_mean_s", "tool_time_dist", "token_id_low",
            "token_id_high", "output_feedback", "content_salt")}),
        seed=run.get("seed"), duration=dur, t_end=t_end, status=meta.get("status"),
        abort=out.get("abort_reason"), t_abort=out.get("t_abort_s"),
        prereg=meta.get("prereg_file") or mt.get("prereg_file"),
        notes=mt.get("notes"),
    ))
    print(rel, file=sys.stderr)

runs = pd.DataFrame(rows)
runs.to_csv(os.path.join(OUT, "runs.csv"), index=False)
pd.concat(bins_all).to_csv(os.path.join(OUT, "bins.csv"), index=False)
print(len(runs), "runs")
