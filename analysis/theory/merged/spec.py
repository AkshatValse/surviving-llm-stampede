"""Cell specification (YAML) -> the merged model, with a fitting audit.

A cell spec may name only independent inputs:
  * ``workload.config``: the agentload config whose ``workload`` section defines the sessions (configs/agentload_e2_burst.yaml);
  * ``pool_tokens``: the KV pool M;
  * ``engine.mode``: ``separate`` (SGLang: prefill iterations with priority) or ``mixed`` (vLLM: chunked prefill riding on
    decode iterations), and ``engine.hit_prefill_tokens`` (tokens a follow-up hit prefills: the new tool tokens plus the last
    decoded token, plus the mean unfilled block for a block-granular cache);
  * ``costs``: the calibrated SGLang A100 iteration-time constants (calibration/round6_server_log_fit/calibration.yaml),
    optionally multiplied by architecture ratios (``architecture_ratios``), optionally with the memory/CPU-side terms divided
    by a fixed factor (``decode_side_speedup``), and optionally divided by ONE speed factor fitted to the cell's own E0a
    all-miss token rate (``fit_speed_to_e0a``) -- the only fitted parameter any spec may carry;
  * ``lambda_ref``: the reference rate the experiments' arrival rates are multiples of (the cell's E0a turns-based
    lambda_miss, or ``model`` for a cell without data);
  * protocols: Stage C grid and window, E0b multiples and horizon, E2 multiples / burst / window / cap, and registered tests.
It never names a measured mu(n) point, an E0b outcome or an E2 outcome (``audit`` records where every value comes from).
"""
from __future__ import annotations

import copy
import math
import os
from dataclasses import replace
from typing import Any, Dict, List, Tuple

import yaml

from ..fluid_rigorous.model import Costs, Model, Workload

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CELLS_DIR = os.path.join(ROOT, "analysis", "theory", "cells")
CAL_KEYS = dict(a="iter_fixed_s", f="iter_floor_s", b="per_token_s", cd="decode_attn_s", cp="prefill_attn_s",
                norm="attn_ctx_norm", chunk="prefill_chunk_budget", max_running="max_running_seqs")


def _merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_spec(path: str) -> Dict[str, Any]:
    """Read a spec; ``base: other.yaml`` (relative to the spec) is loaded first and deep-merged under it."""
    path = os.path.abspath(path)
    with open(path) as f:
        s = yaml.safe_load(f) or {}
    if "base" in s:
        base = load_spec(os.path.join(os.path.dirname(path), s.pop("base")))
        base.pop("_path", None)              # lists (tests, grids) are replaced, not merged
        s = _merge(base, s)
    s["_path"] = os.path.relpath(path, ROOT).replace(os.sep, "/")
    return s


def _row(parameter: str, value: Any, source: str, kind: str, fitted_to: str = "", note: str = "") -> Dict[str, Any]:
    """kind: input (independent measurement or configuration), structural (engine design), protocol (experimental setup),
    derived (computed from other inputs), fitted (adjusted so the model reproduces a measured quantity)."""
    return dict(parameter=parameter, value=value, source=source, kind=kind, fitted_to=fitted_to,
                uses_measured_mu_curve=False, uses_e0b_or_e2_outcome=False, note=note)


