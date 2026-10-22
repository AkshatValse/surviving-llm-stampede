"""Periodic scrape of the engine's Prometheus ``/metrics`` endpoint into a long-format CSV.

Rows: ``t_s`` (seconds since run start), ``name``, ``labels`` (raw ``{...}`` string), ``value``. Names are
filtered by prefix (default ``vllm:`` and ``sglang:``) and histogram ``_bucket`` samples are dropped, so no
metric name has to be known in advance. The first scrape's raw text is saved (``metrics_first.txt``) so the
real metric names can be inspected after the first Nova test job; the last one is saved too.
Client-side gauges (in-flight requests, active sessions) are logged each tick under the ``agentload:`` prefix,
together with scrape success/latency, so a queue proxy exists even if the engine exposes nothing.
"""
from __future__ import annotations

import asyncio
import csv
import time
from pathlib import Path
from typing import Callable, Dict, Optional, TextIO

import aiohttp

from .config import MetricsCfg
from .parse import parse_prometheus


class MetricsPoller:
    def __init__(self, http: aiohttp.ClientSession, url: str, cfg: MetricsCfg, out_dir: Path,
                 now: Callable[[], float], client_gauges: Optional[Callable[[], Dict[str, float]]] = None):
        self.http, self.url, self.cfg, self.out_dir = http, url, cfg, out_dir
        self.now = now
        self.client_gauges = client_gauges
        self.n_scrapes = 0
        self.n_failures = 0
        self.n_skipped_ticks = 0               # ticks dropped because a scrape overran the interval
        self.first_scrape_unix: Optional[float] = None    # wall clock of the first scrape (aligns with server logs)
        self.first_scrape_t_s: Optional[float] = None
        self._fh: Optional[TextIO] = None
        self._w: Optional[csv.writer] = None
        self._first_saved = False
        self._last_text: Optional[str] = None

    def open(self) -> None:
        self._fh = open(self.out_dir / "metrics.csv", "w", newline="")
        self._w = csv.writer(self._fh)
        self._w.writerow(["t_s", "name", "labels", "value"])

    def close(self) -> None:
        if self._last_text is not None:
            (self.out_dir / "metrics_last.txt").write_text(self._last_text)
        if self._fh:
            self._fh.close()
            self._fh = None

    async def scrape_once(self) -> None:
        assert self._w is not None
        t = self.now()
        if self.first_scrape_unix is None:
            self.first_scrape_unix, self.first_scrape_t_s = time.time(), t
        t_req = time.monotonic()
        ok = 0.0
        try:
            async with self.http.get(self.url, timeout=aiohttp.ClientTimeout(total=self.cfg.timeout_s)) as r:
                body = await r.text()
                if r.status == 200:
                    ok = 1.0
                    for name, labels, v in parse_prometheus(body, self.cfg.prefixes, self.cfg.drop_suffixes):
                        self._w.writerow([f"{t:.3f}", name, labels, repr(v)])
                    if not self._first_saved:
                        (self.out_dir / "metrics_first.txt").write_text(body)
                        self._first_saved = True
                    self._last_text = body
        except asyncio.CancelledError:
            raise
        except Exception:
            ok = 0.0
        self.n_scrapes += 1
        if not ok:
            self.n_failures += 1
        self._w.writerow([f"{t:.3f}", "agentload:scrape_ok", "", repr(ok)])
        self._w.writerow([f"{t:.3f}", "agentload:scrape_latency_s", "", repr(time.monotonic() - t_req)])
        if self.client_gauges:
            for k, v in self.client_gauges().items():
                self._w.writerow([f"{t:.3f}", k, "", repr(float(v))])
        if self.n_scrapes % 6 == 0 and self._fh:
            self._fh.flush()

    async def run(self) -> None:
        """Scrape every ``interval_s`` (fixed-rate schedule, no drift; overrun ticks are skipped and counted)."""
        loop = asyncio.get_running_loop()
        nxt = loop.time()
        try:
            while True:
                await self.scrape_once()
                nxt += self.cfg.interval_s
                now = loop.time()
                if nxt < now:             # the scrape overran the interval: skip the missed ticks, do not burst-catch-up
                    self.n_skipped_ticks += int((now - nxt) // self.cfg.interval_s) + 1
                    nxt = now + self.cfg.interval_s
                await asyncio.sleep(max(0.0, nxt - now))
        except asyncio.CancelledError:
            pass
