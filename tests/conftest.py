"""Shared test helpers: tiny configs, an in-process mock server, and a one-call generator run."""
from __future__ import annotations

import asyncio
import copy
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import pytest

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

from agentload.client import LoadGenerator, Outcome, write_plan_csv
from agentload.config import Config, config_from_dict
from agentload.mock_server import MockConfig, MockServer
from agentload.runmeta import git_info, new_result_dir

REPO = Path(__file__).resolve().parent.parent

BASE_CFG: Dict[str, Any] = {
    "research_question": "test",
    "server": {"base_url": "http://127.0.0.1:1", "model": "mock", "request_timeout_s": 30,
               "extra_body": {"ignore_eos": True}, "request_token_ids": True},
    "workload": {"prompt_mode": "tokens", "initial_context_tokens": 100, "new_prompt_tokens": 30,
                 "decode_tokens": 6, "mean_turns": 3, "max_turns": 6, "tool_time_mean_s": 0.1,
                 "tool_time_dist": "exp"},
    "arrivals": {"kind": "constant", "rate": 5.0},
    "run": {"duration_s": 4.0, "seed": 0, "max_inflight": 500, "max_errors": 50, "preflight_wait_s": 3},
    "metrics": {"enabled": True, "interval_s": 0.5},
    "meta": {"hardware": "Apple M3 Max CPU (simulation)", "engine_label": "mock-test"},
    "output": {"root": "results", "name": "agentload_test"},
}


def make_raw(**sections: Dict[str, Any]) -> Dict[str, Any]:
    """BASE_CFG with per-section dict updates, e.g. make_raw(run={"duration_s": 2})."""
    raw = copy.deepcopy(BASE_CFG)
    for k, v in sections.items():
        if isinstance(v, dict) and isinstance(raw.get(k), dict):
            raw[k].update(v)
        else:
            raw[k] = v
    return raw


async def _run(raw: Dict[str, Any], mock_cfg: MockConfig, out_root: Path, hook: Optional[Callable[..., Awaitable]]
               ) -> Tuple[Outcome, Dict[str, Any], MockServer]:
    async with MockServer(mock_cfg) as srv:
        raw = copy.deepcopy(raw)
        raw["server"]["base_url"] = srv.url
        raw["output"]["root"] = str(out_root)
        cfg: Config = config_from_dict(raw)
        git = git_info(REPO)
        t_start = datetime.now()
        out_dir = new_result_dir(cfg.output.root, cfg.output.name)
        (out_dir / "config.yaml").write_text("research_question: test\n")
        import yaml
        (out_dir / "config_effective.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
        gen = LoadGenerator(cfg, raw, out_dir, REPO)
        plan = gen.build_plan()
        write_plan_csv(out_dir / "plan.csv", plan)
        outcome = await gen.run(["pytest"], git, t_start, plan)
        stats = srv.engine.stats if srv.engine else {}
        seen = list(srv.engine.seen) if srv.engine else []
        return outcome, {"stats": dict(stats), "seen": seen, "cache_entries": len(srv.engine.cache)}, srv


def run_gen(raw: Dict[str, Any], mock_cfg: Optional[MockConfig], out_root: Path
            ) -> Tuple[Outcome, Dict[str, Any]]:
    """Run the generator against a fresh in-process mock server; returns (outcome, mock ground truth)."""
    mc = mock_cfg or MockConfig(kv_capacity_tokens=10_000_000, slots=16, fixed_s=0.001, per_uncached_token_s=1e-6,
                                per_completion_token_s=1e-4, log_requests=True)
    out, truth, _ = asyncio.run(_run(raw, mc, out_root, None))
    return out, truth


@pytest.fixture
def tmp_results(tmp_path: Path) -> Path:
    return tmp_path / "results"
