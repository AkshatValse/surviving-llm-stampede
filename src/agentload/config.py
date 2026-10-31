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
    # Optional tool-latency spike (plan N3, TOOLSLOW): every tool call whose sleep STARTS (the agent's previous response
    # completed) at t in [t_s, t_s + width_s) sleeps its drawn tool time plus add_s; tool calls starting outside the window
    # are unchanged. Logged per call in tool_calls.csv (only when set). null (the default) = no slowdown: the client, plan.csv
    # and every output file are then exactly those of the client before the option existed.
    tool_slowdown: Optional["ToolSlowdownCfg"] = None


@dataclass
class ToolSlowdownCfg:
    t_s: float = 0.0                       # window start (seconds since run start)
    width_s: float = 0.0                   # window length: a tool call starting in [t_s, t_s + width_s) is slowed
    add_s: float = 0.0                     # seconds added to that tool call's drawn tool time


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
    # ANALYSIS REFERENCE ONLY (the generator never uses it for load): the all-miss uncached prefill tokens/s of E0a that trap
    # criterion (a) compares the post-burst prefill-token rate with. float, or "path/to/calibration.json:key"
    # (``all_miss_uncached_tokens_per_s``); resolved at run start and recorded in meta.json. A placeholder fails loudly.
    uncached_tokens_ref: Optional[Any] = None
    ramp: List[List[float]] = field(default_factory=list)   # knots [[t_s, rate], ...], piecewise linear
    ramp_is_mult: bool = False             # true: ramp rates are multiples of lambda_ref (resolve_ramp)
    closed_n: int = 0                      # closed: population kept constant (replace on completion)
    burst: Optional[BurstCfg] = None
    # ANALYSIS REFERENCE ONLY (the generator ignores it): the burst time t_b of the paired BURST arm. The NOBURST arm has
    # ``burst: null`` but is evaluated over the same post-burst window, so every arm's config records the same t_b.
    analysis_t_burst_s: Optional[float] = None


@dataclass
class GateCfg:
    """Client-side session cap (the CAPPED arm). Sessions still ARRIVE on the open-loop schedule; the gate sits between
    arrival and the first request: at most ``n_cap`` sessions are admitted (= active: admitted and not yet ended,
    including their tool-time sleeps); the rest wait in a FIFO queue and their wait is logged. ``n_cap`` is an int, or
    ``"path/to/mu_curve.json:n_cap"`` (the Stage-C result, argmax of the closed-population curve mu(n)), resolved like
    ``arrivals.lambda_ref``. null = no gate.

    ``mode`` selects when the cap acts:

    * ``static`` (default; the CAPPED arm): the cap holds from t = 0. The rescue-only keys below must stay unset.
    * ``rescue`` (the RESCUE arm): the run is uncapped until ``t_on_s`` (so the client is byte-identical to the BURST arm
      before it), then the cap is set to ``n_cap``. The cap cannot evict, so it drops below the active count by
      attrition, and with ``pause_at_turns`` a session whose tool call ends while active > cap gives up its slot and
      waits in a resume deque that is served before new arrivals (FIFO within each). From ``t_on_s + min_on_s`` the
      gate checks every ``release_check_s`` seconds (ticks at ``t_on_s + k * release_check_s``) and is released
      (cap removed, both queues drained in order) at the first tick at which the arrival queue and the resume deque
      have both been empty continuously for ``release_hold_s``. There is no forced release. Requires ``n_cap``,
      ``t_on_s`` and ``pause_at_turns``."""
    n_cap: Optional[Any] = None
    mode: str = "static"                   # static | rescue
    t_on_s: Optional[float] = None         # rescue: when the cap is engaged (seconds since run start)
    pause_at_turns: Optional[bool] = None  # rescue: pause over-cap sessions at their next tool-call boundary
    release_hold_s: Optional[float] = None # rescue: both queues empty this long -> release (default 300)
    min_on_s: Optional[float] = None       # rescue: no release before t_on_s + min_on_s (default 600)
    release_check_s: Optional[float] = None  # rescue: release-check tick (default 10)


GATE_RESCUE_DEFAULTS = {"release_hold_s": 300.0, "min_on_s": 600.0, "release_check_s": 10.0}
_GATE_RESCUE_KEYS = ("t_on_s", "pause_at_turns", "release_hold_s", "min_on_s", "release_check_s")


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
    # which arm of a paired E2 set this run is: burst | noburst | capped | rescue | "" (not part of a paired set). Recorded
    # in meta.json; the analysis cross-checks it against what the config structurally implies (burst / gate present /
    # gate.mode). arm rescue requires gate.mode rescue and vice versa (config.validate).
    arm: str = ""
    # set by the job script for MODE=burst from the committed pre-registration it validated (slurm/common.sh); recorded in
    # meta.json so the analysis can check that the runs were launched under exactly the file that is being applied
    prereg_sha256: str = ""
    prereg_file: str = ""


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
    gate: GateCfg = field(default_factory=GateCfg)
    run: RunCfg = field(default_factory=RunCfg)
    metrics: MetricsCfg = field(default_factory=MetricsCfg)
    canary: CanaryCfg = field(default_factory=CanaryCfg)
    meta: MetaCfg = field(default_factory=MetaCfg)
    output: OutputCfg = field(default_factory=OutputCfg)