def workload_from(spec: Dict[str, Any]) -> Tuple[Workload, List[Dict[str, Any]]]:
    w = spec.get("workload", {})
    cfg = w.get("config", "configs/agentload_e2_burst.yaml")
    with open(os.path.join(ROOT, cfg)) as f:
        ws = yaml.safe_load(f)["workload"]
    if ws.get("tool_time_dist", "exp") != "exp":
        raise ValueError("the merged model implements exponential tool times only (tool_time_dist: exp)")
    eng = spec.get("engine", {})
    delta, d = int(ws["new_prompt_tokens"]), int(ws["decode_tokens"])
    xh = eng.get("hit_prefill_tokens", "auto")
    block = int(eng.get("cache_block_tokens", 1))
    if xh == "auto":
        # a hit prefills the appended tool tokens plus the last decoded token (its KV is never written), plus on a
        # block-granular cache the mean unfilled part of the last block ((block - 1) / 2 rounded up)
        xh = delta + 1 + (int(math.ceil((block - 1) / 2.0)) if block > 1 else 0)
    wl = Workload(L0=int(ws["initial_context_tokens"]), delta=delta, d=d, mean_turns=float(ws["mean_turns"]),
                  K=int(ws["max_turns"]), zbar=float(ws["tool_time_mean_s"]), x_hit=int(xh))
    audit = [
        _row("workload (L0, delta, d, mean_turns, max_turns, zbar)",
             [wl.L0, wl.delta, wl.d, wl.mean_turns, wl.K, wl.zbar], f"{cfg} (workload section)", "protocol"),
        _row("tool-time law", "exponential", f"{cfg}: tool_time_dist", "protocol"),
        _row("hit_prefill_tokens x_h", wl.x_hit,
             "delta + 1 (last decoded token has no KV)" + (f" + mean unfilled {block}-token block" if block > 1 else ""),
             "structural",
             note="equals the SGLang Stage C fact 'cached = prompt - 551'; derivable a priori, not fitted"),
    ]
    return wl, audit


def _calibration(path: str) -> Dict[str, float]:
    with open(os.path.join(ROOT, path)) as f:
        eng = yaml.safe_load(f)["engine"]
    if eng.get("prefill_attn_ctx", "mid") != "mid":
        raise ValueError("calibration must use the 'mid' prefill-attention convention")
    return {k: float(eng[v]) for k, v in CAL_KEYS.items()}


def all_miss_tokens(wl: Workload, cost: Costs, M: float, pop: float) -> float:
    return Model(wl, cost, M).all_miss_closed(pop)["tok"]


