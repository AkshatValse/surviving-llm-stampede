"""r15 REPLICATE-EDGE (EXPLORATORY): same-plan replicates of the 2.5 x from-empty edge, A100 300k SGLang FCFS cell.

Question: is the 2.5 x from-empty edge fixed by the workload path, or does the same plan escape on some runs and not others
(noise-induced escape at a fixed workload)? The two runs that define the edge are re-run on their identical plans: seed 0
(collapsed at about 1600 s, job 17084754, nova22-gpu-1) and seed 4 (stable for 3000 s, job 17168507, nova22-gpu-3), in two
MODE=cap jobs with SEEDS "0 4 0" and "4 0 4" (CAP_RUN_S 3000, MULTS 2.5; the job glue flushes and verifies between runs).

Every number used here comes from the FROZEN rule file configs/r15_edge_replicate.yaml (status must be FROZEN):

* per run (originals included), the data-B D3 definition (scratch d3d5.py, applied unchanged): follow-up hit fraction (ok
  turns > 1, cached / prompt tokens > 0.5) in 100 s bins by completion time, rolling 300 s windows (3 bins, >= 5 turns, window
  start = bin start - 200 s). UNSTABLE iff a valid window starting at or after 600 s has hit <= 0.2, an earlier valid window
  had hit >= 0.6, and no valid later window reaches >= 0.5 (tau = start of the first such window); STABLE otherwise.
  The registered E0b stability verdict (analysis.hysteresis.stable_verdict, as ``analysis.summarize stable``) is recorded
  next to it for comparison only.
* manipulation check: the run's plan.csv equals the original's (same rows; sid, origin, idx, n_turns identical; arrival_s and
  tool_time_total_s within 1e-9 s). Validity: finished full-length run, verified start state, effective config equal to the
  original's except the job-specific keys, cell hardware / label, clean git state, engine not shown to differ (server_args of
  the job's server.log except port and random_seed, the banner's run parameters incl. REFRESH, pip freezes, HF snapshot, when
  the job log dir is present).
* verdict: PLAN-CONDITIONAL ESCAPE iff a plan's runs disagree, the original counted as a 4th replicate (whatever the
  replicate counts); else REPRODUCIBLE iff seed 0 UNSTABLE and seed 4 STABLE in all of >= 3 valid replicates each; else
  INCOMPLETE iff a plan has < 2 valid replicates; else CONSISTENT-PARTIAL. A disagreement is located: WITHIN-GPU (same node
  and PCI Bus-Id), WITHIN-NODE, or ACROSS-NODES-ONLY (outcome constant within every node; a node effect, not noise at a fixed
  workload). Descriptive: whether the NEW runs of a plan disagree among themselves, and where (an original-vs-new
  disagreement is also confounded with the date and the job).

The cell is exploratory (chosen after reading the E0b data; MODE=cap has no registration branch in the job glue) and cannot
be decisive.

CLI:  python -m analysis.r15_edge classify --run-dirs RUN [RUN ...] [--rule configs/r15_edge_replicate.yaml]
                                           [--params configs/agentload_analysis.yaml] [--out-root results]
      python -m analysis.r15_edge originals [--rule ...]        # the two originals under the rule (prints, writes nothing)
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
RULE = "configs/r15_edge_replicate.yaml"
PARAMS = "configs/agentload_analysis.yaml"
PLANS = (0, 4)
UNSTABLE, STABLE = "UNSTABLE", "STABLE"
REPRODUCIBLE, ESCAPE, PARTIAL, INCOMPLETE, RULE_ERROR = (
    "REPRODUCIBLE", "PLAN-CONDITIONAL ESCAPE", "CONSISTENT-PARTIAL", "INCOMPLETE", "RULE-ERROR")
LOCATION_ORDER = ("WITHIN-GPU", "WITHIN-NODE", "ACROSS-NODES-ONLY")
# config_effective.yaml keys that legitimately differ between a replicate and its original (job-specific)
ALLOWED_CONFIG_DIFFS = ("server.base_url", "workload.content_salt", "arrivals.lambda_ref", "meta.engine_label",
                        "meta.start_state_detail")
SERVER_ARGS_IGNORED = ("port", "random_seed")
ENGINE_FILES = ("pip_freeze_sglang.txt", "pip_freeze_swapp.txt", "hf_snapshot.txt")
# job banner "--- run parameters" keys that must equal the original job's (REFRESH is an engine env var, not a server arg)
BANNER_KEYS = ("ENGINE", "MODE", "POLICY", "REFRESH", "LPM_INF", "RADIX", "KV_TOKENS", "CONTEXT_LEN", "OUTPUT_FEEDBACK",
               "REQUEST_TOKEN_IDS", "STRICT_FLUSH", "STRICT_FLAGS", "MODEL", "SERVED_MODEL", "HF_REVISION", "HF_HOME", "MULTS")
PLAN_TOL_S = 1e-9


# ============================================================================================ rule file
def _path(p: str | Path) -> Path:
    p = Path(p)
    if p.is_absolute() or p.exists():
        return p
    return REPO / p


def load_rule(path: str | Path = RULE) -> Dict[str, Any]:
    rule = yaml.safe_load(_path(path).read_text(encoding="utf-8"))
    if not isinstance(rule, dict) or rule.get("status") != "FROZEN":
        raise ValueError(f"{path}: status is not FROZEN")
    if rule.get("exploratory") is not True:
        raise ValueError(f"{path}: the REPLICATE-EDGE cell is exploratory (exploratory: true)")
    for k in ("cell", "jobs", "originals", "per_run_rule", "verdict"):
        if k not in rule:
            raise ValueError(f"{path}: missing {k}")
    if sorted(int(s) for s in rule["originals"]) != list(PLANS):
        raise ValueError(f"{path}: originals must be the plans {PLANS}")
    return rule


# ============================================================================================ per-run rule
def hit_bins(run_dir: str | Path, bin_s: float = 100.0) -> Tuple[pd.DataFrame, float]:
    """Follow-up turns and hits per 100 s completion-time bin (data-B extract.py): ok rows with turn > 1; hit iff
    cached_tokens / max(prompt_tokens, 1) > 0.5; bins 0 .. ceil(t_end / bin_s) - 1, completions at or after the last edge
    in the last bin. t_end = meta.outcome.t_end_s, else run.duration_s."""
    d = Path(run_dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((d / "config_effective.yaml").read_text(encoding="utf-8")) or {}
    dur = float((cfg.get("run") or {}).get("duration_s") or meta.get("duration_s_configured") or 0.0)
    t_end = float((meta.get("outcome") or {}).get("t_end_s") or dur)
    r = pd.read_csv(d / "requests.csv", usecols=["turn", "t_complete", "status", "prompt_tokens", "cached_tokens"])
    w = r[(r["status"] == "ok") & (r["turn"] > 1) & r["t_complete"].notna()]
    hit = (w["cached_tokens"] / w["prompt_tokens"].clip(lower=1)) > 0.5
    nb = max(int(math.ceil(t_end / bin_s)), 1)
    idx = np.clip((w["t_complete"].to_numpy(dtype=float) // bin_s).astype(int), 0, nb - 1)
    n = np.bincount(idx, minlength=nb)
    h = np.bincount(idx, weights=hit.to_numpy().astype(float), minlength=nb)
    return pd.DataFrame({"t0": np.arange(nb) * bin_s, "n": n, "hits": h}), t_end


def rolling_windows(bins: pd.DataFrame, pr: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(window start, hit fraction or NaN, follow-up turns) of the rolling windows of ``window_bins`` bins ending at each bin."""
    k, bin_s, nmin = int(pr["window_bins"]), float(pr["bin_s"]), int(pr["min_turns_per_window"])
    b = bins.sort_values("t0").reset_index(drop=True)
    n = b["n"].rolling(k, min_periods=k).sum().to_numpy(dtype=float)
    h = b["hits"].rolling(k, min_periods=k).sum().to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        hf = np.where(n >= nmin, h / np.clip(n, 1, None), np.nan)
    return b["t0"].to_numpy(dtype=float) - (k - 1) * bin_s, hf, n