_NESTED = {"server": ServerCfg, "workload": WorkloadCfg, "arrivals": ArrivalsCfg, "gate": GateCfg, "run": RunCfg,
           "metrics": MetricsCfg, "canary": CanaryCfg, "meta": MetaCfg, "output": OutputCfg}


def _build(cls: Any, d: Dict[str, Any], where: str) -> Any:
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(d) - names
    if unknown:
        raise KeyError(f"unknown config key(s) in {where}: {sorted(unknown)}")
    kw = dict(d)
    if cls is ArrivalsCfg and kw.get("burst") is not None:
        kw["burst"] = _build(BurstCfg, kw["burst"], f"{where}.burst")
    if cls is WorkloadCfg and kw.get("tool_slowdown") is not None:
        ts = kw["tool_slowdown"]
        if not isinstance(ts, dict):
            raise ValueError(f"{where}.tool_slowdown must be a mapping {{t_s, width_s, add_s}} or null, got {ts!r}")
        missing = sorted({"t_s", "width_s", "add_s"} - set(ts))
        if missing:
            raise KeyError(f"{where}.tool_slowdown lacks {missing} (all of t_s, width_s, add_s are required)")
        kw["tool_slowdown"] = _build(ToolSlowdownCfg, ts, f"{where}.tool_slowdown")
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


ARMS = {"", "burst", "noburst", "capped", "rescue"}


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
    validate_tool_slowdown(cfg)
    if a.kind not in ("constant", "ramp", "closed"):
        raise ValueError(f"arrivals.kind must be constant|ramp|closed, got {a.kind!r}")
    if a.kind == "closed" and a.closed_n < 1:
        raise ValueError("arrivals.closed_n must be >= 1 for kind=closed")
    if a.kind == "ramp" and len(a.ramp) < 2:
        raise ValueError("arrivals.ramp needs >= 2 knots [t_s, rate]")
    if r.duration_s <= 0:
        raise ValueError("run.duration_s must be positive")
    if cfg.meta.arm not in ARMS:
        raise ValueError(f"meta.arm must be one of {sorted(ARMS)}, got {cfg.meta.arm!r}")
    if cfg.gate.n_cap is not None:
        if a.kind == "closed":
            raise ValueError("gate.n_cap is for open-loop arrivals; a closed population is its own cap (arrivals.closed_n)")
        n = cfg.gate.n_cap
        if isinstance(n, bool) or not (isinstance(n, int) or (isinstance(n, str) and ":" in n)):
            raise ValueError(f"gate.n_cap must be an int or 'path/to/mu_curve.json:key', got {n!r}")
        if isinstance(n, int) and n < 1:
            raise ValueError("gate.n_cap must be >= 1")
    validate_gate(cfg)
    if a.analysis_t_burst_s is not None and a.burst is not None and abs(a.analysis_t_burst_s - a.burst.t_s) > 1e-9:
        raise ValueError("arrivals.analysis_t_burst_s must equal arrivals.burst.t_s when a burst is configured")


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


def validate_tool_slowdown(cfg: Config) -> None:
    """``workload.tool_slowdown`` (plan N3): finite numbers with t_s >= 0, width_s > 0, add_s > 0, the window inside the run,
    and open-loop arrivals (a closed population is a calibration run, never slowed)."""
    ts = cfg.workload.tool_slowdown
    if ts is None:
        return
    for k in ("t_s", "width_s", "add_s"):
        if not _num(getattr(ts, k)):
            raise ValueError(f"workload.tool_slowdown.{k} must be a finite number, got {getattr(ts, k)!r}")
    if ts.t_s < 0:
        raise ValueError(f"workload.tool_slowdown.t_s must be >= 0, got {ts.t_s!r}")
    if ts.width_s <= 0:
        raise ValueError(f"workload.tool_slowdown.width_s must be > 0, got {ts.width_s!r}")
    if ts.add_s <= 0:
        raise ValueError(f"workload.tool_slowdown.add_s must be > 0 (omit the block for no slowdown), got {ts.add_s!r}")
    if ts.t_s + ts.width_s > cfg.run.duration_s:
        raise ValueError(f"workload.tool_slowdown window [{ts.t_s}, {ts.t_s + ts.width_s}) ends after run.duration_s "
                         f"{cfg.run.duration_s}")
    if cfg.arrivals.kind == "closed":
        raise ValueError("workload.tool_slowdown is for open-loop runs (arrivals.kind constant|ramp), not a closed population")


