"""Mock OpenAI-compatible server with a simulated prefix cache, for local end-to-end tests.

NOT a model of any real engine's performance; it only has the *structure* needed to test the harness:

* ``POST /v1/completions`` accepts ``prompt`` as a token-id list or a string (whitespace-split words are the
  "tokens"), ``max_tokens`` and ``ignore_eos``; returns exactly ``max_tokens`` output units.
* Prefix cache: one entry per session (keyed by the first ``key_prefix_len`` prompt units), LRU over
  sessions, capacity ``kv_capacity_tokens``. The hit length is the common prefix of the new prompt and the
  stored prompt+output, capped at ``len(prompt)-1``. Lookup happens at ADMISSION (waiting requests do not pin
  their entries), as in the simulator.
* Latency: FIFO ``slots`` parallel slots; service time = fixed + per_uncached_prompt_token * uncached
  + per_completion_token * max_tokens (``asyncio.sleep``). Running requests' KV is not counted against capacity.
* Reports ``cached_tokens`` in the format selected by ``cached_style`` (usage | choice_meta | none) and
  Prometheus metrics named like vLLM (``vllm:*``) or SGLang (``sglang:*``) according to ``metrics_style``.
* ``GET /stats`` returns ground-truth counters (used by tests), ``POST /flush_cache`` empties the cache,
  ``GET /health``, ``GET /v1/models``.

Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import asyncio
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from aiohttp import web


@dataclass
class MockConfig:
    kv_capacity_tokens: int = 200_000
    slots: int = 8
    fixed_s: float = 0.002
    per_uncached_token_s: float = 2e-6
    per_completion_token_s: float = 2e-4
    key_prefix_len: int = 8
    cached_style: str = "usage"          # usage | choice_meta | none
    metrics_style: str = "vllm"          # vllm | sglang
    fail_every_n: int = 0                # return HTTP 500 for every n-th request (0 = never)
    model_name: str = "mock"
    host: str = "127.0.0.1"
    port: int = 0
    log_requests: bool = False           # keep the last prompts seen (tests inspect growth / prefixes)


def to_units(prompt: Any) -> np.ndarray:
    """Prompt -> integer units: token ids as is; text -> crc32 of each whitespace-separated word."""
    if isinstance(prompt, str):
        return np.array([zlib.crc32(w.encode()) for w in prompt.split()], dtype=np.int64)
    if isinstance(prompt, list) and prompt and isinstance(prompt[0], list):
        prompt = prompt[0]                     # batch of one
    return np.asarray(prompt, dtype=np.int64)


def common_prefix_len(a: np.ndarray, b: np.ndarray) -> int:
    n = min(len(a), len(b))
    if n == 0:
        return 0
    neq = np.nonzero(a[:n] != b[:n])[0]
    return int(neq[0]) if len(neq) else n


class MockEngine:
    def __init__(self, cfg: MockConfig):
        self.cfg = cfg
        self.cache: "OrderedDict[bytes, np.ndarray]" = OrderedDict()
        self.used = 0
        self.slots = asyncio.Semaphore(cfg.slots)
        self.waiting = 0
        self.running = 0
        self.n_requests = 0
        self.stats: Dict[str, float] = {"requests": 0, "prompt_tokens": 0, "cached_tokens": 0, "completed": 0,
                                        "evictions": 0, "max_waiting": 0, "errors_injected": 0,
                                        "first_turn_like_misses": 0}
        self.seen: List[np.ndarray] = []

    def _key(self, units: np.ndarray) -> bytes:
        return units[: self.cfg.key_prefix_len].tobytes()

    def lookup(self, units: np.ndarray) -> int:
        """Admission-time lookup; touches LRU on a (partial) hit. Returns cached token count."""
        k = self._key(units)
        ent = self.cache.get(k)
        if ent is None:
            return 0
        self.cache.move_to_end(k)
        return min(common_prefix_len(units, ent), max(len(units) - 1, 0))

    def store(self, units: np.ndarray, out_units: np.ndarray) -> None:
        k = self._key(units)
        full = np.concatenate([units, out_units])
        old = self.cache.pop(k, None)
        if old is not None:
            self.used -= len(old)
        self.cache[k] = full
        self.used += len(full)
        while self.used > self.cfg.kv_capacity_tokens and len(self.cache) > 1:
            kk, ent = next(iter(self.cache.items()))
            if kk == k:
                self.cache.move_to_end(kk)
                continue
            self.cache.popitem(last=False)
            self.used -= len(ent)
            self.stats["evictions"] += 1

    def flush(self) -> None:
        self.cache.clear()
        self.used = 0

    def output_units(self, units: np.ndarray, n: int) -> np.ndarray:
        """Deterministic pseudo-output: function of the prompt's last 8 units."""
        seed = zlib.crc32(units[-8:].tobytes())
        return np.random.default_rng(seed).integers(1000, 100000, size=n, dtype=np.int64)

    def prom_text(self) -> str:
        c, s = self.cfg, self.stats
        if c.metrics_style == "vllm":
            lab = f'{{model_name="{c.model_name}",engine="0"}}'
            return (
                "# HELP vllm:num_requests_running Number of requests in model execution batches.\n"
                "# TYPE vllm:num_requests_running gauge\n"
                f"vllm:num_requests_running{lab} {self.running}.0\n"
                f"vllm:num_requests_waiting{lab} {self.waiting}.0\n"
                f"vllm:kv_cache_usage_perc{lab} {self.used / max(c.kv_capacity_tokens, 1):.6f}\n"
                f"vllm:prefix_cache_queries_total{lab} {int(s['prompt_tokens'])}.0\n"
                f"vllm:prefix_cache_hits_total{lab} {int(s['cached_tokens'])}.0\n"
                f'vllm:e2e_request_latency_seconds_bucket{{le="1.0",model_name="{c.model_name}"}} 3.0\n'
                f'vllm:e2e_request_latency_seconds_count{lab} {int(s["completed"])}.0\n'
                "python_gc_objects_collected_total{generation=\"0\"} 17.0\n")
        lab = f'{{model_name="{c.model_name}"}}'
        hit = s["cached_tokens"] / s["prompt_tokens"] if s["prompt_tokens"] else 0.0
        return (
            "# TYPE sglang:num_running_reqs gauge\n"
            f"sglang:num_running_reqs{lab} {self.running}.0\n"
            f"sglang:num_queue_reqs{lab} {self.waiting}.0\n"
            f"sglang:token_usage{lab} {self.used / max(c.kv_capacity_tokens, 1):.6f}\n"
            f"sglang:cache_hit_rate{lab} {hit:.6f}\n")


