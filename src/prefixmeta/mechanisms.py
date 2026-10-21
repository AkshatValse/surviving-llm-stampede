"""Admission / eviction modifiers layered on top of an ordering policy (round 2).

An *ordering* policy (``policies.py``) decides the order in which waiting requests are considered. The
*mechanisms* here change what the engine may evict and who may enter the system:

``protect_queued``  (PEEK-like). KV of a session that currently has a QUEUED request is protected.
    * ``"pin"``  : hard protection. Protected KV is never evicted; an admission that does not fit because of it
      WAITS (non-work-conserving). Deadlock breaker: if the engine is idle and the blocked head still does not
      fit, protection is released in latest-program-arrival order until it fits.
    * ``"rank"`` : ranking only (the PEEK paper: "protection is a ranking, not a pin"). Queued KV is evicted
      after every unprotected idle block, but it can still be evicted; admission never waits for it.
``ttl_s``  (TTL pin, "blocking pin"). The KV of a session that just finished a NON-final turn is pinned until
    ``finish + ttl_s``. Pinned KV is never evicted (admission waits if it does not fit). At expiry the pin is freed
    unless the session's next request is already queued (then it stays until that request is admitted).
    ``ttl_unpin`` says when a pin is released BEFORE its expiry:
    * ``"idle"``      (default, the round-2 pre-registered behaviour): only the idle-engine deadlock breaker releases
      pins, so pins THROTTLE the admission of misses (a non-work-conserving admission control).
    * ``"eager"``     (Continuum-faithful reading of the scout spec, Sec. 5.2, NOT checked against the paper or its
      code): whenever the request being considered in a scheduling pass does not fit because of pinned KV, pins of
      other sessions are released latest-program-arrival first until it fits or no pin is left.
    * ``"eager_fit"`` (sensitivity): as ``eager`` but pins are released only if that makes the request fit.
``session_cap``  (CAP / LB-CAP / AIMD-CAP). Sessions beyond the cap wait in a gate and are not in the system.
    A static integer, ``lb`` (= N_lb = floor(M / E_lb), E_lb the length-biased mean context), ``{lb_mult: x}``
    (= floor(x N_lb)) or an AIMD controller (``{aimd: {...}}``) that is stepped every ``interval_s`` seconds.

Nothing here reads simulation outcomes: N_lb is a function of (M, workload) only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .workload import WorkloadParams, length_biased_session_cap


@dataclass(frozen=True)
class AimdParams:
    """Additive-increase / multiplicative-decrease controller of the session cap.

    rule ``"hit"``   (task fallback spec): every ``interval_s``: window hit rate < ``hit_threshold`` ->
                     cap = max(min_cap, floor(decrease * cap)), else cap += increase.
    rule ``"concur"`` (CONCUR Eq. 1): usage U < ``u_low`` -> cap += increase; U > ``u_high`` and hit rate H <
                     ``h_thresh`` -> cap = max(min_cap, floor(decrease * cap)); otherwise hold.
    A window with no admissions has an undefined (NaN) hit rate: it never triggers a decrease.
    """
    rule: str = "hit"
    interval_s: float = 10.0
    start: Any = "lb"                 # "lb" (= N_lb) or an int
    min_cap: int = 4
    max_cap: Optional[int] = None
    hit_threshold: float = 0.7
    increase: int = 1
    decrease: float = 0.7
    u_low: float = 0.2
    u_high: float = 0.5
    h_thresh: float = 0.2

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AimdParams":
        p = cls(**d)
        if p.rule not in ("hit", "concur"):
            raise ValueError(f"unknown AIMD rule {p.rule!r}")
        if p.interval_s <= 0 or p.min_cap < 1 or not (0.0 < p.decrease < 1.0) or p.increase < 1:
            raise ValueError("bad AIMD parameters")
        return p


def aimd_step(cap: int, hit_rate: float, usage: float, p: AimdParams) -> int:
    """One controller step (pure). ``hit_rate`` may be NaN (no admissions in the window)."""
    if p.rule == "hit":
        down = hit_rate < p.hit_threshold                   # NaN -> False -> increase
        up = not down
    else:
        down = usage > p.u_high and hit_rate < p.h_thresh
        up = usage < p.u_low
    if down:
        new = max(p.min_cap, int(math.floor(p.decrease * cap)))
    elif up:
        new = cap + p.increase
    else:
        new = cap
    if p.max_cap is not None and new > p.max_cap:
        new = p.max_cap
    return new


TTL_UNPIN_MODES = ("idle", "eager", "eager_fit")


@dataclass(frozen=True)
class Mechanisms:
    protect_queued: Optional[str] = None      # None | "pin" | "rank"
    ttl_s: Optional[float] = None
    aimd: Optional[AimdParams] = None
    ttl_unpin: str = "idle"                   # one of TTL_UNPIN_MODES (only meaningful with ttl_s)

    @property
    def any_protection(self) -> bool:
        return self.protect_queued is not None or self.ttl_s is not None


def resolve_session_cap(value: Any, memory_tokens: float, wl: WorkloadParams
                        ) -> Tuple[Optional[int], Optional[AimdParams]]:
    """Resolve a policy's ``session_cap`` entry to (initial integer cap or None, AIMD params or None).

    Accepted: None | int | "lb" / "auto_lb" | {"lb_mult": x} | {"aimd": {...}}. ("auto" is handled by the caller,
    it is the round-1 spec-literal cap.)"""
    if value is None:
        return None, None
    if isinstance(value, bool):
        raise ValueError("session_cap must not be a bool")
    if isinstance(value, int):
        return int(value), None
    if value in ("lb", "auto_lb"):
        n = length_biased_session_cap(memory_tokens, wl)
        return (int(n) if n is not None else None), None
    if isinstance(value, dict):
        if "lb_mult" in value:
            n = length_biased_session_cap(memory_tokens, wl)
            if n is None:
                return None, None
            return int(math.floor(float(value["lb_mult"]) * n)), None
        if "aimd" in value:
            ap = AimdParams.from_dict(value["aimd"] or {})
            if ap.start in ("lb", "auto_lb"):
                n = length_biased_session_cap(memory_tokens, wl)
                start = int(n) if n is not None else None
            else:
                start = int(ap.start)
            if start is None:
                return None, None
            start = max(ap.min_cap, start)
            return start, ap
    raise ValueError(f"unsupported session_cap spec {value!r}")


def make_mechanisms(spec: Dict[str, Any], aimd: Optional[AimdParams]) -> Mechanisms:
    pq = spec.get("protect_queued")
    if pq is not None and pq not in ("pin", "rank"):
        raise ValueError(f"protect_queued must be 'pin' or 'rank', got {pq!r}")
    ttl = spec.get("ttl_pin_s")
    if ttl is not None:
        ttl = float(ttl)
        if ttl <= 0:
            raise ValueError("ttl_pin_s must be > 0")
    unpin = spec.get("ttl_unpin", "idle")
    if unpin not in TTL_UNPIN_MODES:
        raise ValueError(f"ttl_unpin must be one of {TTL_UNPIN_MODES}, got {unpin!r}")
    if unpin != "idle" and ttl is None:
        raise ValueError("ttl_unpin requires ttl_pin_s")
    return Mechanisms(protect_queued=pq, ttl_s=ttl, aimd=aimd, ttl_unpin=unpin)
