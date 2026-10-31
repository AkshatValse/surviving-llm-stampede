"""Registrations of the rescue cells (plan R1, R4) and of the R1 GPU smoke job.

``analysis.prereg fill --engine-cell-label sglang-fcfs-r1-rescue`` cannot be used directly: fill looks the label up in
mu_curve.json and in the E0b bracket, which only hold the measured cells (``sglang-fcfs-r1``, ``sglang-fcfs-r1-native``). As in
``analysis.basin fill``, the fill therefore runs under the MEASURED label, with the rescue cell's E2 config (so fill copies its
gate block into ``protocol.gate`` and the config's sha256 into ``protocol.e2_config_sha256``), and only
``inputs.engine_cell_label`` is then set to the rescue cell's label. That keeps the rescue runs out of the measured cells'
verdicts. Output is exactly what ``analysis.prereg fill`` writes (yaml.safe_dump, sort_keys=False), LF, never overwrites.

CLI:  python -m analysis.rescue_prereg fill --cell r1|r4|smoke [--out FILE]
      python -m analysis.rescue_prereg diff --cell r1|r4|smoke [--file FILE]     (scripted diff against the parent registration)
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
from . import rescue as R
from .params import AnalysisParams, load_params

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = "configs/agentload_prereg_template.yaml"
PARAMS = "configs/agentload_analysis.yaml"
PRED_TAG = "r11-rescue-pred"
PRED_DIR = "results/r11_predict_rescue/20261030-195231"
HARDWARE = "NVIDIA A100 80GB PCIe, 81920 MiB"

CELLS: Dict[str, Dict[str, Any]] = {
    "r1": {"label": "sglang-fcfs-r1-rescue", "measured": "sglang-fcfs-r1", "inputs": "prereg/inputs/2026-10-23",
           "e2": "configs/agentload_e2_rescue.yaml", "mults": [1.35, 1.65],
           "parent": "configs/agentload_prereg_2026-10-24.yaml", "out": "configs/agentload_prereg_2026-10-31_rescue.yaml"},
    "r4": {"label": "sglang-fcfs-r1-rescue-native", "measured": "sglang-fcfs-r1-native",
           "inputs": "prereg/inputs/2026-10-25-native", "e2": "configs/agentload_e2_rescue_native.yaml", "mults": [4.0],
           "parent": "configs/agentload_prereg_2026-10-25_native.yaml",
           "out": "configs/agentload_prereg_2026-10-31_rescue_native.yaml"},
    "smoke": {"label": "sglang-fcfs-r1-rescue-smoke", "measured": "sglang-fcfs-r1", "inputs": "prereg/inputs/2026-10-23",
              "e2": "configs/agentload_e2_rescue_smoke.yaml", "mults": [1.65],
              "parent": "configs/agentload_prereg_2026-10-24.yaml",
              "out": "configs/agentload_prereg_2026-10-31_rescue_smoke.yaml"},
}


def _j(d: Any) -> str:
    return json.dumps(d, sort_keys=True)


def _constants_text(profile: str) -> str:
    """The frozen constants of analysis/rescue.py, by value (they are part of the registered rule)."""
    pr = R.PROFILES[profile]
    keys = ("label", "control_label", "rate_mults", "seeds", "t_on_s", "n_cap", "horizon_s", "t_burst_s", "pass_min_rescued",
            "require_controls_stuck", "primary_rate", "refute_relapse_min", "refute_unreleased_min", "prediction_cell",
            "hardware")
    return (f"FROZEN CONSTANTS (analysis/rescue.py at this tag, by value): RULE={_j(R.RULE)}; STUCK={_j(R.STUCK)}; "
            f"PROFILES[{profile!r}]={_j({k: pr[k] for k in keys})}; CHECK={_j(R.CHECK)}; "
            f"T_REL_SCORING={_j(R.T_REL_SCORING)} (descriptive).")


_COMMON_RULE = (
    "REGISTERED PER-RUN RULE (FU-hit = share of completed turns >= 2, attributed by completion time, with cached/prompt > 0.5): "
    "(a) VALID: FU-hit < 0.2 over [t_on - 300, t_on) AND more than 50 outstanding at t_on (outstanding = requests in flight + "
    "sessions waiting at the gate + paused sessions); a run whose meta.hardware differs from the registered hardware string "
    f"('{HARDWARE}': all three nova22-gpu nodes report it and the sbatch header excludes nova22-amp-7) is INVALID; an "
    "undefined VALID window is INVALID; INVALID counts against PASS. (b) RELEASED with t_rel <= 7200 s (first release gate "
    "event). (c) POST-GOOD over [t_rel + 300, 8700): every 300-s window (tiling from the start; a short remainder is covered by "
    "the window ending at 8700) has FU-hit >= 0.5, the whole interval has FU-hit > 0.8, the uncached-token rate is < 0.5 x "
    "the all-miss reference, and the registered trap_v2 RECOVERED predicate holds over the last 300 s; a window with no "
    "completed follow-up turn fails (c) but is not a RELAPSE. RESCUED = a and b and c. RELAPSE = any such window with FU-hit "
    "< 0.2. STUCK (same-seed committed BURST control) := FU-hit over [t_on, 8700) < 0.2 AND trap_v2 RECOVERED false over the "
    "last 300 s. CHANGED CONSTANTS ACCEPTED BY THE LEAD BEFORE THIS TAG (after the bundle-3 review, before any rescue run): "
    "REFUTED takes precedence over PASS (a cell that also meets PASS is listed, the verdict is REFUTED); the no-shed part of a "
    "PASS claim is withheld if any counted run has failed sessions (a failed session also leaves the gate, which is "
    "shedding); R4 requires stuck same-seed BURST controls like R1; the check-run tolerances CHECK (up to 3 sessions spawned "
    "in the last instant and never started, release on the t_on + k*release_check_s grid within 2 s, the hold within 2 s, "
    "asyncio timers up to 0.05 s early, engage within 10 s of t_on). Pairing: common random numbers with the committed "
    "BURST / NOBURST runs of the same seed and rate (BURST plan.csv sha256 equal; NOBURST plan = rescue plan minus the burst "
    "sessions), equal resolved rate, references, hardware and burst time; a cell with pairing or protocol problems does not "
    "count. Blinding: no requests.csv of a rescue run is read before all cells of a rate end; the job runs only the "
    "mechanical analysis.rescue check-run (no hit fractions). The verdict is python -m analysis.rescue verdict with this "
    "file as --prereg and the bundle-3 predictions as --predictions. The pass_rule and kill_conditions below are the "
    "template's three-arm rule, inherited unchanged so the rule keys match the analysis; this one-arm cell is judged by the "
    "rule above, not by the paired PASS rule.")


def rule_text(cell: str) -> str:
    if cell == "r1":
        return (
            "Rate points 1.35 and 1.65 x lambda_ref: the registered points of configs/agentload_prereg_2026-10-24.yaml, same "
            "inputs (prereg/inputs/2026-10-23: mu_curve, calibration, E0b bracket), same window (1, 2.0) x lambda_ref and the "
            "same 1/3-2/3 rule written on 2026-10-23 before E0b was read; cap n_cap = 20 by smallest_within_margin (5% of the "
            "mu(n) peak); measured values of cell sglang-fcfs-r1 (filled by analysis.rescue_prereg fill under that label, then "
            "only inputs.engine_cell_label set), so these runs stay out of the sglang-fcfs-r1 verdict. RESCUE cell (plan R1), "
            "arm rescue only, seeds 0, 1, 2, 300k pool, OUTPUT_FEEDBACK=server, the E2 burst of 200 at [1200, 1260), 8700-s "
            "runs. Gate (protocol.gate, copied from configs/agentload_e2_rescue.yaml, whose sha256 is protocol.e2_config_sha256): "
            "mode rescue, uncapped until t_on_s = 1800 (the run is the BURST run until then), then n_cap = 20 by attrition plus "
            "pause (a session whose tool call ends while active > cap gives up its slot and joins a resume deque served before "
            "new arrivals, FIFO within each), released (cap removed) at the first 10-s tick with t >= t_on + 600 at which both "
            "queues have been empty for 300 s; no forced release. " + _COMMON_RULE + " DECISION: per rate cell PASS iff >= 2 of "
            "the 3 registered seeds are RESCUED and every same-seed committed BURST control is STUCK; the no-shed drain claim is "
            "made if 1.35 x passes, 'at both test points' if 1.65 x passes too; REFUTED (a negative result) if >= 2 of the 6 "
            "runs RELAPSE or >= 2 of the 6 are not released by 7200 s; a missing seed counts against PASS. Predictions (tag "
            f"{PRED_TAG}, {PRED_DIR}, cell R1_rescue): RESCUED 20/20 at both rates, PASS. " + _constants_text("r1"))
    if cell == "r4":
        return (
            "Rate point 4.0 x lambda_ref: the upper registered point (m2) of configs/agentload_prereg_2026-10-25_native.yaml, "
            "same inputs (prereg/inputs/2026-10-25-native), same window (1, 5.5) x lambda_ref and the same 1/3-2/3 rule written "
            "before native E0b was read; cap n_cap = 64 by smallest_within_margin; measured values of cell sglang-fcfs-r1-native "
            "(filled by analysis.rescue_prereg fill under that label, then only inputs.engine_cell_label set). RESCUE cell at "
            "the native 955,757-token pool (plan R4), KV_TOKENS=native, arm rescue only, seeds 0, 1, 2, the E2 burst of 200 at "
            "[1200, 1260), 8700-s runs. Gate (protocol.gate, from configs/agentload_e2_rescue_native.yaml): as R1 with n_cap = "
            "64 and t_on_s = 2100. ENGAGE TIME: plan R4 said 2400; the lead moved it to 2100 after the 2400-s bundle-3 "
            "prediction (13/20 RESCUED mixed, below the plan's 7/10 rethink threshold) was seen and before any real rescue run; "
            "VALID is therefore FU-hit < 0.2 over [1800, 2100) and more than 50 outstanding at 2100 s. " + _COMMON_RULE
            + " DECISION: PASS iff >= 2 of the 3 registered seeds are RESCUED and every same-seed committed native BURST "
            "control is STUCK; >= 2 of 3 RELAPSE refutes persistence at the native pool; INVALID runs count against PASS; a "
            f"missing seed counts against PASS. Prediction of record (tag {PRED_TAG}, {PRED_DIR}, cell R4s_t2100): RESCUED "
            "16/20 (mixed) and 18/20 (separate), exact seeds 0-2 RESCUED, PASS. " + _constants_text("r4"))
    if cell == "smoke":
        return (
            "GPU SMOKE JOB of plan R1 (cell sglang-fcfs-r1-rescue-smoke): a mechanical gate test, NOT a test of any hypothesis; "
            "no verdict of it is ever decisive and it is never pooled with the R1 or R4 cells. Rate point 1.65 x lambda_ref, "
            "the m2 point of configs/agentload_prereg_2026-10-24.yaml (same inputs prereg/inputs/2026-10-23, window, cap rule "
            "smallest_within_margin; "
            "n_cap = 20), measured values of cell sglang-fcfs-r1 (filled under that label, then only inputs.engine_cell_label "
            "set). Protocol from configs/agentload_e2_rescue_smoke.yaml (sha256 protocol.e2_config_sha256): 2400-s run, burst "
            "of 200 at 300 s, gate mode rescue, n_cap 20, t_on 900, hold 120, min_on 300, seed 0, arm rescue only. The smoke "
            "passes iff python -m analysis.rescue check-run --smoke exits 0: one engage within 10 s of t_on at the cap, >= 10 "
            "pause and >= 10 resume events, session conservation, the gate-log invariants and 0 request errors. A release is "
            "NOT required (bundle-3 prediction, tag r11-rescue-pred: release before 2400 s in 0/10 seeds; the plan requires a "
            f"release only if >= 8/10). A run whose hardware differs from the registered string ('{HARDWARE}') is refused at job "
            "start. The "
            "capped_drain limit below is informational (no CAPPED arm runs). The R1 and R4 jobs depend on this job (afterok).")
    raise ValueError(f"unknown cell {cell!r} (r1 | r4 | smoke)")


def fill_registration(cell: str, *, repo: Path = REPO, params: Optional[AnalysisParams] = None) -> Dict[str, Any]:
    c = CELLS[cell]
    p = params if params is not None else load_params(repo / PARAMS, [])
    rd = lambda rel: (repo / rel).read_text()                                   # noqa: E731
    inp = c["inputs"]
    pr = prereg_mod.fill(
        yaml.safe_load(rd(TEMPLATE)), json.loads(rd(f"{inp}/mu_curve.json")), json.loads(rd(f"{inp}/calibration.json")),
        e0b=json.loads(rd(f"{inp}/lambda_cap_bracket.json")), e2_cfg=yaml.safe_load(rd(c["e2"])), lambda_mults=c["mults"],
        rule=rule_text(cell), engine_cell_label=c["measured"], mu_curve_path=f"{inp}/mu_curve.json",
        calibration_path=f"{inp}/calibration.json", e0b_path=f"{inp}/lambda_cap_bracket.json", e2_cfg_path=c["e2"],
        n_cap_rule="smallest_within_margin", p=p,
        e2_cfg_sha256=hashlib.sha256((repo / c["e2"]).read_bytes()).hexdigest())
    if pr["status"] != "FILLED":
        raise ValueError(f"fill did not produce a FILLED registration: {pr['fill_problems']}")
    g = pr["protocol"].get("gate") or {}
    if g.get("mode") != "rescue" or g.get("n_cap") != pr["measured"]["n_cap"]:
        raise ValueError(f"{c['e2']} gate {g} does not register the rescue arm at the registered cap {pr['measured']['n_cap']}")
    if pr["measured"].get("hardware") != HARDWARE:
        raise ValueError(f"registered hardware {pr['measured'].get('hardware')!r} != {HARDWARE!r}")
    if cell in R.PROFILES and (float(g["t_on_s"]) != float(R.PROFILES[cell]["t_on_s"])
                               or int(g["n_cap"]) != int(R.PROFILES[cell]["n_cap"])
                               or R.PROFILES[cell]["hardware"] != HARDWARE):
        raise ValueError(f"{c['e2']} gate {g} disagrees with analysis.rescue PROFILES[{cell!r}]")
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


ALLOWED = ("inputs.engine_cell_label", "inputs.e2_config", "protocol.e2_config_sha256", "lambda_selection.lambda_mults",
           "lambda_selection.rule")
ALLOWED_PREFIX = ("protocol.gate.",)
DERIVED_PREFIX = ("predicted_boundaries.capped_drain.",)
SMOKE_EXTRA = ("protocol.duration_s", "protocol.t_burst_s", "fill_problems")


def registration_diff(parent: Dict[str, Any], child: Dict[str, Any], cell: str) -> Dict[str, List[str]]:
    """Leaves that differ between the parent registration and the rescue one: allowed (label, e2 config, gate block, its
    sha256, lambda list, rule), derived (the CAPPED-drain numbers fill derives from the protocol and lambda list; for the smoke
    registration also its run length, burst time and fill warnings) and forbidden (anything else)."""
    a, b = _flatten(parent), _flatten(child)
    diff = [k for k in sorted(set(a) | set(b)) if a.get(k, "<missing>") != b.get(k, "<missing>")]
    allowed = [k for k in diff if k in ALLOWED or k.startswith(ALLOWED_PREFIX)]
    derived = [k for k in diff if k not in allowed and (k.startswith(DERIVED_PREFIX) or (cell == "smoke" and k in SMOKE_EXTRA))]
    return {"allowed": allowed, "derived": derived, "forbidden": [k for k in diff if k not in allowed and k not in derived]}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.rescue_prereg")
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
        out = Path(args.out or c["out"])
        pr = fill_registration(args.cell)
        try:
            with out.open("xb") as fh:                                         # refuses to overwrite
                fh.write(dump_registration(pr))
        except FileExistsError:
            print(f"refusing to overwrite {out}", file=sys.stderr)
            return 2
        print(f"wrote {out} status={pr['status']} label={pr['inputs']['engine_cell_label']} n_cap={pr['measured']['n_cap']}")
        for x in pr["fill_problems"]:
            print(f"  [{x['severity']}] {x['code']}: {x['message']}")
        return 0
    parent = yaml.safe_load((REPO / c["parent"]).read_text())
    child = yaml.safe_load(Path(args.file or REPO / c["out"]).read_text())
    res = registration_diff(parent, child, args.cell)
    a, b = _flatten(parent), _flatten(child)
    print(f"parent {c['parent']}  vs  {args.file or c['out']}")
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
