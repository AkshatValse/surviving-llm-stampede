"""Typed, file-driven configuration for the load generator.

Configs live in ``configs/agentload_*.yaml``. The first key of every config is ``research_question``.
Unknown keys are rejected so typos in a config (or in a ``--set`` override) fail loudly.
"""
from __future__ import annotations

import copy
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml


@dataclass
class ServerCfg:
    base_url: str = "http://127.0.0.1:8000"
    model: str = "mock"
    completions_path: str = "/v1/completions"
    metrics_path: str = "/metrics"
    health_path: str = "/health"
    models_path: str = "/v1/models"
    request_timeout_s: float = 7200.0
    # One TCP connection per request (no keep-alive reuse). Idle pooled connections race with the server's own
    # keep-alive timeout (uvicorn defaults to ~5 s, about the tool time); a reused connection that the server just
    # closed fails with ServerDisconnectedError and would silently kill a whole session. Localhost connects are cheap.
    force_close_connections: bool = True
    # merged into every request body; SGLang and vLLM both accept ``ignore_eos``
    extra_body: Dict[str, Any] = field(default_factory=lambda: {"ignore_eos": True})
    # adds ``return_token_ids: true`` to the body (vLLM); harmless to leave on only if the engine accepts it
    request_token_ids: bool = False
    # dotted paths into the response JSON where output token ids may live (first present wins)
    output_ids_paths: List[str] = field(default_factory=lambda: ["choices.0.token_ids", "choices.0.output_ids",
                                                                 "choices.0.meta_info.output_ids"])


@dataclass
class WorkloadCfg:
    prompt_mode: str = "tokens"            # tokens | text
    initial_context_tokens: int = 2000     # L0
    new_prompt_tokens: int = 550           # Delta
    decode_tokens: int = 100               # d  (max_tokens, ignore_eos)
    mean_turns: float = 15.0               # Geometric(1/mean_turns) on {1,2,...}
    max_turns: int = 60
    tool_time_mean_s: float = 5.0
    tool_time_dist: str = "exp"            # exp | lognormal | const
    tool_time_cv: float = 1.5              # lognormal only
    token_id_low: int = 1000               # synthetic token ids are uniform on [low, high)
    token_id_high: int = 100000
    text_words_per_token: float = 1.0      # text mode: words emitted per requested token
    temperature: float = 0.0
    # tokens mode: where the next prompt's "previous model output" comes from.
    #   auto: server-returned ids if the response has them, else synthetic ids (logged per request)
    #   server: server ids only (a missing id list is an error);  synthetic: always synthetic ids
    #   REAL-ENGINE RUNS MUST PIN server|synthetic (slurm/common.sh requires OUTPUT_FEEDBACK for non-smoke modes and
    #   the analysis flags runs whose output_ids_source is mixed or differs across compared runs); auto is for the
    #   Stage-0 smoke run and the mock only.
    output_feedback: str = "auto"
    # text mode is not token-stable on a real engine (decoded text is re-tokenized, BPE merges can cross chunk
    # boundaries) and counts words, not tokens: it is accepted only for mock engines unless this flag is set.
    allow_text_mode: bool = False
    # per-run salt mixed into the CONTENT streams only (arrival and spec streams stay common across runs). The job
    # scripts give every run in a job a different salt, so a flush that silently failed cannot make the next run's
    # prompts hit the previous run's cache. 0 = the unsalted legacy streams.
    content_salt: int = 0


@dataclass
class BurstCfg:
    n: int = 200
    t_s: float = 5000.0
    width_s: float = 60.0


@dataclass
class ArrivalsCfg:
    kind: str = "constant"                 # constant | ramp | closed
    rate: Optional[float] = None           # sessions/s (constant)
    rate_mult: Optional[float] = None      # alternative: rate = rate_mult * lambda_ref
    lambda_ref: Optional[Any] = None       # float, or "path/to/summary.json:key" (see config.resolve_rate)
    ramp: List[List[float]] = field(default_factory=list)   # knots [[t_s, rate], ...], piecewise linear
    ramp_is_mult: bool = False             # true: ramp rates are multiples of lambda_ref (resolve_ramp)
    closed_n: int = 0                      # closed: population kept constant (replace on completion)
    burst: Optional[BurstCfg] = None


@dataclass
class RunCfg:
    duration_s: float = 60.0
    seed: int = 0
    max_inflight: int = 3000               # safety: abort (and cancel everything) above this many in-flight requests
    max_errors: int = 100                  # safety: abort after this many failed requests
    flush_every_s: float = 5.0
    preflight_wait_s: float = 60.0         # wait this long for the health endpoint before giving up


