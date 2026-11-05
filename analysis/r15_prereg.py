"""Registrations of the r15 TOOLSLOW cells T1 and T2: SGLang FCFS with waiting-prefix refresh, 300k pool, one rate per cell.

T1  sglang-fcfs-r1-toolslow-d30w1800   1.35 x lambda_ref, no burst (arm noburst): every tool call whose sleep starts in
    [1200, 3000) s sleeps its drawn tool time plus 30 s (configs/agentload_e2_toolslow_d30w1800.yaml: the registered r14 d30
    config with width_s 1800 instead of 900; nothing else differs). The decisive cell: a reliability test of the trigger.
T2  sglang-fcfs-r1-toolslow-d15-165    1.65 x lambda_ref, no burst: every tool call whose sleep starts in [1200, 2100) s sleeps
    its drawn tool time plus 15 s (configs/agentload_e2_toolslow_d15.yaml: the r14 d30 config with add_s 15 instead of 30).
    Optional: the cell where pred2's fluid verdict and the simulator's exact-plan runs disagree (on seeds 1 and 2).
Both: seeds 0, 1, 2, one seed per job, 8700-s runs, client option workload.tool_slowdown {t_s, width_s, add_s}. Each run pairs by
seed (common random numbers) with the committed E2 NOBURST run at the cell's rate (jobs 17093387-404,
results/nova/e2_170933xx_pulled_20261025-144558); the slowdown changes no random draw, so plan.csv must equal the control's.

A copy of analysis/r14_prereg.py (frozen, unchanged) with a per-cell rate multiplier: each CELLS entry carries ``mult`` (its
only registered lambda_mults entry) and its own decision rule (tri-state per cell, no conjunction across cells). As in
``analysis.r14_prereg fill``, ``analysis.prereg.fill`` cannot look the new labels up in mu_curve.json or the E0b bracket, so the
fill runs under the MEASURED label sglang-fcfs-r1 from the inputs of the 2026-10-24 registration (prereg/inputs/2026-10-23),
with the cell's E2 config (its sha256 goes into protocol.e2_config_sha256), the cell's arm (protocol.arms) and the cell's mult
(lambda_selection.lambda_mults), and only ``inputs.engine_cell_label`` is then set to the cell's label. Output is exactly what
``analysis.prereg fill`` writes (yaml.safe_dump, sort_keys=False), LF, never overwrites.

CLI:  python -m analysis.r15_prereg fill --cell toolslow-d30w1800|toolslow-d15-165 [--out FILE]
      python -m analysis.r15_prereg diff --cell CELL [--file FILE]     (scripted diff against the 2026-10-24 registration)
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
CONTROL_JOBS = "17093387-17093404 (results/nova/e2_170933xx_pulled_20261025-144558)"
R14_D30 = "configs/agentload_prereg_2026-10-31_toolslow_d30.yaml"
R14_D30_JOBS = "17169905-17169907 (results/nova/toolslow_shed_1716990x_pulled_20261101-154800)"
R14_D30_CONFIG = "configs/agentload_e2_toolslow_d30.yaml"

# the decision rule of each cell (tri-state, per cell; the same words for both cells, applied to each cell alone)
TRI_RULE = ("TRAPS iff STUCK in >= 2 of the 3 registered seeds; NO-TRAP iff GOOD in >= 2 of 3; else MIXED (a cell that meets "
            "both counts, possible only through runs that are both STUCK and GOOD, is MIXED)")

CELLS: Dict[str, Dict[str, Any]] = {
    "toolslow-d30w1800": {"label": "sglang-fcfs-r1-toolslow-d30w1800", "id": "T1", "mult": 1.35,
                          "t_s": 1200, "width_s": 1800, "add_s": 30,
                          "e2": "configs/agentload_e2_toolslow_d30w1800.yaml", "arms": ["noburst"], "seeds": [0, 1, 2],
                          "out": "configs/agentload_prereg_2026-11-05_toolslow_d30w1800.yaml"},
    "toolslow-d15-165": {"label": "sglang-fcfs-r1-toolslow-d15-165", "id": "T2", "mult": 1.65,
                         "t_s": 1200, "width_s": 900, "add_s": 15,
                         "e2": "configs/agentload_e2_toolslow_d15.yaml", "arms": ["noburst"], "seeds": [0, 1, 2],
                         "out": "configs/agentload_prereg_2026-11-05_toolslow_d15_165.yaml"},
}


def decision_rule(cell: str) -> str:
    """The cell's own decision rule (no conjunction with any other cell); r15_cells.CELLS[label]['rule'] is this string."""
    c = CELLS[cell]
    return f"{c['id']} ({c['label']}) is decided alone, with no conjunction with any other cell: {TRI_RULE}"


