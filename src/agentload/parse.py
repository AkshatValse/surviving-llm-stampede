"""Parsing of OpenAI-compatible completion responses (vLLM / SGLang variants) and Prometheus text."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------- completion responses
def get_path(obj: Any, dotted: str) -> Any:
    """``get_path(d, "choices.0.meta_info.cached_tokens")``; None if any step is missing."""
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


# Where engines put the number of prompt tokens served from the prefix cache.
#   vLLM:   usage.prompt_tokens_details.cached_tokens  (only if the server flag enabling prompt-token details is on)
#   SGLang: usage.prompt_tokens_details.cached_tokens  (only if its cache-report flag is on), or
#           meta_info.cached_tokens (native /generate; may be nested under choices.0 for the OpenAI route)
CACHED_PATHS: Tuple[Tuple[str, str], ...] = (
    ("usage.prompt_tokens_details.cached_tokens", "usage.prompt_tokens_details"),
    ("choices.0.meta_info.cached_tokens", "choices.0.meta_info"),
    ("meta_info.cached_tokens", "meta_info"),
    ("usage.cached_tokens", "usage"),
)


def _as_int(x: Any) -> Optional[int]:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)) and x == x:
        return int(x)
    return None


def extract_cached_tokens(data: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """(cached_tokens, source) where source names the path used, or ``(None, "none")`` if the server reports none.
    A reported 0 is returned as 0 (distinct from absent)."""
    for path, label in CACHED_PATHS:
        v = _as_int(get_path(data, path))
        if v is not None:
            return v, label
    return None, "none"


def extract_usage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Server-reported prompt/completion tokens, cached tokens (+ source) and a compact raw-usage JSON string
    (the ``usage`` object plus the scalar entries of any ``meta_info``)."""
    usage = data.get("usage") if isinstance(data, dict) else None
    cached, src = extract_cached_tokens(data)
    raw: Dict[str, Any] = {"usage": usage}
    for mp in ("choices.0.meta_info", "meta_info"):
        mi = get_path(data, mp)
        if isinstance(mi, dict):
            raw[mp] = {k: v for k, v in mi.items() if isinstance(v, (int, float, str, bool)) or v is None}
    return {
        "prompt_tokens": _as_int(get_path(data, "usage.prompt_tokens")),
        "completion_tokens": _as_int(get_path(data, "usage.completion_tokens")),
        "cached_tokens": cached,
        "cached_source": src,
        "raw_usage_json": json.dumps(raw, separators=(",", ":"), sort_keys=True),
    }


def extract_output_text(data: Dict[str, Any]) -> Optional[str]:
    t = get_path(data, "choices.0.text")
    return t if isinstance(t, str) else None


def extract_output_ids(data: Dict[str, Any], paths: Sequence[str]) -> Optional[List[int]]:
    for p in paths:
        v = get_path(data, p)
        if isinstance(v, list) and v and all(isinstance(i, int) and not isinstance(i, bool) for i in v):
            return list(v)
    return None


# ---------------------------------------------------------------- Prometheus text exposition
_SAMPLE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*)(\{.*\})?\s+(\S+)(?:\s+\S+)?\s*$")


def parse_prometheus(text: str, prefixes: Sequence[str] = (), drop_suffixes: Sequence[str] = ()
                     ) -> List[Tuple[str, str, float]]:
    """Parse Prometheus text into ``(name, labels, value)``. Keeps only names starting with one of ``prefixes``
    (all names if empty) and drops names ending with any of ``drop_suffixes`` (e.g. histogram ``_bucket``).
    ``labels`` is the raw ``{...}`` string (empty if none). Comment lines and unparsable lines are skipped."""
    out: List[Tuple[str, str, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        if not m:
            continue
        name, labels, val = m.group(1), m.group(2) or "", m.group(3)
        if prefixes and not any(name.startswith(p) for p in prefixes):
            continue
        if any(name.endswith(s) for s in drop_suffixes):
            continue
        try:
            v = float(val)
        except ValueError:
            continue
        out.append((name, labels, v))
    return out