def classify_series(ws: Sequence[float], hf: Sequence[float], pr: Dict[str, Any]) -> Dict[str, Any]:
    """The per-run rule on a rolling-window series (NaN = invalid window, skipped)."""
    ws, hf = np.asarray(ws, dtype=float), np.asarray(hf, dtype=float)
    warm, low = float(pr["warm_s"]), float(pr["collapse_hit_at_most"])
    good, rec = float(pr["good_hit_at_least"]), float(pr["recover_hit_at_least"])
    valid = ~np.isnan(hf)
    good_seen, tau, i_tau = False, None, None
    for i in range(len(hf)):
        if not valid[i]:
            continue
        if ws[i] < warm:
            good_seen = good_seen or bool(hf[i] >= good)
            continue
        good_seen = good_seen or bool(hf[i] >= good)
        if good_seen and hf[i] <= low:
            later = hf[i + 1:]
            later = later[~np.isnan(later)]
            if not np.any(later >= rec):
                tau, i_tau = float(ws[i]), i
                break
    label = UNSTABLE if tau is not None else STABLE
    after = valid & (ws >= warm)
    low_after = np.nonzero(after & (hf <= low))[0]
    if label == UNSTABLE:
        kind = None
    elif not np.any(valid & (hf >= good)):
        kind = "never_good"
    elif len(low_after):
        j = int(low_after[0])
        prior_good = bool(np.any(valid[:j] & (hf[:j] >= good)))
        kind = "dipped_and_recovered" if prior_good else "low_without_prior_good"
    else:
        kind = "good"
    sub = hf[after]
    sub = sub[~np.isnan(sub)]
    pre = hf[:i_tau] if i_tau is not None else hf
    pre = pre[~np.isnan(pre)]
    below05 = np.nonzero(after & (hf < rec))[0]
    return {"label": label, "tau_s": tau, "stable_kind": kind, "n_windows_valid": int(valid.sum()),
            "max_hit_before_tau": float(pre.max()) if len(pre) else float("nan"),
            "min_hit_after_warm": float(sub.min()) if len(sub) else float("nan"),
            "last_window_hit": float(hf[valid][-1]) if valid.any() else float("nan"),
            "first_window_below_recover_after_warm_s": float(ws[below05[0]]) if len(below05) else None,
            "n_windows_below_recover_after_warm": int(len(below05))}