def _window(c: Dict[str, Any]) -> str:
    return f"[{c['t_s']}, {c['t_s'] + c['width_s']}) s"


def _common(c: Dict[str, Any]) -> str:
    m = c["mult"]
    point = {1.35: "the lower registered point (m1)", 1.65: "the upper registered point (m2)"}[m]
    return (
        f"Single point {m:g} x lambda_ref: {point} of {PARENT}, same inputs ({INPUTS}: mu_curve, calibration, E0b bracket), "
        "same window (1, 2.0) x lambda_ref and the same 1/3-2/3 rule written on 2026-10-23 before E0b was read; reused "
        "unchanged so that each run pairs by seed (common random numbers) with the committed 300k E2 NOBURST run at "
        f"{m:g} x (jobs {CONTROL_JOBS}). The measured values are those of cell {MEASURED} (same hardware, pool, policy and "
        f"refresh flag; filled by analysis.r15_prereg fill, which runs analysis.prereg.fill under {MEASURED} with this cell's "
        "E2 config, arm and rate and then sets only inputs.engine_cell_label), so these runs stay out of the "
        f"{MEASURED} verdict. The cell's E2 config is registered by its sha256 (protocol.e2_config_sha256; check-job refuses a "
        "job whose --e2-config bytes differ, and a run whose config.yaml differs is not bound), the only authorised arm is "
        f"protocol.arms and the only authorised rate is lambda_selection.lambda_mults = [{m:g}]. Hardware: a run on hardware "
        f"other than '{HARDWARE}' is not bound (measured.hardware). FROZEN PRIMARY ENDPOINTS: STUCK and GOOD exactly as "
        f"{ENDPOINTS} defines them (its endpoints block, read by analysis/basin.py load_endpoints, unchanged), evaluated per "
        "run over [t_burst_s + eval_from_s, duration_s) = [5700, 8700) s with hit = pass_rule.hit_metric (a turn is a hit if "
        "cached_tokens / prompt_tokens > 0.5, attributed by completion time): STUCK := hit_eval < 0.2 (the registered constant "
        "burst.trap_hit_below); GOOD := trap_v2 RECOVERED (pass_rule recovered_*), or (hit_eval > 0.8 and backlog slope <= "
        "slope_frac x (lambda - lambda_miss), the registered trap_v2 slope threshold, lambda = the run's resolved rate, "
        f"{m:g} x lambda_ref). A run counts only if it completed, is bound to this file, ran arm noburst at {m:g} x on a "
        "registered seed, its plan.csv equals the same-seed control's (same columns and rows; sid, origin, idx and n_turns "
        "exactly, arrival_s and tool_time_total_s within 1e-9 s), and the manipulation happened (checked from the run's own "
        "files, stricter than r14): meta.tool_slowdown is this cell's block; its tool_calls.csv is complete (its row count and "
        "its count of slowed calls equal meta.outcome.tool_slowdown) and logs at least one tool call starting in "
        f"{_window(c)}; every call starting in that window has add_s = {c['add_s']}; no call starting outside it has add_s != "
        "0; and every call has t_ready = t_start + tool_s + add_s. Statistics per seed (CRN pairs), no pooled intervals; a "
        "seed without a counted run counts against both TRAPS and NO-TRAP; two counted runs of one seed leave the cell "
        "undecided until a human resolves it. Classification: python -m analysis.r15_cells classify (this file as --prereg). "
        "The pass_rule and kill_conditions "
        "below are the template's three-arm rule, inherited unchanged so the rule keys match the analysis; this one-arm cell is "
        "judged by the endpoints and the decision rule above (analysis/r15_cells.py), not by the paired PASS rule.")


_HISTORY = (
    "HOW THE CELLS WERE CHOSEN (not blind to earlier outcomes): T1 and T2 were chosen on 2026-11-05 after the registered r14 "
    f"d30 cell ({R14_D30}, jobs {R14_D30_JOBS}: 30 s added to tool calls starting in [1200, 2100) s at 1.35 x) trapped 1 of "
    "its 3 seeds (STUCK in seed 2 only, GOOD in seeds 0 and 1, so its registered rule failed), and after reading simulator "
    "outputs (the calibrated simulator with a tool-slowdown hook written after the d10 / d30 results were known, run on the "
    "exact client plans and on random seeds). Every model we have (the calibrated simulator and the fluid model pred2) "
    "predicts that T1 TRAPS, so T1 is a reliability test of the trigger (does a tool-side slowdown with no added sessions "
    "trap the engine in at least 2 of 3 seeds?), not a test between models. T2 is the model-discrimination cell: pred2's "
    "fluid verdict (one plan-averaged call applied to every seed) and the simulator's exact-plan runs predict different "
    "outcomes for some of its seeds, so T2 discriminates pred2 vs the simulator per seed. The models' per-seed predictions "
    "are not part of this file: they are frozen in their own committed files (which also fix how each model output, "
    "including pred2's per-seed layer, is scored), pushed before the first job of these cells is submitted; the TRAPS / "
    "NO-TRAP / MIXED call below depends on neither model. ")


