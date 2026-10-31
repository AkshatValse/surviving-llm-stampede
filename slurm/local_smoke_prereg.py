"""LOCAL SMOKE TEST ONLY (slurm/local_smoke.sh): write fake inputs for the mock-server run of the job glue. Nothing here is a
measurement: a fake E0a calibration.json, a Stage-C-shaped mu_curve.json (argmax n = 3, so the CAPPED arm gets a gate of 3), an
E0b bracket and, with --prereg, a pre-registration filled from them BY THE SAME CODE the real workflow uses
(analysis.prereg.fill), registering the smoke protocol (duration/burst time from the job's env). The file is NOT committed; the
job runs it with PREREG_ALLOW_UNCOMMITTED=1, so no verdict from such runs can be decisive.
    python slurm/local_smoke_prereg.py --dir D --label mock-fcfs --hardware HW --mult 1.5 --duration-s 14 --t-burst-s 6 [--prereg]
                                       [--set k=v ...]      (the same analysis overrides the smoke analysis uses)
                                       [--rescue-config FILE]  (ARMS=rescue: write a mock-scale copy of
                                                                configs/agentload_e2_rescue_smoke.yaml to FILE and register it)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from analysis.closed import mu_curve  # noqa: E402
from analysis.params import load_params  # noqa: E402
from analysis import prereg  # noqa: E402

FAKE_MU = {1: 50.0, 2: 80.0, 3: 100.0, 4: 80.0, 6: 50.0, 8: 20.0, 300: 1.0}       # argmax n = 3; mu(300) = lambda_miss = 1


def rescue_mock_config(duration_s: float, t_burst_s: float, n_cap: int) -> dict:
    """configs/agentload_e2_rescue_smoke.yaml scaled to a mock run: a burst of 60 that piles up on the small mock pool, the cap
    engaged 3 s after it (so many sessions are over the cap and pause), a short hold; the workload and the burst live in the
    config (the job glue's GEN_EXTRA for ARMS=rescue sets no burst keys), so check-run compares them with this file."""
    c = yaml.safe_load((REPO / "configs" / "agentload_e2_rescue_smoke.yaml").read_text())
    c["run"]["duration_s"] = duration_s
    c["arrivals"]["burst"].update(n=60, t_s=t_burst_s, width_s=0.5)
    c["arrivals"]["analysis_t_burst_s"] = t_burst_s
    c["workload"].update(initial_context_tokens=400, new_prompt_tokens=50, decode_tokens=10, mean_turns=6, max_turns=12,
                         tool_time_mean_s=0.3)
    c["gate"].update(n_cap=n_cap, t_on_s=t_burst_s + 3.0, release_hold_s=2.0, min_on_s=3.0, release_check_s=1.0)
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--hardware", required=True)
    ap.add_argument("--mult", type=float, default=1.5)
    ap.add_argument("--duration-s", type=float, default=14.0)
    ap.add_argument("--t-burst-s", type=float, default=6.0)
    ap.add_argument("--prereg", action="store_true")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--rescue-config", default=None, help="ARMS=rescue: write the mock-scale rescue smoke config here")
    args = ap.parse_args(argv)
    d = Path(args.dir)
    d.mkdir(parents=True, exist_ok=True)
    cal = {"lambda_miss": 1.0, "lambda_miss_turns_based": 1.0, "all_miss_uncached_tokens_per_s": 1000.0, "hardware": args.hardware}
    (d / "calibration.json").write_text(json.dumps(cal))
    cp = {"n_grid": list(FAKE_MU), "lpm_n": [], "n_inf": 300, "mu_estimator": "sessions", "argmax_margin_warn": 0.05}
    pts = pd.DataFrame([dict(label=args.label, seed=0, n=n, mu_sessions=m, mu_turns_based=m, turns_per_s=1.0, hit_frac_turns=0.9,
                             hit_frac_followup=0.9, cached_frac_tokens=0.9, queue_mean=0.0, aborted=False, hardware=args.hardware)
                        for n, m in FAKE_MU.items()])
    curve = json.loads(json.dumps(mu_curve(pts, cp, "fcfs")))
    (d / "mu_curve.json").write_text(json.dumps(curve))
    (d / "e0b.json").write_text(json.dumps({"by_label": {args.label: {
        "largest_all_stable_mult": 3.0, "first_unstable_mult_above": 4.0, "monotone": True, "hardware": [args.hardware]}}}))
    if args.prereg:
        p = load_params(REPO / "configs" / "agentload_analysis.yaml", args.set)
        e2_sha = None
        if args.rescue_config:
            e2 = rescue_mock_config(args.duration_s, args.t_burst_s, int(curve["n_cap"]))
            rc = Path(args.rescue_config)
            rc.write_bytes(yaml.safe_dump(e2, sort_keys=False).encode("utf-8"))
            e2_sha = hashlib.sha256(rc.read_bytes()).hexdigest()
        else:
            e2 = yaml.safe_load((REPO / "configs" / "agentload_e2_burst.yaml").read_text())
            e2["run"]["duration_s"], e2["arrivals"]["analysis_t_burst_s"] = args.duration_s, args.t_burst_s
        tmpl = prereg.load_prereg(REPO / "configs" / "agentload_prereg_template.yaml")
        tmpl["inputs"]["fcfs_substr"] = "fcfs"
        for key, path in prereg.RULE_KEYS.items():          # the smoke analysis uses scaled-down rule values: register those
            tmpl["pass_rule"][key] = prereg._param(p, path)
        pr = prereg.fill(tmpl, curve, cal, e0b=json.loads((d / "e0b.json").read_text()), e2_cfg=e2, lambda_mults=[args.mult],
                         rule="local smoke test: one fake point inside the fake window", engine_cell_label=args.label, p=p,
                         e2_cfg_sha256=e2_sha)
        (d / "prereg.yaml").write_text(yaml.safe_dump(pr, sort_keys=False))
        print(f"fake prereg status={pr['status']}", [x for x in pr["fill_problems"] if x["severity"] == "error"])
        return 0 if pr["status"] == "FILLED" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