def coarse_string(bins: pd.DataFrame, block_s: float = 300.0, nmin: int = 5) -> str:
    """One character per non-overlapping 300 s block: floor(10 hit), X if >= 0.95, '.' if < nmin turns (descriptive)."""
    g = (bins["t0"] // block_s).astype(int)
    n3, h3 = bins["n"].groupby(g).sum(), bins["hits"].groupby(g).sum()
    return "".join("." if n < nmin else ("X" if h / n >= 0.95 else str(int(10 * h / n))) for n, h in zip(n3, h3))


def classify_bins(bins: pd.DataFrame, pr: Dict[str, Any]) -> Dict[str, Any]:
    ws, hf, _ = rolling_windows(bins, pr)
    out = classify_series(ws, hf, pr)
    out["coarse_300s"] = coarse_string(bins, nmin=int(pr["min_turns_per_window"]))
    return out


# ============================================================================================ run facts and checks
def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _flat(d: Any, pre: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict) and v:
            out.update(_flat(v, f"{pre}{k}."))
        else:
            out[f"{pre}{k}"] = v
    return out


def find_job_dir(run_dir: str | Path, job_id: Optional[str]) -> Optional[Path]:
    """<results root>/nova_job_logs/<job>-<ts> of the job that wrote ``run_dir`` (root = the run dir's grandparent)."""
    if not job_id:
        return None
    d = Path(run_dir)
    cands = sorted((d.parent.parent / "nova_job_logs").glob(f"{job_id}-*"))
    if len(cands) <= 1:
        return cands[0] if cands else None
    for c in cands:                                    # several log dirs of one job id: the one that lists this run dir
        for f in c.glob("run_dirs_*.txt"):
            if d.name in f.read_text(encoding="utf-8", errors="replace"):
                return c
    return cands[-1]


_BUS = re.compile(r"\|\s*\d+\s+(NVIDIA[^|]*?)\s{2,}\S+\s*\|\s*([0-9A-Fa-f]{8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-9A-Fa-f])\s")


def gpu_of_job(job_dir: Optional[Path]) -> Dict[str, Optional[str]]:
    """GPU name and PCI Bus-Id from the job banner's nvidia-smi table (first GPU row; every job has one GPU)."""
    if job_dir is None or not (job_dir / "banner.txt").exists():
        return {"gpu_name": None, "gpu_bus_id": None}
    for line in (job_dir / "banner.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        m = _BUS.search(line)
        if m:
            return {"gpu_name": m.group(1).strip(), "gpu_bus_id": m.group(2).upper()}
    return {"gpu_name": None, "gpu_bus_id": None}


def server_args(job_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    """The ``server_args={...}`` dict SGLang logs at startup (first occurrence in the job's server.log), or None."""
    if job_dir is None or not (job_dir / "server.log").exists():
        return None
    with open(job_dir / "server.log", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.search(r"server_args=(\{.*\})\s*$", line)
            if m:
                try:
                    return ast.literal_eval(m.group(1))
                except (ValueError, SyntaxError):
                    return None
    return None


def banner_params(job_dir: Optional[Path]) -> Optional[Dict[str, str]]:
    """KEY=VALUE pairs of the job banner's "--- run parameters" block (quoted values unquoted), or None."""
    if job_dir is None or not (job_dir / "banner.txt").exists():
        return None
    out: Dict[str, str] = {}
    inside = False
    for line in (job_dir / "banner.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- run parameters"):
            inside = True
            continue
        if inside and line.startswith("---"):
            break
        if inside:
            for k, v in re.findall(r"\b([A-Z][A-Z0-9_]*)=(\"[^\"]*\"|\S*)", line):
                out.setdefault(k, v.strip('"'))
    return out or None


def engine_identity(job_dir: Optional[Path], orig_job_dir: Optional[Path]) -> Dict[str, Any]:
    """verified True/False, or None when either job log dir (or a server_args line) is missing."""
    out: Dict[str, Any] = {"verified": None, "job_dir": str(job_dir) if job_dir else None, "differing_server_args": [],
                           "differing_banner_params": [], "files_equal": {}}
    a, b = server_args(job_dir), server_args(orig_job_dir)
    if a is None or b is None:
        out["reason"] = "job log dir or server_args line missing"
        return out
    diff = sorted(k for k in set(a) | set(b) if k not in SERVER_ARGS_IGNORED and a.get(k) != b.get(k))
    out["differing_server_args"] = diff
    ba, bb = banner_params(job_dir) or {}, banner_params(orig_job_dir) or {}
    out["differing_banner_params"] = sorted(k for k in BANNER_KEYS if ba.get(k) != bb.get(k))
    ok = not diff and not out["differing_banner_params"]
    for f in ENGINE_FILES:
        fa, fb = job_dir / f, orig_job_dir / f
        if fa.exists() and fb.exists():
            eq = fa.read_bytes().replace(b"\r\n", b"\n") == fb.read_bytes().replace(b"\r\n", b"\n")
        else:
            eq = None
        out["files_equal"][f] = eq
        ok = ok and eq is not False
    out["verified"] = bool(ok)
    return out


def compare_plans(a: pd.DataFrame, b: pd.DataFrame, tol: float = PLAN_TOL_S) -> Dict[str, Any]:
    out: Dict[str, Any] = {"rows": int(len(a)), "rows_original": int(len(b))}
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        out.update(equal=False, reason="row count or columns differ")
        return out
    ints = all((a[c].astype(str).to_numpy() == b[c].astype(str).to_numpy()).all() for c in ("sid", "origin", "idx", "n_turns"))
    da = float(np.max(np.abs(a["arrival_s"].to_numpy(float) - b["arrival_s"].to_numpy(float)))) if len(a) else 0.0
    dt = float(np.max(np.abs(a["tool_time_total_s"].to_numpy(float) - b["tool_time_total_s"].to_numpy(float)))) if len(a) else 0.0
    out.update(ids_and_turns_identical=bool(ints), max_abs_arrival_diff_s=da, max_abs_tool_total_diff_s=dt,
               equal=bool(ints and da <= tol and dt <= tol))
    return out


def plan_check(run_dir: str | Path, orig_dir: str | Path, tol: float = PLAN_TOL_S) -> Dict[str, Any]:
    pa, pb = Path(run_dir) / "plan.csv", _path(orig_dir) / "plan.csv"
    if not pa.exists():
        return {"equal": False, "reason": "plan.csv missing", "bytes_equal": False}
    out = compare_plans(pd.read_csv(pa, float_precision="round_trip"), pd.read_csv(pb, float_precision="round_trip"), tol)
    out["bytes_equal"] = pa.read_bytes().replace(b"\r\n", b"\n") == pb.read_bytes().replace(b"\r\n", b"\n")
    return out


def config_check(run_dir: str | Path, orig_dir: str | Path, rule: Dict[str, Any]) -> List[str]:
    """Problems of the effective config / resolved rate against the original's (empty list = equal where it must be)."""
    probs: List[str] = []
    fa = _flat(yaml.safe_load((Path(run_dir) / "config_effective.yaml").read_text(encoding="utf-8")))
    fb = _flat(yaml.safe_load((_path(orig_dir) / "config_effective.yaml").read_text(encoding="utf-8")))
    for k in sorted(set(fa) | set(fb)):
        if k in ALLOWED_CONFIG_DIFFS or k in ("meta.start_state_verified",):
            continue
        if fa.get(k) != fb.get(k):
            probs.append(f"config {k}: {fa.get(k)!r} != original {fb.get(k)!r}")
    meta = _read_json(Path(run_dir) / "meta.json")
    c = rule["cell"]
    if meta.get("lambda_ref_resolved") != c["lambda_ref"]:
        probs.append(f"lambda_ref_resolved {meta.get('lambda_ref_resolved')!r} != {c['lambda_ref']!r}")
    if meta.get("resolved_rate_sessions_per_s") != c["resolved_rate_sessions_per_s"]:
        probs.append(f"resolved rate {meta.get('resolved_rate_sessions_per_s')!r} != {c['resolved_rate_sessions_per_s']!r}")
    return probs


def run_facts(run_dir: str | Path) -> Dict[str, Any]:
    d = Path(run_dir)
    meta = _read_json(d / "meta.json")
    cfg = yaml.safe_load((d / "config_effective.yaml").read_text(encoding="utf-8")) or {}
    out = meta.get("outcome") or {}
    job = (meta.get("slurm_env") or {}).get("SLURM_JOB_ID")
    jd = find_job_dir(d, job)
    salt = (cfg.get("workload") or {}).get("content_salt")
    return {"run_dir": str(d).replace("\\", "/"), "seed": int((cfg.get("run") or {}).get("seed", meta.get("seeds", [-1])[0])),
            "rate_mult": (cfg.get("arrivals") or {}).get("rate_mult"), "engine_label": meta.get("engine_label"),
            "job": job, "node": meta.get("hostname"), **gpu_of_job(jd), "job_dir": str(jd).replace("\\", "/") if jd else None,
            "commit": (meta.get("git") or {}).get("commit"), "git_dirty": (meta.get("git") or {}).get("dirty"),
            "content_salt": salt, "run_position": salt, "start_time": meta.get("start_time"),
            "status": meta.get("status"), "abort_reason": out.get("abort_reason"), "t_end_s": out.get("t_end_s"),
            "start_state_verified": meta.get("start_state_verified"), "hardware": meta.get("hardware"),
            "n_sessions_planned": meta.get("n_sessions_planned"), "requests_ok": out.get("requests_ok"),
            "requests_error": out.get("requests_error"), "sessions_completed": out.get("sessions_completed"),
            "sessions_cancelled": out.get("sessions_cancelled"), "max_inflight_seen": out.get("max_inflight_seen")}


def registered_stable(run_dir: str | Path, params: Any) -> Dict[str, Any]:
    """The registered E0b from-empty verdict, exactly as ``analysis.summarize stable`` computes it (comparison only)."""
    from .hysteresis import stable_verdict
    from .load import load_run
    from .windows import queue_trace
    run = load_run(str(run_dir))
    v = stable_verdict(run, queue_trace(run, params), params)
    return {"stable_registered": bool(v["stable"]), "final_queue": v["final_queue"], "trend_rise": v["trend_rise"],
            "queue_source": v["queue_source"]}


def validity(facts: Dict[str, Any], plan: Dict[str, Any], cfg_probs: List[str], eng: Dict[str, Any],
             rule: Dict[str, Any]) -> List[str]:
    """Reasons a NEW run does not count as a replicate (empty = counts)."""
    c, probs = rule["cell"], []
    if facts["seed"] not in PLANS:
        probs.append(f"seed {facts['seed']} is not a plan of this cell")
    if not plan.get("equal"):
        probs.append(f"manipulation check failed: plan.csv differs from the original's ({plan.get('reason', 'values')})")
    if facts["status"] != "finished" or facts["abort_reason"] is not None:
        probs.append(f"run not finished cleanly (status {facts['status']}, abort {facts['abort_reason']})")
    if facts["t_end_s"] is None or float(facts["t_end_s"]) < float(c["duration_s"]) - 1.0:
        probs.append(f"run shorter than {c['duration_s']} s (t_end {facts['t_end_s']})")
    if facts["start_state_verified"] is not True:
        probs.append("start state not verified (canary check after the flush)")
    if facts["hardware"] != c["hardware"]:
        probs.append(f"hardware {facts['hardware']!r} != {c['hardware']!r}")
    if facts["engine_label"] != c["engine_label"]:
        probs.append(f"engine_label {facts['engine_label']!r} != {c['engine_label']!r}")
    if facts["git_dirty"] is not False:
        probs.append(f"git state of the clone not clean (dirty={facts['git_dirty']!r})")
    if facts.get("rate_mult") != c["rate_mult"]:
        probs.append(f"rate_mult {facts.get('rate_mult')!r} != {c['rate_mult']!r}")
    probs += cfg_probs
    if eng.get("verified") is False:
        probs.append(f"engine differs from the original job's: server_args {eng.get('differing_server_args')}, "
                     f"banner {eng.get('differing_banner_params')}, files {eng.get('files_equal')}")
    return probs


def classify_run(run_dir: str | Path, rule: Dict[str, Any], params: Any = None, *, role: Optional[str] = None,
                 registered: bool = True) -> Dict[str, Any]:
    """Every per-run quantity: facts, the r15 label, the registered verdict, and (for a new run) the checks and validity."""
    pr = rule["per_run_rule"]
    facts = run_facts(run_dir)
    bins, t_end = hit_bins(run_dir, float(pr["bin_s"]))
    row: Dict[str, Any] = {**facts, **classify_bins(bins, pr), "t_end_used_s": t_end}
    if registered:
        row.update(registered_stable(run_dir, params))
    seed = facts["seed"]
    orig = rule["originals"].get(str(seed)) if seed in PLANS else None
    is_orig = bool(orig and _path(orig["run_dir"]).resolve() == Path(run_dir).resolve())
    row["role"] = role or ("original" if is_orig else "replicate")
    if row["role"] == "original" or orig is None:
        row.update(counted=False, problems="" if orig is not None else f"seed {seed} is not a plan of this cell")
        return row
    plan = plan_check(run_dir, orig["run_dir"])
    cprobs = config_check(run_dir, orig["run_dir"], rule)
    eng = engine_identity(_path(facts["job_dir"]) if facts["job_dir"] else None, _path(orig["job_log_dir"]))
    probs = validity(facts, plan, cprobs, eng, rule)
    row.update(plan_equal=plan.get("equal"), plan_bytes_equal=plan.get("bytes_equal"),
               plan_max_abs_tool_total_diff_s=plan.get("max_abs_tool_total_diff_s"), engine_verified=eng.get("verified"),
               engine_differing_server_args=";".join(eng.get("differing_server_args") or []),
               engine_differing_banner_params=";".join(eng.get("differing_banner_params") or []),
               content_salt_equals_original=facts["content_salt"] == orig["content_salt"],
               counted=not probs, problems=" | ".join(probs))
    return row


# ============================================================================================ verdict
def disagreement_location(runs: Sequence[Dict[str, Any]], label_key: str = "label") -> Dict[str, Any]:
    by_node: Dict[Any, set] = defaultdict(set)
    by_gpu: Dict[Any, set] = defaultdict(set)
    for r in runs:
        by_node[r.get("node")].add(r[label_key])
        if r.get("gpu_bus_id"):
            by_gpu[(r.get("node"), r.get("gpu_bus_id"))].add(r[label_key])
    gpus = sorted(f"{k[0]}/{k[1]}" for k, v in by_gpu.items() if len(v) > 1)
    nodes = sorted(str(k) for k, v in by_node.items() if len(v) > 1)
    level = "WITHIN-GPU" if gpus else "WITHIN-NODE" if nodes else "ACROSS-NODES-ONLY"
    return {"level": level, "gpus_with_disagreement": gpus, "nodes_with_disagreement": nodes,
            "gpu_ids_complete": all(bool(r.get("gpu_bus_id")) for r in runs),
            "outcomes_by_node": {str(k): sorted(v) for k, v in by_node.items()}}


def verdict(rows: Sequence[Dict[str, Any]], originals: Dict[int, Dict[str, Any]], rule: Dict[str, Any],
            label_key: str = "label") -> Dict[str, Any]:
    """The frozen verdict over the counted new runs (``counted``) and the two originals (keyed by plan)."""
    v = rule["verdict"]
    nmin, nrep = int(v["min_replicates_per_plan"]), int(v["replicates_for_reproducible"])
    known = {int(s): o["known_outcome"] for s, o in rule["originals"].items()}
    plans: Dict[str, Any] = {}
    for s in PLANS:
        o = originals[s]
        reps = [r for r in rows if r.get("counted") and int(r["seed"]) == s]
        runs = [o] + reps
        labels = [r[label_key] for r in runs]
        dis = len(set(labels)) > 1
        dis_new = len({r[label_key] for r in reps}) > 1
        plans[str(s)] = {
            "original": o[label_key], "original_known_outcome": known[s], "n_valid_replicates": len(reps),
            "replicates_unstable": sum(r[label_key] == UNSTABLE for r in reps),
            "replicates_stable": sum(r[label_key] == STABLE for r in reps),
            "disagree": dis, "location": disagreement_location(runs, label_key) if dis else None,
            # descriptive: the new runs alone (same date, commit and engine build); a disagreement with the original only is
            # also confounded with the date and the job
            "disagree_among_new_runs": dis_new,
            "location_among_new_runs": disagreement_location(reps, label_key) if dis_new else None,
            "runs": [{k: r.get(k) for k in ("role", "job", "node", "gpu_bus_id", "run_position", "content_salt", label_key,
                                            "tau_s", "run_dir")} for r in runs]}
    originals_ok = all(plans[str(s)]["original"] == known[s] for s in PLANS) if label_key == "label" else True
    dis_any = any(p["disagree"] for p in plans.values())
    # order as designed: a disagreement is an ESCAPE whatever the replicate counts; INCOMPLETE only without one
    if not originals_ok:
        overall = RULE_ERROR
    elif dis_any:
        overall = ESCAPE
    elif all(p["n_valid_replicates"] >= nrep for p in plans.values()) and plans["0"]["original"] == UNSTABLE \
            and plans["4"]["original"] == STABLE:
        overall = REPRODUCIBLE
    elif any(p["n_valid_replicates"] < nmin for p in plans.values()):
        overall = INCOMPLETE
    else:
        overall = PARTIAL
    levels = [p["location"]["level"] for p in plans.values() if p["disagree"]]
    strongest = min(levels, key=LOCATION_ORDER.index) if levels else None
    return {"verdict": overall, "disagreement_observed": dis_any, "disagreement_level": strongest,
            "noise_induced_escape_at_fixed_workload": bool(overall == ESCAPE and strongest in ("WITHIN-GPU", "WITHIN-NODE")),
            "disagreement_among_new_runs_observed": any(p["disagree_among_new_runs"] for p in plans.values()),
            "originals_match_known_outcomes": originals_ok, "plans": plans, "label_key": label_key,
            "exploratory": True, "not_decisive": rule["verdict"]["not_decisive"]}


def classify(run_dirs: Iterable[str | Path], rule: Dict[str, Any], params: Any = None, *,
             registered: bool = True) -> Dict[str, Any]:
    """Classify the two originals and the given runs (originals among them are recognised and not counted twice)."""
    orig_rows = {s: classify_run(_path(rule["originals"][str(s)]["run_dir"]), rule, params, role="original",
                                 registered=registered) for s in PLANS}
    seen = {Path(r["run_dir"]).resolve() for r in orig_rows.values()}
    rows: List[Dict[str, Any]] = []
    for d in run_dirs:
        p = _path(d).resolve()
        if p in seen:
            continue
        seen.add(p)
        rows.append(classify_run(p, rule, params, registered=registered))
    # job layout (descriptive): the seed order of each job by run position must be one of the planned layouts
    layouts = {tuple(int(x) for x in j["seeds"]): j["name"] for j in rule["jobs"]}
    by_job: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_job[str(r["job"])].append(r)
    jobs = {}
    for j, rs in by_job.items():
        order = tuple(int(r["seed"]) for r in sorted(rs, key=lambda r: (r["run_position"] or 0)))
        jobs[j] = {"seeds_by_position": list(order), "planned_job": layouts.get(order),
                   "nodes": sorted({str(r["node"]) for r in rs}), "gpus": sorted({str(r.get("gpu_bus_id")) for r in rs})}
    main = verdict(rows, orig_rows, rule, "label")
    reg = None
    if registered:
        for r in [*orig_rows.values(), *rows]:
            r["label_registered"] = STABLE if r["stable_registered"] else UNSTABLE
        reg = verdict(rows, orig_rows, rule, "label_registered")
    return {"rows": rows, "originals": orig_rows, "jobs": jobs, "verdict": main,
            "verdict_with_registered_stable_rule_descriptive": reg}


COLS = ("role", "seed", "job", "node", "gpu_bus_id", "run_position", "content_salt", "label", "tau_s", "stable_kind",
        "max_hit_before_tau", "min_hit_after_warm", "last_window_hit", "coarse_300s", "stable_registered", "final_queue",
        "trend_rise", "counted", "problems", "plan_equal", "plan_bytes_equal", "plan_max_abs_tool_total_diff_s",
        "engine_verified", "engine_differing_server_args", "engine_differing_banner_params", "content_salt_equals_original",
        "engine_label", "commit",
        "git_dirty", "start_state_verified", "status", "abort_reason", "t_end_s", "requests_ok", "requests_error",
        "sessions_completed", "sessions_cancelled", "max_inflight_seen", "start_time", "job_dir", "run_dir")


def _jd(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r15_edge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="per-run UNSTABLE / STABLE, manipulation and validity checks, the frozen verdict")
    c.add_argument("--run-dirs", nargs="+", required=True)
    c.add_argument("--rule", default=RULE)
    c.add_argument("--params", default=PARAMS)
    c.add_argument("--out-root", default="results")
    o = sub.add_parser("originals", help="the two original runs under the frozen rule (prints; writes nothing)")
    o.add_argument("--rule", default=RULE)
    o.add_argument("--params", default=PARAMS)
    args = ap.parse_args(argv)
    from .params import load_params
    rule = load_rule(args.rule)
    params = load_params(_path(args.params), [])
    if args.cmd == "originals":
        for s in PLANS:
            r = classify_run(_path(rule["originals"][str(s)]["run_dir"]), rule, params, role="original")
            print(json.dumps({k: r.get(k) for k in COLS if k in r}, default=_jd))
        return 0
    from agentload.runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta
    t0 = datetime.now()
    git = git_info(REPO)
    res = classify(args.run_dirs, rule, params)
    d = new_result_dir(args.out_root, "agentload_analysis_r15_edge")
    allrows = [*res["originals"].values(), *res["rows"]]
    df = pd.DataFrame(allrows)
    df[[k for k in COLS if k in df.columns]].to_csv(d / "r15_edge_runs.csv", index=False)
    out = {k: res[k] for k in ("verdict", "verdict_with_registered_stable_rule_descriptive", "jobs")}
    out["rule_file"] = str(args.rule)
    (d / "r15_edge_verdict.json").write_text(json.dumps(out, indent=2, default=_jd))
    write_meta(d, build_meta(experiment="agentload_analysis_r15_edge",
                             argv=[sys.executable, "-m", "analysis.r15_edge", *(argv if argv is not None else sys.argv[1:])],
                             seeds=sorted({int(r["seed"]) for r in allrows}), hardware=default_hardware(), git=git, t_start=t0,
                             t_end=datetime.now(), status="finished",
                             extra={"run_dirs": [str(x) for x in args.run_dirs], "rule": str(args.rule),
                                    "params": str(args.params), "exploratory": True}))
    v = res["verdict"]
    print(json.dumps({"verdict": v["verdict"], "disagreement_level": v["disagreement_level"],
                      "noise_induced_escape_at_fixed_workload": v["noise_induced_escape_at_fixed_workload"],
                      "plans": {s: {k: p[k] for k in ("original", "n_valid_replicates", "replicates_unstable",
                                                       "replicates_stable", "disagree", "disagree_among_new_runs")}
                                for s, p in v["plans"].items()}},
                     indent=2, default=_jd))
    for r in res["rows"]:
        if not r.get("counted"):
            print(f"NOT COUNTED: {r['run_dir']}: {r.get('problems')}", file=sys.stderr)
    print(f"r15 edge outputs: {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
