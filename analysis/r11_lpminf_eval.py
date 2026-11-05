"""Engine-side evaluator of the L1 step-2 LPM-INF runs (cell sglang-lpminf), against the FROZEN endpoints.

Reads only git-tracked pulls and the frozen endpoint file configs/r11_lpminf_predict.yaml (tag r11-lpminf-pred); every
constant below comes from that file (it is read, not copied), except the paths of the pulls and the committed verdict
dirs, which are listed here. Read-only, zero GPU. Written 2026-10-31 after the three LPM-INF jobs ended; the endpoints and
the decision rule it applies were frozen before they were submitted.

Per run (INF and the CRN controls at 1.65 x, seeds 0-2: stock LPM sglang-lpm-r1 / -r0, FCFS sglang-fcfs-r1 (E2) / -r0):
  primary   token hit over W = [5700, 8700) (cached / prompt tokens of ok turns completing in W) and collapse := < 0.05
  trap_v2   the state from the committed burst2 verdict (registered rule, E2 overrides), uncached tokens/s ratio, slope
  latency   p50 / p99 of ok-turn latency (client send to response end) over W and over [1200, 8700)
  miss      latency p50 / p90 / p99 / max of miss turns (cached / prompt <= 0.5) completing in W; turns with latency > 600 s
  sessions  unfinished = sessions (base + burst) whose status is not 'completed' at the run end
  queue     sglang:num_queue_reqs max, share of post-burst samples > 128, longest stretch > 128
  manip.    scheduler cost: get_next_batch_to_run counter differenced over 60-s bins (s/s), in the bins whose mean queue
            is > 128; fraction of such bins >= 0.008 (FAIL if < 0.9; UNINFORMATIVE if no bin qualifies); plus the hook
            marker (lpm_inf_markers.txt, a pid other than the server pid with 128 -> 1000000000) and the self-test line
            of flag_check.txt (value 1e9, schedule_policy md5) for INF runs.

Usage:  python -m analysis.r11_lpminf_eval [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import io
import json
import math
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = "configs/r11_lpminf_predict.yaml"

# (pull, committed verdict dir with the registered trap_v2 rule and the E2 overrides)
PULLS: Tuple[Tuple[str, str], ...] = (
    ("results/nova/lpminf_1716874x_pulled_20261031-042548", "results/agentload_analysis_burst2/20261031-042736"),
    ("results/nova/r7_native_grid_vllm_pulled_20261025-145126", "results/agentload_analysis_burst2/20261025-144230"),
    ("results/nova/r7_native_grid_vllm_pulled_20261025-145126", "results/agentload_analysis_burst2/20261025-144233"),
    ("results/nova/r7_native_grid_vllm_pulled_20261025-145126", "results/agentload_analysis_burst2/20261025-144236"),
    ("results/nova/e2_170933xx_pulled_20261025-144558", "results/agentload_analysis_burst2/20261025-144012"),
)
LABELS = ("sglang-lpminf", "sglang-lpm-r1", "sglang-lpm-r0", "sglang-fcfs-r1", "sglang-fcfs-r0")
MULT = "1.65"
THRESHOLD = 128.0
T_BURST = 1200.0
LONG_SPAN = (1200.0, 8700.0)
HOOK_RE = re.compile(r"\[pm-lpminf-hook\] pid=(\d+) ppid=(\d+) \S+WAITING_QUEUE_PREFIX_MATCH_MAX (\d+) -> (\d+)")
SERVER_PID_RE = re.compile(r"server pid (\d+), log ")
SELFTEST_RE = re.compile(r"^lpm_inf_selftest value=(\d+) md5=([0-9a-f]+) hook_md5=([0-9a-f]+) active100=(\w+) active300=(\w+)")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _q(x: np.ndarray, q: float) -> float:
    return float(np.quantile(x, q)) if len(x) else float("nan")


def load_endpoints() -> dict:
    with open(ROOT / ENDPOINTS) as fh:
        ep = yaml.safe_load(fh)
    assert ep["status"] == "FROZEN", ep["status"]
    return ep


def read_metrics(p: Path) -> Tuple[np.ndarray, np.ndarray]:
    """(queue samples [t, v], get_next_batch_to_run counter samples [t, c]) from metrics.csv."""
    q: Dict[float, float] = {}
    g: Dict[float, float] = {}
    with open(p, newline="") as fh:
        header = fh.readline()
        keep = [ln for ln in fh if ("sglang:num_queue_reqs" in ln or "get_next_batch_to_run" in ln)]
    for r in csv.DictReader(io.StringIO(header + "".join(keep))):
        if r["name"] == "sglang:num_queue_reqs":
            q[float(r["t_s"])] = float(r["value"])
        elif r["name"] == "sglang:scheduler_stage_seconds_total" and 'category="get_next_batch_to_run"' in r["labels"]:
            g[float(r["t_s"])] = float(r["value"])
    return np.array(sorted(q.items())), np.array(sorted(g.items()))


def read_requests(p: Path) -> Dict[str, np.ndarray]:
    t, pt, ct, lat = [], [], [], []
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["status"] != "ok":
                continue
            t.append(float(r["t_complete"]))
            pt.append(float(r["prompt_tokens"] or 0))
            ct.append(float(r["cached_tokens"] or 0))
            lat.append(float(r["latency_s"]))
    return {"t": np.array(t), "pt": np.array(pt), "ct": np.array(ct), "lat": np.array(lat)}


def read_sessions(p: Path) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            out["n"] += 1
            out[f"status_{r['status']}"] += 1
            if r["status"] != "completed":
                out["unfinished"] += 1
                out[f"unfinished_{r['origin']}"] += 1
    return dict(out)


def sched_cost_bins(queue: np.ndarray, gnb: np.ndarray, bin_s: float) -> List[Tuple[float, float, float]]:
    """(bin start, mean queue, get_next_batch_to_run s/s) per bin [k*bin_s, (k+1)*bin_s); the rate is the counter's
    increase between its first and last sample inside the bin divided by their time difference."""
    out = []
    if len(queue) == 0 or len(gnb) == 0:
        return out
    kmax = int(max(queue[-1, 0], gnb[-1, 0]) // bin_s)
    for k in range(kmax + 1):
        a, b = k * bin_s, (k + 1) * bin_s
        qs = queue[(queue[:, 0] >= a) & (queue[:, 0] < b), 1]
        gs = gnb[(gnb[:, 0] >= a) & (gnb[:, 0] < b)]
        if len(qs) == 0 or len(gs) < 2 or gs[-1, 0] <= gs[0, 0]:
            continue
        out.append((a, float(qs.mean()), float((gs[-1, 1] - gs[0, 1]) / (gs[-1, 0] - gs[0, 0]))))
    return out


def hook_check(joblog: Path, outlog: Path) -> Dict[str, object]:
    """Manipulation check items (a) and (b) from the job's own files."""
    server_pid = None
    selftest = None
    hook_ok_line = None
    with open(outlog, errors="replace") as fh:
        for ln in fh:
            m = SERVER_PID_RE.search(ln)
            if m and server_pid is None:
                server_pid = m.group(1)
            m = SELFTEST_RE.match(ln.strip())
            if m and selftest is None:     # the first self-test line is the hooked one; the second is the control
                selftest = m.groups()
            if ln.startswith("lpm_inf hook ok:"):
                hook_ok_line = ln.strip()
    markers = []
    with open(joblog / "lpm_inf_markers.txt", errors="replace") as fh:
        for ln in fh:
            m = HOOK_RE.search(ln)
            if m:
                markers.append(m.groups())
    child = [mk for mk in markers if mk[0] != server_pid and mk[1] == server_pid and mk[2] == "128" and mk[3] == "1000000000"]
    srv_log_markers = 0
    with open(joblog / "server.log", errors="replace") as fh:
        for ln in fh:
            if "[pm-lpminf-hook]" in ln:
                srv_log_markers += 1
    return {
        "server_pid": server_pid,
        "markers": len(markers),
        "child_markers_1e9": len(child),
        "child_pids": ";".join(mk[0] for mk in child),
        "server_log_marker_lines": srv_log_markers,
        "selftest_value": selftest[0] if selftest else None,
        "selftest_md5": selftest[1] if selftest else None,
        "selftest_hook_md5": selftest[2] if selftest else None,
        "selftest_active300": selftest[4] if selftest else None,
        "hook_ok_line": hook_ok_line,
    }