def tool_slowdown_add_s(ts: Optional[ToolSlowdownCfg], t_start: float) -> float:
    """Seconds added to a tool call whose sleep starts at ``t_start`` (0.0 outside [t_s, t_s + width_s) or without the option)."""
    if ts is None:
        return 0.0
    return float(ts.add_s) if ts.t_s <= t_start < ts.t_s + ts.width_s else 0.0


def validate_gate(cfg: Config) -> None:
    """``gate.mode`` and the rescue keys (see :class:`GateCfg`). A static gate is exactly the CAPPED gate: the rescue
    keys must be unset. A rescue gate needs ``n_cap``, ``t_on_s`` and ``pause_at_turns``, open-loop arrivals, and
    ``meta.arm`` rescue (or "" outside a paired set); ``meta.arm`` rescue needs ``gate.mode`` rescue."""
    g = cfg.gate
    if g.mode not in ("static", "rescue"):
        raise ValueError(f"gate.mode must be static|rescue, got {g.mode!r}")
    if g.mode == "static":
        set_keys = [k for k in _GATE_RESCUE_KEYS if getattr(g, k) is not None]
        if set_keys:
            raise ValueError(f"gate.{', gate.'.join(set_keys)} only apply to gate.mode=rescue (mode is static)")
        if cfg.meta.arm == "rescue":
            raise ValueError("meta.arm=rescue needs gate.mode=rescue")
        return
    if cfg.meta.arm not in ("", "rescue"):
        raise ValueError(f"gate.mode=rescue is the rescue arm; meta.arm must be rescue (or ''), got {cfg.meta.arm!r}")
    if g.n_cap is None:
        raise ValueError("gate.mode=rescue requires gate.n_cap (the cap engaged at t_on_s)")
    if cfg.arrivals.kind == "closed":
        raise ValueError("gate.mode=rescue is for open-loop arrivals")
    if g.t_on_s is None or not _num(g.t_on_s) or g.t_on_s < 0:
        raise ValueError(f"gate.mode=rescue requires gate.t_on_s >= 0 (seconds since run start), got {g.t_on_s!r}")
    if not isinstance(g.pause_at_turns, bool):
        raise ValueError(f"gate.mode=rescue requires gate.pause_at_turns true|false, got {g.pause_at_turns!r}")
    for k in ("release_hold_s", "min_on_s"):
        v = getattr(g, k)
        if v is not None and (not _num(v) or v < 0):
            raise ValueError(f"gate.{k} must be a number >= 0, got {v!r}")
    v = g.release_check_s
    if v is not None and (not _num(v) or v <= 0):
        raise ValueError(f"gate.release_check_s must be a positive number, got {v!r}")


def gate_rescue_params(g: GateCfg) -> Dict[str, Any]:
    """The effective rescue parameters (defaults filled in), as recorded in meta.json."""
    out: Dict[str, Any] = {"mode": g.mode, "n_cap_configured": g.n_cap}
    if g.mode == "rescue":
        out.update(t_on_s=float(g.t_on_s), pause_at_turns=bool(g.pause_at_turns))
        for k, d in GATE_RESCUE_DEFAULTS.items():
            v = getattr(g, k)
            out[k] = float(d if v is None else v)
    return out


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


def resolve_uncached_tokens_ref(a: ArrivalsCfg, base_dir: Optional[Path] = None) -> Optional[float]:
    """``arrivals.uncached_tokens_ref`` as a positive float (None if unset). A configured but unresolvable reference (e.g.
    the placeholder in configs/agentload_e2_burst.yaml) raises: the run would be unjudgeable by the token-unit criterion."""
    if a.uncached_tokens_ref is None:
        return None
    v = float(resolve_lambda_ref(a.uncached_tokens_ref, base_dir))
    if not (v == v and v > 0):
        raise ValueError(f"arrivals.uncached_tokens_ref resolved to {v!r}: need a positive tokens/s value")
    return v


def resolve_n_cap(g: GateCfg, base_dir: Optional[Path] = None) -> Optional[int]:
    """The gate's session cap as an int (None = no gate). ``"path:key"`` reads a top-level numeric ``key`` from a JSON
    file (the Stage-C ``mu_curve.json:n_cap``); a non-integer or non-positive value is an error, not rounded."""
    if g.n_cap is None:
        return None
    v = float(resolve_lambda_ref(g.n_cap, base_dir))
    if v != v or v < 1 or abs(v - round(v)) > 1e-9:
        raise ValueError(f"gate.n_cap resolved to {v!r}: need a positive integer (is the Stage-C n_cap null?)")
    return int(round(v))


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