@dataclass
class MetricsCfg:
    enabled: bool = True
    interval_s: float = 5.0
    prefixes: List[str] = field(default_factory=lambda: ["vllm:", "sglang:"])
    drop_suffixes: List[str] = field(default_factory=lambda: ["_bucket"])
    timeout_s: float = 10.0


@dataclass
class CanaryCfg:
    """Start-state check around a cache flush (``python -m agentload canary``; driven by slurm/common.sh).
    prime: wait until the engine is idle, send a fixed canary prompt twice; the 2nd must report cached_tokens >=
    resident_min_frac * tokens (the cache works and holds the canary). After the flush, check: idle again and the
    same canary must report cached_tokens <= max_cached_after_flush (one vLLM block is 16 tokens). The metric names
    are CANDIDATES from memory (first present wins) and are not verified for v0.5.22 / v0.32.0: a category with no
    metric present is reported as unknown, not as passed."""
    tokens: int = 1024
    resident_min_frac: float = 0.5
    max_cached_after_flush: int = 15
    idle_wait_s: float = 120.0
    idle_poll_s: float = 2.0
    kv_in_use_max: float = 0.02
    waiting_metrics: List[str] = field(default_factory=lambda: ["vllm:num_requests_waiting", "sglang:num_queue_reqs",
                                                                "sglang:num_waiting_reqs"])
    running_metrics: List[str] = field(default_factory=lambda: ["vllm:num_requests_running", "sglang:num_running_reqs"])
    kv_in_use_metrics: List[str] = field(default_factory=lambda: ["vllm:kv_cache_usage_perc",
                                                                  "vllm:gpu_cache_usage_perc", "sglang:token_usage"])


@dataclass
class MetaCfg:
    hardware: str = "Apple M3 Max CPU (simulation)"
    engine_label: str = "mock"
    notes: str = ""
    # set by the job script from the post-flush canary check (slurm/common.sh); recorded verbatim in meta.json
    start_state_verified: Optional[bool] = None
    start_state_detail: str = ""


@dataclass
class OutputCfg:
    root: str = "results"
    name: str = "agentload"


@dataclass
class Config:
    research_question: str = ""
    server: ServerCfg = field(default_factory=ServerCfg)
    workload: WorkloadCfg = field(default_factory=WorkloadCfg)
    arrivals: ArrivalsCfg = field(default_factory=ArrivalsCfg)
    run: RunCfg = field(default_factory=RunCfg)
    metrics: MetricsCfg = field(default_factory=MetricsCfg)
    canary: CanaryCfg = field(default_factory=CanaryCfg)
    meta: MetaCfg = field(default_factory=MetaCfg)
    output: OutputCfg = field(default_factory=OutputCfg)


_NESTED = {"server": ServerCfg, "workload": WorkloadCfg, "arrivals": ArrivalsCfg, "run": RunCfg,
           "metrics": MetricsCfg, "canary": CanaryCfg, "meta": MetaCfg, "output": OutputCfg}


def _build(cls: Any, d: Dict[str, Any], where: str) -> Any:
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(d) - names
    if unknown:
        raise KeyError(f"unknown config key(s) in {where}: {sorted(unknown)}")
    kw = dict(d)
    if cls is ArrivalsCfg and kw.get("burst") is not None:
        kw["burst"] = _build(BurstCfg, kw["burst"], f"{where}.burst")
    return cls(**kw)


