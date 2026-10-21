"""Start-state verification (agentload.canary): the cache flush is judged by its effect, not by an HTTP status."""
import asyncio

import aiohttp
import pytest

from agentload.canary import (EXIT_FAIL, EXIT_OK, EXIT_UNVERIFIABLE, canary_ids, idle_state, run_canary)
from agentload.config import config_from_dict
from agentload.mock_server import MockConfig, MockServer
from conftest import make_raw

FAST = dict(kv_capacity_tokens=10**7, slots=8, fixed_s=0.001, per_uncached_token_s=0, per_completion_token_s=0)


def cfg_for(url, **canary):
    raw = make_raw()
    raw["server"]["base_url"] = url
    raw["canary"] = {"idle_wait_s": 3.0, "idle_poll_s": 0.1, **canary}
    return config_from_dict(raw)


async def flush(url):
    async with aiohttp.ClientSession() as h:
        async with h.post(url + "/flush_cache") as r:
            return r.status


def go(mock_cfg, scenario):
    async def main():
        async with MockServer(mock_cfg) as srv:
            return await scenario(srv)
    return asyncio.run(main())


def test_a_real_flush_passes_prime_and_check():
    async def sc(srv):
        cfg = cfg_for(srv.url)
        rc1, prime = await run_canary(cfg, "prime", 1, True)
        assert await flush(srv.url) == 200
        rc2, chk = await run_canary(cfg, "check", 1, True, prime)
        return rc1, prime, rc2, chk
    rc1, prime, rc2, chk = go(MockConfig(**FAST), sc)
    assert rc1 == EXIT_OK and prime["second"]["cached_tokens"] >= 512 and prime["first"]["cached_tokens"] == 0
    assert rc2 == EXIT_OK and chk["after_flush"]["cached_tokens"] == 0 and chk["idle"]["idle"] is True


def test_a_flush_that_returns_200_without_emptying_the_cache_fails_the_check():
    async def sc(srv):
        cfg = cfg_for(srv.url)
        rc1, prime = await run_canary(cfg, "prime", 2, True)
        assert await flush(srv.url) == 200                    # HTTP 200, cache untouched
        rc2, chk = await run_canary(cfg, "check", 2, True, prime)
        return rc1, rc2, chk
    rc1, rc2, chk = go(MockConfig(flush_is_noop=True, **FAST), sc)
    assert rc1 == EXIT_OK and rc2 == EXIT_FAIL
    assert chk["after_flush"]["cached_tokens"] >= 1000 and "still cached after flush" in chk["reason"] and chk["ok"] is False


def test_the_check_must_use_the_primed_canary():
    async def sc(srv):
        cfg = cfg_for(srv.url)
        rc, _ = await run_canary(cfg, "prime", 3, True)
        await flush(srv.url)
        rc2, chk = await run_canary(cfg, "check", 4, True, None)      # a different canary: also a miss, trivially
        return chk
    chk = go(MockConfig(flush_is_noop=True, **FAST), sc)
    assert chk["ok"] is True                                         # salt 4 was never primed: why salts must match
    cfg = cfg_for("http://x")
    assert canary_ids(cfg, 3) == canary_ids(cfg, 3) and canary_ids(cfg, 3) != canary_ids(cfg, 4)
    assert len(canary_ids(cfg, 3)) == 1024


def test_an_engine_without_cached_tokens_is_unverifiable_not_ok():
    async def sc(srv):
        cfg = cfg_for(srv.url)
        return await run_canary(cfg, "prime", 5, True)
    rc, res = go(MockConfig(cached_style="none", **FAST), sc)
    assert rc == EXIT_UNVERIFIABLE and "no cached_tokens" in res["reason"]


def test_prime_requires_the_cache_to_hold_the_canary():
    async def sc(srv):
        cfg = cfg_for(srv.url, resident_min_frac=2.0)             # impossible: the 2nd request cannot cache > 100% of it
        return await run_canary(cfg, "prime", 6, True)
    rc, res = go(MockConfig(**FAST), sc)
    assert rc == EXIT_UNVERIFIABLE and "cache not working" in res["reason"] and res["second"]["cached_tokens"] >= 1000


def test_cache_disabled_engines_only_get_the_idle_check():
    async def sc(srv):
        cfg = cfg_for(srv.url)
        return await run_canary(cfg, "prime", 7, False), await run_canary(cfg, "check", 7, False)
    (rc1, r1), (rc2, r2) = go(MockConfig(**FAST), sc)
    assert rc1 == rc2 == EXIT_OK and "first" not in r1 and "after_flush" not in r2 and "idle verified" in r1["reason"]


def test_a_busy_engine_is_not_idle():
    async def sc(srv):
        cfg = cfg_for(srv.url, idle_wait_s=0.6)
        async with aiohttp.ClientSession() as h:
            body = {"model": "mock", "prompt": list(range(2000, 2300)), "max_tokens": 300, "ignore_eos": True}
            t = asyncio.create_task(h.post(srv.url + "/v1/completions", json=body))
            await asyncio.sleep(0.3)
            out = await run_canary(cfg, "prime", 8, True)
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
        return out
    rc, res = go(MockConfig(kv_capacity_tokens=10**7, slots=8, fixed_s=0.0, per_uncached_token_s=0,
                            per_completion_token_s=0.05), sc)
    assert rc == EXIT_FAIL and "did not become idle" in res["reason"]
    assert res["idle"]["running"]["value"] >= 1 and res["idle"]["idle"] is False        # the running gauge was read


def test_idle_state_from_metrics_text():
    cfg = cfg_for("http://x")
    idle = 'vllm:num_requests_running{m="a"} 0.0\nvllm:num_requests_waiting{m="a"} 0.0\nvllm:kv_cache_usage_perc{m="a"} 0.0\n'
    assert idle_state(idle, cfg)["idle"] is True and idle_state(idle, cfg)["n_categories_known"] == 3
    busy = idle.replace("waiting{m=\"a\"} 0.0", "waiting{m=\"a\"} 3.0")
    assert idle_state(busy, cfg)["idle"] is False
    kv = idle.replace("perc{m=\"a\"} 0.0", "perc{m=\"a\"} 0.4")
    assert idle_state(kv, cfg)["idle"] is False
    sg = "sglang:num_running_reqs 0\nsglang:num_queue_reqs 0\nsglang:token_usage 0.0\n"
    assert idle_state(sg, cfg)["idle"] is True
    unknown = idle_state("some_other_metric 1\n", cfg)
    assert unknown["idle"] is True and unknown["n_categories_known"] == 0          # unknown categories do not fail
    # two engines' label sets are summed
    two = 'vllm:num_requests_waiting{e="0"} 0.0\nvllm:num_requests_waiting{e="1"} 2.0\n'
    assert idle_state(two, cfg)["waiting"]["value"] == 2.0