def costs_from(spec: Dict[str, Any], wl: Workload, M: float) -> Tuple[Costs, List[Dict[str, Any]], Dict[str, Any]]:
    c = spec.get("costs", {})
    cal_path = c.get("calibration", "calibration/round6_server_log_fit/calibration.yaml")
    cal = _calibration(cal_path)
    mode = spec.get("engine", {}).get("mode", "separate")
    base = Costs(a=cal["a"], f=cal["f"], b=cal["b"], cd=cal["cd"], cp=cal["cp"], norm=cal["norm"], chunk=cal["chunk"],
                 mode=mode, max_running=cal["max_running"])
    audit = [_row("iteration costs (a, f, b, c_d, c_p, chunk, norm)", [base.a, base.f, base.b, base.cd, base.cp, base.chunk, base.norm],
                  cal_path, "input",
                  note="fitted ONLY to SGLang 0.5.22 A100 server-log iteration timing (jobs 17060165, 17062103-05); never to mu(n), "
                       "hit fractions, E0b or E2. The 300k Stage C jobs' server logs are among its data (same runs, different "
                       "observable)."),
             _row("engine iteration mode", mode, "engine design (SGLang: separate prefill iterations with priority; vLLM: mixed)",
                  "structural")]
    info: Dict[str, Any] = dict(calibration=cal_path, mode=mode)
    arch = c.get("architecture_ratios")
    if arch:
        base = replace(base, **{k: getattr(base, k) * float(v) for k, v in arch.items()})
        audit.append(_row("architecture ratios", dict(arch), c.get("architecture_source", "published model configs"), "derived",
                          note="roofline scaling of the calibrated Qwen2.5-7B costs (an assumption, no measurement)"))
        info["architecture_ratios"] = dict(arch)
    dside = c.get("decode_side_speedup")
    fit = c.get("fit_speed_to_e0a")
    if dside and not fit:
        raise ValueError("decode_side_speedup requires fit_speed_to_e0a (the compute side is fitted)")
    if fit:
        target = float(fit["tokens_per_s"])
        pop = float(fit.get("pop", 32))
        if dside:
            def split(ds: float):
                mk = lambda sp: replace(base, a=base.a / ds, f=base.f / ds, cd=base.cd / ds, b=base.b / sp, cp=base.cp / sp)
                lo, hi = 0.5, 10.0
                for _ in range(70):
                    mid = 0.5 * (lo + hi)
                    if all_miss_tokens(wl, mk(mid), M, pop) < target:
                        lo = mid
                    else:
                        hi = mid
                return mk(0.5 * (lo + hi)), 0.5 * (lo + hi)
            if isinstance(dside, dict):
                # second fitted parameter: the decode/memory-side factor that reproduces the E0a POP-64 / POP-32 token ratio
                r_t = float(dside["fit_pop64_over_pop32"])
                ratio = lambda ds: (lambda cc: all_miss_tokens(wl, cc, M, 64) / all_miss_tokens(wl, cc, M, pop))(split(ds)[0])
                lo, hi = 1.0, 6.0
                if ratio(lo) < r_t:
                    raise ValueError("POP-64 ratio not reachable with decode_side_speedup >= 1")
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if ratio(mid) > r_t:
                        lo = mid
                    else:
                        hi = mid
                ds = 0.5 * (lo + hi)
                audit.append(_row("decode/memory-side speed-up (a, f, c_d divided by)", ds, dside.get("source", ""), "fitted",
                                  fitted_to=f"E0a POP-64 / POP-32 uncached token ratio {r_t:g}",
                                  note="sensitivity variant; the model under-predicts the A100's measured POP-64 ratio by "
                                       "1.6 points, so part of this fit absorbs model bias"))
            else:
                ds = float(dside)
                audit.append(_row("decode/memory-side speed-up (a, f, c_d divided by)", ds, c.get("decode_side_source", "assumption"),
                                  "input", note="sensitivity variant"))
            cost, s = split(ds)
            info.update(decode_side_speedup=ds, compute_speed_factor_fitted=s)
            audit.append(_row("compute-side speed factor (b, c_p divided by)", s, fit.get("source", ""), "fitted",
                              fitted_to=f"E0a all-miss uncached token rate {target:g} tok/s (closed POP {pop:g}, cache off)"))
        else:
            s = target / all_miss_tokens(wl, base, M, pop)
            for _ in range(6):
                s *= target / all_miss_tokens(wl, base.scaled(s), M, pop)
            cost = base.scaled(s)
            info.update(speed_factor_fitted=s)
            audit.append(_row("uniform speed factor s (every cost divided by s)", s, fit.get("source", ""), "fitted",
                              fitted_to=f"E0a all-miss uncached token rate {target:g} tok/s (closed POP {pop:g}, cache off)",
                              note="one parameter; the model's all-miss rate is exactly proportional to s (time rescaling), so "
                                   "this fixes lambda_miss in tokens; lambda_miss in turns is then a prediction"))
        info["fit_target_tokens_per_s"] = target
    else:
        cost = base
        info.update(speed_factor_fitted=None)
        audit.append(_row("speed factor", 1.0, "none: calibrated constants used unchanged", "input"))
    return cost, audit, info


def build(spec: Dict[str, Any]) -> Tuple[Model, List[Dict[str, Any]], Dict[str, Any]]:
    wl, a1 = workload_from(spec)
    M = float(spec["pool_tokens"])
    cost, a2, info = costs_from(spec, wl, M)
    a0 = [_row("KV pool M (tokens)", M, spec.get("pool_source", ""), "input")]
    return Model(wl, cost, M), a0 + a1 + a2, info


def lambda_ref_of(spec: Dict[str, Any], m: Model) -> Tuple[float, Dict[str, Any]]:
    lr = spec.get("lambda_ref", "model")
    if lr == "model" or lr is None:
        v = m.all_miss_closed(32)["mu"]
        return v, _row("lambda_ref", v, "the model's own E0a analogue (closed POP 32, cache off): no measurement exists",
                       "derived")
    v = float(lr["value"])
    return v, _row("lambda_ref", v, lr.get("source", ""), "protocol",
                   note="the measured E0a turns-based lambda_miss; used ONLY to place the E0b/E2 arrival rates (mult x lambda_ref) "
                        "where the experiments placed them, and to express windows as multiples")
