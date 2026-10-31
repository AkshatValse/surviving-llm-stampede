"""LPM-128 crossing analysis (r11, plan item L1 step 1). POST HOC AND CORRELATIONAL. Read-only, zero GPU.

Question: does stock SGLang LPM fall into the all-miss trap only after its waiting queue crosses the hard-coded
128-request threshold at which SGLang 0.5.22 silently stops LPM ordering and falls back to FCFS?

This is post hoc: the 128-request hypothesis was formed after these runs had been read (r10 review and the r11 lpm
scope), so nothing here was registered and nothing here is causal evidence. The causal test is L1 step 2 (LPM-INF: the
same cell with the constant raised by a job-local hook), registered and predicted separately.

ENGINE SOURCE. SGLang 0.5.22, sglang/srt/managers/schedule_policy.py. The installed copy on Nova
(/work/classtmp/avalse/swapp/envs/sglang/lib/python3.11/site-packages/...) has md5 b8ec334ac1ed028e3c176022ea1f9143, the
same as the v0.5.22 tag copy; the lines below were re-read there with sed on 2026-10-30.
  :132-133  "# Arbitrary; bounds per-round prefix work on the waiting queue."  WAITING_QUEUE_PREFIX_MATCH_MAX = 128
  :300-311  _determine_active_policy returns CacheAgnosticPolicy.FCFS when self.policy is LPM or HRRN and
            len(waiting_queue) > WAITING_QUEUE_PREFIX_MATCH_MAX  (strictly greater than 128; comment at :309: "Turn off the
            expensive prefix matching and sorting when the #queue is large.")
  :215/:227/:260  calc_priority takes the ACTIVE policy (215) but branches on the CONFIGURED one (227, `self.policy ==
            FCFS` is false for LPM), so in fallback control reaches the cache-agnostic branch where FCFS is `pass` (260):
            no prefix match, no re-sort. The queue keeps its last LPM order and new arrivals are appended at the end.
  :276-297  _touch_waiting_prefixes(active policy) returns at once while the active policy is cache-aware. The waiting-prefix
            refresh (SGLANG_ENABLE_WAITING_PREFIX_REFRESH, the "-r1" cells) therefore acts on an LPM run only during
            fallback; its window is waiting_queue[:128] (297), the constant's only other use.
  No env var or server flag sets the constant. The queue gauge sglang:num_queue_reqs is len(scheduler.waiting_queue) at the
  scheduler's last stats tick (scheduler_components/metrics_reporter.py), scraped by the client every 5 s; the engine tests
  the condition on every scheduling pass, so a 5-s sample can miss short excursions above 128.

DATA (git-tracked pulls, every run a separate Nova job; see ``Run.job_id``):
  grid  results/nova/r7_native_grid_vllm_pulled_20261025-145126: exploratory grid, BURST arm only, cells sglang-fcfs-r0,
        sglang-lpm-r0, sglang-lpm-r1 (jobs 17097086-17097103, code 6d0dad7)
  e2    results/nova/e2_170933xx_pulled_20261025-144558: the registered E2 paired test, cell sglang-fcfs-r1, BURST arm only
        here (jobs 17093387-17093404, code d279b7b)
  SGLang 0.5.22, Qwen2.5-7B-Instruct, one A100 80GB PCIe, 300k-token KV pool, burst of 200 sessions at t = 1200 s,
  lambda = 1.35 and 1.65 x lambda_ref (0.07153 sessions/s), seeds 0-2. Same (rate, seed) => byte-identical plan.csv in every
  cell (common random numbers), so lpm-r0 and lpm-r1 replicate each other on the same arrival stream and differ only by
  the refresh flag, which is inert until the queue passes 128.

TWO TABLES.
  ``queue_table``  the scout's queue_vs_128 table, ported with its arithmetic unchanged (tests/test_lpm_crossing.py checks
                   it cell by cell against the scout's CSV). Column ``tok_hit_every600s_from900`` keeps the scout's name;
                   its values are the 300-s token-hit bins that start at 1200, 1800, ..., 8400 s.
  ``crossing_table``  per run: queue against 128, first sample above 128, the first SUSTAINED crossing (60 consecutive
                   5-s samples above 128, i.e. about 300 s; the scout's crossing.py), token hit in the 600 s before and
                   [+300, +900) / [+900, +1800) s after it, the scheduler cost around it, and the outcome.
  Outcome: ``state`` is the committed trap_v2 verdict (registered rule, eval window t_b + 4500 s to the end);
  ``collapsed`` is the L1 endpoint, token hit (cached / prompt tokens of ok requests completed in [5700, 8700) s, pooled)
  below 0.05.
  Scheduler cost: sglang:scheduler_stage_seconds_total{category="get_next_batch_to_run"} increments per wall second.
  LPM's prefix matching is the expensive part of get_next_batch_to_run, so this drops to the FCFS level when the fallback
  engages. It shows the fallback engaged; it does not show that the fallback caused the collapse.
  Dependence: lpm-r0 and lpm-r1 replicate each other on one arrival stream, so ``summary`` also gives the exact test
  stratified by rate and with one unit per stream (``streams``). Timing: ``event_time`` puts the share of time above 128
  and the token hit side by side in 60-s bins around each sustained crossing.

Usage:  python -m analysis.lpm_crossing [--out DIR]
        (prints the report; with --out also writes queue_vs_128.csv, crossing.csv and summary.json into DIR)
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
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

SOURCES: Tuple[Tuple[str, str], ...] = (
    ("grid", "results/nova/r7_native_grid_vllm_pulled_20261025-145126"),
    ("e2", "results/nova/e2_170933xx_pulled_20261025-144558"),
)

# engine constant and its source (see the module docstring)
THRESHOLD = 128
SGLANG_VERSION = "0.5.22"
SOURCE_FILE = "sglang/srt/managers/schedule_policy.py"
SOURCE_MD5 = "b8ec334ac1ed028e3c176022ea1f9143"
SOURCE_LINES = {"constant": "132-133", "fallback": "300-311", "calc_priority": "215, 227, 260", "refresh": "276-297"}

T_BURST = 1200.0               # burst time (arrivals.analysis_t_burst_s of every run here)
EVAL_T0, EVAL_T1 = 5700.0, 8700.0   # the L1 endpoint window (= t_b + 4500 s to the end of an 8700-s run)
SAMPLE_DT = 5.0                # client scrape interval of metrics.csv (s); checked by the tests
SUSTAIN_N = 60                 # consecutive queue samples > 128 that make a sustained crossing (60 x 5 s = 300 s)
BELOW_N = 12                   # consecutive samples <= 128 after the peak that count as back under (60 s)
GNB_MIN_QUEUE = 20.0           # scheduler-cost regime split uses samples with queue >= 20 only (congested)
HIT_BIN_S = 300.0              # token-hit bins
COLLAPSE_HIT = 0.05            # L1 endpoint: collapse := pooled token hit over [5700, 8700) < 0.05
PRE_S = 600.0                  # window before a sustained crossing
POST = (300.0, 900.0)          # window after it
POST2 = (900.0, 1800.0)        # later window after it
EVENT_BIN_S = 60.0             # event-time view around a sustained crossing
FLOOR_BIN_S = 60.0             # bins for the onset of the all-miss floor (t_hit_floor60; t_hit_floor uses 300-s bins)
EVENT_K = (-12, 4)             # bins k in [-12, 4): [t_cross - 720 s, t_cross + 240 s)
CONGESTED_Q = 80.0             # "congested below the threshold": 80 <= queue <= 128

QUEUE_COLUMNS = ["src", "run", "label", "seed", "mult", "state", "q_max", "t_peak", "t_first_gt128", "frac_post_gt128",
                 "t_below128_60s", "q_eval_mean", "tok_hit_eval", "gnb_s_per_s_q_le128", "gnb_s_per_s_q_gt128",
                 "tok_hit_every600s_from900"]

_LABEL_RE = re.compile(r"^sglang-(fcfs|lpm)-r([01])$")
_LAUNCH_RE = re.compile(r"launching SGLang: policy=(\S+) refresh=(\S+) radix=(\S+) lpm_inf=(\S+) kv_tokens=(\S+)")

PathFn = Callable[[str], Path]


def _repo_path(rel: str) -> Path:
    return ROOT / rel


# --------------------------------------------------------------------------- loading
@dataclass
class Run:
    src: str                     # "grid" | "e2"
    pull: str                    # repo-relative pull dir
    run: str                     # run dir name (start time)
    rel: str                     # repo-relative run dir
    label: str                   # meta engine_label, e.g. sglang-lpm-r0
    policy: str                  # fcfs | lpm  (from the label; cross-checked with the job log's launch line)
    refresh: int                 # waiting-prefix refresh flag (from the label)
    seed: str                    # as written in the verdict CSV, e.g. "0"
    mult: str                    # as written in the verdict CSV, e.g. "1.35"
    state: str                   # committed trap_v2 state
    verdict_csv: str             # repo-relative trap_v2_runs.csv the state came from (the last of the sorted list)
    job_id: str
    git_commit: str
    plan_sha256: str
    launch: Dict[str, str]       # parsed "launching SGLang: ..." line of the job log ({} if no log)
    queue: List[Tuple[float, float]]          # (t_s, num_queue_reqs), sorted
    gnb: List[Tuple[float, float]]            # (t_s, get_next_batch_to_run cumulative seconds), sorted
    reqs: List[Tuple[float, float, float]]    # ok requests in file order: (t_complete, prompt_tokens, cached_tokens)
    lat: List[Tuple[float, float]] = field(default_factory=list)   # ok requests: (t_complete, latency_s)
    verdict: Dict[str, str] = field(default_factory=dict)


def _verdicts(pull: str, path_fn: PathFn) -> Dict[str, Tuple[Dict[str, str], str]]:
    """run-dir name -> (verdict row, csv path). Later files (sorted order) win; disagreeing states are an error."""
    out: Dict[str, Tuple[Dict[str, str], str]] = {}
    pat = os.path.join(str(ROOT / pull), "results", "agentload_analysis_burst2", "*", "trap_v2_runs.csv")
    for f in sorted(glob.glob(pat)):
        rel = Path(f).resolve().relative_to(ROOT).as_posix()
        with open(path_fn(rel), newline="") as fh:
            for r in csv.DictReader(fh):
                key = os.path.basename(r["run_dir"].rstrip("/"))
                if key in out and out[key][0]["state"] != r["state"]:
                    raise ValueError(f"{key}: verdict files disagree ({out[key][1]}: {out[key][0]['state']}, {rel}: {r['state']})")
                out[key] = (r, rel)
    return out


def _read_metrics(p: Path) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """Queue gauge and get_next_batch_to_run counter from metrics.csv (lines pre-filtered by substring for speed, then
    parsed with the csv module; same keys and values as a full DictReader pass)."""
    q: Dict[float, float] = {}
    gnb: Dict[float, float] = {}
    with open(p, newline="") as fh:
        header = fh.readline()
        keep = [ln for ln in fh if ("sglang:num_queue_reqs" in ln or "get_next_batch_to_run" in ln)]
    for r in csv.DictReader(io.StringIO(header + "".join(keep))):
        n = r["name"]
        if n == "sglang:num_queue_reqs":
            q[float(r["t_s"])] = float(r["value"])
        elif n == "sglang:scheduler_stage_seconds_total" and 'category="get_next_batch_to_run"' in r["labels"]:
            gnb[float(r["t_s"])] = float(r["value"])
    return sorted(q.items()), sorted(gnb.items())


def _read_requests(p: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float]]]:
    out, lat = [], []
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["status"] != "ok":
                continue
            out.append((float(r["t_complete"]), float(r["prompt_tokens"] or 0), float(r["cached_tokens"] or 0)))
            lat.append((float(r["t_complete"]), float(r["latency_s"])))
    return out, lat


def _launch_line(pull: str, job_id: str, path_fn: PathFn) -> Dict[str, str]:
    for f in sorted(glob.glob(os.path.join(str(ROOT / pull), "logs", f"*-{job_id}.out"))):
        rel = Path(f).resolve().relative_to(ROOT).as_posix()
        with open(path_fn(rel), errors="replace") as fh:
            for ln in fh:
                m = _LAUNCH_RE.search(ln)
                if m:
                    return dict(zip(("policy", "refresh", "radix", "lpm_inf", "kv_tokens"), m.groups()))
    return {}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def discover(sources: Sequence[Tuple[str, str]] = SOURCES) -> List[Tuple[str, str, str]]:
    """(src tag, pull, repo-relative run dir) of every run dir with a meta.json, sorted per pull."""
    out = []
    for tag, pull in sources:
        for d in sorted(glob.glob(os.path.join(str(ROOT / pull), "results", "agentload_e2_burst", "*"))):
            if os.path.isfile(os.path.join(d, "meta.json")):
                out.append((tag, pull, Path(d).resolve().relative_to(ROOT).as_posix()))
    return out


def load_runs(sources: Sequence[Tuple[str, str]] = SOURCES, path_fn: PathFn = _repo_path,
              labels: Optional[Iterable[str]] = None) -> List[Run]:
    """Every BURST-arm SGLang FCFS / LPM run of the given pulls. ``path_fn`` maps a repo-relative file path to the file
    to open (the paper figure passes figures/paper/_style.src, which refuses untracked or modified files)."""
    want = set(labels) if labels is not None else None
    runs: List[Run] = []
    verdicts: Dict[str, Dict[str, Tuple[Dict[str, str], str]]] = {}
    for tag, pull, rel in discover(sources):
        with open(path_fn(f"{rel}/meta.json")) as fh:
            meta = json.load(fh)
        if meta.get("arm") != "burst":
            continue
        label = meta.get("engine_label") or ""
        m = _LABEL_RE.match(label)
        if not m or (want is not None and label not in want):
            continue
        if pull not in verdicts:
            verdicts[pull] = _verdicts(pull, path_fn)
        name = rel.rsplit("/", 1)[-1]
        if name not in verdicts[pull]:
            raise ValueError(f"{rel}: no trap_v2 verdict in {pull}")
        vr, vcsv = verdicts[pull][name]
        queue, gnb = _read_metrics(path_fn(f"{rel}/metrics.csv"))
        reqs, lat = _read_requests(path_fn(f"{rel}/requests.csv"))
        job = str((meta.get("slurm_env") or {}).get("SLURM_JOB_ID", ""))
        runs.append(Run(src=tag, pull=pull, run=name, rel=rel, label=label, policy=m.group(1), refresh=int(m.group(2)),
                        seed=vr["seed"], mult=vr["rate_mult"], state=vr["state"], verdict_csv=vcsv, job_id=job,
                        git_commit=(meta.get("git") or {}).get("commit", ""),
                        plan_sha256=_sha256(path_fn(f"{rel}/plan.csv")), launch=_launch_line(pull, job, path_fn),
                        queue=queue, gnb=gnb, reqs=reqs, lat=lat, verdict=vr))
    return runs


# --------------------------------------------------------------------------- primitives
def hit_bins(reqs: Sequence[Tuple[float, float, float]], width: float = HIT_BIN_S) -> Dict[float, float]:
    """Token hit (cached / prompt) of ok requests per completion-time bin, keyed by bin start; NaN for an empty bin."""
    b: Dict[int, List[float]] = defaultdict(lambda: [0.0, 0.0])
    for t, pt, ct in reqs:
        b[int(t // width)][0] += ct
        b[int(t // width)][1] += pt
    return {k * width: (v[0] / v[1] if v[1] else float("nan")) for k, v in sorted(b.items())}


def hitfrac(reqs: Sequence[Tuple[float, float, float]], a: float, b: float) -> Tuple[float, float, int]:
    """(token hit, turn hit = share of requests with cached > prompt / 2, n) over requests completed in [a, b)."""
    c = p = 0.0
    n = h = 0
    for t, pt, ct in reqs:
        if a <= t < b:
            c += ct
            p += pt
            n += 1
            h += ct > 0.5 * pt
    return (c / p if p else float("nan"), h / n if n else float("nan"), n)


def sustained_crossing(queue: Sequence[Tuple[float, float]], t_from: float = T_BURST, n: int = SUSTAIN_N,
                       thr: float = THRESHOLD) -> Optional[float]:
    """First sample time t >= t_from that starts n consecutive samples all > thr (None if never)."""
    for i, (t, _) in enumerate(queue):
        if t < t_from:
            continue
        win = queue[i:i + n]
        if len(win) == n and all(v > thr for _, v in win):
            return t
    return None


def longest_above_s(queue: Sequence[Tuple[float, float]], t_from: float = T_BURST, thr: float = THRESHOLD,
                    dt: float = 5.0) -> float:
    """Longest stretch (s) of consecutive samples > thr after t_from, counting each sample as dt seconds."""
    best = cur = 0
    for t, v in queue:
        if t < t_from:
            continue
        cur = cur + 1 if v > thr else 0
        best = max(best, cur)
    return best * dt


def counter_rate(series: Sequence[Tuple[float, float]], a: float, b: float) -> float:
    """Increase per second of a cumulative counter between its first and last sample inside [a, b]."""
    s = [(t, c) for t, c in series if a <= t <= b]
    if len(s) < 2 or s[-1][0] <= s[0][0]:
        return float("nan")
    return (s[-1][1] - s[0][1]) / (s[-1][0] - s[0][0])


def gnb_by_regime(queue: Sequence[Tuple[float, float]], gnb: Sequence[Tuple[float, float]], t_from: float = T_BURST,
                  qmin: float = GNB_MIN_QUEUE, thr: float = THRESHOLD) -> Tuple[float, float]:
    """get_next_batch_to_run s/s over scrape intervals whose start has queue in [qmin, thr] vs > thr (the scout's split)."""
    qd = dict(queue)
    acc = {"le": [0.0, 0.0], "gt": [0.0, 0.0]}
    for (t0, c0), (t1, c1) in zip(gnb, gnb[1:]):
        if t0 < t_from:
            continue
        qq = qd.get(t0)
        if qq is None or qq < qmin:
            continue
        k = "gt" if qq > thr else "le"
        acc[k][0] += c1 - c0
        acc[k][1] += t1 - t0
    le = acc["le"][0] / acc["le"][1] if acc["le"][1] else float("nan")
    gt = acc["gt"][0] / acc["gt"][1] if acc["gt"][1] else float("nan")
    return le, gt


def gnb_by_queue_bin(runs: Sequence[Run], edges: Sequence[float], t_from: float = T_BURST) -> List[Dict[str, float]]:
    """Pooled get_next_batch_to_run s/s per queue-length bin [edges[i], edges[i+1]) over the given runs (the queue value
    is the one at the start of each scrape interval)."""
    tot = [[0.0, 0.0, 0] for _ in range(len(edges) - 1)]
    for r in runs:
        qd = dict(r.queue)
        for (t0, c0), (t1, c1) in zip(r.gnb, r.gnb[1:]):
            if t0 < t_from or t0 not in qd:
                continue
            q = qd[t0]
            for i in range(len(edges) - 1):
                if edges[i] <= q < edges[i + 1]:
                    tot[i][0] += c1 - c0
                    tot[i][1] += t1 - t0
                    tot[i][2] += 1
                    break
    return [dict(q_lo=edges[i], q_hi=edges[i + 1], s_per_s=(c / d if d else float("nan")), n=n)
            for i, (c, d, n) in enumerate(tot)]


COST_EDGES = tuple(range(17, 370, 16))   # 16-wide queue bins with an edge at 129 (the first fallback length)


def lpm_cost_fit(runs: Sequence[Run], edges: Sequence[int] = COST_EDGES, min_n: int = 20) -> Tuple[float, float]:
    """OLS of pooled get_next_batch_to_run s/s on queue length over the stock-LPM bins below 129 (LPM active): returns
    (intercept s/s, slope s/s per waiting request). Bins with fewer than ``min_n`` scrape intervals are left out."""
    b = [x for x in gnb_by_queue_bin([r for r in runs if r.policy == "lpm"], edges)
         if x["n"] >= min_n and x["q_hi"] <= THRESHOLD + 1]
    xs = [(x["q_lo"] + x["q_hi"] - 1) / 2 for x in b]
    ys = [x["s_per_s"] for x in b]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - slope * mx, slope


def queue_binned(queue: Sequence[Tuple[float, float]], width: float = 60.0) -> List[Tuple[float, float]]:
    """(bin centre, mean queue) per time bin, for plotting."""
    b: Dict[int, List[float]] = defaultdict(list)
    for t, v in queue:
        b[int(t // width)].append(v)
    return [((k + 0.5) * width, sum(v) / len(v)) for k, v in sorted(b.items())]


# --------------------------------------------------------------------------- the scout's table (ported unchanged)
def queue_row(r: Run) -> Optional[Dict[str, object]]:
    q = r.queue
    post = [(t, v) for t, v in q if t >= T_BURST]
    if not post:
        return None
    qmax = max(v for _, v in post)
    t_peak = max(post, key=lambda x: x[1])[0]
    frac_gt = sum(1 for _, v in post if v > THRESHOLD) / len(post)
    t_below = None
    after = [(t, v) for t, v in post if t >= t_peak]
    for i in range(len(after)):
        win = after[i:i + BELOW_N]
        if len(win) == BELOW_N and all(v <= THRESHOLD for _, v in win):
            t_below = after[i][0]
            break
    t_first_gt = next((t for t, v in post if v > THRESHOLD), None)
    ev = [v for t, v in q if EVAL_T0 <= t <= EVAL_T1]
    q_eval = sum(ev) / len(ev) if ev else float("nan")
    gnb_le, gnb_gt = gnb_by_regime(q, r.gnb)
    hb = hit_bins(r.reqs)
    hit_eval_l = [h for t, h in hb.items() if EVAL_T0 <= t < EVAL_T1]
    hit_eval = sum(hit_eval_l) / len(hit_eval_l) if hit_eval_l else float("nan")
    hit_trace = " ".join(f"{h:.2f}" for t, h in hb.items() if t >= 900 and int(t) % 600 == 0)
    return dict(src=r.src, run=r.run, label=r.label, seed=r.seed, mult=r.mult, state=r.state,
                q_max=qmax, t_peak=round(t_peak), t_first_gt128=t_first_gt and round(t_first_gt),
                frac_post_gt128=round(frac_gt, 3), t_below128_60s=t_below and round(t_below),
                q_eval_mean=round(q_eval, 1), tok_hit_eval=round(hit_eval, 3),
                gnb_s_per_s_q_le128=round(gnb_le, 4), gnb_s_per_s_q_gt128=round(gnb_gt, 4),
                tok_hit_every600s_from900=hit_trace)


def queue_table(runs: Sequence[Run]) -> List[Dict[str, object]]:
    rows = [x for x in (queue_row(r) for r in runs) if x is not None]
    rows.sort(key=lambda x: (x["label"], str(x["mult"]), str(x["seed"])))
    return rows


# --------------------------------------------------------------------------- crossing table
def _r(x: Optional[float], nd: int) -> Optional[float]:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, nd)


def hit_floor(hb: Dict[float, float], t_from: float = T_BURST, t_to: float = EVAL_T1) -> Optional[int]:
    """Onset of the absorbing all-miss floor: start of the first bin in [t_from, t_to) from which every later bin up to
    t_to has token hit < 0.05 (empty bins are skipped). None if the run never stays below 0.05."""
    ks = [t for t in sorted(hb) if t_from <= t < t_to and not math.isnan(hb[t])]
    for i, t in enumerate(ks):
        if all(hb[u] < COLLAPSE_HIT for u in ks[i:]):
            return round(t)
    return None


def crossing_row(r: Run) -> Dict[str, object]:
    post = [(t, v) for t, v in r.queue if t >= T_BURST]
    qmax = max(v for _, v in post)
    t_qmax = max(post, key=lambda x: x[1])[0]
    t_first = next((t for t, v in post if v > THRESHOLD), None)
    tx = sustained_crossing(r.queue)
    hit_ev, turn_ev, n_ev = hitfrac(r.reqs, EVAL_T0, EVAL_T1)
    hb = hit_bins(r.reqs)
    binmean = [h for t, h in hb.items() if EVAL_T0 <= t < EVAL_T1]
    row: Dict[str, object] = dict(
        src=r.src, run=r.run, job=r.job_id, label=r.label, policy=r.policy, refresh=r.refresh, mult=r.mult, seed=r.seed,
        q_max_post=qmax, t_q_max=round(t_qmax), t_first_gt128=None if t_first is None else round(t_first),
        longest_gt128_s=longest_above_s(r.queue), crossed=tx is not None, t_cross=None if tx is None else round(tx),
        hit_pre=None, hit_post=None, hit_post2=None, turn_hit_pre=None, turn_hit_post=None,
        gnb_pre=None, gnb_post=None, t_hit_floor=None, t_hit_floor60=None, share_gt128_first_to_cross=None, lat_med_pre=None,
        s_q80_128=SAMPLE_DT * sum(1 for t, v in post if CONGESTED_Q <= v <= THRESHOLD),
        tok_hit_eval=_r(hit_ev, 4), tok_hit_eval_binmean=_r(sum(binmean) / len(binmean) if binmean else float("nan"), 4),
        turn_hit_eval=_r(turn_ev, 4), n_eval=n_ev, collapsed=bool(hit_ev < COLLAPSE_HIT), state=r.state)
    row["t_hit_floor"] = hit_floor(hb)
    row["t_hit_floor60"] = hit_floor(hit_bins(r.reqs, FLOOR_BIN_S))
    if tx is not None:
        b = hitfrac(r.reqs, tx - PRE_S, tx)
        a = hitfrac(r.reqs, tx + POST[0], tx + POST[1])
        a2 = hitfrac(r.reqs, tx + POST2[0], tx + POST2[1])
        row.update(hit_pre=_r(b[0], 4), hit_post=_r(a[0], 4), hit_post2=_r(a2[0], 4), turn_hit_pre=_r(b[1], 3),
                   turn_hit_post=_r(a[1], 3), gnb_pre=_r(counter_rate(r.gnb, tx - PRE_S, tx), 5),
                   gnb_post=_r(counter_rate(r.gnb, tx + POST[0], tx + POST[1]), 5))
        between = [v for t, v in r.queue if t_first <= t < tx]
        row["share_gt128_first_to_cross"] = round(sum(1 for v in between if v > THRESHOLD) / len(between), 3) if between else None
        lats = sorted(x for t, x in r.lat if tx - PRE_S <= t < tx)
        row["lat_med_pre"] = round(lats[len(lats) // 2], 1) if lats else None
    return row


def event_time(r: Run, width: float = EVENT_BIN_S, k_range: Tuple[int, int] = EVENT_K) -> List[Dict[str, object]]:
    """Around the run's sustained crossing t_x: per bin [t_x + k w, t_x + (k+1) w), the share of queue samples above 128
    and the token hit of requests COMPLETED in the bin. A request's cache outcome is fixed when it is admitted, somewhere
    between its send and its completion, so this hit series lags the engine state by up to one send-to-complete latency
    (``lat_med_pre`` in the crossing table, about 2 min here). Empty for a run without a sustained crossing."""
    tx = sustained_crossing(r.queue)
    if tx is None:
        return []
    out = []
    for k in range(*k_range):
        a = tx + k * width
        s = [v for t, v in r.queue if a <= t < a + width]
        h = hitfrac(r.reqs, a, a + width)
        out.append(dict(k=k, t0_rel=k * width, share_gt128=(sum(1 for v in s if v > THRESHOLD) / len(s)) if s else float("nan"),
                        hit=h[0], n=h[2]))
    return out


def crossing_table(runs: Sequence[Run]) -> List[Dict[str, object]]:
    rows = [crossing_row(r) for r in runs]
    rows.sort(key=lambda x: (x["policy"], x["refresh"], str(x["mult"]), str(x["seed"])))
    return rows


# --------------------------------------------------------------------------- exact tests
def _hypergeom_pmf(N: int, K: int, n: int) -> Dict[int, float]:
    tot = math.comb(N, n)
    return {x: math.comb(K, x) * math.comb(N - K, n - x) / tot for x in range(max(0, n - (N - K)), min(n, K) + 1)}


def fisher_one_sided(a: int, b: int, c: int, d: int) -> float:
    """One-sided (greater) Fisher exact p for [[a, b], [c, d]]: P(X >= a) with all margins fixed."""
    pmf = _hypergeom_pmf(a + b + c + d, a + c, a + b)
    return sum(p for x, p in pmf.items() if x >= a)


def stratified_exact_one_sided(tables: Sequence[Tuple[int, int, int, int]]) -> float:
    """Exact conditional test of a common association across strata (margins fixed in each): P(sum of a >= observed),
    from the convolution of the per-stratum hypergeometric distributions."""
    dist = {0: 1.0}
    obs = 0
    for a, b, c, d in tables:
        pmf = _hypergeom_pmf(a + b + c + d, a + c, a + b)
        new: Dict[int, float] = defaultdict(float)
        for s, ps in dist.items():
            for x, px in pmf.items():
                new[s + x] += ps * px
        dist = dict(new)
        obs += a
    return sum(p for s, p in dist.items() if s >= obs)


def two_by_two(rows: Sequence[Dict[str, object]]) -> Tuple[int, int, int, int]:
    """(crossed & collapsed, crossed & not, not crossed & collapsed, neither)."""
    a = sum(1 for x in rows if x["crossed"] and x["collapsed"])
    b = sum(1 for x in rows if x["crossed"] and not x["collapsed"])
    c = sum(1 for x in rows if not x["crossed"] and x["collapsed"])
    d = sum(1 for x in rows if not x["crossed"] and not x["collapsed"])
    return a, b, c, d


# --------------------------------------------------------------------------- summary
def _lpm(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    return [x for x in rows if x["policy"] == "lpm"]


def pairs(rows: Sequence[Dict[str, object]], runs: Sequence[Run]) -> List[Dict[str, object]]:
    """Stock-LPM replicate pairs (refresh off / on) on the same (rate, seed) arrival stream."""
    by = {(x["label"], x["mult"], x["seed"]): x for x in rows}
    plan = {(r.label, r.mult, r.seed): r.plan_sha256 for r in runs}
    out = []
    for m, s in sorted({(x["mult"], x["seed"]) for x in _lpm(rows)}):
        r0, r1 = by.get(("sglang-lpm-r0", m, s)), by.get(("sglang-lpm-r1", m, s))
        if r0 is None or r1 is None:
            continue
        out.append(dict(mult=m, seed=s, same_plan=plan[("sglang-lpm-r0", m, s)] == plan[("sglang-lpm-r1", m, s)],
                        r0_crossed=r0["crossed"], r0_collapsed=r0["collapsed"], r0_state=r0["state"], r0_q_max=r0["q_max_post"],
                        r1_crossed=r1["crossed"], r1_collapsed=r1["collapsed"], r1_state=r1["state"], r1_q_max=r1["q_max_post"],
                        discordant=r0["crossed"] != r1["crossed"]))
    return out


def streams(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Stock LPM collapsed to one unit per arrival stream (rate, seed): crossed / collapsed in ANY replicate. The most
    conservative reading of the dependence between the r0 and r1 replicates."""
    out = []
    lpm = _lpm(rows)
    for m, s in sorted({(x["mult"], x["seed"]) for x in lpm}):
        g = [x for x in lpm if x["mult"] == m and x["seed"] == s]
        out.append(dict(mult=m, seed=s, n=len(g), crossed=any(x["crossed"] for x in g), collapsed=any(x["collapsed"] for x in g)))
    return out


def natural_experiment(runs: Sequence[Run], mult: str = "1.35", seed: str = "0", t_end: float = 4500.0) -> Dict[str, object]:
    """The same-seed pair the plan names (1.35 x, seed 0): queue and token hit side by side in 300-s bins."""
    sel = {r.label: r for r in runs if r.policy == "lpm" and r.mult == mult and r.seed == seed}
    r0, r1 = sel["sglang-lpm-r0"], sel["sglang-lpm-r1"]
    h0, h1 = hit_bins(r0.reqs), hit_bins(r1.reqs)
    q0, q1 = queue_binned(r0.queue, HIT_BIN_S), queue_binned(r1.queue, HIT_BIN_S)
    qd0 = {c - HIT_BIN_S / 2: v for c, v in q0}
    qd1 = {c - HIT_BIN_S / 2: v for c, v in q1}
    bins = [t for t in sorted(h0) if 600.0 <= t < t_end]
    return dict(mult=mult, seed=seed, same_plan=r0.plan_sha256 == r1.plan_sha256, plan_sha256=r0.plan_sha256,
                jobs=(r0.job_id, r1.job_id),
                r0=crossing_row(r0), r1=crossing_row(r1),
                trace=[dict(t=round(t), q_r0=_r(qd0.get(t), 1), q_r1=_r(qd1.get(t), 1), hit_r0=_r(h0.get(t), 3),
                            hit_r1=_r(h1.get(t), 3)) for t in bins])


def _rng(vals: Iterable[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
    v = [x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return (min(v), max(v)) if v else (None, None)


def _mean(vals: Iterable[Optional[float]]) -> Optional[float]:
    v = [x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(v) / len(v) if v else None


def summary(runs: Sequence[Run]) -> Dict[str, object]:
    qrows = queue_table(runs)
    xrows = crossing_table(runs)
    lpm = _lpm(xrows)
    a, b, c, d = two_by_two(lpm)
    strata = []
    for m in sorted({x["mult"] for x in lpm}):
        strata.append(two_by_two([x for x in lpm if x["mult"] == m]))
    qlpm = [x for x in qrows if "lpm" in str(x["label"])]
    qfcfs = [x for x in qrows if "fcfs" in str(x["label"])]
    crossed = [x for x in lpm if x["crossed"]]
    q_by_run = {x["run"]: x for x in qrows}
    st = two_by_two(streams(xrows))
    ev = {r.run: event_time(r) for r in runs if r.policy == "lpm"}
    return dict(
        threshold=THRESHOLD, sglang=SGLANG_VERSION, source=dict(file=SOURCE_FILE, md5=SOURCE_MD5, lines=SOURCE_LINES),
        n_runs=len(xrows), n_lpm=len(lpm), n_fcfs=len(xrows) - len(lpm),
        fisher=dict(table=[[a, b], [c, d]], rows="crossed (>= 300 s above 128) yes / no", cols="collapsed yes / no",
                    p_one_sided=fisher_one_sided(a, b, c, d),
                    p_exact_fraction=(f"1/{math.comb(a + b + c + d, a + b)}" if (b, c) == (0, 0) else None),
                    strata_by_rate=dict(zip(sorted({x["mult"] for x in lpm}), [list(t) for t in strata])),
                    p_stratified_by_rate=stratified_exact_one_sided(strata),
                    stream_table=[list(st[:2]), list(st[2:])], p_streams=fisher_one_sided(*st)),
        crossings=[dict(label=x["label"], mult=x["mult"], seed=x["seed"], job=x["job"], t_first_gt128=x["t_first_gt128"],
                        t_cross=x["t_cross"], t_hit_floor=x["t_hit_floor"], t_hit_floor60=x["t_hit_floor60"], hit_pre=x["hit_pre"], hit_post=x["hit_post"],
                        hit_post2=x["hit_post2"], gnb_pre=x["gnb_pre"], gnb_post=x["gnb_post"], state=x["state"],
                        share_gt128_first_to_cross=x["share_gt128_first_to_cross"], lat_med_pre=x["lat_med_pre"],
                        tok_hit_eval=x["tok_hit_eval"],
                        event=[dict(t0_rel=e["t0_rel"], share_gt128=_r(e["share_gt128"], 2), hit=_r(e["hit"], 3))
                               for e in ev[x["run"]]]) for x in crossed],
        lpm_not_crossed_q_max=_rng(x["q_max_post"] for x in lpm if not x["crossed"]),
        lpm_not_crossed_s_q80_128=_rng(x["s_q80_128"] for x in lpm if not x["crossed"]),
        lpm_not_crossed_hit_eval=_rng(x["tok_hit_eval"] for x in lpm if not x["crossed"]),
        streams=streams(xrows),
        sched_cost=dict(
            lpm_q_le128=_rng(x["gnb_s_per_s_q_le128"] for x in qlpm),
            lpm_q_le128_mean=_mean(x["gnb_s_per_s_q_le128"] for x in qlpm),
            lpm_q_gt128_crossed=_rng(q_by_run[x["run"]]["gnb_s_per_s_q_gt128"] for x in crossed),
            lpm_q_gt128_crossed_mean=_mean(q_by_run[x["run"]]["gnb_s_per_s_q_gt128"] for x in crossed),
            fcfs_all=_rng([x["gnb_s_per_s_q_le128"] for x in qfcfs] + [x["gnb_s_per_s_q_gt128"] for x in qfcfs]),
            at_crossing_pre=_rng(x["gnb_pre"] for x in crossed), at_crossing_post=_rng(x["gnb_post"] for x in crossed),
            at_crossing_pre_mean=_mean(x["gnb_pre"] for x in crossed),
            at_crossing_post_mean=_mean(x["gnb_post"] for x in crossed),
            lpm_fit_intercept=lpm_cost_fit(runs)[0], lpm_fit_per_100_waiting=100.0 * lpm_cost_fit(runs)[1]),
        pairs=pairs(xrows, runs),
        natural_experiment=natural_experiment(runs),
        launch_matches_label=all(r.launch.get("policy") == r.policy and r.launch.get("refresh") == str(r.refresh)
                                 and r.launch.get("lpm_inf") == "0" for r in runs),
    )


# --------------------------------------------------------------------------- output
def write_csv(rows: Sequence[Dict[str, object]], fh, columns: Optional[Sequence[str]] = None) -> None:
    w = csv.DictWriter(fh, fieldnames=list(columns or rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def _fmt(v: object) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return f"{v:g}"
    return str(v)


def markdown_table(rows: Sequence[Dict[str, object]], cols: Sequence[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_fmt(r.get(c)) for c in cols) + " |")
    return "\n".join(out)


CROSSING_COLS = ["label", "mult", "seed", "job", "q_max_post", "t_first_gt128", "longest_gt128_s", "s_q80_128", "t_cross",
                 "hit_pre", "hit_post", "hit_post2", "t_hit_floor60", "gnb_pre", "gnb_post", "tok_hit_eval", "collapsed", "state"]


def report(runs: Sequence[Run]) -> str:
    s = summary(runs)
    xrows = crossing_table(runs)
    f = s["fisher"]
    sc = s["sched_cost"]
    ne = s["natural_experiment"]
    lines = [
        "POST HOC, CORRELATIONAL: SGLang 0.5.22 LPM -> FCFS fallback at waiting queue > 128 vs outcome, BURST arm.",
        f"source {SOURCE_FILE} (md5 {SOURCE_MD5}) lines {SOURCE_LINES}",
        f"runs: {s['n_runs']} ({s['n_lpm']} stock LPM, {s['n_fcfs']} FCFS); job log launch lines match labels: "
        f"{s['launch_matches_label']}",
        "",
        "crossing table (t in s since run start; burst at 1200 s; hit = token hit; gnb = get_next_batch_to_run s/s; "
        "pre = [t_cross-600, t_cross), post = [+300, +900), post2 = [+900, +1800)):",
        markdown_table(xrows, CROSSING_COLS),
        "",
        f"Fisher (stock LPM, crossed >= 300 s above 128 x collapsed): table {f['table']}, one-sided p = "
        f"{f['p_one_sided']:.5f} ({f['p_exact_fraction']}); stratified by rate {f['strata_by_rate']}: "
        f"p = {f['p_stratified_by_rate']:.4f}; one unit per arrival stream {f['stream_table']}: p = {f['p_streams']:.4f}",
        "",
        "event time around each sustained crossing (60-s bins, t0 relative to t_cross; share of 5-s queue samples > 128 / "
        "token hit of requests completed in the bin):",
    ]
    for c in s["crossings"]:
        lines.append(f"  {c['label']} {c['mult']} x s{c['seed']} (t_first_gt128 {c['t_first_gt128']}, t_cross {c['t_cross']}, "
                     f"share > 128 in between {c['share_gt128_first_to_cross']}, median latency before {c['lat_med_pre']} s)")
        lines.append("    t0   : " + " ".join(f"{e['t0_rel']:>5.0f}" for e in c["event"]))
        lines.append("    >128 : " + " ".join(f"{e['share_gt128']:>5.2f}" for e in c["event"]))
        lines.append("    hit  : " + " ".join(f"{e['hit']:>5.2f}" for e in c["event"]))
    lines += [
        "",
        "replicate pairs (lpm-r0 / lpm-r1 on the same arrival stream):",
        markdown_table(s["pairs"], ["mult", "seed", "same_plan", "r0_q_max", "r0_crossed", "r0_collapsed", "r0_state",
                                    "r1_q_max", "r1_crossed", "r1_collapsed", "r1_state", "discordant"]),
        "",
        f"natural experiment {ne['mult']} x seed {ne['seed']}: same plan.csv {ne['same_plan']} (sha256 "
        f"{ne['plan_sha256'][:12]}...), jobs {ne['jobs']}",
        markdown_table(ne["trace"], ["t", "q_r0", "q_r1", "hit_r0", "hit_r1"]),
        "",
        f"scheduler cost (s/s): LPM with queue in [20, 128]: {sc['lpm_q_le128']} (mean {sc['lpm_q_le128_mean']:.4f}); "
        f"LPM above 128 (crossed runs): {sc['lpm_q_gt128_crossed']} (mean {sc['lpm_q_gt128_crossed_mean']:.4f}); "
        f"FCFS: {sc['fcfs_all']}; at the crossing: before {sc['at_crossing_pre']} (mean {sc['at_crossing_pre_mean']:.4f}) "
        f"-> after {sc['at_crossing_post']} (mean {sc['at_crossing_post_mean']:.4f})",
    ]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="directory for queue_vs_128.csv, crossing.csv and summary.json")
    args = ap.parse_args(argv)
    runs = load_runs()
    print(report(runs))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "queue_vs_128.csv", "w", newline="") as fh:
            write_csv(queue_table(runs), fh, QUEUE_COLUMNS)
        with open(out / "crossing.csv", "w", newline="") as fh:
            write_csv(crossing_table(runs), fh)
        with open(out / "summary.json", "w") as fh:
            json.dump(summary(runs), fh, indent=1, default=str)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