def rule_text(cell: str) -> str:
    c = CELLS[cell]
    other = [k for k in CELLS if k != cell][0]
    if c["id"] == "T1":
        protocol = (
            f"Protocol from {c['e2']} (a byte copy of {R14_D30_CONFIG}, the registered r14 d30 config, except the "
            "workload.tool_slowdown values, their comment lines and meta.notes): every tool call whose sleep STARTS in "
            f"{_window(c)} sleeps its drawn tool time plus {c['add_s']} s (client option workload.tool_slowdown {{t_s: "
            f"{c['t_s']}, width_s: {c['width_s']}, add_s: {c['add_s']}}}, logged per call in tool_calls.csv); tool calls "
            f"starting at or after {c['t_s'] + c['width_s']} s are normal. Only the window width differs from the registered "
            "d30 cell (900 s there): same delay, same start, same rate, same seeds, same controls. ")
    else:
        protocol = (
            f"Protocol from {c['e2']} (a byte copy of {R14_D30_CONFIG}, the registered r14 d30 config, except the "
            "workload.tool_slowdown values, their comment lines and meta.notes): every tool call whose sleep STARTS in "
            f"{_window(c)} sleeps its drawn tool time plus {c['add_s']} s (client option workload.tool_slowdown {{t_s: "
            f"{c['t_s']}, width_s: {c['width_s']}, add_s: {c['add_s']}}}, logged per call in tool_calls.csv); tool calls "
            f"starting at or after {c['t_s'] + c['width_s']} s are normal. The d30 window at half the delay, run at "
            f"{c['mult']:g} x instead of 1.35 x. ")
    return (
        f"TOOLSLOW cell {c['id']} (r15), label {c['label']}: the E2 NOBURST protocol (arm noburst only: the job glue sets "
        "arrivals.burst=null; the evaluation window is anchored to analysis_t_burst_s = 1200), seeds 0, 1, 2 (one seed per "
        f"job), 300k pool, OUTPUT_FEEDBACK=server, 8700-s runs, {c['mult']:g} x lambda_ref. " + protocol
        + "The slowdown changes no random draw: plan.csv equals the committed E2 NOBURST run of the same seed at "
        f"{c['mult']:g} x, its CRN control; the same-seed BURST run at {c['mult']:g} x is reported beside it. " + _HISTORY
        + f"DECISION RULE: {decision_rule(cell)}. The other r15 cell, {CELLS[other]['label']}, is decided by its own "
        "registration. " + _common(c))


def fill_registration(cell: str, *, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    c = CELLS[cell]
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                   # noqa: E731
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{INPUTS}/mu_curve.json")), json.loads(rd(f"{INPUTS}/calibration.json")),
        e0b=json.loads(rd(f"{INPUTS}/lambda_cap_bracket.json")), e2_cfg=yaml.safe_load(rd(c["e2"])), lambda_mults=[c["mult"]],
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
    if pr["lambda_selection"].get("lambda_mults") != [float(c["mult"])]:
        raise ValueError(f"registered lambda_mults {pr['lambda_selection'].get('lambda_mults')} != [{c['mult']}]")
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
    """Leaves that differ between the 2026-10-24 registration and an r15 one: allowed (label, e2 config and its sha256, arms,
    lambda list, rule), derived (the CAPPED-drain numbers fill derives from the lambda list) and forbidden (anything else)."""
    a, b = _flatten(parent), _flatten(child)
    diff = [k for k in sorted(set(a) | set(b)) if a.get(k, "<missing>") != b.get(k, "<missing>")]
    allowed = [k for k in diff if k in ALLOWED]
    derived = [k for k in diff if k not in allowed and k.startswith(DERIVED_PREFIX)]
    return {"allowed": allowed, "derived": derived, "forbidden": [k for k in diff if k not in allowed and k not in derived]}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.r15_prereg")
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
              f"lambda_mults={pr['lambda_selection']['lambda_mults']} e2_config_sha256={pr['protocol']['e2_config_sha256']}")
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
