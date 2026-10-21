"""Consistency guards over a set of runs that are about to be compared.

A guard problem does not change any number; it says that the comparison may not mean what it appears to mean.
``summarize`` writes them to ``guards.json`` (and into meta.json), prints them to stderr, and with
``--strict-guards`` exits non-zero if any problem has severity ``error``.

Checks (code: meaning)
  start_state_unverified   an open-loop (from-empty) run whose post-flush canary check did not pass or was not recorded
  hardware_mixed           runs on different hardware strings (GPU model / memory) in one comparison
  hardware_vs_calibration  a run's hardware differs from the calibration.json that set its arrival rate
  calibration_hardware     calibration.json records no single hardware string
  output_source_mixed      a run used both server-returned and synthetic output ids (effective Delta differs by d)
  output_source_differs    runs in one comparison used different output-id sources
  prompt_tokens_mismatch   server prompt_tokens != tokens sent on some requests (tokens mode)
  transport_errors         connection-level request failures (they kill sessions and shed offered load)
CLI:  python -m analysis.guards calib-hw --calib calibration.json --hardware "NVIDIA A100 80GB PCIe, 81920 MiB"
      (exit 1 if the calibration's hardware differs; used by slurm/common.sh before cap/burst runs)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .load import Run

ERROR, WARN = "error", "warn"


def _problem(sev: str, code: str, msg: str, run: Optional[Run] = None) -> Dict[str, Any]:
    return {"severity": sev, "code": code, "run_dir": str(run.dir) if run is not None else None, "message": msg}


def load_calibration_for(run: Run) -> Optional[Dict[str, Any]]:
    """The calibration.json that set this run's arrival rate (``arrivals.lambda_ref = 'path:key'``), if readable."""
    ref = (run.cfg.get("arrivals") or {}).get("lambda_ref")
    if not (isinstance(ref, str) and ":" in ref):
        return None
    path = Path(ref.rsplit(":", 1)[0])
    cands = [path] if path.is_absolute() else [Path.cwd() / path, run.dir.parent.parent.parent / path]
    for c in cands:
        if c.is_file():
            try:
                return json.loads(c.read_text())
            except Exception:
                return None
    return None


def check_runs(runs: Sequence[Run], require_verified_start: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if require_verified_start:
        for r in runs:
            if (r.cfg.get("arrivals") or {}).get("kind") == "closed":
                continue
            v = r.start_state_verified
            if v is not True:
                why = "not recorded" if v is None else f"verification failed: {r.meta.get('start_state_detail', '')}"
                out.append(_problem(ERROR, "start_state_unverified",
                                    f"from-empty premise not verified ({why})", r))
    hw = sorted({str(r.hardware) for r in runs})
    if len(hw) > 1:
        out.append(_problem(ERROR, "hardware_mixed", f"runs on different hardware: {hw}"))
    for r in runs:
        cal = load_calibration_for(r)
        if cal is None:
            continue
        ch = cal.get("hardware")
        if ch is None:
            out.append(_problem(WARN, "calibration_hardware", "calibration.json records no single hardware string", r))
        elif str(ch) != str(r.hardware):
            out.append(_problem(ERROR, "hardware_vs_calibration",
                                f"run hardware {r.hardware!r} != calibration hardware {ch!r}: lambda_miss does not "
                                "transfer across GPU variants", r))
    srcs = []
    for r in runs:
        s = r.output_ids_sources
        if len(s) > 1:
            out.append(_problem(ERROR, "output_source_mixed", f"mixed output_ids_source {s}", r))
        srcs.append(tuple(sorted(s)))
    if len(set(srcs)) > 1:
        out.append(_problem(ERROR, "output_source_differs", f"runs use different output-id sources: {sorted(set(srcs))}"))
    for r in runs:
        o = r.meta.get("outcome") or {}
        if o.get("prompt_tokens_mismatch"):
            out.append(_problem(ERROR, "prompt_tokens_mismatch",
                                f"{o['prompt_tokens_mismatch']} requests where server prompt_tokens != tokens sent", r))
        tr = (o.get("errors_by_kind") or {}).get("transport", 0)
        if tr:
            out.append(_problem(WARN, "transport_errors", f"{tr} transport-level request errors", r))
    return out


def summarize_problems(problems: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"n_errors": sum(p["severity"] == ERROR for p in problems),
            "n_warnings": sum(p["severity"] == WARN for p in problems),
            "codes": sorted({p["code"] for p in problems})}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.guards")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calib-hw", help="exit 1 unless calibration.json's hardware equals --hardware")
    c.add_argument("--calib", required=True)
    c.add_argument("--hardware", required=True)
    args = ap.parse_args(argv)
    cal = json.loads(Path(args.calib).read_text())
    ch = cal.get("hardware")
    if ch is None:
        print(f"calibration {args.calib} records no single hardware string (hardware_all={cal.get('hardware_all')})")
        return 1
    if str(ch) != str(args.hardware):
        print(f"hardware mismatch: calibration {ch!r} vs this job {args.hardware!r}")
        return 1
    print(f"hardware matches calibration: {ch!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