def load_verdicts() -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for pull, vdir in PULLS:
        with open(ROOT / pull / vdir / "trap_v2_runs.csv", newline="") as fh:
            for r in csv.DictReader(fh):
                key = f"{pull}/{r['run_dir']}"
                r["_verdict_dir"] = f"{pull}/{vdir}"
                out[key] = r
    return out


def evaluate(ep: dict) -> List[Dict[str, object]]:
    W0, W1 = ep["primary"]["window_s"]
    cut = ep["primary"]["collapse_hit_below"]
    thr_cached = ep["secondaries"]["trap_v2"]["cached_frac_threshold"]
    long_wait = ep["secondaries"]["miss_turn_latency"]["long_wait_s"]
    mc = ep["manipulation_check"]
    verdicts = load_verdicts()
    rows: List[Dict[str, object]] = []
    for key, v in sorted(verdicts.items()):
        if v["label"] not in LABELS or v["arm"] != "burst" or v["rate_mult"] != MULT:
            continue
        pull = key.split("/results/agentload_e2_burst/")[0]
        rd = ROOT / key
        meta = json.load(open(rd / "meta.json"))
        job = str((meta.get("slurm_env") or {}).get("SLURM_JOB_ID", ""))
        req = read_requests(rd / "requests.csv")
        ses = read_sessions(rd / "sessions.csv")
        queue, gnb = read_metrics(rd / "metrics.csv")
        inW = (req["t"] >= W0) & (req["t"] < W1)
        inL = (req["t"] >= LONG_SPAN[0]) & (req["t"] < LONG_SPAN[1])
        frac = np.divide(req["ct"], req["pt"], out=np.zeros_like(req["ct"]), where=req["pt"] > 0)
        miss = frac <= thr_cached
        tok_hit = float(req["ct"][inW].sum() / req["pt"][inW].sum()) if inW.any() else float("nan")
        post = queue[queue[:, 0] >= T_BURST] if len(queue) else queue
        longest = cur = 0
        for _, val in post:
            cur = cur + 1 if val > THRESHOLD else 0
            longest = max(longest, cur)
        dt = float(np.median(np.diff(queue[:, 0]))) if len(queue) > 1 else float("nan")
        bins = sched_cost_bins(queue, gnb, mc["scheduler_cost_bin_s"])
        qual = [b for b in bins if b[1] > THRESHOLD]
        low = [b for b in bins if 20.0 <= b[1] <= THRESHOLD and b[0] >= T_BURST]
        n_pass = sum(1 for b in qual if b[2] >= mc["scheduler_cost_min_s_per_s"])
        frac_pass = n_pass / len(qual) if qual else float("nan")
        if not qual:
            sc_state = "UNINFORMATIVE"
        else:
            sc_state = "PASS" if frac_pass >= mc["scheduler_cost_min_pass_fraction"] else "FAIL"
        row: Dict[str, object] = {
            "label": v["label"], "seed": int(v["seed"]), "mult": v["rate_mult"], "job": job,
            "run_dir": key, "verdict_dir": v["_verdict_dir"], "plan_sha256": _sha256(rd / "plan.csv"),
            "git_commit": (meta.get("git") or {}).get("commit", ""), "t_end_s": float(v["t_end_s"]),
            "tok_hit_W": tok_hit, "collapse": bool(tok_hit < cut) if not math.isnan(tok_hit) else None,
            "turn_hit_W": float((~miss[inW]).mean()) if inW.any() else float("nan"), "n_turns_W": int(inW.sum()),
            "trap_v2_state": v["state"], "trap_v2_hit_eval": float(v["hit_eval"]),
            "uncached_tok_s_W": float(v["rate_uncached_tokens"]),
            "uncached_ratio": float(v["rate_uncached_tokens"]) / float(v["uncached_tokens_ref"]),
            "crit_a": v["crit_a"], "backlog_slope": float(v["backlog_slope"]), "slope_threshold": float(v["slope_threshold"]),
            "crit_b": v["crit_b"], "outstanding_end": float(v["outstanding_end"]), "hit_end": float(v["hit_end"]),
            "lat_p50_W": _q(req["lat"][inW], 0.5), "lat_p99_W": _q(req["lat"][inW], 0.99),
            "lat_p50_1200": _q(req["lat"][inL], 0.5), "lat_p99_1200": _q(req["lat"][inL], 0.99),
            "miss_n_W": int((inW & miss).sum()),
            "miss_lat_p50_W": _q(req["lat"][inW & miss], 0.5), "miss_lat_p90_W": _q(req["lat"][inW & miss], 0.9),
            "miss_lat_p99_W": _q(req["lat"][inW & miss], 0.99),
            "miss_lat_max_W": float(req["lat"][inW & miss].max()) if (inW & miss).any() else float("nan"),
            "n_lat_gt600": int((req["lat"] > long_wait).sum()), "lat_max": float(req["lat"].max()),
            "sessions": ses.get("n", 0), "unfinished": ses.get("unfinished", 0),
            "unfinished_base": ses.get("unfinished_base", 0), "unfinished_burst": ses.get("unfinished_burst", 0),
            "q_max": float(queue[:, 1].max()) if len(queue) else float("nan"),
            "q_frac_post_gt128": float((post[:, 1] > THRESHOLD).mean()) if len(post) else float("nan"),
            "q_longest_gt128_s": longest * dt, "q_mean_W": float(queue[(queue[:, 0] >= W0) & (queue[:, 0] < W1), 1].mean()),
            "sc_bins_q_gt128": len(qual), "sc_bins_pass": n_pass, "sc_frac_pass": frac_pass, "sc_state": sc_state,
            "sc_median_q_gt128": float(np.median([b[2] for b in qual])) if qual else float("nan"),
            "sc_min_q_gt128": float(min(b[2] for b in qual)) if qual else float("nan"),
            "sc_median_q20_128": float(np.median([b[2] for b in low])) if low else float("nan"),
        }
        if v["label"] == "sglang-lpminf":
            jl = glob.glob(str(ROOT / pull / "results" / "nova_job_logs" / f"{job}-*"))
            assert len(jl) == 1, jl
            hc = hook_check(Path(jl[0]), ROOT / pull / "logs" / f"pm-lpminf-{job}.out")
            row.update({f"hook_{k}": val for k, val in hc.items()})
            # the md5 is the one named in the frozen manipulation_check.self_test text
            md5 = re.search(r"md5 ([0-9a-f]{32})", ep["manipulation_check"]["self_test"]).group(1)
            row["hook_ok"] = bool(hc["child_markers_1e9"] >= 1 and hc["selftest_value"] == "1000000000"
                                  and hc["selftest_md5"] == md5 and hc["selftest_active300"] == "lpm")
            row["manipulation_verified"] = bool(row["hook_ok"] and sc_state != "FAIL")
        rows.append(row)
    return rows