ENGINE_KEY: "web.AppKey[MockEngine]" = web.AppKey("engine", MockEngine)


def _make_app(cfg: MockConfig) -> web.Application:
    eng = MockEngine(cfg)
    app = web.Application()
    app[ENGINE_KEY] = eng

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def models(_: web.Request) -> web.Response:
        return web.json_response({"object": "list", "data": [{"id": cfg.model_name, "object": "model"}]})

    async def metrics(_: web.Request) -> web.Response:
        return web.Response(text=eng.prom_text(), content_type="text/plain")

    async def stats(_: web.Request) -> web.Response:
        return web.json_response({**eng.stats, "cache_entries": len(eng.cache), "cache_used_tokens": eng.used})

    async def flush(_: web.Request) -> web.Response:
        eng.flush()
        return web.json_response({"flushed": True})

    async def completions(request: web.Request) -> web.Response:
        body = await request.json()
        eng.n_requests += 1
        if cfg.fail_every_n and eng.n_requests % cfg.fail_every_n == 0:
            eng.stats["errors_injected"] += 1
            return web.json_response({"error": "injected failure"}, status=500)
        units = to_units(body["prompt"])
        is_text = isinstance(body["prompt"], str)
        n_out = int(body.get("max_tokens", 16))
        eng.stats["requests"] += 1
        eng.waiting += 1
        eng.stats["max_waiting"] = max(eng.stats["max_waiting"], eng.waiting)
        try:
            await eng.slots.acquire()
        except BaseException:
            eng.waiting -= 1
            raise
        eng.waiting -= 1
        eng.running += 1
        try:
            cached = eng.lookup(units)                          # admission-time lookup
            service = cfg.fixed_s + cfg.per_uncached_token_s * (len(units) - cached) + cfg.per_completion_token_s * n_out
            await asyncio.sleep(service)
            out = eng.output_units(units, n_out)
            if is_text:
                out_text = "".join(f" m{int(u) % 1000}" for u in out)
                out_units = to_units(out_text)
            else:
                out_text = " ".join(f"t{int(u)}" for u in out[:8])
                out_units = out
            eng.store(units, out_units)
            eng.stats["prompt_tokens"] += len(units)
            eng.stats["cached_tokens"] += cached
            eng.stats["completed"] += 1
            if cfg.log_requests:
                eng.seen.append(units)
        finally:
            eng.running -= 1
            eng.slots.release()
        choice: Dict[str, Any] = {"index": 0, "text": out_text, "finish_reason": "length"}
        if body.get("return_token_ids") and not is_text:
            choice["token_ids"] = [int(u) for u in out_units]
        usage: Dict[str, Any] = {"prompt_tokens": int(len(units)), "completion_tokens": n_out,
                                 "total_tokens": int(len(units)) + n_out}
        data: Dict[str, Any] = {"id": f"cmpl-{eng.n_requests}", "object": "text_completion",
                                "model": cfg.model_name, "choices": [choice], "usage": usage}
        if cfg.cached_style == "usage":
            usage["prompt_tokens_details"] = {"cached_tokens": int(cached)}
        elif cfg.cached_style == "choice_meta":
            choice["meta_info"] = {"cached_tokens": int(cached), "e2e_latency": service}
        return web.json_response(data)

    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_get("/metrics", metrics)
    app.router.add_get("/stats", stats)
    app.router.add_post("/flush_cache", flush)
    app.router.add_post("/v1/completions", completions)
    return app


