"""Start-state verification around a prefix-cache flush (engine-agnostic).

``flush_cache`` in slurm/common.sh only sees an HTTP status, and engines may answer 200 without having emptied the
cache (e.g. refusing because blocks are still in use). This module measures the outcome instead:

* ``prime``  wait until the engine is idle (waiting = running = 0, KV in use ~ 0); send a fixed canary prompt twice;
             the second request must report ``cached_tokens`` >= ``resident_min_frac * tokens``.
* ``check``  (after the flush) wait until idle; send the same canary once; it must report ``cached_tokens`` <=
             ``max_cached_after_flush``.
* ``idle``   only the idle wait (used when the engine runs with prefix caching disabled).

Exit codes of the CLI: 0 verified, 1 failed, 3 unverifiable (the engine does not report cached_tokens, or an
expected metric is missing in a way that prevents a verdict). A category of idle gauge for which no candidate metric
exists is recorded as ``unknown`` and does not fail the check; the cached_tokens canary is the primary evidence.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np

from .config import Config
from .parse import extract_usage, parse_prometheus
from .workload import make_rng

S_CANARY = 6                       # stream id (workload.py uses 0..5)
EXIT_OK, EXIT_FAIL, EXIT_UNVERIFIABLE = 0, 1, 3


def canary_ids(cfg: Config, salt: int) -> List[int]:
    """Fixed pseudo-random token ids of the canary prompt for ``salt`` (distinct from every session stream)."""
    rng = make_rng(int(salt), S_CANARY)
    w = cfg.workload
    return [int(x) for x in rng.integers(w.token_id_low, w.token_id_high, size=cfg.canary.tokens, dtype=np.int64)]


def _first_present(samples: List[Tuple[str, str, float]], names: List[str]) -> Tuple[Optional[str], Optional[float]]:
    """(name, value summed over label sets) of the first candidate name present in the scrape."""
    for n in names:
        vals = [v for (nm, _, v) in samples if nm == n]
        if vals:
            return n, float(sum(vals))
    return None, None


def idle_state(metrics_text: str, cfg: Config) -> Dict[str, Any]:
    """Idle verdict from one /metrics scrape. ``idle`` is True/False when every available category agrees, and the
    per-category entries say ``unknown`` (name None) when no candidate metric exists."""
    c = cfg.canary
    samples = parse_prometheus(metrics_text, (), ())
    out: Dict[str, Any] = {}
    bad = False
    for key, names, limit in (("waiting", c.waiting_metrics, 0.0), ("running", c.running_metrics, 0.0),
                              ("kv_in_use", c.kv_in_use_metrics, c.kv_in_use_max)):
        name, val = _first_present(samples, names)
        out[key] = {"metric": name, "value": val}
        if name is not None and val is not None and val > limit:
            bad = True
    out["idle"] = not bad
    out["n_categories_known"] = sum(1 for k in ("waiting", "running", "kv_in_use") if out[k]["metric"] is not None)
    return out


async def wait_idle(http: aiohttp.ClientSession, cfg: Config) -> Dict[str, Any]:
    srv, c = cfg.server, cfg.canary
    deadline = time.monotonic() + c.idle_wait_s
    last: Dict[str, Any] = {"idle": False, "error": "no scrape"}
    t0 = time.monotonic()
    while True:
        try:
            async with http.get(srv.base_url.rstrip("/") + srv.metrics_path,
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    last = idle_state(await r.text(), cfg)
                else:
                    last = {"idle": False, "error": f"metrics HTTP {r.status}"}
        except Exception as e:
            last = {"idle": False, "error": f"{type(e).__name__}: {e}"}
        if last.get("idle") or time.monotonic() > deadline:
            last["waited_s"] = round(time.monotonic() - t0, 2)
            return last
        await asyncio.sleep(c.idle_poll_s)


async def _send_canary(http: aiohttp.ClientSession, cfg: Config, salt: int) -> Dict[str, Any]:
    srv = cfg.server
    body: Dict[str, Any] = {"model": srv.model, "prompt": canary_ids(cfg, salt), "max_tokens": 1,
                            "temperature": 0.0, "stream": False, **srv.extra_body}
    async with http.post(srv.base_url.rstrip("/") + srv.completions_path, json=body,
                         timeout=aiohttp.ClientTimeout(total=300)) as r:
        txt = await r.text()
        if r.status != 200:
            return {"http": r.status, "error": txt[:200]}
        u = extract_usage(json.loads(txt))
        return {"http": 200, "prompt_tokens": u["prompt_tokens"], "cached_tokens": u["cached_tokens"],
                "cached_source": u["cached_source"]}


async def run_canary(cfg: Config, phase: str, salt: int, cache_expected: bool,
                     prime: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
    """Run one phase; returns (exit code, result dict). See the module docstring for the pass criteria."""
    c = cfg.canary
    res: Dict[str, Any] = {"phase": phase, "salt": salt, "cache_expected": cache_expected, "tokens": c.tokens}
    conn = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=conn) as http:
        res["idle"] = await wait_idle(http, cfg)
        if not res["idle"].get("idle"):
            res.update(ok=False, reason="engine did not become idle within canary.idle_wait_s")
            return EXIT_FAIL, res
        if phase == "idle" or not cache_expected:
            res.update(ok=True, reason="idle verified (prefix caching not expected: no canary hit test)")
            return EXIT_OK, res
        if phase == "prime":
            first = await _send_canary(http, cfg, salt)
            second = await _send_canary(http, cfg, salt)
            res.update(first=first, second=second)
            if first.get("http") != 200 or second.get("http") != 200:
                res.update(ok=False, reason="canary request failed")
                return EXIT_FAIL, res
            cached = second.get("cached_tokens")
            if cached is None:
                res.update(ok=False, reason="engine reports no cached_tokens: flush cannot be verified")
                return EXIT_UNVERIFIABLE, res
            need = c.resident_min_frac * c.tokens
            if cached < need:
                res.update(ok=False, reason=f"2nd identical canary request cached {cached} < {need:.0f} tokens: "
                                            "cache not working, so a post-flush miss would prove nothing")
                return EXIT_UNVERIFIABLE, res
            res.update(ok=True, reason=f"canary resident (2nd request cached {cached} of {c.tokens})")
            return EXIT_OK, res
        if phase == "check":
            one = await _send_canary(http, cfg, salt)
            res.update(after_flush=one)
            if one.get("http") != 200:
                res.update(ok=False, reason="canary request failed")
                return EXIT_FAIL, res
            cached = one.get("cached_tokens")
            if cached is None:
                seen = bool(prime and (prime.get("second") or {}).get("cached_source") not in (None, "none"))
                if not seen:
                    res.update(ok=False, reason="engine reports no cached_tokens: flush cannot be verified")
                    return EXIT_UNVERIFIABLE, res
                cached = 0                  # the field exists (the prime phase saw it), absent here means 0
                res["cached_missing_treated_as_zero"] = True
            if cached > c.max_cached_after_flush:
                res.update(ok=False, reason=f"canary still cached after flush: {cached} > {c.max_cached_after_flush} "
                                            "tokens (flush did not empty the cache)")
                return EXIT_FAIL, res
            res.update(ok=True, reason=f"canary not cached after flush ({cached} tokens)")
            return EXIT_OK, res
    raise ValueError(f"unknown canary phase {phase!r}")