def decision(rows: Sequence[Dict[str, object]], ep: dict) -> Dict[str, object]:
    inf = {r["seed"]: r for r in rows if r["label"] == "sglang-lpminf"}
    col = {}
    for s in ep["cell"]["informative_seeds"]:
        r = inf.get(s)
        col[s] = None if (r is None or not r.get("manipulation_verified") or r["collapse"] is None) else r["collapse"]
    if col.get(0) is False and col.get(1) is False:
        out = "consistent"
    elif col.get(0) is True and col.get(1) is True:
        out = "against"
    else:
        out = "inconclusive"
    # trade-off clause: against stock LPM of the same seed (both replicates reported; r1 is the same-refresh pairing)
    trade = []
    for s, r in sorted(inf.items()):
        for lab in ("sglang-lpm-r1", "sglang-lpm-r0"):
            st = [x for x in rows if x["label"] == lab and x["seed"] == s]
            if not st:
                continue
            st = st[0]
            trade.append({"seed": s, "vs": lab, "unfinished_inf": r["unfinished"], "unfinished_stock": st["unfinished"],
                          "unfinished_above_stock": r["unfinished"] > st["unfinished"],
                          "p99_W_inf": r["lat_p99_W"], "p99_W_stock": st["lat_p99_W"],
                          "p99_W_above_stock": r["lat_p99_W"] > st["lat_p99_W"]})
    return {"outcome": out, "collapse_informative_seeds": col, "trade_off": trade}


