"""Registrations of the r14 extra cells: TOOLSLOW (remedy plan N3) and SHED (remedy plan N4), SGLang FCFS, 300k pool, 1.35 x.

TOOLSLOW  sglang-fcfs-r1-toolslow-d10 / -d30: the E2 NOBURST protocol at 1.35 x lambda_ref (no burst, 8700-s runs) with a
          tool-latency spike: every tool call whose sleep starts in [1200, 2100) s sleeps its drawn tool time plus 10 s resp.
          30 s (configs/agentload_e2_toolslow_d10.yaml / _d30.yaml, client option workload.tool_slowdown). Arm noburst only,
          seeds 0, 1, 2. Pairs by seed with the committed E2 NOBURST run (same plan.csv) and BURST run at 1.35 x.
SHED      sglang-fcfs-r1-shed-t600 / -t3600: the E2 BURST protocol at 1.35 x (burst of 200 in [1200, 1260)) with the arrivals
          stopped over [1800, 1800 + tau) (configs/agentload_e2_shed_t600.yaml / _t3600.yaml, arrivals.kind ramp). Arm burst
          only, seeds 0, 1. Pairs by seed with the committed E2 BURST run at 1.35 x (the arrivals outside the stop are its).

As in ``analysis.basin fill`` and ``analysis.rescue_prereg fill``, ``analysis.prereg.fill`` cannot look the new labels up in
mu_curve.json or the E0b bracket, so the fill runs under the MEASURED label sglang-fcfs-r1 from the inputs of the 2026-10-24
registration (prereg/inputs/2026-10-23), with the cell's E2 config (its sha256 goes into protocol.e2_config_sha256) and the
cell's arm (protocol.arms), and only ``inputs.engine_cell_label`` is then set to the cell's label. Output is exactly what
``analysis.prereg fill`` writes (yaml.safe_dump, sort_keys=False), LF, never overwrites.

CLI:  python -m analysis.r14_prereg fill --cell toolslow-d10|toolslow-d30|shed-t600|shed-t3600 [--out FILE]
      python -m analysis.r14_prereg diff --cell CELL [--file FILE]     (scripted diff against the 2026-10-24 registration)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from . import prereg as prereg_mod
from .params import AnalysisParams, load_params

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = "configs/agentload_prereg_template.yaml"
PARAMS = "configs/agentload_analysis.yaml"
PARENT = "configs/agentload_prereg_2026-10-24.yaml"
INPUTS = "prereg/inputs/2026-10-23"
MEASURED = "sglang-fcfs-r1"
ENDPOINTS = "configs/r11_basin_predict.yaml"
HARDWARE = "NVIDIA A100 80GB PCIe, 81920 MiB"
MULT = 1.35
CONTROL_JOBS = "17093387-17093404 (results/nova/e2_170933xx_pulled_20261025-144558)"

TOOLSLOW_RULE = "causal test of the gap: d10 GOOD in >=2/3 seeds and d30 STUCK in >=2/3"
SHED_RULE = "tau600 STUCK in >=2/3 and tau3600 GOOD in >=2/3; sessions shed reported; compared with R1 (0 shed)"

CELLS: Dict[str, Dict[str, Any]] = {
    "toolslow-d10": {"label": "sglang-fcfs-r1-toolslow-d10", "family": "toolslow", "param": 10,
                     "e2": "configs/agentload_e2_toolslow_d10.yaml", "arms": ["noburst"], "seeds": [0, 1, 2],
                     "out": "configs/agentload_prereg_2026-10-31_toolslow_d10.yaml"},
    "toolslow-d30": {"label": "sglang-fcfs-r1-toolslow-d30", "family": "toolslow", "param": 30,
                     "e2": "configs/agentload_e2_toolslow_d30.yaml", "arms": ["noburst"], "seeds": [0, 1, 2],
                     "out": "configs/agentload_prereg_2026-10-31_toolslow_d30.yaml"},
    "shed-t600": {"label": "sglang-fcfs-r1-shed-t600", "family": "shed", "param": 600,
                  "e2": "configs/agentload_e2_shed_t600.yaml", "arms": ["burst"], "seeds": [0, 1],
                  "out": "configs/agentload_prereg_2026-10-31_shed_t600.yaml"},
    "shed-t3600": {"label": "sglang-fcfs-r1-shed-t3600", "family": "shed", "param": 3600,
                   "e2": "configs/agentload_e2_shed_t3600.yaml", "arms": ["burst"], "seeds": [0, 1],
                   "out": "configs/agentload_prereg_2026-10-31_shed_t3600.yaml"},
}

_COMMON = (
    f"Single point {MULT:g} x lambda_ref: the lower registered point (m1) of {PARENT}, same inputs ({INPUTS}: mu_curve, "
    "calibration, E0b bracket), same window (1, 2.0) x lambda_ref and the same 1/3-2/3 rule written on 2026-10-23 before E0b "
    "was read; reused unchanged so that each run pairs by seed (common random numbers) with the committed 300k E2 runs at "
    f"{MULT:g} x (jobs {CONTROL_JOBS}). The measured values are those of cell {MEASURED} (same hardware, pool, policy and "
    f"refresh flag; filled by analysis.r14_prereg fill, which runs analysis.prereg.fill under {MEASURED} with this cell's E2 "
    "config and arm and then sets only inputs.engine_cell_label), so these runs stay out of the "
    f"{MEASURED} verdict. The cell's E2 config is registered by its sha256 (protocol.e2_config_sha256; check-job refuses a job "
    "whose --e2-config bytes differ, and a run whose config.yaml differs is not bound) and the only authorised arm is "
    "protocol.arms. Hardware: a run on hardware other than "
    f"'{HARDWARE}' is not bound (measured.hardware). FROZEN PRIMARY ENDPOINTS: STUCK and GOOD exactly as {ENDPOINTS} "
    "defines them (its endpoints block, read by analysis/basin.py load_endpoints, unchanged), evaluated per run over "
    "[t_burst_s + eval_from_s, duration_s) = [5700, 8700) s with hit = pass_rule.hit_metric (a turn is a hit if "
    "cached_tokens / prompt_tokens > 0.5, attributed by completion time): STUCK := hit_eval < 0.2 (the registered constant "
    "burst.trap_hit_below); GOOD := trap_v2 RECOVERED (pass_rule recovered_*), or (hit_eval > 0.8 and backlog slope <= "
    "slope_frac x (lambda - lambda_miss), the registered trap_v2 slope threshold, lambda = 1.35 x lambda_ref). "
    "Statistics per seed (CRN pairs), no pooled intervals; '>= 2/3' means at least ceil(2/3 x the number of registered "
    "seeds) of the registered seeds; a seed without a completed, bound run counts against. Classification: python -m "
    "analysis.r14_cells classify (this file as --prereg). BLINDNESS: the theory session's predictions for these cells "
    "('pred2', branch r13/pred2) are committed separately and pushed before the first job of these cells is submitted; this "
    "registration neither contains nor was written from them. The pass_rule and kill_conditions below are the template's "
    "three-arm rule, inherited unchanged so the rule keys match the analysis; this one-arm cell is judged by the endpoints "
    "and the decision rule above (analysis/r14_cells.py), not by the paired PASS rule.")


def rule_text(cell: str) -> str:
    c = CELLS[cell]
    if c["family"] == "toolslow":
        d = c["param"]
        return (
            f"TOOLSLOW cell (remedy plan N3), label {c['label']}: the E2 NOBURST protocol (arm noburst only: the job glue sets "
            "arrivals.burst=null; the evaluation window is anchored to analysis_t_burst_s = 1200), seeds 0, 1, 2, 300k pool, "
            f"OUTPUT_FEEDBACK=server, 8700-s runs. Protocol from {c['e2']} (a byte copy of configs/agentload_e2_burst.yaml plus "
            f"the workload.tool_slowdown block and meta.notes): every tool call whose sleep STARTS in [1200, 2100) s sleeps its "
            f"drawn tool time plus {d} s (client option workload.tool_slowdown {{t_s: 1200, width_s: 900, add_s: {d}}}, logged "
            "per call in tool_calls.csv); tool calls starting after 2100 s are normal. The slowdown changes no random draw: "
            "plan.csv equals the committed E2 NOBURST run of the same seed at 1.35 x, its CRN control; the same-seed BURST run "
            f"is reported beside it. DECISION RULE (cells d10 and d30 together, as registered): {TOOLSLOW_RULE} (of the "
            "registered seeds 0, 1, 2: 2 of 3 each). Reported as they are otherwise (d10 STUCK, d30 GOOD, or neither). " + _COMMON)
    tau = c["param"]
    return (
        f"SHED cell (remedy plan N4), label {c['label']}: the E2 BURST protocol (arm burst only), seeds 0, 1, 300k pool, "
        f"OUTPUT_FEEDBACK=server, the E2 burst of 200 at [1200, 1260), 8700-s runs. Protocol from {c['e2']} (a byte copy of "
        "configs/agentload_e2_burst.yaml except the arrivals kind, ramp and ramp_is_mult lines and their comment, and "
        f"meta.notes): arrivals.kind ramp, ramp_is_mult true, knots [[0,1.35],[1800,1.35],[1800.001,0],[{1800 + tau},0],"
        f"[{1800 + tau}.001,1.35],[8700,1.35]]: arrivals stop for tau = {tau} s from t_on = 1800 s and restart at 1.35 x "
        "lambda_ref. The candidate arrivals come from the same S_ARRIVALS stream at rate_max = 1.35 x lambda_ref as the "
        "constant BURST arm and are all kept where the ramp is at 1.35 (thinning probability 1), so the arrivals outside the "
        "stop and the burst sessions are those of the committed BURST run of the same seed (CRN); sessions arriving after the "
        "stop get re-drawn specs (their index within origin shifts), so pairing after 1800 s is by the arrival process only. "
        "The job's MULTS must equal the ramp's 1.35 (check-job). Sessions shed := base arrivals of the same-seed BURST "
        "control's plan.csv in [1800, 1800 + tau + 0.001) that the SHED plan lacks. DECISION RULE (cells t600 and t3600 "
        f"together, as registered): {SHED_RULE} (of the registered seeds 0, 1: 2 of 2 each; R1, the rescue cap of "
        "configs/agentload_prereg_2026-10-31_rescue.yaml, defers sessions and drops none). Reported as they are otherwise. "
        + _COMMON)


def fill_registration(cell: str, *, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    c = CELLS[cell]
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                   # noqa: E731
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{INPUTS}/mu_curve.json")), json.loads(rd(f"{INPUTS}/calibration.json")),
        e0b=json.loads(rd(f"{INPUTS}/lambda_cap_bracket.json")), e2_cfg=yaml.safe_load(rd(c["e2"])), lambda_mults=[MULT],
        rule=rule_text(cell), engine_cell_label=MEASURED, mu_curve_path=f"{INPUTS}/mu_curve.json",
        calibration_path=f"{INPUTS}/calibration.json", e0b_path=f"{INPUTS}/lambda_cap_bracket.json", e2_cfg_path=c["e2"],
        n_cap_rule="smallest_within_margin", p=p,
        e2_cfg_sha256=hashlib.sha256((repo / c["e2"]).read_bytes()).hexdigest(), arms=c["arms"])
    if pr["status"] != "FILLED":
        raise ValueError(f"fill did not produce a FILLED registration: {pr['fill_problems']}")
    if pr["measured"].get("hardware") != HARDWARE:
        raise ValueError(f"registered hardware {pr['measured'].get('hardware')!r} != {HARDWARE!r}")
    if pr["protocol"].get("e2_config_sha256") is None or pr["protocol"].get("arms") != c["arms"]:
        raise ValueError(f"{c['e2']}: the sha256 / arms binding was not recorded: {pr['protocol']}")
    pr["inputs"]["engine_cell_label"] = c["label"]
    return pr


def dump_registration(pr: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(pr, sort_keys=False).encode("utf-8")


def _flatten(d: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(d, list):
        out[prefix] = json.dumps(d, sort_keys=True)
    else:
        out[prefix] = d
    return out


ALLOWED = ("inputs.engine_cell_label", "inputs.e2_config", "protocol.e2_config_sha256", "protocol.arms",
           "lambda_selection.lambda_mults", "lambda_selection.rule")
DERIVED_PREFIX = ("predicted_boundaries.capped_drain.",)


def registration_diff(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, List[str]]:
    """Leaves that differ between the 2026-10-24 registration and an r14 one: allowed (label, e2 config and its sha256, arms,
    lambda list, rule), derived (the CAPPED-drain numbers fill derives from the lambda list) and forbidden (anything else)."""
    a, b = _flatten(parent), _flatten(child)
    diff = [k for k in sorted(set(a) | set(b)) if a.get(k, "<missing>") != b.get(k, "<missing>")]
    allowed = [k for k in diff if k in ALLOWED]
    derived = [k for k in diff if k not in allowed and k.startswith(DERIVED_PREFIX)]
    return {"allowed": allowed, "derived": derived, "forbidden": [k for k in diff if k not in allowed and k not in derived]}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r14_prereg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill")
    f.add_argument("--cell", required=True, choices=sorted(CELLS))
    f.add_argument("--out", default=None)
    d = sub.add_parser("diff")
    d.add_argument("--cell", required=True, choices=sorted(CELLS))
    d.add_argument("--file", default=None)
    args = ap.parse_args(argv)
    c = CELLS[args.cell]
    if args.cmd == "fill":
        out = Path(args.out or REPO / c["out"])
        pr = fill_registration(args.cell)
        try:
            with out.open("xb") as fh:                                         # refuses to overwrite
                fh.write(dump_registration(pr))
        except FileExistsError:
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        print(f"wrote {out} status={pr['status']} label={pr['inputs']['engine_cell_label']} arms={pr['protocol']['arms']} "
              f"e2_config_sha256={pr['protocol']['e2_config_sha256']}")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0
    parent = yaml.safe_load((REPO / PARENT).read_text())
    child = yaml.safe_load(Path(args.file or REPO / c["out"]).read_text())
    res = registration_diff(parent, child)
    a, b = _flatten(parent), _flatten(child)
    print(f"parent {PARENT}  vs  {args.file or c['out']}")
    for kind in ("allowed", "derived", "forbidden"):
        print(f"{kind}: {len(res[kind])}")
        for k in res[kind]:
            va, vb = a.get(k, "<missing>"), b.get(k, "<missing>")
            sa = str(va) if len(str(va)) < 90 else str(va)[:87] + "..."
            sb = str(vb) if len(str(vb)) < 90 else str(vb)[:87] + "..."
            print(f"  {k}: {sa}  ->  {sb}")
    return 1 if res["forbidden"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