class MockServer:
    """Async context manager: ``async with MockServer(cfg) as srv: srv.url``."""

    def __init__(self, cfg: Optional[MockConfig] = None):
        self.cfg = cfg or MockConfig()
        self.runner: Optional[web.AppRunner] = None
        self.url = ""
        self.engine: Optional[MockEngine] = None

    async def __aenter__(self) -> "MockServer":
        app = _make_app(self.cfg)
        self.engine = app[ENGINE_KEY]
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.cfg.host, self.cfg.port)
        await site.start()
        port = self.runner.addresses[0][1]
        self.url = f"http://{self.cfg.host}:{port}"
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self.runner:
            await self.runner.cleanup()


def main(argv: Optional[Sequence[str]] = None) -> int:
    import yaml
    ap = argparse.ArgumentParser(description="Mock OpenAI-compatible server with a simulated prefix cache")
    ap.add_argument("--config", default=None, help="YAML with MockConfig fields (under key 'mock_server')")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--set", action="append", default=[], help="MockConfig field override, e.g. slots=4")
    args = ap.parse_args(argv)
    d: Dict[str, Any] = {}
    if args.config:
        d = (yaml.safe_load(open(args.config)) or {}).get("mock_server", {})
    for item in args.set:
        k, v = item.split("=", 1)
        d[k] = yaml.safe_load(v)
    if args.port is not None:
        d["port"] = args.port
    cfg = MockConfig(**d)

    async def _serve() -> None:
        async with MockServer(cfg) as srv:
            print(f"mock server listening on {srv.url}", flush=True)
            await asyncio.Event().wait()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