def score_sim(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """The frozen simulator comparison (mixed, primary): predicted token hit, collapse and trap_v2 state per seed."""
    pred = {0: (0.093, False, "trapped"), 1: (0.080, False, "trapped"), 2: (0.100, False, "trapped")}
    out = []
    for r in rows:
        if r["label"] != "sglang-lpminf":
            continue
        ph, pc, ps = pred[r["seed"]]
        out.append({"seed": r["seed"], "pred_tok_hit": ph, "eng_tok_hit": r["tok_hit_W"],
                    "abs_diff": abs(r["tok_hit_W"] - ph), "numeric_match": abs(r["tok_hit_W"] - ph) <= 0.1,
                    "collapse_match": r["collapse"] == pc, "pred_state": ps, "eng_state": r["trap_v2_state"],
                    "state_match": r["trap_v2_state"] == ps})
    return out


def _fmt(x: object) -> str:
    if isinstance(x, float):
        return "nan" if math.isnan(x) else f"{x:.4g}"
    return str(x)


def tables_md(rows: Sequence[Dict[str, object]]) -> str:
    cols = ["label", "seed", "job", "tok_hit_W", "collapse", "turn_hit_W", "trap_v2_state", "uncached_ratio",
            "backlog_slope", "lat_p50_W", "lat_p99_W", "lat_p99_1200", "miss_lat_p99_W", "n_lat_gt600", "unfinished",
            "q_max", "q_longest_gt128_s", "sc_bins_q_gt128", "sc_median_q_gt128", "sc_state"]
    order = {lab: i for i, lab in enumerate(LABELS)}
    rs = sorted(rows, key=lambda r: (order[r["label"]], r["seed"]))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rs:
        lines.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ep = load_endpoints()
    rows = evaluate(ep)
    dec = decision(rows, ep)
    sim = score_sim(rows)
    print(tables_md(rows))
    print(json.dumps({"decision": dec, "simulator_scoring": sim}, indent=1, default=str))
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        keys = list(rows[0].keys()) + sorted({k for r in rows for k in r} - set(rows[0].keys()))
        with open(out / "runs.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        (out / "tables.md").write_text(tables_md(rows))
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        (out / "summary.json").write_text(json.dumps({
            "endpoints": ENDPOINTS, "endpoints_sha256": _sha256(ROOT / ENDPOINTS), "pulls": PULLS,
            "code": "analysis/r11_lpminf_eval.py", "code_sha256": _sha256(Path(__file__)), "git_head": commit,
            "decision": dec, "simulator_scoring": sim}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