def config_from_dict(d: Dict[str, Any]) -> Config:
    """Build a validated :class:`Config` from a plain dict (unknown keys raise ``KeyError``)."""
    allowed = {"research_question", "assumptions_note", *(_NESTED)}
    unknown = set(d) - allowed
    if unknown:
        raise KeyError(f"unknown top-level config key(s): {sorted(unknown)}")
    kw: Dict[str, Any] = {"research_question": str(d.get("research_question", ""))}
    for k, cls in _NESTED.items():
        kw[k] = _build(cls, d.get(k) or {}, k)
    cfg = Config(**kw)
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    w, a, r = cfg.workload, cfg.arrivals, cfg.run
    if w.prompt_mode not in ("tokens", "text"):
        raise ValueError(f"workload.prompt_mode must be tokens|text, got {w.prompt_mode!r}")
    if w.output_feedback not in ("auto", "server", "synthetic"):
        raise ValueError(f"workload.output_feedback must be auto|server|synthetic, got {w.output_feedback!r}")
    if w.tool_time_dist not in ("exp", "lognormal", "const"):
        raise ValueError(f"workload.tool_time_dist must be exp|lognormal|const, got {w.tool_time_dist!r}")
    if w.mean_turns < 1 or w.max_turns < 1:
        raise ValueError("mean_turns and max_turns must be >= 1")
    if w.token_id_high <= w.token_id_low:
        raise ValueError("token_id_high must exceed token_id_low")
    if w.prompt_mode == "text" and not w.allow_text_mode and not cfg.meta.engine_label.lower().startswith("mock"):
        raise ValueError("workload.prompt_mode=text is only allowed for mock engines (meta.engine_label starting with "
                         "'mock') unless workload.allow_text_mode=true: text mode is not token-stable on real engines")
    if not isinstance(w.content_salt, int) or isinstance(w.content_salt, bool) or w.content_salt < 0:
        raise ValueError("workload.content_salt must be a non-negative integer")
    if a.kind not in ("constant", "ramp", "closed"):
        raise ValueError(f"arrivals.kind must be constant|ramp|closed, got {a.kind!r}")
    if a.kind == "closed" and a.closed_n < 1:
        raise ValueError("arrivals.closed_n must be >= 1 for kind=closed")
    if a.kind == "ramp" and len(a.ramp) < 2:
        raise ValueError("arrivals.ramp needs >= 2 knots [t_s, rate]")
    if r.duration_s <= 0:
        raise ValueError("run.duration_s must be positive")


def load_config(path: str | Path, overrides: Optional[Sequence[str]] = None) -> Tuple[Config, Dict[str, Any]]:
    """Load a YAML config, apply ``key.sub=value`` overrides (value parsed as YAML), validate.
    Returns the typed config and the effective raw dict (after overrides)."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    raw = apply_overrides(raw, overrides)
    return config_from_dict(raw), raw


def apply_overrides(raw: Dict[str, Any], overrides: Optional[Sequence[str]]) -> Dict[str, Any]:
    out = copy.deepcopy(raw)
    for item in overrides or []:
        if "=" not in item:
            raise ValueError(f"override must look like a.b=value, got {item!r}")
        key, val = item.split("=", 1)
        node = out
        parts = key.split(".")
        for p in parts[:-1]:
            if node.get(p) is None:
                node[p] = {}
            node = node[p]
        node[parts[-1]] = yaml.safe_load(val)
    return out


def resolve_lambda_ref(ref: Any, base_dir: Optional[Path] = None) -> float:
    """``ref`` is a number, or ``"path/to/file.json:key"`` whose JSON has a top-level numeric ``key``."""
    if isinstance(ref, (int, float)):
        return float(ref)
    if isinstance(ref, str) and ":" in ref:
        path_s, key = ref.rsplit(":", 1)
        p = Path(path_s)
        if not p.is_absolute() and base_dir is not None:
            p = base_dir / p
        if not p.is_file():
            raise FileNotFoundError(f"arrivals.lambda_ref file not found: {p} (is it still a placeholder? "
                                    f"set it with --set arrivals.lambda_ref=<path>/calibration.json:<key>)")
        return float(json.loads(p.read_text())[key])
    raise ValueError(f"cannot resolve lambda_ref {ref!r}")


def resolve_rate(a: ArrivalsCfg, base_dir: Optional[Path] = None) -> Optional[float]:
    """Constant arrival rate (sessions/s): ``rate`` if given, else ``rate_mult * lambda_ref``."""
    if a.rate is not None:
        if a.rate_mult is not None:
            raise ValueError("set either arrivals.rate or arrivals.rate_mult/lambda_ref, not both")
        return float(a.rate)
    if a.rate_mult is not None:
        if a.lambda_ref is None:
            raise ValueError("arrivals.rate_mult needs arrivals.lambda_ref")
        return float(a.rate_mult) * resolve_lambda_ref(a.lambda_ref, base_dir)
    return None


def resolve_ramp(a: ArrivalsCfg, base_dir: Optional[Path] = None) -> List[Tuple[float, float]]:
    """Ramp knots as ``(t_s, sessions/s)``; if ``ramp_is_mult`` the rates are multiplied by ``lambda_ref``."""
    scale = 1.0
    if a.ramp_is_mult:
        if a.lambda_ref is None:
            raise ValueError("arrivals.ramp_is_mult needs arrivals.lambda_ref")
        scale = resolve_lambda_ref(a.lambda_ref, base_dir)
    knots = [(float(t), float(r) * scale) for t, r in a.ramp]
    if any(knots[i][0] >= knots[i + 1][0] for i in range(len(knots) - 1)):
        raise ValueError("arrivals.ramp knot times must be strictly increasing")
    return knots
