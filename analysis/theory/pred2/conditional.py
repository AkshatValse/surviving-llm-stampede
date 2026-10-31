"""Registration-conditional predictions for the H200 and Llama-3.1-8B cells (the frozen rule of analysis/theory/merged/scoring.yaml,
general.registration_conditional_rule, made mechanical).

After a cell's E2 registration is pushed, run (Windows Git Bash, from a clone at tag r13-theory-pred or at this pred2 commit,
whose analysis/theory diff against 997d2c4 lists only new files):

    PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell h200_300k --registration configs/agentload_prereg_<date>_h200.yaml
    PYTHONPATH="src;." python -m analysis.theory.pred2.conditional --cell llama31_8b_300k --registration configs/agentload_prereg_<date>_llama31.yaml

It reads ONLY these registration fields: lambda_selection.lambda_mults (the registered rate multiples) and measured.n_cap (the
CAPPED-arm cap), plus for Llama measured.lambda_ref (the measured E0a turns-based lambda_miss) and
measured.all_miss_uncached_tokens_per_s (the measured E0a token rate).  It writes, under results/theory/pred2/conditional/,
one derived spec per variant (base: the frozen spec; changed: e2.multiples, e2.cap, tests = []; Llama also lambda_ref, and a
second variant with fit_speed_to_e0a = the measured tokens), runs the FROZEN analysis.theory.predict on it, and writes
<cell>_conditional[_<variant>].json with a 'conditional' block (registration path, its sha256, the fields read, the rule).
H200 variants: the primary h200_300k and the four frozen band variants.  Manual form: --mults 1.10 1.15 --cap 32.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import yaml

from ..merged.spec import ROOT, load_spec
from ..predict import clean, predict
from .common import CELLS_DIR, OUT_DIR, provenance

H200_VARIANTS = ["h200_300k", "h200_300k_ratiofit", "h200_300k_lamratiofit", "h200_300k_decode2", "h200_300k_e0a2"]
RULE = ("rerun predict.py at the frozen tag with a spec that differs from the frozen one ONLY in e2.multiples, e2.cap and tests "
        "(Llama: plus lambda_ref = the measured E0a value and a second variant with fit_speed_to_e0a = the measured E0a tokens); "
        "read only the registration's rate and cap fields; write <cell>_conditional.json, labelled conditional")


def read_registration(path: str) -> Dict[str, Any]:
    with open(path) as f:
        reg = yaml.safe_load(f)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    ls, ms = reg.get("lambda_selection") or {}, reg.get("measured") or {}
    fields = dict(lambda_mults=[float(x) for x in ls.get("lambda_mults") or []], n_cap=ms.get("n_cap"),
                  lambda_ref=ms.get("lambda_ref"), all_miss_uncached_tokens_per_s=ms.get("all_miss_uncached_tokens_per_s"))
    if not fields["lambda_mults"] or fields["n_cap"] is None:
        raise ValueError(f"{path}: lambda_selection.lambda_mults or measured.n_cap missing")
    return dict(path=os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/"), sha256=sha, fields=fields)


def derived_specs(cell: str, mults: List[float], cap: float, lam_ref: Optional[float], tokens: Optional[float],
                  variants: str = "all") -> List[Dict[str, Any]]:
    out = []
    names = (H200_VARIANTS if variants == "all" else H200_VARIANTS[:1]) if cell.startswith("h200") else [cell]
    for base in names:
        d = dict(base=os.path.join(CELLS_DIR, f"{base}.yaml").replace(os.sep, "/"), name=f"{base}_conditional",
                 description=f"REGISTRATION-CONDITIONAL rerun of the frozen spec {base} (only e2.multiples, e2.cap, tests changed)",
                 e2=dict(multiples=[float(x) for x in mults], cap=float(cap)), tests=[])
        if cell.startswith("llama"):
            if lam_ref is None or tokens is None:
                raise ValueError("Llama needs measured.lambda_ref and measured.all_miss_uncached_tokens_per_s")
            d["lambda_ref"] = dict(value=float(lam_ref), source="registration measured.lambda_ref (measured Llama E0a)")
            out.append(d)
            d2 = copy.deepcopy(d)
            d2["name"] = f"{base}_conditional_fit"
            d2["costs"] = dict(fit_speed_to_e0a=dict(tokens_per_s=float(tokens), pop=32,
                                                     source="registration measured.all_miss_uncached_tokens_per_s (measured Llama E0a)"))
            out.append(d2)
        else:
            out.append(d)
    return out


def run(cell: str, mults: List[float], cap: float, lam_ref: Optional[float] = None, tokens: Optional[float] = None,
        registration: Optional[Dict[str, Any]] = None, variants: str = "all", out_dir: Optional[str] = None,
        quick: bool = False) -> List[str]:
    out_dir = out_dir or os.path.join(OUT_DIR, "conditional")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for d in derived_specs(cell, mults, cap, lam_ref, tokens, variants):
        sp = os.path.join(out_dir, f"{d['name']}.yaml")
        with open(sp, "w") as f:
            yaml.safe_dump(d, f, sort_keys=False)
        spec = load_spec(sp)
        res = predict(spec, quick=quick)
        res["conditional"] = dict(label="conditional", rule=RULE, registration=registration,
                                  overrides=dict(e2=d["e2"], tests=d["tests"], lambda_ref=d.get("lambda_ref"), costs=d.get("costs")))
        res["pred2_provenance"] = provenance([spec["_path"]])
        p = os.path.join(out_dir, f"{d['name']}.json")
        with open(p, "w") as f:
            json.dump(clean(res), f, indent=1)
        paths.append(p)
        arms = res["e2"]["arms"]
        print(f"{d['name']}: cap {res['e2']['cap']}, " + "; ".join(
            f"{k} x: lam {a['lam']:.4f} n1 {a['n1']:.2f} n_u {a['n_u']:.2f}" + (
                f" backlog {a['burst_trapped']['backlog']:.1f} token-ratio {a['burst_trapped']['token_ratio_vs_model_e0a']:.3f} "
                f"gap/R {a['burst_trapped']['gap_over_R']:.2f} noburst-hit {a['noburst_good_state']['hit']:.3f} "
                f"capped-drain {a['capped_static']['drain_after_burst_s']:.0f} s b_crit {a['critical_burst_fresh'].get('b_fresh', float('nan')):.1f}"
                if a["in_window"] else " (outside the predicted window)") for k, a in arms.items()) + f" -> {os.path.relpath(p, ROOT)}",
              flush=True)
    return paths


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cell", required=True, choices=["h200_300k", "llama31_8b_300k"])
    ap.add_argument("--registration", default=None, help="the pushed E2 registration YAML (reads rates and cap only)")
    ap.add_argument("--mults", type=float, nargs="*", default=None, help="manual form: the registered multiples")
    ap.add_argument("--cap", type=float, default=None, help="manual form: the registered cap")
    ap.add_argument("--lambda-ref", type=float, default=None, help="manual form (Llama): the measured E0a lambda_miss")
    ap.add_argument("--tokens", type=float, default=None, help="manual form (Llama): the measured E0a all-miss tokens/s")
    ap.add_argument("--variants", default="all", choices=["all", "primary"])
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--quick", action="store_true", help="coarser grids (smoke test only; not a prediction)")
    a = ap.parse_args(argv)
    reg = None
    if a.registration:
        reg = read_registration(a.registration)
        f = reg["fields"]
        mults, cap, lam_ref, tokens = f["lambda_mults"], f["n_cap"], f["lambda_ref"], f["all_miss_uncached_tokens_per_s"]
    else:
        if a.mults is None or a.cap is None:
            ap.error("give --registration, or --mults and --cap")
        mults, cap, lam_ref, tokens = a.mults, a.cap, a.lambda_ref, a.tokens
    run(a.cell, mults, cap, lam_ref, tokens, reg, a.variants, a.out_dir, a.quick)


if __name__ == "__main__":
    main()
